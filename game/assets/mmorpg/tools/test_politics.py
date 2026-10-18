"""Crownfall phase 9: living politics. Run: python3 tools/test_politics.py"""
import asyncio
import os
import random
import sqlite3
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "server"))

import apprentice as ap  # noqa: E402
import clans  # noqa: E402
import nobility as nb  # noqa: E402
import politics as po  # noqa: E402
import property as prop  # noqa: E402
import reputation as rep  # noqa: E402
import royal_treasury as rt  # noqa: E402
import ruling as ru  # noqa: E402
import throne as th  # noqa: E402

T0 = 1_760_000_000.0
DAY = 86400
MONARCH, CHANCELLOR, NOBODY = 1, 2, 3


def _db(balance=500_000, player_king=True, king_state="imprisoned"):
    c = sqlite3.connect(":memory:")
    c.execute("CREATE TABLE players (id INTEGER PRIMARY KEY, char_name TEXT, gender TEXT, "
              "bank_coins INTEGER DEFAULT 0, coins INTEGER DEFAULT 0, reputation INTEGER DEFAULT 0)")
    for i in range(1, 10):
        c.execute("INSERT INTO players (id, char_name, gender) VALUES (?, ?, ?)", (i, f"p{i}", "male"))
    for mod in (rt, rep, ap, prop, nb, th):
        mod.ensure_schema(c)
    clans.ensure_tables(c)
    clans._CONN = c
    ru.ensure_schema(c)
    po.ensure_schema(c)
    th.set_titles_hook(None)
    c.execute("UPDATE royal_treasury SET balance = ? WHERE id = 1", (balance,))
    if player_king:
        th._crown(c, MONARCH, "conquest", king_state, T0 - 10 * DAY)
        c.execute("UPDATE players SET noble_rank = 1")
        assert ru.appoint(c, MONARCH, "Chancellor", CHANCELLOR, T0)[0]
    c.commit()
    return c


def _days(c, n, start=T0, rng=None):
    rng = rng or random.Random(1)
    vals = []
    for d in range(n):
        po.daily_mood_tick(c, start + d * DAY, rng=rng)
        c.execute("DELETE FROM court_events")   # keep events out of the drift maths
        vals.append(po.mood(c))
    return vals


def test_drift():
    c = _db(player_king=False)
    vals = _days(c, 30)
    assert all(35 <= v <= 64 for v in vals), vals
    assert vals[-1] <= 60
    c = _db(player_king=False)
    c.execute("UPDATE realm_settings SET value = 0.10 WHERE key = 'sales_tax'")
    for k, (d, *_r) in ru.SETTINGS.items():
        if k.startswith("land_fee_"):
            c.execute("UPDATE realm_settings SET value = ? WHERE key = ?", (d * 2, k))
    vals = _days(c, 7)
    assert any(po.band_of(v) in ("Unrest", "Revolt") for v in vals), vals
    # 3 public works at the default tax lift the realm into Content (balance pass: damped mood)
    c = _db(player_king=False)
    for k in ru.PUBLIC_WORKS:
        c.execute("INSERT INTO public_works (key, funded_at, expires_at) VALUES (?, ?, ?)", (k, T0, T0 + 30 * DAY))
    vals = _days(c, 10)
    assert vals[-1] > vals[0] and po.band_of(vals[-1]) == "Content", vals
    # one public work alone no longer pushes the realm to Prosperous (the Commons backing it adds +1),
    # and 6% tax no longer means Unrest
    c = _db(player_king=False)
    c.execute("INSERT INTO public_works (key, funded_at, expires_at) VALUES ('feast', ?, ?)", (T0, T0 + 60 * DAY))
    assert po.band_of(_days(c, 40)[-1]) in ("Calm", "Content")
    c = _db(player_king=False)
    c.execute("UPDATE realm_settings SET value = 0.06 WHERE key = 'sales_tax'")
    assert po.band_of(_days(c, 40)[-1]) == "Calm"


def test_clamp_and_bands():
    c = _db()
    assert po.set_mood(c, 150) == 100 and po.set_mood(c, -20) == 0
    assert po.band_of(14) == "Revolt" and po.band_of(15) == "Unrest" and po.band_of(85) == "Prosperous"
    assert po.band_of(34) == "Unrest" and po.band_of(35) == "Calm" and po.band_of(65) == "Content"


