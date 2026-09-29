import asyncio
import logging
import os

import aiosqlite
from aiohttp import web

from app.egress import observed_egress_ips

logger = logging.getLogger(__name__)

COUNTED_TABLES = ("users", "linked_players", "war_rooms", "ai_connections")


async def _health(_: web.Request) -> web.Response:
    return web.json_response({"status": "ok"})


async def _database_counts() -> dict[str, int]:
    path = os.getenv("DATABASE_PATH", "data/bot.sqlite3")
    counts: dict[str, int] = {}
    try:
        async with aiosqlite.connect(path) as connection:
            for table in COUNTED_TABLES:
                try:
                    cursor = await connection.execute(f"SELECT COUNT(*) FROM {table}")
                    row = await cursor.fetchone()
                except aiosqlite.Error:
                    counts[table] = 0
                else:
                    counts[table] = int(row[0]) if row else 0
    except (aiosqlite.Error, OSError):
        logger.warning("Could not read database counts", exc_info=True)
    return counts


async def _diag(request: web.Request) -> web.Response:
    """Expose diagnostics (never secret data) behind DIAG_TOKEN."""
    expected = os.getenv("DIAG_TOKEN", "").strip()
    if not expected or request.query.get("token") != expected:
        return web.json_response({"status": "not_found"}, status=404)
    return web.json_response(
        {
            "status": "ok",
            "egress_ips": observed_egress_ips(),
            "counts": await _database_counts(),
        }
    )


def create_health_app() -> web.Application:
    application = web.Application()
    application.router.add_get("/", _health)
    application.router.add_get("/health", _health)
    application.router.add_get("/diag", _diag)
    return application


async def serve_health(port: int) -> None:
    """Serve a minimal HTTP endpoint so cloud platforms see the bot as healthy."""
    runner = web.AppRunner(create_health_app())
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", port)
    try:
        await site.start()
    except OSError:
        logger.exception("Could not start health server on port %s", port)
        await runner.cleanup()
        return
    logger.info("Health server listening on port %s", port)
    try:
        await asyncio.Event().wait()
    finally:
        await runner.cleanup()
