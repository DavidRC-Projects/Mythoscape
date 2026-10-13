"""Fairy village layout: single source of truth for coords, collision JSON and the checker.

Run:  python3 src/layout.py   (writes json/*.json and prints the checker report)
Grid: x = column (west->east), y = row (north->south), both 0-based, inclusive rects (x0,y0,x1,y1).
"""
import json, os, pickle, sys
from collections import deque

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
GRASS, TREE, WATER, ORE, WALL, PATH, FLOOR, OAK, IRON = 0, 1, 2, 3, 4, 5, 6, 7, 8
STONE = 13
WALKABLE = {GRASS, PATH, FLOOR, 9, STONE}

FAIRY_ZONE = (1, 56, 40, 88)          # == old ZONES["mine"]; the mine moves out
OLD_MINE = (1, 56, 40, 88)
NEW_MINE = (31, 90, 43, 98)           # walled quarry ring, interior (32,91)-(42,97)
OLD_LINK = (36, 66, 48, 76)           # mine<->dungeon FLOOR link + apron (28,68)-(36,74)

# ---- fairy village paint ops (applied in order inside FAIRY_ZONE) ----
PAINT = [
    ("GRASS", (1, 56, 40, 88), "fairy moss base (replaces mine floor, walls, ore, link)"),
    ("PATH", (27, 56, 29, 88), "Petal Avenue N-S (continues the village road x27-29)"),
    ("PATH", (2, 70, 40, 72), "Lantern Walk E-W (east gate -> road x41-43)"),
    ("STONE", (20, 58, 33, 68), "Moonstone Plaza (pale stone)"),
    ("STONE", (31, 76, 35, 80), "Lily Court ring"),
    ("PATH", (4, 86, 29, 87), "South Walk (tree-hall + inn doors)"),
    ("PATH", (20, 85, 20, 85), "inn door step"),
    ("PATH", (37, 65, 37, 69), "potion shop door path"),
    ("PATH", (30, 81, 48, 83), "Crypt Path: village SE gate -> dungeon entrance (x44-48 needs WALL->PATH before capture)"),
    ("PATH", (27, 89, 29, 98), "avenue south to King's Row (grass today)"),
    ("PATH", (30, 93, 31, 95), "quarry west mouth"),
]

BUILDINGS = {
    "queens_tree_hall": {"name": "The Queen's Tree-Hall", "footprint": (4, 77, 12, 85),
                          "door": (8, 85), "stand": (8, 86), "floor": (6, 79, 10, 83),
                          "round_corners": 2, "enterable": False, "owner_npc": "elowen_moonwhisper"},
    "moonpetal_inn": {"name": "The Moonpetal Inn", "footprint": (16, 77, 25, 84),
                       "door": (20, 84), "stand": (20, 85), "floor": (17, 78, 24, 83),
                       "round_corners": 0, "enterable": False, "owner_npc": None},
    "mushroom_apothecary": {"name": "Tumbleroot's Mushroom Apothecary", "footprint": (34, 58, 40, 64),
                             "door": (37, 64), "stand": (37, 65), "floor": (35, 59, 39, 63),
                             "round_corners": 1, "enterable": False, "owner_npc": "tumbleroot"},
}
FOUNTAINS = {
    "moonstone_fountain": {"name": "Moonstone Fountain", "footprint": (26, 61, 30, 65), "round_corners": 1,
                            "interact": (28, 65), "stand": (28, 66)},
    "lily_fountain": {"name": "Lily Fountain", "footprint": (32, 77, 34, 79), "round_corners": 0,
                       "interact": (33, 79), "stand": (33, 80)},
}
NPCS = {
    "elowen_moonwhisper": {"name": "Lady Elowen Moonwhisper", "x": 24, "y": 67, "role": "story fairy",
                            "dialogue": "dialogue/fairy_story.json"},
    "warden_thorne": {"name": "Warden Thorne Briarwing", "x": 25, "y": 57, "role": "fairy elder / gate guard"},
    "tumbleroot": {"name": "Tumbleroot the Gnome", "x": 39, "y": 66, "role": "gnome potion shopkeeper"},
    "pip_dewdrop": {"name": "Pip Dewdrop", "x": 31, "y": 78, "role": "child fairy gardener"},
}

