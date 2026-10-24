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

# Larger world — room east of the massif for Stonehaven walls + housing.
WIDTH = 230
HEIGHT = 145

# Zone bounding boxes (x0, y0, x1, y1) inclusive
ZONES = {
    "village": (1, 1, 92, 52),
    "forest":  (98, 1, 132, 42),
    # Wolf Pass + keep sit here after SHIFT_X (-24 from the authored 136–165 pack).
    "mountains": (110, 1, 145, 42),
    "fishing_village": (168, 1, 198, 42),
    "mine":    (50, 99, 84, 132),
    "fairy_village": (1, 56, 40, 88),
    "dungeon": (44, 54, 90, 143),
    "city":    (98, 56, 148, 96),  # flag-off shell. city_bounds() grows it.
    "volcano": (188, 58, 220, 96),  # Emberdeep cone slid east
    # Void slid east (VOID_DX) so it no longer eats Stonehaven's east wall.
    "shadow_crypt": (183, 96, 228, 143),
}

SPAWN_POINT = (28, 24)  # village crossroads


def city_bounds():
    """Stonehaven plaza (room east of the keep for a few castle-side homes)."""
    if feature_flags.USE_NEW_BUILDINGS:
        # West curtain pulled in +7 → open land outside; east edge unchanged.
        return (101, 56, 162, 132)
    return ZONES["city"]

