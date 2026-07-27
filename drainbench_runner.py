#!/usr/bin/env python3
"""Run a benchmarked task while sampling Android battery/thermal state and recording screen."""

from __future__ import annotations

import argparse
import json
import os
import re
import shlex
import signal
import subprocess
import sys
import threading
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


THERMAL_RE = re.compile(
    r"Temperature\{mValue=(?P<value>[-0-9.]+), mType=(?P<type>\d+), mName=(?P<name>[^,]+), mStatus=(?P<status>\d+)\}"
)


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def slugify(value: str) -> str:
    value = value.strip().lower()
    value = re.sub(r"[^a-z0-9]+", "-", value)
    return value.strip("-") or "task"


def run_checked(cmd: list[str], *, text: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(cmd, check=True, text=text, capture_output=True)


def adb_cmd(serial: str, *parts: str) -> list[str]:
    return ["adb", "-s", serial, *parts]


def adb_shell(serial: str, command: str) -> str:
    result = run_checked(adb_cmd(serial, "shell", command))
    return result.stdout


def parse_battery_output(text: str) -> dict[str, Any]:
    data: dict[str, Any] = {
        "raw": text,
    }
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
            try:
                data[int_fields[key]] = int(raw_value)
            except ValueError:
                data[int_fields[key]] = raw_value
        elif key in bool_fields:
            data[bool_fields[key]] = raw_value.lower() == "true"

    if "battery_temp_tenths_c" in data:
        data["battery_temp_c"] = data["battery_temp_tenths_c"] / 10.0
    if "vendor_phone_temp_tenths_c" in data:
        data["vendor_phone_temp_c"] = data["vendor_phone_temp_tenths_c"] / 10.0
    return data


def parse_thermal_output(text: str) -> dict[str, Any]:
    data: dict[str, Any] = {
        "raw": text,
        "thermal_status_code": None,
        "hal_temperatures_c": {},
    }
    in_hal_section = False
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("Thermal Status:"):
            try:
                data["thermal_status_code"] = int(stripped.split(":", 1)[1].strip())
            except ValueError:
                data["thermal_status_code"] = stripped.split(":", 1)[1].strip()
        elif stripped == "Current temperatures from HAL:":
            in_hal_section = True
            continue
        elif in_hal_section and stripped.endswith("from HAL:"):
            in_hal_section = False
        elif in_hal_section:
            match = THERMAL_RE.search(stripped)
            if match:
                name = match.group("name")
                data["hal_temperatures_c"][name] = {
                    "value_c": float(match.group("value")),
                    "type_code": int(match.group("type")),
                    "status_code": int(match.group("status")),
                }
    return data


def capture_sample(serial: str) -> dict[str, Any]:
    battery_raw = adb_shell(serial, "dumpsys battery")
    thermal_raw = adb_shell(serial, "dumpsys thermalservice")
    battery = parse_battery_output(battery_raw)
    thermal = parse_thermal_output(thermal_raw)
    return {
        "timestamp_utc": utc_now(),
        "battery": battery,
        "thermal": thermal,
    }


def write_json(path: Path, payload: Any) -> None:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")


class Sampler(threading.Thread):
    def __init__(self, serial: str, sample_interval: float, out_path: Path):
        super().__init__(daemon=True)
        self.serial = serial
        self.sample_interval = sample_interval
        self.out_path = out_path
        self.stop_event = threading.Event()
        self.samples: list[dict[str, Any]] = []
        self.errors: list[str] = []

    def run(self) -> None:
        while not self.stop_event.is_set():
            started = time.monotonic()
            try:
                sample = capture_sample(self.serial)
                self.samples.append(sample)
                with self.out_path.open("a", encoding="utf-8") as handle:
                    handle.write(json.dumps(sample, sort_keys=True) + "\n")
            except Exception as exc:  # noqa: BLE001
                self.errors.append(f"{utc_now()} {exc}")
            elapsed = time.monotonic() - started
            remaining = max(0.0, self.sample_interval - elapsed)
            self.stop_event.wait(remaining)

    def stop(self) -> None:
        self.stop_event.set()
        self.join(timeout=5)


@dataclass
class ScreenRecording:
    process: subprocess.Popen[Any]
    local_path: Path
    stdout_path: Path
    stderr_path: Path


def start_screenrecord(
    serial: str,
    local_path: Path,
    bit_rate: str,
    size: str | None,
    stdout_path: Path,
    stderr_path: Path,
) -> ScreenRecording:
    parts = [
        "scrcpy",
        "-s",
        serial,
        "--record",
        str(local_path),
        "--record-format",
        "mp4",
        "--no-window",
        "--no-audio",
        "--stay-awake",
        "--show-touches",
        "--video-bit-rate",
        bit_rate,
        "--max-fps",
        "30",
    ]
    if size:
        parts.extend(["--max-size", size])
    stdout_handle = stdout_path.open("w", encoding="utf-8")
    stderr_handle = stderr_path.open("w", encoding="utf-8")
    process = subprocess.Popen(
        parts,
        stdout=stdout_handle,
        stderr=stderr_handle,
    )
    time.sleep(1)
    return ScreenRecording(
        process=process,
        local_path=local_path,
        stdout_path=stdout_path,
        stderr_path=stderr_path,
    )


def stop_screenrecord(serial: str, recording: ScreenRecording) -> None:
    if recording.process.poll() is None:
        recording.process.send_signal(signal.SIGINT)
        try:
            recording.process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            recording.process.terminate()
            try:
                recording.process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                recording.process.kill()
                recording.process.wait(timeout=5)
    time.sleep(2)


def summarize(samples: list[dict[str, Any]], meta: dict[str, Any]) -> dict[str, Any]:
    summary: dict[str, Any] = {
        "run_id": meta["run_id"],
        "label": meta["label"],
        "sample_count": len(samples),
        "started_at_utc": meta["started_at_utc"],
        "ended_at_utc": meta["ended_at_utc"],
        "elapsed_seconds": meta["elapsed_seconds"],
        "command_exit_code": meta["command_exit_code"],
    }
    if not samples:
        return summary

    first = samples[0]
    last = samples[-1]
    first_battery = first["battery"]
    last_battery = last["battery"]
    summary["battery_level_start_pct"] = first_battery.get("level_pct")
    summary["battery_level_end_pct"] = last_battery.get("level_pct")
    if (
        first_battery.get("level_pct") is not None
        and last_battery.get("level_pct") is not None
    ):
        summary["battery_level_delta_pct"] = (
            last_battery["level_pct"] - first_battery["level_pct"]
        )
    summary["charge_counter_start_uah"] = first_battery.get("charge_counter_uah")
    summary["charge_counter_end_uah"] = last_battery.get("charge_counter_uah")
    if (
        first_battery.get("charge_counter_uah") is not None
        and last_battery.get("charge_counter_uah") is not None
    ):
        summary["charge_counter_delta_uah"] = (
            last_battery["charge_counter_uah"] - first_battery["charge_counter_uah"]
        )

    for key in ["battery_temp_c", "vendor_phone_temp_c"]:
        values = [
            sample["battery"].get(key)
            for sample in samples
            if sample["battery"].get(key) is not None
        ]
        if values:
            base = key.replace("_c", "")
            summary[f"{base}_start_c"] = values[0]
            summary[f"{base}_end_c"] = values[-1]
            summary[f"{base}_max_c"] = max(values)

    thermal_statuses = [
        sample["thermal"].get("thermal_status_code")
        for sample in samples
        if isinstance(sample["thermal"].get("thermal_status_code"), int)
    ]
    if thermal_statuses:
        summary["thermal_status_max"] = max(thermal_statuses)

    for sensor_name in ["CPU", "GPU", "BATTERY", "SKIN", "NPU", "POWER_AMPLIFIER"]:
        values = []
        for sample in samples:
            entry = sample["thermal"]["hal_temperatures_c"].get(sensor_name)
            if entry is not None:
                values.append(entry["value_c"])
        if values:
            name = sensor_name.lower()
            summary[f"{name}_temp_start_c"] = values[0]
            summary[f"{name}_temp_end_c"] = values[-1]
            summary[f"{name}_temp_max_c"] = max(values)

    return summary


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run one benchmarked task while sampling battery and thermal state."
    )
    parser.add_argument(
        "--serial",
        default=os.environ.get("DRAINBENCH_SERIAL"),
        help="ADB serial to use. Defaults to DRAINBENCH_SERIAL.",
    )
    parser.add_argument(
        "--label",
        required=True,
        help="Short task label used for folder naming.",
    )
    parser.add_argument(
        "--sample-interval",
        type=float,
        default=1.0,
        help="Sampling interval in seconds. Default: 1.0",
    )
    parser.add_argument(
        "--out-dir",
        default="runs",
        help="Base output directory. Default: runs",
    )
    parser.add_argument(
        "--screen-bit-rate",
        default="8M",
        help="scrcpy video bit rate. Default: 8M",
    )
    parser.add_argument(
        "--screen-size",
        default=None,
        help="Optional scrcpy max-size value, e.g. 1080.",
    )
    parser.add_argument(
        "--no-screen-record",
        action="store_true",
        help="Disable phone screen recording.",
    )
    parser.add_argument(
        "command",
        nargs=argparse.REMAINDER,
        help="Command to run. Pass it after --.",
    )
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    if not args.serial:
        parser.error("ADB serial required via --serial or DRAINBENCH_SERIAL")
    if not args.command:
        parser.error("Benchmark command required after --")

    command = args.command
    if command and command[0] == "--":
        command = command[1:]
    if not command:
        parser.error("Benchmark command required after --")

    run_id = f"{datetime.now().strftime('%Y%m%d-%H%M%S')}-{slugify(args.label)}"
    run_dir = Path(args.out_dir) / run_id
    run_dir.mkdir(parents=True, exist_ok=True)

    meta = {
        "run_id": run_id,
        "label": args.label,
        "serial": args.serial,
        "started_at_utc": utc_now(),
        "command": command,
        "sample_interval_seconds": args.sample_interval,
    }
    write_json(run_dir / "meta.json", meta)

    preflight = capture_sample(args.serial)
    write_json(run_dir / "preflight.json", preflight)

    recording = None
    if not args.no_screen_record:
        local_mp4 = run_dir / "screen.mp4"
        scrcpy_stdout = run_dir / "screenrecord.stdout.txt"
        scrcpy_stderr = run_dir / "screenrecord.stderr.txt"
        recording = start_screenrecord(
            args.serial,
            local_mp4,
            bit_rate=args.screen_bit_rate,
            size=args.screen_size,
            stdout_path=scrcpy_stdout,
            stderr_path=scrcpy_stderr,
        )
        meta["screenrecord_local_path"] = str(local_mp4)
        meta["screenrecord_stdout_path"] = str(scrcpy_stdout)
        meta["screenrecord_stderr_path"] = str(scrcpy_stderr)
        write_json(run_dir / "meta.json", meta)

    sampler = Sampler(args.serial, args.sample_interval, run_dir / "samples.ndjson")
    sampler.start()

    stdout_path = run_dir / "command.stdout.txt"
    stderr_path = run_dir / "command.stderr.txt"
    start_monotonic = time.monotonic()
    with stdout_path.open("w", encoding="utf-8") as out_handle, stderr_path.open(
        "w", encoding="utf-8"
    ) as err_handle:
        proc = subprocess.Popen(command, stdout=out_handle, stderr=err_handle)
        try:
            return_code = proc.wait()
        except KeyboardInterrupt:
            proc.send_signal(signal.SIGINT)
            return_code = proc.wait()
    elapsed = time.monotonic() - start_monotonic

    sampler.stop()

    if recording is not None:
        stop_screenrecord(args.serial, recording)
        if recording.local_path.exists():
            meta["screenrecord_local_path"] = str(recording.local_path)
        if recording.process.returncode is not None:
            meta["screenrecord_exit_code"] = recording.process.returncode

    postflight = capture_sample(args.serial)
    write_json(run_dir / "postflight.json", postflight)

    meta["ended_at_utc"] = utc_now()
    meta["elapsed_seconds"] = elapsed
    meta["command_exit_code"] = return_code
    meta["sampler_errors"] = sampler.errors
    write_json(run_dir / "meta.json", meta)

    summary = summarize(sampler.samples, meta)
    write_json(run_dir / "summary.json", summary)

    print(f"Run directory: {run_dir}")
    print(json.dumps(summary, indent=2, sort_keys=True))
    return return_code


if __name__ == "__main__":
    raise SystemExit(main())
