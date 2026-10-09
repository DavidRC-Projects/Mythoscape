"""Geometry helpers on the rigged rest-pose body: garment shells, hem binding + stitching, tubes, skirts, studs."""
import bpy, bmesh, math, random
from mathutils import Vector
from mathutils.bvhtree import BVHTree
import fv_common as C
import fv_npc_helpers as H
import pl_rig as R


class Ctx:
    """Per-sex build context."""
    def __init__(self, kind, col, body, eyes, J, arm, bw):
        self.kind, self.col, self.body, self.eyes, self.J, self.arm, self.bw = kind, col, body, eyes, J, arm, bw
        self.mask = J["mask"]; self.h = J["h"]; self.s = self.h / 1.617
        self.layers = {}       # layer id -> [objects]
        bm = bmesh.new(); bm.from_mesh(body.data); self.tree = BVHTree.FromBMesh(bm); bm.free()
        self.cur = None

    def layer(self, lid):
        self.cur = lid
        self.layers.setdefault(lid, [])
        return self

    def add(self, o):
        self.layers[self.cur].append(o)
        return o

    def z(self, frac):            # height fraction -> metres for this body
        return frac * self.h

    def nearest(self, co):
        loc, nrm, idx, d = self.tree.find_nearest(Vector(co))
        return loc, nrm


def shell(ctx, name, pred, mat, offset=0.012, thick=0.004, subsurf=1, folds=0.0035, fold_size=0.035):
    o = H.extract(ctx.body, name, pred, offset=offset, thick=thick, mat=mat, col=ctx.col, subsurf=subsurf)
    R.copy_groups_from_body(o, ctx.body)
    if mat is not None and ("Steel" in mat.name or "Mail" in mat.name):
        folds = 0
    if folds:
        # real geometric creases at rest pose (before the armature, so they ride with the cloth)
        tex = bpy.data.textures.new(f"{name}_fold", "CLOUDS"); tex.noise_scale = fold_size; tex.noise_depth = 2
        if o.data.polygons and len(o.data.polygons) > 0:
            sub0 = o.modifiers.new("PreSub", "SUBSURF"); sub0.levels = 1; sub0.render_levels = 1
            o.modifiers.move(len(o.modifiers) - 1, 0)
            d = o.modifiers.new("Folds", "DISPLACE"); d.texture = tex; d.strength = folds; d.mid_level = 0.5; d.texture_coords = "LOCAL"
            o.modifiers.move(len(o.modifiers) - 1, 1)
            for md in o.modifiers:
                if md.type == "SUBSURF" and md.name != "PreSub":
                    o.modifiers.remove(md); break
    R.ensure_armature_mod(o, ctx.arm)
    return ctx.add(o)


def boundary_loops(o, min_len=8):
    me = o.data
    bm = bmesh.new(); bm.from_mesh(me); bm.verts.ensure_lookup_table(); bm.normal_update()
    edges = [e for e in bm.edges if len(e.link_faces) == 1]
    adj = {}
    for e in edges:
        a, b = e.verts[0].index, e.verts[1].index
        adj.setdefault(a, []).append(b); adj.setdefault(b, []).append(a)
    seen = set(); loops = []
    nrm = {v.index: v.normal.copy() for v in bm.verts}
    co = {v.index: (o.matrix_world @ v.co) for v in bm.verts}
    for start in list(adj):
        if start in seen:
            continue
        loop = [start]; seen.add(start); prev = None; cur = start
        while True:
            nxt = [n for n in adj[cur] if n != prev and n not in seen]
            if not nxt:
                break
            prev, cur = cur, nxt[0]; loop.append(cur); seen.add(cur)
        if len(loop) >= min_len:
            closed = start in adj[loop[-1]]
            loops.append(([co[i] for i in loop], [nrm[i] for i in loop], closed))
    bm.free()
    return loops


def _smooth(pts, closed, it=3):
    pts = [p.copy() for p in pts]
    n = len(pts)
    for _ in range(it):
        new = []
        for i in range(n):
            if not closed and (i == 0 or i == n - 1):
                new.append(pts[i]); continue
            a = pts[(i - 1) % n]; b = pts[(i + 1) % n]
            new.append(pts[i] * 0.5 + (a + b) * 0.25)
        pts = new
    return pts


