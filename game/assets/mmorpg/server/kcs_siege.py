"""Bridge from the live server onto the isolated King's Castle Siege foundations.

The siege map, roster, and elimination record live in ``kcs_server`` and in
their own SQLite file. This module never opens ``world.db``, never calls
``throne._crown``, and never writes Castle Realm ownership. Flag default is
OFF (``USE_KINGS_CASTLE_SIEGE``). When the flag is off, no siege database is
created.

Presence on either siege plane is granted only by ``EntryGuard.may_enter``.
Callers must obey the decision. A denial, a store error, or an elimination
that has not been confirmed yet leaves the player off the siege map.
"""
from __future__ import annotations

import logging
import os
import threading
from typing import Optional

import database
import feature_flags
from kcs_server.guard import (
    PLANE_BATTLEFIELD,
    PLANE_THRONE,
    SIEGE_PLANES,
    DeathOutcome,
    Decision,
    EntryGuard,
)
from kcs_server.plane import SiegeMap
from kcs_server.store import FaultPlan, KCSStore

log = logging.getLogger("kcs_siege")

DUNGEON_ID = "kings_castle_siege"
# Denials that mean "this resume must not be retried". A store outage
# (``guard_error``) keeps the resume so a living deployment can be restored
# once the store answers, but the player is still not placed on the map.
CLEAR_RESUME_CODES = frozenset({
    "eliminated",
    "elimination_pending",
    "not_on_roster",
    "not_deployed",
    "teleport_blocked",
    "no_open_war",
    "war_not_live",
    "not_a_siege_plane",
    "unknown_reason",
    "deploy_refused",
})

_lock = threading.Lock()
_store: Optional[KCSStore] = None
_guard: Optional[EntryGuard] = None
_map: Optional[SiegeMap] = None
_configured_path: Optional[str] = None
_configured_journal: Optional[str] = None
_configured_faults: Optional[FaultPlan] = None
# Player ids whose siege death was accepted in this process but not yet
# confirmed in the store. Checked before any presence grant.
_unconfirmed: set = set()
# Deaths currently inside EntryGuard.on_death. Presence grants wait them out.
_dying: set = set()


def enabled() -> bool:
    """Shared process switch. Default off. Tests may assign the flag."""
    return bool(getattr(feature_flags, "USE_KINGS_CASTLE_SIEGE", False))


def on_map(session) -> bool:
    data = getattr(session, "dungeon", None) or {}
    return data.get("id") == DUNGEON_ID


def targets_siege(dest) -> bool:
    """True when a teleport destination would land on the siege map."""
    if not isinstance(dest, dict):
        return False
    for key in ("id", "where", "plane", "map"):
        value = str(dest.get(key) or "")
        if not value:
            continue
        if value == DUNGEON_ID or value in SIEGE_PLANES or value.startswith(DUNGEON_ID + "."):
            return True
    return False


def plane_from_dest(dest) -> str:
    plane = str((dest or {}).get("plane") or "")
    if plane in SIEGE_PLANES:
        return plane
    where = str((dest or {}).get("where") or "")
    if where in SIEGE_PLANES:
        return where
    return PLANE_BATTLEFIELD


def transition_at(plane, x, y):
    """Intra-siege plane link at a tile.

    No link is authored in this integration. Battlefield and throne are
    reached only through the guarded entry, teleport, and resume paths, or
    through ``retarget`` if a link is added later. The tuple list is the
    single place a link may be declared.
    """
    for src, tx, ty, dst in _PLANE_LINKS:
        if src == plane and int(tx) == int(x) and int(ty) == int(y):
            return dst
    return None


# (from_plane, x, y, to_plane). Empty on purpose; see transition_at.
_PLANE_LINKS = ()


def deny_message(decision: Decision) -> str:
    code = decision.code
    if code == "feature_disabled":
        return "The siege is closed."
    if code in ("eliminated", "elimination_pending"):
        return "You are eliminated from this siege."
    if code == "teleport_blocked":
        return "You can't teleport into the siege."
    if code in ("not_on_roster", "not_deployed", "deploy_refused"):
        return "You are not deployed for this siege."
    if code in ("no_open_war", "war_not_live"):
        return "There is no siege to enter."
    if code == "guard_error":
        return "The siege can't be reached right now."
    return "You can't enter the siege."


