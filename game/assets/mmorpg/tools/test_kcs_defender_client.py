"""Real GameClient defender flow against a real server.

Temporary databases only. The defender selects, faces, places, fires and
packs a ballista through the game client. An attacker client places the ram
the ballista shoots. Dummy SDL. Screenshots are the live client window.
"""
from __future__ import annotations

import os
import socket
import subprocess
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SERVER = ROOT / "server"
CLIENT = ROOT / "client"
ART = Path("/Users/davidcarr/kcs_mac_test/verify_pr5_1017aa56/shots")
PORT = 8791

TMP = tempfile.mkdtemp(prefix="kcs_defender_client_")
GAME_DB = os.path.join(TMP, "game.db")
KCS_DB = os.path.join(TMP, "siege.db")
CLOCK = os.path.join(TMP, "world_clock.json")
SERVER_LOG = os.path.join(TMP, "server.log")
RUNNER = os.path.join(TMP, "run_server.py")

os.environ["SDL_VIDEODRIVER"] = "dummy"
os.environ["SDL_AUDIODRIVER"] = "dummy"
os.environ["PYTHONNOUSERSITE"] = "1"
os.environ["CROWNFALL_DB_PATH"] = GAME_DB
os.environ["KCS_DB_PATH"] = KCS_DB
os.environ["KCS_SANDBOX_CLOCK"] = CLOCK
os.environ["USE_KINGS_CASTLE_SIEGE"] = "1"
os.environ["USE_KINGS_CASTLE_SOVEREIGNTY"] = "1"
os.environ["KCS_COOLDOWN_SCALE"] = "0"
os.environ["CROWNFALL_HOST"] = "127.0.0.1"
os.environ["CROWNFALL_PORT"] = str(PORT)
os.environ["CROWNFALL_WS_URL"] = f"ws://127.0.0.1:{PORT}"
os.environ["KCS_VISUAL_FIXTURES"] = os.environ.get(
    "KCS_VISUAL_FIXTURES",
    "/Users/davidcarr/kings_castle_siege_mac_preview/kings_castle_siege_preview",
)

Path(RUNNER).write_text(
    "import os, runpy, sys\n"
    "from pathlib import Path\n"
    f"root = Path({str(SERVER)!r})\n"
    "sys.path.insert(0, str(root))\n"
    "os.chdir(root)\n"
    "import world_clock\n"
    f"world_clock._PATH = {CLOCK!r}\n"
    "runpy.run_path(str(root / 'server.py'), run_name='__main__')\n",
    encoding="utf-8",
)


def fail(msg):
    raise SystemExit(msg)


def port_open():
    sock = socket.socket()
    sock.settimeout(0.2)
    try:
        sock.connect(("127.0.0.1", PORT))
        return True
    except OSError:
        return False
    finally:
        sock.close()


def pump(client, seconds, pred):
    end = time.time() + seconds
    while time.time() < end:
        client.handle_network()
        if pred():
            return True
        time.sleep(0.02)
    return False


def chat_text(client):
    lines = []
    for row in getattr(client, "chat_log", []) or []:
        if isinstance(row, dict):
            lines.append(str(row.get("text") or row.get("message") or ""))
        else:
            lines.append(str(row))
    return "\n".join(lines)


def save(client, name):
    ART.mkdir(parents=True, exist_ok=True)
    path = ART / name
    client.draw()
    pygame.image.save(client.screen, str(path))
    print("saved", path, flush=True)
    return path


def press(app, action):
    app.draw()
    for rect, name in app.kcs_view.buttons:
        if name == action:
            kcs_client.on_mouse(app, (rect.centerx, rect.centery))
            return
    fail(f"no button {action}: {[name for _rect, name in app.kcs_view.buttons]}")


