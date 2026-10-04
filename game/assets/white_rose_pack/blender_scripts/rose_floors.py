"""rose_floors.py - renders the 4 interior floors of the White Rose palace keep as cutaway tile sprites.
The camera and scale are the same as the castle sprites (ortho az 0 / el 32, Y pre-stretched, 80 px per tile at 2x).
Each floor is 24x11 tiles, exactly the keep's exterior footprint.
Changes from phase 1:
  * clearer stairs: a straight 7-step flight with balustrades and an 'up' arrow; the down stairwell is a railed
    opening with steps descending and a 'down' arrow
  * more furnishing: rugs per room, paintings and sconces on the visible wall faces, lit windows in the outer
    north wall, planters with white roses, and ~25 furniture kinds
  * the top floor is an open roof terrace (balustrade parapet) with a glass conservatory
  ~/bin/blender -b -P rose_floors.py -- [--json ../json/white_rose_castle.json] [--out ../rose/floors] [--fast]
"""
import bpy, json, math, os, sys
from mathutils import Matrix, Vector, Euler
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import rose_geo as cg
from rose_geo import T

ARGS = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
HERE = os.path.dirname(os.path.abspath(__file__))
JS = ARGS[ARGS.index("--json") + 1] if "--json" in ARGS else os.path.join(HERE, "..", "json", "white_rose_castle.json")
OUT = ARGS[ARGS.index("--out") + 1] if "--out" in ARGS else os.path.join(HERE, "..", "rose", "floors")
FAST = "--fast" in ARGS
EL = math.radians(32.0); SIN, COS = math.sin(EL), math.cos(EL)
S = Matrix.Diagonal((1.0, 1.0 / SIN, 1.0, 1.0))
PPT2 = 80
WALL_H = 2.1
D = json.load(open(JS))
PRE = "rose"

PAL = dict(cg.PAL)
PAL.update({
    "wall_top": "#5e564c", "wall_face": "#c9c0ae", "wall_face_l": "#d6cdbb", "fl_marble": "#eeeae2", "fl_marble_b": "#d9cfc4",
    "fl_pink": "#e8cfcf", "fl_wood": "#a4764c", "fl_wood_d": "#8a603c", "fl_terracotta": "#b9745a", "fl_terracotta_d": "#a3644c",
    "fl_blue": "#b8c8d4", "fl_stone": "#cfc8bb", "fl_terrace": "#d8d0bf", "rug": "#9a5a66", "rug_trim": "#e8d8a8", "rug_rose": "#8a3a4a",
    "table_wood": "#8a5e3a", "cloth": "#f4f1e8", "cloth_green": "#3d6b3a", "cloth_rose": "#c98a92", "gold": "#d4b04a",
    "book_a": "#7a2a2a", "book_b": "#2a4a6a", "book_c": "#3d6a2a", "canvas_a": "#6a8ab0", "canvas_b": "#c9a86a", "canvas_c": "#7a9a5a",
    "copper": "#b8733a", "candle": "#ffd98a", "fire": "#ff8a3a", "fire_core": "#ffd88a", "stair": "#b07a4a", "stair_d": "#6a4428",
    "stair_run": "#2f5a2c", "hole": "#141210", "arrow_up": "#3fbf5a", "arrow_dn": "#e0a030", "exit_glow": "#f6d890", "bronze": "#9a7a4a",
    "iron_d": "#34363b", "bone": "#efe8d8", "glass_wall": "#bfe3ea",
})
EMIS = dict(cg.EMISSIVE); EMIS.update({"exit_glow": 0.8, "candle": 6.0, "fire": 6.0, "fire_core": 8.0, "arrow_up": 0.8, "arrow_dn": 0.8,
                                       "window": 1.6, "glass_wall": 0.2})
ROOM_FLOOR = {"kitchen": ("fl_terracotta", "fl_terracotta_d"), "pantry": ("fl_terracotta", "fl_terracotta_d"),
              "entrance": ("fl_marble", "fl_marble_b"), "chapel": ("fl_blue", "fl_marble"), "stair_hall": ("fl_marble", "fl_pink"),
              "great_hall": ("fl_wood", "fl_wood_d"), "solar": ("fl_wood", "fl_wood_d"), "bedchamber": ("fl_wood", "fl_wood_d"),
              "chamber": ("fl_wood", "fl_wood_d"), "bath": ("fl_marble", "fl_blue"), "corridor": ("fl_marble", "fl_pink"),
              "gallery": ("fl_marble", "fl_pink"), "terrace": ("fl_terrace", "fl_stone"), "conservatory": ("fl_marble", "fl_pink"),
              "stair_head": ("fl_terrace", "fl_stone")}
