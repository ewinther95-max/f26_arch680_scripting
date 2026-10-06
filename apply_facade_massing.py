"""Skin the three Rhino massings and give each a different entrance.

  0  corner entrance on the short end
  1  side entrance centered on the long straight wall
  2  curved entrance on one arc, with a canopy that follows it

Reads the desktop massing file and writes a new 3dm beside it.
The original extrusions stay. Facade and entrances are new layers.
"""

import math
from pathlib import Path

import rhino3dm

import parametric_facade as facade

SOURCE = Path("/Users/evanwinther/Desktop/Massing Models.3dm")
OUTPUT = Path("/Users/evanwinther/Desktop/Massing Models Facade.3dm")

MODULE = 2.0
FRAME = 0.16
APERTURE_MIN = 0.16
APERTURE_MAX = 0.78
SUN_ALTITUDE = 42.0
SKIN = 0.12
RIB_MIN = 0.25
RIB_MAX = 0.85

# One entrance per massing: corner, side, curved.
ENTRANCES = (
    {"kind": "corner", "segment": 1, "t0": 0.62, "t1": 1.0, "height": 4.6},
    {"kind": "side", "segment": 1, "t0": 0.34, "t1": 0.66, "height": 5.2},
    {"kind": "curved", "segment": 0, "t0": 0.28, "t1": 0.72, "height": 4.4},
)


def sun_direction():
    altitude = math.radians(SUN_ALTITUDE)
    # 180 degrees: sun is due south, toward -Y.
    return (0.0, -math.cos(altitude), math.sin(altitude))


def unit2(x, y):
    length = math.hypot(x, y)
    if length < 1e-9:
        return (0.0, 1.0)
    return (x / length, y / length)


def outward_at(segment, t):
    """CCW footprints: outward is to the right of the tangent."""
    domain = segment.Domain
    span = domain.T1 - domain.T0
    t0 = domain.T0 + span * max(0.0, t - 0.01)
    t1 = domain.T0 + span * min(1.0, t + 0.01)
    a = segment.PointAt(t0)
    b = segment.PointAt(t1)
    return unit2(b.Y - a.Y, -(b.X - a.X))


def point_on(segment, t, z, offset, normal):
    domain = segment.Domain
    at = segment.PointAt(domain.T0 + (domain.T1 - domain.T0) * t)
    return (
        at.X + normal[0] * offset,
        at.Y + normal[1] * offset,
        z,
    )


def segment_length(segment, steps=24):
    length = 0.0
    previous = segment.PointAtStart
    domain = segment.Domain
    for i in range(1, steps + 1):
        t = domain.T0 + (domain.T1 - domain.T0) * i / steps
        point = segment.PointAt(t)
        length += previous.DistanceTo(point)
        previous = point
    return length


def add_quad(mesh, corners, color):
    start = mesh.VertexColors.Count
    for x, y, z in corners:
        mesh.Vertices.Add(x, y, z)
        mesh.VertexColors.Add(*color)
    mesh.Faces.AddFace(start, start + 1, start + 2, start + 3)


def panel_wall(mesh, rib_mesh, segment, z0, z1, skip, sun):
    length = segment_length(segment)
    count_h = max(1, int(round(length / MODULE)))
    count_v = max(1, int(round((z1 - z0) / MODULE)))
    cell_h = length / count_h
    cell_v = (z1 - z0) / count_v
    inset_h = min(0.4, FRAME / cell_h)
    inset_v = min(0.4, FRAME / cell_v)

    def at(h, v):
        z = z0 + (z1 - z0) * v
        normal = outward_at(segment, h)
        return point_on(segment, h, z, SKIN, normal), normal

    for i in range(count_h):
        for j in range(count_v):
            h0 = i / count_h
            h1 = (i + 1) / count_h
            v0 = j / count_v
            v1 = (j + 1) / count_v
            hc = (h0 + h1) / 2
            zc = z0 + (z1 - z0) * (v0 + v1) / 2
            if skip(hc, zc):
                continue
            placed, normal = at(hc, (v0 + v1) / 2)
            incidence = facade.clamp(
                normal[0] * sun[0] + normal[1] * sun[1],
                0.0,
                1.0,
            )
            aperture = facade.lerp(APERTURE_MAX, APERTURE_MIN, incidence)
            color = facade.aperture_color(aperture, APERTURE_MIN, APERTURE_MAX)
            ih0 = facade.lerp(h0, h1, inset_h)
            ih1 = facade.lerp(h1, h0, inset_h)
            iv0 = facade.lerp(v0, v1, inset_v)
            iv1 = facade.lerp(v1, v0, inset_v)
            ch = (ih0 + ih1) / 2
            cv = (iv0 + iv1) / 2
            half_h = (ih1 - ih0) / 2 * aperture
            half_v = (iv1 - iv0) / 2 * aperture
            oh0, oh1 = ch - half_h, ch + half_h
            ov0, ov1 = cv - half_v, cv + half_v

            def quad(a0, a1, b0, b1):
                return [
                    at(a0, b0)[0],
                    at(a1, b0)[0],
                    at(a1, b1)[0],
                    at(a0, b1)[0],
                ]

            for border in (
                quad(h0, h1, v0, ov0),
                quad(h0, h1, ov1, v1),
                quad(h0, oh0, ov0, ov1),
                quad(oh1, h1, ov0, ov1),
            ):
                add_quad(mesh, border, color)

    for i in range(count_h + 1):
        h = i / count_h
        depth = facade.lerp(RIB_MIN, RIB_MAX, math.sin(math.pi * h))
        for j in range(count_v):
            v0 = j / count_v
            v1 = (j + 1) / count_v
            z_mid = z0 + (z1 - z0) * (v0 + v1) / 2
            if skip(h, z_mid):
                continue
            outer0, normal = at(h, v0)
            outer1, _ = at(h, v1)
            inner0 = (
                outer0[0] - normal[0] * depth,
                outer0[1] - normal[1] * depth,
                outer0[2],
            )
            inner1 = (
                outer1[0] - normal[0] * depth,
                outer1[1] - normal[1] * depth,
                outer1[2],
            )
            add_quad(rib_mesh, [outer0, inner0, inner1, outer1], (55, 50, 46))


