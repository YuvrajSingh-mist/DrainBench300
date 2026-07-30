"""Pytest coverage for filesystem helpers."""

from __future__ import annotations

from pathlib import Path

from DailyBench.files import dated_out_dir, make_run_dir, slugify, write_json, write_text


def test_slugify_and_make_run_dir(tmp_path) -> None:
    """slugify normalizes a label to a filesystem-safe slug, and make_run_dir creates a dir named after the label (no timestamp prefix)."""
    assert slugify(" Search Weather! ") == "search-weather"
    run_dir = make_run_dir(str(tmp_path), "Search Weather!")
    assert run_dir.is_dir()
    assert run_dir.name == "search-weather"
    # parent is the date-time folder (YYYY-MM-DD-HHMMSS)
    assert "-" in run_dir.parent.name and len(run_dir.parent.name.split("-")) >= 4


def test_dated_out_dir_inserts_datetime_right_after_the_runs_root() -> None:
    """A `runs/...` out-dir gets a date-time stamp inserted as the segment right under `runs`."""
    result = dated_out_dir("runs/gmail/easy")
    assert result.parts[0] == "runs"
    # parts[1] is the date-time folder (e.g. "2026-07-31-000818")
    assert len(result.parts[1].split("-")) == 4  # YYYY-MM-DD-HHMMSS
    assert result.parts[2:] == ("gmail", "easy")
    result2 = dated_out_dir("runs")
    assert result2.parts[0] == "runs"
    assert len(result2.parts[1].split("-")) == 4


def test_dated_out_dir_appends_datetime_for_a_non_runs_root(tmp_path) -> None:
    """An out-dir that isn't rooted at `runs` just gets the date-time appended."""
    result = dated_out_dir(str(tmp_path))
    assert result.parent == tmp_path
    assert len(result.name.split("-")) == 4  # YYYY-MM-DD-HHMMSS


def test_write_json_and_text(tmp_path) -> None:
    """write_json/write_text create files with the expected serialized/plain contents."""
    json_path = tmp_path / "meta.json"
    text_path = tmp_path / "output.txt"
    write_json(json_path, {"a": 1})
    write_text(text_path, "done")
    assert '"a": 1' in json_path.read_text()
    assert text_path.read_text() == "done"
