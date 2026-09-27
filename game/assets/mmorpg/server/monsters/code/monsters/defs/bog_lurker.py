"""Bog Lurker - squat toad/troll ambusher of the fens. ~1.5 m hunched, very
wide. Frog-legged crouch, huge flat head with a wide jaw, bulging eyes on
top, weed hanging off its shoulders, long arms with webbed hands."""
import math

from ..mesh_builder import Rig
from ..registry import MonsterStats, register
from .parts import seg

P = {"skin": "#4f5c39", "skin_dark": "#38412a", "belly": "#8e8a5b", "wart": "#3f4a2c",
     "weed": "#667a36", "weed_dark": "#4b5a2a", "eye": "#cdb84a", "pupil": "#1c1a12",
     "mouth": "#5c3a30", "mud": "#4a3d2c", "tooth": "#cfc5a2"}


@register("bog_lurker", "Bog Lurker", "bog", "medium", "biped",
          MonsterStats(45, 60, "melee (crush) + tongue pull", 9, 2.4, "fire spells / slash",
                       aggressive=True,
                       notes="Hides submerged (only eyes visible) until the player is within 2 tiles."),
          P, 1.5)
def build_bog_lurker():
    rig = Rig("bog_lurker")
    rig.joint("hips", "root", (0, 0, 0.55))
    rig.mesh("hips").sphere(0.34, P["skin"], scale=(1.15, 1.0, 0.8), rings=3, segments=7)
    # frog-crouch legs: thighs splay sideways, knees high and out
    for side, sx in (("l", -1), ("r", 1)):
        m = seg(rig, f"{side}_leg", "hips", (sx * 0.28, 0.0, -0.05),
                (sx * 0.30, 0.22, 0.02), 0.16, 0.11, P["skin"], segments=6)
        m = seg(rig, f"{side}_shin", f"{side}_leg", (sx * 0.30, 0.22, 0.02),
                (sx * 0.06, 0.00, -0.50), 0.11, 0.08, P["mud"], segments=6)
        m.box((0.24, 0.34, 0.06), P["skin_dark"], pos=(sx * 0.08, 0.10, -0.52), taper=(1.3, 0.6))
        for t in (-1, 0, 1):
            m.cone((sx * 0.08 + t * 0.09, 0.24, -0.53), (sx * 0.08 + t * 0.14, 0.34, -0.54),
                   0.03, P["skin_dark"], segments=3)
    # pear-shaped torso leaning forward
    rig.joint("torso", "hips", (0, 0.05, 0.12), (0, -30, 0))
    t = rig.mesh("torso")
    t.sphere(0.42, P["skin"], pos=(0, 0, 0.28), scale=(1.15, 0.95, 1.0), rings=4, segments=8)
    t.sphere(0.34, P["belly"], pos=(0, 0.14, 0.18), scale=(1.1, 0.8, 1.0), rings=3, segments=7)
    for i in range(5):                                          # back fin ridge
        z = 0.12 + i * 0.12
        t.prism([(0, 0), (0.0, 0.18 - abs(i - 2) * 0.03), (-0.12, 0.0)], 0.03, P["skin_dark"],
                pos=(0, -0.36 + i * 0.03, z), hpr=(90, 0, 0))
    for (x, y, z) in ((0.25, -0.2, 0.45), (-0.3, -0.15, 0.3), (0.1, -0.33, 0.25), (-0.12, -0.3, 0.55),
                      (0.35, 0.0, 0.2)):
        t.sphere(0.05, P["wart"], pos=(x, y, z), rings=2, segments=5)
    # weed strands hanging from the shoulders
    rig.joint("weed", "torso", (0, 0, 0.55))
    for k in range(9):
        a = math.radians(-160 + k * 40)
        x, y = math.cos(a) * 0.38, math.sin(a) * 0.30 - 0.05
        rig.mesh("weed").tube((x, y, 0.0), (x * 1.12, y * 1.1, -0.35 - (k % 3) * 0.10), 0.05, 0.0,
                              P["weed"] if k % 2 else P["weed_dark"], segments=3, squash=0.4)
    # head: wide & flat, fused low on the torso front
    rig.joint("head", "torso", (0, 0.28, 0.52), (0, 30, 0))
    h = rig.mesh("head")
    h.box((0.62, 0.46, 0.22), P["skin"], pos=(0, 0.10, 0.06), taper=(0.85, 0.8))
    h.box((0.66, 0.10, 0.06), P["skin_dark"], pos=(0, 0.32, -0.02))              # upper lip ridge
    for sx in (-1, 1):
        h.sphere(0.10, P["skin"], pos=(sx * 0.20, 0.10, 0.20), rings=3, segments=6)  # eye bulges
        h.sphere(0.03, P["wart"], pos=(sx * 0.12, 0.34, 0.10), rings=2, segments=4)  # nostrils
        h.cone((sx * 0.30, 0.0, 0.10), (sx * 0.42, -0.15, 0.22), 0.05, P["skin_dark"], segments=3)  # gill spikes
    h.cone((0, 0.0, 0.18), (0, -0.10, 0.30), 0.05, P["skin_dark"], segments=3)
    rig.joint("eyes", "head", (0, 0.18, 0.22))
    for sx in (-1, 1):
        rig.mesh("eyes").sphere(0.06, P["eye"], pos=(sx * 0.20, 0, 0.02), rings=2, segments=6)
        rig.mesh("eyes").box((0.08, 0.02, 0.02), P["pupil"], pos=(sx * 0.20, 0.055, 0.03))
    rig.joint("jaw", "head", (0, -0.05, -0.05), (0, -8, 0))
    j = rig.mesh("jaw")
    j.box((0.60, 0.44, 0.12), P["belly"], pos=(0, 0.18, -0.06), taper=(1.0, 0.95))
    j.box((0.52, 0.36, 0.02), P["mouth"], pos=(0, 0.18, 0.005))
    for k in range(6):
        x = -0.24 + k * 0.096
        j.cone((x, 0.37, 0.0), (x, 0.37, 0.06), 0.018, P["tooth"], segments=3)
    # long arms, webbed hands resting near the ground
    for side, sx in (("l", -1), ("r", 1)):
        m = seg(rig, f"{side}_arm", "torso", (sx * 0.44, 0.05, 0.42), (0, 0, -0.42), 0.11, 0.09,
                P["skin"], hpr=(0, 55, sx * -18), segments=6)
        m = seg(rig, f"{side}_forearm", f"{side}_arm", (0, 0, -0.42), (0, 0, -0.40), 0.09, 0.08,
                P["skin_dark"], hpr=(0, -35, 0), segments=6)
        m.box((0.18, 0.14, 0.06), P["skin_dark"], pos=(0, 0.02, -0.43))
        base = (0, 0.02, -0.45)
        tips = [(-0.14, 0.18, -0.52), (0, 0.22, -0.54), (0.14, 0.18, -0.52)]
        for tp in tips:
            m.tube(base, tp, 0.03, 0.015, P["skin_dark"], segments=3)
        m.polygon([base, tips[0], tips[1]], P["belly"])
        m.polygon([base, tips[1], tips[2]], P["belly"])
        rig.mesh(f"{side}_arm").tube((0, 0, -0.1), (0, -0.05, -0.45), 0.10, 0.0, P["weed_dark"],
                                     segments=3, squash=0.4)
    rig.bake()
    rig["eyes"].set_light_off()
    return rig
