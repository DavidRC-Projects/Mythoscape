"""realm_data.py - Castle Realm map + Duskspire Keep (gothic castle #1) floor data + multi-floor checker.

Pure python (no pygame). Produces:
  json/castle_realm_map.json   realm plane: 300x200 tile rows, legend, plots/castle registry, roads, portals
  json/gothic_castle.json      castle #1: footprint grid (castle_v2 format) + 4 interior floors (planes)
Run:  python realm_data.py [--out DIR] [--check]
The checker does a BFS over ALL planes (overworld portal -> realm -> drawbridge -> bailey -> keep door ->
floor 1 -> stairs -> floors 2..4) and asserts every room on every floor is reachable, stairs are symmetric, etc.
Later castles plug in by adding one CASTLES entry + one data file with the same schema.
"""
import json, os, random, sys
from collections import deque

W, H = 300, 200
# realm legend -> server tile names (server/world_map.py constants)
LEGEND = {
    ".": ("GRASS", True, "grass"), "=": ("PATH", True, "road (3 wide)"), "T": ("WALL", False, "tree / hedge (blocking)"),
    "#": ("WALL", False, "realm rim cliff"), "~": ("WATER", False, "pond"), "P": ("PATH", True, "return portal (-> overworld)"),
    "S": ("PATH", True, "arrival spawn"), "o": ("PATH", True, "plaza paving"), "f": ("GRASS", True, "flower bed (decor)"),
    "c": ("WALL", False, "castle footprint: walkability comes from the castle grid"),
    "r": ("GRASS", True, "reserved plot (castle not built yet)"), "l": ("PATH", True, "lamp / signpost tile (decor, walkable)"),
}
OVERWORLD_PORTAL = {"x": 32, "y": 33, "approach": [32, 34], "return_arrival": [32, 34],
                    "note": "grass 11 tiles south of the wishing well (32,22), east of the village road. Ten clear tiles between them."}
HUB = {"x0": 138, "y0": 168, "x1": 162, "y1": 188}
REALM_PORTAL = {"x": 150, "y": 186}
SPAWN = {"x": 150, "y": 182}

# castle registry: every castle = plot (reserved land incl. sprite overdraw) + footprint (grid) + gate apron
CASTLES = [
    {"id": "gothic", "name": "Duskspire Keep", "phase": 1, "status": "built", "plot": [20, 40, 80, 100],
     "footprint": [38, 52, 61, 75], "gate_apron": [[49, 76], [50, 76]], "data": "gothic_castle.json",
     "sprite_overdraw_tiles_up": 16, "size_vs_original": 1.0},
    {"id": "king", "name": "King's Castle", "phase": 3, "status": "reserved", "plot": [110, 8, 190, 90],
     "footprint": [120, 16, 179, 75], "gate_apron": [[149, 76], [150, 76]], "data": "king_castle.json", "size_vs_original": 6.25},
    {"id": "white_rose", "name": "White Rose Castle", "phase": 2, "status": "reserved", "plot": [220, 26, 292, 100],
     "footprint": [231, 36, 278, 83], "gate_apron": [[254, 84], [255, 84]], "data": "white_rose_castle.json", "size_vs_original": 4.0},
    {"id": "sky_anchor", "name": "Sky-Anchor Citadel", "phase": 4, "status": "reserved", "plot": [18, 118, 82, 178],
     "footprint": [35, 128, 64, 157], "gate_apron": [[49, 158], [50, 158]], "data": "sky_anchor_castle.json", "size_vs_original": 1.6},
]


