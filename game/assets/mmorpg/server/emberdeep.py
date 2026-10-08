"""
Emberdeep — private lava-themed instance dungeon east of Stonehaven.

Clear each floor to advance. Floor 8 yields a completion reward + Emberdeep Medal.
"""
from __future__ import annotations

import random

import os

from world_map import WALL, FLOOR, WATER, widen_single_file_passages, is_walkable as _world_walkable
import feature_flags

EMBERDEEP_FLOORS = [
    {"floor": 1, "level": 22, "count": 10, "label": "Ash Approach"},
    {"floor": 2, "level": 30, "count": 9, "label": "Cinder Galleries"},
    {"floor": 3, "level": 38, "count": 8, "label": "Magma Seams"},
    {"floor": 4, "level": 48, "count": 7, "label": "Ember Vaults"},
    {"floor": 5, "level": 58, "count": 6, "label": "Cracked Crucible"},
    {"floor": 6, "level": 68, "count": 5, "label": "Molten Bridge"},
    {"floor": 7, "level": 78, "count": 4, "label": "Infernal Hall"},
    {"floor": 8, "level": 88, "count": 3, "label": "Heart of Emberdeep"},
]

DUNGEON_W, DUNGEON_H = 20, 16
DUNGEON_SPAWN = (10, 13)
# South of the volcano mouth (overworld)
CAVE_RETURN = (186, 86)

_FLOOR_VISUAL = {
    1: "magma_slug", 2: "magma_slug",
    3: "ash_imp", 4: "ash_imp",
    5: "ember_wolf", 6: "ember_wolf",
    7: "magma_knight",
    8: "crucible_beast",
}

EMBERDEEP_REWARDS = [
    ("mithril_body", 1),
    ("mithril_sword", 1),
    ("ruby", (2, 4)),
    ("diamond", (1, 2)),
    ("onyx", 1),
    ("coins", (4000, 9000)),
    ("super_attack_potion", (2, 4)),
    ("super_strength_potion", (2, 4)),
    ("super_defence_potion", (2, 4)),
    ("health_potion", (5, 10)),
]


