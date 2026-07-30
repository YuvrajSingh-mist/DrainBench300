"""Pytest coverage for dataset-backed batch command building."""

from __future__ import annotations

import json
import sys
from types import SimpleNamespace

import pytest

from DailyBench import task_batch


def test_build_run_command_contains_selection_config(tmp_path) -> None:
    """The per-task CLI command built for a batch run includes the assigned proxy port, step budget, and prompt."""
    parser = task_batch.build_parser()
    args = parser.parse_args(
        [
            "--bucket", "easy",
            "--app", "gmail",
            "--serial", "device-1",
            "--llm-upstream-base", "http://mini2:8081/v1",
            "--model", "demo-model",
            "--no-screen-record",
        ]
    )
    task = {"bucket": "easy", "app_slug": "gmail", "task_number_within_app": 1, "day": 1}
    command, label = task_batch.build_run_command(args, task, "Check inbox", 8123)
    assert command[0] == sys.executable
    assert "--llm-proxy-port" in command
    assert "8123" in command
    assert "50" in command
    assert "--no-stream" not in command
    assert "Check inbox" == command[-1]
    assert "--out-dir" not in command


def test_parse_vars_and_skip_unresolved() -> None:
    """parse_vars turns `key=value` CLI args into a plain dict of placeholder substitutions."""
    assert task_batch.parse_vars(["sender=alice", "contact=bob"]) == {"sender": "alice", "contact": "bob"}


def test_default_steps_is_fixed_fairness_budget() -> None:
    """The default --steps budget is a fixed 50, so every task in a batch gets the same fairness budget."""
    parser = task_batch.build_parser()
    args = parser.parse_args([])
    assert args.steps == 50


def test_default_repeats_is_one() -> None:
    """--repeats defaults to 1 (opt-in): runs are already deterministic at temperature=0, so repeating by default adds no value."""
    parser = task_batch.build_parser()
    args = parser.parse_args([])
    assert args.repeats == 1


def test_build_run_command_omits_rep_suffix_when_repeats_is_one(tmp_path) -> None:
    """With the default repeats_total=1, the run label has no '-repNN' suffix at all."""
    parser = task_batch.build_parser()
    args = parser.parse_args(
        [
            "--serial", "device-1",
            "--llm-upstream-base", "http://mini2:8081/v1",
            "--model", "demo-model",
        ]
    )
    task = {"bucket": "easy", "app_slug": "gmail", "task_number_within_app": 1, "day": 1}
    command, label = task_batch.build_run_command(args, task, "Check inbox", 8090)
    assert label == "day1--easy-gmail-001"
    assert command[command.index("--label") + 1] == label


def test_build_run_command_labels_by_repeat_index_when_repeats_requested(tmp_path) -> None:
    """When --repeats is explicitly requested, each repeat gets a distinct, zero-padded '-repNN' suffix."""
    parser = task_batch.build_parser()
    args = parser.parse_args(
        [
            "--serial", "device-1",
            "--llm-upstream-base", "http://mini2:8081/v1",
            "--model", "demo-model",
        ]
    )
    task = {"bucket": "easy", "app_slug": "gmail", "task_number_within_app": 1, "day": 1}
    command_rep1, label1 = task_batch.build_run_command(args, task, "Check inbox", 8090, 1, 2)
    command_rep2, label2 = task_batch.build_run_command(args, task, "Check inbox", 8091, 2, 2)
    assert label1 == "day1--easy-gmail-001-rep01"
    assert label2 == "day1--easy-gmail-001-rep02"


def test_build_run_command_defaults_to_no_tracing_and_no_trajectory(tmp_path) -> None:
    """By default the built command has no --tracing flag and passes --save-trajectory none explicitly."""
    parser = task_batch.build_parser()
    args = parser.parse_args(
        [
            "--serial", "device-1",
            "--llm-upstream-base", "http://mini2:8081/v1",
            "--model", "demo-model",
        ]
    )
    task = {"bucket": "easy", "app_slug": "gmail", "task_number_within_app": 1, "day": 1}
    command, label = task_batch.build_run_command(args, task, "Check inbox", 8090)
    assert "--tracing" not in command
    assert command[command.index("--save-trajectory") + 1] == "none"


