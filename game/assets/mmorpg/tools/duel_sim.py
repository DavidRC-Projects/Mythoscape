"""Headless boss-duel simulator: bot vs every boss, per weapon style / skill / gear.

  python tools/duel_sim.py [N_PER_CELL] [--md out.md]

Bots: skill = chance to read a telegraph and answer it in time (0.45 casual, 0.7 decent, 0.9 expert).
Reports win rate, mean duel length (s) and finisher rate (share of wins ended by a finisher).
Tuning: server/duel_tuning.json.
"""
import os
import random
import zlib
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "server"))
import arena_duel as D  # noqa: E402

BOSSES = ["varro", "brutus", "crixus", "sabina", "ignatius", "unbroken"]
STYLES = ["sword", "axe", "bow"]
SKILLS = {"casual": 0.45, "decent": 0.70, "expert": 0.90}
GEARS = {"under": (0.85, "iron"), "matched": (1.0, "steel"), "over": (1.15, "adamant")}


class Bot:
    def __init__(self, skill, rng):
        self.skill, self.rng = skill, rng
        self.plan = None  # (atk_id, react_at_left, action)

    def choose(self, d):
        rng = self.rng
        S = D.tuning()["styles"][d["style"]]
        tel = D.telegraph(d)
        p = d["p"]
        if d["finisher_ready"]:
            if S["ranged"]:
                need = D._boss(d).get("bow_focus", D.tuning()["finisher"].get("bow_focus", 0.0))
                return "finish" if p["focus"] >= need else None  # hold still to steady the shot
            if d["gap"] <= 2.0:
                return "finish"
            return "forward"
        if tel:
            if self.plan is None or self.plan[0] != id(d["b"]["atk"]):
                good = rng.random() < self.skill
                if S["ranged"]:
                    reach = tel["reach"]
                    if reach < 4 and p["wall"] > 1.0 and d["gap"] + S["move"]["speed"] * (tel["left"] - 1) > reach + 0.2:
                        act = "back"
                    else:
                        act = "dodge"
                else:
                    act = "parry" if tel["parry"] and rng.random() < 0.75 else "dodge"
                at = 1 if good else rng.choice([3, 4, 0])
                self.plan = (id(d["b"]["atk"]), at, act)
            _, at, act = self.plan
            if act == "back":
                return "back" if tel["left"] > 1 else ("dodge" if self.skill > rng.random() else None)
            if tel["left"] == at:
                return act
            if tel["left"] > 2 and p["busy"] == 0 and p["sta"] > 45 and not S["ranged"] and d["gap"] <= 2:
                return "light"
            if tel["left"] > 2 and p["busy"] == 0 and p["sta"] > 40 and S["ranged"] and d["gap"] >= S["light"]["min_gap"]:
                return "light"  # loose a quick shot while the wind-up plays out
            return None
        self.plan = None
        if p["busy"]:
            return None
        if S["ranged"]:
            if p["counter"] > 0 and p["sta"] >= S["light"]["sta"]:
                return "light"
            # kite to long range only against slow bosses; vs fast ones hold mid range and shoot
            slow = D.tuning()["bosses"][d["boss_id"]]["speed"] < S["move"]["speed"] * 0.6
            keep = 5.0 if slow else 3.0
            if d["gap"] < keep and d["b"]["state"] != "stagger" and p["wall"] >= 0.5:
                return "back"
            if p["focus"] >= 0.95 and p["sta"] >= S["heavy"]["sta"]:
                return "heavy"
            if p["sta"] > 25 and rng.random() < 0.8:
                return "light"
            return None
        if d["gap"] > S["reach"]:
            return "forward"
        if p["counter"] > 0 or d["b"]["state"] == "stagger":
            return "heavy" if p["sta"] >= S["heavy"]["sta"] + 15 else "light"
        if p["sta"] > 35:
            return "light"
        return None


def duel(boss, style, skill, ratio, gear, seed):
    rng = random.Random(seed)
    d = D.new_duel(boss, style, level_ratio=ratio, gear=gear, seed=seed)
    bot = Bot(skill, rng)
    while not d["done"]:
        a = bot.choose(d)
        if a:
            D.act(d, a)
        D.step(d)
    return d["won"], d["step"] * D.tuning()["step_ms"] / 1000.0, d["finisher"]


def run(n=200):
    rows = []
    for boss in BOSSES:
        for style in STYLES:
            for sk_name, sk in SKILLS.items():
                for g_name, (ratio, gear) in GEARS.items():
                    w = f = 0
                    secs = 0.0
                    for i in range(n):
                        won, s, fin = duel(boss, style, sk, ratio, gear, zlib.crc32(f'{boss}|{style}|{sk_name}|{g_name}|{i}'.encode()) & 0xffffff)
                        w += won
                        f += bool(fin)
                        secs += s
                    rows.append((boss, style, sk_name, g_name, w / n, secs / n, (f / w) if w else 0.0))
    return rows


def table(rows, gear="matched"):
    out = ["| Boss | Style | Casual win | Decent win | Expert win | Avg length (decent) | Finisher rate (decent wins) |",
           "|---|---|---|---|---|---|---|"]
    idx = {(r[0], r[1], r[2], r[3]): r for r in rows}
    for boss in BOSSES:
        for style in STYLES:
            c, m, e = (idx[(boss, style, k, gear)] for k in ("casual", "decent", "expert"))
            out.append(f"| {boss} | {style} | {c[4]:.0%} | {m[4]:.0%} | {e[4]:.0%} | {m[5]:.0f}s | {m[6]:.0%} |")
    return "\n".join(out)


if __name__ == "__main__":
    n = int(sys.argv[1]) if len(sys.argv) > 1 and sys.argv[1].isdigit() else 200
    rows = run(n)
    md = "## Matched gear/level\n\n" + table(rows) + "\n\n## Under-geared (0.85 level, iron)\n\n" + table(rows, "under") \
        + "\n\n## Over-geared (1.15 level, adamant)\n\n" + table(rows, "over") + "\n"
    print(md)
    if "--md" in sys.argv:
        open(sys.argv[sys.argv.index("--md") + 1], "w").write(md)
