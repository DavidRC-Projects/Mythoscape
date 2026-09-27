"""Spiders: giant spider (common) and broodmother (bloated, egg sacs).
Eight 3-part legs, each leg joint named leg_<l|r><0-3> -> knee_<l|r><0-3>."""
import math

from ..mesh_builder import Rig
from ..registry import MonsterStats, register

GIANT = {"body": "#3d3228", "body_dark": "#2a221b", "hair": "#54463a",
         "mark": "#9a8458", "fang": "#c9bda0", "eye": "#b8322a"}
BROOD = {"body": "#2f2a2e", "body_dark": "#1d1a1d", "hair": "#4a3f45",
         "mark": "#a6905a", "fang": "#d4c7a4", "eye": "#c2402f",
         "egg": "#c9c2a8", "egg_dark": "#9f977f"}


def _spider(name, p, s=1.0, brood=False):
    rig = Rig(name)
    rig.joint("body", "root", (0, 0, 0.42 * s))
    b = rig.mesh("body")
    b.sphere(0.24 * s, p["body"], pos=(0, 0.10 * s, 0), scale=(1.0, 1.15, 0.72), rings=4, segments=8)
    ab = 0.42 * s if brood else 0.34 * s
    b.sphere(ab, p["body_dark"], pos=(0, -0.42 * s - (0.08 * s if brood else 0), 0.10 * s),
             scale=(0.95, 1.2, 0.85), rings=5, segments=9)
    # abdomen markings: a row of flat diamonds along the back
    for i in range(4):
        y = -0.22 * s - i * 0.14 * s - (0.08 * s if brood else 0)
        z = 0.10 * s + ab * 0.80 - abs(i - 1.2) * 0.035 * s
        w = 0.07 * s * (1.25 - i * 0.18)
        b.sphere(w, p["mark"], pos=(0, y, z), scale=(1.0, 1.3, 0.35), rings=2, segments=4)
    # bristles
    for i in range(6):
        a = i * math.pi / 3
        b.cone((math.cos(a) * 0.2 * s, -0.42 * s + math.sin(a) * 0.2 * s, 0.10 * s + ab * 0.6),
               (math.cos(a) * 0.3 * s, -0.42 * s + math.sin(a) * 0.3 * s, 0.10 * s + ab * 0.95),
               0.025 * s, p["hair"], segments=3)
    if brood:
        # clutch of silk-wrapped egg sacs clinging to the abdomen
        for k, (x, y, z, r) in enumerate(((0.16, -0.62, 0.47, 0.12), (-0.12, -0.70, 0.49, 0.11),
                                          (0.02, -0.52, 0.53, 0.10), (-0.24, -0.52, 0.38, 0.09),
                                          (0.28, -0.46, 0.34, 0.09))):
            b.sphere(r * s, p["egg"] if k % 2 == 0 else p["egg_dark"], pos=(x * s, y * s, z * s),
                     scale=(1.0, 1.15, 0.8), rings=3, segments=6)
    # head, fangs, eyes
    rig.joint("head", "body", (0, 0.34 * s, 0.02 * s))
    h = rig.mesh("head")
    h.sphere(0.13 * s, p["body"], scale=(1.1, 1.0, 0.8), rings=3, segments=7)
    for sx in (-1, 1):
        h.tube((sx * 0.05 * s, 0.08 * s, -0.02 * s), (sx * 0.05 * s, 0.14 * s, -0.10 * s),
               0.035 * s, 0.03 * s, p["body_dark"], segments=5)
        h.cone((sx * 0.05 * s, 0.14 * s, -0.10 * s), (sx * 0.02 * s, 0.17 * s, -0.20 * s),
               0.028 * s, p["fang"], segments=4)
    rig.joint("eyes", "head", (0, 0.11 * s, 0.05 * s))
    e = rig.mesh("eyes")
    for (x, z, r) in ((-0.04, 0.02, 0.022), (0.04, 0.02, 0.022), (-0.08, 0.0, 0.015),
                      (0.08, 0.0, 0.015), (-0.02, 0.05, 0.013), (0.02, 0.05, 0.013)):
        e.sphere(r * s, p["eye"], pos=(x * s, 0, z * s), rings=2, segments=4)
    # 8 legs: headings from front to back
    angles = (55, 22, -12, -45)
    for side, sx in (("l", -1), ("r", 1)):
        for i, a in enumerate(angles):
            heading = a if sx > 0 else 180 - a
            y0 = (0.18 - i * 0.075) * s
            rig.joint(f"leg_{side}{i}", "body", (sx * 0.14 * s, y0 + 0.08 * s, 0.0), (heading, 0, 0))
            femur = 0.42 * s * (1.0 if i in (0, 3) else 0.92)
            knee = (femur * math.cos(math.radians(42)), 0, femur * math.sin(math.radians(42)))
            m = rig.mesh(f"leg_{side}{i}")
            m.tube((0, 0, 0), knee, 0.045 * s, 0.038 * s, p["body"], segments=5)
            for k in range(2):
                f = 0.35 + k * 0.3
                m.cone((knee[0] * f, 0, knee[2] * f), (knee[0] * f, 0, knee[2] * f + 0.07 * s),
                       0.012 * s, p["hair"], segments=3)
            rig.joint(f"knee_{side}{i}", f"leg_{side}{i}", knee)
            tib = 0.88 * s * (1.0 if i in (0, 3) else 0.9)
            foot_drop = 0.42 * s + knee[2]
            reach = math.sqrt(max(tib ** 2 - foot_drop ** 2, 0.01))
            m2 = rig.mesh(f"knee_{side}{i}")
            mid = (reach * 0.45, 0, -foot_drop * 0.35)
            m2.tube((0, 0, 0), mid, 0.038 * s, 0.03 * s, p["body_dark"], segments=5)
            m2.tube(mid, (reach, 0, -foot_drop), 0.03 * s, 0.012 * s, p["body"], segments=5)
    return rig


@register("spider_giant", "Giant Spider", "spider", "medium", "spider",
          MonsterStats(26, 36, "melee (stab) + poison", 5, 1.8, "slash / fire",
                       aggressive=True, notes="Poison 4. Webs slow the player for 3 ticks."),
          GIANT, 0.75)
def build_spider_giant():
    rig = _spider("spider_giant", GIANT, s=1.0).bake()
    rig["eyes"].set_light_off()
    return rig


@register("spider_broodmother", "Spider Broodmother", "spider", "large", "spider",
          MonsterStats(62, 140, "melee (stab) + poison", 14, 2.4, "slash / fire",
                       aggressive=True, notes="Spawns 2 hatchlings (lvl 8) at 50% HP. Poison 8."),
          BROOD, 1.4)
def build_spider_broodmother():
    rig = _spider("spider_broodmother", BROOD, s=1.7, brood=True).bake()
    rig["eyes"].set_light_off()
    return rig
