"""Materials + armour/weapon/shield part builders for the HD knights."""
import bpy, bmesh, math, random
from collections import defaultdict
from mathutils import Vector, Matrix
import fv_common as C
import fv_npc_helpers as H
from kn_rig import WMODE, sm, cen


# ------------------------------------------------------------------ materials
def _mix(nt, fac, a, b):
    m = nt.nodes.new("ShaderNodeMix"); m.data_type = "RGBA"
    for sock, val in ((6, a), (7, b)):
        if isinstance(val, tuple):
            m.inputs[sock].default_value = (*val[:3], 1)
        else:
            nt.links.new(val, m.inputs[sock])
    if isinstance(fac, float):
        m.inputs[0].default_value = fac
    else:
        nt.links.new(fac, m.inputs[0])
    return m.outputs[2]


def _mixf(nt, fac, a, b):
    m = nt.nodes.new("ShaderNodeMix"); m.data_type = "FLOAT"
    for sock, val in ((2, a), (3, b)):
        if isinstance(val, (int, float)):
            m.inputs[sock].default_value = val
        else:
            nt.links.new(val, m.inputs[sock])
    nt.links.new(fac, m.inputs[0])
    return m.outputs[0]


def _mr(nt, x, a, b, c=0.0, d=1.0):
    m = nt.nodes.new("ShaderNodeMapRange")
    m.inputs[1].default_value = a; m.inputs[2].default_value = b; m.inputs[3].default_value = c; m.inputs[4].default_value = d
    nt.links.new(x, m.inputs[0]); return m.outputs[0]


def _math(nt, op, a, b):
    m = nt.nodes.new("ShaderNodeMath"); m.operation = op
    for k, v in enumerate((a, b)):
        if isinstance(v, (int, float)):
            m.inputs[k].default_value = v
        else:
            nt.links.new(v, m.inputs[k])
    return m.outputs[0]


def _noise(nt, vec, scale, detail=6, rough=0.55):
    n = nt.nodes.new("ShaderNodeTexNoise"); n.inputs["Scale"].default_value = scale; n.inputs["Detail"].default_value = detail
    n.inputs["Roughness"].default_value = rough; nt.links.new(vec, n.inputs[0]); return n.outputs["Fac"]


