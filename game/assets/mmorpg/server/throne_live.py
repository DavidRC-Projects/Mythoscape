"""Crownfall phase 7 runtime: scheduler, battles, King NPC state. Wraps throne.py for server.py."""
from __future__ import annotations

import time

import throne

_BATTLES = {}      # challenge id -> battle dict (+ "guards", "captain")
_LOADED = False
_KING_HOME = None


def _srv():
    import server
    return server


def _name(pid):
    s = _srv()
    live = s.WORLD.sessions.get(int(pid)) if pid else None
    if live:
        return live.char_name
    row = s.WORLD.db.conn.execute("SELECT char_name FROM players WHERE id = ?", (pid,)).fetchone()
    return row[0] if row else f"#{pid}"


def _guild_name(cid):
    if not cid:
        return "no guild"
    row = _srv().WORLD.db.conn.execute("SELECT name FROM clans WHERE clan_id = ?", (cid,)).fetchone()
    return row[0] if row else "a guild"


async def _announce(text):
    s = _srv()
    await s.broadcast("CHAT_MSG", **{"from": "Royal Herald", "text": text})


def titles_hook(want):
    s = _srv()
    for sess in list(s.WORLD.sessions.values()):
        sess.royal_title = want.get(int(sess.player_id))


titles_hook.gender_of = lambda pid: getattr(_srv().WORLD.sessions.get(int(pid)), "gender", None)


def apply_king_state():
    """Hide the throne-room King once overthrown; imprisoned puts him in the barracks cell."""
    global _KING_HOME
    s = _srv()
    st = throne.state(s.WORLD.db.conn)
    king = next((n for n in s.NPCS if n.get("id") == "king"), None)
    if king is not None:
        if _KING_HOME is None:
            _KING_HOME = king.get("plane")
        king["plane"] = _KING_HOME if st["old_king_state"] == "reigning" else "hidden"
    s.NPCS[:] = [n for n in s.NPCS if n.get("id") not in ("old_king_prisoner", "old_king_aldous")]
    s.NPC_BY_ID.pop("old_king_prisoner", None)
    s.NPC_BY_ID.pop("old_king_aldous", None)
    if st["old_king_state"] == "freed":
        n = {"id": "old_king_aldous", "name": "Old King Aldous, Royal Advisor", "x": 20, "y": 16,
             "plane": throne.THRONE_PLANE,
             "lines": ["Sit, sit. Let an old man tell you how this kingdom really works."]}
        s.NPCS.append(n)
        s.NPC_BY_ID[n["id"]] = n
    if st["old_king_state"] == "imprisoned":
        n = {"id": "old_king_prisoner", "name": "The Old King", "x": throne.PRISON_SPOT[0],
             "y": throne.PRISON_SPOT[1], "plane": throne.PRISON_PLANE,
             "lines": ["So you sit my throne. Come speak with me again when you've learned what it costs."]}
        s.NPCS.append(n)
        s.NPC_BY_ID[n["id"]] = n


def _plane_of(kind, castle_id):
    return throne.THRONE_PLANE if kind == "crown" else throne.CASTLE_KEEP_PLANE.get(castle_id)


def _in_area(sess, plane, area):
    d = sess.dungeon or {}
    if d.get("id") != "castle_realm" or d.get("plane") != plane:
        return False
    if area is None:
        return True
    x0, y0, x1, y1 = area
    return x0 <= sess.x <= x1 and y0 <= sess.y <= y1


def _spawn_guards(b, plane):
    s = _srv()
    guards = []
    base = dict(s.MONSTERS.get(throne.GUARD_MONSTER) or {})
    spots = list(throne.THRONE_GUARD_SPOTS)
    if b["kind"] != "crown":
        spots = spots[: max(0, throne.CASTLE_GUARDS - 1)]
    for x, y in spots:
        guards.append(s.MonsterInstance(f"battle_{b['id']}_{x}_{y}", throne.GUARD_MONSTER, x, y,
                                        stats=dict(base), no_respawn=True))
    cap_stats = dict(base)
    cap_stats["hp"] = int(base.get("hp", 50)) * throne.CAPTAIN_HP_MULT
    cap_stats["name"] = "Captain of the Royal Guard"
    cx, cy = throne.CAPTAIN_SPOT
    captain = s.MonsterInstance(f"battle_{b['id']}_captain", throne.GUARD_MONSTER, cx, cy,
                                stats=cap_stats, no_respawn=True)
    guards.append(captain)
    b["guards"], b["captain"], b["plane"] = guards, captain, plane


