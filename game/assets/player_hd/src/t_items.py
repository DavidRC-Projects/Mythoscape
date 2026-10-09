import bpy, sys, time, math
sys.path.insert(0, "/workspace/player_hd/src")
import pl_scene as S
C, H = S.C, S.H
kind = sys.argv[sys.argv.index("--") + 1]
tag = sys.argv[sys.argv.index("--") + 2] if len(sys.argv) > sys.argv.index("--") + 2 else "v2"
B = ["body", "brows"]
combos = {
 "casual": B + ["hair_side_part" if kind == "male" else "hair_ponytail", "top_linen_shirt", "bottom_work_trousers" if kind == "male" else "bottom_long_skirt", "shoes_leather"],
 "jerkin": B + ["hair_crop", "top_leather_jerkin", "bottom_leather_breeches", "shoes_riding_boots", "acc_satchel"],
 "gambeson": B + ["hair_braid", "top_gambeson", "bottom_kilt", "shoes_fur_boots", "acc_scarf"],
 "ranger": B + ["hair_long_straight", "top_ranger_tunic", "bottom_noble_hose", "shoes_sandals", "acc_leather_gloves", "wpn_bow"],
 "doublet": B + ["hair_shoulder_wavy", "top_noble_doublet", "bottom_work_trousers", "shoes_leather", "acc_travel_cloak"],
 "tunic": B + ["hair_crop", "top_wool_tunic", "bottom_long_skirt", "shoes_leather"],
 "o_hunter": B + ["hair_ponytail", "outfit_hunter", "shoes_riding_boots"],
 "o_festival": B + ["hair_braid", "outfit_festival", "shoes_leather"],
 "o_mage": B + ["hair_long_straight", "outfit_mage_robe", "shoes_leather"],
 "o_noble": B + ["hair_side_part", "outfit_noble", "shoes_riding_boots"],
 "armour": B + ["arm_helm", "arm_platebody", "arm_platelegs", "arm_gauntlets", "arm_sabatons", "arm_kiteshield", "wpn_sword"],
 "chain": B + ["hair_crop", "arm_chainbody", "arm_platelegs", "arm_sabatons", "wpn_axe"],
}
t0 = time.time()
sc, ctx = S.build(kind, only=None, hero=True)
print("build", round(time.time() - t0, 1), "errors", list(ctx.errors))
cam = H.persp_camera(sc, (0, 0, ctx.h * 0.52), 4.4, 20, 10, 85, 480, 640)
C.cycles(sc, samples=32, w=480, h=640)
sc.render.use_persistent_data = True
for nm, L in combos.items():
    S.show(ctx, L, skin=["light", "tan", "deep"][hash(nm) % 3])
    for face in (("s", "e") if nm in ("armour", "casual") else ("s",)):
        S.pose(ctx, "idle", 0, face)
        t1 = time.time(); C.render(sc, f"/workspace/player_hd/work/qa_{tag}_{kind}_{nm}_{face}.png"); print("R", nm, face, round(time.time() - t1, 1), flush=True)
