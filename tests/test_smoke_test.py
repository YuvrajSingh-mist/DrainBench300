"""Pytest coverage for scripts/smoke_test.sh and scripts/device_health_check.py.

Real subprocesses throughout - no mocks. The LLM checks run against a real local stub
HTTP server this test starts itself (not an external llama.cpp box), so they're
reproducible without network access. The device checks run against whatever real ADB
devices happen to be attached, skipping when a given transport isn't available.
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest
from conftest import first_adb_device, first_wired_adb_device, first_wireless_adb_device

from DailyBench import processes

ROOT = Path(__file__).resolve().parents[1]
SMOKE_TEST = ROOT / "scripts" / "smoke_test.sh"
HEALTH_CHECK = ROOT / "scripts" / "device_health_check.py"

WIRED_SERIAL = first_wired_adb_device()
WIRELESS_SERIAL = first_wireless_adb_device()
ANY_SERIAL = first_adb_device()


def run_smoke_test(args: list[str], timeout: float = 60.0) -> subprocess.CompletedProcess[str]:
    """Run the real smoke_test.sh subprocess with the given args and capture its output."""
    return subprocess.run(
        [str(SMOKE_TEST), *args], cwd=ROOT, capture_output=True, text=True, timeout=timeout, check=False
    )


def failed_count(stdout: str) -> int:
    """Extract the 'N failed' count from the script's final Summary line."""
    match = re.search(r"(\d+) failed", stdout)
    assert match, f"no 'N failed' summary line found in:\n{stdout}"
    return int(match.group(1))


class _StubLLMHandler(BaseHTTPRequestHandler):
    """A tiny real HTTP server standing in for an OpenAI-compatible /v1 endpoint."""

    def do_GET(self) -> None:  # noqa: N802
        """Serve a canned /v1/models listing."""
        if self.path.startswith("/v1/models"):
            body = json.dumps({"object": "list", "data": [{"id": "stub-model-a"}, {"id": "stub-model-b"}]}).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(body)
            return
        self.send_response(404)
        self.end_headers()

    def do_POST(self) -> None:  # noqa: N802
        """Serve a canned /v1/chat/completions reply."""
        length = int(self.headers.get("Content-Length", "0"))
        self.rfile.read(length)
        body = json.dumps(
            {
                "id": "chatcmpl-stub",
                "model": "stub-model-a",
                "choices": [{"message": {"content": "pong"}, "finish_reason": "stop"}],
            }
        ).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format: str, *args: object) -> None:  # noqa: A002
        """Silence default request logging so test output stays clean."""
        return


@pytest.fixture
def stub_llm_server():
    """Start a real local stub OpenAI-compatible server for the duration of one test."""
    server = ThreadingHTTPServer(("127.0.0.1", 0), _StubLLMHandler)
    port = server.server_address[1]
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{port}/v1"
    finally:
        server.shutdown()
        thread.join(timeout=5)


def test_help_exits_zero_and_prints_usage() -> None:
    """--help prints the usage text and exits 0 without touching any device or network."""
    result = run_smoke_test(["--help"])
    assert result.returncode == 0
    assert "Usage: scripts/smoke_test.sh" in result.stdout
    assert "--wireless-serial" in result.stdout


def test_unknown_flag_exits_two_with_usage() -> None:
    """An unrecognized flag exits 2 and still shows the usage text."""
    result = run_smoke_test(["--not-a-real-flag"])
    assert result.returncode == 2
    combined = result.stdout + result.stderr
    assert "Unknown option: --not-a-real-flag" in combined
    assert "Usage: scripts/smoke_test.sh" in combined


def test_skip_everything_still_runs_prerequisites_and_exits_zero() -> None:
    """Skipping every check still runs the prerequisites section and prints a clean summary."""
    result = run_smoke_test(["--skip-llm", "--skip-wired", "--skip-wireless", "--skip-agent-run"])
    assert result.returncode == 0
    assert "== Prerequisites ==" in result.stdout
    assert "[PASS] adb found" in result.stdout
    assert "[PASS] mobilerun SDK imports cleanly" in result.stdout
    assert "skipped (--skip-llm)" in result.stdout
    assert "skipped (--skip-agent-run)" in result.stdout
    assert failed_count(result.stdout) == 0


def test_llm_section_lists_models_and_auto_selects_when_model_not_given(stub_llm_server: str) -> None:
    """Against a real stub server, /models is listed and its first model auto-fills --model."""
    result = run_smoke_test(
        ["--llm-url", stub_llm_server, "--skip-wired", "--skip-wireless", "--skip-agent-run"]
    )
    assert result.returncode == 0
    assert "[PASS] GET" in result.stdout
    assert "models: stub-model-a, stub-model-b" in result.stdout
    assert 'auto-selected "stub-model-a"' in result.stdout
    assert "chat completion succeeded" in result.stdout
    assert 'reply: "pong"' in result.stdout


def test_llm_section_respects_explicit_model_override(stub_llm_server: str) -> None:
    """An explicit --model is used as-is and skips the auto-select message."""
    result = run_smoke_test(
        ["--llm-url", stub_llm_server, "--model", "stub-model-b", "--skip-wired", "--skip-wireless", "--skip-agent-run"]
    )
    assert result.returncode == 0
    assert "auto-selected" not in result.stdout
    assert "model=stub-model-b" in result.stdout


