"""Blender — same facade as parametric_facade_grasshopper.py.

Run from Blender's Scripting workspace, or from a terminal:

  /Applications/Blender.app/Contents/MacOS/Blender --python parametric_facade_blender.py

Edit the values in PARAMS. Re-running replaces the ParametricFacade collection.
"""

import sys
from pathlib import Path

import bpy

COURSE = Path("/Users/evanwinther/Projects/f26_arch680_scripting")
here = Path(__file__).resolve().parent if "__file__" in dir() else COURSE
for folder in (here, COURSE):
    if str(folder) not in sys.path:
        sys.path.insert(0, str(folder))

import parametric_facade as facade

PARAMS = dict(
    width=24.0,
    depth=12.0,
    floor_height=3.6,
    floors=6,
    bays_x=16,
    bays_per_floor=2,
    camber=3.0,
    sun_azimuth=25.0,
    sun_altitude=42.0,
    aperture_min=0.18,
    aperture_max=0.82,
    frame=0.15,
    rib_min=0.28,
    rib_max=1.05,
)

COLLECTION = "ParametricFacade"


def collection():
    old = bpy.data.collections.get(COLLECTION)
    if old:
        for obj in list(old.objects):
            mesh = obj.data
            bpy.data.objects.remove(obj, do_unlink=True)
            if mesh and mesh.users == 0 and isinstance(mesh, bpy.types.Mesh):
                bpy.data.meshes.remove(mesh)
        bpy.data.collections.remove(old)
    col = bpy.data.collections.new(COLLECTION)
    bpy.context.scene.collection.children.link(col)
    return col


def mesh_object(name, loops, col, rgb, thickness=0.0, normals=None):
    mesh = bpy.data.meshes.new(name)
    verts = []
    faces = []
    for index, loop in enumerate(loops):
        base = len(verts)
        if thickness and normals is not None:
            n = normals[index]
            offset = tuple(c * thickness for c in n)
            for xyz in loop:
                verts.append(xyz)
            for xyz in loop:
                verts.append(tuple(xyz[i] + offset[i] for i in range(3)))
            faces.append((base, base + 1, base + 2, base + 3))
            faces.append((base + 4, base + 7, base + 6, base + 5))
            for k in range(4):
                a = base + k
                b = base + (k + 1) % 4
                faces.append((a, base + 4 + k, base + 4 + (k + 1) % 4, b))
        else:
            for xyz in loop:
                verts.append(xyz)
            faces.append((base, base + 1, base + 2, base + 3))
    mesh.from_pydata(verts, [], faces)
    mesh.update()
    obj = bpy.data.objects.new(name, mesh)
    col.objects.link(obj)
    mat = bpy.data.materials.get(name) or bpy.data.materials.new(name)
    mat.diffuse_color = (rgb[0], rgb[1], rgb[2], 1.0)
    if mat.name not in obj.data.materials:
        obj.data.materials.append(mat)
    return obj


def curve_object(name, points, col, rgb, bevel=0.04):
    curve = bpy.data.curves.new(name, type="CURVE")
    curve.dimensions = "3D"
    curve.bevel_depth = bevel
    spline = curve.splines.new("POLY")
    spline.points.add(len(points) - 1)
    for point, xyz in zip(spline.points, points):
        point.co = (xyz[0], xyz[1], xyz[2], 1.0)
    obj = bpy.data.objects.new(name, curve)
    col.objects.link(obj)
    mat = bpy.data.materials.get(name) or bpy.data.materials.new(name)
    mat.diffuse_color = (rgb[0], rgb[1], rgb[2], 1.0)
    if mat.name not in obj.data.materials:
        obj.data.materials.append(mat)
    return obj


def colored_panels(model, col):
    """Frame quads, so each bay keeps a hole sized by the sun."""
    mesh = bpy.data.meshes.new("panels")
    verts = []
    faces = []
    slot_for_face = []
    palette = {}
    for panel in model.panels:
        color = facade.aperture_color(
            panel.aperture, model.params.aperture_min, model.params.aperture_max
        )
        key = tuple(channel / 255.0 for channel in color)
        if key not in palette:
            palette[key] = len(palette)
        n = panel.normal
        offset = tuple(c * model.params.panel_thickness for c in n)
        for loop in panel.frame:
            base = len(verts)
            for xyz in loop:
                verts.append(xyz)
            for xyz in loop:
                verts.append(tuple(xyz[i] + offset[i] for i in range(3)))
            faces.append((base, base + 1, base + 2, base + 3))
            slot_for_face.append(palette[key])
            faces.append((base + 4, base + 7, base + 6, base + 5))
            slot_for_face.append(palette[key])
    mesh.from_pydata(verts, [], faces)
    for polygon, slot in zip(mesh.polygons, slot_for_face):
        polygon.material_index = slot
    mesh.update()
    obj = bpy.data.objects.new("panels", mesh)
    col.objects.link(obj)
    for key in palette:
        mat = bpy.data.materials.new("panel_{:02d}".format(palette[key]))
        mat.diffuse_color = (key[0], key[1], key[2], 1.0)
        obj.data.materials.append(mat)
    return obj


def main():
    model = facade.build(**PARAMS)
    col = collection()
    for key, value in PARAMS.items():
        col[key] = value

    colored_panels(model, col)
    mesh_object("walls", model.walls, col, (0.78, 0.76, 0.72))
    mesh_object("mullions", model.vertical_ribs, col, (0.28, 0.26, 0.24))
    spandrels = [quad for strip in model.horizontal_ribs for quad in strip]
    mesh_object("spandrels", spandrels, col, (0.36, 0.32, 0.28))

    origin = (0.0, model.params.depth + model.params.camber + 6.0, model.params.height * 0.55)
    tip = tuple(origin[i] + model.sun[i] * 8.0 for i in range(3))
    curve_object("sun", [origin, tip], col, (0.93, 0.72, 0.18), bevel=0.06)

    blend = COURSE / "parametric_facade.blend"
    bpy.ops.wm.save_as_mainfile(filepath=str(blend))
    print(
        "ParametricFacade: {} panels, height {:.2f} m, saved {}".format(
            len(model.panels), model.params.height, blend.name
        )
    )


main()
