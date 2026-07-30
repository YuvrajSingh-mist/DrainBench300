#!/usr/bin/env python3
"""SDK-only device health check: connects to one ADB serial via mobilerun's AndroidDriver
and exercises a few real device operations. Used by scripts/smoke_test.sh in place of the
`mobilerun ping`/`mobilerun doctor` CLI commands, since this harness drives mobilerun purely
through its Python SDK (see https://docs.mobilerun.ai/framework/sdk/adb-tools).

Prints one `CHECK <name> <PASS|WARN|FAIL> <message>` line per check plus a final
`RESULT <PASS|WARN|FAIL>` line, and exits 0 for PASS/WARN, 1 for FAIL.
"""

from __future__ import annotations

import argparse
import asyncio
import sys

from mobilerun import AndroidDriver


def build_parser() -> argparse.ArgumentParser:
    """Build the CLI parser for the device health check."""
    parser = argparse.ArgumentParser(description="SDK-only ADB device + mobilerun Portal health check.")
    parser.add_argument("--serial", required=True, help="ADB serial (USB device ID or ip:port for wireless)")
    parser.add_argument("--timeout", type=float, default=30.0, help="Overall timeout in seconds for all checks")
    return parser


def report(name: str, status: str, message: str) -> None:
    """Print one CHECK line in the shared format the shell wrapper parses."""
    print(f"CHECK {name} {status} {message}")


async def run_checks(serial: str) -> str:
    """Run the connect/portal/date/screenshot checks and return the overall PASS/WARN/FAIL verdict."""
    driver = AndroidDriver(serial=serial)

    try:
        await driver.connect()
    except Exception as exc:
        report("adb_connect", "FAIL", f"could not connect to {serial}: {exc}")
        return "FAIL"
    report("adb_connect", "PASS", f"{serial} is online")

    if driver.portal_available:
        report("portal", "PASS", "mobilerun Portal reachable")
    else:
        report("portal", "WARN", "Portal not available - actions will fall back to plain ADB")

    overall = "PASS"

    try:
        device_date = await driver.get_date()
        report("get_date", "PASS", f"device reports: {device_date}")
    except Exception as exc:
        report("get_date", "FAIL", f"could not read device date: {exc}")
        overall = "FAIL"

    try:
        screenshot_bytes = await driver.screenshot()
        report("screenshot", "PASS", f"captured {len(screenshot_bytes)} bytes")
    except Exception as exc:
        report("screenshot", "FAIL", f"could not capture a screenshot: {exc}")
        overall = "FAIL"

    if overall == "PASS" and not driver.portal_available:
        overall = "WARN"
    return overall


def main() -> int:
    """Run the device health check and print the final RESULT line."""
    args = build_parser().parse_args()
    try:
        verdict = asyncio.run(asyncio.wait_for(run_checks(args.serial), timeout=args.timeout))
    except asyncio.TimeoutError:
        report("timeout", "FAIL", f"checks did not complete within {args.timeout}s")
        verdict = "FAIL"
    print(f"RESULT {verdict}")
    return 0 if verdict in ("PASS", "WARN") else 1


if __name__ == "__main__":
    raise SystemExit(main())
