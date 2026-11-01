"""Arena duel v2 balance: win rate by gear tier (weapon + full armour set) vs each champion,
per weapon class and bot skill.  python3 tools/duel_tier_sim.py [N] [--md out.md]"""
import os, sys, zlib, random
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import duel_sim as S   # noqa: E402  (Bot + arena_duel import)
D = S.D
TIERS = ["arena", "iron", "steel", "mithril", "adamant", "mythos"]


def one(boss, style, skill, tier, seed):
    rng = random.Random(seed)
    d = D.new_duel(boss, style, level_ratio=1.0, gear=tier, armour=tier, seed=seed)
    bot = S.Bot(skill, rng)
    while not d["done"]:
        a = bot.choose(d)
        if a:
            D.act(d, a)
        D.step(d)
    return d["won"]


def rate(boss, style, skill, tier, n):
    return sum(one(boss, style, skill, tier, zlib.crc32(f"{boss}|{style}|{skill}|{tier}|{i}".encode()) & 0xffffff)
               for i in range(n)) / n


def main():
    n = int(sys.argv[1]) if len(sys.argv) > 1 and sys.argv[1].isdigit() else 60
    out = ["## Win rate by gear tier (decent bot, skill 0.70), averaged over the 6 champions", "",
           "| Gear (weapon + full set) | Sword | Axe | Bow |", "|---|---|---|---|"]
    for t in TIERS:
        row = [f"{100 * sum(rate(b, st, 0.70, t, n) for b in S.BOSSES) / len(S.BOSSES):.0f}%" for st in S.STYLES]
        out.append(f"| {t} | " + " | ".join(row) + " |")
    out += ["", "## Skill vs gear: casual (0.45) / decent (0.70) / expert (0.90), sword, vs each champion", "",
            "| Champion (tier) | arena casual/decent/expert | steel | mythos |", "|---|---|---|---|"]
    for b in S.BOSSES:
        cells = []
        for t in ("arena", "steel", "mythos"):
            cells.append("/".join(f"{100 * rate(b, 'sword', sk, t, n):.0f}" for sk in (0.45, 0.70, 0.90)))
        out.append(f"| {b} ({D.tuning()['bosses'][b].get('tier', '?')}) | " + " | ".join(cells) + " |")
    out += ["", "## Per class vs each champion (steel set, decent)", "", "| Champion | Sword | Axe | Bow |", "|---|---|---|---|"]
    for b in S.BOSSES:
        out.append(f"| {b} | " + " | ".join(f"{100 * rate(b, st, 0.70, 'steel', n):.0f}%" for st in S.STYLES) + " |")
    txt = "\n".join(out)
    print(txt)
    if "--md" in sys.argv:
        open(sys.argv[sys.argv.index("--md") + 1], "w").write(txt + "\n")


if __name__ == "__main__":
    main()
