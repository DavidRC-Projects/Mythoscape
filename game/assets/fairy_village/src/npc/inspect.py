import bpy, sys
from mathutils import Vector
p = "/workspace/fairy_village/src/basemesh/human-base-meshes-bundle-v1.4.1/human_base_meshes_bundle.blend"
with bpy.data.libraries.load(p) as (src, dst):
    dst.objects = [n for n in src.objects if n.startswith("GEO-body") and "stylized" in n and "primitive" not in n]
for o in dst.objects:
    bpy.context.scene.collection.objects.link(o)
    me = o.data
    if o.type != 'MESH':
        print('OBJ', o.name, o.type); continue
    vs = [o.matrix_world @ v.co for v in me.vertices]
    print("OBJ", o.name, len(vs), "mods", [m.type for m in o.modifiers], "mats", [m.name for m in me.materials if m], "parent", o.parent.name if o.parent else None)
    if "body" in o.name:
        xs = [v.x for v in vs]; zs = [v.z for v in vs]
        cx = sum(xs)/len(xs)
        print(" bbox x", min(xs), max(xs), "z", min(zs), max(zs), "cx", cx)
        # arm: hand extremity
        far = max(vs, key=lambda v: v.x)
        print(" right-most vert", far)
        for z in [1.5,1.45, 1.4,1.35, 1.3,1.25, 1.2, 1.1, 1.0, 0.9, 0.8, 0.7]:
            sl = [v.x - cx for v in vs if abs(v.z - z) < 0.01]
            print("  z", z, "xmax", round(max(sl),3) if sl else None, "n", len(sl))
        print(" vgroups", [g.name for g in o.vertex_groups][:30], "shapekeys", me.shape_keys and [k.name for k in me.shape_keys.key_blocks])
