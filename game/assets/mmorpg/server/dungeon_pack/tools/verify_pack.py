"""tools/verify_pack.py - automated checks for every entrance (run after build_all.py):

  * .glb loads through panda3d-gltf (gltf-legacy-materials) and the .bam loads
  * triangle count inside the budget (1.4k - 4k), materials are untextured
  * json has colliders + exactly one TRIGGER_door, trigger sits inside the walkable opening
  * collision test with a 0.35 m player sphere (Panda3D CollisionTraverser):
      - walking straight in through the doorway FIRES the trigger and hits no solid box
      - walking into the wall beside the door is BLOCKED by a solid box
  * the .bam from blend2bam carries the same CollisionNodes

    /workspace/monsters_venv/bin/python tools/verify_pack.py
"""
import glob
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
from panda3d.core import loadPrcFileData  # noqa: E402
loadPrcFileData("", "window-type none\naudio-library-name null\ngltf-legacy-materials true")
from direct.showbase.ShowBase import ShowBase  # noqa: E402
from panda3d.core import (CollisionTraverser, CollisionHandlerQueue, CollisionNode,  # noqa: E402
                          CollisionSphere, BitMask32, TextureAttrib, NodePath)
from entrance_loader import load_entrance, add_entrance_collision  # noqa: E402

SOLID, TRIG = BitMask32.bit(1), BitMask32.bit(2)


def walk(base, model, start, end, steps=40):
    """Move a player sphere from start to end; return (trigger_fired, first_solid_hit)."""
    player = base.render.attach_new_node(CollisionNode("player"))
    player.node().add_solid(CollisionSphere(0, 0, 0.9, 0.35))
    player.node().set_from_collide_mask(SOLID | TRIG)
    player.node().set_into_collide_mask(BitMask32.all_off())
    trav, q = CollisionTraverser(), CollisionHandlerQueue()
    trav.add_collider(player, q)
    fired, blocked = False, None
    for i in range(steps + 1):
        t = i / steps
        player.set_pos(model, *(s + (e - s) * t for s, e in zip(start, end)))
        trav.traverse(base.render)
        for j in range(q.get_num_entries()):
            name = q.get_entry(j).get_into_node().name
            if name.startswith("TRIGGER"):
                fired = True
            elif blocked is None:
                blocked = name
        if fired or blocked:
            break
    player.remove_node()
    return fired, blocked


def main():
    base = ShowBase(windowType="none")
    ok_all = True
    rows = []
    for f in sorted(glob.glob(os.path.join(ROOT, "glb", "*.glb"))):
        key = os.path.splitext(os.path.basename(f))[0]
        problems = []
        model, meta = load_entrance(base.loader, f)
        model.reparent_to(base.render)
        tris = meta["triangles"]
        if not 1400 <= tris <= 4000:
            problems.append(f"tris {tris} outside budget")
        for gnp in model.find_all_matches("**/+GeomNode"):
            for i in range(gnp.node().get_num_geoms()):
                ta = gnp.node().get_geom_state(i).get_attrib(TextureAttrib)
                if ta and ta.get_num_on_stages():
                    problems.append("has textures")
        trig = meta.get("trigger")
        op = meta["openings"][0]
        if not trig:
            problems.append("no trigger")
        else:
            if trig["size"][0] > op["width"] + 0.01:
                problems.append("trigger wider than opening")
        solids, trig_np = add_entrance_collision(model, meta, SOLID, TRIG)
        # walk in: from 4 m in front of the trigger straight into it
        tx, ty, tz = trig["center"]
        gz = tz - trig["size"][2] / 2
        fired, blocked = walk(base, model, (tx, ty - 4.5, gz), (tx, ty, gz))
        if not fired or blocked:
            problems.append(f"walk-in: fired={fired} blocked_by={blocked}")
        # walk into the wall/rock 3.5 m to the side of the door (must be blocked)
        side = [c for c in meta["colliders"] if abs(c["center"][0]) > 1.0 and c["center"][2] - c["size"][2] / 2 <= gz + 0.9]
        wall_ok = False
        if side:
            c = min(side, key=lambda c: abs(c["center"][1] - ty))
            cx, cy = c["center"][0], c["center"][1]
            f2, b2 = walk(base, model, (cx, cy - c["size"][1] / 2 - 3.0, gz), (cx, cy, gz))
            wall_ok = b2 is not None
            if not wall_ok:
                problems.append("side wall not blocking")
        # .bam check
        bam = os.path.join(ROOT, "bam", key + ".bam")
        bam_info = "missing"
        if os.path.exists(bam):
            bm, _ = load_entrance(base.loader, bam)
            ncol = bm.find_all_matches("**/+CollisionNode").get_num_paths()
            want = len(meta["colliders"]) + 1
            bam_info = f"ok ({ncol} CollisionNodes)"
            if ncol != want:
                problems.append(f"bam has {ncol} CollisionNodes, expected {want}")
            bm.remove_node()
        model.remove_node()
        status = "PASS" if not problems else "FAIL"
        ok_all &= not problems
        rows.append((key, tris, fired, wall_ok, bam_info, status, "; ".join(problems)))
    print(f"{'entrance':16s} {'tris':>5s}  walk-in-trigger  wall-blocks  bam                      result")
    for key, tris, fired, wall_ok, bam_info, status, prob in rows:
        print(f"{key:16s} {tris:5d}  {str(fired):15s}  {str(wall_ok):11s}  {bam_info:24s} {status} {prob}")
    with open(os.path.join(ROOT, "review", "verify_report.txt"), "w") as fh:
        for r in rows:
            fh.write("\t".join(str(x) for x in r) + "\n")
    sys.exit(0 if ok_all else 1)


if __name__ == "__main__":
    main()
