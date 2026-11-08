"""Real-handler coverage for siege engines and independent openings.

Temporary SQLite only. Placement rules come from the approved map fixture.
No engine cost, currency, or damage formula is applied.
"""
from __future__ import annotations

import asyncio
import json
import os
import sys
import tempfile
import threading

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "server"))
sys.path.insert(0, os.path.join(ROOT, "server", "kcs_parity"))
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

_TMP = tempfile.mkdtemp(prefix="kcs_p2_")
os.environ["CROWNFALL_DB_PATH"] = os.path.join(_TMP, "game_world.db")
os.environ.pop("USE_KINGS_CASTLE_SIEGE", None)

import database  # noqa: E402
database.Database.__init__.__defaults__ = (":memory:",)

import feature_flags  # noqa: E402
import server  # noqa: E402
import kcs_siege  # noqa: E402
from kings_castle_siege_map.layout import build_battlefield  # noqa: E402
from kings_castle_siege_map.placement import PlacedEngine, SPECS, find_valid_on_side, rotated_size  # noqa: E402
from kcs_server.guard import PLANE_BATTLEFIELD  # noqa: E402
from kcs_server.store import FaultPlan  # noqa: E402

W = server.WORLD
_N = [0]
CHECKS = 0
BF = build_battlefield()


def check(ok, msg):
    global CHECKS
    CHECKS += 1
    if not ok:
        raise AssertionError(msg)
    print("ok ", msg)


class WS:
    def __init__(self):
        self.sent = []

    async def send(self, raw):
        self.sent.append(json.loads(raw))


def messages(session, kind):
    return [m for m in session.ws.sent if m.get("type") == kind]


def errors(session):
    return [m.get("message") for m in session.ws.sent if m.get("type") == "ERROR"]


def player(username=None):
    _N[0] += 1
    name = username or f"p2{_N[0]}"
    W.db.create_account(name, "pw", name.title())
    row = W.db.get_player_by_username(name)
    W.db.conn.execute("UPDATE players SET stats_allocated = 1 WHERE id = ?", (row["id"],))
    W.db.conn.commit()
    session = server.PlayerSession(WS(), W.db.get_player_by_id(row["id"]))
    session.stats_allocated = True
    session.inventory = {}
    session.bank = {}
    session.equipment = {}
    session.knows_teleport = True
    session.teleport_marks = ["village", "realm", "king"]
    session.teleport_ready_at = 0
    W.sessions[session.player_id] = session
    return session


def use_store():
    fd, path = tempfile.mkstemp(prefix="kcs_", suffix=".db", dir=_TMP)
    os.close(fd)
    os.unlink(path)
    kcs_siege.configure(path, journal_path=path + ".pending.jsonl", faults=FaultPlan())
    return path


def open_registration(store):
    return store.create_war(f"p2-{store.path}")


def go_live(store, war):
    store.set_war_status(war.war_id, "locking")
    store.set_war_status(war.war_id, "active")


def spot(kind, side, rotation, existing):
    found = find_valid_on_side(BF, kind, side, existing, rotation=rotation)
    check(found is not None, f"approved search finds a {kind} on the {side} side")
    return found


def remember(existing, engine):
    existing.append(PlacedEngine(
        str(engine["engine_id"]), engine["engine_type"], engine["x"], engine["y"], engine["rotation"],
    ))


async def place(session, kind, found, request_id):
    before = len(messages(session, "KCS_DELTA"))
    await server.handle_kcs_place(session, {
        "engine_type": kind,
        "x": found[0],
        "y": found[1],
        "rotation": found[2],
        "request_id": request_id,
    })
    oks = messages(session, "KCS_PLACE_OK")
    check(oks and oks[-1]["engine"]["engine_type"] == kind, f"handler places {kind}")
    check(len(messages(session, "KCS_DELTA")) == before + 1, f"{kind} placement emits one delta to the placer")
    return oks[-1]["engine"]


async def test_flag_off_refuses_without_a_store():
    feature_flags.USE_KINGS_CASTLE_SIEGE = False
    path = use_store()
    s = player()
    await server.handle_kcs_place(s, {
        "engine_type": "ram", "x": 1, "y": 1, "rotation": 0, "request_id": "off",
    })
    await server.handle_kcs_opening(s, {"opening_id": "main_gate", "state": "destroyed", "damage": 999})
    await server.handle_kcs_snapshot(s, {})
    check(errors(s)[-3:] == [
        "The siege is closed.",
        "The siege does not take structure orders from the client.",
        "The siege is closed.",
    ], "flag off denies place, structure orders, and snapshot")
    check(not os.path.exists(path), "flag off does not create the siege database")
    try:
        await server.apply_kcs_opening("main_gate", "destroyed")
        check(False, "flag off server opening change must fail")
    except RuntimeError as exc:
        check(str(exc) == "feature_disabled", "flag off server opening change is refused")
    check(not os.path.exists(path), "refused opening change still does not create the database")