def test_crown_fee():
    c = _db()
    po.set_mood(c, 28)
    assert th.CROWN_FEE == 150_000
    assert po.crown_fee(c, th.CROWN_FEE) == 112_500    # Unrest: -25%
    po.set_mood(c, 5)
    c.execute("UPDATE houses SET stance = -50 WHERE key IN ('valcrest', 'ironhold')")
    assert po.crown_fee(c, th.CROWN_FEE) == 75_000     # capped at -50%
    po.set_mood(c, 50)
    assert po.crown_fee(c, th.CROWN_FEE) == 120_000    # two opposing houses alone: -20%


def test_prosperity():
    c = _db(balance=300_000, player_king=False)
    po.set_mood(c, 95)
    po.daily_mood_tick(c, T0, rng=random.Random(2))
    assert rt.balance(c) == 303_000
    c2 = _db(balance=5_000_000, player_king=False)
    po.set_mood(c2, 95)
    po.daily_mood_tick(c2, T0, rng=random.Random(2))
    assert rt.balance(c2) == 5_010_000
    assert c2.execute("SELECT COUNT(*) FROM treasury_ledger WHERE source = 'prosperity'").fetchone()[0] == 1
    assert c2.execute("SELECT COUNT(*) FROM royal_audit WHERE action = 'prosperity'").fetchone()[0] == 1


def test_pledges():
    c = _db()
    assert po.pledge(c, 5, "valcrest", T0)[0]
    assert not po.pledge(c, 5, "thornmere", T0 + 3 * DAY)[0]
    assert po.pledge(c, 5, "thornmere", T0 + 8 * DAY)[0]
    t = T0 + 9 * DAY
    assert po.errand_done(c, 5, "thornmere", t)[0]
    assert not po.errand_done(c, 5, "thornmere", t + 60)[0]
    assert not po.errand_done(c, 5, "valcrest", t + DAY)[0]
    assert ap.bank_get(c, 5) == po.ERRAND_COINS and po.pledge_of(c, 5)["favour"] == 10
    c.execute("UPDATE house_pledges SET favour = 495 WHERE player_id = 5")
    assert po.errand_done(c, 5, "thornmere", t + DAY)[0] and po.pledge_of(c, 5)["favour"] == 500
    assert po.title_suffix(c, 5) == "Champion of House Thornmere"
    before = po.stances(c)["thornmere"]
    assert po.support(c, 5, "support", t)[0] and not po.support(c, 5, "oppose", t + 60)[0]
    assert po.stances(c)["thornmere"] == before + 1


def test_court_events():
    c = _db(balance=50_000)
    rng = random.Random(3)
    assert po.roll_event(c, T0, rng, force=True)
    assert po.roll_event(c, T0, rng, force=True) is None          # one open at a time
    c.execute("DELETE FROM court_events")
    keys = []
    for i in range(12):
        po.roll_event(c, T0 + i, rng, force=True)
        ev = po.open_event(c)
        keys.append(ev["key"])
        c.execute("UPDATE court_events SET resolved_at = ? WHERE id = ?", (T0 + i, ev["id"]))
    for i in range(3, len(keys)):
        assert keys[i] not in keys[i - 3:i], keys
    # Valcrest event not drawn once he's freed
    c.execute("UPDATE throne SET old_king_state = 'freed' WHERE id = 1")
    c.execute("DELETE FROM court_events")
    assert all(e["key"] != "valcrest_release" for e in po._eligible_events(c))
    # unaffordable choice refused; treasury unchanged (cap: 20% of 50,000 = 10,000)
    c.execute("INSERT INTO court_events (event_key, opened_at) VALUES ('plague', ?)", (T0,))
    bal = rt.balance(c)
    assert not po.resolve(c, MONARCH, "healers", T0 + 10)[0] and rt.balance(c) == bal
    assert not po.event_payload(c, MONARCH, T0 + 10)["choices"][0]["ok"]
    # Chancellor only after 12h
    assert not po.resolve(c, CHANCELLOR, "ignore", T0 + 3600)[0]
    assert not po.resolve(c, NOBODY, "ignore", T0 + 13 * 3600)[0]
    assert po.resolve(c, CHANCELLOR, "ignore", T0 + 13 * 3600)[0]
    # 24h auto-ignore
    c.execute("INSERT INTO court_events (event_key, opened_at) VALUES ('flood', ?)", (T0,))
    m0 = po.mood(c)
    assert po.tick_events(c, T0 + 3600) is None
    assert po.tick_events(c, T0 + DAY + 1)[0]
    assert po.mood(c) == m0 - 5 and po.open_event(c) is None
    # NPC King answers at once with the first affordable non-ignore choice
    n = _db(balance=1_000_000, player_king=False)
    n.execute("INSERT INTO court_events (event_key, opened_at) VALUES ('flood', ?)", (T0,))
    assert po.tick_events(n, T0 + 1)[0]
    row = n.execute("SELECT choice FROM court_events").fetchone()
    assert row[0] == "relief" and rt.balance(n) == 980_000
    assert n.execute("SELECT COUNT(*) FROM royal_audit WHERE action = 'court_event'").fetchone()[0] == 1


