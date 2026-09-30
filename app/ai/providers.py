"""Provider-agnostic chat/vision calls (OpenAI-compatible + Gemini)."""

from __future__ import annotations

import asyncio
import base64
import io
import logging
from dataclasses import dataclass, field
from typing import Any

import aiohttp
from PIL import Image

from app.core.errors import AiAuthError, AiUnavailable, AiUnsupported

logger = logging.getLogger(__name__)

OPENAI_COMPATIBLE = {"openrouter", "openai", "custom", "nvidia"}
PROVIDER_LABELS = {
    "openrouter": "OpenRouter",
    "openai": "OpenAI",
    "gemini": "Google Gemini",
    "nvidia": "NVIDIA NIM",
    "custom": "خدمة مخصصة",
}
KNOWN_BASE_URLS = {
    "openrouter": "https://openrouter.ai/api/v1",
    "openai": "https://api.openai.com/v1",
    "gemini": "https://generativelanguage.googleapis.com/v1beta",
    "nvidia": "https://integrate.api.nvidia.com/v1",
}


@dataclass(frozen=True)
class AiConfig:
    provider: str
    model: str
    api_key: str
    base_url: str
    label: str | None = None
    header_extra: dict[str, str] = field(default_factory=dict)

    @property
    def provider_label(self) -> str:
        return self.label or PROVIDER_LABELS.get(self.provider, self.provider)

    @property
    def supports_vision(self) -> bool:
        return self.provider in OPENAI_COMPATIBLE or self.provider == "gemini"


def _mime_from_bytes(data: bytes) -> str:
    if data[:8] == b"\x89PNG\r\n\x1a\n":
        return "image/png"
    if data[:3] == b"\xff\xd8\xff":
        return "image/jpeg"
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "image/webp"
    return "image/jpeg"


def compress_image(data: bytes, *, max_side: int = 1280, quality: int = 82) -> tuple[bytes, str]:
    """Downscale/re-encode a screenshot to keep vision requests fast.

    Large uploads are the main reason slow vision models time out. Returns
    ``(bytes, mime_type)`` and falls back to the original on any failure.
    """
    try:
        image = Image.open(io.BytesIO(data))
        image.load()
        image = image.convert("RGB")
        width, height = image.size
        scale = min(1.0, max_side / max(width, height))
        if scale < 1.0:
            new_size = (max(1, int(width * scale)), max(1, int(height * scale)))
            image = image.resize(new_size, Image.LANCZOS)
        buffer = io.BytesIO()
        image.save(buffer, format="JPEG", quality=quality, optimize=True)
        result = buffer.getvalue()
        if len(result) < len(data) or scale < 1.0:
            return result, "image/jpeg"
    except Exception:  # noqa: BLE001 - compression is an optimisation
        logger.debug("Image compression skipped", exc_info=True)
    return data, _mime_from_bytes(data)


class _ProviderError(Exception):
    def __init__(self, status: int, body: str) -> None:
        super().__init__(f"{status}: {body[:200]}")
        self.status = status
        self.body = body


async def _post_json(
    session: aiohttp.ClientSession,
    url: str,
    payload: dict[str, Any],
    headers: dict[str, str],
    timeout: int,
) -> dict[str, Any]:
    try:
        async with session.post(
            url, json=payload, headers=headers, timeout=aiohttp.ClientTimeout(total=timeout)
        ) as response:
            text = await response.text()
            if response.status != 200:
                raise _ProviderError(response.status, text)
            try:
                return await response.json(content_type=None)
            except ValueError as exc:
                raise _ProviderError(response.status, text) from exc
    except TimeoutError as exc:
        raise AiUnavailable("انتهت مهلة مزود الذكاء الاصطناعي.") from exc
    except aiohttp.ClientError as exc:
        raise AiUnavailable("تعذّر الاتصال بمزود الذكاء الاصطناعي.") from exc