def tube_mesh(name, pts, r, mat, col, closed=False, segs=6, uv_scale=1.0):
    bm = bmesh.new(); uvl = bm.loops.layers.uv.new("UVMap")
    n = len(pts)
    rings = []; acc = [0.0]
    for i in range(1, n):
        acc.append(acc[-1] + (pts[i] - pts[i - 1]).length)
    for i, p in enumerate(pts):
        a = pts[(i - 1) % n] if (closed or i > 0) else pts[i]
        b = pts[(i + 1) % n] if (closed or i < n - 1) else pts[i]
        t = (b - a); t = t.normalized() if t.length > 1e-9 else Vector((0, 0, 1))
        up = Vector((0, 0, 1)) if abs(t.z) < 0.9 else Vector((1, 0, 0))
        u = t.cross(up).normalized(); v = t.cross(u).normalized()
        rr = r(i / max(1, n - 1)) if callable(r) else r
        rings.append([bm.verts.new(p + (u * math.cos(2 * math.pi * k / segs) + v * math.sin(2 * math.pi * k / segs)) * rr) for k in range(segs)])
    m = n if closed else n - 1
    for i in range(m):
        i2 = (i + 1) % n
        for k in range(segs):
            k2 = (k + 1) % segs
            f = bm.faces.new((rings[i][k], rings[i][k2], rings[i2][k2], rings[i2][k]))
            u0 = acc[i] * uv_scale; u1 = (acc[i2] if i2 > i else acc[-1] + (pts[0] - pts[-1]).length) * uv_scale
            for lp, (uu, vv) in zip(f.loops, ((u0, k / segs), (u0, (k + 1) / segs), (u1, (k + 1) / segs), (u1, k / segs))):
                lp[uvl].uv = (uu, vv)
    return C.obj_from_bm(bm, name, mat, col)


def hem(ctx, o, mat, r=0.0045, stitch_mat=None, push=0.002, min_len=10, skip=None):
    """Rolled hem/binding tube along every open edge of a garment shell + dashed stitching on it."""
    out = []
    for k, (pts, nrms, closed) in enumerate(boundary_loops(o, min_len)):
        if skip and skip(pts):
            continue
        p2 = [p + n * (push + r * 0.6) for p, n in zip(pts, nrms)]
        p2 = _smooth(p2, closed, 4)
        t = tube_mesh(f"{o.name}_hem{k}", p2, r, mat, ctx.col, closed=closed)
        R.bind(t, ctx.arm, ctx.bw); out.append(ctx.add(t))
        if stitch_mat is not None:
            p3 = [p + n * (r * 0.9) for p, n in zip(p2, nrms)]
            st = tube_mesh(f"{o.name}_st{k}", p3, r * 0.28, stitch_mat, ctx.col, closed=closed, segs=4)
            R.bind(st, ctx.arm, ctx.bw); out.append(ctx.add(st))
    return out


def surf_pt(ctx, x, z, front=True, push=0.0):
    hit, nrm = H.surf(ctx.tree, (x, -0.8 if front else 0.8, z), (0, 1 if front else -1, 0))
    if hit is None:
        return None, None
    return hit + nrm * push, nrm


def studs(ctx, pts_nrms, r, mat, name="stud", bone=None):
    out = []
    for i, (p, n) in enumerate(pts_nrms):
        o = C.uvsphere(f"{name}{i}", r, p + n * r * 0.4, segs=12, rings=6, mat=mat, col=ctx.col, scale=(1, 1, 0.6))
        o.rotation_euler = n.to_track_quat("Z", "Y").to_euler()
        if bone:
            R.bone_parent(o, ctx.arm, bone)
        else:
            R.bind(o, ctx.arm, ctx.bw)
        out.append(ctx.add(o))
    return out


def rivets_on_loop(ctx, o, mat, r=0.004, every=0.045, inset=0.012, min_len=10):
    """Rivets along a plate's edges (slightly inside the boundary)."""
    out = []
    for pts, nrms, closed in boundary_loops(o, min_len):
        pts = _smooth(pts, closed, 3)
        acc = 0.0; cur = []
        for i in range(1, len(pts)):
            acc += (pts[i] - pts[i - 1]).length
            if acc >= every:
                acc = 0.0
                cur.append((pts[i] + nrms[i] * 0.004, nrms[i]))
        out += studs(ctx, cur, r, mat, name=f"{o.name}_rv")
    return out


def skirt(ctx, name, z_top, z_bot, r_bot, mat, folds=14, fold_amp=0.02, thick=0.005, hem_fn=None, expo=1.4, train=0.0):
    o = H.skirt(name, ctx.body, ctx.mask, z_top, z_bot, r_bot, mat, ctx.col, folds=folds, fold_amp=fold_amp, thick=thick,
                hem=hem_fn, expo=expo, train=train)
    R.bind(o, ctx.arm, ctx.bw, override=R.skirt_override(ctx.J, z_top, z_bot))
    return ctx.add(o)


def rigid(ctx, o, bone):
    R.bone_parent(o, ctx.arm, bone)
    return ctx.add(o)


def bound(ctx, o):
    R.bind(o, ctx.arm, ctx.bw)
    return ctx.add(o)


def ring_band(ctx, name, z, mat, r=0.008, grow=0.012, n=48, bone_bind=True, y_extra=0.0):
    x0, x1, y0, y1 = H.section(ctx.body, z, ctx.mask, tol=0.012)
    cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
    rx, ry = (x1 - x0) / 2 + grow, (y1 - y0) / 2 + grow + y_extra
    pts = [Vector((cx + rx * math.cos(2 * math.pi * k / n), cy + ry * math.sin(2 * math.pi * k / n), z)) for k in range(n)]
    t = tube_mesh(name, pts, r, mat, ctx.col, closed=True, segs=8)
    return bound(ctx, t)
