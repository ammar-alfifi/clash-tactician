from app.ai import GEMINI_MODEL, OPENAI_MODEL, AIProviderError
from app.ai_gemini import create_attack_plan as create_gemini_plan
from app.ai_gemini import test_gemini_key
from app.ai_openai import create_attack_plan as create_openai_plan

OPENROUTER_MODEL = "stealth/space-bunny-alpha"
OPENROUTER_FALLBACK_MODELS = (
    "google/gemma-4-31b-it:free",
    "qwen/qwen3.8-27b:free",
)
OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
OPENAI_BASE_URL = "https://api.openai.com/v1"

PROVIDERS = {
    "openrouter": ("OpenRouter", OPENROUTER_MODEL),
    "openai": ("OpenAI", OPENAI_MODEL),
    "gemini": ("Gemini", GEMINI_MODEL),
}

OPENAI_COMPATIBLE_BASE_URLS = {
    "openrouter": OPENROUTER_BASE_URL,
    "openai": OPENAI_BASE_URL,
}


def provider_details(provider: str) -> tuple[str, str]:
    try:
        return PROVIDERS[provider]
    except KeyError as exc:
        raise AIProviderError("مزود الذكاء الاصطناعي المحفوظ غير معروف؛ أعد إعداد المفتاح.") from exc


async def test_provider_key(
    provider: str,
    api_key: str,
    model: str | None = None,
    base_url: str | None = None,
) -> None:
    if provider == "custom":
        if not model:
            raise AIProviderError("معرّف النموذج مطلوب لإعداد الواجهة المخصصة.")
    else:
        _, default_model = provider_details(provider)
        model = model or default_model
    await test_configured_provider_key(provider, api_key, model, base_url)


async def create_provider_plan(
    provider: str,
    api_key: str,
    prompt: str,
    image_data_url: str,
    model: str | None = None,
    base_url: str | None = None,
    fallback_models: tuple[str, ...] = (),
) -> str:
    if provider == "custom":
        default_model = model
    else:
        _, default_model = provider_details(provider)
    if provider == "gemini":
        return await create_gemini_plan(api_key, prompt, image_data_url)
    endpoint = base_url or OPENAI_COMPATIBLE_BASE_URLS.get(provider)
    if not endpoint:
        raise AIProviderError("عنوان واجهة الذكاء الاصطناعي غير مضبوط؛ أعد إعداد المزود.")
    return await create_openai_plan(
        api_key,
        prompt,
        image_data_url,
        model=model or default_model,
        base_url=endpoint,
        fallback_models=fallback_models if provider == "openrouter" else (),
    )


async def test_configured_provider_key(
    provider: str, api_key: str, model: str, base_url: str | None = None
) -> None:
    if provider == "gemini":
        await test_gemini_key(api_key)
        return
    endpoint = base_url or OPENAI_COMPATIBLE_BASE_URLS.get(provider)
    if not endpoint:
        raise AIProviderError("عنوان واجهة الذكاء الاصطناعي غير مضبوط؛ أعد إعداد المزود.")
    from app.ai_openai import test_openai_compatible_key

    await test_openai_compatible_key(api_key, endpoint, model)


def provider_endpoint(provider: str) -> str | None:
    return OPENAI_COMPATIBLE_BASE_URLS.get(provider)


def validate_custom_endpoint(value: str) -> str:
    from ipaddress import ip_address
    from urllib.parse import urlsplit, urlunsplit

    endpoint = value.strip().rstrip("/")
    parsed = urlsplit(endpoint)
    hostname = parsed.hostname
    if not hostname or parsed.username or parsed.password or parsed.query or parsed.fragment:
        raise ValueError("أرسل عنوانًا كاملًا دون بيانات دخول أو معاملات إضافية.")
    is_loopback = hostname.lower() == "localhost"
    try:
        is_loopback = is_loopback or ip_address(hostname).is_loopback
    except ValueError:
        pass
    if parsed.scheme != "https" and not (parsed.scheme == "http" and is_loopback):
        raise ValueError("يجب أن يستخدم العنوان HTTPS؛ يُسمح بـHTTP على localhost فقط.")
    if parsed.path.endswith(("/chat/completions", "/models")):
        raise ValueError("أرسل عنوان API الأساسي مثل https://example.com/v1 دون مسار العملية.")
    return urlunsplit((parsed.scheme, parsed.netloc, parsed.path.rstrip("/"), "", ""))