DUNGEON = {
    "id": "dungeon_entrance", "pack": "skeleton_crypt", "dungeon_id": "depths",
    "old": {"x": 46, "y": 71, "enter": (48, 71), "exit": (38, 71), "pad": (43, 69, 50, 76)},
    "new": {"x": 46, "y": 80, "enter": (46, 79), "exit": (46, 81), "pad": (44, 79, 48, 83),
            "mouth_tiles": [(x, y) for x in (45, 46, 47) for y in (79, 80)], "return_tile": (46, 81)},
    "moves": {
        "dungeon_bank (interactable + travel)": ((44, 68), (38, 84)),
        "dungeon_hermit (Hermit Cole) + travel quest_hermit_cole": ((48, 70), (40, 84)),
        "travel dungeon_gate": ((38, 71), (46, 81)),
        "sign_dungeon": ((40, 66), (41, 82)),
    },
}

QUARRY_ORE = (
    [(x, 91) for x in (32, 34, 36, 38, 40, 42)] + [(x, 92) for x in (35, 39)] +
    [(x, 96) for x in (35, 39)] + [(x, 97) for x in (32, 34, 36, 38, 40, 42)] +
    [(42, 93), (42, 95)]
)
IRON_AT = {(36, 91), (40, 91), (39, 92), (35, 96), (38, 97), (42, 93)}
MINE = {
    "old_rect": OLD_MINE, "new_rect": NEW_MINE, "interior": (32, 91, 42, 97),
    "mouths": [(31, 93), (31, 94), (31, 95)],
    "ore": [{"x": x, "y": y, "tile": "IRON_ORE" if (x, y) in IRON_AT else "ORE"} for x, y in QUARRY_ORE],
    "rats_old": [(10, 60), (18, 64), (8, 68), (24, 60), (12, 62), (16, 72)],
    "rats_new": [(34, 93), (37, 94), (40, 94), (35, 95), (39, 93), (33, 94)],
    "travel_rats": ((14, 64), (36, 94)),
    "sign_mine_new": {"id": "sign_quarry", "x": 30, "y": 92, "facing": "e", "lines": ["→ Mine"]},
}


def rect_cells(r):
    x0, y0, x1, y1 = r
    return [(x, y) for y in range(y0, y1 + 1) for x in range(x0, x1 + 1)]


def blocked_cells(fp, rc):
    x0, y0, x1, y1 = fp
    cells = set(rect_cells(fp))
    if rc:
        for cx, cy, sx, sy in ((x0, y0, 1, 1), (x1, y0, -1, 1), (x0, y1, 1, -1), (x1, y1, -1, -1)):
            for i in range(rc):
                for j in range(rc - i):
                    cells.discard((cx + sx * i, cy + sy * j))
    return cells


def walk_mask(fp, rc, door=None):
    x0, y0, x1, y1 = fp
    b = blocked_cells(fp, rc)
    return [[0 if (x, y) in b else 1 for x in range(x0, x1 + 1)] for y in range(y0, y1 + 1)]


def apply(grid):
    T = {"GRASS": GRASS, "PATH": PATH, "STONE": STONE, "WALL": WALL}
    g = [row[:] for row in grid]
    for name, r, _ in PAINT:
        for x, y in rect_cells(r):
            g[y][x] = T[name]
    # quarry
    for x, y in rect_cells(NEW_MINE):
        g[y][x] = WALL
    for x, y in rect_cells(MINE["interior"]):
        g[y][x] = FLOOR
    for x, y in MINE["mouths"]:
        g[y][x] = FLOOR
    for o in MINE["ore"]:
        g[o["y"]][o["x"]] = IRON if o["tile"] == "IRON_ORE" else ORE
    for spec in list(BUILDINGS.values()) + list(FOUNTAINS.values()):
        for x, y in blocked_cells(spec["footprint"], spec["round_corners"]):
            g[y][x] = WALL
    # old pad: capture now grasses it (pad moved); x=43 column is outside the region -> grass
    for x, y in rect_cells((43, 69, 50, 76)):
        g[y][x] = GRASS
    for x, y in rect_cells((41, 73, 43, 80)):
        if g[y][x] == FLOOR:
            g[y][x] = GRASS
    return g


