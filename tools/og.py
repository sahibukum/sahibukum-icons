#!/usr/bin/env python3
"""Draw the share images for the set: dist/og.png (1200x630, link previews) and
dist/social.png (1280x640, the GitHub repository's social preview).

Run after build.py:  python3 tools/og.py
The icons come from dist/SahibukumIcons.ttf; the words are set in Avenir Next (macOS),
falling back to Helvetica Neue.
"""

import json
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent.parent
DIST = ROOT / "dist"

BG = (4, 8, 8)            # gallery black
INK = (240, 234, 220)     # ivory
MUTED = (150, 160, 156)
GOLD = (232, 190, 98)
LINE = (28, 38, 36)

# The prayer day first, then the icons that say what the set is for.
HERO = ["fajr", "sunrise", "dhuhr", "asr", "maghrib", "isha"]
FIELD = [
    "adhan", "mosque", "mihrab", "prayer_mat", "qibla", "quran",
    "mushaf", "dua", "counter", "names", "crescent", "lantern",
    "moon_half", "hijri", "fast", "charity", "halal_scan", "scroll",
]


def face(weight):
    """Avenir Next in the given weight, else Helvetica Neue, else PIL's default."""
    for path, names in (
        ("/System/Library/Fonts/Avenir Next.ttc", {"bold": "Bold", "medium": "Medium", "regular": "Regular"}),
        ("/System/Library/Fonts/HelveticaNeue.ttc", {"bold": "Bold", "medium": "Medium", "regular": "Regular"}),
    ):
        if not Path(path).exists():
            continue
        for i in range(16):
            try:
                f = ImageFont.truetype(path, 10, index=i)
            except OSError:
                break
            if f.getname()[1] == names[weight]:
                return lambda size, p=path, i=i: ImageFont.truetype(p, size, index=i)
    return lambda size: ImageFont.load_default(size)


def draw(width, height, out):
    cat = json.loads((DIST / "icons.json").read_text())
    cp = {i["name"]: int(i["codepoint"], 16) for i in cat["icons"]}
    icon = lambda size: ImageFont.truetype(str(DIST / "SahibukumIcons.ttf"), size)

    s = width / 1200  # everything is laid out on 1200 wide, then scaled
    img = Image.new("RGB", (width, height), BG)
    d = ImageDraw.Draw(img)
    bold, medium, regular = face("bold"), face("medium"), face("regular")

    pad = round(72 * s)

    # Words, left.
    y = round(86 * s)
    d.text((pad, y), "SAHIBUKUM ICONS", font=medium(round(20 * s)), fill=GOLD, spacing=0)
    y += round(48 * s)
    h1 = bold(round(64 * s))
    for line in ("Islamic icons", "for apps and", "websites"):
        d.text((pad, y), line, font=h1, fill=INK)
        y += round(72 * s)
    y += round(18 * s)
    sub = regular(round(24 * s))
    d.text((pad, y), f"{len(cat['icons'])} icons, one hand. SVG, web font, Flutter.", font=sub, fill=MUTED)
    y += round(36 * s)
    d.text((pad, y), "Free with credit under CC BY 4.0.", font=sub, fill=MUTED)
    d.text((pad, height - round(70 * s)), "sahibukum.com/developers/icons", font=medium(round(22 * s)), fill=INK)

    # Icons, right: the six prayers large, then a quieter field.
    x0 = round(700 * s)
    cell = round(76 * s)
    big = icon(round(52 * s))
    for k, name in enumerate(HERO):
        cx = x0 + (k % 3) * cell * 1.42
        cy = round(110 * s) + (k // 3) * cell * 1.3
        d.text((cx, cy), chr(cp[name]), font=big, fill=GOLD)
    d.line((x0, round(330 * s), width - pad, round(330 * s)), fill=LINE, width=max(1, round(2 * s)))
    small = icon(round(34 * s))
    for k, name in enumerate(FIELD):
        cx = x0 + (k % 6) * cell * 0.7
        cy = round(366 * s) + (k // 6) * cell * 0.72
        d.text((cx, cy), chr(cp[name]), font=small, fill=GOLD if k % 3 == 0 else INK)

    img.save(out, optimize=True)
    print(f"wrote {out.relative_to(ROOT)} ({width}x{height})")


if __name__ == "__main__":
    draw(1200, 630, DIST / "og.png")
    draw(1280, 640, DIST / "social.png")
