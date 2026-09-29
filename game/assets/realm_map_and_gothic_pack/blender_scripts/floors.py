"""floors.py - renders the 4 interior floors (planes) of Duskspire Keep as cutaway tile sprites.
Same camera / scale as castle_pack: ortho az 0 el 32, Y pre-stretched 1/sin32, 80 px/tile at 2x.
Walls are cut at 2.1 m so rooms read from above (OSRS-style roof-off interior).
  ~/bin/blender -b -P floors.py -- [--json ../json/gothic_castle.json] [--out ../gothic/floors] [--fast]
"""
import bpy, json, math, os, sys
from mathutils import Matrix, Vector, Euler
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import gothic_geo as cg
from gothic_geo import T

ARGS = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
HERE = os.path.dirname(os.path.abspath(__file__))
JS = ARGS[ARGS.index("--json") + 1] if "--json" in ARGS else os.path.join(HERE, "..", "json", "gothic_castle.json")
OUT = ARGS[ARGS.index("--out") + 1] if "--out" in ARGS else os.path.join(HERE, "..", "gothic", "floors")
FAST = "--fast" in ARGS
EL = math.radians(32.0); SIN, COS = math.sin(EL), math.cos(EL)
S = Matrix.Diagonal((1.0, 1.0 / SIN, 1.0, 1.0))
PPT2 = 80; PPM2 = PPT2 / T
WALL_H = 2.1
D = json.load(open(JS))

PAL = dict(cg.PAL)
PAL.update({
    "fl_stone": "#4a4850", "fl_stone_d": "#3c3a42", "fl_chapel": "#3a2f3a", "fl_kitchen": "#5a4a3c", "fl_wood": "#5b4331",
    "fl_wood_d": "#4a3527", "fl_rug": "#6e1119", "fl_rug_trim": "#b08a3a", "fl_library": "#4f3d2e", "fl_roof": "#56545c",
    "wall_top": "#2a2930", "wall_face": "#44434b", "wall_face_l": "#55545d", "door_wood": "#5e3f28", "door_iron": "#232329",
    "stair": "#6a6870", "stair_d": "#3a3940", "hole": "#0b0a0d", "exit_glow": "#d9a050", "table_wood": "#6b4a30",
    "cloth_red": "#7d1018", "cloth_black": "#1c1b21", "gold": "#c9a23a", "straw": "#b39a5a", "bone": "#cfc6ae",
    "book_a": "#6d1d1d", "book_b": "#1f3a5a", "book_c": "#3d5a2a", "potion": "#57ff6a", "bronze": "#8a6a3a",
    "candle": "#ffcf6a", "fire": "#ff7a2a", "fire_core": "#ffd27a", "ember": "#ff4a1a",
})
EMIS = dict(cg.EMISSIVE); EMIS.update({"exit_glow": 0.9, "potion": 3.0, "candle": 6.0, "fire": 6.0, "fire_core": 8.0})
ROOM_FLOOR = {"chapel": "fl_chapel", "guard": "fl_stone", "kitchen": "fl_kitchen", "hall": "fl_stone", "great_hall": "fl_wood",
              "library": "fl_library", "lobby": "fl_stone_d", "bedchamber": "fl_wood", "armoury": "fl_stone", "alchemist": "fl_stone_d",
              "corridor": "fl_stone", "treasury": "fl_stone_d", "roof_walk": "fl_roof", "bell": "fl_wood_d", "stair_head": "fl_roof"}


def C(x, y, z=0.0):
    return ((x + 0.5) * T, -(y + 0.5) * T, z)


def room_kind(f, x, y):
    best = None
    for r in f["rooms"]:
        x0, y0, x1, y1 = r["rect"]
        if x0 <= x <= x1 and y0 <= y <= y1:
            a = (x1 - x0) * (y1 - y0)
            if best is None or a < best[0]:
                best = (a, r["kind"])
    return best[1] if best else None


