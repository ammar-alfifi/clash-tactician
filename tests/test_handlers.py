from app.handlers import _format_clan_profile, _format_war_room


def test_clan_profile_shows_war_log_visibility():
    text = _format_clan_profile(
        {"name": "نسور", "isWarLogPublic": False},
        "#2PYLQGR",
    )

    assert "سجل الحرب: خاص" in text


def test_clan_profile_counts_members_without_dumping_the_list():
    text = _format_clan_profile(
        {
            "name": "نسور",
            "isWarLogPublic": True,
            "members": [{"name": "أ"}, {"name": "ب"}, {"name": "ج"}],
        },
        "#2PYLQGR",
    )

    assert "الأعضاء: 3/50" in text
    assert "{'name'" not in text


def test_war_room_summary_counts_attacks_and_unattacked_members():
    text = _format_war_room(
        {
            "state": "inWar",
            "teamSize": 2,
            "clan": {
                "name": "النسور",
                "stars": 3,
                "destructionPercentage": 75.5,
                "members": [
                    {"name": "مهاجم", "attacks": [{"stars": 3}]},
                    {"name": "لاعب جديد", "attacks": []},
                ],
            },
            "opponent": {
                "name": "الخصم",
                "stars": 2,
                "destructionPercentage": 60,
            },
        }
    )

    assert "حرب جارية" in text
    assert "هجمات مسجلة من قبيلتك: 1" in text
    assert "أعضاء هاجموا: 1/2" in text
    assert "لاعب جديد" in text


def test_war_room_handles_no_current_war():
    assert _format_war_room({"state": "notInWar"}) == (
        "لا توجد حرب قبلية متاحة لهذه القبيلة حاليًا."
    )