def _translate_error(error: _ProviderError, provider_label: str) -> Exception:
    if error.status in (401, 403):
        return AiAuthError(f"مزود {provider_label} رفض المفتاح.")
    if error.status == 402 or "insufficient" in error.body.lower():
        return AiAuthError(f"لا يوجد رصيد كافٍ لدى {provider_label}.")
    if error.status == 404:
        return AiUnavailable(f"النموذج أو العنوان المحدد غير متاح لدى {provider_label}.")
    if error.status == 400 and "model" in error.body.lower():
        return AiUnavailable(f"النموذج المحدد غير متاح لدى {provider_label}.")
    if "image" in error.body.lower() or "vision" in error.body.lower():
        return AiUnsupported(f"النموذج المحدد لدى {provider_label} لا يدعم الصور.")
    if error.status == 429:
        return AiUnavailable(f"{provider_label} يحدّ الطلبات حاليًا، جرّب بعد قليل.")
    return AiUnavailable(f"خطأ من {provider_label} ({error.status}).")


async def _chat_openai_compatible(
    config: AiConfig,
    *,
    system: str,
    user_text: str,
    image: bytes | None,
    temperature: float,
    max_tokens: int,
    json_mode: bool,
    timeout: int,
) -> str:
    if image is not None:
        image_bytes, mime = compress_image(image)
        content: Any = [
            {"type": "text", "text": user_text},
            {
                "type": "image_url",
                "image_url": {
                    "url": f"data:{mime};base64,{base64.b64encode(image_bytes).decode()}"
                },
            },
        ]
    else:
        content = user_text

    payload: dict[str, Any] = {
        "model": config.model,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": content},
        ],
        "temperature": temperature,
        "max_tokens": max_tokens,
    }
    if json_mode:
        payload["response_format"] = {"type": "json_object"}

    headers = {"Authorization": f"Bearer {config.api_key}", "Content-Type": "application/json"}
    headers.update(config.header_extra)
    url = f"{config.base_url.rstrip('/')}/chat/completions"

    async with aiohttp.ClientSession() as session:
        try:
            data = await _post_json(session, url, payload, headers, timeout)
        except _ProviderError as error:
            raise _translate_error(error, config.provider_label) from error

    try:
        return str(data["choices"][0]["message"]["content"])
    except (KeyError, IndexError, TypeError) as exc:
        raise AiUnavailable("استجابة غير متوقعة من مزود الذكاء الاصطناعي.") from exc


async def _chat_gemini(
    config: AiConfig,
    *,
    system: str,
    user_text: str,
    image: bytes | None,
    temperature: float,
    max_tokens: int,
    json_mode: bool,
    timeout: int,
) -> str:
    parts: list[dict[str, Any]] = [{"text": user_text}]
    if image is not None:
        parts.append(
            {
                "inline_data": {
                    "mime_type": _mime_from_bytes(image),
                    "data": base64.b64encode(image).decode(),
                }
            }
        )
    payload: dict[str, Any] = {
        "systemInstruction": {"parts": [{"text": system}]},
        "contents": [{"role": "user", "parts": parts}],
        "generationConfig": {
            "temperature": temperature,
            "maxOutputTokens": max_tokens,
        },
    }
    if json_mode:
        payload["generationConfig"]["responseMimeType"] = "application/json"

    base = config.base_url.rstrip("/")
    url = f"{base}/models/{config.model}:generateContent"
    headers = {"x-goog-api-key": config.api_key, "Content-Type": "application/json"}

    async with aiohttp.ClientSession() as session:
        try:
            data = await _post_json(session, url, payload, headers, timeout)
        except _ProviderError as error:
            raise _translate_error(error, config.provider_label) from error

    try:
        candidates = data["candidates"][0]["content"]["parts"]
        return "".join(str(part.get("text", "")) for part in candidates)
    except (KeyError, IndexError, TypeError) as exc:
        raise AiUnavailable("استجابة غير متوقعة من Gemini.") from exc


