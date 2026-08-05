#!/usr/bin/env python3
"""Aggregate a batch of DailyBench run folders into MobileWorld-style metrics.

Computes Success Rate (overall + per bucket + interaction vs GUI-only), Average
Completion Steps, Average User Queries, and User Interaction Quality (UIQ) from
arXiv:2512.19432 (MobileWorld), excluding the MCP metric by design.

Each run folder contributes:
  output.json          -> success, steps
  run_metrics.json     -> ask_user_call_count (falls back to counting the lines
                          in ask_user_metrics.jsonl for older runs)
  meta.json            -> model, label, task_id (task_id may be absent on older
                          runs; it is then reconstructed from --label)

Interaction (ASK USER) tasks are identified by task_id membership in the ask_user_facts
sidecar for the runs' source: `--source tasks.md` (default) selects
benchmarks/dailyBench-600/ask_user_facts_730.json, `--source public.md` selects
benchmarks/dailyBench-600/ask_user_facts.json (overridable via --ask-user-facts).

Usage:
  uv run scripts/dailybench_report.py --runs runs/2026-08-01-001234
  uv run scripts/dailybench_report.py --model qwen/qwen3.6-plus
"""

from __future__ import annotations

import argparse
import glob
import json
import re
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from DailyBench.benchmark_metrics import (
    avg_steps,
    avg_user_queries,
    success_rate,
    user_interaction_quality,
    user_interaction_quality_factmatch,
)
from DailyBench.task_batch import load_ask_user_facts
from DailyBench.task_dataset import ask_user_facts_path

# Matches both the older flat layout `runs/<batch>/<run-folder>` and the newer
# per-day layout `runs/<batch>/<day>/<run-folder>` by walking for output.json.
DEFAULT_RUNS = "runs/**"
DEFAULT_SOURCE = "tasks.md"
REP_SUFFIX_RE = re.compile(r"-rep\d+$")


def _read_json(path: Path) -> dict[str, Any] | None:
    """Read a JSON file, returning None for missing/corrupt files."""
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def _count_jsonl_lines(path: Path) -> int:
    """Count non-empty lines in a JSONL file (0 when missing)."""
    if not path.exists():
        return 0
    return sum(1 for line in path.open("r", encoding="utf-8") if line.strip())


_TOKEN_RE = re.compile(r"[a-z0-9]+")


def _normalize_tokens(text: str) -> set[str]:
    """Lowercase alphanumeric tokens of a string ('' -> empty set)."""
    return set(_TOKEN_RE.findall((text or "").lower()))


def _answers_match(answer: str, fact: str) -> bool:
    """True when the simulated user's answer contains the ground-truth fact.

    Digit-bearing tokens (dates/times) are the strong signal: the fact's digit
    tokens must all appear in the answer. Otherwise fall back to a 60% token
    overlap against the fact.
    """
    answer_tokens = _normalize_tokens(answer)
    fact_tokens = _normalize_tokens(fact)
    if not answer_tokens or not fact_tokens:
        return False
    fact_digits = {token for token in fact_tokens if any(char.isdigit() for char in token)}
    answer_digits = {token for token in answer_tokens if any(char.isdigit() for char in token)}
    if fact_digits and answer_digits:
        return fact_digits.issubset(answer_digits)
    overlap = len(answer_tokens & fact_tokens)
    return overlap / len(fact_tokens) >= 0.6


def _count_correct_ask_user(run_dir: Path, fact: str | None) -> int:
    """# ask_user calls whose returned answer matched the task's ground-truth fact.

    Reads the per-run ask_user_metrics.jsonl and compares each ``response`` to
    the fact. A question whose answer matched the fact counts as a "right
    question" even if the overall task failed.
    """
    if not fact:
        return 0
    log = run_dir / "ask_user_metrics.jsonl"
    if not log.exists():
        return 0
    correct = 0
    for line in log.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            entry = json.loads(line)
        except json.JSONDecodeError:
            continue
        if _answers_match(entry.get("response") or "", fact):
            correct += 1
    return correct