def roll_kill_loot(floor: int, level: int):
    floor = max(1, int(floor))
    out = []
    coin_lo = 12 + floor * 10
    coin_hi = 28 + floor * 18
    out.append(("coins", random.randint(coin_lo, coin_hi)))
    if random.random() < min(0.15, 0.08 + floor * 0.006):
        food = "cooked_lobster" if floor < 5 else "cooked_swordfish"
        out.append((food, random.randint(1, 2)))
    if random.random() < min(0.40, 0.12 + floor * 0.03):
        out.append(("health_potion", 1))
    if random.random() < 0.04:
        gem = random.choice(["topaz", "sapphire", "emerald", "ruby"][: max(1, floor // 2)])
        out.append((gem, 1))
    if floor >= 5 and random.random() < 0.08:
        out.append(("adamant_ore" if random.random() < 0.5 else "coal", random.randint(1, 2)))
    return out


def floor_info(floor: int) -> dict:
    for entry in EMBERDEEP_FLOORS:
        if entry["floor"] == floor:
            return entry
    return EMBERDEEP_FLOORS[-1]


def scaled_monster_stats(level: int) -> dict:
    hp = max(18, int(level * 2.4))
    att = max(5, int(level * 0.78)) + 10
    strength = max(5, int(level * 0.80)) + 10
    defence = max(4, int(level * 0.68))
    return {
        "level": level,
        "hp": hp,
        "attack": att,
        "strength": strength,
        "defence": defence,
        "def_bonus": max(0, level // 4),
        "xp": max(30, int(level * 5.2)),
        "name": f"Ember Beast (lvl {level})",
    }


_V2_MARKS = {}
_V2_BASE_W, _V2_BASE_H = DUNGEON_W, DUNGEON_H
_V2_BASE_SPAWN = DUNGEON_SPAWN


def v2_marks():
    """Hoard, nest, boss door, spawn, and exit from the hand grid. Empty if unused."""
    return dict(_V2_MARKS)


def _v2_floor_path():
    here = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(here, "..", "..", "emberdeep_v2_pack", "interior", "emberdeep_v2_floor.txt")


def _load_v2_floor():
    """Map the authored grid onto WALL / FLOOR / WATER. All eight floors share it."""
    global DUNGEON_W, DUNGEON_H, DUNGEON_SPAWN, _V2_MARKS
    text = open(_v2_floor_path(), encoding="utf-8").read().splitlines()
    rows = [line.rstrip("\n") for line in text if line.strip("\n")]
    width = max(len(row) for row in rows)
    tiles = []
    marks = {}
    names = {"S": "spawn", "E": "exit", "H": "hoard", "N": "nest", "K": "boss"}
    for y, row in enumerate(rows):
        row = row.ljust(width, "#")
        out = []
        for x, ch in enumerate(row):
            if ch == "L":
                out.append(WATER)
            elif ch == "#":
                out.append(WALL)
            else:
                out.append(FLOOR)
                if ch in names:
                    marks[names[ch]] = (x, y)
        tiles.append(out)
    DUNGEON_W = width
    DUNGEON_H = len(tiles)
    DUNGEON_SPAWN = marks.get("spawn", (width // 2, len(tiles) - 3))
    _V2_MARKS = marks
    _widen_v2_halls(tiles, marks.get("boss"))
    return tiles


def _widen_v2_halls(tiles, boss):
    """Open one-tile halls that are cut through rock. Room walls stay put.

    A hall cell has floor straight ahead and behind, and rock on both sides.
    Each side becomes floor only when the tile beyond that rock is still
    rock, so a one-tile wall between two rooms is not knocked out. Lava,
    the boss threshold, and the map border are left alone.
    """
    height = len(tiles)
    width = len(tiles[0]) if height else 0
    if width < 3 or height < 3:
        return
    ortho = ((1, 0), (-1, 0), (0, 1), (0, -1))
    opened = []
    for y in range(1, height - 1):
        for x in range(1, width - 1):
            if tiles[y][x] != FLOOR or (x, y) == boss:
                continue
            neigh = []
            for dx, dy in ortho:
                if tiles[y + dy][x + dx] == FLOOR:
                    neigh.append((dx, dy))
            if len(neigh) != 2:
                continue
            axes = {(abs(dx), abs(dy)) for dx, dy in neigh}
            if len(axes) != 1:
                continue
            ax, _ay = next(iter(axes))
            sides = ((0, 1), (0, -1)) if ax == 1 else ((1, 0), (-1, 0))
            for dx, dy in sides:
                nx, ny = x + dx, y + dy
                if not (0 < nx < width - 1 and 0 < ny < height - 1):
                    continue
                if tiles[ny][nx] != WALL:
                    continue
                ox, oy = nx + dx, ny + dy
                if not (0 <= ox < width and 0 <= oy < height):
                    continue
                if tiles[oy][ox] != WALL:
                    continue
                opened.append((nx, ny))
    for nx, ny in opened:
        tiles[ny][nx] = FLOOR


def generate_floor_tiles(floor: int, rng=None):
    """Mountain chamber — irregular walls, lava rivers, basalt pillars, exit mouth south."""
    if feature_flags.USE_EMBERDEEP_V2:
        return _load_v2_floor()
    global DUNGEON_W, DUNGEON_H, DUNGEON_SPAWN, _V2_MARKS
    DUNGEON_W, DUNGEON_H = _V2_BASE_W, _V2_BASE_H
    DUNGEON_SPAWN = _V2_BASE_SPAWN
    _V2_MARKS = {}
    rng = rng or random.Random(floor * 9133 + 41)
    w, h = DUNGEON_W, DUNGEON_H
    tiles = [[WALL for _ in range(w)] for _ in range(h)]
    # Main cavern — slightly irregular oval carve
    cx, cy = w // 2, h // 2 - 1
    for y in range(1, h - 1):
        for x in range(1, w - 1):
            dx = (x - cx) / max(1, (w // 2 - 1.5))
            dy = (y - cy) / max(1, (h // 2 - 1.5))
            jitter = (rng.random() - 0.5) * 0.25
            if dx * dx + dy * dy < 0.92 + jitter:
                tiles[y][x] = FLOOR
    sx, sy = DUNGEON_SPAWN
    # Southern exit corridor (mouth back to overworld)
    for y in range(sy - 1, h - 1):
        for x in range(sx - 1, sx + 2):
            if 0 < x < w - 1:
                tiles[y][x] = FLOOR
    tiles[h - 1][sx] = FLOOR  # exit mouth tile on south wall
    # Side chambers on deeper floors
    if floor >= 3:
        for ox, oy, rw, rh in ((3, 3, 4, 3), (w - 7, 3, 4, 3)):
            for y in range(oy, oy + rh):
                for x in range(ox, ox + rw):
                    if 0 < x < w - 1 and 0 < y < h - 1:
                        tiles[y][x] = FLOOR
            # Tunnel to main room
            for x in range(min(ox + 2, cx), max(ox + 2, cx) + 1):
                if 0 < x < w - 1:
                    tiles[oy + 1][x] = FLOOR
    # Magma pillars / basalt clutter
    for _ in range(4 + floor):
        x = rng.randint(2, w - 3)
        y = rng.randint(2, h - 4)
        if abs(x - sx) + abs(y - sy) < 3:
            continue
        if tiles[y][x] != FLOOR:
            continue
        tiles[y][x] = WALL
        if rng.random() < 0.55 and tiles[y][min(w - 2, x + 1)] == FLOOR:
            tiles[y][x + 1] = WALL
    # Lava river / pools (WATER = lava inside Emberdeep)
    river_y = 5 + (floor % 3)
    if 2 < river_y < h - 3:
        for x in range(3, w - 3):
            if abs(x - sx) < 2:
                continue  # leave bridge gap
            if tiles[river_y][x] == FLOOR:
                tiles[river_y][x] = WATER
                if rng.random() < 0.4 and tiles[min(h - 2, river_y + 1)][x] == FLOOR:
                    tiles[river_y + 1][x] = WATER
    for _ in range(2 + floor // 2):
        x = rng.randint(3, w - 4)
        y = rng.randint(3, h - 5)
        if abs(x - sx) + abs(y - sy) < 4:
            continue
        for dx, dy in ((0, 0), (1, 0), (0, 1), (1, 1)):
            nx, ny = x + dx, y + dy
            if tiles[ny][nx] == FLOOR:
                tiles[ny][nx] = WATER
    # Ensure spawn + exit path clear
    tiles[sy][sx] = FLOOR
    for dx, dy in ((0, -1), (0, -2), (-1, 0), (1, 0), (0, 1), (0, 2)):
        nx, ny = sx + dx, sy + dy
        if 0 <= nx < w and 0 <= ny < h:
            tiles[ny][nx] = FLOOR
    tiles[h - 1][sx] = FLOOR
    # Permanent south corridor to exit (lava/pillars must not seal it)
    for y in range(sy, h):
        for x in range(sx - 1, sx + 2):
            if 0 < x < w - 1 and 0 <= y < h:
                if y == h - 1 and x != sx:
                    continue
                tiles[y][x] = FLOOR
    tiles[h - 1][sx] = FLOOR
    # Connectivity: every FLOOR must reach spawn (carve tunnels or seal pockets)
    _ensure_floor_connected(tiles, sx, sy, rng)
    widen_single_file_passages(tiles)
    return tiles


def _ensure_floor_connected(tiles, sx, sy, rng):
    """BFS from spawn; carve short tunnels to orphan FLOOR, else seal as WALL."""
    h = len(tiles)
    w = len(tiles[0]) if h else 0
    if w < 3 or h < 3:
        return

    def neighbors(x, y):
        for dx, dy in ((0, 1), (0, -1), (1, 0), (-1, 0)):
            nx, ny = x + dx, y + dy
            if 0 <= nx < w and 0 <= ny < h:
                yield nx, ny

    def reachable():
        seen = set()
        if tiles[sy][sx] != FLOOR:
            tiles[sy][sx] = FLOOR
        q = [(sx, sy)]
        seen.add((sx, sy))
        i = 0
        while i < len(q):
            x, y = q[i]
            i += 1
            for nx, ny in neighbors(x, y):
                if (nx, ny) in seen:
                    continue
                if tiles[ny][nx] == FLOOR:
                    seen.add((nx, ny))
                    q.append((nx, ny))
        return seen

    for _attempt in range(48):
        reached = reachable()
        orphans = [
            (x, y)
            for y in range(h)
            for x in range(w)
            if tiles[y][x] == FLOOR and (x, y) not in reached
        ]
        if not orphans:
            return
        # Prefer carving toward the nearest reached tile
        ox, oy = orphans[0]
        # Find closest reached cell
        best = None
        best_d = 10**9
        for rx, ry in reached:
            d = abs(rx - ox) + abs(ry - oy)
            if d < best_d:
                best_d = d
                best = (rx, ry)
        if best is None:
            tiles[oy][ox] = WALL
            continue
        bx, by = best
        x, y = ox, oy
        # Dig a 3-tile-wide L so the tunnel stays walkable beside a monster
        while x != bx:
            x += 1 if bx > x else -1
            for ox in (-1, 0, 1):
                xx = x + ox
                if 0 < xx < w - 1 and 0 < y < h - 1:
                    tiles[y][xx] = FLOOR
        while y != by:
            y += 1 if by > y else -1
            for oy in (-1, 0, 1):
                yy = y + oy
                if 0 < x < w - 1 and 0 < yy < h - 1:
                    if yy == h - 1 and x != sx:
                        continue
                    tiles[yy][x] = FLOOR
    # Seal any remaining orphans
    reached = reachable()
    for y in range(h):
        for x in range(w):
            if tiles[y][x] == FLOOR and (x, y) not in reached:
                tiles[y][x] = WALL
    tiles[sy][sx] = FLOOR
    tiles[h - 1][sx] = FLOOR


def dungeon_walkable(tiles, x, y) -> bool:
    if not tiles or y < 0 or y >= len(tiles) or x < 0 or x >= len(tiles[0]):
        return False
    return tiles[y][x] == FLOOR


def pick_spawn_tiles(tiles, count, rng=None):
    rng = rng or random
    sx, sy = DUNGEON_SPAWN
    # Only tiles reachable from spawn
    h = len(tiles)
    w = len(tiles[0]) if h else 0
    seen = set()
    q = [(sx, sy)]
    if 0 <= sy < h and 0 <= sx < w and tiles[sy][sx] == FLOOR:
        seen.add((sx, sy))
    i = 0
    while i < len(q):
        x, y = q[i]
        i += 1
        for dx, dy in ((0, 1), (0, -1), (1, 0), (-1, 0)):
            nx, ny = x + dx, y + dy
            if (nx, ny) in seen:
                continue
            if 0 <= nx < w and 0 <= ny < h and tiles[ny][nx] == FLOOR:
                seen.add((nx, ny))
                q.append((nx, ny))
    spots = [p for p in seen if p != DUNGEON_SPAWN]
    if feature_flags.USE_EMBERDEEP_V2:
        # Keep the rolled monsters in the rooms. The one-tile passages stay clear.
        # The north lair is the wyrm's. Nothing else spawns in there.
        lair = room_box(tiles, 22, 3) if tiles[3][22] == FLOOR else None
        spots = [
            p for p in spots
            if _in_room_block(tiles, p[0], p[1])
            and max(abs(p[0] - sx), abs(p[1] - sy)) > 2
            and not (
                lair
                and lair[0] <= p[0] <= lair[2]
                and lair[1] <= p[1] <= lair[3]
            )
        ]
    rng.shuffle(spots)
    return spots[:count]


def _in_room_block(tiles, x, y):
    """True when this floor tile is part of a room, not a one-tile corridor.

    A bend in a corridor is still a corridor. A room contains a 2 by 2 of floor.
    """
    h = len(tiles)
    w = len(tiles[0]) if h else 0

    def floor(nx, ny):
        return 0 <= nx < w and 0 <= ny < h and tiles[ny][nx] == FLOOR

    if not floor(x, y):
        return False
    for dx, dy in ((0, 0), (-1, 0), (0, -1), (-1, -1)):
        if all(floor(x + dx + a, y + dy + b) for a in (0, 1) for b in (0, 1)):
            return True
    return False


def _one_tile_passage(tiles, x, y):
    """True when this floor tile is a corridor, not the inside of a room."""
    h = len(tiles)
    w = len(tiles[0]) if h else 0

    def open_tile(nx, ny):
        return 0 <= nx < w and 0 <= ny < h and tiles[ny][nx] == FLOOR

    sides_h = sum(open_tile(x + d, y) for d in (-1, 1))
    sides_v = sum(open_tile(x, y + d) for d in (-1, 1))
    return (sides_h == 0 and sides_v > 0) or (sides_v == 0 and sides_h > 0)


def room_box(tiles, x, y):
    """The room around a creature. The narrow passages are left out."""
    h = len(tiles)
    w = len(tiles[0]) if h else 0
    x, y = int(x), int(y)
    if not (0 <= x < w and 0 <= y < h) or tiles[y][x] != FLOOR or not _in_room_block(tiles, x, y):
        return (x, y, x, y)
    seen = {(x, y)}
    queue = [(x, y)]
    i = 0
    while i < len(queue):
        cx, cy = queue[i]
        i += 1
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            nx, ny = cx + dx, cy + dy
            if (nx, ny) in seen or not (0 <= nx < w and 0 <= ny < h):
                continue
            if tiles[ny][nx] != FLOOR or not _in_room_block(tiles, nx, ny):
                continue
            seen.add((nx, ny))
            queue.append((nx, ny))
    xs = [px for px, _py in seen]
    ys = [py for _px, py in seen]
    return (min(xs), min(ys), max(xs), max(ys))


def pick_completion_reward():
    item_id, qty = random.choice(EMBERDEEP_REWARDS)
    if isinstance(qty, tuple):
        qty = random.randint(qty[0], qty[1])
    return item_id, qty


def visual_type_for_floor(floor: int) -> str:
    return _FLOOR_VISUAL.get(floor, "ash_imp")


def monster_display_name(visual: str, level: int) -> str:
    names = {
        "magma_slug": "Magma Slug",
        "ash_imp": "Ash Imp",
        "ember_wolf": "Ember Wolf",
        "magma_knight": "Magma Knight",
        "crucible_beast": "Crucible Beast",
    }
    base = names.get(visual, "Ember Beast")
    return f"{base} (lvl {level})"
