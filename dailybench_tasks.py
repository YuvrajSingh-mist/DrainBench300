"""Thin CLI wrapper for dataset-backed DailyBench task runs."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

from DailyBench.task_batch import main


if __name__ == "__main__":
    raise SystemExit(main())
