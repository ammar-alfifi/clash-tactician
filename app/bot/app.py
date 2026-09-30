"""Bot application entry point: wiring, background jobs and lifecycle."""

from __future__ import annotations

import asyncio
import contextlib
import logging

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage

from app.bot.deps import build_deps
from app.bot.handlers import build_router
from app.bot.middlewares import DepsMiddleware, ErrorMiddleware
from app.config import Settings
from app.core.logging import setup_logging
from app.ops.backup import DatabaseBackup
from app.ops.egress import egress_loop
from app.ops.health import HealthContext, serve_health
from app.services.war_reminders import reminder_loop
from app.services.watcher import watcher_loop

logger = logging.getLogger(__name__)


async def run() -> None:
    setup_logging()
    settings = Settings.from_environment()
    logger.info(
        "Starting Clash Tactician (CoC=%s, shared AI=%s)",
        settings.has_coc,
        settings.has_shared_ai,
    )

    backup = DatabaseBackup(settings.database_path)
    if backup.enabled and await backup.restore():
        logger.info("Database restored from cloud backup")

    deps = build_deps(settings)
    await deps.db.initialize()

    bot = Bot(
        token=settings.bot_token,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    dispatcher = Dispatcher(storage=MemoryStorage())
    dispatcher.update.outer_middleware(ErrorMiddleware())
    dispatcher.update.outer_middleware(DepsMiddleware(deps))
    dispatcher.include_router(build_router())

    tasks: list[asyncio.Task] = [asyncio.create_task(egress_loop(settings.egress_interval_seconds))]

    if settings.port is not None:
        context = HealthContext(settings, deps.db, deps.coc.client)
        tasks.append(asyncio.create_task(serve_health(context, settings.port)))

    if backup.enabled:
        tasks.append(asyncio.create_task(backup.run()))

    if settings.enable_background_jobs and settings.has_coc:
        tasks.append(asyncio.create_task(reminder_loop(bot, deps)))
        tasks.append(asyncio.create_task(watcher_loop(bot, deps)))

    try:
        await dispatcher.start_polling(bot, allowed_updates=dispatcher.resolve_used_update_types())
    finally:
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
        if backup.enabled:
            await backup.backup_once()
        await deps.coc.client.close()
        await bot.session.close()
        logger.info("Clash Tactician stopped")


def main() -> None:
    with contextlib.suppress(KeyboardInterrupt, SystemExit):
        asyncio.run(run())


if __name__ == "__main__":  # pragma: no cover
    main()
