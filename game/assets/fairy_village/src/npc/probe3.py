import bpy, sys
sys.argv += []
exec(open("/workspace/fairy_village/src/npc/fv_npc.py").read().split("# ------------------------------------------------------------------ cameras")[0])
for kind in ("female", "male"):
    for o in list(bpy.data.objects): bpy.data.objects.remove(o)
    body, eyes = load_body(kind)
    t = bvh(body)
    print(kind, "eyes", [tuple(round(c,3) for c in e.matrix_world.translation) for e in eyes])
    zs = [v.co.z for v in body.data.vertices]; print("height", max(zs))
    for zi in range(130, 152):
        z = zi / 100 * max(zs) / 1.617
        h, n = surf(t, (0, -0.5, z), (0, 1, 0))
        print(round(z,3), round(h.y,4) if h else None)
