"""Pytest coverage for the main CLI using real argument flow."""

from __future__ import annotations

import json
import sys
from pathlib import Path

from drainbench import cli


class FakeSampler:
    """Deterministic sampler stub."""

    def __init__(self, serial: str, sample_interval: float, out_path: Path) -> None:
        self.serial = serial
        self.sample_interval = sample_interval
        self.out_path = out_path
        self.samples = [{"battery": {"level_pct": 90}, "thermal": {"hal_temperatures_c": {}}}]
        self.errors: list[str] = []

    def start(self) -> None:
        self.out_path.write_text("")

    def stop(self) -> None:
        return None


class FakeCommandPopen:
    """Stub for the foreground Mobilerun command."""

    def __init__(self, cmd, stdout=None, stderr=None):
        self.cmd = cmd
        self.returncode = 0
        if stdout is not None:
            stdout.write('INFO mobilerun 🎉 Goal achieved: Done successfully.\n')
            stdout.flush()
        if stderr is not None:
            stderr.write("")
            stderr.flush()

    def wait(self):
        return self.returncode


def test_cli_main_writes_run_artifacts(monkeypatch, tmp_path: Path) -> None:
    samples = iter(
        [
            {"battery": {"level_pct": 90}, "thermal": {"hal_temperatures_c": {}, "thermal_status_code": 1}},
            {"battery": {"level_pct": 89}, "thermal": {"hal_temperatures_c": {}, "thermal_status_code": 2}},
        ]
    )
    monkeypatch.setattr(cli, "capture_sample", lambda serial: next(samples))
    monkeypatch.setattr(cli, "start_llm_proxy", lambda run_dir, upstream, port: (object(), 8099, run_dir / "llm_proxy_metrics.jsonl"))
    monkeypatch.setattr(cli, "stop_process", lambda *args, **kwargs: 0)
    monkeypatch.setattr(cli, "start_scrcpy", lambda *args, **kwargs: object())
    monkeypatch.setattr(cli, "Sampler", FakeSampler)
    monkeypatch.setattr(cli.subprocess, "Popen", FakeCommandPopen)
    monkeypatch.setattr(cli, "read_jsonl", lambda path, offset: [{"kind": "chat.completion", "usage": {"prompt_tokens": 10, "completion_tokens": 3, "total_tokens": 13}, "timings": {"prompt_ms": 100.0, "predicted_ms": 50.0}}])
    monkeypatch.setattr(cli, "wait_briefly", lambda seconds: None)
    ticks = iter([100.0, 112.5])
    monkeypatch.setattr(cli.time, "monotonic", lambda: next(ticks))
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "drainbench_runner.py",
            "--serial", "device-1",
            "--label", "cli smoke",
            "--out-dir", str(tmp_path),
            "--llm-upstream-base", "http://mini2:8082/v1",
            "--llm-proxy-port", "8090",
            "--",
            "mobilerun", "run",
            "--api_base", "http://127.0.0.1:8090/v1",
            "--temperature", "0",
            "Check current battery percentage.",
        ],
    )
    assert cli.main() == 0
    run_dir = next(tmp_path.iterdir())
    meta = json.loads((run_dir / "meta.json").read_text())
    summary = json.loads((run_dir / "summary.json").read_text())
    assert meta["llm_proxy_port"] == 8099
    assert "http://127.0.0.1:8099/v1" in meta["command"]
    assert summary["elapsed_seconds"] == 12.5
    assert (run_dir / "output.txt").read_text() == "Done successfully."
