"""Threaded phone sampler for battery and thermal metrics."""

from __future__ import annotations

import json
import threading
import time
from pathlib import Path

from .adb import capture_sample, utc_now


class Sampler(threading.Thread):
    """Sample phone battery and thermal state at a fixed interval."""

    def __init__(self, serial: str, sample_interval: float, out_path: Path) -> None:
        super().__init__(daemon=True)
        self.serial = serial
        self.sample_interval = sample_interval
        self.out_path = out_path
        self.stop_event = threading.Event()
        self.samples: list[dict] = []
        self.errors: list[str] = []

    def run(self) -> None:
        """Collect samples until asked to stop."""
        while not self.stop_event.is_set():
            started = time.monotonic()
            try:
                sample = capture_sample(self.serial)
                self.samples.append(sample)
                with self.out_path.open("a", encoding="utf-8") as handle:
                    handle.write(json.dumps(sample, sort_keys=True) + "\n")
            except Exception as exc:  # noqa: BLE001
                self.errors.append(f"{utc_now()} {exc}")
            remaining = max(0.0, self.sample_interval - (time.monotonic() - started))
            self.stop_event.wait(remaining)

    def stop(self) -> None:
        """Stop sampling and join the thread."""
        self.stop_event.set()
        self.join(timeout=5)