# Void Sanctum shift east of Stonehaven (authored mouth was x=175).
VOID_DX = 30

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
    # Void Sanctum (SE mystical crypt) — in shadow_crypt zone (+VOID_DX)
    (156 + VOID_DX, 108, 164 + VOID_DX, 112),   # shades
    (168 + VOID_DX, 108, 178 + VOID_DX, 112),   # crypt ghouls
    (156 + VOID_DX, 114, 164 + VOID_DX, 120),   # void imps
    (168 + VOID_DX, 114, 178 + VOID_DX, 120),   # obsidian colossi
    (156 + VOID_DX, 122, 164 + VOID_DX, 128),   # shadow knights
    (168 + VOID_DX, 122, 178 + VOID_DX, 128),   # void horror
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


    # Spacious village ring around spawn (28,24) / well (32,22).
    # Shells match buildings_v2._OLD_SHELL (v2 stamp grows to pack art).
    # Plaza ~x20–48, y14–30 stays open so roofs cannot cover the hub.
    # NW cottage (Elder Miriam) — door (14, 13)
    _building(8, 3, 25, 13, door_x=14)
    # NE shop (Shopkeeper Joe) — door (42, 13)
    _building(37, 3, 49, 13, door_x=42)
    # SW inn (Innkeeper Sarah) — door (14, 42)
    _building(8, 30, 23, 42, door_x=14)
    # SE cottage (Farmer Tom) — door (56, 64), east of Fairy Glade
    _building(51, 54, 65, 64, door_x=56)
    # Bank — door (44, 33), east of the plaza
    _building(38, 25, 50, 33, door_x=44)
    # Smithy — door (88, 52), south of the crypt / east of pet
    _building(80, 38, 96, 52, door_x=88)
    # Pet Emporium — door (70, 52), north of the dungeon capture rect
    _building(64, 41, 79, 52, door_x=70)

    # Restore village roads (do not punch through walls)
    for x in range(vx0, min(vx1, 94) + 1):
        if grid[road_y][x] != WALL:
            grid[road_y][x] = PATH
    for y in range(vy0, vy1 + 1):
        if grid[y][road_x] != WALL:
            grid[y][road_x] = PATH
    # 3-wide apron tiles outside village doors + wishing-well plaza
    door_aprons = (
        (14, 14), (42, 14), (14, 43), (56, 65),
        (44, 34), (70, 53), (88, 53), (56, 85),
        (9, 19), (9, 20), (8, 19), (10, 19),  # Castle Realm portal apron
    )
    for cx, cy in door_aprons:
        for ox in (-1, 0, 1):
            dx, dy = cx + ox, cy
            if 0 <= dx < WIDTH and 0 <= dy < HEIGHT and grid[dy][dx] != WALL:
                grid[dy][dx] = PATH
    for dx, dy in (
        (32, 22), (31, 22), (33, 22), (32, 21), (32, 23),  # wishing well
        (28, 24), (27, 24), (29, 24), (28, 23), (28, 25),  # spawn plaza
        (30, 22), (34, 22), (32, 24), (30, 24), (34, 24),
    ):
        if 0 <= dx < WIDTH and 0 <= dy < HEIGHT and grid[dy][dx] != WALL:
            grid[dy][dx] = PATH

    # --- Starter trees on village fringe (outside the open plaza + ring) ---
    # Core stays clear so hub sightlines and door approaches stay open.
    village_fringe = []
    for y in range(vy0 + 1, vy1):
        for x in range(vx0 + 1, min(vx1, 90)):
            if grid[y][x] != GRASS:
                continue
            if 6 <= x <= 96 and 2 <= y <= 88:
                continue
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

    # --- Forest + lake (west of Wolf Pass; water first, then spaced trees) ---
    fx0, fy0, fx1, fy1 = ZONES["forest"]
    # Lake sits west of the shifted massif (wolf x0=112); leave east (x=108+)
    # and south (y=22+) as shore so the path + Mad Scientist stay on land.
    lake = (96, 11, 107, 21)
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

    # Keep the lake clear if trees landed on the shore ring; path south → pass.
    for y in range(lake[1], lake[3] + 1):
        for x in range(lake[0], lake[2] + 1):
            if grid[y][x] in TREE_TILES:
                grid[y][x] = WATER
    # South shore road (connects west approach → east shore → Wolf Pass)
    for y in (22, 23, 24):
        for x in range(96, 112):
            if grid[y][x] in (GRASS, *TREE_TILES, PATH, WATER):
                grid[y][x] = PATH
    # East shore path along the lake (must punch water if lake overgrew)
    for y in range(12, 25):
        for x in (108, 109):
            if grid[y][x] in (GRASS, *TREE_TILES, PATH, WATER):
                grid[y][x] = PATH
    # Link village road into forest
    for x in range(90, 98):
        if grid[road_y][x] in (GRASS, *TREE_TILES):
            grid[road_y][x] = PATH

    # Clear small plazas so key NPCs aren't buried under canopy
    for nx, ny in (
        (102, 8), (103, 8), (102, 9), (101, 8),                 # Mia
        (100, 23), (99, 23), (101, 23), (100, 24), (100, 22),  # Mad Scientist (south shore)
        (94, 16), (95, 16), (93, 16), (94, 15), (94, 17),  # Pete (west lake shore)
        (28, 22), (29, 22), (28, 21),                       # Timmy
    ):
        if 0 <= nx < WIDTH and 0 <= ny < HEIGHT and grid[ny][nx] in (GRASS, *TREE_TILES, PATH, WATER):
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
    if getattr(feature_flags, "USE_WOLF_PASS", False):
        import wolf_pass
        if wolf_pass.geo():
            # Painted massif (MOUNTAIN_SPEC.md): clear every old grey ridge tile, then the art's collision.
            for y in range(my0, my1 + 1):
                for x in range(mx0, mx1 + 1):
                    if grid[y][x] == WALL:
                        grid[y][x] = GRASS
            wolf_pass.apply(grid, PATH, GRASS, WALL)

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

    # Tidehollow cave — a little further south of the harbour, clear of the shops.
    _rect(grid, 176, 38, 192, 48, GRASS)
    for y in range(37, 47):
        if grid[y][184] != WATER:
            grid[y][184] = PATH
    for dx in (-1, 0, 1):
        grid[44][184 + dx] = PATH
        grid[43][184 + dx] = PATH
    grid[44][184] = FLOOR

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

    # --- Stonehaven City (east of dungeon, south of forest / castle gate) ---
    cx0, cy0, cx1, cy1 = city_bounds()
    # Outer stone plaza (full ward — housing stamps over east plots later)
    _rect(grid, cx0 + 1, cy0 + 1, cx1 - 1, cy1 - 1, STONE)
    # Style B city walls: 2-tile-thick shell with gatehouses (south / west / north→castle).
    _stamp_stonehaven_walls(grid, cx0, cy0, cx1, cy1)
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
        for x in range(100, min(cx1 - 1, 150)):
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

    # Town houses along the west plaza (cleared of the west curtain by +7)
    _city_building(109, 60, 117, 68, door_x=113)
    _city_building(109, 74, 117, 82, door_x=113)
    # Barracks / armory east of square
    _city_building(130, 74, 138, 84, door_x=134)
    # Same village bank, three tiles south of the barracks door line.
    _city_building(135, 105, 145, 112, door_x=140)
    # 3-wide aprons south of city doors
    for cx, cy in ((113, 69), (113, 83), (134, 85)):
        for ox in (-1, 0, 1):
            dx, dy = cx + ox, cy
            if 0 <= dx < WIDTH and 0 <= dy < HEIGHT and grid[dy][dx] != WALL:
                grid[dy][dx] = PATH

    # Castle keep (north plaza). With the v2 castle on, the keep stands by
    # Wolf Pass instead (castle_v2.DX/DY) and this ground stays open plaza.
    if not castle_v2.active():
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

    # Road from forest south into the city / castle approach (west of keep)
    for y in range(40, cy0 + 1):
        for x in (118, 119):
            if grid[y][x] in (GRASS, *TREE_TILES, PATH, STONE):
                grid[y][x] = PATH
    # Path from dungeon fringe toward the west wall (stops at the solid curtain)
    for x in range(82, cx0):
        if grid[72][x] in (GRASS, *TREE_TILES, PATH, WALL):
            grid[72][x] = PATH
    # Wide south gate only (no west/east side gates)
    for gx in range(116, 123):
        for gy in (cy1, cy1 - 1):
            if 0 <= gx < WIDTH and 0 <= gy < HEIGHT:
                grid[gy][gx] = PATH
    if castle_v2.active():
        ax0, _ = castle_v2.w(104, 55)
        ax1, _ = castle_v2.w(119, 55)
        for ax in range(ax0, ax1 + 1):
            for oy in (0, 1, 2):
                ay = cy0 + oy
                if 0 <= ax < WIDTH and 0 <= ay < HEIGHT and grid[ay][ax] in (WALL, GRASS, *TREE_TILES, PATH, STONE):
                    grid[ay][ax] = PATH if oy == 0 else STONE

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

    # --- City east approach (south bypass under Emberdeep is laid with roads) ---
    for x in range(cx1, min(WIDTH - 1, 190)):
        for y in (72, 73, 74):
            if 0 <= x < WIDTH and grid[y][x] in (GRASS, *TREE_TILES, PATH, WALL, STONE):
                grid[y][x] = PATH
    for y in (72, 73, 74):
        grid[y][cx1] = PATH

    # --- Void Sanctum (SE mystical crypt) — dark building + 6 sealed rooms ---
    vd = VOID_DX
    sx0, sy0, sx1, sy1 = ZONES["shadow_crypt"]
    _rect(grid, sx0, sy0, sx1, sy1, WALL)
    # Entrance building shell (matches BUILDINGS void_sanctum) — south massif mouth
    _building(169 + vd, 122, 181 + vd, 128, door_x=175 + vd)
    # Six crypt rooms (must match DUNGEON_ROOMS)
    sanctum_rooms = [
        (156 + vd, 108, 164 + vd, 112),
        (168 + vd, 108, 178 + vd, 112),
        (156 + vd, 114, 164 + vd, 120),
        (168 + vd, 114, 178 + vd, 120),
        (156 + vd, 122, 164 + vd, 128),
        (168 + vd, 122, 178 + vd, 128),
    ]
    for room in sanctum_rooms:
        _rect(grid, *room, FLOOR)
    # Corridors between rooms + descent toward the south mouth
    _rect(grid, 164 + vd, 109, 168 + vd, 111, FLOOR)   # room1 ↔ room2
    _rect(grid, 158 + vd, 112, 161 + vd, 114, FLOOR)   # room1 ↔ room3
    _rect(grid, 171 + vd, 112, 174 + vd, 114, FLOOR)   # room2 ↔ room4
    _rect(grid, 164 + vd, 116, 168 + vd, 118, FLOOR)   # room3 ↔ room4
    _rect(grid, 158 + vd, 120, 161 + vd, 122, FLOOR)   # room3 ↔ room5
    _rect(grid, 171 + vd, 120, 174 + vd, 122, FLOOR)   # room4 ↔ room6
    _rect(grid, 164 + vd, 124, 168 + vd, 126, FLOOR)   # room5 ↔ room6
    _rect(grid, 172 + vd, 120, 178 + vd, 128, FLOOR)   # hall into south mouth
    # South door + apron (VOID_MOUTH) — 3-wide enter zone
    mx_void = 175 + vd
    for ax in (mx_void - 2, mx_void - 1, mx_void, mx_void + 1, mx_void + 2):
        if 0 <= ax < WIDTH:
            grid[128][ax] = PATH
            if 129 < HEIGHT:
                grid[129][ax] = PATH
            if 130 < HEIGHT:
                grid[130][ax] = PATH
    for ax in (mx_void - 1, mx_void, mx_void + 1):
        if 0 <= ax < WIDTH:
            grid[128][ax] = PATH
    # Road from Stonehaven / east city into the south void mouth.
    if cy1 > 110:
        for y in (98, 99):
            grid[y][cx1] = PATH
        for x in range(cx1, mx_void + 1):
            for yy in (98, 99):
                if grid[yy][x] in (GRASS, PATH, STONE, WALL):
                    grid[yy][x] = PATH
        for y in range(99, 131):
            for x in (mx_void - 1, mx_void, mx_void + 1):
                if grid[y][x] in (GRASS, PATH, WALL, FLOOR) and not (
                    169 + vd < x < 181 + vd and 122 < y < 128
                ):
                    grid[y][x] = PATH
    else:
        for x in range(118, mx_void + 1):
            for yy in (cy1 + 1, cy1 + 2):
                if 0 <= yy < HEIGHT and grid[yy][x] in (GRASS, PATH, STONE, WALL):
                    if yy == cy1:
                        continue
                    grid[yy][x] = PATH
        for y in range(cy1 + 1, 131):
            for x in (mx_void - 1, mx_void, mx_void + 1):
                if grid[y][x] in (GRASS, PATH, WALL, FLOOR) and not (
                    169 + vd < x < 181 + vd and 122 < y < 128
                ):
                    grid[y][x] = PATH
    grid[128][mx_void] = PATH

    castle_v2.apply_stamp(grid, sys.modules[__name__])
    buildings_v2.apply_stamp(grid, sys.modules[__name__])
    import housing
    housing.stamp(grid, sys.modules[__name__])
    if housing.enabled():
        import property as _property
        _property.stamp(grid, sys.modules[__name__])
    import fairy_village
    fairy_village.stamp(grid)
    _clear_trees_near_buildings(grid)
    _paint_void_grounds(grid)
    _lay_wayfinder_roads(grid)
    # Last: the castle's outer moat, the harbour seal and the Fairy Glade ring.
    # They run after the roads so no road reopens a gap through them.
    castle_v2.apply_outer_moat(grid, sys.modules[__name__])
    import harbour_seal
    harbour_seal.stamp(grid, sys.modules[__name__])
    import fairy_glade
    fairy_glade.stamp(grid, sys.modules[__name__])
    lay_fairy_glade_approach(grid)
    # Aprons + orphan trim after seals so harbour/fairy stamps cannot wipe them.
    _stamp_exterior_door_aprons(grid)
    trim_orphan_village_paths(grid)
    # Arch posts must stay trunks after apron/trim road stamps.
    for ax, ay in fairy_glade.arch_posts():
        if 0 <= ay < HEIGHT and 0 <= ax < WIDTH:
            grid[ay][ax] = WALL
    restore_city_and_void_paving(grid)
    return grid


