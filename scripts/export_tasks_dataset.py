#!/usr/bin/env python3
"""Export the markdown task list into JSON and JSONL dataset files."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from drainbench.task_dataset import parse_tasks_markdown, save_dataset_files


def main() -> int:
    """Parse docs/tasks.md and write the dataset artifacts."""
    source = ROOT / "docs" / "tasks.md"
    dataset = parse_tasks_markdown(source.read_text(encoding="utf-8"), source_path="docs/tasks.md")
    save_dataset_files(dataset, ROOT / "datasets" / "drainbench_730_v3.json", ROOT / "datasets" / "drainbench_730_v3.jsonl")
    print(f"Exported {dataset['task_count']} tasks.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
