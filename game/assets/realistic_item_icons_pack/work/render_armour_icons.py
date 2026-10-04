"""Render detailed helmet and cleaver icons. Blender 5, background mode.

    blender --background --python render_armour_icons.py
"""
import math
import os

import bpy

OUT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "mmorpg", "assets", "items", "realistic"))
PACK = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "icons"))

METALS = {
    "bronze_helmet": ((0.72, 0.42, 0.18), (0.45, 0.22, 0.08), False, False),
    "iron_helmet": ((0.62, 0.64, 0.68), (0.28, 0.30, 0.34), False, False),
    "steel_helmet": ((0.78, 0.80, 0.84), (0.35, 0.38, 0.42), True, False),
    "mithril_helmet": ((0.55, 0.82, 0.95), (0.15, 0.35, 0.55), True, False),
    "adamant_helmet": ((0.28, 0.72, 0.38), (0.08, 0.28, 0.12), True, True),
    "mythos_helmet": ((0.62, 0.35, 0.85), (0.22, 0.08, 0.35), True, True),
    "eclipse_helmet": ((0.12, 0.10, 0.14), (0.95, 0.72, 0.28), True, True),
}


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


def metal(name, color, roughness=0.22, emission=None, emit_strength=0.0):
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes["Principled BSDF"]
    bsdf.inputs["Base Color"].default_value = (*color, 1)
    bsdf.inputs["Metallic"].default_value = 1.0
    bsdf.inputs["Roughness"].default_value = roughness
    if emission and emit_strength:
        for key in ("Emission Color", "Emission"):
            if key in bsdf.inputs:
                bsdf.inputs[key].default_value = (*emission, 1)
                break
        if "Emission Strength" in bsdf.inputs:
            bsdf.inputs["Emission Strength"].default_value = emit_strength
    return mat


def leather():
    mat = bpy.data.materials.new("Leather")
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes["Principled BSDF"]
    bsdf.inputs["Base Color"].default_value = (0.28, 0.14, 0.07, 1)
    bsdf.inputs["Roughness"].default_value = 0.72
    return mat


def assign(obj, mat):
    obj.data.materials.append(mat)
    return obj


def primitive(kind, loc, scale, mat, rot=(0, 0, 0)):
    if kind == "uv":
        bpy.ops.mesh.primitive_uv_sphere_add(segments=48, ring_count=24, location=loc, rotation=rot)
    elif kind == "cube":
        bpy.ops.mesh.primitive_cube_add(location=loc, rotation=rot)
    elif kind == "cyl":
        bpy.ops.mesh.primitive_cylinder_add(vertices=24, location=loc, rotation=rot)
    else:
        bpy.ops.mesh.primitive_cone_add(vertices=24, location=loc, rotation=rot)
    obj = bpy.context.active_object
    obj.scale = scale
    assign(obj, mat)
    if kind != "cube":
        bpy.ops.object.shade_smooth()
    return obj


def lights_and_camera(target=(0, 0, 0.35), distance=4.2):
    import mathutils
    key = bpy.data.lights.new("Key", "AREA")
    key.energy = 400
    key.size = 2.5
    key_ob = bpy.data.objects.new("Key", key)
    bpy.context.collection.objects.link(key_ob)
    key_ob.location = (2.4, -2.2, 3.2)
    fill = bpy.data.lights.new("Fill", "AREA")
    fill.energy = 160
    fill.size = 3
    fill_ob = bpy.data.objects.new("Fill", fill)
    bpy.context.collection.objects.link(fill_ob)
    fill_ob.location = (-2.2, -1.4, 1.6)
    rim = bpy.data.lights.new("Rim", "AREA")
    rim.energy = 220
    rim.color = (0.75, 0.85, 1.0)
    rim_ob = bpy.data.objects.new("Rim", rim)
    bpy.context.collection.objects.link(rim_ob)
    rim_ob.location = (-0.4, 2.6, 2.2)
    cam_data = bpy.data.cameras.new("Cam")
    cam_data.type = "ORTHO"
    cam_data.ortho_scale = 3.4
    cam_data.clip_start = 0.01
    cam_data.clip_end = 100
    cam = bpy.data.objects.new("Cam", cam_data)
    bpy.context.collection.objects.link(cam)
    cam.location = (distance * 0.62, -distance * 0.72, distance * 0.42)
    aim = mathutils.Vector(target) - mathutils.Vector(cam.location)
    cam.rotation_euler = aim.to_track_quat("-Z", "Y").to_euler()
    bpy.context.scene.camera = cam


