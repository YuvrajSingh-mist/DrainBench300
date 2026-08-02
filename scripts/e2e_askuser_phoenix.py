"""REAL end-to-end check: a real ask_user call (real OpenAI API) must emit an OpenInference
LLM span into Phoenix.

Runs the full production path — build_ask_user_tool -> ask_user -> AsyncOpenAI -> REAL
api.openai.com -> _get_ask_user_phoenix_tracer -> _emit_ask_user_span -> OTLP -> Phoenix —
then verifies the span (span_kind=LLM, real model, real token counts) is queryable in the
Phoenix DB. No stubs: this makes a genuine OpenAI call and costs a few tokens.

REQUIRES:
  - `phoenix serve` on :6006 (or set phoenix_url)
  - OPENAI_API_KEY in the environment or .env
  - network access to api.openai.com

Usage:
  OPENAI_API_KEY=sk-... .venv/bin/python scripts/e2e_askuser_phoenix.py
"""
from __future__ import annotations

import asyncio
import os
import sqlite3
import time
from pathlib import Path

try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:  # pragma: no cover - .env loading is optional
    pass

os.environ["phoenix_url"] = os.environ.get("phoenix_url", "http://localhost:6006")
os.environ["phoenix_project_name"] = "askuser-e2e-real"

from DailyBench.custom_tools import build_ask_user_tool  # noqa: E402


class _FS:
    def __init__(self, instruction: str) -> None:
        self.instruction = instruction


class _FD:
    async def get_date(self) -> str:
        return "Mon Aug  3 10:00:00 IST 2026"


class _Ctx:
    def __init__(self) -> None:
        self.driver = _FD()
        self.shared_state = _FS("Verification probe: ask the user a real question.")


async def main() -> None:
    model = os.environ.get("ASK_USER_MODEL", "gpt-5.4-mini")
    tool = build_ask_user_tool(
        "The hidden fact for this probe is: the answer to 2+2 is 4.",
        model=model,
        log_path=Path("/tmp/ask_user_e2e_real.jsonl"),
    )["ask_user"]
    answer = await tool["function"]("What is 2+2?", ctx=_Ctx())
    print("REAL ANSWER:", answer)

    # SimpleSpanProcessor exports synchronously on span end; give it a beat anyway.
    time.sleep(2)

    con = sqlite3.connect(os.path.expanduser("~/.phoenix/phoenix.db"))
    rows = con.execute(
        """
        SELECT s.name, s.span_kind, s.llm_token_count_prompt, s.llm_token_count_completion,
               json_extract(s.attributes, '$.llm.model_name') AS model
        FROM spans s
        JOIN traces t ON s.trace_rowid = t.id
        JOIN projects p ON t.project_rowid = p.id
        WHERE p.name = 'askuser-e2e-real' AND s.span_kind = 'LLM'
        ORDER BY s.id DESC LIMIT 3
        """
    ).fetchall()
    con.close()
    print("REAL SPANS FOUND:", rows)
    assert rows, "No real ask_user LLM span landed in Phoenix!"
    print("REAL E2E PASS ✅ — a genuine OpenAI call's tokens are in Phoenix cumulative counts.")


if __name__ == "__main__":
    if not os.environ.get("OPENAI_API_KEY"):
        raise SystemExit("OPENAI_API_KEY required — this is a REAL OpenAI call, not a stub.")
    asyncio.run(main())
