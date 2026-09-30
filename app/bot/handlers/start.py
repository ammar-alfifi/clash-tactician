"""Start, help, privacy and the main-menu navigation."""

from __future__ import annotations

from aiogram import F, Router
from aiogram.filters import Command, CommandStart
from aiogram.types import CallbackQuery, Message

from app.bot import keyboards, texts
from app.bot.handlers.common import safe_edit

router = Router(name="start")


@router.message(CommandStart())
async def cmd_start(message: Message) -> None:
    await message.answer(texts.WELCOME, reply_markup=keyboards.main_menu())


@router.message(Command("help"))
async def cmd_help(message: Message) -> None:
    await message.answer(texts.HELP, reply_markup=keyboards.back_home())


@router.message(Command("privacy"))
async def cmd_privacy(message: Message) -> None:
    await message.answer(texts.PRIVACY, reply_markup=keyboards.back_home())


@router.callback_query(F.data == "nav:home")
async def nav_home(callback: CallbackQuery) -> None:
    await safe_edit(callback, texts.WELCOME, keyboards.main_menu())


@router.callback_query(F.data == "nav:help")
async def nav_help(callback: CallbackQuery) -> None:
    await safe_edit(callback, texts.HELP, keyboards.back_home())


# Fallback for unrecognized private text: show the menu instead of silence.
@router.message(F.chat.type == "private", F.text)
async def fallback(message: Message) -> None:
    if message.text and message.text.startswith("/"):
        await message.answer(texts.UNKNOWN_COMMAND, reply_markup=keyboards.main_menu())
        return
    await message.answer(texts.WELCOME, reply_markup=keyboards.main_menu())
