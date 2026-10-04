"""Headless concept renders for pets and legacy monsters that have no
matching model in the existing low-poly pack.

Reuses monsters.defs.wolves._wolf and monsters.defs.dragons._dragon so the
facet, lighting and proportion language matches /workspace/monsters/images.

    /workspace/monsters_venv/bin/python render_previews.py
"""
from __future__ import annotations

import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
PACK = os.path.dirname(HERE)
MONSTER_CODE = "/workspace/monsters/code"
sys.path.insert(0, MONSTER_CODE)

from panda3d.core import loadPrcFileData  # noqa: E402

SIZE = 768
SS = 3
loadPrcFileData("", f"""
window-type offscreen
win-size {SIZE * SS} {SIZE * SS}
audio-library-name null
sync-video false
""")

from direct.showbase.ShowBase import ShowBase  # noqa: E402
from panda3d.core import Point3, TransparencyAttrib  # noqa: E402
from PIL import Image, ImageDraw, ImageFont  # noqa: E402

from monsters.lighting import setup_osrs_lighting  # noqa: E402
from monsters.mesh_builder import MeshBuilder, Rig  # noqa: E402
from monsters.defs.dragons import _dragon  # noqa: E402
from monsters.defs.parts import biped_legs, seg  # noqa: E402
from monsters.defs.wolves import _wolf  # noqa: E402

OUT = os.path.join(PACK, "previews")
BG = (0.62, 0.60, 0.56, 1)


def _eyes_off(rig):
    rig.bake()
    for name in ("eyes", "gem", "core", "belly_glow"):
        if name in rig.joints:
            rig[name].set_light_off()
    return rig


def build_pet_cat():
    """Tabby house cat, ~0.32 m at the shoulder. Standing, tail up."""
    s = 1.0
    fur, dark, belly = "#c4a36a", "#8d6a3c", "#efe2c4"
    stripe, nose, eye = "#6b4a28", "#c46a78", "#d8b03a"
    rig = Rig("pet_cat")
    rig.joint("body", "root", (0, 0, 0.22 * s))
    b = rig.mesh("body")
    b.sphere(0.11 * s, fur, pos=(0, 0.0, 0.0), scale=(0.82, 1.45, 0.72), rings=4, segments=7)
    b.sphere(0.07 * s, belly, pos=(0, 0.02 * s, -0.045 * s), scale=(0.7, 1.2, 0.45), rings=3, segments=6)
    for y in (-0.02, 0.04):
        b.box((0.09 * s, 0.012 * s, 0.012 * s), stripe, pos=(0, y * s, 0.07 * s))
    # short digitigrade legs tucked under the chest
    for side, sx in (("l", -1), ("r", 1)):
        for name, y in (("front", 0.07), ("hind", -0.07)):
            jn = f"{side}_{name}"
            rig.joint(jn, "body", (sx * 0.05 * s, y * s, -0.02 * s))
            m = rig.mesh(jn)
            m.tube((0, 0, 0), (0, 0.015 * s, -0.12 * s), 0.028 * s, 0.018 * s, fur, segments=5)
            m.box((0.034 * s, 0.05 * s, 0.014 * s), dark, pos=(0, 0.03 * s, -0.125 * s))
    rig.joint("neck", "body", (0, 0.12 * s, 0.04 * s))
    rig.mesh("neck").tube((0, 0, 0), (0, 0.04 * s, 0.05 * s), 0.045 * s, 0.035 * s, fur, segments=6)
    rig.joint("head", "neck", (0, 0.05 * s, 0.06 * s))
    h = rig.mesh("head")
    h.sphere(0.075 * s, fur, scale=(1.05, 0.95, 0.95), rings=4, segments=7)
    h.box((0.045 * s, 0.05 * s, 0.03 * s), belly, pos=(0, 0.06 * s, -0.01 * s))  # muzzle
    h.box((0.018 * s, 0.012 * s, 0.012 * s), nose, pos=(0, 0.09 * s, 0.005 * s))
    for sx in (-1, 1):
        h.cone((sx * 0.04 * s, -0.01 * s, 0.04 * s), (sx * 0.05 * s, -0.02 * s, 0.11 * s),
               0.028 * s, fur, segments=4, squash=0.45)
        h.cone((sx * 0.04 * s, -0.005 * s, 0.045 * s), (sx * 0.045 * s, -0.01 * s, 0.085 * s),
               0.014 * s, "#f2c2c8", segments=3, squash=0.4)
    # collar + bell
    h.tube((0, 0.0, -0.05 * s), (0, 0.015 * s, -0.055 * s), 0.042 * s, 0.040 * s, "#8c3b3b", segments=6)
    rig.joint("gem", "head", (0, 0.045 * s, -0.07 * s))
    rig.mesh("gem").sphere(0.010 * s, "#e0b84a", rings=2, segments=5)
    rig.joint("eyes", "head", (0, 0.05 * s, 0.02 * s))
    for sx in (-1, 1):
        rig.mesh("eyes").box((0.018 * s, 0.012 * s, 0.016 * s), eye, pos=(sx * 0.03 * s, 0, 0))
    rig.joint("tail", "body", (0, -0.12 * s, 0.04 * s), (0, 70, 0))
    tl = rig.mesh("tail")
    tl.tube((0, 0, 0), (0, 0.02 * s, 0.16 * s), 0.018 * s, 0.012 * s, fur, segments=5)
    tl.tube((0, 0.02 * s, 0.16 * s), (0.02 * s, 0.04 * s, 0.26 * s), 0.012 * s, 0.008 * s, stripe, segments=5)
    return _eyes_off(rig)