# Building footprints — keep in sync with content.BUILDINGS (avoid import cycle)
_BUILDING_FOOTPRINTS = [
    # spacious village ring (plaza clear around spawn/well)
    (8, 3, 25, 13), (37, 3, 49, 13), (8, 30, 23, 42), (51, 54, 65, 64),
    (38, 25, 50, 33), (80, 38, 96, 52), (64, 41, 79, 52),
    (50, 74, 63, 84),  # outfitters
    (81, 6, 89, 10),   # estate office (door 85, 10)
    (135, 105, 145, 112),
    # harbour
    (172, 6, 182, 14), (172, 20, 182, 28),
    # city — tree clearing keeps the old keep rect (now open plaza; the keep
    # moved by Wolf Pass, see castle_v2.DX/DY). The v2 stamp already
    # replaces every tile inside the new footprint, and the client hides
    # canopy sprites against the expanded building rect. Widening this rect
    # would turn margin trees into grass and open new walkable tiles.
    (109, 60, 117, 68), (109, 74, 117, 82), (130, 74, 138, 84), (118, 58, 136, 70),
    # void sanctum entrance building (south massif mouth, +VOID_DX)
    (169 + VOID_DX, 122, 181 + VOID_DX, 128),
    # tidehollow cave mouth, south of Harbourreach
    (186, 49, 194, 56),
    # crypt graveyard east of the plaza
    (52, 4, 74, 20),
]


# Graveyard east of the compact plaza. Inclusive outer wall.
GRAVEYARD = (54, 4, 74, 18)
GRAVEYARD_GATE = ((63, 18), (64, 18), (65, 18))
CRYPT_MOUTH = (64, 11)
GRAVEYARD_GRAVES = (
    (56, 7), (56, 10), (56, 13), (56, 16),
    (57, 8), (57, 15),
    (71, 8), (71, 15),
    (72, 7), (72, 10), (72, 13), (72, 16),
)


def is_graveyard_wall(x, y) -> bool:
    x0, y0, x1, y1 = GRAVEYARD
    ix, iy = int(x), int(y)
    if not (x0 <= ix <= x1 and y0 <= iy <= y1):
        return False
    if (ix, iy) in GRAVEYARD_GATE:
        return False
    return ix in (x0, x1) or iy in (y0, y1)


def is_stonehaven_fort_wall(x, y) -> bool:
    """Outer Style-B city shell (not the open castle approach) and flank spurs."""
    ix, iy = int(x), int(y)
    cx0, cy0, cx1, cy1 = city_bounds()
    # North ring is open toward the keep — not a fort wall footing.
    on_south = (cy1 - 1 <= iy <= cy1) and cx0 <= ix <= cx1
    on_sides = (
        (cx0 <= ix <= cx0 + 1 or cx1 - 1 <= ix <= cx1)
        and cy0 <= iy <= cy1
    )
    if on_south or on_sides:
        return True
    if not castle_v2.active():
        return False
    x0, y0, x1, y1 = castle_v2.footprint_tiles()
    west_x = x0 - castle_v2.MOAT_SIDE - 1
    east_x = x1 + castle_v2.MOAT_SIDE + 1
    y_lo = max(0, y0 - castle_v2.MOAT_BACK)
    if y_lo <= iy <= cy0 and ix in (west_x, west_x - 1, east_x, east_x + 1):
        return True
    cap_y = max(0, y0 - castle_v2.MOAT_BACK - 1)
    return iy == cap_y and west_x - 1 <= ix <= east_x + 1


