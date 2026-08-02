"""ADB helpers for DailyBench benchmark runs."""

from __future__ import annotations

import json
import os
import re
import subprocess
import time
from datetime import datetime, timezone
from typing import Any

THERMAL_RE = re.compile(
    r"Temperature\{mValue=(?P<value>[-0-9.]+), mType=(?P<type>\d+), mName=(?P<name>[^,]+), mStatus=(?P<status>\d+)\}"
)
FOREGROUND_PACKAGE_RE = re.compile(r"mCurrentFocus=Window\{[^}]*\su\d+\s+([a-zA-Z0-9_.]+)/")

# The OnePlus/ColorOS launcher on the benchmark's target device keeps a stale Recents card for
# a force-stopped app until it's explicitly dismissed - force-stop kills the process, but Recents
# is launcher-owned task history, not process state. This matches that launcher's "Close all"
# control by resource-id (other launchers may not expose one - clear_recents() treats that as a
# no-op, not an error).
_CLEAR_ALL_BUTTON_RE = re.compile(
    r'resource-id="[^"]*(?:btn_clear|clear_all)[^"]*"[^>]*bounds="\[(\d+),(\d+)\]\[(\d+),(\d+)\]"'
)
_RECENTS_DUMP_PATH = "/sdcard/dailybench_recents_dump.xml"

# Never force-stopped even if found in the foreground: the mobilerun Portal is needed
# for the *next* task's own automation (auto_setup would just relaunch it anyway, but
# there's no reason to churn it). Launcher/systemui packages vary by OEM skin, so
# they're matched by substring in should_force_stop() instead of listed here.
APP_RESET_EXCLUDED_PACKAGES = {"com.mobilerun.portal"}
APP_RESET_EXCLUDED_SUBSTRINGS = ("launcher", "systemui")


def should_force_stop(package: str) -> bool:
    """Decide whether a foreground package is safe to force-stop for a between-task reset."""
    if package in APP_RESET_EXCLUDED_PACKAGES:
        return False
    return not any(marker in package.lower() for marker in APP_RESET_EXCLUDED_SUBSTRINGS)


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


# "    UID u0a209: 51.9 fg: 3.70 ( ..." — per-app estimated power (mAh) in the
# "Estimated power use (mAh):" section of `dumpsys batterystats`. u0a<id> = user-0 app id
# (full uid is 10000 + id).
BATTERY_STATS_UID_RE = re.compile(r"UID u0a(\d+):\s*([0-9.]+)")
# "package:com.google.android.apps.docs uid:10209" from `pm list packages -U`.
PM_PACKAGE_UID_RE = re.compile(r"package:(\S+)\s+uid:(\d+)")


def capture_app_battery(serial: str) -> dict[str, float]:
    """Return {package: estimated_mAh} for every app from `dumpsys batterystats`.

    Cumulative since the last reset/boot — the harness diffs a pre/post pair to get
    per-run per-app consumption, so no intrusive `--reset` is needed. Best-effort:
    an empty dict when the device or parsing fails.
    """
    try:
        raw = adb_shell(serial, "dumpsys batterystats")
        packages = adb_shell(serial, "pm list packages -U")
    except subprocess.CalledProcessError:
        return {}
    uid_to_pkg: dict[int, str] = {}
    for line in packages.splitlines():
        match = PM_PACKAGE_UID_RE.search(line)
        if match:
            uid_to_pkg[int(match.group(2)) % 10000] = match.group(1)
    result: dict[str, float] = {}
    in_estimated = False
    for line in raw.splitlines():
        stripped = line.strip()
        if not stripped:
            in_estimated = False
            continue
        if stripped.startswith("Estimated power use"):
            in_estimated = True
            continue
        if in_estimated:
            match = BATTERY_STATS_UID_RE.search(stripped)
            if match:
                pkg = uid_to_pkg.get(int(match.group(1)))
                if pkg:
                    result[pkg] = float(match.group(2))
    return result


def get_foreground_package(serial: str) -> str | None:
    """Return the package name currently focused on-screen, or None if it can't be determined."""
    output = adb_shell(serial, "dumpsys window")
    match = FOREGROUND_PACKAGE_RE.search(output)
    return match.group(1) if match else None


def force_stop_app(serial: str, package: str) -> None:
    """Force-stop one Android package via `am force-stop`."""
    run_checked(adb_cmd(serial, "shell", "am", "force-stop", package))


def press_home(serial: str) -> None:
    """Press the Home button, returning the device to the launcher."""
    run_checked(adb_cmd(serial, "shell", "input", "keyevent", "KEYCODE_HOME"))


def open_recents(serial: str) -> None:
    """Open the Recents/Overview screen."""
    run_checked(adb_cmd(serial, "shell", "input", "keyevent", "KEYCODE_APP_SWITCH"))


def clear_recents(serial: str) -> bool:
    """Best-effort: tap the launcher's "Close all" control in Recents, if present, then
    return home. Returns True if a clear-all control was found and tapped, False if the
    current launcher doesn't expose one (a no-op, not an error).
    """
    open_recents(serial)
    time.sleep(1)
    run_checked(adb_cmd(serial, "shell", "uiautomator", "dump", _RECENTS_DUMP_PATH))
    dump = adb_shell(serial, f"cat {_RECENTS_DUMP_PATH}")
    match = _CLEAR_ALL_BUTTON_RE.search(dump)
    if not match:
        press_home(serial)
        return False
    left, top, right, bottom = (int(value) for value in match.groups())
    center_x, center_y = (left + right) // 2, (top + bottom) // 2
    run_checked(adb_cmd(serial, "shell", "input", "tap", str(center_x), str(center_y)))
    press_home(serial)
    return True


def reset_app_state(serial: str) -> str | None:
    """Force-stop whatever app is in the foreground and return to the home screen.

    Used between benchmark tasks for fairness: without this, a task can silently
    inherit UI/navigation state left behind by whichever app the previous task's
    agent happened to leave open, instead of starting fresh. Also clears any stale
    Recents card left behind by the force-stop (see clear_recents). Returns the
    package that was stopped, or None if nothing eligible was in the foreground.
    """
    package = get_foreground_package(serial)
    stopped = None
    if package and should_force_stop(package):
        force_stop_app(serial, package)
        stopped = package
    clear_recents(serial)
    return stopped


def read_jsonl(path: str, start_offset: int) -> list[dict[str, Any]]:
    """Read JSONL objects from a file starting at a byte offset.
    Returns an empty list if the file doesn't exist (e.g. the proxy logged nothing)."""
    entries: list[dict[str, Any]] = []
    if not os.path.exists(path):
        return entries
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
