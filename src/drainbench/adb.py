"""ADB helpers for DrainBench benchmark runs."""

from __future__ import annotations

import json
import re
import subprocess
import time
from datetime import datetime, timezone
from typing import Any

THERMAL_RE = re.compile(
    r"Temperature\{mValue=(?P<value>[-0-9.]+), mType=(?P<type>\d+), mName=(?P<name>[^,]+), mStatus=(?P<status>\d+)\}"
)


def utc_now() -> str:
    """Return the current UTC timestamp in ISO-8601 format."""
    return datetime.now(timezone.utc).isoformat()


def run_checked(cmd: list[str], *, text: bool = True) -> subprocess.CompletedProcess[str]:
    """Run a subprocess and raise if it fails."""
    return subprocess.run(cmd, check=True, text=text, capture_output=True)


def adb_cmd(serial: str, *parts: str) -> list[str]:
    """Build an adb command for one device serial."""
    return ["adb", "-s", serial, *parts]


def adb_shell(serial: str, command: str) -> str:
    """Run one adb shell command and return stdout."""
    return run_checked(adb_cmd(serial, "shell", command)).stdout


def parse_battery_output(text: str) -> dict[str, Any]:
    """Parse `dumpsys battery` output into normalized fields."""
    data: dict[str, Any] = {"raw": text}
    int_fields = {
        "Battery current": "vendor_battery_current_raw",
        "PhoneTemp": "vendor_phone_temp_tenths_c",
        "Charge counter": "charge_counter_uah",
        "level": "level_pct",
        "temperature": "battery_temp_tenths_c",
        "status": "status_code",
        "health": "health_code",
        "Charging state": "charging_state",
        "PlugType": "vendor_plug_type",
    }
    bool_fields = {
        "AC powered": "ac_powered",
        "USB powered": "usb_powered",
        "Wireless powered": "wireless_powered",
        "Dock powered": "dock_powered",
        "ChargeFastCharger": "vendor_fast_charger",
    }
    for line in text.splitlines():
        if ":" not in line:
            continue
        key, raw_value = [piece.strip() for piece in line.split(":", 1)]
        if key in int_fields:
            data[int_fields[key]] = int(raw_value) if raw_value.isdigit() else raw_value
        elif key in bool_fields:
            data[bool_fields[key]] = raw_value.lower() == "true"
    if "battery_temp_tenths_c" in data:
        data["battery_temp_c"] = data["battery_temp_tenths_c"] / 10.0
    if "vendor_phone_temp_tenths_c" in data:
        data["vendor_phone_temp_c"] = data["vendor_phone_temp_tenths_c"] / 10.0
    return data


def parse_thermal_output(text: str) -> dict[str, Any]:
    """Parse `dumpsys thermalservice` HAL temperatures and status."""
    data: dict[str, Any] = {"raw": text, "thermal_status_code": None, "hal_temperatures_c": {}}
    in_hal_section = False
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("Thermal Status:"):
            raw = stripped.split(":", 1)[1].strip()
            data["thermal_status_code"] = int(raw) if raw.isdigit() else raw
        elif stripped == "Current temperatures from HAL:":
            in_hal_section = True
        elif in_hal_section and stripped.endswith("from HAL:"):
            in_hal_section = False
        elif in_hal_section:
            match = THERMAL_RE.search(stripped)
            if match:
                data["hal_temperatures_c"][match.group("name")] = {
                    "value_c": float(match.group("value")),
                    "type_code": int(match.group("type")),
                    "status_code": int(match.group("status")),
                }
    return data


def capture_sample(serial: str) -> dict[str, Any]:
    """Capture one battery+thermal sample from the phone."""
    return {
        "timestamp_utc": utc_now(),
        "battery": parse_battery_output(adb_shell(serial, "dumpsys battery")),
        "thermal": parse_thermal_output(adb_shell(serial, "dumpsys thermalservice")),
    }


def read_jsonl(path: str, start_offset: int) -> list[dict[str, Any]]:
    """Read JSONL objects from a file starting at a byte offset."""
    entries: list[dict[str, Any]] = []
    with open(path, "r", encoding="utf-8") as handle:
        handle.seek(start_offset)
        for line in handle:
            line = line.strip()
            if not line:
                continue
            try:
                payload = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(payload, dict):
                entries.append(payload)
    return entries


def wait_briefly(seconds: float) -> None:
    """Sleep briefly for tool startup/shutdown coordination."""
    time.sleep(seconds)
