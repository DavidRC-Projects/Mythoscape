"""Decorative props inside private dungeons.

Each floor keeps two 2x2 pads a few tiles into the room from the spawn,
off the exit lane, so they are on screen when you enter. The pads stay
floor tiles; monsters are not spawned on them.
"""
from __future__ import annotations

from world_map import FLOOR, WALKABLE_TILES

# Tidehollow's floors already change creature, so the dressing follows.
_TIDEHOLLOW = {
    1: ("goblin_campfire", "goblin_loot"),
    2: ("goblin_campfire", "goblin_loot"),
    3: ("crypt_sarcophagus", "crypt_candelabra"),
    4: ("crypt_sarcophagus", "crypt_candelabra"),
    5: ("wolf_bone_pile", "wolf_den_bed"),
    6: ("wolf_bone_pile", "wolf_den_bed"),
    7: ("spider_cocoons", "spider_egg_sacs"),
    8: ("spider_cocoons", "spider_egg_sacs"),
    9: ("giant_throne", "giant_table"),
    10: ("dragon_hoard", "dragon_egg_nest"),
}
_BY_ID = {
    "emberdeep": ("dragon_hoard", "dragon_egg_nest"),
    "depths": ("crypt_sarcophagus", "crypt_candelabra"),
    "sanctum": ("void_altar", "void_crystals"),
}


def keys_for(dungeon_id: str, floor: int):
    if dungeon_id == "tidehollow":
        return _TIDEHOLLOW.get(int(floor), _TIDEHOLLOW[1])
    return _BY_ID.get(dungeon_id)


def cells(props) -> set:
    out = set()
    for prop in props or []:
        x, y = int(prop["x"]), int(prop["y"])
        out.update(((x, y), (x + 1, y), (x, y + 1), (x + 1, y + 1)))
    return out


def install(tiles, dungeon_id: str, floor: int, spawn, exit_xy, avoid=()):
    """Carve two pads and return [{key, x, y}, ...] using the pad's top-left tile."""
    keys = keys_for(dungeon_id, floor)
    if not keys or not tiles:
        return []
    avoid = set(avoid or ())
    spots = _pads_near_spawn(tiles, spawn, exit_xy, avoid)
    props = []
    for key, spot in zip(keys, spots):
        _carve_pad(tiles, spot[0], spot[1], spawn)
        props.append({"key": key, "x": int(spot[0]), "y": int(spot[1])})
    return props


def _pads_near_spawn(tiles, spawn, exit_xy, avoid):
    """West and east of the spawn, a few tiles further into the room."""
    h = len(tiles)
    w = len(tiles[0]) if h else 0
    sx, sy = int(spawn[0]), int(spawn[1])
    y = max(1, min(h - 4, sy - 3))
    left_x = max(1, min(w - 5, sx - 6))
    right_x = max(1, min(w - 5, sx + 4))
    if right_x <= left_x + 2:
        left_x = max(1, min(w - 5, sx - 3))
        right_x = max(left_x + 3, min(w - 5, sx + 2))
    left = _shift_clear(tiles, left_x, y, spawn, exit_xy, avoid)
    right = _shift_clear(tiles, right_x, y, spawn, exit_xy, avoid)
    if left == right:
        right = _shift_clear(tiles, min(w - 5, left[0] + 5), left[1], spawn, exit_xy, avoid)
    return [left, right]


def _shift_clear(tiles, x, y, spawn, exit_xy, avoid):
    h = len(tiles)
    w = len(tiles[0]) if h else 0
    for dy in (0, -2, 2, -4, 4, 1, -1):
        for dx in (0, 1, -1, 2, -2, 3, -3):
            nx = max(1, min(w - 5, x + dx))
            ny = max(1, min(h - 4, y + dy))
            if _near((nx, ny), spawn, 3) or _near((nx, ny), exit_xy):
                continue
            cells = ((nx, ny), (nx + 1, ny), (nx, ny + 1), (nx + 1, ny + 1))
            if any(cell in avoid for cell in cells):
                continue
            return (nx, ny)
    return (max(1, min(w - 5, x)), max(1, min(h - 4, y)))


def _carve_pad(tiles, x, y, spawn):
    h = len(tiles)
    w = len(tiles[0]) if h else 0
    for dy in range(0, 3):
        for dx in range(0, 2):
            nx, ny = x + dx, y + dy
            if 0 < nx < w - 1 and 0 < ny < h - 1:
                tiles[ny][nx] = FLOOR
    yy = y + 2
    guard = 0
    while yy < h - 1 and guard < 16 and not _reaches(tiles, x, y, spawn):
        for dx in range(0, 2):
            nx = x + dx
            if 0 < nx < w - 1:
                tiles[yy][nx] = FLOOR
        yy += 1
        guard += 1


def _reaches(tiles, x, y, spawn) -> bool:
    if not _walkable(tiles, spawn[0], spawn[1]):
        return False
    h = len(tiles)
    w = len(tiles[0]) if h else 0
    goal = (x, y)
    seen = {tuple(spawn)}
    q = [tuple(spawn)]
    i = 0
    while i < len(q):
        cx, cy = q[i]
        i += 1
        if abs(cx - goal[0]) + abs(cy - goal[1]) <= 2:
            return True
        for dx, dy in ((0, 1), (0, -1), (1, 0), (-1, 0)):
            nx, ny = cx + dx, cy + dy
            if (nx, ny) in seen:
                continue
            if 0 <= nx < w and 0 <= ny < h and _walkable(tiles, nx, ny):
                seen.add((nx, ny))
                q.append((nx, ny))
    return False


def _walkable(tiles, x, y) -> bool:
    if y < 0 or y >= len(tiles) or x < 0 or x >= len(tiles[0]):
        return False
    return tiles[y][x] in WALKABLE_TILES or tiles[y][x] == FLOOR


def _near(a, b, dist=5) -> bool:
    if not b:
        return False
    return max(abs(int(a[0]) - int(b[0])), abs(int(a[1]) - int(b[1]))) < dist
