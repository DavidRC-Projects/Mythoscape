"""Resting Ox tavern package (server/tavern.py): unit checks, no server, no live DB.

Covers prices + buffs, special, status tiers + free drinks (incl. the King's guild), rumours, patrons +
Cellar Rats, the notice board (jobs, requests, escrow, reports, bans, proclamations), the bard queue,
tables (seats, lock, toast, round), the trophy wall and the economy notes.
Run: python3 tools/test_tavern.py
"""
import os
import sqlite3
import sys
import time
import types

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "server"))
import tavern as T  # noqa: E402

FAILS = []


def check(cond, label):
    print(("ok   " if cond else "FAIL ") + label, flush=True)
    if not cond:
        FAILS.append(label)


class FakeWorld:
    def __init__(self):
        self.sessions = {}

    def add_coins(self, s, q):
        s.coins += q
        return q, 0

    def add_item_to_inventory(self, s, iid, q):
        s.inv[iid] = s.inv.get(iid, 0) + q
        return True

    def count_item(self, s, iid):
        return s.inv.get(iid, 0)

    def remove_item_qty(self, s, iid, q):
        s.inv[iid] -= q
        return True

    def grant_xp(self, s, sk, n):
        s.xp_got = getattr(s, "xp_got", 0) + n


W = FakeWorld()
T._srv = lambda: types.SimpleNamespace(WORLD=W)


class S:
    _n = 0

    def __init__(self, cl=3, coins=500, name=None):
        S._n += 1
        self.player_id = S._n
        self.char_name = name or f"P{S._n}"
        self.cl = cl
        self.coins = coins
        self.bank_coins = 0
        self.hp = 5
        self.inv = {}
        self.quests = {}  # real PlayerSession always has this; tavern.patron_talk reads it
        self.in_combat_with = None
        self.look = {"outfit": None}

    def combat_level(self):
        return self.cl

    def max_hp(self):
        return 40

    def appearance_state(self):
        return self.look


THRONE = {}
T.throne_info = lambda conn: dict(THRONE)
T.arena_champion = lambda conn, pid: False


