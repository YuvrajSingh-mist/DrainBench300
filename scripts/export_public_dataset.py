#!/usr/bin/env python3
"""Export the public sample markdown task list into JSON and JSONL dataset files."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from DailyBench.task_dataset import ask_user_facts_path, merge_ask_user_facts, parse_tasks_markdown, save_dataset_files


def main() -> int:
    """Parse benchmarks/dailyBench-600/public.md (the 3-day public sample) and write the dataset artifacts.

    This is a structural preview, not the real held-out eval, so unlike the private benchmark it's
    fine to publish each ASK USER task's `ask_user_fact` right in the dataset (see
    docs/advanced-features.md's Custom tools section).
    """
    source_path = "benchmarks/dailyBench-600/public.md"
    source = ROOT / source_path
    dataset = parse_tasks_markdown(source.read_text(encoding="utf-8"), source_path=source_path)
    # Stays on the PUBLIC facts file (ask_user_facts.json, via ask_user_facts_path) - never the
    # 730 benchmark's ask_user_facts_730.json, since the preview is fine to publish with answers.
    merge_ask_user_facts(dataset, ROOT / ask_user_facts_path("public.md"))
    # Per-task prompt overrides that survive regeneration (the datasets are gitignored and
    # rebuilt from this script). easy__contacts__001 is scoped to a different real device
    # contact (Akash Kumar) so the shared `contact` var used by messaging tasks is
    # unaffected — see docs/fabricated-test-data.md §5.
    for task in dataset["tasks"]:
        if task["task_id"] == "easy__contacts__001":
            task["prompt_text"] = "In Contacts, change Akash Kumar's name to include their middle initial: [middle initial]"
            task["prompt_template"] = "In Contacts, change Akash Kumar's name to include their middle initial: {{ middle initial }}"
            task["placeholders"] = ["middle initial"]
            task["placeholder_count"] = 1
    dataset["dataset_name"] = "DailyBench-Public"
    dataset["dataset_version"] = "v2"
    save_dataset_files(dataset, ROOT / "benchmarks" / "dailyBench-600" / "DailyBench_public_v2.json", ROOT / "benchmarks" / "dailyBench-600" / "DailyBench_public_v2.jsonl")
    print(f"Exported {dataset['task_count']} tasks.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
