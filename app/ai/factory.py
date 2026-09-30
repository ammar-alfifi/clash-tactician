"""Resolve which AI configurations to use for a request."""

from __future__ import annotations

from app.ai.providers import KNOWN_BASE_URLS, AiConfig, default_model
from app.config import Settings
from app.core.errors import ConfigurationError
from app.storage.models import AiKey


def is_safe_base_url(url: str) -> bool:
    """Reject obviously unsafe custom endpoints (SSRF guard)."""
    from urllib.parse import urlparse

    try:
        parsed = urlparse(url.strip())
    except ValueError:
        return False
    if parsed.scheme != "https":
        return False
    host = (parsed.hostname or "").lower()
    if not host or host in {"localhost", "127.0.0.1", "0.0.0.0", "::1"}:
        return False
    if host.endswith(".local") or host.endswith(".internal"):
        return False
    # Block literal private IPv4 ranges.
    parts = host.split(".")
    if len(parts) == 4 and all(part.isdigit() for part in parts):
        octets = [int(part) for part in parts]
        if octets[0] in (10, 127) or (octets[0] == 192 and octets[1] == 168):
            return False
        if octets[0] == 172 and 16 <= octets[1] <= 31:
            return False
        if octets[0] == 169 and octets[1] == 254:
            return False
    return True


def build_user_configs(settings: Settings, key: AiKey, api_key: str) -> list[AiConfig]:
    provider = key.provider
    model = key.model or default_model(provider)
    if provider == "custom":
        base_url = (key.base_url or "").strip()
        if not is_safe_base_url(base_url):
            raise ConfigurationError("عنوان الخدمة المخصصة غير آمن أو غير صالح.")
        return [AiConfig(provider="custom", model=model, api_key=api_key, base_url=base_url)]

    base_url = key.base_url or KNOWN_BASE_URLS.get(provider, "")
    configs = [
        AiConfig(
            provider=provider,
            model=model,
            api_key=api_key,
            base_url=base_url,
            header_extra=_openrouter_headers(provider),
        )
    ]
    if provider == "openrouter":
        configs.extend(
            AiConfig(
                provider="openrouter",
                model=fallback,
                api_key=api_key,
                base_url=base_url,
                header_extra=_openrouter_headers(provider),
            )
            for fallback in settings.openrouter_fallback_models
            if fallback != model
        )
    elif provider == "nvidia":
        configs.extend(
            AiConfig(provider="nvidia", model=fallback, api_key=api_key, base_url=base_url)
            for fallback in settings.nvidia_fallback_models
            if fallback != model
        )
    return configs


def build_shared_configs(settings: Settings) -> list[AiConfig]:
    """Shared operator keys, ordered by what actually works for vision + JSON.

    Verified against the live APIs (2026): many NVIDIA models advertised as
    multimodal reject images (HTTP 400), so only models confirmed to accept
    image input are included. Both providers are offered so the planner's race
    can hide the latency or congestion of any single model.
    """
    configs: list[AiConfig] = []
    if settings.openrouter_api_key:
        models = _dedupe((settings.openrouter_model, *settings.openrouter_fallback_models))
        configs.extend(
            AiConfig(
                provider="openrouter",
                model=model,
                api_key=settings.openrouter_api_key,
                base_url=settings.openrouter_base_url,
                label="OpenRouter (مشترك)",
                header_extra=_openrouter_headers("openrouter"),
            )
            for model in models
        )
    if settings.nvidia_api_key:
        models = _dedupe((settings.nvidia_model, *settings.nvidia_fallback_models))
        configs.extend(
            AiConfig(
                provider="nvidia",
                model=model,
                api_key=settings.nvidia_api_key,
                base_url=settings.nvidia_base_url,
                label="NVIDIA NIM (مشترك)",
            )
            for model in models
        )
        # Strong text-only model for the planning stage (no image needed).
        if settings.nvidia_text_model:
            configs.append(
                AiConfig(
                    provider="nvidia",
                    model=settings.nvidia_text_model,
                    api_key=settings.nvidia_api_key,
                    base_url=settings.nvidia_base_url,
                    label="NVIDIA NIM (تخطيط)",
                    vision=False,
                )
            )
    return configs


def _dedupe(values: tuple[str, ...]) -> list[str]:
    seen: list[str] = []
    for value in values:
        if value and value not in seen:
            seen.append(value)
    return seen


def resolve_configs(
    settings: Settings, key: AiKey | None, api_key: str | None
) -> list[AiConfig]:
    """Prefer the user's own key, otherwise the shared operator key."""
    if key and api_key:
        return build_user_configs(settings, key, api_key)
    return build_shared_configs(settings)


def _openrouter_headers(provider: str) -> dict[str, str]:
    if provider != "openrouter":
        return {}
    return {"HTTP-Referer": "https://clash-tactician.onrender.com", "X-Title": "Clash Tactician"}
