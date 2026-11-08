"""M30 server-foundation tests: export, walkability, storage, guard, spatial.

Synthetic data and temp/in-memory SQLite only. No live game imports.
"""
from __future__ import annotations

import ast
import hashlib
import json
import os
import random
import sqlite3
import subprocess
import sys
import tempfile
import threading
from pathlib import Path

# Foundations live next to the game server. The standalone
# kings_castle_siege_map package is not part of this repository; layout
# parity checks skip when it cannot be imported.
ROOT = Path(__file__).resolve().parents[1] / "server"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from kcs_server import export_schema as E  # noqa: E402
from kcs_server import flags  # noqa: E402
from kcs_server.guard import EntryGuard, PLANE_BATTLEFIELD, PLANE_THRONE  # noqa: E402
from kcs_server.plane import BadOpeningState, SiegeMap, UnknownOpening  # noqa: E402
from kcs_server.spatial import GridIndex, all_pairs_nearby, nearby_for_all  # noqa: E402
from kcs_server.store import (  # noqa: E402
    FaultPlan, InjectedFault, InvalidTransition, KCSStore, ResultConflict, StoreBusy, StoreError,
)

CHECKS = 0
SKIPPED = []


def layout_module():
    try:
        from kings_castle_siege_map import layout as layout_mod
    except ImportError:
        return None
    return layout_mod


def skip(name, why):
    SKIPPED.append((name, why))
    print(f"SKIP {name}: {why}")


def check(ok, msg):
    global CHECKS
    CHECKS += 1
    if not ok:
        raise AssertionError(msg)


def expect(exc, fn, *a, **kw):
    try:
        fn(*a, **kw)
    except exc as e:
        return e
    raise AssertionError(f"expected {exc.__name__} from {getattr(fn, '__name__', fn)}")


ON = lambda: True  # noqa: E731
OFF = lambda: False  # noqa: E731
_MAP = None
_BF = None


def smap():
    global _MAP
    if _MAP is None:
        _MAP = SiegeMap.load()
    return _MAP


def bf():
    global _BF
    layout = layout_module()
    if layout is None:
        raise RuntimeError("kings_castle_siege_map is not in this repository")
    if _BF is None:
        _BF = layout.build_battlefield()
    return _BF


def live_war(store, key="w"):
    w = store.create_war(key)
    store.enlist(w.war_id, 1, "attack")
    store.enlist(w.war_id, 2, "defend")
    store.set_war_status(w.war_id, "locking")
    store.set_war_status(w.war_id, "active")
    return w


# ---------------------------------------------------------------- export / map
def test_export_frozen_matches_layout():
    doc = E.load_export()
    check(doc["content_sha256"].startswith("6dbbdfa8"), "frozen export keeps the M30 content hash")
    check(doc["body"]["schema_version"] == 1 and doc["body"]["map_id"] == "kings_castle_siege", "schema id/version")
    layout = layout_module()
    if layout is None:
        skip("test_export_frozen_matches_layout layout parity",
             "kings_castle_siege_map is not in this repository; frozen export was loaded and hashed")
    else:
        fresh = E.build_export()
        check(doc["content_sha256"] == fresh["content_sha256"],
              "frozen export drifted from layout.py: regenerate deliberately with tools/m30_export_map.py")
    body = doc["body"]
    check(body["map_id"] not in body["forbidden_ids"], "map id isolated from live ids")
    bp = body["planes"][0]
    check(bp["width"] == 280 and bp["height"] == 280, "280x280 battlefield")
    ids = [o["id"] for o in bp["openings"]]
    check(len(ids) == 11 and "main_gate" in ids and "keep_doors" in ids, "11 battlefield openings")
    check(sum("breach" in i for i in ids) == 6 and sum(i.endswith("_gate") for i in ids) == 4, "4 gates + 6 breaches")


