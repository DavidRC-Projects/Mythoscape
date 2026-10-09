"""Strand hair (Blender hair Curves, rendered as real strands in Cycles) — 6 styles, neutral grey for runtime tint."""
import bpy, bmesh, math, random
import numpy as np
from mathutils import Vector
import fv_npc_helpers as H
import pl_rig as R
import pl_mats as M
import pl_geo as G

STYLES = ["crop", "side_part", "shoulder_wavy", "long_straight", "ponytail", "braid"]


def head_info(ctx):
    V = ctx.body.data.vertices
    ez = sum(e.matrix_world.translation.z for e in ctx.eyes) / len(ctx.eyes)
    ey = sum(e.matrix_world.translation.y for e in ctx.eyes) / len(ctx.eyes)
    hv = [v.co for v in V if v.co.z > ctx.J["head"].z + 0.01 * ctx.s]
    zmax = max(p.z for p in hv); ymax = max(p.y for p in hv); ymin = min(p.y for p in hv)
    xr = max(abs(p.x) for p in hv if p.z > ez)
    return dict(ez=ez, ey=ey, top=zmax, back=ymax, front=ymin, xr=xr,
                c=Vector((0, (ymax + ymin) / 2, (zmax + ez) / 2 - 0.01 * ctx.s)))


def scalp_faces(ctx, hi, style):
    ez = hi["ez"]; s = ctx.s
    hairline_front = ez + 0.045 * s
    nape = ez - (0.07 if style in ("crop", "side_part") else 0.10) * s
    V = ctx.body.data.vertices

    def ok(co):
        if co.z > hairline_front:
            return True
        if co.y > hi["c"].y - 0.005 * s and co.z > nape and abs(co.x) < hi["xr"] * 1.02:
            # sides behind the ears + back of head
            return co.y > hi["ey"] + 0.075 * s or co.z > ez + 0.012 * s
        return False
    bm = bmesh.new(); bm.from_mesh(ctx.body.data); bm.faces.ensure_lookup_table()
    faces = []
    for f in bm.faces:
        if all(ok(v.co) for v in f.verts) and not any(ctx.mask[v.index] for v in f.verts):
            faces.append(([v.co.copy() for v in f.verts], f.normal.copy(), f.calc_area()))
    bm.free()
    return faces, ok


def sample_roots(faces, n, rnd):
    areas = np.array([a for _, _, a in faces]); cdf = np.cumsum(areas) / areas.sum()
    out = []
    for _ in range(n):
        i = int(np.searchsorted(cdf, rnd.random()))
        vs, nrm, _ = faces[min(i, len(faces) - 1)]
        a, b = rnd.random(), rnd.random()
        if a + b > 1:
            a, b = 1 - a, 1 - b
        p = vs[0] + (vs[1] - vs[0]) * a + (vs[2] - vs[0]) * b
        out.append((p, nrm))
    return out


def collide(ctx, p, margin):
    loc, nrm = ctx.nearest(p)
    d = (p - loc).dot(nrm)
    if d < margin:
        p = p + nrm * (margin - d)
    return p


