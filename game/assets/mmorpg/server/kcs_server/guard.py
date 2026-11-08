"""Shared, fail-closed entry guard for King's Castle Siege planes (M30).

Every presence-granting path (deploy, teleport, portal, login, reconnect,
spectate) must call ``EntryGuard.may_enter`` and obey the decision. Any error
inside the guard yields a DENY. Not hooked into the live game yet.

Policy encoded here comes from the M29 contract / established requirements,
not from balance numbers:
* combatant presence is granted only by a server deploy, or by restoring an
  already-deployed, living roster member on login/reconnect;
* teleport/portal never grants combatant presence on a siege plane;
* a death on a siege plane eliminates the player for that war before anything
  else, and elimination is never cleared for that war.
"""
from __future__ import annotations

import json
import os
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Dict, Optional, Tuple

from . import flags
from .store import KCSStore

PLANE_BATTLEFIELD = "kings_castle_siege.battlefield"
PLANE_THRONE = "kings_castle_siege.throne_room"
SIEGE_PLANES = frozenset({PLANE_BATTLEFIELD, PLANE_THRONE})
REASONS = frozenset({"deploy", "teleport", "portal", "login", "reconnect", "spectate"})
LIVE_STATUSES = frozenset({"locking", "active"})


@dataclass(frozen=True)
class Decision:
    allowed: bool
    mode: str  # 'combatant' | 'spectator' | 'none'
    code: str


@dataclass(frozen=True)
class DeathOutcome:
    eliminated: bool          # elimination is in force for this process (always True for a siege death)
    persisted: bool           # durable DB write confirmed
    journaled: bool           # durable local journal write confirmed
    respawn_as_combatant: bool  # always False


def _deny(code: str) -> Decision:
    return Decision(False, "none", code)


class PendingJournal:
    """Append-only, fsync'd JSON-lines journal of eliminations not yet in the DB.

    ``append`` returns only after fsync. A process kill before
    ``journal.before_write`` leaves no line. A kill after
    ``journal.after_fsync`` leaves a line the next process replays.
    Power loss before fsync is not covered: the kernel may still drop
    those bytes, and this process cannot observe that.
    """

    def __init__(self, path: Optional[str], fault=None):
        self.path = Path(path) if path else None
        self._fault = fault
        self._lock = threading.Lock()

    def _hit(self, point: str) -> None:
        if self._fault is not None:
            self._fault(point)

    def append(self, war_id: Optional[int], player_id: int, cause: str) -> bool:
        if self.path is None:
            return False
        line = json.dumps({"war_id": war_id, "player_id": player_id, "cause": cause}) + "\n"
        with self._lock:
            self._hit("journal.before_write")
            with open(self.path, "a", encoding="utf-8") as fh:
                fh.write(line)
                fh.flush()
                self._hit("journal.before_fsync")
                os.fsync(fh.fileno())
                self._hit("journal.after_fsync")
        return True

    def read(self) -> Dict[Tuple[int, int], str]:
        out: Dict[Tuple[int, int], str] = {}
        if self.path is None or not self.path.exists():
            return out
        for raw in self.path.read_text(encoding="utf-8").splitlines():
            try:
                rec = json.loads(raw)
                w = rec["war_id"]
                out[(None if w is None else int(w), int(rec["player_id"]))] = str(rec.get("cause", ""))
            except Exception:
                continue  # torn final line after a crash: the in-DB state still governs
        return out

    def rewrite(self, remaining: Dict[Tuple[int, int], str]) -> None:
        if self.path is None:
            return
        with self._lock:
            tmp = self.path.with_suffix(self.path.suffix + ".tmp")
            with open(tmp, "w", encoding="utf-8") as fh:
                for (w, p), cause in remaining.items():
                    fh.write(json.dumps({"war_id": w, "player_id": p, "cause": cause}) + "\n")
                fh.flush()
                os.fsync(fh.fileno())
            os.replace(tmp, self.path)


