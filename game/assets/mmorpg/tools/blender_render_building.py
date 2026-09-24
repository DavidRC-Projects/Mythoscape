"""
Blender script — build a simple cottage and render an orthographic PNG shell.

Run (with Blender installed):
  blender --background --python tools/blender_render_building.py -- cottage_nw

Output:
  client/assets/buildings/{id}.png
  client/assets/buildings/{id}.json

Matches the same pad_* metadata as bake_building_sprite.py so the pygame
client can swap between bake and Blender renders with no code changes.
"""
from __future__ import annotations

import json
import math
import os
import sys

try:
    import bpy
    from mathutils import Vector
except ImportError:
    print("This script must be run inside Blender:", file=sys.stderr)
    print("  blender --background --python blender_render_building.py -- cottage_nw", file=sys.stderr)
    sys.exit(1)

# --- paths ---
_SCRIPT = os.path.abspath(__file__)
_TOOLS = os.path.dirname(_SCRIPT)
_CLIENT = os.path.normpath(os.path.join(_TOOLS, "..", "client"))
_OUT = os.path.join(_CLIENT, "assets", "buildings")
_TEX = os.path.join(_CLIENT, "textures")

PAD_X = 0.14
PAD_TOP = 0.62
PAD_BOT = 0.10

# Tile footprint defaults (Elder’s Hall style 9×9)
DEFAULTS = {
    "cottage_nw": {"name": "Elder's Hall", "tiles": (9, 9), "wood": True},
    "cottage_ne": {"name": "General Store", "tiles": (9, 9), "wood": True},
    "cottage_sw": {"name": "The Resting Ox", "tiles": (9, 9), "wood": False},
    "cottage_se": {"name": "Farmhouse", "tiles": (9, 9), "wood": True},
    "bank": {"name": "Village Bank", "tiles": (9, 7), "wood": False},
}


def _argv_id():
    if "--" in sys.argv:
        i = sys.argv.index("--")
        if i + 1 < len(sys.argv):
            return sys.argv[i + 1]
    return "cottage_nw"


def _clear_scene():
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete(use_global=False)
    for block in (bpy.data.meshes, bpy.data.materials, bpy.data.images):
        for b in list(block):
            block.remove(b)


def _img_tex(mat, path, name):
    if not os.path.isfile(path):
        return None
    img = bpy.data.images.load(path)
    nodes = mat.node_tree.nodes
    links = mat.node_tree.links
    nodes.clear()
    out = nodes.new("ShaderNodeOutputMaterial")
    bsdf = nodes.new("ShaderNodeBsdfPrincipled")
    tex = nodes.new("ShaderNodeTexImage")
    tex.image = img
    tex.projection = "BOX"
    mapn = nodes.new("ShaderNodeTexCoord")
    links.new(mapn.outputs["Generated"], tex.inputs["Vector"])
    links.new(tex.outputs["Color"], bsdf.inputs["Base Color"])
    links.new(bsdf.outputs["BSDF"], out.inputs["Surface"])
    bsdf.inputs["Roughness"].default_value = 0.75
    return mat


def _mat(name, color, tex_file=None):
    mat = bpy.data.materials.new(name=name)
    mat.use_nodes = True
    path = os.path.join(_TEX, tex_file) if tex_file else None
    if path and _img_tex(mat, path, name):
        return mat
    bsdf = mat.node_tree.nodes.get("Principled BSDF")
    if bsdf:
        bsdf.inputs["Base Color"].default_value = (*color, 1.0)
        bsdf.inputs["Roughness"].default_value = 0.7
    return mat


def _add_box(name, loc, scale, mat):
    bpy.ops.mesh.primitive_cube_add(size=1, location=loc)
    obj = bpy.context.active_object
    obj.name = name
    obj.scale = scale
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    if obj.data.materials:
        obj.data.materials[0] = mat
    else:
        obj.data.materials.append(mat)
    return obj


