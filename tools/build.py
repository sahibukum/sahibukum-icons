"""Build every format of the Sahibukum icons from icons/*.svg.

The SVGs in icons/ are the only source. Each is drawn on a 24 x 24 grid with a
1.75 px round stroke (see README.md, "Drawing an icon"). This script outlines
them and writes, into dist/:

  svg/<name>.svg        filled outlines in currentColor, for any use
  sahibukum-icons.svg   one sprite: <use href="sahibukum-icons.svg#name">
  SahibukumIcons.ttf    the icon font (Flutter, the device's renderer)
  SahibukumIcons.woff2  the same font for the web
  sahibukum_icons.dart  SahibukumIcons, one const IconData per icon
  icons.json            name, codepoint, category, tags, the outline path
  contact-sheet.png     every icon, to check by eye

codepoints.json is append-only: a name keeps its codepoint for ever.

  python3 -m venv .venv && .venv/bin/pip install -r tools/requirements.txt
  .venv/bin/python tools/build.py
"""
import json
import pathlib
import re
import sys
import xml.etree.ElementTree as ET

import pathops
from fontTools.fontBuilder import FontBuilder
from fontTools.pens.cu2quPen import Cu2QuPen
from fontTools.pens.svgPathPen import SVGPathPen
from fontTools.pens.transformPen import TransformPen
from fontTools.pens.ttGlyphPen import TTGlyphPen
from fontTools.svgLib.path import parse_path

ROOT = pathlib.Path(__file__).resolve().parent.parent
SRC, DIST = ROOT / "icons", ROOT / "dist"
META = json.loads((ROOT / "icons.meta.json").read_text())
CODEPOINTS = ROOT / "codepoints.json"
FAMILY, UPM, STROKE, FIRST = "SahibukumIcons", 960, 1.75, 0xE000
SCALE = UPM / 24
NS = "{http://www.w3.org/2000/svg}"


def _circle(cx, cy, r):
    return f"M{cx - r} {cy}A{r} {r} 0 1 0 {cx + r} {cy}A{r} {r} 0 1 0 {cx - r} {cy}Z"


def _rect(x, y, w, h, rx):
    rx = min(rx, w / 2, h / 2)
    if rx <= 0:
        return f"M{x} {y}H{x + w}V{y + h}H{x}Z"
    return (f"M{x + rx} {y}H{x + w - rx}A{rx} {rx} 0 0 1 {x + w} {y + rx}V{y + h - rx}"
            f"A{rx} {rx} 0 0 1 {x + w - rx} {y + h}H{x + rx}A{rx} {rx} 0 0 1 {x} {y + h - rx}"
            f"V{y + rx}A{rx} {rx} 0 0 1 {x + rx} {y}Z")


def element_d(el):
    tag = el.tag.replace(NS, "")
    f = lambda k, d=0.0: float(el.get(k, d))
    if tag == "path":
        return el.get("d")
    if tag == "circle":
        return _circle(f("cx"), f("cy"), f("r"))
    if tag == "ellipse":
        cx, cy, rx, ry = f("cx"), f("cy"), f("rx"), f("ry")
        return f"M{cx - rx} {cy}A{rx} {ry} 0 1 0 {cx + rx} {cy}A{rx} {ry} 0 1 0 {cx - rx} {cy}Z"
    if tag == "rect":
        return _rect(f("x"), f("y"), f("width"), f("height"), f("rx", el.get("ry", 0)))
    if tag == "line":
        return f"M{f('x1')} {f('y1')}L{f('x2')} {f('y2')}"
    raise SystemExit(f"unsupported element <{tag}>")


def outline(svg_path):
    """Strokes expanded and unioned. fill="currentColor" stroke="none" is a
    filled shape; class="solid" is filled and stroked (the filled twin of an
    outline icon); class="cut" is knocked out of the rest; class="over" is
    drawn after the cut (the slash of an off icon)."""
    root = ET.parse(svg_path).getroot()
    parts, cuts, over = [], [], []
    for el in root.iter():
        tag = el.tag.replace(NS, "")
        if tag in ("svg", "g", "title", "desc"):
            continue
        classes = (el.get("class") or "").split()
        d = element_d(el)
        filled = el.get("fill") not in (None, "none") and el.get("stroke") == "none"
        if filled or "solid" in classes:
            p = pathops.Path()
            parse_path(d, p.getPen())
            p.fillType = pathops.FillType.WINDING
            parts.append(p)
        if not filled:
            p = pathops.Path()
            parse_path(d, p.getPen())
            p.stroke(float(el.get("stroke-width", STROKE)), pathops.LineCap.ROUND_CAP,
                     pathops.LineJoin.ROUND_JOIN, 4)
            p.convertConicsToQuads()
            (cuts if "cut" in classes else over if "over" in classes else parts).append(p)
    out = pathops.Path()
    pathops.union(parts, out.getPen())
    if cuts:
        res = pathops.Path()
        pathops.difference([out], cuts, res.getPen())
        out = res
    if over:
        res = pathops.Path()
        pathops.union([out] + over, res.getPen())
        out = res
    return out


def svg_d(path):
    pen = SVGPathPen(None, ntos=lambda v: f"{v:.2f}".rstrip("0").rstrip("."))
    path.draw(pen)
    return pen.getCommands()


def codepoints(names):
    table = json.loads(CODEPOINTS.read_text()) if CODEPOINTS.exists() else {}
    gone = sorted(set(table) - set(names))
    if gone:
        raise SystemExit(f"codepoints.json names icons no longer drawn: {', '.join(gone)}")
    nxt = max([int(v, 16) for v in table.values()] + [FIRST - 1]) + 1
    for name in names:
        if name not in table:
            table[name] = f"{nxt:04X}"
            nxt += 1
    CODEPOINTS.write_text(json.dumps(dict(sorted(table.items(), key=lambda kv: kv[1])), indent=2) + "\n")
    return {k: int(v, 16) for k, v in table.items()}


