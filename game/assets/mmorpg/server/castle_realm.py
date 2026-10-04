"""Server-side data plane support for the flag-gated Castle Realm.

The realm is transported through the existing per-player dungeon instance, but
its planes are data-driven rather than combat floors.  This module owns only
loading, conversion, walkability, and transition lookup; the legacy dungeon
code remains responsible for the existing dungeons.
"""
from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

import feature_flags
import world_map as wm


_HERE = Path(__file__).resolve().parent
_ASSET_ROOT = _HERE.parent / "client" / "assets" / "castle_realm"
_SOURCE_ROOT = _HERE.parent.parent / "assets" / "realm_map_and_gothic_pack"

_REALM_TILE_IDS = {
    "GRASS": wm.GRASS,
    "PATH": wm.PATH,
    "WALL": wm.WALL,
    "WATER": wm.WATER,
}
_FLOOR_WALKABLE = set(".DUVE")


def _load_json(filename: str) -> dict:
    """Load a realm data file from the installed client pack or source pack."""
    candidates = (
        _ASSET_ROOT / "json" / filename,
        _SOURCE_ROOT / "json" / filename,
    )
    for path in candidates:
        if path.is_file():
            with path.open(encoding="utf-8") as handle:
                return json.load(handle)
    raise FileNotFoundError(
        f"Castle Realm data file not found: {filename} "
        f"(looked in {', '.join(str(path) for path in candidates)})"
    )


def _load_built_castles():
    """Every castle whose registry status is built and whose data file exists."""
    data = {}
    floors = {}
    for entry in REALM.get("castles", []):
        if entry.get("status") != "built":
            continue
        filename = entry.get("data")
        if not filename:
            continue
        try:
            blob = _load_json(filename)
        except FileNotFoundError:
            continue
        data[entry["id"]] = blob
        for floor in blob.get("floors", []):
            floors[floor["plane"]] = floor
    return data, floors


REALM = _load_json("castle_realm_map.json")
CASTLE_DATA, FLOORS = _load_built_castles()
CASTLES = {castle["id"]: castle for castle in REALM.get("castles", [])}
GOTHIC = CASTLE_DATA.get("gothic", {})

_V2_FILES = (
    "duskspire_interiors_v2.json",
    "white_rose_interiors_v2.json",
    "kings_interiors_v2.json",
    "sky_anchor_interiors_v2.json",
)
# Barracks is a second building on King's Castle. Its world door stays put.
_V2_EXTRA_ARRIVE = {(171, 49): (5, 25)}


def _widen_doors(rows):
    """Turn each one-tile doorway into a three-tile opening."""
    if not rows:
        return rows
    grid = [list(row) for row in rows]
    height, width = len(grid), len(grid[0])
    doors = [(x, y) for y in range(height) for x in range(width) if grid[y][x] == "D"]
    for x, y in doors:
        horizontal = (
            (x > 0 and grid[y][x - 1] == "#")
            or (x + 1 < width and grid[y][x + 1] == "#")
        )
        vertical = (
            (y > 0 and grid[y - 1][x] == "#")
            or (y + 1 < height and grid[y + 1][x] == "#")
        )
        if horizontal:
            for nx in (x - 1, x + 1):
                if 0 < nx < width - 1 and grid[y][nx] == "#":
                    grid[y][nx] = "D"
        if vertical:
            for ny in (y - 1, y + 1):
                if 0 < ny < height - 1 and grid[ny][x] == "#":
                    grid[ny][x] = "D"
    return ["".join(row) for row in grid]


