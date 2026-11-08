"""Authoritative collision / zone layout — milestone 2 full-perimeter field."""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from typing import Dict, Iterable, List, Optional, Sequence, Set, Tuple

from .constants import (
    DESIGN_ATTACKERS,
    DESIGN_DEFENDERS,
    FORBIDDEN_IDS,
    HEIGHT,
    KEEP_RECT,
    MAP_ID,
    MAP_TITLE,
    OWNERSHIP_KEY_RESERVED,
    PLANE_BATTLEFIELD,
    PLANE_THRONE,
    STAGING_TILES_PER_PLAYER,
    STEP_SECONDS,
    TILE_METERS,
    WALL_E,
    WALL_N,
    WALL_S,
    WALL_THICK,
    WALL_W,
    WIDTH,
)

Coord = Tuple[int, int]
Rect = Tuple[int, int, int, int]

WALK = "."
ROAD = "="
STONE = ","
WALL = "#"
WATER = "~"
TREE = "T"
GATE = "G"
PALISADE = "P"
WALLWALK = "H"


def _rect(x0: int, y0: int, x1: int, y1: int) -> Rect:
    return (int(x0), int(y0), int(x1), int(y1))


def _inside(rect: Rect, x: int, y: int) -> bool:
    x0, y0, x1, y1 = rect
    return x0 <= x <= x1 and y0 <= y <= y1


def _fill(grid: List[List[str]], rect: Rect, ch: str) -> None:
    x0, y0, x1, y1 = rect
    for y in range(max(0, y0), min(HEIGHT, y1 + 1)):
        row = grid[y]
        for x in range(max(0, x0), min(WIDTH, x1 + 1)):
            row[x] = ch


def _frame(grid: List[List[str]], rect: Rect, ch: str, thickness: int) -> None:
    x0, y0, x1, y1 = rect
    for t in range(thickness):
        _fill(grid, _rect(x0 + t, y0 + t, x1 - t, y0 + t), ch)
        _fill(grid, _rect(x0 + t, y1 - t, x1 - t, y1 - t), ch)
        _fill(grid, _rect(x0 + t, y0 + t, x0 + t, y1 - t), ch)
        _fill(grid, _rect(x1 - t, y0 + t, x1 - t, y1 - t), ch)


