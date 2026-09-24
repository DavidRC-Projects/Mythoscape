"""
Tidehollow Cave — private 10-floor instance dungeon by Harbourreach.

Floors scale combat level 10 → 80. Creature count shrinks each floor.
Clear every monster to advance; finish floor 10 for a high-value reward,
the Tidehollow Medal, and a golden chat announcement outside.
"""
from __future__ import annotations

import random

from world_map import WALL, FLOOR, is_walkable as _world_walkable

# Floor combat levels (1..10) and spawn counts (fewer, harder deeper)
TIDEHOLLOW_FLOORS = [
    {"floor": 1, "level": 10, "count": 12, "label": "Dripping Halls"},
    {"floor": 2, "level": 18, "count": 11, "label": "Salted Tunnels"},
    {"floor": 3, "level": 26, "count": 10, "label": "Barnacle Gallery"},
    {"floor": 4, "level": 34, "count": 9, "label": "Echoing Grotto"},
    {"floor": 5, "level": 42, "count": 8, "label": "Blackwater Bend"},
    {"floor": 6, "level": 49, "count": 7, "label": "Kraken's Teeth"},
    {"floor": 7, "level": 57, "count": 6, "label": "Abyss Antechamber"},
    {"floor": 8, "level": 65, "count": 5, "label": "Pearl Vault"},
    {"floor": 9, "level": 72, "count": 4, "label": "Sunken Throne"},
    {"floor": 10, "level": 80, "count": 3, "label": "Tidehollow Heart"},
]

DUNGEON_W, DUNGEON_H = 28, 22
DUNGEON_SPAWN = (14, 19)
CAVE_RETURN = (138, 3)  # just south of the cave mouth

# Visual monster type by floor band (uses existing drawers)
_FLOOR_VISUAL = {
    1: "goblin", 2: "goblin",
    3: "skeleton", 4: "skeleton",
    5: "wolf", 6: "wolf",
    7: "spider", 8: "spider",
    9: "big_skeleton", 10: "dragon",
}

TIDEHOLLOW_REWARDS = [
    ("mythos_dagger", 1),
    ("mythos_longsword", 1),
    ("mythos_helmet", 1),
    ("mythos_legs", 1),
    ("mythos_shield", 1),
    ("adamant_sword", 1),
    ("adamant_body", 1),
    ("adamant_battleaxe", 1),
    ("mithril_body", 1),
    ("coins", (2500, 6000)),
    ("health_potion", (4, 8)),
    ("super_attack_potion", (2, 4)),
    ("super_strength_potion", (2, 4)),
]


def roll_kill_loot(floor: int, level: int):
    """Per-kill drops inside Tidehollow — scales with floor depth.

    Returns a list of (item_id, qty) tuples (may be empty).
    """
    floor = max(1, int(floor))
    level = max(1, int(level))
    out = []
    # Coins always (more on deeper floors)
    coin_lo = 8 + floor * 6
    coin_hi = 18 + floor * 14
    out.append(("coins", random.randint(coin_lo, coin_hi)))
    # Food / potions — keep runs sustainable
    if random.random() < min(0.55, 0.22 + floor * 0.03):
        food = "cooked_trout" if floor < 5 else ("cooked_salmon" if floor < 8 else "cooked_lobster")
        out.append((food, random.randint(1, 2)))
    if random.random() < min(0.35, 0.10 + floor * 0.025):
        out.append(("health_potion", 1))
    # Fletching / smith scraps
    if random.random() < 0.28:
        out.append(("feather", random.randint(2, 6 + floor)))
    if random.random() < 0.18:
        out.append(("arrow_shaft", random.randint(3, 8 + floor)))
    if random.random() < min(0.30, 0.08 + floor * 0.02):
        if floor >= 8:
            tip = "mithril_arrowtips"
        elif floor >= 5:
            tip = "steel_arrowtips"
        elif floor >= 3:
            tip = "iron_arrowtips"
        else:
            tip = "bronze_arrowtips"
        out.append((tip, random.randint(3, 8)))
    if random.random() < min(0.22, 0.05 + floor * 0.015):
        arrow = "bronze_arrow" if floor < 4 else ("iron_arrow" if floor < 7 else "steel_arrow")
        out.append((arrow, random.randint(4, 12)))
    # Occasional ore / bar tease on mid+ floors
    if floor >= 4 and random.random() < 0.12:
        ore = "iron_ore" if floor < 7 else ("mithril_ore" if floor < 9 else "adamantite_ore")
        out.append((ore, random.randint(1, 2)))
    if floor >= 6 and random.random() < 0.06:
        out.append(("bow_string", random.randint(1, 2)))
    return out


