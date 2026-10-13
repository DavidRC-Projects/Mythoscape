"""Blender (headless) renderer for one seamless ground tile.
blender -b -P src/ground/bl_ground.py -- <name> [samples]
Reads work/ground/<name>_{albedo.png,height.npy,height16.png,emis.png,scatter.json},
builds a 1.5x1.5-tile wrapped neighbourhood (ground mesh + instanced 3D details copied at
every +-1 tile offset), renders the centre tile top-down orthographic at 640 px.
"""
import bpy, bmesh, sys, os, json, math
import numpy as np
from mathutils import Vector
sys.path.insert(0, "/workspace/fairy_village/src/blender")
import fv_common as C

argv = sys.argv[sys.argv.index("--") + 1:]
NAME = argv[0]
SAMPLES = int(argv[1]) if len(argv) > 1 else 64
W = "/workspace/fairy_village/work/ground"
N = 640
meta = json.load(open(f"{W}/{NAME}_scatter.json"))
# macro mode: the tile is sub-tile (I,J) of a seamless M x M-tile texture (maps + objects in macro tile units)
MAC = meta.get("macro")
MM, MI, MJ = (MAC["M"], MAC["i"], MAC["j"]) if MAC else (1, 0, 0)
SRC = MAC["base"] if MAC else NAME
H = np.load(f"{W}/{SRC}_height.npy")
NH = H.shape[0]

sc = C.reset()
C.cycles(sc, samples=SAMPLES, w=N, h=N, transparent=False, denoise=True)
sc.cycles.max_bounces = 4


def hsample(xi, yi):
    """bilinear periodic sample of height at image coords (0..1)."""
    xi = (xi + MI) / MM; yi = (yi + MJ) / MM
    fx = (xi % 1.0) * NH - 0.5; fy = (yi % 1.0) * NH - 0.5
    x0 = np.floor(fx).astype(int); y0 = np.floor(fy).astype(int)
    tx = fx - x0; ty = fy - y0
    x0 %= NH; y0 %= NH; x1 = (x0 + 1) % NH; y1 = (y0 + 1) % NH
    return (H[y0, x0] * (1 - tx) * (1 - ty) + H[y0, x1] * tx * (1 - ty) + H[y1, x0] * (1 - tx) * ty + H[y1, x1] * tx * ty)


def srgb2lin(c):
    c = np.asarray(c, float) / 255.0
    return np.where(c <= 0.04045, c / 12.92, ((c + 0.055) / 1.055) ** 2.4)


# ---------------------------------------------------------------- ground mesh
LO, HI, G = -0.25, 1.25, 384
xs = np.linspace(LO, HI, G + 1)
GX, GY = np.meshgrid(xs, xs)                       # world X east, world Y north
Z = hsample(GX, 1.0 - GY)
verts = np.stack([GX.ravel(), GY.ravel(), Z.ravel()], 1)
ii = np.arange(G)
a = (ii[None, :] + ii[:, None] * (G + 1)).ravel()
faces = np.stack([a, a + 1, a + G + 2, a + G + 1], 1)
me = bpy.data.meshes.new("ground")
me.vertices.add(len(verts)); me.vertices.foreach_set("co", verts.astype(np.float32).ravel())
me.loops.add(faces.size); me.loops.foreach_set("vertex_index", faces.astype(np.int32).ravel())
me.polygons.add(len(faces)); me.polygons.foreach_set("loop_start", (np.arange(len(faces)) * 4).astype(np.int32))
me.polygons.foreach_set("loop_total", np.full(len(faces), 4, np.int32))
uv = me.uv_layers.new(name="UVMap")
lv = faces.ravel()
uv.data.foreach_set("uv", np.stack([(verts[lv, 0] + MI) / MM, (verts[lv, 1] + MM - 1 - MJ) / MM], 1).astype(np.float32).ravel())
me.update(); me.validate()
me.polygons.foreach_set("use_smooth", np.ones(len(faces), bool))
ground = bpy.data.objects.new("ground", me); sc.collection.objects.link(ground)


def img_node(nodes, path, noncolor=False):
    n = nodes.new("ShaderNodeTexImage")
    n.image = bpy.data.images.load(path)
    n.extension = "REPEAT"; n.interpolation = "Cubic"
    if noncolor:
        n.image.colorspace_settings.name = "Non-Color"
    return n


m = bpy.data.materials.new("ground_mat"); m.use_nodes = True
nt = m.node_tree; nn = nt.nodes; L = nt.links
bsdf = nn["Principled BSDF"]
alb = img_node(nn, f"{W}/{SRC}_albedo.png")
hgt = img_node(nn, f"{W}/{SRC}_height16.png", True)
emi = img_node(nn, f"{W}/{SRC}_emis.png")
bump = nn.new("ShaderNodeBump"); bump.inputs["Strength"].default_value = 0.35
bump.inputs["Distance"].default_value = float(H.max() - H.min()) * 0.6
L.new(alb.outputs["Color"], bsdf.inputs["Base Color"])
L.new(hgt.outputs["Color"], bump.inputs["Height"]); L.new(bump.outputs["Normal"], bsdf.inputs["Normal"])
bsdf.inputs["Roughness"].default_value = meta.get("rough", 0.8)
L.new(emi.outputs["Color"], bsdf.inputs["Emission Color"]); bsdf.inputs["Emission Strength"].default_value = 1.6
ground.data.materials.append(m)


