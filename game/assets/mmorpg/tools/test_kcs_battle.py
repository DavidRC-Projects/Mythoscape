"""Focused siege loop. Temporary databases only. Not the full historical suites.

Covers four-side facing, distinct engine shots, a breach that opens a tile,
siege-only elimination, a throne claim, and an idempotent sovereignty
projection that does not call throne._crown.
"""
from __future__ import annotations

import ast
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
os.environ["KCS_COOLDOWN_SCALE"] = "0"
os.environ["KCS_WAR_SECONDS"] = "1200"

import test_kcs_integration as harness  # noqa: E402
import kcs_balance  # noqa: E402
import kcs_battle  # noqa: E402

SERVER = os.path.join(ROOT, "server")
PARITY = os.path.join(SERVER, "kcs_parity")
sys.path.insert(0, PARITY)

from kings_castle_siege_map.layout import build_battlefield  # noqa: E402
from kings_castle_siege_map.placement import validate_placement  # noqa: E402

SIDES = {
    "south": (0, ("main_gate", "south_")),
    "north": (180, ("north_gate", "north_")),
    "west": (90, ("west_gate", "west_wall")),
    "east": (270, ("east_gate", "east_wall")),
}


def server_cells():
    """The same gate cells the server aims at, not the whole opening rectangle."""
    smap = harness.kcs_siege.siege_map()
    pdata = smap.plane(harness.kcs_siege.PLANE_BATTLEFIELD)
    found = {}
    for oid in pdata.opening_ids:
        cells = [tuple(tile) for tile, owner in pdata.opening_at.items() if owner == oid]
        if cells:
            found[oid] = cells
    return found


def on_side(oid, hints):
    return any(oid == hint or oid.startswith(hint) for hint in hints)


def find_shot(bf, cells, kind, side):
    rot, hints = SIDES[side]
    ww, wn, we, ws = bf.wall_box
    bands = {
        "south": (ww - 20, ws + 1, we + 20, min(bf.plane.height - 2, ws + 48)),
        "north": (ww - 20, max(2, wn - 48), we + 20, wn - 1),
        "west": (max(2, ww - 48), wn + 8, ww - 1, ws - 8),
        "east": (we + 1, wn + 8, min(bf.plane.width - 2, we + 48), ws - 8),
    }
    x0, y0, x1, y1 = bands[side]
    for y in range(y0, y1):
        for x in range(x0, x1):
            res = validate_placement(bf, kind, x, y, rot, [])
            if not res.ok:
                continue
            hit = kcs_balance.shot_target(res.tiles, rot, kind, cells)
            if hit and on_side(hit[0], hints):
                return (x, y, rot, hit[0])
    return None


