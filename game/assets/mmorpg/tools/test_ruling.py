"""Crownfall phase 8: ruling. Run: python3 tools/test_ruling.py"""
import os
import sqlite3
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "server"))

import apprentice as ap  # noqa: E402
import clans  # noqa: E402
import nobility as nb  # noqa: E402
import property as prop  # noqa: E402
import reputation as rep  # noqa: E402
import royal_treasury as rt  # noqa: E402
import ruling as ru  # noqa: E402
import throne as th  # noqa: E402

T0 = 1_760_000_000.0
DAY = 86400
MONARCH, STEWARD, NOBODY = 1, 2, 3


def _db(balance=0):
    c = sqlite3.connect(":memory:")
    c.execute("CREATE TABLE players (id INTEGER PRIMARY KEY, char_name TEXT, gender TEXT, "
              "bank_coins INTEGER DEFAULT 0, coins INTEGER DEFAULT 0)")
    for i in range(1, 10):
        c.execute("INSERT INTO players (id, char_name, gender) VALUES (?, ?, ?)",
                  (i, f"p{i}", "female" if i % 2 == 0 else "male"))
    for mod in (rt, rep, ap, prop, nb, th):
        mod.ensure_schema(c)
    clans.ensure_tables(c)
    clans._CONN = c
    ru.ensure_schema(c)
    th.set_titles_hook(None)
    c.execute("UPDATE royal_treasury SET balance = ? WHERE id = 1", (balance,))
    c.execute("UPDATE players SET noble_rank = 1")
    th._crown(c, MONARCH, "conquest", "imprisoned", T0 - 10 * DAY)
    c.execute("UPDATE players SET noble_rank = 1")
    ru.appoint(c, MONARCH, "Steward", STEWARD, T0)
    c.commit()
    return c


def test_defaults():
    c = sqlite3.connect(":memory:")
    ru.ensure_schema(c)
    assert rt.sales_tax_rate() == 0.05 and rt.land_fee_daily() == 500 and prop.land_fee("workshop") == 450
    assert prop.land_fee("farm") == 300
    # save migration: an untouched old default moves, a monarch's own choice stays (clamped to the new bounds)
    c2 = sqlite3.connect(":memory:")
    c2.execute("CREATE TABLE realm_settings (key TEXT PRIMARY KEY, value REAL, changed_at REAL, changed_by INTEGER)")
    c2.execute("INSERT INTO realm_settings VALUES ('land_fee_farm', 400, NULL, NULL)")
    c2.execute("INSERT INTO realm_settings VALUES ('land_fee_workshop', 1200, 1.0, 7)")
    ru.ensure_schema(c2)
    vals = dict(c2.execute("SELECT key, value FROM realm_settings").fetchall())
    assert vals["land_fee_farm"] == 300 and vals["land_fee_workshop"] == 900, vals


def test_tax_bounds():
    c = _db()
    assert not ru.set_tax(c, MONARCH, "sales_tax", 0.11, T0)[0]
    assert not ru.set_tax(c, MONARCH, "sales_tax", 0.08, T0)[0]
    assert ru.set_tax(c, MONARCH, "sales_tax", 0.07, T0)[0]
    assert rt.sales_tax_rate() == 0.05                    # not until the daily tick
    assert not ru.set_tax(c, MONARCH, "sales_tax", 0.06, T0 + 3600)[0]
    ru.apply_pending(c, T0 + DAY)
    assert abs(rt.sales_tax_rate() - 0.07) < 1e-9


def test_roles():
    c = _db(balance=10**6)
    assert ru.set_tax(c, STEWARD, "land_fee_house", 600, T0)[0]
    assert not ru.set_tax(c, STEWARD, "sales_tax", 0.06, T0)[0]
    for call in (lambda: ru.set_tax(c, NOBODY, "sales_tax", 0.06, T0),
                 lambda: ru.fund_work(c, NOBODY, "feast", T0),
                 lambda: ru.post_bounty(c, NOBODY, "goblin", 5000, {"goblin": {}}, T0),
                 lambda: ru.cancel_bounty(c, NOBODY, 1, T0),
                 lambda: ru.appoint(c, NOBODY, "Marshal", 4, T0),
                 lambda: ru.dismiss(c, NOBODY, "Steward", T0),
                 lambda: ru.herald_announce(c, NOBODY, "hi", T0),
                 lambda: ru.free_king(c, NOBODY, T0),
                 lambda: ru.recall_king(c, NOBODY, T0)):
        assert not call()[0]