def test_export_tamper_rejected():
    doc = json.loads(E.FROZEN_PATH.read_text())
    with tempfile.TemporaryDirectory() as td:
        p = Path(td) / "x.json"
        bad = json.loads(json.dumps(doc))
        row = list(bad["body"]["planes"][0]["rows"][100]); row[100] = "." if row[100] != "." else "#"
        bad["body"]["planes"][0]["rows"][100] = "".join(row)
        p.write_text(json.dumps(bad))
        expect(E.ExportError, E.load_export, p)
        bad2 = json.loads(json.dumps(doc)); bad2["body"]["schema_version"] = 2
        bad2["content_sha256"] = E.content_hash(bad2["body"])
        p.write_text(json.dumps(bad2))
        expect(E.ExportError, E.load_export, p)
        bad3 = json.loads(json.dumps(doc)); bad3["body"]["map_id"] = "castle_realm"
        bad3["content_sha256"] = E.content_hash(bad3["body"])
        p.write_text(json.dumps(bad3))
        expect(E.ExportError, E.load_export, p)
        bad4 = json.loads(json.dumps(doc))
        ops = bad4["body"]["planes"][0]["openings"]
        ops[1]["rect"] = list(ops[0]["rect"])  # north_gate now overlaps main_gate
        bad4["content_sha256"] = E.content_hash(bad4["body"])
        expect(E.ExportError, SiegeMap, bad4)
    check(True, "tamper, version, namespace and overlapping openings rejected")


def test_walkability_parity_full_grid():
    if layout_module() is None:
        skip("test_walkability_parity_full_grid",
             "kings_castle_siege_map is not in this repository")
        return
    L = layout_module()
    m, b = smap(), bf()
    plane = b.plane
    ids = list(plane.openings)
    configs = [
        {k: "intact" for k in ids},
        {k: "damaged" for k in ids},
        {k: "destroyed" for k in ids},
    ]
    for cfg in configs:
        bad = 0
        for y in range(-1, plane.height + 1):
            for x in range(-1, plane.width + 1):
                if m.walkable(PLANE_BATTLEFIELD, x, y, cfg) != L.walkable(plane, x, y, cfg):
                    bad += 1
        check(bad == 0, f"full-grid parity {set(cfg.values())}: {bad} mismatches")
    t = b.throne
    for st in ("intact", "destroyed"):
        cfg = {"throne_doors": st}
        bad = sum(m.walkable(PLANE_THRONE, x, y, cfg) != L.walkable(t, x, y, cfg)
                  for y in range(t.height) for x in range(t.width))
        check(bad == 0, f"throne parity {st}")
    # default states (None) parity
    bad = sum(m.walkable(PLANE_BATTLEFIELD, x, y) != L.walkable(plane, x, y)
              for y in range(0, plane.height, 3) for x in range(plane.width))
    check(bad == 0, "default-state parity")


def test_independent_openings():
    m = smap()
    gate_tiles = sorted(m.plane(PLANE_BATTLEFIELD).opening_at)
    ids = m.plane(PLANE_BATTLEFIELD).opening_ids
    intact = {k: "intact" for k in ids}
    for oid in ids:
        st = m.new_states(PLANE_BATTLEFIELD)
        changed = st.set(oid, "destroyed")
        cfg = st.as_dict()
        flipped = [t for t in gate_tiles
                   if m.walkable(PLANE_BATTLEFIELD, *t, cfg) != m.walkable(PLANE_BATTLEFIELD, *t, intact)]
        check(sorted(flipped) == changed and changed, f"{oid}: only its own tiles open ({len(changed)})")
        check(st.set(oid, "damaged") == changed, f"{oid}: damaged re-blocks same tiles")
        check(st.set(oid, "intact") == [], f"{oid}: intact after damaged changes nothing")
    st = m.new_states(PLANE_BATTLEFIELD)
    expect(UnknownOpening, st.set, "king", "destroyed")
    expect(BadOpeningState, st.set, "main_gate", "rubble")
    expect(KeyError, m.walkable, "castle_realm", 1, 1)
    if layout_module() is None:
        skip("test_independent_openings layout parity",
             "kings_castle_siege_map is not in this repository")
        return
    L = layout_module()
    b = bf()
    plane = b.plane
    gate_tiles = sorted(m.plane(PLANE_BATTLEFIELD).opening_at)
    intact = {k: "intact" for k in plane.openings}
    for oid in plane.openings:
        st = m.new_states(PLANE_BATTLEFIELD)
        changed = st.set(oid, "destroyed")
        cfg = st.as_dict()
        flipped = [t for t in gate_tiles if m.walkable(PLANE_BATTLEFIELD, *t, cfg) != m.walkable(PLANE_BATTLEFIELD, *t, intact)]
        check(sorted(flipped) == changed and changed, f"{oid}: only its own tiles open ({len(changed)})")
        check(all(L.walkable(plane, *t, cfg) == m.walkable(PLANE_BATTLEFIELD, *t, cfg) for t in gate_tiles), f"{oid} parity")
        check(st.set(oid, "damaged") == changed, f"{oid}: damaged re-blocks same tiles")
        check(st.set(oid, "intact") == [], f"{oid}: intact after damaged changes nothing")
    st = m.new_states(PLANE_BATTLEFIELD)
    expect(UnknownOpening, st.set, "king", "destroyed")
    expect(BadOpeningState, st.set, "main_gate", "rubble")
    expect(KeyError, m.walkable, "castle_realm", 1, 1)


