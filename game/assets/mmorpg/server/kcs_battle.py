"""Playable King's Castle siege loop. Provisional numbers live in kcs_balance.

The client cannot declare damage, a winner, or a crown. Gold is not spent
and is not taken when the castle falls. Sovereignty projection, when its own
flag is on, writes only the siege database. It does not call throne._crown.
"""
from __future__ import annotations

import logging
import time

import feature_flags
import kcs_balance
import kcs_siege

log = logging.getLogger("crownfall.kcs_battle")


def sovereignty_enabled() -> bool:
    return bool(getattr(feature_flags, "USE_KINGS_CASTLE_SOVEREIGNTY", False))


def _fail(text: str) -> dict:
    return {"ok": False, "error": text}


def _store():
    return kcs_siege.store()


def _side(session):
    try:
        war = _store().open_war()
        if war is None:
            return None
        row = _store().roster_status(war.war_id, int(session.player_id))
        return row.side if row.on_roster else None
    except Exception:
        log.exception("kcs side read failed")
        return None


def lobby(session) -> dict:
    if not kcs_siege.enabled():
        return _fail("The siege is closed.")
    try:
        war = _store().open_war()
    except Exception:
        log.exception("kcs lobby failed")
        return _fail("The siege can't be reached right now.")
    if war is None:
        return {"ok": True, "status": "none", "text": "No siege is open. Enlist to start one.",
                "your_side": None, "attack": 0, "defend": 0}
    rows = _store().roster_rows(war.war_id)
    you = None
    for pid, side, _dep, _elim in rows:
        if int(pid) == int(session.player_id):
            you = side
    return {
        "ok": True,
        "war_id": war.war_id,
        "status": war.status,
        "your_side": you,
        "attack": sum(1 for _p, side, _d, elim in rows if side == "attack" and not elim),
        "defend": sum(1 for _p, side, _d, elim in rows if side == "defend" and not elim),
        "ends_at": _store().get_clock(war.war_id),
        "text": f"Siege is {war.status}. You are {you or 'not enlisted'}.",
    }


def enlist(session, side: str) -> dict:
    if not kcs_siege.enabled():
        return _fail("The siege is closed.")
    if side not in ("attack", "defend"):
        return _fail("Choose attackers or defenders.")
    try:
        store = _store()
        war = store.open_war()
        if war is None:
            war = store.create_war(f"kcs-{int(time.time())}-{int(session.player_id)}")
        if war.status not in ("registration", "locking"):
            return _fail("The siege has already started. Wait for the next one.")
        store.enlist(war.war_id, int(session.player_id), side)
    except Exception as exc:
        log.exception("kcs enlist failed")
        return _fail(str(exc) or "Could not enlist.")
    body = lobby(session)
    body["text"] = f"Enlisted as {side}. Press Begin, then Deploy."
    return body


def begin(session) -> dict:
    if not kcs_siege.enabled():
        return _fail("The siege is closed.")
    try:
        store = _store()
        war = store.open_war()
        if war is None:
            return _fail("Enlist before beginning the siege.")
        row = store.roster_status(war.war_id, int(session.player_id))
        if not row.on_roster or row.eliminated:
            return _fail("Enlist before beginning the siege.")
        if war.status == "registration":
            store.set_war_status(war.war_id, "locking")
            war = store.war(war.war_id)
        if war.status == "locking":
            store.set_war_status(war.war_id, "active")
            war = store.war(war.war_id)
        if war.status != "active":
            return _fail(f"The siege is {war.status}.")
        if store.get_clock(war.war_id) is None:
            store.set_clock(war.war_id, time.time() + kcs_balance.war_seconds())
            _seed_openings(store, war.war_id)
    except Exception:
        log.exception("kcs begin failed")
        return _fail("The siege can't be started right now.")
    body = lobby(session)
    body["text"] = "The siege is live. Deploy to enter."
    return body


def _seed_openings(store, war_id: int) -> None:
    smap = kcs_siege.siege_map()
    for plane_id in (kcs_siege.PLANE_BATTLEFIELD, kcs_siege.PLANE_THRONE):
        pdata = smap.plane(plane_id)
        for oid in pdata.opening_ids:
            state = pdata.defaults.get(oid, "intact")
            hp = 0 if state == "destroyed" else kcs_balance.opening_max_hp(oid)
            store.seed_opening(war_id, oid, hp, state)


