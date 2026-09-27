"""
monsters/mesh_builder.py
------------------------
Tiny procedural low-poly mesh toolkit for Panda3D 1.10.x (OSRS-style art).

* Every triangle gets its OWN three vertices (no sharing) so each face has a
  single flat normal and a single colour -> crisp faceted "flat shading" even
  with Panda3D's default fixed-function (per-vertex) lighting.
* Colours are per face (vertex colours), no textures needed.
* A small deterministic brightness jitter per face gives the hand-painted,
  slightly uneven look of early-2000s MMO models (set jitter=0 to disable).
* Primitives are convex and are auto-oriented so faces always point outward,
  so you never have to think about winding order.

Coordinate convention (Panda3D default): +X right, +Y forward, +Z up.
1 unit = 1 metre. Monsters face +Y.
"""
from __future__ import annotations

import math
import random
import zlib
from typing import Iterable, Sequence

from panda3d.core import (
    Geom,
    GeomNode,
    GeomTriangles,
    GeomVertexData,
    GeomVertexFormat,
    GeomVertexWriter,
    LColor,
    Mat4,
    NodePath,
    Point3,
    TransformState,
    Vec3,
)

ColorLike = "str | Sequence[float]"


# --------------------------------------------------------------------------
# colour helpers
# --------------------------------------------------------------------------
def hex_to_rgba(value, alpha: float = 1.0) -> LColor:
    """'#6b8e23' / '6b8e23' / (r,g,b[,a]) floats 0-1 -> LColor."""
    if isinstance(value, LColor):
        return LColor(value)
    if isinstance(value, str):
        h = value.lstrip("#")
        r, g, b = (int(h[i:i + 2], 16) / 255.0 for i in (0, 2, 4))
        return LColor(r, g, b, alpha)
    vals = list(value)
    if len(vals) == 3:
        vals.append(alpha)
    return LColor(*vals)


def shade(color, factor: float) -> LColor:
    """Multiply rgb by factor (0.8 = 20% darker, 1.2 = lighter), clamped."""
    c = hex_to_rgba(color)
    return LColor(min(c[0] * factor, 1.0), min(c[1] * factor, 1.0),
                  min(c[2] * factor, 1.0), c[3])


def _mat(pos=(0, 0, 0), hpr=(0, 0, 0), scale=1.0) -> Mat4:
    if isinstance(scale, (int, float)):
        scale = (scale, scale, scale)
    return TransformState.make_pos_hpr_scale(
        Point3(*pos), Vec3(*hpr), Vec3(*scale)).get_mat()


def _basis(axis: Vec3):
    """Two unit vectors perpendicular to axis (and to each other)."""
    a = Vec3(axis)
    a.normalize()
    ref = Vec3(0, 0, 1) if abs(a.z) < 0.95 else Vec3(0, 1, 0)
    u = a.cross(ref)
    u.normalize()
    v = a.cross(u)
    v.normalize()
    return u, v


