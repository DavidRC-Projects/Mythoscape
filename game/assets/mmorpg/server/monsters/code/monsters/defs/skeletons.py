"""Skeletons: warrior (sword + shield, rusty helm) and mage (tattered robe,
staff, glowing eyes). ~1.8 m, player-sized, thin but readable limbs."""
from ..mesh_builder import Rig
from ..registry import MonsterStats, register
from .parts import aim, seg

WARRIOR = {
    "bone": "#d6cdb2", "bone_dark": "#a39a7f", "socket": "#221e19",
    "iron": "#707271", "rust": "#7b4d2f", "wood": "#5e4630", "leather": "#4f3b28",
}
MAGE = {
    "bone": "#cfc8b0", "bone_dark": "#9c9580", "socket": "#1a1a1d",
    "robe": "#3d3a4a", "robe_dark": "#2a2833", "trim": "#7a6a3e",
    "wood": "#4a3a2c", "glow": "#86d1b8",
}


def _skeleton(name, p, mage=False):
    rig = Rig(name)
    B, D = p["bone"], p["bone_dark"]
    rig.joint("hips", "root", (0, 0, 0.94))
    pel = rig.mesh("hips")
    pel.box((0.30, 0.14, 0.12), B, taper=(1.25, 1.0))
    pel.box((0.12, 0.06, 0.08), D, pos=(0, 0.04, -0.05), taper=(0.5, 1))
    # legs with knobbly joints
    for side, sx in (("l", -1), ("r", 1)):
        m = seg(rig, f"{side}_leg", "hips", (sx * 0.11, 0, -0.04), (0, 0, -0.43),
                0.04, 0.03, B, hpr=(0, 4, 0), segments=5)
        m.sphere(0.05, D, pos=(0, 0, -0.43), rings=3, segments=5)
        m = seg(rig, f"{side}_shin", f"{side}_leg", (0, 0, -0.43), (0, 0, -0.41),
                0.034, 0.028, B, hpr=(0, -8, 0), segments=5)
        m.box((0.09, 0.20, 0.05), B, pos=(0, 0.05, -0.43), taper=(0.8, 0.6))
    # spine + ribcage
    rig.joint("torso", "hips", (0, 0, 0.06), (0, -4, 0))
    t = rig.mesh("torso")
    for i in range(5):
        t.box((0.05, 0.05, 0.04), D, pos=(0, -0.05, 0.04 + i * 0.055))
    for i, z in enumerate((0.26, 0.33, 0.40, 0.47)):
        r = 0.15 - abs(i - 2) * 0.012
        t.tube((0, 0.0, z), (0, 0.0, z + 0.035), r, r, B, segments=8, caps=False,
               squash=0.72, double_sided=True)
    t.box((0.06, 0.03, 0.26), B, pos=(0, 0.105, 0.39))                  # sternum
    t.box((0.40, 0.10, 0.05), B, pos=(0, -0.01, 0.52), taper=(0.85, 1))  # collar/shoulders
    if not mage:
        t.box((0.22, 0.06, 0.12), p["leather"], pos=(0, 0.06, 0.02))    # rotted loin cloth
        t.box((0.34, 0.20, 0.04), p["leather"], pos=(0, 0.0, 0.06))       # belt
    else:
        t.box((0.34, 0.26, 0.36), p["robe"], pos=(0, -0.02, 0.36), taper=(1.25, 1.1))  # robe top
        t.box((0.50, 0.36, 0.95), p["robe"], pos=(0, 0.0, -0.40), taper=(0.62, 0.62))   # robe skirt
        t.box((0.10, 0.02, 0.75), p["trim"], pos=(0, 0.16, -0.30), taper=(0.6, 1))
        for i in range(8):     # ragged hem: downward points
            x = -0.26 + i * 0.075
            t.cone((x, 0.17 if i % 2 else -0.17, -0.82), (x * 1.05, (0.2 if i % 2 else -0.2), -0.95),
                   0.05, p["robe_dark"], segments=3)
    # skull
    rig.joint("head", "torso", (0, 0.02, 0.60), (0, 6, 0))
    h = rig.mesh("head")
    h.box((0.05, 0.05, 0.06), D, pos=(0, -0.01, -0.01))                 # neck vertebra
    h.sphere(0.125, B, pos=(0, 0, 0.125), scale=(0.95, 1.1, 1.0), rings=4, segments=7)
    h.box((0.15, 0.12, 0.07), B, pos=(0, 0.06, 0.04), taper=(0.9, 1))   # cheek/maxilla
    rig.joint("jaw", "head", (0, 0.0, 0.05))
    rig.mesh("jaw").box((0.13, 0.12, 0.04), D, pos=(0, 0.06, -0.02), taper=(1.1, 1))
    for i in range(4):
        rig.mesh("jaw").box((0.018, 0.01, 0.02), B, pos=(-0.03 + i * 0.02, 0.118, 0.005))
    for sx in (-1, 1):
        h.box((0.045, 0.02, 0.04), p["socket"], pos=(sx * 0.042, 0.118, 0.12))
    h.box((0.022, 0.02, 0.03), p["socket"], pos=(0, 0.122, 0.075))
    if not mage:
        # conical kettle helm sitting above the eye sockets
        h.tube((0, -0.01, 0.165), (0, -0.01, 0.215), 0.132, 0.132, p["iron"], segments=8, squash=1.1)
        h.cone((0, -0.01, 0.215), (0, -0.02, 0.33), 0.132, p["iron"], segments=8, squash=1.1)
        h.tube((0, -0.01, 0.160), (0, -0.01, 0.180), 0.14, 0.14, p["rust"], segments=8, squash=1.1)
        h.box((0.028, 0.03, 0.075), p["rust"], pos=(0, 0.135, 0.135))          # nasal guard
    else:
        h.box((0.33, 0.32, 0.27), p["robe_dark"], pos=(0, -0.04, 0.14), taper=(0.55, 0.65))  # hood
        h.cone((0, -0.18, 0.2), (0, -0.34, 0.0), 0.08, p["robe_dark"], segments=4)
        rig.joint("eyes", "head", (0, 0.125, 0.12))
        for sx in (-1, 1):
            rig.mesh("eyes").box((0.022, 0.012, 0.018), p["glow"], pos=(sx * 0.042, 0, 0))
    # arms
    for side, sx in (("l", -1), ("r", 1)):
        m = seg(rig, f"{side}_arm", "torso", (sx * 0.22, -0.01, 0.50), (0, 0, -0.30),
                0.035, 0.028, p["robe"] if mage else B, hpr=(0, 12, sx * -6), segments=5)
        m.sphere(0.05, p["robe"] if mage else D, rings=3, segments=5)
        m = seg(rig, f"{side}_forearm", f"{side}_arm", (0, 0, -0.30), (0, 0, -0.27),
                0.028, 0.024, B, hpr=(0, 28, 0), segments=5)
        m.box((0.06, 0.05, 0.09), B, pos=(0, 0.01, -0.31))
        for f in range(3):
            m.box((0.012, 0.012, 0.06), D, pos=(-0.02 + f * 0.02, 0.02, -0.38))
        rig.joint(f"{side}_hand", f"{side}_forearm", (0, 0.01, -0.32))
    if not mage:
        # rusty longsword, raised forward
        s = rig.mesh("r_hand")
        s.box((0.035, 0.035, 0.14), p["leather"], pos=(0, 0, 0.0))                # grip
        s.box((0.20, 0.04, 0.035), p["iron"], pos=(0, 0, 0.08))                   # crossguard
        s.prism([(-0.035, 0.1), (0.035, 0.1), (0.028, 0.72), (0, 0.80), (-0.028, 0.72)],
                0.018, p["iron"], hpr=(0, 0, 0))                                  # blade
        s.box((0.02, 0.022, 0.18), p["rust"], pos=(0.012, 0, 0.35))                # rust patch
        # round wooden shield strapped to left forearm
        rig["l_arm"].set_hpr(0, 25, 12)
        sh = rig.mesh("l_forearm")
        sh.tube((-0.035, 0.02, -0.15), (-0.075, 0.02, -0.15), 0.23, 0.22, p["wood"], segments=8)
        sh.tube((-0.074, 0.02, -0.15), (-0.08, 0.02, -0.15), 0.23, 0.225, p["iron"], segments=8)
        sh.cone((-0.08, 0.02, -0.15), (-0.13, 0.02, -0.15), 0.06, p["iron"], segments=6)
    else:
        rig["r_arm"].set_hpr(0, 8, -28)
        rig["r_forearm"].set_hpr(0, 38, 10)
        st = rig.mesh("r_hand")
        st.tube((0, 0, -0.85), (0, 0, 0.55), 0.024, 0.03, p["wood"], segments=5)
        st.cone((0, 0, 0.55), (0.06, 0, 0.66), 0.03, p["wood"], segments=4)
        st.cone((0, 0, 0.55), (-0.06, 0, 0.66), 0.03, p["wood"], segments=4)
        rig.joint("staff_gem", "r_hand", (0, 0, 0.66))
        rig.mesh("staff_gem").sphere(0.055, p["glow"], scale=(0.8, 0.8, 1.4), rings=2, segments=4)
        rig["l_arm"].set_hpr(0, 40, 20)
        rig["l_forearm"].set_hpr(0, 45, 0)
    if not mage:
        rig["r_arm"].set_hpr(0, 25, -25)
        rig["r_forearm"].set_hpr(0, 45, 0)
        aim(rig, "r_hand", (0.75, 0.45, 0.65))   # sword points forward, tip raised
    else:
        aim(rig, "r_hand", (0.05, 0.1, 1.0))    # staff upright
    return rig


@register("skeleton_warrior", "Skeleton Warrior", "skeleton", "medium", "biped",
          MonsterStats(24, 32, "melee (slash)", 5, 2.4, "crush weapons",
                       aggressive=True, notes="Immune to poison. Reassembles once if not finished with crush."),
          WARRIOR, 1.85)
def build_skeleton_warrior():
    return _skeleton("skeleton_warrior", WARRIOR).bake()


@register("skeleton_mage", "Skeleton Mage", "skeleton", "medium", "biped",
          MonsterStats(34, 38, "magic (necrotic bolt)", 8, 3.0, "crush + ranged",
                       aggressive=True, notes="Keeps 3-4 tiles distance; drains Prayer on hit."),
          MAGE, 1.85)
def build_skeleton_mage():
    rig = _skeleton("skeleton_mage", MAGE, mage=True).bake()
    rig["eyes"].set_light_off()
    rig["staff_gem"].set_light_off()
    return rig
