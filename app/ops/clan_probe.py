"""Read-only Clash of Clans data dump used by /diag?...&clans= (owner diagnostics).

The API key is bound to the cloud egress IP, so ad-hoc clan research has to run
server-side. This module only fetches public data; it never touches the database
and never returns secrets.
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)

MAX_TAGS = 12
MAX_TAG_LENGTH = 20


def parse_tags(raw: str | None) -> list[str]:
    """Accept tags separated by commas, pipes or spaces: ``#A0B1C2D, P2008JU2``."""
    if not raw:
        return []
    normalized = raw.replace("|", ",").replace(" ", ",")
    tags: list[str] = []
    for part in normalized.split(","):
        part = part.strip().upper().lstrip("#")
        if not part or len(part) > MAX_TAG_LENGTH or not part.isalnum():
            continue
        tag = f"#{part}"
        if tag not in tags:
            tags.append(tag)
    return tags[:MAX_TAGS]


async def dump(client: Any, tags: list[str]) -> dict[str, Any]:
    """Fetch clan + current war + war log for every tag, never raising."""
    result: dict[str, Any] = {}
    for tag in tags:
        entry: dict[str, Any] = {}
        try:
            entry["clan"] = await client.clan(tag)
        except Exception as error:  # noqa: BLE001 - reported, never raised
            entry["clan_error"] = type(error).__name__
            result[tag] = entry
            continue
        try:
            entry["war"] = await client.current_war(tag)
        except Exception as error:  # noqa: BLE001
            entry["war_error"] = type(error).__name__
        try:
            entry["log"] = await client.war_log(tag, limit=10)
        except Exception as error:  # noqa: BLE001
            entry["log_error"] = type(error).__name__
        result[tag] = entry
        logger.info("clan_probe: dumped %s", tag)
    return result