def parse_task_id_from_label(label: str) -> str | None:
    """Reconstruct a dataset task_id from a run --label like `day1--easy-gmail-001`.

    The label format (see task_batch.run_label) is
    `{sub}--{bucket}-{app_slug}-{num:03d}` with an optional `-repNN` suffix for
    repeats. Returns None when the label doesn't parse.
    """
    label = REP_SUFFIX_RE.sub("", (label or "").strip())
    if "--" not in label:
        return None
    _, rest = label.split("--", 1)
    tokens = rest.split("-")
    if len(tokens) < 3:
        return None
    bucket, number = tokens[0], tokens[-1]
    app_slug = "-".join(tokens[1:-1])
    if not bucket or not app_slug or not number.isdigit():
        return None
    return f"{bucket}__{app_slug}__{int(number):03d}"


def discover_run_folders(runs_arg: str | None) -> list[Path]:
    """Return run folders (dirs containing output.json) under a path or glob.

    Walks for `output.json` so it works with both the flat layout
    `runs/<batch>/<run-folder>` and the per-day layout
    `runs/<batch>/<day>/<run-folder>`.
    """
    if runs_arg:
        if any(char in runs_arg for char in "*?["):
            candidates = [Path(path) for path in glob.glob(runs_arg, recursive=True)]
            return sorted(path for path in candidates if path.is_dir() and (path / "output.json").exists())
        path = Path(runs_arg)
        if not path.is_dir():
            raise SystemExit(f"--runs path not found: {runs_arg}")
        return sorted(p.parent for p in path.rglob("output.json") if p.parent.is_dir())
    root = Path("runs")
    if not root.is_dir():
        return []
    return sorted(p.parent for p in root.rglob("output.json") if p.parent.is_dir())


def load_run_record(
    run_dir: Path, interaction_ids: set[str], facts: dict[str, str] | None = None
) -> dict[str, Any]:
    """Load one run folder into a benchmark_metrics record dict.

    ``facts`` (task_id -> ground-truth fact, from ask_user_facts) lets the record
    also carry ``ask_user_correct``: the number of ask_user calls whose answer
    matched the ground truth (used by the success-free UIQ).
    """
    output = _read_json(run_dir / "output.json") or {}
    meta = _read_json(run_dir / "meta.json") or {}
    run_metrics = _read_json(run_dir / "run_metrics.json") or {}

    ask_user_calls = run_metrics.get("ask_user_call_count")
    if ask_user_calls is None:
        ask_user_calls = _count_jsonl_lines(run_dir / "ask_user_metrics.jsonl")

    task_id = meta.get("task_id") or parse_task_id_from_label(meta.get("label", ""))
    bucket = task_id.split("__", 1)[0] if task_id else None
    is_interaction = bool(task_id in interaction_ids) if task_id else False
    ask_user_calls = int(ask_user_calls or 0)
    success = bool(output.get("success"))
    # ASK USER (interaction) tasks only count as a success if the agent actually
    # asked the user for the missing fact. An agent that guesses instead gets 0 -
    # mirrors MobileWorld's q_i = s_i / c_i (c_i = 0 -> q_i = 0).
    if is_interaction and ask_user_calls == 0:
        success = False

    fact = (facts or {}).get(task_id) if task_id else None
    ask_user_correct = _count_correct_ask_user(run_dir, fact) if is_interaction else 0

    return {
        "run_dir": str(run_dir),
        "label": meta.get("label"),
        "model": meta.get("model"),
        "task_id": task_id,
        "bucket": bucket,
        "success": success,
        "steps": int(output.get("steps") or 0),
        "ask_user_calls": ask_user_calls,
        "ask_user_correct": ask_user_correct,
        "is_interaction": is_interaction,
    }


