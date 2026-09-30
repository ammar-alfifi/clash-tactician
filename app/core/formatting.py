"""Formatting helpers for tags, numbers and progress bars."""

from __future__ import annotations

import html

from app.core.timeutil import parse_coc_time, remaining_until


def normalize_tag(raw: str | None) -> str | None:
    """Turn ``#abc123``/``abc123``/a profile link into ``#ABC123``."""
    if not raw:
        return None
    value = raw.strip().upper().replace(" ", "")
    if value.startswith("HTTP"):
        # Profile links look like ...?tag=ABC123 or .../ABC123
        if "TAG=" in value:
            value = value.split("TAG=", 1)[1].split("&", 1)[0]
        else:
            value = value.rsplit("/", 1)[-1].split("?", 1)[0]
    value = value.replace("O", "0")
    value = value.lstrip("#").strip()
    if not value or not all(ch.isalnum() for ch in value):
        return None
    return f"#{value}"


def is_tag_like(raw: str | None) -> bool:
    return normalize_tag(raw) is not None


def esc(value: object) -> str:
    """Escape untrusted text for Telegram HTML parse mode."""
    return html.escape(str(value if value is not None else ""), quote=False)


def num(value: int | float | None) -> str:
    if value is None:
        return "0"
    try:
        return f"{int(value):,}".replace(",", "٬")
    except (TypeError, ValueError):
        return "0"


def progress_bar(current: int | None, total: int | None, width: int = 10) -> str:
    if not total:
        return "—"
    current = max(0, min(int(current or 0), int(total)))
    filled = round(width * current / total)
    return "▰" * filled + "▱" * (width - filled)


def percent(current: int | float | None, total: int | float | None) -> str:
    if not total:
        return "0%"
    return f"{round(100 * float(current or 0) / float(total))}%"


def stars(count: int | None) -> str:
    count = max(0, min(int(count or 0), 3))
    return "⭐" * count if count else "✩"


def th_emoji(level: int | None) -> str:
    return f"🏰{level}" if level else "🏰؟"


def war_countdown(end_time: str | None) -> str:
    parsed = parse_coc_time(end_time)
    return remaining_until(parsed)


def hero_line(name: str, level: int | None, max_level: int | None, emoji: str) -> str:
    level_txt = str(level) if level is not None else "—"
    max_txt = f"/{max_level}" if max_level else ""
    bar = progress_bar(level, max_level, width=8) if level and max_level else ""
    return f"{emoji} {esc(name)}: <b>{level_txt}{max_txt}</b> {bar}"
