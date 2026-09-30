"""Player progress snapshots used for growth reports and hero alerts."""

from __future__ import annotations

from typing import Any

from app.bot.deps import Deps
from app.coc.models import Player

TRACKED_KEYS = (
    "trophies",
    "best_trophies",
    "donations",
    "donations_received",
    "war_stars",
    "clan_capital_contributions",
    "town_hall",
    "exp_level",
)


def player_payload(player: Player) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "tag": player.tag,
        "name": player.name,
        "town_hall": player.town_hall,
        "clan_tag": player.clan_tag,
        "heroes": {hero.name: hero.level for hero in player.heroes if hero.village == "home"},
    }
    payload.update({key: getattr(player, key, 0) for key in TRACKED_KEYS})
    return payload


def diff_payload(old: dict[str, Any], new: dict[str, Any]) -> dict[str, Any]:
    deltas: dict[str, Any] = {}
    for key in TRACKED_KEYS:
        before = int(old.get(key, 0) or 0)
        after = int(new.get(key, 0) or 0)
        if before != after:
            deltas[key] = after - before
    old_heroes = old.get("heroes", {}) or {}
    new_heroes = new.get("heroes", {}) or {}
    hero_changes = {
        name: (old_heroes.get(name, 0), level)
        for name, level in new_heroes.items()
        if old_heroes.get(name, 0) != level
    }
    if hero_changes:
        deltas["heroes"] = hero_changes
    return deltas


async def record_player(deps: Deps, player: Player) -> bool:
    """Store a snapshot when the tracked values changed. Returns True if stored."""
    payload = player_payload(player)
    latest = await deps.snapshots.latest("player", player.tag)
    if latest and _same(latest[1], payload):
        return False
    await deps.snapshots.add("player", player.tag, payload)
    return True


async def previous_player(deps: Deps, tag: str) -> tuple[str, dict[str, Any]] | None:
    return await deps.snapshots.latest("player", tag, skip=1)


def _same(a: dict[str, Any], b: dict[str, Any]) -> bool:
    same_values = all(a.get(key) == b.get(key) for key in TRACKED_KEYS)
    return same_values and a.get("heroes") == b.get("heroes")
