"""End-to-end: create a brand-new account and play into the world, headless.

Starts a throwaway server (free port, empty temp DB; the live world.db and
port 8765 are never touched), then drives the real GameClient through
CREATE_CHARACTER -> stat allocation (incl. a preset click) -> opening comic
-> GAME, drawing every frame. Any exception fails the test.
Covers two regressions that broke new accounts:
  * stat presets keyed a dict by pygame.Rect (unhashable) -> TypeError on
    the first stat-alloc frame;
  * a function-local `import new_player_guide` in process_message made the
    WELCOME_STATE branch raise UnboundLocalError.
"""
import os, sys, socket, tempfile, threading, asyncio, time
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRV, CLI = os.path.join(ROOT, "server"), os.path.join(ROOT, "client")


def free_port():
    s = socket.socket(); s.bind(("127.0.0.1", 0)); p = s.getsockname()[1]; s.close(); return p


def start_server(port, db_path):
    sys.path.insert(0, SRV)
    cwd = os.getcwd(); os.chdir(SRV)
    import database
    database.Database.__init__.__defaults__ = (db_path,)
    database.DB_PATH = db_path
    import server
    os.chdir(cwd)
    server.PORT = port
    threading.Thread(target=lambda: asyncio.run(server.main()), daemon=True).start()
    for _ in range(200):
        try:
            socket.create_connection(("127.0.0.1", port), 0.2).close(); return
        except OSError:
            time.sleep(0.1)
    raise SystemExit("FAIL: test server did not start")


def main():
    port = free_port()
    db = os.path.join(tempfile.mkdtemp(prefix="newacct_"), "world.db")
    start_server(port, db)
    sys.path.insert(0, CLI); os.chdir(CLI)
    import client, pygame, idle_client
    client.SERVER_URI = f"ws://127.0.0.1:{port}"
    g = client.GameClient()
    t0 = time.time()
    while not g.net.connected and time.time() - t0 < 10:
        g.handle_network(); time.sleep(0.05)
    assert g.net.connected, "client could not connect"
    name = "nt%d" % (int(time.time() * 1000) % 10**7)
    g.login_mode = "register"
    g.fields.update(username=name, password="pw12345", char_name=name.capitalize())
    g.submit_login()
    seen, clicked, sent = [], False, False
    for i in range(900):
        g.handle_network(); g.update_walk(); g.handle_events()
        idle_client.tick(g); g._pump_zoom(); g.update_inventory_hover(); g.draw()
        if not seen or seen[-1] != g.state:
            seen.append(g.state)
        if g.state == "STAT_ALLOC" and not clicked and getattr(g, "stat_preset_rects", None):
            rect, points = g.stat_preset_rects[0]
            pygame.event.post(pygame.event.Event(pygame.MOUSEBUTTONDOWN, button=1, pos=rect.center))
            clicked = True
        elif g.state == "STAT_ALLOC" and clicked and not sent and g.remaining_stat_points() == 0:
            g.submit_stat_alloc(); sent = True
        elif g.state == "OPENING_COMIC" and i % 15 == 0:
            pygame.event.post(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_ESCAPE, mod=0, unicode="", scancode=0))
        if g.state == "GAME" and seen.count("GAME") and i > 120 and sent:
            break
        time.sleep(1 / 120)
    print("states:", " -> ".join(seen), flush=True)
    assert clicked, "stat preset buttons never drawn"
    assert sent, "stat allocation never submitted (preset click failed?)"
    assert seen[-1] == "GAME", f"new account never reached the world: {seen}"
    print("NEW ACCOUNT TEST PASSED", flush=True)
    os._exit(0)


if __name__ == "__main__":
    try:
        main()
    except BaseException:
        import traceback; traceback.print_exc(); sys.stderr.flush(); print("NEW ACCOUNT TEST FAILED", flush=True); os._exit(1)
