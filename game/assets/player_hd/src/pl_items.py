"""Player HD: body + cosmetic catalogue + steel armour/weapons, all built on ONE rig per sex."""
import bpy, bmesh, math, random
from mathutils import Vector
import fv_common as C
import fv_npc_helpers as H
import pl_rig as R
import pl_mats as M
import pl_geo as G
import pl_hair as HR

SKINS = {"light": (0.92, 0.72, 0.60), "tan": (0.74, 0.52, 0.38), "deep": (0.44, 0.28, 0.19)}
IRIS = {"male": (0.20, 0.15, 0.09), "female": (0.14, 0.24, 0.30)}   # darker irises so eyes read as eyes at 2x


def build_base(kind, col):
    body, eyes = H.take_body(col, kind)
    J = R.joints(body, kind)
    arm = R.build_armature(col, J)
    R.skin_auto(body, arm)
    bw = R.BodyWeights(body)
    ctx = G.Ctx(kind, col, body, eyes, J, arm, bw)
    tree = H.bvh(body)
    face = H.find_face(tree, eyes)
    ctx.face = face
    ctx.skin_mats = {}
    for nm, base in SKINS.items():
        lips = (0.58, 0.30, 0.28) if kind == "male" else (0.66, 0.22, 0.26)
        if nm == "deep":
            lips = (0.36, 0.16, 0.15)
        ctx.skin_mats[nm] = H.skin_mat(f"PL_Skin_{kind}_{nm}", base=base, lips=lips,
                                       blush=tuple(min(1, c * 1.12) for c in base),
                                       sss_col=(1.0, 0.42, 0.28))
        # pores / micro detail stronger for the higher bar
        nt = ctx.skin_mats[nm].node_tree
        for n in nt.nodes:
            if n.type == "BUMP":
                n.inputs["Strength"].default_value = 0.07
        M._aov(nt, 0.0)
    H.setup_skin(body, eyes, tree, ctx.skin_mats["light"], IRIS[kind], face, ctx.s,
                 cheeks_dx=0.05 if kind == "female" else 0.055)
    import pl_face
    pl_face.enhance(ctx, face)
    ctx.layer("body")
    ctx.add(body)
    for e in eyes:
        ctx.add(e)
    if kind == "female":
        for o in H.lashes("lash", eyes, M.cloth("PL_Lash", (0.05, 0.03, 0.03), "silk"), col, ctx.h):
            G.rigid(ctx, o, "head")
    # modest base underlayer (always present under cosmetics)
    s, h, mask = ctx.s, ctx.h, ctx.mask
    under = M.cloth(f"PL_Under_{kind}", (0.34, 0.29, 0.24), "linen")
    hipz, kz = ctx.J["hip_L"].z, ctx.J["knee_L"].z
    G.shell(ctx, "under_shorts", lambda v: (not mask[v.index]) and kz + 0.12 * h * 0.5 < v.co.z < hipz + 0.07 * h, under, offset=0.004, thick=0.002)
    if kind == "female":
        G.shell(ctx, "under_top", lambda v: (not mask[v.index]) and ctx.J["spine"].z + 0.01 * h < v.co.z < ctx.J["shoulder_L"].z - 0.035 * h,
                under, offset=0.004, thick=0.002)
    # brows: own tintable layer (follows hair colour)
    ctx.layer("brows")
    bm = M.scalp_grey("PL_Brow", 0.24)
    for o in H.brows("brow", eyes, tree, bm, col, ctx.h, thick=0.0046 if kind == "male" else 0.0032,
                     lift=0.028, arch=0.003 if kind == "male" else 0.005, w=0.032 if kind == "male" else 0.029):
        G.rigid(ctx, o, "head")
    for e in eyes:
        R.bone_parent(e, arm, "head")
    return ctx


# ------------------------------------------------------------------ helpers on h-fractions
def zs(ctx):
    J, h = ctx.J, ctx.h
    return dict(neck=J["shoulder_L"].z + 0.035 * h, shoulder=J["shoulder_L"].z, chest=J["chest"].z, spine=J["spine"].z,
                waist=J["spine"].z - 0.03 * h, hip=J["hip_L"].z, knee=J["knee_L"].z, ankle=J["ankle_L"].z,
                elbow=J["elbow_L"].z, wrist=J["wrist_L"].z)


def torso(ctx, lo, hi, neck_front_cut=0.03):
    Z = zs(ctx); m = ctx.mask
    return lambda v: (not m[v.index]) and lo < v.co.z < hi and not (v.co.z > Z["shoulder"] + 0.005 * ctx.h and v.co.y < -0.035 * ctx.s and abs(v.co.x) < 0.06 * ctx.s) \
        and not (v.co.z > Z["neck"] - neck_front_cut * ctx.h * 0.2)


def arms(ctx, lo_z):
    m = ctx.mask
    return lambda v: m[v.index] and v.co.z > lo_z


def legs(ctx, lo, hi):
    m = ctx.mask
    return lambda v: (not m[v.index]) and lo < v.co.z < hi


def either(*ps):
    return lambda v: any(p(v) for p in ps)


def laces(ctx, z0, z1, mat, n=5, w=0.018, name="lace"):
    for i in range(n):
        z = z0 + (z1 - z0) * i / max(1, n - 1)
        p, nr = G.surf_pt(ctx, -w * ctx.s, z, push=0.016)
        q, nq = G.surf_pt(ctx, w * ctx.s, z + (z1 - z0) / max(1, n - 1) * 0.9, push=0.016)
        if p is None or q is None:
            continue
        mid = (p + q) / 2 + Vector((0, -0.003, 0))
        t = G.tube_mesh(f"{name}{i}", [p, mid, q], 0.0016 * ctx.s, mat, ctx.col)
        G.bound(ctx, t)
        t2 = G.tube_mesh(f"{name}b{i}", [Vector((-p.x, p.y, p.z)), mid, Vector((-q.x, q.y, q.z))], 0.0016 * ctx.s, mat, ctx.col)
        G.bound(ctx, t2)


def buttons(ctx, zlist, mat, x=0.0, r=0.006, push=0.02, name="btn"):
    pn = []
    for z in zlist:
        p, n = G.surf_pt(ctx, x, z, push=push)
        if p is not None:
            pn.append((p, n))
    G.studs(ctx, pn, r * ctx.s, mat, name=name)


def belt(ctx, z, leather, metal, name="belt", w=0.012, grow=0.026):
    G.ring_band(ctx, name, z, leather, r=w * ctx.s, grow=grow * ctx.s, y_extra=0.004)
    p, n = G.surf_pt(ctx, 0, z, push=grow + 0.012)
    if p is not None:
        b = C.torus(f"{name}_buckle", 0.016 * ctx.s, 0.0035 * ctx.s, p, mat=metal, col=ctx.col, rot=(math.radians(90), 0, 0))
        b.scale = (1.0, 1.25, 1.0)
        G.bound(ctx, b)


# ------------------------------------------------------------------ TOPS
def top_linen_shirt(ctx):
    Z = zs(ctx); s, h = ctx.s, ctx.h
    lin = M.cloth("PL_Linen", (0.86, 0.82, 0.72), "linen")
    o = G.shell(ctx, "shirt", either(torso(ctx, Z["hip"] - 0.03 * h, Z["neck"]), arms(ctx, Z["wrist"] + 0.025 * h)), lin, offset=0.011)
    G.hem(ctx, o, lin, r=0.004 * s, stitch_mat=M.stitch("PL_StitchCream", (0.70, 0.64, 0.50)))
    laces(ctx, Z["shoulder"] - 0.10 * h, Z["shoulder"] - 0.01 * h, M.cloth("PL_LaceCord", (0.45, 0.30, 0.18), "leather"), n=4)


def top_wool_tunic(ctx):
    Z = zs(ctx); s, h = ctx.s, ctx.h
    wool = M.cloth("PL_WoolTunic", (0.42, 0.30, 0.20), "wool", color2=(0.36, 0.25, 0.17))
    o = G.shell(ctx, "tunic", either(torso(ctx, Z["hip"] - 0.07 * h, Z["neck"]), arms(ctx, Z["elbow"] - 0.03 * h)), wool, offset=0.013)
    G.hem(ctx, o, M.cloth("PL_TunicTrim", (0.62, 0.48, 0.24), "wool"), r=0.0055 * s, stitch_mat=M.stitch("PL_StitchGold", (0.85, 0.70, 0.35)))
    belt(ctx, Z["waist"], M.cloth("PL_BeltBrown", (0.30, 0.18, 0.09), "leather"), M.metal("PL_BuckleIron", tint=0.0), grow=0.03)


def top_leather_jerkin(ctx):
    Z = zs(ctx); s, h = ctx.s, ctx.h
    lin = M.cloth("PL_Linen", (0.86, 0.82, 0.72), "linen")
    o = G.shell(ctx, "jk_shirt", arms(ctx, Z["wrist"] + 0.025 * h), lin, offset=0.011)
    G.hem(ctx, o, lin, r=0.004 * s)
    G.shell(ctx, "jk_shirt_t", torso(ctx, Z["hip"] - 0.03 * h, Z["neck"]), lin, offset=0.010)
    lea = M.cloth("PL_JerkinLeather", (0.36, 0.22, 0.12), "leather")
    j = G.shell(ctx, "jerkin", lambda v: (not ctx.mask[v.index]) and Z["hip"] - 0.05 * h < v.co.z < Z["shoulder"] + 0.01 * h
                and not (v.co.y < -0.02 * s and abs(v.co.x) < 0.022 * s) and not (abs(v.co.x) > 0.14 * s and v.co.z > Z["shoulder"] - 0.04 * h),
                lea, offset=0.022, thick=0.006)
    G.hem(ctx, j, M.cloth("PL_JerkinEdge", (0.22, 0.13, 0.07), "leather"), r=0.005 * s, stitch_mat=M.stitch("PL_StitchTan", (0.78, 0.62, 0.40)))
    iron = M.metal("PL_BuckleIron", tint=0.0)
    for i in range(4):
        z = Z["waist"] + (0.02 + 0.045 * i) * h
        p, n = G.surf_pt(ctx, 0.0, z, push=0.03)
        if p is not None:
            st = G.tube_mesh(f"jk_strap{i}", [p + Vector((-0.03 * s, 0, 0)), p + Vector((0.03 * s, -0.002, 0))], 0.0045 * s, lea, ctx.col)
            G.bound(ctx, st)
            bk = C.box(f"jk_buckle{i}", (0.012 * s, 0.004 * s, 0.014 * s), p + Vector((0.006 * s, -0.006, 0)), iron, ctx.col, bevel=0.0015)
            G.bound(ctx, bk)


