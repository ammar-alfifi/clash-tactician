"""Typed rows returned by repositories."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class User:
    telegram_id: int
    username: str | None
    first_name: str | None
    language: str
    notifications: bool
    created_at: str
    last_seen_at: str


@dataclass(frozen=True)
class Account:
    id: int
    telegram_id: int
    player_tag: str
    name: str | None
    is_primary: bool
    linked_at: str


@dataclass(frozen=True)
class AiKey:
    telegram_id: int
    provider: str
    model: str
    base_url: str | None
    encrypted_key: str
    ok: bool | None
    last_checked_at: str | None


@dataclass(frozen=True)
class ClanRoom:
    chat_id: int
    clan_tag: str
    configured_by: int | None
    reminders: bool
    interval_minutes: int
    last_reminder_at: str | None


@dataclass(frozen=True)
class Subscription:
    id: int
    chat_id: int
    kind: str
    target_tag: str
    created_by: int | None


@dataclass(frozen=True)
class Plan:
    id: int
    telegram_id: int
    title: str | None
    goal: str | None
    data: str
    created_at: str


@dataclass(frozen=True)
class Ticket:
    id: int
    telegram_id: int
    kind: str
    body: str
    status: str
    created_at: str
