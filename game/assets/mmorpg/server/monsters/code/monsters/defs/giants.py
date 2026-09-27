"""Giants: Hill Giant (~4 m, crude club, loincloth, hunched) and Ice Giant
(~4.3 m, frost-blue skin, ice shoulder spikes, icicle beard, ice-headed club).
Shared rig `_giant()`; biped joint names so any biped/giant profile works."""
from ..mesh_builder import Rig
from ..registry import MonsterStats, register
from .parts import aim, seg

HILL = {"skin": "#a47b5a", "skin_dark": "#7d5b43", "hair": "#4a3526", "cloth": "#6b5a3a",
        "cloth_dark": "#4b3f28", "rope": "#8c7751", "wood": "#5e4630", "wood_dark": "#44331f",
        "eye": "#2a2018", "tooth": "#d2c6a2", "iron": "#6d6c68"}
ICE = {"skin": "#8ea5b4", "skin_dark": "#667e8d", "hair": "#d4e4ea", "cloth": "#c8bea8",
       "cloth_dark": "#8f8574", "rope": "#6b5f4f", "wood": "#4f4438", "wood_dark": "#3a3129",
       "eye": "#a8e6f2", "tooth": "#e4ecee", "ice": "#bcd9e4", "ice_dark": "#8fb6c6"}


