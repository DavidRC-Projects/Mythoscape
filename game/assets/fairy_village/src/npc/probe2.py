import bpy
from mathutils import Vector
p = "/workspace/fairy_village/src/basemesh/human-base-meshes-bundle-v1.4.1/human_base_meshes_bundle.blend"
with bpy.data.libraries.load(p) as (src, dst):
    dst.objects = [n for n in src.objects if n.startswith("GEO-body_female_stylized")]
for o in dst.objects:
    bpy.context.scene.collection.objects.link(o)
bpy.context.view_layer.update()
b = [o for o in dst.objects if o.name == "GEO-body_female_stylized"][0]
print("body loc", b.location, b.rotation_euler, b.scale)
for o in dst.objects:
    if o is not b:
        print(o.name, "world", o.matrix_world.translation, "local", o.location, o.rotation_euler, o.scale)
vs = [b.matrix_world @ v.co for v in b.data.vertices]
cx = b.matrix_world.translation.x
for z in [1.6,1.55,1.5,1.45,1.4,1.35,1.3,1.25,1.2,1.1,1.0,0.9,0.8,0.7,0.6]:
    sl = [v for v in vs if abs(v.z - z) < 0.008]
    if sl:
        xs = [v.x - cx for v in sl]; ys = [v.y for v in sl]
        print("z", z, "x", round(min(xs),3), round(max(xs),3), "y", round(min(ys),3), round(max(ys),3), len(sl))
