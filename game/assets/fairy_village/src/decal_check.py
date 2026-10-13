"""Independent check of json/ground_decals.json against the layout + collision JSON.

python3 src/decal_check.py   -> prints one line per rule and OVERALL PASS/FAIL (exit code 1 on FAIL)
Rules: every tile under every decal is inside the fairy zone, is painted GRASS, and is NOT
  - any collision tile (json/collision/*.json blocked_tiles, current AND trimmed lists),
  - any door / interaction tile or stand tile,
  - any fountain footprint tile,
  - any NPC spawn tile (json/npc_spawns.json) or moved NPC/interactable tile (json/dungeon_entrance.json moves),
  - any dungeon mouth / enter / exit / return tile;
  decals do not overlap each other, every decal id has art at 1x/2x/4x, and the list is deterministic
  (re-running src/ground_layout.py reproduces it byte for byte).
"""
import json, os, glob, sys, subprocess, hashlib

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def L(p):
    return json.load(open(os.path.join(ROOT, p)))


def main():
    lay = L("json/village_layout.json"); dec = L("json/ground_decals.json")
    zx0, zy0, zx1, zy1 = lay["fairy_zone"]
    paint = {}
    for op in lay["paint_ops"]:
        x0, y0, x1, y1 = op["rect"]
        for y in range(y0, y1 + 1):
            for x in range(x0, x1 + 1):
                paint[(x, y)] = op["tile"]
    bad = {}
    for p in glob.glob(os.path.join(ROOT, "json", "collision", "*.json")) + glob.glob(os.path.join(ROOT, "json", "collision_trimmed", "*.json")):
        c = json.load(open(p)); k = c.get("key", os.path.basename(p))
        for t in c["blocked_tiles"]:
            bad[tuple(t)] = f"collision {k}"
        for f in ("interaction_tile", "stand_tile", "door_tile"):
            if c.get(f):
                bad[tuple(c[f])] = f"{f} {k}"
        if "footprint" in c and k in lay["fountains"]:
            fp = c["footprint"]
            for y in range(fp["y0"], fp["y1"] + 1):
                for x in range(fp["x0"], fp["x1"] + 1):
                    bad[(x, y)] = f"fountain {k}"
    for n in L("json/npc_spawns.json")["npcs"]:
        bad[(n["x"], n["y"])] = f"npc {n['id']}"
    d = L("json/dungeon_entrance.json")
    for t in d["new"]["mouth_tiles"] + [d["new"]["return_tile"], d["new"]["enter"], d["new"]["exit"]]:
        bad[tuple(t)] = "dungeon mouth/return"
    for name, (_, new) in d["moves"].items():
        bad[tuple(new)] = f"moved {name}"
    fails = []; used = {}
    for i, e in enumerate(dec["decals"]):
        for y in range(e["y"], e["y"] + e["h"]):
            for x in range(e["x"], e["x"] + e["w"]):
                t = (x, y)
                if not (zx0 <= x <= zx1 and zy0 <= y <= zy1):
                    fails.append(f"{e['id']}@{e['x']},{e['y']} tile {t} outside fairy zone")
                if paint.get(t) != "GRASS":
                    fails.append(f"{e['id']}@{e['x']},{e['y']} tile {t} is {paint.get(t)} not GRASS")
                if t in bad:
                    fails.append(f"{e['id']}@{e['x']},{e['y']} tile {t} is forbidden ({bad[t]})")
                if t in used:
                    fails.append(f"{e['id']}@{e['x']},{e['y']} overlaps decal #{used[t]}")
                used[t] = i
    missing = []
    for did in {e["id"] for e in dec["decals"]}:
        for s in ("1x", "2x", "4x"):
            if not os.path.exists(os.path.join(ROOT, "assets", "decals", did, f"{did}_{s}.png")):
                missing.append(f"{did}_{s}.png")
    h0 = hashlib.md5(open(os.path.join(ROOT, "json", "ground_decals.json"), "rb").read()).hexdigest()
    subprocess.run([sys.executable, os.path.join(ROOT, "src", "ground_layout.py")], capture_output=True, check=True)
    h1 = hashlib.md5(open(os.path.join(ROOT, "json", "ground_decals.json"), "rb").read()).hexdigest()
    rows = [
        (not fails, f"{len(dec['decals'])} decals, {len(used)} tiles: none on collision/door/stand/NPC/fountain/dungeon tiles, all on GRASS in the zone, no overlaps" + ("" if not fails else f"  -> {fails[:8]}")),
        (not missing, "art present for every decal at 1x/2x/4x" + ("" if not missing else f" missing {missing}")),
        (h0 == h1, "placement is deterministic (regenerated file is identical)"),
    ]
    ok = all(r[0] for r in rows)
    for good, msg in rows:
        print(("PASS  " if good else "FAIL  ") + msg)
    print(f"forbidden tiles checked: {len(bad)}")
    print("OVERALL", "PASS" if ok else "FAIL")
    return ok


if __name__ == "__main__":
    sys.exit(0 if main() else 1)
