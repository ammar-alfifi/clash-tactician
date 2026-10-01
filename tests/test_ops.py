"""Health server, egress and backup helpers."""

from __future__ import annotations

import sqlite3
from pathlib import Path

from aiohttp.test_utils import TestClient, TestServer

from app.config import Settings
from app.ops.backup import DatabaseBackup, _decode_key, _snapshot_sqlite
from app.ops.health import HealthContext, create_health_app
from app.storage.database import Database


async def _client(settings: Settings, database: Database) -> TestClient:
    app = create_health_app(HealthContext(settings, database))
    client = TestClient(TestServer(app))
    await client.start_server()
    return client


async def test_health(settings: Settings, database: Database):
    client = await _client(settings, database)
    try:
        response = await client.get("/health")
        assert response.status == 200
        assert (await response.json())["status"] == "ok"
    finally:
        await client.close()


async def test_diag_requires_token(settings: Settings, database: Database):
    client = await _client(settings, database)
    try:
        assert (await client.get("/diag")).status == 404
        assert (await client.get("/diag?token=wrong")).status == 404
        response = await client.get("/diag?token=diag-secret")
        assert response.status == 200
        payload = await response.json()
        assert payload["status"] == "ok"
        assert "ct_users" in payload["counts"]
    finally:
        await client.close()


def test_self_test_image_is_valid_png():
    from app.ops.health import _self_test_image

    data = _self_test_image()
    assert data[:8] == b"\x89PNG\r\n\x1a\n"
    assert len(data) > 100


def test_snapshot_sqlite(tmp_path: Path):
    source = tmp_path / "source.sqlite3"
    connection = sqlite3.connect(source)
    connection.execute("CREATE TABLE t (id INTEGER)")
    connection.execute("INSERT INTO t VALUES (1)")
    connection.commit()
    connection.close()

    destination = tmp_path / "snapshot.sqlite3"
    _snapshot_sqlite(source, destination)
    check = sqlite3.connect(destination)
    assert check.execute("SELECT COUNT(*) FROM t").fetchone()[0] == 1
    check.close()


def test_backup_disabled_without_remote(tmp_path: Path, monkeypatch):
    monkeypatch.delenv("BACKUP_GIT_REMOTE", raising=False)
    backup = DatabaseBackup(tmp_path / "db.sqlite3", remote="")
    assert not backup.enabled


def test_backup_decodes_base64_key(monkeypatch):
    import base64

    encoded = base64.b64encode(b"my-private-key").decode()
    assert _decode_key(encoded) == "my-private-key"
    assert _decode_key("plain-key") == "plain-key"
    assert _decode_key("") == ""


async def test_restore_skips_when_db_exists(tmp_path: Path):
    path = tmp_path / "db.sqlite3"
    path.write_bytes(b"data")
    backup = DatabaseBackup(path, remote="git@example.com:repo.git")
    assert await backup.restore() is False


def test_parse_tags_accepts_separators():
    from app.ops.clan_probe import parse_tags

    assert parse_tags("#2C0GPVLJ2, 2RCJ2PYJG|P2008JU2") == [
        "#2C0GPVLJ2",
        "#2RCJ2PYJG",
        "#P2008JU2",
    ]


def test_parse_tags_rejects_junk_and_caps():
    from app.ops.clan_probe import parse_tags

    assert parse_tags("../etc/passwd") == []
    assert parse_tags(None) == []
    assert len(parse_tags(",".join(f"#{index}" for index in range(30)))) == 12


async def test_diag_clan_dump(settings: Settings, database: Database):
    class _FakeCoc:
        async def clan(self, tag: str) -> dict:
            return {"tag": tag, "name": "Fake"}

        async def current_war(self, tag: str) -> dict:
            return {"state": "notInWar"}

        async def war_log(self, tag: str, limit: int = 10) -> dict:
            return {"items": []}

    app = create_health_app(HealthContext(settings, database, _FakeCoc()))
    client = TestClient(TestServer(app))
    await client.start_server()
    try:
        response = await client.get("/diag?token=diag-secret&clans=%232C0GPVLJ2")
        assert response.status == 200
        dump = (await response.json())["clans"]
        assert dump["#2C0GPVLJ2"]["clan"]["name"] == "Fake"
        assert dump["#2C0GPVLJ2"]["war"]["state"] == "notInWar"
        assert (await client.get("/diag?clans=%232C0GPVLJ2")).status == 404
    finally:
        await client.close()