# ---------------------------------------------------------------- detail templates (local, unit = tile)
def heart(n=14):
    pts = []
    for k in range(n):
        t = math.pi * 2 * k / n
        x = 16 * math.sin(t) ** 3
        y = 13 * math.cos(t) - 5 * math.cos(2 * t) - 2 * math.cos(3 * t) - math.cos(4 * t)
        pts.append((x / 34.0, (y + 17) / 34.0))      # point at origin-ish, notch at +y
    return pts


HEART = heart()


def fan(outline, cz, zf):
    """polygon fan around centroid; zf(x,y)->z."""
    cx = sum(p[0] for p in outline) / len(outline); cy = sum(p[1] for p in outline) / len(outline)
    v = [(cx, cy, cz)] + [(x, y, zf(x, y)) for x, y in outline]
    f = [(0, i + 1, (i + 1) % len(outline) + 1) for i in range(len(outline))]
    return v, f


def t_clover(s, r):
    V, Fc = [], []
    for k in range(3):
        a = k * 2.094 + r.uniform(-0.25, 0.25)
        ln = s * 0.5 * r.uniform(0.85, 1.1)
        out = []
        for (hx, hy) in HEART:
            x, y = hx * ln * 1.05, hy * ln
            out.append((x * math.cos(a) - y * math.sin(a), x * math.sin(a) + y * math.cos(a)))
        v, f = fan(out, s * 0.18, lambda x, y: s * 0.10 + 0.25 * math.hypot(x, y) - 0.0 * s)
        base = len(V); V += v; Fc += [tuple(i + base for i in t) for t in f]
    return V, Fc


def t_tuft(s, r):
    V, Fc = [], []
    nb = r.randint(5, 8)
    for k in range(nb):
        a = r.random() * 6.283; ln = s * r.uniform(0.45, 0.8); w = s * 0.07
        ca, sa = math.cos(a), math.sin(a)
        base = len(V)
        V += [(-sa * w, ca * w, 0.002), (sa * w, -ca * w, 0.002), (ca * ln, sa * ln, ln * 0.55)]
        Fc.append((base, base + 1, base + 2))
    return V, Fc


def t_flower(s, r):
    V, Fc = [], []
    for k in range(5):
        a = k * 1.2566
        out = []
        for j in range(10):
            t = math.pi * 2 * j / 10
            x = (math.cos(t) * 0.5 + 0.5) * s * 0.5; y = math.sin(t) * s * 0.15
            out.append((x * math.cos(a) - y * math.sin(a), x * math.sin(a) + y * math.cos(a)))
        v, f = fan(out, s * 0.25, lambda x, y: s * 0.25 + 0.15 * math.hypot(x, y))
        base = len(V); V += v; Fc += [tuple(i + base for i in t) for t in f]
    return V, Fc


def t_center(s, r):
    out = [(math.cos(t) * s * 0.13, math.sin(t) * s * 0.13) for t in np.linspace(0, 6.283, 9)[:-1]]
    return fan(out, s * 0.36, lambda x, y: s * 0.31)


def t_speck(s, r):
    V = [(s, 0, s), (-s, 0, s), (0, s, s), (0, -s, s), (0, 0, 2.2 * s), (0, 0, 0)]
    Fc = [(0, 2, 4), (2, 1, 4), (1, 3, 4), (3, 0, 4), (2, 0, 5), (1, 2, 5), (3, 1, 5), (0, 3, 5)]
    return V, Fc


def t_petal(s, r):
    out = []
    for j in range(12):
        t = math.pi * 2 * j / 12
        x = math.cos(t) * s * 0.5; y = math.sin(t) * s * 0.26 * (0.55 + 0.45 * (1 + math.cos(t)) / 2)
        out.append((x, y))
    bend = r.uniform(0.1, 0.35)
    return fan(out, 0.003, lambda x, y: 0.002 + bend * (y * y) / s * 2 + 0.002)


def t_blob(s, r, flat=0.5, n=7):
    V, Fc = [], []
    rings = [(0.0, 1.0), (0.55, 0.85), (0.9, 0.45)]
    for (zf, rf) in rings:
        for k in range(n):
            a = k * 6.283 / n
            j = r.uniform(0.85, 1.12)
            V.append((math.cos(a) * s * rf * j, math.sin(a) * s * rf * j, zf * s * flat))
    V.append((0, 0, s * flat * 1.05))
    for ri in range(2):
        for k in range(n):
            a0 = ri * n + k; a1 = ri * n + (k + 1) % n
            Fc.append((a0, a1, a1 + n, a0 + n))
    top = len(V) - 1
    for k in range(n):
        Fc.append((2 * n + k, 2 * n + (k + 1) % n, top))
    return V, Fc


