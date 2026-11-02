"""Generic multi-step quests (type \"steps\" in content.QUESTS).

Progress packing: progress = step_index * 10000 + counter
  step_index — current step (0-based) while status is active/ready
  counter    — kill/collect progress within the current step
"""
from __future__ import annotations

from content import QUESTS, ITEMS, MONSTERS, NPCS


def _npc_by_id(npc_id):
    return next((n for n in NPCS if n.get("id") == npc_id), None)


def pack_progress(step_index, counter=0):
    return int(step_index) * 10000 + int(counter)


def unpack_progress(progress):
    p = int(progress or 0)
    return p // 10000, p % 10000


def steps_of(qdef):
    return list((qdef or {}).get("steps") or [])


def current_step(qdef, prog):
    status = (prog or {}).get("status") or "not_started"
    if status == "ready":
        return None
    if status != "active":
        return None
    steps = steps_of(qdef)
    idx, _c = unpack_progress((prog or {}).get("progress"))
    if idx < 0 or idx >= len(steps):
        return None
    return idx, steps[idx]


def step_guide(qdef, prog):
    """(x, y, label) for the current step, or giver when ready, or None."""
    status = (prog or {}).get("status") or "not_started"
    if status == "ready":
        return _giver_xy(qdef)
    cur = current_step(qdef, prog)
    if not cur:
        return None
    _idx, step = cur
    guide = step.get("guide") or {}
    if guide.get("x") is not None and guide.get("y") is not None:
        return int(guide["x"]), int(guide["y"]), guide.get("label") or step.get("objective") or "Quest"
    travel = step.get("guide_travel") or guide.get("travel")
    if travel:
        try:
            from content import TRAVEL_DESTINATIONS
            place = next((p for p in TRAVEL_DESTINATIONS if p.get("id") == travel), None)
            if place:
                return int(place["x"]), int(place["y"]), place.get("label") or travel
        except Exception:
            pass
    kind = step.get("kind")
    if kind in ("talk", "find_npc", "deliver"):
        target = step.get("target") or (qdef.get("giver") if kind == "deliver" else None)
        return _npc_xy(target, step.get("objective") or "Talk")
    if kind == "kill":
        try:
            from content import TRAVEL_DESTINATIONS
            camp = next(
                (d for d in TRAVEL_DESTINATIONS
                 if d.get("kind") == "monster" and d.get("monster") == step.get("target")),
                None,
            )
            if camp:
                return int(camp["x"]), int(camp["y"]), camp.get("label") or "Camp"
        except Exception:
            pass
    return _giver_xy(qdef)


def _npc_xy(npc_id, label=None):
    if not npc_id:
        return None
    # Interior / virtual givers — point at their building door.
    INTERIOR = {
        "hale": (9, 48, "Resting Ox — Hale"),
        "selune": (21, 83, "Moonpetal Inn — Selune"),
        "ivria": (21, 83, "Moonpetal Inn — Ivria"),
        "maelis": (21, 83, "Moonpetal Inn — Maelis"),
        "aerin": (21, 83, "Moonpetal Inn — Aerin"),
        "rhosyn": (21, 83, "Moonpetal Inn — Rhosyn"),
        "tamsin_moon": (21, 83, "Moonpetal Inn — Tamsin"),
        "kaede": (21, 83, "Moonpetal Inn — Kaede"),
        "bryony": (21, 83, "Moonpetal Inn — Bryony"),
    }
    if npc_id in INTERIOR:
        x, y, lab = INTERIOR[npc_id]
        return x, y, label or lab
    npc = _npc_by_id(npc_id)
    if not npc:
        return None
    return int(npc["x"]), int(npc["y"]), label or npc.get("name") or npc_id


def _giver_xy(qdef):
    return _npc_xy(qdef.get("giver"), "Hand in")


