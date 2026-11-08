"""Shared SSW orthographic camera for the M8 angled renderer.

World: +X east, +Y south, +Z up (same as the nav grid).
Camera yaw is measured from north toward east so the view looks from the
south-southwest — south and west facades are both visible, matching the
owner reference. Pitch tilts the view downward. The transform is
orthographic (no perspective divide) so it inverts cleanly for picking.
"""

from __future__ import annotations

import math
from typing import Iterable, List, Sequence, Tuple

# Fixed cinematic camera — one projection for ground, architecture, engines, avatar.
YAW_DEG = 26.0
PITCH_DEG = 26.0

YAW = math.radians(YAW_DEG)
PITCH = math.radians(PITCH_DEG)
COS_Y = math.cos(YAW)
SIN_Y = math.sin(YAW)
SIN_P = math.sin(PITCH)
COS_P = math.cos(PITCH)

# Camera right (world XY) and look (world XY, points roughly north-northeast).
RIGHT = (COS_Y, SIN_Y)
LOOK = (SIN_Y, -COS_Y)


def project(
    x: float,
    y: float,
    z: float,
    origin: Tuple[float, float],
    scale: float,
    screen_o: Tuple[float, float] = (0.0, 0.0),
) -> Tuple[float, float, float]:
    """World (x,y,z) -> (sx, sy, depth). Depth increases away from the camera."""
    dx = x - origin[0]
    dy = y - origin[1]
    sx = (dx * COS_Y + dy * SIN_Y) * scale + screen_o[0]
    depth = dx * SIN_Y - dy * COS_Y
    sy = -depth * scale * SIN_P - z * scale * COS_P + screen_o[1]
    return sx, sy, depth


def unproject(
    sx: float,
    sy: float,
    origin: Tuple[float, float],
    scale: float,
    screen_o: Tuple[float, float] = (0.0, 0.0),
    z: float = 0.0,
) -> Tuple[float, float]:
    """Inverse of project() for a known height z (ground picking uses z=0)."""
    u = (sx - screen_o[0]) / scale
    v = -((sy - screen_o[1]) / scale + z * COS_P) / SIN_P
    dx = u * COS_Y + v * SIN_Y
    dy = u * SIN_Y - v * COS_Y
    return origin[0] + dx, origin[1] + dy


def depth_of(x: float, y: float, origin: Tuple[float, float]) -> float:
    dx = x - origin[0]
    dy = y - origin[1]
    return dx * SIN_Y - dy * COS_Y


def pick_tile(
    sx: float,
    sy: float,
    origin: Tuple[float, float],
    scale: float,
    screen_o: Tuple[float, float],
    z: float = 0.0,
) -> Tuple[int, int]:
    wx, wy = unproject(sx, sy, origin, scale, screen_o, z)
    return int(math.floor(wx)), int(math.floor(wy))


def project_many(
    points: Sequence[Tuple[float, float, float]],
    origin: Tuple[float, float],
    scale: float,
    screen_o: Tuple[float, float] = (0.0, 0.0),
) -> List[Tuple[float, float, float]]:
    return [project(p[0], p[1], p[2], origin, scale, screen_o) for p in points]


def screen_aabb(
    points: Iterable[Tuple[float, float, float]],
    origin: Tuple[float, float],
    scale: float,
    screen_o: Tuple[float, float],
) -> Tuple[float, float, float, float]:
    xs, ys = [], []
    for p in points:
        sx, sy, _ = project(p[0], p[1], p[2], origin, scale, screen_o)
        xs.append(sx)
        ys.append(sy)
    return min(xs), min(ys), max(xs), max(ys)
