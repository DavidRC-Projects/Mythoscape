"""entrance_loader.py - drop-in Panda3D helper for the Blender-built dungeon entrances.

    from entrance_loader import load_entrance, add_entrance_collision
    model, meta = load_entrance(base.loader, "assets/dungeons/glb/goblin_cave.glb")
    model.reparent_to(render); model.set_pos(x, y, z); model.set_h(heading)
    solids, trigger_np = add_entrance_collision(model, meta)   # optional (3D route)

* Loads .glb (needs `pip install panda3d-gltf`, which auto-registers the loader on
  Panda3D >= 1.10.4) or a pre-converted .bam - same call.
* Put `gltf-legacy-materials true` in your PRC (done below if not already set) so the
  materials become plain fixed-function Materials that work with set_shader_off().
* glTF stores colours in LINEAR space. The fixed-function pipeline does not convert back,
  so without a fix everything renders too dark. `srgb_fix=True` converts every material's
  colour back to sRGB once at load time so the in-engine colours match the Blender concept
  and the monster pack's hex palette.
* Metadata (collision boxes, doorway trigger, bounds) comes from json/<key>.json, which
  the Blender script writes next to the glb. Coordinates are model-space metres, Z up,
  entrance front facing -Y.
"""
import json
import os

from panda3d.core import (ConfigVariableBool, Material, ShadeModelAttrib, MaterialAttrib,
                          loadPrcFileData, CollisionBox, CollisionNode, Point3, BitMask32,
                          AmbientLight, DirectionalLight, LColor, AntialiasAttrib, Fog)

# The entrances face -Y, the monster pack's creatures face +Y. Same sun, heading mirrored
# so the entrance front is lit from the camera side (front-right, 45 deg down).
ENTRANCE_SUN_HPR = (20, -45, 0)

if not ConfigVariableBool("gltf-legacy-materials", False).get_value():
    loadPrcFileData("entrance_loader", "gltf-legacy-materials true")


def _lin_to_srgb(c):
    c = max(0.0, min(1.0, c))
    return c * 12.92 if c <= 0.0031308 else 1.055 * c ** (1 / 2.4) - 0.055


def _osrs_material(src, srgb_fix=True, glow=False):
    """New fixed-function Material from a glTF one: sRGB colour, ambient = diffuse,
    no specular. (Loaded Materials are attrib-locked, so we build fresh ones.)"""
    conv = _lin_to_srgb if srgb_fix else (lambda c: c)
    d = src.get_diffuse() if src.has_diffuse() else (src.get_base_color() if src.has_base_color() else LColor(1))
    col = LColor(conv(d[0]), conv(d[1]), conv(d[2]), d[3])
    m = Material(src.get_name())
    m.set_diffuse(col)
    # glTF has no ambient colour; without one the fixed-function pipeline treats the
    # surface as WHITE under ambient light and everything washes out.
    m.set_ambient(col)
    m.set_specular(LColor(0, 0, 0, 1))
    m.set_shininess(0)
    if glow:
        # panda3d-gltf's legacy mode drops glTF emission, so glowing parts (portal, embers,
        # flames - listed in the json "emissive" map) are rebuilt here: full-bright emission
        # plus a little lit colour so they still read as solid shapes.
        m.set_emission(LColor(col[0], col[1], col[2], 1))
        m.set_diffuse(col * 0.35)
        m.set_ambient(col * 0.35)
    elif src.has_emission():
        e = src.get_emission()
        m.set_emission(LColor(conv(e[0]), conv(e[1]), conv(e[2]), 1))
    return m


def _fix_materials(model, srgb_fix=True, glow_names=()):
    cache = {}
    glow_names = set(glow_names)
    for gnp in model.find_all_matches("**/+GeomNode"):
        gn = gnp.node()
        for i in range(gn.get_num_geoms()):
            st = gn.get_geom_state(i)
            ma = st.get_attrib(MaterialAttrib)
            if ma is None or ma.is_off() or ma.get_material() is None:
                continue
            src = ma.get_material()
            key = src.get_name() + str(src.get_diffuse() if src.has_diffuse() else "")
            if key not in cache:
                base_name = src.get_name().split(".")[0]
                cache[key] = _osrs_material(src, srgb_fix, glow=base_name in glow_names)
            gn.set_geom_state(i, st.set_attrib(MaterialAttrib.make(cache[key])))


