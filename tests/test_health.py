import sqlite3

from aiohttp.test_utils import TestClient, TestServer

from app.health import create_health_app


async def test_health_endpoints() -> None:
    client = TestClient(TestServer(create_health_app()))
    await client.start_server()
    try:
        for path in ("/", "/health"):
            response = await client.get(path)
            assert response.status == 200
            assert await response.json() == {"status": "ok"}
    finally:
        await client.close()


async def test_diag_requires_token(monkeypatch) -> None:
    monkeypatch.setenv("DIAG_TOKEN", "secret-token")
    client = TestClient(TestServer(create_health_app()))
    await client.start_server()
    try:
        assert (await client.get("/diag")).status == 404
        assert (await client.get("/diag?token=wrong")).status == 404

        response = await client.get("/diag?token=secret-token")
        assert response.status == 200
        payload = await response.json()
        assert payload["status"] == "ok"
        assert "egress_ips" in payload
    finally:
        await client.close()


async def test_diag_hidden_without_token(monkeypatch) -> None:
    monkeypatch.delenv("DIAG_TOKEN", raising=False)
    client = TestClient(TestServer(create_health_app()))
    await client.start_server()
    try:
        assert (await client.get("/diag?token=anything")).status == 404
    finally:
        await client.close()


async def test_diag_reports_database_counts(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("DIAG_TOKEN", "secret-token")
    database_path = tmp_path / "bot.sqlite3"
    connection = sqlite3.connect(database_path)
    try:
        connection.execute("CREATE TABLE users (telegram_id INTEGER PRIMARY KEY)")
        connection.execute("INSERT INTO users (telegram_id) VALUES (1)")
        connection.commit()
    finally:
        connection.close()
    monkeypatch.setenv("DATABASE_PATH", str(database_path))

    client = TestClient(TestServer(create_health_app()))
    await client.start_server()
    try:
        response = await client.get("/diag?token=secret-token")
        payload = await response.json()
        assert payload["counts"]["users"] == 1
        assert payload["counts"]["linked_players"] == 0
    finally:
        await client.close()