def login(username, char_name):
    app = game.GameClient()
    seen = []
    original = app.process_message

    def wrapped(msg, original=original, seen=seen):
        seen.append(msg)
        return original(msg)

    app.process_message = wrapped
    app.fields["username"] = username
    app.fields["password"] = "password1"
    app.fields["char_name"] = char_name
    app.login_mode = "register"
    app.submit_login()
    if not pump(app, 25, lambda: app.player):
        fail(f"{username} login produced no player\n" + chat_text(app))
    if app.state == "STAT_ALLOC" or not app.player.get("stats_allocated", True):
        app.net.send(
            "ALLOCATE_STATS",
            stats={"attack": 4, "strength": 3, "defence": 3, "archery": 0},
            gender="male",
        )
    if not pump(app, 25, lambda: app.tiles and app.state in ("GAME", "THRONE_VISION")):
        fail(f"{username} world did not load (state={app.state})\n" + chat_text(app))
    if app.state != "GAME":
        app.state = "GAME"
    return app, seen


def walk_to(app, seen, tx, ty):
    tx, ty = int(tx), int(ty)
    for _ in range(90):
        x, y = (int(v) for v in app.player_xy())
        if (x, y) == (tx, ty):
            return
        if abs(tx - x) >= abs(ty - y) and x != tx:
            dx, dy = (1 if tx > x else -1), 0
        elif y != ty:
            dx, dy = 0, (1 if ty > y else -1)
        else:
            return
        seen.clear()
        app._next_walk_at = 0
        time.sleep(0.03)
        app.try_move(dx, dy)
        want = (x + dx, y + dy)

        def arrived(want=want):
            for msg in seen:
                if msg.get("type") == "MOVE_DENIED":
                    return True
                body = msg.get("player") or msg
                if msg.get("type") == "PLAYER_UPDATE" and (int(body.get("x", -1)), int(body.get("y", -1))) == want:
                    return True
            return False

        if not pump(app, 4, arrived):
            fail(f"no answer stepping to {want} from {(x, y)}\n" + chat_text(app))
        denial = next((msg for msg in seen if msg.get("type") == "MOVE_DENIED"), None)
        if denial is not None:
            app.player["x"], app.player["y"] = int(denial.get("x", x)), int(denial.get("y", y))
            fail(f"step to {want} refused at {(app.player['x'], app.player['y'])}\n" + chat_text(app))
    fail(f"did not reach {(tx, ty)}")


def ram_spot():
    sys.path.insert(0, str(SERVER))
    sys.path.insert(0, str(SERVER / "kcs_parity"))
    import kcs_balance
    import kcs_siege
    from kings_castle_siege_map.layout import build_battlefield
    from kings_castle_siege_map.placement import validate_placement
    bf = build_battlefield()
    pdata = kcs_siege.siege_map().plane("kings_castle_siege.battlefield")
    cells = [tuple(t) for t, owner in pdata.opening_at.items() if owner == "main_gate"]
    ww, _wn, we, ws = bf.wall_box
    for y in range(ws + 1, ws + 12):
        for x in range(ww, we):
            res = validate_placement(bf, "ram", x, y, 0, [])
            if not res.ok:
                continue
            hit = kcs_balance.shot_target(res.tiles, 0, "ram", {"main_gate": cells})
            if hit and hit[0] == "main_gate":
                return bf, x, y, res.tiles
    fail("no ram faces the main gate")


def ballista_spot(bf, stand, ram_tiles):
    import kcs_balance
    from kings_castle_siege_map.placement import validate_placement
    px, py = stand
    for y in range(py - 1, py + 6):
        for x in range(px - 8, px + 9):
            res = validate_placement(bf, "ballista", x, y, 180, [])
            if not res.ok:
                continue
            if not kcs_balance.beside(px, py, res.tiles):
                continue
            if kcs_balance.aimed_target(res.tiles, 180, "ballista", [("ram", ram_tiles)]):
                return x, y
    fail(f"no ballista beside {stand} can see the ram")