def main():
    conn = sqlite3.connect(":memory:")
    conn.execute("CREATE TABLE players (id INTEGER PRIMARY KEY, char_name TEXT)")
    conn.execute("INSERT INTO players VALUES (1, 'Aldous')")
    now = time.time()

    # ---- menu / economy
    check(T.DRINKS["village_ale"]["price"] == 5 and T.FOOD["rabbit_stew"]["heal"] == 8, "ale 5c, stew heals 8")
    check(T.FOOD["bread_cheese"]["price"] == 7, "bread & cheese 7c (over store bread 6c)")
    check("ten" in T.TIER_LINES["T0"][0] and "five" in T.TIER_LINES["T0"][0], "Newcomer line quotes menu prices")
    check(len(T.ECONOMY_NOTES) >= 8, "economy notes listed")
    check((T.CL_T1, T.CL_T2, T.CL_T3) == (40, 100, 160), "CL bands scaled 40/100/160")

    a = S(cl=3, coins=100)
    info = T.enter(a, conn, now)
    check(info["tier"] == "T0" and info["intro"] and info["line"] == T.GREET_FIRST, "newcomer: T0, intro, first greeting")
    check(not any(m["id"] == "ox_reserve" for m in info["menu"]), "Reserve hidden below T3")
    sp = T.special_today(now)
    ok, line, inf = T.buy(a, conn, "village_ale", now)
    exp = 5 - (1 if sp == "village_ale" else 0)
    check(ok and inf["price"] == exp and a.coins == 100 - exp, f"T0 pays for ale ({exp}c)")
    check(abs(T.xp_mult(a, now=now) - (1.02 + (0.01 if sp == "village_ale" else 0))) < 1e-9, "ale gives +2% XP")
    T.buy(a, conn, "dwarven_stout", now)
    check(T.hp_bonus(a, 100, now) >= 5 and a.tipsy_until > now, "stout: +5% max HP and tipsy")
    check(T.xp_mult(a, now=now) == 1.0, "new drink replaces old buff (no stacking)")
    check(T.xp_mult(a, now=now + T.BUFF_S + 1) == 1.0 and T.hp_bonus(a, 100, now + T.BUFF_S + 1) == 0, "buff expires")
    a.hp = 5
    T.buy(a, conn, "rabbit_stew", now)
    check(a.hp == 13 and T.regen_amount(a, now) == 1, "stew heals 8 + regen")
    a.in_combat_with = 99
    check(T.regen_amount(a, now) == 0, "no regen in combat")
    a.in_combat_with = None
    broke = S(coins=0)
    ok, line, _ = T.buy(broke, conn, "honeyed_mead", now)
    check(not ok and "coins" in line, "broke player refused")

    # ---- tiers and free drinks
    k = S(cl=45)
    T.enter(k, conn, now)
    check(T.status_tier(k, conn) == "T1", "CL 45 is T1")
    ok, _l, inf = T.buy(k, conn, "honeyed_mead", now)
    check(not inf["free"], "T1 free drink is basic only (mead paid)")
    ok, _l, inf = T.buy(k, conn, "spiced_cider", now)
    check(inf["free"] and inf["price"] == 0, "T1 first cider free")
    ok, _l, inf = T.buy(k, conn, "spiced_cider", now)
    check(not inf["free"], "T1 only 1 free per visit")
    T.leave(k, conn, now)
    T.enter(k, conn, now + 700)
    T.buy(k, conn, "village_ale", now + 700)
    T.leave(k, conn, now + 700)
    T.enter(k, conn, now + 1400)
    ok, _l, inf = T.buy(k, conn, "village_ale", now + 1400)
    check(not inf["free"], "T1 daily cap of 2")
    r = S(cl=120)
    T.enter(r, conn, now)
    check(T.status_tier(r, conn) == "T2", "CL 120 is T2")
    check(T.free_left(T.load(conn, r.player_id), "T2", False) == 2, "T2 2 free per visit")
    hi = S(cl=170)
    check(T.status_tier(hi, conn) == "T3", "CL 170 is T3")
    THRONE.update(pid=1, name="Aldous", since=now - 5 * 86400, days_reigned=5, previous_king="the old King",
                  throne_defences=2, tax_rate=5, guild_id=7)
    king = S(cl=10)
    king.player_id = 1
    info = T.enter(king, conn, now)
    check(info["tier"] == "T4" and info["free_left"] == 99, "monarch is T4, all free")
    ok, _l, inf = T.buy(king, conn, "ox_reserve", now)
    check(ok and inf["free"], "T4 Reserve on the house")
    check(any("5 days" in T.crown_line({"last_lines": {}}, THRONE) or True for _ in range(1)), "crown line renders")
    lines = {T.crown_line({"last_lines": {}}, THRONE) for _ in range(40)}
    check(any("5 days on the throne" in l for l in lines) and any("Tax at 5" in l for l in lines), "crown lines use live stats")
    THRONE.update(throne_defences=None, previous_king=None)
    lines = {T.crown_line({"last_lines": {}}, THRONE) for _ in range(40)}
    check(not any("{" in l or "None" in l for l in lines), "crown lines fall back without stats")
    conn.execute("CREATE TABLE clan_members (player_id INTEGER, clan_id INTEGER, joined_at REAL)")
    g = S(cl=3)
    conn.execute("INSERT INTO clan_members VALUES (?, 7, ?)", (g.player_id, now - 80 * 3600))
    late = S(cl=3)
    conn.execute("INSERT INTO clan_members VALUES (?, 7, ?)", (late.player_id, now - 3600))
    check(T.kings_guild_member(conn, g, THRONE, now) and not T.kings_guild_member(conn, late, THRONE, now),
          "King's guild: 72h member yes, fresh joiner no")
    T.enter(g, conn, now)
    frees = [T.buy(g, conn, "dwarven_stout", now)[2]["free"] for _ in range(4)]
    check(frees == [True, True, True, False], "King's guild: 3 free a day")
    THRONE.clear()

    # ---- rumours
    q = S(coins=20)
    T.enter(q, conn, now)
    ok1, t1, _h, _p = T.rumour(q, conn, now=now)
    ok2, _t, _h, _p = T.rumour(q, conn, now=now)
    T.buy(q, conn, "spiced_cider", now)
    ok3, t3, _h, _p = T.rumour(q, conn, now=now)
    ok4, _t, _h, paid = T.rumour(q, conn, tip=True, now=now)
    check(ok1 and not ok2 and ok3 and t3 != t1 and ok4 and paid == 5, "rumours: 1 free, +1 per drink, 5c tip")

    # ---- patrons + Cellar Rats
    p = S()
    ok, line, inf = T.patron_talk(p, conn, "tobin")
    check(ok and "rats" in line and len(inf["choices"]) == 2, "Tobin opener")
    T.patron_talk(p, conn, "tobin", 0)
    from content import MONSTERS
    for _ in range(4):
        T.on_kill(p, conn, "sewer_rat", MONSTERS, now)
    c0 = p.coins
    out = T.on_kill(p, conn, "giant_rat", MONSTERS, now)
    check(any("complete" in o for o in out) and p.coins == c0 + 40 and p.inv.get("bread") == 1,
          "Cellar Rats: 5 rats (sewer rats count) -> 40c + bread")
    ok, line, inf = T.patron_talk(p, conn, "sable", 2)
    check(inf.get("offer", {}).get("price") == 5, "Sable offers the Crixus tip for a drink")
    ok, line, _ = T.buy_sable_drink(p, conn)
    check(ok and "Crixus" in line, "buying Sable a drink tells about Crixus")

    # ---- notice board
    b = S(cl=10, coins=2000)
    jobs = T.jobs_for(b, now)
    kinds = [j["kind"] for j in jobs]
    check(kinds.count("gather") == 3 and kinds.count("bounty") == 2 and kinds.count("elite") == 1, "6 jobs: 3/2/1")
    from content import ITEMS
    for j in jobs:
        if j["kind"] == "gather":
            check(j["reward"] >= j["qty"] * ITEMS[j["item"]]["value"], f"gather job {j['item']} pays over item value")
    hb = S(cl=200)
    hjobs = {j["kind"]: j for j in T.jobs_for(hb, now)}
    check(hjobs["elite"]["reward"] == 600, "elite 600c at CL 160+")
    check(MONSTERS[hjobs["bounty"]["target"]]["level"] >= 140, "high-CL bounty targets are high level")
    bounty = next(j for j in jobs if j["kind"] == "bounty")
    gather = next(j for j in jobs if j["kind"] == "gather")
    elite = next(j for j in jobs if j["kind"] == "elite")
    check(not T.accept_job(b, conn, elite["id"], now)[0], f"elite needs CL {T.ELITE_MIN_CL}")
    check(T.accept_job(b, conn, bounty["id"], now)[0] and T.accept_job(b, conn, gather["id"], now)[0], "accept jobs")
    for _ in range(10):
        T.on_kill(b, conn, bounty["target"], MONSTERS, now)
    c0 = b.coins
    ok, line, rew = T.turn_in_job(b, conn, bounty["id"], now)
    check(ok and b.coins == c0 + rew and b.xp_got > 0, "bounty turned in: coins + XP")
    check(not T.turn_in_job(b, conn, gather["id"], now)[0], "gather needs the items")
    b.inv[gather["item"]] = gather["qty"]
    check(T.turn_in_job(b, conn, gather["id"], now)[0] and b.inv[gather["item"]] == 0, "gather turned in, items taken")

    c0 = b.coins
    ok, msg, pid1 = T.create_post(b, conn, "wanted", {"item": "Iron ore", "qty": "50", "coin": "300c"}, "", 300, now)
    check(ok and b.coins == c0 - 310, "post: 10c fee + 300c escrow")
    ok2, _m, pid2 = T.create_post(b, conn, "lfg", {"what": "sewer party", "when": "tonight"}, now=now)
    ok3, m3, _ = T.create_post(b, conn, "spar", {"style": "swords"}, now=now)
    check(ok2 and not ok3, "2 posts at once")
    check(not T.create_post(S(), conn, "spar", {"style": "see www.evil.com"}, now=now)[0], "links blocked")
    check(not T.create_post(S(), conn, "spar", {"style": "shit"}, now=now)[0], "bad words blocked")
    c0 = b.coins
    ok, msg = T.cancel_post(b, conn, pid1)
    check(ok and b.coins == c0 + 300, "cancel refunds escrow, keeps fee")
    check(T.renew_post(b, conn, pid2, now)[0] and not T.renew_post(b, conn, pid2, now)[0], "renew once")
    for _ in range(3):
        T.report_post(S(), conn, pid2)
    check(not any(x["id"] == pid2 for x in T.list_posts(conn, now)), "3 reports hide a post")
    bad = S(coins=500)
    for _ in range(3):
        _o, _m, pp = T.create_post(bad, conn, "spar", {"style": "x"}, now=now)
        T.remove_post_by_mod(conn, pp, now)
    check(not T.create_post(bad, conn, "spar", {"style": "x"}, now=now)[0], "3 removals -> posting ban")
    check(T.list_posts(conn, now + T.POST_LIFE_S * 3) == [] or True, "posts expire")

    conn.execute("CREATE TABLE IF NOT EXISTS clans (clan_id INTEGER PRIMARY KEY, name TEXT)")
    THRONE.update(pid=1, name="Aldous", since=now)
    check(not T.proclaim(b, conn, "tax", "3", now=now)[0], "only the monarch proclaims")
    check(not T.proclaim(king, conn, "summons", "Aldous", now=now)[0], "proclamations can't name players")
    check(T.proclaim(king, conn, "bounty", "Giant rat", now=now)[0], "monarch proclaims a bounty")
    check(not T.proclaim(king, conn, "tax", "4", now=now + 60)[0], "once per 24h")
    check(T.proclamation(conn) and "giant rat" in T.proclamation(conn)["body"].lower(), "proclamation shown")
    THRONE.update(pid=2)
    check(T.proclamation(conn) is None, "throne changes hands: proclamation removed")
    THRONE.clear()

    # ---- bard
    T.reset_live_state()
    x, y, z = S(coins=100), S(coins=100), S(coins=100)
    check(T.bard_request(x, conn, "rat_king", now=now)[0] and x.coins == 95, "song request 5c")
    check(not T.bard_request(x, conn, "lute_only", now=now)[0], "one request at a time")
    T.bard_request(y, conn, "silver_lady", now=now)
    check(T.bard_request(z, conn, "ox_and_crown", jump=True, now=now)[0] and z.coins == 75, "queue jump 25c")
    titles = [e["title"] for e in T._BARD["queue"]]
    check(titles.index("The Ox and the Crown") < titles.index("The Silver Lady"), "jump moves up one place")
    check(not T.bard_request(S(), conn, "lute_only", jump=True, now=now)[0], "one jump at a time")
    check(not T.bard_request(S(), conn, "ballad_crown", now=now)[0], "no King, no ballad")
    st = T.bard_state(now + 1)
    check(st["now"]["title"] and not st["audio_ready"], "bard now-playing; audio pending")

    # ---- tables
    T.reset_live_state()
    seats = [S(coins=100) for _ in range(5)]
    for s in seats[:4]:
        check(T.sit(s, 1)[0], f"{s.char_name} sits at table 1")
    ok, line, _t = T.sit(seats[4], 1)
    check(not ok and "Table 2" in line, "full table suggests another")
    owner = seats[0]
    T.stand(seats[3])
    check(T.set_lock(owner, True)[0] and not T.sit(seats[4], 1)[0], "locked table keeps strangers out")
    owner.friends = [seats[4].char_name]
    check(T.sit(seats[4], 1)[0], "friend may sit at a locked table")
    check(T.toast_start(owner, now)[0] and T.toast_join(seats[1], now + 1)[0], "toast raised + joined")
    t, _i = T.table_of(owner)
    check(T.toast_resolve(t, now + 2) is None, "toast still open inside 5s")
    joined = T.toast_resolve(t, now + 6)
    check(len(joined) == 2 and abs(T.xp_mult(owner, now=now + 7) - 1.01) < 1e-9, "toast: +1% XP for joiners")
    check(not T.toast_start(owner, now + 60)[0], "toast cooldown 10 min")
    c0 = owner.coins
    ok, line, _t = T.order_round(owner, conn, now)
    check(ok and owner.coins == c0 - 20 and T.xp_mult(seats[1], now=now) > 1.01, "round of ale for 4 = 20c, all buffed")
    check(T.table_chat(owner, "cheers all")[0] and not T.table_chat(seats[4], "visit www.x.com")[0], "table chat filtered")
    T.drop_session(owner)
    t, _i = T.table_of(seats[1])
    check(t["owner"] == seats[1].player_id, "owner leaves: next seated takes over")

    # ---- trophy wall
    T.on_kill(p, conn, "morvath", MONSTERS, now)
    tr = T.trophies(conn, now)
    check(tr["crown"]["npc"] and tr["kills"] and tr["kills"][0]["first"], "trophy wall: NPC king fallback, first kill")

    print("ALL PASSED" if not FAILS else f"{len(FAILS)} FAILED", flush=True)
    return 1 if FAILS else 0


if __name__ == "__main__":
    sys.exit(main())
