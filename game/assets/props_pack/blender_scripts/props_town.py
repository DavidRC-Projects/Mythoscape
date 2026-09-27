"""Town / service props: bank, smithy, well, fountain, shops.
blender -b -P blender_scripts/props_town.py [-- --only furnace,anvil --no-render]"""
import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from prop_parts import (OLD_BASE_PX, new_kit, run, barrel, crate, chest, candle, flame, logs, stool,  # noqa: E402
                        coin_pile, sword)


def game(k, kind, ids, drawer, cur_px, note=""):
    k.meta["group"] = "town"
    k.meta["game"] = {"kind": kind, "ids": ids, "drawer": drawer, "current_px_at_tile40": cur_px,
                      "footprint_tiles": [1, 1], "old_base_offset_px": OLD_BASE_PX.get(k.key), "note": note}


# ------------------------------------------------------------------ bank
def bank_booth():
    k = new_kit("bank_booth", seed=11, title="Bank Booth")
    k.box((0, 0, 0.05), (2.55, 1.05, 0.1), "stone_d")
    k.box((0, 0.02, 0.55), (2.4, 0.8, 0.9), "wood")
    for x in (-0.8, 0.0, 0.8):                     # recessed front panels
        k.box((x, -0.385, 0.55), (0.6, 0.04, 0.58), "wood_d")
        k.box((x, -0.41, 0.55), (0.34, 0.02, 0.3), "wood_red")
    for x in (-1.2, -0.4, 0.4, 1.2):               # pilasters
        k.box((x, -0.41, 0.55), (0.12, 0.08, 0.9), "plank")
    k.box((0, -0.05, 1.04), (2.62, 1.02, 0.09), "plank")
    k.box((0, -0.57, 0.99), (2.62, 0.06, 0.05), "wood_d")
    for x in (-1.22, 1.22):                        # screen posts
        k.box((x, 0.28, 1.75), (0.16, 0.16, 1.35), "wood_d")
        k.cone((x, 0.28, 2.62), 0.1, 0.18, "gold", segs=4)
    k.box((0, 0.28, 2.5), (2.75, 0.22, 0.2), "wood")
    k.box((0, 0.14, 2.52), (1.2, 0.07, 0.36), "wood_red")          # sign board
    k.cyl((0, 0.1, 2.52), 0.13, 0.13, 0.04, "gold", segs=8, rot=(90, 0, 0))
    k.cyl((0, 0.06, 2.52), 0.07, 0.07, 0.02, "coin", segs=8, rot=(90, 0, 0))
    for i in range(10):                            # teller bars, window gap in the middle
        x = -1.08 + i * 0.24
        if abs(x) < 0.3:
            continue
        k.box((x, 0.28, 1.74), (0.04, 0.04, 1.32), "steel", jitter=False)
    k.box((0, 0.28, 2.02), (2.3, 0.05, 0.05), "iron", jitter=False)
    k.box((0, 0.28, 1.12), (2.3, 0.06, 0.06), "iron", jitter=False)
    # teller window arch
    k.box((0, 0.26, 1.72), (0.62, 0.08, 0.08), "gold", jitter=False)
    k.box((0, 0.26, 1.1), (0.7, 0.14, 0.06), "plank")
    # back wall panel (so the booth reads as a room divider, not a floating fence)
    k.box((0, 0.42, 1.74), (2.4, 0.06, 1.32), "wood_d")
    # counter clutter: ledger, coins, quill
    k.box((-0.7, -0.15, 1.11), (0.42, 0.3, 0.06), "red_d", rot=(0, 0, 12))
    k.box((-0.7, -0.15, 1.145), (0.38, 0.27, 0.012), "cream", rot=(0, 0, 12), jitter=False)
    k.tube([(-0.58, -0.18, 1.15), (-0.5, -0.1, 1.38)], [0.012, 0.03], "cream", segs=3)
    for i, (x, y) in enumerate(((0.55, -0.2), (0.68, -0.12), (0.62, -0.28))):
        for j in range(3 - i):
            k.cyl((x, y, 1.085 + j * 0.035), 0.06, 0.06, 0.035, "coin", segs=6)
    k.box((0.0, -0.2, 1.1), (0.22, 0.16, 0.04), "gold", jitter=False)   # bell plate
    k.cyl((0.0, -0.2, 1.12), 0.07, 0.03, 0.08, "gold", segs=6)
    k.collider("booth", (0, 0.05, 1.3), (2.6, 1.05, 2.6))
    k.interact((0, -1.15, 1.0), (2.2, 1.2, 2.0))
    game(k, "bank", ["bank_booth", "bank_booth_w", "bank_booth_e"], "sprites.draw_bank_booth", (80, 70),
         "desk + barred teller window; opens the bank (vault) UI")
    k.finish()


