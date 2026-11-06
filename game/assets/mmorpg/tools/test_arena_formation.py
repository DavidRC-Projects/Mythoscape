"""Saved battle formation: validation, order, backward compatibility, practice staging (5 Nov)."""
import os, sys, sqlite3, types, random
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "server"))
import combat, mercenaries as merc
random.seed(3)
c = sqlite3.connect(":memory:"); c.row_factory = sqlite3.Row
c.execute("CREATE TABLE players (id INTEGER PRIMARY KEY, coins INTEGER DEFAULT 0, bank_coins INTEGER DEFAULT 0, command_xp INTEGER DEFAULT 0, reputation INTEGER DEFAULT 0, noble_rank INTEGER DEFAULT 0)")
c.execute("CREATE TABLE rep_log (id INTEGER PRIMARY KEY AUTOINCREMENT, ts REAL, player_id INTEGER, source TEXT, delta INTEGER)")
for pid in (1, 2): c.execute("INSERT INTO players (id, coins) VALUES (?, 9000000)", (pid,))
merc.ensure_schema(c)
def sess(pid):
    xp = {"command": combat.xp_for_level(99), "smithing": 0}
    return types.SimpleNamespace(player_id=pid, coins=9_000_000, bank_coins=0, xp=xp, reputation=0, char_name=f"P{pid}",
                                 arena_match=None, level=lambda s: combat.level_from_xp(int(xp.get(s) or 0)))
S, O = sess(1), sess(2)
fails = []
def ok(cond, label):
    print(("PASS " if cond else "FAIL ") + label); cond or fails.append(label)
for i in range(10):
    merc.recruit(c, S, ["man_at_arms", "bulwark", "skirmisher", "duelist", "medic"][i % 5] if i != 9 else "veteran")
merc.recruit(c, O, "levy")
ids = [int(r["id"]) for r in merc.roster_rows(c, 1)]
other = int(merc.roster_rows(c, 2)[0]["id"])
ok(len(ids) == 10, "ten soldiers recruited")
ok([int(r["id"]) for r in merc.battle_rows(c, 1)] == ids, "no formation = roster order (backward compatible)")
p = merc.formation_payload(c, 1)
ok(p["slots"] == ids and not p["saved"] and p["mounts"] is False, "payload default slots, mounts not implemented")
ok(not merc.set_formation(c, S, ids + [ids[0]])[0], "rejects >10 slots")
ok(not merc.set_formation(c, S, [ids[0], ids[0]])[0], "rejects duplicates")
ok(not merc.set_formation(c, S, [other])[0], "rejects soldier not owned")
ok(not merc.set_formation(c, S, ["x"])[0], "rejects garbage id")
ok(not merc.set_formation(c, S, "nope")[0], "rejects non-list")
want = list(reversed(ids))
ok(merc.set_formation(c, S, want)[0], "saves reversed formation")
ok(merc.get_formation(c, 1) == want, "loads saved slots")
ok([int(r["id"]) for r in merc.battle_rows(c, 1)] == want, "battle order follows formation")
partial = [ids[3], None, ids[1], None, None, ids[0], None, None, None, None]
merc.set_formation(c, S, partial)
order = [int(r["id"]) for r in merc.battle_rows(c, 1)]
ok(order[:3] == [ids[3], ids[1], ids[0]] and sorted(order) == sorted(ids), "partial formation: placed first, rest still fight")
merc.set_formation(c, S, want)
st, text, m = merc.start_live_practice(c, S, "squire_alden")
you = [u for u in m["units"] if u["side"] == "you"]
front = [u for u in you if u["rank"] == "front"]
ok_ = len(you) == 10 and len(front) == 5
print(("PASS " if ok_ else "FAIL ") + "practice fields 10, 5 front"); ok_ or fails.append("staging")
names = {int(r["id"]): r["name"] for r in merc.roster_rows(c, 1)}
fn = sorted(u["name"] for u in front); wn = sorted(names[i] for i in want[:5])
print(("PASS " if fn == wn else "FAIL ") + "front rank = first five formation slots"); fn == wn or fails.append("front names")
xp_before = {int(r["id"]): int(r["attack_xp"]) + int(r["strength_xp"]) + int(r["defence_xp"]) + int(r["hitpoints_xp"]) for r in merc.roster_rows(c, 1)}
merc.begin_live_fight(S)
for _ in range(2000):
    merc.tick_live_match(m)
    if m["phase"] == "done": break
text, summ = merc.settle_live_practice(c, S, m)
xp_after = {int(r["id"]): int(r["attack_xp"]) + int(r["strength_xp"]) + int(r["defence_xp"]) + int(r["hitpoints_xp"]) for r in merc.roster_rows(c, 1)}
g = all(xp_after[k] >= xp_before[k] for k in xp_before) and len(xp_after) == 10
print(("PASS " if g else "FAIL ") + f"battle settled ({'won' if summ.get('won') else 'lost'}), no soldier lost XP"); g or fails.append("xp")
merc.dismiss(c, S, want[0])
ok2 = want[0] not in merc.get_formation(c, 1) and len(merc.battle_rows(c, 1)) == 9
print(("PASS " if ok2 else "FAIL ") + "dismissed soldier drops out of formation"); ok2 or fails.append("dismiss")
merc.clear_formation(c, S)
ok3 = not merc.has_formation(c, 1)
print(("PASS " if ok3 else "FAIL ") + "reset to default"); ok3 or fails.append("reset")
print("FAILED" if fails else "ALL PASS", fails)
sys.exit(1 if fails else 0)