def build_pet_husky():
    """White husky. Same wolf rig as Grey Wolf, cream coat, blue eyes, collar."""
    s = 0.82
    p = {
        "fur": "#e4dfd4", "fur_dark": "#b7b1a4", "belly": "#f4f1ea", "muzzle": "#f7f5f0",
        "nose": "#2a2622", "eye": "#6aa4cc", "mouth": "#6a4038", "tooth": "#efe8d8", "claw": "#4a433c",
    }
    rig = _wolf("pet_husky", p, s=s)
    n = rig.mesh("neck_0")
    n.tube((0, 0.06 * s, 0.02 * s), (0, 0.12 * s, 0.06 * s), 0.145 * s, 0.145 * s, "#6b3a2a", segments=6)
    rig.joint("gem", "neck_0", (0, 0.14 * s, -0.02 * s))
    rig.mesh("gem").sphere(0.028 * s, "#d4b15a", rings=2, segments=5)
    return _eyes_off(rig)


def build_pet_dragon_frost():
    """Small frost-dragon pet. Ice palette on the shared dragon rig, plus shards."""
    s = 0.55
    p = {
        "body": "#7ea8be", "dark": "#4f7388", "belly": "#d7e7ee", "wing": "#c5dce6",
        "wing_bone": "#5d8498", "horn": "#eef6f8", "eye": "#7ec8ff", "claw": "#e7f1f4",
        "mouth": "#3a5562",
    }
    rig = _dragon("pet_dragon_frost", p, s=s, elder=False)
    b = rig.mesh("body")
    for (x, y, z, h) in (
        (0.22, 0.15, 0.28, 0.22),
        (-0.18, -0.20, 0.22, 0.18),
        (0.10, -0.45, 0.18, 0.16),
    ):
        b.cone((x * s, y * s, z * s), (x * s, (y - 0.05) * s, (z + h) * s),
               0.045 * s, "#e7f4f8", segments=4, squash=0.55)
    return _eyes_off(rig)


def build_pet_dragon_mythic():
    """Gold-and-violet elder hatchling. Chest gem unlit."""
    s = 0.72
    p = {
        "body": "#c6a15a", "dark": "#7a5428", "belly": "#efe0b0", "wing": "#6a4a86",
        "wing_bone": "#3e2a52", "horn": "#f3e6c4", "eye": "#f0d56a", "claw": "#f4ecd4",
        "mouth": "#5a2848",
    }
    rig = _dragon("pet_dragon_mythic", p, s=s, elder=True)
    rig.joint("gem", "body", (0, 0.25 * s, -0.05 * s))
    g = rig.mesh("gem")
    g.sphere(0.09 * s, "#b56ad9", rings=3, segments=6)
    g.cone((0, 0.02 * s, 0.06 * s), (0, 0.02 * s, 0.16 * s), 0.03 * s, "#e7d2ff", segments=4)
    return _eyes_off(rig)


