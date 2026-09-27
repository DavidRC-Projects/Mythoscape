"""tools/panda_render.py - the in-engine check. Loads every prop .glb (or .bam with --bam) in
Panda3D through prop_loader (panda3d-gltf legacy materials + the sRGB/ambient/emission fixes)
under the monster pack's OSRS lighting and renders:
    panda_renders/<key>_panda.png    - the GAME camera (ortho, az 0, el 32), same framing as the
                                       Blender concept (json concept_camera)
    panda_renders/<key>_panda34.png  - the OSRS 3/4 perspective (az 35, el 30, fov 30)
both with the same 1.8 m reference figure and floor colour as the concept.

    /workspace/monsters_venv/bin/python tools/panda_render.py [--only furnace anvil] [--size 640] [--bam]
"""
import argparse
import glob
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
ap = argparse.ArgumentParser()
ap.add_argument("--only", nargs="*")
ap.add_argument("--size", type=int, default=640)
ap.add_argument("--bam", action="store_true", help="load bam/<key>.bam instead of glb/<key>.glb")
ap.add_argument("--out", default=os.path.join(ROOT, "panda_renders"))
args = ap.parse_args()
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
from panda3d.core import Point3, CardMaker, Vec3, OrthographicLens, PerspectiveLens  # noqa: E402
from PIL import Image  # noqa: E402
from prop_loader import load_prop, setup_osrs_lighting, PROP_SUN_HPR  # noqa: E402

BG = (0.62, 0.60, 0.56, 1)


def hex_rgb(h):
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) / 255 for i in (0, 2, 4))


def main():
    base = ShowBase()
    base.disable_mouse()
    base.set_background_color(*BG)
    setup_osrs_lighting(base.render, sun_hpr=PROP_SUN_HPR)
    os.makedirs(args.out, exist_ok=True)
    ext = "bam" if args.bam else "glb"
    for f in sorted(glob.glob(os.path.join(ROOT, ext, "*." + ext))):
        key = os.path.splitext(os.path.basename(f))[0]
        if args.only and key not in args.only:
            continue
        model, meta = load_prop(base.loader, f)
        model.reparent_to(base.render)
        lo, hi = Point3(*meta["bounds_min"]), Point3(*meta["bounds_max"])
        extra = []
        R = max(hi.x - lo.x, hi.y - lo.y) * 0.75 + 2.5
        cx0, cy0 = (lo.x + hi.x) / 2, (lo.y + hi.y) / 2
        cm = CardMaker("ground")
        cm.set_frame(cx0 - R, cx0 + R, cy0 - R, cy0 + R)
        g = base.render.attach_new_node(cm.generate())
        g.set_p(-90)
        g.set_z(-0.01)
        g.set_color(*hex_rgb(meta.get("concept_ground", "#7a6448")), 1)
        extra.append(g)
        ref = os.path.join(ROOT, "ref", key + "_ref_player.glb")
        if os.path.exists(ref):
            fig, _ = load_prop(base.loader, ref)
            fig.reparent_to(base.render)
            extra.append(fig)
        cc = meta["concept_camera"]
        target = Point3(*cc["target"])
        for suffix, (az, el) in (("panda", (cc["azimuth_deg"], cc["elevation_deg"])), ("panda34", (35.0, 30.0))):
            azr, elr = math.radians(az), math.radians(el)
            back = Vec3(math.sin(azr) * math.cos(elr), -math.cos(azr) * math.cos(elr), math.sin(elr))
            if suffix == "panda" and cc.get("type") == "ortho":
                lens = OrthographicLens()
                lens.set_film_size(cc["ortho_scale"], cc["ortho_scale"])
                lens.set_near_far(0.1, 300)
                dist = 60
            else:
                lens = PerspectiveLens()
                lens.set_fov(30)
                lens.set_near_far(0.3, 300)
                span = max(hi.x - lo.x, hi.y - lo.y, hi.z - max(lo.z, 0)) + 1.2
                dist = span / (2 * math.tan(math.radians(15))) * 0.9 + 0.8
            base.cam.node().set_lens(lens)
            base.cam.set_pos(target + back * dist)
            base.cam.look_at(target)
            base.graphics_engine.render_frame()
            base.graphics_engine.render_frame()
            tmp = os.path.join(args.out, f"_{key}.png")
            base.win.save_screenshot(tmp)
            Image.open(tmp).convert("RGB").resize((args.size, args.size), Image.LANCZOS).save(
                os.path.join(args.out, f"{key}_{suffix}.png"))
            os.remove(tmp)
        print(f"{key:18s} {ext} loaded OK  tris(meta)={meta['triangles']:5d}  "
              f"geomnodes={model.find_all_matches('**/+GeomNode').get_num_paths()}")
        model.remove_node()
        for e in extra:
            e.remove_node()


if __name__ == "__main__":
    main()
