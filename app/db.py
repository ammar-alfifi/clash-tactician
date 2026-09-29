from pathlib import Path

import aiosqlite


class Database:
    def __init__(self, path: Path) -> None:
        self.path = path

    async def initialize(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        async with aiosqlite.connect(self.path) as connection:
            await connection.execute("PRAGMA foreign_keys = ON")
            await connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS users (
                    telegram_id INTEGER PRIMARY KEY,
                    username TEXT,
                    language TEXT NOT NULL DEFAULT 'ar',
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    last_seen_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                );

                CREATE TABLE IF NOT EXISTS support_tickets (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    telegram_id INTEGER NOT NULL REFERENCES users(telegram_id) ON DELETE CASCADE,
                    kind TEXT NOT NULL CHECK (kind IN ('support', 'idea')),
                    body TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'new',
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                );

                CREATE TABLE IF NOT EXISTS linked_players (
                    telegram_id INTEGER PRIMARY KEY REFERENCES users(telegram_id) ON DELETE CASCADE,
                    player_tag TEXT NOT NULL,
                    linked_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                );

                CREATE TABLE IF NOT EXISTS ai_connections (
                    telegram_id INTEGER PRIMARY KEY REFERENCES users(telegram_id) ON DELETE CASCADE,
                    provider TEXT NOT NULL DEFAULT 'openai',
                    model TEXT NOT NULL,
                    base_url TEXT,
                    encrypted_api_key TEXT NOT NULL,
                    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                );

                CREATE TABLE IF NOT EXISTS war_rooms (
                    chat_id INTEGER PRIMARY KEY,
                    clan_tag TEXT NOT NULL,
                    configured_by INTEGER NOT NULL,
                    configured_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                );

                CREATE TABLE IF NOT EXISTS war_reminder_settings (
                    chat_id INTEGER PRIMARY KEY REFERENCES war_rooms(chat_id) ON DELETE CASCADE,
                    enabled INTEGER NOT NULL DEFAULT 0,
                    interval_minutes INTEGER NOT NULL DEFAULT 60,
                    last_sent_at TEXT,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                );
                """
            )
            columns = {
                str(row[1])
                for row in await (await connection.execute("PRAGMA table_info(ai_connections)")).fetchall()
            }
            if "base_url" not in columns:
                await connection.execute("ALTER TABLE ai_connections ADD COLUMN base_url TEXT")
            await connection.commit()

    async def upsert_user(self, telegram_id: int, username: str | None, language: str) -> None:
        async with aiosqlite.connect(self.path) as connection:
            await connection.execute(
                """
                INSERT INTO users (telegram_id, username, language)
                VALUES (?, ?, ?)
                ON CONFLICT(telegram_id) DO UPDATE SET
                    username = excluded.username,
                    language = excluded.language,
                    last_seen_at = CURRENT_TIMESTAMP
                """,
                (telegram_id, username, language),
            )
            await connection.commit()

    async def create_ticket(self, telegram_id: int, kind: str, body: str) -> int:
        async with aiosqlite.connect(self.path) as connection:
            cursor = await connection.execute(
                "INSERT INTO support_tickets (telegram_id, kind, body) VALUES (?, ?, ?)",
                (telegram_id, kind, body),
            )
            await connection.commit()
            return int(cursor.lastrowid)

    async def set_linked_player(self, telegram_id: int, player_tag: str) -> None:
        async with aiosqlite.connect(self.path) as connection:
            await connection.execute(
                """
                INSERT INTO linked_players (telegram_id, player_tag)
                VALUES (?, ?)
                ON CONFLICT(telegram_id) DO UPDATE SET
                    player_tag = excluded.player_tag,
                    linked_at = CURRENT_TIMESTAMP
                """,
                (telegram_id, player_tag),
            )
            await connection.commit()

    async def get_linked_player(self, telegram_id: int) -> str | None:
        async with aiosqlite.connect(self.path) as connection:
            cursor = await connection.execute(
                "SELECT player_tag FROM linked_players WHERE telegram_id = ?", (telegram_id,)
            )
            row = await cursor.fetchone()
            return str(row[0]) if row else None

    async def delete_linked_player(self, telegram_id: int) -> bool:
        async with aiosqlite.connect(self.path) as connection:
            cursor = await connection.execute(
                "DELETE FROM linked_players WHERE telegram_id = ?", (telegram_id,)
            )
            await connection.commit()
            return cursor.rowcount > 0

    async def save_ai_connection(
        self,
        telegram_id: int,
        model: str,
        encrypted_api_key: str,
        provider: str = "openai",
        base_url: str | None = None,
    ) -> None:
        async with aiosqlite.connect(self.path) as connection:
            await connection.execute(
                """
                INSERT INTO ai_connections (telegram_id, provider, model, base_url, encrypted_api_key)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(telegram_id) DO UPDATE SET
                    provider = excluded.provider, model = excluded.model,
                    base_url = excluded.base_url,
                    encrypted_api_key = excluded.encrypted_api_key,
                    updated_at = CURRENT_TIMESTAMP
                """,
                (telegram_id, provider, model, base_url, encrypted_api_key),
            )
            await connection.commit()

    async def get_ai_connection(self, telegram_id: int) -> tuple[str, str, str | None, str] | None:
        async with aiosqlite.connect(self.path) as connection:
            cursor = await connection.execute(
                "SELECT provider, model, base_url, encrypted_api_key FROM ai_connections WHERE telegram_id = ?",
                (telegram_id,),
            )
            row = await cursor.fetchone()
            return (str(row[0]), str(row[1]), str(row[2]) if row[2] else None, str(row[3])) if row else None

    async def delete_ai_connection(self, telegram_id: int) -> bool:
        async with aiosqlite.connect(self.path) as connection:
            cursor = await connection.execute(
                "DELETE FROM ai_connections WHERE telegram_id = ?", (telegram_id,)
            )
            await connection.commit()
            return cursor.rowcount > 0

    async def set_war_room(self, chat_id: int, clan_tag: str, configured_by: int) -> None:
        async with aiosqlite.connect(self.path) as connection:
            await connection.execute(
                """
                INSERT INTO war_rooms (chat_id, clan_tag, configured_by)
                VALUES (?, ?, ?)
                ON CONFLICT(chat_id) DO UPDATE SET
                    clan_tag = excluded.clan_tag,
                    configured_by = excluded.configured_by,
                    configured_at = CURRENT_TIMESTAMP
                """,
                (chat_id, clan_tag, configured_by),
            )
            await connection.commit()

    async def get_war_room(self, chat_id: int) -> str | None:
        async with aiosqlite.connect(self.path) as connection:
            cursor = await connection.execute(
                "SELECT clan_tag FROM war_rooms WHERE chat_id = ?", (chat_id,)
            )
            row = await cursor.fetchone()
            return str(row[0]) if row else None

    async def set_war_reminder(
        self, chat_id: int, enabled: bool, interval_minutes: int | None = None
    ) -> None:
        async with aiosqlite.connect(self.path) as connection:
            await connection.execute("PRAGMA foreign_keys = ON")
            if interval_minutes is None:
                await connection.execute(
                    """
                    INSERT INTO war_reminder_settings (chat_id, enabled)
                    VALUES (?, ?)
                    ON CONFLICT(chat_id) DO UPDATE SET enabled = excluded.enabled
                    """,
                    (chat_id, 1 if enabled else 0),
                )
            else:
                await connection.execute(
                    """
                    INSERT INTO war_reminder_settings (chat_id, enabled, interval_minutes)
                    VALUES (?, ?, ?)
                    ON CONFLICT(chat_id) DO UPDATE SET
                        enabled = excluded.enabled,
                        interval_minutes = excluded.interval_minutes
                    """,
                    (chat_id, 1 if enabled else 0, interval_minutes),
                )
            await connection.commit()

    async def get_war_reminder(
        self, chat_id: int
    ) -> tuple[bool, int, str | None] | None:
        async with aiosqlite.connect(self.path) as connection:
            cursor = await connection.execute(
                """
                SELECT enabled, interval_minutes, last_sent_at
                FROM war_reminder_settings WHERE chat_id = ?
                """,
                (chat_id,),
            )
            row = await cursor.fetchone()
            return (bool(row[0]), int(row[1]), str(row[2]) if row[2] else None) if row else None

    async def list_due_war_reminders(self) -> list[tuple[int, str]]:
        """War rooms whose reminder interval elapsed and that have a linked clan."""
        async with aiosqlite.connect(self.path) as connection:
            cursor = await connection.execute(
                """
                SELECT reminder.chat_id, room.clan_tag
                FROM war_reminder_settings AS reminder
                JOIN war_rooms AS room ON room.chat_id = reminder.chat_id
                WHERE reminder.enabled = 1
                  AND (
                      reminder.last_sent_at IS NULL
                      OR datetime(
                          reminder.last_sent_at,
                          '+' || reminder.interval_minutes || ' minutes'
                      ) <= datetime('now')
                  )
                """
            )
            return [(int(row[0]), str(row[1])) for row in await cursor.fetchall()]

    async def mark_war_reminder_sent(self, chat_id: int) -> None:
        async with aiosqlite.connect(self.path) as connection:
            await connection.execute(
                """
                UPDATE war_reminder_settings
                SET last_sent_at = CURRENT_TIMESTAMP
                WHERE chat_id = ?
                """,
                (chat_id,),
            )
            await connection.commit()