async def chat(
    config: AiConfig,
    *,
    system: str,
    user_text: str,
    image: bytes | None = None,
    temperature: float = 0.4,
    max_tokens: int = 2000,
    json_mode: bool = False,
    timeout: int = 120,
) -> str:
    if image is not None and not config.supports_vision:
        raise AiUnsupported(f"{config.provider_label} لا يدعم تحليل الصور.")
    if config.provider == "gemini":
        return await _chat_gemini(
            config,
            system=system,
            user_text=user_text,
            image=image,
            temperature=temperature,
            max_tokens=max_tokens,
            json_mode=json_mode,
            timeout=timeout,
        )
    return await _chat_openai_compatible(
        config,
        system=system,
        user_text=user_text,
        image=image,
        temperature=temperature,
        max_tokens=max_tokens,
        json_mode=json_mode,
        timeout=timeout,
    )


async def chat_with_fallback(
    configs: list[AiConfig],
    *,
    system: str,
    user_text: str,
    image: bytes | None = None,
    temperature: float = 0.5,
    max_tokens: int = 1400,
    timeout: int = 120,
) -> str:
    """Try each config in order, returning the first successful reply."""
    return await chat_race(
        configs,
        system=system,
        user_text=user_text,
        image=image,
        temperature=temperature,
        max_tokens=max_tokens,
        timeout=timeout,
    )


async def chat_race(
    configs: list[AiConfig],
    *,
    system: str,
    user_text: str,
    image: bytes | None = None,
    temperature: float = 0.5,
    max_tokens: int = 1400,
    timeout: int = 120,
    json_mode: bool = False,
) -> str:
    """Query configs in parallel and return the first successful answer.

    Slow vision models are the main cause of "no reply", so racing several
    models hides individual latencies. Auth errors abort immediately (a bad key
    will fail everywhere); other errors are tolerated until one succeeds.
    """
    if not configs:
        from app.core.errors import AiNotConfigured

        raise AiNotConfigured("لا يوجد مفتاح ذكاء اصطناعي متاح.")

    async def _one(config: AiConfig) -> tuple[AiConfig, str]:
        text = await chat(
            config,
            system=system,
            user_text=user_text,
            image=image,
            temperature=temperature,
            max_tokens=max_tokens,
            json_mode=json_mode,
            timeout=timeout,
        )
        return config, text

    tasks = [asyncio.create_task(_one(config)) for config in configs]
    errors: list[Exception] = []
    try:
        pending: set[asyncio.Task] = set(tasks)
        while pending:
            done, pending = await asyncio.wait(pending, return_when=asyncio.FIRST_COMPLETED)
            for task in done:
                try:
                    config, text = task.result()
                    logger.info("AI answered via %s/%s", config.provider, config.model)
                    return text
                except AiAuthError:
                    for other in pending:
                        other.cancel()
                    raise
                except Exception as exc:  # noqa: BLE001 - collect and continue
                    errors.append(exc)
        raise errors[-1] if errors else AiUnavailable("تعذّر الحصول على رد حاليًا.")
    finally:
        for task in tasks:
            if not task.done():
                task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)


async def ping(config: AiConfig, *, timeout: int = 30) -> tuple[bool, str]:
    """Validate a key/model with a tiny request."""
    try:
        await chat(
            config,
            system="Reply with the single word: OK",
            user_text="ping",
            max_tokens=8,
            temperature=0,
            timeout=timeout,
        )
        return True, "ok"
    except Exception as exc:  # noqa: BLE001 - reported to the user
        return False, str(exc)


async def ping_all(configs: list[AiConfig], *, timeout: int = 30) -> tuple[bool, str]:
    """Try each config (primary then fallbacks) until one answers."""
    last = "لا يوجد نموذج متاح."
    for config in configs:
        ok, message = await ping(config, timeout=timeout)
        if ok:
            return True, "ok"
        last = message
        logger.info("AI ping failed for %s/%s: %s", config.provider, config.model, message)
        # Auth errors are terminal: no point trying other models with a bad key.
        if "المفتاح" in message or "رصيد" in message:
            return False, message
    return False, last


def default_model(provider: str) -> str:
    return {
        "openrouter": "google/gemma-4-31b-it:free",
        "openai": "gpt-4.1-mini",
        "gemini": "gemini-2.5-flash",
        "nvidia": "meta/llama-3.2-11b-vision-instruct",
    }.get(provider, "")


async def sleep_between(seconds: float = 0.2) -> None:
    await asyncio.sleep(seconds)