def vault_chest():
    k = new_kit("vault_chest", seed=12, title="Vault Chest")
    k.box((0, 0, 0.09), (1.5, 1.0, 0.18), "stone")
    k.box((0, 0, 0.19), (1.38, 0.88, 0.04), "stone_l")
    chest(k, 0, 0, 0.21, w=1.22, d=0.74, h=0.56, wood="wood", band="iron", lock="gold", lid_h=0.3)
    for sx in (-1, 1):                             # iron corner caps
        for sy in (-1, 1):
            k.box((sx * 0.6, sy * 0.36, 0.3), (0.1, 0.1, 0.18), "iron")
    for x in (-0.39, 0.39):                        # rivets on the bands
        for z in (0.36, 0.55):
            k.box((x, -0.395, 0.21 + z), (0.035, 0.02, 0.035), "steel", jitter=False)
    # coin sack + spilled coins beside it
    k.rock((0.95, -0.2, 0.25), (0.26, 0.24, 0.3), "cloth", subdiv=1, rough=0.1)
    k.cyl((0.95, -0.2, 0.46), 0.08, 0.05, 0.12, "cloth", segs=5)
    k.cyl((0.95, -0.2, 0.47), 0.085, 0.085, 0.03, "rope", segs=5)
    for (x, y) in ((0.7, -0.55), (0.82, -0.62), (0.58, -0.66)):
        k.cyl((x, y, 0.19), 0.05, 0.05, 0.02, "coin", segs=6)
    k.collider("chest", (0.1, 0, 0.5), (1.7, 1.0, 1.0))
    k.interact((0, -1.05, 1.0), (1.6, 1.1, 2.0))
    game(k, "bank", ["bank_chest_a", "bank_chest_b", "dungeon_bank"], "sprites.draw_chest (bank variant='chest')",
         (34, 26), "'Vault Chest' - opens the same bank UI as the booth")
    k.finish()


def vault_door():
    k = new_kit("vault_door", seed=13, title="Bank Vault Door")
    k.box((0, 0.25, 1.5), (3.2, 0.5, 3.0), "stone")           # wall section
    for x in (-1.45, 1.45):
        k.box((x, -0.02, 1.5), (0.4, 0.1, 3.0), "stone_l")    # pilasters
    k.box((0, -0.03, 2.9), (3.3, 0.14, 0.24), "stone_l")
    k.box((0, -0.05, 0.08), (3.3, 0.2, 0.16), "stone_d")
    k.cyl((0, 0.0, 1.35), 1.2, 1.2, 0.08, "stone_d", segs=14, rot=(90, 0, 0))    # frame ring
    k.cyl((0, -0.08, 1.35), 1.02, 1.0, 0.2, "steel", segs=14, rot=(90, 0, 0))    # door
    k.cyl((0, -0.28, 1.35), 0.78, 0.74, 0.05, "iron", segs=14, rot=(90, 0, 0))
    for i in range(12):                            # bolts
        a = 2 * math.pi * i / 12
        k.box((math.cos(a) * 0.9, -0.29, 1.35 + math.sin(a) * 0.9), (0.08, 0.05, 0.08), "gold", jitter=False)
    k.cyl((0, -0.33, 1.35), 0.14, 0.12, 0.12, "gold", segs=8, rot=(90, 0, 0))    # hub
    ring = [(math.cos(2 * math.pi * i / 10) * 0.46, -0.44, 1.35 + math.sin(2 * math.pi * i / 10) * 0.46)
            for i in range(11)]
    k.tube(ring, [0.035] * 11, "gold", segs=4)
    for a in (0, 60, 120):                         # wheel spokes
        k.box((0, -0.42, 1.35), (0.92, 0.05, 0.06), "gold", rot=(0, a, 0), jitter=False)
    for z in (0.75, 1.95):                         # hinges
        k.box((-1.08, -0.2, z), (0.3, 0.2, 0.22), "iron")
    k.box((0, -0.08, 2.62), (0.9, 0.06, 0.22), "wood_red")    # "VAULT" plaque
    k.box((0, -0.12, 2.62), (0.6, 0.02, 0.06), "gold", jitter=False)
    k.collider("wall", (0, 0.2, 1.5), (3.3, 0.7, 3.0))
    k.interact((0, -0.95, 1.0), (1.8, 1.0, 2.0))
    game(k, "bank (optional decor)", [], "none - NEW optional prop",
         None, "the repo's 'bank vault' is the bank UI; this door is optional set dressing for the bank interior")
    k.finish()


