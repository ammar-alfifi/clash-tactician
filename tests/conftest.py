"""Shared test fixtures."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

os.environ.setdefault("TELEGRAM_BOT_TOKEN", "123456:TESTTOKEN")

from app.config import Settings  # noqa: E402
from app.storage.database import Database  # noqa: E402


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    return Settings(
        bot_token="123456:TESTTOKEN",
        coc_api_token="test-coc-token",
        ai_key_encryption_key=None,
        database_path=tmp_path / "test.sqlite3",
        port=None,
        diag_token="diag-secret",
    )


@pytest.fixture
async def database(tmp_path: Path) -> Database:
    db = Database(tmp_path / "test.sqlite3")
    await db.initialize()
    return db
