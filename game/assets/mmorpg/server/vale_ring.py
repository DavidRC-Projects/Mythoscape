"""Crownfall Vale mountain ring (ZONES_SPEC.md section 2), shared by server and client.

A painted ring of peaks around the starter village, built from the Vale kit in
assets/vale_ring/ (keyed from the same art direction as the Wolf Pass massif).
Collision is only the band of cliff-base tiles in BANDS, minus every protected
tile (lanes and their verges, buildings, doors, NPCs, spawns, interactables),
so no existing route, quest NPC or tutorial spot is ever walled in. The
passes are the existing roads: they stay open and get a watchtower and torches.
"""
import os
import random

ASSET_DIR = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "assets", "vale_ring"))

# Inclusive tile rects of the mountain band (re-checked against the 31 Oct mirror map:
# the village is x1-96, y1-51; buildings sit 4+ tiles in from the west/east edges and
# 1 tile below the north edge, so the band hugs the map edge there and needs no moves).
BANDS = {
    "north": (1, 1, 95, 2),
    "west": (1, 1, 4, 51),
    "east_n": (91, 1, 95, 21),
    "east_m": (91, 27, 96, 37),
    "east_s": (97, 36, 102, 51),
    "east_gap": (91, 36, 98, 37),    # closes the leak between east_m and east_s (31 Oct)
    "east_edge": (96, 1, 96, 35),    # strip behind the east ridge led round to the wilderness
    "south_w": (34, 52, 50, 52),     # south rim between the South Pass and the Farm Gate
    "south_e": (67, 52, 95, 52),
    "se_east": (104, 42, 110, 50),   # rock shoulder on the SE Pass's east side     # south rim between the Farm Gate and the SE Pass
}
# Bands that ignore building margins (lanes, NPCs and spawn points still stay open).
EDGE_BANDS = {"east_gap", "east_edge", "south_w", "south_e", "se_east"}
# South rim: every plain WALL block in this rect (not a building, glade hedge or
# Stonehaven wall) is painted as mountain by the client. No new collision.
ROCK_REGION = (34, 52, 92, 68)
# ...plus the full wall between the glade hedge and the dungeon maze (the south-west rim).
ROCK_EXTRA = (44, 52, 47, 82)
# Existing dark wall blocks on the south edge get the rock art too (no new collision).
SOUTH_ROCK = (34, 53, 50, 57)
# Roads that end at the map edge run into the mountain instead (dead-end stubs only).
DEAD_END_STUBS = ((27, 1, 29, 2), (1, 23, 4, 25))

# Passes: name, banner/minimap anchor tile, lane rect kept open.
PASSES = (
    ("East Pass", (92, 24), (88, 22, 100, 26)),       # forest / Wolf Pass road (y=22-25)
    ("South Pass", (31, 53), (30, 52, 33, 57)),       # Fairy Glade road
    ("Farm Gate", (58, 53), (45, 52, 66, 55)),        # farmhouse / Mae's outfitters / mine road
    ("SE Pass", (100, 53), (96, 52, 110, 55)),        # Stonehaven road
)
# Watchtowers and torches (tile, kind). Their tiles are solid.
PROPS = (
    ("tower", 89.5, 21.6), ("torch", 90.5, 21.9), ("pillar", 90.6, 27.9),
    ("torch", 29.5, 52.8), ("torch", 34.5, 52.8),
    ("pillar", 50.6, 55.0), ("pillar", 65.5, 55.1),           # Farm Gate
    ("pillar", 100.5, 51.0), ("pillar", 112.4, 53.2), ("torch", 96.6, 52.4),   # SE Pass
)
PROP_TILES = {(89, 20), (90, 20), (89, 21), (90, 21), (90, 27)}   # the other props stand on existing WALL tiles

# Glade hedge trees on the vale's south rim that the ring's peaks replace, so the
# South Pass arch reads as a gap in the mountains. The glade interior is untouched.
GLADE_CUT = ((3, 52, 27, 53), (34, 52, 43, 57))


def glade_tree_replaced(x, y):
    return any(x0 <= x <= x1 and y0 <= y <= y1 for x0, y0, x1, y1 in GLADE_CUT)


VALE_RECT = (0, 0, 102, 52)   # banner: "inside the Vale"

_CACHE = {}


