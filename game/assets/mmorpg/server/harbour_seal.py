"""Wolf Pass is the only deliberate chokepoint into Harbourreach from the west.

A rock spur (x 166–169) runs the full map height except the pass road (y 13–17),
so nothing can slip south around the massif into the harbour. The old Harbour
Inlet (sea at y 43–45) was removed — it cut the fields south of the docks.
"""

ROCK_X = (166, 169)
PASS_Y0, PASS_Y1 = 13, 17
PASS_ROWS = (PASS_Y0, PASS_Y1)


def rock_cells(height):
    """Impassable spur cells for a grid of the given height (pass rows stay open)."""
    open_y = set(range(PASS_Y0, PASS_Y1 + 1))
    return {
        (x, y)
        for y in range(height)
        if y not in open_y
        for x in range(ROCK_X[0], ROCK_X[1] + 1)
    }


def stamp(grid, wm):
    """Runs after the wayfinder roads so no road reopens a gap."""
    h, w = len(grid), len(grid[0])
    for x, y in rock_cells(h):
        if 0 < x < w - 1 and 0 <= y < h and grid[y][x] in wm.WALKABLE_TILES | wm.TREE_TILES:
            grid[y][x] = wm.WALL
    return grid