def _sync_guards(b):
    """The same guard objects sit in every session's instance on the battle plane."""
    s = _srv()
    for sess in list(s.WORLD.sessions.values()):
        d = sess.dungeon or {}
        mons = d.get("monsters")
        if mons is None:
            continue
        here = d.get("id") == "castle_realm" and d.get("plane") == b["plane"]
        for g in b["guards"]:
            if here and g.alive:
                mons[g.id] = g
            else:
                mons.pop(g.id, None)


def _despawn(b):
    for g in b.get("guards") or []:
        g.alive = False
    _sync_guards(b)


async def _start(c, now):
    conn = _srv().WORLD.db.conn
    throne.start(conn, c["id"], now)
    b = throne.new_battle(c, now)
    plane = _plane_of(c["kind"], c["castle_id"])
    if plane:
        _spawn_guards(b, plane)
    b.update(challenger_id=c["challenger_id"], clan_id=c["clan_id"], castle_id=c["castle_id"])
    _BATTLES[c["id"]] = b
    where = "the King's Castle" if c["kind"] == "crown" else c["castle_id"]
    await _announce(f"⚔ The battle for {where} begins now! {_name(c['challenger_id'])} of "
                    f"{_guild_name(c['clan_id'])} has {int(throne.window_for(c['kind']) // 60)} minutes.")


def _defender_clan(b):
    import clans
    conn = _srv().WORLD.db.conn
    if b["kind"] == "crown":
        st = throne.state(conn)
        if st["monarch_kind"] == "player":
            return clans.clan_of(st["monarch_player_id"])
        return None
    row = conn.execute("SELECT owner_account_id FROM castle_ownership WHERE castle_id = ?",
                       (b["castle_id"],)).fetchone()
    return clans.clan_of(row[0]) if row else None


async def _step(b, now):
    import clans
    s = _srv()
    conn = s.WORLD.db.conn
    _sync_guards(b)
    area = throne.THRONE_AREA if b["kind"] == "crown" else None
    dclan = _defender_clan(b)
    challengers = defenders = 0
    watchers = []
    for sess in list(s.WORLD.sessions.values()):
        if not _in_area(sess, b["plane"], None):
            continue
        watchers.append(sess)
        cid = clans.clan_of(sess.player_id)
        if cid and cid == b["clan_id"] and _in_area(sess, b["plane"], area):
            challengers += 1
        elif dclan and cid == dclan and sess.hp > 0:
            defenders += 1
    defenders += sum(1 for g in b["guards"] if g.alive)
    result = throne.step_battle(b, now, not b["captain"].alive, challengers, defenders)
    left = max(0, int(b["end"] - now))
    label = "Crown Challenge" if b["kind"] == "crown" else "Castle Challenge"
    hud = (f"{label}: {left // 60:02d}:{left % 60:02d} left · Hold {int(b['hold']) // 60:02d}:"
           f"{int(b['hold']) % 60:02d}/{throne.HOLD_SECONDS // 60:02d}:00")
    for sess in watchers:
        await s.send(sess.ws, "THRONE_HUD", text=hud, ttl=12)
    if not result:
        return
    _despawn(b)
    _BATTLES.pop(b["id"], None)
    row = {"id": b["id"], "challenger_id": b["challenger_id"], "castle_id": b["castle_id"], "kind": b["kind"]}
    who = f"{_name(b['challenger_id'])} of {_guild_name(b['clan_id'])}"
    if b["kind"] == "crown":
        out = throne.resolve_crown(conn, row, result, now)
        if result == "win":
            title = out["titles"].get(int(b["challenger_id"]), "King")
            await _announce(f"👑 {who} has taken the throne! Long live {title} {_name(b['challenger_id'])}.")
        else:
            lost = out.get("castle_lost")
            await _announce(f"The Crown holds. {who} is beaten back"
                            + (f" and loses the deed to {lost}." if lost else "."))
        apply_king_state()
    else:
        throne.resolve_castle(conn, row, result, now, name=_name(b["challenger_id"]))
        await _announce(f"{who} " + (f"has won {b['castle_id']}!" if result == "win"
                                     else f"failed to take {b['castle_id']}."))
        try:
            import castle_owners
            await castle_owners.broadcast()
        except Exception:
            pass
    await _refresh_all()


