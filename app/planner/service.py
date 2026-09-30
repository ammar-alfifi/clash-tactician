"""Attack planner service: generate and refine plans through AI providers."""

from __future__ import annotations

import logging

from app.ai.providers import AiConfig, chat
from app.config import Settings
from app.core.errors import AiAuthError, AiError, AiUnavailable, PlanError
from app.planner.prompts import (
    SYSTEM_PROMPT,
    PlannerContext,
    build_refine_prompt,
    build_user_prompt,
)
from app.planner.schema import Plan, parse_plan

logger = logging.getLogger(__name__)


class PlannerService:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    async def generate(
        self, configs: list[AiConfig], context: PlannerContext, image: bytes | None
    ) -> Plan:
        return await self._run(
            configs,
            system=SYSTEM_PROMPT,
            user_text=build_user_prompt(context),
            image=image,
        )

    async def refine(
        self,
        configs: list[AiConfig],
        plan: Plan,
        instruction: str,
        context: PlannerContext,
    ) -> Plan:
        return await self._run(
            configs,
            system=SYSTEM_PROMPT,
            user_text=build_refine_prompt(plan, instruction, context),
            image=None,
        )

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
        last_error: Exception | None = None
        for index, config in enumerate(configs):
            try:
                raw = await chat(
                    config,
                    system=system,
                    user_text=user_text,
                    image=image,
                    temperature=0.35,
                    max_tokens=2600,
                    json_mode=True,
                    timeout=self._timeout_for(config),
                )
                return parse_plan(raw)
            except AiAuthError:
                raise
            except (AiUnavailable, PlanError) as exc:
                last_error = exc
                logger.info(
                    "Planner attempt %d failed on %s/%s: %s",
                    index + 1,
                    config.provider,
                    config.model,
                    exc,
                )
                continue
        raise last_error or AiUnavailable("تعذّر توليد الخطة حاليًا، جرّب مرة أخرى.")

    def _timeout_for(self, config: AiConfig) -> int:
        if config.provider == "nvidia":
            return max(self.settings.ai_timeout_seconds, self.settings.nvidia_timeout_seconds)
        return self.settings.ai_timeout_seconds