def build_report(records: list[dict[str, Any]], *, model: str | None = None) -> dict[str, Any]:
    """Compute MobileWorld-style metrics (MCP excluded) over a batch of records."""
    if model:
        records = [record for record in records if record.get("model") == model]
    buckets = sorted({record["bucket"] for record in records if record.get("bucket")})
    interaction = [record for record in records if record["is_interaction"]]
    gui_only = [record for record in records if not record["is_interaction"]]
    return {
        "run_count": len(records),
        "model_filter": model,
        "success_rate": success_rate(records),
        "success_rate_by_bucket": {bucket: success_rate([r for r in records if r["bucket"] == bucket]) for bucket in buckets},
        "interaction_success_rate": success_rate(interaction),
        "gui_only_success_rate": success_rate(gui_only),
        "average_steps": avg_steps(records),
        "average_user_queries": avg_user_queries(records),
        "user_interaction_quality": user_interaction_quality(records),
        "user_interaction_quality_factmatch": user_interaction_quality_factmatch(records),
        "interaction_run_count": len(interaction),
        "gui_only_run_count": len(gui_only),
    }


def render_markdown(report: dict[str, Any]) -> str:
    """Render the report as a compact Markdown table."""
    lines = [
        "# DailyBench batch report (MobileWorld metrics, no MCP)",
        "",
        f"- runs: {report['run_count']}  ·  model: {report['model_filter'] or 'all'}",
        "",
        "| metric | value |",
        "|---|---|",
        f"| Success Rate | {report['success_rate']:.1%} |",
        f"| Success Rate (interaction / ASK USER) | {report['interaction_success_rate']:.1%} ({report['interaction_run_count']} runs) |",
        f"| Success Rate (GUI-only) | {report['gui_only_success_rate']:.1%} ({report['gui_only_run_count']} runs) |",
        f"| Average Completion Steps | {report['average_steps']:.2f} |",
        f"| Average User Queries | {report['average_user_queries']:.2f} |",
        f"| User Interaction Quality (UIQ, success-gated) | {report['user_interaction_quality']:.3f} |",
        f"| User Interaction Quality (UIQ, success-free fact-match) | {report['user_interaction_quality_factmatch']:.3f} |",
        "",
        "### Success rate by bucket",
        "",
    ]
    by_bucket = report.get("success_rate_by_bucket") or {}
    if by_bucket:
        lines.append("| bucket | success rate |")
        lines.append("|---|---|")
        for bucket, rate in by_bucket.items():
            lines.append(f"| {bucket} | {rate:.1%} |")
    else:
        lines.append("*(no bucket breakdown — runs lack a recognizable task_id)*")
    return "\n".join(lines) + "\n"


def build_parser() -> argparse.ArgumentParser:
    """Build the CLI parser."""
    parser = argparse.ArgumentParser(description="Aggregate a batch of run folders into MobileWorld-style metrics.")
    parser.add_argument("--runs", default=None, help=f"Run batch dir or glob of run folders (default: {DEFAULT_RUNS}).")
    parser.add_argument("--source", choices=("tasks.md", "public.md"), default=DEFAULT_SOURCE, help=f"Task source markdown the runs came from; selects the ask_user_facts sidecar marking interaction tasks (tasks.md -> ask_user_facts_730.json, public.md -> ask_user_facts.json). Default: {DEFAULT_SOURCE}.")
    parser.add_argument("--ask-user-facts", default=None, help="task_id -> fact mapping marking interaction tasks (default: derived from --source via ask_user_facts_path, e.g. tasks.md -> benchmarks/dailyBench-600/ask_user_facts_730.json).")
    parser.add_argument("--model", default=None, help="Restrict the report to runs whose meta.json model equals this.")
    parser.add_argument("--out", default="report.json", help="JSON report output path.")
    parser.add_argument("--out-md", default="report.md", help="Markdown report output path.")
    return parser


def main() -> int:
    """Run the aggregation and write report.json + report.md."""
    args = build_parser().parse_args()
    run_dirs = discover_run_folders(args.runs)
    if not run_dirs:
        print(f"No run folders found under {args.runs or DEFAULT_RUNS}.")
        return 1
    facts_path = args.ask_user_facts or ask_user_facts_path(args.source)
    facts = load_ask_user_facts(facts_path)
    interaction_ids = set(facts)
    records = [load_run_record(run_dir, interaction_ids, facts) for run_dir in run_dirs]
    report = build_report(records, model=args.model)
    Path(args.out).write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    markdown = render_markdown(report)
    Path(args.out_md).write_text(markdown, encoding="utf-8")
    print(markdown)
    print(f"Wrote {args.out} and {args.out_md}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
