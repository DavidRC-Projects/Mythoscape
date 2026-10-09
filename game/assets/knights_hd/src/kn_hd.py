"""Mythoscape HD attackable knights (Blender 4.2 / Cycles) on the CC0 stylized base bodies, FK rig, idle/walk/attack.
  blender -b -P kn_hd.py -- --key knight --mode hero|portrait|sprites|test|all [--preview] [--samples N] [--states idle,walk,attack]
"""
import bpy, bmesh, math, os, random, sys, json
from mathutils import Vector, Matrix, Euler
sys.path.insert(0, "/workspace/fairy_village/src/blender")
sys.path.insert(0, "/workspace/npc_hd_overworld/batch4/src")
sys.path.insert(0, "/workspace/knights_hd/src")
import fv_common as C
import fv_npc_helpers as H
import kn_rig as RG
import kn_parts as KP
from kn_rig import WMODE

OUT = "/workspace/knights_hd"
KEY = C.arg("--key", "knight")
MODE = C.arg("--mode", "hero")
PREVIEW = bool(C.arg("--preview", False))
FACINGS = C.arg("--facings", "s,e,n,w").split(",")
SAMPLES = int(C.arg("--samples", 40))
SPRDIR = C.arg("--sprdir", "sprite_4x")
STATES = C.arg("--states", "idle,walk,attack,hit,death").split(",")
H.KEY = KEY; H.MODE = MODE; H.OUT = OUT; H.PREVIEW = PREVIEW; H.SAMPLES = SAMPLES; H.ANIM.clear()
NFR = {"idle": 4, "walk": 8, "attack": 6, "hit": 3, "death": 6}
CANVAS = (512, 576); FEET = (256, 528); PPM = 175.6


def srgb(c):
    return tuple(x for x in c)


# ------------------------------------------------------------------ base body
def age_face(body, face, s, amount=1.0):
    nose = face["nose"]; mouth = face["mouth"]; ez = face["eye_z"]
    for v in body.data.vertices:
        co = v.co
        for side in (1, -1):
            ch = Vector((side * 0.055 * s, nose.y + 0.02 * s, (ez + mouth.z) / 2))
            d = (co - ch).length
            if d < 0.05 * s and co.y < 0:
                v.co.y += (1 - d / (0.05 * s)) ** 2 * 0.013 * s * amount
        if abs(co.x) < 0.08 * s and abs(co.z - (ez + 0.03 * s)) < 0.025 * s and co.y < -0.05 * s:
            v.co.y -= 0.006 * s * amount; v.co.z += 0.003 * s * amount
    body.data.update()


def base(col, sex="male", skin=(0.75, 0.55, 0.43), iris=(0.3, 0.4, 0.6), scale=1.0, age=0.0, eye_glow=None, arm_angle=10.0, eye_k=8.0):
    body, eyes = H.take_body(col, sex)
    if scale != 1.0:
        body.data.transform(Matrix.Scale(scale, 4))
        for e in eyes:
            e.location = e.location * scale; e.scale = e.scale * scale
    h = max(v.co.z for v in body.data.vertices); s = h / 1.617
    H.pose_arms(body, arm_angle, pivot=(0.17, 1.29), h=h)
    mask = H.arm_mask(body, h)
    tree = H.bvh(body); face = H.find_face(tree, eyes)
    if age:
        age_face(body, face, s, age); tree = H.bvh(body); face = H.find_face(tree, eyes)
    sk = H.skin_mat("KN_Skin_" + KEY, base=skin, lips=tuple(c * 0.75 for c in skin), blush=tuple(c * 0.95 for c in skin))
    H.setup_skin(body, eyes, tree, sk, iris, face, s)
    if eye_glow:
        g = KP.glow("KN_EyeGlow_" + KEY, eye_glow, eye_k)
        for e in eyes:
            e.data.materials.clear(); e.data.materials.append(g)
    for e in eyes:
        WMODE[e.name] = ("bone", "head")
    J = RG.joints(body, mask, h, face)
    W = RG.body_weights(body, mask, J)
    groups = {}
    for i, w in enumerate(W):
        for b, bw in w.items():
            if bw > 1e-3:
                if b not in groups:
                    groups[b] = body.vertex_groups.new(name=b)
                groups[b].add([i], bw, "REPLACE")
    WMODE[body.name] = "body"
    return dict(body=body, eyes=eyes, mask=mask, tree=tree, face=face, s=s, h=h, J=J, skin=sk, sex=sex, W=W,
                rest_co=[v.co.copy() for v in body.data.vertices])


# ------------------------------------------------------------------ generic plate harness
def suit(ctx, col, M, o):
    body, mask, s, J, face = ctx["body"], ctx["mask"], ctx["s"], ctx["J"], ctx["face"]
    at = J["arm_t"]; ez = face["eye_z"]
    P, T, R, LTH = M["plate"], M["trim"], M["rivet"], M["leather"]
    er = o.get("edge_r", 0.0055)

    def arm(lo, hi):
        return lambda v: v.index in at and lo <= at[v.index][0] < hi

    def tor(lo, hi, extra=None):
        return lambda v: (v.index not in at) and lo * s < v.co.z < hi * s and (extra is None or extra(v))
    KP.shell(ctx, "breast", tor(1.03, 1.44), 0.022, 0.013, M.get("breast", P), col, smooth=10, trim=T, edge_r=er, rivets=R, rivet_every=7)
    KP.shell(ctx, "gorget", tor(1.40, 1.58, lambda v: v.co.z < ez - 0.075 * s), 0.036, 0.010, P, col, smooth=4, trim=T, edge_r=er * 0.9,
             rivets=R, rivet_every=6)
    for k, (lo, hi, off) in enumerate(((0.975, 1.045, 0.031), (0.925, 0.99, 0.037), (0.875, 0.94, 0.043))):
        KP.shell(ctx, f"fauld{k}", tor(lo, hi), off, 0.010, P, col, smooth=3, trim=T, edge_r=er * 0.85, rivets=R, rivet_every=9)
    KP.shell(ctx, "mail_skirt", tor(0.72, 0.90), 0.02, 0.006, M["mail"], col)
    if o.get("tassets", True):
        KP.shell(ctx, "tassets", tor(0.74, 0.88, lambda v: v.co.y < J["yc"] - 0.03 * s and abs(v.co.x) > 0.025 * s), 0.052, 0.010, P, col,
                 smooth=3, trim=T, edge_r=er * 0.85, rivets=R, rivet_every=6)
    KP.shell(ctx, "cuisses", tor(0.58, 0.84), 0.027, 0.011, P, col, smooth=3, trim=T, edge_r=er * 0.8, rivets=R, rivet_every=9)
    KP.shell(ctx, "poleyns", tor(0.42, 0.565), 0.036, 0.012, P, col, smooth=4, trim=T, edge_r=er * 0.8, rivets=R, rivet_every=6)
    KP.shell(ctx, "greaves", tor(0.075, 0.435), 0.022, 0.010, P, col, smooth=3, trim=T, edge_r=er * 0.8)
    sabatons(ctx, col, M.get("boot", P), T, R, LTH)
    for sd, sx in (("L", 1), ("R", -1)):
        kn = J[f"knee_{sd}"]
        pts = [v.co for v in body.data.vertices if v.index not in at and v.co.x * sx > 0.004 and abs(v.co.z - kn.z) < 0.01]
        fy = min(p.y for p in pts)
        cop = C.uvsphere(f"kneecop{sd}", 0.052 * s, (kn.x, fy - 0.035 * s, kn.z + 0.01 * s), mat=P, col=col, scale=(1.0, 0.62, 0.85))
        WMODE[cop.name] = "single"
        fan = H.leaf_shape(f"kneefan{sd}", 0.075 * s, 0.05 * s, P, col, curl=0.3)
        fan.location = (kn.x + sx * 0.05 * s, fy - 0.0, kn.z + 0.01 * s); fan.rotation_euler = (math.radians(90), 0, math.radians(90 if sx > 0 else -90))
        WMODE[fan.name] = "single"
        C.ico(f"kneeboss{sd}", 0.012 * s, (kn.x, fy - 0.062 * s, kn.z + 0.01 * s), sub=2, mat=T, col=col)
    # arms
    cap = lambda v: (v.index in at and at[v.index][0] < 0.17) or ((v.index not in at) and abs(v.co.x) > 0.118 * s and 1.30 * s < v.co.z < ez - 0.1 * s)
    pz = o.get("paul_off", 0.05)
    KP.shell(ctx, "pauldron", cap, pz, 0.015, M.get("paul", P), col, smooth=6, trim=T, edge_r=er * 1.1, rivets=R, rivet_every=5)
    KP.shell(ctx, "paul_lame0", arm(0.13, 0.215), pz - 0.006, 0.011, M.get("paul", P), col, smooth=3, trim=T, edge_r=er * 0.9, rivets=R, rivet_every=6)
    KP.shell(ctx, "paul_lame1", arm(0.195, 0.275), pz - 0.012, 0.010, M.get("paul", P), col, smooth=3, trim=T, edge_r=er * 0.9, rivets=R, rivet_every=6)
    KP.shell(ctx, "rerebrace", arm(0.26, 0.40), 0.02, 0.009, P, col, smooth=2, trim=T, edge_r=er * 0.75)
    KP.shell(ctx, "couter", arm(0.37, 0.49), 0.03, 0.011, P, col, smooth=3, trim=T, edge_r=er * 0.8, rivets=R, rivet_every=6)
    KP.shell(ctx, "vambrace", arm(0.47, 0.71), 0.021, 0.009, P, col, smooth=2, trim=T, edge_r=er * 0.75)
    KP.shell(ctx, "gauntlet", arm(0.70, 1.01), 0.011, 0.006, M.get("gaunt", P), col)
    KP.shell(ctx, "cuff", arm(0.68, 0.765), 0.032, 0.009, P, col, smooth=2, trim=T, edge_r=er * 0.8, rivets=R, rivet_every=7)
    for sd in ("L", "R"):
        el = J[f"elbow_{sd}"]
        cp = C.uvsphere(f"elbowcop{sd}", 0.045 * s, el + Vector((0, 0.03 * s, 0)), mat=P, col=col, scale=(0.9, 0.7, 0.9))
        WMODE[cp.name] = "single"
        C.ico(f"elbowboss{sd}", 0.011 * s, el + Vector((0, 0.062 * s, 0)), sub=2, mat=T, col=col)
        KP.arm_ring(ctx, sd, 0.56, 0.03, 0.006, LTH, col, f"strapA{sd}", buckle=T)
        KP.arm_ring(ctx, sd, 0.645, 0.03, 0.006, LTH, col, f"strapB{sd}", buckle=T)
        KP.arm_ring(ctx, sd, 0.32, 0.026, 0.0055, LTH, col, f"strapC{sd}", buckle=T)
        KP.leg_ring(ctx, sd, 0.70 * s, 0.032, 0.0065, LTH, col, f"thighstrap{sd}", buckle=T)
        KP.leg_ring(ctx, sd, 0.22 * s, 0.027, 0.0055, LTH, col, f"shinstrap{sd}", buckle=T)
    # belt
    x0, x1, y0, y1 = H.section(body, 1.0 * s, mask)
    H.ring_curve("belt", 0, (y0 + y1) / 2, (x1 - x0) / 2 + 0.045, (y1 - y0) / 2 + 0.05, 1.0 * s, 0.015 * s, LTH, col)
    C.box("buckle", (0.075 * s, 0.016 * s, 0.06 * s), (0, y0 - 0.055 * s, 1.0 * s), T, col, bevel=0.005)
    C.box("pouch", (0.07 * s, 0.045 * s, 0.08 * s), (0.13 * s, y0 - 0.0, 0.95 * s), LTH, col, bevel=0.012, rot=(0, 0, math.radians(30)))
    # chest ridge
    hit, nrm = H.surf(ctx["tree"], (0, -0.8, 1.30 * s), (0, 1, 0))
    yfront = hit.y if hit else -0.15 * s
    ctx["chest_front"] = Vector((0, yfront - 0.036 * s, 1.22 * s))
    ctx["hide"] = lambda v: (v.index not in at and v.co.z < 1.40 * s) or (v.index in at and at[v.index][0] > 0.12)


