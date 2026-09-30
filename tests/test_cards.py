"""Cards, keyboards and wrapping helpers."""

from __future__ import annotations

from app.bot import keyboards
from app.bot.cards import (
    attacks_card,
    clan_card,
    members_card,
    plan_text,
    player_card,
    targets_card,
    war_card,
)
from app.coc.models import Clan, Player, War
from app.coc.service import CapitalSummary, Target
from app.planner.schema import parse_plan
from tests.test_planner import VALID

PLAYER = {
    "tag": "#P1",
    "name": "Ammar",
    "townHallLevel": 14,
    "trophies": 5000,
    "donations": 100,
    "warStars": 50,
    "league": {"name": "Legend"},
    "clan": {"tag": "#C1", "name": "Kings"},
    "heroes": [{"name": "Barbarian King", "level": 70, "maxLevel": 80, "village": "home"}],
}


def test_player_card_contains_core_fields():
    text = player_card(Player.from_api(PLAYER))
    assert "Ammar" in text and "#P1" in text
    assert "الملك البربري" not in text  # names stay in English from the API
    assert "Barbarian King" in text


def test_player_card_escapes_html():
    payload = dict(PLAYER, name="<script>")
    text = player_card(Player.from_api(payload))
    assert "<script>" not in text and "&lt;script&gt;" in text


def test_clan_and_members_cards():
    clan = Clan.from_api(
        {
            "tag": "#C1",
            "name": "Kings",
            "members": 2,
            "memberList": [
                {"tag": "#A", "name": "A", "role": "leader", "trophies": 10, "donations": 5},
                {"tag": "#B", "name": "B", "role": "member", "trophies": 5, "donations": 50},
            ],
        }
    )
    assert "Kings" in clan_card(clan)
    donations = members_card(clan, sort="donations")
    assert donations.index("B") < donations.index("A")


def test_war_card_and_attacks():
    from tests.test_coc import _war_payload

    war = War.from_api(_war_payload())
    text = war_card(war)
    assert "Kings" in text and "Rivals" in text
    assert "هجماتنا" in text
    attacks = attacks_card(war)
    assert "Ammar" in attacks


def test_targets_card():
    target = Target(1, "#E1", "Enemy", 14, 2, 60, 1, 0, True)
    text = targets_card([target])
    assert "Enemy" in text and "مفتوح" in text
    assert "لا توجد أهداف" in targets_card([])


def test_capital_card():
    summary = CapitalSummary(
        state="ongoing",
        start_time="20240101T000000.000Z",
        end_time="20240102T000000.000Z",
        capital_total_loot=12345,
        raids_completed=2,
        total_attacks=5,
        total_districts=8,
        offensive_reward=100,
        defensive_reward=50,
        members=({"name": "Ammar", "capitalResourcesLooted": 500},),
    )
    from app.bot.cards import capital_card

    assert "12345" in capital_card(summary).replace("٬", "")


def test_plan_text_renders_phases():
    plan = parse_plan(VALID)
    text = plan_text(plan)
    assert "خطة الهجوم" in text
    assert "1." in text and "فصل الجناح" in text


def test_keyboards_build_without_error():
    assert keyboards.main_menu().inline_keyboard
    assert keyboards.planner_goals().inline_keyboard
    assert keyboards.settings_menu().inline_keyboard
    assert keyboards.clan_menu("#C1").inline_keyboard
    assert keyboards.war_menu("#C1").inline_keyboard
    assert keyboards.library_menu([]).inline_keyboard
    assert keyboards.confirm_menu("yes", "no").inline_keyboard
