#!/usr/bin/env python3
"""Build a meter-true West Village site dataset from OSM."""

import json
import math
from pathlib import Path

ROOT = Path(__file__).resolve().parent
OSM_PATH = ROOT / "westvillage_osm.json"
OUT_PATH = ROOT / "westvillage.json"

LAT0 = 51.0466
LON0 = -114.1000
M_LAT = 111132.954
M_LON = 111132.954 * math.cos(math.radians(LAT0))


def project(lat, lon):
    return ((lon - LON0) * M_LON, (lat - LAT0) * M_LAT)


def way_xy(nodes, w):
    pts = []
    for nid in w.get("nodes", []):
        n = nodes.get(nid)
        if n:
            pts.append(project(n["lat"], n["lon"]))
    return pts


def simplify(pts, eps=12):
    if len(pts) >= 2 and pts[0] == pts[-1]:
        pts = pts[:-1]
    if len(pts) < 3:
        return pts

    def dp(points):
        if len(points) < 3:
            return points
        a, b = points[0], points[-1]
        dx, dy = b[0] - a[0], b[1] - a[1]
        mag = math.hypot(dx, dy) or 1
        maxd, idx = -1, 0
        for i in range(1, len(points) - 1):
            px, py = points[i]
            d = abs(dy * px - dx * py + b[0] * a[1] - b[1] * a[0]) / mag
            if d > maxd:
                maxd, idx = d, i
        if maxd > eps:
            return dp(points[: idx + 1])[:-1] + dp(points[idx:])
        return [points[0], points[-1]]

    out = dp(pts)
    if out[0] != out[-1]:
        out.append(out[0])
    return out


def poly_area(pts):
    a = 0
    for i, (x1, y1) in enumerate(pts):
        x2, y2 = pts[(i + 1) % len(pts)]
        a += x1 * y2 - x2 * y1
    return abs(a) / 2


def inside(x, y, poly):
    odd = False
    n = len(poly)
    for i in range(n):
        x1, y1 = poly[i]
        x2, y2 = poly[(i + 1) % n]
        if (y1 > y) != (y2 > y) and x < (x2 - x1) * (y - y1) / (y2 - y1 + 1e-12) + x1:
            odd = not odd
    return odd


def interp_y(edge, x):
    edge = sorted(edge, key=lambda p: p[0])
    if x <= edge[0][0]:
        return edge[0][1]
    if x >= edge[-1][0]:
        return edge[-1][1]
    for i in range(len(edge) - 1):
        x1, y1 = edge[i]
        x2, y2 = edge[i + 1]
        if x1 <= x <= x2:
            t = 0 if x2 == x1 else (x - x1) / (x2 - x1)
            return y1 + t * (y2 - y1)
    return edge[-1][1]


def envelope(pts, by="y", stat="max", width=25):
    buckets = {}
    for x, y in pts:
        key = (y if by == "y" else x)
        b = round(key / width) * width
        buckets.setdefault(b, []).append(x if by == "y" else y)
    keys = sorted(buckets)
    out = []
    for k in keys:
        vals = buckets[k]
        v = max(vals) if stat == "max" else min(vals)
        out.append((v, k) if by == "y" else (k, v))
    return out


