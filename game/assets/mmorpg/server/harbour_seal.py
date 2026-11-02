"""Wolf Pass is the only deliberate chokepoint into Harbourreach from the west.

A rock spur (x 166–169) runs the full map height so nothing can slip south
around the massif into the harbour. Known east–west roads that must cross the
spur (Wolf Pass, Stonehaven→Emberdeep, Void Sanctum approach) stay open —
without those gaps the spur is invisible grass on the client but still WALL
on the server and blocks dungeon approaches.
"""

ROCK_X = (166, 169)
PASS_Y0, PASS_Y1 = 13, 17
PASS_ROWS = (PASS_Y0, PASS_Y1)
# Extra open rows: city east approach, Emberdeep south apron, Void Sanctum road.
ROAD_GAPS = frozenset((72, 73, 74, 80, 98, 99))


def _open_y():
    return set(range(PASS_Y0, PASS_Y1 + 1)) | set(ROAD_GAPS)


def rock_cells(height):
    """Impassable spur cells for a grid of the given height (pass/road rows stay open)."""
    open_y = _open_y()
    return {
        (x, y)
        for y in range(height)
        if y not in open_y
        for x in range(ROCK_X[0], ROCK_X[1] + 1)
    }


def stamp(grid, wm):
    """Runs after the wayfinder roads so no road reopens a harbour flank gap.

    Road gap rows listed in ROAD_GAPS are left alone (and forced to PATH if a
    prior stamp left WALL there), so Void / Emberdeep approaches stay walkable.
    """
    h, w = len(grid), len(grid[0])
    open_y = _open_y()
    for x, y in rock_cells(h):
        if 0 < x < w - 1 and 0 <= y < h and grid[y][x] in wm.WALKABLE_TILES | wm.TREE_TILES:
            grid[y][x] = wm.WALL
    # Ensure dungeon approach rows stay open through the spur.
    for y in ROAD_GAPS:
        if not (0 <= y < h):
            continue
        for x in range(ROCK_X[0], ROCK_X[1] + 1):
            if 0 < x < w - 1 and grid[y][x] == wm.WALL:
                grid[y][x] = wm.PATH
    return grid
