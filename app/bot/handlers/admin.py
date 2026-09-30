"""Operator-only administration."""

from __future__ import annotations

import logging

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from app.bot import keyboards, texts
from app.bot.deps import Deps
from app.bot.handlers.common import safe_edit
from app.bot.states import BroadcastFlow

logger = logging.getLogger(__name__)
router = Router(name="admin")


@router.message(Command("admin"))
async def cmd_admin(message: Message, deps: Deps) -> None:
    if not deps.is_admin(message.from_user.id):
        await message.answer(texts.NOT_ADMIN)
        return
    await message.answer("🛠️ <b>لوحة الإدارة</b>", reply_markup=keyboards.admin_menu())


@router.callback_query(F.data == "admin:stats")
async def admin_stats(callback: CallbackQuery, deps: Deps) -> None:
    if not deps.is_admin(callback.from_user.id):
        await callback.answer(texts.NOT_ADMIN, show_alert=True)
        return
    users = await deps.users.count()
    accounts = len(await deps.accounts.distinct_tags())
    tickets = await deps.tickets.count()
    text = (
        "📊 <b>إحصاءات البوت</b>\n\n"
        f"👤 المستخدمون: <b>{users}</b>\n"
        f"🔗 الحسابات المرتبطة: <b>{accounts}</b>\n"
        f"🗂️ التذاكر: <b>{tickets}</b>\n"
        f"🤖 مفتاح مشترك: {'✅' if deps.settings.has_shared_ai else '❌'}\n"
        f"🎮 واجهة اللعبة: {'✅' if deps.settings.has_coc else '❌'}"
    )
    await safe_edit(callback, text, keyboards.admin_menu())


@router.callback_query(F.data == "admin:broadcast")
async def admin_broadcast(callback: CallbackQuery, state: FSMContext, deps: Deps) -> None:
    if not deps.is_admin(callback.from_user.id):
        await callback.answer(texts.NOT_ADMIN, show_alert=True)
        return
    await state.set_state(BroadcastFlow.body)
    await safe_edit(callback, "📣 أرسل نص البث ليصل إلى كل المستخدمين.", keyboards.back_home())


@router.message(BroadcastFlow.body, F.text)
async def send_broadcast(message: Message, state: FSMContext, deps: Deps) -> None:
    if not deps.is_admin(message.from_user.id):
        return
    await state.set_state(None)
    text = message.text.strip()[:3500]
    ids = await deps.users.all_ids()
    sent = 0
    for telegram_id in ids:
        try:
            await message.bot.send_message(telegram_id, f"📣 {text}")
            sent += 1
        except Exception:  # noqa: BLE001
            continue
    await message.answer(f"✅ تم إرسال البث إلى {sent} من {len(ids)} مستخدمًا.")
