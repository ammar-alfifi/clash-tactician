"""Shared handler helpers."""

from __future__ import annotations

import logging

from aiogram.exceptions import TelegramBadRequest
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, Message

from app.bot import texts
from app.bot.deps import Deps
from app.core.formatting import normalize_tag

logger = logging.getLogger(__name__)


async def safe_edit(
    event: Message | CallbackQuery,
    text: str,
    reply_markup: InlineKeyboardMarkup | None = None,
) -> None:
    """Edit a message in place, ignoring Telegram's 'not modified' error."""
    message = event.message if isinstance(event, CallbackQuery) else event
    if not isinstance(message, Message):
        return
    try:
        await message.edit_text(
            text, reply_markup=reply_markup, disable_web_page_preview=True
        )
    except TelegramBadRequest as exc:
        if "not modified" in str(exc).lower():
            return
        # Message might be a photo/too old: fall back to a fresh message.
        try:
            await message.answer(text, reply_markup=reply_markup, disable_web_page_preview=True)
        except TelegramBadRequest:
            logger.debug("Could not edit or resend message", exc_info=True)


async def reply(
    event: Message | CallbackQuery,
    text: str,
    reply_markup: InlineKeyboardMarkup | None = None,
) -> None:
    if isinstance(event, CallbackQuery):
        if isinstance(event.message, Message):
            await event.message.answer(
                text, reply_markup=reply_markup, disable_web_page_preview=True
            )
    else:
        await event.answer(text, reply_markup=reply_markup, disable_web_page_preview=True)


async def present(
    event: Message | CallbackQuery,
    text: str,
    reply_markup: InlineKeyboardMarkup | None = None,
) -> None:
    """Edit for callbacks, send a new message for plain messages."""
    if isinstance(event, CallbackQuery):
        await safe_edit(event, text, reply_markup)
    else:
        await reply(event, text, reply_markup)


def get_deps(data: dict) -> Deps:
    return data["deps"]


async def linked_tag(deps: Deps, telegram_id: int) -> str | None:
    return await deps.primary_tag(telegram_id)


async def resolve_clan_tag(deps: Deps, telegram_id: int, explicit: str | None = None) -> str | None:
    """Explicit tag wins; otherwise derive from the user's primary account."""
    if explicit:
        return normalize_tag(explicit)
    tag = await deps.primary_tag(telegram_id)
    if not tag:
        return None
    if not deps.settings.has_coc:
        return None
    try:
        player = await deps.coc.player(tag)
    except Exception:  # noqa: BLE001 - fall back to a friendly message upstream
        logger.info("Could not resolve clan for %s", tag, exc_info=True)
        return None
    return player.clan_tag


def parse_callback(data: str | None) -> tuple[str, list[str]]:
    if not data:
        return "", []
    parts = data.split(":")
    return parts[0], parts[1:]


def missing_coc_notice() -> str:
    return texts.NO_COC