def test_nav_parity_bfs():
    if layout_module() is None:
        skip("test_nav_parity_bfs", "kings_castle_siege_map is not in this repository")
        return
    L = layout_module()
    m, b = smap(), bf()
    start = b.plane.spawn["attacker"]
    for destroyed in ((), ("main_gate",), ("west_wall_breach",), ("north_east_breach", "keep_doors")):
        cfg = {k: ("destroyed" if k in destroyed else "intact") for k in b.plane.openings}
        a = m.reachable(PLANE_BATTLEFIELD, start, cfg)
        r = L.bfs(b.plane, start, cfg)
        check(a == r, f"reachable set parity for {destroyed or 'all intact'} ({len(a)})")
    court = b.plane.spawn["courtyard"]
    intact = {k: "intact" for k in b.plane.openings}
    check(court not in m.reachable(PLANE_BATTLEFIELD, start, intact), "intact perimeter seals courtyard")
    for oid in ("main_gate", "north_gate", "west_gate", "east_gate", "west_wall_breach", "east_wall_breach",
                "north_west_breach", "north_east_breach", "south_west_breach", "south_east_breach"):
        cfg = dict(intact); cfg[oid] = "destroyed"
        check(court in m.reachable(PLANE_BATTLEFIELD, start, cfg), f"{oid} alone opens the courtyard")


def test_renderer_and_nav_sources_unchanged():
    baseline = ROOT / "m30_evidence" / "baseline_sha256.txt"
    if not baseline.is_file():
        skip("test_renderer_and_nav_sources_unchanged",
             "M30 renderer baseline is not in this repository; siege export is the server copy")
        return
    base = {}
    for line in (ROOT / "m30_evidence" / "baseline_sha256.txt").read_text().splitlines():
        h, p = line.split(None, 1)
        base[p.strip()] = h
    for rel in ("kings_castle_siege_map/angled_view.py", "kings_castle_siege_map/layout.py",
                "kings_castle_siege_map/placement.py", "kings_castle_siege_map/walk.py",
                "kings_castle_siege_map/world_view.py", "kings_castle_siege_map/constants.py",
                "tests/test_kings_castle_siege_map.py"):
        h = hashlib.sha256((ROOT / rel).read_bytes()).hexdigest()
        check(h == base[rel], f"{rel} unchanged since M28 baseline")
    check(base["kings_castle_siege_map/angled_view.py"].startswith("20ad8f10"), "M28 angled_view baseline")


# ---------------------------------------------------------------- store
def test_lifecycle_and_single_open_war():
    s = KCSStore(":memory:")
    w = s.create_war("a")
    expect(StoreError, s.create_war, "b")
    expect(InvalidTransition, s.set_war_status, w.war_id, "active")
    expect(InvalidTransition, s.record_result, w.war_id, "attack", 1, 1, {})
    s.set_war_status(w.war_id, "locking"); s.set_war_status(w.war_id, "active")
    expect(InvalidTransition, s.enlist, w.war_id, 5, "attack")
    s.set_war_status(w.war_id, "voided")
    check(s.open_war() is None, "voided war frees the open slot")
    w2 = s.create_war("b")
    check(s.open_war().war_id == w2.war_id, "second war opens")
    expect(StoreError, s.enlist, w2.war_id, 1, "king")
    expect(TypeError, KCSStore, sqlite3.connect(":memory:"))
    check(True, "store refuses caller connections")


def test_result_replay_and_conflict():
    s = KCSStore(":memory:")
    w = live_war(s)
    check(s.record_result(w.war_id, "attack", 10, 1, {"held": 1}) == "recorded", "recorded")
    check(s.record_result(w.war_id, "attack", 10, 1, {"held": 1}) == "duplicate", "identical replay")
    expect(ResultConflict, s.record_result, w.war_id, "defend", 20, 2, {"held": 0})
    expect(ResultConflict, s.record_result, w.war_id, "attack", 10, 1, {"held": 2})
    r = s.result(w.war_id)
    check(r["winner_side"] == "attack" and r["winning_guild_id"] == 10, "original result kept")
    check(s.war(w.war_id).status == "resolved" and s.open_war() is None, "war resolved")
    expect(sqlite3.IntegrityError, s.conn.execute, "UPDATE kcs_result SET winning_guild_id=99 WHERE war_id=?", (w.war_id,))
    expect(sqlite3.IntegrityError, s.conn.execute, "DELETE FROM kcs_result")
    check(s.apply_result(w.war_id) == "applied", "applied")
    for _ in range(3):
        check(s.apply_result(w.war_id) == "already_applied", "re-apply is no-op")
    sov = s.sovereignty()
    check(sov["rev"] == 1 and sov["owner_guild_id"] == 10 and sov["monarch_player_id"] == 1
          and sov["castle_key"] == "kings_castle_siege", "throne + castle owner in one row")
    check(len(s.history()) == 1 and len(s.outbox()) == 1, "one history + one outbox entry")