# ------------------------------------------------------------------ smithy
def furnace():
    k = new_kit("furnace", seed=21, title="Furnace", emissive=("fire", "fire_core", "ember"))
    k.box((0, 0.05, 0.12), (1.9, 1.55, 0.24), "stone_d")
    k.box((0, 0.05, 0.85), (1.7, 1.4, 1.3), "brick", taper=0.9)
    for x in (-0.92, 0.92):                        # buttresses
        k.box((x, -0.25, 0.6), (0.22, 0.5, 1.2), "stone", taper=0.75)
    k.box((0, 0.05, 1.56), (1.66, 1.36, 0.14), "stone_l")
    k.box((0, 0.3, 2.15), (0.78, 0.74, 1.1), "brick", taper=0.8)
    k.box((0, 0.3, 2.76), (0.74, 0.7, 0.14), "stone_l")
    k.box((0, 0.3, 2.84), (0.44, 0.4, 0.04), "soot", jitter=False)
    # mouth: projecting firebox frame, dark recess, arch of voussoirs, fire bed
    k.box((0, -0.62, 0.62), (1.2, 0.16, 1.02), "stone_d", taper=0.92)
    k.box((0, -0.715, 0.6), (0.8, 0.03, 0.62), "soot", jitter=False)
    k.cyl((0, -0.7, 0.9), 0.4, 0.4, 0.03, "soot", segs=10, rot=(90, 0, 0), jitter=False)
    for i in range(7):
        a = math.pi * i / 6
        k.box((math.cos(a) * 0.5, -0.74, 0.92 + math.sin(a) * 0.48), (0.2, 0.1, 0.16), "stone_l",
              rot=(0, -math.degrees(a) + 90, 0))
    for x in (-0.5, 0.5):
        k.box((x, -0.74, 0.6), (0.18, 0.1, 0.64), "stone_l")
    k.box((0, -0.74, 0.34), (0.78, 0.1, 0.1), "ember")
    for x in (-0.2, 0.18):
        flame(k, x, -0.76, 0.38, s=0.66, core=(x < 0))
    # coal heap + bars cooling on the top slab
    for i in range(6):
        k.rock((-0.45 + k.rng.uniform(-0.12, 0.12), -0.2 + k.rng.uniform(-0.1, 0.1), 1.66), (0.09, 0.08, 0.06),
               "black", subdiv=1, rough=0.25)
    for j in range(3):
        k.box((0.5, -0.3 + j * 0.13, 1.66), (0.26, 0.1, 0.06), "steel", taper=0.8)
    k.box((0, -0.92, 0.28), (1.1, 0.34, 0.08), "stone")         # front ledge
    for i, (x, m) in enumerate(((-0.4, "iron"), (-0.28, "brick"), (0.35, "stone_d"))):
        k.rock((x, -0.96, 0.37), (0.1, 0.09, 0.08), m, subdiv=1, rough=0.2)
    k.cyl((0.12, -0.96, 0.32), 0.09, 0.12, 0.14, "iron", segs=6)   # crucible
    k.box((0.12, -0.96, 0.455), (0.16, 0.16, 0.012), "ember", jitter=False)
    # bellows on the right side
    k.add([(1.02, -0.2, 0.55), (1.02, 0.35, 0.62), (1.02, 0.35, 0.95), (1.3, -0.2, 0.55),
           (1.3, 0.35, 0.62), (1.3, 0.35, 0.95)], [(0, 1, 2), (3, 5, 4), (0, 3, 4, 1), (1, 4, 5, 2), (2, 5, 3, 0)],
          "leather")
    k.box((1.16, 0.08, 0.99), (0.34, 0.62, 0.05), "wood", rot=(-8, 0, 0))
    k.box((1.16, 0.62, 1.02), (0.06, 0.4, 0.05), "wood_d")
    # glow cracks at the top vent
    k.box((0, 0.05, 1.64), (0.5, 0.3, 0.03), "ember", jitter=False)
    k.collider("body", (0, 0.1, 1.0), (2.1, 1.6, 2.0))
    k.interact((0, -1.35, 1.0), (1.9, 1.1, 2.0))
    game(k, "furnace", ["smithy_furnace"], "sprites.draw_furnace", (67, 79), "smelt ores into bars")
    k.finish()


