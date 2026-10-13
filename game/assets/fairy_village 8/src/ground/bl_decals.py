"""Blender (headless) renderer for ground decals + building contact skirts.
blender -b -P src/ground/bl_decals.py -- <decal_name> [samples]
Same oblique game projection + light rig as the buildings pack (fv_common.game_camera / rig),
transparent film with a shadow catcher, 4x master (160 px / tile). Writes work/ground/decal_<name>_4x.png
and work/ground/decal_<name>_meta.json (canvas tiles, origin_px of the footprint NW corner).
"""
import bpy, bmesh, sys, os, math, random, json
from mathutils import Vector
sys.path.insert(0, "/workspace/fairy_village/src/blender")
import fv_common as C

argv = sys.argv[sys.argv.index("--") + 1:]
NAME = argv[0]
SAMPLES = int(argv[1]) if len(argv) > 1 else 96
T = C.T
W = "/workspace/fairy_village/work/ground"
sc = C.reset()
C.cycles(sc, samples=SAMPLES, transparent=True)
C.rig(sc)
col = sc.collection
root = C.game_root(col)
made = []
rnd = random.Random(hash(NAME) & 0xFFFF)


def keep(o):
    made.append(o)
    return o


def mat(name, c, rough=0.6, **kw):
    return C.principled(name, c, rough=rough, **kw)


GREEN = [(0.10, 0.30, 0.07), (0.16, 0.40, 0.09), (0.22, 0.46, 0.12), (0.12, 0.34, 0.14)]


def blades(cx, cy, n=9, h=0.10, spread=0.06, colr=None):
    bm = bmesh.new()
    for k in range(n):
        a = rnd.uniform(0, 6.283); r0 = rnd.uniform(0, spread)
        bx, by = cx + r0 * math.cos(a), cy + r0 * math.sin(a)
        lean = rnd.uniform(0.2, 0.7); hh = h * rnd.uniform(0.6, 1.2); w = h * 0.07
        ca, sa = math.cos(a), math.sin(a)
        v1 = bm.verts.new((bx - sa * w, by + ca * w, 0)); v2 = bm.verts.new((bx + sa * w, by - ca * w, 0))
        v3 = bm.verts.new((bx + ca * hh * lean, by + sa * hh * lean, hh))
        bm.faces.new((v1, v2, v3))
    o = C.obj_from_bm(bm, "blades", mat("FV_DBlade%d" % int(rnd.random() * 4), colr or rnd.choice(GREEN), 0.7), col, smooth=False)
    return keep(o)


def leaf(name, base, ang, ln, wd, lift, m, droop=0.5):
    bm = bmesh.new()
    pts = []
    for k in range(9):
        t = k / 8
        w = wd * math.sin(math.pi * t) ** 0.8
        z = lift * math.sin(math.pi * t * 0.8) - droop * lift * t * t
        pts.append((t * ln, w, z)); 
    left = [bm.verts.new((x, y, z)) for x, y, z in pts]
    right = [bm.verts.new((x, -y, z)) for x, y, z in pts[1:-1]]
    mid = [bm.verts.new((x, 0, z + 0.004)) for x, y, z in pts[1:-1]]
    for k in range(len(mid) - 1):
        bm.faces.new((left[k + 1], left[k + 2], mid[k + 1], mid[k]))
        bm.faces.new((mid[k], mid[k + 1], right[k + 1], right[k]))
    bm.faces.new((left[0], left[1], mid[0])); bm.faces.new((left[0], mid[0], right[0]))
    bm.faces.new((mid[-1], left[-2], left[-1])); bm.faces.new((mid[-1], left[-1], right[-1]))
    o = C.obj_from_bm(bm, name, m, col)
    o.location = (base[0], base[1], base[2] if len(base) > 2 else 0); o.rotation_euler = (0, 0, ang)
    return keep(o)


def petal(name, x, y, ang, ln, m, z=0.004):
    bm = bmesh.new()
    pts = [(0, 0), (0.3, 0.32), (0.7, 0.34), (1.0, 0.0), (0.7, -0.34), (0.3, -0.32)]
    vs = [bm.verts.new((u * ln, w * ln * 0.55, z + 0.02 * ln * (w * w) * 8)) for u, w in pts]
    bm.faces.new(vs)
    o = C.obj_from_bm(bm, name, m, col)
    o.location = (x, y, 0); o.rotation_euler = (rnd.uniform(-0.15, 0.15), rnd.uniform(-0.15, 0.15), ang)
    return keep(o)


