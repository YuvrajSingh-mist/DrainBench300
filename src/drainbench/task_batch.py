"""Dataset-backed batch runner for DrainBench task segments."""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path

from .task_dataset import app_slug, load_dataset, render_prompt, select_tasks


def build_parser() -> argparse.ArgumentParser:
    """Build the batch runner CLI parser."""
    parser = argparse.ArgumentParser(description="Run DrainBench task slices from an exported dataset.")
    parser.add_argument("--dataset", default="datasets/drainbench_730_v3.json")
    parser.add_argument("--bucket", choices=["easy", "medium", "hard-deterministic", "open-ended"])
    parser.add_argument("--app")
    parser.add_argument("--task-id", action="append", default=[])
    parser.add_argument("--var", action="append", default=[])
    parser.add_argument("--limit", type=int)
    parser.add_argument("--all", action="store_true", dest="include_all")
    parser.add_argument("--list", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--skip-unresolved", action="store_true")
    parser.add_argument("--serial", default=os.environ.get("DRAINBENCH_SERIAL"))
    parser.add_argument("--out-dir", default="runs")
    parser.add_argument("--sample-interval", type=float, default=1.0)
    parser.add_argument("--llm-upstream-base", default=os.environ.get("LLM_UPSTREAM"))
    parser.add_argument("--llm-proxy-port-base", type=int, default=8090)
    parser.add_argument("--mobilerun-bin", default=os.path.expanduser("~/.local/bin/mobilerun"))
    parser.add_argument("--provider", default="OpenAILike")
    parser.add_argument("--model", default=os.environ.get("MODEL"))
    parser.add_argument("--temperature", type=float, default=0.0)
    parser.add_argument("--steps", type=int, default=50)
    parser.add_argument("--api-base", default="http://127.0.0.1:8090/v1")
    parser.add_argument("--no-screen-record", action="store_true")
    parser.add_argument("--no-vision", action="store_true", default=True)
    parser.add_argument("--no-reasoning", action="store_true", default=True)
    parser.add_argument("--debug", action="store_true", default=True)
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


def build_run_command(args: argparse.Namespace, task: dict[str, str], prompt: str, proxy_port: int) -> list[str]:
    """Build one `drainbench_runner.py` invocation for a selected task."""
    repo_root = Path(__file__).resolve().parents[2]
    label = f"{task['bucket']}-{task['app_slug']}-{task['task_number_within_app']:03d}"
    command = [
        sys.executable,
        str(repo_root / "drainbench_runner.py"),
        "--serial", args.serial,
        "--label", label,
        "--out-dir", args.out_dir,
        "--sample-interval", str(args.sample_interval),
        "--llm-upstream-base", args.llm_upstream_base,
        "--llm-proxy-port", str(proxy_port),
    ]
    if args.no_screen_record:
        command.append("--no-screen-record")
    command.extend(
        [
            "--",
            args.mobilerun_bin, "run",
            "-d", args.serial,
            "-p", args.provider,
            "-m", args.model,
            "--api_base", args.api_base,
            "--temperature", str(args.temperature),
            "--steps", str(args.steps),
        ]
    )
    for flag, enabled in [("--no-vision", args.no_vision), ("--no-reasoning", args.no_reasoning), ("--debug", args.debug)]:
        if enabled:
            command.append(flag)
    command.append(prompt)
    return command


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
    exit_code = 0
    for index, task in enumerate(tasks):
        unresolved = [name for name in task["placeholders"] if name not in variables]
        if unresolved and args.skip_unresolved:
            print(f"Skipping {task['task_id']} unresolved placeholders: {', '.join(unresolved)}")
            continue
        if unresolved:
            raise SystemExit(f"Task {task['task_id']} needs --var values for: {', '.join(unresolved)}")
        prompt = render_prompt(task, variables)
        command = build_run_command(args, task, prompt, args.llm_proxy_port_base + index)
        print(" ".join(command))
        if args.dry_run:
            continue
        result = subprocess.run(command, check=False)
        if result.returncode != 0:
            exit_code = result.returncode
    return exit_code
