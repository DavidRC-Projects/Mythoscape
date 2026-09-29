"""Overworld dungeon interiors live on their own maps.

The overworld keeps a walk-up pad and the entrance sprite. Entering copies
the captured interior onto a private map. Walking onto the south exit tile,
or pressing Leave, returns you to the entrance.
"""
from __future__ import annotations

import dungeon_props
from world_map import GRASS, FLOOR, WALKABLE_TILES, room_containing, widen_single_file_passages

# World rects captured before the overworld interior is cleared.
# Pads stay on the overworld so you can walk up to the entrance.
REGIONS = {
    "depths": {
        "name": "The Depths",
        "label": "Dungeon",
        "x0": 44, "y0": 54, "x1": 90, "y1": 143,
        "pad": (43, 69, 50, 76),
        "entrance": (46, 71),
    },
    "sanctum": {
        "name": "Void Sanctum",
        "label": "Void Sanctum",
        "x0": 154, "y0": 98, "x1": 190, "y1": 140,
        "pad": (166, 104, 176, 112),
        "entrance": (171, 108),
    },
}

_SNAPSHOTS: dict[str, dict] = {}


def _in_rect(x, y, rect) -> bool:
    x0, y0, x1, y1 = rect
    return x0 <= x <= x1 and y0 <= y <= y1


def contains_region(x, y) -> bool:
    """True if this tile belongs to a dungeon map, including the entrance pad."""
    for spec in REGIONS.values():
        if _in_rect(x, y, (spec["x0"], spec["y0"], spec["x1"], spec["y1"])):
            return True
    return False


def capture_and_hide(grid) -> None:
    """Save each interior, then turn the overworld copy into open ground."""
    _SNAPSHOTS.clear()
    height = len(grid)
    width = len(grid[0]) if height else 0
    for key, spec in REGIONS.items():
        x0, y0, x1, y1 = spec["x0"], spec["y0"], spec["x1"], spec["y1"]
        tiles = []
        for y in range(y0, y1 + 1):
            row = []
            for x in range(x0, x1 + 1):
                if 0 <= y < height and 0 <= x < width:
                    row.append(grid[y][x])
                else:
                    row.append(GRASS)
            tiles.append(row)
        ex, ey = spec["entrance"]
        local_door = (ex - x0, ey - y0)
        _open_entrance_lane(tiles, local_door[0], local_door[1])
        widen_single_file_passages(tiles)
        spawn = _nearest_walkable(tiles, local_door[0], max(0, local_door[1] - 1))
        exit_xy = _nearest_walkable(tiles, local_door[0], min(len(tiles) - 1, local_door[1] + 2))
        if exit_xy == spawn:
            exit_xy = _nearest_walkable(tiles, local_door[0], min(len(tiles) - 1, local_door[1] + 4))
        _SNAPSHOTS[key] = {
            "tiles": tiles,
            "width": x1 - x0 + 1,
            "height": y1 - y0 + 1,
            "origin": (x0, y0),
            "spawn": spawn,
            "exit": exit_xy,
            "name": spec["name"],
            "label": spec["label"],
            "bounds": (x0, y0, x1, y1),
        }
        for y in range(max(0, y0), min(height, y1 + 1)):
            for x in range(max(0, x0), min(width, x1 + 1)):
                if _in_rect(x, y, spec["pad"]):
                    continue
                grid[y][x] = GRASS


def _open_entrance_lane(tiles, door_x, door_y):
    """Keep a three-tile-wide walk from the mouth into the dungeon."""
    h = len(tiles)
    w = len(tiles[0]) if h else 0
    for y in range(door_y - 2, door_y + 5):
        for x in range(door_x - 1, door_x + 2):
            if 0 < x < w - 1 and 0 < y < h - 1 and tiles[y][x] not in WALKABLE_TILES:
                tiles[y][x] = FLOOR


def _nearest_walkable(tiles, x, y):
    if _walkable_cell(tiles, x, y):
        return (x, y)
    h = len(tiles)
    w = len(tiles[0]) if h else 0
    for r in range(1, 8):
        for dy in range(-r, r + 1):
            for dx in range(-r, r + 1):
                nx, ny = x + dx, y + dy
                if 0 <= nx < w and 0 <= ny < h and _walkable_cell(tiles, nx, ny):
                    return (nx, ny)
    return (max(0, min(w - 1, x)), max(0, min(h - 1, y)))


def _walkable_cell(tiles, x, y) -> bool:
    if y < 0 or y >= len(tiles) or x < 0 or x >= len(tiles[0]):
        return False
    return tiles[y][x] in WALKABLE_TILES


def dungeon_walkable(tiles, x, y) -> bool:
    return _walkable_cell(tiles, x, y)


def is_explore(dungeon_id: str) -> bool:
    return dungeon_id in REGIONS


def build(session, dungeon_id: str, next_id, monster_cls, spawns) -> None:
    if dungeon_id == "sanctum":
        import feature_flags
        if feature_flags.USE_NEW_VOID_DUNGEON:
            import void_v2
            return void_v2.build(session, next_id, monster_cls, spawns)
    if dungeon_id == "depths":
        import feature_flags
        if feature_flags.USE_NEW_DEPTHS_DUNGEON:
            import depths_v2
            return depths_v2.build(session, next_id, monster_cls, spawns)
    snap = _SNAPSHOTS[dungeon_id]
    tiles = [row[:] for row in snap["tiles"]]
    x0, y0, x1, y1 = snap["bounds"]
    monsters = {}
    for mtype, mx, my in spawns:
        if x0 <= mx <= x1 and y0 <= my <= y1:
            mid = next_id()
            m = monster_cls(mid, mtype, mx - x0, my - y0)
            room = room_containing(mx, my)
            if room:
                rx0, ry0, rx1, ry1 = room
                m.home_room = (rx0 - x0, ry0 - y0, rx1 - x0, ry1 - y0)
            else:
                m.home_room = (m.x - 3, m.y - 3, m.x + 3, m.y + 3)
            monsters[mid] = m
    session.dungeon = {
        "id": dungeon_id,
        "explore": True,
        "floor": 1,
        "floors": 1,
        "label": snap["label"],
        "tiles": tiles,
        "width": snap["width"],
        "height": snap["height"],
        "monsters": monsters,
        "return_x": None,
        "return_y": None,
        "exit_x": snap["exit"][0],
        "exit_y": snap["exit"][1],
        "name": snap["name"],
    }
    props = dungeon_props.install(
        tiles, dungeon_id, 1, snap["spawn"], snap["exit"],
        avoid=[(m.x, m.y) for m in monsters.values()],
    )
    session.dungeon["props"] = props
    session.x, session.y = snap["spawn"]
    session.in_combat_with = None
    session.gathering_node = None
    if session.pet_id:
        session.pet_x, session.pet_y = session.x, session.y
        session.pet_target_id = None
