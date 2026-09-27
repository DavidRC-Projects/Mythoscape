"""Dungeon interior props, 2 per entrance theme of the dungeon entrance pack:
dragon lair, goblin cave, skeleton crypt, spider nest, void rift, giant's cavern, wolf den.
blender -b -P blender_scripts/props_dungeons.py"""
import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from prop_parts import new_kit, run, chest, candle, flame, logs, coin_pile, sword, bone, crate  # noqa: E402


def game(k, theme, note="", ids=None):
    k.meta["group"] = "dungeons"
    k.meta["game"] = {"kind": "dungeon_prop (NEW)", "theme": theme, "ids": ids or [],
                      "drawer": "none yet - dungeon_interior_3d.draw_dungeon_props only has 'shadow_crypt'",
                      "current_px_at_tile40": None, "footprint_tiles": [2, 2], "note": note}


# ------------------------------------------------------------------ dragon lair
def dragon_hoard():
    k = new_kit("dragon_hoard", seed=61, title="Dragon Treasure Hoard", floor="cave")
    coin_pile(k, 0, 0.1, 0, r=1.1, h=0.55, n=18)
    coin_pile(k, -0.75, -0.35, 0, r=0.5, h=0.28, n=6)
    coin_pile(k, 0.8, -0.3, 0, r=0.45, h=0.22, n=6)
    chest(k, 0.55, 0.45, 0.0, w=0.8, d=0.5, h=0.38, wood="wood_red", band="gold", lock="gold", rot=-20, lid_h=0.2)
    k.box((0.55, 0.45, 0.45), (0.6, 0.3, 0.1), "coin", rot=(0, 0, -20))
    sword(k, -0.2, 0.2, 0.3, length=1.1, rot=(0, -18, 10))
    k.cyl((-0.55, 0.2, 0.3), 0.35, 0.35, 0.05, "gold", segs=8, rot=(-70, 0, 20))       # shield
    k.cyl((-0.56, 0.16, 0.34), 0.1, 0.06, 0.07, "gem_r", segs=6, rot=(-70, 0, 20))
    k.cyl((0.1, -0.2, 0.52), 0.13, 0.15, 0.1, "gold", segs=6)                          # crown
    for i in range(6):
        a = 2 * math.pi * i / 6
        k.cone((0.1 + math.cos(a) * 0.12, -0.2 + math.sin(a) * 0.12, 0.62), 0.03, 0.08, "gold", segs=3)
    for i, m in enumerate(("gem_r", "gem_b", "gem_g", "gem_r", "gem_b")):
        a = 1.2 * i + 0.3
        k.box((math.cos(a) * 0.7, 0.1 + math.sin(a) * 0.55, 0.2 + 0.06 * (i % 2)), (0.1, 0.1, 0.12), m,
              rot=(30, 45, i * 20), jitter=False)
    for (x, y) in ((0.95, 0.3), (-1.0, 0.25)):                                        # goblets
        k.cyl((x, y, 0.0), 0.07, 0.03, 0.12, "gold", segs=5)
        k.cyl((x, y, 0.12), 0.03, 0.08, 0.12, "gold", segs=5)
    k.collider("hoard", (0, 0.1, 0.35), (2.4, 1.8, 0.7))
    game(k, "dragon_lair", "decor; could be the lair's loot interactable")
    k.finish()


def dragon_egg_nest():
    k = new_kit("dragon_egg_nest", seed=62, title="Dragon Egg Nest", floor="cave", emissive=("ember",))
    for i in range(11):                                                               # charred ring
        a = 2 * math.pi * i / 11
        k.rock((math.cos(a) * 0.95, math.sin(a) * 0.8, 0.12), (0.3, 0.22, 0.2), "stone_d", subdiv=1, rough=0.25)
    for i in range(8):
        a = 2 * math.pi * i / 8 + 0.2
        k.cyl((math.cos(a) * 0.7, math.sin(a) * 0.55, 0.12), 0.05, 0.035, 0.8, "soot", segs=4,
              rot=(0, 80, math.degrees(a) + 80))
    k.disc((0, 0, 0), 0.8, "ember", segs=10, z=0.02, jag=0.2)
    k.cyl((0, 0, 0.02), 0.72, 0.6, 0.08, "black", segs=9)
    for (x, y, s, m) in ((-0.22, 0.05, 1.0, "scale_g"), (0.25, 0.12, 0.9, "red"), (0.02, -0.25, 0.85, "purple")):
        k.rock((x, y, 0.28 * s + 0.08), (0.2 * s, 0.2 * s, 0.3 * s), m, subdiv=2, rough=0.04, flat_bottom=True,
               rot=(0, 0, 0))
        for j in range(3):                                                             # speckles
            a = j * 2.1
            k.box((x + math.cos(a) * 0.19 * s, y + math.sin(a) * 0.19 * s, 0.3 * s + 0.08 + (j - 1) * 0.08),
                  (0.05, 0.05, 0.05), "bone", rot=(20, 20, math.degrees(a)), jitter=False)
    k.skull((0.85, -0.6, 0.0), 0.28, "bone", "black", rot=(0, 0, 30))
    bone(k, (-0.9, -0.5, 0.05), (-0.45, -0.75, 0.05))
    k.collider("nest", (0, 0, 0.3), (2.2, 1.9, 0.6))
    game(k, "dragon_lair")
    k.finish()