def is_grave(x, y) -> bool:
    return (int(x), int(y)) in GRAVEYARD_GRAVES


# Crater on the open ground south of the castle. The mouth is the tile the
# player was standing on; the walk-up is the two tiles south of it.
# East volcano massif — 3-wide cave door faces south onto the apron.
EMBERDEEP_MOUTH = (196, 78)
EMBERDEEP_RETURN = (196, 81)

# Giant-rat mine (village-south pit). Door x is fixed — not the Emberdeep mouth.
VOLCANO_MINE_DOOR_X = 67
VOLCANO_MINE = (50, 99, 84, 132)
VOLCANO_MINE_FLOOR = (51, 100, 83, 131)
VOLCANO_MINE_REVEAL = (50, 98, 84, 132)
VOLCANO_RAT_LEASH = (51, 100, 83, 113)
VOLCANO_WOLF_LEASH = (51, 114, 83, 131)


def relayout_village_south_roads(grid):
    """Re-paint south-spur roads after explore_dungeons.capture_and_hide.

    Roads jog around building shells (never through floors) and meet every door.
    """
    for seg in (
        (56, 43, 56, 53),       # plaza south toward farm (stop north of shell)
        (56, 53, 67, 53),       # jog east around the farm (east of x65 shell)
        (67, 24, 67, 53),       # east spur: hub → south of Pet / Smithy row
        (67, 53, 89, 53),       # Pet + Smithy door aprons
        (49, 53, 49, 66),       # west of farm: fairy road → farm door row
        (49, 65, 57, 66),       # into Farmhouse door
        (56, 65, 56, 73),       # farm door → north of Outfitters shell
        (56, 65, 88, 65),       # farm / smithy east link
        (56, 85, 56, 86),       # Outfitters door apron
        # South bypass under Emberdeep (city road y=73 is blocked by the cone).
        (150, 80, 202, 80),
        (202, 73, 202, 80),
    ):
        _stamp_road(grid, *seg)


def trim_orphan_village_paths(grid):
    """Turn PATH that leads nowhere into grass (whole map, fairy-safe).

    Keeps anything reachable from spawn, Fairy Glade lanes, and petal avenues
    inside the fairy_village zone. STONE plazas are never touched.
    """
    from collections import deque
    import fairy_glade

    h = len(grid)
    w = len(grid[0]) if h else 0
    sx, sy = SPAWN_POINT
    if not (0 <= sy < h and 0 <= sx < w) or grid[sy][sx] != PATH:
        # Prefer a PATH neighbour of spawn if the spawn tile itself is grass.
        start = None
        for dx, dy in ((0, 0), (1, 0), (-1, 0), (0, 1), (0, -1)):
            nx, ny = sx + dx, sy + dy
            if 0 <= ny < h and 0 <= nx < w and grid[ny][nx] == PATH:
                start = (nx, ny)
                break
        if start is None:
            return
        sx, sy = start
    seen = {(sx, sy)}
    q = deque([(sx, sy)])
    while q:
        x, y = q.popleft()
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            nx, ny = x + dx, y + dy
            if not (0 <= ny < h and 0 <= nx < w) or (nx, ny) in seen:
                continue
            if grid[ny][nx] != PATH:
                continue
            seen.add((nx, ny))
            q.append((nx, ny))
    lane = fairy_glade.lane_cells()
    fx0, fy0, fx1, fy1 = ZONES["fairy_village"]
    hv0, hvy0, hv1, hvy1 = ZONES["fishing_village"]
    # Wolf Pass floor is PATH but often only joins the village via city STONE,
    # which this BFS does not cross — keep the massif + its west approach.
    wolf_keep = set()
    try:
        import wolf_pass as _wp
        if _wp.enabled() and _wp.bounds():
            wx0, wy0, wx1, wy1 = _wp.bounds()
            r0, r1 = (_wp.geo().get("road") or (14, 17))
            for y in range(wy0, wy1 + 1):
                for x in range(wx0, wx1 + 1):
                    wolf_keep.add((x, y))
            for x in range(max(0, wx0 - 8), wx0):
                for y in range(r0, r1 + 1):
                    wolf_keep.add((x, y))
            for x in range(wx1 + 1, min(w, wx1 + 4)):
                for y in range(r0, r1 + 1):
                    wolf_keep.add((x, y))
    except Exception:
        pass
    for y in range(h):
        for x in range(w):
            if grid[y][x] != PATH or (x, y) in seen:
                continue
            if (x, y) in lane or (x, y) in wolf_keep:
                continue
            if fx0 <= x <= fx1 and fy0 <= y <= fy1:
                continue
            # Harbourreach pier / shore PATH joins spawn via STONE/Wolf Pass —
            # never orphan-trim the decking into grass.
            if hv0 <= x <= hv1 and hvy0 <= y <= hvy1:
                continue
            grid[y][x] = GRASS


def stamp_outfitters_shell(grid):
    """Outfitters south of the farm (door 56, 84), clear of Fairy Glade."""
    relayout_village_south_roads(grid)
    x0, y0, x1, y1, door_x = 50, 74, 63, 84, 56
    _rect(grid, x0, y0, x1, y1, WALL)
    _rect(grid, x0 + 1, y0 + 1, x1 - 1, y1 - 1, FLOOR)
    for x in range(x0, x1 + 1):
        grid[y1][x] = WALL
    for x in range(door_x - 1, door_x + 2):
        if x0 < x < x1:
            grid[y1][x] = PATH
    for x in range(x0 + 1, x1):
        grid[y0][x] = GRASS
    for ox in (-1, 0, 1):
        ax, ay = door_x + ox, y1 + 1
        if 0 <= ax < WIDTH and 0 <= ay < HEIGHT and grid[ay][ax] != WATER:
            grid[ay][ax] = PATH
    # Approach from the farm stops at the north wall — skirt west around the
    # shell to the south door instead of punching through the floor.
    _stamp_road(grid, door_x, 65, door_x, y0 - 1)   # farm → north of shell
    _stamp_road(grid, door_x, y0 - 1, x0 - 2, y0 - 1)
    _stamp_road(grid, x0 - 2, y0 - 1, x0 - 2, y1 + 1)
    _stamp_road(grid, x0 - 2, y1 + 1, door_x + 1, y1 + 1)
    lay_void_sanctum_approach(grid)
    lay_fairy_glade_approach(grid)
    lay_east_village_road(grid)
    _stamp_exterior_door_aprons(grid)
    trim_orphan_village_paths(grid)
    import fairy_glade
    for ax, ay in fairy_glade.arch_posts():
        if 0 <= ay < HEIGHT and 0 <= ax < WIDTH:
            grid[ay][ax] = WALL
    restore_city_and_void_paving(grid)