def build_giant_rat():
    """Mangy giant rat, ~0.45 m. Big incisors, naked tail, round ears."""
    s = 1.0
    fur, dark, belly = "#7a6a58", "#4e4338", "#cbb89a"
    skin, eye, tooth = "#c48b84", "#1a1614", "#efe6d0"
    rig = Rig("giant_rat")
    rig.joint("body", "root", (0, 0, 0.28))
    b = rig.mesh("body")
    b.sphere(0.16, fur, pos=(0, 0.02, 0.02), scale=(0.85, 1.55, 0.72), rings=4, segments=7)
    b.sphere(0.09, belly, pos=(0, 0.04, -0.07), scale=(0.7, 1.3, 0.4), rings=3, segments=6)
    b.box((0.05, 0.09, 0.012), dark, pos=(0.11, -0.02, 0.05), hpr=(20, 25, 0))  # scar
    for side, sx in (("l", -1), ("r", 1)):
        for name, y, zoff in (("front", 0.14, -0.02), ("hind", -0.12, 0.0)):
            rig.joint(f"{side}_{name}", "body", (sx * 0.09, y, zoff))
            m = rig.mesh(f"{side}_{name}")
            m.tube((0, 0, 0), (sx * 0.01, 0.02, -0.22), 0.04, 0.028, dark, segments=5)
            m.box((0.05, 0.07, 0.02), dark, pos=(0, 0.03, -0.23))
            m.cone((0, 0.055, -0.235), (0, 0.08, -0.24), 0.008, tooth, segments=3)
    rig.joint("neck", "body", (0, 0.18, 0.04))
    rig.mesh("neck").tube((0, 0, 0), (0, 0.06, 0.04), 0.07, 0.05, fur, segments=6)
    rig.joint("head", "neck", (0, 0.07, 0.04), (0, -8, 0))
    h = rig.mesh("head")
    h.sphere(0.10, fur, pos=(0, 0.02, 0.02), scale=(1.05, 1.15, 0.9), rings=4, segments=7)
    h.box((0.07, 0.10, 0.045), belly, pos=(0, 0.12, -0.01), taper=(0.7, 0.85))
    h.box((0.025, 0.02, 0.015), "#2a1818", pos=(0, 0.175, 0.01))
    for sx in (-1, 1):
        h.cone((sx * 0.018, 0.14, -0.03), (sx * 0.018, 0.16, -0.07), 0.012, tooth, segments=4)
        # round ears
        h.sphere(0.045, fur, pos=(sx * 0.09, -0.02, 0.06), scale=(0.35, 1.0, 1.15), rings=3, segments=6)
        h.sphere(0.028, skin, pos=(sx * 0.09, -0.01, 0.06), scale=(0.25, 0.8, 0.9), rings=2, segments=5)
    rig.joint("eyes", "head", (0, 0.08, 0.04))
    for sx in (-1, 1):
        rig.mesh("eyes").sphere(0.012, eye, pos=(sx * 0.045, 0.01, 0), rings=2, segments=4)
    rig.joint("tail", "body", (0, -0.20, 0.0), (0, -15, 0))
    tl = rig.mesh("tail")
    tl.tube((0, 0, 0), (0, -0.28, -0.06), 0.025, 0.012, skin, segments=5)
    tl.tube((0, -0.28, -0.06), (0.04, -0.48, -0.02), 0.012, 0.004, skin, segments=5)
    return _eyes_off(rig)


