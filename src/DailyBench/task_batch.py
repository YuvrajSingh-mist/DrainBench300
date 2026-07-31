"""Dataset-backed batch runner for DailyBench task segments."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path

from dotenv import load_dotenv

from .adb import capture_sample
from .custom_tools import DEFAULT_ASK_USER_MODEL
from .files import slugify, write_json
from .task_dataset import app_slug, load_dataset, render_prompt, select_tasks

load_dotenv()  # picks up .env from the repo root (or any parent dir) - see README's Setup section

# Medium/hard tasks are real multi-step tasks that routinely need more than
# mobilerun's own 1000s MobileAgent default (see reports/qwen35-4b-public-wired-run-analysis.md
# section C1). Easy tasks get a short 5-minute leash (they're 1-step by design - if "star the
# latest email" takes more than 5 minutes, something is genuinely broken and the phone is better
# off freed up for the next task). Hard tasks get 30 minutes for cross-app multi-step work.
EASY_TASK_TIMEOUT_SECONDS = 300
MEDIUM_TASK_TIMEOUT_SECONDS = 1000
HARD_TASK_TIMEOUT_SECONDS = 1800

# A task that fails almost immediately with a dropped-request/empty-completion error is a
# transient LLM-infra blip, not genuine task difficulty (section C3/A4) - only flag failures
# this early, so a real multi-step failure never gets mistaken for a transient one.
TRANSIENT_FAILURE_MAX_STEPS = 3
TRANSIENT_FAILURE_MARKERS = ("Request timed out", "Empty response content")

# Fallback {task_id: fact} mapping for Hard/ASK USER tasks whose dataset row has no
# `ask_user_fact` of its own (only the public dataset publishes it inline - see
# docs/advanced-features.md's Custom tools section). Not a CLI flag: there's exactly one
# relevant facts file at a time, not something worth reconfiguring per invocation.
ASK_USER_FACTS_PATH = "benchmarks/dailyBench-600/ask_user_facts.json"


def build_parser() -> argparse.ArgumentParser:
    """Build the batch runner CLI parser."""
    parser = argparse.ArgumentParser(description="Run DailyBench task slices from an exported dataset.")
    parser.add_argument("--dataset", default="benchmarks/dailyBench-600/DailyBench_730_v4.json")
    parser.add_argument("--bucket", choices=["easy", "medium", "hard", "hard-deterministic", "open-ended"])
    parser.add_argument("--app")
    parser.add_argument("--task-id", action="append", default=[])
    parser.add_argument("--var", action="append", default=[])
    parser.add_argument("--limit", type=int)
    parser.add_argument("--all", action="store_true", dest="include_all")
    parser.add_argument("--list", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--skip-unresolved", action="store_true")
    parser.add_argument("--serial", default=os.environ.get("DAILYBENCH_SERIAL"))
    parser.add_argument("--sample-interval", type=float, default=0.1, help="Seconds between battery/thermal samples, forwarded to each task run (0.1 = every 100ms).")
    parser.add_argument("--llm-upstream-base", default=os.environ.get("LLM_UPSTREAM"))
    parser.add_argument("--llm-proxy-port-base", type=int, default=8090)
    parser.add_argument("--model", default=os.environ.get("MODEL"))
    parser.add_argument("--temperature", type=float, default=0.0)
    parser.add_argument("--steps", type=int, default=50)
    parser.add_argument("--repeats", type=int, default=1, help="Run each selected task this many times (opt-in; runs are already deterministic at temperature=0).")
    parser.add_argument("--no-screen-record", action="store_true")
    parser.add_argument("--vision", action="store_true", help="Enable vision (screenshots) for the agent; off by default for this harness.")
    parser.add_argument("--reasoning", action="store_true", help="Use mobilerun's manager/executor planning workflow instead of the fast-agent loop.")
    parser.add_argument("--no-debug", action="store_true", help="Disable mobilerun's verbose debug logging (on by default).")
    parser.add_argument("--tracing", action="store_true", help="Enable Arize Phoenix tracing (needs `phoenix serve` running locally; see docs.mobilerun.ai/framework/features/tracing).")
    parser.add_argument("--phoenix-url", default=None, help="Phoenix collector endpoint, e.g. http://localhost:6006 (sets the `phoenix_url` env var for the mobilerun process).")
    parser.add_argument("--phoenix-project", default=None, help="Phoenix project name to group traces under (sets the `phoenix_project_name` env var).")
    parser.add_argument("--save-trajectory", choices=["none", "step", "action"], default="none", help="Local trajectory recording level: none, step (per agent step), or action (per atomic action).")
    parser.add_argument("--no-app-reset", action="store_true", help="Skip force-stopping the foreground app and returning home after each task (on by default, for fairness between consecutive tasks).")
    parser.add_argument("--cooldown-seconds", type=float, default=10.0, help="Fixed pause between tasks so the device doesn't run continuously into thermal/load territory (see reports/qwen35-4b-public-wired-run-analysis.md section C2). 0 disables it.")
    parser.add_argument("--ask-user-model", default=DEFAULT_ASK_USER_MODEL, help="Forwarded to each task run's ask_user tool.")
    return parser


def parse_vars(items: list[str]) -> dict[str, str]:
    """Parse repeated `key=value` CLI items into a dictionary."""
    values: dict[str, str] = {}
    for item in items:
        if "=" not in item:
            raise ValueError(f"Expected key=value, got: {item}")
        key, value = item.split("=", 1)
        values[key.strip()] = value
    return values


def day_subfolder(task: dict[str, object]) -> str:
    """Return the run-folder subfolder for a task: `day{N}` for schedule tasks, or `hard`/
    `open-ended` for the Limit-Testing tasks, which aren't tied to any day."""
    day = task.get("day")
    if day is not None:
        return f"day{day}"
    return "hard" if task.get("bucket") in ("hard", "hard-deterministic") else "open-ended"