def top_gambeson(ctx):
    Z = zs(ctx); s, h = ctx.s, ctx.h
    fresh = bpy.data.materials.get("PL_Gambeson") is None
    gam = M.cloth("PL_Gambeson", (0.72, 0.62, 0.44), "canvas")
    nt = gam.node_tree; b = nt.nodes["Principled BSDF"]
    if not fresh:
        nt = None
    # diamond quilting: extra bump from two diagonal wave textures
    acc = None
    for rot in ((0.785, -0.785) if nt else ()):
        tc = nt.nodes.new("ShaderNodeTexCoord")
        mp = nt.nodes.new("ShaderNodeMapping"); mp.inputs["Rotation"].default_value = (0, rot, 0)
        nt.links.new(tc.outputs["Object"], mp.inputs["Vector"])
        w = nt.nodes.new("ShaderNodeTexWave"); w.bands_direction = "X"; w.inputs["Scale"].default_value = 22; w.wave_profile = "TRI"
        nt.links.new(mp.outputs["Vector"], w.inputs["Vector"])
        if acc is None:
            acc = w.outputs["Fac"]
        else:
            mn = nt.nodes.new("ShaderNodeMath"); mn.operation = "MINIMUM"; nt.links.new(acc, mn.inputs[0]); nt.links.new(w.outputs["Fac"], mn.inputs[1]); acc = mn.outputs[0]
    if nt is None:
        acc = None
    if acc is not None:
      bq = nt.nodes.new("ShaderNodeBump"); bq.inputs["Strength"].default_value = 0.6; bq.inputs["Distance"].default_value = 0.006
      nt.links.new(acc, bq.inputs["Height"])
      old = b.inputs["Normal"].links[0].from_socket if b.inputs["Normal"].links else None
      if old is not None:
          nt.links.new(old, bq.inputs["Normal"])
      nt.links.new(bq.outputs["Normal"], b.inputs["Normal"])
    o = G.shell(ctx, "gambeson", either(torso(ctx, Z["hip"] - 0.09 * h, Z["neck"] + 0.02 * h, neck_front_cut=0.0), arms(ctx, Z["wrist"] + 0.02 * h)),
                gam, offset=0.02, thick=0.008)
    G.hem(ctx, o, M.cloth("PL_GambTrim", (0.40, 0.30, 0.18), "leather"), r=0.006 * s, stitch_mat=M.stitch("PL_StitchDark", (0.25, 0.18, 0.10)))
    buttons(ctx, [Z["waist"] + k * 0.05 * h for k in range(5)], M.metal("PL_BtnBrass", base=(0.80, 0.62, 0.30), tint=0.0), r=0.0055, push=0.028)


def top_ranger_tunic(ctx):
    Z = zs(ctx); s, h = ctx.s, ctx.h
    grn = M.cloth("PL_RangerGreen", (0.18, 0.30, 0.14), "wool", color2=(0.14, 0.24, 0.11))
    o = G.shell(ctx, "ranger", either(torso(ctx, Z["hip"] - 0.10 * h, Z["neck"]), arms(ctx, Z["wrist"] + 0.03 * h)), grn, offset=0.014)
    G.hem(ctx, o, M.cloth("PL_RangerTrim", (0.30, 0.22, 0.10), "leather"), r=0.005 * s, stitch_mat=M.stitch("PL_StitchTan", (0.78, 0.62, 0.40)))
    lea = M.cloth("PL_Bracer", (0.34, 0.20, 0.10), "leather")
    for side in ("L", "R"):
        sx = 1 if side == "L" else -1
        br = G.shell(ctx, f"bracer{side}", lambda v, sx=sx: ctx.mask[v.index] and v.co.x * sx > 0 and Z["wrist"] + 0.005 * h < v.co.z < Z["wrist"] + 0.10 * h,
                     lea, offset=0.026, thick=0.005)
        G.hem(ctx, br, M.cloth("PL_BracerEdge", (0.20, 0.12, 0.06), "leather"), r=0.003 * s)
    belt(ctx, Z["waist"], M.cloth("PL_BeltBrown", (0.30, 0.18, 0.09), "leather"), M.metal("PL_BuckleIron", tint=0.0), grow=0.032)


def top_noble_doublet(ctx):
    Z = zs(ctx); s, h = ctx.s, ctx.h
    vel = M.cloth("PL_Burgundy", (0.36, 0.05, 0.08), "velvet")
    o = G.shell(ctx, "doublet", either(torso(ctx, Z["hip"] - 0.04 * h, Z["neck"] + 0.015 * h, neck_front_cut=0.0), arms(ctx, Z["wrist"] + 0.02 * h)),
                vel, offset=0.016, thick=0.006)
    goldm = M.gold("PL_Gold")
    G.hem(ctx, o, goldm, r=0.0042 * s)
    buttons(ctx, [Z["waist"] + k * 0.035 * h for k in range(8)], goldm, r=0.0055, push=0.024)
    # slashed-sleeve puffs (gold silk showing through)
    silk = M.cloth("PL_GoldSilk", (0.85, 0.66, 0.28), "silk")
    for side in ("L", "R"):
        sx = 1 if side == "L" else -1
        for k in range(3):
            zc = Z["shoulder"] - (0.05 + 0.035 * k) * h
            pts = [ctx.body.data.vertices[i].co for i in range(len(ctx.body.data.vertices))
                   if ctx.mask[i] and ctx.body.data.vertices[i].co.x * sx > 0 and abs(ctx.body.data.vertices[i].co.z - zc) < 0.01]
            if pts:
                c = sum(pts, Vector()) / len(pts)
                o2 = C.uvsphere(f"puff{side}{k}", 0.012 * s, c + Vector((sx * 0.035 * s, -0.012, 0)), segs=12, rings=8, mat=silk, col=ctx.col, scale=(0.5, 1.0, 1.6))
                G.bound(ctx, o2)


# ------------------------------------------------------------------ BOTTOMS
def bottom_work_trousers(ctx):
    Z = zs(ctx); s, h = ctx.s, ctx.h
    w = M.cloth("PL_TrouserBrown", (0.30, 0.22, 0.15), "wool")
    o = G.shell(ctx, "trousers", legs(ctx, Z["ankle"] + 0.015 * h, Z["waist"] + 0.01 * h), w, offset=0.02, thick=0.004, folds=0.006)
    G.hem(ctx, o, w, r=0.0045 * s, stitch_mat=M.stitch("PL_StitchDark", (0.25, 0.18, 0.10)))
    belt(ctx, Z["waist"] - 0.005 * h, M.cloth("PL_BeltDark", (0.18, 0.11, 0.06), "leather"), M.metal("PL_BuckleIron", tint=0.0), grow=0.022)


def bottom_long_skirt(ctx):
    Z = zs(ctx); s, h = ctx.s, ctx.h
    w = M.cloth("PL_SkirtBlue", (0.20, 0.26, 0.38), "wool", color2=(0.16, 0.21, 0.31))
    sk = G.skirt(ctx, "long_skirt", Z["waist"], Z["ankle"] + 0.045 * h, (0.31 * s, 0.29 * s), w, folds=14, fold_amp=0.018 * s)
    G.ring_band(ctx, "skirt_band", Z["waist"], M.cloth("PL_SkirtBand", (0.55, 0.42, 0.22), "wool"), r=0.008 * s, grow=0.02 * s)


def bottom_leather_breeches(ctx):
    Z = zs(ctx); s, h = ctx.s, ctx.h
    lea = M.cloth("PL_Breeches", (0.28, 0.17, 0.09), "leather")
    o = G.shell(ctx, "breeches", legs(ctx, Z["knee"] - 0.035 * h, Z["waist"] + 0.01 * h), lea, offset=0.012, thick=0.005)
    G.hem(ctx, o, M.cloth("PL_BreechEdge", (0.18, 0.10, 0.05), "leather"), r=0.005 * s, stitch_mat=M.stitch("PL_StitchTan", (0.78, 0.62, 0.40)))
    hose = M.cloth("PL_HoseGrey", (0.40, 0.40, 0.38), "knit")
    G.shell(ctx, "hose", legs(ctx, Z["ankle"] + 0.01 * h, Z["knee"] - 0.02 * h), hose, offset=0.007, thick=0.003)
    belt(ctx, Z["waist"] - 0.005 * h, M.cloth("PL_BeltDark", (0.18, 0.11, 0.06), "leather"), M.metal("PL_BuckleIron", tint=0.0), grow=0.022)


def tartan(name):
    m, nt = M._nt(name)
    if nt is None:
        return m
    M.cloth(name + "_x", (0.2, 0.2, 0.2), "wool")
    b = nt.nodes["Principled BSDF"]
    tc = nt.nodes.new("ShaderNodeTexCoord")
    cols = []
    for ax, sc in (("X", 18.0), ("Z", 18.0)):
        w = nt.nodes.new("ShaderNodeTexWave"); w.bands_direction = ax; w.inputs["Scale"].default_value = sc; w.wave_profile = "SAW"
        nt.links.new(tc.outputs["Object"], w.inputs["Vector"])
        cr = nt.nodes.new("ShaderNodeValToRGB"); e = cr.color_ramp.elements
        e[0].position = 0.0; e[0].color = (0.08, 0.18, 0.10, 1); e[1].position = 0.55; e[1].color = (0.05, 0.10, 0.22, 1)
        x = e.new(0.82); x.color = (0.45, 0.06, 0.06, 1); y = e.new(0.9); y.color = (0.85, 0.75, 0.4, 1)
        cr.color_ramp.interpolation = "CONSTANT"
        nt.links.new(w.outputs["Fac"], cr.inputs["Fac"]); cols.append(cr.outputs["Color"])
    mx = nt.nodes.new("ShaderNodeMix"); mx.data_type = "RGBA"; mx.inputs["Factor"].default_value = 0.5
    nt.links.new(cols[0], mx.inputs["A"]); nt.links.new(cols[1], mx.inputs["B"])
    nt.links.new(mx.outputs["Result"], b.inputs["Base Color"])
    b.inputs["Roughness"].default_value = 0.9; b.inputs["Sheen Weight"].default_value = 0.5
    nz = nt.nodes.new("ShaderNodeTexWave"); nz.inputs["Scale"].default_value = 300
    nt.links.new(tc.outputs["Object"], nz.inputs["Vector"])
    bp = nt.nodes.new("ShaderNodeBump"); bp.inputs["Strength"].default_value = 0.1
    nt.links.new(nz.outputs["Fac"], bp.inputs["Height"]); nt.links.new(bp.outputs["Normal"], b.inputs["Normal"])
    M._aov(nt, 0.0)
    return m


def bottom_kilt(ctx):
    Z = zs(ctx); s, h = ctx.s, ctx.h
    t = tartan("PL_Tartan")
    G.skirt(ctx, "kilt", Z["waist"], Z["knee"] - 0.01 * h, (0.21 * s, 0.19 * s), t, folds=26, fold_amp=0.009 * s, expo=1.1)
    hose = M.cloth("PL_KiltHose", (0.78, 0.74, 0.64), "knit")
    o = G.shell(ctx, "kilt_hose", legs(ctx, Z["ankle"] + 0.01 * h, Z["knee"] - 0.04 * h), hose, offset=0.008, thick=0.003)
    G.hem(ctx, o, hose, r=0.0055 * s)
    belt(ctx, Z["waist"], M.cloth("PL_BeltDark", (0.18, 0.11, 0.06), "leather"), M.metal("PL_BuckleIron", tint=0.0), grow=0.028)


