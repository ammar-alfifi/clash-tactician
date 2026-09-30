"""Automatic war reminders for linked group chats."""

from __future__ import annotations

import asyncio
import logging

from aiogram import Bot

from app.bot.deps import Deps
from app.core.errors import CocError

logger = logging.getLogger(__name__)


async def room_reminder_text(deps: Deps, clan_tag: str) -> str | None:
    """Return a reminder message when members still have attacks left."""
    war = await deps.coc.war(clan_tag)
    if not war.in_war or not war.clan:
        return None
    missing = [
        member
        for member in war.clan.members
        if len(member.attacks) < war.attacks_per_member
    ]
    if not missing:
        return None
    header = f"⏰ <b>تذكير هجمات الحرب</b> — {war.clan.name}\n"
    header += f"⭐ النتيجة: {war.clan.stars} ضد {war.opponent.stars if war.opponent else 0}\n\n"
    names = "، ".join(
        f"{member.name} ({len(member.attacks)}/{war.attacks_per_member})"
        for member in missing[:25]
    )
    return header + f"⚠️ بقي {len(missing)} لاعبًا لم يُكملوا هجماتهم:\n{names}"


async def send_reminder(bot: Bot, deps: Deps, chat_id: int, clan_tag: str) -> bool:
    try:
        text = await room_reminder_text(deps, clan_tag)
    except CocError as exc:
        logger.info("Reminder skipped for %s: %s", clan_tag, exc.reason)
        return False
    if not text:
        return False
    try:
        await bot.send_message(chat_id, text)
    except Exception:  # noqa: BLE001 - group may have removed the bot
        logger.warning("Could not send reminder to %s", chat_id, exc_info=True)
        return False
    return True


async def reminder_loop(bot: Bot, deps: Deps) -> None:
    interval = deps.settings.reminder_tick_seconds
    while True:
        await asyncio.sleep(interval)
        try:
            rooms = await deps.rooms.due_reminders()
        except Exception:  # noqa: BLE001
            logger.warning("Could not load due reminders", exc_info=True)
            continue
        for room in rooms:
            if await send_reminder(bot, deps, room.chat_id, room.clan_tag):
                await deps.rooms.mark_reminded(room.chat_id)
