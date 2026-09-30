"""Middlewares: dependency injection, user tracking and error handling."""

from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable
from typing import Any

from aiogram import BaseMiddleware
from aiogram.types import CallbackQuery, Message, TelegramObject, User

from app.bot.deps import Deps
from app.core.errors import AppError

logger = logging.getLogger(__name__)


def _extract_user(event: TelegramObject) -> User | None:
    update = getattr(event, "event", event)
    for attr in ("message", "edited_message", "callback_query", "inline_query"):
        obj = getattr(update, attr, None)
        if obj is not None:
            return getattr(obj, "from_user", None)
    return None


def _extract_message(event: TelegramObject) -> Message | None:
    update = getattr(event, "event", event)
    for attr in ("message", "edited_message"):
        obj = getattr(update, attr, None)
        if obj is not None:
            return obj
    callback = getattr(update, "callback_query", None)
    if callback is not None and isinstance(callback.message, Message):
        return callback.message
    return None


class DepsMiddleware(BaseMiddleware):
    def __init__(self, deps: Deps) -> None:
        self.deps = deps

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        data["deps"] = self.deps
        user = _extract_user(event)
        if user and not user.is_bot:
            try:
                await self.deps.users.upsert(
                    user.id, username=user.username, first_name=user.first_name
                )
            except Exception:  # pragma: no cover - never block handling on tracking
                logger.debug("Could not track user", exc_info=True)
        return await handler(event, data)


class ErrorMiddleware(BaseMiddleware):
    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        try:
            return await handler(event, data)
        except AppError as exc:
            await _notify(event, f"⚠️ {exc.reason}")
            return None
        except Exception:  # noqa: BLE001 - last line of defence
            logger.exception("Unhandled error while processing update")
            await _notify(event, "حدث خطأ غير متوقع. جرّب مرة أخرى بعد قليل.")
            return None


async def _notify(event: TelegramObject, text: str) -> None:
    callback: CallbackQuery | None = getattr(event, "callback_query", None)
    if callback is not None:
        try:
            await callback.answer(text, show_alert=True)
            return
        except Exception:  # pragma: no cover
            logger.debug("Could not answer callback", exc_info=True)
    message = _extract_message(event)
    if message is not None:
        try:
            await message.answer(text)
        except Exception:  # pragma: no cover
            logger.debug("Could not send error notice", exc_info=True)
