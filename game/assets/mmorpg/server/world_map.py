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
import sys

import castle_v2
import buildings_v2
import feature_flags

(
    GRASS, TREE, WATER, ORE, WALL, PATH, FLOOR, OAK_TREE, IRON_ORE, FISH_SPOT,
    COAL, MITHRIL_ORE, ADAMANTITE_ORE, STONE, WILLOW_TREE, MAPLE_TREE, YEW_TREE, MAGIC_TREE,
) = range(18)

WALKABLE_TILES = {GRASS, PATH, FLOOR, FISH_SPOT, STONE}
TREE_TILES = {TREE, OAK_TREE, WILLOW_TREE, MAPLE_TREE, YEW_TREE, MAGIC_TREE}

# Larger world — room for cottage shells, paths, and spaced districts.
WIDTH = 200
HEIGHT = 145

# Zone bounding boxes (x0, y0, x1, y1) inclusive
ZONES = {
    "village": (1, 1, 92, 52),
    "forest":  (98, 1, 132, 42),
    "mountains": (138, 1, 162, 42),
    "fishing_village": (168, 1, 198, 42),
    "mine":    (31, 90, 43, 98),
    "fairy_village": (1, 56, 40, 88),
    "dungeon": (44, 54, 90, 143),
    "city":    (98, 56, 148, 96),  # flag-off shell. city_bounds() grows it.
    "volcano": (176, 58, 198, 94),
    "shadow_crypt": (153, 96, 198, 143),
}

SPAWN_POINT = (28, 24)  # village crossroads


def city_bounds():
    """Stonehaven plaza. The new houses need the ground south of the castle."""
    if feature_flags.USE_NEW_BUILDINGS:
        return (94, 56, 152, 132)
    return ZONES["city"]

