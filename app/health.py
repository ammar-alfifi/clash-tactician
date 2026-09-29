import asyncio
import logging
import os

import aiohttp
import aiosqlite
from aiohttp import web

from app.egress import observed_egress_ips, sample_egress_ip

logger = logging.getLogger(__name__)

COUNTED_TABLES = ("users", "linked_players", "war_rooms", "ai_connections")
COC_API_URL = "https://api.clashofclans.com/v1/locations"


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


async def _coc_check() -> dict[str, object]:
    """Self-test for the Clash of Clans API key (mainly the registered IP)."""
    token = os.getenv("COC_API_TOKEN", "").strip()
    if not token:
        return {"ok": False, "reason": "missing_token"}
    headers = {"Authorization": f"Bearer {token}", "Accept": "application/json"}
    try:
        timeout = aiohttp.ClientTimeout(total=20)
        async with (
            aiohttp.ClientSession(timeout=timeout) as session,
            session.get(COC_API_URL, headers=headers) as response,
        ):
            body = await response.text()
            return {"ok": response.status == 200, "status": response.status, "detail": body[:200]}
    except (TimeoutError, aiohttp.ClientError) as error:
        return {"ok": False, "reason": type(error).__name__}


async def _diag(request: web.Request) -> web.Response:
    """Expose diagnostics (never secret data) behind DIAG_TOKEN."""
    expected = os.getenv("DIAG_TOKEN", "").strip()
    if not expected or request.query.get("token") != expected:
        return web.json_response({"status": "not_found"}, status=404)
    payload: dict[str, object] = {
        "status": "ok",
        "egress_ips": observed_egress_ips(),
        "counts": await _database_counts(),
    }
    if request.query.get("current"):
        payload["current_egress_ip"] = await sample_egress_ip()
    if request.query.get("coc"):
        payload["coc"] = await _coc_check()
    return web.json_response(payload)


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
