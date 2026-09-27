"""Cave Gnasher - blind burrowing beast of the deep mines. 2.2 m long,
1.2 m at the shoulder hump. Front-heavy mole/badger/bear build, eyeless
skull with a massive underbite, huge digging claws."""
from ..mesh_builder import Rig
from ..registry import MonsterStats, register

P = {"hide": "#8a7a6c", "hide_dark": "#5f5249", "belly": "#a69482", "fur": "#4a3f38",
     "claw": "#d7ccb0", "gum": "#7a4640", "tooth": "#e0d6bc", "nose": "#6e4a44"}


@register("cave_gnasher", "Cave Gnasher", "cave", "large", "quadruped",
          MonsterStats(64, 95, "melee (crush/stab)", 13, 2.4, "slash / fire; stunned by light sources",
                       aggressive=True, notes="Burrows and re-emerges under the player (telegraphed by dust)."),
          P, 1.25)
def build_cave_gnasher():
    rig = Rig("cave_gnasher")
    rig.joint("body", "root", (0, 0, 0.78))
    b = rig.mesh("body")
    b.sphere(0.50, P["hide"], pos=(0, 0.22, 0.08), scale=(1.0, 1.0, 0.95), rings=4, segments=8)   # chest/hump
    b.sphere(0.40, P["hide_dark"], pos=(0, -0.42, -0.02), scale=(0.95, 1.15, 0.85), rings=4, segments=7)
    b.sphere(0.36, P["belly"], pos=(0, 0.18, -0.16), scale=(0.9, 1.2, 0.7), rings=3, segments=7)
    for i in range(7):                                       # bristle ridge along the spine
        y = 0.45 - i * 0.16
        z = 0.52 - abs(i - 1.5) * 0.05
        b.cone((0, y, z), (0, y - 0.12, z + 0.22 - abs(i - 1.5) * 0.02), 0.07, P["fur"], segments=3,
               squash=0.5)
    rig.joint("tail", "body", (0, -0.86, 0.0), (0, -30, 0))
    rig.mesh("tail").cone((0, 0, 0), (0, -0.32, -0.05), 0.09, P["hide_dark"], segments=5)
    # head: low, wide, eyeless
    rig.joint("head", "body", (0, 0.68, 0.02), (0, -12, 0))
    h = rig.mesh("head")
    h.box((0.46, 0.42, 0.32), P["hide"], pos=(0, 0.16, 0.04), taper=(0.8, 0.85))
    h.box((0.30, 0.26, 0.20), P["hide"], pos=(0, 0.44, 0.0), taper=(0.75, 0.8))
    h.sphere(0.08, P["nose"], pos=(0, 0.58, 0.02), scale=(1.3, 0.7, 0.8), rings=2, segments=6)
    h.box((0.48, 0.12, 0.10), P["hide_dark"], pos=(0, 0.20, 0.20), hpr=(0, -10, 0))   # heavy brow, no eyes
    for sx in (-1, 1):
        h.box((0.06, 0.06, 0.012), P["hide_dark"], pos=(sx * 0.10, 0.32, 0.16), hpr=(0, -10, sx * 20))  # scars
        h.cone((sx * 0.20, -0.02, 0.16), (sx * 0.28, -0.10, 0.26), 0.05, P["hide_dark"], segments=3)  # ears
        for t in range(3):                                  # upper teeth
            h.cone((sx * (0.06 + t * 0.04), 0.52 - t * 0.08, -0.09),
                   (sx * (0.06 + t * 0.04), 0.52 - t * 0.08, -0.15), 0.018, P["tooth"], segments=3)
    rig.joint("jaw", "head", (0, 0.05, -0.12), (0, -14, 0))
    j = rig.mesh("jaw")
    j.box((0.44, 0.58, 0.14), P["hide_dark"], pos=(0, 0.28, -0.04), taper=(1.0, 1.0))
    j.box((0.36, 0.48, 0.02), P["gum"], pos=(0, 0.28, 0.035))
    for sx in (-1, 1):
        j.cone((sx * 0.17, 0.52, 0.02), (sx * 0.18, 0.56, 0.20), 0.035, P["tooth"], segments=4)  # tusks
        for t in range(3):
            j.cone((sx * (0.08 + t * 0.03), 0.46 - t * 0.09, 0.03),
                   (sx * (0.08 + t * 0.03), 0.46 - t * 0.09, 0.09), 0.02, P["tooth"], segments=3)
    # legs: thick front with digging claws, shorter hind
    for side, sx in (("l", -1), ("r", 1)):
        rig.joint(f"{side}_front_leg", "body", (sx * 0.36, 0.38, -0.12), (0, 0, sx * -8))
        m = rig.mesh(f"{side}_front_leg")
        m.tube((0, 0, 0), (0, 0.06, -0.34), 0.17, 0.13, P["hide"], segments=6)
        rig.joint(f"{side}_front_shin", f"{side}_front_leg", (0, 0.06, -0.34), (0, 0, sx * 8))
        m = rig.mesh(f"{side}_front_shin")
        m.tube((0, 0, 0), (0, 0.04, -0.26), 0.13, 0.12, P["hide_dark"], segments=6)
        m.box((0.26, 0.24, 0.08), P["hide_dark"], pos=(0, 0.08, -0.28), taper=(0.9, 0.8))
        for c in (-1, 0, 1):
            m.tube((c * 0.08, 0.16, -0.26), (c * 0.10, 0.30, -0.25), 0.03, 0.022, P["claw"], segments=4)
            m.cone((c * 0.10, 0.30, -0.25), (c * 0.11, 0.38, -0.31), 0.022, P["claw"], segments=4)
        rig.joint(f"{side}_hind_leg", "body", (sx * 0.30, -0.50, -0.14))
        m = rig.mesh(f"{side}_hind_leg")
        m.sphere(0.18, P["hide_dark"], rings=3, segments=6)
        m.tube((0, 0, 0), (0, 0.10, -0.28), 0.15, 0.10, P["hide_dark"], segments=6)
        rig.joint(f"{side}_hind_shin", f"{side}_hind_leg", (0, 0.10, -0.28))
        m = rig.mesh(f"{side}_hind_shin")
        m.tube((0, 0, 0), (0, -0.06, -0.30), 0.10, 0.08, P["hide_dark"], segments=5)
        m.box((0.18, 0.22, 0.07), P["hide_dark"], pos=(0, 0.02, -0.33), taper=(0.9, 0.8))
        for c in (-1, 1):
            m.cone((c * 0.05, 0.12, -0.34), (c * 0.06, 0.20, -0.36), 0.02, P["claw"], segments=3)
    return rig.bake()
