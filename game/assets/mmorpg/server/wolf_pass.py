"""Wolf Pass massif (MOUNTAIN_SPEC.md): shared server/client geometry.

One painted massif (North Ridge + South Ridge) replaces the grey mountain tiles east of the forest.
Collision comes from the painted cliff bases (assets/wolf_pass/wolf_pass.json, built from the art);
the canyon floor follows the spec: 8 at the mouths, 6-7 along the pass, 4 at the centre choke.
Set USE_WOLF_PASS=0 to keep the old generated ridges.
"""
import json
import os

PACK = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "wolf_pass"))
_GEO = None


def geo():
    global _GEO
    if _GEO is None:
        try:
            with open(os.path.join(PACK, "wolf_pass.json")) as fh:
                _GEO = json.load(fh)
        except (OSError, ValueError):
            _GEO = {}
    return _GEO


def enabled():
    try:
        import feature_flags
        return bool(getattr(feature_flags, "USE_WOLF_PASS", False)) and bool(geo())
    except ImportError:
        return bool(geo())


def bounds():
    """(x0, y0, x1, y1) of the massif footprint in tiles."""
    g = geo()
    return (g["x0"], 0, g["x1"], 28) if g else None


def blocked(x, y):
    g = geo()
    col = (g.get("cols") or {}).get(str(x)) if g else None
    if not col:
        return False
    north, _ft, _fb, south = col
    return y in north or y in south


def floor_rows(x):
    col = (geo().get("cols") or {}).get(str(x))
    return (col[1], col[2]) if col else None


def in_massif(x, y):
    b = bounds()
    return bool(b) and b[0] <= x <= b[2] and b[1] <= y <= b[3]


def is_cliff(x, y):
    """Blocked massif tile (the client paints the ridge over it, not a grey rock tile)."""
    return in_massif(x, y) and blocked(x, y)


def wolf_zone():
    return tuple(geo().get("wolf_zone") or (145, 13, 156, 18))


def wolf_spawns():
    """6 wolves on the canyon floor inside the 12x6 zone centred on the choke."""
    x0, y0, x1, y1 = wolf_zone()
    picks = [(146, 15), (148, 17), (150, 14), (152, 16), (154, 15), (155, 17)]
    out = []
    for x, y in picks:
        fr = floor_rows(x)
        if fr and fr[0] <= y <= fr[1] and x0 <= x <= x1 and y0 <= y <= y1:
            out.append(("wolf", x, y))
    return out


def leash_area():
    """10-tile leash around the zone, clipped to the canyon (wolves never leave the floor: walls block)."""
    x0, y0, x1, y1 = wolf_zone()
    g = geo()
    return (max(g.get("x0", x0), x0 - 10), 11, min(g.get("x1", x1), x1 + 10), 20)


def apply(grid, path_tile, grass_tile, wall_tile):
    """Rewrite the massif footprint on the world grid."""
    g = geo()
    x0, y0, x1, y1 = bounds()
    r0, r1 = g.get("road") or (14, 17)
    for y in range(y0, y1 + 1):
        for x in range(x0, x1 + 1):
            if blocked(x, y):
                grid[y][x] = wall_tile
            elif r0 <= y <= r1:
                grid[y][x] = path_tile
            else:
                grid[y][x] = grass_tile
    # Approaches: forest road in from the west, harbour road out east (4 wide, same rows as the pass).
    for x in list(range(130, x0)) + list(range(x1 + 1, x1 + 3)):
        for y in range(r0, r1 + 1):
            if grid[y][x] != wall_tile or x < x0:
                grid[y][x] = path_tile
