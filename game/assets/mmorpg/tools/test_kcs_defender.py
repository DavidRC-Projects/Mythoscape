"""Defender siege equipment. Temporary databases only.

Allowed and refused placement, firing, attacker counterplay, restart,
flag-off isolation, and a throne result that still cannot be replayed
onto the other side.
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
from kings_castle_siege_map.placement import find_valid_on_side, validate_placement  # noqa: E402

OUTWARD = {"south": 180, "north": 0, "west": 270, "east": 90}


def server_cells():
    smap = harness.kcs_siege.siege_map()
    pdata = smap.plane(harness.kcs_siege.PLANE_BATTLEFIELD)
    found = {}
    for oid in pdata.opening_ids:
        cells = [tuple(tile) for tile, owner in pdata.opening_at.items() if owner == oid]
        if cells:
            found[oid] = cells
    return found


def stand_beside(session, tiles):
    """A walkable tile next to the equipment, on the bailey side when possible."""
    cx = int(sum(t[0] for t in tiles) / len(tiles))
    cy = int(sum(t[1] for t in tiles) / len(tiles))
    for dist in range(1, 4):
        for dx, dy in ((0, -1), (0, 1), (-1, 0), (1, 0), (1, -1), (-1, -1), (1, 1), (-1, 1)):
            x, y = cx + dx * dist, cy + dy * dist
            session.x, session.y = x, y
            if kcs_balance.beside(x, y, tiles) and harness.kcs_siege.walkable(session, x, y):
                return x, y
    raise AssertionError(f"no place to stand beside {tiles[0]}")


def find_defense(bf, kind, side, existing=()):
    rot = OUTWARD[side]
    ww, wn, we, ws = bf.wall_box
    bands = {
        "south": (ww + 6, ws - 6, we - 8, ws - 3),
        "north": (ww + 6, wn + 3, we - 8, wn + 7),
        "west": (ww + 3, wn + 8, ww + 7, ws - 8),
        "east": (we - 7, wn + 8, we - 3, ws - 8),
    }
    x0, y0, x1, y1 = bands[side]
    for y in range(y0, y1 + 1):
        for x in range(x0, x1 + 1):
            res = validate_placement(bf, kind, x, y, rot, existing)
            if res.ok:
                return x, y, rot, res.tiles
    return None


def find_ram(bf, cells):
    ww, _wn, we, ws = bf.wall_box
    for y in range(ws + 1, ws + 14):
        for x in range(ww, we):
            res = validate_placement(bf, "ram", x, y, 0, [])
            if not res.ok:
                continue
            hit = kcs_balance.shot_target(res.tiles, 0, "ram", cells)
            if hit and hit[0] == "main_gate":
                return x, y, 0, res.tiles, hit[0]
    return None


def messages(session, kind):
    return [row for row in session.ws.sent if row.get("type") == kind]


async def place(session, body):
    session.ws.sent.clear()
    await harness.server.handle_kcs_place(session, body)
    return messages(session, "KCS_PLACE_OK"), [row.get("message") for row in messages(session, "ERROR")]


async def main():
    live_world = os.path.join(SERVER, "world.db")
    live_kcs = os.path.join(SERVER, "kcs_siege.db")
    before = (
        os.path.getsize(live_world) if os.path.exists(live_world) else None,
        os.path.getmtime(live_world) if os.path.exists(live_world) else None,
        os.path.getsize(live_kcs) if os.path.exists(live_kcs) else None,
        os.path.getmtime(live_kcs) if os.path.exists(live_kcs) else None,
    )
    text = open(os.path.join(SERVER, "kcs_battle.py"), encoding="utf-8").read()
    called = set()
    for node in ast.walk(ast.parse(text)):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
            called.add(node.func.attr)
    harness.check("_crown" not in called, "defender combat does not call throne._crown")

    harness.flag(False)
    harness.feature_flags.USE_KINGS_CASTLE_SOVEREIGNTY = False
    closed = kcs_battle.fire(harness.player(), "ballista")
    harness.check(closed.get("ok") is False and "closed" in closed.get("error", "").lower(),
                  "flag off: a ballista cannot fire")
    closed_place = harness.kcs_siege.propose_placement(harness.player(), {
        "engine_type": "ballista", "x": 1, "y": 1, "rotation": 180, "request_id": "off",
    })
    harness.check(closed_place.get("ok") is False, "flag off: placement does not open a siege")

    harness.flag(True)
    path, _journal = harness.use_store()
    bf = build_battlefield()
    cells = server_cells()
    for side in OUTWARD:
        for kind in ("ballista", "cauldron"):
            spot = find_defense(bf, kind, side)
            harness.check(spot is not None, f"a {kind} fits the {side} wall-walk")
            if spot:
                center = (sum(t[0] for t in spot[3]) / len(spot[3]), sum(t[1] for t in spot[3]) / len(spot[3]))
                harness.check(
                    kcs_balance.outward_rotation(center[0], center[1], bf.wall_box) == spot[2],
                    f"{side} {kind} facing matches the outward control",
                )

    store, war = harness.open_war()
    attacker = harness.player()
    defender = harness.player()
    outsider = harness.player()
    attacker.coins = 70
    defender.coins = 40
    outsider.coins = 15
    harness.enlist(store, war, attacker, "attack")
    harness.enlist(store, war, defender, "defend")
    harness.enlist(store, war, outsider, "defend")
    started = kcs_battle.begin(defender)
    harness.check(started.get("status") == "active", "the defender can begin the siege")
    sov_rev = store.sovereignty()["rev"]
    await harness.server.handle_enter_dungeon(attacker, {"dungeon_id": "kings_castle_siege"})
    await harness.server.handle_enter_dungeon(defender, {"dungeon_id": "kings_castle_siege"})
    harness.check(harness.kcs_siege.on_map(defender), "defender deploys onto the siege")

    ram = find_ram(bf, cells)
    harness.check(ram is not None, "a ram still has a south gate placement")
    ballista = None
    for y in range(bf.wall_box[1], bf.wall_box[3]):
        for x in range(ram[0] - 6, ram[0] + 8):
            res = validate_placement(bf, "ballista", x, y, 180, [])
            if not res.ok:
                continue
            aimed = kcs_balance.aimed_target(res.tiles, 180, "ballista", [("ram", ram[3])])
            if aimed:
                ballista = (x, y, 180, res.tiles)
                break
        if ballista:
            break
    harness.check(ballista is not None, "a south ballista can aim at that ram")
    cauldron = None
    from kings_castle_siege_map.placement import PlacedEngine
    existing = [
        PlacedEngine("ram", "ram", ram[0], ram[1], 0),
        PlacedEngine("ballista", "ballista", ballista[0], ballista[1], 180),
    ]
    gate_cells = cells["main_gate"]
    for y in range(bf.wall_box[1], bf.wall_box[3]):
        for x in range(ram[0] - 14, ram[0] + 16):
            res = validate_placement(bf, "cauldron", x, y, 180, existing)
            if not res.ok:
                continue
            if any(max(abs(tx - gx), abs(ty - gy)) <= 1
                   for tx, ty in res.tiles for gx, gy in gate_cells):
                cauldron = (x, y, 180, res.tiles)
                break
        if cauldron:
            break
    harness.check(cauldron is not None, "a cauldron fits on the main gate beside that ballista")

    stand_beside(defender, ballista[3])
    bad_far = await place(defender, {
        "engine_type": "ballista", "x": ballista[0], "y": ballista[1] + 40,
        "rotation": 180, "request_id": "far-wall",
    })
    # The far coordinate is rejected by the wall rule or by range. Either denial is a refusal.
    harness.check(not bad_far[0], "a defender cannot build off the wall-walk")

    saved = (defender.x, defender.y)
    defender.x, defender.y = 20, 20
    too_far, too_far_err = await place(defender, {
        "engine_type": "ballista", "x": ballista[0], "y": ballista[1],
        "rotation": 180, "request_id": "too-far",
    })
    harness.check(not too_far and any("wall" in (e or "").lower() for e in too_far_err),
                  f"building requires standing at the wall ({too_far_err})")
    defender.x, defender.y = saved

    inward, inward_err = await place(defender, {
        "engine_type": "ballista", "x": ballista[0], "y": ballista[1],
        "rotation": 0, "request_id": "inward",
    })
    harness.check(not inward and any("face" in (e or "").lower() for e in inward_err),
                  f"a ballista facing into the bailey is refused ({inward_err})")

    ram_denied, ram_err = await place(defender, {
        "engine_type": "ram", "x": ram[0], "y": ram[1], "rotation": 0, "request_id": "def-ram",
    })
    harness.check(not ram_denied and any("cannot place" in (e or "").lower() for e in ram_err),
                  "a defender cannot place a ram")
    atk_denied, atk_err = await place(attacker, {
        "engine_type": "ballista", "x": ballista[0], "y": ballista[1],
        "rotation": 180, "request_id": "atk-ballista",
    })
    harness.check(not atk_denied and any("cannot place" in (e or "").lower() for e in atk_err),
                  "an attacker cannot place a ballista")
    out_ok, out_err = await place(outsider, {
        "engine_type": "ballista", "x": ballista[0], "y": ballista[1],
        "rotation": 180, "request_id": "not-deployed",
    })
    harness.check(not out_ok, f"a player who never deployed cannot build ({out_err})")

    defender.dungeon["mode"] = "spectator"
    spec_ok, spec_err = await place(defender, {
        "engine_type": "ballista", "x": ballista[0], "y": ballista[1],
        "rotation": 180, "request_id": "spec",
    })
    harness.check(not spec_ok and any("here" in (e or "").lower() or "spectator" in (e or "").lower() for e in spec_err),
                  f"a spectator cannot build ({spec_err})")
    defender.dungeon["mode"] = "combatant"
    defender.hp = 0
    dead_ok, dead_err = await place(defender, {
        "engine_type": "ballista", "x": ballista[0], "y": ballista[1],
        "rotation": 180, "request_id": "dead",
    })
    harness.check(not dead_ok, f"a downed defender cannot build ({dead_err})")
    defender.hp = defender.max_hp()

    placed, placed_err = await place(defender, {
        "engine_type": "ballista", "x": ballista[0], "y": ballista[1],
        "rotation": 180, "request_id": "ballista-1",
    })
    harness.check(placed, f"defender places a ballista ({placed_err})")
    harness.check(placed[0]["engine"]["side"] == "defend", "the stored ballista belongs to the defence")
    harness.check(any(m.get("kind") == "engine" for m in messages(attacker, "KCS_DELTA")),
                  "the attacker receives the placement delta")

    ram_ok, ram_place_err = await place(attacker, {
        "engine_type": "ram", "x": ram[0], "y": ram[1], "rotation": 0, "request_id": "ram-1",
    })
    harness.check(ram_ok, f"attacker ram still places ({ram_place_err})")
    gate_before = store.opening_hps(war.war_id).get("main_gate")
    stand_beside(defender, ballista[3])
    shot = kcs_battle.fire(defender, "ballista")
    harness.check(shot.get("ok"), f"ballista fires ({shot.get('error')})")
    harness.check("ram" in shot.get("text", ""), f"ballista hits the ram ({shot.get('text')})")
    ram_hp = store.engine_combat_map(war.war_id)
    ram_id = ram_ok[0]["engine"]["engine_id"]
    harness.check(ram_hp[ram_id][0] < kcs_balance.ENGINES["ram"]["hp"], "the ram loses hp")
    harness.check(store.opening_hps(war.war_id).get("main_gate") == gate_before,
                  "a ballista does not damage the gate")
    os.environ["KCS_COOLDOWN_SCALE"] = "30"
    held = kcs_battle.fire(defender, "ballista")
    harness.check(held.get("ok"), f"the ballista fires before its long reload ({held.get('error')})")
    reloading = kcs_battle.fire(defender, "ballista")
    harness.check(reloading.get("ok") is False and "reload" in reloading.get("error", "").lower(),
                  f"the ballista respects its cooldown ({reloading})")
    os.environ["KCS_COOLDOWN_SCALE"] = "0"
    store.write_engine_action(
        war.war_id, placed[0]["engine"]["engine_id"],
        kcs_balance.DEFENDER_ENGINES["ballista"]["hp"], 0.0, [])
    again = kcs_battle.fire(defender, "ballista")
    harness.check(again.get("ok"), f"the ballista fires again once reloaded ({again.get('error')})")

    stolen = kcs_battle.pack(attacker, "ballista")
    harness.check(stolen.get("ok") is False, "an attacker cannot pack a defender's ballista")
    packed = kcs_battle.pack(defender, "ballista")
    harness.check(packed.get("ok"), f"the owner packs the ballista ({packed.get('error')})")
    harness.check(all(e.engine_id != placed[0]["engine"]["engine_id"] for e in store.engines(war.war_id)),
                  "packing removes that ballista")

    stand_beside(defender, ballista[3])
    replaced, replace_err = await place(defender, {
        "engine_type": "ballista", "x": ballista[0], "y": ballista[1],
        "rotation": 180, "request_id": "ballista-2",
    })
    harness.check(replaced, f"the ballista can be built again ({replace_err})")
    defender.x, defender.y = 24, 24
    attacker.x, attacker.y = ballista[3][0]
    struck = kcs_battle.strike(attacker)
    harness.check(struck.get("engine_id") == replaced[0]["engine"]["engine_id"],
                  f"an attacker can strike the ballista ({struck})")
    hurt = store.engine_combat_map(war.war_id)[replaced[0]["engine"]["engine_id"]][0]
    harness.check(hurt < kcs_balance.DEFENDER_ENGINES["ballista"]["hp"], "the strike is stored")
    attacker.x, attacker.y = ram[0], ram[1]
    harness.kcs_siege.simulate_restart()
    store = harness.kcs_siege.store()
    snap = harness.kcs_siege.snapshot(defender)
    restored = [e for e in snap["engines"] if e["engine_id"] == replaced[0]["engine"]["engine_id"]]
    harness.check(restored and restored[0]["hp"] == hurt and restored[0]["side"] == "defend",
                  "restart keeps the damaged ballista")
    harness.check(restored[0]["max_hp"] == kcs_balance.DEFENDER_ENGINES["ballista"]["hp"],
                  "the snapshot reports the provisional ballista hp")

    stand_beside(defender, cauldron[3])
    pot, pot_err = await place(defender, {
        "engine_type": "cauldron", "x": cauldron[0], "y": cauldron[1],
        "rotation": 180, "request_id": "cauldron-1",
    })
    harness.check(pot, f"defender places a cauldron ({pot_err})")
    pot_id = pot[0]["engine"]["engine_id"]
    before_pot = kcs_balance.DEFENDER_ENGINES["cauldron"]["hp"]
    attacker.ws.sent.clear()
    ram_shot = kcs_battle.fire(attacker, "ram")
    harness.check(ram_shot.get("ok"), f"the ram still fires ({ram_shot.get('error')})")
    after_pot = store.engine_combat_map(war.war_id).get(pot_id, (before_pot, 0))[0]
    harness.check(after_pot < before_pot, f"a ram shot splashes the cauldron ({after_pot})")
    attacker.hp = max(int(getattr(attacker, "hp", 0) or 0), 80)
    ram_before_dump = store.engine_combat_map(war.war_id)[ram_id][0]
    dump = kcs_battle.fire(defender, "cauldron")
    harness.check(dump.get("ok") and "cauldron" in dump.get("text", "").lower(),
                  f"the cauldron dumps ({dump.get('error')})")
    harness.check(store.engine_combat_map(war.war_id)[ram_id][0] < ram_before_dump,
                  "the dump damages the ram")

    defender.x, defender.y = 30, 30
    attacker.x = ballista[3][0][0]
    attacker.y = ballista[3][0][1]
    swing = kcs_battle.strike(attacker)
    harness.check(swing.get("ok") and swing.get("engine_id") == replaced[0]["engine"]["engine_id"],
                  f"an attacker strikes the ballista ({swing})")
    wrecked_hp = store.engine_combat_map(war.war_id)[replaced[0]["engine"]["engine_id"]][0]
    harness.check(wrecked_hp < hurt, "the strike reduces ballista hp")

    ladder = find_valid_on_side(bf, "ladder", "east", [], 270)
    harness.check(ladder is not None, "a ladder still has an east placement")
    ladder_ok, ladder_err = await place(attacker, {
        "engine_type": "ladder", "x": ladder[0], "y": ladder[1], "rotation": ladder[2],
        "request_id": "ladder-east",
    })
    harness.check(ladder_ok, f"attacker ladder still places ({ladder_err})")
    crossing = [tile for tile in harness.kcs_siege._crossing_tiles()
                if bf.plane.cell(tile[0], tile[1]) in ("#", "H", "G")]
    harness.check(crossing and harness.kcs_siege.walkable(attacker, crossing[0][0], crossing[0][1]),
                  "a live ladder still opens a curtain crossing")
    kcs_battle.pack(attacker, "ladder")
    harness.check(not harness.kcs_siege.walkable(attacker, crossing[0][0], crossing[0][1])
                  or (crossing[0][0], crossing[0][1]) not in harness.kcs_siege._crossing_tiles(),
                  "packing the ladder closes that crossing")

    await harness.server.handle_enter_dungeon(outsider, {"dungeon_id": "kings_castle_siege"})
    store.eliminate(war.war_id, outsider.player_id, "test")
    outsider.hp = outsider.max_hp()
    outsider.dungeon["mode"] = "combatant"
    stand_beside(outsider, ballista[3])
    elim_ok, elim_err = await place(outsider, {
        "engine_type": "ballista", "x": ballista[0] + 4, "y": ballista[1],
        "rotation": 180, "request_id": "elim",
    })
    harness.check(not elim_ok, f"an eliminated defender cannot build ({elim_err})")
    elim_fire = kcs_battle.fire(outsider, "ballista")
    harness.check(elim_fire.get("ok") is False, "an eliminated defender cannot fire")

    harness.check(attacker.coins == 70 and defender.coins == 40 and outsider.coins == 15,
                  "equipment does not spend or take gold")
    harness.check(store.result(war.war_id) is None, "using equipment does not decide the war")
    harness.check(store.sovereignty()["rev"] == sov_rev, "equipment does not move sovereignty")

    defender.hp = 0
    down = kcs_battle.fire(defender, "cauldron")
    harness.check(down.get("ok") is False, "a downed defender cannot dump the cauldron")
    defender.hp = defender.max_hp()
    defender.dungeon["mode"] = "spectator"
    watching = kcs_battle.fire(defender, "cauldron")
    harness.check(watching.get("ok") is False and "spectator" in watching.get("error", "").lower(),
                  "a spectator cannot operate equipment")
    defender.dungeon["mode"] = "combatant"

    forged = await place(defender, {
        "engine_type": "cauldron", "x": cauldron[0], "y": cauldron[1], "rotation": 180,
        "request_id": "forged", "hp": 1, "owner": attacker.player_id,
    })
    harness.check(not forged[0], "a forged hp or owner is refused")

    realm = harness.player()
    realm.x, realm.y = 9, 28
    await harness.server.handle_enter_dungeon(realm, {"dungeon_id": "castle_realm"})
    harness.check(realm.dungeon and realm.dungeon.get("id") == "castle_realm",
                  "Castle Realm still opens")
    harness.flag(False)
    sealed = kcs_battle.fire(defender, "ballista")
    harness.check(sealed.get("ok") is False, "flag off again: the ballista is silent")
    harness.check(os.path.basename(path) != "world.db", "the siege file is not world.db")
    after = (
        os.path.getsize(live_world) if os.path.exists(live_world) else None,
        os.path.getmtime(live_world) if os.path.exists(live_world) else None,
        os.path.getsize(live_kcs) if os.path.exists(live_kcs) else None,
        os.path.getmtime(live_kcs) if os.path.exists(live_kcs) else None,
    )
    harness.check(before == after, "preexisting live database files were not opened or replaced")
    print(f"kcs defender tests ok ({harness.CHECKS} checks)")


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
