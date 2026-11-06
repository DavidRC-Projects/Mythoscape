"""A click on the painted tree chops it, and you cannot walk through the art."""
import os
import sys
from collections import deque

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, ".."))
sys.path.insert(0, os.path.join(ROOT, "server"))
sys.path.insert(0, os.path.join(ROOT, "client"))

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import tree_cover
import world_map as wm


_GRID = None


def grid():
    global _GRID
    if _GRID is None:
        _GRID = wm.generate_world()
    return _GRID


def trees():
    found = []
    for y, row in enumerate(grid()):
        for x, tile in enumerate(row):
            name = tree_cover._TILE_NAME.get(tile)
            if name:
                found.append((x, y, name))
    return found


def reachable():
    g = grid()
    start = wm.SPAWN_POINT
    seen = set()
    if not wm.is_walkable(g, *start):
        raise AssertionError(f"spawn {start} is not walkable")
    q = deque([start])
    seen.add(start)
    while q:
        x, y = q.popleft()
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            nx, ny = x + dx, y + dy
            if (nx, ny) in seen or not wm.is_walkable(g, nx, ny):
                continue
            seen.add((nx, ny))
            q.append((nx, ny))
    return seen


def test_trees_block_their_art_and_can_be_chopped():
    g = grid()
    woods = trees()
    assert len(woods) >= 8, len(woods)
    open_tiles = reachable()
    missed = []
    sealed = []
    walked_through = []
    for x, y, name in woods:
        # The tile in front stays open when this tree's own art does not cover it
        # and nothing else paints it. Every tree still needs a reachable stand.
        stands = [
            (nx, ny)
            for dy in range(-8, 3)
            for dx in range(-5, 6)
            if (nx := x + dx, ny := y + dy)
            and wm.is_walkable(g, nx, ny)
            and tree_cover.beside(name, x, y, nx, ny)
            and (nx, ny) in open_tiles
        ]
        if not stands:
            sealed.append((x, y, name))
        # Clicking the canopy, including a side the old ±1 search missed.
        hit = None
        for dx, dy in tree_cover.mask(name, x, y):
            if abs(dx) >= 2 and dy <= -2 and g[y + dy][x + dx] == wm.GRASS:
                hit = tree_cover.trunk_at([(x, y, name)], x + dx, y + dy)
                if hit != (x, y):
                    missed.append((x, y, name, dx, dy, hit))
                if wm.is_walkable(g, x + dx, y + dy):
                    walked_through.append((x, y, name, dx, dy))
                break
        # Directly north of the trunk is canopy for every painted tree.
        if tree_cover.covers(name, x, y, x, y - 1) and g[y - 1][x] == wm.GRASS:
            if wm.is_walkable(g, x, y - 1):
                walked_through.append((x, y, name, 0, -1))
    assert not sealed, sealed
    assert not missed, missed
    assert not walked_through, walked_through
    for y, row in enumerate(g):
        for x, tile in enumerate(row):
            if tile == wm.PATH:
                assert wm.is_walkable(g, x, y), (x, y)


def test_client_click_matches_server():
    import client as client_mod
    g = grid()
    woods = trees()
    nodes = {f"{x},{y}": name for x, y, name in woods}

    class Stub:
        tiles = g
        world_w = len(g[0])
        resources = nodes

        def _tree_blocks_building(self, x, y):
            return False

    stub = Stub()
    stub.tile_walkable = lambda x, y: client_mod.GameClient.tile_walkable(stub, x, y)
    stub._grass_under_trees = lambda: client_mod.GameClient._grass_under_trees(stub)
    # A wide canopy click used to walk onto the grass instead of chopping.
    chosen = None
    for x, y, name in woods:
        for dx, dy in tree_cover.mask(name, x, y):
            if abs(dx) >= 2 and dy <= -2:
                chosen = (x, y, name, x + dx, y + dy)
                break
        if chosen:
            break
    assert chosen, "no wide canopy tile"
    tx, ty, name, cx, cy = chosen
    assert client_mod.GameClient.resolve_gather_click(stub, cx, cy) == (tx, ty)
    assert client_mod.GameClient.tile_walkable(stub, cx, cy) is False
    assert wm.is_walkable(g, cx, cy) is False
    goals = client_mod.GameClient.tree_chop_goals(stub, tx, ty, name)
    assert goals, (tx, ty, name)
    assert any(tree_cover.beside(name, tx, ty, sx, sy) for sx, sy in goals)
    # Far from the sprite, the server still refuses the chop.
    assert tree_cover.beside(name, tx, ty, 28, 24) is False


if __name__ == "__main__":
    test_trees_block_their_art_and_can_be_chopped()
    test_client_click_matches_server()
    print("tree cover ok", len(trees()))