def configure(path: str, journal_path: Optional[str] = None, faults: Optional[FaultPlan] = None) -> None:
    """Point the siege store at a database path. Tests pass a temporary file.

    Refuses ``world.db`` and the live server database path before opening
    anything. ``:memory:`` is accepted for tests.
    """
    global _configured_path, _configured_journal, _configured_faults
    _reject_live_db(path)
    with _lock:
        _close_locked()
        _configured_path = path
        _configured_journal = journal_path
        _configured_faults = faults


def simulate_restart() -> None:
    """Drop this process's store and unconfirmed set, then reopen on next use.

    The journal file and the database file stay. The rebuilt guard replays
    the journal, which is what a process restart does.
    """
    global _unconfirmed, _dying
    with _lock:
        _close_locked()
        _unconfirmed = set()
        _dying = set()


def close() -> None:
    with _lock:
        _close_locked()


def store() -> KCSStore:
    return _require_guard().store


def guard() -> EntryGuard:
    return _require_guard()


def siege_map() -> SiegeMap:
    global _map
    if _map is None:
        _map = SiegeMap.load()
    return _map


def decide(player_id: int, plane_id: str, reason: str) -> Decision:
    """Fail-closed presence decision. Flag off does not open the store."""
    plane_id = str(plane_id or "")
    if not EntryGuard.applies(plane_id):
        return Decision(False, "none", "not_a_siege_plane")
    if not enabled():
        return Decision(False, "none", "feature_disabled")
    pid = int(player_id)
    if pid in _dying:
        return Decision(False, "none", "elimination_pending")
    if pid in _unconfirmed:
        try:
            _require_guard().flush_pending()
        except Exception:
            log.exception("kcs flush of unconfirmed elimination failed")
            return Decision(False, "none", "elimination_pending")
        if pid in _dying:
            return Decision(False, "none", "elimination_pending")
        try:
            still = any(p == pid for (_w, p) in _require_guard().pending().items())
        except Exception:
            log.exception("kcs pending read failed")
            return Decision(False, "none", "elimination_pending")
        if still or not _eliminated_in_store(pid):
            return Decision(False, "none", "elimination_pending")
        _unconfirmed.discard(pid)
    try:
        return _require_guard().may_enter(pid, plane_id, reason)
    except Exception:
        log.exception("kcs guard failed")
        return Decision(False, "none", "guard_error")


def presence_decision(session) -> Decision:
    """Re-check someone already standing on a siege plane."""
    data = getattr(session, "dungeon", None) or {}
    plane = data.get("plane") or ""
    reason = "spectate" if data.get("mode") == "spectator" else "reconnect"
    return decide(session.player_id, plane, reason)


def record_death(player_id: int) -> DeathOutcome:
    """Durable elimination. Call before respawn, loot, or leaving the plane.

    The player is held in ``_unconfirmed`` before the store is touched, so a
    store outage still denies the next presence grant in this process.
    """
    pid = int(player_id)
    _dying.add(pid)
    _unconfirmed.add(pid)
    try:
        try:
            outcome = _require_guard().on_death(pid, "death")
        except Exception:
            log.exception("kcs death record failed")
            return DeathOutcome(True, False, False, False)
        if outcome.persisted or not outcome.eliminated:
            _unconfirmed.discard(pid)
        return outcome
    finally:
        _dying.discard(pid)


def walkable(session, x: int, y: int) -> bool:
    data = getattr(session, "dungeon", None) or {}
    plane = data.get("plane")
    if plane not in SIEGE_PLANES:
        return False
    try:
        states = _opening_states()
        return bool(siege_map().walkable(plane, int(x), int(y), states))
    except Exception:
        log.exception("kcs walkability check failed")
        return False