def test_build_run_command_includes_tracing_and_trajectory_when_requested(tmp_path) -> None:
    """--tracing and --save-trajectory step both flow straight through into the invocation."""
    parser = task_batch.build_parser()
    args = parser.parse_args(
        [
            "--serial", "device-1",
            "--llm-upstream-base", "http://mini2:8081/v1",
            "--model", "demo-model",
            "--tracing",
            "--save-trajectory", "step",
        ]
    )
    task = {"bucket": "easy", "app_slug": "gmail", "task_number_within_app": 1, "day": 1}
    command, label = task_batch.build_run_command(args, task, "Check inbox", 8090)
    assert "--tracing" in command
    assert command[command.index("--save-trajectory") + 1] == "step"


def test_build_run_command_forwards_phoenix_flags_only_when_provided() -> None:
    """--phoenix-url/--phoenix-project flow through to the child invocation only when explicitly set."""
    parser = task_batch.build_parser()
    bare_args = parser.parse_args(["--serial", "device-1", "--llm-upstream-base", "http://mini2:8081/v1", "--model", "m"])
    task = {"bucket": "easy", "app_slug": "gmail", "task_number_within_app": 1, "day": 1}
    bare_command, label = task_batch.build_run_command(bare_args, task, "Check inbox", 8090)
    assert "--phoenix-url" not in bare_command
    assert "--phoenix-project" not in bare_command

    configured_args = parser.parse_args(
        [
            "--serial", "device-1",
            "--llm-upstream-base", "http://mini2:8081/v1",
            "--model", "m",
            "--phoenix-url", "http://localhost:6006",
            "--phoenix-project", "DailyBench",
        ]
    )
    configured_command, _ = task_batch.build_run_command(configured_args, task, "Check inbox", 8090)
    assert configured_command[configured_command.index("--phoenix-url") + 1] == "http://localhost:6006"
    assert configured_command[configured_command.index("--phoenix-project") + 1] == "DailyBench"


def test_main_runs_each_task_once_by_default(monkeypatch, tmp_path) -> None:
    """Without --repeats, main() invokes DailyBench_runner exactly once per task, with no '-repNN' label suffix."""
    dataset = {
        "tasks": [
            {
                "task_id": "easy__gmail__001",
                "bucket": "easy",
                "app_slug": "gmail",
                "task_number_within_app": 1,
                "prompt_text": "Check inbox",
                "placeholders": [],
            }
        ]
    }
    dataset_path = tmp_path / "dataset.json"
    dataset_path.write_text(json.dumps(dataset))

    calls: list[list[str]] = []

    def fake_run(command, check=False, **kwargs):
        # capture_sample()'s pre-batch device snapshot shells out via "adb ... shell dumpsys ...";
        # only the DailyBench_runner invocations (python commands) are what these tests assert on.
        if command[0] != "adb":
            calls.append(command)
        return SimpleNamespace(returncode=0, stdout="")

    monkeypatch.setattr(task_batch.subprocess, "run", fake_run)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "task_batch.py",
            "--dataset", str(dataset_path),
            "--bucket", "easy",
            "--app", "gmail",
            "--serial", "device-1",
            "--llm-upstream-base", "http://mini2:8081/v1",
            "--model", "demo-model",
            "--cooldown-seconds", "0",
        ],
    )
    assert task_batch.main() == 0
    assert len(calls) == 1
    assert calls[0][calls[0].index("--label") + 1] == "open-ended--easy-gmail-001"