# ------------------------------------------------------------------ goblin cave
def goblin_campfire():
    k = new_kit("goblin_campfire", seed=63, title="Goblin Campfire", floor="cave",
                emissive=("fire", "fire_core", "ember"))
    for i in range(8):
        a = 2 * math.pi * i / 8
        k.rock((math.cos(a) * 0.5, math.sin(a) * 0.5, 0.08), (0.15, 0.13, 0.12), "stone", subdiv=1, rough=0.2)
    k.disc((0, 0, 0), 0.42, "ember", segs=8, z=0.015)
    logs(k, 0, 0, 0.02, s=1.0, n=4)
    flame(k, 0, 0, 0.1, s=1.0)
    for x in (-0.75, 0.75):                                                          # Y-sticks + spit
        k.tube([(x, 0, 0), (x, 0, 0.75)], [0.03, 0.025], "wood_d", segs=4)
        k.tube([(x, 0, 0.72), (x - 0.08, 0, 0.9)], [0.02, 0.015], "wood_d", segs=3)
        k.tube([(x, 0, 0.72), (x + 0.08, 0, 0.9)], [0.02, 0.015], "wood_d", segs=3)
    k.tube([(-0.85, 0, 0.8), (0.85, 0, 0.8)], [0.02, 0.02], "wood", segs=4)
    k.rock((0, 0, 0.78), (0.22, 0.14, 0.13), "leather", subdiv=1, rough=0.12)       # roast rat/boar
    k.tube([(0.2, 0, 0.8), (0.32, 0.03, 0.72)], [0.04, 0.02], "leather", segs=4)
    for (x, y) in ((-0.95, -0.55), (0.9, 0.55)):                                     # log stools
        k.cyl((x, y, 0), 0.2, 0.18, 0.35, "wood", segs=7)
        k.cyl((x, y, 0.35), 0.18, 0.18, 0.01, "plank", segs=7)
    k.cyl((0.85, -0.6, 0.0), 0.16, 0.2, 0.25, "iron", segs=7)                        # pot
    k.cyl((0.85, -0.6, 0.22), 0.17, 0.17, 0.02, "green", segs=7)
    k.collider("fire", (0, 0, 0.4), (1.2, 1.2, 0.8))
    game(k, "goblin_cave")
    k.finish()


