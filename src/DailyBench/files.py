"""Filesystem and metadata helpers for DailyBench runs."""

from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any


def slugify(value: str) -> str:
    """Convert a label into a filesystem-safe slug."""
    value = re.sub(r"[^a-z0-9]+", "-", value.strip().lower())
    return value.strip("-") or "task"


def dated_out_dir(base_dir: str | Path) -> Path:
    """Insert a date-time stamp as the top-level segment right under a `runs`-rooted base dir.

    `runs/gmail/easy` becomes `runs/2026-07-30-143052/gmail/easy` — a unique batch-level
    folder so re-running the same bucket/app/config seconds later lands in a different
    top-level directory instead of mixing with the previous batch's run folders.
    """
    path = Path(base_dir)
    date_str = datetime.now().strftime("%Y-%m-%d-%H%M%S")
    if path.parts and path.parts[0] == "runs":
        return Path(path.parts[0]) / date_str / Path(*path.parts[1:])
    return path / date_str


def make_run_dir(base_dir: str, label: str) -> Path:
    """Create and return a new run directory named by its label, nested under a date-time folder."""
    run_id = slugify(label)
    run_dir = dated_out_dir(base_dir) / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    return run_dir


def write_json(path: Path, payload: Any) -> None:
    """Write pretty JSON to disk with a trailing newline."""
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")


def write_text(path: Path, text: str) -> None:
    """Write plain text to disk."""
    path.write_text(text, encoding="utf-8")
