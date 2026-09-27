"""osrs_kit.py - shared low-poly OSRS-style building kit for Blender 4.2 (bpy + bmesh).

Every entrance script does:

    import sys, os; sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from osrs_kit import Kit
    k = Kit("goblin_cave", PALETTE, seed=7)
    ... k.box(...), k.rock(...), k.archway(...), k.collider(...), k.trigger(...)
    k.finish()          # builds mesh, saves .blend, exports .glb + .json, renders concept

Run headless:   blender --background --python blender_scripts/goblin_cave.py
Optional args after "--":  --no-render   --out /path/to/dungeons

Conventions
-----------
* 1 Blender unit = 1 metre, Z up, ground at z = 0.
* The entrance FRONT faces -Y (Blender "Front" view). The doorway is centred on x = 0,
  the opening's front edge is at y = 0 and the interior goes into +Y.
* glTF export converts to Y-up; panda3d-gltf converts back to Z-up, so in Panda3D the
  model keeps the same axes (front faces -Y, Panda's default camera looks down +Y).
* Colours: hex values are sRGB (same as the monster guide); converted to linear for Blender.
* No textures, no UVs needed. One material per palette colour, plus darker/lighter
  variants picked per face (".d" / ".l") so facets read like OSRS colour noise.
"""
import bpy
import bmesh
import json
import math
import os
import random
import sys
from mathutils import Vector, Matrix, Euler

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)            # /workspace/dungeons


# ---------------------------------------------------------------- helpers
def hex_rgb(h):
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) / 255.0 for i in (0, 2, 4))


def srgb_to_lin(c):
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


def shade(rgb, f):
    return tuple(max(0.0, min(1.0, c * f)) for c in rgb)


def parse_args():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    opts = {"render": True, "out": ROOT, "export": True}
    i = 0
    while i < len(argv):
        a = argv[i]
        if a == "--no-render":
            opts["render"] = False
        elif a == "--no-export":
            opts["export"] = False
        elif a == "--out":
            opts["out"] = argv[i + 1]
            i += 1
        i += 1
    return opts


def _mat(rotation=(0, 0, 0), loc=(0, 0, 0), scale=(1, 1, 1)):
    rx, ry, rz = (math.radians(a) for a in rotation)
    m = Matrix.Translation(Vector(loc)) @ Euler((rx, ry, rz), "XYZ").to_matrix().to_4x4()
    s = Matrix.Diagonal((scale[0], scale[1], scale[2], 1.0))
    return m @ s


