"""Two real clients share a placed ram and see each other only when nearby.

Temporary databases. Dummy SDL. Refuses ports 8765 and 8789.
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
PORT = 8793

TMP = tempfile.mkdtemp(prefix="kcs_sync_client_")
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
os.environ["KCS_COOLDOWN_SCALE"] = "0"
os.environ["KCS_WAR_SECONDS"] = "1200"
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


def port_open(port):
    sock = socket.socket()
    sock.settimeout(0.2)
    try:
        sock.connect(("127.0.0.1", port))
        return True
    except OSError:
        return False
    finally:
        sock.close()


def pump(client, seconds, pred):
    end = time.time() + seconds
    while time.time() < end:
        client.handle_network()
        client.draw()
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


def login(username, char_name):
    app = game.GameClient()
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
        fail(f"{username} world did not load (state={app.state})")
    if app.state != "GAME":
        app.state = "GAME"
    return app


def press(app, action):
    app.draw()
    for rect, name in app.kcs_view.buttons:
        if name == action:
            kcs_client.on_mouse(app, (rect.centerx, rect.centery))
            return
    fail(f"no button {action}")


def ram_spot():
    sys.path.insert(0, str(SERVER))
    sys.path.insert(0, str(SERVER / "kcs_parity"))
    from kings_castle_siege_map.layout import build_battlefield
    from kings_castle_siege_map.placement import validate_placement
    bf = build_battlefield()
    for y in range(150, 210):
        for x in range(80, 180):
            res = validate_placement(bf, "ram", x, y, 0, [])
            if res.ok:
                return x, y
    fail("no ram tile")


def main():
    global pygame, kcs_client, game
    if PORT in (8765, 8789):
        fail("refusing live or sandbox port")
    if port_open(PORT):
        fail(f"port {PORT} is already in use")
    proc = subprocess.Popen(
        [sys.executable, RUNNER],
        cwd=str(SERVER),
        stdout=open(SERVER_LOG, "w"),
        stderr=subprocess.STDOUT,
    )
    try:
        for _ in range(50):
            if port_open(PORT):
                break
            if proc.poll() is not None:
                fail("server exited\n" + Path(SERVER_LOG).read_text()[-2000:])
            time.sleep(0.2)
        else:
            fail("server did not listen\n" + Path(SERVER_LOG).read_text()[-2000:])

        sys.path.insert(0, str(CLIENT))
        os.environ["SDL_VIDEODRIVER"] = "dummy"
        import pygame  # noqa: F401
        import client as game
        import kcs_client

        attacker = login("syncatk", "SyncAtk")
        defender = login("syncdef", "SyncDef")
        press(attacker, "enlist-attack")
        if not pump(attacker, 10, lambda: (attacker.kcs_view.status or {}).get("attack_enlisted", 0) >= 1):
            fail("attacker did not enlist\n" + chat_text(attacker))
        press(defender, "enlist-defend")
        if not pump(defender, 10, lambda: (defender.kcs_view.status or {}).get("defend_enlisted", 0) >= 1):
            fail("defender did not enlist\n" + chat_text(defender))
        press(attacker, "begin")
        if not pump(attacker, 10, lambda: (attacker.kcs_view.status or {}).get("status") == "active"
                    or "active" in chat_text(attacker).lower()):
            fail("begin did not start the siege\n" + chat_text(attacker))
        press(attacker, "deploy")
        press(defender, "deploy")
        if not pump(attacker, 15, lambda: kcs_client.active(attacker) and attacker.kcs_view.sync_seq is not None):
            fail("attacker did not get a siege snapshot\n" + chat_text(attacker))
        if not pump(defender, 15, lambda: kcs_client.active(defender) and defender.kcs_view.sync_seq is not None):
            fail("defender did not get a siege snapshot\n" + chat_text(defender))

        bx, by = ram_spot()
        attacker.kcs_view.engine_type = "ram"
        attacker.kcs_view.rotation = 0
        attacker.kcs_view.build = True
        kcs_client._place(attacker, bx, by)
        if not pump(attacker, 12, lambda: any(row.get("engine_type") == "ram" for row in attacker.kcs_view.engines)):
            fail("attacker did not show the ram\n" + chat_text(attacker))
        if not pump(defender, 12, lambda: any(row.get("engine_type") == "ram" for row in defender.kcs_view.engines)):
            fail(f"defender did not see the ram {defender.kcs_view.engines}")
        ram = next(row for row in defender.kcs_view.engines if row.get("engine_type") == "ram")
        if ram.get("side") != "attack":
            fail(f"defender saw the wrong side {ram}")
        if not isinstance(ram.get("rotation"), int):
            fail(f"defender did not see the ram facing {ram}")

        pump(attacker, 2.0, lambda: False)
        pump(defender, 0.2, lambda: False)
        ax = (attacker.player or {}).get("x")
        ay = (attacker.player or {}).get("y")
        seen = defender.players.get((attacker.player or {}).get("id"))
        dist = None if seen is None else max(abs(int(seen["x"]) - int(defender.player["x"])), abs(int(seen["y"]) - int(defender.player["y"])))
        if dist is not None and dist <= 24:
            if seen.get("kcs_side") != "attack":
                fail(f"nearby attacker side was {seen.get('kcs_side')}")
            if seen.get("hp") is None:
                fail("nearby attacker had no hit points")
        elif seen is not None and dist is not None and dist > 24:
            fail(f"defender saw an attacker {dist} tiles away")
        print("shared ram", ram.get("engine_id"), "facing", ram.get("rotation"),
              "attacker tile", ax, ay, "defender sees", None if seen is None else (seen.get("x"), seen.get("y"), dist),
              flush=True)

        defender.kcs_view.stale = True
        defender.kcs_view.sync_seq = None
        kcs_client._button(defender, "fire")
        if "paused" not in (defender.kcs_view.notice or "").lower() and "paused" not in (defender.kcs_view.error or "").lower():
            fail(f"stale client did not pause: {defender.kcs_view.notice}")
        ART.mkdir(parents=True, exist_ok=True)
        defender.draw()
        shot = ART / "kcs-sync-shared.png"
        pygame.image.save(defender.screen, str(shot))
        print("saved", shot, flush=True)
        print("sync client ok", flush=True)
        attacker.net.send("LOGOUT")
        defender.net.send("LOGOUT")
        time.sleep(0.5)
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()


if __name__ == "__main__":
    if port_open(8765):
        print("note: live port 8765 is open and was not used", flush=True)
    if port_open(8789):
        print("note: sandbox port 8789 is open and was not used", flush=True)
    main()