def _load_v2():
    """Interior-only floor rows. Exterior sprites and door world tiles stay v1."""
    floors = {}
    arrives = {}
    if not feature_flags.USE_CASTLE_INTERIORS_V2:
        return floors, arrives
    root = _HERE.parent.parent / "interiors_v2" / "json"
    for filename in _V2_FILES:
        path = root / filename
        if not path.is_file():
            continue
        with path.open(encoding="utf-8") as handle:
            blob = json.load(handle)
        integration = blob.get("integration") or {}
        world_tiles = integration.get("keep_doors_world_tiles_unchanged") or []
        new_arrive = integration.get("new_interior_arrive") or []
        for tile, arrive in zip(world_tiles, new_arrive):
            arrives[(int(tile[0]), int(tile[1]))] = (int(arrive[0]), int(arrive[1]))
        castle_name = blob.get("name") or ""
        for floor in blob.get("floors", []):
            floor = dict(floor)
            floor["v2"] = True
            floor["castle_name"] = castle_name
            floor["rows"] = _widen_doors(floor.get("rows") or [])
            floors[floor["plane"]] = floor
    arrives.update(_V2_EXTRA_ARRIVE)
    return floors, arrives


V2_FLOORS, V2_DOOR_ARRIVE = _load_v2()


def _floor_for(name: str):
    if name in V2_FLOORS:
        return V2_FLOORS[name]
    return FLOORS.get(name)


def _plane_name(plane) -> str:
    if isinstance(plane, str):
        return plane
    if isinstance(plane, dict):
        return str(plane.get("plane") or plane.get("name") or "")
    raise TypeError(f"plane must be a name or mapping, got {type(plane).__name__}")


def _resolve_plane(plane) -> dict:
    name = _plane_name(plane)
    if name == "realm":
        return build_plane("realm")
    if name in FLOORS:
        return build_plane(name)
    raise KeyError(f"unknown Castle Realm plane: {name}")


def _castle_at(x: int, y: int):
    """Return the built castle data whose footprint contains (x, y)."""
    for castle_id, registry in CASTLES.items():
        if registry.get("status") != "built":
            continue
        data = CASTLE_DATA.get(castle_id)
        if not data:
            continue
        x0, y0, x1, y1 = registry.get("footprint", ())
        if x0 <= x <= x1 and y0 <= y <= y1:
            return data
    return None


def _castle_char_at(data: dict, x: int, y: int):
    fp = data.get("footprint", {})
    x0, y0 = int(fp.get("x0", 0)), int(fp.get("y0", 0))
    rows = data.get("walkability", [])
    lx, ly = int(x) - x0, int(y) - y0
    if ly < 0 or ly >= len(rows) or lx < 0 or lx >= len(rows[ly]):
        return None
    return rows[ly][lx]


def _add_transition(transitions: dict, plane: str, x: int, y: int,
                    to_plane: str, arrive, kind: str = "transition") -> None:
    transitions[(int(x), int(y))] = {
        "to_plane": str(to_plane),
        "arrive": [int(arrive[0]), int(arrive[1])],
        "kind": kind,
    }


