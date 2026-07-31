"""Task-outcome typing and run summary generation."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel


class TaskOutcome(BaseModel):
    """Typed, structured result of one benchmarked task, taken straight from mobilerun's ResultEvent."""

    success: bool
    reason: str
    steps: int


def summarize(samples: list[dict], meta: dict[str, Any], llm_entries: list[dict[str, Any]]) -> dict[str, Any]:
    """Build one summary dictionary combining phone and model metrics."""
    summary: dict[str, Any] = {
        "run_id": meta["run_id"], "label": meta["label"], "sample_count": len(samples),
        "started_at_utc": meta["started_at_utc"], "ended_at_utc": meta["ended_at_utc"],
        "elapsed_seconds": meta["elapsed_seconds"], "command_exit_code": meta["command_exit_code"],
    }
    _add_llm_summary(summary, llm_entries)
    _add_phone_summary(summary, samples)
    return summary


def _add_llm_summary(summary: dict[str, Any], llm_entries: list[dict[str, Any]]) -> None:
    """Attach aggregate LLM token counts. Per-call detail stays in llm_proxy_metrics.jsonl."""
    completions = [entry for entry in llm_entries if entry.get("kind") == "chat.completion"]
    summary["llm_request_count"] = len(llm_entries)
    summary["llm_completion_count"] = len(completions)
    if not completions:
        return
    prompt_tokens = [(e.get("usage") or {}).get("prompt_tokens", 0) for e in completions]
    completion_tokens = [(e.get("usage") or {}).get("completion_tokens", 0) for e in completions]
    summary["llm_prompt_tokens_sum"] = sum(prompt_tokens)
    summary["llm_completion_tokens_sum"] = sum(completion_tokens)
    summary["llm_total_tokens_sum"] = sum(prompt_tokens) + sum(completion_tokens)


def _add_phone_summary(summary: dict[str, Any], samples: list[dict]) -> None:
    """Attach battery/thermal deltas and peaks.

    Start/end snapshots already live in preflight.json and postflight.json, so this
    only adds what those two files can't provide: the net change over the run
    (``_delta``) and the worst value seen mid-run (``_max``, which a start/end
    snapshot pair can miss).
    """
    if not samples:
        return
    first, last = samples[0], samples[-1]
    first_battery, last_battery = first["battery"], last["battery"]
    if first_battery.get("level_pct") is not None and last_battery.get("level_pct") is not None:
        summary["battery_level_delta_pct"] = last_battery["level_pct"] - first_battery["level_pct"]
    if first_battery.get("charge_counter_uah") is not None and last_battery.get("charge_counter_uah") is not None:
        summary["charge_counter_delta_uah"] = last_battery["charge_counter_uah"] - first_battery["charge_counter_uah"]
    for key in ("battery_temp_c", "vendor_phone_temp_c"):
        values = [sample["battery"].get(key) for sample in samples if sample["battery"].get(key) is not None]
        if values:
            summary[f"{key.replace('_c', '')}_max_c"] = max(values)
    statuses = [sample["thermal"].get("thermal_status_code") for sample in samples if isinstance(sample["thermal"].get("thermal_status_code"), int)]
    if statuses:
        summary["thermal_status_max"] = max(statuses)
    for sensor in ("CPU", "GPU", "BATTERY", "SKIN", "NPU", "POWER_AMPLIFIER"):
        values = [sample["thermal"]["hal_temperatures_c"].get(sensor, {}).get("value_c") for sample in samples]
        values = [value for value in values if value is not None]
        if values:
            summary[f"{sensor.lower()}_temp_max_c"] = max(values)
