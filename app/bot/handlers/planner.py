"""The attack planner flow: image -> annotated plan, refine, save, library."""

from __future__ import annotations

import asyncio
import contextlib
import io
import logging

from aiogram import Bot, F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import BufferedInputFile, CallbackQuery, Message

from app.bot import cards, keyboards, texts
from app.bot.deps import Deps
from app.bot.handlers.common import present, reply, safe_edit
from app.bot.states import PlannerFlow
from app.core.errors import AiError, CocError
from app.planner.prompts import PlannerContext
from app.planner.renderer import render_plan
from app.planner.schema import GOALS, Plan, plan_from_stored

logger = logging.getLogger(__name__)
router = Router(name="planner")

MAX_CAPTION = 1024


def _target_message(event: Message | CallbackQuery) -> Message | None:
    if isinstance(event, CallbackQuery):
        return event.message if isinstance(event.message, Message) else None
    return event


async def _select_configs(deps: Deps, telegram_id: int, mode: str):
    """Pick AI configs based on the user's chosen quality/cost preference."""
    from app.ai.factory import build_shared_configs, build_user_configs

    if mode == "fast":
        key = await deps.keys.get(telegram_id)
        api_key = deps.vault.decrypt(key.encrypted_key) if key else None
        if key and api_key:
            return build_user_configs(deps.settings, key, api_key)
        return []  # caller shows the "add a key" message
    return build_shared_configs(deps.settings)


async def _context(
    deps: Deps, telegram_id: int, goal: str, army: str
) -> PlannerContext:
    town_hall, hero_info, player_name = 0, "", ""
    account = await deps.accounts.primary(telegram_id)
    if account and deps.settings.has_coc:
        try:
            player = await deps.coc.player(account.player_tag)
            town_hall = player.town_hall
            player_name = player.name
            hero_info = "، ".join(
                f"{hero.name} {hero.level}/{hero.max_level}"
                for hero in player.heroes
                if hero.village == "home"
            )
        except CocError:
            logger.info("Planner context: player lookup failed", exc_info=True)
    return PlannerContext(
        town_hall=town_hall,
        goal_label=GOALS.get(goal, "ثلاث نجوم"),
        army=army,
        player_name=player_name,
        hero_info=hero_info,
    )


async def start_flow(event: Message | CallbackQuery, state: FSMContext, deps: Deps) -> None:
    await state.clear()
    await state.set_state(PlannerFlow.mode)
    key = await deps.keys.get(event.from_user.id)
    await present(event, texts.PLAN_MODE_INTRO, keyboards.planner_modes(bool(key)))


@router.message(Command("plan"))
async def cmd_plan(message: Message, state: FSMContext, deps: Deps) -> None:
    await start_flow(message, state, deps)


@router.callback_query(F.data == "nav:planner")
async def nav_planner(callback: CallbackQuery, state: FSMContext, deps: Deps) -> None:
    await start_flow(callback, state, deps)


@router.callback_query(F.data == "plan:new")
async def new_plan(callback: CallbackQuery, state: FSMContext, deps: Deps) -> None:
    await start_flow(callback, state, deps)


