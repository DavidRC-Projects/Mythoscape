"""Royal Herald outside King's Castle + Seraphine War for the Crown walk."""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, ".."))
sys.path.insert(0, os.path.join(ROOT, "server"))

import content  # noqa: E402
import crown_war_guide as cg  # noqa: E402
import database  # noqa: E402
import throne  # noqa: E402

database.Database.__init__.__defaults__ = (":memory:",)


def check(ok, msg):
    if not ok:
        raise AssertionError(msg)
    print("ok ", msg)


def test_herald_outside_castle():
    herald = next(n for n in content.NPCS if n["id"] == "royal_herald")
    check((herald["x"], herald["y"]) == cg.HERALD_OUTSIDE,
          f"Herald stands outside castle approach {herald['x'], herald['y']}")
    check("outside" in " ".join(herald["lines"]).lower()
          or "approach" in " ".join(herald["lines"]).lower(),
          "Herald lines mention outside / approach")
    dest = next(d for d in content.TELEPORT_DESTINATIONS if d["id"] == "royal_herald")
    check((dest["x"], dest["y"]) == cg.HERALD_OUTSIDE, f"teleport pin matches ({dest})")
    check(any(o["id"] == "siege_guide" for o in throne.HERALD_OPTIONS),
          "Herald options include How the War works")


def test_verbose_guide_pages():
    pages = cg.guide_pages()
    check(len(pages) >= 6, f"enough guide pages ({len(pages)})")
    blob = " ".join(" ".join(p) for p in pages).lower()
    for needle in ("war for the crown", "storehouse", "throne", "royal guard",
                   "assault", "guild", "utc", "/siege"):
        check(needle in blob, f"guide mentions {needle!r}")
    lines, page = cg.guide_dialogue_lines(0)
    check(page == 0 and lines and "1/" in lines[-1], f"page 0 footer ({lines[-1]})")
    opts = cg.guide_options(0)
    check(any(o["id"] == "siege_guide_1" for o in opts), f"next option ({opts})")
    last = len(pages) - 1
    opts_last = cg.guide_options(last)
    check(any(o["id"] == "siege_guide_done" for o in opts_last), f"done option ({opts_last})")


def test_crown_guide_progress():
    db = database.Database(":memory:")
    cg.ensure_schema(db.conn)
    db.create_account("guide_t", "pw", "GuideTester", gender="male")
    pid = db.conn.execute("SELECT id FROM players WHERE username='guide_t'").fetchone()[0]
    row = db.conn.execute("SELECT crown_guide FROM players WHERE id=?", (pid,)).fetchone()
    check(int(row[0]) == 0, "starts available")
    db.conn.execute("UPDATE players SET crown_guide=? WHERE id=?", (cg.CROWN_GUIDE_TALK, pid))
    db.conn.commit()

    class Sess:
        crown_guide = cg.CROWN_GUIDE_TALK

    sess = Sess()
    ok = cg.mark_talked(db.conn, pid, session=sess)
    check(ok and sess.crown_guide == cg.CROWN_GUIDE_DONE, "talk completes tour")
    row = db.conn.execute("SELECT crown_guide FROM players WHERE id=?", (pid,)).fetchone()
    check(int(row[0]) == cg.CROWN_GUIDE_DONE, "persisted done")


if __name__ == "__main__":
    test_herald_outside_castle()
    test_verbose_guide_pages()
    test_crown_guide_progress()
    print("crown war guide ok")
