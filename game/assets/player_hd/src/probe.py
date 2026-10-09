import bpy, sys
sys.path.insert(0, "/workspace/fairy_village/src/blender"); sys.path.insert(0, "/workspace/npc_hd_overworld/batch4/src")
import fv_common as C, fv_npc_helpers as H
for kind in ("male", "female"):
    C.reset()
    col = bpy.data.collections.new(kind); bpy.context.scene.collection.children.link(col)
    body, eyes = H.take_body(col, kind)
    V = body.data.vertices
    zs = [v.co.z for v in V]; print(kind, "verts", len(V), "zmax", max(zs), "eyes", [tuple(round(c,3) for c in e.location) for e in eyes])
    h = max(zs)
    mask = H.arm_mask(body, h)
    arm = [V[i].co for i in range(len(V)) if mask[i] and V[i].co.x > 0]
    lo = min(arm, key=lambda p: p.z); hi = max(arm, key=lambda p: p.z); far = max(arm, key=lambda p: p.x)
    print(" arm lowest", tuple(round(c,3) for c in lo), "highest", tuple(round(c,3) for c in hi), "farx", tuple(round(c,3) for c in far))
    for z in (0.05, 0.1, 0.3, 0.5, 0.7, 0.9, 1.0, 1.1, 1.2, 1.3, 1.4, 1.5):
        pts = [V[i].co for i in range(len(V)) if abs(V[i].co.z - z) < 0.01 and not mask[i]]
        if pts:
            print("  z", z, "x", round(min(p.x for p in pts),3), round(max(p.x for p in pts),3), "y", round(min(p.y for p in pts),3), round(max(p.y for p in pts),3))
    print(" vgroups", len(body.vertex_groups), [g.name for g in body.vertex_groups][:10])