async def test_perimeter_placement_collision_and_denials():
    feature_flags.USE_KINGS_CASTLE_SIEGE = True
    path = use_store()
    store = kcs_siege.store()
    war = open_registration(store)
    attacker = player("atk")
    defender = player("def")
    outsider = player("out")
    realm = player("realm")
    store.enlist(war.war_id, attacker.player_id, "attack")
    store.enlist(war.war_id, defender.player_id, "defend")
    store.enlist(war.war_id, outsider.player_id, "attack")
    go_live(store, war)
    await server.handle_enter_dungeon(attacker, {"dungeon_id": "kings_castle_siege"})
    await server.handle_enter_dungeon(defender, {"dungeon_id": "kings_castle_siege"})
    realm.x, realm.y = 9, 28
    await server.handle_enter_dungeon(realm, {"dungeon_id": "castle_realm"})
    check(realm.dungeon and realm.dungeon.get("id") == "castle_realm", "Castle Realm enter is unchanged")
    check(attacker.dungeon.get("plane") == PLANE_BATTLEFIELD, "attacker is on the battlefield")
    snaps = messages(attacker, "KCS_SNAPSHOT")
    check(snaps and snaps[-1]["engines"] == [], "deploy snapshot starts with no engines")
    check(len(snaps[-1]["openings"]) == 12, "snapshot lists every battlefield and throne opening")

    existing = []
    plan = [
        ("ram", "south", 0),
        ("ram", "west", 90),
        ("siege_tower", "east", 90),
        ("trebuchet", "north", 0),
        ("ladder", "north", 180),
    ]
    placed = []
    for kind, side, rotation in plan:
        found = spot(kind, side, rotation, existing)
        engine = await place(attacker, kind, found, f"{kind}-{side}")
        placed.append(engine)
        remember(existing, engine)
    extra = spot("trebuchet", "south", 0, existing)
    engine = await place(attacker, "trebuchet", extra, "extra-treb")
    placed.append(engine)
    check(len(store.engines(war.war_id)) == 6, "six engines stored and the sample is not a cap")
    ww, wn, we, ws = BF.wall_box
    sides = set()
    for engine in placed:
        width, height = rotated_size(SPECS[engine["engine_type"]], engine["rotation"])
        cx = engine["x"] + width // 2
        cy = engine["y"] + height // 2
        if cy > ws:
            sides.add("south")
        elif cy < wn:
            sides.add("north")
        elif cx < ww:
            sides.add("west")
        elif cx > we:
            sides.add("east")
    check(sides == {"south", "north", "west", "east"}, f"placed engines cover the perimeter ({sides})")

    keep = BF.keep_rect
    await server.handle_kcs_place(attacker, {
        "engine_type": "trebuchet", "x": keep[0] + 2, "y": keep[1] + 2,
        "rotation": 0, "request_id": "keep",
    })
    water = next(
        (x, y) for y in range(BF.plane.height) for x in range(BF.plane.width) if BF.plane.cell(x, y) == "~"
    )
    await server.handle_kcs_place(attacker, {
        "engine_type": "trebuchet", "x": water[0], "y": water[1], "rotation": 0, "request_id": "water",
    })
    first = placed[0]
    await server.handle_kcs_place(attacker, {
        "engine_type": first["engine_type"], "x": first["x"], "y": first["y"],
        "rotation": first["rotation"], "request_id": "overlap",
    })
    await server.handle_kcs_place(attacker, {
        "engine_type": "ram", "x": first["x"], "y": first["y"], "rotation": "sideways", "request_id": "badrot",
    })
    await server.handle_kcs_place(attacker, {
        "engine_type": "ram", "x": first["x"], "y": first["y"], "rotation": 0,
        "request_id": "forged", "damage": 500, "resources": {"timber": 0}, "owner": attacker.player_id,
    })
    await server.handle_kcs_place(defender, {
        "engine_type": "ladder", "x": first["x"] + 20, "y": first["y"], "rotation": 0, "request_id": "def",
    })
    await server.handle_kcs_place(outsider, {
        "engine_type": "ladder", "x": first["x"] + 20, "y": first["y"], "rotation": 0, "request_id": "out",
    })
    attacker.hp = 0
    await server.handle_kcs_place(attacker, {
        "engine_type": "ladder", "x": extra[0], "y": extra[1] + 8, "rotation": 0, "request_id": "dead",
    })
    attacker.hp = attacker.max_hp()
    attacker.dungeon["mode"] = "spectator"
    await server.handle_kcs_place(attacker, {
        "engine_type": "ladder", "x": extra[0], "y": extra[1] + 8, "rotation": 0, "request_id": "spec",
    })
    attacker.dungeon["mode"] = "combatant"
    text = " ".join(errors(attacker) + errors(defender) + errors(outsider))
    check("keep" in text.lower() or "Cannot build on the keep." in text, "keep placement is refused")
    check("water" in text.lower(), "water placement is refused")
    check("overlap" in text.lower() or "operating space" in text.lower(), "overlap is refused")
    check("not valid" in text.lower(), "malformed rotation is refused")
    check("does not accept that" in text.lower(), "client damage and resources are refused")
    check(any("cannot place" in e.lower() for e in errors(defender)), "defender placement is refused")
    check(any("not deployed" in e.lower() or "cannot place" in e.lower() for e in errors(outsider)),
          "a roster member who is not on the map cannot place")
    check(len(store.engines(war.war_id)) == 6, "refused requests did not store an engine")

    replay_before = len(messages(defender, "KCS_DELTA"))
    await server.handle_kcs_place(attacker, {
        "engine_type": first["engine_type"], "x": first["x"], "y": first["y"],
        "rotation": first["rotation"], "request_id": f"{first['engine_type']}-south",
    })
    check(messages(attacker, "KCS_PLACE_OK")[-1]["replayed"] is True, "replaying a request returns the original engine")
    check(len(messages(defender, "KCS_DELTA")) == replay_before, "a replay does not broadcast a second delta")
    check(len(store.engines(war.war_id)) == 6, "replay does not insert another row")
    await server.handle_kcs_place(attacker, {
        "engine_type": "ladder", "x": first["x"], "y": first["y"] + 30,
        "rotation": 0, "request_id": f"{first['engine_type']}-south",
    })
    check(len(store.engines(war.war_id)) == 6, "a conflicting replay writes nothing")

    tile = tuple(first["tiles"][0])
    check(kcs_siege.walkable(attacker, *tile) is False, "placer collides with the engine footprint")
    check(kcs_siege.walkable(defender, *tile) is False, "defender collides with the same footprint")
    stepped = False
    for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
        nx, ny = tile[0] - dx, tile[1] - dy
        if kcs_siege.walkable(attacker, nx, ny):
            attacker.x, attacker.y = nx, ny
            await server.handle_move(attacker, {"dx": dx, "dy": dy})
            check((attacker.x, attacker.y) == (nx, ny), "a real step cannot enter an engine tile")
            stepped = True
            break
    check(stepped, "an engine tile has a walkable neighbour to step from")

    stored_before = dict(store.openings(war.war_id))
    await server.handle_kcs_opening(attacker, {
        "opening_id": "main_gate", "state": "destroyed", "damage": 10000, "resources": {"timber": 9},
    })
    check(store.openings(war.war_id) == stored_before, "client structure message does not change openings")
    west_tiles = [
        tuple(t) for t, oid in kcs_siege.siege_map().plane(PLANE_BATTLEFIELD).opening_at.items()
        if oid == "west_gate"
    ]
    main_tiles = [
        tuple(t) for t, oid in kcs_siege.siege_map().plane(PLANE_BATTLEFIELD).opening_at.items()
        if oid == "main_gate"
    ]
    check(all(not kcs_siege.walkable(attacker, *t) for t in main_tiles), "intact main gate blocks the attacker")
    check(all(not kcs_siege.walkable(defender, *t) for t in main_tiles), "intact main gate blocks the defender")
    body = await server.apply_kcs_opening("main_gate", "destroyed", 0)
    check(body["opening_id"] == "main_gate" and body["state"] == "destroyed", "server opening change is explicit")
    check({tuple(t) for t in body["tiles"]} == set(main_tiles), "the delta lists only the main gate tiles")
    check(all(kcs_siege.walkable(attacker, *t) for t in main_tiles), "destroyed main gate opens for the attacker")
    check(all(kcs_siege.walkable(defender, *t) for t in main_tiles), "destroyed main gate opens for the defender")
    check(all(not kcs_siege.walkable(attacker, *t) for t in west_tiles), "west gate tiles stay closed")
    check(all(not kcs_siege.walkable(defender, *t) for t in west_tiles), "west gate stays closed for the other player")
    damaged = await server.apply_kcs_opening("main_gate", "damaged")
    check({tuple(t) for t in damaged["tiles"]} == set(main_tiles), "damaged state names the same tiles")
    check(all(not kcs_siege.walkable(attacker, *t) for t in main_tiles), "damaged gate is not a walkable opening")
    await server.apply_kcs_opening("west_wall_breach", "destroyed")
    check(all(not kcs_siege.walkable(attacker, *t) for t in west_tiles), "a breach does not open the west gate")

    def saw_delta(session, opening_id):
        return any(
            m.get("kind") == "opening" and m.get("opening_id") == opening_id
            for m in messages(session, "KCS_DELTA")
        )
    check(saw_delta(attacker, "main_gate") and saw_delta(defender, "main_gate"),
          "both siege participants receive the opening delta")
    check(not messages(outsider, "KCS_DELTA") and not messages(realm, "KCS_DELTA"),
          "overworld and Castle Realm sessions do not receive siege deltas")

    engine_ids = [e.engine_id for e in store.engines(war.war_id)]
    kcs_siege.simulate_restart()
    reopened = kcs_siege.store()
    check([e.engine_id for e in reopened.engines(war.war_id)] == engine_ids, "engines survive a process restart")
    check(reopened.openings(war.war_id)["west_wall_breach"] == "destroyed", "breach state survives a process restart")
    check(reopened.openings(war.war_id)["main_gate"] == "damaged", "main gate state survives a process restart")
    check(os.path.abspath(path) != os.path.abspath(database.DB_PATH), "siege file is not the game database")
    username = W.db.get_player_by_id(attacker.player_id)["username"]
    await server.logout_session(attacker, "test")
    ws = WS()
    await server.handle_login(ws, {"username": username, "password": "pw"}, False, "127.0.0.1")
    back = W.sessions[W.db.get_player_by_username(username)["id"]]
    shot = [m for m in back.ws.sent if m.get("type") == "KCS_SNAPSHOT"]
    check(shot and [e["engine_id"] for e in shot[-1]["engines"]] == engine_ids,
          "reconnect snapshot restores the same engines")
    states = {row["id"]: row["state"] for row in shot[-1]["openings"]}
    check(states["main_gate"] == "damaged" and states["west_wall_breach"] == "destroyed",
          "reconnect snapshot restores opening states")
    check(states["west_gate"] == "intact", "unrelated openings stay intact across restart")


