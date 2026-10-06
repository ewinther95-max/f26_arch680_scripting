#!/usr/bin/env python3
"""West Village proposal — true-scale linework.

Reads the local OSM extract and redraws the site plan in metres:
existing river, rail, streets, and buildings stay in their surveyed
proportions; the proposal (three mandorla rooms, linear bar, rerouted
parkway, riverfront and paths) is resolved onto that base.

Outputs
  westvillage_proposal.svg   sheet at 1:2000, 1 unit = 1 mm
  westvillage_proposal.dxf   model space, 1 unit = 1 metre
"""

import json
import math
from pathlib import Path

ROOT = Path(__file__).resolve().parent
OSM_PATH = ROOT / "westvillage_context_osm.json"
SVG_PATH = ROOT / "westvillage_proposal.svg"
DXF_PATH = ROOT / "westvillage_proposal.dxf"

LAT0 = 51.0466
LON0 = -114.1000
M_LAT = 111132.954
M_LON = 111132.954 * math.cos(math.radians(LAT0))

# Map window, metres, y north.
XMIN, XMAX = -1080.0, 940.0
YMIN, YMAX = -370.0, 440.0

# Sheet. 1:2000 → 0.5 mm per metre.
PPM = 0.5
ML, MT, MR, MB = 18.0, 16.0, 18.0, 14.0
TITLE_H = 42.0
GAP = 6.0
DRAW_W = (XMAX - XMIN) * PPM
DRAW_H = (YMAX - YMIN) * PPM
SHEET_W = ML + DRAW_W + MR
SHEET_H = MT + DRAW_H + GAP + TITLE_H + MB

# Proposal extent along the south bank.
WORK_X0, WORK_X1 = -660.0, 650.0
RETAIN = ("pumphouse", "armoury", "armory", "planetarium", "contemporary")
KEEP_ROADS = {
    "14 Street SW",
    "14 Street NW",
    "Mewata Bridge",
    "Memorial Drive NW",
    "Crowchild Trail SW",
    "Crowchild Trail NW",
    "10 Avenue SW",
    "11 Street SW",
    "11 Avenue SW",
    "12 Avenue SW",
    "Kensington Road NW",
    "Bowness Road NW",
    "Broadview Road NW",
    "5 Avenue SW",
    "6 Avenue SW",
    "8 Avenue SW",
}


def project(lat, lon):
    return ((lon - LON0) * M_LON, (lat - LAT0) * M_LAT)


def to_sheet(x, y):
    return (ML + (x - XMIN) * PPM, MT + (YMAX - y) * PPM)


def hypot(dx, dy):
    return math.hypot(dx, dy)


def sub(a, b):
    return (a[0] - b[0], a[1] - b[1])


def add(a, b):
    return (a[0] + b[0], a[1] + b[1])


def mul(a, s):
    return (a[0] * s, a[1] * s)


def dot(a, b):
    return a[0] * b[0] + a[1] * b[1]


def lerp(a, b, t):
    return (a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t)


def dist(a, b):
    return hypot(b[0] - a[0], b[1] - a[1])


def length(pts):
    return sum(dist(a, b) for a, b in zip(pts, pts[1:]))


def in_window(x, y, pad=0):
    return XMIN - pad <= x <= XMAX + pad and YMIN - pad <= y <= YMAX + pad


def bbox_hits(pts, pad=40):
    xs = [p[0] for p in pts]
    ys = [p[1] for p in pts]
    return not (max(xs) < XMIN - pad or min(xs) > XMAX + pad or max(ys) < YMIN - pad or min(ys) > YMAX + pad)


def simplify(pts, eps):
    if len(pts) < 3:
        return pts
    closed = dist(pts[0], pts[-1]) < 0.05
    core = pts[:-1] if closed else pts

    def dp(p):
        if len(p) < 3:
            return p
        a, b = p[0], p[-1]
        dx, dy = b[0] - a[0], b[1] - a[1]
        mag = hypot(dx, dy) or 1
        maxd, idx = -1, 0
        for i in range(1, len(p) - 1):
            px, py = p[i]
            d = abs(dy * px - dx * py + b[0] * a[1] - b[1] * a[0]) / mag
            if d > maxd:
                maxd, idx = d, i
        if maxd > eps:
            return dp(p[: idx + 1])[:-1] + dp(p[idx:])
        return [p[0], p[-1]]

    out = dp(core)
    if closed:
        out = out + [out[0]]
    return out


def catmull(pts, per=14):
    if len(pts) < 2:
        return list(pts)
    p = [pts[0]] + list(pts) + [pts[-1]]
    out = []
    for i in range(1, len(p) - 2):
        p0, p1, p2, p3 = p[i - 1], p[i], p[i + 1], p[i + 2]
        for s in range(per):
            t = s / per
            t2, t3 = t * t, t * t * t
            x = 0.5 * (
                (2 * p1[0])
                + (-p0[0] + p2[0]) * t
                + (2 * p0[0] - 5 * p1[0] + 4 * p2[0] - p3[0]) * t2
                + (-p0[0] + 3 * p1[0] - 3 * p2[0] + p3[0]) * t3
            )
            y = 0.5 * (
                (2 * p1[1])
                + (-p0[1] + p2[1]) * t
                + (2 * p0[1] - 5 * p1[1] + 4 * p2[1] - p3[1]) * t2
                + (-p0[1] + 3 * p1[1] - 3 * p2[1] + p3[1]) * t3
            )
            out.append((x, y))
    out.append(pts[-1])
    return out


def quad(p0, p1, p2, n=16):
    """Quadratic Bezier. Stays inside the control triangle, so it will not bow backward."""
    out = []
    for i in range(n + 1):
        t = i / n
        o = 1 - t
        out.append(
            (
                o * o * p0[0] + 2 * o * t * p1[0] + t * t * p2[0],
                o * o * p0[1] + 2 * o * t * p1[1] + t * t * p2[1],
            )
        )
    return out


def offset_open(pts, dist):
    """Offset an open polyline. Positive dist is to the left of travel."""
    if len(pts) < 2 or dist == 0:
        return list(pts)
    segs = []
    for i in range(len(pts) - 1):
        dx, dy = pts[i + 1][0] - pts[i][0], pts[i + 1][1] - pts[i][1]
        mag = hypot(dx, dy) or 1
        segs.append((-dy / mag, dx / mag))
    out = []
    for i, p in enumerate(pts):
        if i == 0:
            n = segs[0]
            scale = 1
        elif i == len(pts) - 1:
            n = segs[-1]
            scale = 1
        else:
            n1, n2 = segs[i - 1], segs[i]
            nx, ny = n1[0] + n2[0], n1[1] + n2[1]
            mag = hypot(nx, ny)
            if mag < 1e-6:
                n, scale = n1, 1
            else:
                n = (nx / mag, ny / mag)
                d = n[0] * n1[0] + n[1] * n1[1]
                scale = 1 / max(0.35, d)
                scale = min(scale, 1.45)
        out.append((p[0] + n[0] * dist * scale, p[1] + n[1] * dist * scale))
    return out


