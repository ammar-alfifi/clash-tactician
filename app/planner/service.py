"""Attack planner service: generate, validate and refine plans through AI."""

from __future__ import annotations

import logging

from app.ai.providers import AiConfig, chat_race
from app.config import Settings
from app.core.errors import AiAuthError, AiError, AiUnavailable, PlanError
from app.planner.prompts import (
    SYSTEM_PROMPT,
    PlannerContext,
    build_refine_prompt,
    build_user_prompt,
)
from app.planner.schema import Plan, parse_plan
from app.planner.validator import ValidationResult, validate_plan

logger = logging.getLogger(__name__)


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
        try:
            raw = await chat_race(
                configs,
                system=system,
                user_text=user_text,
                image=image,
                temperature=0.25,
                max_tokens=4000,
                json_mode=True,
                timeout=timeout,
            )
            return parse_plan(raw)
        except AiAuthError:
            raise
        except (AiUnavailable, PlanError) as exc:
            logger.info("Planner race failed: %s", exc)
            # One stricter retry asking for bare JSON only.
            repaired = await self._retry_json_only(configs, system, user_text, image, timeout)
            if repaired is not None:
                return repaired
            raise exc

    async def _retry_json_only(
        self,
        configs: list[AiConfig],
        system: str,
        user_text: str,
        image: bytes | None,
        timeout: int,
    ) -> Plan | None:
        strict = (
            "لا تكتب أي شرح أو نص قبل JSON أو بعده، وبلا markdown. أعد JSON صالحًا فقط.\n\n"
            "أخرج كائن JSON مختصرًا (3 مراحل فقط) لتجنب القطع.\n\n" + user_text
        )
        try:
            raw = await chat_race(
                configs,
                system=system,
                user_text=strict,
                image=image,
                temperature=0.1,
                max_tokens=3000,
                json_mode=True,
                timeout=timeout,
            )
            return parse_plan(raw)
        except (AiError, PlanError):
            logger.info("Strict JSON retry failed")
            return None

    def _timeout_for(self, config: AiConfig) -> int:
        if config.provider == "nvidia":
            return max(self.settings.ai_timeout_seconds, self.settings.nvidia_timeout_seconds)
        return self.settings.ai_timeout_seconds
