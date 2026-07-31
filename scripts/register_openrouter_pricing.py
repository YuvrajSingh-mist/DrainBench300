#!/usr/bin/env python3
"""Register OpenRouter model pricing with the local Phoenix database.

Phoenix computes per-span LLM cost by matching the span's ``llm.model_name``
against rows in ``generative_models`` and applying each model's ``token_prices``
(USD per token). Its bundled manifest only covers OpenAI/Anthropic/Gemini/...,
so OpenRouter models (e.g. ``qwen/qwen3.6-plus``) get ``total_cost = NULL`` —
shown as $0.00 in the Phoenix UI.

This script upserts real OpenRouter pricing into ``~/.phoenix/phoenix.db`` as
user-defined models (``is_built_in = 0``). Phoenix's ``GenerativeModelStore``
daemon refreshes every ~5 seconds, so newly registered models start costing new
spans almost immediately.

Pricing source:
  * live from https://openrouter.ai/api/v1/models using ``OPENROUTER_API_KEY``
    (default), or
  * explicit ``--prompt-price-per-m`` / ``--completion-price-per-m``.

OpenRouter's ``pricing.prompt``/``pricing.completion`` fields are USD per single
token; the CLI's ``--*-per-m`` flags are USD per 1M tokens and are converted to
per-token before being stored.

Examples:
  uv run scripts/register_openrouter_pricing.py --model qwen/qwen3.6-plus
  uv run scripts/register_openrouter_pricing.py --model qwen/qwen3.6-plus \\
      --prompt-price-per-m 0.15 --completion-price-per-m 0.60
  uv run scripts/register_openrouter_pricing.py --all
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sqlite3
import sys
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

OPENROUTER_MODELS_URL = "https://openrouter.ai/api/v1/models"
DEFAULT_DB = "~/.phoenix/phoenix.db"


def fetch_openrouter_pricing(
    api_key: str,
    model_ids: list[str] | None = None,
    timeout: float = 30.0,
) -> dict[str, tuple[float, float]]:
    """Return ``{model_id: (prompt_price_per_token, completion_price_per_token)}``.

    Fetches OpenRouter's model catalog. OpenRouter's ``pricing.prompt`` and
    ``pricing.completion`` fields are USD per single token. When ``model_ids`` is
    given, only those slugs are returned; otherwise every model is returned.
    """
    req = urllib.request.Request(
        OPENROUTER_MODELS_URL,
        headers={"Authorization": f"Bearer {api_key}", "User-Agent": "dailybench-pricing/1.0"},
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        payload: dict[str, Any] = json.loads(resp.read().decode("utf-8"))
    wanted = set(model_ids) if model_ids else None
    pricing: dict[str, tuple[float, float]] = {}
    for model in payload.get("data", []):
        model_id = model.get("id")
        if not model_id or (wanted is not None and model_id not in wanted):
            continue
        p = model.get("pricing") or {}
        try:
            prompt_per_m = float(p["prompt"])
            completion_per_m = float(p["completion"])
        except (KeyError, TypeError, ValueError):
            continue
        pricing[model_id] = (prompt_per_m, completion_per_m)
    return pricing


def upsert_pricing(
    db_path: str | Path,
    pricing: dict[str, tuple[float, float]],
    provider: str = "openrouter",
) -> int:
    """Upsert ``generative_models`` + ``token_prices`` rows into the Phoenix DB.

    ``pricing`` maps model slug -> (prompt_price_per_token, completion_price_per_token);
    these are stored directly as ``token_prices.base_rate`` (USD per token), which is
    what Phoenix's cost calculator multiplies token counts by. Returns the number of
    models registered/updated.
    """
    db_path = Path(db_path).expanduser()
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
    conn = sqlite3.connect(str(db_path), timeout=30)
    conn.execute("PRAGMA busy_timeout = 30000")
    count = 0
    try:
        for model_id, (prompt_per_token, completion_per_token) in pricing.items():
            pattern = re.escape(model_id)
            conn.execute(
                """INSERT OR IGNORE INTO generative_models
                       (name, provider, name_pattern, is_built_in, created_at, updated_at)
                       VALUES (?, ?, ?, 0, ?, ?)""",
                (model_id, provider, pattern, now, now),
            )
            row = conn.execute(
                "SELECT id FROM generative_models WHERE name = ? AND is_built_in = 0 AND deleted_at IS NULL",
                (model_id,),
            ).fetchone()
            if row is None:
                continue
            model_pk = row[0]
            for token_type, is_prompt, per_token in (
                ("input", True, prompt_per_token),
                ("output", False, completion_per_token),
            ):
                if per_token is None:
                    continue
                base_rate = per_token
                conn.execute(
                    """INSERT INTO token_prices (model_id, token_type, is_prompt, base_rate)
                           VALUES (?, ?, ?, ?)
                           ON CONFLICT(model_id, token_type, is_prompt)
                           DO UPDATE SET base_rate = excluded.base_rate""",
                    (model_pk, token_type, int(is_prompt), base_rate),
                )
            # Bump updated_at so the GenerativeModelStore daemon's incremental
            # fetch (updated_at >= last_fetch) picks this row up promptly.
            conn.execute(
                "UPDATE generative_models SET updated_at = ? WHERE id = ?",
                (now, model_pk),
            )
            count += 1
        conn.commit()
    finally:
        conn.close()
    return count


def build_parser() -> argparse.ArgumentParser:
    """Build the CLI parser."""
    parser = argparse.ArgumentParser(
        description="Register OpenRouter model pricing with the local Phoenix database.",
    )
    parser.add_argument("--db", default=DEFAULT_DB, help=f"Path to the Phoenix SQLite DB (default: {DEFAULT_DB}).")
    parser.add_argument("--model", action="append", default=[], help="OpenRouter model slug(s) to register (repeatable).")
    parser.add_argument("--all", action="store_true", help="Register every model in OpenRouter's catalog.")
    parser.add_argument("--prompt-price-per-m", type=float, default=None, help="USD per 1M prompt tokens (bypasses the OpenRouter API).")
    parser.add_argument("--completion-price-per-m", type=float, default=None, help="USD per 1M completion tokens (bypasses the OpenRouter API).")
    parser.add_argument("--api-key", default=None, help="OpenRouter API key (defaults to the OPENROUTER_API_KEY env var / .env).")
    return parser


def main() -> int:
    """Run the registration and print a summary."""
    args = build_parser().parse_args()
    load_dotenv()
    model_ids = list(args.model)

    if args.prompt_price_per_m is not None or args.completion_price_per_m is not None:
        if not model_ids:
            raise SystemExit("--prompt-price-per-m/--completion-price-per-m require at least one --model.")
        # CLI flags are USD per 1M tokens; convert to USD per token for the DB.
        pricing = {
            mid: (
                args.prompt_price_per_m / 1_000_000.0 if args.prompt_price_per_m is not None else None,
                args.completion_price_per_m / 1_000_000.0 if args.completion_price_per_m is not None else None,
            )
            for mid in model_ids
        }
    else:
        api_key = args.api_key or os.environ.get("OPENROUTER_API_KEY")
        if not api_key:
            raise SystemExit(
                "OPENROUTER_API_KEY is required to fetch pricing from OpenRouter "
                "(or pass --prompt-price-per-m/--completion-price-per-m explicitly)."
            )
        if not model_ids and not args.all:
            raise SystemExit("Specify --model (repeatable) or --all to fetch the whole catalog.")
        pricing = fetch_openrouter_pricing(api_key, model_ids or None)

    if not pricing:
        raise SystemExit("No matching models found to register.")

    missing = [mid for mid in model_ids if mid not in pricing]
    if missing:
        print(f"WARNING: not found in OpenRouter's catalog (skipped): {missing}")

    count = upsert_pricing(args.db, pricing)
    print(f"Registered/updated {count} OpenRouter model(s) in {Path(args.db).expanduser()}")
    for mid in model_ids:
        if mid in pricing:
            prompt_per_token, completion_per_token = pricing[mid]
            print(
                f"  {mid}: prompt ${prompt_per_token * 1_000_000:.6g}/1M, "
                f"completion ${completion_per_token * 1_000_000:.6g}/1M"
            )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
