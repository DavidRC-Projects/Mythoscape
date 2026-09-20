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
   10 COAL          blocked, coal mining resource (deep dungeon)
   11 MITHRIL_ORE   blocked, mithril mining resource
   12 ADAMANTITE_ORE blocked, adamantite mining resource
"""
import random

GRASS, TREE, WATER, ORE, WALL, PATH, FLOOR, OAK_TREE, IRON_ORE, FISH_SPOT, COAL, MITHRIL_ORE, ADAMANTITE_ORE = range(13)

WALKABLE_TILES = {GRASS, PATH, FLOOR, FISH_SPOT}

# Stretched world — room between buildings, forest, and lake.
WIDTH = 76
HEIGHT = 108

# Zone bounding boxes (x0, y0, x1, y1) inclusive
ZONES = {
    "village": (1, 1, 40, 30),
    "forest":  (42, 1, 74, 30),
    "mine":    (1, 32, 34, 60),
    "dungeon": (36, 32, 74, 106),
}

SPAWN_POINT = (20, 16)  # village crossroads

# Dungeon combat rooms — monsters spawned inside one stay inside it.
DUNGEON_ROOMS = [
    (40, 34, 52, 42),
    (56, 34, 70, 44),
    (40, 46, 54, 56),
    (56, 48, 70, 58),
    (42, 60, 56, 70),   # iron cavern
    (58, 62, 70, 76),   # giant hall
    (40, 80, 54, 96),   # mithril cavern
    (58, 77, 70, 81),   # spider nest
    (56, 82, 70, 102),  # adamantite lair
]


def room_containing(x, y):
    """Return (x0,y0,x1,y1) for the dungeon room containing (x,y), or None."""
    for x0, y0, x1, y1 in DUNGEON_ROOMS:
        if x0 <= x <= x1 and y0 <= y <= y1:
            return (x0, y0, x1, y1)
    return None


def in_room(x, y, room):
    if not room:
        return True
    x0, y0, x1, y1 = room
    return x0 <= x <= x1 and y0 <= y <= y1


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


def _near_water(grid, x, y, radius=3):
    for dy in range(-radius, radius + 1):
        for dx in range(-radius, radius + 1):
            nx, ny = x + dx, y + dy
            if 0 <= nx < WIDTH and 0 <= ny < HEIGHT and grid[ny][nx] == WATER:
                return True
    return False


def generate_world():
    rng = random.Random(1337)
    grid = [[GRASS for _ in range(WIDTH)] for _ in range(HEIGHT)]

    _border(grid, 0, 0, WIDTH - 1, HEIGHT - 1, WALL)

    # --- Village paths (crossroads) ---
    road_y, road_x = 16, 20
    vx0, vy0, vx1, vy1 = ZONES["village"]
    for x in range(vx0, vx1 + 1):
        if grid[road_y][x] == GRASS:
            grid[road_y][x] = PATH
    for y in range(vy0, vy1 + 1):
        if grid[y][road_x] == GRASS:
            grid[y][road_x] = PATH

    # --- Village buildings (larger shells; single-tile south door) ---
    def _building(x0, y0, x1, y1, door_x):
        """Solid wall shell, floored interior, one south-wall door tile."""
        _rect(grid, x0, y0, x1, y1, WALL)
        _rect(grid, x0 + 1, y0 + 1, x1 - 1, y1 - 1, FLOOR)
        for x in range(x0, x1 + 1):
            grid[y1][x] = WALL
        grid[y1][door_x] = PATH

    # NW cottage (Elder Miriam) — roomier hall
    _building(3, 3, 11, 11, door_x=7)
    # NE shop (Shopkeeper Joe)
    _building(15, 3, 23, 11, door_x=19)
    # SW inn (Innkeeper Sarah)
    _building(3, 20, 11, 28, door_x=7)
    # SE cottage (Farmer Tom)
    _building(15, 20, 23, 28, door_x=19)
    # Bank (east of crossroads)
    _building(26, 12, 34, 18, door_x=30)
    # Smithy — large workshop
    _building(36, 4, 48, 14, door_x=42)
    # Pet Emporium
    _building(36, 20, 46, 28, door_x=41)

    # Restore village roads (do not punch through walls)
    for x in range(vx0, min(vx1, 48) + 1):
        if grid[road_y][x] != WALL:
            grid[road_y][x] = PATH
    for y in range(vy0, vy1 + 1):
        if grid[y][road_x] != WALL:
            grid[y][road_x] = PATH
    # Apron tiles outside doors so the road meets each doorway
    for dx, dy in (
        (7, 12), (19, 12), (7, 29), (19, 29),
        (30, 19), (42, 15), (41, 29),
    ):
        if 0 <= dx < WIDTH and 0 <= dy < HEIGHT and grid[dy][dx] != WALL:
            grid[dy][dx] = PATH

    # --- Forest + lake (water first, then trees with shoreline buffer) ---
    fx0, fy0, fx1, fy1 = ZONES["forest"]
    # Lake sits deeper into the forest with grass shores
    lake = (62, 12, 72, 22)
    _rect(grid, *lake, WATER)

    trees_placed = 0
    attempts = 0
    while trees_placed < 45 and attempts < 500:
        attempts += 1
        x = rng.randint(fx0 + 1, fx1 - 1)
        y = rng.randint(fy0 + 1, fy1 - 1)
        if grid[y][x] != GRASS:
            continue
        # Keep large tree sprites off the water (visual + gameplay)
        if _near_water(grid, x, y, radius=3):
            continue
        grid[y][x] = OAK_TREE if rng.random() < 0.25 else TREE
        trees_placed += 1

    # --- Mine ---
    mx0, my0, mx1, my1 = ZONES["mine"]
    _rect(grid, mx0, my0, mx1, my1, FLOOR)
    _border(grid, mx0, my0, mx1, my1, WALL, skip={(road_x, my0)})  # opening to village path
    # Path stub from village into the mine
    for y in range(vy1, my0 + 1):
        if grid[y][road_x] != WALL:
            grid[y][road_x] = PATH
    grid[my0][road_x] = FLOOR
    for _ in range(45):
        x = rng.randint(mx0 + 2, mx1 - 2)
        y = rng.randint(my0 + 2, my1 - 2)
        if grid[y][x] == FLOOR:
            grid[y][x] = IRON_ORE if rng.random() < 0.25 else ORE

    # --- Dungeon rooms (upper) ---
    dx0, dy0, dx1, dy1 = ZONES["dungeon"]
    _rect(grid, dx0, dy0, dx1, dy1, WALL)
    rooms = [
        (40, 34, 52, 42),
        (56, 34, 70, 44),
        (40, 46, 54, 56),
        (56, 48, 70, 58),
    ]
    for (x0, y0, x1, y1) in rooms:
        _rect(grid, x0, y0, x1, y1, FLOOR)
    _rect(grid, 52, 38, 56, 38, FLOOR)
    _rect(grid, 46, 42, 46, 46, FLOOR)
    _rect(grid, 62, 44, 62, 48, FLOOR)
    _rect(grid, 54, 52, 56, 52, FLOOR)
    # mine <-> dungeon link — large, obvious mouth
    _rect(grid, 32, 44, 44, 54, FLOOR)
    for y in range(46, 53):
        grid[y][mx1] = FLOOR
    for px, py in ((33, 44), (42, 44), (33, 54), (42, 54), (32, 48), (32, 52), (43, 48), (43, 52)):
        if 0 <= px < WIDTH and 0 <= py < HEIGHT:
            grid[py][px] = WALL

    # --- Deep dungeon: iron / coal veins + giant hall ---
    iron_room = (42, 60, 56, 70)
    giant_hall = (58, 62, 70, 76)
    _rect(grid, *iron_room, FLOOR)
    _rect(grid, *giant_hall, FLOOR)
    _rect(grid, 48, 56, 48, 60, FLOOR)
    _rect(grid, 56, 66, 58, 66, FLOOR)
    _rect(grid, 62, 58, 62, 62, FLOOR)

    for _ in range(30):
        x = rng.randint(iron_room[0] + 1, iron_room[2] - 1)
        y = rng.randint(iron_room[1] + 1, iron_room[3] - 1)
        if grid[y][x] == FLOOR:
            grid[y][x] = COAL if rng.random() < 0.4 else IRON_ORE

    for pos in ((49, 58), (47, 61), (53, 62), (55, 66)):
        x, y = pos
        if grid[y][x] == FLOOR:
            grid[y][x] = IRON_ORE

    # --- Mithril cavern (west) ---
    mithril_room = (40, 80, 54, 96)
    _rect(grid, *mithril_room, FLOOR)
    _rect(grid, 48, 70, 48, 80, FLOOR)
    for _ in range(24):
        x = rng.randint(mithril_room[0] + 1, mithril_room[2] - 1)
        y = rng.randint(mithril_room[1] + 1, mithril_room[3] - 1)
        if grid[y][x] == FLOOR:
            grid[y][x] = MITHRIL_ORE

    # --- Spider nest (between giant hall / mithril path and adamantite lair) ---
    spider_nest = (58, 77, 70, 81)
    _rect(grid, *spider_nest, FLOOR)
    _rect(grid, 64, 76, 64, 77, FLOOR)   # from giant hall
    _rect(grid, 64, 81, 64, 82, FLOOR)   # into adamantite lair
    _rect(grid, 54, 79, 58, 79, FLOOR)   # side link from mithril approach

    # --- Adamantite lair (east) ---
    adamant_room = (56, 82, 70, 102)
    _rect(grid, *adamant_room, FLOOR)
    _rect(grid, 64, 76, 64, 82, FLOOR)
    _rect(grid, 54, 88, 56, 88, FLOOR)
    for _ in range(20):
        x = rng.randint(adamant_room[0] + 1, adamant_room[2] - 1)
        y = rng.randint(adamant_room[1] + 1, adamant_room[3] - 1)
        if grid[y][x] == FLOOR:
            grid[y][x] = ADAMANTITE_ORE

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
            elif t == MITHRIL_ORE:
                nodes[(x, y)] = {"type": "mithril_rock", "depleted": False, "respawn_at": 0}
            elif t == ADAMANTITE_ORE:
                nodes[(x, y)] = {"type": "adamantite_rock", "depleted": False, "respawn_at": 0}

    for y in range(HEIGHT):
        for x in range(WIDTH):
            if grid[y][x] != WATER:
                continue
            # Only shoreline tiles — player fishes from adjacent land
            has_shore = False
            for dy in (-1, 0, 1):
                for dx in (-1, 0, 1):
                    if dx == 0 and dy == 0:
                        continue
                    nx, ny = x + dx, y + dy
                    if 0 <= nx < WIDTH and 0 <= ny < HEIGHT and grid[ny][nx] in WALKABLE_TILES:
                        has_shore = True
                        break
                if has_shore:
                    break
            if not has_shore:
                continue
            ftype = "fishing_spot_sardine" if (x + y) % 2 == 0 else "fishing_spot_shrimp"
            nodes[(x, y)] = {
                "type": ftype, "depleted": False, "respawn_at": 0, "is_fish_spot": True,
            }
    return nodes
