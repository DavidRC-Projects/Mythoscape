"""Seraphine's tour is for NEW accounts only; guide_tour textures are opaque on a cocoa (alpha) display.
Throwaway server (free port, temp DB); never 8765 or the live world.db.
  * legacy_migration: a pre-tour players table (no guide_tour column) migrates every existing row to 100
    (finished), exactly like throne_vision_seen -> 1; rows made afterwards default to 0
  * existing_high_level_no_tour: a combat-100+ character with guide_tour=100 logs in, opens Equipment,
    and the tour never shows; a brand-new account does get it
  * textures_opaque: _portrait/_parchment are RGB-opaque even when flagless Surfaces carry an alpha mask
"""
import os, sys, sqlite3, tempfile, importlib.util
os.environ.setdefault("SDL_VIDEODRIVER", "dummy"); os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
spec = importlib.util.spec_from_file_location("_eqhl", os.path.join(ROOT, "tools", "test_equipment_highlevel.py"))
HL = importlib.util.module_from_spec(spec); spec.loader.exec_module(HL)
EQ = HL.EQ; check, RESULTS = EQ.check, EQ.RESULTS
ST = {}


def _add(conn, name):
    """Insert a minimal player row (every NOT NULL column without a default gets a dummy value)."""
    cols = [r for r in conn.execute("PRAGMA table_info(players)") if r[3] and r[4] is None and not r[5]]
    vals = {c[1]: (name if c[1] in ("username", "char_name") else (0 if "INT" in (c[2] or "").upper() or "REAL" in (c[2] or "").upper() else "x")) for c in cols}
    conn.execute(f"INSERT INTO players ({','.join(vals)}) VALUES ({','.join('?' * len(vals))})", list(vals.values()))


def test_legacy_migration():
    sys.path.insert(0, EQ.SRV)
    from database import Database
    path = os.path.join(tempfile.mkdtemp(prefix="tour_legacy_"), "w.db")
    Database(path).conn.close()
    c = sqlite3.connect(path)
    _add(c, 'old1')
    _add(c, 'old2')
    c.commit()
    c.execute("ALTER TABLE players DROP COLUMN guide_tour")          # back to the pre-tour schema
    c.commit(); c.close()
    d = Database(path)
    vals = [r[0] for r in d.conn.execute("SELECT guide_tour FROM players")]
    assert vals == [100, 100], vals
    _add(d.conn, 'new1')
    assert d.conn.execute("SELECT guide_tour FROM players WHERE username='new1'").fetchone()[0] == 0
    d.conn.close()


def test_existing_high_level_no_tour():
    import guide_tour
    port = EQ._na.free_port()
    db = os.path.join(tempfile.mkdtemp(prefix="tour_srv_"), "world.db")
    EQ._na.start_server(port, db); os.chdir(EQ.CLI)
    g = EQ.register(port, "veteran"); g.logout(); EQ.pump(g, 60)
    c = sqlite3.connect(db)
    for k, v in HL.GEAR.items():
        c.execute(f"UPDATE players SET equip_{k}=? WHERE username='veteran'", (v,))
    for k, v in HL.XP.items():
        c.execute(f"UPDATE players SET {k}=? WHERE username='veteran'", (v,))
    c.execute("UPDATE players SET guide_tour=100 WHERE username='veteran'")   # what the migration gives them
    c.commit(); c.close()
    g = EQ.login(port, "veteran")
    assert g.player_combat_level() >= 100
    g.show_equipment = True; EQ.pump(g, 40)
    assert int(g.player.get("guide_tour", -1)) == 100, g.player.get("guide_tour")
    assert not guide_tour.active(g), "tour showed for an existing account"
    if EQ.SHOTS:
        import pygame; pygame.image.save(g.screen, os.path.join(EQ.SHOTS, "veteran_no_tour.png"))
    n = EQ.register(port, "newbie"); n.needs_appearance = False; n.dialogue = None; EQ.pump(n, 40)
    assert int(n.player.get("guide_tour", -1)) == 0 or guide_tour.active(n), n.player.get("guide_tour")


def test_textures_opaque():
    import guide_tour
    guide_tour._ART.clear()
    with HL._AlphaSurface():
        for s in (guide_tour._portrait(120, 160), guide_tour._parchment(300, 120)):
            assert s.get_masks()[3] == 0, s.get_masks()
            assert all(s.get_at((x, y))[3] == 255 for x in range(0, s.get_width(), 9) for y in range(0, s.get_height(), 9))
    guide_tour._ART.clear()


def main():
    import pygame
    pygame.init()
    check("legacy_migration_marks_existing_finished", test_legacy_migration)
    check("existing_high_level_no_tour_new_account_gets_it", test_existing_high_level_no_tour)
    check("guide_tour_textures_opaque", test_textures_opaque)
    n = sum(1 for r in RESULTS if r[1])
    print(f"{n}/{len(RESULTS)} tour existing-account tests passed", flush=True)
    os._exit(0 if n == len(RESULTS) == 3 else 1)


if __name__ == "__main__":
    try:
        main()
    except BaseException:
        import traceback; traceback.print_exc(); print("TOUR EXISTING TEST FAILED", flush=True); os._exit(1)