def goblin_loot():
    k = new_kit("goblin_loot", seed=64, title="Goblin Loot Pile & Lean-to", floor="cave")
    # hide lean-to on two crooked poles
    for x in (-0.9, 0.9):
        k.tube([(x, 0.55, 0), (x * 0.95, 0.5, 1.5)], [0.04, 0.03], "wood_d", segs=4)
    k.add([(-1.0, 0.5, 1.45), (1.0, 0.5, 1.45), (1.05, 1.1, 0.0), (-1.05, 1.1, 0.0)], [(0, 1, 2, 3), (3, 2, 1, 0)],
          "hide")
    k.box((0, 0.51, 1.46), (2.1, 0.08, 0.08), "wood_d")
    for (x, z) in ((-0.5, 0.9), (0.4, 0.5)):
        k.box((x, 0.78, z), (0.3, 0.02, 0.22), "leather", rot=(-68, 0, 12), jitter=False)   # patches
    for i, (x, y, s) in enumerate(((-0.55, 0.0, 0.3), (-0.2, 0.2, 0.26), (0.55, 0.05, 0.28))):   # sacks
        k.rock((x, y, s * 0.8), (s, s * 0.9, s), "cloth" if i != 1 else "goblin_cloth", subdiv=1, rough=0.12)
        k.cyl((x, y, s * 1.55), 0.07, 0.04, 0.1, "cloth", segs=5)
    crate(k, 0.95, -0.1, 0, s=0.5, rot=25)
    k.box((0.95, -0.1, 0.52), (0.3, 0.52, 0.04), "plank", rot=(10, 20, 60))                  # broken lid
    k.cyl((0.2, -0.45, 0.15), 0.32, 0.32, 0.05, "wood", segs=7, rot=(70, 0, -10))           # crude shield
    k.box((0.2, -0.5, 0.36), (0.36, 0.03, 0.06), "red", rot=(-20, 0, 35), jitter=False)
    k.tube([(-0.9, -0.3, 0.02), (0.1, 0.3, 0.2)], [0.025, 0.02], "wood_d", segs=4)           # spear
    k.cone((0.1, 0.3, 0.2), 0.04, 0.2, "iron", segs=4, rot=(0, 72, 30))
    coin_pile(k, -0.25, -0.35, 0, r=0.2, h=0.08, n=5)
    k.skull((-0.95, -0.55, 0.0), 0.2, "bone", "black", rot=(0, 0, -20))
    bone(k, (0.5, -0.6, 0.03), (0.85, -0.45, 0.03))
    k.collider("pile", (0, 0.3, 0.5), (2.2, 1.6, 1.0))
    game(k, "goblin_cave")
    k.finish()


# ------------------------------------------------------------------ skeleton crypt
def crypt_sarcophagus():
    k = new_kit("crypt_sarcophagus", seed=65, title="Crypt Sarcophagus", floor="stone", emissive=("candle",))
    k.box((0, 0, 0.12), (1.3, 2.5, 0.24), "stone_d")
    # coffin: hexagonal-plan prism (wide at the shoulders)
    def ring(z, s):
        return [(-0.34 * s, -1.0 * s, z), (0.34 * s, -1.0 * s, z), (0.5 * s, -0.45 * s, z), (0.4 * s, 1.0 * s, z),
                (-0.4 * s, 1.0 * s, z), (-0.5 * s, -0.45 * s, z)]
    a, b = ring(0.24, 1.0), ring(0.9, 1.0)
    v = a + b
    f = [(i, (i + 1) % 6, 6 + (i + 1) % 6, 6 + i) for i in range(6)] + [tuple(range(5, -1, -1)), tuple(range(6, 12))]
    k.add(v, f, "stone")
    c, d = ring(0.9, 1.06), ring(1.02, 1.0)                                          # lid, slightly askew
    from mathutils import Matrix, Vector
    m = Matrix.Translation(Vector((0.08, 0.05, 0))) @ Matrix.Rotation(math.radians(6), 4, "Z")
    v = [tuple(m @ Vector(p)) for p in c + d]
    k.add(v, f, "stone_l")
    # effigy on the lid: bold relief so it reads from the high game camera
    k.box((0.07, -0.72, 1.14), (0.28, 0.26, 0.22), "marble")                          # head
    k.box((0.07, -0.72, 1.27), (0.3, 0.2, 0.05), "gold", jitter=False)                # circlet
    k.box((0.09, -0.12, 1.12), (0.46, 0.95, 0.18), "marble", taper=0.85)             # body
    k.box((0.1, 0.62, 1.1), (0.34, 0.32, 0.14), "marble")                             # feet
    k.box((0.08, -0.32, 1.23), (0.4, 0.12, 0.08), "stone_l", rot=(0, 0, 6))           # folded arms
    k.box((0.1, 0.0, 1.25), (0.07, 0.95, 0.05), "steel", rot=(0, 0, 6), jitter=False)  # sword blade
    k.box((0.07, -0.44, 1.26), (0.28, 0.06, 0.05), "gold", rot=(0, 0, 6), jitter=False)
    k.box((-0.55, -0.45, 0.8), (0.03, 0.6, 0.3), "black", rot=(0, 0, 18), jitter=False)   # dark gap at the lid
    for x in (-0.55, 0.55):
        for y in (-1.1, 1.1):
            k.cyl((x, y, 0.24), 0.07, 0.07, 0.03, "wax", segs=5)
            candle(k, x, y, 0.27, h=0.12 + 0.08 * ((x + y) > 0), r=0.035)
    k.skull((-0.5, 1.05, 0.24), 0.18, "bone", "black", rot=(0, 0, 20))
    # built head-to-foot along Y; turn it 90 deg so the effigy lies across the game view
    k.transform_since(0, rot_z=-90)
    k.collider("tomb", (0, 0, 0.55), (2.5, 1.3, 1.1))
    game(k, "skeleton_crypt", "could host a 'search' interaction; none required")
    k.finish()


