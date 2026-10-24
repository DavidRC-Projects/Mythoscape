"""
Tidehollow Cave — private chamber-chain instance by Harbourreach.

One map of ten chambers. Each fight room spawns three different beasts;
the final chamber is dragons. Clear every chamber for a completion reward,
the Tidehollow Medal, and a golden chat announcement outside.
"""
from __future__ import annotations

import random

from world_map import WALL, FLOOR, widen_single_file_passages, is_walkable as _world_walkable

# Single run: the ten chambers on the map *are* the dungeon.
# `elite` / `boss` land in the final (dragon) chamber.
TIDEHOLLOW_FLOORS = [
    {"floor": 1, "level": 40, "count": 30, "label": "Tidehollow Cave",
     "elite": "Heart of the Deep",
     "boss": {"name": "The Tidehollow Leviathan", "level_bonus": 8}},
]

# One map holds all ten chambers: two ranks of five, 12 tiles apart.
DUNGEON_W, DUNGEON_H = 71, 38
# Entrance hall centre (chamber 0) with the exit passage running south.
DUNGEON_SPAWN = (7, 33)
CAVE_RETURN = (189, 54)  # just south of the cave mouth

# Per chamber: combat level + three distinct monster types.
# Room 0 is the entrance (EXIT south) — it fights too, so the first sealed door
# always has beasts in the room you are standing in. Room 9 is dragons.
ROOM_ENCOUNTERS = {
    0: {"level": 12, "types": ("goblin", "wolf", "skeleton"), "label": "Dripping Halls"},
    1: {"level": 20, "types": ("goblin", "skeleton", "giant"), "label": "Salted Tunnels"},
    2: {"level": 28, "types": ("wolf", "skeleton", "giant"), "label": "Barnacle Gallery"},
    3: {"level": 36, "types": ("skeleton", "giant", "big_skeleton"), "label": "Echoing Grotto"},
    4: {"level": 44, "types": ("wolf", "giant", "spider"), "label": "Blackwater Bend"},
    5: {"level": 52, "types": ("giant", "spider", "big_skeleton"), "label": "Kraken's Teeth"},
    6: {"level": 60, "types": ("spider", "big_skeleton", "giant"), "label": "Abyss Antechamber"},
    7: {"level": 68, "types": ("big_skeleton", "spider", "wolf"), "label": "Pearl Vault"},
    8: {"level": 74, "types": ("spider", "giant", "big_skeleton"), "label": "Sunken Throne"},
    9: {"level": 80, "types": ("dragon", "dragon", "dragon"), "label": "Tidehollow Heart"},
}

# Fallback visual when a room has no encounter table entry.
_FLOOR_VISUAL = {1: "goblin"}

TIDEHOLLOW_REWARDS = [
    ("mithril_body", 1),
    ("mithril_sword", 1),
    ("steel_body", 1),
    ("coins", (2500, 6000)),
    ("health_potion", (4, 8)),
    ("super_attack_potion", (2, 4)),
    ("super_strength_potion", (2, 4)),
]

# Always granted on first clear (also listed so completion UI can show it).
TIDEHOLLOW_MEDAL_ID = "tidehollow_amulet"


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
    if random.random() < min(0.15, 0.08 + floor * 0.006):
        food = "cooked_trout" if floor < 5 else ("cooked_salmon" if floor < 8 else "cooked_lobster")
        out.append((food, random.randint(1, 2)))
    if random.random() < min(0.35, 0.10 + floor * 0.025):
        out.append(("health_potion", 1))
    # Fletching / smith scraps
    if random.random() < 0.15:
        out.append(("feather", random.randint(1, 4)))
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
    if floor >= 6 and random.random() < 0.12:
        out.append(("bow_string", 1))
    return out


def floor_info(floor: int) -> dict:
    for entry in TIDEHOLLOW_FLOORS:
        if entry["floor"] == floor:
            return entry
    return TIDEHOLLOW_FLOORS[-1]