def stamp_emberdeep_mouth(grid):
    """Solid volcano cone (WALL) with a south-facing 3-wide cave door.

    Players approach from the south apron, stand on any of the three door
    tiles, then enter. The cone itself is not walkable. A wide scorched
    basalt field surrounds the cone (client paints AI volcano floor).
    """
    mx, my = EMBERDEEP_MOUTH
    # Unwalkable basalt mass north of the door (under the oversized sprite).
    for y in range(my - 7, my):
        for x in range(mx - 6, mx + 7):
            if not (0 <= x < WIDTH and 0 <= y < HEIGHT) or grid[y][x] == WATER:
                continue
            if ((x - mx) / 5.5) ** 2 + ((y - (my - 3)) / 4.2) ** 2 <= 1.0:
                grid[y][x] = WALL
    # Wide scorched field — walkable STONE the client dresses as volcano floor.
    for y in range(my - 2, my + 10):
        for x in range(mx - 10, mx + 11):
            if not (0 <= x < WIDTH and 0 <= y < HEIGHT) or grid[y][x] == WATER:
                continue
            if ((x - mx) / 9.5) ** 2 + ((y - (my + 3)) / 6.5) ** 2 > 1.0:
                continue
            if grid[y][x] == WALL:
                continue
            if grid[y][x] in (GRASS, PATH, FLOOR, STONE, *TREE_TILES):
                grid[y][x] = STONE
    # Small lava pools (WATER in volcano zone → client lava)
    for lx, ly in ((mx - 7, my + 5), (mx + 6, my + 4), (mx - 3, my + 7), (mx + 4, my + 8)):
        if 0 <= lx < WIDTH and 0 <= ly < HEIGHT and grid[ly][lx] != WALL:
            grid[ly][lx] = WATER
            for ox, oy in ((1, 0), (0, 1), (-1, 0)):
                nx, ny = lx + ox, ly + oy
                if 0 <= nx < WIDTH and 0 <= ny < HEIGHT and grid[ny][nx] in (GRASS, PATH, STONE, *TREE_TILES):
                    grid[ny][nx] = WATER
    # Scorched walkable apron at the door and south of it (enter zone).
    for y in range(my, my + 4):
        for x in range(mx - 2, mx + 3):
            if not (0 <= x < WIDTH and 0 <= y < HEIGHT) or grid[y][x] == WATER:
                continue
            if grid[y][x] in (GRASS, PATH, FLOOR, STONE, WALL, *TREE_TILES):
                grid[y][x] = PATH
    # 3-wide cave mouth + apron in front (enter from the opening, not past it).
    for ax in (mx - 1, mx, mx + 1):
        if not (0 <= ax < WIDTH):
            continue
        for ay in (my, my + 1, my + 2, my + 3):
            if 0 <= ay < HEIGHT:
                grid[ay][ax] = PATH
    # Keep the south city bypass clear after the cone stamp.
    _stamp_road(grid, 150, 80, 202, 80)
    _stamp_road(grid, 202, 73, 202, 80)
    restore_city_and_void_paving(grid)


def is_emberdeep_volcano_field(x, y) -> bool:
    """Walkable scorched ground around the Emberdeep cone (AI floor overlay)."""
    mx, my = EMBERDEEP_MOUTH
    ix, iy = int(x), int(y)
    if ((ix - mx) / 10.0) ** 2 + ((iy - (my + 3)) / 7.0) ** 2 > 1.0:
        return False
    return True


def near_volcano_mine(x, y) -> bool:
    x0, y0, x1, y1 = VOLCANO_MINE
    return x0 - 2 <= x <= x1 + 2 and y0 - 2 <= y <= y1 + 2


def stamp_volcano_mine(grid):
    """Rat mine south of the village pit, with a wide mithril and adamantite end."""
    x0, y0, x1, y1 = VOLCANO_MINE
    _rect(grid, x0, y0, x1, y1, WALL)
    _rect(grid, x0 + 1, y0 + 1, x1 - 1, y1 - 1, FLOOR)
    mx = VOLCANO_MINE_DOOR_X
    for x in (mx - 1, mx, mx + 1):
        if not (0 <= x < WIDTH):
            continue
        grid[y0][x] = PATH
        for y in range(81, y0):
            if grid[y][x] in (GRASS, PATH, FLOOR):
                grid[y][x] = PATH
    for x, y, iron in (
        (59, 101, False), (61, 101, False), (63, 101, False),
        (71, 101, True), (73, 101, True), (75, 101, True),
        (59, 105, False), (75, 105, True),
        (59, 109, True), (75, 109, False),
    ):
        grid[y][x] = IRON_ORE if iron else ORE
    for y in (116, 121, 126, 130):
        for x in (54, 59, 64):
            grid[y][x] = MITHRIL_ORE
        for x in (70, 75, 80):
            grid[y][x] = ADAMANTITE_ORE


def _stamp_crypt_graveyard(grid):
    """Stone-walled yard behind the bank, with a south gate and a path to the road."""
    x0, y0, x1, y1 = GRAVEYARD
    _border(grid, x0, y0, x1, y1, WALL, skip=set(GRAVEYARD_GATE))
    for x, y in GRAVEYARD_GATE:
        grid[y][x] = PATH
    mx, my = CRYPT_MOUTH
    for y in range(my, y1 + 3):
        for x in range(mx - 1, mx + 2):
            if 0 <= x < WIDTH and 0 <= y < HEIGHT and grid[y][x] != WATER:
                grid[y][x] = PATH
    grid[my][mx] = FLOOR
    # Path from the graveyard gate south/west into the compact plaza roads.
    for y in range(18, 25):
        for x in range(mx - 1, mx + 2):
            if grid[y][x] not in (WATER, WALL):
                grid[y][x] = PATH
    for x in range(48, mx + 2):
        if grid[24][x] not in (WATER, WALL):
            grid[24][x] = PATH


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


