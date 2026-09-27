"""Castle keep props (Stonehaven castle): throne, banners, council/banquet table, chairs,
suit of armour, chandelier, braziers.   blender -b -P blender_scripts/props_castle.py"""
import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from prop_parts import OLD_BASE_PX, new_kit, run, candle, flame, sword  # noqa: E402

BANNER = {"banner": "#a02830"}   # content.py castle_banner colour [160, 40, 48]


def game(k, kind, ids, drawer, cur_px, note=""):
    k.meta["group"] = "castle"
    k.meta["game"] = {"kind": kind, "ids": ids, "drawer": drawer, "current_px_at_tile40": cur_px,
                      "footprint_tiles": [1, 1], "old_base_offset_px": OLD_BASE_PX.get(k.key), "note": note}


def throne():
    k = new_kit("throne", seed=41, title="Castle Throne", floor="stone")
    k.box((0, 0.05, 0.1), (2.0, 1.6, 0.2), "stone")
    k.box((0, 0.1, 0.27), (1.6, 1.3, 0.14), "stone_l")
    k.box((0, -0.72, 0.1), (0.9, 0.3, 0.205), "red", jitter=False)          # carpet runner on the step
    k.box((0, 0.1, 0.55), (1.1, 0.85, 0.42), "wood_red")
    k.box((0, -0.33, 0.55), (1.12, 0.04, 0.3), "gold", jitter=False)
    k.box((0, 0.05, 0.82), (0.95, 0.72, 0.14), "red")                      # cushion
    k.box((0, 0.46, 1.5), (1.1, 0.22, 1.9), "wood_red", taper=0.82)        # backrest
    k.box((0, 0.34, 1.35), (0.74, 0.04, 1.1), "red")
    k.box((0, 0.33, 1.35), (0.5, 0.02, 0.7), "red_d", jitter=False)
    # crest: pointed gold arch + gem
    k.add([(-0.46, 0.35, 2.4), (0.46, 0.35, 2.4), (0, 0.35, 2.9), (-0.46, 0.5, 2.4), (0.46, 0.5, 2.4),
           (0, 0.5, 2.9)], [(0, 1, 2), (5, 4, 3), (0, 3, 4, 1), (1, 4, 5, 2), (2, 5, 3, 0)], "gold")
    k.box((0, 0.33, 2.58), (0.14, 0.05, 0.18), "gem_r", rot=(0, 45, 0), jitter=False)
    for x in (-0.55, 0.55):
        k.box((x, 0.46, 1.4), (0.14, 0.26, 2.0), "wood_red")               # back posts
        k.cone((x, 0.46, 2.4), 0.1, 0.3, "gold", segs=4)
        k.box((x, 0.05, 1.02), (0.16, 0.82, 0.12), "wood_red")             # armrests
        k.rock((x, -0.36, 1.1), (0.1, 0.1, 0.1), "gold", subdiv=1, rough=0.1)
        k.box((x, -0.34, 0.6), (0.14, 0.14, 0.62), "wood_red")
    k.collider("dais", (0, 0.1, 0.9), (2.0, 1.6, 1.8))
    game(k, "throne", ["castle_throne"], "draw_furniture -> draw_throne (x0.72)", (46, 57))
    k.finish()


