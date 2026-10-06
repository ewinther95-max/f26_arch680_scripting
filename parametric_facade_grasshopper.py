"""Grasshopper / Rhino 8 — facade on a massing.

Paste this into a Grasshopper Python 3 Script component.

The massing is, in order:
  1. a Grasshopper input named massing (Brep, Extrusion, Surface, or Mesh)
  2. whatever is selected in the Rhino document
  3. objects on a layer named Massing
  4. the built-in study bar, if none of those exist

Vertical faces are divided into bays about `module` metres wide.
Openings shrink where the face looks at the sun. Mullions deepen
toward the middle of each face. Roofs and soffits are left alone.

Sun azimuth is degrees clockwise from north (+Y). 180 faces the facade
from the south. Altitude is degrees above the horizon.

Optional inputs: massing, module, sun_azimuth, sun_altitude,
aperture_min, aperture_max, frame, rib_min, rib_max, skin_gap.

With no massing connected, these also apply to the study bar:
width, depth, floor_height, floors, bays_x, bays_per_floor, camber.
"""

import math
import sys
from pathlib import Path

import Rhino
import Rhino.Geometry as rg
import System.Drawing as drawing

COURSE = Path("/Users/evanwinther/Projects/f26_arch680_scripting")
here = Path(__file__).resolve().parent if "__file__" in dir() else COURSE
for folder in (here, COURSE):
    if str(folder) not in sys.path:
        sys.path.insert(0, str(folder))

import parametric_facade as facade

ROOF = 0.7


def given(name, default):
    if name in globals() and globals()[name] is not None:
        return globals()[name]
    return default


def flatten(value):
    if value is None:
        return []
    if hasattr(value, "AllData"):
        return list(value.AllData())
    if isinstance(value, (list, tuple)):
        return list(value)
    return [value]


def as_brep(geo):
    if geo is None:
        return None
    if hasattr(geo, "Value"):
        return as_brep(geo.Value)
    if isinstance(geo, rg.Brep):
        return geo
    if isinstance(geo, rg.Extrusion):
        return geo.ToBrep()
    if isinstance(geo, rg.Surface):
        return geo.ToBrep()
    if isinstance(geo, rg.Mesh):
        return rg.Brep.CreateFromMesh(geo, False)
    return None


def sun_vector(azimuth, altitude):
    az = math.radians(azimuth)
    alt = math.radians(altitude)
    horizontal = math.cos(alt)
    vector = rg.Vector3d(math.sin(az) * horizontal, math.cos(az) * horizontal, math.sin(alt))
    vector.Unitize()
    return vector


def collect_massing(rhino):
    found = []
    for item in flatten(given("massing", None)):
        brep = as_brep(item)
        if brep is not None:
            found.append(brep)
    if found or rhino is None:
        return found

    selected = []
    for obj in rhino.Objects:
        if obj.Attributes.LayerIndex == facade_layer(rhino, create=False):
            continue
        if obj.IsSelected(False):
            brep = as_brep(obj.Geometry)
            if brep is not None:
                selected.append(brep)
    if selected:
        return selected

    for name in ("Massing", "massing", "MASSING"):
        index = rhino.Layers.FindName(name)
        if index < 0:
            continue
        for obj in rhino.Objects:
            if obj.Attributes.LayerIndex != index:
                continue
            brep = as_brep(obj.Geometry)
            if brep is not None:
                found.append(brep)
        break
    return found


def facade_layer(rhino, create):
    if rhino is None:
        return -1
    index = rhino.Layers.FindName("ParametricFacade")
    if index < 0 and create:
        index = rhino.Layers.Add("ParametricFacade")
    return index


def color_for(aperture, low, high):
    red, green, blue = facade.aperture_color(aperture, low, high)
    return drawing.Color.FromArgb(255, red, green, blue)


def quad_mesh(loops, colors):
    mesh = rg.Mesh()
    for loop, color in zip(loops, colors):
        start = mesh.Vertices.Count
        for xyz in loop:
            mesh.Vertices.Add(xyz.X, xyz.Y, xyz.Z)
            mesh.VertexColors.Add(color)
        mesh.Faces.AddFace(start, start + 1, start + 2, start + 3)
    mesh.Normals.ComputeNormals()
    mesh.Compact()
    return mesh


def curve_of(loop):
    polyline = rg.Polyline(loop)
    if polyline[0].DistanceTo(polyline[-1]) > 1e-6:
        polyline.Add(polyline[0])
    return polyline.ToNurbsCurve()


