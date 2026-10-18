"""Crownfall phase 7: throne paths, marriage, consorts. Run: python3 tools/test_throne.py"""
import os
import sqlite3
import sys
import time
import types

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "server"))

import apprentice as ap  # noqa: E402
import clans  # noqa: E402
import nobility as nb  # noqa: E402
import property as prop  # noqa: E402
import reputation as rep  # noqa: E402
import royal_treasury as rt  # noqa: E402
import throne as th  # noqa: E402

T0 = 1_760_000_000.0
QUESTS = ["q1", "q2"]


def _db():
    c = sqlite3.connect(":memory:")
    c.execute("CREATE TABLE players (id INTEGER PRIMARY KEY, char_name TEXT, gender TEXT, "
              "bank_coins INTEGER DEFAULT 0, coins INTEGER DEFAULT 0)")
    for i in range(1, 30):
        c.execute("INSERT INTO players (id, char_name, gender) VALUES (?, ?, ?)",
                  (i, f"p{i}", "female" if i % 2 == 0 else "male"))
    for mod in (rt, rep, ap, prop, nb, th):
        mod.ensure_schema(c)
    clans.ensure_tables(c)
    c.execute("CREATE TABLE castle_ownership (castle_id TEXT PRIMARY KEY, owner_account_id INTEGER, "
              "owner_display_name TEXT, purchased_at REAL, last_tax_paid_at REAL, tax_weeks_owed INTEGER DEFAULT 0)")
    clans._CONN = c
    th.set_titles_hook(None)
    return c


def _sess(pid=1, gender="male", combat=120, rank=0, score=900, lvl=99):
    s = types.SimpleNamespace(player_id=pid, gender=gender, noble_rank=rank, reputation=score, bank_coins=0,
                              char_name=f"p{pid}", xp={"etiquette": 1, "charisma": 1},
                              quests={q: {"status": "complete"} for q in QUESTS})
    s.level = lambda sk: lvl
    s.combat_level = lambda: combat
    return s


def _ready_guild(c, leader=1, players=12, recruits=8):
    ap.bank_set(c, leader, clans.CHARTER_COST)
    _ok, _m, cid = clans.create_core(leader, f"Guild {leader}", now=T0)
    assert _ok, _m
    for i in [p for p in range(1, 29) if p != leader][: players - 1]:
        clans.join_core(i, cid)
    for i in range(recruits):
        c.execute("INSERT INTO clan_recruits (clan_id, name, role, hired_at, upkeep_paid_through, active) "
                  "VALUES (?, ?, 'Guard', ?, ?, 1)", (cid, f"r{i}", T0, T0))
    c.execute("INSERT OR REPLACE INTO castle_ownership VALUES ('gothic', ?, 'x', ?, ?, 0)", (leader, T0, T0))
    return cid


def test_crown_eligibility():
    c = _db()
    s = _sess(combat=50)
    s.quests = {}
    ok, missing = th.crown_eligible(s, c, QUESTS)
    assert not ok and len(missing) == 4
    c2 = _db()
    _ready_guild(c2, players=11)
    ok, missing = th.crown_eligible(_sess(), c2, QUESTS)
    assert not ok and len(missing) == 1 and "Royal Challenge" in missing[0]
    c3 = _db()
    _ready_guild(c3)
    assert th.crown_eligible(_sess(), c3, QUESTS)[0]


def test_scheduling():
    c = _db()
    _ready_guild(c)
    s = _sess()
    ap.bank_set(c, 1, 49_999)
    assert not th.schedule_crown(s, c, 24, T0, QUESTS)[0] and ap.bank_get(c, 1) == 49_999
    ap.bank_set(c, 1, 10**6)
    assert not th.schedule_crown(s, c, 11, T0, QUESTS)[0]
    assert not th.schedule_crown(s, c, 49, T0, QUESTS)[0]
    assert th.schedule_crown(s, c, 12, T0, QUESTS)[0]
    assert not th.schedule_crown(s, c, 48, T0, QUESTS)[0]      # one at a time
    c.execute("DELETE FROM challenges")
    assert th.schedule_crown(s, c, 48, T0, QUESTS)[0]
    assert rt.balance(c) >= 2 * th.CROWN_FEE


