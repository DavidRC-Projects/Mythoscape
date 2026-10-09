"""Simple FK armature for the CC0 stylized base body + weight transfer to armour pieces + pose helpers."""
import bpy, math
from collections import defaultdict
from mathutils import Vector, Matrix, Euler
from mathutils.kdtree import KDTree

WMODE = {}  # obj name -> "vert" | "single" | ("bone", name) | ("skirt", side, z_top, z_bot) | "skip"


def sm(x):
    x = max(0.0, min(1.0, x)); return x * x * (3 - 2 * x)


def cen(pts):
    return sum(pts, Vector()) / max(1, len(pts))


def joints(body, mask, h, face):
    V = body.data.vertices; s = h / 1.617
    J = {"h": h, "s": s}
    for side, sx in (("L", 1), ("R", -1)):
        for nm, f in (("hip", 0.505), ("knee", 0.285), ("ankle", 0.055)):
            z = f * h
            pts = [V[i].co for i in range(len(V)) if not mask[i] and V[i].co.x * sx > 0.004 and abs(V[i].co.z - z) < 0.012]
            c = cen(pts); J[f"{nm}_{side}"] = Vector((c.x, c.y, z))
        foot = [V[i].co for i in range(len(V)) if not mask[i] and V[i].co.x * sx > 0 and V[i].co.z < 0.04 * h]
        tmin = min(foot, key=lambda p: p.y); tmax = max(foot, key=lambda p: p.y)
        a = J[f"ankle_{side}"]
        J[f"toe_{side}"] = Vector((a.x, tmin.y + 0.02, 0.02))
        J[f"heel_{side}"] = Vector((a.x, tmax.y - 0.015, 0.012))
        idx = [i for i in range(len(V)) if mask[i] and V[i].co.x * sx > 0]
        top = max(V[i].co.z for i in idx)
        cap = [V[i].co for i in idx if V[i].co.z > top - 0.07 * s]
        cc = cen(cap)
        S = Vector((cc.x - sx * 0.012 * s, cc.y, top - 0.06 * s))
        tip = min((V[i].co for i in idx), key=lambda p: p.z).copy()
        d = tip - S; L = d.length; dn = d.normalized()

        def at(t):
            ps = [V[i].co for i in idx if abs((V[i].co - S).dot(dn) - t * L) < 0.015]
            return cen(ps) if ps else S + dn * t * L
        J[f"shoulder_{side}"] = S; J[f"elbow_{side}"] = at(0.42); J[f"wrist_{side}"] = at(0.73); J[f"tip_{side}"] = tip
        J[f"armdir_{side}"] = (S, dn, L)
    tor = [V[i].co for i in range(len(V)) if not mask[i] and abs(V[i].co.z - 0.62 * h) < 0.01]
    yc = cen(tor).y
    J["yc"] = yc
    J["pelvis"] = Vector((0, yc, 0.555 * h)); J["spine"] = Vector((0, yc, 0.625 * h)); J["chest"] = Vector((0, yc, 0.715 * h))
    J["neck"] = Vector((0, yc + 0.01, J["shoulder_L"].z + 0.035 * s)); J["head"] = Vector((0, yc + 0.01, face["eye_z"] - 0.085 * s))
    J["top"] = Vector((0, yc, h))
    # arm param per vertex
    J["arm_t"] = {}
    for side, sx in (("L", 1), ("R", -1)):
        S, dn, L = J[f"armdir_{side}"]
        for i in range(len(V)):
            if mask[i] and V[i].co.x * sx > 0:
                J["arm_t"][i] = ((V[i].co - S).dot(dn) / L, side)
    return J


