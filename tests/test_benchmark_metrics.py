"""Coverage for MobileWorld-style benchmark metrics (arXiv:2512.19432, MCP excluded)."""

from __future__ import annotations

import pytest

from DailyBench.benchmark_metrics import avg_steps, avg_user_queries, success_rate, user_interaction_quality


def _rec(success: bool, steps: int = 0, ask_user_calls: int = 0, is_interaction: bool = False) -> dict:
    return {"success": success, "steps": steps, "ask_user_calls": ask_user_calls, "is_interaction": is_interaction}


def test_success_rate_overall_and_empty() -> None:
    assert success_rate([_rec(True), _rec(False), _rec(True)]) == pytest.approx(2 / 3)
    assert success_rate([]) == 0.0


def test_avg_steps_overall_and_empty() -> None:
    assert avg_steps([_rec(True, 10), _rec(False, 4), _rec(True, 1)]) == pytest.approx(5.0)
    assert avg_steps([]) == 0.0


def test_avg_user_queries_counts_interaction_tasks_only() -> None:
    records = [
        _rec(True, ask_user_calls=2, is_interaction=True),
        _rec(True, ask_user_calls=1, is_interaction=True),
        _rec(True, ask_user_calls=5, is_interaction=False),  # excluded from denominator
    ]
    assert avg_user_queries(records) == pytest.approx(1.5)
    assert avg_user_queries([]) == 0.0


def test_uiq_success_with_one_query_is_one() -> None:
    assert user_interaction_quality([_rec(True, ask_user_calls=1, is_interaction=True)]) == pytest.approx(1.0)


def test_uiq_success_with_more_queries_scores_lower() -> None:
    assert user_interaction_quality([_rec(True, ask_user_calls=2, is_interaction=True)]) == pytest.approx(0.5)


def test_uiq_failed_interaction_with_query_scores_zero() -> None:
    assert user_interaction_quality([_rec(False, ask_user_calls=1, is_interaction=True)]) == pytest.approx(0.0)


def test_uiq_interaction_that_never_asked_scores_zero() -> None:
    # q_i = 0 when c_i = 0, and the task still counts in the denominator
    assert user_interaction_quality([_rec(True, ask_user_calls=0, is_interaction=True)]) == pytest.approx(0.0)


def test_uiq_penalizes_unnecessary_ask_user_on_gui_only() -> None:
    records = [
        _rec(True, ask_user_calls=1, is_interaction=True),   # q = 1
        _rec(True, ask_user_calls=2, is_interaction=False),  # triggered -> denominator +1
    ]
    assert user_interaction_quality(records) == pytest.approx(1 / 2)


def test_uiq_empty_or_no_interaction_is_zero() -> None:
    assert user_interaction_quality([]) == 0.0
    assert user_interaction_quality([_rec(True, ask_user_calls=3, is_interaction=False)]) == 0.0
