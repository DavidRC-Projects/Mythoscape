"""castle_map_patch.py - reference implementation + checker for the v2 castle tile stamp.

The function apply_new_castle(grid, wm) is what Cursor ports into server/world_map.py
generate_world() (behind USE_NEW_CASTLE, AFTER the city block + forest belt, BEFORE
_clear_trees_near_buildings). It reads the 24x24 walkability rows from sprites/castle_v2.json.

Run the checker against a Mythoscape checkout (read-only, it never writes to the repo):
    python tools/castle_map_patch.py --repo /path/to/Mythoscape
It generates the world with the current code, applies the stamp, and verifies:
  * every old castle interior spot shifted by (+3,-2) is walkable, doors/enter/exit tiles are walkable,
  * NPC spots are walkable, Herald Rowan is reachable (4-neighbour moves, like handle_move),
  * the courtyard is reachable from the spawn point only through the gate,
  * outside the castle footprint the set of reachable tiles is unchanged except for tiles the castle
    now covers (no new leaks through the city wall or the mountain rock),
  * the mountain pass is not newly connected to the city.
"""
import json
import os
import sys
from collections import deque

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
META = json.load(open(os.path.join(ROOT, "sprites", "castle_v2.json")))
FP = META["footprint"]
X0, Y0 = FP["x0"], FP["y0"]


def apply_new_castle(grid, wm):
    code_to_tile = {"M": wm.WATER, "W": wm.WALL, "K": wm.WALL, "F": wm.FLOOR, "A": wm.FLOOR,
                    "P": wm.FLOOR, "B": wm.PATH, "G": wm.PATH}
    for ly, row in enumerate(META["walkability"]["rows"]):
        for lx, c in enumerate(row):
            grid[Y0 + ly][X0 + lx] = code_to_tile[c]
    # apron in front of the bridge (row 55) + path onto the main street
    for x in range(104, 120):
        grid[55][x] = wm.STONE
    for x in (111, 112):
        grid[55][x] = wm.PATH
        grid[56][x] = wm.PATH
    return grid


def bfs(grid, wm, start, block=frozenset()):
    H, W = len(grid), len(grid[0])
    seen = {start}
    q = deque([start])
    while q:
        x, y = q.popleft()
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            nx, ny = x + dx, y + dy
            if 0 <= nx < W and 0 <= ny < H and (nx, ny) not in seen and (nx, ny) not in block \
                    and grid[ny][nx] in wm.WALKABLE_TILES:
                seen.add((nx, ny))
                q.append((nx, ny))
    return seen


def main():
    repo = sys.argv[sys.argv.index("--repo") + 1] if "--repo" in sys.argv else None
    if not repo:
        raise SystemExit("usage: castle_map_patch.py --repo /path/to/Mythoscape")
    sys.path.insert(0, os.path.join(repo, "game", "assets", "mmorpg", "server"))
    import world_map as wm
    old = wm.generate_world()
    new = [row[:] for row in old]
    apply_new_castle(new, wm)
    inside = lambda x, y: X0 <= x <= FP["x1"] and Y0 <= y <= FP["y1"]
    ok = True

    def check(cond, msg):
        nonlocal ok
        print(("PASS " if cond else "FAIL ") + msg)
        ok &= bool(cond)

    spawn = wm.SPAWN_POINT
    r_old, r_new = bfs(old, wm, spawn), bfs(new, wm, spawn)
    check((111, 55) in r_new, "apron (111,55) reachable from spawn")
    check((111, 48) in r_new, "courtyard (111,48) reachable from spawn")
    gate_block = {(111, 52), (112, 52)}
    r_gate_closed = bfs(new, wm, spawn, block=gate_block)
    check(not any(inside(x, y) and new[y][x] == wm.FLOOR for (x, y) in r_gate_closed),
          "courtyard only reachable through the gate tiles (111,52)/(112,52)")
    for k, (x, y) in META["interior_shift"]["spots_new"].items():
        check(new[y][x] in wm.WALKABLE_TILES, f"interior spot {k} -> ({x},{y}) walkable")
    for d, v in META["doors"].items():
        for (x, y) in ([v["x"], v["y"]], v["enter"], v["exit"]):
            check((x, y) in r_new, f"door {d} tile ({x},{y}) reachable")
    for s in META["npc_spots"]:
        x, y = s["new"]
        if s["kind"].startswith(("npc", "monster")):
            check((x, y) in r_new, f"spot {s['id']} ({x},{y}) reachable")
    hr = [(107 + dx, 51 + dy) for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1))]
    check(any(p in r_new for p in hr), "Herald Rowan (107,51) has a reachable neighbour for talking")
    for t in META["trigger_tiles"]["outer"] + META["trigger_tiles"]["inner"]:
        check(tuple(t) in r_new, f"trigger tile {tuple(t)} reachable")
    lost = {p for p in r_old if not inside(*p)} - r_new
    gained = {p for p in r_new if not inside(*p)} - r_old
    check(not gained - {(x, 55) for x in range(104, 120)}, f"no new reachable tiles outside the castle (gained {sorted(gained)[:8]})")
    check(not lost, f"no tiles outside the castle became unreachable (lost {sorted(lost)[:8]})")
    pass_tile = (112, 16)
    check((pass_tile in r_old) == (pass_tile in r_new), "mountain pass connectivity unchanged")
    covered = [(x, y) for y in range(Y0, FP["y1"] + 1) for x in range(X0, FP["x1"] + 1)]
    kinds = {}
    for (x, y) in covered:
        kinds[old[y][x]] = kinds.get(old[y][x], 0) + 1
    names = {getattr(wm, n): n for n in ("GRASS", "TREE", "WATER", "WALL", "PATH", "FLOOR", "STONE", "OAK_TREE",
                                          "MAPLE_TREE", "YEW_TREE", "MAGIC_TREE", "WILLOW_TREE")}
    print("tiles the new footprint replaces:", {names.get(k, k): v for k, v in kinds.items()})
    print("RESULT:", "ALL PASS" if ok else "FAILURES")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