async def _refresh_all():
    s = _srv()
    for sess in list(s.WORLD.sessions.values()):
        await s.send(sess.ws, "PLAYER_UPDATE", player=sess.full_state())


async def _court_tick(now):
    s = _srv()
    conn = s.WORLD.db.conn
    for sess in list(s.WORLD.sessions.values()):
        if str(getattr(sess, "gender", "")).lower() != "female":
            continue
        if not conn.execute("SELECT 1 FROM court_favour WHERE player_id = ?", (sess.player_id,)).fetchone():
            continue
        lost = throne.standing_penalty(conn, sess, now)
        if lost:
            await s.send(sess.ws, "CHAT_MSG", **{"from": "Mistress of the Robes",
                         "text": f"The court frowns on your standing: {lost} Court Favour."})
        if throne.ball_open(now) and _in_area(sess, throne.THRONE_PLANE, None):
            got = throne.ball_attend(conn, sess.player_id, now)
            if got:
                await s.send(sess.ws, "CHAT_MSG", **{"from": "Mistress of the Robes",
                             "text": f"You are seen at the Court Ball: +{got} Court Favour."})


async def tick(now=None):
    """Called every 10 ticks from the game loop."""
    global _LOADED
    now = time.time() if now is None else now
    s = _srv()
    conn = s.WORLD.db.conn
    if not _LOADED:
        _LOADED = True
        throne.set_titles_hook(titles_hook)
        for cid, b in throne.reload(conn, now).items():
            c = next(x for x in throne.scheduled(conn) if x["id"] == cid)
            plane = _plane_of(c["kind"], c["castle_id"])
            if plane:
                _spawn_guards(b, plane)
            b.update(challenger_id=c["challenger_id"], clan_id=c["clan_id"], castle_id=c["castle_id"])
            _BATTLES[cid] = b
        apply_king_state()
    for c in throne.scheduled(conn):
        if c["status"] != "scheduled":
            continue
        if not c["warned"] and c["scheduled_at"] - now <= throne.WARN_BEFORE and c["kind"] != "acclaim":
            conn.execute("UPDATE challenges SET warned = 1 WHERE id = ?", (c["id"],))
            conn.commit()
            await _announce(f"⚔ One hour until {_name(c['challenger_id'])} of {_guild_name(c['clan_id'])} "
                            f"challenges for {'the Crown' if c['kind'] == 'crown' else c['castle_id']}!")
        if now >= c["scheduled_at"]:
            if c["kind"] == "acclaim":
                out = throne.resolve_acclaim(conn, c, now)
                if out["result"] == "win":
                    await _announce(f"👑 The court acclaims Queen {_name(c['challenger_id'])}! "
                                    "The old King abdicates and leaves Crownfall."
                                    if throne.state(conn)["old_king_state"] == "exiled"
                                    else f"👑 The court acclaims Queen {_name(c['challenger_id'])}!")
                    apply_king_state()
                else:
                    await _announce(f"The court refuses to acclaim {_name(c['challenger_id'])}.")
                await _refresh_all()
            else:
                await _start(c, now)
    for b in list(_BATTLES.values()):
        await _step(b, now)
    await _court_tick(now)
