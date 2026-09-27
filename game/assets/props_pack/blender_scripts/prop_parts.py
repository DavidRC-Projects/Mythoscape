"""prop_parts.py - shared palette + reusable chunky sub-parts for the Mythoscape props pack.

Every group script (props_town.py, props_castle.py, props_pets.py, props_dungeons.py) does

    from prop_parts import new_kit, barrel, chest, candle, cage, ...
    k = new_kit("furnace", seed=3, emissive=("fire", "ember"))
    ... geometry ...
    k.collider("body", centre, size); k.interact(centre, size)
    k.finish()

All sizes in metres (1 unit = 1 m), front faces -Y, ground z = 0, origin = tile centre.
Mythoscape scale: 1 tile = 40 px = ~1.49 m, 1.8 m player ~ 48 px (26.9 px/m).
"""
import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from osrs_kit import Kit  # noqa: E402

# Muted OSRS palette (sRGB hex). Emissive keys are listed in EMISSIVE with Blender strength:
# strength >= 2 -> full-bright in Panda (fire/candles/void), < 2 -> soft glow (water).
P = {
    "wood": "#7a5434", "wood_d": "#553a24", "plank": "#94703f", "wood_red": "#6a3a28",
    "iron": "#4f535a", "steel": "#8a9098", "gold": "#c8a03c", "coin": "#d9b54a",
    "stone": "#8c8a80", "stone_d": "#65635c", "stone_l": "#a8a598", "brick": "#8a5440",
    "marble": "#bdb7a8", "soot": "#2e2926", "black": "#1b1917",
    "red": "#8f2a2c", "red_d": "#5e1c1f", "blue": "#3e5a86", "green": "#4f6b3a",
    "purple": "#5a3a72", "cream": "#d8ccaa", "straw": "#b89a4e", "rope": "#9c8458",
    "leather": "#6e4a30", "bone": "#d8cfb4", "cloth": "#b9ab8a", "slate": "#4a4f58",
    "water_still": "#3f6f8c", "moss": "#5d6e3a", "dirt": "#6a5238",
    "gem_r": "#b8323a", "gem_b": "#3b6cc0", "gem_g": "#3f9a52",
    "fur_ginger": "#c07a3a", "fur_white": "#e2e0da", "fur_grey": "#8e8f94", "fur_dark": "#3a3533",
    "scale_g": "#4f8a3a", "scale_gl": "#9cc05a", "eye": "#141210", "nose": "#2a2220",
    "pink": "#c98a86", "web": "#d9d6cc", "chitin": "#2f2a30", "egg": "#cfc6a2",
    "void_stone": "#34303f", "void_dark": "#1c1924", "goblin_cloth": "#6b6a3a", "hide": "#8a6a48",
    "wax": "#e8dcb8", "straw_d": "#8f7438",
    # emissive
    "fire": "#ff9a2a", "fire_core": "#ffe08a", "ember": "#d8502a", "candle": "#ffd27a",
    "water": "#4a88b8", "water_hi": "#8cc4e4", "void": "#8e3fd6", "void_core": "#d09cff",
    "egg_glow": "#e0c060",
}
EMISSIVE = {"fire": 6.0, "fire_core": 8.0, "ember": 3.0, "candle": 6.0, "water": 0.45,
            "water_hi": 0.6, "void": 5.0, "void_core": 7.0, "egg_glow": 2.5}
# Where each OLD 2D drawer puts the object's ground contact (its contact shadow), in px BELOW the
# tile centre (cx, cy) at TILE 40 - read from procedural_sprites_finished.py. Blit the new sprite so
# its origin_px lands on (cx, cy + OLD_BASE_PX[key] * TILE / 40) to keep the object where it stood.
OLD_BASE_PX = {"furnace": 30, "anvil": 21, "bank_booth": 25, "vault_chest": 9, "barrel": 10, "shop_counter": 13, "hearth": 17, "workbench": 13, "weapon_rack": 13, "quench_bucket": 8, "pet_bed": 8, "cage_cat": 12, "cage_husky": 12, "cage_skeleton": 12, "cage_dragon": 12, "castle_chair": 10, "banquet_table": 12, "brazier": 9, "banner_stand": 11, "fountain": 15, "market_stall": 13, "throne": 16, "wishing_well": 69}
FLOOR = {"indoor": "#7a6448", "outdoor": "#6f7a4a", "stone": "#6b675e", "cave": "#4e463c"}


