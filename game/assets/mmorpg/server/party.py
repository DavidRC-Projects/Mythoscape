"""Minimal player parties — invite nearby, share Endless Depths runs.

Max four. Leader invites; invitee accepts. Used by Endless Depths group entry
and party chat. Not a full social system.
"""
from __future__ import annotations

import time

MAX_SIZE = 4
INVITE_TTL = 45.0
SPEAKER = "Party"

# party_id -> {"leader": pid, "members": [pid, ...], "created": t}
_PARTIES = {}
# invitee_pid -> {"from": pid, "party_id": id, "expires": t}
_INVITES = {}
_next = 1


def _srv():
    import server
    return server


def _new_id():
    global _next
    pid = _next
    _next += 1
    return f"p{pid}"


def _clean():
    now = time.time()
    dead = [k for k, v in _INVITES.items() if float(v.get("expires") or 0) < now]
    for k in dead:
        _INVITES.pop(k, None)


def party_of(player_id):
    """Return party dict or None."""
    for p in _PARTIES.values():
        if int(player_id) in p["members"]:
            return p
    return None


def party_id_of(player_id):
    for pid, p in _PARTIES.items():
        if int(player_id) in p["members"]:
            return pid
    return None


def members(player_id):
    p = party_of(player_id)
    return list(p["members"]) if p else [int(player_id)]


def size(player_id):
    return len(members(player_id))


def is_leader(player_id):
    p = party_of(player_id)
    return bool(p) and int(p["leader"]) == int(player_id)


def public(player_id):
    p = party_of(player_id)
    srv = _srv()
    if not p:
        return {"in_party": False, "members": [], "leader_id": None, "party_id": None}
    rows = []
    for mid in p["members"]:
        s = srv.WORLD.sessions.get(mid)
        rows.append({
            "id": mid,
            "name": (s.char_name if s else f"Player {mid}"),
            "online": bool(s),
            "leader": mid == p["leader"],
        })
    return {
        "in_party": True,
        "party_id": party_id_of(player_id),
        "leader_id": p["leader"],
        "members": rows,
        "size": len(p["members"]),
    }


async def _push(session, text=None):
    srv = _srv()
    payload = public(session.player_id)
    await srv.send(session.ws, "PARTY_UPDATE", **payload)
    if text:
        await srv.send(session.ws, "CHAT_MSG", **{
            "from": SPEAKER, "text": text, "channel": "party",
        })


async def _push_all(member_ids, text=None):
    srv = _srv()
    for mid in member_ids:
        s = srv.WORLD.sessions.get(mid)
        if s:
            await _push(s, text if mid == member_ids[0] else None)
            if text and mid != member_ids[0]:
                await srv.send(s.ws, "CHAT_MSG", **{
                    "from": SPEAKER, "text": text, "channel": "party",
                })


def _attach(session):
    session.party_ids = set(members(session.player_id))
    session.party_id = party_id_of(session.player_id)


async def invite(session, target_id):
    """Leader (or solo player) invites another online player."""
    _clean()
    srv = _srv()
    try:
        tid = int(target_id)
    except (TypeError, ValueError):
        return False, "No such player."
    if tid == session.player_id:
        return False, "You cannot invite yourself."
    target = srv.WORLD.sessions.get(tid)
    if not target:
        return False, "That player is not online."
    if party_of(tid):
        return False, f"{target.char_name} is already in a party."
    mine = party_of(session.player_id)
    if mine and int(mine["leader"]) != session.player_id:
        return False, "Only the party leader can invite."
    if mine and len(mine["members"]) >= MAX_SIZE:
        return False, f"Party is full ({MAX_SIZE})."
    # Must be near each other on the overworld (or both outside dungeons).
    if session.dungeon or target.dungeon:
        return False, "Invite on the overworld, near your ally."
    if abs(session.x - target.x) > 8 or abs(session.y - target.y) > 8:
        return False, "Stand closer to invite them."
    if not mine:
        pid = _new_id()
        _PARTIES[pid] = {
            "leader": session.player_id,
            "members": [session.player_id],
            "created": time.time(),
        }
        _attach(session)
        await _push(session)
    else:
        pid = party_id_of(session.player_id)
    _INVITES[tid] = {
        "from": session.player_id,
        "party_id": pid,
        "expires": time.time() + INVITE_TTL,
        "from_name": session.char_name,
    }
    await srv.send(target.ws, "PARTY_INVITE", **{
        "from_id": session.player_id,
        "from_name": session.char_name,
        "party_id": pid,
        "expires_in": INVITE_TTL,
    })
    await srv.send(session.ws, "CHAT_MSG", **{
        "from": SPEAKER,
        "text": f"Invited {target.char_name} to the party.",
        "channel": "party",
    })
    return True, "ok"


