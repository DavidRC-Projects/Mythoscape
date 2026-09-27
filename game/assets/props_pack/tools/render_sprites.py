"""tools/render_sprites.py - the 2D (pygame) route. Renders every prop from the Mythoscape
GAME camera to transparent PNGs + an anchor JSON the client can blit with.

Game camera (matches game/assets/mmorpg/tools/blender_render_building.py, which bakes the
building PNGs): ORTHOGRAPHIC, azimuth 0 (looking north, the prop's -Y front faces the viewer),
elevation 32 deg. Scale: TILE 40 px = ~1.49 m, the 1.8 m player is ~48 px -> 26.9 px/m.

Outputs  sprites/game/<key>_1x.png  2x  3x   true scale (26.9 / 53.8 / 80.7 px per metre)
         sprites/game/<key>_match.png        scaled so its WIDTH equals the current 2D drawer's
                                              on-screen width at TILE 40 (json game.current_px)
         sprites/game/<key>_{s,w,n,e}_1x.png yaw variants (building_sprites.py naming: s = front)
                                              only with --yaws
         sprites/osrs/<key>_2x.png            3/4 view (az 35, el 30, ortho) at 53.8 px/m
         sprites/<view>/<key>.json            anchors per image:
             origin_px    - model origin = TILE CENTRE at ground level -> blit so this pixel
                            lands on the old draw point (cx, cy)
             interact_px  - interaction volume footprint polygon (4 pts, ground level)
             collider_px  - list of solid footprints (4 pts each)
             px_per_m, metres_per_px, w, h

    /workspace/monsters_venv/bin/python tools/render_sprites.py [--only furnace anvil] [--yaws]
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
ap.add_argument("--yaws", action="store_true", help="also render _s/_w/_n/_e yaw variants (1x, 2x)")
ap.add_argument("--out", default=os.path.join(ROOT, "sprites"))
ap.add_argument("--ss", type=int, default=4, help="supersample factor")
args = ap.parse_args()
PPM = 40 / 1.4866            # 26.9 px per metre at TILE 40
GAME = (0.0, 32.0)
OSRS = (35.0, 30.0)

from panda3d.core import loadPrcFileData  # noqa: E402
loadPrcFileData("", """
window-type offscreen
win-size 64 64
framebuffer-alpha true
audio-library-name null
sync-video false
gltf-legacy-materials true
""")
from direct.showbase.ShowBase import ShowBase  # noqa: E402
from panda3d.core import (OrthographicLens, Vec3, Point3, FrameBufferProperties, WindowProperties,  # noqa: E402
                          GraphicsPipe, GeomVertexReader)
from PIL import Image  # noqa: E402
from prop_loader import load_prop, setup_osrs_lighting, PROP_SUN_HPR  # noqa: E402


def cam_basis(az_deg, el_deg):
    az, el = math.radians(az_deg), math.radians(el_deg)
    back = Vec3(math.sin(az) * math.cos(el), -math.cos(az) * math.cos(el), math.sin(el))
    right = (-back).cross(Vec3(0, 0, 1))
    right.normalize()
    up = right.cross(-back)
    up.normalize()
    return back, right, up


def box_poly(c, heading):
    cx, cy, cz = c["center"]
    sx, sy = c["size"][0] / 2, c["size"][1] / 2
    gz = max(0.0, cz - c["size"][2] / 2)
    h = math.radians(heading)
    out = []
    for a, b in ((-1, -1), (1, -1), (1, 1), (-1, 1)):
        x, y = cx + a * sx, cy + b * sy
        out.append(Vec3(x * math.cos(h) - y * math.sin(h), x * math.sin(h) + y * math.cos(h), gz))
    return out


def render(base, model, meta, key, view_dir, name, az, el, heading, ppms, match_w=None):
    model.set_h(heading)
    pts = []
    for gnp in model.find_all_matches("**/+GeomNode"):
        mat = gnp.get_mat(base.render)
        for geom in gnp.node().get_geoms():
            r = GeomVertexReader(geom.get_vertex_data(), "vertex")
            while not r.is_at_end():
                pts.append(mat.xform_point(r.get_data3()))
    back, right, up = cam_basis(az, el)
    rs = [p.dot(right) for p in pts]
    us = [p.dot(up) for p in pts]
    pad = 0.06
    r0, r1, u0, u1 = min(rs) - pad, max(rs) + pad, min(us) - pad, max(us) + pad
    fw, fh = r1 - r0, u1 - u0
    centre = right * ((r0 + r1) / 2) + up * ((u0 + u1) / 2)
    lens = OrthographicLens()
    lens.set_film_size(fw, fh)
    lens.set_near_far(-200, 400)
    base.cam.node().set_lens(lens)
    base.cam.set_pos(Point3(*(centre + back * 100)))
    base.cam.look_at(Point3(*centre), up)
    big_ppm = max(ppms.values()) * args.ss
    W, H = max(8, int(round(fw * big_ppm))), max(8, int(round(fh * big_ppm)))
    fbp = FrameBufferProperties()
    fbp.set_rgba_bits(8, 8, 8, 8)
    fbp.set_depth_bits(24)
    fbp.set_multisamples(0)
    buf = base.graphics_engine.make_output(base.pipe, f"spr_{key}_{name}", -2, fbp, WindowProperties.size(W, H),
                                           GraphicsPipe.BF_refuse_window, base.win.get_gsg(), base.win)
    buf.set_clear_color_active(True)
    buf.set_clear_color((0, 0, 0, 0))
    dr = buf.make_display_region()
    dr.set_camera(base.cam)
    base.graphics_engine.render_frame()
    base.graphics_engine.render_frame()
    os.makedirs(view_dir, exist_ok=True)
    tmp = os.path.join(view_dir, f"_{key}_{name}.png")
    buf.save_screenshot(tmp)
    base.graphics_engine.remove_window(buf)
    big = Image.open(tmp).convert("RGBA")
    os.remove(tmp)
    info = {}
    targets = dict(ppms)
    if match_w:
        targets["match"] = match_w / fw
    for tag, ppm in targets.items():
        w, h = max(1, int(round(fw * ppm))), max(1, int(round(fh * ppm)))
        fn = f"{key}_{name}{tag}.png" if name else f"{key}_{tag}.png"
        big.resize((w, h), Image.LANCZOS).save(os.path.join(view_dir, fn))

        def px(p):
            return [round((p.dot(right) - r0) * ppm, 1), round((u1 - p.dot(up)) * ppm, 1)]
        d = {"file": fn, "w": w, "h": h, "px_per_m": round(ppm, 3), "metres_per_px": round(1 / ppm, 4),
             "origin_px": px(Vec3(0, 0, 0)), "heading_deg": heading,
             "collider_px": [[px(p) for p in box_poly(c, heading)] for c in meta.get("colliders", [])]}
        it = meta.get("interact")
        if it:
            d["interact_px"] = [px(p) for p in box_poly(it, heading)]
        info[fn] = d
    model.set_h(0)
    return info


def main():
    base = ShowBase()
    base.disable_mouse()
    setup_osrs_lighting(base.render, sun_hpr=PROP_SUN_HPR)
    for f in sorted(glob.glob(os.path.join(ROOT, "glb", "*.glb"))):
        key = os.path.splitext(os.path.basename(f))[0]
        if args.only and key not in args.only:
            continue
        model, meta = load_prop(base.loader, f)
        model.reparent_to(base.render)
        cur = (meta.get("game") or {}).get("current_px_at_tile40")
        gdir = os.path.join(args.out, "game")
        info = {"key": key, "camera": {"projection": "orthographic", "azimuth_deg": GAME[0],
                                       "elevation_deg": GAME[1]}, "images": {}}
        info["images"].update(render(base, model, meta, key, gdir, "", *GAME, 0,
                                     {"1x": PPM, "2x": 2 * PPM, "3x": 3 * PPM}, match_w=cur[0] if cur else None))
        if args.yaws:
            for suf, hd in (("s", 0), ("w", 90), ("n", 180), ("e", -90)):
                info["images"].update(render(base, model, meta, key, gdir, suf + "_", *GAME, hd,
                                             {"1x": PPM, "2x": 2 * PPM}))
        with open(os.path.join(gdir, f"{key}.json"), "w") as fh:
            json.dump(info, fh, indent=2)
        odir = os.path.join(args.out, "osrs")
        oinfo = {"key": key, "camera": {"projection": "orthographic", "azimuth_deg": OSRS[0],
                                        "elevation_deg": OSRS[1]}, "images": {}}
        oinfo["images"].update(render(base, model, meta, key, odir, "", *OSRS, 0, {"2x": 2 * PPM}))
        with open(os.path.join(odir, f"{key}.json"), "w") as fh:
            json.dump(oinfo, fh, indent=2)
        g1 = info["images"][f"{key}_1x.png"]
        print(f"{key:18s} game 1x {g1['w']}x{g1['h']} px  origin {g1['origin_px']}"
              + (f"  match {info['images'][key + '_match.png']['w']}x{info['images'][key + '_match.png']['h']}"
                 if cur else ""))
        model.remove_node()


if __name__ == "__main__":
    main()
