"""Filesystem and metadata helpers for DrainBench runs."""

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


def make_run_dir(base_dir: str, label: str) -> Path:
    """Create and return a new timestamped run directory."""
    run_id = f"{datetime.now().strftime('%Y%m%d-%H%M%S')}-{slugify(label)}"
    run_dir = Path(base_dir) / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    return run_dir


def write_json(path: Path, payload: Any) -> None:
    """Write pretty JSON to disk with a trailing newline."""
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")


def write_text(path: Path, text: str) -> None:
    """Write plain text to disk."""
    path.write_text(text, encoding="utf-8")
