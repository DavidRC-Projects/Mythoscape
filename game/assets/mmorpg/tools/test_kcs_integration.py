"""Real-handler regressions for the King's Castle Siege presence guard.

Temporary SQLite only. The game Database is forced onto :memory: before the
server imports it. The siege store is a different temporary file and must
never be world.db.
"""
from __future__ import annotations

import asyncio
import json
import os
import sys
import tempfile
import threading
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "server"))
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

_TMP = tempfile.mkdtemp(prefix="kcs_p1_")
os.environ["CROWNFALL_DB_PATH"] = os.path.join(_TMP, "game_world.db")
# The siege flag is off unless a test assigns it. An empty value must not enable it.
os.environ.pop("USE_KINGS_CASTLE_SIEGE", None)

import database  # noqa: E402
database.Database.__init__.__defaults__ = (":memory:",)

import feature_flags  # noqa: E402
import server  # noqa: E402
import kcs_siege  # noqa: E402
from kcs_server.guard import PLANE_BATTLEFIELD, PLANE_THRONE  # noqa: E402
from kcs_server.store import FaultPlan  # noqa: E402

W = server.WORLD
_N = [0]
CHECKS = 0


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


def errors(ws):
    return [m.get("message") for m in ws.sent if m.get("type") == "ERROR"]


def entered(ws):
    return [m for m in ws.sent if m.get("type") == "DUNGEON_ENTER"]


def player(username=None):
    _N[0] += 1
    name = username or f"kcs{_N[0]}"
    W.db.create_account(name, "pw", name.title())
    row = W.db.get_player_by_username(name)
    W.db.conn.execute("UPDATE players SET stats_allocated = 1 WHERE id = ?", (row["id"],))
    W.db.conn.commit()
    row = W.db.get_player_by_id(row["id"])
    session = server.PlayerSession(WS(), row)
    session.stats_allocated = True
    session.inventory = {}
    session.bank = {}
    session.knows_teleport = True
    session.teleport_marks = ["village", "realm", "king"]
    session.teleport_ready_at = 0
    W.sessions[session.player_id] = session
    return session


def use_store(faults=None):
    fd, path = tempfile.mkstemp(prefix="kcs_", suffix=".db", dir=_TMP)
    os.close(fd)
    os.unlink(path)
    journal = path + ".pending.jsonl"
    kcs_siege.configure(path, journal_path=journal, faults=faults or FaultPlan())
    return path, journal


def open_war():
    store = kcs_siege.store()
    war = store.create_war("war-1")
    return store, war


def enlist(store, war, session, side):
    store.enlist(war.war_id, session.player_id, side)


def arm_live(store, war):
    store.set_war_status(war.war_id, "locking")
    store.set_war_status(war.war_id, "active")


def flag(on):
    feature_flags.USE_KINGS_CASTLE_SIEGE = bool(on)


def resume_of(session):
    return {
        "id": "kings_castle_siege",
        "plane": (session.dungeon or {}).get("plane") or PLANE_BATTLEFIELD,
        "x": int(session.x),
        "y": int(session.y),
        "return_x": (session.dungeon or {}).get("return_x", 28),
        "return_y": (session.dungeon or {}).get("return_y", 24),
        "mode": (session.dungeon or {}).get("mode") or "combatant",
    }


