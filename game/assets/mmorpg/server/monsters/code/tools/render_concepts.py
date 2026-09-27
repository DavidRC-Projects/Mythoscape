"""tools/render_concepts.py - render 3/4-view concept/portrait PNGs of every
registered monster, headless/offscreen.

    python tools/render_concepts.py --out images/ [--only goblin_grunt] [--size 768]

Supersamples (renders at 2x, downsamples with Pillow) because llvmpipe/
offscreen buffers often have no MSAA.
"""
import argparse
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))

from panda3d.core import loadPrcFileData  # noqa: E402

ap = argparse.ArgumentParser()
ap.add_argument("--out", default="images")
ap.add_argument("--only", nargs="*")
ap.add_argument("--size", type=int, default=768)
ap.add_argument("--az", type=float, default=35.0, help="camera azimuth deg")
ap.add_argument("--el", type=float, default=16.0, help="camera elevation deg")
args = ap.parse_args()
SS = 3
loadPrcFileData("", f"""
window-type offscreen
win-size {args.size * SS} {args.size * SS}
audio-library-name null
sync-video false
""")

from direct.showbase.ShowBase import ShowBase  # noqa: E402
from panda3d.core import Point3, TransparencyAttrib  # noqa: E402
from PIL import Image  # noqa: E402

from monsters import registry  # noqa: E402
from monsters.lighting import setup_osrs_lighting  # noqa: E402
from monsters.mesh_builder import MeshBuilder  # noqa: E402

BG = (0.62, 0.60, 0.56, 1)   # plain warm neutral grey


def shadow_disc(radius):
    mb = MeshBuilder("shadow", jitter=0)
    n = 16
    for i in range(n):
        a0, a1 = 2 * math.pi * i / n, 2 * math.pi * (i + 1) / n
        mb.tri((0, 0, 0), (math.cos(a0) * radius, math.sin(a0) * radius, 0),
               (math.cos(a1) * radius, math.sin(a1) * radius, 0), (0, 0, 0, 0.22))
    np = mb.build_node()
    np.set_transparency(TransparencyAttrib.M_alpha)
    np.set_light_off()
    np.set_depth_write(False)
    np.set_bin("background", 10)
    return np


def crop_to_content(img, margin=0.10):
    """Square crop around every non-background pixel (creature + shadow)."""
    from PIL import ImageChops
    bg = Image.new("RGB", img.size, tuple(int(c * 255) for c in BG[:3]))
    diff = ImageChops.difference(img, bg).convert("L").point(lambda v: 255 if v > 8 else 0)
    box = diff.getbbox()
    if not box:
        return img
    x0, y0, x1, y1 = box
    side = int(max(x1 - x0, y1 - y0) * (1 + 2 * margin))
    cx, cy = (x0 + x1) // 2, (y0 + y1) // 2
    pad = Image.new("RGB", (img.width + 2 * side, img.height + 2 * side), bg.getpixel((0, 0)))
    pad.paste(img, (side, side))
    cx, cy = cx + side, cy + side
    return pad.crop((cx - side // 2, cy - side // 2, cx - side // 2 + side, cy - side // 2 + side))


def main():
    base = ShowBase()
    base.disable_mouse()
    base.set_background_color(*BG)
    setup_osrs_lighting(base.render)
    base.cam.node().get_lens().set_fov(28)
    registry.load_all()
    os.makedirs(args.out, exist_ok=True)
    keys = args.only or list(registry.MONSTERS)
    for key in keys:
        mt = registry.MONSTERS[key]
        rig = mt.build()
        model = rig.root
        model.reparent_to(base.render)
        lo, hi = model.get_tight_bounds()
        lo.z = min(lo.z, 0.0)          # keep the ground shadow in frame for floaters
        centre = (lo + hi) / 2
        ext = hi - lo
        radius = max(ext.x, ext.y) * 0.55
        sh = shadow_disc(radius)
        sh.reparent_to(base.render)
        sh.set_pos(centre.x, centre.y, 0.005)
        sh.set_scale(1.0, 0.8, 1.0)
        # frame the whole creature
        span = max(ext.x, ext.y, ext.z)
        dist = span / (2 * math.tan(math.radians(28 / 2))) * 1.8
        az, el = math.radians(args.az), math.radians(args.el)
        cam_pos = Point3(centre.x + dist * math.sin(az) * math.cos(el),
                         centre.y + dist * math.cos(az) * math.cos(el),
                         centre.z + dist * math.sin(el))
        base.cam.set_pos(cam_pos)
        base.cam.look_at(centre)
        base.graphics_engine.render_frame()
        base.graphics_engine.render_frame()
        tmp = os.path.join(args.out, f"_{key}_tmp.png")
        base.win.save_screenshot(tmp)
        img = Image.open(tmp).convert("RGB")
        img = crop_to_content(img).resize((args.size, args.size), Image.LANCZOS)
        img.save(os.path.join(args.out, f"{key}.png"))
        os.remove(tmp)
        print(f"{key:18s} tris={rig.triangle_count:5d} h={ext.z:.2f}m")
        model.remove_node()
        sh.remove_node()


if __name__ == "__main__":
    main()