def camel(name):
    head, *rest = name.split("_")
    return head + "".join(w[:1].upper() + w[1:] for w in rest)


def main():
    names = sorted(p.stem for p in SRC.glob("*.svg"))
    for name in names:
        if not re.fullmatch(r"[a-z][a-z0-9_]*", name):
            raise SystemExit(f"{name}: names are lower_snake_case")
    missing = [n for n in names if n not in META["icons"]]
    if missing:
        raise SystemExit(f"no entry in icons.meta.json for: {', '.join(missing)}")
    cps = codepoints(names)
    paths = {n: outline(SRC / f"{n}.svg") for n in names}

    (DIST / "svg").mkdir(parents=True, exist_ok=True)
    for old in (DIST / "svg").glob("*.svg"):
        old.unlink()
    ds = {n: svg_d(p) for n, p in paths.items()}
    for n in names:
        (DIST / "svg" / f"{n}.svg").write_text(
            '<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" '
            f'fill="currentColor"><path d="{ds[n]}"/></svg>\n')
    (DIST / "sahibukum-icons.svg").write_text(
        '<svg xmlns="http://www.w3.org/2000/svg">\n'
        + "".join(f'<symbol id="{n}" viewBox="0 0 24 24"><path d="{ds[n]}"/></symbol>\n' for n in names)
        + "</svg>\n")

    order = [".notdef"] + sorted(names, key=lambda n: cps[n])
    glyphs = {".notdef": TTGlyphPen(None).glyph()}
    for n in names:
        pen = TTGlyphPen(None)
        paths[n].draw(TransformPen(Cu2QuPen(pen, max_err=0.5, reverse_direction=True),
                                   (SCALE, 0, 0, -SCALE, 0, UPM)))
        glyphs[n] = pen.glyph()
    fb = FontBuilder(UPM, isTTF=True)
    fb.setupGlyphOrder(order)
    fb.setupCharacterMap({cps[n]: n for n in names})
    fb.setupGlyf(glyphs)
    fb.setupHorizontalMetrics({g: (UPM, 0) for g in order})
    fb.setupHorizontalHeader(ascent=UPM, descent=0)
    fb.setupNameTable({"familyName": FAMILY, "styleName": "Regular",
                       "copyright": "Sahibukum Icons (c) 2026 Sahibukum Pte. Ltd. CC BY 4.0"})
    fb.setupOS2(sTypoAscender=UPM, sTypoDescender=0, sTypoLineGap=0, usWinAscent=UPM, usWinDescent=0)
    fb.setupPost()
    fb.save(str(DIST / f"{FAMILY}.ttf"))
    fb.font.flavor = "woff2"
    fb.save(str(DIST / f"{FAMILY}.woff2"))

    mirrored = set(META.get("mirrored", []))
    lines = ["// GENERATED by sahibukum-icons tools/build.py from icons/*.svg. Do not edit.",
             "// Sahibukum Icons, CC BY 4.0: https://sahibukum.com/developers/icons", "",
             "import 'package:flutter/widgets.dart';", "",
             "/// Sahibukum Icons: one drawn set for the app, the device and the web.",
             "abstract final class SahibukumIcons {",
             f"  static const String _family = '{FAMILY}';", ""]
    for n in names:
        md = ", matchTextDirection: true" if n in mirrored else ""
        lines.append(f"  /// {META['icons'][n]['title']}")
        lines.append(f"  static const IconData {camel(n)} =\n      IconData(0x{cps[n]:04X}, fontFamily: _family{md});")
    lines.append("}")
    (DIST / "sahibukum_icons.dart").write_text("\n".join(lines) + "\n")

    (DIST / "icons.json").write_text(json.dumps({
        "name": "Sahibukum Icons", "version": META["version"], "licence": "CC-BY-4.0",
        "attribution": META["attribution"], "grid": 24, "stroke": STROKE,
        "categories": META["categories"],
        "icons": [{"name": n, "codepoint": f"{cps[n]:04X}", **META["icons"][n],
                   "mirrored": n in mirrored, "path": ds[n]} for n in names],
    }, indent=1, ensure_ascii=False) + "\n")

    if "--no-sheet" not in sys.argv:
        from PIL import Image, ImageDraw, ImageFont
        cols, cell = 12, 128
        cats = META["categories"]
        ordered = [n for c in cats for n in names if META["icons"][n]["category"] == c["id"]]
        img = Image.new("RGB", (cols * cell, ((len(ordered) + cols - 1) // cols) * cell), "#061513")
        draw = ImageDraw.Draw(img)
        font = ImageFont.truetype(str(DIST / f"{FAMILY}.ttf"), 40)
        small = ImageFont.truetype(str(DIST / f"{FAMILY}.ttf"), 24)
        label = ImageFont.load_default(12)
        for i, n in enumerate(ordered):
            x, y = (i % cols) * cell, (i // cols) * cell
            draw.rectangle([x, y, x + cell - 1, y + cell - 1], outline="#22332F")
            draw.text((x + 28, y + 26), chr(cps[n]), font=font, fill="#E8BE62")
            draw.text((x + 82, y + 34), chr(cps[n]), font=small, fill="#E8BE62")
            t = n if len(n) <= 18 else n[:17] + "."
            w = draw.textlength(t, font=label)
            draw.text((x + (cell - w) / 2, y + cell - 24), t, font=label, fill="#A3ADA9")
        img.save(DIST / "contact-sheet.png")
    print(f"{len(names)} icons -> {DIST}")


if __name__ == "__main__":
    main()
