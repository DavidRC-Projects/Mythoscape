"""Moon Petal Inn door, end to end on a scratch server (live 8765 / world.db never touched):
door (21,82) reachable from the plaza forecourt, hover glow + door cursor, click walks over and enters,
walking north into the door tile enters. MP_SHOTS=/dir saves the hover frame."""
import os, sys, shutil, tempfile, time
from collections import deque
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import test_new_account as T

DOOR, STAND, FORECOURT = (21, 82), (21, 83), (13, 100)
fails = []


def check(name, ok):
    print(("ok   " if ok else "FAIL ") + name)
    if not ok:
        fails.append(name)


def main():
    p = T.free_port()
    tmp = tempfile.mkdtemp(prefix="mpdoor_")
    db = os.path.join(tmp, "world.db")
    src = os.environ.get("CROWNFALL_DB_PATH") or os.path.expanduser("~/grokbot_tmp/testdb/world.db")
    if os.path.isfile(src):
        shutil.copy(src, db)
    T.start_server(p, db)
    sys.path.insert(0, T.CLI); os.chdir(T.CLI)
    import client, pygame, server, world_map as wm, moon_petal_inn as M
    client.SERVER_URI = f"ws://127.0.0.1:{p}"
    g = client.GameClient()
    t0 = time.time()
    while not g.net.connected and time.time() - t0 < 10:
        g.handle_network(); time.sleep(0.05)
    name = "mp%d" % (int(time.time() * 1000) % 10**7)
    g.login_mode = "register"
    g.fields.update(username=name, password="pw123456", char_name=name.capitalize())
    g.submit_login()

    def pump(n=1, draw=True):
        for _ in range(n):
            g.handle_network(); g.update_walk(); g.handle_events()
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
    sess = list(server.WORLD.sessions.values())[-1]
    grid = server.WORLD.grid

    # 1) reachability: forecourt -> stand tile in front of the door
    seen, q = {FORECOURT}, deque([FORECOURT])
    while q:
        x, y = q.popleft()
        for n in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)):
            if n not in seen and 0 <= n[1] < len(grid) and 0 <= n[0] < len(grid[0]) and wm.is_walkable(grid, *n):
                seen.add(n); q.append(n)
    check("forecourt tile walkable", wm.is_walkable(grid, *FORECOURT))
    check("door stand tile (21,83) reachable from the forecourt", STAND in seen)
    check("door is a known interactable on the client", g.moon_petal.is_door(*DOOR))

    def place(x, y):
        # a veteran: the new-account guide tour (which owns clicks) is finished
        g.player["guide_tour"] = 100
        if hasattr(sess, "guide_tour"):
            sess.guide_tour = 100
        sess.x, sess.y = x, y
        g.player["x"], g.player["y"] = x, y
        g._predicted_step = None
        g.path = [] if hasattr(g, "path") else None
        pump(20)

    def door_pixel():
        for my in range(0, client.MAP_H, 4):
            for mx in range(0, client.MAP_W, 4):
                if g.screen_to_tile(mx, my) == DOOR:
                    return mx + 2, my + 2
        return None

    # 2) hover: glow + door cursor
    place(21, 86)
    pos = door_pixel()
    check("door tile on screen", pos is not None)
    real = pygame.mouse.get_pos
    pygame.mouse.get_pos = lambda: pos
    calls = []
    orig = M.draw_door_hover
    M.draw_door_hover = lambda c, r: (calls.append(r), orig(c, r))
    pump(3)
    check("hover draws the door glow", bool(calls))
    check("hover sets the door cursor", M._CURSOR["kind"] == "door")
    shots = os.environ.get("MP_SHOTS")
    if shots:
        os.makedirs(shots, exist_ok=True); pygame.image.save(g.screen, os.path.join(shots, "door_hover.png"))
    M.draw_door_hover = orig

    # 3) click from a few tiles away: walk over and enter
    place(16, 86)
    pos = door_pixel()
    pygame.mouse.get_pos = lambda: pos
    if os.environ.get("MP_TRACE"):
        last = {}
        def tr(frame, ev, arg):
            if frame.f_code.co_name == "handle_mouse_click":
                if ev == "line": last["l"] = frame.f_lineno
                if ev == "return": print("click returned at line", last.get("l"))
                return tr
            return tr if frame.f_code.co_name == "handle_mouse_click" else None
        sys.settrace(lambda f, e, a: tr if f.f_code.co_name == "handle_mouse_click" else None)
        import guide_tour, ui_coach, new_player_guide, mercenaries_ui, arena_duel_ui
        for mod, fn in ((guide_tour, "handle_click"), (ui_coach, "handle_event"), (new_player_guide, "handle_event"), (mercenaries_ui, "handle_event"), (arena_duel_ui, "handle_event")):
            o = getattr(mod, fn)
            setattr(mod, fn, (lambda o, n: lambda *a, **k: (lambda r: (print("handler", n, r), r)[1])(o(*a, **k)))(o, mod.__name__ + "." + fn))
        _w = g.walk_and_act
        g.walk_and_act = lambda goals, act: (print("walk_and_act", sorted(goals)[:6], act), _w(goals, act))[1]
    pygame.event.post(pygame.event.Event(pygame.MOUSEBUTTONDOWN, button=1, pos=pos))
    pygame.event.post(pygame.event.Event(pygame.MOUSEBUTTONUP, button=1, pos=pos))
    end = time.time() + 12
    while time.time() < end and not g.moon_petal.active:
        pump(1)
    sys.settrace(None)
    print("player now", g.player_xy(), "pos", pos, "tile", g.screen_to_tile(*pos))
    check("click on the door walks over and enters the inn", g.moon_petal.active)
    if shots and g.moon_petal.active:
        pygame.image.save(g.screen, os.path.join(shots, "door_click_entered.png"))
    g.moon_petal.leave() if hasattr(g.moon_petal, "leave") else setattr(g.moon_petal, "active", False)
    g.moon_petal.active = False
    pygame.mouse.get_pos = real

    # 4) walk north into the door from the stand tile
    place(*STAND)
    g._next_walk_at = 0
    g.try_move(0, -1) if hasattr(g, "try_move") else None
    pump(5)
    check("walking north into the door enters the inn", g.moon_petal.active)
    print("ALL PASSED" if not fails else f"{len(fails)} FAILED")
    T.stop_server() if hasattr(T, "stop_server") else None
    os._exit(1 if fails else 0)


if __name__ == "__main__":
    main()
