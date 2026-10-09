import bpy, sys, time
sys.path.insert(0, "/workspace/player_hd/src")
import pl_scene as S
C, H = S.C, S.H
kind = sys.argv[sys.argv.index("--") + 1]
L = ["body", "brows", "hair_crop", "arm_platebody", "arm_platelegs", "arm_helm", "wpn_sword", "arm_kiteshield"]
sc, ctx = S.build(kind, only=set(L))
H.sprite_camera(sc, h_px=87.8, height_m=1.0, w=192, hgt=256, feet=(96, 236))
C.cycles(sc, samples=12, w=192, h=256); sc.render.use_persistent_data = True
S.show(ctx, L)
for anim, n in (("death", 8), ("hit", 4)):
    for f in ("s", "e", "n"):
        for k in range(n):
            S.pose(ctx, anim, k, f)
            C.render(sc, f"/workspace/player_hd/work/td/{kind}_{anim}_{f}_{k}.png")
for k in (3, 4, 5):
    S.pose(ctx, "melee", k, "e"); C.render(sc, f"/workspace/player_hd/work/td/{kind}_melee_e_{k}.png")