def lay_fairy_glade_approach(grid):
    """Join Guard Aldric's apron to the fairy road and keep the arch mouth open.

    fairy_glade.stamp leaves a 1-tile grass cut at (30,50)-(30,51) between the
    north pad and the east–west lane — that is the broken path in the arch shots.
    """
    import fairy_glade

    # Three-wide bridge: Aldric pad (27-29) → mouth lane (30-33) → east road.
    _stamp_road(grid, 27, 50, 36, 50)
    _stamp_road(grid, 27, 51, 36, 51)
    # Mouth under the arch (posts are restored to WALL after trim).
    _stamp_road(grid, 30, 51, 33, 56)
    # North spur from the village south lane down to the arch.
    _stamp_road(grid, 31, 43, 31, 52)
    # Fill the grass bite in the east–west approach (y45 x33-35).
    _stamp_road(grid, 30, 44, 36, 46)
    for ax, ay in fairy_glade.arch_posts():
        if 0 <= ay < HEIGHT and 0 <= ax < WIDTH:
            grid[ay][ax] = WALL


def lay_east_village_road(grid):
    """Village east road → Stonehaven gate.

    explore_dungeons.capture_and_hide clears depths to grass including the
    north edge row (y=54, x<=90), which punches a hole in this corridor.
    Safe to call after capture.
    """
    _stamp_road(grid, 80, 53, 108, 53)
    _stamp_road(grid, 80, 54, 108, 54)
    # Exact boundary cell the depths wipe leaves as grass.
    if 0 <= 54 < HEIGHT and 0 <= 90 < WIDTH and grid[54][90] in (GRASS, PATH, *TREE_TILES):
        grid[54][90] = PATH


# South massif void rift mouth (overworld pack entrance).
VOID_MOUTH = (175 + VOID_DX, 128)
VOID_RETURN = (175, 130)


def lay_void_sanctum_approach(grid):
    """Dirt corridor from the east city road to the Void Sanctum mouth.

    Safe to call after capture_and_hide — overwrites GRASS/FLOOR/trees.
    """
    mx, my = VOID_MOUTH
    # Approach from Stonehaven's east gate toward the shifted sanctum mouth.
    for seg in (
        (163, 97, mx + 1, 97),
        (163, 98, mx + 1, 98),
        (163, 99, mx + 1, 99),
        (mx - 1, 97, mx + 1, my + 2),
    ):
        _stamp_road(grid, *seg, also=(FLOOR,))
    for x, y in (
        (mx - 1, my), (mx, my), (mx + 1, my),
        (mx - 1, my + 1), (mx, my + 1), (mx + 1, my + 1),
        (mx - 1, my + 2), (mx, my + 2), (mx + 1, my + 2),
    ):
        if 0 <= x < WIDTH and 0 <= y < HEIGHT and grid[y][x] not in (WATER,):
            if grid[y][x] != WALL or (y == my and mx - 1 <= x <= mx + 1):
                grid[y][x] = PATH
    # Punch the three-wide door if the south wall resealed.
    for ax in (mx - 1, mx, mx + 1):
        if 0 <= ax < WIDTH:
            grid[my][ax] = PATH


def _path_spur_to_network(grid, ax, ay, ignore=None, limit=48):
    """Paint a 1-wide PATH spur from (ax,ay) to the nearest network PATH.

    Walks only through soft tiles (not WALL/WATER) so spurs skirt buildings.
    Returns True if a connection was made (or the cell is already on PATH).
    """
    from collections import deque

    ignore = ignore or set()
    soft = {GRASS, PATH, STONE, FLOOR, *TREE_TILES}
    if not (0 <= ax < WIDTH and 0 <= ay < HEIGHT):
        return False
    if grid[ay][ax] == PATH and (ax, ay) not in ignore:
        # Already on the network if some neighbour PATH is outside the apron.
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            nx, ny = ax + dx, ay + dy
            if 0 <= nx < WIDTH and 0 <= ny < HEIGHT and grid[ny][nx] == PATH:
                if (nx, ny) not in ignore:
                    return True
    q = deque([(ax, ay)])
    prev = {(ax, ay): None}
    found = None
    while q and found is None and len(prev) < limit * limit:
        x, y = q.popleft()
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            nx, ny = x + dx, y + dy
            if not (0 <= nx < WIDTH and 0 <= ny < HEIGHT) or (nx, ny) in prev:
                continue
            t = grid[ny][nx]
            if t not in soft:
                continue
            prev[(nx, ny)] = (x, y)
            if t == PATH and (nx, ny) not in ignore and (nx, ny) != (ax, ay):
                found = (nx, ny)
                break
            q.append((nx, ny))
    if found is None:
        return False
    cur = found
    while cur is not None:
        cx, cy = cur
        if grid[cy][cx] in soft:
            grid[cy][cx] = PATH
        cur = prev[cur]
    return True


def _stamp_exterior_door_aprons(grid):
    """3-wide PATH apron at every overworld door, spurred into the main road.

    Skips indoor/plane spots. Does not paint through WATER or solid WALL.
    """
    try:
        import content
    except Exception:
        return
    for spot in content.INTERACTABLES:
        if spot.get("plane"):
            continue
        kind = spot.get("kind")
        if kind not in ("door", "dungeon_entrance", "cave_entrance", "volcano_entrance"):
            continue
        x = int(spot.get("x", 0))
        y = int(spot.get("y", 0))
        # Prefer authored exit/stand south of the shell when present.
        if isinstance(spot.get("stand"), (list, tuple)) and len(spot["stand"]) >= 2:
            ax, ay = int(spot["stand"][0]), int(spot["stand"][1])
        elif spot.get("exit_x") is not None and spot.get("exit_y") is not None:
            ax, ay = int(spot["exit_x"]), int(spot["exit_y"])
        else:
            ax, ay = x, y + 1
        # Door gap + apron pad (south-facing shells).
        for nx, ny in ((x, y), (ax, ay)):
            if 0 <= nx < WIDTH and 0 <= ny < HEIGHT:
                if grid[ny][nx] in (GRASS, PATH, STONE, FLOOR, *TREE_TILES):
                    grid[ny][nx] = PATH
        apron = set()
        for ox in (-1, 0, 1):
            for oy in (0, 1):
                nx, ny = ax + ox, ay + oy
                if not (0 <= nx < WIDTH and 0 <= ny < HEIGHT):
                    continue
                if grid[ny][nx] in (GRASS, PATH, STONE, FLOOR, *TREE_TILES):
                    grid[ny][nx] = PATH
                    apron.add((nx, ny))
        apron.add((ax, ay))
        apron.add((x, y))
        # Soft BFS spur into the main PATH network (skirts walls).
        if not _path_spur_to_network(grid, ax, ay, ignore=apron, limit=64):
            _stamp_road(grid, ax, max(1, ay - 2), ax, ay, half=1, also=(FLOOR,))
        # Widen the apron after the spur lands.
        for ox in (-1, 0, 1):
            for oy in (0, 1):
                nx, ny = ax + ox, ay + oy
                if 0 <= nx < WIDTH and 0 <= ny < HEIGHT:
                    if grid[ny][nx] in (GRASS, PATH, STONE, FLOOR, *TREE_TILES):
                        grid[ny][nx] = PATH