def body_weights(body, mask, J):
    V = body.data.vertices; h = J["h"]; s = J["s"]
    W = []
    hz = J["hip_L"].z; kz = J["knee_L"].z; az = J["ankle_L"].z
    for i, v in enumerate(V):
        w = defaultdict(float); z = v.co.z
        if i in J["arm_t"]:
            t, side = J["arm_t"][i]
            sh = sm((0.14 - t) / 0.14) * 0.55
            fa = sm((t - 0.39) / 0.07); ha = sm((t - 0.70) / 0.06)
            up = (1 - fa); fo = fa * (1 - ha); hd = fa * ha
            w["chest"] += sh; w[f"upper_arm_{side}"] += up * (1 - sh); w[f"forearm_{side}"] += fo * (1 - sh); w[f"hand_{side}"] += hd * (1 - sh)
        else:
            wl = sm((hz + 0.015 * h - z) / (0.075 * h))
            if wl > 0:
                wk = sm((kz + 0.03 * h - z) / (0.06 * h)); wf = sm((az + 0.015 * h - z) / (0.03 * h))
                sides = [("L", 1.0)] if v.co.x > 0.003 else [("R", 1.0)] if v.co.x < -0.003 else [("L", 0.5), ("R", 0.5)]
                for sd, f in sides:
                    w[f"thigh_{sd}"] += wl * f * (1 - wk); w[f"shin_{sd}"] += wl * f * wk * (1 - wf); w[f"foot_{sd}"] += wl * f * wk * wf
            rest = 1 - wl
            if rest > 0:
                b = [("pelvis", -1e9), ("spine", 0.625 * h), ("chest", 0.715 * h), ("neck", J["neck"].z), ("head", J["head"].z)]
                acc = []
                for k in range(len(b)):
                    lo = b[k][1]; hi = b[k + 1][1] if k + 1 < len(b) else 1e9
                    bw = 0.025 * h
                    a1 = sm((z - lo + bw) / (2 * bw)) if lo > -1e8 else 1.0
                    a2 = 1 - sm((z - hi + bw) / (2 * bw)) if hi < 1e8 else 1.0
                    acc.append(a1 * a2)
                tot = sum(acc) or 1
                for (nm, _), a in zip(b, acc):
                    if a > 0:
                        w[nm] += rest * a / tot
        W.append(dict(w))
    return W


BONES = [
    ("root", lambda J: Vector((0, 0, 0)), lambda J: Vector((0, 0, 0.25)), None),
    ("pelvis", lambda J: J["pelvis"], lambda J: J["spine"], "root"),
    ("spine", lambda J: J["spine"], lambda J: J["chest"], "pelvis"),
    ("chest", lambda J: J["chest"], lambda J: J["neck"], "spine"),
    ("neck", lambda J: J["neck"], lambda J: J["head"], "chest"),
    ("head", lambda J: J["head"], lambda J: J["top"], "neck"),
    ("cape", lambda J: Vector((0, J["yc"] + 0.12 * J["s"], J["neck"].z - 0.02)), lambda J: Vector((0, J["yc"] + 0.25 * J["s"], 0.5)), "chest"),
]
for sd in ("L", "R"):
    BONES += [
        (f"upper_arm_{sd}", lambda J, sd=sd: J[f"shoulder_{sd}"], lambda J, sd=sd: J[f"elbow_{sd}"], "chest"),
        (f"forearm_{sd}", lambda J, sd=sd: J[f"elbow_{sd}"], lambda J, sd=sd: J[f"wrist_{sd}"], f"upper_arm_{sd}"),
        (f"hand_{sd}", lambda J, sd=sd: J[f"wrist_{sd}"], lambda J, sd=sd: J[f"tip_{sd}"], f"forearm_{sd}"),
        (f"thigh_{sd}", lambda J, sd=sd: J[f"hip_{sd}"], lambda J, sd=sd: J[f"knee_{sd}"], "pelvis"),
        (f"shin_{sd}", lambda J, sd=sd: J[f"knee_{sd}"], lambda J, sd=sd: J[f"ankle_{sd}"], f"thigh_{sd}"),
        (f"foot_{sd}", lambda J, sd=sd: J[f"ankle_{sd}"], lambda J, sd=sd: J[f"toe_{sd}"], f"shin_{sd}"),
    ]


