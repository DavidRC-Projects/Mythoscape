"""realm_data.py (v3, phase 3) - Castle Realm map + #1 Duskspire Keep + #2 White Rose Castle + #3 King's Castle.
Multi-castle, multi-BUILDING, multi-floor checker (a castle can now have several enterable buildings, e.g. keep +
barracks). Every building's interior must match its exterior footprint (legacy gothic keep = warning only).

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
OVERWORLD_PORTAL = {"x": 111, "y": 43, "approach": [111, 44], "return_arrival": [111, 45],
                    "note": "grass NW of the live castle, west of the north road (x117-118). 3x3 (110-112,42-44) is grass on main ca336ee"}
HUB = {"x0": 138, "y0": 168, "x1": 162, "y1": 188}
REALM_PORTAL = {"x": 150, "y": 186}
SPAWN = {"x": 150, "y": 182}

# castle registry: every castle = plot (reserved land incl. sprite overdraw) + footprint (grid) + gate apron
CASTLES = [
    {"id": "gothic", "name": "Duskspire Keep", "phase": 1, "status": "built", "plot": [20, 40, 80, 100],
     "footprint": [38, 52, 61, 75], "gate_apron": [[49, 76], [50, 76]], "data": "gothic_castle.json",
     "sprite_overdraw_tiles_up": 16, "size_vs_original": 1.0},
    {"id": "king", "name": "King's Castle", "phase": 3, "status": "built", "plot": [110, 8, 190, 90],
     "footprint": [120, 16, 179, 75], "gate_apron": [[149, 76], [150, 76]], "data": "king_castle.json", "size_vs_original": 6.25,
     "sprite_overdraw_tiles_up": 9},
    {"id": "white_rose", "name": "White Rose Castle", "phase": 2, "status": "built", "plot": [220, 26, 292, 100],
     "footprint": [231, 36, 278, 83], "gate_apron": [[254, 84], [255, 84]], "data": "white_rose_castle.json", "size_vs_original": 4.0,
     "sprite_overdraw_tiles_up": 12},
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


def floor_grid(f, top, fw=None, fh=None, su=None, sd=None):
    fw, fh, su, sd = fw or FW, fh or FH, su or STAIR_UP, sd or STAIR_DOWN
    g = [["#"] * fw for _ in range(fh)]
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
        g[su[1]][su[0]] = "U"
    if f["level"] > 1:
        g[sd[1]][sd[0]] = "V"
    return ["".join(r) for r in g]


def room_at(f, x, y):
    best = None
    for (kind, name, x0, y0, x1, y1) in f["rooms"]:
        if x0 <= x <= x1 and y0 <= y <= y1:
            if best is None or (x1 - x0) * (y1 - y0) < (best[4] - best[2]) * (best[5] - best[3]):
                best = (kind, name, x0, y0, x1, y1)
    return best


# ---------------------------------------------------------------- castle #2: White Rose Castle (48x48)
ROSE_KEEP = (12, 5, 35, 15)        # tiles (inclusive) -> 24 x 11, identical to the interior floor size
ROSE_KEEP_DOORS = [(23, 15), (24, 15)]
ROSE_FW, ROSE_FH = 24, 11
ROSE_SU, ROSE_SD, ROSE_AU, ROSE_AD = (21, 8), (22, 8), (22, 9), (21, 9)
ROSE_GRID_LEGEND = dict(GRID_LEGEND)
ROSE_GRID_LEGEND.update({"K": "palace / building / tower (blocked, sprite)", "N": "fountain basin (blocked)",
                         "H": "flower bed, hedge or tree (blocked)"})


def rose_grid():
    n = 48
    g = [["F"] * n for _ in range(n)]
    for y in range(n):
        for x in range(n):
            if x < 3 or y < 3 or x > 44 or y > 44:
                g[y][x] = "M"
            elif x < 5 or y < 5 or x > 42 or y > 42:
                g[y][x] = "W"
    def circ(cx, cy, r, ch):
        for y in range(n):
            for x in range(n):
                if (x + 0.5 - cx) ** 2 + (y + 0.5 - cy) ** 2 <= r * r:
                    g[y][x] = ch
    for c in ((4.4, 4.4), (43.6, 4.4), (4.4, 43.6), (43.6, 43.6)):
        circ(c[0], c[1], 2.5, "W")
    for c in ((4.0, 24.0), (44.0, 24.0)):
        circ(c[0], c[1], 1.9, "W")
    for c in ((20.3, 44.6), (27.7, 44.6)):
        circ(c[0], c[1], 2.1, "W")
    for y in range(41, 45):
        for x in range(20, 28):
            g[y][x] = "W"
    for y in range(41, 44):
        for x in (23, 24):
            g[y][x] = "P"
    for x in (23, 24):
        g[44][x] = "G"
        for y in (45, 46, 47):
            g[y][x] = "B"
    x0, y0, x1, y1 = ROSE_KEEP
    for y in range(y0, y1 + 1):
        for x in range(x0, x1 + 1):
            g[y][x] = "K"
    for (x, y) in ROSE_KEEP_DOORS:
        g[y][x] = "D"
    circ(24.0, 28.0, 3.3, "N")
    for (a0, b0, a1, b1) in ((14, 20, 21, 26), (27, 20, 34, 26), (14, 30, 21, 36), (27, 30, 34, 36),
                             (6, 42, 19, 43), (29, 42, 42, 43), (5, 6, 6, 17), (42, 6, 43, 17), (5, 33, 6, 41), (42, 33, 43, 41)):
        for y in range(b0, b1):
            for x in range(a0, a1):
                if g[y][x] == "F":
                    g[y][x] = "H"
    for (a0, b0, a1, b1) in ((6, 19, 12, 31), (37, 19, 43, 32)):
        for y in range(b0, b1):
            for x in range(a0, a1):
                if g[y][x] in "FH":
                    g[y][x] = "K"
    for (x, y) in ((8, 38), (40, 38), (8, 9), (39, 9), (16, 40), (32, 40)):
        g[y][x] = "H"
    return ["".join(r) for r in g]


ROSE_FLOORS = [
    {"level": 1, "name": "Rose Hall", "height_m": 0.0,
     "rooms": [("kitchen", "Kitchen", 1, 1, 6, 4), ("pantry", "Pantry & Still-room", 1, 6, 6, 9), ("entrance", "Entrance Hall", 8, 1, 15, 9),
               ("chapel", "Oratory", 17, 1, 22, 5), ("stair_hall", "Grand Stair", 17, 7, 22, 9)],
     "doors": [(7, 2), (3, 5), (16, 3), (16, 8)], "exit": [(11, 10), (12, 10)],
     "furniture": [("hearth", 2, 1), ("hearth", 3, 1), ("table", 4, 3), ("table", 5, 3), ("barrel", 6, 1), ("shelf", 1, 3),
                   ("barrel", 1, 9), ("barrel", 2, 9), ("shelf", 5, 7), ("shelf", 6, 9), ("sack", 4, 9),
                   ("statue", 8, 1), ("statue", 15, 1), ("planter", 8, 9), ("planter", 15, 9), ("fountain_small", 11, 4), ("fountain_small", 12, 4),
                   ("altar", 19, 1), ("altar", 20, 1), ("pew", 18, 3), ("pew", 21, 3), ("candelabra", 17, 1), ("candelabra", 22, 1),
                   ("planter", 17, 9), ("statue", 20, 7)]},
    {"level": 2, "name": "Great Hall of Roses", "height_m": 4.2,
     "rooms": [("great_hall", "Great Hall of Roses", 1, 1, 14, 9), ("solar", "Solar", 16, 1, 22, 5), ("stair_hall", "Grand Stair", 16, 7, 22, 9)],
     "doors": [(15, 8), (19, 6)], "exit": [],
     "furniture": [("throne", 7, 1), ("throne", 8, 1), ("long_table", 4, 4), ("long_table", 5, 4), ("long_table", 6, 4), ("long_table", 9, 4),
                   ("long_table", 10, 4), ("long_table", 11, 4), ("long_table", 4, 6), ("long_table", 5, 6), ("long_table", 6, 6),
                   ("long_table", 9, 6), ("long_table", 10, 6), ("long_table", 11, 6), ("harp", 1, 1), ("planter", 14, 1),
                   ("brazier", 1, 9), ("brazier", 14, 9), ("hearth", 3, 1),
                   ("bookshelf", 16, 1), ("bookshelf", 17, 1), ("desk", 20, 2), ("armchair", 18, 3), ("armchair", 21, 4), ("planter", 22, 1)]},
    {"level": 3, "name": "Royal Chambers", "height_m": 8.4,
     "rooms": [("bedchamber", "Queen's Bedchamber", 1, 1, 7, 4), ("chamber", "Lady's Chamber", 9, 1, 14, 4), ("bath", "Rose Bath", 16, 1, 22, 4),
               ("corridor", "Long Corridor", 1, 6, 19, 7), ("stair_hall", "Grand Stair", 20, 6, 22, 9), ("gallery", "Rose Gallery", 1, 9, 18, 9)],
     "doors": [(4, 5), (11, 5), (19, 5), (6, 8)], "exit": [],
     "furniture": [("bed_big", 1, 1), ("bed_big", 2, 1), ("wardrobe", 7, 1), ("dresser", 5, 1), ("armchair", 6, 4),
                   ("bed", 9, 1), ("wardrobe", 14, 1), ("desk", 12, 3), ("harp", 9, 4),
                   ("bath", 18, 2), ("bath", 19, 2), ("planter", 16, 1), ("planter", 22, 1), ("screen", 22, 3),
                   ("planter", 1, 9), ("statue", 18, 9)]},
    {"level": 4, "name": "Rose Terrace", "height_m": 12.6,
     "rooms": [("terrace", "Roof Terrace", 1, 1, 22, 9), ("conservatory", "Glass Conservatory", 6, 2, 15, 7), ("stair_head", "Stair Head", 20, 7, 22, 9)],
     "walls": [(5, 1, 16, 8)], "doors": [(10, 8)], "exit": [],
     "furniture": [("planter", 1, 1), ("planter", 22, 1), ("planter", 1, 9), ("planter", 3, 5), ("planter", 18, 3), ("telescope", 19, 1),
                   ("fountain_small", 10, 4), ("fountain_small", 11, 4), ("planter", 6, 2), ("planter", 15, 2), ("planter", 6, 7),
                   ("planter", 15, 7), ("bench_in", 8, 6), ("bench_in", 13, 6)]},
]

# ---------------------------------------------------------------- castle #3: King's Castle (60x60, concentric)
KING_KEEP = (22, 17, 37, 30)          # tiles inclusive -> 16 x 14 = interior floor size
KING_BARRACKS = (48, 18, 54, 33)      # 7 x 16 = barracks interior size
KING_GRID_LEGEND = dict(ROSE_GRID_LEGEND)
KING_GRID_LEGEND.update({"K": "keep / barracks / stables / towers (blocked, sprite)", "N": "statue of the king (blocked)",
                         "H": "garden bed, market stall, tilt barrier, tree or well (blocked)",
                         "D": "door -> building interior (keep or barracks, see doors[])"})


def king_grid():
    n = 60
    g = [["F"] * n for _ in range(n)]
    for y in range(n):
        for x in range(n):
            if x < 3 or y < 3 or x > 56 or y > 56:
                g[y][x] = "M"
            elif x < 5 or y < 5 or x > 54 or y > 54:
                g[y][x] = "W"
            elif (13 <= x <= 46 and 13 <= y <= 46) and not (15 <= x <= 44 and 15 <= y <= 44):
                g[y][x] = "W"
    def circ(cx, cy, r, ch="W"):
        for y in range(n):
            for x in range(n):
                if (x + 0.5 - cx) ** 2 + (y + 0.5 - cy) ** 2 <= r * r:
                    g[y][x] = ch
    for c in ((4.2, 4.2), (55.8, 4.2), (4.2, 55.8), (55.8, 55.8)):
        circ(c[0], c[1], 2.5)
    for c in ((4.0, 30.0), (56.0, 30.0), (30.0, 4.0), (17.0, 4.0), (43.0, 4.0), (4.0, 17.0), (56.0, 17.0), (4.0, 43.0), (56.0, 43.0)):
        circ(c[0], c[1], 1.9)
    for c in ((14.0, 14.0), (46.0, 14.0), (14.0, 46.0), (46.0, 46.0)):
        circ(c[0], c[1], 2.3)
    for y in range(44, 47):                     # inner gatehouse
        for x in range(26, 34):
            g[y][x] = "W"
    for c in ((26.6, 46.4), (33.4, 46.4)):
        circ(c[0], c[1], 1.9)
    for y in range(52, 57):                     # grand outer gatehouse
        for x in range(24, 36):
            g[y][x] = "W"
    for c in ((24.7, 56.3), (35.3, 56.3)):
        circ(c[0], c[1], 2.6)
    for x in (29, 30):
        for y in range(44, 47):
            g[y][x] = "P"
        for y in range(52, 56):
            g[y][x] = "P"
        g[56][x] = "G"
        for y in (57, 58, 59):
            g[y][x] = "B"
    for (x0, y0, x1, y1) in (KING_KEEP, KING_BARRACKS, (5, 18, 10, 33)):
        for y in range(y0, y1 + 1):
            for x in range(x0, x1 + 1):
                g[y][x] = "K"
    for (x, y) in ((29, 30), (30, 30), (51, 33)):
        g[y][x] = "D"
    for (x, y) in ((29, 37), (30, 37), (29, 38), (30, 38)):
        g[y][x] = "N"
    blocked = []
    for (a0, b0, a1, b1) in ((16, 18, 20, 28), (40, 18, 44, 28)):
        blocked += [(x, y) for y in range(b0, b1) for x in range(a0, a1)]
    for lx in (9, 13, 17, 21):
        blocked += [(lx - 1, 49), (lx, 49)]
    blocked += [(x, 48) for x in range(37, 50)]
    for (lx, ly) in ((9, 8.5), (14, 9.5), (19, 8.5), (24, 9.5), (36, 9.5), (41, 8.5), (46, 9.5), (51, 8.5), (8.5, 40), (51.5, 40), (8.5, 44), (51.5, 44)):
        blocked.append((int(lx), int(ly)))
    blocked += [(8, 12), (9, 12)]
    for (x, y) in blocked:
        if g[y][x] == "F":
            g[y][x] = "H"
    return ["".join(r) for r in g]


KING_FLOORS = [
    {"level": 1, "name": "Great Hall", "height_m": 0.0,
     "rooms": [("great_hall", "Great Hall", 1, 1, 14, 7), ("kitchen", "Royal Kitchen", 1, 9, 4, 12), ("vestibule", "Vestibule", 6, 9, 10, 12),
               ("stair_hall", "Grand Stair", 12, 9, 14, 12)],
     "doors": [(8, 8), (5, 10), (11, 10), (2, 8)], "exit": [(7, 13), (8, 13)],
     "furniture": [("hearth", 7, 1), ("hearth", 8, 1), ("long_table", 3, 3), ("long_table", 4, 3), ("long_table", 5, 3), ("long_table", 10, 3),
                   ("long_table", 11, 3), ("long_table", 12, 3), ("long_table", 3, 5), ("long_table", 4, 5), ("long_table", 5, 5),
                   ("long_table", 10, 5), ("long_table", 11, 5), ("long_table", 12, 5), ("brazier", 1, 1), ("brazier", 14, 1),
                   ("armour_stand", 1, 7), ("armour_stand", 14, 7),
                   ("hearth", 1, 9), ("table", 3, 11), ("barrel", 4, 12), ("barrel", 1, 12), ("shelf", 4, 9),
                   ("statue", 6, 9), ("statue", 10, 9), ("planter", 6, 12), ("planter", 10, 12), ("planter", 12, 12)]},
    {"level": 2, "name": "Throne Room", "height_m": 4.5,
     "rooms": [("throne_room", "Throne Room", 1, 1, 10, 12), ("council", "Council Chamber", 12, 1, 14, 7), ("stair_hall", "Grand Stair", 12, 9, 14, 12)],
     "doors": [(11, 10), (13, 8)], "exit": [],
     "furniture": [("throne", 5, 1), ("throne", 6, 1), ("armour_stand", 3, 1), ("armour_stand", 8, 1), ("brazier", 1, 1), ("brazier", 10, 1),
                   ("pillar", 3, 5), ("pillar", 8, 5), ("pillar", 3, 9), ("pillar", 8, 9), ("statue", 1, 12), ("statue", 10, 12),
                   ("table", 13, 3), ("table", 13, 4), ("bookshelf", 12, 1), ("bookshelf", 14, 1), ("armchair", 12, 7), ("armchair", 14, 7),
                   ("planter", 12, 12)]},
    {"level": 3, "name": "Royal Apartments", "height_m": 9.0,
     "rooms": [("bedchamber", "King's Bedchamber", 1, 1, 6, 5), ("chamber", "Queen's Chamber", 8, 1, 14, 5), ("corridor", "Royal Corridor", 1, 7, 14, 7),
               ("treasury", "Treasury", 1, 9, 5, 12), ("chapel", "Royal Chapel", 7, 9, 10, 12), ("stair_hall", "Grand Stair", 12, 9, 14, 12)],
     "doors": [(3, 6), (11, 6), (3, 8), (8, 8), (13, 8)], "exit": [],
     "furniture": [("bed_big", 2, 1), ("bed_big", 3, 1), ("wardrobe", 6, 1), ("armchair", 5, 4), ("bed_big", 10, 1), ("bed_big", 11, 1),
                   ("dresser", 14, 1), ("harp", 8, 1), ("armchair", 13, 4),
                   ("chest", 1, 9), ("chest", 5, 9), ("chest", 3, 12), ("gold_pile", 1, 12), ("gold_pile", 5, 12),
                   ("altar", 9, 9), ("altar", 10, 9), ("pew", 9, 11), ("pew", 10, 11), ("candelabra", 7, 9)]},
    {"level": 4, "name": "Battlements & Crown Room", "height_m": 13.5, "roof_open": True,
     "rooms": [("terrace", "Keep Battlements", 1, 1, 14, 12), ("crown_room", "Crown Room (Great Tower)", 5, 4, 10, 9),
               ("stair_head", "Stair Head", 12, 9, 14, 12)],
     "walls": [(4, 3, 11, 10)], "doors": [(7, 10)], "exit": [],
     "furniture": [("crown", 7, 6), ("crown", 8, 6), ("armour_stand", 5, 4), ("armour_stand", 10, 4), ("bookshelf", 6, 4), ("bookshelf", 9, 4),
                   ("telescope", 1, 1), ("brazier", 14, 1), ("brazier", 1, 12), ("cannon", 3, 1), ("cannon", 12, 1), ("banner_pole", 1, 6)]},
]
BARRACKS_FLOORS = [
    {"level": 1, "name": "Royal Guard Barracks", "height_m": 0.0,
     "rooms": [("armoury", "Armoury", 1, 1, 5, 2), ("dormitory", "Dormitory", 1, 4, 5, 8), ("mess_hall", "Mess Hall", 1, 10, 5, 14)],
     "doors": [(3, 3), (3, 9)], "exit": [(3, 15)],
     "furniture": [("weapon_rack", 1, 1), ("weapon_rack", 2, 1), ("weapon_rack", 4, 1), ("weapon_rack", 5, 1), ("armour_stand", 5, 2),
                   ("bunk", 1, 4), ("bunk", 1, 6), ("bunk", 1, 8), ("bunk", 5, 4), ("bunk", 5, 6), ("bunk", 5, 8), ("chest", 2, 4), ("chest", 4, 8),
                   ("long_table", 2, 11), ("long_table", 2, 12), ("long_table", 4, 11), ("long_table", 4, 12), ("hearth", 5, 10), ("barrel", 1, 14),
                   ("barrel", 5, 14)]},
]


def B(bid, prefix, floors, fw, fh, rect, doors, door_arrive, exit_arrive, su=None, sd=None, au=None, ad=None):
    return {"id": bid, "prefix": prefix, "floors": floors, "fw": fw, "fh": fh, "rect": rect, "doors": doors,
            "door_arrive": door_arrive, "exit_arrive": exit_arrive, "su": su, "sd": sd, "au": au, "ad": ad}


SPECS = {
    "gothic": {"name": "Duskspire Keep", "grid": gothic_grid, "legend": GRID_LEGEND, "buildings": [
        B("keep", "gothic", FLOORS, FW, FH, (7, 4, 16, 9), GOTHIC_KEEP_DOORS, [(8, 10), (9, 10)], [(11, 10), (12, 10)],
          STAIR_UP, STAIR_DOWN, ARRIVE_UP, ARRIVE_DOWN)]},
    "white_rose": {"name": "White Rose Castle", "grid": rose_grid, "legend": ROSE_GRID_LEGEND, "buildings": [
        B("keep", "rose", ROSE_FLOORS, ROSE_FW, ROSE_FH, ROSE_KEEP, ROSE_KEEP_DOORS, [(11, 9), (12, 9)], [(23, 16), (24, 16)],
          ROSE_SU, ROSE_SD, ROSE_AU, ROSE_AD)]},
    "king": {"name": "King's Castle", "grid": king_grid, "legend": KING_GRID_LEGEND, "buildings": [
        B("keep", "king", KING_FLOORS, 16, 14, KING_KEEP, [(29, 30), (30, 30)], [(7, 12), (8, 12)], [(29, 31), (30, 31)],
          (13, 10), (14, 10), (14, 11), (13, 11)),
        B("barracks", "king_barracks", BARRACKS_FLOORS, 7, 16, KING_BARRACKS, [(51, 33)], [(3, 14)], [(51, 34)])]},
}
FDEF = {}      # plane -> floor definition (for the checker)


def castle_data(cid):
    sp = SPECS[cid]
    c = [c for c in CASTLES if c["id"] == cid][0]
    fx0, fy0, fx1, fy1 = c["footprint"]
    floors, doors, rects = [], [], {}
    for b in sp["buildings"]:
        pre = b["prefix"]
        top = len(b["floors"])
        rects[b["id"]] = list(b["rect"])
        for f in b["floors"]:
            grid = floor_grid(f, top, b["fw"], b["fh"], b["su"] or (0, 0), b["sd"] or (0, 0)) if top > 1 else floor_grid(f, 1, b["fw"], b["fh"], (0, 0), (0, 0))
            stairs = []
            if f["level"] < top:
                stairs.append({"tile": list(b["su"]), "dir": "up", "to_plane": "%s_f%d" % (pre, f["level"] + 1), "arrive": list(b["au"])})
            if f["level"] > 1:
                stairs.append({"tile": list(b["sd"]), "dir": "down", "to_plane": "%s_f%d" % (pre, f["level"] - 1), "arrive": list(b["ad"])})
            plane = "%s_f%d" % (pre, f["level"])
            FDEF[plane] = f
            fl = {
                "plane": plane, "building": b["id"], "level": f["level"], "name": f["name"], "width": b["fw"], "height": b["fh"],
                "height_m": f["height_m"], "rows": grid, "sprite_2x": "floors/%s.png" % plane, "sprite_1x": "floors/1x/%s.png" % plane,
                "rooms": [{"kind": k, "name": n, "rect": [x0, y0, x1, y1]} for (k, n, x0, y0, x1, y1) in f["rooms"]],
                "doors": [{"tile": [x, y]} for (x, y) in f["doors"]],
                "stairs": stairs,
                "exits": [{"tile": [x, y], "to_plane": "realm", "arrive": [fx0 + b["exit_arrive"][i][0], fy0 + b["exit_arrive"][i][1]]}
                          for i, (x, y) in enumerate(f["exit"])],
                "furniture": [{"kind": k, "tile": [x, y]} for (k, x, y) in f["furniture"]],
            }
            if f.get("roof_open"):
                fl["roof_open"] = True
            floors.append(fl)
        for i, (x, y) in enumerate(b["doors"]):
            doors.append({"tile_local": [x, y], "tile": [fx0 + x, fy0 + y], "to_plane": "%s_f1" % pre, "arrive": list(b["door_arrive"][i]),
                          "building": b["id"]})
    grid = sp["grid"]()
    n = len(grid)
    gcols = [x for x, ch in enumerate(grid[n - 1]) if ch == "B"]
    brow0 = min(y for y, r in enumerate(grid) if "B" in r)
    prow = [y for y, r in enumerate(grid) if ("P" in r or "G" in r) and y > n // 2]
    kr = sp["buildings"][0]["rect"]
    out = {
        "id": cid, "name": sp["name"], "realm": "castle_realm", "flag": "USE_CASTLE_REALM", "version": 1,
        "footprint": {"x0": fx0, "y0": fy0, "x1": fx0 + n - 1, "y1": fy0 + n - 1, "w": n, "h": n, "plane": "realm"},
        "keep_rect_local": list(kr), "building_rects_local": rects,
        "grid_legend": sp["legend"], "walkability": grid, "walkable_chars": sorted(CASTLE_WALK),
        "keep_doors": doors,
        "trigger_tiles": {
            "outer": [[fx0 + x, fy0 + n] for x in range(gcols[0] - 1, gcols[-1] + 2)],
            "hold": [[fx0 + x, fy0 + y] for y in list(prow) + list(range(brow0, n)) for x in gcols],
            "inner": [[fx0 + x, fy0 + y] for y in (min(prow) - 2, min(prow) - 1) for x in gcols],
            "rule": "same as castle_v2: gate opens while the local player stands on outer/inner/hold; closes when none"},
        "floor_legend": FLOOR_LEGEND, "floor_walkable_chars": sorted(FLOOR_WALK), "floors": floors,
    }
    return out


def gothic_data():
    return castle_data("gothic")


# ---------------------------------------------------------------- checker (all built castles, all planes)
def check(realm_rows, datas, verbose=True):
    errs, log = [], []
    by_fp = []
    floors = {}
    fdefs = {}
    for cid, gd in datas.items():
        by_fp.append((gd["footprint"], gd["walkability"]))
        for f in gd["floors"]:
            floors[f["plane"]] = f
            fdefs[f["plane"]] = FDEF[f["plane"]]
            for r in f["rows"]:
                if len(r) != f["width"]:
                    errs.append("%s row width %d" % (f["plane"], len(r)))
            if len(f["rows"]) != f["height"]:
                errs.append("%s height" % f["plane"])
        # exterior/interior size consistency, per enterable building
        for bid, (kx0, ky0, kx1, ky1) in gd["building_rects_local"].items():
            kw, kh = kx1 - kx0 + 1, ky1 - ky0 + 1
            bf = [f for f in gd["floors"] if f.get("building", "keep") == bid][0]
            fw, fh = bf["width"], bf["height"]
            ok = (kw, kh) == (fw, fh)
            log.append("%-10s %-8s exterior %dx%d tiles vs interior %dx%d -> %s" % (
                cid, bid, kw, kh, fw, fh, "MATCH" if ok else "mismatch %.2fx area (legacy phase-1 castle, warning only)" % (fw * fh / (kw * kh))))
            if not ok and cid != "gothic":
                errs.append("%s %s interior %dx%d does not match exterior %dx%d" % (cid, bid, fw, fh, kw, kh))
            for d in gd["keep_doors"]:
                if d.get("building", "keep") == bid:
                    dx, dy = d["tile_local"]
                    if not (kx0 <= dx <= kx1 and ky0 <= dy <= ky1):
                        errs.append("%s door %s outside building %s" % (cid, d["tile_local"], bid))

    def walk(plane, x, y):
        if plane == "realm":
            if not (0 <= x < W and 0 <= y < H):
                return False
            ch = realm_rows[y][x]
            if ch == "c":
                for fp, grid in by_fp:
                    if fp["x0"] <= x <= fp["x1"] and fp["y0"] <= y <= fp["y1"]:
                        return grid[y - fp["y0"]][x - fp["x0"]] in CASTLE_WALK
                return False
            return LEGEND[ch][1]
        f = floors[plane]
        return 0 <= x < f["width"] and 0 <= y < f["height"] and f["rows"][y][x] in FLOOR_WALK

    trans = {("realm", REALM_PORTAL["x"], REALM_PORTAL["y"]): ("overworld",) + tuple(OVERWORLD_PORTAL["return_arrival"])}
    for gd in datas.values():
        for d in gd["keep_doors"]:
            trans[("realm",) + tuple(d["tile"])] = (d["to_plane"],) + tuple(d["arrive"])
        for f in gd["floors"]:
            for s_ in f["stairs"] + f["exits"]:
                trans[(f["plane"],) + tuple(s_["tile"])] = (s_["to_plane"],) + tuple(s_["arrive"])
    for k_, (p, x, y) in trans.items():
        if p == "overworld":
            continue
        if not walk(p, x, y):
            errs.append("arrival %s not walkable (from %s)" % ((p, x, y), k_))
        if (p, x, y) in trans:
            errs.append("arrival %s is itself a transition" % ((p, x, y),))
    for f in floors.values():
        for s_ in f["stairs"]:
            dest = floors[s_["to_plane"]]
            back = [b for b in dest["stairs"] if b["to_plane"] == f["plane"]]
            if not back:
                errs.append("%s stair %s has no return stair" % (f["plane"], s_["dir"])); continue
            bt = back[0]["tile"]
            if abs(bt[0] - s_["arrive"][0]) + abs(bt[1] - s_["arrive"][1]) != 1:
                errs.append("%s->%s arrival not adjacent to return stair" % (f["plane"], s_["to_plane"]))
            if abs(back[0]["arrive"][0] - s_["tile"][0]) + abs(back[0]["arrive"][1] - s_["tile"][1]) != 1:
                errs.append("%s<-%s return arrival not adjacent to stair" % (f["plane"], s_["to_plane"]))
    for pl, f in floors.items():
        fl = fdefs[pl]
        for d in f["doors"]:
            x, y = d["tile"]
            ok = False
            for a, b in (((x - 1, y), (x + 1, y)), ((x, y - 1), (x, y + 1))):
                if walk(pl, *a) and walk(pl, *b):
                    ra, rb = room_at(fl, *a), room_at(fl, *b)
                    ok = ok or bool(ra and rb and ra[0] != rb[0])
            if not ok:
                errs.append("%s door %s does not join two rooms" % (pl, d["tile"]))
    start = ("realm", SPAWN["x"], SPAWN["y"])
    seen = {start}; dq = deque([start]); used = set()
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
        OVERWORLD_PORTAL["x"], OVERWORLD_PORTAL["y"], SPAWN["x"], SPAWN["y"], len(seen), len({s_[0] for s_ in seen})))
    if ("realm", REALM_PORTAL["x"], REALM_PORTAL["y"]) not in seen:
        errs.append("realm return portal unreachable")
    for c in CASTLES:
        for a in c["gate_apron"]:
            if ("realm",) + tuple(a) not in seen:
                errs.append("%s gate apron %s unreachable" % (c["id"], a))
    for cid, gd in datas.items():
        fx0, fy0 = gd["footprint"]["x0"], gd["footprint"]["y0"]
        for ch, what in (("B", "drawbridge"), ("G", "portcullis"), ("P", "gate passage"), ("F", "bailey"), ("D", "keep door")):
            tiles = [("realm", fx0 + x, fy0 + y) for y, r in enumerate(gd["walkability"]) for x, c in enumerate(r) if c == ch]
            if not tiles:
                continue
            n_ = sum(t in seen for t in tiles)
            log.append("%-10s %-12s %d/%d tiles reachable" % (cid, what, n_, len(tiles)))
            if n_ != len(tiles):
                errs.append("%s %s: %d/%d reachable" % (cid, what, n_, len(tiles)))
        for f in gd["floors"]:
            fl = fdefs[f["plane"]]
            wt = [(f["plane"], x, y) for y, r in enumerate(f["rows"]) for x, c in enumerate(r) if c in FLOOR_WALK]
            n_ = sum(t in seen for t in wt)
            rooms_ok = []
            for (kind, name, x0, y0, x1, y1) in fl["rooms"]:
                hit = any((f["plane"], x, y) in seen for y in range(y0, y1 + 1) for x in range(x0, x1 + 1))
                rooms_ok.append(hit)
                if not hit:
                    errs.append("%s room %s unreachable" % (f["plane"], name))
            log.append("%-10s %s floor %d %-24s walkable %d/%d reachable, rooms %d/%d" % (cid, f.get("building", "keep")[:1].upper(), f["level"], f["name"], n_, len(wt), sum(rooms_ok), len(rooms_ok)))
            if n_ != len(wt):
                errs.append("%s: %d walkable tiles unreachable" % (f["plane"], len(wt) - n_))
    for k_ in trans:
        if k_ not in used:
            errs.append("transition %s never reached" % (k_,))
    for i, a in enumerate(CASTLES):
        for b in CASTLES[i + 1:]:
            ax0, ay0, ax1, ay1 = a["footprint"]; bx0, by0, bx1, by1 = b["footprint"]
            gap = max(bx0 - ax1, ax0 - bx1, by0 - ay1, ay0 - by1) - 1
            pa, pb = a["plot"], b["plot"]
            overlap = not (pa[2] < pb[0] or pb[2] < pa[0] or pa[3] < pb[1] or pb[3] < pa[1])
            log.append("spacing %-10s <-> %-10s %3d tiles%s" % (a["id"], b["id"], gap, "  PLOT OVERLAP" if overlap else ""))
            if gap < 30 or overlap:
                errs.append("plots %s/%s too close" % (a["id"], b["id"]))
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
    datas = {c["id"]: castle_data(c["id"]) for c in CASTLES if c["status"] == "built"}
    realm = {"id": "castle_realm", "name": "Castle Realm", "flag": "USE_CASTLE_REALM", "version": 2, "width": W, "height": H,
             "legend": {k: {"server_tile": v[0], "walkable": v[1], "what": v[2]} for k, v in LEGEND.items()},
             "rows": rows, "spawn": SPAWN, "return_portal": REALM_PORTAL, "hub": HUB, "overworld_portal": OVERWORLD_PORTAL,
             "roads": roads, "castles": CASTLES,
             "note": "castle footprints ('c') are blocked in the realm rows; walkability inside comes from each castle's data file grid"}
    json.dump(realm, open(os.path.join(out, "castle_realm_map.json"), "w"), indent=1)
    for cid, gd in datas.items():
        name = [c["data"] for c in CASTLES if c["id"] == cid][0]
        json.dump(gd, open(os.path.join(out, name), "w"), indent=1)
    errs, log = check(rows, datas)
    json.dump({"pass": not errs, "errors": errs, "log": log}, open(os.path.join(out, "realm_check.json"), "w"), indent=1)
    return 1 if errs else 0


if __name__ == "__main__":
    sys.exit(main())