def sabatons(ctx, col, P, T, R, LTH):
    """Articulated plate shoes (no toes): rounded shell + overlapping lames + sole."""
    J = ctx["J"]; s = ctx["s"]
    for sd, sx in (("L", 1), ("R", -1)):
        a, toe, heel = J[f"ankle_{sd}"], J[f"toe_{sd}"], J[f"heel_{sd}"]
        y0, y1 = toe.y - 0.03 * s, heel.y + 0.012 * s
        L = (y1 - y0); cy = (y0 + y1) / 2
        shoe = C.uvsphere(f"sabaton{sd}", 1.0, (a.x + sx * 0.004, cy, 0.0), segs=40, rings=20, mat=P, col=col)
        bm = bmesh.new(); bm.from_mesh(shoe.data)
        for v in bm.verts:
            x, y, z = v.co
            fr = max(0.0, -y)  # front half narrows to a rounded point
            v.co = Vector((x * 0.058 * s * (1 - 0.35 * fr ** 2), y * L / 2, max(z, -0.05) * (0.085 * s if y > -0.3 else 0.085 * s * (1 - 0.45 * (fr - 0.3)))))
        bmesh.ops.delete(bm, geom=[v for v in bm.verts if v.co.z < -0.004], context="VERTS")
        bm.to_mesh(shoe.data); bm.free()
        shoe.modifiers.new("Sol", "SOLIDIFY").thickness = 0.006; C.add_mod_subsurf(shoe, 1)
        for k in range(4):
            t = 0.18 + 0.17 * k
            yy = y0 + L * t
            rx = 0.058 * s * (1 - 0.35 * max(0.0, (cy - yy) / (L / 2)) ** 2) + 0.004
            hz = 0.085 * s * math.sqrt(max(0.05, 1 - ((yy - cy) / (L / 2)) ** 2)) + 0.004
            pts = [Vector((a.x + sx * 0.004 + rx * math.cos(u), yy, hz * math.sin(u))) for u in [math.pi * i / 16 for i in range(17)]]
            C.tube_curve(f"sab_lame{sd}{k}", pts, radius=0.0045 * s, mat=T, col=col, res=2, bevel_res=2)
        C.box(f"sab_sole{sd}", (0.10 * s, L * 0.95, 0.010 * s), (a.x + sx * 0.004, cy, 0.006 * s), LTH, col, bevel=0.004)
        C.ico(f"sab_rivet{sd}", 0.007 * s, (a.x + sx * (0.004 + 0.06 * s), cy + 0.03 * s, 0.045 * s), sub=1, mat=R, col=col)
        C.ico(f"sab_rivet2{sd}", 0.007 * s, (a.x + sx * (0.004 - 0.06 * s), cy + 0.03 * s, 0.045 * s), sub=1, mat=R, col=col)


# ------------------------------------------------------------------ emblems
def tower_emblem(name, loc, sc, mat, dark, col, normal_y=-1):
    x, y, z = loc
    objs = [C.box(name + "_body", (0.09 * sc, 0.008, 0.13 * sc), (x, y, z), mat, col, bevel=0.002)]
    for k in range(3):
        objs.append(C.box(f"{name}_cr{k}", (0.024 * sc, 0.008, 0.03 * sc), (x + (k - 1) * 0.034 * sc, y, z + 0.078 * sc), mat, col, bevel=0.0015))
    objs.append(C.box(name + "_gate", (0.03 * sc, 0.006, 0.05 * sc), (x, y - 0.004, z - 0.04 * sc), dark, col))
    objs.append(C.box(name + "_win", (0.014 * sc, 0.006, 0.022 * sc), (x, y - 0.004, z + 0.025 * sc), dark, col))
    objs.append(C.box(name + "_base", (0.13 * sc, 0.008, 0.02 * sc), (x, y, z - 0.07 * sc), mat, col, bevel=0.0015))
    return objs


def sun_emblem(name, loc, sc, mat, col):
    x, y, z = loc
    objs = [C.uvsphere(name + "_disc", 0.035 * sc, (x, y, z), mat=mat, col=col, scale=(1, 0.3, 1))]
    for k in range(12):
        a = 2 * math.pi * k / 12; ln = 0.06 if k % 2 == 0 else 0.045
        c = C.cyl(f"{name}_ray{k}", 0.009 * sc, ln * sc, (x + math.cos(a) * (0.035 + ln / 2) * sc, y, z + math.sin(a) * (0.035 + ln / 2) * sc),
                  segs=6, mat=mat, col=col, r2=0.001)
        c.rotation_euler = (0, -a + math.pi / 2, 0); c.scale = (1, 0.4, 1); objs.append(c)
    return objs


def void_sigil(name, loc, sc, mat, gl, col):
    x, y, z = loc
    objs = [C.torus(name + "_ring", 0.05 * sc, 0.007 * sc, (x, y, z), mat=mat, col=col, rot=(math.pi / 2, 0, 0))]
    objs.append(C.uvsphere(name + "_eye", 0.03 * sc, (x, y - 0.004, z), mat=gl, col=col, scale=(1.4, 0.3, 0.6)))
    objs.append(C.uvsphere(name + "_pupil", 0.012 * sc, (x, y - 0.012, z), mat=C.principled("KN_Pupil", (0.01, 0.0, 0.0), rough=0.3), col=col,
                           scale=(0.5, 0.3, 1.2)))
    for k in range(4):
        a = math.pi / 4 + k * math.pi / 2
        c = C.cyl(f"{name}_sp{k}", 0.012 * sc, 0.07 * sc, (x + math.cos(a) * 0.085 * sc, y, z + math.sin(a) * 0.085 * sc), segs=6, mat=mat, col=col, r2=0.0)
        c.rotation_euler = (0, -a + math.pi / 2, 0); objs.append(c)
    return objs


# ------------------------------------------------------------------ helms
def helm_great(ctx, col, P, T, R, dark, plume_a, plume_b):
    hi = KP.head_info(ctx); s = ctx["s"]; ez = hi["ez"]
    z0 = ez - 0.135 * s
    o, Rr, ry = KP.helm_shell("helm", hi, [(0.94, z0), (1.0, z0 + 0.05 * s), (1.03, ez), (1.0, ez + 0.07 * s), (0.88, ez + 0.125 * s),
                                           (0.6, ez + 0.165 * s), (0.08, ez + 0.18 * s)], P, col)
    fy = KP.front_y(hi, Rr, ry, 0.0)
    parts = []
    for sgn in (1, -1):
        parts.append(C.box(f"helm_slit{sgn}", (0.075 * s, 0.03, 0.016 * s), (sgn * 0.048 * s, fy + 0.006, ez + 0.004 * s), dark, col))
    parts.append(C.box("helm_cross_v", (0.024 * s, 0.014, 0.21 * s), (0, fy - 0.006, ez - 0.02 * s), T, col, bevel=0.003))
    parts.append(KP.H.ring_curve("helm_brow", 0, hi["cy"] + 0.01, Rr * 1.03 + 0.004, ry * 1.03 + 0.004, ez + 0.03 * s, 0.0075 * s, T, col))
    parts.append(KP.H.ring_curve("helm_rim", 0, hi["cy"] + 0.01, Rr * 0.95 + 0.004, ry * 0.95 + 0.004, z0 + 0.008, 0.007 * s, T, col))
    rv = []
    for k in range(18):
        a = 2 * math.pi * k / 18
        rv.append((Vector((Rr * 1.04 * math.cos(a), hi["cy"] + 0.01 + ry * 1.04 * math.sin(a), ez + 0.052 * s)), Vector((math.cos(a), math.sin(a), 0))))
    parts.append(KP.rivet_mesh("helm_rivets", rv, 0.0055, R, col))
    for i in range(3):
        for j in range(4):
            x = -(0.03 + 0.017 * j) * s; z = ez - (0.04 + 0.022 * i) * s
            c = C.cyl(f"helm_breath{i}{j}", 0.0042 * s, 0.03, (x, KP.front_y(hi, Rr, ry, x) - 0.002, z), segs=8, mat=dark, col=col)
            c.rotation_euler = (math.pi / 2, 0, 0); parts.append(c)
    top = ez + 0.18 * s
    parts.append(C.torus("helm_torse", 0.05 * s, 0.014 * s, (0, hi["cy"] + 0.01, top - 0.008), mat=plume_b, col=col, segs=24))
    rnd = random.Random(4)
    for k in range(13):
        u = (k - 6) / 6.0
        m = plume_a if k % 3 else plume_b
        pts = [Vector((u * 0.02 * s, hi["cy"], top)), Vector((u * 0.06 * s, hi["cy"] + 0.04 * s, top + 0.12 * s)),
               Vector((u * 0.09 * s, hi["cy"] + 0.17 * s, top + 0.14 * s + 0.02 * rnd.random())),
               Vector((u * 0.11 * s, hi["cy"] + 0.30 * s, top + 0.02 * s)), Vector((u * 0.12 * s, hi["cy"] + 0.36 * s, top - 0.12 * s))]
        parts.append(C.tube_curve(f"helm_plume{k}", pts, radius=0.022 * s, mat=m, col=col, radii=[0.6, 1.0, 1.0, 0.7, 0.15]))
    KP.headbone(*parts)


