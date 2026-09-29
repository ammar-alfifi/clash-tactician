import json

import aiohttp

from app.ai import OPENAI_MODEL, AIProviderError

MODEL = OPENAI_MODEL

OPENAI_MODELS_URL = "https://api.openai.com/v1/models"
OPENAI_RESPONSES_URL = "https://api.openai.com/v1/responses"
DEFAULT_BASE_URL = "https://api.openai.com/v1"


async def test_openai_key(api_key: str) -> None:
    await test_openai_compatible_key(api_key, DEFAULT_BASE_URL, OPENAI_MODEL)


async def test_openai_compatible_key(api_key: str, base_url: str, model: str) -> None:
    timeout = aiohttp.ClientTimeout(total=15)
    try:
        async with (
            aiohttp.ClientSession(timeout=timeout) as session,
            session.get(
                f"{base_url.rstrip('/')}/models",
                headers={"Authorization": f"Bearer {api_key}"},
            ) as response,
        ):
            if response.status == 401:
                raise AIProviderError("مفتاح API غير صالح. تحقق منه وحاول مجددًا.")
            if response.status == 429:
                raise AIProviderError("رفض المزود الطلب بسبب حد الاستخدام أو الرصيد.")
            if response.status >= 500:
                raise AIProviderError("خدمة المزود لا تستجيب الآن؛ حاول لاحقًا.")
            if response.status in {404, 405}:
                # Some OpenAI-compatible services do not expose a model-list endpoint.
                return
            if response.status >= 400:
                raise AIProviderError("تعذر اختبار المفتاح؛ تحقق من صلاحياته وإعداد الحساب.")
            payload = await response.json()
            model_ids = {item.get("id") for item in payload.get("data", [])}
            if model_ids and model not in model_ids:
                raise AIProviderError(
                    f"المفتاح صالح، لكن النموذج {model} غير موجود لدى هذا المزود."
                )
    except TimeoutError as exc:
        raise AIProviderError("انتهت مهلة الاتصال بمزود الذكاء الاصطناعي؛ حاول مجددًا.") from exc
    except aiohttp.ClientError as exc:
        raise AIProviderError("تعذر الاتصال بمزود الذكاء الاصطناعي؛ حاول لاحقًا.") from exc


async def create_attack_plan(
    api_key: str,
    prompt: str,
    image_data_url: str,
    model: str = OPENAI_MODEL,
    base_url: str = DEFAULT_BASE_URL,
    fallback_models: tuple[str, ...] = (),
) -> str:
    schema = {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "goal": {"type": "string"},
            "summary": {"type": "string"},
            "confidence": {"type": "number"},
            "phases": {
                "type": "array",
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "properties": {
                        "name": {"type": "string"},
                        "action": {"type": "string"},
                        "reason": {"type": "string"},
                        "point": {
                            "type": "object",
                            "additionalProperties": False,
                            "properties": {
                                "x": {"type": "number"},
                                "y": {"type": "number"},
                            },
                            "required": ["x", "y"],
                        },
                    },
                    "required": ["name", "action", "reason", "point"],
                },
            },
            "uncertainties": {"type": "array", "items": {"type": "string"}},
        },
        "required": ["goal", "summary", "confidence", "phases", "uncertainties"],
    }
    payload = {
        "model": model,
        "messages": [
            {
                "role": "system",
                "content": (
                    "Return only a JSON object matching this schema; do not include markdown: "
                    + json.dumps(schema, ensure_ascii=False)
                ),
            },
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {"type": "image_url", "image_url": {"url": image_data_url}},
                ],
            }
        ],
        "response_format": {"type": "json_object"},
        "max_tokens": 1800,
    }
    if fallback_models:
        # OpenRouter accepts at most 3 entries in the fallback "models" array.
        payload["models"] = [model, *fallback_models][:3]
        payload.pop("model")
    timeout = aiohttp.ClientTimeout(total=240)
    try:
        async with (
            aiohttp.ClientSession(timeout=timeout) as session,
            session.post(
                f"{base_url.rstrip('/')}/chat/completions",
                headers={"Authorization": f"Bearer {api_key}"},
                json=payload,
            ) as response,
        ):
            body_text = await response.text()
            try:
                error_body = json.loads(body_text) if body_text else {}
            except ValueError:
                error_body = {}
            provider_error = str(
                (error_body.get("error") or {}).get("message") or ""
            ).strip()
            if response.status in {401, 403}:
                raise AIProviderError("تعذر استخدام المفتاح؛ أعد اختباره عبر /testkey.")
            if response.status == 402:
                raise AIProviderError("رصيد حساب المزود غير كافٍ لهذا الطلب.")
            if response.status == 429:
                if "rate-limited upstream" in provider_error:
                    raise AIProviderError(
                        "النموذج المجاني مثقل حاليًا عند المزود؛ جرّب بعد دقائق، "
                        "أو أعد المحاولة لأن البوت سيجرب النموذج الاحتياطي تلقائيًا."
                    )
                raise AIProviderError(
                    "وصل حد الاستخدام اليومي للنماذج المجانية؛ أعد المحاولة لاحقًا "
                    "أو أضف مفتاحًا شخصيًا عبر /setkey لرفع الحد."
                )
            if response.status >= 500:
                raise AIProviderError("خدمة المزود لا تستجيب الآن؛ حاول لاحقًا.")
            if response.status >= 400:
                detail = (
                    f" ({provider_error[:140]})" if provider_error else ""
                )
                raise AIProviderError(
                    f"رفض المزود طلب تحليل الصورة{detail}؛ تحقق من النموذج والمفتاح."
                )
            data = error_body
            choices = data.get("choices", [])
            output_text = choices[0].get("message", {}).get("content") if choices else None
            if not isinstance(output_text, str) or not output_text.strip():
                raise AIProviderError("لم يرجع النموذج خطة قابلة للتحقق؛ جرّب صورة أو وصفًا أوضح.")
            return output_text
    except TimeoutError as exc:
        raise AIProviderError("استغرق تحليل الصورة وقتًا طويلًا؛ حاول مجددًا لاحقًا.") from exc
    except aiohttp.ClientError as exc:
        raise AIProviderError("تعذر الاتصال بمزود الذكاء الاصطناعي؛ حاول لاحقًا.") from exc