def bottom_noble_hose(ctx):
    Z = zs(ctx); s, h = ctx.s, ctx.h
    hose = M.cloth("PL_HoseBlack", (0.05, 0.05, 0.06), "silk")
    G.shell(ctx, "noble_hose", legs(ctx, Z["ankle"] + 0.008 * h, Z["hip"] - 0.03 * h), hose, offset=0.007, thick=0.003)
    vel = M.cloth("PL_TrunkVelvet", (0.10, 0.08, 0.20), "velvet")
    th = G.shell(ctx, "trunk_hose", legs(ctx, Z["hip"] - 0.11 * h, Z["waist"] + 0.01 * h), vel, offset=0.026, thick=0.006)
    G.hem(ctx, th, M.gold("PL_Gold"), r=0.004 * s)


# ------------------------------------------------------------------ SHOES
def _boot(ctx, name, top_frac, mat, cuff_mat=None, sole=None, toe_round=1.0, fur=False):
    s, h, J = ctx.s, ctx.h, ctx.J
    sole = sole or M.cloth("PL_Sole", (0.08, 0.06, 0.05), "leather")
    V = ctx.body.data.vertices
    for side, sx in (("L", 1), ("R", -1)):
        foot = [V[i].co for i in range(len(V)) if (not ctx.mask[i]) and V[i].co.x * sx > 0 and V[i].co.z < 0.05 * h]
        fx0, fx1 = min(p.x for p in foot), max(p.x for p in foot)
        fy0, fy1 = min(p.y for p in foot), max(p.y for p in foot)
        cx, cy = (fx0 + fx1) / 2, (fy0 + fy1) / 2
        hx, hy = (fx1 - fx0) / 2 + 0.012 * s, (fy1 - fy0) / 2 + 0.014 * s
        bm = bmesh.new(); bmesh.ops.create_uvsphere(bm, u_segments=32, v_segments=16, radius=1.0)
        for v in bm.verts:
            x, y, z = v.co
            v.co = Vector((cx + x * hx * (1.0 + 0.10 * max(0, -y) * toe_round), cy + y * hy, max(0.0, z) * 0.072 * s * (1 - 0.35 * max(0, -y)) + 0.012 * s))
            if v.co.z < 0.012 * s:
                v.co.z = 0.012 * s
        fo = C.obj_from_bm(bm, f"{name}_foot{side}", mat, ctx.col); G.rigid(ctx, fo, f"foot_{side}")
        so = C.box(f"{name}_sole{side}", (2 * hx + 0.006, 2 * hy + 0.008, 0.014 * s), (cx, cy, 0.007 * s), sole, ctx.col, bevel=0.005)
        G.rigid(ctx, so, f"foot_{side}")
        hl = C.box(f"{name}_heel{side}", (2 * hx * 0.8, 0.06 * s, 0.026 * s), (cx, fy1 - 0.018 * s, 0.013 * s), sole, ctx.col, bevel=0.004)
        G.rigid(ctx, hl, f"foot_{side}")
    if top_frac > 0.06:
        z0 = 0.045 * h
        o = G.shell(ctx, f"{name}_shaft", lambda v: (not ctx.mask[v.index]) and z0 < v.co.z < top_frac * h, mat, offset=0.014, thick=0.005)
        if cuff_mat is not None:
            G.ring_band(ctx, f"{name}_cuffL", top_frac * h - 0.006 * h, cuff_mat, r=(0.016 if fur else 0.009) * s, grow=0.02 * s) if False else None
            G.hem(ctx, o, cuff_mat, r=(0.014 if fur else 0.007) * s, skip=lambda pts: sum(p.z for p in pts) / len(pts) < 0.08 * h)


def shoes_leather(ctx):
    _boot(ctx, "shoe", 0.075, M.cloth("PL_ShoeLeather", (0.30, 0.18, 0.09), "leather"))


def boots_riding(ctx):
    _boot(ctx, "riding", 0.27, M.cloth("PL_RidingBoot", (0.10, 0.07, 0.05), "leather"), cuff_mat=M.cloth("PL_RidingCuff", (0.32, 0.20, 0.10), "leather"))


def boots_fur(ctx):
    _boot(ctx, "furboot", 0.20, M.cloth("PL_FurBoot", (0.36, 0.24, 0.14), "suede"), cuff_mat=M.cloth("PL_Fur", (0.80, 0.74, 0.64), "fur"), fur=True)


def sandals(ctx):
    s, h = ctx.s, ctx.h
    lea = M.cloth("PL_SandalLeather", (0.48, 0.30, 0.14), "leather")
    V = ctx.body.data.vertices
    for side, sx in (("L", 1), ("R", -1)):
        foot = [V[i].co for i in range(len(V)) if (not ctx.mask[i]) and V[i].co.x * sx > 0 and V[i].co.z < 0.05 * h]
        fx0, fx1 = min(p.x for p in foot), max(p.x for p in foot); fy0, fy1 = min(p.y for p in foot), max(p.y for p in foot)
        so = C.box(f"sandal_sole{side}", (fx1 - fx0 + 0.012, fy1 - fy0 + 0.014, 0.012 * s), ((fx0 + fx1) / 2, (fy0 + fy1) / 2, 0.006 * s), lea, ctx.col, bevel=0.004)
        G.rigid(ctx, so, f"foot_{side}")
    for k, zf in enumerate((0.022, 0.034, 0.055, 0.075)):
        G.shell(ctx, f"sandal_strap{k}", lambda v, zf=zf: (not ctx.mask[v.index]) and abs(v.co.z - zf * h) < 0.006 * h and v.co.z < 0.09 * h,
                lea, offset=0.006, thick=0.003)


# ------------------------------------------------------------------ OUTFITS (full)
def outfit_mage_robe(ctx):
    Z = zs(ctx); s, h = ctx.s, ctx.h
    robe = M.cloth("PL_MageBlue", (0.10, 0.14, 0.40), "velvet", color2=(0.07, 0.09, 0.28))
    G.shell(ctx, "robe_top", either(torso(ctx, Z["waist"] - 0.02 * h, Z["neck"]), arms(ctx, Z["wrist"] + 0.005 * h)), robe, offset=0.016, thick=0.005)
    # bell sleeves
    for side, sx in (("L", 1), ("R", -1)):
        wr = ctx.J[f"wrist_{side}"]; el = ctx.J[f"elbow_{side}"]
        d = (wr - el).normalized()
        sl = C.cyl(f"bell{side}", 0.045 * s, 0.14 * s, wr - d * 0.05, segs=24, mat=robe, col=ctx.col, r2=0.075 * s, caps=False)
        sl.rotation_euler = (-d).to_track_quat("Z", "Y").to_euler()
        sl.modifiers.new("Sol", "SOLIDIFY").thickness = 0.004
        G.bound(ctx, sl)
        G.bound(ctx, C.torus(f"bell_trim{side}", 0.075 * s, 0.004 * s, wr + d * 0.02 * s, mat=M.gold("PL_Gold"), col=ctx.col,
                             rot=(-d).to_track_quat("Z", "Y").to_euler()))
    G.skirt(ctx, "robe_skirt", Z["waist"] - 0.01 * h, 0.035 * h, (0.33 * s, 0.31 * s), robe, folds=16, fold_amp=0.02 * s)
    goldm = M.gold("PL_Gold")
    G.ring_band(ctx, "robe_hemtrim", 0.04 * h, goldm, r=0.005 * s, grow=0.0) if False else None
    rope = M.cloth("PL_Rope", (0.80, 0.66, 0.30), "canvas")
    G.ring_band(ctx, "rope_belt", Z["waist"] - 0.005 * h, rope, r=0.008 * s, grow=0.03 * s)
    # star embroidery: small gold studs scattered on the chest/skirt front
    rnd = random.Random(5)
    pn = []
    for _ in range(14):
        x = rnd.uniform(-0.09, 0.09) * s; z = rnd.uniform(Z["knee"], Z["chest"])
        p, n = G.surf_pt(ctx, x, z, push=0.03 if z > Z["waist"] else 0.0)
        if p is not None and z > Z["waist"]:
            pn.append((p, n))
    G.studs(ctx, pn, 0.004 * s, goldm, name="star")
    # turned-down hood collar
    hood = G.shell(ctx, "hood_collar", lambda v: (not ctx.mask[v.index]) and Z["shoulder"] - 0.02 * h < v.co.z < Z["neck"] + 0.01 * h and v.co.y > -0.04 * s,
                   robe, offset=0.03, thick=0.006)
    G.hem(ctx, hood, goldm, r=0.004 * s)


def outfit_noble(ctx):
    Z = zs(ctx); s, h = ctx.s, ctx.h
    goldm = M.gold("PL_Gold")
    if ctx.kind == "male":
        coat = M.cloth("PL_NobleCoat", (0.06, 0.16, 0.12), "velvet")
        o = G.shell(ctx, "coat", either(torso(ctx, Z["waist"] - 0.02 * h, Z["neck"] + 0.02 * h, 0.0), arms(ctx, Z["wrist"] + 0.01 * h)), coat, offset=0.02, thick=0.006)
        G.hem(ctx, o, goldm, r=0.0045 * s)
        G.skirt(ctx, "coat_skirt", Z["waist"] - 0.01 * h, Z["knee"] + 0.07 * h, (0.21 * s, 0.19 * s), coat, folds=10, fold_amp=0.012 * s, expo=1.1)
        buttons(ctx, [Z["waist"] + k * 0.04 * h for k in range(6)], goldm, r=0.006, push=0.03)
        hose = M.cloth("PL_NobleHose", (0.88, 0.86, 0.80), "silk")
        G.shell(ctx, "nob_hose", legs(ctx, Z["ankle"] + 0.008 * h, Z["knee"]), hose, offset=0.007, thick=0.003)
        cr = M.cloth("PL_Cravat", (0.95, 0.94, 0.90), "silk")
        p, n = G.surf_pt(ctx, 0, Z["shoulder"] - 0.01 * h, push=0.03)
        if p is not None:
            for k in range(3):
                G.bound(ctx, C.uvsphere(f"cravat{k}", 0.018 * s, p + Vector((0, -0.004, -k * 0.02 * s)), segs=14, rings=8, mat=cr, col=ctx.col, scale=(1.3, 0.6, 1.0)))
    else:
        gown = M.cloth("PL_Gown", (0.42, 0.06, 0.20), "silk")
        bod = G.shell(ctx, "bodice", either(torso(ctx, Z["waist"] - 0.02 * h, Z["shoulder"] + 0.01 * h), arms(ctx, Z["elbow"] - 0.02 * h)), gown, offset=0.012, thick=0.004)
        G.hem(ctx, bod, goldm, r=0.0035 * s)
        G.skirt(ctx, "gown_skirt", Z["waist"] - 0.01 * h, 0.012 * h, (0.40 * s, 0.38 * s), gown, folds=18, fold_amp=0.024 * s, train=0.05 * s)
        under = M.cloth("PL_GownLace", (0.94, 0.90, 0.84), "silk")
        for side, sx in (("L", 1), ("R", -1)):
            wr = ctx.J[f"wrist_{side}"]; el = ctx.J[f"elbow_{side}"]; d = (wr - el).normalized()
            sl = C.cyl(f"lace_sleeve{side}", 0.035 * s, 0.10 * s, el + d * 0.02, segs=20, mat=under, col=ctx.col, r2=0.055 * s, caps=False)
            sl.rotation_euler = (-d).to_track_quat("Z", "Y").to_euler(); sl.modifiers.new("Sol", "SOLIDIFY").thickness = 0.003
            G.bound(ctx, sl)
        laces(ctx, Z["waist"] + 0.01 * h, Z["chest"] + 0.02 * h, goldm, n=5, w=0.02)
        G.ring_band(ctx, "gown_waist", Z["waist"] - 0.005 * h, goldm, r=0.005 * s, grow=0.016 * s)