def test_llm_section_reports_failure_when_server_unreachable() -> None:
    """A closed --llm-url port is reported as a real FAIL, and the script exits 1 overall."""
    closed_port = processes.find_free_tcp_port()  # reserved-then-released; nothing is listening on it
    result = run_smoke_test(
        ["--llm-url", f"http://127.0.0.1:{closed_port}/v1", "--skip-wired", "--skip-wireless", "--skip-agent-run"],
        timeout=30,
    )
    assert result.returncode == 1
    assert "[FAIL] GET" in result.stdout
    assert failed_count(result.stdout) >= 1


def test_list_models_prints_ids_and_exits_zero_without_running_any_checks(stub_llm_server: str) -> None:
    """--list-models prints every model ID from a real server and exits before touching devices."""
    result = run_smoke_test(["--llm-url", stub_llm_server, "--list-models"])
    assert result.returncode == 0
    assert "stub-model-a" in result.stdout
    assert "stub-model-b" in result.stdout
    assert '--model "stub-model-a"' in result.stdout
    assert "== Prerequisites ==" not in result.stdout


def test_list_models_fails_when_server_unreachable() -> None:
    """--list-models against an unreachable server exits 1 with a clear stderr message."""
    closed_port = processes.find_free_tcp_port()
    result = run_smoke_test(
        ["--llm-url", f"http://127.0.0.1:{closed_port}/v1", "--list-models"], timeout=30
    )
    assert result.returncode == 1
    assert "Could not reach" in result.stderr


def test_wireless_serial_alone_autoskips_wired_without_a_skip_flag() -> None:
    """Passing only --wireless-serial skips the wired section on its own, without --skip-wired."""
    result = run_smoke_test(
        ["--skip-llm", "--skip-agent-run", "--wireless-serial", "203.0.113.5:5555"], timeout=30
    )
    assert "skipped (a --wireless-serial was given without --usb-serial" in result.stdout
    assert "skipped (--skip-wired)" not in result.stdout


def test_usb_serial_alone_autoskips_wireless_without_a_skip_flag() -> None:
    """Passing only --usb-serial skips the wireless section on its own, without --skip-wireless."""
    result = run_smoke_test(
        ["--skip-llm", "--skip-agent-run", "--usb-serial", "FAKE1234"], timeout=30
    )
    assert "skipped (a --usb-serial was given without --wireless-serial" in result.stdout
    assert "skipped (--skip-wireless)" not in result.stdout


def test_unreachable_usb_serial_reports_failure() -> None:
    """A --usb-serial that isn't actually attached is reported as a FAIL, not silently skipped."""
    result = run_smoke_test(
        ["--skip-llm", "--skip-wireless", "--skip-agent-run", "--usb-serial", "NONEXISTENT000"], timeout=30
    )
    assert result.returncode == 1
    assert "NONEXISTENT000" in result.stdout
    assert failed_count(result.stdout) >= 1


def test_no_mobilerun_cli_subcommands_anywhere_in_output() -> None:
    """The whole script is SDK-only: no `mobilerun ping`/`doctor`/`connect` CLI subcommand ever runs."""
    result = run_smoke_test(
        ["--skip-llm", "--skip-wired", "--skip-wireless", "--skip-agent-run"], timeout=30
    )
    combined = result.stdout + result.stderr
    assert "mobilerun ping" not in combined
    assert "mobilerun doctor" not in combined
    assert "mobilerun connect" not in combined


@pytest.mark.skipif(WIRED_SERIAL is None, reason="No wired ADB device attached")
def test_real_wired_device_health_check_passes() -> None:
    """Against a real wired device, the SDK-only health check reports PASS/WARN-only and exit 0."""
    result = run_smoke_test(
        ["--skip-llm", "--skip-wireless", "--skip-agent-run", "--usb-serial", WIRED_SERIAL], timeout=60
    )
    assert result.returncode == 0
    assert f"adb_connect: {WIRED_SERIAL} is online" in result.stdout
    assert "uv run mobilerun" not in result.stdout


@pytest.mark.skipif(WIRELESS_SERIAL is None, reason="No wireless ADB device attached")
def test_real_wireless_device_health_check_passes() -> None:
    """Against a real wireless device, the SDK-only health check reports PASS/WARN-only and exit 0."""
    result = run_smoke_test(
        ["--skip-llm", "--skip-wired", "--skip-agent-run", "--wireless-serial", WIRELESS_SERIAL], timeout=60
    )
    assert result.returncode == 0
    assert f"adb_connect: {WIRELESS_SERIAL} is online" in result.stdout


@pytest.mark.skipif(ANY_SERIAL is None, reason="No ADB device attached")
def test_device_health_check_script_passes_directly() -> None:
    """device_health_check.py, invoked directly (not through smoke_test.sh), passes against a real device."""
    result = subprocess.run(
        [sys.executable, str(HEALTH_CHECK), "--serial", ANY_SERIAL],
        capture_output=True, text=True, timeout=30, check=False,
    )
    assert result.returncode == 0
    assert "RESULT PASS" in result.stdout or "RESULT WARN" in result.stdout
    assert "CHECK adb_connect PASS" in result.stdout


def test_device_health_check_script_fails_for_a_nonexistent_serial() -> None:
    """device_health_check.py reports RESULT FAIL and exits 1 for a serial that isn't attached."""
    result = subprocess.run(
        [sys.executable, str(HEALTH_CHECK), "--serial", "NONEXISTENT000", "--timeout", "10"],
        capture_output=True, text=True, timeout=30, check=False,
    )
    assert result.returncode == 1
    assert "RESULT FAIL" in result.stdout
    assert "CHECK adb_connect FAIL" in result.stdout
