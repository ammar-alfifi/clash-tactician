"""Message builders (cards) for player, clan, war and plans."""

from __future__ import annotations

from typing import Any

from app.coc.models import Clan, Player, War
from app.coc.service import CapitalSummary, Target
from app.core.formatting import esc, num, progress_bar, stars, th_emoji
from app.core.timeutil import humanize_seconds, parse_coc_time, relative_ar, remaining_until
from app.planner.schema import Plan

ROLE_AR = {
    "leader": "👑 قائد",
    "coLeader": "🥇 مساعد",
    "admin": "🎖️ شيخ",
    "member": "👤 عضو",
}

WAR_STATE_AR = {
    "notInWar": "لا توجد حرب",
    "preparation": "⏳ التحضير",
    "inWar": "⚔️ الحرب جارية",
    "warEnded": "🏁 انتهت الحرب",
    "unknown": "غير معروف",
}

CAPITAL_STATE_AR = {
    "ongoing": "⚔️ غارة جارية",
    "ended": "🏁 انتهت الغارة",
    "unknown": "غير معروف",
}


def player_card(player: Player, *, is_primary: bool = False) -> str:
    lines = [
        f"🧑 <b>{esc(player.name)}</b>  <code>{esc(player.tag)}</code>",
        f"{th_emoji(player.town_hall)} • المستوى {player.exp_level} "
        f"• {esc(player.league or 'بلا دوري')}",
    ]
    if player.clan_name:
        lines.append(f"🛡️ {esc(player.clan_name)} <code>{esc(player.clan_tag or '')}</code>")
    lines.append("")
    lines.append(f"🏆 الكؤوس: <b>{num(player.trophies)}</b> (الأفضل {num(player.best_trophies)})")
    lines.append(
        f"⭐ نجوم الحرب: <b>{num(player.war_stars)}</b> "
        f"• هجمات فائزة {num(player.attack_wins)}"
    )
    lines.append(
        f"🎁 التبرعات: <b>{num(player.donations)}</b> / استقبل {num(player.donations_received)}"
    )
    if player.clan_capital_contributions:
        lines.append(f"🏰 مساهمات العاصمة: {num(player.clan_capital_contributions)}")
    if player.role:
        lines.append(f"الدور: {ROLE_AR.get(player.role, player.role)}")

    home_heroes = [hero for hero in player.heroes if hero.village == "home"]
    if home_heroes:
        lines.append("")
        lines.append("<b>الأبطال</b>")
        for hero in home_heroes:
            lines.append(
                f"{progress_bar(hero.level, hero.max_level)} "
                f"{esc(hero.name)} <b>{hero.level}</b>/{hero.max_level}"
            )
    return "\n".join(lines)


def growth_card(player: Player, previous: dict[str, Any] | None, when: str | None) -> str:
    if not previous:
        return "📊 لا توجد قياسات سابقة بعد. سأبدأ بتتبّع تطورك تلقائيًا."
    lines = ["📊 <b>تطور حسابك</b>"]
    if when:
        lines.append(f"(مقارنة مع آخر قياس {esc(when)})")
    lines.append("")

    def delta(key: str, label: str, current: int) -> str:
        old = int(previous.get(key, current) or 0)
        diff = current - old
        arrow = "▲" if diff > 0 else "▼" if diff < 0 else "＝"
        return f"{label}: {num(current)} ({arrow} {num(abs(diff))})"

    lines.append(delta("trophies", "🏆 الكؤوس", player.trophies))
    lines.append(delta("best_trophies", "🥇 أفضل كؤوس", player.best_trophies))
    lines.append(delta("donations", "🎁 التبرعات", player.donations))
    lines.append(delta("war_stars", "⭐ نجوم الحرب", player.war_stars))
    lines.append(
        delta("clan_capital_contributions", "🏰 العاصمة", player.clan_capital_contributions)
    )
    return "\n".join(lines)


