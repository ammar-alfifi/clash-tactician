"""HTTP health and diagnostics server (keeps the cloud platform happy)."""

from __future__ import annotations

import asyncio
import logging

import aiohttp
from aiohttp import web

from app.config import Settings
from app.core.errors import CocError
from app.ops import egress
from app.storage.database import Database

logger = logging.getLogger(__name__)

COUNTED_TABLES = (
    "ct_users",
    "ct_accounts",
    "ct_ai_keys",
    "ct_clan_rooms",
    "ct_subscriptions",
    "ct_plans",
    "ct_tickets",
)


class HealthContext:
    def __init__(self, settings: Settings, database: Database, coc=None) -> None:
        self.settings = settings
        self.database = database
        self.coc = coc


def create_health_app(context: HealthContext) -> web.Application:
    application = web.Application()
    application["context"] = context
    application.router.add_get("/", _health)
    application.router.add_get("/health", _health)
    application.router.add_get("/diag", _diag)
    return application


async def _health(_: web.Request) -> web.Response:
    return web.json_response({"status": "ok", "service": "clash-tactician"})


async def _diag(request: web.Request) -> web.Response:
    context: HealthContext = request.app["context"]
    expected = context.settings.diag_token
    if not expected or request.query.get("token") != expected:
        return web.json_response({"status": "not_found"}, status=404)

    payload: dict[str, object] = {
        "status": "ok",
        "egress_ips": egress.observed_ips(),
        "counts": await context.database.table_counts(COUNTED_TABLES),
        "coc_enabled": context.settings.has_coc,
        "shared_ai": context.settings.has_shared_ai,
    }
    if request.query.get("current"):
        payload["current_egress_ip"] = await egress.sample_egress_ip()
    if request.query.get("coc"):
        payload["coc"] = await _coc_check(context)
    return web.json_response(payload)


async def _coc_check(context: HealthContext) -> dict[str, object]:
    if not context.settings.coc_api_token:
        return {"ok": False, "reason": "missing_token"}
    if context.coc is not None:
        ok, status, detail = await context.coc.verify()
        return {"ok": ok, "status": status, "detail": detail}
    headers = {
        "Authorization": f"Bearer {context.settings.coc_api_token}",
        "Accept": "application/json",
    }
    timeout = aiohttp.ClientTimeout(total=20)
    try:
        async with (
            aiohttp.ClientSession(timeout=timeout) as session,
            session.get(
                f"{context.settings.coc_base_url}/locations",
                headers=headers,
                params={"limit": 1},
            ) as response,
        ):
            body = await response.text()
            return {"ok": response.status == 200, "status": response.status, "detail": body[:200]}
    except (TimeoutError, aiohttp.ClientError, CocError) as error:
        return {"ok": False, "reason": type(error).__name__}


async def serve_health(context: HealthContext, port: int) -> None:
    runner = web.AppRunner(create_health_app(context))
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