def banner_stand():
    k = new_kit("banner_stand", seed=42, title="Castle Banner", floor="stone", extra=BANNER)
    k.box((0, 0, 0.05), (0.8, 0.14, 0.1), "wood_d")
    k.box((0, 0, 0.05), (0.14, 0.8, 0.1), "wood_d")
    k.cyl((0, 0, 0.1), 0.1, 0.1, 0.1, "iron", segs=6)
    k.cyl((0, 0, 0.1), 0.05, 0.045, 2.75, "wood_d", segs=6)
    k.cone((0, 0, 2.85), 0.07, 0.22, "gold", segs=4)
    k.cyl((0, 0, 2.8), 0.07, 0.07, 0.06, "gold", segs=6)
    k.box((0, -0.06, 2.58), (1.1, 0.06, 0.06), "wood_d")
    for x in (-0.57, 0.57):
        k.rock((x, -0.06, 2.58), (0.05, 0.05, 0.05), "gold", subdiv=1, rough=0.05)
    # banner cloth: 6 vertical strips with a gentle wave + swallowtail, real thickness
    n, w, top, h = 6, 1.0, 2.55, 1.45
    for i in range(n):
        x0 = -w / 2 + i * w / n
        y = -0.1 + 0.035 * math.sin(i * 1.3)
        bot = top - h + (0.25 * abs((i + 0.5) / n - 0.5) * 2 if True else 0)
        k.box((x0 + w / n / 2, y, (top + bot) / 2), (w / n + 0.004, 0.025, top - bot), "banner", jitter=False)
    k.box((0, -0.125, 2.47), (1.02, 0.02, 0.1), "gold", jitter=False)
    # emblem: gold crown on the cloth
    k.box((0, -0.13, 1.85), (0.36, 0.02, 0.14), "gold", jitter=False)
    for x in (-0.14, 0, 0.14):
        k.add([(x - 0.06, -0.135, 1.92), (x + 0.06, -0.135, 1.92), (x, -0.135, 2.08)], [(0, 1, 2), (2, 1, 0)], "gold",
              jitter=False)
    k.box((0, -0.14, 1.6), (0.04, 0.02, 0.3), "gold", jitter=False)
    k.collider("pole", (0, 0, 1.0), (0.5, 0.5, 2.0))
    k.meta["recolour"] = {"material": "banner", "default_rgb": [160, 40, 48],
                          "note": "content.py passes spot['color']; tint material 'banner' or render one sprite per colour"}
    game(k, "banner", ["castle_banner_w", "castle_banner_e"], "draw_banner_stand(color=...)", (31, 42))
    k.finish()


def banquet_table():
    k = new_kit("banquet_table", seed=43, title="Council / Banquet Table", floor="stone",
                emissive=("candle",))
    L, W, H = 3.2, 1.15, 0.82
    k.box((0, 0, H), (L, W, 0.1), "plank")
    k.box((0, 0, H - 0.08), (L - 0.2, W - 0.2, 0.06), "wood_d")
    for x in (-1.25, 1.25):                                    # trestles
        k.box((x, 0, 0.06), (0.2, W - 0.1, 0.12), "wood_d")
        k.box((x, 0, H / 2), (0.14, 0.2, H - 0.1), "wood")
        k.box((x, 0, H - 0.14), (0.16, W - 0.25, 0.1), "wood_d")
    k.box((0, 0, 0.3), (2.5, 0.12, 0.1), "wood")
    k.box((0, 0, H + 0.055), (L - 0.4, 0.42, 0.012), "red", jitter=False)    # runner
    for x in (-0.95, 0.95):
        k.box((x, -0.23, H - 0.1), (0.42, 0.02, 0.24), "red", jitter=False)
    # centre candelabra
    k.cyl((0, 0, H + 0.06), 0.12, 0.05, 0.08, "gold", segs=6)
    k.cyl((0, 0, H + 0.14), 0.03, 0.03, 0.35, "gold", segs=5)
    k.box((0, 0, H + 0.45), (0.5, 0.05, 0.04), "gold", jitter=False)
    for x in (-0.24, 0, 0.24):
        candle(k, x, 0, H + 0.47 + (0.05 if x == 0 else 0), h=0.14, r=0.03)
    # plates, goblets, roast, bread
    for x in (-1.2, -0.55, 0.55, 1.2):
        for y in (-0.38, 0.38):
            k.cyl((x, y, H + 0.05), 0.14, 0.14, 0.02, "steel", segs=8)
            k.cyl((x + 0.2, y * 0.8, H + 0.05), 0.035, 0.05, 0.14, "gold", segs=5)
    k.cyl((0.75, 0.0, H + 0.06), 0.26, 0.3, 0.03, "steel", segs=8)
    k.rock((0.75, 0.0, H + 0.14), (0.2, 0.14, 0.1), "leather", subdiv=1, rough=0.1)
    k.tube([(0.9, 0.0, H + 0.14), (1.02, 0.02, H + 0.2)], [0.03, 0.02], "bone", segs=4)
    k.rock((-0.75, 0.05, H + 0.1), (0.16, 0.09, 0.07), "plank", subdiv=1, rough=0.1)
    k.collider("table", (0, 0, 0.5), (L, W, 1.0))
    game(k, "table", ["castle_table (Council Table)", "any long table"], "draw_furniture -> draw_table", (48, 30),
         "the keep has a 'Council Table' + 2 chairs; this is its banquet version")
    k.finish()


