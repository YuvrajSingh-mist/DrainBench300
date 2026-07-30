"""Pytest coverage for the OpenAI-compatible proxy/logger's streaming response handling."""

from __future__ import annotations

from openai_proxy_logger import (
    merge_stream_events,
    parse_response_payload,
    parse_sse_events,
    with_stream_usage_requested,
)


def test_with_stream_usage_requested_leaves_non_streaming_payload_untouched() -> None:
    """Non-streaming requests are returned as the same object, since they already report usage normally."""
    payload = {"model": "m", "messages": [], "stream": False}
    assert with_stream_usage_requested(payload) is payload


def test_with_stream_usage_requested_adds_include_usage_for_streamed_payload() -> None:
    """A streamed request gets stream_options.include_usage injected without mutating the original payload."""
    payload = {"model": "m", "messages": [], "stream": True}
    updated = with_stream_usage_requested(payload)
    assert updated is not payload
    assert updated["stream_options"] == {"include_usage": True}
    # original payload is untouched
    assert "stream_options" not in payload


def test_with_stream_usage_requested_preserves_existing_stream_options() -> None:
    """A caller who already set stream_options (even disabling include_usage) has that choice respected, not overridden."""
    payload = {"stream": True, "stream_options": {"include_usage": False, "other": 1}}
    updated = with_stream_usage_requested(payload)
    # explicit user choice to disable usage reporting is respected
    assert updated["stream_options"] == {"include_usage": False, "other": 1}


# OpenRouter's real SSE format: comment lines first, then data chunks
OPENROUTER_SSE = (
    ": OPENROUTER PROCESSING\n\n"
    ": OPENROUTER PROCESSING\n\n"
    'data: {"id":"gen-abc","object":"chat.completion.chunk","model":"qwen/qwen3.6-plus",'
    '"choices":[{"index":0,"delta":{"content":"Hello"},"finish_reason":null}]}\n\n'
    'data: {"id":"gen-abc","object":"chat.completion.chunk","model":"qwen/qwen3.6-plus",'
    '"choices":[{"index":0,"delta":{},"finish_reason":"stop"}]}\n\n'
    'data: {"id":"gen-abc","object":"chat.completion.chunk","model":"qwen/qwen3.6-plus",'
    '"choices":[],"usage":{"prompt_tokens":15,"completion_tokens":5,"total_tokens":20}}\n\n'
    "data: [DONE]\n\n"
)


def test_parse_sse_with_openrouter_comment_lines() -> None:
    """OpenRouter prepends SSE comment lines (: OPENROUTER PROCESSING) before
    data chunks. The parser must skip comments and extract usage."""
    payload = parse_response_payload(OPENROUTER_SSE.encode())
    assert payload["usage"] == {"prompt_tokens": 15, "completion_tokens": 5, "total_tokens": 20}
    assert payload["model"] == "qwen/qwen3.6-plus"


SSE_BODY_WITH_TRAILING_USAGE = (
    'data: {"choices":[{"finish_reason":null,"index":0,"delta":{"role":"assistant","content":null}}],'
    '"id":"chatcmpl-abc","model":"qwen","object":"chat.completion.chunk"}\n\n'
    'data: {"choices":[{"finish_reason":null,"index":0,"delta":{"content":"Hi"}}],'
    '"id":"chatcmpl-abc","model":"qwen","object":"chat.completion.chunk"}\n\n'
    'data: {"choices":[{"finish_reason":"length","index":0,"delta":{}}],'
    '"id":"chatcmpl-abc","model":"qwen","object":"chat.completion.chunk",'
    '"timings":{"prompt_ms":35.0,"predicted_ms":114.0,"prompt_per_second":28.0,"predicted_per_second":43.0}}\n\n'
    'data: {"choices":[],"id":"chatcmpl-abc","model":"qwen","object":"chat.completion.chunk",'
    '"usage":{"prompt_tokens":9,"completion_tokens":5,"total_tokens":14}}\n\n'
    "data: [DONE]\n\n"
)


def test_parse_sse_events_skips_done_and_blank_lines() -> None:
    """A real llama.cpp SSE body yields exactly its 4 JSON chunks, with `[DONE]` and blank separators dropped."""
    events = parse_sse_events(SSE_BODY_WITH_TRAILING_USAGE)
    assert len(events) == 4
    assert events[0]["id"] == "chatcmpl-abc"


def test_parse_sse_events_skips_malformed_json_chunk() -> None:
    """A truncated/corrupt chunk mid-stream is dropped without breaking parsing of the surrounding valid chunks."""
    body = 'data: {"not": "json"\n\ndata: {"ok": true}\n\ndata: [DONE]\n\n'
    events = parse_sse_events(body)
    assert events == [{"ok": True}]


def test_merge_stream_events_combines_usage_and_timings_from_different_chunks() -> None:
    """timings (on the finish_reason chunk) and usage (on a later, separate chunk) are merged into one payload."""
    events = parse_sse_events(SSE_BODY_WITH_TRAILING_USAGE)
    merged = merge_stream_events(events)
    assert merged["usage"] == {"prompt_tokens": 9, "completion_tokens": 5, "total_tokens": 14}
    assert merged["timings"]["prompt_ms"] == 35.0
    assert merged["choices"][0]["finish_reason"] == "length"
    assert merged["id"] == "chatcmpl-abc"
    assert merged["model"] == "qwen"


def test_merge_stream_events_with_no_events_returns_empty_dict() -> None:
    """Merging zero SSE events yields {}, letting the caller skip logging rather than write a null-filled entry."""
    assert merge_stream_events([]) == {}


def test_parse_response_payload_recovers_usage_from_streamed_body() -> None:
    """End-to-end: raw SSE response bytes in, a completion-shaped dict with real usage/timings out."""
    payload = parse_response_payload(SSE_BODY_WITH_TRAILING_USAGE.encode())
    assert payload["usage"]["total_tokens"] == 14
    assert payload["timings"]["predicted_ms"] == 114.0


def test_parse_response_payload_handles_plain_json_body() -> None:
    """A non-streamed, plain-JSON response body is parsed the same way it was before the SSE fix."""
    body = b'{"usage":{"total_tokens":3},"timings":{"prompt_ms":1.0},"id":"x","model":"m","choices":[{"finish_reason":"stop"}]}'
    payload = parse_response_payload(body)
    assert payload["usage"]["total_tokens"] == 3
    assert payload["choices"][0]["finish_reason"] == "stop"


def test_parse_response_payload_returns_empty_dict_for_invalid_body() -> None:
    """Garbage or empty response bodies degrade to {} instead of raising.
    The proxy now always logs (even with {}), adding a response_body_preview for debugging."""
    assert parse_response_payload(b"not json at all") == {}
    assert parse_response_payload(b"") == {}