def sample_along(pts, spacing):
    if len(pts) < 2:
        return list(pts)
    out = [pts[0]]
    acc = 0
    for a, b in zip(pts, pts[1:]):
        L = dist(a, b)
        if L < 1e-6:
            continue
        while acc + L >= spacing:
            t = (spacing - acc) / L
            a = lerp(a, b, t)
            out.append(a)
            L = dist(a, b)
            acc = 0
        acc += L
    if dist(out[-1], pts[-1]) > spacing * 0.45:
        out.append(pts[-1])
    return out


def break_vertical(pts, gaps):
    """Drop portions of an east-trending polyline whose x falls in any (x0, x1)."""
    runs, cur = [], []
    for p in pts:
        if any(a < p[0] < b for a, b in gaps):
            if len(cur) >= 2:
                runs.append(cur)
            cur = []
        else:
            cur.append(p)
    if len(cur) >= 2:
        runs.append(cur)
    return runs


def rectangle(cx, cy, w, h, ang=0):
    ca, sa = math.cos(ang), math.sin(ang)
    pts = []
    for sx, sy in ((-w / 2, -h / 2), (w / 2, -h / 2), (w / 2, h / 2), (-w / 2, h / 2)):
        pts.append((cx + sx * ca - sy * sa, cy + sx * sa + sy * ca))
    pts.append(pts[0])
    return pts


def circle_poly(cx, cy, r, n=64):
    pts = [
        (cx + r * math.cos(2 * math.pi * i / n), cy + r * math.sin(2 * math.pi * i / n))
        for i in range(n)
    ]
    pts.append(pts[0])
    return pts


def arc_through(center, radius, p0, pm, p1, n):
    def ang(p):
        return math.atan2(p[1] - center[1], p[0] - center[0])

    def ccw(a, b):
        return (b - a) % (2 * math.pi)

    a0, am, a1 = ang(p0), ang(pm), ang(p1)
    if ccw(a0, am) <= ccw(a0, a1) + 1e-4:
        sweep = ccw(a0, a1)
        angs = [a0 + sweep * i / n for i in range(n + 1)]
    else:
        sweep = ccw(a1, a0)
        angs = [a0 - sweep * i / n for i in range(n + 1)]
    return [
        (center[0] + radius * math.cos(a), center[1] + radius * math.sin(a)) for a in angs
    ]


def vesica(cx, cy, length, width, ang, n=36):
    """Pointed mandorla, long axis at ang (radians, CCW from east)."""
    L, W = float(length), float(width)
    R = (L * L + W * W) / (4 * W)
    D = 2 * R - W
    ca, sa = math.cos(ang), math.sin(ang)
    px, py = -sa, ca  # short axis
    c = (cx, cy)
    c1 = (cx - px * D / 2, cy - py * D / 2)
    c2 = (cx + px * D / 2, cy + py * D / 2)
    tip_e = (cx + ca * L / 2, cy + sa * L / 2)
    tip_w = (cx - ca * L / 2, cy - sa * L / 2)
    waist_n = (cx + px * W / 2, cy + py * W / 2)
    waist_s = (cx - px * W / 2, cy - py * W / 2)
    a = arc_through(c1, R, tip_w, waist_n, tip_e, n)
    b = arc_through(c2, R, tip_e, waist_s, tip_w, n)
    return a[:-1] + b[:-1] + [a[0]]


def clip_open(pts, box):
    """Cohen–Sutherland clip of an open polyline. Returns runs inside the box."""
    xmin, ymin, xmax, ymax = box

    def code(x, y):
        c = 0
        if x < xmin:
            c |= 1
        elif x > xmax:
            c |= 2
        if y < ymin:
            c |= 4
        elif y > ymax:
            c |= 8
        return c

    def seg(a, b):
        x0, y0 = a
        x1, y1 = b
        c0, c1 = code(x0, y0), code(x1, y1)
        for _ in range(12):
            if c0 == 0 and c1 == 0:
                return (x0, y0), (x1, y1)
            if c0 & c1:
                return None
            c = c0 or c1
            if c & 8:
                x = x0 + (x1 - x0) * (ymax - y0) / (y1 - y0 or 1e-12)
                y = ymax
            elif c & 4:
                x = x0 + (x1 - x0) * (ymin - y0) / (y1 - y0 or 1e-12)
                y = ymin
            elif c & 2:
                y = y0 + (y1 - y0) * (xmax - x0) / (x1 - x0 or 1e-12)
                x = xmax
            else:
                y = y0 + (y1 - y0) * (xmin - x0) / (x1 - x0 or 1e-12)
                x = xmin
            if c == c0:
                x0, y0, c0 = x, y, code(x, y)
            else:
                x1, y1, c1 = x, y, code(x, y)
        return None

    runs, cur = [], []
    for a, b in zip(pts, pts[1:]):
        hit = seg(a, b)
        if hit is None:
            if len(cur) >= 2:
                runs.append(cur)
            cur = []
            continue
        p, q = hit
        if not cur:
            cur = [p, q]
        elif dist(cur[-1], p) < 0.05:
            cur.append(q)
        else:
            if len(cur) >= 2:
                runs.append(cur)
            cur = [p, q]
    if len(cur) >= 2:
        runs.append(cur)
    return runs


def sutherland(pts, box):
    xmin, ymin, xmax, ymax = box

    def clip_edge(poly, inside, intersect):
        if not poly:
            return []
        out = []
        prev = poly[-1]
        for cur in poly:
            if inside(cur):
                if not inside(prev):
                    out.append(intersect(prev, cur))
                out.append(cur)
            elif inside(prev):
                out.append(intersect(prev, cur))
            prev = cur
        return out

    def ix(a, b, vertical, val):
        if vertical:
            t = (val - a[0]) / (b[0] - a[0] or 1e-12)
            return (val, a[1] + t * (b[1] - a[1]))
        t = (val - a[1]) / (b[1] - a[1] or 1e-12)
        return (a[0] + t * (b[0] - a[0]), val)

    poly = list(pts[:-1] if dist(pts[0], pts[-1]) < 0.05 else pts)
    poly = clip_edge(poly, lambda p: p[0] >= xmin, lambda a, b: ix(a, b, True, xmin))
    poly = clip_edge(poly, lambda p: p[0] <= xmax, lambda a, b: ix(a, b, True, xmax))
    poly = clip_edge(poly, lambda p: p[1] >= ymin, lambda a, b: ix(a, b, False, ymin))
    poly = clip_edge(poly, lambda p: p[1] <= ymax, lambda a, b: ix(a, b, False, ymax))
    if len(poly) < 3:
        return []
    return poly + [poly[0]]


def inside(x, y, poly):
    odd = False
    n = len(poly)
    for i in range(n):
        x1, y1 = poly[i]
        x2, y2 = poly[(i + 1) % n]
        if (y1 > y) != (y2 > y) and x < (x2 - x1) * (y - y1) / (y2 - y1 + 1e-12) + x1:
            odd = not odd
    return odd