def armor_mat(name, base, dark, hi, metal=1.0, rough=0.28, wear=0.6, rust=0.0, moss=0.0, lava=None, lava_k=0.0,
              coat=0.25, scale=14.0, verdigris=False):
    m, nt = C.node_mat(name)
    if nt is None:
        return m
    N = nt.nodes; b = N["Principled BSDF"]
    tc = N.new("ShaderNodeTexCoord"); geo = N.new("ShaderNodeNewGeometry")
    vec = tc.outputs["Object"]
    n1 = _noise(nt, vec, scale, 8)
    ramp = N.new("ShaderNodeValToRGB")
    ramp.color_ramp.elements[0].position = 0.3; ramp.color_ramp.elements[0].color = (*dark, 1)
    ramp.color_ramp.elements[1].position = 0.74; ramp.color_ramp.elements[1].color = (*hi, 1)
    e = ramp.color_ramp.elements.new(0.52); e.color = (*base, 1)
    nt.links.new(n1, ramp.inputs[0])
    col = ramp.outputs[0]
    edge = _mr(nt, geo.outputs["Pointiness"], 0.5, 0.57)
    edge = _math(nt, "MULTIPLY", edge, wear)
    col = _mix(nt, edge, col, tuple(min(1.0, c * 1.25 + 0.06) for c in hi))
    # brushed scratches
    mp = N.new("ShaderNodeMapping"); mp.inputs["Scale"].default_value = (90, 90, 6); nt.links.new(vec, mp.inputs[0])
    sc = _noise(nt, mp.outputs[0], 1.0, 4)
    rgh = _math(nt, "ADD", _math(nt, "MULTIPLY", _math(nt, "SUBTRACT", sc, 0.5), 0.22), rough)
    rgh = _mixf(nt, edge, rgh, max(0.05, rough - 0.12))
    met = metal
    met_s = None
    if rust > 0:
        nr = _noise(nt, vec, 4.5, 12, 0.68)
        t0 = 0.66 - 0.2 * rust
        rf = _mr(nt, nr, t0 - 0.05, t0 + 0.05)
        rr = N.new("ShaderNodeValToRGB")
        if verdigris:
            rr.color_ramp.elements[0].color = (0.10, 0.22, 0.17, 1); rr.color_ramp.elements[1].color = (0.30, 0.48, 0.38, 1)
        else:
            rr.color_ramp.elements[0].color = (0.07, 0.035, 0.02, 1); rr.color_ramp.elements[1].color = (0.26, 0.12, 0.05, 1)
        nt.links.new(_noise(nt, vec, 30, 6), rr.inputs[0])
        col = _mix(nt, rf, col, rr.outputs[0])
        rgh = _mixf(nt, rf, rgh, 0.85)
        met_s = _mixf(nt, rf, metal, 0.15)
    if moss > 0:
        sep = N.new("ShaderNodeSeparateXYZ"); nt.links.new(geo.outputs["Normal"], sep.inputs[0])
        up = _mr(nt, sep.outputs["Z"], 0.15, 0.8)
        nm = _noise(nt, vec, 7, 10, 0.7)
        mf = _math(nt, "MULTIPLY", up, _mr(nt, nm, 0.62 - 0.25 * moss, 0.70 - 0.25 * moss))
        col = _mix(nt, mf, col, (0.13, 0.22, 0.06))
        rgh = _mixf(nt, mf, rgh, 0.92)
        met_s = _mixf(nt, mf, met_s if met_s is not None else metal, 0.0)
    nt.links.new(col, b.inputs["Base Color"])
    nt.links.new(rgh, b.inputs["Roughness"])
    if met_s is not None:
        nt.links.new(met_s, b.inputs["Metallic"])
    else:
        b.inputs["Metallic"].default_value = met
    b.inputs["Coat Weight"].default_value = coat
    b.inputs["Coat Roughness"].default_value = 0.15
    hgt = _math(nt, "MULTIPLY", n1, 1.0)
    if lava:
        dist = N.new("ShaderNodeVectorMath"); dist.operation = "ADD"
        nt.links.new(vec, dist.inputs[0])
        nn = N.new("ShaderNodeTexNoise"); nn.inputs["Scale"].default_value = 6; nn.inputs["Detail"].default_value = 3
        nt.links.new(vec, nn.inputs[0]); nt.links.new(nn.outputs["Color"], dist.inputs[1])
        vo = N.new("ShaderNodeTexVoronoi"); vo.feature = "DISTANCE_TO_EDGE"; vo.inputs["Scale"].default_value = 6.0
        nt.links.new(dist.outputs[0], vo.inputs[0])
        crack = _mr(nt, vo.outputs["Distance"], 0.0, 0.011, 1.0, 0.0)
        crack = _math(nt, "POWER", crack, 1.6)
        hot = _mr(nt, _noise(nt, vec, 2.5, 3), 0.5, 0.62, 0.0, 1.0)
        em = _math(nt, "MULTIPLY", crack, hot)
        nt.links.new(_math(nt, "MULTIPLY", em, lava_k), b.inputs["Emission Strength"])
        b.inputs["Emission Color"].default_value = (*lava, 1)
        hgt = _math(nt, "SUBTRACT", hgt, _math(nt, "MULTIPLY", crack, 0.6))
    bump = N.new("ShaderNodeBump"); bump.inputs["Strength"].default_value = 0.14; bump.inputs["Distance"].default_value = 0.01
    nt.links.new(hgt, bump.inputs["Height"]); nt.links.new(bump.outputs[0], b.inputs["Normal"])
    return m


def mail_mat(name, c=(0.32, 0.33, 0.35), rust=0.0):
    m, nt = C.node_mat(name)
    if nt is None:
        return m
    N = nt.nodes; b = N["Principled BSDF"]
    tc = N.new("ShaderNodeTexCoord")
    vo = N.new("ShaderNodeTexVoronoi"); vo.inputs["Scale"].default_value = 230; vo.feature = "F1"
    nt.links.new(tc.outputs["Object"], vo.inputs[0])
    ring = _mr(nt, vo.outputs["Distance"], 0.15, 0.45, 1.0, 0.0)
    col = _mix(nt, ring, (c[0] * 0.25, c[1] * 0.25, c[2] * 0.25), c)
    if rust:
        rf = _mr(nt, _noise(nt, tc.outputs["Object"], 5, 10), 0.6 - 0.25 * rust, 0.66 - 0.25 * rust)
        col = _mix(nt, rf, col, (0.16, 0.08, 0.035))
    nt.links.new(col, b.inputs["Base Color"])
    b.inputs["Metallic"].default_value = 0.9; b.inputs["Roughness"].default_value = 0.4
    bump = N.new("ShaderNodeBump"); bump.inputs["Strength"].default_value = 0.6; bump.inputs["Distance"].default_value = 0.004
    nt.links.new(ring, bump.inputs["Height"]); nt.links.new(bump.outputs[0], b.inputs["Normal"])
    return m


