"""
World map for MMORPG v0.1: one persistent world containing
a village, a forest, a mine, and a dungeon, all on one tile grid.

Tile ids:
    0 GRASS    walkable
    1 TREE     blocked, woodcutting resource (chop from an adjacent tile)
    2 WATER    blocked, fishing resource (fish from an adjacent tile)
    3 ORE      blocked, mining resource (mine from an adjacent tile)
    4 WALL     blocked, scenery / dungeon walls
    5 PATH     walkable, village paths
    6 FLOOR    walkable, dungeon floor
    7 OAK_TREE blocked, higher level woodcutting resource
"""
import random

GRASS, TREE, WATER, ORE, WALL, PATH, FLOOR, OAK_TREE, IRON_ORE, FISH_SPOT = range(10)

WALKABLE_TILES = {GRASS, PATH, FLOOR, FISH_SPOT}

WIDTH = 40
HEIGHT = 36

# Zone bounding boxes (x0, y0, x1, y1) inclusive, used by the client for
# labels/minimap and by the server for spawn placement sanity checks.
ZONES = {
    "village": (1, 1, 16, 14),
    "forest":  (17, 1, 38, 16),
    "mine":    (1, 17, 17, 34),
    "dungeon": (18, 17, 38, 34),
}

SPAWN_POINT = (9, 7)  # village center, where new characters appear


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
    rng = random.Random(1337)  # deterministic layout
    grid = [[GRASS for _ in range(WIDTH)] for _ in range(HEIGHT)]

    # Outer world border (impassable edge of the map)
    _border(grid, 0, 0, WIDTH - 1, HEIGHT - 1, WALL)

    # --- Village: simple paths + a couple of house-shaped wall blocks ---
    vx0, vy0, vx1, vy1 = ZONES["village"]
    for x in range(vx0, vx1 + 1):
        grid[7][x] = PATH if grid[7][x] == GRASS else grid[7][x]
    for y in range(vy0, vy1 + 1):
        grid[y][9] = PATH if grid[y][9] == GRASS else grid[y][9]
    # A couple of small "house" blocks (decorative walls, not enterable)
    _rect(grid, 2, 2, 4, 3, WALL)
    _rect(grid, 12, 2, 14, 3, WALL)
    _rect(grid, 3, 12, 5, 13, WALL)

    # --- Forest: scattered trees + a small lake for fishing ---
    fx0, fy0, fx1, fy1 = ZONES["forest"]
    tree_spots = []
    for _ in range(55):
        x = rng.randint(fx0 + 1, fx1 - 1)
        y = rng.randint(fy0 + 1, fy1 - 1)
        if grid[y][x] == GRASS:
            grid[y][x] = OAK_TREE if rng.random() < 0.25 else TREE
            tree_spots.append((x, y))
    # small lake, bottom-right of the forest
    _rect(grid, 32, 10, 36, 13, WATER)
    for x in range(31, 38):
        for y in range(9, 15):
            if grid[y][x] == WATER:
                pass
    # a couple of fishable grass tiles right next to the lake stay GRASS
    # (fishing is done by standing on grass adjacent to WATER)

    # --- Mine: cave-like area with ore rocks ---
    mx0, my0, mx1, my1 = ZONES["mine"]
    _rect(grid, mx0, my0, mx1, my1, FLOOR)
    _border(grid, mx0, my0, mx1, my1, WALL, skip={(9, my0)})  # opening north to village path
    ore_spots = []
    for _ in range(22):
        x = rng.randint(mx0 + 2, mx1 - 2)
        y = rng.randint(my0 + 2, my1 - 2)
        if grid[y][x] == FLOOR:
            roll = rng.random()
            grid[y][x] = IRON_ORE if roll < 0.25 else ORE
            ore_spots.append((x, y))

    # --- Dungeon: hand-laid rooms + corridors (guarantees connectivity) ---
    dx0, dy0, dx1, dy1 = ZONES["dungeon"]
    _rect(grid, dx0, dy0, dx1, dy1, WALL)
    rooms = [
        (19, 18, 25, 22),
        (29, 18, 37, 23),
        (19, 26, 26, 33),
        (28, 26, 37, 33),
    ]
    for (x0, y0, x1, y1) in rooms:
        _rect(grid, x0, y0, x1, y1, FLOOR)
    # corridors connecting the rooms
    _rect(grid, 25, 20, 29, 20, FLOOR)   # room1 <-> room2
    _rect(grid, 22, 22, 22, 26, FLOOR)   # room1 <-> room3
    _rect(grid, 33, 23, 33, 26, FLOOR)   # room2 <-> room4
    _rect(grid, 26, 29, 28, 29, FLOOR)   # room3 <-> room4
    # entrance corridor connecting dungeon to the mine (west side)
    _rect(grid, dx0 - 2, 30, dx0, 30, FLOOR)
    grid[30][mx1] = FLOOR

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
    tile_to_type = {
        TREE: "tree",
        OAK_TREE: "oak_tree",
        ORE: "copper_rock",  # copper/tin randomly assigned below
        IRON_ORE: "iron_rock",
    }
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

    # Fishing spots: grass tiles adjacent to water
    for y in range(HEIGHT):
        for x in range(WIDTH):
            if grid[y][x] == WATER:
                for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                    nx, ny = x + dx, y + dy
                    if 0 <= nx < WIDTH and 0 <= ny < HEIGHT and grid[ny][nx] == GRASS:
                        ftype = "fishing_spot_sardine" if (nx + ny) % 2 == 0 else "fishing_spot_shrimp"
                        nodes[(nx, ny)] = {"type": ftype, "depleted": False, "respawn_at": 0, "is_fish_spot": True}
    return nodes