def outfit_hunter(ctx):
    Z = zs(ctx); s, h = ctx.s, ctx.h
    lea = M.cloth("PL_HunterLeather", (0.30, 0.19, 0.10), "leather")
    dark = M.cloth("PL_HunterDark", (0.16, 0.12, 0.08), "suede")
    o = G.shell(ctx, "hunter_top", either(torso(ctx, Z["hip"] - 0.06 * h, Z["neck"] + 0.01 * h, 0.0), arms(ctx, Z["wrist"] + 0.02 * h)), lea, offset=0.018, thick=0.006)
    G.hem(ctx, o, dark, r=0.0055 * s, stitch_mat=M.stitch("PL_StitchTan", (0.78, 0.62, 0.40)))
    o2 = G.shell(ctx, "hunter_legs", legs(ctx, Z["ankle"] + 0.02 * h, Z["waist"]), dark, offset=0.012, thick=0.004)
    G.hem(ctx, o2, dark, r=0.004 * s)
    belt(ctx, Z["waist"], M.cloth("PL_BeltDark", (0.18, 0.11, 0.06), "leather"), M.metal("PL_BuckleIron", tint=0.0), grow=0.03)
    # shoulder mantle + quiver strap
    G.shell(ctx, "mantle", lambda v: (not ctx.mask[v.index]) and Z["shoulder"] - 0.06 * h < v.co.z < Z["neck"] + 0.005 * h, dark, offset=0.03, thick=0.006)
    pts = []
    for t in (0.0, 0.25, 0.5, 0.75, 1.0):
        x = (0.10 - 0.22 * t) * s; z = Z["shoulder"] + 0.01 * h - (Z["shoulder"] - Z["waist"] + 0.02 * h) * t
        p, n = G.surf_pt(ctx, x, z, push=0.034)
        if p is not None:
            pts.append(p)
    if len(pts) >= 3:
        G.bound(ctx, G.tube_mesh("hunter_strap", pts, 0.006 * s, lea, ctx.col))


def outfit_festival(ctx):
    Z = zs(ctx); s, h = ctx.s, ctx.h
    red = M.cloth("PL_FestRed", (0.62, 0.08, 0.06), "linen")
    gold_c = M.cloth("PL_FestGold", (0.85, 0.62, 0.15), "silk")
    if ctx.kind == "female":
        o = G.shell(ctx, "fest_bodice", either(torso(ctx, Z["waist"] - 0.02 * h, Z["shoulder"]), arms(ctx, Z["elbow"] + 0.02 * h)), red, offset=0.012)
        G.hem(ctx, o, gold_c, r=0.005 * s)
        G.skirt(ctx, "fest_skirt", Z["waist"] - 0.01 * h, Z["knee"] - 0.08 * h, (0.36 * s, 0.34 * s), red, folds=16, fold_amp=0.03 * s, expo=0.9)
        G.skirt(ctx, "fest_petticoat", Z["waist"] - 0.03 * h, Z["knee"] - 0.11 * h, (0.33 * s, 0.31 * s), M.cloth("PL_FestWhite", (0.95, 0.93, 0.88), "silk"), folds=22, fold_amp=0.02 * s, expo=0.9)
    else:
        o = G.shell(ctx, "fest_tunic", either(torso(ctx, Z["hip"] - 0.08 * h, Z["neck"]), arms(ctx, Z["wrist"] + 0.03 * h)), red, offset=0.014)
        G.hem(ctx, o, gold_c, r=0.006 * s, stitch_mat=M.stitch("PL_StitchGold", (0.85, 0.70, 0.35)))
        o2 = G.shell(ctx, "fest_legs", legs(ctx, Z["ankle"] + 0.02 * h, Z["waist"]), M.cloth("PL_FestLegs", (0.90, 0.86, 0.76), "linen"), offset=0.011)
    # diagonal sash
    pts = []
    for t in (0.0, 0.25, 0.5, 0.75, 1.0):
        x = (-0.10 + 0.20 * t) * s; z = Z["shoulder"] - (Z["shoulder"] - Z["waist"] + 0.04 * h) * t
        p, n = G.surf_pt(ctx, x, z, push=0.03)
        if p is not None:
            pts.append(p)
    if len(pts) >= 3:
        G.bound(ctx, G.tube_mesh("sash", pts, 0.011 * s, gold_c, ctx.col))


# ------------------------------------------------------------------ ACCESSORIES
def acc_travel_cloak(ctx):
    Z = zs(ctx); s, h = ctx.s, ctx.h
    wool = M.cloth("PL_CloakWool", (0.20, 0.17, 0.14), "wool", color2=(0.17, 0.14, 0.11))
    # cloak: back half-skirt hanging from the shoulders (procedural, weighted to chest/spine)
    x0, x1, y0, y1 = H.section(ctx.body, Z["shoulder"] - 0.02 * h, ctx.mask, tol=0.015)
    rows = []
    for i in range(29):
        t = i / 28
        z = Z["neck"] - 0.01 * h - t * (Z["neck"] - 0.13 * h)
        rx = (x1 - x0) / 2 + 0.03 * s + 0.11 * s * t ** 0.8
        ry = (y1 - y0) / 2 + 0.03 * s + 0.08 * s * t ** 0.8
        cy = (y0 + y1) / 2 + 0.01 * s + 0.03 * t
        row = []
        for j in range(41):
            a = math.radians(-15 + 210 * j / 40)
            fr = 0.012 * s * t * math.sin(9 * a)
            row.append(Vector(((rx + fr) * math.cos(a), cy + (ry + fr) * math.sin(a), z)))
        rows.append(row)
    bm = bmesh.new()
    grid = [[bm.verts.new(p) for p in r] for r in rows]
    for i in range(len(grid) - 1):
        for j in range(len(grid[0]) - 1):
            bm.faces.new((grid[i][j], grid[i][j + 1], grid[i + 1][j + 1], grid[i + 1][j]))
    cl = C.obj_from_bm(bm, "cloak", wool, ctx.col)
    cl.modifiers.new("Sol", "SOLIDIFY").thickness = 0.006
    C.add_mod_subsurf(cl, 1)

    def ov(co):
        t = max(0.0, min(1.0, (Z["neck"] - co.z) / (Z["neck"] - Z["waist"])))
        return {"chest": 1.0 - 0.4 * t, "spine": 0.4 * t}
    R.bind(cl, ctx.arm, ctx.bw, override=ov); ctx.add(cl)
    G.hem(ctx, cl, M.cloth("PL_CloakTrim", (0.12, 0.10, 0.08), "wool"), r=0.006 * s, stitch_mat=M.stitch("PL_StitchCream", (0.70, 0.64, 0.50)))
    hood = G.shell(ctx, "cloak_hood", lambda v: (not ctx.mask[v.index]) and Z["shoulder"] - 0.01 * h < v.co.z < Z["neck"] + 0.03 * h and v.co.y > -0.02 * s,
                   wool, offset=0.04, thick=0.007)
    p, n = G.surf_pt(ctx, 0.07 * s, Z["shoulder"] + 0.0 * h, push=0.035)
    if p is not None:
        br = C.cyl("brooch", 0.014 * s, 0.006 * s, p, segs=20, mat=M.gold("PL_Gold"), col=ctx.col)
        br.rotation_euler = (math.radians(90), 0, 0); G.bound(ctx, br)


def acc_scarf(ctx):
    Z = zs(ctx); s, h = ctx.s, ctx.h
    knit = M.cloth("PL_ScarfKnit", (0.62, 0.16, 0.12), "knit")
    sc = G.shell(ctx, "scarf", lambda v: (not ctx.mask[v.index]) and Z["shoulder"] - 0.005 * h < v.co.z < Z["neck"] + 0.012 * h, knit, offset=0.024, thick=0.012, subsurf=2)
    p, n = G.surf_pt(ctx, 0.03 * s, Z["shoulder"] - 0.02 * h, push=0.034)
    if p is not None:
        for k in range(2):
            t = C.box(f"scarf_tail{k}", (0.045 * s, 0.012 * s, 0.17 * s), p + Vector((k * 0.03 * s, -0.004 * k, -0.08 * s)), knit, ctx.col, bevel=0.008,
                      rot=(math.radians(-6), 0, math.radians(6 - 12 * k)))
            G.bound(ctx, t)


def acc_satchel(ctx):
    Z = zs(ctx); s, h = ctx.s, ctx.h
    lea = M.cloth("PL_SatchelLeather", (0.40, 0.24, 0.12), "leather")
    x0, x1, y0, y1 = H.section(ctx.body, Z["hip"] + 0.02 * h, ctx.mask, tol=0.012)
    sx = x0 - 0.035 * s
    pts = []
    for t in (0.0, 0.2, 0.4, 0.6, 0.8, 1.0):
        x = (0.11 - (0.11 + abs(sx) * 0.9) * t) * s / s
        z = Z["shoulder"] + 0.015 * h - (Z["shoulder"] - Z["hip"]) * t
        p, n = G.surf_pt(ctx, x, z, push=0.03)
        if p is not None:
            pts.append(p)
    G.bound(ctx, G.tube_mesh("satchel_strap", pts, 0.008 * s, lea, ctx.col))
    pts_b = [Vector((0.11 * s, 0.03, Z["shoulder"] + 0.02 * h)), Vector((0.02, (y1 + 0.03), Z["chest"])), Vector((sx * 0.9, y1, Z["hip"] + 0.05 * h))]
    G.bound(ctx, G.tube_mesh("satchel_strap_b", pts_b, 0.008 * s, lea, ctx.col))
    bag = C.box("satchel", (0.06 * s, 0.17 * s, 0.14 * s), (sx - 0.015 * s, (y0 + y1) / 2, Z["hip"] - 0.03 * h), lea, ctx.col, bevel=0.012)
    G.bound(ctx, bag)
    flap = C.box("satchel_flap", (0.066 * s, 0.172 * s, 0.07 * s), (sx - 0.018 * s, (y0 + y1) / 2, Z["hip"] + 0.005 * h), lea, ctx.col, bevel=0.01)
    G.bound(ctx, flap)
    G.bound(ctx, C.box("satchel_buckle", (0.008 * s, 0.03 * s, 0.025 * s), (sx - 0.052 * s, (y0 + y1) / 2, Z["hip"] - 0.012 * h), M.gold("PL_Brass", tint=0.0), ctx.col, bevel=0.002))