def enrich_snapshot(body: dict, war_id: int) -> dict:
    try:
        store = _store()
        hps = store.opening_hps(war_id)
        for opening in body.get("openings") or []:
            oid = opening.get("id")
            opening["max_hp"] = kcs_balance.opening_max_hp(oid)
            if oid in hps:
                opening["hp"] = hps[oid]
        combat = store.engine_combat_map(war_id)
        for engine in body.get("engines") or []:
            spec = kcs_balance.ENGINES.get(engine.get("engine_type") or "", {})
            rec = combat.get(int(engine.get("engine_id")))
            engine["max_hp"] = int(spec.get("hp") or 1)
            engine["hp"] = rec[0] if rec else engine["max_hp"]
            engine["cooldown_until"] = rec[1] if rec else 0
            engine["facing"] = kcs_balance.FACE_NAME.get(int(engine.get("rotation") or 0), "north")
        body["ends_at"] = store.get_clock(war_id)
    except Exception:
        log.exception("kcs snapshot enrich failed")
    return body


def _opening_cells():
    smap = kcs_siege.siege_map()
    found = {}
    for plane_id in (kcs_siege.PLANE_BATTLEFIELD, kcs_siege.PLANE_THRONE):
        pdata = smap.plane(plane_id)
        for oid in pdata.opening_ids:
            cells = [tuple(t) for t, owner in pdata.opening_at.items() if owner == oid]
            if cells:
                found[oid] = cells
    return found


def _live(session):
    if not kcs_siege.enabled():
        return None, _fail("The siege is closed.")
    if not kcs_siege.on_map(session):
        return None, _fail("You are not deployed in the siege.")
    if int(getattr(session, "hp", 0) or 0) <= 0:
        return None, _fail("You cannot do that while you are down.")
    data = session.dungeon or {}
    if data.get("mode") != "combatant":
        return None, _fail("Spectators cannot do that.")
    try:
        store = _store()
        war = store.open_war()
    except Exception:
        log.exception("kcs action failed")
        return None, _fail("The siege can't be reached right now.")
    if war is None or war.status != "active":
        return None, _fail("The siege is not being fought right now.")
    return (store, war), None


def timeout_if_due():
    """If the clock has run out, defenders win. None when the war continues."""
    if not kcs_siege.enabled():
        return None
    try:
        store = _store()
        war = store.open_war()
        if war is None or war.status != "active":
            return None
        ends = store.get_clock(war.war_id)
        if ends is None or time.time() < ends:
            return None
        return _finish(store, war.war_id, "defend", None, "timeout")
    except Exception:
        log.exception("kcs timeout check failed")
        return None


def defenders_if_attackers_gone():
    if not kcs_siege.enabled():
        return None
    try:
        store = _store()
        war = store.open_war()
        if war is None or war.status != "active":
            return None
        rows = store.roster_rows(war.war_id)
        attackers = [row for row in rows if row[1] == "attack"]
        if not attackers or any(not row[3] for row in attackers):
            return None
        return _finish(store, war.war_id, "defend", None, "attackers_eliminated")
    except Exception:
        log.exception("kcs elimination victory check failed")
        return None


def fire(session, engine_type: str) -> dict:
    due = timeout_if_due()
    if due:
        return due
    ctx, err = _live(session)
    if err:
        return err
    store, war = ctx
    if _side(session) != "attack":
        return _fail("Only attackers fire siege engines.")
    if engine_type not in kcs_balance.ENGINES:
        return _fail("Choose a ram, trebuchet, siege tower, or ladder.")
    engines = [e for e in store.engines(war.war_id)
               if e.player_id == int(session.player_id) and e.engine_type == engine_type]
    if not engines:
        return _fail(f"You have no {engine_type.replace('_', ' ')} on the field.")
    combat = store.engine_combat_map(war.war_id)
    now = time.time()
    cells = _opening_cells()
    states = store.openings(war.war_id)
    hps = store.opening_hps(war.war_id)
    refusal = "Nothing is in front of that engine."
    for engine in engines:
        hp, ready = combat.get(engine.engine_id, (kcs_balance.ENGINES[engine_type]["hp"], 0.0))
        if hp <= 0:
            refusal = "That engine is wrecked."
            continue
        if ready > now:
            refusal = "That engine is still reloading."
            continue
        hit = kcs_balance.shot_target(engine.tiles, engine.rotation, engine_type, cells)
        if hit is None:
            facing = kcs_balance.FACE_NAME.get(int(engine.rotation), "north")
            refusal = f"No gate or breach is {facing} of that {engine_type.replace('_', ' ')}. Rotate it toward the wall."
            continue
        oid, damage = hit
        if states.get(oid, "intact") == "destroyed" or hps.get(oid, 1) <= 0:
            refusal = "That opening is already breached."
            continue
        max_hp = kcs_balance.opening_max_hp(oid)
        current = hps.get(oid, max_hp if states.get(oid, "intact") != "destroyed" else 0)
        new_hp = max(0, int(current) - int(damage))
        state = kcs_balance.state_for_hp(new_hp, max_hp)
        cd = now + kcs_balance.ENGINES[engine_type]["cooldown"] * kcs_balance.cooldown_scale()
        rev = store.write_shot(war.war_id, engine.engine_id, hp, cd, oid, new_hp, state)
        _grant(session.player_id, kcs_balance.xp_shot())
        return {
            "ok": True,
            "text": f"{engine_type.replace('_', ' ')} hit {oid.replace('_', ' ')} for {damage}. It is {state}.",
            "opening": {"opening_id": oid, "state": state, "rev": rev, "hp": new_hp,
                        "plane": kcs_siege.PLANE_BATTLEFIELD},
            "engine_id": engine.engine_id,
        }
    return _fail(refusal)


