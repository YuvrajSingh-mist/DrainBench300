"""Pytest coverage for markdown task parsing, selection, and placeholder rendering."""

from __future__ import annotations

import json

from DailyBench.task_dataset import (
    extract_inline_app,
    find_apps_in_text,
    merge_ask_user_facts,
    parse_tasks_markdown,
    render_prompt,
    select_tasks,
)


def test_parse_tasks_markdown_extracts_structure() -> None:
    """Bucket headers, app names, cross-app tags, and placeholders are all parsed from markdown."""
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


def test_extract_inline_app_finds_leading_app_name() -> None:
    """A leading 'On/In/Using/Open/Go to <App>,' or '<App> and' clause yields the app name."""
    assert extract_inline_app("On Gmail, summarize the last 3 unread emails") == "Gmail"
    assert extract_inline_app("In Google Maps, compare the ETA") == "Google Maps"
    assert extract_inline_app("Open Chrome and find yesterday's page") == "Chrome"
    assert extract_inline_app("Go to Clock and set a 10-minute timer") == "Clock"


def test_extract_inline_app_finds_trailing_app_name() -> None:
    """A trailing ', on <App>' clause yields the app name when there's no leading match."""
    assert extract_inline_app("Create a note titled '[X]', on Notes") == "Notes"
    assert extract_inline_app("Skip to the next track, on Music") == "Music"


def test_extract_inline_app_returns_none_when_no_app_named() -> None:
    """A sentence with neither a leading nor trailing app clause yields None."""
    assert extract_inline_app("Reply to the latest email with a short update") is None


def test_find_apps_in_text_detects_multiple_apps_in_order() -> None:
    """A composite task mentioning several apps returns all of them, in first-appearance order, deduplicated."""
    text = "Get directions to the airport on Maps, check the ETA, and message Dad on Telegram with the arrival time"
    assert find_apps_in_text(text) == ["Google Maps", "Telegram"]


def test_find_apps_in_text_normalizes_short_aliases_to_canonical_names() -> None:
    """Short aliases (Maps/Drive/Photos/Search) resolve to their full canonical app name."""
    assert find_apps_in_text("Upload it to Drive") == ["Google Drive"]
    assert find_apps_in_text("Look it up via Search") == ["Google Search"]


def test_parse_tasks_markdown_handles_the_21_day_schedule_format() -> None:
    """Inline `- *Easy/Medium (Npt):*` bullets (no **App** heading) parse into per-app easy/medium tasks."""
    markdown = """
## The 21-Day Schedule

### Day 1 (2 apps active)

- *Easy (1pt):* In Gmail, check how many unread emails are in the inbox
- *Medium (3pt):* Open Chrome and find yesterday's page about [topic] in history, summarize what it said, and reopen it
- *Easy (1pt):* Skip to the next track, on Music

### Day 2 (1 app active)

- *Medium (3pt):* Using Gmail, find all emails with 'urgent' in the subject, count them
""".strip()
    dataset = parse_tasks_markdown(markdown, source_path="benchmarks/dailyBench-600/tasks.md")
    assert dataset["task_count"] == 4
    assert dataset["bucket_counts"] == {"easy": 2, "medium": 2}

    gmail_easy = next(t for t in dataset["tasks"] if t["task_id"] == "easy__gmail__001")
    assert gmail_easy["app"] == "Gmail"
    # prompt_text keeps the full natural sentence, including the app clause - only the
    # app/app_slug metadata is derived from it, the prompt itself is never rewritten.
    assert gmail_easy["prompt_text"] == "In Gmail, check how many unread emails are in the inbox"

    music_easy = next(t for t in dataset["tasks"] if t["app_slug"] == "music")
    assert music_easy["app"] == "Music"

    gmail_medium = next(t for t in dataset["tasks"] if t["task_id"] == "medium__gmail__001")
    assert gmail_medium["app"] == "Gmail"
    assert gmail_medium["placeholders"] == []


def test_parse_tasks_markdown_handles_h3_hard_and_open_ended_headings() -> None:
    """`### Hard — ...` / `### Open-Ended ...` H3 headings resolve to the same buckets as the old H2 form."""
    markdown = """
## Limit-Testing Battery

### Hard — Deterministic Composite (2), 5pt flat

1. Get directions to [place] on Maps, check the ETA, and message [contact] on Telegram with the arrival time
2. Find all contacts with no phone number, list them, and delete them

### Open-Ended (1)

1. Find a highly-rated coffee shop nearby that's open now on Maps, then send its location to [contact] on Telegram
""".strip()
    dataset = parse_tasks_markdown(markdown, source_path="benchmarks/dailyBench-600/tasks.md")
    assert dataset["bucket_counts"] == {"hard-deterministic": 2, "open-ended": 1}

    composite = dataset["tasks"][0]
    assert composite["is_cross_app"] is True
    assert composite["cross_app_label"] == "Google Maps + Telegram"

    no_app_named = dataset["tasks"][1]
    assert no_app_named["app_slug"] == "unknown"

    open_ended = dataset["tasks"][2]
    assert open_ended["bucket"] == "open-ended"
    assert open_ended["cross_app_label"] == "Google Maps + Telegram"


