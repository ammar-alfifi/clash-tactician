"""Pure formatting helpers for clan roster, war targets and clan leaderboards.

These functions only shape data returned by the official Clash of Clans API into
safe Arabic HTML strings. They never call the network, which keeps them easy to
test and reuse from both message handlers and background reminders.
"""

from collections import Counter
from html import escape

ROLE_LABELS = {
    "leader": "قائد",
    "coLeader": "قائد مشارك",
    "admin": "مساعد",
    "member": "عضو",
}

WAR_STATE_LABELS = {
    "preparation": "مرحلة الاستعداد",
    "inWar": "حرب جارية",
    "warEnded": "انتهت الحرب",
}

ATTACKS_PER_MEMBER = 2


def _int(value: object) -> int:
    try:
        return int(value or 0)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return 0


def _float(value: object) -> float:
    try:
        return float(value or 0)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return 0.0


def _town_hall_level(member: dict) -> int:
    return _int(member.get("townHallLevel"))


def _name(member: dict) -> str:
    return escape(str(member.get("name") or "لاعب"))


def _clan_members(clan: dict) -> list[dict]:
    return [member for member in (clan.get("members") or []) if isinstance(member, dict)]


def _role_label(member: dict) -> str:
    return ROLE_LABELS.get(str(member.get("role")), "")


def format_clan_members(clan: dict, fallback_tag: str) -> str:
    members = _clan_members(clan)
    if not members:
        return "لا تتوفر قائمة أعضاء لهذه القبيلة حاليًا."

    name = escape(str(clan.get("name") or "قبيلة"))
    tag = escape(str(clan.get("tag") or fallback_tag))
    header = (
        f"<b>🧑‍🤝‍🧑 أعضاء {name}</b> — <code>{tag}</code>\n"
        f"المستوى: {clan.get('clanLevel', '—')} | الأعضاء: {len(members)}/50"
    )

    levels = [_town_hall_level(member) for member in members]
    distribution = ""
    if any(level > 0 for level in levels):
        counts = Counter(level for level in levels if level > 0)
        parts = [f"قاعة {level}: {count}" for level, count in sorted(counts.items(), reverse=True)]
        distribution = "\nتوزيع قاعات المدينة: " + " · ".join(parts)

    roles = Counter(str(member.get("role")) for member in members)
    role_parts = [f"{label} {roles[key]}" for key, label in ROLE_LABELS.items() if roles.get(key)]
    role_summary = "\nالأدوار: " + " · ".join(role_parts) if role_parts else ""

    ordered = sorted(
        members,
        key=lambda member: _int(member.get("clanRank")) or 10_000,
    )
    limit = 30
    lines = []
    for member in ordered[:limit]:
        level = _town_hall_level(member)
        level_part = f"قاعة {level}" if level else "قاعة —"
        role = _role_label(member)
        role_part = f" — {escape(role)}" if role else ""
        lines.append(
            f"• {_name(member)} — {level_part} — 🏆{_int(member.get('trophies'))}"
            f" — 🎁{_int(member.get('donations'))}{role_part}"
        )
    remaining = len(ordered) - len(lines)
    footer = f"\n… و{remaining} عضوًا آخر." if remaining > 0 else ""

    return (
        f"{header}{distribution}{role_summary}\n\n"
        "<b>القائمة (حسب الترتيب):</b>\n" + "\n".join(lines) + footer
    )


def _format_ranked(members: list[dict], key: str, unit: str, limit: int = 5) -> str:
    ranked = sorted(members, key=lambda member: _int(member.get(key)), reverse=True)
    ranked = [member for member in ranked if _int(member.get(key)) > 0][:limit]
    if not ranked:
        return "لا توجد بيانات كافية."
    return "\n".join(
        f"{index}. {_name(member)} — {_int(member.get(key))} {unit}"
        for index, member in enumerate(ranked, start=1)
    )


