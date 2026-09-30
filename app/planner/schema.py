"""Structured attack-plan schema with server-side validation."""

from __future__ import annotations

import json
import re
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

# A 4x4 grid reduces coordinate guessing: the model names a cell, the server
# turns it into a point. This is materially more reliable than free x/y values.
GRID_SIZE = 4

MAX_PHASES = 6
MAX_MARKERS = 6
MAX_DETECTIONS = 24

# Placeholder values some models echo from the schema instead of filling in.
PLACEHOLDERS = {"..", "...", "؟", "?", "n/a", "na", "-", "غير محدد", "tbd"}


def _is_placeholder(value: str) -> bool:
    return value.strip().lower() in PLACEHOLDERS

# Threat weighting used by the server-side validator.
DEFENSE_THREATS = {
    "Eagle Artillery": 5,
    "Monolith": 5,
    "Inferno Tower": 5,
    "Scattershot": 5,
    "Air Defense": 4,
    "X-Bow": 4,
    "Spell Tower": 4,
    "Multi-Archer Tower": 4,
    "Wizard Tower": 3,
    "Archer Tower": 3,
    "Hidden Tesla": 3,
    "Ricochet Cannon": 3,
    "Mortar": 2,
    "Bomb Tower": 2,
    "Air Sweeper": 2,
    "Cannon": 1,
}



@dataclass
class Marker:
    x: float
    y: float
    kind: str = "target"
    label: str = ""
    cell: str = ""


@dataclass
class Detection:
    """A building the model believes it saw, at a coarse grid cell."""

    building: str
    cell: str
    confidence: float = 0.5
    th_level: int | None = None
    air: bool = False


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
    detections: list[Detection] = field(default_factory=list)
    style: str = ""
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


def cell_to_point(cell: str) -> tuple[float, float] | None:
    """Convert a grid label like ``B3`` into a normalized centre point.

    Rows are labelled top-to-bottom with letters (A..D for a 4x4 grid), columns
    with digits (1..4 left-to-right).
    """
    if not cell:
        return None
    text = cell.strip().upper()
    if len(text) < 2:
        return None
    letter, digits = text[0], text[1:]
    if not letter.isalpha() or not digits.isdigit():
        return None
    row = ord(letter) - ord("A")
    col = int(digits) - 1
    if not (0 <= row < GRID_SIZE and 0 <= col < GRID_SIZE):
        return None
    x = (col + 0.5) / GRID_SIZE
    y = (row + 0.5) / GRID_SIZE
    return x, y


def _valid_cell(cell: str) -> bool:
    return cell_to_point(cell) is not None


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
        cell = str(item.get("cell", "")).strip().upper()
        point = cell_to_point(cell)
        if point is not None:
            x, y = point
        else:
            cell = ""
            x = _clamp(_as_float(item.get("x"), 0.5), 0.0, 1.0)
            y = _clamp(_as_float(item.get("y"), 0.5), 0.0, 1.0)
        markers.append(
            Marker(
                x=x,
                y=y,
                kind=kind,
                label=str(item.get("label", ""))[:60],
                cell=cell,
            )
        )
        if len(markers) >= MAX_MARKERS:
            break
    return markers