def leather_mat(name, c=(0.16, 0.08, 0.04)):
    m, nt = C.node_mat(name)
    if nt is None:
        return m
    N = nt.nodes; b = N["Principled BSDF"]; tc = N.new("ShaderNodeTexCoord")
    n1 = _noise(nt, tc.outputs["Object"], 60, 6)
    col = _mix(nt, n1, tuple(x * 0.6 for x in c), tuple(min(1, x * 1.4) for x in c))
    nt.links.new(col, b.inputs["Base Color"]); b.inputs["Roughness"].default_value = 0.55
    b.inputs["Coat Weight"].default_value = 0.15
    bump = N.new("ShaderNodeBump"); bump.inputs["Strength"].default_value = 0.25
    nt.links.new(n1, bump.inputs["Height"]); nt.links.new(bump.outputs[0], b.inputs["Normal"])
    return m


def cloth_mat(name, top, bot, sheen=0.6, rough=0.6, z0=0.2, z1=1.5, dirt=0.0):
    return H.fabric_mat(name, top, bot, sheen=sheen, rough=rough, z0=z0, z1=z1)


def glow(name, c, k=6.0):
    return C.glow_mat(name, c, k)


def ghost_mat(name, c, k=3.0, alpha=0.45):
    m, nt = C.node_mat(name)
    if nt is None:
        return m
    N = nt.nodes; out = N["Material Output"]; b = N["Principled BSDF"]
    em = N.new("ShaderNodeEmission"); em.inputs[0].default_value = (*c, 1); em.inputs[1].default_value = k
    tr = N.new("ShaderNodeBsdfTransparent"); mix = N.new("ShaderNodeMixShader"); mix.inputs[0].default_value = alpha
    nt.links.new(tr.outputs[0], mix.inputs[1]); nt.links.new(em.outputs[0], mix.inputs[2]); nt.links.new(mix.outputs[0], out.inputs["Surface"])
    m.blend_method = "BLEND" if hasattr(m, "blend_method") else None
    return m


# ------------------------------------------------------------------ edge rolls + rivets
def boundary_loops(me, min_pts=10):
    bm = bmesh.new(); bm.from_mesh(me); bm.normal_update(); bm.verts.ensure_lookup_table()
    adj = defaultdict(list)
    for e in bm.edges:
        if e.is_boundary:
            a, b = e.verts; adj[a.index].append(b.index); adj[b.index].append(a.index)
    seen = set(); loops = []
    for st in list(adj):
        if st in seen:
            continue
        loop = [st]; seen.add(st); prev = None; cur = st
        while True:
            nxt = [n for n in adj[cur] if n != prev and n not in seen]
            if not nxt:
                break
            prev, cur = cur, nxt[0]; loop.append(cur); seen.add(cur)
        cyc = st in adj[loop[-1]] and len(loop) > 2
        if len(loop) >= min_pts:
            loops.append(([(bm.verts[i].co.copy(), bm.verts[i].normal.copy()) for i in loop], cyc))
    bm.free()
    return loops


def _smooth(pts, cyc, it=2):
    for _ in range(it):
        n = len(pts); out = []
        for i in range(n):
            if not cyc and (i == 0 or i == n - 1):
                out.append(pts[i]); continue
            out.append((pts[(i - 1) % n] + pts[i] * 2 + pts[(i + 1) % n]) / 4)
        pts = out
    return pts


def rivet_mesh(name, pts, r, mat, col, squash=0.6):
    bm = bmesh.new()
    for p, n in pts:
        ret = bmesh.ops.create_icosphere(bm, subdivisions=1, radius=r)
        q = n.to_track_quat("Z", "Y").to_matrix().to_4x4()
        M = Matrix.Translation(p) @ q @ Matrix.Diagonal((1, 1, squash, 1))
        bmesh.ops.transform(bm, matrix=M, verts=ret["verts"])
    o = C.obj_from_bm(bm, name, mat, col)
    return o


