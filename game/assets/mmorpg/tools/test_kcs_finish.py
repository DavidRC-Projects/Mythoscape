"""Camera quarter, ladder crossing, pack, spectate, and the throne destination.

Temporary databases only. Does not open a live world.db.
"""
from __future__ import annotations

import ast
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(ROOT, "client"))
os.environ["KCS_COOLDOWN_SCALE"] = "0"

import test_kcs_integration as harness  # noqa: E402
import kcs_battle  # noqa: E402
import kcs_siege  # noqa: E402
import kcs_client  # noqa: E402
import throne  # noqa: E402
import castle_owners  # noqa: E402

PARITY = os.path.join(ROOT, "server", "kcs_parity")
sys.path.insert(0, PARITY)
from kings_castle_siege_map.angled_proj import pick_tile, project  # noqa: E402
from kings_castle_siege_map.layout import build_battlefield  # noqa: E402
from kings_castle_siege_map.placement import validate_placement  # noqa: E402


def check(ok, msg):
    harness.check(ok, msg)


def no_crown(path):
    tree = ast.parse(open(path, encoding="utf-8").read())
    called = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Attribute):
            called.add(node.attr)
    check("_crown" not in called, os.path.basename(path) + " does not call throne._crown")


def camera():
    origin, screen, scale = (20.0, 20.0), (220.0, 180.0), 28.0
    kcs_client.apply_view_quarter(0)
    sx0, sy0, _z = project(30.5, 40.5, 0, origin, scale, screen)
    kcs_client.apply_view_quarter(1)
    sx1, sy1, _z = project(30.5, 40.5, 0, origin, scale, screen)
    check((round(sx0), round(sy0)) != (round(sx1), round(sy1)), "a view quarter moves the same tile on screen")
    picked = pick_tile(sx1, sy1, origin, scale, screen)
    check(picked == (30, 40), f"the click maps back to that tile ({picked})")
    kcs_client.apply_view_quarter(0)
    again = pick_tile(*project(30.5, 40.5, 0, origin, scale, screen)[:2], origin, scale, screen)
    check(again == (30, 40), "quarter 0 is the original projection again")


def ladder_spot(bf, cells):
    ww, wn, we, ws = bf.wall_box
    for y in range(ws + 1, min(bf.plane.height - 2, ws + 8)):
        for x in range(ww, we):
            res = validate_placement(bf, "ladder", x, y, 0, [])
            if res.ok:
                return res
    return None


