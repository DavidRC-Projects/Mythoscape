"""Resting Ox bar scene, end to end (headless): new account -> walk-in via the door action -> sit at the bar,
turn left/right, talk to both patrons, order + drink an ale, sit at a table, leave back to the village.
Test server on port 8798 (or a free port) with a COPY of the test DB; live 8765 / world.db never touched.
Set BAR_SHOTS=/dir to save proof frames.
"""
import os, sys, shutil, socket, tempfile, time
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import test_new_account as T

SHOTS = os.environ.get("BAR_SHOTS")


def port():
    try:
        s = socket.socket(); s.bind(("127.0.0.1", 8798)); s.close(); return 8798
    except OSError:
        return T.free_port()


def main():
    p = port()
    tmp = tempfile.mkdtemp(prefix="bar_")
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
    g.fire_action({"type": "BAR_ENTER"}); pump(90)
    assert bar.active and bar.view == "bar", (bar.active, bar.view)
    assert "Resting Ox" in bar.line, bar.line
    shot("01_bar_counter")
    key(pygame.K_t, 40); assert bar.speaker == "Barnaby", bar.speaker
    key(pygame.K_a, 60); assert bar.view == "left"
    key(pygame.K_t, 40); assert bar.speaker == "Old Tam", bar.speaker
    shot("02_look_left_talk")
    key(pygame.K_d, 10); key(pygame.K_d, 60); assert bar.view == "right"
    key(pygame.K_t, 40); assert bar.speaker.startswith("Wren"), bar.speaker
    shot("03_look_right_talk")
    key(pygame.K_o, 40); assert bar.view == "bar" and bar.has_ale, "ale not served"
    assert sess.coins == 10, "first ale should be free"
    key(pygame.K_SPACE, 1)
    assert bar.drinking()
    until(lambda: time.time() - bar.drink_t > 0.9, 3); shot("04_drink_mid")
    assert until(lambda: bar.sips == 1); assert not bar.drinking()
    shot("05_after_sip")
    key(pygame.K_SPACE, 1); until(lambda: bar.sips == 2); pump(2)
    key(pygame.K_SPACE, 1); until(lambda: bar.sips == 3)
    assert not bar.has_ale and bar.sips == 3
    key(pygame.K_o, 40); assert bar.has_ale and sess.coins == 8, sess.coins
    key(pygame.K_s, 60); assert bar.seat == "table" and bar.view == "table"
    assert (sess.bar or {}).get("seat") == "table"
    pump_for(0.5); shot("07_table")
    key(pygame.K_SPACE, 1); until(lambda: time.time() - bar.drink_t > 0.9, 3); shot("06_table_drink")
    until(lambda: not bar.drinking())
    key(pygame.K_ESCAPE, 60)
    assert not bar.active and (sess.x, sess.y) == (20, 43) and (g.player["x"], g.player["y"]) == (20, 43)
    shot("08_back_in_village")
    print("RESTING OX BAR TEST PASSED", flush=True)
    os._exit(0)


if __name__ == "__main__":
    try:
        main()
    except BaseException:
        import traceback; traceback.print_exc(); print("RESTING OX BAR TEST FAILED", flush=True); os._exit(1)