def test_parse_tasks_markdown_handles_the_3day_sample_format() -> None:
    """`**[App]**` bold-bracket headers, plain `- Easy/Medium (Npt): ...` bullets (optionally with
    an inline `**[App1+App2]**` cross-app tag), and the shuffled `## Hard (...)` section with
    `**N. [App1+App2] — TAG**` headers all parse into the new schema fields."""
    markdown = """
### Day 1

**[Gmail]**
- Easy (1pt): In Gmail, star the most recent email from [sender]

**[YouTube]**
- Medium (3pt) **[YouTube+Telegram]**: Using YouTube, find the longest video in Watch Later, note its length, and message [contact] on Telegram if it's over 40 minutes

## Hard (2 tasks, shuffled order)

**1. [Google Maps+Telegram] — DETERMINISTIC**
- Check Maps for the nearest pharmacy and text [contact] the winner via Telegram

**2. [Gmail+Contacts] — ASK USER**
- Could you just forward that report over? (deliberately no file identified as 'the report' and no manager contact saved - agent must ask which report and who the manager actually is)
""".strip()
    dataset = parse_tasks_markdown(markdown, source_path="benchmarks/dailyBench-600/public.md")
    assert dataset["task_count"] == 4
    assert dataset["bucket_counts"] == {"easy": 1, "medium": 1, "hard": 2}

    gmail_easy = next(t for t in dataset["tasks"] if t["task_id"] == "easy__gmail__001")
    assert gmail_easy["difficulty"] == "easy"
    assert gmail_easy["points"] == 1
    assert gmail_easy["apps"] == ["Gmail"]
    assert gmail_easy["num_apps"] == 1
    assert gmail_easy["cross_app_required"] is False
    assert gmail_easy["ahi"] is None
    assert gmail_easy["day"] == 1

    youtube_medium = next(t for t in dataset["tasks"] if t["app_slug"] == "youtube-telegram")
    assert youtube_medium["points"] == 3
    assert youtube_medium["apps"] == ["YouTube", "Telegram"]
    assert youtube_medium["cross_app_required"] is True
    assert youtube_medium["num_apps"] == 2

    deterministic = next(t for t in dataset["tasks"] if t["task_id"] == "hard__google-maps-telegram__001")
    assert deterministic["difficulty"] == "hard"
    assert deterministic["points"] == 5
    assert deterministic["day"] is None
    assert deterministic["apps"] == ["Google Maps", "Telegram"]
    assert deterministic["ahi"] == "DETERMINISTIC"
    assert deterministic["is_ask_user"] is False
    assert deterministic["note"] is None
    assert deterministic["prompt_text"] == "Check Maps for the nearest pharmacy and text [contact] the winner via Telegram"

    ask_user = next(t for t in dataset["tasks"] if t["task_id"] == "hard__gmail-contacts__002")
    assert ask_user["ahi"] == "ASK USER"
    assert ask_user["is_ask_user"] is True
    assert ask_user["apps"] == ["Gmail", "Contacts"]
    assert ask_user["prompt_text"] == "Could you just forward that report over?"
    assert ask_user["note"] == "deliberately no file identified as 'the report' and no manager contact saved - agent must ask which report and who the manager actually is"


def test_resolve_apps_maps_a_browser_tagged_category_header_to_chrome() -> None:
    """A non-app category header tagged '(browser)' (e.g. 'Shopping & Delivery (browser)')
    resolves straight to Chrome - the only browser app in this corpus - even when the task's own
    sentence never names an app at all, or would otherwise false-positive against a generic verb
    like "Search for ..." matching the "Search" alias."""
    markdown = """
### Day 3

**[Shopping & Delivery (browser)]**
- Easy (1pt): Check the estimated restock date for wireless earbuds on Amazon
- Medium (3pt): Search for "Nike Air Jordans" and compare prices on Amazon and Nike's site
""".strip()
    dataset = parse_tasks_markdown(markdown, source_path="benchmarks/dailyBench-600/public.md")
    no_app_named, generic_verb_task = dataset["tasks"]
    assert no_app_named["apps"] == ["Chrome"]
    assert no_app_named["cross_app_required"] is False
    assert generic_verb_task["apps"] == ["Chrome"]


