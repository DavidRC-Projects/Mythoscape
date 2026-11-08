"""Playable King's Castle siege loop. Provisional numbers live in kcs_balance.

The client cannot declare damage, a winner, or a crown. Gold is not spent
and is not taken when the castle falls. Sovereignty projection, when its own
flag is on, writes only the siege database. It does not call throne._crown.
"""
from __future__ import annotations

import json
import logging
import os
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
        return public_status(session)
    except Exception:
        log.exception("kcs lobby failed")
        return _fail("The siege can't be reached right now.")


def public_status(session=None) -> dict:
    """One status body for the panel, the lobby, and a reconnect."""
    if not kcs_siege.enabled():
        return _fail("The siege is closed.")
    store = _store()
    war = store.open_war() or store.latest_war()
    sandbox = os.environ.get("KCS_SANDBOX_PREP") == "1"
    if war is None:
        body = _empty_status(sandbox)
        body["ownership"] = _ownership_view()
        return body
    rows = store.roster_rows(war.war_id)
    you = None
    if session is not None:
        for pid, side, _dep, _elim in rows:
            if int(pid) == int(session.player_id):
                you = side
    ends = store.get_clock(war.war_id)
    started = _battle_started(store, war.war_id, ends)
    now = time.time()
    remaining = None
    grace_left = None
    if war.status == "active":
        if ends is not None:
            remaining = max(0, int(ends - now))
        if started is not None:
            grace_left = max(0, int(float(started) + kcs_balance.deploy_grace() - now))
    result = _result_view(store, war.war_id)
    previous = None
    if war.status != "resolved":
        prev = store.previous_resolved(war.war_id)
        if prev is not None:
            previous = _result_view(store, prev)
    counts = _side_counts(rows)
    phase = {
        "registration": "Registration",
        "locking": "Starting",
        "active": "Battle",
        "resolving": "Deciding",
        "resolved": "Finished",
        "voided": "Archived",
    }.get(war.status, war.status)
    if result:
        text = result["text"]
    elif sandbox and war.status == "registration":
        text = (
            "SANDBOX ONLY: the next test siege is open for registration. "
            "Previous wars, eliminations, and accounts were kept."
        )
    else:
        text = f"Siege is {war.status}. You are {you or 'not enlisted'}."
    body = {
        "ok": True,
        "war_id": war.war_id,
        "status": war.status,
        "phase": phase,
        "your_side": you,
        "ends_at": ends,
        "started_at": started,
        "remaining": remaining,
        "grace_seconds": int(kcs_balance.deploy_grace()),
        "grace_left": grace_left,
        "grace_rule": kcs_balance.grace_rule(),
        "objectives": _objectives(store, war.war_id),
        "result": result,
        "previous": previous,
        "ownership": _ownership_view(),
        "sandbox": sandbox,
        "text": text,
    }
    body.update(counts)
    if sandbox:
        body["sandbox_players"] = _sandbox_players()
    return body


def _empty_status(sandbox: bool) -> dict:
    body = {
        "ok": True,
        "status": "none",
        "phase": "No siege",
        "text": "No siege is open. Enlist to start one.",
        "your_side": None,
        "attack": 0,
        "defend": 0,
        "attack_enlisted": 0,
        "defend_enlisted": 0,
        "attack_deployed": 0,
        "defend_deployed": 0,
        "attack_eliminated": 0,
        "defend_eliminated": 0,
        "attack_absent": 0,
        "defend_absent": 0,
        "ends_at": None,
        "started_at": None,
        "remaining": None,
        "grace_seconds": int(kcs_balance.deploy_grace()),
        "grace_left": None,
        "grace_rule": kcs_balance.grace_rule(),
        "objectives": [],
        "result": None,
        "previous": None,
        "sandbox": sandbox,
    }
    if sandbox:
        body["sandbox_players"] = _sandbox_players()
    return body


def _side_counts(rows) -> dict:
    out = {}
    for side in ("attack", "defend"):
        group = [row for row in rows if row[1] == side]
        out[side] = sum(1 for row in group if not row[3])
        out[f"{side}_enlisted"] = len(group)
        out[f"{side}_deployed"] = sum(1 for row in group if row[2] and not row[3])
        out[f"{side}_eliminated"] = sum(1 for row in group if row[3])
        out[f"{side}_absent"] = sum(1 for row in group if not row[2] and not row[3])
    return out


