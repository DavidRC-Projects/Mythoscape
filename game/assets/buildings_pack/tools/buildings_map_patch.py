"""buildings_map_patch.py - reference map stamp + checker for the 11 bigger village/city/harbour houses.

    python3 tools/buildings_map_patch.py --repo /path/to/Mythoscape [--dump]

apply_new_buildings(grid, wm) re-stamps each building exactly like world_map._building():
WALL rect, FLOOR floor-rect, PATH door tile, PATH apron below the door.  Doors never move, and the
south wall row (y1) never moves, so every door / enter / exit tile and every interior spot stays valid.
Porch/yard tiles (inside the rect, outside the floor) are WALL: props stand there.
"""
import argparse, collections, importlib, os, sys

# id: (x0,y0,x1,y1, floor x0,y0,x1,y1, door_x)   old values in OLD
NEW = {
    "cottage_nw":        (2, 2, 17, 11,    3, 3, 16, 9,    7),    # Elder's Hall (porch row y 10)
    "cottage_ne":        (23, 2, 33, 11,   24, 3, 32, 9,   27),   # General Store
    "cottage_sw":        (2, 21, 15, 32,   3, 22, 14, 30,  7),    # The Resting Ox
    "cottage_se":        (23, 23, 35, 32,  24, 24, 30, 30, 27),   # Farmhouse (barn + veg patch east = yard)
    "bank":              (33, 13, 43, 20,  34, 14, 42, 18, 38),   # Village Bank (portico row y 19)
    "pet_emporium":      (50, 22, 63, 32,  51, 23, 59, 30, 55),   # Pet Emporium (pen east = yard)
    "city_house_nw":     (81, 42, 91, 52,  82, 43, 90, 50, 86),   # Stonehaven Cottage
    "city_house_sw":     (80, 58, 92, 66,  81, 59, 91, 64, 86),   # Stonehaven House
    "city_barracks":     (109, 57, 119, 68, 110, 58, 118, 66, 114),  # City Barracks (3rd stone house)
    "harbour_fishmonger": (130, 20, 143, 28, 135, 21, 142, 26, 138),  # Kai's Catch (stall wing west = yard)
    "harbour_tackle":    (134, 6, 146, 14, 135, 7, 141, 12, 138),  # Harbourreach Tackle (deck east = yard)
}
OLD = {
    "cottage_nw": (3, 3, 11, 11, 4, 4, 10, 10, 7), "cottage_ne": (23, 3, 31, 11, 24, 4, 30, 10, 27),
    "cottage_sw": (3, 24, 11, 32, 4, 25, 10, 31, 7), "cottage_se": (23, 24, 31, 32, 24, 25, 30, 31, 27),
    "bank": (34, 14, 42, 20, 35, 15, 41, 19, 38), "pet_emporium": (50, 24, 60, 32, 51, 25, 59, 31, 55),
    "city_house_nw": (82, 44, 90, 52, 83, 45, 89, 51, 86), "city_house_sw": (82, 58, 90, 66, 83, 59, 89, 65, 86),
    "city_barracks": (110, 58, 118, 68, 111, 59, 117, 67, 114),
    "harbour_fishmonger": (134, 20, 142, 28, 135, 21, 141, 27, 138),
    "harbour_tackle": (134, 6, 142, 14, 135, 7, 141, 13, 138),
}
# entities that must move because the new footprint covers them
MOVES = {"jeweler_lira (npc + place 'jeweler')": ((33, 8), (35, 8))}
EXTRA_WALKABLE_FLOOR_ROW = True   # the row directly north of the door (door_x, y1-1) must be FLOOR


