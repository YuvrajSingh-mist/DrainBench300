"""Markdown task parsing and dataset export helpers.

Three dialects are auto-detected line by line:

1. The original `## Bucket` / `**App**` / numbered-list format (docs/tasks.md).
2. The "21-Day Schedule" format (older benchmarks/dailyBench-600/tasks.md revisions): each
   easy/medium task is its own `- *Easy (1pt):* ...` bullet naming its app inline, with no
   separate **App** heading, under `### Day N` headings; hard/open-ended tasks sit under
   `### Hard — ...` / `### Open-Ended ...` H3 headings.
3. The current "3-Day Sample" format (benchmarks/dailyBench-600/public.md, and the format
   docs/tasks.md is migrating to): `### Day N` headings, `**[AppName]**` bold-bracket app
   section headers, plain `- Easy (1pt): ...` / `- Medium (3pt): ...` bullets (optionally with
   an inline `**[App1+App2]**` cross-app tag before the colon), and a single shuffled
   `## Hard (N tasks, shuffled order)` section whose tasks are each introduced by a
   `**N. [App1+App2] — DETERMINISTIC|ASK USER**` header followed by one bullet - natural
   first-person text, with ASK USER tasks carrying a trailing `(deliberately ...)` methodology
   note that must never leak into the agent-facing prompt.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

BUCKET_RE = re.compile(r"^#{2,3}\s+(.+)$")
APP_RE = re.compile(r"^\*\*(.+?)\*\*(?:\s+—.*)?$")
CROSS_APP_RE = re.compile(r"^\*\[(.+?)\]\*\s+(.*)$")
TASK_RE = re.compile(r"^(\d+)\.\s+(.*)$")
PLACEHOLDER_RE = re.compile(r"\[([^\]]+)\]")

DAY_RE = re.compile(r"^###\s+Day\s+(\d+)\b")
INLINE_TIER_RE = re.compile(r"^-\s+\*(Easy|Medium)\s*\(\d+pt\):\*\s+(.*)$")
LEADING_INLINE_APP_RE = re.compile(r"^(?:On|In|Using|Open|Go to)\s+([A-Z][A-Za-z0-9]*(?:\s+[A-Z][A-Za-z0-9]*)*)(?:,|\s+and\b)")
TRAILING_INLINE_APP_RE = re.compile(r",\s+on\s+([A-Z][A-Za-z0-9]*(?:\s+[A-Z][A-Za-z0-9]*)*)\s*$")

# -- "3-Day Sample" dialect (public.md) --------------------------------------------------------
APP_HEADER_RE = re.compile(r"^\*\*\[(.+?)\]\*\*$")
NEW_TIER_RE = re.compile(r"^-\s+(Easy|Medium)\s*\((\d+)pt\)(?:\s+\*\*\[(.+?)\]\*\*)?:\s*(.*)$")
HARD_HEADER_RE = re.compile(r"^\*\*(\d+)\.\s+\[(.+?)\]\s+—\s+(DETERMINISTIC|ASK USER)\*\*$")
HARD_BODY_RE = re.compile(r"^-\s+(.*)$")
HARD_NOTE_RE = re.compile(r"^(.*?)\s*\((deliberately.*)\)\s*$")

HARD_FLAT_POINTS = 5

# Canonical app name -> the aliases this corpus actually uses for it, longest first so a
# multi-word alias (e.g. "Google Maps") is matched whole rather than as its shorter substring.
APP_ALIASES: dict[str, tuple[str, ...]] = {
    "Google Maps": ("Google Maps", "Maps"),
    "Google Drive": ("Google Drive", "Drive"),
    "Google Photos": ("Google Photos", "Photos"),
    "Google Search": ("Google Search", "Search"),
    "Gmail": ("Gmail",),
    "Chrome": ("Chrome",),
    "YouTube": ("YouTube",),
    "Telegram": ("Telegram",),
    "Calculator": ("Calculator",),
    "Clock": ("Clock",),
    "Calendar": ("Calendar",),
    "Contacts": ("Contacts",),
    "Notes": ("Notes",),
    "Files": ("Files",),
    "Camera": ("Camera",),
    "Gallery": ("Gallery",),
    "Music": ("Music",),
    "Messages": ("Messages",),
    "Phone": ("Phone",),
    "Settings": ("Settings",),
}
_ALIAS_TO_APP: dict[str, str] = {
    alias: app for app, aliases in APP_ALIASES.items() for alias in aliases
}
_KNOWN_APP_SCAN_RE = re.compile(
    r"\b(" + "|".join(sorted(_ALIAS_TO_APP, key=len, reverse=True)) + r")\b"
)


def extract_inline_app(task_text: str) -> str | None:
    """Pull a task's own app name out of its sentence (leading "On X, ..." or trailing ", on X")."""
    match = LEADING_INLINE_APP_RE.match(task_text) or TRAILING_INLINE_APP_RE.search(task_text)
    return match.group(1).strip() if match else None


