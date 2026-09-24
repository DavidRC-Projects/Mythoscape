"""
World map for MMORPG v0.1: one persistent world containing
a village, a forest, a mountain pass, a fishing village, a mine,
and a dungeon, all on one tile grid.

Tile ids:
    0 GRASS    walkable
    1 TREE     blocked, woodcutting resource (chop from an adjacent tile)
    2 WATER    blocked, fishing resource (click the water from an adjacent tile)
    3 ORE      blocked, mining resource (mine from an adjacent tile)
    4 WALL     blocked, scenery / dungeon walls / mountains
    5 PATH     walkable, village paths
    6 FLOOR    walkable, dungeon / building floor
    7 OAK_TREE blocked, higher level woodcutting resource
    8 IRON_ORE blocked, iron mining resource
    9 FISH_SPOT walkable marker (unused on grid; fishing uses WATER)
   10 COAL          blocked, coal mining resource (deep dungeon)
   11 MITHRIL_ORE   blocked, mithril mining resource
   12 ADAMANTITE_ORE blocked, adamantite mining resource
   13 STONE         walkable, city flagstone plaza
   14 WILLOW_TREE   blocked, wetland woodcutting
   15 MAPLE_TREE    blocked, mid-tier woodcutting
   16 YEW_TREE      blocked, high-tier woodcutting
   17 MAGIC_TREE    blocked, rare high-tier woodcutting
"""
import random

(
    GRASS, TREE, WATER, ORE, WALL, PATH, FLOOR, OAK_TREE, IRON_ORE, FISH_SPOT,
    COAL, MITHRIL_ORE, ADAMANTITE_ORE, STONE, WILLOW_TREE, MAPLE_TREE, YEW_TREE, MAGIC_TREE,
) = range(18)

WALKABLE_TILES = {GRASS, PATH, FLOOR, FISH_SPOT, STONE}
TREE_TILES = {TREE, OAK_TREE, WILLOW_TREE, MAPLE_TREE, YEW_TREE, MAGIC_TREE}

# Stretched world — room between buildings, forest, mountains, and harbour.
WIDTH = 160
HEIGHT = 115

# Zone bounding boxes (x0, y0, x1, y1) inclusive
ZONES = {
    "village": (1, 1, 66, 36),
    "forest":  (70, 1, 100, 34),
    "mountains": (105, 1, 125, 34),
    "fishing_village": (130, 1, 158, 34),
    "mine":    (1, 38, 34, 66),
    "dungeon": (36, 36, 74, 113),
    "city":    (78, 40, 120, 72),
    "volcano": (122, 42, 150, 70),
    "shadow_crypt": (122, 74, 150, 108),
}

SPAWN_POINT = (22, 18)  # village crossroads

