"""Real GameClient against a real server, on temporary databases.

Dummy SDL display. Screenshots are the live client window, not a standalone
renderer. The siege flag is on only in this process.
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
ART = Path("/opt/cursor/artifacts")
PORT = 8779

TMP = tempfile.mkdtemp(prefix="kcs_client_smoke_")
GAME_DB = os.path.join(TMP, "game.db")
KCS_DB = os.path.join(TMP, "siege.db")
SERVER_LOG = os.path.join(TMP, "server.log")

os.environ["SDL_VIDEODRIVER"] = "dummy"
os.environ["SDL_AUDIODRIVER"] = "dummy"
os.environ["CROWNFALL_DB_PATH"] = GAME_DB
os.environ["KCS_DB_PATH"] = KCS_DB
os.environ["USE_KINGS_CASTLE_SIEGE"] = "1"
os.environ["CROWNFALL_HOST"] = "127.0.0.1"
os.environ["CROWNFALL_PORT"] = str(PORT)
os.environ["CROWNFALL_WS_URL"] = f"ws://127.0.0.1:{PORT}"
os.environ["KCS_VISUAL_FIXTURES"] = os.environ.get("KCS_VISUAL_FIXTURES", "/tmp/kcs_visual_fixtures")


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
            lines.append(str(row.get("text") or ""))
        else:
            lines.append(str(row))
    return "\n".join(lines)


def save(client, name):
    ART.mkdir(parents=True, exist_ok=True)
    path = ART / name
    client.draw()
    pygame.image.save(client.screen, str(path))
    print("saved", path, "render_ms", getattr(getattr(client, "kcs_view", None), "last_ms", None))
    return path


def valid_trebuchet(px, py):
    sys.path.insert(0, str(SERVER / "kcs_parity"))
    from kings_castle_siege_map.layout import build_battlefield
    from kings_castle_siege_map.placement import find_valid_on_side, validate_placement
    bf = build_battlefield()
    best = None
    best_dist = 10 ** 9
    for y in range(max(2, py - 30), min(bf.plane.height - 2, py + 30), 2):
        for x in range(max(2, px - 30), min(bf.plane.width - 2, px + 30), 2):
            res = validate_placement(bf, "trebuchet", x, y, 0, [])
            if not res.ok:
                continue
            dist = abs(x - px) + abs(y - py)
            if dist < best_dist:
                best = (x, y, 0)
                best_dist = dist
    if best:
        return best
    found = find_valid_on_side(bf, "trebuchet", "south", [], 0)
    if not found:
        fail("no valid trebuchet tile")
    return found


def stamp(path):
    """Size and mtime only. Do not open the file."""
    if not path.exists():
        return None
    st = path.stat()
    return (st.st_size, st.st_mtime_ns)


def press(app, action):
    app.draw()
    for rect, name in app.kcs_view.buttons:
        if name == action:
            kcs_client.on_mouse(app, (rect.centerx, rect.centery))
            return
    fail(f"no button {action}")


def main():
    global pygame, kcs_client
    if not (Path(os.environ["KCS_VISUAL_FIXTURES"]) / "assets" / "baked_m9" / "gatehouse.png").is_file():
        fail("siege art fixture is missing")
    before_world = stamp(SERVER / "world.db")
    before_kcs = stamp(SERVER / "kcs_siege.db")

    log_fh = open(SERVER_LOG, "w", encoding="utf-8")
    server = subprocess.Popen(
        [sys.executable, str(SERVER / "server.py")],
        cwd=str(SERVER),
        env=os.environ.copy(),
        stdout=log_fh,
        stderr=subprocess.STDOUT,
        start_new_session=True,
    )
    try:
        deadline = time.time() + 120
        while time.time() < deadline and server.poll() is None and not port_open():
            time.sleep(0.2)
        if not port_open():
            tail = Path(SERVER_LOG).read_text(encoding="utf-8")[-1200:]
            fail(f"server did not listen\n{tail}")

        sys.path.insert(0, str(CLIENT))
        os.chdir(CLIENT)
        import pygame
        import client as game
        import kcs_client

        app = game.GameClient()
        seen = []
        original = app.process_message

        def wrapped(msg):
            seen.append(msg)
            return original(msg)

        app.process_message = wrapped
        app.fields["username"] = "kcspilot"
        app.fields["password"] = "password1"
        app.fields["char_name"] = "SiegePilot"
        app.login_mode = "register"
        print("client up, logging in", flush=True)
        app.submit_login()
        if not pump(app, 20, lambda: app.player):
            fail("login produced no player\n" + chat_text(app) + "\n" + Path(SERVER_LOG).read_text(encoding="utf-8")[-800:])
        if app.state == "STAT_ALLOC" or not app.player.get("stats_allocated", True):
            app.net.send(
                "ALLOCATE_STATS",
                stats={"attack": 4, "strength": 3, "defence": 3, "archery": 0},
                gender="male",
            )
        if not pump(app, 20, lambda: app.tiles and app.state in ("GAME", "THRONE_VISION")):
            fail(f"world did not load (state={app.state})\n" + chat_text(app))
        if app.state != "GAME":
            app.state = "GAME"
        print("world loaded, drawing overworld", flush=True)
        save(app, "kcs-client-overworld.png")
        if app.dungeon and app.dungeon.get("id") == "kings_castle_siege":
            fail("overworld frame is already the siege")

        press(app, "enlist-attack")
        if not pump(app, 15, lambda: (getattr(app, "kcs_view", None) and (app.kcs_view.lobby or {}).get("your_side") == "attack")):
            fail("enlist did not stick\n" + chat_text(app) + "\n" + Path(SERVER_LOG).read_text(encoding="utf-8")[-800:])
        press(app, "begin")
        if not pump(app, 15, lambda: (app.kcs_view.lobby or {}).get("status") == "active"):
            fail("begin did not go live\n" + chat_text(app))
        press(app, "deploy")
        print("deploying", flush=True)
        if not pump(app, 20, lambda: (app.dungeon or {}).get("id") == "kings_castle_siege"):
            fail("F8 did not deploy\n" + chat_text(app) + "\n" + Path(SERVER_LOG).read_text(encoding="utf-8")[-800:])
        if not pump(app, 10, lambda: (getattr(app, "kcs_view", None) and app.kcs_view.openings)):
            app.net.send("KCS_SNAPSHOT")
            if not pump(app, 10, lambda: app.kcs_view and app.kcs_view.openings):
                fail("no siege snapshot\n" + chat_text(app))
        print("drawing siege", flush=True)
        join_path = save(app, "kcs-client-join.png")
        for kind in ("ram", "trebuchet", "siege_tower", "ladder"):
            press(app, f"type-{kind}")
            if app.kcs_view.engine_type != kind or not app.kcs_view.build:
                fail(f"button did not select {kind}")
        key = pygame.event.Event(pygame.KEYDOWN, key=pygame.K_2, mod=0, unicode="2")
        app.handle_game_event(key)
        if app.kcs_view.engine_type != "trebuchet":
            fail("key 2 did not select the trebuchet")
        press(app, "rotate")
        if app.kcs_view.rotation != 90:
            fail(f"rotate did not turn the engine ({app.kcs_view.rotation})")
        press(app, "type-ram")
        press(app, "face")
        print("selected", app.kcs_view.engine_type, "facing", app.kcs_view.rotation, flush=True)
        save(app, "kcs-e2e-select.png")
        openings_before = [(row.get("id"), row.get("state")) for row in app.kcs_view.openings]

        start = app.player_xy()
        moved = None
        for dx, dy in ((0, 1), (0, -1), (1, 0), (-1, 0)):
            seen.clear()
            before = tuple(int(v) for v in app.player_xy())
            app.try_move(dx, dy)
            def accepted(before=before, dx=dx, dy=dy):
                for msg in seen:
                    if msg.get("type") == "MOVE_DENIED":
                        return True
                    if msg.get("type") == "PLAYER_UPDATE":
                        body = msg.get("player") or msg
                        if int(body.get("x", -1)) == before[0] + dx and int(body.get("y", -1)) == before[1] + dy:
                            return True
                return False
            pump(app, 3, accepted)
            denied = any(msg.get("type") == "MOVE_DENIED" for msg in seen)
            confirmed = any(
                msg.get("type") == "PLAYER_UPDATE"
                and int((msg.get("player") or msg).get("x", -1)) == before[0] + dx
                and int((msg.get("player") or msg).get("y", -1)) == before[1] + dy
                for msg in seen
            )
            if confirmed and not denied:
                moved = (before[0] + dx, before[1] + dy)
                break
            app._next_walk_at = 0
        if moved is None:
            fail(f"no server-confirmed step from {start}\n" + chat_text(app))
        print("moved", start, "->", moved)

        px, py = (int(v) for v in app.player_xy())
        pid = int(app.player["id"])
        tx, ty, rot = valid_trebuchet(px, py)
        app.kcs_view.build = True
        app.kcs_view.engine_type = "trebuchet"
        app.kcs_view.rotation = rot
        app.draw()
        spot = kcs_client.tile_to_screen(app, tx, ty)
        seen.clear()
        if spot and 0 <= spot[0] < game.MAP_W and kcs_client.HUD_TOP <= spot[1] < game.MAP_H - kcs_client.HUD_BOT:
            click = pygame.event.Event(pygame.MOUSEBUTTONDOWN, pos=spot, button=1)
            app.handle_game_event(click)
            print("clicked", spot, "tile", (tx, ty))
        else:
            app.kcs_view.request_n += 1
            app.net.send(
                "KCS_PLACE",
                engine_type="trebuchet",
                x=int(tx),
                y=int(ty),
                rotation=int(rot),
                request_id=f"smoke-{pid}-{int(time.time())}",
            )
            print("place message tile", (tx, ty), "offscreen", spot)

        def placed():
            return any(msg.get("type") == "KCS_PLACE_OK" for msg in seen) or any(
                str(msg.get("message") or "").startswith("That placement") or msg.get("type") == "ERROR"
                for msg in seen
            )
        if not pump(app, 15, placed):
            fail("no placement reply\n" + chat_text(app))
        if not any(msg.get("type") == "KCS_PLACE_OK" for msg in seen):
            fail("server refused the engine\n" + chat_text(app))
        if not any(row.get("engine_type") == "trebuchet" for row in app.kcs_view.engines):
            fail("client did not apply the engine")
        save(app, "kcs-client-place.png")

        seen.clear()
        app.net.send("KCS_OPENING", opening_id="main_gate", state="destroyed")
        if not pump(app, 8, lambda: any(msg.get("type") == "ERROR" for msg in seen)):
            fail("structure order got no refusal")
        refusal = " ".join(str(msg.get("message") or "") for msg in seen if msg.get("type") == "ERROR")
        if "structure" not in refusal.lower():
            fail("unexpected structure reply: " + refusal)
        openings_after = [(row.get("id"), row.get("state")) for row in app.kcs_view.openings]
        if openings_after != openings_before:
            fail(f"client openings changed {openings_before} -> {openings_after}")

        engines = list(app.kcs_view.engines)
        app.kcs_view.engines = []
        seen.clear()
        app.net.send("KCS_SNAPSHOT")
        if not pump(app, 8, lambda: any(msg.get("type") == "KCS_SNAPSHOT" for msg in seen)):
            fail("snapshot refresh missing")
        if not any(row.get("engine_type") == "trebuchet" for row in app.kcs_view.engines):
            fail("snapshot did not restore the engine")
        print("snapshot restored", len(engines), "engine(s)")
        print("join", join_path)
        if stamp(SERVER / "world.db") != before_world or stamp(SERVER / "kcs_siege.db") != before_kcs:
            fail("a preexisting live database changed, or one was created in the server folder")
        print("kcs client smoke ok")
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
