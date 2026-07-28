"""Pytest coverage for summary and task-output parsing."""

from __future__ import annotations

from drainbench.summary import extract_task_output, summarize


def test_extract_task_output_multiline_success() -> None:
    stdout_text = """
INFO mobilerun 🎉 Goal achieved: Successfully searched for "weather tomorrow"
and opened the first result showing Tuesday's forecast: Rain, High of 27°C, Low
of 26°C.
DEBUG mobilerun 🔄 ResultEvent
""".strip()
    assert extract_task_output(stdout_text) == (
        'Successfully searched for "weather tomorrow" and opened the first result '
        "showing Tuesday's forecast: Rain, High of 27°C, Low of 26°C."
    )


def test_extract_task_output_failure_message() -> None:
    stdout_text = """
INFO mobilerun ❌ Goal failed: Battery percentage not visible in current UI
elements. Unable to retrieve the current battery level.
DEBUG mobilerun 🔄 ResultEvent
""".strip()
    assert extract_task_output(stdout_text) == (
        "Battery percentage not visible in current UI elements. "
        "Unable to retrieve the current battery level."
    )


def test_summarize_combines_llm_and_phone_metrics() -> None:
    samples = [
        {
            "battery": {"level_pct": 80, "charge_counter_uah": 5000, "battery_temp_c": 31.0},
            "thermal": {"thermal_status_code": 1, "hal_temperatures_c": {"CPU": {"value_c": 42.0}}},
        },
        {
            "battery": {"level_pct": 78, "charge_counter_uah": 4700, "battery_temp_c": 34.0},
            "thermal": {"thermal_status_code": 3, "hal_temperatures_c": {"CPU": {"value_c": 47.5}}},
        },
    ]
    meta = {
        "run_id": "run-1",
        "label": "demo",
        "started_at_utc": "2026-07-28T00:00:00Z",
        "ended_at_utc": "2026-07-28T00:02:00Z",
        "elapsed_seconds": 120.0,
        "command_exit_code": 0,
    }
    llm_entries = [
        {
            "kind": "chat.completion",
            "usage": {"prompt_tokens": 100, "completion_tokens": 20, "total_tokens": 120},
            "timings": {"prompt_ms": 2000.0, "predicted_ms": 1000.0, "prompt_per_second": 50.0, "predicted_per_second": 20.0},
        },
        {
            "kind": "chat.completion",
            "usage": {"prompt_tokens": 50, "completion_tokens": 10, "total_tokens": 60},
            "timings": {"prompt_ms": 1000.0, "predicted_ms": 500.0, "prompt_per_second": 50.0, "predicted_per_second": 20.0},
        },
    ]
    summary = summarize(samples, meta, llm_entries)
    assert summary["llm_total_tokens_sum"] == 180
    assert summary["llm_ttft_ms"] == 2000.0
    assert summary["battery_level_delta_pct"] == -2
    assert summary["cpu_temp_max_c"] == 47.5
