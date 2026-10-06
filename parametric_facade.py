"""Parametric environmental facade.

The Kaarwan article
(https://www.kaarwan.com/blog/architecture/unlocking-the-potential-of-parametric-design-how-grasshopper-software-revolutionizes-modern-architecture?id=837)
describes Grasshopper as a way to change building height, bend a facade,
resize structure for load, and let the skin respond to the environment.
It does not include a drawing or dimensions. This module is that idea
as numbers: one curved bar, a sun vector, apertures that close as the
sun hits them, and mullions that deepen toward midspan.

Units are metres. u runs 0 to 1 along the facade, from -X to +X.
z is up. The facade faces +Y and bows outward by `camber`.

Both hosts import this file:
  parametric_facade_grasshopper.py   Rhino 8 / Grasshopper Script
  parametric_facade_blender.py       Blender
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field


def clamp(value, low, high):
    return max(low, min(high, value))


def lerp(a, b, t):
    return a + (b - a) * t


def add(a, b):
    return tuple(a[i] + b[i] for i in range(3))


def sub(a, b):
    return tuple(a[i] - b[i] for i in range(3))


def scale(a, s):
    return tuple(c * s for c in a)


def dot(a, b):
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def dist(a, b):
    return math.hypot(a[0] - b[0], a[1] - b[1], a[2] - b[2])


def normalize(v):
    length = math.hypot(v[0], v[1], v[2])
    if length < 1e-9:
        return (0.0, 1.0, 0.0)
    return (v[0] / length, v[1] / length, v[2] / length)


@dataclass
class Params:
    width: float = 24.0
    depth: float = 12.0
    floor_height: float = 3.6
    floors: int = 6
    bays_x: int = 16
    bays_per_floor: int = 2
    camber: float = 3.0
    # 0 degrees: sun straight in front of the facade. Positive swings toward +X.
    sun_azimuth: float = 25.0
    sun_altitude: float = 42.0
    aperture_min: float = 0.18
    aperture_max: float = 0.82
    frame: float = 0.15
    rib_min: float = 0.28
    rib_max: float = 1.05
    panel_thickness: float = 0.06

    @property
    def height(self):
        return self.floors * self.floor_height

    @property
    def bays_z(self):
        return max(1, self.floors * self.bays_per_floor)


@dataclass
class Panel:
    corners: list
    opening: list
    frame: list
    aperture: float
    incidence: float
    normal: tuple
    u0: float
    u1: float
    z0: float
    z1: float
    flat_outer: list
    flat_opening: list


@dataclass
class Model:
    params: Params
    sun: tuple
    panels: list = field(default_factory=list)
    vertical_ribs: list = field(default_factory=list)
    horizontal_ribs: list = field(default_factory=list)
    floor_plates: list = field(default_factory=list)
    walls: list = field(default_factory=list)
    arc_samples: int = 48

    def facade_point(self, u, z):
        p = self.params
        x = -p.width / 2 + u * p.width
        y = p.depth + p.camber * math.sin(math.pi * u)
        return (x, y, z)

    def facade_tangent_u(self, u):
        p = self.params
        return (p.width, p.camber * math.pi * math.cos(math.pi * u), 0.0)

    def facade_normal(self, u):
        dx, dy, _ = self.facade_tangent_u(u)
        return normalize((-dy, dx, 0.0))

    def rib_depth(self, u):
        """Simply-supported moment diagram: zero at the supports, peak at center."""
        p = self.params
        return lerp(p.rib_min, p.rib_max, math.sin(math.pi * clamp(u, 0.0, 1.0)))

    def developed_s(self, u, steps=64):
        """Arc length from the west end of the facade to parameter u."""
        u = clamp(u, 0.0, 1.0)
        if u <= 0:
            return 0.0
        n = max(1, int(steps * u))
        length = 0.0
        prev = self.facade_point(0.0, 0.0)
        for i in range(1, n + 1):
            t = u * i / n
            pt = self.facade_point(t, 0.0)
            length += dist(prev, pt)
            prev = pt
        return length


def sun_vector(azimuth_deg, altitude_deg):
    az = math.radians(azimuth_deg)
    alt = math.radians(altitude_deg)
    horizontal = math.cos(alt)
    return normalize((math.sin(az) * horizontal, math.cos(az) * horizontal, math.sin(alt)))


def _inset_params(model, u0, u1, z0, z1, frame):
    span = dist(model.facade_point(u0, z0), model.facade_point(u1, z0))
    height = abs(z1 - z0)
    frame = min(frame, span * 0.45, height * 0.45)
    du = (u1 - u0) * (frame / span) if span > 1e-6 else 0.0
    dz = frame
    return u0 + du, u1 - du, z0 + dz, z1 - dz


def _quad(model, u0, u1, z0, z1):
    return [
        model.facade_point(u0, z0),
        model.facade_point(u1, z0),
        model.facade_point(u1, z1),
        model.facade_point(u0, z1),
    ]


def build(params=None, **overrides):
    if params is None:
        params = Params()
    for key, value in overrides.items():
        setattr(params, key, value)
    params.floors = max(1, int(params.floors))
    params.bays_x = max(1, int(params.bays_x))
    params.bays_per_floor = max(1, int(params.bays_per_floor))
    params.aperture_min = clamp(params.aperture_min, 0.02, 1.0)
    params.aperture_max = clamp(max(params.aperture_max, params.aperture_min), 0.02, 1.0)

    model = Model(params=params, sun=sun_vector(params.sun_azimuth, params.sun_altitude))
    height = params.height
    bays_z = params.bays_z

    for i in range(params.bays_x):
        for j in range(bays_z):
            u0 = i / params.bays_x
            u1 = (i + 1) / params.bays_x
            z0 = j / bays_z * height
            z1 = (j + 1) / bays_z * height
            um = (u0 + u1) / 2
            normal = model.facade_normal(um)
            incidence = clamp(dot(normal, model.sun), 0.0, 1.0)
            # Head-on sun closes the opening. Glancing sun leaves it open.
            aperture = lerp(params.aperture_max, params.aperture_min, incidence)
            iu0, iu1, iz0, iz1 = _inset_params(model, u0, u1, z0, z1, params.frame)
            cu = (iu0 + iu1) / 2
            cz = (iz0 + iz1) / 2
            hu = (iu1 - iu0) / 2 * aperture
            hz = (iz1 - iz0) / 2 * aperture
            ou0, ou1 = cu - hu, cu + hu
            oz0, oz1 = cz - hz, cz + hz
            opening = _quad(model, ou0, ou1, oz0, oz1)
            frame = [
                _quad(model, u0, u1, z0, oz0),
                _quad(model, u0, u1, oz1, z1),
                _quad(model, u0, ou0, oz0, oz1),
                _quad(model, ou1, u1, oz0, oz1),
            ]
            s0 = model.developed_s(u0)
            s1 = model.developed_s(u1)
            si0 = lerp(s0, s1, (ou0 - u0) / (u1 - u0))
            si1 = lerp(s0, s1, (ou1 - u0) / (u1 - u0))
            panel = Panel(
                corners=_quad(model, u0, u1, z0, z1),
                opening=opening,
                frame=frame,
                aperture=aperture,
                incidence=incidence,
                normal=normal,
                u0=u0,
                u1=u1,
                z0=z0,
                z1=z1,
                flat_outer=[(s0, z0), (s1, z0), (s1, z1), (s0, z1)],
                flat_opening=[(si0, oz0), (si1, oz0), (si1, oz1), (si0, oz1)],
            )
            model.panels.append(panel)

    for i in range(params.bays_x + 1):
        u = i / params.bays_x
        depth = model.rib_depth(u)
        normal = model.facade_normal(u)
        outer_b = model.facade_point(u, 0.0)
        outer_t = model.facade_point(u, height)
        inner_b = sub(outer_b, scale(normal, depth))
        inner_t = sub(outer_t, scale(normal, depth))
        model.vertical_ribs.append([outer_b, inner_b, inner_t, outer_t])

    for level in range(params.floors + 1):
        z = level * params.floor_height
        strip = []
        for i in range(params.bays_x):
            u0 = i / params.bays_x
            u1 = (i + 1) / params.bays_x
            d0 = model.rib_depth(u0)
            d1 = model.rib_depth(u1)
            n0 = model.facade_normal(u0)
            n1 = model.facade_normal(u1)
            a = model.facade_point(u0, z)
            b = model.facade_point(u1, z)
            c = sub(b, scale(n1, d1))
            d = sub(a, scale(n0, d0))
            strip.append([a, b, c, d])
        model.horizontal_ribs.append(strip)

    samples = model.arc_samples
    front = [model.facade_point(i / samples, 0.0) for i in range(samples + 1)]
    for level in range(params.floors + 1):
        z = level * params.floor_height
        plate = [(-params.width / 2, 0.0, z), (params.width / 2, 0.0, z)]
        plate.extend((p[0], p[1], z) for p in reversed(front))
        model.floor_plates.append(plate)

    z1 = height
    west = model.facade_point(0.0, 0.0)
    east = model.facade_point(1.0, 0.0)
    model.walls = [
        [(-params.width / 2, 0.0, 0.0), (params.width / 2, 0.0, 0.0),
         (params.width / 2, 0.0, z1), (-params.width / 2, 0.0, z1)],
        [(-params.width / 2, 0.0, 0.0), west, (west[0], west[1], z1), (-params.width / 2, 0.0, z1)],
        [(params.width / 2, 0.0, 0.0), east, (east[0], east[1], z1), (params.width / 2, 0.0, z1)],
    ]
    return model


def aperture_color(aperture, aperture_min, aperture_max):
    """Closed/shaded reads terracotta. Open reads pale glass."""
    span = max(1e-6, aperture_max - aperture_min)
    t = clamp((aperture - aperture_min) / span, 0.0, 1.0)
    closed = (176, 78, 48)
    open_ = (214, 228, 232)
    return tuple(int(lerp(closed[i], open_[i], t)) for i in range(3))


def write_preview(model, path):
    """Plan, elevation, and unfolded panel sheet. 1 unit in the file is 1 metre, scaled to mm."""
    p = model.params
    scale_px = 18.0
    gap = 28.0

    def xy(x, y, ox, oy):
        return ox + x * scale_px, oy - y * scale_px

    plan_w = (p.width + 8) * scale_px
    plan_h = (p.depth + p.camber + 8) * scale_px
    elev_w = plan_w
    elev_h = (p.height + 6) * scale_px
    sheet_w = model.developed_s(1.0) + 2
    sheet_h = p.height + 2
    fab_w = sheet_w * scale_px
    fab_h = sheet_h * scale_px

    width = max(plan_w, elev_w, fab_w) + 2 * gap
    height = gap + plan_h + gap + elev_h + gap + fab_h + gap
    parts = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width:.1f}" height="{height:.1f}" viewBox="0 0 {width:.1f} {height:.1f}">',
        '<rect width="100%" height="100%" fill="#f4f1ea"/>',
        '<style>text{font-family:Georgia,serif;fill:#1c1a17;font-size:14px}</style>',
    ]

    def polyline(points, stroke, ox, oy, width_px=1.2, close=False):
        mapped = [xy(x, y, ox, oy) for x, y in points]
        if close:
            mapped.append(mapped[0])
        d = " ".join(f"{x:.2f},{y:.2f}" for x, y in mapped)
        parts.append(
            f'<polyline points="{d}" fill="none" stroke="{stroke}" stroke-width="{width_px}" stroke-linejoin="round"/>'
        )

    def polygon(points, fill, ox, oy, opacity=1):
        mapped = [xy(x, y, ox, oy) for x, y in points]
        d = " ".join(f"{x:.2f},{y:.2f}" for x, y in mapped)
        parts.append(f'<polygon points="{d}" fill="{fill}" fill-opacity="{opacity}" stroke="none"/>')

    ox = gap + 4 * scale_px
    oy = gap + (p.depth + p.camber + 4) * scale_px
    parts.append(f'<text x="{gap}" y="{gap - 8}">plan — camber {p.camber:.2f} m, rib depth follows the span</text>')
    front = [(model.facade_point(i / 64, 0)[0], model.facade_point(i / 64, 0)[1]) for i in range(65)]
    plan = [(-p.width / 2, 0), (p.width / 2, 0)] + list(reversed(front))
    polygon([(a, b) for a, b in plan], "#d9d3c7", ox, oy)
    polyline(plan, "#1c1a17", ox, oy, 1.4, close=True)
    for rib in model.vertical_ribs:
        a, b = rib[0], rib[1]
        polyline([(a[0], a[1]), (b[0], b[1])], "#8a3b28", ox, oy, 1.1)

    oy2 = oy + gap + 4 * scale_px
    parts.append(f'<text x="{gap}" y="{oy + gap - 10}">elevation — {p.floors} floors, height {p.height:.1f} m</text>')
    for panel in model.panels:
        color = aperture_color(panel.aperture, p.aperture_min, p.aperture_max)
        hex_color = "#{:02x}{:02x}{:02x}".format(*color)
        outer = [(c[0], c[2]) for c in panel.corners]
        opening = [(c[0], c[2]) for c in panel.opening]
        polygon(outer, hex_color, ox, oy2)
        polygon(opening, "#f4f1ea", ox, oy2)
    for plate in model.floor_plates:
        a, b = plate[0], plate[1]
        polyline([(a[0], a[2]), (b[0], b[2])], "#1c1a17", ox, oy2, 0.8)

    sun = model.sun
    parts.append(
        f'<text x="{gap}" y="{oy2 + 18}">sun azimuth {p.sun_azimuth:.0f}°, altitude {p.sun_altitude:.0f}° — '
        f'vector ({sun[0]:.2f}, {sun[1]:.2f}, {sun[2]:.2f})</text>'
    )

    fab_ox = gap
    fab_oy = oy2 + elev_h + gap * 0.2
    parts.append(f'<text x="{gap}" y="{oy2 + gap + elev_h - 36}">unfolded panels for fabrication</text>')
    for panel in model.panels:
        color = aperture_color(panel.aperture, p.aperture_min, p.aperture_max)
        hex_color = "#{:02x}{:02x}{:02x}".format(*color)
        polygon(panel.flat_outer, hex_color, fab_ox, fab_oy)
        polygon(panel.flat_opening, "#f4f1ea", fab_ox, fab_oy)
        polyline(panel.flat_outer, "#1c1a17", fab_ox, fab_oy, 0.4, close=True)

    parts.append("</svg>")
    path.write_text("\n".join(parts), encoding="utf-8")


def main():
    from pathlib import Path

    model = build()
    incidences = [panel.incidence for panel in model.panels]
    assert min(incidences) < max(incidences)
    assert model.vertical_ribs[0]
    mid = model.rib_depth(0.5)
    end = model.rib_depth(0.0)
    assert mid > end
    out = Path(__file__).resolve().parent / "parametric_facade_preview.svg"
    write_preview(model, out)
    print(f"panels {len(model.panels)}")
    print(f"height {model.params.height:.2f} m")
    print(f"incidence {min(incidences):.2f} to {max(incidences):.2f}")
    print(f"wrote {out.name}")


if __name__ == "__main__":
    main()