# --------------------------------------------------------------------------
# MeshBuilder
# --------------------------------------------------------------------------
class MeshBuilder:
    """Accumulates flat-coloured triangles, then bakes one Geom."""

    _FORMAT = GeomVertexFormat.get_v3n3c4()

    def __init__(self, name: str = "mesh", jitter: float = 0.05, seed: int = 1):
        self.name = name
        self.jitter = jitter
        self._rng = random.Random(seed)
        self._tris: list[tuple[Point3, Point3, Point3, LColor]] = []

    # ---- low level ---------------------------------------------------------
    @property
    def triangle_count(self) -> int:
        return len(self._tris)

    def _face_color(self, color) -> LColor:
        c = hex_to_rgba(color)
        if self.jitter:
            c = shade(c, 1.0 + self._rng.uniform(-self.jitter, self.jitter))
        return c

    def tri(self, a, b, c, color, outward_from=None, double_sided=False):
        """Add one triangle. If outward_from (a point) is given, the winding is
        flipped when needed so the face normal points away from that point."""
        a, b, c = Point3(*a), Point3(*b), Point3(*c)
        n = (b - a).cross(c - a)
        if n.length_squared() < 1e-12:
            return  # degenerate, skip
        if outward_from is not None:
            centre = (a + b + c) / 3.0
            if n.dot(centre - Point3(*outward_from)) < 0:
                b, c = c, b
        col = self._face_color(color)
        self._tris.append((a, b, c, col))
        if double_sided:
            self._tris.append((a, c, b, col))

    def quad(self, a, b, c, d, color, outward_from=None, double_sided=False):
        """Quad a-b-c-d (in order around the edge) -> 2 tris, same colour."""
        col = self._face_color(color)
        j, self.jitter = self.jitter, 0.0   # keep both halves identical
        self.tri(a, b, c, col, outward_from, double_sided)
        self.tri(a, c, d, col, outward_from, double_sided)
        self.jitter = j

    def polygon(self, points: Sequence, color, double_sided=True):
        """Flat convex-ish polygon as a fan (wing membranes, ears, fins)."""
        pts = [Point3(*p) for p in points]
        col = self._face_color(color)
        j, self.jitter = self.jitter, 0.0
        for i in range(1, len(pts) - 1):
            self.tri(pts[0], pts[i], pts[i + 1], col, double_sided=double_sided)
        self.jitter = j

    # ---- primitives --------------------------------------------------------
    def box(self, size=(1, 1, 1), color="#808080", pos=(0, 0, 0), hpr=(0, 0, 0),
            taper=(1.0, 1.0), top_offset=(0.0, 0.0)):
        """Box centred on pos. taper scales the TOP face (x, y) -> frustum /
        wedge shapes; top_offset shifts the top face (x, y) for slanted boxes."""
        sx, sy, sz = (s * 0.5 for s in size)
        tx, ty = sx * taper[0], sy * taper[1]
        ox, oy = top_offset
        m = _mat(pos, hpr)
        bottom = [(-sx, -sy, -sz), (sx, -sy, -sz), (sx, sy, -sz), (-sx, sy, -sz)]
        top = [(-tx + ox, -ty + oy, sz), (tx + ox, -ty + oy, sz),
               (tx + ox, ty + oy, sz), (-tx + ox, ty + oy, sz)]
        B = [m.xform_point(Point3(*p)) for p in bottom]
        T = [m.xform_point(Point3(*p)) for p in top]
        centre = sum(B + T, Point3(0, 0, 0)) / 8.0
        self.quad(*B, color, outward_from=centre)
        self.quad(*T, color, outward_from=centre)
        for i in range(4):
            k = (i + 1) % 4
            self.quad(B[i], B[k], T[k], T[i], color, outward_from=centre)
        return self

    def tube(self, start, end, r_start=0.1, r_end=None, color="#808080",
             segments=6, caps=True, twist=0.0, squash=1.0, double_sided=False):
        """Tapered cylinder between two points (limbs, necks, tails, horns).
        r_end=0 makes a cone. squash<1 flattens the cross-section."""
        if r_end is None:
            r_end = r_start
        s, e = Point3(*start), Point3(*end)
        axis = e - s
        if axis.length_squared() < 1e-12:
            return self
        u, v = _basis(axis)
        ring_s, ring_e = [], []
        for i in range(segments):
            ang = twist + 2 * math.pi * i / segments
            off = u * math.cos(ang) + v * (math.sin(ang) * squash)
            ring_s.append(s + off * r_start)
            ring_e.append(e + off * r_end)
        centre = (s + e) / 2.0
        for i in range(segments):
            k = (i + 1) % segments
            if r_end <= 1e-6:
                self.tri(ring_s[i], ring_s[k], e, color, outward_from=centre)
            elif r_start <= 1e-6:
                self.tri(s, ring_e[k], ring_e[i], color, outward_from=centre)
            else:
                self.quad(ring_s[i], ring_s[k], ring_e[k], ring_e[i], color,
                          outward_from=centre, double_sided=double_sided)
        if caps:
            if r_start > 1e-6:
                self._cap(ring_s, color, centre)
            if r_end > 1e-6:
                self._cap(ring_e, color, centre)
        return self

    def _cap(self, ring, color, centre):
        col = self._face_color(color)
        j, self.jitter = self.jitter, 0.0
        for i in range(1, len(ring) - 1):
            self.tri(ring[0], ring[i], ring[i + 1], col, outward_from=centre)
        self.jitter = j

    def cone(self, base, tip, radius=0.1, color="#808080", segments=5, twist=0.0,
             squash=1.0):
        """Cone (spikes, claws, teeth, horns, hats)."""
        return self.tube(base, tip, radius, 0.0, color, segments, twist=twist,
                         squash=squash)

    def sphere(self, radius=0.5, color="#808080", pos=(0, 0, 0), hpr=(0, 0, 0),
               scale=(1, 1, 1), rings=4, segments=6):
        """Low-poly UV sphere / ellipsoid (rings>=2). Great for heads, bellies,
        joints, eyes. rings=3, segments=5 is very chunky; 5x8 is 'smooth'."""
        m = _mat(pos, hpr, scale)
        grid = []
        for r in range(rings + 1):
            phi = math.pi * r / rings
            z = math.cos(phi) * radius
            rr = math.sin(phi) * radius
            row = []
            for s in range(segments):
                th = 2 * math.pi * s / segments
                row.append(m.xform_point(Point3(rr * math.cos(th), rr * math.sin(th), z)))
            grid.append(row)
        centre = m.xform_point(Point3(0, 0, 0))
        for r in range(rings):
            for s in range(segments):
                k = (s + 1) % segments
                a, b = grid[r][s], grid[r][k]
                c, d = grid[r + 1][k], grid[r + 1][s]
                if r == 0:
                    self.tri(a, c, d, color, outward_from=centre)
                elif r == rings - 1:
                    self.tri(a, b, c, color, outward_from=centre)
                else:
                    self.quad(a, b, c, d, color, outward_from=centre)
        return self

    def prism(self, points2d: Sequence, depth: float, color="#808080",
              pos=(0, 0, 0), hpr=(0, 0, 0)):
        """Extrude a convex 2D outline (in the XZ plane) along Y by depth.
        Good for blades, shields, axe heads, ears, teeth plates."""
        m = _mat(pos, hpr)
        h = depth / 2.0
        front = [m.xform_point(Point3(x, -h, z)) for x, z in points2d]
        back = [m.xform_point(Point3(x, h, z)) for x, z in points2d]
        centre = sum(front + back, Point3(0, 0, 0)) / (2 * len(front))
        self._cap(front, color, centre)
        self._cap(back, color, centre)
        n = len(front)
        for i in range(n):
            k = (i + 1) % n
            self.quad(front[i], front[k], back[k], back[i], color, outward_from=centre)
        return self

    # ---- output ------------------------------------------------------------
    def build_geom(self) -> Geom:
        vdata = GeomVertexData(self.name, self._FORMAT, Geom.UH_static)
        vdata.unclean_set_num_rows(len(self._tris) * 3)
        vw = GeomVertexWriter(vdata, "vertex")
        nw = GeomVertexWriter(vdata, "normal")
        cw = GeomVertexWriter(vdata, "color")
        prim = GeomTriangles(Geom.UH_static)
        for i, (a, b, c, col) in enumerate(self._tris):
            n = (b - a).cross(c - a)
            n.normalize()
            for p in (a, b, c):
                vw.set_data3(p)
                nw.set_data3(n)
                cw.set_data4(col)
            prim.add_vertices(i * 3, i * 3 + 1, i * 3 + 2)
        geom = Geom(vdata)
        geom.add_primitive(prim)
        return geom

    def build_node(self) -> NodePath:
        node = GeomNode(self.name)
        if self._tris:
            node.add_geom(self.build_geom())
        return NodePath(node)


