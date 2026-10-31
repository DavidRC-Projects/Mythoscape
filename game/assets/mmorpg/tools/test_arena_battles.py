"""Arena battles: bosses, renown/deed, ranked seasons, crowd, gear, rival rosters.
Run: python3 tools/test_arena_battles.py (in-memory DB only)."""
import os
import random
import sqlite3
import sys
import time
import types

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "server"))

import combat  # noqa: E402
import mercenaries as merc  # noqa: E402
import arena_battles as ab  # noqa: E402
from content import ITEMS  # noqa: E402


def _conn():
    c = sqlite3.connect(":memory:")
    c.row_factory = sqlite3.Row
    c.execute("CREATE TABLE players (id INTEGER PRIMARY KEY, coins INTEGER DEFAULT 0, bank_coins INTEGER DEFAULT 0,"
              " command_xp INTEGER DEFAULT 0, reputation INTEGER DEFAULT 0, noble_rank INTEGER DEFAULT 0)")
    for pid in (1, 2):
        c.execute("INSERT INTO players (id, coins) VALUES (?, 500000)", (pid,))
    c.execute("CREATE TABLE rep_log (id INTEGER PRIMARY KEY AUTOINCREMENT, ts REAL, player_id INTEGER,"
              " source TEXT, delta INTEGER)")
    merc.ensure_schema(c)
    return c


def _session(pid=1, cmd=99):
    xp = {"command": combat.xp_for_level(cmd), "smithing": 0}
    return types.SimpleNamespace(player_id=pid, coins=10_000_000, bank_coins=0, xp=xp, reputation=0,
                                 char_name=f"Tester{pid}", arena_match=None,
                                 level=lambda s: combat.level_from_xp(int(xp.get(s) or 0)))


def _army(c, s, tmpl="mythos_guard", n=10):
    for _ in range(n):
        ok, msg, _ = merc.recruit(c, s, tmpl)
        assert ok, msg
    c.execute("UPDATE mercenary_roster SET attack_xp=?, strength_xp=?, defence_xp=?, hitpoints_xp=?, gear_tier='mythos'",
              (combat.xp_for_level(99),) * 4)
    c.commit()


def _run(match, cap=400):
    merc.begin_live_fight(types.SimpleNamespace(arena_match=match))
    evs = []
    for _ in range(cap):
        evs += merc.tick_live_match(match)
        if match["phase"] == "done":
            break
    return evs


def test_boss_per_tier_and_unlock():
    assert sorted(ab.BOSSES) == [1, 2, 3, 4, 5, 6]
    names = {b["name"] for b in ab.BOSSES.values()}
    assert len(names) == 6
    for b in ab.BOSSES.values():
        p = os.path.join(ROOT, "client/assets/castle_realm/arena/bosses", b["id"])
        for tag in ("1x", "2x"):
            for f in "senw":
                assert os.path.isfile(os.path.join(p, tag, f + ".png")), (b["id"], tag, f)
    c, s = _conn(), _session()
    _army(c, s)
    ok, err, _ = merc.validate_practice(c, s, "boss:1")
    assert not ok and "first" in err.lower()
    merc.set_practice_highest(c, 1, 1)
    ok, err, entry = merc.validate_practice(c, s, "boss:1")
    assert ok, err
    assert entry["boss"]["id"] == "varro"


def test_boss_match_staging_and_abilities():
    random.seed(3)
    c, s = _conn(), _session()
    _army(c, s, "levy", 10)
    merc.set_practice_highest(c, 1, 6)
    for tier in range(1, 7):
        s.arena_match = None
        c.execute("UPDATE practice_progress SET fights_today=0")
        ok, msg, m = merc.start_live_practice(c, s, f"boss:{tier}")
        assert ok, msg
        # Boss fights are one-on-one duels: the commander alone vs the champion.
        assert m["mode"] == "duel"
        foes = [u for u in m["units"] if u["side"] == "foe"]
        yours = [u for u in m["units"] if u["side"] == "you"]
        bosses = [u for u in foes if u.get("boss")]
        assert len(foes) == 1 and len(bosses) == 1 and len(yours) == 1 and yours[0]["duel_player"]
        assert bosses[0]["template_id"] == f"gladiator_{ab.BOSSES[tier]['id']}"
        hud = merc.match_hud(m)
        assert hud["boss"]["name"] == ab.BOSSES[tier]["name"] and "crowd" in hud and "duel" in hud
        assert merc.unit_public(bosses[0])["boss"] is True
        merc.begin_live_fight(s)
        evs = []
        for _ in range(400):
            evs += merc.tick_live_match(m)
            if m["phase"] == "done":
                break
        assert m["phase"] == "done"
        assert any(e.get("type") == "ARENA_DUEL" for e in evs), tier
        assert any("Announcer" in line for line in m["log"])


