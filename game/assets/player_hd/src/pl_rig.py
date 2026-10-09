"""Shared player rig: CC0 stylized base body + simple FK armature + poses matched to rs_style timing."""
import bpy, bmesh, math, sys
from mathutils import Vector, Matrix, Quaternion
from mathutils.kdtree import KDTree
sys.path.insert(0, "/workspace/fairy_village/src/blender"); sys.path.insert(0, "/workspace/npc_hd_overworld/batch4/src")
import fv_common as C
import fv_npc_helpers as H

TAU = math.pi * 2


def _centroid(pts):
    return sum(pts, Vector()) / max(1, len(pts))


def joints(body, kind):
    V = body.data.vertices
    h = max(v.co.z for v in V)
    mask = H.arm_mask(body, h)
    J = {"h": h, "mask": mask}
    f = dict(hip=0.53, knee=0.285, ankle=0.05) if kind == "male" else dict(hip=0.53, knee=0.285, ankle=0.05)
    for side, sx in (("L", 1), ("R", -1)):
        for nm in ("hip", "knee", "ankle"):
            z = f[nm] * h
            pts = [V[i].co for i in range(len(V)) if (not mask[i]) and V[i].co.x * sx > 0.01 and abs(V[i].co.z - z) < 0.012]
            c = _centroid(pts)
            J[f"{nm}_{side}"] = Vector((c.x, c.y, z))
        toe = [V[i].co for i in range(len(V)) if (not mask[i]) and V[i].co.x * sx > 0 and V[i].co.z < 0.04 * h]
        tmin = min(toe, key=lambda p: p.y)
        J[f"toe_{side}"] = Vector((J[f"ankle_{side}"].x, tmin.y + 0.02, 0.02))
        arm = [V[i].co for i in range(len(V)) if mask[i] and V[i].co.x * sx > 0]
        top = max(arm, key=lambda p: p.z); tip = min(arm, key=lambda p: p.z)
        S = Vector((top.x - sx * 0.035, _centroid([p for p in arm if p.z > top.z - 0.06]).y, top.z - 0.055))
        d = (tip - S); L = d.length; dn = d.normalized()

        def at(t):
            ps = [p for p in arm if abs((p - S).dot(dn) - t * L) < 0.015]
            c = _centroid(ps) if ps else S + dn * t * L
            return c
        J[f"shoulder_{side}"] = S
        J[f"elbow_{side}"] = at(0.43)
        J[f"wrist_{side}"] = at(0.74)
        J[f"knuckle_{side}"] = at(0.86)
        J[f"tip_{side}"] = tip
        kn = J[f"knuckle_{side}"]; wr = J[f"wrist_{side}"]
        # grip: inside the curled fist, a little toward the palm (body side) and below the knuckles
        J[f"grip_{side}"] = kn + (kn - wr).normalized() * 0.01 + Vector((-sx * 0.022, -0.005, -0.012))
    eyes_z = None
    J["pelvis"] = Vector((0, (J["hip_L"].y + J["hip_R"].y) / 2, J["hip_L"].z + 0.03 * h))
    J["spine"] = Vector((0, J["pelvis"].y, 0.62 * h))
    J["chest"] = Vector((0, J["pelvis"].y, 0.71 * h))
    J["neck"] = Vector((0, J["pelvis"].y + 0.0, (J["shoulder_L"].z + 0.03 * h)))
    J["head"] = Vector((0, J["pelvis"].y, J["neck"].z + 0.045 * h))
    J["top"] = Vector((0, J["pelvis"].y, h))
    return J