# --------------------------------------------------------------------------
# Rig: joints (pivot NodePaths) + attached meshes
# --------------------------------------------------------------------------
class Rig:
    """Node hierarchy for a monster.

    Each joint is an empty NodePath placed at the pivot point (hip, shoulder,
    neck ...). Meshes are built in the joint's LOCAL space and attached, so
    rotating a joint (e.g. with LerpHprInterval) swings the whole limb and all
    of its children.

        rig = Rig("goblin")
        rig.joint("hips", pos=(0, 0, 0.55))
        rig.joint("l_leg", parent="hips", pos=(-0.12, 0, 0))
        rig.mesh("l_leg").tube((0, 0, 0), (0, 0, -0.5), 0.07, 0.05, "#556b2f")
        rig.bake()
    """

    def __init__(self, name: str, jitter: float = 0.05):
        self.root = NodePath(name)
        self.joints: dict[str, NodePath] = {"root": self.root}
        self.triangle_count = 0
        self.jitter = jitter
        self._meshes: dict[str, MeshBuilder] = {}

    def joint(self, name: str, parent: str = "root", pos=(0, 0, 0), hpr=(0, 0, 0)) -> NodePath:
        if name in self.joints:
            raise ValueError(f"joint {name!r} already exists")
        np = self.joints[parent].attach_new_node(name)
        np.set_pos(*pos)
        np.set_hpr(*hpr)
        self.joints[name] = np
        return np

    def attach(self, joint: str, mesh: MeshBuilder) -> NodePath:
        self.triangle_count += mesh.triangle_count
        geom_np = mesh.build_node()
        geom_np.reparent_to(self.joints[joint])
        return geom_np

    def mesh(self, joint: str) -> MeshBuilder:
        """MeshBuilder bound to a joint (created on first use). Call bake()
        once everything is modelled."""
        if joint not in self._meshes:
            if joint not in self.joints:
                raise KeyError(f"unknown joint {joint!r}")
            self._meshes[joint] = MeshBuilder(
                joint, jitter=self.jitter, seed=zlib.crc32(joint.encode()))
        return self._meshes[joint]

    def bake(self) -> "Rig":
        """Turn every pending MeshBuilder into geometry under its joint.
        Returns self so build functions can `return rig.bake()`."""
        for joint, mb in self._meshes.items():
            self.attach(joint, mb)
        self._meshes.clear()
        return self

    def __getitem__(self, name: str) -> NodePath:
        return self.joints[name]

    def rest_pose(self) -> dict[str, tuple]:
        """Snapshot of every joint's hpr - animations lerp relative to this."""
        return {n: tuple(np.get_hpr()) for n, np in self.joints.items()}


def mirror_x(points: Iterable) -> list:
    """Mirror a list of points across the YZ plane (left <-> right parts)."""
    return [(-p[0], p[1], p[2]) for p in points]