def anvil():
    k = new_kit("anvil", seed=22, title="Anvil", emissive=("ember",))
    k.cyl((0, 0, 0), 0.4, 0.35, 0.12, "wood_d", segs=8)
    k.cyl((0, 0, 0.12), 0.35, 0.33, 0.36, "wood", segs=8)
    k.cyl((0, 0, 0.48), 0.33, 0.33, 0.02, "plank", segs=8)
    for a in (20, 140, 260):                       # roots
        r = math.radians(a)
        k.box((math.cos(r) * 0.38, math.sin(r) * 0.38, 0.06), (0.24, 0.1, 0.12), "wood_d", rot=(0, 20, a))
    z = 0.5
    k.box((0, 0, z + 0.05), (0.46, 0.32, 0.1), "iron", taper=0.8)
    k.box((0, 0, z + 0.17), (0.24, 0.18, 0.16), "iron")
    k.box((0, 0, z + 0.3), (0.56, 0.26, 0.12), "iron", taper=1.08)
    k.box((0, 0, z + 0.365), (0.6, 0.27, 0.012), "steel", jitter=False)
    k.cone((0.29, 0, z + 0.3), 0.12, 0.34, "iron", segs=5, rot=(0, 90, 0))    # horn
    k.box((-0.34, 0, z + 0.31), (0.12, 0.22, 0.08), "iron", taper=0.8)          # heel
    k.box((0.05, -0.02, z + 0.385), (0.3, 0.05, 0.03), "ember", jitter=False)   # hot bar
    k.box((-0.12, 0.05, z + 0.41), (0.12, 0.07, 0.07), "steel")                  # hammer head
    k.box((-0.02, 0.1, z + 0.39), (0.3, 0.035, 0.035), "wood", rot=(0, 0, 25))
    # tongs leaning on the stump
    k.tube([(0.35, -0.3, 0.0), (0.36, -0.26, 0.48)], [0.018, 0.018], "iron", segs=3)
    k.tube([(0.42, -0.26, 0.0), (0.37, -0.25, 0.48)], [0.018, 0.018], "iron", segs=3)
    k.collider("anvil", (0, 0, 0.45), (0.9, 0.8, 0.9))
    k.interact((0, -0.95, 0.9), (1.4, 1.0, 1.8))
    game(k, "anvil", ["smithy_anvil"], "sprites.draw_anvil", (60, 28), "smith bars into items")
    k.finish()


def workbench():
    k = new_kit("workbench", seed=23, title="Workbench")
    for x in (-0.72, 0.72):
        for y in (-0.3, 0.3):
            k.box((x, y, 0.4), (0.12, 0.12, 0.8), "wood_d")
    k.box((0, 0, 0.86), (1.75, 0.82, 0.1), "plank")
    k.box((0, 0, 0.25), (1.5, 0.64, 0.05), "wood")               # lower shelf
    for x in (-0.4, 0.1, 0.45):
        k.box((x, 0, 0.3), (0.3, 0.55, 0.06), "plank", rot=(0, 0, 8))
    k.box((0, 0.36, 1.15), (1.7, 0.06, 0.5), "wood")            # back board with tools
    k.box((-0.75, -0.38, 0.9), (0.14, 0.14, 0.14), "iron")      # vice
    k.box((-0.75, -0.48, 0.92), (0.1, 0.08, 0.1), "iron")
    k.tube([(-0.9, -0.52, 0.92), (-0.6, -0.52, 0.92)], [0.015, 0.015], "steel", segs=3)
    k.box((0.15, -0.1, 0.92), (0.5, 0.02, 0.14), "steel", rot=(0, 0, 10), jitter=False)   # saw blade
    k.box((-0.13, -0.15, 0.93), (0.1, 0.05, 0.14), "wood", rot=(0, 0, 10))
    k.box((0.55, 0.05, 0.94), (0.14, 0.07, 0.07), "iron")       # hammer
    k.box((0.55, -0.1, 0.93), (0.04, 0.3, 0.035), "wood")
    for x, m in ((-0.5, "steel"), (-0.2, "iron"), (0.25, "steel")):   # hanging tools
        k.box((x, 0.32, 1.18), (0.05, 0.02, 0.32), m, jitter=False)
    k.collider("bench", (0, 0, 0.6), (1.8, 0.9, 1.2))
    game(k, "workbench", ["smithy_workbench"], "draw_furniture -> draw_workbench", (52, 35))
    k.finish()