def _objectives(store, war_id: int) -> list:
    states = store.openings(war_id)
    hps = store.opening_hps(war_id)
    named = (("main_gate", "Main gate"), ("keep_doors", "Keep doors"), ("throne_doors", "Throne doors"))
    lines = []
    for oid, label in named:
        if oid not in states and oid not in hps:
            continue
        state = states.get(oid, "intact")
        hp = hps.get(oid)
        max_hp = kcs_balance.opening_max_hp(oid)
        if state == "destroyed" or (hp is not None and int(hp) <= 0):
            shown = "breached"
        elif hp is not None and int(hp) < max_hp:
            shown = f"damaged {int(hp)}/{max_hp}"
        else:
            shown = "intact"
        lines.append({"id": oid, "label": label, "state": shown, "hp": hp, "max_hp": max_hp})
    return lines


def _result_view(store, war_id: int):
    existing = store.result(war_id)
    if not existing:
        return None
    reason = ""
    try:
        proof = json.loads(existing.get("proof_json") or "{}")
        reason = str(proof.get("reason") or "")
    except (TypeError, ValueError):
        reason = ""
    winner = existing.get("winner_side")
    text = {
        "claim": "The attackers have taken the throne.",
        "timeout": "The defenders held the castle until the siege ended.",
        "attackers_eliminated": "The attackers are eliminated. The defenders hold the castle.",
    }.get(reason, f"The siege is decided for the {winner} side.")
    return {
        "war_id": int(war_id),
        "winner": winner,
        "reason": reason,
        "monarch_player_id": existing.get("monarch_player_id"),
        "text": text + " Gold is unchanged.",
    }


