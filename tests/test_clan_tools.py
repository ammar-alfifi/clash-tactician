from app.clan_tools import (
    format_clan_members,
    format_clan_stats,
    format_war_reminder,
    format_war_targets,
)


def _war() -> dict:
    return {
        "state": "inWar",
        "teamSize": 2,
        "clan": {
            "tag": "#AAA",
            "name": "قبيلتنا",
            "stars": 5,
            "destructionPercentage": 80.0,
            "members": [
                {
                    "name": "مهاجم",
                    "townHallLevel": 12,
                    "mapPosition": 1,
                    "attacks": [
                        {
                            "defenderTag": "#E1",
                            "stars": 3,
                            "destructionPercentage": 100,
                        }
                    ],
                },
                {"name": "متردد", "townHallLevel": 11, "mapPosition": 2, "attacks": []},
            ],
        },
        "opponent": {
            "tag": "#BBB",
            "name": "الخصم",
            "stars": 2,
            "destructionPercentage": 50.0,
            "members": [
                {"tag": "#E1", "name": "هدف قوي", "townHallLevel": 13, "mapPosition": 1},
                {"tag": "#E2", "name": "هدف سهل", "townHallLevel": 10, "mapPosition": 2},
            ],
        },
    }


def test_clan_members_lists_levels_roles_and_distribution():
    clan = {
        "name": "النسور",
        "tag": "#AAA",
        "clanLevel": 10,
        "members": [
            {"name": "قائدنا", "role": "leader", "townHallLevel": 15, "trophies": 5000,
             "donations": 800, "clanRank": 1},
            {"name": "عضو", "role": "member", "townHallLevel": 12, "trophies": 3000,
             "donations": 100, "clanRank": 2},
        ],
    }

    text = format_clan_members(clan, "#AAA")

    assert "أعضاء النسور" in text
    assert "توزيع قاعات المدينة: قاعة 15: 1 · قاعة 12: 1" in text
    assert "قائد 1" in text
    assert "عضو 1" in text
    assert "قائدنا" in text


def test_clan_members_handles_empty_roster():
    assert "لا تتوفر قائمة أعضاء" in format_clan_members({"members": []}, "#AAA")


def test_war_targets_orders_available_targets_and_pending_attacks():
    text = format_war_targets(_war(), "#AAA")

    assert "أهداف الحرب" in text
    assert "لم تُحسم بثلاث نجوم: 1" in text
    assert "هدف سهل" in text
    assert "لم تُهاجَم بعد" in text
    assert "متردد: 2 متبقية" in text
    assert "مهاجم: 1 متبقية" in text


def test_war_targets_handles_no_war():
    assert format_war_targets({"state": "notInWar"}).startswith("لا توجد حرب")


def test_clan_stats_includes_leaderboards_and_war_performance():
    clan = {
        "name": "النسور",
        "tag": "#AAA",
        "clanLevel": 8,
        "members": 2,
        "clanPoints": 30000,
        "members_list": [],
        "members_data": [],
        "warLeague": {"name": "دوري ذهبي"},
    }
    # The API nests members under "members"; supply the ranking data there.
    clan["members"] = [
        {"name": "غني", "trophies": 5200, "donations": 900, "clanCapitalContributions": 5000},
        {"name": "كريم", "trophies": 4100, "donations": 1500, "clanCapitalContributions": 1000},
    ]

    text = format_clan_stats(clan, _war())

    assert "إحصاءات وترتيب النسور" in text
    assert "أكثر التبرعات" in text
    assert "كريم — 1500 وحدة" in text
    assert "أفضل المهاجمين" in text
    assert "مهاجم — 3⭐" in text


def test_war_reminder_lists_pending_and_stops_when_done():
    text = format_war_reminder(_war())

    assert text is not None
    assert "متردد" in text
    assert "unsubscribe" in text

    done = _war()
    done["clan"]["members"][0]["attacks"].append(
        {"defenderTag": "#E2", "stars": 2, "destructionPercentage": 60}
    )
    done["clan"]["members"][1]["attacks"] = [
        {"defenderTag": "#E2", "stars": 2, "destructionPercentage": 60},
        {"defenderTag": "#E2", "stars": 1, "destructionPercentage": 30},
    ]
    assert format_war_reminder(done) is None
    assert format_war_reminder({"state": "preparation"}) is None