def floor_info(floor: int) -> dict:
    for entry in TIDEHOLLOW_FLOORS:
        if entry["floor"] == floor:
            return entry
    return TIDEHOLLOW_FLOORS[-1]


def scaled_monster_stats(level: int) -> dict:
    """Rough combat stats for a given combat level."""
    hp = max(12, int(level * 2.2))
    att = max(3, int(level * 0.72))
    strength = max(3, int(level * 0.75))
    defence = max(2, int(level * 0.62))
    return {
        "level": level,
        "hp": hp,
        "attack": att,
        "strength": strength,
        "defence": defence,
        "def_bonus": max(0, level // 5),
        "xp": max(20, int(level * 4.5)),
        "name": f"Cavern Beast (lvl {level})",
    }


def generate_floor_tiles(floor: int, rng=None):
    """Larger cave chamber — wall shell, floor interior, rock pillars, side alcoves."""
    rng = rng or random.Random(floor * 7919 + 17)
    w, h = DUNGEON_W, DUNGEON_H
    tiles = [[WALL for _ in range(w)] for _ in range(h)]
    for y in range(1, h - 1):
        for x in range(1, w - 1):
            tiles[y][x] = FLOOR
    # Carve a few side alcoves for 3D corridor read
    for _ in range(3 + floor // 3):
        ax = rng.randint(3, w - 4)
        ay = rng.randint(3, h - 5)
        aw = rng.randint(2, 4)
        ah = rng.randint(2, 3)
        for yy in range(ay, min(h - 2, ay + ah)):
            for xx in range(ax, min(w - 2, ax + aw)):
                tiles[yy][xx] = FLOOR
    # Pillars / clutter (never block spawn)
    sx, sy = DUNGEON_SPAWN
    for _ in range(6 + floor // 2):
        x = rng.randint(3, w - 4)
        y = rng.randint(3, h - 4)
        if abs(x - sx) + abs(y - sy) < 4:
            continue
        tiles[y][x] = WALL
        if rng.random() < 0.45 and tiles[y][x + 1] == FLOOR:
            tiles[y][x + 1] = WALL
        if rng.random() < 0.3 and tiles[y + 1][x] == FLOOR:
            tiles[y + 1][x] = WALL
    # Ensure spawn walkable
    tiles[sy][sx] = FLOOR
    for dx, dy in ((0, -1), (0, -2), (0, -3), (-1, 0), (1, 0), (0, 1), (-1, -1), (1, -1)):
        nx, ny = sx + dx, sy + dy
        if 0 <= nx < w and 0 <= ny < h:
            tiles[ny][nx] = FLOOR
    # Southern exit mouth on the wall (must not equal spawn)
    for y in range(sy, h - 1):
        tiles[y][sx] = FLOOR
        if sx > 0:
            tiles[y][sx - 1] = FLOOR
        if sx < w - 1:
            tiles[y][sx + 1] = FLOOR
    tiles[h - 1][sx] = FLOOR
    if sx > 0:
        tiles[h - 1][sx - 1] = FLOOR
    if sx < w - 1:
        tiles[h - 1][sx + 1] = FLOOR
    return tiles


def dungeon_walkable(tiles, x, y) -> bool:
    if not tiles or y < 0 or y >= len(tiles) or x < 0 or x >= len(tiles[0]):
        return False
    return tiles[y][x] == FLOOR


def pick_spawn_tiles(tiles, count, rng=None):
    rng = rng or random
    spots = [
        (x, y)
        for y, row in enumerate(tiles)
        for x, t in enumerate(row)
        if t == FLOOR and (x, y) != DUNGEON_SPAWN
    ]
    rng.shuffle(spots)
    return spots[:count]


def pick_completion_reward():
    item_id, qty = random.choice(TIDEHOLLOW_REWARDS)
    if isinstance(qty, tuple):
        qty = random.randint(qty[0], qty[1])
    return item_id, qty


def visual_type_for_floor(floor: int) -> str:
    return _FLOOR_VISUAL.get(floor, "skeleton")
