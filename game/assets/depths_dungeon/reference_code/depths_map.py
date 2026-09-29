"""The Depths v2 (crypt descent): map data (reference for Cursor).

Pure data plus a tiny builder, with the same shape as void_dungeon/reference_code/void_map.py,
so the shared v2 dungeon systems (seals, keys, secrets, chests, fog, banners,
boss bar) can load either map.

Grid legend (one char per tile):
  '#' wall            '.' floor            '~' burial pit (blocked, drawn as a bottomless pit)
  '=' bridge          '%' shallow water (walkable, splash decor)   'W' deep water (blocked)
  'A' 'B' 'C' locked doors (blocked until that player unlocks them)
  'X' shortcut gate (blocked until lever 'v' is pulled; persists per player)
  'S' secret wall (loose bricks)   'K' skull-lever niche (a secret wall opened by turning the skull)
  'h' hidden floor (sent as wall until its secret is opened)
  'E' exit            'P' spawn            'H' shrine / checkpoint
  'c' chest           'k' key pedestal     'l' lore note        'g' supply cache
  'v' lever           'Z' sarcophagus (blocked, searchable: loot / ambush / empty)
  'o' candelabrum (blocked)   'i' pew / bone pile / rubble / pillar (blocked)
  'w' warning stone (blocked) '$' ground loot   'b' boss spawn
"""
from __future__ import annotations

W, H = 70, 106

ZONES = [
    ("chapel",    "Ruined Chapel",        "Lv 8–15",  (13, 2, 45, 16),  "chapel"),
    ("ossuary",   "Ossuary Halls",        "Lv 15–34", (5, 17, 59, 34),  "ossuary"),
    ("catacombs", "Flooded Catacombs",    "Lv 36–48", (1, 35, 59, 51),  "catacomb"),
    ("tomb",      "Tomb of the Knights",  "Lv 44–52", (0, 52, 59, 67),  "tomb"),
    ("mausoleum", "Collapsed Mausoleum",  "Lv 55–62", (12, 68, 52, 78), "mausoleum"),
    ("wyrm",      "Wyrm Ossuary",         "Optional · Lv 78", (1, 68, 11, 78), "wyrm"),
    ("stair",     "Sexton's Stair",       "Shortcut", (46, 8, 66, 74), "mausoleum"),
    ("bridge",    "The Bone Bridge",      "Grasping hands", (12, 79, 54, 91), "bridge"),
    ("arena",     "Throne of Bones",      "Boss · Lv 70", (13, 92, 53, 105), "arena"),
]


def _grid():
    return [["#"] * W for _ in range(H)]


def _rect(g, x0, y0, x1, y1, ch="."):
    for y in range(y0, y1 + 1):
        for x in range(x0, x1 + 1):
            g[y][x] = ch


def _put(g, x, y, ch):
    g[y][x] = ch