def _soldier(name, p, helm="nasal", cape=False, greathelm=False, crown=False, scale=1.0):
    """Armoured humanoid, ~1.85 m. Separate from the player walk rig."""
    s = scale
    rig = Rig(name)
    rig.joint("hips", "root", (0, 0, 0.92 * s))
    biped_legs(rig, "hips", 0.11 * s, -0.02 * s, 0.42 * s, 0.42 * s,
               0.07 * s, 0.055 * s, p["plate"], p["boot"],
               foot=(0.10 * s, 0.22 * s, 0.06 * s), knee_bend=6, segments=6)
    # scale the leg joints' geometry is already in metres via radii; biped_legs
    # doesn't multiply hip offsets that we passed scaled. Good.
    rig.joint("torso", "hips", (0, 0, 0.02 * s))
    t = rig.mesh("torso")
    t.box((0.42 * s, 0.24 * s, 0.28 * s), p["plate"], pos=(0, 0, 0.22 * s), taper=(0.92, 1.0))
    t.box((0.36 * s, 0.22 * s, 0.16 * s), p["plate_dark"], pos=(0, 0.02 * s, 0.40 * s), taper=(1.05, 1.0))
    t.box((0.18 * s, 0.04 * s, 0.22 * s), p["trim"], pos=(0, 0.125 * s, 0.24 * s))  # breast ridge
    t.box((0.44 * s, 0.26 * s, 0.06 * s), p["leather"], pos=(0, 0, 0.06 * s))  # belt
    t.box((0.08 * s, 0.03 * s, 0.07 * s), p["trim"], pos=(0, 0.145 * s, 0.06 * s))
    if cape:
        t.box((0.34 * s, 0.04 * s, 0.55 * s), p["cape"], pos=(0, -0.14 * s, 0.12 * s), taper=(0.75, 1.0))
        t.box((0.30 * s, 0.02 * s, 0.50 * s), p["cape_dark"], pos=(0, -0.155 * s, 0.08 * s), taper=(0.7, 1.0))
    for sx in (-1, 1):
        t.box((0.16 * s, 0.16 * s, 0.08 * s), p["plate"], pos=(sx * 0.24 * s, 0.0, 0.42 * s),
              hpr=(0, 0, sx * -18))
    rig.joint("head", "torso", (0, 0, 0.52 * s))
    h = rig.mesh("head")
    if greathelm:
        h.box((0.24 * s, 0.26 * s, 0.28 * s), p["plate"], pos=(0, 0.0, 0.12 * s), taper=(0.9, 0.95))
        h.box((0.26 * s, 0.08 * s, 0.06 * s), p["plate_dark"], pos=(0, 0.02 * s, 0.26 * s))  # crest base
        h.box((0.04 * s, 0.16 * s, 0.10 * s), p["trim"], pos=(0, 0.0, 0.32 * s))
        h.box((0.16 * s, 0.02 * s, 0.06 * s), "#1a1816", pos=(0, 0.13 * s, 0.12 * s))  # visor slit
        rig.joint("eyes", "head", (0, 0.14 * s, 0.12 * s))
        rig.mesh("eyes").box((0.12 * s, 0.012 * s, 0.018 * s), p["eye"], pos=(0, 0, 0))
    else:
        # face + nasal / open helm
        h.sphere(0.11 * s, p["skin"], pos=(0, 0.02 * s, 0.08 * s), rings=4, segments=7)
        h.box((0.22 * s, 0.22 * s, 0.10 * s), p["plate"], pos=(0, 0.0, 0.16 * s), taper=(0.85, 0.9))  # skullcap
        h.box((0.04 * s, 0.16 * s, 0.14 * s), p["plate"], pos=(0, 0.08 * s, 0.06 * s))  # nasal
        if helm == "horned":
            for sx in (-1, 1):
                h.cone((sx * 0.10 * s, -0.02 * s, 0.16 * s), (sx * 0.22 * s, -0.12 * s, 0.34 * s),
                       0.035 * s, p["horn"], segments=5)
        h.box((0.16 * s, 0.08 * s, 0.04 * s), p["plate_dark"], pos=(0, 0.06 * s, 0.0))  # beard shadow / bevor
        rig.joint("eyes", "head", (0, 0.10 * s, 0.10 * s))
        for sx in (-1, 1):
            rig.mesh("eyes").box((0.028 * s, 0.012 * s, 0.016 * s), p["eye"], pos=(sx * 0.04 * s, 0, 0))
    if crown:
        h.cone((0, 0, 0.24 * s), (0, 0, 0.36 * s), 0.06 * s, p["trim"], segments=5)
        for sx in (-1, 1):
            h.cone((sx * 0.07 * s, 0, 0.22 * s), (sx * 0.10 * s, 0, 0.32 * s), 0.02 * s, p["trim"], segments=4)
    # arms
    for side, sx in (("l", -1), ("r", 1)):
        seg(rig, f"{side}_arm", "torso", (sx * 0.24 * s, 0.02 * s, 0.38 * s),
            (sx * 0.04 * s, 0.02 * s, -0.28 * s), 0.07 * s, 0.055 * s, p["plate"], segments=6)
        m = seg(rig, f"{side}_forearm", f"{side}_arm", (sx * 0.04 * s, 0.02 * s, -0.28 * s),
                (0, 0.02 * s, -0.26 * s), 0.05 * s, 0.04 * s, p["plate_dark"], segments=5)
        m.box((0.09 * s, 0.08 * s, 0.04 * s), p["trim"], pos=(0, 0.01 * s, -0.02 * s))
        rig.joint(f"{side}_hand", f"{side}_forearm", (0, 0.02 * s, -0.26 * s))
        rig.mesh(f"{side}_hand").box((0.07 * s, 0.05 * s, 0.08 * s), p["glove"], pos=(0, 0.02 * s, -0.03 * s))
    # sword in right, shield on left
    rig["r_arm"].set_hpr(0, 20, -30)
    c = rig.mesh("r_hand")
    c.box((0.03 * s, 0.03 * s, 0.55 * s), p["blade"], pos=(0, 0.02 * s, -0.32 * s))
    c.box((0.10 * s, 0.035 * s, 0.03 * s), p["trim"], pos=(0, 0.02 * s, -0.06 * s))
    c.cone((0, 0.02 * s, -0.58 * s), (0, 0.02 * s, -0.66 * s), 0.02 * s, p["blade"], segments=4)
    sh = rig.mesh("l_hand")
    sh.box((0.06 * s, 0.28 * s, 0.38 * s), p["shield"], pos=(0, 0.08 * s, 0.02 * s), taper=(0.85, 0.9))
    sh.box((0.02 * s, 0.10 * s, 0.12 * s), p["trim"], pos=(0, 0.12 * s, 0.02 * s))
    return _eyes_off(rig)


