# SPDX-License-Identifier: Apache-2.0
"""Sharewerk's app sign, built by the rules of the Azentrius Design System.

The sign: two stacked cards (a carousel) with an arrow leaving the front card
(passing it on), and the dot of the wordmark on the baseline to the right,
the same size as in Lautwerk and Stellwerk.

Rules followed (design system, section "Android", "App-Symbol"):
- 108 x 108 dp grid, only the inner 72 dp are visible, the sign stays inside
  the circle of 66 dp diameter around the centre (safe zone, radius 33 dp)
- the sign in brand-gold on brand-ink, nothing else; no shadow, no gradient
- cut-outs are real holes (fill rule evenodd), so they survive in the
  monochrome layer and in the notification icon
- dot radius 4.120 dp, as in Lautwerk and Stellwerk

Usage: python scripts/app-icon-sharewerk.py [OUTPUT_DIR]   (default: app/static/icons)
Needs: pip install shapely pillow
"""

from __future__ import annotations

import sys
from pathlib import Path

from PIL import Image, ImageDraw
from shapely import affinity
from shapely.geometry import LineString, MultiPolygon, Point, Polygon, box
from shapely.ops import unary_union

BRAND_GOLD = "#C8A96E"
BRAND_INK = "#0A0A0F"
PREVIEW_INK = "#151515"  # notification preview colour, as in the design system
SAFE_RADIUS = 33.0
DOT_RADIUS = 4.120
QUAD = 24  # segments per quarter circle


def rounded_rect(x0: float, y0: float, x1: float, y1: float, r: float) -> Polygon:
    return box(x0 + r, y0 + r, x1 - r, y1 - r).buffer(r, quad_segs=QUAD)


def build_sign() -> MultiPolygon:
    front = rounded_rect(31, 41, 61, 79, 5)
    back = rounded_rect(40, 32, 69, 69, 5)
    gap = 3.0
    back_visible = back.difference(front.buffer(gap, quad_segs=QUAD))

    # Arrow "up and to the right", cut out of the front card.
    stroke = 4.2
    tip = (52.5, 53.5)
    shaft = LineString([(39.5, 66.5), tip])
    arm_left = LineString([(44.0, 53.5), tip])
    arm_down = LineString([tip, (52.5, 62.0)])
    arrow = unary_union([g.buffer(stroke / 2, quad_segs=QUAD) for g in (shaft, arm_left, arm_down)])
    front_cut = front.difference(arrow)

    dot = Point(61 + gap + DOT_RADIUS, 79 - DOT_RADIUS).buffer(DOT_RADIUS, quad_segs=QUAD)

    sign = unary_union([back_visible, front_cut, dot])
    # Centre the sign's bounding box in the 108 grid.
    minx, miny, maxx, maxy = sign.bounds
    sign = affinity.translate(sign, 54 - (minx + maxx) / 2, 54 - (miny + maxy) / 2)
    return sign if isinstance(sign, MultiPolygon) else MultiPolygon([sign])


def check(sign: MultiPolygon) -> dict:
    centre = Point(54, 54)
    radius = max(centre.distance(Point(c)) for poly in sign.geoms for c in poly.exterior.coords)
    minx, miny, maxx, maxy = sign.bounds
    return {"width": maxx - minx, "height": maxy - miny, "max_radius": radius, "inside_safe_zone": radius <= SAFE_RADIUS}


# ------------------------------------------------------------------- output

def ring_path(coords, scale: float = 1.0, dx: float = 0.0, dy: float = 0.0) -> str:
    pts = [(x * scale + dx, y * scale + dy) for x, y in list(coords)[:-1]]
    head = f"M{pts[0][0]:.3f},{pts[0][1]:.3f}"
    return head + "".join(f"L{x:.3f},{y:.3f}" for x, y in pts[1:]) + "Z"


def path_data(sign: MultiPolygon, scale: float = 1.0, dx: float = 0.0, dy: float = 0.0) -> str:
    parts = []
    for poly in sign.geoms:
        parts.append(ring_path(poly.exterior.coords, scale, dx, dy))
        parts.extend(ring_path(i.coords, scale, dx, dy) for i in poly.interiors)
    return "".join(parts)


