"""Group (war room) commands: link a clan, reminders and manual nudge."""

from __future__ import annotations

from aiogram import Bot, F, Router
from aiogram.filters import Command, CommandObject
from aiogram.types import Message

from app.bot import keyboards, texts
from app.bot.deps import Deps
from app.core.errors import CocError
from app.core.formatting import normalize_tag
from app.services.war_reminders import room_reminder_text

router = Router(name="groups")

GROUP_TYPES = {"group", "supergroup"}


async def _is_group_admin(message: Message, deps: Deps) -> bool:
    if deps.is_admin(message.from_user.id):
        return True
    try:
        member = await message.chat.get_member(message.from_user.id)
    except Exception:  # noqa: BLE001
        return False
    return getattr(member, "status", "") in {"administrator", "creator"}


async def _resolve_clan(message: Message, deps: Deps, explicit: str | None) -> str | None:
    tag = normalize_tag(explicit)
    if tag:
        return tag
    account = await deps.accounts.primary(message.from_user.id)
    if not account:
        return None
    try:
        player = await deps.coc.player(account.player_tag)
    except CocError:
        return None
    return player.clan_tag


@router.message(Command("warroom"), F.chat.type.in_(GROUP_TYPES))
async def cmd_warroom(message: Message, command: CommandObject, deps: Deps) -> None:
    if not await _is_group_admin(message, deps):
        await message.reply(texts.NOT_ADMIN)
        return
    if not deps.settings.has_coc:
        await message.reply(texts.NO_COC)
        return
    tag = await _resolve_clan(message, deps, command.args)
    if not tag:
        await message.reply(
            "أرسل وسم القبيلة صراحةً: <code>/warroom #ABC123</code> "
            "(أو اربط حسابك أولًا لأستنتج قبيلتك)."
        )
        return
    try:
        clan = await deps.coc.clan(tag)
    except CocError as exc:
        await message.reply(f"⚠️ {exc.reason}")
        return
    await deps.rooms.upsert(message.chat.id, clan.tag, message.from_user.id)
    await message.reply(
        f"✅ تم ربط هذه المجموعة بقبيلة <b>{clan.name}</b>.\n"
        "فعّل التذكيرات بـ <code>/subscribe</code> أو أرسل تذكيرًا فوريًا بـ <code>/remind</code>.",
        reply_markup=keyboards.back_home(),
    )


@router.message(Command("subscribe"), F.chat.type.in_(GROUP_TYPES))
async def cmd_subscribe(message: Message, command: CommandObject, deps: Deps) -> None:
    if not await _is_group_admin(message, deps):
        await message.reply(texts.NOT_ADMIN)
        return
    room = await deps.rooms.get(message.chat.id)
    if not room:
        await message.reply("اربط القبيلة أولًا بالأمر <code>/warroom #TAG</code>.")
        return
    interval = None
    if command.args and command.args.strip().isdigit():
        interval = max(5, min(int(command.args.strip()), 1440))
    await deps.rooms.set_reminders(message.chat.id, True, interval)
    await message.reply(
        f"🔔 تم تفعيل تذكيرات الحرب كل {interval or room.interval_minutes} دقيقة."
    )


@router.message(Command("unsubscribe"), F.chat.type.in_(GROUP_TYPES))
async def cmd_unsubscribe(message: Message, deps: Deps) -> None:
    if not await _is_group_admin(message, deps):
        await message.reply(texts.NOT_ADMIN)
        return
    await deps.rooms.set_reminders(message.chat.id, False)
    await message.reply("🔕 تم إيقاف التذكيرات.")


@router.message(Command("remind"), F.chat.type.in_(GROUP_TYPES))
async def cmd_remind(message: Message, deps: Deps, bot: Bot) -> None:
    if not await _is_group_admin(message, deps):
        await message.reply(texts.NOT_ADMIN)
        return
    room = await deps.rooms.get(message.chat.id)
    if not room:
        await message.reply("اربط القبيلة أولًا بالأمر <code>/warroom #TAG</code>.")
        return
    try:
        text = await room_reminder_text(deps, room.clan_tag)
    except CocError as exc:
        await message.reply(f"⚠️ {exc.reason}")
        return
    if not text:
        await message.reply("✅ لا يوجد من يحتاج تذكيرًا الآن (لا حرب جارية أو اكتملت الهجمات).")
        return
    await bot.send_message(message.chat.id, text)
    await deps.rooms.mark_reminded(message.chat.id)


@router.message(Command("remind"))
async def cmd_remind_private(message: Message, deps: Deps) -> None:
    await message.answer(texts.GROUP_ONLY)
