#!/usr/bin/env python3
"""Audit overworld PATH connectivity (spawn, harbour, void, doors).

Run from repo root or mmorpg/:
  python tools/path_audit.py
"""
from __future__ import annotations

import os
import sys
from collections import deque

_ROOT = os.path.normpath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(_ROOT, "server"))

import world_map as wm  # noqa: E402
import explore_dungeons  # noqa: E402
import content  # noqa: E402


LANDMARKS = {
    "spawn": wm.SPAWN_POINT,
    "harbour": (176, 18),
    "void_door": (171, 108),
    "bank_apron": (44, 34),
    "city_square": (118, 74),
    "wolf_pass": (121, 16),  # after wolf_pass.SHIFT_X
}


def _grid():
    g = wm.generate_world()
    explore_dungeons.capture_and_hide(g)
    try:
        wm.stamp_outfitters_shell(g)
    except Exception:
        pass
    return g


def _path_ok(t):
    return t == wm.PATH


def bfs_path(grid, start, goals):
    goals = {tuple(g) for g in goals}
    h = len(grid)
    w = len(grid[0]) if h else 0
    sx, sy = start
    if not (0 <= sy < h and 0 <= sx < w):
        return False
    if not _path_ok(grid[sy][sx]):
        # step onto a neighbouring PATH
        found = None
        for dx, dy in ((0, 0), (1, 0), (-1, 0), (0, 1), (0, -1), (1, 1), (-1, 1)):
            nx, ny = sx + dx, sy + dy
            if 0 <= ny < h and 0 <= nx < w and _path_ok(grid[ny][nx]):
                found = (nx, ny)
                break
        if found is None:
            return False
        sx, sy = found
    q = deque([(sx, sy)])
    seen = {(sx, sy)}
    while q:
        x, y = q.popleft()
        if (x, y) in goals or any(max(abs(x - gx), abs(y - gy)) <= 1 for gx, gy in goals):
            return True
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            nx, ny = x + dx, y + dy
            if (nx, ny) in seen:
                continue
            if 0 <= ny < h and 0 <= nx < w and _path_ok(grid[ny][nx]):
                seen.add((nx, ny))
                q.append((nx, ny))
    return False


def components(grid):
    h = len(grid)
    w = len(grid[0]) if h else 0
    seen = set()
    comps = []
    for y in range(h):
        for x in range(w):
            if (x, y) in seen or not _path_ok(grid[y][x]):
                continue
            q = deque([(x, y)])
            seen.add((x, y))
            cells = []
            while q:
                cx, cy = q.popleft()
                cells.append((cx, cy))
                for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                    nx, ny = cx + dx, cy + dy
                    if (nx, ny) in seen:
                        continue
                    if 0 <= ny < h and 0 <= nx < w and _path_ok(grid[ny][nx]):
                        seen.add((nx, ny))
                        q.append((nx, ny))
            comps.append(cells)
    comps.sort(key=len, reverse=True)
    return comps


def door_gaps(grid):
    """Exterior doors with no PATH in a 2-tile south apron, or not on spawn PATH."""
    h = len(grid)
    w = len(grid[0]) if h else 0
    missing_local = []
    missing_net = []
    spawn = LANDMARKS["spawn"]
    for spot in content.INTERACTABLES:
        if spot.get("kind") != "door" and not (
            spot.get("kind") == "dungeon_entrance" and spot.get("dungeon_id")
        ):
            continue
        if spot.get("plane"):
            continue
        x, y = int(spot["x"]), int(spot["y"])
        near = False
        for dy in range(0, 3):
            for dx in range(-1, 2):
                nx, ny = x + dx, y + dy
                if not (0 <= ny < h and 0 <= nx < w):
                    continue
                # City plazas use STONE; dirt roads use PATH — either is fine.
                if grid[ny][nx] in (wm.PATH, wm.STONE, wm.FLOOR):
                    near = True
        if not near:
            missing_local.append(spot.get("id") or f"{x},{y}")
            continue
        # Network check: PATH or STONE walk to spawn PATH component.
        if not bfs_path(grid, spawn, [(x, y), (x, y + 1)]):
            if not any(
                0 <= y + dy < h and 0 <= x + dx < w
                and grid[y + dy][x + dx] in (wm.PATH, wm.STONE)
                for dy in range(0, 3) for dx in range(-1, 2)
            ):
                missing_net.append(spot.get("id") or f"{x},{y}")
    return missing_local, missing_net


def orphan_count(grid):
    """PATH cells outside fairy/glade not reachable from spawn on PATH."""
    import fairy_glade

    comps = components(grid)
    if not comps:
        return 0
    main = set(comps[0])
    # ensure spawn's component is main
    sx, sy = LANDMARKS["spawn"]
    for c in comps:
        if (sx, sy) in c or any(abs(x - sx) + abs(y - sy) <= 2 for x, y in c):
            main = set(c)
            break
    fx0, fy0, fx1, fy1 = wm.ZONES["fairy_village"]
    lane = fairy_glade.lane_cells()
    n = 0
    h = len(grid)
    w = len(grid[0]) if h else 0
    for y in range(h):
        for x in range(w):
            if not _path_ok(grid[y][x]):
                continue
            if (x, y) in main:
                continue
            if (x, y) in lane:
                continue
            if fx0 <= x <= fx1 and fy0 <= y <= fy1:
                continue
            n += 1
    return n


def main():
    grid = _grid()
    comps = components(grid)
    print(f"PATH components: {len(comps)} sizes={ [len(c) for c in comps[:12]] }")
    for name, pos in LANDMARKS.items():
        ok = bfs_path(grid, LANDMARKS["spawn"], [pos])
        print(f"  PATH spawn -> {name} {pos}: {'PASS' if ok else 'FAIL'}")
    hv = bfs_path(grid, LANDMARKS["harbour"], [LANDMARKS["void_door"]])
    print(f"  PATH harbour -> void: {'PASS' if hv else 'FAIL'}")
    local, net = door_gaps(grid)
    print(f"doors missing local PATH: {len(local)} {local[:12]}")
    print(f"doors not on spawn PATH net: {len(net)} {net[:12]}")
    orphans = orphan_count(grid)
    print(f"orphan PATH outside fairy: {orphans}")
    fails = []
    if not bfs_path(grid, LANDMARKS["spawn"], [LANDMARKS["harbour"]]):
        fails.append("spawn-harbour")
    if not bfs_path(grid, LANDMARKS["spawn"], [LANDMARKS["void_door"]]):
        fails.append("spawn-void")
    if not hv:
        fails.append("harbour-void")
    if orphans:
        fails.append(f"orphans={orphans}")
    if fails:
        print("AUDIT FAIL:", ", ".join(fails))
        return 1
    print("AUDIT PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