def crypt_candelabra():
    k = new_kit("crypt_candelabra", seed=66, title="Crypt Candelabra & Urns", floor="stone", emissive=("candle",))
    for i in range(3):
        a = math.radians(90 + 120 * i)
        k.tube([(0, 0, 0.25), (math.cos(a) * 0.3, math.sin(a) * 0.3, 0.0)], [0.03, 0.03], "iron", segs=4)
    k.skull((0, 0, 0.12), 0.22, "bone", "black")
    k.tube([(0, 0, 0.3), (0, 0, 1.55)], [0.035, 0.03], "iron", segs=5)
    k.cyl((0, 0, 0.9), 0.07, 0.07, 0.06, "iron", segs=6)
    for sx in (-1, 1):
        for w, z in ((0.42, 1.45), (0.25, 1.62)):
            k.tube(k.arc_pts((0, 0, 1.4), (sx * w * 0.6, 0, 1.3), (sx * w, 0, z - 0.05), 3), [0.02] * 4, "iron", segs=3)
            k.cyl((sx * w, 0, z - 0.06), 0.05, 0.06, 0.04, "iron", segs=5)
            candle(k, sx * w, 0, z - 0.02, h=0.16, r=0.03)
            k.box((sx * w + 0.03, -0.02, z - 0.02), (0.02, 0.02, 0.1), "wax", jitter=False)   # drips
    k.cyl((0, 0, 1.55), 0.06, 0.07, 0.04, "iron", segs=5)
    candle(k, 0, 0, 1.59, h=0.2, r=0.035)
    for (x, y, s, m) in ((0.65, 0.15, 1.0, "stone_l"), (-0.6, 0.25, 0.8, "brick")):   # urns
        k.cyl((x, y, 0), 0.1 * s, 0.2 * s, 0.25 * s, m, segs=7)
        k.cyl((x, y, 0.25 * s), 0.2 * s, 0.1 * s, 0.25 * s, m, segs=7)
        k.cyl((x, y, 0.5 * s), 0.1 * s, 0.13 * s, 0.08 * s, m, segs=7)
        k.cyl((x, y, 0.58 * s), 0.1 * s, 0.03 * s, 0.05 * s, "stone_d", segs=7)
    k.disc((0.3, -0.35, 0), 0.25, "wax", segs=7, z=0.01)
    k.collider("stand", (0, 0.1, 0.8), (1.6, 0.8, 1.6))
    game(k, "skeleton_crypt")
    k.finish()


# ------------------------------------------------------------------ spider nest
def spider_cocoons():
    k = new_kit("spider_cocoons", seed=67, title="Web-wrapped Cocoons", floor="cave")
    k.disc((0, 0.1, 0), 1.1, "web", segs=12, z=0.01, jag=0.25)
    for (x, y, rz, s) in ((-0.45, 0.1, 25, 1.0), (0.4, 0.3, -30, 0.85)):          # lying victims
        k.rock((x, y, 0.2 * s), (0.25 * s, 0.6 * s, 0.22 * s), "web", subdiv=1, rough=0.1, rot=(0, 0, rz))
        for j in range(4):
            t = -0.45 + j * 0.3
            ang = math.radians(rz)
            cx, cy = x - math.sin(ang) * t * s, y + math.cos(ang) * t * s
            k.cyl((cx, cy, 0.2 * s), 0.22 * s * (1 - abs(t) * 0.5), 0.22 * s * (1 - abs(t) * 0.5), 0.05, "cloth",
                  segs=6, rot=(90, 0, rz + 90 + 15), caps=False)
    k.box((-0.2, -0.5, 0.08), (0.12, 0.2, 0.1), "leather", rot=(0, 0, 25))          # boot poking out
    # standing cocoon strung up on a web strand to a post
    k.tube([(0.1, -0.35, 0.0), (0.05, -0.35, 1.9)], [0.06, 0.04], "wood_d", segs=4)
    k.rock((0.35, -0.35, 0.9), (0.2, 0.2, 0.45), "web", subdiv=1, rough=0.1, flat_bottom=False)
    k.tube([(0.35, -0.35, 1.3), (0.35, -0.35, 1.6), (0.06, -0.35, 1.8)], [0.012, 0.012, 0.012], "web", segs=3)
    for z in (0.7, 1.0):
        k.cyl((0.35, -0.35, z), 0.19, 0.19, 0.04, "cloth", segs=6, caps=False)
    k.web(0.0, -0.3, 1.2, 0.8, 90, 200, spokes=5, rings=3)
    for i in range(3):                                                                # leg remains
        k.tube(k.arc_pts((0.85, -0.3 + i * 0.1, 0.02), (1.0, -0.2 + i * 0.1, 0.2), (1.1, -0.1 + i * 0.1, 0.02), 3),
               [0.02, 0.02, 0.015, 0.0], "chitin", segs=3)
    k.collider("cocoons", (0, 0.1, 0.4), (1.9, 1.6, 0.8))
    game(k, "spider_nest")
    k.finish()


