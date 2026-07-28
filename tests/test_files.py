"""Pytest coverage for filesystem helpers."""

from __future__ import annotations

from drainbench.files import make_run_dir, slugify, write_json, write_text


def test_slugify_and_make_run_dir(tmp_path) -> None:
    assert slugify(" Search Weather! ") == "search-weather"
    run_dir = make_run_dir(str(tmp_path), "Search Weather!")
    assert run_dir.is_dir()
    assert run_dir.name.endswith("-search-weather")


def test_write_json_and_text(tmp_path) -> None:
    json_path = tmp_path / "meta.json"
    text_path = tmp_path / "output.txt"
    write_json(json_path, {"a": 1})
    write_text(text_path, "done")
    assert '"a": 1' in json_path.read_text()
    assert text_path.read_text() == "done"