async def test_flag_off_and_ordinary_maps():
    flag(False)
    check(feature_flags.USE_KINGS_CASTLE_SIEGE is False, "USE_KINGS_CASTLE_SIEGE default off")
    check(kcs_siege.enabled() is False, "bridge reads the shared flag")
    path, _journal = use_store()
    default_db = os.path.join(ROOT, "server", "kcs_siege.db")
    s = player()
    before = (s.x, s.y)
    await server.handle_enter_dungeon(s, {"dungeon_id": "kings_castle_siege"})
    check(s.dungeon is None, "flag off: siege enter does not create a dungeon")
    check(errors(s.ws)[-1] == "The siege is closed.", "flag off: enter denied")
    check(not os.path.exists(path), "flag off: enter does not create the siege database")
    check(not os.path.exists(default_db), "flag off: default kcs_siege.db was not created")

    forged = {
        "id": "kings_castle_siege",
        "label": "Siege",
        "where": "kings_castle_siege",
        "plane": PLANE_BATTLEFIELD,
        "x": 139,
        "y": 244,
    }
    server.TELEPORT_DESTINATIONS.append(forged)
    s.teleport_marks.append(forged["id"])
    try:
        await server.handle_teleport(s, {"dest": forged["id"]})
    finally:
        server.TELEPORT_DESTINATIONS.remove(forged)
    check(s.dungeon is None and (s.x, s.y) == before, "flag off: teleport does not enter the siege")
    check(not os.path.exists(path), "flag off: teleport does not create the siege database")

    stale = {
        "id": "kings_castle_siege",
        "plane": PLANE_BATTLEFIELD,
        "x": 139, "y": 244, "return_x": before[0], "return_y": before[1],
    }
    check(server._apply_kcs_resume(s, stale, reason="login") is False, "flag off: login resume denied")
    check(s.dungeon is None and (s.x, s.y) == before, "flag off: login leaves overworld coordinates")
    await server._resume_dungeon(s, stale)
    check(s.dungeon is None, "flag off: reconnect resume denied")

    s.x, s.y = 9, 28
    await server.handle_enter_dungeon(s, {"dungeon_id": "castle_realm"})
    check(s.dungeon and s.dungeon.get("id") == "castle_realm", "flag off: Castle Realm enter still works")
    check(not os.path.exists(path), "Castle Realm enter does not open the siege database")
    await server.handle_leave_dungeon(s, silent=True)
    check(s.dungeon is None, "left Castle Realm")

    flag(True)
    s.x, s.y = before
    await server.handle_enter_dungeon(s, {"dungeon_id": "tidehollow"})
    check(s.dungeon is None, "flag on: a normal dungeon still requires its entrance")
    check(any("entrance" in (m or "").lower() for m in errors(s.ws)), "flag on: ordinary entrance error unchanged")
    s.x, s.y = 9, 28
    await server.handle_enter_dungeon(s, {"dungeon_id": "castle_realm"})
    check(s.dungeon and s.dungeon.get("id") == "castle_realm", "flag on: Castle Realm enter unchanged")
    check(s.dungeon.get("id") != "kings_castle_siege", "Castle Realm is not the siege map")
    await server.handle_teleport(s, {"dest": "village"})
    check(s.dungeon is None, "teleport from Castle Realm still returns to the overworld")
    check(not os.path.exists(path), "ordinary maps did not create the siege database")
    s.x, s.y = 9, 28
    await server.handle_enter_dungeon(s, {"dungeon_id": "castle_realm"})
    s.hp = 0
    s.in_combat_with = ("player", 999)
    s.coins = 40
    await server.resolve_player_death(s, [])
    check(s.dungeon is None and not kcs_siege.on_map(s), "castle realm death still leaves the realm")
    check(s.hp == s.max_hp() and s.in_combat_with is None, "castle realm death still restores hp and clears combat")
    check(not os.path.exists(path), "castle realm death does not open the siege database")
    await server.resolve_player_death(s, [])
    check(not os.path.exists(path), "overworld death does not open the siege database")
    check(s.dungeon is None, "overworld death still leaves the player outside")