def _giant(name, p, ice=False):
    s = 1.08 if ice else 1.0
    rig = Rig(name)
    rig.joint("hips", "root", (0, 0, 1.72 * s))
    rig.mesh("hips").box((0.95 * s, 0.62 * s, 0.40 * s), p["skin_dark"], taper=(1.1, 1.0))
    # legs: thick, slightly bowed, bare feet with toes
    for side, sx in (("l", -1), ("r", 1)):
        m = seg(rig, f"{side}_leg", "hips", (sx * 0.30 * s, 0, -0.10 * s), (0, 0.04 * s, -0.80 * s),
                0.24 * s, 0.18 * s, p["skin"], hpr=(0, 8, sx * -5), segments=7)
        m.sphere(0.19 * s, p["skin_dark"], pos=(0, 0.04 * s, -0.80 * s), rings=3, segments=6)
        m = seg(rig, f"{side}_shin", f"{side}_leg", (0, 0.04 * s, -0.80 * s), (0, -0.02 * s, -0.76 * s),
                0.18 * s, 0.14 * s, p["skin"], hpr=(0, -14, sx * 5), segments=7)
        m.box((0.30 * s, 0.50 * s, 0.14 * s), p["skin_dark"], pos=(0, 0.10 * s, -0.80 * s),
              hpr=(0, 6, 0), taper=(0.9, 0.75))
        for t in range(4):
            m.box((0.06 * s, 0.08 * s, 0.07 * s), p["skin"],
                  pos=((t - 1.5) * 0.07 * s, 0.35 * s, -0.83 * s))
        if ice:   # fur boot wraps
            m.tube((0, 0, -0.52 * s), (0, 0, -0.74 * s), 0.19 * s, 0.20 * s, p["cloth"], segments=7)
    # torso: pot belly + broad hunched chest, leaning forward
    rig.joint("torso", "hips", (0, 0, 0.12 * s), (0, -22, 0))
    t = rig.mesh("torso")
    t.sphere(0.62 * s, p["skin"], pos=(0, 0.14 * s, 0.40 * s), scale=(1.0, 0.95, 0.95), rings=4, segments=8)
    t.box((1.25 * s, 0.82 * s, 0.80 * s), p["skin_dark"] if not ice else p["skin"],
          pos=(0, -0.02 * s, 1.02 * s), taper=(1.18, 1.05))
    t.box((0.60 * s, 0.30 * s, 0.30 * s), p["skin_dark"], pos=(0, -0.30 * s, 1.40 * s),
          hpr=(0, 20, 0))                                                     # hunched upper back
    # loincloth + belt + rope strap
    t.box((1.10 * s, 0.78 * s, 0.30 * s), p["cloth"], pos=(0, 0.06 * s, -0.02 * s), taper=(1.0, 1.0))
    t.box((0.46 * s, 0.06 * s, 0.62 * s), p["cloth_dark"], pos=(0, 0.46 * s, -0.24 * s),
          hpr=(0, 12, 0), taper=(0.75, 1))                                    # front flap
    t.box((1.14 * s, 0.82 * s, 0.09 * s), p["rope"], pos=(0, 0.06 * s, 0.14 * s))
    t.box((1.35 * s, 0.07 * s, 0.10 * s), p["rope"], pos=(0.05 * s, 0.43 * s, 0.95 * s),
          hpr=(0, 0, 38))                                                     # chest strap
    if not ice:
        t.sphere(0.12 * s, p["cloth_dark"], pos=(0.52 * s, 0.10 * s, 0.10 * s), rings=3,
                 segments=5)                                                  # belt pouch
    else:
        # fur pelt over the shoulders
        t.box((1.40 * s, 0.95 * s, 0.22 * s), p["cloth"], pos=(0, -0.04 * s, 1.40 * s), taper=(0.8, 0.85))
    # head: small for the body, heavy brow, big nose, underbite
    t.tube((0, 0.22 * s, 1.30 * s), (0, 0.50 * s, 1.60 * s), 0.24 * s, 0.20 * s, p["skin"], segments=6)  # thick neck
    rig.joint("head", "torso", (0, 0.50 * s, 1.58 * s), (0, 32, 0))
    h = rig.mesh("head")
    h.sphere(0.33 * s, p["skin"], pos=(0, 0.04 * s, 0.24 * s), scale=(1.05, 1.0, 1.0), rings=4, segments=7)
    h.box((0.54 * s, 0.14 * s, 0.12 * s), p["skin_dark"], pos=(0, 0.26 * s, 0.34 * s), hpr=(0, -10, 0))
    h.box((0.14 * s, 0.14 * s, 0.18 * s), p["skin_dark"], pos=(0, 0.34 * s, 0.22 * s), taper=(1.3, 1.2))
    for sx in (-1, 1):
        h.box((0.07 * s, 0.03 * s, 0.05 * s), p["eye"], pos=(sx * 0.11 * s, 0.305 * s, 0.27 * s))
        h.sphere(0.08 * s, p["skin_dark"], pos=(sx * 0.30 * s, 0.0, 0.24 * s), scale=(0.5, 1, 1.2),
                 rings=2, segments=5)                                         # ears
    rig.joint("jaw", "head", (0, 0.10 * s, 0.08 * s), (0, -6, 0))
    j = rig.mesh("jaw")
    j.box((0.44 * s, 0.30 * s, 0.16 * s), p["skin"], pos=(0, 0.12 * s, -0.02 * s), taper=(1.05, 0.95))
    for sx in (-1, 1):
        j.cone((sx * 0.13 * s, 0.25 * s, 0.05 * s), (sx * 0.14 * s, 0.26 * s, 0.15 * s), 0.035 * s,
               p["tooth"], segments=4)                                        # tusks
    if not ice:
        for k, (x, y) in enumerate(((0, -0.1), (-0.15, -0.05), (0.15, -0.05), (0, 0.12), (-0.1, -0.22),
                                    (0.1, -0.22))):
            h.box((0.20 * s, 0.20 * s, 0.10 * s), p["hair"], pos=(x * s, y * s, 0.50 * s - abs(y) * 0.3 * s),
                  hpr=(k * 25, 10, 0), taper=(0.5, 0.5))                      # shaggy mop
    else:
        # icicle beard hanging from the jaw + frosty brow
        for k in range(7):
            x = (k - 3) * 0.065
            ln = 0.30 - abs(k - 3) * 0.05
            j.cone((x * s, 0.16 * s, -0.08 * s), (x * 1.2 * s, 0.22 * s, (-0.08 - ln) * s), 0.05 * s,
                   p["hair"] if k % 2 else p["ice"], segments=4)
        h.box((0.56 * s, 0.10 * s, 0.05 * s), p["hair"], pos=(0, 0.28 * s, 0.40 * s), hpr=(0, -10, 0))
        for k in range(5):
            x = (k - 2) * 0.1
            h.cone((x * s, -0.04 * s, 0.48 * s), (x * 1.3 * s, -0.20 * s, 0.70 * s - abs(k - 2) * 0.05 * s),
                   0.07 * s, p["hair"], segments=4)                           # swept frost hair
    rig.joint("eyes", "head", (0, 0.31 * s, 0.27 * s))
    if ice:
        for sx in (-1, 1):
            rig.mesh("eyes").box((0.075 * s, 0.02 * s, 0.05 * s), p["eye"], pos=(sx * 0.11 * s, 0, 0))
    # long heavy arms
    for side, sx in (("l", -1), ("r", 1)):
        m = seg(rig, f"{side}_arm", "torso", (sx * 0.78 * s, 0.0, 1.22 * s), (0, 0, -0.92 * s),
                0.22 * s, 0.17 * s, p["skin"], hpr=(0, 18, sx * -10), segments=7)
        m.sphere(0.27 * s, p["skin_dark"], rings=3, segments=6)
        m = seg(rig, f"{side}_forearm", f"{side}_arm", (0, 0, -0.92 * s), (0, 0, -0.86 * s),
                0.18 * s, 0.17 * s, p["skin"], hpr=(0, 22, 0), segments=7)
        m.box((0.32 * s, 0.26 * s, 0.34 * s), p["skin_dark"], pos=(0, 0.02 * s, -0.98 * s), taper=(0.9, 0.9))
        if not ice:
            m.tube((0, 0, -0.52 * s), (0, 0, -0.70 * s), 0.19 * s, 0.19 * s, p["cloth_dark"], segments=7)  # wrist wrap
        rig.joint(f"{side}_hand", f"{side}_forearm", (0, 0.02 * s, -0.98 * s))
    if ice:
        # ice crystal clusters on both shoulders
        rig.joint("ice_spikes", "torso", (0, 0, 1.40 * s))
        sp = rig.mesh("ice_spikes")
        for sx in (-1, 1):
            for k, (dx, dy, hgt, lean) in enumerate(((0.0, 0.0, 0.62, 0.10), (0.16, 0.12, 0.45, 0.25),
                                                      (-0.12, -0.14, 0.40, -0.1), (0.2, -0.12, 0.34, 0.3),
                                                      (-0.05, 0.18, 0.32, 0.0))):
                bx, by = sx * (0.62 + dx) * s, dy * s
                sp.cone((bx, by, 0), (bx + sx * lean * s, by - 0.08 * s, hgt * s), 0.10 * s,
                        p["ice"] if k % 2 == 0 else p["ice_dark"], segments=4)
    # weapon: crude club dragged forward-down
    c = rig.mesh("r_hand")
    c.tube((0, 0, -0.15 * s), (0, 0, 1.15 * s), 0.08 * s, 0.14 * s, p["wood"], segments=6)
    if not ice:
        c.sphere(0.24 * s, p["wood_dark"], pos=(0, 0, 1.30 * s), scale=(1, 1, 1.25), rings=3, segments=6)
        for a in ((0.2, 0, 1.3), (-0.18, 0.08, 1.4), (0, -0.2, 1.22), (0.05, 0.2, 1.45)):
            c.cone((a[0] * 0.6 * s, a[1] * 0.6 * s, a[2] * s), (a[0] * 1.3 * s, a[1] * 1.3 * s, a[2] * s + 0.05 * s),
                   0.04 * s, p["iron"], segments=4)                           # driven-in nails
        c.box((0.20 * s, 0.20 * s, 0.10 * s), p["rope"], pos=(0, 0, 0.0))    # grip binding
    else:
        rig.joint("ice_club", "r_hand", (0, 0, 1.25 * s))
        ic = rig.mesh("ice_club")
        ic.sphere(0.22 * s, p["ice_dark"], scale=(1, 1, 1.3), rings=3, segments=6)
        for a in ((1, 0, 0.2), (-1, 0.3, 0.1), (0, -1, 0.25), (0.3, 1, -0.1), (0, 0, 1)):
            ic.cone((a[0] * 0.1 * s, a[1] * 0.1 * s, a[2] * 0.1 * s),
                    (a[0] * 0.34 * s, a[1] * 0.34 * s, a[2] * 0.34 * s + 0.08 * s), 0.08 * s, p["ice"], segments=4)
    if not ice:   # hill giant: club raised out to the side
        rig["r_arm"].set_hpr(0, 25, -32)
        rig["r_forearm"].set_hpr(0, 50, 0)
        aim(rig, "r_hand", (0.70, 0.15, 0.75))
    else:         # ice giant: club held low and forward, ready to sweep
        rig["r_arm"].set_hpr(0, 12, -14)
        aim(rig, "r_hand", (0.50, 0.80, -0.45))
    rig["l_arm"].set_hpr(0, 28, 12)
    return rig


@register("giant_hill", "Hill Giant", "giant", "large", "giant",
          MonsterStats(36, 70, "melee (crush)", 9, 3.0, "stab / ranged (slow to close distance)",
                       aggressive=False, notes="Common mid-level grind monster; drops big bones."),
          HILL, 4.0)
def build_giant_hill():
    return _giant("giant_hill", HILL).bake()


@register("giant_ice", "Ice Giant", "giant", "large", "giant",
          MonsterStats(61, 105, "melee (crush) + frost", 13, 3.0, "fire spells / crush",
                       aggressive=True, notes="Hits can freeze the player for 2 ticks; immune to water spells."),
          ICE, 4.3)
def build_giant_ice():
    rig = _giant("giant_ice", ICE, ice=True).bake()
    for j in ("eyes", "ice_spikes", "ice_club"):
        rig[j].set_light_off()
    return rig