def castle_chair():
    k = new_kit("castle_chair", seed=44, title="Castle Chair", floor="stone")
    for x in (-0.24, 0.24):
        for y in (-0.22, 0.22):
            k.box((x, y, 0.24), (0.07, 0.07, 0.48), "wood_d")
    k.box((0, 0, 0.5), (0.58, 0.54, 0.07), "wood_red")
    k.box((0, -0.02, 0.56), (0.5, 0.46, 0.06), "red")
    for x in (-0.25, 0.25):
        k.box((x, 0.24, 0.95), (0.08, 0.08, 0.9), "wood_red")
        k.cone((x, 0.24, 1.4), 0.06, 0.14, "gold", segs=4)
    k.box((0, 0.25, 1.05), (0.44, 0.05, 0.55), "wood_red")
    k.box((0, 0.22, 1.05), (0.3, 0.02, 0.36), "red", jitter=False)
    k.box((0, 0.25, 1.35), (0.56, 0.07, 0.07), "wood_d")
    k.box((0, -0.22, 0.15), (0.48, 0.04, 0.04), "wood_d")
    k.collider("chair", (0, 0, 0.5), (0.6, 0.6, 1.0))
    k.meta["facing_note"] = "game chairs have 'facing'; render yaw sprites _s/_w/_n/_e (render_sprites.py --yaws)"
    game(k, "chair", ["castle_chair_a", "castle_chair_b", "other chairs"], "draw_furniture -> draw_chair(facing)",
         (21, 35))
    k.finish()


def suit_of_armour():
    k = new_kit("suit_of_armour", seed=45, title="Suit of Armour", floor="stone")
    k.box((0, 0, 0.07), (0.75, 0.6, 0.14), "wood_d")
    k.box((0, 0, 0.16), (0.65, 0.5, 0.04), "stone_l")
    for x in (-0.13, 0.13):
        k.box((x, -0.06, 0.24), (0.16, 0.28, 0.12), "steel")               # sabatons
        k.box((x, 0, 0.55), (0.14, 0.15, 0.55), "steel", taper=1.15)       # greaves
        k.box((x, -0.02, 0.86), (0.15, 0.16, 0.1), "iron")                 # knees
        k.box((x, 0, 1.08), (0.17, 0.18, 0.38), "steel", taper=1.12)       # thighs
    k.box((0, 0, 1.28), (0.44, 0.26, 0.14), "iron", taper=0.9)              # fauld
    k.box((0, 0, 1.54), (0.46, 0.28, 0.44), "steel", taper=1.18)           # breastplate
    k.box((0, -0.15, 1.56), (0.04, 0.02, 0.38), "steel", jitter=False)     # ridge
    k.box((0, 0, 1.32), (0.42, 0.24, 0.06), "leather", jitter=False)       # belt
    k.box((0, -0.125, 1.32), (0.07, 0.02, 0.06), "gold", jitter=False)
    for x in (-0.33, 0.33):
        k.rock((x, 0, 1.76), (0.14, 0.15, 0.1), "steel", subdiv=1, rough=0.06)   # pauldrons
        k.box((x * 1.02, 0, 1.52), (0.12, 0.13, 0.34), "steel")
        k.box((x * 1.02, -0.02, 1.3), (0.11, 0.12, 0.14), "iron")
    k.box((-0.34, -0.06, 1.16), (0.12, 0.14, 0.12), "iron")                 # left gauntlet
    k.box((0.36, -0.1, 1.18), (0.12, 0.14, 0.12), "iron")
    k.cyl((0, 0, 1.78), 0.13, 0.13, 0.26, "steel", segs=6)                  # helm
    k.cone((0, 0, 2.04), 0.13, 0.08, "steel", segs=6)
    k.box((0, -0.125, 1.92), (0.18, 0.02, 0.03), "black", jitter=False)    # visor slit
    k.box((0, -0.12, 1.85), (0.03, 0.03, 0.12), "steel", jitter=False)
    k.tube(k.arc_pts((0, 0.02, 2.1), (0, 0.1, 2.35), (0, 0.32, 2.2), 4), [0.05, 0.06, 0.05, 0.04, 0.0], "red", segs=4)
    # halberd held in the right hand
    k.tube([(0.36, -0.12, 0.18), (0.36, -0.12, 2.45)], [0.022, 0.022], "wood_d", segs=4)
    k.add([(0.36, -0.12, 2.0), (0.58, -0.12, 2.08), (0.58, -0.12, 2.32), (0.36, -0.12, 2.26)],
          [(0, 1, 2, 3), (3, 2, 1, 0)], "steel", jitter=False)
    k.cone((0.36, -0.12, 2.45), 0.04, 0.2, "steel", segs=4)
    k.collider("stand", (0, 0, 1.0), (0.8, 0.65, 2.0))
    game(k, "suit_of_armour (NEW)", [], "none - NEW optional prop",
         None, "castle has an 'Armoury Rack' (weapon_rack); this is optional extra dressing, or use it for castle_rack")
    k.finish()


