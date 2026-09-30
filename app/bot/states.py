"""FSM states."""

from __future__ import annotations

from aiogram.fsm.state import State, StatesGroup


class LinkFlow(StatesGroup):
    waiting_tag = State()
    waiting_account_choice = State()


class PlannerFlow(StatesGroup):
    mode = State()
    goal = State()
    army = State()
    image = State()
    refine = State()


class AskFlow(StatesGroup):
    question = State()


class KeyFlow(StatesGroup):
    provider = State()
    model = State()
    api_key = State()
    custom_base = State()
    custom_model = State()


class SupportFlow(StatesGroup):
    kind = State()
    body = State()


class WatchFlow(StatesGroup):
    target = State()


class BroadcastFlow(StatesGroup):
    body = State()