def _state(s, war_id):
    r = s.result(war_id)
    return (s.war(war_id).status, None if r is None else r["apply_state"], s.sovereignty()["rev"],
            len(s.history()), len(s.outbox()))


def test_record_faults_roll_back_only_own_unit():
    for point in ("record_result.after_insert", "record_result.after_resolve", "record_result.before_commit"):
        f = FaultPlan()
        s = KCSStore(":memory:", faults=f)
        w = live_war(s)
        f.arm(point)
        expect(InjectedFault, s.record_result, w.war_id, "attack", 3, 1, {})
        check(_state(s, w.war_id) == ("active", None, 0, 0, 0), f"{point}: nothing written")
        check(not s.conn.in_transaction, f"{point}: no dangling tx")
        check(s.record_result(w.war_id, "attack", 3, 1, {}) == "recorded", f"{point}: retry records")
    f = FaultPlan(); s = KCSStore(":memory:", faults=f); w = live_war(s)
    f.arm("record_result.after_commit")
    expect(InjectedFault, s.record_result, w.war_id, "attack", 3, 1, {})
    check(_state(s, w.war_id)[:2] == ("resolved", "pending"), "after_commit: committed despite lost ack")
    check(s.record_result(w.war_id, "attack", 3, 1, {}) == "duplicate", "after_commit: retry is duplicate")


def test_apply_faults_atomic_and_retriable():
    for point in ("apply_result.after_sovereignty", "apply_result.after_history",
                  "apply_result.after_outbox", "apply_result.before_commit"):
        f = FaultPlan()
        s = KCSStore(":memory:", faults=f)
        w = live_war(s)
        s.record_result(w.war_id, "attack", 7, 1, {})
        f.arm(point)
        expect(InjectedFault, s.apply_result, w.war_id)
        check(_state(s, w.war_id) == ("resolved", "pending", 0, 0, 0), f"{point}: throne/owner/history/outbox untouched")
        check(s.sovereignty()["owner_guild_id"] is None, f"{point}: owner unchanged")
        check(s.pending_results() == [w.war_id], f"{point}: still pending for retry")
        check(s.apply_result(w.war_id) == "applied", f"{point}: retry applies")
        check(_state(s, w.war_id) == ("resolved", "applied", 1, 1, 1), f"{point}: exactly once")
    f = FaultPlan(); s = KCSStore(":memory:", faults=f); w = live_war(s)
    s.record_result(w.war_id, "attack", 7, 1, {})
    f.arm("apply_result.after_commit")
    expect(InjectedFault, s.apply_result, w.war_id)
    check(s.apply_result(w.war_id) == "already_applied" and _state(s, w.war_id)[2:] == (1, 1, 1),
          "after_commit: retry sees applied, no double crown")


def test_superseded_out_of_order_apply():
    s = KCSStore(":memory:")
    w1 = live_war(s, "w1"); s.record_result(w1.war_id, "attack", 1, 11, {})
    w2 = live_war(s, "w2"); s.record_result(w2.war_id, "defend", 2, 22, {})
    check(s.apply_result(w2.war_id) == "applied", "newer applied first")
    check(s.apply_result(w1.war_id) == "superseded", "older result cannot overwrite")
    check(s.apply_result(w1.war_id) == "superseded", "superseded is stable")
    sov = s.sovereignty()
    check(sov["source_war_id"] == w2.war_id and sov["owner_guild_id"] == 2 and sov["rev"] == 1, "sovereignty from newer war")


