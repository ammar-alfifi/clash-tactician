"""Settings: language, notifications, privacy and AI key management."""

from __future__ import annotations

import contextlib
import logging

from aiogram import F, Router
from aiogram.enums import ChatType
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from app.ai.factory import build_user_configs, is_safe_base_url
from app.ai.providers import PROVIDER_LABELS, default_model, ping_all
from app.bot import keyboards, texts
from app.bot.deps import Deps
from app.bot.handlers.common import reply, safe_edit
from app.bot.states import KeyFlow
from app.core.errors import AppError, ConfigurationError
from app.storage.models import AiKey

logger = logging.getLogger(__name__)
router = Router(name="settings")

PROVIDERS = {"openrouter", "openai", "gemini", "custom"}


def _is_private(event: Message | CallbackQuery) -> bool:
    message = event.message if isinstance(event, CallbackQuery) else event
    return bool(message and message.chat.type == ChatType.PRIVATE)


@router.callback_query(F.data == "nav:settings")
async def nav_settings(callback: CallbackQuery, deps: Deps) -> None:
    if not _is_private(callback):
        await callback.answer(texts.PRIVATE_ONLY, show_alert=True)
        return
    await safe_edit(callback, "⚙️ <b>الإعدادات</b>\nاختر ما تريد ضبطه:", keyboards.settings_menu())


@router.message(Command("settings"))
async def cmd_settings(message: Message, deps: Deps) -> None:
    await message.answer("⚙️ <b>الإعدادات</b>", reply_markup=keyboards.settings_menu())


# -- language --------------------------------------------------------------
@router.callback_query(F.data == "set:lang")
async def lang_menu(callback: CallbackQuery, deps: Deps) -> None:
    language = await deps.users.language(callback.from_user.id)
    await safe_edit(callback, "🌐 اختر لغة الواجهة:", keyboards.language_menu(language))


@router.callback_query(F.data.startswith("set:lang:"))
async def set_lang(callback: CallbackQuery, deps: Deps) -> None:
    language = callback.data.split(":", 2)[2]
    await deps.users.set_language(callback.from_user.id, language)
    await callback.answer("✅ تم تغيير اللغة" if language == "ar" else "✅ Language updated")
    await nav_settings(callback, deps)


# -- notifications ---------------------------------------------------------
@router.callback_query(F.data == "set:notif")
async def notif_menu(callback: CallbackQuery, deps: Deps) -> None:
    user = await deps.users.get(callback.from_user.id)
    enabled = user.notifications if user else True
    await safe_edit(
        callback,
        "🔔 الإشعارات: أرسل لك تنبيهات الحرب وتطور حسابك.",
        keyboards.notifications_menu(enabled),
    )


@router.callback_query(F.data == "set:notif:toggle")
async def notif_toggle(callback: CallbackQuery, deps: Deps) -> None:
    user = await deps.users.get(callback.from_user.id)
    enabled = not (user.notifications if user else True)
    await deps.users.set_notifications(callback.from_user.id, enabled)
    await callback.answer("🔔 مفعّلة" if enabled else "🔕 موقوفة")
    await notif_menu(callback, deps)


# -- privacy ---------------------------------------------------------------
@router.callback_query(F.data == "set:privacy")
async def privacy(callback: CallbackQuery) -> None:
    await safe_edit(callback, texts.PRIVACY, keyboards.privacy_menu())


@router.callback_query(F.data == "set:privacy:delete")
async def privacy_delete_confirm(callback: CallbackQuery) -> None:
    await safe_edit(
        callback,
        "⚠️ سيُحذف حسابك وكل بياناتك (الحسابات المرتبطة، المفاتيح، الخطط) نهائيًا. متأكد؟",
        keyboards.confirm_menu("set:privacy:confirm", "nav:settings"),
    )


@router.callback_query(F.data == "set:privacy:confirm")
async def privacy_delete(callback: CallbackQuery, deps: Deps) -> None:
    await deps.users.delete(callback.from_user.id)
    await safe_edit(callback, "🗑️ تم حذف جميع بياناتك.", keyboards.main_menu())


# -- AI keys ---------------------------------------------------------------
@router.callback_query(F.data == "set:keys")
async def keys_overview(callback: CallbackQuery, deps: Deps) -> None:
    if not _is_private(callback):
        await callback.answer(texts.PRIVATE_ONLY, show_alert=True)
        return
    key = await deps.keys.get(callback.from_user.id)
    if key:
        text = (
            "🔑 <b>مفتاحك الحالي</b>\n"
            f"المزود: <b>{PROVIDER_LABELS.get(key.provider, key.provider)}</b>\n"
            f"النموذج: <code>{key.model}</code>\n"
            f"الحالة: {'✅ يعمل' if key.ok else '⚠️ يحتاج اختبارًا'}"
        )
        await safe_edit(callback, text, keyboards.keys_menu(True, key.provider))
    else:
        shared = "المفتاح المشترك مفعّل ✅" if deps.settings.has_shared_ai else "لا يوجد مفتاح مشترك"
        text = (
            "🔑 <b>مفاتيح الذكاء الاصطناعي</b>\n\n"
            "أضف مفتاحك الشخصي لاستخدامه أنت فقط (مشفّرًا).\n"
            f"{shared}"
        )
        await safe_edit(callback, text, keyboards.keys_menu(False))


