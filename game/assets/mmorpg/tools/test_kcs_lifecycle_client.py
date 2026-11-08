"""Real client: battle panel, a throne claim, the crown, and a sandbox registration.

Temporary databases only. Dummy SDL. Refuses ports 8765 and 8789.
"""
from __future__ import annotations

import os
import socket
import subprocess
import sys
import tempfile
import time
from collections import deque
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SERVER = ROOT / "server"
CLIENT = ROOT / "client"
ART = Path("/Users/davidcarr/kcs_mac_test/verify_pr5_1017aa56/shots")
PORT = 8792

TMP = tempfile.mkdtemp(prefix="kcs_lifecycle_client_")
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
os.environ["KCS_SANDBOX_PREP"] = "1"
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


def login(username, char_name, mode="register"):
    app = game.GameClient()
    app.fields["username"] = username
    app.fields["password"] = "password1"
    app.fields["char_name"] = char_name
    app.login_mode = mode
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
    app._seen = []
    original = app.process_message

    def wrapped(msg, original=original, app=app):
        app._seen.append(msg)
        return original(msg)

    app.process_message = wrapped
    return app


def opening(app, oid):
    for row in app.kcs_view.openings:
        if row.get("id") == oid:
            return row
    return None


def states_of(app):
    found = {}
    for row in app.kcs_view.openings:
        if row.get("id"):
            found[row["id"]] = row.get("state") or "intact"
    return found


def step(app, dx, dy):
    x, y = (int(v) for v in app.player_xy())
    app._seen.clear()
    app._next_walk_at = 0
    time.sleep(0.02)
    app.try_move(dx, dy)
    want = (x + dx, y + dy)

    def arrived():
        for msg in app._seen:
            if msg.get("type") == "MOVE_DENIED":
                return True
            if msg.get("type") == "DUNGEON_ENTER":
                return True
            if msg.get("type") == "PLAYER_UPDATE":
                body = msg.get("player") or msg
                try:
                    if (int(body.get("x")), int(body.get("y"))) == want:
                        return True
                except (TypeError, ValueError):
                    continue
        return False

    if not pump(app, 4, arrived):
        fail(f"no answer stepping to {want} from {(x, y)}\n" + chat_text(app))
    if (app.dungeon or {}).get("plane") == "kings_castle_siege.throne_room":
        return
    denial = next((msg for msg in app._seen if msg.get("type") == "MOVE_DENIED"), None)
    if denial is not None:
        fail(f"step to {want} refused at {app.player_xy()}\n" + chat_text(app))
    px, py = (int(v) for v in app.player_xy())
    if (px, py) != want:
        fail(f"step to {want} landed at {(px, py)}\n" + chat_text(app))


def map_walkable(bf, x, y, states):
    from kings_castle_siege_map.layout import walkable
    return walkable(bf, x, y, states)


def route_siege(plane_id, start, goals, states, blocked):
    import kcs_siege
    smap = kcs_siege.siege_map()
    goals = set(goals)
    prev = {start: None}
    q = deque([start])
    found = start if start in goals else None
    while q and found is None:
        x, y = q.popleft()
        for nx, ny in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)):
            nxt = (nx, ny)
            if nxt in prev or nxt in blocked:
                continue
            if not smap.walkable(plane_id, nx, ny, states):
                continue
            prev[nxt] = (x, y)
            if nxt in goals:
                found = nxt
                break
            q.append(nxt)
    if found is None:
        return None
    path = [found]
    cur = prev[found]
    while cur is not None:
        path.append(cur)
        cur = prev[cur]
    path.reverse()
    return path


def route_map(bf, start, goals, states, blocked):
    goals = set(goals)
    prev = {start: None}
    q = deque([start])
    found = None
    while q:
        x, y = q.popleft()
        for nx, ny in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)):
            nxt = (nx, ny)
            if nxt in prev or nxt in blocked:
                continue
            if not map_walkable(bf, nx, ny, states):
                continue
            prev[nxt] = (x, y)
            if nxt in goals:
                found = nxt
                break
            q.append(nxt)
        if found:
            break
    if found is None:
        return None
    path = [found]
    cur = prev[found]
    while cur is not None:
        path.append(cur)
        cur = prev[cur]
    path.reverse()
    return path


def blocked_tiles(app):
    tiles = set()
    for row in app.kcs_view.engines:
        if row.get("engine_type") in ("ladder", "siege_tower"):
            continue
        for pair in row.get("tiles") or []:
            try:
                tiles.add((int(pair[0]), int(pair[1])))
            except (TypeError, ValueError, IndexError):
                continue
    return tiles