def build_cottage(wood=True):
    """Unit cottage: footprint roughly 9×9 Blender units (1 unit ≈ 1 tile)."""
    wall = _mat(
        "Wall",
        (0.55, 0.42, 0.28) if wood else (0.45, 0.46, 0.48),
        "wood_planks.jpg" if wood else "brick.jpg",
    )
    roof = _mat(
        "Roof",
        (0.55, 0.28, 0.18) if wood else (0.3, 0.32, 0.36),
        "roof_terracotta.jpg" if wood else "roof_slate.jpg",
    )
    # Body
    _add_box("Body", (0, 0, 1.35), (8.2, 8.2, 2.7), wall)
    # Roof — two slanted slabs
    bpy.ops.mesh.primitive_cube_add(size=1, location=(0, 0, 3.2))
    r = bpy.context.active_object
    r.name = "Roof"
    r.scale = (9.2, 5.2, 0.35)
    r.rotation_euler[0] = math.radians(32)
    bpy.ops.object.transform_apply(location=False, rotation=True, scale=True)
    r.data.materials.append(roof)
    bpy.ops.mesh.primitive_cube_add(size=1, location=(0, 0, 3.2))
    r2 = bpy.context.active_object
    r2.name = "Roof2"
    r2.scale = (9.2, 5.2, 0.35)
    r2.rotation_euler[0] = math.radians(-32)
    bpy.ops.object.transform_apply(location=False, rotation=True, scale=True)
    r2.data.materials.append(roof)
    # Chimney
    _add_box("Chimney", (2.4, -1.5, 3.8), (0.7, 0.7, 1.4), _mat("Chim", (0.35, 0.36, 0.4)))
    # Door cut: boolean not required — we rely on camera framing; door painted
    # in post is optional. For true cutout, leave a dark recess:
    dark = _mat("DoorDark", (0.05, 0.04, 0.03))
    _add_box("DoorRecess", (0, 4.05, 0.85), (1.4, 0.25, 1.7), dark)


def setup_camera_light(tiles=(9, 9)):
    # Orthographic camera — slight RS-style top-down / south-facing
    bpy.ops.object.camera_add(location=(0, -14, 11))
    cam = bpy.context.active_object
    cam.data.type = "ORTHO"
    cam.data.ortho_scale = max(tiles) * 1.55
    cam.rotation_euler = (math.radians(58), 0, 0)
    bpy.context.scene.camera = cam

    bpy.ops.object.light_add(type="SUN", location=(6, -4, 12))
    sun = bpy.context.active_object
    sun.data.energy = 3.5
    sun.rotation_euler = (math.radians(40), math.radians(15), math.radians(-30))

    bpy.ops.object.light_add(type="AREA", location=(-5, 4, 6))
    fill = bpy.context.active_object
    fill.data.energy = 80
    fill.data.size = 8


def render(building_id: str, tiles=(9, 9), wood=True, name="Building"):
    _clear_scene()
    build_cottage(wood=wood)
    setup_camera_light(tiles)

    scene = bpy.context.scene
    scene.render.engine = "BLENDER_EEVEE_NEXT" if hasattr(bpy.types, "EEVEE") or True else "BLENDER_EEVEE"
    # Prefer EEVEE; fall back if missing
    try:
        scene.render.engine = "BLENDER_EEVEE_NEXT"
    except Exception:
        try:
            scene.render.engine = "BLENDER_EEVEE"
        except Exception:
            scene.render.engine = "CYCLES"

    ppt = 48
    fw, fh = tiles[0] * ppt, tiles[1] * ppt
    W = int(fw * (1 + 2 * PAD_X))
    H = int(fh * (1 + PAD_TOP + PAD_BOT))
    scene.render.resolution_x = W
    scene.render.resolution_y = H
    scene.render.film_transparent = True
    scene.render.image_settings.file_format = "PNG"
    scene.render.image_settings.color_mode = "RGBA"

    os.makedirs(_OUT, exist_ok=True)
    out_png = os.path.join(_OUT, f"{building_id}.png")
    scene.render.filepath = out_png
    bpy.ops.render.render(write_still=True)

    meta = {
        "id": building_id,
        "name": name,
        "source": "blender_render_building.py",
        "pad_x": PAD_X,
        "pad_y_top": PAD_TOP,
        "pad_y_bot": PAD_BOT,
        "ppt": ppt,
        "pixels": [W, H],
        "footprint_tiles": list(tiles),
    }
    with open(os.path.join(_OUT, f"{building_id}.json"), "w", encoding="utf-8") as f:
        json.dump(meta, f, indent=2)
    print(f"Rendered {out_png}")


def main():
    bid = _argv_id()
    cfg = DEFAULTS.get(bid, {"name": bid, "tiles": (9, 9), "wood": True})
    render(bid, tiles=cfg["tiles"], wood=cfg["wood"], name=cfg["name"])


if __name__ == "__main__":
    main()
