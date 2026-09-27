"""tools/panda_render.py - load every entrance .glb in Panda3D (panda3d-gltf, legacy
materials) with the monster pack's OSRS lighting and render a 3/4 view PNG.
This is the in-engine check: if it looks right here, it looks right in the game.

    /workspace/monsters_venv/bin/python tools/panda_render.py [--only goblin_cave] [--size 768]

Needs: pip install panda3d panda3d-gltf pillow   (monster pack's lighting.py is imported
from ../../monsters/code or from --monsters-code).
"""
import argparse
import glob
import json
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
ap = argparse.ArgumentParser()
ap.add_argument("--only", nargs="*")
ap.add_argument("--size", type=int, default=768)
ap.add_argument("--out", default=os.path.join(ROOT, "panda_renders"))
ap.add_argument("--monsters-code", default=os.path.join(os.path.dirname(ROOT), "monsters", "code"))
ap.add_argument("--no-ground", action="store_true")
args = ap.parse_args()
sys.path.insert(0, args.monsters_code)
sys.path.insert(0, HERE)

SS = 2
from panda3d.core import loadPrcFileData  # noqa: E402
loadPrcFileData("", f"""
window-type offscreen
win-size {args.size * SS} {args.size * SS}
audio-library-name null
sync-video false
gltf-legacy-materials true
""")
from direct.showbase.ShowBase import ShowBase  # noqa: E402
from panda3d.core import Point3, CardMaker, Vec3  # noqa: E402
from PIL import Image  # noqa: E402
try:
    from monsters.lighting import setup_osrs_lighting  # the monster pack's lighting
except ImportError:  # standalone copy of the same function
    from entrance_loader import setup_osrs_lighting
from entrance_loader import load_entrance, ENTRANCE_SUN_HPR  # noqa: E402

BG = (0.62, 0.60, 0.56, 1)


def main():
    base = ShowBase()
    base.disable_mouse()
    base.set_background_color(*BG)
    setup_osrs_lighting(base.render, sun_hpr=ENTRANCE_SUN_HPR)
    lens = base.cam.node().get_lens()
    lens.set_fov(30)
    lens.set_near_far(0.5, 500)
    os.makedirs(args.out, exist_ok=True)
    files = sorted(glob.glob(os.path.join(ROOT, "glb", "*.glb")))
    for f in files:
        key = os.path.splitext(os.path.basename(f))[0]
        if args.only and key not in args.only:
            continue
        model, meta = load_entrance(base.loader, f)
        model.reparent_to(base.render)
        lo, hi = Point3(*meta["bounds_min"]), Point3(*meta["bounds_max"])
        ground = []
        if not args.no_ground:
            R = max(hi.x - lo.x, hi.y - lo.y) * 0.75 + 3
            cx0, cy0 = (lo.x + hi.x) / 2, (lo.y + hi.y) / 2
            rects = [(cx0 - R, cy0 - R, cx0 + R, cy0 + R)]
            cut = meta.get("ground_cutout")
            if cut:     # crypt: leave the stairwell open, same as the Blender concept
                hx, hy = cut["size"][0] / 2, cut["size"][1] / 2
                ax0, ax1 = cut["center"][0] - hx, cut["center"][0] + hx
                ay0, ay1 = cut["center"][1] - hy, cut["center"][1] + hy
                X0, Y0, X1, Y1 = rects[0]
                rects = [(X0, Y0, X1, ay0), (X0, ay1, X1, Y1), (X0, ay0, ax0, ay1), (ax1, ay0, X1, ay1)]
            for (a, b, c, d) in rects:
                cm = CardMaker("ground")
                cm.set_frame(a, c, b, d)
                g = base.render.attach_new_node(cm.generate())
                g.set_p(-90)
                g.set_z(-0.01)
                g.set_color(0x6f / 255, 0x7a / 255, 0x4a / 255, 1)
                ground.append(g)
        ref = os.path.join(ROOT, "ref", key + "_ref_player.glb")
        if os.path.exists(ref):   # the same 1.8 m figure as the concept, for scale
            fig, _ = load_entrance(base.loader, ref)
            fig.reparent_to(base.render)
            ground.append(fig)
        cc = meta["concept_camera"]            # identical camera to the Blender concept
        target = Point3(*cc["target"])
        dist = cc["distance"]
        az, el = math.radians(cc["azimuth_deg"]), math.radians(cc["elevation_deg"])
        lens.set_fov(cc["fov_deg"])
        base.cam.set_pos(target + Vec3(math.sin(az) * math.cos(el), -math.cos(az) * math.cos(el),
                                       math.sin(el)) * dist)
        base.cam.look_at(target)
        base.graphics_engine.render_frame()
        base.graphics_engine.render_frame()
        tmp = os.path.join(args.out, f"_{key}.png")
        base.win.save_screenshot(tmp)
        Image.open(tmp).convert("RGB").resize((args.size, args.size), Image.LANCZOS).save(
            os.path.join(args.out, f"{key}_panda.png"))
        os.remove(tmp)
        print(f"{key:16s} loaded OK  tris(meta)={meta['triangles']}  geoms={len(model.find_all_matches('**/+GeomNode'))}")
        model.remove_node()
        for g in ground:
            g.remove_node()


if __name__ == "__main__":
    main()