def test_main_runs_each_task_repeats_times(monkeypatch, tmp_path) -> None:
    """main() invokes DailyBench_runner --repeats times per selected task, each with a bumped proxy port and rep label."""
    dataset = {
        "tasks": [
            {
                "task_id": "easy__gmail__001",
                "bucket": "easy",
                "app_slug": "gmail",
                "task_number_within_app": 1,
                "prompt_text": "Check inbox",
                "placeholders": [],
            }
        ]
    }
    dataset_path = tmp_path / "dataset.json"
    dataset_path.write_text(json.dumps(dataset))

    calls: list[list[str]] = []

    def fake_run(command, check=False, **kwargs):
        # capture_sample()'s pre-batch device snapshot shells out via "adb ... shell dumpsys ...";
        # only the DailyBench_runner invocations (python commands) are what these tests assert on.
        if command[0] != "adb":
            calls.append(command)
        return SimpleNamespace(returncode=0, stdout="")

    monkeypatch.setattr(task_batch.subprocess, "run", fake_run)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "task_batch.py",
            "--dataset", str(dataset_path),
            "--bucket", "easy",
            "--app", "gmail",
            "--serial", "device-1",
            "--llm-upstream-base", "http://mini2:8081/v1",
            "--model", "demo-model",
            "--repeats", "2",
            "--cooldown-seconds", "0",
        ],
    )
    assert task_batch.main() == 0
    assert len(calls) == 2
    labels = [command[command.index("--label") + 1] for command in calls]
    assert labels == ["open-ended--easy-gmail-001-rep01", "open-ended--easy-gmail-001-rep02"]
    ports = [command[command.index("--llm-proxy-port") + 1] for command in calls]
    assert ports == ["8090", "8091"]


def test_task_timeout_seconds_is_per_bucket_tier() -> None:
    """Easy gets 300s (5 min), medium gets 1000s, hard gets 1800s (30 min)."""
    assert task_batch.task_timeout_seconds({"bucket": "easy"}) == task_batch.EASY_TASK_TIMEOUT_SECONDS
    assert task_batch.task_timeout_seconds({"bucket": "medium"}) == task_batch.MEDIUM_TASK_TIMEOUT_SECONDS
    assert task_batch.task_timeout_seconds({"bucket": "hard"}) == task_batch.HARD_TASK_TIMEOUT_SECONDS
    assert task_batch.task_timeout_seconds({"bucket": "hard-deterministic"}) == task_batch.HARD_TASK_TIMEOUT_SECONDS
    assert task_batch.task_timeout_seconds({"bucket": "open-ended"}) == task_batch.HARD_TASK_TIMEOUT_SECONDS


def test_build_run_command_always_adds_task_timeout_flag() -> None:
    """--task-timeout is always added to the child command (every bucket gets an explicit timeout now)."""
    parser = task_batch.build_parser()
    args = parser.parse_args(
        ["--serial", "device-1", "--llm-upstream-base", "http://mini2:8081/v1", "--model", "m"]
    )
    easy_task = {"bucket": "easy", "app_slug": "gmail", "task_number_within_app": 1, "day": 1}
    medium_task = {"bucket": "medium", "app_slug": "gmail", "task_number_within_app": 1, "day": 1}
    easy_command, _ = task_batch.build_run_command(args, easy_task, "Check inbox", 8090)
    medium_command, _ = task_batch.build_run_command(args, medium_task, "Check inbox", 8090)
    assert "--task-timeout" in easy_command
    assert easy_command[easy_command.index("--task-timeout") + 1] == str(task_batch.EASY_TASK_TIMEOUT_SECONDS)
    assert medium_command[medium_command.index("--task-timeout") + 1] == str(task_batch.MEDIUM_TASK_TIMEOUT_SECONDS)


def test_load_ask_user_facts_returns_empty_dict_for_missing_file(tmp_path) -> None:
    """A missing --ask-user-facts file is fine (e.g. a DETERMINISTIC-only selection) - no crash."""
    assert task_batch.load_ask_user_facts(str(tmp_path / "does-not-exist.json")) == {}


def test_load_ask_user_facts_reads_the_task_id_keyed_mapping(tmp_path) -> None:
    """The facts file is a plain {task_id: relevant_information} JSON mapping."""
    facts_path = tmp_path / "ask_user_facts.json"
    facts_path.write_text(json.dumps({"hard__calendar__003": "The appointment is on 2026-08-05 at 3:30 PM."}))
    assert task_batch.load_ask_user_facts(str(facts_path)) == {"hard__calendar__003": "The appointment is on 2026-08-05 at 3:30 PM."}


