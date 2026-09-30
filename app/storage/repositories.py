"""Repository classes: one focused API per table."""

from __future__ import annotations

import json

from app.storage.database import Database
from app.storage.models import (
    Account,
    AiKey,
    ClanRoom,
    Plan,
    Subscription,
    User,
)

RETENTION_SNAPSHOTS = 40


class UserRepo:
    def __init__(self, db: Database) -> None:
        self.db = db

    async def upsert(
        self,
        telegram_id: int,
        *,
        username: str | None = None,
        first_name: str | None = None,
        language: str = "ar",
    ) -> None:
        async with self.db.connect() as connection:
            await connection.execute(
                """
                INSERT INTO ct_users (telegram_id, username, first_name, language)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(telegram_id) DO UPDATE SET
                    username = COALESCE(excluded.username, ct_users.username),
                    first_name = COALESCE(excluded.first_name, ct_users.first_name),
                    last_seen_at = CURRENT_TIMESTAMP
                """,
                (telegram_id, username, first_name, language),
            )
            await connection.commit()

    async def get(self, telegram_id: int) -> User | None:
        async with self.db.connect() as connection:
            cursor = await connection.execute(
                "SELECT * FROM ct_users WHERE telegram_id = ?", (telegram_id,)
            )
            row = await cursor.fetchone()
        return self._to_user(row) if row else None

    async def language(self, telegram_id: int) -> str:
        user = await self.get(telegram_id)
        return user.language if user else "ar"

    async def set_language(self, telegram_id: int, language: str) -> None:
        async with self.db.connect() as connection:
            await connection.execute(
                "UPDATE ct_users SET language = ? WHERE telegram_id = ?",
                (language, telegram_id),
            )
            await connection.commit()

    async def set_notifications(self, telegram_id: int, enabled: bool) -> None:
        async with self.db.connect() as connection:
            await connection.execute(
                "UPDATE ct_users SET notifications = ? WHERE telegram_id = ?",
                (1 if enabled else 0, telegram_id),
            )
            await connection.commit()

    async def delete(self, telegram_id: int) -> None:
        async with self.db.connect() as connection:
            await connection.execute("DELETE FROM ct_users WHERE telegram_id = ?", (telegram_id,))
            await connection.execute(
                "DELETE FROM ct_accounts WHERE telegram_id = ?", (telegram_id,)
            )
            await connection.execute("DELETE FROM ct_ai_keys WHERE telegram_id = ?", (telegram_id,))
            await connection.execute("DELETE FROM ct_plans WHERE telegram_id = ?", (telegram_id,))
            await connection.execute(
                "DELETE FROM ct_subscriptions WHERE chat_id = ?", (telegram_id,)
            )
            await connection.commit()

    async def all_ids(self) -> list[int]:
        async with self.db.connect() as connection:
            cursor = await connection.execute("SELECT telegram_id FROM ct_users")
            return [int(row[0]) for row in await cursor.fetchall()]

    async def count(self) -> int:
        async with self.db.connect() as connection:
            cursor = await connection.execute("SELECT COUNT(*) FROM ct_users")
            row = await cursor.fetchone()
            return int(row[0]) if row else 0

    @staticmethod
    def _to_user(row) -> User:
        return User(
            telegram_id=int(row["telegram_id"]),
            username=row["username"],
            first_name=row["first_name"],
            language=str(row["language"]),
            notifications=bool(row["notifications"]),
            created_at=str(row["created_at"]),
            last_seen_at=str(row["last_seen_at"]),
        )