BONES = [
    # name, head, tail, parent
    ("root", lambda J: Vector((0, 0, 0)), lambda J: Vector((0, 0.2, 0)), None),
    ("pelvis", lambda J: J["pelvis"], lambda J: J["spine"], "root"),
    ("spine", lambda J: J["spine"], lambda J: J["chest"], "pelvis"),
    ("chest", lambda J: J["chest"], lambda J: J["neck"], "spine"),
    ("neck", lambda J: J["neck"], lambda J: J["head"], "chest"),
    ("head", lambda J: J["head"], lambda J: J["top"], "neck"),
]
for s in ("L", "R"):
    BONES += [
        (f"upper_arm_{s}", (lambda s: lambda J: J[f"shoulder_{s}"])(s), (lambda s: lambda J: J[f"elbow_{s}"])(s), "chest"),
        (f"forearm_{s}", (lambda s: lambda J: J[f"elbow_{s}"])(s), (lambda s: lambda J: J[f"wrist_{s}"])(s), f"upper_arm_{s}"),
        (f"hand_{s}", (lambda s: lambda J: J[f"wrist_{s}"])(s), (lambda s: lambda J: J[f"knuckle_{s}"])(s), f"forearm_{s}"),
        (f"fingers_{s}", (lambda s: lambda J: J[f"knuckle_{s}"])(s), (lambda s: lambda J: J[f"tip_{s}"])(s), f"hand_{s}"),
        (f"prop_{s}", (lambda s: lambda J: J[f"grip_{s}"])(s), (lambda s: lambda J: J[f"grip_{s}"] + Vector((0, -0.1, 0)))(s), f"hand_{s}"),
        (f"thigh_{s}", (lambda s: lambda J: J[f"hip_{s}"])(s), (lambda s: lambda J: J[f"knee_{s}"])(s), "pelvis"),
        (f"shin_{s}", (lambda s: lambda J: J[f"knee_{s}"])(s), (lambda s: lambda J: J[f"ankle_{s}"])(s), f"thigh_{s}"),
        (f"foot_{s}", (lambda s: lambda J: J[f"ankle_{s}"])(s), (lambda s: lambda J: J[f"toe_{s}"])(s), f"shin_{s}"),
    ]


def build_armature(col, J, name="RIG"):
    ad = bpy.data.armatures.new(name)
    arm = bpy.data.objects.new(name, ad); col.objects.link(arm)
    bpy.context.view_layer.objects.active = arm
    for o in bpy.context.view_layer.objects:
        o.select_set(False)
    arm.select_set(True)
    bpy.ops.object.mode_set(mode="EDIT")
    for nm, hd, tl, par in BONES:
        b = ad.edit_bones.new(nm)
        b.head = hd(J); b.tail = tl(J)
        if (b.tail - b.head).length < 1e-3:
            b.tail = b.head + Vector((0, 0, 0.05))
        b.roll = 0.0
        if par:
            b.parent = ad.edit_bones[par]
            b.use_connect = False
    bpy.ops.object.mode_set(mode="OBJECT")
    for pb in arm.pose.bones:
        pb.rotation_mode = "QUATERNION"
    return arm


def skin_auto(body, arm):
    for nm in ("root", "prop_L", "prop_R"):
        arm.data.bones[nm].use_deform = False
    for o in bpy.context.view_layer.objects:
        o.select_set(False)
    body.select_set(True); arm.select_set(True)
    bpy.context.view_layer.objects.active = arm
    bpy.ops.object.parent_set(type="ARMATURE_AUTO")
    md = [m for m in body.modifiers if m.type == "ARMATURE"]
    if md:
        body.modifiers.move(body.modifiers.find(md[0].name), 0)
    return len(body.vertex_groups)


def ensure_armature_mod(o, arm):
    m = o.modifiers.new("Armature", "ARMATURE"); m.object = arm
    lead = 0
    for md in o.modifiers:
        if md.name in ("PreSub", "Folds"):
            lead += 1
    o.modifiers.move(len(o.modifiers) - 1, lead)
    o.parent = arm
    return m


def copy_groups_from_body(o, body):
    """For meshes extracted from the body (bmesh keeps the deform layer): recreate group names in order."""
    for g in body.vertex_groups:
        if g.name not in o.vertex_groups:
            o.vertex_groups.new(name=g.name)


