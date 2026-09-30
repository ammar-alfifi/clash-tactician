"""Parsed Clash of Clans models (defensive: the API evolves)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


def _get(data: dict[str, Any], *path: str, default: Any = None) -> Any:
    current: Any = data
    for key in path:
        if not isinstance(current, dict):
            return default
        current = current.get(key)
        if current is None:
            return default
    return current


def _int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


@dataclass(frozen=True)
class Hero:
    name: str
    level: int
    max_level: int
    village: str


@dataclass(frozen=True)
class Troop:
    name: str
    level: int
    max_level: int
    village: str


@dataclass(frozen=True)
class Player:
    tag: str
    name: str
    town_hall: int
    exp_level: int
    trophies: int
    best_trophies: int
    war_stars: int
    attack_wins: int
    defense_wins: int
    donations: int
    donations_received: int
    role: str | None
    clan_tag: str | None
    clan_name: str | None
    league: str | None
    builder_hall: int
    clan_capital_contributions: int
    heroes: tuple[Hero, ...] = ()
    troops: tuple[Troop, ...] = ()
    achievements: tuple[dict[str, Any], ...] = ()
    labels: tuple[str, ...] = ()
    raw: dict[str, Any] = field(default_factory=dict, repr=False)

    @classmethod
    def from_api(cls, data: dict[str, Any]) -> Player:
        heroes = tuple(
            Hero(
                name=str(_get(hero, "name", default="?")),
                level=_int(_get(hero, "level")),
                max_level=_int(_get(hero, "maxLevel")),
                village=str(_get(hero, "village", default="home")),
            )
            for hero in data.get("heroes", []) or []
        )
        troops = tuple(
            Troop(
                name=str(_get(troop, "name", default="?")),
                level=_int(_get(troop, "level")),
                max_level=_int(_get(troop, "maxLevel")),
                village=str(_get(troop, "village", default="home")),
            )
            for troop in data.get("troops", []) or []
        )
        labels = tuple(
            str(_get(label, "name", default="")) for label in data.get("labels", []) or []
        )
        return cls(
            tag=str(data.get("tag", "")),
            name=str(data.get("name", "?")),
            town_hall=_int(data.get("townHallLevel")),
            exp_level=_int(data.get("expLevel")),
            trophies=_int(data.get("trophies")),
            best_trophies=_int(data.get("bestTrophies")),
            war_stars=_int(data.get("warStars")),
            attack_wins=_int(data.get("attackWins")),
            defense_wins=_int(data.get("defenseWins")),
            donations=_int(data.get("donations")),
            donations_received=_int(data.get("donationsReceived")),
            role=_get(data, "role"),
            clan_tag=_get(data, "clan", "tag"),
            clan_name=_get(data, "clan", "name"),
            league=_get(data, "league", "name"),
            builder_hall=_int(data.get("builderHallLevel")),
            clan_capital_contributions=_int(data.get("clanCapitalContributions")),
            heroes=heroes,
            troops=troops,
            achievements=tuple(data.get("achievements", []) or []),
            labels=labels,
            raw=data,
        )

    @property
    def hero_map(self) -> dict[str, Hero]:
        return {hero.name: hero for hero in self.heroes}


@dataclass(frozen=True)
class ClanMember:
    tag: str
    name: str
    role: str
    town_hall: int
    trophies: int
    donations: int
    donations_received: int
    clan_capital_contributions: int
    exp_level: int
    league: str | None = None

    @classmethod
    def from_api(cls, data: dict[str, Any]) -> ClanMember:
        return cls(
            tag=str(data.get("tag", "")),
            name=str(data.get("name", "?")),
            role=str(data.get("role", "member")),
            town_hall=_int(data.get("townHallLevel")),
            trophies=_int(data.get("trophies")),
            donations=_int(data.get("donations")),
            donations_received=_int(data.get("donationsReceived")),
            clan_capital_contributions=_int(data.get("clanCapitalContributions")),
            exp_level=_int(data.get("expLevel")),
            league=_get(data, "league", "name"),
        )


@dataclass(frozen=True)
class Clan:
    tag: str
    name: str
    level: int
    description: str
    members: tuple[ClanMember, ...]
    member_count: int
    clan_points: int
    clan_capital_points: int
    war_wins: int
    war_losses: int
    war_ties: int
    war_streak: int
    required_trophies: int
    location: str | None
    type: str | None
    badges: tuple[str, ...] = ()
    capital_hall_level: int = 0
    raw: dict[str, Any] = field(default_factory=dict, repr=False)

    @classmethod
    def from_api(cls, data: dict[str, Any]) -> Clan:
        members = tuple(
            ClanMember.from_api(member) for member in data.get("memberList", []) or []
        )
        return cls(
            tag=str(data.get("tag", "")),
            name=str(data.get("name", "?")),
            level=_int(data.get("clanLevel")),
            description=str(data.get("description", "")),
            members=members,
            member_count=_int(data.get("members")),
            clan_points=_int(data.get("clanPoints")),
            clan_capital_points=_int(data.get("clanCapitalPoints")),
            war_wins=_int(data.get("warWins")),
            war_losses=_int(data.get("warLosses")),
            war_ties=_int(data.get("warTies")),
            war_streak=_int(data.get("warWinStreak")),
            required_trophies=_int(data.get("requiredTrophies")),
            location=_get(data, "location", "name"),
            type=_get(data, "type"),
            badges=tuple(
                str(_get(badge, "name", default="")) for badge in data.get("labels", []) or []
            ),
            capital_hall_level=_int(_get(data, "capitalHall", "capitalHallLevel"))
            or _int(_get(data, "clanCapital", "capitalHallLevel")),
            raw=data,
        )


@dataclass(frozen=True)
class WarAttack:
    attacker_tag: str
    defender_tag: str
    stars: int
    destruction: int
    order: int
    duration: int = 0


@dataclass(frozen=True)
class WarMember:
    tag: str
    name: str
    town_hall: int
    map_position: int
    attacks: tuple[WarAttack, ...] = ()
    opponent_attacks: int = 0
    stars: int = 0
    destruction: int = 0

    @classmethod
    def from_api(cls, data: dict[str, Any], *, side: str = "clan") -> WarMember:
        attacks = tuple(
            WarAttack(
                attacker_tag=str(attack.get("attackerTag", "")),
                defender_tag=str(attack.get("defenderTag", "")),
                stars=_int(attack.get("stars")),
                destruction=_int(attack.get("destructionPercentage")),
                order=_int(attack.get("order")),
                duration=_int(attack.get("duration")),
            )
            for attack in data.get("attacks", []) or []
        )
        opponent = data.get("opponentAttacks", 0)
        return cls(
            tag=str(data.get("tag", "")),
            name=str(data.get("name", "?")),
            town_hall=_int(data.get("townHallLevel")),
            map_position=_int(data.get("mapPosition")),
            attacks=attacks,
            opponent_attacks=_int(opponent),
            stars=_int(data.get("stars")),
            destruction=_int(data.get("destructionPercentage")),
        )


@dataclass(frozen=True)
class WarSide:
    tag: str
    name: str
    level: int
    stars: int
    destruction: float
    attacks: int
    members: tuple[WarMember, ...] = ()

    @classmethod
    def from_api(cls, data: dict[str, Any]) -> WarSide:
        return cls(
            tag=str(data.get("tag", "")),
            name=str(data.get("name", "?")),
            level=_int(data.get("clanLevel")),
            stars=_int(data.get("stars")),
            destruction=float(data.get("destructionPercentage", 0) or 0),
            attacks=_int(data.get("attacks")),
            members=tuple(
                WarMember.from_api(member, side="clan")
                for member in data.get("members", []) or []
            ),
        )


@dataclass(frozen=True)
class War:
    state: str
    team_size: int
    attacks_per_member: int
    preparation_start: str | None
    start_time: str | None
    end_time: str | None
    clan: WarSide | None
    opponent: WarSide | None
    is_cwl: bool = False
    raw: dict[str, Any] = field(default_factory=dict, repr=False)

    @classmethod
    def from_api(cls, data: dict[str, Any]) -> War:
        clan = WarSide.from_api(data["clan"]) if data.get("clan") else None
        opponent = WarSide.from_api(data["opponent"]) if data.get("opponent") else None
        return cls(
            state=str(data.get("state", "notInWar")),
            team_size=_int(data.get("teamSize")),
            attacks_per_member=_int(data.get("attacksPerMember", 2)) or 2,
            preparation_start=data.get("preparationStartTime"),
            start_time=data.get("startTime"),
            end_time=data.get("endTime"),
            clan=clan,
            opponent=opponent,
            is_cwl=_get(data, "isCwl", default=False) or data.get("warType") == "cwl",
            raw=data,
        )

    @property
    def in_war(self) -> bool:
        return self.state in {"preparation", "inWar"} and self.clan is not None

    @property
    def total_attacks(self) -> int:
        return self.team_size * self.attacks_per_member

    def attacks_used(self) -> int:
        if not self.clan:
            return 0
        return sum(len(member.attacks) for member in self.clan.members)

    def member_by_tag(self, tag: str) -> WarMember | None:
        if not self.clan:
            return None
        for member in self.clan.members:
            if member.tag == tag:
                return member
        return None


def war_fingerprint(war: War) -> str:
    """Stable-ish signature used to detect meaningful war changes."""
    if not war.in_war or not war.clan:
        return f"state:{war.state}"
    parts = [war.state, str(war.clan.stars), str(round(war.clan.destruction, 1))]
    parts.extend(f"{member.tag}:{len(member.attacks)}" for member in war.clan.members)
    return "|".join(parts)
