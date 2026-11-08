"""Siege sync, authority, and stale-message regressions.

Temporary databases only. The game database is the harness memory file.
"""
from __future__ import annotations

import asyncio
import os
import sys
import threading

os.environ["SDL_VIDEODRIVER"] = "dummy"
os.environ["SDL_AUDIODRIVER"] = "dummy"
os.environ["KCS_COOLDOWN_SCALE"] = "0"
os.environ["KCS_WAR_SECONDS"] = "1200"

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(ROOT, "client"))

import importlib.util  # noqa: E402

import test_kcs_integration as harness  # noqa: E402

sys.path.insert(0, os.path.join(ROOT, "client"))
import kcs_battle  # noqa: E402
import kcs_client  # noqa: E402
import kcs_siege  # noqa: E402
import kcs_sync  # noqa: E402

_net_spec = importlib.util.spec_from_file_location(
    "kcs_network_under_test", os.path.join(ROOT, "client", "network.py"),
)
_net = importlib.util.module_from_spec(_net_spec)
_net_spec.loader.exec_module(_net)
NetworkClient = _net.NetworkClient

check = harness.check
flag = harness.flag
player = harness.player
use_store = harness.use_store
open_war = harness.open_war
enlist = harness.enlist
arm_live = harness.arm_live
server = harness.server
PLANE_BATTLEFIELD = harness.PLANE_BATTLEFIELD
PLANE_THRONE = harness.PLANE_THRONE


def messages(session, kind):
    return [row for row in session.ws.sent if row.get("type") == kind]


class Net:
    def __init__(self):
        self.connected = True
        self.sent = []

    def send(self, kind, **fields):
        self.sent.append({"type": kind, **fields})


class App:
    def __init__(self):
        self.dungeon = {"id": "kings_castle_siege", "mode": "combatant"}
        self.net = Net()
        self.players = {2: {"id": 2, "hp": 20, "x": 1, "y": 1}}
        self.player = {"id": 1}
        self.chat = []

    def add_chat(self, text, color=None):
        self.chat.append(text)


def test_client_drops_stale_and_duplicate_updates():
    app = App()
    kcs_client.on_message(app, "KCS_SNAPSHOT", {
        "type": "KCS_SNAPSHOT",
        "war_id": 4,
        "sync_seq": 3,
        "your_side": "attack",
        "openings": [{"id": "main_gate", "state": "intact", "rev": 2, "hp": 140}],
        "engines": [{"engine_id": 7, "hp": 40, "rev": 1, "rotation": 0}],
        "eliminated": [9],
    })
    view = app.kcs_view
    check(view.sync_seq == 3 and 9 in view.eliminated, "snapshot is the ordered baseline")
    check(not view.stale, "a snapshot clears the reconnecting pause")

    kcs_client.on_message(app, "KCS_DELTA", {
        "type": "KCS_DELTA", "seq": 4, "war_id": 4, "kind": "engine_hp",
        "engine_id": 7, "hp": 11,
    })
    check(view.engines[0]["hp"] == 11 and view.sync_seq == 4, "the next delta applies")
    kcs_client.on_message(app, "KCS_DELTA", {
        "type": "KCS_DELTA", "seq": 4, "war_id": 4, "kind": "engine_hp",
        "engine_id": 7, "hp": 40,
    })
    check(view.engines[0]["hp"] == 11, "a duplicate delta does not restore hit points")
    kcs_client.on_message(app, "KCS_DELTA", {
        "type": "KCS_DELTA", "seq": 2, "war_id": 4, "kind": "engine_hp",
        "engine_id": 7, "hp": 80,
    })
    check(view.engines[0]["hp"] == 11, "an older delta does not restore hit points")
    kcs_client.on_message(app, "KCS_DELTA", {
        "type": "KCS_DELTA", "seq": 5, "war_id": 4, "kind": "engine_removed",
        "engine_id": 7,
    })
    check(view.engines == [] and 7 in view.removed, "packing removes the engine")
    kcs_client.on_message(app, "KCS_DELTA", {
        "type": "KCS_DELTA", "seq": 3, "war_id": 4, "kind": "engine",
        "engine": {"engine_id": 7, "hp": 40, "engine_type": "ram"},
    })
    check(view.engines == [], "a late place does not restore a packed engine")
    kcs_client.on_message(app, "KCS_DELTA", {
        "type": "KCS_DELTA", "seq": 6, "war_id": 4, "kind": "engine",
        "engine": {"engine_id": 7, "hp": 40, "engine_type": "ram"},
    })
    check(view.engines == [], "a newer place for a packed id stays removed until a snapshot")
    kcs_client.on_message(app, "KCS_DELTA", {
        "type": "KCS_DELTA", "seq": 7, "war_id": 4, "kind": "opening",
        "opening_id": "main_gate", "state": "damaged", "rev": 1, "hp": 200,
    })
    gate = view.openings[0]
    check(gate["rev"] == 2 and gate["hp"] == 140, "a lower opening rev cannot raise the gate")
    kcs_client.on_message(app, "KCS_DELTA", {
        "type": "KCS_DELTA", "seq": 8, "war_id": 4, "kind": "eliminated", "player_id": 2,
    })
    check(2 in view.eliminated and 2 not in app.players, "an eliminated player leaves the field")
    kcs_client.on_message(app, "KCS_DELTA", {
        "type": "KCS_DELTA", "seq": 9, "war_id": 4, "kind": "player_hp",
        "player_id": 2, "hp": 20,
    })
    check(2 not in app.players, "a later hit-point update does not restore an eliminated player")
    before = len(app.net.sent)
    kcs_client.on_message(app, "KCS_DELTA", {
        "type": "KCS_DELTA", "seq": 12, "war_id": 4, "kind": "engine_hp",
        "engine_id": 7, "hp": 1,
    })
    check(view.stale and view.engines == [], "a sequence gap does not apply the skipped update")
    check(app.net.sent[before:] and app.net.sent[-1]["type"] == "KCS_SNAPSHOT",
          "a sequence gap asks for one snapshot")
    kcs_client.on_message(app, "KCS_DELTA", {
        "type": "KCS_DELTA", "seq": 99, "war_id": 9, "kind": "engine",
        "engine": {"engine_id": 1, "hp": 5},
    })
    check(view.engines == [], "a delta from another war is ignored")

    view.stale = True
    kcs_client._button(app, "fire")
    check(not any(row["type"] == "KCS_ACT" for row in app.net.sent),
          "a stale client does not fire")
    app.dungeon["mode"] = "spectator"
    view.stale = False
    view.sync_seq = 8
    kcs_client._button(app, "claim")
    check(not any(row["type"] == "KCS_CLAIM" for row in app.net.sent),
          "a spectator client does not claim")

    link = NetworkClient("ws://127.0.0.1:9")
    for i in range(70):
        link.send("MOVE", dx=1, dy=0, n=i)
    check(link.outgoing.qsize() == 64, "the outgoing queue stops at 64")
    behind = []
    while True:
        try:
            behind.append(link.incoming.get_nowait())
        except Exception:
            break
    check(any(row.get("type") == "_LINK_BEHIND" for row in behind),
          "a full queue tells the player the link is behind")


