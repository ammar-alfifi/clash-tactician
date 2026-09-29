import base64
import binascii

import aiohttp

from app.ai import GEMINI_MODEL, AIProviderError

GEMINI_API_URL = "https://generativelanguage.googleapis.com/v1beta"


async def _request_error(response: aiohttp.ClientResponse) -> None:
    if response.status in {400, 401, 403}:
        raise AIProviderError("مفتاح Gemini غير صالح أو لا يملك صلاحية استخدام Gemini API.")
    if response.status == 429:
        raise AIProviderError("وصل حساب Gemini إلى حد الاستخدام أو الحصة المتاحة؛ حاول لاحقًا.")
    if response.status >= 500:
        raise AIProviderError("خدمة Gemini لا تستجيب الآن؛ حاول لاحقًا.")
    if response.status >= 400:
        raise AIProviderError("رفض Gemini الطلب؛ تحقق من المفتاح وإعداد Google AI Studio.")


async def test_gemini_key(api_key: str) -> None:
    timeout = aiohttp.ClientTimeout(total=15)
    try:
        async with (
            aiohttp.ClientSession(timeout=timeout) as session,
            session.get(
                f"{GEMINI_API_URL}/models",
                headers={"x-goog-api-key": api_key},
            ) as response,
        ):
            await _request_error(response)
            payload = await response.json()
            models = {
                item.get("name", "").removeprefix("models/"): item
                for item in payload.get("models", [])
            }
            model = models.get(GEMINI_MODEL)
            if not model or "generateContent" not in model.get("supportedGenerationMethods", []):
                raise AIProviderError(
                    "المفتاح صالح، لكن نموذج Gemini الافتراضي غير متاح لهذا المفتاح أو المنطقة."
                )
    except TimeoutError as exc:
        raise AIProviderError("انتهت مهلة الاتصال بـGemini؛ حاول مجددًا.") from exc
    except aiohttp.ClientError as exc:
        raise AIProviderError("تعذر الاتصال بـGemini؛ حاول لاحقًا.") from exc


def _response_schema() -> dict:
    return {
        "type": "OBJECT",
        "properties": {
            "goal": {"type": "STRING"},
            "summary": {"type": "STRING"},
            "confidence": {"type": "NUMBER"},
            "phases": {
                "type": "ARRAY",
                "items": {
                    "type": "OBJECT",
                    "properties": {
                        "name": {"type": "STRING"},
                        "action": {"type": "STRING"},
                        "reason": {"type": "STRING"},
                        "point": {
                            "type": "OBJECT",
                            "properties": {
                                "x": {"type": "NUMBER"},
                                "y": {"type": "NUMBER"},
                            },
                            "required": ["x", "y"],
                        },
                    },
                    "required": ["name", "action", "reason", "point"],
                },
            },
            "uncertainties": {"type": "ARRAY", "items": {"type": "STRING"}},
        },
        "required": ["goal", "summary", "confidence", "phases", "uncertainties"],
    }


async def create_attack_plan(api_key: str, prompt: str, image_data_url: str) -> str:
    try:
        header, encoded_image = image_data_url.split(",", maxsplit=1)
        mime_type = header.removeprefix("data:").removesuffix(";base64")
        image_bytes = base64.b64decode(encoded_image, validate=True)
    except (ValueError, binascii.Error) as exc:
        raise AIProviderError("تعذر تجهيز الصورة للتحليل؛ أعد إرسالها بصيغة JPG أو PNG.") from exc

    payload = {
        "contents": [
            {
                "parts": [
                    {"text": prompt},
                    {
                        "inlineData": {
                            "mimeType": mime_type,
                            "data": base64.b64encode(image_bytes).decode("ascii"),
                        }
                    },
                ]
            }
        ],
        "generationConfig": {
            "responseMimeType": "application/json",
            "responseSchema": _response_schema(),
            "maxOutputTokens": 1800,
        },
    }
    timeout = aiohttp.ClientTimeout(total=60)
    try:
        async with (
            aiohttp.ClientSession(timeout=timeout) as session,
            session.post(
                f"{GEMINI_API_URL}/models/{GEMINI_MODEL}:generateContent",
                headers={"x-goog-api-key": api_key},
                json=payload,
            ) as response,
        ):
            await _request_error(response)
            data = await response.json()
            candidates = data.get("candidates", [])
            parts = candidates[0].get("content", {}).get("parts", []) if candidates else []
            output_text = next(
                (part.get("text") for part in parts if isinstance(part.get("text"), str)),
                None,
            )
            if not output_text or not output_text.strip():
                raise AIProviderError("لم يرجع Gemini خطة قابلة للتحقق؛ جرّب صورة أو وصفًا أوضح.")
            return output_text
    except TimeoutError as exc:
        raise AIProviderError("استغرق تحليل الصورة وقتًا طويلًا؛ حاول مجددًا لاحقًا.") from exc
    except aiohttp.ClientError as exc:
        raise AIProviderError("تعذر الاتصال بـGemini؛ حاول لاحقًا.") from exc