def build_realm():
    g = [["." for _ in range(W)] for _ in range(H)]
    def rect(x0, y0, x1, y1, ch):
        for y in range(max(0, y0), min(H, y1 + 1)):
            for x in range(max(0, x0), min(W, x1 + 1)):
                g[y][x] = ch
    rng = random.Random(4242)
    # tree rim
    rect(0, 0, W - 1, 2, "#"); rect(0, H - 3, W - 1, H - 1, "#"); rect(0, 0, 2, H - 1, "#"); rect(W - 3, 0, W - 1, H - 1, "#")
    roads = []
    def road(x0, y0, x1, y1, name):
        rect(min(x0, x1), min(y0, y1), max(x0, x1), max(y0, y1), "="); roads.append({"name": name, "rect": [min(x0, x1), min(y0, y1), max(x0, x1), max(y0, y1)]})
    road(148, 77, 151, 168, "King's Avenue (hub -> King's gate)")
    road(48, 110, 256, 112, "Crown Boulevard (east-west)")
    road(48, 77, 51, 110, "Duskspire Lane (boulevard -> gothic gate)")
    road(253, 85, 256, 110, "Rose Walk (boulevard -> White Rose gate)")
    road(48, 159, 51, 185, "Anchor Path north leg (-> Sky-Anchor gate)")
    road(48, 184, 138, 186, "Anchor Path west leg (hub -> Sky-Anchor)")
    rect(HUB["x0"], HUB["y0"], HUB["x1"], HUB["y1"], "o")
    for (x, y) in ((HUB["x0"], HUB["y0"]), (HUB["x1"], HUB["y0"]), (HUB["x0"], HUB["y1"]), (HUB["x1"], HUB["y1"])):
        g[y][x] = "l"
    for (x, y) in ((47, 76), (52, 76), (147, 76), (152, 76), (252, 84), (257, 84), (47, 158), (52, 158)):
        g[y][x] = "l"   # gate lamps
    # ponds + flower beds (decor)
    for (cx, cy, r) in ((105, 140, 7), (205, 150, 9), (250, 170, 6)):
        for y in range(cy - r, cy + r + 1):
            for x in range(cx - r - 3, cx + r + 4):
                if ((x - cx) / (r + 3)) ** 2 + ((y - cy) / r) ** 2 <= 1:
                    g[y][x] = "~"
    for (x0, y0) in ((140, 164), (156, 164), (132, 176), (164, 176)):
        rect(x0, y0, x0 + 4, y0 + 2, "f")
    # castle plots / footprints
    for c in CASTLES:
        px0, py0, px1, py1 = c["plot"]
        fx0, fy0, fx1, fy1 = c["footprint"]
        if c["status"] == "reserved":
            rect(fx0, fy0, fx1, fy1, "r")
        else:
            rect(fx0, fy0, fx1, fy1, "c")
        for (ax, ay) in c["gate_apron"]:
            g[ay][ax] = "="
    # scattered trees (never on roads/plots/hub, never within 2 of a road)
    def free(x, y):
        for c in CASTLES:
            px0, py0, px1, py1 = c["plot"]
            if px0 - 2 <= x <= px1 + 2 and py0 - 2 <= y <= py1 + 2:
                return False
        for yy in range(y - 2, y + 3):
            for xx in range(x - 2, x + 3):
                if 0 <= xx < W and 0 <= yy < H and g[yy][xx] in "=oPSl~f":
                    return False
        return True
    for _ in range(900):
        x, y = rng.randrange(4, W - 4), rng.randrange(4, H - 4)
        if g[y][x] == "." and free(x, y):
            g[y][x] = "T"
    g[REALM_PORTAL["y"]][REALM_PORTAL["x"]] = "P"
    g[SPAWN["y"]][SPAWN["x"]] = "S"
    return ["".join(r) for r in g], roads


# ---------------------------------------------------------------- gothic castle footprint grid (24x24)
BASE_ROWS = (["M" * 24] * 2 + ["MMWWWWWWWWWWWWWWWWWWWWMM"] * 2 + ["MMWWFFFKKKKKKKKKKFFFWWMM"] * 6 +
             ["MMWWFFFFFFFFFFFFFFFFWWMM"] * 10 + ["MMWWWAAAWWWPPWWWAAAWWWMM", "MMWWWWWWWWWGGWWWWWWWWWMM"] +
             ["MMMMMMMMMMMBBMMMMMMMMMMM"] * 2)
GOTHIC_KEEP_DOORS = [(11, 9), (12, 9)]   # local tiles in the keep's south face -> floor 1
GRID_LEGEND = {"M": "moat (blocked)", "W": "wall/tower (blocked)", "K": "keep (blocked, sprite)", "F": "bailey floor",
               "A": "wall-walk (NPC only, not player-reachable)", "P": "gate passage", "G": "portcullis (walkable when open)",
               "B": "drawbridge (walkable when down)", "D": "keep door -> interior floor 1 (transition)"}
CASTLE_WALK = set("FPGBD")


def gothic_grid():
    rows = [list(r) for r in BASE_ROWS]
    for (x, y) in GOTHIC_KEEP_DOORS:
        rows[y][x] = "D"
    return ["".join(r) for r in rows]


