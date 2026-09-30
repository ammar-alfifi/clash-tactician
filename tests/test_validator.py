"""Grid coordinates, knowledge base and strict plan validation."""

from __future__ import annotations

import pytest

from app.coc.knowledge import (
    DEFENSES,
    composition_text,
    knowledge_block,
    spell_text,
    targeting_rules_text,
)
from app.core.errors import PlanError
from app.planner.schema import GRID_SIZE, cell_to_point, parse_plan
from app.planner.validator import detected_summary, validate_plan

GRID_PLAN = {
    "title": "هجوم جوي",
    "style": "جوي",
    "goal": "three_stars",
    "summary": "افتح بالتنين الكهربائي",
    "confidence": 0.8,
    "detections": [
        {"building": "Air Defense", "cell": "B2", "confidence": 0.9, "air": True},
        {"building": "Inferno Tower", "cell": "C3", "confidence": 0.85},
        {"building": "Eagle Artillery", "cell": "A1", "confidence": 0.7},
        {"building": "Monolith", "cell": "D4", "confidence": 0.8},
    ],
    "phases": [
        {
            "name": "تمهيد",
            "action": "أسقط دفاع الجو بصاعقة ثم أطلق التنين الكهربائي",
            "reason": "القوات الجوية تستهدف أقرب مبنى",
            "markers": [{"cell": "B2", "kind": "target"}],
        },
        {
            "name": "الهجوم الرئيسي",
            "action": "أدخل التنين الكهربائي مع التعويذات",
            "markers": [{"cell": "C3", "kind": "entry"}],
        },
    ],
    "risks": [],
    "uncertainties": [],
    "army_notes": [],
}


def test_cell_to_point_bounds():
    assert cell_to_point("A1") == (0.125, 0.125)
    assert cell_to_point("D4") == (0.875, 0.875)
    assert cell_to_point("E1") is None  # out of a 4x4 grid
    assert cell_to_point("A0") is None
    assert cell_to_point("") is None
    assert cell_to_point("b2") == (0.375, 0.375)  # case insensitive


def test_markers_prefer_cell_over_xy():
    payload = dict(GRID_PLAN)
    payload["phases"] = [
        {
            "name": "p",
            "action": "a",
            "markers": [{"cell": "C3", "x": 0.0, "y": 0.0, "kind": "entry"}],
        }
    ]
    plan = parse_plan(payload)
    marker = plan.phases[0].markers[0]
    assert marker.cell == "C3"
    assert marker.x == 0.625 and marker.y == 0.625


def test_invalid_cell_falls_back_to_xy():
    payload = dict(GRID_PLAN)
    payload["phases"] = [
        {"name": "p", "action": "a", "markers": [{"cell": "Z9", "x": 0.9, "y": 0.1}]}
    ]
    plan = parse_plan(payload)
    marker = plan.phases[0].markers[0]
    assert marker.cell == ""
    assert marker.x == 0.9 and marker.y == 0.1


def test_detections_parsed_and_capped():
    plan = parse_plan(GRID_PLAN)
    assert len(plan.detections) == 4
    assert plan.style == "جوي"
    # Invalid detections are dropped.
    payload = dict(GRID_PLAN)
    payload["detections"] = [
        {"building": "X", "cell": "Z9"},
        {"building": "", "cell": "A1"},
        {"building": "Cannon", "cell": "A1"},
    ]
    assert len(parse_plan(payload).detections) == 1


def test_valid_plan_passes_validation():
    plan = parse_plan(GRID_PLAN)
    result = validate_plan(plan, town_hall=14, army="12 Electro Dragon, 8 Balloon")
    assert result.ok
    assert result.issues == []
    # Structural validity passes; unread high-threat defenses (e.g. Scattershot
    # at TH13+) are reported as warnings, not blocking issues.
    assert all("Scattershot" not in issue for issue in result.issues)


def test_missing_markers_is_an_issue():
    payload = dict(GRID_PLAN)
    payload["phases"] = [
        {"name": "p", "action": "افعل شيئًا", "markers": []},
        {"name": "q", "action": "افعل شيئًا آخر", "markers": []},
    ]
    plan = parse_plan(payload)
    result = validate_plan(plan, town_hall=14)
    assert not result.ok
    assert any("علامات" in issue for issue in result.issues)


def test_high_threat_unread_lowers_confidence():
    payload = dict(GRID_PLAN)
    payload["detections"] = [{"building": "Cannon", "cell": "A1", "confidence": 0.9}]
    payload["summary"] = "هجوم بسيط"
    payload["phases"] = [
        {"name": "p", "action": "استخدم التنين الكهربائي", "markers": [{"cell": "A1"}]}
    ]
    plan = parse_plan(payload)
    before = plan.confidence
    result = validate_plan(plan, town_hall=14)
    assert result.high_threat_unread
    assert plan.confidence < before
    assert result.confidence_penalty > 0


def test_low_confidence_detections_penalised():
    payload = dict(GRID_PLAN)
    payload["detections"] = [
        {"building": "Air Defense", "cell": "A1", "confidence": 0.2},
        {"building": "Inferno Tower", "cell": "A2", "confidence": 0.1},
    ]
    plan = parse_plan(payload)
    result = validate_plan(plan, town_hall=14)
    assert result.confidence_penalty >= 0.06
    assert any("ثقة منخفضة" in warning for warning in result.warnings)


def test_air_plan_without_air_defense_warns():
    payload = dict(GRID_PLAN)
    payload["style"] = "جوي"
    payload["detections"] = [{"building": "Cannon", "cell": "A1", "confidence": 0.9}]
    payload["phases"] = [
        {"name": "p", "action": "أطلق التنين الكهربائي", "markers": [{"cell": "A1"}]}
    ]
    result = validate_plan(parse_plan(payload), town_hall=14)
    assert any("دفاع الجو" in warning for warning in result.warnings)


def test_detected_summary_groups_by_building():
    plan = parse_plan(GRID_PLAN)
    summary = detected_summary(plan.detections)
    assert "Air Defense" in summary
    assert "لم يتعرّف" in detected_summary([])


def test_knowledge_block_grounded():
    block = knowledge_block(14)
    assert "Inferno Tower 9.0" in block
    assert "أقرب مبنى" in block
    assert "Root Rider" in block  # TH14 composition
    assert "بيانات_مصدرية" in block
    # Stays compact so the model keeps the JSON shape.
    assert len(block) < 900
    inferno = next(d for d in DEFENSES if d.en == "Inferno Tower")
    assert inferno.range_tiles == 9.0 and inferno.threat == 5


def test_knowledge_helpers_not_empty():
    assert targeting_rules_text()
    assert composition_text(14)
    assert spell_text()


def test_parse_requires_phases():
    with pytest.raises(PlanError):
        parse_plan({"summary": "no phases"})


def test_grid_size_constant():
    assert GRID_SIZE == 4
