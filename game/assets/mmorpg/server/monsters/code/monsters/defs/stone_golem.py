"""Stone Golem - 2.6 m animated barrow-stone guardian. Stacked, slightly
skewed boulders, moss on the shoulders, amber rune-light in the chest crack
and eye slit (unlit joints = emissive)."""
from ..mesh_builder import Rig
from ..registry import MonsterStats, register

P = {"stone": "#7b776c", "stone_dark": "#5b584f", "stone_light": "#958f82",
     "moss": "#5f6d3a", "moss_dark": "#4a5630", "rune": "#e0a542"}


@register("stone_golem", "Stone Golem", "golem", "large", "biped",
          MonsterStats(70, 120, "melee (crush)", 15, 3.6, "crush (pickaxes deal +20%) / water spells",
                       aggressive=False, notes="Very slow. Takes 50% less from stab and slash."),
          P, 2.6)
def build_stone_golem():
    rig = Rig("stone_golem")
    S, D, L = P["stone"], P["stone_dark"], P["stone_light"]
    rig.joint("hips", "root", (0, 0, 1.05))
    rig.mesh("hips").box((0.70, 0.46, 0.34), D, hpr=(4, 0, 2), taper=(1.1, 1.0))
    for side, sx in (("l", -1), ("r", 1)):
        rig.joint(f"{side}_leg", "hips", (sx * 0.26, 0, -0.12), (0, 4, 0))
        m = rig.mesh(f"{side}_leg")
        m.box((0.34, 0.36, 0.46), S, pos=(0, 0, -0.24), hpr=(sx * 6, 0, sx * 4), taper=(0.85, 0.85))
        rig.joint(f"{side}_shin", f"{side}_leg", (0, 0, -0.46), (0, -8, 0))
        m = rig.mesh(f"{side}_shin")
        m.box((0.30, 0.32, 0.40), D, pos=(0, 0, -0.20), hpr=(sx * -5, 3, 0), taper=(1.15, 1.1))
        m.box((0.42, 0.54, 0.14), S, pos=(0, 0.06, -0.44), hpr=(sx * 4, 0, 0), taper=(0.85, 0.8))
    rig.joint("torso", "hips", (0, 0, 0.16), (0, -8, 0))
    t = rig.mesh("torso")
    t.box((0.80, 0.56, 0.50), S, pos=(0, 0, 0.26), hpr=(-3, 0, 2), taper=(1.25, 1.1))
    t.box((1.05, 0.66, 0.36), L, pos=(0, -0.02, 0.66), hpr=(3, 2, -2), taper=(0.8, 0.8))
    t.box((0.40, 0.30, 0.20), D, pos=(0.18, -0.22, 0.95), hpr=(20, 10, 0))      # hunched back rock
    t.box((0.36, 0.30, 0.10), P["moss"], pos=(-0.26, -0.02, 0.88), hpr=(-8, 0, 6), taper=(0.7, 0.7))
    t.box((0.30, 0.34, 0.08), P["moss_dark"], pos=(0.30, 0.02, 0.86), hpr=(10, 0, -4), taper=(0.7, 0.7))
    for (x, y) in ((-0.34, 0.05), (-0.2, -0.1), (0.32, 0.1)):
        t.cone((x, y, 0.90), (x * 1.05, y, 1.04), 0.04, P["moss"], segments=3)   # grass tufts
    rig.joint("rune", "torso", (0.02, 0.29, 0.36))
    rn = rig.mesh("rune")
    rn.box((0.05, 0.02, 0.30), P["rune"], hpr=(0, 0, 12))
    rn.box((0.16, 0.02, 0.04), P["rune"], pos=(0.0, 0, 0.05), hpr=(0, 0, -20))
    rn.box((0.04, 0.02, 0.14), P["rune"], pos=(-0.07, 0, -0.10), hpr=(0, 0, -30))
    # small head set low and forward
    rig.joint("head", "torso", (0, 0.20, 0.90), (0, 8, 0))
    h = rig.mesh("head")
    h.box((0.34, 0.32, 0.28), S, pos=(0, 0.04, 0.10), hpr=(5, 0, -3), taper=(0.85, 0.9))
    h.box((0.40, 0.14, 0.09), D, pos=(0, 0.17, 0.19), hpr=(0, -12, 0))           # brow slab
    h.box((0.14, 0.10, 0.10), P["moss"], pos=(-0.08, -0.02, 0.27), taper=(0.6, 0.6))
    rig.joint("eyes", "head", (0, 0.205, 0.11))
    rig.mesh("eyes").box((0.22, 0.02, 0.035), P["rune"])
    # arms: boulder shoulder, slab upper arm, huge fist
    for side, sx in (("l", -1), ("r", 1)):
        rig.joint(f"{side}_arm", "torso", (sx * 0.66, 0, 0.66), (0, 10, sx * -8))
        m = rig.mesh(f"{side}_arm")
        m.sphere(0.27, L, scale=(1.0, 1.0, 0.9), rings=2, segments=5)
        m.box((0.28, 0.28, 0.46), S, pos=(0, 0, -0.34), hpr=(sx * 8, 0, 0), taper=(0.85, 0.85))
        m.box((0.18, 0.16, 0.06), P["moss"], pos=(0, 0, 0.22), taper=(0.7, 0.7))
        rig.joint(f"{side}_forearm", f"{side}_arm", (0, 0, -0.58), (0, 22, 0))
        m = rig.mesh(f"{side}_forearm")
        m.box((0.32, 0.32, 0.44), D, pos=(0, 0, -0.20), hpr=(sx * -6, 0, 3), taper=(1.2, 1.2))
        m.box((0.44, 0.42, 0.36), S, pos=(0, 0.02, -0.56), hpr=(sx * 12, 5, 4))       # fist boulder
        m.box((0.10, 0.02, 0.18), P["rune"], pos=(sx * 0.02, 0.17, -0.20), hpr=(0, 0, sx * 15))
    rig.bake()
    for j in ("rune", "eyes"):
        rig[j].set_light_off()
    return rig
