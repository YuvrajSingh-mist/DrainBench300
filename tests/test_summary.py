"""Pytest coverage for summary generation and task-outcome typing."""

from __future__ import annotations

from DailyBench.summary import TaskOutcome, summarize


def test_task_outcome_round_trips_through_model_dump() -> None:
    """TaskOutcome carries mobilerun's ResultEvent fields straight through to a plain dict."""
    outcome = TaskOutcome(success=True, reason="Replied to the latest email.", steps=4)
    assert outcome.model_dump() == {"success": True, "reason": "Replied to the latest email.", "steps": 4}


def test_summarize_combines_llm_and_phone_metrics() -> None:
    """Baseline happy path: fully-populated phone samples and LLM completions aggregate to the expected totals."""
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
        },
        {
            "kind": "chat.completion",
            "usage": {"prompt_tokens": 50, "completion_tokens": 10, "total_tokens": 60},
        },
    ]
    summary = summarize(samples, meta, llm_entries)
    assert summary["llm_total_tokens_sum"] == 180
    assert summary["llm_prompt_tokens_sum"] == 150
    assert summary["llm_completion_tokens_sum"] == 30
    assert summary["battery_level_delta_pct"] == -2
    assert summary["cpu_temp_max_c"] == 47.5
    # start/end snapshots live in preflight/postflight; run_metrics only keeps delta + max
    assert "battery_level_start_pct" not in summary
    assert "cpu_temp_start_c" not in summary
    assert "cpu_temp_end_c" not in summary


def _base_meta() -> dict:
    return {
        "run_id": "run-null-usage",
        "label": "demo",
        "started_at_utc": "2026-07-28T00:00:00Z",
        "ended_at_utc": "2026-07-28T00:02:00Z",
        "elapsed_seconds": 77.0,
        "command_exit_code": 0,
    }


def test_summarize_survives_null_usage() -> None:
    """A proxy that failed to parse a streamed response logs usage as null."""
    llm_entries = [
        {"kind": "chat.completion", "usage": None},
        {"kind": "chat.completion", "usage": None},
    ]
    summary = summarize([], _base_meta(), llm_entries)
    assert summary["llm_completion_count"] == 2
    assert summary["llm_prompt_tokens_sum"] == 0
    assert summary["llm_completion_tokens_sum"] == 0
    assert summary["llm_total_tokens_sum"] == 0


def test_summarize_handles_mixed_null_and_populated_entries() -> None:
    """One good completion and one with null usage should still aggregate the good one."""
    llm_entries = [
        {"kind": "chat.completion", "usage": None},
        {
            "kind": "chat.completion",
            "usage": {"prompt_tokens": 40, "completion_tokens": 8, "total_tokens": 48},
        },
    ]
    summary = summarize([], _base_meta(), llm_entries)
    assert summary["llm_completion_count"] == 2
    assert summary["llm_prompt_tokens_sum"] == 40
    assert summary["llm_completion_tokens_sum"] == 8
    assert summary["llm_total_tokens_sum"] == 48


def test_summarize_with_no_llm_entries_skips_llm_fields() -> None:
    """With zero LLM entries, only the request/completion counts are set and no aggregate llm_* fields appear."""
    summary = summarize([], _base_meta(), [])
    assert summary["llm_request_count"] == 0
    assert summary["llm_completion_count"] == 0
    assert "llm_total_tokens_sum" not in summary