def strand(ctx, hi, style, root, nrm, rnd, seg=14):
    s = ctx.s; ez = hi["ez"]; c = hi["c"]
    pts = [root.copy()]
    p = root.copy()
    side = 1 if root.x >= 0 else -1
    if style == "crop":
        L = rnd.uniform(0.020, 0.034) * s; seg = 6
        comb = Vector((0.25 * side, 0.9, 0.35 if root.y < c.y else -0.3))
        d = (nrm * 0.35 + comb.normalized()).normalized()
        for i in range(seg):
            p = p + d * (L / seg); p = collide(ctx, p, 0.0035 * s + 0.002 * s * i / seg)
            loc, n2 = ctx.nearest(p)
            if (p - loc).length > 0.009 * s:
                p = loc + (p - loc).normalized() * 0.009 * s
            d = (d + Vector((0, 0.06, -0.08))).normalized(); pts.append(p.copy())
        return pts, 0.00045 * s
    if style == "side_part":
        L = rnd.uniform(0.06, 0.10) * s; seg = 8
        part_x = 0.028 * s
        comb = Vector((-1.0 if root.x < part_x else 0.6, 0.55, 0.0))
        d = (nrm * 0.6 + comb.normalized()).normalized()
        for i in range(seg):
            p = p + d * (L / seg)
            p = collide(ctx, p, 0.006 * s + 0.004 * s * (i / seg))
            loc, n2 = ctx.nearest(p)
            if (p - loc).length > 0.016 * s:          # keep it lying on the scalp
                p = loc + (p - loc).normalized() * 0.016 * s
            d = (d + Vector((0, 0.04, -0.10))).normalized(); pts.append(p.copy())
        return pts, 0.0005 * s
    if style in ("shoulder_wavy", "long_straight"):
        L = (rnd.uniform(0.22, 0.30) if style == "shoulder_wavy" else rnd.uniform(0.40, 0.50)) * s
        seg = 16 if style == "long_straight" else 14
        part = Vector((0.0, 0, 0))
        # front roots are swept back behind the ear line so the face profile stays clear in e/w facings
        out = Vector((side * 0.75, 1.0, 0.1)) if root.y < c.y else Vector((side * 0.3, 0.8, -0.2))
        d = (nrm * 0.5 + out.normalized()).normalized()
        wave_ph = rnd.uniform(0, 6.28)
        for i in range(seg):
            u = (i + 1) / seg
            p = p + d * (L / seg)
            if style == "shoulder_wavy":
                p = p + Vector((math.cos(u * 14 + wave_ph) * 0.004, math.sin(u * 14 + wave_ph) * 0.004, 0)) * s
            p = collide(ctx, p, 0.007 * s + 0.01 * s * u)
            d = (d + Vector((0, 0.02 + (0.10 if root.y < c.y and u < 0.5 else 0.0), -0.32 - u * 0.5))).normalized()
            if p.y < hi["ey"] + 0.035 * s and p.z < hi["ez"] + 0.02 * s:      # never hang in front of the cheek / ear
                p.y = hi["ey"] + 0.035 * s
            pts.append(p.copy())
        return pts, 0.0005 * s
    if style in ("ponytail", "braid"):
        tie = Vector((0, hi["back"] + 0.012 * s, ez + (0.035 if style == "ponytail" else -0.075) * s))
        # stage 1: combed over the scalp to the tie point
        n1 = 7
        for i in range(n1):
            u = (i + 1) / n1
            q = root.lerp(tie, u)
            loc, n2 = ctx.nearest(q)
            q = loc + n2 * (0.006 * s + 0.002 * s * u)
            pts.append(q.copy())
        p = pts[-1]
        if style == "ponytail":
            L = rnd.uniform(0.22, 0.30) * s; seg = 12
            spread = Vector((rnd.uniform(-1, 1), rnd.uniform(0, 1), 0)) * 0.012 * s
            d = Vector((0, 0.45, -0.2)).normalized()
            for i in range(seg):
                u = (i + 1) / seg
                p = p + d * (L / seg) + spread * (0.35 / seg) * (1 + u)
                p = collide(ctx, p, 0.012 * s)
                d = (d + Vector((0, -0.01, -0.35))).normalized()
                pts.append(p.copy())
            return pts, 0.00048 * s
        # braid: three interleaved bundles
        b = rnd.randrange(3); off = Vector((rnd.gauss(0, 1), rnd.gauss(0, 1), 0)) * 0.004 * s
        L = 0.30 * s; seg = 22
        for i in range(seg):
            u = (i + 1) / seg
            t = u * 6.0 * math.pi + b * 2 * math.pi / 3
            w = 0.016 * s * (1 - 0.45 * u)
            q = tie + Vector((math.sin(t) * w, 0.012 * s + math.sin(2 * t) * w * 0.45, -L * u)) + off * (1 - 0.5 * u)
            q = collide(ctx, q, 0.012 * s)
            pts.append(q)
        return pts, 0.00048 * s
    raise KeyError(style)