def find_apps_in_text(task_text: str) -> list[str]:
    """Return every known app named anywhere in a task's text, in first-appearance order, deduplicated."""
    apps: list[str] = []
    for alias in _KNOWN_APP_SCAN_RE.findall(task_text):
        canonical = _ALIAS_TO_APP[alias]
        if canonical not in apps:
            apps.append(canonical)
    return apps


def resolve_apps(app_label: str, task_body: str) -> list[str]:
    """Resolve a task's app list from a header label like "Gmail" or "Gmail+Contacts".

    Each `+`-joined token is canonicalized via APP_ALIASES. A category header naming no known
    app but tagged "(browser)" (e.g. "Shopping & Delivery (browser)") resolves to Chrome - the
    only browser app in this corpus - taking priority over scanning the task's own sentence,
    since generic verbs in the task text (e.g. "Search for ...") can false-positive against an
    app alias. If neither the header nor the "(browser)" tag resolves anything, falls back to
    scanning the task's own sentence for a recognized app.
    """
    canonical: list[str] = []
    for token in app_label.split("+"):
        canonical_name = _ALIAS_TO_APP.get(token.strip())
        if canonical_name and canonical_name not in canonical:
            canonical.append(canonical_name)
    if canonical:
        return canonical
    if "browser" in app_label.lower():
        return ["Chrome"]
    return find_apps_in_text(task_body)


def bucket_slug(title: str) -> str:
    """Normalize a markdown bucket title into a stable slug."""
    lowered = title.strip().lower()
    if lowered.startswith("easy"):
        return "easy"
    if lowered.startswith("medium"):
        return "medium"
    if lowered.startswith("hard"):
        # The current dialect's single shuffled "Hard (N tasks, shuffled order)" section vs.
        # the older dialects' "Hard — Deterministic Composite ..." section.
        return "hard" if "shuffled" in lowered else "hard-deterministic"
    if lowered.startswith("open-ended"):
        return "open-ended"
    value = re.sub(r"[^a-z0-9]+", "-", lowered)
    return value.strip("-")