def _parse_detections(value: Any) -> list[Detection]:
    if not isinstance(value, list):
        return []
    detections: list[Detection] = []
    for item in value:
        if not isinstance(item, dict):
            continue
        building = str(item.get("building", "")).strip()[:60]
        cell = str(item.get("cell", "")).strip().upper()
        if not building or _is_placeholder(building) or not _valid_cell(cell):
            continue
        level = item.get("level")
        try:
            level_val = int(level) if level is not None else None
        except (TypeError, ValueError):
            level_val = None
        detections.append(
            Detection(
                building=building,
                cell=cell,
                confidence=_clamp(_as_float(item.get("confidence"), 0.5), 0.0, 1.0),
                th_level=level_val,
                air=bool(item.get("air", False)),
            )
        )
        if len(detections) >= MAX_DETECTIONS:
            break
    return detections


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
        name = str(item.get("name", "")).strip()
        if not action or _is_placeholder(action):
            continue
        if _is_placeholder(name):
            name = ""
        phases.append(
            Phase(
                name=name[:80] or f"مرحلة {len(phases) + 1}",
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
        detections=_parse_detections(data.get("detections")),
        style=str(data.get("style", "")).strip()[:40],
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
    # Models (esp. NVIDIA) often wrap the JSON in prose. Prefer a fenced block,
    # then fall back to the first balanced object.
    block = _extract_fenced_json(raw)
    if block is not None:
        return block
    candidate = _extract_first_object(text)
    for attempt in (
        candidate,
        _sanitize_json(candidate),
        _repair_truncated_json(candidate),
        _repair_truncated_json(_sanitize_json(candidate)),
    ):
        try:
            return json.loads(attempt)
        except json.JSONDecodeError:
            continue
    raise PlanError("تعذّر قراءة الخطة من رد النموذج.")


def _sanitize_json(text: str) -> str:
    """Fix the most common near-JSON defects produced by chat models.

    Handles raw newlines/tabs inside string literals and trailing commas before
    ``}`` or ``]`` — both are frequent when a model rewrites JSON as prose.
    """
    # Remove trailing commas before a closing brace/bracket.
    text = re.sub(r",\s*([}\]])", r"\1", text)
    # Escape control characters that appear inside strings.
    out: list[str] = []
    in_string = False
    escape = False
    for char in text:
        if in_string:
            if escape:
                escape = False
            elif char == "\\":
                escape = True
            elif char == '"':
                in_string = False
            elif char == "\n":
                out.append("\\n")
                continue
            elif char == "\r":
                out.append("\\r")
                continue
            elif char == "\t":
                out.append("\\t")
                continue
        elif char == '"':
            in_string = True
        out.append(char)
    return "".join(out)


def _extract_fenced_json(raw: str) -> Any | None:
    markers = ("```json", "```JSON", "```")
    for marker in markers:
        start = raw.find(marker)
        if start == -1:
            continue
        end = raw.find("```", start + len(marker))
        if end == -1:
            continue
        chunk = raw[start + len(marker) : end].strip()
        try:
            return json.loads(chunk)
        except json.JSONDecodeError:
            continue
    return None


def _extract_first_object(text: str) -> str:
    """Return the text starting at a brace that begins valid-looking JSON.

    Prose may contain stray braces and a response may be truncated, so:
    1. try each ``{`` and return the first that parses as complete JSON;
    2. otherwise return the candidate from the **earliest** ``{`` (which is the
       one we can best repair when the tail was cut off).
    """
    starts = [i for i, ch in enumerate(text) if ch == "{"]
    if not starts:
        raise PlanError("لا يوجد كائن JSON في رد النموذج.")
    for start in starts:
        candidate = _balanced_object(text, start)
        try:
            parsed = json.loads(candidate)
        except json.JSONDecodeError:
            continue
        if isinstance(parsed, dict) and ("phases" in parsed or "goal" in parsed):
            return candidate
    for start in starts:
        candidate = _balanced_object(text, start)
        if candidate.endswith("}"):
            continue
        return candidate
    return _balanced_object(text, starts[0])


def _balanced_object(text: str, start: int) -> str:
    depth = 0
    in_string = False
    escape = False
    for index in range(start, len(text)):
        char = text[index]
        if in_string:
            if escape:
                escape = False
            elif char == "\\":
                escape = True
            elif char == '"':
                in_string = False
            continue
        if char == '"':
            in_string = True
        elif char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return text[start : index + 1]
    return text[start:]


def _repair_truncated_json(text: str) -> str:
    """Best-effort close of an object cut off by a token limit."""
    result = text.rstrip()
    # Drop a trailing partial string / property.
    if result.endswith(","):
        result = result[:-1]
    # Close any open string.
    if result.count('"') % 2 == 1:
        result += '"'
    open_braces = result.count("{") - result.count("}")
    open_brackets = result.count("[") - result.count("]")
    result += "]" * max(0, open_brackets)
    result += "}" * max(0, open_braces)
    return result