def _ram_spot():
    parity = os.path.join(ROOT, "server", "kcs_parity")
    if parity not in sys.path:
        sys.path.insert(0, parity)
    from kings_castle_siege_map.layout import build_battlefield
    from kings_castle_siege_map.placement import validate_placement
    bf = build_battlefield()
    for y in range(150, 210):
        for x in range(80, 180):
            res = validate_placement(bf, "ram", x, y, 0, [])
            if res.ok:
                return x, y
    raise AssertionError("no ram tile")


async def _live_pair():
    flag(True)
    use_store()
    store, war = open_war()
    attacker = player("synca")
    other = player("synco")
    defender = player("syncd")
    far = player("syncf")
    enlist(store, war, attacker, "attack")
    enlist(store, war, other, "attack")
    enlist(store, war, defender, "defend")
    enlist(store, war, far, "attack")
    arm_live(store, war)
    for session in (attacker, other, defender, far):
        await server.handle_enter_dungeon(session, {"dungeon_id": "kings_castle_siege"})
        check(kcs_siege.on_map(session), f"{session.char_name} deployed")
    return store, war, attacker, other, defender, far


async def test_visibility_sequence_and_authority():
    store, war, attacker, other, defender, far = await _live_pair()
    snap = messages(attacker, "KCS_SNAPSHOT")[-1]
    check(isinstance(snap.get("sync_seq"), int) and snap.get("eliminated") == [],
          "deploy snapshot carries a sequence and an empty eliminated list")
    attacker.x, attacker.y = 120, 120
    defender.x, defender.y = 124, 121
    far.x, far.y = 20, 20
    visible = server._kcs_visible_players(attacker, server._kcs_player_pool())
    ids = {row["id"] for row in visible}
    check(attacker.player_id in ids and defender.player_id in ids,
          "nearby fighters are in the siege player list")
    check(far.player_id not in ids, "a fighter outside the interest radius is left out")
    sides = {row["id"]: row.get("kcs_side") for row in visible}
    check(sides[attacker.player_id] == "attack" and sides[defender.player_id] == "defend",
          "the player list carries the server side")
    me = next(row for row in visible if row["id"] == attacker.player_id)
    check(me.get("hp") == attacker.hp, "the player list carries hit points")

    before_far = len(far.ws.sent)
    await server._publish_kcs_combat({
        "engines": [{"engine_id": 1, "hp": 9}],
        "shot": {"engine_id": 1, "x": 120, "y": 120, "tx": 120, "ty": 110},
        "players": [{"player_id": defender.player_id, "hp": 4, "killed": True, "damage": 99}],
    }, attacker)
    far_new = far.ws.sent[before_far:]
    near_new = [row for row in attacker.ws.sent if row.get("type") == "KCS_DELTA"]
    check(near_new and near_new[-1].get("events"), "a shot is one nearby delta")
    kinds = {ev.get("kind") for ev in near_new[-1]["events"]}
    check("engine_hp" in kinds and "shot" in kinds, "the nearby delta has hit points and the shot")
    check("player_hp" not in kinds, "a killing blow is not applied as a client-chosen wound")
    check(not any(row.get("type") == "KCS_DELTA" and row.get("seq") == near_new[-1]["seq"]
                  for row in far_new),
          "the far fighter does not receive that shot")
    await server._broadcast_kcs(
        "KCS_DELTA", kind="opening", opening_id="main_gate", state="damaged", rev=1, hp=20,
    )
    check(any(row.get("kind") == "opening" for row in far.ws.sent if row.get("type") == "KCS_DELTA"),
          "a gate change still reaches a fighter across the field")

    x, y = _ram_spot()
    placed = await server.handle_kcs_place(attacker, {
        "engine_type": "ram", "x": x, "y": y, "rotation": 0, "request_id": "sync-ram",
    })
    del placed
    engines = store.engines(war.war_id)
    check(len(engines) == 1, "one ram was placed")
    both = [
        messages(attacker, "KCS_DELTA"),
        messages(defender, "KCS_DELTA"),
    ]
    check(all(any(row.get("kind") == "engine" for row in rows) for rows in both),
          "both sides receive the placed engine")
    check(all(isinstance(row.get("seq"), int) for row in both[0] if row.get("kind") == "engine"),
          "the place delta has a sequence")

    store.eliminate(war.war_id, far.player_id, "test")
    body = kcs_siege.snapshot(attacker)
    check(far.player_id in body["eliminated"], "a snapshot lists eliminated fighters")
    check(engines[0].engine_id in {row["engine_id"] for row in body["engines"]},
          "elimination does not delete someone else's engine")

    defender.dungeon["mode"] = "spectator"
    await server.handle_kcs_act(defender, {"engine_type": "ballista"})
    check(any("spectator" in (row.get("message") or "").lower() for row in defender.ws.sent
              if row.get("type") == "ERROR"),
          "a spectator cannot fire")
    defender.dungeon["mode"] = "combatant"
    await server.handle_kcs_act(attacker, {
        "engine_type": "ram", "damage": 999, "hp": 1, "owner": 1,
        "side": "defend", "eliminated": 0, "cost": 0,
    })
    check(any(row.get("message") == "The siege does not accept that."
              for row in attacker.ws.sent if row.get("type") == "ERROR"),
          "the client cannot choose damage, cost, owner, side, or elimination")
    await server.handle_kcs_opening(attacker, {"opening_id": "main_gate", "state": "destroyed", "hp": 0})
    check(any("structure" in (row.get("message") or "").lower() for row in attacker.ws.sent
              if row.get("type") == "ERROR"),
          "the client cannot order a breach")

    packs = []

    def pack_once():
        try:
            packs.append(kcs_battle.pack(attacker, "ram"))
        except Exception as exc:
            packs.append({"ok": False, "error": str(exc)})

    threads = [threading.Thread(target=pack_once) for _ in range(2)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    check(sum(1 for row in packs if row.get("ok")) == 1, f"one pack wins ({packs})")
    check(store.engines(war.war_id) == [], "the ram is packed once")

    for session in (attacker, other):
        session.dungeon["plane"] = PLANE_THRONE
        session.dungeon["mode"] = "combatant"
        session.x, session.y = 36, 10
    await server.apply_kcs_opening("keep_doors", "destroyed")
    claims = []

    def claim_once(session):
        try:
            claims.append(kcs_battle.claim(session))
        except Exception as exc:
            claims.append({"ok": False, "error": str(exc)})

    threads = [threading.Thread(target=claim_once, args=(session,)) for session in (attacker, other)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    finished = [row for row in claims if row.get("finished")]
    check(len(finished) == 1 and finished[0].get("winner") == "attack",
          f"one claim finishes the war ({claims})")
    check(store.result(war.war_id).get("winner_side") == "attack", "one result row is stored")
    again = kcs_battle.claim(attacker)
    check(again.get("duplicate") or not again.get("finished"), "a second claim does not crown again")


async def main():
    world = os.path.join(ROOT, "server", "world.db")
    before = os.stat(world).st_mtime if os.path.exists(world) else None
    test_client_drops_stale_and_duplicate_updates()
    await test_visibility_sequence_and_authority()
    flag(False)
    kcs_siege.close()
    check(harness.feature_flags.USE_KINGS_CASTLE_SIEGE is False, "the siege flag is off again")
    check(kcs_sync.interest_radius() == 24 and kcs_sync.interest_cap() == 100,
          "interest still uses the existing 24-tile, 100-fighter fan-out")
    after = os.stat(world).st_mtime if os.path.exists(world) else None
    check(before == after, "the worktree world.db was not touched")
    print(f"{harness.CHECKS} checks passed")


if __name__ == "__main__":
    asyncio.run(main())