def test_concurrent_apply_and_conflicting_record():
    with tempfile.TemporaryDirectory() as td:
        path = os.path.join(td, "kcs.db")
        s = KCSStore(path)
        w = live_war(s)
        s.record_result(w.war_id, "attack", 5, 1, {})
        outcomes, errors = [], []
        barrier = threading.Barrier(8, timeout=30)

        def worker():
            st = KCSStore(path, timeout=10)
            barrier.wait()
            try:
                outcomes.append(st.apply_result(w.war_id))
            except Exception as e:  # pragma: no cover
                errors.append(repr(e))
            finally:
                st.close()

        ts = [threading.Thread(target=worker, daemon=True) for _ in range(8)]
        [t.start() for t in ts]; [t.join(60) for t in ts]
        check(not any(t.is_alive() for t in ts), "apply workers finished (no deadlock)")
        check(not errors, f"no errors: {errors}")
        check(outcomes.count("applied") == 1 and outcomes.count("already_applied") == 7, f"exactly one apply {outcomes}")
        check(s.sovereignty()["rev"] == 1 and len(s.history()) == 1, "one sovereignty rev")

        w2 = live_war(s, "w2")
        res, errs = [], []
        barrier2 = threading.Barrier(6, timeout=30)

        def recorder(i):
            st = KCSStore(path, timeout=10)
            barrier2.wait()
            try:
                res.append((i, st.record_result(w2.war_id, "attack" if i % 2 else "defend", 100 + i, i, {"i": i})))
            except ResultConflict:
                errs.append(i)
            finally:
                st.close()

        ts = [threading.Thread(target=recorder, args=(i,), daemon=True) for i in range(6)]
        [t.start() for t in ts]; [t.join(60) for t in ts]
        check(not any(t.is_alive() for t in ts), "record workers finished (no deadlock)")
        check(len(res) == 1 and len(errs) == 5, f"one conflicting writer wins ({res}, {errs})")
        winner = res[0][0]
        check(s.result(w2.war_id)["winning_guild_id"] == 100 + winner, "stored payload is the winner's")
        s.close()


def test_never_touches_caller_work():
    with tempfile.TemporaryDirectory() as td:
        path = os.path.join(td, "kcs.db")
        s = KCSStore(path, timeout=0.2)
        w = live_war(s)
        caller = sqlite3.connect(path, timeout=0.2)
        caller.execute("CREATE TABLE IF NOT EXISTS caller_work (v INTEGER)")
        caller.commit()
        caller.execute("INSERT INTO caller_work VALUES (1)")  # implicit tx, uncommitted, holds write lock
        check(caller.in_transaction, "caller has pending work")
        expect(StoreBusy, s.eliminate, w.war_id, 1, "death")
        check(not s.conn.in_transaction, "store left no tx open")
        caller.commit()
        check(caller.execute("SELECT COUNT(*) FROM caller_work").fetchone()[0] == 1, "caller work survived store failure")
        check(s.eliminate(w.war_id, 1, "death") is True, "store retry after caller commits")
        # Store fault + rollback while a caller holds an open read/write tx on another DB.
        other = sqlite3.connect(os.path.join(td, "game.db"))
        other.execute("CREATE TABLE t (v)"); other.commit()
        other.execute("INSERT INTO t VALUES (42)")
        f = FaultPlan("apply_result.before_commit")
        s2 = KCSStore(path, faults=f)
        s2.record_result(w.war_id, "attack", 1, 1, {})
        expect(InjectedFault, s2.apply_result, w.war_id)
        check(other.in_transaction, "unrelated caller tx still open after store rollback")
        other.commit()
        check(other.execute("SELECT v FROM t").fetchone()[0] == 42, "unrelated caller work committed intact")
        caller.close(); other.close(); s.close(); s2.close()


def test_elimination_permanent_and_per_war():
    s = KCSStore(":memory:")
    w = live_war(s)
    check(s.eliminate(w.war_id, 1, "death") is True, "first elimination")
    check(s.eliminate(w.war_id, 1, "other") is False, "idempotent")
    row = s.conn.execute("SELECT elim_cause FROM kcs_roster WHERE war_id=? AND player_id=1", (w.war_id,)).fetchone()
    check(row[0] == "death", "first cause kept")
    expect(sqlite3.IntegrityError, s.conn.execute, "UPDATE kcs_roster SET eliminated=0 WHERE player_id=1")
    expect(sqlite3.IntegrityError, s.conn.execute, "DELETE FROM kcs_roster WHERE player_id=1")
    s.enlist  # noqa
    check(s.eliminate(w.war_id, 77, "death") is True, "non-roster death recorded")
    s.record_result(w.war_id, "defend", 2, 2, {})
    w2 = s.create_war("w2")
    s.enlist(w2.war_id, 1, "attack")
    check(not s.roster_status(w2.war_id, 1).eliminated, "elimination is per war")


