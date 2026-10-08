"""Low-poly Emberdeep props. Renders transparent sprites for the first-person view.

Run:
  blender --background --python game/assets/emberdeep_creatures_pack/blender/render_room_props.py
"""
import math
import os

import bpy
from mathutils import Vector


OUT = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", "props"))


def hex_rgb(h):
    h = h.ljust(7, "0")
    return tuple(int(h[i:i + 2], 16) / 255.0 for i in (1, 3, 5))


def material(name, color, emission=0.0, rough=0.55):
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    nodes = mat.node_tree.nodes
    links = mat.node_tree.links
    bsdf = nodes.get("Principled BSDF")
    out = nodes.get("Material Output")
    rgba = (*hex_rgb(color), 1.0)
    bsdf.inputs["Base Color"].default_value = rgba
    bsdf.inputs["Roughness"].default_value = rough
    if emission > 0:
        emit = nodes.new("ShaderNodeEmission")
        emit.inputs["Color"].default_value = rgba
        emit.inputs["Strength"].default_value = emission
        add = nodes.new("ShaderNodeAddShader")
        for link in list(out.inputs["Surface"].links):
            links.remove(link)
        links.new(bsdf.outputs["BSDF"], add.inputs[0])
        links.new(emit.outputs["Emission"], add.inputs[1])
        links.new(add.outputs["Shader"], out.inputs["Surface"])
    return mat


def link(obj, mat):
    if obj.data.materials:
        obj.data.materials[0] = mat
    else:
        obj.data.materials.append(mat)
    bpy.ops.object.select_all(action="DESELECT")
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj
    bpy.ops.object.shade_flat()
    return obj


def add(kind, mat, loc=(0, 0, 0), scale=(1, 1, 1), rot=(0, 0, 0), **kwargs):
    ops = {
        "ico": lambda: bpy.ops.mesh.primitive_ico_sphere_add(subdivisions=1, radius=1, location=loc),
        "uv": lambda: bpy.ops.mesh.primitive_uv_sphere_add(segments=8, ring_count=6, radius=1, location=loc),
        "cube": lambda: bpy.ops.mesh.primitive_cube_add(size=1, location=loc),
        "cyl": lambda: bpy.ops.mesh.primitive_cylinder_add(vertices=8, radius=1, depth=1, location=loc),
        "cone": lambda: bpy.ops.mesh.primitive_cone_add(vertices=8, radius1=1, depth=1, location=loc),
        "torus": lambda: bpy.ops.mesh.primitive_torus_add(
            major_segments=10, minor_segments=6, major_radius=1, minor_radius=0.18, location=loc,
        ),
    }
    ops[kind]()
    obj = bpy.context.active_object
    obj.scale = scale
    obj.rotation_euler = tuple(math.radians(a) for a in rot)
    if kind == "cyl" and kwargs.get("radius2") is not None:
        pass
    link(obj, mat)
    return obj


def clear():
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete()
    for block in (bpy.data.meshes, bpy.data.materials, bpy.data.lights, bpy.data.cameras):
        for item in list(block):
            if item.users == 0:
                block.remove(item)


def look_at(obj, target):
    direction = Vector(target) - obj.location
    obj.rotation_euler = direction.to_track_quat("-Z", "Y").to_euler()


def stage():
    world = bpy.context.scene.world
    if world is None:
        world = bpy.data.worlds.new("World")
        bpy.context.scene.world = world
    world.use_nodes = True
    bg = world.node_tree.nodes.get("Background")
    if bg:
        bg.inputs[0].default_value = (0.02, 0.015, 0.012, 1)
        bg.inputs[1].default_value = 0.4
    bpy.ops.object.light_add(type="SUN", location=(2, -3, 6))
    sun = bpy.context.active_object
    sun.data.energy = 3.2
    look_at(sun, (0, 0, 0.4))
    bpy.ops.object.light_add(type="AREA", location=(-2.4, -1.2, 2.4))
    fill = bpy.context.active_object
    fill.data.energy = 40
    fill.data.size = 3
    look_at(fill, (0, 0, 0.3))
    bpy.ops.object.camera_add(location=(2.15, -2.35, 1.55))
    cam = bpy.context.active_object
    look_at(cam, (0, 0, 0.35))
    cam.data.lens = 48
    bpy.context.scene.camera = cam


def render(name):
    scene = bpy.context.scene
    try:
        scene.render.engine = "BLENDER_EEVEE_NEXT"
    except TypeError:
        scene.render.engine = "BLENDER_EEVEE"
    scene.render.resolution_x = 256
    scene.render.resolution_y = 256
    scene.render.resolution_percentage = 100
    scene.render.film_transparent = True
    scene.render.image_settings.file_format = "PNG"
    scene.render.image_settings.color_mode = "RGBA"
    os.makedirs(OUT, exist_ok=True)
    scene.render.filepath = os.path.join(OUT, name + ".png")
    bpy.ops.render.render(write_still=True)


def egg(name, tilt=8, crack_angles=(20, 140, 250)):
    shell = material(name + "_shell", "#2c2826", rough=0.4)
    crack = material(name + "_crack", "#ff9a1f", emission=8.0, rough=0.2)
    nest = material(name + "_nest", "#6a5340", rough=0.7)
    add("uv", shell, loc=(0, 0, 0.58), scale=(0.42, 0.38, 0.58), rot=(tilt, 0, 8))
    for ang in crack_angles:
        rad = math.radians(ang + tilt)
        add(
            "cone", crack,
            loc=(math.cos(rad) * 0.36, math.sin(rad) * 0.34, 0.62),
            scale=(0.07, 0.05, 0.22),
            rot=(78, 0, ang),
        )
    for ang in range(0, 360, 45):
        rad = math.radians(ang)
        add(
            "ico", nest,
            loc=(math.cos(rad) * 0.58, math.sin(rad) * 0.58, 0.1),
            scale=(0.14, 0.11, 0.08),
            rot=(0, 0, ang),
        )