def weapon_rack():
    k = new_kit("weapon_rack", seed=24, title="Weapon Rack")
    k.box((0, 0, 0.06), (1.5, 0.45, 0.12), "wood_d")
    for x in (-0.68, 0.68):
        k.box((x, 0.05, 0.85), (0.12, 0.12, 1.6), "wood")
        k.cone((x, 0.05, 1.65), 0.09, 0.14, "wood_d", segs=4)
    k.box((0, 0.05, 1.45), (1.5, 0.12, 0.1), "wood")
    k.box((0, 0.05, 0.45), (1.5, 0.12, 0.08), "wood")
    for i, x in enumerate((-0.42, -0.14, 0.14)):
        sword(k, x, -0.02, 0.13, length=1.25, rot=(0, 0, 0))
    k.tube([(0.4, 0.0, 0.12), (0.4, 0.0, 1.9)], [0.025, 0.025], "wood", segs=4)        # spear
    k.cone((0.4, 0.0, 1.9), 0.05, 0.22, "steel", segs=4)
    k.box((0.55, 0.0, 0.14 + 0.62), (0.03, 0.03, 1.24), "wood")                         # axe
    k.add([(0.55, 0.0, 1.3), (0.72, 0.0, 1.22), (0.72, 0.0, 1.46), (0.55, 0.0, 1.38)], [(0, 1, 2, 3), (3, 2, 1, 0)],
          "steel", jitter=False)
    k.cyl((-0.25, -0.34, 0.12), 0.34, 0.34, 0.06, "red", segs=8, rot=(72, 0, 0))       # shield
    k.cyl((-0.25, -0.36, 0.12), 0.36, 0.36, 0.03, "iron", segs=8, rot=(72, 0, 0), caps=False)
    k.cyl((-0.25, -0.42, 0.45), 0.08, 0.05, 0.05, "gold", segs=6, rot=(72, 0, 0))
    k.collider("rack", (0, 0, 0.9), (1.55, 0.6, 1.8))
    game(k, "weapon_rack", ["smithy_rack", "castle_rack (Armoury Rack)"], "draw_furniture -> draw_weapon_rack",
         (40, 42))
    k.finish()


def quench_bucket():
    k = new_kit("quench_bucket", seed=25, title="Quench Tub")
    k.cyl((0, 0, 0), 0.36, 0.42, 0.48, "wood", segs=9, caps=False)
    k.cyl((0, 0, 0.44), 0.42, 0.38, 0.04, "wood_d", segs=9, caps=False)       # inner lip
    k.cyl((0, 0, 0.02), 0.36, 0.36, 0.02, "wood_d", segs=9)
    for z in (0.07, 0.38):
        k.cyl((0, 0, z), 0.38 + (z * 0.12), 0.39 + (z * 0.12), 0.05, "iron", segs=9, caps=False)
    k.cyl((0, 0, 0.36), 0.39, 0.39, 0.02, "water_still", segs=9)
    k.tube([(0.1, -0.05, 0.3), (0.3, -0.25, 0.75)], [0.018, 0.018], "iron", segs=3)     # tongs
    k.tube([(0.16, -0.02, 0.3), (0.34, -0.2, 0.75)], [0.018, 0.018], "iron", segs=3)
    k.box((-0.12, 0.1, 0.39), (0.26, 0.05, 0.04), "steel", rot=(0, 20, 30))    # blade cooling in the water
    k.collider("tub", (0, 0, 0.25), (0.9, 0.9, 0.5))
    game(k, "quench_bucket", ["smithy_quench"], "draw_furniture -> draw_quench_bucket", (15, 14))
    k.finish()


