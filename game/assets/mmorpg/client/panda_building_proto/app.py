"""
Panda3D ShowBase app: one original cottage, fixed isometric-style review camera.

Panda owns the window. Does not start pygame display.
Launch: python client.py --panda-building-proto
"""

from __future__ import annotations

import os
import sys

from direct.showbase.ShowBase import ShowBase
from direct.gui.OnscreenText import OnscreenText
from panda3d.core import (
    AmbientLight,
    DirectionalLight,
    Filename,
    TextNode,
    Vec4,
    WindowProperties,
)

from .camera_rs import RSCameraController
from .cottage import CottageConfig, build_cottage
from .debug_faces import build_debug_volume
from .geom_util import make_box, make_ground


_YAW_VIEW = {
    0: "iso FRONT (south/door) — default review",
    1: "LEFT (west)",
    2: "BACK (north)",
    3: "RIGHT (east)",
}


class BuildingProtoApp(ShowBase):
    def __init__(self, qa_shots: bool = False):
        ShowBase.__init__(self)

        props = WindowProperties()
        props.setTitle("Mythoscape — Cottage Test Scene (Panda3D)")
        props.setSize(1200, 800)
        self.win.requestProperties(props)

        self.setBackgroundColor(0.58, 0.74, 0.90, 1)
        self.disableMouse()

        self.debug_mode = False
        self._qa_shots = qa_shots
        self._building_root = self.render.attachNewNode("building_root")
        self._rebuild_building()

        make_ground("ground", half=30.0, y=0.0, color=(118, 152, 82)).reparentTo(self.render)
        make_box("path", (-1.5, 0.005, 4.0), (1.5, 0.04, 12.0), (150, 125, 88)).reparentTo(self.render)

        # Player-scale marker (~1.7 units) beside the door
        make_box(
            "player_scale",
            (2.2, 0.0, 4.3),
            (2.8, 1.7, 4.7),
            (205, 160, 115),
        ).reparentTo(self.render)

        self._setup_lights()

        # Fixed isometric-style 3/4 view (yaw 0 + lateral bias)
        self.cam_ctrl = RSCameraController(self)
        self.cam_ctrl.reset_iso()

        self._help = OnscreenText(
            text=(
                "Cottage test scene (fixed iso cam)  |  [ ] A/D: optional yaw  |  "
                "0: reset iso  |  F: debug faces  |  Esc: quit"
            ),
            pos=(-1.32, 0.92),
            scale=0.040,
            fg=(1, 1, 0.92, 1),
            align=TextNode.ALeft,
            mayChange=True,
        )
        self._yaw_label = OnscreenText(
            text="",
            pos=(-1.32, 0.84),
            scale=0.042,
            fg=(1, 0.95, 0.72, 1),
            align=TextNode.ALeft,
            mayChange=True,
        )
        self._update_yaw_label()

        self.accept("escape", self._quit)
        self.accept("q", self._quit)
        self.accept("[", self._yaw_ccw)
        self.accept("]", self._yaw_cw)
        self.accept("a", self._yaw_ccw)
        self.accept("d", self._yaw_cw)
        self.accept("0", self._reset_iso)
        self.accept("f", self._toggle_debug)
        self.accept("f5", self._toggle_debug)

        if qa_shots:
            self.taskMgr.add(self._qa_shot_task, "qa_shots")

    def _quit(self):
        self.userExit()

    def _setup_lights(self):
        amb = AmbientLight("amb")
        amb.setColor(Vec4(0.58, 0.58, 0.62, 1))
        self.render.setLight(self.render.attachNewNode(amb))

        sun = DirectionalLight("sun")
        sun.setColor(Vec4(0.95, 0.90, 0.80, 1))
        sun_np = self.render.attachNewNode(sun)
        sun_np.setHpr(35, -50, 0)
        self.render.setLight(sun_np)

        fill = DirectionalLight("fill")
        fill.setColor(Vec4(0.32, 0.36, 0.42, 1))
        fill_np = self.render.attachNewNode(fill)
        fill_np.setHpr(-125, -22, 0)
        self.render.setLight(fill_np)

    def _rebuild_building(self):
        self._building_root.removeNode()
        self._building_root = self.render.attachNewNode("building_root")
        if self.debug_mode:
            build_debug_volume(self._building_root, size_x=8.0, size_z=8.0, height=2.4)
        else:
            build_cottage(self._building_root, CottageConfig())

    def _toggle_debug(self):
        self.debug_mode = not self.debug_mode
        self._rebuild_building()
        self._update_yaw_label()

    def _yaw_cw(self):
        self.cam_ctrl.rotate(+1)
        self._update_yaw_label()

    def _yaw_ccw(self):
        self.cam_ctrl.rotate(-1)
        self._update_yaw_label()

    def _reset_iso(self):
        self.cam_ctrl.reset_iso()
        self._update_yaw_label()

    def _update_yaw_label(self):
        mode = "DEBUG faces" if self.debug_mode else "cottage"
        y = self.cam_ctrl.yaw
        self._yaw_label.setText(f"yaw {y} — {_YAW_VIEW[y]}  [{mode}]")

    def _qa_shot_task(self, task):
        """Save default iso shot + yaw cycle, then exit."""
        out_dir = os.path.normpath(
            os.path.join(os.path.dirname(__file__), "..", "..", "..", "characters", "_qa_review")
        )
        os.makedirs(out_dir, exist_ok=True)

        if not hasattr(self, "_qa_i"):
            self._qa_i = 0
            self._qa_wait = 0

        self._qa_wait += 1
        if self._qa_wait < 10:
            return task.cont

        i = self._qa_i
        # 0: default iso cottage; 1–4: yaw 0–3 cottage; 5–8: debug faces
        if i == 0:
            self.debug_mode = False
            self._rebuild_building()
            self.cam_ctrl.reset_iso()
            self._update_yaw_label()
            self.graphicsEngine.renderFrame()
            self.graphicsEngine.renderFrame()
            path = os.path.join(out_dir, "cottage_test_scene_iso.png")
            self.win.saveScreenshot(Filename.fromOsSpecific(path))
            print(f"QA shot: {path}")
        elif 1 <= i <= 4:
            yaw = i - 1
            self.debug_mode = False
            if i == 1:
                self._rebuild_building()
            self.cam_ctrl.set_yaw(yaw)
            self._update_yaw_label()
            self.graphicsEngine.renderFrame()
            self.graphicsEngine.renderFrame()
            path = os.path.join(out_dir, f"panda_cottage_yaw{yaw}.png")
            self.win.saveScreenshot(Filename.fromOsSpecific(path))
            print(f"QA shot: {path}")
        elif 5 <= i <= 8:
            yaw = i - 5
            if i == 5:
                self.debug_mode = True
                self._rebuild_building()
            self.cam_ctrl.set_yaw(yaw)
            self._update_yaw_label()
            self.graphicsEngine.renderFrame()
            self.graphicsEngine.renderFrame()
            path = os.path.join(out_dir, f"panda_debug_faces_yaw{yaw}.png")
            self.win.saveScreenshot(Filename.fromOsSpecific(path))
            print(f"QA shot: {path}")
        else:
            print("QA screenshots done.")
            self.userExit()
            return task.done

        self._qa_i = i + 1
        self._qa_wait = 0
        return task.cont


def main(argv=None):
    argv = list(argv if argv is not None else sys.argv)
    qa = "--qa-shots" in argv
    app = BuildingProtoApp(qa_shots=qa)
    app.run()


if __name__ == "__main__":
    main()