def _runs(loop, cyc, zmax):
    keep = [p.z < zmax for p, n in loop]
    if all(keep):
        return [(loop, cyc)]
    if cyc:
        st = keep.index(False); loop = loop[st:] + loop[:st]; keep = keep[st:] + keep[:st]
    runs = []; cur = []
    for it, k in zip(loop, keep):
        if k:
            cur.append(it)
        elif cur:
            runs.append((cur, False)); cur = []
    if cur:
        runs.append((cur, False))
    return runs


def edge_roll(shell, r, mat, col, thick=0.0, rivets=None, rivet_every=5, rivet_r=0.0055, inset=0.012, step=2, min_pts=10, zmin=None, zmax=None):
    """Rolled metal edge along every open border of a shell (+ optional rivet line just inside it)."""
    out = []; rv = []
    loops = boundary_loops(shell.data, min_pts)
    if zmax is not None:
        loops = [r_ for L in loops for r_ in _runs(L[0], L[1], zmax)]
    for k, (loop, cyc) in enumerate(loops):
        pts = [p + n * (thick * 0.6) for p, n in loop[::step]]
        nrm = [n for p, n in loop[::step]]
        if len(pts) < 4:
            continue
        pts = _smooth(pts, cyc, 2)
        if zmin is not None and max(p.z for p in pts) < zmin:
            continue
        cpts = pts + ([pts[0]] if cyc else [])
        o = C.tube_curve(f"{shell.name}_edge{k}", cpts, radius=r, mat=mat, col=col, res=3, bevel_res=2)
        if cyc:
            o.data.splines[0].use_cyclic_u = True
        out.append(o)
        if rivets is not None:
            c = cen(pts)
            for i in range(0, len(pts), rivet_every):
                p = pts[i]; n = nrm[i]
                tang = (pts[(i + 1) % len(pts)] - pts[i - 1]).normalized()
                inward = n.cross(tang).normalized()
                if inward.dot(c - p) < 0 and abs((c - p).z) < 0.001:
                    pass
                cand = p + inward * inset
                if (cand - c).length > (p - c).length:
                    cand = p - inward * inset
                rv.append((cand + n * (thick * 0.4 + 0.002), n))
    if rivets is not None and rv:
        out.append(rivet_mesh(f"{shell.name}_rivets", rv, rivet_r, rivets, col))
    return out


def shell(ctx, name, pred, off, thick, mat, col, smooth=0, sub=1, trim=None, edge_r=0.0045, rivets=None, rivet_every=5,
          min_pts=10, step=2):
    body = ctx["body"]
    o = H.extract(body, name, pred, offset=off, thick=thick, mat=mat, col=col, subsurf=sub)
    if smooth:
        sm_ = o.modifiers.new("Smooth", "LAPLACIANSMOOTH"); sm_.lambda_factor = 0.7; sm_.iterations = smooth
        sm_.use_volume_preserve = True; o.modifiers.move(len(o.modifiers) - 1, 0)
    if trim is not None and len(o.data.vertices):
        edge_roll(o, edge_r, trim, col, thick=thick, rivets=rivets, rivet_every=rivet_every, min_pts=min_pts, step=step)
    return o


# ------------------------------------------------------------------ limb rings (straps, cuffs)
def arm_ring(ctx, side, t, r_off, tube_r, mat, col, name, buckle=None):
    J = ctx["J"]; V = ctx["body"].data.vertices
    S, dn, L = J[f"armdir_{side}"]
    ids = [i for i, (tt, sd) in J["arm_t"].items() if sd == side and abs(tt - t) < 0.02]
    c = cen([V[i].co for i in ids]); rad = sum((V[i].co - c - dn * (V[i].co - c).dot(dn)).length for i in ids) / max(1, len(ids))
    u = dn.cross(Vector((0, 1, 0))).normalized(); w = dn.cross(u).normalized()
    pts = [c + (u * math.cos(a) + w * math.sin(a)) * (rad + r_off) for a in [2 * math.pi * k / 24 for k in range(25)]]
    o = C.tube_curve(name, pts, radius=tube_r, mat=mat, col=col, res=2, bevel_res=2); o.data.splines[0].use_cyclic_u = True
    if buckle is not None:
        fp = min(pts, key=lambda p: p.y)
        C.box(name + "_bk", (0.016, 0.006, 0.016), fp + Vector((0, -0.004, 0)), buckle, col, bevel=0.002)
    return o