def test_newer_schema_refused():
    with tempfile.TemporaryDirectory() as td:
        path = os.path.join(td, "kcs.db")
        KCSStore(path).close()
        c = sqlite3.connect(path); c.execute("UPDATE kcs_meta SET value='99' WHERE key='schema_version'"); c.commit(); c.close()
        expect(StoreError, KCSStore, path)
    check(True, "newer schema refused")


_CRASH_CHILD = r'''
import os, sys
sys.path.insert(0, sys.argv[1])
from kcs_server.store import KCSStore, FaultPlan
class Crash(FaultPlan):
    def check(self, point):
        if point == sys.argv[3]:
            os._exit(9)
s = KCSStore(sys.argv[2], faults=Crash())
op = sys.argv[4]
if op == "apply":
    s.apply_result(int(sys.argv[5]))
elif op == "eliminate":
    s.eliminate(int(sys.argv[5]), 1, "death")
elif op == "record":
    s.record_result(int(sys.argv[5]), "attack", 9, 1, {"x": 1})
'''


def test_hard_crash_mid_transaction():
    with tempfile.TemporaryDirectory() as td:
        path = os.path.join(td, "kcs.db")
        child = os.path.join(td, "child.py"); Path(child).write_text(_CRASH_CHILD)
        s = KCSStore(path)
        w = live_war(s)
        s.close()

        def run(point, op):
            r = subprocess.run([sys.executable, child, str(ROOT), path, point, op, str(w.war_id)])
            return r.returncode

        check(run("record_result.after_insert", "record") == 9, "child died mid record")
        s = KCSStore(path)
        check(s.result(w.war_id) is None and s.war(w.war_id).status == "active", "crash mid record: nothing persisted")
        s.close()
        check(run("record_result.after_commit", "record") == 9, "child died after record commit")
        s = KCSStore(path)
        check(s.result(w.war_id)["apply_state"] == "pending", "record survived post-commit crash")
        s.close()
        for point in ("apply_result.after_sovereignty", "apply_result.after_history", "apply_result.after_outbox",
                      "apply_result.before_commit"):
            check(run(point, "apply") == 9, f"child died at {point}")
            s = KCSStore(path)
            check(s.sovereignty()["rev"] == 0 and not s.history() and not s.outbox()
                  and s.result(w.war_id)["apply_state"] == "pending", f"crash at {point}: no partial crown/ownership")
            s.close()
        check(run("apply_result.after_commit", "apply") == 9, "child died after apply commit")
        s = KCSStore(path)
        check(s.sovereignty()["rev"] == 1 and s.apply_result(w.war_id) == "already_applied", "post-commit crash: applied once")
        s.close()


# ---------------------------------------------------------------- guard
def test_flag_default_off():
    check(flags.enabled({}) is False, "flag default off")
    check(flags.enabled({"USE_KINGS_CASTLE_SIEGE": "1"}) is True, "flag on")
    check(flags.enabled({"USE_KINGS_CASTLE_SIEGE": "off"}) is False, "flag off value")
    s = KCSStore(":memory:"); live_war(s)
    g = EntryGuard(s)  # real env flag (unset in tests)
    if not flags.enabled():
        for r in ("deploy", "login", "reconnect", "teleport", "spectate"):
            check(g.may_enter(1, PLANE_BATTLEFIELD, r).code == "feature_disabled", f"flag off denies {r}")
    check(EntryGuard.applies(PLANE_THRONE) and not EntryGuard.applies("castle_realm"), "guard scope")
    check(g.may_enter(1, "castle_realm", "teleport").code == "not_a_siege_plane", "foreign plane not judged")