def test_merge_ask_user_facts_fills_in_matching_task_ids_only(tmp_path) -> None:
    """merge_ask_user_facts sets `ask_user_fact` only for task_ids present in the facts file,
    leaving every other task's field at its default None - safe to publish since public.md is a
    structural preview, not the real held-out eval (see docs/advanced-features.md)."""
    markdown = """
### Day 1

**[Gmail]**
- Easy (1pt): Star the most recent email from [sender]

## Hard (1 tasks, shuffled order)

**1. [Gmail+Contacts] — ASK USER**
- Forward the report? (deliberately no file identified - agent must ask)
""".strip()
    dataset = parse_tasks_markdown(markdown, source_path="benchmarks/dailyBench-600/public.md")
    facts_path = tmp_path / "ask_user_facts.json"
    facts_path.write_text(json.dumps({"hard__gmail-contacts__001": "The report is Q2_Budget.xlsx."}))

    merge_ask_user_facts(dataset, facts_path)

    easy_task = next(t for t in dataset["tasks"] if t["bucket"] == "easy")
    hard_task = next(t for t in dataset["tasks"] if t["bucket"] == "hard")
    assert easy_task["ask_user_fact"] is None
    assert hard_task["ask_user_fact"] == "The report is Q2_Budget.xlsx."


def test_merge_ask_user_facts_is_a_no_op_for_a_missing_file(tmp_path) -> None:
    """A missing facts file (e.g. none authored yet) leaves every task's ask_user_fact as None."""
    dataset = {"tasks": [{"task_id": "hard__gmail-contacts__001", "ask_user_fact": None}]}
    merge_ask_user_facts(dataset, tmp_path / "does-not-exist.json")
    assert dataset["tasks"][0]["ask_user_fact"] is None


def test_select_and_render_prompt() -> None:
    """select_tasks filters by bucket/app, and render_prompt substitutes the selected task's placeholder."""
    dataset = {
        "tasks": [
            {"task_id": "easy__gmail__001", "bucket": "easy", "app_slug": "gmail", "prompt_text": "Check [thing]", "placeholders": ["thing"]},
            {"task_id": "medium__youtube__001", "bucket": "medium", "app_slug": "youtube", "prompt_text": "Play it", "placeholders": []},
        ]
    }
    selected = select_tasks(dataset, bucket="easy", app="gmail")
    assert len(selected) == 1
    assert render_prompt(selected[0], {"thing": "mail"}) == "Check mail"


def test_render_prompt_replaces_multiple_distinct_placeholders() -> None:
    """A task with two different placeholders (e.g. calculator's [numberA]/[numberB]) gets both substituted."""
    task = {
        "prompt_text": "Add [numberA] and [numberB]",
        "placeholders": ["numberA", "numberB"],
    }
    assert render_prompt(task, {"numberA": "12", "numberB": "7"}) == "Add 12 and 7"


def test_render_prompt_replaces_repeated_placeholder_occurrences() -> None:
    """The same placeholder name used twice in one prompt is replaced at every occurrence."""
    task = {
        "prompt_text": "Message [contact] and cc [contact] on the reply",
        "placeholders": ["contact"],
    }
    assert render_prompt(task, {"contact": "Alice"}) == "Message Alice and cc Alice on the reply"


def test_render_prompt_leaves_unresolved_placeholder_literal() -> None:
    """A placeholder missing from the variables dict is left as literal bracket text, not blanked out."""
    task = {
        "prompt_text": "Add [numberA] and [numberB]",
        "placeholders": ["numberA", "numberB"],
    }
    assert render_prompt(task, {"numberA": "12"}) == "Add 12 and [numberB]"


def test_render_prompt_ignores_extraneous_variables() -> None:
    """Extra keys in the variables dict that the task doesn't use are ignored, not appended or errored on."""
    task = {"prompt_text": "Check [thing]", "placeholders": ["thing"]}
    assert render_prompt(task, {"thing": "mail", "unused": "value"}) == "Check mail"


def test_render_prompt_handles_placeholder_names_with_spaces() -> None:
    """Multi-word placeholder names like '[type of place]' (seen in the real dataset) resolve correctly."""
    task = {
        "prompt_text": "Find a nearby [type of place]",
        "placeholders": ["type of place"],
    }
    assert render_prompt(task, {"type of place": "coffee shop"}) == "Find a nearby coffee shop"


def test_render_prompt_with_no_placeholders_returns_text_unchanged() -> None:
    """A task with an empty placeholders list is returned verbatim regardless of the variables passed in."""
    task = {"prompt_text": "Archive the most recent email", "placeholders": []}
    assert render_prompt(task, {"anything": "ignored"}) == "Archive the most recent email"


def test_render_prompt_end_to_end_from_markdown_with_two_placeholders() -> None:
    """Parsing a cross-app, multi-placeholder task from markdown and rendering it fills in both values."""
    markdown = """
## Hard-deterministic (1)

1. *[Maps + Telegram]* Get directions to [place] and message [contact] the ETA
""".strip()
    dataset = parse_tasks_markdown(markdown, source_path="docs/tasks.md")
    selected = select_tasks(dataset, bucket="hard-deterministic")
    task = selected[0]
    assert task["placeholders"] == ["place", "contact"]
    rendered = render_prompt(task, {"place": "the airport", "contact": "Dad"})
    assert rendered == "Get directions to the airport and message Dad the ETA"