class AccountRepo:
    def __init__(self, db: Database) -> None:
        self.db = db

    async def add(
        self, telegram_id: int, player_tag: str, *, name: str | None = None, primary: bool = False
    ) -> None:
        async with self.db.connect() as connection:
            if primary:
                await connection.execute(
                    "UPDATE ct_accounts SET is_primary = 0 WHERE telegram_id = ?", (telegram_id,)
                )
            await connection.execute(
                """
                INSERT INTO ct_accounts (telegram_id, player_tag, name, is_primary)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(telegram_id, player_tag) DO UPDATE SET
                    name = COALESCE(excluded.name, ct_accounts.name),
                    is_primary = CASE
                        WHEN excluded.is_primary = 1 THEN 1
                        ELSE ct_accounts.is_primary
                    END
                """,
                (telegram_id, player_tag, name, 1 if primary else 0),
            )
            await connection.commit()

    async def set_name(self, telegram_id: int, player_tag: str, name: str) -> None:
        async with self.db.connect() as connection:
            await connection.execute(
                "UPDATE ct_accounts SET name = ? WHERE telegram_id = ? AND player_tag = ?",
                (name, telegram_id, player_tag),
            )
            await connection.commit()

    async def list(self, telegram_id: int) -> list[Account]:
        async with self.db.connect() as connection:
            cursor = await connection.execute(
                """
                SELECT * FROM ct_accounts WHERE telegram_id = ?
                ORDER BY is_primary DESC, linked_at ASC
                """,
                (telegram_id,),
            )
            rows = await cursor.fetchall()
        return [self._to_account(row) for row in rows]

    async def get(self, telegram_id: int, player_tag: str) -> Account | None:
        async with self.db.connect() as connection:
            cursor = await connection.execute(
                "SELECT * FROM ct_accounts WHERE telegram_id = ? AND player_tag = ?",
                (telegram_id, player_tag),
            )
            row = await cursor.fetchone()
        return self._to_account(row) if row else None

    async def primary(self, telegram_id: int) -> Account | None:
        accounts = await self.list(telegram_id)
        return accounts[0] if accounts else None

    async def set_primary(self, telegram_id: int, player_tag: str) -> bool:
        async with self.db.connect() as connection:
            await connection.execute(
                "UPDATE ct_accounts SET is_primary = 0 WHERE telegram_id = ?", (telegram_id,)
            )
            cursor = await connection.execute(
                "UPDATE ct_accounts SET is_primary = 1 WHERE telegram_id = ? AND player_tag = ?",
                (telegram_id, player_tag),
            )
            await connection.commit()
            return cursor.rowcount > 0

    async def remove(self, telegram_id: int, player_tag: str) -> bool:
        async with self.db.connect() as connection:
            cursor = await connection.execute(
                "DELETE FROM ct_accounts WHERE telegram_id = ? AND player_tag = ?",
                (telegram_id, player_tag),
            )
            await connection.commit()
            return cursor.rowcount > 0

    async def distinct_tags(self) -> list[str]:
        async with self.db.connect() as connection:
            cursor = await connection.execute("SELECT DISTINCT player_tag FROM ct_accounts")
            return [str(row[0]) for row in await cursor.fetchall()]

    async def all(self) -> list[Account]:
        async with self.db.connect() as connection:
            cursor = await connection.execute("SELECT * FROM ct_accounts")
            rows = await cursor.fetchall()
        return [self._to_account(row) for row in rows]

    @staticmethod
    def _to_account(row) -> Account:
        return Account(
            id=int(row["id"]),
            telegram_id=int(row["telegram_id"]),
            player_tag=str(row["player_tag"]),
            name=row["name"],
            is_primary=bool(row["is_primary"]),
            linked_at=str(row["linked_at"]),
        )