def _stamp_road(grid, x0, y0, x1, y1, half=1, also=()):
    """Axis-aligned road, three tiles wide. Skips walls, water, and ore by default.

    Pass also=(FLOOR,) when reclaiming void grounds or similar walkable fills.
    """
    ok = {GRASS, PATH, STONE, *TREE_TILES, *also}
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
        # Spacious village spokes around spawn (28,24) / well (32,22).
        (12, 24, 80, 24),       # east–west hub through plaza
        (28, 12, 28, 51),       # north–south hub (stops north of Fairy thicket)
        (12, 14, 44, 14),       # north lane: Elder ↔ Store aprons
        (12, 43, 80, 43),       # south lane from Inn
        (28, 34, 45, 34),       # plaza → Bank door (south of shell, not through it)
        (9, 19, 28, 19),        # Castle Realm portal → west hub
        (56, 43, 56, 53),       # plaza south (stops north of farm)
        (56, 53, 67, 53),       # jog east around the farm
        (67, 24, 67, 53),       # east spur: hub → Pet / Smithy row
        (67, 53, 89, 53),       # Pet + Smithy door aprons
        (49, 53, 49, 66),       # west of farm → farm door row
        (49, 65, 57, 66),       # Farmhouse door
        (56, 65, 56, 73),       # farm door → north of Outfitters
        (56, 65, 88, 65),       # farm / smithy east link
        (56, 85, 56, 86),       # Outfitters door apron
        # Out of village east toward forest / lake / mad scientist.
        (84, 24, 130, 24),
        (85, 11, 85, 24),       # estate office apron → east hub road
        (100, 23, 100, 25),     # Mad Scientist south-shore plaza
        (96, 23, 112, 23),      # south lake shore connector
        # Forest up to the (west-shifted) pass, across to Harbourreach, Tidehollow.
        (108, 12, 108, 40),     # east lake shore (land corridor)
        (109, 12, 109, 25),
        (100, 16, 107, 16),      # north of lake only (does not cross water)
        (141, 16, 176, 16),      # east exit after the massif
        (170, 15, 178, 15),
        # Harbourreach is reached only through the pass now; the old
        # south road out of the harbour ends at the Harbour Inlet.
        (171, 16, 171, 36),
        (171, 36, 184, 36),
        (184, 36, 184, 41),
        # Tidehollow — skirt east of the housing ward (x 148–166).
        (167, 58, 172, 58),
        (172, 48, 172, 58),
        (172, 48, 188, 48),
        (188, 48, 188, 52),
        # Fairy Glade approach — village dirt up to the arch mouth.
        (31, 51, 54, 51),
        (31, 52, 54, 52),
        # East village → Stonehaven west gate (closes the grass cut at ~90,54).
        (80, 53, 108, 53),
        (80, 54, 108, 54),
        # Emberdeep south apron bypass — east of housing, then to the cone.
        (167, 80, 202, 80),
        (202, 73, 202, 80),
        # West of the keep, into Stonehaven's west gate.
        (108, 25, 108, 54),
        (92, 54, 108, 54),
        (92, 54, 92, 72),
        # City streets, Emberdeep, and the sanctum approach (east of city wall).
        (94, 72, 162, 72),
        (162, 72, 205, 72),
        (118, 73, 118, 130),
        (128, 73, 128, 125),
        (162, 73, 202, 73),
        (202, 73, 202, 86),
        (100, 98, 162, 98),
        (162, 98, 205, 98),
        (205, 98, 205, 128),
        (196, 98, 196, 101),
    )
    for seg in roads:
        _stamp_road(grid, *seg)
    lay_void_sanctum_approach(grid)
    # Designed mouths (void only — Stonehaven west/east curtains stay sealed).
    for x, y in (
        (VOID_MOUTH[0] - 1, 128), (VOID_MOUTH[0], 128), (VOID_MOUTH[0] + 1, 128),
        (VOID_MOUTH[0] - 1, 129), (VOID_MOUTH[0], 129), (VOID_MOUTH[0] + 1, 129),
    ):
        if 0 <= x < WIDTH and 0 <= y < HEIGHT and grid[y][x] not in (WATER, WALL):
            grid[y][x] = PATH
    for y in range(74, 87):
        for x in (185, 186, 187):
            if grid[y][x] != WATER:
                grid[y][x] = PATH
    # Tidehollow mouth on the grass where the player stood.
    for y in range(52, 55):
        for x in range(188, 191):
            if grid[y][x] != WATER:
                grid[y][x] = PATH
    grid[52][189] = FLOOR
    _stamp_crypt_graveyard(grid)
    # Door aprons + orphan trim run again at end of generate_world (after seals)
    # and in stamp_outfitters_shell (after capture_and_hide).


