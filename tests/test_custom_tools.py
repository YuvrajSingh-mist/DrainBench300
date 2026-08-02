"""Pytest coverage for the custom mobilerun tools: real-device date/time/location, and ask_user
against a real local HTTP server standing in for OpenAI's chat completions endpoint.
"""

from __future__ import annotations

import asyncio
import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest
from conftest import first_adb_device

from DailyBench.custom_tools import CUSTOM_TOOLS, build_ask_user_tool

DEVICE_SERIAL = first_adb_device()


class _FakeSharedState:
    def __init__(self, instruction: str) -> None:
        self.instruction = instruction


class _FakeDriver:
    def __init__(self, date_value: str) -> None:
        self._date_value = date_value

    async def get_date(self) -> str:
        return self._date_value


class _FakeCtx:
    def __init__(self, driver: _FakeDriver, instruction: str) -> None:
        self.driver = driver
        self.shared_state = _FakeSharedState(instruction)


class _StubOpenAIHandler(BaseHTTPRequestHandler):
    """A real local HTTP server standing in for OpenAI's /chat/completions endpoint."""

    received_requests: list[dict] = []

    def do_POST(self) -> None:  # noqa: N802
        length = int(self.headers.get("Content-Length", "0"))
        body = json.loads(self.rfile.read(length))
        type(self).received_requests.append(body)
        answer = "I don't have that information, sorry." if "unrelated" in body["messages"][1]["content"] else "The report is named Q2_Budget.xlsx."
        payload = json.dumps(
            {
                "id": "chatcmpl-test",
                "object": "chat.completion",
                "created": 0,
                "model": body["model"],
                "choices": [{"index": 0, "message": {"role": "assistant", "content": answer}, "finish_reason": "stop"}],
                "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15},
            }
        ).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(payload)

    def log_message(self, format: str, *args: object) -> None:  # noqa: A002
        return


@pytest.fixture
def stub_openai_server():
    _StubOpenAIHandler.received_requests = []
    server = ThreadingHTTPServer(("127.0.0.1", 0), _StubOpenAIHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_address[1]}/v1"
    finally:
        server.shutdown()
        thread.join(timeout=5)


def test_ask_user_sends_adapted_system_prompt_and_returns_the_answer(stub_openai_server) -> None:
    """The tool builds a system prompt from goal + relevant_information + real device date/time,
    sends it to the configured OpenAI-compatible endpoint, and returns the model's raw answer."""
    tool = build_ask_user_tool(
        "The report is named Q2_Budget.xlsx.",
        model="gpt-5.4-mini",
        api_key="sk-test-not-real",
        base_url=stub_openai_server,
    )["ask_user"]
    ctx = _FakeCtx(_FakeDriver("Thu Jul 30 09:03:21 IST 2026"), "Forward the manager's report.")

    answer = asyncio.run(tool["function"]("Which report do you mean?", ctx=ctx))

    assert answer == "The report is named Q2_Budget.xlsx."
    sent = _StubOpenAIHandler.received_requests[0]
    assert sent["model"] == "gpt-5.4-mini"
    system_prompt = sent["messages"][0]["content"]
    assert "Forward the manager's report." in system_prompt
    assert "The report is named Q2_Budget.xlsx." in system_prompt
    assert "Thu Jul 30 09:03:21 IST 2026" in system_prompt
    assert sent["messages"][1]["content"] == "Which report do you mean?"


def test_ask_user_defaults_relevant_information_placeholder_when_none_given(stub_openai_server) -> None:
    """An empty --ask-user-context still produces a valid system prompt (no missing-field crash)."""
    tool = build_ask_user_tool("", model="gpt-5.4-mini", api_key="sk-test-not-real", base_url=stub_openai_server)["ask_user"]
    ctx = _FakeCtx(_FakeDriver("Thu Jul 30 09:03:21 IST 2026"), "Some unrelated goal.")

    asyncio.run(tool["function"]("What's the capital of France?", ctx=ctx))

    system_prompt = _StubOpenAIHandler.received_requests[0]["messages"][0]["content"]
    assert "(none provided for this task)" in system_prompt


def test_ask_user_tool_is_zero_parameter_free_form_question() -> None:
    """The registered tool spec exposes exactly one required `question` string parameter."""
    tool = build_ask_user_tool("info", model="gpt-5.4-mini", api_key="sk-test")["ask_user"]
    assert set(tool["parameters"].keys()) == {"question"}
    assert tool["parameters"]["question"]["required"] is True


def test_get_ask_user_phoenix_tracer_returns_none_without_phoenix_url(monkeypatch) -> None:
    """Without a phoenix_url env var, no ask_user tracer is built (no Phoenix spans attempted)."""
    from DailyBench import custom_tools

    monkeypatch.delenv("phoenix_url", raising=False)
    monkeypatch.setattr(custom_tools, "_ask_user_phoenix_tracer", None)
    assert custom_tools._get_ask_user_phoenix_tracer() is None


def test_annotate_ask_user_span_records_tokens_and_model() -> None:
    """The ask_user span carries model + token counts so Phoenix counts the simulated user."""
    from DailyBench import custom_tools

    recorded: dict[str, object] = {}

    class FakeSpan:
        def set_attribute(self, key: str, value: object) -> None:
            recorded[key] = value

    class FakeUsage:
        prompt_tokens = 10
        completion_tokens = 5
        total_tokens = 15

    class FakeResponse:
        usage = FakeUsage()

    custom_tools._annotate_ask_user_span(
        FakeSpan(), "gpt-5.4-mini", "sys", "Which report?", "Q2_Budget.xlsx", FakeResponse()
    )
    assert recorded["openinference.span.kind"] == "LLM"
    assert recorded["llm.provider"] == "openai"
    assert recorded["llm.model_name"] == "gpt-5.4-mini"
    assert recorded["llm.token_count.prompt"] == 10
    assert recorded["llm.token_count.completion"] == 5
    assert recorded["llm.token_count.total"] == 15


def test_emit_ask_user_span_never_raises_on_tracer_failure() -> None:
    """A tracer that explodes must not break the ask_user answer (span emission is best-effort)."""
    from DailyBench import custom_tools

    class ExplodingTracer:
        def start_as_current_span(self, name: str) -> None:
            raise RuntimeError("tracing exploded")

    custom_tools._emit_ask_user_span(ExplodingTracer(), "gpt-5.4-mini", "sys", "q", "a", object())


@pytest.mark.skipif(DEVICE_SERIAL is None, reason="No ADB device attached (wired or wireless)")
def test_get_current_datetime_and_location_against_the_real_device() -> None:
    """get_current_datetime/get_current_location run against the real connected device."""
    from mobilerun_core_local.driver.android.adb import AndroidDriver

    class _RealCtx:
        def __init__(self, driver) -> None:
            self.driver = driver

    async def run() -> tuple[str, str]:
        driver = AndroidDriver(serial=DEVICE_SERIAL)
        ctx = _RealCtx(driver)
        datetime_value = await CUSTOM_TOOLS["get_current_datetime"]["function"](ctx=ctx)
        location_value = await CUSTOM_TOOLS["get_current_location"]["function"](ctx=ctx)
        return datetime_value, location_value

    datetime_value, location_value = asyncio.run(run())
    assert datetime_value.strip()
    assert "location" in location_value.lower()
