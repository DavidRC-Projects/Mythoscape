"""Cut-gem icons, faceted stones on the rings, and deed scrolls.

    blender --background --python render_gems_deeds.py
"""
import math
import os
import shutil

import bpy
import bmesh
import mathutils

OUT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "mmorpg", "assets", "items", "realistic"))
PACK = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "icons"))

GEMS = {
    "opal": ((0.93, 0.90, 0.84), 0.12),
    "jade": ((0.15, 0.62, 0.32), 0.1),
    "topaz": ((0.95, 0.58, 0.12), 0.16),
    "sapphire": ((0.12, 0.28, 0.92), 0.18),
    "emerald": ((0.05, 0.72, 0.34), 0.14),
    "ruby": ((0.82, 0.06, 0.10), 0.18),
    "diamond": ((0.92, 0.96, 1.0), 0.22),
    "onyx": ((0.10, 0.09, 0.13), 0.04),
}

RINGS = {
    "opal_ring": ((0.86, 0.66, 0.22), GEMS["opal"]),
    "jade_ring": ((0.86, 0.66, 0.22), GEMS["jade"]),
    "topaz_ring": ((0.86, 0.66, 0.22), GEMS["topaz"]),
    "sapphire_ring": ((0.86, 0.66, 0.22), GEMS["sapphire"]),
    "emerald_ring": ((0.86, 0.66, 0.22), GEMS["emerald"]),
    "ruby_ring": ((0.86, 0.66, 0.22), GEMS["ruby"]),
    "diamond_ring": ((0.86, 0.66, 0.22), GEMS["diamond"]),
    "onyx_ring": ((0.22, 0.20, 0.24), GEMS["onyx"]),
    "void_ring": ((0.10, 0.08, 0.14), ((0.55, 0.20, 0.95), 1.3)),
}

# wax color, optional emblem: "crown", "rose", "anchor"
DEEDS = {
    "deed_king": ((0.82, 0.58, 0.16), "crown"),
    "deed_gothic": ((0.42, 0.16, 0.58), None),
    "deed_white_rose": ((0.93, 0.90, 0.92), "rose"),
    "deed_sky_anchor": ((0.25, 0.55, 0.88), "anchor"),
    "deed_willow_cottage": ((0.55, 0.16, 0.14), None),
    "deed_reed_cottage": ((0.55, 0.16, 0.14), None),
    "deed_meadow_house": ((0.55, 0.16, 0.14), None),
    "deed_oak_villa": ((0.55, 0.16, 0.14), None),
    "deed_ash_manor": ((0.55, 0.16, 0.14), None),
    "deed_cedar_townhouse": ((0.55, 0.16, 0.14), None),
    "deed_stonehaven_row": ((0.55, 0.16, 0.14), None),
    "deed_riverview_estate": ((0.55, 0.16, 0.14), None),
    "deed_crown_villa": ((0.55, 0.16, 0.14), None),
    "deed_kings_folly": ((0.55, 0.16, 0.14), None),
}

MAJOR = 0.78
MINOR = 0.15


def clear_scene():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    scene = bpy.context.scene
    scene.render.engine = "BLENDER_EEVEE"
    scene.render.resolution_x = 256
    scene.render.resolution_y = 256
    scene.render.film_transparent = True
    scene.render.image_settings.file_format = "PNG"
    scene.render.image_settings.color_mode = "RGBA"
    scene.view_settings.view_transform = "Standard"
    if hasattr(scene, "eevee") and hasattr(scene.eevee, "taa_render_samples"):
        scene.eevee.taa_render_samples = 32
    world = bpy.data.worlds.new("IconWorld")
    scene.world = world
    world.use_nodes = True
    bg = world.node_tree.nodes["Background"]
    bg.inputs[0].default_value = (0.02, 0.02, 0.025, 1)
    bg.inputs[1].default_value = 0.15


def principled(name, color, metallic=0.0, roughness=0.2, transmission=0.0, emit=0.0):
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes["Principled BSDF"]
    bsdf.inputs["Base Color"].default_value = (*color, 1)
    bsdf.inputs["Metallic"].default_value = metallic
    bsdf.inputs["Roughness"].default_value = roughness
    for key in ("Transmission Weight", "Transmission"):
        if key in bsdf.inputs:
            bsdf.inputs[key].default_value = transmission
            break
    if "IOR" in bsdf.inputs:
        bsdf.inputs["IOR"].default_value = 2.2
    if emit:
        for key in ("Emission Color", "Emission"):
            if key in bsdf.inputs:
                bsdf.inputs[key].default_value = (*color, 1)
                break
        if "Emission Strength" in bsdf.inputs:
            bsdf.inputs["Emission Strength"].default_value = emit
    return mat


