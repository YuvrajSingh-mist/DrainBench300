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
from .files import dated_out_dir, slugify, write_json
from .task_dataset import app_slug, ask_user_facts_path, load_dataset, select_tasks
from .user_config import load_user_config, parse_flat_config, resolve_template, var_map

load_dotenv()  # picks up .env from the repo root (or any parent dir) - see README's Setup section

# No wall-clock timeouts at all (timeout=None for every bucket): the step budget (--steps,
# default 200) is the real bound, and on a real phone the battery is the ultimate failsafe
# anyway. Wall-clock caps proved counterproductive - legitimately long runs (medium-clock,
# medium-photos, medium-search-telegram) exceeded 20 minutes and were killed mid-verification.
# The batch passes --task-timeout 0 for every bucket, which dailybench_runner translates to
# timeout=None (the runner's own 1000s default would otherwise cap all tasks - smoke-test finding).
EASY_TASK_TIMEOUT_SECONDS = None
MEDIUM_TASK_TIMEOUT_SECONDS = None
HARD_TASK_TIMEOUT_SECONDS = None

# A task that fails almost immediately with a dropped-request/empty-completion error is a
# transient LLM-infra blip, not genuine task difficulty (section C3/A4) - only flag failures
# this early, so a real multi-step failure never gets mistaken for a transient one.
TRANSIENT_FAILURE_MAX_STEPS = 3
TRANSIENT_FAILURE_MARKERS = ("Request timed out", "Empty response content")

# Fallback {task_id: fact} mapping for Hard/ASK USER tasks whose dataset row has no
# `ask_user_fact` of its own (only the public dataset publishes it inline - see
# docs/advanced-features.md's Custom tools section). The facts file is never hardcoded
# here: --source picks the source markdown and ask_user_facts_path(source) derives the
# right file (tasks.md -> ask_user_facts_730.json, public.md -> ask_user_facts.json).
DEFAULT_SOURCE = "tasks.md"


