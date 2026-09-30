"""Attack planner service.

Uses a two-stage pipeline that separates perception from reasoning:
  1. A vision model describes the base (buildings + grid cells) — cheap and fast.
  2. A strong text model builds the plan from that grounded description.

This is far more reliable than asking one small multimodal model to both read
the image and reason about it, which is what free providers struggle with.
"""

from __future__ import annotations

import json
import logging

from app.ai.providers import AiConfig, chat_race
from app.config import Settings
from app.core.errors import AiError, AiUnavailable, PlanError
from app.planner.prompts import (
    SYSTEM_PROMPT,
    VISION_SYSTEM_PROMPT,
    PlannerContext,
    build_plan_from_description,
    build_refine_prompt,
    build_user_prompt,
    build_vision_prompt,
)
from app.planner.schema import Plan, parse_plan
from app.planner.validator import ValidationResult, validate_plan

logger = logging.getLogger(__name__)

STRICT_JSON_INSTRUCTION = (
    "تعليمات صارمة: أعد كائن JSON واحدًا فقط بلا شرح وبلا markdown. "
    "يجب أن يحتوي على مفتاح phases وهو مصفوفة فيها 3 مراحل على الأقل، "
    "كل مرحلة تحتوي name و action و reason و markers، وكل علامة تحتوي cell "
    "من الشبكة 4×4. لا تكتفِ بـ detections.\n\n"
)

def _strict_json_instruction(user_text: str) -> str:
    return STRICT_JSON_INSTRUCTION + user_text


def _is_usable_plan(raw: str) -> bool:
    """Cheap check: does this reply parse into a plan with real, filled phases?"""
    try:
        plan = parse_plan(raw)
    except PlanError:
        return False
    if not plan.phases:
        return False
    return any(len(phase.action.strip()) > 3 for phase in plan.phases)


def _is_usable_description(raw: str) -> bool:
    """A vision description is usable when it parsed and found any building."""
    data = _loads_lenient(raw)
    if not isinstance(data, dict):
        return False
    detections = data.get("detections")
    return isinstance(detections, list) and len(detections) > 0


def _vision_configs(configs: list[AiConfig]) -> list[AiConfig]:
    return [config for config in configs if config.supports_vision]


def _text_configs(configs: list[AiConfig]) -> list[AiConfig]:
    """Text models can reason without images; keep the full pool as fallback."""
    text_only = [config for config in configs if not config.supports_vision]
    return text_only or configs


class PlanOutcome:
    """A validated plan plus the server-side validation verdict."""

    def __init__(
        self,
        plan: Plan,
        validation: ValidationResult,
        description: str = "",
        source: str = "one_stage",
    ) -> None:
        self.plan = plan
        self.validation = validation
        self.description = description
        self.source = source


class PlannerService:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    async def generate(
        self, configs: list[AiConfig], context: PlannerContext, image: bytes | None
    ) -> PlanOutcome:
        if image:
            two_stage = await self._generate_two_stage(configs, context, image)
            if two_stage is not None:
                return two_stage
        plan = await self._run(
            configs,
            system=SYSTEM_PROMPT,
            user_text=build_user_prompt(context),
            image=image,
        )
        return self._validate(plan, context)

    async def _generate_two_stage(
        self, configs: list[AiConfig], context: PlannerContext, image: bytes
    ) -> PlanOutcome | None:
        """Describe the base with a vision model, then plan with a text model."""
        vision = _vision_configs(configs)
        if not vision:
            return None
        timeout = max(self._timeout_for(c) for c in configs)
        try:
            description = await chat_race(
                vision,
                system=VISION_SYSTEM_PROMPT,
                user_text=build_vision_prompt(),
                image=image,
                temperature=0.1,
                max_tokens=1200,
                json_mode=True,
                timeout=timeout,
                validator=_is_usable_description,
            )
        except (AiError, PlanError):
            logger.info("Vision stage failed; falling back to one-stage planning")
            return None

        logger.info("Vision description ready (%d chars)", len(description))
        planner_configs = _text_configs(configs)
        plan = await self._run(
            planner_configs,
            system=SYSTEM_PROMPT,
            user_text=build_plan_from_description(context, description),
            image=None,
        )
        outcome = self._validate(plan, context)
        outcome.description = description
        outcome.source = "two_stage"
        return outcome

    async def refine(
        self,
        configs: list[AiConfig],
        plan: Plan,
        instruction: str,
        context: PlannerContext,
    ) -> PlanOutcome:
        refined = await self._run(
            configs,
            system=SYSTEM_PROMPT,
            user_text=build_refine_prompt(plan, instruction, context),
            image=None,
        )
        return self._validate(refined, context)

    def _validate(self, plan: Plan, context: PlannerContext) -> PlanOutcome:
        result = validate_plan(plan, town_hall=context.town_hall, army=context.army)
        if not result.ok:
            logger.info("Plan validation issues: %s", result.summary)
        return PlanOutcome(plan, result)

    async def _run(
        self,
        configs: list[AiConfig],
        *,
        system: str,
        user_text: str,
        image: bytes | None,
    ) -> Plan:
        if not configs:
            raise AiError("لا يوجد مفتاح ذكاء اصطناعي متاح. أضف مفتاحك في الإعدادات.")
        timeout = max(self._timeout_for(c) for c in configs)
        attempt_inputs = [user_text, None]
        last_error: Exception | None = None
        for index, prompt in enumerate(attempt_inputs):
            text = prompt if prompt is not None else _strict_json_instruction(user_text)
            try:
                raw = await chat_race(
                    configs,
                    system=system,
                    user_text=text,
                    image=image,
                    temperature=0.25 if index == 0 else 0.1,
                    max_tokens=4000 if index == 0 else 3000,
                    json_mode=True,
                    timeout=timeout,
                    validator=_is_usable_plan,
                )
                return parse_plan(raw)
            except (AiError, PlanError) as exc:
                last_error = exc
                logger.info("Planner attempt %d failed: %s", index + 1, exc)
                continue
        raise last_error or AiUnavailable("تعذّر توليد الخطة حاليًا، جرّب مرة أخرى.")

    def _timeout_for(self, config: AiConfig) -> int:
        if config.provider == "nvidia":
            return max(self.settings.ai_timeout_seconds, self.settings.nvidia_timeout_seconds)
        return self.settings.ai_timeout_seconds


def _loads_lenient(raw: str):
    """Parse a model's JSON as loosely as needed for the usability check."""
    text = raw.strip()
    if text.startswith("```"):
        text = text.strip("`")
        if text.lower().startswith("json"):
            text = text[4:]
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end <= start:
        return None
    try:
        return json.loads(text[start : end + 1])
    except json.JSONDecodeError:
        return None
