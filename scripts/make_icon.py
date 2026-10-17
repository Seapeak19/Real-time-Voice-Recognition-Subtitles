"""Generate the SubLoom app icon and a small-size preview sheet.

Run from the repository root:
    python scripts/make_icon.py

Requires Pillow (dev extra).
"""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parent.parent
ASSETS = ROOT / "src" / "subloom" / "assets"

VIOLET = (155, 108, 255)
PINK = (255, 79, 154)
LIME = (216, 255, 62)
INK = (7, 7, 11)
WHITE = (250, 248, 255)

SCALE = 4
SIZE = 512 * SCALE


def _rgb(c1: tuple[int, int, int], c2: tuple[int, int, int], t: float) -> tuple[int, int, int, int]:
    t = max(0.0, min(1.0, t))
    return (
        int(c1[0] + (c2[0] - c1[0]) * t),
        int(c1[1] + (c2[1] - c1[1]) * t),
        int(c1[2] + (c2[2] - c1[2]) * t),
        255,
    )


def _diagonal_gradient(
    box: tuple[int, int, int, int],
    colors: list[tuple[float, tuple[int, int, int]]],
) -> Image.Image:
    """Create a diagonal multi-stop gradient clipped to a rounded rectangle."""
    box = tuple(int(round(value)) for value in box)
    left, top, right, bottom = box
    width, height = right - left, bottom - top
    layer = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    pixels = layer.load()
    for y in range(height):
        for x in range(width):
            t = (x + y) / max(1, width + height - 2)
            for index in range(len(colors) - 1):
                start_t, start_color = colors[index]
                end_t, end_color = colors[index + 1]
                if start_t <= t <= end_t or index == len(colors) - 2:
                    local = (t - start_t) / max(0.0001, end_t - start_t)
                    pixels[x, y] = _rgb(start_color, end_color, local)
                    break
    return layer


def _rounded(image: Image.Image, box: tuple[int, int, int, int], radius: int) -> Image.Image:
    mask = Image.new("L", image.size, 0)
    ImageDraw.Draw(mask).rounded_rectangle(box, radius=radius, fill=255)
    result = Image.new("RGBA", image.size, (0, 0, 0, 0))
    result.paste(image, (0, 0), mask)
    return result


def _fill_rounded(
    canvas: Image.Image,
    box: tuple[int, int, int, int],
    radius: int,
    colors: list[tuple[float, tuple[int, int, int]]],
) -> None:
    box = tuple(int(round(value)) for value in box)
    radius = int(round(radius))
    gradient = _diagonal_gradient(box, colors)
    shape = _rounded(gradient, (0, 0, gradient.width - 1, gradient.height - 1), radius)
    canvas.alpha_composite(shape, (box[0], box[1]))


def _bubble(
    canvas: Image.Image,
    box: tuple[int, int, int, int],
    radius: int,
    colors: list[tuple[float, tuple[int, int, int]]],
    tail: list[tuple[int, int]] | None = None,
) -> None:
    _fill_rounded(canvas, box, radius, colors)
    if tail:
        # The tail is a simple triangle attached to the lower-left corner.
        layer = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
        points = [(int(round(x)), int(round(y))) for x, y in tail]
        ImageDraw.Draw(layer).polygon(points, fill=(*colors[-1][1], 255))
        canvas.alpha_composite(layer)


def draw_icon() -> Image.Image:
    canvas = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
    u = SIZE / 512

    # Dark squircle with a neon gradient border.
    _fill_rounded(
        canvas,
        (16 * u, 16 * u, 496 * u, 496 * u),
        int(136 * u),
        [(0.0, VIOLET), (0.52, PINK), (1.0, LIME)],
    )
    _fill_rounded(
        canvas,
        (26 * u, 26 * u, 486 * u, 486 * u),
        int(128 * u),
        [(0.0, (26, 18, 44)), (0.55, (12, 9, 20)), (1.0, (8, 7, 12))],
    )

    # Back bubble: a second language / conversation.
    _bubble(
        canvas,
        (92 * u, 84 * u, 342 * u, 284 * u),
        int(58 * u),
        [(0.0, VIOLET), (1.0, PINK)],
        [(112 * u, 270 * u), (86 * u, 338 * u), (174 * u, 286 * u)],
    )
    back = ImageDraw.Draw(canvas)
    back.rounded_rectangle(
        (130 * u, 148 * u, 286 * u, 170 * u), radius=int(11 * u), fill=(250, 248, 255, 225)
    )
    back.rounded_rectangle(
        (130 * u, 192 * u, 240 * u, 214 * u), radius=int(11 * u), fill=(250, 248, 255, 155)
    )

    # Front bubble: the translated subtitle.
    _bubble(
        canvas,
        (176 * u, 208 * u, 428 * u, 402 * u),
        int(62 * u),
        [(0.0, (235, 255, 125)), (1.0, LIME)],
        [(224 * u, 392 * u), (190 * u, 452 * u), (286 * u, 400 * u)],
    )
    front = ImageDraw.Draw(canvas)
    front.rounded_rectangle(
        (216 * u, 268 * u, 374 * u, 294 * u), radius=int(13 * u), fill=(*INK, 255)
    )
    front.rounded_rectangle(
        (216 * u, 324 * u, 318 * u, 350 * u), radius=int(13 * u), fill=(*INK, 255)
    )

    # Small spark for the "live" energy.
    cx, cy, r = 410 * u, 112 * u, 25 * u
    front.polygon(
        [
            (cx, cy - r),
            (cx + 0.28 * r, cy - 0.28 * r),
            (cx + r, cy),
            (cx + 0.28 * r, cy + 0.28 * r),
            (cx, cy + r),
            (cx - 0.28 * r, cy + 0.28 * r),
            (cx - r, cy),
            (cx - 0.28 * r, cy - 0.28 * r),
        ],
        fill=(250, 248, 255, 245),
    )

    return canvas.resize((512, 512), Image.Resampling.LANCZOS)


def draw_preview(icon: Image.Image) -> Image.Image:
    sheet = Image.new("RGBA", (760, 230), (8, 7, 12, 255))
    draw = ImageDraw.Draw(sheet)
    draw.text((24, 18), "SubLoom icon / size check", fill=(216, 255, 62, 255))
    x = 24
    for size in (128, 64, 32, 16):
        thumb = icon.resize((size, size), Image.Resampling.LANCZOS)
        sheet.alpha_composite(thumb, (x, 70))
        draw.text((x, 210), f"{size}px", fill=(154, 147, 181, 255))
        x += size + 30
    # A small "installed app" mock.
    sheet.alpha_composite(icon.resize((96, 96), Image.Resampling.LANCZOS), (560, 72))
    draw.text((560, 210), "app tile", fill=(154, 147, 181, 255))
    return sheet


def main() -> int:
    ASSETS.mkdir(parents=True, exist_ok=True)
    icon = draw_icon()
    icon.save(ASSETS / "icon.png")
    icon.save(
        ASSETS / "icon.ico",
        sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)],
    )
    draw_preview(icon).save(ROOT / "docs" / "_icon-preview.png")
    print(f"Wrote {ASSETS / 'icon.png'}")
    print(f"Wrote {ASSETS / 'icon.ico'}")
    print(f"Wrote {ROOT / 'docs' / '_icon-preview.png'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