def stone(name, x, y, r, m, squash=0.55):
    o = C.ico(name, r, (x, y, r * squash * 0.35), sub=3, mat=m, col=col, scale=(1, rnd.uniform(0.75, 1.0), squash))
    C.displace(o, r * 0.3, r * 1.5)
    o.rotation_euler = (0, 0, rnd.uniform(0, 6.28))
    return keep(o)


def moss(x, y, r, m=None):
    o = C.ico("moss", r, (x, y, 0), sub=2, mat=m or mat("FV_DMoss", (0.12, 0.30, 0.07), 0.9), col=col, scale=(1, rnd.uniform(0.7, 1), 0.35))
    C.displace(o, r * 0.35, r * 0.8)
    return keep(o)


def shroom(x, y, h, cr, capc, glow=(0.6, 0.45, 1.0), strength=1.2):
    strength *= 0.45
    o = C.mushroom("sh", (x, y, 0), h=h, cap_r=cr, cap_col=capc, glow=glow, col=col, lean=rnd.uniform(-0.12, 0.12), strength=strength)
    keep(o); made.extend(o.children)
    return o


def fern(cx, cy, n=7, ln=0.42):
    fm = mat("FV_Fern", (0.12, 0.36, 0.08), 0.65, sss=0.2)
    for k in range(n):
        a = k * 6.283 / n + rnd.uniform(-0.25, 0.25)
        L = ln * rnd.uniform(0.75, 1.1)
        bm = bmesh.new()
        segs = 9
        for s in range(segs):
            t0 = s / segs
            x0 = t0 * L; z0 = 0.16 * math.sin(math.pi * t0 * 0.9) - 0.03 * t0
            wl = (0.09 * (1 - t0) ** 0.7 + 0.015) * L
            for side in (1, -1):
                tipx = x0 + 0.35 * wl; tipy = side * wl
                v1 = bm.verts.new((x0, 0, z0 + 0.01)); v2 = bm.verts.new((x0 + L / segs * 0.9, 0, z0 + 0.01))
                v3 = bm.verts.new((tipx + L / segs * 0.5, tipy, z0 - 0.02 * t0))
                bm.faces.new((v1, v2, v3) if side > 0 else (v2, v1, v3))
        o = C.obj_from_bm(bm, "frond", fm, col, smooth=False)
        o.location = (cx, cy, 0); o.rotation_euler = (0, 0, a)
        keep(o)


# ------------------------------------------------------------------ decal builders (metres; footprint x 0..wT, y -hT..0)
def b_mushroom_ring():
    cx, cy = T, -T
    caps = [(0.46, 0.20, 0.76), (0.95, 0.86, 0.78), (0.80, 0.30, 0.60), (0.46, 0.20, 0.76)]
    n = 14
    for k in range(n):
        a = k * 6.283 / n + rnd.uniform(-0.12, 0.12); R = 0.68 * T * rnd.uniform(0.92, 1.08)
        x, y = cx + R * math.cos(a), cy + R * math.sin(a)
        s = rnd.uniform(0.75, 1.25)
        shroom(x, y, 0.17 * s, 0.10 * s, rnd.choice(caps), strength=1.0)
        if k % 2 == 0:
            blades(x + 0.05, y - 0.03, 6, 0.08)
        if rnd.random() < 0.4:
            shroom(x + rnd.uniform(-0.08, 0.08), y + rnd.uniform(-0.08, 0.08), 0.07, 0.04, rnd.choice(caps), strength=0.8)
    for k in range(5):
        a = rnd.uniform(0, 6.28); R = rnd.uniform(0.62, 0.78) * T
        keep(C.ico("spark", 0.012, (cx + R * math.cos(a), cy + R * math.sin(a), rnd.uniform(0.15, 0.35)), sub=1,
                   mat=C.glow_mat("FV_Spark", (0.7, 0.85, 1.0), 12), col=col))
    return (2, 2), (-0.25, 2.25, -2.25, 0.75)


