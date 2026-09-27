"""panda_castle_check.py - in-engine check of the v2 castle in Panda3D through prop_loader.

    DISPLAY=:5 /workspace/monsters_venv/bin/python tools/panda_castle_check.py [--bam]

Renders panda_renders/castle_{game,34}_{closed,open}.png + gate closeups for frames 0/6/11 by
driving the separable gate nodes (castle_bridge / castle_portcullis / castle_chain_l / _r) from
json/render_info.json, reports node + collision counts, and checks the glb carries the animation.
"""
import json
import math
import os
import struct
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
USE_BAM = "--bam" in sys.argv
SIZE = 1100
from panda3d.core import loadPrcFileData  # noqa: E402
loadPrcFileData("", f"""
window-type offscreen
win-size {SIZE} {SIZE}
audio-library-name null
sync-video false
gltf-legacy-materials true
framebuffer-multisample 1
multisamples 4
""")
from direct.showbase.ShowBase import ShowBase  # noqa: E402
from panda3d.core import (Point3, Vec3, CardMaker, OrthographicLens, PerspectiveLens, Mat4,  # noqa: E402
                          AntialiasAttrib)
from PIL import Image  # noqa: E402
from prop_loader import load_prop, setup_osrs_lighting, PROP_SUN_HPR, add_prop_collision  # noqa: E402

RI = json.load(open(os.path.join(ROOT, "json", "render_info.json")))
T = 40 / 26.9
OUT = os.path.join(ROOT, "panda_renders")
os.makedirs(OUT, exist_ok=True)


def glb_animations(path):
    with open(path, "rb") as fh:
        data = fh.read()
    ln = struct.unpack("<I", data[12:16])[0]
    js = json.loads(data[20:20 + ln])
    return [a.get("name") for a in js.get("animations", [])], [n.get("name") for n in js.get("nodes", [])]


def main():
    base = ShowBase()
    base.disable_mouse()
    base.set_background_color(0.55, 0.62, 0.72, 1)
    setup_osrs_lighting(base.render, sun_hpr=PROP_SUN_HPR)
    path = os.path.join(ROOT, "models", "stonehaven_castle_v2." + ("bam" if USE_BAM else "glb"))
    model, meta = load_prop(base.loader, path)
    model.reparent_to(base.render)
    model.set_antialias(AntialiasAttrib.M_multisample)
    hidden = 0
    for gn in model.find_all_matches("**/+GeomNode"):      # blend2bam keeps the COL_/TRIGGER_ cubes as geometry too
        if gn.name.startswith(("COL_", "TRIGGER_")) or gn.get_parent().name.startswith(("COL_", "TRIGGER_")):
            gn.hide(); hidden += 1
    for cn in model.find_all_matches("**/+CollisionNode"):   # blend2bam leaves them visible
        cn.hide(); hidden += 1
    report = {"collision_nodes_hidden": hidden, "file": os.path.relpath(path, ROOT), "geomnodes": model.find_all_matches("**/+GeomNode").get_num_paths()}
    gate = {}
    for nm in ("bridge", "portcullis", "chain_l", "chain_r"):
        np_ = model.find("**/castle_" + nm)
        report["node_castle_" + nm] = not np_.is_empty()
        gate[nm] = np_
    solids, trig = add_prop_collision(model, meta)
    report["collision_nodes"] = len(solids) + (1 if trig else 0)
    if not USE_BAM:
        anims, nodes = glb_animations(path)
        report["glb_animations"] = anims
    # ground around the castle (plaza south, grass elsewhere)
    W = 24 * T
    for (x0, x1, y0, y1, col) in ((-60, W + 60, 0, 60, (0.37, 0.48, 0.24)), (-60, 0, -W, 0, (0.37, 0.48, 0.24)),
                                  (W, W + 60, -W, 0, (0.37, 0.48, 0.24)), (-60, W + 60, -W - 60, -W, (0.56, 0.55, 0.51))):
        cm = CardMaker("g")
        cm.set_frame(x0, x1, y0, y1)
        g = base.render.attach_new_node(cm.generate())
        g.set_p(-90)
        g.set_z(-0.01)
        g.set_color(*col, 1)
    fig, _ = load_prop(base.loader, os.path.join(ROOT, "models", "ref_player_1p8m.glb"))
    fig.reparent_to(base.render)
    fig.set_pos(RI["hinge_m"][0] + 0.9, -24.5 * T, 0.06)

    def pose(f):
        for nm, np_ in gate.items():
            if np_.is_empty():
                continue
            m = RI["frames"][f]["matrices"][nm]
            # Blender (column vectors) -> Panda (row vectors): transpose
            np_.set_mat(model, Mat4(*[m[c][r] for r in range(4) for c in range(4)]))

    def shot(name, az, el, target, ortho=None, dist=80, fov=30, size=SIZE):
        azr, elr = math.radians(az), math.radians(el)
        back = Vec3(math.sin(azr) * math.cos(elr), -math.cos(azr) * math.cos(elr), math.sin(elr))
        if ortho:
            lens = OrthographicLens()
            lens.set_film_size(ortho, ortho)
            lens.set_near_far(1, 600)
            dist = 250
        else:
            lens = PerspectiveLens()
            lens.set_fov(fov)
            lens.set_near_far(0.5, 800)
        base.cam.node().set_lens(lens)
        base.cam.set_pos(Point3(*target) + back * dist)
        base.cam.look_at(Point3(*target))
        base.graphics_engine.render_frame()
        base.graphics_engine.render_frame()
        p = os.path.join(OUT, name)
        base.win.save_screenshot(p)
        Image.open(p).convert("RGB").save(p)
        return p

    tag = "bam" if USE_BAM else "glb"
    C = 12 * T
    gx, hy = RI["hinge_m"][0], RI["hinge_m"][1]
    for f, st in ((0, "closed"), (NF_OPEN, "open")):
        pose(f)
        shot(f"castle_game_{st}_{tag}.png", 0, 32, (C, -C, 6), ortho=44)
        shot(f"castle_34_{st}_{tag}.png", 35, 28, (C, -C - 2, 5), dist=95, fov=38)
    for f in (0, 6, NF_OPEN):
        pose(f)
        shot(f"gate_frame{f:02d}_{tag}.png", 20, 20, (gx, hy - 2.0, 2.8), dist=22, fov=36)
    print(json.dumps(report, indent=1))
    with open(os.path.join(OUT, f"panda_report_{tag}.json"), "w") as fh:
        json.dump(report, fh, indent=1)


NF_OPEN = len(RI["frames"]) - 1
if __name__ == "__main__":
    main()