class Sheet:
    def __init__(self):
        self.groups = []
        self.dxf = []  # (layer, kind, payload)

    def g(self, name):
        self.groups.append([name, []])
        return self

    def _add(self, svg, layer, kind, payload):
        self.groups[-1][1].append(svg)
        if layer:
            self.dxf.append((layer, kind, payload))

    def poly(self, pts, layer, sw=0.2, stroke="#111", fill="none", closed=False, dash=None, opacity=1):
        if len(pts) < 2:
            return
        clean = []
        for p in pts:
            if not clean or dist(clean[-1], p) > 0.02:
                clean.append(p)
        if len(clean) < 2:
            return
        sm = [to_sheet(*p) for p in clean]
        d = "M " + " L ".join(f"{x:.2f},{y:.2f}" for x, y in sm)
        if closed:
            d += " Z"
        extra = ""
        if dash:
            extra += f' stroke-dasharray="{dash}"'
        if opacity != 1 and fill != "none":
            extra += f' fill-opacity="{opacity}"'
        self._add(
            f'<path d="{d}" fill="{fill}" stroke="{stroke}" stroke-width="{sw:.3f}" '
            f'stroke-linejoin="round" stroke-linecap="round"{extra}/>',
            layer,
            "poly",
            (clean, closed),
        )

    def path_cased(self, pts, layer, sw=0.22, casing=1.05):
        self.poly(pts, None, sw=sw + casing, stroke="#ffffff")
        self.poly(pts, layer, sw=sw, stroke="#111")

    def circle(self, cx, cy, r, layer, sw=0.12, fill="none", stroke="#111"):
        x, y = to_sheet(cx, cy)
        rr = r * PPM
        self._add(
            f'<circle cx="{x:.2f}" cy="{y:.2f}" r="{rr:.2f}" fill="{fill}" stroke="{stroke}" stroke-width="{sw:.3f}"/>',
            layer,
            "circle",
            (cx, cy, r),
        )

    def text(self, x, y, s, size=2.4, ang=0, anchor="middle", layer="A-ANNO", weight="400", family="sans"):
        sx, sy = to_sheet(x, y)
        # World angle (CCW from east, degrees) → SVG rotation (y down).
        rot = -ang
        ff = "Times, 'Times New Roman', serif" if family == "serif" else "Helvetica, Arial, sans-serif"
        self._add(
            f'<text x="{sx:.2f}" y="{sy:.2f}" font-size="{size:.2f}" font-family="{ff}" '
            f'font-weight="{weight}" text-anchor="{anchor}" fill="#161616" '
            f'transform="rotate({rot:.2f} {sx:.2f} {sy:.2f})">{s}</text>',
            layer,
            "text",
            (x, y, s, size / PPM),
        )

    def sheet_text(self, x, y, s, size=3, anchor="start", weight="400", family="sans", tracking=0):
        ff = "Times, 'Times New Roman', serif" if family == "serif" else "Helvetica, Arial, sans-serif"
        ls = f' letter-spacing="{tracking}"' if tracking else ""
        self.groups[-1][1].append(
            f'<text x="{x:.2f}" y="{y:.2f}" font-size="{size:.2f}" font-family="{ff}" '
            f'font-weight="{weight}" text-anchor="{anchor}" fill="#161616"{ls}>{s}</text>'
        )


def load():
    osm = json.loads(OSM_PATH.read_text())
    nodes = {e["id"]: e for e in osm["elements"] if e["type"] == "node"}
    ways = [e for e in osm["elements"] if e["type"] == "way"]
    rels = [e for e in osm["elements"] if e["type"] == "relation"]
    return nodes, ways, rels


def way_xy(nodes, w):
    pts = []
    for nid in w.get("nodes", []):
        n = nodes.get(nid)
        if n:
            pts.append(project(n["lat"], n["lon"]))
    return pts


def chain_banks(nodes, ways, rels):
    ids = {541411390}
    for r in rels:
        t = r.get("tags") or {}
        if t.get("natural") == "water":
            for m in r.get("members", []):
                if m.get("type") == "way" and m.get("role") == "outer":
                    ids.add(m["ref"])
    polys = []
    by_id = {w["id"]: w for w in ways}
    for i in ids:
        w = by_id.get(i)
        if not w:
            continue
        pts = way_xy(nodes, w)
        if len(pts) >= 4 and bbox_hits(pts, 0):
            polys.append(pts)
    return polys


def envelope(polys, xs):
    south, north = [], []
    for x in xs:
        ys = []
        for poly in polys:
            seq = poly
            for (x1, y1), (x2, y2) in zip(seq, seq[1:] + seq[:1]):
                if (x1 <= x < x2) or (x2 <= x < x1):
                    t = (x - x1) / (x2 - x1 or 1e-12)
                    ys.append(y1 + t * (y2 - y1))
        if len(ys) >= 2 and (max(ys) - min(ys)) > 25:
            south.append(min(ys))
            north.append(max(ys))
        else:
            south.append(None)
            north.append(None)

    def fill(vals):
        idx = [i for i, v in enumerate(vals) if v is not None]
        if not idx:
            return vals
        for i in range(len(vals)):
            if vals[i] is not None:
                continue
            prev = max((j for j in idx if j < i), default=None)
            nxt = min((j for j in idx if j > i), default=None)
            if prev is None:
                vals[i] = vals[nxt]
            elif nxt is None:
                vals[i] = vals[prev]
            else:
                t = (i - prev) / (nxt - prev)
                vals[i] = vals[prev] * (1 - t) + vals[nxt] * t
        k = 2
        sm = []
        for i in range(len(vals)):
            sl = [vals[j] for j in range(max(0, i - k), min(len(vals), i + k + 1)) if vals[j] is not None]
            sm.append(sum(sl) / len(sl))
        return sm

    return fill(south), fill(north)


def rail_north(nodes, ways, xs):
    pts = []
    for w in ways:
        t = w.get("tags") or {}
        if t.get("railway") != "rail":
            continue
        for p in way_xy(nodes, w):
            if XMIN - 50 < p[0] < XMAX + 50 and -400 < p[1] < 40:
                pts.append(p)
    ys = []
    for x in xs:
        near = [p[1] for p in pts if abs(p[0] - x) < 45]
        ys.append(max(near) if near else None)
    # fill gaps
    idx = [i for i, v in enumerate(ys) if v is not None]
    for i in range(len(ys)):
        if ys[i] is not None:
            continue
        prev = max((j for j in idx if j < i), default=None)
        nxt = min((j for j in idx if j > i), default=None)
        if prev is None:
            ys[i] = ys[nxt]
        elif nxt is None:
            ys[i] = ys[prev]
        else:
            t = (i - prev) / (nxt - prev)
            ys[i] = ys[prev] * (1 - t) + ys[nxt] * t
    return ys


