"""Dragons: green / red / black tiers share one rig, scaled and decorated.
Quadruped body, 2-joint neck, jaw joint, 3-joint tail, raised half-spread
wings (wing joint rolls to flap)."""
from ..mesh_builder import Rig
from ..registry import MonsterStats, register

GREEN = {"body": "#4f6b35", "dark": "#3a4f28", "belly": "#a39a68", "wing": "#667543",
         "wing_bone": "#3a4f28", "horn": "#cfc3a0", "eye": "#e3c243", "claw": "#d6ccb0",
         "mouth": "#5a2a22"}
RED = {"body": "#8c3b2a", "dark": "#62291d", "belly": "#c49a64", "wing": "#9e5236",
       "wing_bone": "#62291d", "horn": "#d8cba5", "eye": "#f2c14a", "claw": "#dcd0b2",
       "mouth": "#4a1d18"}
BLACK = {"body": "#3b393e", "dark": "#262428", "belly": "#6a625a", "wing": "#57505a",
         "wing_bone": "#262428", "horn": "#bfb49a", "eye": "#d8452f", "claw": "#c9bfa6",
         "mouth": "#3a1512"}


def _dragon(name, p, s=1.0, elder=False):
    rig = Rig(name)
    rig.joint("body", "root", (0, 0, 1.05 * s))
    b = rig.mesh("body")
    b.sphere(0.55 * s, p["body"], scale=(0.85, 1.5, 0.78), rings=5, segments=8)
    b.sphere(0.50 * s, p["belly"], pos=(0, 0.05 * s, -0.10 * s), scale=(0.72, 1.45, 0.70),
             rings=4, segments=8)
    for i in range(6):   # dorsal spikes along the spine
        y = (0.55 - i * 0.22) * s
        hgt = (0.18 + (0.06 if elder else 0)) * s * (1 - abs(i - 2) * 0.12)
        b.cone((0, y, 0.40 * s), (0, y - 0.10 * s, 0.40 * s + hgt), 0.06 * s, p["horn"], segments=4,
               squash=0.5)

    # ---- neck + head -----------------------------------------------------
    rig.joint("neck_0", "body", (0, 0.72 * s, 0.18 * s))
    n0 = rig.mesh("neck_0")
    n0.tube((0, 0, 0), (0, 0.32 * s, 0.38 * s), 0.27 * s, 0.20 * s, p["body"], segments=7)
    n0.tube((0, 0.06 * s, -0.10 * s), (0, 0.36 * s, 0.26 * s), 0.16 * s, 0.13 * s, p["belly"],
            segments=6)
    n0.cone((0, 0.12 * s, 0.24 * s), (0, 0.04 * s, 0.42 * s), 0.05 * s, p["horn"], segments=4, squash=0.5)
    rig.joint("neck_1", "neck_0", (0, 0.32 * s, 0.38 * s))
    n1 = rig.mesh("neck_1")
    n1.tube((0, 0, 0), (0, 0.28 * s, 0.30 * s), 0.20 * s, 0.16 * s, p["body"], segments=7)
    n1.cone((0, 0.10 * s, 0.18 * s), (0, 0.02 * s, 0.34 * s), 0.045 * s, p["horn"], segments=4, squash=0.5)
    rig.joint("head", "neck_1", (0, 0.28 * s, 0.30 * s), (0, -12, 0))
    h = rig.mesh("head")
    h.box((0.34 * s, 0.36 * s, 0.26 * s), p["body"], pos=(0, 0.08 * s, 0.04 * s), taper=(0.85, 0.9))
    h.box((0.24 * s, 0.40 * s, 0.15 * s), p["body"], pos=(0, 0.42 * s, 0.02 * s),
          taper=(0.8, 0.85))                                                   # upper snout
    h.box((0.36 * s, 0.10 * s, 0.07 * s), p["dark"], pos=(0, 0.20 * s, 0.17 * s),
          hpr=(0, -12, 0))                                                     # brow ridge
    for sx in (-1, 1):
        h.box((0.03 * s, 0.03 * s, 0.03 * s), "#1b1612", pos=(sx * 0.06 * s, 0.62 * s, 0.07 * s))  # nostrils
        h.cone((sx * 0.13 * s, -0.02 * s, 0.14 * s), (sx * 0.24 * s, -0.55 * s, 0.34 * s),
               0.065 * s, p["horn"], segments=5)                                  # main horns
        h.prism([(0, 0), (0.16 * s, -0.04 * s), (0.05 * s, 0.14 * s)], 0.02 * s, p["dark"],
                pos=(sx * 0.17 * s, -0.02 * s, 0.0), hpr=(sx * -70, 0, sx * -20))   # cheek frill
        for t in range(3):                                                        # upper teeth
            h.cone((sx * 0.09 * s, (0.30 + t * 0.1) * s, -0.05 * s),
                   (sx * 0.09 * s, (0.30 + t * 0.1) * s, -0.10 * s), 0.018 * s, p["claw"], segments=3)
        if elder:
            h.cone((sx * 0.16 * s, 0.10 * s, 0.10 * s), (sx * 0.34 * s, -0.25 * s, 0.10 * s),
                   0.045 * s, p["horn"], segments=4)                              # extra horns
            h.cone((sx * 0.08 * s, 0.45 * s, 0.09 * s), (sx * 0.08 * s, 0.40 * s, 0.20 * s),
                   0.03 * s, p["horn"], segments=4)                               # snout spikes
    rig.joint("eyes", "head", (0, 0.20 * s, 0.11 * s))
    for sx in (-1, 1):
        rig.mesh("eyes").box((0.035 * s, 0.07 * s, 0.03 * s), p["eye"], pos=(sx * 0.155 * s, 0, 0),
                             hpr=(sx * -15, 0, 0))
    rig.joint("jaw", "head", (0, 0.12 * s, -0.08 * s), (0, -10, 0))
    j = rig.mesh("jaw")
    j.box((0.24 * s, 0.50 * s, 0.08 * s), p["belly"], pos=(0, 0.26 * s, -0.02 * s), taper=(0.75, 0.9))
    j.box((0.18 * s, 0.42 * s, 0.02 * s), p["mouth"], pos=(0, 0.26 * s, 0.025 * s))
    for sx in (-1, 1):
        for t in range(3):
            j.cone((sx * 0.08 * s, (0.22 + t * 0.1) * s, 0.02 * s),
                   (sx * 0.08 * s, (0.22 + t * 0.1) * s, 0.07 * s), 0.016 * s, p["claw"], segments=3)

    # ---- legs ------------------------------------------------------------
    for side, sx in (("l", -1), ("r", 1)):
        # front
        rig.joint(f"{side}_front_leg", "body", (sx * 0.38 * s, 0.50 * s, -0.10 * s))
        m = rig.mesh(f"{side}_front_leg")
        m.sphere(0.17 * s, p["body"], rings=3, segments=6)
        m.tube((0, 0, 0), (sx * 0.03 * s, 0.05 * s, -0.45 * s), 0.15 * s, 0.11 * s, p["body"], segments=6)
        rig.joint(f"{side}_front_shin", f"{side}_front_leg", (sx * 0.03 * s, 0.05 * s, -0.45 * s))
        m = rig.mesh(f"{side}_front_shin")
        m.tube((0, 0, 0), (0, -0.02 * s, -0.42 * s), 0.11 * s, 0.09 * s, p["dark"], segments=6)
        m.box((0.20 * s, 0.24 * s, 0.08 * s), p["dark"], pos=(0, 0.06 * s, -0.44 * s), taper=(0.9, 0.7))
        for c in (-1, 0, 1):
            m.cone((c * 0.06 * s, 0.16 * s, -0.46 * s), (c * 0.08 * s, 0.26 * s, -0.47 * s),
                   0.025 * s, p["claw"], segments=4)
        # hind (bigger thigh, digitigrade bend)
        rig.joint(f"{side}_hind_leg", "body", (sx * 0.40 * s, -0.55 * s, -0.02 * s))
        m = rig.mesh(f"{side}_hind_leg")
        m.sphere(0.24 * s, p["body"], scale=(0.9, 1.2, 1.1), rings=3, segments=6)
        m.tube((0, 0, 0), (sx * 0.04 * s, 0.22 * s, -0.46 * s), 0.20 * s, 0.12 * s, p["body"], segments=6)
        rig.joint(f"{side}_hind_shin", f"{side}_hind_leg", (sx * 0.04 * s, 0.22 * s, -0.46 * s))
        m = rig.mesh(f"{side}_hind_shin")
        m.tube((0, 0, 0), (0, -0.18 * s, -0.43 * s), 0.12 * s, 0.09 * s, p["dark"], segments=6)
        m.box((0.22 * s, 0.28 * s, 0.08 * s), p["dark"], pos=(0, -0.10 * s, -0.47 * s), taper=(0.9, 0.7))
        for c in (-1, 0, 1):
            m.cone((c * 0.06 * s, 0.02 * s, -0.49 * s), (c * 0.08 * s, 0.13 * s, -0.50 * s),
                   0.028 * s, p["claw"], segments=4)

    # ---- wings (half spread, raised) -----------------------------------
    for side, sx in (("l", -1), ("r", 1)):
        rig.joint(f"{side}_wing", "body", (sx * 0.28 * s, 0.30 * s, 0.38 * s), (0, 0, sx * -10))
        w = rig.mesh(f"{side}_wing")
        root_f, root_b = (0, 0, 0), (0, -0.70 * s, -0.05 * s)
        elbow = (sx * 0.62 * s, -0.10 * s, 0.55 * s)
        wrist = (sx * 1.20 * s, -0.30 * s, 0.80 * s)
        tips = [(sx * 1.75 * s, -0.75 * s, 0.35 * s), (sx * 1.45 * s, -1.05 * s, 0.05 * s),
                (sx * 0.95 * s, -1.05 * s, -0.05 * s)]
        w.tube(root_f, elbow, 0.08 * s, 0.06 * s, p["wing_bone"], segments=5)
        w.tube(elbow, wrist, 0.06 * s, 0.04 * s, p["wing_bone"], segments=5)
        w.cone(wrist, (sx * 1.32 * s, -0.22 * s, 1.02 * s), 0.04 * s, p["horn"], segments=4)  # thumb claw
        for t in tips:
            w.tube(wrist, t, 0.03 * s, 0.012 * s, p["wing_bone"], segments=4)
        # membrane panels (double sided, alternating shade for the faceted look)
        panels = [(root_f, elbow, root_b), (elbow, wrist, tips[2], root_b),
                  (wrist, tips[0], tips[1]), (wrist, tips[1], tips[2])]
        for k, poly in enumerate(panels):
            w.polygon(poly, p["wing"] if k % 2 == 0 else p["dark"] if k == 3 else p["wing"])

    # ---- tail -------------------------------------------------------------
    rig.joint("tail_0", "body", (0, -0.78 * s, 0.02 * s), (8, 0, 0))
    t0 = rig.mesh("tail_0")
    t0.tube((0, 0, 0), (0, -0.55 * s, -0.20 * s), 0.25 * s, 0.17 * s, p["body"], segments=7)
    t0.cone((0, -0.28 * s, 0.18 * s), (0, -0.38 * s, 0.34 * s), 0.05 * s, p["horn"], segments=4, squash=0.5)
    rig.joint("tail_1", "tail_0", (0, -0.55 * s, -0.20 * s), (15, 0, 0))
    t1 = rig.mesh("tail_1")
    t1.tube((0, 0, 0), (0, -0.55 * s, -0.30 * s), 0.17 * s, 0.10 * s, p["body"], segments=6)
    t1.cone((0, -0.25 * s, 0.08 * s), (0, -0.36 * s, 0.22 * s), 0.04 * s, p["horn"], segments=4, squash=0.5)
    rig.joint("tail_2", "tail_1", (0, -0.55 * s, -0.30 * s), (18, 0, 0))
    t2 = rig.mesh("tail_2")
    t2.tube((0, 0, 0), (0, -0.55 * s, -0.12 * s), 0.10 * s, 0.035 * s, p["body"], segments=5)
    t2.prism([(0, 0), (0.12 * s, 0.10 * s), (0, 0.28 * s), (-0.12 * s, 0.10 * s)], 0.03 * s,
             p["dark"], pos=(0, -0.55 * s, -0.12 * s), hpr=(0, 100, 0))       # spade tip
    return rig


