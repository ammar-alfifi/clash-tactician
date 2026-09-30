"""Higher-level Clash of Clans operations used by handlers."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

from app.coc.client import CocClient
from app.coc.models import Clan, Player, War, WarMember

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class Target:
    position: int
    tag: str
    name: str
    town_hall: int
    stars: int
    destruction: int
    our_attacks: int
    their_attacks: int
    open: bool

    @property
    def perfect(self) -> bool:
        return self.stars < 3


@dataclass(frozen=True)
class CapitalSummary:
    state: str
    start_time: str | None
    end_time: str | None
    capital_total_loot: int
    raids_completed: int
    total_attacks: int
    total_districts: int
    offensive_reward: int
    defensive_reward: int
    members: tuple[dict[str, Any], ...] = ()


class CocService:
    def __init__(self, client: CocClient) -> None:
        self.client = client

    async def player(self, tag: str) -> Player:
        return Player.from_api(await self.client.player(tag))

    async def clan(self, tag: str) -> Clan:
        return Clan.from_api(await self.client.clan(tag))

    async def war(self, tag: str) -> War:
        return War.from_api(await self.client.current_war(tag))

    async def war_log(self, tag: str, limit: int = 10) -> list[dict[str, Any]]:
        data = await self.client.war_log(tag, limit)
        return list(data.get("items", []) or [])

    async def paged_items(self, tag: str, limit: int = 5) -> list[dict[str, Any]]:
        return list((await self.client.clan(tag)).get("memberList", []) or [])[:limit]

    async def capital(self, tag: str) -> CapitalSummary | None:
        data = await self.client.capital_raid_seasons(tag, limit=1)
        items = data.get("items") or []
        if not items:
            return None
        season = items[0]
        return CapitalSummary(
            state=str(season.get("state", "unknown")),
            start_time=season.get("startTime"),
            end_time=season.get("endTime"),
            capital_total_loot=int(season.get("capitalTotalLoot", 0) or 0),
            raids_completed=int(season.get("raidsCompleted", 0) or 0),
            total_attacks=int(season.get("totalAttacks", 0) or 0),
            total_districts=int(season.get("enemyDistrictsDestroyed", 0) or 0),
            offensive_reward=int(season.get("offensiveReward", 0) or 0),
            defensive_reward=int(season.get("defensiveReward", 0) or 0),
            members=tuple(season.get("members", []) or []),
        )

    async def league_group(self, tag: str) -> dict[str, Any] | None:
        try:
            return await self.client.league_group(tag)
        except Exception:  # CWL group is often unavailable (not CWL week)
            logger.debug("No CWL league group for %s", tag, exc_info=True)
            return None

    async def suggestions(self, clan_tag: str, *, player_tag: str | None = None) -> list[Target]:
        war = await self.war(clan_tag)
        if not war.in_war or not war.opponent:
            return []
        targets: list[Target] = []
        for enemy in war.opponent.members:
            our_attacks = enemy.opponent_attacks
            targets.append(
                Target(
                    position=enemy.map_position,
                    tag=enemy.tag,
                    name=enemy.name,
                    town_hall=enemy.town_hall,
                    stars=enemy.stars,
                    destruction=enemy.destruction,
                    our_attacks=our_attacks,
                    their_attacks=len(enemy.attacks),
                    open=our_attacks < war.attacks_per_member,
                )
            )
        targets.sort(key=lambda t: (not t.perfect, -t.town_hall, t.our_attacks))
        return targets

    async def member_war_status(self, clan_tag: str, player_tag: str | None) -> WarMember | None:
        if not player_tag:
            return None
        war = await self.war(clan_tag)
        return war.member_by_tag(player_tag)
