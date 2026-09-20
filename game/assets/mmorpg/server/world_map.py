"""
World map for MMORPG v0.1: one persistent world containing
a village, a forest, a mine, and a dungeon, all on one tile grid.

Tile ids:
    0 GRASS    walkable
    1 TREE     blocked, woodcutting resource (chop from an adjacent tile)
    2 WATER    blocked, fishing resource (click the water from an adjacent tile)
    3 ORE      blocked, mining resource (mine from an adjacent tile)
    4 WALL     blocked, scenery / dungeon walls
    5 PATH     walkable, village paths
    6 FLOOR    walkable, dungeon / building floor
    7 OAK_TREE blocked, higher level woodcutting resource
    8 IRON_ORE blocked, iron mining resource
    9 FISH_SPOT walkable marker (unused on grid; fishing uses WATER)
   10 COAL     blocked, coal mining resource (deep dungeon)
"""
import random

GRASS, TREE, WATER, ORE, WALL, PATH, FLOOR, OAK_TREE, IRON_ORE, FISH_SPOT, COAL = range(11)

WALKABLE_TILES = {GRASS, PATH, FLOOR, FISH_SPOT}

# Larger world so big sprites / buildings have room to breathe.
WIDTH = 64
HEIGHT = 72

# Zone bounding boxes (x0, y0, x1, y1) inclusive
ZONES = {
    "village": (1, 1, 26, 22),
    "forest":  (28, 1, 62, 24),
    "mine":    (1, 26, 28, 54),
    "dungeon": (30, 26, 62, 70),
}

SPAWN_POINT = (14, 12)  # village crossroads


def _rect(grid, x0, y0, x1, y1, tile):
    for y in range(y0, y1 + 1):
        for x in range(x0, x1 + 1):
            if 0 <= x < WIDTH and 0 <= y < HEIGHT:
                grid[y][x] = tile


def _border(grid, x0, y0, x1, y1, tile, skip=()):
    for x in range(x0, x1 + 1):
        if (x, y0) not in skip:
            grid[y0][x] = tile
        if (x, y1) not in skip:
            grid[y1][x] = tile
    for y in range(y0, y1 + 1):
        if (x0, y) not in skip:
            grid[y][x0] = tile
        if (x1, y) not in skip:
            grid[y][x1] = tile