def leg_ring(ctx, side, z, r_off, tube_r, mat, col, name, buckle=None, front_only=False):
    V = ctx["body"].data.vertices; mask = ctx["mask"]; sx = 1 if side == "L" else -1
    pts0 = [V[i].co for i in range(len(V)) if not mask[i] and V[i].co.x * sx > 0.004 and abs(V[i].co.z - z) < 0.006]
    c = cen(pts0)
    rx = max(abs(p.x - c.x) for p in pts0) + r_off; ry = max(abs(p.y - c.y) for p in pts0) + r_off
    o = H.ring_curve(name, c.x, c.y, rx, ry, z, tube_r, mat, col, n=32)
    if buckle is not None:
        C.box(name + "_bk", (0.016, 0.006, 0.016), (c.x + sx * rx * 0.7, c.y - ry * 0.7, z), buckle, col, bevel=0.002)
    return o


# ------------------------------------------------------------------ cloth
def cape(ctx, name, mat, col, z_neck, z_hem, length_y=0.2, folds=9, tatter=0.0, width=1.0, seed=1, trim=None, holes=0.0, clear=0.06):
    """Cape draped from the shoulder blades, following the back, then falling with a slight flare."""
    body, mask, s = ctx["body"], ctx["mask"], ctx["s"]
    V = body.data.vertices
    rnd = random.Random(seed)
    rings, segs = 34, 40
    zs = [z_neck + (z_hem - z_neck) * (i / rings) for i in range(rings + 1)]
    yb = []
    run = -1.0
    for z in zs:
        pts = [V[i].co.y for i in range(len(V)) if not mask[i] and abs(V[i].co.x) < 0.14 * s and abs(V[i].co.z - z) < 0.012]
        y = max(pts) if pts else run
        run = max(run, y); yb.append(run)
    hem = [1.0 - tatter * (0.15 + 0.85 * rnd.random()) * (0.4 + 0.6 * abs(math.sin(j * 1.7))) for j in range(segs + 1)]
    bm = bmesh.new(); grid = []
    for i in range(rings + 1):
        t = i / rings; row = []
        for j in range(segs + 1):
            u = -1 + 2 * j / segs
            tt = min(t, hem[j])
            k = int(round(tt * rings)); zc = z_neck + (z_hem - z_neck) * tt
            hw = (0.20 + 0.09 * tt) * s * width
            ph = (u + 1) * math.pi / 2
            fold = 0.024 * s * (0.65 * math.sin(folds * ph) + 0.35 * math.sin(folds * 1.73 * ph + 1.3)) * (0.25 + tt ** 0.7)
            y = yb[k] + clear * s + length_y * s * tt ** 2 + (1 - u * u) * 0.02 * s + abs(fold) - (u * u) * 0.05 * s * (1 - tt)
            x = u * hw + fold * 0.3
            row.append(bm.verts.new((x, y, zc)))
        grid.append(row)
    for i in range(rings):
        for j in range(segs):
            if holes and i > rings * 0.45 and rnd.random() < holes * (i / rings):
                continue
            if i / rings >= hem[j] or i / rings >= hem[j + 1]:
                continue
            bm.faces.new((grid[i][j], grid[i][j + 1], grid[i + 1][j + 1], grid[i + 1][j]))
    loose = [v for v in bm.verts if not v.link_faces]
    bmesh.ops.delete(bm, geom=loose, context="VERTS")
    o = C.obj_from_bm(bm, name, mat, col)
    so = o.modifiers.new("Sol", "SOLIDIFY"); so.thickness = 0.007 * s
    C.add_mod_subsurf(o, 1)
    WMODE[o.name] = ("bone", "cape")
    if trim is not None:
        for e in edge_roll(o, 0.005 * s, trim, col, thick=0.004, step=1, min_pts=6):
            WMODE[e.name] = ("bone", "cape")
    return o