def opening_cells():
    import kcs_siege
    pdata = kcs_siege.siege_map().plane("kings_castle_siege.battlefield")
    found = {}
    for tile, owner in pdata.opening_at.items():
        found.setdefault(owner, []).append(tuple(tile))
    return found


def find_shot(kind, opening, skip=()):
    """A placement whose nearest living opening is ``opening``, not a nearer gate."""
    import kcs_balance
    from kings_castle_siege_map.layout import build_battlefield
    from kings_castle_siege_map.placement import validate_placement
    bf = build_battlefield()
    cells = {oid: tiles for oid, tiles in opening_cells().items() if oid not in skip}
    ww, wn, we, ws = bf.wall_box
    bands = (
        (0, range(ww - 8, we + 8), range(ws + 1, min(bf.plane.height - 2, ws + 40))),
        (180, range(ww - 8, we + 8), range(max(2, wn - 40), wn)),
        (90, range(max(2, ww - 40), ww), range(wn + 4, ws - 4)),
        (270, range(we + 1, min(bf.plane.width - 2, we + 40)), range(wn + 4, ws - 4)),
    )
    for rot, xs, ys in bands:
        for y in ys:
            for x in xs:
                res = validate_placement(bf, kind, x, y, rot, [])
                if not res.ok:
                    continue
                hit = kcs_balance.shot_target(res.tiles, rot, kind, cells)
                if hit and hit[0] == opening:
                    return x, y, rot
    fail(f"no {kind} has {opening} as its nearest opening")


def place(app, kind, x, y, rot, key):
    app.net.send("KCS_PLACE", engine_type=kind, x=int(x), y=int(y), rotation=int(rot), request_id=key)
    if not pump(app, 12, lambda: any(row.get("engine_type") == kind for row in app.kcs_view.engines)
            or "cannot" in chat_text(app).lower() or "not valid" in chat_text(app).lower()):
        fail(f"no placement reply for {kind}\n" + chat_text(app))
    if not any(row.get("engine_type") == kind for row in app.kcs_view.engines):
        fail(f"server refused the {kind}\n" + chat_text(app))


def bombard(app, kind, oid, limit=48):
    """Fire until that opening is gone. Nearer gates in front of it fall first."""
    app.kcs_view.engine_type = kind
    for _ in range(limit):
        row = opening(app, oid) or {}
        if row.get("state") == "destroyed" or int(row.get("hp") or 1) <= 0:
            return
        mark = len(chat_text(app))
        app.net.send("KCS_ACT", engine_type=kind)

        def grew(mark=mark):
            return len(chat_text(app)) > mark

        if not pump(app, 8, grew):
            fail(f"{kind} got no reply while shooting {oid}\n" + chat_text(app))
    row = opening(app, oid)
    fail(f"{oid} is still {None if row is None else row.get('state')} after {limit} shots\n" + chat_text(app))


def shoot_until(app, kind, oid):
    app.kcs_view.engine_type = kind
    for _ in range(12):
        row = opening(app, oid) or {}
        if row.get("state") == "destroyed" or int(row.get("hp") or 1) <= 0:
            return
        before = (row.get("hp"), row.get("state"))
        app.net.send("KCS_ACT", engine_type=kind)

        def changed(before=before, oid=oid):
            nxt = opening(app, oid) or {}
            return (nxt.get("hp"), nxt.get("state")) != before or "error" in chat_text(app).lower()

        if not pump(app, 8, changed):
            fail(f"{kind} shot at {oid} got no reply\n" + chat_text(app))
        if "cannot" in chat_text(app).lower() and (opening(app, oid) or {}).get("state") != "destroyed":
            fail(f"{kind} could not fire at {oid}\n" + chat_text(app))
    row = opening(app, oid)
    if not row or row.get("state") != "destroyed":
        fail(f"{oid} is still {None if row is None else row.get('state')} hp={None if row is None else row.get('hp')}\n" + chat_text(app))