RUG_ROOMS = {"entrance", "great_hall", "solar", "bedchamber", "chamber", "corridor", "gallery", "chapel"}


def C(x, y, z=0.0):
    return ((x + 0.5) * T, -(y + 0.5) * T, z)


def room_of(f, x, y):
    best = None
    for r in f["rooms"]:
        x0, y0, x1, y1 = r["rect"]
        if x0 <= x <= x1 and y0 <= y <= y1:
            a = (x1 - x0 + 1) * (y1 - y0 + 1)
            if best is None or a < best[0]:
                best = (a, r)
    return best[1] if best else None


def furniture(k, kind, x, y, f, occ, rng):
    cx, cy, _ = C(x, y)
    right = occ.get((x + 1, y)) == kind
    left = occ.get((x - 1, y)) == kind
    if kind in ("bed_big", "bath", "fountain_small") and left:
        return
    if kind in ("bed_big", "bath", "fountain_small") and right:
        cx += T / 2
    if kind == "hearth":
        k.box((cx, cy - 0.45, 1.05), (T * 1.0, 0.55, 2.1), "cstone_l"); k.box((cx, cy - 0.12, 0.45), (0.95, 0.12, 0.8), "hole")
        k.box((cx, cy - 0.12, 1.0), (1.3, 0.3, 0.16), "ctrim")
        k.cone((cx, cy - 0.2, 0.1), 0.3, 0.5, "fire", segs=5); k.cone((cx, cy - 0.18, 0.1), 0.16, 0.35, "fire_core", segs=4)
        k.cyl((cx + 0.45, cy + 0.3, 0), 0.25, 0.3, 0.45, "copper", 8)
    elif kind in ("table", "desk"):
        k.box((cx, cy, 0.8), (1.3, 0.9, 0.1), "table_wood")
        for sx in (-1, 1):
            for sy in (-1, 1):
                k.box((cx + sx * 0.55, cy + sy * 0.35, 0.38), (0.1, 0.1, 0.76), "fl_wood_d")
        if kind == "desk":
            k.box((cx - 0.3, cy, 0.9), (0.4, 0.3, 0.1), "book_a"); k.cone((cx + 0.4, cy, 0.85), 0.05, 0.15, "candle", 4)
            k.box((cx, cy + 0.65, 0.45), (0.5, 0.45, 0.08), "fl_wood_d")
        else:
            k.cyl((cx - 0.3, cy, 0.85), 0.14, 0.1, 0.12, "copper", 7); k.box((cx + 0.25, cy, 0.88), (0.35, 0.25, 0.06), "bone")
    elif kind == "long_table":
        k.box((cx, cy, 0.8), (T * 1.02, 1.1, 0.1), "table_wood"); k.box((cx, cy, 0.86), (T * 1.02, 0.5, 0.02), "cloth")
        for sy in (-1, 1):
            k.box((cx, cy + sy * 0.75, 0.25), (0.45, 0.4, 0.5), "fl_wood_d")    # chairs
        k.cyl((cx + 0.35, cy - 0.15, 0.85), 0.1, 0.08, 0.16, "gold", 6); k.box((cx - 0.3, cy + 0.1, 0.88), (0.28, 0.2, 0.05), "bone")
        k.cyl((cx, cy, 0.86), 0.05, 0.05, 0.35, "gold", 4); k.cone((cx, cy, 1.21), 0.05, 0.14, "candle", 4)
    elif kind == "throne":
        k.box((cx, cy + 0.1, 0.12), (1.4, 1.4, 0.24), "cstone_l"); k.box((cx, cy + 0.1, 0.55), (0.9, 0.8, 0.6), "cloth_green")
        k.box((cx, cy + 0.45, 1.35), (0.95, 0.15, 1.7), "gold"); k.box((cx, cy + 0.36, 1.25), (0.62, 0.04, 1.2), "cloth_green")
        k.cyl((cx, cy + 0.36, 2.0), 0.25, 0.25, 0.04, "rose_w", 7, rot=(90, 0, 0))
    elif kind == "brazier" or kind == "candelabra":
        k.cyl((cx, cy, 0), 0.25, 0.08, 0.2, "gold", 6); k.cyl((cx, cy, 0.2), 0.05, 0.05, 1.3, "gold", 5)
        if kind == "brazier":
            k.cyl((cx, cy, 1.5), 0.2, 0.4, 0.25, "gold", 7); k.cone((cx, cy, 1.7), 0.28, 0.5, "fire", segs=5)
        else:
            for sx in (-0.3, 0, 0.3):
                k.box((cx + sx / 2, cy, 1.5), (abs(sx) + 0.05, 0.05, 0.05), "gold"); k.cone((cx + sx, cy, 1.5), 0.05, 0.2, "candle", 4)
    elif kind in ("bookshelf", "shelf"):
        k.box((cx, cy - 0.35, 1.0), (1.4, 0.45, 2.0), "fl_wood_d")
        for sh in range(3):
            for b in range(6):
                mat = rng.choice(["book_a", "book_b", "book_c", "bone"]) if kind == "bookshelf" else rng.choice(["copper", "bone", "cloth", "canvas_b"])
                k.box((cx - 0.55 + b * 0.22, cy - 0.58, 0.4 + sh * 0.6), (0.16, 0.06, 0.4 if kind == "bookshelf" else 0.25), mat)
    elif kind == "barrel":
        k.cyl((cx, cy, 0), 0.45, 0.45, 1.0, "fl_wood", 8); k.cyl((cx, cy, 0.2), 0.47, 0.47, 0.08, "iron_d", 8)
        k.cyl((cx, cy, 0.75), 0.47, 0.47, 0.08, "iron_d", 8)
    elif kind == "sack":
        k.rock((cx - 0.2, cy, 0.3), (0.35, 0.3, 0.35), "canvas_b"); k.rock((cx + 0.3, cy + 0.1, 0.25), (0.3, 0.28, 0.3), "bone")
    elif kind == "statue":
        k.box((cx, cy, 0.4), (0.8, 0.8, 0.8), "cstone"); k.box((cx, cy, 0.83), (0.9, 0.9, 0.08), "ctrim")
        k.box((cx, cy, 1.4), (0.35, 0.3, 1.0), "marble"); k.box((cx, cy, 2.05), (0.24, 0.24, 0.28), "marble")
        k.box((cx + 0.25, cy - 0.1, 1.6), (0.12, 0.12, 0.6), "marble", rot=(0, -25, 0))
    elif kind == "planter":
        k.box((cx, cy, 0.3), (0.9, 0.9, 0.6), "cstone_l"); k.box((cx, cy, 0.62), (0.95, 0.95, 0.06), "ctrim")
        k.rock((cx, cy, 0.9), (0.45, 0.45, 0.4), "vine", sink=0)
        for i in range(6):
            a = 2 * math.pi * i / 6
            k.box((cx + math.cos(a) * 0.28, cy + math.sin(a) * 0.28, 1.1 + 0.1 * (i % 2)), (0.16, 0.16, 0.14), "rose_w", jitter=False)
    elif kind == "fountain_small":
        k.cyl((cx, cy, 0), 1.1, 1.0, 0.5, "marble", 12); k.disc((cx, cy, 0), 0.9, "water", segs=12, z=0.46, jag=0.0)
        k.cyl((cx, cy, 0.4), 0.15, 0.15, 0.8, "marble", 6); k.cyl((cx, cy, 1.2), 0.1, 0.45, 0.15, "marble", 8)
        k.cyl((cx, cy, 1.3), 0.05, 0.02, 0.4, "water_fall", 5)
    elif kind == "altar":
        k.box((cx, cy, 0.5), (1.3, 0.9, 1.0), "marble"); k.box((cx, cy, 1.03), (1.45, 1.0, 0.08), "cloth")
        k.box((cx, cy - 0.48, 0.7), (0.5, 0.02, 0.5), "cloth_green"); k.cyl((cx, cy, 1.07), 0.2, 0.2, 0.05, "gold", 8)
        k.box((cx, cy + 0.2, 1.6), (0.08, 0.08, 1.0), "gold")
        k.cone((cx - 0.45, cy, 1.07), 0.05, 0.2, "candle", 4); k.cone((cx + 0.45, cy, 1.07), 0.05, 0.2, "candle", 4)
    elif kind == "pew":
        k.box((cx, cy, 0.25), (1.35, 0.45, 0.5), "table_wood"); k.box((cx, cy + 0.22, 0.6), (1.35, 0.08, 0.7), "fl_wood_d")
    elif kind in ("bed", "bed_big"):
        w = 2.6 if kind == "bed_big" else 1.3
        k.box((cx, cy, 0.3), (w, 1.4, 0.4), "fl_wood_d"); k.box((cx, cy + 0.1, 0.55), (w - 0.1, 1.2, 0.15), "cloth_green" if kind == "bed_big" else "cloth_rose")
        k.box((cx, cy + 0.35, 0.64), (w - 0.1, 0.5, 0.05), "cloth")
        for sx in ((-0.55, 0.55) if kind == "bed_big" else (0,)):
            k.box((cx + sx, cy - 0.45, 0.66), (0.8 if kind == "bed_big" else 0.8, 0.3, 0.14), "bone")
        for sx in (-1, 1):
            k.box((cx + sx * (w / 2 - 0.05), cy - 0.65, 1.2), (0.08, 0.08, 2.0), "gold" if kind == "bed_big" else "fl_wood_d")
        if kind == "bed_big":
            k.box((cx, cy - 0.65, 2.2), (w, 0.1, 0.1), "gold"); k.box((cx, cy - 0.68, 1.5), (w - 0.2, 0.04, 1.2), "cloth_rose")
    elif kind == "wardrobe":
        k.box((cx, cy - 0.3, 1.0), (1.2, 0.6, 2.0), "fl_wood_d"); k.box((cx, cy - 0.61, 1.0), (0.04, 0.02, 1.8), "gold")
    elif kind == "dresser":
        k.box((cx, cy - 0.3, 0.45), (1.2, 0.6, 0.9), "fl_wood"); k.box((cx, cy - 0.55, 1.5), (0.7, 0.05, 0.9), "glass_wall")
        k.box((cx, cy - 0.57, 1.5), (0.8, 0.03, 1.0), "gold"); k.cyl((cx + 0.35, cy - 0.3, 0.9), 0.08, 0.05, 0.2, "cloth_rose", 5)
    elif kind == "armchair":
        k.box((cx, cy, 0.25), (0.9, 0.85, 0.5), "cloth_rose"); k.box((cx, cy + 0.35, 0.7), (0.9, 0.18, 0.9), "cloth_rose")
        for sx in (-1, 1):
            k.box((cx + sx * 0.4, cy, 0.55), (0.14, 0.8, 0.25), "fl_wood_d")
    elif kind == "harp":
        k.box((cx, cy, 0.1), (0.5, 0.4, 0.2), "gold"); k.box((cx - 0.15, cy, 1.0), (0.1, 0.1, 1.8), "gold")
        k.box((cx + 0.1, cy, 1.7), (0.6, 0.1, 0.1), "gold", rot=(0, 20, 0))
        for i in range(5):
            k.box((cx - 0.05 + i * 0.07, cy, 1.1), (0.015, 0.015, 1.1 - i * 0.1), "bone")
    elif kind == "bath":
        k.box((cx, cy, 0.35), (2.6, 1.2, 0.7), "marble"); k.box((cx, cy, 0.7), (2.4, 1.0, 0.04), "water")
        for sx in (-1, 1):
            k.cyl((cx + sx * 1.1, cy - 0.45, 0.7), 0.06, 0.06, 0.35, "gold", 5)
        for i in range(8):
            k.box((cx - 1.0 + i * 0.28, cy + 0.02, 0.73), (0.12, 0.12, 0.03), "rose_w", jitter=False)
    elif kind == "screen":
        for i in range(3):
            k.box((cx - 0.4 + i * 0.4, cy, 0.9), (0.4, 0.05, 1.8), "cloth_rose" if i % 2 else "cloth", rot=(0, 0, 25 if i % 2 else -25))
    elif kind == "telescope":
        k.cyl((cx, cy, 0), 0.3, 0.05, 1.0, "fl_wood_d", 3); k.cyl((cx, cy, 1.0), 0.1, 0.07, 1.2, "copper", 7, rot=(-55, 0, 0))
    elif kind == "bench_in":
        k.box((cx, cy, 0.42), (1.4, 0.5, 0.08), "fl_wood"); k.box((cx, cy, 0.2), (1.2, 0.35, 0.4), "cstone_l")


