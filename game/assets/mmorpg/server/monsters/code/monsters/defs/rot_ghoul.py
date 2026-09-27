"""Rot Ghoul - gaunt, hunched graveyard scavenger. 1.75 m if it stood up,
~1.4 m hunched. Lanky knuckle-dragging arms with black claws, visible ribs,
spine knobs, long hanging jaw and sickly yellow eyes."""
from ..mesh_builder import Rig
from ..registry import MonsterStats, register
from .parts import seg

P = {"skin": "#7d8472", "skin_dark": "#585e4f", "rib": "#9ca28b", "cloth": "#4d4235",
     "cloth_dark": "#382f25", "claw": "#2f2a24", "eye": "#d0c56a", "mouth": "#3a2020",
     "tooth": "#b9ae8a", "hair": "#2e2c28"}


@register("rot_ghoul", "Rot Ghoul", "ghoul", "medium", "biped",
          MonsterStats(33, 44, "melee (slash) + disease", 7, 1.8, "fire / holy; crush",
                       aggressive=True, notes="Disease: drains 1 Strength per hit until cured. Feeds on corpses to heal."),
          P, 1.45)
def build_rot_ghoul():
    rig = Rig("rot_ghoul")
    rig.joint("hips", "root", (0, 0, 0.78))
    pel = rig.mesh("hips")
    pel.box((0.28, 0.16, 0.14), P["skin_dark"], taper=(1.2, 1))
    pel.box((0.32, 0.22, 0.20), P["cloth"], pos=(0, 0.0, -0.06), taper=(1.0, 1.0))
    pel.box((0.14, 0.04, 0.22), P["cloth_dark"], pos=(0.04, 0.12, -0.18), hpr=(0, 0, 8), taper=(0.6, 1))
    # bent, digitigrade-ish legs
    for side, sx in (("l", -1), ("r", 1)):
        m = seg(rig, f"{side}_leg", "hips", (sx * 0.11, 0, -0.04), (0, 0, -0.42), 0.055, 0.04,
                P["skin"], hpr=(0, 28, sx * -4), segments=5)
        m.sphere(0.05, P["skin_dark"], pos=(0, 0, -0.42), rings=2, segments=5)
        m = seg(rig, f"{side}_shin", f"{side}_leg", (0, 0, -0.42), (0, 0, -0.40), 0.042, 0.032,
                P["skin"], hpr=(0, -50, 0), segments=5)
        m.box((0.10, 0.22, 0.05), P["skin_dark"], pos=(0, 0.08, -0.41), hpr=(0, 22, 0), taper=(0.9, 0.6))
        for t in (-1, 0, 1):
            m.cone((t * 0.03, 0.18, -0.40), (t * 0.04, 0.24, -0.34 - 0.08), 0.012, P["claw"], segments=3)
    # thin torso bent far forward
    rig.joint("torso", "hips", (0, 0, 0.06), (0, -45, 0))
    t = rig.mesh("torso")
    t.box((0.26, 0.18, 0.24), P["skin_dark"], pos=(0, 0, 0.12), taper=(1.2, 1.1))
    t.box((0.38, 0.24, 0.26), P["skin"], pos=(0, 0, 0.36), taper=(1.1, 0.95))
    for i in range(4):                                       # ribs
        t.box((0.30 - i * 0.02, 0.02, 0.025), P["rib"], pos=(0, 0.125, 0.28 + i * 0.055), hpr=(0, 0, 0))
    for i in range(6):                                       # spine knobs
        t.sphere(0.035, P["rib"], pos=(0, -0.12, 0.08 + i * 0.075), rings=2, segments=4)
    # head: long, gaunt, jaw hanging open
    rig.joint("head", "torso", (0, 0.06, 0.52), (0, 55, 0))
    h = rig.mesh("head")
    h.box((0.05, 0.05, 0.10), P["skin_dark"], pos=(0, -0.02, 0.0))            # neck
    h.sphere(0.12, P["skin"], pos=(0, 0.02, 0.12), scale=(0.9, 1.2, 1.0), rings=3, segments=6)
    h.box((0.20, 0.06, 0.05), P["skin_dark"], pos=(0, 0.13, 0.15), hpr=(0, -10, 0))   # brow
    h.box((0.12, 0.14, 0.08), P["skin"], pos=(0, 0.15, 0.06), taper=(0.8, 0.8))      # snout
    for sx in (-1, 1):
        h.cone((sx * 0.03, 0.2, 0.03), (sx * 0.03, 0.21, -0.01), 0.012, P["tooth"], segments=3)
    for k in range(4):                                       # stringy hair strands
        x = -0.06 + k * 0.04
        h.tube((x, -0.02, 0.22), (x * 1.8, -0.12, 0.02 - (k % 2) * 0.06), 0.012, 0.004, P["hair"], segments=3)
    rig.joint("eyes", "head", (0, 0.145, 0.115))
    for sx in (-1, 1):
        rig.mesh("eyes").box((0.035, 0.012, 0.02), P["eye"], pos=(sx * 0.045, 0, 0))
    rig.joint("jaw", "head", (0, 0.06, 0.04), (0, -25, 0))
    j = rig.mesh("jaw")
    j.box((0.11, 0.16, 0.035), P["skin_dark"], pos=(0, 0.08, -0.02), taper=(0.8, 1))
    j.box((0.08, 0.12, 0.01), P["mouth"], pos=(0, 0.08, 0.0))
    for sx in (-1, 1):
        j.cone((sx * 0.035, 0.14, 0.0), (sx * 0.035, 0.145, 0.035), 0.01, P["tooth"], segments=3)
    # very long arms reaching the ground, black claws
    for side, sx in (("l", -1), ("r", 1)):
        m = seg(rig, f"{side}_arm", "torso", (sx * 0.20, 0.02, 0.46), (0, 0, -0.40), 0.045, 0.035,
                P["skin"], hpr=(0, 30, sx * -12), segments=5)
        m.sphere(0.055, P["skin_dark"], rings=2, segments=5)
        m = seg(rig, f"{side}_forearm", f"{side}_arm", (0, 0, -0.40), (0, 0, -0.38), 0.036, 0.03,
                P["skin"], hpr=(0, 18, 0), segments=5)
        m.box((0.08, 0.06, 0.10), P["skin_dark"], pos=(0, 0.01, -0.42))
        for f in range(4):
            a = (f - 1.5) * 0.022
            m.tube((a, 0.02, -0.46), (a * 1.6, 0.06, -0.58), 0.011, 0.008, P["skin"], segments=3)
            m.cone((a * 1.6, 0.06, -0.58), (a * 1.8, 0.14, -0.64), 0.009, P["claw"], segments=3)
    rig.bake()
    rig["eyes"].set_light_off()
    return rig
