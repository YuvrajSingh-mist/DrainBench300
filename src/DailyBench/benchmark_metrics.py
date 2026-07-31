"""MobileWorld-style benchmark metrics (arXiv:2512.19432, MCP metric excluded).

Implements the Success Rate, Average Completion Steps, Average User Queries, and
User Interaction Quality (UIQ) metrics from MobileWorld Section 4.2, operating on
per-run records produced by the DailyBench harness. The paper's Average MCP Tool
Calls metric is deliberately excluded.

A "record" is a dict with at least these fields (produced by
``scripts/dailybench_report.py``):

    success: bool          # s_i in the paper: 1 if the task fully completed
    steps: int             # t_i: number of action steps in the trajectory
    ask_user_calls: int    # c_i: number of ask_user invocations
    is_interaction: bool   # True for ASK USER (agent-user interaction) tasks

Formulas (Section 4.2):

    SR            = (1/N) * sum(s_i)
    Ave. Steps    = (1/N) * sum(t_i)
    Ave. Queries  = (1/|I_interact|) * sum_{i in I_interact}(c_i)
    UIQ           = sum_{i in I_interact}(q_i) / (|I_interact| + |I_triggered|)
      where q_i   = s_i / c_i if c_i > 0 else 0
      and I_triggered = non-interaction tasks that invoked ask_user >= 1 time

UIQ rewards success with few clarification queries and penalizes both failing to
ask on interaction tasks (c_i = 0 -> q_i = 0, still counted in the denominator)
and asking unnecessarily on non-interaction tasks (adds to I_triggered).
"""

from __future__ import annotations

from typing import Any, Iterable

Record = dict[str, Any]


def _mean(values: Iterable[float]) -> float:
    """Mean of a sequence; 0.0 when empty or all-None."""
    values = [float(value) for value in values if value is not None]
    return sum(values) / len(values) if values else 0.0


def success_rate(records: Iterable[Record]) -> float:
    """Success Rate: the proportion of tasks fully completed (formula 1)."""
    return _mean(1.0 if record["success"] else 0.0 for record in records)


def avg_steps(records: Iterable[Record]) -> float:
    """Average Completion Steps across all trajectories (formula 3)."""
    return _mean(record.get("steps", 0) for record in records)


def avg_user_queries(records: Iterable[Record]) -> float:
    """Average User Queries over interaction tasks only (formula 4).

    Non-interaction tasks are excluded from the denominator, matching the paper.
    """
    interaction = [record for record in records if record["is_interaction"]]
    return _mean(record.get("ask_user_calls", 0) for record in interaction)


def user_interaction_quality(records: Iterable[Record]) -> float:
    """User Interaction Quality (formulas 5-6).

    ``q_i = s_i / c_i`` for interaction task ``i`` (0 when it never asked), summed
    over interaction tasks and divided by the number of interaction tasks plus the
    number of non-interaction tasks that nevertheless invoked ``ask_user``.
    """
    interaction = [record for record in records if record["is_interaction"]]
    triggered = [
        record
        for record in records
        if not record["is_interaction"] and (record.get("ask_user_calls") or 0) > 0
    ]
    numerator = 0.0
    for record in interaction:
        queries = record.get("ask_user_calls") or 0
        if queries > 0:
            numerator += (1.0 if record["success"] else 0.0) / queries
    denominator = len(interaction) + len(triggered)
    return numerator / denominator if denominator else 0.0
