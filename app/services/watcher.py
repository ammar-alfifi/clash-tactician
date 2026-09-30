"""Background watcher: war events and player progress notifications."""

from __future__ import annotations

import asyncio
import logging

from aiogram import Bot

from app.bot.deps import Deps
from app.coc.models import war_fingerprint
from app.core.errors import CocError
from app.core.formatting import num
from app.services.snapshots import diff_payload, player_payload

logger = logging.getLogger(__name__)

WAR_TICK_SECONDS = 300
PROGRESS_EVERY_TICKS = 72  # ~6 hours at 5-minute ticks

WAR_STATES_ACTIVE = {"preparation", "inWar"}


async def check_wars(bot: Bot, deps: Deps) -> None:
    subs = await deps.subs.by_kind("war") + await deps.subs.by_kind("cwl")
    for sub in subs:
        try:
            war = await deps.coc.war(sub.target_tag)
        except CocError as exc:
            logger.debug("War check skipped for %s: %s", sub.target_tag, exc.reason)
            continue
        previous = await deps.war_state.get(sub.target_tag)
        previous_state = (previous[1] or {}).get("state") if previous else None
        await deps.war_state.set(
            sub.target_tag,
            war_fingerprint(war),
            {
                "state": war.state,
                "stars": war.clan.stars if war.clan else 0,
                "opponent_stars": war.opponent.stars if war.opponent else 0,
            },
        )
        message = _transition_message(war, previous_state)
        if message:
            try:
                await bot.send_message(sub.chat_id, message)
            except Exception:  # noqa: BLE001
                logger.debug("Could not notify %s", sub.chat_id, exc_info=True)


def _transition_message(war, previous_state: str | None) -> str | None:
    if war.state in WAR_STATES_ACTIVE and previous_state not in WAR_STATES_ACTIVE:
        label = "دوري أبطال القبائل" if war.is_cwl else "الحرب"
        opponent = war.opponent.name if war.opponent else "الخصم"
        return f"⚔️ <b>بدأت {label}</b> ضد <b>{opponent}</b>!\nوفّق الله قبيلتكم."
    if war.state == "warEnded" and previous_state != "warEnded":
        own = war.clan.stars if war.clan else 0
        their = war.opponent.stars if war.opponent else 0
        result = "🟢 فوز" if own > their else "🔴 خسارة" if own < their else "🟡 تعادل"
        return f"🏁 <b>انتهت الحرب</b> — {result}\nالنجوم: {own} ضد {their}"
    return None


async def check_progress(bot: Bot, deps: Deps) -> None:
    accounts = await deps.accounts.all()
    for account in accounts:
        try:
            player = await deps.coc.player(account.player_tag)
        except CocError:
            continue
        before = await deps.snapshots.latest("player", player.tag)
        payload = player_payload(player)
        await deps.snapshots.add("player", player.tag, payload)
        if not before:
            continue
        deltas = diff_payload(before[1], payload)
        if not deltas:
            continue
        user = await deps.users.get(account.telegram_id)
        if user is None or not user.notifications:
            continue
        message = _progress_message(player.name, deltas)
        if message:
            try:
                await bot.send_message(account.telegram_id, message)
            except Exception:  # noqa: BLE001
                logger.debug("Could not send progress DM to %s", account.telegram_id, exc_info=True)


def _progress_message(name: str, deltas: dict) -> str | None:
    lines: list[str] = []
    hero_changes = deltas.get("heroes", {})
    for hero, change in hero_changes.items():
        old, new = change
        if new > old:
            lines.append(f"🦸 {hero}: {old} ➜ <b>{new}</b>")
        elif new < old:
            lines.append(f"🦸 {hero}: نزل إلى {new}")
    for key, label in (
        ("trophies", "🏆 الكؤوس"),
        ("best_trophies", "🥇 أفضل كؤوس"),
        ("donations", "🎁 التبرعات"),
        ("war_stars", "⭐ نجوم الحرب"),
    ):
        if key in deltas:
            diff = int(deltas[key])
            arrow = "▲" if diff > 0 else "▼"
            lines.append(f"{label}: {arrow} {num(abs(diff))}")
    if not lines:
        return None
    return f"📊 <b>تطور {name}</b>\n" + "\n".join(lines)


async def watcher_loop(bot: Bot, deps: Deps) -> None:
    tick = 0
    while True:
        await asyncio.sleep(WAR_TICK_SECONDS)
        tick += 1
        try:
            await check_wars(bot, deps)
            if tick % PROGRESS_EVERY_TICKS == 0:
                await check_progress(bot, deps)
        except Exception:  # noqa: BLE001
            logger.warning("Watcher tick failed", exc_info=True)