@lru_cache(maxsize=None)
def build_plane(name: str) -> dict:
    """Build one server tile plane from the realm or gothic data files.

    The returned dictionary intentionally contains only the transport-facing
    fields.  Character-level walkability is retained by :func:`walkable` so a
    castle footprint can defer to its own grid while the client receives the
    normal blocked ``WALL`` tile underneath the sprite.
    """
    name = str(name)
    if name == "realm":
        rows = REALM.get("rows", [])
        width = int(REALM.get("width", len(rows[0]) if rows else 0))
        height = int(REALM.get("height", len(rows)))
        if len(rows) != height or any(len(row) != width for row in rows):
            raise ValueError("castle_realm_map.json has inconsistent realm dimensions")
        legend = REALM.get("legend", {})
        tiles = []
        for row in rows:
            converted = []
            for char in row:
                spec = legend.get(char)
                if not spec:
                    raise ValueError(f"unknown realm tile character: {char!r}")
                # Castle footprint is visually blocked until the castle grid
                # is consulted by walkable().
                converted.append(_REALM_TILE_IDS.get(
                    spec.get("server_tile"), wm.WALL
                ))
            tiles.append(converted)
        transitions = {}
        return_portal = REALM.get("return_portal", {})
        if return_portal:
            _add_transition(
                transitions, name,
                int(return_portal["x"]), int(return_portal["y"]),
                "overworld", REALM["overworld_portal"]["return_arrival"],
                "return_portal",
            )
        for blob in CASTLE_DATA.values():
            for door in blob.get("keep_doors", []):
                wx, wy = int(door["tile"][0]), int(door["tile"][1])
                arrive = V2_DOOR_ARRIVE.get((wx, wy), door["arrive"])
                _add_transition(
                    transitions, name, wx, wy,
                    door["to_plane"], arrive,
                    "keep_door" if door.get("building", "keep") == "keep" else "building_door",
                )
        return {
            "plane": name,
            "tiles": tiles,
            "width": width,
            "height": height,
            "transitions": transitions,
        }

    floor = _floor_for(name)
    if floor is None:
        raise KeyError(f"unknown Castle Realm plane: {name}")
    rows = floor.get("rows", [])
    width = int(floor.get("width", len(rows[0]) if rows else 0))
    height = int(floor.get("height", len(rows)))
    if len(rows) != height or any(len(row) != width for row in rows):
        raise ValueError(f"{name} has inconsistent floor dimensions")
    walkable = set(floor.get("floor_walkable_chars", _FLOOR_WALKABLE))
    walkable.update(_FLOOR_WALKABLE)
    # v2 furniture ('x') blocks walking but is not a wall. Decor never blocks.
    visual_floor = set(walkable)
    if floor.get("v2"):
        visual_floor.add("x")
    tiles = [
        [wm.FLOOR if char in visual_floor else wm.WALL for char in row]
        for row in rows
    ]
    transitions = {}
    for stair in floor.get("stairs", []):
        _add_transition(
            transitions, name, int(stair["tile"][0]), int(stair["tile"][1]),
            stair["to_plane"], stair["arrive"], "stair_" + str(stair.get("dir", "")),
        )
    for exit_tile in floor.get("exits", []):
        _add_transition(
            transitions, name, int(exit_tile["tile"][0]), int(exit_tile["tile"][1]),
            exit_tile["to_plane"], exit_tile["arrive"], "exit",
        )
    return {
        "plane": name,
        "tiles": tiles,
        "width": width,
        "height": height,
        "transitions": transitions,
    }


def walkable(plane, x: int, y: int) -> bool:
    """Return whether a player may stand on a plane tile."""
    name = _plane_name(plane)
    x, y = int(x), int(y)
    if name == "realm":
        rows = REALM.get("rows", [])
        if not (0 <= y < len(rows) and 0 <= x < len(rows[y])):
            return False
        char = rows[y][x]
        if char == "c":
            data = _castle_at(x, y)
            if data is None:
                return False
            castle_char = _castle_char_at(data, x, y)
            return castle_char in set(data.get("walkable_chars", ()))
        spec = REALM.get("legend", {}).get(char, {})
        return bool(spec.get("walkable", False))
    floor = _floor_for(name)
    if floor is None:
        return False
    rows = floor.get("rows", [])
    if not (0 <= y < len(rows) and 0 <= x < len(rows[y])):
        return False
    return rows[y][x] in set(floor.get("floor_walkable_chars", _FLOOR_WALKABLE))


def transition_at(plane, x: int, y: int):
    """Return the transition at a plane coordinate, or ``None``."""
    data = _resolve_plane(plane)
    return data.get("transitions", {}).get((int(x), int(y)))


