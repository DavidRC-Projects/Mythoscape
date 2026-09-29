"""Unique house layouts from the buildings pack.

The pack was authored for an older map. Each house is shifted so its door
tile stays on the live door. The footprint follows the art, growing where
the pack is larger than today's shell.
"""
import json
import os

import feature_flags

# Pack door -> live door. (dx, dy) added to every pack coordinate.
_SHIFT = {
    "cottage_nw": (2, 4),       # (7, 11) -> (9, 15)
    "cottage_ne": (18, 4),      # (27, 11) -> (45, 15)
    "cottage_sw": (2, 15),      # (7, 32) -> (9, 47)
    "cottage_se": (18, 15),     # (27, 32) -> (45, 47)
    "bank": (26, 8),            # (38, 20) -> (64, 28)
    "pet_emporium": (30, 16),   # (55, 32) -> (85, 48)
    "harbour_tackle": (39, 0),  # (138, 14) -> (177, 14)
    "harbour_fishmonger": (39, 0),  # (138, 28) -> (177, 28)
    # Spread below the castle. Doors face south onto the new streets.
    "city_house_nw": (19, 44),  # (86, 52) -> (105, 96)
    "city_house_sw": (20, 56),  # (86, 66) -> (106, 122)
    "city_barracks": (26, 28),  # (114, 68) -> (140, 96)
    # Authored on the live smithy. No shift, and the stamp is left alone.
    "smithy": (0, 0),
}

_KEY = {
    "cottage_nw": "elders_hall",
    "cottage_ne": "general_store",
    "cottage_sw": "resting_ox",
    "cottage_se": "farmhouse",
    "bank": "village_bank",
    "pet_emporium": "pet_emporium",
    "harbour_tackle": "harbour_tackle",
    "harbour_fishmonger": "kais_catch",
    "city_house_nw": "stonehaven_cottage",
    "city_house_sw": "stonehaven_house",
    "city_barracks": "city_barracks",
    "smithy": "smithy",
}

# Shell stamped by world_map before this module runs.
_OLD_SHELL = {
    "cottage_nw": (4, 4, 15, 15),
    "cottage_ne": (40, 4, 51, 15),
    "cottage_sw": (4, 36, 15, 47),
    "cottage_se": (40, 36, 51, 47),
    "bank": (58, 18, 70, 28),
    "pet_emporium": (78, 36, 92, 48),
    "harbour_tackle": (172, 6, 182, 14),
    "harbour_fishmonger": (172, 20, 182, 28),
    "city_house_nw": (102, 60, 110, 68),
    "city_house_sw": (102, 74, 110, 82),
    "city_barracks": (130, 74, 138, 84),
}

_DIR = os.path.join(
    os.path.dirname(__file__),
    "..", "client", "assets", "buildings", "v2",
)
_META = {}
_TRIED = set()
_CELL_CACHE = {}


def _load(building_id):
    if building_id in _TRIED:
        return _META.get(building_id)
    _TRIED.add(building_id)
    key = _KEY.get(building_id)
    if not key:
        return None
    path = os.path.join(_DIR, key + ".json")
    try:
        with open(path, encoding="utf-8") as f:
            _META[building_id] = json.load(f)
    except OSError:
        _META[building_id] = None
    return _META.get(building_id)


def enabled(building_id):
    if not feature_flags.USE_NEW_BUILDINGS:
        return False
    if building_id not in feature_flags.NEW_BUILDINGS_ENABLED:
        return False
    return _load(building_id) is not None


def meta(building_id):
    return _load(building_id)


def w(building_id, px, py):
    dx, dy = _SHIFT[building_id]
    return int(px) + dx, int(py) + dy


def old_shell(building_id):
    return _OLD_SHELL[building_id]


def footprint(building_id):
    fp = meta(building_id)["footprint"]
    x0, y0 = w(building_id, fp["x0"], fp["y0"])
    x1, y1 = w(building_id, fp["x1"], fp["y1"])
    return x0, y0, x1, y1


def floor_rect(building_id):
    fl = meta(building_id)["floor"]
    x0, y0 = w(building_id, fl["floor_x0"], fl["floor_y0"])
    x1, y1 = w(building_id, fl["floor_x1"], fl["floor_y1"])
    return x0, y0, x1, y1


def doorway_tiles(building_id):
    door = meta(building_id)["door"]
    return {w(building_id, x, y) for x, y in door["doorway_path_tiles"]}


def _cells(building_id, codes):
    key = (building_id, codes)
    if key in _CELL_CACHE:
        return _CELL_CACHE[key]
    info = meta(building_id)
    rows = info["walkability"]["rows"]
    origin_x, origin_y = info["walkability"]["origin"]
    out = set()
    for ly, row in enumerate(rows):
        for lx, cell in enumerate(row):
            if cell in codes:
                out.add(w(building_id, origin_x + lx, origin_y + ly))
    _CELL_CACHE[key] = out
    return out


def floor_cells(building_id):
    return _cells(building_id, "F")


def footprint_cells(building_id):
    return _cells(building_id, "WFDP")


def apply_stamp(grid, wm):
    """Replace each enabled house. The old shell has already been stamped."""
    code_to_tile = {
        "W": wm.WALL,
        "F": wm.FLOOR,
        "D": wm.PATH,
        "P": wm.WALL,
    }
    for building_id in list(feature_flags.NEW_BUILDINGS_ENABLED):
        if not enabled(building_id):
            continue
        info = meta(building_id)
        if info.get("footprint_unchanged"):
            continue
        x0, y0, x1, y1 = footprint(building_id)
        ox0, oy0, ox1, oy1 = _OLD_SHELL[building_id]
        # City houses leave the stone plaza. Village houses leave grass.
        release = wm.STONE if building_id.startswith("city_") else wm.GRASS
        clearing = (wm.WALL, wm.FLOOR, wm.PATH) if release == wm.STONE else (wm.WALL, wm.FLOOR)
        for y in range(oy0, oy1 + 1):
            for x in range(ox0, ox1 + 1):
                if x0 <= x <= x1 and y0 <= y <= y1:
                    continue
                if grid[y][x] in clearing:
                    grid[y][x] = release
        rows = info["walkability"]["rows"]
        origin_x, origin_y = info["walkability"]["origin"]
        for ly, row in enumerate(rows):
            for lx, cell in enumerate(row):
                wx, wy = w(building_id, origin_x + lx, origin_y + ly)
                grid[wy][wx] = code_to_tile[cell]
        door = info["door"]
        ax, ay = w(building_id, door["x"], door["y"] + 1)
        if 0 <= ay < len(grid) and 0 <= ax < len(grid[0]) and grid[ay][ax] != wm.WALL:
            grid[ay][ax] = wm.PATH
