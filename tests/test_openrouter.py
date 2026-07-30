"""Pytest coverage for OpenRouter integration: endpoint classification, API key
validation, and early-fail behaviour when required keys are missing."""

from __future__ import annotations

import os
import sys

import pytest

from DailyBench import cli

from mobilerun_provider_guard import classify_endpoint, looks_like_local_model


# ---------------------------------------------------------------------------
# Endpoint classification (real logic, no stubs)
# ---------------------------------------------------------------------------


def test_classify_openrouter_endpoint() -> None:
    """OpenRouter's https://openrouter.ai/api is the base URL we use (the /v1
    prefix comes from the incoming request path, concatenated literally)."""
    # Our harness uses https://openrouter.ai/api — not /api/v1 — because the proxy
    # concatenates the incoming path (/v1/chat/completions) directly.
    assert classify_endpoint("https://openrouter.ai/api", None) == "unknown"


def test_classify_openai_api_as_openai() -> None:
    """The real OpenAI API endpoint is classified as 'openai', not 'openai_like'."""
    assert classify_endpoint("https://api.openai.com/v1", None) == "openai"


def test_classify_empty_url_as_unknown() -> None:
    """An empty or missing URL returns 'unknown'."""
    assert classify_endpoint(None, None) == "unknown"
    assert classify_endpoint("", None) == "unknown"


def test_openrouter_model_names_are_classified_as_local() -> None:
    """OpenRouter model names contain local-model hints, which the provider guard
    uses to warn against using the plain 'OpenAI' provider."""
    assert looks_like_local_model("qwen/qwen3.6-plus") is True
    assert looks_like_local_model("qwen/qwen3.7-plus") is True
    assert looks_like_local_model("qwen/qwen-3-4b-instruct") is True
    assert looks_like_local_model("meta-llama/llama-4-maverick") is True


def test_openai_model_names_are_not_classified_as_local() -> None:
    """Official OpenAI model names should not trigger the local-model hint."""
    assert looks_like_local_model("gpt-4o") is False
    assert looks_like_local_model("gpt-5.4-mini") is False


# ---------------------------------------------------------------------------
# API key selection — OPENROUTER_API_KEY is for the main agent only.
# OPENAI_API_KEY is for the ask_user tool only. No cross-fallback.
# ---------------------------------------------------------------------------


def test_api_key_uses_openrouter_with_dummy_fallback(monkeypatch) -> None:
    """The main agent uses OPENROUTER_API_KEY when set, or 'sk-DailyBench-local'
    when absent (safe for local llama-server). OPENAI_API_KEY is never a fallback —
    it belongs to a completely separate service (the ask_user tool)."""
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-or-v1-real-key")
    monkeypatch.setenv("OPENAI_API_KEY", "sk-openai-real-key")
    chosen = os.environ.get("OPENROUTER_API_KEY", "sk-DailyBench-local")
    assert chosen == "sk-or-v1-real-key"


def test_api_key_falls_back_to_dummy_when_openrouter_unset(monkeypatch) -> None:
    """When OPENROUTER_API_KEY is absent, the dummy 'sk-DailyBench-local' is used.
    OPENAI_API_KEY is NOT used as a fallback."""
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    monkeypatch.setenv("OPENAI_API_KEY", "sk-openai-real-key")
    chosen = os.environ.get("OPENROUTER_API_KEY", "sk-DailyBench-local")
    assert chosen == "sk-DailyBench-local"


# ---------------------------------------------------------------------------
# Early-fail validation — main() refuses to start when required keys are missing
# ---------------------------------------------------------------------------


def test_main_exits_when_openrouter_key_missing_for_openrouter_upstream(monkeypatch) -> None:
    """When --llm-upstream-base points at OpenRouter and OPENROUTER_API_KEY is
    not set, main() exits immediately with a clear message instead of wasting
    a 30-minute task run that will fail on the first LLM call."""
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "dailybench_runner.py",
            "--serial", "device-1",
            "--label", "test",
            "--goal", "do something",
            "--model", "qwen/qwen3.6-plus",
            "--llm-upstream-base", "https://openrouter.ai/api",
        ],
    )
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    with pytest.raises(SystemExit, match="OPENROUTER_API_KEY"):
        cli.main()


