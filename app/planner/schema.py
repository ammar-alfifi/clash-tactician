"""Structured attack-plan schema with server-side validation."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from typing import Any

from app.core.errors import PlanError

MARKER_KINDS = {"entry", "target", "spell", "hero", "cleanup", "danger", "rally", "siege"}
GOALS = {
    "three_stars": "ثلاث نجوم",
    "two_stars": "ضمان نجمتين",
    "one_star": "ضمان نجمة",
    "cleanup": "تنظيف",
    "practice": "تدريب",
}

MAX_PHASES = 6
MAX_MARKERS = 6


@dataclass
class Marker:
    x: float
    y: float
    kind: str = "target"
    label: str = ""


@dataclass
class Phase:
    name: str
    action: str
    reason: str = ""
    markers: list[Marker] = field(default_factory=list)
    depends_on: list[str] = field(default_factory=list)


@dataclass
class Plan:
    goal: str
    summary: str
    confidence: float
    phases: list[Phase]
    risks: list[str] = field(default_factory=list)
    alternatives: list[str] = field(default_factory=list)
    uncertainties: list[str] = field(default_factory=list)
    army_notes: list[str] = field(default_factory=list)
    title: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False)

    @property
    def confidence_label(self) -> str:
        if self.confidence >= 0.75:
            return "عالية"
        if self.confidence >= 0.5:
            return "متوسطة"
        return "منخفضة"

    @property
    def goal_label(self) -> str:
        return GOALS.get(self.goal, self.goal)


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def _as_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _as_str_list(value: Any, limit: int = 8) -> list[str]:
    if not isinstance(value, list):
        return []
    result: list[str] = []
    for item in value:
        text = str(item).strip()
        if text:
            result.append(text[:300])
        if len(result) >= limit:
            break
    return result


def _parse_markers(value: Any) -> list[Marker]:
    if not isinstance(value, list):
        return []
    markers: list[Marker] = []
    for item in value:
        if not isinstance(item, dict):
            continue
        kind = str(item.get("kind", "target")).strip().lower()
        if kind not in MARKER_KINDS:
            kind = "target"
        markers.append(
            Marker(
                x=_clamp(_as_float(item.get("x")), 0.0, 1.0),
                y=_clamp(_as_float(item.get("y")), 0.0, 1.0),
                kind=kind,
                label=str(item.get("label", ""))[:60],
            )
        )
        if len(markers) >= MAX_MARKERS:
            break
    return markers


def parse_plan(raw: str | dict[str, Any]) -> Plan:
    data = _loads(raw) if isinstance(raw, str) else raw
    if not isinstance(data, dict):
        raise PlanError("صيغة الخطة غير صحيحة.")

    phases_raw = data.get("phases")
    if not isinstance(phases_raw, list) or not phases_raw:
        raise PlanError("الخطة لا تحتوي على مراحل.")

    phases: list[Phase] = []
    for item in phases_raw:
        if not isinstance(item, dict):
            continue
        action = str(item.get("action", "")).strip()
        if not action:
            continue
        phases.append(
            Phase(
                name=str(item.get("name", "")).strip()[:80] or f"مرحلة {len(phases) + 1}",
                action=action[:800],
                reason=str(item.get("reason", "")).strip()[:500],
                markers=_parse_markers(item.get("markers")),
                depends_on=_as_str_list(item.get("depends_on"), limit=4),
            )
        )
        if len(phases) >= MAX_PHASES:
            break

    if not phases:
        raise PlanError("الخطة لا تحتوي على خطوات صالحة.")

    goal = str(data.get("goal", "three_stars")).strip()
    if goal not in GOALS:
        goal = "three_stars"

    confidence = _clamp(_as_float(data.get("confidence"), 0.5), 0.0, 1.0)
    if confidence > 1:
        confidence = confidence / 100 if confidence <= 100 else 1.0

    return Plan(
        goal=goal,
        summary=str(data.get("summary", "")).strip()[:700],
        confidence=confidence,
        phases=phases,
        risks=_as_str_list(data.get("risks")),
        alternatives=_as_str_list(data.get("alternatives")),
        uncertainties=_as_str_list(data.get("uncertainties")),
        army_notes=_as_str_list(data.get("army_notes")),
        title=str(data.get("title", "")).strip()[:80],
    )


def plan_from_stored(text: str) -> Plan:
    return parse_plan(text)


def _loads(raw: str) -> Any:
    text = raw.strip()
    if text.startswith("```"):
        text = text.strip("`")
        if text.lower().startswith("json"):
            text = text[4:]
    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1 and end > start:
        text = text[start : end + 1]
    try:
        return json.loads(text)
    except json.JSONDecodeError as exc:
        raise PlanError("تعذّر قراءة الخطة من رد النموذج.") from exc