def _center(rect: Rect) -> Coord:
    return ((rect[0] + rect[2]) // 2, (rect[1] + rect[3]) // 2)


def _area(rect: Rect) -> int:
    return max(0, rect[2] - rect[0] + 1) * max(0, rect[3] - rect[1] + 1)


def _width(rect: Rect) -> int:
    return rect[2] - rect[0] + 1


@dataclass
class Opening:
    opening_id: str
    name: str
    rect: Rect
    default_state: str = "intact"

    @property
    def width_tiles(self) -> int:
        return _width(self.rect)

    @property
    def passage_tiles(self) -> int:
        """Clear opening measured along the longer axis (people walking through)."""
        return max(_width(self.rect), self.rect[3] - self.rect[1] + 1)


@dataclass
class Landmark:
    landmark_id: str
    name: str
    kind: str
    rect: Rect
    note: str = ""


@dataclass
class Plane:
    plane_id: str
    name: str
    width: int
    height: int
    grid: List[List[str]]
    openings: Dict[str, Opening] = field(default_factory=dict)
    landmarks: Dict[str, Landmark] = field(default_factory=dict)
    spawn: Dict[str, Coord] = field(default_factory=dict)

    def in_bounds(self, x: int, y: int) -> bool:
        return 0 <= x < self.width and 0 <= y < self.height

    def cell(self, x: int, y: int) -> str:
        return self.grid[y][x]


@dataclass
class Battlefield:
    plane: Plane
    throne: Plane
    gate_states: Dict[str, str] = field(default_factory=dict)
    wall_box: Rect = (WALL_W, WALL_N, WALL_E, WALL_S)
    keep_rect: Rect = KEEP_RECT
    interior_rect: Rect = (0, 0, 0, 0)
    wall_tiles: Set[Coord] = field(default_factory=set)
    gate_tiles: Set[Coord] = field(default_factory=set)
    circulation: Set[Coord] = field(default_factory=set)
    build_exclusion: Set[Coord] = field(default_factory=set)

    @property
    def map_id(self) -> str:
        return MAP_ID


def _opening_blocked(ch: str, x: int, y: int, openings: Sequence[Opening], states: Dict[str, str]) -> bool:
    if ch == WALLWALK:
        return False
    if ch != GATE:
        return ch in {WALL, WATER, TREE, PALISADE}
    for op in openings:
        if _inside(op.rect, x, y):
            return states.get(op.opening_id, op.default_state) != "destroyed"
    return True


def walkable(plane: Plane, x: int, y: int, gate_states: Optional[Dict[str, str]] = None) -> bool:
    if not plane.in_bounds(x, y):
        return False
    states = gate_states or {op.opening_id: op.default_state for op in plane.openings.values()}
    return not _opening_blocked(plane.cell(x, y), x, y, list(plane.openings.values()), states)


def neighbors(x: int, y: int) -> Iterable[Coord]:
    yield x + 1, y
    yield x - 1, y
    yield x, y + 1
    yield x, y - 1


def bfs(plane: Plane, start: Coord, gate_states: Optional[Dict[str, str]] = None) -> set:
    if not walkable(plane, start[0], start[1], gate_states):
        return set()
    seen = {start}
    q = deque([start])
    while q:
        x, y = q.popleft()
        for nx, ny in neighbors(x, y):
            if (nx, ny) in seen:
                continue
            if walkable(plane, nx, ny, gate_states):
                seen.add((nx, ny))
                q.append((nx, ny))
    return seen


def path_exists(plane: Plane, a: Coord, b: Coord, gate_states: Optional[Dict[str, str]] = None) -> bool:
    return b in bfs(plane, a, gate_states)


def shortest_length(plane: Plane, a: Coord, b: Coord, gate_states: Optional[Dict[str, str]] = None) -> Optional[int]:
    if not walkable(plane, a[0], a[1], gate_states):
        return None
    seen = {a: 0}
    q = deque([a])
    while q:
        x, y = q.popleft()
        d = seen[(x, y)]
        if (x, y) == b:
            return d
        for nx, ny in neighbors(x, y):
            if (nx, ny) in seen:
                continue
            if walkable(plane, nx, ny, gate_states):
                seen[(nx, ny)] = d + 1
                q.append((nx, ny))
    return None


def travel_seconds(tiles: int) -> float:
    return round(tiles * STEP_SECONDS, 2)


def build_throne_room() -> Plane:
    w, h = 72, 44
    grid = [[STONE for _ in range(w)] for _ in range(h)]
    _frame(grid, _rect(0, 0, w - 1, h - 1), WALL, 2)
    nave_x0, nave_x1 = 28, 43
    for x in (18, 22, 49, 53):
        for y in range(8, h - 6, 6):
            _fill(grid, _rect(x, y, x + 1, y + 1), WALL)
    dais = _rect(24, 4, 47, 11)
    _fill(grid, dais, STONE)
    throne = _rect(33, 5, 38, 8)
    _fill(grid, throne, WALL)
    entrance = _rect(30, h - 3, 41, h - 1)
    _fill(grid, entrance, GATE)
    opening = Opening("throne_doors", "Throne Room Doors", entrance, "destroyed")
    return Plane(
        plane_id=PLANE_THRONE,
        name="Throne Room",
        width=w, height=h, grid=grid,
        openings={"throne_doors": opening},
        landmarks={
            "dais": Landmark("dais", "Royal Dais", "objective", dais, "Last-stand objective"),
            "nave": Landmark("nave", "Hall Nave", "route", _rect(nave_x0, 12, nave_x1, h - 4)),
        },
        spawn={"entrance": _center(entrance), "dais": (36, 10)},
    )


def build_battlefield(gate_states: Optional[Dict[str, str]] = None) -> Battlefield:
    if MAP_ID in FORBIDDEN_IDS or OWNERSHIP_KEY_RESERVED in FORBIDDEN_IDS:
        raise RuntimeError("namespace collision with live Castle Realm ids")

    grid = [[WALK for _ in range(WIDTH)] for _ in range(HEIGHT)]
    ww, wn, we, ws = WALL_W, WALL_N, WALL_E, WALL_S
    thick = WALL_THICK
    outer = _rect(ww, wn, we, ws)
    interior = _rect(ww + thick, wn + thick, we - thick, ws - thick)

    # Flank ditches (crossed by the ring road and extra bridges)
    west_ditch = _rect(ww - 36, wn + 8, ww - 33, ws - 8)
    east_ditch = _rect(we + 33, wn + 8, we + 36, ws - 8)
    _fill(grid, west_ditch, WATER)
    _fill(grid, east_ditch, WATER)

    # Perimeter ring road — circulation around the whole castle
    inset, ring_w = 12, 6
    ring_outer = _rect(ww - inset - ring_w, wn - inset - ring_w, we + inset + ring_w, ws + inset + ring_w)
    ring_inner = _rect(ww - inset, wn - inset, we + inset, ws + inset)
    _frame(grid, ring_outer, ROAD, ring_w)

    # Approach lanes from each cardinal staging to the facing wall
    south_lane = _rect((ww + we) // 2 - 10, ws + 1, (ww + we) // 2 + 10, HEIGHT - 8)
    north_lane = _rect((ww + we) // 2 - 8, 8, (ww + we) // 2 + 8, wn - 1)
    west_lane = _rect(8, (wn + ws) // 2 - 8, ww - 1, (wn + ws) // 2 + 8)
    east_lane = _rect(we + 1, (wn + ws) // 2 - 8, WIDTH - 8, (wn + ws) // 2 + 8)
    for lane in (south_lane, north_lane, west_lane, east_lane):
        _fill(grid, lane, ROAD)

    # Extra ditch bridges so water never cuts the ring or a side lane
    _fill(grid, _rect(west_ditch[0], west_lane[1], west_ditch[2], west_lane[3]), ROAD)
    _fill(grid, _rect(east_ditch[0], east_lane[1], east_ditch[2], east_lane[3]), ROAD)
    _fill(grid, _rect(west_ditch[0], ring_inner[1] - 2, west_ditch[2], ring_inner[1] + 2), ROAD)
    _fill(grid, _rect(east_ditch[0], ring_inner[1] - 2, east_ditch[2], ring_inner[1] + 2), ROAD)
    _fill(grid, _rect(west_ditch[0], ring_inner[3] - 2, west_ditch[2], ring_inner[3] + 2), ROAD)
    _fill(grid, _rect(east_ditch[0], ring_inner[3] - 2, east_ditch[2], ring_inner[3] + 2), ROAD)

    # Sparse trees — off the ring
    for x, y in ((10, 10), (16, 24), (26, 18), (WIDTH - 12, 14), (WIDTH - 20, 28),
                 (12, HEIGHT - 14), (22, HEIGHT - 22), (WIDTH - 14, HEIGHT - 16),
                 (40, 40), (WIDTH - 42, 38), (36, HEIGHT - 36), (WIDTH - 38, HEIGHT - 40)):
        if 0 <= x < WIDTH and 0 <= y < HEIGHT and grid[y][x] == WALK:
            grid[y][x] = TREE

    # Curtain walls
    _frame(grid, outer, WALL, thick)
    _fill(grid, interior, STONE)

    # Inner wall-walk: innermost 2 tiles of the 6-thick curtain
    for t in (thick - 2, thick - 1):
        _fill(grid, _rect(ww + t, wn + t, we - t, wn + t), WALLWALK)
        _fill(grid, _rect(ww + t, ws - t, we - t, ws - t), WALLWALK)
        _fill(grid, _rect(ww + t, wn + t, ww + t, ws - t), WALLWALK)
        _fill(grid, _rect(we - t, wn + t, we - t, ws - t), WALLWALK)

    # Keep inside courtyard — leaves a northern inner passage to the north wall-walk
    keep = _rect(*KEEP_RECT)
    _fill(grid, keep, WALL)
    keep_door = _rect(keep[0] + 14, keep[3], keep[2] - 14, keep[3] + 2)
    _fill(grid, keep_door, GATE)

    def tower(cx: int, cy: int, r: int = 5) -> Rect:
        rec = _rect(cx - r, cy - r, cx + r, cy + r)
        _fill(grid, rec, WALL)
        return rec

    towers = {
        "nw_tower": tower(ww + 4, wn + 4, 6),
        "ne_tower": tower(we - 4, wn + 4, 6),
        "sw_tower": tower(ww + 4, ws - 4, 6),
        "se_tower": tower(we - 4, ws - 4, 6),
    }
    # Re-cut the inner wall-walk through solid corner towers so defenders
    # can circuit the curtain.
    for t in (thick - 2, thick - 1):
        _fill(grid, _rect(ww + t, wn + t, we - t, wn + t), WALLWALK)
        _fill(grid, _rect(ww + t, ws - t, we - t, ws - t), WALLWALK)
        _fill(grid, _rect(ww + t, wn + t, ww + t, ws - t), WALLWALK)
        _fill(grid, _rect(we - t, wn + t, we - t, ws - t), WALLWALK)
    # Stairs: walkable 2x2 from courtyard into the wall-walk at each tower
    stair_pts = [
        (ww + thick, wn + thick),
        (we - thick - 1, wn + thick),
        (ww + thick, ws - thick - 1),
        (we - thick - 1, ws - thick - 1),
    ]
    for sx, sy in stair_pts:
        _fill(grid, _rect(sx, sy, sx + 1, sy + 1), WALLWALK)
        _fill(grid, _rect(sx - 1, sy - 1, sx + 2, sy + 2), WALLWALK)

    # Perimeter openings — gates plus wall-breach panels on every side
    main_gate = _rect((ww + we) // 2 - 11, ws - thick + 1, (ww + we) // 2 + 11, ws)
    north_gate = _rect((ww + we) // 2 - 7, wn, (ww + we) // 2 + 6, wn + thick - 1)
    west_gate = _rect(ww, (wn + ws) // 2 - 7, ww + thick - 1, (wn + ws) // 2 + 7)
    east_gate = _rect(we - thick + 1, (wn + ws) // 2 - 7, we, (wn + ws) // 2 + 7)
    west_breach = _rect(ww, wn + 22, ww + thick - 1, wn + 33)
    east_breach = _rect(we - thick + 1, wn + 22, we, wn + 33)
    north_west_breach = _rect(ww + 18, wn, ww + 29, wn + thick - 1)
    north_east_breach = _rect(we - 29, wn, we - 18, wn + thick - 1)
    south_west_breach = _rect(ww + 18, ws - thick + 1, ww + 29, ws)
    south_east_breach = _rect(we - 29, ws - thick + 1, we - 18, ws)
    for rec in (main_gate, north_gate, west_gate, east_gate, west_breach, east_breach,
                north_west_breach, north_east_breach, south_west_breach, south_east_breach):
        _fill(grid, rec, GATE)
    _fill(grid, keep_door, GATE)

    # Restore the innermost wall-walk across gatehouses so an intact gate
    # still blocks the exterior, but defenders can circuit the curtain.
    for t in (thick - 2, thick - 1):
        for rec in (
            _rect(ww + t, wn + t, we - t, wn + t),
            _rect(ww + t, ws - t, we - t, ws - t),
            _rect(ww + t, wn + t, ww + t, ws - t),
            _rect(we - t, wn + t, we - t, ws - t),
        ):
            x0, y0, x1, y1 = rec
            for y in range(y0, y1 + 1):
                for x in range(x0, x1 + 1):
                    if 0 <= x < WIDTH and 0 <= y < HEIGHT and grid[y][x] == GATE:
                        if not (keep_door[0] <= x <= keep_door[2] and keep_door[1] <= y <= keep_door[3]):
                            grid[y][x] = WALLWALK

    openings = {
        "main_gate": Opening("main_gate", "Main Gatehouse", main_gate),
        "north_gate": Opening("north_gate", "North Postern", north_gate),
        "west_gate": Opening("west_gate", "West Postern", west_gate),
        "east_gate": Opening("east_gate", "East Postern", east_gate),
        "west_wall_breach": Opening("west_wall_breach", "West Curtain Breach", west_breach),
        "east_wall_breach": Opening("east_wall_breach", "East Curtain Breach", east_breach),
        "north_west_breach": Opening("north_west_breach", "Northwest Curtain Breach", north_west_breach),
        "north_east_breach": Opening("north_east_breach", "Northeast Curtain Breach", north_east_breach),
        "south_west_breach": Opening("south_west_breach", "Southwest Curtain Breach", south_west_breach),
        "south_east_breach": Opening("south_east_breach", "Southeast Curtain Breach", south_east_breach),
        "keep_doors": Opening("keep_doors", "Keep Doors", keep_door),
    }

    staging_south = _rect(24, ws + 28, WIDTH - 25, HEIGHT - 6)
    staging_north = _rect(24, 6, WIDTH - 25, wn - 22)
    staging_west = _rect(6, wn - 4, ww - 40, ws + 4)
    staging_east = _rect(we + 40, wn - 4, WIDTH - 7, ws + 4)
    defend_west = _rect(interior[0] + 2, interior[1] + 8, keep[0] - 4, interior[3] - 4)
    defend_east = _rect(keep[2] + 4, interior[1] + 8, interior[2] - 2, interior[3] - 4)
    north_inner = _rect(interior[0] + 4, interior[1], interior[2] - 4, keep[1] - 1)

    landmarks = {
        "attacker_staging": Landmark("attacker_staging", "South Attacker Staging", "staging", staging_south,
                                     f"Primary southern camp for {DESIGN_ATTACKERS} design slots (shared with other sides)"),
        "staging_south": Landmark("staging_south", "South Staging", "staging", staging_south),
        "staging_north": Landmark("staging_north", "North Staging", "staging", staging_north),
        "staging_west": Landmark("staging_west", "West Staging", "staging", staging_west),
        "staging_east": Landmark("staging_east", "East Staging", "staging", staging_east),
        "defender_west": Landmark("defender_west", "West Defender Staging", "staging", defend_west),
        "defender_east": Landmark("defender_east", "East Defender Staging", "staging", defend_east),
        "courtyard": Landmark("courtyard", "Courtyard", "objective", interior, "Inner bailey rings the keep"),
        "keep": Landmark("keep", "Royal Keep", "objective", keep, "Inside courtyard; north passage remains"),
        "north_inner": Landmark("north_inner", "North Inner Passage", "route", north_inner,
                                "Courtyard path north of the keep — keep does not seal the north"),
        "center_lane": Landmark("center_lane", "South Approach", "route",
                                _rect(south_lane[0], ws + 1, south_lane[2], min(south_lane[3], staging_south[1] + 4))),
        "north_lane": Landmark("north_lane", "North Approach", "route",
                               _rect(north_lane[0], north_lane[1], north_lane[2], wn - 1)),
        "west_lane": Landmark("west_lane", "West Approach", "route",
                              _rect(west_lane[0], west_lane[1], ww - 1, west_lane[3])),
        "east_lane": Landmark("east_lane", "East Approach", "route",
                              _rect(we + 1, east_lane[1], east_lane[2], east_lane[3])),
        "ring_route": Landmark("ring_route", "Perimeter Ring Road", "route", ring_outer,
                               "Reserved circulation around all four sides"),
        "heal_defend": Landmark("heal_defend", "Defender Healing", "station",
                                _rect((ww + we) // 2 - 6, keep[3] + 4, (ww + we) // 2 + 6, keep[3] + 10)),
        "eng_defend": Landmark("eng_defend", "Defender Engineering", "station",
                               _rect(keep[2] + 6, (wn + ws) // 2 - 4, keep[2] + 16, (wn + ws) // 2 + 4)),
        "res_defend": Landmark("res_defend", "Defender Resources", "station",
                               _rect(keep[0] - 16, (wn + ws) // 2 - 4, keep[0] - 6, (wn + ws) // 2 + 4)),
        "heal_attack": Landmark("heal_attack", "Attacker Healing (example station)", "station",
                                _rect((ww + we) // 2 - 6, HEIGHT - 16, (ww + we) // 2 + 6, HEIGHT - 10),
                                "Example service area — not the only legal build slot"),
        "eng_attack": Landmark("eng_attack", "Attacker Engineering (example station)", "station",
                               _rect(40, HEIGHT - 18, 52, HEIGHT - 12),
                               "Example service area — engines may be placed around the perimeter"),
        "res_attack": Landmark("res_attack", "Attacker Resources (example station)", "station",
                               _rect(WIDTH - 52, HEIGHT - 18, WIDTH - 40, HEIGHT - 12)),
    }
    for key, rec in towers.items():
        landmarks[key] = Landmark(key, key.replace("_", " ").title(), "tower", rec)

    spawn = {
        "attacker": _center(staging_south),
        "attacker_north": _center(staging_north),
        "attacker_west": _center(staging_west),
        "attacker_east": _center(staging_east),
        "defender": ((ww + we) // 2, keep[3] + 8),
        "main_gate_south": ((main_gate[0] + main_gate[2]) // 2, main_gate[3] + 3),
        "north_gate_north": ((north_gate[0] + north_gate[2]) // 2, north_gate[1] - 3),
        "courtyard": ((ww + we) // 2, keep[3] + 8),
        "keep_door": _center(keep_door),
        "north_inner": _center(north_inner),
        "ring_sw": (ring_inner[0] - ring_w // 2, ring_inner[3] + 2),
        "ring_nw": (ring_inner[0] - ring_w // 2, ring_inner[1] - 2),
        "ring_ne": (ring_inner[2] + ring_w // 2, ring_inner[1] - 2),
        "ring_se": (ring_inner[2] + ring_w // 2, ring_inner[3] + 2),
    }

    plane = Plane(
        plane_id=PLANE_BATTLEFIELD, name=MAP_TITLE,
        width=WIDTH, height=HEIGHT, grid=grid,
        openings=openings, landmarks=landmarks, spawn=spawn,
    )

    # Circulation: ring-road tiles plus a tile in front of every exterior opening
    circulation: Set[Coord] = set()
    for y in range(ring_outer[1], ring_outer[3] + 1):
        for x in range(ring_outer[0], ring_outer[2] + 1):
            if not _inside(ring_inner, x, y) and plane.in_bounds(x, y) and grid[y][x] == ROAD:
                circulation.add((x, y))
    # Gate tiles themselves stay unbuildable via terrain 'G'. Do not reserve
    # the exterior contact apron — rams and towers need those wall-adjacent tiles.

    wall_tiles: Set[Coord] = set()
    gate_tiles: Set[Coord] = set()
    for y in range(HEIGHT):
        for x in range(WIDTH):
            if grid[y][x] == WALL:
                wall_tiles.add((x, y))
            elif grid[y][x] == GATE:
                gate_tiles.add((x, y))

    build_exclusion: Set[Coord] = set()
    for y in range(interior[1], interior[3] + 1):
        for x in range(interior[0], interior[2] + 1):
            build_exclusion.add((x, y))
    for y in range(keep[1], keep[3] + 1):
        for x in range(keep[0], keep[2] + 1):
            build_exclusion.add((x, y))

    states = {oid: op.default_state for oid, op in openings.items()}
    if gate_states:
        states.update(gate_states)
    return Battlefield(
        plane=plane, throne=build_throne_room(), gate_states=states,
        wall_box=(ww, wn, we, ws), keep_rect=keep, interior_rect=interior,
        wall_tiles=wall_tiles, gate_tiles=gate_tiles,
        circulation=circulation, build_exclusion=build_exclusion,
    )


def staging_capacity(bf: Battlefield) -> Dict[str, int]:
    atk = sum(_area(bf.plane.landmarks[k].rect) for k in (
        "staging_south", "staging_north", "staging_west", "staging_east",
    ))
    dfn = sum(_area(bf.plane.landmarks[k].rect) for k in ("defender_west", "defender_east"))
    return {
        "attacker_tiles": atk,
        "defender_tiles": dfn,
        "attacker_design_slots": atk // STAGING_TILES_PER_PLAYER,
        "defender_design_slots": dfn // STAGING_TILES_PER_PLAYER,
    }


def future_integration_points(bf: Battlefield) -> Dict[str, object]:
    return {
        "map_id": MAP_ID,
        "ownership_key_reserved": OWNERSHIP_KEY_RESERVED,
        "do_not_use_ids": sorted(FORBIDDEN_IDS),
        "planes": [bf.plane.plane_id, bf.throne.plane_id],
        "openings": {
            oid: {
                "name": op.name,
                "rect": list(op.rect),
                "width_tiles": op.width_tiles,
                "states": ["intact", "damaged", "destroyed"],
                "walkable_when": "destroyed",
            }
            for oid, op in bf.plane.openings.items()
        },
        "engine_placement": (
            "Player-built footprints validated by placement.py. "
            "Stations are service examples, not exclusive build slots. "
            "No resource costs or caps are approved here."
        ),
        "note": "Server combat, engineering XP, elimination and ownership remain unwired.",
    }


def scale_report(bf: Battlefield) -> Dict[str, object]:
    cap = staging_capacity(bf)
    intact = {k: "intact" for k in bf.plane.openings}
    open_main = dict(intact)
    open_main["main_gate"] = "destroyed"
    start = bf.plane.spawn["attacker"]
    north = bf.plane.spawn["attacker_north"]
    west = bf.plane.spawn["ring_nw"]
    gate = bf.plane.spawn["main_gate_south"]
    court = bf.plane.spawn["courtyard"]
    inner = bf.plane.spawn["north_inner"]
    return {
        "tile_meters": TILE_METERS,
        "step_seconds": STEP_SECONDS,
        "map_tiles": [WIDTH, HEIGHT],
        "map_meters": [round(WIDTH * TILE_METERS, 1), round(HEIGHT * TILE_METERS, 1)],
        "attacker_to_gate_tiles": shortest_length(bf.plane, start, gate, intact),
        "attacker_to_gate_seconds": travel_seconds(shortest_length(bf.plane, start, gate, intact) or 0),
        "south_to_north_via_west_tiles": shortest_length(bf.plane, start, north, intact),
        "south_to_north_via_west_seconds": travel_seconds(shortest_length(bf.plane, start, north, intact) or 0),
        "attacker_to_courtyard_via_main_tiles": shortest_length(bf.plane, start, court, open_main),
        "attacker_to_courtyard_via_main_seconds": travel_seconds(shortest_length(bf.plane, start, court, open_main) or 0),
        "courtyard_to_north_inner_tiles": shortest_length(bf.plane, court, inner, open_main),
        "ring_sw_to_ring_nw_tiles": shortest_length(bf.plane, bf.plane.spawn["ring_sw"], west, intact),
        "main_gate_width_tiles": bf.plane.openings["main_gate"].width_tiles,
        "north_gate_width_tiles": bf.plane.openings["north_gate"].width_tiles,
        "west_gate_width_tiles": bf.plane.openings["west_gate"].width_tiles,
        "east_gate_width_tiles": bf.plane.openings["east_gate"].width_tiles,
        "staging": cap,
    }