def skin_brep(brep, sun, module, aperture_min, aperture_max, frame, rib_min, rib_max, skin_gap):
    frames = []
    frame_colors = []
    ribs = []
    openings = []
    for face in brep.Faces:
        sample = face.NormalAt(face.Domain(0).Mid, face.Domain(1).Mid)
        sample.Unitize()
        if abs(sample.Z) > ROOF:
            continue
        piece = skin_face(
            face, sun, module, aperture_min, aperture_max, frame, rib_min, rib_max, skin_gap
        )
        frames.extend(piece[0])
        frame_colors.extend(piece[1])
        ribs.extend(piece[2])
        openings.extend(piece[3])
    return frames, frame_colors, ribs, openings


def skin_face(face, sun, module, aperture_min, aperture_max, frame, rib_min, rib_max, skin_gap):
    udomain = face.Domain(0)
    vdomain = face.Domain(1)
    origin = face.PointAt(udomain.T0, vdomain.T0)
    along_u = face.PointAt(udomain.T1, vdomain.T0) - origin
    along_v = face.PointAt(udomain.T0, vdomain.T1) - origin
    u_horizontal = abs(along_u.Z) <= abs(along_v.Z)
    span_h = along_u.Length if u_horizontal else along_v.Length
    span_v = along_v.Length if u_horizontal else along_u.Length
    if span_h < frame * 3 or span_v < frame * 3:
        return [], [], [], []

    count_h = max(1, int(round(span_h / module)))
    count_v = max(1, int(round(span_v / module)))
    cell_h = span_h / count_h
    cell_v = span_v / count_v
    inset_h = min(0.42, frame / cell_h)
    inset_v = min(0.42, frame / cell_v)

    def place(h, v, offset):
        if u_horizontal:
            u = udomain.ParameterAt(h)
            vpar = vdomain.ParameterAt(v)
        else:
            u = udomain.ParameterAt(v)
            vpar = vdomain.ParameterAt(h)
        if face.IsPointOnFace(u, vpar) == rg.PointFaceRelation.Exterior:
            return None
        point = face.PointAt(u, vpar)
        normal = face.NormalAt(u, vpar)
        normal.Unitize()
        point += normal * offset
        return point, normal

    frames = []
    colors = []
    openings = []
    for i in range(count_h):
        for j in range(count_v):
            h0 = i / float(count_h)
            h1 = (i + 1) / float(count_h)
            v0 = j / float(count_v)
            v1 = (j + 1) / float(count_v)
            center = place((h0 + h1) / 2, (v0 + v1) / 2, skin_gap)
            if center is None:
                continue
            incidence = facade.clamp(center[1] * sun, 0.0, 1.0)
            aperture = facade.lerp(aperture_max, aperture_min, incidence)
            ih0 = facade.lerp(h0, h1, inset_h)
            ih1 = facade.lerp(h1, h0, inset_h)
            iv0 = facade.lerp(v0, v1, inset_v)
            iv1 = facade.lerp(v1, v0, inset_v)
            hc = (ih0 + ih1) / 2
            vc = (iv0 + iv1) / 2
            half_h = (ih1 - ih0) / 2 * aperture
            half_v = (iv1 - iv0) / 2 * aperture
            oh0, oh1 = hc - half_h, hc + half_h
            ov0, ov1 = vc - half_v, vc + half_v

            def quad(a0, a1, b0, b1):
                corners = []
                for h, v in ((a0, b0), (a1, b0), (a1, b1), (a0, b1)):
                    hit = place(h, v, skin_gap)
                    if hit is None:
                        return None
                    corners.append(hit[0])
                return corners

            borders = (
                quad(h0, h1, v0, ov0),
                quad(h0, h1, ov1, v1),
                quad(h0, oh0, ov0, ov1),
                quad(oh1, h1, ov0, ov1),
            )
            if any(border is None for border in borders):
                continue
            tint = color_for(aperture, aperture_min, aperture_max)
            for border in borders:
                frames.append(border)
                colors.append(tint)
            hole = quad(oh0, oh1, ov0, ov1)
            if hole is not None:
                openings.append(curve_of(hole))

    rib_quads = []

    def rib_at(h, v0, v1, depth):
        start = place(h, v0, skin_gap)
        end = place(h, v1, skin_gap)
        if start is None or end is None:
            return
        outer0, normal0 = start
        outer1, normal1 = end
        rib_quads.append([
            outer0,
            outer0 - normal0 * depth,
            outer1 - normal1 * depth,
            outer1,
        ])

    for i in range(count_h + 1):
        h = i / float(count_h)
        depth = facade.lerp(rib_min, rib_max, math.sin(math.pi * h))
        for j in range(count_v):
            rib_at(h, j / float(count_v), (j + 1) / float(count_v), depth)
    for j in range(count_v + 1):
        v = j / float(count_v)
        for i in range(count_h):
            h0 = i / float(count_h)
            h1 = (i + 1) / float(count_h)
            d0 = facade.lerp(rib_min, rib_max, math.sin(math.pi * h0))
            d1 = facade.lerp(rib_min, rib_max, math.sin(math.pi * h1))
            a = place(h0, v, skin_gap)
            b = place(h1, v, skin_gap)
            if a is None or b is None:
                continue
            rib_quads.append([
                a[0],
                b[0],
                b[0] - b[1] * d1,
                a[0] - a[1] * d0,
            ])
    return frames, colors, rib_quads, openings


