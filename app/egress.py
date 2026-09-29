import asyncio
import logging

import aiohttp

logger = logging.getLogger(__name__)

EGRESS_CHECK_URL = "https://api.ipify.org"
EGRESS_LOG_INTERVAL_SECONDS = 6 * 60 * 60


async def fetch_egress_ip() -> str | None:
    try:
        timeout = aiohttp.ClientTimeout(total=15)
        async with (
            aiohttp.ClientSession(timeout=timeout) as session,
            session.get(EGRESS_CHECK_URL) as response,
        ):
            response.raise_for_status()
            return (await response.text()).strip() or None
    except (TimeoutError, aiohttp.ClientError):
        logger.warning("Could not determine egress IP", exc_info=True)
        return None


async def log_egress_ip_loop() -> None:
    """Log the public IP the host uses, needed to register the CoC API key."""
    while True:
        ip = await fetch_egress_ip()
        if ip:
            logger.info("Egress IP: %s", ip)
        await asyncio.sleep(EGRESS_LOG_INTERVAL_SECONDS)