class EntryGuard:
    def __init__(self, store: KCSStore, *, journal_path: Optional[str] = None,
                 enabled: Optional[Callable[[], bool]] = None):
        self.store = store
        self.journal = PendingJournal(journal_path, fault=getattr(store, "_fault", None))
        self._enabled = enabled or flags.enabled
        self._lock = threading.Lock()
        # Eliminations seen in this process (or the journal) whose DB write is unconfirmed.
        self._pending: Dict[Tuple[int, int], str] = dict(self.journal.read())
        if self._pending:
            self.flush_pending()

    @staticmethod
    def applies(plane_id: str) -> bool:
        """True when a destination plane is governed by this guard."""
        return plane_id in SIEGE_PLANES

    # ---- entry ------------------------------------------------------------
    def may_enter(self, player_id: int, plane_id: str, reason: str) -> Decision:
        try:
            return self._decide(int(player_id), plane_id, reason)
        except Exception:
            return _deny("guard_error")

    def _decide(self, player_id: int, plane_id: str, reason: str) -> Decision:
        if plane_id not in SIEGE_PLANES:
            return _deny("not_a_siege_plane")
        if not self._enabled():
            return _deny("feature_disabled")
        if reason not in REASONS:
            return _deny("unknown_reason")
        war = self.store.open_war()
        if war is None:
            return _deny("no_open_war")
        with self._lock:
            pending = ((war.war_id, player_id) in self._pending
                       or (None, player_id) in self._pending)
        st = self.store.roster_status(war.war_id, player_id)
        if not st.on_roster or st.side is None:
            # Non-roster rows only exist because of an elimination record.
            return _deny("eliminated" if st.eliminated else "not_on_roster")
        if reason == "spectate":
            if war.status in LIVE_STATUSES:
                return Decision(True, "spectator", "spectator_only")
            return _deny("war_not_live")
        if pending:
            return _deny("elimination_pending")
        if st.eliminated:
            return _deny("eliminated")
        if war.status not in LIVE_STATUSES:
            return _deny("war_not_live")
        if reason in ("teleport", "portal"):
            return _deny("teleport_blocked")
        if reason == "deploy":
            if not self.store.mark_deployed(war.war_id, player_id):
                return _deny("deploy_refused")
            return Decision(True, "combatant", "deployed")
        # login / reconnect
        if not st.deployed:
            return _deny("not_deployed")
        return Decision(True, "combatant", "restored")

    # ---- death ------------------------------------------------------------
    def on_death(self, player_id: int, cause: str = "death") -> DeathOutcome:
        """Call on 0 HP on a siege plane BEFORE any respawn/loot/logout/zone change."""
        player_id = int(player_id)
        try:
            war = self.store.open_war()
            war_id = None if war is None else war.war_id
        except Exception:
            # Store unreadable: fail closed. Hold the elimination against
            # whichever war is open when the store is readable again.
            war, war_id = None, None
            unknown = True
        else:
            unknown = False
        if war is None and not unknown:
            # No open war: nothing to eliminate, but never respawn as a siege combatant.
            return DeathOutcome(False, False, False, False)
        key = (war_id, player_id)
        with self._lock:
            self._pending[key] = str(cause)
        journaled = False
        try:
            journaled = self.journal.append(war_id, player_id, str(cause))
        except Exception:
            journaled = False
        persisted = self._persist(key, str(cause))
        return DeathOutcome(True, persisted, journaled, False)

    def _persist(self, key, cause: str) -> bool:
        if key[0] is None:
            try:
                war = self.store.open_war()
            except Exception:
                return False
            if war is None:
                self._drop(key)
                return True
            if not self._persist((war.war_id, key[1]), cause):
                return False
            self._drop(key)
            return True
        try:
            self.store.eliminate(key[0], key[1], cause)
        except Exception:
            # Committed-but-unacknowledged is possible; confirm by reading back.
            try:
                if not self.store.roster_status(*key).eliminated:
                    return False
            except Exception:
                return False
        self._drop(key)
        return True

    def _drop(self, key) -> None:
        with self._lock:
            self._pending.pop(key, None)
            remaining = dict(self._pending)
        try:
            self.journal.rewrite(remaining)
        except Exception:
            pass  # journal replays are idempotent

    def flush_pending(self) -> int:
        """Retry unconfirmed eliminations. Returns how many are still pending."""
        with self._lock:
            items = list(self._pending.items())
        for key, cause in items:
            self._persist(key, cause)
        with self._lock:
            return len(self._pending)

    def pending(self) -> Dict[Tuple[int, int], str]:
        with self._lock:
            return dict(self._pending)

    def death_intent_durable(self, player_id: int) -> bool:
        """True when this death is in the database or in the fsynced journal.

        An in-memory hold alone is not durable. A failed read fails closed
        (treated as durable) so a player is not kept in play when the record
        cannot be checked.
        """
        player_id = int(player_id)
        try:
            war = self.store.open_war()
            if war is not None and self.store.roster_status(war.war_id, player_id).eliminated:
                return True
        except Exception:
            return True
        try:
            recorded = self.journal.read()
        except Exception:
            return True
        return any(pid == player_id for (_war_id, pid) in recorded)
