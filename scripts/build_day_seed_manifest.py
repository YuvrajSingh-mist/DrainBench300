#!/usr/bin/env python3
"""Build `seeds/full_tasks/day_<N>/` fabricated-data manifests for one day of the 730-task
schedule.

For every task on the requested day this writes:
  seeds/full_tasks/day_<N>/manifests.json                     - day-level index
  seeds/full_tasks/day_<N>/day_<N>_fabricated_data.jsonl      - one JSON line per task (meticulous)
  seeds/full_tasks/day_<N>/<task_id>/manifest.json            - per-task fabricated-data manifest
  seeds/full_tasks/day_<N>/<task_id>/seed_files/...           - literal seed file templates (optional)

The manifest for each task records:
  - the task (id, bucket, points, apps, ASK USER flag)
  - the resolved prompt (placeholder values filled in) and the exact --var map
  - the ASK USER fact the simulated user holds (if any)
  - the fabricated seed data required on-device (type, location, exact values, status)
  - the expected end state used for manual grading (the benchmark's rubric)

Status vocabulary (filled in honestly, verified against the live device where cheap):
  present       - verified present on-device
  needs_seed    - seedable via ADB (shared storage: files/photos/obsidian .md)
  needs_ui      - only seedable via UI automation or operator (app-private/cloud/blocked insert)
  web           - no fabricated data; resolved from the real web at run time
  creation      - the task itself creates the artifact; nothing to pre-seed
  sanity        - relies on real personal state (Telegram/SMS/location); sanity-check only

Run:  uv run python scripts/build_day_seed_manifest.py --day 1
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from datetime import date
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from DailyBench.user_config import (  # noqa: E402
    load_user_config,
    resolve_template,
    resolve_templates,
    template_keys,
)

# Runnable dataset (the deterministic 530-task subset; the 730 corpus is the parent).
DATASET = REPO_ROOT / "benchmarks" / "dailyBench-600" / "DailyBench_530_v1.json"
ASK_USER_FACTS = REPO_ROOT / "benchmarks" / "dailyBench-600" / "ask_user_facts_730.json"
SEEDS_ROOT = REPO_ROOT / "seeds" / "full_tasks"
CONFIG_PATH = REPO_ROOT / "config" / "user.yaml"


# ---------------------------------------------------------------------------
# Placeholder values + fabricated seed data + end-state rubric, per Day-1 task
# of the RUNNABLE 530 subset. Values are {config_key} templates resolved from
# config/user.yaml at build time (persona-free script). A few legacy specs below
# cover tasks that the 530 subset DROPPED from Day 1 (still in the 730 corpus) -
# they are inert here but kept so a full-corpus seed pass could reuse them.
# ---------------------------------------------------------------------------
DAY1_TASKS: dict[str, dict] = {
    "easy__chrome__001": {
        "vars": {},
        "seed": [
            {"type": "chrome_page", "location": "Chrome foreground", "value": "No deterministic seed: the batch app-resets between tasks, so Chrome has no page open at task start.", "status": "sanity"},
        ],
        "end_state": "Chrome has a page saved for offline reading.",
    },
    "medium__chrome__001": {
        "vars": {"article url": "{article url}"},
        "seed": [{"type": "web", "location": "real web via Chrome", "value": "Article is a live, stable Wikipedia page.", "status": "web"}],
        "end_state": "A pinned note exists with a 2-3 sentence summary of the article; the article is bookmarked in Chrome.",
    },
    "medium__chrome-telegram__001": {
        "vars": {"topic": "{topic}", "contact": "{contact}"},
        "seed": [{"type": "telegram_contact", "location": "Telegram (real)", "value": "Contact '{contact}' exists (device's own number).", "status": "present"}],
        "end_state": "Telegram message sent to {contact} containing the two-result summary with links to both chosen websites.",
    },
    "hard__chrome-obsidian-calendar__007": {
        "vars": {},
        "ask_user_fact": "The destination is {destination}.",
        "seed": [
            {"type": "web", "location": "real web via Chrome", "value": "Train times searched live; nothing pre-seeded.", "status": "web"},
        ],
        "end_state": "A note has the chosen departure time; a calendar reminder is set 20 minutes before; agent replies with only the departure time.",
    },
    "easy__telegram__001": {
        "vars": {"contact": "{contact}"},
        "seed": [{"type": "telegram_contact", "location": "Telegram (real)", "value": "Chat '{contact}' exists.", "status": "present"}],
        "end_state": "The {contact} chat is open.",
    },
    "medium__telegram__001": {
        "vars": {},
        "seed": [{"type": "telegram_unread", "location": "Telegram (real)", "value": "Depends on real unread state with differing wait times; not seedable via ADB.", "status": "sanity"}],
        "end_state": "The chat that has waited longest without a reply is opened.",
    },
    "easy__google-search__001": {
        "vars": {"currency pair": "{currency pair}"},
        "seed": [{"type": "web", "location": "real web via Google Search", "value": "Live exchange rate.", "status": "web"}],
        "end_state": "Agent replies with the current {currency pair} rate.",
    },
    "medium__google-search__001": {
        "vars": {"topic": "{topic}"},
        "seed": [{"type": "web", "location": "real web via Google Search", "value": "Live results.", "status": "web"}],
        "end_state": "Agent replies with a one-line takeaway from each of the two best results.",
    },
    "hard__google-search-obsidian-telegram__057": {
        "vars": {"stock name": "{stock name}", "stock note title": "{stock note title}"},
        "ask_user_fact": "Message {contact_b} when it crosses the threshold.",
        "seed": [
            {"type": "obsidian_note", "location": "/sdcard/Obsidian/Papers vault oneplus/{stock note title}.md", "value": "Note '{stock note title}' with threshold + last recorded value (see seed_files/note_stock_watch.md).", "status": "needs_seed", "device_path": "/sdcard/Obsidian/Papers vault oneplus/{stock note title}.md"},
            {"type": "telegram_contact", "location": "Telegram (real)", "value": "Contact '{contact_b}' exists.", "status": "present"},
        ],
        "end_state": "Obsidian '{stock note title}' note updated with today's value; Telegram sent to {contact_b} only if the value crossed the threshold since the last recorded value.",
    },
    "medium__google-search-notes__001": {
        "vars": {},
        "seed": [{"type": "creation", "location": "Notes app", "value": "Agent creates the note titled '{news note title}: {today's date}'.", "status": "creation"}],
        "end_state": "A note '{news note title}: 2026-08-05' exists with the top headlines.",
    },
    "easy__calendar__001": {
        "vars": {},
        "seed": [{"type": "calendar_event", "location": "Calendar (local or Google-synced)", "value": "At least one existing event today; agent adds its current location to it.", "status": "needs_ui"}],
        "end_state": "One existing calendar event has the device's current location added.",
    },
    "medium__calendar__001": {
        "vars": {},
        "seed": [
            {"type": "calendar_event", "location": "Calendar", "value": "Recurring events with NO attendees for today; at least one is outdated (series should still repeat).", "status": "needs_ui"},
        ],
        "end_state": "The outdated recurring event is deleted; the remaining series still repeats correctly.",
    },
    "easy__contacts__001": {
        "vars": {"contact name": "{contact name}"},
        "seed": [{"type": "contact", "location": "Contacts", "value": "Contact '{contact name}' with a phone number (restored by the reset script).", "status": "needs_verify"}],
        "end_state": "Agent replies with {contact name}'s number.",
    },
    "easy__contacts__002": {
        "vars": {"letter": "{letter}"},
        "seed": [{"type": "contact", "location": "Contacts", "value": "Several contacts starting with '{letter}' (Yuvraj*, etc.).", "status": "present"}],
        "end_state": "Agent replies with the count of contacts starting with '{letter}'.",
    },
    "medium__contacts__001": {
        "vars": {},
        "seed": [
            {"type": "contact_birthday", "location": "Contacts", "value": "H-prefix contacts with birthdays in August (Aug 4-7), e.g. Harshit (Aug 5), Hariom (Aug 15), Hemant (Aug 20); birthday-type records added via UI by operator.", "status": "needs_ui"},
        ],
        "end_state": "A reminder is added to each birthday contact a week before the due date; the agent counts them.",
    },
    "easy__obsidian__001": {
        "vars": {"note title": "{note title}"},
        "seed": [{"type": "creation", "location": "Obsidian vault", "value": "Agent creates the note.", "status": "creation"}],
        "end_state": "A note titled '{note title}' exists in the Obsidian vault.",
    },
    "medium__obsidian__001": {
        "vars": {},
        "seed": [{"type": "obsidian_vault", "location": "/sdcard/Obsidian/Papers vault oneplus/", "value": "20 existing .md notes with varied lengths (verified present) - the agent ranks by word count.", "status": "present"}],
        "end_state": "Agent opens the longest note and reports its word count.",
    },
    "hard__chrome-telegram-notes__008": {
        "vars": {"shopping_website_1": "{shopping_website_1}", "shopping_website_2": "{shopping_website_2}", "contact": "{contact}"},
        "ask_user_fact": "The item is {item}.",
        "seed": [
            {"type": "web", "location": "real web via Chrome", "value": "{shopping_website_1} and {shopping_website_2} prices for the item.", "status": "web"},
            {"type": "telegram_contact", "location": "Telegram (real)", "value": "Contact '{contact}' exists.", "status": "present"},
        ],
        "end_state": "If the price difference is > $10: Telegram to {contact} with the cheaper link. Else: note both prices and star the cheaper listing.",
    },
    "easy__camera__001": {
        "vars": {},
        "seed": [{"type": "creation", "location": "Camera", "value": "Agent takes the photo.", "status": "creation"}],
        "end_state": "A photo of a desk object is saved with an appropriate name.",
    },
    "medium__camera__001": {
        "vars": {},
        "seed": [{"type": "none", "location": "Camera settings", "value": "Agent configures night mode on, HDR on, flash off.", "status": "sanity"}],
        "end_state": "Camera is set for low light: night mode on, HDR on, flash off.",
    },
    "medium__gallery__001": {
        "vars": {"food_category": "{food_category}"},
        "seed": [{"type": "photo", "location": "/sdcard/DCIM/Camera/", "value": "5 '{food_category}' photos (pizza1.jpg..pizza5.jpg) of differing resolutions (see seed_files/).", "status": "needs_seed", "device_path": "/sdcard/DCIM/Camera/pizza1.jpg (and pizza2-5.jpg)"}],
        "end_state": "A new album contains the best 3 {food_category} photos by resolution.",
    },
    "easy__gallery__001": {
        "vars": {},
        "seed": [{"type": "photo", "location": "/sdcard/DCIM/Camera/", "value": "A photo with mtime ~1 hour ago (hide_me.jpg) so it is the 'specific photo taken about an hour back'.", "status": "needs_seed", "device_path": "/sdcard/DCIM/Camera/hide_me.jpg"}],
        "end_state": "That photo is hidden from the main Gallery view.",
    },
    "medium__gallery__002": {
        "vars": {},
        "seed": [{"type": "screenshot", "location": "/sdcard/DCIM/Screenshots/", "value": "Several screenshots with mtimes > 1 month old (2026-05-xx and earlier), e.g. old_shot_1.png..old_shot_4.png.", "status": "needs_seed"}],
        "end_state": "All screenshots older than a month are deleted; agent reports the count and storage freed.",
    },
    "medium__gallery-telegram__001": {
        "vars": {"contact": "{contact}"},
        "seed": [
            {"type": "photo", "location": "/sdcard/DCIM/Camera/", "value": "A short burst of 4-5 photos taken 'today' (today_1.jpg..today_5.jpg, mtime today) to make a GIF.", "status": "needs_seed", "device_path": "/sdcard/DCIM/Camera/today_1.jpg (and today_2-5.jpg)"},
            {"type": "telegram_contact", "location": "Telegram (real)", "value": "Contact '{contact}' exists.", "status": "present"},
        ],
        "end_state": "A GIF from today's burst is created and shared via Telegram to {contact}.",
    },
    "easy__messages__001": {
        "vars": {"search word": "{search word}"},
        "seed": [{"type": "sms", "location": "Messages (content://sms)", "value": "An SMS containing the word '{search word}' (e.g. 'Your movie ticket for Sat is confirmed'). SMS insert may be blocked on non-rooted.", "status": "needs_ui"}],
        "end_state": "Agent finds the message containing '{search word}'.",
    },
    "easy__messages__002": {
        "vars": {},
        "seed": [{"type": "none", "location": "Messages", "value": "Uses the device's real location.", "status": "sanity"}],
        "end_state": "A text with the current location is sent.",
    },
    "medium__messages__001": {
        "vars": {},
        "seed": [{"type": "sms", "location": "Messages (content://sms)", "value": "SMS from this week containing an unanswered question (e.g. 'Are we meeting on Friday?'). SMS insert may be blocked on non-rooted.", "status": "needs_ui"}],
        "end_state": "The most recent unanswered-question message is answered with 'Will get back to you fr in some time!'; the agent tells which question it answered.",
    },
    "hard__calendar-telegram-obsidian__002": {
        "vars": {"meeting folder": "{meeting folder}"},
        "ask_user_fact": "The meeting is with {contact}.",
        "seed": [
            {"type": "calendar_event", "location": "Calendar", "value": "A meeting event this week with a known start time (e.g. 'Team Sync' Wed 08:30 so the reschedule branch is exercised).", "status": "needs_ui"},
            {"type": "telegram_contact", "location": "Telegram (real)", "value": "Contact '{contact}' exists.", "status": "present"},
        ],
        "end_state": "A note logs which message was sent (reschedule if <9am, else confirm); the event is starred.",
    },
    "easy__phone__001": {
        "vars": {},
        "seed": [{"type": "none", "location": "Phone settings", "value": "Agent sets the unknown-caller ringtone to a smooth-jazz-equivalent.", "status": "sanity"}],
        "end_state": "Custom ringtone set for unknown numbers.",
    },
    "medium__phone__001": {
        "vars": {"digits": "{digits}"},
        "seed": [{"type": "call_log", "location": "Phone call log (content://call_log/calls)", "value": "Call-log entries with numbers starting '{digits}' (98765xxxx). Call-log insert is usually allowed without root.", "status": "needs_ui"}],
        "end_state": "Agent reports whether all matching calls are from the same number and flags if so.",
    },
}

# Schedule order for Day 1 of the RUNNABLE 530 subset (22 tasks; the 730
# superset's Day 1 has 8 more tasks that the subset drops).
DAY1_ORDER = [
    "easy__chrome__001",
    "medium__chrome__001",
    "medium__chrome-telegram__001",
    "hard__google-search-obsidian-telegram__057",
    "easy__google-search__001",
    "medium__google-search__001",
    "easy__calendar__001",
    "medium__calendar__001",
    "easy__contacts__001",
    "medium__contacts__001",
    "easy__obsidian__001",
    "medium__obsidian__001",
    "hard__chrome-telegram-notes__008",
    "easy__camera__001",
    "medium__camera__001",
    "medium__gallery__001",
    "easy__gallery__001",
    "medium__gallery-telegram__001",
    "easy__messages__001",
    "medium__messages__001",
    "hard__calendar-telegram-obsidian__002",
    "easy__phone__001",
]

# Literal seed-file templates written into each task's seed_files/ dir. Each
# entry maps local artifact filename -> {content template, on-device path}.
# {key} templates are resolved from config/user.yaml at build time.
SEED_FILE_TEMPLATES: dict[str, dict[str, dict[str, str]]] = {
    "hard__google-search-obsidian-telegram__057": {
        "note_stock_watch.md": {
            "content": (
                "# {stock note title}\n\n"
                "- Stock: {stock name}\n"
                "- Threshold: {stock threshold}\n"
                "- Last recorded value: {stock last value}\n"
                "- Date: 2026-08-03\n"
            ),
            "device_path": "/sdcard/Obsidian/Papers vault oneplus/{stock note title}.md",
        },
    },
}


def load_dataset() -> dict:
    return json.loads(DATASET.read_text(encoding="utf-8"))


def load_ask_user_facts() -> dict:
    if ASK_USER_FACTS.exists():
        return json.loads(ASK_USER_FACTS.read_text(encoding="utf-8"))
    return {}


def _spec_keys(obj) -> set[str]:
    """Collect every {key} referenced anywhere in a spec (vars, seeds, end_state...)."""
    if isinstance(obj, str):
        return set(template_keys(obj))
    if isinstance(obj, dict):
        keys: set[str] = set()
        for v in obj.values():
            keys |= _spec_keys(v)
        return keys
    if isinstance(obj, list):
        keys = set()
        for v in obj:
            keys |= _spec_keys(v)
        return keys
    return set()


def resolve_vars(task: dict, spec: dict) -> dict:
    """Return {placeholder_name: value} for every placeholder on the dataset row."""
    ph = task.get("placeholders") or []
    declared = spec.get("vars", {})
    out: dict[str, str] = {}
    for name in ph:
        if name in declared:
            out[name] = declared[name]
        else:
            # Placeholders not covered by the spec are left verbatim so the batch
            # runner errors loudly rather than silently guessing.
            out[name] = None
    return out


def render_prompt(task: dict, vars_map: dict) -> str:
    """Render exactly like the batch runner (task_dataset.render_prompt): start from
    prompt_text and substitute [name]. Also handle {name} / {{ name }} forms so the
    manifest stays readable regardless of which template variant a task uses."""
    prompt = task.get("prompt_text") or task.get("prompt_template") or ""
    for name, value in vars_map.items():
        if value is None:
            continue
        prompt = prompt.replace("{{ " + name + " }}", value)
        prompt = prompt.replace("{" + name + "}", value)
        prompt = prompt.replace("[" + name + "]", value)
    return prompt


def build_day(day: int) -> Path:
    dataset = load_dataset()
    facts = load_ask_user_facts()
    cfg = load_user_config(CONFIG_PATH)
    tasks = {t["task_id"]: t for t in dataset["tasks"] if t.get("day") == day}

    if day == 1:
        order = DAY1_ORDER
        spec_map = DAY1_TASKS
    else:
        # Fallback for other days: alphabetical by task_id (to be fleshed out later).
        order = sorted(tasks.keys())
        spec_map = {}

    day_dir = SEEDS_ROOT / f"day_{day}"
    day_dir.mkdir(parents=True, exist_ok=True)

    # stale-task cleanup: drop task subdirs that no longer belong to this day's set
    # (e.g. tasks dropped from the runnable subset) so a rebuild is always clean.
    current_ids = set(order)
    for child in day_dir.iterdir():
        if child.is_dir() and child.name not in current_ids:
            print(f"  [cleanup] removing stale task dir {child.name}")
            shutil.rmtree(child, ignore_errors=True)

    unresolved_errors: list[str] = []
    records: list[dict] = []
    for task_id in order:
        task = tasks.get(task_id)
        if task is None:
            print(f"  [warn] {task_id} not found on day {day}")
            continue
        # spec values are {config_key} templates (persona-free) -> resolve now
        raw_spec = spec_map.get(task_id, {"vars": {}})
        spec = resolve_templates(raw_spec, cfg)
        var_map = resolve_vars(task, spec)
        missing = [k for k, v in var_map.items() if v is None]
        if missing:
            unresolved_errors.append(f"{task_id}: {', '.join(missing)}")
            print(f"  [warn] {task_id} unresolved placeholders: {missing}")

        fact = spec.get("ask_user_fact") or facts.get(task_id)
        if fact and "{" in fact:
            fact = resolve_template(fact, cfg)

        # config keys this task consumed (from the UNRESOLVED spec; transparency +
        # verifier cross-check)
        config_keys_used = sorted({k for k in _spec_keys(raw_spec) if k in cfg})
        seed_device_paths = {
            str(i): s["device_path"]
            for i, s in enumerate(spec.get("seed", []))
            if s.get("device_path")
        }
        record = {
            "task_id": task_id,
            "day": day,
            "schedule_position": order.index(task_id) + 1,
            "bucket": task.get("bucket"),
            "difficulty": task.get("difficulty"),
            "points": task.get("points"),
            "apps": task.get("apps"),
            "is_ask_user": task.get("is_ask_user"),
            "task_number_within_dataset_app": task.get("task_number_within_dataset_app"),
            "prompt_resolved": render_prompt(task, var_map),
            "prompt_template": task.get("prompt_template"),
            "vars_required": var_map,
            "ask_user_fact": fact,
            "fabricated_seed_data": spec.get("seed", []),
            "seed_device_paths": seed_device_paths,
            "expected_end_state": spec.get("end_state", ""),
            "config_keys_used": config_keys_used,
            "built_at": date.today().isoformat(),
        }
        records.append(record)

        # per-task folder + manifest
        task_dir = day_dir / task_id
        task_dir.mkdir(parents=True, exist_ok=True)
        (task_dir / "manifest.json").write_text(
            json.dumps(record, indent=2, ensure_ascii=False), encoding="utf-8"
        )
        # literal seed-file templates (resolved from config) + on-device path links
        device_links: list[str] = []
        for fname, fmeta in SEED_FILE_TEMPLATES.get(task_id, {}).items():
            sf = task_dir / "seed_files"
            sf.mkdir(parents=True, exist_ok=True)
            (sf / fname).write_text(resolve_template(fmeta["content"], cfg), encoding="utf-8")
            device_links.append(f"- `{fname}` -> `{resolve_template(fmeta['device_path'], cfg)}`")
        for i, s in enumerate(spec.get("seed", [])):
            if s.get("device_path"):
                device_links.append(f"- seed #{i} ({s.get('type')}) -> `{s['device_path']}`")
        if device_links:
            sf = task_dir / "seed_files"
            sf.mkdir(parents=True, exist_ok=True)
            (sf / "DEVICE_PATHS.md").write_text(
                f"# Seed artifacts for `{task_id}` -> on-device paths\n\n"
                + "\n".join(device_links) + "\n", encoding="utf-8")

    # impeccable: a day must never ship with unresolved placeholders - fail loudly
    if unresolved_errors:
        raise SystemExit(f"Day {day} has unresolved placeholders:\n  " + "\n  ".join(unresolved_errors))

    # day-level index
    manifest = {
        "schema_version": 1,
        "day": day,
        "built_at": date.today().isoformat(),
        "dataset": str(DATASET.relative_to(REPO_ROOT)),
        "task_count": len(records),
        "buckets": {b: sum(1 for r in records if r["bucket"] == b) for b in {r["bucket"] for r in records}},
        "tasks": [r["task_id"] for r in records],
    }
    (day_dir / "manifests.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8"
    )

    # day-level jsonl, one meticulous line per task
    jsonl_path = day_dir / f"day_{day}_fabricated_data.jsonl"
    with jsonl_path.open("w", encoding="utf-8") as handle:
        for record in records:
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")

    print(f"Wrote {len(records)} task manifests to {day_dir}")
    return day_dir


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--day", type=int, required=True)
    args = parser.parse_args()
    build_day(args.day)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
