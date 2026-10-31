"""Throne vision intro film: assets, audio/picture sync, played flag, skip, Settings replay, credits.

Uses a throwaway server (free port, temp DB) like test_new_account; the live world.db and
port 8765 are never touched.
  * the shipped film: 1020 pre-extracted 1280x720 frames at 24 fps + audio.ogg of the same
    length (so the audio clock maps onto the frames with no drift); source is v4, not v3
  * DB: a new account starts unseen; accounts that existed before the column count as seen
  * server validation: THRONE_VISION_SEEN only from a logged-in session, no extra fields,
    one-way, written once
  * client: a new account goes LOGIN -> STAT_ALLOC -> THRONE_VISION (frames advancing with the
    clock) -> any key skips -> GAME, and the server flag is set; logging in again does not
    replay it; Settings 'Replay throne vision' plays it again and its Skip button ends it
  * the music credit is in the game credits
"""
import os, sys, time, sqlite3, tempfile, asyncio, importlib.util
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRV, CLI = os.path.join(ROOT, "server"), os.path.join(ROOT, "client")
CREDIT = "Five Armies by Kevin MacLeod (incompetech.com), CC BY 4.0"

spec = importlib.util.spec_from_file_location("_na", os.path.join(ROOT, "tools", "test_new_account.py"))
_na = importlib.util.module_from_spec(spec); spec.loader.exec_module(_na)

RESULTS = []


def check(name, fn):
    try:
        fn(); RESULTS.append((name, True, "")); print("ok  ", name, flush=True)
    except Exception as e:
        import traceback; traceback.print_exc()
        RESULTS.append((name, False, repr(e))); print("FAIL", name, repr(e), flush=True)


def test_assets_and_sync():
    sys.path.insert(0, CLI)
    import pygame, throne_vision as TV
    pygame.init(); pygame.display.set_mode((8, 8)); pygame.mixer.init(44100)
    m = TV.meta()
    assert m.get("source") == "throne_vision_v4.mp4", m
    assert not os.path.exists(os.path.join(TV.DIR, "throne_vision_v3.mp4"))
    assert os.path.isfile(os.path.join(TV.DIR, "throne_vision_v4.mp4"))
    frames = sorted(f for f in os.listdir(os.path.join(TV.DIR, "frames")) if f.endswith(".jpg"))
    assert len(frames) == m["frames"] == 1020, len(frames)
    for i in (1, 510, 1020):
        assert pygame.image.load(TV._frame_path(i)).get_size() == (1280, 720)
    alen = pygame.mixer.Sound(os.path.join(TV.DIR, m["audio"])).get_length()
    assert abs(alen - m["frames"] / m["fps"]) < 0.1, (alen, m["frames"] / m["fps"])
    assert TV.frame_for_ms(0) == 1 and TV.frame_for_ms(1000) == 25 and TV.frame_for_ms(10_000_000) == 1020
    assert TV.frame_for_ms(21250) == 511                  # mid-film: audio time -> frame, no drift


def test_db_flag_and_migration():
    sys.path.insert(0, SRV)
    cwd = os.getcwd(); os.chdir(SRV)
    import database
    os.chdir(cwd)
    d = tempfile.mkdtemp(prefix="tv_db_")
    # a database from before the column: existing players count as having seen it
    old = os.path.join(d, "old.db")
    schema = "\n".join(l for l in database.SCHEMA.splitlines() if "throne_vision_seen" not in l)
    c = sqlite3.connect(old); c.executescript(schema)
    c.execute("INSERT INTO players (username, password_hash, salt, char_name, x, y, created_at, last_login) "
              "VALUES ('veteran','h','s','Vet',1,1,'2026-01-01 00:00:00','2026-01-01 00:00:00')")
    c.commit(); c.close()
    db = database.Database(old)
    assert db.conn.execute("SELECT throne_vision_seen FROM players WHERE username='veteran'").fetchone()[0] == 1
    db.create_account("rookie1", "pw123456", "Rookie")
    q = "SELECT throne_vision_seen FROM players WHERE username=?"
    assert db.conn.execute(q, ("rookie1",)).fetchone()[0] == 0
    # fresh database
    db2 = database.Database(os.path.join(d, "new.db"))
    db2.create_account("rookie2", "pw123456", "Rookie2")
    assert db2.conn.execute(q, ("rookie2",)).fetchone()[0] == 0


def _pump(g, frames, until=None, each=None):
    import idle_client
    for i in range(frames):
        g.handle_network(); g.update_walk(); g.handle_events()
        idle_client.tick(g); g._pump_zoom(); g.update_inventory_hover(); g.draw()
        if each:
            each(i)
        if until and until():
            return True
        time.sleep(1 / 120)
    return bool(until and until())


def _new_client(port):
    import client
    client.SERVER_URI = f"ws://127.0.0.1:{port}"
    g = client.GameClient()
    t0 = time.time()
    while not g.net.connected and time.time() - t0 < 10:
        g.handle_network(); time.sleep(0.05)
    assert g.net.connected
    return g


STATE = {}