class BodyWeights:
    """Nearest-vertex weight transfer from the rest-pose body to any generated mesh."""
    def __init__(self, body):
        V = body.data.vertices
        self.kd = KDTree(len(V))
        for i, v in enumerate(V):
            self.kd.insert(v.co, i)
        self.kd.balance()
        self.names = [g.name for g in body.vertex_groups]
        self.w = [{self.names[g.group]: g.weight for g in v.groups if g.weight > 0.01} for v in V]

    def apply(self, o, k=4, override=None):
        """override(co)-> dict or None lets callers force procedural weights (skirts)."""
        bpy.context.view_layer.update()
        mw = o.matrix_world.copy()
        for nm in self.names:
            if nm not in o.vertex_groups:
                o.vertex_groups.new(name=nm)
        acc_groups = {}
        for v in o.data.vertices:
            co = mw @ v.co
            wd = override(co) if override else None
            if wd is None:
                wd = {}
                hits = self.kd.find_n(co, k)
                tot = 0.0
                for (_, idx, dist) in hits:
                    ww = 1.0 / (dist + 1e-4)
                    tot += ww
                    for nm, x in self.w[idx].items():
                        wd[nm] = wd.get(nm, 0.0) + x * ww
                wd = {nm: x / tot for nm, x in wd.items()}
            for nm, x in wd.items():
                if x > 0.005:
                    acc_groups.setdefault(nm, []).append((v.index, x))
        for nm, lst in acc_groups.items():
            g = o.vertex_groups[nm]
            for idx, x in lst:
                g.add([idx], x, "REPLACE")


def bind(o, arm, bw, override=None):
    bw.apply(o, override=override)
    ensure_armature_mod(o, arm)


def bone_parent(o, arm, bone):
    bpy.context.view_layer.update()
    mw = o.matrix_world.copy()
    o.parent = arm; o.parent_type = "BONE"; o.parent_bone = bone
    bpy.context.view_layer.update()
    o.matrix_world = mw


def skirt_override(J, z_top, z_bot):
    """Procedural skirt weights: pelvis at the waist, blending to each thigh/shin by height and side."""
    def f(co):
        t = max(0.0, min(1.0, (z_top - co.z) / max(1e-3, (z_top - z_bot))))
        side = max(0.0, min(1.0, 0.5 + co.x / 0.18))
        leg = 0.75 * t
        shin = max(0.0, (J["knee_L"].z + 0.05 - co.z) / 0.3) * 0.5
        d = {"pelvis": 1.0 - leg}
        d["thigh_L"] = leg * side * (1 - shin); d["thigh_R"] = leg * (1 - side) * (1 - shin)
        d["shin_L"] = leg * side * shin; d["shin_R"] = leg * (1 - side) * shin
        return d
    return f


# ----------------------------------------------------------------------------- posing
def _q(axis, ang):
    return Quaternion(Vector(axis), ang)


def set_rot(arm, name, q_arm):
    """q_arm: rotation expressed in ARMATURE rest axes (X = character left, -Y = forward, Z = up)."""
    pb = arm.pose.bones[name]
    R = pb.bone.matrix_local.to_quaternion()
    pb.rotation_quaternion = R.inverted() @ q_arm @ R


def reset_pose(arm):
    for pb in arm.pose.bones:
        pb.rotation_quaternion = (1, 0, 0, 0); pb.location = (0, 0, 0); pb.scale = (1, 1, 1)


def smooth(u):
    u = max(0.0, min(1.0, u)); return u * u * (3 - 2 * u)


def keyed(p, keys):
    """keys: list of (p, dict). Smoothstep interpolation between neighbours."""
    for i in range(len(keys) - 1):
        p0, a = keys[i]; p1, b = keys[i + 1]
        if p0 <= p <= p1:
            u = smooth((p - p0) / max(1e-6, p1 - p0))
            return {k: a.get(k, 0.0) + (b.get(k, 0.0) - a.get(k, 0.0)) * u for k in set(a) | set(b)}
    return dict(keys[-1][1])


ARM_DOWN = 0.20   # adduction from the CC0 A-pose so arms hang by the sides


