"""Tests for runtime model pricing (DailyBench.pricing) and ask_user cost logging.

Pricing is fetched live from a provider catalog, so these tests stand in a local HTTP server
that serves a small OpenRouter-shaped ``/v1/models`` payload — no real network, no hardcoded
rates in the assertions beyond what the fake catalog publishes.
"""

from __future__ import annotations

import asyncio
import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

from DailyBench.custom_tools import _log_ask_user_call, build_ask_user_tool
from DailyBench.pricing import ModelPricing

# The fake catalog this test serves: standard per-token USD rates (OpenRouter shape).
FAKE_CATALOG = {
    "data": [
        {
            "id": "openai/gpt-5.4-mini",
            "pricing": {"prompt": "0.00000015", "completion": "0.00000060"},
        },
        {
            "id": "qwen/qwen3.6-plus",
            "pricing": {"prompt": "0.00000025", "completion": "0.00000100"},
        },
        # Unpublished price (OpenRouter -1 sentinel) must be skipped.
        {"id": "vendor/secret-model", "pricing": {"prompt": "-1", "completion": "-1"}},
    ]
}


class _CatalogHandler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:  # noqa: N802
        if self.path.startswith("/v1/models"):
            body = json.dumps(FAKE_CATALOG).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        self.send_response(404)
        self.end_headers()

    def log_message(self, format: str, *args: object) -> None:  # noqa: A002
        return


@pytest.fixture
def catalog_url() -> str:
    server = ThreadingHTTPServer(("127.0.0.1", 0), _CatalogHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_address[1]}/v1/models"
    finally:
        server.shutdown()
        thread.join(timeout=5)


@pytest.fixture
def pricing(catalog_url: str) -> ModelPricing:
    return ModelPricing(catalog_url=catalog_url, ttl=3600, timeout=5.0)


class _FakeUsage:
    def __init__(self, prompt: int, completion: int, cost: float | None = None) -> None:
        self.prompt_tokens = prompt
        self.completion_tokens = completion
        self.total_tokens = prompt + completion
        self.cost = cost


class _FakeChoice:
    def __init__(self) -> None:
        self.finish_reason = "stop"


class _FakeMessage:
    def __init__(self, content: str) -> None:
        self.content = content


class _FakeResponse:
    def __init__(self, usage: _FakeUsage, model: str = "gpt-5.4-mini") -> None:
        self.usage = usage
        self.id = "chatcmpl-fake"
        self.model = model
        self.choices = [_FakeChoice()]
        self.choices[0].message = _FakeMessage("The answer.")


def test_lookup_reads_price_from_runtime_catalog(pricing: ModelPricing) -> None:
    """The per-1M-token rate comes from the served catalog, keyed by model id."""
    price = pricing.lookup("openai/gpt-5.4-mini")
    assert price is not None
    assert price.prompt_per_1m == pytest.approx(0.15)  # 0.00000015 * 1e6
    assert price.completion_per_1m == pytest.approx(0.60)


def test_lookup_maps_bare_name_to_openai_namespace(pricing: ModelPricing) -> None:
    """A bare model name like gpt-5.4-mini resolves against the openai/ namespace."""
    price = pricing.lookup("gpt-5.4-mini")
    assert price is not None
    assert price.prompt_per_1m == pytest.approx(0.15)


def test_lookup_returns_none_for_unknown_or_unpublished(pricing: ModelPricing) -> None:
    """Unknown models and -1 sentinel prices resolve to None, not a fabricated number."""
    assert pricing.lookup("openai/gpt-99") is None
    assert pricing.lookup("vendor/secret-model") is None


def test_estimate_cost_computes_dollars(pricing: ModelPricing) -> None:
    """cost = prompt/1M * prompt_rate + completion/1M * completion_rate."""
    # 1000 prompt tokens @ $0.15/1M + 200 completion @ $0.60/1M
    cost = pricing.estimate_cost("gpt-5.4-mini", 1000, 200)
    assert cost is not None
    assert cost == pytest.approx(1000 / 1e6 * 0.15 + 200 / 1e6 * 0.60)


def test_estimate_cost_none_when_unpublished(pricing: ModelPricing) -> None:
    assert pricing.estimate_cost("openai/gpt-99", 100, 100) is None


def test_log_ask_user_call_writes_runtime_pricing_cost(pricing: ModelPricing, tmp_path) -> None:
    """Cost is computed from the runtime catalog and written to the JSONL entry."""
    log = tmp_path / "ask_user_metrics.jsonl"
    _log_ask_user_call(
        log,
        "gpt-5.4-mini",
        "What time?",
        "9:30 AM",
        _FakeResponse(_FakeUsage(prompt=1000, completion=200)),
        elapsed_ms=10.0,
        pricing=pricing,
    )
    entry = json.loads(log.read_text().strip())
    assert entry["cost"] == pytest.approx(1000 / 1e6 * 0.15 + 200 / 1e6 * 0.60)
    assert entry["cost_details"]["source"] == "runtime_pricing_catalog"
    assert entry["cost_details"]["prompt_per_1m"] == pytest.approx(0.15)


def test_log_ask_user_call_prefers_provider_returned_cost(pricing: ModelPricing, tmp_path) -> None:
    """If the provider already returned usage.cost (gateway), that wins over the catalog."""
    log = tmp_path / "ask_user_metrics.jsonl"
    _log_ask_user_call(
        log,
        "gpt-5.4-mini",
        "What time?",
        "9:30 AM",
        _FakeResponse(_FakeUsage(prompt=1000, completion=200, cost=0.00123)),
        elapsed_ms=10.0,
        pricing=pricing,
    )
    entry = json.loads(log.read_text().strip())
    assert entry["cost"] == pytest.approx(0.00123)
    assert entry["cost_details"] is None


def test_log_ask_user_call_no_rate_logs_null_with_reason(pricing: ModelPricing, tmp_path) -> None:
    """A model with no published rate logs cost: null and an explanatory detail, never a guess."""
    log = tmp_path / "ask_user_metrics.jsonl"
    _log_ask_user_call(
        log,
        "openai/gpt-99",
        "What time?",
        "9:30 AM",
        _FakeResponse(_FakeUsage(prompt=1000, completion=200)),
        elapsed_ms=10.0,
        pricing=pricing,
    )
    entry = json.loads(log.read_text().strip())
    assert entry["cost"] is None
    assert "no published rate" in entry["cost_details"]["error"]


def test_ask_user_tool_injects_pricing_into_log(pricing: ModelPricing, tmp_path) -> None:
    """build_ask_user_tool accepts a pricing resolver and uses it when logging."""
    tool = build_ask_user_tool(
        "fact",
        model="gpt-5.4-mini",
        api_key="sk-test",
        base_url="http://127.0.0.1:1/v1",  # never reached: build only
        log_path=tmp_path / "ask_user_metrics.jsonl",
        pricing=pricing,
    )["ask_user"]
    assert tool["function"] is not None  # tool built fine with the resolver attached
