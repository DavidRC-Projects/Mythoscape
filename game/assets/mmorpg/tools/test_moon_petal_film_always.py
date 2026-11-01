"""Moon Petal Inn: walking into the door plays the entry film EVERY time; Space, Esc and a click each skip it.
Based on test_resting_ox_bar.py: (headless): new account -> walk in through the arch -> entry film (skipped) ->
Bram's greeting and menu, turn left/right, talk to Wenna and Tobin, buy + drink a 5c ale (no free ale for a
new traveller), pick table 1, board / trophy wall / bard, leave back to the village.
Test server on port 8797 (or a free port) with a COPY of the test DB; live 8765 / world.db never touched.
Set BAR_SHOTS=/dir to save proof frames.
"""
import os, sys, shutil, socket, tempfile, time
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import test_new_account as T

SHOTS = os.environ.get("MOON_SHOTS")


def port():
    try:
        s = socket.socket(); s.bind(("127.0.0.1", 8797)); s.close(); return 8797
    except OSError:
        return T.free_port()


def main():
    p = port()
    tmp = tempfile.mkdtemp(prefix="moonfilm_")
    db = os.path.join(tmp, "world.db")
    src = os.environ.get("CROWNFALL_DB_PATH") or os.path.expanduser("~/grokbot_tmp/testdb/world.db")
    if os.path.isfile(src):
        shutil.copy(src, db)
    T.start_server(p, db)
    sys.path.insert(0, T.CLI); os.chdir(T.CLI)
    import client, pygame, server
    client.SERVER_URI = f"ws://127.0.0.1:{p}"
    g = client.GameClient()
    t0 = time.time()
    while not g.net.connected and time.time() - t0 < 10:
        g.handle_network(); time.sleep(0.05)
    name = "ox%d" % (int(time.time() * 1000) % 10**7)
    g.login_mode = "register"
    g.fields.update(username=name, password="pw123456", char_name=name.capitalize())
    g.submit_login()

    def pump(n=1, draw=True):
        for _ in range(n):
            g.handle_network(); g.handle_events()
            if draw:
                g.draw()
            time.sleep(1 / 120)

    for i in range(900):
        pump(1, draw=False)
        if g.state == "STAT_ALLOC" and g.remaining_stat_points() > 0:
            from client_screens import STAT_PRESETS
            g.stat_alloc = dict(STAT_PRESETS[0][1]); g.submit_stat_alloc()
        elif g.state == "THRONE_VISION" and i % 15 == 0:
            pygame.event.post(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_ESCAPE, mod=0, unicode="", scancode=0))
        if g.state == "GAME" and g.player:
            break
    assert g.state == "GAME", g.state
    g.needs_appearance = False
    if g.outfitters.active:
        g.outfitters.active = False
    sess = next(s for s in server.WORLD.sessions.values() if s.username == name) \
        if hasattr(next(iter(server.WORLD.sessions.values())), "username") else next(iter(server.WORLD.sessions.values()))
    # stand just inside the arched door, as click_door leaves you
    sess.x, sess.y = 21, 83     # Moon Petal Inn door stand tile
    g.player["x"], g.player["y"] = 21, 83
    sess.coins = 10
    bar = g.resting_ox

    def pump_for(sec):
        end = time.time() + sec
        while time.time() < end:
            pump(1)

    def until(cond, sec=8):
        end = time.time() + sec
        while time.time() < end and not cond():
            pump(1)
        return cond()

    def key(k, n=30):
        pygame.event.post(pygame.event.Event(pygame.KEYDOWN, key=k, mod=0, unicode="", scancode=0)); pump(n)

    def shot(tag):
        if SHOTS:
            os.makedirs(SHOTS, exist_ok=True); pygame.image.save(g.screen, os.path.join(SHOTS, tag + ".png"))

    mp = g.moon_petal
    skips = [("space", lambda: key(pygame.K_SPACE, 1)), ("esc", lambda: key(pygame.K_ESCAPE, 1)),
             ("click", lambda: (pygame.event.post(pygame.event.Event(pygame.MOUSEBUTTONDOWN, button=1, pos=(400, 300))), pump(1)))]
    for n, (how, skip) in enumerate(skips, 1):
        sess.x, sess.y = 21, 83; g.player["x"], g.player["y"] = 21, 83; pump(3)
        g._next_walk_at = 0; g.try_move(0, -1); pump(2)
        assert mp.active and mp.mode == "film" and mp.film is not None, ("visit %d: no film" % n, mp.active, mp.mode)
        pump_for(0.8); shot("moon_%d_film_playing" % n)
        skip()
        assert until(lambda: mp.mode == "room", 3), ("visit %d: %s did not skip" % (n, how), mp.mode)
        pump_for(0.4); shot("moon_%d_room_after_%s" % (n, how))
        mp.leave(); pump(3); assert not mp.active
    print("PASS test_moon_petal_film_always", flush=True)
    os._exit(0)


if __name__ == "__main__":
    try:
        main()
    except BaseException:
        import traceback; traceback.print_exc(); print("FAIL test_moon_petal_film_always", flush=True); os._exit(1)
