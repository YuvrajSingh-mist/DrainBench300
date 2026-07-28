#!/usr/bin/env python3
"""Validate Mobilerun provider/model combinations before a benchmark run."""

from __future__ import annotations

import argparse
import sys
from urllib.parse import urlparse


OPENAI_PROVIDER_NAMES = {"openai", "openairesponses"}
OPENAI_LIKE_PROVIDER_NAMES = {
    "openai compatible",
    "openai-compatible",
    "openai_compatible",
    "openai like",
    "openai-like",
    "openailike",
}
OLLAMA_PROVIDER_NAMES = {"ollama"}

OPENAI_MODEL_PREFIXES = (
    "gpt-",
    "o1",
    "o3",
    "o4",
    "chatgpt-",
    "text-",
    "davinci",
    "curie",
    "babbage",
    "ada",
)

LOCAL_MODEL_HINTS = (
    "qwen",
    "llama",
    "gemma",
    "mistral",
    "phi",
    "deepseek",
    "glm",
    "vicuna",
)


def normalize_provider(name: str) -> str:
    """Normalize a provider label for stable comparison."""
    return " ".join(name.strip().lower().replace("_", " ").split())


def looks_like_openai_model(model: str) -> bool:
    """Return whether the model name looks like an official OpenAI model."""
    value = model.strip().lower()
    return value.startswith(OPENAI_MODEL_PREFIXES)


def looks_like_local_model(model: str) -> bool:
    """Return whether the model name looks like a local OSS model."""
    value = model.strip().lower()
    return any(hint in value for hint in LOCAL_MODEL_HINTS)


def classify_endpoint(base_url: str | None, api_base: str | None) -> str:
    """Classify the target endpoint family from the provided base URL."""
    url = api_base or base_url or ""
    if not url:
        return "unknown"

    parsed = urlparse(url)
    host = (parsed.hostname or "").lower()
    path = (parsed.path or "").lower()

    if host.endswith("api.openai.com"):
        return "openai"
    if host.endswith("11434") or ":11434" in url or host in {"localhost", "127.0.0.1"} and path == "":
        return "unknown"
    if "11434" in url:
        return "ollama"
    if path.endswith("/v1") or "/v1/" in path:
        return "openai_like"
    return "unknown"


def fail(message: str) -> int:
    """Print one guard failure and return the standard exit code."""
    print(f"provider-guard: {message}", file=sys.stderr)
    return 2


def main() -> int:
    """Validate one provider/model/endpoint combination from CLI args."""
    parser = argparse.ArgumentParser(
        description="Reject common Mobilerun provider/model mismatches."
    )
    parser.add_argument("--provider", required=True)
    parser.add_argument("--model", required=True)
    parser.add_argument("--base-url")
    parser.add_argument("--api-base")
    args = parser.parse_args()

    provider = normalize_provider(args.provider)
    model = args.model.strip()
    endpoint = classify_endpoint(args.base_url, args.api_base)

    if provider in OPENAI_PROVIDER_NAMES:
        if looks_like_local_model(model):
            return fail(
                f"provider '{args.provider}' is wrong for local/non-OpenAI model "
                f"'{model}'. Use 'OpenAI Compatible' / 'OpenAILike' instead."
            )
        if endpoint == "openai_like":
            return fail(
                f"endpoint '{args.api_base or args.base_url}' looks OpenAI-compatible "
                f"rather than the real OpenAI API. Use 'OpenAI Compatible' / "
                f"'OpenAILike' instead of '{args.provider}'."
            )

    if provider in OPENAI_LIKE_PROVIDER_NAMES:
        if looks_like_openai_model(model) and endpoint == "openai":
            print(
                "provider-guard: note: this looks like the real OpenAI API; "
                "plain 'OpenAI' may be a cleaner choice here.",
                file=sys.stderr,
            )

    if provider in OLLAMA_PROVIDER_NAMES:
        url = args.base_url or args.api_base or ""
        if "11434" not in url and endpoint == "openai_like":
            return fail(
                f"provider '{args.provider}' expects an Ollama endpoint, but "
                f"'{url}' looks like an OpenAI-compatible '/v1' server."
            )

    print(
        f"provider-guard: OK - provider={args.provider}, model={model}, "
        f"endpoint_type={endpoint}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
