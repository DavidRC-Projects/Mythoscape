"""tools/render_sprites.py - pre-render 2D sprite sheets from the 3D monsters
(for a pygame-drawn world, minimap markers, or UI). Transparent PNGs.

    python tools/render_sprites.py goblin_grunt --out sprites/ --size 128 \
        --dirs 8 --frames 8 --anims idle walk attack death

Output: sprites/<key>_<anim>.png, a grid: rows = directions (0 = facing the
camera/south, then clockwise), columns = frames. Camera uses a fixed
OSRS-like pitch so all sprites share one projection.
"""
import argparse
import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from panda3d.core import loadPrcFileData  # noqa: E402

ap = argparse.ArgumentParser()
ap.add_argument("key")
ap.add_argument("--out", default="sprites")
ap.add_argument("--size", type=int, default=128)
ap.add_argument("--dirs", type=int, default=8)
ap.add_argument("--frames", type=int, default=8)
ap.add_argument("--anims", nargs="*", default=["idle", "walk", "attack", "death"])
ap.add_argument("--pitch", type=float, default=30.0, help="camera look-down angle")
args = ap.parse_args()
loadPrcFileData("", f"window-type offscreen\nwin-size {args.size} {args.size}\n"
                    "framebuffer-alpha true\naudio-library-name null\n")

from direct.showbase.ShowBase import ShowBase  # noqa: E402
from panda3d.core import ClockObject, OrthographicLens, PNMImage  # noqa: E402

from monsters import registry  # noqa: E402
from monsters.lighting import setup_osrs_lighting  # noqa: E402

base = ShowBase()
base.disable_mouse()
base.set_background_color(0, 0, 0, 0)
setup_osrs_lighting(base.render)
clock = ClockObject.get_global_clock()
clock.set_mode(ClockObject.M_non_real_time)
registry.load_all()
mon = registry.create(args.key, base.render)
h = mon.type.height_m
lo, hi = mon.rig.root.get_tight_bounds(base.render)
span = max((hi - lo).x, (hi - lo).y, (hi - lo).z) * 1.25
lens = OrthographicLens()          # orthographic = consistent pixel scale for sprites
lens.set_film_size(span, span)
lens.set_near_far(0.1, 100)
base.cam.node().set_lens(lens)
pr = math.radians(args.pitch)
base.cam.set_pos(0, 30 * math.cos(pr), 30 * math.sin(pr) + h * 0.45)
base.cam.look_at(0, 0, h * 0.45)
ANIM_LEN = {"idle": 2.0, "walk": 0.9, "attack": 0.9, "death": 1.2}
os.makedirs(args.out, exist_ok=True)
for anim in args.anims:
    sheet = PNMImage(args.size * args.frames, args.size * args.dirs, 4)
    for d in range(args.dirs):
        mon.respawn()
        mon.node.set_h(360.0 * d / args.dirs)
        mon.play(anim)
        dt = ANIM_LEN.get(anim, 1.0) / args.frames
        clock.set_dt(dt)
        for f in range(args.frames):
            base.task_mgr.step()
            img = PNMImage()
            base.win.get_screenshot(img)
            if not img.has_alpha():
                img.add_alpha()
            sheet.copy_sub_image(img, f * args.size, d * args.size)
    path = os.path.join(args.out, f"{args.key}_{anim}.png")
    sheet.write(path)
    print("wrote", path)
