"""Grounded Clash of Clans catalog used by the AI planner and validators.

Values are intentionally kept in one place so they can be updated when the
game changes. Levels are approximate reference points, not authoritative.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Unit:
    id: int
    en: str
    ar: str
    housing: int
    th: int  # town hall required
    kind: str  # troop | spell | siege | pet | hero


HEROES: tuple[Unit, ...] = (
    Unit(0, "Barbarian King", "الملك البربري", 0, 7, "hero"),
    Unit(0, "Archer Queen", "الملكة الرامية", 0, 9, "hero"),
    Unit(0, "Grand Warden", "الحارس الأعظم", 0, 11, "hero"),
    Unit(0, "Royal Champion", "البطلة الملكية", 0, 13, "hero"),
    Unit(0, "Minion Prince", "أمير الشبح", 0, 15, "hero"),
)

MAX_HERO_LEVELS: dict[int, dict[str, int]] = {
    9: {"Barbarian King": 30, "Archer Queen": 30},
    10: {"Barbarian King": 40, "Archer Queen": 40},
    11: {"Barbarian King": 50, "Archer Queen": 50, "Grand Warden": 20},
    12: {"Barbarian King": 65, "Archer Queen": 65, "Grand Warden": 40},
    13: {"Barbarian King": 75, "Archer Queen": 75, "Grand Warden": 50, "Royal Champion": 25},
    14: {"Barbarian King": 80, "Archer Queen": 80, "Grand Warden": 55, "Royal Champion": 30},
    15: {"Barbarian King": 90, "Archer Queen": 90, "Grand Warden": 60, "Royal Champion": 40},
    16: {"Barbarian King": 95, "Archer Queen": 95, "Grand Warden": 65, "Royal Champion": 45},
    17: {
        "Barbarian King": 100,
        "Archer Queen": 100,
        "Grand Warden": 70,
        "Royal Champion": 50,
        "Minion Prince": 60,
    },
}

TROOPS: tuple[Unit, ...] = (
    Unit(0, "Barbarian", "البربري", 1, 1, "troop"),
    Unit(1, "Archer", "الرامية", 1, 1, "troop"),
    Unit(2, "Giant", "العملاق", 5, 1, "troop"),
    Unit(3, "Goblin", "الغوبلن", 1, 1, "troop"),
    Unit(4, "Wall Breaker", "كاسر الجدران", 2, 2, "troop"),
    Unit(5, "Balloon", "المنطاد", 5, 4, "troop"),
    Unit(6, "Wizard", "الساحر", 4, 5, "troop"),
    Unit(7, "Healer", "المعالجة", 14, 6, "troop"),
    Unit(8, "Dragon", "التنين", 20, 7, "troop"),
    Unit(9, "P.E.K.K.A", "بيكا", 25, 8, "troop"),
    Unit(10, "Baby Dragon", "التنين الصغير", 10, 9, "troop"),
    Unit(11, "Miner", "المنقّب", 6, 10, "troop"),
    Unit(12, "Electro Dragon", "التنين الكهربائي", 30, 11, "troop"),
    Unit(13, "Yeti", "الييتي", 18, 12, "troop"),
    Unit(14, "Dragon Rider", "فارس التنين", 25, 13, "troop"),
    Unit(15, "Electro Titan", "التيتان الكهربائي", 32, 14, "troop"),
    Unit(16, "Root Rider", "راكب الجذور", 20, 15, "troop"),
    Unit(17, "Apprentice Warden", "الحارس المتدرب", 24, 15, "troop"),
    Unit(18, "Thrower", "القاذف", 16, 17, "troop"),
)

SPELLS: tuple[Unit, ...] = (
    Unit(0, "Lightning Spell", "الصاعقة", 1, 5, "spell"),
    Unit(1, "Healing Spell", "الشفاء", 2, 6, "spell"),
    Unit(2, "Rage Spell", "الغضب", 2, 7, "spell"),
    Unit(3, "Jump Spell", "القفز", 2, 9, "spell"),
    Unit(4, "Freeze Spell", "التجميد", 1, 9, "spell"),
    Unit(5, "Clone Spell", "الاستنساخ", 3, 10, "spell"),
    Unit(6, "Invisibility Spell", "الاختفاء", 1, 11, "spell"),
    Unit(7, "Recall Spell", "الاسترجاع", 2, 13, "spell"),
    Unit(8, "Revive Spell", "الإحياء", 2, 15, "spell"),
    Unit(9, "Overgrowth Spell", "النمو الزائد", 2, 16, "spell"),
    Unit(10, "Poison Spell", "السم", 1, 8, "spell"),
    Unit(11, "Earthquake Spell", "الزلزال", 1, 8, "spell"),
    Unit(12, "Haste Spell", "السرعة", 1, 8, "spell"),
    Unit(13, "Skeleton Spell", "الهيكل العظمي", 1, 9, "spell"),
    Unit(14, "Bat Spell", "الخفافيش", 1, 10, "spell"),
    Unit(15, "Ice Block Spell", "كتلة الجليد", 1, 17, "spell"),
)

SIEGE_MACHINES: tuple[Unit, ...] = (
    Unit(0, "Wall Wrecker", "محطم الجدران", 1, 12, "siege"),
    Unit(1, "Battle Blimp", "المنطاد الحربي", 1, 12, "siege"),
    Unit(2, "Stone Slammer", "المطرقة الحجرية", 1, 12, "siege"),
    Unit(3, "Siege Barracks", "ثكنة الحصار", 1, 13, "siege"),
    Unit(4, "Log Launcher", "قاذف الجذوع", 1, 13, "siege"),
    Unit(5, "Flame Flinger", "قاذف اللهب", 1, 14, "siege"),
    Unit(6, "Battle Drill", "المثقاب الحربي", 1, 15, "siege"),
    Unit(7, "Troop Launcher", "قاذف القوات", 1, 16, "siege"),
)

PETS: tuple[Unit, ...] = (
    Unit(0, "L.A.S.S.I", "لاسي", 0, 14, "pet"),
    Unit(0, "Electro Owl", "البومة الكهربائية", 0, 14, "pet"),
    Unit(0, "Mighty Yak", "الياك القوي", 0, 14, "pet"),
    Unit(0, "Unicorn", "وحيد القرن", 0, 14, "pet"),
    Unit(0, "Frosty", "فروستي", 0, 15, "pet"),
    Unit(0, "Diggy", "ديغي", 0, 15, "pet"),
    Unit(0, "Poison Lizard", "سحلية السم", 0, 15, "pet"),
    Unit(0, "Phoenix", "العنقاء", 0, 15, "pet"),
    Unit(0, "Spirit Fox", "الثعلب الروحي", 0, 15, "pet"),
    Unit(0, "Angry Jelly", "الهلام الغاضب", 0, 16, "pet"),
    Unit(0, "Sneezy", "سنيزي", 0, 16, "pet"),
)

_KNOWN_AR: dict[str, str] = {}
for _group in (HEROES, TROOPS, SPELLS, SIEGE_MACHINES, PETS):
    for _unit in _group:
        _KNOWN_AR[_unit.en.lower()] = _unit.ar


def arabic_name(english: str) -> str:
    return _KNOWN_AR.get(english.strip().lower(), english)


def catalog_prompt(include_heroes_upto: int = 17) -> str:
    """Compact catalog text embedded in AI prompts."""
    lines: list[str] = []

    def _fmt(units: tuple[Unit, ...], label: str) -> None:
        names = ", ".join(f"{u.en} ({u.ar})" for u in units if u.th <= include_heroes_upto)
        lines.append(f"{label}: {names}")

    _fmt(HEROES, "Heroes")
    _fmt(TROOPS, "Troops")
    _fmt(SPELLS, "Spells")
    _fmt(SIEGE_MACHINES, "Siege machines")
    _fmt(PETS, "Pets")
    return "\n".join(lines)


def max_hero_level(th: int, hero: str) -> int | None:
    table = MAX_HERO_LEVELS.get(th)
    if not table:
        return None
    return table.get(hero)