def _war_performance(war: dict) -> list[tuple[str, int, float, int]]:
    clan = war.get("clan") or {}
    performance = []
    for member in clan.get("members") or []:
        attacks = member.get("attacks") or []
        if not attacks:
            continue
        stars = sum(_int(attack.get("stars")) for attack in attacks)
        destruction = sum(_float(attack.get("destructionPercentage")) for attack in attacks)
        performance.append(
            (str(member.get("name") or "لاعب"), stars, destruction, len(attacks))
        )
    performance.sort(key=lambda item: (item[1], item[2]), reverse=True)
    return performance


def format_clan_stats(clan: dict, war: dict | None = None) -> str:
    members = _clan_members(clan)
    name = escape(str(clan.get("name") or "قبيلة"))
    tag = escape(str(clan.get("tag") or ""))
    lines = [
        f"<b>📊 إحصاءات وترتيب {name}</b> — <code>{tag}</code>",
        (
            f"المستوى: {clan.get('clanLevel', '—')} | الأعضاء: "
            f"{len(members)}/50 | النقاط: {clan.get('clanPoints', '—')}"
        ),
        f"دوري الحرب: {escape(str((clan.get('warLeague') or {}).get('name') or 'غير متاح'))}",
        "",
        "<b>🏆 أعلى الكؤوس:</b>",
        _format_ranked(members, "trophies", "🏆"),
        "",
        "<b>🎁 أكثر التبرعات:</b>",
        _format_ranked(members, "donations", "وحدة"),
        "",
        "<b>🏗️ مساهمات عاصمة القبيلة:</b>",
        _format_ranked(members, "clanCapitalContributions", "نقطة"),
    ]

    if war and war.get("state") in {"inWar", "warEnded"}:
        state = WAR_STATE_LABELS.get(str(war.get("state")), "غير معروفة")
        war_clan = war.get("clan") or {}
        war_members = _clan_members(war_clan)
        team_size = _int(war.get("teamSize"))
        used = sum(len(member.get("attacks") or []) for member in war_members)
        total = team_size * ATTACKS_PER_MEMBER if team_size else len(war_members) * ATTACKS_PER_MEMBER
        lines += [
            "",
            f"<b>⚔️ أداء الحرب الحالية ({state}):</b>",
            (
                f"هجمات مستخدمة: {used}/{total} | النجوم: {war_clan.get('stars', 0)} "
                f"| التدمير: {war_clan.get('destructionPercentage', 0)}٪"
            ),
        ]
        performance = _war_performance(war)[:5]
        if performance:
            lines.append("<b>أفضل المهاجمين:</b>")
            for index, (member_name, stars, _destruction, attacks) in enumerate(performance, start=1):
                lines.append(
                    f"{index}. {escape(member_name)} — {stars}⭐ ({attacks} هجمات)"
                )
        else:
            lines.append("لم تُسجَّل هجمات بعد.")
    return "\n".join(lines)


def _orient_war(war: dict, clan_tag: str | None) -> tuple[dict, dict]:
    clan = war.get("clan") or {}
    opponent = war.get("opponent") or {}
    if clan_tag and str(opponent.get("tag") or "") == clan_tag:
        return opponent, clan
    return clan, opponent


def _received_stars(our_members: list[dict]) -> tuple[dict[str, int], dict[str, int]]:
    best: dict[str, int] = {}
    count: dict[str, int] = {}
    for member in our_members:
        for attack in member.get("attacks") or []:
            defender = attack.get("defenderTag")
            if not defender:
                continue
            defender = str(defender)
            stars = _int(attack.get("stars"))
            best[defender] = max(best.get(defender, 0), stars)
            count[defender] = count.get(defender, 0) + 1
    return best, count