async def test_deploy_move_restore_and_castle_teleport():
    flag(True)
    path, _journal = use_store()
    store, war = open_war()
    s = player()
    enlist(store, war, s, "attack")
    arm_live(store, war)
    overworld = (int(s.x), int(s.y))
    await server.handle_enter_dungeon(s, {"dungeon_id": "kings_castle_siege", "plane": "castle_realm"})
    check(s.dungeon is None, "a Castle Realm plane id cannot deploy onto the siege")
    await server.handle_enter_dungeon(s, {
        "dungeon_id": "kings_castle_siege",
        "plane": PLANE_BATTLEFIELD,
    })
    check(s.dungeon and s.dungeon.get("id") == "kings_castle_siege", "roster member deploys onto the siege map")
    check(s.dungeon.get("plane") == PLANE_BATTLEFIELD, "deploy lands on the battlefield")
    check(s.dungeon.get("mode") == "combatant", "deploy grants combatant presence")
    check((s.dungeon.get("return_x"), s.dungeon.get("return_y")) == overworld, "overworld return is remembered")
    check(store.roster_status(war.war_id, s.player_id).deployed, "deploy is durable")
    check(os.path.abspath(path) != os.path.abspath(database.DB_PATH), "siege file is not the game database path")
    check(store.conn is not W.db.conn, "siege connection is not the game connection")

    nx, ny = _step_target(s)
    dx, dy = nx - s.x, ny - s.y
    origin = (s.x, s.y)
    await server.handle_move(s, {"dx": dx, "dy": dy})
    check((s.x, s.y) == (nx, ny), "living combatant can step onto a walkable siege tile")
    blocked = _blocked_stand(s)
    check(blocked is not None, "the battlefield has a walkable tile beside a blocked one")
    s.x, s.y = blocked[0], blocked[1]
    await server.handle_move(s, {"dx": blocked[2], "dy": blocked[3]})
    check((s.x, s.y) == (blocked[0], blocked[1]), "blocked siege step does not move the player")
    s.x, s.y = origin

    link_to = _step_target(s)
    kcs_siege._PLANE_LINKS = ((PLANE_BATTLEFIELD, link_to[0], link_to[1], PLANE_THRONE),)
    try:
        await server.handle_move(s, {"dx": link_to[0] - s.x, "dy": link_to[1] - s.y})
        check(s.dungeon.get("plane") == PLANE_THRONE, "in-map plane change goes through the guard and is allowed while alive")
    finally:
        kcs_siege._PLANE_LINKS = ()

    # Castle teleport from the siege is an exit, not a siege grant.
    await server.handle_teleport(s, {"dest": "realm"})
    check(s.dungeon and s.dungeon.get("id") == "castle_realm", "teleport to the King's Realm still enters Castle Realm")
    check(not kcs_siege.on_map(s), "that teleport does not leave them on the siege map")
    await server.handle_leave_dungeon(s, silent=True)

    # Alive login/reconnect restores the deployment.
    await server.handle_enter_dungeon(s, {"dungeon_id": "kings_castle_siege"})
    check(kcs_siege.on_map(s), "redeploy after leaving")
    saved = resume_of(s)
    username = s.username
    await server.logout_session(s, "test")
    check(s.player_id not in W.sessions, "logout drops the session")
    raw = W.db.get_player_by_id(s.player_id)["dungeon_resume"]
    check(json.loads(raw)["id"] == "kings_castle_siege", "logout saved a siege resume")
    check(json.loads(raw)["plane"] == saved["plane"], "resume keeps the siege plane")
    back = await login_account(username)
    check(kcs_siege.on_map(back), "login restores a living deployed player")
    check(back.dungeon.get("mode") == "combatant", "restored presence is combatant")
    check(any(m.get("type") == "DUNGEON_ENTER" and m.get("id") == "kings_castle_siege" for m in back.ws.sent),
          "login sends a siege enter, not a Castle Realm payload")
    await server.logout_session(back, "test")


async def login_account(username):
    ws = WS()
    await server.handle_login(ws, {"username": username, "password": "pw"}, False, "127.0.0.1")
    row = W.db.get_player_by_username(username)
    session = W.sessions.get(row["id"])
    check(session is not None, f"{username} logged in")
    session.knows_teleport = True
    session.teleport_marks = ["village", "realm", "king"]
    session.teleport_ready_at = 0
    return session