# ---------------------------------------------------------------- interior floors (planes)
FW, FH = 18, 12
FLOOR_LEGEND = {"#": "wall (blocked)", ".": "floor", "D": "door (walkable, between rooms)", "U": "stairs up (transition)",
                "V": "stairs down (transition)", "E": "exit to bailey (transition)", "x": "furniture (blocked, see furniture list)"}
FLOOR_WALK = set(".DUVE")
STAIR_UP, STAIR_DOWN = (16, 9), (16, 10)
ARRIVE_UP, ARRIVE_DOWN = (15, 10), (15, 9)   # arrival after going up / going down

FLOORS = [
    {"level": 1, "name": "Hall of Shadows", "height_m": 0.0,
     "rooms": [("chapel", "Black Chapel", 1, 1, 6, 4), ("guard", "Guard Room", 8, 1, 11, 4),
               ("kitchen", "Kitchen", 13, 1, 16, 4), ("hall", "Entrance Hall", 1, 6, 16, 10)],
     "doors": [(7, 3), (12, 3), (4, 5), (10, 5)], "exit": [(8, 11), (9, 11)],
     "furniture": [("altar", 3, 1), ("altar", 4, 1), ("pew", 2, 3), ("pew", 5, 3), ("weapon_rack", 8, 1), ("table", 10, 2),
                   ("hearth", 14, 1), ("hearth", 15, 1), ("table", 14, 3), ("pillar", 4, 8), ("pillar", 12, 8)]},
    {"level": 2, "name": "Great Hall", "height_m": 4.2,
     "rooms": [("great_hall", "Great Hall", 1, 1, 10, 10), ("library", "Library", 12, 1, 16, 5), ("lobby", "Stair Lobby", 12, 7, 16, 10)],
     "doors": [(11, 4), (11, 8)], "exit": [],
     "furniture": [("throne", 5, 1), ("long_table", 3, 4), ("long_table", 3, 5), ("long_table", 3, 6), ("long_table", 7, 4),
                   ("long_table", 7, 5), ("long_table", 7, 6), ("brazier", 1, 10), ("brazier", 10, 10),
                   ("bookshelf", 12, 1), ("bookshelf", 13, 1), ("bookshelf", 14, 1), ("bookshelf", 15, 1), ("desk", 14, 3)]},
    {"level": 3, "name": "Lord's Chambers", "height_m": 8.4,
     "rooms": [("bedchamber", "Bedchamber", 1, 1, 5, 4), ("armoury", "Armoury", 7, 1, 11, 4), ("alchemist", "Alchemist's Den", 13, 1, 16, 4),
               ("corridor", "Corridor & Stair Lobby", 1, 6, 16, 7), ("lobby", "Stair Lobby", 13, 8, 16, 10), ("treasury", "Treasury", 1, 9, 11, 10)],
     "doors": [(3, 5), (9, 5), (14, 5), (4, 8)], "exit": [],
     "furniture": [("bed", 1, 1), ("bed", 2, 1), ("wardrobe", 5, 1), ("weapon_rack", 7, 1), ("weapon_rack", 11, 1), ("armour_stand", 9, 1),
                   ("cauldron", 14, 2), ("bookshelf", 16, 1), ("chest", 2, 9), ("chest", 6, 9), ("chest", 9, 9)]},
    {"level": 4, "name": "Spire Top", "height_m": 12.6,
     "rooms": [("roof_walk", "Roof Walk", 3, 2, 14, 8), ("bell", "Bell Chamber", 5, 4, 12, 6), ("stair_head", "Stair Head", 14, 9, 16, 10)],
     "walls": [(4, 3, 13, 7)], "doors": [(8, 7)], "exit": [],
     "furniture": [("bell", 8, 5), ("bell", 9, 5)]},
]


