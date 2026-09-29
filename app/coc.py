import asyncio
import re
import time
from urllib.parse import quote

import aiohttp

TAG_PATTERN = re.compile(r"^[0289PYLQGRJCUV]+$")
API_BASE = "https://api.clashofclans.com/v1"


class CocAPIError(Exception):
    """An expected, safe-to-display Clash of Clans API failure."""

    def __init__(self, user_message: str) -> None:
        super().__init__(user_message)
        self.user_message = user_message


def api_error_message(path: str, status: int) -> str | None:
    if status == 404:
        return "لم يُعثر على البيانات. تحقق من الوسم أو من توفر الحرب."
    if status == 401:
        return "مفتاح CoC API غير صالح أو منتهي؛ أنشئ مفتاحًا فعالًا من لوحة المطورين."
    if status == 403 and path.endswith("/currentwar"):
        return (
            "رفضت واجهة CoC عرض بيانات الحرب؛ السبب المعتاد أن سجل الحرب مضبوط على خاص. "
            "اطلب من قائد القبيلة أو مساعده جعل War Log (سجل الحرب) عامًا من إعدادات القبيلة. "
            "هذا يتيح الوصول إلى سجل الحروب عبر API."
        )
    if status == 403:
        return (
            "رفضت واجهة CoC مفتاح المطور. تحقق من أن المفتاح فعال وأن عنوان IP العام "
            "للجهاز الذي يشغّل البوت ضمن قائمة العناوين المسموحة في لوحة Supercell."
        )
    if status == 429:
        return "وصلنا إلى حد طلبات اللعبة مؤقتًا؛ حاول بعد قليل."
    if status >= 500:
        return "واجهة اللعبة لا تستجيب الآن؛ حاول لاحقًا."
    if status >= 400:
        return "تعذر جلب البيانات. تحقق من الوسم وحاول مجددًا."
    return None


def normalize_tag(value: str) -> str:
    tag = value.strip().upper().removeprefix("#").replace(" ", "")
    if not 3 <= len(tag) <= 15 or not TAG_PATTERN.fullmatch(tag):
        raise ValueError("وسم اللاعب غير صالح. أرسل الوسم كما يظهر داخل اللعبة، مثل #2PYLQGR.")
    return f"#{tag}"


class CocClient:
    def __init__(self, token: str | None, cache_seconds: int = 60) -> None:
        self.token = token
        self.cache_seconds = cache_seconds
        self._session: aiohttp.ClientSession | None = None
        self._cache: dict[str, tuple[float, dict]] = {}
        self._cache_lock = asyncio.Lock()

    async def _get_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession(
                headers={"Authorization": f"Bearer {self.token}"},
                timeout=aiohttp.ClientTimeout(total=12),
            )
        return self._session

    async def close(self) -> None:
        if self._session and not self._session.closed:
            await self._session.close()

    async def _get(self, path: str) -> dict:
        if not self.token:
            raise CocAPIError("خدمة بيانات اللعبة غير مفعّلة بعد؛ يلزم إعداد مفتاح المطور الرسمي.")

        now = time.monotonic()
        async with self._cache_lock:
            cached = self._cache.get(path)
            if cached and cached[0] > now:
                return cached[1]

        session = await self._get_session()
        try:
            async with session.get(f"{API_BASE}{path}") as response:
                error_message = api_error_message(path, response.status)
                if error_message:
                    raise CocAPIError(error_message)
                data = await response.json()
        except TimeoutError as exc:
            raise CocAPIError("انتهت مهلة الاتصال بواجهة اللعبة؛ حاول مجددًا.") from exc
        except aiohttp.ClientError as exc:
            raise CocAPIError("تعذر الاتصال بواجهة اللعبة؛ حاول لاحقًا.") from exc

        async with self._cache_lock:
            self._cache[path] = (time.monotonic() + self.cache_seconds, data)
        return data

    async def player(self, tag: str) -> dict:
        encoded = quote(normalize_tag(tag), safe="")
        return await self._get(f"/players/{encoded}")

    async def clan(self, tag: str) -> dict:
        encoded = quote(normalize_tag(tag), safe="")
        return await self._get(f"/clans/{encoded}")

    async def current_war(self, tag: str) -> dict:
        normalized_tag = normalize_tag(tag)
        clan = await self.clan(normalized_tag)
        if clan.get("isWarLogPublic") is False:
            raise CocAPIError(
                "تحققنا من أن سجل حرب هذه القبيلة مضبوط على خاص. "
                "اطلب من قائد القبيلة أو مساعده جعله عامًا من إعدادات القبيلة."
            )
        encoded = quote(normalized_tag, safe="")
        return await self._get(f"/clans/{encoded}/currentwar")