def _paint_void_grounds(grid):
    """Walkable void floor around the sanctum. Room walls and the gatehouse stay."""
    vd = VOID_DX
    x0, y0, x1, y1 = ZONES["shadow_crypt"]
    building = (169 + vd, 122, 181 + vd, 128)
    rooms = [
        (156 + vd, 108, 164 + vd, 112),
        (168 + vd, 108, 178 + vd, 112),
        (156 + vd, 114, 164 + vd, 120),
        (168 + vd, 114, 178 + vd, 120),
        (156 + vd, 122, 164 + vd, 128),
        (168 + vd, 122, 178 + vd, 128),
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
            # Keep the south approach / door apron as PATH so city dirt reaches
            # the sanctum mouth (wayfinder reclaims FLOOR afterward too).
            mx, my = VOID_MOUTH
            if mx - 3 <= x <= mx + 3 and my - 10 <= y <= my + 3 and tile == PATH:
                if not (building[0] < x < building[2] and building[1] < y < building[3]):
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


def _stamp_stonehaven_walls(grid, cx0, cy0, cx1, cy1):
    """Style B outer shell: 2-tile-thick walls, gatehouses, castle-side spurs.

    South / west / east enclose the plaza + housing ward. North opens onto the
    castle bridge; 2-tile spurs run up both flanks of the keep (outside the moat)
    so the wall reads as one fortification around castle + Stonehaven.
    """
    # South only — wide open arch. West/east are solid curtain (no side gates).
    gate_s = set()
    for gx in range(116, 123):
        gate_s.add((gx, cy1))
        gate_s.add((gx, cy1 - 1))
    # Full castle south apron open — no city door/wall in front of the keep.
    gate_n = set()
    if castle_v2.active():
        ax0, _ = castle_v2.w(104, 55)
        ax1, _ = castle_v2.w(119, 55)
        for gx in range(ax0, ax1 + 1):
            gate_n.add((gx, cy0))
            gate_n.add((gx, cy0 + 1))
    else:
        gate_n = {(118, cy0), (119, cy0), (118, cy0 + 1), (119, cy0 + 1)}
    skips = gate_s | gate_n

    def _wall_cell(x, y):
        if (x, y) in skips:
            return
        if 0 <= x < WIDTH and 0 <= y < HEIGHT:
            grid[y][x] = WALL

    # Double ring on the plaza rectangle
    for x in range(cx0, cx1 + 1):
        for y in (cy0, cy0 + 1, cy1 - 1, cy1):
            _wall_cell(x, y)
    for y in range(cy0, cy1 + 1):
        for x in (cx0, cx0 + 1, cx1 - 1, cx1):
            _wall_cell(x, y)

    # South gatehouse cheeks (pillars beside the wide opening)
    for gx, gy in ((115, cy1), (123, cy1), (115, cy1 - 1), (123, cy1 - 1)):
        _wall_cell(gx, gy)

    # Spurs up the castle flanks (outside the 4-tile moat) to the mountain foot.
    if castle_v2.active():
        x0, y0, x1, y1 = castle_v2.footprint_tiles()
        west_x = x0 - castle_v2.MOAT_SIDE - 1
        east_x = x1 + castle_v2.MOAT_SIDE + 1
        for y in range(max(0, y0 - castle_v2.MOAT_BACK), cy0 + 1):
            for x in (west_x, west_x - 1, east_x, east_x + 1):
                if 0 <= x < WIDTH and 0 <= y < HEIGHT and grid[y][x] != WATER:
                    grid[y][x] = WALL
        # North cap between the spurs, just under the ridge (skip moat water)
        cap_y = max(0, y0 - castle_v2.MOAT_BACK - 1)
        for x in range(west_x - 1, east_x + 2):
            if 0 <= x < WIDTH and grid[cap_y][x] != WATER:
                grid[cap_y][x] = WALL


def extend_castle_gate_paving(grid):
    """Stonehaven cobble continues through the castle bridge into the plaza."""
    if not castle_v2.active():
        return
    ax0, ay = castle_v2.w(104, 55)
    ax1, _ = castle_v2.w(119, 55)
    for y in range(ay, min(HEIGHT, ay + 4)):
        for x in range(ax0, ax1 + 1):
            if 0 <= x < WIDTH and grid[y][x] in (GRASS, *TREE_TILES, PATH, STONE):
                grid[y][x] = STONE
    for px in (111, 112):
        bx, by = castle_v2.w(px, 55)
        for y in range(by, min(HEIGHT, by + 5)):
            if 0 <= bx < WIDTH and grid[y][bx] in (GRASS, *TREE_TILES, PATH, STONE, WALL):
                grid[y][bx] = PATH


def restore_city_and_void_paving(grid):
    """Put Stonehaven / Void back on their native floors (no dirt / grass).

    Wayfinder roads stamp PATH through these zones; restore STONE plazas in
    Stonehaven (and clear any grass/trees there) and crypt FLOOR in the void
    massif so village dirt never shows in either zone.
    """
    soft_city = {PATH, GRASS, *TREE_TILES}
    for y in range(HEIGHT):
        for x in range(WIDTH):
            tile = grid[y][x]
            zone = get_zone(x, y)
            if zone == "city" and tile in soft_city:
                grid[y][x] = STONE
            elif zone == "shadow_crypt" and tile == PATH:
                grid[y][x] = FLOOR
    # Mouth apron must stay walkable crypt floor (orphan trim can wipe PATH
    # before this restore if the approach was briefly disconnected).
    mx, my = VOID_MOUTH
    for dx in (-2, -1, 0, 1, 2):
        for dy in (0, 1, 2):
            ax, ay = mx + dx, my + dy
            if 0 <= ax < WIDTH and 0 <= ay < HEIGHT and grid[ay][ax] in (GRASS, PATH, FLOOR, STONE):
                grid[ay][ax] = FLOOR
    extend_castle_gate_paving(grid)
    # Re-open gate PATH after the city soft→STONE restore.
    if castle_v2.active():
        for px in (111, 112):
            bx, by = castle_v2.w(px, 55)
            for y in range(by, min(HEIGHT, by + 5)):
                if 0 <= bx < WIDTH:
                    grid[y][bx] = PATH
    cx0, cy0, cx1, cy1 = city_bounds()
    # Roads / void stamps punch the shell — lay Style B walls last, then reopen south + north.
    _stamp_stonehaven_walls(grid, cx0, cy0, cx1, cy1)
    for gx in range(116, 123):
        for gy in (cy1, cy1 - 1):
            if 0 <= gx < WIDTH and 0 <= gy < HEIGHT:
                grid[gy][gx] = PATH
    if castle_v2.active():
        ax0, _ = castle_v2.w(104, 55)
        ax1, _ = castle_v2.w(119, 55)
        for ax in range(ax0, ax1 + 1):
            for oy in (0, 1):
                ay = cy0 + oy
                if 0 <= ax < WIDTH and 0 <= ay < HEIGHT:
                    grid[ay][ax] = PATH


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