def helm_sallet(ctx, col, P, T, gl, dark, horn_m):
    hi = KP.head_info(ctx); s = ctx["s"]; ez = hi["ez"]
    z0 = ez - 0.06 * s
    o, Rr, ry = KP.helm_shell("helm", hi, [(1.08, z0 - 0.03 * s), (1.04, z0), (1.04, ez + 0.04 * s), (0.9, ez + 0.12 * s), (0.55, ez + 0.17 * s),
                                           (0.06, ez + 0.185 * s)], P, col)
    # tail: pull lower back verts backward/outward
    for v in o.data.vertices:
        if v.co.y > 0 and v.co.z < ez + 0.03 * s:
            k = (ez + 0.03 * s - v.co.z) / (0.12 * s)
            v.co.y += v.co.y * 0.9 * k; v.co.z -= 0.03 * s * k * (v.co.y / (ry + 1e-3))
    o.data.update()
    fy = KP.front_y(hi, Rr, ry, 0.0)
    parts = []
    bev = C.lathe("helm_bevor", [(Rr * 0.92, ez - 0.17 * s), (Rr * 1.02, ez - 0.10 * s), (Rr * 1.05, ez - 0.012 * s)], segs=40, mat=P, col=col)
    bev.scale = (1, ry / Rr, 1); bev.location = (0, hi["cy"] + 0.01 - 0.012, 0)
    bm = bmesh.new(); bm.from_mesh(bev.data)
    bmesh.ops.delete(bm, geom=[v for v in bm.verts if v.co.y > 0.25 * Rr], context="VERTS"); bm.to_mesh(bev.data); bm.free()
    bev.modifiers.new("Sol", "SOLIDIFY").thickness = 0.006; C.add_mod_subsurf(bev, 1)
    parts.append(bev)
    parts.append(C.box("helm_slit", (0.15 * s, 0.03, 0.012 * s), (0, fy + 0.004, ez + 0.003 * s), gl, col))
    parts.append(C.box("helm_ridge", (0.012 * s, 0.03, 0.10 * s), (0, fy - 0.012, ez - 0.07 * s), T, col, bevel=0.003))
    for sgn in (1, -1):
        pts = [Vector((sgn * 0.08 * s, hi["cy"] - 0.02 * s, ez + 0.09 * s)), Vector((sgn * 0.15 * s, hi["cy"] + 0.02 * s, ez + 0.16 * s)),
               Vector((sgn * 0.17 * s, hi["cy"] + 0.14 * s, ez + 0.22 * s)), Vector((sgn * 0.14 * s, hi["cy"] + 0.27 * s, ez + 0.25 * s))]
        parts.append(C.tube_curve(f"helm_horn{sgn}", pts, radius=0.026 * s, mat=horn_m, col=col, radii=[1.0, 0.85, 0.5, 0.06]))
    for k in range(5):
        t = k / 4
        c = C.cyl(f"helm_fin{k}", 0.012 * s, (0.07 - 0.02 * abs(t - 0.4)) * s, (0, hi["cy"] - 0.05 * s + 0.15 * s * t, ez + 0.18 * s + 0.02 * s - 0.03 * s * t * t),
                  segs=6, mat=T, col=col, r2=0.0005)
        c.rotation_euler = (math.radians(-25 + 40 * t), 0, 0); parts.append(c)
    KP.headbone(*parts)
    return hi


def helm_captain(ctx, col, P, T, R, gl, dark, crest_m):
    hi = KP.head_info(ctx); s = ctx["s"]; ez = hi["ez"]
    z0 = ez - 0.14 * s
    o, Rr, ry = KP.helm_shell("helm", hi, [(0.95, z0), (1.02, z0 + 0.05 * s), (1.04, ez), (0.98, ez + 0.08 * s), (0.7, ez + 0.15 * s),
                                           (0.2, ez + 0.19 * s), (0.02, ez + 0.2 * s)], P, col)
    fy = KP.front_y(hi, Rr, ry, 0.0)
    parts = []
    sn = C.lathe("helm_snout", [(0.001, 0), (0.085 * s, 0.01 * s), (0.092 * s, 0.05 * s), (0.06 * s, 0.10 * s), (0.001, 0.15 * s)], segs=16, mat=P, col=col,
                 close_bottom=True)
    sn.location = (0, fy + 0.03, ez - 0.035 * s); sn.rotation_euler = (math.radians(95), 0, 0); sn.scale = (1.05, 0.62, 1.15)
    sn.modifiers.new("Sol", "SOLIDIFY").thickness = 0.005; C.add_mod_subsurf(sn, 1); parts.append(sn)
    for sgn in (1, -1):
        b = C.box(f"helm_eye{sgn}", (0.055 * s, 0.03, 0.013 * s), (sgn * 0.045 * s, fy - 0.006, ez + 0.006 * s), gl, col)
        b.rotation_euler = (0, sgn * math.radians(-10), 0); parts.append(b)
    parts.append(C.box("helm_ridge", (0.014 * s, 0.03, 0.17 * s), (0, fy - 0.05 * s, ez - 0.045 * s), T, col, bevel=0.003))
    for i in range(4):
        for sgn in (1, -1):
            c = C.cyl(f"helm_br{i}{sgn}", 0.004 * s, 0.03, (sgn * 0.022 * s, fy - 0.075 * s + 0.012 * s * i, ez - 0.065 * s - 0.016 * s * i), segs=8, mat=dark, col=col)
            c.rotation_euler = (math.radians(70), 0, 0); parts.append(c)
    parts.append(KP.H.ring_curve("helm_band", 0, hi["cy"] + 0.01, Rr * 1.0 + 0.006, ry * 1.0 + 0.006, ez + 0.06 * s, 0.009 * s, T, col))
    for k in range(10):
        a = 2 * math.pi * k / 10 - math.pi / 2
        x = (Rr + 0.006) * math.cos(a); y = hi["cy"] + 0.01 + (ry + 0.006) * math.sin(a)
        c = C.cyl(f"helm_spike{k}", 0.012 * s, 0.07 * s, (x * 0.98, y, ez + 0.09 * s), segs=6, mat=T, col=col, r2=0.0)
        c.rotation_euler = (math.sin(a) * math.radians(-18), math.cos(a) * math.radians(18), 0); parts.append(c)
    # transverse crest
    top = ez + 0.19 * s
    parts.append(C.box("helm_crestbase", (0.30 * s, 0.03 * s, 0.03 * s), (0, hi["cy"], top - 0.005), T, col, bevel=0.006))
    for k in range(31):
        a = math.pi * k / 30
        pts = [Vector((math.cos(a) * 0.12 * s, hi["cy"], top + 0.01 * s)), Vector((math.cos(a) * 0.19 * s, hi["cy"] + 0.01 * s, top + math.sin(a) * 0.17 * s + 0.03 * s)),
               Vector((math.cos(a) * 0.24 * s, hi["cy"] + 0.04 * s, top + math.sin(a) * 0.20 * s))]
        parts.append(C.tube_curve(f"helm_crest{k}", pts, radius=0.016 * s, mat=crest_m, col=col, radii=[0.8, 1.0, 0.2]))
    KP.headbone(*parts)


def helm_bascinet_open(ctx, col, P, T, mail):
    hi = KP.head_info(ctx); s = ctx["s"]; ez = hi["ez"]
    o, Rr, ry = KP.helm_shell("helm", hi, [(1.02, ez + 0.035 * s), (1.0, ez + 0.08 * s), (0.82, ez + 0.14 * s), (0.45, ez + 0.2 * s),
                                           (0.04, ez + 0.245 * s)], P, col)
    for v in o.data.vertices:
        if v.co.z > ez + 0.17 * s:
            v.co.y += (v.co.z - ez - 0.17 * s) * 0.6
    o.data.update()
    # side cheek-plates down to the jaw, open front
    av = C.lathe("helm_aventail", [(Rr * 0.99, ez + 0.04 * s), (Rr * 0.97, ez - 0.06 * s), (Rr * 0.86, ez - 0.13 * s), (Rr * 1.12, ez - 0.19 * s),
                                    (Rr * 1.6, ez - 0.25 * s)], segs=48, mat=mail, col=col)
    av.scale = (1, ry / Rr, 1); av.location = (0, hi["cy"] + 0.012, 0)
    bm = bmesh.new(); bm.from_mesh(av.data)
    bmesh.ops.delete(bm, geom=[f for f in bm.faces if all(v.co.y < -0.28 * Rr and v.co.z > ez - 0.15 * s for v in f.verts)], context="FACES")
    bm.to_mesh(av.data); bm.free()
    av.modifiers.new("Sol", "SOLIDIFY").thickness = 0.008; C.add_mod_subsurf(av, 1)
    WMODE[av.name] = "vert"
    parts = []
    parts.append(KP.H.ring_curve("helm_rim", 0, hi["cy"] + 0.01, Rr * 1.03, ry * 1.03, ez + 0.035 * s, 0.0085 * s, T, col))
    nas = C.box("helm_nasal", (0.018 * s, 0.012, 0.08 * s), (0, KP.front_y(hi, Rr, ry, 0) - 0.01, ez - 0.005 * s), P, col, bevel=0.003)
    parts.append(nas)
    KP.headbone(*parts)


def crown(ctx, col, name, z, rx, ry, cy, gold, gem, broken=(), s=1.0):
    H.ring_curve(name + "_band", 0, cy, rx, ry, z, 0.013 * s, gold, col, tilt=-0.01)
    objs = []
    for k in range(8):
        a = 2 * math.pi * k / 8
        px = rx * math.cos(a); py = cy + ry * math.sin(a)
        hgt = (0.075 if k % 2 == 0 else 0.05) * s * (0.45 if k in broken else 1.0)
        objs.append(C.cyl(f"{name}_fl{k}", 0.012 * s, hgt, (px, py, z + hgt / 2), segs=8, mat=gold, col=col, r2=0.003))
        if k % 2 == 0 and k not in broken:
            objs.append(C.ico(f"{name}_gem{k}", 0.012 * s, (px, py, z + hgt + 0.008 * s), sub=2, mat=gem, col=col))
    KP.headbone(*objs)
    WMODE[name + "_band"] = ("bone", "head")