def b_toadstool_cluster():
    cx, cy = T * 0.5, -T * 0.55
    capc = (0.42, 0.15, 0.72)
    for (dx, dy, s) in ((0, 0, 1.0), (0.3, 0.1, 0.7), (-0.28, 0.12, 0.62), (0.1, -0.26, 0.5), (-0.14, -0.22, 0.38)):
        shroom(cx + dx, cy + dy, 0.42 * s, 0.24 * s, capc if s > 0.45 else (0.86, 0.5, 0.78), strength=1.6)
    blades(cx - 0.25, cy - 0.12, 8, 0.1); blades(cx + 0.28, cy - 0.1, 7, 0.09); moss(cx + 0.05, cy - 0.05, 0.16)
    return (1, 1), (-0.25, 1.25, -1.25, 0.9)


def b_moonpetal_clump():
    cx, cy = T * 0.5, -T * 0.52
    lm = mat("FV_LeafLance", (0.13, 0.38, 0.10), 0.55, sss=0.15)
    for k in range(12):
        a = k * 6.283 / 12 + rnd.uniform(-0.2, 0.2)
        leaf("lf", (cx, cy, 0.01), a, rnd.uniform(0.22, 0.34), 0.035, 0.10, lm, 0.8)
    stem_m = mat("FV_Stem", (0.18, 0.42, 0.12), 0.6)
    for k in range(7):
        a = rnd.uniform(0, 6.28); r0 = rnd.uniform(0.0, 0.16); h = rnd.uniform(0.16, 0.28)
        x, y = cx + r0 * math.cos(a), cy + r0 * math.sin(a)
        keep(C.tube_curve("st", [(cx, cy, 0), ((cx + x) / 2, (cy + y) / 2, h * 0.6), (x, y, h)], radius=0.008, mat=stem_m, col=col))
        cb = rnd.choice([(0.78, 0.70, 1.0), (0.92, 0.90, 1.0), (0.70, 0.76, 1.0)])
        f = C.flower("mp", (x, y, h), r=rnd.uniform(0.06, 0.08), petals=5, c_base=cb, c_tip=(1, 1, 1), center=(1.0, 0.92, 0.6),
                     col=col, glow=(0.6, 0.65, 1.0), tilt=rnd.uniform(-0.3, 0.3), rot=rnd.uniform(0, 6.28))
        keep(f); made.extend(f.children)
    return (1, 1), (-0.25, 1.25, -1.25, 0.9)


def b_rosebell_clump():
    cx, cy = T * 0.5, -T * 0.5
    lm = mat("FV_LeafRound", (0.15, 0.40, 0.12), 0.55, sss=0.15)
    for k in range(9):
        a = k * 6.283 / 9 + rnd.uniform(-0.2, 0.2)
        leaf("lf", (cx, cy, 0.01), a, rnd.uniform(0.16, 0.24), 0.06, 0.07, lm, 0.6)
    stem_m = mat("FV_Stem", (0.18, 0.42, 0.12), 0.6)
    bell = mat("FV_Bell", (1.0, 0.50, 0.72), 0.45, sss=0.4, emit=(1.0, 0.6, 0.8), emit_strength=0.25)
    for k in range(5):
        a = k * 6.283 / 5 + rnd.uniform(-0.3, 0.3); h = rnd.uniform(0.22, 0.32); L = rnd.uniform(0.14, 0.22)
        p0 = (cx, cy, 0); p1 = (cx + 0.3 * L * math.cos(a), cy + 0.3 * L * math.sin(a), h)
        p2 = (cx + L * math.cos(a), cy + L * math.sin(a), h * 0.85)
        keep(C.tube_curve("st", [p0, p1, p2], radius=0.007, mat=stem_m, col=col))
        for j in range(3):
            t = 0.45 + 0.25 * j
            bx = p1[0] + (p2[0] - p1[0]) * t; by = p1[1] + (p2[1] - p1[1]) * t; bz = p1[2] + (p2[2] - p1[2]) * t - 0.03
            b = C.cyl("bell", 0.026, 0.05, (bx, by, bz), segs=10, mat=bell, col=col, r2=0.012)
            keep(b)
    blades(cx + 0.2, cy - 0.15, 6, 0.09)
    return (1, 1), (-0.25, 1.25, -1.25, 0.9)


def b_fallen_petals():
    ms = [C.petal_mat("FV_FP%d" % i, c, (1, 0.95, 0.98)) for i, c in enumerate([(0.95, 0.45, 0.66), (0.98, 0.66, 0.80), (0.74, 0.56, 0.95), (1.0, 0.88, 0.86)])]
    for k in range(34):
        r0 = T * 0.42 * math.sqrt(rnd.random()); a = rnd.uniform(0, 6.28)
        petal("pt", T * 0.5 + r0 * math.cos(a), -T * 0.5 + r0 * math.sin(a), rnd.uniform(0, 6.28), rnd.uniform(0.07, 0.10), rnd.choice(ms))
    return (1, 1), (-0.25, 1.25, -1.25, 0.5)