def furniture(k, kind, x, y, rng):
    cx, cy, _ = C(x, y)
    if kind == "altar":
        k.box((cx, cy, 0.5), (1.3, 0.9, 1.0), "cstone_l"); k.box((cx, cy, 1.03), (1.45, 1.0, 0.08), "cloth_red")
        k.cyl((cx - 0.4, cy, 1.07), 0.05, 0.05, 0.3, "bone", 5); k.cone((cx - 0.4, cy, 1.37), 0.05, 0.12, "candle", 4)
        k.box((cx + 0.2, cy + 0.2, 1.5), (0.08, 0.08, 0.9), "iron_d"); k.box((cx + 0.2, cy + 0.2, 1.7), (0.45, 0.08, 0.08), "iron_d")
    elif kind == "pew":
        k.box((cx, cy, 0.25), (1.35, 0.45, 0.5), "table_wood"); k.box((cx, cy + 0.22, 0.6), (1.35, 0.08, 0.7), "fl_wood_d")
    elif kind in ("table", "desk", "long_table"):
        w = 1.4 if kind != "long_table" else T * 1.02
        k.box((cx, cy, 0.8), (w, 1.0, 0.1), "table_wood")
        for sx in (-1, 1):
            for sy in (-1, 1):
                k.box((cx + sx * (w / 2 - 0.1), cy + sy * 0.4, 0.38), (0.1, 0.1, 0.76), "fl_wood_d")
        if kind == "long_table":
            k.box((cx, cy, 0.86), (0.3, 0.9, 0.02), "cloth_red")
            k.cyl((cx + 0.3, cy - 0.2, 0.85), 0.12, 0.08, 0.14, "bronze", 6); k.box((cx - 0.3, cy + 0.2, 0.88), (0.3, 0.2, 0.06), "bone")
        elif kind == "desk":
            k.box((cx - 0.3, cy, 0.9), (0.4, 0.3, 0.1), "book_a"); k.cone((cx + 0.4, cy, 0.85), 0.05, 0.15, "candle", 4)
        else:
            k.cyl((cx, cy, 0.85), 0.1, 0.08, 0.18, "bronze", 6)
    elif kind == "weapon_rack":
        k.box((cx, cy - 0.3, 0.9), (1.3, 0.12, 1.8), "fl_wood_d")
        for i in range(4):
            k.box((cx - 0.45 + i * 0.3, cy - 0.4, 1.0), (0.05, 0.05, 1.8), "iron!")
            k.cone((cx - 0.45 + i * 0.3, cy - 0.4, 1.9), 0.07, 0.25, "iron!", segs=4)
    elif kind == "armour_stand":
        k.cyl((cx, cy, 0), 0.3, 0.3, 0.1, "fl_wood_d", 6); k.box((cx, cy, 1.1), (0.55, 0.35, 0.8), "iron!")
        k.box((cx, cy, 1.65), (0.3, 0.3, 0.3), "iron_d"); k.box((cx, cy - 0.2, 1.1), (0.25, 0.04, 0.5), "cloth_red")
    elif kind == "hearth":
        k.box((cx, cy - 0.35, 0.9), (1.45, 0.6, 1.8), "cstone_l"); k.box((cx, cy - 0.05, 0.4), (0.9, 0.2, 0.7), "hole")
        k.cone((cx, cy + 0.0, 0.1), 0.3, 0.5, "fire", segs=5); k.cone((cx, cy + 0.02, 0.1), 0.16, 0.35, "fire_core", segs=4)
        k.cyl((cx + 0.5, cy + 0.35, 0.0), 0.25, 0.3, 0.45, "iron_d", 7)
    elif kind == "pillar":
        k.cyl((cx, cy, 0), 0.5, 0.5, 0.25, "cstone_l", 8); k.cyl((cx, cy, 0.25), 0.36, 0.36, WALL_H - 0.25, "wall_face", 8)
        k.box((cx, cy, WALL_H), (0.8, 0.8, 0.12), "wall_top")
    elif kind == "throne":
        k.box((cx, cy + 0.1, 0.12), (1.45, 1.4, 0.24), "cstone_l")
        k.box((cx, cy + 0.1, 0.55), (0.9, 0.8, 0.6), "cloth_black"); k.box((cx, cy + 0.45, 1.3), (0.95, 0.15, 1.6), "cloth_black")
        k.box((cx, cy + 0.36, 1.25), (0.6, 0.04, 1.1), "cloth_red")
        for sx in (-1, 1):
            k.cyl((cx + sx * 0.5, cy + 0.45, 2.1), 0.07, 0.0, 0.45, "gold", 4)
    elif kind == "brazier":
        k.cyl((cx, cy, 0), 0.08, 0.08, 0.9, "iron_d", 5); k.cyl((cx, cy, 0.9), 0.2, 0.4, 0.25, "iron_d", 7)
        k.cone((cx, cy, 1.1), 0.28, 0.55, "fire", segs=5); k.cone((cx, cy, 1.1), 0.15, 0.4, "fire_core", segs=4)
    elif kind == "bookshelf":
        k.box((cx, cy - 0.35, 1.0), (1.4, 0.45, 2.0), "fl_wood_d")
        for sh in range(3):
            for b in range(6):
                k.box((cx - 0.55 + b * 0.22, cy - 0.58, 0.4 + sh * 0.6), (0.16, 0.06, 0.42), rng.choice(["book_a", "book_b", "book_c", "bone"]))
    elif kind == "bed":
        k.box((cx, cy, 0.3), (1.3, 1.4, 0.4), "fl_wood_d"); k.box((cx, cy + 0.1, 0.55), (1.2, 1.2, 0.15), "cloth_red")
        k.box((cx, cy - 0.5, 0.62), (0.8, 0.3, 0.14), "bone")
        for sx in (-1, 1):
            k.box((cx + sx * 0.6, cy - 0.65, 1.1), (0.08, 0.08, 2.0), "fl_wood_d")
    elif kind == "wardrobe":
        k.box((cx, cy - 0.3, 1.0), (1.2, 0.6, 2.0), "fl_wood_d"); k.box((cx, cy - 0.61, 1.0), (0.04, 0.02, 1.8), "gold")
    elif kind == "cauldron":
        k.cyl((cx, cy, 0.05), 0.55, 0.65, 0.7, "iron_d", 9); k.cyl((cx, cy, 0.72), 0.5, 0.5, 0.03, "potion", 9)
        k.cone((cx, cy, 0.0), 0.35, 0.2, "fire", segs=5)
        for i in range(3):
            k.cyl((cx - 0.9 + i * 0.25, cy + 0.6, 0), 0.08, 0.08, 0.25, "potion", 5)
    elif kind == "chest":
        k.box((cx, cy, 0.3), (1.0, 0.7, 0.6), "table_wood"); k.box((cx, cy, 0.62), (1.05, 0.75, 0.08), "gold")
        k.box((cx, cy - 0.36, 0.4), (0.15, 0.04, 0.2), "gold")
        k.cyl((cx + 0.2, cy - 0.5, 0), 0.25, 0.2, 0.12, "gold", 6)
    elif kind == "bell":
        pass   # built once per floor (spans 2 tiles)