def new_kit(key, seed=1, title=None, emissive=(), floor="indoor", extra=None):
    pal = dict(P)
    pal.update(extra or {})
    em = {e: EMISSIVE[e] for e in emissive}
    return Kit(key, pal, seed=seed, title=title, emissive=em, ground=FLOOR[floor])


def only_keys():
    """`blender -b -P props_town.py -- --only furnace,anvil` builds a subset."""
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    if "--only" in argv:
        return set(argv[argv.index("--only") + 1].split(","))
    return None


def run(builders):
    sel = only_keys()
    for key, fn in builders.items():
        if sel and key not in sel:
            continue
        fn()


# ------------------------------------------------------------------ small parts
def barrel(k, x, y, z=0.0, r=0.33, h=0.85, wood="wood", lid=True):
    k.cyl((x, y, z), r * 0.88, r, h * 0.5, wood, segs=8)
    k.cyl((x, y, z + h * 0.5), r, r * 0.88, h * 0.5, wood, segs=8)
    for zz in (0.12, 0.5, 0.86):
        rr = r * (0.93 if zz != 0.5 else 1.02)
        k.cyl((x, y, z + h * zz - 0.03), rr + 0.02, rr + 0.02, 0.06, "iron", segs=8, caps=False)
    if lid:
        k.cyl((x, y, z + h - 0.01), r * 0.84, r * 0.84, 0.03, "plank", segs=8)


def crate(k, x, y, z=0.0, s=0.6, rot=0):
    k.box((x, y, z + s / 2), (s, s, s), "plank", rot=(0, 0, rot))
    t = 0.07
    ca, sa = math.cos(math.radians(rot)), math.sin(math.radians(rot))
    # corner battens (chunky frame so it does not read as a plain cube)
    for dx in (-1, 1):
        for dy in (-1, 1):
            px, py = dx * (s / 2 - t / 2 + 0.01), dy * (s / 2 - t / 2 + 0.01)
            k.box((x + px * ca - py * sa, y + px * sa + py * ca, z + s / 2), (t, t, s + 0.01), "wood_d",
                  rot=(0, 0, rot))
    fy = -s / 2 - 0.012
    k.box((x - fy * sa, y + fy * ca, z + s / 2), (s * 1.15, 0.03, t), "wood_d", rot=(0, 45, rot))


def chest(k, x, y, z=0.0, w=1.0, d=0.62, h=0.5, wood="wood", band="iron", lock="gold", rot=0, lid_h=0.26):
    """Chunky chest with a faceted domed lid, metal bands and lock (faces -Y)."""
    r = math.radians(rot)
    ca, sa = math.cos(r), math.sin(r)

    def P_(px, py, pz):
        return (x + px * ca - py * sa, y + px * sa + py * ca, z + pz)
    k.box(P_(0, 0, h / 2), (w, d, h), wood, rot=(0, 0, rot))
    k.box(P_(0, 0, 0.03), (w + 0.06, d + 0.06, 0.06), "wood_d", rot=(0, 0, rot))
    # domed lid = half hexagon prism along X
    segs = 4
    v, f = [], []
    for side in (-1, 1):
        for i in range(segs + 1):
            a = math.pi * i / segs
            v.append(P_(side * w / 2, -math.cos(a) * d / 2, h + math.sin(a) * lid_h))
    n = segs + 1
    for i in range(segs):
        f.append((i, i + 1, n + i + 1, n + i))
    f.append(tuple(range(n - 1, -1, -1)))
    f.append(tuple(range(n, 2 * n)))
    k.add(v, f, wood)
    for bx in (-w * 0.32, w * 0.32):   # metal bands over lid + body
        k.box(P_(bx, -d / 2 - 0.012, h / 2), (0.08, 0.03, h), band, rot=(0, 0, rot))
        bv = []
        for i in range(segs + 1):
            a = math.pi * i / segs
            for sx in (-0.045, 0.045):
                bv.append(P_(bx + sx, -math.cos(a) * (d / 2 + 0.02), h + math.sin(a) * (lid_h + 0.02)))
        bf = [(2 * i, 2 * i + 1, 2 * i + 3, 2 * i + 2) for i in range(segs)]
        k.add(bv, bf, band)
    k.box(P_(0, -d / 2 - 0.03, h - 0.02), (0.14, 0.05, 0.18), lock, jitter=False, rot=(0, 0, rot))
    k.box(P_(0, -d / 2 - 0.058, h - 0.04), (0.04, 0.01, 0.06), "black", jitter=False, rot=(0, 0, rot))