def ash_urn():
    clay = material("urn", "#5c4638", rough=0.62)
    ash = material("ash", "#8a8178", rough=0.8)
    ember = material("urn_ember", "#e07028", emission=2.2, rough=0.4)
    add("cyl", clay, loc=(0, 0, 0.38), scale=(0.34, 0.34, 0.7))
    add("cyl", clay, loc=(0, 0, 0.78), scale=(0.22, 0.22, 0.18))
    add("cone", clay, loc=(0, 0, 0.16), scale=(0.4, 0.4, 0.28))
    add("ico", ash, loc=(0.05, 0.02, 1.02), scale=(0.18, 0.14, 0.08))
    add("ico", ember, loc=(-0.02, 0.04, 1.08), scale=(0.1, 0.08, 0.07))
    add("cube", clay, loc=(0.28, 0.05, 0.42), scale=(0.08, 0.16, 0.28), rot=(0, 8, 12))


def candle_cluster():
    wax = material("wax", "#d7c7a2", rough=0.45)
    iron = material("iron", "#3e3a36", rough=0.4)
    flame = material("flame", "#ffb020", emission=12.0, rough=0.2)
    add("cyl", iron, loc=(0, 0, 0.06), scale=(0.55, 0.55, 0.08))
    for loc, h in (((-0.22, 0.05), 0.55), ((0.16, -0.08), 0.78), ((0.05, 0.18), 0.4)):
        add("cyl", wax, loc=(loc[0], loc[1], h / 2 + 0.08), scale=(0.08, 0.08, h))
        add("cone", flame, loc=(loc[0], loc[1], h + 0.22), scale=(0.07, 0.07, 0.22))


def coin_heap():
    gold = material("gold", "#e0b04a", rough=0.28)
    dark = material("gold_dark", "#a67c32", rough=0.35)
    for i, (x, y, z, s) in enumerate((
        (0, 0, 0.06, 0.22), (0.18, 0.06, 0.06, 0.18), (-0.16, 0.04, 0.06, 0.16),
        (0.04, -0.16, 0.06, 0.17), (0.02, 0.02, 0.14, 0.16), (-0.06, -0.02, 0.2, 0.12),
        (0.12, -0.04, 0.16, 0.11),
    )):
        add("cyl", gold if i % 2 == 0 else dark, loc=(x, y, z), scale=(s, s, 0.035), rot=(0, 0, i * 20))


def chain_stake():
    iron = material("stake", "#4a4744", rough=0.35)
    rust = material("rust", "#7a4a32", rough=0.55)
    bone = material("bone", "#cbb892", rough=0.4)
    add("cyl", iron, loc=(0, 0, 0.7), scale=(0.08, 0.08, 1.3))
    add("ico", iron, loc=(0, 0, 1.35), scale=(0.14, 0.14, 0.1))
    add("torus", rust, loc=(0.22, 0, 0.85), scale=(0.18, 0.18, 0.18), rot=(90, 0, 20))
    add("torus", rust, loc=(0.4, 0.05, 0.62), scale=(0.16, 0.16, 0.16), rot=(80, 10, 0))
    add("torus", rust, loc=(0.5, 0.02, 0.4), scale=(0.14, 0.14, 0.14), rot=(70, 0, -10))
    add("ico", bone, loc=(0.15, -0.2, 0.08), scale=(0.28, 0.1, 0.08), rot=(0, 10, 30))


def toadstool():
    cap = material("cap", "#6d3b42", rough=0.5)
    spot = material("spot", "#efe6c8", rough=0.4)
    stem = material("stem", "#d9d0be", rough=0.55)
    add("cyl", stem, loc=(0, 0, 0.28), scale=(0.12, 0.12, 0.5))
    add("ico", cap, loc=(0, 0, 0.58), scale=(0.48, 0.48, 0.22))
    for loc in ((0.12, 0.08, 0.72), (-0.16, 0.05, 0.7), (0.02, -0.16, 0.71)):
        add("ico", spot, loc=loc, scale=(0.08, 0.08, 0.04))
    add("cyl", stem, loc=(0.38, 0.22, 0.16), scale=(0.07, 0.07, 0.28))
    add("ico", cap, loc=(0.38, 0.22, 0.34), scale=(0.22, 0.22, 0.1))


def cinder_vent():
    rock = material("vent_rock", "#3a3532", rough=0.7)
    lava = material("vent_lava", "#ff6a12", emission=10.0, rough=0.2)
    add("cyl", lava, loc=(0, 0, 0.1), scale=(0.34, 0.34, 0.1))
    for i, ang in enumerate(range(0, 360, 40)):
        rad = math.radians(ang)
        add(
            "ico", rock,
            loc=(math.cos(rad) * 0.42, math.sin(rad) * 0.42, 0.14),
            scale=(0.18, 0.14, 0.16),
            rot=(0, 0, ang),
        )


BUILDS = {
    "dragon_egg": lambda: egg("egg_a", 6, (30, 150, 260)),
    "dragon_egg_b": lambda: egg("egg_b", -12, (70, 190, 310)),
    "dragon_egg_c": lambda: egg("egg_c", 16, (10, 120, 220)),
    "ash_urn": ash_urn,
    "candle_cluster": candle_cluster,
    "coin_heap": coin_heap,
    "chain_stake": chain_stake,
    "toadstool": toadstool,
    "cinder_vent": cinder_vent,
}


if __name__ == "__main__":
    for name, build in BUILDS.items():
        clear()
        stage()
        build()
        render(name)
        print("rendered", name)
