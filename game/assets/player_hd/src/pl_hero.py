"""Hero renders (high samples) for the grey lineup + 4x-style showcase.
blender -b --factory-startup -noaudio --python pl_hero.py -- <kind> [samples]"""
import bpy, sys, os, math
sys.path.insert(0, "/workspace/player_hd/src")
import pl_scene as S
C, H = S.C, S.H
argv = sys.argv[sys.argv.index("--") + 1:]
kind = argv[0]; samples = int(argv[1]) if len(argv) > 1 else 160
OUT = "/workspace/player_hd/work/hero"; os.makedirs(OUT, exist_ok=True)
B = ["body", "brows"]
LOOKS = {
 "male": [
   ("starter", "light", (0.30, 0.20, 0.12), None, B + ["hair_side_part", "top_linen_shirt", "bottom_work_trousers", "shoes_leather"]),
   ("noble", "tan", (0.08, 0.07, 0.07), None, B + ["hair_shoulder_wavy", "top_noble_doublet", "bottom_noble_hose", "shoes_riding_boots", "acc_travel_cloak"]),
   ("ranger", "deep", (0.10, 0.08, 0.07), None, B + ["hair_crop", "outfit_hunter", "shoes_riding_boots", "acc_satchel", "wpn_bow"]),
   ("steel", "light", (0.45, 0.28, 0.14), (170, 175, 185), B + ["arm_helm", "arm_platebody", "arm_platelegs", "arm_gauntlets", "arm_sabatons", "arm_kiteshield", "wpn_sword"]),
 ],
 "female": [
   ("starter", "light", (0.62, 0.40, 0.18), None, B + ["hair_ponytail", "top_linen_shirt", "bottom_long_skirt", "shoes_leather"]),
   ("noble", "deep", (0.06, 0.05, 0.05), None, B + ["hair_long_straight", "outfit_noble", "shoes_leather"]),
   ("mage", "tan", (0.85, 0.72, 0.48), None, B + ["hair_braid", "outfit_mage_robe", "shoes_leather", "acc_scarf", "wpn_staff"]),
   ("bronze", "tan", (0.30, 0.12, 0.06), (200, 150, 75), B + ["arm_helm", "arm_platebody", "arm_platelegs", "arm_gauntlets", "arm_sabatons", "arm_kiteshield", "wpn_sword"]),
 ],
}


def set_hair(col):
    m = bpy.data.materials.get("PL_HairGrey")
    if m:
        for n in m.node_tree.nodes:
            if n.type == "VALTORGB" and n.inputs[0].links and n.inputs[0].links[0].from_socket.name == "Random":
                n.color_ramp.elements[0].color = (*(c * 0.75 for c in col), 1)
                n.color_ramp.elements[1].color = (*(min(1, c * 1.25) for c in col), 1)
    for nm in ("PL_Scalp", "PL_Brow"):
        m = bpy.data.materials.get(nm)
        if m:
            m.node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value = (*(c * 0.8 for c in col), 1)


def set_tier(rgb):
    f = [(c / 255.0) ** 2.2 * 1.35 if rgb else 1.0 for c in (rgb or (255, 255, 255))]
    for nm, base in (("PL_Steel", (0.66, 0.67, 0.70)), ("PL_Mail", (0.55, 0.56, 0.58)), ("PL_SteelDark", (0.45, 0.46, 0.48)), ("PL_BuckleIron2", (0.66, 0.66, 0.68))):
        m = bpy.data.materials.get(nm)
        if m:
            b = m.node_tree.nodes["Principled BSDF"]
            b.inputs["Base Color"].default_value = (*(min(1.0, x * y) for x, y in zip(base, f)), 1)
            for n in m.node_tree.nodes:
                if n.type == "RGB":
                    n.outputs[0].default_value = (*(min(1.0, x * y) for x, y in zip(base, f)), 1)
                if n.type == "MIX" and n.blend_type == "MULTIPLY" and not n.inputs["A"].links:
                    n.inputs["A"].default_value = (*(min(1.0, x * y) for x, y in zip(base, f)), 1)


sc, ctx = S.build(kind, hero=True)
cat = C.shadow_catcher("HeroCatcher", 8.0, (0, 0, 0), ctx.col)
C.cycles(sc, samples=samples, w=int(os.environ.get("PL_HW","1000")), h=int(os.environ.get("PL_HH","1500")))
sc.cycles.use_denoising = True
sc.cycles.use_light_tree = True
H.persp_camera(sc, (0, 0, ctx.h * 0.50), 5.6, 24, 9, 85, int(os.environ.get("PL_HW", "1000")), int(os.environ.get("PL_HH", "1500")))
for name, skin, hair, tier, layers in LOOKS[kind]:
    p = f"{OUT}/{kind}_{name}.png"
    if os.path.exists(p):
        continue
    S.show(ctx, layers, skin=skin)
    ctx.cur_layer = "wpn_staff" if "wpn_staff" in layers else ""
    set_hair(hair); set_tier(tier)
    pose = ("idle", 0, "s") if name not in ("ranger",) else ("idle", 2, "s")
    S.pose(ctx, *pose)
    ctx.arm.rotation_euler = (0, 0, math.radians(-12))
    C.render(sc, p)
print("[hero] done", kind)