def test_guard_paths():
    s = KCSStore(":memory:")
    w = live_war(s)
    g = EntryGuard(s, enabled=ON)
    for r in ("teleport", "portal"):
        check(g.may_enter(1, PLANE_BATTLEFIELD, r).code == "teleport_blocked", f"{r} blocked")
    check(g.may_enter(1, PLANE_BATTLEFIELD, "login").code == "not_deployed", "login before deploy denied")
    check(g.may_enter(1, PLANE_BATTLEFIELD, "bogus").code == "unknown_reason", "unknown reason")
    check(g.may_enter(9, PLANE_BATTLEFIELD, "deploy").code == "not_on_roster", "non-roster")
    d = g.may_enter(1, PLANE_BATTLEFIELD, "deploy")
    check(d.allowed and d.mode == "combatant", "deploy")
    for r in ("login", "reconnect"):
        d = g.may_enter(1, PLANE_THRONE, r)
        check(d.allowed and d.code == "restored", f"{r} restores deployed")
    out = g.on_death(1)
    check(out.eliminated and out.persisted and not out.respawn_as_combatant, "death eliminates durably")
    for r in ("deploy", "login", "reconnect", "teleport", "portal"):
        check(g.may_enter(1, PLANE_BATTLEFIELD, r).code == "eliminated", f"eliminated denied via {r}")
    d = g.may_enter(1, PLANE_BATTLEFIELD, "spectate")
    check(d.allowed and d.mode == "spectator", "eliminated may spectate only")
    g2 = EntryGuard(KCSStore(":memory:"), enabled=ON)
    check(g2.may_enter(1, PLANE_BATTLEFIELD, "deploy").code == "no_open_war", "no war")
    s.record_result(w.war_id, "attack", 1, 2, {})
    check(g.may_enter(2, PLANE_BATTLEFIELD, "login").code == "no_open_war", "resolved war closes field")


def test_guard_fail_closed_and_death_errors():
    with tempfile.TemporaryDirectory() as td:
        jpath = os.path.join(td, "pending.jsonl")
        dbp = os.path.join(td, "kcs.db")
        f = FaultPlan()
        s = KCSStore(dbp, faults=f)
        w = live_war(s)
        g = EntryGuard(s, journal_path=jpath, enabled=ON)
        check(g.may_enter(1, PLANE_BATTLEFIELD, "deploy").allowed, "p1 deployed")
        f.arm("eliminate.before_commit")
        out = g.on_death(1)
        check(out.eliminated and not out.persisted and out.journaled, "DB write failed but journaled")
        check(not s.roster_status(w.war_id, 1).eliminated, "DB not yet eliminated")
        for r in ("login", "reconnect", "deploy"):
            check(g.may_enter(1, PLANE_BATTLEFIELD, r).code == "elimination_pending", f"pending blocks {r}")
        # simulated process restart: fresh store + guard rebuilt from the journal
        s.close()
        s2 = KCSStore(dbp)
        g2 = EntryGuard(s2, journal_path=jpath, enabled=ON)
        check(s2.roster_status(w.war_id, 1).eliminated and not g2.pending(), "journal replay persisted after restart")
        check(g2.may_enter(1, PLANE_BATTLEFIELD, "login").code == "eliminated", "restart cannot resurrect")
        check(Path(jpath).read_text() == "", "journal drained")
        # Post-commit fault: guard confirms by read-back.
        f3 = FaultPlan("eliminate.after_commit")
        s3 = KCSStore(dbp, faults=f3)
        g3 = EntryGuard(s3, journal_path=jpath, enabled=ON)
        g3.may_enter(2, PLANE_BATTLEFIELD, "deploy")
        out = g3.on_death(2)
        check(out.persisted and not g3.pending(), "after_commit fault confirmed by read-back")
        # No journal, DB down: in-process deny, later flush persists.
        s4 = KCSStore(":memory:", faults=FaultPlan())
        w4 = live_war(s4)
        g4 = EntryGuard(s4, enabled=ON)
        g4.may_enter(1, PLANE_BATTLEFIELD, "deploy")
        s4._faults.arm("eliminate.after_upsert")
        out = g4.on_death(1)
        check(not out.persisted and not out.journaled and out.eliminated, "no journal + DB failure")
        check(g4.may_enter(1, PLANE_BATTLEFIELD, "reconnect").code == "elimination_pending", "in-process deny")
        check(g4.flush_pending() == 0 and s4.roster_status(w4.war_id, 1).eliminated, "flush persists")
        # Store unreadable at death time.
        s5 = KCSStore(":memory:"); w5 = live_war(s5)
        g5 = EntryGuard(s5, enabled=ON)
        g5.may_enter(2, PLANE_BATTLEFIELD, "deploy")
        real = s5.open_war
        s5.open_war = lambda: (_ for _ in ()).throw(sqlite3.OperationalError("disk I/O error"))
        out = g5.on_death(2)
        check(out.eliminated and not out.persisted, "unknown war: held as pending")
        check(g5.may_enter(2, PLANE_BATTLEFIELD, "login").code == "guard_error", "store down: deny")
        s5.open_war = real
        check(g5.may_enter(2, PLANE_BATTLEFIELD, "login").code == "elimination_pending", "pending until flushed")
        check(g5.flush_pending() == 0 and s5.roster_status(w5.war_id, 2).eliminated, "bound to open war on flush")
        # Internal guard error -> deny.
        s6 = KCSStore(":memory:"); live_war(s6)
        g6 = EntryGuard(s6, enabled=ON)
        s6.roster_status = lambda *a: 1 / 0
        check(g6.may_enter(1, PLANE_BATTLEFIELD, "deploy").code == "guard_error", "exception -> deny")
        # Deploy write failure -> deny and not deployed.
        f7 = FaultPlan("mark_deployed.after_update")
        s7 = KCSStore(":memory:", faults=f7); w7 = live_war(s7)
        g7 = EntryGuard(s7, enabled=ON)
        check(g7.may_enter(1, PLANE_BATTLEFIELD, "deploy").code == "guard_error", "deploy write failure denies")
        check(not s7.roster_status(w7.war_id, 1).deployed, "deploy rolled back")
        check(g7.may_enter(1, PLANE_BATTLEFIELD, "login").code == "not_deployed", "no login restore after failed deploy")


