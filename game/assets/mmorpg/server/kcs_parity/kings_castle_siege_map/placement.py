"""Player-built siege-equipment placement prototype.

Pictured engines on landscape plates are scenery only. This module models
independently placed footprints with validation. It does not set resource
costs, cooldowns, or approved army caps.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Sequence, Tuple

from .constants import HEIGHT, WIDTH
from .layout import (
    Battlefield,
    Coord,
    Rect,
    path_exists,
    walkable,
)

# Terrain the engines may sit on (exterior earth/road). Interior stone is excluded.
BUILD_GROUND = frozenset({".", "="})
BLOCKING = frozenset({"#", "~", "T", "P", "G", "H"})


@dataclass(frozen=True)
class EngineSpec:
    engine_type: str
    name: str
    width: int
    height: int
    wall_contact: bool
    setback_min: int = 0
    setback_max: int = 99
    operating_margin: int = 1
    note: str = ""
    stance: str = "assault"
    covers_opening: bool = False


SPECS: Dict[str, EngineSpec] = {
    "ram": EngineSpec(
        "ram", "Battering ram", 3, 4, wall_contact=True,
        note="Needs an exterior wall or gate edge to push against.",
    ),
    "trebuchet": EngineSpec(
        "trebuchet", "Trebuchet", 4, 4, wall_contact=False,
        setback_min=8, setback_max=40,
        note="Needs open exterior ground set back from the curtain.",
    ),
    "siege_tower": EngineSpec(
        "siege_tower", "Siege tower", 3, 4, wall_contact=True,
        note="Needs wall contact so it can be rolled up to the curtain.",
    ),
    "ladder": EngineSpec(
        "ladder", "Siege ladder", 2, 3, wall_contact=True,
        operating_margin=0,
        note="Needs wall contact; small footprint.",
    ),
    "ballista": EngineSpec(
        "ballista", "Ballista", 2, 1, wall_contact=False,
        operating_margin=0, stance="defense",
        note="Sits on the wall-walk and must face out.",
    ),
    "cauldron": EngineSpec(
        "cauldron", "Cauldron", 2, 1, wall_contact=False,
        operating_margin=0, stance="defense", covers_opening=True,
        note="Sits on the wall-walk over a gate or breach and faces out.",
    ),
}

# Same quarter-turns as kcs_balance.FACE. Kept here so the map module does not
# import the server.
_OUT = {0: (0, -1), 90: (1, 0), 180: (0, 1), 270: (-1, 0)}


def rotated_size(spec: EngineSpec, rotation: int) -> Tuple[int, int]:
    rotation = int(rotation) % 360
    if rotation % 180 == 0:
        return spec.width, spec.height
    return spec.height, spec.width


def footprint(x: int, y: int, w: int, h: int) -> List[Coord]:
    return [(x + dx, y + dy) for dy in range(h) for dx in range(w)]


def footprint_rect(x: int, y: int, w: int, h: int) -> Rect:
    return (x, y, x + w - 1, y + h - 1)


@dataclass
class PlacedEngine:
    engine_id: str
    engine_type: str
    x: int
    y: int
    rotation: int = 0

    def spec(self) -> EngineSpec:
        return SPECS[self.engine_type]

    def size(self) -> Tuple[int, int]:
        return rotated_size(self.spec(), self.rotation)

    def tiles(self) -> List[Coord]:
        w, h = self.size()
        return footprint(self.x, self.y, w, h)

    def rect(self) -> Rect:
        w, h = self.size()
        return footprint_rect(self.x, self.y, w, h)

    def padded_tiles(self) -> List[Coord]:
        margin = self.spec().operating_margin
        w, h = self.size()
        return footprint(self.x - margin, self.y - margin, w + margin * 2, h + margin * 2)


@dataclass
class PlacementResult:
    ok: bool
    reason: str
    tiles: List[Coord] = field(default_factory=list)


def _inside_keep(bf: Battlefield, x: int, y: int) -> bool:
    rec = bf.keep_rect
    return rec[0] <= x <= rec[2] and rec[1] <= y <= rec[3]


def _inside_courtyard(bf: Battlefield, x: int, y: int) -> bool:
    rec = bf.interior_rect
    return rec[0] <= x <= rec[2] and rec[1] <= y <= rec[3]


def _manhattan_to_curtain(bf: Battlefield, x: int, y: int) -> int:
    """Manhattan distance to the outer face of the curtain (wall_box)."""
    ww, wn, we, ws = bf.wall_box
    if ww <= x <= we and wn <= y <= ws:
        return min(x - ww, we - x, y - wn, ws - y)
    dx = 0 if ww <= x <= we else (ww - x if x < ww else x - we)
    dy = 0 if wn <= y <= ws else (wn - y if y < wn else y - ws)
    return dx + dy


def _nearest_wall_dist(bf: Battlefield, tiles: Sequence[Coord]) -> Optional[int]:
    if not bf.wall_tiles:
        return None
    return min(_manhattan_to_curtain(bf, x, y) for x, y in tiles)


def _touches_wall(bf: Battlefield, tiles: Sequence[Coord]) -> bool:
    wallish = bf.wall_tiles | bf.gate_tiles
    for x, y in tiles:
        for nx, ny in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)):
            if (nx, ny) in wallish:
                return True
    return False


def _faces_outward(bf: Battlefield, tiles: Sequence[Coord], rotation: int) -> bool:
    rec = bf.interior_rect
    mx = (rec[0] + rec[2]) / 2.0
    my = (rec[1] + rec[3]) / 2.0
    cx = sum(t[0] for t in tiles) / len(tiles)
    cy = sum(t[1] for t in tiles) / len(tiles)
    fdx, fdy = _OUT[int(rotation) % 360]
    return (cx - mx) * fdx + (cy - my) * fdy > 0


def _covers_opening(bf: Battlefield, tiles: Sequence[Coord]) -> bool:
    for x, y in tiles:
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                if (x + dx, y + dy) in bf.gate_tiles:
                    return True
    return False


def _padded_overlap(x, y, w, h, margin, existing) -> bool:
    proposed = set(footprint(x - margin, y - margin, w + margin * 2, h + margin * 2))
    for other in existing or ():
        if proposed & set(other.padded_tiles()):
            return True
    return False


def _validate_defense(bf, spec, x, y, rotation, tiles, existing) -> PlacementResult:
    w, h = rotated_size(spec, rotation)
    for tx, ty in tiles:
        if (tx, ty) in bf.build_exclusion or _inside_keep(bf, tx, ty):
            return PlacementResult(False, "Defensive engines sit on the wall-walk.", tiles)
        if bf.plane.cell(tx, ty) != "H":
            return PlacementResult(False, "Defensive engines sit on the wall-walk.", tiles)
    if int(rotation) % 360 not in _OUT or not _faces_outward(bf, tiles, rotation):
        return PlacementResult(False, f"{spec.name} must face out from the wall.", tiles)
    if spec.covers_opening and not _covers_opening(bf, tiles):
        return PlacementResult(False, f"{spec.name} must sit on the wall-walk over a gate or breach.", tiles)
    if _padded_overlap(x, y, w, h, spec.operating_margin, existing):
        return PlacementResult(False, "Overlaps another engine or its operating space.", tiles)
    return PlacementResult(True, "Valid placement.", tiles)


def validate_placement(
    bf: Battlefield,
    engine_type: str,
    x: int,
    y: int,
    rotation: int = 0,
    existing: Optional[Sequence[PlacedEngine]] = None,
) -> PlacementResult:
    if engine_type not in SPECS:
        return PlacementResult(False, f"Unknown engine type {engine_type!r}.")
    spec = SPECS[engine_type]
    w, h = rotated_size(spec, rotation)
    tiles = footprint(x, y, w, h)
    if any(tx < 0 or ty < 0 or tx >= WIDTH or ty >= HEIGHT for tx, ty in tiles):
        return PlacementResult(False, "Out of bounds.", tiles)
    if spec.stance == "defense":
        return _validate_defense(bf, spec, x, y, rotation, tiles, existing)
    for tx, ty in tiles:
        if _inside_keep(bf, tx, ty):
            return PlacementResult(False, "Cannot build on the keep.", tiles)
        if _inside_courtyard(bf, tx, ty):
            return PlacementResult(False, "Cannot build inside the courtyard.", tiles)
        if (tx, ty) in bf.circulation:
            return PlacementResult(False, "Would block a ring or gate circulation route.", tiles)
        ch = bf.plane.cell(tx, ty)
        if ch not in BUILD_GROUND:
            if ch == "~":
                return PlacementResult(False, "Cannot build on water.", tiles)
            if ch in {"#", "H"}:
                return PlacementResult(False, "Cannot build on walls or wall-walks.", tiles)
            if ch == "G":
                return PlacementResult(False, "Cannot build on a gate opening.", tiles)
            return PlacementResult(False, f"Illegal terrain ({ch}).", tiles)
        # Even walkable cells reserved as interior exclusion (belt just inside)
        if (tx, ty) in bf.build_exclusion:
            return PlacementResult(False, "Excluded interior or reserved ground.", tiles)
    if spec.wall_contact and not _touches_wall(bf, tiles):
        return PlacementResult(False, f"{spec.name} must touch an exterior wall or gate.", tiles)
    if not spec.wall_contact:
        dist = _nearest_wall_dist(bf, tiles)
        if dist is None:
            return PlacementResult(False, "No curtain wall found.", tiles)
        if dist < spec.setback_min:
            return PlacementResult(False, f"{spec.name} is too close to the wall (needs setback).", tiles)
        if dist > spec.setback_max:
            return PlacementResult(False, f"{spec.name} is too far from the wall to be useful.", tiles)
    # Overlap + operating space
    proposed = set()
    margin = spec.operating_margin
    proposed.update(footprint(x - margin, y - margin, w + margin * 2, h + margin * 2))
    for other in existing or ():
        if proposed & set(other.padded_tiles()):
            return PlacementResult(False, "Overlaps another engine or its operating space.", tiles)
    return PlacementResult(True, "Valid placement.", tiles)


def place(
    bf: Battlefield,
    engine_type: str,
    x: int,
    y: int,
    rotation: int = 0,
    existing: Optional[List[PlacedEngine]] = None,
    engine_id: Optional[str] = None,
) -> Tuple[Optional[PlacedEngine], PlacementResult]:
    bag = list(existing or [])
    result = validate_placement(bf, engine_type, x, y, rotation, bag)
    if not result.ok:
        return None, result
    item = PlacedEngine(
        engine_id=engine_id or f"{engine_type}_{len(bag)+1}",
        engine_type=engine_type,
        x=x, y=y, rotation=rotation,
    )
    return item, result


def find_valid_on_side(
    bf: Battlefield,
    engine_type: str,
    side: str,
    existing: Optional[Sequence[PlacedEngine]] = None,
    rotation: int = 0,
) -> Optional[Tuple[int, int, int]]:
    """Search a side's exterior band for one valid top-left (x,y,rot)."""
    ww, wn, we, ws = bf.wall_box
    bands = {
        "south": (ww - 20, ws + 1, we + 20, min(HEIGHT - 2, ws + 48)),
        "north": (ww - 20, max(2, wn - 48), we + 20, wn - 1),
        "west": (max(2, ww - 48), wn + 8, ww - 1, ws - 8),
        "east": (we + 1, wn + 8, min(WIDTH - 2, we + 48), ws - 8),
    }
    if side not in bands:
        return None
    x0, y0, x1, y1 = bands[side]
    spec = SPECS[engine_type]
    rots = (rotation,) if rotation is not None else (0, 90, 180, 270)
    bag = list(existing or [])
    # Face the wall by default: south wall -> rotation 0 (engine extends south)
    for rot in rots:
        w, h = rotated_size(spec, rot)
        y_range = range(y0, y1 - h + 2, 2)
        x_range = range(x0, x1 - w + 2, 2)
        if side == "north":
            y_range = range(y1 - h, y0 - 1, -2)
        for y in y_range:
            for x in x_range:
                res = validate_placement(bf, engine_type, x, y, rot, bag)
                if res.ok:
                    return x, y, rot
    return None


