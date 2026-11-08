"""Process-kill checks for a King's Castle elimination.

A child process blocks at one fault point. The parent SIGKILLs it, then
opens the same temporary database. Nothing here is a thread that already
exited. Temporary files only. No world.db.
"""
from __future__ import annotations

import json
import os
import signal
import subprocess
import sys
import tempfile
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
SERVER = os.path.join(ROOT, "server")

CHECKS = 0


def check(ok, msg):
    global CHECKS
    CHECKS += 1
    if not ok:
        raise AssertionError(msg)
    print("ok ", msg)


def _child():
    cfg = json.loads(open(sys.argv[2], encoding="utf-8").read())
    if SERVER not in sys.path:
        sys.path.insert(0, SERVER)
    from kcs_server.guard import EntryGuard
    from kcs_server.store import KCSStore

    store = KCSStore(cfg["db"])
    target = cfg["point"]
    ready = cfg["ready"]

    def hang(point):
        if point != target:
            return
        with open(ready, "w", encoding="utf-8") as fh:
            fh.write("ready\n")
            fh.flush()
            os.fsync(fh.fileno())
        time.sleep(120)

    store._faults.check = hang
    guard = EntryGuard(store, journal_path=cfg["journal"], enabled=lambda: True)
    war = store.create_war("crash-war")
    store.enlist(war.war_id, 1, "attack")
    store.enlist(war.war_id, 2, "defend")
    store.set_war_status(war.war_id, "locking")
    store.set_war_status(war.war_id, "active")
    with open(cfg["meta"], "w", encoding="utf-8") as fh:
        fh.write(json.dumps({"war_id": war.war_id}))
        fh.flush()
        os.fsync(fh.fileno())
    guard.on_death(1, "death")
    store.close()


def _kill_at(point):
    if SERVER not in sys.path:
        sys.path.insert(0, SERVER)
    from kcs_server.guard import EntryGuard
    from kcs_server.store import KCSStore

    tmp = tempfile.mkdtemp(prefix=f"kcs_crash_{point.replace('.', '_')}_")
    db = os.path.join(tmp, "siege.db")
    journal = db + ".pending.jsonl"
    ready = os.path.join(tmp, "ready")
    meta = os.path.join(tmp, "meta.json")
    err = os.path.join(tmp, "child.err")
    cfg = os.path.join(tmp, "cfg.json")
    with open(cfg, "w", encoding="utf-8") as fh:
        json.dump({
            "db": db, "journal": journal, "ready": ready, "meta": meta, "point": point,
        }, fh)
    with open(err, "w", encoding="utf-8") as err_fh:
        proc = subprocess.Popen(
            [sys.executable, os.path.abspath(__file__), "--child", cfg],
            stderr=err_fh,
            start_new_session=True,
        )
    deadline = time.time() + 20
    while time.time() < deadline and proc.poll() is None and not os.path.exists(ready):
        time.sleep(0.05)
    if not os.path.exists(ready):
        tail = ""
        if os.path.exists(err):
            tail = open(err, encoding="utf-8").read()[-800:]
        raise AssertionError(f"{point}: child never reached the fault (exit {proc.poll()})\n{tail}")
    os.kill(proc.pid, signal.SIGKILL)
    proc.wait(timeout=5)
    check(proc.returncode < 0 or proc.returncode is None or proc.returncode != 0,
          f"{point}: child was killed")
    war_id = json.loads(open(meta, encoding="utf-8").read())["war_id"]
    store = KCSStore(db)
    before = store.roster_status(war_id, 1)
    other = store.roster_status(war_id, 2)
    check(not other.eliminated, f"{point}: the other deployed player is not eliminated")
    if point == "journal.before_write":
        check(not before.eliminated, "kill before the journal write does not eliminate")
        text = open(journal, encoding="utf-8").read() if os.path.exists(journal) else ""
        check('"player_id": 1' not in text, "kill before the journal write leaves no death line")
    elif point == "journal.after_fsync":
        check(not before.eliminated, "kill after fsync and before the database write is not committed yet")
        text = open(journal, encoding="utf-8").read()
        check('"player_id": 1' in text, "kill after fsync keeps the journal line")
    elif point == "eliminate.after_commit":
        check(before.eliminated, "kill after the database commit keeps the elimination")
    else:
        raise AssertionError(point)
    EntryGuard(store, journal_path=journal, enabled=lambda: True)
    after = store.roster_status(war_id, 1)
    other = store.roster_status(war_id, 2)
    if point == "journal.before_write":
        check(not after.eliminated, "restart does not invent an elimination that was never written")
    else:
        check(after.eliminated, f"{point}: restart keeps the dead player eliminated")
    check(not other.eliminated, f"{point}: restart does not eliminate the living player")
    store.close()


def _undurable_death():
    """Both durable writes fail inside the real death handler. No heal, no eject."""
    sys.path.insert(0, SERVER)
    os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
    os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
    import test_kcs_integration as harness
    from kcs_server.store import InjectedFault

    harness.flag(True)
    harness.use_store()
    store, war = harness.open_war()

    def both(point):
        if point in ("journal.before_write", "eliminate.before_commit"):
            raise InjectedFault(point)

    store._faults.check = both
    victim = harness.player()
    bystander = harness.player()
    harness.enlist(store, war, victim, "attack")
    harness.enlist(store, war, bystander, "defend")
    harness.arm_live(store, war)

    async def body():
        await harness.server.handle_enter_dungeon(victim, {"dungeon_id": "kings_castle_siege"})
        check(harness.kcs_siege.on_map(victim), "victim is deployed before the failed death")
        spot = (victim.x, victim.y)
        victim.hp = 0
        victim.coins = 80
        await harness.server.resolve_player_death(victim, [])
        check(victim.hp == 0, "a death with no durable write stays at 0 HP")
        check(victim.hp != victim.max_hp(), "hit points are not restored without a durable write")
        check(victim.coins == 80, "coins are not taken without a durable write")
        check(harness.kcs_siege.on_map(victim), "the player is not ejected without a durable write")
        check(not store.roster_status(war.war_id, victim.player_id).eliminated,
              "the roster is not eliminated when both writes fail")
        check(not store.roster_status(war.war_id, bystander.player_id).eliminated,
              "a living roster member is not eliminated by someone else's failed death")
        stayed = harness.server._apply_kcs_resume(victim, harness.resume_of(victim), "reconnect")
        check(stayed and harness.kcs_siege.on_map(victim),
              "an already-attached player is not cleared while the death is only in memory")
        raw = harness.W.db.get_player_by_id(victim.player_id)["dungeon_resume"]
        check("kings_castle_siege" in (raw or ""), "the siege resume is still saved")
        nx, ny = harness._step_target(victim)
        await harness.server._handle_kcs_move(victim, nx - victim.x, ny - victim.y)
        check(harness.kcs_siege.on_map(victim), "a step does not eject an unrecorded death")
        check((victim.x, victim.y) == spot, "that step does not move them either")

    import asyncio
    asyncio.run(body())


def main():
    if len(sys.argv) >= 3 and sys.argv[1] == "--child":
        _child()
        return
    for point in ("journal.before_write", "journal.after_fsync", "eliminate.after_commit"):
        _kill_at(point)
    _undurable_death()
    print(f"kcs crash tests ok ({CHECKS} checks)")


if __name__ == "__main__":
    main()