def test_guard_death_entry_race():
    with tempfile.TemporaryDirectory() as td:
        dbp = os.path.join(td, "kcs.db")
        s = KCSStore(dbp, timeout=10)
        live_war(s)
        g = EntryGuard(s, enabled=ON)
        g.may_enter(1, PLANE_BATTLEFIELD, "deploy")
        died = threading.Event()
        late_allows = []

        def enterer():
            gs = EntryGuard(KCSStore(dbp, timeout=10), enabled=ON)
            for _ in range(300):
                after = died.is_set()
                d = gs.may_enter(1, PLANE_BATTLEFIELD, "reconnect")
                if after and d.allowed:
                    late_allows.append(d)

        t = threading.Thread(target=enterer, daemon=True); t.start()
        g.on_death(1); died.set()
        t.join(60)
        check(not t.is_alive(), "race thread finished")
        check(not late_allows, "no combatant entry observed after death completed (separate process-like guard)")


# ---------------------------------------------------------------- spatial
def test_spatial_parity():
    rng = random.Random(30)
    for trial in range(400):
        n = rng.choice([0, 1, 2, 5, 50, 200, 250])
        spread = rng.choice([10, 60, 280])
        players = [(i, rng.randint(-3, spread), rng.randint(-3, spread)) for i in range(n)]
        if n and rng.random() < 0.3:
            players += [(n + k, players[0][1], players[0][2]) for k in range(5)]  # stacked tiles
        radius = rng.choice([0, 1, 5, 24, 36, 300])
        cap = rng.choice([None, 0, 1, 10, 100])
        cell = rng.choice([None, 1, 7, 24, 64])
        ref = nearby_for_all(players, radius, cap, method="all_pairs")
        got = nearby_for_all(players, radius, cap, method="grid", cell=cell)
        check(ref == got, f"spatial parity trial {trial}")
    idx = GridIndex(24).build([(1, 0, 0), (2, 24, 24), (3, 25, 0)])
    check(idx.query((1, 0, 0), 24) == [2] and all_pairs_nearby([(1, 0, 0), (2, 24, 24), (3, 25, 0)], (1, 0, 0), 24) == [2],
          "boundary inclusive/exclusive")
    expect(ValueError, GridIndex, 0)


# ---------------------------------------------------------------- isolation
def test_kcs_server_isolated_from_live_game():
    banned = {"crown_siege", "castle_realm", "server", "throne", "throne_live", "castle_owners", "database",
              "pygame", "numpy", "cv2", "feature_flags"}
    for py in sorted((ROOT / "kcs_server").glob("*.py")):
        tree = ast.parse(py.read_text())
        for node in ast.walk(tree):
            names = []
            if isinstance(node, ast.Import):
                names = [a.name.split(".")[0] for a in node.names]
            elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
                names = [node.module.split(".")[0]]
            for nm in names:
                check(nm not in banned, f"{py.name} imports {nm}")
        check("world.db" not in py.read_text(), f"{py.name} never references world.db")


if __name__ == "__main__":
    tests = [v for k, v in list(globals().items()) if k.startswith("test_") and callable(v)]
    for t in tests:
        t()
        print("ok", t.__name__)
    print(f"kcs_server M30 tests ok ({len(tests)} tests, {CHECKS} checks)")
    if SKIPPED:
        print(f"skipped portions: {len(SKIPPED)}")
        for name, why in SKIPPED:
            print(f"  - {name}: {why}")