def split_skirt(ctx, name, mat, col, z_top, z_bot, flare=0.06, gap_deg=7, tatter=0.0, seed=3, trim=None, folds=10, front=True):
    body, mask, s = ctx["body"], ctx["mask"], ctx["s"]
    rnd = random.Random(seed)
    objs = []
    for sd, a0, a1 in (("L", -90 + gap_deg, 90 - gap_deg), ("R", 90 + gap_deg, 270 - gap_deg)):
        segs, rings = 26, 22
        hem = [1.0 - tatter * rnd.random() * (0.5 + 0.5 * abs(math.sin(j * 2.3))) for j in range(segs + 1)]
        bm = bmesh.new(); grid = []
        for i in range(rings + 1):
            t = i / rings
            row = []
            for j in range(segs + 1):
                tt = t * hem[j]
                z = z_top + (z_bot - z_top) * tt
                zz = max(z, 0.55 * s)
                x0, x1, y0, y1 = H.section(body, zz, mask, tol=0.012)
                cx = (x0 + x1) / 2; cyy = (y0 + y1) / 2
                rx = (x1 - x0) / 2 + 0.03 * s + flare * s * tt; ry = (y1 - y0) / 2 + 0.035 * s + flare * s * tt * 0.8
                a = math.radians(a0 + (a1 - a0) * j / segs)
                f = 1 + 0.06 * math.sin(folds * a) * tt
                row.append(bm.verts.new((cx + rx * f * math.cos(a), cyy + ry * f * math.sin(a), z)))
            grid.append(row)
        for i in range(rings):
            for j in range(segs):
                bm.faces.new((grid[i][j], grid[i][j + 1], grid[i + 1][j + 1], grid[i + 1][j]))
        o = C.obj_from_bm(bm, f"{name}_{sd}", mat, col)
        so = o.modifiers.new("Sol", "SOLIDIFY"); so.thickness = 0.006 * s
        C.add_mod_subsurf(o, 1)
        WMODE[o.name] = ("skirt", sd, z_top, z_bot)
        if trim is not None:
            for e in edge_roll(o, 0.005 * s, trim, col, thick=0.004, step=1, min_pts=4, zmax=z_top - 0.6 * (z_top - z_bot)):
                WMODE[e.name] = ("skirt", sd, z_top, z_bot)
        objs.append(o)
    return objs


# ------------------------------------------------------------------ helm helpers
def head_info(ctx):
    V = ctx["body"].data.vertices; ez = ctx["face"]["eye_z"]; s = ctx["s"]
    pts = [v.co for v in V if v.co.z > ez - 0.04 * s]
    c = cen(pts)
    rx = max(abs(p.x) for p in pts); y0 = min(p.y for p in pts); y1 = max(p.y for p in pts)
    return {"cy": (y0 + y1) / 2, "rx": rx, "ry": (y1 - y0) / 2, "top": max(p.z for p in pts), "ez": ez, "y0": y0}


def helm_shell(name, hi, prof, mat, col, segs=56, thick=0.006, extra_y=1.0):
    """prof: [(r_factor, z)] r in units of head rx+margin; ellipse ratio from head."""
    R = hi["rx"] + 0.028; ry = (hi["ry"] + 0.03) * extra_y
    o = C.lathe(name, [(R * f, z) for f, z in prof], segs=segs, mat=mat, col=col, close_top=True)
    o.scale = (1.0, ry / R, 1.0); o.location = (0, hi["cy"] + 0.01, 0)
    so = o.modifiers.new("Sol", "SOLIDIFY"); so.thickness = thick
    C.add_mod_subsurf(o, 1)
    WMODE[o.name] = ("bone", "head")
    return o, R, ry


def front_y(hi, R, ry, x, z_scale=1.0):
    q = max(0.0, 1 - (x / R) ** 2)
    return hi["cy"] + 0.01 - ry * math.sqrt(q)


def headbone(*objs):
    for o in objs:
        if o is not None:
            WMODE[o.name] = ("bone", "head")
    return objs[0] if objs else None