async def test_overlapping_placements_are_serialized():
    feature_flags.USE_KINGS_CASTLE_SIEGE = True
    use_store()
    store = kcs_siege.store()
    war = open_registration(store)
    attacker = player("race")
    store.enlist(war.war_id, attacker.player_id, "attack")
    go_live(store, war)
    await server.handle_enter_dungeon(attacker, {"dungeon_id": "kings_castle_siege"})
    found = spot("trebuchet", "east", 0, [])
    results = []

    def go(i):
        results.append(kcs_siege.propose_placement(attacker, {
            "engine_type": "trebuchet",
            "x": found[0],
            "y": found[1],
            "rotation": found[2],
            "request_id": f"race-{i}",
        }))

    threads = [threading.Thread(target=go, args=(i,)) for i in range(2)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    oks = [row for row in results if row.get("ok")]
    check(len(results) == 2 and len(oks) == 1, f"concurrent overlap allows one engine ({results})")
    check(len(store.engines(war.war_id)) == 1, "the loser did not persist")


async def main():
    real_world = os.path.join(ROOT, "server", "world.db")
    before = os.stat(real_world).st_mtime if os.path.exists(real_world) else None
    await test_flag_off_refuses_without_a_store()
    await test_perimeter_placement_collision_and_denials()
    await test_overlapping_placements_are_serialized()
    feature_flags.USE_KINGS_CASTLE_SIEGE = False
    kcs_siege.close()
    after = os.stat(real_world).st_mtime if os.path.exists(real_world) else None
    check(before == after, "world.db was not modified")
    print(f"kcs p2 tests ok ({CHECKS} checks)")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except Exception:
        import traceback
        traceback.print_exc()
        raise SystemExit(1)
