"""End-to-end check: a real ask_user call must emit an OpenInference LLM span into Phoenix.

Runs the full path: build_ask_user_tool -> ask_user -> AsyncOpenAI (stub server) ->
_get_ask_user_phoenix_tracer -> _emit_ask_user_span -> OTLP -> Phoenix, then verifies
the span (span_kind=LLM, model name, token counts) is queryable in the Phoenix DB.
"""
import asyncio
import json
import os
import sqlite3
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

os.environ["phoenix_url"] = "http://localhost:6006"
os.environ["phoenix_project_name"] = "askuser-e2e-test"

from DailyBench.custom_tools import build_ask_user_tool  # noqa: E402


class _Handler(BaseHTTPRequestHandler):
    def do_POST(self):  # noqa: N802
        n = int(self.headers.get("Content-Length", "0"))
        body = json.loads(self.rfile.read(n))
        payload = json.dumps({
            "id": "chatcmpl-e2e", "object": "chat.completion", "created": 0,
            "model": body["model"],
            "choices": [{"index": 0, "message": {"role": "assistant", "content": "42 MG Road, Bhubaneswar"}, "finish_reason": "stop"}],
            "usage": {"prompt_tokens": 77, "completion_tokens": 13, "total_tokens": 90},
        }).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(payload)

    def log_message(self, *args):  # noqa: A002
        return


server = ThreadingHTTPServer(("127.0.0.1", 0), _Handler)
threading.Thread(target=server.serve_forever, daemon=True).start()
base = f"http://127.0.0.1:{server.server_address[1]}/v1"


class _FS:
    def __init__(self, inst: str) -> None:
        self.instruction = inst


class _FD:
    async def get_date(self) -> str:
        return "Mon Aug  3 10:00:00 IST 2026"


class _Ctx:
    def __init__(self) -> None:
        self.driver = _FD()
        self.shared_state = _FS("Send the dinner address to Yuvraj.")


tool = build_ask_user_tool(
    "The dinner address is 42 MG Road, Bhubaneswar.",
    model="gpt-5.4-mini",
    api_key="sk-e2e-not-real",
    base_url=base,
)["ask_user"]
answer = asyncio.run(tool["function"]("What's the address?", ctx=_Ctx()))
print("ANSWER:", answer)
server.shutdown()

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
    WHERE p.name = 'askuser-e2e-test' AND s.span_kind = 'LLM'
    ORDER BY s.id DESC LIMIT 5
    """
).fetchall()
con.close()
print("E2E SPANS FOUND:", rows)
assert rows, "No ask_user LLM span landed in Phoenix!"
assert rows[0][3] == 13, "completion token count mismatch"
print("E2E PASS ✅ — ask_user tokens are in Phoenix cumulative counts.")