# ------------------------------------------------------------------ outdoor landmarks
def wishing_well():
    k = new_kit("wishing_well", seed=31, title="Wishing Well", emissive=("water", "water_hi"), floor="outdoor")
    n = 10
    for course, (z, off, r) in enumerate(((0.2, 0.0, 1.0), (0.58, 0.5, 0.98))):
        for i in range(n):
            a = 2 * math.pi * (i + off) / n
            k.box((math.cos(a) * r, math.sin(a) * r, z), (0.64, 0.32, 0.38), "stone",
                  rot=(0, 0, math.degrees(a) + 90))
    for i in range(n):                              # coping
        a = 2 * math.pi * (i + 0.25) / n
        k.box((math.cos(a) * 1.0, math.sin(a) * 1.0, 0.82), (0.68, 0.4, 0.1), "stone_l",
              rot=(0, 0, math.degrees(a) + 90))
    k.cyl((0, 0, 0.0), 0.86, 0.86, 0.5, "soot", segs=10, caps=False)
    k.cyl((0, 0, 0.52), 0.86, 0.86, 0.02, "water", segs=10)
    for (x, y) in ((0.3, -0.2), (-0.25, 0.3), (0.05, 0.4)):
        k.cyl((x, y, 0.545), 0.05, 0.05, 0.01, "water_hi", segs=6)
    for x in (-1.12, 1.12):                         # posts
        k.box((x, 0, 1.35), (0.17, 0.17, 2.7), "wood_d")
    k.box((0, 0, 2.52), (2.5, 0.15, 0.15), "wood")
    k.cyl((-0.95, 0, 1.95), 0.11, 0.11, 1.9, "wood", segs=6, rot=(0, 90, 0))           # windlass
    k.box((0, 0, 1.95), (0.5, 0.25, 0.25), "rope")
    k.box((1.02, -0.12, 1.95), (0.05, 0.25, 0.05), "iron", jitter=False)            # crank
    k.box((1.02, -0.26, 1.85), (0.05, 0.05, 0.25), "iron", jitter=False)
    k.box((0, 0, 1.58), (0.03, 0.03, 0.62), "rope", jitter=False)
    k.cyl((0, 0, 1.08), 0.13, 0.16, 0.2, "wood", segs=7)                            # bucket
    k.cyl((0, 0, 1.12), 0.14, 0.15, 0.04, "iron", segs=7, caps=False)
    for side in (-1, 1):                            # roof (thick shingled planes)
        k.box((0, side * 0.62, 2.82), (2.9, 1.42, 0.09), "wood_red", rot=(side * -30, 0, 0))
        for j, t in enumerate((0.2, 0.55, 0.9)):
            y = side * (0.1 + t * 1.15)
            z = 3.15 - t * 0.66
            k.box((0, y, z + 0.06), (2.95, 0.12, 0.05), "wood_d", rot=(side * -30, 0, 0))
    k.box((0, 0, 3.22), (3.0, 0.14, 0.12), "wood_d")                                  # ridge
    for x in (-1.12, 1.12):                         # gable boards
        k.add([(x, -1.2, 2.45), (x, 1.2, 2.45), (x, 0, 3.15)], [(0, 1, 2), (2, 1, 0)], "wood")
    k.collider("ring", (0, 0, 0.5), (2.3, 2.3, 1.0))
    k.collider("posts", (0, 0, 1.4), (2.45, 0.3, 2.8))
    k.interact((0, -1.75, 1.0), (2.4, 1.1, 2.0))
    game(k, "wishing_well", ["wishing_well"], "sprites.draw_wishing_well (x1.55 scale)", (148, 188),
         "coin toss / wish UI; the old sprite is drawn ~5.5 m wide, this model is 2.9 m - scale the sprite up if "
         "you want the old footprint")
    k.finish()


def fountain():
    k = new_kit("fountain", seed=32, title="Plaza Fountain", emissive=("water", "water_hi"), floor="stone")
    k.cyl((0, 0, 0), 1.55, 1.55, 0.08, "stone_d", segs=8)
    k.cyl((0, 0, 0.08), 1.38, 1.34, 0.42, "stone", segs=8, caps=False)
    for i in range(8):                              # rim slabs
        a = 2 * math.pi * (i + 0.5) / 8
        w = 2 * 1.36 * math.tan(math.pi / 8) + 0.05
        k.box((math.cos(a) * 1.3, math.sin(a) * 1.3, 0.54), (w, 0.26, 0.1), "stone_l",
              rot=(0, 0, math.degrees(a) + 90))
    k.cyl((0, 0, 0.08), 1.2, 1.2, 0.34, "water", segs=8)
    k.cyl((0, 0, 0.42), 0.3, 0.22, 0.6, "marble", segs=6)
    k.cyl((0, 0, 0.95), 0.22, 0.72, 0.2, "marble", segs=8)
    k.cyl((0, 0, 1.15), 0.72, 0.72, 0.04, "stone_l", segs=8, caps=False)
    k.cyl((0, 0, 1.1), 0.64, 0.64, 0.06, "water", segs=8)
    k.cyl((0, 0, 1.15), 0.13, 0.09, 0.42, "marble", segs=6)
    k.cyl((0, 0, 1.57), 0.16, 0.16, 0.08, "marble", segs=6)
    k.cone((0, 0, 1.65), 0.1, 0.42, "water_hi", segs=5)
    for i in range(6):                              # falling sheets from the bowl
        a = 2 * math.pi * i / 6
        c, s = math.cos(a), math.sin(a)
        k.add([(c * 0.66 - s * 0.12, s * 0.66 + c * 0.12, 1.12), (c * 0.66 + s * 0.12, s * 0.66 - c * 0.12, 1.12),
               (c * 0.9 + s * 0.08, s * 0.9 - c * 0.08, 0.43), (c * 0.9 - s * 0.08, s * 0.9 + c * 0.08, 0.43)],
              [(0, 1, 2, 3), (3, 2, 1, 0)], "water_hi")
    for i in range(6):                              # ripples
        a = 2 * math.pi * (i + 0.5) / 6
        k.cyl((math.cos(a) * 0.95, math.sin(a) * 0.95, 0.42), 0.12, 0.12, 0.012, "water_hi", segs=6)
    k.collider("basin", (0, 0, 0.45), (3.1, 3.1, 0.9))
    k.interact((0, -2.0, 1.0), (2.4, 1.0, 2.0))
    game(k, "fountain", ["city_fountain"], "draw_furniture -> draw_fountain (x0.78)", (70, 62),
         "Plaza Fountain; sorted with rugs at cy - TILE//2")
    k.finish()