def chandelier():
    k = new_kit("chandelier", seed=46, title="Chandelier", floor="stone", emissive=("candle",))
    k.tube([(0, 0, 3.6), (0, 0, 2.75)], [0.02, 0.02], "iron", segs=4)       # chain
    for z in (3.45, 3.2, 2.95):
        k.box((0, 0, z), (0.06, 0.02, 0.12), "iron", rot=(0, 0, (z * 100) % 90), jitter=False)
    for i in range(4):
        a = math.radians(45 + 90 * i)
        k.tube([(0, 0, 2.75), (math.cos(a) * 0.62, math.sin(a) * 0.62, 2.42)], [0.02, 0.02], "iron", segs=3)
    ring = [(math.cos(2 * math.pi * i / 10) * 0.66, math.sin(2 * math.pi * i / 10) * 0.66, 2.4) for i in range(11)]
    k.tube(ring, [0.045] * 11, "iron", segs=4)
    k.cyl((0, 0, 2.3), 0.12, 0.2, 0.16, "gold", segs=6)
    k.cone((0, 0, 2.3), 0.12, 0.2, "gold", segs=6, rot=(180, 0, 0))
    for i in range(6):
        a = 2 * math.pi * (i + 0.5) / 6
        x, y = math.cos(a) * 0.66, math.sin(a) * 0.66
        k.cyl((x, y, 2.42), 0.06, 0.08, 0.05, "gold", segs=6)
        candle(k, x, y, 2.47, h=0.16, r=0.035)
    k.meta["hangs"] = {"ceiling_z": 3.6, "note": "origin is the floor point under it; no collider (overhead)"}
    game(k, "chandelier (NEW)", [], "none - NEW optional prop; castle has 'castle_candle' + braziers", None,
         "draw it in an overhead layer after the roof check, or skip in 2D and use only in a 3D route")
    k.finish()


def brazier():
    k = new_kit("brazier", seed=47, title="Brazier", floor="stone", emissive=("fire", "fire_core", "ember"))
    for i in range(3):
        a = math.radians(90 + 120 * i)
        k.tube([(math.cos(a) * 0.36, math.sin(a) * 0.36, 0.0), (math.cos(a) * 0.2, math.sin(a) * 0.2, 0.55),
                (math.cos(a) * 0.3, math.sin(a) * 0.3, 0.78)], [0.035, 0.03, 0.03], "iron", segs=4)
        k.box((math.cos(a) * 0.37, math.sin(a) * 0.37, 0.03), (0.1, 0.1, 0.06), "iron")
    k.cyl((0, 0, 0.45), 0.08, 0.08, 0.1, "iron", segs=6)
    k.cyl((0, 0, 0.62), 0.16, 0.4, 0.22, "iron", segs=8)
    k.cyl((0, 0, 0.84), 0.41, 0.43, 0.05, "steel", segs=8, caps=False)
    k.cyl((0, 0, 0.8), 0.37, 0.37, 0.03, "ember", segs=8)
    for i in range(6):
        a = 2 * math.pi * i / 6
        k.rock((math.cos(a) * 0.2, math.sin(a) * 0.2, 0.84), (0.08, 0.08, 0.05), "black", subdiv=1, rough=0.25)
    flame(k, 0, 0, 0.82, s=0.85)
    k.collider("brazier", (0, 0, 0.5), (0.8, 0.8, 1.0))
    game(k, "brazier", ["castle_brazier_w", "castle_brazier_e"], "draw_furniture -> draw_brazier", (21, 38))
    k.finish()


BUILDERS = {"throne": throne, "banner_stand": banner_stand, "banquet_table": banquet_table,
            "castle_chair": castle_chair, "suit_of_armour": suit_of_armour, "chandelier": chandelier,
            "brazier": brazier}

if __name__ == "__main__":
    run(BUILDERS)
