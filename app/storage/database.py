"""SQLite storage: connection management, schema and legacy data import."""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

import aiosqlite

logger = logging.getLogger(__name__)

SCHEMA = """
CREATE TABLE IF NOT EXISTS ct_users (
    telegram_id   INTEGER PRIMARY KEY,
    username      TEXT,
    first_name    TEXT,
    language      TEXT NOT NULL DEFAULT 'ar',
    notifications INTEGER NOT NULL DEFAULT 1,
    created_at    TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    last_seen_at  TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS ct_accounts (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    telegram_id INTEGER NOT NULL,
    player_tag TEXT NOT NULL,
    name       TEXT,
    is_primary INTEGER NOT NULL DEFAULT 0,
    linked_at  TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(telegram_id, player_tag)
);

CREATE TABLE IF NOT EXISTS ct_ai_keys (
    telegram_id     INTEGER PRIMARY KEY,
    provider        TEXT NOT NULL,
    model           TEXT NOT NULL,
    base_url        TEXT,
    encrypted_key   TEXT NOT NULL,
    ok              INTEGER,
    last_checked_at TEXT,
    updated_at      TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS ct_clan_rooms (
    chat_id          INTEGER PRIMARY KEY,
    clan_tag         TEXT NOT NULL,
    configured_by    INTEGER,
    reminders        INTEGER NOT NULL DEFAULT 0,
    interval_minutes INTEGER NOT NULL DEFAULT 60,
    last_reminder_at TEXT,
    created_at       TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS ct_subscriptions (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    chat_id    INTEGER NOT NULL,
    kind       TEXT NOT NULL,
    target_tag TEXT NOT NULL,
    created_by INTEGER,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(chat_id, kind, target_tag)
);

CREATE TABLE IF NOT EXISTS ct_snapshots (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    kind       TEXT NOT NULL,
    target_tag TEXT NOT NULL,
    payload    TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_ct_snapshots_target
    ON ct_snapshots (kind, target_tag, created_at DESC);

CREATE TABLE IF NOT EXISTS ct_plans (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    telegram_id INTEGER NOT NULL,
    title       TEXT,
    goal        TEXT,
    data        TEXT NOT NULL,
    created_at  TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS ct_tickets (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    telegram_id INTEGER NOT NULL,
    kind        TEXT NOT NULL,
    body        TEXT NOT NULL,
    status      TEXT NOT NULL DEFAULT 'new',
    created_at  TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS ct_war_state (
    target_tag  TEXT PRIMARY KEY,
    fingerprint TEXT,
    payload     TEXT,
    updated_at  TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
"""

LEGACY_TABLES = ("users", "linked_players", "ai_connections", "support_tickets", "war_rooms")


class Database:
    """Thin async wrapper around aiosqlite with a shared schema."""

    def __init__(self, path: Path) -> None:
        self.path = Path(path)

    @asynccontextmanager
    async def connect(self) -> AsyncIterator[aiosqlite.Connection]:
        async with aiosqlite.connect(self.path) as connection:
            connection.row_factory = aiosqlite.Row
            await connection.execute("PRAGMA foreign_keys = ON")
            await connection.execute("PRAGMA journal_mode = WAL")
            yield connection

    async def initialize(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        async with self.connect() as connection:
            await connection.executescript(SCHEMA)
            await connection.commit()
            await self._import_legacy(connection)

    # -- legacy import -----------------------------------------------------
    async def _existing_tables(self, connection: aiosqlite.Connection) -> set[str]:
        cursor = await connection.execute("SELECT name FROM sqlite_master WHERE type='table'")
        return {str(row[0]) for row in await cursor.fetchall()}

    async def _import_legacy(self, connection: aiosqlite.Connection) -> None:
        """Best-effort one-time import from the v1 schema, if present."""
        tables = await self._existing_tables(connection)
        if "users" not in tables and "linked_players" not in tables:
            return
        try:
            if "users" in tables:
                await connection.execute(
                    """
                    INSERT OR IGNORE INTO ct_users (telegram_id, username, language)
                    SELECT telegram_id, username, COALESCE(language, 'ar') FROM users
                    """
                )
            if "linked_players" in tables:
                await connection.execute(
                    """
                    INSERT OR IGNORE INTO ct_accounts (telegram_id, player_tag, is_primary)
                    SELECT telegram_id, player_tag, 1 FROM linked_players
                    """
                )
            if "ai_connections" in tables:
                columns = {
                    str(row[1])
                    for row in await (
                        await connection.execute("PRAGMA table_info(ai_connections)")
                    ).fetchall()
                }
                base_expr = "COALESCE(base_url, '')" if "base_url" in columns else "NULL"
                await connection.execute(
                    f"""
                    INSERT OR IGNORE INTO ct_ai_keys
                        (telegram_id, provider, model, base_url, encrypted_key)
                    SELECT telegram_id, COALESCE(provider, 'openai'), model,
                           {base_expr}, encrypted_api_key
                    FROM ai_connections
                    """
                )
            await connection.commit()
            logger.info("Imported legacy v1 data (users=%s)", "users" in tables)
        except aiosqlite.Error:
            logger.warning("Legacy import skipped", exc_info=True)

    async def table_counts(self, tables: tuple[str, ...]) -> dict[str, int]:
        counts: dict[str, int] = {}
        async with self.connect() as connection:
            for table in tables:
                try:
                    cursor = await connection.execute(f"SELECT COUNT(*) FROM {table}")
                    row = await cursor.fetchone()
                    counts[table] = int(row[0]) if row else 0
                except aiosqlite.Error:
                    counts[table] = -1
        return counts
