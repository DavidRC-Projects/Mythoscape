"""Void Sanctum v2 — map data (reference for Cursor).

Pure data + a tiny builder. No game imports. `build()` returns a dict that
explore_dungeons can turn into a private instance when USE_NEW_VOID_DUNGEON=1.

Grid legend (one char per tile):
  '#' wall            '.' floor             '~' abyss (blocked, drawn as void)
  '=' bridge floor    'a' bridge anchor (walkable, safe from void wind)
  'A' 'B' 'C' locked doors (blocked until that player unlocks them)
  'X' shortcut gate (blocked until the player pulls lever 'v'; persists per player)
  'S' secret wall (cracked hint; blocked until searched)
  'h' hidden floor (sent to the client as wall until its secret is opened)
  'E' exit portal     'P' player spawn      'H' healing shrine / checkpoint
  'c' chest           'k' key pedestal      'l' lore note     'g' supply cache
  'v' lever           'o' eclipse pylon (blocked)   'i' crystal / rubble pillar (blocked)
  'w' warning stone (blocked)  '$' ground loot pile  'r' rift pool (walkable decor)
  'b' boss spawn
"""
from __future__ import annotations

W, H = 66, 100

ZONES = [
    # id, banner name, level band, rect (x0, y0, x1, y1) inclusive, floor style
    ("entry",     "Entry Hall",          "Lv 50s", (12, 2, 41, 14),  "entry"),
    ("galleries", "Shattered Galleries", "Lv 60s", (4, 15, 60, 32),  "gallery"),
    ("barracks",  "Hollow Barracks",     "Lv 70s", (2, 33, 56, 48),  "barracks"),
    ("crystal",   "Crystal Depths",      "Lv 80s", (2, 49, 60, 61),  "crystal"),
    ("rift",      "The Rift Edge",       "Lv 90s", (10, 62, 64, 72), "rift"),
    ("whisper",   "Whispering Passage",  "Shortcut", (41, 7, 64, 66), "rift"),
    ("bridge",    "The Narrow Way",      "Void wind", (12, 73, 52, 84), "bridge"),
    ("arena",     "Eclipse Throne",      "Boss · Lv 110", (14, 85, 50, 98), "arena"),
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
    # ---- Entry Hall (exit at the top, like today) ----
    _rect(g, 24, 3, 40, 13)
    _put(g, 32, 2, "E")
    _put(g, 32, 4, "P")
    for x, y in ((26, 5), (38, 5), (26, 11), (38, 11)):
        _put(g, x, y, "i")               # broken pillars
    _put(g, 25, 12, "g")                  # supply cache
    _put(g, 39, 12, "l")                  # lore 1
    # Secret 1: Hidden Reliquary behind the west wall
    _put(g, 23, 8, "S")
    _rect(g, 20, 8, 22, 8, "h")
    _rect(g, 13, 5, 19, 11, "h")
    _put(g, 15, 6, "c"); _put(g, 17, 10, "$"); _put(g, 14, 10, "l")
    # ---- corridor down ----
    _rect(g, 31, 14, 33, 17)
    # ---- Shattered Galleries ----
    _rect(g, 27, 18, 37, 24)              # hub
    _rect(g, 5, 18, 26, 30)               # west gallery
    _rect(g, 38, 18, 57, 30)              # east gallery
    _rect(g, 26, 18, 26, 30, "#"); _rect(g, 38, 18, 38, 30, "#")   # gallery walls
    _rect(g, 26, 20, 26, 22); _rect(g, 38, 20, 38, 22)            # archways
    for x, y in ((9, 21), (10, 21), (15, 25), (20, 20), (21, 28), (12, 28),
                 (43, 21), (48, 25), (49, 25), (54, 20), (53, 28), (44, 28)):
        _put(g, x, y, "i")
    _rect(g, 27, 25, 30, 30, "#"); _rect(g, 34, 25, 37, 30, "#")
    _rect(g, 31, 25, 33, 30)              # corridor to door A
    _put(g, 6, 19, "c"); _put(g, 24, 29, "l"); _put(g, 56, 29, "$")
    # ---- Door A (Amethyst Key from the Gallery Warden) ----
    _rect(g, 31, 31, 33, 32, "#"); _put(g, 32, 31, "A"); _put(g, 32, 32, ".")
    # ---- Hollow Barracks ----
    _rect(g, 10, 33, 54, 33, "#")
    for cx0 in range(11, 50, 7):          # bunk cells along the north wall
        _rect(g, cx0, 34, cx0 + 5, 37)
    _rect(g, 10, 39, 54, 46)              # main hall
    for cx0 in range(11, 50, 7):
        _put(g, cx0 + 2, 38, ".")         # cell doorways
    _rect(g, 31, 33, 33, 38)              # entrance from door A
    _put(g, 12, 35, "$"); _put(g, 50, 35, "c"); _put(g, 30, 45, "g"); _put(g, 46, 45, "l")
    for x in (18, 25, 39, 46):
        _put(g, x, 42, "i")               # weapon racks / rubble
    # Secret 2: Quartermaster's Cache, west wall (holds the Obsidian Key)
    _put(g, 9, 42, "S")
    _rect(g, 3, 39, 8, 45, "h")
    _put(g, 5, 42, "k"); _put(g, 4, 40, "c"); _put(g, 7, 44, "l")
    # ---- Door B (Obsidian Key) ----
    _rect(g, 31, 47, 33, 48, "#"); _put(g, 32, 47, "B"); _put(g, 32, 48, ".")
    # ---- Crystal Depths ----
    _rect(g, 4, 49, 58, 59)
    for x, y in ((8, 51), (14, 57), (19, 52), (23, 55), (27, 51), (37, 51), (41, 56),
                 (46, 52), (50, 57), (54, 51), (57, 55), (11, 54)):
        _put(g, x, y, "i")
    _rect(g, 4, 49, 12, 50, "#"); _rect(g, 50, 49, 58, 50, "#")
    _put(g, 5, 58, "l"); _put(g, 57, 58, "c"); _put(g, 30, 53, "g")
    # Secret 3: The Starwell, south wall (lore finale + rare chest)
    _put(g, 45, 60, "S")
    _rect(g, 45, 61, 45, 61, "h")
    _rect(g, 43, 62, 48, 64, "h")         # small vault under the depths
    _put(g, 44, 63, "c"); _put(g, 47, 63, "l")
    # ---- Door C (Rift Sigil from Knight-Captain Vorn) ----
    _rect(g, 31, 60, 33, 61, "#"); _put(g, 32, 60, "C"); _put(g, 32, 61, ".")
    # ---- Rift Edge ----
    _rect(g, 14, 62, 40, 71)
    _rect(g, 41, 66, 50, 71)
    for x, y in ((17, 64), (22, 67), (37, 64), (27, 69), (44, 68)):
        _put(g, x, y, "i")
    _put(g, 32, 70, "H")                  # healing shrine / checkpoint
    _put(g, 30, 71, "w")                  # boss warning stone
    _put(g, 15, 70, "l"); _put(g, 39, 63, "$")
    # Shortcut: lever at the Rift Edge opens the gate into the Entry Hall
    _put(g, 49, 67, "v")
    _rect(g, 51, 67, 60, 67)              # east spur
    _rect(g, 60, 9, 61, 67)               # Whispering Passage (north)
    _rect(g, 42, 9, 59, 9)                # back to the Entry Hall
    _put(g, 41, 9, "X")                   # gate (opens from the far side only)
    _put(g, 61, 30, "l"); _put(g, 61, 50, "l")
    # ---- Abyss + the Narrow Way ----
    _rect(g, 12, 72, 52, 84, "~")
    _rect(g, 32, 72, 32, 84, "=")         # 1-wide bridge, 13 tiles
    for y in (75, 79, 83):
        _put(g, 32, y, "a"); _put(g, 31, y, "a")   # 2-wide rune anchors
    # ---- Boss arena ----
    for y in range(85, 98):
        for x in range(15, 50):
            dx, dy = (x - 32) / 17.0, (y - 91.5) / 6.8
            if dx * dx + dy * dy <= 1.0:
                g[y][x] = "."
    _rect(g, 31, 85, 33, 86)
    for x, y in ((23, 88), (41, 88), (23, 95), (41, 95)):
        _put(g, x, y, "o")                # eclipse pylons (light-safe zones in phase 3)
    for x, y in ((19, 91), (45, 91)):
        _put(g, x, y, "r")                # rift pools (phase 2 adds)
    _put(g, 32, 92, "b")
    return g


# Monster spawns: (type, x, y). New types are defined in NEW_MONSTERS.
SPAWNS = [
    # Entry Hall — Lv 55
    ("shade", 28, 7), ("shade", 36, 7), ("shade", 30, 10), ("shade", 35, 11), ("shade", 33, 8),
    # Shattered Galleries — Lv 62 (+ mini-boss 68)
    ("crypt_ghoul", 8, 24), ("crypt_ghoul", 14, 20), ("crypt_ghoul", 19, 26), ("crypt_ghoul", 24, 22),
    ("crypt_ghoul", 41, 24), ("crypt_ghoul", 46, 19), ("crypt_ghoul", 52, 23), ("crypt_ghoul", 57, 26),
    ("gallery_warden", 51, 28),
    # Hollow Barracks — Lv 70 / 78
    ("void_imp", 14, 36), ("void_imp", 21, 35), ("void_imp", 15, 41), ("void_imp", 22, 44),
    ("void_imp", 28, 40), ("void_imp", 36, 44),
    ("obsidian_colossus", 40, 40), ("obsidian_colossus", 44, 44), ("obsidian_colossus", 50, 41),
    ("obsidian_colossus", 42, 36),
    # Crystal Depths — Lv 82 / 88 (+ mini-boss 92)
    ("void_crawler", 16, 53), ("void_crawler", 21, 58), ("void_crawler", 34, 56),
    ("void_crawler", 44, 54), ("void_crawler", 52, 55),
    ("shadow_knight", 25, 57), ("shadow_knight", 30, 50), ("shadow_knight", 39, 58),
    ("shadow_knight", 48, 51), ("shadow_knight", 55, 57),
    ("knight_captain_vorn", 8, 56),
    # Rift Edge — Lv 91 / 95
    ("rift_wraith", 18, 66), ("rift_wraith", 26, 64), ("rift_wraith", 35, 67), ("rift_wraith", 45, 69),
    ("void_horror", 21, 69), ("void_horror", 30, 65), ("void_horror", 38, 69),
    # Boss
    ("nyxarath", 32, 92),
]

# Mini-bosses and the boss never respawn during a visit.
NO_RESPAWN = {"gallery_warden", "knight_captain_vorn", "nyxarath"}

DOORS = {
    # door char: (x, y, key item id, name)
    "A": (32, 31, "void_key_amethyst", "Amethyst Seal"),
    "B": (32, 47, "void_key_obsidian", "Obsidian Seal"),
    "C": (32, 60, "void_rift_sigil", "Rift Seal"),
}

KEYS = {
    "void_key_amethyst": {"source": "drop", "monster": "gallery_warden", "chance": 1.0},
    "void_key_obsidian": {"source": "pedestal", "xy": (5, 42), "secret": "quartermaster"},
    "void_rift_sigil":   {"source": "drop", "monster": "knight_captain_vorn", "chance": 1.0},
}

SECRETS = {
    # id: wall tile, hidden tiles rect(s), hint text
    "reliquary":    {"wall": (23, 8),  "reveal": [(20, 8, 22, 8), (13, 5, 19, 11)],
                     "hint": "A draught whistles through a crack in the stone."},
    "quartermaster": {"wall": (9, 42), "reveal": [(3, 39, 8, 45)],
                     "hint": "These bricks are newer than the rest… and loose."},
    "starwell":     {"wall": (45, 60), "reveal": [(45, 61, 45, 61), (43, 62, 48, 64)],
                     "hint": "Faint starlight leaks from beneath the crystal."},
}

LEVER = {"xy": (49, 67), "gate": (41, 9), "flag": "void_shortcut_open"}

CHESTS = {
    # xy: loot table id (rolled once per player per visit)
    (6, 19): "gallery_chest", (50, 35): "barracks_chest", (57, 58): "crystal_chest",
    (15, 6): "reliquary_chest", (4, 40): "quartermaster_chest", (44, 63): "starwell_chest",
}

SUPPLY_CACHES = [(25, 12), (30, 45), (30, 53)]   # food + potions, once per visit
GROUND_LOOT = [(17, 10), (56, 29), (12, 35), (39, 63)]
SHRINE = (32, 70)
WARNING_STONE = (30, 71)
BRIDGE = {"x": 32, "y0": 72, "y1": 84, "anchors": [75, 79, 83]}
BOSS_SPAWN = (32, 92)
EXIT = (32, 2)
SPAWN = (32, 4)

LORE = {
    (39, 12): ("Warden's Notice", "By order of the Circle: none pass the Amethyst Seal without the Warden's leave."),
    (14, 10): ("Pilgrim's Scrap", "We hid the relics here when the sky went black at noon. May the Eclipse never find them."),
    (24, 29): ("Shattered Plaque", "Here the Circle of Selwyn first opened the Rift, to draw power from the dark between stars."),
    (46, 45): ("Barracks Roster", "Night watch: 12. Day watch: 12. Returned from the Depths: 3. They do not sleep now."),
    (7, 44):  ("Quartermaster's Ledger", "Obsidian key kept behind the loose bricks. The Captain must never have it."),
    (5, 58):  ("Crystal-etched Journal", "Captain Vorn hears it too. He carries the Rift Sigil and will not let it go."),
    (47, 63): ("Selwyn's Last Page", "It is not a god. It is a hunger shaped like an eclipse: Nyxarath. We fed it our light."),
    (15, 70): ("Pilgrim's Warning", "Rest at the shrine. Cross on the runes. The wind obeys the one on the throne."),
    (61, 30): ("Scratched Wall", "This passage leads back to the gate. Only the far side can lift the bar."),
    (61, 50): ("Scratched Wall", "Counted the gusts: one every ten breaths. Stand on the runes."),
}


def build():
    g = build_grid()
    return {
        "width": W, "height": H, "grid": ["".join(r) for r in g], "zones": ZONES,
        "spawns": SPAWNS, "doors": DOORS, "keys": KEYS, "secrets": SECRETS, "lever": LEVER,
        "chests": {f"{x},{y}": t for (x, y), t in CHESTS.items()},
        "supply_caches": SUPPLY_CACHES, "ground_loot": GROUND_LOOT, "shrine": SHRINE,
        "warning_stone": WARNING_STONE, "bridge": BRIDGE, "boss_spawn": BOSS_SPAWN,
        "exit": EXIT, "spawn": SPAWN,
        "lore": {f"{x},{y}": v for (x, y), v in LORE.items()},
    }


if __name__ == "__main__":
    import json, sys
    d = build()
    out = sys.argv[1] if len(sys.argv) > 1 else "void_map.json"
    with open(out, "w") as f:
        json.dump(d, f, indent=1)
    print("\n".join(d["grid"]))
