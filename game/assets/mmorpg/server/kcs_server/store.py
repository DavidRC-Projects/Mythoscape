"""Isolated SQLite storage for King's Castle Siege (M30).

Guarantees (see M30_SERVER_FOUNDATIONS.md for limits):
* The store owns its own connection. It never accepts a caller's connection,
  so it can never commit or roll back unrelated caller work.
* Every mutation is one ``BEGIN IMMEDIATE`` ... ``COMMIT`` unit. On any
  exception inside the unit, only that unit is rolled back.
* A war result is written once per war (idempotent replay, conflicting replay
  rejected). Applying it updates throne + castle ownership in ONE row
  (``kcs_sovereignty``) plus history and an outbox entry, atomically, at most
  once (compare-and-set on ``apply_state``).
* Elimination is durable and cannot be reversed for that war (DB trigger).
"""
from __future__ import annotations

import hashlib
import json
import re
import sqlite3
import threading
import time
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Any, Dict, Iterable, Iterator, Optional, Sequence, Tuple

SCHEMA_VERSION = 1
CASTLE_KEY = "kings_castle_siege"

WAR_STATUSES = ("registration", "locking", "active", "resolving", "resolved", "voided")
OPEN_STATUSES = ("registration", "locking", "active", "resolving")
# Lifecycle order only. No timers, caps or balance values are defined here.
_TRANSITIONS = {
    "registration": {"locking", "voided"},
    "locking": {"active", "voided"},
    "active": {"resolving", "voided"},
    "resolving": {"resolved", "voided"},
    "resolved": set(),
    "voided": set(),
}
SIDES = ("attack", "defend")
# Assault engines from the approved placement spec. Not a count cap.
ENGINE_TYPES = ("ram", "trebuchet", "siege_tower", "ladder")
# Defender engines are not in that spec, so only the attack side may place these.
PLACEMENT_SIDE = "attack"
_REQUEST_KEY = re.compile(r"^[A-Za-z0-9._:-]{1,64}$")
LIVE_WAR = ("locking", "active")


class StoreError(RuntimeError):
    pass


class StoreBusy(StoreError):
    pass


class InvalidTransition(StoreError):
    pass


class ResultConflict(StoreError):
    pass


class PlacementRejected(StoreError):
    """The engine cannot be stored. Nothing was written."""


class NotFound(StoreError):
    pass


class InjectedFault(RuntimeError):
    """Raised at a named fault point by tests."""


class FaultPlan:
    """One-shot named fault points for tests. Thread-safe."""

    def __init__(self, *points: str):
        self._armed = set(points)
        self._lock = threading.Lock()
        self.hits: list = []

    def arm(self, *points: str) -> None:
        with self._lock:
            self._armed.update(points)

    def check(self, point: str) -> None:
        with self._lock:
            if point in self._armed:
                self._armed.discard(point)
                self.hits.append(point)
                raise InjectedFault(point)


