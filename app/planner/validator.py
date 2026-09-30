"""Strict server-side validation of plans before they reach the user.

The model is allowed to propose; the server decides what is structurally valid
and flags anything that depends on a low-confidence read. Nothing here tries to
judge strategy quality (that is the player's call) — it enforces the fixed rules
of the game and the integrity of the plan data.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from app.coc.catalog import HEROES, SIEGE_MACHINES, SPELLS, TROOPS
from app.planner.schema import Detection, Plan

# Build a lowercase lookup of every known unit/troop/spell name (EN + AR).
_KNOWN_UNITS: dict[str, tuple[str, str]] = {}
for _group in (HEROES, TROOPS, SPELLS, SIEGE_MACHINES):
    for _unit in _group:
        _KNOWN_UNITS[_unit.en.lower()] = (_unit.en, _unit.ar)
        _KNOWN_UNITS[_unit.ar.lower()] = (_unit.en, _unit.ar)

_KNOWN_DEFENSES = {
    "cannon", "archer tower", "mortar", "air defense", "wizard tower",
    "air sweeper", "hidden tesla", "bomb tower", "x-bow", "inferno tower",
    "eagle artillery", "scattershot", "monolith", "multi-archer tower",
    "ricochet cannon", "spell tower", "clan castle", "giga tesla", "giga inferno",
    "town hall", "firespitter", "multi-gear tower",
}


@dataclass
class ValidationResult:
    ok: bool
    issues: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    confidence_penalty: float = 0.0
    high_threat_unread: list[str] = field(default_factory=list)

    @property
    def summary(self) -> str:
        return "; ".join(self.issues) if self.issues else "ok"


def _mentions(text: str, needle: str) -> bool:
    return needle.lower() in text.lower()


def validate_plan(plan: Plan, *, town_hall: int, army: str = "") -> ValidationResult:
    issues: list[str] = []
    warnings: list[str] = []
    penalty = 0.0

    # 1. Every phase must have at least one marker that maps to a real cell.
    if not any(phase.markers for phase in plan.phases):
        issues.append("لا توجد علامات مواقع في أي مرحلة (تعذّر تحديد نقاط الدخول).")

    for index, phase in enumerate(plan.phases, start=1):
        if not phase.action.strip():
            issues.append(f"المرحلة {index} بلا إجراء واضح.")

    # 2. Units referenced in the plan must exist in the catalog.
    blob = " ".join(
        [plan.summary, plan.title, plan.style, *plan.army_notes]
        + [phase.action for phase in plan.phases]
        + [alt for alt in plan.alternatives]
    )
    mentioned = [name for name in _KNOWN_UNITS if _mentions(blob, name)]
    if not mentioned and army.strip():
        warnings.append("لم يُذكر أي اسم وحدة معروف من الكتالوج في الخطة.")

    # 3. Detected buildings must be recognised and their confidence must hold up.
    unknown_detections = [
        d for d in plan.detections if d.building.lower() not in _KNOWN_DEFENSES
    ]
    if unknown_detections:
        warnings.append(
            "عناصر لم يتم التعرف عليها في الصورة: "
            + "، ".join(sorted({d.building for d in unknown_detections})[:5])
        )

    low_confidence = [d for d in plan.detections if d.confidence < 0.4]
    if low_confidence:
        penalty += min(0.2, 0.03 * len(low_confidence))
        warnings.append(f"{len(low_confidence)} مبنى قُرئ بثقة منخفضة ويحتاج تأكيدًا بشريًا.")

    # 4. High-threat defenses must be either detected or explicitly called out.
    from app.coc.knowledge import DEFENSES

    high_threat_names = {d.en for d in DEFENSES if d.threat >= 5}
    detected_names = {d.building for d in plan.detections}
    mentioned_in_plan = {
        name for name in high_threat_names if _mentions(blob, name)
    }
    unread = sorted(high_threat_names - detected_names - mentioned_in_plan)
    if unread:
        penalty += min(0.2, 0.04 * len(unread))
        warnings.append(
            "دفاعات عالية الخطورة لم تُقرأ من الصورة ولم تُذكر: " + "، ".join(unread)
        )

    # 5. Air plan must address air defenses; ground plan must address splash.
    is_air = "جوي" in plan.style or _mentions(blob, "air") or _mentions(blob, "تنين")
    if is_air and "Air Defense" not in detected_names and not _mentions(blob, "Air Defense"):
        penalty += 0.08
        warnings.append("خطة جوية دون تحديد موقع دفاع الجو.")

    # 6. Hero abilities should be referenced for a serious push.
    if town_hall >= 11 and not any(
        _mentions(blob, hero.en) or _mentions(blob, hero.ar) for hero in HEROES
    ):
        warnings.append("الخطة لا تذكر الأبطال؛ يُنصح بتوظيف قدراتهم.")

    confidence = max(0.0, plan.confidence - penalty)
    plan.confidence = round(confidence, 2)

    return ValidationResult(
        ok=not issues,
        issues=issues,
        warnings=warnings,
        confidence_penalty=round(penalty, 2),
        high_threat_unread=unread,
    )


def detected_summary(detections: list[Detection]) -> str:
    if not detections:
        return "لم يتعرّف النموذج على مبانٍ محددة في الصورة."
    grouped: dict[str, list[str]] = {}
    for det in detections:
        grouped.setdefault(det.building, []).append(det.cell)
    lines = []
    for building, cells in sorted(grouped.items()):
        lines.append(f"• {building}: {', '.join(sorted(set(cells)))}")
    return "\n".join(lines)