class AiKeyRepo:
    def __init__(self, db: Database) -> None:
        self.db = db

    async def save(
        self,
        telegram_id: int,
        *,
        provider: str,
        model: str,
        base_url: str | None,
        encrypted_key: str,
    ) -> None:
        async with self.db.connect() as connection:
            await connection.execute(
                """
                INSERT INTO ct_ai_keys
                    (telegram_id, provider, model, base_url, encrypted_key, ok, last_checked_at)
                VALUES (?, ?, ?, ?, ?, 1, CURRENT_TIMESTAMP)
                ON CONFLICT(telegram_id) DO UPDATE SET
                    provider = excluded.provider,
                    model = excluded.model,
                    base_url = excluded.base_url,
                    encrypted_key = excluded.encrypted_key,
                    ok = 1,
                    last_checked_at = CURRENT_TIMESTAMP,
                    updated_at = CURRENT_TIMESTAMP
                """,
                (telegram_id, provider, model, base_url, encrypted_key),
            )
            await connection.commit()

    async def get(self, telegram_id: int) -> AiKey | None:
        async with self.db.connect() as connection:
            cursor = await connection.execute(
                "SELECT * FROM ct_ai_keys WHERE telegram_id = ?", (telegram_id,)
            )
            row = await cursor.fetchone()
        if not row:
            return None
        return AiKey(
            telegram_id=int(row["telegram_id"]),
            provider=str(row["provider"]),
            model=str(row["model"]),
            base_url=row["base_url"],
            encrypted_key=str(row["encrypted_key"]),
            ok=bool(row["ok"]) if row["ok"] is not None else None,
            last_checked_at=row["last_checked_at"],
        )

    async def delete(self, telegram_id: int) -> bool:
        async with self.db.connect() as connection:
            cursor = await connection.execute(
                "DELETE FROM ct_ai_keys WHERE telegram_id = ?", (telegram_id,)
            )
            await connection.commit()
            return cursor.rowcount > 0

    async def mark(self, telegram_id: int, ok: bool) -> None:
        async with self.db.connect() as connection:
            await connection.execute(
                "UPDATE ct_ai_keys SET ok = ?, "
                "last_checked_at = CURRENT_TIMESTAMP WHERE telegram_id = ?",
                (1 if ok else 0, telegram_id),
            )
            await connection.commit()


class ClanRoomRepo:
    def __init__(self, db: Database) -> None:
        self.db = db

    async def upsert(self, chat_id: int, clan_tag: str, configured_by: int) -> None:
        async with self.db.connect() as connection:
            await connection.execute(
                """
                INSERT INTO ct_clan_rooms (chat_id, clan_tag, configured_by)
                VALUES (?, ?, ?)
                ON CONFLICT(chat_id) DO UPDATE SET
                    clan_tag = excluded.clan_tag,
                    configured_by = excluded.configured_by
                """,
                (chat_id, clan_tag, configured_by),
            )
            await connection.commit()

    async def get(self, chat_id: int) -> ClanRoom | None:
        async with self.db.connect() as connection:
            cursor = await connection.execute(
                "SELECT * FROM ct_clan_rooms WHERE chat_id = ?", (chat_id,)
            )
            row = await cursor.fetchone()
        return self._to_room(row) if row else None

    async def delete(self, chat_id: int) -> bool:
        async with self.db.connect() as connection:
            cursor = await connection.execute(
                "DELETE FROM ct_clan_rooms WHERE chat_id = ?", (chat_id,)
            )
            await connection.commit()
            return cursor.rowcount > 0

    async def set_reminders(
        self, chat_id: int, enabled: bool, interval_minutes: int | None = None
    ) -> None:
        async with self.db.connect() as connection:
            if interval_minutes is None:
                await connection.execute(
                    "UPDATE ct_clan_rooms SET reminders = ? WHERE chat_id = ?",
                    (1 if enabled else 0, chat_id),
                )
            else:
                await connection.execute(
                    "UPDATE ct_clan_rooms SET reminders = ?, "
                    "interval_minutes = ? WHERE chat_id = ?",
                    (1 if enabled else 0, interval_minutes, chat_id),
                )
            await connection.commit()

    async def mark_reminded(self, chat_id: int) -> None:
        async with self.db.connect() as connection:
            await connection.execute(
                "UPDATE ct_clan_rooms SET last_reminder_at = CURRENT_TIMESTAMP WHERE chat_id = ?",
                (chat_id,),
            )
            await connection.commit()

    async def due_reminders(self) -> list[ClanRoom]:
        async with self.db.connect() as connection:
            cursor = await connection.execute(
                """
                SELECT * FROM ct_clan_rooms
                WHERE reminders = 1
                  AND (
                      last_reminder_at IS NULL
                      OR datetime(last_reminder_at, '+' || interval_minutes || ' minutes')
                         <= datetime('now')
                  )
                """
            )
            rows = await cursor.fetchall()
        return [self._to_room(row) for row in rows]

    @staticmethod
    def _to_room(row) -> ClanRoom:
        return ClanRoom(
            chat_id=int(row["chat_id"]),
            clan_tag=str(row["clan_tag"]),
            configured_by=row["configured_by"],
            reminders=bool(row["reminders"]),
            interval_minutes=int(row["interval_minutes"]),
            last_reminder_at=row["last_reminder_at"],
        )