def test_raids_rebuilt():
    import politics_live as pl

    class M:
        def __init__(self, mid, t, x, y, no_respawn=False):
            self.id, self.type, self.x, self.y, self.alive = mid, t, x, y, True

    class W:
        monsters, sessions, grid = {}, {}, None

    class Srv:
        WORLD = W()
        NPCS = []
        NPC_BY_ID = {}
        MonsterInstance = M
        _n = [0]

        @staticmethod
        def next_id():
            Srv._n[0] += 1
            return Srv._n[0]

    import world_map
    orig, orig_srv = world_map.is_walkable, pl._srv
    world_map.is_walkable = lambda g, x, y: True
    pl._srv = lambda: Srv
    try:
        c = _db()
        rid = po.schedule_raid(c, T0, rng=random.Random(1))
        assert po.schedule_raid(c, T0) is None                  # no duplicate raids
        first = pl.spawn_raid(rid, "north_road")
        assert len(first) == po.raid_size(rid) and pl.spawn_raid(rid, "north_road") == first
        pl._RAID_MONSTERS.clear()                                # simulated restart
        W.monsters.clear()
        again = pl.spawn_raid(rid, "north_road")
        assert len(W.monsters) == len(again) == po.raid_size(rid)
        pl.despawn_raid(rid)
        assert not W.monsters
        # protesters follow the band, never duplicated
        Srv.WORLD.db = type("D", (), {"conn": c})()

        async def nob(*a, **k):
            return None
        Srv.broadcast = staticmethod(nob)
        po.set_mood(c, 20)
        assert asyncio.run(pl.sync_protesters()) and not asyncio.run(pl.sync_protesters())
        assert sum(1 for n in Srv.NPCS if n["id"].startswith("protester_")) == 3
        po.set_mood(c, 40)
        asyncio.run(pl.sync_protesters())
        assert not any(n["id"].startswith("protester_") for n in Srv.NPCS)
    finally:
        world_map.is_walkable, pl._srv = orig, orig_srv
        pl._RAID_MONSTERS.clear()


def test_news():
    c = _db()
    for i in range(130):
        po.news(c, "t", f"line {i}", T0 + i)
    assert c.execute("SELECT COUNT(*) FROM politics_news").fetchone()[0] == 100
    got = po.latest_news(c)
    assert len(got) == 5 and got[0].endswith("line 129")


def test_throne_change_keeps_politics():
    c = _db()
    po.set_mood(c, 22)
    c.execute("UPDATE houses SET stance = 30 WHERE key = 'commons'")
    th._crown(c, 4, "conquest", "exiled", T0)
    assert po.mood(c) == 22 and po.stances(c)["commons"] == 30


def test_mood_multipliers():
    c = _db()
    po.set_mood(c, 70)
    assert po.shift_income_mult(c) == 1.05 and po.sales_tax_mult(c) == 1.05
    po.set_mood(c, 90)
    assert po.shift_income_mult(c) == 1.10
    po.set_mood(c, 50)
    assert po.shift_income_mult(c) == 1.0


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print("ok", name)
