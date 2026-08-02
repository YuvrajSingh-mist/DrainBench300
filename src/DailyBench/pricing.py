"""Runtime per-model USD pricing, fetched from the provider's published catalog.

The whole point of this module is that rates are **never hardcoded**. Instead the per-1M-token
price for a model is read live from a provider pricing catalog (default: OpenRouter's public
``GET /v1/models``, which lists every model's standard prompt/completion rate in USD per token).
Because the lookup is keyed by the exact model id the user chose (``--model`` for the agent,
``--ask-user-model`` for the simulated user), costs automatically track whatever model is
selected and any price changes the provider makes — no code changes needed.

Design notes:

- Catalog is fetched at most once per ``ttl`` (default 1 hour) and cached process-wide, so a
  long benchmark run pays for one HTTP request, not one per LLM call.
- The fetch is best-effort: if the catalog is unreachable we keep the last known prices (or
  empty) and record ``last_error``; callers surface that as ``cost: null`` rather than guessing.
- A bare model name (e.g. ``gpt-5.4-mini``) is also tried as ``openai/<name>`` so direct-OpenAI
  models resolve against the same catalog namespace used for the agent.
- Providers that already return a dollar figure in the response (OpenRouter gateways return
  ``usage.cost``) take priority in ``custom_tools._log_ask_user_call``; this module is the
  fallback for direct calls (like ask_user -> api.openai.com) where the API returns only tokens.
"""

from __future__ import annotations

import json
import os
import threading
import time
import urllib.request
from dataclasses import dataclass
from typing import Any

# OpenRouter's public catalog: every model with its standard per-token prompt/completion rate.
# Overridable at runtime via the ASK_USER_PRICING_URL env var so no URL is baked in either.
DEFAULT_PRICING_URL = "https://openrouter.ai/api/v1/models"
PRICING_URL_ENV = "ASK_USER_PRICING_URL"
CATALOG_TTL_SECONDS = 60 * 60  # refresh at most once an hour
CATALOG_TIMEOUT_SECONDS = 15.0

# OpenRouter uses a -1 sentinel for models whose price is not published.
_UNKNOWN_PRICE = -1.0


@dataclass(frozen=True)
class Price:
    """USD cost per 1M tokens for one model."""

    prompt_per_1m: float
    completion_per_1m: float


class ModelPricing:
    """Fetch + cache per-model USD rates from a provider pricing catalog."""

    def __init__(
        self,
        catalog_url: str | None = None,
        ttl: float = CATALOG_TTL_SECONDS,
        timeout: float = CATALOG_TIMEOUT_SECONDS,
    ) -> None:
        self._url = catalog_url or os.environ.get(PRICING_URL_ENV) or DEFAULT_PRICING_URL
        self._ttl = ttl
        self._timeout = timeout
        self._catalog: dict[str, Price] = {}
        self._loaded_at = 0.0
        self._lock = threading.Lock()
        self._last_error: str | None = None

    def _fetch_catalog(self) -> dict[str, Price]:
        """GET the catalog and return {model_id: Price}. Raises on network/parse failure."""
        with urllib.request.urlopen(self._url, timeout=self._timeout) as resp:
            payload: dict[str, Any] = json.loads(resp.read().decode("utf-8"))
        out: dict[str, Price] = {}
        for item in payload.get("data", []):
            model_id = item.get("id")
            if not model_id:
                continue
            pricing = item.get("pricing") or {}
            try:
                prompt = float(pricing.get("prompt") or 0.0)
                completion = float(pricing.get("completion") or 0.0)
            except (TypeError, ValueError):
                continue
            # Skip unpublished prices (negative sentinel or missing).
            if prompt < 0 or completion < 0:
                continue
            out[str(model_id)] = Price(prompt_per_1m=prompt * 1e6, completion_per_1m=completion * 1e6)
        return out

    def _ensure_loaded(self) -> None:
        with self._lock:
            if self._catalog and (time.monotonic() - self._loaded_at) < self._ttl:
                return
            try:
                self._catalog = self._fetch_catalog()
                self._loaded_at = time.monotonic()
                self._last_error = None
            except Exception as exc:  # noqa: BLE001 - network/catalog down: keep stale data
                self._last_error = f"{type(exc).__name__}: {exc}"

    def lookup(self, model: str) -> Price | None:
        """Return the model's per-1M-token rate, or None if unknown/unpublished."""
        self._ensure_loaded()
        candidates = [model]
        if "/" not in model:
            candidates.append(f"openai/{model}")
        for candidate in candidates:
            price = self._catalog.get(candidate)
            if price is not None:
                return price
        return None

    def estimate_cost(self, model: str, prompt_tokens: int, completion_tokens: int) -> float | None:
        """Estimate USD cost for a token split, or None if the model has no published rate."""
        price = self.lookup(model)
        if price is None:
            return None
        return (prompt_tokens / 1e6) * price.prompt_per_1m + (completion_tokens / 1e6) * price.completion_per_1m

    @property
    def last_error(self) -> str | None:
        """Human-readable reason the last catalog fetch failed (None if it succeeded)."""
        return self._last_error


# Process-wide default instance (lazy so offline runs / tests never pay for a network fetch).
_default_pricing: ModelPricing | None = None
_default_pricing_lock = threading.Lock()


def get_default_pricing() -> ModelPricing:
    """Return the process-wide ModelPricing singleton, creating it on first use."""
    global _default_pricing
    with _default_pricing_lock:
        if _default_pricing is None:
            _default_pricing = ModelPricing()
        return _default_pricing
