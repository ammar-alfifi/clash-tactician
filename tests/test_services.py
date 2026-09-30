"""Background jobs: reminders, war watcher and progress snapshots."""

from __future__ import annotations

from unittest.mock import AsyncMock

from app.coc.models import Player, War
from app.services import watcher
from app.services.snapshots import diff_payload, player_payload, record_player
from app.services.war_reminders import room_reminder_text, send_reminder
from tests.test_coc import _war_payload


class _Deps:
    def __init__(self, war: War):
        self.coc = AsyncMock()
        self.coc.war.return_value = war


async def test_room_reminder_lists_missing_members():
    deps = _Deps(War.from_api(_war_payload()))
    text = await room_reminder_text(deps, "#C1")
    assert text is not None
    assert "Sami" in text  # Sami has 0/2 attacks


async def test_room_reminder_all_attacks_done():
    payload = _war_payload()
    payload["clan"]["members"][1]["attacks"] = [
        {"attackerTag": "#P2", "defenderTag": "#E1", "stars": 3,
         "destructionPercentage": 100, "order": 2},
        {"attackerTag": "#P2", "defenderTag": "#E2", "stars": 2,
         "destructionPercentage": 80, "order": 3},
    ]
    # Give both clan members a second attack too, so nobody is missing.
    payload["clan"]["members"][0]["attacks"].append(
        {"attackerTag": "#P1", "defenderTag": "#E2", "stars": 2,
         "destructionPercentage": 80, "order": 4}
    )
    deps = _Deps(War.from_api(payload))
    assert await room_reminder_text(deps, "#C1") is None


async def test_send_reminder_marks_and_sends():
    deps = _Deps(War.from_api(_war_payload()))
    bot = AsyncMock()
    assert await send_reminder(bot, deps, -100, "#C1")
    bot.send_message.assert_awaited_once()


def test_player_payload_and_diff():
    old = player_payload(
        Player.from_api({"tag": "#P1", "name": "A", "trophies": 100, "donations": 5})
    )
    new = player_payload(
        Player.from_api(
            {
                "tag": "#P1",
                "name": "A",
                "trophies": 150,
                "donations": 3,
                "heroes": [
                    {"name": "Archer Queen", "level": 40, "maxLevel": 50, "village": "home"}
                ],
            }
        )
    )
    deltas = diff_payload(old, new)
    assert deltas["trophies"] == 50
    assert deltas["donations"] == -2
    assert deltas["heroes"]["Archer Queen"] == (0, 40)


async def test_record_player_skips_unchanged(database):
    from app.storage.repositories import SnapshotRepo

    class _SnapDeps:
        snapshots = SnapshotRepo(database)

    deps = _SnapDeps()
    player = Player.from_api({"tag": "#P1", "name": "A", "trophies": 100})
    assert await record_player(deps, player) is True
    assert await record_player(deps, player) is False
    changed = Player.from_api({"tag": "#P1", "name": "A", "trophies": 200})
    assert await record_player(deps, changed) is True


def test_war_transition_message():
    war = War.from_api(_war_payload())
    assert "بدأت" in watcher._transition_message(war, "notInWar")
    ended = War.from_api(_war_payload("warEnded"))
    assert "انتهت" in watcher._transition_message(ended, "inWar")
    assert watcher._transition_message(war, "inWar") is None


def test_progress_message():
    message = watcher._progress_message(
        "Ammar", {"trophies": 30, "heroes": {"Archer Queen": (39, 40)}}
    )
    assert "Ammar" in message and "Archer Queen" in message
    assert watcher._progress_message("Ammar", {}) is None