def candle(k, x, y, z, h=0.18, r=0.035):
    k.cyl((x, y, z), r, r * 0.9, h, "wax", segs=5)
    k.cone((x, y, z + h + 0.005), r * 1.1, 0.09, "candle", segs=4)


def flame(k, x, y, z, s=1.0, core=True):
    """Chunky low-poly flame: 3 tilted cones + core."""
    for i, (dx, dy, hh, tilt) in enumerate(((0, 0, 0.55, 0), (0.1, 0.02, 0.38, 14), (-0.1, -0.03, 0.4, -14))):
        k.cone((x + dx * s, y + dy * s, z), 0.16 * s, hh * s, "fire", segs=5, rot=(0, tilt, i * 25))
    if core:
        k.cone((x, y - 0.04 * s, z), 0.09 * s, 0.3 * s, "fire_core", segs=4)


def logs(k, x, y, z, s=1.0, n=3):
    for i in range(n):
        a = 360 * i / n + 20
        k.cyl((x, y, z + 0.05 * s), 0.07 * s, 0.06 * s, 0.55 * s, "wood_d", segs=5,
              rot=(0, 78, a))


def bars_box(k, cx, cy, z0, w, d, h, n_front=5, n_side=3, mat="steel", t=0.03):
    """Vertical bars on all four sides of a w x d x h cage volume."""
    for i in range(n_front):
        x = cx - w / 2 + w * (i + 0.5) / n_front
        for yy in (cy - d / 2, cy + d / 2):
            k.box((x, yy, z0 + h / 2), (t, t, h), mat, jitter=False)
    for i in range(n_side):
        y = cy - d / 2 + d * (i + 0.5) / n_side
        for xx in (cx - w / 2, cx + w / 2):
            k.box((xx, y, z0 + h / 2), (t, t, h), mat, jitter=False)


