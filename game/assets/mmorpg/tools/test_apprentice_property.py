"""Crownfall phase 4: apprenticeships and property. Run: python3 tools/test_apprentice_property.py"""
import os
import sqlite3
import sys
import types

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "server"))

import apprentice as ap  # noqa: E402
import property as prop  # noqa: E402
import reputation as rep  # noqa: E402
import royal_treasury as rt  # noqa: E402

T0 = 1_760_000_000.0   # a fixed moment; tests step whole hours from here
H = 3600


def _db():
    c = sqlite3.connect(":memory:")
    c.execute("CREATE TABLE players (id INTEGER PRIMARY KEY, name TEXT, bank_coins INTEGER DEFAULT 0, coins INTEGER DEFAULT 0)")
    for pid in (1, 2):
        c.execute("INSERT INTO players (id, name) VALUES (?, ?)", (pid, f"p{pid}"))
    rt.ensure_schema(c)
    rep.ensure_schema(c)
    ap.ensure_schema(c)
    prop.ensure_schema(c)
    return c


def _session(pid=1):
    import combat
    s = types.SimpleNamespace(player_id=pid, bank_coins=0, reputation=0,
                              xp={"smithing": 0, "cooking": 0, "fletching": 0})
    s.level = lambda sk: combat.level_from_xp(s.xp.get(sk, 0))
    return s


def _start_of_day():
    import time
    lt = time.localtime(T0)
    return time.mktime((lt.tm_year, lt.tm_mon, lt.tm_mday, 0, 0, 0, 0, 0, -1)) + 86400


def test_three_hours_smithy():
    c, s = _db(), _session()
    ap.sign_on(c, 1, "master_doran", "smithy", now=T0)
    r = ap.settle(c, s, now=T0 + 3 * H + 5)
    assert r["shifts"] == 3 and r["tax"] == 9 and r["coins"] == 171
    assert ap.bank_get(c, 1) == 171 and s.bank_coins == 171
    assert r["xp"] == 3 * int(90 * 1.01) == 270
    assert rt.balance(c) == 9


def test_thirty_days_offline_caps_at_24():
    c, s = _db(), _session()
    ap.sign_on(c, 1, "master_doran", "smithy", now=T0)
    now = T0 + 30 * 86400 + 10
    r = ap.settle(c, s, now=now)
    assert r["shifts"] <= ap.BACKLOG_SHIFT_CAP == 24
    last = ap.contract(c, 1)["last_settled"]
    assert now - last < H


def test_daily_cap_8():
    c, s = _db(), _session()
    day = _start_of_day()
    ap.sign_on(c, 1, "master_hollis", "farm", now=day)
    r = ap.settle(c, s, now=day + 10 * H + 1)
    assert r["shifts"] == 8


def test_rep_cap_5_a_day():
    c = _db()
    took = sum(rep.daily_take(c, 1, "rep_shift", ap.REP_PER_SHIFT, ap.REP_SHIFT_DAILY_CAP, now=T0) for _ in range(8))
    assert took == 5


def test_shift_xp_below_active():
    from content import CRAFT_RECIPES
    xps = [r.get("xp", 0) for r in (CRAFT_RECIPES.values() if isinstance(CRAFT_RECIPES, dict) else CRAFT_RECIPES)
           if r.get("skill") == "smithing"]
    active_hour = min(x for x in xps if x) * 100
    assert ap.shift_xp("smithy", 99) < active_hour


def test_plot_buy_and_upgrade():
    c = _db()
    ap.bank_set(c, 1, 24_999)
    ok, _ = prop.buy_plot(c, 1, now=T0)
    assert not ok and ap.bank_get(c, 1) == 24_999 and prop.owned(c, 1) is None
    ap.bank_set(c, 1, 25_000 + 175_000)
    assert prop.buy_plot(c, 1, now=T0)[0] and ap.bank_get(c, 1) == 175_000
    assert prop.upgrade(c, 1, "workshop")[0] and ap.bank_get(c, 1) == 0
    assert prop.owned(c, 1)["kind"] == "workshop" and prop.slots("workshop") == 3


def test_npc_worker_owner_short():
    c = _db()
    ap.bank_set(c, 1, 25_000 + 95_000 + 2_000)
    prop.buy_plot(c, 1, now=T0)
    prop.upgrade(c, 1, "farm")
    day = _start_of_day()
    c.execute("DELETE FROM property_workers")
    ap.bank_set(c, 1, 2_000)
    prop.hire(c, 1, now=day)
    ap.bank_set(c, 1, 100)
    before_tax = rt.balance(c)
    r = prop.settle_income(c, 1, now=day + 5 * H + 1)
    assert r["shifts"] == 3 and r["skipped"] == 2
    gross = 3 * (prop.WORKER_VALUE - prop.WORKER_WAGE)
    assert prop.WORKER_VALUE == 110 and gross == 240
    assert r["tax"] == int(gross * 0.05) == 12 and r["net"] == gross - 12
    assert ap.bank_get(c, 1) == 100 - 3 * prop.WORKER_WAGE + 3 * prop.WORKER_VALUE - 12 >= 0
    assert rt.balance(c) - before_tax == 12


def test_workshop_land_fee():
    c = _db()
    ap.bank_set(c, 1, 200_000)
    prop.buy_plot(c, 1, now=T0)
    prop.upgrade(c, 1, "workshop")
    ap.bank_set(c, 1, 1_000)
    purse, bank, out = prop.settle_land_fee_rows(c, 1, 0, 1_000, now=T0 + 3 * 86400 + 5)
    assert out == [("workshop", 2, 3)] and bank == 100 and purse == 0   # 2 x 450 paid, 1 unpaid day forgiven
    assert prop.land_fee("workshop") == 450


def test_player_apprentice_paid_by_owner():
    c = _db()
    ap.bank_set(c, 1, 200_000)
    prop.buy_plot(c, 1, now=T0)
    prop.upgrade(c, 1, "workshop")
    ap.bank_set(c, 1, 40)
    pid_, owner, kind = prop.find_workplace(c, 2)
    assert owner == 1 and kind == "workshop"
    ap.sign_on(c, 2, f"property:{pid_}", "workshop", pid_, now=T0)
    r = ap.settle(c, _session(2), now=T0 + 3 * H + 1)
    assert r["shifts"] == 0 and r["skipped"] == 3     # 40 can't cover a 50-gold wage
    assert ap.bank_get(c, 1) == 40 and prop.owned(c, 1)["unpaid_shifts"] == 3
    # with one wage in hand each shift pays for the next (value 110 beats the 50 wage)
    ap.bank_set(c, 1, 50)
    r = ap.settle(c, _session(2), now=T0 + 6 * H + 1)
    assert r["shifts"] == 3 and r["skipped"] == 0
    assert ap.bank_get(c, 1) > 50                      # the owner comes out ahead


def test_resign_cooldown():
    c = _db()
    ap.sign_on(c, 1, "master_wren", "workshop", now=T0)
    assert not ap.sign_on(c, 1, "master_doran", "smithy", now=T0 + 10)[0]
    ap.leave(c, 1, now=T0 + 20)
    assert not ap.sign_on(c, 1, "master_doran", "smithy", now=T0 + 60)[0]
    assert ap.sign_on(c, 1, "master_doran", "smithy", now=T0 + 20 + H)[0]


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print("ok", name)
