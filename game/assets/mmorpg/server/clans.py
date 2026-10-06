"""One clan per player. Invites last two minutes and are not saved."""
from __future__ import annotations

import re
import time

_NAME = re.compile(r"^[A-Za-z0-9 ]{3,20}$")
_INVITES = {}  # player_id -> (clan_id, inviter_id, expires_at)
_INVITE_SECONDS = 120.0


def ensure_tables(conn):
    conn.execute(
        "CREATE TABLE IF NOT EXISTS clans ("
        "clan_id INTEGER PRIMARY KEY,"
        "name TEXT UNIQUE COLLATE NOCASE,"
        "leader_id INTEGER,"
        "created_at REAL)"
    )
    conn.execute(
        "CREATE TABLE IF NOT EXISTS clan_members ("
        "player_id INTEGER PRIMARY KEY,"
        "clan_id INTEGER,"
        "joined_at REAL)"
    )


def _db():
    from server import WORLD
    return WORLD.db.conn


def clan_of(player_id):
    if not player_id:
        return None
    row = _db().execute(
        "SELECT clan_id FROM clan_members WHERE player_id = ?", (int(player_id),),
    ).fetchone()
    return int(row[0]) if row else None


def member_count(clan_id):
    if not clan_id:
        return 0
    row = _db().execute(
        "SELECT COUNT(*) FROM clan_members WHERE clan_id = ?", (int(clan_id),),
    ).fetchone()
    return int(row[0] if row else 0)


def members(clan_id):
    if not clan_id:
        return []
    rows = _db().execute(
        "SELECT m.player_id, p.char_name, m.joined_at, c.leader_id "
        "FROM clan_members m "
        "JOIN players p ON p.id = m.player_id "
        "JOIN clans c ON c.clan_id = m.clan_id "
        "WHERE m.clan_id = ? ORDER BY m.joined_at, m.player_id",
        (int(clan_id),),
    ).fetchall()
    return [
        {
            "id": int(row[0]),
            "name": row[1],
            "joined_at": row[2],
            "leader": int(row[0]) == int(row[3]),
        }
        for row in rows
    ]


def _clan_row(clan_id):
    return _db().execute(
        "SELECT clan_id, name, leader_id FROM clans WHERE clan_id = ?", (int(clan_id),),
    ).fetchone()


def public(clan_id):
    row = _clan_row(clan_id) if clan_id else None
    people = members(clan_id) if row else []
    leader = next((p["name"] for p in people if p["leader"]), "")
    return {
        "name": row[1] if row else "",
        "leader": leader,
        "members": [p["name"] + (" *" if p["leader"] else "") for p in people],
        "count": len(people),
    }


def _player_named(name):
    return _db().execute(
        "SELECT id, char_name FROM players WHERE char_name = ? COLLATE NOCASE",
        (name.strip(),),
    ).fetchone()


def _clean_invites():
    now = time.time()
    dead = [pid for pid, (_c, _i, exp) in _INVITES.items() if exp <= now]
    for pid in dead:
        _INVITES.pop(pid, None)


async def _push(clan_id):
    from server import WORLD, send
    info = public(clan_id)
    for session in list(WORLD.sessions.values()):
        if clan_of(session.player_id) == int(clan_id):
            await send(session.ws, "CLAN_INFO", **info)


async def _say(session, text):
    from server import send
    await send(session.ws, "CHAT_MSG", **{"from": "Clan", "text": text})


async def on_login(session):
    from server import send
    clan_id = clan_of(session.player_id)
    await send(session.ws, "CLAN_INFO", **public(clan_id))


async def handle_command(session, text):
    _clean_invites()
    parts = text.split()
    cmd = parts[1].lower() if len(parts) > 1 else ""
    rest = text.split(None, 2)
    arg = rest[2].strip() if len(rest) > 2 else ""
    if cmd == "create":
        await create(session, arg)
    elif cmd == "invite":
        await invite(session, arg)
    elif cmd == "accept":
        await accept(session)
    elif cmd == "leave":
        await leave(session)
    elif cmd == "kick":
        await kick(session, arg)
    elif cmd == "list":
        await _list(session)
    else:
        await _say(session, (
            "Clan: /clan create <name> · /clan invite <player> · /clan accept · "
            "/clan leave · /clan kick <player> · /clan list"
        ))