def test_daily_cap():
    c = _db(balance=500_000)
    assert ru.daily_cap(c, T0) == 100_000
    c2 = _db(balance=2_000_000)
    assert ru.daily_cap(c2, T0) == 250_000
    assert ru.fund_work(c, MONARCH, "roads", T0)[0] and ru.fund_work(c, MONARCH, "markets", T0)[0]
    assert not ru.fund_work(c, MONARCH, "feast", T0)[0]       # 90k + 30k > 100k
    c3 = _db(balance=10_000)
    assert not ru.fund_work(c3, MONARCH, "feast", T0)[0] and rt.balance(c3) == 10_000


def test_bounties():
    c = _db(balance=500_000)
    mons = {"goblin": {}, "wolf": {}, "rat": {}, "bear": {}}
    assert not ru.post_bounty(c, MONARCH, "goblin", 999, mons, T0)[0]
    assert ru.post_bounty(c, MONARCH, "goblin", 5_000, mons, T0)[0] and ru.reserved(c) == 5_000
    assert ru.post_bounty(c, MONARCH, "wolf", 5_000, mons, T0)[0]
    assert ru.post_bounty(c, MONARCH, "rat", 5_000, mons, T0)[0]
    assert not ru.post_bounty(c, MONARCH, "bear", 5_000, mons, T0)[0]
    ru.cancel_bounty(c, MONARCH, 3, T0)
    assert ru.reserved(c) == 10_000
    assert ru.claim_bounty(c, "goblin", 5, T0) == 5_000 and ap.bank_get(c, 5) == 5_000
    assert ru.claim_bounty(c, "goblin", 6, T0) == 0 and rt.balance(c) == 495_000


def test_stipends():
    c = _db(balance=1_000)
    paid, skipped = ru.pay_stipends(c, T0)
    assert paid == [] and skipped and rt.balance(c) == 1_000 and ap.bank_get(c, STEWARD) == 0
    c2 = _db(balance=10_000)
    before = ru.spent_today(c2, T0)
    ru.pay_stipends(c2, T0)
    assert ap.bank_get(c2, STEWARD) == 1_500 and ru.spent_today(c2, T0) == before


def test_no_self_payment():
    banned = ("withdraw", "pay_self", "take", "transfer", "to_bank", "personal")
    assert not [n for n in dir(ru) if any(b in n.lower() for b in banned)]


def test_throne_change():
    c = _db(balance=10**6)
    ru.set_tax(c, MONARCH, "sales_tax", 0.07, T0)
    ru.apply_pending(c, T0 + DAY)
    c.execute("UPDATE players SET noble_rank = 2 WHERE id = 4")
    th._crown(c, 4, "conquest", "imprisoned", T0 + 5 * DAY)
    old = c.execute("SELECT days, ended_at FROM reigns WHERE player_id = ? ORDER BY id DESC", (MONARCH,)).fetchone()
    assert old[0] == 15 and old[1] is not None
    assert ru.current_reign(c)["player_id"] == 4
    assert c.execute("SELECT COUNT(*) FROM council").fetchone()[0] == 0
    assert abs(rt.sales_tax_rate() - 0.07) < 1e-9
    assert c.execute("SELECT royal_title, noble_rank FROM players WHERE id = ?", (MONARCH,)).fetchone() == (None, 1)


def test_old_king():
    c = _db(balance=10**6)
    assert ru.free_king(c, MONARCH, T0)[0] and th.state(c)["old_king_state"] == "freed"
    th._crown(c, 4, "conquest", "imprisoned", T0 + DAY)
    assert th.state(c)["old_king_state"] == "freed"
    c2 = _db(balance=10**6)
    c2.execute("UPDATE throne SET old_king_state = 'exiled'")
    assert not ru.free_king(c2, MONARCH, T0)[0]
    before = rt.balance(c2)
    assert ru.recall_king(c2, MONARCH, T0)[0] and before - rt.balance(c2) == 50_000
    assert ru.counsel(c2, 5, T0) == ru.COUNSEL_XP == 150 and ru.counsel(c2, 5, T0 + 60) == 0


def test_consort():
    assert rep.buy_price(100, 900, nb.shop_discount(5) + ru.consort_discount("Queen Consort")) == 90
    assert ru.consort_discount("King") == 0
    c = _db()
    c.execute("UPDATE players SET royal_title = 'Prince Consort', noble_rank = 0 WHERE id = 7")
    ap.bank_set(c, 7, 200_000)
    prop.buy_plot(c, 7, now=T0)
    prop.upgrade(c, 7, "workshop")
    assert prop.status(c, 7)["slots"] == 4


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print("ok", name)