def floor_grid(f, top):
    g = [["#"] * FW for _ in range(FH)]
    for (_, _, x0, y0, x1, y1) in f["rooms"]:
        for y in range(y0, y1 + 1):
            for x in range(x0, x1 + 1):
                g[y][x] = "."
    for (x0, y0, x1, y1) in f.get("walls", []):     # hollow wall ring (bell chamber)
        for x in range(x0, x1 + 1):
            g[y0][x] = g[y1][x] = "#"
        for y in range(y0, y1 + 1):
            g[y][x0] = g[y][x1] = "#"
        for (_, _, rx0, ry0, rx1, ry1) in f["rooms"]:
            if rx0 > x0 and ry0 > y0 and rx1 < x1 and ry1 < y1:
                for y in range(ry0, ry1 + 1):
                    for x in range(rx0, rx1 + 1):
                        g[y][x] = "."
    for (x, y) in f["doors"]:
        g[y][x] = "D"
    for (x, y) in f["exit"]:
        g[y][x] = "E"
    for (_, x, y) in f["furniture"]:
        g[y][x] = "x"
    if f["level"] < top:
        g[STAIR_UP[1]][STAIR_UP[0]] = "U"
    if f["level"] > 1:
        g[STAIR_DOWN[1]][STAIR_DOWN[0]] = "V"
    return ["".join(r) for r in g]


def room_at(f, x, y):
    best = None
    for (kind, name, x0, y0, x1, y1) in f["rooms"]:
        if x0 <= x <= x1 and y0 <= y <= y1:
            if best is None or (x1 - x0) * (y1 - y0) < (best[4] - best[2]) * (best[5] - best[3]):
                best = (kind, name, x0, y0, x1, y1)
    return best


def gothic_data():
    fx0, fy0, _, _ = CASTLES[0]["footprint"]
    top = len(FLOORS)
    floors = []
    for f in FLOORS:
        grid = floor_grid(f, top)
        stairs = []
        if f["level"] < top:
            stairs.append({"tile": list(STAIR_UP), "dir": "up", "to_plane": "gothic_f%d" % (f["level"] + 1), "arrive": list(ARRIVE_UP)})
        if f["level"] > 1:
            stairs.append({"tile": list(STAIR_DOWN), "dir": "down", "to_plane": "gothic_f%d" % (f["level"] - 1), "arrive": list(ARRIVE_DOWN)})
        floors.append({
            "plane": "gothic_f%d" % f["level"], "level": f["level"], "name": f["name"], "width": FW, "height": FH,
            "height_m": f["height_m"], "rows": grid, "sprite_2x": "floors/gothic_f%d.png" % f["level"],
            "sprite_1x": "floors/1x/gothic_f%d.png" % f["level"],
            "rooms": [{"kind": k, "name": n, "rect": [x0, y0, x1, y1]} for (k, n, x0, y0, x1, y1) in f["rooms"]],
            "doors": [{"tile": [x, y]} for (x, y) in f["doors"]],
            "stairs": stairs,
            "exits": [{"tile": [x, y], "to_plane": "realm", "arrive": [fx0 + 11 + i, fy0 + 10]} for i, (x, y) in enumerate(f["exit"])],
            "furniture": [{"kind": k, "tile": [x, y]} for (k, x, y) in f["furniture"]],
        })
    grid = gothic_grid()
    return {
        "id": "gothic", "name": "Duskspire Keep", "realm": "castle_realm", "flag": "USE_CASTLE_REALM", "version": 1,
        "footprint": {"x0": fx0, "y0": fy0, "x1": fx0 + 23, "y1": fy0 + 23, "w": 24, "h": 24, "plane": "realm"},
        "grid_legend": GRID_LEGEND, "walkability": grid,
        "walkable_chars": sorted(CASTLE_WALK),
        "keep_doors": [{"tile_local": [x, y], "tile": [fx0 + x, fy0 + y], "to_plane": "gothic_f1", "arrive": [8 + i, 10]}
                       for i, (x, y) in enumerate(GOTHIC_KEEP_DOORS)],
        "trigger_tiles": {
            "outer": [[fx0 + x, fy0 + 24] for x in (10, 11, 12, 13)],
            "hold": [[fx0 + x, fy0 + y] for y in (20, 21, 22, 23) for x in (11, 12)],
            "inner": [[fx0 + x, fy0 + y] for y in (18, 19) for x in (11, 12)],
            "rule": "same as castle_v2: gate opens while the local player stands on outer/inner/hold; closes when none"},
        "floor_legend": FLOOR_LEGEND, "floor_walkable_chars": sorted(FLOOR_WALK), "floors": floors,
    }