def build_grid():
    g = _grid()
    # ---- 1 Ruined Chapel ----
    _rect(g, 23, 3, 43, 15)
    _put(g, 33, 2, "E"); _put(g, 33, 4, "P")
    for y in (8, 10, 12):                        # pews either side of the aisle
        _rect(g, 25, y, 30, y, "i"); _rect(g, 36, y, 41, y, "i")
    _put(g, 33, 6, "o"); _put(g, 29, 5, "o"); _put(g, 37, 5, "o")   # altar candles
    _put(g, 24, 14, "g"); _put(g, 42, 14, "l")
    # Secret 1: Sexton's Hidey-hole, loose bricks in the west wall
    _put(g, 22, 9, "S")
    _rect(g, 20, 9, 21, 9, "h"); _rect(g, 14, 6, 19, 12, "h")
    _put(g, 15, 7, "c"); _put(g, 18, 11, "$"); _put(g, 15, 11, "l")
    _rect(g, 32, 16, 34, 18)
    # ---- 2 Ossuary Halls (bone walls) ----
    _rect(g, 28, 19, 38, 26)                     # hub
    _rect(g, 6, 19, 26, 32)                      # west hall
    _rect(g, 40, 19, 58, 32)                     # east hall
    _rect(g, 27, 21, 27, 23); _rect(g, 39, 21, 39, 23)   # archways
    for x, y in ((10, 22), (15, 27), (20, 21), (12, 30), (22, 29), (44, 22), (50, 26), (55, 21), (46, 30), (54, 30)):
        _put(g, x, y, "i")                       # bone piles
    _rect(g, 32, 27, 34, 33)
    _put(g, 7, 20, "c"); _put(g, 25, 31, "l"); _put(g, 57, 31, "$")
    _rect(g, 32, 34, 34, 35, "#"); _put(g, 33, 34, "A"); _put(g, 33, 35, ".")
    # ---- 3 Flooded Catacombs ----
    _rect(g, 8, 36, 56, 50)
    _rect(g, 8, 42, 56, 44, "W")                 # deep channel across the middle
    _rect(g, 8, 41, 56, 41, "%"); _rect(g, 8, 45, 56, 45, "%")   # shallow banks
    for x in (14, 33, 50):                       # three stone crossings
        _rect(g, x - 1, 41, x + 1, 45, ".")
    for x in range(10, 56, 4):                   # burial niches along the walls
        _put(g, x, 36, "i"); _put(g, x, 50, "i")
    _put(g, 55, 37, "c"); _put(g, 31, 48, "g"); _put(g, 10, 48, "l"); _put(g, 44, 38, "$")
    # Secret 2: skull lever niche on the west wall → Drowned Reliquary (key B)
    _put(g, 7, 39, "K")
    _rect(g, 2, 37, 6, 40, "h")
    _put(g, 3, 38, "k"); _put(g, 5, 40, "c"); _put(g, 2, 40, "l")
    _rect(g, 32, 51, 34, 52, "#"); _put(g, 33, 51, "B"); _put(g, 33, 52, ".")
    # ---- 4 Tomb of the Knights ----
    _rect(g, 7, 53, 57, 65)
    for x in range(11, 56, 6):                   # two rows of searchable sarcophagi
        if abs(x - 33) > 2:
            _put(g, x, 56, "Z"); _put(g, x, 62, "Z")
    for x in (9, 21, 45, 55):
        _put(g, x, 59, "o")                      # candelabra down the hall
    _put(g, 56, 54, "l"); _put(g, 31, 64, "g")
    # Secret 3: Aldric's Armoury behind loose bricks, west wall
    _put(g, 6, 59, "S")
    _rect(g, 1, 56, 5, 62, "h")
    _put(g, 2, 57, "c"); _put(g, 4, 61, "$"); _put(g, 2, 61, "l")
    _rect(g, 32, 66, 34, 67, "#"); _put(g, 33, 66, "C"); _put(g, 33, 67, ".")
    # ---- 5 Collapsed Mausoleum ----
    _rect(g, 13, 68, 51, 77)
    for x, y in ((16, 70), (17, 70), (22, 74), (27, 70), (40, 71), (45, 75), (46, 75), (18, 76), (48, 69)):
        _put(g, x, y, "i")                       # fallen masonry
    _put(g, 33, 76, "H"); _put(g, 31, 77, "w"); _put(g, 14, 69, "l"); _put(g, 44, 69, "$")
    _put(g, 50, 72, "v")
    # Optional side lair: the Wyrm Ossuary (keeps today's Adamant Dragon)
    _rect(g, 2, 69, 10, 77); _rect(g, 11, 72, 12, 74)
    _put(g, 3, 76, "c")
    # Shortcut: Sexton's Stair from the Mausoleum lever up to the chapel gate
    _rect(g, 52, 72, 62, 72); _rect(g, 62, 10, 63, 72); _rect(g, 45, 10, 61, 10)
    _put(g, 44, 10, "X")
    _put(g, 63, 30, "l")
    # ---- 6 Burial pit + the Bone Bridge ----
    _rect(g, 12, 79, 54, 91, "~")
    _rect(g, 33, 78, 33, 91, "=")                # 1-wide, 14 tiles
    # ---- 7 Throne of Bones ----
    for y in range(92, 105):
        for x in range(14, 53):
            dx, dy = (x - 33) / 18.0, (y - 98.3) / 6.6
            if dx * dx + dy * dy <= 1.0:
                g[y][x] = "."
    _rect(g, 32, 92, 34, 93)
    for x, y in ((22, 95), (44, 95), (22, 101), (44, 101)):
        _put(g, x, y, "Z")                       # raise-dead sarcophagi (phase 2)
    for x, y in ((18, 98), (48, 98), (33, 103)):
        _put(g, x, y, "o")
    _put(g, 33, 98, "b")
    return g