def assign(obj, mat):
    obj.data.materials.append(mat)
    return obj


def primitive(kind, loc, scale, mat, rot=(0, 0, 0), smooth=True):
    if kind == "cube":
        bpy.ops.mesh.primitive_cube_add(location=loc, rotation=rot)
    elif kind == "cyl":
        bpy.ops.mesh.primitive_cylinder_add(vertices=24, location=loc, rotation=rot)
    elif kind == "cone":
        bpy.ops.mesh.primitive_cone_add(vertices=12, location=loc, rotation=rot)
    else:
        bpy.ops.mesh.primitive_torus_add(
            major_segments=64, minor_segments=20,
            major_radius=MAJOR, minor_radius=MINOR,
            location=loc, rotation=rot,
        )
    obj = bpy.context.active_object
    obj.scale = scale
    assign(obj, mat)
    if smooth:
        bpy.ops.object.shade_smooth()
    else:
        bpy.ops.object.shade_flat()
    return obj


def cut_gem(name, loc, scale, mat, tilt=0.35):
    """Round brilliant: flat table, crown, girdle, pavilion. Flat facets."""
    mesh = bpy.data.meshes.new(name)
    bm = bmesh.new()
    n = 8
    girdle = []
    table = []
    for i in range(n):
        ang = (i + 0.5) * math.tau / n
        girdle.append(bm.verts.new((math.cos(ang), math.sin(ang), 0.0)))
        table.append(bm.verts.new((math.cos(ang) * 0.38, math.sin(ang) * 0.38, 0.48)))
    culet = bm.verts.new((0.0, 0.0, -0.62))
    bm.faces.new(table)
    for i in range(n):
        j = (i + 1) % n
        bm.faces.new((table[i], girdle[i], girdle[j], table[j]))
        bm.faces.new((girdle[i], culet, girdle[j]))
    bmesh.ops.recalc_face_normals(bm, faces=list(bm.faces))
    bm.to_mesh(mesh)
    bm.free()
    for poly in mesh.polygons:
        poly.use_smooth = False
    obj = bpy.data.objects.new(name, mesh)
    bpy.context.collection.objects.link(obj)
    obj.location = loc
    obj.scale = (scale, scale, scale)
    obj.rotation_euler = (tilt, 0.0, 0.4)
    assign(obj, mat)
    return obj


def look_at(ortho, location, target):
    key = bpy.data.lights.new("Key", "AREA")
    key.energy = 380
    key.size = 2.0
    key_ob = bpy.data.objects.new("Key", key)
    bpy.context.collection.objects.link(key_ob)
    key_ob.location = (1.8, -2.0, 3.2)
    fill = bpy.data.lights.new("Fill", "AREA")
    fill.energy = 120
    fill.size = 3
    fill_ob = bpy.data.objects.new("Fill", fill)
    bpy.context.collection.objects.link(fill_ob)
    fill_ob.location = (-2.2, -0.8, 1.8)
    rim = bpy.data.lights.new("Rim", "AREA")
    rim.energy = 160
    rim.color = (0.85, 0.9, 1.0)
    rim_ob = bpy.data.objects.new("Rim", rim)
    bpy.context.collection.objects.link(rim_ob)
    rim_ob.location = (0.2, 2.2, 1.4)
    cam_data = bpy.data.cameras.new("Cam")
    cam_data.type = "ORTHO"
    cam_data.ortho_scale = ortho
    cam_data.clip_start = 0.01
    cam_data.clip_end = 100
    cam = bpy.data.objects.new("Cam", cam_data)
    bpy.context.collection.objects.link(cam)
    cam.location = location
    aim = mathutils.Vector(target) - mathutils.Vector(cam.location)
    cam.rotation_euler = aim.to_track_quat("-Z", "Y").to_euler()
    bpy.context.scene.camera = cam


def build_loose_gem(name, color, emit):
    clear_scene()
    stone = principled(name, color, roughness=0.04, transmission=0.85, emit=emit)
    cut_gem(name + "_cut", (0, 0, 0), 0.95, stone, tilt=-0.55)
    look_at(2.3, (0.9, -2.4, 1.5), (0, 0, 0.05))