def spider_egg_sacs():
    k = new_kit("spider_egg_sacs", seed=68, title="Spider Egg Sacs", floor="cave", emissive=("egg_glow",))
    k.disc((0, 0, 0), 0.95, "web", segs=10, z=0.01, jag=0.3)
    pts = [(0, 0, 0.3, 1.0), (-0.35, 0.15, 0.22, 0.75), (0.35, 0.1, 0.24, 0.8), (-0.1, -0.35, 0.2, 0.7),
           (0.25, -0.3, 0.16, 0.55), (-0.45, -0.2, 0.14, 0.5), (0.05, 0.4, 0.18, 0.6)]
    for (x, y, z, s) in pts:
        k.rock((x, y, z), (0.24 * s, 0.24 * s, 0.3 * s), "egg", subdiv=1, rough=0.08, flat_bottom=True)
    for (x, y, z, s) in pts[:3]:
        k.rock((x, y - 0.18 * s, z + 0.05), (0.06 * s, 0.03, 0.07 * s), "egg_glow", subdiv=1, rough=0.1)
    for i in range(6):                                                               # web strands over the sacs
        a = 2 * math.pi * i / 6
        k.tube(k.arc_pts((math.cos(a) * 0.7, math.sin(a) * 0.6, 0.0), (math.cos(a) * 0.3, math.sin(a) * 0.25, 0.7),
                         (0, 0, 0.62), 3), [0.012] * 4, "web", segs=3)
    k.rock((0.75, 0.4, 0.1), (0.12, 0.1, 0.08), "chitin", subdiv=1, rough=0.2)       # hatched shell
    k.collider("sacs", (0, 0, 0.35), (1.6, 1.4, 0.7))
    game(k, "spider_nest")
    k.finish()


# ------------------------------------------------------------------ void rift
def void_altar():
    k = new_kit("void_altar", seed=69, title="Void Altar", floor="stone", emissive=("void", "void_core", "candle"))
    k.box((0, 0.05, 0.1), (2.2, 1.6, 0.2), "void_stone")
    k.box((0, 0.1, 0.28), (1.8, 1.2, 0.16), "void_dark")
    k.box((0, 0.15, 0.7), (1.3, 0.7, 0.7), "void_stone", taper=0.9)
    k.box((0, 0.15, 1.1), (1.45, 0.82, 0.12), "void_dark")
    for x in (-0.4, 0.0, 0.4):                                                        # glowing runes
        k.box((x, -0.18, 0.72), (0.14, 0.02, 0.22), "void", jitter=False)
        k.box((x, -0.185, 0.72), (0.04, 0.02, 0.3), "void_core", jitter=False)
    k.box((0, -0.62, 0.21), (1.2, 0.02, 0.02), "void", jitter=False)
    # floating crystal above
    k.cone((0, 0.15, 1.55), 0.2, 0.32, "void_core", segs=4)
    k.cone((0, 0.15, 1.55), 0.2, 0.26, "void", segs=4, rot=(180, 0, 0))
    k.box((0, 0.15, 1.17), (0.5, 0.3, 0.012), "void", jitter=False)
    # forbidden tomes (the repo draws void_altar as a bookshelf "Forbidden Tomes")
    for i, m in enumerate(("purple", "red_d", "slate")):
        k.box((-0.48, 0.2, 1.2 + i * 0.07), (0.3, 0.22, 0.065), m, rot=(0, 0, i * 12))
    k.box((0.5, 0.1, 1.19), (0.34, 0.26, 0.05), "purple", rot=(0, 0, -15))
    k.box((0.5, 0.1, 1.22), (0.3, 0.22, 0.012), "cream", rot=(0, 0, -15), jitter=False)
    for x in (-0.95, 0.95):                                                           # obelisks
        k.box((x, 0.5, 0.75), (0.24, 0.24, 1.3), "void_stone", taper=0.6)
        k.cone((x, 0.5, 1.4), 0.1, 0.2, "void", segs=4)
    k.collider("altar", (0, 0.1, 0.6), (2.2, 1.4, 1.2))
    k.interact((0, -1.2, 1.0), (1.8, 1.0, 2.0))
    game(k, "void_rift", "the repo's void_altar ('Forbidden Tomes') is an interactable - keep its action",
         ids=["void_altar"])
    k.finish()