def market_stall():
    k = new_kit("market_stall", seed=33, title="Market Stall", floor="outdoor")
    k.box((0, 0, 0.47), (2.2, 0.8, 0.86), "wood")
    for x in (-0.72, 0, 0.72):
        k.box((x, -0.41, 0.47), (0.66, 0.03, 0.7), "plank")
    k.box((0, -0.05, 0.93), (2.35, 0.95, 0.08), "plank")
    for x in (-1.1, 1.1):
        for y, h in ((-0.45, 2.1), (0.45, 2.45)):
            k.box((x, y, h / 2), (0.1, 0.1, h), "wood_d")
    stripes = 6
    for i in range(stripes):
        x = -1.2 + (i + 0.5) * 2.4 / stripes
        k.box((x, -0.02, 2.3), (2.4 / stripes + 0.005, 1.25, 0.06), "red" if i % 2 == 0 else "cream",
              rot=(-16, 0, 0), jitter=False)
        k.add([(x - 0.2, -0.62, 2.13), (x + 0.2, -0.62, 2.13), (x, -0.63, 1.95)], [(0, 1, 2), (2, 1, 0)],
              "red" if i % 2 == 0 else "cream", jitter=False)
    for i, (x, m) in enumerate(((-0.75, "gem_r"), (-0.2, "straw"), (0.4, "gem_g"))):
        k.box((x, -0.05, 1.05), (0.45, 0.4, 0.16), "wood_d")
        for j in range(5):
            k.rock((x + k.rng.uniform(-0.14, 0.14), -0.05 + k.rng.uniform(-0.12, 0.12), 1.16), (0.07, 0.07, 0.07),
                   m, subdiv=1, rough=0.12)
    k.rock((0.88, -0.1, 1.04), (0.14, 0.09, 0.07), "plank", subdiv=1, rough=0.1)       # bread
    k.rock((0.95, 0.1, 1.04), (0.12, 0.08, 0.06), "plank", subdiv=1, rough=0.1)
    crate(k, 1.35, 0.3, 0, s=0.45, rot=10)
    k.collider("stall", (0.1, 0, 1.1), (2.55, 1.0, 2.2))
    k.interact((0, -1.05, 1.0), (2.0, 1.0, 2.0))
    game(k, "market_stall", ["market_stall_a", "market_stall_b", "market_stall_c"],
         "draw_furniture -> draw_market_stall (x0.7)", (54, 45))
    k.finish()


def shop_counter():
    k = new_kit("shop_counter", seed=34, title="Shop Counter")
    k.box((0, 0, 0.5), (2.2, 0.75, 0.96), "wood")
    for x in (-0.72, 0, 0.72):
        k.box((x, -0.385, 0.5), (0.62, 0.03, 0.66), "wood_d")
    for x in (-1.08, -0.36, 0.36, 1.08):
        k.box((x, -0.39, 0.5), (0.08, 0.05, 0.96), "plank")
    k.box((0, -0.03, 1.02), (2.35, 0.86, 0.08), "plank")
    # balance scale
    k.box((-0.6, -0.05, 1.08), (0.3, 0.18, 0.04), "wood_d")
    k.box((-0.6, -0.05, 1.3), (0.04, 0.04, 0.42), "gold", jitter=False)
    k.box((-0.6, -0.05, 1.5), (0.5, 0.03, 0.03), "gold", jitter=False)
    for dx in (-0.23, 0.23):
        k.cyl((-0.6 + dx, -0.05, 1.3), 0.1, 0.12, 0.04, "gold", segs=6)
        k.box((-0.6 + dx, -0.05, 1.41), (0.01, 0.01, 0.18), "iron", jitter=False)
    for i, m in enumerate(("red", "blue", "green")):   # cloth rolls
        k.cyl((0.2 + i * 0.05, 0.05 + i * 0.12, 1.12), 0.07, 0.07, 0.6, m, segs=6, rot=(0, 90, 8))
    k.cyl((0.75, -0.2, 1.06), 0.13, 0.09, 0.08, "wood_d", segs=7)                    # coin bowl
    k.cyl((0.75, -0.2, 1.12), 0.1, 0.1, 0.02, "coin", segs=7)
    k.box((0.0, -0.2, 1.08), (0.3, 0.2, 0.04), "cream", rot=(0, 0, -10))              # ledger
    k.collider("counter", (0, 0, 0.55), (2.3, 0.85, 1.1))
    k.interact((0, -1.0, 1.0), (2.0, 1.0, 2.0))
    game(k, "counter", ["shop_counter", "tackle_counter", "fish_counter", "pet_counter"],
         "draw_furniture -> draw_counter", (54, 30), "shopkeeper stands behind (+Y); buy/sell UI unchanged")
    k.finish()


