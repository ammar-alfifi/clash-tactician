"""Key vault, provider resolution and SSRF guard."""

from __future__ import annotations

import pytest

from app.ai.factory import (
    build_shared_configs,
    build_user_configs,
    is_safe_base_url,
    resolve_configs,
)
from app.ai.providers import AiConfig, chat
from app.ai.vault import KeyVault
from app.config import Settings
from app.core.errors import AiUnsupported, ConfigurationError
from app.storage.models import AiKey


def _key(provider="openrouter", model="m", base_url=None) -> AiKey:
    return AiKey(
        telegram_id=1,
        provider=provider,
        model=model,
        base_url=base_url,
        encrypted_key="cipher",
        ok=True,
        last_checked_at=None,
    )


def test_vault_roundtrip():
    vault = KeyVault(KeyVault.generate_key())
    token = vault.encrypt("secret-key")
    assert token != "secret-key"
    assert vault.decrypt(token) == "secret-key"


def test_vault_invalid_master_key():
    with pytest.raises(ConfigurationError):
        KeyVault("not-a-valid-fernet-key")


def test_vault_without_key():
    vault = KeyVault(None)
    assert not vault.enabled
    assert vault.decrypt("anything") is None
    with pytest.raises(ConfigurationError):
        vault.encrypt("x")


def test_safe_base_url():
    assert is_safe_base_url("https://api.example.com/v1")
    assert not is_safe_base_url("http://api.example.com/v1")
    assert not is_safe_base_url("https://127.0.0.1/v1")
    assert not is_safe_base_url("https://192.168.1.10/v1")
    assert not is_safe_base_url("https://10.0.0.5/v1")
    assert not is_safe_base_url("https://internal.local/v1")
    assert not is_safe_base_url("file:///etc/passwd")


def test_build_user_configs_openrouter_fallbacks(settings: Settings):
    settings = Settings(
        bot_token="t",
        openrouter_fallback_models=("fb1", "fb2"),
    )
    configs = build_user_configs(settings, _key(model="main"), "k")
    assert [c.model for c in configs] == ["main", "fb1", "fb2"]
    assert all(c.api_key == "k" for c in configs)


def test_build_user_configs_rejects_unsafe_custom(settings: Settings):
    with pytest.raises(ConfigurationError):
        build_user_configs(settings, _key(provider="custom", base_url="http://localhost"), "k")


def test_build_shared_configs_dedupes():
    settings = Settings(
        bot_token="t",
        openrouter_api_key="shared",
        openrouter_model="a",
        openrouter_fallback_models=("a", "b"),
    )
    configs = build_shared_configs(settings)
    assert [c.model for c in configs] == ["a", "b"]


def test_resolve_prefers_user_key():
    settings = Settings(bot_token="t", openrouter_api_key="shared")
    configs = resolve_configs(settings, _key(model="mine"), "user-key")
    assert configs[0].api_key == "user-key"
    configs = resolve_configs(settings, None, None)
    assert configs[0].api_key == "shared"
    configs = resolve_configs(settings, None, None)
    assert configs


def test_nvidia_shared_preferred_over_openrouter():
    settings = Settings(
        bot_token="t",
        nvidia_api_key="nv",
        nvidia_model="meta/llama-3.2-11b-vision-instruct",
        nvidia_fallback_models=("meta/llama-3.2-90b-vision-instruct",),
        openrouter_api_key="or",
    )
    configs = build_shared_configs(settings)
    assert configs[0].provider == "nvidia"
    assert [c.model for c in configs] == [
        "meta/llama-3.2-11b-vision-instruct",
        "meta/llama-3.2-90b-vision-instruct",
    ]
    assert configs[0].supports_vision


def test_openrouter_shared_used_as_fallback():
    settings = Settings(bot_token="t", openrouter_api_key="or", openrouter_model="m")
    configs = build_shared_configs(settings)
    assert configs[0].provider == "openrouter"


def test_nvidia_user_key_has_fallbacks():
    settings = Settings(
        bot_token="t",
        nvidia_fallback_models=("fb",),
    )
    configs = build_user_configs(
        settings, _key(provider="nvidia", model="main"), "user-nv"
    )
    assert [c.model for c in configs] == ["main", "fb"]
    assert all(c.base_url == "https://integrate.api.nvidia.com/v1" for c in configs)


def test_has_shared_ai_covers_nvidia():
    assert Settings(bot_token="t", nvidia_api_key="nv").has_shared_ai
    assert Settings(bot_token="t", openrouter_api_key="or").has_shared_ai
    assert not Settings(bot_token="t").has_shared_ai


async def test_chat_rejects_vision_for_text_only():
    config = AiConfig(provider="multimodal", model="text", api_key="k", base_url="https://x.test")
    with pytest.raises(AiUnsupported):
        await chat(config, system="s", user_text="u", image=b"x" * 10)


async def test_chat_remote_supports_vision_flag():
    config = AiConfig(
        provider="custom", model="vision", api_key="k", base_url="https://x.test"
    )
    # OpenAI-compatible providers are assumed to support images (no error raised
    # before any network call); the request itself fails without a server.
    assert config.supports_vision
    assert not AiConfig(
        provider="multimodal", model="m", api_key="k", base_url="https://x.test"
    ).supports_vision