def cage(k, cx=0.0, cy=0.0, w=0.95, d=0.75, h=0.8, legs=0.28, roof="wood", bar="steel"):
    """Pet emporium cage: wooden plinth on stubby legs, bars, wooden roof with a ridge and a
    carry ring. Returns (floor_z, inner w, inner d) so the pet can be placed inside."""
    for dx in (-1, 1):
        for dy in (-1, 1):
            k.box((cx + dx * (w / 2 - 0.06), cy + dy * (d / 2 - 0.06), legs / 2), (0.1, 0.1, legs), "wood_d")
    z0 = legs
    k.box((cx, cy, z0 + 0.05), (w + 0.08, d + 0.08, 0.1), "wood")
    k.box((cx, cy, z0 + 0.105), (w - 0.06, d - 0.06, 0.012), "straw", jitter=True)
    zf = z0 + 0.1
    for dx in (-1, 1):
        for dy in (-1, 1):
            k.box((cx + dx * w / 2, cy + dy * d / 2, zf + h / 2), (0.07, 0.07, h), "wood_d")
    bars_box(k, cx, cy, zf, w, d, h, n_front=5, n_side=3, mat=bar, t=0.026)
    k.box((cx, cy - d / 2, zf + 0.04), (w, 0.06, 0.08), "wood_d")
    # roof: frame + gable with the ridge running front-to-back, so the camera sees a
    # triangular gable end (reads as a little house) instead of a flat sloped panel
    k.box((cx, cy, zf + h + 0.04), (w + 0.1, d + 0.1, 0.08), "wood")
    zr = zf + h + 0.08
    ex, ey, rh = w / 2 + 0.1, d / 2 + 0.1, 0.3
    rv = [(cx - ex, cy - ey, zr), (cx + ex, cy - ey, zr), (cx + ex, cy + ey, zr), (cx - ex, cy + ey, zr),
          (cx, cy - ey, zr + rh), (cx, cy + ey, zr + rh)]
    k.add(rv, [(0, 4, 5, 3), (1, 2, 5, 4), (0, 1, 4), (2, 3, 5)], roof)
    for sx in (-1, 1):                              # eave boards give the roof thickness
        k.box((cx + sx * ex * 0.5, cy, zr + rh * 0.5 + 0.02), (ex * 1.05, d + 0.26, 0.05), "wood_d",
              rot=(0, sx * math.degrees(math.atan2(rh, ex)), 0))
    k.box((cx, cy - ey - 0.01, zr + rh * 0.38), (0.12, 0.02, 0.12), "gold", rot=(0, 45, 0), jitter=False)
    k.tube(k.arc_pts((cx, cy - 0.12, zr + rh), (cx, cy, zr + rh + 0.2), (cx, cy + 0.12, zr + rh), 4),
           [0.025] * 5, "iron", segs=4)
    # door latch + hinge (front, right side)
    k.box((cx + w * 0.28, cy - d / 2 - 0.03, zf + h * 0.45), (0.07, 0.04, 0.1), "gold", jitter=False)
    return zf + 0.012, w, d


def stool(k, x, y, z=0.0, h=0.45, r=0.2):
    for i in range(3):
        a = math.radians(90 + 120 * i)
        k.box((x + math.cos(a) * r * 0.6, y + math.sin(a) * r * 0.6, z + h / 2 - 0.03), (0.05, 0.05, h - 0.05),
              "wood_d", rot=(math.sin(a) * 8, -math.cos(a) * 8, 0))
    k.cyl((x, y, z + h - 0.06), r, r, 0.06, "wood", segs=7)


def coin_pile(k, x, y, z, r=0.4, h=0.25, n=10, seed_off=0):
    k.cyl((x, y, z), r, r * 0.25, h, "coin", segs=7)
    for i in range(n):
        a = k.rng.uniform(0, 6.283)
        rr = k.rng.uniform(0.2, 1.0) * r
        k.cyl((x + math.cos(a) * rr, y + math.sin(a) * rr, z + 0.002), 0.06, 0.06, 0.02, "gold", segs=6,
              rot=(k.rng.uniform(-15, 15), k.rng.uniform(-15, 15), 0))


def sword(k, x, y, z, length=1.0, rot=(0, 0, 0), blade="steel"):
    """Upright sword standing on its tip at (x,y,z); rot applied about the tip."""
    from mathutils import Euler, Vector
    e = Euler(tuple(math.radians(a) for a in rot), "XYZ")

    def T(p):
        v = Vector(p)
        v.rotate(e)
        return (x + v.x, y + v.y, z + v.z)
    L = length
    k.add([T((-0.035, 0, 0.1)), T((0.035, 0, 0.1)), T((0, 0, 0))], [(0, 1, 2)], blade, jitter=False)
    k.box(T((0, 0, 0.1 + L * 0.33)), (0.07, 0.02, L * 0.66), blade, rot=rot, jitter=False)
    k.box(T((0, 0, 0.1 + L * 0.68)), (0.24, 0.05, 0.05), "gold", rot=rot, jitter=False)
    k.box(T((0, 0, 0.1 + L * 0.78)), (0.04, 0.04, L * 0.18), "leather", rot=rot, jitter=False)
    k.box(T((0, 0, 0.1 + L * 0.88)), (0.07, 0.07, 0.06), "gold", rot=rot, jitter=False)


def bone(k, a, b, r=0.035, mat="bone"):
    k.tube([a, b], [r, r], mat, segs=4)
    for p in (a, b):
        k.rock(p, (r * 1.7, r * 1.7, r * 1.5), mat, subdiv=1, rough=0.1, flat_bottom=False)
