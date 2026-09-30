"""Telegram bot layer."""

__all__ = ["main", "run"]


def __getattr__(name: str):
    if name in {"main", "run"}:
        from app.bot import app as _app

        return getattr(_app, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