def b_glow_stones():
    cx, cy = T * 0.5, -T * 0.5
    gm = C.principled("FV_GlowStone", (0.72, 0.82, 0.95), rough=0.25, emit=(0.45, 0.75, 1.0), emit_strength=1.4, sss=0.5, coat=0.5)
    for (dx, dy, r) in ((0, 0, 0.13), (0.2, 0.1, 0.09), (-0.16, 0.12, 0.08), (0.06, -0.2, 0.06)):
        stone("gs", cx + dx, cy + dy, r, gm, 0.7)
        moss(cx + dx + r * 0.6, cy + dy - r * 0.6, r * 0.6)
    blades(cx - 0.22, cy - 0.12, 7, 0.09); blades(cx + 0.25, cy - 0.12, 6, 0.08)
    return (1, 1), (-0.25, 1.25, -1.25, 0.6)


def b_fairy_lantern():
    cx, cy = T * 0.5, -T * 0.55
    wood = C.wood_mat(); gold = C.gold_mat()
    keep(C.cyl("stake", 0.022, 0.55, (cx, cy, 0.275), segs=8, mat=wood, col=col, r2=0.016))
    keep(C.tube_curve("hook", [(cx, cy, 0.54), (cx + 0.05, cy, 0.62), (cx + 0.13, cy, 0.60), (cx + 0.16, cy, 0.52)], radius=0.008, mat=gold, col=col))
    lx, lz = cx + 0.16, 0.42
    keep(C.cyl("glass", 0.045, 0.085, (lx, cy, lz), segs=6, mat=C.glow_mat("FV_LanternGlow", (1.0, 0.72, 0.34), 7.0), col=col, smooth=False))
    keep(C.cyl("capT", 0.055, 0.03, (lx, cy, lz + 0.055), segs=6, mat=gold, col=col, r2=0.01, smooth=False))
    keep(C.cyl("capB", 0.05, 0.02, (lx, cy, lz - 0.05), segs=6, mat=gold, col=col, smooth=False))
    blades(cx, cy, 10, 0.12); moss(cx - 0.05, cy - 0.03, 0.07)
    shroom(cx - 0.15, cy - 0.08, 0.08, 0.05, (0.62, 0.36, 0.86), strength=1.0)
    return (1, 1), (-0.25, 1.25, -1.25, 1.25)


def b_fern_clump():
    fern(T * 0.5, -T * 0.5, 8, 0.45)
    return (1, 1), (-0.25, 1.25, -1.25, 0.8)


def b_pebbles():
    sm = C.stone_mat("FV_Pebble", (0.42, 0.42, 0.44), (0.70, 0.68, 0.66), moss_amt=0.45)
    for k in range(9):
        r0 = T * 0.32 * math.sqrt(rnd.random()); a = rnd.uniform(0, 6.28)
        stone("pb", T * 0.5 + r0 * math.cos(a), -T * 0.5 + r0 * math.sin(a), rnd.uniform(0.035, 0.09), sm, 0.5)
    blades(T * 0.45, -T * 0.55, 6, 0.07)
    return (1, 1), (-0.25, 1.25, -1.25, 0.5)


