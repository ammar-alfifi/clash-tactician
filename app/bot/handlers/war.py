"""War center: current war, attacks and target suggestions."""

from __future__ import annotations

from aiogram import F, Router
from aiogram.filters import Command, CommandObject
from aiogram.types import CallbackQuery, Message

from app.bot import cards, keyboards, texts
from app.bot.deps import Deps
from app.bot.handlers.clan import _derived_clan
from app.bot.handlers.common import reply, safe_edit
from app.core.errors import CocError
from app.core.formatting import normalize_tag

router = Router(name="war")


async def show_war(event: Message | CallbackQuery, deps: Deps, tag: str) -> None:
    war = await deps.coc.war(tag)
    if not war.in_war and war.state != "warEnded":
        league = await deps.coc.league_group(tag)
        extra = ""
        if league:
            extra = "\n🏆 توجد بيانات دوري أبطال القبائل متاحة، لكن لا حرب جارية الآن."
        await safe_edit(
            event,
            f"⚔️ لا توجد حرب جارية حاليًا لهذه القبيلة.{extra}",
            keyboards.war_menu(tag),
        )
        return
    await safe_edit(event, cards.war_card(war), keyboards.war_menu(tag))


@router.message(Command("war"))
async def cmd_war(message: Message, command: CommandObject, deps: Deps) -> None:
    tag = normalize_tag(command.args) or await _derived_clan(message, deps)
    if not tag:
        return
    await _guard(message, deps, lambda: show_war(message, deps, tag))


@router.callback_query(F.data == "nav:war")
async def nav_war(callback: CallbackQuery, deps: Deps) -> None:
    tag = await _derived_clan(callback, deps)
    if not tag:
        return
    await _guard(callback, deps, lambda: show_war(callback, deps, tag))


@router.callback_query(F.data.startswith("war:view:"))
async def war_view(callback: CallbackQuery, deps: Deps) -> None:
    tag = callback.data.split(":", 2)[2]
    await _guard(callback, deps, lambda: show_war(callback, deps, tag))


@router.callback_query(F.data.startswith("war:attacks:"))
async def war_attacks(callback: CallbackQuery, deps: Deps) -> None:
    tag = callback.data.split(":", 2)[2]
    war = await deps.coc.war(tag)
    await safe_edit(callback, cards.attacks_card(war), keyboards.war_menu(tag))


@router.callback_query(F.data.startswith("war:targets:"))
async def war_targets(callback: CallbackQuery, deps: Deps) -> None:
    tag = callback.data.split(":", 2)[2]
    player_tag = await deps.primary_tag(callback.from_user.id)
    targets = await deps.coc.suggestions(tag, player_tag=player_tag)
    await safe_edit(callback, cards.targets_card(targets), keyboards.war_menu(tag))


@router.message(Command("targets"))
async def cmd_targets(message: Message, command: CommandObject, deps: Deps) -> None:
    tag = normalize_tag(command.args) or await _derived_clan(message, deps)
    if not tag:
        return
    player_tag = await deps.primary_tag(message.from_user.id)
    targets = await deps.coc.suggestions(tag, player_tag=player_tag)
    await message.answer(cards.targets_card(targets), reply_markup=keyboards.war_menu(tag))


async def _guard(event: Message | CallbackQuery, deps: Deps, action) -> None:
    if not deps.settings.has_coc:
        await reply(event, texts.NO_COC)
        return
    try:
        await action()
    except CocError as exc:
        await reply(event, f"⚠️ {exc.reason}")