def _protected(grid, footprints, points, wm):
    h, w = len(grid), len(grid[0])
    keep = set()
    open_tiles = (wm.PATH, wm.FLOOR, wm.STONE, wm.WATER)
    for y in range(h):
        row = grid[y]
        for x in range(min(w, 112)):
            if row[x] in open_tiles:
                for dy in (-1, 0, 1):
                    for dx in (-1, 0, 1):
                        keep.add((x + dx, y + dy))
    for x0, y0, x1, y1 in footprints:
        for y in range(y0 - 2, y1 + 3):
            for x in range(x0 - 2, x1 + 3):
                keep.add((x, y))
    for (px, py) in points:
        for dy in range(-2, 3):
            for dx in range(-2, 3):
                keep.add((px + dx, py + dy))
    for _n, _a, (x0, y0, x1, y1) in PASSES:
        for y in range(y0, y1 + 1):
            for x in range(x0, x1 + 1):
                keep.add((x, y))
    return keep


def _key_points():
    pts = []
    try:
        import content
        for n in getattr(content, "NPCS", []):
            if isinstance(n, dict) and n.get("x") is not None:
                pts.append((int(n["x"]), int(n["y"])))
        for i in getattr(content, "INTERACTABLES", []):
            if isinstance(i, dict) and i.get("x") is not None:
                pts.append((int(i["x"]), int(i["y"])))
        for m in getattr(content, "MONSTER_SPAWNS", []):
            if isinstance(m, (tuple, list)) and len(m) >= 3:
                pts.append((int(m[1]), int(m[2])))
    except Exception:
        pass
    pts += [(28, 24), (25, 30), (25, 29), (24, 28), (26, 27), (32, 22)]   # spawn, grate, rats, well
    return pts


def _in_lane(x, y):
    return any(x0 <= x <= x1 and y0 <= y <= y1 for _n, _a, (x0, y0, x1, y1) in PASSES)


def cliff_tiles(grid=None, footprints=None):
    """Set of solid band tiles. Computed once from the generated grid."""
    if "cliff" in _CACHE:
        return _CACHE["cliff"]
    if grid is None:
        return set()
    import world_map as wm
    keep = _protected(grid, footprints or [], _key_points(), wm)
    keep_pts = _protected(grid, [], _key_points(), wm)
    exact = (set(_key_points()) - {(88, 52)})   # smithy door works from the wall tile; the pet door (70,52) leads only to the pet yard, which lies outside the ring
    stubs = set()
    for x0, y0, x1, y1 in DEAD_END_STUBS:
        for y in range(y0, y1 + 1):
            for x in range(x0, x1 + 1):
                stubs.add((x, y))
    out = set()
    for band, (x0, y0, x1, y1) in BANDS.items():
        for y in range(y0, y1 + 1):
            for x in range(x0, x1 + 1):
                ok_tile = grid[y][x] in (wm.GRASS, wm.WALL, *wm.TREE_TILES)
                if band in EDGE_BANDS:
                    # rim bands: old roads crossing the ring are closed too; only the
                    # exact NPC / spawn / door tiles and the pass lanes stay open
                    if (grid[y][x] in (wm.PATH,) or ok_tile) and (x, y) not in exact and not _in_lane(x, y):
                        out.add((x, y))
                    continue
                # Row 1 hugs the map edge: behind-house strips are never needed, so only
                # lanes and NPC/spawn points (not building margins) keep it open.
                edge = y == 1 and (x, y) not in keep_pts
                if (x, y) in stubs or (ok_tile and ((x, y) not in keep or edge)):
                    out.add((x, y))
    out |= PROP_TILES
    x0, y0, x1, y1 = SOUTH_ROCK
    rock = {(x, y) for y in range(y0, y1 + 1) for x in range(x0, x1 + 1) if grid[y][x] == wm.WALL}
    _CACHE["cliff"] = out
    _CACHE["rock"] = rock
    return out


def south_rock():
    return _CACHE.get("rock", set())


def apply(grid, footprints, wall_tile):
    _CACHE.clear()
    for (x, y) in cliff_tiles(grid, footprints):
        grid[y][x] = wall_tile
    return grid


def is_cliff(x, y):
    return (x, y) in _CACHE.get("cliff", ()) or (x, y) in _CACHE.get("rock", ())


def load_from_tiles(tiles):
    """Client side: rebuild the cliff set from the WORLD_STATE grid (same rule as the server)."""
    if "cliff" in _CACHE or not tiles:
        return
    import world_map as wm
    grid = [list(r) for r in tiles]
    # The server already stamped the band as WALL; rebuild from band rects + WALL.
    out = set()
    for x0, y0, x1, y1 in BANDS.values():
        for y in range(y0, y1 + 1):
            for x in range(x0, x1 + 1):
                if 0 <= y < len(grid) and 0 <= x < len(grid[0]) and grid[y][x] == wm.WALL:
                    out.add((x, y))
    out |= {t for t in PROP_TILES if grid[t[1]][t[0]] == wm.WALL}
    x0, y0, x1, y1 = SOUTH_ROCK
    _CACHE["rock"] = {(x, y) for y in range(y0, y1 + 1) for x in range(x0, x1 + 1) if grid[y][x] == wm.WALL}
    _CACHE["cliff"] = out