def test_net_cast_stuns():
    c, s = _conn(), _session()
    _army(c, s, "levy", 10)
    merc.set_practice_highest(c, 1, 1)
    ok, _, m = merc.start_live_practice(c, s, "boss:1")
    merc.begin_live_fight(s)
    boss = next(u for u in m["units"] if u.get("boss"))
    boss["boss_cd"] = 0
    ev = []
    ab.on_tick(m, ev)
    assert any(u.get("stun") == 3 for u in m["units"] if u["side"] == "you")


def test_second_wind_once():
    c, s = _conn(), _session()
    _army(c, s, "levy", 10)
    merc.set_practice_highest(c, 1, 6)
    ok, _, m = merc.start_live_practice(c, s, "boss:6")
    boss = next(u for u in m["units"] if u.get("boss"))
    boss["hp"] = boss["max_hp"] // 5
    ab.on_tick(m, [])
    assert boss["hp"] == int(boss["max_hp"] * 0.75) and boss["second_wind_used"]
    boss["hp"] = 5
    ab.on_tick(m, [])
    assert boss["hp"] == 5


def _win_boss(c, s, tier):
    s.arena_match = None
    c.execute("UPDATE practice_progress SET fights_today=0")
    ok, msg, m = merc.start_live_practice(c, s, f"boss:{tier}")
    assert ok, msg
    m["phase"] = "done"
    m["won"] = True
    m["crowd"] = 90
    return merc.settle_live_practice(c, s, m)


def test_renown_feeds_standing_and_gear_drop():
    c, s = _conn(), _session()
    _army(c, s)
    merc.set_practice_highest(c, 1, 6)
    text, summ = _win_boss(c, s, 3)
    assert summ["boss_first_clear"] and summ["renown_gain"] >= ab.RENOWN_BOSS_FIRST * 3
    assert s.reputation == summ["renown"] * ab.RENOWN_TO_REPUTATION
    assert summ["gear_drop"]["item_id"] == "thraex_greaves"
    assert "thraex_greaves" in ITEMS and ITEMS["thraex_greaves"]["equip_slot"] == "legs"
    assert summ["crowd_purse"] > 0
    assert "renown" in text
    # standing counts for nobility petitions (reputation tier)
    import reputation
    _win_boss(c, s, 4)
    assert reputation.tier(s.reputation) in ("Respected", "Honoured", "Revered")
    _, summ2 = _win_boss(c, s, 3)
    assert not summ2["boss_first_clear"]
    for iid in ab.GLADIATOR_ITEMS:
        assert os.path.isfile(os.path.join(ROOT, "assets/items/realistic", iid + ".png")), iid
        assert ITEMS[iid].get("art_as") in ITEMS


def test_top_tier_grants_deed():
    c, s = _conn(), _session()
    _army(c, s)
    merc.set_practice_highest(c, 1, 6)
    import housing
    housing.ensure_schema(c)
    _, summ = _win_boss(c, s, 6)
    deed = summ["deed"]
    assert deed["kind"] in ("deed", "gold")
    if deed["kind"] == "deed":
        assert housing.owned_house_key(c, 1) == deed["house_key"]
    import player_houses
    assert player_houses.has_house(c, 1)
    _, again = _win_boss(c, s, 6)
    assert "deed" not in again


def test_ranked_rival_elo_and_saved_roster():
    c = _conn()
    a, b = _session(1), _session(2)
    _army(c, a, "levy", 5)
    _army(c, b, "levy", 5)
    ab.save_roster(c, b)
    riv = ab.rivals(c, 1)
    assert riv and riv[0]["id"] == "rival:2"
    ok, err, _ = merc.validate_practice(c, a, "rival:1")
    assert not ok
    ok, msg, m = merc.start_live_practice(c, a, "rival:2")
    assert ok, msg
    foes = [u for u in m["units"] if u["side"] == "foe"]
    assert len(foes) == 5 and m["entry"]["ranked"]
    m["phase"] = "done"
    m["won"] = True
    _, summ = merc.settle_live_practice(c, a, m)
    assert summ["elo"]["delta"] > 0 and summ["elo"]["after"] == ab.ladder(c, 1)["rating"]
    assert ab.leaderboard(c)[0]["player_id"] == 1
    assert c.execute("SELECT 1 FROM arena_saved_roster WHERE player_id=1").fetchone()


