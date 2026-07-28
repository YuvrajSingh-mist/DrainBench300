"""Pytest coverage for ADB output parsing."""

from __future__ import annotations

from drainbench.adb import parse_battery_output, parse_thermal_output


def test_parse_battery_output_normalizes_fields() -> None:
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