def run_label(task: dict[str, object], repeat_index: int = 1, repeats_total: int = 1) -> str:
    """Build the `--label` for one task's repeat_index'th run (1-based).

    Prefixes with the day subfolder (day1/day2/day3/hard) so runs are organized:
    e.g. `day1--easy-gmail-001`.
    """
    sub = day_subfolder(task)
    label = f"{sub}--{task['bucket']}-{task['app_slug']}-{task['task_number_within_app']:03d}"
    if repeats_total > 1:
        label += f"-rep{repeat_index:02d}"
    return label


def task_timeout_seconds(task: dict[str, object]) -> int | None:
    """Return the task timeout for one task based on its bucket tier.

    Easy (1-step): 5 minutes - if a single action takes longer, it's stuck.
    Medium (2-3 steps): 1000s (mobilerun's own SDK default).
    Hard (3-5 cross-app steps): 30 minutes.
    """
    bucket = task["bucket"]
    if bucket == "easy":
        return EASY_TASK_TIMEOUT_SECONDS
    if bucket in ("hard", "hard-deterministic", "open-ended"):
        return HARD_TASK_TIMEOUT_SECONDS
    return MEDIUM_TASK_TIMEOUT_SECONDS


def load_ask_user_facts(path: str) -> dict[str, str]:
    """Load the {task_id: relevant_information} mapping for Hard/ASK USER tasks' ask_user tool.

    A missing file just means no facts are configured yet (fine for DETERMINISTIC-only
    selections) - it's gitignored on purpose, see .gitignore's comment above the entry.
    """
    facts_path = Path(path)
    if not facts_path.exists():
        return {}
    return json.loads(facts_path.read_text(encoding="utf-8"))


def build_run_command(
    args: argparse.Namespace,
    task: dict[str, str],
    prompt: str,
    proxy_port: int,
    repeat_index: int = 1,
    repeats_total: int = 1,
    ask_user_facts: dict[str, str] | None = None,
) -> tuple[list[str], str]:
    """Build one `dailybench_runner.py` invocation. Returns (command, label)."""
    repo_root = Path(__file__).resolve().parents[2]
    label = run_label(task, repeat_index, repeats_total)
    command = [
        sys.executable,
        str(repo_root / "dailybench_runner.py"),
        "--serial", args.serial,
        "--label", label,
        "--sample-interval", str(args.sample_interval),
        "--llm-upstream-base", args.llm_upstream_base,
        "--llm-proxy-port", str(proxy_port),
        "--model", args.model,
        "--temperature", str(args.temperature),
        "--steps", str(args.steps),
    ]
    if task.get("task_id"):
        command.extend(["--task-id", task["task_id"]])
    timeout = task_timeout_seconds(task)
    if timeout is not None:
        command.extend(["--task-timeout", str(timeout)])
    if args.no_screen_record:
        command.append("--no-screen-record")
    if args.vision:
        command.append("--vision")
    if args.reasoning:
        command.append("--reasoning")
    if args.no_debug:
        command.append("--no-debug")
    if args.tracing:
        command.append("--tracing")
    if args.phoenix_url:
        command.extend(["--phoenix-url", args.phoenix_url])
    if args.phoenix_project:
        command.extend(["--phoenix-project", args.phoenix_project])
    command.extend(["--save-trajectory", args.save_trajectory])
    if args.no_app_reset:
        command.append("--no-app-reset")
    if task.get("ahi") == "ASK USER":
        fact = task.get("ask_user_fact") or (ask_user_facts or {}).get(task["task_id"])
        if fact is None:
            print(f"Warning: {task['task_id']} is an ASK USER task but has no ask_user_fact on its dataset row and no entry in {ASK_USER_FACTS_PATH} - its ask_user tool will have nothing to reveal.")
        command.extend(["--ask-user-context", fact or ""])
    command.extend(["--ask-user-model", args.ask_user_model])
    command.extend(["--goal", prompt])
    return command, label