def build_ring(name, band_color, gem_color, emit):
    clear_scene()
    band = principled(name + "_band", band_color, metallic=1.0, roughness=0.18)
    primitive("torus", (0, 0, 0), (1, 1, 1), band)
    stone = principled(name + "_gem", gem_color, roughness=0.04, transmission=0.85, emit=emit)
    seat = (0.0, MAJOR + MINOR * 0.15, MINOR * 0.2)
    primitive("cyl", (seat[0], seat[1], seat[2] + 0.04), (0.16, 0.16, 0.03), band)
    cut_gem(name + "_cut", (seat[0], seat[1], seat[2] + 0.16), 0.2, stone, tilt=-0.15)
    look_at(2.55, (0.35, -2.15, 2.55), (0.0, 0.05, 0.15))


def build_deed(name, wax_color, emblem):
    clear_scene()
    page = principled(name + "_page", (0.78, 0.66, 0.46), roughness=0.72)
    roll = principled(name + "_roll", (0.55, 0.40, 0.24), roughness=0.65)
    ink = principled(name + "_ink", (0.28, 0.18, 0.10), roughness=0.8)
    wax = principled(name + "_wax", wax_color, roughness=0.35)
    # Rolls at the top and bottom, sheet between them, facing the camera (-Y).
    primitive("cyl", (0, 0.02, 0.78), (0.16, 0.16, 0.48), roll, (0, math.pi / 2, 0))
    primitive("cyl", (0, 0.02, -0.78), (0.15, 0.15, 0.46), roll, (0, math.pi / 2, 0))
    primitive("cube", (0, -0.02, 0.0), (0.42, 0.02, 0.72), page)
    for z in (0.38, 0.22, 0.06, -0.10):
        primitive("cube", (-0.02, -0.05, z), (0.26, 0.008, 0.018), ink, smooth=False)
    primitive("cyl", (0.08, -0.08, -0.42), (0.16, 0.16, 0.025), wax, (math.pi / 2, 0, 0))
    if emblem == "crown":
        gold = principled(name + "_crown", (0.95, 0.78, 0.28), metallic=1.0, roughness=0.25)
        primitive("cube", (0.08, -0.11, -0.42), (0.06, 0.015, 0.025), gold, (math.pi / 2, 0, 0), smooth=False)
        for x in (-0.045, 0.0, 0.045):
            primitive("cone", (0.08 + x, -0.12, -0.40), (0.018, 0.018, 0.028), gold, (math.pi / 2, 0, 0), smooth=False)
    elif emblem == "rose":
        petal = principled(name + "_rose", (0.75, 0.18, 0.28), roughness=0.4)
        primitive("cyl", (0.08, -0.11, -0.42), (0.05, 0.05, 0.012), petal, (math.pi / 2, 0, 0), smooth=False)
    elif emblem == "anchor":
        metal = principled(name + "_anchor", (0.85, 0.88, 0.92), metallic=1.0, roughness=0.3)
        primitive("cube", (0.08, -0.11, -0.44), (0.012, 0.012, 0.07), metal, smooth=False)
        primitive("cube", (0.08, -0.11, -0.40), (0.05, 0.012, 0.012), metal, smooth=False)
    look_at(2.15, (0.15, -2.6, 0.15), (0.0, 0.0, 0.0))


def save(filename):
    os.makedirs(OUT, exist_ok=True)
    os.makedirs(PACK, exist_ok=True)
    path = os.path.join(OUT, filename)
    bpy.context.scene.render.filepath = path
    bpy.ops.render.render(write_still=True)
    shutil.copyfile(path, os.path.join(PACK, filename))
    print("wrote", path)


def wanted(name):
    only = os.environ.get("ICON_ONLY")
    return not only or name in only.split(",")


def main():
    for name, (color, emit) in GEMS.items():
        if not wanted(name):
            continue
        build_loose_gem(name, color, emit)
        save(name + ".png")
    for name, (band, gem) in RINGS.items():
        if not wanted(name):
            continue
        build_ring(name, band, gem[0], gem[1])
        save(name + ".png")
    for name, (wax, emblem) in DEEDS.items():
        if not wanted(name):
            continue
        build_deed(name, wax, emblem)
        save(name + ".png")


if __name__ == "__main__":
    main()
