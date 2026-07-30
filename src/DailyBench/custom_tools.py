"""Custom mobilerun tools exposing ground-truth device date/time and approximate location.

mobilerun's FastAgent loop has no built-in way to learn the real current date/time: the
underlying AndroidDriver.get_date() exists but is never registered as a callable tool, and
`phone_state` only ever carries packageName/currentApp (see reports/qwen35-4b-public-wired-run-
analysis.md, finding A3). No location tool exists at all. Both are read directly via ADB rather
than by swiping open Quick Settings and reading the status bar off a UI dump - that's slower,
fragile against OEM UI variation, and for location doesn't even surface coordinates there in the
first place. `dumpsys location` is the standard ADB-level way to read a device's last known fix
and is already privacy-redacted by Android itself (coarse ~2-decimal precision), which is exactly
the right level of precision for these benchmark tasks.
"""

from __future__ import annotations

import json
import re
import time
from pathlib import Path
from typing import TYPE_CHECKING, Any, Dict

from openai import AsyncOpenAI

if TYPE_CHECKING:
    from mobilerun.agent.action_context import ActionContext

_LOCATION_RE = re.compile(r"last location=Location\[(\w+) ([\-\d.*]+),([\-\d.*]+)")

# Fixed for the whole harness - not exposed as a CLI flag, since every run uses the same
# simulated-user model. Override via the function's own `model=` kwarg in tests.
DEFAULT_ASK_USER_MODEL = "gpt-5.4-mini"

# Adapted from the AndroidWorld/MobileAgent-family "ask-user" simulated-user prompt. The
# original hardcoded "Today is 2025-10-16, Thursday" as a fixed snapshot; this asks for the
# device's own real `adb shell date` output instead, so the simulated user is never stale.
ASK_USER_SYSTEM_PROMPT_TEMPLATE = """You are acting as a mobile phone user. A mobile GUI agent is executing a task on your phone. The task goal is: {goal}

The relevant information for the task is: {relevant_information}

You need to answer questions from the mobile GUI agent about the task above. You can ONLY answer using the relevant information given and the task goal - do not make up any information under any circumstances. If the question is not related to the task, or no relevant information is available to answer it, refuse to answer in a polite manner and say so plainly.

The current real date and time is: {current_datetime}. If the question is about the date or time, answer using this real value rather than any date you might otherwise assume."""


async def get_current_datetime(*, ctx: "ActionContext") -> str:
    """Return the device's real current date and time."""
    return await ctx.driver.get_date()


async def get_current_location(*, ctx: "ActionContext") -> str:
    """Return the device's last known approximate location as latitude/longitude."""
    dump = await ctx.driver.device.shell("dumpsys location")
    match = _LOCATION_RE.search(dump)
    if not match:
        return "Failed: no location fix available on this device (location services may be off)."
    provider, lat, lon = match.groups()
    return f"Approximate location ({provider} provider): latitude {lat}, longitude {lon}"


def build_ask_user_tool(
    relevant_information: str,
    *,
    model: str = DEFAULT_ASK_USER_MODEL,
    api_key: str | None = None,
    base_url: str | None = None,
    log_path: Path | None = None,
) -> Dict[str, Dict[str, Any]]:
    """Build a per-run `ask_user` custom tool, closing over this task's hidden ground-truth fact.

    Hard/ASK-USER tasks are deliberately missing one load-bearing fact (see public.md's Grading
    model note: "resolved by an LLM playing the user, holding only the omitted fact, answering
    just what's asked"). `relevant_information` is that fact, supplied per run via
    `--ask-user-context` - the tool itself never invents it.

    When `log_path` is set, each call appends a JSONL entry with timing, token usage, and model
    info — same shape as the main proxy's `llm_proxy_metrics.jsonl` — so ask_user costs are
    tracked alongside the main agent's LLM costs.

    The client is constructed lazily, on first actual call - most tasks never call ask_user at
    all, and building it eagerly would make every single run require OPENAI_API_KEY to be set,
    even for tasks that will never touch this tool.
    """
    client: AsyncOpenAI | None = None

    async def ask_user(question: str, *, ctx: "ActionContext") -> str:
        nonlocal client
        if client is None:
            client = AsyncOpenAI(api_key=api_key, base_url=base_url)
        current_datetime = await ctx.driver.get_date()
        system_prompt = ASK_USER_SYSTEM_PROMPT_TEMPLATE.format(
            goal=ctx.shared_state.instruction,
            relevant_information=relevant_information or "(none provided for this task)",
            current_datetime=current_datetime,
        )
        start = time.monotonic()
        response = await client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": question},
            ],
        )
        elapsed_ms = (time.monotonic() - start) * 1000.0
        content = response.choices[0].message.content
        if log_path is not None:
            _log_ask_user_call(log_path, model, question, content, response, elapsed_ms)
        return content.strip() if content else "Failed: empty response from the simulated user."

    return {
        "ask_user": {
            "function": ask_user,
            "parameters": {
                "question": {
                    "type": "string",
                    "required": True,
                    "description": "The clarifying question to ask the user, in plain language.",
                },
            },
            "description": (
                "Ask the human user a clarifying question when the task is missing a load-bearing "
                "fact you can't find anywhere on the device (e.g. which contact, which file, what "
                "date). Use this instead of guessing or making something up. Only call it when "
                "you're genuinely stuck, and ask one specific question at a time."
            ),
        }
    }


def _log_ask_user_call(log_path: Path, model: str, question: str, answer: str | None, response: Any, elapsed_ms: float) -> None:
    """Append one ask_user completion record to a JSONL log, matching the main proxy's format."""
    usage = response.usage
    entry = {
        "timestamp_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "kind": "chat.completion",
        "source": "ask_user",
        "elapsed_ms": elapsed_ms,
        "request": {"model": model, "message_count": 2, "framework_prompt": question},
        "response": answer or "",
        "usage": {
            "prompt_tokens": usage.prompt_tokens if usage else None,
            "completion_tokens": usage.completion_tokens if usage else None,
            "total_tokens": usage.total_tokens if usage else None,
        },
        "id": response.id,
        "model": response.model,
        "finish_reason": response.choices[0].finish_reason if response.choices else None,
    }
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with open(log_path, "a", encoding="utf-8") as handle:
        handle.write(json.dumps(entry, sort_keys=True) + "\n")


CUSTOM_TOOLS: Dict[str, Dict[str, Any]] = {
    "get_current_datetime": {
        "function": get_current_datetime,
        "parameters": {},
        "description": (
            "Get the device's real current date and time. Call this whenever a task references "
            "'today', 'this week', 'right now', or any other relative date/time - do not guess or "
            "infer the date from on-screen content alone."
        ),
    },
    "get_current_location": {
        "function": get_current_location,
        "parameters": {},
        "description": (
            "Get the device's last known approximate location as latitude/longitude. Call this for "
            "tasks that reference 'my current place' or 'nearby'."
        ),
    },
}
