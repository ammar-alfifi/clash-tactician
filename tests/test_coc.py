"""CoC model parsing and client behaviour."""

from __future__ import annotations

import pytest
from aiohttp import web

from app.coc.client import CocClient
from app.coc.models import Clan, Player, War, war_fingerprint
from app.coc.service import CocService
from app.core.errors import CocAuthError, CocDisabled, CocNotFound, CocUnavailable

PLAYER = {
    "tag": "#P1",
    "name": "Ammar",
    "townHallLevel": 14,
    "expLevel": 200,
    "trophies": 5000,
    "bestTrophies": 5300,
    "warStars": 900,
    "attackWins": 1200,
    "defenseWins": 400,
    "donations": 15000,
    "donationsReceived": 9000,
    "role": "leader",
    "clan": {"tag": "#C1", "name": "Kings"},
    "league": {"name": "Legend"},
    "builderHallLevel": 10,
    "clanCapitalContributions": 8000,
    "heroes": [
        {"name": "Barbarian King", "level": 70, "maxLevel": 80, "village": "home"},
        {"name": "Archer Queen", "level": 65, "maxLevel": 80, "village": "home"},
    ],
    "troops": [{"name": "Dragon", "level": 8, "maxLevel": 8, "village": "home"}],
    "labels": [{"name": "Clan Wars"}],
}


def test_player_parsing():
    player = Player.from_api(PLAYER)
    assert player.town_hall == 14
    assert player.clan_tag == "#C1"
    assert player.hero_map["Archer Queen"].level == 65
    assert player.heroes[0].village == "home"


def test_player_parsing_defensive():
    player = Player.from_api({"tag": "#X", "name": "Empty"})
    assert player.town_hall == 0
    assert player.heroes == ()
    assert player.clan_tag is None


def test_clan_parsing():
    clan = Clan.from_api(
        {
            "tag": "#C1",
            "name": "Kings",
            "clanLevel": 20,
            "members": 30,
            "clanPoints": 45000,
            "warWins": 300,
            "warWinStreak": 5,
            "memberList": [
                {"tag": "#P1", "name": "Ammar", "role": "leader", "townHallLevel": 14,
                 "trophies": 5000, "donations": 100, "donationsReceived": 50,
                 "clanCapitalContributions": 1000, "expLevel": 200},
            ],
        }
    )
    assert clan.member_count == 30
    assert clan.members[0].role == "leader"
    assert clan.war_wins == 300


def _war_payload(state="inWar"):
    return {
        "state": state,
        "teamSize": 2,
        "attacksPerMember": 2,
        "startTime": "20240101T000000.000Z",
        "endTime": "20240102T000000.000Z",
        "clan": {
            "tag": "#C1",
            "name": "Kings",
            "clanLevel": 20,
            "stars": 4,
            "destructionPercentage": 70.5,
            "attacks": 2,
            "members": [
                {
                    "tag": "#P1",
                    "name": "Ammar",
                    "townHallLevel": 14,
                    "mapPosition": 1,
                    "attacks": [{"attackerTag": "#P1", "defenderTag": "#E1", "stars": 3,
                                 "destructionPercentage": 100, "order": 1}],
                },
                {"tag": "#P2", "name": "Sami", "townHallLevel": 13, "mapPosition": 2},
            ],
        },
        "opponent": {
            "tag": "#C2",
            "name": "Rivals",
            "clanLevel": 18,
            "stars": 2,
            "destructionPercentage": 40.0,
            "attacks": 1,
            "members": [
                {"tag": "#E1", "name": "Enemy1", "townHallLevel": 14, "mapPosition": 1,
                 "opponentAttacks": 1, "stars": 2, "destructionPercentage": 60},
                {"tag": "#E2", "name": "Enemy2", "townHallLevel": 12, "mapPosition": 2},
            ],
        },
    }


def test_war_parsing_and_helpers():
    war = War.from_api(_war_payload())
    assert war.in_war
    assert war.total_attacks == 4
    assert war.attacks_used() == 1
    assert war.member_by_tag("#P2").name == "Sami"
    assert war_fingerprint(war).startswith("inWar")


def test_war_not_in_war():
    war = War.from_api({"state": "notInWar"})
    assert not war.in_war
    assert war_fingerprint(war) == "state:notInWar"


class _FakeCoc(CocClient):
    def __init__(self, payloads, **kwargs):
        super().__init__("token", **kwargs)
        self.payloads = payloads

    async def request(self, path, *, params=None, use_cache=True):
        from urllib.parse import unquote

        decoded = unquote(path)
        for key, value in self.payloads.items():
            if decoded.startswith(key):
                if isinstance(value, Exception):
                    raise value
                return value
        raise CocNotFound("missing")


async def test_service_suggestions():
    service = CocService(_FakeCoc({"clans/#C1/currentwar": _war_payload()}))
    targets = await service.suggestions("#C1")
    assert targets
    # The TH14 target with 2 stars is still "perfect-able" and open, so it ranks
    # first; the TH12 target is listed too.
    assert targets[0].position == 1
    assert {t.position for t in targets} == {1, 2}
    assert any(tag.open for tag in targets)


async def test_client_disabled_without_token():
    client = CocClient(None)
    with pytest.raises(CocDisabled):
        await client.request("players/%23P1")


async def test_client_error_mapping():
    async def handler(request: web.Request) -> web.Response:
        name = request.match_info["name"]
        if name == "http403":
            return web.Response(status=403)
        if name == "http404":
            return web.Response(status=404)
        if name == "http500":
            return web.Response(status=500)
        return web.json_response(PLAYER)

    app = web.Application()
    app.router.add_get("/players/{name}", handler)
    app.router.add_get("/{name}/suffix", handler)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "127.0.0.1", 0)
    await site.start()
    port = site._server.sockets[0].getsockname()[1]
    client = CocClient("token", base_url=f"http://127.0.0.1:{port}", cache_seconds=60)
    try:
        assert (await client.player("ok"))["tag"] == "#P1"
        assert (await client.player("ok"))["tag"] == "#P1"  # served from cache
        with pytest.raises(CocAuthError):
            await client.player("http403")
        with pytest.raises(CocNotFound):
            await client.player("http404")
        with pytest.raises(CocUnavailable):
            await client.player("http500")
    finally:
        await client.close()
        await runner.cleanup()


async def test_client_verifies_token():
    async def handler(_: web.Request) -> web.Response:
        return web.json_response({"items": []})

    app = web.Application()
    app.router.add_get("/locations", handler)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "127.0.0.1", 0)
    await site.start()
    port = site._server.sockets[0].getsockname()[1]
    client = CocClient("token", base_url=f"http://127.0.0.1:{port}")
    try:
        ok, status, _ = await client.verify()
        assert ok and status == 200
    finally:
        await client.close()
        await runner.cleanup()
