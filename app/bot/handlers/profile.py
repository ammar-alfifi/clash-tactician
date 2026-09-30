"""Player profile, account linking and growth."""

from __future__ import annotations

from aiogram import F, Router
from aiogram.filters import Command, CommandObject
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from app.bot import cards, keyboards, texts
from app.bot.deps import Deps
from app.bot.handlers.common import reply, safe_edit
from app.bot.states import LinkFlow
from app.core.errors import CocNotFound
from app.core.formatting import normalize_tag
from app.services.snapshots import previous_player, record_player

router = Router(name="profile")


async def show_profile(event: Message | CallbackQuery, deps: Deps, telegram_id: int) -> None:
    account = await deps.accounts.primary(telegram_id)
    if not account or not deps.settings.has_coc:
        text = texts.NO_ACCOUNT if not account else texts.NO_COC
        await safe_edit(event, text, keyboards.profile_menu(False))
        return
    player = await deps.coc.player(account.player_tag)
    if player.name and player.name != account.name:
        await deps.accounts.set_name(telegram_id, player.tag, player.name)
    await record_player(deps, player)
    await safe_edit(event, cards.player_card(player), keyboards.profile_menu(True))


@router.message(Command("profile", "me"))
async def cmd_profile(message: Message, deps: Deps) -> None:
    await show_profile(message, deps, message.from_user.id)


@router.callback_query(F.data == "nav:profile")
async def nav_profile(callback: CallbackQuery, deps: Deps) -> None:
    await show_profile(callback, deps, callback.from_user.id)


@router.callback_query(F.data == "profile:refresh")
async def refresh_profile(callback: CallbackQuery, deps: Deps) -> None:
    await deps.coc.client.invalidate()
    await show_profile(callback, deps, callback.from_user.id)


@router.callback_query(F.data == "profile:growth")
async def growth(callback: CallbackQuery, deps: Deps) -> None:
    telegram_id = callback.from_user.id
    account = await deps.accounts.primary(telegram_id)
    if not account:
        await safe_edit(callback, texts.NO_ACCOUNT, keyboards.profile_menu(False))
        return
    player = await deps.coc.player(account.player_tag)
    await record_player(deps, player)
    previous = await previous_player(deps, player.tag)
    when = previous[0] if previous else None
    payload = previous[1] if previous else None
    await safe_edit(callback, cards.growth_card(player, payload, when), keyboards.back_home())


@router.callback_query(F.data == "profile:accounts")
async def accounts(callback: CallbackQuery, deps: Deps) -> None:
    items = await deps.accounts.list(callback.from_user.id)
    if not items:
        await safe_edit(callback, texts.NO_ACCOUNT, keyboards.profile_menu(False))
        return
    lines = ["🗂️ <b>حساباتك المرتبطة</b>", ""]
    for account in items:
        star = "⭐ " if account.is_primary else "• "
        lines.append(f"{star}<code>{account.player_tag}</code> — {account.name or 'لاعب'}")
    lines.append("")
    lines.append("اضغط على حساب لتعيينه كأساسي.")
    await safe_edit(callback, "\n".join(lines), keyboards.accounts_menu(items))


@router.callback_query(F.data == "profile:link")
async def start_link(callback: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(LinkFlow.waiting_tag)
    await safe_edit(callback, texts.LINK_PROMPT, keyboards.back_home())


@router.message(Command("link"))
async def cmd_link(message: Message, command: CommandObject, state: FSMContext, deps: Deps) -> None:
    raw = (command.args or "").strip()
    if raw:
        await _link_tag(message, deps, message.from_user.id, raw)
        return
    await state.set_state(LinkFlow.waiting_tag)
    await message.answer(texts.LINK_PROMPT)


@router.message(LinkFlow.waiting_tag)
async def receive_tag(message: Message, state: FSMContext, deps: Deps) -> None:
    await state.clear()
    if not message.text:
        await message.answer(texts.TAG_NOT_FOUND)
        return
    await _link_tag(message, deps, message.from_user.id, message.text)


async def _link_tag(event: Message | CallbackQuery, deps: Deps, telegram_id: int, raw: str) -> None:
    tag = normalize_tag(raw)
    if not tag:
        await reply(event, texts.TAG_NOT_FOUND)
        return
    if not deps.settings.has_coc:
        await reply(event, texts.NO_COC)
        return
    try:
        player = await deps.coc.player(tag)
    except CocNotFound:
        await reply(event, texts.TAG_NOT_FOUND, None)
        return
    accounts = await deps.accounts.list(telegram_id)
    await deps.accounts.add(telegram_id, player.tag, name=player.name, primary=not accounts)
    await record_player(deps, player)
    await reply(
        event,
        f"✅ تم ربط الحساب: <b>{player.name}</b> <code>{player.tag}</code>",
        keyboards.profile_menu(True),
    )


@router.callback_query(F.data.startswith("acc:set:"))
async def set_primary_account(callback: CallbackQuery, deps: Deps) -> None:
    tag = callback.data.split(":", 2)[2]
    ok = await deps.accounts.set_primary(callback.from_user.id, tag)
    if ok:
        await callback.answer("⭐ تم تعيينه كحساب أساسي")
    await accounts(callback, deps)


@router.callback_query(F.data.startswith("acc:del:"))
async def delete_account(callback: CallbackQuery, deps: Deps) -> None:
    tag = callback.data.split(":", 2)[2]
    await deps.accounts.remove(callback.from_user.id, tag)
    remaining = await deps.accounts.list(callback.from_user.id)
    if remaining and not any(account.is_primary for account in remaining):
        await deps.accounts.set_primary(callback.from_user.id, remaining[0].player_tag)
    await callback.answer("🗑️ تم الحذف")
    await accounts(callback, deps)


@router.message(Command("unlink"))
async def cmd_unlink(message: Message, deps: Deps) -> None:
    account = await deps.accounts.primary(message.from_user.id)
    if not account:
        await message.answer(texts.NO_ACCOUNT)
        return
    await deps.accounts.remove(message.from_user.id, account.player_tag)
    await message.answer(f"✅ تم إلغاء ربط {account.player_tag}.")