def acc_leather_gloves(ctx):
    Z = zs(ctx); s, h = ctx.s, ctx.h
    lea = M.cloth("PL_Gloves", (0.22, 0.13, 0.07), "leather")
    for side, sx in (("L", 1), ("R", -1)):
        wz = ctx.J[f"wrist_{side}"].z
        o = G.shell(ctx, f"glove{side}", lambda v, sx=sx, wz=wz: ctx.mask[v.index] and v.co.x * sx > 0 and v.co.z < wz + 0.04 * h, lea, offset=0.004, thick=0.002)
        G.hem(ctx, o, M.cloth("PL_GloveCuff", (0.14, 0.08, 0.04), "leather"), r=0.005 * s)


# ------------------------------------------------------------------ ARMOUR (neutral steel; tier tint at runtime)
def _steel():
    return M.metal("PL_Steel", base=(0.66, 0.67, 0.70), rough=0.22, tint=1.0)


def _mail():
    m, nt = M._nt("PL_Mail")
    if nt is None:
        return m
    M.metal("PL_Mail_x")
    b = nt.nodes["Principled BSDF"]
    b.inputs["Base Color"].default_value = (0.55, 0.56, 0.58, 1); b.inputs["Metallic"].default_value = 1.0; b.inputs["Roughness"].default_value = 0.38
    tc = nt.nodes.new("ShaderNodeTexCoord")
    vo = nt.nodes.new("ShaderNodeTexVoronoi"); vo.feature = "DISTANCE_TO_EDGE"; vo.inputs["Scale"].default_value = 160
    nt.links.new(tc.outputs["Object"], vo.inputs["Vector"])
    cr = nt.nodes.new("ShaderNodeValToRGB"); cr.color_ramp.elements[0].position = 0.0; cr.color_ramp.elements[1].position = 0.12
    nt.links.new(vo.outputs["Distance"], cr.inputs["Fac"])
    bp = nt.nodes.new("ShaderNodeBump"); bp.inputs["Strength"].default_value = 0.9; bp.inputs["Distance"].default_value = 0.002
    nt.links.new(cr.outputs["Color"], bp.inputs["Height"]); nt.links.new(bp.outputs["Normal"], b.inputs["Normal"])
    dk = nt.nodes.new("ShaderNodeMix"); dk.data_type = "RGBA"; dk.blend_type = "MULTIPLY"; dk.inputs["Factor"].default_value = 0.7
    dk.inputs["A"].default_value = (0.58, 0.59, 0.61, 1); nt.links.new(cr.outputs["Color"], dk.inputs["B"])
    nt.links.new(dk.outputs["Result"], b.inputs["Base Color"])
    M._aov(nt, 1.0)
    return m


def arm_helm(ctx):
    s, h = ctx.s, ctx.h
    hi = HR.head_info(ctx)
    st = _steel(); lea = M.cloth("PL_ArmLeather", (0.26, 0.15, 0.07), "leather")
    c = hi["c"]
    rx = hi["xr"] + 0.022 * s; ry = (hi["back"] - hi["front"]) / 2 + 0.018 * s; rz = (hi["top"] - hi["ez"]) + 0.02 * s
    bm = bmesh.new(); bmesh.ops.create_uvsphere(bm, u_segments=40, v_segments=20, radius=1.0)
    cut = []
    for v in bm.verts:
        x, y, z = v.co
        v.co = Vector((c.x + x * rx, c.y + y * ry, hi["ez"] + 0.012 * s + max(z, -0.25) * rz))
    # rim: brow height at the front, dropping to the nape at the back
    def rim(v):
        back = max(0.0, (v.co.y - c.y) / ry)
        return hi["ez"] + 0.030 * s - 0.05 * s * back
    bmesh.ops.delete(bm, geom=[f for f in bm.faces if all(v.co.z < rim(v) for v in f.verts)], context="FACES")
    dome = C.obj_from_bm(bm, "helm_dome", st, ctx.col)
    dome.modifiers.new("Sol", "SOLIDIFY").thickness = 0.004
    C.add_mod_subsurf(dome, 1)
    G.rigid(ctx, dome, "head")
    G.hem(ctx, dome, st, r=0.004 * s, min_len=8)
    # crest ridge + nasal + brow band rivets
    pts = [Vector((0, c.y + ry * math.cos(a), hi["ez"] + rz * math.sin(a) + 0.004)) for a in [math.radians(x) for x in range(-80, 260, 20)]
           if hi["ez"] + rz * math.sin(a) > hi["ez"] + 0.02 * s]
    G.rigid(ctx, G.tube_mesh("helm_crest", pts, 0.005 * s, st, ctx.col), "head")
    nas = C.box("helm_nasal", (0.014 * s, 0.006 * s, 0.065 * s), (0, hi["front"] - 0.016 * s, hi["ez"] + 0.004 * s), st, ctx.col, bevel=0.002)
    G.rigid(ctx, nas, "head")
    for k in range(10):
        a = math.radians(-75 + k * 16.6)
        p = Vector((c.x + math.sin(a) * rx * 1.0, c.y - math.cos(a) * ry * 1.0, hi["ez"] + 0.042 * s - 0.05 * s * max(0.0, -math.cos(a)) + 0.0))
        o = C.uvsphere(f"helm_rivet{k}", 0.0042 * s, p, segs=10, rings=6, mat=st, col=ctx.col)
        G.rigid(ctx, o, "head")
    # mail aventail (covers neck + nape, so hair never needs to show under the helm)
    av = G.shell(ctx, "aventail", lambda v: (not ctx.mask[v.index]) and zs(ctx)["shoulder"] - 0.01 * h < v.co.z < hi["ez"] + 0.005 * s
                 and not (v.co.y < c.y - 0.01 * s and v.co.z > hi["ez"] - 0.11 * s and abs(v.co.x) < 0.075 * s), _mail(), offset=0.02, thick=0.004)
    strap = G.tube_mesh("helm_strap", [Vector((rx * 0.95, c.y - 0.01, hi["ez"] - 0.0)), Vector((0.03 * s, hi["front"] + 0.06 * s, hi["ez"] - 0.11 * s)),
                                       Vector((-0.03 * s, hi["front"] + 0.06 * s, hi["ez"] - 0.11 * s)), Vector((-rx * 0.95, c.y - 0.01, hi["ez"]))], 0.003 * s, lea, ctx.col)
    G.rigid(ctx, strap, "head")


def cuirass(ctx, z0, z1, mat, rows=26, cols=64, off=0.034, ridge=0.012):
    s = ctx.s
    secs = []
    for i in range(rows + 1):
        z = z0 + (z1 - z0) * i / rows
        x0, x1, y0, y1 = H.section(ctx.body, z, ctx.mask, tol=0.01)
        secs.append([z, (x1 - x0) / 2, (y0 + y1) / 2, (y1 - y0) / 2])
    # smooth the profile so the plate reads as one convex form
    for _ in range(6):
        for i in range(1, rows):
            for j in (1, 2, 3):
                secs[i][j] = 0.25 * secs[i - 1][j] + 0.5 * secs[i][j] + 0.25 * secs[i + 1][j]
    bm = bmesh.new(); grid = []
    for i, (z, rx, cy, ry) in enumerate(secs):
        u = i / rows
        top = max(0.0, (u - 0.80) / 0.20)                 # roll the top edge inward toward the neck
        rxx = (rx + off * s) * (1 - 0.30 * top ** 1.5)
        ryy = (ry + off * s) * (1 - 0.15 * top ** 1.5)
        row = []
        for j in range(cols):
            a = 2 * math.pi * j / cols
            ca, sa = math.cos(a), math.sin(a)
            e = 2.6
            x = rxx * math.copysign(abs(ca) ** (2 / e), ca)
            y = ryy * math.copysign(abs(sa) ** (2 / e), sa)
            if y < 0:                                       # front: medial ridge
                y -= ridge * s * max(0.0, 1 - abs(x) / (0.55 * rxx)) * (0.6 + 0.4 * math.sin(math.pi * min(1, u * 1.2)))
            row.append(bm.verts.new((x, cy + y, z)))
        grid.append(row)
    for i in range(rows):
        for j in range(cols):
            bm.faces.new((grid[i][j], grid[i][(j + 1) % cols], grid[i + 1][(j + 1) % cols], grid[i + 1][j]))
    # armholes: drop faces at the sides near the top
    kill = [f for f in bm.faces if all(abs(v.co.x) > 0.62 * max(secs[-1][1], 0.1) and v.co.z > z1 - (z1 - z0) * 0.42 for v in f.verts)]
    bmesh.ops.delete(bm, geom=kill, context="FACES")
    o = C.obj_from_bm(bm, "cuirass", mat, ctx.col)
    o.modifiers.new("Sol", "SOLIDIFY").thickness = 0.004
    C.add_mod_subsurf(o, 1)
    return G.bound(ctx, o)


