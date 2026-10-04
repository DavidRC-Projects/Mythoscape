"""Void Sanctum v2. Map data plus the private-instance builder.

Used only when USE_NEW_VOID_DUNGEON is on. The old Sanctum is untouched.

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


def map_pack():
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


# ---------------------------------------------------------------------------
# Instance builder and handlers. Imported by the server only.
# ---------------------------------------------------------------------------
import random

from world_map import FLOOR, WALL

BLOCKED = set("#~ABCXSoiw")
FLOORISH = set(".=aPEHclg$rbhkv")
PHASE_A = {
    "gallery_warden": "crypt_ghoul",
    "void_crawler": "void_imp",
    "knight_captain_vorn": "shadow_knight",
    "rift_wraith": "shade",
    "nyxarath": "void_horror",
}
KEY_IDS = ("void_key_amethyst", "void_key_obsidian", "void_rift_sigil")
SEAL_HINT = {
    "A": "The Amethyst Seal is locked. Defeat the Gallery Warden for the Amethyst Key, then walk into this door.",
    "B": "The Obsidian Seal is locked. The key is behind the loose bricks on the west wall of the barracks. Walk into this door once you have it.",
    "C": "The Rift Seal is locked. Defeat Knight-Captain Vorn for the Rift Sigil, then walk into this door.",
}
CHEST_LOOT = {
    "gallery_chest": [("coins", (200, 500)), ("super_attack_potion", (1, 1)), ("mithril_arrow", (15, 30))],
    "barracks_chest": [("coins", (300, 700)), ("adamant_chainbody", (1, 1), 0.10), ("cooked_lobster", (2, 4))],
    "crystal_chest": [("coins", (500, 900)), ("onyx", (1, 1)), ("super_defence_potion", (1, 1))],
    "reliquary_chest": [("coins", (400, 400)), (("ruby_ring", "diamond_ring", "ruby_amulet", "diamond_amulet"), (1, 1))],
    "quartermaster_chest": [("adamantite_bar", (2, 4)), ("super_strength_potion", (1, 2)), ("health_potion", (1, 2))],
    "starwell_chest": [("coins", (1500, 1500)), ("void_ring", (1, 1), 0.05), ("void_amulet", (1, 1), 0.04), ("onyx", (2, 2))],
}
GROUND_TABLE = [
    ("coins", (40, 120)),
    ("mithril_arrow", (8, 16)),
    ("ruby", (1, 1)),
    ("coins", (80, 200)),
]
WIND_EVERY = 17   # ~10s at 0.6s ticks
WIND_WARN = 3     # ~2s telegraph
ORB_GAP = 8
ADD_GAP = 33
PULSE_GAP = 10
PYLON_RELIGHT = 20


def _zone_at(x, y):
    hit = None
    for zid, name, band, rect, style in ZONES:
        x0, y0, x1, y1 = rect
        if x0 <= x <= x1 and y0 <= y <= y1:
            if zid == "whisper" and x < 58:
                continue
            hit = (zid, name, band, rect, style)
            if zid != "whisper":
                return hit
    return hit


def _secret_wall_open(x, y, open_secrets):
    for sid in open_secrets:
        if tuple(SECRETS[sid]["wall"]) == (x, y):
            return True
    return False


def _hidden_revealed(x, y, open_secrets):
    for sid in open_secrets:
        for rect in SECRETS[sid]["reveal"]:
            x0, y0, x1, y1 = rect
            if x0 <= x <= x1 and y0 <= y <= y1:
                return True
    return False


def _cell_tile(ch, x, y, opened, open_secrets, gate_open):
    hidden = _in_any_secret(x, y) and not _hidden_revealed(x, y, open_secrets)
    if hidden and not _secret_wall_open(x, y, open_secrets):
        return WALL
    if ch == "S":
        return FLOOR if _secret_wall_open(x, y, open_secrets) else WALL
    if ch in "ABC":
        return FLOOR if ch in opened else WALL
    if ch == "X":
        return FLOOR if gate_open else WALL
    if ch in BLOCKED:
        return WALL
    # Hidden floors stay walled until their secret is opened, then they become a room.
    if ch == "h":
        return FLOOR if _hidden_revealed(x, y, open_secrets) else WALL
    return FLOOR


def _decor_for(ch, x, y, opened, open_secrets, gate_open):
    if ch == "~":
        return "abyss"
    if ch == "=":
        return "bridge"
    if ch == "a":
        return "anchor"
    if ch in "ABC":
        return ("seal_open:" if ch in opened else "seal:") + ch
    if ch == "X" and not gate_open:
        return "gate"
    if ch == "S" and not _secret_wall_open(x, y, open_secrets):
        return "secret"
    if _in_any_secret(x, y) and not _hidden_revealed(x, y, open_secrets):
        return None
    if ch == "o":
        return "pylon"
    if ch == "i":
        return "pillar"
    if ch == "w":
        return "warning"
    if ch == "H":
        return "shrine"
    if ch == "v":
        return "lever"
    if ch == "r":
        return "rift"
    if ch == "c":
        return "chest"
    if ch == "l":
        return "lore"
    if ch == "g":
        return "cache"
    if ch == "$":
        return "loot"
    if ch == "k":
        return "pedestal"
    return None


def _in_any_secret(x, y):
    for spec in SECRETS.values():
        if tuple(spec["wall"]) == (x, y):
            return True
        for rect in spec["reveal"]:
            x0, y0, x1, y1 = rect
            if x0 <= x <= x1 and y0 <= y <= y1:
                return True
    return False


def _bake(chars, opened, open_secrets, gate_open):
    tiles = []
    decor = {}
    for y, row in enumerate(chars):
        out = []
        for x, ch in enumerate(row):
            out.append(_cell_tile(ch, x, y, opened, open_secrets, gate_open))
            kind = _decor_for(ch, x, y, opened, open_secrets, gate_open)
            if kind:
                decor[f"{x},{y}"] = kind
        tiles.append(out)
    return tiles, decor


def _shortcut_open(session):
    row = (getattr(session, "quests", None) or {}).get("void_shortcut") or {}
    return row.get("status") == "complete"


def build(session, next_id, monster_cls, spawns=None):
    """Install a private v2 Sanctum on the session. Spawns arg is ignored."""
    from content import MONSTERS
    pack = map_pack()
    chars = [list(r) for r in pack["grid"]]
    gate = _shortcut_open(session)
    opened = set()
    secrets = set()
    tiles, decor = _bake(chars, opened, secrets, gate)
    monsters = {}
    for mtype, mx, my in SPAWNS:
        if mtype not in MONSTERS:
            mtype = PHASE_A.get(mtype, mtype)
        mid = next_id()
        m = monster_cls(mid, mtype, mx, my, no_respawn=(mtype in NO_RESPAWN or SPAWNS and False))
        real = None
        for raw, rx, ry in SPAWNS:
            if rx == mx and ry == my:
                real = raw
                break
        m.no_respawn = real in NO_RESPAWN
        zone = _zone_at(mx, my)
        if zone:
            m.home_room = zone[3]
        else:
            m.home_room = (mx - 4, my - 4, mx + 4, my + 4)
        m.v2_type = real
        monsters[mid] = m
    ground = {}
    for i, (x, y) in enumerate(GROUND_LOOT):
        item_id, bounds = GROUND_TABLE[i % len(GROUND_TABLE)]
        ground[(x, y)] = [{"item_id": item_id, "qty": random.randint(*bounds)}]
    sx, sy = SPAWN
    ex, ey = EXIT
    session.dungeon = {
        "id": "sanctum",
        "explore": True,
        "v2": True,
        "floor": 1,
        "floors": 1,
        "label": "Void Sanctum",
        "name": "Void Sanctum",
        "tiles": tiles,
        "chars": ["".join(r) for r in chars],
        "decor": decor,
        "width": W,
        "height": H,
        "monsters": monsters,
        "return_x": None,
        "return_y": None,
        "exit_x": ex,
        "exit_y": ey,
        "props": [],
        "opened": [],
        "secrets": [],
        "chests": [],
        "caches": [],
        "pedestal": False,
        "shrine_used": False,
        "checkpoint": None,
        "ground": ground,
        "gate_open": gate,
        "boss": {
            "phase": 1,
            "next_orb": 0,
            "orbs": [],
            "next_add": 0,
            "next_pulse": 0,
            "pylons": {f"{x},{y}": 0 for x, y in ((23, 88), (41, 88), (23, 95), (41, 95))},
            "warned_phase": 1,
        },
        "wind_at": WIND_EVERY,
        "wind_hits": 0,
        "boss_phase": "Umbra",
        "zones": [
            {"id": zid, "name": name, "band": band, "rect": list(rect), "style": style}
            for zid, name, band, rect, style in ZONES
        ],
        "lore": pack["lore"],
    }
    session.x, session.y = sx, sy
    session.in_combat_with = None
    session.gathering_node = None
    if session.pet_id:
        session.pet_x, session.pet_y = session.x, session.y
        session.pet_target_id = None


def client_extra(session):
    d = session.dungeon
    return {
        "v2": True,
        "decor": d.get("decor") or {},
        "zones": d.get("zones") or [],
        "lore": d.get("lore") or {},
        "ground_items": ground_public(d),
        "door_hints": SEAL_HINT,
    }


def ground_public(d):
    tiles = d.get("tiles") or []
    out = {}
    for (x, y), items in (d.get("ground") or {}).items():
        if not items:
            continue
        if 0 <= y < len(tiles) and 0 <= x < len(tiles[y]) and tiles[y][x] == WALL:
            continue
        out[f"{x},{y}"] = items
    return out


def _refresh(d):
    chars = [list(r) for r in d["chars"]]
    tiles, decor = _bake(chars, set(d["opened"]), set(d["secrets"]), d.get("gate_open"))
    d["tiles"] = tiles
    d["decor"] = decor
    return tiles


def _changes_from(before, after):
    changes = []
    for y, row in enumerate(after):
        for x, tile in enumerate(row):
            if before[y][x] != tile:
                changes.append([x, y, tile])
    return changes


def strip_keys(session):
    """Remove Sanctum keys from the inventory and the bank."""
    from content import ITEMS
    changed = False
    for slot in list(session.inventory.keys()):
        entry = session.inventory.get(slot)
        if entry and (ITEMS.get(entry["item_id"]) or {}).get("dungeon_bound"):
            del session.inventory[slot]
            changed = True
    bank = getattr(session, "bank", None) or {}
    for slot in list(bank.keys()):
        entry = bank.get(slot)
        if entry and (ITEMS.get(entry["item_id"]) or {}).get("dungeon_bound"):
            del bank[slot]
            changed = True
    if changed:
        _persist_inventory(session)
    return changed


def _persist_inventory(session):
    from content import INVENTORY_SIZE
    world = _world()
    if world is None or not getattr(session, "player_id", None):
        return
    for slot in range(INVENTORY_SIZE):
        entry = session.inventory.get(slot)
        if entry is None:
            world.db.clear_slot(session.player_id, slot)
        else:
            world.db.add_item_to_slot(session.player_id, slot, entry["item_id"], entry["qty"])


def _world():
    import server as srv
    return getattr(srv, "WORLD", None)


def _has_item(session, item_id):
    return any(e.get("item_id") == item_id for e in session.inventory.values())


def _take_one(session, item_id):
    world = _world()
    if world is None:
        return False
    return world.remove_item_qty(session, item_id, 1)


def _give(session, item_id, qty):
    world = _world()
    if item_id == "coins":
        if world:
            world.add_coins(session, qty)
        return True
    if world and world.add_item_to_inventory(session, item_id, qty):
        return True
    return False


async def try_blocked_step(session, nx, ny):
    """Walking into a seal with the key opens it. Otherwise say what the door wants."""
    import time
    d = session.dungeon
    if not d or not (0 <= ny < d["height"] and 0 <= nx < d["width"]):
        return None
    ch = d["chars"][ny][nx]
    interesting = ch in "ABC" or ch == "S" or any(
        tuple(spec["wall"]) == (nx, ny) for spec in SECRETS.values()
    )
    if not interesting:
        return None
    if ch in "ABC" and ch in d.get("opened", []):
        return None
    now = time.time()
    if getattr(session, "_block_hint_tile", None) == (nx, ny) and now < getattr(session, "_block_hint_at", 0) + 2.5:
        return "blocked"
    session._block_hint_tile = (nx, ny)
    session._block_hint_at = now
    await handle_interact(session, {"x": nx, "y": ny})
    tiles = d.get("tiles") or []
    if 0 <= ny < len(tiles) and 0 <= nx < len(tiles[ny]) and tiles[ny][nx] != WALL:
        return "opened"
    return "blocked"


async def handle_interact(session, msg):
    import server as srv
    d = session.dungeon
    if not d or not d.get("v2"):
        return
    try:
        x, y = int(msg.get("x")), int(msg.get("y"))
    except (TypeError, ValueError):
        return
    if max(abs(session.x - x), abs(session.y - y)) > 1:
        await srv.send(session.ws, "CHAT_MSG", **{"from": "Void Sanctum", "text": "You need to stand next to that."})
        return
    if not (0 <= y < d["height"] and 0 <= x < d["width"]):
        return
    ch = d["chars"][y][x]
    if ch in "ABC" and ch not in d["opened"]:
        key = DOORS[ch][2]
        name = DOORS[ch][3]
        if not _has_item(session, key):
            await srv.send(session.ws, "CHAT_MSG", **{"from": name, "text": SEAL_HINT[ch]})
            return
        _take_one(session, key)
        d["opened"].append(ch)
        srv._save_dungeon_resume(session)
        before = [row[:] for row in d["tiles"]]
        _refresh(d)
        changes = _changes_from(before, d["tiles"])
        await srv.send(session.ws, "DUNGEON_TILES", changes=changes, decor=d["decor"])
        await srv.send(session.ws, "CHAT_MSG", **{"from": name, "text": f"The {name} grinds open."})
        await srv.send(session.ws, "PLAYER_UPDATE", player=session.full_state())
        return
    for sid, spec in SECRETS.items():
        if tuple(spec["wall"]) == (x, y) and sid not in d["secrets"]:
            d["secrets"].append(sid)
            before = [row[:] for row in d["tiles"]]
            _refresh(d)
            changes = _changes_from(before, d["tiles"])
            await srv.send(session.ws, "DUNGEON_TILES", changes=changes, decor=d["decor"])
            await srv.send(session.ws, "CHAT_MSG", **{
                "from": "Void Sanctum",
                "text": "You push the loose stones. A hidden passage grinds open!",
            })
            return
    if ch == "k" and not d.get("pedestal"):
        if not _hidden_revealed(x, y, set(d["secrets"])):
            return
        d["pedestal"] = True
        if _give(session, "void_key_obsidian", 1):
            await srv.send(session.ws, "CHAT_MSG", **{
                "from": "Void Sanctum", "text": "You take the Obsidian Key from the pedestal.",
            })
        else:
            d["pedestal"] = False
            await srv.send(session.ws, "CHAT_MSG", **{"from": "Void Sanctum", "text": "Your inventory is full."})
        await srv.send(session.ws, "PLAYER_UPDATE", player=session.full_state())
        _refresh(d)
        await srv.send(session.ws, "DUNGEON_TILES", changes=[], decor=d["decor"])
        return
    if ch == "c":
        key = f"{x},{y}"
        if key in d["chests"]:
            await srv.send(session.ws, "CHAT_MSG", **{"from": "Void Sanctum", "text": "The chest is empty."})
            return
        table = CHESTS.get((x, y))
        if not table:
            return
        d["chests"].append(key)
        await _grant_table(session, CHEST_LOOT[table])
        _refresh(d)
        d["decor"][key] = "chest_open"
        await srv.send(session.ws, "DUNGEON_TILES", changes=[], decor=d["decor"])
        return
    if ch == "g":
        key = f"{x},{y}"
        if key in d["caches"]:
            await srv.send(session.ws, "CHAT_MSG", **{"from": "Void Sanctum", "text": "The cache is empty."})
            return
        d["caches"].append(key)
        await _grant_table(session, [("cooked_lobster", (3, 3)), ("health_potion", (1, 1))])
        d["decor"][key] = "cache_open"
        await srv.send(session.ws, "DUNGEON_TILES", changes=[], decor=d["decor"])
        return
    if ch == "l":
        title, text = LORE.get((x, y), ("Note", "..."))
        await srv.send(session.ws, "LORE_NOTE", title=title, text=text)
        return
    if ch == "H":
        if d.get("shrine_used"):
            await srv.send(session.ws, "CHAT_MSG", **{"from": "Shrine", "text": "The shrine is dark."})
            return
        d["shrine_used"] = True
        d["checkpoint"] = [x, y]
        heal = max(1, session.max_hp() // 2)
        session.hp = min(session.max_hp(), session.hp + heal)
        await srv.send(session.ws, "CHAT_MSG", **{
            "from": "Shrine", "text": "Warm light knits your wounds. This place will remember you.",
        })
        await srv.send(session.ws, "PLAYER_UPDATE", player=session.full_state())
        return
    if ch == "v":
        if d.get("gate_open"):
            await srv.send(session.ws, "CHAT_MSG", **{"from": "Lever", "text": "The passage is already open."})
            return
        d["gate_open"] = True
        world = _world()
        if world and session.player_id:
            world.db.set_quest_progress(session.player_id, "void_shortcut", "complete", 1)
            session.quests["void_shortcut"] = {"status": "complete", "progress": 1}
        before = [row[:] for row in d["tiles"]]
        _refresh(d)
        changes = _changes_from(before, d["tiles"])
        await srv.send(session.ws, "DUNGEON_TILES", changes=changes, decor=d["decor"])
        await srv.send(session.ws, "CHAT_MSG", **{
            "from": "Lever", "text": "A bar lifts somewhere above. The Whispering Passage is open.",
        })
        return
    if ch == "w":
        await srv.send(session.ws, "WARNING_STONE")
        return


async def _grant_table(session, table):
    import server as srv
    got = []
    for row in table:
        item_id, bounds = row[0], row[1]
        chance = row[2] if len(row) > 2 else 1.0
        if random.random() > chance:
            continue
        if isinstance(item_id, tuple):
            item_id = random.choice(item_id)
        qty = random.randint(bounds[0], bounds[1])
        if _give(session, item_id, qty):
            from content import ITEMS
            name = ITEMS.get(item_id, {}).get("name", item_id)
            got.append(f"{qty}x {name}" if qty > 1 else name)
        else:
            await srv.send(session.ws, "CHAT_MSG", **{"from": "Loot", "text": "Your inventory is full."})
            break
    if got:
        await srv.send(session.ws, "CHAT_MSG", **{"from": "Loot", "text": "Loot: " + ", ".join(got) + "."})
        await srv.send(session.ws, "PLAYER_UPDATE", player=session.full_state())


def place_ground(session, item_id, qty):
    import time
    import feature_flags
    d = session.dungeon
    pile = d["ground"].setdefault((session.x, session.y), [])
    entry = {"item_id": item_id, "qty": qty}
    if feature_flags.USE_REALISTIC_ITEM_ICONS:
        entry["expires_at"] = time.time() + 300
    pile.append(entry)


async def handle_pickup(session, msg):
    import server as srv
    srv.expire_ground_items()
    d = session.dungeon
    pile = d["ground"].get((session.x, session.y)) or []
    if not pile:
        return
    take_all = bool(msg.get("all"))
    want = msg.get("item_id")
    kept = []
    picked = False
    for entry in pile:
        if picked and not take_all:
            kept.append(entry)
            continue
        if want and entry["item_id"] != want and not take_all:
            kept.append(entry)
            continue
        if _give(session, entry["item_id"], entry["qty"]):
            picked = True
            if not take_all:
                continue
        else:
            kept.append(entry)
            break
    if kept:
        d["ground"][(session.x, session.y)] = kept
    else:
        d["ground"].pop((session.x, session.y), None)
    await srv.send(session.ws, "PLAYER_UPDATE", player=session.full_state())


async def vacuum(session, quiet=False):
    """Coins on the dungeon pile underfoot. Other drops stay until clicked."""
    import server as srv
    d = session.dungeon
    pile = d["ground"].get((session.x, session.y))
    if not pile:
        return
    kept = []
    coins = 0
    for entry in pile:
        if entry["item_id"] == "coins":
            _give(session, "coins", entry["qty"])
            coins += entry["qty"]
        else:
            kept.append(entry)
    if kept:
        d["ground"][(session.x, session.y)] = kept
    else:
        d["ground"].pop((session.x, session.y), None)
    if coins and not quiet:
        await srv.send(session.ws, "CHAT_MSG", **{"from": "You", "text": f"You pick up {coins} coins."})


def mitigate(session, monster, dmg):
    """Nyxarath takes half damage while rift adds are alive."""
    d = session.dungeon or {}
    boss_type = d.get("mitigate_boss") or "nyxarath"
    if not d.get("v2") or monster.type != boss_type or dmg <= 0:
        return dmg
    adds = any(
        m.alive and getattr(m, "boss_add", False)
        and (boss_type != "nyxarath" or getattr(m, "v2_type", "") == "void_crawler")
        for m in d["monsters"].values()
    )
    if adds:
        return max(1, dmg // 2)
    return dmg


def process_ai(session):
    """Aggro by range, leash to the zone, respawn when the player is far."""
    import server as srv
    from content import MONSTERS
    from world_map import in_room
    d = session.dungeon
    tiles = d["tiles"]
    monsters = list(d["monsters"].values())

    def walkable(x, y):
        return 0 <= y < len(tiles) and 0 <= x < len(tiles[0]) and tiles[y][x] == FLOOR

    def occupied(nx, ny, me):
        return any(o.alive and o.id != me.id and o.x == nx and o.y == ny for o in monsters)

    def step_toward(m, tx, ty):
        if (m.x, m.y) == (tx, ty):
            return
        dx = 0 if tx == m.x else (1 if tx > m.x else -1)
        dy = 0 if ty == m.y else (1 if ty > m.y else -1)
        order = [(dx, 0), (0, dy)] if abs(tx - m.x) >= abs(ty - m.y) else [(0, dy), (dx, 0)]
        for sx, sy in order:
            if sx == 0 and sy == 0:
                continue
            nx, ny = m.x + sx, m.y + sy
            if (nx, ny) == (session.x, session.y):
                continue
            if m.home_room and not in_room(nx, ny, m.home_room):
                continue
            if not walkable(nx, ny) or occupied(nx, ny, m):
                continue
            m.x, m.y = nx, ny
            return

    eligible = []
    for m in monsters:
        if getattr(m, "concealed", False):
            continue
        if not m.alive:
            _maybe_respawn(session, m)
            continue
        in_area = in_room(session.x, session.y, m.home_room) if m.home_room else True
        dist = max(abs(session.x - m.x), abs(session.y - m.y))
        aggro = int((MONSTERS.get(m.type) or {}).get("aggro_range") or 6)
        if not in_area or dist > aggro:
            if m.target_player_id == session.player_id:
                m.target_player_id = None
            if session.in_combat_with == ("monster", m.id):
                session.in_combat_with = None
            step_toward(m, m.spawn_x, m.spawn_y)
            continue
        eligible.append((dist, m.id, m))
    eligible.sort()
    active = {mid for _d, mid, _m in eligible[:1]}
    closest = None
    for dist, mid, m in eligible:
        if mid not in active:
            if m.target_player_id == session.player_id:
                m.target_player_id = None
            continue
        m.target_player_id = session.player_id
        reach = max(1, int((m.def_stats() or {}).get("attack_range") or 1))
        if dist <= reach and closest is None:
            closest = m.id
        if dist > 1:
            step_toward(m, session.x, session.y)
    if closest is not None:
        session.in_combat_with = ("monster", closest)
    elif session.in_combat_with and session.in_combat_with[0] == "monster":
        current = d["monsters"].get(session.in_combat_with[1])
        if current is None or not current.alive or current.id not in active:
            session.in_combat_with = None


def _maybe_respawn(session, m):
    import server as srv
    from content import MONSTERS
    if m.no_respawn or getattr(m, "v2_type", m.type) in NO_RESPAWN:
        return
    dist = max(abs(session.x - m.spawn_x), abs(session.y - m.spawn_y))
    if dist <= 8:
        m.respawn_at_tick = 0
        return
    if m.respawn_at_tick <= 0:
        base = int((MONSTERS.get(m.type) or {}).get("respawn_ticks") or 50)
        m.respawn_at_tick = srv.WORLD.tick_count + int(base * 1.5)
        return
    if srv.WORLD.tick_count >= m.respawn_at_tick:
        m.alive = True
        m.hp = m.max_hp
        m.x, m.y = m.spawn_x, m.spawn_y
        m.respawn_at_tick = 0
        m.target_player_id = None


async def _nearby_hints(session):
    """Once, when you get close, say how a seal or a loose wall works."""
    import server as srv
    d = session.dungeon
    seen = d.setdefault("hinted", [])
    x, y = session.x, session.y
    for sid, spec in SECRETS.items():
        if sid in d.get("secrets") or sid in seen:
            continue
        wx, wy = spec["wall"]
        if max(abs(x - wx), abs(y - wy)) <= 2:
            seen.append(sid)
            await srv.send(session.ws, "CHAT_MSG", **{
                "from": "Void Sanctum",
                "text": spec["hint"] + " Click the cracked wall, or walk into it.",
            })
            return
    for ch, (dx, dy, key, name) in DOORS.items():
        if ch in d.get("opened") or ch in seen:
            continue
        if max(abs(x - dx), abs(y - dy)) > 2:
            continue
        seen.append(ch)
        if _has_item(session, key):
            text = f"The {name} recognises the key in your pack. Walk into the door."
        else:
            text = SEAL_HINT[ch]
        await srv.send(session.ws, "CHAT_MSG", **{"from": name, "text": text})
        return


async def tick_sessions():
    import server as srv
    for session in list(srv.WORLD.sessions.values()):
        d = session.dungeon
        if not d or d.get("v2") is not True:
            continue
        await _nearby_hints(session)
        await _wind(session)
        await _boss(session)


async def _wind(session):
    import server as srv
    d = session.dungeon
    tick = srv.WORLD.tick_count
    if tick < d.get("wind_at", 0) - WIND_WARN:
        return
    if tick == d.get("wind_at", 0) - WIND_WARN:
        await srv.send(session.ws, "VOID_WIND", warn=True)
        await srv.send(session.ws, "CHAT_MSG", **{"from": "The Rift", "text": "The void wind rises."})
        return
    if tick < d.get("wind_at", 0):
        return
    d["wind_at"] = tick + WIND_EVERY
    x, y = session.x, session.y
    if not (0 <= y < H and 0 <= x < W):
        return
    if d["chars"][y][x] != "=":
        return
    session.hp = max(0, session.hp - 8)
    for _ in range(2):
        ny = y - 1
        if ny < 0 or d["tiles"][ny][x] != FLOOR:
            break
        y = ny
    session.y = y
    await srv.send(session.ws, "VOID_WIND", warn=False, x=session.x, y=session.y, hp=session.hp)
    await srv.send(session.ws, "CHAT_MSG", **{"from": "The Rift", "text": "The wind shoves you back along the bridge."})
    await srv.send(session.ws, "PLAYER_UPDATE", player=session.full_state())
    if session.hp <= 0:
        await _downed(session)


async def _downed(session):
    import server as srv
    stayed = await on_death(session)
    if stayed:
        return
    await srv.handle_leave_dungeon(session, silent=True)
    await srv.send(session.ws, "CHAT_MSG", **{
        "from": "Void Sanctum",
        "text": "You fall in the sanctum and wake outside. The dark keeps what you carried.",
    })


async def _boss(session):
    import server as srv
    from world_map import in_room
    d = session.dungeon
    boss = None
    for m in d["monsters"].values():
        if getattr(m, "v2_type", m.type) == "nyxarath":
            boss = m
            break
    if boss is None:
        return
    arena = (14, 85, 50, 98)
    if not in_room(session.x, session.y, arena):
        if boss.hp < boss.max_hp or not boss.alive:
            boss.alive = True
            boss.hp = boss.max_hp
            boss.x, boss.y = boss.spawn_x, boss.spawn_y
            boss.target_player_id = None
            d["boss"]["phase"] = 1
            d["boss_phase"] = "Umbra"
            for m in list(d["monsters"].values()):
                if getattr(m, "boss_add", False):
                    m.alive = False
        return
    if not boss.alive:
        d["boss_phase"] = ""
        return
    ratio = boss.hp / max(1, boss.max_hp)
    phase = 1 if ratio > 0.66 else (2 if ratio > 0.33 else 3)
    names = {1: "Umbra", 2: "Rift Tide", 3: "Eclipse"}
    d["boss"]["phase"] = phase
    d["boss_phase"] = names[phase]
    tick = srv.WORLD.tick_count
    state = d["boss"]
    # Resolve orbs whose telegraph has elapsed.
    still = []
    for orb in state["orbs"]:
        if tick >= orb["at"]:
            if (session.x, session.y) in [tuple(p) for p in orb["tiles"]]:
                session.hp = max(0, session.hp - 25)
                await srv.send(session.ws, "CHAT_MSG", **{"from": "Nyxarath", "text": "An umbral orb bursts under you."})
                await srv.send(session.ws, "PLAYER_UPDATE", player=session.full_state())
        else:
            still.append(orb)
    state["orbs"] = still
    if tick >= state["next_orb"]:
        tiles = []
        for _ in range(3):
            tiles.append([session.x + random.randint(-2, 2), session.y + random.randint(-2, 2)])
        state["orbs"].append({"tiles": tiles, "at": tick + WIND_WARN})
        state["next_orb"] = tick + ORB_GAP
        await srv.send(session.ws, "BOSS_TELEGRAPH", tiles=tiles, at=tick + WIND_WARN)
    if phase >= 2 and tick >= state["next_add"]:
        alive_adds = [m for m in d["monsters"].values() if getattr(m, "boss_add", False) and m.alive]
        if len(alive_adds) < 2:
            for px, py in ((19, 91), (45, 91)):
                if len([m for m in d["monsters"].values() if getattr(m, "boss_add", False) and m.alive]) >= 2:
                    break
                mid = srv.next_id()
                m = srv.MonsterInstance(mid, "void_crawler", px, py)
                m.home_room = arena
                m.boss_add = True
                m.no_respawn = True
                m.v2_type = "void_crawler"
                d["monsters"][mid] = m
        state["next_add"] = tick + ADD_GAP
    if phase >= 3 and tick >= state["next_pulse"]:
        safe = False
        for key, relight in state["pylons"].items():
            if relight and tick < relight:
                continue
            px, py = (int(n) for n in key.split(","))
            if max(abs(session.x - px), abs(session.y - py)) <= 1:
                safe = True
                break
        if not safe:
            session.hp = max(0, session.hp - 30)
            await srv.send(session.ws, "CHAT_MSG", **{"from": "Nyxarath", "text": "The eclipse pulse finds you in the dark."})
            await srv.send(session.ws, "PLAYER_UPDATE", player=session.full_state())
        lit = [k for k, rel in state["pylons"].items() if not rel or tick >= rel]
        if lit:
            snuff = random.choice(lit)
            state["pylons"][snuff] = tick + PYLON_RELIGHT
        state["next_pulse"] = tick + PULSE_GAP
    if session.hp <= 0:
        await _downed(session)


def hud_state(d, tick):
    boss = d.get("boss") or {}
    pylons = []
    for key, relight in (boss.get("pylons") or {}).items():
        x, y = key.split(",")
        pylons.append({"x": int(x), "y": int(y), "lit": not relight or tick >= relight})
    return {"boss_phase": d.get("boss_phase") or "", "pylons": pylons}


async def on_death(session):
    """Strip keys. Past the shrine, wake at the checkpoint instead of outside."""
    import server as srv
    strip_keys(session)
    _persist_inventory(session)
    d = session.dungeon
    point = d.get("checkpoint") if d else None
    if not point:
        return False
    session.hp = session.max_hp()
    session.x, session.y = int(point[0]), int(point[1])
    session.in_combat_with = None
    session.coins = 0
    await srv.send(session.ws, "CHAT_MSG", **{
        "from": "Shrine", "text": "You wake at the shrine. The keys you carried are gone.",
    })
    await srv.send(session.ws, "PLAYER_UPDATE", player=session.full_state())
    return True


async def announce_first_kill(session):
    import server as srv
    row = (session.quests or {}).get("void_nyxarath") or {}
    if row.get("status") == "complete":
        return
    if session.player_id:
        srv.WORLD.db.set_quest_progress(session.player_id, "void_nyxarath", "complete", 1)
        session.quests["void_nyxarath"] = {"status": "complete", "progress": 1}
    text = f"{session.char_name} has slain Nyxarath, the Hollow Eclipse!"
    for s in srv.WORLD.sessions.values():
        await srv.send(s.ws, "CHAT_MSG", **{"from": "Void Sanctum", "text": text, "style": "gold"})