async def accept(session):
    _clean()
    inv = _INVITES.pop(session.player_id, None)
    if not inv:
        return False, "No pending party invite."
    pid = inv["party_id"]
    party = _PARTIES.get(pid)
    if not party:
        return False, "That party no longer exists."
    if len(party["members"]) >= MAX_SIZE:
        return False, "That party is full."
    if session.player_id in party["members"]:
        return False, "Already in that party."
    party["members"].append(session.player_id)
    _attach(session)
    for mid in party["members"]:
        s = _srv().WORLD.sessions.get(mid)
        if s:
            _attach(s)
    await _push_all(party["members"], f"{session.char_name} joined the party.")
    return True, "ok"


async def decline(session):
    inv = _INVITES.pop(session.player_id, None)
    if not inv:
        return False, "No pending party invite."
    srv = _srv()
    leader = srv.WORLD.sessions.get(int(inv["from"]))
    if leader:
        await srv.send(leader.ws, "CHAT_MSG", **{
            "from": SPEAKER,
            "text": f"{session.char_name} declined the invite.",
            "channel": "party",
        })
    await srv.send(session.ws, "CHAT_MSG", **{
        "from": SPEAKER, "text": "Invite declined.", "channel": "party",
    })
    return True, "ok"


async def leave(session):
    pid = party_id_of(session.player_id)
    if not pid:
        return False, "You are not in a party."
    party = _PARTIES.get(pid)
    if not party:
        return False, "You are not in a party."
    members_before = list(party["members"])
    party["members"] = [m for m in party["members"] if m != session.player_id]
    session.party_ids = set()
    session.party_id = None
    await _push(session, "You left the party.")
    if len(party["members"]) <= 1:
        # Disband when alone.
        leftover = list(party["members"])
        _PARTIES.pop(pid, None)
        for mid in leftover:
            s = _srv().WORLD.sessions.get(mid)
            if s:
                s.party_ids = set()
                s.party_id = None
                await _push(s, "The party disbanded.")
        return True, "ok"
    if party["leader"] == session.player_id:
        party["leader"] = party["members"][0]
    for mid in party["members"]:
        s = _srv().WORLD.sessions.get(mid)
        if s:
            _attach(s)
    await _push_all(
        party["members"],
        f"{session.char_name} left the party.",
    )
    return True, "ok"


async def handle(session, msg):
    """PARTY message: action invite|accept|decline|leave, optional target_id."""
    action = (msg.get("action") or "").strip().lower()
    if action == "invite":
        ok, err = await invite(session, msg.get("target_id"))
        if not ok:
            await _srv().send(session.ws, "CHAT_MSG", **{
                "from": SPEAKER, "text": err, "channel": "party",
            })
        return
    if action == "accept":
        ok, err = await accept(session)
        if not ok:
            await _srv().send(session.ws, "CHAT_MSG", **{
                "from": SPEAKER, "text": err, "channel": "party",
            })
        return
    if action == "decline":
        await decline(session)
        return
    if action == "leave":
        ok, err = await leave(session)
        if not ok:
            await _srv().send(session.ws, "CHAT_MSG", **{
                "from": SPEAKER, "text": err, "channel": "party",
            })
        return
    if action == "sync":
        await _push(session)
        return
    await _srv().send(session.ws, "CHAT_MSG", **{
        "from": SPEAKER,
        "text": "Party: invite / accept / decline / leave.",
        "channel": "party",
    })


async def broadcast_chat(session, text):
    """Send party-channel chat to every online member."""
    p = party_of(session.player_id)
    if not p:
        await _srv().send(session.ws, "CHAT_MSG", **{
            "from": SPEAKER,
            "text": "You are not in a party.",
            "channel": "party",
        })
        return
    srv = _srv()
    import nobility
    name = nobility.display_name(session)
    for mid in p["members"]:
        s = srv.WORLD.sessions.get(mid)
        if s:
            await srv.send(s.ws, "CHAT_MSG", **{
                "from": name,
                "text": text,
                "player_id": session.player_id,
                "channel": "party",
            })


def on_logout(session):
    """Drop invites; leave party quietly if alone would disband."""
    _INVITES.pop(session.player_id, None)
    # Keep the party roster for a reconnect window — mark offline via public().
    # If they were the only online member later, leave is optional.
    pass