@router.callback_query(F.data == "key:add")
async def key_add(callback: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(KeyFlow.provider)
    await safe_edit(callback, "اختر مزود الذكاء الاصطناعي:", keyboards.providers_menu())


@router.callback_query(F.data.startswith("key:prov:"))
async def key_provider(callback: CallbackQuery, state: FSMContext) -> None:
    provider = callback.data.split(":", 2)[2]
    if provider not in PROVIDERS:
        provider = "openrouter"
    await state.update_data(provider=provider)
    if provider == "custom":
        await state.set_state(KeyFlow.custom_base)
        await safe_edit(
            callback,
            "أرسل عنوان الخدمة الكامل (HTTPS) المتوافق مع OpenAI.\n"
            "مثال: <code>https://api.example.com/v1</code>",
            keyboards.back_home(),
        )
        return
    await state.set_state(KeyFlow.model)
    await safe_edit(
        callback,
        f"أرسل معرّف النموذج، أو اضغط «الافتراضي» ({default_model(provider)}).",
        keyboards.key_model_menu(),
    )


@router.message(KeyFlow.custom_base, F.text)
async def custom_base(message: Message, state: FSMContext) -> None:
    url = message.text.strip()
    if not is_safe_base_url(url):
        await message.answer("عنوان غير صالح. يجب أن يكون HTTPS وليس عنوانًا داخليًا.")
        return
    await state.update_data(base_url=url)
    await state.set_state(KeyFlow.model)
    await message.answer("أرسل معرّف النموذج لهذه الخدمة.", reply_markup=keyboards.key_model_menu())


@router.message(KeyFlow.model, F.text)
async def custom_model(message: Message, state: FSMContext) -> None:
    await _after_model(message, state, message.text.strip()[:120])


@router.callback_query(KeyFlow.model, F.data == "key:defmodel")
async def default_model_step(callback: CallbackQuery, state: FSMContext) -> None:
    data = await state.get_data()
    model = default_model(data.get("provider", "openrouter"))
    await _after_model(callback, state, model)


async def _after_model(event: Message | CallbackQuery, state: FSMContext, model: str) -> None:
    if not model:
        await reply(event, "أرسل معرّفًا صالحًا للنموذج.")
        return
    await state.update_data(model=model)
    await state.set_state(KeyFlow.api_key)
    text = (
        "🔐 أرسل مفتاح API الآن في هذه المحادثة الخاصة.\n"
        "سيتم اختباره ثم تشفيره وحفظه، وسأحذف رسالتك إن أمكن."
    )
    await reply(event, text, keyboards.back_home())


@router.message(KeyFlow.api_key, F.text)
async def receive_key(message: Message, state: FSMContext, deps: Deps) -> None:
    data = await state.get_data()
    provider = data.get("provider", "openrouter")
    model = data.get("model") or default_model(provider)
    base_url = data.get("base_url")
    api_key = message.text.strip()
    with contextlib.suppress(Exception):
        await message.delete()

    if len(api_key) < 8:
        await message.answer("المفتاح يبدو غير صالح، حاول مرة أخرى.")
        return

    key = AiKey(
        telegram_id=message.from_user.id,
        provider=provider,
        model=model,
        base_url=base_url,
        encrypted_key="",
        ok=None,
        last_checked_at=None,
    )
    try:
        configs = build_user_configs(deps.settings, key, api_key)
    except ConfigurationError as exc:
        await message.answer(f"⚠️ {exc.reason}")
        return

    await message.answer("🧪 أختبر المفتاح…")
    ok, reason = await ping_all(configs)
    if not ok:
        await state.set_state(None)
        await message.answer(f"❌ فشل الاختبار: {reason}\nلم يُحفظ المفتاح.")
        return

    try:
        encrypted = deps.vault.encrypt(api_key)
    except (ConfigurationError, AppError) as exc:
        await message.answer(f"⚠️ {exc.reason}")
        return
    await deps.keys.save(
        message.from_user.id,
        provider=provider,
        model=model,
        base_url=base_url,
        encrypted_key=encrypted,
    )
    await state.set_state(None)
    await message.answer(
        f"✅ تم حفظ المفتاح ({PROVIDER_LABELS.get(provider, provider)} / <code>{model}</code>).",
        reply_markup=keyboards.keys_menu(True, provider),
    )


@router.callback_query(F.data == "key:test")
async def key_test(callback: CallbackQuery, deps: Deps) -> None:
    configs = await deps.ai_configs(callback.from_user.id)
    if not configs:
        await callback.answer(texts.NO_AI, show_alert=True)
        return
    await callback.answer("🧪 أختبر…")
    ok, reason = await ping_all(configs)
    await deps.keys.mark(callback.from_user.id, ok)
    await safe_edit(
        callback,
        "✅ المفتاح يعمل بشكل سليم." if ok else f"❌ فشل الاختبار: {reason}",
        keyboards.keys_menu(True),
    )


@router.callback_query(F.data == "key:delete")
async def key_delete(callback: CallbackQuery, deps: Deps) -> None:
    removed = await deps.keys.delete(callback.from_user.id)
    await callback.answer("🗑️ تم الحذف" if removed else "لا يوجد مفتاح")
    await keys_overview(callback, deps)


# Legacy-compatible commands.
@router.message(Command("setkey", "testkey", "deletekey"))
async def legacy_key_commands(
    message: Message, command, state: FSMContext, deps: Deps
) -> None:
    name = (command.command or "").lower()
    if name == "deletekey":
        await deps.keys.delete(message.from_user.id)
        await message.answer("🗑️ تم حذف مفتاحك الشخصي.")
        return
    if name == "testkey":
        configs = await deps.ai_configs(message.from_user.id)
        if not configs:
            await message.answer(texts.NO_AI)
            return
        ok, reason = await ping_all(configs)
        await deps.keys.mark(message.from_user.id, ok)
        await message.answer("✅ يعمل" if ok else f"❌ {reason}")
        return
    await state.set_state(KeyFlow.provider)
    await message.answer("اختر مزود الذكاء الاصطناعي:", reply_markup=keyboards.providers_menu())
