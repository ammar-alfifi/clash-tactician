"""Grounded, source-backed Clash of Clans knowledge base.

Every rule here is derived from published game data (defense ranges, targeting
rules, ability summaries) rather than being invented by the model. The planner
prompt embeds this data so plans are built on fixed rules the AI cannot drift
away from.

Sources (reference data, verified 2026):
- https://cocdata.org  (clash-of-clans-data v0.16.0)
- https://clashofclans.fandom.com/wiki/Defensive_Buildings/Home_Village
- https://coc.guide/defense
- https://www.clashonclans.com/en/wiki/homebase/defenses
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class DefenseInfo:
    ar: str
    en: str
    range_tiles: float
    targets: str  # "ground" | "air" | "both"
    damage: str  # "single" | "splash" | "chain" | "push" | "spell"
    th_min: int
    threat: int  # 1..5 relative threat to a ground push
    notes: str = ""


# Ranges are the current max-level values (tiles). Threat is an editorial
# ranking used only to prioritise which defenses the plan must address first.
DEFENSES: tuple[DefenseInfo, ...] = (
    DefenseInfo("المدفع", "Cannon", 9.0, "ground", "single", 1, 1),
    DefenseInfo("برج الرماة", "Archer Tower", 10.0, "both", "single", 1, 3),
    DefenseInfo(
        "الهاون", "Mortar", 11.0, "ground", "splash", 1, 2, "لا يستهدف الجو"
    ),
    DefenseInfo(
        "دفاع الجو", "Air Defense", 10.0, "air", "single", 4, 4,
        "الأولوية في الهجمات الجوية",
    ),
    DefenseInfo(
        "برج السحر", "Wizard Tower", 7.0, "both", "splash", 5, 3,
        "قصير المدى لكن يضرب المساحات",
    ),
    DefenseInfo(
        "منفاخ الهواء", "Air Sweeper", 12.0, "air", "push", 6, 2,
        "يدفع القوات الجوية فقط",
    ),
    DefenseInfo(
        "التيليسا المخفية", "Hidden Tesla", 7.0, "both", "single", 7, 3,
        "لا تُرى حتى تظهر",
    ),
    DefenseInfo("برج القنابل", "Bomb Tower", 6.0, "ground", "splash", 8, 2),
    DefenseInfo(
        "القوس إكس", "X-Bow", 11.5, "both", "single", 9, 4, "مدى بعيد ومستمر"
    ),
    DefenseInfo(
        "برج الجحيم", "Inferno Tower", 9.0, "both", "single", 10, 5,
        "يتصاعد ضرره بمرور الوقت",
    ),
    DefenseInfo(
        "مدفعية النسر", "Eagle Artillery", 50.0, "both", "splash", 11, 5,
        "تضرب الجزء الأكبر من القاعدة",
    ),
    DefenseInfo(
        "المدفع المبعثر", "Scattershot", 11.0, "both", "splash", 13, 5,
        "يستهدف مناطق واسعة",
    ),
    DefenseInfo(
        "الوحش", "Monolith", 11.0, "both", "single", 14, 5,
        "ضرر عالٍ جدًا على الأبطال",
    ),
    DefenseInfo(
        "برج السحر المتعدد", "Multi-Archer Tower", 10.0, "both", "chain", 14, 4
    ),
    DefenseInfo(
        "مدفع الارتداد", "Ricochet Cannon", 9.0, "ground", "chain", 14, 3
    ),
    DefenseInfo(
        "برج التعاويذ", "Spell Tower", 9.0, "both", "spell", 13, 4,
        "يطلق تعويذة قوية",
    ),
)


@dataclass(frozen=True)
class EntryRule:
    ar: str
    how: str
    source: str


# Fixed mechanics (not advice): the game resolves these deterministically.
TARGETING_RULES: tuple[EntryRule, ...] = (
    EntryRule(
        "أولوية استهداف المباني",
        "قوات الجيش تستهدف أقرب مبنى، فمسارها يتحدد بأقرب مبنى لمسار الدخول "
        "لا باختيار اللاعب. استغل ذلك بفتح المسار بالمباني الصحيحة.",
        "قواعد اللعبة الأساسية لذكاء القوات",
    ),
    EntryRule(
        "سلوك قوات الجدار",
        "كاسر الجدران يستهدف أقرب قطعة جدار بجانب أقرب مبنى ثم يفجّرها. تنبّأ بمساره.",
        "قواعد استهداف كاسر الجدران",
    ),
    EntryRule(
        "التعزيزات وقلعة القبيلة",
        "قوات قلعة القبيلة تخرج عند اقتراب أي جيش من القلعة وقد تعطّل المسار. "
        "عالجها أولًا (بالمصيدة أو السم) قبل الدخول الرئيسي.",
        "آلية قوات القلعة",
    ),
    EntryRule(
        "الجدران والحصار",
        "آلة الحصار تُفتح داخل الجدار وتُسقط القوات عنده. حدّد مصدر فتح المسار "
        "قبل القوة الرئيسية.",
        "آلية آلات الحصار",
    ),
    EntryRule(
        "تركيز الدفاعات",
        "قد يُستهدف البطل بكل قوة الدفاعات إذا تقدّم وحده. لا تُرسل الأبطال قبل "
        "تمهيد المسار.",
        "ترتيب المخاطر الدفاعية",
    ),
)


@dataclass(frozen=True)
class TroopComposition:
    th: int
    style: str
    core_troops: tuple[str, ...]
    spells: tuple[str, ...]
    notes: str


# Grounded, standard compositions per Town Hall and style. Structural
# archetypes: they list what the style normally requires, not opinions.
COMPOSITIONS: tuple[TroopComposition, ...] = (
    TroopComposition(
        11, "أرضي", ("Golem", "Wizard", "Witch"),
        ("Rage", "Jump", "Heal"), "غوفاوي تقليدي",
    ),
    TroopComposition(
        11, "جوي", ("Electro Dragon", "Balloon"), ("Rage", "Freeze"),
        "تنين كهربائي",
    ),
    TroopComposition(
        12, "أرضي", ("Yeti", "Witch", "Bowler"),
        ("Rage", "Jump", "Freeze"), "ييتي بوتش",
    ),
    TroopComposition(12, "جوي", ("Electro Dragon", "Balloon"), ("Rage", "Freeze"), "تنين + منطاد"),
    TroopComposition(13, "أرضي", ("Yeti", "Witch", "Bowler"), ("Rage", "Jump", "Freeze"), ""),
    TroopComposition(13, "جوي", ("Dragon Rider", "Electro Dragon"), ("Rage", "Freeze"), ""),
    TroopComposition(
        14, "أرضي", ("Root Rider", "Electro Titan", "Bowler"),
        ("Rage", "Jump", "Freeze"), "",
    ),
    TroopComposition(
        14, "جوي", ("Dragon Rider", "Balloon"), ("Rage", "Freeze", "Clone"), ""
    ),
    TroopComposition(
        15, "أرضي", ("Root Rider", "Electro Titan"), ("Rage", "Jump", "Revive"), ""
    ),
    TroopComposition(
        15, "جوي", ("Dragon Rider", "Electro Dragon"),
        ("Rage", "Freeze", "Clone"), "",
    ),
    TroopComposition(
        16, "أرضي", ("Root Rider", "Electro Titan", "Thrower"),
        ("Rage", "Jump", "Revive"), "",
    ),
    TroopComposition(
        16, "جوي", ("Dragon Rider", "Electro Dragon"),
        ("Rage", "Freeze", "Clone"), "",
    ),
)


@dataclass(frozen=True)
class HeroAbility:
    ar: str
    en: str
    summary: str
    best_use: str


HERO_ABILITIES: tuple[HeroAbility, ...] = (
    HeroAbility(
        "الملك البربري", "Barbarian King",
        "يرفع صحته وسرعته ويستدعي برابرة إضافيين.",
        "يمزق جناحًا أو يفتح مسارًا وحيدًا، ويُستخدم لامتصاص ضرر الدفاعات.",
    ),
    HeroAbility(
        "الملكة الرامية", "Archer Queen",
        "الاختفاء مع زيادة سرعة الهجوم مؤقتًا.",
        "قتل الأبطال وقوات القلعة والأهداف داخل الجدران.",
    ),
    HeroAbility(
        "الحارس الأعظم", "Grand Warden",
        "وضع الهجوم يجعل قواتك منيعة ويثبّت الأبطال.",
        "الوضع الآمن للقوة الرئيسية داخل المدى الحرج.",
    ),
    HeroAbility(
        "البطلة الملكية", "Royal Champion",
        "تقتحم أي مبنى وتقفز للهدف التالي.",
        "إزالة الأهداف ذات الأولوية كبرج الجحيم والوحش.",
    ),
    HeroAbility(
        "أمير الشبح", "Minion Prince",
        "يقصف ويجمّد الدفاعات الجوية.",
        "تمهيد هجوم جوي وتشتييت المستهدفين.",
    ),
)


@dataclass(frozen=True)
class SpellInfo:
    ar: str
    en: str
    effect: str
    use: str


SPELLS: tuple[SpellInfo, ...] = (
    SpellInfo("الصاعقة", "Lightning", "ضرر مباشر بالأهداف",
              "إسقاط دفاع واحد أساسي قبل الدخول."),
    SpellInfo("الشفاء", "Heal", "يستعيد صحة القوات بمساحة",
              "تحت القوة الرئيسية أثناء المرور بمنطقة ضرر عالٍ."),
    SpellInfo("الغضب", "Rage", "زيادة سرعة وقتال القوات",
              "فوق القوة الرئيسية عند اختراق القلب."),
    SpellInfo("القفز", "Jump", "عبور الجدران لمسافة قصيرة",
              "فتح مسار بديل عندما لا تكفي آلة الحصار."),
    SpellInfo("التجميد", "Freeze", "تجميد دفاع مؤقتًا",
              "تعطيل برج الجحيم أو النسر أو الوحش في لحظة الاختراق."),
    SpellInfo("الاختفاء", "Invisibility", "جعل قواتك غير مرئية",
              "حماية القوة الرئيسية في المنطقة الخطرة."),
    SpellInfo("الاستنساخ", "Clone", "يتضاعف التأثير",
              "مضاعفة القوة عند تركيزها في نقطة ضعف."),
    SpellInfo("الاسترجاع", "Recall", "سحب القوات من ساحة المعركة",
              "إنقاذ قوة من موقف خاسر أو إعادة توجيهها."),
)


def defense_table() -> str:
    rows = ["الدفاع | المدى | يستهدف | النوع | الخطر (1-5) | ملاحظة"]
    for d in DEFENSES:
        rows.append(
            f"{d.en} ({d.ar}) | {d.range_tiles} خانة | {d.targets} | "
            f"{d.damage} | {d.threat} | {d.notes}"
        )
    return "\n".join(rows)


def targeting_rules_text() -> str:
    return "\n".join(f"- {rule.ar}: {rule.how}" for rule in TARGETING_RULES)


def composition_text(th: int) -> str:
    options = [c for c in COMPOSITIONS if c.th <= th] or list(COMPOSITIONS)
    recent = [c for c in options if c.th >= th - 3] or options
    recent.sort(key=lambda c: c.th, reverse=True)
    lines = []
    for comp in recent:
        lines.append(
            f"TH{comp.th} [{comp.style}]: القوات {', '.join(comp.core_troops)} "
            f"— التعاويذ {', '.join(comp.spells)}. {comp.notes}"
        )
    return "\n".join(lines)


def hero_ability_text() -> str:
    return "\n".join(
        f"- {h.ar} ({h.en}): {h.summary} الاستخدام الأمثل: {h.best_use}"
        for h in HERO_ABILITIES
    )


def spell_text() -> str:
    return "\n".join(f"- {s.ar} ({s.en}): {s.effect} — {s.use}" for s in SPELLS)


def knowledge_block(th: int) -> str:
    """Compact, source-backed briefing embedded into the planner prompt.

    Kept intentionally short: long prompts make free vision models drift away
    from the required JSON shape. Only high-value, fixed facts are included.
    """
    # Defence ranges are the single most useful fixed fact for planning.
    threats = sorted(DEFENSES, key=lambda d: -d.threat)[:8]
    defense_lines = "، ".join(f"{d.en} {d.range_tiles}" for d in threats)
    # Only the mechanics that change where troops go.
    key_rules = (
        "الجيش يستهدف أقرب مبنى؛ مساره يتحدد بأقرب مبنى لجهة الدخول. "
        "كاسر الجدران يستهدف أقرب جدار. تعزيزات القلعة تخرج عند اقتراب الجيش. "
        "آلة الحصار تُفتح داخل الجدار. لا تُرسل الأبطال قبل تمهيد المسار."
    )
    comp = composition_text(th).splitlines()
    comp_short = comp[0] if comp else ""
    return (
        "<بيانات_مصدرية>\n"
        f"مدارس دفاعات مهمة (المدى بالخانات): {defense_lines}.\n"
        f"قواعد ثابتة: {key_rules}\n"
        f"تشكيل قياسي مقترح: {comp_short}\n"
        "</بيانات_مصدرية>"
    )