def helm_aldric(ctx, col, P, T, gem):
    hi = KP.head_info(ctx); s = ctx["s"]; ez = hi["ez"]
    cap = C.uvsphere("helm_cap", hi["rx"] + 0.03, (0, hi["cy"] + 0.012, ez + 0.06 * s), mat=P, col=col, scale=(1.0, (hi["ry"] + 0.03) / (hi["rx"] + 0.03), 0.92))
    bm = bmesh.new(); bm.from_mesh(cap.data)
    bmesh.ops.delete(bm, geom=[v for v in bm.verts if v.co.y < -0.02 and v.co.z < 0.03], context="VERTS")
    bmesh.ops.delete(bm, geom=[v for v in bm.verts if v.co.z < -0.075], context="VERTS")
    bm.to_mesh(cap.data); bm.free()
    cap.modifiers.new("Sol", "SOLIDIFY").thickness = 0.006; C.add_mod_subsurf(cap, 1)
    parts = [cap]
    R = hi["rx"] + 0.03; ry = hi["ry"] + 0.03
    parts.append(KP.H.ring_curve("helm_brow", 0, hi["cy"] + 0.012, R * 1.02, ry * 1.02, ez + 0.06 * s, 0.009 * s, T, col, tilt=-0.02))
    for sgn in (1, -1):
        parts.append(C.box(f"helm_cheek{sgn}", (0.035 * s, 0.07 * s, 0.10 * s), (sgn * 0.095 * s, hi["cy"] - 0.02 * s, ez - 0.035 * s), P, col, bevel=0.01))
        parts.append(H.leaf_shape(f"helm_wing{sgn}", 0.12 * s, 0.05 * s, T, col, curl=0.2))
        parts[-1].location = (sgn * 0.11 * s, hi["cy"] + 0.02 * s, ez + 0.08 * s)
        parts[-1].rotation_euler = (math.radians(-30), sgn * math.radians(60), math.radians(90 if sgn > 0 else -90))
    KP.headbone(*parts)
    crown(ctx, col, "crown", ez + 0.105 * s, R * 0.95, ry * 0.95, hi["cy"] + 0.012, T, gem, broken=(2, 5), s=s)


def helm_magma(ctx, col, P, T, gl, dark, horn_m):
    hi = KP.head_info(ctx); s = ctx["s"]; ez = hi["ez"]
    z0 = ez - 0.13 * s
    o, Rr, ry = KP.helm_shell("helm", hi, [(0.98, z0), (1.04, z0 + 0.05 * s), (1.06, ez), (1.0, ez + 0.08 * s), (0.72, ez + 0.15 * s),
                                           (0.2, ez + 0.185 * s), (0.02, ez + 0.19 * s)], P, col)
    fy = KP.front_y(hi, Rr, ry, 0.0)
    parts = []
    parts.append(C.box("helm_t_h", (0.16 * s, 0.03, 0.016 * s), (0, fy + 0.005, ez + 0.004 * s), gl, col))
    parts.append(C.box("helm_t_v", (0.02 * s, 0.03, 0.09 * s), (0, fy + 0.005, ez - 0.045 * s), gl, col))
    parts.append(C.box("helm_brow", (0.20 * s, 0.03 * s, 0.022 * s), (0, fy - 0.004, ez + 0.03 * s), T, col, bevel=0.006))
    for sgn in (1, -1):
        pts = []
        for k in range(9):
            t = k / 8; a = t * math.pi * 1.35
            r = 0.07 * s * (1 - 0.45 * t)
            pts.append(Vector((sgn * (0.10 * s + 0.05 * s * t + r * 0.3), hi["cy"] + 0.02 * s + r * math.sin(a) + 0.03 * s * t,
                               ez + 0.07 * s - r * math.cos(a) + 0.05 * s)))
        pts[0] = Vector((sgn * 0.09 * s, hi["cy"], ez + 0.10 * s))
        parts.append(C.tube_curve(f"helm_ram{sgn}", pts, radius=0.034 * s, mat=horn_m, col=col, radii=[1.0, 0.95, 0.85, 0.75, 0.62, 0.5, 0.38, 0.26, 0.1]))
    rnd = random.Random(8)
    for k in range(6):
        t = k / 5
        c = C.cyl(f"helm_shard{k}", 0.016 * s, (0.06 + 0.04 * rnd.random()) * s, (0, hi["cy"] - 0.06 * s + 0.16 * s * t, ez + 0.19 * s - 0.04 * s * (t - 0.4) ** 2),
                  segs=5, mat=horn_m, col=col, r2=0.0)
        c.rotation_euler = (math.radians(-30 + 55 * t), math.radians(rnd.uniform(-8, 8)), 0); parts.append(c)
    KP.headbone(*parts)


def braid(ctx, col, name, mat, start_z_off=-0.02, length=0.38, tie=None):
    hi = KP.head_info(ctx); s = ctx["s"]; ez = hi["ez"]
    y0 = hi["cy"] + hi["ry"] + 0.035
    pts = [Vector((0, y0 - 0.01, ez + start_z_off * s)), Vector((0, y0 + 0.03 * s, ez - 0.10 * s)), Vector((0.01, y0 + 0.06 * s, ez - 0.25 * s)),
           Vector((0.015, y0 + 0.06 * s, ez - (0.12 + length) * s))]
    parts = []
    from kn_parts import _smooth
    for k in range(16):
        t = k / 15
        seg = len(pts) - 1; i = min(seg - 1, int(t * seg)); f = t * seg - i
        p = pts[i].lerp(pts[i + 1], f)
        r = (0.03 - 0.016 * t) * s
        e = C.uvsphere(f"{name}{k}", r, p + Vector(((-1) ** k * 0.008 * s, 0, 0)), segs=12, rings=8, mat=mat, col=col, scale=(1.0, 0.8, 1.35))
        e.rotation_euler = (0, (-1) ** k * 0.35, 0); parts.append(e)
    if tie:
        parts.append(C.torus(name + "_tie", 0.014 * s, 0.005 * s, pts[-1] + Vector((0, 0, 0.02 * s)), mat=tie, col=col, segs=16))
    for p in parts:
        WMODE[p.name] = "single"


# ------------------------------------------------------------------ designs
def design_knight(col):
    ctx = base(col, "male", skin=(0.76, 0.56, 0.44), iris=(0.3, 0.42, 0.62))
    s = ctx["s"]
    steel = KP.armor_mat("KN_Steel", base=(0.60, 0.62, 0.66), dark=(0.30, 0.31, 0.34), hi=(0.84, 0.86, 0.90), rough=0.22, wear=0.7)
    trim = KP.armor_mat("KN_SteelTrim", base=(0.80, 0.82, 0.86), dark=(0.55, 0.56, 0.6), hi=(0.95, 0.96, 0.98), rough=0.16, wear=0.3)
    brass = C.gold_mat("KN_Brass", (0.95, 0.72, 0.38))
    M = dict(plate=steel, trim=trim, rivet=brass, leather=KP.leather_mat("KN_Leather", (0.17, 0.09, 0.045)), mail=KP.mail_mat("KN_Mail"))
    suit(ctx, col, M, {})
    blue = KP.cloth_mat("KN_StoneBlue", (0.07, 0.15, 0.42), (0.04, 0.08, 0.24), sheen=0.6)
    white = KP.cloth_mat("KN_StoneWhite", (0.78, 0.80, 0.84), (0.62, 0.64, 0.68), sheen=0.5)
    at = ctx["J"]["arm_t"]
    KP.split_skirt(ctx, "tabard_skirt", blue, col, 1.02 * s, 0.52 * s, flare=0.05, gap_deg=8, trim=white, folds=9)
    cf = ctx["chest_front"]
    enamel = C.principled("KN_Enamel", (0.05, 0.12, 0.42), rough=0.18, coat=1.0)
    plq = KP.heater_shield("plaque", col, W=0.15 * s, Hh=0.19 * s, curv=0.012, field=enamel, rim=trim, rivet=brass, thick=0.006)
    plq += tower_emblem("tab_tower", (0, -0.016, 0.006), 0.8 * s, trim, C.principled("KN_Dark", (0.02, 0.02, 0.03), rough=0.6), col)
    KP.place(plq, Matrix.Translation((cf.x, cf.y - 0.026, 1.15 * s)) @ Matrix.Rotation(math.radians(-4), 4, "X"))
    bpy.context.view_layer.update()
    for o in plq:
        WMODE[o.name] = "single"
    KP.cape(ctx, "cape", KP.cloth_mat("KN_CapeBlue", (0.06, 0.12, 0.36), (0.03, 0.06, 0.18), sheen=0.7), col, 1.36 * s, 0.22 * s, length_y=0.2,
            folds=9, trim=white, width=0.95)
    for sgn in (1, -1):
        C.torus(f"cape_clasp{sgn}", 0.026 * s, 0.007 * s, (sgn * 0.12 * s, -0.04 * s, 1.40 * s), mat=brass, col=col, rot=(math.pi / 2, 0, 0))
    dark = C.principled("KN_Slit", (0.005, 0.005, 0.008), rough=0.9)
    helm_great(ctx, col, steel, trim, brass, dark, KP.cloth_mat("KN_PlumeBlue", (0.10, 0.22, 0.6), (0.06, 0.12, 0.4), sheen=1.0), white)
    wpn = dict(kind="sword", L=0.88, w0=0.032, blade=KP.armor_mat("KN_Blade", base=(0.80, 0.82, 0.86), dark=(0.5, 0.52, 0.56), hi=(0.97, 0.98, 1.0), rough=0.14, wear=0.15, coat=0.6, scale=4.0), guard=brass,
               grip=KP.leather_mat("KN_GripBlue", (0.05, 0.08, 0.2)), pommel=brass, profile="long", guard_style="bar")
    shd = dict(kind="heater", field=blue, rim=trim, rivet=brass, emblem="tower", emblem_mat=trim)
    return ctx, wpn, shd, dict(lights=[])


