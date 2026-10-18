"""Balance pass (BALANCE_REVIEW.md changes 1-7). Run: python3 tools/test_balance.py"""
import asyncio
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "server"))
sys.path.insert(0, os.path.join(ROOT, "tools"))
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

import apprentice as ap  # noqa: E402
import clans  # noqa: E402
import nobility as nb  # noqa: E402
import politics as po  # noqa: E402
import property as prop  # noqa: E402
import reputation as rep  # noqa: E402
import ruling as ru  # noqa: E402
import throne as th  # noqa: E402
import test_throne as tt  # noqa: E402

DAY = 86400


def test_social_xp_and_requirements():
    assert (rep.ETIQUETTE_TAX_XP, rep.ETIQUETTE_FEE_XP, rep.ETIQUETTE_FEE_DAILY_CAP) == (150, 300, 2_500)
    assert (ap.ETIQUETTE_PER_SHIFT, rep.ETIQUETTE_WEEKLY_XP, nb.ETIQUETTE_PROMOTION_XP) == (40, 1_500, 2_000)
    assert (rep.CHARISMA_QUEST_XP, rep.CHARISMA_TALK_XP, clans.CHARISMA_TUTORIAL_XP) == (300, 40, 600)
    assert (ru.COUNSEL_XP, po.ERRAND_CHARISMA) == (150, 100)
    import content
    assert content.QUESTS["guild_basics"]["rewards"]["charisma_xp"] == 600
    assert [(r[1], r[2]) for _k, r in sorted(nb.REQUIREMENTS.items())] == [(10, 5), (20, 15), (35, 30), (50, 45),
                                                                          (65, 55)]
    assert (th.COURTIER_MIN_ETIQUETTE, th.COURTIER_MIN_CHARISMA) == (55, 55)
    # Courtier's Path opens at 55/55
    c = tt._db()
    s = tt._sess(pid=2, gender="female", rank=3, lvl=55)
    assert th.courtier_eligible(s, c)[0]
    s.level = lambda sk: 54
    ok, missing = th.courtier_eligible(s, c)
    assert not ok and "Etiquette 55" in missing and "Charisma 55" in missing


def test_property_payback():
    assert prop.WORKER_VALUE == 110
    assert ru.SETTINGS["land_fee_farm"][:3] == (300, 150, 600)
    assert ru.SETTINGS["land_fee_workshop"][:3] == (450, 225, 900)
    net = int((prop.WORKER_VALUE - prop.WORKER_WAGE) * 0.95)
    assert net == 76
    assert 2 * 8 * net - 300 == 916 and 3 * 8 * net - 450 == 1_374     # per day (farm, workshop)


def test_castle_fee_and_cooldown():
    import castle_owners
    deed = int(castle_owners.castle_row("white_rose")["deed_price"])
    assert th.castle_fee("white_rose") == round(deed * 0.01) >= 250_000
    c = tt._db()
    cid = tt._ready_guild(c)
    c.execute("UPDATE clans SET challenge_castle_id = 'white_rose' WHERE clan_id = ?", (cid,))
    ap.bank_set(c, 1, 10**7)
    allc = ["gothic", "white_rose", "sky_anchor", "king"]
    s = tt._sess()
    assert th.schedule_castle(s, c, 24, tt.T0, owned_castles=allc[:3], all_castles=allc)[0]
    assert ap.bank_get(c, 1) == 10**7 - th.castle_fee("white_rose")
    c.execute("UPDATE challenges SET status = 'loss'")           # that battle is over
    ok, msg = th.schedule_castle(s, c, 24, tt.T0 + 2 * DAY, owned_castles=allc[:3], all_castles=allc)
    assert not ok and "challenged again in" in msg, msg
    assert th.schedule_castle(s, c, 24, tt.T0 + 8 * DAY, owned_castles=allc[:3], all_castles=allc)[0]


def test_crown_and_acclaim_fees():
    assert th.CROWN_FEE == 150_000 and th.ACCLAIM_FEE == 100_000


def _tie_db(mood, opposing=0):
    c = tt._db()
    po.ensure_schema(c)
    c.execute("UPDATE players SET reputation = 1000 WHERE id IN (3, 4)")
    th._crown(c, 3, "conquest", "imprisoned", tt.T0)
    po.set_mood(c, mood)
    keys = list(po.HOUSES)[:opposing]
    for k in keys:
        c.execute("UPDATE houses SET stance = -50 WHERE key = ?", (k,))
    th.add_favour(c, 4, 1000)
    ap.bank_set(c, 4, 10**6)
    assert th.schedule_acclaim(tt._sess(pid=4, gender="female", rank=3, score=1000), c, 12, tt.T0)[0]
    return c