def clan_card(clan: Clan) -> str:
    lines = [
        f"🛡️ <b>{esc(clan.name)}</b>  <code>{esc(clan.tag)}</code>",
        f"المستوى {clan.level} • {esc(clan.location or 'غير محدد')} • {esc(clan.type or '')}",
    ]
    if clan.description:
        lines.append(f"📝 {esc(clan.description)}")
    lines.append("")
    lines.append(f"👥 الأعضاء: <b>{clan.member_count}</b>")
    lines.append(f"🏅 نقاط القبيلة: <b>{num(clan.clan_points)}</b>")
    lines.append(
        f"⚔️ سجل الحرب: فوز <b>{num(clan.war_wins)}</b> "
        f"• خسارة {num(clan.war_losses)} • تعادل {num(clan.war_ties)}"
    )
    lines.append(f"🔥 سلسلة الفوز: <b>{num(clan.war_streak)}</b>")
    if clan.capital_hall_level:
        lines.append(f"🏰 قاعة العاصمة: مستوى {clan.capital_hall_level}")
    if clan.members:
        lines.append("")
        top = clan.members[0]
        lines.append(f"🏆 أفضل الأعضاء في الكؤوس: {esc(top.name)} ({num(top.trophies)})")
    return "\n".join(lines)


def members_card(clan: Clan, limit: int = 30, *, sort: str = "trophies") -> str:
    members = list(clan.members)
    if sort == "donations":
        members.sort(key=lambda m: m.donations, reverse=True)
    elif sort == "capital":
        members.sort(key=lambda m: m.clan_capital_contributions, reverse=True)
    else:
        members.sort(key=lambda m: m.trophies, reverse=True)

    header = {
        "trophies": "🏆 الأعضاء حسب الكؤوس",
        "donations": "🎁 الأعضاء حسب التبرعات",
        "capital": "🏰 الأعضاء حسب مساهمات العاصمة",
    }.get(sort, "👥 الأعضاء")

    lines = [f"<b>{header}</b>", ""]
    for index, member in enumerate(members[:limit], start=1):
        role = ROLE_AR.get(member.role, member.role).split()[-1]
        lines.append(
            f"{index:>2}. {th_emoji(member.town_hall)} {esc(member.name)} "
            f"— 🏆{num(member.trophies)} 🎁{num(member.donations)} ({esc(role)})"
        )
    if len(members) > limit:
        lines.append(f"… و{len(members) - limit} عضوًا آخر.")
    return "\n".join(lines)


def war_card(war: War) -> str:
    state = WAR_STATE_AR.get(war.state, war.state)
    lines = [f"{state}"]
    if war.state == "preparation":
        lines.append(f"يبدأ بعد: <b>{remaining_until(parse_coc_time(war.start_time))}</b>")
    elif war.state == "inWar":
        lines.append(f"ينتهي بعد: <b>{remaining_until(parse_coc_time(war.end_time))}</b>")
    if war.is_cwl:
        lines.append("🏆 وضع دوري أبطال القبائل (CWL)")
    lines.append("")

    if war.clan and war.opponent:
        lines.append(f"🛡️ <b>{esc(war.clan.name)}</b>  ضد  ⚔️ <b>{esc(war.opponent.name)}</b>")
        lines.append(
            f"║ {stars(war.clan.stars)} {num(war.clan.stars)} نجوم  —  "
            f"{num(war.opponent.stars)} نجوم {stars(war.opponent.stars)} ║"
        )
        lines.append(
            f"║ التدمير: {war.clan.destruction:.1f}%  —  {war.opponent.destruction:.1f}% ║"
        )
        used, total = war.attacks_used(), war.total_attacks
        lines.append("")
        lines.append(f"🎯 هجماتنا: <b>{used}</b>/{total} {progress_bar(used, total)}")
        lines.append(
            f"🛡️ هجماتهم: <b>{war.opponent.attacks}</b>/{total} "
            f"{progress_bar(war.opponent.attacks, total)}"
        )
        if war.state == "inWar":
            remaining = total - used
            lines.append(f"⏳ هجماتك المتبقية على مستوى القبيلة: <b>{remaining}</b>")
    else:
        lines.append("لا توجد تفاصيل حرب متاحة الآن.")
    return "\n".join(lines)