def design_shadow(col):
    ctx = base(col, "female", skin=(0.70, 0.62, 0.66), iris=(0.6, 0.3, 0.9), scale=1.07)
    s = ctx["s"]
    VIO = (0.62, 0.22, 1.0)
    plate = KP.armor_mat("KN_Void", base=(0.035, 0.03, 0.045), dark=(0.01, 0.008, 0.014), hi=(0.16, 0.11, 0.24), rough=0.2, wear=0.9, coat=0.6)
    trim = KP.armor_mat("KN_VoidTrim", base=(0.30, 0.16, 0.48), dark=(0.12, 0.06, 0.2), hi=(0.55, 0.36, 0.8), rough=0.2, wear=0.4)
    gl = KP.glow("KN_VoidGlow", VIO, 9.0)
    M = dict(plate=plate, trim=trim, rivet=gl, leather=KP.leather_mat("KN_VLeather", (0.05, 0.03, 0.06)), mail=KP.mail_mat("KN_VMail", (0.12, 0.1, 0.16)))
    suit(ctx, col, M, {"paul_off": 0.055})
    # jagged pauldron points
    J = ctx["J"]
    for sd, sx in (("L", 1), ("R", -1)):
        S = J[f"shoulder_{sd}"]
        for k in range(4):
            a = math.radians(-20 + 22 * k)
            c = C.cyl(f"paul_tooth{sd}{k}", 0.022 * s, 0.11 * s, S + Vector((sx * (0.09 + 0.01 * k) * s, (-0.06 + 0.045 * k) * s, (0.02 - 0.005 * k) * s)),
                      segs=4, mat=plate, col=col, r2=0.0)
            c.rotation_euler = (math.radians(-10 + 10 * k), sx * math.radians(115), 0); WMODE[c.name] = "single"
        for k in range(3):
            c = C.cyl(f"paul_spine{sd}{k}", 0.016 * s, 0.09 * s, S + Vector((sx * (0.03 + 0.03 * k) * s, (0.0 - 0.01 * k) * s, (0.13 - 0.01 * k) * s)),
                      segs=5, mat=trim, col=col, r2=0.0)
            c.rotation_euler = (0, sx * math.radians(20 + 12 * k), 0); WMODE[c.name] = "single"
    cf = ctx["chest_front"]
    for o in void_sigil("chest_sigil", (cf.x, cf.y - 0.01 * s, cf.z + 0.03 * s), 0.85 * s, trim, gl, col):
        WMODE[o.name] = "single"
    KP.cape(ctx, "cape", KP.cloth_mat("KN_VoidCape", (0.08, 0.03, 0.12), (0.02, 0.01, 0.03), sheen=0.8), col, 1.36 * s, 0.12 * s, length_y=0.24,
            folds=11, tatter=0.45, holes=0.05, seed=7, trim=None)
    KP.split_skirt(ctx, "skirt", KP.cloth_mat("KN_VoidSkirt", (0.06, 0.02, 0.09), (0.02, 0.005, 0.03), sheen=0.8), col, 0.98 * s, 0.40 * s,
                   flare=0.07, tatter=0.5, seed=4)
    dark = C.principled("KN_Slit", (0.005, 0.005, 0.008), rough=0.9)
    helm_sallet(ctx, col, plate, trim, gl, dark, plate)
    braid(ctx, col, "braid", H.hair_mat("KN_HairSilver", (0.62, 0.6, 0.68), (0.92, 0.9, 0.96)), tie=trim)
    wpn = dict(kind="sword", L=1.0, w0=0.036, blade=KP.armor_mat("KN_VoidBlade", base=(0.05, 0.04, 0.07), dark=(0.01, 0.01, 0.02), hi=(0.25, 0.18, 0.35),
                                                                    rough=0.15, wear=1.0), rune=gl, guard=trim, grip=M["leather"], pommel=gl,
               profile="jagged", guard_style="wing", guard_w=0.2)
    return ctx, wpn, None, dict(offhand="void", glow=VIO)


def design_vorn(col):
    ctx = base(col, "male", skin=(0.6, 0.45, 0.38), iris=(0.8, 0.2, 0.1), arm_angle=11.0)
    s = ctx["s"]
    RED = (1.0, 0.28, 0.12)
    plate = KP.armor_mat("KN_Vorn", base=(0.20, 0.035, 0.03), dark=(0.04, 0.01, 0.01), hi=(0.48, 0.10, 0.07), rough=0.24, wear=0.75, coat=0.55)
    black = KP.armor_mat("KN_VornBlack", base=(0.05, 0.045, 0.05), dark=(0.015, 0.012, 0.015), hi=(0.2, 0.17, 0.18), rough=0.22, wear=0.8, coat=0.5)
    gold = KP.armor_mat("KN_VornGold", base=(0.55, 0.36, 0.12), dark=(0.25, 0.14, 0.04), hi=(0.85, 0.62, 0.28), rough=0.2, wear=0.5)
    gl = KP.glow("KN_VornGlow", RED, 10.0)
    M = dict(plate=plate, trim=gold, rivet=gold, leather=KP.leather_mat("KN_VLeath", (0.08, 0.03, 0.02)), mail=KP.mail_mat("KN_VornMail", (0.14, 0.12, 0.12)),
             paul=black, gaunt=black)
    suit(ctx, col, M, {"paul_off": 0.062, "edge_r": 0.0065})
    J = ctx["J"]
    for sd, sx in (("L", 1), ("R", -1)):
        S = J[f"shoulder_{sd}"]
        for k in range(3):
            c = C.cyl(f"paul_spike{sd}{k}", 0.028 * s, 0.16 * s, S + Vector((sx * (0.035 + 0.04 * k) * s, (-0.02 + 0.03 * k) * s, (0.15 - 0.02 * k) * s)),
                      segs=8, mat=black, col=col, r2=0.0)
            c.rotation_euler = (math.radians(5), sx * math.radians(18 + 16 * k), 0); WMODE[c.name] = "single"
            C.torus(f"paul_spr{sd}{k}", 0.026 * s, 0.006 * s, S + Vector((sx * (0.035 + 0.04 * k) * s, (-0.02 + 0.03 * k) * s, (0.085 - 0.02 * k) * s)),
                    mat=gold, col=col, segs=16)
        haute = C.box(f"paul_haute{sd}", (0.012 * s, 0.17 * s, 0.10 * s), S + Vector((-sx * 0.035 * s, 0.0, 0.16 * s)), black, col, bevel=0.01,
                      rot=(0, sx * math.radians(-12), 0))
        WMODE[haute.name] = "single"
    cf = ctx["chest_front"]
    for o in void_sigil("chest_sigil", (cf.x, cf.y - 0.012 * s, cf.z + 0.03 * s), 0.95 * s, gold, gl, col):
        WMODE[o.name] = "single"
    KP.cape(ctx, "cape", KP.cloth_mat("KN_VornCape", (0.42, 0.04, 0.04), (0.14, 0.01, 0.015), sheen=0.9), col, 1.37 * s, 0.07 * s, length_y=0.28,
            folds=12, tatter=0.18, seed=3, trim=gold, width=1.05)
    KP.split_skirt(ctx, "skirt", KP.cloth_mat("KN_VornSkirt", (0.06, 0.02, 0.02), (0.02, 0.005, 0.005), sheen=0.7), col, 0.98 * s, 0.44 * s, flare=0.06,
                   trim=gold, folds=11)
    dark = C.principled("KN_Slit", (0.005, 0.005, 0.008), rough=0.9)
    helm_captain(ctx, col, black, gold, gold, gl, dark, KP.cloth_mat("KN_CrestRed", (0.75, 0.06, 0.04), (0.45, 0.02, 0.02), sheen=1.0))
    wpn = dict(kind="sword", L=1.02, w0=0.045, th=0.009, blade=KP.armor_mat("KN_VornBlade", base=(0.12, 0.1, 0.1), dark=(0.03, 0.02, 0.02), hi=(0.6, 0.55, 0.55),
                                                                              rough=0.15, wear=1.0), rune=gl, guard=gold, grip=M["leather"], pommel=gold,
               profile="falchion", guard_style="spike", guard_w=0.2)
    shd = dict(kind="tower", field=black, rim=gold, rivet=gold, emblem="void", emblem_mat=gold, glow=gl)
    return ctx, wpn, shd, dict(glow=RED)


def design_barrow(col):
    ctx = base(col, "male", skin=(0.40, 0.44, 0.36), iris=(0.4, 1.0, 0.5), age=2.2, eye_glow=(0.35, 1.0, 0.45))
    s = ctx["s"]
    GRN = (0.35, 1.0, 0.45)
    plate = KP.armor_mat("KN_Barrow", base=(0.26, 0.26, 0.25), dark=(0.09, 0.09, 0.09), hi=(0.46, 0.46, 0.45), rough=0.42, wear=0.6, rust=0.45, moss=0.55)
    trim = KP.armor_mat("KN_BarrowBronze", base=(0.40, 0.30, 0.16), dark=(0.2, 0.14, 0.07), hi=(0.6, 0.48, 0.28), rough=0.4, wear=0.4, rust=0.5,
                        verdigris=True)
    M = dict(plate=plate, trim=trim, rivet=trim, leather=KP.leather_mat("KN_RotLeather", (0.10, 0.08, 0.05)), mail=KP.mail_mat("KN_BMail", (0.24, 0.24, 0.23), rust=0.3))
    suit(ctx, col, M, {"tassets": False})
    shroud = KP.cloth_mat("KN_Shroud", (0.30, 0.31, 0.26), (0.12, 0.13, 0.10), sheen=0.3, rough=0.85)
    KP.cape(ctx, "cape", shroud, col, 1.37 * s, 0.10 * s, length_y=0.22, folds=10, tatter=0.6, holes=0.09, seed=11)
    KP.split_skirt(ctx, "skirt", shroud, col, 1.0 * s, 0.38 * s, flare=0.06, tatter=0.65, seed=9, folds=13)
    helm_bascinet_open(ctx, col, plate, trim, M["mail"])
    # lank grey hair under the helm
    hm = H.hair_mat("KN_DeadHair", (0.32, 0.32, 0.3), (0.55, 0.55, 0.52))
    hi = KP.head_info(ctx); ez = hi["ez"]; rnd = random.Random(3)
    for k in range(10):
        a = math.radians(-60 + 120 * k / 9)
        x = math.sin(a) * (hi["rx"] + 0.012); y = hi["cy"] + math.cos(a) * (hi["ry"] + 0.01)
        c = C.tube_curve(f"deadhair{k}", [Vector((x, y, ez + 0.03 * s)), Vector((x * 1.08, y + 0.01, ez - 0.06 * s)), Vector((x * 1.1, y + 0.02, ez - (0.14 + 0.05 * rnd.random()) * s))],
                         radius=0.006 * s, mat=hm, col=col, radii=[1, 0.8, 0.1])
        WMODE[c.name] = ("bone", "head")
    gl = KP.glow("KN_GraveGlow", GRN, 6.0)
    wpn = dict(kind="sword", L=0.82, w0=0.032, blade=KP.armor_mat("KN_RustBlade", base=(0.4, 0.38, 0.35), dark=(0.15, 0.13, 0.12), hi=(0.62, 0.6, 0.58),
                                                                     rough=0.35, rust=0.55), guard=trim, grip=M["leather"], pommel=trim, profile="notched",
               guard_style="bar", guard_w=0.12)
    shd = dict(kind="round", wood=C.wood_mat("KN_RotWood", (0.14, 0.11, 0.07), (0.26, 0.21, 0.13)), rim=plate, rivet=trim, boss=plate)
    return ctx, wpn, shd, dict(glow=GRN)


