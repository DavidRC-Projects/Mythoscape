"""Crownfall phase 6: noble ranks. Run: python3 tools/test_nobility.py"""
import os
import sqlite3
import sys
import types

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "server"))

import apprentice as ap  # noqa: E402
import clans  # noqa: E402
import nobility as nb  # noqa: E402
import property as prop  # noqa: E402
import reputation as rep  # noqa: E402
import royal_treasury as rt  # noqa: E402

T0 = 1_760_000_000.0


def _db():
    c = sqlite3.connect(":memory:")
    c.execute("CREATE TABLE players (id INTEGER PRIMARY KEY, char_name TEXT, bank_coins INTEGER DEFAULT 0)")
    for i in range(1, 15):
        c.execute("INSERT INTO players (id, char_name) VALUES (?, ?)", (i, f"p{i}"))
    for mod in (rt, rep, ap, prop, nb):
        mod.ensure_schema(c)
    clans.ensure_tables(c)
    clans._CONN = c
    return c


def _sess(pid=1, rank=0, gender="female", score=900, lvl=99, combat=120, bank=0):
    s = types.SimpleNamespace(player_id=pid, noble_rank=rank, gender=gender, reputation=score,
                              char_name="Elsa", bank_coins=bank, xp={"etiquette": 1, "charisma": 1})
    s.level = lambda sk: lvl
    s.combat_level = lambda: combat
    return s


def test_rank_names():
    assert nb.rank_name(2, "female") == "Dame" and nb.rank_name(3, "male") == "Baron"
    assert nb.rank_name(5, "female") == "Duchess" and nb.rank_name(3, None) == "Baron"
    assert nb.display_name(_sess(rank=2)) == "Dame Elsa" and nb.display_name(_sess(rank=0)) == "Elsa"
    assert nb.display_name(_sess(rank=2, gender="male")) == "Sir Elsa"


def test_migration():
    c = _db()
    assert c.execute("SELECT noble_rank, royal_title FROM players WHERE id = 1").fetchone() == (0, None)
    nb.ensure_schema(c)


def _house(c, pid=1):
    c.execute("CREATE TABLE IF NOT EXISTS housing_deeds (house_key TEXT PRIMARY KEY, owner_id INTEGER)")
    c.execute("INSERT INTO housing_deeds VALUES (?, ?)", (f"h{pid}", pid))


def test_petition_fee():
    c = _db()
    _house(c)
    s = _sess(rank=1)
    ap.bank_set(c, 1, 24_999)
    s.bank_coins = 24_999
    ok, _m, _o = nb.petition(s, c, now=T0)
    assert not ok and s.noble_rank == 1 and ap.bank_get(c, 1) == 24_999 and nb.cooldown_left(c, 1, T0) > 0
    c.execute("UPDATE players SET last_petition_refused = NULL")
    ap.bank_set(c, 1, 25_000)
    s.bank_coins = 25_000
    ok, _m, _o = nb.petition(s, c, now=T0)
    assert ok and s.noble_rank == 2 and ap.bank_get(c, 1) == 0 and rt.balance(c) == 25_000
    assert c.execute("SELECT from_rank, to_rank, fee FROM noble_log").fetchone() == (1, 2, 25_000)


def test_no_skip_and_cooldown():
    c = _db()
    s = _sess(rank=0, bank=10**7)
    ap.bank_set(c, 1, 10**7)
    assert nb.petition(s, c, now=T0)[0] and s.noble_rank == 1   # one step only
    s2 = _sess(pid=2, rank=0, score=0)
    assert not nb.petition(s2, c, now=T0)[0]
    s2.reputation = 900
    ap.bank_set(c, 2, 10**7)
    s2.bank_coins = 10**7
    assert not nb.petition(s2, c, now=T0 + 3600)[0]           # still cooling down
    assert nb.petition(s2, c, now=T0 + 25 * 3600)[0]


def test_missing_list():
    c = _db()
    s = _sess(rank=1, lvl=5, bank=10**6)
    ok, missing = nb.check(s, c)
    assert not ok and any("Etiquette" in m for m in missing) and any("house" in m.lower() for m in missing)


def test_rank_kept():
    c = _db()
    s = _sess(rank=0, bank=10**6)
    ap.bank_set(c, 1, 10**6)
    nb.petition(s, c, now=T0)
    s.reputation = -200
    assert rep.tier(s.reputation) == "Distrusted" and nb.rank_of(c, 1) == 1
    c.execute("UPDATE players SET royal_title = 'King' WHERE id = 1")
    c.execute("UPDATE players SET royal_title = NULL WHERE id = 1")
    assert nb.rank_of(c, 1) == 1


def test_shop_cap():
    price = rep.buy_price(100, 900, nb.shop_discount(5))
    assert price == 90 and rt.buy_tax(price) == 5
    assert rep.buy_price(100, 0, nb.shop_discount(0)) == 100


def test_perks():
    c = _db()
    c.execute("UPDATE players SET noble_rank = 3 WHERE id = 1")
    ap.bank_set(c, 1, 200_000)
    prop.buy_plot(c, 1, now=T0)
    prop.upgrade(c, 1, "workshop")
    assert prop.status(c, 1)["slots"] == 4
    c.execute("UPDATE players SET noble_rank = 5 WHERE id = 2")
    ap.bank_set(c, 2, clans.CHARTER_COST)
    _ok, _m, cid = clans.create_core(2, "Dukes", now=T0)
    assert clans.recruit_cap(cid) == 10
    for i in range(10):
        c.execute("INSERT INTO clan_recruits (clan_id, name, role, hired_at, upkeep_paid_through, active) "
                  "VALUES (?, ?, 'Guard', ?, ?, 1)", (cid, f"r{i}", T0, T0))
    assert clans.royal_challenge_strength(cid)[2] == 1 + 8


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print("ok", name)
