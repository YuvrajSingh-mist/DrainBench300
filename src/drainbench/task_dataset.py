"""Markdown task parsing and dataset export helpers."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

BUCKET_RE = re.compile(r"^##\s+(.+)$")
APP_RE = re.compile(r"^\*\*(.+?)\*\*(?:\s+—.*)?$")
CROSS_APP_RE = re.compile(r"^\*\[(.+?)\]\*\s+(.*)$")
TASK_RE = re.compile(r"^(\d+)\.\s+(.*)$")
PLACEHOLDER_RE = re.compile(r"\[([^\]]+)\]")


def bucket_slug(title: str) -> str:
    """Normalize a markdown bucket title into a stable slug."""
    lowered = title.strip().lower()
    if lowered.startswith("easy"):
        return "easy"
    if lowered.startswith("medium"):
        return "medium"
    if "hard" in lowered and "deterministic" in lowered:
        return "hard-deterministic"
    if lowered.startswith("open-ended"):
        return "open-ended"
    value = re.sub(r"[^a-z0-9]+", "-", lowered)
    return value.strip("-")


def app_slug(name: str) -> str:
    """Normalize an app/category name into a stable slug."""
    value = re.sub(r"[^a-z0-9]+", "-", name.strip().lower())
    return value.strip("-")


def to_prompt_template(task_text: str) -> str:
    """Convert `[placeholder]` style text into `{{ placeholder }}` form."""
    return PLACEHOLDER_RE.sub(lambda match: "{{ " + match.group(1).strip() + " }}", task_text)


def extract_placeholders(task_text: str) -> list[str]:
    """Return placeholder names in first-seen order."""
    values: list[str] = []
    for name in PLACEHOLDER_RE.findall(task_text):
        normalized = name.strip()
        if normalized not in values:
            values.append(normalized)
    return values


def parse_tasks_markdown(markdown_text: str, *, source_path: str) -> dict[str, Any]:
    """Parse the task markdown into a structured dataset dictionary."""
    tasks: list[dict[str, Any]] = []
    current_bucket = ""
    current_app = ""
    bucket_counts: dict[str, int] = {}
    app_counts: dict[str, int] = {}
    for raw_line in markdown_text.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        bucket_match = BUCKET_RE.match(line)
        if bucket_match:
            current_bucket = bucket_slug(bucket_match.group(1))
            if current_bucket not in {"easy", "medium", "hard-deterministic", "open-ended"}:
                current_bucket = ""
                current_app = ""
                continue
            current_app = ""
            continue
        app_match = APP_RE.match(line)
        if app_match:
            current_app = app_match.group(1).strip()
            continue
        task_match = TASK_RE.match(line)
        if not task_match or not current_bucket:
            continue
        task_index = int(task_match.group(1))
        task_body = task_match.group(2).strip()
        cross_app = CROSS_APP_RE.match(task_body)
        app_name = current_app
        cross_app_label = None
        if cross_app:
            cross_app_label = cross_app.group(1).strip()
            task_body = cross_app.group(2).strip()
            app_name = cross_app_label
        placeholders = extract_placeholders(task_body)
        app_key = app_slug(app_name or "unknown")
        bucket_counts[current_bucket] = bucket_counts.get(current_bucket, 0) + 1
        app_counts[app_key] = app_counts.get(app_key, 0) + 1
        ordinal = app_counts[app_key]
        tasks.append(
            {
                "task_id": f"{current_bucket}__{app_key}__{task_index:03d}",
                "bucket": current_bucket,
                "app": app_name,
                "app_slug": app_key,
                "task_number_within_app": task_index,
                "task_number_within_dataset_app": ordinal,
                "prompt_text": task_body,
                "prompt_template": to_prompt_template(task_body),
                "placeholders": placeholders,
                "placeholder_count": len(placeholders),
                "is_cross_app": cross_app_label is not None,
                "cross_app_label": cross_app_label,
                "source_path": source_path,
            }
        )
    return {
        "dataset_name": "DrainBench-730",
        "dataset_version": "v3",
        "source_path": source_path,
        "task_count": len(tasks),
        "bucket_counts": bucket_counts,
        "tasks": tasks,
    }


def load_dataset(path: str | Path) -> dict[str, Any]:
    """Load one exported dataset JSON file."""
    return json.loads(Path(path).read_text(encoding="utf-8"))


def save_dataset_files(dataset: dict[str, Any], json_path: str | Path, jsonl_path: str | Path) -> None:
    """Write dataset JSON and JSONL artifacts."""
    json_target = Path(json_path)
    jsonl_target = Path(jsonl_path)
    json_target.parent.mkdir(parents=True, exist_ok=True)
    json_target.write_text(json.dumps(dataset, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    with jsonl_target.open("w", encoding="utf-8") as handle:
        for task in dataset["tasks"]:
            handle.write(json.dumps(task, ensure_ascii=False) + "\n")


def render_prompt(task: dict[str, Any], variables: dict[str, str]) -> str:
    """Render a task prompt with simple placeholder substitution."""
    prompt = task["prompt_text"]
    for name in task["placeholders"]:
        if name not in variables:
            continue
        prompt = prompt.replace(f"[{name}]", variables[name])
    return prompt


def select_tasks(
    dataset: dict[str, Any],
    *,
    bucket: str | None = None,
    app: str | None = None,
    task_ids: list[str] | None = None,
    include_all: bool = False,
    limit: int | None = None,
) -> list[dict[str, Any]]:
    """Filter dataset tasks by selection flags."""
    chosen = dataset["tasks"]
    if not include_all and not any([bucket, app, task_ids]):
        raise ValueError("Choose at least one selector or pass --all.")
    if bucket:
        chosen = [task for task in chosen if task["bucket"] == bucket]
    if app:
        chosen = [task for task in chosen if task["app_slug"] == app_slug(app)]
    if task_ids:
        wanted = set(task_ids)
        chosen = [task for task in chosen if task["task_id"] in wanted]
    if limit is not None:
        chosen = chosen[:limit]
    return chosen
