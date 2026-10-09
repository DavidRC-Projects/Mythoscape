import bpy, sys, os
sys.path.insert(0, "/workspace/player_hd/src")
import pl_scene as S, pl_rig as R, pl_items as I
from mathutils import Vector
from bpy_extras.object_utils import world_to_camera_view
kind = sys.argv[sys.argv.index("--")+1]
sc, ctx = S.build(kind, only={"wpn_sword"})
cam, ppm = S.H.sprite_camera(sc, h_px=87.8, height_m=1.0, w=288, hgt=288, feet=(144, 248))
arm = ctx.arm; bpy.context.view_layer.update()
rest = arm.matrix_world @ arm.pose.bones["prop_R"].bone.matrix_local
g = rest.translation; best, bd = None, -1
for o in ctx.layers["wpn_sword"]:
    if o.type == "MESH":
        for v in o.data.vertices:
            p = o.matrix_world @ v.co
            if (p-g).length > bd: bd, best = (p-g).length, p
off = rest.inverted() @ best
def px(p):
    u = world_to_camera_view(sc, cam, p); return (round(u.x*288), round((1-u.y)*288))
for k in range(10):
    S.pose(ctx, "melee", k, "e"); bpy.context.view_layer.update()
    m = arm.matrix_world @ arm.pose.bones["prop_R"].matrix
    print("PROBE", k, R.MELEE_P[k], "hand", px(m.translation), "tip", px(m @ off))
