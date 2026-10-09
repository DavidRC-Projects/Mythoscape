"""Face/hair test: close-up + 2x sprite. blender ... -- <kind> <layers comma> <out>"""
import bpy, sys, math
sys.path.insert(0, "/workspace/player_hd/src")
import pl_scene as S
from mathutils import Vector
argv = sys.argv[sys.argv.index("--") + 1:]
kind, layers, out = argv[0], argv[1].split(","), argv[2]
anim = argv[3] if len(argv) > 3 else "idle"; k = int(argv[4]) if len(argv) > 4 else 0; face = argv[5] if len(argv) > 5 else "s"
sc, ctx = S.build(kind, only=set(layers))
C, H = S.C, S.H
S.show(ctx, ["body", "brows"] + layers, skin=argv[6] if len(argv) > 6 else "light")
S.pose(ctx, anim, k, face)
C.cycles(sc, samples=48, w=288, h=288)
sc.view_settings.view_transform = "AgX"
H.sprite_camera(sc, h_px=87.8, height_m=1.0, w=288, hgt=288, feet=(144, 248))
C.render(sc, out + "_2x.png")
# close-up: same 30deg ortho camera, zoomed on the head
cam = sc.camera
cam.data.ortho_scale = 0.42
top = ctx.J["top"]
el = math.radians(30)
d = Vector((0, -math.cos(el), math.sin(el)))
cam.location = Vector((0, 0, top.z - 0.15)) + d * 5
C.cycles(sc, samples=96, w=420, h=420)
C.render(sc, out + "_close.png")
print("TF done")
