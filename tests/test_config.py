"""Settings parsing from the environment."""

from __future__ import annotations

import pytest

from app.config import Settings


def test_settings_require_token(monkeypatch):
    monkeypatch.delenv("TELEGRAM_BOT_TOKEN", raising=False)
    monkeypatch.setattr("app.config.load_dotenv", lambda *a, **k: None)
    with pytest.raises(ValueError):
        Settings.from_environment()


def test_settings_parse(monkeypatch, tmp_path):
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "abc:def")
    monkeypatch.setenv("ADMIN_IDS", "1,2;3")
    monkeypatch.setenv("SUPPORT_CHAT_ID", "-100123")
    monkeypatch.setenv("DATABASE_PATH", str(tmp_path / "x.sqlite3"))
    monkeypatch.setenv("OPENROUTER_MODEL", "model-a")
    monkeypatch.setenv("OPENROUTER_FALLBACK_MODELS", "model-b,model-a,model-c")
    monkeypatch.setenv("WAR_REMINDER_INTERVAL_MINUTES", "5")
    monkeypatch.setenv("PORT", "9090")
    settings = Settings.from_environment()
    assert settings.bot_token == "abc:def"
    assert settings.admin_ids == (1, 2, 3)
    assert settings.support_chat_id == -100123
    assert settings.openrouter_fallback_models == ("model-b", "model-c")
    assert settings.war_reminder_interval_minutes == 5
    assert settings.port == 9090
    assert settings.is_admin(2)


def test_settings_invalid_support_id(monkeypatch):
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "abc:def")
    monkeypatch.setenv("SUPPORT_CHAT_ID", "not-a-number")
    with pytest.raises(ValueError):
        Settings.from_environment()
