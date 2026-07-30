"""Pytest coverage for ADB output parsing and real ADB command execution (wired and wireless)."""

from __future__ import annotations

import subprocess
import time

import pytest
from conftest import first_adb_device

from DailyBench import adb
from DailyBench.adb import adb_cmd, adb_shell, capture_sample, get_foreground_package, parse_battery_output, parse_thermal_output, reset_app_state, should_force_stop

DEVICE_SERIAL = first_adb_device()


def test_parse_battery_output_normalizes_fields() -> None:
    """`dumpsys battery` text is parsed into normalized numeric/bool fields (temps in °C, tenths converted)."""
    text = """
level: 79
temperature: 320
PhoneTemp: 345
Charge counter: 4123456
AC powered: false
USB powered: true
""".strip()
    parsed = parse_battery_output(text)
    assert parsed["level_pct"] == 79
    assert parsed["battery_temp_c"] == 32.0
    assert parsed["vendor_phone_temp_c"] == 34.5
    assert parsed["charge_counter_uah"] == 4123456
    assert parsed["usb_powered"] is True


def test_parse_thermal_output_extracts_hal_temperatures() -> None:
    """`dumpsys thermalservice` text yields a thermal status code plus a per-sensor HAL temperature map."""
    text = """
Thermal Status: 2
Current temperatures from HAL:
Temperature{mValue=41.5, mType=0, mName=CPU, mStatus=0}
Temperature{mValue=36.2, mType=0, mName=BATTERY, mStatus=0}
Current cooling devices from HAL:
""".strip()
    parsed = parse_thermal_output(text)
    assert parsed["thermal_status_code"] == 2
    assert parsed["hal_temperatures_c"]["CPU"]["value_c"] == 41.5
    assert parsed["hal_temperatures_c"]["BATTERY"]["status_code"] == 0


def test_adb_cmd_passes_through_wired_usb_serial_verbatim() -> None:
    """A wired USB device serial (alphanumeric, no colon) is forwarded as-is to `adb -s`."""
    assert adb_cmd("R58N801XXXX", "shell", "dumpsys battery") == [
        "adb", "-s", "R58N801XXXX", "shell", "dumpsys battery",
    ]


def test_adb_cmd_passes_through_wireless_ip_port_serial_verbatim() -> None:
    """A wireless ADB serial (`ip:port`, e.g. over Tailscale or LAN) is forwarded the same way as a wired one."""
    assert adb_cmd("100.75.134.64:5555", "shell", "dumpsys battery") == [
        "adb", "-s", "100.75.134.64:5555", "shell", "dumpsys battery",
    ]


@pytest.mark.skipif(DEVICE_SERIAL is None, reason="No ADB device attached (wired or wireless)")
def test_adb_shell_raises_for_unreachable_serial() -> None:
    """A real `adb` invocation against a serial that doesn't exist fails loudly instead of hanging or returning junk."""
    with pytest.raises(subprocess.CalledProcessError):
        adb_shell("no-such-device:5555", "dumpsys battery")


def test_should_force_stop_excludes_launcher_systemui_and_portal() -> None:
    """The launcher, systemui, and mobilerun's own Portal are never force-stopped, across common OEM package names."""
    assert should_force_stop("com.android.launcher") is False
    assert should_force_stop("com.oneplus.launcher") is False
    assert should_force_stop("com.sec.android.app.launcher") is False
    assert should_force_stop("com.android.systemui") is False
    assert should_force_stop("com.mobilerun.portal") is False


def test_should_force_stop_allows_regular_apps() -> None:
    """An ordinary user-facing app is eligible for the between-task force-stop reset."""
    assert should_force_stop("com.google.android.youtube") is True
    assert should_force_stop("com.google.android.gm") is True


def test_get_foreground_package_parses_mcurrentfocus(monkeypatch) -> None:
    """get_foreground_package extracts the package name from a real `dumpsys window` mCurrentFocus line."""
    dumpsys_output = "  mCurrentFocus=Window{df5fae u0 com.android.launcher/com.android.launcher.Launcher}\n"
    monkeypatch.setattr(adb, "adb_shell", lambda serial, command: dumpsys_output)
    assert get_foreground_package("device-1") == "com.android.launcher"


def test_get_foreground_package_returns_none_when_unparseable(monkeypatch) -> None:
    """A dumpsys output with no recognizable mCurrentFocus line yields None instead of raising."""
    monkeypatch.setattr(adb, "adb_shell", lambda serial, command: "mCurrentFocus=null\n")
    assert get_foreground_package("device-1") is None


@pytest.mark.skipif(DEVICE_SERIAL is None, reason="No ADB device attached (wired or wireless)")
def test_reset_app_state_force_stops_foreground_app_and_returns_home() -> None:
    """Against a real device: launch YouTube, confirm it's foreground, then reset_app_state force-stops it and lands on the launcher."""
    assert DEVICE_SERIAL is not None
    subprocess.run(
        ["adb", "-s", DEVICE_SERIAL, "shell", "am", "start", "-n", "com.google.android.youtube/com.google.android.youtube.HomeActivity"],
        capture_output=True, timeout=10, check=False,
    )
    time.sleep(2)
    assert get_foreground_package(DEVICE_SERIAL) == "com.google.android.youtube"

    stopped = reset_app_state(DEVICE_SERIAL)
    assert stopped == "com.google.android.youtube"

    time.sleep(1)
    assert get_foreground_package(DEVICE_SERIAL) != "com.google.android.youtube"



@pytest.mark.skipif(DEVICE_SERIAL is None, reason="No ADB device attached (wired or wireless)")
def test_capture_sample_against_real_attached_device() -> None:
    """capture_sample runs real `adb shell` calls against whatever device is attached and returns sane, parsed values.

    The currently attached test device connects over wireless ADB (an `ip:port` serial), but adb_cmd/adb_shell apply
    no special-casing between connection types, so this same path covers a wired USB serial identically.
    """
    assert DEVICE_SERIAL is not None
    sample = capture_sample(DEVICE_SERIAL)
    assert 0 <= sample["battery"]["level_pct"] <= 100
    assert isinstance(sample["thermal"]["hal_temperatures_c"], dict)
    assert sample["thermal"]["hal_temperatures_c"]
    assert "timestamp_utc" in sample
