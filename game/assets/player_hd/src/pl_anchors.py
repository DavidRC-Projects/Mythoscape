"""Per-frame anchor points (2x canvas px) for hitsplats / HP bar / projectile origins.
blender -b --factory-startup -noaudio --python pl_anchors.py"""
import bpy, sys, json, math
sys.path.insert(0, "/workspace/player_hd/src")
import pl_scene as S
import pl_rig as R
import pl_items as I
from mathutils import Vector
from bpy_extras.object_utils import world_to_camera_view
C, H = S.C, S.H
OUT = {}
W, HH = 288, 288
for kind in ("male", "female"):
    wl = {w[0] for w in I.WEAPONS}
    sc, ctx = S.build(kind, only=wl)
    cam, ppm = H.sprite_camera(sc, h_px=87.8, height_m=1.0, w=W, hgt=HH, feet=(144, 248))
    arm = ctx.arm
    bpy.context.view_layer.update()
    rest = {b.name: arm.matrix_world @ b.bone.matrix_local for b in arm.pose.bones}
    # local offsets in bone rest space
    loc = {"head_top": ("head", rest["head"].inverted() @ (ctx.J["top"] + Vector((0, 0, 0.01)))),
           "chest": ("chest", rest["chest"].inverted() @ (ctx.J["chest"] + Vector((0, -0.10 * ctx.s, 0.04 * ctx.s)))),
           "hand_R": ("prop_R", Vector((0, 0, 0))), "hand_L": ("prop_L", Vector((0, 0, 0)))}
    tips = {}
    for lid, b, match, anims in I.WEAPONS:
        bone = "prop_L" if lid == "wpn_bow" else "prop_R"
        g = rest[bone].translation
        best, bd = None, -1
        for o in ctx.layers.get(lid, []):
            if o.type != "MESH":
                continue
            mw = o.matrix_world
            for v in o.data.vertices:
                p = mw @ v.co
                d = (p - g).length
                if d > bd:
                    bd, best = d, p
        if lid == "wpn_bow":   # bow: arrow leaves from the grip / string centre, not the limb tip
            best = g
        tips[lid] = (bone, rest[bone].inverted() @ best, set(anims))
    res = {}
    for anim, (n, facings, loop, doc) in R.ANIMS.items():
        res[anim] = {}
        for f in facings:
            frames = []
            for k in range(n):
                S.pose(ctx, anim, k, f)
                bpy.context.view_layer.update()
                d = {}

                def px(bone, off):
                    p = arm.matrix_world @ arm.pose.bones[bone].matrix @ off
                    u = world_to_camera_view(sc, cam, p)
                    return [round(u.x * W, 1), round((1 - u.y) * HH, 1)]
                for nm, (bone, off) in loc.items():
                    d[nm] = px(bone, off)
                d["tip"] = {lid: px(bone, off) for lid, (bone, off, an) in tips.items() if anim in an}
                if "wpn_staff" in d["tip"] and anim != "melee":      # staff is carried head-up outside melee
                    ctx.cur_layer = "wpn_staff"; S.pose(ctx, anim, k, f); bpy.context.view_layer.update()
                    bone, off, an = tips["wpn_staff"]; d["tip"]["wpn_staff"] = px(bone, off)
                    ctx.cur_layer = ""
                frames.append(d)
            res[anim][f] = frames
    OUT[kind] = res
json.dump({"scale": "2x canvas px (288x288, feet 144,248); 1x = /2, 4x = x2; w facing: x' = 288 - x",
           "points": {"head_top": "top of the head (+1 cm): place HP bar / nameplate / overhead icons above this",
                      "chest": "centre of mass in front of the chest: hitsplat + magic impact point on the player",
                      "hand_R": "weapon grip (main hand)", "hand_L": "off-hand / bow grip = arrow origin",
                      "tip": "weapon tip per weapon layer for the anims that weapon is drawn in (melee contact, chop/mine impact, rod tip = fishing line)"},
           "anchors": OUT}, open("/workspace/player_hd/assets/anchors.json", "w"))
print("[anchors] ok")
