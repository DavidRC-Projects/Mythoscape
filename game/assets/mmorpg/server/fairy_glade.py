"""Fairy Glade: a ring of glowing trees around the fairy village (ZONES_SPEC §Fairy Glade).

The village buildings are not planted over. Every ring cell is a tree trunk and is
a WALL on the server grid, so only trunks block; the painted canopies drawn by
the client stand over the open tiles around them. One entrance (north, off the
village road) and one exit (south, onto
the southern meadow), each a long winding 4-wide path through a thicket,
with a painted tree arch over its outer mouth.
"""
ZONE = (1, 56, 40, 88)          # live fairy_village box, unchanged
BUILDINGS = (4, 58, 40, 85)     # legacy name: the village core (kept for callers)
ENTRANCE_MOUTH = (31, 52)
EXIT_MOUTH = (13, 97)
LANE_WIDTH = 4

# Arches: (post_left, post_right, base_row). Posts are trunk cells (the only
# collision); the 4-wide lane between them stays open.
ARCHES = (
    ("north", (29, 52), (34, 52)),
    ("south", (11, 97), (16, 97)),
)

# Thicket regions that become trees (minus the lanes). Only plantable ground
# (grass, path, trees) is planted, so buildings, floors and the plaza stay.
_REGIONS = (
    # West of the arch only — leave x35+ on y52 as the village approach road.
    (1, 52, 28, 52),
    (1, 53, 43, 57),     # north thicket, full width
    (4, 58, 19, 62),     # west meadow top (lane punches a short south spur)
    (1, 53, 5, 91),      # west band — solid tree wall (no open west U-turn)
    (41, 53, 43, 91),    # east band
    (1, 88, 43, 93),     # south thicket, full width
    (1, 94, 1, 94),      # (x2-10 on row 94 is the south-west house wall)
    (11, 94, 43, 97),    # rows 95-97 hide the exit lane from the meadow below
)

_RING = None
_LANE = None


def _rect(cells, x0, y0, x1, y1):
    for x in range(x0, x1 + 1):
        for y in range(y0, y1 + 1):
            cells.add((x, y))


def lane_cells():
    global _LANE
    if _LANE is None:
        lane = set()
        # Entrance under the arch, then west to Scout Elena. A short spur
        # punches south through the hedge (row 57) so the upper road joins the
        # lower lane where players stand — no open gap in the west tree wall.
        _rect(lane, 30, 52, 33, 56)
        _rect(lane, 18, 53, 33, 56)
        _rect(lane, 20, 56, 23, 61)   # connector at Elena (~22,54)
        _rect(lane, 15, 58, 23, 61)
        _rect(lane, 15, 58, 18, 62)   # down into the meadow
        # Exit (~45 tiles, 4 wide): end of Petal Avenue -> east along y88-91 ->
        # down x36-39 -> long run west along y93-96 -> down x12-15 under the
        # arch on row 97. Row 92 stays thicket between the runs.
        _rect(lane, 27, 88, 39, 91)
        _rect(lane, 36, 88, 39, 96)
        _rect(lane, 12, 93, 39, 96)
        _rect(lane, 12, 93, 15, 97)
        _LANE = frozenset(lane)
    return _LANE


def arch_posts():
    return frozenset(p for _n, a, b in ARCHES for p in (a, b))


def _band():
    band = set()
    for r in _REGIONS:
        _rect(band, *r)
    return band


def _plantable(grid, wm, x, y):
    if grid is None:
        return True
    t = grid[y][x]
    return t in (wm.GRASS, wm.PATH) or t in getattr(wm, "TREE_TILES", ())


def ring_cells(grid=None, wm=None):
    """Trunk tiles (x, y): the thickets minus the lanes and the map border.

    Computed once from the grid at stamp time; later calls reuse it."""
    global _RING
    if _RING is None or grid is not None:
        lane = lane_cells()
        h = len(grid) if grid is not None else 10 ** 6
        w = len(grid[0]) if grid is not None else 10 ** 6
        _RING = frozenset(
            (x, y) for (x, y) in _band()
            if 1 <= x < w and y < h and (x, y) not in lane
            and ((x, y) in arch_posts() or _plantable(grid, wm, x, y))
        )
    return _RING


def tree_cells():
    """Trunks that get a tree sprite (arch posts are drawn by the arch)."""
    return ring_cells() - arch_posts()


def near_lane(x, y):
    """True when a lane lies just north of this trunk, under its canopy."""
    lane = lane_cells()
    return any((x + dx, y - dy) in lane for dx in (-1, 0, 1) for dy in (1, 2, 3))


def is_trunk(x, y):
    return (int(x), int(y)) in ring_cells()


def is_lane(x, y):
    return (int(x), int(y)) in lane_cells()


def stamp(grid, wm):
    """Runs last (after the wayfinder roads)."""
    global _RING, _LANE
    _RING = None
    _LANE = None
    h, w = len(grid), len(grid[0])
    for x, y in ring_cells(grid, wm):
        if 0 <= x < w and 0 <= y < h:
            grid[y][x] = wm.WALL
    # Entrance / exit lanes are PATH so village dirt runs under the arches and
    # joins petal avenues inside the fairy zone (client paints by zone).
    for x, y in lane_cells():
        if 0 <= x < w and 0 <= y < h:
            grid[y][x] = wm.PATH
    return grid