def objective_text(qdef, prog, session=None):
    status = (prog or {}).get("status") or "not_started"
    steps = steps_of(qdef)
    n = len(steps)
    if status == "complete":
        return "Done"
    if status == "ready":
        giver = qdef.get("giver") or "quest giver"
        name = _giver_name(giver)
        return f"Return to {name} ({n}/{n})"
    cur = current_step(qdef, prog)
    if not cur:
        return qdef.get("description") or ""
    idx, step = cur
    base = step.get("objective") or step.get("id") or "Continue"
    kind = step.get("kind")
    _si, counter = unpack_progress((prog or {}).get("progress"))
    if kind == "kill":
        need = int(step.get("count") or 1)
        name = (MONSTERS.get(step.get("target")) or {}).get("name") or (step.get("target") or "foe")
        return f"Step {idx + 1}/{n}: {counter}/{need} {name} — {base}"
    if kind == "collect":
        iid = step.get("target")
        need = int(step.get("count") or 1)
        name = (ITEMS.get(iid) or {}).get("name", iid or "item")
        have = 0
        if session is not None:
            try:
                have = session.available_craft_input(iid)
            except Exception:
                have = counter
        else:
            have = counter
        return f"Step {idx + 1}/{n}: {min(have, need)}/{need} {name} — {base}"
    if kind == "collect_multi":
        parts = []
        for iid, need in (step.get("targets") or {}).items():
            name = (ITEMS.get(iid) or {}).get("name", iid)
            have = 0
            if session is not None:
                try:
                    have = session.available_craft_input(iid)
                except Exception:
                    pass
            parts.append(f"{min(have, int(need))}/{int(need)} {name}")
        return f"Step {idx + 1}/{n}: " + " · ".join(parts)
    return f"Step {idx + 1}/{n}: {base}"


def _giver_name(giver_id):
    INTERIOR_NAMES = {
        "hale": "Hale",
        "selune": "Selune",
        "ivria": "Ivria",
        "maelis": "Maelis",
        "aerin": "Aerin",
        "rhosyn": "Rhosyn",
        "tamsin_moon": "Tamsin",
        "kaede": "Kaede",
        "bryony": "Bryony",
    }
    if giver_id in INTERIOR_NAMES:
        return INTERIOR_NAMES[giver_id]
    npc = _npc_by_id(giver_id)
    return (npc or {}).get("name") or (giver_id or "quest giver").replace("_", " ").title()


def _save(session, qid, prog):
    import server
    server.WORLD.db.set_quest_progress(
        session.player_id, qid, prog["status"], int(prog.get("progress") or 0),
    )
    session.quest_log_dirty = True


def advance_to(session, qid, new_index, counter=0):
    """Move to step new_index; if past last step, mark ready."""
    qdef = QUESTS.get(qid) or {}
    prog = session.quests.get(qid)
    if not prog or prog.get("status") != "active":
        return False
    steps = steps_of(qdef)
    if new_index >= len(steps):
        prog["status"] = "ready"
        prog["progress"] = pack_progress(max(0, len(steps) - 1), 0)
        _save(session, qid, prog)
        return True
    prog["progress"] = pack_progress(new_index, counter)
    _save(session, qid, prog)
    return True


def complete_current_step(session, qid):
    """Finish the current step and move to the next (or ready)."""
    qdef = QUESTS.get(qid) or {}
    prog = session.quests.get(qid)
    cur = current_step(qdef, prog)
    if not cur:
        return False
    idx, _step = cur
    return advance_to(session, qid, idx + 1, 0)


def on_talk(session, npc_id):
    """Advance talk / find_npc / deliver steps targeting npc_id. Returns changed."""
    changed = False
    for qid, qdef in QUESTS.items():
        if qdef.get("type") != "steps":
            continue
        prog = session.quests.get(qid)
        if not prog or prog.get("status") != "active":
            continue
        cur = current_step(qdef, prog)
        if not cur:
            continue
        idx, step = cur
        kind = step.get("kind")
        target = step.get("target")
        if kind == "deliver":
            target = target or qdef.get("giver")
        if kind not in ("talk", "find_npc", "deliver"):
            continue
        if target != npc_id:
            continue
        # deliver may require holding an item
        need_item = step.get("item")
        need_count = int(step.get("count") or 1)
        if need_item:
            have = session.available_craft_input(need_item)
            if have < need_count:
                continue
            if step.get("consume"):
                session.consume_craft_input(need_item, need_count)
        if complete_current_step(session, qid):
            changed = True
            # If this was the last step, status is ready — auto-complete on deliver to giver
            prog = session.quests.get(qid)
            if prog and prog.get("status") == "ready" and kind == "deliver":
                # Leave ready for turn-in UI, unless auto_complete
                if step.get("auto_complete") or qdef.get("auto_complete_on_deliver"):
                    pass  # turn-in still grants rewards via handle_quest_turnin
    return changed


def on_kill(session, monster_type):
    monster_type = (MONSTERS.get(monster_type) or {}).get("quest_as") or monster_type
    changed = False
    for qid, qdef in QUESTS.items():
        if qdef.get("type") != "steps":
            continue
        prog = session.quests.get(qid)
        if not prog or prog.get("status") != "active":
            continue
        cur = current_step(qdef, prog)
        if not cur:
            continue
        idx, step = cur
        if step.get("kind") != "kill" or step.get("target") != monster_type:
            continue
        need = int(step.get("count") or 1)
        _si, counter = unpack_progress(prog.get("progress"))
        counter += 1
        if counter >= need:
            complete_current_step(session, qid)
        else:
            prog["progress"] = pack_progress(idx, counter)
            _save(session, qid, prog)
        changed = True
    return changed


