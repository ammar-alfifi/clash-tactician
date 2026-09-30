"""Clan dashboard: info, members, war log and capital."""

from __future__ import annotations

from aiogram import F, Router
from aiogram.filters import Command, CommandObject
from aiogram.types import CallbackQuery, Message

from app.bot import cards, keyboards, texts
from app.bot.deps import Deps
from app.bot.handlers.common import reply, safe_edit
from app.coc.models import Clan
from app.core.errors import CocError, CocNotFound
from app.core.formatting import normalize_tag

router = Router(name="clan")


async def fetch_clan(deps: Deps, tag: str) -> Clan:
    """Fetch a clan, accepting a player tag as a convenience fallback."""
    try:
        return await deps.coc.clan(tag)
    except CocNotFound:
        player = await deps.coc.player(tag)
        if not player.clan_tag:
            raise CocNotFound("لا ينتمي هذا اللاعب إلى قبيلة.") from None
        return await deps.coc.clan(player.clan_tag)


async def show_clan(event: Message | CallbackQuery, deps: Deps, tag: str) -> None:
    clan = await fetch_clan(deps, tag)
    await safe_edit(event, cards.clan_card(clan), keyboards.clan_menu(clan.tag))


@router.message(Command("clan", "c"))
async def cmd_clan(message: Message, command: CommandObject, deps: Deps) -> None:
    tag = normalize_tag(command.args)
    if not tag:
        tag = await _derived_clan(message, deps)
        if not tag:
            return
    await _guard(message, deps, lambda: show_clan(message, deps, tag))


@router.callback_query(F.data == "nav:clan")
async def nav_clan(callback: CallbackQuery, deps: Deps) -> None:
    tag = await _derived_clan(callback, deps)
    if not tag:
        return
    await _guard(callback, deps, lambda: show_clan(callback, deps, tag))


async def _derived_clan(event: Message | CallbackQuery, deps: Deps) -> str | None:
    account = await deps.accounts.primary(event.from_user.id)
    if not account:
        await reply(event, texts.NO_ACCOUNT, keyboards.profile_menu(False))
        return None
    try:
        player = await deps.coc.player(account.player_tag)
    except CocError as exc:
        await reply(event, f"⚠️ {exc.reason}")
        return None
    if not player.clan_tag:
        await reply(event, "هذا الحساب غير منضم إلى قبيلة حاليًا.")
        return None
    return player.clan_tag


async def _guard(event: Message | CallbackQuery, deps: Deps, action) -> None:
    if not deps.settings.has_coc:
        await reply(event, texts.NO_COC)
        return
    try:
        await action()
    except CocError as exc:
        await reply(event, f"⚠️ {exc.reason}")


@router.callback_query(F.data.startswith("clan:view:"))
async def view_clan(callback: CallbackQuery, deps: Deps) -> None:
    tag = callback.data.split(":", 2)[2]
    await _guard(callback, deps, lambda: show_clan(callback, deps, tag))


@router.callback_query(F.data.startswith("clan:members:"))
async def clan_members(callback: CallbackQuery, deps: Deps) -> None:
    tag = callback.data.split(":", 2)[2]
    clan = await fetch_clan(deps, tag)
    await safe_edit(callback, cards.members_card(clan), keyboards.clan_menu(clan.tag))


@router.callback_query(F.data.startswith("clan:don:"))
async def clan_donations(callback: CallbackQuery, deps: Deps) -> None:
    tag = callback.data.split(":", 2)[2]
    clan = await fetch_clan(deps, tag)
    await safe_edit(
        callback, cards.members_card(clan, sort="donations"), keyboards.clan_menu(clan.tag)
    )


@router.callback_query(F.data.startswith("clan:cap:"))
async def clan_capital_contrib(callback: CallbackQuery, deps: Deps) -> None:
    tag = callback.data.split(":", 2)[2]
    clan = await fetch_clan(deps, tag)
    await safe_edit(
        callback, cards.members_card(clan, sort="capital"), keyboards.clan_menu(clan.tag)
    )


@router.callback_query(F.data.startswith("clan:raid:"))
async def clan_raid(callback: CallbackQuery, deps: Deps) -> None:
    tag = callback.data.split(":", 2)[2]
    summary = await deps.coc.capital(tag)
    if not summary:
        await safe_edit(callback, "🏰 لا تتوفر بيانات غارة عاصمة حاليًا.", keyboards.clan_menu(tag))
        return
    await safe_edit(callback, cards.capital_card(summary), keyboards.clan_menu(tag))


@router.callback_query(F.data.startswith("clan:warlog:"))
async def clan_warlog(callback: CallbackQuery, deps: Deps) -> None:
    tag = callback.data.split(":", 2)[2]
    try:
        entries = await deps.coc.war_log(tag, 8)
    except CocError:
        entries = []
    await safe_edit(callback, cards.war_log_card(entries), keyboards.clan_menu(tag))


@router.message(Command("members"))
async def cmd_members(message: Message, deps: Deps) -> None:
    tag = await _derived_clan(message, deps)
    if tag:
        clan = await fetch_clan(deps, tag)
        await message.answer(cards.members_card(clan), reply_markup=keyboards.clan_menu(clan.tag))


@router.message(Command("top"))
async def cmd_top(message: Message, deps: Deps) -> None:
    tag = await _derived_clan(message, deps)
    if tag:
        clan = await fetch_clan(deps, tag)
        await message.answer(
            cards.members_card(clan, sort="donations"), reply_markup=keyboards.clan_menu(clan.tag)
        )