def repair(session) -> dict:
    due = timeout_if_due()
    if due:
        return due
    ctx, err = _live(session)
    if err:
        return err
    store, war = ctx
    if _side(session) != "defend":
        return _fail("Only defenders repair the walls.")
    ready = float(getattr(session, "_kcs_repair_at", 0) or 0)
    if ready > time.time():
        return _fail("You are still catching your breath.")
    cells = _opening_cells()
    hps = store.opening_hps(war.war_id)
    states = store.openings(war.war_id)
    px, py = int(session.x), int(session.y)
    nearest = None
    for oid, tiles in cells.items():
        if oid == "throne_doors":
            continue
        if states.get(oid, "intact") == "intact" and hps.get(oid, 1) >= kcs_balance.opening_max_hp(oid):
            continue
        dist = min(max(abs(px - tx), abs(py - ty)) for tx, ty in tiles)
        if nearest is None or dist < nearest[0]:
            nearest = (dist, oid)
    if nearest is None:
        return _fail("Nothing nearby needs repair.")
    if nearest[0] > 8:
        return _fail("Move closer to the gate or breach to repair it.")
    oid = nearest[1]
    max_hp = kcs_balance.opening_max_hp(oid)
    current = hps.get(oid, 0 if states.get(oid) == "destroyed" else max_hp)
    new_hp = min(max_hp, int(current) + kcs_balance.repair_amount())
    state = kcs_balance.state_for_hp(new_hp, max_hp)
    rev = store.write_repair(war.war_id, oid, new_hp, state)
    session._kcs_repair_at = time.time() + 5.0 * kcs_balance.cooldown_scale()
    _grant(session.player_id, kcs_balance.xp_repair())
    return {
        "ok": True,
        "text": f"Repaired {oid.replace('_', ' ')}. It is {state}.",
        "opening": {"opening_id": oid, "state": state, "rev": rev, "hp": new_hp,
                    "plane": kcs_siege.PLANE_BATTLEFIELD},
    }


def strike(session) -> dict:
    """Siege-only blow. Does not enable overworld or global PvP."""
    due = timeout_if_due()
    if due:
        return due
    ctx, err = _live(session)
    if err:
        return err
    store, war = ctx
    ready = float(getattr(session, "_kcs_swing_at", 0) or 0)
    if ready > time.time():
        return _fail("You are still recovering your swing.")
    me = _side(session)
    if me not in ("attack", "defend"):
        return _fail("You are not fighting in this siege.")
    reach = kcs_balance.player_range()
    px, py = int(session.x), int(session.y)
    foe = None
    best = None
    try:
        import server
        sessions = list(server.WORLD.sessions.values())
    except Exception:
        sessions = []
    for other in sessions:
        if other is session or not kcs_siege.on_map(other):
            continue
        if (other.dungeon or {}).get("plane") != (session.dungeon or {}).get("plane"):
            continue
        if _side(other) == me or _side(other) not in ("attack", "defend"):
            continue
        if int(getattr(other, "hp", 0) or 0) <= 0:
            continue
        dist = max(abs(px - int(other.x)), abs(py - int(other.y)))
        if dist <= reach and (best is None or dist < best):
            best = dist
            foe = other
    session._kcs_swing_at = time.time() + 1.2 * kcs_balance.cooldown_scale()
    if foe is not None:
        dmg = kcs_balance.player_hit()
        foe.hp = max(0, int(foe.hp) - dmg)
        return {"ok": True, "text": f"You strike for {dmg}.", "target_id": foe.player_id,
                "target_hp": foe.hp, "killed": foe.hp <= 0}
    if me == "defend":
        wreck = _strike_engine(store, war.war_id, px, py)
        if wreck:
            return wreck
    return _fail("Nobody is in reach.")