def apply_pose(arm, P, J):
    """P keys (radians / metres): bob, lean, twist, head, sh_L/sh_R (flex: -fwd), ab_L/ab_R (abduct +out),
    el_L/el_R (elbow flex), wr_L/wr_R, fg_L/fg_R (finger curl), th_L/th_R (hip flex, -fwd), kn_L/kn_R, ft_L/ft_R, sx (pelvis shift fwd)."""
    reset_pose(arm)
    g = P.get
    rootb = arm.pose.bones["root"]
    rootb.location = (0, 0, 0)
    fall = g("fall", 0.0)
    if fall:
        h = J["h"]
        if P.get("fall_axis", "x") == "x":      # falls backward (+Y), body re-centred over the feet anchor
            set_rot(arm, "root", _q((1, 0, 0), -fall))
            off = Vector((0, -0.5 * h * math.sin(fall), 0.10 * h / 1.7 * math.sin(fall)))
        else:                                    # falls to its left (+X) - keeps the body side-on to s / n cameras
            set_rot(arm, "root", _q((0, 1, 0), fall))
            off = Vector((-0.5 * h * math.sin(fall), 0, 0.10 * h / 1.7 * math.sin(fall)))
        rootb.location = rootb.bone.matrix_local.to_quaternion().inverted() @ off
    # root bob via pelvis location (bone-local Y is up the spine; use armature-space via matrix)
    pel = arm.pose.bones["pelvis"]
    off = Vector((0, -g("sx", 0.0), -g("bob", 0.0)))
    pel.location = pel.bone.matrix_local.to_quaternion().inverted() @ off
    # +X rotation tips an upward bone toward -Y (forward)
    set_rot(arm, "pelvis", _q((0, 0, 1), g("twist", 0.0) * 0.3) @ _q((1, 0, 0), g("hip_lean", 0.0)))
    set_rot(arm, "spine", _q((0, 0, 1), g("twist", 0.0) * 0.35) @ _q((1, 0, 0), g("lean", 0.0) * 0.5))
    set_rot(arm, "chest", _q((0, 0, 1), g("twist", 0.0) * 0.35) @ _q((1, 0, 0), g("lean", 0.0) * 0.5 - g("breath", 0.0)))
    set_rot(arm, "neck", _q((1, 0, 0), -g("lean", 0.0) * 0.45 + g("head", 0.0) * 0.5))
    set_rot(arm, "head", _q((0, 0, 1), g("look", 0.0)) @ _q((1, 0, 0), g("head", 0.0) * 0.5))
    for s, sx in (("L", 1), ("R", -1)):
        ab = g(f"ab_{s}", 0.0)
        set_rot(arm, f"upper_arm_{s}", _q((1, 0, 0), g(f"sh_{s}", 0.0)) @ _q((0, 1, 0), sx * (ARM_DOWN - ab))
                @ _q((0, 0, 1), sx * g(f"rot_{s}", 0.0)))
        set_rot(arm, f"forearm_{s}", _q((1, 0, 0), -g(f"el_{s}", 0.1)))
        set_rot(arm, f"hand_{s}", _q((1, 0, 0), -g(f"wr_{s}", 0.0)) @ _q((0, 0, 1), sx * g(f"wrz_{s}", 0.0)))
        set_rot(arm, f"fingers_{s}", _q((1, 0, 0), -g(f"fg_{s}", 0.15)))
        set_rot(arm, f"prop_{s}", _q((1, 0, 0), g(f"pr_{s}", 0.0)))
        set_rot(arm, f"thigh_{s}", _q((1, 0, 0), g(f"th_{s}", 0.0)) @ _q((0, 1, 0), sx * g(f"tha_{s}", 0.0)))
        set_rot(arm, f"shin_{s}", _q((1, 0, 0), g(f"kn_{s}", 0.0)))
        set_rot(arm, f"foot_{s}", _q((1, 0, 0), g(f"ft_{s}", 0.0)))
    bpy.context.view_layer.update()