TEMPL = {"clover": ("leaf", t_clover), "tuft": ("leaf", t_tuft), "flower": ("leaf", t_flower),
         "petal": ("leaf", t_petal), "pebble": ("leaf", lambda s, r: t_blob(s, r, 0.45)),
         "moss": ("leaf", lambda s, r: t_blob(s, r, 0.55, 6)), "mossflat": ("leaf", lambda s, r: t_blob(s, r, 0.25, 7)), "speck": ("glow", t_speck)}
import random
buckets = {"leaf": [[], [], []], "glow": [[], [], []], "fcentre": [[], [], []]}


def add(bucket, V, Fc, x, y, rot, col, zbase):
    vb, fb, cb = buckets[bucket]
    ca, sa = math.cos(rot), math.sin(rot)
    for ox in (-MM, 0, MM):
        for oy in (-MM, 0, MM):
            wx, wy = x - MI + ox, (1 - (y - MJ)) + oy
            if not (LO - 0.08 < wx < HI + 0.08 and LO - 0.08 < wy < HI + 0.08):
                continue
            base = len(vb)
            for (vx, vy, vz) in V:
                vb.append((wx + vx * ca - vy * sa, wy + vx * sa + vy * ca, zbase + vz))
                cb.append(col)
            fb.extend([tuple(i + base for i in f) for f in Fc])


for k, o in enumerate(meta["objects"]):
    r = random.Random(hash((o["x"], o["y"], o["t"])) & 0xFFFFFFFF)
    bucket, fn = TEMPL[o["t"]]
    V, Fc = fn(o["s"], r)
    z0 = float(hsample(np.array(o["x"] - MI), np.array(o["y"] - MJ))) - 0.001
    col = tuple(srgb2lin(o["col"])) + (1.0,)
    add(bucket, V, Fc, o["x"], o["y"], o["rot"], col, z0)
    if o["t"] == "flower":
        V2, F2 = t_center(o["s"], r)
        add("fcentre", V2, F2, o["x"], o["y"], o["rot"], tuple(srgb2lin((255, 236, 160))) + (1.0,), z0)


def make_mat(name, emis=0.0, rough=0.6):
    m = bpy.data.materials.new(name); m.use_nodes = True
    nt = m.node_tree; b = nt.nodes["Principled BSDF"]
    at = nt.nodes.new("ShaderNodeAttribute"); at.attribute_name = "Col"
    nt.links.new(at.outputs["Color"], b.inputs["Base Color"])
    b.inputs["Roughness"].default_value = rough
    if emis:
        nt.links.new(at.outputs["Color"], b.inputs["Emission Color"]); b.inputs["Emission Strength"].default_value = emis
    return m


mats = {"leaf": make_mat("leaf", 0, 0.55), "glow": make_mat("glow", 9.0, 0.4), "fcentre": make_mat("fcentre", 1.2, 0.5)}
for bname, (vb, fb, cb) in buckets.items():
    if not vb:
        continue
    me = bpy.data.meshes.new(bname)
    me.from_pydata(vb, [], fb)
    ca = me.color_attributes.new("Col", "FLOAT_COLOR", "POINT")
    ca.data.foreach_set("color", np.array(cb, np.float32).ravel())
    me.update()
    ob = bpy.data.objects.new(bname, me); sc.collection.objects.link(ob)
    ob.data.materials.append(mats[bname])
    for p in me.polygons:
        p.use_smooth = bname != "leaf"

# ---------------------------------------------------------------- light + camera
C.world(sc, strength=0.75)
Ldir = Vector((-0.58, 0.81, 0.0)).normalized() * math.cos(math.radians(52))
Ldir.z = math.sin(math.radians(52))
sun = bpy.data.lights.new("Key", "SUN"); sun.energy = 3.6; sun.color = (1.0, 0.93, 0.82); sun.angle = math.radians(4)
so = bpy.data.objects.new("Key", sun); sc.collection.objects.link(so)
so.rotation_euler = Ldir.to_track_quat("Z", "Y").to_euler()
cam = bpy.data.cameras.new("cam"); cam.type = "ORTHO"; cam.ortho_scale = 1.0; cam.clip_start = 0.1; cam.clip_end = 20
co = bpy.data.objects.new("cam", cam); sc.collection.objects.link(co)
co.location = (0.5, 0.5, 5.0); co.rotation_euler = (0, 0, 0)
sc.camera = co
sc.render.filepath = f"{W}/{NAME}_render.png"
bpy.ops.render.render(write_still=True)
print("RENDERED", NAME)