def attacks_card(war: War, limit: int = 18) -> str:
    if not war.in_war or not war.clan:
        return "لا توجد حرب جارية لعرض الهجمات."
    members = sorted(war.clan.members, key=lambda m: m.map_position)
    rows = ["<b>🧾 حالة هجمات الأعضاء</b>", ""]
    for member in members[:limit]:
        used = len(member.attacks)
        total = war.attacks_per_member
        check = "✅" if used >= total else ("🟡" if used else "🔴")
        rows.append(
            f"{check} {esc(member.name)} — {used}/{total} "
            f"({stars(member.stars)} {member.destruction}%)"
        )
    missing = [m for m in war.clan.members if len(m.attacks) < war.attacks_per_member]
    rows.append("")
    rows.append(f"⚠️ لم يكملوا هجماتهم: <b>{len(missing)}</b>")
    if missing:
        rows.append("، ".join(esc(m.name) for m in missing[:20]))
    return "\n".join(rows)


def targets_card(targets: list[Target]) -> str:
    if not targets:
        return "🎯 لا توجد أهداف متاحة (لا حرب جارية، أو لم تُجلب البيانات بعد)."
    rows = ["<b>🎯 أهداف مقترحة (العدو)</b>", ""]
    for target in targets[:20]:
        flag = "🟢 مفتوح" if target.open else "🔴 مُغطّى"
        star_mark = "⬜" if target.perfect else "✅"
        rows.append(
            f"{target.position}. {th_emoji(target.town_hall)} {esc(target.name)} "
            f"— {star_mark} {stars(target.stars)} {target.destruction}% • {flag}"
        )
    rows.append("")
    rows.append("🟢 = ما زال قابلًا للهجوم • ⬜ = لم يُحقّق ٣ نجوم بعد")
    return "\n".join(rows)


def capital_card(summary: CapitalSummary) -> str:
    state = CAPITAL_STATE_AR.get(summary.state, summary.state)
    lines = ["🏰 <b>عاصمة القبيلة</b>", state]
    if summary.state == "ongoing":
        lines.append(f"ينتهي بعد: <b>{remaining_until(parse_coc_time(summary.end_time))}</b>")
    lines.extend(
        [
            "",
            f"💰 الغنائم: <b>{num(summary.capital_total_loot)}</b>",
            f"⚔️ الهجمات: <b>{num(summary.total_attacks)}</b> "
            f"• مناطق مدمّرة {num(summary.total_districts)}",
            f"🏅 مكافأة الهجوم: {num(summary.offensive_reward)} "
            f"• الدفاع: {num(summary.defensive_reward)}",
        ]
    )
    members = sorted(
        summary.members, key=lambda m: int(m.get("capitalResourcesLooted", 0) or 0), reverse=True
    )[:10]
    if members:
        lines.append("")
        lines.append("<b>أفضل المساهمين</b>")
        for index, member in enumerate(members, start=1):
            lines.append(
                f"{index}. {esc(member.get('name', '?'))} "
                f"— 💰{num(member.get('capitalResourcesLooted'))}"
            )
    return "\n".join(lines)


