"""tools/monster_viewer.py - interactive / headless check for lowpoly dragons.

    python -m monsters_lowpoly.tools.monster_viewer dragon_green
    python monsters_lowpoly/tools/monster_viewer.py dragon_green --screenshot out.png

Keys: Left/Right = previous/next, 1 idle, 2 walk, 3 attack, 4 death,
      R = respawn, W = wireframe, F = fog, mouse-drag = orbit, wheel = zoom.
"""
import argparse
import math
import os
import sys

# Parent of monsters_lowpoly package (mmorpg/)
_PKG_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _PKG_ROOT not in sys.path:
    sys.path.insert(0, _PKG_ROOT)

from panda3d.core import loadPrcFileData  # noqa: E402

ap = argparse.ArgumentParser()
ap.add_argument("key", nargs="?", default="dragon_green")
ap.add_argument("--screenshot")
args = ap.parse_args()
cfg = "window-title Monster Viewer\nwin-size 1024 768\nsync-video true\n"
if args.screenshot:
    cfg += "window-type offscreen\naudio-library-name null\n"
loadPrcFileData("", cfg)

from direct.showbase.ShowBase import ShowBase  # noqa: E402
from direct.gui.OnscreenText import OnscreenText  # noqa: E402
from panda3d.core import CardMaker, TextNode, WindowProperties  # noqa: E402

from monsters_lowpoly import registry  # noqa: E402
from monsters_lowpoly.lighting import setup_osrs_lighting  # noqa: E402


class Viewer(ShowBase):
    def __init__(self, start_key=None):
        super().__init__()
        self.disable_mouse()
        self.set_background_color(0.45, 0.52, 0.58, 1)
        _, _, self.fog = setup_osrs_lighting(self.render, fog_color=(0.45, 0.52, 0.58),
                                             fog_range=(12, 40))
        self.render.clear_fog()
        self.fog_on = False
        cm = CardMaker("ground")
        cm.set_frame(-6, 6, -6, 6)
        ground = self.render.attach_new_node(cm.generate())
        ground.set_p(-90)
        ground.set_color(0.36, 0.42, 0.26, 1)
        from monsters_lowpoly.mesh_builder import MeshBuilder
        post = MeshBuilder("player_ref", jitter=0)
        post.box((0.45, 0.3, 1.8), "#b8a07a", pos=(0, 0, 0.9))
        self.ref = post.build_node()
        self.ref.reparent_to(self.render)
        registry.load_all()
        self.keys = list(registry.MONSTERS)
        self.idx = self.keys.index(start_key) if start_key in self.keys else 0
        self.monster = None
        self.cam_h, self.cam_p, self.cam_d = 35.0, -14.0, 7.0
        self.hud = OnscreenText(text="", pos=(-1.3, 0.92), scale=0.05, align=TextNode.A_left,
                                fg=(1, 1, 1, 1), shadow=(0, 0, 0, 1))
        self.load()
        for k, a in (("1", "idle"), ("2", "walk"), ("3", "attack"), ("4", "death")):
            self.accept(k, self.monster_play, [a])
        self.accept("arrow_right", self.cycle, [1])
        self.accept("arrow_left", self.cycle, [-1])
        self.accept("r", lambda: self.monster.respawn())
        self.accept("w", self.toggle_wireframe)
        self.accept("f", self.toggle_fog)
        self.accept("wheel_up", self.zoom, [0.9])
        self.accept("wheel_down", self.zoom, [1.1])
        self.accept("mouse1", self.start_drag)
        self.accept("mouse1-up", self.stop_drag)
        self.drag = None
        self.task_mgr.add(self.update_cam, "cam")

    def load(self):
        if self.monster:
            self.monster.destroy()
        key = self.keys[self.idx]
        self.monster = registry.create(key, self.render)
        mt = self.monster.type
        self.ref.set_x(-(mt.height_m * 0.9 + 0.8))
        self.cam_d = max(4.0, mt.height_m * 3.2)
        self.hud.setText(f"{mt.name}  (lvl {mt.stats.level}, {mt.stats.hp} HP)  "
                          f"tris={self.monster.rig.triangle_count}  [1-4 anims, <- -> cycle]")
        if not args.screenshot:
            props = WindowProperties()
            props.set_title(f"Monster Viewer - {key}")
            self.win.request_properties(props)

    def monster_play(self, name):
        self.monster.play(name)

    def cycle(self, d):
        self.idx = (self.idx + d) % len(self.keys)
        self.load()

    def zoom(self, f):
        self.cam_d = max(1.5, min(40.0, self.cam_d * f))

    def toggle_wireframe(self):
        from panda3d.core import RenderModeAttrib
        mode = self.render.get_attrib(RenderModeAttrib)
        if mode and mode.get_mode() == RenderModeAttrib.M_wireframe:
            self.render.clear_attrib(RenderModeAttrib)
        else:
            self.render.set_attrib(RenderModeAttrib.make(RenderModeAttrib.M_wireframe))

    def toggle_fog(self):
        self.fog_on = not self.fog_on
        if self.fog_on:
            self.render.set_fog(self.fog)
        else:
            self.render.clear_fog()

    def start_drag(self):
        if self.mouseWatcherNode.has_mouse():
            m = self.mouseWatcherNode.get_mouse()
            self.drag = (m.x, m.y, self.cam_h, self.cam_p)

    def stop_drag(self):
        self.drag = None

    def update_cam(self, task):
        if self.drag and self.mouseWatcherNode.has_mouse():
            m = self.mouseWatcherNode.get_mouse()
            self.cam_h = self.drag[2] - (m.x - self.drag[0]) * 180
            self.cam_p = max(-80, min(-2, self.drag[3] + (m.y - self.drag[1]) * 90))
        h = self.monster.type.height_m
        hr, pr = math.radians(self.cam_h), math.radians(self.cam_p)
        self.camera.set_pos(self.cam_d * math.sin(hr) * math.cos(pr),
                            self.cam_d * math.cos(hr) * math.cos(pr),
                            h * 0.5 - self.cam_d * math.sin(pr))
        self.camera.look_at(0, 0, h * 0.5)
        return task.cont


app = Viewer(args.key)
if args.screenshot:
    for _ in range(3):
        app.task_mgr.step()
    app.win.save_screenshot(args.screenshot)
    print("saved", args.screenshot)
else:
    app.run()
