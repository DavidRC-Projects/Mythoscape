"""
Debug world-space volume: each face a distinct color.

FRONT (S) red → RIGHT (E) yellow → BACK (N) green → LEFT (W) blue
when the camera orbits a stationary building. TOP = purple.

See .cursor/rules/building-architecture.mdc
"""

from __future__ import annotations

from panda3d.core import NodePath

from .geom_util import make_colored_mesh, quad


# Face colors (readable QA)
COLOR_FRONT = (220, 60, 60)      # SOUTH +Z
COLOR_RIGHT = (230, 200, 50)     # EAST  +X
COLOR_BACK = (60, 180, 80)       # NORTH -Z
COLOR_LEFT = (60, 110, 220)      # WEST  -X
COLOR_TOP = (160, 80, 200)       # UP    +Y
COLOR_BOTTOM = (40, 40, 40)


def build_debug_volume(
    parent: NodePath,
    size_x: float = 8.0,
    size_z: float = 8.0,
    height: float = 2.4,
    name: str = "debug_volume",
) -> NodePath:
    """
    Axis-aligned box centered on XZ origin, base on y=0.
    Faces are separate meshes so colors stay world-fixed.
    """
    root = parent.attachNewNode(name)
    hx, hz = size_x * 0.5, size_z * 0.5
    y0, y1 = 0.0, height

    # Corners
    # SW(-X,+Z), SE(+X,+Z), NE(+X,-Z), NW(-X,-Z)
    sw0, sw1 = (-hx, y0, hz), (-hx, y1, hz)
    se0, se1 = (hx, y0, hz), (hx, y1, hz)
    ne0, ne1 = (hx, y0, -hz), (hx, y1, -hz)
    nw0, nw1 = (-hx, y0, -hz), (-hx, y1, -hz)

    faces = [
        ("face_front", COLOR_FRONT, quad(sw0, se0, se1, sw1)),  # +Z, CCW from south
        ("face_right", COLOR_RIGHT, quad(se0, ne0, ne1, se1)),  # +X
        ("face_back", COLOR_BACK, quad(ne0, nw0, nw1, ne1)),    # -Z
        ("face_left", COLOR_LEFT, quad(nw0, sw0, sw1, nw1)),    # -X
        ("face_top", COLOR_TOP, quad(sw1, se1, ne1, nw1)),
        ("face_bottom", COLOR_BOTTOM, quad(sw0, nw0, ne0, se0)),
    ]
    for fname, color, tris in faces:
        np = make_colored_mesh(fname, tris, color)
        np.reparentTo(root)
    return root
