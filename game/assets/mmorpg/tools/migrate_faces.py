"""Give every saved look a face (David, 29 Oct 2026): a look with no face, or one no longer in the catalogue,
gets the face its outfit was painted with (outfits.default_face), so nobody's face changes.
The game also does this lazily, so running this is optional.
Run: python3 tools/migrate_faces.py --db PATH [--dry-run]    (refuses the live server/world.db unless --live)"""
import argparse
import json
import os
import shutil
import sqlite3
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "server"))
import outfits  # noqa: E402

LIVE = os.path.realpath(os.path.join(ROOT, "server", "world.db"))


def migrate(path, dry=False):
    con = sqlite3.connect(path)
    con.row_factory = sqlite3.Row
    changed = seen = 0
    for row in con.execute("SELECT id, gender, appearance FROM players").fetchall():
        try:
            look = json.loads(row["appearance"]) if row["appearance"] else None
        except ValueError:
            continue
        if not isinstance(look, dict):
            continue
        seen += 1
        sex = row["gender"] or "male"
        if look.get("face") in outfits.face_ids(sex):
            continue
        look["face"] = outfits.default_face(sex, look)
        changed += 1
        if not dry:
            con.execute("UPDATE players SET appearance = ? WHERE id = ?", (json.dumps(look), row["id"]))
    if not dry:
        con.commit()
    con.close()
    return seen, changed


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", required=True)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--live", action="store_true", help="allow the live world.db (stop the server first)")
    a = ap.parse_args()
    if os.path.realpath(a.db) == LIVE and not a.live:
        sys.exit("Refusing the live world.db without --live (stop the server first).")
    if not a.dry_run:
        bak = f"{a.db}.pre_faces_{time.strftime('%Y%m%d_%H%M%S')}"
        src = sqlite3.connect(a.db)
        dst = sqlite3.connect(bak)
        src.backup(dst)
        dst.close()
        src.close()
        print("backup:", bak)
    seen, changed = migrate(a.db, a.dry_run)
    print(f"looks: {seen}  given a face: {changed}{'  (dry run)' if a.dry_run else ''}")


if __name__ == "__main__":
    main()
