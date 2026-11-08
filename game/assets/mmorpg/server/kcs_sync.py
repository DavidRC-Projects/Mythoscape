"""Ordered King's Castle siege updates.

Each player has their own sequence. A snapshot is the baseline. A later
delta on that same connection uses the next number. Anything older,
repeated, or missing a number is dropped, so a late message cannot put a
wrecked engine or a dead fighter back.

Player positions reuse the existing Crown siege interest radius and cap.
Shots and engine hit points go to that same nearby ring. A gate, a placed
engine, or an elimination is rare and goes to everyone on the siege map.
"""
from __future__ import annotations


WRITE_BUFFER_LIMIT = 256 * 1024


def bump(session) -> int:
    nxt = int(getattr(session, "_kcs_seq", 0) or 0) + 1
    session._kcs_seq = nxt
    return nxt


def write_backlog(ws) -> int:
    try:
        return int(ws.transport.get_write_buffer_size())
    except Exception:
        return 0


def interest_radius() -> int:
    import crown_siege
    return int(crown_siege.INTEREST_RADIUS)


def interest_cap() -> int:
    import crown_siege
    return int(crown_siege.INTEREST_CAP)


def near(origin, other, radius=None) -> bool:
    import crown_siege
    return crown_siege.in_interest(origin[0], origin[1], other[0], other[1], radius)
