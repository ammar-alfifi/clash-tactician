"""Support tickets and feature ideas."""

from __future__ import annotations

import logging

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from app.bot import keyboards, texts
from app.bot.cards import ticket_card
from app.bot.deps import Deps
from app.bot.handlers.common import safe_edit
from app.bot.states import SupportFlow
from app.core.formatting import esc

logger = logging.getLogger(__name__)
router = Router(name="support")

KINDS = {"bug": "🐞 مشكلة تقنية", "help": "❓ طلب مساعدة", "idea": "💡 اقتراح ميزة"}


@router.callback_query(F.data == "nav:support")
async def nav_support(callback: CallbackQuery) -> None:
    await safe_edit(
        callback,
        "💬 <b>الدعم والأفكار</b>\nاختر نوع طلبك وسأرسله لفريق المشرفين:",
        keyboards.support_kinds(),
    )


@router.callback_query(F.data.startswith("sup:kind:"))
async def choose_kind(callback: CallbackQuery, state: FSMContext) -> None:
    kind = callback.data.split(":", 2)[2]
    if kind not in KINDS:
        kind = "help"
    await state.set_state(SupportFlow.body)
    await state.update_data(kind=kind)
    await safe_edit(
        callback,
        f"{KINDS[kind]}\n\nاكتب تفاصيل طلبك في رسالة واحدة، وسأرسلها لفريق الدعم.",
        keyboards.back_home(),
    )


@router.message(Command("support", "idea"))
async def cmd_support(message: Message, command, state: FSMContext) -> None:
    kind = "idea" if (command.command or "").lower() == "idea" else "help"
    await state.set_state(SupportFlow.body)
    await state.update_data(kind=kind)
    await message.answer(
        f"{KINDS[kind]}\n\nاكتب تفاصيل طلبك في رسالة واحدة.",
        reply_markup=keyboards.back_home(),
    )


@router.message(Command("cancel"))
async def cmd_cancel(message: Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer(texts.CANCELLED, reply_markup=keyboards.main_menu())


@router.message(SupportFlow.body, F.text)
async def receive_ticket(message: Message, state: FSMContext, deps: Deps) -> None:
    data = await state.get_data()
    kind = data.get("kind", "help")
    body = message.text.strip()[:1500]
    await state.clear()
    ticket_id = await deps.tickets.add(message.from_user.id, kind, body)
    await message.answer(
        f"✅ تم استلام طلبك، رقم التذكرة <b>#{ticket_id}</b>. سنراجعه قريبًا.",
        reply_markup=keyboards.back_home(),
    )
    if deps.settings.support_chat_id:
        try:
            await message.bot.send_message(
                deps.settings.support_chat_id,
                ticket_card(ticket_id, kind, body, message.from_user.id),
            )
        except Exception:  # noqa: BLE001 - support channel may be unreachable
            logger.warning("Could not deliver ticket %s to support chat", ticket_id, exc_info=True)
    if kind == "idea":
        await message.answer(f"💡 شكرًا لمشاركتك الفكرة: {esc(body[:120])}")