def design_aldric(col):
    ctx = base(col, "male", skin=(0.55, 0.60, 0.66), iris=(1.0, 0.5, 0.2), age=1.6, eye_glow=(1.0, 0.48, 0.15), eye_k=2.2)
    s = ctx["s"]
    ORG = (1.0, 0.45, 0.15)
    plate = KP.armor_mat("KN_Aldric", base=(0.56, 0.55, 0.52), dark=(0.24, 0.23, 0.22), hi=(0.82, 0.8, 0.76), rough=0.3, wear=0.6, rust=0.18, moss=0.15)
    gild = KP.armor_mat("KN_AldGild", base=(0.66, 0.50, 0.22), dark=(0.32, 0.22, 0.08), hi=(0.9, 0.74, 0.4), rough=0.22, wear=0.5, rust=0.15, verdigris=True)
    M = dict(plate=plate, trim=gild, rivet=gild, leather=KP.leather_mat("KN_ALeather", (0.12, 0.07, 0.04)), mail=KP.mail_mat("KN_AMail", (0.4, 0.4, 0.4), rust=0.3))
    suit(ctx, col, M, {"paul_off": 0.056})
    cf = ctx["chest_front"]
    for o in sun_emblem("chest_sun", (cf.x, cf.y - 0.012 * s, cf.z + 0.02 * s), 1.2 * s, gild, col):
        WMODE[o.name] = "single"
    teal = KP.cloth_mat("KN_AldTeal", (0.08, 0.22, 0.27), (0.03, 0.08, 0.10), sheen=0.7, rough=0.7)
    KP.split_skirt(ctx, "surcoat", teal, col, 1.0 * s, 0.30 * s, flare=0.08, tatter=0.35, seed=6, trim=gild, folds=12)
    KP.cape(ctx, "cape", KP.cloth_mat("KN_AldCape", (0.10, 0.2, 0.26), (0.03, 0.05, 0.07), sheen=0.8), col, 1.37 * s, 0.06 * s, length_y=0.26,
            folds=12, tatter=0.35, holes=0.04, seed=5, trim=gild, width=1.05)
    helm_aldric(ctx, col, plate, gild, KP.glow("KN_AldGem", ORG, 5.0))
    hm = H.hair_mat("KN_GhostBeard", (0.72, 0.76, 0.8), (0.95, 0.97, 1.0))
    tree = H.bvh(ctx["body"])
    before = set(o.name for o in col.objects)
    H.beard("beard", tree, hm, col, ctx["face"], s, n=14, length=0.16, width=0.042, bushy=0.0, seed=6)
    H.brows("brow", ctx["eyes"], tree, hm, col, ctx["h"], thick=0.0045, lift=0.026, arch=0.002, w=0.032)
    for o in col.objects:
        if o.name not in before:
            WMODE[o.name] = ("bone", "head")
    wpn = dict(kind="sword", L=0.95, w0=0.033, blade=KP.ghost_mat("KN_SpectralBlade", (1.0, 0.40, 0.10), 2.2, 0.6), rune=KP.glow("KN_AldRune", ORG, 8.0),
               guard=gild, grip=M["leather"], pommel=gild, profile="long", guard_style="wing", guard_w=0.18, core=C.principled("KN_AldCore", (0.55, 0.55, 0.55), rough=0.2, metal=1.0))
    shd = dict(kind="heater", field=teal, rim=gild, rivet=gild, emblem="sun", emblem_mat=gild, battered=1.0)
    return ctx, wpn, shd, dict(glow=ORG)


def design_magma(col):
    ctx = base(col, "female", skin=(0.62, 0.42, 0.32), iris=(1.0, 0.5, 0.1), scale=1.08, eye_glow=(1.0, 0.45, 0.08))
    s = ctx["s"]
    LAVA = (1.0, 0.32, 0.04)
    obs = KP.armor_mat("KN_Obsidian", base=(0.085, 0.072, 0.07), dark=(0.02, 0.016, 0.015), hi=(0.40, 0.32, 0.28), rough=0.16, wear=0.55, coat=0.8,
                       lava=LAVA, lava_k=4.5, scale=4.5)
    obs2 = KP.armor_mat("KN_Obsidian2", base=(0.09, 0.078, 0.075), dark=(0.02, 0.016, 0.015), hi=(0.42, 0.34, 0.3), rough=0.15, wear=0.55, coat=0.8)
    iron = KP.armor_mat("KN_CharIron", base=(0.36, 0.22, 0.12), dark=(0.12, 0.07, 0.04), hi=(0.78, 0.5, 0.28), rough=0.3, wear=0.5)
    gl = KP.glow("KN_LavaGlow", LAVA, 12.0)
    M = dict(plate=obs, trim=iron, rivet=gl, leather=KP.leather_mat("KN_CharLeather", (0.06, 0.035, 0.025)), mail=KP.mail_mat("KN_MMail", (0.12, 0.09, 0.08)),
             paul=obs, gaunt=obs)
    suit(ctx, col, M, {"paul_off": 0.058})
    J = ctx["J"]; rnd = random.Random(12)
    for sd, sx in (("L", 1), ("R", -1)):
        S = J[f"shoulder_{sd}"]
        for k in range(4):
            c = C.cyl(f"paul_shard{sd}{k}", (0.022 + 0.008 * rnd.random()) * s, (0.10 + 0.07 * rnd.random()) * s,
                      S + Vector((sx * (0.03 + 0.035 * k) * s, (-0.03 + 0.025 * k) * s, (0.14 - 0.015 * k) * s)), segs=5, mat=obs2, col=col, r2=0.0)
            c.rotation_euler = (math.radians(rnd.uniform(-12, 12)), sx * math.radians(12 + 15 * k), 0); WMODE[c.name] = "single"
    char = KP.cloth_mat("KN_Char", (0.24, 0.07, 0.04), (0.07, 0.02, 0.012), sheen=0.3, rough=0.9)
    sk = KP.split_skirt(ctx, "skirt", char, col, 0.98 * s, 0.42 * s, flare=0.07, tatter=0.55, seed=13, trim=KP.glow("KN_Ember", (1.0, 0.36, 0.05), 6.0), folds=12)
    dark = C.principled("KN_Slit", (0.005, 0.005, 0.008), rough=0.9)
    helm_magma(ctx, col, obs, iron, gl, dark, obs2)
    braid(ctx, col, "braid", H.hair_mat("KN_HairFire", (0.45, 0.06, 0.02), (1.0, 0.45, 0.12)), length=0.42, tie=iron)
    wpn = dict(kind="sword", L=1.05, w0=0.05, th=0.011, blade=KP.armor_mat("KN_MagmaBlade", base=(0.05, 0.04, 0.04), dark=(0.01, 0.01, 0.01), hi=(0.22, 0.2, 0.2),
                                                                               rough=0.12, coat=0.9, lava=LAVA, lava_k=20.0, scale=14.0),
               rune=gl, guard=obs2, grip=M["leather"], pommel=gl, profile="broad", guard_style="spike", guard_w=0.2)
    return ctx, wpn, None, dict(offhand="lava", glow=LAVA)


BUILD = {"knight": design_knight, "shadow_knight": design_shadow, "knight_captain_vorn": design_vorn,
         "barrow_knight": design_barrow, "sir_aldric": design_aldric, "magma_knight": design_magma}