def test_weekly_season_reset_and_reward():
    c, s = _conn(), _session()
    ab.ladder(c, 1)
    c.execute("UPDATE arena_ladder SET rating=1500, wins=9, losses=1, season='2020-W01' WHERE player_id=1")
    c.commit()
    lad = ab.ladder(c, 1)
    assert lad["rating"] == 1250 and lad["wins"] == 0 and lad["season"] == ab.season_key()
    paid = ab.pay_season_rewards(c, s)
    assert paid and paid[0]["band"] == "Silver" and s.bank_coins == 25_000
    assert ab.pay_season_rewards(c, s) == []
    assert ab.season_key(0) == "1970-W01" and ab.season_ends() > time.time()


def test_crowd_meter_moves():
    c, s = _conn(), _session()
    _army(c, s)
    ok, _, m = merc.start_live_practice(c, s, "squire_alden")
    assert m["crowd"] == ab.CROWD_START
    _run(m)
    assert m["crowd"] != ab.CROWD_START
    assert merc.match_hud(m)["announce"]


def test_payload_has_arena_block():
    c, s = _conn(), _session()
    s.level = lambda sk: 1
    p = ab.payload(c, s)
    assert len(p["bosses"]) == 6 and "ladder" in p and "rivals" in p and p["renown_title"] == "Tiro"


def _realm_map():
    import json
    from pathlib import Path
    base = Path(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))) / "client" / "assets" / "castle_realm"
    return (json.loads((base / "json" / "castle_realm_map.json").read_text()),
            json.loads((base / "arena" / "meta.json").read_text()))


def test_arena_stands_block_and_npcs_reachable():
    from collections import deque
    d, _meta = _realm_map()
    rows, legend = d["rows"], d["legend"]
    assert legend["W"]["walkable"] is False
    walk = {k for k, v in legend.items() if v.get("walkable")}
    # stand tiles north/east/west of the ring are blocked; ring + pit stay walkable
    for t in ((196, 104), (172, 128), (220, 128), (180, 146)):
        assert rows[t[1]][t[0]] == "W", t
    assert rows[128][196] == "s" and rows[110][196] == "A"
    sp = d["spawn"]
    start = (int(sp["x"]), int(sp["y"])) if isinstance(sp, dict) else tuple(sp)
    seen, q = {start}, deque([start])
    while q:
        x, y = q.popleft()
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            n = (x + dx, y + dy)
            if n not in seen and 0 <= n[1] < len(rows) and 0 <= n[0] < len(rows[0]) and rows[n[1]][n[0]] in walk:
                seen.add(n); q.append(n)
    for t in ((188, 147), (196, 147), (196, 148), (196, 128)):
        assert t in seen, t


def test_pond_clear_of_arena_art():
    d, meta = _realm_map()
    x0, y0, x1, y1 = meta["hd"]["art_tiles"]
    pond = [(x, y) for y, r in enumerate(d["rows"]) for x, c in enumerate(r) if c == "~" and 150 < x < 245 and 80 < y < 180]
    assert len(pond) >= 100
    assert not [p for p in pond if x0 - 0.5 <= p[0] <= x1 and y0 <= p[1] <= y1 and not (p[0] > 222 or p[1] > 158)]


def test_client_boss_draw_frames_and_no_monkeypatch():
    os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
    import pygame
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    sys.path.insert(0, os.path.join(root, "client"))
    pygame.init(); pygame.display.set_mode((64, 64))
    import arena_battles_ui as ui
    assert not hasattr(ui, "install")
    src = open(os.path.join(root, "client", "client.py"), encoding="utf-8").read()
    assert "arena_battles_ui.draw_boss(" in src and "draw_boss_plate" in src
    scr = pygame.Surface((400, 400), pygame.SRCALPHA)
    for bid in ("varro", "brutus", "crixus", "sabina", "ignatius", "unbroken"):
        m = {"boss_id": bid, "side": "foe", "name": bid, "hp": 5, "max_hp": 10, "level": 50}
        top = ui.draw_boss(scr, m, 200, 350, 44, 0.3, "idle", 0, 0, "s")
        assert top is not None and 350 - top > 44 * 2.5, (bid, top)
        walk = {ui.boss_frame(bid, f, 44, "walk", k)[0].get_bounding_rect().h for f in "nesw" for k in range(4)}
        assert walk and ui.boss_frame(bid, "e", 44, "walk", 1)[0] is not ui.boss_frame(bid, "e", 44, "walk", 0)[0]
        assert ui.boss_frame(bid, "e", 44, "melee", 1) is not None
    assert ui.draw_boss(scr, {"boss_id": "nobody"}, 200, 350, 44, 0, "idle", 0, 0, "s") is None


if __name__ == "__main__":
    fails = 0
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            try:
                fn()
                print("ok", name)
            except Exception as exc:
                fails += 1
                import traceback
                traceback.print_exc()
                print("FAIL", name, exc)
    print("ALL PASSED" if not fails else f"{fails} FAILED")
    sys.exit(1 if fails else 0)
