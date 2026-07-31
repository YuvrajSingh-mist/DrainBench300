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

Interaction (ASK USER) tasks are identified by task_id membership in
benchmarks/dailyBench-600/ask_user_facts.json.

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

from DailyBench.benchmark_metrics import avg_steps, avg_user_queries, success_rate, user_interaction_quality
from DailyBench.task_batch import load_ask_user_facts

DEFAULT_RUNS = "runs/*/*"
DEFAULT_ASK_USER_FACTS = "benchmarks/dailyBench-600/ask_user_facts.json"
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
    """Return run folders (dirs containing output.json) under a path or glob."""
    if runs_arg:
        if any(char in runs_arg for char in "*?["):
            candidates = [Path(path) for path in glob.glob(runs_arg)]
        else:
            path = Path(runs_arg)
            if not path.is_dir():
                raise SystemExit(f"--runs path not found: {runs_arg}")
            candidates = [child for child in path.iterdir() if child.is_dir()]
    else:
        candidates = [Path(path) for path in glob.glob(DEFAULT_RUNS)]
    return sorted(path for path in candidates if path.is_dir() and (path / "output.json").exists())


def load_run_record(run_dir: Path, interaction_ids: set[str]) -> dict[str, Any]:
    """Load one run folder into a benchmark_metrics record dict."""
    output = _read_json(run_dir / "output.json") or {}
    meta = _read_json(run_dir / "meta.json") or {}
    run_metrics = _read_json(run_dir / "run_metrics.json") or {}

    ask_user_calls = run_metrics.get("ask_user_call_count")
    if ask_user_calls is None:
        ask_user_calls = _count_jsonl_lines(run_dir / "ask_user_metrics.jsonl")

    task_id = meta.get("task_id") or parse_task_id_from_label(meta.get("label", ""))
    bucket = task_id.split("__", 1)[0] if task_id else None

    return {
        "run_dir": str(run_dir),
        "label": meta.get("label"),
        "model": meta.get("model"),
        "task_id": task_id,
        "bucket": bucket,
        "success": bool(output.get("success")),
        "steps": int(output.get("steps") or 0),
        "ask_user_calls": int(ask_user_calls or 0),
        "is_interaction": bool(task_id in interaction_ids) if task_id else False,
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
        f"| User Interaction Quality (UIQ) | {report['user_interaction_quality']:.3f} |",
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
    parser.add_argument("--ask-user-facts", default=DEFAULT_ASK_USER_FACTS, help=f"task_id -> fact mapping marking interaction tasks (default: {DEFAULT_ASK_USER_FACTS}).")
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
    interaction_ids = set(load_ask_user_facts(args.ask_user_facts))
    records = [load_run_record(run_dir, interaction_ids) for run_dir in run_dirs]
    report = build_report(records, model=args.model)
    Path(args.out).write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    markdown = render_markdown(report)
    Path(args.out_md).write_text(markdown, encoding="utf-8")
    print(markdown)
    print(f"Wrote {args.out} and {args.out_md}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