def build_helmet(name, color, accent, crest, visor):
    clear_scene()
    plate = metal(name + "_plate", color, 0.28)
    dark = metal(name + "_dark", tuple(max(0.02, c * 0.45) for c in color), 0.45)
    trim = metal(
        name + "_trim", accent, 0.2,
        emission=accent if name.startswith("eclipse") else None,
        emit_strength=1.6 if name.startswith("eclipse") else 0,
    )
    # Solid dome. The brim sits under it so the silhouette reads as a helm.
    primitive("uv", (0, 0, 0.55), (0.95, 0.82, 0.62), plate)
    primitive("cyl", (0, 0, 0.18), (1.15, 1.0, 0.07), trim)
    primitive("cyl", (0, 0, 0.02), (1.28, 1.12, 0.045), dark)
    # Brow, nasal, and cheek plates, facing the camera (negative Y).
    primitive("cube", (0, -0.55, 0.48), (0.72, 0.08, 0.08), trim)
    primitive("cube", (0, -0.72, 0.22), (0.12, 0.1, 0.38), plate)
    primitive("cube", (-0.55, -0.48, 0.16), (0.1, 0.22, 0.32), plate, (0.15, 0, 0.35))
    primitive("cube", (0.55, -0.48, 0.16), (0.1, 0.22, 0.32), plate, (0.15, 0, -0.35))
    for i in range(6):
        ang = -0.7 + i * 0.28
        primitive(
            "uv",
            (math.sin(ang) * 1.05, -math.cos(ang) * 0.15 - 0.15, 0.2),
            (0.055, 0.055, 0.055),
            trim,
        )
    if visor:
        primitive("cube", (0, -0.78, 0.4), (0.42, 0.04, 0.05), dark)
    if crest:
        primitive("cube", (0, 0, 1.15), (0.07, 0.16, 0.28), trim)
        primitive("uv", (0, -0.12, 1.02), (0.11, 0.11, 0.11), trim)
    if name.startswith("eclipse"):
        primitive("uv", (0, -0.2, 0.95), (0.14, 0.14, 0.14), trim)
    lights_and_camera(target=(0, -0.1, 0.5))
    bpy.context.scene.camera.data.ortho_scale = 2.7


def build_cleaver():
    clear_scene()
    blade = metal("blade", (0.38, 0.36, 0.4), 0.28)
    edge = metal("edge", (0.95, 0.75, 0.28), 0.18, emission=(1.0, 0.72, 0.2), emit_strength=0.8)
    grip_mat = leather()
    pommel = metal("pommel", (0.75, 0.58, 0.24), 0.28)
    # Tall blade. The gold edge sits on the face the camera sees.
    primitive("cube", (0.0, 0.05, 0.35), (0.22, 0.42, 0.78), blade)
    primitive("cube", (0.16, 0.28, 0.68), (0.12, 0.16, 0.2), blade, (0, 0, 0.4))
    primitive("cube", (0.0, -0.4, 0.28), (0.2, 0.03, 0.7), edge)
    primitive("cube", (0.0, -0.38, 0.55), (0.06, 0.02, 0.28), edge)
    for z in (0.05, 0.22):
        primitive("uv", (0.0, 0.0, z), (0.05, 0.05, 0.05), pommel)
    primitive("cyl", (0.0, 0.0, -0.45), (0.1, 0.1, 0.32), grip_mat)
    primitive("cyl", (0.0, 0.0, -0.22), (0.13, 0.13, 0.035), pommel)
    primitive("cyl", (0.0, 0.0, -0.68), (0.13, 0.13, 0.035), pommel)
    primitive("uv", (0.0, 0.0, -0.82), (0.14, 0.14, 0.09), pommel)
    lights_and_camera(target=(0.0, 0.0, 0.05))
    bpy.context.scene.camera.data.ortho_scale = 2.8


def save(filename):
    os.makedirs(OUT, exist_ok=True)
    os.makedirs(PACK, exist_ok=True)
    path = os.path.join(OUT, filename)
    bpy.context.scene.render.filepath = path
    bpy.ops.render.render(write_still=True)
    pack = os.path.join(PACK, filename)
    if path != pack:
        import shutil
        shutil.copyfile(path, pack)
    print("wrote", path)


def main():
    for name, (color, accent, crest, visor) in METALS.items():
        build_helmet(name, color, accent, crest, visor)
        save(name + ".png")
    build_cleaver()
    save("eclipse_cleaver.png")


if __name__ == "__main__":
    main()
