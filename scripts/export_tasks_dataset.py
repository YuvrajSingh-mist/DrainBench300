#!/usr/bin/env python3
"""Export the markdown task list into JSON and JSONL dataset files."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from DailyBench.task_dataset import parse_tasks_markdown, save_dataset_files


def main() -> int:
    """Parse benchmarks/dailyBench-600/tasks.md (the 21-Day Survival Schedule) and write the dataset artifacts."""
    source_path = "benchmarks/dailyBench-600/tasks.md"
    source = ROOT / source_path
    dataset = parse_tasks_markdown(source.read_text(encoding="utf-8"), source_path=source_path)
    dataset["dataset_name"] = "DailyBench-21Day"
    dataset["dataset_version"] = "v4"
    save_dataset_files(dataset, ROOT / "benchmarks" / "dailyBench-600" / "DailyBench_730_v4.json", ROOT / "benchmarks" / "dailyBench-600" / "DailyBench_730_v4.jsonl")
    print(f"Exported {dataset['task_count']} tasks.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