async def test_death_ordering_denies_return():
    flag(True)
    path, journal = use_store()
    store, war = open_war()
    s = player()
    enlist(store, war, s, "attack")
    arm_live(store, war)
    await server.handle_enter_dungeon(s, {"dungeon_id": "kings_castle_siege"})
    check(kcs_siege.on_map(s), "deployed before death")
    stale = resume_of(s)
    seen = {}
    real = store.eliminate

    def wrapped(war_id, player_id, cause):
        seen["hp"] = s.hp
        seen["combat"] = s.in_combat_with
        seen["on_map"] = kcs_siege.on_map(s)
        seen["cause"] = cause
        return real(war_id, player_id, cause)

    store.eliminate = wrapped
    s.hp = 0
    s.in_combat_with = ("player", 999)
    s.coins = 100
    await server.resolve_player_death(s, [])
    check(seen.get("hp") == 0, "elimination runs while hit points are still zero")
    check(seen.get("combat") == ("player", 999), "elimination runs before combat credit is cleared")
    check(seen.get("on_map") is True, "elimination runs before the player leaves the plane")
    check(seen.get("cause") == "death", "death cause is recorded")
    check(not kcs_siege.on_map(s), "death removes siege presence")
    check(s.hp == s.max_hp(), "hit points are restored only after elimination")
    check(s.in_combat_with is None, "combat credit is cleared only after elimination")
    check(store.roster_status(war.war_id, s.player_id).eliminated, "elimination is durable")
    check((s.x, s.y) == (stale["return_x"], stale["return_y"]), "player wakes on the overworld return tile")

    await server.handle_enter_dungeon(s, {"dungeon_id": "kings_castle_siege"})
    check(not kcs_siege.on_map(s), "eliminated player cannot deploy again")
    check("eliminated" in (errors(s.ws)[-1] or "").lower(), "deploy error says eliminated")

    forged = {
        "id": "kings_castle_siege",
        "label": "Siege",
        "where": PLANE_THRONE,
        "plane": PLANE_THRONE,
        "x": 35, "y": 42,
    }
    server.TELEPORT_DESTINATIONS.append(forged)
    s.teleport_marks.append(forged["id"])
    spot = (s.x, s.y)
    try:
        await server.handle_teleport(s, {"dest": forged["id"]})
    finally:
        server.TELEPORT_DESTINATIONS.remove(forged)
    check(not kcs_siege.on_map(s) and (s.x, s.y) == spot, "eliminated player cannot teleport onto the siege")

    username = W.db.get_player_by_id(s.player_id)["username"]
    await server.logout_session(s, "test")
    # Death clears the resume. Put it back, the way a resume written before
    # the death hook would still be sitting in the player row.
    W.db.save_player_stats(s.player_id, dungeon_resume=json.dumps(stale))
    back = await login_account(username)
    check(not kcs_siege.on_map(back), "eliminated login does not restore siege presence")
    shell = WS()
    # Reconnect handler, separate from the login reason used above.
    ghost = server.PlayerSession(shell, W.db.get_player_by_id(back.player_id))
    ghost.dungeon = None
    W.sessions.pop(back.player_id, None)
    await server._resume_dungeon(ghost, stale)
    check(not kcs_siege.on_map(ghost), "eliminated reconnect does not restore siege presence")
    check(os.path.basename(path) != "world.db", "siege test database is not named world.db")
    check(os.path.exists(journal) or store.roster_status(war.war_id, s.player_id).eliminated,
          "death left a durable elimination")


