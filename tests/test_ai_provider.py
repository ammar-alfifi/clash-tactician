from unittest.mock import AsyncMock

import pytest

from app import ai_provider
from app.ai import AIProviderError


def test_provider_models_are_defined():
    assert ai_provider.provider_details("openai") == ("OpenAI", "gpt-4.1-mini")
    assert ai_provider.provider_details("gemini") == ("Gemini", "gemini-2.5-flash")
    assert ai_provider.provider_details("openrouter") == (
        "OpenRouter",
        "stealth/space-bunny-alpha",
    )


def test_unknown_provider_is_rejected():
    with pytest.raises(AIProviderError):
        ai_provider.provider_details("unknown")


@pytest.mark.asyncio
async def test_plan_dispatches_to_selected_provider(monkeypatch):
    gemini_plan = AsyncMock(return_value='{"summary":"خطة"}')
    monkeypatch.setattr(ai_provider, "create_gemini_plan", gemini_plan)

    result = await ai_provider.create_provider_plan("gemini", "secret", "prompt", "image")

    assert result == '{"summary":"خطة"}'
    gemini_plan.assert_awaited_once_with("secret", "prompt", "image")


@pytest.mark.asyncio
async def test_custom_provider_uses_its_model_and_endpoint(monkeypatch):
    openai_plan = AsyncMock(return_value='{"summary":"خطة"}')
    monkeypatch.setattr(ai_provider, "create_openai_plan", openai_plan)

    await ai_provider.create_provider_plan(
        "custom",
        "secret",
        "prompt",
        "image",
        model="llama-3.3-70b",
        base_url="https://llm.example/v1",
        fallback_models=(),
    )

    openai_plan.assert_awaited_once_with(
        "secret",
        "prompt",
        "image",
        model="llama-3.3-70b",
        base_url="https://llm.example/v1",
        fallback_models=(),
    )


@pytest.mark.asyncio
async def test_openrouter_uses_free_fallback_models(monkeypatch):
    openai_plan = AsyncMock(return_value='{"summary":"خطة"}')
    monkeypatch.setattr(ai_provider, "create_openai_plan", openai_plan)
    fallbacks = ("qwen/qwen3.8-27b:free", "google/gemma-4-26b-a4b-it:free")

    await ai_provider.create_provider_plan(
        "openrouter",
        "secret",
        "prompt",
        "image",
        model="google/gemma-4-31b-it:free",
        fallback_models=fallbacks,
    )

    openai_plan.assert_awaited_once_with(
        "secret",
        "prompt",
        "image",
        model="google/gemma-4-31b-it:free",
        base_url=ai_provider.OPENROUTER_BASE_URL,
        fallback_models=fallbacks,
    )


def test_custom_endpoint_requires_secure_openai_compatible_api_root():
    assert ai_provider.validate_custom_endpoint("https://llm.example/v1/") == (
        "https://llm.example/v1"
    )
    with pytest.raises(ValueError):
        ai_provider.validate_custom_endpoint("http://llm.example/v1")
    with pytest.raises(ValueError):
        ai_provider.validate_custom_endpoint("https://llm.example/v1/models")
