"""Async Clash of Clans API client with caching and typed errors."""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Any
from urllib.parse import quote

import aiohttp

from app.core.errors import CocAuthError, CocDisabled, CocNotFound, CocUnavailable

logger = logging.getLogger(__name__)


class _TTLCache:
    def __init__(self, ttl_seconds: int) -> None:
        self.ttl = ttl_seconds
        self._store: dict[str, tuple[float, Any]] = {}
        self._lock = asyncio.Lock()

    async def get(self, key: str) -> Any | None:
        entry = self._store.get(key)
        if not entry:
            return None
        expiry, value = entry
        if expiry < time.monotonic():
            self._store.pop(key, None)
            return None
        return value

    async def set(self, key: str, value: Any) -> None:
        async with self._lock:
            self._store[key] = (time.monotonic() + self.ttl, value)

    async def clear(self) -> None:
        async with self._lock:
            self._store.clear()


class CocClient:
    def __init__(
        self,
        token: str | None,
        *,
        base_url: str = "https://api.clashofclans.com/v1",
        timeout_seconds: int = 20,
        cache_seconds: int = 300,
    ) -> None:
        self.token = token
        self.base_url = base_url.rstrip("/")
        self.timeout = aiohttp.ClientTimeout(total=timeout_seconds)
        self.cache = _TTLCache(cache_seconds)
        self._session: aiohttp.ClientSession | None = None
        self._semaphore = asyncio.Semaphore(5)

    @property
    def enabled(self) -> bool:
        return bool(self.token)

    async def session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession(timeout=self.timeout)
        return self._session

    async def close(self) -> None:
        if self._session and not self._session.closed:
            await self._session.close()

    async def request(
        self,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        use_cache: bool = True,
    ) -> dict[str, Any]:
        if not self.token:
            raise CocDisabled("Clash of Clans API token is not configured.")

        cache_key = f"{path}?{sorted((params or {}).items())}"
        if use_cache:
            cached = await self.cache.get(cache_key)
            if cached is not None:
                return cached

        url = f"{self.base_url}/{path.lstrip('/')}"
        headers = {"Authorization": f"Bearer {self.token}", "Accept": "application/json"}
        try:
            async with self._semaphore:
                session = await self.session()
                async with session.get(url, headers=headers, params=params) as response:
                    if response.status == 200:
                        data = await response.json(content_type=None)
                        if use_cache:
                            await self.cache.set(cache_key, data)
                        return data
                    body = (await response.text())[:200]
                    self._raise_for_status(response.status, path, body)
        except TimeoutError as exc:
            raise CocUnavailable("انتهت مهلة الاتصال بواجهة اللعبة.") from exc
        except aiohttp.ClientError as exc:
            raise CocUnavailable("تعذّر الوصول إلى واجهة اللعبة.") from exc
        raise CocUnavailable("استجابة غير متوقعة من واجهة اللعبة.")

    @staticmethod
    def _raise_for_status(status: int, path: str, body: str) -> None:
        if status == 403:
            raise CocAuthError(
                "مفتاح واجهة اللعبة غير صالح أو غير مسموح لهذا العنوان (IP)."
            )
        if status == 404:
            raise CocNotFound("لم يُعثر على العنصر المطلوب في واجهة اللعبة.")
        if status == 429:
            raise CocUnavailable("الطلبات كثيرة جدًا على واجهة اللعبة، جرّب لاحقًا.")
        if status >= 500:
            raise CocUnavailable("واجهة اللعبة غير متاحة حاليًا.")
        raise CocUnavailable(f"خطأ من واجهة اللعبة ({status}).")

    # -- endpoints ---------------------------------------------------------
    async def player(self, tag: str) -> dict[str, Any]:
        return await self.request(f"players/{quote(tag)}")

    async def clan(self, tag: str) -> dict[str, Any]:
        return await self.request(f"clans/{quote(tag)}")

    async def current_war(self, tag: str) -> dict[str, Any]:
        # Wars change quickly; cache briefly.
        return await self.request(f"clans/{quote(tag)}/currentwar", use_cache=True)

    async def league_group(self, tag: str) -> dict[str, Any]:
        return await self.request(f"clans/{quote(tag)}/currentwar/leaguegroup")

    async def war_log(self, tag: str, limit: int = 10) -> dict[str, Any]:
        return await self.request(f"clans/{quote(tag)}/warlog", params={"limit": limit})

    async def capital_raid_seasons(self, tag: str, limit: int = 1) -> dict[str, Any]:
        return await self.request(
            f"clans/{quote(tag)}/capitalraidseasons", params={"limit": limit}
        )

    async def verify(self) -> tuple[bool, int | None, str]:
        """Lightweight token check used by the diagnostics endpoint."""
        try:
            await self.request("locations", params={"limit": 1})
        except CocAuthError as exc:
            return False, 403, exc.reason
        except CocUnavailable as exc:
            return False, None, exc.reason
        except CocDisabled as exc:
            return False, None, exc.reason
        return True, 200, "ok"

    async def invalidate(self) -> None:
        await self.cache.clear()