def generate_world():
    rng = random.Random(1337)
    grid = [[GRASS for _ in range(WIDTH)] for _ in range(HEIGHT)]

    _border(grid, 0, 0, WIDTH - 1, HEIGHT - 1, WALL)

    # --- Village paths (crossroads) ---
    vx0, vy0, vx1, vy1 = ZONES["village"]
    for x in range(vx0, vx1 + 1):
        if grid[12][x] == GRASS:
            grid[12][x] = PATH
    for y in range(vy0, vy1 + 1):
        if grid[y][14] == GRASS:
            grid[y][14] = PATH

    # Decorative cottages (solid, not enterable)
    _rect(grid, 3, 3, 6, 5, WALL)
    _rect(grid, 8, 3, 11, 5, WALL)
    _rect(grid, 3, 16, 6, 18, WALL)
    _rect(grid, 8, 17, 10, 19, WALL)

    # Large enterable smithy (furnace + anvil + blacksmith)
    _rect(grid, 17, 5, 25, 13, WALL)
    _rect(grid, 18, 6, 24, 12, FLOOR)
    grid[13][21] = PATH  # south doorway onto the road
    grid[13][20] = PATH
    grid[13][22] = PATH
    grid[12][21] = PATH
    grid[12][20] = PATH
    grid[12][22] = PATH

    # --- Forest + lake ---
    fx0, fy0, fx1, fy1 = ZONES["forest"]
    for _ in range(110):
        x = rng.randint(fx0 + 1, fx1 - 1)
        y = rng.randint(fy0 + 1, fy1 - 1)
        if grid[y][x] == GRASS:
            grid[y][x] = OAK_TREE if rng.random() < 0.25 else TREE
    _rect(grid, 50, 14, 58, 20, WATER)

    # --- Mine ---
    mx0, my0, mx1, my1 = ZONES["mine"]
    _rect(grid, mx0, my0, mx1, my1, FLOOR)
    _border(grid, mx0, my0, mx1, my1, WALL, skip={(14, my0)})  # opening to village path
    for _ in range(40):
        x = rng.randint(mx0 + 2, mx1 - 2)
        y = rng.randint(my0 + 2, my1 - 2)
        if grid[y][x] == FLOOR:
            grid[y][x] = IRON_ORE if rng.random() < 0.25 else ORE

    # --- Dungeon rooms (upper) ---
    dx0, dy0, dx1, dy1 = ZONES["dungeon"]
    _rect(grid, dx0, dy0, dx1, dy1, WALL)
    rooms = [
        (32, 28, 42, 34),
        (46, 28, 58, 35),
        (32, 38, 44, 48),
        (46, 40, 58, 50),
    ]
    for (x0, y0, x1, y1) in rooms:
        _rect(grid, x0, y0, x1, y1, FLOOR)
    _rect(grid, 42, 31, 46, 31, FLOOR)
    _rect(grid, 37, 34, 37, 38, FLOOR)
    _rect(grid, 52, 35, 52, 40, FLOOR)
    _rect(grid, 44, 44, 46, 44, FLOOR)
    # mine <-> dungeon link
    _rect(grid, mx1, 41, 33, 43, FLOOR)
    grid[42][mx1] = FLOOR
    grid[42][31] = FLOOR

    # --- Deep dungeon: iron / coal veins + giant hall ---
    iron_room = (34, 52, 48, 62)
    giant_hall = (50, 54, 60, 68)
    _rect(grid, *iron_room, FLOOR)
    _rect(grid, *giant_hall, FLOOR)
    # corridors from existing south rooms into the deep wing
    _rect(grid, 40, 48, 40, 52, FLOOR)
    _rect(grid, 48, 56, 50, 56, FLOOR)
    _rect(grid, 52, 50, 52, 54, FLOOR)

    # Scatter rich iron + coal in the iron cavern
    for _ in range(28):
        x = rng.randint(iron_room[0] + 1, iron_room[2] - 1)
        y = rng.randint(iron_room[1] + 1, iron_room[3] - 1)
        if grid[y][x] == FLOOR:
            grid[y][x] = COAL if rng.random() < 0.4 else IRON_ORE

    # A few iron rocks on the path into the deep wing
    for pos in ((41, 50), (39, 53), (45, 54), (47, 58)):
        x, y = pos
        if grid[y][x] == FLOOR:
            grid[y][x] = IRON_ORE

    return grid


def get_zone(x, y):
    for name, (x0, y0, x1, y1) in ZONES.items():
        if x0 <= x <= x1 and y0 <= y <= y1:
            return name
    return "wilderness"


def is_walkable(grid, x, y):
    if not (0 <= x < WIDTH and 0 <= y < HEIGHT):
        return False
    return grid[y][x] in WALKABLE_TILES


def build_resource_nodes(grid):
    """Scan the generated grid and return a dict of resource nodes keyed by (x, y)."""
    nodes = {}
    rng = random.Random(2024)
    for y in range(HEIGHT):
        for x in range(WIDTH):
            t = grid[y][x]
            if t == TREE:
                nodes[(x, y)] = {"type": "tree", "depleted": False, "respawn_at": 0}
            elif t == OAK_TREE:
                nodes[(x, y)] = {"type": "oak_tree", "depleted": False, "respawn_at": 0}
            elif t == ORE:
                rtype = "copper_rock" if rng.random() < 0.5 else "tin_rock"
                nodes[(x, y)] = {"type": rtype, "depleted": False, "respawn_at": 0}
            elif t == IRON_ORE:
                nodes[(x, y)] = {"type": "iron_rock", "depleted": False, "respawn_at": 0}
            elif t == COAL:
                nodes[(x, y)] = {"type": "coal_rock", "depleted": False, "respawn_at": 0}

    for y in range(HEIGHT):
        for x in range(WIDTH):
            if grid[y][x] == WATER:
                ftype = "fishing_spot_sardine" if (x + y) % 2 == 0 else "fishing_spot_shrimp"
                nodes[(x, y)] = {
                    "type": ftype, "depleted": False, "respawn_at": 0, "is_fish_spot": True,
                }
    return nodes