def sampler(xs, vals):
    def f(x):
        if x <= xs[0]:
            return vals[0]
        if x >= xs[-1]:
            return vals[-1]
        t = (x - xs[0]) / (xs[1] - xs[0])
        i = int(t)
        i = max(0, min(len(xs) - 2, i))
        u = (x - xs[i]) / (xs[i + 1] - xs[i])
        return vals[i] * (1 - u) + vals[i + 1] * u

    return f


def line_of(xs, f, x0, x1, step=8):
    pts = []
    x = x0
    while x <= x1:
        pts.append((x, f(x)))
        x += step
    if pts[-1][0] < x1:
        pts.append((x1, f(x1)))
    return pts


def work_contains(x, y, bank, rail):
    if not (WORK_X0 <= x <= WORK_X1):
        return False
    return (rail(x) + 32) < y < (bank(x) - 6)


def retained(tags):
    name = ((tags.get("name") or "") + " " + (tags.get("addr:street") or "")).lower()
    return any(k in name for k in RETAIN)


def road_weight(tags):
    h = tags.get("highway") or ""
    name = tags.get("name") or ""
    if name in ("14 Street SW", "14 Street NW", "Mewata Bridge") or "Crowchild" in name:
        return 0.34
    if h in ("motorway", "motorway_link", "trunk", "trunk_link"):
        return 0.28
    if h in ("primary", "primary_link", "secondary", "secondary_link"):
        return 0.18
    if h in ("tertiary", "tertiary_link"):
        return 0.13
    return 0.07


def emit_svg(sheet):
    parts = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{SHEET_W:.2f}mm" height="{SHEET_H:.2f}mm" '
        f'viewBox="0 0 {SHEET_W:.2f} {SHEET_H:.2f}">',
        "<defs>",
        f'  <clipPath id="map"><rect x="{ML:.2f}" y="{MT:.2f}" width="{DRAW_W:.2f}" height="{DRAW_H:.2f}"/></clipPath>',
        "</defs>",
        f'<rect width="{SHEET_W:.2f}" height="{SHEET_H:.2f}" fill="#ffffff"/>',
        '<g id="map" clip-path="url(#map)">',
    ]
    title = None
    for name, items in sheet.groups:
        if name == "titleblock":
            title = items
            continue
        parts.append(f'<g id="{name}">')
        parts.extend(items)
        parts.append("</g>")
    parts.append("</g>")
    parts.append('<g id="titleblock">')
    if title:
        parts.extend(title)
    parts.append("</g>")
    parts.append("</svg>")
    SVG_PATH.write_text("\n".join(parts))


def emit_dxf(sheet):
    layers = [
        "A-RIVER",
        "A-RAIL",
        "A-ROAD",
        "A-ROAD-PROP",
        "A-BLDG",
        "A-BLDG-PROP",
        "A-PATH",
        "A-TREE",
        "A-BRIDGE",
        "A-LIMIT",
        "A-ANNO",
    ]
    out = ["0", "SECTION", "2", "HEADER", "9", "$INSUNITS", "70", "6", "0", "ENDSEC"]
    out += ["0", "SECTION", "2", "TABLES", "0", "TABLE", "2", "LAYER", "70", str(len(layers))]
    for name in layers:
        out += ["0", "LAYER", "2", name, "70", "0", "62", "7", "6", "CONTINUOUS"]
    out += ["0", "ENDTAB", "0", "ENDSEC", "0", "SECTION", "2", "ENTITIES"]
    box = (XMIN - 20, YMIN - 160, XMAX + 20, YMAX + 20)
    for layer, kind, payload in sheet.dxf:
        if kind == "poly":
            pts, closed = payload
            if closed:
                clipped = sutherland(pts, (XMIN - 5, YMIN - 5, XMAX + 5, YMAX + 5))
                runs = [clipped] if len(clipped) >= 4 else []
            else:
                runs = clip_open(pts, box)
            for run in runs:
                if len(run) < 2:
                    continue
                out += ["0", "LWPOLYLINE", "8", layer, "90", str(len(run)), "70", "1" if closed else "0"]
                for x, y in run:
                    out += ["10", f"{x:.3f}", "20", f"{y:.3f}"]
        elif kind == "circle":
            cx, cy, r = payload
            if not in_window(cx, cy, 30):
                continue
            out += ["0", "CIRCLE", "8", layer, "10", f"{cx:.3f}", "20", f"{cy:.3f}", "40", f"{r:.3f}"]
        elif kind == "text":
            x, y, s, h = payload
            if not (XMIN - 40 <= x <= XMAX + 40 and YMIN - 180 <= y <= YMAX + 40):
                continue
            out += [
                "0",
                "TEXT",
                "8",
                layer,
                "10",
                f"{x:.3f}",
                "20",
                f"{y:.3f}",
                "40",
                f"{max(h, 2.5):.2f}",
                "1",
                s,
            ]
    out += ["0", "ENDSEC", "0", "EOF"]
    DXF_PATH.write_text("\n".join(out))


