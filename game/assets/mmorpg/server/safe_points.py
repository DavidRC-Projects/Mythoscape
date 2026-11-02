"""Universal safe arrival / logout park points.

Teleport landings and sticky-context logout parks share one table so coords
cannot drift (e.g. arena teleport vs outside_arena_tile).
"""
from __future__ import annotations

# Shared constants — keep in sync with TELEPORT_DESTINATIONS / module stands.
ARENA_GATE = (196, 164)
SEWER_GRATE_STAND = (25, 28)
VILLAGE_SPAWN = (28, 24)
STONEHAVEN_PLAZA = (118, 75)
ESTATE_FOOT = (85, 11)
CASTLE_PLAZA = (150, 183)

SAFE_POINTS = [
    {
        "id": "arena_gate",
        "kind": "logout_park",
        "contexts": ("arena", "duel"),
        "where": "castle",
        "plane": "realm",
        "x": ARENA_GATE[0],
        "y": ARENA_GATE[1],
        "radius": 0,
        "clear": ("arena_match",),
    },
    {
        "id": "sewer_grate",
        "kind": "logout_park",
        "contexts": ("sewer",),
        "where": "overworld",
        "x": SEWER_GRATE_STAND[0],
        "y": SEWER_GRATE_STAND[1],
        "radius": 0,
        "clear": (),
    },
    {
        "id": "deepdelve_return",
        "kind": "logout_park",
        "contexts": ("deepdelve",),
        "where": "overworld",
        "x": None,  # resolved from session return / saved overworld
        "y": None,
        "radius": 0,
        "clear": (),
    },
    {
        "id": "resting_ox_door",
        "kind": "logout_park",
        "contexts": ("resting_ox",),
        "where": "overworld",
        "x": None,  # resolved from resting_ox_inn._door()
        "y": None,
        "radius": 0,
        "clear": ("bar",),
    },
    {
        "id": "house_estate",
        "kind": "logout_park",
        "contexts": ("house",),
        "where": "overworld",
        "x": ESTATE_FOOT[0],
        "y": ESTATE_FOOT[1],
        "radius": 1,
        "clear": ("house_level",),
    },
    {
        "id": "teleport_arena",
        "kind": "teleport_land",
        "contexts": (),
        "where": "castle",
        "plane": "realm",
        "x": ARENA_GATE[0],
        "y": ARENA_GATE[1],
        "radius": 0,
        "clear": (),
    },
]

BY_ID = {p["id"]: p for p in SAFE_POINTS}


def point_by_id(pid):
    return BY_ID.get(pid)


def resolve_open_tile(x, y, walk_fn, occupied_fn=None, radius=2, exclude_id=None):
    """Chebyshev ring search for a free walkable tile. radius 0 = exact only."""
    x, y = int(x), int(y)
    radius = max(0, int(radius))
    for r in range(0, radius + 1):
        for dy in range(-r, r + 1):
            for dx in range(-r, r + 1):
                if max(abs(dx), abs(dy)) != r:
                    continue
                nx, ny = x + dx, y + dy
                if not walk_fn(nx, ny):
                    continue
                if occupied_fn and occupied_fn(nx, ny, exclude_id):
                    continue
                return nx, ny
    return None


def resolve_arrival(x, y, walk_fn, session, occupied_fn=None, radius=2):
    """Open landing near (x, y). Returns (nx, ny) or None if crowded."""
    pid = getattr(session, "player_id", None)
    return resolve_open_tile(x, y, walk_fn, occupied_fn=occupied_fn, radius=radius, exclude_id=pid)


def _ox_exit_xy():
    try:
        import resting_ox_inn
        _door, exit_xy, _enter, _floor = resting_ox_inn._door()
        return int(exit_xy[0]), int(exit_xy[1])
    except Exception:
        return 9, 48


def _deepdelve_return_xy(session):
    ret = getattr(session, "_dungeon_return", None)
    if ret and len(ret) >= 2:
        return int(ret[0]), int(ret[1])
    d = getattr(session, "dungeon", None) or {}
    if d.get("return_x") is not None:
        return int(d["return_x"]), int(d["return_y"])
    return VILLAGE_SPAWN


def detect_logout_context(session):
    """First matching sticky context for logout parking, or None."""
    import mercenaries as merc
    had_match = bool(getattr(session, "arena_match", None))
    d = getattr(session, "dungeon", None) or {}
    did = d.get("id")
    if had_match or (
        did == "castle_realm"
        and d.get("plane") in (None, "", "realm")
        and merc.inside_arena_campus(int(session.x), int(session.y))
    ):
        return "arena"
    if did == "deepdelve":
        return "deepdelve"
    try:
        import sewer_tutorial
        if did == getattr(sewer_tutorial, "SEWER_ID", "sewer_tutorial"):
            return "sewer"
    except Exception:
        if did in ("sewer", "sewer_tutorial", "below_the_village"):
            return "sewer"
    if getattr(session, "bar", None):
        return "resting_ox"
    if int(getattr(session, "house_level", 0) or 0) > 0:
        return "house"
    return None


def _point_for_context(ctx):
    for p in SAFE_POINTS:
        if ctx in (p.get("contexts") or ()):
            return p
    return None


def resolve_logout_park(session):
    """Apply sticky logout park. Returns (context_id or None, cleared_keys).

    Mutates session.x/y (and pet) when a park applies. Always aborts arena match.
    """
    import mercenaries as merc
    cleared = []
    had_match = merc.abort_arena_match(session)
    if had_match:
        cleared.append("arena_match")

    ctx = detect_logout_context(session)
    # Arena match already aborted — still park if we were mid-match or on campus.
    if had_match and ctx is None:
        d = getattr(session, "dungeon", None) or {}
        if d.get("id") == "castle_realm" and d.get("plane") in (None, "", "realm"):
            ctx = "arena"

    if ctx is None:
        if int(getattr(session, "house_level", 0) or 0) > 0:
            session.house_level = 0
            cleared.append("house_level")
        return None, cleared

    point = _point_for_context(ctx)
    if point is None:
        return ctx, cleared

    where = point.get("where")
    x, y = point.get("x"), point.get("y")
    if ctx == "resting_ox":
        x, y = _ox_exit_xy()
    elif ctx == "deepdelve":
        x, y = _deepdelve_return_xy(session)
    elif ctx == "arena":
        x, y = merc.outside_arena_tile()
        # Ensure we are on realm plane outdoors for resume.
        d = getattr(session, "dungeon", None)
        if d and d.get("id") == "castle_realm":
            d["plane"] = "realm"

    if x is None or y is None:
        return ctx, cleared

    radius = int(point.get("radius") or 0)
    if radius > 0:
        # Soft open search on overworld only when we have a grid walker later;
        # for logout park prefer exact tile.
        pass
    session.x, session.y = int(x), int(y)
    if getattr(session, "pet_id", None):
        session.pet_x, session.pet_y = int(x), int(y)

    for key in point.get("clear") or ():
        if key == "arena_match":
            continue  # already aborted
        if key == "house_level":
            session.house_level = 0
            cleared.append("house_level")
        elif key == "bar":
            # tavern.drop_session still runs in logout_session
            cleared.append("bar")
    return ctx, cleared