def ring_still_clear(bf: Battlefield, existing: Sequence[PlacedEngine], start: Coord, goal: Coord, via_point: Optional[Coord] = None) -> bool:
    """Ensure placed engines did not cut the exterior ring (circulation is reserved,
    this is an extra path check on walkable tiles treating engine tiles as blocked).
    """
    blocked = {t for e in existing for t in e.tiles()}

    def ok(x, y):
        if (x, y) in blocked:
            return False
        return walkable(bf.plane, x, y, {k: "intact" for k in bf.plane.openings})

    from collections import deque
    seen = {start} if ok(*start) else set()
    q = deque([start] if start in seen else [])
    while q:
        x, y = q.popleft()
        if (x, y) == goal:
            if via_point is None or via_point in seen:
                return True
        for nx, ny in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)):
            if (nx, ny) not in seen and ok(nx, ny):
                seen.add((nx, ny))
                q.append((nx, ny))
    return False


def sample_perimeter_layout(bf: Battlefield) -> List[PlacedEngine]:
    """A demonstration set spanning all four sides. Not a cap."""
    placed: List[PlacedEngine] = []
    plan = [
        ("ram", "south", 0),
        ("ram", "west", 90),
        ("siege_tower", "east", 90),
        ("siege_tower", "north", 180),
        ("ladder", "west", 90),
        ("ladder", "east", 270),
        ("ladder", "north", 180),
        ("trebuchet", "south", 0),
        ("trebuchet", "north", 0),
        ("trebuchet", "west", 0),
        ("trebuchet", "east", 0),
    ]
    for kind, side, rot in plan:
        found = find_valid_on_side(bf, kind, side, placed, rotation=rot)
        if not found:
            found = find_valid_on_side(bf, kind, side, placed, rotation=0)
        if found:
            item, res = place(bf, kind, found[0], found[1], found[2], placed)
            if item:
                placed.append(item)
    return placed
