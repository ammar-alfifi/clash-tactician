"""Free-form AI assistant for Clash of Clans questions."""

from __future__ import annotations

from aiogram import F, Router
from aiogram.filters import Command, CommandObject
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from app.ai.providers import chat_with_fallback
from app.bot import keyboards, texts
from app.bot.deps import Deps
from app.bot.handlers.common import reply, safe_edit
from app.bot.states import AskFlow
from app.core.errors import AiError

router = Router(name="assistant")

SYSTEM = (
    "أنت «مدرب كلاش» الخبير في Clash of Clans. أجب بالعربية بوضوح وإيجاز، "
    "وقدّم خطوات عملية قابلة للتطبيق. إن لم تكن متأكدًا فأوضح ذلك بدل التخمين. "
    "ركّز على استراتيجيات الهجوم، الدفاع، تطوير الأبطال والوحدات، وإدارة القبيلة."
)


async def _ask(event: Message | CallbackQuery, deps: Deps, question: str) -> None:
    configs = await deps.ai_configs(event.from_user.id)
    if not configs:
        await reply(event, texts.NO_AI, keyboards.keys_menu(False))
        return
    target = event.message if isinstance(event, CallbackQuery) else event
    if isinstance(target, Message):
        await target.answer("🤔 أفكر…")
    try:
        answer = await chat_with_fallback(
            configs,
            system=SYSTEM,
            user_text=question,
            temperature=0.6,
            max_tokens=1200,
            timeout=max(
                deps.settings.ai_timeout_seconds, deps.settings.nvidia_timeout_seconds
            ),
        )
    except AiError as exc:
        await reply(event, f"⚠️ {exc.reason}")
        return
    text = answer.strip()[:3800]
    if isinstance(target, Message):
        await target.answer(f"🤖 {text}", reply_markup=keyboards.back_home())
    else:
        await reply(event, f"🤖 {text}", keyboards.back_home())


@router.message(Command("ask"))
async def cmd_ask(message: Message, command: CommandObject, state: FSMContext, deps: Deps) -> None:
    question = (command.args or "").strip()
    if question:
        await _ask(message, deps, question)
        return
    await state.set_state(AskFlow.question)
    await message.answer(texts.ASK_PROMPT, reply_markup=keyboards.back_home())


@router.callback_query(F.data == "nav:ask")
async def nav_ask(callback: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(AskFlow.question)
    await safe_edit(callback, texts.ASK_PROMPT, keyboards.back_home())


@router.message(AskFlow.question, F.text)
async def receive_question(message: Message, state: FSMContext, deps: Deps) -> None:
    await state.set_state(None)
    await _ask(message, deps, message.text.strip()[:1000])