def void_crystals():
    k = new_kit("void_crystals", seed=70, title="Void Crystal Cluster", floor="cave", emissive=("void", "void_core"))
    for i in range(7):
        k.rock((math.cos(i) * 0.5, math.sin(i * 1.3) * 0.4, 0.1), (0.3, 0.25, 0.2), "void_stone", subdiv=1, rough=0.25)
    specs = [(0, 0, 1.5, 0.2, 0, "void"), (-0.35, 0.1, 1.0, 0.14, -20, "void"), (0.35, -0.05, 1.15, 0.15, 18, "void"),
             (0.15, 0.35, 0.8, 0.12, 12, "void_core"), (-0.2, -0.3, 0.6, 0.1, -25, "void_core"),
             (0.55, 0.3, 0.55, 0.09, 30, "void"), (-0.6, -0.1, 0.5, 0.09, -35, "void")]
    for (x, y, h, r, tilt, m) in specs:
        rot = (tilt * 0.5, tilt, (x * 90) % 360)
        k.cyl((x, y, 0.05), r, r * 0.9, h * 0.75, m, segs=5, rot=rot)
        from mathutils import Euler, Vector
        top = Vector((0, 0, h * 0.75))
        top.rotate(Euler(tuple(math.radians(a) for a in rot), "XYZ"))
        k.cone((x + top.x, y + top.y, 0.05 + top.z), r * 0.9, h * 0.3, m, segs=5, rot=rot)
    k.disc((0, 0, 0), 0.9, "void_dark", segs=9, z=0.012)
    k.collider("crystals", (0, 0, 0.6), (1.4, 1.2, 1.2))
    game(k, "void_rift")
    k.finish()


# ------------------------------------------------------------------ giant's cavern
def giant_table():
    k = new_kit("giant_table", seed=71, title="Giant's Table", floor="cave")
    L, W, H = 3.6, 1.8, 1.7
    k.box((0, 0, H), (L, W, 0.22), "plank")
    for i in range(4):                                                               # plank seams
        k.box((0, -W / 2 + (i + 0.5) * W / 4, H + 0.112), (L - 0.05, 0.03, 0.01), "wood_d", jitter=False)
    for x in (-1.45, 1.45):
        for y in (-0.65, 0.65):
            k.cyl((x, y, 0), 0.2, 0.17, H - 0.1, "wood", segs=7)                    # log legs
    k.box((0, 0, 0.5), (2.9, 0.16, 0.16), "wood_d")
    k.cyl((-0.7, 0.1, H + 0.11), 0.28, 0.3, 0.55, "wood", segs=8)                   # giant mug
    k.cyl((-0.7, 0.1, H + 0.2), 0.31, 0.31, 0.06, "iron", segs=8, caps=False)
    k.cyl((-0.7, 0.1, H + 0.6), 0.25, 0.25, 0.02, "cream", segs=8)
    k.tube(k.arc_pts((-0.42, 0.1, H + 0.55), (-0.2, 0.1, H + 0.4), (-0.42, 0.1, H + 0.25), 3), [0.05] * 4, "wood", segs=4)
    k.cyl((0.7, -0.1, H + 0.11), 0.55, 0.6, 0.06, "stone_l", segs=9)                 # platter + drumstick
    k.rock((0.65, -0.1, H + 0.35), (0.35, 0.28, 0.22), "leather", subdiv=1, rough=0.1)
    k.tube([(0.95, -0.1, H + 0.3), (1.35, -0.05, H + 0.45)], [0.07, 0.05], "bone", segs=5)
    k.rock((1.38, -0.05, H + 0.46), (0.1, 0.1, 0.09), "bone", subdiv=1, rough=0.1)
    k.box((0.0, 0.55, H + 0.14), (0.9, 0.1, 0.04), "steel", rot=(0, 0, 10))         # huge knife
    k.collider("table", (0, 0, H / 2 + 0.1), (L, W, H + 0.2))
    game(k, "giants_cavern", "tabletop at 1.7 m - taller than the 1.8 m player's chest")
    k.finish()


