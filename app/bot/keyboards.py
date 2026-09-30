"""Inline keyboard builders. Callback data uses `prefix:action:payload` strings."""

from __future__ import annotations

from collections.abc import Iterable

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from app.storage.models import Account, Plan, Subscription


def _rows(buttons: Iterable[Iterable[InlineKeyboardButton]]) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[list(row) for row in buttons])


def _btn(text: str, data: str) -> InlineKeyboardButton:
    return InlineKeyboardButton(text=text, callback_data=data)


def main_menu() -> InlineKeyboardMarkup:
    return _rows(
        [
            [_btn("🎯 خطة هجوم", "nav:planner"), _btn("🧑 ملفي", "nav:profile")],
            [_btn("🛡️ قبيلتي", "nav:clan"), _btn("⚔️ الحرب", "nav:war")],
            [_btn("📚 خططي", "nav:plans"), _btn("🔔 المراقبة", "nav:watch")],
            [_btn("🤖 اسأل المدرب", "nav:ask"), _btn("⚙️ الإعدادات", "nav:settings")],
            [_btn("💬 الدعم والأفكار", "nav:support"), _btn("ℹ️ مساعدة", "nav:help")],
        ]
    )


def back_home(extra: Iterable[InlineKeyboardButton] = ()) -> InlineKeyboardMarkup:
    rows = [[button] for button in extra]
    rows.append([_btn("🏠 القائمة", "nav:home")])
    return _rows(rows)


def profile_menu(has_account: bool) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []
    if has_account:
        rows.append(
            [
                _btn("🔄 تحديث", "profile:refresh"),
                _btn("📊 التطور", "profile:growth"),
            ]
        )
        rows.append([_btn("🗂️ حساباتي", "profile:accounts")])
    rows.append([_btn("🔗 ربط حساب", "profile:link")])
    rows.append([_btn("🏠 القائمة", "nav:home")])
    return _rows(rows)


def accounts_menu(accounts: list[Account]) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []
    for account in accounts:
        label = account.name or account.player_tag
        star = "⭐ " if account.is_primary else ""
        rows.append([_btn(f"{star}{label}", f"acc:set:{account.player_tag}")])
        rows.append([_btn(f"🗑️ حذف {account.player_tag}", f"acc:del:{account.player_tag}")])
    rows.append([_btn("🔗 إضافة حساب", "profile:link")])
    rows.append([_btn("🏠 القائمة", "nav:home")])
    return _rows(rows)


def clan_menu(clan_tag: str) -> InlineKeyboardMarkup:
    return _rows(
        [
            [
                _btn("👥 الأعضاء", f"clan:members:{clan_tag}"),
                _btn("🎁 التبرعات", f"clan:don:{clan_tag}"),
            ],
            [
                _btn("🏅 مساهمات العاصمة", f"clan:cap:{clan_tag}"),
                _btn("⚔️ غارة العاصمة", f"clan:raid:{clan_tag}"),
            ],
            [_btn("📈 سجل الحرب", f"clan:warlog:{clan_tag}")],
            [_btn("🔄 تحديث", f"clan:view:{clan_tag}"), _btn("🏠 القائمة", "nav:home")],
        ]
    )


def war_menu(clan_tag: str) -> InlineKeyboardMarkup:
    return _rows(
        [
            [_btn("🎯 أهداف مقترحة", f"war:targets:{clan_tag}")],
            [_btn("🧾 الهجمات", f"war:attacks:{clan_tag}")],
            [_btn("🔄 تحديث", f"war:view:{clan_tag}")],
            [_btn("🏠 القائمة", "nav:home")],
        ]
    )


def planner_goals() -> InlineKeyboardMarkup:
    return _rows(
        [
            [_btn("⭐ ثلاث نجوم", "plan:goal:three_stars")],
            [_btn("✌️ نجمتان", "plan:goal:two_stars")],
            [_btn("⭐ نجمة", "plan:goal:one_star")],
            [_btn("🧹 تنظيف", "plan:goal:cleanup")],
            [_btn("🎓 تدريب", "plan:goal:practice")],
            [_btn("✖️ إلغاء", "plan:cancel")],
        ]
    )


def planner_ask_army() -> InlineKeyboardMarkup:
    return _rows(
        [
            [_btn("⏭️ تخطّي (استخدم حسابي)", "plan:skiparmy")],
            [_btn("✖️ إلغاء", "plan:cancel")],
        ]
    )


def planner_ask_image() -> InlineKeyboardMarkup:
    return _rows(
        [
            [_btn("⏭️ تخطّي الصورة (خطة نصية)", "plan:skipimage")],
            [_btn("✖️ إلغاء", "plan:cancel")],
        ]
    )


def plan_result(plan_id: int | None = None) -> InlineKeyboardMarkup:
    rows = [
        [_btn("🔄 خطة بديلة", "plan:again"), _btn("✏️ عدّل الخطة", "plan:refine")],
    ]
    if plan_id:
        rows.append([_btn("💾 محفوظة في خططي ✅", "plan:saved")])
    else:
        rows.append([_btn("💾 حفظ الخطة", "plan:save")])
    rows.append([_btn("🎯 خطة جديدة", "plan:new"), _btn("🏠 القائمة", "nav:home")])
    return _rows(rows)