def arm_platebody(ctx):
    Z = zs(ctx); s, h = ctx.s, ctx.h
    st = _steel(); lea = M.cloth("PL_ArmLeather", (0.26, 0.15, 0.07), "leather")
    gam = M.cloth("PL_ArmGambeson", (0.36, 0.10, 0.08), "canvas")
    # arming jacket sleeves under the plate
    G.shell(ctx, "pb_sleeve", arms(ctx, Z["wrist"] + 0.04 * h), gam, offset=0.012)
    # breastplate + backplate: clean convex shell lofted from torso slices (not a muscle cuirass)
    br = cuirass(ctx, Z["waist"] - 0.005 * h, Z["shoulder"] + 0.004 * h, st)
    G.hem(ctx, br, st, r=0.0055 * s, min_len=6)
    G.rivets_on_loop(ctx, br, st, r=0.0042 * s, every=0.05 * s, min_len=6)
    # gorget + faulds as real plate lames (hemmed shells)
    g = G.shell(ctx, "gorget", lambda v: (not ctx.mask[v.index]) and Z["shoulder"] - 0.005 * h < v.co.z < Z["neck"] + 0.005 * h, st, offset=0.03, thick=0.004, folds=0)
    G.hem(ctx, g, st, r=0.004 * s)
    for k in range(3):
        z1 = Z["waist"] + 0.004 * h - k * 0.028 * h; z0 = z1 - 0.034 * h
        f = G.shell(ctx, f"fauld{k}", lambda v, z0=z0, z1=z1: (not ctx.mask[v.index]) and z0 < v.co.z < z1, st, offset=0.040 + 0.005 * k, thick=0.004, folds=0)
        G.hem(ctx, f, st, r=0.0038 * s)
        G.rivets_on_loop(ctx, f, st, r=0.0035 * s, every=0.06 * s)
    # pauldrons (3 lames per shoulder) + rerebrace + couter + vambrace
    for side, sx in (("L", 1), ("R", -1)):
        S = ctx.J[f"shoulder_{side}"]
        for k in range(3):
            o = C.uvsphere(f"pauldron{side}{k}", (0.088 - 0.011 * k) * s, S + Vector((sx * (0.01 + 0.012 * k) * s, 0, (0.012 - 0.03 * k) * s)),
                           segs=24, rings=12, mat=st, col=ctx.col, scale=(0.95, 1.05, 0.62))
            bm = bmesh.new(); bm.from_mesh(o.data)
            bmesh.ops.delete(bm, geom=[f for f in bm.faces if all(v.co.z < -0.15 for v in f.verts)], context="FACES")
            bm.to_mesh(o.data); bm.free()
            o.modifiers.new("Sol", "SOLIDIFY").thickness = 0.004
            G.rigid(ctx, o, f"upper_arm_{side}")
        G.rigid(ctx, C.uvsphere(f"paul_rivet{side}", 0.006 * s, S + Vector((sx * 0.03 * s, -0.05 * s, 0.03 * s)), segs=10, rings=6, mat=st, col=ctx.col), f"upper_arm_{side}")
        E = ctx.J[f"elbow_{side}"]
        cou = C.uvsphere(f"couter{side}", 0.035 * s, E + Vector((sx * 0.008, 0.02 * s, 0)), segs=20, rings=10, mat=st, col=ctx.col, scale=(1.0, 0.8, 1.0))
        G.rigid(ctx, cou, f"forearm_{side}")
        for nm, lo, hi_ in (("rere", Z["elbow"] + 0.025 * h, Z["shoulder"] - 0.06 * h), ("vamb", Z["wrist"] + 0.03 * h, Z["elbow"] - 0.02 * h)):
            G.shell(ctx, f"{nm}{side}", lambda v, sx=sx, lo=lo, hi_=hi_: ctx.mask[v.index] and v.co.x * sx > 0 and lo < v.co.z < hi_, st, offset=0.024, thick=0.004)
    # side straps (leather) with buckles
    for side, sx in (("L", 1), ("R", -1)):
        for k in range(2):
            z = Z["chest"] - (0.02 + 0.06 * k) * h
            x0, x1, y0, y1 = H.section(ctx.body, z, ctx.mask, tol=0.012)
            xe = (x1 if sx > 0 else x0) + sx * 0.03 * s
            G.bound(ctx, G.tube_mesh(f"pb_strap{side}{k}", [Vector((xe - sx * 0.01, y0 * 0.5, z)), Vector((xe + sx * 0.004, (y0 + y1) / 2, z)), Vector((xe - sx * 0.01, y1 * 0.5, z))], 0.006 * s, lea, ctx.col))


def arm_chainbody(ctx):
    Z = zs(ctx); s, h = ctx.s, ctx.h
    mail = _mail(); lea = M.cloth("PL_ArmLeather", (0.26, 0.15, 0.07), "leather")
    o = G.shell(ctx, "hauberk", either(torso(ctx, Z["hip"] - 0.03 * h, Z["neck"] + 0.01 * h, 0.0), arms(ctx, Z["elbow"] - 0.03 * h)), mail, offset=0.018, thick=0.004)
    G.skirt(ctx, "hauberk_skirt", Z["hip"] - 0.01 * h, Z["knee"] + 0.06 * h, (0.21 * s, 0.19 * s), mail, folds=10, fold_amp=0.008 * s, expo=1.2)
    G.hem(ctx, o, M.cloth("PL_MailEdge", (0.24, 0.14, 0.07), "leather"), r=0.005 * s)
    belt(ctx, Z["waist"], lea, M.metal("PL_BuckleIron2", tint=1.0), grow=0.03)


def arm_platelegs(ctx):
    Z = zs(ctx); s, h = ctx.s, ctx.h
    st = _steel(); lea = M.cloth("PL_ArmLeather", (0.26, 0.15, 0.07), "leather")
    hose = M.cloth("PL_ArmHose", (0.20, 0.17, 0.15), "wool")
    G.shell(ctx, "arming_hose", legs(ctx, Z["ankle"] + 0.01 * h, Z["waist"] + 0.01 * h), hose, offset=0.010, thick=0.003)
    for side, sx in (("L", 1), ("R", -1)):
        cu = G.shell(ctx, f"cuisse{side}", lambda v, sx=sx: (not ctx.mask[v.index]) and v.co.x * sx > 0.012 * s and Z["knee"] + 0.04 * h < v.co.z < Z["hip"] - 0.01 * h
                     and v.co.y < 0.02 * s, st, offset=0.028, thick=0.004)
        G.hem(ctx, cu, st, r=0.004 * s); G.rivets_on_loop(ctx, cu, st, r=0.0038 * s, every=0.05 * s)
        gr = G.shell(ctx, f"greave{side}", lambda v, sx=sx: (not ctx.mask[v.index]) and v.co.x * sx > 0 and Z["ankle"] + 0.03 * h < v.co.z < Z["knee"] - 0.03 * h,
                     st, offset=0.026, thick=0.004)
        G.hem(ctx, gr, st, r=0.004 * s)
        K = ctx.J[f"knee_{side}"]
        pol = C.uvsphere(f"poleyn{side}", 0.04 * s, K + Vector((0, -0.035 * s, 0)), segs=20, rings=10, mat=st, col=ctx.col, scale=(1.0, 0.75, 1.0))
        G.rigid(ctx, pol, f"shin_{side}")
        wing = C.uvsphere(f"poleyn_wing{side}", 0.03 * s, K + Vector((sx * 0.035 * s, -0.02 * s, 0)), segs=16, rings=8, mat=st, col=ctx.col, scale=(0.35, 0.9, 1.1))
        G.rigid(ctx, wing, f"shin_{side}")
        G.rigid(ctx, C.uvsphere(f"poleyn_rv{side}", 0.006 * s, K + Vector((0, -0.065 * s, 0)), segs=10, rings=6, mat=st, col=ctx.col), f"shin_{side}")
        # strap around the thigh plate
        z = (Z["knee"] + Z["hip"]) / 2
        G.shell(ctx, f"cuisse_strap{side}", lambda v, sx=sx, z=z: (not ctx.mask[v.index]) and v.co.x * sx > 0 and abs(v.co.z - z) < 0.008 * h, lea, offset=0.034, thick=0.003)
    # tassets: two plates hanging from the waist at the front of each thigh
    for side, sx in (("L", 1), ("R", -1)):
        for k in range(2):
            z = Z["hip"] + 0.02 * h - k * 0.035 * h
            p, n = G.surf_pt(ctx, sx * 0.065 * s, z, push=0.045)
            if p is not None:
                t = C.box(f"tasset{side}{k}", (0.10 * s, 0.006 * s, 0.05 * s), p, st, ctx.col, bevel=0.003, rot=(math.radians(-8), 0, math.radians(-sx * 10)))
                G.bound(ctx, t)


def arm_gauntlets(ctx):
    Z = zs(ctx); s, h = ctx.s, ctx.h
    st = _steel(); lea = M.cloth("PL_GlovePalm", (0.20, 0.12, 0.06), "leather")
    for side, sx in (("L", 1), ("R", -1)):
        wz = ctx.J[f"wrist_{side}"].z
        G.shell(ctx, f"gl_palm{side}", lambda v, sx=sx, wz=wz: ctx.mask[v.index] and v.co.x * sx > 0 and v.co.z < wz + 0.01 * h, lea, offset=0.004, thick=0.002)
        cuff = G.shell(ctx, f"gl_cuff{side}", lambda v, sx=sx, wz=wz: ctx.mask[v.index] and v.co.x * sx > 0 and wz - 0.035 * h < v.co.z < wz + 0.05 * h,
                       st, offset=0.016, thick=0.004)
        G.hem(ctx, cuff, st, r=0.0035 * s)
        # articulated plates: 2 wrist lames, back-of-hand plate, 4 finger lames (rigid to hand / fingers bones)
        B = ctx.arm.data.bones; aw = ctx.arm.matrix_world
        h0, h1 = aw @ B[f"hand_{side}"].head_local, aw @ B[f"hand_{side}"].tail_local
        f0, f1 = aw @ B[f"fingers_{side}"].head_local, aw @ B[f"fingers_{side}"].tail_local
        out = Vector((sx * 0.011 * s, 0, 0))
        for k in range(2):
            p = h0.lerp(h1, 0.05 + 0.18 * k) + out * 0.9
            o = C.uvsphere(f"gl_wl{side}{k}", 0.027 * s, p, segs=18, rings=8, mat=st, col=ctx.col, scale=(0.42, 0.95, 0.42))
            G.rigid(ctx, o, f"hand_{side}")
        p = h0.lerp(h1, 0.62) + out
        o = C.uvsphere(f"gl_back{side}", 0.030 * s, p, segs=18, rings=10, mat=st, col=ctx.col, scale=(0.38, 0.95, 1.05))
        G.rigid(ctx, o, f"hand_{side}")
        for k in range(4):
            p = f0.lerp(f1, 0.08 + 0.24 * k) + out * (0.95 - 0.12 * k)
            o = C.uvsphere(f"gl_fl{side}{k}", 0.022 * s * (1 - 0.1 * k), p, segs=16, rings=8, mat=st, col=ctx.col, scale=(0.40, 0.95, 0.42))
            G.rigid(ctx, o, f"fingers_{side}")


def arm_sabatons(ctx):
    s, h = ctx.s, ctx.h
    st = _steel()
    _boot(ctx, "sabaton", 0.11, st, sole=M.cloth("PL_Sole", (0.08, 0.06, 0.05), "leather"), toe_round=0.6)
    V = ctx.body.data.vertices
    for side, sx in (("L", 1), ("R", -1)):
        A = ctx.J[f"ankle_{side}"]; T = ctx.J[f"toe_{side}"]
        for k in range(4):
            u = 0.2 + 0.2 * k
            p = A.lerp(T, u); p.z = 0.05 * h - 0.008 * h * k
            lame = C.uvsphere(f"sab_lame{side}{k}", 0.045 * s, p, segs=18, rings=8, mat=st, col=ctx.col, scale=(1.0, 0.35, 0.45))
            G.rigid(ctx, lame, f"foot_{side}")