def draw_title(sheet, promenade_m):
    sheet.g("titleblock")
    y0 = MT + DRAW_H + GAP
    x0, x1 = ML, ML + DRAW_W
    sheet.groups[-1][1].append(
        f'<line x1="{x0:.2f}" y1="{y0:.2f}" x2="{x1:.2f}" y2="{y0:.2f}" stroke="#111" stroke-width="0.35"/>'
    )
    sheet.groups[-1][1].append(
        f'<rect x="0.6" y="0.6" width="{SHEET_W - 1.2:.2f}" height="{SHEET_H - 1.2:.2f}" '
        f'fill="none" stroke="#111" stroke-width="0.45"/>'
    )
    sheet.groups[-1][1].append(
        f'<rect x="2.2" y="2.2" width="{SHEET_W - 4.4:.2f}" height="{SHEET_H - 4.4:.2f}" '
        f'fill="none" stroke="#111" stroke-width="0.15"/>'
    )
    ty = y0 + 12
    sheet.sheet_text(x0, ty, "WEST VILLAGE", size=7.2, family="serif", tracking=1.6)
    sheet.sheet_text(x0, ty + 6.2, "CALGARY  ·  BOW RIVER", size=2.6, tracking=0.6)
    sheet.sheet_text(x0, ty + 11.4, "PROPOSAL SITE PLAN", size=2.6, tracking=0.8)
    sheet.sheet_text(
        x0,
        ty + 17.2,
        "Riverfront, path network, and Bow Trail rerouted to the measured bank, rail, and street grid.",
        size=2.15,
    )
    sheet.sheet_text(
        x0,
        ty + 21.6,
        f"South-bank promenade drawn {promenade_m:.0f} m.  Solid poche is proposed.  Heavy outline is retained.",
        size=2.15,
    )
    sheet.sheet_text(x0, ty + 26.2, "1 : 2 000", size=3.0, family="serif")
    sheet.sheet_text(x0 + 28, ty + 26.2, "METRES", size=2.3, tracking=0.4)

    # Graphic scale, true at 1:2000. 200 m = 100 mm.
    sx = x0 + 250
    sy = ty + 8
    sheet.sheet_text(sx, sy - 3.2, "0", size=2.0, anchor="middle")
    sheet.sheet_text(sx + 25, sy - 3.2, "50", size=2.0, anchor="middle")
    sheet.sheet_text(sx + 50, sy - 3.2, "100", size=2.0, anchor="middle")
    sheet.sheet_text(sx + 100, sy - 3.2, "200 m", size=2.0, anchor="middle")
    for i, (a, b) in enumerate(((0, 25), (25, 50), (50, 75), (75, 100))):
        fill = "#161616" if i % 2 == 0 else "#ffffff"
        sheet.groups[-1][1].append(
            f'<rect x="{sx + a:.2f}" y="{sy:.2f}" width="{b - a:.2f}" height="3.2" fill="{fill}" stroke="#161616" stroke-width="0.2"/>'
        )

    # Legend
    lx = x0 + 430
    ly = ty + 1
    legends = [
        ("poche", "PROPOSED BUILDING"),
        ("heavy", "RETAINED LANDMARK"),
        ("line", "EXISTING BUILDING"),
        ("road", "REROUTED ROADWAY"),
        ("path", "PEDESTRIAN PATH"),
        ("bank", "RIVER BANK"),
    ]
    for i, (kind, label) in enumerate(legends):
        col = i % 3
        row = i // 3
        px = lx + col * 78
        py = ly + row * 12
        if kind == "poche":
            sheet.groups[-1][1].append(
                f'<rect x="{px:.2f}" y="{py:.2f}" width="7" height="3.4" fill="#161616"/>'
            )
        elif kind == "heavy":
            sheet.groups[-1][1].append(
                f'<rect x="{px:.2f}" y="{py:.2f}" width="7" height="3.4" fill="none" stroke="#161616" stroke-width="0.55"/>'
            )
        elif kind == "line":
            sheet.groups[-1][1].append(
                f'<rect x="{px:.2f}" y="{py:.2f}" width="7" height="3.4" fill="none" stroke="#161616" stroke-width="0.15"/>'
            )
        elif kind == "road":
            sheet.groups[-1][1].append(
                f'<line x1="{px:.2f}" y1="{py + 1.6:.2f}" x2="{px + 7:.2f}" y2="{py + 1.6:.2f}" stroke="#161616" stroke-width="0.55"/>'
            )
        elif kind == "path":
            sheet.groups[-1][1].append(
                f'<line x1="{px:.2f}" y1="{py + 1.6:.2f}" x2="{px + 7:.2f}" y2="{py + 1.6:.2f}" stroke="#161616" stroke-width="0.28"/>'
            )
        else:
            sheet.groups[-1][1].append(
                f'<line x1="{px:.2f}" y1="{py + 1.2:.2f}" x2="{px + 7:.2f}" y2="{py + 1.2:.2f}" stroke="#161616" stroke-width="0.35"/>'
            )
            sheet.groups[-1][1].append(
                f'<line x1="{px:.2f}" y1="{py + 2.6:.2f}" x2="{px + 7:.2f}" y2="{py + 2.6:.2f}" stroke="#161616" stroke-width="0.12"/>'
            )
        sheet.sheet_text(px + 9, py + 2.8, label, size=1.9, tracking=0.15)

    # North arrow — grid north, aligned with 14 Street.
    nx = x1 - 28
    ny = y0 + 28
    sheet.groups[-1][1].append(
        f'<line x1="{nx:.2f}" y1="{ny:.2f}" x2="{nx:.2f}" y2="{ny - 16:.2f}" stroke="#161616" stroke-width="0.35"/>'
    )
    sheet.groups[-1][1].append(
        f'<polygon points="{nx:.2f},{ny - 18:.2f} {nx - 2.3:.2f},{ny - 12:.2f} {nx + 2.3:.2f},{ny - 12:.2f}" fill="#161616"/>'
    )
    sheet.groups[-1][1].append(
        f'<line x1="{nx - 3.2:.2f}" y1="{ny - 6:.2f}" x2="{nx + 3.2:.2f}" y2="{ny - 6:.2f}" stroke="#161616" stroke-width="0.25"/>'
    )
    sheet.sheet_text(nx, ny - 22.5, "N", size=3.4, anchor="middle", family="serif")
    sheet.sheet_text(nx, ny + 4.5, "GRID NORTH", size=1.7, anchor="middle", tracking=0.3)

    sheet.sheet_text(x1, ty + 4, "ARCH 680", size=2.2, anchor="end", tracking=0.6)
    sheet.sheet_text(x1, ty + 9, "SEPTEMBER 2026", size=2.2, anchor="end", tracking=0.4)
    sheet.sheet_text(x1, ty + 14.5, "LOCAL METRE GRID", size=2.0, anchor="end", tracking=0.3)
    sheet.sheet_text(x1, ty + 18.6, "ORIGIN  51.0466° N", size=2.0, anchor="end")
    sheet.sheet_text(x1, ty + 22.6, "114.1000° W", size=2.0, anchor="end")