# ------------------------------------------------------------------ poses
IMP_HAND = [tuple(float(x) for x in C.arg("--imp3", "105,0,0").split(",")), tuple(float(x) for x in C.arg("--imp4", "95,0,0").split(","))]
DTH_ARM = [tuple(float(x) for x in C.arg("--dth3", "-10,40,0").split(",")), tuple(float(x) for x in C.arg("--dth4", "-5,50,0").split(","))]
def pose(state, k, n, shield):
    p = {}
    if state == "idle":
        b = math.sin(2 * math.pi * k / n)
        p["chest"] = (1.5 * b, 0, 0); p["neck"] = (-0.8 * b, 0, 0)
        p["upper_arm_R"] = (-16 + 1.5 * b, 9, 0); p["forearm_R"] = (-52 - 2 * b, 0, 0); p["hand_R"] = (8, 0, 0)
        if shield:
            p["upper_arm_L"] = (-12, -11, 0); p["forearm_L"] = (-68 + 1.5 * b, 0, 14)
        else:
            p["upper_arm_L"] = (-6 + b, -12, 0); p["forearm_L"] = (-24, 0, 0)
        p["thigh_L"] = (0, -3, 0); p["thigh_R"] = (0, 3, 0)
        p["cape"] = (2 + 1.5 * b, 0, 0)
        return p
    if state == "walk":
        a = 2 * math.pi * k / n; sn, cs = math.sin(a), math.cos(a)
        tl, tr = -21 * sn, 21 * sn
        kl = 6 + 44 * max(0.0, cs) ** 1.5; kr = 6 + 44 * max(0.0, -cs) ** 1.5
        p["thigh_L"] = (tl, -2, 0); p["thigh_R"] = (tr, 2, 0)
        p["shin_L"] = (kl, 0, 0); p["shin_R"] = (kr, 0, 0)
        p["foot_L"] = (-(tl + kl) * 0.8, 0, 0); p["foot_R"] = (-(tr + kr) * 0.8, 0, 0)
        p["pelvis"] = (0, 0, 5 * sn); p["spine"] = (3, 0, 0); p["chest"] = (3, 0, -7 * sn)
        p["upper_arm_R"] = (-16 - 14 * sn, 9, 0); p["forearm_R"] = (-52 - 6 * sn, 0, 0); p["hand_R"] = (8, 0, 0)
        if shield:
            p["upper_arm_L"] = (-12 + 5 * sn, -11, 0); p["forearm_L"] = (-68, 0, 14)
        else:
            p["upper_arm_L"] = (-6 + 16 * sn, -11, 0); p["forearm_L"] = (-26 + 6 * sn, 0, 0)
        p["cape"] = (12 + 4 * math.sin(2 * a), 0, 0)
        return p
    if state == "attack":
        K = [
            dict(upper_arm_R=(-70, 26, 0), forearm_R=(-85, 0, 0), hand_R=(-5, 0, 0), chest=(-4, 0, -14), pelvis=(0, 0, -6), cape=(4, 0, 0)),
            dict(upper_arm_R=(-150, 22, 0), forearm_R=(-72, 0, 0), hand_R=(-15, 0, 0), chest=(-9, 0, -22), pelvis=(0, 0, -8), cape=(2, 0, 0),
                 thigh_R=(8, 0, 0), thigh_L=(-6, -3, 0)),
            dict(upper_arm_R=(-118, 12, 0), forearm_R=(-30, 0, 0), hand_R=(25, 0, 0), chest=(6, 0, 6), pelvis=(0, 0, 4), cape=(8, 0, 0),
                 thigh_L=(-18, -3, 0), shin_L=(14, 0, 0), thigh_R=(10, 3, 0)),
            dict(upper_arm_R=(-58, 2, 0), forearm_R=(-22, 0, 0), hand_R=IMP_HAND[0], chest=(15, 0, 22), spine=(6, 0, 0), pelvis=(4, 0, 10), cape=(16, 0, 0),
                 thigh_L=(-30, -3, 0), shin_L=(24, 0, 0), foot_L=(5, 0, 0), thigh_R=(16, 3, 0), shin_R=(8, 0, 0)),
            dict(upper_arm_R=(-32, -4, 0), forearm_R=(-20, 0, 0), hand_R=IMP_HAND[1], chest=(12, 0, 18), spine=(4, 0, 0), pelvis=(3, 0, 8), cape=(12, 0, 0),
                 thigh_L=(-26, -3, 0), shin_L=(22, 0, 0), foot_L=(4, 0, 0), thigh_R=(14, 3, 0), shin_R=(6, 0, 0)),
            dict(upper_arm_R=(-22, 8, 0), forearm_R=(-46, 0, 0), hand_R=(16, 0, 0), chest=(4, 0, 6), pelvis=(0, 0, 2), cape=(5, 0, 0),
                 thigh_L=(-10, -3, 0), shin_L=(8, 0, 0), thigh_R=(5, 3, 0)),
        ]
        p = dict(K[k])
        if shield:
            p["upper_arm_L"] = (-28 if 1 <= k <= 4 else -14, -10, 0); p["forearm_L"] = (-72, 0, 18)
        else:
            p["upper_arm_L"] = (-30 if 1 <= k <= 4 else -10, -22, 0); p["forearm_L"] = (-40, 0, 0)
        return p
    if state == "hit":
        # recoil from a blow to the chest: snap back, guard up, settle
        a = (0.75, 1.0, 0.35)[k]
        p = pose("idle", 0, 4, shield)
        p["spine"] = (-6 * a, 0, 0); p["chest"] = (-12 * a, 0, 5 * a); p["neck"] = (-16 * a, 0, -6 * a)
        p["upper_arm_R"] = (-16 - 26 * a, 9 + 22 * a, 0); p["forearm_R"] = (-52 - 10 * a, 0, 0)
        if shield:
            p["upper_arm_L"] = (-12 - 26 * a, -11, 0); p["forearm_L"] = (-68 - 8 * a, 0, 14)
        else:
            p["upper_arm_L"] = (-6 - 30 * a, -24 * a - 12, 0); p["forearm_L"] = (-24 - 20 * a, 0, 0)
        p["thigh_L"] = (8 * a, -3, 0); p["shin_L"] = (10 * a, 0, 0); p["foot_L"] = (-12 * a, 0, 0)
        p["thigh_R"] = (-10 * a, 3, 0); p["shin_R"] = (14 * a, 0, 0); p["foot_R"] = (-4 * a, 0, 0)
        return p
    if state == "death":
        D = [  # stagger, buckle, falling, nearly down, impact bounce, settled
            dict(chest=(-12, 0, 6), neck=(-14, 0, 0), spine=(-4, 0, 0), upper_arm_R=(-34, 34, 0), forearm_R=(-30, 0, 0),
                 thigh_L=(-6, -3, 0), shin_L=(14, 0, 0), thigh_R=(6, 3, 0), shin_R=(10, 0, 0)),
            dict(chest=(12, 0, 0), spine=(8, 0, 0), neck=(18, 0, 0), upper_arm_R=(-8, 16, 0), forearm_R=(-22, 0, 0),
                 thigh_L=(-32, -3, 0), shin_L=(58, 0, 0), foot_L=(-22, 0, 0), thigh_R=(-28, 3, 0), shin_R=(52, 0, 0), foot_R=(-20, 0, 0)),
            dict(chest=(4, 0, 0), neck=(-12, 0, 0), upper_arm_R=(-58, 48, 0), forearm_R=(-20, 0, 0),
                 thigh_L=(-36, -4, 0), shin_L=(60, 0, 0), foot_L=(-18, 0, 0), thigh_R=(-30, 4, 0), shin_R=(50, 0, 0)),
            dict(chest=(-4, 0, 0), neck=(-16, 0, 0), upper_arm_R=DTH_ARM[0], forearm_R=(-16, 0, 0),
                 thigh_L=(-26, -6, 0), shin_L=(36, 0, 0), thigh_R=(-18, 6, 0), shin_R=(28, 0, 0)),
            dict(chest=(-2, 0, 0), neck=(-6, 0, 10), upper_arm_R=DTH_ARM[1], forearm_R=(-12, 0, 0),
                 thigh_L=(-16, -8, 0), shin_L=(22, 0, 0), thigh_R=(-10, 8, 0), shin_R=(16, 0, 0)),
            dict(chest=(0, 0, 0), neck=(0, 0, 24), upper_arm_R=(-74, 78, 0), forearm_R=(-14, 0, 0), hand_R=(10, 0, 0),
                 thigh_L=(-10, -9, 0), shin_L=(14, 0, 0), foot_L=(10, 0, 0), thigh_R=(-6, 9, 0), shin_R=(10, 0, 0), foot_R=(8, 0, 0)),
        ]
        p = dict(D[k])
        la = (-30, -12, -64, -96, -80, -72)[k]
        if shield:
            p["upper_arm_L"] = (la * 0.6, -14 - 20 * (k >= 2), 0); p["forearm_L"] = (-64, 0, 14)
        else:
            p["upper_arm_L"] = (la, -30 - 30 * (k >= 2), 0); p["forearm_L"] = (-20, 0, 0)
        return p
    return p


# attack: wind-up (f01) -> strike (f02) -> impact (f03, the hitsplat frame) -> follow-through (f04) -> recovery (f05)
ATTACK_FRAME_STARTS = [0.0, 0.14, 0.30, 0.42, 0.60, 0.80]   # progress 0..1 over ATTACK_ANIM_SECS (1.05 s)
ATTACK_IMPACT_FRAME = 3                                        # covers progress 0.42-0.60; client hitsplat releases at 0.48
LUNGE = (0.0, 0.02, -0.03, -0.06, -0.05, -0.02)               # root step along facing (x s), negative = toward target
DEATH_FALL = (0, 15, 40, 72, 88, 90)                           # degrees from upright


def root_for(state, k, facing, J):
    """(root_rotation_euler_deg or None, root_offset) for a frame. Death falls stay screen-horizontal:
    s/n fall to the knight's right (-X), shield side up; e/w fall backward (+Y, away from the target)."""
    s = J["s"]
    if state == "attack":
        return None, (0, LUNGE[k] * s, 0)
    if state == "hit":
        return None, (0, (0.03, 0.045, 0.015)[k] * s, 0)
    if state == "death":
        th = DEATH_FALL[k]; sh = J["pelvis"].z * math.sin(math.radians(th)) * 0.62
        back = 0.03 * s if k == 0 else 0.0
        if facing in ("s", "n"):
            return (0, -th, 0), (sh * 1.45, back, 0)
        return (-th, 0, 0), (0, back - sh, 0)
    return None, (0, 0, 0)


def pose_full(state, k, n, shield):
    p = pose(state, k, n, shield)
    lean = sum(p.get(b, (0, 0, 0))[0] for b in ("pelvis", "spine", "chest"))
    if state == "walk":
        fl = 4 + 2 * math.sin(4 * math.pi * k / n)
    elif state == "attack":
        fl = (3, 2, 5, 7, 6, 3)[k]
    elif state == "hit":
        fl = (6, 9, 4)[k]
    elif state == "death":
        fl = (8, 10, 6, 2, 0, 0)[k]
    else:
        fl = 1.5 + 1.0 * math.sin(2 * math.pi * k / n)
    p["cape"] = (fl - lean, 0, 0)
    return p


# ------------------------------------------------------------------ weapons placement (in idle pose)
def frame_from(z, x):
    z = z.normalized(); x = (x - z * x.dot(z)).normalized(); y = z.cross(x)
    return Matrix((x, y, z)).transposed().to_4x4()


def attach_weapons(col, arm, ctx, wpn, shd, extra):
    J = ctx["J"]; s = ctx["s"]
    has_shield = shd is not None
    RG.set_pose(arm, pose("idle", 0, 4, has_shield))
    PM = RG.posed(arm)
    w, t = J["wrist_R"], J["tip_R"]
    g_rest = w + (t - w) * 0.40
    grip = RG.posed_point(arm, PM, "hand_R", g_rest)
    d = Vector((0, -0.42, 0.9))
    parts = KP.sword("wpn", col, L=wpn["L"], w0=wpn["w0"], th=wpn.get("th", 0.007), blade=wpn["blade"], guard=wpn["guard"], grip=wpn["grip"],
                     pommel=wpn.get("pommel"), rune=wpn.get("rune"), profile=wpn["profile"], guard_w=wpn.get("guard_w", 0.13),
                     guard_style=wpn.get("guard_style", "bar"))
    if wpn.get("core"):
        parts.append(KP.blade_mesh("wpn_core", wpn["L"] * 0.92, wpn["w0"] * 0.35, 0.003, wpn["core"], col, "long"))
    KP.place(parts, Matrix.Translation(grip) @ frame_from(d, Vector((1, 0, 0))) @ Matrix.Translation((0, 0, 0.065)))
    bpy.context.view_layer.update()
    for p in parts:
        RG.bone_parent(p, arm, "hand_R", PM["hand_R"])
    if has_shield:
        e, wr = J["elbow_L"], J["wrist_L"]
        mid = RG.posed_point(arm, PM, "forearm_L", e.lerp(wr, 0.55))
        hp = [RG.posed_point(arm, PM, "hand_L", J["wrist_L"].lerp(J["tip_L"], t)) for t in (0.0, 0.5, 1.0)] + [mid]
        ymin = min(p.y for p in hp) - 0.05 * s
        c = Vector((mid.x + 0.05 * s, ymin, mid.z + 0.01 * s))
        if shd["kind"] == "round":
            sp = KP.round_shield("shield", col, R=0.25 * s, wood=shd["wood"], rim=shd["rim"], boss=shd["boss"], rivet=shd["rivet"])
        else:
            dark = C.principled("KN_Dark", (0.02, 0.02, 0.03), rough=0.6)
            em = None
            if shd.get("emblem") == "tower":
                em = lambda y: tower_emblem("sh_tower", (0, y - 0.004, 0.02), 1.5, shd["emblem_mat"], dark, col)
            elif shd.get("emblem") == "sun":
                em = lambda y: sun_emblem("sh_sun", (0, y - 0.004, 0.03), 1.4, shd["emblem_mat"], col)
            elif shd.get("emblem") == "void":
                em = lambda y: void_sigil("sh_void", (0, y - 0.006, 0.06), 1.5, shd["emblem_mat"], shd["glow"], col)
            if shd["kind"] == "tower":
                sp = KP.heater_shield("shield", col, W=0.36 * s, Hh=0.62 * s, curv=0.06, field=shd["field"], rim=shd["rim"], rivet=shd["rivet"],
                                      emblem_fn=em, shape="tower", thick=0.022)
                for k, (dx, dz) in enumerate(((0.12, 0.22), (-0.12, 0.22), (0.12, -0.12), (-0.12, -0.12))):
                    sp.append(C.cyl(f"sh_stud{k}", 0.016, 0.05, (dx * s, -0.08, dz * s), segs=8, mat=shd["rim"], col=col, r2=0.0))
                    sp[-1].rotation_euler = (math.pi / 2, 0, 0)
            else:
                sp = KP.heater_shield("shield", col, W=0.30 * s, Hh=0.46 * s, curv=0.05, field=shd["field"], rim=shd["rim"], rivet=shd["rivet"],
                                      emblem_fn=em, battered=shd.get("battered", 0.0))
        KP.place(sp, Matrix.Translation(c) @ Matrix.Rotation(math.radians(16), 4, "Z"))
        bpy.context.view_layer.update()
        for p in sp:
            RG.bone_parent(p, arm, "forearm_L", PM["forearm_L"])
    off = extra.get("offhand")
    if off:
        w, t = J["wrist_L"], J["tip_L"]
        hpos = RG.posed_point(arm, PM, "hand_L", w + (t - w) * 0.45)
        rnd = random.Random(21)
        gm = KP.ghost_mat("KN_Offhand_" + off, extra["glow"], 6.0, 0.6)
        objs = [C.ico("off_core", 0.035 * s, hpos + Vector((0, -0.01, 0.0)), sub=3, mat=KP.glow("KN_OffCore", extra["glow"], 10.0), col=col)]
        for k in range(7):
            a = 2 * math.pi * k / 7
            b = hpos + Vector((math.cos(a) * 0.035, math.sin(a) * 0.035, 0.0))
            pts = [b, b + Vector((math.cos(a) * 0.03, math.sin(a) * 0.03, 0.06)), b + Vector((rnd.uniform(-0.03, 0.03), rnd.uniform(-0.03, 0.03), 0.14 + 0.05 * rnd.random()))]
            if off == "lava":
                pts = [b, b + Vector((0, 0, -0.04)), b + Vector((rnd.uniform(-0.01, 0.01), 0, -0.07 - 0.05 * rnd.random()))]
            objs.append(C.tube_curve(f"off_flame{k}", pts, radius=0.012 * s, mat=gm if off == "void" else KP.glow("KN_LavaDrip", extra["glow"], 9.0), col=col,
                                     radii=[1.0, 0.7, 0.05]))
        bpy.context.view_layer.update()
        for o in objs:
            RG.bone_parent(o, arm, "hand_L", PM["hand_L"])
    return has_shield


