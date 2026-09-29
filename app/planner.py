import base64
from io import BytesIO
from math import atan2, cos, sin

from PIL import Image, ImageDraw, ImageOps, UnidentifiedImageError
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from app.ai import AIProviderError
from app.ai_provider import create_provider_plan

MAX_UPLOAD_BYTES = 8 * 1024 * 1024
MAX_IMAGE_PIXELS = 20_000_000
MAX_SIDE = 1536


class Point(BaseModel):
    model_config = ConfigDict(extra="forbid")

    x: float = Field(ge=0, le=1)
    y: float = Field(ge=0, le=1)


class PlanPhase(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=80)
    action: str = Field(min_length=1, max_length=500)
    reason: str = Field(min_length=1, max_length=500)
    point: Point


class AttackPlan(BaseModel):
    model_config = ConfigDict(extra="forbid")

    goal: str = Field(min_length=1, max_length=120)
    summary: str = Field(min_length=1, max_length=500)
    confidence: float = Field(ge=0, le=1)
    phases: list[PlanPhase] = Field(min_length=2, max_length=5)
    uncertainties: list[str] = Field(max_length=8)


def prepare_image(image_bytes: bytes) -> tuple[str, BytesIO]:
    if not image_bytes or len(image_bytes) > MAX_UPLOAD_BYTES:
        raise ValueError("حجم الصورة فارغ أو يتجاوز 8 ميغابايت.")
    try:
        with Image.open(BytesIO(image_bytes)) as source:
            if source.format not in {"JPEG", "PNG", "WEBP"}:
                raise ValueError("أرسل صورة بصيغة JPG أو PNG أو WEBP.")
            if source.width * source.height > MAX_IMAGE_PIXELS:
                raise ValueError("أبعاد الصورة كبيرة جدًا؛ أرسل لقطة شاشة أصغر.")
            source.load()
            image = ImageOps.exif_transpose(source).convert("RGB")
            image.thumbnail((MAX_SIDE, MAX_SIDE))
    except (UnidentifiedImageError, OSError) as exc:
        raise ValueError("تعذر قراءة الصورة؛ أرسل لقطة شاشة واضحة بصيغة JPG أو PNG.") from exc

    output = BytesIO()
    image.save(output, format="JPEG", quality=85, optimize=True)
    output.seek(0)
    data_url = "data:image/jpeg;base64," + base64.b64encode(output.getvalue()).decode("ascii")
    return data_url, output


def validate_plan(raw_json: str) -> AttackPlan:
    try:
        return AttackPlan.model_validate_json(raw_json)
    except ValidationError as exc:
        raise AIProviderError("وصلت خطة غير مكتملة أو بإحداثيات غير صالحة؛ أعد المحاولة.") from exc


def render_plan(image_stream: BytesIO, plan: AttackPlan) -> BytesIO:
    image_stream.seek(0)
    with Image.open(image_stream) as source:
        image = source.convert("RGB")
    draw = ImageDraw.Draw(image)
    points = [
        (int(phase.point.x * (image.width - 1)), int(phase.point.y * (image.height - 1)))
        for phase in plan.phases
    ]
    for index, (x, y) in enumerate(points, start=1):
        radius = max(14, min(image.size) // 24)
        if index > 1:
            previous_x, previous_y = points[index - 2]
            draw.line((previous_x, previous_y, x, y), fill=(255, 220, 0), width=max(4, radius // 5))
            angle = atan2(y - previous_y, x - previous_x)
            head_length = max(12, radius)
            head_width = head_length * 0.55
            base_x = x - head_length * cos(angle)
            base_y = y - head_length * sin(angle)
            offset_x = head_width * sin(angle)
            offset_y = -head_width * cos(angle)
            draw.polygon(
                [
                    (x, y),
                    (base_x + offset_x, base_y + offset_y),
                    (base_x - offset_x, base_y - offset_y),
                ],
                fill=(255, 220, 0),
            )
        draw.ellipse((x - radius, y - radius, x + radius, y + radius), fill=(190, 35, 35))
        label = str(index)
        bounds = draw.textbbox((0, 0), label)
        draw.text(
            (x - (bounds[2] - bounds[0]) / 2, y - (bounds[3] - bounds[1]) / 2),
            label,
            fill="white",
        )
    result = BytesIO()
    image.save(result, format="JPEG", quality=88, optimize=True)
    result.seek(0)
    return result


async def create_plan(
    provider: str,
    api_key: str,
    prompt: str,
    image_data_url: str,
    model: str | None = None,
    base_url: str | None = None,
    fallback_models: tuple[str, ...] = (),
) -> AttackPlan:
    return validate_plan(
        await create_provider_plan(
            provider, api_key, prompt, image_data_url, model, base_url, fallback_models
        )
    )
