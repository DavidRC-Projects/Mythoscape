"""Crownfall phase 5: guilds. Run: python3 tools/test_guilds.py"""
import os
import sqlite3
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "server"))

import apprentice as ap  # noqa: E402
import clans  # noqa: E402
import royal_treasury as rt  # noqa: E402

T0 = 1_760_000_000.0


def _db(n_players=30, old=False):
    c = sqlite3.connect(":memory:")
    c.execute("CREATE TABLE players (id INTEGER PRIMARY KEY, char_name TEXT, bank_coins INTEGER DEFAULT 0)")
    for i in range(1, n_players + 1):
        c.execute("INSERT INTO players (id, char_name) VALUES (?, ?)", (i, f"p{i}"))
    if old:
        c.execute("CREATE TABLE clans (clan_id INTEGER PRIMARY KEY, name TEXT UNIQUE COLLATE NOCASE, "
                  "leader_id INTEGER, created_at REAL)")
        c.execute("CREATE TABLE clan_members (player_id INTEGER PRIMARY KEY, clan_id INTEGER, joined_at REAL)")
        c.execute("INSERT INTO clans VALUES (1, 'Old Guard', 2, 1.0)")
        for pid, t in ((1, 1.0), (2, 2.0), (3, 3.0)):
            c.execute("INSERT INTO clan_members VALUES (?, 1, ?)", (pid, t))
    clans.ensure_tables(c)
    rt.ensure_schema(c)
    clans._CONN = c
    return c


def _guild(c, members=0, ranks=None):
    ap.bank_set(c, 1, clans.CHARTER_COST)
    ok, _m, cid = clans.create_core(1, "Testers", now=T0)
    assert ok
    for i in range(2, 2 + members):
        clans.join_core(i, cid, now=T0 + i)
    for pid, rank in (ranks or {}).items():
        c.execute("UPDATE clan_members SET rank = ? WHERE player_id = ?", (rank, pid))
    return cid


def test_migration():
    c = _db(old=True)
    ranks = dict(c.execute("SELECT player_id, rank FROM clan_members"))
    assert ranks == {1: "Member", 2: "Leader", 3: "Member"}
    assert clans.bank_balance(1) == 0 and clans.public(1)["name"] == "Old Guard"
    clans.ensure_tables(c)   # idempotent


def test_create_cost():
    c = _db()
    ap.bank_set(c, 1, 9_999)
    assert not clans.create_core(1, "Poor")[0] and ap.bank_get(c, 1) == 9_999
    ap.bank_set(c, 1, 10_000)
    assert clans.create_core(1, "Rich")[0]
    assert ap.bank_get(c, 1) == 0 and rt.balance(c) == 10_000 and clans.rank_of(1) == "Leader"


def test_ranks():
    c = _db()
    _guild(c, members=4, ranks={2: "Officer", 3: "Officer", 4: "Member", 5: "Recruit"})
    assert not clans.can_invite(clans.rank_of(4)) and clans.can_invite(clans.rank_of(2))
    assert clans.kick_core(2, 4)[0]
    assert not clans.kick_core(2, 3)[0]
    cid = clans.clan_of(1)
    ap.bank_set(c, 1, 200_000)
    clans.deposit_core(1, 200_000, now=T0)
    clans.join_core(4, cid)
    c.execute("UPDATE clan_members SET rank = 'Member' WHERE player_id = 4")
    assert clans.withdraw_core(4, 5_000, now=T0)[0] and not clans.withdraw_core(4, 1, now=T0)[0]
    assert clans.withdraw_core(2, 50_000, now=T0)[0] and not clans.withdraw_core(2, 1, now=T0)[0]
    assert not clans.withdraw_core(5, 1, now=T0)[0]
    assert clans.withdraw_core(4, 5_000, now=T0 + 86400)[0]   # new day


def test_bank_never_negative_and_logged():
    c = _db()
    cid = _guild(c)
    ap.bank_set(c, 1, 100)
    clans.deposit_core(1, 100, now=T0)
    assert not clans.withdraw_core(1, 101, now=T0)[0]
    assert clans.withdraw_core(1, 100, now=T0)[0] and clans.bank_balance(cid) == 0
    acts = [r[0] for r in c.execute("SELECT action FROM clan_bank_log ORDER BY id")]
    assert acts == ["deposit", "withdraw"]


def test_recruits_and_upkeep():
    c = _db()
    cid = _guild(c)
    c.execute("UPDATE clans SET bank_coins = ? WHERE clan_id = ?", (9 * clans.RECRUIT_HIRE_COST, cid))
    for _ in range(8):
        assert clans.hire_core(1, "Guard", now=T0)[0]
    assert not clans.hire_core(1, "Guard", now=T0)[0]
    c.execute("DELETE FROM clan_recruits WHERE id > 3")
    c.execute("UPDATE clans SET bank_coins = 600 WHERE clan_id = ?", (cid,))
    t0 = rt.balance(c)
    paid, skipped = clans.settle_upkeep(c, cid, now=T0 + 86400 + 1)
    assert (paid, skipped) == (2, 1) and clans.bank_balance(cid) == 100
    assert clans.recruit_count(cid, active_only=True) == 2
    assert rt.balance(c) - t0 == 2 * int(250 * 0.05)
    c.execute("UPDATE clans SET bank_coins = 1000000 WHERE clan_id = ?", (cid,))
    paid, skipped = clans.settle_upkeep(c, cid, now=T0 + 31 * 86400 + 1)
    assert paid + skipped <= 3 * 7 and clans.recruit_count(cid, active_only=True) == 3


def _strength(c, players, recruits, inactive=0):
    cid = _guild(c, members=players - 1)
    for i in range(recruits):
        c.execute("INSERT INTO clan_recruits (clan_id, name, role, hired_at, upkeep_paid_through, active) "
                  "VALUES (?, ?, 'Guard', ?, ?, ?)", (cid, f"r{i}", T0, T0, 0 if i < inactive else 1))
    return clans.royal_challenge_strength(cid)


def test_strength():
    assert _strength(_db(), 12, 8)[3]
    assert not _strength(_db(), 11, 8)[3]
    assert _strength(_db(), 12, 10)[2] == 20
    assert not _strength(_db(), 12, 8, inactive=1)[3]


def test_castle_hook():
    c = _db()
    cid = _guild(c)
    allc = ["gothic", "white_rose", "sky_anchor", "king"]
    assert not clans.can_challenge_castle(cid, "king", owned_castles=allc, all_castles=allc)
    assert clans.can_challenge_castle(cid, "gothic", owned_castles=allc[:3], all_castles=allc)
    assert not clans.can_challenge_castle(cid, "gothic", owned_castles=allc[:1], all_castles=allc)


def test_succession():
    c = _db()
    cid = _guild(c, members=3, ranks={2: "Member", 3: "Officer", 4: "Officer"})
    clans.leave_core(1)
    assert clans.rank_of(3) == "Leader"     # longest-serving Officer
    clans.leave_core(3)
    assert clans.rank_of(4) == "Leader"
    clans.leave_core(4)
    assert clans.rank_of(2) == "Leader"     # then Member
    assert clans.leave_core(2) == (cid, True)


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print("ok", name)
