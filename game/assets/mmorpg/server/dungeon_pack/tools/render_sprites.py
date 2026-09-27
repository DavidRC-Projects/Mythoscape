"""tools/render_sprites.py - the 2D route: render every entrance .glb from a FIXED camera to
transparent PNGs at several sizes, plus a JSON with the pixel anchors a pygame game needs.

    /workspace/monsters_venv/bin/python tools/render_sprites.py                  # all, defaults
    /workspace/monsters_venv/bin/python tools/render_sprites.py --only wolf_den --views front34 --sizes 256

Views (orthographic, so there is no perspective drift across the map):
    front34 : camera straight in front, 35 deg down  (classic top-down 3/4 RPG view)
    iso     : camera front-right 45 deg, 30 deg down (2:1-ish isometric)
    osrs    : front-right 35 deg, 30 deg down        (same angle as the concept renders)

Output: sprites/<view>/<key>_<size>.png  (size = sprite WIDTH in px, height follows the shape)
        sprites/<view>/<key>.json         anchors per size:
            origin_px  - where model origin (centre of the doorway threshold, ground level) lands
            door_px    - centre of the doorway trigger at ground level
            trigger_px - the trigger box footprint as a 4-point polygon (for 2D hit tests)
            metres_per_px
Blit so that origin_px sits on the old entrance's world position; keep the old trigger logic.
Lighting = the monster pack's OSRS lighting (sun mirrored because entrances face -Y).
"""
import argparse
import glob
import json
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
ap = argparse.ArgumentParser()
ap.add_argument("--only", nargs="*")
ap.add_argument("--views", nargs="*", default=["front34", "iso", "osrs"])
ap.add_argument("--sizes", nargs="*", type=int, default=[128, 256, 512])
ap.add_argument("--out", default=os.path.join(ROOT, "sprites"))
ap.add_argument("--ss", type=int, default=3, help="supersample factor")
args = ap.parse_args()
VIEWS = {"front34": (0.0, 35.0), "iso": (45.0, 30.0), "osrs": (35.0, 30.0)}
MAXW = max(args.sizes) * args.ss

from panda3d.core import loadPrcFileData  # noqa: E402
loadPrcFileData("", f"""
window-type offscreen
win-size {MAXW} {MAXW}
framebuffer-alpha true
audio-library-name null
sync-video false
gltf-legacy-materials true
""")
from direct.showbase.ShowBase import ShowBase  # noqa: E402
from panda3d.core import (OrthographicLens, Vec3, Point3, Texture, GraphicsOutput,  # noqa: E402
                          FrameBufferProperties, WindowProperties, GraphicsPipe)
from PIL import Image  # noqa: E402
from entrance_loader import load_entrance, setup_osrs_lighting, ENTRANCE_SUN_HPR  # noqa: E402


def cam_basis(az_deg, el_deg):
    az, el = math.radians(az_deg), math.radians(el_deg)
    back = Vec3(math.sin(az) * math.cos(el), -math.cos(az) * math.cos(el), math.sin(el))  # towards camera
    fwd = -back
    right = fwd.cross(Vec3(0, 0, 1))
    right.normalize()
    up = right.cross(fwd)
    up.normalize()
    return back, right, up


def main():
    base = ShowBase()
    base.disable_mouse()
    setup_osrs_lighting(base.render, sun_hpr=ENTRANCE_SUN_HPR)
    files = sorted(glob.glob(os.path.join(ROOT, "glb", "*.glb")))
    for f in files:
        key = os.path.splitext(os.path.basename(f))[0]
        if args.only and key not in args.only:
            continue
        model, meta = load_entrance(base.loader, f)
        model.reparent_to(base.render)
        # every vertex of the model, for a tight fit
        pts = []
        for gnp in model.find_all_matches("**/+GeomNode"):
            mat = gnp.get_mat(base.render)
            for geom in gnp.node().get_geoms():
                from panda3d.core import GeomVertexReader
                r = GeomVertexReader(geom.get_vertex_data(), "vertex")
                while not r.is_at_end():
                    pts.append(mat.xform_point(r.get_data3()))
        for view in args.views:
            az, el = VIEWS[view]
            back, right, up = cam_basis(az, el)
            rs = [p.dot(right) for p in pts]
            us = [p.dot(up) for p in pts]
            r0, r1, u0, u1 = min(rs), max(rs), min(us), max(us)
            pad = 0.03 * max(r1 - r0, u1 - u0)
            r0, r1, u0, u1 = r0 - pad, r1 + pad, u0 - pad, u1 + pad
            fw, fh = r1 - r0, u1 - u0
            centre = right * ((r0 + r1) / 2) + up * ((u0 + u1) / 2)
            lens = OrthographicLens()
            lens.set_film_size(fw, fh)
            lens.set_near_far(-200, 400)
            base.cam.node().set_lens(lens)
            base.cam.set_pos(Point3(*(centre + back * 100)))
            base.cam.look_at(Point3(*centre), up)
            outdir = os.path.join(args.out, view)
            os.makedirs(outdir, exist_ok=True)
            H = max(1, int(round(MAXW * fh / fw)))
            # offscreen buffer of the right aspect with an alpha channel
            fbp = FrameBufferProperties()
            fbp.set_rgba_bits(8, 8, 8, 8)
            fbp.set_depth_bits(24)
            wp = WindowProperties.size(MAXW, H)
            buf = base.graphics_engine.make_output(base.pipe, f"spr_{key}_{view}", -2, fbp, wp,
                                                   GraphicsPipe.BF_refuse_window, base.win.get_gsg(), base.win)
            buf.set_clear_color_active(True)
            buf.set_clear_color((0, 0, 0, 0))
            dr = buf.make_display_region()
            dr.set_camera(base.cam)
            base.graphics_engine.render_frame()
            base.graphics_engine.render_frame()
            tmp = os.path.join(outdir, f"_{key}.png")
            buf.save_screenshot(tmp)
            base.graphics_engine.remove_window(buf)
            big = Image.open(tmp).convert("RGBA")
            os.remove(tmp)
            info = {"key": key, "view": view, "azimuth_deg": az, "elevation_deg": el,
                    "projection": "orthographic", "sizes": {}}
            trig = meta.get("trigger")

            def to_px(p, w, h):
                return [round((p.dot(right) - r0) / fw * w, 1), round((u1 - p.dot(up)) / fh * h, 1)]
            for size in args.sizes:
                h = max(1, int(round(size * fh / fw)))
                img = big.resize((size, h), Image.LANCZOS)
                img.save(os.path.join(outdir, f"{key}_{size}.png"))
                d = {"file": f"{key}_{size}.png", "w": size, "h": h,
                     "metres_per_px": round(fw / size, 4),
                     "origin_px": to_px(Vec3(0, 0, 0), size, h)}
                if trig:
                    cx, cy, cz = trig["center"]
                    sx, sy = trig["size"][0] / 2, trig["size"][1] / 2
                    gz = cz - trig["size"][2] / 2
                    d["door_px"] = to_px(Vec3(cx, cy, gz), size, h)
                    d["trigger_px"] = [to_px(Vec3(cx + a * sx, cy + b * sy, gz), size, h)
                                       for a, b in ((-1, -1), (1, -1), (1, 1), (-1, 1))]
                info["sizes"][str(size)] = d
            with open(os.path.join(outdir, f"{key}.json"), "w") as fh_:
                json.dump(info, fh_, indent=2)
            print(f"{key:16s} {view:8s} -> {', '.join(str(s) for s in args.sizes)} px")
        model.remove_node()


if __name__ == "__main__":
    main()