def study_bar():
    model = facade.build(
        width=float(given("width", 24)),
        depth=float(given("depth", 12)),
        floor_height=float(given("floor_height", 3.6)),
        floors=int(given("floors", 6)),
        bays_x=int(given("bays_x", 16)),
        bays_per_floor=int(given("bays_per_floor", 2)),
        camber=float(given("camber", 3)),
        sun_azimuth=float(given("sun_azimuth", 180)),
        sun_altitude=float(given("sun_altitude", 42)),
        aperture_min=float(given("aperture_min", 0.18)),
        aperture_max=float(given("aperture_max", 0.82)),
        frame=float(given("frame", 0.15)),
        rib_min=float(given("rib_min", 0.28)),
        rib_max=float(given("rib_max", 1.05)),
    )
    frames = []
    colors = []
    for panel in model.panels:
        tint = color_for(panel.aperture, model.params.aperture_min, model.params.aperture_max)
        for loop in panel.frame:
            frames.append([rg.Point3d(*xyz) for xyz in loop])
            colors.append(tint)
    rib_quads = []
    for loop in model.vertical_ribs:
        rib_quads.append([rg.Point3d(*xyz) for xyz in loop])
    for strip in model.horizontal_ribs:
        for loop in strip:
            rib_quads.append([rg.Point3d(*xyz) for xyz in loop])
    walls = [[rg.Point3d(*xyz) for xyz in loop] for loop in model.walls]
    origin = rg.Point3d(0.0, model.params.depth + model.params.camber + 6.0, model.params.height * 0.55)
    sun_line = rg.Line(origin, origin + rg.Vector3d(*model.sun) * 8.0)
    return frames, colors, rib_quads, walls, sun_line


rhino = Rhino.RhinoDoc.ActiveDoc
module = float(given("module", 1.5))
azimuth = float(given("sun_azimuth", 180))
altitude = float(given("sun_altitude", 42))
aperture_min = float(given("aperture_min", 0.18))
aperture_max = float(given("aperture_max", 0.82))
frame = float(given("frame", 0.15))
rib_min = float(given("rib_min", 0.28))
rib_max = float(given("rib_max", 1.05))
skin_gap = float(given("skin_gap", 0.05))
sun_dir = sun_vector(azimuth, altitude)

massing_breps = collect_massing(rhino)
source = "massing"
if massing_breps:
    frame_loops = []
    frame_colors = []
    rib_loops = []
    openings = []
    box = rg.BoundingBox.Empty
    for brep in massing_breps:
        frames, colors, rib_quads, holes = skin_brep(
            brep, sun_dir, module, aperture_min, aperture_max, frame, rib_min, rib_max, skin_gap
        )
        frame_loops.extend(frames)
        frame_colors.extend(colors)
        rib_loops.extend(rib_quads)
        openings.extend(holes)
        box.Union(brep.GetBoundingBox(True))
    walls = rg.Mesh()
    center = box.Center
    sun = rg.Line(center, center + sun_dir * max(box.Diagonal.Length * 0.35, 4.0))
else:
    source = "study bar"
    frame_loops, frame_colors, rib_loops, wall_loops, sun = study_bar()
    openings = []
    walls = quad_mesh(wall_loops, [drawing.Color.FromArgb(255, 210, 206, 198)] * len(wall_loops))

panels = quad_mesh(frame_loops, frame_colors) if frame_loops else rg.Mesh()
rib_colors = [drawing.Color.FromArgb(255, 55, 50, 46)] * len(rib_loops)
ribs = quad_mesh(rib_loops, rib_colors) if rib_loops else rg.Mesh()

if rhino is not None:
    layer_index = facade_layer(rhino, create=True)
    stale = [obj.Id for obj in rhino.Objects if obj.Attributes.LayerIndex == layer_index]
    for object_id in stale:
        rhino.Objects.Delete(object_id, True)
    attributes = Rhino.DocObjects.ObjectAttributes()
    attributes.LayerIndex = layer_index
    if panels.Faces.Count:
        rhino.Objects.AddMesh(panels, attributes)
    if ribs.Faces.Count:
        rhino.Objects.AddMesh(ribs, attributes)
    if isinstance(walls, rg.Mesh) and walls.Faces.Count:
        rhino.Objects.AddMesh(walls, attributes)
    rhino.Objects.AddLine(sun, attributes)
    rhino.Views.Redraw()

print("facade source: {} ({} faces)".format(source, panels.Faces.Count))
