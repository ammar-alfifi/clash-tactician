from unittest.mock import AsyncMock

import pytest

from app.coc import CocAPIError
from app.reminders import send_due_reminders


def _war_with_pending() -> dict:
    return {
        "state": "inWar",
        "teamSize": 2,
        "clan": {
            "name": "قبيلتنا",
            "members": [
                {"name": "نشيط", "attacks": [{"stars": 3}, {"stars": 2}]},
                {"name": "غائب", "attacks": []},
            ],
        },
    }


@pytest.mark.asyncio
async def test_send_due_reminders_sends_once_and_marks_sent():
    database = AsyncMock()
    database.list_due_war_reminders.return_value = [(1, "#AAA"), (2, "#BBB")]
    coc_client = AsyncMock()
    coc_client.current_war.side_effect = [
        _war_with_pending(),
        {"state": "notInWar"},
    ]
    bot = AsyncMock()

    sent = await send_due_reminders(bot, database, coc_client)

    assert sent == 1
    bot.send_message.assert_awaited_once()
    assert bot.send_message.await_args.args[0] == 1
    database.mark_war_reminder_sent.assert_awaited_once_with(1)


@pytest.mark.asyncio
async def test_send_due_reminders_skips_room_on_api_error():
    database = AsyncMock()
    database.list_due_war_reminders.return_value = [(1, "#AAA")]
    coc_client = AsyncMock()
    coc_client.current_war.side_effect = CocAPIError("لا حرب")
    bot = AsyncMock()

    assert await send_due_reminders(bot, database, coc_client) == 0
    bot.send_message.assert_not_awaited()
    database.mark_war_reminder_sent.assert_not_awaited()


@pytest.mark.asyncio
async def test_send_due_reminders_without_due_rooms_is_noop():
    database = AsyncMock()
    database.list_due_war_reminders.return_value = []
    bot = AsyncMock()

    assert await send_due_reminders(bot, database, AsyncMock()) == 0
    bot.send_message.assert_not_awaited()
