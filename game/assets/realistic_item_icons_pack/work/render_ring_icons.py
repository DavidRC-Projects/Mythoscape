"""Render ring icons with the stone set on the band, not in the hole.

    blender --background --python render_ring_icons.py
"""
import math
import os
import shutil

import bpy
import mathutils

OUT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "mmorpg", "assets", "items", "realistic"))
PACK = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "icons"))

# band rgb, gem rgb or None, gem emission strength
RINGS = {
    "gold_ring": ((0.86, 0.66, 0.22), None, 0.0),
    "opal_ring": ((0.86, 0.66, 0.22), (0.92, 0.88, 0.82), 0.15),
    "jade_ring": ((0.86, 0.66, 0.22), (0.20, 0.62, 0.32), 0.12),
    "topaz_ring": ((0.86, 0.66, 0.22), (0.92, 0.55, 0.12), 0.18),
    "sapphire_ring": ((0.86, 0.66, 0.22), (0.15, 0.32, 0.92), 0.2),
    "emerald_ring": ((0.86, 0.66, 0.22), (0.08, 0.72, 0.32), 0.16),
    "ruby_ring": ((0.86, 0.66, 0.22), (0.82, 0.08, 0.12), 0.2),
    "diamond_ring": ((0.86, 0.66, 0.22), (0.90, 0.95, 1.0), 0.25),
    "onyx_ring": ((0.22, 0.20, 0.24), (0.08, 0.07, 0.10), 0.05),
    "void_ring": ((0.10, 0.08, 0.14), (0.55, 0.22, 0.95), 1.4),
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


def metal(name, color, roughness=0.18):
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes["Principled BSDF"]
    bsdf.inputs["Base Color"].default_value = (*color, 1)
    bsdf.inputs["Metallic"].default_value = 1.0
    bsdf.inputs["Roughness"].default_value = roughness
    return mat


def gem_mat(name, color, emit):
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes["Principled BSDF"]
    bsdf.inputs["Base Color"].default_value = (*color, 1)
    bsdf.inputs["Metallic"].default_value = 0.0
    bsdf.inputs["Roughness"].default_value = 0.04
    for key in ("Transmission Weight", "Transmission"):
        if key in bsdf.inputs:
            bsdf.inputs[key].default_value = 0.9
            break
    if "IOR" in bsdf.inputs:
        bsdf.inputs["IOR"].default_value = 2.15
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


def primitive(kind, loc, scale, mat, rot=(0, 0, 0)):
    if kind == "uv":
        bpy.ops.mesh.primitive_uv_sphere_add(segments=16, ring_count=8, location=loc, rotation=rot)
    elif kind == "cube":
        bpy.ops.mesh.primitive_cube_add(location=loc, rotation=rot)
    elif kind == "cyl":
        bpy.ops.mesh.primitive_cylinder_add(vertices=16, location=loc, rotation=rot)
    elif kind == "cone":
        bpy.ops.mesh.primitive_cone_add(vertices=8, location=loc, rotation=rot)
    else:
        bpy.ops.mesh.primitive_torus_add(
            major_segments=64, minor_segments=20,
            major_radius=MAJOR, minor_radius=MINOR,
            location=loc, rotation=rot,
        )
    obj = bpy.context.active_object
    obj.scale = scale
    assign(obj, mat)
    bpy.ops.object.shade_smooth()
    return obj


def lights_and_camera():
    key = bpy.data.lights.new("Key", "AREA")
    key.energy = 350
    key.size = 2.2
    key_ob = bpy.data.objects.new("Key", key)
    bpy.context.collection.objects.link(key_ob)
    key_ob.location = (1.6, -1.8, 3.4)
    fill = bpy.data.lights.new("Fill", "AREA")
    fill.energy = 140
    fill.size = 3
    fill_ob = bpy.data.objects.new("Fill", fill)
    bpy.context.collection.objects.link(fill_ob)
    fill_ob.location = (-2.0, -0.6, 2.2)
    rim = bpy.data.lights.new("Rim", "AREA")
    rim.energy = 180
    rim.color = (0.8, 0.88, 1.0)
    rim_ob = bpy.data.objects.new("Rim", rim)
    bpy.context.collection.objects.link(rim_ob)
    rim_ob.location = (0.2, 2.4, 1.6)
    cam_data = bpy.data.cameras.new("Cam")
    cam_data.type = "ORTHO"
    cam_data.ortho_scale = 2.55
    cam_data.clip_start = 0.01
    cam_data.clip_end = 100
    cam = bpy.data.objects.new("Cam", cam_data)
    bpy.context.collection.objects.link(cam)
    cam.location = (0.35, -2.15, 2.55)
    aim = mathutils.Vector((0.0, 0.05, 0.15)) - mathutils.Vector(cam.location)
    cam.rotation_euler = aim.to_track_quat("-Z", "Y").to_euler()
    bpy.context.scene.camera = cam


def build_ring(name, band_color, gem_color, emit):
    clear_scene()
    band = metal(name + "_band", band_color)
    # Flat band. The hole stays empty; the stone is mounted on the far rim.
    primitive("torus", (0, 0, 0), (1, 1, 1), band)
    if gem_color:
        stone = gem_mat(name + "_gem", gem_color, emit)
        # Center of the tube at the top of the picture (far side, +Y).
        # Outer shoulder of the band, so the stone sits on the metal.
        seat = (0.0, MAJOR + MINOR * 0.25, MINOR * 0.35)
        primitive("cyl", (seat[0], seat[1], seat[2] + 0.03), (0.22, 0.22, 0.04), band)
        primitive("cone", (seat[0], seat[1], seat[2] + 0.24), (0.22, 0.22, 0.16), stone)
        primitive(
            "cone",
            (seat[0], seat[1], seat[2] + 0.08),
            (0.16, 0.16, 0.08),
            stone,
            (math.pi, 0, 0),
        )
        for ang in (0.5, 2.1, 3.7, 5.3):
            primitive(
                "cyl",
                (
                    seat[0] + math.cos(ang) * 0.16,
                    seat[1] + math.sin(ang) * 0.16,
                    seat[2] + 0.1,
                ),
                (0.022, 0.022, 0.09),
                band,
            )
    lights_and_camera()


def save(filename):
    os.makedirs(OUT, exist_ok=True)
    os.makedirs(PACK, exist_ok=True)
    path = os.path.join(OUT, filename)
    bpy.context.scene.render.filepath = path
    bpy.ops.render.render(write_still=True)
    shutil.copyfile(path, os.path.join(PACK, filename))
    print("wrote", path)


def main():
    only = os.environ.get("RING_ONLY")
    for name, (band, gem, emit) in RINGS.items():
        if only and name != only:
            continue
        build_ring(name, band, gem, emit)
        save(name + ".png")


if __name__ == "__main__":
    main()
