"""Void monsters: void spawn (small floating eye-horror with tentacles) and
void brute (2.4 m knuckle-walking hulk). Glowing parts live on their own
joints and are drawn unlit (set_light_off) so they read as emissive."""
import math

from ..mesh_builder import Rig
from ..registry import MonsterStats, register
from .parts import seg

SPAWN = {"shell": "#3a3150", "shell_dark": "#241f33", "flesh": "#4d4166",
         "glow": "#b56ad9", "glow_core": "#e0b8f0", "pupil": "#1a0f22"}
BRUTE = {"shell": "#383049", "shell_dark": "#211c2d", "hide": "#4a4060",
         "plate": "#4f4568", "glow": "#b56ad9", "claw": "#9d93b3"}


def _void_spawn():
    p = SPAWN
    rig = Rig("void_spawn")
    rig.joint("body", "root", (0, 0, 1.20))
    b = rig.mesh("body")
    b.sphere(0.30, p["flesh"], scale=(1.0, 0.95, 0.9), rings=3, segments=6)
    # angular shell plates, each tilted a different way -> jagged crystal silhouette
    for i in range(6):
        a = i * 60 + 30
        x, y = math.cos(math.radians(a)) * 0.20, math.sin(math.radians(a)) * 0.20 - 0.04
        b.box((0.20, 0.20, 0.14), p["shell"] if i % 2 else p["shell_dark"],
              pos=(x, y, 0.14), hpr=(a, 25, 15), taper=(0.5, 0.4))
    for k, (x, y) in enumerate(((0, -0.05), (0.12, -0.12), (-0.13, -0.10))):
        b.cone((x, y, 0.22), (x * 1.6, y * 1.6 - 0.05, 0.50 - k * 0.07), 0.06, p["shell_dark"],
               segments=4)                                                  # dorsal crystal spikes
    b.box((0.30, 0.10, 0.10), p["shell_dark"], pos=(0, 0.22, 0.12), hpr=(0, -30, 0),
          taper=(0.7, 1))                                                   # brow plate
    # mouth: ring of teeth under the eye
    for i in range(5):
        x = -0.10 + i * 0.05
        b.cone((x, 0.24, -0.10), (x * 0.8, 0.27, -0.03), 0.02, p["glow_core"], segments=3)
    rig.joint("eye", "body", (0, 0.24, 0.02))
    e = rig.mesh("eye")
    e.sphere(0.12, p["glow"], scale=(1.0, 0.55, 0.85), rings=3, segments=7)
    e.sphere(0.05, p["glow_core"], pos=(0, 0.05, 0), scale=(1, 0.6, 1), rings=2, segments=5)
    e.box((0.025, 0.02, 0.09), p["pupil"], pos=(0, 0.085, 0))
    # 4 dangling two-part tentacles
    for i, a in enumerate((45, 135, 225, 315)):
        x, y = math.cos(math.radians(a)) * 0.14, math.sin(math.radians(a)) * 0.14
        m = seg(rig, f"tentacle_{i}", "body", (x, y, -0.18), (x * 0.4, y * 0.4, -0.24),
                0.065, 0.045, p["flesh"], hpr=(0, 0, 0), segments=5)
        m2 = seg(rig, f"tentacle_{i}_tip", f"tentacle_{i}", (x * 0.4, y * 0.4, -0.24),
                 (x * 1.4, y * 1.4, -0.12), 0.045, 0.0, p["shell_dark"], segments=5)  # curls outward
        m2.sphere(0.03, p["glow"], pos=(x * 1.4, y * 1.4, -0.12), rings=2, segments=4)
    # orbiting shards (animate by spinning the 'shards' joint)
    rig.joint("shards", "body", (0, 0, 0))
    for i in range(3):
        a = math.radians(i * 120 + 20)
        rig.mesh("shards").cone((math.cos(a) * 0.48, math.sin(a) * 0.48, -0.08 + i * 0.1),
                                (math.cos(a) * 0.50, math.sin(a) * 0.50, 0.12 + i * 0.1),
                                0.05, p["glow"], segments=4)
        rig.mesh("shards").cone((math.cos(a) * 0.48, math.sin(a) * 0.48, -0.08 + i * 0.1),
                                (math.cos(a) * 0.47, math.sin(a) * 0.47, -0.22 + i * 0.1),
                                0.05, p["glow"], segments=4)
    rig.bake()
    for j in ("eye", "shards"):
        rig[j].set_light_off()
    return rig