def _ownership_view() -> dict:
    """Read the throne and King's Castle rows the rest of the game already uses."""
    empty = {"crown_line": "", "castle_line": "", "monarch": None, "castle_owner": None, "royal_title": None}
    try:
        import server
        conn = server.WORLD.db.conn
        tables = {row[0] for row in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'")}
    except Exception:
        return empty
    crown = ""
    monarch = None
    title = None
    if "throne" in tables:
        try:
            st = conn.execute(
                "SELECT monarch_kind, monarch_player_id FROM throne WHERE id=1").fetchone()
        except Exception:
            st = None
        if st is not None and st[0] == "player" and st[1]:
            who = conn.execute(
                "SELECT char_name, royal_title FROM players WHERE id=?", (int(st[1]),)).fetchone()
            if who is not None:
                monarch = who[0]
                title = who[1]
                if title and monarch:
                    crown = f"{title} {monarch} wears the crown."
                elif monarch:
                    crown = f"{monarch} wears the crown."
        elif st is not None:
            crown = "The crown is not held by a player."
    castle = ""
    owner = None
    if "castle_ownership" in tables:
        try:
            row = conn.execute(
                "SELECT owner_display_name FROM castle_ownership WHERE castle_id='king'").fetchone()
        except Exception:
            row = None
        if row is not None and row[0]:
            owner = row[0]
            castle = f"King's Castle is held by {owner}."
        else:
            castle = "King's Castle is held by the crown."
    return {
        "crown_line": crown,
        "castle_line": castle,
        "monarch": monarch,
        "castle_owner": owner,
        "royal_title": title,
    }


def _sandbox_players() -> list:
    try:
        import server
        rows = server.WORLD.db.conn.execute(
            "SELECT id, char_name FROM players ORDER BY id LIMIT 24").fetchall()
    except Exception:
        log.exception("kcs sandbox roster failed")
        return []
    return [{"player_id": int(row[0]), "name": row[1] or f"player {row[0]}"} for row in rows]


def _battle_started(store, war_id: int, ends):
    started = store.started_at(war_id)
    if started is not None:
        return started
    if ends is None:
        return None
    return float(ends) - kcs_balance.war_seconds()


def prepare_next(assignments) -> dict:
    """Sandbox-only fresh registration. Archives the open registration if it is still only a roster.

    Refuses a battle that has started. Does not delete wars, results, or eliminations,
    and does not create accounts.
    """
    if os.environ.get("KCS_SANDBOX_PREP") != "1":
        return _fail("Sandbox preparation is not enabled.")
    if not kcs_siege.enabled():
        return _fail("The siege is closed.")
    if not isinstance(assignments, list) or not assignments:
        return _fail("Choose the test participants and their sides first.")
    try:
        import server
        conn = server.WORLD.db.conn
        chosen = []
        seen = set()
        for item in assignments:
            if not isinstance(item, dict):
                return _fail("Choose the test participants and their sides first.")
            try:
                pid = int(item.get("player_id"))
            except (TypeError, ValueError):
                return _fail("Choose the test participants and their sides first.")
            side = item.get("side")
            if side not in ("attack", "defend"):
                return _fail("Each participant needs an attacker or defender side.")
            if pid in seen:
                return _fail("A participant can only be listed once.")
            seen.add(pid)
            row = conn.execute("SELECT id FROM players WHERE id=?", (pid,)).fetchone()
            if row is None:
                return _fail("That participant is not an existing character. No account was created.")
            chosen.append((pid, side))
        store = _store()
        war = store.open_war()
        if war is not None and war.status in ("locking", "active", "resolving"):
            return _fail("A battle is in progress. It was not reset.")
        if war is not None and war.status == "registration":
            rows = store.roster_rows(war.war_id)
            if any(row[3] for row in rows):
                return _fail("This registration has eliminations. It was not reset.")
            if any(row[2] for row in rows):
                return _fail("Someone is already deployed. It was not reset.")
            store.set_war_status(war.war_id, "voided")
        fresh = store.create_war(f"kcs-sandbox-{int(time.time())}")
        for pid, side in chosen:
            store.enlist(fresh.war_id, pid, side)
    except Exception as exc:
        log.exception("kcs sandbox prepare failed")
        return _fail(str(exc) or "The next test siege was not prepared.")
    body = public_status()
    body["text"] = (
        "SANDBOX ONLY: the next test siege is open for registration. "
        "Previous wars, eliminations, and accounts were kept."
    )
    return body


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
            kind = engine.get("engine_type") or ""
            spec = kcs_balance.engine_spec(kind) if (
                kind in kcs_balance.ENGINES or kind in kcs_balance.DEFENDER_ENGINES) else {}
            rec = combat.get(int(engine.get("engine_id")))
            engine["max_hp"] = int(spec.get("hp") or 1)
            engine["hp"] = rec[0] if rec else engine["max_hp"]
            engine["cooldown_until"] = rec[1] if rec else 0
            engine["facing"] = kcs_balance.FACE_NAME.get(int(engine.get("rotation") or 0), "north")
        body["ends_at"] = store.get_clock(war_id)
        panel = public_status()
        body["status_panel"] = {key: value for key, value in panel.items() if key != "ok"}
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


def _attacker_holds(row, started, now) -> bool:
    """True when this attacker still stops a defender elimination victory.

    Deployed living attackers hold the field. An enlisted attacker who has not
    deployed holds it only until the grace ends. Elimination is never flipped
    on just because they did not deploy.
    """
    _pid, _side, deployed, eliminated = row
    if eliminated:
        return False
    if deployed:
        return True
    if started is None:
        return True
    return now < float(started) + kcs_balance.deploy_grace()


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
        if not attackers:
            return None
        ends = store.get_clock(war.war_id)
        started = _battle_started(store, war.war_id, ends)
        now = time.time()
        if any(_attacker_holds(row, started, now) for row in attackers):
            return None
        return _finish(store, war.war_id, "defend", None, "attackers_eliminated")
    except Exception:
        log.exception("kcs elimination victory check failed")
        return None


def resolution_if_due():
    """Timeout first, then an elimination victory once the deploy grace has ended."""
    due = timeout_if_due()
    if due:
        return due
    return defenders_if_attackers_gone()


def fire(session, engine_type: str) -> dict:
    due = resolution_if_due()
    if due:
        return due
    ctx, err = _live(session)
    if err:
        return err
    store, war = ctx
    side = _side(session)
    if side == "defend":
        return _fire_defender(session, store, war, engine_type)
    if side != "attack":
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
        live_cells = {
            oid: tiles for oid, tiles in cells.items()
            if states.get(oid, "intact") != "destroyed" and hps.get(oid, 1) > 0
        }
        hit = kcs_balance.shot_target(engine.tiles, engine.rotation, engine_type, live_cells)
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
        splash = _splash_hits(store, war.war_id, cells.get(oid) or [], combat)
        rev = store.write_shot(war.war_id, engine.engine_id, hp, cd, oid, new_hp, state, splash)
        _grant(session.player_id, kcs_balance.xp_shot())
        aim = (cells.get(oid) or engine.tiles)[0]
        return {
            "ok": True,
            "text": f"{engine_type.replace('_', ' ')} hit {oid.replace('_', ' ')} for {damage}. It is {state}.",
            "opening": {"opening_id": oid, "state": state, "rev": rev, "hp": new_hp,
                        "plane": kcs_siege.PLANE_BATTLEFIELD},
            "engine_id": engine.engine_id,
            "shot": _shot_line(engine, aim[0], aim[1]),
            "engines": [{"engine_id": engine.engine_id, "hp": hp, "cooldown_until": cd}]
                       + [{"engine_id": eid, "hp": shp} for eid, shp in splash],
        }
    return _fail(refusal)


def _splash_hits(store, war_id, gate_tiles, combat):
    """Defender engines standing on the opening an attacker just hit."""
    amount = kcs_balance.opening_splash()
    if amount <= 0 or not gate_tiles:
        return []
    hits = []
    for engine in store.engines(war_id):
        if engine.side != "defend" or engine.engine_type not in kcs_balance.DEFENDER_ENGINES:
            continue
        near = any(
            max(abs(int(tx) - int(gx)), abs(int(ty) - int(gy))) <= 1
            for tx, ty in engine.tiles for gx, gy in gate_tiles
        )
        if not near:
            continue
        spec = kcs_balance.DEFENDER_ENGINES[engine.engine_type]
        hp = combat.get(engine.engine_id, (spec["hp"], 0.0))[0]
        if hp <= 0:
            continue
        hits.append((engine.engine_id, max(0, int(hp) - amount)))
    return hits


def _foes(session):
    me = _side(session)
    try:
        import server
        sessions = list(server.WORLD.sessions.values())
    except Exception:
        sessions = []
    found = []
    plane = (session.dungeon or {}).get("plane")
    for other in sessions:
        if other is session or not kcs_siege.on_map(other):
            continue
        if (other.dungeon or {}).get("plane") != plane:
            continue
        if _side(other) == me or _side(other) not in ("attack", "defend"):
            continue
        if int(getattr(other, "hp", 0) or 0) <= 0:
            continue
        found.append(other)
    return found


def _fire_defender(session, store, war, engine_type: str) -> dict:
    if (session.dungeon or {}).get("plane") != kcs_siege.PLANE_BATTLEFIELD:
        return _fail("Defensive engines are used from the walls.")
    roster = store.roster_status(war.war_id, int(session.player_id))
    if roster.side != "defend" or not roster.deployed or roster.eliminated:
        return _fail("You cannot operate siege equipment.")
    if engine_type not in kcs_balance.DEFENDER_ENGINES:
        return _fail("Choose a ballista or a cauldron.")
    spec = kcs_balance.DEFENDER_ENGINES[engine_type]
    label = engine_type.replace("_", " ")
    owned = [
        e for e in store.engines(war.war_id)
        if e.player_id == int(session.player_id) and e.engine_type == engine_type and e.side == "defend"
    ]
    if not owned:
        return _fail(f"You have no {label} on the wall.")
    px, py = int(session.x), int(session.y)
    beside = [e for e in owned if kcs_balance.beside(px, py, e.tiles)]
    if not beside:
        return _fail(f"Stand beside your {label} to use it.")
    combat = store.engine_combat_map(war.war_id)
    now = time.time()
    refusal = "That engine cannot fire."
    for engine in beside:
        hp, ready = combat.get(engine.engine_id, (spec["hp"], 0.0))
        if hp <= 0:
            refusal = "That engine is wrecked."
            continue
        if ready > now:
            refusal = "That engine is still reloading."
            continue
        outcome = _defender_shot(session, store, war, engine, spec, combat, now, hp)
        if outcome is None:
            refusal = "Nothing is in front of that engine."
            continue
        return outcome
    return _fail(refusal)


def _defender_shot(session, store, war, engine, spec, combat, now, hp):
    engine_type = engine.engine_type
    cd = now + spec["cooldown"] * kcs_balance.cooldown_scale()
    attackers = []
    for other in store.engines(war.war_id):
        if other.side != "attack" or other.engine_type not in kcs_balance.ENGINES:
            continue
        ohp = combat.get(other.engine_id, (kcs_balance.ENGINES[other.engine_type]["hp"], 0.0))[0]
        if ohp <= 0:
            continue
        attackers.append((other, int(ohp)))
    foes = _foes(session)
    shooter = {"engine_id": engine.engine_id, "hp": hp, "cooldown_until": cd}
    if engine_type == "cauldron":
        cells = []
        for tiles in _opening_cells().values():
            cells.extend(tiles)
        zone = kcs_balance.cauldron_zone(engine.tiles, cells, spec["range"])
        hits = []
        for other, ohp in attackers:
            if any((int(tx), int(ty)) in zone for tx, ty in other.tiles):
                hits.append((other.engine_id, max(0, ohp - int(spec["engine"]))))
        players = []
        for foe in foes:
            if (int(foe.x), int(foe.y)) not in zone:
                continue
            dmg = int(spec["player"])
            foe.hp = max(0, int(foe.hp) - dmg)
            players.append({
                "player_id": foe.player_id, "hp": foe.hp, "killed": foe.hp <= 0, "damage": dmg,
            })
        if not hits and not players:
            return None
        store.write_engine_action(war.war_id, engine.engine_id, hp, cd, hits)
        _grant(session.player_id, kcs_balance.xp_shot())
        shot = None
        if hits:
            struck = next((e for e in store.engines(war.war_id) if e.engine_id == hits[0][0]), None)
            if struck is not None:
                shot = _shot_line(engine, struck.tiles[0][0], struck.tiles[0][1])
        elif players:
            foe = next((f for f in foes if f.player_id == players[0]["player_id"]), None)
            if foe is not None:
                shot = _shot_line(engine, foe.x, foe.y)
        parts = []
        if hits:
            parts.append(f"{len(hits)} engine" + ("s" if len(hits) != 1 else ""))
        if players:
            parts.append(f"{len(players)} attacker" + ("s" if len(players) != 1 else ""))
        body = {
            "ok": True,
            "text": f"The cauldron douses the apron. It hits {' and '.join(parts)}.",
            "engine_id": engine.engine_id,
            "engines": [shooter] + [{"engine_id": eid, "hp": nhp} for eid, nhp in hits],
            "players": players,
        }
        if shot is not None:
            body["shot"] = shot
        return body
    aimed = kcs_balance.aimed_target(
        engine.tiles, engine.rotation, engine_type,
        [(other.engine_id, other.tiles) for other, _ohp in attackers],
    )
    if aimed is not None:
        eid = aimed[0]
        other, ohp = next(item for item in attackers if item[0].engine_id == eid)
        new_hp = max(0, ohp - int(spec["engine"]))
        store.write_engine_action(war.war_id, engine.engine_id, hp, cd, [(eid, new_hp)])
        _grant(session.player_id, kcs_balance.xp_shot())
        word = "wrecked" if new_hp <= 0 else "damaged"
        return {
            "ok": True,
            "text": f"Ballista {word} the {other.engine_type.replace('_', ' ')} ({new_hp} hp).",
            "engine_id": engine.engine_id,
            "shot": _shot_line(engine, other.tiles[0][0], other.tiles[0][1]),
            "engines": [shooter, {"engine_id": eid, "hp": new_hp}],
        }
    aimed = kcs_balance.aimed_target(
        engine.tiles, engine.rotation, engine_type,
        [(foe.player_id, [(int(foe.x), int(foe.y))]) for foe in foes],
    )
    if aimed is None:
        return None
    foe = next(item for item in foes if item.player_id == aimed[0])
    dmg = int(spec["player"])
    foe.hp = max(0, int(foe.hp) - dmg)
    store.write_engine_action(war.war_id, engine.engine_id, hp, cd, [])
    _grant(session.player_id, kcs_balance.xp_shot())
    return {
        "ok": True,
        "text": f"Ballista hits for {dmg}.",
        "engine_id": engine.engine_id,
        "shot": _shot_line(engine, foe.x, foe.y),
        "engines": [shooter],
        "players": [{"player_id": foe.player_id, "hp": foe.hp, "killed": foe.hp <= 0, "damage": dmg}],
    }


def _shot_line(engine, tx, ty) -> dict:
    ox, oy = engine.tiles[0]
    return {
        "engine_id": engine.engine_id,
        "x": int(ox), "y": int(oy),
        "tx": int(tx), "ty": int(ty),
    }


def repair(session) -> dict:
    due = resolution_if_due()
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
    due = resolution_if_due()
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
    wreck = _strike_engine(store, war.war_id, px, py, me)
    if wreck:
        return wreck
    return _fail("Nobody is in reach.")


def _strike_engine(store, war_id, px, py, my_side):
    combat = store.engine_combat_map(war_id)
    nearest = None
    for engine in store.engines(war_id):
        if engine.side == my_side or engine.side not in ("attack", "defend"):
            continue
        if engine.engine_type not in kcs_balance.ENGINES and engine.engine_type not in kcs_balance.DEFENDER_ENGINES:
            continue
        hp = combat.get(engine.engine_id, (kcs_balance.engine_spec(engine.engine_type)["hp"], 0))[0]
        if hp <= 0:
            continue
        dist = min(max(abs(px - tx), abs(py - ty)) for tx, ty in engine.tiles)
        if dist <= 1 and (nearest is None or dist < nearest[0]):
            nearest = (dist, engine, hp)
    if nearest is None:
        return None
    engine, hp = nearest[1], nearest[2]
    new_hp = max(0, hp - kcs_balance.strike_damage())
    store.damage_engine_hp(war_id, engine.engine_id, new_hp)
    word = "wrecked" if new_hp <= 0 else "damaged"
    return {
        "ok": True,
        "text": f"You {word} the {engine.engine_type.replace('_', ' ')} ({new_hp} hp).",
        "engine_id": engine.engine_id,
        "engine_hp": new_hp,
        "engines": [{"engine_id": engine.engine_id, "hp": new_hp}],
    }


def claim(session) -> dict:
    due = resolution_if_due()
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
        existing = None
        try:
            existing = store.result(war_id)
        except Exception:
            existing = None
        if existing is not None:
            return {
                "ok": True,
                "duplicate": True,
                "finished": False,
                "winner": existing.get("winner_side"),
                "text": f"The siege is already decided for the {existing.get('winner_side')} side.",
            }
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


def pack(session, engine_type: str = "") -> dict:
    """Pick up one engine you placed. Someone else's engine stays where it is."""
    due = resolution_if_due()
    if due:
        return due
    ctx, err = _live(session)
    if err:
        return err
    store, war = ctx
    side = _side(session)
    if side not in ("attack", "defend"):
        return _fail("Only the side that placed an engine can pack it.")
    owned = [
        e for e in store.engines(war.war_id)
        if e.player_id == int(session.player_id) and e.side == side
    ]
    if engine_type:
        owned = [e for e in owned if e.engine_type == engine_type]
    if not owned:
        return _fail("You have no engine of that kind to pack.")
    px, py = int(session.x), int(session.y)
    if side == "defend":
        owned = [e for e in owned if kcs_balance.beside(px, py, e.tiles)]
        if not owned:
            return _fail("Stand beside your engine to pack it.")
    owned.sort(key=lambda e: min(max(abs(px - tx), abs(py - ty)) for tx, ty in e.tiles))
    engine = owned[0]
    try:
        store.remove_engine(war.war_id, engine.engine_id, int(session.player_id))
    except Exception as exc:
        if exc.__class__.__name__ != "PlacementRejected":
            log.exception("kcs pack failed")
        return _fail(str(exc) or "That engine stayed where it is.")
    return {"ok": True, "text": f"Packed the {engine.engine_type.replace('_', ' ')}.",
            "engine_id": engine.engine_id}


def project(store=None, war_id: int = None):
    """Record sovereignty, then deliver the throne and King's Castle once.

    Never calls throne._crown. The outbox stays pending until the game
    database transaction commits, so a retry finishes the same result.
    """
    if not sovereignty_enabled():
        return "flag_off"
    store = store or _store()
    ids = [war_id] if war_id is not None else list(store.pending_results())
    results = []
    for wid in ids:
        outcome = store.apply_result(int(wid))
        results.append(outcome)
        if outcome in ("applied", "already_applied"):
            _deliver_pending(store, int(wid))
    return results[0] if war_id is not None and results else results


def _deliver_pending(store, war_id: int) -> None:
    import json
    import kcs_throne_dest
    import server
    conn = server.WORLD.db.conn
    for rev, _kind, raw in store.undelivered_outbox():
        try:
            payload = json.loads(raw)
        except (TypeError, ValueError):
            log.exception("kcs outbox payload was not readable")
            continue
        if int(payload.get("war_id") or 0) != int(war_id):
            continue
        kcs_throne_dest.deliver(conn, payload)
        store.mark_outbox_delivered(int(rev))


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