def arm_kiteshield(ctx):
    s, h = ctx.s, ctx.h
    st = _steel()
    face = M.cloth("PL_ShieldFace", (0.50, 0.10, 0.08), "leather")
    E = ctx.J["elbow_L"]; W = ctx.J["wrist_L"]
    c = E.lerp(W, 0.55) + Vector((0.07 * s, -0.04 * s, 0))
    outline = []
    for k in range(25):
        t = k / 24
        a = math.pi * t
        x = math.cos(a) * 0.20 * s
        z = math.sin(a) * 0.12 * s if t <= 1 else 0
        outline.append((x, z))
    pts = [(math.cos(math.pi * k / 16) * 0.20 * s, 0.10 * s + math.sin(math.pi * k / 16) * 0.10 * s) for k in range(17)]
    pts += [(-0.20 * s + 0.20 * s * (1 - (1 - u) ** 1.0) * 0 + (-0.20 * s) * 0, 0.10 * s) for u in []]
    prof = [(0.20 * s, 0.10 * s)] + pts[1:] + [(-0.20 * s, 0.10 * s), (-0.14 * s, -0.18 * s), (0.0, -0.40 * s), (0.14 * s, -0.18 * s)]
    bm = bmesh.new()
    vs = [bm.verts.new((x, -0.04 * s * (1 - (x / (0.2 * s)) ** 2), z)) for x, z in prof]
    f = bm.faces.new(vs)
    bmesh.ops.triangulate(bm, faces=[f])
    o = C.obj_from_bm(bm, "kite", face, ctx.col)
    sub = o.modifiers.new("Rem", "SUBSURF"); sub.levels = 0; sub.render_levels = 0
    o.modifiers.new("Sol", "SOLIDIFY").thickness = 0.012
    rim = G.tube_mesh("kite_rim", [Vector((x, -0.04 * s * (1 - (x / (0.2 * s)) ** 2) - 0.004, z)) for x, z in prof] , 0.008 * s, st, ctx.col, closed=True)
    boss = C.uvsphere("kite_boss", 0.045 * s, (0, -0.05 * s, 0.02 * s), segs=24, rings=12, mat=st, col=ctx.col, scale=(1, 0.55, 1))
    cross = C.box("kite_cross", (0.03 * s, 0.006 * s, 0.42 * s), (0, -0.05 * s, -0.08 * s), st, ctx.col, bevel=0.003)
    cross2 = C.box("kite_cross2", (0.34 * s, 0.006 * s, 0.03 * s), (0, -0.05 * s, 0.07 * s), st, ctx.col, bevel=0.003)
    parts = [o, rim, boss, cross, cross2]
    for k in range(10):
        x, z = prof[min(len(prof) - 1, k * 2)]
        parts.append(C.uvsphere(f"kite_rv{k}", 0.006 * s, (x * 0.9, -0.05 * s, z * 0.9), segs=10, rings=6, mat=st, col=ctx.col))
    piv = bpy.data.objects.new("kite_piv", None); ctx.col.objects.link(piv)
    for p in parts:
        p.parent = piv
    piv.location = c
    piv.rotation_euler = (0, 0, math.radians(55))     # face angled outward-forward
    bpy.context.view_layer.update()
    for p in parts:
        mw = p.matrix_world.copy(); p.parent = None; p.matrix_world = mw
        G.rigid(ctx, p, "forearm_L")
    bpy.data.objects.remove(piv)


# ------------------------------------------------------------------ WEAPONS (blade tint = tier; hafts fixed)
def _prop(ctx, parts, side="R", rot=(0, 0, 0), offset=Vector((0, 0, 0))):
    g = ctx.J[f"grip_{side}"]
    piv = bpy.data.objects.new("wpiv", None); ctx.col.objects.link(piv)
    for p in parts:
        p.parent = piv
    piv.location = g + offset; piv.rotation_euler = rot
    bpy.context.view_layer.update()
    for p in parts:
        mw = p.matrix_world.copy(); p.parent = None; p.matrix_world = mw
        G.rigid(ctx, p, f"prop_{side}")
    bpy.data.objects.remove(piv)


def blade_loft(name, L, w0, th, mat, col, y0=-0.06, taper_from=0.80):
    """Diamond-section blade along -Y: edge bevels + centre ridge, tapering to a point."""
    bm = bmesh.new(); rings = []
    N = 16
    for i in range(N + 1):
        u = i / N
        w = w0 * (1.0 - 0.18 * u) if u < taper_from else w0 * (1.0 - 0.18 * taper_from) * (1 - (u - taper_from) / (1 - taper_from)) ** 0.8
        w = max(w, 0.0004)
        y = y0 - L * u
        rings.append([bm.verts.new(p) for p in ((w, y, 0), (w * 0.55, y, th * 0.5), (0, y, th), (-w * 0.55, y, th * 0.5),
                                                (-w, y, 0), (-w * 0.55, y, -th * 0.5), (0, y, -th), (w * 0.55, y, -th * 0.5))])
    for i in range(N):
        for k in range(8):
            bm.faces.new((rings[i][k], rings[i][(k + 1) % 8], rings[i + 1][(k + 1) % 8], rings[i + 1][k]))
    bm.faces.new(list(reversed(rings[0])))
    o = C.obj_from_bm(bm, name, mat, col, smooth=False)
    return o


def wpn_sword(ctx):
    s = ctx.s; st = _steel(); lea = M.cloth("PL_GripLeather", (0.20, 0.10, 0.05), "leather")
    L = 0.66 * s
    o = blade_loft("sw_blade", L, 0.022 * s, 0.0045 * s, st, ctx.col, y0=-0.06 * s)
    guard = C.box("sw_guard", (0.16 * s, 0.022 * s, 0.024 * s), (0, -0.05 * s, 0), st, ctx.col, bevel=0.006)
    gends = [C.uvsphere(f"sw_gend{k}", 0.014 * s, (sx * 0.08 * s, -0.05 * s, 0), segs=12, rings=8, mat=st, col=ctx.col) for k, sx in enumerate((1, -1))]
    grip = C.cyl("sw_grip", 0.014 * s, 0.11 * s, (0, 0.012 * s, 0), segs=12, mat=lea, col=ctx.col); grip.rotation_euler = (math.radians(90), 0, 0)
    wraps = [C.torus(f"sw_wrap{k}", 0.015 * s, 0.0025 * s, (0, -0.03 * s + 0.018 * s * k, 0), mat=lea, col=ctx.col, rot=(math.radians(90), 0, 0)) for k in range(5)]
    pom = C.uvsphere("sw_pommel", 0.022 * s, (0, 0.075 * s, 0), segs=16, rings=8, mat=st, col=ctx.col, scale=(1, 0.8, 1))
    _prop(ctx, [o, guard, grip, pom] + gends + wraps, "R", rot=(math.radians(68), 0, 0))


def wpn_axe(ctx):
    s = ctx.s; st = _steel(); wd = M.wood("PL_Haft", (0.30, 0.18, 0.08), (0.52, 0.34, 0.16))
    haft = C.cyl("ax_haft", 0.014 * s, 0.62 * s, (0, -0.22 * s, 0), segs=12, mat=wd, col=ctx.col); haft.rotation_euler = (math.radians(90), 0, 0)
    head = C.box("ax_head", (0.012 * s, 0.07 * s, 0.13 * s), (0, -0.48 * s, 0.05 * s), st, ctx.col, bevel=0.004)
    edge = C.cyl("ax_edge", 0.075 * s, 0.014 * s, (0, -0.48 * s, 0.11 * s), segs=24, mat=st, col=ctx.col); edge.rotation_euler = (0, math.radians(90), 0); edge.scale = (1, 1, 1)
    edge.scale = (0.9, 1.0, 0.8)
    wrap = C.cyl("ax_wrap", 0.016 * s, 0.10 * s, (0, 0.02 * s, 0), segs=12, mat=M.cloth("PL_GripLeather", (0.20, 0.10, 0.05), "leather"), col=ctx.col)
    wrap.rotation_euler = (math.radians(90), 0, 0)
    _prop(ctx, [haft, head, edge, wrap], "R", rot=(math.radians(55), 0, 0))


def wpn_pickaxe(ctx):
    s = ctx.s; st = _steel(); wd = M.wood("PL_Haft", (0.30, 0.18, 0.08), (0.52, 0.34, 0.16))
    haft = C.cyl("pk_haft", 0.014 * s, 0.66 * s, (0, -0.24 * s, 0), segs=12, mat=wd, col=ctx.col); haft.rotation_euler = (math.radians(90), 0, 0)
    pts = [Vector((0, -0.52 * s, -0.18 * s)), Vector((0, -0.56 * s, -0.05 * s)), Vector((0, -0.57 * s, 0.05 * s)), Vector((0, -0.53 * s, 0.17 * s))]
    pick = G.tube_mesh("pk_head", pts, lambda u: (0.008 + 0.012 * math.sin(math.pi * u)) * s, st, ctx.col, segs=8)
    _prop(ctx, [haft, pick], "R", rot=(math.radians(55), 0, 0))


def wpn_bow(ctx):
    s = ctx.s; wd = M.wood("PL_BowWood", (0.36, 0.20, 0.08), (0.58, 0.36, 0.16))
    lim = []
    for k in range(13):
        u = k / 12; z = (u - 0.5) * 1.20 * s; y = 0.10 * s * (1 - (2 * u - 1) ** 2) - 0.02 * s * (2 * u - 1) ** 6
        lim.append(Vector((0, -y, z)))
    bow = G.tube_mesh("bow_limbs", lim, lambda u: (0.006 + 0.008 * (1 - abs(2 * u - 1))) * s, wd, ctx.col, segs=8)
    string = G.tube_mesh("bow_string", [lim[0], lim[-1]], 0.0012 * s, M.cloth("PL_BowString", (0.85, 0.82, 0.72), "linen"), ctx.col, segs=4)
    grip = C.cyl("bow_grip", 0.016 * s, 0.10 * s, (0, -0.10 * s, 0), segs=12, mat=M.cloth("PL_GripLeather", (0.20, 0.10, 0.05), "leather"), col=ctx.col)
    _prop(ctx, [bow, string, grip], "L", offset=Vector((0, 0.09 * s, 0)))


