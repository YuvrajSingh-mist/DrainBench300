"""Pytest coverage for process helpers, using real subprocesses instead of Popen stand-ins."""

from __future__ import annotations

import json
import shutil
import socket
import subprocess
import sys
import threading
import time
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest

from DailyBench import processes


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
                "usage": {"prompt_tokens": 5, "completion_tokens": 2, "total_tokens": 7},
            }
        ).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format: str, *args: object) -> None:  # noqa: A002
        """Silence default request logging so test output stays clean."""
        return


def _wait_until_port_open(port: int, timeout: float = 5.0) -> None:
    """Poll until something is listening on 127.0.0.1:port, or raise once the timeout elapses."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
            probe.settimeout(0.2)
            if probe.connect_ex(("127.0.0.1", port)) == 0:
                return
        time.sleep(0.05)
    raise TimeoutError(f"Nothing listening on port {port} after {timeout}s")


def test_start_llm_proxy_forwards_and_logs_a_real_completion(tmp_path: Path) -> None:
    """The real openai_proxy_logger.py subprocess forwards a real HTTP request and logs real usage."""
    upstream = ThreadingHTTPServer(("127.0.0.1", 0), _StubUpstreamHandler)
    upstream_port = upstream.server_address[1]
    upstream_thread = threading.Thread(target=upstream.serve_forever, daemon=True)
    upstream_thread.start()

    background = None
    try:
        preferred_port = processes.find_free_tcp_port()
        background, port, log_jsonl = processes.start_llm_proxy(
            tmp_path, f"http://127.0.0.1:{upstream_port}/v1", preferred_port
        )
        _wait_until_port_open(port)

        request_body = json.dumps({"model": "m", "messages": [], "stream": False}).encode()
        req = urllib.request.Request(
            f"http://127.0.0.1:{port}/v1/chat/completions",
            data=request_body,
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=5) as resp:
            response_payload = json.loads(resp.read())
        assert response_payload["usage"]["total_tokens"] == 7

        logged_lines = log_jsonl.read_text().strip().splitlines()
        assert len(logged_lines) == 1
        logged_entry = json.loads(logged_lines[0])
        assert logged_entry["usage"]["total_tokens"] == 7
    finally:
        if background is not None:
            processes.stop_process(background)
        upstream.shutdown()
        upstream_thread.join(timeout=5)


def test_start_llm_proxy_logs_even_when_upstream_returns_garbage(tmp_path: Path) -> None:
    """When the upstream returns HTML or empty content (e.g. a 404 page, auth error),
    the proxy still writes a log entry with elapsed time and a response_body_preview
    so the bug is diagnosable instead of silently swallowed."""
    import http.server

    class _GarbageHandler(http.server.BaseHTTPRequestHandler):
        def do_POST(self) -> None:  # noqa: N802
            body = b"<html><body>502 Bad Gateway</body></html>"
            self.send_response(502)
            self.send_header("Content-Type", "text/html")
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, format, *args):  # noqa: A002
            return

    upstream = ThreadingHTTPServer(("127.0.0.1", 0), _GarbageHandler)
    upstream_port = upstream.server_address[1]
    upstream_thread = threading.Thread(target=upstream.serve_forever, daemon=True)
    upstream_thread.start()

    background = None
    try:
        preferred_port = processes.find_free_tcp_port()
        background, port, log_jsonl = processes.start_llm_proxy(
            tmp_path, f"http://127.0.0.1:{upstream_port}/v1", preferred_port
        )
        _wait_until_port_open(port)

        request_body = json.dumps({"model": "m", "messages": []}).encode()
        req = urllib.request.Request(
            f"http://127.0.0.1:{port}/v1/chat/completions",
            data=request_body,
            headers={"Content-Type": "application/json"},
        )
        try:
            urllib.request.urlopen(req, timeout=5)
        except urllib.error.HTTPError:
            pass  # 502 is expected

        # The proxy must still log — even with garbage response
        logged_lines = log_jsonl.read_text().strip().splitlines()
        assert len(logged_lines) == 1, f"Expected 1 log entry, got {len(logged_lines)}"
        entry = json.loads(logged_lines[0])
        assert entry["kind"] == "chat.completion"
        assert entry["elapsed_proxy_ms"] > 0
        assert "response_body_preview" in entry
        assert "502 Bad Gateway" in entry["response_body_preview"]
    finally:
        if background is not None:
            processes.stop_process(background)
        upstream.shutdown()
        upstream_thread.join(timeout=5)


def test_start_llm_proxy_falls_back_to_free_port_when_preferred_port_is_taken(tmp_path: Path) -> None:
    """With the preferred port genuinely occupied by another socket, the real proxy binds a different, free port."""
    occupied = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    occupied.bind(("127.0.0.1", 0))
    occupied.listen(1)
    occupied_port = occupied.getsockname()[1]

    background = None
    try:
        background, port, _log_jsonl = processes.start_llm_proxy(tmp_path, "http://127.0.0.1:1/v1", occupied_port)
        assert port != occupied_port
        _wait_until_port_open(port)
    finally:
        if background is not None:
            processes.stop_process(background)
        occupied.close()


def test_stop_process_terminates_a_real_long_running_subprocess() -> None:
    """stop_process sends a real termination signal to a real subprocess and returns promptly, not after a long wait."""
    process = subprocess.Popen(
        [sys.executable, "-c", "import time; time.sleep(30)"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    background = processes.BackgroundProcess(process=process, stdout_path=Path("a"), stderr_path=Path("b"))
    started = time.monotonic()
    returncode = processes.stop_process(background)
    elapsed = time.monotonic() - started
    assert returncode is not None
    assert elapsed < 5.0


@pytest.mark.skipif(shutil.which("scrcpy") is None, reason="scrcpy binary not installed")
def test_start_scrcpy_invokes_the_real_binary(tmp_path: Path) -> None:
    """start_scrcpy launches the actual scrcpy binary; against a nonexistent serial it fails fast with a real error."""
    background = processes.start_scrcpy("no-such-device:5555", tmp_path, "8M", None)
    try:
        background.process.wait(timeout=10)
        assert background.process.returncode != 0
        assert background.stderr_path.read_text().strip() != ""
    finally:
        processes.stop_process(background)
