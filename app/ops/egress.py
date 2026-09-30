"""Track the host's public IP so the CoC API key can be registered correctly."""

from __future__ import annotations

import asyncio
import logging

import aiohttp

logger = logging.getLogger(__name__)

EGRESS_CHECK_URL = "https://api.ipify.org"
_OBSERVED: set[str] = set()


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


def observed_ips() -> list[str]:
    return sorted(_OBSERVED)


async def sample_egress_ip() -> str | None:
    ip = await fetch_egress_ip()
    if ip:
        _OBSERVED.add(ip)
        logger.info("Egress IP: %s", ip)
    return ip


async def egress_loop(interval_seconds: int = 300) -> None:
    while True:
        await sample_egress_ip()
        await asyncio.sleep(interval_seconds)
