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
    "mine":    (1, 56, 40, 88),
    "dungeon": (44, 54, 90, 143),
    "city":    (98, 56, 148, 96),
    "volcano": (154, 58, 190, 94),
    "shadow_crypt": (154, 98, 190, 140),
}

SPAWN_POINT = (28, 24)  # village crossroads

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
        (64, 29), (86, 19), (85, 49),
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
    # mine <-> dungeon link — large, obvious mouth
    _rect(grid, 36, 66, 48, 76, FLOOR)
    for y in range(68, 75):
        for x in (mix1 - 1, mix1, mix1 + 1):
            if mix0 <= x <= mix1 + 2:
                grid[y][x] = FLOOR
    for px, py in ((37, 66), (46, 66), (37, 76), (46, 76), (36, 70), (36, 74), (47, 70), (47, 74)):
        if 0 <= px < WIDTH and 0 <= py < HEIGHT:
            grid[py][px] = WALL
    # PATH apron west of the dungeon mouth (from village/mine approach)
    _rect(grid, 28, 68, 36, 74, PATH)
    for y in range(68, 75):
        grid[y][36] = FLOOR

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
    cx0, cy0, cx1, cy1 = ZONES["city"]
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

    # --- Emberdeep volcano (east of Stonehaven) — conical massif + crater mouth ---
    vx0, vy0, vx1, vy1 = ZONES["volcano"]
    # Scorched foothills (ash grass)
    for y in range(vy0, vy1 + 1):
        for x in range(vx0, vx1 + 1):
            if grid[y][x] in (GRASS, *TREE_TILES):
                grid[y][x] = GRASS
    # Concentric basalt rings → reads as a rising cone
    rings = [
        (154, 58, 176, 80),  # outer foothills
        (156, 60, 174, 78),
        (158, 62, 172, 76),
        (160, 64, 170, 74),
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
    _rect(grid, 161, 65, 169, 71, WALL)
    _rect(grid, 162, 66, 168, 70, FLOOR)
    # Magma glow pit in crater center (blocked lava tile)
    grid[68][164] = WATER
    grid[68][165] = WATER
    grid[69][164] = WATER
    # Mouth tunnel opening south through the rings
    for y in range(70, 74):
        for x in range(163, 166):
            grid[y][x] = FLOOR
    # Apron / landing in front of the mouth
    _rect(grid, 160, 73, 169, 77, PATH)
    grid[72][164] = PATH  # old mouth; lair entrance moved south of the crater
    # Jagged outer peaks
    for _ in range(55):
        x = rng.randint(152, 178)
        y = rng.randint(57, 81)
        # Keep mouth corridor clear
        if 162 <= x <= 166 and 70 <= y <= 74:
            continue
        if abs(x - 164) + abs(y - 68) < 5:
            continue
        if grid[y][x] in (GRASS, PATH):
            grid[y][x] = WALL
    # Road from Stonehaven east gate into the crater mouth
    for x in range(148, 162):
        for y in (72, 73, 74):
            if 0 <= x < WIDTH and grid[y][x] in (GRASS, *TREE_TILES, PATH, WALL, STONE):
                if x == 148 and grid[y][x] == WALL:
                    grid[y][x] = PATH
                elif x > 148:
                    grid[y][x] = PATH
    for y in (72, 73, 74):
        grid[y][148] = PATH  # east city gate
    # Dragon-lair mouth south of the crater, with a walk-in pad.
    _rect(grid, 158, 80, 172, 90, PATH)
    for y in range(78, 85):
        grid[y][164] = PATH
    for dx in (-1, 0, 1):
        grid[84][164 + dx] = PATH
        grid[83][164 + dx] = PATH
    grid[84][164] = FLOOR

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
    # Road from Stonehaven south gate east, then south to the sanctum
    for x in range(118, 172):
        for yy in (cy1 + 1, cy1 + 2):
            if 0 <= yy < HEIGHT and grid[yy][x] in (GRASS, PATH, STONE, WALL):
                # Don't erase city wall except the existing south gate tiles
                if yy == cy1:
                    continue
                grid[yy][x] = PATH
    for y in range(cy1 + 1, 110):
        for x in (170, 171, 172):
            if grid[y][x] in (GRASS, PATH, WALL) and not (166 < x < 176 and 102 < y < 108):
                grid[y][x] = PATH
    grid[108][171] = PATH

    castle_v2.apply_stamp(grid, sys.modules[__name__])
    _clear_trees_near_buildings(grid)
    return grid


# Building footprints — keep in sync with content.BUILDINGS (avoid import cycle)
_BUILDING_FOOTPRINTS = [
    # village
    (4, 4, 15, 15), (40, 4, 51, 15), (4, 36, 15, 47), (40, 36, 51, 47),
    (58, 18, 70, 28), (78, 4, 94, 18), (78, 36, 92, 48),
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
    (158, 78, 172, 90),
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
    if castle_v2.counts_as_city(x, y):
        return "city"
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
