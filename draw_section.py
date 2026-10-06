#!/usr/bin/env python3
"""South-facing urban section through West Village.

The cut is an east-west line at y = 16 m, through the proposed rooms
and the east bar. Looking south, so east (downtown) is on the left.

Horizontal 1:4000, vertical 1:1000 (four times the horizontal), so the
flat river terrace and the downtown heights can be read on one sheet.
Ground is the municipal 1 m contour model. Nearby building heights are
OpenStreetMap (a storey count is taken as 3.2 m). Downtown towers east
of that extract are published architectural heights.
"""

import json
import math
from pathlib import Path

ROOT = Path(__file__).resolve().parent
OSM_PATH = ROOT / "westvillage_context_osm.json"
SVG_PATH = ROOT / "westvillage_section.svg"

LAT0 = 51.0466
LON0 = -114.1000
M_LAT = 111132.954
M_LON = 111132.954 * math.cos(math.radians(LAT0))

CUT_Y = 16.0
# How far south of the cut still reads as the view beyond the section,
# and how far north is kept only as downtown height context.
SOUTH_DEPTH = 450.0
NORTH_DEPTH = 280.0

X0, X1 = -1050.0, 2750.0
Z0, Z1 = 1035.0, 1320.0
H_PPM = 0.25   # 1:4000
V_PPM = 1.00   # 1:1000
ML, MR, MT, MB = 28.0, 22.0, 16.0, 14.0
TITLE_H = 32.0
DRAW_W = (X1 - X0) * H_PPM
DRAW_H = (Z1 - Z0) * V_PPM
SHEET_W = ML + DRAW_W + MR
SHEET_H = MT + DRAW_H + TITLE_H + MB

PAPER = "#f3f0e8"
INK = "#1a1a18"
EARTH = "#c4bfb4"
SECTION = "#1a1a18"
BEYOND = "#8a867e"
NORTH = "#b7b3ab"
SITE = "#e4e0d6"
LABEL = "#3c3a36"

# Published architectural heights, used where the local extract stops.
# Coordinates and roof heights from the published Calgary list.
TOWERS = [
    ("Brookfield Place", 51.04728, -114.06600, 247.0),
    ("The Bow", 51.04793, -114.06188, 237.5),
    ("Telus Sky", 51.04678, -114.06354, 225.4),
    ("Suncor Energy Centre", 51.04793, -114.06460, 215.2),
    ("Eighth Avenue Place", 51.04533, -114.07239, 212.3),
    ("Bankers Hall West", 51.04525, -114.06948, 197.0),
    ("Bankers Hall East", 51.04517, -114.06844, 197.0),
    ("Calgary Tower", 51.044312, -114.063164, 191.0),
    ("Eighth Avenue Place II", 51.045456, -114.073395, 176.7),
    ("West Village Towers", 51.045681, -114.088211, 150.0),
    ("West Village Towers II", 51.045593, -114.086731, 150.0),
    ("Eleven", 51.043392, -114.089256, 138.0),
    ("801 Seventh", 51.046692, -114.07917, 153.0),
    ("Western Canadian Place", 51.045673, -114.077126, 164.0),
    ("TD Canada Trust Tower", 51.046551, -114.070938, 162.0),
]

# 1 m contour crossings of this cut, municipal model. The contours run
# with the valley, so an east-west line meets them only in a few places;
# between samples the terrace is held level.
GROUND = [
    (-1100, 1056),
    (-1000, 1053),
    (-720, 1052),
    (-200, 1052),
    (-160, 1049),
    (2800, 1049),
]

# Proposed envelopes the cut passes through. Plan only — no height
# is given in the drawings, so they are marked on the ground.
PROPOSED = [
    (-52, 16, "ROOMS"),
    (77, 159, ""),
    (214, 282, ""),
    (440, 650, "EAST BAR"),
    (648, 680, "ROTUNDA"),
]


def project(lat, lon):
    return ((lon - LON0) * M_LON, (lat - LAT0) * M_LAT)


def ground_z(x):
    if x <= GROUND[0][0]:
        return GROUND[0][1]
    if x >= GROUND[-1][0]:
        return GROUND[-1][1]
    for (x0, z0), (x1, z1) in zip(GROUND, GROUND[1:]):
        if x0 <= x <= x1:
            t = (x - x0) / (x1 - x0)
            return z0 + t * (z1 - z0)
    return GROUND[-1][1]


def sx(x):
    # Looking south: east is to the left.
    return ML + (X1 - x) * H_PPM


def sz(z):
    return MT + (Z1 - z) * V_PPM


