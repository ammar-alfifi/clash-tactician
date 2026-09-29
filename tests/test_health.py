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