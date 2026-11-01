"""One-shot: the King's Row plaza moved 10 rows south. Saved positions still inside the OLD plaza
area (x 0-44, rows 97-144) are moved down by 10 rows, so those players don't log in 10 rows off.

Dry run (default, changes nothing):   python3 tools/migrate_plaza_shift_2026_10.py /path/to/world.db
Apply (STOP THE SERVER FIRST):        python3 tools/migrate_plaza_shift_2026_10.py /path/to/world.db --apply
Optional: --before "2026-10-31 19:12"  only move players whose last_login is before the shift went live
(anyone who has logged in since is already standing on new coordinates).

Apply makes a backup (<db>.pre_plaza_shift_2026_10.bak), writes a map_migrations row and refuses to
run twice. dungeon_resume return points inside the old area are shifted too.
"""
import argparse
import json
import os
import socket
import sqlite3
import sys
import time

NAME = "plaza_shift_2026_10"
X0, X1, Y0, Y1, DY = 0, 44, 97, 144, 10


def inside(x, y):
    return x is not None and y is not None and X0 <= int(x) <= X1 and Y0 <= int(y) <= Y1


def server_up(port=8765):
    try:
        socket.create_connection(("127.0.0.1", port), 0.3).close()
        return True
    except OSError:
        return False


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("db")
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--before", default=None, help="only players whose last_login < this (text compare, 'YYYY-MM-DD HH:MM')")
    a = ap.parse_args()
    if not os.path.exists(a.db):
        sys.exit(f"no such db: {a.db}")
    if a.apply and server_up():
        sys.exit("refusing: something is listening on 8765 - stop the game server first")
    conn = sqlite3.connect(a.db)
    conn.execute("CREATE TABLE IF NOT EXISTS map_migrations (name TEXT PRIMARY KEY, applied_at REAL, moved INTEGER)") if a.apply else None
    try:
        done = conn.execute("SELECT applied_at FROM map_migrations WHERE name = ?", (NAME,)).fetchone()
    except sqlite3.OperationalError:
        done = None
    if done:
        print(f"{NAME} already applied at {time.ctime(done[0])} - nothing to do")
        return
    rows = conn.execute("SELECT id, char_name, x, y, dungeon_resume, last_login FROM players").fetchall()
    plan = []
    for pid, name, x, y, resume, last in rows:
        if a.before and last and str(last) >= a.before:
            continue
        if inside(x, y):
            plan.append((pid, name, "pos", (int(x), int(y)), (int(x), int(y) + DY), last))
        try:
            d = json.loads(resume) if resume else None
        except (TypeError, ValueError):
            d = None
        if isinstance(d, dict) and inside(d.get("return_x"), d.get("return_y")):
            rx, ry = int(d["return_x"]), int(d["return_y"])
            plan.append((pid, name, "resume", (rx, ry), (rx, ry + DY), last))
    players = len({p[0] for p in plan})
    print(f"{'APPLY' if a.apply else 'DRY RUN'} {NAME} on {a.db}")
    print(f"players scanned: {len(rows)}; players to move: {players}; entries: {len(plan)}")
    for pid, name, what, old, new, last in plan:
        print(f"  #{pid:<5} {name:<20} {what:<6} {old} -> {new}   last_login={last}")
    if not a.apply:
        print("dry run only - nothing written")
        return
    dest = a.db + f".pre_{NAME}.bak"
    out = sqlite3.connect(dest); conn.backup(out); out.close()
    print("backup:", dest)
    with conn:
        for pid, name, what, old, new, last in plan:
            if what == "pos":
                conn.execute("UPDATE players SET x = ?, y = ? WHERE id = ?", (new[0], new[1], pid))
            else:
                d = json.loads(conn.execute("SELECT dungeon_resume FROM players WHERE id = ?", (pid,)).fetchone()[0])
                d["return_x"], d["return_y"] = new
                conn.execute("UPDATE players SET dungeon_resume = ? WHERE id = ?", (json.dumps(d), pid))
        conn.execute("INSERT INTO map_migrations (name, applied_at, moved) VALUES (?, ?, ?)", (NAME, time.time(), players))
    print(f"applied: {players} players moved")


if __name__ == "__main__":
    main()
