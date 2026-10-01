"""HTTP health and diagnostics server (keeps the cloud platform happy)."""

from __future__ import annotations

import asyncio
import logging

import aiohttp
from aiohttp import web

from app.config import Settings
from app.core.errors import CocError
from app.ops import clan_probe, egress
from app.storage.database import Database

logger = logging.getLogger(__name__)

COUNTED_TABLES = (
    "ct_users",
    "ct_accounts",
    "ct_ai_keys",
    "ct_clan_rooms",
    "ct_subscriptions",
    "ct_plans",
    "ct_tickets",
)


class HealthContext:
    def __init__(self, settings: Settings, database: Database, coc=None) -> None:
        self.settings = settings
        self.database = database
        self.coc = coc


def create_health_app(context: HealthContext) -> web.Application:
    application = web.Application()
    application["context"] = context
    application.router.add_get("/", _health)
    application.router.add_get("/health", _health)
    application.router.add_get("/diag", _diag)
    return application


async def _health(_: web.Request) -> web.Response:
    return web.json_response({"status": "ok", "service": "clash-tactician"})


async def _diag(request: web.Request) -> web.Response:
    context: HealthContext = request.app["context"]
    expected = context.settings.diag_token
    if not expected or request.query.get("token") != expected:
        return web.json_response({"status": "not_found"}, status=404)

    payload: dict[str, object] = {
        "status": "ok",
        "egress_ips": egress.observed_ips(),
        "counts": await context.database.table_counts(COUNTED_TABLES),
        "coc_enabled": context.settings.has_coc,
        "shared_ai": context.settings.has_shared_ai,
    }
    if request.query.get("current"):
        payload["current_egress_ip"] = await egress.sample_egress_ip()
    if request.query.get("coc"):
        payload["coc"] = await _coc_check(context)
    if request.query.get("ai"):
        payload["ai"] = await _ai_check(context)
    if request.query.get("vision"):
        payload["vision"] = await _vision_check(context)
    if request.query.get("plan"):
        payload["plan"] = await _plan_check(context)
    if request.query.get("trace"):
        payload["trace"] = await _plan_trace(context)
    tags = clan_probe.parse_tags(request.query.get("clans"))
    if tags:
        payload["clans"] = await _clan_dump(context, tags)
    return web.json_response(payload)


async def _clan_dump(context: HealthContext, tags: list[str]) -> dict[str, object]:
    """Public clan/war data for owner research (read-only, token-gated above)."""
    if context.coc is None:
        return {"error": "coc_client_unavailable"}
    return await clan_probe.dump(context.coc, tags)


async def _coc_check(context: HealthContext) -> dict[str, object]:
    if not context.settings.coc_api_token:
        return {"ok": False, "reason": "missing_token"}
    if context.coc is not None:
        ok, status, detail = await context.coc.verify()
        return {"ok": ok, "status": status, "detail": detail}
    headers = {
        "Authorization": f"Bearer {context.settings.coc_api_token}",
        "Accept": "application/json",
    }
    timeout = aiohttp.ClientTimeout(total=20)
    try:
        async with (
            aiohttp.ClientSession(timeout=timeout) as session,
            session.get(
                f"{context.settings.coc_base_url}/locations",
                headers=headers,
                params={"limit": 1},
            ) as response,
        ):
            body = await response.text()
            return {"ok": response.status == 200, "status": response.status, "detail": body[:200]}
    except (TimeoutError, aiohttp.ClientError, CocError) as error:
        return {"ok": False, "reason": type(error).__name__}


async def _ai_check(context: HealthContext) -> dict[str, object]:
    """Verify the shared AI key can actually answer (no secrets returned)."""
    from app.ai.factory import build_shared_configs
    from app.ai.providers import ping

    configs = build_shared_configs(context.settings)
    if not configs:
        return {"ok": False, "reason": "no_shared_key"}
    results: list[dict[str, object]] = []
    for config in configs:
        ok, message = await ping(config, timeout=60)
        results.append({"provider": config.provider, "model": config.model, "ok": ok})
        if ok:
            return {
                "ok": True,
                "provider": config.provider,
                "model": config.model,
                "tried": results,
            }
    return {"ok": False, "tried": results}


async def _vision_check(context: HealthContext) -> dict[str, object]:
    """Prove that a vision model can read a base image (stage 1 of planning)."""
    import time

    from app.ai.factory import build_shared_configs
    from app.ai.providers import chat_race
    from app.planner.prompts import VISION_SYSTEM_PROMPT, build_vision_prompt
    from app.planner.service import _is_usable_description, _vision_configs

    vision = _vision_configs(build_shared_configs(context.settings))
    if not vision:
        return {"ok": False, "reason": "no_vision_model"}
    started = time.monotonic()
    try:
        raw = await chat_race(
            vision,
            system=VISION_SYSTEM_PROMPT,
            user_text=build_vision_prompt(),
            image=_self_test_image(),
            temperature=0.1,
            max_tokens=900,
            json_mode=True,
            timeout=max(context.settings.nvidia_timeout_seconds, 60),
            validator=_is_usable_description,
        )
    except Exception as error:  # noqa: BLE001 - reported, never raised
        return {
            "ok": False,
            "error": type(error).__name__,
            "detail": str(error)[:200],
            "seconds": round(time.monotonic() - started, 1),
        }
    return {
        "ok": True,
        "seconds": round(time.monotonic() - started, 1),
        "description": raw[:400],
    }