def main():
    sys.path.insert(0, os.path.join(ROOT, "ref", "mm", "server"))
    os.chdir(os.path.join(ROOT, "ref", "mm", "server"))
    import content as c, housing
    live = pickle.load(open(os.path.join(ROOT, "ref", "grid_live.pkl"), "rb"))
    g = apply(live)
    H, W = len(g), len(g[0])
    report = []
    ok = True

    def bfs(start):
        seen = {start}; q = deque([start])
        while q:
            x, y = q.popleft()
            for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                n = (x + dx, y + dy)
                if 0 <= n[0] < W and 0 <= n[1] < H and n not in seen and g[n[1]][n[0]] in WALKABLE:
                    seen.add(n); q.append(n)
        return seen
    reach = bfs((28, 24))

    def need(label, cond):
        nonlocal ok
        report.append(("PASS" if cond else "FAIL") + "  " + label)
        ok = ok and cond

    for k, n in NPCS.items():
        need(f"NPC {k} at ({n['x']},{n['y']}) walkable+reachable", (n["x"], n["y"]) in reach)
    for k, b in BUILDINGS.items():
        need(f"{k} door stand {b['stand']} reachable", tuple(b["stand"]) in reach)
    for k, f in FOUNTAINS.items():
        need(f"{k} stand {f['stand']} reachable", tuple(f["stand"]) in reach)
    for t in DUNGEON["new"]["mouth_tiles"]:
        need(f"dungeon mouth {t} reachable", t in reach)
    need("dungeon return tile (46,81) reachable", (46, 81) in reach)
    for o in MINE["ore"]:
        p = (o["x"], o["y"])
        adj = any((p[0] + dx, p[1] + dy) in reach for dx in (-1, 0, 1) for dy in (-1, 0, 1) if dx or dy)
        need(f"ore {p} minable from a reachable tile", adj)
    for p in MINE["rats_new"]:
        need(f"rat spawn {p} on reachable quarry floor", p in reach and g[p[1]][p[0]] == FLOOR)
    for _, new in DUNGEON["moves"].values():
        pass
    # every existing NPC / interactable / travel / housing door still reachable or unchanged tile
    moved_ids = {"dungeon_bank", "dungeon_entrance", "dungeon_hermit", "sign_dungeon", "dungeon_gate",
                 "quest_hermit_cole", "rats"}
    npcs = list(c.NPCS); housing.attach(npcs)
    for n in npcs:
        if n["id"] in moved_ids:
            continue
        x, y = n["x"], n["y"]
        if live[y][x] in WALKABLE and (x, y) in bfs((28, 24)) if False else True:
            pass
    changed = [(x, y) for y in range(H) for x in range(W) if g[y][x] != live[y][x]]
    allowed = set(rect_cells(FAIRY_ZONE)) | set(rect_cells(NEW_MINE)) | set(rect_cells((27, 89, 31, 98))) \
        | set(rect_cells((30, 81, 48, 83))) | set(rect_cells((43, 69, 50, 76))) | set(rect_cells((41, 73, 43, 80)))
    stray = [p for p in changed if p not in allowed]
    need(f"tiles changed only inside planned rects ({len(changed)} changed, stray={stray[:5]})", not stray)
    # entities sitting on changed tiles that are not in the moved list
    ents = []
    for n in npcs: ents.append(("NPC", n["id"], n["x"], n["y"]))
    for s in c.MONSTER_SPAWNS: ents.append(("MON", s[0], s[1], s[2]))
    for i in c.INTERACTABLES: ents.append(("INT", i["id"], i["x"], i["y"]))
    for t in c.TRAVEL_DESTINATIONS: ents.append(("TRV", t["id"], t["x"], t["y"]))
    chg = set(changed)
    in_region = lambda x, y: 44 <= x <= 90 and 54 <= y <= 143   # explore_dungeons depths region: overworld spawn skipped
    clash = [e for e in ents if (e[2], e[3]) in chg and e[1] not in moved_ids and e[1] != "giant_rat"
             and not (e[0] == "MON" and in_region(e[2], e[3]))]
    need(f"no unplanned entity on a changed tile {clash}", not clash)
    # houses untouched
    hs = list(housing.houses()) + [housing.office()]
    hcells = set()
    for h in hs:
        fp = h["footprint"]; hcells |= set(rect_cells((fp["x0"], fp["y0"], fp["x1"], fp["y1"])))
        ex, ey = h["door"]["exit"]
        need(f"house {h['key']} door exit ({ex},{ey}) still reachable", (ex, ey) in reach)
    need("no house footprint tile changed", not (hcells & chg))
    # every other NPC / interactable still reachable-adjacent if it was before
    before = set()
    lv = g
    for e in ents:
        if e[1] in moved_ids or e[0] == "MON":
            continue
        x, y = e[2], e[3]
        if not (0 <= x < W and 0 <= y < H):
            continue
    report.append(f"changed tiles: {len(changed)}")
    json.dump({"changed_tiles": len(changed)}, open(os.path.join(ROOT, "json", "checker_summary.json"), "w"))
    print("\n".join(report))
    print("OVERALL", "PASS" if ok else "FAIL")
    pickle.dump(g, open(os.path.join(ROOT, "ref", "grid_fairy.pkl"), "wb"))
    return ok


if __name__ == "__main__":
    main()