def refresh_collect(session):
    """Mark collect / collect_multi steps ready to advance when inventory meets need."""
    changed = False
    for qid, qdef in QUESTS.items():
        if qdef.get("type") != "steps":
            continue
        prog = session.quests.get(qid)
        if not prog or prog.get("status") != "active":
            continue
        cur = current_step(qdef, prog)
        if not cur:
            continue
        idx, step = cur
        kind = step.get("kind")
        if kind == "collect":
            iid = step.get("target")
            need = int(step.get("count") or 1)
            have = session.available_craft_input(iid)
            if have >= need:
                # Auto-advance collect steps (item stays until a later deliver consumes)
                if step.get("auto_advance", True):
                    if step.get("consume_on_advance"):
                        session.consume_craft_input(iid, need)
                    complete_current_step(session, qid)
                    changed = True
                else:
                    prog["progress"] = pack_progress(idx, min(have, need))
                    _save(session, qid, prog)
                    changed = True
            else:
                new_p = pack_progress(idx, have)
                if int(prog.get("progress") or 0) != new_p:
                    prog["progress"] = new_p
                    _save(session, qid, prog)
                    changed = True
        elif kind == "collect_multi":
            targets = step.get("targets") or {}
            if all(session.available_craft_input(iid) >= int(need) for iid, need in targets.items()):
                if step.get("auto_advance", True):
                    if step.get("consume_on_advance"):
                        for iid, need in targets.items():
                            session.consume_craft_input(iid, int(need))
                    complete_current_step(session, qid)
                    changed = True
    return changed


def on_goto(session, x, y):
    """Advance goto steps when the player stands near the guide tile."""
    changed = False
    x, y = int(x), int(y)
    for qid, qdef in QUESTS.items():
        if qdef.get("type") != "steps":
            continue
        prog = session.quests.get(qid)
        if not prog or prog.get("status") != "active":
            continue
        cur = current_step(qdef, prog)
        if not cur:
            continue
        _idx, step = cur
        if step.get("kind") != "goto":
            continue
        guide = step.get("guide") or {}
        gx, gy = guide.get("x"), guide.get("y")
        if gx is None or gy is None:
            continue
        rad = int(step.get("radius") or guide.get("radius") or 2)
        if max(abs(x - int(gx)), abs(y - int(gy))) <= rad:
            complete_current_step(session, qid)
            changed = True
    return changed


def try_interior_offer_lines(session, giver_id):
    """Quest offer / active / ready blurb for interior NPCs (Hale, fairies)."""
    out = []
    for qid, qdef in QUESTS.items():
        if qdef.get("type") != "steps":
            continue
        if qdef.get("giver") != giver_id:
            continue
        prog = session.quests.get(qid) or {"status": "not_started", "progress": 0}
        status = prog.get("status")
        if status == "complete":
            continue
        if status == "not_started" or qid not in session.quests:
            if not _prereqs_met(session, qdef):
                continue
            out.append({
                "quest_id": qid,
                "state": "offerable",
                "name": qdef.get("name"),
                "description": qdef.get("description"),
                "objective": qdef.get("description"),
            })
        elif status == "active":
            out.append({
                "quest_id": qid,
                "state": "active",
                "name": qdef.get("name"),
                "objective": objective_text(qdef, prog, session),
            })
        elif status == "ready":
            out.append({
                "quest_id": qid,
                "state": "ready",
                "name": qdef.get("name"),
                "objective": objective_text(qdef, prog, session),
            })
    return out


def _prereqs_met(session, qdef):
    req = qdef.get("requires")
    if not req:
        return True
    if isinstance(req, str):
        req = [req]
    for qid in req:
        st = (session.quests.get(qid) or {}).get("status")
        if st != "complete":
            return False
    return True


def fairy_id_from_name(name):
    """Map Moonpetal display name → quest npc id."""
    MAP = {
        "Selune": "selune",
        "Ivria": "ivria",
        "Maelis": "maelis",
        "Aerin": "aerin",
        "Rhosyn": "rhosyn",
        "Tamsin": "tamsin_moon",
        "Kaede": "kaede",
        "Bryony": "bryony",
        "Nyx": "nyx",
    }
    return MAP.get(name) or (name or "").lower()