def build_parser() -> argparse.ArgumentParser:
    """Build the batch runner CLI parser."""
    parser = argparse.ArgumentParser(description="Run DailyBench task slices from an exported dataset.")
    parser.add_argument("--dataset", default="benchmarks/dailyBench-600/DailyBench_530_v1.json")
    parser.add_argument("--source", choices=("tasks.md", "public.md"), default=DEFAULT_SOURCE, help=f"Task source markdown the dataset was exported from; selects the ask_user_facts sidecar for Hard/ASK USER fallback facts (tasks.md -> ask_user_facts_730.json, public.md -> ask_user_facts.json). Default: {DEFAULT_SOURCE}.")
    parser.add_argument("--bucket", choices=["easy", "medium", "hard", "hard-deterministic", "open-ended"])
    parser.add_argument("--app")
    parser.add_argument("--task-id", action="append", default=[])
    parser.add_argument("--var", action="append", default=[])
    parser.add_argument("--config", default=str(Path(__file__).resolve().parents[2] / "config" / "user.yaml"),
                        help="Flat user config (config/user.yaml) that resolves prompt placeholders, ASK USER fact templates ({...}) and seed values. CLI --var overrides it.")
    parser.add_argument("--vars-file", default=None, metavar="PATH",
                        help="Optional per-day 'key=value' vars file (e.g. benchmarks/dailyBench-600/tasks_vars/day_1.env); merged under --var.")
    parser.add_argument("--limit", type=int)
    parser.add_argument("--run-root", default=None, help="Run folder root to continue into (e.g. runs/2026-08-03-162853) instead of creating a fresh dated folder. Pair with --resume-from to continue an interrupted batch in place.")
    parser.add_argument("--resume-from", default=None, metavar="TASK_ID", help="Skip every selected task whose task_id comes before TASK_ID and start at TASK_ID (inclusive), so an interrupted batch can resume without re-running earlier tasks.")
    parser.add_argument("--all", action="store_true", dest="include_all")
    parser.add_argument("--list", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--skip-unresolved", action="store_true")
    parser.add_argument("--serial", default=os.environ.get("DAILYBENCH_SERIAL"))
    parser.add_argument("--sample-interval", type=float, default=1.0, help="Seconds between battery/thermal samples, forwarded to each task run (1.0 = every second; 0.1 = every 100ms, heavier).")
    parser.add_argument("--llm-upstream-base", default=os.environ.get("LLM_UPSTREAM"))
    parser.add_argument("--llm-proxy-port-base", type=int, default=8090)
    parser.add_argument("--model", default=os.environ.get("MODEL"))
    parser.add_argument("--temperature", type=float, default=0.0)
    parser.add_argument("--steps", type=int, default=200)
    parser.add_argument("--repeats", type=int, default=1, help="Run each selected task this many times (opt-in; runs are already deterministic at temperature=0).")
    parser.add_argument("--screen-record", action="store_true", help="Record screen.mp4 via scrcpy (OFF by default — saves significant disk/CPU; a single task can produce 10-70MB of mp4).")
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

    Every tier is None (no wall-clock cap) - the step budget (--steps, default 200)
    is the real bound, and on a real phone the battery is the ultimate failsafe.
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
    cfg: dict[str, str] | None = None,
    task_vars: dict[str, str] | None = None,
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
    if getattr(args, "run_root", None):
        command.extend(["--run-root", args.run_root])
    if task.get("task_id"):
        command.extend(["--task-id", task["task_id"]])
    timeout = task_timeout_seconds(task)
    # Hard/None = no wall-clock cap: pass --task-timeout 0, which dailybench_runner translates
    # to timeout=None. (Omitting the flag would fall back to the runner's own 1000s default and
    # silently cap hard tasks - smoke-test finding.)
    command.extend(["--task-timeout", "0" if timeout is None else str(timeout)])
    if args.screen_record:
        command.append("--screen-record")
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
            print(f"Warning: {task['task_id']} is an ASK USER task but has no ask_user_fact on its dataset row and no entry in {ask_user_facts_path(args.source)} - its ask_user tool will have nothing to reveal.")
        elif "{" in fact:
            # fact is a {config_key} template (persona-free) -> resolve from user config
            if not cfg:
                raise SystemExit(f"{task['task_id']} fact {fact!r} needs a --config (see config/user_config.example)")
            fact = resolve_template(fact, cfg)
        command.extend(["--ask-user-context", fact or ""])
    command.extend(["--ask-user-model", args.ask_user_model])
    command.extend(["--goal", prompt])
    # mobilerun-native custom variables: pass the task's resolved placeholders so
    # the agent gets them as structured data (rendered in the system prompt, readable
    # by custom tools). Only this task's placeholders - never the hidden ASK USER fact.
    if task_vars:
        for key, value in task_vars.items():
            command.extend(["--var", f"{key}={value}"])
    return command, label


def find_run_dir(label: str, runs_root: str | Path = "runs") -> Path | None:
    """Best-effort: find the run folder `dailybench_runner.py` just created for this label.

    Batch labels are `{sub}--{rest}` and are stored under `runs/<batch>/<sub>/<rest>`
    (see files.run_dir_for_label), so the day/hard subfolder is included in the glob.
    `runs_root` is overridable for hermetic tests.
    """
    sub, sep, rest = label.partition("--")
    pattern = f"*/{sub}/{slugify(rest)}" if sep else f"*/{slugify(label)}"
    matches = sorted(Path(runs_root).glob(pattern))
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


def write_initial_device_sample(serial: str, batch_dir: Path) -> None:
    """Write one battery+thermal snapshot into the batch run folder before any task runs."""
    batch_dir.mkdir(parents=True, exist_ok=True)
    write_json(batch_dir / "initial_device_sample.json", capture_sample(serial))


def main() -> int:
    """Run or list one selected batch of dataset tasks."""
    args = build_parser().parse_args()
    dataset = load_dataset(args.dataset)
    tasks = select_tasks(dataset, bucket=args.bucket, app=args.app, task_ids=args.task_id, include_all=args.include_all, limit=args.limit)
    cfg = load_user_config(args.config)
    vars_file = parse_flat_config(Path(args.vars_file).read_text(encoding="utf-8")) if args.vars_file else None
    variables = var_map(cfg, cli_vars=parse_vars(args.var), vars_file=vars_file)
    if args.list:
        for task in tasks:
            print(f"{task['task_id']}\t{task['bucket']}\t{task['app_slug']}\t{task['prompt_text']}")
        return 0
    if not args.serial or not args.llm_upstream_base or not args.model:
        raise SystemExit("Need --serial, --llm-upstream-base, and --model for execution.")
    if args.repeats < 1:
        raise SystemExit("--repeats must be at least 1.")
    if not args.dry_run:
        if args.run_root:
            batch_dir = Path(args.run_root).resolve()
            batch_dir.mkdir(parents=True, exist_ok=True)
            # Resume path: continue into the existing run root and keep the batch's
            # original initial_device_sample.json baseline instead of overwriting it.
            print(f"Continuing into existing run root: {batch_dir}")
        else:
            batch_dir = dated_out_dir("runs")
            batch_dir.mkdir(parents=True, exist_ok=True)
            args.run_root = str(batch_dir)
            write_initial_device_sample(args.serial, batch_dir)
    ask_user_facts = load_ask_user_facts(ask_user_facts_path(args.source))
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
            if run_dir is not None and (run_dir / "PROXY_STARTUP_FAILED").exists():
                marker = (run_dir / "PROXY_STARTUP_FAILED").read_text(encoding="utf-8").strip()
                print(f"\nABORTING benchmark: LLM proxy failed to start for {task_id} ({label}) after all retries.\n{marker}", file=sys.stderr)
                raise SystemExit(2)
            if is_transient_failure(run_dir):
                print(f"Flagging {task_id} ({label}) for rerun at end of batch - looks like a transient LLM/infra blip, not a real failure: {run_dir}")
                retry_queue.append((command, label, task_id))
            else:
                unresolved_failures.append(task_id)
        if args.cooldown_seconds > 0:
            time.sleep(args.cooldown_seconds)

    resuming = args.resume_from is not None
    for task in tasks:
        if resuming:
            if task["task_id"] == args.resume_from:
                print(f"Resuming batch at {task['task_id']} (reached --resume-from).")
                resuming = False
            else:
                print(f"Skipping {task['task_id']} (before --resume-from {args.resume_from})")
                continue
        unresolved = [name for name in task["placeholders"] if name not in variables]
        if unresolved and args.skip_unresolved:
            print(f"Skipping {task['task_id']} unresolved placeholders: {', '.join(unresolved)}")
            continue
        if unresolved:
            raise SystemExit(f"Task {task['task_id']} needs --var values for: {', '.join(unresolved)}")
        # RAW goal + mobilerun-native variables: the goal keeps its [placeholder] slots and
        # the agent substitutes them from the "Your Task Variables" block rendered into its
        # system prompt (values appear once, never text-interpolated). Only this task's
        # resolved placeholders are forwarded - never the hidden ASK USER fact.
        prompt = task.get("prompt_text") or task.get("prompt_template") or ""
        task_vars = {ph: variables[ph] for ph in (task.get("placeholders") or []) if ph in variables}
        for repeat_index in range(1, args.repeats + 1):
            command, label = build_run_command(args, task, prompt, args.llm_proxy_port_base + invocation, repeat_index, args.repeats, ask_user_facts, cfg, task_vars)
            run_once(command, label, task["task_id"])

    if resuming and args.resume_from is not None:
        print(f"Error: --resume-from {args.resume_from} was not found among the selected tasks - nothing was run.", file=sys.stderr)
        return 2

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