def wpn_staff(ctx):
    s = ctx.s; wd = M.wood("PL_StaffWood", (0.26, 0.15, 0.07), (0.48, 0.31, 0.15))
    lea = M.cloth("PL_StaffWrap", (0.22, 0.11, 0.05), "leather")
    shaft = C.cyl("st_shaft", 0.015 * s, 1.12 * s, (0, -0.15 * s, 0), segs=12, mat=wd, col=ctx.col, r2=0.012 * s)
    shaft.rotation_euler = (math.radians(90), 0, 0)
    wraps = [C.torus(f"st_wrap{k}", 0.0165 * s, 0.0028 * s, (0, -0.04 * s + 0.018 * s * k, 0), mat=lea, col=ctx.col, rot=(math.radians(90), 0, 0)) for k in range(5)]
    ferrule = C.cyl("st_ferrule", 0.014 * s, 0.05 * s, (0, 0.40 * s, 0), segs=12, mat=_steel(), col=ctx.col); ferrule.rotation_euler = (math.radians(90), 0, 0)
    # gnarled head: three curling prongs cradling a crystal
    parts = [shaft, ferrule] + wraps
    top = Vector((0, -0.71 * s, 0))
    for k in range(3):
        a = k * 2 * math.pi / 3
        pts = [top + Vector((math.cos(a) * r * s, -u * s, math.sin(a) * r * s)) for u, r in ((0.0, 0.012), (0.04, 0.03), (0.09, 0.032), (0.13, 0.012))]
        parts.append(G.tube_mesh(f"st_prong{k}", pts, 0.0075 * s, wd, ctx.col, segs=8))
    gem = C.uvsphere("st_gem", 0.026 * s, top + Vector((0, -0.075 * s, 0)), segs=16, rings=10, mat=M.gem("PL_StaffGem") if hasattr(M, "gem") else _steel(), col=ctx.col, scale=(0.8, 1.3, 0.8))
    parts.append(gem)
    _prop(ctx, parts, "R", rot=(math.radians(68), 0, 0))


def wpn_rod(ctx):
    s = ctx.s; wd = M.wood("PL_RodWood", (0.40, 0.26, 0.12), (0.60, 0.42, 0.20))
    rod = C.cyl("rod", 0.010 * s, 0.57 * s, (0, -0.235 * s, 0), segs=10, mat=wd, col=ctx.col, r2=0.004 * s); rod.rotation_euler = (math.radians(90), 0, 0)
    reel = C.cyl("reel", 0.025 * s, 0.02 * s, (0.02 * s, -0.05 * s, -0.02 * s), segs=16, mat=M.metal("PL_ReelBrass", base=(0.75, 0.58, 0.28), tint=0.0), col=ctx.col)
    reel.rotation_euler = (0, math.radians(90), 0)
    line = G.tube_mesh("rod_line", [Vector((0, -0.515 * s, 0)), Vector((0, -0.54 * s, -0.4 * s)), Vector((0, -0.56 * s, -0.8 * s))], 0.0008 * s,
                       M.cloth("PL_Line", (0.90, 0.90, 0.88), "silk"), ctx.col, segs=4)
    _prop(ctx, [rod, reel, line], "R", rot=(math.radians(35), 0, 0))


# ------------------------------------------------------------------ CATALOGUE (single source of truth)
# z: draw order per facing (low first). armour overrides the cosmetic slot(s) in 'covers'.
Z_S = dict(shadow=0, cloak_back=4, shield_back=6, body=10, brows=11, bottom_trousers=20, shoes=24, bottom_skirt=28, top=40, outfit=45,
           acc_mid=50, armour_legs=52, armour_feet=54, armour_body=58, armour_hands=60, hair=70, armour_head=80, weapon=90, shield=92, acc_front=55)
CATALOGUE = [
    # id, slot, name, price, starter, tint, builder, z-class
    ("skin_light", "skin", "Fair skin", 0, True, False, None, "body"),
    ("skin_tan", "skin", "Tan skin", 0, True, False, None, "body"),
    ("skin_deep", "skin", "Deep skin", 0, True, False, None, "body"),
    ("hair_crop", "hair", "Short Crop", 0, True, True, "crop", "hair"),
    ("hair_side_part", "hair", "Side Part", 0, True, True, "side_part", "hair"),
    ("hair_shoulder_wavy", "hair", "Shoulder Waves", 120, False, True, "shoulder_wavy", "hair"),
    ("hair_long_straight", "hair", "Long & Straight", 150, False, True, "long_straight", "hair"),
    ("hair_ponytail", "hair", "High Ponytail", 0, True, True, "ponytail", "hair"),
    ("hair_braid", "hair", "Warrior Braid", 200, False, True, "braid", "hair"),
    ("top_linen_shirt", "top", "Linen Shirt", 0, True, False, top_linen_shirt, "top"),
    ("top_wool_tunic", "top", "Wool Tunic", 0, True, False, top_wool_tunic, "top"),
    ("top_leather_jerkin", "top", "Leather Jerkin", 120, False, False, top_leather_jerkin, "top"),
    ("top_ranger_tunic", "top", "Ranger Tunic", 180, False, False, top_ranger_tunic, "top"),
    ("top_gambeson", "top", "Quilted Gambeson", 260, False, False, top_gambeson, "top"),
    ("top_noble_doublet", "top", "Noble Doublet", 650, False, False, top_noble_doublet, "top"),
    ("bottom_work_trousers", "bottom", "Work Trousers", 0, True, False, bottom_work_trousers, "bottom_trousers"),
    ("bottom_long_skirt", "bottom", "Long Wool Skirt", 0, True, False, bottom_long_skirt, "bottom_skirt"),
    ("bottom_leather_breeches", "bottom", "Leather Breeches", 120, False, False, bottom_leather_breeches, "bottom_trousers"),
    ("bottom_kilt", "bottom", "Highland Kilt", 200, False, False, bottom_kilt, "bottom_skirt"),
    ("bottom_noble_hose", "bottom", "Noble Hose", 300, False, False, bottom_noble_hose, "bottom_trousers"),
    ("shoes_leather", "shoes", "Leather Shoes", 0, True, False, shoes_leather, "shoes"),
    ("shoes_sandals", "shoes", "Sandals", 40, False, False, sandals, "shoes"),
    ("shoes_riding_boots", "shoes", "Riding Boots", 150, False, False, boots_riding, "shoes"),
    ("shoes_fur_boots", "shoes", "Fur-trimmed Boots", 220, False, False, boots_fur, "shoes"),
    ("outfit_hunter", "outfit", "Hunter's Leathers", 800, False, False, outfit_hunter, "outfit"),
    ("outfit_festival", "outfit", "Festival Garb", 700, False, False, outfit_festival, "outfit"),
    ("outfit_mage_robe", "outfit", "Mage Robe", 900, False, False, outfit_mage_robe, "outfit"),
    ("outfit_noble", "outfit", "Noble Attire (coat / gown)", 1200, False, False, outfit_noble, "outfit"),
    ("acc_scarf", "accessory", "Knit Scarf", 80, False, False, acc_scarf, "acc_mid"),
    ("acc_leather_gloves", "accessory", "Leather Gloves", 100, False, False, acc_leather_gloves, "acc_mid"),
    ("acc_satchel", "accessory", "Satchel", 150, False, False, acc_satchel, "acc_front"),
    ("acc_travel_cloak", "accessory", "Travel Cloak", 300, False, False, acc_travel_cloak, "cloak_back"),
]
ARMOUR = [
    # layer id, game equip slot, builder, z-class, covers (cosmetic slots hidden while worn), item-id match
    ("arm_helm", "helmet", arm_helm, "armour_head", ["hair"], "*_helmet"),
    ("arm_platebody", "body", arm_platebody, "armour_body", ["top", "outfit"], "*_body"),
    ("arm_chainbody", "body", arm_chainbody, "armour_body", ["top", "outfit"], "*_chainbody"),
    ("arm_platelegs", "legs", arm_platelegs, "armour_legs", ["bottom", "outfit"], "*_legs | *_chainlegs (fallback)"),
    ("arm_gauntlets", "body", arm_gauntlets, "armour_hands", ["accessory:acc_leather_gloves"], "shown with *_body plate"),
    ("arm_sabatons", "legs", arm_sabatons, "armour_feet", ["shoes"], "shown with *_legs plate"),
    ("arm_kiteshield", "shield", arm_kiteshield, "shield", [], "*_shield | *_sq_shield (fallback) | wooden_shield"),
]
WEAPONS = [
    ("wpn_sword", wpn_sword, "*_sword | *_longsword | *_dagger (fallback)", ("idle", "walk", "melee", "hit", "death")),
    ("wpn_axe", wpn_axe, "*_axe | *_battleaxe (fallback) | woodcutting tool", ("idle", "walk", "melee", "chop", "hit", "death")),
    ("wpn_pickaxe", wpn_pickaxe, "*_pickaxe | mining tool", ("idle", "walk", "melee", "mine", "hit", "death")),
    ("wpn_bow", wpn_bow, "*bow*", ("idle", "walk", "ranged", "hit", "death")),
    ("wpn_staff", wpn_staff, "*staff* | *wand* (magic weapons; melee anim when used in melee, idle/hit/death otherwise)", ("idle", "walk", "melee", "hit", "death")),
    ("wpn_rod", wpn_rod, "fishing tool (shown only while fishing)", ("fish",)),
]


def PUSH_OUT_SLOTS(lid):
    return lid.startswith(("top_", "bottom_", "outfit_")) or lid in ("arm_platelegs", "arm_platebody", "arm_chainbody")


def push_out(ctx, objs, margin):
    """Move garment vertices that sit inside / too close to the skin out to 'margin' (rest pose), so the body holdout
    never punches holes in a garment (buttocks / hips poking through skirts, robes and leg plates)."""
    from mathutils import Vector as V
    n = 0
    for o in objs:
        if o.type != "MESH":
            continue
        mw = o.matrix_world; mi = mw.inverted()
        for v in o.data.vertices:
            p = mw @ v.co
            loc, nrm = ctx.nearest(p)
            if loc is None:
                continue
            d = (p - loc).dot(nrm)
            if d < margin and (p - loc).length < 0.06:
                v.co = mi @ (p + nrm * (margin - d)); n += 1
    return n


def build_all(kind, col, only=None, strict=False):
    import traceback, time
    ctx = build_base(kind, col)
    ctx.errors = {}
    want = lambda lid: (only is None) or (lid in only)
    jobs = []
    for cid, slot, name, price, starter, tint, b, zc in CATALOGUE:
        if b is not None:
            jobs.append((cid, (lambda b=b: HR.build_hair(ctx, b)) if slot == "hair" else (lambda b=b: b(ctx))))
    for lid, slot, b, zc, covers, match in ARMOUR:
        jobs.append((lid, lambda b=b: b(ctx)))
    for lid, b, match, anims in WEAPONS:
        jobs.append((lid, lambda b=b: b(ctx)))
    for lid, fn in jobs:
        if not want(lid):
            continue
        ctx.layer(lid); t0 = time.time()
        try:
            fn()
            if PUSH_OUT_SLOTS(lid):
                push_out(ctx, ctx.layers[lid], 0.008 * ctx.s)
            print(f"[build] {kind} {lid} ok {len(ctx.layers[lid])} objs {time.time()-t0:.1f}s", flush=True)
        except Exception as e:
            ctx.errors[lid] = traceback.format_exc()
            print(f"[build] {kind} {lid} FAILED: {e}\n{ctx.errors[lid]}", flush=True)
            if strict:
                raise
    return ctx