async def main():
    live_world = os.path.join(ROOT, "server", "world.db")
    live_kcs = os.path.join(ROOT, "server", "kcs_siege.db")
    before = (
        os.path.getsize(live_world) if os.path.exists(live_world) else None,
        os.path.getmtime(live_world) if os.path.exists(live_world) else None,
        os.path.getsize(live_kcs) if os.path.exists(live_kcs) else None,
        os.path.getmtime(live_kcs) if os.path.exists(live_kcs) else None,
    )
    text = open(os.path.join(SERVER, "kcs_battle.py"), encoding="utf-8").read()
    tree = ast.parse(text)
    called = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
            called.add(node.func.attr)
    harness.check("_crown" not in called, "the battle loop does not call throne._crown")

    harness.flag(False)
    harness.feature_flags.USE_KINGS_CASTLE_SOVEREIGNTY = False
    closed = kcs_battle.enlist(harness.player(), "attack")
    harness.check(closed.get("ok") is False and "closed" in closed.get("error", "").lower(),
                  "flag off: enlist is refused")

    harness.flag(True)
    path, _journal = harness.use_store()
    bf = build_battlefield()
    cells = server_cells()
    found = {}
    for side in SIDES:
        for kind in kcs_balance.ENGINES:
            spot = find_shot(bf, cells, kind, side)
            harness.check(spot is not None, f"{kind} can face a {side} opening")
            if spot:
                harness.check(spot[2] == SIDES[side][0], f"{kind} on the {side} uses rotation {SIDES[side][0]}")
                found[(kind, side)] = spot

    store, war = harness.open_war()
    attacker = harness.player()
    defender = harness.player()
    attacker.coins = 80
    defender.coins = 50
    harness.enlist(store, war, attacker, "attack")
    harness.enlist(store, war, defender, "defend")
    started = kcs_battle.begin(attacker)
    harness.check(started.get("status") == "active", "begin makes the siege live without a manual database edit")
    await harness.server.handle_enter_dungeon(attacker, {"dungeon_id": "kings_castle_siege"})
    await harness.server.handle_enter_dungeon(defender, {"dungeon_id": "kings_castle_siege"})
    harness.check(harness.kcs_siege.on_map(attacker) and harness.kcs_siege.on_map(defender),
                  "attacker and defender both deploy")

    ram = found[("ram", "south")]
    placed = harness.kcs_siege.propose_placement(attacker, {
        "engine_type": "ram", "x": ram[0], "y": ram[1], "rotation": ram[2], "request_id": "ram-south",
    })
    harness.check(placed.get("ok"), f"south-facing ram places ({placed.get('error')})")
    harness.check(placed["engine"]["rotation"] == 0, "the placed ram keeps the north-facing rotation")
    xp = harness.W.db.conn.execute(
        "SELECT engineering_xp FROM players WHERE id=?", (attacker.player_id,)).fetchone()[0]
    harness.check(int(xp or 0) >= kcs_balance.xp_place(), "placement grants the existing engineering skill")

    for kind, side in (("trebuchet", "south"), ("siege_tower", "west"), ("ladder", "east")):
        spot = found[(kind, side)]
        body = harness.kcs_siege.propose_placement(attacker, {
            "engine_type": kind, "x": spot[0], "y": spot[1], "rotation": spot[2],
            "request_id": f"{kind}-{side}",
        })
        harness.check(body.get("ok"), f"{kind} places on the {side} ({body.get('error')})")
        before_hp = store.opening_hps(war.war_id).get(spot[3])
        shot = kcs_battle.fire(attacker, kind)
        harness.check(shot.get("ok"), f"{kind} fires ({shot.get('error')})")
        harness.check(on_side(shot["opening"]["opening_id"], SIDES[side][1]),
                      f"{kind} hits a {side} opening, not a different wall")
        after_hp = shot["opening"]["hp"]
        if before_hp is not None:
            harness.check(after_hp < before_hp, f"{kind} reduces opening hp")

    destroyed = None
    for _ in range(12):
        shot = kcs_battle.fire(attacker, "ram")
        harness.check(shot.get("ok"), f"ram fires ({shot.get('error')})")
        if shot.get("opening", {}).get("state") == "destroyed":
            destroyed = shot["opening"]
            break
    harness.check(destroyed is not None, "repeated ram shots breach an opening")
    oid = destroyed["opening_id"]
    tile = cells[oid][0]
    attacker.x, attacker.y = tile
    harness.check(harness.kcs_siege.walkable(attacker, tile[0], tile[1]),
                  "a destroyed opening is no longer solid")

    refused = kcs_battle.fire(defender, "ram")
    harness.check(refused.get("ok") is False, "a defender cannot fire an attack engine")
    bad = harness.kcs_siege.propose_placement(defender, {
        "engine_type": "ram", "x": ram[0] + 8, "y": ram[1], "rotation": 0, "request_id": "def-ram",
    })
    harness.check(bad.get("ok") is False, "a defender cannot place an engine")

    defender.coins = 50
    attacker.hp = 8
    defender.x, defender.y = attacker.x, attacker.y
    swing = kcs_battle.strike(defender)
    harness.check(swing.get("ok") and swing.get("killed"), f"a siege strike can drop an attacker ({swing})")
    await harness.server.resolve_player_death(attacker, [])
    harness.check(not harness.kcs_siege.on_map(attacker), "the killed attacker is removed")
    harness.check(store.roster_status(war.war_id, attacker.player_id).eliminated, "the death is an elimination")
    await harness.server.handle_enter_dungeon(attacker, {"dungeon_id": "kings_castle_siege"})
    harness.check(not harness.kcs_siege.on_map(attacker), "an eliminated attacker cannot deploy again")
    harness.check(defender.coins == 50, "winning the fight does not take the defender's gold")

    # A second war for the throne claim, so the elimination victory above can stand.
    path2, _j = harness.use_store()
    store, war = harness.open_war()
    claimant = harness.player()
    claimant.coins = 100
    harness.enlist(store, war, claimant, "attack")
    kcs_battle.begin(claimant)
    await harness.server.handle_enter_dungeon(claimant, {"dungeon_id": "kings_castle_siege"})
    keep = harness.kcs_siege.siege_map().plane(harness.kcs_siege.PLANE_BATTLEFIELD).opening_rects["keep_doors"]
    harness.check(harness.kcs_siege.transition_at(harness.kcs_siege.PLANE_BATTLEFIELD, keep[0], keep[1]) is None,
                  "intact keep doors do not open the throne")
    store.write_repair(war.war_id, "keep_doors", 0, "destroyed")
    link = harness.kcs_siege.transition_at(harness.kcs_siege.PLANE_BATTLEFIELD, keep[0], keep[1])
    harness.check(link == harness.kcs_siege.PLANE_THRONE, "a breached keep opens the throne room")
    await harness.server._kcs_change_plane(claimant, harness.kcs_siege.PLANE_THRONE)
    harness.check((claimant.dungeon or {}).get("plane") == harness.kcs_siege.PLANE_THRONE,
                  "the attacker can enter the throne room")
    dais = harness.kcs_siege.siege_map().plane(harness.kcs_siege.PLANE_THRONE).spawn["dais"]
    claimant.x, claimant.y = int(dais[0]), int(dais[1])
    harness.feature_flags.USE_KINGS_CASTLE_SOVEREIGNTY = False
    first = kcs_battle.claim(claimant)
    harness.check(first.get("finished") and first.get("winner") == "attack", "the claim records an attacker victory")
    harness.check(claimant.coins == 100, "taking the castle does not change gold")
    harness.check(first.get("projected") is None, "projection stays off with its own flag")
    again = kcs_battle._finish(store, war.war_id, "defend", None, "timeout")
    harness.check(again.get("duplicate") and again.get("winner") == "attack",
                  "a retried result cannot crown the other side")
    harness.feature_flags.USE_KINGS_CASTLE_SOVEREIGNTY = True
    applied = kcs_battle.project(store, war.war_id)
    harness.check(applied == "applied", "the projector applies the one result")
    harness.check(kcs_battle.project(store, war.war_id) == "already_applied",
                  "a restart of the projector does not apply a second crown")
    harness.check(store.sovereignty()["source_war_id"] == war.war_id, "sovereignty points at that war only")
    harness.feature_flags.USE_KINGS_CASTLE_SOVEREIGNTY = False

    realm = harness.player()
    realm.x, realm.y = 9, 28
    await harness.server.handle_enter_dungeon(realm, {"dungeon_id": "castle_realm"})
    harness.check(realm.dungeon and realm.dungeon.get("id") == "castle_realm",
                  "Castle Realm still opens while the new siege flag is on")
    harness.check(os.path.basename(path) != "world.db" and os.path.basename(path2) != "world.db",
                  "siege files are not world.db")
    after = (
        os.path.getsize(live_world) if os.path.exists(live_world) else None,
        os.path.getmtime(live_world) if os.path.exists(live_world) else None,
        os.path.getsize(live_kcs) if os.path.exists(live_kcs) else None,
        os.path.getmtime(live_kcs) if os.path.exists(live_kcs) else None,
    )
    harness.check(before == after, "preexisting live database files were not opened or replaced")
    print(f"kcs battle tests ok ({harness.CHECKS} checks)")


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