# ------------------------------------------------------------------ lights / render
def light_rig(sc, hero=False, glow=None):
    C.world(sc, top=(0.22, 0.22, 0.30), bottom=(0.45, 0.38, 0.32), strength=0.36 if hero else 0.5)
    C.sun(sc, energy=2.8 if hero else 3.4, color=(1.0, 0.88, 0.74), rot=(42, 18, -35), name="Key")
    C.sun(sc, energy=1.5, color=(0.6, 0.7, 1.0), rot=(55, -10, 155), name="Rim")
    C.sun(sc, energy=0.6, color=(1.0, 0.82, 0.6), rot=(20, 40, 60), name="Fill2")
    if hero:
        a = bpy.data.lights.new("Fill", "AREA"); a.energy = 60; a.size = 2.2; a.color = (0.9, 0.88, 1.0)
        o = bpy.data.objects.new("Fill", a); o.location = (2.2, -2.6, 1.7); o.rotation_euler = (math.radians(70), 0, math.radians(40)); sc.collection.objects.link(o)
        a2 = bpy.data.lights.new("Kick", "AREA"); a2.energy = 90; a2.size = 1.2; a2.color = glow or (1.0, 0.6, 0.4)
        o2 = bpy.data.objects.new("Kick", a2); o2.location = (-1.6, 1.9, 2.1); o2.rotation_euler = (math.radians(-55), 0, math.radians(-140)); sc.collection.objects.link(o2)


def main():
    sc = C.reset()
    col = bpy.data.collections.new(KEY.upper()); sc.collection.children.link(col)
    WMODE.clear()
    ctx, wpn, shd, extra = BUILD[KEY](col)
    if extra.get("glow"):
        L = bpy.data.lights.new("ArmourGlow", "POINT"); L.energy = 1.5; L.color = extra["glow"]; L.shadow_soft_size = 0.3
        lo = bpy.data.objects.new("ArmourGlow", L); lo.location = (0, -0.6 * ctx["s"], 1.75 * ctx["s"]); col.objects.link(lo)
    H.hide_covered(ctx["body"], ctx["hide"])
    RG.curves_to_mesh(col)
    print("BUILD_DONE objects", len(col.objects), flush=True)
    return sc, col, ctx, wpn, shd, extra


_ANCH = {}


def record_anchor(sc, cam, arm, J, wpn, base, st, f, k, fn="anchors_4x.json"):
    """Project head top, weapon tip and sword hand into 4x canvas pixels (feet anchor is fixed at FEET)."""
    from bpy_extras.object_utils import world_to_camera_view
    bpy.context.view_layer.update()
    PM = RG.posed(arm)
    AW = arm.matrix_world

    def px(co):
        v = world_to_camera_view(sc, cam, co)
        return [round(v.x * CANVAS[0], 1), round((1 - v.y) * CANVAS[1], 1)]
    head = AW @ RG.posed_point(arm, PM, "head", J["top"])
    hand = AW @ RG.posed_point(arm, PM, "hand_R", J["wrist_R"].lerp(J["tip_R"], 0.4))
    bl = bpy.data.objects.get("wpn_blade")
    tip = bl.matrix_world @ Vector((0, 0, 0.03 + wpn["L"])) if bl else hand
    _ANCH[f"{st}/{f}/{k:02d}"] = {"head": px(head), "weapon_tip": px(tip), "weapon_hand": px(hand)}
    with open(f"{base}/{fn}", "w") as fh:
        json.dump(_ANCH, fh)


def rig_and_render(sc, col, ctx, wpn, shd, extra):
    J = ctx["J"]
    arm = RG.build_armature(col, J)
    RG.skin_all(col, arm, ctx["body"], ctx["W"], ctx["rest_co"])
    shield = attach_weapons(col, arm, ctx, wpn, shd, extra)
    if MODE == "debug":
        RG.ground(arm, pose("idle", 0, 4, shield), J)
        dg = bpy.context.evaluated_depsgraph_get()
        for ob in col.objects:
            if ob.type != "MESH":
                continue
            e = ob.evaluated_get(dg)
            try:
                me = e.to_mesh()
            except Exception:
                continue
            if len(me.vertices):
                zs = [(e.matrix_world @ v.co).z for v in me.vertices]
                if min(zs) < 0.06 and max(zs) < 0.3:
                    print("DBG low", ob.name, round(min(zs), 3), round(max(zs), 3), ob.parent_type, ob.parent_bone)
            e.to_mesh_clear()
        return
    base = f"{OUT}/renders/{KEY}"; os.makedirs(base, exist_ok=True)
    pv = "_preview" if PREVIEW else ""
    glow = extra.get("glow")
    if MODE in ("hero", "all"):
        light_rig(sc, hero=True, glow=glow)
        RG.ground(arm, pose("idle", 0, 4, shield), J)
        C.cycles(sc, samples=20 if PREVIEW else max(SAMPLES, 96), w=2048, h=2048, transparent=True)
        if PREVIEW:
            sc.render.resolution_percentage = 30
        cam = H.persp_camera(sc, (0, 0, 1.06), 6.7, 22, 6, 85, 2048, 2048, name="Cam")
        C.render(sc, f"{base}/hero{pv}.png"); bpy.data.objects.remove(cam)
    if MODE in ("portrait", "all"):
        if not any(o.name == "Key" for o in sc.objects):
            light_rig(sc, hero=True, glow=glow)
        RG.ground(arm, pose("idle", 0, 4, shield), J)
        C.cycles(sc, samples=20 if PREVIEW else max(SAMPLES, 96), w=1024, h=1024, transparent=True)
        if PREVIEW:
            sc.render.resolution_percentage = 40
        pz = ctx["face"]["eye_z"] - 0.02
        cam = H.persp_camera(sc, (0, -0.02, pz), 1.75, 16, 3, 85, 1024, 1024, name="PCam")
        C.render(sc, f"{base}/portrait_bust{pv}.png"); bpy.data.objects.remove(cam)
    if MODE in ("sprites", "test", "all"):
        for o in list(sc.objects):
            if o.type == "LIGHT" and (o.name in ("Fill", "Kick") or o.data.type == "SUN"):
                bpy.data.objects.remove(o)
        light_rig(sc, hero=False, glow=glow)
        C.shadow_catcher("catcher", 8, (0, 0, 0), None)
        cam, ppm = H.sprite_camera(sc, h_px=PPM, height_m=1.0, w=CANVAS[0], hgt=CANVAS[1], feet=FEET)
        # The shared helper sets ortho_scale from the width, but Blender's AUTO fit applies it to the larger side
        # (height here), which would give 197.5 px/m and put the feet at y=558. Fit to width = true 175.6 px/m, feet at FEET.
        cam.data.sensor_fit = "HORIZONTAL"
        test = MODE == "test"
        C.cycles(sc, samples=12 if test else SAMPLES, w=CANVAS[0], h=CANVAS[1], transparent=True)
        if test:
            sc.render.resolution_percentage = int(C.arg("--pct", 50))
        rots = {"s": 0, "e": 90, "n": 180, "w": -90}
        plan = [(st, k) for st in STATES for k in range(NFR[st])]
        if test:
            plan = [tuple((x.split(":")[0], int(x.split(":")[1]))) for x in C.arg("--plan", "idle:0,walk:0,walk:2,attack:1,attack:3").split(",")]
        for f in (FACINGS if not test else C.arg("--tf", "s,e").split(",")):
            arm.rotation_euler = (0, 0, math.radians(rots[f]))
            for st, k in plan:
                out = f"{base}/{'test' if test else SPRDIR}/{st}/{f}/f{k:02d}.png"
                P = pose_full(st, k, NFR[st], shield)
                rr, ro = root_for(st, k, f, J)
                if rr is not None:
                    P["root"] = rr
                if st == "death":
                    RG.ground_any(arm, P, J, ro, lift=0.012 * J["s"] if k == 4 else 0.0)
                else:
                    RG.ground(arm, P, J, ro)
                record_anchor(sc, cam, arm, J, wpn, base, st, f, k, "anchors_test.json" if test else f"anchors_{SPRDIR}.json")
                if test:
                    print("ANCH", st, f, k, _ANCH[f"{st}/{f}/{k:02d}"]["weapon_tip"], flush=True)
                if not test and os.path.exists(out):
                    continue
                C.render(sc, out)
    print("DONE", KEY, MODE, flush=True)


sc, col, ctx, wpn, shd, extra = main()
rig_and_render(sc, col, ctx, wpn, shd, extra)