def build_guard():
    return _soldier("guard", {
        "plate": "#8a8e92", "plate_dark": "#5e6368", "trim": "#b9a36a",
        "leather": "#5c4632", "boot": "#3e342c", "skin": "#e0c2a0",
        "eye": "#2a2620", "glove": "#4a3b30", "blade": "#c5c8cc",
        "shield": "#6e2e32", "cape": "#6e2e32", "cape_dark": "#4a1e22",
        "horn": "#cfc3a0",
    }, helm="nasal", cape=True, scale=1.0)


def build_knight():
    return _soldier("castle_knight", {
        "plate": "#9aa3ad", "plate_dark": "#66707a", "trim": "#d4c48a",
        "leather": "#4a3c30", "boot": "#3a332c", "skin": "#e0c2a0",
        "eye": "#1c1a18", "glove": "#3e3632", "blade": "#d5d8dc",
        "shield": "#2c3f66", "cape": "#2c3f66", "cape_dark": "#1c2a44",
        "horn": "#d8d0b8",
    }, greathelm=True, cape=True, scale=1.02)


def build_mythos_champion():
    return _soldier("mythos_champion", {
        "plate": "#c6a15a", "plate_dark": "#8a6230", "trim": "#f0e2a8",
        "leather": "#4a3048", "boot": "#3a2838", "skin": "#e0c2a0",
        "eye": "#f0d56a", "glove": "#5a4030", "blade": "#efe6c8",
        "shield": "#5a2a68", "cape": "#5a2a68", "cape_dark": "#3a1848",
        "horn": "#f2e6c0",
    }, greathelm=True, cape=True, crown=True, scale=1.08)


def build_shadow_knight():
    return _soldier("shadow_knight", {
        "plate": "#3c4048", "plate_dark": "#26282e", "trim": "#7a6a98",
        "leather": "#2a2428", "boot": "#1e1c20", "skin": "#8a8478",
        "eye": "#c9b6ff", "glove": "#2a2830", "blade": "#b7a8d4",
        "shield": "#2a2438", "cape": "#2a2430", "cape_dark": "#16141c",
        "horn": "#6a6080",
    }, helm="horned", cape=True, scale=1.06)