def attach(session, decision: Decision, resume: Optional[dict] = None) -> None:
    """Place a player the guard has already allowed. Does not re-decide.

    Raises on failure and leaves ``session.dungeon`` unset.
    """
    if not decision.allowed or decision.mode not in ("combatant", "spectator"):
        raise RuntimeError("refusing to attach without an allow decision")
    resume = resume or {}
    plane = resume.get("plane") or PLANE_BATTLEFIELD
    if plane not in SIEGE_PLANES:
        raise RuntimeError("refusing to attach to a non-siege plane")
    smap = siege_map()
    pdata = smap.plane(plane)
    states = _opening_states()
    x, y = _stand_tile(session, pdata, plane, states, resume)
    ret_x = resume.get("return_x")
    ret_y = resume.get("return_y")
    if ret_x is None or ret_y is None:
        ret_x, ret_y = int(session.x), int(session.y)
    dungeon = {
        "id": DUNGEON_ID,
        "plane": plane,
        "mode": decision.mode,
        "floor": 0,
        "floors": 1,
        "label": "King's Castle Siege",
        "name": pdata.plane_id,
        "tiles": [],
        "width": pdata.width,
        "height": pdata.height,
        "monsters": {},
        "transitions": {},
        "return_x": int(ret_x),
        "return_y": int(ret_y),
        "explore": False,
        "realm": False,
        "kcs": True,
        "schema_version": smap.schema_version,
        "content_sha256": smap.content_sha256,
    }
    session.dungeon = dungeon
    session._dungeon_return = (int(ret_x), int(ret_y))
    session.x, session.y = int(x), int(y)
    session.in_combat_with = None
    session.gathering_node = None
    session.pet_target_id = None
    if getattr(session, "pet_id", None):
        session.pet_x, session.pet_y = session.x, session.y


def retarget(session, plane_id: str, mode: str) -> None:
    """Move an already-attached player to the other siege plane."""
    if not on_map(session):
        raise RuntimeError("not on the siege map")
    if plane_id not in SIEGE_PLANES:
        raise RuntimeError("not a siege plane")
    if mode not in ("combatant", "spectator"):
        raise RuntimeError("bad siege mode")
    smap = siege_map()
    pdata = smap.plane(plane_id)
    states = _opening_states()
    x, y = _stand_tile(session, pdata, plane_id, states, {})
    session.dungeon["plane"] = plane_id
    session.dungeon["mode"] = mode
    session.dungeon["width"] = pdata.width
    session.dungeon["height"] = pdata.height
    session.dungeon["name"] = pdata.plane_id
    session.x, session.y = int(x), int(y)
    if getattr(session, "pet_id", None):
        session.pet_x, session.pet_y = session.x, session.y


def leave(session) -> None:
    """Drop siege presence and stand the player on their overworld return tile."""
    data = getattr(session, "dungeon", None) or {}
    if data.get("id") != DUNGEON_ID:
        raise ValueError("session is not in King's Castle Siege")
    rx, ry = _return_tile(session)
    force_clear(session, rx, ry)


def force_clear(session, x=None, y=None) -> None:
    """Remove siege presence even if ``leave`` cannot."""
    if x is None or y is None:
        try:
            x, y = _return_tile(session)
        except Exception:
            x, y = int(getattr(session, "x", 0)), int(getattr(session, "y", 0))
    session.dungeon = None
    session.in_combat_with = None
    session.pet_target_id = None
    session.gathering_node = None
    session.x, session.y = int(x), int(y)
    if getattr(session, "pet_id", None):
        session.pet_x, session.pet_y = int(x), int(y)


def payload(session, resume: bool = False) -> dict:
    data = getattr(session, "dungeon", None) or {}
    body = {
        "id": DUNGEON_ID,
        "plane": data.get("plane"),
        "mode": data.get("mode"),
        "floor": 0,
        "floors": 1,
        "label": "King's Castle Siege",
        "name": "King's Castle Siege",
        "width": data.get("width"),
        "height": data.get("height"),
        "x": int(session.x),
        "y": int(session.y),
        "kcs": True,
        "schema_version": data.get("schema_version"),
        "content_sha256": data.get("content_sha256"),
    }
    if resume:
        body["resume"] = True
    return body