# ---------------------------------------------------------------- checker
def check(realm_rows, gd, verbose=True):
    errs, log = [], []
    fx0, fy0 = gd["footprint"]["x0"], gd["footprint"]["y0"]
    cgrid = gd["walkability"]
    floors = {f["plane"]: f for f in gd["floors"]}
    for f in gd["floors"]:
        for r in f["rows"]:
            if len(r) != FW:
                errs.append("%s row width %d" % (f["plane"], len(r)))
        if len(f["rows"]) != FH:
            errs.append("%s height" % f["plane"])

    def walk(plane, x, y):
        if plane == "realm":
            if not (0 <= x < W and 0 <= y < H):
                return False
            ch = realm_rows[y][x]
            if ch == "c":
                return cgrid[y - fy0][x - fx0] in CASTLE_WALK
            return LEGEND[ch][1]
        f = floors[plane]
        return 0 <= x < FW and 0 <= y < FH and f["rows"][y][x] in FLOOR_WALK

    # transitions
    trans = {}
    trans[("realm", REALM_PORTAL["x"], REALM_PORTAL["y"])] = ("overworld", OVERWORLD_PORTAL["return_arrival"][0], OVERWORLD_PORTAL["return_arrival"][1])
    for d in gd["keep_doors"]:
        trans[("realm",) + tuple(d["tile"])] = (d["to_plane"],) + tuple(d["arrive"])
    for f in gd["floors"]:
        for s in f["stairs"] + f["exits"]:
            trans[(f["plane"],) + tuple(s["tile"])] = (s["to_plane"],) + tuple(s["arrive"])
    # arrivals valid
    for k, (p, x, y) in trans.items():
        if p == "overworld":
            continue
        if not walk(p, x, y):
            errs.append("arrival %s not walkable (from %s)" % ((p, x, y), k))
        if (p, x, y) in trans:
            errs.append("arrival %s is itself a transition" % ((p, x, y),))
    # stair symmetry: up from A arrives next to a down stair that returns next to the up stair
    for f in gd["floors"]:
        for s in f["stairs"]:
            dest = floors[s["to_plane"]]
            back = [b for b in dest["stairs"] if b["to_plane"] == f["plane"]]
            if not back:
                errs.append("%s stair %s has no return stair on %s" % (f["plane"], s["dir"], s["to_plane"]))
                continue
            bt = back[0]["tile"]
            if abs(bt[0] - s["arrive"][0]) + abs(bt[1] - s["arrive"][1]) != 1:
                errs.append("%s->%s arrival not adjacent to return stair" % (f["plane"], s["to_plane"]))
            if abs(back[0]["arrive"][0] - s["tile"][0]) + abs(back[0]["arrive"][1] - s["tile"][1]) != 1:
                errs.append("%s<-%s return arrival not adjacent to stair" % (f["plane"], s["to_plane"]))
    # doors sit between two different rooms (walkable on opposite sides)
    for f in gd["floors"]:
        fl = [x for x in FLOORS if x["level"] == f["level"]][0]
        for d in f["doors"]:
            x, y = d["tile"]
            pairs = [((x - 1, y), (x + 1, y)), ((x, y - 1), (x, y + 1))]
            ok = False
            for a, b in pairs:
                if walk(f["plane"], *a) and walk(f["plane"], *b):
                    ra, rb = room_at(fl, *a), room_at(fl, *b)
                    ok = ok or (ra and rb and ra[0] != rb[0])
            if not ok:
                errs.append("%s door %s does not join two rooms" % (f["plane"], d["tile"]))
    # BFS from the overworld portal
    start = ("realm", SPAWN["x"], SPAWN["y"])
    seen = {start}
    dq = deque([start])
    used = set()
    while dq:
        p, x, y = dq.popleft()
        if (p, x, y) in trans:
            used.add((p, x, y))
            q = trans[(p, x, y)]
            if q[0] != "overworld" and q not in seen:
                seen.add(q); dq.append(q)
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            q = (p, x + dx, y + dy)
            if q not in seen and walk(*q):
                seen.add(q); dq.append(q)
    log.append("overworld portal (%d,%d) -> realm spawn (%d,%d): BFS visited %d tiles over %d planes" % (
        OVERWORLD_PORTAL["x"], OVERWORLD_PORTAL["y"], SPAWN["x"], SPAWN["y"], len(seen), len({s[0] for s in seen})))
    if ("realm", REALM_PORTAL["x"], REALM_PORTAL["y"]) not in seen:
        errs.append("realm return portal unreachable")
    for c in CASTLES:
        for a in c["gate_apron"]:
            if ("realm",) + tuple(a) not in seen:
                errs.append("%s gate apron %s unreachable" % (c["id"], a))
    for ch, what in (("B", "drawbridge"), ("G", "portcullis"), ("F", "bailey"), ("D", "keep door")):
        tiles = [("realm", fx0 + x, fy0 + y) for y, r in enumerate(cgrid) for x, c in enumerate(r) if c == ch]
        n = sum(t in seen for t in tiles)
        log.append("gothic %-10s %d/%d tiles reachable" % (what, n, len(tiles)))
        if n != len(tiles):
            errs.append("gothic %s: %d/%d reachable" % (what, n, len(tiles)))
    for f in gd["floors"]:
        fl = [x for x in FLOORS if x["level"] == f["level"]][0]
        wt = [(f["plane"], x, y) for y, r in enumerate(f["rows"]) for x, c in enumerate(r) if c in FLOOR_WALK]
        n = sum(t in seen for t in wt)
        rooms_ok = []
        for (kind, name, x0, y0, x1, y1) in fl["rooms"]:
            hit = any((f["plane"], x, y) in seen for y in range(y0, y1 + 1) for x in range(x0, x1 + 1))
            rooms_ok.append(hit)
            if not hit:
                errs.append("%s room %s unreachable" % (f["plane"], name))
        log.append("floor %d %-16s walkable %d/%d reachable, rooms %d/%d" % (f["level"], f["name"], n, len(wt), sum(rooms_ok), len(rooms_ok)))
        if n != len(wt):
            errs.append("%s: %d walkable tiles unreachable" % (f["plane"], len(wt) - n))
    for k in trans:
        if k not in used and k[0] != "overworld":
            errs.append("transition %s never reached" % (k,))
    # plots: no overlap, spacing between footprints >= 30
    for i, a in enumerate(CASTLES):
        for b in CASTLES[i + 1:]:
            ax0, ay0, ax1, ay1 = a["footprint"]; bx0, by0, bx1, by1 = b["footprint"]
            gap = max(bx0 - ax1, ax0 - bx1, by0 - ay1, ay0 - by1) - 1
            pa, pb = a["plot"], b["plot"]
            overlap = not (pa[2] < pb[0] or pb[2] < pa[0] or pa[3] < pb[1] or pb[3] < pa[1])
            log.append("spacing %-10s <-> %-10s %3d tiles%s" % (a["id"], b["id"], gap, "  PLOT OVERLAP" if overlap else ""))
            if gap < 30 or overlap:
                errs.append("plots %s/%s too close (gap %d, overlap %s)" % (a["id"], b["id"], gap, overlap))
    if verbose:
        for l in log:
            print("  " + l)
        print("RESULT:", "PASS" if not errs else "FAIL")
        for e in errs:
            print("  ERROR", e)
    return errs, log


