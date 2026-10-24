"""Wolf Pass is the only walkable way into Harbourreach.

Two pieces close every other route:
  * a rock spur (x 166–169) north and south of the pass mouth, joining the
    Wolf Pass massif to the castle's east moat, and
  * the Harbour Inlet, a 3-tile channel of sea from that moat to the east
    coast (y 43–45), cutting off the open fields south of the harbour.
The pass road itself (y 13–17) stays open. Collision is per tile; the client
draws the inlet as water and the spur as rock.
"""

ROCK_X = (166, 169)
ROCK_ROWS = tuple(range(0, 13)) + tuple(range(18, 29))
PASS_ROWS = (13, 17)
INLET_X = (170, 198)
INLET_Y = (43, 45)


def rock_cells():
    return {(x, y) for y in ROCK_ROWS for x in range(ROCK_X[0], ROCK_X[1] + 1)}


def inlet_cells():
    return {(x, y) for y in range(INLET_Y[0], INLET_Y[1] + 1)
            for x in range(INLET_X[0], INLET_X[1] + 1)}


def stamp(grid, wm):
    """Runs after the wayfinder roads so no road reopens a gap."""
    h, w = len(grid), len(grid[0])
    for x, y in rock_cells():
        if 0 < x < w - 1 and 0 <= y < h and grid[y][x] in wm.WALKABLE_TILES | wm.TREE_TILES:
            grid[y][x] = wm.WALL
    for x, y in inlet_cells():
        if 0 < x < w - 1 and 0 <= y < h and grid[y][x] != wm.WALL:
            grid[y][x] = wm.WATER
    return grid