# Pose library. Frame counts / phase mapping mirror rs_style.py so HD timing == 2D timing.
ANIMS = {
    # name: (frames, facings, loop, runtime mapping doc)
    "idle":   (8, ("s", "e", "n"), True,  "frame = int(((t / math.pi) % 1.0) * 8)   # pose_idle breath sin(t*2.0) period = pi s"),
    "walk":   (8, ("s", "e", "n"), True,  "frame = int(((t * 1.15) % 1.0) * 8)      # pose_walk cadence TAU*1.15"),
    "melee":  (10, ("e",), False,         "frame = last i with MELEE_P[i] <= progress   # pose_attack progress over ATTACK_ANIM_SECS=1.05; frame 4 = contact at 0.48 = client strike_t (hitsplat)"),
    "ranged": (8, ("e",), False,          "frame = last i with RANGED_P[i] <= progress  # pose_ranged over RANGED_ANIM_SECS=0.72; frame 5 = release at 0.55 = arrow spawn"),
    "chop":   (8, ("e",), True,           "frame = int(((t * 1.1) % 1.0) * 8)       # pose_chop ph = (t*1.1)%1"),
    "mine":   (8, ("e",), True,           "frame = int(((t * 1.05) % 1.0) * 8)      # pose_mine ph = (t*1.05)%1"),
    "fish":   (8, ("e",), True,           "frame = int(((t * 0.55) % 1.0) * 8)      # pose_fish ph = t*TAU*0.55"),
    "hit":    (4, ("s", "e", "n"), False, "NEW (2D has none): frame = min(3, int(u * 4)), u = (now - splat_show_at) / 0.36; only when not attacking/moving"),
    "death":  (8, ("s", "e", "n"), False, "NEW (2D has none): frame = min(7, int(u * 8)), u = (now - death_at) / 1.2, then hold frame 7 until respawn"),
}
# progress sample per frame (non-uniform so the contact / release poses sit exactly on the client's strike / arrow times)
MW_SH, MW_EL = -2.75, 1.25
MA_SH, MA_EL, MA_WR = -2.30, 0.55, 0.30
MC_SH, MC_EL, MC_WR = -1.45, 0.10, -0.30
MF_SH, MF_WR = -1.15, -0.30
STAFF_FLIP = float(__import__('os').environ.get('PL_STAFF_FLIP', '3.7'))
MELEE_P = [0.0, 0.10, 0.22, 0.34, 0.48, 0.55, 0.62, 0.71, 0.80, 0.91]
RANGED_P = [0.0, 0.12, 0.24, 0.36, 0.48, 0.55, 0.72, 0.86]