SPAWNS = [
    # Ruined Chapel: grave-robber goblins and the first skeletons
    ("goblin", 27, 6), ("goblin", 39, 6), ("goblin", 26, 14), ("goblin", 40, 13),
    ("skeleton", 31, 11), ("skeleton", 35, 9), ("skeleton", 24, 4), ("skeleton", 42, 8), ("goblin", 33, 13),
    # Ossuary Halls: skeletons, then big skeletons, mini-boss
    ("skeleton", 9, 25), ("skeleton", 14, 20), ("skeleton", 19, 25), ("skeleton", 23, 22), ("skeleton", 30, 21),
    ("big_skeleton", 43, 25), ("big_skeleton", 48, 20), ("big_skeleton", 53, 24), ("big_skeleton", 57, 27),
    ("skeleton", 11, 30), ("skeleton", 20, 19), ("skeleton", 36, 22), ("big_skeleton", 47, 31), ("big_skeleton", 33, 27),
    ("ossuary_keeper", 51, 29),
    # Flooded Catacombs: rats in the water, drowned dead, a spider brood by the east niches
    ("drowned_dead", 12, 46), ("drowned_dead", 27, 40), ("drowned_dead", 40, 46),
    ("drowned_dead", 16, 38), ("drowned_dead", 26, 38), ("drowned_dead", 38, 47),
    ("drowned_dead", 46, 48), ("drowned_dead", 21, 48),
    ("drowned_dead", 10, 47), ("drowned_dead", 48, 40),
    ("spider", 52, 38), ("spider", 53, 48), ("spider", 55, 45),
    # Tomb of the Knights: barrow knights, and Sir Aldric on the dais
    ("barrow_knight", 14, 59), ("barrow_knight", 26, 58), ("barrow_knight", 40, 60),
    ("barrow_knight", 50, 58), ("barrow_knight", 30, 63),
    ("barrow_knight", 9, 64), ("barrow_knight", 45, 54), ("barrow_knight", 20, 54),
    ("sir_aldric", 51, 64),
    # Collapsed Mausoleum: shades, ghouls
    ("shade", 20, 72), ("shade", 30, 73), ("shade", 38, 69), ("crypt_ghoul", 43, 73), ("crypt_ghoul", 25, 76),
    ("shade", 46, 76), ("shade", 17, 72), ("crypt_ghoul", 35, 71),
    # Optional Wyrm Ossuary: today's Adamant Dragon, unchanged
    ("dragon", 6, 72),
    # Boss
    ("morvath", 33, 98),
]

NO_RESPAWN = {"ossuary_keeper", "sir_aldric", "morvath", "dragon"}

DOORS = {
    "A": (33, 34, "depths_bone_key", "Bone Gate"),
    "B": (33, 51, "depths_tide_key", "Drowned Gate"),
    "C": (33, 66, "depths_knight_seal", "Knights' Seal"),
}

KEYS = {
    "depths_bone_key":    {"source": "drop", "monster": "ossuary_keeper", "chance": 1.0},
    "depths_tide_key":    {"source": "pedestal", "xy": (3, 38), "secret": "reliquary"},
    "depths_knight_seal": {"source": "drop", "monster": "sir_aldric", "chance": 1.0},
}