def build_floor(f):
    k = cg.PartKit("gothic_" + f["plane"], PAL, seed=31 + f["level"], title=f["name"], emissive=EMIS)
    rng = k.rng
    rows = f["rows"]
    H, W = len(rows), len(rows[0])
    def wall(x, y):
        return not (0 <= x < W and 0 <= y < H) or rows[y][x] == "#"
    top = f["level"] == 4
    for y in range(H):
        for x in range(W):
            ch = rows[y][x]
            cx, cy, _ = C(x, y)
            if ch == "#":
                if top and not any(not wall(x + dx, y + dy) for dx in (-1, 0, 1) for dy in (-1, 0, 1)):
                    continue      # open sky around the spire top (nothing drawn)
                h = 1.0 if top else WALL_H
                k.box((cx, cy, h / 2), (T, T, h), "wall_face" if (x + y) % 3 else "wall_face_l")
                k.box((cx, cy, h + 0.04), (T * 1.001, T * 1.001, 0.08), "wall_top")
                if top and (x + y) % 2 == 0:
                    k.box((cx, cy, h + 0.35), (T * 0.6, T * 0.6, 0.6), "wall_face")   # crenellation
                continue
            kind = room_kind(f, x, y) or "corridor"
            mat = ROOM_FLOOR.get(kind, "fl_stone")
            if ch in "DE":
                mat = "fl_stone_d"
            k.box((cx, cy, -0.05), (T * 0.97, T * 0.97, 0.1), mat)
            k.box((cx, cy, -0.12), (T, T, 0.1), "wall_top")
            if ch == "D":
                horiz = wall(x - 1, y) and wall(x + 1, y)     # door in a horizontal wall
                for s in (-1, 1):
                    px, py = (cx + s * 0.62 * T / 1.0 * 0.5 * 2 * 0.5, cy) if horiz else (cx, cy + s * 0.31 * T)
                    k.box((px, py, WALL_H / 2), (0.22, 0.22, WALL_H) if horiz else (0.22, 0.22, WALL_H), "cstone_l")
                if horiz:
                    k.box((cx - 0.45, cy - 0.45, 0.95), (0.08, 0.95, 1.9), "door_wood", rot=(0, 0, -20))   # door swung open
                    k.box((cx - 0.45, cy - 0.45, 1.3), (0.1, 0.9, 0.08), "door_iron", rot=(0, 0, -20))
                else:
                    k.box((cx + 0.45, cy - 0.45, 0.95), (0.95, 0.08, 1.9), "door_wood", rot=(0, 0, 20))
                    k.box((cx + 0.45, cy - 0.45, 1.3), (0.9, 0.1, 0.08), "door_iron", rot=(0, 0, 20))
            elif ch == "U":
                for i in range(6):     # spiral stair winding up to the north-east
                    a = math.radians(-90 + i * 50)
                    k.box((cx + 0.35 * math.cos(a), cy + 0.35 * math.sin(a), 0.18 + i * 0.32), (0.75, 0.42, 0.36), "stair" if i % 2 else "stair_d", rot=(0, 0, math.degrees(a)))
                k.cyl((cx, cy, 0), 0.14, 0.14, 2.3, "cstone_l", 6)
                k.box((cx, cy + 0.66, 2.35), (T, 0.12, 0.12), "iron_d")
            elif ch == "V":
                k.box((cx, cy, -0.02), (T * 0.8, T * 0.8, 0.06), "hole")
                for i in range(4):
                    a = math.radians(90 + i * 55)
                    k.box((cx + 0.3 * math.cos(a), cy + 0.3 * math.sin(a), 0.02 - i * 0.02), (0.6, 0.35, 0.04), "stair_d" if i % 2 else "stair", rot=(0, 0, math.degrees(a)))
                k.cyl((cx, cy, 0), 0.12, 0.12, 0.9, "iron_d", 5)
            elif ch == "E":
                k.box((cx, cy, 0.02), (T * 0.9, T * 0.9, 0.04), "exit_glow")
    # rugs / carpets along main rooms
    if f["level"] == 2:
        for y in range(2, 11):
            cx, cy, _ = C(5, y)
            k.box((cx + T / 2, cy, 0.02), (T * 1.4, T, 0.03), "fl_rug")
    if f["level"] == 1:
        for x in range(2, 16):
            cx, cy, _ = C(x, 7)
            k.box((cx, cy - T / 2, 0.02), (T, T * 0.9, 0.03), "fl_rug")
    for fu in f["furniture"]:
        furniture(k, fu["kind"], fu["tile"][0], fu["tile"][1], rng)
    if f["level"] == 4:          # great bell hung from a timber frame, spanning tiles 8-9
        cx = (C(8, 5)[0] + C(9, 5)[0]) / 2; cy = C(8, 5)[1]
        for sx in (-1, 1):
            k.box((cx + sx * 1.3, cy, 1.4), (0.2, 0.2, 2.8), "fl_wood_d")
        k.box((cx, cy, 2.8), (2.9, 0.25, 0.25), "fl_wood_d")
        k.cyl((cx, cy, 1.1), 1.0, 0.55, 1.5, "bronze", 10); k.cyl((cx, cy, 2.55), 0.55, 0.1, 0.25, "bronze", 10)
        k.box((cx, cy, 0.9), (0.2, 0.2, 0.4), "iron_d")
    # candles / wall torches for mood
    for (x, y) in [(r["rect"][0], r["rect"][1]) for r in f["rooms"]]:
        cx, cy, _ = C(x, y)
        k.cone((cx - 0.5, cy + 0.5, 1.6), 0.07, 0.25, "candle", 4)
    return k


