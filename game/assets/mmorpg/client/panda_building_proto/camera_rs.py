"""RuneScape-style discrete yaw camera for the Panda prototype.

Default pose is a fixed isometric-like 3/4 view (~35–40° elevation).
Optional yaw snaps 0..3 match camera_yaw.py for face QA — building never rotates.
"""

from __future__ import annotations

from direct.showbase.ShowBase import ShowBase
from panda3d.core import OrthographicLens, PerspectiveLens, Point3, Vec3

from .coords import yaw_camera_offset


# Fixed review pose: readable walls + roof (iso MMORPG feel)
DEFAULT_DISTANCE = 17.0
DEFAULT_HEIGHT = 7.8  # atan(7.8/17) ≈ 25° from horizontal → ~35–40° look-down feel with bias
DEFAULT_FILM = (18.0, 12.5)


class RSCameraController:
    """
    Camera orbits a fixed look-at target. The building never rotates.

    yaw 0: camera south (biased) → FRONT + side (default iso review)
    yaw 1: camera west  → LEFT
    yaw 2: camera north → BACK
    yaw 3: camera east  → RIGHT

    Press `[` (yaw -1) for architecture test: FRONT → RIGHT → BACK → LEFT.
    """

    def __init__(
        self,
        base: ShowBase,
        look_at: tuple[float, float, float] = (0.0, 1.1, 0.0),
        distance: float = DEFAULT_DISTANCE,
        height: float = DEFAULT_HEIGHT,
        use_ortho: bool = True,
        film_size: tuple[float, float] = DEFAULT_FILM,
    ):
        self.base = base
        self.look_at = Point3(*look_at)
        self.distance = float(distance)
        self.height = float(height)
        self.film_size = film_size
        self.yaw = 0
        self.use_ortho = use_ortho
        self._apply_lens()
        self.apply()

    def _apply_lens(self):
        if self.use_ortho:
            lens = OrthographicLens()
            lens.setFilmSize(*self.film_size)
            lens.setNearFar(-80, 120)
            self.base.cam.node().setLens(lens)
        else:
            lens = PerspectiveLens()
            lens.setFov(40)
            lens.setNearFar(0.5, 200)
            self.base.cam.node().setLens(lens)

    def set_yaw(self, yaw: int):
        self.yaw = int(yaw) % 4
        self.apply()

    def rotate(self, delta: int):
        """delta +1 = ] in pygame client (yaw increases)."""
        self.set_yaw(self.yaw + delta)

    def reset_iso(self):
        """Return to default fixed isometric review pose (yaw 0)."""
        self.set_yaw(0)

    def apply(self):
        ox, oy, oz = yaw_camera_offset(self.yaw, self.distance, self.height)
        pos = Point3(
            self.look_at.x + ox,
            self.look_at.y + oy,
            self.look_at.z + oz,
        )
        self.base.cam.setPos(pos)
        self.base.cam.lookAt(self.look_at, Vec3(0, 1, 0))
