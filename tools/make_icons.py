"""
Generate the application icon (PNG + multi-size ICO) and the combo-box chevrons.

Run this only if you want to change the artwork:
    pip install pillow
    python tools/make_icons.py

The generated files are committed to the repository, so normal builds do
NOT need Pillow.
"""
from pathlib import Path

from PIL import Image, ImageDraw

ASSETS = Path(__file__).resolve().parent.parent / "src" / "bandwidthguard" / "assets"
SIZE = 1024  # draw large, then down-sample for crisp edges


def lerp(a, b, t):
    return tuple(int(a[i] + (b[i] - a[i]) * t) for i in range(3))


def bezier(p0, p1, p2, steps=40):
    """Sample a quadratic Bezier curve."""
    pts = []
    for i in range(steps + 1):
        t = i / steps
        x = (1 - t) ** 2 * p0[0] + 2 * (1 - t) * t * p1[0] + t ** 2 * p2[0]
        y = (1 - t) ** 2 * p0[1] + 2 * (1 - t) * t * p1[1] + t ** 2 * p2[1]
        pts.append((x, y))
    return pts


def build_icon() -> Image.Image:
    img = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))

    # Rounded-square background with a blue -> violet diagonal gradient.
    grad = Image.new("RGBA", (SIZE, SIZE))
    gpx = grad.load()
    c1, c2 = (37, 99, 235), (124, 58, 237)
    for y in range(SIZE):
        for x in range(SIZE):
            gpx[x, y] = lerp(c1, c2, (x + y) / (2 * SIZE)) + (255,)
    mask = Image.new("L", (SIZE, SIZE), 0)
    ImageDraw.Draw(mask).rounded_rectangle((40, 40, SIZE - 40, SIZE - 40), radius=230, fill=255)
    img.paste(grad, (0, 0), mask)

    d = ImageDraw.Draw(img)

    # White shield.
    right = bezier((800, 540), (800, 740), (512, 870))
    left = [(SIZE - x, y) for x, y in reversed(right)]
    shield = [(512, 165), (800, 265)] + right + left + [(224, 265)]
    d.polygon(shield, fill=(255, 255, 255, 255))

    # Download arrow ending on a "limit" bar, drawn in the gradient's blue.
    blue = (37, 99, 235, 255)
    d.rectangle((470, 330, 554, 520), fill=blue)
    d.polygon([(365, 510), (659, 510), (512, 665)], fill=blue)
    d.rounded_rectangle((372, 705, 652, 755), radius=25, fill=blue)
    return img


def build_chevron(color) -> Image.Image:
    big = 96
    img = Image.new("RGBA", (big, big), (0, 0, 0, 0))
    ImageDraw.Draw(img).line([(20, 34), (48, 62), (76, 34)], fill=color, width=10, joint="curve")
    return img.resize((24, 24), Image.LANCZOS)


def main():
    ASSETS.mkdir(parents=True, exist_ok=True)
    icon = build_icon()
    icon.resize((256, 256), Image.LANCZOS).save(ASSETS / "icon.png")
    icon.save(ASSETS / "icon.ico", sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])
    build_chevron((203, 213, 225, 255)).save(ASSETS / "chevron_dark.png")   # used on the dark theme
    build_chevron((71, 85, 105, 255)).save(ASSETS / "chevron_light.png")    # used on the light theme
    print("Icons written to", ASSETS)


if __name__ == "__main__":
    main()
