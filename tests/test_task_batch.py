"""Pytest coverage for dataset-backed batch command building."""

from __future__ import annotations

import sys

from drainbench import task_batch


def test_build_run_command_contains_selection_config(tmp_path) -> None:
    parser = task_batch.build_parser()
    args = parser.parse_args(
        [
            "--bucket", "easy",
            "--app", "gmail",
            "--serial", "device-1",
            "--llm-upstream-base", "http://mini2:8081/v1",
            "--model", "demo-model",
            "--out-dir", str(tmp_path),
            "--no-screen-record",
        ]
    )
    task = {"bucket": "easy", "app_slug": "gmail", "task_number_within_app": 1}
    command = task_batch.build_run_command(args, task, "Check inbox", 8123)
    assert command[0] == sys.executable
    assert "--llm-proxy-port" in command
    assert "8123" in command
    assert "50" in command
    assert "--no-stream" not in command
    assert "Check inbox" == command[-1]


def test_parse_vars_and_skip_unresolved() -> None:
    assert task_batch.parse_vars(["sender=alice", "contact=bob"]) == {"sender": "alice", "contact": "bob"}


def test_default_steps_is_fixed_fairness_budget() -> None:
    parser = task_batch.build_parser()
    args = parser.parse_args([])
    assert args.steps == 50
