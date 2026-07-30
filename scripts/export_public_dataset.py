#!/usr/bin/env python3
"""Export the public sample markdown task list into JSON and JSONL dataset files."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from DailyBench.task_dataset import merge_ask_user_facts, parse_tasks_markdown, save_dataset_files


def main() -> int:
    """Parse benchmarks/dailyBench-600/public.md (the 3-day public sample) and write the dataset artifacts.

    This is a structural preview, not the real held-out eval, so unlike the private benchmark it's
    fine to publish each ASK USER task's `ask_user_fact` right in the dataset (see
    docs/advanced-features.md's Custom tools section).
    """
    source_path = "benchmarks/dailyBench-600/public.md"
    source = ROOT / source_path
    dataset = parse_tasks_markdown(source.read_text(encoding="utf-8"), source_path=source_path)
    merge_ask_user_facts(dataset, ROOT / "benchmarks/dailyBench-600/ask_user_facts.json")
    dataset["dataset_name"] = "DailyBench-Public"
    dataset["dataset_version"] = "v2"
    save_dataset_files(dataset, ROOT / "benchmarks" / "dailyBench-600" / "DailyBench_public_v2.json", ROOT / "benchmarks" / "dailyBench-600" / "DailyBench_public_v2.jsonl")
    print(f"Exported {dataset['task_count']} tasks.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
