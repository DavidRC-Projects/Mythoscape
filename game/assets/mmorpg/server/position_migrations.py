"""One-time save fixes for map changes. Runs at server start, once per name.

castle_move_2026_10: the keep moved next to Wolf Pass (new moat), the harbour
was sealed so Wolf Pass is the only way in, and the Fairy Glade ring was
planted. Any saved position (players.x/y, or a dungeon resume's return tile)
that is now blocked, or in a pocket cut off from the spawn, moves to the
nearest reachable open tile (spawn point if none). The database is copied to
world.db.pre_castle_move.bak first. Recorded in table map_migrations so it
never runs twice.
"""
from __future__ import annotations

import json
import os
import sqlite3
import time
from collections import deque

NAME = "castle_move_2026_10"


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


def _applied(conn):
    conn.execute("CREATE TABLE IF NOT EXISTS map_migrations (name TEXT PRIMARY KEY, applied_at REAL, moved INTEGER)")
    return conn.execute("SELECT 1 FROM map_migrations WHERE name = ?", (NAME,)).fetchone() is not None


def backup(conn, db_path):
    if not db_path or db_path == ":memory:":
        return None
    dest = db_path + ".pre_castle_move.bak"
    if os.path.exists(dest):
        dest = f"{db_path}.pre_castle_move.{int(time.time())}.bak"
    out = sqlite3.connect(dest)
    try:
        conn.backup(out)
    finally:
        out.close()
    return dest


def run_once(conn, grid, walkable, spawn, db_path=None, log=print):
    """Returns a list of (player_id, what, old, new). Empty when already applied."""
    if _applied(conn):
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
    path = backup(conn, db_path)
    if path:
        log(f"[migrate] {NAME}: backup at {path}")
    with conn:
        for pid, what, old, new in plan:
            if what == "pos":
                conn.execute("UPDATE players SET x = ?, y = ? WHERE id = ?", (new[0], new[1], pid))
            else:
                raw = conn.execute("SELECT dungeon_resume FROM players WHERE id = ?", (pid,)).fetchone()[0]
                data = json.loads(raw)
                data["return_x"], data["return_y"] = new
                conn.execute("UPDATE players SET dungeon_resume = ? WHERE id = ?", (json.dumps(data), pid))
            log(f"[migrate] {NAME}: player {pid} {what} {old} -> {new}")
        conn.execute("INSERT INTO map_migrations (name, applied_at, moved) VALUES (?, ?, ?)",
                     (NAME, time.time(), len(plan)))
    return plan