def main():
    out = sys.argv[sys.argv.index("--out") + 1] if "--out" in sys.argv else os.path.join(os.path.dirname(__file__), "..", "json")
    os.makedirs(out, exist_ok=True)
    rows, roads = build_realm()
    gd = gothic_data()
    realm = {"id": "castle_realm", "name": "Castle Realm", "flag": "USE_CASTLE_REALM", "version": 1, "width": W, "height": H,
             "legend": {k: {"server_tile": v[0], "walkable": v[1], "what": v[2]} for k, v in LEGEND.items()},
             "rows": rows, "spawn": SPAWN, "return_portal": REALM_PORTAL, "hub": HUB, "overworld_portal": OVERWORLD_PORTAL,
             "roads": roads, "castles": CASTLES,
             "note": "castle footprints ('c') are blocked in the realm rows; walkability inside comes from each castle's data file grid"}
    json.dump(realm, open(os.path.join(out, "castle_realm_map.json"), "w"), indent=1)
    json.dump(gd, open(os.path.join(out, "gothic_castle.json"), "w"), indent=1)
    errs, log = check(rows, gd)
    json.dump({"pass": not errs, "errors": errs, "log": log}, open(os.path.join(out, "realm_check.json"), "w"), indent=1)
    return 1 if errs else 0


if __name__ == "__main__":
    sys.exit(main())