def render_floor(k, path):
    for s in list(bpy.data.scenes):
        pass
    sc = bpy.data.scenes.new("F_" + k.key)
    parts = k.all_parts(); mats = k._materials()
    col = bpy.data.collections.new("C_" + k.key); sc.collection.children.link(col)
    for name, (verts, faces) in parts.items():
        if faces:
            ob = k._make_object(k.key + "_" + name, verts, faces, mats, col)
            ob.data.transform(S)
    W_T, TOP_T, BOT_T = 18, 2, -12
    U0, U1, V0, V1 = 0.0, W_T * T, BOT_T * T, TOP_T * T
    w2, h2 = int(W_T * PPT2), int((TOP_T - BOT_T) * PPT2)
    w = bpy.data.worlds.new("W"); w.use_nodes = True
    w.node_tree.nodes["Background"].inputs["Color"].default_value = (0.36, 0.33, 0.40, 1)
    w.node_tree.nodes["Background"].inputs["Strength"].default_value = 0.8
    sc.world = w
    sc.render.engine = "BLENDER_EEVEE_NEXT"; sc.render.resolution_x, sc.render.resolution_y = w2, h2
    sc.render.resolution_percentage = 100; sc.render.film_transparent = True
    sc.render.image_settings.file_format = "PNG"; sc.render.image_settings.color_mode = "RGBA"
    sc.view_settings.view_transform = "Standard"; sc.eevee.taa_render_samples = 8 if FAST else 24
    sun = bpy.data.lights.new("Sun", "SUN"); sun.energy = 3.0; sun.color = (1.0, 0.95, 0.86); sun.angle = math.radians(3)
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
    return {"size_2x": [w2, h2], "origin_2x": [0, TOP_T * PPT2], "tris": sum(len(f) for _, (v, f) in parts.items())}


info = {}
for f in D["floors"]:
    k = build_floor(f)
    info[f["plane"]] = render_floor(k, os.path.join(OUT, "gothic_f%d.png" % f["level"]))
json.dump(info, open(os.path.join(OUT, "floors_render_info.json"), "w"), indent=1)
print("[floors] done")
