#!/usr/bin/env python3
"""Tiny OpenAI-compatible proxy that logs llama.cpp timing/usage fields per request."""

from __future__ import annotations

import argparse
import json
import time
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import urljoin


def utc_now() -> str:
    """Return the current UTC timestamp used in JSONL log entries."""
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


class ProxyHandler(BaseHTTPRequestHandler):
    """Forward OpenAI-style requests while logging completion metrics."""

    server_version = "OpenAIProxyLogger/0.1"

    def _read_body(self) -> bytes:
        """Read the full HTTP request body."""
        length = int(self.headers.get("Content-Length", "0"))
        return self.rfile.read(length) if length else b""

    def _forward(self, method: str, path: str, body: bytes) -> tuple[int, dict[str, str], bytes]:
        """Forward one request to the upstream model server."""
        target = urljoin(self.server.upstream_base, path)  # type: ignore[attr-defined]
        headers = {
            "Content-Type": self.headers.get("Content-Type", "application/json"),
        }
        req = urllib.request.Request(target, data=body if method != "GET" else None, headers=headers, method=method)
        with urllib.request.urlopen(req, timeout=self.server.timeout_seconds) as resp:  # type: ignore[attr-defined]
            response_body = resp.read()
            response_headers = {k: v for k, v in resp.headers.items()}
            return resp.status, response_headers, response_body

    def _write_response(self, status: int, headers: dict[str, str], body: bytes) -> None:
        """Write one proxied HTTP response back to the caller."""
        self.send_response(status)
        hop_by_hop = {"transfer-encoding", "connection", "content-encoding"}
        for key, value in headers.items():
            if key.lower() in hop_by_hop:
                continue
            self.send_header(key, value)
        self.end_headers()
        self.wfile.write(body)

    def _log_completion(self, request_payload: dict[str, Any], response_payload: dict[str, Any], elapsed_ms: float) -> None:
        """Append one completion timing record to the JSONL log."""
        entry = {
            "timestamp_utc": utc_now(),
            "kind": "chat.completion",
            "elapsed_proxy_ms": elapsed_ms,
            "request": {
                "model": request_payload.get("model"),
                "max_tokens": request_payload.get("max_tokens"),
                "temperature": request_payload.get("temperature"),
                "message_count": len(request_payload.get("messages", [])) if isinstance(request_payload.get("messages"), list) else None,
            },
            "usage": response_payload.get("usage"),
            "timings": response_payload.get("timings"),
            "id": response_payload.get("id"),
            "model": response_payload.get("model"),
            "finish_reason": (
                response_payload.get("choices", [{}])[0].get("finish_reason")
                if isinstance(response_payload.get("choices"), list) and response_payload.get("choices")
                else None
            ),
        }
        with self.server.log_path.open("a", encoding="utf-8") as handle:  # type: ignore[attr-defined]
            handle.write(json.dumps(entry, sort_keys=True) + "\n")

    def do_GET(self) -> None:  # noqa: N802
        """Handle forwarded GET requests used by the harness."""
        if self.path.startswith("/v1/models"):
            status, headers, body = self._forward("GET", self.path, b"")
            self._write_response(status, headers, body)
            return
        if self.path.startswith("/healthz"):
            payload = json.dumps({"ok": True}).encode()
            self._write_response(200, {"Content-Type": "application/json"}, payload)
            return
        self._write_response(404, {"Content-Type": "application/json"}, b'{"error":"not found"}')

    def do_POST(self) -> None:  # noqa: N802
        """Handle forwarded chat completion requests and log metrics."""
        if not self.path.startswith("/v1/chat/completions"):
            self._write_response(404, {"Content-Type": "application/json"}, b'{"error":"not found"}')
            return
        body = self._read_body()
        start = time.monotonic()
        try:
            request_payload = json.loads(body.decode() or "{}")
        except json.JSONDecodeError:
            self._write_response(400, {"Content-Type": "application/json"}, b'{"error":"invalid json"}')
            return
        try:
            status, headers, resp_body = self._forward("POST", self.path, body)
        except urllib.error.HTTPError as exc:
            self._write_response(exc.code, {"Content-Type": "application/json"}, exc.read())
            return
        elapsed_ms = (time.monotonic() - start) * 1000.0
        try:
            response_payload = json.loads(resp_body.decode())
        except json.JSONDecodeError:
            response_payload = {}
        if isinstance(response_payload, dict):
            self._log_completion(request_payload, response_payload, elapsed_ms)
        self._write_response(status, headers, resp_body)

    def log_message(self, format: str, *args: Any) -> None:  # noqa: A003
        """Silence default HTTP access logging for cleaner benchmark output."""
        return


def build_parser() -> argparse.ArgumentParser:
    """Build the CLI parser for the proxy/logger."""
    parser = argparse.ArgumentParser(description="OpenAI-compatible proxy/logger for llama.cpp responses.")
    parser.add_argument("--listen-host", default="127.0.0.1")
    parser.add_argument("--listen-port", type=int, default=8090)
    parser.add_argument("--upstream-base", required=True, help="Upstream base URL, e.g. http://192.168.1.23:8081/v1")
    parser.add_argument("--log-jsonl", required=True, help="Path to append JSONL completion timing logs to.")
    parser.add_argument("--timeout-seconds", type=float, default=300.0)
    return parser


def main() -> int:
    """Start the proxy server and keep serving until interrupted."""
    args = build_parser().parse_args()
    log_path = Path(args.log_jsonl).expanduser()
    log_path.parent.mkdir(parents=True, exist_ok=True)
    log_path.touch(exist_ok=True)

    server = ThreadingHTTPServer((args.listen_host, args.listen_port), ProxyHandler)
    server.upstream_base = args.upstream_base.rstrip("/") + "/"  # type: ignore[attr-defined]
    server.log_path = log_path  # type: ignore[attr-defined]
    server.timeout_seconds = args.timeout_seconds  # type: ignore[attr-defined]
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        return 0

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