def build_floor(f, top):
    k = cg.PartKit("%s_%s" % (PRE, f["plane"]), PAL, seed=51 + f["level"], title=f["name"], emissive=EMIS)
    rng = k.rng
    rows = f["rows"]; H, Wd = len(rows), len(rows[0])
    is_top = f["level"] == top
    def wall(x, y):
        return not (0 <= x < Wd and 0 <= y < H) or rows[y][x] == "#"
    def outer(x, y):
        return x == 0 or y == 0 or x == Wd - 1 or y == H - 1
    occ = {tuple(fu["tile"]): fu["kind"] for fu in f["furniture"]}
    for y in range(H):
        for x in range(Wd):
            ch = rows[y][x]
            cx, cy, _ = C(x, y)
            if ch == "#":
                if is_top and outer(x, y):
                    k.box((cx, cy, 0.5), (T, T * 0.6 if y in (0, H - 1) else T, 1.0) if y in (0, H - 1) else (T * 0.6, T, 1.0), "wall_face_l")
                    k.box((cx, cy, 1.04), (T, T * 0.7, 0.08) if y in (0, H - 1) else (T * 0.7, T, 0.08), "ctrim")
                    continue
                glass = is_top and not outer(x, y)
                k.box((cx, cy, WALL_H / 2), (T, T, WALL_H), "glass_wall" if glass else ("wall_face" if (x + y) % 3 else "wall_face_l"))
                k.box((cx, cy, WALL_H + 0.04), (T * 1.001, T * 1.001, 0.08), "glass_frame" if glass else "wall_top")
                if not glass and not wall(x, y + 1) and y + 1 < H:        # skirting on visible (south) faces
                    k.box((cx, cy - T / 2 - 0.03, 0.12), (T, 0.06, 0.24), "ctrim")
                continue
            rm = room_of(f, x, y)
            kind = rm["kind"] if rm else "corridor"
            m0, m1 = ROOM_FLOOR.get(kind, ("fl_stone", "fl_marble"))
            k.box((cx, cy, -0.05), (T * 0.98, T * 0.98, 0.1), m0 if (x + y) % 2 else m1)
            k.box((cx, cy, -0.12), (T, T, 0.1), "wall_top")
            if ch == "D":
                horiz = wall(x - 1, y) and wall(x + 1, y)
                if horiz:
                    for s in (-1, 1):
                        k.box((cx + s * 0.62, cy, WALL_H / 2), (0.24, T, WALL_H), "ctrim")
                    k.box((cx, cy, WALL_H - 0.1), (T, T, 0.2), "ctrim")
                    k.box((cx - 0.5, cy - 0.5, 1.0), (0.08, 1.0, 2.0), "fl_wood", rot=(0, 0, -25))
                    k.box((cx - 0.5, cy - 0.5, 1.0), (0.1, 0.06, 0.08), "gold", rot=(0, 0, -25))
                else:
                    for s in (-1, 1):
                        k.box((cx, cy + s * 0.62, WALL_H / 2), (T, 0.24, WALL_H), "ctrim")
                    k.box((cx + 0.5, cy - 0.5, 1.0), (1.0, 0.08, 2.0), "fl_wood", rot=(0, 0, 25))
            elif ch == "U":
                # straight flight rising EAST (sawtooth profile faces the camera), runner, rail, newel posts
                n = 7
                dx = (T - 0.1) / n
                for i in range(n):
                    z = 0.3 * (i + 1)
                    xx = cx - T / 2 + 0.05 + (i + 0.5) * dx
                    k.box((xx, cy + 0.05, z / 2), (dx + 0.01, T * 0.78, z), "stair_d")
                    k.box((xx, cy + 0.05, z - 0.04), (dx + 0.02, T * 0.8, 0.08), "stair")
                    k.box((xx, cy + 0.05, z + 0.005), (dx, T * 0.34, 0.02), "stair_run")
                k.add([(cx - T / 2, cy + T * 0.44, 1.2), (cx + T / 2, cy + T * 0.44, 3.1), (cx + T / 2, cy + T * 0.44, 2.95),
                       (cx - T / 2, cy + T * 0.44, 1.05)], [(0, 1, 2, 3), (3, 2, 1, 0)], "gold")
                for i in range(0, n, 2):
                    xx = cx - T / 2 + 0.05 + (i + 0.5) * dx
                    k.box((xx, cy + T * 0.44, 0.3 * (i + 1) + 0.45), (0.06, 0.06, 0.9), "cstone_l")
                k.box((cx - T / 2 + 0.1, cy - T * 0.36, 0.6), (0.16, 0.16, 1.2), "gold")
                k.cone((cx - T / 2 + 0.1, cy - T * 0.36, 1.2), 0.12, 0.2, "gold", segs=4)
            elif ch == "V":
                k.box((cx, cy, -0.02), (T * 0.86, T * 0.86, 0.06), "hole")
                for i in range(5):
                    yy = cy + T / 2 - 0.3 - i * 0.22
                    k.box((cx, yy, -0.02 - i * 0.02), (T * 0.7, 0.2, 0.05), "stair" if i % 2 else "stair_d")
                for (dx, dy, lx, ly) in ((-T * 0.45, 0, 0.08, T * 0.9), (T * 0.45, 0, 0.08, T * 0.9), (0, -T * 0.45, T * 0.9, 0.08)):
                    k.box((cx + dx, cy + dy, 0.95), (lx, ly, 0.08), "gold")
                    for j in range(4):
                        t = (j + 0.5) / 4 - 0.5
                        k.box((cx + dx + (t * lx * 0.95 if lx > 0.1 else 0), cy + dy + (t * ly * 0.95 if ly > 0.1 else 0), 0.46), (0.06, 0.06, 0.92), "cstone_l")
                k.add([(cx - 0.3, cy + T / 2 - 0.12, 0.02), (cx + 0.3, cy + T / 2 - 0.12, 0.02), (cx, cy + T / 2 - 0.45, 0.02)], [(0, 2, 1)], "arrow_dn")
            elif ch == "E":
                k.box((cx, cy, 0.02), (T * 0.9, T * 0.9, 0.04), "exit_glow")
                k.box((cx, cy - T / 2 + 0.1, 1.2), (T, 0.12, 0.12), "ctrim")
    # up arrows drawn on the tile south of every U, labelled floor markers for V
    for y in range(H):
        for x in range(Wd):
            if rows[y][x] == "U":
                cx, cy, _ = C(x, y + 1)
                k.add([(cx - 0.35, cy + 0.2, 0.02), (cx + 0.35, cy + 0.2, 0.02), (cx, cy + 0.6, 0.02)], [(0, 1, 2)], "arrow_up")
    # rugs
    for rm in f["rooms"]:
        if rm["kind"] not in RUG_ROOMS:
            continue
        x0, y0, x1, y1 = rm["rect"]
        if x1 - x0 < 2 or y1 - y0 < 1:
            if rm["kind"] in ("corridor", "gallery"):
                a, b = C(x0 + 0.5, y0), C(x1 - 0.5, y1)
                k.box(((a[0] + b[0]) / 2, (a[1] + b[1]) / 2, 0.015), (b[0] - a[0] + T * 0.6, T * 0.6, 0.02), "rug")
            continue
        a, b = C(x0 + 1, y0 + 1), C(x1 - 1, y1 - 1)
        wx, wy = b[0] - a[0] + T * 0.9, a[1] - b[1] + T * 0.9
        if wx > wy * 1.3:
            wy = min(wy, T * 1.6)
        elif wy > wx * 1.3:
            wx = min(wx, T * 1.6)
        else:
            wx, wy = wx * 0.8, wy * 0.8
        k.box(((a[0] + b[0]) / 2, (a[1] + b[1]) / 2, 0.012), (wx + 0.3, wy + 0.3, 0.02), "rug_trim")
        k.box(((a[0] + b[0]) / 2, (a[1] + b[1]) / 2, 0.02), (wx, wy, 0.02), "rug")
        k.cyl(((a[0] + b[0]) / 2, (a[1] + b[1]) / 2, 0.02), 0.5, 0.5, 0.02, "rose_w", 8)
    # visible wall faces (south faces of walls with floor below): paintings, sconces, windows in the outer north wall
    for y in range(H - 1):
        for x in range(1, Wd - 1):
            if rows[y][x] == "#" and rows[y + 1][x] in ".x" and not (is_top and 0 < y):
                cx, cy, _ = C(x, y)
                yf = cy - T / 2 - 0.02
                if is_top:
                    continue
                if y == 0 and x % 3 == 1:
                    k.box((cx, yf, 1.35), (0.8, 0.08, 1.2), "ctrim"); k.box((cx, yf - 0.03, 1.35), (0.55, 0.08, 0.95), "window")
                elif x % 4 == 2 and rows[y + 1][x] == ".":
                    k.box((cx, yf, 1.35), (0.9, 0.06, 0.7), "gold"); k.box((cx, yf - 0.03, 1.35), (0.75, 0.06, 0.55), rng.choice(["canvas_a", "canvas_b", "canvas_c"]))
                elif x % 4 == 0:
                    k.box((cx, yf - 0.05, 1.5), (0.12, 0.12, 0.25), "gold"); k.cone((cx, yf - 0.1, 1.65), 0.06, 0.18, "candle", 4)
    for fu in f["furniture"]:
        furniture(k, fu["kind"], fu["tile"][0], fu["tile"][1], f, occ, rng)
    return k


