from io import BytesIO

import pytest
from PIL import Image

from app.ai import AIProviderError
from app.planner import prepare_image, render_plan, validate_plan


def _png_bytes(size=(240, 160)):
    image = Image.new("RGB", size, color=(40, 90, 120))
    buffer = BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


def _plan_json(point_x=0.5):
    return (
        '{"goal":"نجمتان","summary":"خطة تجريبية","confidence":0.6,'
        '"phases":[{"name":"دخول","action":"ابدأ من هنا","reason":"تقليل الانجراف",'
        f'"point":{{"x":{point_x},"y":0.25}}}},'
        '{"name":"تنظيف","action":"احتفظ بوحدات للتنظيف","reason":"تغطية الأطراف",'
        '"point":{"x":0.8,"y":0.75}}],"uncertainties":["مستوى الدفاع غير واضح"]}'
    )


def test_prepare_image_converts_to_normalized_jpeg():
    data_url, image_buffer = prepare_image(_png_bytes())

    assert data_url.startswith("data:image/jpeg;base64,")
    with Image.open(image_buffer) as image:
        assert image.format == "JPEG"
        assert image.size == (240, 160)


def test_plan_validation_and_annotation_keep_image_dimensions():
    plan = validate_plan(_plan_json())
    _, original = prepare_image(_png_bytes())

    annotated = render_plan(original, plan)

    with Image.open(annotated) as image:
        assert image.size == (240, 160)
        assert image.format == "JPEG"


def test_rejects_plan_coordinates_outside_image():
    with pytest.raises(AIProviderError):
        validate_plan(_plan_json(point_x=1.2))


def test_rejects_non_image_upload():
    with pytest.raises(ValueError):
        prepare_image(b"not an image")