# ------------------------------------------------------------------ weapons
def blade_mesh(name, L, w0, th, mat, col, profile="long", seed=1, edge_mat=None):
    rnd = random.Random(seed)
    n = 34; bm = bmesh.new(); rows = []
    for k in range(n + 1):
        t = k / n; z = 0.03 + L * t
        if profile == "long":
            w = w0 * (1 - 0.35 * t) if t < 0.88 else w0 * 0.65 * (1 - (t - 0.88) / 0.12)
        elif profile == "falchion":
            w = w0 * (0.8 + 0.5 * t) if t < 0.8 else w0 * 1.2 * (1 - (t - 0.8) / 0.2) ** 0.7
        elif profile == "jagged":
            base = w0 * (1 - 0.3 * t) if t < 0.85 else w0 * 0.7 * (1 - (t - 0.85) / 0.15)
            w = base * (1.0 + (0.28 if (k % 3 == 1 and 0.15 < t < 0.85) else 0.0))
        elif profile == "notched":
            w = w0 * (1 - 0.3 * t) if t < 0.86 else w0 * 0.7 * (1 - (t - 0.86) / 0.14)
            if 0.15 < t < 0.85 and rnd.random() < 0.25:
                w *= 0.72
        else:
            w = w0 * (1 - 0.2 * t) if t < 0.82 else w0 * 0.8 * (1 - (t - 0.82) / 0.18)
        w = max(w, 0.0015); tt = th * max(0.25, w / w0)
        fu = 0.55 if t < 0.7 else 1.0  # fuller groove on the lower blade
        sec = [(w, 0), (0.72 * w, tt * 0.62), (0.28 * w, tt), (0, tt * fu), (-0.28 * w, tt), (-0.72 * w, tt * 0.62),
               (-w, 0), (-0.72 * w, -tt * 0.62), (-0.28 * w, -tt), (0, -tt * fu), (0.28 * w, -tt), (0.72 * w, -tt * 0.62)]
        rows.append([bm.verts.new((x, y, z)) for x, y in sec])
    NS = 12
    for a, b in zip(rows[:-1], rows[1:]):
        for i in range(NS):
            j = (i + 1) % NS
            bm.faces.new((a[i], a[j], b[j], b[i]))
    bm.faces.new(list(reversed(rows[0])))
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=1e-5)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    o = C.obj_from_bm(bm, name, mat, col, smooth=False)
    return o


def sword(name, col, L=0.85, w0=0.03, th=0.007, blade=None, guard=None, grip=None, pommel=None, rune=None,
          profile="long", guard_w=0.13, seed=1, guard_style="bar"):
    parts = []
    parts.append(blade_mesh(name + "_blade", L, w0, th, blade, col, profile, seed))
    if rune is not None:
        for sgn in (1, -1):
            parts.append(C.tube_curve(f"{name}_rune{sgn}", [Vector((0, sgn * th * 0.9, 0.08)), Vector((0, sgn * th * 0.75, 0.03 + L * 0.72))],
                                      radius=0.0028, mat=rune, col=col, res=2, bevel_res=1))
    if guard_style == "bar":
        g = C.box(name + "_guard", (guard_w, 0.024, 0.02), (0, 0, 0.02), guard, col, bevel=0.005); parts.append(g)
        for sgn in (1, -1):
            parts.append(C.ico(f"{name}_gq{sgn}", 0.013, (sgn * guard_w / 2, 0, 0.02), sub=2, mat=guard, col=col))
    elif guard_style == "wing":
        for sgn in (1, -1):
            parts.append(C.tube_curve(f"{name}_gw{sgn}", [Vector((0, 0, 0.02)), Vector((sgn * guard_w * 0.35, 0, 0.03)),
                                                           Vector((sgn * guard_w * 0.55, 0, 0.08))], radius=0.012, mat=guard, col=col, radii=[1, 0.8, 0.25]))
        parts.append(C.ico(name + "_gem", 0.014, (0, -0.012, 0.025), sub=2, mat=rune or guard, col=col))
    elif guard_style == "spike":
        for sgn in (1, -1):
            c = C.cyl(f"{name}_gs{sgn}", 0.016, guard_w * 0.55, (sgn * guard_w * 0.27, 0, 0.02), segs=8, mat=guard, col=col, r2=0.002)
            c.rotation_euler = (0, sgn * math.radians(-75), 0); parts.append(c)
        parts.append(C.box(name + "_gc", (0.05, 0.03, 0.03), (0, 0, 0.02), guard, col, bevel=0.006))
    parts.append(C.cyl(name + "_grip", 0.0145, 0.15, (0, 0, -0.065), segs=12, mat=grip, col=col))
    for k in range(5):
        parts.append(C.torus(f"{name}_wrap{k}", 0.0155, 0.0028, (0, 0, -0.13 + k * 0.03), mat=grip, col=col, segs=16, rsegs=6))
    parts.append(C.lathe(name + "_pommel", [(0.001, -0.175), (0.022, -0.165), (0.026, -0.152), (0.018, -0.14), (0.01, -0.135)],
                         segs=16, mat=pommel or guard, col=col, close_bottom=True))
    return parts


def place(parts, M):
    bpy.context.view_layer.update()
    for p in parts:
        p.matrix_world = M @ p.matrix_world