_SCHEMA = """
CREATE TABLE IF NOT EXISTS kcs_meta (key TEXT PRIMARY KEY, value TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS kcs_wars (
    war_id INTEGER PRIMARY KEY AUTOINCREMENT,
    war_key TEXT NOT NULL UNIQUE,
    status TEXT NOT NULL CHECK (status IN ('registration','locking','active','resolving','resolved','voided')),
    open_slot INTEGER UNIQUE CHECK (open_slot IS NULL OR open_slot = 1),
    created_at REAL NOT NULL,
    updated_at REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS kcs_roster (
    war_id INTEGER NOT NULL REFERENCES kcs_wars(war_id),
    player_id INTEGER NOT NULL,
    side TEXT CHECK (side IS NULL OR side IN ('attack','defend')),
    deployed INTEGER NOT NULL DEFAULT 0 CHECK (deployed IN (0,1)),
    eliminated INTEGER NOT NULL DEFAULT 0 CHECK (eliminated IN (0,1)),
    eliminated_at REAL,
    elim_cause TEXT,
    PRIMARY KEY (war_id, player_id)
);
CREATE TRIGGER IF NOT EXISTS kcs_roster_no_revive
BEFORE UPDATE OF eliminated ON kcs_roster
WHEN OLD.eliminated = 1 AND NEW.eliminated = 0
BEGIN SELECT RAISE(ABORT, 'kcs: elimination is permanent for a war'); END;
CREATE TRIGGER IF NOT EXISTS kcs_roster_no_delete_elim
BEFORE DELETE ON kcs_roster WHEN OLD.eliminated = 1
BEGIN SELECT RAISE(ABORT, 'kcs: eliminated roster rows are kept'); END;
CREATE TABLE IF NOT EXISTS kcs_openings (
    war_id INTEGER NOT NULL REFERENCES kcs_wars(war_id),
    opening_id TEXT NOT NULL,
    state TEXT NOT NULL CHECK (state IN ('intact','damaged','destroyed')),
    rev INTEGER NOT NULL DEFAULT 0,
    updated_at REAL NOT NULL,
    PRIMARY KEY (war_id, opening_id)
);
CREATE TABLE IF NOT EXISTS kcs_engines (
    war_id INTEGER NOT NULL REFERENCES kcs_wars(war_id),
    engine_id INTEGER NOT NULL,
    request_key TEXT NOT NULL,
    player_id INTEGER NOT NULL,
    side TEXT NOT NULL CHECK (side IN ('attack','defend')),
    engine_type TEXT NOT NULL,
    x INTEGER NOT NULL,
    y INTEGER NOT NULL,
    rotation INTEGER NOT NULL CHECK (rotation IN (0,90,180,270)),
    tiles_json TEXT NOT NULL,
    pad_json TEXT NOT NULL,
    rev INTEGER NOT NULL,
    created_at REAL NOT NULL,
    PRIMARY KEY (war_id, engine_id),
    UNIQUE (war_id, player_id, request_key)
);
CREATE TABLE IF NOT EXISTS kcs_result (
    war_id INTEGER PRIMARY KEY REFERENCES kcs_wars(war_id),
    winner_side TEXT NOT NULL CHECK (winner_side IN ('attack','defend')),
    winning_guild_id INTEGER,
    monarch_player_id INTEGER,
    proof_json TEXT NOT NULL,
    payload_sha256 TEXT NOT NULL,
    recorded_at REAL NOT NULL,
    apply_state TEXT NOT NULL DEFAULT 'pending' CHECK (apply_state IN ('pending','applied','superseded')),
    applied_at REAL,
    sovereignty_rev INTEGER
);
CREATE TRIGGER IF NOT EXISTS kcs_result_immutable
BEFORE UPDATE OF war_id, winner_side, winning_guild_id, monarch_player_id, proof_json, payload_sha256
ON kcs_result
BEGIN SELECT RAISE(ABORT, 'kcs: results are written once'); END;
CREATE TRIGGER IF NOT EXISTS kcs_result_no_delete
BEFORE DELETE ON kcs_result
BEGIN SELECT RAISE(ABORT, 'kcs: results are never deleted'); END;
CREATE TABLE IF NOT EXISTS kcs_sovereignty (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    castle_key TEXT NOT NULL,
    owner_guild_id INTEGER,
    monarch_player_id INTEGER,
    source_war_id INTEGER REFERENCES kcs_wars(war_id),
    since REAL,
    rev INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS kcs_sovereignty_history (
    rev INTEGER PRIMARY KEY,
    castle_key TEXT NOT NULL,
    owner_guild_id INTEGER,
    monarch_player_id INTEGER,
    source_war_id INTEGER NOT NULL UNIQUE,
    applied_at REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS kcs_outbox (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    sovereignty_rev INTEGER NOT NULL UNIQUE,
    kind TEXT NOT NULL,
    payload_json TEXT NOT NULL,
    created_at REAL NOT NULL,
    delivered_at REAL
);
"""


@dataclass(frozen=True)
class War:
    war_id: int
    war_key: str
    status: str