def build_magma_slug():
    rig = Rig("magma_slug")
    rig.joint("body", "root", (0, 0, 0.28))
    b = rig.mesh("body")
    b.sphere(0.38, "#5a3428", scale=(1.15, 1.55, 0.62), rings=4, segments=8)
    b.sphere(0.28, "#3a241c", pos=(0, -0.05, 0.08), scale=(1.0, 1.4, 0.4), rings=3, segments=7)
    # crust plates
    for (x, y, z, hx) in (
        (-0.22, 0.15, 0.16, 18), (0.18, -0.05, 0.18, -12),
        (0.05, 0.28, 0.12, 8), (-0.08, -0.28, 0.14, -20),
    ):
        b.box((0.16, 0.18, 0.05), "#2c1c16", pos=(x, y, z), hpr=(0, hx, 0))
    rig.joint("core", "body", (0, 0.05, 0.02))
    rig.mesh("core").sphere(0.16, "#ff8a28", scale=(0.9, 1.3, 0.55), rings=3, segments=6)
    rig.joint("belly_glow", "body", (0, 0.08, -0.02))
    rig.mesh("belly_glow").sphere(0.08, "#ffd27a", scale=(0.7, 1.1, 0.4), rings=2, segments=5)
    # eye stalks
    for sx in (-1, 1):
        b.tube((sx * 0.10, 0.28, 0.10), (sx * 0.14, 0.40, 0.22), 0.035, 0.028, "#4a3028", segments=5)
    rig.joint("eyes", "body", (0, 0.42, 0.24))
    for sx in (-1, 1):
        rig.mesh("eyes").sphere(0.035, "#ffd27a", pos=(sx * 0.14, 0, 0), rings=2, segments=4)
    # drips
    for x, y in ((-0.15, 0.05), (0.12, -0.1), (0.0, 0.2)):
        b.cone((x, y, -0.16), (x, y + 0.02, -0.28), 0.03, "#ff6a20", segments=4)
    return _eyes_off(rig)


def build_ash_imp():
    rig = Rig("ash_imp")
    rig.joint("body", "root", (0, 0, 0.55))
    b = rig.mesh("body")
    b.sphere(0.16, "#3a3438", scale=(0.9, 0.75, 1.15), rings=4, segments=7)
    b.box((0.18, 0.12, 0.10), "#2a2428", pos=(0, 0.02, -0.10))
    rig.joint("head", "body", (0, 0.02, 0.18))
    h = rig.mesh("head")
    h.sphere(0.11, "#4a4044", rings=4, segments=6)
    for sx in (-1, 1):
        h.cone((sx * 0.05, 0.0, 0.06), (sx * 0.10, -0.04, 0.18), 0.028, "#2a2426", segments=4)
    h.box((0.06, 0.05, 0.03), "#2a2022", pos=(0, 0.08, -0.02))
    rig.joint("eyes", "head", (0, 0.08, 0.02))
    for sx in (-1, 1):
        rig.mesh("eyes").box((0.025, 0.012, 0.018), "#ff8a30", pos=(sx * 0.04, 0, 0))
    # wings
    for side, sx in (("l", -1), ("r", 1)):
        rig.joint(f"{side}_wing", "body", (sx * 0.10, -0.04, 0.08))
        w = rig.mesh(f"{side}_wing")
        root = (0, 0, 0)
        tip_u = (sx * 0.38, -0.05, 0.22)
        tip_d = (sx * 0.32, -0.08, -0.16)
        elbow = (sx * 0.16, -0.02, 0.06)
        w.polygon([root, elbow, tip_u], "#5a5054")
        w.polygon([root, tip_d, elbow], "#3e3638")
        w.tube(root, tip_u, 0.012, 0.006, "#2a2426", segments=4)
    # arms and little legs
    for side, sx in (("l", -1), ("r", 1)):
        seg(rig, f"{side}_arm", "body", (sx * 0.12, 0.04, 0.02),
            (sx * 0.10, 0.08, -0.16), 0.035, 0.025, "#3a3438", segments=5)
        rig.mesh(f"{side}_arm").box((0.05, 0.04, 0.04), "#2a2426", pos=(sx * 0.12, 0.08, -0.18))
        seg(rig, f"{side}_leg", "body", (sx * 0.06, 0.0, -0.14),
            (0, 0.02, -0.22), 0.03, 0.02, "#2e2a2c", segments=5)
    # tail
    rig.joint("tail", "body", (0, -0.08, -0.06))
    tl = rig.mesh("tail")
    tl.tube((0, 0, 0), (0, -0.22, -0.08), 0.02, 0.01, "#3a3438", segments=5)
    tl.cone((0, -0.22, -0.08), (0, -0.30, -0.02), 0.025, "#ff6a28", segments=4)
    return _eyes_off(rig)


