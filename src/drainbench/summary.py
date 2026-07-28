"""Task-output extraction and run summary generation."""

from __future__ import annotations

import re
from typing import Any

LOG_PREFIX_RE = re.compile(r"^(DEBUG|INFO|WARNING|ERROR)\s+mobilerun\b")
GOAL_PREFIXES = (
    "INFO mobilerun 🎉 Goal achieved: ",
    "INFO mobilerun ❌ Goal failed: ",
)


def extract_task_output(stdout_text: str) -> str:
    """Extract the full wrapped final task-facing message from Mobilerun stdout."""
    lines = stdout_text.splitlines()
    for index, line in enumerate(lines):
        for prefix in GOAL_PREFIXES:
            if prefix not in line:
                continue
            message_lines = [line.split(prefix, 1)[1].strip()]
            for next_line in lines[index + 1:]:
                stripped = next_line.strip()
                if not stripped:
                    continue
                if LOG_PREFIX_RE.match(next_line):
                    break
                message_lines.append(stripped)
            return _normalize_wrapped_message(message_lines)
    return ""


def _normalize_wrapped_message(message_lines: list[str]) -> str:
    """Collapse wrapped terminal lines into one readable message."""
    return re.sub(r"\s+", " ", " ".join(message_lines)).strip()


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
    """Attach aggregate LLM timing and token fields."""
    completions = [entry for entry in llm_entries if entry.get("kind") == "chat.completion"]
    summary["llm_request_count"] = len(llm_entries)
    summary["llm_completion_count"] = len(completions)
    if not completions:
        return
    first, last = completions[0], completions[-1]
    prompt_tokens = [e.get("usage", {}).get("prompt_tokens", 0) for e in completions]
    completion_tokens = [e.get("usage", {}).get("completion_tokens", 0) for e in completions]
    total_tokens = [e.get("usage", {}).get("total_tokens", 0) for e in completions]
    prompt_ms = [e.get("timings", {}).get("prompt_ms", 0.0) for e in completions]
    decode_ms = [e.get("timings", {}).get("predicted_ms", 0.0) for e in completions]
    summary.update({
        "llm_first_prompt_tokens": first.get("usage", {}).get("prompt_tokens"),
        "llm_first_completion_tokens": first.get("usage", {}).get("completion_tokens"),
        "llm_last_prompt_tokens": last.get("usage", {}).get("prompt_tokens"),
        "llm_last_completion_tokens": last.get("usage", {}).get("completion_tokens"),
        "llm_last_total_tokens": last.get("usage", {}).get("total_tokens"),
        "llm_last_prompt_ms": last.get("timings", {}).get("prompt_ms"),
        "llm_last_decode_ms": last.get("timings", {}).get("predicted_ms"),
        "llm_last_prompt_tokens_per_second": last.get("timings", {}).get("prompt_per_second"),
        "llm_last_decode_tokens_per_second": last.get("timings", {}).get("predicted_per_second"),
        "llm_prompt_tokens_sum": sum(prompt_tokens),
        "llm_completion_tokens_sum": sum(completion_tokens),
        "llm_total_tokens_sum": sum(total_tokens),
        "llm_prompt_ms_sum": sum(prompt_ms),
        "llm_decode_ms_sum": sum(decode_ms),
        "llm_ttft_ms": first.get("timings", {}).get("prompt_ms"),
    })
    if sum(prompt_ms) > 0:
        summary["llm_prefill_tokens_per_second"] = sum(prompt_tokens) * 1000.0 / sum(prompt_ms)
    if sum(decode_ms) > 0:
        summary["llm_decode_tokens_per_second"] = sum(completion_tokens) * 1000.0 / sum(decode_ms)


def _add_phone_summary(summary: dict[str, Any], samples: list[dict]) -> None:
    """Attach aggregate battery and thermal fields."""
    if not samples:
        return
    first, last = samples[0], samples[-1]
    first_battery, last_battery = first["battery"], last["battery"]
    summary["battery_level_start_pct"] = first_battery.get("level_pct")
    summary["battery_level_end_pct"] = last_battery.get("level_pct")
    if first_battery.get("level_pct") is not None and last_battery.get("level_pct") is not None:
        summary["battery_level_delta_pct"] = last_battery["level_pct"] - first_battery["level_pct"]
    summary["charge_counter_start_uah"] = first_battery.get("charge_counter_uah")
    summary["charge_counter_end_uah"] = last_battery.get("charge_counter_uah")
    if first_battery.get("charge_counter_uah") is not None and last_battery.get("charge_counter_uah") is not None:
        summary["charge_counter_delta_uah"] = last_battery["charge_counter_uah"] - first_battery["charge_counter_uah"]
    for key in ("battery_temp_c", "vendor_phone_temp_c"):
        values = [sample["battery"].get(key) for sample in samples if sample["battery"].get(key) is not None]
        if values:
            base = key.replace("_c", "")
            summary[f"{base}_start_c"], summary[f"{base}_end_c"], summary[f"{base}_max_c"] = values[0], values[-1], max(values)
    statuses = [sample["thermal"].get("thermal_status_code") for sample in samples if isinstance(sample["thermal"].get("thermal_status_code"), int)]
    if statuses:
        summary["thermal_status_max"] = max(statuses)
    for sensor in ("CPU", "GPU", "BATTERY", "SKIN", "NPU", "POWER_AMPLIFIER"):
        values = [sample["thermal"]["hal_temperatures_c"].get(sensor, {}).get("value_c") for sample in samples]
        values = [value for value in values if value is not None]
        if values:
            name = sensor.lower()
            summary[f"{name}_temp_start_c"], summary[f"{name}_temp_end_c"], summary[f"{name}_temp_max_c"] = values[0], values[-1], max(values)