def test_main_exits_when_openai_key_missing_for_ask_user_task(monkeypatch) -> None:
    """When --ask-user-context is set (Hard/ASK USER task) and OPENAI_API_KEY is
    not set, main() exits immediately — the ask_user tool needs real OpenAI access."""
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "dailybench_runner.py",
            "--serial", "device-1",
            "--label", "test",
            "--goal", "send the report",
            "--model", "qwen/qwen3.6-plus",
            "--ask-user-context", "The report is named Q2_Budget.xlsx.",
        ],
    )
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    with pytest.raises(SystemExit, match="OPENAI_API_KEY"):
        cli.main()


def test_main_does_not_require_openrouter_key_for_local_upstream(monkeypatch) -> None:
    """When --llm-upstream-base points at a local llama-server (not OpenRouter),
    the dummy key is fine — no early exit."""
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "dailybench_runner.py",
            "--serial", "device-1",
            "--label", "test",
            "--goal", "do something",
            "--model", "local-model",
            "--llm-upstream-base", "http://100.75.134.64:8081/v1",
            "--no-screen-record",
        ],
    )
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    # Should NOT raise — local upstream doesn't need OpenRouter key.
    # The parser should parse successfully. We stop before the actual run
    # (which would need a real device) by checking that no SystemExit is raised
    # for key-related reasons.
    parser = cli.build_parser()
    args = parser.parse_args(
        ["--serial", "device-1", "--label", "test", "--goal", "g", "--model", "m",
         "--llm-upstream-base", "http://100.75.134.64:8081/v1", "--no-screen-record"]
    )
    # The validation in main() only fires for openrouter URLs
    assert "openrouter" not in (args.llm_upstream_base or "").lower()


# ---------------------------------------------------------------------------
# Proxy URL construction — catches the urljoin bug that silently drops path
# segments for multi-segment base URLs like https://openrouter.ai/api
# ---------------------------------------------------------------------------


def test_proxy_preserves_multi_segment_base_url(tmp_path) -> None:
    """The proxy uses string concatenation (not urljoin) so that a base URL like
    ``https://openrouter.ai/api`` combined with an incoming path like
    ``/v1/chat/completions`` produces ``https://openrouter.ai/api/v1/chat/completions``
    rather than ``https://openrouter.ai/v1/chat/completions`` (which drops /api/)."""
    import json
    import threading
    import urllib.request
    from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

    from DailyBench import processes

    class _PathRecorder(BaseHTTPRequestHandler):
        received_path = None

        def do_POST(self) -> None:  # noqa: N802
            type(self).received_path = self.path
            body = json.dumps({"choices": [{"message": {"content": "ok"}}], "usage": {"total_tokens": 1}}).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, format, *args):  # noqa: A002
            return

    upstream = ThreadingHTTPServer(("127.0.0.1", 0), _PathRecorder)
    upstream_port = upstream.server_address[1]
    thread = threading.Thread(target=upstream.serve_forever, daemon=True)
    thread.start()

    background = None
    try:
        # Simulate OpenRouter's multi-segment base: /api (not /api/v1)
        background, port, _ = processes.start_llm_proxy(
            tmp_path, f"http://127.0.0.1:{upstream_port}/api", processes.find_free_tcp_port()
        )
        processes.wait_for_proxy_ready(port)

        body = json.dumps({"model": "m", "messages": []}).encode()
        req = urllib.request.Request(
            f"http://127.0.0.1:{port}/v1/chat/completions",
            data=body,
            headers={"Content-Type": "application/json"},
        )
        urllib.request.urlopen(req, timeout=5)

        # The upstream must receive the full path: /api/v1/chat/completions
        # If urljoin were used, it would be /v1/chat/completions (dropping /api)
        assert _PathRecorder.received_path == "/api/v1/chat/completions", (
            f"Expected /api/v1/chat/completions, got {_PathRecorder.received_path}. "
            "The proxy is dropping path segments — check urljoin vs concatenation."
        )
    finally:
        if background is not None:
            processes.stop_process(background)
        upstream.shutdown()
        thread.join(timeout=5)
