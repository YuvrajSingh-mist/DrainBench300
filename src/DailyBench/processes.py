"""Background process helpers for recording and proxy services."""

from __future__ import annotations

import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path


@dataclass
class BackgroundProcess:
    """A long-lived child process with captured stdout/stderr paths."""

    process: subprocess.Popen[object]
    stdout_path: Path
    stderr_path: Path


def find_free_tcp_port() -> int:
    """Reserve and return one free localhost TCP port."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        sock.listen(1)
        return int(sock.getsockname()[1])


def start_scrcpy(serial: str, run_dir: Path, bit_rate: str, size: str | None) -> BackgroundProcess:
    """Start scrcpy screen recording for one run."""
    stdout_path = run_dir / "screenrecord.stdout.txt"
    stderr_path = run_dir / "screenrecord.stderr.txt"
    video_path = run_dir / "screen.mp4"
    cmd = [
        "scrcpy", "-s", serial, "--record", str(video_path), "--record-format", "mp4",
        "--no-window", "--no-audio", "--stay-awake", "--show-touches",
        "--video-bit-rate", bit_rate, "--max-fps", "30",
    ]
    if size:
        cmd.extend(["--max-size", size])
    process = subprocess.Popen(cmd, stdout=stdout_path.open("w"), stderr=stderr_path.open("w"))
    return BackgroundProcess(process=process, stdout_path=stdout_path, stderr_path=stderr_path)


def start_llm_proxy(
    run_dir: Path,
    upstream_base: str,
    preferred_port: int,
    *,
    retries: int = 3,
    retry_delays: tuple[float, ...] = (5.0, 10.0, 15.0),
    per_attempt_timeout: float = 30.0,
) -> tuple[BackgroundProcess, int, Path]:
    """Start the local OpenAI-compatible proxy/logger for one run, retrying startup.

    The proxy binds its own port (honoring ``preferred_port`` when it's free, else
    letting the OS pick one) and writes the actual bound port to a sidecar file.
    Startup is retried up to ``retries`` times with ``retry_delays`` between attempts so
    a slow cold start under system load can't silently kill a task. If it still hasn't
    become ready, a :class:`ProxyStartupError` is raised - the caller should abort the
    run rather than proceed without an LLM endpoint.
    """
    stdout_path = run_dir / "llm_proxy.stdout.txt"
    stderr_path = run_dir / "llm_proxy.stderr.txt"
    log_jsonl = run_dir / "llm_proxy_metrics.jsonl"
    port_file = run_dir / "llm_proxy.port"
    repo_root = Path(__file__).resolve().parents[2]
    cmd = [
        sys.executable,
        str(repo_root / "scripts" / "openai_proxy_logger.py"),
        "--listen-host", "127.0.0.1",
        "--listen-port", str(preferred_port),
        "--upstream-base", upstream_base,
        "--log-jsonl", str(log_jsonl),
        "--port-file", str(port_file),
    ]
    last_error: Exception | None = None
    for attempt in range(1, retries + 1):
        port_file.unlink(missing_ok=True)
        process = subprocess.Popen(cmd, stdout=stdout_path.open("w"), stderr=stderr_path.open("w"))
        try:
            port = _read_proxy_port(port_file, process, timeout=per_attempt_timeout)
            return BackgroundProcess(process=process, stdout_path=stdout_path, stderr_path=stderr_path), port, log_jsonl
        except (TimeoutError, RuntimeError) as exc:
            last_error = exc
            if process.poll() is None:
                process.kill()
            process.wait(timeout=5)
            if attempt < retries:
                delay = retry_delays[attempt - 1] if attempt - 1 < len(retry_delays) else retry_delays[-1]
                print(f"LLM proxy attempt {attempt}/{retries} failed ({exc}); retrying in {delay}s", file=sys.stderr)
                time.sleep(delay)
    raise ProxyStartupError(
        f"LLM proxy failed to start after {retries} attempts (last error: {last_error}). "
        f"See {stderr_path}. The benchmark will not run - fix the proxy/upstream environment and retry."
    ) from last_error


class ProxyStartupError(RuntimeError):
    """Raised when the LLM proxy cannot be started after several retries."""


def _read_proxy_port(port_file: Path, process: subprocess.Popen[object], timeout: float = 60.0) -> int:
    """Wait for the proxy's --port-file and return the port it actually bound.

    The proxy writes this right after startup, so it is authoritative even when the
    preferred port was taken and the OS assigned a different one. Raises if the
    process dies before writing it.
    """
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if process.poll() is not None:
            stderr_path = port_file.with_suffix(".stderr.txt")
            raise RuntimeError(
                f"llm proxy exited early (code {process.returncode}) before writing its port; see {stderr_path}"
            )
        if port_file.exists():
            return int(port_file.read_text().strip())
        time.sleep(0.05)
    raise TimeoutError(f"llm proxy did not write {port_file} within {timeout}s")


def wait_for_proxy_ready(port: int, timeout: float = 30.0) -> None:
    """Poll the local proxy's /healthz endpoint until it responds, or raise once the timeout elapses.

    A fixed sleep isn't reliable startup-readiness: under real system load (disk/CPU
    contention), even a trivial stdlib subprocess can take well over a couple of
    seconds just to import and bind, and a race here silently turns into every LLM
    call in the run failing with a connection error.
    """
    deadline = time.monotonic() + timeout
    last_error: Exception | None = None
    while time.monotonic() < deadline:
        try:
            with urllib.request.urlopen(f"http://127.0.0.1:{port}/healthz", timeout=1.0) as response:
                if response.status == 200:
                    return
        except (urllib.error.URLError, OSError) as exc:
            last_error = exc
        time.sleep(0.1)
    raise TimeoutError(f"LLM proxy on port {port} did not become ready within {timeout}s ({last_error})")


def stop_process(proc: BackgroundProcess, *, sigint: bool = False) -> int | None:
    """Stop a background process and return its exit code."""
    if proc.process.poll() is None:
        if sigint:
            proc.process.send_signal(subprocess.signal.SIGINT)
        else:
            proc.process.terminate()
        try:
            proc.process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            proc.process.kill()
            proc.process.wait(timeout=5)
    return proc.process.returncode
