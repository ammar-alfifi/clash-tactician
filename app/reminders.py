"""Background war reminders for Telegram groups linked to a clan war room."""

import asyncio
import logging

from aiogram import Bot
from aiogram.exceptions import TelegramAPIError

from app.clan_tools import format_war_reminder
from app.coc import CocAPIError, CocClient
from app.db import Database

logger = logging.getLogger(__name__)

DEFAULT_CHECK_SECONDS = 60


async def send_due_reminders(
    bot: Bot, database: Database, coc_client: CocClient
) -> int:
    """Send one reminder to each due war room; return the number of messages sent."""
    sent = 0
    for chat_id, clan_tag in await database.list_due_war_reminders():
        try:
            war = await coc_client.current_war(clan_tag)
        except CocAPIError:
            continue
        except Exception:
            logger.exception("Could not fetch war for reminder in chat %s", chat_id)
            continue
        text = format_war_reminder(war)
        if not text:
            continue
        try:
            await bot.send_message(chat_id, text)
        except TelegramAPIError:
            logger.warning("Could not deliver war reminder to chat %s", chat_id)
            continue
        await database.mark_war_reminder_sent(chat_id)
        sent += 1
    return sent


async def war_reminder_loop(
    bot: Bot,
    database: Database,
    coc_client: CocClient,
    check_seconds: int = DEFAULT_CHECK_SECONDS,
) -> None:
    """Periodically deliver reminders until the task is cancelled."""
    while True:
        await asyncio.sleep(check_seconds)
        try:
            await send_due_reminders(bot, database, coc_client)
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("War reminder loop iteration failed")