def find_meta(path):
    key = os.path.splitext(os.path.basename(path))[0]
    here = os.path.dirname(os.path.abspath(path))
    for cand in (os.path.join(here, key + ".json"), os.path.join(here, "..", "json", key + ".json")):
        if os.path.exists(cand):
            with open(cand) as fh:
                return json.load(fh)
    return {"key": key}


def load_entrance(loader, path, srgb_fix=True, flat=True):
    """Returns (NodePath, meta dict). The model is NOT parented - reparent it yourself."""
    model = loader.load_model(path)
    meta = find_meta(path)
    _fix_materials(model, srgb_fix, glow_names=meta.get("emissive", {}).keys())
    if flat:
        model.set_attrib(ShadeModelAttrib.make(ShadeModelAttrib.M_flat))
    model.set_shader_off(1)
    model.set_tag("dungeon_entrance", meta.get("key", ""))
    return model, meta


def add_entrance_collision(model, meta, solid_mask=BitMask32.bit(1), trigger_mask=BitMask32.bit(2),
                           show=False):
    """Invisible CollisionBoxes for the walls + ONE trigger box at the doorway.
    Parented to `model`, so they follow its position/heading/scale.
    Wire the trigger to your EXISTING enter-dungeon function (see the guide, section 6)."""
    existing = model.find_all_matches("**/+CollisionNode")
    if existing.get_num_paths():
        # .bam made by blend2bam already carries the boxes as CollisionNodes - reuse them
        solids, trig_np = [], None
        for np in existing:
            if np.name.startswith("TRIGGER"):
                np.node().set_into_collide_mask(trigger_mask)
                np.set_tag("dungeon_entrance", meta.get("key", ""))
                trig_np = np
            else:
                np.node().set_into_collide_mask(solid_mask)
                solids.append(np)
            np.node().set_from_collide_mask(BitMask32.all_off())
            if show:
                np.show()
        return solids, trig_np
    solids = []
    for c in meta.get("colliders", []):
        cn = CollisionNode(c["name"])
        cx, cy, cz = c["center"]
        sx, sy, sz = (s / 2 for s in c["size"])
        cn.add_solid(CollisionBox(Point3(cx - sx, cy - sy, cz - sz), Point3(cx + sx, cy + sy, cz + sz)))
        cn.set_into_collide_mask(solid_mask)
        cn.set_from_collide_mask(BitMask32.all_off())
        np = model.attach_new_node(cn)
        if show:
            np.show()
        solids.append(np)
    trig_np = None
    t = meta.get("trigger")
    if t:
        cn = CollisionNode("TRIGGER_door")
        cx, cy, cz = t["center"]
        sx, sy, sz = (s / 2 for s in t["size"])
        cn.add_solid(CollisionBox(Point3(cx - sx, cy - sy, cz - sz), Point3(cx + sx, cy + sy, cz + sz)))
        cn.set_into_collide_mask(trigger_mask)
        cn.set_from_collide_mask(BitMask32.all_off())
        trig_np = model.attach_new_node(cn)
        trig_np.set_tag("dungeon_entrance", meta.get("key", ""))
        if show:
            trig_np.show()
    return solids, trig_np


def setup_osrs_lighting(render, ambient=0.42, sun=0.85, sun_hpr=(160, -45, 0),
                        fog_color=None, fog_range=(40.0, 120.0)):
    """Identical copy of monsters/lighting.py (so this file also works on its own)."""
    from panda3d.core import ShadeModelAttrib as _S
    render.set_shader_off()
    render.set_attrib(_S.make(_S.M_flat))
    render.set_antialias(AntialiasAttrib.M_none)
    amb = AmbientLight("ambient")
    amb.set_color(LColor(ambient, ambient, ambient * 1.05, 1))
    amb_np = render.attach_new_node(amb)
    dl = DirectionalLight("sun")
    dl.set_color(LColor(sun, sun * 0.96, sun * 0.88, 1))
    sun_np = render.attach_new_node(dl)
    sun_np.set_hpr(*sun_hpr)
    render.set_light(amb_np)
    render.set_light(sun_np)
    fog = None
    if fog_color is not None:
        fog = Fog("distance_fog")
        fog.set_color(*fog_color)
        fog.set_linear_range(*fog_range)
        render.set_fog(fog)
    return amb_np, sun_np, fog


def point_in_box(p, box):
    """2D/3D helper for games without Panda collisions: is point p (x, y[, z]) in box?"""
    c, s = box["center"], box["size"]
    return all(abs(p[i] - c[i]) <= s[i] / 2 for i in range(len(p)))
