"""Provisional King's Castle siege numbers.

Nothing in here is an approved final balance pass. Every value is a default
so a match can be played and tested. Override with the environment variables
named below. Placement does not spend gold. Losing the castle does not take
gold. Engineering XP uses the existing engineering skill and the amounts are
small on purpose.

Rotation faces the wall the engine is built against:
  0 north, 90 east, 180 south, 270 west.
A ram on the south wall uses 0 so its nose points north, into that wall.
"""
from __future__ import annotations

import os

# Quarter-turn nose. The footprint extends behind the nose.
FACE = {0: (0, -1), 90: (1, 0), 180: (0, 1), 270: (-1, 0)}
FACE_NAME = {0: "north", 90: "east", 180: "south", 270: "west"}

# hp, range in tiles, min_range, cooldown seconds, damage to a gate, damage to a breach.
# contact engines must have their nose within range of the opening.
# The keep sits about 35 tiles inside the curtain, and a trebuchet must stand
# at least 8 tiles back, so 36 could not reach the keep after the outer gate fell.
ENGINES = {
    "ram": {"hp": 80, "range": 2, "min_range": 0, "cooldown": 4.0, "gate": 28, "breach": 8},
    "trebuchet": {"hp": 50, "range": 72, "min_range": 6, "cooldown": 8.0, "gate": 22, "breach": 18},
    "siege_tower": {"hp": 100, "range": 2, "min_range": 0, "cooldown": 6.0, "gate": 10, "breach": 24},
    "ladder": {"hp": 40, "range": 2, "min_range": 0, "cooldown": 3.0, "gate": 6, "breach": 14},
}

# Defender equipment is provisional too. A ballista sits on the wall-walk and
# shoots outward. A cauldron sits on the walk over a gate or breach and dumps
# onto the apron. ``engine`` damages an attacker engine; ``player`` damages
# an attacker. Override with the KCS_* variables read below.
DEFENDER_ENGINES = {
    "ballista": {"hp": 70, "range": 28, "min_range": 0, "cooldown": 5.0, "engine": 22, "player": 10},
    "cauldron": {"hp": 48, "range": 5, "min_range": 0, "cooldown": 6.0, "engine": 34, "player": 12},
}

OPENING_HP = {
    "main_gate": 140,
    "keep_doors": 100,
    "north_gate": 80,
    "west_gate": 80,
    "east_gate": 80,
    "west_wall_breach": 70,
    "east_wall_breach": 70,
    "north_west_breach": 70,
    "north_east_breach": 70,
    "south_west_breach": 70,
    "south_east_breach": 70,
    "throne_doors": 60,
}


def _num(name: str, default: float) -> float:
    raw = os.environ.get(name)
    if raw is None or raw == "":
        return float(default)
    return float(raw)


def war_seconds() -> float:
    return _num("KCS_WAR_SECONDS", 1200)


def deploy_grace() -> float:
    """Seconds after the battle starts that a non-deployed attacker still counts.

    Provisional. An attacker who never takes the field is out once this ends.
    That is not an elimination, and it does not delete the roster row.
    """
    return max(0.0, _num("KCS_DEPLOY_GRACE", 45))


def grace_rule() -> str:
    seconds = int(deploy_grace())
    return (
        f"Provisional rule: an attacker who has not deployed within {seconds}s of the "
        "battle starting is out of the fight. That is not an elimination. Defenders win "
        "when every attacker who took the field is eliminated, or when time runs out."
    )


def player_hit() -> int:
    return max(1, int(_num("KCS_PLAYER_HIT", 8)))


def player_range() -> int:
    return max(1, int(_num("KCS_PLAYER_RANGE", 2)))


def cooldown_scale() -> float:
    return max(0.0, _num("KCS_COOLDOWN_SCALE", 1))


def xp_place() -> int:
    return max(0, int(_num("KCS_ENG_XP_PLACE", 6)))


def xp_shot() -> int:
    return max(0, int(_num("KCS_ENG_XP_SHOT", 4)))


def xp_repair() -> int:
    return max(0, int(_num("KCS_ENG_XP_REPAIR", 6)))


def repair_amount() -> int:
    return max(1, int(_num("KCS_REPAIR_AMOUNT", 20)))


def engine_spec(engine_type: str) -> dict:
    if engine_type in ENGINES:
        return dict(ENGINES[engine_type])
    return dict(DEFENDER_ENGINES[engine_type])


def operate_range() -> int:
    """How far a defender may stand from equipment to build, fire, or pack it."""
    return max(1, int(_num("KCS_OPERATE_RANGE", 3)))


def opening_splash() -> int:
    """Damage an attacker shot also does to a defender engine on that opening."""
    return max(0, int(_num("KCS_OPENING_SPLASH", 16)))


def strike_damage() -> int:
    return max(1, int(_num("KCS_STRIKE_ENGINE", 12)))


def outward_rotation(cx: float, cy: float, wall_box) -> int:
    """Quarter turn that points off the nearest curtain, away from the bailey."""
    ww, wn, we, ws = wall_box
    dists = [
        (abs(float(cy) - ws), 180),
        (abs(float(cy) - wn), 0),
        (abs(float(cx) - ww), 270),
        (abs(float(cx) - we), 90),
    ]
    dists.sort(key=lambda item: (item[0], item[1]))
    return int(dists[0][1])