class SubscriptionRepo:
    def __init__(self, db: Database) -> None:
        self.db = db

    async def add(self, chat_id: int, kind: str, target_tag: str, created_by: int | None) -> None:
        async with self.db.connect() as connection:
            await connection.execute(
                """
                INSERT OR IGNORE INTO ct_subscriptions (chat_id, kind, target_tag, created_by)
                VALUES (?, ?, ?, ?)
                """,
                (chat_id, kind, target_tag, created_by),
            )
            await connection.commit()

    async def remove(self, chat_id: int, kind: str, target_tag: str) -> bool:
        async with self.db.connect() as connection:
            cursor = await connection.execute(
                "DELETE FROM ct_subscriptions WHERE chat_id = ? AND kind = ? AND target_tag = ?",
                (chat_id, kind, target_tag),
            )
            await connection.commit()
            return cursor.rowcount > 0

    async def remove_all(self, chat_id: int) -> None:
        async with self.db.connect() as connection:
            await connection.execute("DELETE FROM ct_subscriptions WHERE chat_id = ?", (chat_id,))
            await connection.commit()

    async def list_for_chat(self, chat_id: int) -> list[Subscription]:
        async with self.db.connect() as connection:
            cursor = await connection.execute(
                "SELECT * FROM ct_subscriptions WHERE chat_id = ? ORDER BY kind, target_tag",
                (chat_id,),
            )
            rows = await cursor.fetchall()
        return [self._to_sub(row) for row in rows]

    async def by_kind(self, kind: str) -> list[Subscription]:
        async with self.db.connect() as connection:
            cursor = await connection.execute(
                "SELECT * FROM ct_subscriptions WHERE kind = ?", (kind,)
            )
            rows = await cursor.fetchall()
        return [self._to_sub(row) for row in rows]

    @staticmethod
    def _to_sub(row) -> Subscription:
        return Subscription(
            id=int(row["id"]),
            chat_id=int(row["chat_id"]),
            kind=str(row["kind"]),
            target_tag=str(row["target_tag"]),
            created_by=row["created_by"],
        )


class SnapshotRepo:
    def __init__(self, db: Database) -> None:
        self.db = db

    async def add(self, kind: str, target_tag: str, payload: dict) -> None:
        async with self.db.connect() as connection:
            await connection.execute(
                "INSERT INTO ct_snapshots (kind, target_tag, payload) VALUES (?, ?, ?)",
                (kind, target_tag, json.dumps(payload, ensure_ascii=False)),
            )
            await connection.execute(
                """
                DELETE FROM ct_snapshots
                WHERE kind = ? AND target_tag = ? AND id NOT IN (
                    SELECT id FROM ct_snapshots
                    WHERE kind = ? AND target_tag = ?
                    ORDER BY id DESC LIMIT ?
                )
                """,
                (kind, target_tag, kind, target_tag, RETENTION_SNAPSHOTS),
            )
            await connection.commit()

    async def latest(self, kind: str, target_tag: str, *, skip: int = 0) -> tuple[str, dict] | None:
        async with self.db.connect() as connection:
            cursor = await connection.execute(
                """
                SELECT payload, created_at FROM ct_snapshots
                WHERE kind = ? AND target_tag = ?
                ORDER BY id DESC LIMIT 1 OFFSET ?
                """,
                (kind, target_tag, skip),
            )
            row = await cursor.fetchone()
        if not row:
            return None
        try:
            payload = json.loads(row["payload"])
        except json.JSONDecodeError:
            return None
        return str(row["created_at"]), payload