@dataclass(frozen=True)
class RosterStatus:
    on_roster: bool
    side: Optional[str]
    deployed: bool
    eliminated: bool


@dataclass(frozen=True)
class EngineRecord:
    engine_id: int
    player_id: int
    side: str
    engine_type: str
    x: int
    y: int
    rotation: int
    tiles: Tuple[Tuple[int, int], ...]
    rev: int
    request_key: str


def _payload_hash(winner_side, guild, monarch, proof_json) -> str:
    blob = json.dumps([winner_side, guild, monarch, proof_json], separators=(",", ":"))
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


class KCSStore:
    def __init__(self, path: str, *, timeout: float = 5.0, faults: Optional[FaultPlan] = None,
                 clock=time.time):
        if not isinstance(path, str):
            raise TypeError("KCSStore takes a database path, never a caller connection")
        self.path = path
        self._faults = faults or FaultPlan()
        self._clock = clock
        self._lock = threading.RLock()
        # isolation_level=None: the sqlite3 module never opens implicit
        # transactions; every transaction below is explicit.
        self.conn = sqlite3.connect(path, timeout=timeout, isolation_level=None, check_same_thread=False)
        self.conn.execute("PRAGMA foreign_keys=ON")
        if path != ":memory:" and not path.startswith("file::memory:"):
            self.conn.execute("PRAGMA journal_mode=WAL")
            self.conn.execute("PRAGMA synchronous=FULL")
        self._migrate()

    # ---- infrastructure -------------------------------------------------
    def close(self) -> None:
        self.conn.close()

    def _fault(self, point: str) -> None:
        self._faults.check(point)

    @contextmanager
    def _tx(self, op: str) -> Iterator[sqlite3.Connection]:
        with self._lock:
            if self.conn.in_transaction:
                raise StoreError("kcs store transaction already open (re-entrant use)")
            try:
                self.conn.execute("BEGIN IMMEDIATE")
            except sqlite3.OperationalError as exc:
                raise StoreBusy(f"{op}: {exc}") from exc
            try:
                yield self.conn
                self._fault(f"{op}.before_commit")
                self.conn.execute("COMMIT")
            except BaseException:
                if self.conn.in_transaction:
                    self.conn.execute("ROLLBACK")
                raise
        self._fault(f"{op}.after_commit")

    def _migrate(self) -> None:
        with self._tx("migrate") as c:
            for stmt in _split_sql(_SCHEMA):
                c.execute(stmt)
            row = c.execute("SELECT value FROM kcs_meta WHERE key='schema_version'").fetchone()
            if row is None:
                c.execute("INSERT INTO kcs_meta(key, value) VALUES ('schema_version', ?)", (str(SCHEMA_VERSION),))
            elif int(row[0]) > SCHEMA_VERSION:
                raise StoreError(f"kcs db schema {row[0]} is newer than code {SCHEMA_VERSION}")
            c.execute(
                "INSERT OR IGNORE INTO kcs_sovereignty(id, castle_key, rev) VALUES (1, ?, 0)", (CASTLE_KEY,)
            )

    # ---- wars -------------------------------------------------------------
    def create_war(self, war_key: str) -> War:
        now = self._clock()
        with self._tx("create_war") as c:
            try:
                cur = c.execute(
                    "INSERT INTO kcs_wars(war_key, status, open_slot, created_at, updated_at) "
                    "VALUES (?, 'registration', 1, ?, ?)", (war_key, now, now))
            except sqlite3.IntegrityError as exc:
                raise StoreError(f"cannot open war {war_key!r}: {exc}") from exc
            return War(cur.lastrowid, war_key, "registration")

    def war(self, war_id: int) -> War:
        row = self.conn.execute("SELECT war_id, war_key, status FROM kcs_wars WHERE war_id=?", (war_id,)).fetchone()
        if row is None:
            raise NotFound(f"war {war_id}")
        return War(*row)

    def open_war(self) -> Optional[War]:
        row = self.conn.execute(
            "SELECT war_id, war_key, status FROM kcs_wars WHERE open_slot = 1").fetchone()
        return War(*row) if row else None

    def _transition(self, c, war_id: int, new: str) -> None:
        row = c.execute("SELECT status FROM kcs_wars WHERE war_id=?", (war_id,)).fetchone()
        if row is None:
            raise NotFound(f"war {war_id}")
        if new not in _TRANSITIONS[row[0]]:
            raise InvalidTransition(f"{row[0]} -> {new}")
        slot = 1 if new in OPEN_STATUSES else None
        c.execute("UPDATE kcs_wars SET status=?, open_slot=?, updated_at=? WHERE war_id=?",
                  (new, slot, self._clock(), war_id))

    def set_war_status(self, war_id: int, new: str) -> War:
        with self._tx("set_war_status") as c:
            self._transition(c, war_id, new)
        return self.war(war_id)

    # ---- roster / elimination --------------------------------------------
    def enlist(self, war_id: int, player_id: int, side: str) -> None:
        if side not in SIDES:
            raise StoreError(f"bad side {side!r}")
        with self._tx("enlist") as c:
            st = c.execute("SELECT status FROM kcs_wars WHERE war_id=?", (war_id,)).fetchone()
            if st is None:
                raise NotFound(f"war {war_id}")
            if st[0] not in ("registration", "locking"):
                raise InvalidTransition(f"enlist while {st[0]}")
            c.execute(
                "INSERT INTO kcs_roster(war_id, player_id, side) VALUES (?, ?, ?) "
                "ON CONFLICT(war_id, player_id) DO UPDATE SET side=excluded.side "
                "WHERE kcs_roster.eliminated = 0 AND kcs_roster.deployed = 0",
                (war_id, player_id, side))

    def roster_status(self, war_id: int, player_id: int) -> RosterStatus:
        row = self.conn.execute(
            "SELECT side, deployed, eliminated FROM kcs_roster WHERE war_id=? AND player_id=?",
            (war_id, player_id)).fetchone()
        if row is None:
            return RosterStatus(False, None, False, False)
        return RosterStatus(True, row[0], bool(row[1]), bool(row[2]))

    def mark_deployed(self, war_id: int, player_id: int) -> bool:
        """Set deployed=1 for a living roster member. Returns False if not allowed."""
        with self._tx("mark_deployed") as c:
            cur = c.execute(
                "UPDATE kcs_roster SET deployed=1 WHERE war_id=? AND player_id=? "
                "AND eliminated=0 AND side IS NOT NULL", (war_id, player_id))
            self._fault("mark_deployed.after_update")
            return cur.rowcount == 1

    def eliminate(self, war_id: int, player_id: int, cause: str) -> bool:
        """Durably eliminate. Idempotent; keeps the first time and cause.

        Returns True if this call performed the elimination, False if it was
        already eliminated.
        """
        now = self._clock()
        with self._tx("eliminate") as c:
            if c.execute("SELECT 1 FROM kcs_wars WHERE war_id=?", (war_id,)).fetchone() is None:
                raise NotFound(f"war {war_id}")
            c.execute(
                "INSERT OR IGNORE INTO kcs_roster(war_id, player_id, side) VALUES (?, ?, NULL)",
                (war_id, player_id))
            self._fault("eliminate.after_upsert")
            cur = c.execute(
                "UPDATE kcs_roster SET eliminated=1, eliminated_at=?, elim_cause=? "
                "WHERE war_id=? AND player_id=? AND eliminated=0",
                (now, str(cause), war_id, player_id))
            return cur.rowcount == 1

    # ---- openings ---------------------------------------------------------
    def save_opening(self, war_id: int, opening_id: str, state: str, expected_rev: Optional[int] = None) -> int:
        """Persist one opening's state with optional optimistic concurrency. Returns new rev."""
        now = self._clock()
        with self._tx("save_opening") as c:
            row = c.execute("SELECT rev FROM kcs_openings WHERE war_id=? AND opening_id=?",
                            (war_id, opening_id)).fetchone()
            cur_rev = row[0] if row else 0
            if expected_rev is not None and expected_rev != cur_rev:
                raise ResultConflict(f"opening {opening_id} rev {cur_rev} != expected {expected_rev}")
            c.execute(
                "INSERT INTO kcs_openings(war_id, opening_id, state, rev, updated_at) VALUES (?, ?, ?, ?, ?) "
                "ON CONFLICT(war_id, opening_id) DO UPDATE SET state=excluded.state, rev=excluded.rev, "
                "updated_at=excluded.updated_at", (war_id, opening_id, state, cur_rev + 1, now))
            return cur_rev + 1

    def openings(self, war_id: int) -> Dict[str, str]:
        return dict(self.conn.execute(
            "SELECT opening_id, state FROM kcs_openings WHERE war_id=?", (war_id,)).fetchall())

    def opening_revs(self, war_id: int) -> Dict[str, int]:
        return {row[0]: int(row[1]) for row in self.conn.execute(
            "SELECT opening_id, rev FROM kcs_openings WHERE war_id=?", (war_id,)).fetchall()}

    # ---- engines ----------------------------------------------------------
    def engines(self, war_id: int) -> list:
        rows = self.conn.execute(
            "SELECT engine_id, player_id, side, engine_type, x, y, rotation, tiles_json, rev, request_key "
            "FROM kcs_engines WHERE war_id=? ORDER BY engine_id", (war_id,)).fetchall()
        return [_engine_row(row) for row in rows]

    def place_engine(self, war_id: int, player_id: int, side: str, engine_type: str,
                     x: int, y: int, rotation: int, request_key: str,
                     tiles: Sequence[Sequence[int]], pad: Sequence[Sequence[int]]) -> Tuple[EngineRecord, bool]:
        """Insert one engine, or return the original row when the same request is replayed.

        Overlap is decided inside the transaction. A conflicting replay or a
        rejected placement writes nothing. The caller supplies the footprint;
        this method does not trust a client tile list on its own because only
        the bridge computes tiles from the approved spec.
        """
        if side != PLACEMENT_SIDE:
            raise PlacementRejected("this side cannot place siege engines")
        if engine_type not in ENGINE_TYPES:
            raise PlacementRejected(f"unknown engine type {engine_type!r}")
        if int(rotation) not in (0, 90, 180, 270):
            raise PlacementRejected("rotation must be a quarter turn")
        if not isinstance(request_key, str) or _REQUEST_KEY.fullmatch(request_key) is None:
            raise PlacementRejected("bad request id")
        tiles_t = _norm_tiles(tiles)
        pad_t = _norm_tiles(pad)
        if not set(tiles_t) <= set(pad_t):
            raise PlacementRejected("engine footprint is outside its operating space")
        with self._tx("place_engine") as c:
            war = c.execute("SELECT status FROM kcs_wars WHERE war_id=?", (war_id,)).fetchone()
            if war is None or war[0] not in LIVE_WAR:
                raise PlacementRejected("no live war")
            roster = c.execute(
                "SELECT side, deployed, eliminated FROM kcs_roster WHERE war_id=? AND player_id=?",
                (war_id, int(player_id))).fetchone()
            if roster is None or roster[0] != PLACEMENT_SIDE or not roster[1] or roster[2]:
                raise PlacementRejected("player cannot place an engine")
            existing = c.execute(
                "SELECT engine_id, player_id, side, engine_type, x, y, rotation, tiles_json, rev, request_key "
                "FROM kcs_engines WHERE war_id=? AND player_id=? AND request_key=?",
                (war_id, int(player_id), request_key)).fetchone()
            if existing is not None:
                record = _engine_row(existing)
                if (record.engine_type, record.x, record.y, record.rotation) == (
                        engine_type, int(x), int(y), int(rotation)):
                    return record, True
                raise ResultConflict("request id was already used for a different engine")
            proposed = set(pad_t)
            for row in c.execute("SELECT pad_json FROM kcs_engines WHERE war_id=?", (war_id,)):
                if proposed & set(_norm_tiles(json.loads(row[0]))):
                    raise PlacementRejected("overlaps another engine or its operating space")
            next_id = c.execute(
                "SELECT COALESCE(MAX(engine_id), 0) + 1 FROM kcs_engines WHERE war_id=?",
                (war_id,)).fetchone()[0]
            now = self._clock()
            c.execute(
                "INSERT INTO kcs_engines(war_id, engine_id, request_key, player_id, side, engine_type, "
                "x, y, rotation, tiles_json, pad_json, rev, created_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1, ?)",
                (war_id, int(next_id), request_key, int(player_id), side, engine_type,
                 int(x), int(y), int(rotation),
                 json.dumps(tiles_t, separators=(",", ":")),
                 json.dumps(pad_t, separators=(",", ":")), now))
            return EngineRecord(
                int(next_id), int(player_id), side, engine_type, int(x), int(y), int(rotation),
                tiles_t, 1, request_key), False

    # ---- results + sovereignty -------------------------------------------
    def record_result(self, war_id: int, winner_side: str, winning_guild_id: Optional[int],
                      monarch_player_id: Optional[int], proof: Dict[str, Any]) -> str:
        """Write the authoritative result once and mark the war resolved.

        Returns 'recorded' or 'duplicate' (identical replay). A different
        payload for the same war raises ResultConflict and changes nothing.
        """
        if winner_side not in SIDES:
            raise StoreError(f"bad winner side {winner_side!r}")
        proof_json = json.dumps(proof, sort_keys=True, separators=(",", ":"))
        digest = _payload_hash(winner_side, winning_guild_id, monarch_player_id, proof_json)
        with self._tx("record_result") as c:
            existing = c.execute("SELECT payload_sha256 FROM kcs_result WHERE war_id=?", (war_id,)).fetchone()
            if existing is not None:
                if existing[0] == digest:
                    return "duplicate"
                raise ResultConflict(f"war {war_id} already has a different result")
            st = c.execute("SELECT status FROM kcs_wars WHERE war_id=?", (war_id,)).fetchone()
            if st is None:
                raise NotFound(f"war {war_id}")
            if st[0] == "active":
                self._transition(c, war_id, "resolving")
            elif st[0] != "resolving":
                raise InvalidTransition(f"record result while {st[0]}")
            c.execute(
                "INSERT INTO kcs_result(war_id, winner_side, winning_guild_id, monarch_player_id, "
                "proof_json, payload_sha256, recorded_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (war_id, winner_side, winning_guild_id, monarch_player_id, proof_json, digest, self._clock()))
            self._fault("record_result.after_insert")
            self._transition(c, war_id, "resolved")
            self._fault("record_result.after_resolve")
            return "recorded"

    def apply_result(self, war_id: int) -> str:
        """Project a recorded result onto throne + castle ownership, at most once.

        Returns 'applied', 'already_applied' or 'superseded' (an older war's
        result arriving after a newer one was applied). Retriable after any
        failure: a failed attempt leaves no partial state.
        """
        now = self._clock()
        with self._tx("apply_result") as c:
            row = c.execute(
                "SELECT winning_guild_id, monarch_player_id, apply_state, winner_side "
                "FROM kcs_result WHERE war_id=?", (war_id,)).fetchone()
            if row is None:
                raise NotFound(f"no result for war {war_id}")
            guild, monarch, state, winner_side = row
            if state == "applied":
                return "already_applied"
            if state == "superseded":
                return "superseded"
            sov = c.execute("SELECT source_war_id, rev FROM kcs_sovereignty WHERE id=1").fetchone()
            source_war, rev = sov
            if source_war is not None and war_id <= source_war:
                c.execute("UPDATE kcs_result SET apply_state='superseded', applied_at=? "
                          "WHERE war_id=? AND apply_state='pending'", (now, war_id))
                return "superseded"
            new_rev = rev + 1
            cur = c.execute(
                "UPDATE kcs_sovereignty SET owner_guild_id=?, monarch_player_id=?, source_war_id=?, "
                "since=?, rev=? WHERE id=1 AND rev=?", (guild, monarch, war_id, now, new_rev, rev))
            if cur.rowcount != 1:
                raise ResultConflict("sovereignty changed concurrently")
            self._fault("apply_result.after_sovereignty")
            c.execute(
                "INSERT INTO kcs_sovereignty_history(rev, castle_key, owner_guild_id, monarch_player_id, "
                "source_war_id, applied_at) VALUES (?, ?, ?, ?, ?, ?)",
                (new_rev, CASTLE_KEY, guild, monarch, war_id, now))
            self._fault("apply_result.after_history")
            c.execute(
                "INSERT INTO kcs_outbox(sovereignty_rev, kind, payload_json, created_at) VALUES (?, ?, ?, ?)",
                (new_rev, "sovereignty_changed",
                 json.dumps({"castle_key": CASTLE_KEY, "rev": new_rev, "war_id": war_id,
                             "winner_side": winner_side, "owner_guild_id": guild,
                             "monarch_player_id": monarch}, sort_keys=True), now))
            self._fault("apply_result.after_outbox")
            cas = c.execute(
                "UPDATE kcs_result SET apply_state='applied', applied_at=?, sovereignty_rev=? "
                "WHERE war_id=? AND apply_state='pending'", (now, new_rev, war_id))
            if cas.rowcount != 1:
                raise ResultConflict("result apply CAS lost")
            return "applied"

    def pending_results(self) -> Iterable[int]:
        return [r[0] for r in self.conn.execute(
            "SELECT war_id FROM kcs_result WHERE apply_state='pending' ORDER BY war_id")]

    def sovereignty(self) -> Dict[str, Any]:
        row = self.conn.execute(
            "SELECT castle_key, owner_guild_id, monarch_player_id, source_war_id, since, rev "
            "FROM kcs_sovereignty WHERE id=1").fetchone()
        keys = ("castle_key", "owner_guild_id", "monarch_player_id", "source_war_id", "since", "rev")
        return dict(zip(keys, row))

    def result(self, war_id: int) -> Optional[Dict[str, Any]]:
        cur = self.conn.execute("SELECT * FROM kcs_result WHERE war_id=?", (war_id,))
        row = cur.fetchone()
        if row is None:
            return None
        return dict(zip([d[0] for d in cur.description], row))

    def outbox(self) -> list:
        return self.conn.execute(
            "SELECT sovereignty_rev, kind, payload_json, delivered_at FROM kcs_outbox ORDER BY id").fetchall()

    def history(self) -> list:
        return self.conn.execute(
            "SELECT rev, owner_guild_id, monarch_player_id, source_war_id FROM kcs_sovereignty_history "
            "ORDER BY rev").fetchall()


def _norm_tiles(tiles) -> Tuple[Tuple[int, int], ...]:
    if not isinstance(tiles, (list, tuple)) or not tiles or len(tiles) > 64:
        raise StoreError("bad engine footprint")
    out = []
    for item in tiles:
        if not isinstance(item, (list, tuple)) or len(item) != 2:
            raise StoreError("bad engine footprint")
        try:
            x, y = int(item[0]), int(item[1])
        except (TypeError, ValueError) as exc:
            raise StoreError("bad engine footprint") from exc
        if abs(x) > 10000 or abs(y) > 10000:
            raise StoreError("bad engine footprint")
        out.append((x, y))
    return tuple(sorted(set(out)))


def _engine_row(row) -> EngineRecord:
    tiles = tuple(tuple(pair) for pair in json.loads(row[7]))
    return EngineRecord(
        int(row[0]), int(row[1]), row[2], row[3], int(row[4]), int(row[5]), int(row[6]),
        tiles, int(row[8]), row[9])


def _split_sql(script: str):
    """Split the schema into statements, keeping trigger bodies intact."""
    out, buf = [], []
    for line in script.strip().splitlines():
        buf.append(line)
        joined = "\n".join(buf).strip()
        if joined.endswith(";") and sqlite3.complete_statement(joined):
            out.append(joined)
            buf = []
    if buf and "\n".join(buf).strip():
        out.append("\n".join(buf))
    return out