PEAKS = ["peak_1", "peak_2", "peak_3", "peak_4", "peak_5", "peak_6", "peak_8", "peak_9", "peak_10", "peak_5", "peak_8"]
LOW_PEAKS = ["peak_5", "peak_8", "peak_9", "peak_1", "peak_3"]
RIDGES = ["ridge_1", "ridge_2", "ridge_3", "ridge_4"]


def _pk(rng, pool=None, w=(7.5, 9.5)):
    """One varied peak: sprite, width, flip, tint index (0 neutral, 1 warm, 2 sun-bleached)."""
    return rng.choice(pool or PEAKS), rng.uniform(*w), rng.random() < 0.5, rng.randrange(3)


def placements():
    """Painted sprites: (sprite, centre_x, base_y, width_tiles, flip, tint).
    base_y = tile row edge the art stands on."""
    if "place" in _CACHE:
        return _CACHE["place"]
    rng = random.Random(4417)
    out = []

    def add(cx, by, pool=None, w=(7.5, 9.5)):
        n, wd, fl, ti = _pk(rng, pool, w)
        out.append((n, cx, by, wd, fl, ti))

    # north edge: the camera stops at row 0, so the art must fit in rows 0-3.
    # Back row of low ridges, front row of small low peaks (tops stay on screen).
    # north back row: the painted backdrop band (client, backdrop_1) replaces the ridges
    x = 0.5
    while x < 97:
        add(x + rng.uniform(-0.4, 0.4), 3.3 + rng.uniform(-0.1, 0.15), LOW_PEAKS, (4.4, 5.0))
        x += rng.uniform(3.6, 4.6)
    # west edge: chain of peaks, half beyond the map edge
    # west back row: backdrop slices (client) replace the half-off-map peaks
    for by in range(5, 54, 3):      # front row, peaks fully on the map
        add(3.4 + rng.uniform(-0.5, 0.5), by + rng.uniform(-0.3, 0.3), None, (7.0, 8.5))
    # east edge, north of the East Pass (back row first so the front row overlaps it)
    for by in range(4, 22, 3):
        add(95.4 + rng.uniform(-0.4, 0.4), by + 0.5, None, (8.0, 10.0))
    for by in range(5, 23, 3):
        add(93.0 + rng.uniform(-0.5, 0.5), min(22.0, by + rng.uniform(-0.3, 0.3)))
    # east edge, south of the pass, then stepping out east of the smithy
    for by in (30.0, 32.8, 35.6, 38.0):
        add(94.2 + rng.uniform(-0.4, 0.4), by, None, (7.5, 9.0))
    add(97.6, 38.1, LOW_PEAKS, (5.0, 6.0))            # over the closed x91-98 gap
    for by in (40.5, 43.3, 46.1, 48.9, 51.2):
        add(99.8 + rng.uniform(-0.4, 0.4), by, None, (7.5, 9.0))
    # SE Pass east shoulder
    for by in (43.5, 46.0, 48.5, 51.0):
        add(107.2 + rng.uniform(-0.5, 0.5), by, None, (7.0, 8.5))
    for by in (45.0, 47.5, 50.0):
        add(103.6 + rng.uniform(-0.3, 0.3), by + 0.6, LOW_PEAKS, (3.6, 4.6))
    # foothills: small low peaks and boulder scree in front of each chain, so the
    # ring reads as one ridge with no village grass showing between the cones
    for by in range(4, 52, 2):
        add(5.6 + rng.uniform(-0.4, 0.3), by + 0.9 + rng.uniform(-0.2, 0.2), LOW_PEAKS, (3.4, 4.4))
    for by in range(4, 22, 2):
        add(90.9 + rng.uniform(-0.3, 0.3), min(21.4, by + 0.9), LOW_PEAKS, (3.4, 4.4))
    for by in range(28, 37, 2):
        add(91.4 + rng.uniform(-0.3, 0.3), by + 0.9, LOW_PEAKS, (3.4, 4.4))
    for by in range(38, 52, 2):
        add(97.4 + rng.uniform(-0.3, 0.3), by + 0.9, LOW_PEAKS, (3.4, 4.4))
    # south rim: the client paints peaks over the rock blocks and the cut glade hedge
    # (vale_ring_client._rock_place), so nothing is listed here.
    _CACHE["place"] = out
    return out


def props():
    return PROPS


def in_vale(x, y):
    x0, y0, x1, y1 = VALE_RECT
    return x0 <= x <= x1 and y0 <= y <= y1
