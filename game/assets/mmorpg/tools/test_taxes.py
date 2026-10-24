"""Crownfall phase 2: royal taxes, treasury, land fee. Run: python3 tools/test_taxes.py"""
import asyncio
import os
import sqlite3
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "server"))

import royal_treasury as rt  # noqa: E402
import housing  # noqa: E402

DAY = rt.DAY_SECONDS


def _conn():
    c = sqlite3.connect(":memory:")
    rt.ensure_schema(c)
    housing.ensure_schema(c)
    return c


def test_rates():
    assert rt.buy_tax(100) == 5 and rt.buy_tax(1) == 1 and rt.buy_tax(0) == 0
    assert rt.sell_tax(39) == 1 and rt.sell_tax(0) == 0 and rt.buy_tax(101) == 6


def test_credit():
    c = _conn()
    rt.credit(c, "sales_tax_buy", 1, 5)
    rt.credit(c, "sales_tax_buy", 1, 0)
    rt.credit(c, "sales_tax_buy", 1, -9)
    assert rt.balance(c) == 5
    assert c.execute("SELECT COUNT(*) FROM treasury_ledger").fetchone()[0] == 1


def _house(c, pid, paid_through):
    c.execute("INSERT INTO housing_deeds (house_key, owner_id, owner_name, land_fee_paid_through) VALUES (?, ?, 'x', ?)",
              (f"h{pid}", pid, paid_through))


def test_land_fee():
    c = _conn()
    now = 1_000_000.0
    _house(c, 1, now - 1 * DAY)
    purse, bank, res = housing.settle_land_fee_rows(c, 1, 499, 0, now=now)
    assert (purse, bank) == (499, 0) and res == [("h1", 0, 1)]
    assert c.execute("SELECT land_fee_paid_through FROM housing_deeds WHERE owner_id=1").fetchone()[0] == now
    _house(c, 2, now - 3 * DAY)
    purse, bank, res = housing.settle_land_fee_rows(c, 2, 2000, 8000, now=now)
    assert purse + bank == 10000 - 1500 and bank == 6500 and rt.balance(c) == 1500
    _house(c, 3, now - 30 * DAY)
    purse, bank, res = housing.settle_land_fee_rows(c, 3, 100000, 0, now=now)
    assert 100000 - purse == 3500
    # NULL paid_through: stamped now, no back-pay
    _house(c, 4, None)
    purse, bank, res = housing.settle_land_fee_rows(c, 4, 5000, 0, now=now)
    assert purse == 5000 and res == []


def test_buy_refused_without_tax_room():
    import types
    sys.argv = sys.argv[:1]
    import database
    database.Database.__init__.__defaults__ = (":memory:",)   # never touch world.db
    import server
    sent = []

    async def fake_send(ws, kind, **kw):
        sent.append((kind, kw))
    server.send = fake_send
    shop_id, item_id, price = next(
        (k, iid, i["price"]) for k, v in server.SHOPS.items() for iid, i in v["stock"].items()
        if i["price"] >= 20 and (server.ITEMS.get(iid) or {}).get("type") != "pet")
    sess = types.SimpleNamespace(reputation=0, coins=price, bank_coins=0, ws=None, player_id=1, owned_pets=[],
                                 equipment={}, inventory={}, bank={})
    asyncio.run(server.handle_shop_buy(sess, {"shop_id": shop_id, "item_id": item_id, "qty": 1}))
    assert sess.coins == price and sent and sent[0][0] == "ERROR"


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print("ok", name)