async def main():
    live_world = os.path.join(ROOT, "server", "world.db")
    live_kcs = os.path.join(ROOT, "server", "kcs_siege.db")
    before = tuple(
        (os.path.getsize(p), os.path.getmtime(p)) if os.path.exists(p) else None
        for p in (live_world, live_kcs)
    )
    server_dir = os.path.join(ROOT, "server")
    no_crown(os.path.join(server_dir, "kcs_throne_dest.py"))
    no_crown(os.path.join(server_dir, "kcs_battle.py"))
    camera()

    harness.flag(False)
    harness.feature_flags.USE_KINGS_CASTLE_SOVEREIGNTY = False
    check(kcs_battle.project() == "flag_off", "the throne projector stays off with the siege")

    harness.flag(True)
    harness.use_store()
    conn = harness.W.db.conn
    throne.ensure_schema(conn)
    castle_owners.ensure_schema(conn)
    cols = {row[1] for row in conn.execute("PRAGMA table_info(players)").fetchall()}
    if "noble_rank" not in cols:
        conn.execute("ALTER TABLE players ADD COLUMN noble_rank INTEGER DEFAULT 0")
    if "royal_title" not in cols:
        conn.execute("ALTER TABLE players ADD COLUMN royal_title TEXT NULL")
    conn.commit()

    bf = build_battlefield()
    spot = ladder_spot(bf, None)
    check(spot is not None, "a ladder has a south-wall placement")
    store, war = harness.open_war()
    attacker = harness.player()
    other = harness.player()
    stranger = harness.player()
    attacker.coins = 80
    other.coins = 40
    conn.execute("UPDATE players SET coins=80, noble_rank=2 WHERE id=?", (attacker.player_id,))
    conn.execute("UPDATE players SET coins=40, noble_rank=4, royal_title=NULL WHERE id=?", (other.player_id,))
    conn.execute(
        "INSERT INTO castle_ownership(castle_id, owner_account_id, owner_display_name, purchased_at, "
        "last_tax_paid_at, tax_weeks_owed) VALUES ('eastkeep', ?, 'Other Lord', 1, 1, 0)",
        (other.player_id,))
    conn.commit()
    harness.enlist(store, war, attacker, "attack")
    harness.enlist(store, war, other, "attack")
    kcs_battle.begin(attacker)
    await harness.server.handle_enter_dungeon(attacker, {"dungeon_id": "kings_castle_siege"})
    xs = [t[0] for t in spot.tiles]
    ys = [t[1] for t in spot.tiles]
    placed = harness.kcs_siege.propose_placement(attacker, {
        "engine_type": "ladder", "x": min(xs), "y": min(ys), "rotation": 0, "request_id": "lad-cross",
    })
    check(placed.get("ok"), f"ladder places ({placed.get('error')})")
    wall = None
    for tile in kcs_siege._crossing_tiles():
        if tile in set(map(tuple, spot.tiles)):
            continue
        if not kcs_siege.siege_map().walkable(kcs_siege.PLANE_BATTLEFIELD, tile[0], tile[1], {}):
            wall = tile
            break
    check(wall is not None, "the ladder reaches a tile the curtain still blocks")
    check(kcs_siege.walkable(attacker, wall[0], wall[1]), "that tile can be walked while the ladder stands")
    packed = kcs_battle.pack(attacker, "ladder")
    check(packed.get("ok"), f"the owner can pack the ladder ({packed.get('error')})")
    check(not any(e.engine_type == "ladder" for e in store.engines(war.war_id)), "the packed ladder leaves the field")
    check(not kcs_siege.walkable(attacker, wall[0], wall[1]), "packing the ladder closes the crossing")

    await harness.server.handle_enter_dungeon(stranger, {"dungeon_id": "kings_castle_siege", "watch": True})
    check(not kcs_siege.on_map(stranger), "someone who never enlisted cannot watch")
    await harness.server.handle_enter_dungeon(other, {"dungeon_id": "kings_castle_siege", "watch": True})
    check((other.dungeon or {}).get("mode") == "spectator", "a roster member can watch instead of fighting")

    # Throne destination. A fresh war so the spectator war can stay unresolved.
    harness.use_store()
    store, war = harness.open_war()
    claimant = harness.player()
    bystander = harness.player()
    claimant.coins = 100
    conn.execute("UPDATE players SET coins=100, noble_rank=1 WHERE id=?", (claimant.player_id,))
    conn.execute("UPDATE players SET coins=55, noble_rank=3 WHERE id=?", (bystander.player_id,))
    conn.execute(
        "INSERT OR REPLACE INTO castle_ownership(castle_id, owner_account_id, owner_display_name, purchased_at, "
        "last_tax_paid_at, tax_weeks_owed) VALUES ('eastkeep', ?, 'Other Lord', 1, 1, 0)",
        (bystander.player_id,))
    conn.commit()
    harness.enlist(store, war, claimant, "attack")
    kcs_battle.begin(claimant)
    await harness.server.handle_enter_dungeon(claimant, {"dungeon_id": "kings_castle_siege"})
    store.write_repair(war.war_id, "keep_doors", 0, "destroyed")
    keep = kcs_siege.siege_map().plane(kcs_siege.PLANE_BATTLEFIELD).opening_rects["keep_doors"]
    await harness.server._kcs_change_plane(claimant, kcs_siege.PLANE_THRONE)
    dais = kcs_siege.siege_map().plane(kcs_siege.PLANE_THRONE).spawn["dais"]
    claimant.x, claimant.y = int(dais[0]), int(dais[1])
    harness.feature_flags.USE_KINGS_CASTLE_SOVEREIGNTY = True
    won = kcs_battle.claim(claimant)
    check(won.get("finished") and won.get("winner") == "attack", "the claim finishes for the attackers")
    st = throne.state(conn)
    check(st["monarch_kind"] == "player" and int(st["monarch_player_id"]) == claimant.player_id
          and st["path"] == "siege", "the game throne names the claimant")
    owned = castle_owners.owners(conn)
    check(owned["king"]["owner_id"] == claimant.player_id, "King's Castle ownership names the claimant")
    check(owned["eastkeep"]["owner_id"] == bystander.player_id, "another castle keeps its owner")
    lines = " ".join(throne.summary_lines(conn))
    check(str(claimant.player_id) in lines or "player" in lines.lower() or lines, "the throne summary can be read")
    coins = conn.execute("SELECT coins, noble_rank FROM players WHERE id=?", (bystander.player_id,)).fetchone()
    check(int(coins[0]) == 55 and int(coins[1]) == 3, "the result does not take gold or noble rank")
    claimant_coins = conn.execute("SELECT coins FROM players WHERE id=?", (claimant.player_id,)).fetchone()[0]
    check(int(claimant_coins) == 100, "the claimant's gold is unchanged")
    again = kcs_battle.project(store, war.war_id)
    check(again == "already_applied", "a restart does not apply a second result")
    check(int(throne.state(conn)["monarch_player_id"]) == claimant.player_id, "the retry leaves the same monarch")
    check(len(conn.execute("SELECT id FROM throne").fetchall()) == 1, "there is still one throne row")

    import kcs_throne_dest
    before_throne = throne.state(conn)
    try:
        kcs_throne_dest.deliver(conn, {
            "rev": 99, "war_id": 99, "winner_side": "attack", "monarch_player_id": 999999,
        })
        raised = False
    except kcs_throne_dest.DestinationError:
        raised = True
    check(raised, "a result for a missing character is refused")
    check(throne.state(conn) == before_throne, "the refused result does not leave a partial crown")

    harness.feature_flags.USE_KINGS_CASTLE_SOVEREIGNTY = False
    after = tuple(
        (os.path.getsize(p), os.path.getmtime(p)) if os.path.exists(p) else None
        for p in (live_world, live_kcs)
    )
    check(before == after, "preexisting live database files were not opened or replaced")
    print(f"kcs finish tests ok ({harness.CHECKS} checks)")


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