def difficulty_of(bucket: str) -> str:
    """Collapse any dialect's bucket slug onto one filterable easy/medium/hard axis."""
    if bucket in ("easy", "medium"):
        return bucket
    return "hard"


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
    """Parse the task markdown into a structured dataset dictionary (see module docstring)."""
    tasks: list[dict[str, Any]] = []
    current_bucket = ""
    current_app = ""
    current_day: int | None = None
    pending_hard_header: tuple[int, str, str] | None = None
    bucket_counts: dict[str, int] = {}
    app_counts: dict[tuple[str, str], int] = {}

    def append_task(
        bucket: str,
        task_index: int,
        task_body: str,
        app_name: str,
        cross_app_label: str | None,
        day: int | None,
        *,
        ahi: str | None = None,
        note: str | None = None,
    ) -> None:
        placeholders = extract_placeholders(task_body)
        app_key = app_slug(app_name or "unknown")
        bucket_counts[bucket] = bucket_counts.get(bucket, 0) + 1
        app_counts[(bucket, app_key)] = app_counts.get((bucket, app_key), 0) + 1
        ordinal = app_counts[(bucket, app_key)]
        apps = resolve_apps(app_name, task_body) if app_name else find_apps_in_text(task_body)
        tasks.append(
            {
                "task_id": f"{bucket}__{app_key}__{task_index:03d}",
                "bucket": bucket,
                "difficulty": difficulty_of(bucket),
                "points": 1 if bucket == "easy" else 3 if bucket == "medium" else HARD_FLAT_POINTS,
                "day": day,
                "app": app_name,
                "app_slug": app_key,
                "apps": apps,
                "num_apps": len(apps),
                "cross_app_required": len(apps) > 1,
                "ahi": ahi,
                "note": note,
                "ask_user_fact": None,
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

    for raw_line in markdown_text.splitlines():
        line = raw_line.strip()
        if not line:
            continue

        day_match = DAY_RE.match(line)
        if day_match:
            current_day = int(day_match.group(1))
            continue

        hard_header_match = HARD_HEADER_RE.match(line)
        if hard_header_match:
            index, app_label, ahi_tag = hard_header_match.groups()
            pending_hard_header = (int(index), app_label, ahi_tag)
            continue

        if pending_hard_header is not None:
            body_match = HARD_BODY_RE.match(line)
            if body_match:
                index, app_label, ahi_tag = pending_hard_header
                task_body = body_match.group(1).strip()
                note_match = HARD_NOTE_RE.match(task_body)
                note = None
                if note_match:
                    task_body, note = note_match.group(1).strip(), note_match.group(2).strip()
                cross_app_label = app_label if "+" in app_label else None
                append_task("hard", index, task_body, app_label, cross_app_label, None, ahi=ahi_tag, note=note)
                pending_hard_header = None
                continue
            pending_hard_header = None

        new_tier_match = NEW_TIER_RE.match(line)
        if new_tier_match:
            tier, _points, inline_app_label, task_body = new_tier_match.groups()
            bucket = tier.lower()
            task_body = task_body.strip()
            app_name = inline_app_label if inline_app_label else current_app
            cross_app_label = inline_app_label if inline_app_label and "+" in inline_app_label else None
            next_index = app_counts.get((bucket, app_slug(app_name or "unknown")), 0) + 1
            append_task(bucket, next_index, task_body, app_name, cross_app_label, current_day)
            continue

        app_header_match = APP_HEADER_RE.match(line)
        if app_header_match:
            current_app = app_header_match.group(1).strip()
            continue

        inline_match = INLINE_TIER_RE.match(line)
        if inline_match:
            bucket = inline_match.group(1).lower()
            task_body = inline_match.group(2).strip()
            found_apps = find_apps_in_text(task_body)
            app_name = extract_inline_app(task_body) or (found_apps[0] if found_apps else "")
            next_index = app_counts.get((bucket, app_slug(app_name or "unknown")), 0) + 1
            append_task(bucket, next_index, task_body, app_name, None, current_day)
            continue

        bucket_match = BUCKET_RE.match(line)
        if bucket_match:
            if line.startswith("##") and not line.startswith("###"):
                current_day = None
            resolved = bucket_slug(bucket_match.group(1))
            current_bucket = resolved if resolved in {"easy", "medium", "hard-deterministic", "hard", "open-ended"} else ""
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
        elif not current_app:
            # No **App** heading in scope (the older dialect's Hard/Open-Ended lists have
            # none) - fall back to scanning the task's own text for every app it names.
            found_apps = find_apps_in_text(task_body)
            if len(found_apps) > 1:
                cross_app_label = " + ".join(found_apps)
                app_name = cross_app_label
            elif found_apps:
                app_name = found_apps[0]
        append_task(current_bucket, task_index, task_body, app_name, cross_app_label, current_day)

    return {
        "dataset_name": "DailyBench-730",
        "dataset_version": "v3",
        "source_path": source_path,
        "task_count": len(tasks),
        "bucket_counts": bucket_counts,
        "tasks": tasks,
    }


def load_dataset(path: str | Path) -> dict[str, Any]:
    """Load one exported dataset JSON file."""
    return json.loads(Path(path).read_text(encoding="utf-8"))


def merge_ask_user_facts(dataset: dict[str, Any], facts_path: str | Path) -> None:
    """Fill in each Hard/ASK USER task's `ask_user_fact` field from a {task_id: fact} JSON file.

    Only meaningful for a dataset that's fine to publish with the answer included (a structural
    preview, not a real held-out eval) - see docs/advanced-features.md's Custom tools section for
    why the real private benchmark must never do this. A missing facts file is a no-op.
    """
    path = Path(facts_path)
    if not path.exists():
        return
    facts: dict[str, str] = json.loads(path.read_text(encoding="utf-8"))
    for task in dataset["tasks"]:
        fact = facts.get(task["task_id"])
        if fact is not None:
            task["ask_user_fact"] = fact


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