def _finish(rig):
    rig.bake()
    rig["eyes"].set_light_off()
    return rig


@register("dragon_green", "Green Dragon", "dragon", "large", "dragon",
          MonsterStats(68, 80, "melee (slash) + dragonfire", 8, 2.4, "stab / ranged; anti-dragon shield vs fire",
                       aggressive=True, notes="Dragonfire max 50 without anti-dragon shield."),
          GREEN, 2.9)
def build_dragon_green():
    return _finish(_dragon("dragon_green", GREEN, s=1.0))


@register("dragon_red", "Red Dragon", "dragon", "large", "dragon",
          MonsterStats(118, 130, "melee (slash) + dragonfire", 13, 2.4, "stab / ranged; anti-dragon shield vs fire",
                       aggressive=True, notes="Fire breath sets a 3x3 burning patch."),
          RED, 3.3)
def build_dragon_red():
    return _finish(_dragon("dragon_red", RED, s=1.15))


@register("dragon_black", "Black Dragon", "dragon", "boss", "dragon",
          MonsterStats(175, 200, "melee (slash) + dragonfire", 20, 2.4, "stab / ranged / water spells",
                       aggressive=True, notes="Breath alternates fire / poison. Slayer-tier."),
          BLACK, 4.3)
def build_dragon_black():
    return _finish(_dragon("dragon_black", BLACK, s=1.45, elder=True))