def hearth():
    k = new_kit("hearth", seed=35, title="Hearth / Range", emissive=("fire", "fire_core", "ember"))
    k.box((0, 0.1, 0.55), (1.9, 0.9, 1.1), "stone")
    k.box((0, -0.36, 0.45), (1.0, 0.1, 0.72), "soot", jitter=False)
    for x in (-0.56, 0.56):
        k.box((x, -0.38, 0.45), (0.14, 0.14, 0.9), "stone_l")
    k.box((0, -0.18, 1.14), (2.1, 0.5, 0.14), "wood")                                  # mantel
    k.box((0, 0.2, 2.0), (1.4, 0.7, 1.6), "stone", taper=0.8)
    k.box((0, 0.2, 2.84), (0.8, 0.5, 0.1), "stone_l")
    for z, w in ((1.55, 1.3), (2.05, 1.18), (2.5, 1.06)):         # masonry courses on the breast
        k.box((0, -0.165 + (z - 1.2) * 0.044, z), (w, 0.04, 0.06), "stone_d", jitter=False)
    for (x, z) in ((-0.45, 1.35), (0.38, 1.8), (-0.2, 2.25), (0.3, 2.62), (-0.36, 1.95)):
        k.box((x, -0.17 + (z - 1.2) * 0.044, z), (0.22, 0.06, 0.14), "stone_l")
    k.box((0.55, -0.45, 1.36), (0.04, 0.04, 0.3), "iron", jitter=False)                 # ladle hanging off the mantel
    k.cyl((0.55, -0.45, 1.2), 0.06, 0.07, 0.05, "iron", segs=6)
    k.box((0, -0.72, 0.04), (1.6, 0.6, 0.08), "stone_d")                                # hearthstone
    k.box((0, -0.36, 0.14), (0.8, 0.12, 0.06), "ember", jitter=False)
    logs(k, 0, -0.22, 0.1, s=0.7)
    flame(k, -0.12, -0.36, 0.18, s=0.8)
    flame(k, 0.16, -0.34, 0.18, s=0.6, core=False)
    k.tube([(0.2, -0.2, 0.85), (0.2, -0.38, 0.85), (0.2, -0.38, 0.65)], [0.02] * 3, "iron", segs=3)   # hook
    k.cyl((0.2, -0.38, 0.45), 0.13, 0.17, 0.2, "black", segs=7)                         # pot
    for i, m in enumerate(("gold", "stone_l", "red_d")):                                # mantel items
        k.cyl((-0.7 + i * 0.3, -0.2, 1.21), 0.06, 0.05, 0.14, m, segs=6)
    k.collider("hearth", (0, 0.05, 1.0), (2.1, 1.0, 2.0))
    k.interact((0, -1.35, 1.0), (1.8, 1.0, 2.0))
    game(k, "range / fireplace", ["general_range", "house_hearth", "..."], "sprites.draw_fireplace", (60, 60),
         "cooking range - keep the cook action")
    k.finish()


def barrel_prop():
    k = new_kit("barrel", seed=36, title="Barrel")
    barrel(k, 0, 0, 0, r=0.34, h=0.9)
    k.box((0.1, -0.05, 0.93), (0.28, 0.12, 0.03), "plank", rot=(0, 6, 20))            # loose lid plank
    k.rock((0.34, -0.3, 0.14), (0.2, 0.18, 0.2), "cloth", subdiv=1, rough=0.12)           # sack
    k.cyl((0.34, -0.3, 0.3), 0.06, 0.04, 0.08, "cloth", segs=5)
    k.collider("barrel", (0.05, -0.05, 0.45), (0.85, 0.85, 0.9))
    game(k, "barrel", ["ore barrels, feed barrel, plaza barrel... (14 spots)"], "draw_furniture -> draw_barrel",
         (21, 25))
    k.finish()


BUILDERS = {
    "bank_booth": bank_booth, "vault_chest": vault_chest, "vault_door": vault_door,
    "furnace": furnace, "anvil": anvil, "workbench": workbench, "weapon_rack": weapon_rack,
    "quench_bucket": quench_bucket, "wishing_well": wishing_well, "fountain": fountain,
    "market_stall": market_stall, "shop_counter": shop_counter, "hearth": hearth, "barrel": barrel_prop,
}

if __name__ == "__main__":
    run(BUILDERS)
