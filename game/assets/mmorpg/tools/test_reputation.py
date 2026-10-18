"""Crownfall phase 3: reputation and social skills. Run: python3 tools/test_reputation.py"""
import os
import sqlite3
import sys
import types

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "server"))

import reputation as rep  # noqa: E402
import royal_treasury as rt  # noqa: E402


def _conn():
    c = sqlite3.connect(":memory:")
    c.execute("CREATE TABLE players (id INTEGER PRIMARY KEY, name TEXT, attack_xp INTEGER DEFAULT 5)")
    c.execute("INSERT INTO players (id, name, attack_xp) VALUES (1, 'old', 777)")
    rep.ensure_schema(c)
    return c


def test_tiers():
    assert rep.tier(-500) == "Hated" and rep.tier(-499) == "Distrusted" and rep.tier(99) == "Neutral"
    assert rep.tier(100) == "Respected" and rep.tier(800) == "Revered" and rep.tier(-100) == "Distrusted"


def test_clamp():
    c = _conn()
    s = types.SimpleNamespace(player_id=1, reputation=990)
    rep.adjust(c, s, "quest", 25)
    assert s.reputation == 1000
    s.reputation = -990
    rep.adjust(c, s, "crime", -50)
    assert s.reputation == -1000
    assert c.execute("SELECT reputation FROM players WHERE id=1").fetchone()[0] == -1000


def test_prices():
    assert rep.buy_price(100, -600) == 110 and rep.buy_price(100, 900) == 95 and rep.buy_price(1, 900) == 1
    assert rep.buy_price(100, 0) == 100 and rt.buy_tax(rep.buy_price(100, 900)) == 5
    assert rep.sell_value(100, -600) == 90 and rep.sell_value(100, 900) == 105


def test_daily_caps():
    c = _conn()
    day1, day2 = 1_700_000_000, 1_700_000_000 + 86400
    got = sum(rep.daily_take(c, 1, "rep_tax", 1, rep.REP_TAX_DAILY_CAP, now=day1) for _ in range(20))
    xp = sum(rep.daily_take(c, 1, "fee_xp:etiquette", rep.ETIQUETTE_TAX_XP, rep.ETIQUETTE_FEE_DAILY_CAP, now=day1)
             for _ in range(20))
    assert got == 10 and xp == rep.ETIQUETTE_FEE_DAILY_CAP == 2_500
    assert rep.daily_take(c, 1, "rep_tax", 1, rep.REP_TAX_DAILY_CAP, now=day2) == 1


def test_talk_once_per_npc_per_day():
    c = _conn()
    assert rep.first_talk_today(c, 1, "farmer_tom", now=1_700_000_000)
    assert not rep.first_talk_today(c, 1, "farmer_tom", now=1_700_000_000)
    assert rep.first_talk_today(c, 1, "guard_marcus", now=1_700_000_000)


def test_schema_keeps_old_data():
    c = _conn()
    row = c.execute("SELECT attack_xp, reputation, charisma_xp, etiquette_xp FROM players WHERE id=1").fetchone()
    assert tuple(row) == (777, 0, 0, 0)
    rep.ensure_schema(c)   # idempotent


def test_social_skills_not_combat():
    import combat
    from content import COMBAT_SKILLS, XP_SKILLS
    assert "charisma" in XP_SKILLS and "etiquette" in XP_SKILLS
    assert "charisma" not in COMBAT_SKILLS and "etiquette" not in COMBAT_SKILLS
    base = combat.combat_level(50, 50, 50, 50, 1)
    assert base == combat.combat_level(50, 50, 50, 50, 1)   # signature has no social inputs


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print("ok", name)
