"""One-time save fixes for map changes. Runs at server start, once per name.

castle_move_2026_10: the keep moved next to Wolf Pass (new moat), the harbour
was sealed so Wolf Pass is the only way in, and the Fairy Glade ring was
planted. Any saved position that is blocked or cut off from spawn moves to
the nearest reachable open tile.

massif_west_2026_10: Wolf Pass + keep slid west (SHIFT_X=-24); Stonehaven grew
east. Players standing on the old massif/keep footprint are translated with it,
then the reachability pass rescues anyone left stranded.

stonehaven_west_in_2026_10: west fort curtain + west plots slid +7 (open land
outside). Players in the reclaimed strip or old west homes move with them.
"""
from __future__ import annotations

import json
import os
import sqlite3
import time
from collections import deque

CASTLE_MOVE = "castle_move_2026_10"
MASSIF_WEST = "massif_west_2026_10"
STONEHAVEN_WEST_IN = "stonehaven_west_in_2026_10"
# West curtain slid +7; translate anyone still in the reclaimed strip / old west plots.
_WEST_IN_DX = 7
_WEST_IN_STRIP = (94, 56, 100, 132)  # old cx0 .. new_cx0-1, full city height
_WEST_IN_HOMES = (96, 60, 112, 122)  # ash + west city houses before the slide


def _reachable(grid, walkable, start):
    h, w = len(grid), len(grid[0])
    seen = {start}
    q = deque([start])
    while q:
        x, y = q.popleft()
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            nx, ny = x + dx, y + dy
            if 0 <= nx < w and 0 <= ny < h and (nx, ny) not in seen and grid[ny][nx] in walkable:
                seen.add((nx, ny))
                q.append((nx, ny))
    return seen


def safe_tile(x, y, ok, spawn, width, height):
    """Nearest tile in `ok` to (x, y), ring by ring; spawn when none within 40."""
    if (x, y) in ok:
        return x, y
    for r in range(1, 41):
        best = None
        for dy in range(-r, r + 1):
            for dx in range(-r, r + 1):
                if max(abs(dx), abs(dy)) != r:
                    continue
                c = (x + dx, y + dy)
                if 0 <= c[0] < width and 0 <= c[1] < height and c in ok:
                    d = dx * dx + dy * dy
                    if best is None or d < best[0] or (d == best[0] and c < best[1]):
                        best = (d, c)
        if best:
            return best[1]
    return spawn


def _applied(conn, name):
    conn.execute("CREATE TABLE IF NOT EXISTS map_migrations (name TEXT PRIMARY KEY, applied_at REAL, moved INTEGER)")
    return conn.execute("SELECT 1 FROM map_migrations WHERE name = ?", (name,)).fetchone() is not None


def backup(conn, db_path, tag):
    if not db_path or db_path == ":memory:":
        return None
    dest = db_path + f".pre_{tag}.bak"
    if os.path.exists(dest):
        dest = f"{db_path}.pre_{tag}.{int(time.time())}.bak"
    out = sqlite3.connect(dest)
    try:
        conn.backup(out)
    finally:
        out.close()
    return dest


def _apply_reachability(conn, grid, walkable, spawn, name, db_path, log):
    if _applied(conn, name):
        return []
    width, height = len(grid[0]), len(grid)
    ok = _reachable(grid, walkable, tuple(spawn))
    rows = conn.execute("SELECT id, x, y, dungeon_resume FROM players").fetchall()
    plan = []
    for pid, x, y, resume in rows:
        if x is not None and y is not None and (int(x), int(y)) not in ok:
            plan.append((pid, "pos", (int(x), int(y)), safe_tile(int(x), int(y), ok, tuple(spawn), width, height)))
        try:
            data = json.loads(resume) if resume else None
        except (TypeError, ValueError):
            data = None
        if isinstance(data, dict) and data.get("return_x") is not None and data.get("return_y") is not None:
            rx, ry = int(data["return_x"]), int(data["return_y"])
            if (rx, ry) not in ok:
                nx, ny = safe_tile(rx, ry, ok, tuple(spawn), width, height)
                plan.append((pid, "resume", (rx, ry), (nx, ny)))
    path = backup(conn, db_path, name)
    if path:
        log(f"[migrate] {name}: backup at {path}")
    with conn:
        for pid, what, old, new in plan:
            if what == "pos":
                conn.execute("UPDATE players SET x = ?, y = ? WHERE id = ?", (new[0], new[1], pid))
            else:
                raw = conn.execute("SELECT dungeon_resume FROM players WHERE id = ?", (pid,)).fetchone()[0]
                data = json.loads(raw)
                data["return_x"], data["return_y"] = new
                conn.execute("UPDATE players SET dungeon_resume = ? WHERE id = ?", (json.dumps(data), pid))
            log(f"[migrate] {name}: player {pid} {what} {old} -> {new}")
        conn.execute(
            "INSERT INTO map_migrations (name, applied_at, moved) VALUES (?, ?, ?)",
            (name, time.time(), len(plan)),
        )
    return plan


def _in_rect(x, y, rect):
    x0, y0, x1, y1 = rect
    return x0 <= x <= x1 and y0 <= y <= y1