def sway_group():
    g = bpy.data.node_groups.get("PL_HairSway")
    if g:
        return g
    g = bpy.data.node_groups.new("PL_HairSway", "GeometryNodeTree")
    it = g.interface
    it.new_socket("Geometry", in_out="INPUT", socket_type="NodeSocketGeometry")
    it.new_socket("Sway", in_out="INPUT", socket_type="NodeSocketVector")
    it.new_socket("Pivot", in_out="INPUT", socket_type="NodeSocketFloat")
    it.new_socket("Length", in_out="INPUT", socket_type="NodeSocketFloat")
    it.new_socket("Geometry", in_out="OUTPUT", socket_type="NodeSocketGeometry")
    n = g.nodes; L = g.links.new
    gi = n.new("NodeGroupInput"); go = n.new("NodeGroupOutput")
    pos = n.new("GeometryNodeInputPosition"); sep = n.new("ShaderNodeSeparateXYZ"); L(pos.outputs[0], sep.inputs[0])
    sub = n.new("ShaderNodeMath"); sub.operation = "SUBTRACT"; L(gi.outputs["Pivot"], sub.inputs[0]); L(sep.outputs["Z"], sub.inputs[1])
    div = n.new("ShaderNodeMath"); div.operation = "DIVIDE"; L(sub.outputs[0], div.inputs[0]); L(gi.outputs["Length"], div.inputs[1])
    cl = n.new("ShaderNodeClamp"); L(div.outputs[0], cl.inputs[0])
    pw = n.new("ShaderNodeMath"); pw.operation = "POWER"; pw.inputs[1].default_value = 1.5; L(cl.outputs[0], pw.inputs[0])
    sc = n.new("ShaderNodeVectorMath"); sc.operation = "SCALE"; L(gi.outputs["Sway"], sc.inputs[0]); L(pw.outputs[0], sc.inputs["Scale"])
    sp = n.new("GeometryNodeSetPosition"); L(gi.outputs["Geometry"], sp.inputs["Geometry"]); L(sc.outputs[0], sp.inputs["Offset"])
    L(sp.outputs[0], go.inputs[0])
    return g


def add_sway(o, pivot, length):
    m = o.modifiers.new("Sway", "NODES"); m.node_group = sway_group()
    ids = {i.name: i.identifier for i in m.node_group.interface.items_tree if getattr(i, "in_out", "") == "INPUT"}
    m[ids["Pivot"]] = float(pivot); m[ids["Length"]] = float(length)
    o["sway_id"] = ids["Sway"]


def set_sway(objs, v):
    for o in objs:
        m = o.modifiers.get("Sway") if hasattr(o, "modifiers") else None
        if m:
            m[o["sway_id"]] = tuple(float(x) for x in v)
            o.update_tag()


COUNTS = dict(crop=9000, side_part=8000, shoulder_wavy=7000, long_straight=7000, ponytail=7000, braid=6000)


