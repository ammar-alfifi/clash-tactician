import asyncio
import logging
import os

from aiohttp import web

from app.egress import observed_egress_ips

logger = logging.getLogger(__name__)


async def _health(_: web.Request) -> web.Response:
    return web.json_response({"status": "ok"})


async def _diag(request: web.Request) -> web.Response:
    """Expose diagnostics (never public data) behind DIAG_TOKEN."""
    expected = os.getenv("DIAG_TOKEN", "").strip()
    if not expected or request.query.get("token") != expected:
        return web.json_response({"status": "not_found"}, status=404)
    return web.json_response({"status": "ok", "egress_ips": observed_egress_ips()})


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