def plan_text(plan: Plan, *, header: str = "🎯 <b>خطة الهجوم</b>") -> str:
    lines = [
        header,
        f"🎯 الهدف: <b>{esc(plan.goal_label)}</b> "
        f"• الثقة: <b>{esc(plan.confidence_label)}</b> ({plan.confidence:.0%})",
    ]
    if plan.style:
        lines.append(f"🧭 الأسلوب: <b>{esc(plan.style)}</b>")
    if plan.summary:
        lines.append(f"\n📝 {esc(plan.summary)}")
    lines.append("")
    for index, phase in enumerate(plan.phases, start=1):
        lines.append(f"<b>{index}. {esc(phase.name)}</b>")
        lines.append(f"• {esc(phase.action)}")
        if phase.reason:
            lines.append(f"  ↳ <i>{esc(phase.reason)}</i>")
        if phase.depends_on:
            lines.append(f"  ⚠️ يتطلب: {esc('، '.join(phase.depends_on))}")
    if plan.risks:
        lines.append("")
        lines.append("<b>⚠️ المخاطر</b>")
        lines.extend(f"• {esc(item)}" for item in plan.risks)
    if plan.alternatives:
        lines.append("")
        lines.append("<b>🔁 بدائل عند الفشل</b>")
        lines.extend(f"• {esc(item)}" for item in plan.alternatives)
    if plan.uncertainties:
        lines.append("")
        lines.append("<b>❔ نقاط غير مؤكدة من الصورة</b>")
        lines.extend(f"• {esc(item)}" for item in plan.uncertainties)
    if plan.army_notes:
        lines.append("")
        lines.append("<b>🪖 ملاحظات التشكيلة</b>")
        lines.extend(f"• {esc(item)}" for item in plan.army_notes)
    lines.append("")
    lines.append("<i>خطة مقترحة للمراجعة، والنتيجة تعتمد على التنفيذ.</i>")
    text = "\n".join(lines)
    if len(text) > 3900:
        text = text[:3880].rstrip() + "\n…"
    return text


def war_log_card(entries: list[dict[str, Any]]) -> str:
    if not entries:
        return "📈 لا يتوفر سجل حرب لهذه القبيلة (قد يكون خاصًا)."
    lines = ["<b>📈 آخر نتائج الحرب</b>", ""]
    for entry in entries:
        result = entry.get("result")
        outcome = {
            "win": "🟢 فوز",
            "lose": "🔴 خسارة",
            "tie": "🟡 تعادل",
        }.get(str(result), "•")
        opponent = entry.get("opponent", {})
        summary = entry.get("clan", {})
        lines.append(
            f"{outcome} ضد {esc(opponent.get('name', '?'))} "
            f"— نجومنا {num(summary.get('stars'))} / لهم {num(opponent.get('stars'))} "
            f"({entry.get('teamSize', '?')} ضد {entry.get('teamSize', '?')})"
        )
    return "\n".join(lines)


def ticket_card(ticket_id: int, kind: str, body: str, user_id: int) -> str:
    kind_ar = {"bug": "🐞 مشكلة", "help": "❓ مساعدة", "idea": "💡 اقتراح"}.get(kind, kind)
    return (
        f"🗂️ <b>تذكرة #{ticket_id}</b> ({kind_ar})\n"
        f"من: <code>{user_id}</code>\n\n{esc(body)}"
    )


def time_ago(value: str | None) -> str:
    return relative_ar(parse_coc_time(value))


def duration_label(start: str | None, end: str | None) -> str:
    start_dt, end_dt = parse_coc_time(start), parse_coc_time(end)
    if not start_dt or not end_dt:
        return "—"
    return humanize_seconds((end_dt - start_dt).total_seconds())


def detections_card(plan: Plan) -> str:
    """Show what the model believes it read from the image (transparency)."""
    from app.planner.validator import detected_summary

    lines = ["🔍 <b>ما قرأته من الصورة</b>", detected_summary(plan.detections)]
    low = [d for d in plan.detections if d.confidence < 0.4]
    if low:
        lines.append("")
        lines.append("⚠️ عناصر بثقة منخفضة (تحتاج تأكيدًا):")
        lines.extend(f"• {esc(d.building)} ({d.cell})" for d in low[:6])
    return "\n".join(lines)


def validation_card(validation) -> str:
    if not validation.issues and not validation.warnings:
        return ""
    lines = ["🧪 <b>تحقق الخادم</b>"]
    if validation.issues:
        lines.append("❌ مشاكل تمنع الاعتماد:")
        lines.extend(f"• {esc(item)}" for item in validation.issues)
    if validation.warnings:
        lines.append("⚠️ تنبيهات:")
        lines.extend(f"• {esc(item)}" for item in validation.warnings)
    return "\n".join(lines)