def build_hair(ctx, style, seed=11):
    rnd = random.Random(seed + STYLES.index(style) * 101 + (0 if ctx.kind == "male" else 7))
    hi = head_info(ctx)
    faces, ok = scalp_faces(ctx, hi, style)
    roots = sample_roots(faces, COUNTS[style], rnd)
    strands = []
    for p, n in roots:
        pts, r = strand(ctx, hi, style, p + n * 0.0015, n, rnd)
        strands.append((pts, r))
    # clumping: pull each strand's tip half toward its nearest guide (gives readable locks instead of fuzz)
    guides = strands[::40]
    gl = len(guides)
    if style not in ("crop",):
        import mathutils.kdtree as KD
        kd = KD.KDTree(gl)
        for i, (pts, r) in enumerate(guides):
            kd.insert(pts[0], i)
        kd.balance()
        new = []
        glen = [rnd.uniform(0.82, 1.08) for _ in guides]
        for pts, r in strands:
            _, gi, _ = kd.find(pts[0])
            gp = guides[gi][0]
            if len(gp) == len(pts):
                k = (0.72 if style in ("long_straight", "shoulder_wavy") else 0.6) if style != "braid" else 0.3
                pts = [p.lerp(q + (pts[0] - gp[0]) * (1 - i / len(pts)), k * (i / (len(pts) - 1)) ** 1.2) for i, (p, q) in enumerate(zip(pts, gp))]
                if style in ("long_straight", "shoulder_wavy", "ponytail"):
                    f = glen[gi]
                    if f < 1.0:              # shorter clump: shrink toward the root (staggered, layered tips)
                        n0 = len(pts); keep = max(3, int(n0 * f + 0.5))
                        pts = pts[:keep]
            new.append((pts, r))
        strands = new
    if style != "crop":
        fly = []
        for pts, r in strands[::33]:          # ~3% flyaways: loose strands lifting off the mass
            off = Vector((rnd.uniform(-1, 1), rnd.uniform(0.1, 1), rnd.uniform(-0.2, 0.4))) * 0.018 * ctx.s
            n0 = len(pts)
            fly.append(([p + off * ((i / max(1, n0 - 1)) ** 1.6) + Vector((rnd.gauss(0, 1), rnd.gauss(0, 1), rnd.gauss(0, 1))) * 0.0012 * ctx.s * (i / n0)
                         for i, p in enumerate(pts)], r * 0.7))
        strands += fly
    # hairline feathering: strands rooted near the front hairline get thinner + shorter (no hard helmet edge)
    hl = hi["ez"] + 0.045 * ctx.s
    fe = []
    for pts, r in strands:
        dz = pts[0].z - hl
        if pts[0].y < hi["c"].y and 0 <= dz < 0.012 * ctx.s:
            u = dz / (0.012 * ctx.s)
            if rnd.random() > 0.35 + 0.65 * u:
                continue
            r *= 0.55 + 0.45 * u
        fe.append((pts, r))
    strands = fe
    sizes = [len(p) for p, _ in strands]
    hc = bpy.data.hair_curves.new(f"hair_{style}")
    hc.add_curves(sizes)
    flat = np.array([c for pts, _ in strands for p in pts for c in p], dtype=np.float32)
    hc.position_data.foreach_set("vector", flat)
    rad = []
    for pts, r in strands:
        n = len(pts)
        rad += [r * (1.0 - 0.75 * (i / max(1, n - 1)) ** 1.5) for i in range(n)]
    ra = hc.attributes.new("radius", "FLOAT", "POINT"); ra.data.foreach_set("value", np.array(rad, dtype=np.float32))
    mat = M.hair_grey("PL_HairGrey")
    hc.materials.append(mat)
    o = bpy.data.objects.new(f"hair_{style}_{ctx.kind}", hc); ctx.col.objects.link(o)
    G.rigid(ctx, o, "head")
    if style not in ("crop", "side_part"):
        zs_ = [p.z for pts, _ in strands for p in pts]
        if style == "ponytail":
            piv = hi["ez"] + 0.035 * ctx.s
        elif style == "braid":
            piv = hi["ez"] - 0.075 * ctx.s
        else:
            piv = hi["ez"] + 0.01 * ctx.s
        add_sway(o, piv, max(0.05 * ctx.s, piv - min(zs_)))
    # scalp cap so skin never shows through partings
    cap = G.shell(ctx, f"scalp_{style}", lambda v: ok(v.co) and not ctx.mask[v.index], M.scalp_grey("PL_Scalp", 0.36),
                  offset=0.0025, thick=0.0, subsurf=1)
    if style in ("ponytail", "braid"):
        tie = Vector((0, hi["back"] + 0.012 * ctx.s, hi["ez"] + (0.035 if style == "ponytail" else -0.075) * ctx.s))
        tmat = M.cloth("PL_HairTie", (0.30, 0.12, 0.08), "leather")
        t = bpy.data.objects.new("x", None)
        import fv_common as C
        tt = C.torus(f"hair_tie_{style}", 0.014 * ctx.s, 0.005 * ctx.s, tie + Vector((0, 0.006, -0.01)), mat=tmat, col=ctx.col,
                     rot=(math.radians(70), 0, 0))
        G.rigid(ctx, tt, "head")
        if style == "braid":
            end = tie + Vector((0, 0.012 * ctx.s, -0.30 * ctx.s))
            te = C.torus(f"braid_tie_{style}", 0.009 * ctx.s, 0.004 * ctx.s, end, mat=tmat, col=ctx.col)
            G.rigid(ctx, te, "head")
        bpy.data.objects.remove(t)
    return o