def test_server_validation():
    import server
    seen = []
    class _DB:
        def save_player_stats(self, pid, **f): seen.append((pid, f))
    real = server.WORLD.db
    server.WORLD.db = _DB()
    try:
        class S: pass
        anon = S(); anon.player_id = None; anon.throne_vision_seen = False
        assert asyncio.run(server.handle_throne_vision_seen(anon, {"type": "THRONE_VISION_SEEN"})) is False
        s = S(); s.player_id = 7; s.throne_vision_seen = False
        assert asyncio.run(server.handle_throne_vision_seen(s, {"type": "THRONE_VISION_SEEN", "seen": 0})) is False
        assert asyncio.run(server.handle_throne_vision_seen(s, {"type": "THRONE_VISION_SEEN", "player_id": 1})) is False
        assert asyncio.run(server.handle_throne_vision_seen(s, "x")) is False
        assert not seen and not s.throne_vision_seen
        assert asyncio.run(server.handle_throne_vision_seen(s, {"type": "THRONE_VISION_SEEN"})) is True
        assert asyncio.run(server.handle_throne_vision_seen(s, {"type": "THRONE_VISION_SEEN"})) is False
        assert seen == [(7, {"throne_vision_seen": 1})], seen
    finally:
        server.WORLD.db = real


def test_first_login_skip_and_flag():
    import pygame
    port, db = STATE["port"], STATE["db"]
    g = _new_client(port)
    name = "tv%d" % (int(time.time() * 1000) % 10**7)
    STATE["name"] = name
    g.login_mode = "register"
    g.fields.update(username=name, password="pw123456", char_name=name.capitalize())
    g.submit_login()
    from client_screens import STAT_PRESETS
    def step(i):
        if g.state == "STAT_ALLOC" and not STATE.get("sent"):
            g.stat_alloc = dict(STAT_PRESETS[0][1]); g.submit_stat_alloc(); STATE["sent"] = True
        assert g.state != "OPENING_COMIC", "opening comic is retired"
    assert _pump(g, 1500, until=lambda: g.state == "THRONE_VISION", each=step), g.state
    import throne_vision as TV
    shown = set()
    t0 = time.time()
    _pump(g, 400, until=lambda: time.time() - t0 > 1.5, each=lambda i: shown.add(TV._STATE.get("frame")))
    assert len(shown) > 10, shown                         # picture advances with the clock
    f = TV._STATE.get("frame"); exp = TV.frame_for_ms(TV.elapsed_ms())
    assert abs(f - exp) <= 2, (f, exp)                     # in step with the audio clock
    assert g.throne_vision_skip_rect is not None
    pygame.event.post(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_a, mod=0, unicode="a", scancode=0))
    assert _pump(g, 200, until=lambda: g.state == "GAME"), g.state
    ok = _pump(g, 400, until=lambda: sqlite3.connect(db).execute(
        "SELECT throne_vision_seen FROM players WHERE username=?", (name,)).fetchone()[0] == 1)
    assert ok, "server played flag not saved"
    STATE["g"] = g


def test_settings_replay_and_skip_button():
    import pygame
    g = STATE["g"]
    if getattr(g.outfitters, "active", False):          # the new-account look creator opens after the film
        g.outfitters.active = False
    g.show_help = True
    _pump(g, 3)
    r = g.throne_vision_replay_rect
    assert r is not None
    pygame.event.post(pygame.event.Event(pygame.MOUSEBUTTONDOWN, button=1, pos=r.center))
    assert _pump(g, 30, until=lambda: g.state == "THRONE_VISION"), g.state
    t0 = time.time()
    _pump(g, 200, until=lambda: time.time() - t0 > 0.6)
    pygame.event.post(pygame.event.Event(pygame.MOUSEBUTTONDOWN, button=1, pos=g.throne_vision_skip_rect.center))
    assert _pump(g, 60, until=lambda: g.state == "GAME"), g.state


def test_second_login_does_not_replay():
    if "g" in STATE:                                     # one session per account: log the first out
        STATE["g"].logout(); _pump(STATE["g"], 60)
    g = _new_client(STATE["port"])
    g.login_mode = "login"
    g.fields.update(username=STATE["name"], password="pw123456")
    g.submit_login()
    states = []
    _pump(g, 600, until=lambda: g.state == "GAME" and len(states) > 30,
          each=lambda i: states.append(g.state))
    assert "THRONE_VISION" not in states and g.state == "GAME", (states[-5:], g.login_error)
    assert g.player.get("throne_vision_seen") is True


def test_credits():
    txt = open(os.path.join(ROOT, "assets", "music", "CREDITS.txt")).read()
    assert CREDIT in txt
    assert CREDIT in open(os.path.join(CLI, "client_screens.py")).read()
    import throne_vision
    assert throne_vision.CREDIT == CREDIT


def main():
    check("assets_and_sync", test_assets_and_sync)
    check("db_flag_and_migration", test_db_flag_and_migration)
    port = _na.free_port()
    db = os.path.join(tempfile.mkdtemp(prefix="tv_srv_"), "world.db")
    _na.start_server(port, db)
    STATE.update(port=port, db=db)
    sys.path.insert(0, CLI); os.chdir(CLI)
    check("server_validation", test_server_validation)
    check("first_login_skip_and_flag", test_first_login_skip_and_flag)
    if "g" in STATE:
        check("settings_replay_and_skip_button", test_settings_replay_and_skip_button)
    check("second_login_does_not_replay", test_second_login_does_not_replay)
    check("credits", test_credits)
    n = sum(1 for r in RESULTS if r[1])
    print(f"{n}/{len(RESULTS)} throne vision tests passed", flush=True)
    os._exit(0 if n == len(RESULTS) == 7 else 1)


if __name__ == "__main__":
    try:
        main()
    except BaseException:
        import traceback; traceback.print_exc(); print("THRONE VISION TEST FAILED", flush=True); os._exit(1)
