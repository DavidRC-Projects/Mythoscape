"""
Reusable low-poly mesh helpers for the building prototype.

Techniques informed by (licenses checked — original code only):
  - Panda3D procedural-cube sample (Modified BSD): GeomVertexFormat / Writer,
    quads as two triangles, UHStatic for static buildings, CCW front faces.
  - Epihaius procedural primitives (BSD-3): maker pattern idea only —
    configure then generate once. We do NOT vendor their package.

Do not rebuild geometry every frame.
"""

from __future__ import annotations

from panda3d.core import (
    Geom,
    GeomNode,
    GeomTriangles,
    GeomVertexData,
    GeomVertexFormat,
    GeomVertexWriter,
    Material,
    NodePath,
    Vec3,
    Vec4,
)


def _rgba(color) -> Vec4:
    if len(color) == 3:
        r, g, b = color
        return Vec4(r / 255.0, g / 255.0, b / 255.0, 1.0)
    r, g, b, a = color
    return Vec4(r / 255.0, g / 255.0, b / 255.0, a / 255.0)


def _normal(a, b, c) -> Vec3:
    """Outward normal for CCW triangle a→b→c."""
    ab = Vec3(b[0] - a[0], b[1] - a[1], b[2] - a[2])
    ac = Vec3(c[0] - a[0], c[1] - a[1], c[2] - a[2])
    n = ab.cross(ac)
    if n.lengthSquared() > 1e-12:
        n.normalize()
    else:
        n = Vec3(0, 1, 0)
    return n


def _apply_material(np: NodePath, name: str, color, *, shininess: float = 8.0):
    col = _rgba(color)
    mat = Material(name + "_mat")
    mat.setDiffuse(col)
    mat.setAmbient(Vec4(col[0] * 0.58, col[1] * 0.58, col[2] * 0.58, 1))
    mat.setSpecular(Vec4(0.05, 0.05, 0.05, 1))
    mat.setShininess(shininess)
    np.setMaterial(mat, 1)


def make_colored_mesh(name: str, triangles: list, color, *, shininess: float = 8.0) -> NodePath:
    """
    Build a static Geom from triangles (list of 3×(x,y,z)), CCW from outside.
    Includes normals + stub texcoords (for future textures) + Material.
    """
    # V3n3t2: vertex + normal + texcoord — same spirit as cube sample's richer format
    fmt = GeomVertexFormat.getV3n3t2()
    vdata = GeomVertexData(name, fmt, Geom.UHStatic)
    vertex = GeomVertexWriter(vdata, "vertex")
    normal_w = GeomVertexWriter(vdata, "normal")
    texcoord = GeomVertexWriter(vdata, "texcoord")

    prim = GeomTriangles(Geom.UHStatic)
    idx = 0
    for tri in triangles:
        a, b, c = tri
        n = _normal(a, b, c)
        # Simple planar UV stub (enough for later textured materials)
        uvs = ((0.0, 0.0), (1.0, 0.0), (0.5, 1.0))
        for p, uv in zip((a, b, c), uvs):
            vertex.addData3(float(p[0]), float(p[1]), float(p[2]))
            normal_w.addData3(n)
            texcoord.addData2(uv[0], uv[1])
        prim.addVertices(idx, idx + 1, idx + 2)
        idx += 3

    geom = Geom(vdata)
    geom.addPrimitive(prim)
    node = GeomNode(name)
    node.addGeom(geom)
    np = NodePath(node)
    # One-sided: correct winding — no setTwoSided hack
    _apply_material(np, name, color, shininess=shininess)
    return np


def box_triangles(min_xyz, max_xyz) -> list:
    """Axis-aligned box as outward-facing CCW triangles (min/max are (x,y,z))."""
    x0, y0, z0 = min_xyz
    x1, y1, z1 = max_xyz
    # Ensure min < max
    if x0 > x1:
        x0, x1 = x1, x0
    if y0 > y1:
        y0, y1 = y1, y0
    if z0 > z1:
        z0, z1 = z1, z0
    p000 = (x0, y0, z0)
    p001 = (x0, y0, z1)
    p010 = (x0, y1, z0)
    p011 = (x0, y1, z1)
    p100 = (x1, y0, z0)
    p101 = (x1, y0, z1)
    p110 = (x1, y1, z0)
    p111 = (x1, y1, z1)
    return [
        # -X (west)
        (p000, p010, p011),
        (p000, p011, p001),
        # +X (east)
        (p100, p101, p111),
        (p100, p111, p110),
        # -Y (bottom)
        (p000, p001, p101),
        (p000, p101, p100),
        # +Y (top)
        (p010, p110, p111),
        (p010, p111, p011),
        # -Z (north)
        (p000, p100, p110),
        (p000, p110, p010),
        # +Z (south)
        (p001, p011, p111),
        (p001, p111, p101),
    ]


def quad(a, b, c, d) -> list:
    """Two triangles for quad a-b-c-d (CCW from outside)."""
    return [(a, b, c), (a, c, d)]


def make_box(name: str, min_xyz, max_xyz, color, *, shininess: float = 8.0) -> NodePath:
    return make_colored_mesh(name, box_triangles(min_xyz, max_xyz), color, shininess=shininess)


class BoxMaker:
    """
    Tiny original maker (inspired by CardMaker / BoxMaker API shape, not copied).
    Configure extents + color, then generate() once.
    """

    def __init__(self, name: str = "box"):
        self.name = name
        self._min = (-0.5, 0.0, -0.5)
        self._max = (0.5, 1.0, 0.5)
        self._color = (160, 160, 160)
        self._shininess = 8.0

    def set_extents(self, min_xyz, max_xyz):
        self._min = tuple(min_xyz)
        self._max = tuple(max_xyz)
        return self

    def set_color(self, rgb):
        self._color = rgb
        return self

    def set_shininess(self, s: float):
        self._shininess = float(s)
        return self

    def generate(self) -> NodePath:
        return make_box(self.name, self._min, self._max, self._color, shininess=self._shininess)


def make_ground(name: str, half: float, y: float, color) -> NodePath:
    """Flat ground quad centered at origin on XZ, normal +Y."""
    a = (-half, y, -half)
    b = (half, y, -half)
    c = (half, y, half)
    d = (-half, y, half)
    tris = [(a, d, c), (a, c, b)]
    return make_colored_mesh(name, tris, color, shininess=2.0)


def attach_flat_shadow(parent: NodePath, cx: float, cz: float, sx: float, sz: float, y: float = 0.02):
    """Simple dark ground blob under the building (visual only)."""
    shadow = make_box(
        "ground_shadow",
        (cx - sx * 0.5, y, cz - sz * 0.5),
        (cx + sx * 0.5, y + 0.01, cz + sz * 0.5),
        (28, 36, 22),
        shininess=1.0,
    )
    shadow.setTransparency(1)
    shadow.setColorScale(1, 1, 1, 0.45)
    shadow.reparentTo(parent)
    return shadow