def entrance_mesh(segment, z0, spec):
    """A framed opening, plus a canopy. Curved entrances follow the wall."""
    mesh = rhino3dm.Mesh()
    t0, t1 = spec["t0"], spec["t1"]
    head = z0 + spec["height"]
    samples = 10 if spec["kind"] == "curved" else 2
    band = []
    for i in range(samples):
        t = t0 + (t1 - t0) * i / (samples - 1)
        normal = outward_at(segment, t)
        band.append((t, normal))

    def ring(t, z, offset):
        normal = outward_at(segment, t)
        return point_on(segment, t, z, offset, normal)

    # Jambs and head around the opening, sitting just outside the skin.
    posts = (
        (t0, t0 + 0.04, z0, head),
        (t1 - 0.04, t1, z0, head),
        (t0, t1, head, head + 0.35),
    )
    for a, b, za, zb in posts:
        corners = [
            ring(a, za, SKIN),
            ring(b, za, SKIN),
            ring(b, zb, SKIN),
            ring(a, zb, SKIN),
        ]
        add_quad(mesh, corners, (232, 220, 198))

    # Canopy projects out from the head. The curved one is a strip of quads.
    reach = 2.8 if spec["kind"] == "curved" else 2.2
    for i in range(len(band) - 1):
        ta, tb = band[i][0], band[i + 1][0]
        quad = [
            ring(ta, head, SKIN),
            ring(tb, head, SKIN),
            ring(tb, head, SKIN + reach),
            ring(ta, head, SKIN + reach),
        ]
        add_quad(mesh, quad, (196, 122, 74))
        lip = [
            ring(ta, head, SKIN + reach),
            ring(tb, head, SKIN + reach),
            ring(tb, head + 0.18, SKIN + reach),
            ring(ta, head + 0.18, SKIN + reach),
        ]
        add_quad(mesh, lip, (176, 98, 52))

    if spec["kind"] == "corner":
        # A tall pier on the corner itself, past the opening.
        pier = [
            ring(1.0, z0, SKIN),
            ring(0.96, z0, SKIN + 0.55),
            ring(0.96, z0 + spec["height"] + 3.5, SKIN + 0.55),
            ring(1.0, z0 + spec["height"] + 3.5, SKIN),
        ]
        add_quad(mesh, pier, (232, 220, 198))
    return mesh


def ensure_layer(model, name, color):
    for index in range(len(model.Layers)):
        if model.Layers[index].Name == name:
            return index
    layer = rhino3dm.Layer()
    layer.Name = name
    layer.Color = (color[0], color[1], color[2], 255)
    return model.Layers.Add(layer)


def main():
    model = rhino3dm.File3dm.Read(str(SOURCE))
    facade_layer = ensure_layer(model, "ParametricFacade", (176, 78, 48))
    rib_layer = ensure_layer(model, "FacadeRibs", (55, 50, 46))
    entrance_layer = ensure_layer(model, "Entrances", (196, 122, 74))
    sun = sun_direction()

    extrusions = []
    for obj in list(model.Objects):
        geometry = obj.Geometry
        if geometry.ObjectType != rhino3dm.ObjectType.Extrusion:
            continue
        extrusions.append(geometry)

    for index, geometry in enumerate(extrusions):
        profile = geometry.Profile3d(0, 0.0)
        z0 = geometry.PathStart.Z
        z1 = geometry.PathEnd.Z
        spec = ENTRANCES[index]
        panels = rhino3dm.Mesh()
        ribs = rhino3dm.Mesh()
        for segment_index in range(profile.SegmentCount):
            segment = profile.SegmentCurve(segment_index)

            def skip(t, z, segment_index=segment_index, spec=spec, z0=z0):
                if segment_index != spec["segment"]:
                    return False
                return spec["t0"] <= t <= spec["t1"] and z <= z0 + spec["height"]

            panel_wall(panels, ribs, segment, z0, z1, skip, sun)

        entrance = entrance_mesh(profile.SegmentCurve(spec["segment"]), z0, spec)
        panel_attr = rhino3dm.ObjectAttributes()
        panel_attr.LayerIndex = facade_layer
        panel_attr.Name = "facade {}".format(index)
        rib_attr = rhino3dm.ObjectAttributes()
        rib_attr.LayerIndex = rib_layer
        rib_attr.Name = "ribs {}".format(index)
        door_attr = rhino3dm.ObjectAttributes()
        door_attr.LayerIndex = entrance_layer
        door_attr.Name = "{} entrance {}".format(spec["kind"], index)
        model.Objects.AddMesh(panels, panel_attr)
        model.Objects.AddMesh(ribs, rib_attr)
        model.Objects.AddMesh(entrance, door_attr)
        print(
            "massing {} {}: panels {} ribs {} entrance {}".format(
                index,
                spec["kind"],
                panels.Faces.Count,
                ribs.Faces.Count,
                entrance.Faces.Count,
            )
        )

    model.Write(str(OUTPUT), 7)
    print("wrote", OUTPUT)


if __name__ == "__main__":
    main()
