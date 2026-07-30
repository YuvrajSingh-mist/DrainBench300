"""Real integration tests against OpenRouter — no stubs, real API keys from .env.

These test the EXACT code path that a benchmark run uses: dotenv → proxy subprocess
→ OpenRouter HTTP → JSONL log → parsed metrics. If these pass, the harness works.
"""

from __future__ import annotations

import json
import os
import urllib.request
from pathlib import Path

import pytest
from dotenv import load_dotenv

from DailyBench import processes

load_dotenv()

OPENROUTER_KEY = os.environ.get("OPENROUTER_API_KEY")
OPENROUTER_UPSTREAM = "https://openrouter.ai/api"
TEST_MODEL = "qwen/qwen3.6-plus"

pytestmark = pytest.mark.skipif(
    not OPENROUTER_KEY,
    reason="OPENROUTER_API_KEY not set in .env — set it to run real integration tests",
)


def _wait_until_port_open(port: int, timeout: float = 10.0) -> None:
    import socket
    import time

    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
            probe.settimeout(0.2)
            if probe.connect_ex(("127.0.0.1", port)) == 0:
                return
        time.sleep(0.05)
    raise TimeoutError(f"Proxy not listening on port {port}")


# ---------------------------------------------------------------------------
# Real proxy → real OpenRouter
# ---------------------------------------------------------------------------


def test_proxy_forwards_to_openrouter_and_logs_token_counts(tmp_path: Path) -> None:
    """Starts the real proxy pointed at https://openrouter.ai/api, sends a real
    chat completion, and verifies: (a) the response is valid JSON with token counts,
    (b) the proxy logged it to JSONL with usage data.

    This is the test that catches: the urljoin bug (would 404), the empty-log bug
    (would log nothing), and format mismatches (would produce garbage)."""
    assert OPENROUTER_KEY, "OPENROUTER_API_KEY required"

    background = None
    try:
        proxy_port = processes.find_free_tcp_port()
        background, port, log_jsonl = processes.start_llm_proxy(
            tmp_path, OPENROUTER_UPSTREAM, proxy_port
        )
        _wait_until_port_open(port)

        request_body = json.dumps(
            {
                "model": TEST_MODEL,
                "messages": [{"role": "user", "content": "Say hello in exactly one word."}],
                "stream": False,
                "max_tokens": 10,
            }
        ).encode()
        req = urllib.request.Request(
            f"http://127.0.0.1:{port}/v1/chat/completions",
            data=request_body,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {OPENROUTER_KEY}",
            },
        )

        with urllib.request.urlopen(req, timeout=30) as resp:
            raw = resp.read()
            payload = json.loads(raw)

        # Must be valid JSON, not HTML
        assert "choices" in payload, f"Response is not a chat completion: {raw[:500]}"
        assert len(payload["choices"]) >= 1
        assert payload["choices"][0]["message"]["content"]

        # Must have token counts
        usage = payload.get("usage") or {}
        assert usage.get("total_tokens", 0) > 0, f"No token counts in response: {json.dumps(usage)}"

        # Proxy must have logged it
        logged = log_jsonl.read_text().strip().splitlines()
        assert len(logged) >= 1, "Proxy logged nothing — logging bug"
        entry = json.loads(logged[0])
        assert entry["kind"] == "chat.completion"
        assert entry["usage"]["total_tokens"] > 0, (
            f"Proxy failed to parse token counts. Log entry: {json.dumps(entry)}"
        )
        assert entry["elapsed_proxy_ms"] > 0
    finally:
        if background is not None:
            processes.stop_process(background)


def test_proxy_handles_openrouter_streaming_response(tmp_path: Path) -> None:
    """OpenRouter may return SSE even for non-streaming requests. The proxy must
    parse SSE correctly and extract usage/token counts from it."""
    assert OPENROUTER_KEY, "OPENROUTER_API_KEY required"

    background = None
    try:
        proxy_port = processes.find_free_tcp_port()
        background, port, log_jsonl = processes.start_llm_proxy(
            tmp_path, OPENROUTER_UPSTREAM, proxy_port
        )
        _wait_until_port_open(port)

        # Request WITH streaming — this is what mobilerun typically does
        request_body = json.dumps(
            {
                "model": TEST_MODEL,
                "messages": [{"role": "user", "content": "Say hello in exactly one word."}],
                "stream": True,
                "max_tokens": 10,
            }
        ).encode()
        req = urllib.request.Request(
            f"http://127.0.0.1:{port}/v1/chat/completions",
            data=request_body,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {OPENROUTER_KEY}",
            },
        )

        with urllib.request.urlopen(req, timeout=30) as resp:
            raw = resp.read()
            text = raw.decode(errors="ignore")

# OpenRouter SSE starts with comment lines (: OPENROUTER PROCESSING)
            # before data chunks — not with "data:" directly
            assert "data:" in text, f"Response is not SSE: {text[:500]}"

        # Proxy must have parsed SSE and logged usage
        logged = log_jsonl.read_text().strip().splitlines()
        assert len(logged) >= 1, "Proxy logged nothing for SSE response"
        entry = json.loads(logged[0])
        assert entry["usage"]["total_tokens"] > 0, (
            f"Proxy failed to extract usage from SSE. Log: {json.dumps(entry)}"
        )
        assert entry["finish_reason"] is not None
    finally:
        if background is not None:
            processes.stop_process(background)