def giant_throne():
    k = new_kit("giant_throne", seed=72, title="Giant's Throne", floor="cave")
    k.rock((0, 0.1, 0.25), (1.6, 1.3, 0.35), "stone_d", subdiv=1, rough=0.12)       # rough base
    k.box((0, 0.1, 0.85), (1.9, 1.4, 0.9), "stone", taper=0.95)                    # seat block
    k.box((0, 0.75, 2.2), (2.1, 0.5, 3.0), "stone", taper=0.8)                      # back slab
    for x in (-0.75, 0.75):                                                          # horn-like spires
        k.cone((x, 0.78, 3.65), 0.22, 0.75, "stone_d", segs=5, rot=(0, -x * 12, 0))
    for x in (-1.1, 1.1):
        k.box((x, 0.1, 1.55), (0.42, 1.3, 0.5), "stone_d", taper=0.9)                # armrests
        k.skull((x, -0.55, 1.8), 0.34, "bone", "black")
    # masonry seams so the slabs read as stacked blocks, not a grey box
    for z, w in ((1.45, 1.95), (2.25, 1.8), (3.0, 1.62)):
        k.box((0, 0.5 + (z - 0.7) * 0.035, z), (w, 0.03, 0.05), "stone_d", jitter=False)
    k.box((0, -0.61, 0.62), (1.9, 0.03, 0.05), "stone_d", jitter=False)
    k.box((0.45, -0.61, 0.85), (0.05, 0.03, 0.45), "stone_d", jitter=False)
    # bear pelt draped over the back: body, four leg flaps with claws, head over the top edge
    k.box((0, 0.47, 2.35), (1.0, 0.08, 1.45), "fur_grey", taper=0.8, rot=(-4, 0, 0))
    k.box((0, 0.425, 2.35), (0.46, 0.03, 1.15), "fur_dark", rot=(-4, 0, 0), jitter=False)
    for sx in (-1, 1):
        k.box((sx * 0.62, 0.46, 2.85), (0.42, 0.07, 0.2), "fur_grey", rot=(0, sx * -25, 0))   # fore legs
        k.box((sx * 0.6, 0.45, 1.8), (0.42, 0.07, 0.22), "fur_grey", rot=(0, sx * 30, 0))    # hind legs
        for j in range(3):
            k.cone((sx * 0.8, 0.43, 2.72 + 0.06 * j), 0.02, 0.08, "bone", segs=3, rot=(0, sx * 100, 0))
    k.box((0, 0.44, 3.2), (0.5, 0.36, 0.3), "fur_grey")                                  # bear head
    k.box((0, 0.22, 3.15), (0.24, 0.14, 0.16), "fur_grey")
    k.box((0, 0.145, 3.17), (0.1, 0.02, 0.06), "nose", jitter=False)
    for sx in (-1, 1):
        k.box((sx * 0.2, 0.44, 3.4), (0.12, 0.1, 0.12), "fur_dark")
        k.box((sx * 0.11, 0.26, 3.27), (0.05, 0.02, 0.04), "eye", jitter=False)
    # rough fur cushion on the seat + claw-fringed skirt at the front
    k.rock((0, -0.05, 1.33), (0.78, 0.48, 0.08), "fur_dark", subdiv=1, rough=0.15)
    k.box((0, -0.62, 1.08), (1.2, 0.06, 0.42), "fur_dark", rot=(8, 0, 0))
    for i in range(5):
        k.cone((-0.6 + i * 0.3, -0.66, 0.9), 0.05, 0.14, "bone", segs=3, rot=(180, 0, 0))
    k.skull((0.55, -0.9, 0.0), 0.3, "bone", "black", rot=(0, 0, -25))                   # a snack left behind
    k.collider("throne", (0, 0.2, 1.5), (2.7, 1.8, 3.0))
    game(k, "giants_cavern", "seat at 1.3 m, back 4 m - the reference figure shows the giant scale")
    k.finish()


