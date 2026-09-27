"""Wolves: Grey Wolf (0.9 m at the shoulder, lean) and Dire Wolf (1.35x,
darker, scarred, bristling mane, bigger fangs). Quadruped joint names so the
quadruped/wolf profiles work unchanged."""
import math

from ..mesh_builder import Rig
from ..registry import MonsterStats, register

GREY = {"fur": "#7c776e", "fur_dark": "#57524b", "belly": "#b3aa98", "muzzle": "#c1b8a5",
        "nose": "#1f1c1a", "eye": "#d9a53a", "mouth": "#5a2a26", "tooth": "#e0d8c0", "claw": "#3a342e"}
DIRE = {"fur": "#433d38", "fur_dark": "#2c2825", "belly": "#6f665b", "muzzle": "#5e564d",
        "nose": "#151312", "eye": "#d5552c", "mouth": "#4a1e1b", "tooth": "#e2d9bf", "claw": "#2a2521",
        "mane": "#2e2a27", "scar": "#8e6a60"}


def _wolf(name, p, s=1.0, dire=False):
    rig = Rig(name)
    rig.joint("body", "root", (0, 0, 0.62 * s))
    b = rig.mesh("body")
    b.sphere(0.26 * s, p["fur"], pos=(0, 0.28 * s, 0.02 * s), scale=(0.74, 1.15, 1.05), rings=4, segments=7)  # deep chest
    b.tube((0, 0.20 * s, -0.02 * s), (0, -0.38 * s, 0.03 * s), 0.18 * s, 0.14 * s, p["fur"], segments=7,
           squash=1.15)                                                        # tucked waist
    b.sphere(0.19 * s, p["fur_dark"], pos=(0, -0.42 * s, 0.03 * s), scale=(0.95, 1.1, 1.0), rings=3, segments=7)  # hips
    b.box((0.26 * s, 0.50 * s, 0.10 * s), p["belly"], pos=(0, 0.14 * s, -0.19 * s), taper=(0.7, 0.9))
    b.box((0.22 * s, 0.66 * s, 0.06 * s), p["fur_dark"], pos=(0, -0.08 * s, 0.19 * s), taper=(0.6, 0.9))  # saddle
    if dire:
        for i in range(9):                                                   # bristling mane
            y = 0.52 - i * 0.07
            ang = math.radians(-35 + (i % 3) * 35)
            for sx in (-1, 1):
                b.cone((sx * 0.08 * s, y * s, 0.20 * s),
                       ((sx * 0.08 + math.sin(ang) * 0.10 * sx) * s, (y - 0.12) * s, (0.44 - i * 0.02) * s),
                       0.06 * s, p["mane"], segments=3)
        for (y, z, a) in ((-0.10, 0.10, 25), (-0.2, 0.02, 15)):             # flank scars
            b.box((0.03 * s, 0.24 * s, 0.022 * s), p["scar"], pos=(0.17 * s, y * s, z * s), hpr=(0, a, 0))
    # neck + head
    rig.joint("neck_0", "body", (0, 0.44 * s, 0.10 * s), (0, 0, 0))
    n = rig.mesh("neck_0")
    n.tube((0, 0, 0), (0, 0.22 * s, 0.18 * s), 0.16 * s, 0.12 * s, p["fur"], segments=6)
    n.box((0.20 * s, 0.16 * s, 0.14 * s), p["belly"], pos=(0, 0.10 * s, -0.02 * s), hpr=(0, 40, 0))  # throat ruff
    if dire:
        for k in range(5):
            n.cone((0, (0.02 + k * 0.05) * s, (0.12 + k * 0.04) * s),
                   (0, (-0.06 + k * 0.05) * s, (0.34 + k * 0.03) * s), 0.06 * s, p["mane"], segments=3, squash=0.6)
    rig.joint("head", "neck_0", (0, 0.24 * s, 0.20 * s), (0, -14, 0))
    h = rig.mesh("head")
    h.box((0.24 * s, 0.24 * s, 0.20 * s), p["fur"], pos=(0, 0.04 * s, 0.03 * s), taper=(0.85, 0.9))
    h.box((0.12 * s, 0.24 * s, 0.10 * s), p["muzzle"], pos=(0, 0.26 * s, -0.01 * s), taper=(0.8, 0.9))
    h.box((0.06 * s, 0.05 * s, 0.04 * s), p["nose"], pos=(0, 0.385 * s, 0.03 * s))
    h.box((0.26 * s, 0.07 * s, 0.05 * s), p["fur_dark"], pos=(0, 0.14 * s, 0.11 * s), hpr=(0, -18, 0))  # brow
    for sx in (-1, 1):
        tip_z = 0.28 if not (dire and sx < 0) else 0.22                     # dire: torn left ear
        h.cone((sx * 0.08 * s, -0.02 * s, 0.10 * s), (sx * 0.11 * s, -0.06 * s, tip_z * s), 0.055 * s,
               p["fur_dark"], segments=3, squash=0.5)
        h.box((0.06 * s, 0.10 * s, 0.10 * s), p["fur"], pos=(sx * 0.13 * s, 0.0, -0.02 * s))  # cheek ruff
        h.cone((sx * 0.035 * s, 0.33 * s, -0.05 * s), (sx * 0.035 * s, 0.33 * s, -0.10 * s),
               (0.018 if not dire else 0.024) * s, p["tooth"], segments=3)  # fangs
    if dire:
        h.box((0.02 * s, 0.16 * s, 0.02 * s), p["scar"], pos=(0.065 * s, 0.14 * s, 0.10 * s), hpr=(20, -20, 0))
    rig.joint("eyes", "head", (0, 0.16 * s, 0.07 * s))
    for sx in (-1, 1):
        rig.mesh("eyes").box((0.045 * s, 0.02 * s, 0.025 * s), p["eye"], pos=(sx * 0.075 * s, 0, 0),
                             hpr=(sx * -20, 0, 0))
    rig.joint("jaw", "head", (0, 0.10 * s, -0.07 * s), (0, -12 if dire else -6, 0))
    j = rig.mesh("jaw")
    j.box((0.11 * s, 0.26 * s, 0.05 * s), p["muzzle"], pos=(0, 0.14 * s, -0.02 * s), taper=(0.85, 0.9))
    j.box((0.08 * s, 0.22 * s, 0.01 * s), p["mouth"], pos=(0, 0.14 * s, 0.006 * s))
    for sx in (-1, 1):
        j.cone((sx * 0.035 * s, 0.24 * s, 0.0), (sx * 0.035 * s, 0.24 * s, 0.05 * s), 0.016 * s, p["tooth"], segments=3)
    # legs: straight front, digitigrade hind with a hock
    for side, sx in (("l", -1), ("r", 1)):
        rig.joint(f"{side}_front_leg", "body", (sx * 0.13 * s, 0.36 * s, -0.08 * s))
        m = rig.mesh(f"{side}_front_leg")
        m.tube((0, 0, 0.05 * s), (0, -0.02 * s, -0.28 * s), 0.08 * s, 0.05 * s, p["fur"], segments=5)
        rig.joint(f"{side}_front_shin", f"{side}_front_leg", (0, -0.02 * s, -0.28 * s))
        m = rig.mesh(f"{side}_front_shin")
        m.tube((0, 0, 0), (0, 0.02 * s, -0.24 * s), 0.045 * s, 0.035 * s, p["fur_dark"], segments=5)
        m.box((0.08 * s, 0.11 * s, 0.04 * s), p["fur_dark"], pos=(0, 0.04 * s, -0.25 * s), taper=(0.9, 0.8))
        for c in (-1, 1):
            m.cone((c * 0.02 * s, 0.09 * s, -0.26 * s), (c * 0.02 * s, 0.13 * s, -0.27 * s), 0.01 * s, p["claw"], segments=3)
        rig.joint(f"{side}_hind_leg", "body", (sx * 0.12 * s, -0.44 * s, -0.02 * s))
        m = rig.mesh(f"{side}_hind_leg")
        m.sphere(0.12 * s, p["fur_dark"], scale=(0.8, 1.1, 1.2), rings=3, segments=5)
        m.tube((0, 0, 0), (0, 0.10 * s, -0.28 * s), 0.10 * s, 0.05 * s, p["fur"], segments=5)
        rig.joint(f"{side}_hind_shin", f"{side}_hind_leg", (0, 0.10 * s, -0.28 * s))
        m = rig.mesh(f"{side}_hind_shin")
        m.tube((0, 0, 0), (0, -0.12 * s, -0.14 * s), 0.05 * s, 0.035 * s, p["fur_dark"], segments=5)
        m.tube((0, -0.12 * s, -0.14 * s), (0, -0.09 * s, -0.33 * s), 0.035 * s, 0.03 * s, p["fur_dark"], segments=5)
        m.box((0.08 * s, 0.11 * s, 0.04 * s), p["fur_dark"], pos=(0, -0.06 * s, -0.34 * s), taper=(0.9, 0.8))
    # bushy tail
    rig.joint("tail", "body", (0, -0.56 * s, 0.10 * s), (0, 42, 0))
    tl = rig.mesh("tail")
    tl.tube((0, 0, 0), (0, -0.22 * s, -0.02 * s), 0.05 * s, 0.09 * s, p["fur"], segments=6)
    tl.tube((0, -0.22 * s, -0.02 * s), (0, -0.44 * s, -0.10 * s), 0.09 * s, 0.0, p["fur_dark"], segments=6)
    return rig


@register("wolf_grey", "Grey Wolf", "wolf", "medium", "wolf",
          MonsterStats(18, 26, "melee (stab)", 4, 1.8, "slash / ranged",
                       aggressive=True, notes="Packs of 3-4; flees at 20% HP unless the pack leader is alive."),
          GREY, 0.9)
def build_wolf_grey():
    rig = _wolf("wolf_grey", GREY).bake()
    rig["eyes"].set_light_off()
    return rig


@register("wolf_dire", "Dire Wolf", "wolf", "large", "wolf",
          MonsterStats(49, 72, "melee (stab) + bleed", 10, 1.8, "slash / fire",
                       aggressive=True, notes="Howl buffs nearby wolves +10% accuracy; bite causes bleed (1 dmg/2 ticks x5)."),
          DIRE, 1.2)
def build_wolf_dire():
    rig = _wolf("wolf_dire", DIRE, s=1.35, dire=True).bake()
    rig["eyes"].set_light_off()
    return rig
