"""Resting Ox: Bram's "Watch the entry film again" replays the film (skippable) without touching intro_seen.
Based on test_resting_ox_bar.py: (headless): new account -> walk in through the arch -> entry film (skipped) ->
Bram's greeting and menu, turn left/right, talk to Wenna and Tobin, buy + drink a 5c ale (no free ale for a
new traveller), pick table 1, board / trophy wall / bard, leave back to the village.
Test server on port 8799 (or a free port) with a COPY of the test DB; live 8765 / world.db never touched.
Set BAR_SHOTS=/dir to save proof frames.
"""
import os, sys, shutil, socket, tempfile, time
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import test_new_account as T

SHOTS = os.environ.get("BAR_REPLAY_SHOTS")


def port():
    try:
        s = socket.socket(); s.bind(("127.0.0.1", 8799)); s.close(); return 8799
    except OSError:
        return T.free_port()


def main():
    p = port()
    tmp = tempfile.mkdtemp(prefix="barreplay_")
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
    sess.x, sess.y = 20, 43     # Resting Ox arch exit tile (resting_ox_arch)
    g.player["x"], g.player["y"] = 20, 43
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

    assert g.can_do_action({"type": "BAR_ENTER", "door": (20, 42)}, 20, 43)
    assert not g.can_do_action({"type": "BAR_ENTER", "door": (20, 42)}, 14, 43)   # the wooden front door is not the bar
    g.fire_action({"type": "BAR_ENTER"}); pump(40)
    # first visit: the entry film plays; Skip shows after 0.5 s, any key then skips (0.3 s fade)
    assert bar.intro is not None, "first visit should play the entry film"
    pump_for(0.7); shot("00_intro_frame")
    key(pygame.K_ESCAPE, 1); until(lambda: bar.intro is None, 3)
    assert bar.intro is None and bar.active, "intro did not skip"
    pump_for(0.8)
    assert bar.active and bar.view == "bar", (bar.active, bar.view)
    assert bar.speaker == "Bram" and "traveller" in bar.line, (bar.speaker, bar.line)
    shot("01_bar_counter")
    import tavern
    pump_for(0.5)
    assert tavern.load(server.WORLD.db.conn, sess.player_id).get("intro_seen") is True, "first film should mark seen"
    key(pygame.K_t, 40); assert bar.speaker == "Bram", bar.speaker
    labels = [c[0] for c in bar.choices]
    assert "Watch the entry film again" in labels, labels
    shot("01_bram_menu_watch_again")
    n = labels.index("Watch the entry film again") + 1
    key(getattr(pygame, "K_%d" % n), 20)
    assert bar.intro is not None, "replay did not start the film"
    pump_for(1.5); shot("02_film_replaying")
    key(pygame.K_ESCAPE, 1); until(lambda: bar.intro is None, 3)
    pump_for(0.8)
    assert bar.intro is None and bar.active and bar.view == "bar", (bar.active, bar.view)
    shot("03_back_in_bar")
    assert tavern.load(server.WORLD.db.conn, sess.player_id).get("intro_seen") is True
    # ---- walking into the arch enters the bar like a click (no loop when stepping back out) ----
    key(pygame.K_ESCAPE, 1); until(lambda: not bar.active, 4)
    assert not bar.active, "did not leave the bar"; print("LEFT", getattr(bar, "left_at", None), g.player_xy(), flush=True)
    sess.x, sess.y = 20, 43; g.player["x"], g.player["y"] = 20, 43
    g._next_walk_at = 0; g.try_move(0, -1); pump(20)
    assert not bar.active, ("walk-in re-triggered straight after leaving (cooldown)", time.time() - getattr(bar, "left_at", 0), g.player_xy())
    pump_for(1.7)
    sess.x, sess.y = 20, 43; g.player["x"], g.player["y"] = 20, 43; pump(5)   # stepped back off the arch
    g._next_walk_at = 0; g.try_move(0, -1)
    assert until(lambda: bar.active, 4), "walking into the arch did not enter the bar"
    assert bar.intro is None, "intro_seen=True: walking in should not replay the film"
    pump_for(0.6); shot("04_walked_in_via_arch")
    print("PASS test_bar_replay_intro", flush=True)
    os._exit(0)


if __name__ == "__main__":
    try:
        main()
    except BaseException:
        import traceback; traceback.print_exc(); print("FAIL test_bar_replay_intro", flush=True); os._exit(1)
