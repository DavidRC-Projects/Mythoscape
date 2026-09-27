"""Export the kit's 1.8 m reference figure at the origin -> models/ref_player_1p8m.glb (scale checks)."""
import os
import sys
import bpy
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import castle_geo as cg  # noqa: E402
ARGS = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
OUT = ARGS[ARGS.index("--out") + 1] if "--out" in ARGS else "/workspace/castle"
k = cg.PartKit("ref", cg.PAL, seed=1)
k.figure((0, 0, 0))
k.palette.update({"ref_legs": "#3d4a63", "ref_shirt": "#8f2f2a", "ref_skin": "#d2a47c", "ref_hair": "#4a3526"})
mats = k._materials()
col = bpy.data.collections.new("REF")
bpy.context.scene.collection.children.link(col)
v, f = k._ref[0]
k._make_object("REF_player_1p8m", v, f, mats, col)
vl = bpy.context.view_layer
vl.active_layer_collection = vl.layer_collection.children["REF"]
os.makedirs(os.path.join(OUT, "models"), exist_ok=True)
bpy.ops.export_scene.gltf(filepath=os.path.join(OUT, "models", "ref_player_1p8m.glb"), export_format="GLB",
                          use_active_collection=True, export_texcoords=False, export_materials="EXPORT", export_yup=True)
