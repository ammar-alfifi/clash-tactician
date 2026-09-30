"""Formatting and time helpers."""

from __future__ import annotations

from app.core.formatting import normalize_tag, percent, progress_bar, stars
from app.core.timeutil import humanize_seconds, parse_coc_time, remaining_until


def test_normalize_tag_variants():
    assert normalize_tag("#abc123") == "#ABC123"
    assert normalize_tag("abc123") == "#ABC123"
    assert normalize_tag("  #9py2L  ") == "#9PY2L"
    link = "https://link.clashofclans.com/en?action=OpenPlayerProfile&tag=ABC123"
    assert normalize_tag(link) == "#ABC123"
    assert normalize_tag("O0O") == "#000"
    assert normalize_tag("!!!") is None
    assert normalize_tag(None) is None


def test_progress_and_percent():
    assert progress_bar(0, 10, width=5) == "▱▱▱▱▱"
    assert progress_bar(10, 10, width=5) == "▰▰▰▰▰"
    assert progress_bar(5, 10, width=10) == "▰▰▰▰▰▱▱▱▱▱"
    assert progress_bar(1, 0) == "—"
    assert percent(1, 4) == "25%"
    assert percent(0, 0) == "0%"


def test_stars():
    assert stars(0) == "✩"
    assert stars(2) == "⭐⭐"
    assert stars(9) == "⭐⭐⭐"


def test_humanize_seconds():
    assert humanize_seconds(0) == "انتهى"
    assert humanize_seconds(90) == "1د"
    assert humanize_seconds(3600) == "1س"
    assert humanize_seconds(90000).startswith("1ي")


def test_parse_coc_time_and_remaining():
    parsed = parse_coc_time("20240101T120000.000Z")
    assert parsed is not None and parsed.year == 2024
    assert parse_coc_time("bad") is None
    assert remaining_until(None) == "—"