def heater_shield(name, col, W=0.27, Hh=0.42, curv=0.05, field=None, rim=None, emblem_fn=None, rivet=None, thick=0.018,
                  battered=0.0, seed=2, shape="heater"):
    """Shield built in local XZ (front faces -Y), centre at origin."""
    rnd = random.Random(seed)
    bm = bmesh.new(); rows = []; NZ = 18; NX = 16
    for i in range(NZ + 1):
        t = i / NZ; z = Hh / 2 - Hh * t
        if shape == "heater":
            w = W / 2 if t < 0.45 else W / 2 * math.cos((t - 0.45) / 0.55 * math.pi / 2) ** 0.85
        elif shape == "tower":
            w = W / 2 * (0.92 + 0.08 * math.sin(t * math.pi)) if t < 0.82 else W / 2 * (1 - (t - 0.82) / 0.18 * 0.85)
        else:
            w = W / 2
        w = max(w, 0.006)
        row = []
        for j in range(NX + 1):
            u = -1 + 2 * j / NX; x = u * w
            y = -curv * (1 - u * u)
            if shape == "tower" and t < 0.06:
                z2 = z + 0.03 * (1 - u * u)
            else:
                z2 = z
            if battered:
                y += (rnd.random() - 0.5) * battered * 0.01
            row.append(bm.verts.new((x, y, z2)))
        rows.append(row)
    for a, b in zip(rows[:-1], rows[1:]):
        for j in range(NX):
            bm.faces.new((a[j], a[j + 1], b[j + 1], b[j]))
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=1e-4)
    o = C.obj_from_bm(bm, name, field, col)
    so = o.modifiers.new("Sol", "SOLIDIFY"); so.thickness = thick; so.offset = 1.0
    C.add_mod_subsurf(o, 1)
    parts = [o]
    parts += edge_roll(o, 0.011, rim, col, thick=0.0, rivets=rivet, rivet_every=3, inset=0.024, step=1, min_pts=6)
    if emblem_fn:
        parts += emblem_fn(-curv - 0.004)
    # back strap/handle
    parts.append(C.box(name + "_strap", (0.05, 0.02, 0.16), (0, thick + 0.015, 0.0), rim, col, bevel=0.004))
    return parts


def round_shield(name, col, R=0.24, wood=None, rim=None, boss=None, rivet=None, broken=True, seed=5):
    rnd = random.Random(seed)
    bm = bmesh.new(); NA = 48; NR = 8
    gap = (math.radians(20), math.radians(70)) if broken else None
    grid = []
    for i in range(NR + 1):
        r = R * i / NR; row = []
        for j in range(NA + 1):
            a = 2 * math.pi * j / NA
            rr = r
            if gap and gap[0] < a < gap[1] and i > NR * 0.5:
                rr = min(r, R * (0.5 + 0.12 * rnd.random()))
            row.append(bm.verts.new((rr * math.cos(a), -0.03 * (1 - (r / R) ** 2), rr * math.sin(a))))
        grid.append(row)
    for i in range(NR):
        for j in range(NA):
            try:
                bm.faces.new((grid[i][j], grid[i][j + 1], grid[i + 1][j + 1], grid[i + 1][j]))
            except ValueError:
                pass
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=1e-4)
    o = C.obj_from_bm(bm, name, wood, col)
    so = o.modifiers.new("Sol", "SOLIDIFY"); so.thickness = 0.02; so.offset = 1.0
    parts = [o]
    parts += edge_roll(o, 0.01, rim, col, rivets=rivet, rivet_every=3, inset=0.02, step=1, min_pts=6)
    b = C.uvsphere(name + "_boss", 0.06, (0, -0.03, 0), mat=boss, col=col, scale=(1, 0.55, 1)); parts.append(b)
    parts.append(C.torus(name + "_bossrim", 0.065, 0.008, (0, -0.03, 0), mat=boss, col=col, rot=(math.pi / 2, 0, 0)))
    for k in range(6):
        x = -R + (k + 0.5) * 2 * R / 6
        parts.append(C.box(f"{name}_plank{k}", (0.004, 0.004, 2 * math.sqrt(max(0.0, R * R - x * x)) * 0.92), (x, -0.032 * (1 - (x / R) ** 2) - 0.002, 0),
                           C.principled("KN_PlankLine", (0.05, 0.03, 0.02), rough=0.9), col))
    return parts