def scaled_monster_stats(level: int) -> dict:
    """Stats for a creature whose *combat level* is `level`.

    A monster's combat level is essentially attack + strength + defence, so
    the three offensive stats have to add up to the target rather than each
    scaling off it. They used to be about 2.1x the target between them, which
    made a "level 10" floor spawn level-38 beasts and the floor-80 finale a
    level-189 wall. The difficulty readout was meaningless and the last floor
    was far harder than the table promised.
    """
    target = max(1, int(level))
    # Split the level budget across the three combat stats, then let HP sit a
    # little above that total (a depth bonus) without distorting the label.
    att = max(2, round(target * 0.36))
    strength = max(2, round(target * 0.36))
    defence = max(1, target - att - strength)
    hp = max(12, int(target * 2.2))
    import combat
    stats = {
        "tier": level,
        "hp": hp,
        "attack": att,
        "strength": strength,
        "defence": defence,
        "def_bonus": max(0, level // 8),
        "xp": max(20, int(level * 4.5)),
        # The displayed number is the tier the floor advertises. It is pinned
        # so a stat tweak can never silently change what the player is told
        # they are fighting.
        "level_override": target,
    }
    stats["level"] = combat.monster_combat_level(stats)
    stats["name"] = f"Cavern Beast (lvl {stats['level']})"
    return stats


# ---------------------------------------------------------------------------
# Segmented floors
#
# A floor is a chain of chambers, one per encounter. Each chamber holds its own
# wave of monsters and its exits are sealed until the wave is dead, so progress
# is "clear this room, the way opens". Rooms are laid out on a 2x3 grid of
# slots and joined by short corridors, which keeps every chamber reachable and
# gives each one a distinct arena rather than one open hall.
# ---------------------------------------------------------------------------

DOOR = "door"        # an opening that can seal and open; walkable when open
SEALED = "sealed"    # a sealed opening: solid while the room is uncleared

# Ten chambers on one map, in two ranks of five. The entrance is the bottom
# centre; the chain snakes up one side and back down the other so the player
# sees the whole floor and walks it room by room.
#
# A 10x6 chamber spans 12x8 including its walls, so centres must be that far
# apart or neighbouring rooms merge and the connector has nothing to carve.
_ROOM_W, _ROOM_H = 10, 6
# Two ranks, chained left-to-right then right-to-left so each corridor is
# between neighbours rather than across the whole map.
_ROOM_SLOTS = [
    (7, 30), (21, 30), (35, 30), (49, 30), (63, 30),   # lower rank, west→east
    (63, 14), (49, 14), (35, 14), (21, 14), (7, 14),   # upper rank, east→west
]

# Three beasts per fight chamber — always. The types come from ROOM_ENCOUNTERS.
ROOM_SPAWNS_PER_CHAMBER = 3


def room_spawn_count(floor: int) -> int:
    return ROOM_SPAWNS_PER_CHAMBER


def room_encounter(room_id: int) -> dict:
    """Level + three monster types for a fight chamber."""
    return ROOM_ENCOUNTERS.get(int(room_id)) or {
        "level": 20, "types": ("goblin", "wolf", "skeleton"), "label": "Tidehollow",
    }


def room_monster_types(room_id: int) -> tuple:
    """Exactly three types for the chamber. Final room is dragons."""
    types = tuple(room_encounter(room_id).get("types") or ("goblin", "wolf", "skeleton"))
    if len(types) >= 3:
        return types[:3]
    # Pad without duplicating when possible.
    pool = ("goblin", "wolf", "skeleton", "giant", "spider", "big_skeleton")
    out = list(types)
    for t in pool:
        if len(out) >= 3:
            break
        if t not in out:
            out.append(t)
    while len(out) < 3:
        out.append(out[-1] if out else "goblin")
    return tuple(out[:3])


def room_combat_level(room_id: int) -> int:
    return int(room_encounter(room_id).get("level") or 20)


def is_finale_room(room_id: int) -> bool:
    """True for the last chamber — dragons + Leviathan."""
    return int(room_id) == max(ROOM_ENCOUNTERS)


def _carve_room(tiles, cx, cy, w, h):
    """Carve a rounded chamber; returns the set of floor cells it made."""
    cells = set()
    for y in range(cy - h // 2, cy + h // 2 + 1):
        for x in range(cx - w // 2, cx + w // 2 + 1):
            if not (1 <= x < DUNGEON_W - 1 and 1 <= y < DUNGEON_H - 1):
                continue
            # Clip the corners so rooms are not identical boxes.
            corner = (abs(x - cx) == w // 2 and abs(y - cy) == h // 2)
            if corner:
                continue
            tiles[y][x] = FLOOR
            cells.add((x, y))
    return cells


def _carve_corridor(tiles, a_cells, b_cells, present, rng):
    """Carve a corridor that connects two rooms.

    Walks an L from a cell just outside room A to a cell just outside room B,
    carving only rock. Endpoints are the closest pair of cells between the two
    rooms, so the path is short and points the right way.
    """
    best = None
    for ax, ay in a_cells:
        for bx, by in b_cells:
            d = abs(ax - bx) + abs(ay - by)
            if best is None or d < best[0]:
                best = (d, (ax, ay), (bx, by))
    if best is None:
        return set()
    _d, (ax, ay), (bx, by) = best

    def solid(x, y):
        return (1 <= x < DUNGEON_W - 1 and 1 <= y < DUNGEON_H - 1
                and tiles[y][x] != FLOOR)

    pts = []
    if rng.random() < 0.5:
        step_x = 1 if bx > ax else -1
        for x in range(ax, bx + step_x, step_x):
            pts.append((x, ay))
        step_y = 1 if by > ay else -1
        for y in range(ay, by + step_y, step_y):
            pts.append((bx, y))
    else:
        step_y = 1 if by > ay else -1
        for y in range(ay, by + step_y, step_y):
            pts.append((ax, y))
        step_x = 1 if bx > ax else -1
        for x in range(ax, bx + step_x, step_x):
            pts.append((x, by))

    carved = set()
    for x, y in pts:
        for ox, oy in ((0, 0), (0, 1)):
            nx, ny = x + ox, y + oy
            if not solid(nx, ny):
                continue
            tiles[ny][nx] = FLOOR
            carved.add((nx, ny))
    return carved


def generate_rooms(floor: int, rng=None):
    """Build the whole ten-chamber floor in one map.

    Every chamber is laid out at once so the player can see the entire dungeon
    from the entrance. Each chamber records ``kill_target`` — the number of
    kills needed to open its doors — and ``kills``, which only ever counts up.

    Returns (tiles, rooms). Each room is::

        {"id", "cells", "center", "doors", "cleared", "kills", "kill_target"}
    """
    rng = rng or random.Random(floor * 7919 + 17)
    tiles = [[WALL for _ in range(DUNGEON_W)] for _ in range(DUNGEON_H)]
    rooms, cells_by_room = [], []
    for index, (cx, cy) in enumerate(_ROOM_SLOTS):
        cells = _carve_room(tiles, cx, cy, _ROOM_W, _ROOM_H)
        cells_by_room.append(cells)
        rooms.append({
            "id": index,
            "cells": cells,
            "center": (cx, cy),
            "doors": set(),
            # Every chamber starts uncleared — including the entrance — so the
            # first sealed door always has three beasts in the room you are in.
            "cleared": False,
            "kills": 0,
            # Provisional; the server replaces this with the number that
            # actually spawned in the room.
            "kill_target": room_spawn_count(floor),
        })
    # Chain the rooms in order.
    for i in range(1, len(rooms)):
        corridor = _carve_corridor(
            tiles, cells_by_room[i - 1], cells_by_room[i],
            set().union(*cells_by_room), rng)
        if not corridor:
            continue
        # A door is where the corridor meets the room: the touching pair.
        def touch(room_cells, corridor_cells):
            out = set()
            for x, y in corridor_cells:
                for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1), (0, 0)):
                    n = (x + dx, y + dy)
                    if n in room_cells:
                        out.add(n)
                        break
            return out

        rooms[i]["doors"] |= touch(cells_by_room[i], corridor)
        # The room behind also gets a door, so a corridor between two locked
        # chambers is not left open with no gate on either end.
        rooms[i - 1]["doors"] |= touch(cells_by_room[i - 1], corridor)
        cells_by_room[i] |= corridor
        cells_by_room[i - 1] |= corridor
    # The southern exit passage, so leaving stays possible.
    sx, sy = DUNGEON_SPAWN
    for y in range(sy, DUNGEON_H - 1):
        for dx in (-1, 0, 1):
            nx = sx + dx
            if 0 <= nx < DUNGEON_W:
                tiles[y][nx] = FLOOR
    for dx in (-1, 0, 1):
        nx = sx + dx
        if 0 <= nx < DUNGEON_W:
            tiles[DUNGEON_H - 1][nx] = FLOOR
    # NOTE: no widen_single_file_passages() here. Corridors are already carved
    # two tiles wide, and that helper opens *both* sides of any one-tile gap,
    # which punched holes through the chamber walls and merged the rooms into
    # one long hall.
    _recompute_doors(tiles, rooms)
    return tiles, rooms


def _is_exit_tile(x, y) -> bool:
    """Southern leave-passage — must never be sealed."""
    sx, sy = DUNGEON_SPAWN
    return abs(int(x) - sx) <= 1 and int(y) >= sy


def _recompute_doors(tiles, rooms):
    """Refresh each room's doorway set from the final tile layout.

    A door is a floor cell owned by this chamber that touches a floor cell
    owned by a *different* chamber (the corridor boundary). The southern EXIT
    passage is never a door — sealing it would trap the player inside.
    """
    for room in rooms:
        doors = set()
        for x, y in room["cells"]:
            if _is_exit_tile(x, y):
                continue
            owner = room_at(rooms, x, y)
            if owner is None or owner["id"] != room["id"]:
                continue
            for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                nx, ny = x + dx, y + dy
                if not (0 <= ny < len(tiles) and 0 <= nx < len(tiles[ny])):
                    continue
                if tiles[ny][nx] not in (FLOOR, SEALED):
                    continue
                if _is_exit_tile(nx, ny):
                    continue
                neighbor = room_at(rooms, nx, ny)
                if neighbor is not None and neighbor["id"] != room["id"]:
                    doors.add((x, y))
                    break
        room["doors"] = doors


def _rooms_connected(tiles):
    """Every walkable tile reachable from the spawn (no orphaned chambers).

    Sealed doors count as walkable here. They are floor that happens to be
    blocked until a room is cleared, so treating them as walls makes every
    segmented floor look broken — the chamber beyond a sealed door is
    unreachable *right now* but is reachable once the fight ends.
    """
    sx, sy = DUNGEON_SPAWN

    def walkable(x, y):
        return tiles[y][x] in (FLOOR, SEALED)

    seen = {(sx, sy)}
    stack = [(sx, sy)]
    while stack:
        x, y = stack.pop()
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            n = (x + dx, y + dy)
            if n in seen:
                continue
            nx, ny = n
            if 0 <= nx < DUNGEON_W and 0 <= ny < DUNGEON_H and walkable(nx, ny):
                seen.add(n)
                stack.append(n)
    total = sum(1 for row in tiles for t in row if t in (FLOOR, SEALED))
    return len(seen) >= total


def generate_floor_tiles(floor: int, rng=None):
    """Backwards-compatible: the tiles only."""
    tiles, _rooms = generate_rooms(floor, rng)
    return tiles


def generate_floor_tiles_open(floor: int, rng=None):
    """The original single chamber, kept as the layout of last resort."""
    rng = rng or random.Random(floor * 7919 + 17)
    w, h = DUNGEON_W, DUNGEON_H
    tiles = [[WALL for _ in range(w)] for _ in range(h)]
    for y in range(1, h - 1):
        for x in range(1, w - 1):
            tiles[y][x] = FLOOR
    sx, sy = DUNGEON_SPAWN
    tiles[sy][sx] = FLOOR
    for dx, dy in ((0, -1), (0, -2), (0, -3), (-1, 0), (1, 0), (0, 1), (-1, -1), (1, -1)):
        nx, ny = sx + dx, sy + dy
        if 0 <= nx < w and 0 <= ny < h:
            tiles[ny][nx] = FLOOR
    for y in range(sy, h - 1):
        tiles[y][sx] = FLOOR
        if sx > 0:
            tiles[y][sx - 1] = FLOOR
        if sx < w - 1:
            tiles[y][sx + 1] = FLOOR
    tiles[h - 1][sx] = FLOOR
    widen_single_file_passages(tiles)
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
    """Legacy single-type helper; Tidehollow now prefers room_monster_types."""
    return _FLOOR_VISUAL.get(floor, "skeleton")


def monster_display_name(visual: str, level: int) -> str:
    """Readable name for a Tidehollow spawn (overworld names + cavern flavour)."""
    base = {
        "goblin": "Cave Goblin",
        "wolf": "Brine Wolf",
        "skeleton": "Salt Skeleton",
        "giant": "Drowned Giant",
        "big_skeleton": "Barnacle Skeleton",
        "spider": "Tide Spider",
        "dragon": "Tidehollow Dragon",
    }.get(visual, "Cavern Beast")
    return f"{base} (lvl {int(level)})"


# ---------------------------------------------------------------------------
# Sealing
#
# Cleared chambers stay open. The next fight chamber stays open so the player
# can walk in and meet its beasts. Further chambers stay sealed until the one
# before them is cleared. Once the player is *inside* an uncleared chamber,
# that chamber's doors seal behind them until its kill target is met.
# ---------------------------------------------------------------------------

def frontier_room_id(rooms) -> int | None:
    """Id of the next uncleared fight chamber, or None if the chain is done."""
    for room in sorted(rooms, key=lambda r: r["id"]):
        if room.get("cleared"):
            continue
        if not room.get("doors") and int(room.get("kill_target") or 0) <= 0:
            continue
        return int(room["id"])
    return None


def apply_seals(tiles, rooms, player_xy=None):
    """Seal only rooms the player should not enter yet (and the active fight).

    Passing ``player_xy`` seals the chamber they currently stand in when that
    chamber is still uncleared, so the fight cannot be abandoned by walking out.
    """
    # Clear every former seal first so reopening a frontier never leaves a
    # stale SEALED tile from a previous layout pass.
    for y, row in enumerate(tiles):
        for x, tile in enumerate(row):
            if tile == SEALED:
                row[x] = FLOOR

    frontier = frontier_room_id(rooms)
    inside_id = None
    if player_xy is not None and frontier is not None:
        here = room_at(rooms, player_xy[0], player_xy[1])
        if here is not None and not here.get("cleared") and int(here["id"]) == frontier:
            # Only seal behind once they have stepped past the doorway into the
            # chamber proper — standing on a door tile must not trap them outside.
            if (int(player_xy[0]), int(player_xy[1])) not in here.get("doors", ()):
                inside_id = int(here["id"])

    for room in rooms:
        if room.get("cleared"):
            continue
        rid = int(room["id"])
        # Keep the frontier open until the player is inside it. Seal every
        # chamber beyond that so they cannot skip ahead.
        if frontier is not None and rid == frontier and inside_id != rid:
            continue
        if frontier is not None and rid > frontier:
            pass  # seal
        elif inside_id is not None and rid == inside_id:
            pass  # seal behind
        elif frontier is None:
            continue
        else:
            # Uncleared rooms behind the frontier should not exist in a healthy
            # chain; leave them open rather than soft-locking.
            continue
        for x, y in room.get("doors") or ():
            if _is_exit_tile(x, y):
                continue
            if 0 <= y < len(tiles) and 0 <= x < len(tiles[0]):
                tiles[y][x] = SEALED
    return tiles


def open_room(tiles, rooms, room):
    """Mark a room cleared and refresh seals so the next chamber opens."""
    room["cleared"] = True
    return apply_seals(tiles, rooms)


def room_at(rooms, x, y):
    """The chamber a tile belongs to, or None.

    A room's footprint includes its connecting corridor, and adjoining rooms
    share that corridor, so several rooms can claim the same tile. Returning
    the first match made a player standing in chamber 2 register as chamber 1.
    Pick the room whose centre is nearest: the chamber they are actually in.
    """
    x, y = int(x), int(y)
    best = None
    best_d = None
    for room in rooms:
        if (x, y) not in room["cells"]:
            continue
        cx, cy = room["center"]
        d = abs(cx - x) + abs(cy - y)
        if best_d is None or d < best_d:
            best, best_d = room, d
    return best


def room_clear_reward(floor: int):
    """Loot for clearing one chamber.

    Separate from per-kill drops: this is the reward for the *room*, so it
    scales with depth and always contains something useful. Coins plus one
    consumable, with a chance of a bar or tip bundle on deeper floors.
    """
    floor = max(1, int(floor))
    out = [("coins", random.randint(25 + floor * 18, 70 + floor * 40))]
    consumables = ["cooked_trout", "cooked_salmon", "health_potion"]
    if floor >= 4:
        consumables.append("cooked_lobster")
    if floor >= 6:
        consumables.append("super_attack_potion")
    out.append((random.choice(consumables), random.randint(1, 2)))
    if floor >= 3 and random.random() < 0.45:
        out.append(("iron_ore" if floor < 7 else "mithril_ore", random.randint(1, 3)))
    if floor >= 5 and random.random() < 0.30:
        out.append(("steel_bar" if floor < 8 else "mithril_bar", 1))
    return out


def room_interior_box(room):
    """Axis-aligned leash box for the carved chamber (not the corridor)."""
    cx, cy = room["center"]
    hw, hh = _ROOM_W // 2, _ROOM_H // 2
    return (cx - hw, cy - hh, cx + hw, cy + hh)


def spawn_tiles_for_room(room, tiles, limit, rooms=None):
    """Free floor tiles in the chamber proper — never corridors or the EXIT.

    When ``rooms`` is given, only tiles whose nearest chamber is this room are
    used, so beasts cannot spawn in a neighbour's footprint and open the wrong
    door.
    """
    doors = room["doors"]
    cx, cy = room["center"]
    hw, hh = _ROOM_W // 2, _ROOM_H // 2
    candidates = []
    for x, y in room["cells"]:
        if tiles[y][x] != FLOOR:
            continue
        if _is_exit_tile(x, y):
            continue
        # Stay inside the carved box so corridor merges never host a spawn.
        if abs(x - cx) > hw or abs(y - cy) > hh:
            continue
        if rooms is not None:
            owner = room_at(rooms, x, y)
            if owner is None or owner["id"] != room["id"]:
                continue
        if (x, y) in doors:
            continue
        # Keep a tile between monsters and the doorway so nothing plugs it.
        if any((x + dx, y + dy) in doors for dx in (-1, 0, 1) for dy in (-1, 0, 1)):
            continue
        candidates.append((abs(x - cx) + abs(y - cy), x, y))
    candidates.sort()
    return [(x, y) for _d, x, y in candidates[:limit]]
