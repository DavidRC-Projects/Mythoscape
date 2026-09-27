"""Barrow Wraith - legless, floating 2.1 m spirit in a tattered burial
cloak with a rusted circlet, void-black face, pale glowing eyes and long
skeletal claws. The cloak's tail trails behind and sways (tail joints)."""
import math

from ..mesh_builder import Rig
from ..registry import MonsterStats, register
from .parts import seg

P = {"cloak": "#3d4241", "cloak_dark": "#272b2b", "cloak_light": "#535957",
     "bone": "#bdb59c", "void": "#0e0f10", "eye": "#a9dcd2", "iron": "#6b5d4a"}


@register("barrow_wraith", "Barrow Wraith", "wraith", "medium", "floater",
          MonsterStats(58, 70, "magic (soul drain) / melee (claws)", 11, 2.4,
                       "holy / silver weapons; immune to poison",
                       aggressive=True, notes="Soul drain heals it for 50% of damage. Only appears at night in barrows."),
          P, 2.1)
def build_barrow_wraith():
    rig = Rig("barrow_wraith")
    rig.joint("body", "root", (0, 0, 1.10))
    b = rig.mesh("body")
    # cloak body: tapered tube from shoulders to a flared, ragged hem
    b.tube((0, 0, 0.55), (0, -0.05, -0.55), 0.24, 0.40, P["cloak"], segments=8, caps=True)
    b.tube((0, 0.02, 0.62), (0, 0.0, 0.42), 0.20, 0.30, P["cloak_light"], segments=8)    # mantle
    for k in range(8):                                      # hem tatters
        a = math.radians(k * 45 + 22)
        x, y = math.cos(a) * 0.38, math.sin(a) * 0.38 - 0.05
        b.cone((x, y, -0.50), (x * 1.1, y * 1.1 - 0.08, -0.78 - (k % 2) * 0.1), 0.09,
               P["cloak_dark"], segments=3)
    for k in range(4):                                      # front fold lines
        b.box((0.03, 0.02, 0.60), P["cloak_dark"], pos=(-0.15 + k * 0.1, 0.33 - abs(k - 1.5) * 0.04, -0.2),
              hpr=(0, 12, 0))
    # trailing tail wisps (animated)
    rig.joint("tail_0", "body", (0, -0.25, -0.45), (0, 25, 0))
    rig.mesh("tail_0").tube((0, 0, 0), (0, -0.5, -0.25), 0.25, 0.14, P["cloak_dark"], segments=6)
    rig.joint("tail_1", "tail_0", (0, -0.5, -0.25), (10, 5, 0))
    rig.mesh("tail_1").tube((0, 0, 0), (0, -0.45, -0.05), 0.14, 0.0, P["cloak_dark"], segments=5)
    # hood + face
    rig.joint("head", "body", (0, 0.04, 0.66), (0, 8, 0))
    h = rig.mesh("head")
    h.box((0.36, 0.36, 0.40), P["cloak"], pos=(0, -0.02, 0.18), taper=(0.7, 0.75))
    h.cone((0, -0.10, 0.34), (0, -0.30, 0.48), 0.12, P["cloak"], segments=4)          # hood peak
    h.box((0.22, 0.04, 0.24), P["void"], pos=(0, 0.16, 0.14), taper=(0.8, 1))       # dark face
    h.tube((0, -0.02, 0.33), (0, -0.02, 0.37), 0.17, 0.16, P["iron"], segments=7)  # circlet
    for sx in (-1, 0, 1):
        h.cone((sx * 0.08, 0.12 - abs(sx) * 0.03, 0.36), (sx * 0.09, 0.12 - abs(sx) * 0.03, 0.46),
               0.03, P["iron"], segments=3)
    rig.joint("eyes", "head", (0, 0.185, 0.17))
    for sx in (-1, 1):
        rig.mesh("eyes").box((0.05, 0.01, 0.022), P["eye"], pos=(sx * 0.05, 0, 0), hpr=(0, 0, sx * -12))
    # arms: wide sleeves reaching forward, skeletal clawed hands
    for side, sx in (("l", -1), ("r", 1)):
        m = seg(rig, f"{side}_arm", "body", (sx * 0.26, 0.02, 0.50), (0, 0, -0.34), 0.09, 0.12,
                P["cloak"], hpr=(0, 55, sx * -25), segments=6)
        m = seg(rig, f"{side}_forearm", f"{side}_arm", (0, 0, -0.34), (0, 0, -0.30), 0.12, 0.16,
                P["cloak_light"], hpr=(0, 25, 0), segments=6, squash=0.8)
        for t in range(3):
            m.cone((0, -0.14 + t * 0.14, -0.30), (0.02, -0.16 + t * 0.16, -0.42), 0.06,
                   P["cloak_dark"], segments=3)
        rig.joint(f"{side}_hand", f"{side}_forearm", (0, 0, -0.32))
        hm = rig.mesh(f"{side}_hand")
        hm.box((0.08, 0.10, 0.10), P["bone"], pos=(0, 0.0, -0.04))
        for f in range(4):
            a = (f - 1.5) * 0.045
            hm.tube((a, 0.03, -0.08), (a * 1.8, 0.10, -0.20), 0.015, 0.012, P["bone"], segments=4)
            hm.cone((a * 1.8, 0.10, -0.20), (a * 2.2, 0.22, -0.26), 0.012, P["bone"], segments=3)
    rig.bake()
    rig["eyes"].set_light_off()
    return rig