# ---------------------------------------------------------------- kit
class Kit:
    """Accumulates flat-shaded, per-face-coloured geometry into ONE mesh."""

    def __init__(self, key, palette, seed=1, title=None, emissive=None):
        self.key = key
        self.title = title or key.replace("_", " ").title()
        self.palette = dict(palette)
        self.palette.setdefault("interior", "#2a231e")
        self.palette.setdefault("interior_deep", "#15110f")
        self.palette.setdefault("void_black", "#070606")
        self.emissive = dict(emissive or {})      # key -> strength
        self.rng = random.Random(seed)
        self.opts = parse_args()
        self.verts = []        # Vector
        self.faces = []        # (idx tuple, material name)
        self.colliders = []    # dicts
        self.trig = None
        self.meta = {}
        self.ground_patch = None
        bpy.ops.wm.read_factory_settings(use_empty=True)

    # ---- material picking ------------------------------------------------
    def pick(self, mat, jitter=True):
        """'rock' -> one of rock / rock.d / rock.l (per face). 'rock!' = no jitter."""
        if mat.endswith("!") or not jitter or mat in self.emissive:
            return mat.rstrip("!")
        r = self.rng.random()
        return mat + (".d" if r < 0.3 else ".l" if r > 0.78 else "")

    # ---- raw geometry ----------------------------------------------------
    def add(self, verts, faces, mat, m=None, jitter=True):
        """verts: list of xyz; faces: lists of indices; mat: palette key or list per face."""
        base = len(self.verts)
        for v in verts:
            v = Vector(v)
            self.verts.append(m @ v if m is not None else v)
        for i, f in enumerate(faces):
            mm = mat[i] if isinstance(mat, (list, tuple)) else mat
            self.faces.append((tuple(base + j for j in f), self.pick(mm, jitter)))
        return base

    def poly(self, pts, mat, jitter=False):
        self.add(pts, [list(range(len(pts)))], mat, jitter=jitter)

    # ---- primitives ------------------------------------------------------
    def box(self, loc, size, mat, rot=(0, 0, 0), taper=1.0, jitter=True, skew=(0, 0)):
        """Axis box centred on loc (size = full x,y,z). taper scales the top face."""
        sx, sy, sz = (s / 2 for s in size)
        t = taper
        v = [(-sx, -sy, -sz), (sx, -sy, -sz), (sx, sy, -sz), (-sx, sy, -sz),
             (-sx * t + skew[0], -sy * t + skew[1], sz), (sx * t + skew[0], -sy * t + skew[1], sz),
             (sx * t + skew[0], sy * t + skew[1], sz), (-sx * t + skew[0], sy * t + skew[1], sz)]
        f = [(0, 3, 2, 1), (4, 5, 6, 7), (0, 1, 5, 4), (1, 2, 6, 5), (2, 3, 7, 6), (3, 0, 4, 7)]
        self.add(v, f, mat, _mat(rot, loc), jitter)

    def cyl(self, base, r0, r1, h, mat, segs=6, rot=(0, 0, 0), caps=True, jitter=True,
            scale=(1, 1, 1)):
        """Tapered prism standing on `base` (bottom centre) along local +Z. r1=0 -> cone."""
        v, f = [], []
        for i in range(segs):
            a = 2 * math.pi * (i + 0.5) / segs
            v.append((math.cos(a) * r0, math.sin(a) * r0, 0))
        if r1 > 0:
            for i in range(segs):
                a = 2 * math.pi * (i + 0.5) / segs
                v.append((math.cos(a) * r1, math.sin(a) * r1, h))
            for i in range(segs):
                j = (i + 1) % segs
                f.append((i, j, segs + j, segs + i))
            if caps:
                f.append(tuple(range(segs - 1, -1, -1)))
                f.append(tuple(range(segs, 2 * segs)))
        else:
            v.append((0, 0, h))
            for i in range(segs):
                f.append((i, (i + 1) % segs, segs))
            if caps:
                f.append(tuple(range(segs - 1, -1, -1)))
        self.add(v, f, mat, _mat(rot, base, scale), jitter)

    def cone(self, base, r, h, mat, segs=5, rot=(0, 0, 0), jitter=True):
        self.cyl(base, r, 0, h, mat, segs, rot, jitter=jitter)

    def rock(self, loc, size, mat, subdiv=1, rough=0.22, flat_bottom=True, rot=None, jitter=True,
             sink=0.0):
        """Low-poly boulder: jittered icosphere (80 tris at subdiv 1, 320 at 2)."""
        bm = bmesh.new()
        bmesh.ops.create_icosphere(bm, subdivisions=subdiv, radius=1.0)
        for vert in bm.verts:
            n = vert.co.normalized()
            vert.co = n * (1.0 + self.rng.uniform(-rough, rough))
            if flat_bottom and vert.co.z < -0.35:
                vert.co.z = -0.35 - (vert.co.z + 0.35) * 0.15
        verts = [tuple(vt.co) for vt in bm.verts]
        faces = [[vt.index for vt in fc.verts] for fc in bm.faces]
        bm.free()
        if rot is None:
            rot = (self.rng.uniform(-8, 8), self.rng.uniform(-8, 8), self.rng.uniform(0, 360))
        loc = (loc[0], loc[1], loc[2] - sink)
        self.add(verts, faces, mat, _mat(rot, loc, size), jitter)

    def tube(self, pts, radii, mat, segs=5, jitter=True, cap_end=True):
        """Tapered tube along a polyline (horns, roots, ribs, tusks). radii per point (0 = tip)."""
        pts = [Vector(p) for p in pts]
        rings = []
        v, f = [], []
        up = Vector((0, 0, 1))
        for i, p in enumerate(pts):
            d = (pts[min(i + 1, len(pts) - 1)] - pts[max(i - 1, 0)]).normalized()
            ref = up if abs(d.dot(up)) < 0.9 else Vector((1, 0, 0))
            a = d.cross(ref).normalized()
            b = d.cross(a).normalized()
            r = radii[i]
            if r <= 1e-4:
                rings.append([len(v)])
                v.append(tuple(p))
                continue
            ring = []
            for s in range(segs):
                ang = 2 * math.pi * s / segs
                ring.append(len(v))
                v.append(tuple(p + (a * math.cos(ang) + b * math.sin(ang)) * r))
            rings.append(ring)
        for r0, r1 in zip(rings, rings[1:]):
            if len(r1) == 1:
                for s in range(len(r0)):
                    f.append((r0[s], r0[(s + 1) % len(r0)], r1[0]))
            elif len(r0) == 1:
                for s in range(len(r1)):
                    f.append((r1[(s + 1) % len(r1)], r1[s], r0[0]))
            else:
                for s in range(segs):
                    t = (s + 1) % segs
                    f.append((r0[s], r0[t], r1[t], r1[s]))
        if len(rings[0]) > 1:
            f.append(tuple(reversed(rings[0])))
        if cap_end and len(rings[-1]) > 1:
            f.append(tuple(rings[-1]))
        self.add(v, f, mat, None, jitter)

    def arc_pts(self, start, ctrl, end, n=4):
        """Quadratic bezier points - handy for curved horns/roots/ribs."""
        s, c, e = Vector(start), Vector(ctrl), Vector(end)
        return [tuple((1 - t) ** 2 * s + 2 * (1 - t) * t * c + t * t * e)
                for t in (i / n for i in range(n + 1))]

    def disc(self, loc, r, mat, segs=10, z=0.012, jag=0.15, jitter=False, sy=1.0):
        """Flat ground decal (scorch mark, dirt patch). Drawn a hair above the ground."""
        v = [(loc[0], loc[1], z)]
        for i in range(segs):
            a = 2 * math.pi * i / segs
            rr = r * (1 + self.rng.uniform(-jag, jag))
            v.append((loc[0] + math.cos(a) * rr, loc[1] + math.sin(a) * rr * sy, z))
        f = [(0, i + 1, (i + 1) % segs + 1) for i in range(segs)]
        self.add(v, f, mat, None, jitter)

    def skull(self, loc, s, mat="bone", socket="socket", rot=(0, 0, 0)):
        """Chunky low-poly skull (~40 tris) facing -Y."""
        m = _mat(rot, loc, (s, s, s))

        def b(c, sz, mt, taper=1.0):
            sx, sy, sz2 = (q / 2 for q in sz)
            v = [(-sx, -sy, -sz2), (sx, -sy, -sz2), (sx, sy, -sz2), (-sx, sy, -sz2),
                 (-sx * taper, -sy * taper, sz2), (sx * taper, -sy * taper, sz2),
                 (sx * taper, sy * taper, sz2), (-sx * taper, sy * taper, sz2)]
            v = [(p[0] + c[0], p[1] + c[1], p[2] + c[2]) for p in v]
            f = [(0, 3, 2, 1), (4, 5, 6, 7), (0, 1, 5, 4), (1, 2, 6, 5), (2, 3, 7, 6), (3, 0, 4, 7)]
            self.add(v, f, mt, m, jitter=False)
        b((0, 0, 0.55), (1.0, 1.0, 0.8), mat, 0.8)            # cranium
        b((0, -0.05, 0.1), (0.7, 0.8, 0.35), mat, 1.0)        # jaw
        b((-0.22, -0.52, 0.5), (0.24, 0.06, 0.22), socket)    # eyes
        b((0.22, -0.52, 0.5), (0.24, 0.06, 0.22), socket)
        b((0, -0.47, 0.3), (0.12, 0.06, 0.12), socket)        # nose

    def figure(self, loc, height=1.8, rot_z=0):
        """1.8 m player-height reference (blocky adventurer). Goes to the REF collection."""
        k = height / 1.8
        saved = (len(self.verts), len(self.faces))
        m = _mat((0, 0, rot_z), loc, (k, k, k))
        parts = [((0.0, 0, 0.45), (0.34, 0.2, 0.9), "ref_legs"),
                 ((0.0, 0, 1.2), (0.46, 0.26, 0.62), "ref_shirt"),
                 ((-0.3, 0, 1.18), (0.13, 0.14, 0.6), "ref_shirt"),
                 ((0.3, 0, 1.18), (0.13, 0.14, 0.6), "ref_shirt"),
                 ((0.0, 0, 1.64), (0.26, 0.26, 0.3), "ref_skin"),
                 ((0.0, 0.02, 1.77), (0.28, 0.28, 0.06), "ref_hair")]
        for c, sz, mt in parts:
            sx, sy, sz2 = (q / 2 for q in sz)
            v = [(c[0] - sx, c[1] - sy, c[2] - sz2), (c[0] + sx, c[1] - sy, c[2] - sz2),
                 (c[0] + sx, c[1] + sy, c[2] - sz2), (c[0] - sx, c[1] + sy, c[2] - sz2),
                 (c[0] - sx, c[1] - sy, c[2] + sz2), (c[0] + sx, c[1] - sy, c[2] + sz2),
                 (c[0] + sx, c[1] + sy, c[2] + sz2), (c[0] - sx, c[1] + sy, c[2] + sz2)]
            f = [(0, 3, 2, 1), (4, 5, 6, 7), (0, 1, 5, 4), (1, 2, 6, 5), (2, 3, 7, 6), (3, 0, 4, 7)]
            self.add(v, f, mt, m, jitter=False)
        new_v = self.verts[saved[0]:]
        new_f = self.faces[saved[1]:]
        del self.verts[saved[0]:]
        del self.faces[saved[1]:]
        self._ref = getattr(self, "_ref", [])
        self._ref.append((new_v, [(tuple(i - saved[0] for i in fi), mt) for fi, mt in new_f]))


    # ---- small reusable props ------------------------------------------------
    def torch(self, loc, flame="flame", h=1.6):
        """Stick torch with a chunky emissive flame (palette key `flame` must be emissive)."""
        x, y, z = loc
        self.cyl((x, y, z), 0.06, 0.05, h, "wood_dark", segs=4)
        self.box((x, y, z + h), (0.2, 0.2, 0.16), "wood_dark!")
        self.cone((x, y, z + h + 0.08), 0.16, 0.42, flame, segs=4, rot=(0, 0, 45))

    def scratches(self, x, y, z, n=3, length=0.9, angle=-60, gap=0.16, mat="scratch", w=0.07):
        """Claw marks: n parallel dark gouges on a surface facing -Y at depth y."""
        for i in range(n):
            ox = (i - (n - 1) / 2) * gap
            self.box((x + ox, y, z + (i - (n - 1) / 2) * 0.05), (w, 0.05, length * (0.8 + 0.2 * (i % 2 == 0))),
                     mat + "!", rot=(0, angle + 90, 0))

    def web(self, cx, cy, cz, r, a0, a1, mat="web", spokes=5, rings=3, t=0.035):
        """Chunky corner web in the XZ plane (facing -Y) from angle a0 to a1 (degrees)."""
        pts_by_ring = []
        for sp in range(spokes):
            a = math.radians(a0 + (a1 - a0) * sp / (spokes - 1))
            end = (cx + math.cos(a) * r, cy, cz + math.sin(a) * r)
            self.tube([(cx, cy, cz), end], [t, t * 0.8], mat, segs=3)
            pts_by_ring.append(a)
        for ri in range(1, rings + 1):
            rr = r * ri / (rings + 0.3)
            ring = []
            for a in pts_by_ring:
                sag = 0.08 * rr * (1 if ri % 2 else 0.6)
                ring.append((cx + math.cos(a) * (rr - sag), cy - 0.01, cz + math.sin(a) * (rr - sag)))
            for p0, p1 in zip(ring, ring[1:]):
                self.tube([p0, p1], [t * 0.7, t * 0.7], mat, segs=3)

    # ---- the key piece: a thick wall with an arched walk-through mouth -----
    def archway(self, width, spring, depth, outer_w, outer_h, front="rock", inner=None,
                shape="round", segs=7, y0=0.0, z0=0.0, jag=0.25, floor="interior",
                back=True, slices=3, peak=None, bulge=0.35):
        """Solid slab (outer_w x depth x outer_h) with an opening `width` wide whose sides
        rise to `spring` m, then close with a round / pointed / flat / oval top.
        The inside of the opening is lined with progressively darker 'interior' colours
        and capped with a black back plane -> reads as a passage going inside.
        Returns dict with the opening dimensions (used for the trigger volume)."""
        hw = width / 2.0
        rise = hw if peak is None else peak
        self._slab_hw = max(getattr(self, "_slab_hw", 0.0), outer_w / 2.0 - 0.15)
        # inner contour: bottom-left -> up -> over -> bottom-right
        inner_pts = [(-hw, z0), (-hw, z0 + spring)]
        for i in range(1, segs):
            t = i / segs
            a = math.pi * (1 - t)
            if shape == "round" or shape == "oval":
                x, z = hw * math.cos(a), spring + rise * math.sin(a)
            elif shape == "pointed":
                x = hw * math.cos(a)
                z = spring + rise * (1 - abs(x) / hw) ** 0.8
            else:  # flat lintel
                x, z = -hw + width * t, spring
            inner_pts.append((x, z0 + z))
        inner_pts += [(hw, z0 + spring), (hw, z0)]
        top_z = max(p[1] for p in inner_pts)
        # outer contour: matching count, blown out to the slab outline + jag
        outer = []
        n = len(inner_pts)
        ow, oh = outer_w / 2.0, z0 + outer_h
        for i, (x, z) in enumerate(inner_pts):
            t = i / (n - 1)
            # walk the outline: left edge (bottom->top), top edge, right edge (top->bottom)
            if t < 0.25:
                u = t / 0.25
                ox, oz = -ow, z0 + (oh - z0) * u * 0.92
            elif t > 0.75:
                u = (t - 0.75) / 0.25
                ox, oz = ow, z0 + (oh - z0) * (1 - u) * 0.92
            else:
                u = (t - 0.25) / 0.5
                ox, oz = -ow + outer_w * u, oh
            if 0 < i < n - 1:
                ox += self.rng.uniform(-jag, jag)
                oz += self.rng.uniform(-jag, jag) if oz > z0 + 0.3 else 0
            outer.append((ox, oz))
        outer[0] = (-ow, z0)
        outer[-1] = (ow, z0)
        inner = inner or ["interior", "interior", "interior_deep"]
        ys = [y0 + depth * i / slices for i in range(slices + 1)]

        def V(p, y):
            return (p[0], y, p[1])
        # front face: inner contour -> jittered mid ring -> outer contour (faceted, not flat)
        mid = []
        for i in range(n):
            f = 0.45 + self.rng.uniform(-0.12, 0.12)
            mx = inner_pts[i][0] + (outer[i][0] - inner_pts[i][0]) * f
            mz = inner_pts[i][1] + (outer[i][1] - inner_pts[i][1]) * f
            if i in (0, n - 1):
                mz = z0
            mid.append(((mx, mz), ys[0] - bulge * self.rng.uniform(0.3, 1.0)))
        oy = [ys[0] + (0 if i in (0, n - 1) else self.rng.uniform(0, bulge * 0.8)) for i in range(n)]
        for i in range(n - 1):
            a0, a1 = V(inner_pts[i], ys[0]), V(inner_pts[i + 1], ys[0])
            m0, m1 = V(mid[i][0], mid[i][1]), V(mid[i + 1][0], mid[i + 1][1])
            o0, o1 = V(outer[i], oy[i]), V(outer[i + 1], oy[i + 1])
            self.add([a0, a1, m1], [(0, 1, 2)], front)
            self.add([a0, m1, m0], [(0, 1, 2)], front)
            self.add([m0, m1, o1], [(0, 1, 2)], front)
            self.add([m0, o1, o0], [(0, 1, 2)], front)
        for i in range(n - 1):
            q = [V(inner_pts[i], ys[-1]), V(inner_pts[i + 1], ys[-1]), V(outer[i + 1], ys[-1]), V(outer[i], ys[-1])]
            self.add(q[::-1], [(0, 1, 2, 3)], front)
        # opening lining: slice by depth, darker as it goes in
        for s in range(slices):
            mat = inner[min(s, len(inner) - 1)]
            for i in range(n - 1):
                a, b = inner_pts[i], inner_pts[i + 1]
                q = [V(a, ys[s]), V(a, ys[s + 1]), V(b, ys[s + 1]), V(b, ys[s])]
                self.add(q, [(0, 1, 2, 3)], mat + "!")
        # outer skin (sides + top)
        for i in range(n - 1):
            a, b = outer[i], outer[i + 1]
            q = [V(a, oy[i]), V(b, oy[i + 1]), V(b, ys[-1]), V(a, ys[-1])]
            self.add(q, [(0, 1, 2, 3)], front)
        # floor strip + black back plane
        for s in range(slices):
            mat = inner[min(s, len(inner) - 1)]
            self.poly([(-hw, ys[s], z0 + 0.015), (hw, ys[s], z0 + 0.015),
                       (hw, ys[s + 1], z0 + 0.015), (-hw, ys[s + 1], z0 + 0.015)][::-1], floor if s == 0 else mat + "!")
        if back:
            yb = ys[-1] - 0.02
            pts = [V(p, yb) for p in inner_pts]
            self.add(pts[::-1], [list(range(len(pts)))], "void_black!", jitter=False)
        info = {"width": width, "height": top_z - z0, "depth": depth, "y0": y0, "z0": z0}
        self.meta.setdefault("openings", []).append(info)
        return info

    def mound(self, cx, cy, rx, ry, h, mat, grid=7, rough=0.12, mat_top=None, top_frac=0.55,
              power=0.75, z0=0.0, crop_y=None, skirt_mat=None):
        """Low-poly hill (height-field over an ellipse). Keep it BEHIND the archway slab."""
        pts = {}
        n = grid
        for i in range(-n, n + 1):
            for j in range(-n, n + 1):
                u, v = i / n, j / n
                d = u * u + v * v
                if d > 1.0:
                    zz = 0.0
                else:
                    zz = h * (1 - d) ** power * (1 + self.rng.uniform(-rough, rough))
                pts[(i, j)] = (cx + u * rx + self.rng.uniform(-0.1, 0.1) * rx / n,
                               cy + v * ry + self.rng.uniform(-0.1, 0.1) * ry / n, z0 + zz - 0.05)
        for i in range(-n, n):
            for j in range(-n, n):
                q = [pts[(i, j)], pts[(i + 1, j)], pts[(i + 1, j + 1)], pts[(i, j + 1)]]
                if all(p[2] <= z0 - 0.04 for p in q):
                    continue
                if crop_y is not None and pts[(i, j)][1] < crop_y:
                    # cropped (the archway slab sits here) - drop a skirt down to the ground
                    if pts[(i, j + 1)][1] >= crop_y and j + 1 <= n:
                        a, b = pts[(i, j + 1)], pts[(i + 1, j + 1)]
                        slab = getattr(self, "_slab_hw", 0.0)
                        if max(abs(a[0]), abs(b[0])) < slab:
                            continue          # the archway slab already closes this part
                        if a[2] > z0 or b[2] > z0:
                            self.add([(a[0], a[1], z0 - 0.05), (b[0], b[1], z0 - 0.05), b, a],
                                     [(0, 1, 2, 3)], skirt_mat or mat)
                    continue
                zc = sum(p[2] for p in q) / 4
                mt = mat_top if (mat_top and zc > z0 + h * top_frac) else mat
                # split into 2 tris along the shorter diagonal -> faceted look
                self.add([q[0], q[1], q[2]], [(0, 1, 2)], mt)
                self.add([q[0], q[2], q[3]], [(0, 1, 2)], mt)

    # ---- gameplay volumes ---------------------------------------------------
    def collider(self, name, loc, size):
        """Invisible solid box the player cannot walk through (never covers the doorway)."""
        self.colliders.append({"name": "COL_" + name, "center": list(loc), "size": list(size)})

    def trigger(self, loc, size):
        """Doorway trigger volume: when the player enters it, call the game's EXISTING
        enter-dungeon logic. Exactly one per entrance."""
        self.trig = {"name": "TRIGGER_door", "center": list(loc), "size": list(size)}

    # ---- build / save / export / render --------------------------------------
    def _materials(self):
        mats = {}
        for key, hx in self.palette.items():
            base = hex_rgb(hx)
            variants = {key: base}
            if key not in self.emissive:
                variants[key + ".d"] = shade(base, 0.86)
                variants[key + ".l"] = shade(base, 1.10)
            for name, rgb in variants.items():
                m = bpy.data.materials.new(name)
                m.use_nodes = True
                bsdf = m.node_tree.nodes.get("Principled BSDF")
                lin = tuple(srgb_to_lin(c) for c in rgb)
                bsdf.inputs["Base Color"].default_value = (*lin, 1.0)
                bsdf.inputs["Roughness"].default_value = 1.0
                bsdf.inputs["Metallic"].default_value = 0.0
                bsdf.inputs["Specular IOR Level"].default_value = 0.0
                if key in self.emissive:
                    bsdf.inputs["Emission Color"].default_value = (*lin, 1.0)
                    bsdf.inputs["Emission Strength"].default_value = self.emissive[key]
                m.diffuse_color = (*lin, 1.0)
                mats[name] = m
        return mats

    def _make_object(self, name, verts, faces, mats, coll):
        used = sorted({mt for _, mt in faces})
        me = bpy.data.meshes.new(name)
        bm = bmesh.new()
        bv = [bm.verts.new(v) for v in verts]
        idx = {m: i for i, m in enumerate(used)}
        for fi, mt in faces:
            try:
                f = bm.faces.new([bv[i] for i in fi])
            except ValueError:
                continue
            f.material_index = idx[mt]
            f.smooth = False
        bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=0.0005)
        bmesh.ops.triangulate(bm, faces=bm.faces)
        bm.to_mesh(me)
        bm.free()
        for mt in used:
            if mt not in mats:
                raise KeyError(f"material '{mt}' not in palette")
            me.materials.append(mats[mt])
        for p in me.polygons:
            p.use_smooth = False
        ob = bpy.data.objects.new(name, me)
        coll.objects.link(ob)
        return ob

    def finish(self):
        scene = bpy.context.scene
        # reference-figure / ground colours only used in concept renders
        self.palette.update({"ref_legs": "#3d4a63", "ref_shirt": "#8f2f2a", "ref_skin": "#d2a47c",
                             "ref_hair": "#4a3526", "ref_ground": "#6f7a4a"})
        mats = self._materials()
        ent = bpy.data.collections.new("ENTRANCE")
        col = bpy.data.collections.new("COLLISION")
        ref = bpy.data.collections.new("REF_ONLY")
        for c in (ent, col):
            scene.collection.children.link(c)
        # A second scene holds the concept camera, sun, ground and 1.8 m figure, so the main
        # scene (what blend2bam / glTF export see) contains ONLY the entrance + collision.
        cscene = bpy.data.scenes.new("CONCEPT_RENDER")
        cscene.collection.children.link(ent)
        cscene.collection.children.link(ref)
        self._cscene = cscene
        ob = self._make_object(self.key, self.verts, self.faces, mats, ent)
        tris = len(ob.data.polygons)
        # collision boxes (wire display, never rendered, not exported to glb)
        for c in self.colliders + ([self.trig] if self.trig else []):
            bpy.ops.mesh.primitive_cube_add(size=1.0, location=c["center"])
            b = bpy.context.active_object
            b.name = c["name"]
            b.scale = c["size"]
            b.display_type = "WIRE"
            b.hide_render = True
            # passive rigid body BOX -> blend2bam turns it into a Panda3D CollisionBox
            bpy.context.view_layer.objects.active = b
            try:
                bpy.ops.rigidbody.object_add(type="PASSIVE")
                b.rigid_body.collision_shape = "BOX"
            except Exception as exc:  # rigid body world unavailable - boxes still in json
                print("[osrs_kit] rigid body skipped:", exc)
            b["dungeon_role"] = "trigger" if c["name"].startswith("TRIGGER") else "solid"
            for cc in b.users_collection:
                cc.objects.unlink(b)
            col.objects.link(b)
        # reference figure + ground (concept render only)
        figc = bpy.data.collections.new("REF_FIGURE")
        ref.children.link(figc)
        for i, (v, f) in enumerate(getattr(self, "_ref", [])):
            self._make_object(f"REF_player_1p8m_{i}", v, f, mats, figc)
        lo = Vector((min(v.x for v in self.verts), min(v.y for v in self.verts), min(v.z for v in self.verts)))
        hi = Vector((max(v.x for v in self.verts), max(v.y for v in self.verts), max(v.z for v in self.verts)))
        R = max(hi.x - lo.x, hi.y - lo.y) * 0.75 + 3
        cx0, cy0 = (lo.x + hi.x) / 2, (lo.y + hi.y) / 2
        cut = self.meta.get("ground_cutout")
        if cut:   # square ground with a rectangular hole (e.g. the crypt stairwell)
            hx, hy = cut["size"][0] / 2, cut["size"][1] / 2
            ax0, ax1 = cut["center"][0] - hx, cut["center"][0] + hx
            ay0, ay1 = cut["center"][1] - hy, cut["center"][1] + hy
            X0, X1, Y0, Y1 = cx0 - R, cx0 + R, cy0 - R, cy0 + R
            rects = [(X0, Y0, X1, ay0), (X0, ay1, X1, Y1), (X0, ay0, ax0, ay1), (ax1, ay0, X1, ay1)]
            gv, gf = [], []
            for (a, b, c, d) in rects:
                n0 = len(gv)
                gv += [(a, b, -0.01), (c, b, -0.01), (c, d, -0.01), (a, d, -0.01)]
                gf.append((n0, n0 + 1, n0 + 2, n0 + 3))
        else:
            gv, gf = [(cx0, cy0, -0.01)], []
            for i in range(16):
                a = 2 * math.pi * i / 16
                gv.append((math.cos(a) * R + cx0, math.sin(a) * R + cy0, -0.01))
            gf = [(0, i + 1, (i + 1) % 16 + 1) for i in range(16)]
        self._make_object("REF_ground", gv, [(f, "ref_ground") for f in gf], mats, ref)

        out = self.opts["out"]
        for d in ("blend", "glb", "json", "images"):
            os.makedirs(os.path.join(out, d), exist_ok=True)
        meta = {
            "key": self.key, "title": self.title, "triangles": tris,
            "bounds_min": [round(x, 3) for x in lo], "bounds_max": [round(x, 3) for x in hi],
            "front": "-Y", "up": "+Z", "units": "metres",
            "colliders": self.colliders, "trigger": self.trig,
            "palette": {k: v for k, v in self.palette.items() if not k.startswith("ref_")},
            "emissive": self.emissive,
        }
        self._setup_render(lo, hi)
        meta.update(self.meta)
        with open(os.path.join(out, "json", self.key + ".json"), "w") as fh:
            json.dump(meta, fh, indent=2)
        print(f"[osrs_kit] {self.key}: {tris} triangles, bounds {tuple(round(x,2) for x in lo)} .. "
              f"{tuple(round(x,2) for x in hi)}")
        if self.opts["render"]:
            cscene.render.filepath = os.path.join(out, "images", self.key + "_concept.png")
            bpy.ops.render.render(write_still=True, scene=cscene.name)
        bpy.ops.wm.save_as_mainfile(filepath=os.path.join(out, "blend", self.key + ".blend"))
        if self.opts["export"]:
            self.export_glb(os.path.join(out, "glb", self.key + ".glb"), ent)
            if getattr(self, "_ref", None):   # 1.8 m figure, in place, for in-engine scale checks
                os.makedirs(os.path.join(out, "ref"), exist_ok=True)
                scene.collection.children.link(figc)          # temporarily, for the export
                self.export_glb(os.path.join(out, "ref", self.key + "_ref_player.glb"), figc)
                scene.collection.children.unlink(figc)
        return meta

    def export_glb(self, path, ent):
        vl = bpy.context.view_layer
        vl.active_layer_collection = vl.layer_collection.children[ent.name]
        bpy.ops.export_scene.gltf(filepath=path, export_format="GLB", use_active_collection=True,
                                  export_apply=True, export_texcoords=False, export_normals=True,
                                  export_materials="EXPORT", export_cameras=False,
                                  export_lights=False, export_yup=True)
        print("[osrs_kit] wrote", path)

    def _setup_render(self, lo, hi):
        """3/4 game camera (front-right, 35 deg azimuth, 30 deg elevation), sun + ambient."""
        scene = self._cscene
        scene.render.engine = "BLENDER_EEVEE_NEXT"
        scene.render.resolution_x = scene.render.resolution_y = 1024
        scene.render.film_transparent = False
        scene.view_settings.view_transform = "Standard"
        world = bpy.data.worlds.new("World")
        world.use_nodes = True
        bg = world.node_tree.nodes["Background"]
        bg.inputs["Color"].default_value = (0.34, 0.32, 0.28, 1)   # sRGB ~ (0.62,0.60,0.56)
        bg.inputs["Strength"].default_value = 1.0
        scene.world = world
        try:
            scene.eevee.taa_render_samples = 16
            scene.eevee.use_shadows = True
        except Exception:
            pass
        sun = bpy.data.lights.new("Sun", "SUN")
        sun.energy = 3.2
        sun.color = (1.0, 0.95, 0.86)
        sun.angle = math.radians(3)
        so = bpy.data.objects.new("Sun", sun)
        so.rotation_euler = Euler((math.radians(45), 0, math.radians(35)), "XYZ")
        scene.collection.objects.link(so)
        lo2 = Vector((lo.x, lo.y, max(lo.z, -0.3)))
        centre = (lo2 + hi) / 2
        if hasattr(self, "cam_target"):
            centre = Vector(self.cam_target)
        cam = bpy.data.cameras.new("Cam")
        cam.lens_unit = "FOV"
        cam.angle = math.radians(30)
        co = bpy.data.objects.new("Cam", cam)
        az, el = math.radians(35), math.radians(30)
        fwd = -Vector((math.sin(az) * math.cos(el), -math.cos(az) * math.cos(el), math.sin(el)))
        right = fwd.cross(Vector((0, 0, 1))).normalized()
        up = right.cross(fwd).normalized()
        corners = [v for v in self.verts if v.z > -0.3]
        # also keep the reference figure in frame
        for v, _ in getattr(self, "_ref", []):
            corners += [Vector(p) for p in v[::6]]
        tan_half = math.tan(cam.angle / 2) / getattr(self, "cam_margin", 1.12)
        dist = 1.0
        for c in corners:    # smallest distance that keeps every corner inside the frustum
            rel = c - centre
            a, b, depth = rel.dot(right), rel.dot(up), rel.dot(fwd)
            dist = max(dist, abs(a) / tan_half - depth, abs(b) / tan_half - depth)
        dist *= getattr(self, "cam_scale", 1.0)
        co.location = centre - fwd * dist
        self.meta["concept_camera"] = {"target": [round(c, 3) for c in centre], "distance": round(dist, 3),
                                       "azimuth_deg": 35, "elevation_deg": 30, "fov_deg": 30,
                                       "note": "camera sits front-right: target + dist*(sin az*cos el, -cos az*cos el, sin el)"}
        d = centre - co.location
        co.rotation_euler = d.to_track_quat("-Z", "Y").to_euler()
        scene.collection.objects.link(co)
        scene.camera = co
