"""Pytest coverage for markdown task parsing and selection."""

from __future__ import annotations

from drainbench.task_dataset import parse_tasks_markdown, render_prompt, select_tasks


def test_parse_tasks_markdown_extracts_structure() -> None:
    markdown = """
## Easy (2)

**Gmail**
1. Star the latest email from [sender]
2. Delete the most recent promotional email

## Hard-deterministic (1)

1. *[Gmail + Notes]* Find a bill and save the amount to a note
""".strip()
    dataset = parse_tasks_markdown(markdown, source_path="docs/tasks.md")
    assert dataset["task_count"] == 3
    assert dataset["bucket_counts"]["easy"] == 2
    assert dataset["tasks"][0]["app_slug"] == "gmail"
    assert dataset["tasks"][0]["placeholders"] == ["sender"]
    assert dataset["tasks"][0]["prompt_template"] == "Star the latest email from {{ sender }}"
    assert dataset["tasks"][2]["is_cross_app"] is True


def test_select_and_render_prompt() -> None:
    dataset = {
        "tasks": [
            {"task_id": "easy__gmail__001", "bucket": "easy", "app_slug": "gmail", "prompt_text": "Check [thing]", "placeholders": ["thing"]},
            {"task_id": "medium__youtube__001", "bucket": "medium", "app_slug": "youtube", "prompt_text": "Play it", "placeholders": []},
        ]
    }
    selected = select_tasks(dataset, bucket="easy", app="gmail")
    assert len(selected) == 1
    assert render_prompt(selected[0], {"thing": "mail"}) == "Check mail"