def test_build_run_command_injects_ask_user_context_for_ask_user_tasks_only() -> None:
    """Only a Hard task tagged ahi='ASK USER' gets --ask-user-context auto-filled from the facts
    mapping (looked up by task_id) - DETERMINISTIC and Easy/Medium tasks never get the flag."""
    parser = task_batch.build_parser()
    args = parser.parse_args(
        ["--serial", "device-1", "--llm-upstream-base", "http://mini2:8081/v1", "--model", "m"]
    )
    ask_user_task = {"bucket": "hard", "app_slug": "calendar", "task_number_within_app": 3, "task_id": "hard__calendar__003", "ahi": "ASK USER"}
    deterministic_task = {"bucket": "hard", "app_slug": "maps-telegram", "task_number_within_app": 1, "task_id": "hard__maps-telegram__001", "ahi": "DETERMINISTIC"}
    facts = {"hard__calendar__003": "The appointment is on 2026-08-05 at 3:30 PM."}

    ask_user_command, _ = task_batch.build_run_command(args, ask_user_task, "Book it", 8090, ask_user_facts=facts)
    deterministic_command, _ = task_batch.build_run_command(args, deterministic_task, "Find it", 8090, ask_user_facts=facts)

    assert "--ask-user-context" in ask_user_command
    assert ask_user_command[ask_user_command.index("--ask-user-context") + 1] == "The appointment is on 2026-08-05 at 3:30 PM."
    assert "--ask-user-context" not in deterministic_command


def test_build_run_command_warns_and_passes_empty_context_when_fact_missing(capsys) -> None:
    """An ASK USER task absent from the facts mapping still runs (empty context, not a crash) but prints a warning."""
    parser = task_batch.build_parser()
    args = parser.parse_args(
        ["--serial", "device-1", "--llm-upstream-base", "http://mini2:8081/v1", "--model", "m"]
    )
    task = {"bucket": "hard", "app_slug": "calendar", "task_number_within_app": 3, "task_id": "hard__calendar__003", "ahi": "ASK USER"}

    command, _ = task_batch.build_run_command(args, task, "Book it", 8090, ask_user_facts={})

    assert command[command.index("--ask-user-context") + 1] == ""
    assert "no entry in" in capsys.readouterr().out


def test_is_transient_failure_true_only_for_early_dropped_request_errors(tmp_path) -> None:
    """A short-lived run whose reason matches a known transient LLM-infra error is flagged for retry;
    a real multi-step failure, or a success, is not."""
    transient_dir = tmp_path / "transient"
    transient_dir.mkdir()
    (transient_dir / "output.json").write_text(json.dumps({"success": False, "steps": 2, "reason": "Error: Request timed out."}))
    assert task_batch.is_transient_failure(transient_dir) is True

    real_failure_dir = tmp_path / "real_failure"
    real_failure_dir.mkdir()
    (real_failure_dir / "output.json").write_text(
        json.dumps({"success": False, "steps": 28, "reason": "mobilerun agent raised: Operation timed out after 1000.0 seconds."})
    )
    assert task_batch.is_transient_failure(real_failure_dir) is False

    success_dir = tmp_path / "success"
    success_dir.mkdir()
    (success_dir / "output.json").write_text(json.dumps({"success": True, "steps": 2, "reason": "Empty response content"}))
    assert task_batch.is_transient_failure(success_dir) is False

    assert task_batch.is_transient_failure(None) is False
    assert task_batch.is_transient_failure(tmp_path / "does-not-exist") is False


def test_find_run_dir_globs_for_label_match_under_runs() -> None:
    """find_run_dir locates the run folder under runs/<date-time>/<label>/."""
    (task_batch.Path("runs") / "2026-07-30-090000" / "easy-gmail-001").mkdir(parents=True, exist_ok=True)
    (task_batch.Path("runs") / "2026-07-30-091500" / "easy-gmail-001").mkdir(parents=True, exist_ok=True)
    found = task_batch.find_run_dir("easy-gmail-001")
    assert found == task_batch.Path("runs") / "2026-07-30-091500" / "easy-gmail-001"
    assert task_batch.find_run_dir("no-such-label") is None
