"""Reachability check for the PROPOSED silhouette-trimmed collision (json/collision_trimmed/*.json).

python3 src/trim_check.py
Re-runs the same plan as src/layout.py (live grid ref/grid_live.pkl + layout.apply) but stamps the trimmed
blocked tiles instead of the footprint-minus-round-corners cells, then checks from SPAWN (28,24):
every NPC, every door stand tile, fountain stand tile, dungeon mouth + return tile is reachable, every trimmed
list is a subset of the current list, and every interaction/door tile is still blocked.
"""
import json, os, sys, glob, pickle
from collections import deque
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))
import layout as Lm

trim = {json.load(open(p))["key"]: json.load(open(p)) for p in glob.glob(os.path.join(ROOT, "json", "collision_trimmed", "*.json"))}
cur = {os.path.basename(p)[:-5]: json.load(open(p)) for p in glob.glob(os.path.join(ROOT, "json", "collision", "*.json"))}
by_fp = {}
for k, spec in list(Lm.BUILDINGS.items()) + list(Lm.FOUNTAINS.items()):
    by_fp[tuple(spec["footprint"])] = {tuple(t) for t in trim[k]["blocked_tiles"]}
orig_blocked = Lm.blocked_cells
Lm.blocked_cells = lambda fp, rc: set(by_fp.get(tuple(fp), orig_blocked(fp, rc)))
live = pickle.load(open(os.path.join(ROOT, "ref", "grid_live.pkl"), "rb"))
g = Lm.apply(live)
H, W = len(g), len(g[0])
seen = {(28, 24)}; q = deque([(28, 24)])
while q:
    x, y = q.popleft()
    for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
        n = (x + dx, y + dy)
        if 0 <= n[0] < W and 0 <= n[1] < H and n not in seen and g[n[1]][n[0]] in Lm.WALKABLE:
            seen.add(n); q.append(n)
rows = []
for k, n in Lm.NPCS.items():
    rows.append(((n["x"], n["y"]) in seen, f"NPC {k} ({n['x']},{n['y']}) reachable"))
for k, b in Lm.BUILDINGS.items():
    rows.append((tuple(b["stand"]) in seen, f"{k} stand {b['stand']} reachable"))
    rows.append((g[b["door"][1]][b["door"][0]] == Lm.WALL, f"{k} door {b['door']} still blocked"))
for k, f in Lm.FOUNTAINS.items():
    rows.append((tuple(f["stand"]) in seen, f"{k} stand {f['stand']} reachable"))
    rows.append((g[f["interact"][1]][f["interact"][0]] == Lm.WALL, f"{k} interact {f['interact']} still blocked"))
for t in Lm.DUNGEON["new"]["mouth_tiles"] + [Lm.DUNGEON["new"]["return_tile"]]:
    rows.append((tuple(t) in seen, f"dungeon tile {tuple(t)} reachable"))
for k in trim:
    sub = {tuple(t) for t in trim[k]["blocked_tiles"]} <= {tuple(t) for t in cur[k]["blocked_tiles"]}
    rows.append((sub, f"{k}: trimmed list is a subset of the current list ({len(trim[k]['blocked_tiles'])}/{len(cur[k]['blocked_tiles'])})"))
ok = all(r[0] for r in rows)
for good, m in rows:
    print(("PASS  " if good else "FAIL  ") + m)
print("OVERALL", "PASS" if ok else "FAIL")
sys.exit(0 if ok else 1)
