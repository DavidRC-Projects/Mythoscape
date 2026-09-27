"""tools/anim_test.py - headless smoke test: build every monster through the
factory, play idle/walk/attack/death with a fixed-step clock and (optionally)
save a frame strip per monster.

    python tools/anim_test.py                # all monsters, asserts only
    python tools/anim_test.py --strip out/   # also write <key>_anim.png strips
"""
import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from panda3d.core import loadPrcFileData  # noqa: E402

ap = argparse.ArgumentParser()
ap.add_argument("--strip")
ap.add_argument("--only", nargs="*")
args = ap.parse_args()
loadPrcFileData("", "window-type offscreen\nwin-size 320 320\naudio-library-name null\n")

from direct.showbase.ShowBase import ShowBase  # noqa: E402
from panda3d.core import ClockObject, PNMImage  # noqa: E402

from monsters import registry  # noqa: E402
from monsters.lighting import setup_osrs_lighting  # noqa: E402

base = ShowBase()
base.disable_mouse()
base.set_background_color(0.62, 0.60, 0.56, 1)
setup_osrs_lighting(base.render)
clock = ClockObject.get_global_clock()
clock.set_mode(ClockObject.M_non_real_time)
clock.set_dt(1 / 30)
registry.load_all()


def step(seconds):
    for _ in range(int(seconds * 30)):
        base.task_mgr.step()


for key in args.only or list(registry.MONSTERS):
    mon = registry.create(key, base.render)
    h = mon.type.height_m
    base.cam.set_pos(h * 2.2, h * 3.2, h * 1.1)
    base.cam.look_at(0, 0, h * 0.45)
    frames = []
    for anim, dur in (("idle", 1.0), ("walk", 0.45), ("walk", 0.45), ("attack", 0.3), ("death", 0.7)):
        mon.play(anim)
        step(dur)
        if args.strip:
            img = PNMImage()
            base.win.get_screenshot(img)
            frames.append(img)
    assert mon.state == "death"
    mon.respawn()
    assert mon.state == "idle" and mon.rig.root.get_scale().x == 1
    kills = mon.take_damage(mon.hp)
    assert kills and not mon.alive
    step(2.5)
    if args.strip:
        os.makedirs(args.strip, exist_ok=True)
        w = frames[0].get_x_size()
        strip = PNMImage(w * len(frames), frames[0].get_y_size())
        for i, f in enumerate(frames):
            strip.copy_sub_image(f, i * w, 0)
        strip.write(os.path.join(args.strip, f"{key}_anim.png"))
    mon.destroy()
    print(f"{key:18s} OK  joints={len(mon.rig.joints):3d} tris={mon.rig.triangle_count}")
print("all animations OK")
