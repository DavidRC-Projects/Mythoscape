"""Stonehaven castle v2 layout.

The pack was authored for an older map (footprint x 100–123, y 31–54).
This world keeps the keep on the live city plaza, so every pack coordinate
is shifted by (DX, DY) = (+18, +16), landing on x 118–141, y 47–70.
"""
import json
import os

import feature_flags

# pack (100, 31) -> world (118, 47)
DX, DY = 18, 16

_JSON = os.path.join(
    os.path.dirname(__file__),
    "..", "client", "assets", "buildings", "castle_v2", "castle_v2.json",
)
_META = None
_TRIED = False


def meta():
    global _META, _TRIED
    if _TRIED:
        return _META
    _TRIED = True
    try:
        with open(_JSON, encoding="utf-8") as f:
            _META = json.load(f)
    except OSError:
        _META = None
    return _META


def active():
    return bool(feature_flags.USE_NEW_CASTLE and meta())


def w(px, py):
    return int(px) + DX, int(py) + DY


def footprint_tiles():
    """24×24 moat footprint in world tiles: (x0, y0, x1, y1)."""
    fp = meta()["footprint"]
    x0, y0 = w(fp["x0"], fp["y0"])
    x1, y1 = w(fp["x1"], fp["y1"])
    return x0, y0, x1, y1


def tree_footprint():
    """Footprint plus the south apron row, for tree clearing."""
    x0, y0, x1, y1 = footprint_tiles()
    return x0, y0, x1, y1 + 1


def counts_as_city(x, y):
    if not active():
        return False
    x0, y0, x1, y1 = tree_footprint()
    return x0 <= x <= x1 and y0 <= y <= y1


_CELL_CACHE = {}


def _cells(codes):
    if codes in _CELL_CACHE:
        return _CELL_CACHE[codes]
    rows = meta()["walkability"]["rows"]
    origin_x, origin_y = meta()["walkability"]["origin"]
    out = set()
    for ly, row in enumerate(rows):
        for lx, c in enumerate(row):
            if c in codes:
                out.add(w(origin_x + lx, origin_y + ly))
    _CELL_CACHE[codes] = out
    return out


def bailey_tiles():
    """Inner floor and gate passage (hidden by the shell when outside)."""
    return _cells("FP")


def wall_walk_tiles():
    return _cells("A")


def trigger_tiles():
    tiles = set()
    for group in meta()["trigger_tiles"].values():
        if not isinstance(group, list):
            continue
        for item in group:
            if isinstance(item, (list, tuple)) and len(item) == 2:
                tiles.add(w(item[0], item[1]))
    return tiles


def apply_stamp(grid, wm):
    """Overwrite the castle block. Caller has already stamped the old keep."""
    if not active():
        return grid
    code_to_tile = {
        "M": wm.WATER, "W": wm.WALL, "K": wm.WALL, "F": wm.FLOOR, "A": wm.FLOOR,
        "P": wm.FLOOR, "B": wm.PATH, "G": wm.PATH,
    }
    rows = meta()["walkability"]["rows"]
    ox, oy = meta()["walkability"]["origin"]
    x0, y0 = w(ox, oy)
    for ly, row in enumerate(rows):
        for lx, c in enumerate(row):
            grid[y0 + ly][x0 + lx] = code_to_tile[c]
    # Apron in front of the bridge (pack y 55, x 104–119) and the street join.
    ax0, ay = w(104, 55)
    ax1, _ = w(119, 55)
    for x in range(ax0, ax1 + 1):
        grid[ay][x] = wm.STONE
    for px in (111, 112):
        bx, by = w(px, 55)
        grid[by][bx] = wm.PATH
        grid[by + 1][bx] = wm.PATH
    return grid


def old_castle_footprint():
    return (118, 58, 136, 70)