@router.callback_query(F.data == "plan:mode:addkey")
async def mode_add_key(callback: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await safe_edit(callback, texts.PLAN_MODE_NEEDS_KEY, keyboards.keys_menu(False))


@router.callback_query(F.data.startswith("plan:mode:"))
async def choose_mode(callback: CallbackQuery, state: FSMContext) -> None:
    mode = callback.data.split(":", 2)[2]
    await state.update_data(mode=mode)
    await state.set_state(PlannerFlow.goal)
    await safe_edit(callback, texts.PLAN_INTRO, keyboards.planner_goals())


@router.callback_query(F.data == "plan:cancel")
async def cancel(callback: CallbackQuery, state: FSMContext, deps: Deps) -> None:
    await state.clear()
    await safe_edit(callback, texts.CANCELLED, keyboards.main_menu())


@router.callback_query(F.data.startswith("plan:goal:"))
async def choose_goal(callback: CallbackQuery, state: FSMContext) -> None:
    goal = callback.data.split(":", 2)[2]
    if goal not in GOALS:
        goal = "three_stars"
    await state.update_data(goal=goal)
    await state.set_state(PlannerFlow.army)
    await safe_edit(callback, texts.PLAN_ASK_ARMY, keyboards.planner_ask_army())


@router.message(PlannerFlow.army, F.text)
async def receive_army(message: Message, state: FSMContext) -> None:
    await state.update_data(army=message.text.strip()[:600])
    await state.set_state(PlannerFlow.image)
    await message.answer(texts.PLAN_ASK_IMAGE, reply_markup=keyboards.planner_ask_image())


@router.callback_query(PlannerFlow.army, F.data == "plan:skiparmy")
async def skip_army(callback: CallbackQuery, state: FSMContext) -> None:
    await state.update_data(army="")
    await state.set_state(PlannerFlow.image)
    await safe_edit(callback, texts.PLAN_ASK_IMAGE, keyboards.planner_ask_image())


@router.message(PlannerFlow.image, F.photo | F.document)
async def receive_image(message: Message, state: FSMContext, deps: Deps, bot: Bot) -> None:
    await handle_image(message, state, deps, bot)


# Accept an image at any planner step: users often send the screenshot early.
@router.message(PlannerFlow.goal, F.photo | F.document)
@router.message(PlannerFlow.army, F.photo | F.document)
async def receive_image_early(message: Message, state: FSMContext, deps: Deps, bot: Bot) -> None:
    data = await state.get_data()
    if "goal" not in data:
        await state.update_data(goal="three_stars")
    if "mode" not in data:
        await state.update_data(mode="free")
    await state.update_data(army=data.get("army", ""))
    await handle_image(message, state, deps, bot)


async def handle_image(message: Message, state: FSMContext, deps: Deps, bot: Bot) -> None:
    file_id, size = None, 0
    if message.photo:
        file_id = message.photo[-1].file_id
        size = message.photo[-1].file_size or 0
    elif message.document and (message.document.mime_type or "").startswith("image/"):
        file_id = message.document.file_id
        size = message.document.file_size or 0
    if not file_id:
        await message.answer("أرسل صورة بصيغة مدعومة (JPG أو PNG).")
        return
    if size and size > deps.settings.max_image_bytes:
        await message.answer(texts.IMAGE_TOO_BIG)
        return
    buffer = io.BytesIO()
    try:
        await bot.download(file_id, destination=buffer)
    except Exception:  # noqa: BLE001
        await message.answer("تعذّر تنزيل الصورة، حاول مرة أخرى.")
        return
    image_bytes = buffer.getvalue()
    await state.update_data(image_file_id=file_id)
    await _run_plan(message, state, deps, image_bytes=image_bytes)


@router.callback_query(PlannerFlow.image, F.data == "plan:skipimage")
async def skip_image(callback: CallbackQuery, state: FSMContext, deps: Deps) -> None:
    await state.update_data(image_file_id=None)
    await _run_plan(callback, state, deps, image_bytes=None)


async def _run_plan(
    event: Message | CallbackQuery,
    state: FSMContext,
    deps: Deps,
    *,
    image_bytes: bytes | None,
) -> None:
    telegram_id = event.from_user.id
    if not await deps.has_ai(telegram_id):
        await state.set_state(None)
        await reply(event, texts.NO_AI, keyboards.keys_menu(False))
        return
    data = await state.get_data()
    goal = data.get("goal", "three_stars")
    army = data.get("army", "")
    mode = data.get("mode", "free")
    configs = await _select_configs(deps, telegram_id, mode)
    if not configs:
        await state.set_state(None)
        text = texts.PLAN_MODE_NEEDS_KEY if mode == "fast" else texts.NO_AI
        await reply(event, text, keyboards.keys_menu(False))
        return
    context = await _context(deps, telegram_id, goal, army)

    target = _target_message(event)
    status_message = None
    if target:
        try:
            status_message = await target.answer(texts.PLAN_WORKING)
        except Exception:  # noqa: BLE001
            logger.debug("Could not send working notice", exc_info=True)

    progress_task = None
    if status_message is not None:
        progress_task = asyncio.create_task(_progress_notifier(status_message))

    try:
        outcome = await deps.planner.generate(configs, context, image_bytes)
    except AiError as exc:
        await reply(event, f"⚠️ {exc.reason}")
        return
    except Exception:  # noqa: BLE001 - never leave the user without an answer
        logger.exception("Planner crashed unexpectedly")
        await reply(event, "⚠️ حدث خطأ غير متوقع أثناء توليد الخطة. جرّب مرة أخرى.")
        return
    finally:
        if progress_task is not None:
            progress_task.cancel()
            await asyncio.gather(progress_task, return_exceptions=True)
        if status_message is not None:
            with contextlib.suppress(Exception):
                await status_message.delete()

    plan = outcome.plan
    await state.set_state(None)
    await state.update_data(plan=plan.to_json(), goal=goal, army=army, plan_id=None)
    try:
        await _deliver_plan(event, deps, plan, image_bytes, outcome.validation)
    except Exception:  # noqa: BLE001 - delivery failure must still inform the user
        logger.exception("Plan delivery failed")
        await reply(event, cards.plan_text(plan))


async def _progress_notifier(message: Message) -> None:
    """Reassure the user when generation takes longer than expected."""
    schedule = [(25, texts.PLAN_SLOW), (45, texts.PLAN_STILL), (40, texts.PLAN_STILL)]
    for delay, text in schedule:
        await asyncio.sleep(delay)
        try:
            await message.edit_text(text)
        except Exception:  # noqa: BLE001 - best effort
            logger.debug("Could not update progress message", exc_info=True)


async def _deliver_plan(
    event: Message | CallbackQuery,
    deps: Deps,
    plan: Plan,
    image_bytes: bytes | None,
    validation=None,
) -> None:
    target = _target_message(event)
    if target is None:
        return
    if image_bytes:
        try:
            annotated = render_plan(image_bytes, plan)
            await target.answer_photo(
                BufferedInputFile(annotated, filename="plan.png"),
                caption=f"🗺️ <b>{plan.goal_label}</b> • الثقة {plan.confidence_label}",
            )
        except Exception:  # noqa: BLE001 - rendering is best-effort
            logger.warning("Could not render annotated plan", exc_info=True)
    if plan.detections:
        await target.answer(cards.detections_card(plan))
    if validation is not None:
        check = cards.validation_card(validation)
        if check:
            await target.answer(check)
    await target.answer(cards.plan_text(plan), reply_markup=keyboards.plan_result(None))


@router.callback_query(F.data == "plan:again")
async def regenerate(callback: CallbackQuery, state: FSMContext, deps: Deps, bot: Bot) -> None:
    data = await state.get_data()
    image_bytes = None
    file_id = data.get("image_file_id")
    if file_id:
        buffer = io.BytesIO()
        try:
            await bot.download(file_id, destination=buffer)
            image_bytes = buffer.getvalue()
        except Exception:  # noqa: BLE001
            image_bytes = None
    await _run_plan(callback, state, deps, image_bytes=image_bytes)


@router.callback_query(F.data == "plan:refine")
async def refine_prompt(callback: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(PlannerFlow.refine)
    await safe_edit(callback, texts.PLAN_REFINE_PROMPT, keyboards.back_home())


@router.message(PlannerFlow.refine, F.text)
async def refine_plan(message: Message, state: FSMContext, deps: Deps) -> None:
    data = await state.get_data()
    raw_plan = data.get("plan")
    if not raw_plan:
        await state.set_state(None)
        await message.answer(
            "انتهت صلاحية الخطة، ابدأ خطة جديدة.", reply_markup=keyboards.main_menu()
        )
        return
    configs = await deps.ai_configs(message.from_user.id)
    if not configs:
        await message.answer(texts.NO_AI, reply_markup=keyboards.keys_menu(False))
        return
    context = await _context(
        deps, message.from_user.id, data.get("goal", "three_stars"), data.get("army", "")
    )
    try:
        plan = plan_from_stored(raw_plan)
        outcome = await deps.planner.refine(configs, plan, message.text.strip()[:400], context)
    except AiError as exc:
        await message.answer(f"⚠️ {exc.reason}")
        return
    updated = outcome.plan
    await state.set_state(None)
    await state.update_data(plan=updated.to_json())
    if outcome.validation.issues or outcome.validation.warnings:
        check = cards.validation_card(outcome.validation)
        if check:
            await message.answer(check)
    await message.answer(
        cards.plan_text(updated, header="✏️ <b>الخطة بعد التعديل</b>"),
        reply_markup=keyboards.plan_result(None),
    )


@router.callback_query(F.data == "plan:save")
async def save_plan(callback: CallbackQuery, state: FSMContext, deps: Deps) -> None:
    data = await state.get_data()
    raw_plan = data.get("plan")
    if not raw_plan:
        await callback.answer("لا توجد خطة لحفظها.", show_alert=True)
        return
    plan = plan_from_stored(raw_plan)
    plan_id = await deps.plans.add(
        callback.from_user.id,
        title=plan.title or plan.goal_label,
        goal=plan.goal,
        data=plan.to_dict(),
    )
    await state.update_data(plan_id=plan_id)
    await callback.answer("💾 تم حفظ الخطة في مكتبتك")
    await callback.message.answer(
        "💾 تم حفظ الخطة. يمكنك الوصول إليها من «📚 خططي».",
        reply_markup=keyboards.plan_result(plan_id),
    )


@router.callback_query(F.data == "plan:saved")
async def already_saved(callback: CallbackQuery) -> None:
    await callback.answer("الخطة محفوظة بالفعل ✅")


@router.callback_query(F.data == "nav:plans")
async def library(callback: CallbackQuery, deps: Deps) -> None:
    items = await deps.plans.list(callback.from_user.id)
    if not items:
        await safe_edit(
            callback,
            "📚 لا توجد خطط محفوظة بعد. أنشئ خطتك الأولى من «🎯 خطة هجوم».",
            keyboards.back_home(),
        )
        return
    await safe_edit(
        callback, "📚 <b>مكتبة خططك</b>\nاختر خطة لعرضها:", keyboards.library_menu(items)
    )


@router.callback_query(F.data.startswith("lib:view:"))
async def view_saved(callback: CallbackQuery, deps: Deps) -> None:
    plan_id = int(callback.data.split(":", 2)[2])
    saved = await deps.plans.get(plan_id, callback.from_user.id)
    if not saved:
        await callback.answer("الخطة غير موجودة.", show_alert=True)
        return
    plan = plan_from_stored(saved.data)
    await callback.message.answer(cards.plan_text(plan), reply_markup=keyboards.plan_view(plan_id))


@router.callback_query(F.data.startswith("lib:del:"))
async def delete_saved(callback: CallbackQuery, deps: Deps) -> None:
    plan_id = int(callback.data.split(":", 2)[2])
    await deps.plans.delete(plan_id, callback.from_user.id)
    await callback.answer("🗑️ تم الحذف")
    await library(callback, deps)