async def test_persist_error_restart_and_race():
    flag(True)
    faults = FaultPlan()
    path, journal = use_store(faults)
    store, war = open_war()
    s = player()
    enlist(store, war, s, "defend")
    arm_live(store, war)
    await server.handle_enter_dungeon(s, {"dungeon_id": "kings_castle_siege"})
    check(kcs_siege.on_map(s), "defender deployed")
    stale = resume_of(s)
    # Uncommitted game-db work must survive a siege rollback.
    W.db.conn.execute("CREATE TABLE IF NOT EXISTS kcs_probe (v INTEGER)")
    W.db.conn.execute("INSERT INTO kcs_probe VALUES (7)")
    check(W.db.conn.in_transaction, "game database has uncommitted work")
    faults.arm("eliminate.before_commit")
    s.hp = 0
    s.in_combat_with = ("monster", "m")
    await server.resolve_player_death(s, [])
    check(not kcs_siege.on_map(s), "persistence error still removes combatant presence")
    check(not store.roster_status(war.war_id, s.player_id).eliminated, "failed commit did not eliminate")
    check(s.player_id in kcs_siege._unconfirmed, "unconfirmed elimination is held in process")
    W.db.conn.commit()
    check(W.db.conn.execute("SELECT v FROM kcs_probe").fetchone()[0] == 7,
          "game database work survived the siege rollback")

    await server.handle_enter_dungeon(s, {"dungeon_id": "kings_castle_siege"})
    check(not kcs_siege.on_map(s), "pending elimination blocks deploy")
    spot = (s.x, s.y)
    forged = {
        "id": "kcs_throne",
        "label": "Throne",
        "where": "kings_castle_siege",
        "plane": PLANE_THRONE,
        "x": 36, "y": 10,
    }
    server.TELEPORT_DESTINATIONS.append(forged)
    s.teleport_marks.append(forged["id"])
    try:
        await server.handle_teleport(s, {"dest": forged["id"]})
    finally:
        server.TELEPORT_DESTINATIONS.remove(forged)
    check((s.x, s.y) == spot and not kcs_siege.on_map(s), "pending elimination blocks teleport")
    check(server._apply_kcs_resume(s, stale, reason="login") is False, "pending elimination blocks login")
    check(server._apply_kcs_resume(s, stale, reason="reconnect") is False, "pending elimination blocks reconnect")

    kcs_siege.simulate_restart()
    check(s.player_id not in kcs_siege._unconfirmed, "restart drops the in-memory hold")
    check(os.path.exists(journal), "journal file survived the restart")
    back_ok = server._apply_kcs_resume(s, stale, reason="reconnect")
    check(back_ok is False and not kcs_siege.on_map(s), "restart replay does not restore an eliminated player")
    check(kcs_siege.store().roster_status(war.war_id, s.player_id).eliminated,
          "journal replay made the elimination durable")
    await server.handle_enter_dungeon(s, {"dungeon_id": "kings_castle_siege"})
    check(not kcs_siege.on_map(s), "deploy after restart is still denied")

    # A second living player races a death.
    path2, _j2 = use_store()
    store2, war2 = open_war()
    live = player()
    enlist(store2, war2, live, "attack")
    arm_live(store2, war2)
    await server.handle_enter_dungeon(live, {"dungeon_id": "kings_castle_siege"})
    saved = resume_of(live)
    late = []
    death_done = threading.Event()
    stop = threading.Event()

    def hammer():
        while not stop.is_set():
            shell = WS()
            ghost = type("G", (), {})()
            ghost.player_id = live.player_id
            ghost.dungeon = None
            ghost.x, ghost.y = saved["return_x"], saved["return_y"]
            ghost.pet_id = None
            ghost.in_combat_with = None
            ghost.gathering_node = None
            ghost.pet_target_id = None
            ghost.ws = shell
            allowed = server._apply_kcs_resume(ghost, saved, reason="reconnect")
            if death_done.is_set() and (allowed or kcs_siege.on_map(ghost)):
                late.append("resume")
            decision = kcs_siege.decide(live.player_id, PLANE_BATTLEFIELD, "deploy")
            if death_done.is_set() and decision.allowed:
                late.append("deploy")
            decision = kcs_siege.decide(live.player_id, PLANE_THRONE, "teleport")
            if death_done.is_set() and decision.allowed:
                late.append("teleport")

    thread = threading.Thread(target=hammer, daemon=True)
    thread.start()
    live.hp = 0
    await server.resolve_player_death(live, [])
    death_done.set()
    time.sleep(0.05)
    stop.set()
    thread.join(10)
    check(not thread.is_alive(), "death/entry race thread finished")
    if late:
        st = kcs_siege.store().roster_status(war2.war_id, live.player_id)
        post = kcs_siege.decide(live.player_id, PLANE_BATTLEFIELD, "deploy")
        print("RACE DEBUG", "elim", st, "post", post, "unconfirmed", live.player_id in kcs_siege._unconfirmed,
              "on", kcs_siege.on_map(live), "late", len(late), "sample", late[:8])
    check(not late, f"no siege entry after death completed ({late[:12]})")
    check(not kcs_siege.on_map(live), "dead player is off the siege map")
    check(store2.roster_status(war2.war_id, live.player_id).eliminated, "raced death was eliminated")
    check(path2 != path, "each test store is its own file")


def _step_target(session):
    x, y = int(session.x), int(session.y)
    for dx, dy in ((0, 1), (0, -1), (1, 0), (-1, 0)):
        if kcs_siege.walkable(session, x + dx, y + dy):
            return x + dx, y + dy
    raise AssertionError(f"no walkable neighbour of {(x, y)}")


def _blocked_stand(session):
    """A walkable tile and a one-step delta that the siege map refuses."""
    for y in range(170, 210):
        for x in range(110, 170):
            if not kcs_siege.walkable(session, x, y):
                continue
            for dx, dy in ((0, 1), (0, -1), (1, 0), (-1, 0)):
                if not kcs_siege.walkable(session, x + dx, y + dy):
                    return (x, y, dx, dy)
    return None


def test_refuses_world_db_and_does_not_crown():
    world_named = os.path.join(_TMP, "world.db")
    try:
        kcs_siege.configure(world_named)
        raised = False
    except RuntimeError:
        raised = True
    check(raised, "store path named world.db is refused")
    check(not os.path.exists(world_named), "refused path was not created")
    try:
        kcs_siege.configure(os.environ["CROWNFALL_DB_PATH"])
        raised = False
    except RuntimeError:
        raised = True
    check(raised, "the live game database path is refused")
    import ast
    text = open(os.path.join(ROOT, "server", "kcs_siege.py"), encoding="utf-8").read()
    tree = ast.parse(text)
    called = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Attribute):
            called.add(node.attr)
        if isinstance(node, ast.Name):
            called.add(node.id)
    check("_crown" not in called and "castle_owners" not in called,
          "siege bridge does not call throne crowning or castle ownership")
    server_text = open(os.path.join(ROOT, "server", "server.py"), encoding="utf-8").read()
    check("await resolve_player_death(session, events, dungeon_tag)" in server_text,
          "combat tick calls the death handler")
    check("kcs_siege.record_death(session.player_id)" in server_text,
          "death handler records siege elimination")