def apply_new_buildings(grid, wm):
    changed = collections.Counter()
    for bid, (x0, y0, x1, y1, fx0, fy0, fx1, fy1, dx) in NEW.items():
        def put(x, y, t):
            if grid[y][x] != t:
                changed[grid[y][x]] += 1
                grid[y][x] = t
        for y in range(y0, y1 + 1):
            for x in range(x0, x1 + 1):
                put(x, y, wm.WALL)
        for y in range(fy0, fy1 + 1):
            for x in range(fx0, fx1 + 1):
                put(x, y, wm.FLOOR)
        for y in range(fy1 + 1, y1):            # doorway column through the porch row(s)
            put(dx, y, wm.PATH)
        put(dx, y1, wm.PATH)
        if grid[y1 + 1][dx] != wm.WALL:
            put(dx, y1 + 1, wm.PATH)
    return changed


def flood(grid, wm, start, walk):
    H, W = len(grid), len(grid[0])
    seen = {start}
    q = collections.deque([start])
    while q:
        x, y = q.popleft()
        for nx, ny in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)):
            if 0 <= nx < W and 0 <= ny < H and (nx, ny) not in seen and walk(nx, ny):
                seen.add((nx, ny))
                q.append((nx, ny))
    return seen


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", required=True)
    ap.add_argument("--dump", action="store_true")
    a = ap.parse_args()
    sd = os.path.join(a.repo, "game/assets/mmorpg/server")
    sys.path.insert(0, sd)
    wm = importlib.import_module("world_map")
    c = importlib.import_module("content")
    old = wm.generate_world()
    new = [row[:] for row in old]
    changed = apply_new_buildings(new, wm)
    ok = True
    def res(name, cond, extra=""):
        nonlocal ok
        ok &= bool(cond)
        print(("PASS " if cond else "FAIL ") + name + (("  " + extra) if extra else ""))

    # 1. old values match the repo (doors / rects)
    bmap = {b["id"]: b for b in c.BUILDINGS}
    mism = [bid for bid, o in OLD.items() if (bmap[bid]["x0"], bmap[bid]["y0"], bmap[bid]["x1"], bmap[bid]["y1"],
            bmap[bid]["floor_x0"], bmap[bid]["floor_y0"], bmap[bid]["floor_x1"], bmap[bid]["floor_y1"]) != o[:8]]
    res("old footprints match content.BUILDINGS", not mism, str(mism))
    doors = {i["building"]: i for i in c.INTERACTABLES if i.get("kind") == "door" and i.get("building")}
    dm = [bid for bid, n in NEW.items() if (doors[bid]["x"], doors[bid]["y"]) != (n[8], n[3])]
    res("door tiles unchanged (x, y1)", not dm, str(dm))
    # 2. new rect contains old rect, floor contains old floor except the old porch-less front row
    cont = [bid for bid in NEW if not (NEW[bid][0] <= OLD[bid][0] and NEW[bid][1] <= OLD[bid][1]
            and NEW[bid][2] >= OLD[bid][2] and NEW[bid][3] == OLD[bid][3])]
    res("new rect contains old rect, south wall row unchanged", not cont, str(cont))
    # 3. footprints don't overlap / touch each other or other buildings (1 tile gap)
    rects = {b["id"]: (b["x0"], b["y0"], b["x1"], b["y1"]) for b in c.BUILDINGS}
    rects.update({k: v[:4] for k, v in NEW.items()})
    clash = []
    ids = list(rects)
    for i, p in enumerate(ids):
        for q_ in ids[i + 1:]:
            A, B = rects[p], rects[q_]
            if A[0] - 1 <= B[2] and B[0] - 1 <= A[2] and A[1] - 1 <= B[3] and B[1] - 1 <= A[3]:
                clash.append((p, q_))
    res("no footprint overlaps/touches another building", not clash, str(clash))
    # 4. entity positions: interior spots stay walkable-or-prop, outside entities stay outside walls
    newly_blocked = {(x, y) for y in range(len(old)) for x in range(len(old[0]))
                     if old[y][x] in wm.WALKABLE_TILES and new[y][x] not in wm.WALKABLE_TILES}
    ents = [("npc", n["id"], n["x"], n["y"]) for n in c.NPCS]
    ents += [("spot", i["id"], i["x"], i["y"]) for i in c.INTERACTABLES if i.get("kind") != "door"]
    ents += [("spawn", s[0], s[1], s[2]) for s in c.MONSTER_SPAWNS]
    hit = [e for e in ents if (e[2], e[3]) in newly_blocked]
    moved_ok = all(any(e[1] in k for k in MOVES) and (e[2], e[3]) == MOVES[[k for k in MOVES if e[1] in k][0]][0] for e in hit)
    res("entities on newly blocked tiles are exactly the planned MOVES", moved_ok, str(hit))
    for k, (_, dst) in MOVES.items():
        res(f"move target walkable: {k} -> {dst}", new[dst[1]][dst[0]] in wm.WALKABLE_TILES)
    # 5. every old interior spot still inside the new floor
    lost = []
    for bid, n in NEW.items():
        o = OLD[bid]
        for e in ents:
            if o[4] <= e[2] <= o[6] and o[5] <= e[3] <= o[7] and not (n[4] <= e[2] <= n[6] and n[5] <= e[3] <= n[7]):
                lost.append((bid, e))
    res("every old interior spot/NPC stays inside the new floor", not lost, str(lost))
    # 6. reachability
    sx, sy = wm.SPAWN_POINT
    wo = flood(old, wm, (sx, sy), lambda x, y: old[y][x] in wm.WALKABLE_TILES)
    wn = flood(new, wm, (sx, sy), lambda x, y: new[y][x] in wm.WALKABLE_TILES)
    lost_reach = {p for p in wo - wn if new[p[1]][p[0]] in wm.WALKABLE_TILES}
    res("no walkable tile outside the footprints lost reachability", not lost_reach, str(sorted(lost_reach)[:12]))
    for bid, n in NEW.items():
        fl = [(x, y) for y in range(n[5], n[7] + 1) for x in range(n[4], n[6] + 1)]
        res(f"{bid}: whole floor reachable", all(p in wn for p in fl))
        # sealed: floor reaches outside only through the door column
        dcol = {(n[8], y) for y in range(n[7] + 1, n[3] + 1)}
        inner = flood(new, wm, fl[0], lambda x, y: new[y][x] in wm.WALKABLE_TILES and (x, y) not in dcol)
        res(f"{bid}: sealed except its door", all(n[0] <= x <= n[2] and n[1] <= y <= n[3] for x, y in inner))
    # 7. zones unchanged for doors
    res("door zones unchanged", all(wm.get_zone(n[8], n[3]) == wm.get_zone(OLD[b][8], OLD[b][3]) for b, n in NEW.items()))
    names = {v: k for k, v in vars(wm).items() if k.isupper() and isinstance(v, int) and k not in ("WIDTH", "HEIGHT")}
    diff = collections.Counter((old[y][x], new[y][x]) for y in range(len(old)) for x in range(len(old[0])) if old[y][x] != new[y][x])
    print("tiles changed (old->new):", {f"{names.get(a_, a_)}->{names.get(b_, b_)}": v for (a_, b_), v in sorted(diff.items())})
    for bid, n in NEW.items():
        o = OLD[bid]
        an, ao = (n[2] - n[0] + 1) * (n[3] - n[1] + 1), (o[2] - o[0] + 1) * (o[3] - o[1] + 1)
        print(f"  {bid:20s} {o[2]-o[0]+1}x{o[3]-o[1]+1}={ao:3d} -> {n[2]-n[0]+1}x{n[3]-n[1]+1}={an:3d}  ({an/ao:.2f}x)")
    if a.dump:
        ch = {wm.GRASS: ".", wm.PATH: "=", wm.WALL: "#", wm.FLOOR: "f", wm.WATER: "~", wm.STONE: "s"}
        for t in wm.TREE_TILES:
            ch[t] = "T"
        for (X0, Y0, X1, Y1) in ((0, 0, 66, 36), (76, 38, 124, 72), (126, 0, 159, 32)):
            for y in range(Y0, Y1 + 1):
                print(f"{y:3} " + "".join(ch.get(new[y][x], "?") for x in range(X0, X1 + 1)))
            print()
    print("ALL PASS" if ok else "SOME CHECKS FAILED")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