def _run(b, pattern):
    """pattern: list of (seconds, captain_dead, challengers, defenders)."""
    now = b["start"]
    for secs, dead, ch, df in pattern:
        for _ in range(int(secs // 6)):
            now += 6
            r = th.step_battle(b, now, dead, ch, df)
            if r:
                return r
    while True:
        now += 6
        r = th.step_battle(b, now, False, 0, 5)
        if r:
            return r


def test_battle_rules():
    b = th.new_battle({"id": 1, "kind": "crown"}, T0)
    assert _run(b, [(60, False, 3, 5), (300, True, 6, 2)]) == "win"
    b = th.new_battle({"id": 2, "kind": "crown"}, T0)
    assert _run(b, [(294, True, 6, 2), (6, True, 1, 2), (294, True, 6, 2), (6, False, 6, 2)] * 3) == "loss"


def test_win_and_loss_outcomes():
    c = _db()
    _ready_guild(c, leader=2)               # female leader
    c.execute("UPDATE players SET noble_rank = 3, bank_coins = 777 WHERE id = 5")
    th._crown(c, 5, "conquest", "imprisoned", T0)   # player 5 is monarch first
    assert th.state(c)["old_king_state"] == "imprisoned"
    out = th.resolve_crown(c, {"id": 0, "challenger_id": 2}, "win", T0 + 10)
    assert out["titles"][2] == "Queen"
    assert c.execute("SELECT royal_title, noble_rank, bank_coins FROM players WHERE id = 5").fetchone() == (None, 3, 777)
    c2 = _db()
    _ready_guild(c2, leader=1)
    out = th.resolve_crown(c2, {"id": 0, "challenger_id": 1}, "win", T0)
    assert out["titles"][1] == "King" and th.state(c2)["old_king_state"] == "imprisoned"
    c3 = _db()
    _ready_guild(c3, leader=1)
    ap.bank_set(c3, 1, 1234)
    out = th.resolve_crown(c3, {"id": 0, "challenger_id": 1}, "loss", T0)
    assert out["castle_lost"] == "gothic" and ap.bank_get(c3, 1) == 1234
    assert not c3.execute("SELECT 1 FROM castle_ownership WHERE castle_id = 'gothic'").fetchone()
    assert th._cooldown(c3, 1, "crown", T0 + 6 * 86400) > 0


def test_castle_challenge_rules():
    c = _db()
    cid = _ready_guild(c)
    c.execute("UPDATE clans SET challenge_castle_id = 'white_rose' WHERE clan_id = ?", (cid,))
    ap.bank_set(c, 1, 10**6)
    allc = ["gothic", "white_rose", "sky_anchor", "king"]
    assert not th.schedule_castle(_sess(), c, 24, T0, owned_castles=["gothic"], all_castles=allc)[0]
    c.execute("UPDATE clans SET challenge_castle_id = 'king' WHERE clan_id = ?", (cid,))
    assert not th.schedule_castle(_sess(), c, 24, T0, owned_castles=allc, all_castles=allc)[0]
    c.execute("UPDATE clans SET challenge_castle_id = 'white_rose' WHERE clan_id = ?", (cid,))
    assert th.schedule_castle(_sess(), c, 24, T0, owned_castles=allc[:3], all_castles=allc)[0]


def test_courtier():
    c = _db()
    assert th.courtier_eligible(_sess(gender="male", rank=5), c) == (False, [])
    assert not th.courtier_eligible(_sess(pid=2, gender="female", rank=2), c)[0]
    assert th.courtier_eligible(_sess(pid=2, gender="female", rank=3), c)[0]
    got = sum(th.court_task(c, 2, T0) for _ in range(5))
    assert got == 60
    sat = T0
    while not th.ball_open(sat):
        sat += 1800
    assert th.ball_attend(c, 2, sat) == 100 and th.ball_attend(c, 2, sat + 60) == 0
    th.add_favour(c, 2, 5000)
    assert th.favour_row(c, 2)["favour"] == 1000
    th.add_favour(c, 2, -5000)
    assert th.favour_row(c, 2)["favour"] == 0


def test_acclaim():
    c = _db()
    th.add_favour(c, 2, 1000)
    q = _sess(pid=2, gender="female", rank=3)
    ap.bank_set(c, 2, 10**6)
    assert th.schedule_acclaim(q, c, 24, T0)[0]
    ch = th.scheduled(c)[0]
    out = th.resolve_acclaim(c, ch, T0 + 25 * 3600)
    assert out["result"] == "win" and th.state(c)["old_king_state"] == "exiled"
    assert c.execute("SELECT royal_title FROM players WHERE id = 2").fetchone()[0] == "Queen"
    # against a player monarch with higher reputation
    c2 = _db()
    c2.execute("UPDATE players SET reputation = 900 WHERE id = 3")
    c2.execute("UPDATE players SET reputation = 850 WHERE id = 4")
    th._crown(c2, 3, "conquest", "imprisoned", T0)
    th.add_favour(c2, 4, 1000)
    ap.bank_set(c2, 4, 10**6)
    assert th.schedule_acclaim(_sess(pid=4, gender="female", rank=3, score=850), c2, 12, T0)[0]
    out = th.resolve_acclaim(c2, th.scheduled(c2)[0], T0 + 13 * 3600)
    f = th.favour_row(c2, 4)
    assert out["result"] == "loss" and f["favour"] == 500 and f["cooldown_until"] > T0


def test_marriage_and_consort():
    c = _db()
    ap.bank_set(c, 1, 5_000)
    ap.bank_set(c, 2, 4_999)
    assert not th.marry(c, 1, 2, T0)[0] and ap.bank_get(c, 1) == 5_000
    ap.bank_set(c, 2, 5_000)
    assert th.marry(c, 1, 2, T0)[0] and ap.bank_get(c, 1) == 0 and ap.bank_get(c, 2) == 0
    ap.bank_set(c, 3, 10**5)
    assert not th.marry(c, 3, 2, T0)[0]
    th._crown(c, 2, "courtier", "exiled", T0)
    assert c.execute("SELECT royal_title FROM players WHERE id = 1").fetchone()[0] == "Prince Consort"
    th.divorce(c, 1, T0 + 10)
    assert c.execute("SELECT royal_title FROM players WHERE id = 1").fetchone()[0] is None
    assert c.execute("SELECT royal_title FROM players WHERE id = 2").fetchone()[0] == "Queen"


def test_restart_resumes():
    c = _db()
    _ready_guild(c)
    ap.bank_set(c, 1, 10**6)
    th.schedule_crown(_sess(), c, 12, T0, QUESTS)
    ch = th.scheduled(c)[0]
    th.start(c, ch["id"], T0 + 12 * 3600)
    battles = th.reload(c, now=T0 + 12 * 3600 + 600)
    b = battles[ch["id"]]
    assert b["end"] == T0 + 12 * 3600 + 600 + th.CROWN_WINDOW and th.scheduled(c)[0]["status"] == "active"


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print("ok", name)
