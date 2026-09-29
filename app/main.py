import asyncio
import logging
import os

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage

from app.coc import CocClient
from app.config import Settings
from app.db import Database
from app.handlers import router
from app.health import serve_health
from app.reminders import war_reminder_loop

logger = logging.getLogger(__name__)


def _health_port() -> int | None:
    value = os.getenv("PORT", "8080").strip()
    if not value:
        return None
    try:
        return int(value)
    except ValueError:
        logger.warning("Ignoring invalid PORT value: %s", value)
        return None


async def run() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    settings = Settings.from_environment()
    database = Database(settings.database_path)
    await database.initialize()
    coc_client = CocClient(settings.coc_api_token)

    bot = Bot(
        token=settings.telegram_bot_token,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    dispatcher = Dispatcher(storage=MemoryStorage())
    dispatcher["database"] = database
    dispatcher["settings"] = settings
    dispatcher["coc_client"] = coc_client
    dispatcher.include_router(router)

    health_port = _health_port()
    health_task = asyncio.create_task(serve_health(health_port)) if health_port is not None else None
    reminder_task = asyncio.create_task(
        war_reminder_loop(bot, database, coc_client)
    )
    try:
        await dispatcher.start_polling(bot, allowed_updates=dispatcher.resolve_used_update_types())
    finally:
        reminder_task.cancel()
        pending = [reminder_task]
        if health_task is not None:
            health_task.cancel()
            pending.append(health_task)
        await asyncio.gather(*pending, return_exceptions=True)
        await coc_client.close()
        await bot.session.close()


def main() -> None:
    asyncio.run(run())
