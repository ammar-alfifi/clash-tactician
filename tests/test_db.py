import sqlite3

import pytest

from app.db import Database


@pytest.mark.asyncio
async def test_user_upsert_and_ticket_creation(tmp_path):
    database_path = tmp_path / "nested" / "bot.sqlite3"
    database = Database(database_path)
    await database.initialize()

    await database.upsert_user(1234, "player", "ar")
    await database.upsert_user(5678, "other", "ar")
    await database.upsert_user(1234, "updated_player", "en")
    await database.set_linked_player(1234, "#2PYLQGR")
    await database.set_linked_player(5678, "#3CUVJQG")
    ticket_id = await database.create_ticket(1234, "idea", "Add war reminders")

    with sqlite3.connect(database_path) as connection:
        user = connection.execute(
            "SELECT username, language FROM users WHERE telegram_id = 1234"
        ).fetchone()
        ticket = connection.execute(
            "SELECT telegram_id, kind, body, status FROM support_tickets WHERE id = ?",
            (ticket_id,),
        ).fetchone()

    assert user == ("updated_player", "en")
    assert ticket == (1234, "idea", "Add war reminders", "new")
    assert await database.get_linked_player(1234) == "#2PYLQGR"
    assert await database.get_linked_player(5678) == "#3CUVJQG"
    await database.set_war_room(-100123, "#2PYLQGR", 1234)
    assert await database.get_war_room(-100123) == "#2PYLQGR"
    await database.set_war_room(-100123, "#3CUVJQG", 5678)
    assert await database.get_war_room(-100123) == "#3CUVJQG"
    assert await database.get_war_room(-100456) is None
    await database.save_ai_connection(1234, "gpt-4.1-mini", "ciphertext")
    assert await database.get_ai_connection(1234) == (
        "openai",
        "gpt-4.1-mini",
        None,
        "ciphertext",
    )
    await database.save_ai_connection(
        1234, "gemini-2.5-flash", "gemini-cipher", "gemini"
    )
    assert await database.get_ai_connection(1234) == (
        "gemini",
        "gemini-2.5-flash",
        None,
        "gemini-cipher",
    )
    await database.save_ai_connection(
        1234,
        "llama-3.3-70b",
        "custom-cipher",
        "custom",
        "https://llm.example/v1",
    )
    assert await database.get_ai_connection(1234) == (
        "custom",
        "llama-3.3-70b",
        "https://llm.example/v1",
        "custom-cipher",
    )
    assert await database.get_ai_connection(5678) is None
    assert await database.delete_ai_connection(1234)
    assert await database.get_ai_connection(1234) is None
    assert await database.delete_linked_player(1234)
    assert await database.get_linked_player(1234) is None
    assert await database.get_linked_player(5678) == "#3CUVJQG"


@pytest.mark.asyncio
async def test_initialize_migrates_existing_ai_connections_table(tmp_path):
    database_path = tmp_path / "legacy.sqlite3"
    with sqlite3.connect(database_path) as connection:
        connection.execute(
            """
            CREATE TABLE ai_connections (
                telegram_id INTEGER PRIMARY KEY,
                provider TEXT NOT NULL DEFAULT 'openai',
                model TEXT NOT NULL,
                encrypted_api_key TEXT NOT NULL,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        connection.execute(
            "INSERT INTO ai_connections (telegram_id, model, encrypted_api_key) "
            "VALUES (1, 'gpt-4.1-mini', 'cipher')"
        )

    database = Database(database_path)
    await database.initialize()

    assert await database.get_ai_connection(1) == (
        "openai",
        "gpt-4.1-mini",
        None,
        "cipher",
    )


@pytest.mark.asyncio
async def test_war_reminder_settings_and_due_rooms(tmp_path):
    database = Database(tmp_path / "reminders.sqlite3")
    await database.initialize()
    await database.upsert_user(1, "admin", "ar")
    await database.set_war_room(-100123, "#2PYLQGR", 1)

    assert await database.get_war_reminder(-100123) is None
    assert await database.list_due_war_reminders() == []

    # A linked room with reminders disabled is never due.
    await database.set_war_reminder(-100123, False, 30)
    assert await database.get_war_reminder(-100123) == (False, 30, None)
    assert await database.list_due_war_reminders() == []

    # Enabling without an interval keeps the stored interval and becomes due immediately.
    await database.set_war_reminder(-100123, True)
    assert await database.get_war_reminder(-100123) == (True, 30, None)
    assert await database.list_due_war_reminders() == [(-100123, "#2PYLQGR")]

    # After marking sent within the interval the room is no longer due.
    await database.mark_war_reminder_sent(-100123)
    enabled, interval, last_sent = await database.get_war_reminder(-100123)
    assert enabled is True
    assert interval == 30
    assert last_sent is not None
    assert await database.list_due_war_reminders() == []

    # A new interval of zero-like small value can make it due again.
    await database.set_war_reminder(-100123, True, 5)
    assert (await database.get_war_reminder(-100123))[1] == 5
    assert await database.list_due_war_reminders() == []