def find_run_dir(label: str) -> Path | None:
    """Best-effort: find the run folder `dailybench_runner.py` just created for this label."""
    matches = sorted(Path("runs").glob(f"*/{slugify(label)}"))
    return matches[-1] if matches else None


def is_transient_failure(run_dir: Path | None) -> bool:
    """True if a failed run's own output.json looks like a dropped LLM request / empty
    completion rather than genuine task difficulty - worth one automatic retry at the end
    of the batch instead of counting as a hard failure (see report sections C3 and A4)."""
    if run_dir is None:
        return False
    output_path = run_dir / "output.json"
    if not output_path.exists():
        return False
    try:
        outcome = json.loads(output_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return False
    if outcome.get("success") or outcome.get("steps", 0) > TRANSIENT_FAILURE_MAX_STEPS:
        return False
    reason = outcome.get("reason", "")
    return any(marker in reason for marker in TRANSIENT_FAILURE_MARKERS)


def write_initial_device_sample(serial: str) -> None:
    """Write one battery+thermal snapshot to runs/ before any task runs."""
    root = Path("runs")
    root.mkdir(parents=True, exist_ok=True)
    write_json(root / "initial_device_sample.json", capture_sample(serial))


def main() -> int:
    """Run or list one selected batch of dataset tasks."""
    args = build_parser().parse_args()
    dataset = load_dataset(args.dataset)
    tasks = select_tasks(dataset, bucket=args.bucket, app=args.app, task_ids=args.task_id, include_all=args.include_all, limit=args.limit)
    variables = parse_vars(args.var)
    if args.list:
        for task in tasks:
            print(f"{task['task_id']}\t{task['bucket']}\t{task['app_slug']}\t{task['prompt_text']}")
        return 0
    if not args.serial or not args.llm_upstream_base or not args.model:
        raise SystemExit("Need --serial, --llm-upstream-base, and --model for execution.")
    if args.repeats < 1:
        raise SystemExit("--repeats must be at least 1.")
    if not args.dry_run:
        write_initial_device_sample(args.serial)
    ask_user_facts = load_ask_user_facts(ASK_USER_FACTS_PATH)
    unresolved_failures: list[str] = []
    retry_queue: list[tuple[list[str], str, str]] = []  # (command, label, task_id)
    invocation = 0

    def run_once(command: list[str], label: str, task_id: str) -> None:
        nonlocal invocation
        invocation += 1
        print(" ".join(command))
        if args.dry_run:
            return
        result = subprocess.run(command, check=False)
        if result.returncode != 0:
            run_dir = find_run_dir(label)
            if is_transient_failure(run_dir):
                print(f"Flagging {task_id} ({label}) for rerun at end of batch - looks like a transient LLM/infra blip, not a real failure: {run_dir}")
                retry_queue.append((command, label, task_id))
            else:
                unresolved_failures.append(task_id)
        if args.cooldown_seconds > 0:
            time.sleep(args.cooldown_seconds)

    for task in tasks:
        unresolved = [name for name in task["placeholders"] if name not in variables]
        if unresolved and args.skip_unresolved:
            print(f"Skipping {task['task_id']} unresolved placeholders: {', '.join(unresolved)}")
            continue
        if unresolved:
            raise SystemExit(f"Task {task['task_id']} needs --var values for: {', '.join(unresolved)}")
        prompt = render_prompt(task, variables)
        for repeat_index in range(1, args.repeats + 1):
            command, label = build_run_command(args, task, prompt, args.llm_proxy_port_base + invocation, repeat_index, args.repeats, ask_user_facts)
            run_once(command, label, task["task_id"])

    if retry_queue and not args.dry_run:
        print(f"=== Rerunning {len(retry_queue)} task(s) flagged as transient failures ===")
        for command, label, task_id in retry_queue:
            invocation += 1
            print(" ".join(command))
            result = subprocess.run(command, check=False)
            if result.returncode != 0:
                print(f"{task_id} ({label}) failed again on retry - counting as a real failure this time.")
                unresolved_failures.append(task_id)

    return 1 if unresolved_failures else 0