async def test_untrusted_deploy_and_combat_tick():
    """Client plane/coordinates are not a deploy, and the combat tick itself records death."""
    flag(True)
    path, _journal = use_store()
    store, war = open_war()
    s = player()
    other = player()
    enlist(store, war, s, "attack")
    enlist(store, war, other, "defend")
    arm_live(store, war)
    origin = (int(s.x), int(s.y))
    await server.handle_enter_dungeon(s, {
        "dungeon_id": "kings_castle_siege",
        "plane": PLANE_THRONE,
        "x": 36,
        "y": 10,
        "mode": "spectator",
        "damage": 100,
    })
    check(s.dungeon is None and (s.x, s.y) == origin, "forged plane, tile, mode, and damage do not deploy")
    check(errors(s.ws)[-1] == "The siege does not accept that.", "forged deploy is refused")
    await server.handle_enter_dungeon(s, {"dungeon_id": "kings_castle_siege", "plane": PLANE_BATTLEFIELD})
    check(kcs_siege.on_map(s) and s.dungeon.get("plane") == PLANE_BATTLEFIELD, "server still deploys the battlefield")
    check(s.dungeon.get("mode") == "combatant", "client mode is not copied onto the session")

    monster = server.MonsterInstance(91001, "rat", s.x, s.y, stats={
        "hp": 500, "attack": 1, "strength": 1, "defence": 1,
        "attack_range": 8, "cone_tiles": None, "force_retaliate": False,
    })
    monster.target_player_id = s.player_id
    s.dungeon["monsters"][monster.id] = monster
    s.equipment = {}
    s.hp = 5
    s.in_combat_with = ("player", 999)
    server.process_dungeon_ai()
    check(kcs_siege.on_map(s), "siege ai skip does not eject or crash")
    seen = {}
    real = store.eliminate

    def wrapped(war_id, player_id, cause):
        seen["hp"] = s.hp
        seen["combat"] = s.in_combat_with
        seen["on_map"] = kcs_siege.on_map(s)
        return real(war_id, player_id, cause)

    store.eliminate = wrapped
    original_hit = server.combat.resolve_hit
    server.combat.resolve_hit = lambda _a, _d: (50, True)
    try:
        check(monster.can_strike(s.x, s.y), "the combat tick's monster can strike")
        await server.process_combat([])
    finally:
        server.combat.resolve_hit = original_hit
        store.eliminate = real
    check(seen.get("hp") == 0, "combat tick records the death at zero hit points")
    check(seen.get("combat") == ("player", 999), "combat tick still has kill credit when it records")
    check(seen.get("on_map") is True, "combat tick records the death before leaving the plane")
    check(not kcs_siege.on_map(s), "combat tick ejects the downed player")
    check(s.hp == s.max_hp(), "combat tick restores hit points after the siege record")
    check(store.roster_status(war.war_id, s.player_id).eliminated, "combat tick elimination is durable")

    await server.handle_enter_dungeon(other, {"dungeon_id": "kings_castle_siege"})
    check(kcs_siege.on_map(other), "a living defender can still deploy")
    store.eliminate(war.war_id, other.player_id, "test")
    check(server._apply_kcs_resume(other, resume_of(other), reason="reconnect") is False,
          "an already-attached eliminated player is not left on the map")
    check(other.dungeon is None, "the re-check clears siege presence")


async def main():
    real_world = os.path.join(ROOT, "server", "world.db")
    before = os.stat(real_world).st_mtime if os.path.exists(real_world) else None
    test_refuses_world_db_and_does_not_crown()
    await test_flag_off_and_ordinary_maps()
    await test_deploy_move_restore_and_castle_teleport()
    # The restore test logs the player out and back in. Finish that login
    # inside the test via handle_login — player_login only reloads the row.
    await test_death_ordering_denies_return()
    await test_untrusted_deploy_and_combat_tick()
    await test_persist_error_restart_and_race()
    flag(False)
    kcs_siege.close()
    after = os.stat(real_world).st_mtime if os.path.exists(real_world) else None
    check(before == after, "world.db was not modified")
    print(f"kcs integration tests ok ({CHECKS} checks)")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except Exception:
        import traceback
        traceback.print_exc()
        sys.exit(1)
