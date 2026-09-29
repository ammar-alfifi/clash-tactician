from unittest.mock import AsyncMock

import pytest

from app.coc import CocAPIError, CocClient, api_error_message, normalize_tag


def test_access_denied_explains_developer_key_and_ip_allowlist():
    message = api_error_message("/players/%232PYLQGR", 403)

    assert message is not None
    assert "عنوان IP" in message
    assert "مفتاح المطور" in message


def test_private_war_log_access_denied_has_endpoint_specific_guidance():
    message = api_error_message("/clans/%232PYLQGR/currentwar", 403)

    assert message is not None
    assert "سجل الحرب مضبوط على خاص" in message
    assert "قائد القبيلة أو مساعده" in message
    assert "عام" in message


def test_success_status_has_no_error_message():
    assert api_error_message("/players/%232PYLQGR", 200) is None


@pytest.mark.parametrize(
    ("value", "expected"),
    [("#2pylqgr", "#2PYLQGR"), ("2PYLQGR", "#2PYLQGR"), (" #2PYL QGR ", "#2PYLQGR")],
)
def test_normalize_player_tag(value, expected):
    assert normalize_tag(value) == expected


@pytest.mark.parametrize("value", ["", "#INVALID", "#2AB", "#2PYLQGRJCUV02890"])
def test_reject_invalid_player_tag(value):
    with pytest.raises(ValueError):
        normalize_tag(value)


@pytest.mark.asyncio
async def test_current_war_uses_clan_public_war_log_setting():
    client = CocClient("test-token")
    client.clan = AsyncMock(return_value={"isWarLogPublic": False})
    client._get = AsyncMock()

    with pytest.raises(CocAPIError, match="سجل حرب هذه القبيلة مضبوط على خاص"):
        await client.current_war("#2PYLQGR")

    client._get.assert_not_awaited()


@pytest.mark.asyncio
async def test_current_war_fetches_endpoint_when_war_log_is_public():
    client = CocClient("test-token")
    client.clan = AsyncMock(return_value={"isWarLogPublic": True})
    client._get = AsyncMock(return_value={"state": "inWar"})

    result = await client.current_war("#2PYLQGR")

    assert result == {"state": "inWar"}
    client._get.assert_awaited_once_with("/clans/%232PYLQGR/currentwar")
