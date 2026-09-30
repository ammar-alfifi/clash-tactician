"""Handler routers, composed in dispatch order."""

from __future__ import annotations

from aiogram import Router

from app.bot.handlers import (
    admin,
    assistant,
    clan,
    groups,
    planner,
    profile,
    settings,
    start,
    support,
    war,
    watch,
)


def build_router() -> Router:
    """Return a single router with every feature router attached in order."""
    root = Router(name="root")
    # Feature routers first; the start router owns the private-text fallback
    # and must come last.
    for module in (
        groups,
        profile,
        clan,
        war,
        planner,
        assistant,
        watch,
        settings,
        support,
        admin,
        start,
    ):
        root.include_router(module.router)
    return root
