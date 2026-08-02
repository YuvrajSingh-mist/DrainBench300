"""Pytest coverage for the main CLI end-to-end: real device sampling, real proxy, a stand-in MobileAgent.

mobilerun's own agentic loop (real function-calling against a real LLM) is out of scope for this
harness's tests - that's mobilerun's own test suite's job. These tests stub only the MobileAgent SDK
boundary itself (`cli.MobileAgent`), exactly mirroring how the pre-SDK version of this test stubbed out
the external `mobilerun` binary with a stand-in script - everything DailyBench owns (adb sampling, the
real proxy subprocess, scrcpy wiring, file writes) stays real.
"""

from __future__ import annotations

import json
import sys
import threading
import time
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest
from conftest import first_adb_device

from DailyBench import cli, processes

DEVICE_SERIAL = first_adb_device()


def _newest_run_dir(label: str) -> Path:
    """Return the most recently created run folder for a label.

    Every test invocation writes a fresh runs/<date-time>/<label>/ folder and the
    old ones accumulate, so ``next(glob)`` is not deterministic - it can pick a
    stale folder from a previous run. Use mtime to select the folder this test just
    wrote instead.
    """
    return max(Path("runs").glob(f"*/{label}"), key=lambda p: p.stat().st_mtime)


class _StubUpstreamHandler(BaseHTTPRequestHandler):
    """A tiny real HTTP server standing in for llama.cpp's /v1/chat/completions endpoint."""

    def do_POST(self) -> None:  # noqa: N802
        """Respond to any POST with a canned non-streaming chat completion."""
        length = int(self.headers.get("Content-Length", "0"))
        self.rfile.read(length)
        body = json.dumps(
            {
                "id": "chatcmpl-real",
                "model": "stub-model",
                "choices": [{"finish_reason": "stop"}],
                "usage": {"prompt_tokens": 10, "completion_tokens": 3, "total_tokens": 13},
            }
        ).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format: str, *args: object) -> None:  # noqa: A002
        """Silence default request logging so test output stays clean."""
        return


class _FakeResult:
    """Stand-in for mobilerun's ResultEvent."""

    def __init__(self, success: bool, reason: str, steps: int) -> None:
        self.success = success
        self.reason = reason
        self.steps = steps


def _build_fake_agent_class(created_configs: list) -> type:
    """Build a fake MobileAgent that hits the real LLM proxy once, then reports success."""

    class _FakeMobileAgent:
        def __init__(self, goal: str, config, llms, prompts=None, custom_tools=None, timeout=None) -> None:
            self.goal = goal
            self.llms = llms
            self.prompts = prompts
            self.custom_tools = custom_tools
            created_configs.append(config)

        async def run(self) -> _FakeResult:
            """Exercise the real proxy with one real HTTP call, then return a canned result."""
            body = json.dumps({"model": "m", "messages": [], "stream": False}).encode()
            req = urllib.request.Request(
                self.llms.api_base + "/chat/completions", data=body, headers={"Content-Type": "application/json"}
            )
            urllib.request.urlopen(req, timeout=5).read()
            time.sleep(1.2)
            return _FakeResult(success=True, reason="Done successfully.", steps=3)

    return _FakeMobileAgent


@pytest.mark.skipif(DEVICE_SERIAL is None, reason="No ADB device attached (wired or wireless)")
def test_cli_main_writes_run_artifacts(monkeypatch, tmp_path: Path) -> None:
    """A real CLI run: real device sampling, a real proxy subprocess, and a stand-in MobileAgent."""
    upstream = ThreadingHTTPServer(("127.0.0.1", 0), _StubUpstreamHandler)
    upstream_port = upstream.server_address[1]
    upstream_thread = threading.Thread(target=upstream.serve_forever, daemon=True)
    upstream_thread.start()

    created_configs: list = []
    monkeypatch.setattr(cli, "MobileAgent", _build_fake_agent_class(created_configs))

    try:
        proxy_port = processes.find_free_tcp_port()
        monkeypatch.setattr(
            sys,
            "argv",
            [
                "DailyBench_runner.py",
                "--serial", DEVICE_SERIAL,
                "--label", "cli smoke",
                "--sample-interval", "0.5",
                "--llm-upstream-base", f"http://127.0.0.1:{upstream_port}/v1",
                "--llm-proxy-port", str(proxy_port),
                "--goal", "Check how many unread emails are in the inbox",
                "--model", "stub-model",
            ],
        )
        assert cli.main() == 0
    finally:
        upstream.shutdown()
        upstream_thread.join(timeout=5)

    run_dir = _newest_run_dir("cli-smoke")
    meta = json.loads((run_dir / "meta.json").read_text())
    summary = json.loads((run_dir / "run_metrics.json").read_text())
    llm_metrics = json.loads((run_dir / "llm_metrics.json").read_text())

    # The proxy may fall back to an OS-assigned port if the preferred one was taken
    # (a legitimate TOCTOU race); meta records whichever port it actually bound, so
    # just require a valid port. The llm_metrics assertion below proves it worked.
    assert isinstance(meta["llm_proxy_port"], int) and meta["llm_proxy_port"] > 0
    assert meta["goal"] == "Check how many unread emails are in the inbox"
    assert meta["temperature"] == 0.0
    assert meta["top_p"] == 0.95
    assert meta["seed"] == 42
    assert (run_dir / "output.txt").read_text() == "Done successfully."
    output_json = json.loads((run_dir / "output.json").read_text())
    assert output_json == {"success": True, "reason": "Done successfully.", "steps": 3}
    assert summary["elapsed_seconds"] > 1.0
    assert summary["command_exit_code"] == 0
    assert llm_metrics[0]["usage"]["total_tokens"] == 13
    # run_metrics keeps battery delta only; raw start/end snapshots are in preflight/postflight
    assert -100 <= summary["battery_level_delta_pct"] <= 100
    assert (run_dir / "agent.log.txt").exists()
    assert created_configs[0].device.serial == DEVICE_SERIAL
    assert created_configs[0].logging.trajectory_path == str(run_dir.resolve() / "trajectories")


