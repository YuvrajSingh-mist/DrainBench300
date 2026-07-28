"""Pytest coverage for process helpers."""

from __future__ import annotations

from pathlib import Path

from drainbench import processes


class DummyPopen:
    """Small stand-in for subprocess.Popen."""

    def __init__(self, cmd, stdout=None, stderr=None):
        self.cmd = cmd
        self.stdout = stdout
        self.stderr = stderr
        self.returncode = None

    def poll(self):
        return self.returncode

    def wait(self, timeout=None):
        self.returncode = 0
        return 0

    def terminate(self):
        self.returncode = 0

    def kill(self):
        self.returncode = -9

    def send_signal(self, sig):
        self.returncode = 0


def test_start_llm_proxy_uses_fallback_port(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(processes.subprocess, "Popen", DummyPopen)
    monkeypatch.setattr(processes, "find_free_tcp_port", lambda: 8123)
    class OccupiedSocket:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def bind(self, addr):
            raise OSError("occupied")

        def listen(self, backlog):
            return None

    monkeypatch.setattr(processes.socket, "socket", lambda *args, **kwargs: OccupiedSocket())
    proc, port, log_jsonl = processes.start_llm_proxy(tmp_path, "http://example/v1", 8090)
    assert port == 8123
    assert proc.process.cmd[-4:] == ["--upstream-base", "http://example/v1", "--log-jsonl", str(log_jsonl)]


def test_stop_process_terminates_running_process() -> None:
    proc = processes.BackgroundProcess(process=DummyPopen(["echo"]), stdout_path=Path("a"), stderr_path=Path("b"))
    assert processes.stop_process(proc) == 0
