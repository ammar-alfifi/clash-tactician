"""Watch subscriptions: notify about war / CWL events."""

from __future__ import annotations

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from app.bot import keyboards, texts
from app.bot.deps import Deps
from app.bot.handlers.common import safe_edit
from app.bot.states import WatchFlow
from app.core.errors import CocError
from app.core.formatting import normalize_tag

router = Router(name="watch")

KIND_LABELS = {"war": "الحرب", "cwl": "بطولات أبطال القبائل"}


async def show_watch(event: Message | CallbackQuery, deps: Deps, chat_id: int) -> None:
    subs = await deps.subs.list_for_chat(chat_id)
    header = "🔔 <b>مراقبتك</b>\n" + (
        "لا توجد قبائل مراقَبة بعد." if not subs else "اضغط على قبيلة لإيقاف مراقبتها:"
    )
    await safe_edit(event, header, keyboards.watch_menu(subs))


@router.callback_query(F.data == "nav:watch")
async def nav_watch(callback: CallbackQuery, deps: Deps) -> None:
    await show_watch(callback, deps, callback.from_user.id)


@router.callback_query(F.data.startswith("watch:add:"))
async def watch_add(callback: CallbackQuery, state: FSMContext) -> None:
    kind = callback.data.split(":", 2)[2]
    if kind not in KIND_LABELS:
        kind = "war"
    await state.set_state(WatchFlow.target)
    await state.update_data(kind=kind)
    await safe_edit(
        callback,
        f"أرسل وسم القبيلة لمتابعة {KIND_LABELS[kind]} (مثال: <code>#ABC123</code>).",
        keyboards.back_home(),
    )


@router.message(WatchFlow.target, F.text)
async def watch_target(message: Message, state: FSMContext, deps: Deps) -> None:
    tag = normalize_tag(message.text)
    if not tag:
        await message.answer("وسم غير صالح، جرّب مرة أخرى.")
        return
    await state.set_state(None)
    if not deps.settings.has_coc:
        await message.answer(texts.NO_COC)
        return
    try:
        clan = await deps.coc.clan(tag)
    except CocError as exc:
        await message.answer(f"⚠️ {exc.reason}")
        return
    data = await state.get_data()
    kind = data.get("kind", "war")
    await deps.subs.add(message.from_user.id, kind, clan.tag, message.from_user.id)
    await message.answer(
        f"✅ سأراقب {KIND_LABELS[kind]} لقبيلة <b>{clan.name}</b> وأرسل لك التنبيهات.",
        reply_markup=keyboards.watch_menu(await deps.subs.list_for_chat(message.from_user.id)),
    )


@router.callback_query(F.data.startswith("watch:del:"))
async def watch_delete(callback: CallbackQuery, deps: Deps) -> None:
    parts = callback.data.split(":", 3)
    kind, tag = parts[2], parts[3]
    await deps.subs.remove(callback.from_user.id, kind, tag)
    await callback.answer("🔕 تم إيقاف المراقبة")
    await show_watch(callback, deps, callback.from_user.id)