# Dungeon combat rooms — monsters spawned inside one stay inside it.
DUNGEON_ROOMS = [
    (40, 38, 52, 46),
    (56, 38, 70, 48),
    (40, 50, 54, 60),
    (56, 52, 70, 62),
    (42, 64, 56, 74),   # iron cavern
    (58, 66, 70, 80),   # giant hall
    (40, 84, 54, 100),  # mithril cavern
    (58, 81, 70, 85),   # spider nest
    (56, 86, 70, 110),  # adamantite lair
    # Void Sanctum (SE mystical crypt)
    (124, 84, 132, 88),   # shades
    (136, 84, 146, 88),   # crypt ghouls
    (124, 90, 132, 96),   # void imps
    (136, 90, 146, 96),   # obsidian colossi
    (124, 98, 132, 104),  # shadow knights
    (136, 98, 146, 104),  # void horror
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


def _seeded_noise(x, y):
    """Deterministic 0..1 hash for terrain shaping (no RNG drift)."""
    n = (x * 73856093) ^ (y * 19349663) ^ 83492791
    n = (n * 1103515245 + 12345) & 0x7fffffff
    return (n % 10000) / 10000.0


def generate_world():
    rng = random.Random(1337)
    grid = [[GRASS for _ in range(WIDTH)] for _ in range(HEIGHT)]

    _border(grid, 0, 0, WIDTH - 1, HEIGHT - 1, WALL)

    # --- Village paths (crossroads) ---
    road_y, road_x = 18, 22
    vx0, vy0, vx1, vy1 = ZONES["village"]
    for x in range(vx0, vx1 + 1):
        if grid[road_y][x] == GRASS:
            grid[road_y][x] = PATH
    for y in range(vy0, vy1 + 1):
        if grid[y][road_x] == GRASS:
            grid[y][road_x] = PATH

    # --- Village buildings (spaced shells; single-tile south door) ---
    def _building(x0, y0, x1, y1, door_x):
        """Solid wall shell, floored interior, one south-wall door tile."""
        _rect(grid, x0, y0, x1, y1, WALL)
        _rect(grid, x0 + 1, y0 + 1, x1 - 1, y1 - 1, FLOOR)
        for x in range(x0, x1 + 1):
            grid[y1][x] = WALL
        grid[y1][door_x] = PATH

    # NW cottage (Elder Miriam)
    _building(3, 3, 11, 11, door_x=7)
    # NE shop (Shopkeeper Joe) — further east of the road
    _building(23, 3, 31, 11, door_x=27)
    # SW inn (Innkeeper Sarah) — further south
    _building(3, 24, 11, 32, door_x=7)
    # SE cottage (Farmer Tom)
    _building(23, 24, 31, 32, door_x=27)
    # Bank (east of crossroads)
    _building(34, 14, 42, 20, door_x=38)
    # Smithy — large workshop, east village fringe
    _building(50, 4, 62, 14, door_x=56)
    # Pet Emporium
    _building(50, 24, 60, 32, door_x=55)

    # Restore village roads (do not punch through walls)
    for x in range(vx0, min(vx1, 62) + 1):
        if grid[road_y][x] != WALL:
            grid[road_y][x] = PATH
    for y in range(vy0, vy1 + 1):
        if grid[y][road_x] != WALL:
            grid[y][road_x] = PATH
    # Apron tiles outside doors + wishing-well plaza
    for dx, dy in (
        (7, 12), (27, 12), (7, 33), (27, 33),
        (38, 21), (56, 15), (55, 33),
        (30, 21), (29, 21), (31, 21), (30, 20), (30, 22),  # wishing well plaza
    ):
        if 0 <= dx < WIDTH and 0 <= dy < HEIGHT and grid[dy][dx] != WALL:
            grid[dy][dx] = PATH

    # --- Starter trees on village fringe (normal + sparse oak) ---
    village_fringe = []
    for y in range(vy0 + 1, vy1):
        for x in range(vx0 + 1, min(vx1, 48)):
            if grid[y][x] != GRASS:
                continue
            if x < 14 or x > 46 or y < 14 or y > 34:
                village_fringe.append((x, y))
    rng.shuffle(village_fringe)
    tree_positions = []
    for x, y in village_fringe:
        if any(max(abs(p[0] - x), abs(p[1] - y)) < 3 for p in tree_positions):
            continue
        if len(tree_positions) >= 18:
            break
        tile = OAK_TREE if len(tree_positions) >= 14 else TREE
        grid[y][x] = tile
        tree_positions.append((x, y))

    # --- Forest + lake (water first, then spaced trees by biome) ---
    fx0, fy0, fx1, fy1 = ZONES["forest"]
    lake = (80, 11, 92, 23)
    _rect(grid, *lake, WATER)

    def _try_place(tile, count, pred, gap=3):
        placed = 0
        attempts = 0
        while placed < count and attempts < count * 40:
            attempts += 1
            x = rng.randint(fx0 + 1, fx1 - 1)
            y = rng.randint(fy0 + 1, fy1 - 1)
            if grid[y][x] != GRASS or not pred(x, y):
                continue
            if any(max(abs(x - tx), abs(y - ty)) < gap for tx, ty in tree_positions):
                continue
            grid[y][x] = tile
            tree_positions.append((x, y))
            placed += 1
        return placed

    # Main forest floor: normal + oak (away from water)
    _try_place(TREE, 20, lambda x, y: not _near_water(grid, x, y, radius=3))
    _try_place(OAK_TREE, 16, lambda x, y: not _near_water(grid, x, y, radius=3))
    # Wetland / lake shore: willow
    _try_place(WILLOW_TREE, 12, lambda x, y: _near_water(grid, x, y, radius=3), gap=3)
    # Deeper / higher forest (east & north): maple + yew
    _try_place(MAPLE_TREE, 8, lambda x, y: (x >= 88 or y <= 8) and not _near_water(grid, x, y, radius=2), gap=4)
    _try_place(YEW_TREE, 5, lambda x, y: (x >= 90 or y <= 6) and not _near_water(grid, x, y, radius=2), gap=5)

    # Path south of the lake toward the mountain pass
    for x in range(74, 105):
        if grid[24][x] in (GRASS, *TREE_TILES):
            grid[24][x] = PATH
    for y in range(16, 25):
        if grid[y][100] in (GRASS, *TREE_TILES, PATH):
            grid[y][100] = PATH
    # Link village road into forest
    for x in range(62, 74):
        if grid[road_y][x] in (GRASS, *TREE_TILES):
            grid[road_y][x] = PATH

    # Clear small plazas so key NPCs aren't buried under canopy
    for nx, ny in (
        (74, 8), (75, 8), (74, 9), (73, 8),                 # Mia
        (70, 22), (71, 22), (69, 22), (70, 21), (70, 23),  # Mad Scientist
        (78, 16), (77, 16), (79, 16), (78, 15), (78, 17),  # Pete (west lake shore)
        (28, 22), (29, 22), (28, 21),                       # Timmy
    ):
        if 0 <= nx < WIDTH and 0 <= ny < HEIGHT and grid[ny][nx] in (GRASS, *TREE_TILES, PATH):
            grid[ny][nx] = PATH

    # --- Mountain pass (east of forest) — peaked ridges with a walkable corridor ---
    mx0, my0, mx1, my1 = ZONES["mountains"]
    # Foothill base
    _rect(grid, mx0, my0, mx1, my1, GRASS)
    # Jagged northern / southern ridgelines (peaks), not a solid wall slab
    for x in range(mx0, mx1 + 1):
        # North peaks — taller in the middle of the range
        mid = (mx0 + mx1) / 2
        north_h = 9 + int(4 * (1 - abs(x - mid) / max(1, (mx1 - mx0) / 2)))
        north_h += int(_seeded_noise(x, my0) * 3) - 1
        for y in range(my0, min(my1, my0 + max(5, north_h))):
            grid[y][x] = WALL
        # South ridge (lower foothill cliffs)
        south_top = my1 - (4 + int(_seeded_noise(x, my1) * 4))
        for y in range(max(my0, south_top), my1 + 1):
            grid[y][x] = WALL
    # Interior rocky spurs / outcrops (mountain bulk between ridges)
    for ox, oy, rw, rh in (
        (107, 8, 6, 5), (114, 6, 5, 4), (119, 9, 5, 5),
        (108, 22, 4, 4), (116, 24, 6, 5), (121, 21, 3, 4),
        (111, 20, 3, 3), (118, 11, 3, 3),
    ):
        for y in range(oy, oy + rh):
            for x in range(ox, ox + rw):
                if mx0 <= x <= mx1 and my0 <= y <= my1:
                    if _seeded_noise(x, y) > 0.28:
                        grid[y][x] = WALL
    # Main east–west pass (3 tiles tall) cut through the massif
    _rect(grid, mx0, 15, mx1, 17, PATH)
    # Connect forest approach into the pass
    _rect(grid, 100, 15, 104, 17, PATH)
    # Side clearings where wolves patrol (scree / alpine meadow, no trees)
    _rect(grid, 110, 12, 114, 14, GRASS)
    _rect(grid, 110, 14, 112, 15, PATH)
    _rect(grid, 116, 18, 121, 20, GRASS)
    _rect(grid, 118, 17, 120, 18, PATH)
    _rect(grid, 108, 18, 109, 19, GRASS)
    # Rocky boulder tiles within clearings (still WALL — impassable rock)
    for bx, by in ((111, 12), (113, 12), (117, 19), (121, 19), (109, 18)):
        if mx0 <= bx <= mx1 and my0 <= by <= my1 and grid[by][bx] == GRASS:
            grid[by][bx] = WALL
    # Exit into fishing village
    _rect(grid, mx1, 15, mx1 + 1, 17, PATH)

    # Tidehollow Cave mouth — rocky alcove north of Harbourreach, clear of buildings
    for dx, dy in (
        (136, 1), (137, 1), (138, 1), (139, 1), (140, 1),
        (136, 2), (140, 2), (135, 2), (141, 2), (136, 3), (140, 3),
        (135, 1), (141, 1), (137, 0), (138, 0), (139, 0),
    ):
        if 0 <= dx < WIDTH and 0 <= dy < HEIGHT:
            grid[dy][dx] = WALL
    grid[2][138] = FLOOR  # cave mouth floor (interactable sits here)
    # Wide approach apron (3 tiles) south of the mouth
    _rect(grid, 136, 3, 140, 5, PATH)
    grid[2][137] = PATH
    grid[2][139] = PATH
    grid[2][138] = FLOOR

    # --- Fishing village + harbour ---
    fv0, fvy0, fv1, fvy1 = ZONES["fishing_village"]
    # Village paths
    for x in range(fv0, fv1 + 1):
        if grid[18][x] != WALL:
            grid[18][x] = PATH
    for y in range(6, 30):
        if grid[y][138] in (GRASS, PATH):
            grid[y][138] = PATH
    # Link mountain pass into harbour road
    for x in range(125, 138):
        if grid[16][x] in (GRASS, PATH, WALL):
            if grid[16][x] != WALL or x >= mx1:
                grid[16][x] = PATH
    for y in range(16, 19):
        grid[y][138] = PATH

    # Tackle shop (north) and fishmonger / cookhouse (south) — spaced from cave
    _building(134, 6, 142, 14, door_x=138)
    _building(134, 20, 142, 28, door_x=138)
    for dx, dy in ((138, 15), (138, 29)):
        if 0 <= dx < WIDTH and 0 <= dy < HEIGHT and grid[dy][dx] != WALL:
            grid[dy][dx] = PATH
    # PATH bypass around the tackle shop so Tidehollow stays reachable without entering
    for y in range(3, 16):
        for x in (132, 133, 143, 144):
            if grid[y][x] in (GRASS, PATH, WALL) and not (134 <= x <= 142 and 6 <= y <= 14):
                if grid[y][x] != FLOOR:
                    grid[y][x] = PATH
    # Re-seal shop walls after bypass (don't punch through the building)
    for y in range(6, 15):
        for x in (134, 142):
            if y != 14 or x != 138:
                grid[y][x] = WALL
    _rect(grid, 135, 7, 141, 13, FLOOR)
    grid[14][138] = PATH  # shop door

    # Harbour / bay on the east shore
    harbour = (144, 8, 157, 26)
    _rect(grid, *harbour, WATER)
    # Shore willows by the harbour
    for hx, hy in ((141, 10), (141, 22), (140, 14), (140, 24)):
        if 0 <= hx < WIDTH and 0 <= hy < HEIGHT and grid[hy][hx] == GRASS:
            grid[hy][hx] = WILLOW_TREE
    # Shore strip west of the bay
    for y in range(8, 27):
        if grid[y][143] == WATER:
            grid[y][143] = PATH
        if grid[y][142] in (GRASS, PATH) and y in (17, 18, 19):
            grid[y][142] = PATH
    # Wide wooden pier
    _rect(grid, 141, 17, 150, 19, PATH)
    # Larger end deck
    _rect(grid, 149, 15, 153, 21, PATH)

    # --- Mine ---
    mix0, miy0, mix1, miy1 = ZONES["mine"]
    _rect(grid, mix0, miy0, mix1, miy1, FLOOR)
    # 3-tile mouth opening onto the village road
    _border(grid, mix0, miy0, mix1, miy1, WALL, skip={
        (road_x - 1, miy0), (road_x, miy0), (road_x + 1, miy0),
    })
    # Wide path stub from village into the mine
    for y in range(vy1, miy0 + 1):
        for x in (road_x - 1, road_x, road_x + 1):
            if grid[y][x] != WALL:
                grid[y][x] = PATH
    for x in (road_x - 1, road_x, road_x + 1):
        grid[miy0][x] = FLOOR
    # Apron just north of the mouth
    for y in (miy0 - 2, miy0 - 1):
        for x in (road_x - 2, road_x - 1, road_x, road_x + 1, road_x + 2):
            if 0 <= x < WIDTH and grid[y][x] in (GRASS, PATH, *TREE_TILES):
                grid[y][x] = PATH
    for _ in range(45):
        x = rng.randint(mix0 + 2, mix1 - 2)
        y = rng.randint(miy0 + 2, miy1 - 2)
        if grid[y][x] == FLOOR:
            grid[y][x] = IRON_ORE if rng.random() < 0.25 else ORE

    # --- Dungeon rooms (upper) ---
    dx0, dy0, dx1, dy1 = ZONES["dungeon"]
    _rect(grid, dx0, dy0, dx1, dy1, WALL)
    rooms = [
        (40, 38, 52, 46),
        (56, 38, 70, 48),
        (40, 50, 54, 60),
        (56, 52, 70, 62),
    ]
    for (x0, y0, x1, y1) in rooms:
        _rect(grid, x0, y0, x1, y1, FLOOR)
    # Wider corridors between upper rooms (3 tiles)
    _rect(grid, 52, 41, 56, 43, FLOOR)
    _rect(grid, 45, 46, 47, 50, FLOOR)
    _rect(grid, 61, 48, 63, 52, FLOOR)
    _rect(grid, 54, 55, 56, 57, FLOOR)
    # mine <-> dungeon link — large, obvious mouth
    _rect(grid, 32, 48, 44, 58, FLOOR)
    for y in range(50, 57):
        for x in (mix1 - 1, mix1, mix1 + 1):
            if mix0 <= x <= mix1 + 2:
                grid[y][x] = FLOOR
    for px, py in ((33, 48), (42, 48), (33, 58), (42, 58), (32, 52), (32, 56), (43, 52), (43, 56)):
        if 0 <= px < WIDTH and 0 <= py < HEIGHT:
            grid[py][px] = WALL
    # PATH apron west of the dungeon mouth (from village/mine approach)
    _rect(grid, 28, 50, 32, 56, PATH)
    for y in range(50, 57):
        grid[y][32] = FLOOR

    # --- Deep dungeon: iron / coal veins + giant hall ---
    iron_room = (42, 64, 56, 74)
    giant_hall = (58, 66, 70, 80)
    _rect(grid, *iron_room, FLOOR)
    _rect(grid, *giant_hall, FLOOR)
    _rect(grid, 47, 60, 49, 64, FLOOR)
    _rect(grid, 56, 69, 58, 71, FLOOR)
    _rect(grid, 61, 62, 63, 66, FLOOR)

    for _ in range(30):
        x = rng.randint(iron_room[0] + 1, iron_room[2] - 1)
        y = rng.randint(iron_room[1] + 1, iron_room[3] - 1)
        if grid[y][x] == FLOOR:
            grid[y][x] = COAL if rng.random() < 0.4 else IRON_ORE

    for pos in ((49, 62), (47, 65), (53, 66), (55, 70)):
        x, y = pos
        if grid[y][x] == FLOOR:
            grid[y][x] = IRON_ORE

    # --- Mithril cavern (west) ---
    mithril_room = (40, 84, 54, 100)
    _rect(grid, *mithril_room, FLOOR)
    _rect(grid, 47, 74, 49, 84, FLOOR)
    for _ in range(24):
        x = rng.randint(mithril_room[0] + 1, mithril_room[2] - 1)
        y = rng.randint(mithril_room[1] + 1, mithril_room[3] - 1)
        if grid[y][x] == FLOOR:
            grid[y][x] = MITHRIL_ORE

    # --- Spider nest ---
    spider_nest = (58, 81, 70, 85)
    _rect(grid, *spider_nest, FLOOR)
    _rect(grid, 63, 80, 65, 81, FLOOR)
    _rect(grid, 63, 85, 65, 86, FLOOR)
    _rect(grid, 54, 82, 58, 84, FLOOR)

    # --- Adamantite lair (east) ---
    adamant_room = (56, 86, 70, 110)
    _rect(grid, *adamant_room, FLOOR)
    _rect(grid, 63, 80, 65, 86, FLOOR)
    _rect(grid, 54, 91, 56, 93, FLOOR)
    for _ in range(20):
        x = rng.randint(adamant_room[0] + 1, adamant_room[2] - 1)
        y = rng.randint(adamant_room[1] + 1, adamant_room[3] - 1)
        if grid[y][x] == FLOOR:
            grid[y][x] = ADAMANTITE_ORE

    # --- Stonehaven City (east of dungeon, south of forest) ---
    cx0, cy0, cx1, cy1 = ZONES["city"]
    # Outer stone plaza
    _rect(grid, cx0 + 1, cy0 + 1, cx1 - 1, cy1 - 1, STONE)
    # City walls (brick shell with south gate + west road)
    _border(grid, cx0, cy0, cx1, cy1, WALL, skip={
        (98, cy1), (99, cy1), (100, cy1),  # south gate
        (cx0, 56), (cx0, 55), (cx0, 57),   # west gate
        (98, cy0), (99, cy0),              # north road entry
    })
    # Main streets
    for x in range(cx0 + 2, cx1 - 1):
        grid[56][x] = PATH
        grid[62][x] = PATH
    for y in range(cy0 + 2, cy1 - 1):
        grid[y][98] = PATH
        grid[y][108] = PATH
    # Market square
    _rect(grid, 92, 54, 104, 64, STONE)
    _rect(grid, 94, 56, 102, 62, PATH)

    def _city_building(x0, y0, x1, y1, door_x, door_y=None):
        _rect(grid, x0, y0, x1, y1, WALL)
        _rect(grid, x0 + 1, y0 + 1, x1 - 1, y1 - 1, FLOOR)
        dy = door_y if door_y is not None else y1
        grid[dy][door_x] = PATH

    # Town houses along the west plaza
    _city_building(82, 44, 90, 52, door_x=86)
    _city_building(82, 58, 90, 66, door_x=86)
    # Barracks / armory east of square
    _city_building(110, 58, 118, 68, door_x=114)

    # Castle keep (north plaza) — thick walls, courtyard, battlements
    _rect(grid, 100, 42, 118, 54, WALL)
    _rect(grid, 102, 44, 116, 52, FLOOR)
    # Inner throne hall
    _rect(grid, 106, 45, 114, 50, FLOOR)
    # Gatehouse opening south into the plaza
    grid[54][108] = PATH
    grid[54][109] = PATH
    grid[53][108] = PATH
    grid[53][109] = PATH
    # Courtyard stones just south of the keep
    _rect(grid, 104, 54, 114, 58, STONE)

    # Road from forest south into the city gate
    for y in range(25, cy0 + 1):
        for x in (98, 99):
            if grid[y][x] in (GRASS, *TREE_TILES, PATH, STONE):
                grid[y][x] = PATH
    # Path from dungeon fringe east into city (west gate)
    for x in range(74, cx0 + 1):
        if grid[56][x] in (GRASS, *TREE_TILES, PATH, WALL):
            if x < cx0 or grid[56][x] != WALL:
                grid[56][x] = PATH
    grid[56][cx0] = PATH  # west gate
    # Ensure city gates are walkable paths
    for gx, gy in ((98, cy1), (99, cy1), (100, cy1), (98, cy0), (99, cy0), (cx0, 55), (cx0, 56), (cx0, 57)):
        if 0 <= gx < WIDTH and 0 <= gy < HEIGHT:
            grid[gy][gx] = PATH

    # High forest belt north of the city — maple, yew, rare magic
    for _ in range(80):
        x = rng.randint(78, 100)
        y = rng.randint(34, 40)
        if grid[y][x] != GRASS:
            continue
        if any(grid[ny][nx] in TREE_TILES
               for ny in range(max(0, y - 3), min(HEIGHT, y + 4))
               for nx in range(max(0, x - 3), min(WIDTH, x + 4))
               if (nx, ny) != (x, y)):
            continue
        roll = rng.random()
        if roll < 0.08:
            grid[y][x] = MAGIC_TREE
        elif roll < 0.35:
            grid[y][x] = YEW_TREE
        else:
            grid[y][x] = MAPLE_TREE

    # --- Emberdeep volcano (east of Stonehaven) — conical massif + crater mouth ---
    vx0, vy0, vx1, vy1 = ZONES["volcano"]
    # Scorched foothills (ash grass)
    for y in range(vy0, vy1 + 1):
        for x in range(vx0, vx1 + 1):
            if grid[y][x] in (GRASS, *TREE_TILES):
                grid[y][x] = GRASS
    # Concentric basalt rings → reads as a rising cone
    rings = [
        (126, 44, 148, 66),  # outer foothills
        (128, 46, 146, 64),
        (130, 48, 144, 62),
        (132, 50, 142, 60),
    ]
    for i, (x0, y0, x1, y1) in enumerate(rings):
        _border(grid, x0, y0, x1, y1, WALL)
        # Fill ring band with rock (not the very outer — leave approach)
        if i >= 1:
            for y in range(y0 + 1, y1):
                for x in range(x0 + 1, x1):
                    if grid[y][x] in (GRASS, PATH, *TREE_TILES):
                        grid[y][x] = WALL
    # Inner crater bowl (walkable floor when roof lifts)
    _rect(grid, 133, 51, 141, 57, WALL)
    _rect(grid, 134, 52, 140, 56, FLOOR)
    # Magma glow pit in crater center (blocked lava tile)
    grid[54][136] = WATER
    grid[54][137] = WATER
    grid[55][136] = WATER
    # Mouth tunnel opening south through the rings
    for y in range(56, 60):
        for x in range(135, 138):
            grid[y][x] = FLOOR
    # Apron / landing in front of the mouth
    _rect(grid, 132, 59, 141, 63, PATH)
    grid[58][136] = FLOOR  # interactable stands here
    # Jagged outer peaks
    for _ in range(55):
        x = rng.randint(124, 149)
        y = rng.randint(43, 67)
        # Keep mouth corridor clear
        if 134 <= x <= 138 and 56 <= y <= 60:
            continue
        if abs(x - 136) + abs(y - 54) < 5:
            continue
        if grid[y][x] in (GRASS, PATH):
            grid[y][x] = WALL
    # Road from Stonehaven east gate into the crater mouth
    for x in range(120, 134):
        for y in (56, 57, 58):
            if 0 <= x < WIDTH and grid[y][x] in (GRASS, *TREE_TILES, PATH, WALL, STONE):
                if x == 120 and grid[y][x] == WALL:
                    grid[y][x] = PATH
                elif x > 120:
                    grid[y][x] = PATH
    for y in (56, 57, 58):
        grid[y][120] = PATH  # east city gate

    # --- Void Sanctum (SE mystical crypt) — dark building + 6 sealed rooms ---
    sx0, sy0, sx1, sy1 = ZONES["shadow_crypt"]
    _rect(grid, sx0, sy0, sx1, sy1, WALL)
    # Entrance building shell (matches BUILDINGS void_sanctum)
    _building(132, 74, 142, 80, door_x=137)
    # Six crypt rooms (must match DUNGEON_ROOMS)
    sanctum_rooms = [
        (124, 84, 132, 88),
        (136, 84, 146, 88),
        (124, 90, 132, 96),
        (136, 90, 146, 96),
        (124, 98, 132, 104),
        (136, 98, 146, 104),
    ]
    for room in sanctum_rooms:
        _rect(grid, *room, FLOOR)
    # Corridors between rooms + descent from the sanctum hall (wider for access)
    _rect(grid, 132, 85, 136, 87, FLOOR)   # room1 ↔ room2
    _rect(grid, 126, 88, 129, 90, FLOOR)   # room1 ↔ room3
    _rect(grid, 139, 88, 142, 90, FLOOR)   # room2 ↔ room4
    _rect(grid, 132, 92, 136, 94, FLOOR)   # room3 ↔ room4
    _rect(grid, 126, 96, 129, 98, FLOOR)   # room3 ↔ room5
    _rect(grid, 139, 96, 142, 98, FLOOR)   # room4 ↔ room6
    _rect(grid, 132, 100, 136, 102, FLOOR) # room5 ↔ room6
    # Descent: building interior floor → first corridor (3-wide)
    grid[79][137] = FLOOR
    _rect(grid, 135, 79, 139, 84, FLOOR)
    # Keep the south door + apron walkable (3-wide)
    for ax in (135, 136, 137, 138, 139):
        grid[80][ax] = PATH
        grid[81][ax] = PATH
        grid[82][ax] = PATH
    # Punch 3-wide door gap in the building south wall
    for ax in (136, 137, 138):
        grid[80][ax] = PATH
    # Road from Stonehaven south gate east, then south to the sanctum
    for x in range(98, 138):
        for yy in (cy1 + 1, cy1 + 2):
            if 0 <= yy < HEIGHT and grid[yy][x] in (GRASS, PATH, STONE, WALL):
                # Don't erase city wall except the existing south gate tiles
                if yy == cy1:
                    continue
                grid[yy][x] = PATH
    for y in range(cy1 + 1, 82):
        for x in (136, 137, 138):
            if grid[y][x] in (GRASS, PATH, WALL) and not (132 < x < 142 and 74 < y < 80):
                grid[y][x] = PATH
    grid[80][137] = PATH

    _clear_trees_near_buildings(grid)
    return grid


# Building footprints — keep in sync with content.BUILDINGS (avoid import cycle)
_BUILDING_FOOTPRINTS = [
    # village
    (3, 3, 11, 11), (23, 3, 31, 11), (3, 24, 11, 32), (23, 24, 31, 32),
    (34, 14, 42, 20), (50, 4, 62, 14), (50, 24, 60, 32),
    # harbour
    (134, 6, 142, 14), (134, 20, 142, 28),
    # city
    (82, 44, 90, 52), (82, 58, 90, 66), (110, 58, 118, 68), (100, 42, 118, 54),
    # void sanctum entrance building
    (132, 74, 142, 80),
    # tidehollow cave mouth apron (keep clear of trees)
    (136, 1, 140, 4),
]


def _clear_trees_near_buildings(grid, margin=2, canopy_south=4):
    """Remove trees that hug walls or whose canopies would cover building shells."""
    for x0, y0, x1, y1 in _BUILDING_FOOTPRINTS:
        # Yard / wall margin
        for y in range(max(0, y0 - margin), min(HEIGHT, y1 + margin + 1)):
            for x in range(max(0, x0 - margin), min(WIDTH, x1 + margin + 1)):
                if grid[y][x] in TREE_TILES:
                    grid[y][x] = GRASS
        # Canopy hangs northward on screen from trunks south of the building
        for y in range(y1 + 1, min(HEIGHT, y1 + 1 + canopy_south)):
            for x in range(max(0, x0 - 1), min(WIDTH, x1 + 2)):
                if grid[y][x] in TREE_TILES:
                    grid[y][x] = GRASS


def get_zone(x, y):
    for name, (x0, y0, x1, y1) in ZONES.items():
        if x0 <= x <= x1 and y0 <= y <= y1:
            return name
    return "wilderness"


def is_walkable(grid, x, y):
    if not (0 <= x < WIDTH and 0 <= y < HEIGHT):
        return False
    return grid[y][x] in WALKABLE_TILES


def _harbour_fish_type(x, y):
    """Tiered fishing spots in the fishing village harbour."""
    # North pier / deep water → higher fish; south → mid; near shore → trout
    if y <= 10:
        return "fishing_spot_swordfish" if (x + y) % 3 == 0 else "fishing_spot_tuna"
    if y <= 14:
        return "fishing_spot_lobster" if (x + y) % 2 == 0 else "fishing_spot_salmon"
    if y <= 18:
        return "fishing_spot_salmon" if (x + y) % 2 == 0 else "fishing_spot_trout"
    return "fishing_spot_trout"


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
            elif t == WILLOW_TREE:
                nodes[(x, y)] = {"type": "willow_tree", "depleted": False, "respawn_at": 0}
            elif t == MAPLE_TREE:
                nodes[(x, y)] = {"type": "maple_tree", "depleted": False, "respawn_at": 0}
            elif t == YEW_TREE:
                nodes[(x, y)] = {"type": "yew_tree", "depleted": False, "respawn_at": 0}
            elif t == MAGIC_TREE:
                nodes[(x, y)] = {"type": "magic_tree", "depleted": False, "respawn_at": 0}
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

    # Shoreline fishing — sparse spots, not every water tile
    fish_candidates = []
    for y in range(HEIGHT):
        for x in range(WIDTH):
            if grid[y][x] != WATER:
                continue
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
            if has_shore:
                fish_candidates.append((x, y))

    fish_rng = random.Random(4242)
    fish_rng.shuffle(fish_candidates)
    placed = []
    min_gap = 2  # Chebyshev distance between spots
    for x, y in fish_candidates:
        if any(max(abs(x - px), abs(y - py)) <= min_gap for px, py in placed):
            continue
        zone = get_zone(x, y)
        if zone == "fishing_village":
            ftype = _harbour_fish_type(x, y)
        else:
            ftype = "fishing_spot_sardine" if (x + y) % 2 == 0 else "fishing_spot_shrimp"
        nodes[(x, y)] = {
            "type": ftype, "depleted": False, "respawn_at": 0, "is_fish_spot": True,
        }
        placed.append((x, y))
    return nodes