def main():
    osm = json.loads(OSM_PATH.read_text())
    nodes = {e["id"]: e for e in osm["elements"] if e["type"] == "node"}
    ways = [e for e in osm["elements"] if e["type"] == "way"]

    crow, st11, rail, bowtrail, st14, river, pumphouse_rd = [], [], [], [], [], [], []
    buildings_raw = []

    for w in ways:
        t = w.get("tags") or {}
        pts = way_xy(nodes, w)
        if len(pts) < 2:
            continue
        name = t.get("name") or ""
        if name == "Crowchild Trail SW":
            crow.append(pts)
        elif name == "11 Street SW":
            st11.append(pts)
        elif t.get("railway") == "rail":
            rail.append(pts)
        elif name == "Bow Trail SW":
            bowtrail.append(pts)
        elif name == "14 Street SW":
            st14.append(pts)
        elif name.startswith("Pumphouse"):
            pumphouse_rd.append(pts)
        elif "Bow" in name and t.get("waterway"):
            river.append(pts)
        if "building" in t and len(pts) >= 3:
            cx = sum(p[0] for p in pts) / len(pts)
            cy = sum(p[1] for p in pts) / len(pts)
            buildings_raw.append(
                {
                    "id": w["id"],
                    "name": name,
                    "addr": " ".join(
                        filter(None, [t.get("addr:housenumber"), t.get("addr:street")])
                    ),
                    "cx": cx,
                    "cy": cy,
                    "pts": pts,
                }
            )

    def flat(lines, pred):
        out = []
        for ln in lines:
            out.extend([p for p in ln if pred(*p)])
        return out

    crow_pts = flat(crow, lambda x, y: -1200 < x < -700 and -280 < y < 220)
    st11_pts = flat(st11, lambda x, y: 720 < x < 950 and -280 < y < 280)
    rail_pts = flat(rail, lambda x, y: -1100 < x < 920 and -260 < y < 30)
    riv_pts = flat(river, lambda x, y: -1100 < x < 950 and 30 < y < 280)

    west_x = max(p[0] for p in crow_pts)  # east face of Crowchild
    east_x = min(p[0] for p in st11_pts)  # west face of 11 Street
    south = envelope(rail_pts, by="x", stat="max", width=40)
    if riv_pts:
        north = envelope(riv_pts, by="x", stat="min", width=40)
    else:
        north = [(x, 150) for x, _ in south]

    xs = []
    x = west_x
    while x <= east_x:
        xs.append(x)
        x += 25
    xs.append(east_x)

    south_line = [(x, interp_y(south, x)) for x in xs]
    north_line = [(x, interp_y(north, x)) for x in xs]
    site = south_line + list(reversed(north_line))
    site.append(site[0])

    xmin, xmax = west_x, east_x

    area = poly_area(site[:-1])

    site_buildings = []
    for b in buildings_raw:
        if not inside(b["cx"], b["cy"], site[:-1]):
            continue
        key = (b["name"] + " " + b["addr"]).lower()
        role = "other"
        if "pumphouse" in key:
            role = "pumphouse"
        elif "armoury" in key or "armory" in key:
            role = "armoury"
        elif "planetarium" in key or "contemporary" in key:
            role = "contemporary"
        site_buildings.append(
            {
                "name": b["name"] or b["addr"] or "building",
                "role": role,
                "cx": round(b["cx"], 1),
                "cy": round(b["cy"], 1),
                    "pts": [[round(x, 1), round(y, 1)] for x, y in simplify(b["pts"], 2)],
            }
        )

    def pack_lines(lines, pred, eps=14):
        out = []
        for ln in lines:
            pts = [(round(x, 1), round(y, 1)) for x, y in simplify(ln, eps) if pred(x, y)]
            if len(pts) >= 2:
                out.append(pts)
        return out

    data = {
        "crs": "local meters",
        "origin": {"lat": LAT0, "lon": LON0},
        "official": {
            "name": "West Village, Calgary",
            "area_ha_published": 53,
            "bounds": "Bow River (N), CPR (S), Crowchild Trail SW (W), 11 Street SW (E)",
            "length_m_riverfront_published": 2000,
        },
        "measured": {
            "area_m2": round(area),
            "area_ha": round(area / 10000, 2),
            "width_m": round(xmax - xmin, 1),
            "depth_m": round(max(p[1] for p in north) - min(p[1] for p in south), 1),
        },
        "site": [[round(x, 1), round(y, 1)] for x, y in site],
        "buildings": site_buildings,
        "roads": {
            "crowchild": pack_lines(crow, lambda x, y: -1200 < x < -650 and -300 < y < 250),
            "st11": pack_lines(st11, lambda x, y: 700 < x < 960 and -300 < y < 300),
            "st14": pack_lines(st14, lambda x, y: 300 < x < 450 and -300 < y < 220),
            "bow_trail": pack_lines(bowtrail, lambda x, y: -1100 < x < 900 and -250 < y < 180),
            "pumphouse": pack_lines(pumphouse_rd, lambda x, y: -900 < x < -500 and -80 < y < 80),
        },
        "rail": pack_lines(rail, lambda x, y: -1100 < x < 920 and -260 < y < 40),
        "river": pack_lines(river, lambda x, y: -1100 < x < 950 and 20 < y < 280, eps=20),
        "attractors": [
            next((b for b in site_buildings if b["role"] == r), None)
            for r in ("pumphouse", "contemporary", "armoury")
        ],
    }
    data["attractors"] = [a for a in data["attractors"] if a]

    OUT_PATH.write_text(json.dumps(data))
    print("wrote", OUT_PATH)
    print("site area ha", data["measured"]["area_ha"], "width", data["measured"]["width_m"], "depth", data["measured"]["depth_m"])
    print("buildings", len(site_buildings))
    print("attractors", [a["name"] for a in data["attractors"]])


if __name__ == "__main__":
    main()
