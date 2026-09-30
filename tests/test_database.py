"""Database schema and repository behaviour."""

from __future__ import annotations

import sqlite3

from app.storage.database import Database


async def test_initialize_creates_tables(database: Database):
    async with database.connect() as connection:
        cursor = await connection.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        )
        names = {row[0] for row in await cursor.fetchall()}
    assert {"ct_users", "ct_accounts", "ct_ai_keys", "ct_plans"} <= names


async def test_user_and_account_repo(database: Database):
    from app.storage.repositories import AccountRepo, UserRepo

    users, accounts = UserRepo(database), AccountRepo(database)
    await users.upsert(7, username="ammar", first_name="Ammar")
    assert (await users.get(7)).username == "ammar"
    await users.set_language(7, "en")
    assert await users.language(7) == "en"

    await accounts.add(7, "#AAA", name="First", primary=True)
    await accounts.add(7, "#BBB", name="Second")
    assert (await accounts.primary(7)).player_tag == "#AAA"
    assert await accounts.set_primary(7, "#BBB")
    assert (await accounts.primary(7)).player_tag == "#BBB"
    assert [a.player_tag for a in await accounts.list(7)] == ["#BBB", "#AAA"]
    assert await accounts.remove(7, "#AAA")
    assert len(await accounts.list(7)) == 1


async def test_ai_key_repo_roundtrip(database: Database):
    from app.storage.repositories import AiKeyRepo

    repo = AiKeyRepo(database)
    await repo.save(
        1, provider="openrouter", model="m", base_url=None, encrypted_key="cipher"
    )
    key = await repo.get(1)
    assert key.provider == "openrouter" and key.encrypted_key == "cipher"
    await repo.mark(1, False)
    assert (await repo.get(1)).ok is False
    assert await repo.delete(1)
    assert await repo.get(1) is None


async def test_snapshot_retention(database: Database):
    from app.storage.repositories import SnapshotRepo

    repo = SnapshotRepo(database)
    for index in range(45):
        await repo.add("player", "#AAA", {"trophies": index})
    latest = await repo.latest("player", "#AAA")
    assert latest[1]["trophies"] == 44
    async with database.connect() as connection:
        cursor = await connection.execute(
            "SELECT COUNT(*) FROM ct_snapshots WHERE kind='player'"
        )
        count = (await cursor.fetchone())[0]
    assert count <= 40


async def test_clan_room_reminders(database: Database):
    from app.storage.repositories import ClanRoomRepo

    repo = ClanRoomRepo(database)
    await repo.upsert(-100, "#CLAN", 5)
    await repo.set_reminders(-100, True, 5)
    due = await repo.due_reminders()
    assert len(due) == 1 and due[0].interval_minutes == 5
    await repo.mark_reminded(-100)
    assert await repo.due_reminders() == []


async def test_subscription_repo(database: Database):
    from app.storage.repositories import SubscriptionRepo

    repo = SubscriptionRepo(database)
    await repo.add(1, "war", "#CLAN", 1)
    await repo.add(1, "war", "#CLAN", 1)  # idempotent
    assert len(await repo.by_kind("war")) == 1
    assert await repo.remove(1, "war", "#CLAN")


async def test_plan_and_ticket_repos(database: Database):
    from app.storage.repositories import PlanRepo, TicketRepo

    plans = PlanRepo(database)
    plan_id = await plans.add(9, title="T", goal="three_stars", data={"a": 1})
    assert (await plans.get(plan_id, 9)).title == "T"
    assert await plans.delete(plan_id, 9)
    assert await plans.get(plan_id, 9) is None

    tickets = TicketRepo(database)
    await tickets.add(9, "bug", "broken")
    assert await tickets.count() == 1


async def test_legacy_import(tmp_path):
    """A v1 database should be imported once, without crashing."""
    path = tmp_path / "legacy.sqlite3"
    connection = sqlite3.connect(path)
    connection.executescript(
        """
        CREATE TABLE users (telegram_id INTEGER PRIMARY KEY, username TEXT,
            language TEXT, created_at TEXT, last_seen_at TEXT);
        CREATE TABLE linked_players (telegram_id INTEGER PRIMARY KEY, player_tag TEXT,
            linked_at TEXT);
        CREATE TABLE ai_connections (telegram_id INTEGER PRIMARY KEY, provider TEXT,
            model TEXT, base_url TEXT, encrypted_api_key TEXT,
            updated_at TEXT);
        INSERT INTO users VALUES (42, 'old', 'ar', '2020', '2020');
        INSERT INTO linked_players VALUES (42, '#OLD', '2020');
        INSERT INTO ai_connections VALUES (42, 'openai', 'gpt', NULL, 'cipher', '2020');
        """
    )
    connection.commit()
    connection.close()

    database = Database(path)
    await database.initialize()
    from app.storage.repositories import AccountRepo, AiKeyRepo, UserRepo

    user = await UserRepo(database).get(42)
    assert user is not None and user.username == "old"
    assert (await AccountRepo(database).primary(42)).player_tag == "#OLD"
    assert (await AiKeyRepo(database).get(42)).encrypted_key == "cipher"
