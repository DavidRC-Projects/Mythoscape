"""Crownfall phase 9 runtime: raid monsters, protesters, town criers, court-event expiry.

Everything spawned here is tagged (raid ids in _RAID_MONSTERS, protester NPC ids start with
"protester_") and is rebuilt from the raids table and the mood band after a restart.
"""
import logging
import random
import time

import politics

log = logging.getLogger("politics_live")

_RAID_MONSTERS = {}      # raid id -> [monster ids]
_LAST_CRY = {}           # crier id -> unix time
_CRIER_STARTED = None


def _srv():
    import server
    return server


def _online_near(s, x, y, rng):
    for sess in list(s.WORLD.sessions.values()):
        if sess.dungeon:
            continue
        if max(abs(sess.x - x), abs(sess.y - y)) <= rng:
            yield sess


def _free_tiles(s, cx, cy, n):
    import world_map
    taken = {(m.x, m.y) for m in s.WORLD.monsters.values() if m.alive}
    taken |= {(npc["x"], npc["y"]) for npc in s.NPCS if not npc.get("plane")}
    out = []
    for r in range(0, 5):
        for x in range(cx - r, cx + r + 1):
            for y in range(cy - r, cy + r + 1):
                if max(abs(x - cx), abs(y - cy)) != r or (x, y) in taken:
                    continue
                try:
                    if world_map.is_walkable(s.WORLD.grid, x, y):
                        out.append((x, y))
                except Exception:
                    continue
                if len(out) >= n:
                    return out
    return out


def spawn_raid(raid_id, point):
    """Spawn (or respawn after a restart) one raid's monsters. Never duplicates."""
    s = _srv()
    if _RAID_MONSTERS.get(raid_id):
        return _RAID_MONSTERS[raid_id]
    cx, cy = politics.RAID_POINTS.get(point, next(iter(politics.RAID_POINTS.values())))
    n = politics.raid_size(raid_id)
    ids = []
    for i, (x, y) in enumerate(_free_tiles(s, cx, cy, n)):
        mtype = politics.RAID_TYPES[i % len(politics.RAID_TYPES)]
        mid = s.next_id()
        m = s.MonsterInstance(mid, mtype, x, y, no_respawn=True)
        m.raid_id = raid_id
        s.WORLD.monsters[mid] = m
        ids.append(mid)
    _RAID_MONSTERS[raid_id] = ids
    return ids


def despawn_raid(raid_id):
    s = _srv()
    for mid in _RAID_MONSTERS.pop(raid_id, []):
        s.WORLD.monsters.pop(mid, None)


def _credit_kill(s, conn, m, now):
    pid = getattr(m, "killer_id", None)
    if pid is None:
        return
    import reputation
    got = reputation.daily_take(conn, pid, "raid_rep", politics.RAID_REP, politics.RAID_REP_DAILY_MAX, now)
    if got:
        conn.execute("UPDATE players SET reputation = MAX(-1000, MIN(1000, COALESCE(reputation, 0) + ?)) "
                     "WHERE id = ?", (got, pid))
        conn.commit()
        sess = s.WORLD.sessions.get(pid)
        if sess:
            sess.reputation = min(1000, int(getattr(sess, "reputation", 0) or 0) + got)


async def tick_raids(now=None):
    s = _srv()
    conn = s.WORLD.db.conn
    now = time.time() if now is None else now
    for rid, point, started, ends, status in politics.open_raids(conn):
        if status == "pending" and now >= float(started):
            conn.execute("UPDATE raids SET status = 'active' WHERE id = ?", (rid,))
            conn.commit()
            status = "active"
            spawn_raid(rid, point)
            await s.broadcast("CHAT_MSG", **{"from": "Town Crier", "text":
                              f"Bandits raid the {point.replace('_', ' ')}! Drive them off for the Crown."})
            politics.news(conn, "raid", f"Bandits raid the {point.replace('_', ' ')}.", now)
        if status != "active":
            continue
        if now >= float(ends):
            despawn_raid(rid)
            conn.execute("UPDATE raids SET status = 'done' WHERE id = ?", (rid,))
            conn.commit()
            continue
        if rid not in _RAID_MONSTERS:      # restart: rebuild from the table
            spawn_raid(rid, point)
        alive = []
        for mid in _RAID_MONSTERS.get(rid, []):
            m = s.WORLD.monsters.get(mid)
            if m is None:
                continue
            if not m.alive:
                _credit_kill(s, conn, m, now)
                s.WORLD.monsters.pop(mid, None)
                continue
            alive.append(mid)
        _RAID_MONSTERS[rid] = alive
        if not alive:
            _RAID_MONSTERS.pop(rid, None)
            conn.execute("UPDATE raids SET status = 'cleared' WHERE id = ?", (rid,))
            conn.commit()
            politics.news(conn, "raid", f"The {point.replace('_', ' ')} raiders are driven off.", now)


def _protester_npcs(conn):
    cause = politics.protest_cause(conn)
    return [{"id": f"protester_{i}", "name": politics.PROTESTER_NAMES[i], "x": x, "y": y,
             "protester": True, "lines": [cause, "(Their placard reads: DOWN WITH THE CROWN'S GREED)"]}
            for i, (x, y) in enumerate(politics.PROTESTER_SPOTS)]


async def sync_protesters():
    s = _srv()
    conn = s.WORLD.db.conn
    want = politics.wants_protesters(conn)
    have = any(str(n.get("id", "")).startswith("protester_") for n in s.NPCS)
    if want == have:
        if want:   # keep the placard cause current
            cause = politics.protest_cause(conn)
            for n in s.NPCS:
                if str(n.get("id", "")).startswith("protester_"):
                    n["lines"][0] = cause
        return False
    s.NPCS[:] = [n for n in s.NPCS if not str(n.get("id", "")).startswith("protester_")]
    for k in [k for k in s.NPC_BY_ID if str(k).startswith("protester_")]:
        s.NPC_BY_ID.pop(k, None)
    if want:
        for n in _protester_npcs(conn):
            s.NPCS.append(n)
            s.NPC_BY_ID[n["id"]] = n
    await s.broadcast("NPCS_SYNC", npcs=[n for n in s.NPCS if not n.get("plane")])
    return True


async def tick_criers(now=None):
    global _CRIER_STARTED
    s = _srv()
    now = time.time() if now is None else now
    if _CRIER_STARTED is None:
        _CRIER_STARTED = now
    lines = politics.latest_news(s.WORLD.db.conn, 1)
    if not lines:
        return
    text = "Hear ye! " + lines[0].split("] ", 1)[-1]
    for c in politics.CRIERS:
        if now - _LAST_CRY.get(c["id"], _CRIER_STARTED - politics.CRIER_EVERY + 60) < politics.CRIER_EVERY:
            continue
        _LAST_CRY[c["id"]] = now
        for sess in _online_near(s, c["x"], c["y"], politics.CRIER_RANGE):
            await s.send(sess.ws, "CHAT_MSG", **{"from": c["name"], "text": text})


async def tick(now=None):
    """Every 10 ticks from the game loop."""
    s = _srv()
    conn = s.WORLD.db.conn
    now = time.time() if now is None else now
    try:
        await tick_raids(now)
        await sync_protesters()
        await tick_criers(now)
        out = politics.tick_events(conn, now, s.MONSTERS)
        if out:
            await s.broadcast("CHAT_MSG", **{"from": "Royal Herald", "text": "Court: " + out[1]})
    except Exception:
        log.exception("politics tick failed")
