"""Shared pytest helpers for DailyBench tests."""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
SCRIPTS = ROOT / "scripts"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))


def _adb_device_serials() -> list[str]:
    """Return serials of every attached ADB device whose state is exactly 'device'."""
    if shutil.which("adb") is None:
        return []
    try:
        result = subprocess.run(["adb", "devices"], capture_output=True, text=True, timeout=5, check=False)
    except OSError:
        return []
    serials = []
    for line in result.stdout.splitlines()[1:]:
        parts = line.split()
        if len(parts) >= 2 and parts[1] == "device":
            serials.append(parts[0])
    return serials


def first_adb_device() -> str | None:
    """Return the serial of the first attached ADB device (wired or wireless), or None if none is reachable."""
    serials = _adb_device_serials()
    return serials[0] if serials else None


def first_wired_adb_device() -> str | None:
    """Return the serial of the first attached wired (non ip:port) ADB device, or None if there isn't one."""
    for serial in _adb_device_serials():
        if ":" not in serial:
            return serial
    return None


def first_wireless_adb_device() -> str | None:
    """Return the serial of the first attached wireless (ip:port) ADB device, or None if there isn't one."""
    for serial in _adb_device_serials():
        if ":" in serial:
            return serial
    return None