def build_crucible_beast():
    """Hulking lava brute, ~2.4 m. Horned skull, glowing chest."""
    s = 1.0
    rock, dark, glow = "#6a4036", "#3a241e", "#ff7a28"
    rig = Rig("crucible_beast")
    rig.joint("hips", "root", (0, 0, 1.05))
    hip = rig.mesh("hips")
    hip.box((0.55, 0.32, 0.28), rock, pos=(0, 0, 0.05))
    biped_legs(rig, "hips", 0.16, -0.06, 0.42, 0.40, 0.13, 0.10, rock, dark,
               foot=(0.18, 0.28, 0.08), knee_bend=10, segments=5)
    rig.joint("torso", "hips", (0, 0, 0.16))
    t = rig.mesh("torso")
    t.box((0.78, 0.46, 0.62), rock, pos=(0, 0.02, 0.36), taper=(0.82, 1.0))
    t.box((0.62, 0.38, 0.30), dark, pos=(0, 0.04, 0.70), taper=(1.05, 1.0))
    for sx in (-1, 1):
        t.box((0.22, 0.18, 0.10), dark, pos=(sx * 0.38, 0, 0.62), hpr=(0, 0, sx * -20))
    rig.joint("core", "torso", (0, 0.30, 0.38))
    rig.mesh("core").sphere(0.12, glow, scale=(1.1, 0.45, 1.2), rings=3, segments=6)
    rig.joint("belly_glow", "torso", (0, 0.34, 0.38))
    rig.mesh("belly_glow").sphere(0.06, "#ffd08a", scale=(0.8, 0.35, 0.8), rings=2, segments=5)
    rig.joint("head", "torso", (0, 0.04, 0.92))
    h = rig.mesh("head")
    h.sphere(0.20, rock, scale=(1.1, 0.95, 0.9), rings=4, segments=7)
    h.box((0.16, 0.16, 0.08), dark, pos=(0, 0.10, -0.04))
    for sx in (-1, 1):
        h.cone((sx * 0.10, -0.02, 0.12), (sx * 0.22, -0.16, 0.42), 0.06, "#2a1c18", segments=5)
    rig.joint("eyes", "head", (0, 0.14, 0.04))
    for sx in (-1, 1):
        rig.mesh("eyes").box((0.05, 0.02, 0.03), "#ffd27a", pos=(sx * 0.08, 0, 0))
    for side, sx in (("l", -1), ("r", 1)):
        seg(rig, f"{side}_arm", "torso", (sx * 0.40, 0.02, 0.62),
            (sx * 0.08, 0.04, -0.42), 0.11, 0.08, rock, segments=5)
        m = seg(rig, f"{side}_forearm", f"{side}_arm", (sx * 0.08, 0.04, -0.42),
                (0, 0.06, -0.38), 0.09, 0.07, dark, segments=5)
        m.sphere(0.10, dark, pos=(0, 0.06, -0.42), rings=3, segments=5)
    return _eyes_off(rig)


BUILDERS = [
    ("pet_cat", "Cat", "pet", build_pet_cat),
    ("pet_husky", "White Husky", "pet", build_pet_husky),
    ("pet_dragon_frost", "Frost Dragon", "pet", build_pet_dragon_frost),
    ("pet_dragon_mythic", "Mythic Dragon", "pet", build_pet_dragon_mythic),
    ("giant_rat", "Giant Rat", "overworld", build_giant_rat),
    ("guard", "City Guard", "overworld", build_guard),
    ("castle_knight", "Castle Knight", "overworld", build_knight),
    ("mythos_champion", "Mythos Champion", "overworld", build_mythos_champion),
    ("shadow_knight", "Shadow Knight", "dungeon", build_shadow_knight),
    ("magma_slug", "Magma Slug", "emberdeep", build_magma_slug),
    ("ash_imp", "Ash Imp", "emberdeep", build_ash_imp),
    ("crucible_beast", "Crucible Beast", "emberdeep", build_crucible_beast),
]


def shadow_disc(radius):
    mb = MeshBuilder("shadow", jitter=0)
    n = 16
    for i in range(n):
        a0, a1 = 2 * math.pi * i / n, 2 * math.pi * (i + 1) / n
        mb.tri((0, 0, 0), (math.cos(a0) * radius, math.sin(a0) * radius, 0),
               (math.cos(a1) * radius, math.sin(a1) * radius, 0), (0, 0, 0, 0.22))
    np = mb.build_node()
    np.set_transparency(TransparencyAttrib.M_alpha)
    np.set_light_off()
    np.set_depth_write(False)
    np.set_bin("background", 10)
    return np