# Dungeon combat rooms — monsters spawned inside one stay inside it.
# Shifted with dungeon zone (origin ~44,54).
DUNGEON_ROOMS = [
    (48, 56, 60, 64),
    (64, 56, 78, 66),
    (48, 68, 62, 78),
    (64, 70, 78, 80),
    (50, 82, 64, 92),   # iron cavern
    (66, 84, 78, 98),   # giant hall
    (48, 102, 62, 118),  # mithril cavern
    (66, 99, 78, 103),   # spider nest
    (64, 104, 78, 128),  # adamantite lair
    # Void Sanctum (SE mystical crypt) — in shadow_crypt zone
    (156, 108, 164, 112),   # shades
    (168, 108, 178, 112),   # crypt ghouls
    (156, 114, 164, 120),   # void imps
    (168, 114, 178, 120),   # obsidian colossi
    (156, 122, 164, 128),   # shadow knights
    (168, 122, 178, 128),   # void horror
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


def widen_single_file_passages(tiles):
    """Open every one-tile passage to three tiles so a walker can get through.

    A passage cell has exactly two walkable neighbours. Both sides of that
    cell become floor. Outer walls and water are left alone.
    """
    h = len(tiles)
    w = len(tiles[0]) if h else 0
    if w < 3 or h < 3:
        return 0
    ortho = ((1, 0), (-1, 0), (0, 1), (0, -1))
    opened = 0
    for _pass in range(4):
        changes = []
        for y in range(1, h - 1):
            for x in range(1, w - 1):
                if tiles[y][x] not in WALKABLE_TILES:
                    continue
                neigh = []
                for dx, dy in ortho:
                    if tiles[y + dy][x + dx] in WALKABLE_TILES:
                        neigh.append((dx, dy))
                if len(neigh) != 2:
                    continue
                axes = {(abs(dx), abs(dy)) for dx, dy in neigh}
                # Only straight single-file runs. Room corners stay as they are.
                if len(axes) != 1:
                    continue
                ax, _ay = next(iter(axes))
                sides = ((0, 1), (0, -1)) if ax == 1 else ((1, 0), (-1, 0))
                for dx, dy in sides:
                    nx, ny = x + dx, y + dy
                    if not (0 < nx < w - 1 and 0 < ny < h - 1):
                        continue
                    if tiles[ny][nx] in WALKABLE_TILES or tiles[ny][nx] == WATER:
                        continue
                    changes.append((nx, ny))
        if not changes:
            break
        for nx, ny in changes:
            if tiles[ny][nx] != FLOOR:
                tiles[ny][nx] = FLOOR
                opened += 1
    return opened


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
    road_y, road_x = 24, 28
    vx0, vy0, vx1, vy1 = ZONES["village"]
    for x in range(vx0, vx1 + 1):
        if grid[road_y][x] == GRASS:
            grid[road_y][x] = PATH
    for y in range(vy0, vy1 + 1):
        if grid[y][road_x] == GRASS:
            grid[y][road_x] = PATH

    # --- Village buildings (larger shells for cottage volumes; 3-wide south doors) ---
    def _punch_south_door(x0, x1, y1, door_x, width=3):
        """Open a walkable gap in the south wall, centered on door_x."""
        half = width // 2
        for x in range(door_x - half, door_x + half + 1):
            if x0 < x < x1:
                grid[y1][x] = PATH

    def _building(x0, y0, x1, y1, door_x, behind=GRASS):
        """Solid wall shell, floored interior, 3-wide south-wall door gap.
        North edge (behind the cottage) is walkable exterior — not a blocking wall.
        """
        _rect(grid, x0, y0, x1, y1, WALL)
        _rect(grid, x0 + 1, y0 + 1, x1 - 1, y1 - 1, FLOOR)
        for x in range(x0, x1 + 1):
            grid[y1][x] = WALL
        _punch_south_door(x0, x1, y1, door_x, width=3)
        # Walkable strip behind the building (outside / north of the shell)
        for x in range(x0 + 1, x1):
            grid[y0][x] = behind


    # Spaced ~11×11 shells — readable iso cottage volumes
    # NW cottage (Elder Miriam)
    _building(4, 4, 15, 15, door_x=9)
    # NE shop (Shopkeeper Joe)
    _building(40, 4, 51, 15, door_x=45)
    # SW inn (Innkeeper Sarah)
    _building(4, 36, 15, 47, door_x=9)
    # SE cottage (Farmer Tom)
    _building(40, 36, 51, 47, door_x=45)
    # Bank (east of crossroads)
    _building(58, 18, 70, 28, door_x=64)
    # Smithy — large workshop
    _building(78, 4, 94, 18, door_x=86)
    # Pet Emporium
    _building(78, 36, 92, 48, door_x=85)
    # Mythos Outfitters — open field south-east of the bank, door onto the road.
    _building(60, 37, 72, 47, door_x=66)

    # Restore village roads (do not punch through walls)
    for x in range(vx0, min(vx1, 94) + 1):
        if grid[road_y][x] != WALL:
            grid[road_y][x] = PATH
    for y in range(vy0, vy1 + 1):
        if grid[y][road_x] != WALL:
            grid[y][road_x] = PATH
    # 3-wide apron tiles outside village doors + wishing-well plaza
    door_aprons = (
        (9, 16), (45, 16), (9, 48), (45, 48),
        (64, 29), (86, 19), (85, 49), (66, 48),
    )
    for cx, cy in door_aprons:
        for ox in (-1, 0, 1):
            dx, dy = cx + ox, cy
            if 0 <= dx < WIDTH and 0 <= dy < HEIGHT and grid[dy][dx] != WALL:
                grid[dy][dx] = PATH
    for dx, dy in (
        (32, 22), (31, 22), (33, 22), (32, 21), (32, 23),  # wishing well plaza
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
    lake = (108, 11, 120, 23)
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
    _try_place(MAPLE_TREE, 8, lambda x, y: (x >= 118 or y <= 8) and not _near_water(grid, x, y, radius=2), gap=4)
    _try_place(YEW_TREE, 5, lambda x, y: (x >= 120 or y <= 6) and not _near_water(grid, x, y, radius=2), gap=5)

    # Path south of the lake toward the mountain pass
    for x in range(96, 138):
        if grid[24][x] in (GRASS, *TREE_TILES):
            grid[24][x] = PATH
    for y in range(16, 25):
        if grid[y][130] in (GRASS, *TREE_TILES, PATH):
            grid[y][130] = PATH
    # Link village road into forest
    for x in range(90, 98):
        if grid[road_y][x] in (GRASS, *TREE_TILES):
            grid[road_y][x] = PATH

    # Clear small plazas so key NPCs aren't buried under canopy
    for nx, ny in (
        (102, 8), (103, 8), (102, 9), (101, 8),                 # Mia
        (98, 22), (99, 22), (97, 22), (98, 21), (98, 23),  # Mad Scientist
        (106, 16), (105, 16), (107, 16), (106, 15), (106, 17),  # Pete (west lake shore)
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
        (140, 8, 6, 5), (147, 6, 5, 4), (152, 9, 5, 5),
        (141, 22, 4, 4), (149, 24, 6, 5), (154, 21, 3, 4),
        (144, 20, 3, 3), (151, 11, 3, 3),
    ):
        for y in range(oy, oy + rh):
            for x in range(ox, ox + rw):
                if mx0 <= x <= mx1 and my0 <= y <= my1:
                    if _seeded_noise(x, y) > 0.28:
                        grid[y][x] = WALL
    # Main east–west pass (3 tiles tall) cut through the massif
    _rect(grid, mx0, 15, mx1, 17, PATH)
    # Connect forest approach into the pass
    _rect(grid, 130, 15, 137, 17, PATH)
    # Side clearings where wolves patrol (scree / alpine meadow, no trees)
    _rect(grid, 143, 12, 147, 14, GRASS)
    _rect(grid, 143, 14, 145, 15, PATH)
    _rect(grid, 149, 18, 154, 20, GRASS)
    _rect(grid, 151, 17, 153, 18, PATH)
    _rect(grid, 141, 18, 142, 19, GRASS)
    # Rocky boulder tiles within clearings (still WALL — impassable rock)
    for bx, by in ((144, 12), (146, 12), (150, 19), (154, 19), (142, 18)):
        if mx0 <= bx <= mx1 and my0 <= by <= my1 and grid[by][bx] == GRASS:
            grid[by][bx] = WALL
    # Exit into fishing village
    _rect(grid, mx1, 15, mx1 + 1, 17, PATH)

    # Tidehollow Cave mouth — rocky alcove north of Harbourreach, clear of buildings
    for dx, dy in (
        (174, 1), (175, 1), (176, 1), (177, 1), (178, 1),
        (174, 2), (178, 2), (173, 2), (179, 2), (174, 3), (178, 3),
        (173, 1), (179, 1), (175, 0), (176, 0), (177, 0),
    ):
        if 0 <= dx < WIDTH and 0 <= dy < HEIGHT:
            grid[dy][dx] = WALL
    # Old north-coast alcove is just a path now — the cave moved south so the mound fits.
    _rect(grid, 174, 1, 178, 5, PATH)
    grid[0][175] = WALL
    grid[0][176] = WALL
    grid[0][177] = WALL

    # --- Fishing village + harbour ---
    fv0, fvy0, fv1, fvy1 = ZONES["fishing_village"]
    # Village paths
    for x in range(fv0, fv1 + 1):
        if grid[18][x] != WALL:
            grid[18][x] = PATH
    for y in range(6, 30):
        if grid[y][176] in (GRASS, PATH):
            grid[y][176] = PATH
    # Link mountain pass into harbour road
    for x in range(158, 176):
        if grid[16][x] in (GRASS, PATH, WALL):
            if grid[16][x] != WALL or x >= mx1:
                grid[16][x] = PATH
    for y in range(16, 19):
        grid[y][176] = PATH

    # Tackle shop (north) and fishmonger / cookhouse (south) — spaced from cave
    _building(172, 6, 182, 14, door_x=177)
    _building(172, 20, 182, 28, door_x=177)
    for cx, cy in ((177, 15), (177, 29)):
        for ox in (-1, 0, 1):
            dx, dy = cx + ox, cy
            if 0 <= dx < WIDTH and 0 <= dy < HEIGHT and grid[dy][dx] != WALL:
                grid[dy][dx] = PATH
    # PATH bypass around the tackle shop so Tidehollow stays reachable without entering
    for y in range(3, 16):
        for x in (170, 171, 183, 184):
            if grid[y][x] in (GRASS, PATH, WALL) and not (172 <= x <= 182 and 6 <= y <= 14):
                if grid[y][x] != FLOOR:
                    grid[y][x] = PATH
    # Re-seal shop walls after bypass (don't punch through the building)
    for y in range(6, 15):
        for x in (172, 182):
            if y != 14 or x != 177:
                grid[y][x] = WALL
    _rect(grid, 173, 7, 181, 13, FLOOR)
    for x in (176, 177, 178):
        grid[14][x] = PATH  # 3-wide shop door

    # Tidehollow cave — south of the harbour, clear of the shops, room for the mound.
    _rect(grid, 176, 30, 192, 40, GRASS)
    for y in range(29, 39):
        if grid[y][184] != WATER:
            grid[y][184] = PATH
    for dx in (-1, 0, 1):
        grid[36][184 + dx] = PATH
        grid[35][184 + dx] = PATH
    grid[36][184] = FLOOR

    # Harbour / bay on the east shore
    harbour = (184, 8, 197, 26)
    _rect(grid, *harbour, WATER)
    # Shore willows by the harbour
    for hx, hy in ((181, 10), (181, 22), (180, 14), (180, 24)):
        if 0 <= hx < WIDTH and 0 <= hy < HEIGHT and grid[hy][hx] == GRASS:
            grid[hy][hx] = WILLOW_TREE
    # Shore strip west of the bay
    for y in range(8, 27):
        if grid[y][183] == WATER:
            grid[y][183] = PATH
        if grid[y][182] in (GRASS, PATH) and y in (17, 18, 19):
            grid[y][182] = PATH
    # Wide wooden pier
    _rect(grid, 181, 17, 190, 19, PATH)
    # Larger end deck
    _rect(grid, 189, 15, 193, 21, PATH)

    # --- Quarry beside King's Row (the old mine ground is the fairy village) ---
    _rect(grid, 31, 90, 43, 98, WALL)
    _rect(grid, 32, 91, 42, 97, FLOOR)
    for y in (93, 94, 95):
        grid[y][31] = PATH
        if grid[y][30] in (GRASS, PATH, FLOOR):
            grid[y][30] = PATH
    for x, y, iron in (
        (32, 91, False), (34, 91, False), (36, 91, True), (38, 91, False),
        (40, 91, True), (42, 91, False), (35, 92, False), (39, 92, True),
        (35, 96, True), (39, 96, False), (32, 97, False), (34, 97, False),
        (36, 97, False), (38, 97, True), (40, 97, False), (42, 97, False),
        (42, 93, True), (42, 95, False),
    ):
        grid[y][x] = IRON_ORE if iron else ORE

    # --- Dungeon rooms (upper) ---
    dx0, dy0, dx1, dy1 = ZONES["dungeon"]
    _rect(grid, dx0, dy0, dx1, dy1, WALL)
    rooms = [
        (48, 56, 60, 64),
        (64, 56, 78, 66),
        (48, 68, 62, 78),
        (64, 70, 78, 80),
    ]
    for (x0, y0, x1, y1) in rooms:
        _rect(grid, x0, y0, x1, y1, FLOOR)
    # Wider corridors between upper rooms (3 tiles)
    _rect(grid, 60, 59, 64, 61, FLOOR)
    _rect(grid, 53, 64, 55, 68, FLOOR)
    _rect(grid, 69, 66, 71, 70, FLOOR)
    _rect(grid, 62, 73, 64, 75, FLOOR)

    # --- Deep dungeon: iron / coal veins + giant hall ---
    iron_room = (50, 82, 64, 92)
    giant_hall = (66, 84, 78, 98)
    _rect(grid, *iron_room, FLOOR)
    _rect(grid, *giant_hall, FLOOR)
    _rect(grid, 55, 78, 57, 82, FLOOR)
    _rect(grid, 64, 87, 66, 89, FLOOR)
    _rect(grid, 69, 80, 71, 84, FLOOR)

    for _ in range(30):
        x = rng.randint(iron_room[0] + 1, iron_room[2] - 1)
        y = rng.randint(iron_room[1] + 1, iron_room[3] - 1)
        if grid[y][x] == FLOOR:
            grid[y][x] = COAL if rng.random() < 0.4 else IRON_ORE

    for pos in ((57, 80), (55, 83), (61, 84), (63, 88)):
        x, y = pos
        if grid[y][x] == FLOOR:
            grid[y][x] = IRON_ORE

    # --- Mithril cavern (west) ---
    mithril_room = (48, 102, 62, 118)
    _rect(grid, *mithril_room, FLOOR)
    _rect(grid, 55, 92, 57, 102, FLOOR)
    for _ in range(24):
        x = rng.randint(mithril_room[0] + 1, mithril_room[2] - 1)
        y = rng.randint(mithril_room[1] + 1, mithril_room[3] - 1)
        if grid[y][x] == FLOOR:
            grid[y][x] = MITHRIL_ORE

    # --- Spider nest ---
    spider_nest = (66, 99, 78, 103)
    _rect(grid, *spider_nest, FLOOR)
    _rect(grid, 71, 98, 73, 99, FLOOR)
    _rect(grid, 71, 103, 73, 104, FLOOR)
    _rect(grid, 62, 100, 66, 102, FLOOR)

    # --- Adamantite lair (east) ---
    adamant_room = (64, 104, 78, 128)
    _rect(grid, *adamant_room, FLOOR)
    _rect(grid, 71, 98, 73, 104, FLOOR)
    _rect(grid, 62, 109, 64, 111, FLOOR)
    for _ in range(20):
        x = rng.randint(adamant_room[0] + 1, adamant_room[2] - 1)
        y = rng.randint(adamant_room[1] + 1, adamant_room[3] - 1)
        if grid[y][x] == FLOOR:
            grid[y][x] = ADAMANTITE_ORE

    # --- Stonehaven City (east of dungeon, south of forest) ---
    cx0, cy0, cx1, cy1 = city_bounds()
    # Outer stone plaza
    _rect(grid, cx0 + 1, cy0 + 1, cx1 - 1, cy1 - 1, STONE)
    # City walls (brick shell with south gate + west road)
    _border(grid, cx0, cy0, cx1, cy1, WALL, skip={
        (118, cy1), (119, cy1), (120, cy1),  # south gate
        (cx0, 72), (cx0, 71), (cx0, 73),   # west gate
        (118, cy0), (119, cy0),              # north road entry
    })
    # Main streets
    for x in range(cx0 + 2, cx1 - 1):
        grid[72][x] = PATH
        grid[78][x] = PATH
    for y in range(cy0 + 2, cy1 - 1):
        grid[y][118] = PATH
        grid[y][128] = PATH
    if feature_flags.USE_NEW_BUILDINGS:
        # Street in front of the cottage and barracks, and one in front of the house.
        for x in range(cx0 + 2, cx1):
            grid[98][x] = PATH
            grid[99][x] = PATH
        for x in range(100, 132):
            grid[124][x] = PATH
            grid[125][x] = PATH
    # Market square
    _rect(grid, 112, 70, 124, 80, STONE)
    _rect(grid, 114, 72, 122, 78, PATH)

    def _city_building(x0, y0, x1, y1, door_x, door_y=None):
        _rect(grid, x0, y0, x1, y1, WALL)
        _rect(grid, x0 + 1, y0 + 1, x1 - 1, y1 - 1, FLOOR)
        dy = door_y if door_y is not None else y1
        for x in range(x0, x1 + 1):
            grid[dy][x] = WALL
        half = 1
        for x in range(door_x - half, door_x + half + 1):
            if x0 < x < x1:
                grid[dy][x] = PATH
        # Walkable stone behind the building (city plaza continues north of the shell)
        for x in range(x0 + 1, x1):
            grid[y0][x] = STONE

    # Town houses along the west plaza
    _city_building(102, 60, 110, 68, door_x=106)
    _city_building(102, 74, 110, 82, door_x=106)
    # Barracks / armory east of square
    _city_building(130, 74, 138, 84, door_x=134)
    # 3-wide aprons south of city doors
    for cx, cy in ((106, 69), (106, 83), (134, 85)):
        for ox in (-1, 0, 1):
            dx, dy = cx + ox, cy
            if 0 <= dx < WIDTH and 0 <= dy < HEIGHT and grid[dy][dx] != WALL:
                grid[dy][dx] = PATH

    # Castle keep (north plaza) — thick walls, courtyard, battlements
    _rect(grid, 118, 58, 136, 70, WALL)
    _rect(grid, 120, 60, 134, 68, FLOOR)
    # Inner throne hall
    _rect(grid, 124, 61, 132, 66, FLOOR)
    # Gatehouse opening south into the plaza — wide entrance (5 tiles)
    for gx in range(126, 131):
        grid[70][gx] = PATH
        grid[69][gx] = PATH
        grid[68][gx] = STONE  # threshold into the courtyard
    # Courtyard stones just south of the keep (don't seal the gate)
    _rect(grid, 122, 71, 132, 74, STONE)
    # Keep apron + gate row stay walkable path
    for gx in range(126, 131):
        grid[70][gx] = PATH
        grid[71][gx] = PATH
        grid[72][gx] = PATH
    # Walkable stone behind the keep (north plaza continues outside the shell)
    for x in range(119, 136):
        grid[58][x] = STONE
    # Interior reads as flagstone (not grass under the keep volume)
    for y in range(60, 69):
        for x in range(120, 135):
            if grid[y][x] == FLOOR:
                grid[y][x] = STONE

    # Road from forest south into the city gate
    for y in range(40, cy0 + 1):
        for x in (118, 119):
            if grid[y][x] in (GRASS, *TREE_TILES, PATH, STONE):
                grid[y][x] = PATH
    # Path from dungeon fringe east into city (west gate)
    for x in range(82, cx0 + 1):
        if grid[72][x] in (GRASS, *TREE_TILES, PATH, WALL):
            if x < cx0 or grid[72][x] != WALL:
                grid[72][x] = PATH
    grid[72][cx0] = PATH  # west gate
    # Ensure city gates are walkable paths
    for gx, gy in ((118, cy1), (119, cy1), (120, cy1), (118, cy0), (119, cy0), (cx0, 71), (cx0, 72), (cx0, 73)):
        if 0 <= gx < WIDTH and 0 <= gy < HEIGHT:
            grid[gy][gx] = PATH

    # High forest belt north of the city — maple, yew, rare magic
    for _ in range(80):
        x = rng.randint(98, 130)
        y = rng.randint(44, 54)
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

    # --- Emberdeep volcano (far east edge) — conical massif + crater mouth ---
    vx0, vy0, vx1, vy1 = ZONES["volcano"]
    # Scorched foothills (ash grass)
    for y in range(vy0, vy1 + 1):
        for x in range(vx0, vx1 + 1):
            if grid[y][x] in (GRASS, *TREE_TILES):
                grid[y][x] = GRASS
    # Concentric basalt rings → reads as a rising cone
    rings = [
        (176, 58, 198, 80),  # outer foothills
        (178, 60, 196, 78),
        (180, 62, 194, 76),
        (182, 64, 192, 74),
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
    _rect(grid, 183, 65, 191, 71, WALL)
    _rect(grid, 184, 66, 190, 70, FLOOR)
    # Magma glow pit in crater center (blocked lava tile)
    grid[68][186] = WATER
    grid[68][187] = WATER
    grid[69][186] = WATER
    # Mouth tunnel opening south through the rings
    for y in range(70, 74):
        for x in range(185, 188):
            grid[y][x] = FLOOR
    # Apron / landing in front of the mouth
    _rect(grid, 182, 73, 191, 77, PATH)
    grid[72][186] = PATH  # old mouth; lair entrance moved south of the crater
    # Jagged outer peaks
    for _ in range(55):
        x = rng.randint(174, 198)
        y = rng.randint(57, 81)
        # Keep mouth corridor clear
        if 184 <= x <= 188 and 70 <= y <= 74:
            continue
        if abs(x - 186) + abs(y - 68) < 5:
            continue
        if grid[y][x] in (GRASS, PATH):
            grid[y][x] = WALL
    # Road from Stonehaven east gate to the far-east crater
    for x in range(cx1, 184):
        for y in (72, 73, 74):
            if 0 <= x < WIDTH and grid[y][x] in (GRASS, *TREE_TILES, PATH, WALL, STONE):
                grid[y][x] = PATH
    for y in (72, 73, 74):
        grid[y][cx1] = PATH  # east city gate
    # Dragon-lair mouth south of the crater, with a walk-in pad.
    _rect(grid, 180, 80, 194, 90, PATH)
    for y in range(78, 85):
        grid[y][186] = PATH
    for dx in (-1, 0, 1):
        grid[84][186 + dx] = PATH
        grid[83][186 + dx] = PATH
    grid[84][186] = FLOOR

    # --- Void Sanctum (SE mystical crypt) — dark building + 6 sealed rooms ---
    sx0, sy0, sx1, sy1 = ZONES["shadow_crypt"]
    _rect(grid, sx0, sy0, sx1, sy1, WALL)
    # Entrance building shell (matches BUILDINGS void_sanctum)
    _building(166, 102, 176, 108, door_x=171)
    # Six crypt rooms (must match DUNGEON_ROOMS)
    sanctum_rooms = [
        (156, 108, 164, 112),
        (168, 108, 178, 112),
        (156, 114, 164, 120),
        (168, 114, 178, 120),
        (156, 122, 164, 128),
        (168, 122, 178, 128),
    ]
    for room in sanctum_rooms:
        _rect(grid, *room, FLOOR)
    # Corridors between rooms + descent from the sanctum hall (wider for access)
    _rect(grid, 164, 109, 168, 111, FLOOR)   # room1 ↔ room2
    _rect(grid, 158, 112, 161, 114, FLOOR)   # room1 ↔ room3
    _rect(grid, 171, 112, 174, 114, FLOOR)   # room2 ↔ room4
    _rect(grid, 164, 116, 168, 118, FLOOR)   # room3 ↔ room4
    _rect(grid, 158, 120, 161, 122, FLOOR)   # room3 ↔ room5
    _rect(grid, 171, 120, 174, 122, FLOOR)   # room4 ↔ room6
    _rect(grid, 164, 124, 168, 126, FLOOR) # room5 ↔ room6
    # Descent: building interior floor → first corridor (3-wide)
    grid[107][171] = FLOOR
    _rect(grid, 169, 107, 173, 112, FLOOR)
    # Keep the south door + apron walkable (3-wide)
    for ax in (169, 170, 171, 172, 173):
        grid[108][ax] = PATH
        grid[109][ax] = PATH
        grid[110][ax] = PATH
    # Punch 3-wide door gap in the building south wall
    for ax in (170, 171, 172):
        grid[108][ax] = PATH
    # Road from Stonehaven to the sanctum door.
    # The expanded plaza sits beside the crypt, so that road leaves the east street.
    if cy1 > 110:
        for y in (98, 99):
            grid[y][cx1] = PATH
        for x in range(cx1, 172):
            for yy in (98, 99):
                if grid[yy][x] in (GRASS, PATH, STONE, WALL):
                    grid[yy][x] = PATH
        for y in range(99, 110):
            for x in (170, 171, 172):
                if grid[y][x] in (GRASS, PATH, WALL) and not (166 < x < 176 and 102 < y < 108):
                    grid[y][x] = PATH
    else:
        for x in range(118, 172):
            for yy in (cy1 + 1, cy1 + 2):
                if 0 <= yy < HEIGHT and grid[yy][x] in (GRASS, PATH, STONE, WALL):
                    if yy == cy1:
                        continue
                    grid[yy][x] = PATH
        for y in range(cy1 + 1, 110):
            for x in (170, 171, 172):
                if grid[y][x] in (GRASS, PATH, WALL) and not (166 < x < 176 and 102 < y < 108):
                    grid[y][x] = PATH
    grid[108][171] = PATH

    castle_v2.apply_stamp(grid, sys.modules[__name__])
    buildings_v2.apply_stamp(grid, sys.modules[__name__])
    import housing
    housing.stamp(grid, sys.modules[__name__])
    import fairy_village
    fairy_village.stamp(grid)
    _clear_trees_near_buildings(grid)
    _paint_void_grounds(grid)
    _lay_wayfinder_roads(grid)
    return grid


# Building footprints — keep in sync with content.BUILDINGS (avoid import cycle)
_BUILDING_FOOTPRINTS = [
    # village
    (4, 4, 15, 15), (40, 4, 51, 15), (4, 36, 15, 47), (40, 36, 51, 47),
    (58, 18, 70, 28), (78, 4, 94, 18), (78, 36, 92, 48),
    (60, 37, 72, 47),
    # harbour
    (172, 6, 182, 14), (172, 20, 182, 28),
    # city — tree clearing keeps the old keep rect. The v2 stamp already
    # replaces every tile inside the new footprint, and the client hides
    # canopy sprites against the expanded building rect. Widening this rect
    # would turn margin trees into grass and open new walkable tiles.
    (102, 60, 110, 68), (102, 74, 110, 82), (130, 74, 138, 84), (118, 58, 136, 70),
    # void sanctum entrance building
    (166, 102, 176, 108),
    # tidehollow cave mouth (south of the harbour)
    (176, 28, 192, 40),
    # emberdeep lair mouth
    (180, 78, 194, 90),
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


def _stamp_road(grid, x0, y0, x1, y1, half=1):
    """Axis-aligned road, three tiles wide. Skips walls, water, and ore."""
    ok = {GRASS, PATH, STONE, FLOOR, *TREE_TILES}
    if x0 > x1:
        x0, x1 = x1, x0
    if y0 > y1:
        y0, y1 = y1, y0
    horizontal = y0 == y1
    for y in range(y0, y1 + 1):
        for x in range(x0, x1 + 1):
            for d in range(-half, half + 1):
                nx, ny = (x, y + d) if horizontal else (x + d, y)
                if not (0 <= nx < WIDTH and 0 <= ny < HEIGHT):
                    continue
                if grid[ny][nx] in ok:
                    grid[ny][nx] = PATH


def _lay_wayfinder_roads(grid):
    """Clear roads to every region. Runs after stamps so buildings cannot erase them.

    Walls, water, and the castle moat stay put. The road jogs around them.
    """
    roads = (
        # Village spine and the shop rows off it.
        (8, 24, 54, 24),
        (28, 16, 28, 52),
        (8, 17, 50, 17),
        (48, 17, 48, 21),
        (6, 50, 96, 50),
        (28, 50, 28, 56),
        # Around the bank, then east clear of the lake.
        (54, 24, 54, 32),
        (54, 32, 74, 32),
        (64, 28, 64, 32),
        (72, 24, 72, 32),
        (74, 32, 74, 25),
        (86, 19, 86, 26),
        (74, 25, 130, 25),
        (98, 22, 98, 25),
        # Forest up to the pass, across to Harbourreach, south to Tidehollow.
        (130, 16, 130, 25),
        (130, 16, 176, 16),
        (170, 15, 178, 15),
        (166, 16, 166, 36),
        (166, 36, 184, 36),
        # Mine's east side, down to the dungeon mouth.
        (42, 52, 42, 72),
        (36, 71, 42, 71),
        # West of the castle moat, into Stonehaven's west gate.
        (108, 25, 108, 54),
        (92, 54, 108, 54),
        (92, 54, 92, 72),
        # City streets, Emberdeep, and the sanctum approach.
        (94, 72, 150, 72),
        (118, 73, 118, 130),
        (128, 73, 128, 125),
        (150, 73, 184, 73),
        (186, 73, 186, 86),
        (100, 98, 180, 98),
        (180, 98, 180, 101),
        (168, 100, 180, 100),
    )
    for seg in roads:
        _stamp_road(grid, *seg)
    # Designed mouths. These few cells are the gates, not building walls.
    for x, y in (
        (94, 71), (94, 72), (94, 73),
        (152, 72), (152, 73), (152, 74),
        (170, 108), (171, 108), (172, 108),
    ):
        if 0 <= x < WIDTH and 0 <= y < HEIGHT and grid[y][x] != WATER:
            grid[y][x] = PATH
    for y in range(74, 87):
        for x in (185, 186, 187):
            if grid[y][x] != WATER:
                grid[y][x] = PATH


def _paint_void_grounds(grid):
    """Walkable void floor around the sanctum. Room walls and the gatehouse stay."""
    x0, y0, x1, y1 = ZONES["shadow_crypt"]
    building = (166, 102, 176, 108)
    rooms = [
        (156, 108, 164, 112),
        (168, 108, 178, 112),
        (156, 114, 164, 120),
        (168, 114, 178, 120),
        (156, 122, 164, 128),
        (168, 122, 178, 128),
    ]

    def _ring(x, y, rect):
        rx0, ry0, rx1, ry1 = rect
        if rx0 - 1 <= x <= rx1 + 1 and ry0 - 1 <= y <= ry1 + 1:
            return not (rx0 <= x <= rx1 and ry0 <= y <= ry1)
        return False

    for y in range(y0, y1 + 1):
        for x in range(x0, x1 + 1):
            tile = grid[y][x]
            if tile in (WATER, STONE):
                continue
            if tile == WALL and (
                _ring(x, y, building)
                or (building[0] <= x <= building[2] and building[1] <= y <= building[3])
                or any(_ring(x, y, room) for room in rooms)
            ):
                continue
            if tile in (WALL, GRASS, PATH, *TREE_TILES):
                grid[y][x] = FLOOR


def get_zone(x, y):
    if castle_v2.counts_as_city(x, y):
        return "city"
    x0, y0, x1, y1 = city_bounds()
    if x0 <= x <= x1 and y0 <= y <= y1:
        return "city"
    for name, (x0, y0, x1, y1) in ZONES.items():
        if name == "city":
            continue
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