async def _plan_check(context: HealthContext) -> dict[str, object]:
    """End-to-end planner self-test: image -> JSON -> validation.

    Reproduces the exact flow used by /plan so a silent failure is easy to spot.
    """
    import time

    from app.ai.factory import build_shared_configs
    from app.ai.providers import chat_race
    from app.planner.prompts import SYSTEM_PROMPT, PlannerContext, build_user_prompt
    from app.planner.schema import parse_plan
    from app.planner.service import _is_usable_plan
    from app.planner.validator import validate_plan

    configs = build_shared_configs(context.settings)
    if not configs:
        return {"ok": False, "reason": "no_shared_key"}
    image = _self_test_image()
    ctx = PlannerContext(town_hall=14, goal_label="ثلاث نجوم", army="12 Electro Dragon, 8 Balloon")
    started = time.monotonic()
    try:
        raw = await chat_race(
            configs,
            system=SYSTEM_PROMPT,
            user_text=build_user_prompt(ctx),
            image=image,
            temperature=0.25,
            max_tokens=3000,
            json_mode=True,
            timeout=max(c for c in [context.settings.nvidia_timeout_seconds]),
            validator=_is_usable_plan,
        )
        plan = parse_plan(raw)
        validation = validate_plan(plan, town_hall=ctx.town_hall, army=ctx.army)
    except Exception as error:  # noqa: BLE001 - reported, never raised
        return {
            "ok": False,
            "error": type(error).__name__,
            "detail": str(error)[:200],
            "seconds": round(time.monotonic() - started, 1),
            "configs": [
                {"provider": c.provider, "model": c.model} for c in configs
            ],
        }
    return {
        "ok": True,
        "seconds": round(time.monotonic() - started, 1),
        "phases": len(plan.phases),
        "detections": len(plan.detections),
        "valid": validation.ok,
        "warnings": len(validation.warnings),
    }


def _self_test_image() -> bytes:
    """A tiny synthetic base image, generated once for the self-test."""
    from io import BytesIO

    from PIL import Image, ImageDraw

    image = Image.new("RGB", (900, 700), (44, 96, 48))
    draw = ImageDraw.Draw(image)
    for box in ((200, 200, 320, 320), (560, 180, 680, 300), (380, 430, 500, 550)):
        draw.rectangle(box, fill=(150, 60, 40))
    buffer = BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


async def serve_health(context: HealthContext, port: int) -> None:
    runner = web.AppRunner(create_health_app(context))
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", port)
    try:
        await site.start()
    except OSError:
        logger.exception("Could not start health server on port %s", port)
        await runner.cleanup()
        return
    logger.info("Health server listening on port %s", port)
    try:
        await asyncio.Event().wait()
    finally:
        await runner.cleanup()


async def _plan_trace(context: HealthContext) -> dict[str, object]:
    """Time each planning stage so a slow provider is easy to identify."""
    import time

    from app.ai.factory import build_shared_configs
    from app.ai.providers import chat_race
    from app.planner.prompts import (
        SYSTEM_PROMPT,
        VISION_SYSTEM_PROMPT,
        PlannerContext,
        build_plan_from_description,
        build_vision_prompt,
    )
    from app.planner.service import (
        _is_usable_description,
        _is_usable_plan,
        _text_configs,
        _vision_configs,
    )

    configs = build_shared_configs(context.settings)
    vision = _vision_configs(configs)
    text = _text_configs(configs)
    ctx = PlannerContext(town_hall=14, goal_label="ثلاث نجوم", army="12 Electro Dragon, 8 Balloon")
    image = _self_test_image()
    timeout = max(context.settings.nvidia_timeout_seconds, 60)

    trace: dict[str, object] = {}
    started = time.monotonic()
    try:
        description = await chat_race(
            vision,
            system=VISION_SYSTEM_PROMPT,
            user_text=build_vision_prompt(),
            image=image,
            temperature=0.1,
            max_tokens=900,
            json_mode=True,
            timeout=timeout,
            validator=_is_usable_description,
        )
    except Exception as error:  # noqa: BLE001
        trace["vision"] = {"ok": False, "error": type(error).__name__, "detail": str(error)[:150]}
        trace["vision_seconds"] = round(time.monotonic() - started, 1)
        return trace
    trace["vision"] = {
        "ok": True,
        "seconds": round(time.monotonic() - started, 1),
        "chars": len(description),
    }

    started = time.monotonic()
    try:
        await chat_race(
            text,
            system=SYSTEM_PROMPT,
            user_text=build_plan_from_description(ctx, description),
            image=None,
            temperature=0.25,
            max_tokens=4000,
            json_mode=True,
            timeout=timeout,
            validator=_is_usable_plan,
        )
    except Exception as error:  # noqa: BLE001
        trace["plan"] = {"ok": False, "error": type(error).__name__, "detail": str(error)[:150]}
        trace["plan_seconds"] = round(time.monotonic() - started, 1)
        return trace
    trace["plan"] = {"ok": True, "seconds": round(time.monotonic() - started, 1)}
    trace["two_stage_seconds"] = round(
        float(trace["vision"]["seconds"]) + float(trace["plan"]["seconds"]), 1
    )
    return trace