def crop_to_content(img, margin=0.10):
    from PIL import ImageChops
    bg = Image.new("RGB", img.size, tuple(int(c * 255) for c in BG[:3]))
    diff = ImageChops.difference(img, bg).convert("L").point(lambda v: 255 if v > 8 else 0)
    box = diff.getbbox()
    if not box:
        return img
    x0, y0, x1, y1 = box
    side = int(max(x1 - x0, y1 - y0) * (1 + 2 * margin))
    cx, cy = (x0 + x1) // 2, (y0 + y1) // 2
    pad = Image.new("RGB", (img.width + 2 * side, img.height + 2 * side), bg.getpixel((0, 0)))
    pad.paste(img, (side, side))
    cx, cy = cx + side, cy + side
    return pad.crop((cx - side // 2, cy - side // 2, cx - side // 2 + side, cy - side // 2 + side))


def main():
    os.makedirs(OUT, exist_ok=True)
    base = ShowBase()
    base.disable_mouse()
    base.set_background_color(*BG)
    setup_osrs_lighting(base.render)
    base.cam.node().get_lens().set_fov(28)
    labels = []
    for key, title, group, fn in BUILDERS:
        rig = fn()
        model = rig.root
        model.reparent_to(base.render)
        lo, hi = model.get_tight_bounds()
        lo.z = min(lo.z, 0.0)
        centre = (lo + hi) / 2
        ext = hi - lo
        radius = max(ext.x, ext.y, 0.2) * 0.55
        sh = shadow_disc(max(radius, 0.25))
        sh.reparent_to(base.render)
        sh.set_pos(centre.x, centre.y, 0.005)
        sh.set_scale(1.0, 0.8, 1.0)
        span = max(ext.x, ext.y, ext.z, 0.4)
        dist = span / (2 * math.tan(math.radians(28 / 2))) * 1.85
        az, el = math.radians(35.0), math.radians(16.0)
        cam_pos = Point3(centre.x + dist * math.sin(az) * math.cos(el),
                         centre.y + dist * math.cos(az) * math.cos(el),
                         centre.z + dist * math.sin(el))
        base.cam.set_pos(cam_pos)
        base.cam.look_at(centre)
        base.graphics_engine.render_frame()
        base.graphics_engine.render_frame()
        tmp = os.path.join(OUT, f"_{key}_tmp.png")
        base.win.save_screenshot(tmp)
        img = Image.open(tmp).convert("RGB")
        img = crop_to_content(img).resize((SIZE, SIZE), Image.LANCZOS)
        path = os.path.join(OUT, f"{key}.png")
        img.save(path)
        os.remove(tmp)
        print(f"{key:22s} tris={rig.triangle_count:5d} h={ext.z:.2f}m")
        labels.append((key, title, group, path))
        model.remove_node()
        sh.remove_node()
    make_sheet(labels)
    print("sheet", os.path.join(OUT, "contact_sheet.png"))


def make_sheet(labels):
    cols = 4
    rows = math.ceil(len(labels) / cols)
    cell, cap = 280, 46
    W, H = cols * cell + 24, rows * (cell + cap) + 64
    sheet = Image.new("RGB", (W, H), (42, 40, 38))
    draw = ImageDraw.Draw(sheet)
    try:
        font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 14)
        font_b = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 18)
    except Exception:
        font = font_b = ImageFont.load_default()
    draw.text((12, 10), "Pets and legacy monsters — new previews only", fill=(236, 230, 216), font=font_b)
    draw.text((12, 34), "Same flat-shade pipeline as /workspace/monsters. Reused creatures are not redrawn.",
              fill=(180, 174, 164), font=font)
    for i, (key, title, group, path) in enumerate(labels):
        r, c = divmod(i, cols)
        x = 12 + c * cell
        y = 58 + r * (cell + cap)
        im = Image.open(path).convert("RGB").resize((cell - 8, cell - 8), Image.LANCZOS)
        sheet.paste(im, (x, y))
        draw.text((x, y + cell - 4), title, fill=(236, 230, 216), font=font_b)
        draw.text((x, y + cell + 16), f"{key}  ·  {group}", fill=(180, 174, 164), font=font)
    sheet.save(os.path.join(OUT, "contact_sheet.png"))


if __name__ == "__main__":
    main()