def main():
    global pygame, kcs_client, game
    if PORT in (8765, 8789):
        fail("refusing the live and sandbox ports")
    if port_open(8765) or port_open(8789):
        print("note: 8765 or 8789 is in use; this test will not connect to them", flush=True)
    if port_open(PORT):
        fail(f"port {PORT} is already in use")
    if not (Path(os.environ["KCS_VISUAL_FIXTURES"]) / "assets" / "baked_m9" / "trebuchet.png").is_file():
        fail("siege art fixture is missing")
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
        while time.time() < deadline and server.poll() is None and not port_open(PORT):
            time.sleep(0.2)
        if not port_open(PORT):
            fail("server did not listen\n" + Path(SERVER_LOG).read_text(encoding="utf-8")[-1500:])
        print("server listening", PORT, flush=True)
        sys.path.insert(0, str(CLIENT))
        sys.path.insert(0, str(SERVER))
        sys.path.insert(0, str(SERVER / "kcs_parity"))
        os.chdir(CLIENT)
        import pygame
        import client as game
        import kcs_client

        attacker = login("kcsatk", "SiegeAtk")
        defender = login("kcsdef", "SiegeDef")
        press(attacker, "enlist-attack")
        if not pump(attacker, 12, lambda: (attacker.kcs_view.status or {}).get("your_side") == "attack"):
            fail("attacker enlist failed\n" + chat_text(attacker))
        press(defender, "enlist-defend")
        if not pump(defender, 12, lambda: (defender.kcs_view.status or {}).get("your_side") == "defend"):
            fail("defender enlist failed\n" + chat_text(defender))
        reg = attacker.kcs_view.status or {}
        if reg.get("phase") != "Registration":
            fail(f"registration panel is {reg.get('phase')}")
        if "not an elimination" not in (reg.get("grace_rule") or ""):
            fail("the registration panel does not explain the grace")
        if any(name == "prep" for _r, name in attacker.kcs_view.buttons):
            # Registration may show the sandbox button. It must say sandbox.
            attacker.draw()
            labels = [name for _r, name in attacker.kcs_view.buttons]
            if "prep" not in labels:
                fail("sandbox button missing its action")
        press(defender, "begin")
        if not pump(attacker, 12, lambda: (attacker.kcs_view.status or {}).get("status") == "active"):
            attacker.net.send("KCS_BEGIN")
            if not pump(attacker, 12, lambda: (attacker.kcs_view.status or {}).get("status") == "active"):
                fail("begin failed\n" + chat_text(attacker) + "\n" + chat_text(defender))
        battle = attacker.kcs_view.status or {}
        if battle.get("phase") != "Battle":
            fail(f"battle panel is {battle.get('phase')}")
        if not isinstance(battle.get("remaining"), int):
            fail("the battle panel has no remaining time")
        attacker.draw()
        if "prep" in [name for _r, name in attacker.kcs_view.buttons]:
            fail("the sandbox prepare button is shown during a battle")
        press(attacker, "deploy")
        if not pump(attacker, 15, lambda: (attacker.dungeon or {}).get("id") == "kings_castle_siege"):
            fail("attacker did not deploy\n" + chat_text(attacker))
        if not pump(attacker, 10, lambda: attacker.kcs_view.openings):
            attacker.net.send("KCS_SNAPSHOT")
            if not pump(attacker, 8, lambda: attacker.kcs_view.openings):
                fail("no siege snapshot\n" + chat_text(attacker))
        save(attacker, "kcs-lifecycle-battle.png")
        print("battle panel", battle.get("phase"), battle.get("remaining"), flush=True)

        rx, ry, rot = find_shot("ram", "main_gate")
        place(attacker, "ram", rx, ry, rot, "life-ram")
        shoot_until(attacker, "ram", "main_gate")
        print("main gate breached", flush=True)
        others = tuple(oid for oid in opening_cells() if oid != "keep_doors")
        tx, ty, trot = find_shot("trebuchet", "keep_doors", skip=others)
        place(attacker, "trebuchet", tx, ty, trot, "life-treb")
        bombard(attacker, "trebuchet", "keep_doors")
        print("keep doors breached", flush=True)

        from kings_castle_siege_map.layout import build_battlefield
        import kcs_siege
        bf = build_battlefield().plane
        door = kcs_siege.siege_map().plane("kings_castle_siege.battlefield").opening_rects["keep_doors"]
        goals = [(x, y) for x in range(int(door[0]), int(door[2]) + 1)
                 for y in range(int(door[1]), int(door[3]) + 1)]
        start = tuple(int(v) for v in attacker.player_xy())
        path = route_map(bf, start, goals, states_of(attacker), blocked_tiles(attacker))
        if not path:
            fail(f"no walk from {start} to the keep doors")
        print("walking", len(path) - 1, "tiles to the keep", flush=True)
        for tx, ty in path[1:]:
            if (attacker.dungeon or {}).get("plane") == "kings_castle_siege.throne_room":
                break
            px, py = (int(v) for v in attacker.player_xy())
            step(attacker, tx - px, ty - py)
        if (attacker.dungeon or {}).get("plane") != "kings_castle_siege.throne_room":
            fail(f"still on {(attacker.dungeon or {}).get('plane')} at {attacker.player_xy()}")
        print("in the throne room at", tuple(int(v) for v in attacker.player_xy()), flush=True)
        throne = kcs_siege.siege_map().plane(kcs_siege.PLANE_THRONE)
        dais = tuple(int(v) for v in throne.spawn["dais"])
        here = tuple(int(v) for v in attacker.player_xy())
        door_back = throne.opening_rects.get("throne_doors")
        avoid = set()
        if door_back:
            avoid = {(x, int(door_back[3])) for x in range(int(door_back[0]), int(door_back[2]) + 1)}
            avoid.discard(here)
        near = [(x, y) for x in range(dais[0] - 8, dais[0] + 9) for y in range(dais[1] - 8, dais[1] + 9)
                if max(abs(x - dais[0]), abs(y - dais[1])) <= 8]
        inner = route_siege(kcs_siege.PLANE_THRONE, here, near, states_of(attacker), avoid)
        if not inner:
            fail(f"no walk from {here} to the dais {dais}")
        for tx, ty in inner[1:]:
            px, py = (int(v) for v in attacker.player_xy())
            if max(abs(px - dais[0]), abs(py - dais[1])) <= 8:
                break
            step(attacker, tx - px, ty - py)
        press(attacker, "claim")
        if not pump(attacker, 12, lambda: (attacker.kcs_view.status or {}).get("status") == "resolved"):
            fail("claim did not finish\n" + chat_text(attacker))
        if (attacker.dungeon or {}).get("id") == "kings_castle_siege":
            fail("the claimant is still in the siege")
        result = (attacker.kcs_view.status or {}).get("result") or {}
        if "throne" not in (result.get("text") or "").lower():
            fail(f"result text is {result}")
        own = (attacker.kcs_view.status or {}).get("ownership") or {}
        if "SiegeAtk" not in (own.get("castle_line") or ""):
            fail(f"castle line is {own}")
        if own.get("royal_title") not in ("King", "Queen"):
            fail(f"crown line is {own}")
        if attacker.player.get("royal_title") not in ("King", "Queen"):
            fail(f"character title is {attacker.player.get('royal_title')}")
        text = chat_text(attacker)
        if "King's Castle is held by" not in text and "wears the crown" not in text:
            fail("the herald did not announce the crown\n" + text)
        save(attacker, "kcs-lifecycle-result.png")
        print("result", result.get("text"), own.get("castle_line"), attacker.player.get("royal_title"), flush=True)

        names = [name for _r, name in attacker.kcs_view.buttons]
        if "fire" in names or "claim" in names:
            fail(f"combat buttons remain after the result: {names}")
        if "prep" not in names:
            fail(f"sandbox prepare is not offered after the battle: {names}")
        press(attacker, f"side-{int(attacker.player.get('id'))}")
        # One click selects attacker. The defender needs two clicks to land on defend.
        press(attacker, f"side-{int(defender.player.get('id'))}")
        press(attacker, f"side-{int(defender.player.get('id'))}")
        press(attacker, "prep")
        if not pump(attacker, 12, lambda: (attacker.kcs_view.status or {}).get("status") == "registration"):
            fail("sandbox prepare did not open a registration\n" + chat_text(attacker))
        nxt = attacker.kcs_view.status or {}
        if nxt.get("previous") and (nxt.get("previous") or {}).get("reason") != "claim":
            fail(f"previous result changed: {nxt.get('previous')}")
        if "SANDBOX ONLY" not in (nxt.get("text") or ""):
            fail(f"prepare text is {nxt.get('text')}")
        save(attacker, "kcs-lifecycle-next.png")
        print("next registration", nxt.get("war_id"), nxt.get("phase"), flush=True)

        attacker.net.send("LOGOUT")
        pump(attacker, 1.5, lambda: False)
        again = login("kcsatk", "SiegeAtk", mode="login")
        if not pump(again, 12, lambda: (again.kcs_view.status or {}).get("status") == "registration"):
            fail("reconnect did not restore the registration\n" + chat_text(again))
        if (again.dungeon or {}).get("id") == "kings_castle_siege":
            fail("reconnect opened the finished battle")
        if again.player.get("royal_title") not in ("King", "Queen"):
            fail("reconnect lost the crown title")
        print("reconnect kept the crown and the new registration", flush=True)
        print("kcs lifecycle client ok", flush=True)
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