def _apply_massif_west(conn, grid, walkable, spawn, db_path, log):
    """Slide anyone still standing on the pre-shift massif/keep with SHIFT_X."""
    if _applied(conn, MASSIF_WEST):
        return []
    try:
        import wolf_pass
        import castle_v2
        shift = int(wolf_pass.SHIFT_X)
    except Exception:
        shift = -24
    # Authored seats before this slide (DX=42 keep, wolf x 136–165).
    old_keep = (142, 33, 165, 56)
    old_wolf = (136, 0, 165, 28)
    width, height = len(grid[0]), len(grid)
    rows = conn.execute("SELECT id, x, y, dungeon_resume FROM players").fetchall()
    plan = []
    for pid, x, y, resume in rows:
        if x is not None and y is not None:
            ix, iy = int(x), int(y)
            if _in_rect(ix, iy, old_keep) or _in_rect(ix, iy, old_wolf):
                plan.append((pid, "pos", (ix, iy), (ix + shift, iy)))
        try:
            data = json.loads(resume) if resume else None
        except (TypeError, ValueError):
            data = None
        if isinstance(data, dict) and data.get("return_x") is not None and data.get("return_y") is not None:
            rx, ry = int(data["return_x"]), int(data["return_y"])
            if _in_rect(rx, ry, old_keep) or _in_rect(rx, ry, old_wolf):
                plan.append((pid, "resume", (rx, ry), (rx + shift, ry)))
    path = backup(conn, db_path, MASSIF_WEST)
    if path:
        log(f"[migrate] {MASSIF_WEST}: backup at {path}")
    with conn:
        for pid, what, old, new in plan:
            nx = max(0, min(width - 1, new[0]))
            ny = max(0, min(height - 1, new[1]))
            if what == "pos":
                conn.execute("UPDATE players SET x = ?, y = ? WHERE id = ?", (nx, ny, pid))
            else:
                raw = conn.execute("SELECT dungeon_resume FROM players WHERE id = ?", (pid,)).fetchone()[0]
                data = json.loads(raw)
                data["return_x"], data["return_y"] = nx, ny
                conn.execute("UPDATE players SET dungeon_resume = ? WHERE id = ?", (json.dumps(data), pid))
            log(f"[migrate] {MASSIF_WEST}: player {pid} {what} {old} -> {(nx, ny)}")
        conn.execute(
            "INSERT INTO map_migrations (name, applied_at, moved) VALUES (?, ?, ?)",
            (MASSIF_WEST, time.time(), len(plan)),
        )
    # Reachability rescue for anyone left on water/walls after the slide.
    return plan + _apply_reachability(
        conn, grid, walkable, spawn, MASSIF_WEST + "_reach", db_path, log,
    )


def _apply_stonehaven_west_in(conn, grid, walkable, spawn, db_path, log):
    """Slide players out of the +7 west-curtain reclaim / shifted west homes."""
    if _applied(conn, STONEHAVEN_WEST_IN):
        return []
    width, height = len(grid[0]), len(grid)
    rows = conn.execute("SELECT id, x, y, dungeon_resume FROM players").fetchall()
    plan = []

    def _needs(ix, iy):
        return _in_rect(ix, iy, _WEST_IN_STRIP) or _in_rect(ix, iy, _WEST_IN_HOMES)

    for pid, x, y, resume in rows:
        if x is not None and y is not None:
            ix, iy = int(x), int(y)
            if _needs(ix, iy):
                plan.append((pid, "pos", (ix, iy), (ix + _WEST_IN_DX, iy)))
        try:
            data = json.loads(resume) if resume else None
        except (TypeError, ValueError):
            data = None
        if isinstance(data, dict) and data.get("return_x") is not None and data.get("return_y") is not None:
            rx, ry = int(data["return_x"]), int(data["return_y"])
            if _needs(rx, ry):
                plan.append((pid, "resume", (rx, ry), (rx + _WEST_IN_DX, ry)))
    path = backup(conn, db_path, STONEHAVEN_WEST_IN)
    if path:
        log(f"[migrate] {STONEHAVEN_WEST_IN}: backup at {path}")
    with conn:
        for pid, what, old, new in plan:
            nx = max(0, min(width - 1, new[0]))
            ny = max(0, min(height - 1, new[1]))
            if what == "pos":
                conn.execute("UPDATE players SET x = ?, y = ? WHERE id = ?", (nx, ny, pid))
            else:
                raw = conn.execute("SELECT dungeon_resume FROM players WHERE id = ?", (pid,)).fetchone()[0]
                data = json.loads(raw)
                data["return_x"], data["return_y"] = nx, ny
                conn.execute("UPDATE players SET dungeon_resume = ? WHERE id = ?", (json.dumps(data), pid))
            log(f"[migrate] {STONEHAVEN_WEST_IN}: player {pid} {what} {old} -> {(nx, ny)}")
        conn.execute(
            "INSERT INTO map_migrations (name, applied_at, moved) VALUES (?, ?, ?)",
            (STONEHAVEN_WEST_IN, time.time(), len(plan)),
        )
    return plan + _apply_reachability(
        conn, grid, walkable, spawn, STONEHAVEN_WEST_IN + "_reach", db_path, log,
    )


def run_once(conn, grid, walkable, spawn, db_path=None, log=print):
    """Returns a list of (player_id, what, old, new). Empty when already applied."""
    moved = []
    moved.extend(_apply_reachability(conn, grid, walkable, spawn, CASTLE_MOVE, db_path, log))
    moved.extend(_apply_massif_west(conn, grid, walkable, spawn, db_path, log))
    moved.extend(_apply_stonehaven_west_in(conn, grid, walkable, spawn, db_path, log))
    return moved
