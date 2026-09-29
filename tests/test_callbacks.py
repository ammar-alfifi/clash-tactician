from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from aiogram.enums import ChatType
from aiogram.types import Chat, InaccessibleMessage, Message, User

from app import handlers

PLAYER = {"name": "لاعب", "tag": "#AAA", "clan": {"tag": "#CLAN", "name": "قبيلة"}}
CLAN = {"name": "قبيلة", "tag": "#CLAN", "members": [{"name": "عضو", "role": "member"}]}
WAR = {
    "state": "inWar",
    "teamSize": 1,
    "clan": {"name": "قبيلة", "members": []},
    "opponent": {"tag": "#ENEMY", "name": "خصم", "members": [{"tag": "#E1", "name": "هدف"}]},
}


class StubCocClient:
    async def player(self, tag):
        return PLAYER

    async def clan(self, tag):
        return CLAN

    async def current_war(self, tag):
        return WAR


def _callback(data, message, from_user_id=7):
    query = SimpleNamespace()
    query.data = data
    query.from_user = SimpleNamespace(id=from_user_id, username="player")
    query.answer = AsyncMock()
    query.bot = SimpleNamespace(send_message=AsyncMock())
    query.message = message
    return query


def _text_message(chat_type, answers, chat_id=5):
    class RecordingMessage(Message):
        async def answer(self, text=None, **kwargs):
            answers.append(text or "")

    return RecordingMessage(
        message_id=1,
        date=datetime.now(UTC),
        chat=Chat(id=chat_id, type=chat_type),
        from_user=User(id=7, is_bot=False, first_name="U"),
        text="x",
    )


def _inaccessible_message(chat_type=ChatType.PRIVATE, chat_id=5):
    return InaccessibleMessage(
        message_id=1,
        date=0,
        chat=Chat(id=chat_id, type=chat_type),
    )


@pytest.mark.asyncio
async def test_feature_callback_members_works_from_inaccessible_private_message():
    query = _callback("feature:members", _inaccessible_message())
    database = SimpleNamespace(
        get_linked_player=AsyncMock(return_value="#AAA"),
        get_war_room=AsyncMock(return_value=None),
    )

    await handlers.feature_callback(query, database, StubCocClient())

    query.bot.send_message.assert_awaited_once()
    assert query.bot.send_message.await_args.args[0] == 5
    assert "أعضاء" in query.bot.send_message.await_args.args[1]


@pytest.mark.asyncio
async def test_privacy_callback_replies_in_group():
    answers = []
    query = _callback("page:privacy", _text_message(ChatType.SUPERGROUP, answers, chat_id=-100))

    await handlers.privacy_callback(query)

    assert len(answers) == 1
    assert "الخصوصية" in answers[0]


@pytest.mark.asyncio
async def test_feature_callback_group_uses_war_room():
    answers = []
    query = _callback("feature:targets", _text_message(ChatType.SUPERGROUP, answers, chat_id=-100))
    database = SimpleNamespace(
        get_linked_player=AsyncMock(return_value=None),
        get_war_room=AsyncMock(return_value="#CLAN"),
    )

    await handlers.feature_callback(query, database, StubCocClient())

    assert len(answers) == 1
    assert "أهداف" in answers[0]


@pytest.mark.asyncio
async def test_feature_callback_group_without_war_room_explains():
    answers = []
    query = _callback("feature:clan", _text_message(ChatType.SUPERGROUP, answers, chat_id=-100))
    database = SimpleNamespace(
        get_linked_player=AsyncMock(return_value=None),
        get_war_room=AsyncMock(return_value=None),
    )

    await handlers.feature_callback(query, database, StubCocClient())

    assert len(answers) == 1
    assert "/warroom" in answers[0]


@pytest.mark.asyncio
async def test_feature_callback_private_without_linked_player_guides_user():
    answers = []
    query = _callback("feature:player", _text_message(ChatType.PRIVATE, answers))
    database = SimpleNamespace(
        get_linked_player=AsyncMock(return_value=None),
        get_war_room=AsyncMock(return_value=None),
    )

    await handlers.feature_callback(query, database, StubCocClient())

    assert len(answers) == 1
    assert "/link" in answers[0]