SECRETS = {
    "hideyhole": {"wall": (22, 9), "kind": "loose_bricks", "reveal": [(20, 9, 21, 9), (14, 6, 19, 12)],
                  "hint": "The mortar here is fresh, and the bricks shift under your hand."},
    "reliquary": {"wall": (7, 39), "kind": "skull_lever", "reveal": [(2, 37, 6, 40)],
                  "hint": "One skull in the niche faces the wrong way. Its eyes catch the light."},
    "armoury":   {"wall": (6, 59), "kind": "loose_bricks", "reveal": [(1, 56, 5, 62)],
                  "hint": "The candle flames lean toward this wall. There's a draught behind it."},
}

LEVER = {"xy": (50, 72), "gate": (44, 10), "flag": "depths_shortcut_open"}

CHESTS = {
    (7, 20): "ossuary_chest", (55, 37): "catacomb_chest", (15, 7): "hideyhole_chest",
    (5, 40): "reliquary_chest", (2, 57): "armoury_chest", (3, 76): "wyrm_chest",
}

# Sarcophagi: rolled once per visit per player. Weights: loot 55, ambush 30, empty (+ lore line) 15.
SARCOPHAGI = [(x, y) for y in (56, 62) for x in range(11, 56, 6) if abs(x - 33) > 2]
SARCOPHAGUS_ROLL = {"loot": 55, "ambush": 30, "empty": 15}
AMBUSH = {"tomb": [("skeleton", 1), ("barrow_knight", 1)]}

SUPPLY_CACHES = [(24, 14), (31, 48), (31, 64)]
GROUND_LOOT = [(18, 11), (57, 31), (44, 38), (4, 61), (44, 69)]
SHRINE = (33, 76)
WARNING_STONE = (31, 77)
BRIDGE = {"x": 33, "y0": 79, "y1": 91, "hazard": "grasping_hands"}
BOSS_SPAWN = (33, 98)
EXIT = (33, 2)
SPAWN = (33, 4)

LORE = {
    (42, 14): ("Chapel Notice", "The Brothers of Saint Vell keep the dead below. Pray, pass quietly, and touch nothing."),
    (15, 11): ("Sexton's Diary", "The Abbot pays in silver to have the old king's bones moved deeper. I dig at night now."),
    (25, 31): ("Bone Wall Inscription", "Ten thousand faithful gave their bones to wall the halls. The Keeper counts them still."),
    (10, 48): ("Waterlogged Page", "The river broke in during the spring flood. The Brothers sealed the tide key behind the skulls."),
    (2, 40):  ("Brother's Confession", "I turned the third skull and hid the key. Let the river keep what the King wants."),
    (56, 54): ("Knight's Epitaph", "Sir Aldric swore to guard King Morvath past death. He keeps the Knights' Seal on his breast."),
    (2, 61):  ("Armourer's Tally", "Blades for the honour guard, sharpened every full moon, though none of them breathe."),
    (14, 69): ("Cracked Tablet", "The Abbot read the forbidden rite over the King. The roof fell. The King rose."),
    (63, 30): ("Sexton's Scratches", "My stair to the chapel. The bar lifts only from below."),
}


def build():
    g = build_grid()
    return {
        "width": W, "height": H, "grid": ["".join(r) for r in g], "zones": ZONES,
        "spawns": SPAWNS, "doors": DOORS, "keys": KEYS, "secrets": SECRETS, "lever": LEVER,
        "chests": {f"{x},{y}": t for (x, y), t in CHESTS.items()},
        "sarcophagi": SARCOPHAGI, "sarcophagus_roll": SARCOPHAGUS_ROLL,
        "supply_caches": SUPPLY_CACHES, "ground_loot": GROUND_LOOT, "shrine": SHRINE,
        "warning_stone": WARNING_STONE, "bridge": BRIDGE, "boss_spawn": BOSS_SPAWN,
        "exit": EXIT, "spawn": SPAWN, "no_respawn": sorted(NO_RESPAWN),
        "lore": {f"{x},{y}": v for (x, y), v in LORE.items()},
    }


if __name__ == "__main__":
    import json, sys
    d = build()
    out = sys.argv[1] if len(sys.argv) > 1 else "depths_map.json"
    with open(out, "w") as f:
        json.dump(d, f, indent=1)
    print("\n".join(d["grid"]))