def resume_blob(session) -> Optional[dict]:
    data = getattr(session, "dungeon", None) or {}
    if data.get("id") != DUNGEON_ID:
        return None
    return {
        "id": DUNGEON_ID,
        "plane": data.get("plane") or PLANE_BATTLEFIELD,
        "mode": data.get("mode") or "combatant",
        "x": int(session.x),
        "y": int(session.y),
        "return_x": data.get("return_x"),
        "return_y": data.get("return_y"),
    }


def _return_tile(session):
    data = getattr(session, "dungeon", None) or {}
    saved = getattr(session, "_dungeon_return", None)
    if saved and saved[0] is not None and saved[1] is not None:
        return int(saved[0]), int(saved[1])
    rx, ry = data.get("return_x"), data.get("return_y")
    if rx is None or ry is None:
        return int(session.x), int(session.y)
    return int(rx), int(ry)


def _stand_tile(session, pdata, plane, states, resume):
    candidates = []
    if resume.get("x") is not None and resume.get("y") is not None:
        candidates.append((int(resume["x"]), int(resume["y"])))
    side = _side(session)
    spawns = pdata.spawn
    if side == "defend":
        order = ("defender", "courtyard", "entrance", "dais", "attacker")
    else:
        order = ("attacker", "attacker_south", "entrance", "main_gate_south", "defender")
    for name in order:
        if name in spawns:
            candidates.append(tuple(spawns[name]))
    candidates.extend(spawns.values())
    smap = siege_map()
    for x, y in candidates:
        if smap.walkable(plane, int(x), int(y), states):
            return int(x), int(y)
    raise RuntimeError("no walkable siege tile")


def _side(session) -> Optional[str]:
    try:
        war = _require_guard().store.open_war()
        if war is None:
            return None
        return _require_guard().store.roster_status(war.war_id, int(session.player_id)).side
    except Exception:
        log.exception("kcs side lookup failed")
        return None


def _eliminated_in_store(player_id: int) -> bool:
    try:
        war = _require_guard().store.open_war()
        if war is None:
            return False
        return bool(_require_guard().store.roster_status(war.war_id, int(player_id)).eliminated)
    except Exception:
        log.exception("kcs elimination read failed")
        return False


def _opening_states():
    try:
        war = _require_guard().store.open_war()
        if war is None:
            return None
        return _require_guard().store.openings(war.war_id)
    except Exception:
        log.exception("kcs opening read failed")
        return None


def _default_path() -> str:
    env = os.environ.get("KCS_DB_PATH")
    if env:
        return env
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), "kcs_siege.db")


def _reject_live_db(path: str) -> None:
    if not isinstance(path, str) or not path:
        raise TypeError("KCS store path must be a database path string")
    if path == ":memory:" or path.startswith("file::memory:"):
        return
    absolute = os.path.abspath(path)
    base = os.path.basename(absolute)
    if base == "world.db" or base.startswith("world.db"):
        raise RuntimeError("KCS store cannot use world.db")
    live = getattr(database, "DB_PATH", None)
    if isinstance(live, str) and live not in (":memory:",) and not str(live).startswith("file:"):
        try:
            if os.path.abspath(live) == absolute:
                raise RuntimeError("KCS store cannot use the live world database")
        except OSError:
            pass


def _resolve_path() -> str:
    path = _configured_path or _default_path()
    _reject_live_db(path)
    return path


def _journal_for(path: str) -> Optional[str]:
    if _configured_journal:
        return _configured_journal
    if path == ":memory:" or path.startswith("file::memory:"):
        return None
    return path + ".pending.jsonl"


def _require_guard() -> EntryGuard:
    global _store, _guard
    with _lock:
        if _guard is not None:
            return _guard
        path = _resolve_path()
        faults = _configured_faults or FaultPlan()
        store = KCSStore(path, faults=faults)
        guard = EntryGuard(store, journal_path=_journal_for(path), enabled=enabled)
        _store = store
        _guard = guard
        return guard


def _close_locked() -> None:
    global _store, _guard
    store = _store
    _store = None
    _guard = None
    if store is not None:
        try:
            store.close()
        except Exception:
            log.exception("kcs store close failed")