def parse_height(tags):
    raw = tags.get("height") or tags.get("building:height")
    if raw:
        try:
            return float(str(raw).lower().replace("m", "").split(";")[0].strip()), "measured"
        except ValueError:
            pass
    levels = tags.get("building:levels")
    if levels:
        try:
            return float(str(levels).split(";")[0]) * 3.2, "storeys"
        except ValueError:
            pass
    return None, None


def crosses(pts, y):
    xs = []
    for a, b in zip(pts, pts[1:]):
        if (a[1] - y) * (b[1] - y) > 0 or a[1] == b[1]:
            continue
        t = (y - a[1]) / (b[1] - a[1])
        xs.append(a[0] + t * (b[0] - a[0]))
    if len(xs) < 2:
        return None
    return min(xs), max(xs)


def main():
    data = json.loads(OSM_PATH.read_text())
    nodes = {}
    for el in data["elements"]:
        if el["type"] == "node":
            nodes[el["id"]] = (el["lat"], el["lon"])

    cut = []
    beyond = []
    north = []
    for el in data["elements"]:
        if el["type"] != "way":
            continue
        tags = el.get("tags") or {}
        if "building" not in tags:
            continue
        pts = []
        for nid in el.get("nodes", []):
            if nid in nodes:
                pts.append(project(*nodes[nid]))
        if len(pts) < 4:
            continue
        if pts[0] != pts[-1]:
            pts.append(pts[0])
        height, source = parse_height(tags)
        if not height or height < 6:
            continue
        cx = sum(p[0] for p in pts) / len(pts)
        cy = sum(p[1] for p in pts) / len(pts)
        if not (X0 - 20 <= cx <= X1 + 20):
            continue
        span = crosses(pts, CUT_Y)
        name = tags.get("name") or ""
        if span and span[1] - span[0] > 3:
            cut.append((span[0], span[1], height, name, source))
        elif CUT_Y - SOUTH_DEPTH <= cy < CUT_Y:
            beyond.append((cx, height, name, source))
        elif CUT_Y < cy <= CUT_Y + NORTH_DEPTH:
            north.append((cx, height, name, source))

    parts = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{SHEET_W:.2f}mm" height="{SHEET_H:.2f}mm" '
        f'viewBox="0 0 {SHEET_W:.2f} {SHEET_H:.2f}">',
        f'<rect width="{SHEET_W:.2f}" height="{SHEET_H:.2f}" fill="{PAPER}"/>',
    ]

    def line(x0, z0, x1, z1, stroke, sw, dash=None):
        extra = f' stroke-dasharray="{dash}"' if dash else ""
        parts.append(
            f'<line x1="{sx(x0):.2f}" y1="{sz(z0):.2f}" x2="{sx(x1):.2f}" y2="{sz(z1):.2f}" '
            f'stroke="{stroke}" stroke-width="{sw}"{extra}/>'
        )

    def rect_xz(xa, xb, za, zb, fill, stroke="none", sw=0):
        x = sx(max(xa, xb))
        w = abs(xb - xa) * H_PPM
        y = sz(max(za, zb))
        h = abs(zb - za) * V_PPM
        parts.append(
            f'<rect x="{x:.2f}" y="{y:.2f}" width="{w:.2f}" height="{h:.2f}" '
            f'fill="{fill}" stroke="{stroke}" stroke-width="{sw}"/>'
        )

    def text(x, z, s, size=2.2, anchor="middle", fill=LABEL, ang=0):
        extra = f' transform="rotate({ang} {sx(x):.2f} {sz(z):.2f})"' if ang else ""
        parts.append(
            f'<text x="{sx(x):.2f}" y="{sz(z):.2f}" fill="{fill}" font-family="Helvetica, Arial, sans-serif" '
            f'font-size="{size}" text-anchor="{anchor}" letter-spacing="0.12"{extra}>{s}</text>'
        )

    # Site terrace, between Crowchild and 11 Street.
    rect_xz(-660, 650, Z0, ground_z(0) + 0.4, SITE)

    # Ground profile.
    gpts = []
    x = X0
    while x <= X1:
        gpts.append((x, ground_z(x)))
        x += 40
    gpts.append((X1, ground_z(X1)))
    d = "M " + " L ".join(f"{sx(x):.2f},{sz(z):.2f}" for x, z in gpts)
    d += f" L {sx(X1):.2f},{sz(Z0):.2f} L {sx(X0):.2f},{sz(Z0):.2f} Z"
    parts.append(f'<path d="{d}" fill="{EARTH}" stroke="none"/>')
    d2 = "M " + " L ".join(f"{sx(x):.2f},{sz(z):.2f}" for x, z in gpts)
    parts.append(f'<path d="{d2}" fill="none" stroke="{INK}" stroke-width="0.35"/>')

    # Downtown towers north of the cut: outline, so they read as context
    # rather than as part of the view.
    for name, lat, lon, h in TOWERS:
        x, y = project(lat, lon)
        if not (X0 < x < X1):
            continue
        if y >= CUT_Y:
            kind = "north"
        elif CUT_Y - y <= SOUTH_DEPTH:
            kind = "beyond"
        else:
            continue
        gz = ground_z(x)
        width = 28 if h >= 180 else 22
        stroke = NORTH if kind == "north" else BEYOND
        rect_xz(x - width / 2, x + width / 2, gz, gz + h, "none", stroke, 0.35)
        if h >= 170:
            text(x, gz + h + 8, name.upper(), size=2.0, ang=-90, anchor="start")

    def draw_mass(x, h, name, fill):
        gz = ground_z(x)
        rect_xz(x - 8, x + 8, gz, gz + h, fill)

    # Beyond the cut, looking south.
    for x, h, name, source in beyond:
        if h < 18:
            continue
        draw_mass(x, h, name, BEYOND)
    # On the cut.
    for xa, xb, h, name, source in cut:
        gz = ground_z((xa + xb) / 2)
        rect_xz(xa, xb, gz, gz + h, SECTION)

    # Proposed envelopes, plan position only.
    gz = ground_z(0)
    for xa, xb, label in PROPOSED:
        line(xa, gz, xb, gz, INK, 1.1)
        if label:
            text((xa + xb) / 2, gz - 6, label, size=2.0)

    # Elevation ticks.
    for z in range(1040, 1321, 20):
        parts.append(
            f'<line x1="{ML - 1:.2f}" y1="{sz(z):.2f}" x2="{ML - 4:.2f}" y2="{sz(z):.2f}" '
            f'stroke="{LABEL}" stroke-width="0.2"/>'
        )
        if z % 40 == 0:
            parts.append(
                f'<text x="{ML - 5.2:.2f}" y="{sz(z) + 0.7:.2f}" fill="{LABEL}" '
                f'font-family="Helvetica, Arial, sans-serif" font-size="2.0" text-anchor="end">{z}</text>'
            )

    # Station labels along the ground.
    for x, label in (
        (-900, "CROWCHILD"),
        (370, "14 STREET"),
        (780, "11 STREET"),
        (2000, "DOWNTOWN"),
    ):
        text(x, ground_z(x) - 14, label, size=2.1)

    # Title.
    ty = MT + DRAW_H + 8
    parts.append(
        f'<text x="{ML:.2f}" y="{ty:.2f}" fill="{INK}" font-family="Helvetica, Arial, sans-serif" '
        f'font-size="4.2" letter-spacing="0.4">WEST VILLAGE</text>'
    )
    parts.append(
        f'<text x="{ML:.2f}" y="{ty + 5.2:.2f}" fill="{LABEL}" font-family="Helvetica, Arial, sans-serif" '
        f'font-size="2.3" letter-spacing="0.18">SECTION LOOKING SOUTH  ·  EAST TO THE LEFT</text>'
    )
    parts.append(
        f'<text x="{ML:.2f}" y="{ty + 9.2:.2f}" fill="{LABEL}" font-family="Helvetica, Arial, sans-serif" '
        f'font-size="2.0">Cut at the proposed rooms, {CUT_Y:.0f} m north of the local origin. '
        f'Horizontal 1:4000. Vertical 1:1000.</text>'
    )
    parts.append(
        f'<text x="{ML:.2f}" y="{ty + 12.6:.2f}" fill="{LABEL}" font-family="Helvetica, Arial, sans-serif" '
        f'font-size="2.0">Ground from the municipal contours. Black is on the cut. '
        f'Gray is south of the cut. Outlined towers are published heights north of the cut.</text>'
    )
    parts.append(
        f'<text x="{ML:.2f}" y="{ty + 16.0:.2f}" fill="{LABEL}" font-family="Helvetica, Arial, sans-serif" '
        f'font-size="2.0">The proposal is marked on the ground. Its drawings give no building height.</text>'
    )
    parts.append(
        f'<text x="{ML + 620:.2f}" y="{ty + 5.2:.2f}" fill="{LABEL}" font-family="Helvetica, Arial, sans-serif" '
        f'font-size="2.0">Elevations in metres above sea level.</text>'
    )

    parts.append("</svg>")
    SVG_PATH.write_text("\n".join(parts))
    print(f"cut buildings {len(cut)}  beyond {len(beyond)}  north {len(north)}")
    print(f"sheet {SHEET_W:.0f} x {SHEET_H:.0f} mm")
    print("wrote", SVG_PATH)


if __name__ == "__main__":
    main()