def build_armature(col, J):
    ad = bpy.data.armatures.new("RIG"); arm = bpy.data.objects.new("RIG", ad); col.objects.link(arm)
    vl = bpy.context.view_layer
    for o in vl.objects:
        o.select_set(False)
    vl.objects.active = arm; arm.select_set(True)
    bpy.ops.object.mode_set(mode="EDIT")
    for nm, hd, tl, par in BONES:
        eb = ad.edit_bones.new(nm); eb.head = hd(J); eb.tail = tl(J)
        if (eb.tail - eb.head).length < 1e-3:
            eb.tail = eb.head + Vector((0, 0, 0.05))
        eb.roll = 0
        if par:
            eb.parent = ad.edit_bones[par]; eb.use_connect = False
    bpy.ops.object.mode_set(mode="OBJECT")
    for pb in arm.pose.bones:
        pb.rotation_mode = "QUATERNION"
    return arm


def curves_to_mesh(col):
    dg = bpy.context.evaluated_depsgraph_get()
    for o in list(col.objects):
        if o.type == "CURVE":
            me = bpy.data.meshes.new_from_object(o.evaluated_get(dg))
            nm = o.name; mw = o.matrix_world.copy(); mode = WMODE.get(nm)
            bpy.data.objects.remove(o)
            no = bpy.data.objects.new(nm, me); col.objects.link(no); no.matrix_world = mw
            if mode is not None:
                WMODE[nm] = mode


def bone_parent(o, arm, bone, posed=None):
    """Parent o to a bone keeping its current world matrix (posed: armature-space matrix of the bone right now)."""
    mw = o.matrix_world.copy()
    b = arm.data.bones[bone]
    M = posed if posed is not None else b.matrix_local
    o.parent = arm; o.parent_type = "BONE"; o.parent_bone = bone
    o.matrix_parent_inverse = Matrix.Identity(4)
    pm = arm.matrix_world @ M @ Matrix.Translation((0, b.length, 0))
    o.matrix_basis = pm.inverted() @ mw


def skin_all(col, arm, body, W, rest_co):
    bpy.context.view_layer.update()
    kd = KDTree(len(rest_co))
    for i, co in enumerate(rest_co):
        kd.insert(co, i)
    kd.balance()

    def blend(p, n=4):
        acc = defaultdict(float); tot = 0
        for co, i, d in kd.find_n(p, n):
            f = 1.0 / (d + 1e-3) ** 2; tot += f
            for b, bw in W[i].items():
                acc[b] += bw * f
        return {b: x / tot for b, x in acc.items() if x / tot > 1e-3}

    for o in list(col.objects):
        if o == arm or o.type not in ("MESH",):
            if o.type == "LIGHT":
                bone_parent(o, arm, "chest")
            continue
        mode = WMODE.get(o.name, "vert")
        if mode == "skip":
            continue
        if isinstance(mode, tuple) and mode[0] == "bone":
            bone_parent(o, arm, mode[1]); continue
        if o.parent is not None:
            mw = o.matrix_world.copy(); o.parent = None; o.matrix_world = mw
        o.data.transform(o.matrix_world); o.matrix_world = Matrix.Identity(4)
        if o != body:
            import bmesh
            bm = bmesh.new(); bm.from_mesh(o.data)
            dl = bm.verts.layers.deform.active
            if dl is not None:
                bm.verts.layers.deform.remove(dl)
            bm.to_mesh(o.data); bm.free()
            o.vertex_groups.clear()
        groups = {}

        def g(name):
            if name not in groups:
                groups[name] = o.vertex_groups.new(name=name)
            return groups[name]
        if o == body:
            pass
        elif mode == "single":
            c = cen([v.co for v in o.data.vertices])
            w = blend(c, 6); ids = [v.index for v in o.data.vertices]
            for b, bw in w.items():
                g(b).add(ids, bw, "REPLACE")
        elif isinstance(mode, tuple) and mode[0] == "skirt":
            _, sd, zt, zb = mode
            for v in o.data.vertices:
                t = sm((zt - v.co.z) / max(1e-3, (zt - zb)) * 1.4)
                g("pelvis").add([v.index], 1 - t + 1e-3, "REPLACE"); g(f"thigh_{sd}").add([v.index], t + 1e-3, "REPLACE")
        else:
            for v in o.data.vertices:
                for b, bw in blend(v.co).items():
                    g(b).add([v.index], bw, "REPLACE")
        m = o.modifiers.new("Arm", "ARMATURE"); m.object = arm
        lead = 0
        for k, mm in enumerate(o.modifiers):
            if mm.type == "LAPLACIANSMOOTH":
                lead = k + 1
        o.modifiers.move(len(o.modifiers) - 1, lead)
        o.parent = arm