def main():
    nodes, ways, rels = load()
    xs = []
    x = XMIN - 40
    while x <= XMAX + 40:
        xs.append(x)
        x += 12
    polys = chain_banks(nodes, ways, rels)
    south_v, north_v = envelope(polys, xs)
    rail_v = rail_north(nodes, ways, xs)
    bank = sampler(xs, south_v)
    nbank = sampler(xs, north_v)
    rail = sampler(xs, rail_v)

    print("bank / rail samples")
    for x in range(-1000, 901, 100):
        print(f"  x={x:5}  south {bank(x):6.1f}  north {nbank(x):6.1f}  rail {rail(x):6.1f}")

    sheet = Sheet()
    box = (XMIN, YMIN, XMAX, YMAX)

    # --- river ---
    sheet.g("river")
    for poly in polys:
        clipped = sutherland(simplify(poly, 1.4), (XMIN - 30, YMIN - 30, XMAX + 30, YMAX + 30))
        if len(clipped) >= 4:
            sheet.poly(clipped, "A-RIVER", sw=0.15, fill="#efefef", stroke="#efefef", closed=True)

    def band(frac):
        pts = []
        for x in xs:
            if not (XMIN <= x <= XMAX):
                continue
            s, n = bank(x), nbank(x)
            if n - s < 30:
                continue
            pts.append((x, s + (n - s) * frac))
        return pts

    for frac, sw in ((0.28, 0.06), (0.46, 0.07), (0.64, 0.06), (0.82, 0.05)):
        pts = band(frac)
        for run in clip_open(pts, box):
            sheet.poly(run, "A-RIVER", sw=sw, stroke="#9a9a9a")

    shore = line_of(xs, bank, XMIN, XMAX, 10)
    nshore = line_of(xs, nbank, XMIN, XMAX, 10)
    for run in clip_open(shore, box):
        sheet.poly(run, "A-RIVER", sw=0.40, stroke="#161616")
    for run in clip_open(offset_open(shore, -4.5), box):
        sheet.poly(run, "A-RIVER", sw=0.13, stroke="#161616")
    for run in clip_open(nshore, box):
        sheet.poly(run, "A-RIVER", sw=0.40, stroke="#161616")
    for run in clip_open(offset_open(nshore, 4.5), box):
        sheet.poly(run, "A-RIVER", sw=0.13, stroke="#161616")

    # --- rail and CTrain ---
    sheet.g("rail")
    for w in ways:
        t = w.get("tags") or {}
        kind = t.get("railway")
        if kind not in ("rail", "light_rail", "tram"):
            continue
        pts = simplify(way_xy(nodes, w), 1.0)
        if len(pts) < 2 or not bbox_hits(pts):
            continue
        sw = 0.22 if kind == "rail" else 0.16
        dash = None if kind == "rail" else "1.6 1.1"
        for run in clip_open(pts, box):
            sheet.poly(run, "A-RAIL", sw=sw, stroke="#222", dash=dash)

    # --- existing roads, clipped out of the work area except kept streets ---
    sheet.g("roads-existing")
    for w in ways:
        t = w.get("tags") or {}
        if "highway" not in t:
            continue
        h = t["highway"]
        if h in ("footway", "path", "steps", "cycleway", "pedestrian", "corridor", "track"):
            continue
        pts = simplify(way_xy(nodes, w), 1.1)
        if len(pts) < 2 or not bbox_hits(pts):
            continue
        name = t.get("name") or ""
        keep = (
            h in ("motorway", "motorway_link", "trunk", "trunk_link")
            or name in KEEP_ROADS
            or "Crowchild" in name
        )
        sw = road_weight(t)
        if keep:
            runs = clip_open(pts, box)
        else:
            outside = []
            cur = []
            for p in pts:
                if work_contains(p[0], p[1], bank, rail):
                    if len(cur) >= 2:
                        outside.append(cur)
                    cur = []
                else:
                    cur.append(p)
            if len(cur) >= 2:
                outside.append(cur)
            runs = []
            for run in outside:
                runs.extend(clip_open(run, box))
        for run in runs:
            sheet.poly(run, "A-ROAD", sw=sw, stroke="#2a2a2a")

    # --- existing buildings ---
    sheet.g("buildings-existing")
    for w in ways:
        t = w.get("tags") or {}
        if "building" not in t:
            continue
        pts = way_xy(nodes, w)
        if len(pts) < 4 or not bbox_hits(pts, 0):
            continue
        cx = sum(p[0] for p in pts) / len(pts)
        cy = sum(p[1] for p in pts) / len(pts)
        if not in_window(cx, cy):
            continue
        if work_contains(cx, cy, bank, rail) and not retained(t):
            continue
        pts = simplify(pts, 0.45)
        heavy = retained(t)
        sheet.poly(
            pts,
            "A-BLDG",
            sw=0.45 if heavy else 0.11,
            stroke="#161616",
            fill="#ffffff",
            closed=True,
        )

    # --- proposal geometry ---
    # Vesica rooms first, so the loop road can be held clear of them.
    rooms = []
    for x, L, W in ((-18, 68, 28), (118, 82, 34), (248, 68, 28)):
        ang = math.atan2(bank(x + 28) - bank(x - 28), 56)
        cy = bank(x) - 96
        rooms.append((x, cy, ang, L, W))

    def outer_half_l(L):
        return L * 1.72 / 2

    def outer_half_w(W):
        return W * 2.15 / 2

    parkway_ctrl = [
        (-560, -158),
        (-500, -112),
        (-420, -72),
        (-300, -48),
        (-160, -40),
        (0, -44),
        (140, -50),
        (260, -52),
        (345, -54),
        (470, -70),
        (560, -100),
        (690, -136),
    ]
    parkway = catmull(parkway_ctrl, 12)

    def on_parkway(x):
        return min(parkway, key=lambda p: abs(p[0] - x))

    def loop_y(x):
        y = None
        for rx, cy, ang, L, W in rooms:
            if abs(x - rx) < outer_half_l(L) + 20:
                top = cy + outer_half_w(W) + 22
                y = top if y is None else max(y, top)
        cap = bank(x) - 32
        if y is None:
            return cap
        return min(y, cap)

    last = rooms[-1]
    last_tip = last[0] + outer_half_l(last[3]) + 26
    high = []
    x = -140
    while x <= last_tip:
        high.append((float(x), loop_y(x)))
        x += 20
    high.append((last_tip, loop_y(last_tip)))
    high = catmull(high, 5)
    rise = quad(on_parkway(-210), (-170, 10), high[0], 14)
    drop = quad(high[-1], (high[-1][0] + 36, high[-1][1] - 8), on_parkway(350), 18)
    loop = rise[:-1] + high + drop[1:]

    hits = 0
    for edge in (offset_open(loop, 5.2), offset_open(loop, -5.2)):
        for rx, cy, ang, L, W in rooms:
            outer = vesica(rx, cy, L * 1.72, W * 2.15, ang)
            for p in edge:
                if inside(p[0], p[1], outer):
                    hits += 1
    print("loop crossings of outer rooms", hits)

    spur = catmull([on_parkway(-430), (-520, -36), (-610, -22), (-682, -24)], 10)

    def along_rail(x):
        """Frontage-road centerline, just north of the CPR."""
        return rail(x) + 44

    def parkway_y(x):
        return min(parkway, key=lambda p: abs(p[0] - x))[1]

    # Through-road along the tracks: leaves the parkway at the west rail
    # crossing and rejoins it at 9 Avenue.
    rail_road = quad(on_parkway(-530), (-490, (on_parkway(-530)[1] + along_rail(-460)) / 2), (-450, along_rail(-450)), 12)
    x = -430.0
    while x <= 650:
        rail_road.append((x, along_rail(x)))
        x += 16
    rail_road += quad(rail_road[-1], (675, along_rail(660)), (705, -138), 12)[1:]

    sheet.g("roads-proposed")
    gaps_14 = [(352, 390)]
    for edge in (offset_open(parkway, 8.0), offset_open(parkway, -8.0)):
        for run in break_vertical(edge, gaps_14):
            sheet.poly(run, "A-ROAD-PROP", sw=0.42, stroke="#111")
    for run in break_vertical(offset_open(parkway, 11.6), gaps_14):
        sheet.poly(run, "A-ROAD-PROP", sw=0.12, stroke="#222")
    for edge in (offset_open(loop, 5.2), offset_open(loop, -5.2)):
        sheet.poly(edge, "A-ROAD-PROP", sw=0.32, stroke="#111")
    for edge in (offset_open(spur, 4.0), offset_open(spur, -4.0)):
        sheet.poly(edge, "A-ROAD-PROP", sw=0.28, stroke="#111")
    for edge in (offset_open(rail_road, 7.2), offset_open(rail_road, -7.2)):
        for run in break_vertical(edge, gaps_14):
            sheet.poly(run, "A-ROAD-PROP", sw=0.38, stroke="#111")
    for run in break_vertical(offset_open(rail_road, 10.4), gaps_14):
        sheet.poly(run, "A-ROAD-PROP", sw=0.12, stroke="#222")

    # --- paths ---
    sheet.g("paths")
    prom = line_of(xs, lambda x: bank(x) - 14, -900, 860, 8)
    nprom = line_of(xs, lambda x: nbank(x) + 12, -880, 820, 8)
    sheet.path_cased(prom, "A-PATH", sw=0.30, casing=0.7)
    sheet.path_cased(offset_open(prom, -2.4), "A-PATH", sw=0.12, casing=0.0)
    # second edge of the promenade without a second white casing flood
    sheet.poly(offset_open(prom, 2.4), "A-PATH", sw=0.16, stroke="#111")
    sheet.path_cased(nprom, "A-PATH", sw=0.22, casing=0.55)

    rings = []
    for x, cy, ang, L, W in rooms:
        inner = vesica(x, cy, L, W, ang)
        walk = vesica(x, cy, L * 1.32, W * 1.55, ang)
        outer = vesica(x, cy, L * 1.72, W * 2.15, ang)
        rings.append((inner, walk, outer, x, cy))
        sheet.poly(outer, "A-PATH", sw=0.16, stroke="#222")
        sheet.path_cased(walk, "A-PATH", sw=0.22, casing=0.45)

    # Gaps between rooms: a path from the promenade down to the parkway.
    centers = [r[0] for r in rooms]
    for gx in ((centers[0] + centers[1]) / 2, (centers[1] + centers[2]) / 2):
        sheet.path_cased([(gx, bank(gx) - 16), (gx, -62)], "A-PATH", sw=0.2, casing=0.7)

    # Link the three outer rings along their south side, just clear of the waists.
    link = [(x, cy - outer_half_w(W) - 8) for x, cy, ang, L, W in rooms]
    sheet.path_cased(catmull(link, 8), "A-PATH", sw=0.16, casing=0.4)

    # West court walks, held in the gaps between the bars.
    # The north-south walk continues down to the rail road.
    sheet.path_cased([(-505, bank(-505) - 18), (-505, along_rail(-505) + 12)], "A-PATH", sw=0.2, casing=0.65)
    sheet.path_cased([(-670, 60), (-370, 60)], "A-PATH", sw=0.18, casing=0.55)
    sheet.path_cased([(-665, 22), (-380, 22)], "A-PATH", sw=0.14, casing=0.4)
    for gx in ((centers[0] + centers[1]) / 2, (centers[1] + centers[2]) / 2):
        sheet.path_cased([(gx, -34), (gx, along_rail(gx) + 12)], "A-PATH", sw=0.16, casing=0.45)

    # East bar garden and the bridge landing.
    sheet.poly(rectangle(548, -28, 196, 46), "A-PATH", sw=0.16, stroke="#222", closed=True)
    sheet.path_cased([(450, -28), (646, -28)], "A-PATH", sw=0.14, casing=0.35)
    sheet.path_cased([(548, -4), (548, -50)], "A-PATH", sw=0.14, casing=0.35)
    sheet.path_cased([(420, bank(420) - 16), (420, 36), (450, 18)], "A-PATH", sw=0.2, casing=0.6)
    # Stay west of the planetarium, which sits on the bank east of the rotunda.
    sheet.path_cased([(648, 18), (648, bank(648) - 18)], "A-PATH", sw=0.18, casing=0.5)
    sheet.path_cased([(450, 42), (648, 42)], "A-PATH", sw=0.16, casing=0.45)

    # --- trees ---
    sheet.g("trees")

    def plant(pts, spacing, off, r=3.3, along_left=True):
        base = offset_open(pts, off) if off else pts
        for i, (x, y) in enumerate(sample_along(base, spacing)):
            if not (XMIN + 10 < x < XMAX - 10 and YMIN + 10 < y < YMAX - 10):
                continue
            # Keep the allee on land, south of the south bank and north of the rail.
            if y > bank(x) - 2 or y < rail(x) + 8:
                if not (nbank(x) + 4 < y < nbank(x) + 28):
                    continue
            rr = r if i % 3 else r + 0.7
            sheet.circle(x, y, rr, "A-TREE", sw=0.09)

    plant(prom, 16, -7.5, 3.4)
    plant(nprom, 18, 6.5, 3.1)
    # Extended riverfront groves west of the rooms and east toward the planetarium.
    plant(line_of(xs, lambda x: bank(x) - 36, -820, -220, 8), 18, 0, 3.0)
    plant(line_of(xs, lambda x: bank(x) - 34, 360, 840, 8), 17, 0, 3.2)
    plant(parkway, 22, -14, 3.6)
    for inner, walk, outer, cx, cy in rings:
        ring_pts = sample_along(outer, 14)
        for x, y in ring_pts:
            sheet.circle(x, y, 2.8, "A-TREE", sw=0.09)
    # East court grid.
    gx = 468
    while gx <= 630:
        gy = -46
        while gy <= -12:
            sheet.circle(gx, gy, 2.5, "A-TREE", sw=0.08)
            gy += 12
        gx += 12
    # West court trees.
    for x, y in (
        (-630, 72),
        (-540, 72),
        (-460, 72),
        (-620, 50),
        (-400, 50),
        (-630, 14),
        (-390, 14),
    ):
        sheet.circle(x, y, 3.2, "A-TREE", sw=0.09)
    plant(rail_road, 24, -11, 3.0)

    # --- proposed buildings ---
    sheet.g("buildings-proposed")
    for x, cy, ang, L, W in rooms:
        sheet.poly(vesica(x, cy, L, W, ang), "A-BLDG-PROP", sw=0.15, stroke="#111", fill="#161616", closed=True)

    # Pulled south off the riverbank.
    blocks = [
        (-575, 86, 96, 14, 0),
        (-452, 86, 80, 14, 0),
        (-392, 84, 16, 20, 0),
        (-578, 40, 74, 12, 0),
        (-448, 40, 66, 12, 0),
        (-570, 4, 78, 12, 0),
        (-446, 4, 68, 12, 0),
        (-590, -14, 42, 11, 0),
        (-450, -14, 50, 11, 0),
        (-662, 74, 36, 12, 0),
        (-658, 46, 36, 12, 0),
        (-664, 8, 30, 11, 0),
    ]
    for cx, cy, w, h, ang in blocks:
        sheet.poly(rectangle(cx, cy, w, h, ang), "A-BLDG-PROP", sw=0, stroke="none", fill="#161616", closed=True)

    def clear_of_road(cx, cy, h):
        """True when the bar sits south of the parkway and north of the rail road."""
        if 348 < cx < 400:
            return False
        top = cy + h / 2
        bot = cy - h / 2
        if top > parkway_y(cx) - 22:
            return False
        if bot < along_rail(cx) + 18:
            return False
        return True

    x = -560.0
    flip = False
    while x <= 490:
        if 345 < x < 410:
            x = 420.0
            continue
        cy = along_rail(x) + 32
        w = 42 if flip else 30
        if clear_of_road(x, cy, 13):
            sheet.poly(rectangle(x, cy, w, 13), "A-BLDG-PROP", sw=0, stroke="none", fill="#161616", closed=True)
        cy2 = cy + 30
        if clear_of_road(x + 6, cy2, 12) and cy2 - 8 > cy + 8:
            sheet.poly(rectangle(x + 6, cy2, w - 8, 12), "A-BLDG-PROP", sw=0, stroke="none", fill="#161616", closed=True)
        x += 48
        flip = not flip

    # Linear bar and east rotunda. Kept clear of Mewata Armoury and the planetarium.
    sheet.poly(rectangle(545, 16, 210, 26, -0.015), "A-BLDG-PROP", sw=0, stroke="none", fill="#161616", closed=True)
    sheet.poly(circle_poly(664, 15, 16, 48), "A-BLDG-PROP", sw=0, stroke="none", fill="#161616", closed=True)
    for cx, cy, w, h in ((500, -2, 28, 12), (575, -1, 18, 14), (620, -2, 26, 11)):
        sheet.poly(rectangle(cx, cy, w, h), "A-BLDG-PROP", sw=0, stroke="none", fill="#161616", closed=True)

    # --- pedestrian bridge ---
    sheet.g("bridge")
    sx = -530
    sy = bank(sx) - 14
    nx = -690
    # North landing just inland of the north bank.
    ny = nbank(nx) + 10
    deck = [(sx, sy), (nx, ny)]
    for edge in (offset_open(deck, 2.3), offset_open(deck, -2.3)):
        sheet.poly(edge, "A-BRIDGE", sw=0.28, stroke="#111")
    # Piers.
    for t, r in ((0.34, 1.6), (0.62, 1.6)):
        px, py = lerp((sx, sy), (nx, ny), t)
        sheet.circle(px, py, r, "A-BRIDGE", sw=0.2, fill="#161616", stroke="#111")
    mast = lerp((sx, sy), (nx, ny), 0.18)
    sheet.circle(mast[0], mast[1], 2.2, "A-BRIDGE", sw=0.25, fill="none", stroke="#111")
    for t in (0.4, 0.55, 0.7, 0.85, 1.0):
        tip = lerp((sx, sy), (nx, ny), t)
        sheet.poly([mast, tip], "A-BRIDGE", sw=0.08, stroke="#333")
    # Landing plaza on the south promenade.
    sheet.circle(sx, sy, 7.5, "A-BRIDGE", sw=0.2, fill="none", stroke="#111")

    # 14 Street, drawn as a deck so the bridge and the rerouted crossing read.
    lx = 371
    street = [(lx, nbank(lx) + 6), (lx, rail(lx) + 4)]
    for edge in (offset_open(street, 8.0), offset_open(street, -8.0)):
        sheet.poly(edge, "A-BRIDGE", sw=0.32, stroke="#111")
    ly = bank(lx) - 16
    sheet.circle(lx, ly, 9, "A-BRIDGE", sw=0.22, fill="none", stroke="#111")

    # Limit of work, drawn late so the dash is not buried under the promenade.
    sheet.g("limit")
    lim = []
    x = WORK_X0
    while x <= WORK_X1:
        lim.append((x, bank(x) + 2))
        x += 18
    x = WORK_X1
    while x >= WORK_X0:
        lim.append((x, rail(x) + 18))
        x -= 18
    lim.append(lim[0])
    sheet.poly(lim, None, sw=0.9, stroke="#ffffff", dash="3.2 2.0", closed=True)
    sheet.poly(lim, "A-LIMIT", sw=0.18, stroke="#333", dash="3.2 2.0", closed=True)

    # --- labels ---
    sheet.g("labels")
    labels = [
        (80, (nbank(80) + bank(80)) / 2, "BOW RIVER", 3.6, 0),
        (-260, 292, "MEMORIAL DRIVE NW", 2.5, -4),
        (-960, -20, "CROWCHILD TRAIL", 2.4, -78),
        (348, -280, "14 STREET SW", 2.3, 90),
        (120, -230, "CPR", 2.4, -3),
        (20, -300, "SUNALTA", 2.5, 0),
        (780, -158, "9 AVENUE SW", 2.2, -3),
        (-360, -250, "10 AVENUE SW", 2.2, -2),
        (-710, -78, "PUMPHOUSE", 2.0, 0),
        (800, -10, "MEWATA ARMOURY", 2.0, 0),
        (690, 168, "PLANETARIUM", 2.0, 0),
        (-230, -30, "PARKWAY", 2.1, -4),
        (-200, bank(-200) - 26, "RIVERFRONT", 2.0, math.degrees(math.atan2(bank(-140) - bank(-260), 120))),
    ]
    for x, y, s, size, ang in labels:
        sheet.text(x, y, s, size=size, ang=ang, layer="A-ANNO")

    sheet.text(WORK_X0 + 30, rail(WORK_X0 + 40) + 48, "LIMIT OF WORK", size=1.8, ang=90, anchor="middle")

    # Model-space scale bar and north arrow, true metres, south of the map.
    bar_y = YMIN - 70
    bar_x = XMIN + 40
    sheet.poly([(bar_x, bar_y), (bar_x + 200, bar_y)], "A-ANNO", sw=0.4)
    for i, m in enumerate((0, 50, 100, 150)):
        sheet.poly(
            [(bar_x + m, bar_y), (bar_x + m + 50, bar_y), (bar_x + m + 50, bar_y + 8), (bar_x + m, bar_y + 8), (bar_x + m, bar_y)],
            "A-ANNO",
            sw=0.2,
            fill="#161616" if i % 2 == 0 else "none",
            closed=True,
        )
    sheet.text(bar_x, bar_y - 12, "0", size=4, anchor="middle")
    sheet.text(bar_x + 100, bar_y - 12, "100", size=4, anchor="middle")
    sheet.text(bar_x + 200, bar_y - 12, "200 m", size=4, anchor="start")
    sheet.text(bar_x, bar_y + 18, "SCALE 1:2000   ·   METRES", size=4, anchor="start")
    ax, ay = XMAX - 80, YMIN - 55
    sheet.poly([(ax, ay), (ax, ay + 40)], "A-ANNO", sw=0.4)
    sheet.poly([(ax, ay + 40), (ax - 6, ay + 28), (ax + 6, ay + 28), (ax, ay + 40)], "A-ANNO", sw=0.2, fill="#161616", closed=True)
    sheet.text(ax, ay + 52, "N", size=6, anchor="middle")

    prom_len = length(prom)
    draw_title(sheet, prom_len)
    emit_svg(sheet)
    emit_dxf(sheet)
    print(f"promenade {prom_len:.0f} m")
    print("wrote", SVG_PATH)
    print("wrote", DXF_PATH)
    print(f"sheet {SHEET_W:.0f} x {SHEET_H:.0f} mm at 1:2000")


if __name__ == "__main__":
    main()