def library_menu(plans: list[Plan]) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []
    for plan in plans:
        title = plan.title or f"خطة #{plan.id}"
        rows.append(
            [
                _btn(f"📄 {title[:32]}", f"lib:view:{plan.id}"),
                _btn("🗑️", f"lib:del:{plan.id}"),
            ]
        )
    rows.append([_btn("🎯 خطة جديدة", "plan:new")])
    rows.append([_btn("🏠 القائمة", "nav:home")])
    return _rows(rows)


def plan_view(plan_id: int) -> InlineKeyboardMarkup:
    return _rows(
        [
            [_btn("🗑️ حذف", f"lib:del:{plan_id}")],
            [_btn("📚 خططي", "nav:plans"), _btn("🏠 القائمة", "nav:home")],
        ]
    )


def settings_menu() -> InlineKeyboardMarkup:
    return _rows(
        [
            [_btn("🔑 مفاتيح الذكاء الاصطناعي", "set:keys")],
            [_btn("🔔 الإشعارات", "set:notif")],
            [_btn("🌐 اللغة", "set:lang")],
            [_btn("🧾 خصوصيتي وبياناتي", "set:privacy")],
            [_btn("🏠 القائمة", "nav:home")],
        ]
    )


def language_menu(current: str) -> InlineKeyboardMarkup:
    arabic = "✅ العربية" if current == "ar" else "العربية"
    english = "✅ English" if current == "en" else "English"
    return _rows(
        [
            [_btn(arabic, "set:lang:ar"), _btn(english, "set:lang:en")],
            [_btn("⬅️ رجوع", "nav:settings")],
        ]
    )


def keys_menu(has_key: bool, provider_label: str | None = None) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []
    if has_key:
        rows.append([_btn(f"🧪 اختبار ({provider_label})", "key:test")])
        rows.append([_btn("♻️ استبدال المفتاح", "key:add"), _btn("🗑️ حذف", "key:delete")])
    else:
        rows.append([_btn("➕ إضافة مفتاح خاص", "key:add")])
    rows.append([_btn("⬅️ رجوع", "nav:settings")])
    return _rows(rows)


def providers_menu() -> InlineKeyboardMarkup:
    return _rows(
        [
            [_btn("🌐 OpenRouter (موصى)", "key:prov:openrouter")],
            [_btn("🟢 OpenAI", "key:prov:openai")],
            [_btn("🔵 Gemini", "key:prov:gemini")],
            [_btn("🛠️ خدمة متوافقة (مخصص)", "key:prov:custom")],
            [_btn("✖️ إلغاء", "nav:settings")],
        ]
    )


def watch_menu(subs: list[Subscription]) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []
    for sub in subs:
        kind = "حرب" if sub.kind == "war" else "بطولات القبائل" if sub.kind == "cwl" else sub.kind
        rows.append(
            [
                _btn(f"🔔 {kind}: {sub.target_tag}", f"watch:del:{sub.kind}:{sub.target_tag}"),
            ]
        )
    rows.append(
        [
            _btn("➕ مراقبة قبيلة (حرب)", "watch:add:war"),
            _btn("➕ مراقبة CWL", "watch:add:cwl"),
        ]
    )
    rows.append([_btn("🏠 القائمة", "nav:home")])
    return _rows(rows)


def support_kinds() -> InlineKeyboardMarkup:
    return _rows(
        [
            [_btn("🐞 مشكلة تقنية", "sup:kind:bug")],
            [_btn("❓ طلب مساعدة", "sup:kind:help")],
            [_btn("💡 اقتراح ميزة", "sup:kind:idea")],
            [_btn("✖️ إلغاء", "nav:home")],
        ]
    )


def admin_menu() -> InlineKeyboardMarkup:
    return _rows(
        [
            [_btn("📊 إحصاءات", "admin:stats"), _btn("📣 بث", "admin:broadcast")],
            [_btn("🏠 القائمة", "nav:home")],
        ]
    )


def notifications_menu(enabled: bool) -> InlineKeyboardMarkup:
    toggle = "🔕 إيقاف الإشعارات" if enabled else "🔔 تفعيل الإشعارات"
    return _rows(
        [
            [_btn(toggle, "set:notif:toggle")],
            [_btn("⬅️ رجوع", "nav:settings")],
        ]
    )


def key_model_menu() -> InlineKeyboardMarkup:
    return _rows(
        [
            [_btn("✅ استخدم النموذج الافتراضي", "key:defmodel")],
            [_btn("✖️ إلغاء", "nav:settings")],
        ]
    )


def privacy_menu() -> InlineKeyboardMarkup:
    return _rows(
        [
            [_btn("🗑️ حذف كل بياناتي", "set:privacy:delete")],
            [_btn("⬅️ رجوع", "nav:settings")],
        ]
    )


def confirm_menu(confirm_data: str, cancel_data: str = "nav:home") -> InlineKeyboardMarkup:
    return _rows(
        [
            [_btn("✅ تأكيد", confirm_data), _btn("✖️ إلغاء", cancel_data)],
        ]
    )