def pose_for(anim, k, J, kind):
    n = ANIMS[anim][0]
    L = (J["hip_L"] - J["ankle_L"]).length
    fem = kind == "female"
    if anim == "idle":
        ph = TAU * k / n
        b = math.sin(ph)
        return dict(breath=0.02 * b, bob=0.003 * (1 + b), head=0.03 * math.sin(ph * 0.5), look=0.04 * math.sin(ph),
                    sh_L=0.02 * b, sh_R=-0.02 * b, el_L=0.18, el_R=0.18, fg_L=0.25, fg_R=0.25,
                    th_L=0.0, th_R=0.0, tha_L=0.03, tha_R=0.03, kn_L=0.04, kn_R=0.04)
    if anim == "walk":
        ph = TAU * k / n
        amp = 0.36
        th_L = -math.sin(ph) * amp           # left thigh forward when sin>0 (matches rs hip_l = sin(ph))
        th_R = math.sin(ph) * amp
        sw_L = max(0.0, math.cos(ph)) ** 1.15
        sw_R = max(0.0, -math.cos(ph)) ** 1.15
        kn_L = 0.10 + sw_L * 0.85
        kn_R = 0.10 + sw_R * 0.85
        stance = max(abs(th_L), abs(th_R))
        bob = L * (1 - math.cos(stance)) * 0.85 - 0.004
        arm = math.sin(ph) * 0.30            # contralateral: left arm back when left leg forward
        return dict(bob=bob, lean=0.05 + 0.02 * abs(math.sin(ph)), twist=0.05 * math.sin(ph), head=-0.03,
                    sh_L=arm, sh_R=-arm, el_L=0.25 + 0.15 * max(0, -arm), el_R=0.25 + 0.15 * max(0, arm), fg_L=0.3, fg_R=0.3,
                    th_L=th_L, th_R=th_R, kn_L=kn_L, kn_R=kn_R,
                    ft_L=-0.25 * sw_L + 0.15 * max(0, -th_L), ft_R=-0.25 * sw_R + 0.15 * max(0, -th_R))
    if anim == "melee":
        # windup -> peak -> accelerate -> CONTACT (frame 4 @0.48, blade level at an adjacent monster's chest) -> follow-through -> recover
        p = MELEE_P[k]
        G = dict(fg_R=1.15, fg_L=0.45)
        rest = dict(G, sh_R=-0.55, el_R=0.75, wr_R=0.0, sh_L=-0.30, el_L=0.70, lean=0.0, th_L=-0.10, th_R=0.12, kn_L=0.12, kn_R=0.15)
        keys = [
            (0.00, rest),
            (0.10, dict(G, sh_R=-1.70, el_R=1.45, wr_R=0.25, sh_L=-0.45, el_L=0.85, lean=-0.02, twist=-0.18, th_L=-0.14, th_R=0.16, kn_L=0.16, kn_R=0.18)),
            (0.22, dict(G, sh_R=MW_SH, el_R=MW_EL, wr_R=-0.10, sh_L=-0.60, el_L=0.95, lean=-0.08, twist=-0.40, bob=0.01, th_L=-0.22, th_R=0.20, kn_L=0.24, kn_R=0.18)),
            (0.34, dict(G, sh_R=MA_SH, el_R=MA_EL, wr_R=MA_WR, sh_L=-0.35, el_L=0.85, lean=0.08, twist=-0.05, bob=0.02, sx=0.02, th_L=-0.35, th_R=0.25, kn_L=0.35, kn_R=0.14)),
            (0.48, dict(G, sh_R=MC_SH, el_R=MC_EL, wr_R=MC_WR, sh_L=-0.10, el_L=0.70, lean=0.18, twist=0.28, bob=0.03, sx=0.05, th_L=-0.45, th_R=0.30, kn_L=0.45, kn_R=0.12)),
            (0.55, dict(G, sh_R=MF_SH, el_R=0.12, wr_R=MF_WR, sh_L=-0.10, el_L=0.70, lean=0.22, twist=0.40, bob=0.035, sx=0.05, th_L=-0.45, th_R=0.30, kn_L=0.45, kn_R=0.12)),
            (0.62, dict(G, sh_R=-0.80, el_R=0.15, wr_R=-0.45, sh_L=-0.15, el_L=0.70, lean=0.20, twist=0.38, bob=0.03, sx=0.05, th_L=-0.42, th_R=0.28, kn_L=0.42, kn_R=0.12)),
            (0.80, dict(G, sh_R=-0.60, el_R=0.45, wr_R=-0.15, sh_L=-0.22, el_L=0.68, lean=0.08, twist=0.12, bob=0.012, sx=0.02, th_L=-0.22, th_R=0.18, kn_L=0.22, kn_R=0.13)),
            (1.00, rest),
        ]
        return keyed(p, keys)
    if anim == "ranged":
        p = RANGED_P[k]
        base = dict(sh_L=-1.50, el_L=0.05, rot_L=0.15, ab_L=0.10, fg_L=1.1, pr_L=1.45, look=0.0, th_L=-0.12, th_R=0.10, kn_L=0.10, kn_R=0.12, twist=0.35)
        keys = [
            (0.00, dict(base, sh_L=-0.6, el_L=0.5, pr_L=0.55, sh_R=-0.4, el_R=0.5, fg_R=0.6, twist=0.1)),
            (0.18, dict(base, sh_R=-1.35, el_R=1.2, fg_R=0.9)),
            (0.48, dict(base, sh_R=-1.55, el_R=2.35, ab_R=0.35, fg_R=0.9, lean=-0.05)),
            (0.58, dict(base, sh_R=-1.55, el_R=2.40, ab_R=0.38, fg_R=0.9, lean=-0.05)),
            (0.72, dict(base, sh_R=-1.45, el_R=1.30, ab_R=0.55, fg_R=0.2, lean=0.04)),
            (1.00, dict(base, sh_L=-0.6, el_L=0.5, pr_L=0.55, sh_R=-0.4, el_R=0.5, fg_R=0.6, twist=0.1)),
        ]
        return keyed(p, keys)
    if anim == "hit":
        # flinch: torso snaps back, guard arm (shield side) comes up, knees give; recovers to idle
        u = k / (n - 1)
        r = (1 - u) ** 1.6
        return dict(lean=-0.22 * r, head=-0.25 * r, look=0.08 * r, bob=0.012 * r + 0.003,
                    sh_L=-0.25 - 0.85 * r, el_L=0.25 + 1.25 * r, ab_L=0.15 * r, fg_L=0.6,
                    sh_R=0.10 * r, el_R=0.25 + 0.35 * r, ab_R=0.20 * r, fg_R=0.9,
                    th_L=0.10 * r, th_R=-0.05 * r, kn_L=0.04 + 0.16 * r, kn_R=0.04 + 0.22 * r, tha_L=0.03, tha_R=0.03)
    if anim == "death":
        u = k / (n - 1)
        keys = [
            (0.00, dict(lean=-0.20, head=-0.30, sh_L=-0.5, el_L=0.8, ab_L=0.3, sh_R=-0.3, el_R=0.6, ab_R=0.3, kn_L=0.1, kn_R=0.15, fg_L=0.4, fg_R=0.9)),
            (0.28, dict(lean=0.25, head=0.30, bob=0.10, th_L=-0.55, th_R=-0.45, kn_L=1.05, kn_R=0.95, ft_L=0.35, ft_R=0.3,
                        sh_L=0.1, el_L=0.4, ab_L=0.2, sh_R=0.1, el_R=0.4, ab_R=0.2, fg_L=0.3, fg_R=0.9)),
            (0.55, dict(fall=0.75, lean=0.05, head=0.15, bob=0.06, th_L=-0.35, th_R=-0.30, kn_L=0.6, kn_R=0.55,
                        sh_L=-0.6, el_L=0.3, ab_L=0.5, sh_R=-0.6, el_R=0.3, ab_R=0.5, fg_L=0.3, fg_R=0.9)),
            (0.80, dict(fall=1.40, lean=-0.05, head=-0.10, bob=0.02, th_L=-0.15, th_R=-0.10, kn_L=0.25, kn_R=0.2,
                        sh_L=-0.1, el_L=0.25, ab_L=0.15, sh_R=-0.1, el_R=0.25, ab_R=0.9, fg_L=0.3, fg_R=0.9)),
            (1.00, dict(fall=1.50, lean=-0.06, head=-0.15, look=0.35, bob=0.0, th_L=-0.12, th_R=-0.06, kn_L=0.18, kn_R=0.12, ft_L=-0.2, ft_R=-0.25,
                        sh_L=0.05, el_L=0.30, ab_L=0.1, sh_R=0.05, el_R=0.45, ab_R=0.85, fg_L=0.35, fg_R=0.7)),
        ]
        return keyed(u, keys)
    if anim in ("chop", "mine"):
        ph = k / n
        if anim == "chop":
            hi = dict(sh_R=-2.55, el_R=1.0, sh_L=-2.2, el_L=1.2, lean=-0.08, twist=-0.15, fg_R=1.1, fg_L=1.1, th_L=-0.18, th_R=0.15, kn_L=0.15, kn_R=0.2)
            lo = dict(sh_R=-0.95, el_R=0.15, sh_L=-0.80, el_L=0.35, lean=0.30, twist=0.15, bob=0.04, fg_R=1.1, fg_L=1.1, th_L=-0.30, th_R=0.18, kn_L=0.35, kn_R=0.3)
            keys = [(0.0, lo), (0.35, hi), (0.55, lo), (1.0, lo)]
            mid = dict(lo); mid.update(sh_R=-1.3, sh_L=-1.1, el_R=0.5, el_L=0.6, lean=0.12, bob=0.02)
            keys = [(0.0, mid), (0.35, hi), (0.55, lo), (1.0, mid)]
        else:
            hi = dict(sh_R=-2.35, el_R=1.1, sh_L=-1.9, el_L=1.3, lean=0.05, twist=-0.12, bob=0.03, fg_R=1.1, fg_L=1.1, th_L=-0.32, th_R=0.25, kn_L=0.40, kn_R=0.45)
            lo = dict(sh_R=-0.75, el_R=0.20, sh_L=-0.60, el_L=0.40, lean=0.45, twist=0.12, bob=0.07, fg_R=1.1, fg_L=1.1, th_L=-0.45, th_R=0.25, kn_L=0.60, kn_R=0.55)
            mid = dict(lo); mid.update(sh_R=-1.2, sh_L=-1.0, el_R=0.5, el_L=0.6, lean=0.28, bob=0.05)
            keys = [(0.0, mid), (0.38, hi), (0.58, lo), (1.0, mid)]
        return keyed(ph, keys)
    if anim == "fish":
        ph = TAU * k / n
        bob = math.sin(ph) * 0.18
        tug = max(0.0, math.sin(ph * 0.5 + 0.8)) ** 2
        return dict(lean=0.18 + bob * 0.1, head=0.12, sh_R=-1.05 - bob * 0.25 - tug * 0.2, el_R=0.35, fg_R=1.1,
                    sh_L=-0.75, el_L=1.25, ab_L=-0.15, fg_L=1.0, th_L=-0.10, th_R=0.16, kn_L=0.12, kn_R=0.22, bob=0.01 + abs(bob) * 0.02)
    raise KeyError(anim)


