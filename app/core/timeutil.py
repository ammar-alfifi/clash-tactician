"""Time helpers and Arabic human-friendly durations."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

_COC_FORMATS = ("%Y%m%dT%H%M%S.%fZ", "%Y%m%dT%H%M%SZ")


def utcnow() -> datetime:
    return datetime.now(UTC)


def parse_coc_time(value: str | None) -> datetime | None:
    """Parse Supercell timestamps such as ``20240101T120000.000Z``."""
    if not value:
        return None
    for fmt in _COC_FORMATS:
        try:
            return datetime.strptime(value, fmt).replace(tzinfo=UTC)
        except ValueError:
            continue
    return None


def humanize_seconds(seconds: int | float | None) -> str:
    """Render a duration in compact Arabic (e.g. ``3ي 4س``)."""
    if seconds is None:
        return "—"
    seconds = int(seconds)
    if seconds <= 0:
        return "انتهى"
    days, rem = divmod(seconds, 86400)
    hours, rem = divmod(rem, 3600)
    minutes, _ = divmod(rem, 60)
    parts: list[str] = []
    if days:
        parts.append(f"{days}ي")
    if hours and len(parts) < 2:
        parts.append(f"{hours}س")
    if minutes and len(parts) < 2:
        parts.append(f"{minutes}د")
    return " ".join(parts) if parts else "أقل من دقيقة"


def remaining_until(moment: datetime | None) -> str:
    if moment is None:
        return "—"
    return humanize_seconds((moment - utcnow()).total_seconds())


def relative_ar(moment: datetime | None) -> str:
    """Return an Arabic phrase like ``قبل 5 دقائق`` / ``بعد ساعتين``."""
    if moment is None:
        return "—"
    delta = utcnow() - moment
    future = delta < timedelta(0)
    seconds = abs(int(delta.total_seconds()))
    if seconds < 60:
        amount, unit = seconds, "ثانية"
    elif seconds < 3600:
        amount, unit = seconds // 60, "دقيقة"
    elif seconds < 86400:
        amount, unit = seconds // 3600, "ساعة"
    else:
        amount, unit = seconds // 86400, "يوم"
    plural = unit if amount in (1, 2) else f"{unit}ات" if unit == "ساعة" else f"{unit}"
    if unit == "يوم" and amount > 2:
        plural = "أيام"
    if unit == "دقيقة" and amount > 2:
        plural = "دقائق"
    prefix = "بعد" if future else "قبل"
    return f"{prefix} {amount} {plural}"