def render_floor(k, path, wt, ht):
    sc = bpy.data.scenes.new("F_" + k.key)
    parts = k.all_parts(); mats = k._materials()
    col = bpy.data.collections.new("C_" + k.key); sc.collection.children.link(col)
    for name, (verts, faces) in parts.items():
        if faces:
            ob = k._make_object(k.key + "_" + name, verts, faces, mats, col)
            ob.data.transform(S)
    TOP_T, BOT_T = 2, -ht
    U0, U1, V0, V1 = 0.0, wt * T, BOT_T * T, TOP_T * T
    w2, h2 = int(wt * PPT2), int((TOP_T - BOT_T) * PPT2)
    w = bpy.data.worlds.new("W"); w.use_nodes = True
    w.node_tree.nodes["Background"].inputs["Color"].default_value = (0.55, 0.55, 0.6, 1)
    w.node_tree.nodes["Background"].inputs["Strength"].default_value = 0.9
    sc.world = w
    sc.render.engine = "BLENDER_EEVEE_NEXT"; sc.render.resolution_x, sc.render.resolution_y = w2, h2
    sc.render.resolution_percentage = 100; sc.render.film_transparent = True
    sc.render.image_settings.file_format = "PNG"; sc.render.image_settings.color_mode = "RGBA"
    sc.view_settings.view_transform = "Standard"; sc.eevee.taa_render_samples = 16 if FAST else 32
    sun = bpy.data.lights.new("Sun", "SUN"); sun.energy = 3.0; sun.color = (1.0, 0.96, 0.9); sun.angle = math.radians(3)
    so = bpy.data.objects.new("Sun", sun); so.rotation_euler = Euler((math.radians(40), math.radians(15), math.radians(-30)), "XYZ")
    sc.collection.objects.link(so)
    cam = bpy.data.cameras.new("Cam"); cam.type = "ORTHO"; cam.ortho_scale = max(U1 - U0, V1 - V0)
    cam.clip_start = 1.0; cam.clip_end = 600
    co = bpy.data.objects.new("Cam", cam)
    up = Vector((0, SIN, COS)); fwd = Vector((0, COS, -SIN))
    co.location = Vector(((U0 + U1) / 2, 0, 0)) + up * ((V0 + V1) / 2) - fwd * 250.0
    co.rotation_euler = Euler((math.radians(58), 0, 0), "XYZ")
    sc.collection.objects.link(co); sc.camera = co
    sc.render.filepath = path
    os.makedirs(os.path.dirname(path), exist_ok=True)
    bpy.ops.render.render(write_still=True, scene=sc.name)
    print("[floors] wrote", path, w2, h2)
    return {"size_2x": [w2, h2], "origin_2x": [0, TOP_T * PPT2], "tris": sum(len(fc) for _, (v, fc) in parts.items())}


info = {}
top = len(D["floors"])
for f in D["floors"]:
    k = build_floor(f, top)
    info[f["plane"]] = render_floor(k, os.path.join(OUT, "%s_f%d.png" % (PRE, f["level"])), f["width"], f["height"])
json.dump(info, open(os.path.join(OUT, "floors_render_info.json"), "w"), indent=1)
print("[floors] done")
