"""Scene setup shared by tests + the batch renderer."""
import bpy, sys, math, os
sys.path.insert(0, "/workspace/player_hd/src")
sys.path.insert(0, "/workspace/npc_hd_overworld/batch4/src")
sys.path.insert(0, "/workspace/fairy_village/src/blender")
import fv_common as C
import fv_npc_helpers as H
import pl_rig as R
import pl_mats as M
import pl_items as I

HOLD_SHRINK = float(os.environ.get("PL_HOLD_SHRINK", "0.008"))
FACE_ROT = {"s": 0, "e": 90, "n": 180, "w": -90}


def lights(sc, hero=False):
    C.world(sc, top=(0.30, 0.34, 0.55), bottom=(0.55, 0.48, 0.42), strength=0.42 if hero else 0.5)
    C.sun(sc, energy=2.8 if hero else 3.2, color=(1.0, 0.88, 0.74), rot=(40, 15, -30), name="Key")
    C.sun(sc, energy=1.2, color=(0.60, 0.70, 1.0), rot=(60, 0, 160), name="Rim")
    if hero:
        a = bpy.data.lights.new("Fill", "AREA"); a.energy = 40; a.size = 2.0; a.color = (0.85, 0.9, 1.0)
        o = bpy.data.objects.new("Fill", a); o.location = (2.0, -2.5, 1.6); o.rotation_euler = (math.radians(70), 0, math.radians(40)); sc.collection.objects.link(o)
        a2 = bpy.data.lights.new("Kick", "AREA"); a2.energy = 70; a2.size = 1.0; a2.color = (1.0, 0.9, 0.85)
        o2 = bpy.data.objects.new("Kick", a2); o2.location = (-1.4, 1.8, 2.0); o2.rotation_euler = (math.radians(-60), 0, math.radians(-145)); sc.collection.objects.link(o2)


def build(kind, only=None, hero=False):
    sc = C.reset()
    col = bpy.data.collections.new("P"); sc.collection.children.link(col)
    ctx = I.build_all(kind, col, only=only)
    M.setup_aov(sc)
    lights(sc, hero)
    return sc, ctx


def show(ctx, layers, skin="light", holdout_body=False):
    on = set(layers)
    for lid, objs in ctx.layers.items():
        for o in objs:
            hid = lid not in on and not (holdout_body and lid == "body")
            o.hide_render = hid
            o.hide_viewport = hid          # keeps hidden layers out of depsgraph evaluation (big speed win)
            o.is_holdout = holdout_body and lid == "body"
    b = ctx.body
    b.data.materials[0] = ctx.skin_mats[skin]
    # holdout is a slightly shrunk body: garment surfaces that dip a few mm inside the skin (buttocks, hips) are no longer cut out
    m = b.modifiers.get("HoldShrink")
    if m is None:
        m = b.modifiers.new("HoldShrink", "DISPLACE"); m.strength = -HOLD_SHRINK; m.mid_level = 0.0
    m.show_render = m.show_viewport = bool(holdout_body)


def pose(ctx, anim, k, face):
    P = R.pose_for(anim, k, ctx.J, ctx.kind)
    if anim == "death":
        P["fall_axis"] = "x" if face == "e" else "y"
    if getattr(ctx, "cur_layer", "") == "wpn_staff" and anim != "melee":
        P["pr_R"] = P.get("pr_R", 0.0) + R.STAFF_FLIP     # staff carried head-up (melee swings it head-first like a sword)
    R.apply_pose(ctx.arm, P, ctx.J)
    import pl_hair
    hs = [o for lid, objs in ctx.layers.items() if lid.startswith("hair_") for o in objs if o.type == "CURVES"]
    if hs:
        pl_hair.set_sway(hs, R.sway_for(anim, k, ctx.s))
    ctx.arm.rotation_euler = (0, 0, math.radians(FACE_ROT[face]))