def svg(view: str, size: int, d: str, fill: str, background: str = "") -> str:
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="{view}" width="{size}" height="{size}">'
        f"{background}<path d=\"{d}\" fill=\"{fill}\" fill-rule=\"evenodd\"></path></svg>"
    )


def notification_transform(sign: MultiPolygon) -> tuple[float, float, float]:
    """Scale so the sign fills 22 dp of a 24 dp icon, 1 dp margin (as in Lautwerk)."""
    minx, miny, maxx, maxy = sign.bounds
    scale = 22 / max(maxx - minx, maxy - miny)
    dx = 12 - (minx + maxx) / 2 * scale
    dy = 12 - (miny + maxy) / 2 * scale
    return scale, dx, dy


def raster(sign: MultiPolygon, size: int, view: tuple[float, float, float], *, background: str | None,
           radius_ratio: float = 0.0, fill: str = BRAND_GOLD) -> Image.Image:
    """Render the sign with 8x supersampling. view = (x0, y0, width) in grid units."""
    ss = 8
    big = size * ss
    x0, y0, w = view
    k = big / w
    img = Image.new("RGBA", (big, big), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    if background:
        draw.rounded_rectangle((0, 0, big - 1, big - 1), radius=int(big * radius_ratio), fill=background)
    mask = Image.new("L", (big, big), 0)
    mdraw = ImageDraw.Draw(mask)
    for poly in sign.geoms:
        mdraw.polygon([((x - x0) * k, (y - y0) * k) for x, y in poly.exterior.coords], fill=255)
        for interior in poly.interiors:
            mdraw.polygon([((x - x0) * k, (y - y0) * k) for x, y in interior.coords], fill=0)
    img.paste(Image.new("RGBA", (big, big), fill), (0, 0), mask)
    return img.resize((size, size), Image.Resampling.LANCZOS)


def main(out: Path) -> None:
    out.mkdir(parents=True, exist_ok=True)
    sign = build_sign()
    info = check(sign)
    print(f"size {info['width']:.1f} x {info['height']:.1f} dp, half diagonal {info['max_radius']:.1f} dp "
          f"(safe zone {SAFE_RADIUS} dp): {'ok' if info['inside_safe_zone'] else 'TOO LARGE'}")
    d = path_data(sign)
    ink = f'<rect x="18" y="18" width="72" height="72" fill="{BRAND_INK}"></rect>'
    ink_round = f'<rect x="18" y="18" width="72" height="72" rx="15.75" fill="{BRAND_INK}"></rect>'

    (out / "sharewerk.svg").write_text(svg("18 18 72 72", 512, d, BRAND_GOLD, ink))
    (out / "sharewerk-foreground.svg").write_text(svg("0 0 108 108", 108, d, BRAND_GOLD))
    (out / "sharewerk-monochrome.svg").write_text(svg("0 0 108 108", 108, d, "#000000"))
    (out / "sharewerk-favicon.svg").write_text(svg("18 18 72 72", 32, d, BRAND_GOLD, ink_round))
    scale, dx, dy = notification_transform(sign)
    (out / "sharewerk-notification.svg").write_text(svg("0 0 24 24", 24, path_data(sign, scale, dx, dy), PREVIEW_INK))

    # PWA icons: "any" like the favicon (ink with rounded corners, inner 72 dp),
    # "maskable" as the full 108 dp grid on ink, so any launcher mask works.
    raster(sign, 192, (18, 18, 72), background=BRAND_INK, radius_ratio=15.75 / 72).save(out / "icon-192.png")
    raster(sign, 512, (18, 18, 72), background=BRAND_INK, radius_ratio=15.75 / 72).save(out / "icon-512.png")
    raster(sign, 512, (0, 0, 108), background=BRAND_INK).save(out / "maskable-512.png")
    print(f"written to {out}")


if __name__ == "__main__":
    main(Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).resolve().parent.parent / "app" / "static" / "icons")