def sway_for(anim, k, s=1.0):
    """Hair follow-through offset at the tips (rest space: +X char left, +Y back, +Z up), metres."""
    n = ANIMS[anim][0]
    if anim == "idle":
        ph = TAU * k / n; return (0.0, 0.002 * math.sin(ph) * s, 0.0)
    if anim == "walk":
        ph = TAU * k / n
        return (0.006 * math.sin(ph) * s, (0.010 + 0.006 * math.cos(2 * ph)) * s, 0.003 * math.cos(2 * ph) * s)
    if anim == "melee":
        p = MELEE_P[k]
        keys = [(0.0, dict(x=0, y=0)), (0.22, dict(x=0.008, y=-0.012)), (0.34, dict(x=0.004, y=-0.004)), (0.48, dict(x=-0.010, y=0.024)),
                (0.62, dict(x=-0.006, y=0.016)), (0.80, dict(x=0.002, y=-0.006)), (1.0, dict(x=0, y=0))]
        d = keyed(p, keys); return (d["x"] * s, d["y"] * s, 0.0)
    if anim == "ranged":
        p = RANGED_P[k]
        keys = [(0.0, dict(y=0)), (0.48, dict(y=-0.004)), (0.58, dict(y=0.008)), (0.86, dict(y=0.0)), (1.0, dict(y=0))]
        return (0.0, keyed(p, keys)["y"] * s, 0.0)
    if anim in ("chop", "mine"):
        ph = k / n
        keys = [(0.0, dict(y=0.004)), (0.36, dict(y=-0.010)), (0.56, dict(y=0.016)), (1.0, dict(y=0.004))]
        return (0.0, keyed(ph, keys)["y"] * s, 0.0)
    if anim == "hit":
        r = (1 - k / (n - 1)) ** 1.6; return (0.0, -0.020 * r * s, 0.004 * r * s)
    return (0.0, 0.0, 0.0)