def set_pose(arm, P, root=(0, 0, 0)):
    for pb in arm.pose.bones:
        pb.rotation_quaternion = (1, 0, 0, 0); pb.location = (0, 0, 0)
    for nm, (rx, ry, rz) in P.items():
        b = arm.data.bones[nm]; Bl = b.matrix_local.to_3x3()
        R = Euler((math.radians(rx), math.radians(ry), math.radians(rz)), "XYZ").to_matrix()
        arm.pose.bones[nm].rotation_quaternion = (Bl.inverted() @ R @ Bl).to_quaternion()
    rb = arm.data.bones["root"]
    arm.pose.bones["root"].location = rb.matrix_local.to_3x3().inverted() @ Vector(root)
    bpy.context.view_layer.update()


def posed(arm):
    dg = bpy.context.evaluated_depsgraph_get()
    ae = arm.evaluated_get(dg)
    return {pb.name: pb.matrix.copy() for pb in ae.pose.bones}


def posed_point(arm, PM, bone, p_rest):
    b = arm.data.bones[bone]
    return (PM[bone] @ b.matrix_local.inverted()) @ Vector(p_rest)


def ground(arm, P, J, root=(0, 0, 0)):
    """Pose, then lift/drop the root so the lowest heel/toe sits on the floor."""
    set_pose(arm, P, root)
    PM = posed(arm)
    lows = []
    for sd in ("L", "R"):
        for key in ("heel", "toe"):
            p = posed_point(arm, PM, f"foot_{sd}", J[f"{key}_{sd}"])
            lows.append(p.z - J[f"{key}_{sd}"].z)
    dz = -min(lows)
    r = (root[0], root[1], root[2] + dz)
    set_pose(arm, P, r)
    return r


_GPTS = [("pelvis", "pelvis", 0.13), ("chest", "chest", 0.15), ("neck", "head", 0.10), ("top", "head", 0.11),
         ("head", "head", 0.12)]
for _sd in ("L", "R"):
    _GPTS += [(f"shoulder_{_sd}", f"upper_arm_{_sd}", 0.09), (f"elbow_{_sd}", f"forearm_{_sd}", 0.06),
              (f"wrist_{_sd}", f"hand_{_sd}", 0.05), (f"tip_{_sd}", f"hand_{_sd}", 0.04),
              (f"hip_{_sd}", f"thigh_{_sd}", 0.10), (f"knee_{_sd}", f"shin_{_sd}", 0.07), (f"ankle_{_sd}", f"foot_{_sd}", 0.06)]


def ground_any(arm, P, J, root=(0, 0, 0), lift=0.0):
    """Ground on whatever touches the floor first (knees, back, side): used for collapse / death frames."""
    set_pose(arm, P, root)
    PM = posed(arm)
    s = J["s"]
    lows = []
    for sd in ("L", "R"):
        for key in ("heel", "toe"):
            p = posed_point(arm, PM, f"foot_{sd}", J[f"{key}_{sd}"])
            lows.append(p.z - J[f"{key}_{sd}"].z)
    for jn, bn, r in _GPTS:
        lows.append(posed_point(arm, PM, bn, J[jn]).z - r * s)
    dz = -min(lows) + lift
    r = (root[0], root[1], root[2] + dz)
    set_pose(arm, P, r)
    return r
