import bpy, sys, time, math
sys.path.insert(0, "/workspace/player_hd/src")
import pl_rig as R
C, H = R.C, R.H
kind = sys.argv[sys.argv.index("--")+1]
sc = C.reset()
col = bpy.data.collections.new("P"); sc.collection.children.link(col)
body, eyes = H.take_body(col, kind)
J = R.joints(body, kind)
for k in ("shoulder_L","elbow_L","wrist_L","knuckle_L","hip_L","knee_L","ankle_L","toe_L","neck","head"):
    print(k, tuple(round(c,3) for c in J[k]))
arm = R.build_armature(col, J)
t0=time.time(); n = R.skin_auto(body, arm); print("skin groups", n, "t", round(time.time()-t0,1))
for e in eyes: R.bone_parent(e, arm, "head")
body.data.materials.append(C.principled("sk", (0.8,0.6,0.5), rough=0.5, sss=0.2))
C.sun(sc, energy=3.0); C.world(sc, strength=0.5)
cam, ppm = H.sprite_camera(sc, h_px=87.8, height_m=1.0, w=192, hgt=256, feet=(96, 236))
C.cycles(sc, samples=24, w=192, h=256)
sc.render.use_persistent_data = True
root = arm
import os
os.makedirs("/workspace/player_hd/work/t", exist_ok=True)
times=[]
for anim, k, face in [("idle",0,"s"),("walk",0,"e"),("walk",2,"e"),("walk",2,"s"),("melee",3,"e"),("melee",4,"e"),("ranged",4,"e"),("chop",2,"e"),("mine",4,"e"),("fish",0,"e")]:
    R.apply_pose(arm, R.pose_for(anim, k, J, kind), J)
    arm.rotation_euler = (0,0,math.radians({"s":0,"e":90,"n":180}[face]))
    t0=time.time(); C.render(sc, f"/workspace/player_hd/work/t/{kind}_{anim}{k}_{face}.png"); times.append(time.time()-t0)
print("render times", [round(x,2) for x in times])