def _strike_engine(store, war_id, px, py):
    combat = store.engine_combat_map(war_id)
    nearest = None
    for engine in store.engines(war_id):
        if engine.side != "attack":
            continue
        hp = combat.get(engine.engine_id, (kcs_balance.ENGINES[engine.engine_type]["hp"], 0))[0]
        if hp <= 0:
            continue
        dist = min(max(abs(px - tx), abs(py - ty)) for tx, ty in engine.tiles)
        if dist <= 1 and (nearest is None or dist < nearest[0]):
            nearest = (dist, engine, hp)
    if nearest is None:
        return None
    engine, hp = nearest[1], nearest[2]
    new_hp = max(0, hp - 12)
    store.damage_engine_hp(war_id, engine.engine_id, new_hp)
    word = "wrecked" if new_hp <= 0 else "damaged"
    return {"ok": True, "text": f"You {word} the {engine.engine_type.replace('_', ' ')} ({new_hp} hp).",
            "engine_id": engine.engine_id, "engine_hp": new_hp}


def claim(session) -> dict:
    due = timeout_if_due()
    if due:
        return due
    ctx, err = _live(session)
    if err:
        return err
    store, war = ctx
    if _side(session) != "attack":
        return _fail("Only an attacker can claim the throne.")
    if (session.dungeon or {}).get("plane") != kcs_siege.PLANE_THRONE:
        return _fail("Breach the keep doors and enter the throne room first.")
    states = store.openings(war.war_id)
    if states.get("keep_doors", "intact") != "destroyed":
        return _fail("The keep doors are still standing.")
    smap = kcs_siege.siege_map()
    dais = smap.plane(kcs_siege.PLANE_THRONE).spawn.get("dais", (36, 10))
    if max(abs(int(session.x) - int(dais[0])), abs(int(session.y) - int(dais[1]))) > 8:
        return _fail("Stand on the dais to claim the throne.")
    guild = getattr(session, "guild_id", None)
    try:
        guild = int(guild) if guild else None
    except (TypeError, ValueError):
        guild = None
    return _finish(store, war.war_id, "attack", int(session.player_id), "claim", guild)


def _finish(store, war_id: int, winner: str, monarch, reason: str, guild=None) -> dict:
    existing = store.result(war_id)
    if existing is not None:
        return {
            "ok": True,
            "duplicate": True,
            "finished": False,
            "winner": existing.get("winner_side"),
            "text": f"The siege is already decided for the {existing.get('winner_side')} side.",
        }
    proof = {"reason": reason, "war_id": int(war_id)}
    try:
        recorded = store.record_result(war_id, winner, guild, monarch, proof)
    except Exception:
        log.exception("kcs result failed")
        return _fail("The result could not be recorded.")
    projected = None
    if sovereignty_enabled():
        projected = project(store, war_id)
    text = {
        "claim": "The attackers have taken the throne.",
        "timeout": "The defenders held the castle until the siege ended.",
        "attackers_eliminated": "The attackers are eliminated. The defenders hold the castle.",
    }.get(reason, "The siege is decided.")
    return {
        "ok": True,
        "duplicate": recorded == "duplicate",
        "finished": recorded == "recorded",
        "winner": winner,
        "reason": reason,
        "projected": projected,
        "text": text + " Gold is unchanged.",
    }


def project(store=None, war_id: int = None):
    """Idempotent siege-database projection. Never calls throne._crown."""
    if not sovereignty_enabled():
        return "flag_off"
    store = store or _store()
    ids = [war_id] if war_id is not None else list(store.pending_results())
    results = []
    for wid in ids:
        outcome = store.apply_result(int(wid))
        results.append(outcome)
        if outcome == "applied":
            sov = store.sovereignty()
            if sov.get("rev"):
                store.mark_outbox_delivered(int(sov["rev"]))
    return results[0] if war_id is not None and results else results


def grant_for_placement(player_id: int) -> None:
    _grant(player_id, kcs_balance.xp_place())


def _grant(player_id: int, amount: int) -> None:
    if amount <= 0:
        return
    try:
        import server
        server.WORLD.db.conn.execute(
            "UPDATE players SET engineering_xp = COALESCE(engineering_xp, 0) + ? WHERE id = ?",
            (int(amount), int(player_id)))
        server.WORLD.db.conn.commit()
    except Exception:
        log.exception("kcs engineering xp failed")
