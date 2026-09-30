"""Render an annotated base image from a validated plan (numbers only in-image)."""

from __future__ import annotations

import io
import math

from PIL import Image, ImageDraw, ImageFont

from app.core.errors import ImageError
from app.planner.schema import GRID_SIZE, Plan

PALETTE = [
    (231, 76, 60),
    (52, 152, 219),
    (46, 204, 113),
    (241, 196, 15),
    (155, 89, 182),
    (230, 126, 34),
]

_KIND_SHAPES = {
    "entry": "arrow",
    "target": "circle",
    "spell": "diamond",
    "hero": "square",
    "cleanup": "circle",
    "danger": "cross",
    "rally": "square",
    "siege": "diamond",
}


def _font(size: int) -> ImageFont.ImageFont:
    for name in ("DejaVuSans-Bold.ttf", "DejaVuSans.ttf", "arial.ttf"):
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            continue
    return ImageFont.load_default()


def _draw_arrow(draw: ImageDraw.ImageDraw, start: tuple[float, float], end: tuple[float, float],
                color: tuple[int, int, int], width: int) -> None:
    draw.line([start, end], fill=color, width=width)
    angle = math.atan2(end[1] - start[1], end[0] - start[0])
    head = max(12, width * 4)
    left = (
        end[0] - head * math.cos(angle - math.pi / 7),
        end[1] - head * math.sin(angle - math.pi / 7),
    )
    right = (
        end[0] - head * math.cos(angle + math.pi / 7),
        end[1] - head * math.sin(angle + math.pi / 7),
    )
    draw.polygon([end, left, right], fill=color)


def _draw_marker(
    draw: ImageDraw.ImageDraw,
    x: float,
    y: float,
    number: int,
    kind: str,
    color: tuple[int, int, int],
    radius: int,
    font: ImageFont.ImageFont,
) -> None:
    shape = _KIND_SHAPES.get(kind, "circle")
    box = (x - radius, y - radius, x + radius, y + radius)
    if shape == "square":
        draw.rounded_rectangle(
            box, radius=radius // 3, fill=color, outline=(255, 255, 255), width=3
        )
    elif shape == "diamond":
        draw.polygon(
            [(x, y - radius), (x + radius, y), (x, y + radius), (x - radius, y)],
            fill=color,
            outline=(255, 255, 255),
        )
    elif shape == "cross":
        draw.line([(x - radius, y - radius), (x + radius, y + radius)], fill=color, width=6)
        draw.line([(x - radius, y + radius), (x + radius, y - radius)], fill=color, width=6)
    else:
        draw.ellipse(box, fill=color, outline=(255, 255, 255), width=3)

    text = str(number)
    try:
        bbox = draw.textbbox((0, 0), text, font=font)
        text_w, text_h = bbox[2] - bbox[0], bbox[3] - bbox[1]
    except Exception:  # pragma: no cover - very old Pillow
        text_w, text_h = radius, radius
    draw.text((x - text_w / 2, y - text_h / 2 - 2), text, fill=(255, 255, 255), font=font)


def render_plan(image_bytes: bytes, plan: Plan) -> bytes:
    """Return a PNG with numbered phase markers and arrows."""
    try:
        image = Image.open(io.BytesIO(image_bytes))
        image.load()
    except Exception as exc:  # noqa: BLE001 - surfaced as a friendly error
        raise ImageError("تعذّر فتح الصورة المرسلة.") from exc

    image = image.convert("RGB")
    width, height = image.size
    if width < 64 or height < 64:
        raise ImageError("الصورة صغيرة جدًا لتحليلها.")

    draw = ImageDraw.Draw(image, "RGBA")
    radius = max(14, int(min(width, height) * 0.028))
    line_width = max(5, radius // 3)
    font_big = _font(max(16, int(radius * 1.1)))
    font_leg = _font(max(14, int(radius * 0.8)))

    # Light grid overlay so the player can read the cell labels the plan uses.
    grid_color = (255, 255, 255, 60)
    for step in range(1, GRID_SIZE):
        x = int(width * step / GRID_SIZE)
        y = int(height * step / GRID_SIZE)
        draw.line([(x, 0), (x, height)], fill=grid_color, width=2)
        draw.line([(0, y), (width, y)], fill=grid_color, width=2)

    # Low-confidence detections get a subtle dashed box (transparency aid).
    for detection in plan.detections:
        if detection.confidence >= 0.4:
            continue
        from app.planner.schema import cell_to_point

        point = cell_to_point(detection.cell)
        if point is None:
            continue
        cx, cy = point[0] * width, point[1] * height
        size = radius * 2
        draw.rectangle(
            (cx - size, cy - size, cx + size, cy + size),
            outline=(255, 215, 0, 220),
            width=3,
        )

    points: list[list[tuple[float, float]]] = []
    for phase in plan.phases:
        phase_points = [
            (marker.x * width, marker.y * height) for marker in phase.markers
        ]
        points.append(phase_points)

    # Arrows first so markers sit on top.
    for index in range(len(plan.phases)):
        color = PALETTE[index % len(PALETTE)]
        pts = points[index]
        for start, end in zip(pts, pts[1:], strict=False):
            _draw_arrow(draw, start, end, color, line_width)

    for index, phase in enumerate(plan.phases):
        color = PALETTE[index % len(PALETTE)]
        for (x, y), marker in zip(points[index], phase.markers, strict=False):
            _draw_marker(draw, x, y, index + 1, marker.kind, color, radius, font_big)

    # Legend: numbered color chips (text stays in the caption for Arabic).
    legend_x, legend_y = 12, 12
    chip = radius + 8
    pad = 8
    rows = len(plan.phases)
    box_height = rows * (chip + pad) + pad
    draw.rounded_rectangle(
        (legend_x, legend_y, legend_x + chip + 2 * pad, legend_y + box_height),
        radius=10,
        fill=(0, 0, 0, 150),
    )
    for index in range(rows):
        color = PALETTE[index % len(PALETTE)]
        top = legend_y + pad + index * (chip + pad)
        draw.ellipse(
            (legend_x + pad, top, legend_x + pad + chip, top + chip),
            fill=color,
            outline=(255, 255, 255),
            width=2,
        )
        text = str(index + 1)
        try:
            bbox = draw.textbbox((0, 0), text, font=font_leg)
            tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
        except Exception:  # pragma: no cover
            tw, th = chip, chip
        draw.text(
            (legend_x + pad + (chip - tw) / 2, top + (chip - th) / 2 - 2),
            text,
            fill=(255, 255, 255),
            font=font_leg,
        )

    output = io.BytesIO()
    image.save(output, format="PNG", optimize=True)
    return output.getvalue()