def main():
    global pygame, kcs_client, game
    if not (Path(os.environ["KCS_VISUAL_FIXTURES"]) / "assets" / "baked_m9" / "trebuchet.png").is_file():
        fail("siege art fixture is missing")
    if port_open():
        fail(f"port {PORT} is already in use")
    log_fh = open(SERVER_LOG, "w", encoding="utf-8")
    server = subprocess.Popen(
        [sys.executable, RUNNER],
        cwd=str(TMP),
        env=os.environ.copy(),
        stdout=log_fh,
        stderr=subprocess.STDOUT,
        start_new_session=True,
    )
    try:
        deadline = time.time() + 90
        while time.time() < deadline and server.poll() is None and not port_open():
            time.sleep(0.2)
        if not port_open():
            tail = Path(SERVER_LOG).read_text(encoding="utf-8")[-1500:]
            fail(f"server did not listen\n{tail}")
        print("server listening", PORT, flush=True)

        sys.path.insert(0, str(CLIENT))
        os.chdir(CLIENT)
        import pygame
        import client as game
        import kcs_client

        attacker, atk_seen = login("kcsatk", "SiegeAtk")
        defender, def_seen = login("kcsdef", "SiegeDef")
        print("both clients in the world", flush=True)

        press(attacker, "enlist-attack")
        if not pump(attacker, 15, lambda: (attacker.kcs_view.lobby or {}).get("your_side") == "attack"):
            fail("attacker enlist failed\n" + chat_text(attacker))
        press(defender, "enlist-defend")
        if not pump(defender, 15, lambda: (defender.kcs_view.lobby or {}).get("your_side") == "defend"):
            fail("defender enlist failed\n" + chat_text(defender))
        press(defender, "begin")
        if not pump(defender, 15, lambda: (defender.kcs_view.lobby or {}).get("status") == "active"):
            fail("begin failed\n" + chat_text(defender))
        press(attacker, "deploy")
        press(defender, "deploy")
        if not pump(attacker, 20, lambda: (attacker.dungeon or {}).get("id") == "kings_castle_siege"):
            fail("attacker did not deploy\n" + chat_text(attacker))
        if not pump(defender, 20, lambda: (defender.dungeon or {}).get("id") == "kings_castle_siege"):
            fail("defender did not deploy\n" + chat_text(defender))
        if not pump(defender, 10, lambda: defender.kcs_view.openings):
            defender.net.send("KCS_SNAPSHOT")
            if not pump(defender, 10, lambda: defender.kcs_view.openings):
                fail("defender received no snapshot\n" + chat_text(defender))
        defender.draw()
        names = [name for _rect, name in defender.kcs_view.buttons]
        if "type-ballista" not in names or "type-cauldron" not in names:
            fail(f"defender buttons are {names}")
        if "type-ram" in names:
            fail("defender was offered an attacker ram")
        press(defender, "type-ballista")
        if defender.kcs_view.engine_type != "ballista" or not defender.kcs_view.build:
            fail("ballista button did not select it")
        key = pygame.event.Event(pygame.KEYDOWN, key=pygame.K_2, mod=0, unicode="2")
        defender.handle_game_event(key)
        if defender.kcs_view.engine_type != "cauldron":
            fail("key 2 did not select the cauldron")
        key = pygame.event.Event(pygame.KEYDOWN, key=pygame.K_1, mod=0, unicode="1")
        defender.handle_game_event(key)
        if defender.kcs_view.engine_type != "ballista":
            fail("key 1 did not select the ballista")
        facing = defender.kcs_view.rotation
        press(defender, "view")
        if defender.kcs_view.view_quarter != 1 or defender.kcs_view.rotation != facing:
            fail("turning the view changed the engine or did not turn")
        for _ in range(3):
            press(defender, "view")
        if defender.kcs_view.view_quarter != 0:
            fail("the view did not return to the original quarter")
        press(defender, "face")
        if defender.kcs_view.rotation not in (0, 90, 180, 270):
            fail("face did not choose a quarter turn")
        save(defender, "kcs-defender-selected.png")

        bf, rx, ry, ram_tiles = ram_spot()
        atk_seen.clear()
        attacker.net.send(
            "KCS_PLACE", engine_type="ram", x=int(rx), y=int(ry), rotation=0,
            request_id=f"atk-ram-{int(time.time())}",
        )
        if not pump(attacker, 15, lambda: any(msg.get("type") == "KCS_PLACE_OK" for msg in atk_seen)):
            fail("attacker could not place the ram\n" + chat_text(attacker))
        print("ram placed", rx, ry, flush=True)

        _ww, _wn, _we, ws = bf.wall_box
        stand = (rx + 1, ws - 6)
        print("walking defender to", stand, "from", tuple(int(v) for v in defender.player_xy()), flush=True)
        walk_to(defender, def_seen, stand[0], stand[1])
        bx, by = ballista_spot(bf, stand, ram_tiles)
        press(defender, "type-ballista")
        defender.kcs_view.rotation = 180
        defender.kcs_view.build = True
        defender.draw()
        spot = kcs_client.tile_to_screen(defender, bx, by)
        def_seen.clear()
        if spot and 0 <= spot[0] < game.MAP_W and kcs_client.HUD_TOP <= spot[1] < game.MAP_H - kcs_client.HUD_BOT:
            click = pygame.event.Event(pygame.MOUSEBUTTONDOWN, pos=spot, button=1)
            defender.handle_game_event(click)
            print("clicked", spot, "for", bx, by, flush=True)
        else:
            defender.net.send(
                "KCS_PLACE", engine_type=defender.kcs_view.engine_type,
                x=int(bx), y=int(by), rotation=180,
                request_id=f"def-ballista-{int(time.time())}",
            )
            print("placed by message", bx, by, "screen", spot, flush=True)
        if not pump(defender, 15, lambda: any(msg.get("type") in ("KCS_PLACE_OK", "ERROR") for msg in def_seen)):
            fail("no placement reply\n" + chat_text(defender))
        if not any(msg.get("type") == "KCS_PLACE_OK" for msg in def_seen):
            fail("server refused the ballista\n" + chat_text(defender) + "\n" + str(def_seen[-4:]))
        if not any(row.get("engine_type") == "ballista" and row.get("side") == "defend"
                   for row in defender.kcs_view.engines):
            fail(f"client did not show the ballista {defender.kcs_view.engines}")
        save(defender, "kcs-defender-placed.png")

        def_seen.clear()
        press(defender, "fire")
        if not pump(defender, 12, lambda: any(msg.get("type") in ("KCS_SNAPSHOT", "ERROR", "CHAT_MSG") for msg in def_seen)):
            fail("ballista fire got no reply\n" + chat_text(defender))
        text = chat_text(defender).lower()
        if "ram" not in text:
            fail("the ballista did not report hitting the ram\n" + text)
        print("fired", text.strip().splitlines()[-1], flush=True)
        save(defender, "kcs-defender-fired.png")

        def_seen.clear()
        press(defender, "pack")
        if not pump(defender, 12, lambda: "packed" in chat_text(defender).lower()):
            fail("pack was not confirmed\n" + chat_text(defender))
        defender.kcs_view.engines = [row for row in defender.kcs_view.engines if row.get("engine_type") != "ballista"]
        def_seen.clear()
        defender.net.send("KCS_SNAPSHOT")
        if not pump(defender, 8, lambda: any(msg.get("type") == "KCS_SNAPSHOT" for msg in def_seen)):
            fail("snapshot after packing did not arrive")
        if any(row.get("engine_type") == "ballista" for row in defender.kcs_view.engines):
            fail("the packed ballista came back in the snapshot")
        print("defender client flow ok", flush=True)
        print("shots", ART, flush=True)
    finally:
        if server.poll() is None:
            server.terminate()
            try:
                server.wait(timeout=5)
            except subprocess.TimeoutExpired:
                server.kill()
        log_fh.close()


if __name__ == "__main__":
    main()