def enter(session) -> None:
    if session.dungeon:
        raise RuntimeError('session is already inside an instance')
    spawn = REALM.get('spawn', {})
    return_arrival = REALM.get('overworld_portal', {}).get('return_arrival', [32, 34])
    plane = build_plane('realm')
    session.dungeon = {
        'id': 'castle_realm',
        'plane': 'realm',
        'floor': 0,
        'floors': 1,
        'label': 'Castle Realm',
        'name': 'Castle Realm',
        'tiles': plane['tiles'],
        'width': plane['width'],
        'height': plane['height'],
        'monsters': {},
        'transitions': plane['transitions'],
        'exit_x': int(REALM['return_portal']['x']),
        'exit_y': int(REALM['return_portal']['y']),
        'return_x': int(return_arrival[0]),
        'return_y': int(return_arrival[1]),
        'explore': True,
        'realm': True,
    }
    session.x = int(spawn.get('x', 150))
    session.y = int(spawn.get('y', 182))
    session.in_combat_with = None
    session.gathering_node = None
    session.pet_target_id = None
    if getattr(session, 'pet_id', None):
        session.pet_x, session.pet_y = session.x, session.y


def leave(session) -> None:
    data = session.dungeon or {}
    if data.get('id') != 'castle_realm':
        raise ValueError('session is not in Castle Realm')
    x = int(data.get('return_x', 111))
    y = int(data.get('return_y', 45))
    session.dungeon = None
    session.in_combat_with = None
    session.pet_target_id = None
    session.gathering_node = None
    session.x, session.y = x, y
    if getattr(session, 'pet_id', None):
        session.pet_x, session.pet_y = x, y


def floor_story(plane_name: str):
    """Level index, floor count, room name, and castle name for a plane."""
    if plane_name == "realm" or plane_name not in V2_FLOORS:
        return 0, 1, "Castle Realm", "Castle Realm"
    floor = V2_FLOORS[plane_name]
    prefix = plane_name.rsplit("_f", 1)[0]
    mates = [name for name in V2_FLOORS if name.rsplit("_f", 1)[0] == prefix]
    return (
        int(floor.get("level") or 1),
        max(1, len(mates)),
        floor.get("name") or plane_name,
        floor.get("castle_name") or "Castle",
    )


def stair_tiles(plane) -> list:
    """Every stair pad on this floor. Up and down share one staircase."""
    floor = _floor_for(_plane_name(plane)) or {}
    tiles = []
    for stair in floor.get("stairs") or []:
        tile = stair.get("tile") or [0, 0]
        tiles.append((int(tile[0]), int(tile[1])))
    return tiles


def near_stair(plane, x: int, y: int, reach: int = 1) -> bool:
    return any(max(abs(x - tx), abs(y - ty)) <= reach for tx, ty in stair_tiles(plane))


def stair_going(plane, direction: str):
    """The one stair link for this direction, if the floor has it."""
    floor = _floor_for(_plane_name(plane)) or {}
    for stair in floor.get("stairs") or []:
        if str(stair.get("dir") or "") == direction:
            return stair
    return None


def move_to_plane(session, plane_name: str, arrive) -> None:
    data = build_plane(plane_name)
    level, total, title, castle = floor_story(plane_name)
    session.dungeon.update({
        'plane': plane_name,
        'tiles': data['tiles'],
        'width': data['width'],
        'height': data['height'],
        'transitions': data['transitions'],
        'floor': level,
        'floors': total,
        'name': title,
        'label': castle,
    })
    session.x, session.y = int(arrive[0]), int(arrive[1])


def payload(session) -> dict:
    data = session.dungeon or {}
    return {
        'id': 'castle_realm',
        'plane': data.get('plane', 'realm'),
        'floor': data.get('floor', 0),
        'floors': data.get('floors', 1),
        'label': data.get('label', 'Castle Realm'),
        'name': data.get('name', 'Castle Realm'),
        'tiles': data.get('tiles', []),
        'width': data.get('width', 0),
        'height': data.get('height', 0),
        'monsters': [],
        'remaining': 0,
        'player_x': session.x,
        'player_y': session.y,
        'exit_x': data.get('exit_x') if data.get('plane') == 'realm' else -1,
        'exit_y': data.get('exit_y') if data.get('plane') == 'realm' else -1,
        'explore': True,
        'realm': True,
    }



def plane_names() -> tuple[str, ...]:
    """Names available to the current realm data set."""
    return ("realm",) + tuple(FLOORS)