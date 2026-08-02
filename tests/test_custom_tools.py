"""Pytest coverage for the custom mobilerun tools: real-device date/time/location, the
ask_user tool spec, and the Phoenix span-emission helpers.

ask_user's real OpenAI call is verified end-to-end by scripts/e2e_askuser_phoenix.py
(real API, real token counts) — no fake endpoints/stubs live in this suite.
"""

from __future__ import annotations

import asyncio

import pytest
from conftest import first_adb_device

from DailyBench.custom_tools import CUSTOM_TOOLS, build_ask_user_tool

DEVICE_SERIAL = first_adb_device()


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