def beside(px: int, py: int, tiles, reach: int = None) -> bool:
    limit = operate_range() if reach is None else int(reach)
    return min(max(abs(int(px) - int(tx)), abs(int(py) - int(ty))) for tx, ty in tiles) <= limit


def aimed_target(tiles, rotation: int, engine_type: str, targets):
    """Nearest target in front of a defender engine.

    ``targets`` is a sequence of ``(key, points)``. Returns ``(key, distance)``
    or None. Pure: no database and no gold.
    """
    spec = DEFENDER_ENGINES[engine_type]
    fx, fy = front_point(tiles, rotation)
    fdx, fdy = FACE[int(rotation) % 360]
    best = None
    for key, points in targets:
        points = list(points)
        if not points:
            continue
        nearest = min(points, key=lambda t: (t[0] - fx) ** 2 + (t[1] - fy) ** 2)
        vx, vy = nearest[0] - fx, nearest[1] - fy
        dist = (vx * vx + vy * vy) ** 0.5
        if dist < spec["min_range"] or dist > spec["range"]:
            continue
        if dist > 0 and (vx * fdx + vy * fdy) / dist < 0.15:
            continue
        if best is None or dist < best[0]:
            best = (dist, key)
    if best is None:
        return None
    return best[1], best[0]


def cauldron_zone(tiles, gate_cells, radius: int):
    """Tiles a pot drenches around the gate or breach it sits on."""
    covered = []
    for gx, gy in gate_cells:
        if any(max(abs(gx - tx), abs(gy - ty)) <= 1 for tx, ty in tiles):
            covered.append((int(gx), int(gy)))
    zone = set()
    radius = max(0, int(radius))
    for gx, gy in covered:
        for dx in range(-radius, radius + 1):
            for dy in range(-radius, radius + 1):
                if max(abs(dx), abs(dy)) <= radius:
                    zone.add((gx + dx, gy + dy))
    return zone


def opening_max_hp(opening_id: str) -> int:
    return int(OPENING_HP.get(opening_id, 80))


def state_for_hp(hp: int, max_hp: int) -> str:
    if hp <= 0:
        return "destroyed"
    if hp * 2 <= max_hp:
        return "damaged"
    return "intact"


def rotation_toward_wall(cx: float, cy: float, wall_box) -> int:
    """Quarter turn whose nose points at the nearest curtain side."""
    ww, wn, we, ws = wall_box
    candidates = []
    if cy >= ws:
        candidates.append((cy - ws, 0))
    if cy <= wn:
        candidates.append((wn - cy, 180))
    if cx <= ww:
        candidates.append((ww - cx, 90))
    if cx >= we:
        candidates.append((cx - we, 270))
    if not candidates:
        candidates = [
            (abs(cy - ws), 0),
            (abs(wn - cy), 180),
            (abs(cx - ww), 90),
            (abs(cx - we), 270),
        ]
    candidates.sort(key=lambda item: (item[0], item[1]))
    return int(candidates[0][1])


def front_point(tiles, rotation: int):
    dx, dy = FACE[int(rotation) % 360]
    if dy < 0:
        edge = min(ty for _tx, ty in tiles)
        pts = [p for p in tiles if p[1] == edge]
    elif dy > 0:
        edge = max(ty for _tx, ty in tiles)
        pts = [p for p in tiles if p[1] == edge]
    elif dx > 0:
        edge = max(tx for tx, _ty in tiles)
        pts = [p for p in tiles if p[0] == edge]
    else:
        edge = min(tx for tx, _ty in tiles)
        pts = [p for p in tiles if p[0] == edge]
    ax = sum(p[0] for p in pts) / len(pts) + dx * 0.6
    ay = sum(p[1] for p in pts) / len(pts) + dy * 0.6
    return ax, ay


def shot_target(tiles, rotation: int, engine_type: str, openings: dict):
    """Return (opening_id, damage) for the opening in front of this engine.

    ``openings`` maps id -> iterable of (x, y). Pure: no database and no gold.
    """
    spec = ENGINES[engine_type]
    fx, fy = front_point(tiles, rotation)
    fdx, fdy = FACE[int(rotation) % 360]
    cx = sum(t[0] for t in tiles) / len(tiles)
    cy = sum(t[1] for t in tiles) / len(tiles)
    origin = (cx, cy) if engine_type == "trebuchet" else (fx, fy)
    best = None
    for oid, cells in openings.items():
        cells = list(cells)
        if not cells:
            continue
        nearest = min(cells, key=lambda t: (t[0] - origin[0]) ** 2 + (t[1] - origin[1]) ** 2)
        vx, vy = nearest[0] - origin[0], nearest[1] - origin[1]
        dist = (vx * vx + vy * vy) ** 0.5
        if dist < spec["min_range"] or dist > spec["range"]:
            continue
        if dist > 0 and (vx * fdx + vy * fdy) / dist < 0.15:
            continue
        if best is None or dist < best[0]:
            kind = "breach" if "breach" in oid else "gate"
            best = (dist, oid, int(spec[kind]))
    if best is None:
        return None
    return best[1], best[2]