def _void_brute():
    p = BRUTE
    rig = Rig("void_brute")
    rig.joint("hips", "root", (0, 0, 0.92))
    rig.mesh("hips").box((0.62, 0.40, 0.32), p["hide"], taper=(1.1, 1.0))
    for side, sx in (("l", -1), ("r", 1)):
        m = seg(rig, f"{side}_leg", "hips", (sx * 0.26, 0, -0.08), (0, 0.08, -0.42), 0.17, 0.13,
                p["hide"], hpr=(0, 10, sx * -6), segments=6)
        m = seg(rig, f"{side}_shin", f"{side}_leg", (0, 0.08, -0.42), (0, -0.05, -0.38), 0.13, 0.12,
                p["shell"], hpr=(0, -18, sx * 6), segments=6)
        m.box((0.26, 0.34, 0.12), p["shell_dark"], pos=(0, 0.04, -0.42), taper=(0.9, 0.7))
        m.box((0.20, 0.08, 0.22), p["plate"], pos=(0, 0.1, -0.15), hpr=(0, 10, 0))   # shin plate
    # torso pitched well forward, massive chest & shoulders
    rig.joint("torso", "hips", (0, 0, 0.10), (0, -38, 0))
    t = rig.mesh("torso")
    t.box((0.70, 0.50, 0.55), p["hide"], pos=(0, 0, 0.30), taper=(1.35, 1.25))
    t.box((1.10, 0.62, 0.30), p["shell"], pos=(0, -0.02, 0.70), taper=(0.75, 0.8))   # shoulder yoke
    for sx in (-1, 1):
        t.sphere(0.26, p["plate"], pos=(sx * 0.52, 0, 0.70), scale=(1, 1, 0.85), rings=3, segments=6)
    for i in range(3):
        t.box((0.40 - i * 0.06, 0.08, 0.12), p["shell_dark"], pos=(0, 0.26, 0.10 + i * 0.16),
              hpr=(0, 0, 0))                                               # belly plates
    rig.joint("crystals", "torso", (0, -0.25, 0.62))
    for k, (x, z, hgt) in enumerate(((-0.25, 0.0, 0.40), (0.0, 0.05, 0.55), (0.24, 0.0, 0.42),
                                     (-0.12, -0.25, 0.30), (0.14, -0.25, 0.32))):
        rig.mesh("crystals").cone((x, 0, z), (x * 1.3, -0.25, z + hgt), 0.09, p["glow"], segments=4)
    rig.joint("cracks", "torso", (0, 0.305, 0.36))
    rig.mesh("cracks").box((0.04, 0.01, 0.30), p["glow"], hpr=(0, 0, 20))
    rig.mesh("cracks").box((0.03, 0.01, 0.16), p["glow"], pos=(0.07, 0, -0.12), hpr=(0, 0, -35))
    # small head sunk between the shoulders
    rig.joint("head", "torso", (0, 0.36, 0.66), (0, 38, 0))
    h = rig.mesh("head")
    h.box((0.34, 0.34, 0.28), p["shell"], pos=(0, 0.10, 0.0), taper=(0.8, 0.8))
    h.box((0.40, 0.12, 0.10), p["shell_dark"], pos=(0, 0.25, 0.10), hpr=(0, -15, 0))   # brow
    h.box((0.28, 0.18, 0.12), p["shell_dark"], pos=(0, 0.22, -0.14), taper=(1.1, 1))   # jaw
    for sx in (-1, 1):
        h.cone((sx * 0.14, 0.26, -0.12), (sx * 0.16, 0.30, 0.02), 0.03, p["claw"], segments=3)  # tusks
        h.cone((sx * 0.15, 0.0, 0.10), (sx * 0.35, -0.18, 0.32), 0.06, p["shell_dark"], segments=4)  # horns
    rig.joint("eyes", "head", (0, 0.265, 0.03))
    for sx in (-1, 1):
        rig.mesh("eyes").box((0.07, 0.02, 0.035), p["glow"], pos=(sx * 0.08, 0, 0))
    # huge arms reaching the ground (knuckle walk)
    for side, sx in (("l", -1), ("r", 1)):
        m = seg(rig, f"{side}_arm", "torso", (sx * 0.62, 0.02, 0.62), (0, 0, -0.62), 0.17, 0.14,
                p["hide"], hpr=(0, 70, sx * -12), segments=6)
        m = seg(rig, f"{side}_forearm", f"{side}_arm", (0, 0, -0.62), (0, 0, -0.60), 0.16, 0.20,
                p["shell"], hpr=(0, -20, 0), segments=6)
        m.box((0.30, 0.30, 0.28), p["shell_dark"], pos=(0, 0.02, -0.70), taper=(1.0, 0.9))  # fist
        for f in range(3):
            m.cone((sx * 0.0 + (f - 1) * 0.09, 0.14, -0.78), ((f - 1) * 0.10, 0.24, -0.86),
                   0.035, p["claw"], segments=4)
        m.box((0.10, 0.34, 0.40), p["plate"], pos=(sx * 0.14, 0, -0.32), taper=(0.8, 0.8))  # forearm plate
        m.cone((sx * 0.16, -0.05, -0.20), (sx * 0.34, -0.10, -0.10), 0.05, p["glow"], segments=4)
    rig.bake()
    for j in ("crystals", "cracks", "eyes"):
        rig[j].set_light_off()
    return rig


@register("void_spawn", "Void Spawn", "void", "small", "floater",
          MonsterStats(38, 30, "magic (void pulse)", 6, 2.4, "slash / light (holy) spells",
                       aggressive=True, notes="Explodes on death for 1-5 to adjacent players."),
          SPAWN, 1.1)
def build_void_spawn():
    return _void_spawn()


@register("void_brute", "Void Brute", "void", "large", "biped",
          MonsterStats(98, 150, "melee (crush)", 18, 3.0, "stab / light (holy) spells",
                       aggressive=True, notes="Ground slam hits all adjacent tiles every 5th attack."),
          BRUTE, 2.3)
def build_void_brute():
    return _void_brute()