@pytest.mark.skipif(DEVICE_SERIAL is None, reason="No ADB device attached (wired or wireless)")
def test_cli_main_records_failure_when_agent_raises(monkeypatch, tmp_path: Path) -> None:
    """When MobileAgent.run() raises, main() still writes a complete run folder with success=False."""

    class _RaisingMobileAgent:
        def __init__(self, goal: str, config, llms, prompts=None, custom_tools=None, timeout=None) -> None:
            pass

        async def run(self):
            raise RuntimeError("device disconnected mid-task")

    monkeypatch.setattr(cli, "MobileAgent", _RaisingMobileAgent)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "DailyBench_runner.py",
            "--serial", DEVICE_SERIAL,
            "--label", "cli failure",
            "--sample-interval", "0.5",
            "--goal", "irrelevant",
            "--model", "stub-model",
        ],
    )
    assert cli.main() == 1

    run_dir = _newest_run_dir("cli-failure")
    output_json = json.loads((run_dir / "output.json").read_text())
    assert output_json["success"] is False
    assert "device disconnected mid-task" in output_json["reason"]
    assert output_json["steps"] == 0


def test_run_agent_builds_llm_with_deterministic_sampling_and_thinking_off(tmp_path: Path, monkeypatch) -> None:
    """The real OpenAILike client run_agent() builds always gets temperature/top_p/seed plus the
    Qwen "thinking" chat-template switch turned off - confirmed against real Qwen3-family
    models to actually zero out reasoning tokens and make output reproducible
    (see docs/advanced-features.md's OpenRouter section)."""
    captured_llms: list = []

    class _CapturingFakeAgent:
        def __init__(self, goal: str, config, llms, prompts=None, custom_tools=None, timeout=None) -> None:
            captured_llms.append(llms)

        async def run(self) -> _FakeResult:
            return _FakeResult(success=True, reason="ok", steps=1)

    monkeypatch.setattr(cli, "MobileAgent", _CapturingFakeAgent)
    parser = cli.build_parser()
    args = parser.parse_args(
        ["--serial", "device-1", "--label", "x", "--goal", "g", "--model", "m", "--top-p", "0.9", "--seed", "7"]
    )
    import asyncio

    run_dir = tmp_path / "run-1"
    run_dir.mkdir()
    asyncio.run(cli.run_agent(args, run_dir, "http://127.0.0.1:1/v1"))

    llm = captured_llms[0]
    assert llm.temperature == 0.0
    assert llm.additional_kwargs["top_p"] == 0.9
    assert llm.additional_kwargs["seed"] == 7
    assert llm.additional_kwargs["extra_body"] == {"chat_template_kwargs": {"enable_thinking": False}}


def test_build_mobile_config_maps_cli_flags(tmp_path: Path) -> None:
    """build_mobile_config translates CLI flags into the right nested MobileConfig fields."""
    parser = cli.build_parser()
    args = parser.parse_args(
        [
            "--serial", "device-1",
            "--label", "x",
            "--goal", "g",
            "--model", "m",
            "--steps", "12",
            "--reasoning",
            "--vision",
            "--no-debug",
            "--tracing",
            "--save-trajectory", "action",
        ]
    )
    run_dir = tmp_path / "run-1"
    config = cli.build_mobile_config(args, run_dir)
    assert config.device.serial == "device-1"
    assert config.agent.max_steps == 12
    assert config.agent.reasoning is True
    assert config.agent.fast_agent.vision is True
    assert config.logging.debug is False
    assert config.logging.save_trajectory == "action"
    assert config.logging.trajectory_path == str(run_dir / "trajectories")
    assert config.tracing.enabled is True


def test_build_mobile_config_defaults_are_fast_agent_no_vision_no_tracing(tmp_path: Path) -> None:
    """Without any opt-in flags, the harness runs the fast-agent loop with vision/tracing off and debug on."""
    parser = cli.build_parser()
    args = parser.parse_args(["--serial", "device-1", "--label", "x", "--goal", "g", "--model", "m"])
    config = cli.build_mobile_config(args, tmp_path / "run-1")
    assert config.agent.reasoning is False
    assert config.agent.fast_agent.vision is False
    assert config.logging.debug is True
    assert config.logging.save_trajectory == "none"
    assert config.tracing.enabled is False