# ------------------------------------------------------------------ wolf den
def wolf_bone_pile():
    k = new_kit("wolf_bone_pile", seed=73, title="Wolf Den Bone Pile", floor="cave")
    k.rock((0, 0, 0.1), (0.9, 0.7, 0.22), "dirt", subdiv=1, rough=0.2)
    rng = k.rng
    for i in range(16):
        a = rng.uniform(0, 6.28)
        r = rng.uniform(0.0, 0.75)
        x, y = math.cos(a) * r, math.sin(a) * r * 0.8
        z = 0.22 - r * 0.2 + rng.uniform(0, 0.06)
        b = rng.uniform(0, 6.28)
        L = rng.uniform(0.25, 0.5)
        bone(k, (x - math.cos(b) * L / 2, y - math.sin(b) * L / 2, z), (x + math.cos(b) * L / 2, y + math.sin(b) * L / 2,
                                                                         z + rng.uniform(-0.05, 0.1)), r=0.03)
    for i in range(3):                                                               # ribcage arcs
        k.tube(k.arc_pts((-0.2 + i * 0.12, -0.25, 0.15), (-0.2 + i * 0.12, 0.0, 0.5), (-0.2 + i * 0.12, 0.25, 0.15), 3),
               [0.025] * 4, "bone", segs=3)
    # deer skull with antlers + wolf-chewed skull
    k.skull((0.45, -0.35, 0.12), 0.26, "bone", "black", rot=(0, 0, -25))
    for sx in (-1, 1):
        k.tube(k.arc_pts((0.45 + sx * 0.08, -0.33, 0.3), (0.45 + sx * 0.3, -0.3, 0.55), (0.45 + sx * 0.25, -0.2, 0.75), 3),
               [0.025, 0.022, 0.018, 0.0], "bone", segs=3)
    k.skull((-0.6, -0.4, 0.05), 0.2, "bone", "black", rot=(0, 0, 40))
    k.disc((0.3, 0.5, 0), 0.25, "red_d", segs=7, z=0.012)
    k.collider("pile", (0, 0, 0.3), (1.8, 1.5, 0.6))
    game(k, "wolf_den")
    k.finish()


def wolf_den_bed():
    k = new_kit("wolf_den_bed", seed=74, title="Wolf Straw Bed", floor="cave")
    n = 12
    for i in range(n):                                                               # straw ring
        a = 2 * math.pi * i / n
        k.rock((math.cos(a) * 0.75, math.sin(a) * 0.6, 0.1), (0.3, 0.2, 0.16), "straw" if i % 3 else "straw_d",
               subdiv=1, rough=0.2)
    k.cyl((0, 0, 0), 0.7, 0.6, 0.08, "straw_d", segs=10, scale=(1, 0.82, 1))
    for i in range(14):                                                              # tufts
        a = k.rng.uniform(0, 6.28)
        r = k.rng.uniform(0.55, 0.95)
        k.cone((math.cos(a) * r, math.sin(a) * r * 0.8, 0.12), 0.03, 0.2, "straw", segs=3,
               rot=(k.rng.uniform(-40, 40), k.rng.uniform(-40, 40), 0))
    # hide scrap + sleeping pup
    k.box((-0.2, 0.1, 0.1), (0.7, 0.5, 0.03), "fur_grey", rot=(0, 0, 18))
    k.rock((0.15, 0.0, 0.2), (0.24, 0.18, 0.13), "fur_grey", subdiv=1, rough=0.08)   # curled pup
    k.box((0.0, -0.12, 0.22), (0.16, 0.14, 0.12), "fur_grey")
    k.box((-0.07, -0.19, 0.2), (0.07, 0.08, 0.05), "fur_white")
    for sx in (-1, 1):
        k.cone((0.0 + sx * 0.05, -0.1, 0.28), 0.03, 0.07, "fur_dark", segs=3)
    k.tube(k.arc_pts((0.35, 0.05, 0.15), (0.3, -0.2, 0.15), (0.12, -0.25, 0.15), 3), [0.05, 0.05, 0.04, 0.02],
           "fur_dark", segs=4)
    bone(k, (0.55, -0.55, 0.03), (0.85, -0.4, 0.03))
    k.collider("bed", (0, 0, 0.15), (1.9, 1.6, 0.3))
    game(k, "wolf_den")
    k.finish()


BUILDERS = {
    "dragon_hoard": dragon_hoard, "dragon_egg_nest": dragon_egg_nest,
    "goblin_campfire": goblin_campfire, "goblin_loot": goblin_loot,
    "crypt_sarcophagus": crypt_sarcophagus, "crypt_candelabra": crypt_candelabra,
    "spider_cocoons": spider_cocoons, "spider_egg_sacs": spider_egg_sacs,
    "void_altar": void_altar, "void_crystals": void_crystals,
    "giant_table": giant_table, "giant_throne": giant_throne,
    "wolf_bone_pile": wolf_bone_pile, "wolf_den_bed": wolf_den_bed,
}

if __name__ == "__main__":
    run(BUILDERS)