class PlanRepo:
    def __init__(self, db: Database) -> None:
        self.db = db

    async def add(
        self, telegram_id: int, *, title: str | None, goal: str | None, data: dict
    ) -> int:
        async with self.db.connect() as connection:
            cursor = await connection.execute(
                "INSERT INTO ct_plans (telegram_id, title, goal, data) VALUES (?, ?, ?, ?)",
                (telegram_id, title, goal, json.dumps(data, ensure_ascii=False)),
            )
            await connection.commit()
            return int(cursor.lastrowid or 0)

    async def list(self, telegram_id: int, limit: int = 10) -> list[Plan]:
        async with self.db.connect() as connection:
            cursor = await connection.execute(
                "SELECT * FROM ct_plans WHERE telegram_id = ? ORDER BY id DESC LIMIT ?",
                (telegram_id, limit),
            )
            rows = await cursor.fetchall()
        return [self._to_plan(row) for row in rows]

    async def get(self, plan_id: int, telegram_id: int) -> Plan | None:
        async with self.db.connect() as connection:
            cursor = await connection.execute(
                "SELECT * FROM ct_plans WHERE id = ? AND telegram_id = ?", (plan_id, telegram_id)
            )
            row = await cursor.fetchone()
        return self._to_plan(row) if row else None

    async def delete(self, plan_id: int, telegram_id: int) -> bool:
        async with self.db.connect() as connection:
            cursor = await connection.execute(
                "DELETE FROM ct_plans WHERE id = ? AND telegram_id = ?", (plan_id, telegram_id)
            )
            await connection.commit()
            return cursor.rowcount > 0

    @staticmethod
    def _to_plan(row) -> Plan:
        return Plan(
            id=int(row["id"]),
            telegram_id=int(row["telegram_id"]),
            title=row["title"],
            goal=row["goal"],
            data=str(row["data"]),
            created_at=str(row["created_at"]),
        )


class TicketRepo:
    def __init__(self, db: Database) -> None:
        self.db = db

    async def add(self, telegram_id: int, kind: str, body: str) -> int:
        async with self.db.connect() as connection:
            cursor = await connection.execute(
                "INSERT INTO ct_tickets (telegram_id, kind, body) VALUES (?, ?, ?)",
                (telegram_id, kind, body),
            )
            await connection.commit()
            return int(cursor.lastrowid or 0)

    async def count(self) -> int:
        async with self.db.connect() as connection:
            cursor = await connection.execute("SELECT COUNT(*) FROM ct_tickets")
            row = await cursor.fetchone()
            return int(row[0]) if row else 0


class WarStateRepo:
    def __init__(self, db: Database) -> None:
        self.db = db

    async def get(self, target_tag: str) -> tuple[str | None, dict | None] | None:
        async with self.db.connect() as connection:
            cursor = await connection.execute(
                "SELECT fingerprint, payload FROM ct_war_state WHERE target_tag = ?", (target_tag,)
            )
            row = await cursor.fetchone()
        if not row:
            return None
        payload = None
        if row["payload"]:
            try:
                payload = json.loads(row["payload"])
            except json.JSONDecodeError:
                payload = None
        return row["fingerprint"], payload

    async def set(self, target_tag: str, fingerprint: str, payload: dict) -> None:
        async with self.db.connect() as connection:
            await connection.execute(
                """
                INSERT INTO ct_war_state (target_tag, fingerprint, payload)
                VALUES (?, ?, ?)
                ON CONFLICT(target_tag) DO UPDATE SET
                    fingerprint = excluded.fingerprint,
                    payload = excluded.payload,
                    updated_at = CURRENT_TIMESTAMP
                """,
                (target_tag, fingerprint, json.dumps(payload, ensure_ascii=False)),
            )
            await connection.commit()