def format_war_targets(war: dict, clan_tag: str | None = None) -> str:
    if war.get("state") == "notInWar":
        return "لا توجد حرب قبلية متاحة لهذه القبيلة حاليًا."

    our_side, enemy_side = _orient_war(war, clan_tag)
    enemy_members = _clan_members(enemy_side)
    our_members = _clan_members(our_side)
    if not enemy_members:
        return "لم تتوفر قائمة قواعد الخصم بعد؛ جرّب مجددًا بعد بدء الحرب."

    best_stars, attacks_received = _received_stars(our_members)
    targets = []
    for member in enemy_members:
        tag = str(member.get("tag") or "")
        targets.append(
            {
                "name": _name(member),
                "th": _town_hall_level(member),
                "stars": best_stars.get(tag, 0),
                "count": attacks_received.get(tag, 0),
                "position": _int(member.get("mapPosition")),
            }
        )

    available = [target for target in targets if target["stars"] < 3]
    available.sort(key=lambda target: (target["stars"], target["th"], target["position"]))

    state = WAR_STATE_LABELS.get(str(war.get("state")), "غير معروفة")
    header = (
        f"<b>🎯 أهداف الحرب — {escape(str(our_side.get('name') or 'قبيلتك'))} "
        f"ضد {escape(str(enemy_side.get('name') or 'الخصم'))}</b>\n"
        f"الحالة: {state} | حجم الحرب: {war.get('teamSize', '—')}\n"
        f"قواعد الخصم: {len(targets)} | لم تُحسم بثلاث نجوم: {len(available)}"
    )

    lines = [header]
    if available:
        lines.append("\n<b>أفضل الأهداف المتاحة:</b>")
        limit = 12
        for target in available[:limit]:
            th = f"قاعة {target['th']}" if target["th"] else "قاعة —"
            if target["count"]:
                note = f"هوجمت {target['count']}×"
            else:
                note = "لم تُهاجَم بعد"
            lines.append(f"• {target['name']} — {th} — ⭐{target['stars']}/3 ({note})")
        remaining = len(available) - limit
        if remaining > 0:
            lines.append(f"… و{remaining} هدفًا آخر.")
    else:
        lines.append("\nأُحرزت ثلاث نجوم على كل قواعد الخصم المعلنة.")

    if war.get("state") == "inWar":
        pending = _pending_attackers(our_side)
        lines.append("\n<b>هجمات متبقية في قبيلتك:</b>")
        if pending:
            limit = 15
            for member_name, left in pending[:limit]:
                lines.append(f"• {escape(member_name)}: {left} متبقية")
            remaining = len(pending) - limit
            if remaining > 0:
                lines.append(f"… و{remaining} عضوًا آخر.")
        else:
            lines.append("استُخدمت كل الهجمات المتاحة.")

    return "\n".join(lines)


def _pending_attackers(our_side: dict) -> list[tuple[str, int]]:
    pending = []
    for member in _clan_members(our_side):
        used = len(member.get("attacks") or [])
        left = max(ATTACKS_PER_MEMBER - used, 0)
        if left:
            pending.append((str(member.get("name") or "لاعب"), left))
    pending.sort(key=lambda item: (-item[1], item[0]))
    return pending


def format_war_reminder(war: dict) -> str | None:
    """Return a reminder message for a war in progress, or None when nothing is due."""
    if war.get("state") != "inWar":
        return None
    our_side = war.get("clan") or {}
    pending = _pending_attackers(our_side)
    if not pending:
        return None

    lines = [
        f"⏰ <b>تذكير حرب — {escape(str(our_side.get('name') or 'قبيلتك'))}</b>",
        f"لديكم {len(pending)} عضوًا لم يستخدموا كل هجماتهم بعد:",
    ]
    limit = 20
    for member_name, left in pending[:limit]:
        lines.append(f"• {escape(member_name)}: {left} متبقية")
    remaining = len(pending) - limit
    if remaining > 0:
        lines.append(f"… و{remaining} عضوًا آخر.")
    lines.append("لإيقاف التذكير التلقائي يستخدم مشرف المجموعة /unsubscribe.")
    return "\n".join(lines)