# ------------------------------------------------------------------ contact skirts (footprint-anchored)
def b_queens_tree_hall_skirt():
    Wt, Dt = 9, 9
    tx, ty = Wt * T / 2, -Dt * T + 0.9 + 2.35          # same trunk centre as fv_buildings.build_tree_hall
    rb = C.bark_mat("FV_BarkRoot", (0.16, 0.10, 0.06), (0.40, 0.28, 0.18), (0.30, 0.22, 0.14))
    mm = mat("FV_SkirtMoss", (0.12, 0.32, 0.07), 0.9)
    r_in = 3.6
    for i in range(18):
        a = 2 * math.pi * i / 18 + rnd.uniform(-0.12, 0.12)
        deg = math.degrees(a) % 360
        if abs(deg - 270) < 30:
            continue                                  # keep the door + stand tile clear
        L = rnd.uniform(1.0, 2.3)
        pts = []
        for k in range(5):
            t = k / 4
            rr = r_in + L * t
            aa = a + 0.18 * math.sin(t * 3 + i)
            pts.append((tx + rr * math.cos(aa), ty + rr * math.sin(aa), 0.12 * (1 - t) + 0.02))
        keep(C.tube_curve("sroot", pts, radius=rnd.uniform(0.10, 0.17), mat=rb, col=col, radii=[1.0, 0.8, 0.55, 0.35, 0.12]))
        e = pts[2]
        moss(e[0], e[1], rnd.uniform(0.18, 0.3), mm)
    for k in range(26):
        a = rnd.uniform(0, 6.283); deg = math.degrees(a) % 360
        if abs(deg - 270) < 26:
            continue
        rr = rnd.uniform(3.4, 5.2); x, y = tx + rr * math.cos(a), ty + rr * math.sin(a)
        moss(x, y, rnd.uniform(0.15, 0.32), mm)
        if rnd.random() < 0.5:
            blades(x + 0.1, y, 8, 0.14)
    for k in range(7):
        a = rnd.uniform(0, 6.283)
        if abs(math.degrees(a) % 360 - 270) < 35:
            continue
        rr = rnd.uniform(3.6, 4.8)
        shroom(tx + rr * math.cos(a), ty + rr * math.sin(a), 0.16, 0.1, rnd.choice([(0.62, 0.36, 0.86), (0.95, 0.86, 0.78)]), strength=1.0)
    for k in range(3):
        a = rnd.choice([math.radians(200), math.radians(330), math.radians(150), math.radians(30)]) + rnd.uniform(-0.2, 0.2)
        fern(tx + 4.3 * math.cos(a), ty + 4.3 * math.sin(a), 6, 0.5)
    return (9, 9), (-1, 10, -10, 1)


def _rim(cx, cy, R, n_moss, Wt, Dt, door_ang=270):
    mm = mat("FV_SkirtMoss", (0.12, 0.32, 0.07), 0.9)
    for k in range(n_moss):
        a = rnd.uniform(0, 6.283)
        if abs(math.degrees(a) % 360 - door_ang) < 18:
            continue
        rr = R + rnd.uniform(-0.05, 0.12)
        moss(cx + rr * math.cos(a), cy + rr * math.sin(a), rnd.uniform(0.07, 0.15), mm)
        if rnd.random() < 0.35:
            blades(cx + (rr + 0.08) * math.cos(a), cy + (rr + 0.08) * math.sin(a), 6, 0.08)
    for k in range(int(n_moss / 5)):
        a = rnd.uniform(0, 6.283)
        if abs(math.degrees(a) % 360 - door_ang) < 25:
            continue
        rr = R + rnd.uniform(0.05, 0.2)
        stone("rs", cx + rr * math.cos(a), cy + rr * math.sin(a), rnd.uniform(0.04, 0.07),
              C.stone_mat("FV_Pebble", (0.42, 0.42, 0.44), (0.70, 0.68, 0.66), moss_amt=0.45), 0.5)


def b_moonstone_fountain_rim():
    Wt = Dt = 5
    _rim(Wt * T / 2, -Dt * T / 2, 3.55, 70, Wt, Dt)
    return (5, 5), (-1, 6, -6, 1)


def b_lily_fountain_rim():
    Wt = Dt = 3
    _rim(Wt * T / 2, -Dt * T / 2, 2.15, 44, Wt, Dt)
    return (3, 3), (-1, 4, -4, 1)


BUILD = {k[2:]: v for k, v in globals().items() if k.startswith("b_")}
fp, fixed = BUILD[NAME]()
for o in made:
    if o.parent is None:
        o.parent = root
root.scale = (1.0, 1.0 / C.SIN, C.ZEX)
L, R, B, Tp = fixed
catch = C.shadow_catcher("catch", (max(R - L, Tp - B) + 4) * T, ((L + R) / 2 * T, (B + Tp) / 2 * T, 0), col)
catch.parent = root
bpy.context.view_layer.update()
meta = C.game_camera(sc, [o for o in made], fixed=fixed)
meta.update({"name": NAME, "footprint_tiles": fp})
C.render(sc, f"{W}/decal_{NAME}_4x.png")
C.save_json(f"{W}/decal_{NAME}_meta.json", meta)
print("DECAL", NAME, meta["size"])
