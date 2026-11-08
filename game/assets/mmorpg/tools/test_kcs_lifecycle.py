"""Siege lifecycle: victories, grace, restart, and a sandbox-only next registration.

Temporary databases only. Does not open a live world.db.
"""
from __future__ import annotations

import asyncio
import os
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
os.environ["KCS_COOLDOWN_SCALE"] = "0"
os.environ["KCS_WAR_SECONDS"] = "1200"
os.environ.pop("KCS_SANDBOX_PREP", None)

import test_kcs_integration as harness  # noqa: E402
import kcs_battle  # noqa: E402
import kcs_siege  # noqa: E402
import throne  # noqa: E402
import castle_owners  # noqa: E402
from kcs_server.store import InvalidTransition  # noqa: E402


def check(ok, msg):
    harness.check(ok, msg)


def messages(session, kind):
    return [row for row in session.ws.sent if row.get("type") == kind]


async def deploy(session):
    await harness.server.handle_enter_dungeon(session, {"dungeon_id": "kings_castle_siege"})


async def main():
    live_world = os.path.join(ROOT, "server", "world.db")
    live_kcs = os.path.join(ROOT, "server", "kcs_siege.db")
    before = (
        os.path.getsize(live_world) if os.path.exists(live_world) else None,
        os.path.getmtime(live_world) if os.path.exists(live_world) else None,
        os.path.getsize(live_kcs) if os.path.exists(live_kcs) else None,
        os.path.getmtime(live_kcs) if os.path.exists(live_kcs) else None,
    )
    harness.flag(False)
    check(kcs_battle.resolution_if_due() is None, "flag off: no victory is decided")
    check(kcs_battle.prepare_next([{"player_id": 1, "side": "attack"}]).get("ok") is False,
          "flag off: sandbox preparation does nothing")

    harness.flag(True)
    harness.feature_flags.USE_KINGS_CASTLE_SOVEREIGNTY = True
    path, _journal = harness.use_store()
    conn = harness.W.db.conn
    throne.ensure_schema(conn)
    castle_owners.ensure_schema(conn)
    cols = {row[1] for row in conn.execute("PRAGMA table_info(players)").fetchall()}
    if "noble_rank" not in cols:
        conn.execute("ALTER TABLE players ADD COLUMN noble_rank INTEGER DEFAULT 0")
    if "royal_title" not in cols:
        conn.execute("ALTER TABLE players ADD COLUMN royal_title TEXT NULL")
    conn.commit()

    store, war = harness.open_war()
    attacker = harness.player()
    absent = harness.player()
    defender = harness.player()
    bystander = harness.player()
    for person, coins, rank in (
        (attacker, 80, 1), (absent, 70, 1), (defender, 60, 2), (bystander, 55, 4),
    ):
        person.coins = coins
        conn.execute(
            "UPDATE players SET coins=?, noble_rank=?, royal_title=NULL WHERE id=?",
            (coins, rank, person.player_id))
    conn.execute(
        "INSERT INTO castle_ownership(castle_id, owner_account_id, owner_display_name, purchased_at, "
        "last_tax_paid_at, tax_weeks_owed) VALUES ('eastkeep', ?, 'Other Lord', 1, 1, 0)",
        (bystander.player_id,))
    conn.commit()
    accounts = conn.execute("SELECT COUNT(*) FROM players").fetchone()[0]
    harness.enlist(store, war, attacker, "attack")
    harness.enlist(store, war, absent, "attack")
    harness.enlist(store, war, defender, "defend")
    started = kcs_battle.begin(attacker)
    check(started.get("status") == "active", "the battle status is active")
    check(started.get("phase") == "Battle", "the panel names the battle")
    check(started.get("attack_enlisted") == 2 and started.get("defend_enlisted") == 1,
          "the panel counts both sides")
    check(started.get("attack_absent") == 2, "nobody has deployed yet")
    check(isinstance(started.get("remaining"), int) and started["remaining"] > 0,
          "the panel has time remaining")
    check("not an elimination" in (started.get("grace_rule") or ""),
          "the panel explains the deploy grace")
    check(any(row.get("id") == "main_gate" and row.get("state") == "intact"
              for row in started.get("objectives") or []),
          "the panel lists the main gate")
    check(started.get("sandbox") is False, "the sandbox control is off unless that switch is on")

    await deploy(attacker)
    await deploy(defender)
    store.write_repair(war.war_id, "main_gate", 40, "damaged")
    ends = store.get_clock(war.war_id)
    began = store.started_at(war.war_id)
    check(ends and began, "the battle stores a start and a deadline")
    panel = kcs_battle.public_status(attacker)
    check(panel.get("attack_deployed") == 1 and panel.get("attack_absent") == 1,
          "one attacker is on the field and one has not deployed")
    check(panel.get("your_side") == "attack", "the panel knows the attacker's side")

    kcs_siege.simulate_restart()
    store = kcs_siege.store()
    check(store.war(war.war_id).status == "active", "restart keeps the battle active")
    check(store.get_clock(war.war_id) == ends and store.started_at(war.war_id) == began,
          "restart keeps the clock")
    check(store.opening_hps(war.war_id).get("main_gate") == 40, "restart keeps the damaged gate")
    check(store.roster_status(war.war_id, absent.player_id).eliminated is False,
          "restart does not eliminate the absent attacker")
    resumed = harness.resume_of(attacker)
    attacker.dungeon = None
    await harness.server._resume_kcs(attacker, resumed)
    check(kcs_siege.on_map(attacker), "a deployed attacker reconnects into the battle")
    check(any(row.get("type") == "KCS_SNAPSHOT" for row in attacker.ws.sent),
          "reconnect sends the siege snapshot")

    await harness.server.handle_enter_dungeon(absent, {"dungeon_id": "kings_castle_siege", "watch": True})
    check((absent.dungeon or {}).get("mode") == "spectator", "an enlisted attacker can watch without deploying")
    watch = harness.resume_of(absent)
    absent.dungeon = None
    await harness.server._resume_kcs(absent, watch)
    check((absent.dungeon or {}).get("mode") == "spectator", "a spectator reconnects as a spectator")
    check(store.roster_status(war.war_id, absent.player_id).deployed is False,
          "watching does not count as deploying")

    check(kcs_battle.resolution_if_due() is None, "a living deployed attacker keeps the battle going")
    store.eliminate(war.war_id, attacker.player_id, "test")
    check(kcs_battle.resolution_if_due() is None,
          "during the grace, an attacker who never deployed still holds the field")
    check(store.roster_status(war.war_id, absent.player_id).eliminated is False,
          "the grace does not mark that attacker eliminated")
    store.set_clock(war.war_id, ends, time.time() - 120)
    os.environ["KCS_SANDBOX_PREP"] = "1"
    refused = kcs_battle.prepare_next([
        {"player_id": attacker.player_id, "side": "attack"},
        {"player_id": defender.player_id, "side": "defend"},
    ])
    check(refused.get("ok") is False and "not reset" in (refused.get("error") or ""),
          "sandbox preparation refuses an active battle")
    check(store.war(war.war_id).status == "active", "the active battle is still the same war")
    os.environ.pop("KCS_SANDBOX_PREP", None)

    done = kcs_battle.resolution_if_due()
    check(done and done.get("finished") and done.get("winner") == "defend"
          and done.get("reason") == "attackers_eliminated",
          "after the grace, defenders win because no deployed attacker remains")
    check(store.roster_status(war.war_id, absent.player_id).eliminated is False,
          "the attacker who never deployed is still not eliminated")
    check(store.roster_status(war.war_id, attacker.player_id).eliminated is True,
          "the attacker who fell stays eliminated")
    again = kcs_battle.resolution_if_due()
    check(again is None, "the finished battle is not decided a second time")
    replay = kcs_battle._finish(store, war.war_id, "attack", attacker.player_id, "claim")
    check(replay.get("finished") is False and replay.get("duplicate") is True,
          "a second result is refused")
    check(store.result(war.war_id)["winner_side"] == "defend", "the defender victory stays the result")

    kcs_siege.simulate_restart()
    store = kcs_siege.store()
    check(store.war(war.war_id).status == "resolved" and store.open_war() is None,
          "restart keeps the battle finished and closed")
    check(store.result(war.war_id)["winner_side"] == "defend", "restart keeps the result")
    check(store.opening_hps(war.war_id).get("main_gate") == 40, "restart keeps the gate after victory")
    try:
        store.set_war_status(war.war_id, "active")
        reopened = True
    except InvalidTransition:
        reopened = False
    check(not reopened, "a finished war cannot be reopened")
    await harness.server._finish_kcs_victory(done.get("text"))
    check(not kcs_siege.on_map(attacker) and not kcs_siege.on_map(defender),
          "victory returns the fighters to the overworld")
    check(any(row.get("type") == "KCS_RESULT" for row in defender.ws.sent),
          "the result is sent to the client")
    blocked = kcs_battle.fire(attacker, "ram")
    check(blocked.get("ok") is False, "combat stops after the result")
    attacker.dungeon = None
    await harness.server._resume_kcs(attacker, resumed)
    check(not kcs_siege.on_map(attacker), "reconnect after victory does not re-enter the battle")
    check(any(row.get("type") == "KCS_STATUS" for row in attacker.ws.sent),
          "reconnect after victory still receives the result panel")

    # Defender timeout on the next war. The previous result stays stored.
    timeout_war = store.create_war("lifecycle-timeout")
    store.enlist(timeout_war.war_id, attacker.player_id, "attack")
    store.enlist(timeout_war.war_id, defender.player_id, "defend")
    check(kcs_battle.begin(defender).get("status") == "active", "a new war can be registered after the last one")
    store.set_clock(timeout_war.war_id, time.time() - 5)
    timed = kcs_battle.resolution_if_due()
    check(timed and timed.get("finished") and timed.get("reason") == "timeout"
          and timed.get("winner") == "defend",
          "a clock that has run out is a defender victory")
    check(kcs_battle.resolution_if_due() is None, "the timeout is not applied twice")
    check(throne.state(conn)["monarch_kind"] != "player", "a defence does not crown an attacker")
    check(store.result(war.war_id)["winner_side"] == "defend", "the earlier result is still there")

    # Attacker capture. One destination transaction, then a retry changes nothing.
    claim_war = store.create_war("lifecycle-claim")
    store.enlist(claim_war.war_id, attacker.player_id, "attack")
    store.enlist(claim_war.war_id, defender.player_id, "defend")
    check(kcs_battle.begin(attacker).get("status") == "active", "the claim war begins")
    os.environ["KCS_SANDBOX_PREP"] = "1"
    refused = kcs_battle.prepare_next([{"player_id": attacker.player_id, "side": "attack"}])
    check(refused.get("ok") is False, "preparation does not reset the claim war")
    os.environ.pop("KCS_SANDBOX_PREP", None)
    await deploy(attacker)
    store.write_repair(claim_war.war_id, "keep_doors", 0, "destroyed")
    await harness.server._kcs_change_plane(attacker, kcs_siege.PLANE_THRONE)
    dais = kcs_siege.siege_map().plane(kcs_siege.PLANE_THRONE).spawn["dais"]
    attacker.x, attacker.y = int(dais[0]), int(dais[1])
    attacker.ws.sent.clear()
    won = await harness.server.handle_kcs_claim(attacker, {})
    del won
    check(not kcs_siege.on_map(attacker), "the claimant is returned to the overworld")
    check(any(row.get("type") == "KCS_RESULT" and "throne" in (row.get("text") or "").lower()
              for row in attacker.ws.sent),
          "the client is shown the attacker victory")
    st = throne.state(conn)
    check(st["monarch_kind"] == "player" and int(st["monarch_player_id"]) == attacker.player_id
          and st["path"] == "siege", "the existing throne names the claimant")
    owned = castle_owners.owners(conn)
    check(owned["king"]["owner_id"] == attacker.player_id, "King's Castle uses the existing ownership row")
    check(owned["eastkeep"]["owner_id"] == bystander.player_id, "another castle is untouched")
    panel = kcs_battle.public_status(attacker)
    check(panel.get("status") == "resolved" and (panel.get("result") or {}).get("reason") == "claim",
          "the panel shows the finished claim")
    check(attacker.char_name in (panel.get("ownership") or {}).get("castle_line", ""),
          "the panel shows the King's Castle owner")
    check((panel.get("ownership") or {}).get("royal_title") in ("King", "Queen"),
          "the panel shows the crown the game already stores")
    check(getattr(attacker, "royal_title", None) in ("King", "Queen"),
          "the online character receives the royal title")
    coins = conn.execute(
        "SELECT coins, noble_rank FROM players WHERE id=?", (bystander.player_id,)).fetchone()
    check(int(coins[0]) == 55 and int(coins[1]) == 4, "gold and noble rank are unchanged")
    attacker_coins = conn.execute(
        "SELECT coins FROM players WHERE id=?", (attacker.player_id,)).fetchone()[0]
    check(int(attacker_coins) == 80, "the claimant's gold is unchanged")
    rev = store.sovereignty()["rev"]
    check(kcs_battle.project(store, claim_war.war_id) == "already_applied",
          "projecting the same result again is ignored")
    check(store.sovereignty()["rev"] == rev, "the retry does not mint another crown")
    check(int(throne.state(conn)["monarch_player_id"]) == attacker.player_id,
          "the retry leaves the same monarch")
    await harness.server.handle_kcs_claim(attacker, {})
    check(int(conn.execute("SELECT COUNT(*) FROM throne").fetchone()[0]) == 1,
          "there is still one throne row")

    os.environ["KCS_SANDBOX_PREP"] = "1"
    missing = kcs_battle.prepare_next([{"player_id": 999999, "side": "attack"}])
    check(missing.get("ok") is False and "account" in (missing.get("error") or "").lower(),
          "preparation does not create an account")
    nxt = kcs_battle.prepare_next([
        {"player_id": attacker.player_id, "side": "defend"},
        {"player_id": defender.player_id, "side": "attack"},
    ])
    check(nxt.get("ok") and nxt.get("status") == "registration",
          "sandbox preparation opens a fresh registration")
    check(nxt.get("sandbox") is True, "the panel labels the sandbox control")
    check(conn.execute("SELECT COUNT(*) FROM players").fetchone()[0] == accounts,
          "preparation does not add or remove accounts")
    check(store.war(claim_war.war_id).status == "resolved", "the claimed war stays resolved")
    check(store.result(claim_war.war_id)["winner_side"] == "attack", "the claim result is kept")
    check(store.roster_status(war.war_id, attacker.player_id).eliminated is True,
          "an older elimination is not erased")
    fresh_id = nxt["war_id"]
    check(store.roster_status(fresh_id, attacker.player_id).side == "defend",
          "the new registration uses the chosen side")
    check(store.war(fresh_id).status == "registration", "preparation does not start the battle")
    store.eliminate(fresh_id, attacker.player_id, "keep")
    kept = kcs_battle.prepare_next([
        {"player_id": defender.player_id, "side": "defend"},
    ])
    check(kept.get("ok") is False and "eliminations" in (kept.get("error") or ""),
          "preparation will not discard a registration that has an elimination")
    check(store.roster_status(fresh_id, attacker.player_id).eliminated is True,
          "that elimination is still recorded")
    check(store.war(fresh_id).status == "registration", "the registration was not voided")
    os.environ.pop("KCS_SANDBOX_PREP", None)
    hidden = kcs_battle.prepare_next([
        {"player_id": defender.player_id, "side": "defend"},
    ])
    check(hidden.get("ok") is False, "without the sandbox switch, preparation is refused")

    harness.flag(False)
    check(kcs_battle.public_status().get("ok") is False, "flag off: the panel stays closed")
    check(kcs_battle.prepare_next([{"player_id": attacker.player_id, "side": "attack"}]).get("ok") is False,
          "flag off: preparation stays refused")
    realm = harness.player()
    realm.x, realm.y = 9, 28
    await harness.server.handle_enter_dungeon(realm, {"dungeon_id": "castle_realm"})
    check(realm.dungeon and realm.dungeon.get("id") == "castle_realm",
          "Castle Realm still opens when the siege flag is off")
    check(castle_owners.owners(conn)["eastkeep"]["owner_id"] == bystander.player_id,
          "the unrelated castle is still the same owner")
    check(int(throne.state(conn)["monarch_player_id"]) == attacker.player_id,
          "turning the flag off does not take the crown back")
    after = (
        os.path.getsize(live_world) if os.path.exists(live_world) else None,
        os.path.getmtime(live_world) if os.path.exists(live_world) else None,
        os.path.getsize(live_kcs) if os.path.exists(live_kcs) else None,
        os.path.getmtime(live_kcs) if os.path.exists(live_kcs) else None,
    )
    check(before == after, "preexisting live database files were not opened or replaced")
    check(os.path.basename(path) != "world.db", "the siege file is not world.db")
    print(f"kcs lifecycle tests ok ({harness.CHECKS} checks)")


if __name__ == "__main__":
    asyncio.run(main())
