"""Attack planner service: generate, validate and refine plans through AI."""

from __future__ import annotations

import logging

from app.ai.providers import AiConfig, chat_race
from app.config import Settings
from app.core.errors import AiError, AiUnavailable, PlanError
from app.planner.prompts import (
    SYSTEM_PROMPT,
    PlannerContext,
    build_refine_prompt,
    build_user_prompt,
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
    # Reject plans that are only placeholders ("..") after parsing.
    return any(len(phase.action.strip()) > 3 for phase in plan.phases)


class PlanOutcome:
    """A validated plan plus the server-side validation verdict."""

    def __init__(self, plan: Plan, validation: ValidationResult) -> None:
        self.plan = plan
        self.validation = validation


class PlannerService:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    async def generate(
        self, configs: list[AiConfig], context: PlannerContext, image: bytes | None
    ) -> PlanOutcome:
        plan = await self._run(
            configs,
            system=SYSTEM_PROMPT,
            user_text=build_user_prompt(context),
            image=image,
        )
        return self._validate(plan, context)

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