async def create(session, name):
    name = " ".join((name or "").split())
    if not _NAME.match(name):
        await _say(session, "Clan names are 3–20 letters, digits, and spaces.")
        return
    if clan_of(session.player_id):
        await _say(session, "You are already in a clan. /clan leave first.")
        return
    conn = _db()
    now = time.time()
    try:
        cur = conn.execute(
            "INSERT INTO clans (name, leader_id, created_at) VALUES (?, ?, ?)",
            (name, int(session.player_id), now),
        )
        clan_id = int(cur.lastrowid)
        conn.execute(
            "INSERT INTO clan_members (player_id, clan_id, joined_at) VALUES (?, ?, ?)",
            (int(session.player_id), clan_id, now),
        )
        conn.commit()
    except Exception:
        conn.rollback()
        await _say(session, "That clan name is already taken.")
        return
    await _say(session, f"You founded {name}.")
    await _push(clan_id)


async def invite(session, target_name):
    clan_id = clan_of(session.player_id)
    row = _clan_row(clan_id) if clan_id else None
    if not row or int(row[2]) != int(session.player_id):
        await _say(session, "Only the clan leader can invite.")
        return
    if member_count(clan_id) >= 25:
        await _say(session, "The clan is already at 25 members.")
        return
    target = _player_named(target_name)
    if not target:
        await _say(session, f"No one named {target_name} is known here.")
        return
    if clan_of(target[0]):
        await _say(session, f"{target[1]} is already in a clan.")
        return
    _INVITES[int(target[0])] = (int(clan_id), int(session.player_id), time.time() + _INVITE_SECONDS)
    await _say(session, f"Invited {target[1]}. They have two minutes to /clan accept.")
    from server import WORLD, send
    other = WORLD.sessions.get(int(target[0]))
    if other:
        await send(other.ws, "CHAT_MSG", **{
            "from": "Clan",
            "text": f"{session.char_name} invited you to {row[1]}. /clan accept",
        })


async def accept(session):
    _clean_invites()
    pending = _INVITES.get(int(session.player_id))
    if not pending:
        await _say(session, "You have no clan invite.")
        return
    if clan_of(session.player_id):
        _INVITES.pop(int(session.player_id), None)
        await _say(session, "You are already in a clan.")
        return
    clan_id, _inviter, _exp = pending
    if member_count(clan_id) >= 25:
        _INVITES.pop(int(session.player_id), None)
        await _say(session, "That clan is full.")
        return
    conn = _db()
    conn.execute(
        "INSERT OR REPLACE INTO clan_members (player_id, clan_id, joined_at) VALUES (?, ?, ?)",
        (int(session.player_id), int(clan_id), time.time()),
    )
    conn.commit()
    _INVITES.pop(int(session.player_id), None)
    await _say(session, "You joined the clan.")
    await _push(clan_id)


async def leave(session):
    clan_id = clan_of(session.player_id)
    if not clan_id:
        await _say(session, "You are not in a clan.")
        return
    conn = _db()
    row = _clan_row(clan_id)
    conn.execute("DELETE FROM clan_members WHERE player_id = ?", (int(session.player_id),))
    left = members(clan_id)
    if not left:
        conn.execute("DELETE FROM clans WHERE clan_id = ?", (int(clan_id),))
        conn.commit()
        from server import send
        await send(session.ws, "CLAN_INFO", **public(None))
        await _say(session, "You left, and the clan disbanded.")
        return
    if row and int(row[2]) == int(session.player_id):
        nxt = left[0]["id"]
        conn.execute("UPDATE clans SET leader_id = ? WHERE clan_id = ?", (int(nxt), int(clan_id)))
    conn.commit()
    from server import send
    await send(session.ws, "CLAN_INFO", **public(None))
    await _say(session, "You left the clan.")
    await _push(clan_id)


async def kick(session, target_name):
    clan_id = clan_of(session.player_id)
    row = _clan_row(clan_id) if clan_id else None
    if not row or int(row[2]) != int(session.player_id):
        await _say(session, "Only the clan leader can kick.")
        return
    target = _player_named(target_name)
    if not target or clan_of(target[0]) != int(clan_id):
        await _say(session, f"{target_name} is not in your clan.")
        return
    if int(target[0]) == int(session.player_id):
        await _say(session, "Use /clan leave to step down.")
        return
    conn = _db()
    conn.execute("DELETE FROM clan_members WHERE player_id = ?", (int(target[0]),))
    conn.commit()
    await _say(session, f"Kicked {target[1]}.")
    from server import WORLD, send
    other = WORLD.sessions.get(int(target[0]))
    if other:
        await send(other.ws, "CLAN_INFO", **public(None))
        await send(other.ws, "CHAT_MSG", **{"from": "Clan", "text": "You were kicked from the clan."})
    await _push(clan_id)


async def _list(session):
    clan_id = clan_of(session.player_id)
    info = public(clan_id)
    if not info["name"]:
        await _say(session, "You are not in a clan. /clan create <name>")
        return
    names = ", ".join(info["members"])
    await _say(session, f"{info['name']} — leader {info['leader']} — {info['count']}/25 members. {names}")