def test_acclaim_tie_break():
    c = _tie_db(60)
    assert th.resolve_acclaim(c, th.scheduled(c)[0], tt.T0 + 13 * 3600)["result"] == "loss"
    c = _tie_db(40)
    assert th.resolve_acclaim(c, th.scheduled(c)[0], tt.T0 + 13 * 3600)["result"] == "win"
    c = _tie_db(60, opposing=2)
    assert th.resolve_acclaim(c, th.scheduled(c)[0], tt.T0 + 13 * 3600)["result"] == "win"


def test_mood_damping():
    assert (po.PULL_RATE, po.TAX_DRIFT_PER_PCT, po.WORK_DRIFT, po.FEE_DRIFT_MULT * po.FEE_DRIFT) == (0.15, 1.0, 1, 5)


def _server():
    import database
    database.Database.__init__.__defaults__ = (":memory:",)
    import server
    return server


def test_small_trades_do_not_count():
    server = _server()
    W = server.WORLD
    W.db.create_account("baltax", "pw", "Baltax")
    s = server.PlayerSession(_WS(), W.db.get_player_by_username("baltax"))
    rep0, xp0 = s.reputation, s.xp.get("etiquette", 0)
    for _ in range(5):
        asyncio.run(server._pay_royal_tax(s, "shop_buy", 1))
    assert (s.reputation, s.xp.get("etiquette", 0)) == (rep0, xp0)
    asyncio.run(server._pay_royal_tax(s, "shop_buy", 5))
    assert s.reputation == rep0 + 1 and s.xp.get("etiquette", 0) == xp0 + rep.ETIQUETTE_TAX_XP


class _WS:
    async def send(self, raw):
        pass


def test_guild_bank_castle_deed():
    server = _server()
    import castle_owners
    W = server.WORLD
    conn = W.db.conn
    castle_owners.ensure_schema(conn)
    clans._CONN = conn
    W.db.create_account("balking", "pw", "Balking")
    s = server.PlayerSession(_WS(), W.db.get_player_by_username("balking"))
    ap.bank_set(conn, s.player_id, clans.CHARTER_COST)
    ok, msg, cid = clans.create_core(s.player_id, "Bal Guild")
    assert ok, msg
    deed = int(castle_owners.castle_row("sky_anchor")["deed_price"])
    conn.execute("UPDATE clans SET bank_coins = ? WHERE clan_id = ?", (deed + 5, cid))
    s.bank_coins = 0
    assert castle_owners.can_buy(s, "sky_anchor") == "guild"
    seller = castle_owners.load()["by_castle"]["sky_anchor"]
    assert asyncio.run(castle_owners.buy(s, seller)) == "buy_success"
    own = castle_owners.owners(conn)["sky_anchor"]
    assert own["owner_id"] == s.player_id and own["guild_id"] == cid
    assert clans.bank_balance(cid) == 5 and s.bank_coins == 0
    assert "sky_anchor" in th._castle_owned_by(conn, s.player_id)      # counts for the Crown Challenge
    # a non-leader can't spend the guild bank
    W.db.create_account("balmember", "pw", "Balmember")
    m = server.PlayerSession(_WS(), W.db.get_player_by_username("balmember"))
    clans.join_core(m.player_id, cid)
    conn.execute("UPDATE clans SET bank_coins = ? WHERE clan_id = ?", (10**9, cid))
    m.bank_coins = 0
    assert castle_owners.can_buy(m, "white_rose") == "funds"


def test_male_tier5_rule():
    import json
    with open(os.path.join(ROOT, "..", "player_hd", "assets", "catalogue.json"), encoding="utf-8") as fh:
        cat = json.load(fh)
    rule = {"rank": 4, "rep": "Revered", "challenge_guild": True}
    assert cat["sets"]["set_kings_champion"]["unlock"] == rule
    assert all(i["unlock"] == rule for i in cat["items"] if i.get("set") == "set_kings_champion")


if __name__ == "__main__":
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    for fn in tests:
        fn()
        print("ok", fn.__name__)
    print(f"ALL {len(tests)} BALANCE TESTS PASSED")
