"""Plan schema validation, prompt building and rendering."""

from __future__ import annotations

import io
import json

import pytest
from PIL import Image

from app.coc.catalog import arabic_name, catalog_prompt, max_hero_level
from app.core.errors import ImageError, PlanError
from app.planner.prompts import SYSTEM_PROMPT, PlannerContext, build_user_prompt
from app.planner.renderer import render_plan
from app.planner.schema import Plan, parse_plan

VALID = {
    "title": "هجوم جوي",
    "goal": "three_stars",
    "summary": "افتح بمنطادين ثم أطلق التنين",
    "confidence": 0.8,
    "phases": [
        {
            "name": "فصل الجناح",
            "action": "ابدأ من الشمال الغربي",
            "reason": "تقليل انجراف القوة",
            "markers": [{"x": 0.2, "y": 0.5, "kind": "entry", "label": "بداية"}],
        },
        {"name": "الهجوم الرئيسي", "action": "أطلق التنين", "markers": [{"x": 0.6, "y": 0.3}]},
    ],
    "risks": ["قلعة القبيلة قوية"],
    "uncertainties": ["مستوى الدفاعات غير واضح"],
}


def test_parse_valid_plan():
    plan = parse_plan(json.dumps(VALID))
    assert plan.goal == "three_stars"
    assert [p.name for p in plan.phases] == ["فصل الجناح", "الهجوم الرئيسي"]
    assert len(plan.phases) == 2
    assert plan.phases[0].markers[0].kind == "entry"
    assert plan.confidence_label == "عالية"
    assert plan.goal_label == "ثلاث نجوم"


def test_parse_plan_from_fenced_text():
    raw = "```json\n" + json.dumps(VALID) + "\n```"
    assert parse_plan(raw).phases[1].action == "أطلق التنين"


def test_parse_plan_clamps_and_filters():
    payload = dict(VALID)
    payload["confidence"] = 150
    payload["phases"] = [
        {"name": "x", "action": "ok", "markers": [{"x": 5, "y": -3, "kind": "bogus"}]},
        {"name": "empty", "action": ""},
    ]
    plan = parse_plan(payload)
    marker = plan.phases[0].markers[0]
    assert marker.x == 1.0 and marker.y == 0.0 and marker.kind == "target"
    assert len(plan.phases) == 1  # the empty action phase is dropped


def test_parse_plan_rejects_bad_input():
    with pytest.raises(PlanError):
        parse_plan("not json")
    with pytest.raises(PlanError):
        parse_plan({"phases": []})


def test_marker_kind_allowlist_and_cap():
    payload = dict(VALID)
    payload["phases"] = [
        {
            "name": "p",
            "action": "a",
            "markers": [{"x": 0.1 * i, "y": 0.1, "kind": "entry"} for i in range(20)],
        }
    ]
    plan = parse_plan(payload)
    assert len(plan.phases[0].markers) == 6


def test_catalog_and_hero_levels():
    assert arabic_name("dragon") == "التنين"
    assert "Dragon" in catalog_prompt(12)
    assert max_hero_level(14, "Archer Queen") == 80
    assert max_hero_level(14, "Unknown Hero") is None


def test_prompt_contains_context():
    context = PlannerContext(
        town_hall=13, goal_label="ثلاث نجوم", army="6 تنانين", player_name="Ammar"
    )
    prompt = build_user_prompt(context)
    assert "ثلاث نجوم" in prompt
    assert "6 تنانين" in prompt
    assert "Dragon" in prompt
    assert "JSON" in SYSTEM_PROMPT


def _plan() -> Plan:
    return parse_plan(VALID)


def test_render_plan_produces_png():
    image = Image.new("RGB", (800, 600), (40, 90, 40))
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    result = render_plan(buffer.getvalue(), _plan())
    assert result[:8] == b"\x89PNG\r\n\x1a\n"
    Image.open(io.BytesIO(result)).verify()


def test_render_plan_rejects_garbage():
    with pytest.raises(ImageError):
        render_plan(b"not an image", _plan())
