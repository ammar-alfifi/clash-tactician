import asyncio
import logging

from aiohttp import web

logger = logging.getLogger(__name__)


async def _health(_: web.Request) -> web.Response:
    return web.json_response({"status": "ok"})


def create_health_app() -> web.Application:
    application = web.Application()
    application.router.add_get("/", _health)
    application.router.add_get("/health", _health)
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