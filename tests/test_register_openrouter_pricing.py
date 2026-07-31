"""Coverage for OpenRouter → Phoenix cost-pricing registration."""

from __future__ import annotations

import re
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

import pytest

from register_openrouter_pricing import upsert_pricing


def _make_phoenix_db(path: Path) -> None:
    """Create the minimal Phoenix generative_models/token_prices schema."""
    conn = sqlite3.connect(path)
    conn.executescript(
        """
        CREATE TABLE generative_models (
            id INTEGER PRIMARY KEY,
            name VARCHAR NOT NULL,
            provider VARCHAR NOT NULL,
            name_pattern VARCHAR NOT NULL,
            is_built_in BOOLEAN NOT NULL,
            start_time TIMESTAMP,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL,
            deleted_at TIMESTAMP
        );
        CREATE UNIQUE INDEX ix_generative_models_name_is_built_in
            ON generative_models (name, is_built_in) WHERE deleted_at IS NULL;
        CREATE TABLE token_prices (
            id INTEGER PRIMARY KEY,
            model_id INTEGER NOT NULL,
            token_type VARCHAR NOT NULL,
            is_prompt BOOLEAN NOT NULL,
            base_rate FLOAT NOT NULL,
            customization JSON,
            UNIQUE (model_id, token_type, is_prompt),
            FOREIGN KEY (model_id) REFERENCES generative_models (id) ON DELETE CASCADE
        );
        """
    )
    conn.close()


def test_upsert_pricing_creates_model_and_token_prices(tmp_path: Path) -> None:
    """Registering one model writes the generative_models row plus input/output
    token prices, converting per-1M prices to per-token base_rate."""
    db = tmp_path / "phoenix.db"
    _make_phoenix_db(db)

    count = upsert_pricing(db, {"qwen/qwen3.6-plus": (0.15 / 1_000_000.0, 0.60 / 1_000_000.0)})

    assert count == 1
    conn = sqlite3.connect(db)
    try:
        model = conn.execute(
            "SELECT name, provider, name_pattern, is_built_in FROM generative_models WHERE name='qwen/qwen3.6-plus'"
        ).fetchone()
        assert model == ("qwen/qwen3.6-plus", "openrouter", r"qwen/qwen3\.6\-plus", 0)
        prices = conn.execute(
            "SELECT token_type, is_prompt, base_rate FROM token_prices ORDER BY is_prompt DESC"
        ).fetchall()
        # per-token USD stored directly as base_rate
        assert prices == [("input", 1, 0.15 / 1_000_000.0), ("output", 0, 0.60 / 1_000_000.0)]
    finally:
        conn.close()


def test_upsert_pricing_updates_existing_rates_without_duplicates(tmp_path: Path) -> None:
    """Re-registering with new prices updates base_rate and does not duplicate rows."""
    db = tmp_path / "phoenix.db"
    _make_phoenix_db(db)

    assert upsert_pricing(db, {"qwen/qwen3.6-plus": (0.15 / 1_000_000.0, 0.60 / 1_000_000.0)}) == 1
    assert upsert_pricing(db, {"qwen/qwen3.6-plus": (0.20 / 1_000_000.0, 0.80 / 1_000_000.0)}) == 1

    conn = sqlite3.connect(db)
    try:
        assert conn.execute("SELECT COUNT(*) FROM generative_models").fetchone()[0] == 1
        assert conn.execute("SELECT COUNT(*) FROM token_prices").fetchone()[0] == 2
        rates = dict(conn.execute("SELECT token_type, base_rate FROM token_prices").fetchall())
        assert rates["input"] == pytest.approx(0.20 / 1_000_000.0)
        assert rates["output"] == pytest.approx(0.80 / 1_000_000.0)
    finally:
        conn.close()


def test_cost_computes_from_registered_pricing(tmp_path: Path) -> None:
    """Phoenix's own cost pipeline (CostModelLookup + SpanCostDetailsCalculator)
    prices a span whose model matches the registered rows, instead of returning 0.

    Requires the `tracing` extra (arize-phoenix); skipped in a default env.
    """
    phoenix = pytest.importorskip("phoenix")
    from phoenix.db import models
    from phoenix.server.cost_tracking.cost_details_calculator import SpanCostDetailsCalculator
    from phoenix.server.cost_tracking.cost_model_lookup import CostModelLookup

    model = models.GenerativeModel(
        name="qwen/qwen3.6-plus",
        provider="openrouter",
        name_pattern=re.compile(r"qwen/qwen3\.6\-plus"),
        is_built_in=False,
    )
    model.token_prices = [
        models.TokenPrice(token_type="input", is_prompt=True, base_rate=0.15 / 1_000_000.0),
        models.TokenPrice(token_type="output", is_prompt=False, base_rate=0.60 / 1_000_000.0),
    ]
    lookup = CostModelLookup([model])
    attributes = {
        "llm": {"model_name": "qwen/qwen3.6-plus", "token_count": {"prompt": 3739, "completion": 300}}
    }
    found = lookup.find_model(datetime.now(timezone.utc), attributes)
    assert found is not None
    assert found.name == "qwen/qwen3.6-plus"

    details = SpanCostDetailsCalculator(found.token_prices).calculate_details(attributes)
    total = sum(d.cost or 0.0 for d in details)
    assert total > 0
    assert total == pytest.approx(3739 * 0.15 / 1_000_000.0 + 300 * 0.60 / 1_000_000.0)
