"""Generate the landing page's film frame.

The hero needs one beautiful frame to take apart. It has to be something we
have every right to publish, so it is synthesised here rather than licensed or
borrowed: a dusk field, which is also what the fictional film on the landing
page is called.

Deliberately not a photograph. It reads as a frame — 2.39:1, grain, a soft
halation on the light — without pretending to be footage from a real film.

    python scripts/make_landing_still.py
"""

from __future__ import annotations

import math
import random
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "apps" / "web" / "public" / "film"

WIDTH, HEIGHT = 2400, 1004        # 2.39:1, the scope ratio
HORIZON = int(HEIGHT * 0.66)


def lerp(a: tuple[int, int, int], b: tuple[int, int, int], t: float):
    return tuple(round(a[i] + (b[i] - a[i]) * t) for i in range(3))


def sky(image: Image.Image) -> None:
    """A dusk gradient: cold at the top, warm where the sun has just gone."""
    draw = ImageDraw.Draw(image)
    top = (18, 24, 38)
    mid = (58, 52, 66)
    low = (176, 118, 74)

    for y in range(HORIZON):
        t = y / HORIZON
        colour = lerp(top, mid, min(1.0, t * 1.5)) if t < 0.66 else lerp(
            mid, low, (t - 0.66) / 0.34
        )
        draw.line([(0, y), (WIDTH, y)], fill=colour)


def glow(image: Image.Image) -> Image.Image:
    """Halation around the sun. Bloom is what makes a frame read as film."""
    layer = Image.new("RGB", (WIDTH, HEIGHT), (0, 0, 0))
    draw = ImageDraw.Draw(layer)
    cx, cy = int(WIDTH * 0.62), int(HORIZON - HEIGHT * 0.02)

    for radius, value in ((420, 40), (300, 70), (190, 120), (110, 190), (54, 255)):
        draw.ellipse(
            [cx - radius, cy - radius * 0.55, cx + radius, cy + radius * 0.55],
            fill=(value, int(value * 0.72), int(value * 0.42)),
        )

    layer = layer.filter(ImageFilter.GaussianBlur(70))
    return Image.blend(image, Image.blend(image, layer, 0.0), 0.0) if False else \
        Image.fromarray(
            __import__("numpy").clip(
                __import__("numpy").asarray(image, dtype=int)
                + __import__("numpy").asarray(layer, dtype=int),
                0, 255,
            ).astype("uint8")
        )


def ground(image: Image.Image) -> None:
    """The field itself, and a treeline holding the horizon."""
    draw = ImageDraw.Draw(image)
    near = (10, 12, 14)
    far = (44, 40, 38)

    for y in range(HORIZON, HEIGHT):
        t = (y - HORIZON) / (HEIGHT - HORIZON)
        draw.line([(0, y), (WIDTH, y)], fill=lerp(far, near, t ** 0.6))

    # A ragged treeline, drawn as overlapping silhouettes rather than a curve,
    # so the horizon has texture instead of a drawn edge.
    rng = random.Random(7)
    points = [(0, HORIZON)]
    x = 0
    while x < WIDTH:
        step = rng.randint(18, 70)
        height = rng.randint(4, 26) + int(10 * math.sin(x / 260))
        points.append((x, HORIZON - height))
        x += step
    points.append((WIDTH, HORIZON))
    points.append((WIDTH, HEIGHT))
    points.append((0, HEIGHT))
    draw.polygon(points, fill=(13, 15, 17))

    # Grass, thinning towards the horizon.
    for _ in range(2600):
        gx = rng.randint(0, WIDTH)
        gy = rng.randint(HORIZON + 6, HEIGHT)
        depth = (gy - HORIZON) / (HEIGHT - HORIZON)
        length = int(3 + depth * 22)
        shade = int(26 + depth * 22)
        draw.line(
            [(gx, gy), (gx + rng.randint(-3, 3), gy - length)],
            fill=(shade, shade + 3, shade - 2),
        )


def grain(image: Image.Image, amount: int = 9) -> Image.Image:
    """Film grain. Without it the frame looks rendered, because it is."""
    import numpy as np

    array = np.asarray(image, dtype=np.int16)
    noise = np.random.default_rng(11).normal(0, amount, array.shape)
    return Image.fromarray(np.clip(array + noise, 0, 255).astype("uint8"))


def vignette(image: Image.Image) -> Image.Image:
    import numpy as np

    ys, xs = np.mgrid[0:HEIGHT, 0:WIDTH]
    cx, cy = WIDTH / 2, HEIGHT / 2
    distance = np.sqrt(((xs - cx) / cx) ** 2 + ((ys - cy) / cy) ** 2)
    mask = np.clip(1.06 - 0.42 * distance ** 2.1, 0.35, 1.0)[..., None]
    array = np.asarray(image, dtype=np.float32) * mask
    return Image.fromarray(np.clip(array, 0, 255).astype("uint8"))


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)

    frame = Image.new("RGB", (WIDTH, HEIGHT), (0, 0, 0))
    sky(frame)
    frame = glow(frame)
    ground(frame)
    frame = vignette(frame)
    frame = grain(frame)

    full = OUT / "still.jpg"
    frame.save(full, "JPEG", quality=88, optimize=True, progressive=True)

    # A small copy for the initial paint, so the hero has something on screen
    # before the full frame arrives.
    frame.resize((640, 268), Image.LANCZOS).save(
        OUT / "still-small.jpg", "JPEG", quality=62, optimize=True
    )

    print(f"{full}  {full.stat().st_size / 1024:.0f} KB")
    print(f"{OUT / 'still-small.jpg'}")


if __name__ == "__main__":
    main()
