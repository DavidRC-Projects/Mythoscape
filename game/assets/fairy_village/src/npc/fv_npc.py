"""Fairy Village NPCs built on the CC0 Blender Human Base Meshes (stylized). One NPC per Blender process.

  blender -b -P fv_npc.py -- --key elowen_moonwhisper --mode hero|portrait|sprites|all [--preview] [--facings s,e,n,w] [--frames 8]
"""
import bpy, bmesh, math, os, random, sys
from mathutils import Vector, Matrix, Euler
from mathutils.bvhtree import BVHTree
sys.path.insert(0, "/workspace/fairy_village/src/blender")
import fv_common as C

OUT = "/workspace/fairy_village"
BUNDLE = "/workspace/fairy_village/src/basemesh/human-base-meshes-bundle-v1.4.1/human_base_meshes_bundle.blend"
KEY = C.arg("--key", "elowen_moonwhisper")
MODE = C.arg("--mode", "hero")
PREVIEW = bool(C.arg("--preview", False))
FACINGS = C.arg("--facings", "s,e,n,w").split(",")
FRAMES = int(C.arg("--frames", 8))
SAMPLES = int(C.arg("--samples", 64))
ANIM = []          # (obj, kind, params) evaluated by set_phase


# ------------------------------------------------------------------ base body
def load_body(kind="female"):
    name = f"GEO-body_{kind}_stylized"
    with bpy.data.libraries.load(BUNDLE) as (src, dst):
        dst.objects = [n for n in src.objects if n.startswith(name)]
    col = bpy.context.scene.collection
    body = eyes = None
    eyes = []
    for o in dst.objects:
        col.objects.link(o)
    bpy.context.view_layer.update()
    for o in dst.objects:
        o.animation_data_clear()
        for m in list(o.modifiers):
            o.modifiers.remove(m)
        if o.name == name:
            body = o
        else:
            eyes.append(o)
    # centre the body at the origin (feet on z=0), keep eyes parented
    off = body.matrix_world.translation.copy(); off.z = 0
    for e in eyes:
        mw = e.matrix_world.copy(); e.parent = None; e.matrix_world = mw
    body.location -= off
    for e in eyes:
        e.location -= off
    bpy.context.view_layer.update()
    body.data.materials.clear()
    return body, eyes


def bake_world(o):
    o.data.transform(o.matrix_world); o.matrix_world = Matrix.Identity(4)


def arm_gap_table(verts):
    """Per 1 cm z-bin, the |x| that separates torso from arm (largest gap)."""
    tab = {}
    for zb in range(55, 125):
        z = zb / 100
        xs = sorted(abs(v.co.x) for v in verts if abs(v.co.z - z) < 0.006)
        best = None
        for a, b in zip(xs, xs[1:]):
            if b - a > 0.012 and a > 0.05 and (best is None or b - a > best[1] - best[0]):
                best = (a, b)
        if best:
            tab[zb] = (best[0] + best[1]) / 2
    return tab


def arm_weight(v, tab, h):
    """0 torso .. 1 arm. h = body height scale (1.0 female 1.617)."""
    z = v.z / h * 1.617
    ax = abs(v.x) / h * 1.617
    if z > 1.20:
        t = (ax - 0.125) / 0.05
        t2 = (1.36 - z) / 0.06
        return max(0.0, min(1.0, t)) * max(0.0, min(1.0, t2))
    zb = int(round(z * 100))
    g = tab.get(zb)
    if g is None:
        return 0.0
    return 1.0 if ax > g / h * 1.617 * (h / 1.617) else 0.0


def pose_arms(body, angle_deg=9.0, pivot=(0.15, 1.29), h=1.617):
    me = body.data
    tab = arm_gap_table(me.vertices)
    th = math.radians(angle_deg)
    c, s = math.cos(th), math.sin(th)
    px, pz = pivot[0] * h / 1.617, pivot[1] * h / 1.617
    for v in me.vertices:
        w = arm_weight(v.co, tab, h)
        if w <= 0:
            continue
        sx = 1 if v.co.x > 0 else -1
        dx, dz = abs(v.co.x) - px, v.co.z - pz
        nx, nz = dx * c + dz * s, -dx * s + dz * c
        v.co.x = sx * (px + dx + (nx - dx) * w)
        v.co.z = pz + dz + (nz - dz) * w
    me.update()


def region_scale(body, centre, radius, factor, falloff=0.35, axis_mask=(1, 1, 1)):
    """Smoothly scale vertices around `centre` within `radius` (head enlarge, belly etc.)."""
    cen = Vector(centre)
    for v in body.data.vertices:
        d = (v.co - cen).length
        if d > radius:
            continue
        w = 1.0 if d < radius * (1 - falloff) else (radius - d) / (radius * falloff)
        w = w * w * (3 - 2 * w)
        f = 1 + (factor - 1) * w
        off = v.co - cen
        v.co = cen + Vector((off.x * (f if axis_mask[0] else 1), off.y * (f if axis_mask[1] else 1), off.z * (f if axis_mask[2] else 1)))
    body.data.update()


def wing_mat_iri(name, alpha=0.12, glow=2.2, edge=(0.85, 0.75, 1.0)):
    """Iridescent fairy wing: thin film + facing-driven rainbow tint, few bold radial veins, faint cells, glowing rim."""
    m, nt = C.node_mat(name)
    if nt is None:
        return m
    n = nt.nodes; b = n["Principled BSDF"]
    b.inputs["Roughness"].default_value = 0.08; b.inputs["IOR"].default_value = 1.4
    try:
        b.inputs["Thin Film Thickness"].default_value = 560; b.inputs["Thin Film IOR"].default_value = 1.5
    except KeyError:
        pass
    b.inputs["Coat Weight"].default_value = 0.6
    tc = n.new("ShaderNodeTexCoord")
    sep = n.new("ShaderNodeSeparateXYZ"); C.link(nt, tc.outputs["UV"], sep.inputs[0])
    # fine cells (faint)
    v = n.new("ShaderNodeTexVoronoi"); v.feature = "DISTANCE_TO_EDGE"; v.inputs["Scale"].default_value = 15.0; v.inputs["Randomness"].default_value = 0.85
    C.link(nt, tc.outputs["Object"], v.inputs[0])
    cell = n.new("ShaderNodeMapRange"); cell.inputs["From Min"].default_value = 0.0; cell.inputs["From Max"].default_value = 0.022
    cell.inputs["To Min"].default_value = 0.45; cell.inputs["To Max"].default_value = 0.0
    C.link(nt, v.outputs["Distance"], cell.inputs["Value"])
    # bold radial veins: bands across UV.x (fans out from the root)
    wv = n.new("ShaderNodeTexWave"); wv.wave_type = "BANDS"; wv.bands_direction = "X"; wv.wave_profile = "SIN"
    wv.inputs["Scale"].default_value = 3.2; wv.inputs["Distortion"].default_value = 1.5; wv.inputs["Detail"].default_value = 1.0
    C.link(nt, tc.outputs["UV"], wv.inputs[0])
    vr = n.new("ShaderNodeMapRange"); vr.inputs["From Min"].default_value = 0.93; vr.inputs["From Max"].default_value = 1.0
    C.link(nt, wv.outputs["Fac"], vr.inputs["Value"])
    er = n.new("ShaderNodeMapRange"); er.inputs["From Min"].default_value = 0.9; er.inputs["From Max"].default_value = 1.0
    C.link(nt, sep.outputs["Y"], er.inputs["Value"])
    veins = n.new("ShaderNodeMath"); veins.operation = "MAXIMUM"; C.link(nt, cell.outputs[0], veins.inputs[0]); C.link(nt, vr.outputs[0], veins.inputs[1])
    mxv = n.new("ShaderNodeMath"); mxv.operation = "MAXIMUM"; C.link(nt, veins.outputs[0], mxv.inputs[0]); C.link(nt, er.outputs[0], mxv.inputs[1])
    # iridescent hue: facing + position + noise -> rainbow ramp (rose, violet, cyan, mint, gold)
    lw = n.new("ShaderNodeLayerWeight"); lw.inputs["Blend"].default_value = 0.5
    nz = n.new("ShaderNodeTexNoise"); nz.inputs["Scale"].default_value = 3.0; C.link(nt, tc.outputs["Object"], nz.inputs[0])
    a1 = n.new("ShaderNodeMath"); a1.operation = "MULTIPLY_ADD"; a1.inputs[1].default_value = 0.6
    C.link(nt, sep.outputs["Y"], a1.inputs[0]); C.link(nt, lw.outputs["Facing"], a1.inputs[2])
    a2 = n.new("ShaderNodeMath"); a2.operation = "MULTIPLY_ADD"; a2.inputs[1].default_value = 0.5
    C.link(nt, nz.outputs["Fac"], a2.inputs[0]); C.link(nt, a1.outputs[0], a2.inputs[2])
    fr = n.new("ShaderNodeMath"); fr.operation = "FRACT"; C.link(nt, a2.outputs[0], fr.inputs[0])
    ramp = n.new("ShaderNodeValToRGB"); cr = ramp.color_ramp
    cols = [(0.0, (0.95, 0.12, 0.55)), (0.25, (0.42, 0.12, 1.0)), (0.5, (0.05, 0.55, 1.0)), (0.72, (0.10, 0.95, 0.65)), (0.88, (1.0, 0.70, 0.12)), (1.0, (0.95, 0.12, 0.55))]
    cr.elements[0].position = cols[0][0]; cr.elements[0].color = (*cols[0][1], 1)
    cr.elements[1].position = cols[-1][0]; cr.elements[1].color = (*cols[-1][1], 1)
    for pos, c in cols[1:-1]:
        e = cr.elements.new(pos); e.color = (*c, 1)
    C.link(nt, fr.outputs[0], ramp.inputs["Fac"])
    C.link(nt, ramp.outputs["Color"], b.inputs["Base Color"])
    rim = n.new("ShaderNodeMix"); rim.data_type = "RGBA"; rim.inputs[7].default_value = (*edge, 1)
    C.link(nt, ramp.outputs["Color"], rim.inputs[6]); rf = n.new("ShaderNodeMath"); rf.operation = "MULTIPLY"; rf.inputs[1].default_value = 0.45
    C.link(nt, er.outputs[0], rf.inputs[0]); C.link(nt, rf.outputs[0], rim.inputs["Factor"])
    C.link(nt, rim.outputs[2], b.inputs["Emission Color"])
    al = n.new("ShaderNodeMath"); al.operation = "MULTIPLY_ADD"; al.inputs[1].default_value = 0.55; al.inputs[2].default_value = alpha
    C.link(nt, mxv.outputs[0], al.inputs[0]); C.link(nt, al.outputs[0], b.inputs["Alpha"])
    # emission: soft membrane glow + veins + strong rim
    e1 = n.new("ShaderNodeMath"); e1.operation = "MULTIPLY_ADD"; e1.inputs[1].default_value = glow * 0.22; e1.inputs[2].default_value = 0.45
    C.link(nt, veins.outputs[0], e1.inputs[0])
    e2 = n.new("ShaderNodeMath"); e2.operation = "MULTIPLY_ADD"; e2.inputs[1].default_value = glow
    C.link(nt, er.outputs[0], e2.inputs[0]); C.link(nt, e1.outputs[0], e2.inputs[2])
    C.link(nt, e2.outputs[0], b.inputs["Emission Strength"])
    return m


def extract(body, name, pred, offset=0.004, thick=0.004, mat=None, col=None, subsurf=1):
    """Duplicate body faces whose verts all satisfy pred(co) -> clothing shell pushed out along normals."""
    bm = bmesh.new(); bm.from_mesh(body.data)
    bm.normal_update()
    keep = [f for f in bm.faces if all(pred(v.co) for v in f.verts)]
    kill = [f for f in bm.faces if f not in set(keep)]
    bmesh.ops.delete(bm, geom=kill, context="FACES")
    for v in bm.verts:
        v.co += v.normal * offset
    o = C.obj_from_bm(bm, name, mat, col)
    if thick > 0:
        so = o.modifiers.new("Sol", "SOLIDIFY"); so.thickness = thick; so.offset = 1.0
    if subsurf:
        C.add_mod_subsurf(o, subsurf)
    return o


def bvh(body):
    bm = bmesh.new(); bm.from_mesh(body.data); t = BVHTree.FromBMesh(bm); bm.free(); return t


def surf(tree, origin, direction):
    hit = tree.ray_cast(Vector(origin), Vector(direction).normalized())
    return hit[0], hit[1]


# ------------------------------------------------------------------ materials
def skin_mat(name, base=(0.93, 0.74, 0.64), sss_col=(1.0, 0.45, 0.30), lips=(0.72, 0.32, 0.36), blush=(0.95, 0.52, 0.50)):
    m, nt = C.node_mat(name)
    if nt is None:
        return m
    n = nt.nodes; b = n["Principled BSDF"]
    attr = n.new("ShaderNodeAttribute"); attr.attribute_name = "face_paint"   # R=lips G=blush B=liner
    sep = n.new("ShaderNodeSeparateColor"); C.link(nt, attr.outputs["Color"], sep.inputs[0])
    m1 = n.new("ShaderNodeMix"); m1.data_type = "RGBA"; m1.inputs[6].default_value = (*base, 1); m1.inputs[7].default_value = (*blush, 1)
    f1 = n.new("ShaderNodeMath"); f1.operation = "MULTIPLY"; f1.inputs[1].default_value = 0.35
    C.link(nt, sep.outputs["Green"], f1.inputs[0]); C.link(nt, f1.outputs[0], m1.inputs["Factor"])
    m2 = n.new("ShaderNodeMix"); m2.data_type = "RGBA"; m2.inputs[7].default_value = (*lips, 1)
    C.link(nt, m1.outputs[2], m2.inputs[6]); C.link(nt, sep.outputs["Red"], m2.inputs["Factor"])
    m3 = n.new("ShaderNodeMix"); m3.data_type = "RGBA"; m3.inputs[7].default_value = (0.16, 0.06, 0.12, 1)
    C.link(nt, m2.outputs[2], m3.inputs[6]); C.link(nt, sep.outputs["Blue"], m3.inputs["Factor"])
    C.link(nt, m3.outputs[2], b.inputs["Base Color"])
    b.inputs["Subsurface Weight"].default_value = 0.6
    b.inputs["Subsurface Radius"].default_value = sss_col
    b.inputs["Subsurface Scale"].default_value = 0.02
    b.inputs["Roughness"].default_value = 0.55
    b.inputs["Specular IOR Level"].default_value = 0.4
    b.inputs["Coat Weight"].default_value = 0.05
    nz = n.new("ShaderNodeTexNoise"); nz.inputs["Scale"].default_value = 260; nz.inputs["Detail"].default_value = 4
    bump = n.new("ShaderNodeBump"); bump.inputs["Strength"].default_value = 0.04
    C.link(nt, nz.outputs["Fac"], bump.inputs["Height"]); C.link(nt, bump.outputs[0], b.inputs["Normal"])
    return m


def eye_mat(name, iris=(0.45, 0.30, 0.85)):
    m, nt = C.node_mat(name)
    n = nt.nodes; b = n["Principled BSDF"]
    tc = n.new("ShaderNodeTexCoord"); sep = n.new("ShaderNodeSeparateXYZ"); C.link(nt, tc.outputs["Object"], sep.inputs[0])
    # radial distance from the forward (-Y) axis in object space
    mx = n.new("ShaderNodeMath"); mx.operation = "MULTIPLY"; C.link(nt, sep.outputs["X"], mx.inputs[0]); C.link(nt, sep.outputs["X"], mx.inputs[1])
    mz = n.new("ShaderNodeMath"); mz.operation = "MULTIPLY"; C.link(nt, sep.outputs["Z"], mz.inputs[0]); C.link(nt, sep.outputs["Z"], mz.inputs[1])
    ad = n.new("ShaderNodeMath"); ad.operation = "ADD"; C.link(nt, mx.outputs[0], ad.inputs[0]); C.link(nt, mz.outputs[0], ad.inputs[1])
    sq = n.new("ShaderNodeMath"); sq.operation = "SQRT"; C.link(nt, ad.outputs[0], sq.inputs[0])
    front = n.new("ShaderNodeMath"); front.operation = "LESS_THAN"; front.inputs[1].default_value = 0.0; C.link(nt, sep.outputs["Y"], front.inputs[0])
    ramp = n.new("ShaderNodeValToRGB")
    el = ramp.color_ramp.elements
    el[0].position = 0.0; el[0].color = (0.01, 0.01, 0.015, 1)
    el[1].position = 0.30; el[1].color = (0.97, 0.96, 0.95, 1)
    for pos, c in ((0.16, (0.01, 0.01, 0.015)), (0.175, tuple(x * 0.55 for x in iris)), (0.36, iris), (0.43, tuple(x * 0.25 for x in iris)), (0.47, (0.97, 0.96, 0.95))):
        e = el.new(pos / 0.30 * 0.30 if pos < 0.30 else pos); e.color = (*c, 1)
    el[1].position = 0.52
    div = n.new("ShaderNodeMath"); div.operation = "DIVIDE"; div.inputs[1].default_value = 0.038 * 1.0
    C.link(nt, sq.outputs[0], div.inputs[0])
    sel = n.new("ShaderNodeMix"); sel.data_type = "FLOAT"; sel.inputs[3].default_value = 1.0
    C.link(nt, front.outputs[0], sel.inputs["Factor"]); C.link(nt, div.outputs[0], sel.inputs[2])
    sel.inputs[2].default_value = 0.0
    C.link(nt, div.outputs[0], sel.inputs[3])
    sel2 = n.new("ShaderNodeMix"); sel2.data_type = "FLOAT"
    C.link(nt, front.outputs[0], sel2.inputs["Factor"]); sel2.inputs[2].default_value = 1.0; C.link(nt, div.outputs[0], sel2.inputs[3])
    C.link(nt, sel2.outputs[0], ramp.inputs[0])
    C.link(nt, ramp.outputs[0], b.inputs["Base Color"])
    b.inputs["Roughness"].default_value = 0.05; b.inputs["Coat Weight"].default_value = 1.0; b.inputs["Coat Roughness"].default_value = 0.02
    b.inputs["Emission Color"].default_value = (*iris, 1)
    return m


def fabric_mat(name, c_top, c_bot, sheen=0.8, rough=0.55, stars=None, z0=0.0, z1=1.2, alpha=1.0, trans=0.0, sss=0.1):
    m, nt = C.node_mat(name)
    if nt is None:
        return m
    n = nt.nodes; b = n["Principled BSDF"]
    tc = n.new("ShaderNodeTexCoord"); sep = n.new("ShaderNodeSeparateXYZ"); C.link(nt, tc.outputs["Object"], sep.inputs[0])
    mr = n.new("ShaderNodeMapRange"); mr.inputs["From Min"].default_value = z0; mr.inputs["From Max"].default_value = z1
    C.link(nt, sep.outputs["Z"], mr.inputs["Value"])
    ramp = n.new("ShaderNodeValToRGB"); ramp.color_ramp.elements[0].color = (*c_bot, 1); ramp.color_ramp.elements[1].color = (*c_top, 1)
    C.link(nt, mr.outputs[0], ramp.inputs[0])
    wv = n.new("ShaderNodeTexWave"); wv.wave_type = "BANDS"; wv.inputs["Scale"].default_value = 180; wv.inputs["Distortion"].default_value = 0.5
    C.link(nt, tc.outputs["Object"], wv.inputs[0])
    out = ramp.outputs[0]
    if stars:
        v = n.new("ShaderNodeTexVoronoi"); v.inputs["Scale"].default_value = 38
        C.link(nt, tc.outputs["Object"], v.inputs[0])
        st = n.new("ShaderNodeMapRange"); st.inputs["From Min"].default_value = 0.06; st.inputs["From Max"].default_value = 0.10
        st.inputs["To Min"].default_value = 1.0; st.inputs["To Max"].default_value = 0.0
        C.link(nt, v.outputs["Distance"], st.inputs["Value"])
        msk = n.new("ShaderNodeMath"); msk.operation = "MULTIPLY"; C.link(nt, st.outputs[0], msk.inputs[0])
        inv = n.new("ShaderNodeMath"); inv.operation = "SUBTRACT"; inv.inputs[0].default_value = 1.0; C.link(nt, mr.outputs[0], inv.inputs[1])
        C.link(nt, inv.outputs[0], msk.inputs[1])
        mx = n.new("ShaderNodeMix"); mx.data_type = "RGBA"; C.link(nt, msk.outputs[0], mx.inputs["Factor"])
        C.link(nt, ramp.outputs[0], mx.inputs[6]); mx.inputs[7].default_value = (*stars, 1)
        out = mx.outputs[2]
        em = n.new("ShaderNodeMath"); em.operation = "MULTIPLY"; em.inputs[1].default_value = 4.0
        C.link(nt, msk.outputs[0], em.inputs[0]); C.link(nt, em.outputs[0], b.inputs["Emission Strength"])
        b.inputs["Emission Color"].default_value = (*stars, 1)
    C.link(nt, out, b.inputs["Base Color"])
    b.inputs["Roughness"].default_value = rough
    b.inputs["Sheen Weight"].default_value = sheen; b.inputs["Sheen Roughness"].default_value = 0.35
    b.inputs["Subsurface Weight"].default_value = sss; b.inputs["Subsurface Scale"].default_value = 0.01
    b.inputs["Alpha"].default_value = alpha
    b.inputs["Transmission Weight"].default_value = trans
    bump = n.new("ShaderNodeBump"); bump.inputs["Strength"].default_value = 0.08
    C.link(nt, wv.outputs["Fac"], bump.inputs["Height"]); C.link(nt, bump.outputs[0], b.inputs["Normal"])
    return m


def hair_mat(name, root, tip, spec=(1.0, 0.95, 0.9)):
    m, nt = C.node_mat(name)
    if nt is None:
        return m
    n = nt.nodes; b = n["Principled BSDF"]
    tc = n.new("ShaderNodeTexCoord"); sep = n.new("ShaderNodeSeparateXYZ"); C.link(nt, tc.outputs["Generated"], sep.inputs[0])
    wv = n.new("ShaderNodeTexWave"); wv.wave_type = "BANDS"; wv.bands_direction = "X"
    wv.inputs["Scale"].default_value = 9; wv.inputs["Distortion"].default_value = 2.5; wv.inputs["Detail"].default_value = 6
    C.link(nt, tc.outputs["UV"], wv.inputs[0])
    tcz = n.new("ShaderNodeSeparateXYZ"); C.link(nt, tc.outputs["Object"], tcz.inputs[0])
    mr = n.new("ShaderNodeMapRange"); mr.inputs["From Min"].default_value = 0.9; mr.inputs["From Max"].default_value = 1.6
    C.link(nt, tcz.outputs["Z"], mr.inputs["Value"])
    ramp = n.new("ShaderNodeValToRGB"); ramp.color_ramp.elements[0].color = (*tip, 1); ramp.color_ramp.elements[1].color = (*root, 1)
    C.link(nt, mr.outputs[0], ramp.inputs[0])
    mx = n.new("ShaderNodeMix"); mx.data_type = "RGBA"; mx.blend_type = "MULTIPLY"; mx.inputs["Factor"].default_value = 0.35
    C.link(nt, ramp.outputs[0], mx.inputs[6]); C.link(nt, wv.outputs["Color"], mx.inputs[7])
    C.link(nt, mx.outputs[2], b.inputs["Base Color"])
    b.inputs["Roughness"].default_value = 0.36; b.inputs["Anisotropic"].default_value = 0.9
    b.inputs["Subsurface Weight"].default_value = 0.15; b.inputs["Subsurface Scale"].default_value = 0.01
    b.inputs["Sheen Weight"].default_value = 0.5; b.inputs["Coat Weight"].default_value = 0.4
    bump = n.new("ShaderNodeBump"); bump.inputs["Strength"].default_value = 0.25
    C.link(nt, wv.outputs["Fac"], bump.inputs["Height"]); C.link(nt, bump.outputs[0], b.inputs["Normal"])
    return m


def wing_mat(name, tint=(0.75, 0.88, 1.0), vein=(0.55, 0.75, 1.0), edge=(1.0, 0.7, 0.95), alpha=0.35):
    m, nt = C.node_mat(name)
    if nt is None:
        return m
    n = nt.nodes; b = n["Principled BSDF"]
    b.inputs["Base Color"].default_value = (*tint, 1); b.inputs["Roughness"].default_value = 0.12
    b.inputs["Transmission Weight"].default_value = 0.6; b.inputs["IOR"].default_value = 1.35
    try:
        b.inputs["Thin Film Thickness"].default_value = 480; b.inputs["Thin Film IOR"].default_value = 1.4
    except KeyError:
        pass
    b.inputs["Coat Weight"].default_value = 0.4
    tc = n.new("ShaderNodeTexCoord")
    v = n.new("ShaderNodeTexVoronoi"); v.feature = "DISTANCE_TO_EDGE"; v.inputs["Scale"].default_value = 7.0
    C.link(nt, tc.outputs["UV"], v.inputs[0])
    mr = n.new("ShaderNodeMapRange"); mr.inputs["From Min"].default_value = 0.0; mr.inputs["From Max"].default_value = 0.035
    mr.inputs["To Min"].default_value = 1.0; mr.inputs["To Max"].default_value = 0.0
    C.link(nt, v.outputs["Distance"], mr.inputs["Value"])
    sep = n.new("ShaderNodeSeparateXYZ"); C.link(nt, tc.outputs["UV"], sep.inputs[0])
    # edge glow: UV.y holds the outline factor (1 at the rim)
    er = n.new("ShaderNodeMapRange"); er.inputs["From Min"].default_value = 0.8; er.inputs["From Max"].default_value = 1.0
    C.link(nt, sep.outputs["Y"], er.inputs["Value"])
    mxv = n.new("ShaderNodeMath"); mxv.operation = "MAXIMUM"; C.link(nt, mr.outputs[0], mxv.inputs[0]); C.link(nt, er.outputs[0], mxv.inputs[1])
    al = n.new("ShaderNodeMath"); al.operation = "MULTIPLY_ADD"; al.inputs[1].default_value = 0.55; al.inputs[2].default_value = alpha
    C.link(nt, mxv.outputs[0], al.inputs[0]); C.link(nt, al.outputs[0], b.inputs["Alpha"])
    col = n.new("ShaderNodeMix"); col.data_type = "RGBA"; col.inputs[6].default_value = (*vein, 1); col.inputs[7].default_value = (*edge, 1)
    C.link(nt, er.outputs[0], col.inputs["Factor"]); C.link(nt, col.outputs[2], b.inputs["Emission Color"])
    em = n.new("ShaderNodeMath"); em.operation = "MULTIPLY"; em.inputs[1].default_value = 1.6
    C.link(nt, mxv.outputs[0], em.inputs[0]); C.link(nt, em.outputs[0], b.inputs["Emission Strength"])
    return m


# ------------------------------------------------------------------ parts
def wing(name, outline, mat, col, root, rot, scale=1.0):
    """outline: list of (x, y) in the wing plane, root at (0,0). UV.y = rim factor, UV.x/y also drive veins."""
    bm = bmesh.new(); uvl = bm.loops.layers.uv.new("UVMap")
    ctr = bm.verts.new((0, 0, 0))
    pts = [Vector((x * scale, 0, y * scale)) for x, y in outline]
    # dense fan: 6 rings from root to rim
    R = 6
    rings = []
    for r in range(1, R + 1):
        t = r / R
        rings.append([bm.verts.new(p * t) for p in pts])
    n = len(pts)
    for i in range(n):
        j = (i + 1) % n
        f = bm.faces.new((ctr, rings[0][i], rings[0][j]))
        for r in range(R - 1):
            bm.faces.new((rings[r][i], rings[r + 1][i], rings[r + 1][j], rings[r][j]))
    for f in bm.faces:
        for lp in f.loops:
            co = lp.vert.co
            # rim factor: distance ratio to outline
            best = max((co.length / max(1e-6, p.length)) if (co.normalized() - p.normalized()).length < 0.35 else 0 for p in pts) if co.length > 0 else 0
            lp[uvl].uv = (co.x / scale * 0.9 + co.z / scale * 0.3, min(1.0, best))
    o = C.obj_from_bm(bm, name, mat, col)
    sol = o.modifiers.new("Sol", "SOLIDIFY"); sol.thickness = 0.003
    C.add_mod_subsurf(o, 1)
    o.location = root; o.rotation_mode = "XYZ"; o.rotation_euler = rot
    return o


def strand(name, pts, r, mat, col, taper=(1.0, 0.85, 0.5, 0.15), res=10):
    radii = [taper[min(len(taper) - 1, int(i / max(1, len(pts) - 1) * (len(taper) - 1) + 0.5))] for i in range(len(pts))]
    return C.tube_curve(name, pts, radius=r, mat=mat, col=col, radii=radii, res=res, bevel_res=4)


def paint_face(body, eyes, lips_c, cheeks, mouth_w=0.024, lip_h=0.008, liner=True):
    """Vertex-colour mask on the body: R=lips G=blush B=eye liner. Positions found from the eyes."""
    me = body.data
    if "face_paint" not in me.color_attributes:
        me.color_attributes.new("face_paint", "FLOAT_COLOR", "POINT")
    ca = me.color_attributes["face_paint"]
    eL = [e for e in eyes if e.name.endswith(".L")][0].matrix_world.translation
    eR = [e for e in eyes if e.name.endswith(".R")][0].matrix_world.translation
    for i, v in enumerate(me.vertices):
        co = v.co
        r = g = b = 0.0
        dl = Vector(((co.x - lips_c.x) / mouth_w, (co.y - lips_c.y) / 0.03, (co.z - lips_c.z) / lip_h))
        if co.y < lips_c.y + 0.02:
            r = max(0.0, 1 - dl.length ** 2) ** 0.6
        for ch in cheeks:
            dc = (co - ch).length
            g = max(g, max(0.0, 1 - dc / 0.03))
        if liner:
            for e in (eL, eR):
                d = co - e
                if d.y < 0.0 and 0.006 < d.z < 0.026 and abs(d.x) < 0.034:
                    rr = math.hypot(d.x / 0.034, (d.z - 0.004) / 0.022)
                    if 0.95 < rr < 1.03:
                        b = max(b, 0.5)
        ca.data[i].color = (r, g, b, 1)


def pointed_ear(name, body_tree, side, height, mat, col, length=0.06, h=1.617):
    """Elf/fairy ear tip: a tapered curved cone attached to the ear rim."""
    z = height if height else 1.475 * h / 1.617
    hit, nrm = surf(body_tree, (side * 0.3, 0.005, z), (-side, 0, 0))
    if hit is None:
        return None
    base = hit + Vector((-side * 0.004, 0.006, 0.008))
    pts = [base, base + Vector((side * length * 0.25, length * 0.18, length * 0.42)), base + Vector((side * length * 0.42, length * 0.35, length * 0.9))]
    return C.tube_curve(name, pts, radius=0.011 * h / 1.617, mat=mat, col=col, radii=[1.0, 0.7, 0.08])


# ------------------------------------------------------------------ cameras
def sprite_camera(sc, h_px=288, height_m=1.65, el=30, w=384, hgt=512, feet=(192, 472)):
    """Ortho camera, elevation `el`, figure of height_m projected to ~h_px at 4x. Feet anchored at `feet` px."""
    cam_d = bpy.data.cameras.new("SprCam"); cam_d.type = "ORTHO"
    ppm = h_px / (height_m * math.cos(math.radians(el)) + 0.0)   # px per metre (vertical extent of a standing figure)
    ppm = h_px / height_m
    cam_d.ortho_scale = w / ppm
    cam = bpy.data.objects.new("SprCam", cam_d); sc.collection.objects.link(cam)
    cam.rotation_euler = (math.radians(90 - el), 0, 0)
    fwd = Vector((0, math.cos(math.radians(el)), -math.sin(math.radians(el))))
    up = Vector((0, math.sin(math.radians(el)), math.cos(math.radians(el))))
    # the image point for world origin must land on `feet`
    dx_px = feet[0] - w / 2; dy_px = feet[1] - hgt / 2
    centre = Vector((0, 0, 0)) - Vector((1, 0, 0)) * (dx_px / ppm) + up * (dy_px / ppm)
    cam.location = centre - fwd * 20
    sc.camera = cam
    sc.render.resolution_x = w; sc.render.resolution_y = hgt
    cam_d.shift_x = 0; cam_d.shift_y = 0
    return cam, ppm


# ------------------------------------------------------------------ overrides / generic builders
def eye_mat(name, iris=(0.45, 0.30, 0.85)):
    m, nt = C.node_mat(name)
    if nt is None:
        return m
    n = nt.nodes; b = n["Principled BSDF"]
    tc = n.new("ShaderNodeTexCoord"); sep = n.new("ShaderNodeSeparateXYZ"); C.link(nt, tc.outputs["Object"], sep.inputs[0])
    comb = n.new("ShaderNodeCombineXYZ"); C.link(nt, sep.outputs["X"], comb.inputs["X"]); C.link(nt, sep.outputs["Z"], comb.inputs["Y"])
    ln = n.new("ShaderNodeVectorMath"); ln.operation = "LENGTH"; C.link(nt, comb.outputs[0], ln.inputs[0])
    div = n.new("ShaderNodeMath"); div.operation = "DIVIDE"; div.inputs[1].default_value = 0.0384; C.link(nt, ln.outputs["Value"], div.inputs[0])
    back = n.new("ShaderNodeMath"); back.operation = "GREATER_THAN"; back.inputs[1].default_value = 0.0; C.link(nt, sep.outputs["Y"], back.inputs[0])
    mxf = n.new("ShaderNodeMath"); mxf.operation = "MAXIMUM"; C.link(nt, div.outputs[0], mxf.inputs[0]); C.link(nt, back.outputs[0], mxf.inputs[1])
    ramp = n.new("ShaderNodeValToRGB"); el = ramp.color_ramp.elements
    el[0].position = 0.0; el[0].color = (0.005, 0.005, 0.01, 1); el[1].position = 1.0; el[1].color = (0.80, 0.79, 0.80, 1)
    for pos, c in ((0.17, (0.005, 0.005, 0.01)), (0.19, tuple(x * 0.45 for x in iris)), (0.33, iris), (0.40, tuple(min(1, x * 1.3) for x in iris)),
                   (0.44, tuple(x * 0.25 for x in iris)), (0.48, (0.78, 0.77, 0.79))):
        e = el.new(pos); e.color = (*c, 1)
    C.link(nt, mxf.outputs[0], ramp.inputs[0]); C.link(nt, ramp.outputs[0], b.inputs["Base Color"])
    b.inputs["Roughness"].default_value = 0.25; b.inputs["Coat Weight"].default_value = 1.0; b.inputs["Coat Roughness"].default_value = 0.03
    # faint iris glow (fairy eyes)
    ir = n.new("ShaderNodeMapRange"); ir.inputs["From Min"].default_value = 0.19; ir.inputs["From Max"].default_value = 0.44
    C.link(nt, mxf.outputs[0], ir.inputs["Value"])
    pk = n.new("ShaderNodeMath"); pk.operation = "PINGPONG"; pk.inputs[1].default_value = 0.5; C.link(nt, ir.outputs[0], pk.inputs[0])
    em = n.new("ShaderNodeMath"); em.operation = "MULTIPLY"; em.inputs[1].default_value = 0.6; C.link(nt, pk.outputs[0], em.inputs[0])
    b.inputs["Emission Color"].default_value = (*iris, 1); C.link(nt, em.outputs[0], b.inputs["Emission Strength"])
    return m


def wing(name, outline, mat, col, root, rot, scale=1.0):
    bm = bmesh.new(); uvl = bm.loops.layers.uv.new("UVMap")
    ctr = bm.verts.new((0, 0, 0))
    pts = [Vector((x * scale, 0, y * scale)) for x, y in outline]
    R = 7
    rings = [[bm.verts.new(p * (r / R)) for p in pts] for r in range(1, R + 1)]
    tval = {ctr: 0.0}
    for r, ring in enumerate(rings):
        for v in ring:
            tval[v] = (r + 1) / R
    n = len(pts)
    for i in range(n):
        j = (i + 1) % n
        bm.faces.new((ctr, rings[0][i], rings[0][j]))
        for r in range(R - 1):
            bm.faces.new((rings[r][i], rings[r + 1][i], rings[r + 1][j], rings[r][j]))
    for f in bm.faces:
        for lp in f.loops:
            lp[uvl].uv = (lp.vert.co.x / scale, tval[lp.vert])
    o = C.obj_from_bm(bm, name, mat, col)
    sol = o.modifiers.new("Sol", "SOLIDIFY"); sol.thickness = 0.002
    C.add_mod_subsurf(o, 2)
    o.location = root; o.rotation_mode = "XYZ"; o.rotation_euler = rot
    return o


def wing_mat(name, tint=(0.75, 0.88, 1.0), vein=(0.55, 0.75, 1.0), edge=(1.0, 0.7, 0.95), alpha=0.22, glow=1.2):
    m, nt = C.node_mat(name)
    if nt is None:
        return m
    n = nt.nodes; b = n["Principled BSDF"]
    b.inputs["Base Color"].default_value = (*tint, 1); b.inputs["Roughness"].default_value = 0.1
    b.inputs["IOR"].default_value = 1.4
    try:
        b.inputs["Thin Film Thickness"].default_value = 520; b.inputs["Thin Film IOR"].default_value = 1.45
    except KeyError:
        pass
    b.inputs["Coat Weight"].default_value = 0.5
    tc = n.new("ShaderNodeTexCoord")
    v = n.new("ShaderNodeTexVoronoi"); v.feature = "DISTANCE_TO_EDGE"; v.inputs["Scale"].default_value = 26.0; v.inputs["Randomness"].default_value = 0.7
    C.link(nt, tc.outputs["Object"], v.inputs[0])
    mr = n.new("ShaderNodeMapRange"); mr.inputs["From Min"].default_value = 0.0; mr.inputs["From Max"].default_value = 0.05
    mr.inputs["To Min"].default_value = 0.8; mr.inputs["To Max"].default_value = 0.0
    C.link(nt, v.outputs["Distance"], mr.inputs["Value"])
    # radial main veins
    sep = n.new("ShaderNodeSeparateXYZ"); C.link(nt, tc.outputs["UV"], sep.inputs[0])
    er = n.new("ShaderNodeMapRange"); er.inputs["From Min"].default_value = 0.88; er.inputs["From Max"].default_value = 1.0
    C.link(nt, sep.outputs["Y"], er.inputs["Value"])
    grad = n.new("ShaderNodeMapRange"); grad.inputs["From Min"].default_value = 0.0; grad.inputs["From Max"].default_value = 1.0
    C.link(nt, sep.outputs["Y"], grad.inputs["Value"])
    mxv = n.new("ShaderNodeMath"); mxv.operation = "MAXIMUM"; C.link(nt, mr.outputs[0], mxv.inputs[0]); C.link(nt, er.outputs[0], mxv.inputs[1])
    al = n.new("ShaderNodeMath"); al.operation = "MULTIPLY_ADD"; al.inputs[1].default_value = 0.6; al.inputs[2].default_value = alpha
    C.link(nt, mxv.outputs[0], al.inputs[0]); C.link(nt, al.outputs[0], b.inputs["Alpha"])
    colm = n.new("ShaderNodeMix"); colm.data_type = "RGBA"; colm.inputs[6].default_value = (*vein, 1); colm.inputs[7].default_value = (*edge, 1)
    C.link(nt, grad.outputs[0], colm.inputs["Factor"]); C.link(nt, colm.outputs[2], b.inputs["Emission Color"])
    C.link(nt, colm.outputs[2], b.inputs["Base Color"])
    em = n.new("ShaderNodeMath"); em.operation = "MULTIPLY_ADD"; em.inputs[1].default_value = glow; em.inputs[2].default_value = 0.12
    C.link(nt, mxv.outputs[0], em.inputs[0]); C.link(nt, em.outputs[0], b.inputs["Emission Strength"])
    return m


def extract(body, name, pred, offset=0.004, thick=0.004, mat=None, col=None, subsurf=1):
    bm = bmesh.new(); bm.from_mesh(body.data)
    bm.normal_update(); bm.verts.ensure_lookup_table()
    keep = set(f for f in bm.faces if all(pred(v) for v in f.verts))
    bmesh.ops.delete(bm, geom=[f for f in bm.faces if f not in keep], context="FACES")
    for v in bm.verts:
        v.co += v.normal * offset
    o = C.obj_from_bm(bm, name, mat, col)
    if thick > 0:
        so = o.modifiers.new("Sol", "SOLIDIFY"); so.thickness = thick; so.offset = 1.0
    if subsurf:
        C.add_mod_subsurf(o, subsurf)
    return o


def arm_mask(body, h):
    """Arm vertices: BFS from each hand tip, limited to z < zcut. zcut is the highest level at which the BFS does not leak
    into the torso/legs (the free-hanging part of the arm). Above zcut, the shoulder cap = |x| beyond the torso edge."""
    me = body.data
    s = h / 1.617
    V = me.vertices
    adj = [[] for _ in V]
    for e in me.edges:
        a, b = e.vertices
        adj[a].append(b); adj[b].append(a)
    tips = [max(range(len(V)), key=lambda i: V[i].co.x * side) for side in (1, -1)]

    def bfs(zcut):
        mask = [False] * len(V)
        for side, tip in zip((1, -1), tips):
            stack = [tip]; mask[tip] = True
            while stack:
                i = stack.pop()
                for j in adj[i]:
                    if not mask[j] and V[j].co.z < zcut and V[j].co.x * side > 0.04 * s:
                        mask[j] = True; stack.append(j)
        return mask
    zcut = 1.36 * s
    while zcut > 0.9 * s:
        m = bfs(zcut)
        leak = any(m[i] and abs(V[i].co.x) < 0.10 * s and V[i].co.z < 1.0 * s for i in range(len(V)))
        if not leak:
            break
        zcut -= 0.01
    mask = m
    zc = zcut - 0.02
    torso = [abs(V[i].co.x) for i in range(len(V)) if not mask[i] and abs(V[i].co.z - zc) < 0.015]
    torso_edge = max(torso) if torso else 0.15 * s
    for i, v in enumerate(V):
        if zcut <= v.co.z < zcut + 0.2 * s and abs(v.co.x) > torso_edge + 0.006 + max(0.0, v.co.z - zcut) * 0.25:
            mask[i] = True
    print("ARM_MASK zcut", round(zcut, 3), "torso_edge", round(torso_edge, 3), "count", sum(mask), flush=True)
    return mask


def section(body, z, mask, tol=0.008):
    pts = [v.co for i, v in enumerate(body.data.vertices) if abs(v.co.z - z) < tol and not mask[i]]
    xs = [p.x for p in pts]; ys = [p.y for p in pts]
    return (min(xs), max(xs), min(ys), max(ys))


def skirt(name, body, mask, z_top, z_bot, r_bot, mat, col, folds=16, fold_amp=0.022, train=0.0, hem=None, segs=128, rings=40,
          grow=1.0, thick=0.008, expo=1.5):
    x0, x1, y0, y1 = section(body, z_top, mask)
    rx0, ry0 = (x1 - x0) / 2 + 0.012, (y1 - y0) / 2 + 0.014
    cy0 = (y0 + y1) / 2
    bm = bmesh.new(); uvl = bm.loops.layers.uv.new("UVMap")
    grid = []
    for i in range(rings + 1):
        t = i / rings
        z = z_top + (z_bot - z_top) * t
        k = t ** expo
        rx = rx0 + (r_bot[0] - rx0) * k
        ry = ry0 + (r_bot[1] - ry0) * k
        cy = cy0 + (0.02 - cy0) * k
        row = []
        for j in range(segs):
            a = 2 * math.pi * j / segs
            ca, sa = math.cos(a), math.sin(a)
            amp = fold_amp * (t ** 0.8) * grow
            fr = amp * (math.sin(folds * a + 1.3 * math.sin(3 * a)) * 0.8 + 0.2 * math.sin(2.3 * folds * a))
            tr = train * max(0.0, sa) ** 2 * k
            zz = z
            if hem is not None and i == rings:
                zz = z + hem(a)
            row.append(bm.verts.new(((rx + fr) * ca, cy + (ry + fr) * sa + tr, zz)))
        grid.append(row)
    for i in range(rings):
        for j in range(segs):
            jj = (j + 1) % segs
            f = bm.faces.new((grid[i][j], grid[i][jj], grid[i + 1][jj], grid[i + 1][j]))
            for lp, (u, w) in zip(f.loops, ((j, i), (j + 1, i), (j + 1, i + 1), (j, i + 1))):
                lp[uvl].uv = (u / segs, 1 - w / rings)
    if hem is not None:
        for i in range(1, rings + 1):
            t = i / rings
            for j in range(segs):
                a = 2 * math.pi * j / segs
                v = grid[i][j]
                floor_z = z_bot + hem(a)
                if v.co.z < floor_z:
                    v.co.z = floor_z
    o = C.obj_from_bm(bm, name, mat, col)
    so = o.modifiers.new("Sol", "SOLIDIFY"); so.thickness = thick
    C.add_mod_subsurf(o, 1)
    return o


def ring_curve(name, cx, cy, rx, ry, z, r, mat, col, n=48, tilt=0.0):
    pts = [(cx + rx * math.cos(2 * math.pi * i / n), cy + ry * math.sin(2 * math.pi * i / n),
            z + tilt * math.sin(2 * math.pi * i / n)) for i in range(n + 1)]
    return C.tube_curve(name, pts, radius=r, mat=mat, col=col)


def leaf_shape(name, L, Wd, mat, col, curl=0.25):
    bm = bmesh.new(); uvl = bm.loops.layers.uv.new("UVMap")
    nl, nw = 10, 6
    grid = []
    for i in range(nl + 1):
        t = i / nl
        wv = Wd * math.sin(math.pi * t) ** 0.8 * (1 - 0.3 * t)
        row = []
        for j in range(nw + 1):
            u = j / nw - 0.5
            row.append(bm.verts.new((u * wv, t * L, curl * L * t * t + 0.15 * Wd * (2 * u) ** 2)))
        grid.append(row)
    for i in range(nl):
        for j in range(nw):
            f = bm.faces.new((grid[i][j], grid[i][j + 1], grid[i + 1][j + 1], grid[i + 1][j]))
            for lp, (a, b) in zip(f.loops, ((j, i), (j + 1, i), (j + 1, i + 1), (j, i + 1))):
                lp[uvl].uv = (a / nw, b / nl)
    o = C.obj_from_bm(bm, name, mat, col)
    so = o.modifiers.new("Sol", "SOLIDIFY"); so.thickness = 0.004
    return o


def hair_locks(prefix, body, tree, mat, col, h, n=70, length_z=0.95, back_y=0.10, seed=3, front_frac=0.25, spread=1.25, wave=0.012,
               r=0.016, top_z=1.6, crown=(0.0, -0.01)):
    """Long flowing locks from a scalp ring down the back (some over the shoulders)."""
    rnd = random.Random(seed)
    s = h / 1.617
    out = []
    for i in range(n):
        a = rnd.uniform(-math.pi * 0.95, math.pi * 0.95) if i % 5 else rnd.uniform(-0.5, 0.5)   # 0 = straight back
        el = rnd.uniform(0.15, 1.15)
        d = Vector((math.sin(a) * math.cos(el), math.cos(a) * math.cos(el), math.sin(el)))
        c0 = Vector((crown[0], crown[1] * s, 1.50 * s))
        hit, nrm = surf(tree, c0 + d * 0.4 * s, -d)
        if hit is None:
            continue
        root = hit + nrm * 0.012 * s
        if root.y < -0.07 * s and root.z < 1.56 * s:
            continue
        side = 1 if root.x >= 0 else -1
        front = (abs(root.x) > 0.06 * s and root.y < 0.0 and rnd.random() < front_frac * 2.5) or (rnd.random() < front_frac * 0.3 and abs(root.x) > 0.05 * s)
        endz = (length_z + rnd.uniform(-0.06, 0.06)) * s
        pts = [root, root + nrm * 0.03 * s + Vector((0, 0.0, -0.01 * s))]
        if front:
            sx = side * rnd.uniform(0.10, 0.15) * s
            pts += [Vector((sx * 0.95, -0.02 * s, 1.36 * s)), Vector((sx, -0.07 * s, 1.24 * s)), Vector((sx * 0.9 + side * wave * s, -0.085 * s, (1.24 * s + endz) / 2)),
                    Vector((sx * 0.85, -0.075 * s, max(endz, 1.02 * s)))]
        else:
            bx = root.x * spread + rnd.uniform(-0.015, 0.015) * s
            by = back_y * s + rnd.uniform(-0.01, 0.025) * s
            zs = [1.40 * s, 1.24 * s, (1.24 * s + endz) / 2, endz]
            for k, z in enumerate(zs):
                w = wave * s * math.sin(k * 1.7 + i) * (k / 3)
                pts.append(Vector((bx * (1 + 0.1 * k) + w, by + 0.012 * s * k, z)))
        o = strand(f"{prefix}{i}", pts, r * s * rnd.uniform(0.8, 1.25), mat, col, taper=(1.0, 1.0, 0.95, 0.8, 0.55, 0.12))
        out.append(o)
    return out


def brows(prefix, eyes, tree, mat, col, h, thick=0.0028, lift=0.024, arch=0.004, w=0.03, inner_drop=0.0):
    out = []
    for e in eyes:
        ec = e.matrix_world.translation
        side = 1 if ec.x > 0 else -1
        pts = []
        for k in range(5):
            t = k / 4
            x = ec.x + side * (-0.4 + t) * w * 1.1 * h / 1.617
            z = ec.z + lift * h / 1.617 + arch * math.sin(math.pi * t) - inner_drop * (1 - t)
            hit, nrm = surf(tree, (x, -0.5, z), (0, 1, 0))
            if hit:
                pts.append(hit + nrm * 0.0025)
        if len(pts) >= 3:
            out.append(C.tube_curve(f"{prefix}{side}", pts, radius=thick * h / 1.617, mat=mat, col=col, radii=[0.6, 1.0, 1.0, 0.8, 0.35][:len(pts)]))
    return out


def lashes(prefix, eyes, mat, col, h):
    out = []
    for e in eyes:
        ec = e.matrix_world.translation
        side = 1 if ec.x > 0 else -1
        pts = []
        for k in range(7):
            a = math.radians(200 - k * 33.3)   # arc over the top of the eye, in xz, slightly in front
            pts.append(Vector((ec.x + side * 0.0 + 0.036 * math.cos(a) * -side * -1, ec.y - 0.026, ec.z + 0.004 + 0.02 * max(0, math.sin(a)) + 0.004)))
        out.append(C.tube_curve(f"{prefix}{side}", pts, radius=0.0016, mat=mat, col=col, radii=[0.3, 0.8, 1, 1, 1, 0.9, 1.4]))
    return out


# ------------------------------------------------------------------ characters
def fairy_wings(prefix, col, root, mat, span=1.0, sweep=28, lower=True, droop=0.0):
    upper = [(0.0, 0.0), (0.04, 0.08), (0.10, 0.20), (0.18, 0.33), (0.28, 0.45), (0.40, 0.55), (0.50, 0.60), (0.57, 0.60), (0.60, 0.55), (0.60, 0.45),
             (0.56, 0.33), (0.48, 0.21), (0.36, 0.11), (0.22, 0.04), (0.09, 0.0)]
    low = [(0.0, 0.0), (0.08, -0.01), (0.19, -0.06), (0.29, -0.14), (0.35, -0.24), (0.36, -0.33), (0.32, -0.40), (0.25, -0.41), (0.18, -0.35),
           (0.11, -0.24), (0.05, -0.11)]
    ws = []
    for side in (1, -1):
        ol_u = [(side * x, y) for x, y in upper]
        ol_l = [(side * x, y) for x, y in low]
        if side < 0:
            ol_u = ol_u[::-1]; ol_l = ol_l[::-1]
        rz = math.radians(sweep) * side
        wu = wing(f"{prefix}U{side}", ol_u, mat, col, (root[0] + side * 0.02, root[1], root[2]), (0, side * math.radians(-6 - droop), rz), scale=span)
        ws.append((wu, side, "upper"))
        if lower:
            wl = wing(f"{prefix}L{side}", ol_l, mat, col, (root[0] + side * 0.02, root[1], root[2] - 0.03), (0, side * math.radians(8 + droop), rz * 1.15), scale=span)
            ws.append((wl, side, "lower"))
    for o, side, kind in ws:
        ANIM.append((o, "wing", {"side": side, "base": o.rotation_euler.copy(), "amp": math.radians(16 if kind == "upper" else 12), "kind": kind}))
    return [w[0] for w in ws]


def finish_eyes(eyes, iris):
    m = eye_mat("FV_Eye_" + KEY, iris)
    for e in eyes:
        e.data.materials.clear(); e.data.materials.append(m)
        sub = e.modifiers.new("Sub", "SUBSURF"); sub.levels = 1; sub.render_levels = 2



def hair_sheet(name, mat, col, z_top=1.47, z_bot=0.84, y_off=0.035, s=1.0, a0=-105, a1=105, rx=(0.105, 0.17), ry=(0.11, 0.12), segs=40, rings=24):
    bm = bmesh.new()
    grid = []
    for i in range(rings + 1):
        t = i / rings
        z = (z_top + (z_bot - z_top) * t) * s
        r_x = (rx[0] + (rx[1] - rx[0]) * min(1, t * 1.8)) * s
        r_y = (ry[0] + (ry[1] - ry[0]) * min(1, t * 1.8)) * s
        cy = (-0.02 + (y_off + 0.02) * min(1, t * 2.2)) * s
        row = []
        for j in range(segs + 1):
            a = math.radians(a0 + (a1 - a0) * j / segs)
            wv = 0.006 * s * math.sin(9 * a + 3 * t)
            # back half: angle 0 points to +Y (behind)
            row.append(bm.verts.new(((r_x + wv) * math.sin(a), cy + (r_y + wv) * math.cos(a), z - 0.04 * s * (abs(a) / math.pi) * t)))
        grid.append(row)
    for i in range(rings):
        for j in range(segs):
            bm.faces.new((grid[i][j], grid[i][j + 1], grid[i + 1][j + 1], grid[i + 1][j]))
    o = C.obj_from_bm(bm, name, mat, col)
    so = o.modifiers.new("Sol", "SOLIDIFY"); so.thickness = 0.01 * s
    C.add_mod_subsurf(o, 1)
    return o


def capelet(name, body, mask, mat, col, z_neck=1.335, z_hem=1.16, r_hem=0.255, scallops=9, s=1.0):
    x0, x1, y0, y1 = section(body, z_neck, mask, tol=0.006)
    rx0, ry0, cy0 = (x1 - x0) / 2 + 0.01 * s, (y1 - y0) / 2 + 0.01 * s, (y0 + y1) / 2
    bm = bmesh.new(); grid = []
    rings, segs = 18, 96
    for i in range(rings + 1):
        t = i / rings
        row = []
        for j in range(segs):
            a = 2 * math.pi * j / segs
            k = math.sin(t * math.pi / 2)
            rx = rx0 + (r_hem - rx0) * k
            ry = ry0 + (r_hem * 0.62 - ry0) * k
            z = z_neck + (z_hem - z_neck) * t
            if i == rings:
                z += 0.035 * s * (0.5 + 0.5 * math.cos(scallops * a))
            row.append(bm.verts.new((rx * math.cos(a), cy0 + ry * math.sin(a), z)))
        grid.append(row)
    for i in range(rings):
        for j in range(segs):
            jj = (j + 1) % segs
            bm.faces.new((grid[i][j], grid[i][jj], grid[i + 1][jj], grid[i + 1][j]))
    o = C.obj_from_bm(bm, name, mat, col)
    so = o.modifiers.new("Sol", "SOLIDIFY"); so.thickness = 0.004 * s
    sw = o.modifiers.new("Shrink", "SHRINKWRAP"); sw.target = body; sw.wrap_method = "PROJECT"; sw.use_project_z = False
    o.modifiers.remove(sw)
    C.add_mod_subsurf(o, 1)
    return o



def catmull(pts, n=18):
    P = [Vector(p) for p in pts]
    P = [P[0] + (P[0] - P[1])] + P + [P[-1] + (P[-1] - P[-2])]
    out = []
    for i in range(1, len(P) - 2):
        p0, p1, p2, p3 = P[i - 1], P[i], P[i + 1], P[i + 2]
        for k in range(n):
            t = k / n
            out.append(0.5 * ((2 * p1) + (-p0 + p2) * t + (2 * p0 - 5 * p1 + 4 * p2 - p3) * t * t + (-p0 + 3 * p1 - 3 * p2 + p3) * t ** 3))
    out.append(P[-2])
    return out


def ribbon_lock(name, ctrl, width, mat, col, centre_axis=(0.0, 0.0), thick=0.006, cup=0.35, nw=6, taper_tip=0.18, root_w=0.75, twist=0.0):
    """A flat, slightly cupped hair clump following ctrl points; faces away from the head axis. Tapers to a soft point."""
    sp = catmull(ctrl, 10)
    bm = bmesh.new(); uvl = bm.loops.layers.uv.new("UVMap")
    rows = []
    N = len(sp)
    for i, p in enumerate(sp):
        t = i / (N - 1)
        tan = (sp[min(N - 1, i + 1)] - sp[max(0, i - 1)]).normalized()
        out = Vector((p.x - centre_axis[0], p.y - centre_axis[1], 0))
        if out.length < 1e-4:
            out = Vector((0, 1, 0))
        out.normalize()
        side = tan.cross(out).normalized()
        nrm = side.cross(tan).normalized()
        if twist:
            side = (side * math.cos(twist * t) + nrm * math.sin(twist * t)).normalized()
            nrm = side.cross(tan).normalized()
        wv = width * (root_w + (1 - root_w) * min(1, t * 4)) * (1 - max(0, (t - (1 - taper_tip * 2.5))) / (taper_tip * 2.5)) ** 0.8 if t > 1 - taper_tip * 2.5 else width * (root_w + (1 - root_w) * min(1, t * 4))
        row = []
        for j in range(nw + 1):
            u = j / nw - 0.5
            row.append(bm.verts.new(p + side * (u * wv) - nrm * (cup * wv * (2 * u) ** 2 * 0.5)))
        rows.append(row)
    for i in range(N - 1):
        for j in range(nw):
            f = bm.faces.new((rows[i][j], rows[i][j + 1], rows[i + 1][j + 1], rows[i + 1][j]))
            for lp, (a, b) in zip(f.loops, ((j, i), (j + 1, i), (j + 1, i + 1), (j, i + 1))):
                lp[uvl].uv = (a / nw, b / (N - 1))
    o = C.obj_from_bm(bm, name, mat, col)
    so = o.modifiers.new("Sol", "SOLIDIFY"); so.thickness = thick; so.offset = 0
    C.add_mod_subsurf(o, 1)
    return o


def clump_hair(prefix, tree, mat, col, h, n=46, length_z=0.80, back_y=0.10, seed=7, front=6, width=(0.045, 0.07), wave=0.02):
    """Layered ribbon clumps: a back curtain + locks over the shoulders. Roots sit on the scalp found by ray casts."""
    rnd = random.Random(seed)
    s = h / 1.617
    out = []
    c0 = Vector((0, -0.02 * s, 1.50 * s))
    for i in range(n + front):
        is_front = i >= n
        if is_front:
            side = 1 if i % 2 else -1
            a = side * rnd.uniform(1.25, 1.75)
        else:
            a = rnd.uniform(-1.9, 1.9) * (0.6 + 0.4 * (i % 3) / 2)
        el = rnd.uniform(0.25, 0.75) if not is_front else rnd.uniform(0.25, 0.5)
        d = Vector((math.sin(a) * math.cos(el), math.cos(a) * math.cos(el), math.sin(el)))
        hit, nrm = surf(tree, c0 + d * 0.4 * s, -d)
        if hit is None:
            continue
        root = hit + nrm * 0.016 * s
        w = rnd.uniform(*width) * s
        endz = (length_z + rnd.uniform(-0.07, 0.05)) * s
        sx = 1 if root.x >= 0 else -1
        if is_front:
            px = sx * rnd.uniform(0.105, 0.135) * s
            ctrl = [root, root + nrm * 0.035 * s + Vector((0, 0, -0.03 * s)), Vector((px * 0.92, -0.035 * s, 1.37 * s)), Vector((px, -0.085 * s, 1.25 * s)),
                    Vector((px * 0.95 + sx * wave * s, -0.10 * s, 1.14 * s)), Vector((px * 0.88, -0.095 * s, max(endz + 0.12 * s, 1.0 * s)))]
            axis = (0.0, -0.02 * s)
        else:
            spread = 1.0 + 0.45 * abs(math.sin(a))
            bx = root.x * spread * 1.15
            by = back_y * s * (0.75 + 0.25 * math.cos(a)) + rnd.uniform(0, 0.02) * s
            ph = rnd.uniform(0, 6.28)
            ctrl = [root, root + nrm * 0.04 * s + Vector((0, 0.01 * s, -0.02 * s)), Vector((bx * 1.05, by * 0.9, 1.40 * s)),
                    Vector((bx * 1.15 + wave * s * math.sin(ph), by, 1.25 * s)),
                    Vector((bx * 1.2 + wave * s * math.sin(ph + 1.8), by + 0.015 * s, (1.25 * s + endz) / 2)),
                    Vector((bx * 1.15 + wave * s * math.sin(ph + 3.2), by + 0.03 * s, endz))]
            axis = (0.0, 0.0)
        out.append(ribbon_lock(f"{prefix}{i}", ctrl, w, mat, col, centre_axis=axis, thick=0.008 * s, twist=rnd.uniform(-0.6, 0.6)))
    return out


def raise_forearm(body, mask, side=1, h=1.617, ang_x=-95.0, ang_z=18.0, shoulder_fwd=12.0):
    """Bend one arm at the elbow (speaking gesture). side=+1 is the +X arm (her left)."""
    V = body.data.vertices
    idx = [i for i in range(len(V)) if mask[i] and V[i].co.x * side > 0]
    s = h / 1.617
    zs = [V[i].co.z for i in idx]
    sh_z = 1.27 * s
    el_z = sh_z - 0.25 * s
    near = [V[i].co for i in idx if abs(V[i].co.z - el_z) < 0.012 * s]
    piv = sum(near, Vector()) / len(near)
    shp = [V[i].co for i in idx if abs(V[i].co.z - (sh_z - 0.02 * s)) < 0.01 * s]
    spv = sum(shp, Vector()) / max(1, len(shp))
    Rf = Matrix.Rotation(math.radians(ang_z * side), 4, "Z") @ Matrix.Rotation(math.radians(ang_x), 4, "X")
    Rs = Matrix.Rotation(math.radians(-shoulder_fwd), 4, "X")
    for i in idx:
        co = V[i].co.copy()
        # whole arm slight forward swing around the shoulder
        ws = max(0.0, min(1.0, (sh_z - co.z) / (0.06 * s)))
        co2 = spv + (Rs @ (co - spv))
        co = co.lerp(co2, ws)
        wf = max(0.0, min(1.0, (el_z + 0.03 * s - V[i].co.z) / (0.06 * s)))
        wf = wf * wf * (3 - 2 * wf)
        piv2 = spv + (Rs @ (piv - spv))
        co3 = piv2 + (Rf @ (co - piv2))
        V[i].co = co.lerp(co3, wf)
    body.data.update()


def hide_covered(body, pred):
    bm = bmesh.new(); bm.from_mesh(body.data); bm.verts.ensure_lookup_table()
    bmesh.ops.delete(bm, geom=[f for f in bm.faces if all(pred(v) for v in f.verts)], context="FACES")
    bm.to_mesh(body.data); bm.free(); body.data.update()


def build_elowen(col):
    h = 1.617
    body, eyes = load_body("female")
    for o in [body] + eyes:
        col.objects.link(o) if o.name not in col.objects else None
        for c in list(o.users_collection):
            if c != col:
                c.objects.unlink(o)
    pose_arms(body, 8.0, h=h)
    mask = arm_mask(body, h)
    orig_z = [v.co.z for v in body.data.vertices]
    raise_forearm(body, mask, side=1, h=h)
    tree = bvh(body)
    skin = skin_mat("FV_SkinElowen", base=(0.95, 0.73, 0.61), lips=(0.80, 0.22, 0.34), blush=(1.0, 0.48, 0.52))
    _sb = skin.node_tree.nodes["Principled BSDF"]; _sb.inputs["Subsurface Scale"].default_value = 0.04; _sb.inputs["Subsurface Weight"].default_value = 0.75
    _sb.inputs["Roughness"].default_value = 0.48; _sb.inputs["Coat Weight"].default_value = 0.12; _sb.inputs["Coat Roughness"].default_value = 0.35
    body.data.materials.append(skin)
    paint_face(body, eyes, Vector((0, -0.149, 1.392)), [Vector((0.052, -0.12, 1.418)), Vector((-0.052, -0.12, 1.418))], mouth_w=0.027, lip_h=0.0095)
    C.add_mod_subsurf(body, 1, render=2)
    finish_eyes(eyes, (0.52, 0.36, 0.95))
    lashes("lash", eyes, C.principled("FV_LashE", (0.06, 0.03, 0.06), rough=0.5), col, h)
    _cl = C.glow_mat("FV_Catchlight", (1.0, 1.0, 1.0), 2.5)
    for _e in eyes:
        _c = _e.matrix_world.translation; _r = max(_e.dimensions) / 2
        _sd = 1 if _c.x > 0 else -1
        _d = Vector((-0.28, -0.92, 0.30)).normalized()
        C.ico(f"catch{_sd}", _r * 0.075, _c + _d * (_r * 1.0), sub=2, mat=_cl, col=col)
        pass  # C.ico(f"catch2{_sd}", _r * 0.06, _c + Vector((0.25, -0.94, -0.22)).normalized() * (_r * 1.0), sub=1, mat=_cl, col=col)
    # ---- gown
    bod = fabric_mat("FV_Bodice", (0.20, 0.17, 0.58), (0.10, 0.08, 0.36), sheen=0.12, rough=0.35, stars=(1.0, 0.85, 0.5), z0=0.95, z1=1.35)
    V = body.data.vertices
    bodice = extract(body, "bodice", lambda v: (0.93 < v.co.z < 1.338) and not mask[v.index], offset=0.009, thick=0.004, mat=bod, col=col)
    sm = bodice.modifiers.new("Smooth", "LAPLACIANSMOOTH"); sm.lambda_factor = 0.6; sm.iterations = 6; sm.use_volume_preserve = True
    bodice.modifiers.move(len(bodice.modifiers) - 1, 0)
    sleeve_m = fabric_mat("FV_Sleeve", (0.30, 0.30, 0.72), (0.40, 0.42, 0.86), sheen=0.6, rough=0.3, alpha=0.82, trans=0.15, sss=0.0)
    sleeves = extract(body, "sleeves", lambda v: mask[v.index] and orig_z[v.index] > 0.885 and orig_z[v.index] < 1.32, offset=0.007, thick=0.003, mat=sleeve_m, col=col)
    gown = fabric_mat("FV_Gown", (0.16, 0.12, 0.50), (0.02, 0.03, 0.16), sheen=0.12, rough=0.38, stars=(1.0, 0.88, 0.55), z0=0.0, z1=0.98)
    sk = skirt("skirt", body, mask, 0.97, 0.01, (0.40, 0.38), gown, col, folds=14, fold_amp=0.03, train=0.16)
    over_m = fabric_mat("FV_Overskirt", (0.36, 0.30, 0.88), (0.22, 0.20, 0.70), sheen=0.3, rough=0.25, alpha=0.2, trans=0.4, sss=0.0)
    ov = skirt("overskirt", body, mask, 0.975, 0.16, (0.42, 0.40), over_m, col, folds=7, fold_amp=0.018, train=0.1,
               hem=lambda a: 0.12 * (0.5 + 0.5 * math.cos(6 * a)) + 0.04 * math.sin(a), thick=0.004)
    gold = C.gold_mat("FV_GoldNPC", (1.0, 0.80, 0.45))
    silver = C.principled("FV_Silver", (0.88, 0.90, 0.96), rough=0.18, metal=1.0)
    x0, x1, y0, y1 = section(body, 0.985, mask)
    belt = ring_curve("belt", 0, (y0 + y1) / 2, (x1 - x0) / 2 + 0.018, (y1 - y0) / 2 + 0.02, 0.985, 0.008, gold, col, tilt=-0.012)
    rnd = random.Random(5)
    lm = C.principled("FV_LeafGold", (0.95, 0.78, 0.40), rough=0.25, metal=0.9)
    for k in range(14):
        a = math.pi * (0.15 + 0.7 * k / 13) + math.pi      # front half (y negative)
        px = ((x1 - x0) / 2 + 0.02) * math.cos(a); py = (y0 + y1) / 2 + ((y1 - y0) / 2 + 0.022) * math.sin(a)
        lf = leaf_shape(f"beltleaf{k}", 0.035, 0.016, lm, col, curl=0.1)
        lf.location = (px, py, 0.985); lf.rotation_euler = (math.radians(90), 0, a + math.pi / 2 + (0.5 if k % 2 else -0.5))
    gem = C.ico("belt_gem", 0.012, (0, y0 - 0.025, 0.985), sub=2, mat=C.glow_mat("FV_MoonGemNPC", (0.6, 0.85, 1.0), 4), col=col)
    cape_m = fabric_mat("FV_Capelet", (0.80, 0.82, 1.0), (0.55, 0.58, 0.95), sheen=1.0, rough=0.3, stars=(0.9, 0.95, 1.0), z0=1.12, z1=1.34, alpha=0.75, trans=0.2, sss=0.0)
    # (capelet dropped: it read as a stiff collar)
    # collar: silver filigree band at the neckline + moonstone pendant
    x0n, x1n, y0n, y1n = section(body, 1.33, mask, tol=0.006)
    ring_curve("collar", 0, (y0n + y1n) / 2, (x1n - x0n) / 2 + 0.012, (y1n - y0n) / 2 + 0.012, 1.325, 0.0045, silver, col, tilt=-0.01)
    C.ico("pendant", 0.008, (0, y0n - 0.016, 1.295), sub=2, mat=C.glow_mat("FV_PendantGem", (0.5, 0.75, 1.0), 1.5), col=col)
    # wrist cuffs (follow the posed arm)
    extract(body, "cuffs", lambda v: mask[v.index] and 0.884 < orig_z[v.index] < 0.902, offset=0.011, thick=0.004, mat=gold, col=col)
    # ---- hair (silver-lavender), cap + locks + bangs
    hm = hair_mat("FV_HairElowen", (0.62, 0.64, 0.86), (0.97, 0.97, 1.0))
    _hb = hm.node_tree.nodes["Principled BSDF"]; _hb.inputs["Roughness"].default_value = 0.24; _hb.inputs["Coat Weight"].default_value = 0.6
    _hb.inputs["Emission Color"].default_value = (0.55, 0.65, 1.0, 1); _hb.inputs["Emission Strength"].default_value = 0.04
    cap = extract(body, "hair_cap", lambda v: (v.co.z > 1.47 and (v.co.y > -0.098 or v.co.z > 1.535)) or (v.co.z > 1.37 and v.co.y > -0.02 and not mask[v.index] and not (abs(v.co.x) > 0.085 and v.co.y < 0.03 and v.co.z < 1.5)),
                  offset=0.009, thick=0.01, mat=hm, col=col, subsurf=2)
    locks = clump_hair("clump", tree, hm, col, h, n=38, length_z=0.80, back_y=0.12, seed=7, front=6, width=(0.06, 0.095), wave=0.04)
    hair_sheet("hair_sheet", hm, col, z_top=1.47, z_bot=0.84, y_off=0.035)
    bangs = []
    for k, sgn in enumerate((-1, 1, -1, 1, -1, 1)):
        off = 0.012 * (k // 2)
        p0 = Vector((sgn * (0.005 + off), -0.06, 1.615))
        pts = [p0]
        for (x, z) in ((0.03 + off, 1.585), (0.065 + off * 0.6, 1.53), (0.088, 1.47), (0.094, 1.41)):
            hit, nrm = surf(tree, (sgn * x, -0.5, z), (0, 1, 0))
            if hit:
                pts.append(hit + nrm * (0.016 + 0.003 * k))
            else:
                pts.append(Vector((sgn * x, -0.12, z)))
        if len(pts) >= 4:
            bangs.append(ribbon_lock(f"bang{k}", pts, 0.032, hm, col, centre_axis=(0.0, 0.0), thick=0.006, cup=0.3, root_w=0.6, taper_tip=0.25))
    brows("brow", eyes, tree, C.principled("FV_BrowE", (0.62, 0.58, 0.72), rough=0.6), col, h, thick=0.0018, lift=0.031, arch=0.005)
    pointed_ear("earL", tree, 1, 1.47, skin, col, length=0.055)
    pointed_ear("earR", tree, -1, 1.47, skin, col, length=0.055)
    # ---- tiara: silver circlet with crescent + moonstone
    ring_curve("circlet", 0, -0.02, 0.112, 0.125, 1.578, 0.0035, silver, col, tilt=-0.026)
    cres = C.torus("tiara_moon", 0.018, 0.004, (0, -0.152, 1.622), mat=silver, col=col, rot=(math.pi / 2, 0, 0))
    bmx = bmesh.new(); bmx.from_mesh(cres.data)
    bmesh.ops.delete(bmx, geom=[v for v in bmx.verts if v.co.z > 0.008 and abs(v.co.x) < 0.012], context="VERTS"); bmx.to_mesh(cres.data); bmx.free()
    C.ico("tiara_gem", 0.009, (0, -0.155, 1.61), sub=2, mat=C.glow_mat("FV_MoonGemNPC", (0.6, 0.85, 1.0), 4), col=col)
    # ---- wings
    wm = wing_mat_iri("FV_WingElowen", alpha=0.24, glow=1.8)
    fairy_wings("wing", col, (0, 0.085, 1.21), wm, span=1.0, sweep=18)
    # ---- floating sparkle motes around her
    for k in range(10):
        a = 2 * math.pi * k / 10
        o = C.ico(f"mote{k}", 0.006, (0.35 * math.cos(a), 0.3 * math.sin(a), 0.4 + 0.11 * k), sub=1, mat=C.glow_mat("FV_Mote", (0.75, 0.9, 1.0), 12), col=col)
        ANIM.append((o, "mote", {"a": a, "z": 0.3 + 0.12 * k, "r": 0.32 + 0.05 * (k % 3)}))
    hide_covered(body, lambda v: (not mask[v.index]) and v.co.z < 1.315)
    return {"height": 1.64, "hover": 0.0, "hero_target_z": 0.98, "hero_dist": 5.6, "portrait_z": 1.43, "portrait_dist": 1.5}


BUILD = {"elowen_moonwhisper": build_elowen}


# ------------------------------------------------------------------ shared NPC helpers (Pip, Thorne, Tumbleroot)
def take_body(col, kind):
    body, eyes = load_body(kind)
    for o in [body] + eyes:
        for c in list(o.users_collection):
            c.objects.unlink(o)
        col.objects.link(o)
    return body, eyes


def warp_point(p, centre, radius, factor, falloff=0.35):
    cen = Vector(centre); d = (p - cen).length
    if d > radius:
        return p.copy(), 1.0
    w = 1.0 if d < radius * (1 - falloff) else (radius - d) / (radius * falloff)
    w = w * w * (3 - 2 * w)
    f = 1 + (factor - 1) * w
    return cen + (p - cen) * f, f


def scale_head(body, eyes, centre, radius, factor):
    region_scale(body, centre, radius, factor)
    for e in eyes:
        np_, f = warp_point(e.location.copy(), centre, radius, factor)
        e.location = np_; e.scale = (f, f, f)


def find_face(tree, eyes):
    ez = sum(e.location.z for e in eyes) / len(eyes)
    es = eyes[0].scale.x
    prof = []
    for k in range(70):
        z = ez - 0.002 * es * k
        hit, _ = surf(tree, (0, -0.8, z), (0, 1, 0))
        if hit:
            prof.append((z, hit.y, hit))
    nose = min(prof[:40], key=lambda t: t[1])
    below = [t for t in prof if t[0] < nose[0] - 0.012 * es]
    # mouth = deepest point (max y) in the first 0.05 m below the nose
    win = [t for t in below if t[0] > nose[0] - 0.06 * es]
    mouth = max(win, key=lambda t: t[1]) if win else below[0]
    return {"eye_z": ez, "nose": nose[2], "mouth": mouth[2]}


def hand_pos(body, mask, side):
    V = body.data.vertices
    idx = [i for i in range(len(V)) if mask[i] and V[i].co.x * side > 0]
    zmin = min(V[i].co.z for i in idx)
    pts = [V[i].co for i in idx if V[i].co.z < zmin + 0.07]
    return sum(pts, Vector()) / len(pts)


def flower_crown(prefix, tree, col, z, cy, rx, ry, n=12, palette=((1.0, 0.55, 0.75), (1.0, 0.9, 0.5), (0.7, 0.6, 1.0)), r=0.016, tilt=-0.02):
    vine = ring_curve(prefix + "_vine", 0, cy, rx, ry, z, 0.003, C.principled("FV_Vine", (0.15, 0.32, 0.08)), col, tilt=tilt)
    for k in range(n):
        a = 2 * math.pi * k / n
        p = (rx * math.cos(a), cy + ry * math.sin(a), z + tilt * math.sin(a))
        C.flower(f"{prefix}{k}", p, r=r, petals=5 + k % 2, c_base=palette[k % len(palette)], c_tip=(1, 0.97, 1), col=col,
                 tilt=0.6, rot=a, glow=palette[k % len(palette)] if k % 3 == 0 else None)


def beard(prefix, tree, mat, col, face, s, n=14, length=0.22, width=0.05, seed=4, bushy=0.0):
    rnd = random.Random(seed)
    m = face["mouth"]
    out = []
    for i in range(n):
        u = (i / (n - 1)) * 2 - 1     # -1..1 across the jaw
        x = u * 0.062 * s
        z = m.z - 0.006 * s + abs(u) ** 1.6 * 0.045 * s
        hit, nrm = surf(tree, (x, -0.8, z), (0, 1, 0))
        if hit is None:
            continue
        root = hit + Vector((0, -0.008 * s, 0))
        L = length * s * (1 - 0.35 * abs(u) ** 2) * rnd.uniform(0.9, 1.1)
        bulge = (0.03 + bushy) * s
        ctrl = [root, root + Vector((x * 0.25, -bulge, -L * 0.25)), root + Vector((x * 0.2, -bulge * 1.15, -L * 0.6)),
                root + Vector((x * 0.05 + rnd.uniform(-0.01, 0.01) * s, -bulge * 0.9, -L))]
        out.append(ribbon_lock(f"{prefix}{i}", ctrl, width * s * rnd.uniform(0.85, 1.15), mat, col, centre_axis=(0.0, 0.1 * s), thick=0.012 * s,
                               cup=0.25, root_w=0.9, taper_tip=0.3, twist=rnd.uniform(-0.4, 0.4)))
    # moustache
    for side in (1, -1):
        r0 = m + Vector((side * 0.006 * s, -0.012 * s, 0.014 * s))
        ctrl = [r0, r0 + Vector((side * 0.025 * s, -0.008 * s, -0.004 * s)), r0 + Vector((side * 0.05 * s, 0.0, -0.02 * s)), r0 + Vector((side * 0.06 * s, 0.01 * s, -0.045 * s))]
        out.append(ribbon_lock(f"{prefix}m{side}", ctrl, 0.03 * s, mat, col, centre_axis=(0.0, 0.0), thick=0.01 * s, cup=0.3, root_w=0.9, taper_tip=0.35))
    return out


def gold_buttons(prefix, tree, col, zs, s, mat):
    for k, z in enumerate(zs):
        hit, nrm = surf(tree, (0, -0.8, z), (0, 1, 0))
        if hit:
            C.uvsphere(f"{prefix}{k}", 0.008 * s, hit + nrm * 0.018 * s, mat=mat, col=col)


def watering_can(name, loc, col):
    cop = C.principled("FV_Copper", (0.85, 0.45, 0.28), rough=0.3, metal=1.0)
    b = C.lathe(name, [(0.001, 0), (0.07, 0.0), (0.075, 0.09), (0.06, 0.13), (0.03, 0.14)], segs=24, mat=cop, col=col, close_bottom=True)
    b.location = loc
    sp = C.tube_curve(name + "_spout", [(loc[0], loc[1] - 0.05, loc[2] + 0.04), (loc[0], loc[1] - 0.13, loc[2] + 0.1), (loc[0], loc[1] - 0.18, loc[2] + 0.16)],
                      radius=0.012, mat=cop, col=col, radii=[1.0, 0.8, 1.3])
    C.torus(name + "_handle", 0.055, 0.008, (loc[0], loc[1] + 0.03, loc[2] + 0.13), mat=cop, col=col, rot=(0, math.pi / 2, 0))
    return b


def setup_skin(body, eyes, tree, skin, iris, face, s, cheeks_dx=0.05):
    body.data.materials.append(skin)
    m = face["mouth"]
    ez = face["eye_z"]
    paint_face(body, eyes, m + Vector((0, 0.002, 0)), [Vector((cheeks_dx * s, m.y + 0.03 * s, (ez + m.z) / 2)), Vector((-cheeks_dx * s, m.y + 0.03 * s, (ez + m.z) / 2))],
               mouth_w=0.024 * s, lip_h=0.008 * s)
    C.add_mod_subsurf(body, 1, render=2)
    finish_eyes(eyes, iris)


# ------------------------------------------------------------------ Pip Dewdrop (child fairy gardener)
def build_pip(col):
    h = 1.617
    body, eyes = take_body(col, "female")
    pose_arms(body, 6.0, h=h)
    mask = arm_mask(body, h)
    orig_z = [v.co.z for v in body.data.vertices]
    scale_head(body, eyes, (0, -0.02, 1.48), 0.22, 1.3)
    tree = bvh(body)
    face = find_face(tree, eyes)
    skin = skin_mat("FV_SkinPip", base=(0.90, 0.68, 0.55), lips=(0.80, 0.38, 0.40), blush=(1.0, 0.50, 0.45))
    setup_skin(body, eyes, tree, skin, (0.28, 0.62, 0.30), face, 1.15)
    tun = fabric_mat("FV_PipTunic", (0.42, 0.68, 0.22), (0.20, 0.44, 0.12), sheen=0.3, rough=0.6, z0=0.6, z1=1.3)
    bod = extract(body, "tunic_top", lambda v: (0.93 < v.co.z < 1.33) and not mask[v.index], offset=0.009, thick=0.004, mat=tun, col=col)
    sm = bod.modifiers.new("Smooth", "LAPLACIANSMOOTH"); sm.lambda_factor = 0.6; sm.iterations = 6; sm.use_volume_preserve = True
    bod.modifiers.move(len(bod.modifiers) - 1, 0)
    extract(body, "puff_sleeves", lambda v: mask[v.index] and orig_z[v.index] > 1.10, offset=0.016, thick=0.004, mat=tun, col=col)
    leafhem = lambda a: 0.06 * (0.5 + 0.5 * math.cos(9 * a))
    skirt("tunic_skirt", body, mask, 0.97, 0.56, (0.27, 0.24), tun, col, folds=9, fold_amp=0.02, hem=leafhem, thick=0.006)
    apron = fabric_mat("FV_PipApron", (0.80, 0.68, 0.48), (0.66, 0.52, 0.34), sheen=0.2, rough=0.8, z0=0.6, z1=1.1)
    ap = skirt("apron", body, mask, 0.99, 0.62, (0.28, 0.26), apron, col, folds=4, fold_amp=0.01, thick=0.004,
               hem=lambda a: 0.0)
    bm = bmesh.new(); bm.from_mesh(ap.data)
    bmesh.ops.delete(bm, geom=[v for v in bm.verts if v.co.y > -0.03], context="VERTS"); bm.to_mesh(ap.data); bm.free()
    ap.location.y -= 0.012
    legs = fabric_mat("FV_PipLegs", (0.36, 0.24, 0.14), (0.30, 0.20, 0.12), sheen=0.2, rough=0.8)
    extract(body, "leggings", lambda v: (not mask[v.index]) and v.co.z < 0.62, offset=0.004, thick=0.003, mat=legs, col=col)
    shoe = C.principled("FV_PipShoe", (0.28, 0.16, 0.08), rough=0.5)
    extract(body, "shoes", lambda v: (not mask[v.index]) and v.co.z < 0.1, offset=0.014, thick=0.004, mat=shoe, col=col)
    # hair: auburn bob
    hm = hair_mat("FV_HairPip", (0.42, 0.14, 0.05), (0.78, 0.36, 0.12))
    ez = face["eye_z"]
    extract(body, "hair_cap", lambda v: (v.co.z > ez + 0.012 and (v.co.y > -0.11 or v.co.z > ez + 0.085)) or (v.co.z > ez - 0.1 and v.co.y > -0.01 and not mask[v.index] and v.co.z > 1.36),
            offset=0.011, thick=0.012, mat=hm, col=col, subsurf=2)
    clump_hair("bob", tree, hm, col, h, n=30, length_z=1.36, back_y=0.11, seed=11, front=4, width=(0.05, 0.07), wave=0.01)
    brows("brow", eyes, tree, C.principled("FV_BrowP", (0.40, 0.16, 0.06), rough=0.6), col, h, thick=0.0022, lift=0.03, arch=0.006)
    pointed_ear("earL", tree, 1, ez, skin, col, length=0.05)
    pointed_ear("earR", tree, -1, ez, skin, col, length=0.05)
    flower_crown("crown", tree, col, ez + 0.09, -0.02, 0.135, 0.15, n=11)
    wm = wing_mat("FV_WingPip", tint=(1.0, 0.82, 0.55), vein=(1.0, 0.65, 0.35), edge=(1.0, 0.45, 0.6), alpha=0.25, glow=1.6)
    fairy_wings("wing", col, (0, 0.085, 1.2), wm, span=0.72, sweep=20)
    hp = hand_pos(body, mask, -1)
    watering_can("can", (hp.x - 0.02, hp.y - 0.02, hp.z - 0.12), col)
    hide_covered(body, lambda v: (not mask[v.index]) and 0.62 < v.co.z < 1.31)
    return {"height": 1.04, "scale": 0.62, "hover": 0.0, "hero_target_z": 0.6, "hero_dist": 3.6, "portrait_z": 0.9, "portrait_dist": 1.0}


# ------------------------------------------------------------------ Warden Thorne Briarwing (fairy elder / guard)
def build_thorne(col):
    h = 1.794; s = h / 1.617
    body, eyes = take_body(col, "male")
    pose_arms(body, 5.0, pivot=(0.17, 1.29), h=h)
    mask = arm_mask(body, h)
    orig_z = [v.co.z for v in body.data.vertices]
    tree = bvh(body)
    face = find_face(tree, eyes)
    skin = skin_mat("FV_SkinThorne", base=(0.74, 0.54, 0.42), lips=(0.55, 0.30, 0.28), blush=(0.80, 0.45, 0.38))
    setup_skin(body, eyes, tree, skin, (0.25, 0.65, 0.55), face, s)
    bark = C.bark_mat("FV_ArmourBark", (0.16, 0.10, 0.06), (0.36, 0.24, 0.13), moss=(0.18, 0.30, 0.08))
    gold = C.gold_mat("FV_GoldNPC", (1.0, 0.80, 0.45))
    cuir = extract(body, "breastplate", lambda v: (1.02 * s < v.co.z < 1.435) and not mask[v.index], offset=0.016, thick=0.012, mat=bark, col=col)
    sm = cuir.modifiers.new("Smooth", "LAPLACIANSMOOTH"); sm.lambda_factor = 0.8; sm.iterations = 8; sm.use_volume_preserve = True
    cuir.modifiers.move(len(cuir.modifiers) - 1, 0)
    sleeve = fabric_mat("FV_ThorneSleeve", (0.16, 0.30, 0.18), (0.12, 0.24, 0.14), sheen=0.3, rough=0.7)
    extract(body, "sleeves", lambda v: mask[v.index] and orig_z[v.index] > 0.98 * s, offset=0.007, thick=0.003, mat=sleeve, col=col)
    extract(body, "bracers", lambda v: mask[v.index] and 0.86 * s < orig_z[v.index] < 1.02 * s, offset=0.014, thick=0.006, mat=bark, col=col)
    tab = fabric_mat("FV_ThorneTabard", (0.12, 0.30, 0.16), (0.07, 0.18, 0.10), sheen=0.3, rough=0.6, stars=(1.0, 0.82, 0.45), z0=0.5, z1=1.1)
    skirt("tabard", body, mask, 1.03 * s, 0.50 * s, (0.30, 0.27), tab, col, folds=8, fold_amp=0.02, thick=0.007,
          hem=lambda a: 0.07 * max(0.0, math.cos(a * 2)) ** 6)
    x0, x1, y0, y1 = section(body, 1.04 * s, mask)
    ring_curve("belt", 0, (y0 + y1) / 2, (x1 - x0) / 2 + 0.026, (y1 - y0) / 2 + 0.03, 1.04 * s, 0.014, C.principled("FV_Leather", (0.22, 0.12, 0.06), rough=0.5), col)
    C.box("buckle", (0.06, 0.012, 0.05), (0, y0 - 0.035, 1.04 * s), gold, col, bevel=0.005)
    trou = fabric_mat("FV_ThorneTrousers", (0.24, 0.20, 0.16), (0.20, 0.17, 0.13), sheen=0.2, rough=0.8)
    extract(body, "trousers", lambda v: (not mask[v.index]) and v.co.z < 1.04 * s, offset=0.006, thick=0.003, mat=trou, col=col)
    boot = C.principled("FV_Boot", (0.20, 0.11, 0.06), rough=0.45, coat=0.2)
    extract(body, "boots", lambda v: (not mask[v.index]) and v.co.z < 0.40 * s, offset=0.016, thick=0.005, mat=boot, col=col)
    # leaf pauldrons
    lm = C.principled("FV_LeafArmour", (0.14, 0.34, 0.12), rough=0.35, coat=0.5, sss=0.1)
    for side in (1, -1):
        for k in range(4):
            lf = leaf_shape(f"paul{side}{k}", 0.16, 0.11, lm if k % 2 == 0 else gold, col, curl=0.35)
            lf.location = (side * (0.19 + 0.012 * k), -0.01 + 0.025 * (k - 1.5), 1.45 - 0.035 * k)
            lf.rotation_euler = (math.radians(-90 + 10 * k), side * math.radians(75), math.radians(90 if side > 0 else -90))
    # hair + beard (white), brows, ears, thorn circlet
    hm = hair_mat("FV_HairThorne", (0.82, 0.82, 0.84), (0.96, 0.96, 0.97))
    ez = face["eye_z"]
    extract(body, "hair_cap", lambda v: (v.co.z > ez + 0.03 and (v.co.y > -0.1 * s or v.co.z > ez + 0.09)) or (v.co.z > ez - 0.12 and v.co.y > -0.01 and not mask[v.index] and v.co.z > 1.48 * s),
            offset=0.01, thick=0.012, mat=hm, col=col, subsurf=2)
    clump_hair("hair", tree, hm, col, h, n=30, length_z=1.28, back_y=0.11, seed=21, front=2, width=(0.05, 0.07), wave=0.012)
    beard("beard", tree, hm, col, face, s, n=13, length=0.24, width=0.05, bushy=0.01)
    brows("brow", eyes, tree, hm, col, h, thick=0.005, lift=0.03, arch=0.003, w=0.034, inner_drop=0.006)
    pointed_ear("earL", tree, 1, ez, skin, col, length=0.06)
    pointed_ear("earR", tree, -1, ez, skin, col, length=0.06)
    bronze = C.principled("FV_Bronze", (0.62, 0.42, 0.22), rough=0.3, metal=1.0)
    ring_curve("circlet", 0, -0.02 * s, 0.112 * s, 0.125 * s, ez + 0.09, 0.004, bronze, col, tilt=-0.02)
    for k in range(9):
        a = math.pi * (1.1 + 0.8 * k / 8)
        C.cyl(f"thorn{k}", 0.006, 0.03, (0.112 * s * math.cos(a), -0.02 * s + 0.125 * s * math.sin(a), ez + 0.1 - 0.02 * math.sin(a)), segs=6, mat=bronze, col=col, r2=0.0005)
    # moonwood spear in his right hand
    hp = hand_pos(body, mask, -1)
    wood = C.wood_mat("FV_Moonwood", (0.75, 0.70, 0.62), (0.9, 0.86, 0.78))
    C.cyl("spear_shaft", 0.017, 2.15, (hp.x, hp.y - 0.01, 1.075), segs=16, mat=wood, col=col)
    C.torus("spear_collar", 0.022, 0.008, (hp.x, hp.y - 0.01, 2.1), mat=gold, col=col)
    blade = C.lathe("spear_blade", [(0.001, 0.0), (0.035, 0.05), (0.04, 0.12), (0.022, 0.22), (0.001, 0.30)], segs=4, mat=C.principled("FV_Crystal", (0.6, 0.9, 1.0), rough=0.05, trans=0.8, emit=(0.4, 0.85, 1.0), emit_strength=2.0), col=col, smooth=False)
    blade.location = (hp.x, hp.y - 0.01, 2.11); blade.scale = (1.0, 0.35, 1.0)
    L = bpy.data.lights.new("bladeL", "POINT"); L.energy = 6; L.color = (0.5, 0.85, 1.0)
    lo = bpy.data.objects.new("bladeL", L); lo.location = (hp.x, hp.y - 0.05, 2.25); col.objects.link(lo)
    wm = wing_mat("FV_WingThorne", tint=(0.72, 0.82, 0.70), vein=(0.55, 0.75, 0.55), edge=(0.9, 0.95, 0.75), alpha=0.32, glow=0.9)
    fairy_wings("wing", col, (0, 0.11, 1.36 * s), wm, span=0.95, sweep=38, droop=18)
    hide_covered(body, lambda v: (not mask[v.index]) and v.co.z < 1.42)
    return {"height": 1.80, "hover": 0.0, "hero_target_z": 1.08, "hero_dist": 6.4, "portrait_z": 1.58, "portrait_dist": 1.6}


# ------------------------------------------------------------------ Tumbleroot the Gnome (potion shopkeeper)
def build_tumbleroot(col):
    h = 1.794
    body, eyes = take_body(col, "male")
    pose_arms(body, 3.0, pivot=(0.17, 1.29), h=h)
    mask = arm_mask(body, h)
    V = body.data.vertices
    cut, k = 0.92, 0.62
    drop = cut * (1 - k)
    for i, v in enumerate(V):
        if mask[i] or v.co.z >= cut:
            v.co.z -= drop
        else:
            v.co.z *= k
    body.data.update()
    for e in eyes:
        e.location.z -= drop
    scale_head(body, eyes, (0, -0.02, 1.62 - drop), 0.27, 1.45)
    region_scale(body, (0, -0.06, 1.08 - drop), 0.25, 1.28)
    orig_z = [v.co.z for v in V]
    tree = bvh(body)
    face = find_face(tree, eyes)
    skin = skin_mat("FV_SkinGnome", base=(0.88, 0.62, 0.48), lips=(0.70, 0.36, 0.34), blush=(1.0, 0.45, 0.40))
    setup_skin(body, eyes, tree, skin, (0.30, 0.45, 0.80), face, 1.4, cheeks_dx=0.07)
    ez = face["eye_z"]
    shirt = fabric_mat("FV_GnomeShirt", (0.90, 0.86, 0.74), (0.82, 0.76, 0.62), sheen=0.3, rough=0.8)
    t_lo, t_hi = 0.95 - drop, 1.48 - drop
    extract(body, "shirt", lambda v: mask[v.index] and v.co.z > 0.98 - drop, offset=0.008, thick=0.003, mat=shirt, col=col)
    vest_m = fabric_mat("FV_GnomeVest", (0.12, 0.40, 0.42), (0.08, 0.30, 0.32), sheen=0.4, rough=0.5)
    vest = extract(body, "vest", lambda v: (t_lo - 0.08 < v.co.z < t_hi) and not mask[v.index], offset=0.012, thick=0.006, mat=vest_m, col=col)
    sm = vest.modifiers.new("Smooth", "LAPLACIANSMOOTH"); sm.lambda_factor = 0.6; sm.iterations = 6; sm.use_volume_preserve = True
    vest.modifiers.move(len(vest.modifiers) - 1, 0)
    trou = fabric_mat("FV_GnomeTrousers", (0.40, 0.26, 0.14), (0.34, 0.22, 0.12), sheen=0.2, rough=0.8)
    extract(body, "trousers", lambda v: (not mask[v.index]) and v.co.z < t_lo - 0.06, offset=0.008, thick=0.003, mat=trou, col=col)
    boot = C.principled("FV_Boot", (0.20, 0.11, 0.06), rough=0.45, coat=0.2)
    extract(body, "boots", lambda v: (not mask[v.index]) and v.co.z < 0.16, offset=0.02, thick=0.006, mat=boot, col=col)
    gold = C.gold_mat("FV_GoldNPC", (1.0, 0.80, 0.45))
    gold_buttons("btn", tree, col, [t_lo + 0.08, t_lo + 0.17, t_lo + 0.26], 1.4, gold)
    # leather apron (front only), with a potion in its pocket
    leather = C.principled("FV_Apron", (0.36, 0.22, 0.12), rough=0.55, coat=0.15)
    ap = extract(body, "apron", lambda v: (not mask[v.index]) and v.co.y < -0.02 and 0.25 < v.co.z < t_lo + 0.12, offset=0.03, thick=0.006, mat=leather, col=col)
    sm = ap.modifiers.new("Smooth", "LAPLACIANSMOOTH"); sm.lambda_factor = 1.0; sm.iterations = 10
    ap.modifiers.move(len(ap.modifiers) - 1, 0)
    # big round nose + spectacles
    n = face["nose"]
    C.uvsphere("nose_bulb", 0.034, n + Vector((0, -0.006, -0.012)), mat=skin, col=col)
    for e in eyes:
        c = e.location
        C.torus(f"spec{e.name[-1]}", 0.032 * e.scale.x, 0.0035, (c.x, c.y - 0.05, c.z), mat=gold, col=col, rot=(math.pi / 2, 0, 0))
    C.tube_curve("spec_bridge", [(-0.012, eyes[0].location.y - 0.055, ez + 0.004), (0, eyes[0].location.y - 0.06, ez + 0.012), (0.012, eyes[0].location.y - 0.055, ez + 0.004)], radius=0.003, mat=gold, col=col)
    hm = hair_mat("FV_HairGnome", (0.86, 0.86, 0.88), (0.97, 0.97, 0.98))
    beard("beard", tree, hm, col, face, 1.45, n=15, length=0.30, width=0.055, bushy=0.02, seed=9)
    brows("brow", eyes, tree, hm, col, h, thick=0.006, lift=0.045, arch=0.006, w=0.045)
    pointed_ear("earL", tree, 1, ez, skin, col, length=0.07)
    pointed_ear("earR", tree, -1, ez, skin, col, length=0.07)
    # side tufts under the hat
    for side in (1, -1):
        for k in range(3):
            r0 = Vector((side * 0.13, 0.0 + 0.03 * k, ez + 0.03))
            ribbon_lock(f"tuft{side}{k}", [r0, r0 + Vector((side * 0.03, 0.02, -0.04)), r0 + Vector((side * 0.045, 0.03, -0.1))], 0.04, hm, col, thick=0.01, root_w=0.9)
    # pointy hat with a droop, brim and a little sprig
    zs = [v.co.z for v in V]; top = max(zs)
    hat = fabric_mat("FV_GnomeHat", (0.52, 0.14, 0.40), (0.36, 0.08, 0.30), sheen=0.6, rough=0.6, stars=(1.0, 0.85, 0.5), z0=top - 0.1, z1=top + 0.5)
    C.tube_curve("hat", [(0, -0.01, top - 0.2), (0, 0.0, top + 0.05), (0.0, 0.03, top + 0.28), (0.05, 0.08, top + 0.40), (0.12, 0.12, top + 0.36)],
                 radius=0.205, mat=hat, col=col, radii=[1.0, 0.72, 0.4, 0.18, 0.05])
    C.torus("hat_brim", 0.2, 0.038, (0, -0.01, top - 0.19), mat=hat, col=col).scale = (1.0, 1.08, 0.6)
    C.flower("hat_flower", (0.14, -0.14, top - 0.14), r=0.04, petals=6, c_base=(1.0, 0.85, 0.3), c_tip=(1, 1, 0.9), col=col, tilt=1.2, glow=(1.0, 0.8, 0.4))
    hp = hand_pos(body, mask, -1)
    glass = C.principled("FV_Glass", (0.9, 0.95, 1.0), rough=0.05, trans=1.0)
    b = C.lathe("potion", [(0.001, 0), (0.04, 0.005), (0.05, 0.05), (0.045, 0.08), (0.016, 0.1), (0.014, 0.13), (0.018, 0.135)], segs=20, mat=glass, col=col, close_bottom=True)
    b.location = (hp.x, hp.y - 0.04, hp.z - 0.06)
    lq = C.lathe("potion_lq", [(0.001, 0.005), (0.043, 0.008), (0.045, 0.05), (0.04, 0.075), (0.001, 0.075)], segs=20, mat=C.glow_mat("FV_PotionG", (0.35, 1.0, 0.45), 3), col=col)
    lq.location = b.location
    hide_covered(body, lambda v: (not mask[v.index]) and v.co.z < t_hi - 0.02)
    return {"height": 0.98, "scale": 0.62, "hover": 0.0, "hero_target_z": 0.55, "hero_dist": 3.4, "portrait_z": 0.84, "portrait_dist": 1.05, "breath": 0.01}


BUILD.update({"pip_dewdrop": build_pip, "warden_thorne": build_thorne, "tumbleroot": build_tumbleroot})


# ------------------------------------------------------------------ animation + render
def set_phase(root, ph, info):
    tw = 2 * math.pi * ph
    for o, kind, p in ANIM:
        if kind == "wing":
            a = p["amp"] * math.sin(2 * tw + (0.6 if p["kind"] == "lower" else 0.0))
            b = p["base"]
            o.rotation_euler = (b.x, b.y, b.z + p["side"] * a)
        elif kind == "mote":
            aa = p["a"] + tw
            o.location = (p["r"] * math.cos(aa), p["r"] * math.sin(aa) * 0.8, p["z"] + 0.03 * math.sin(tw + p["a"]))
        elif kind == "sway":
            b = p["base"]
            o.rotation_euler = (b.x + p["amp"] * math.sin(tw + p.get("off", 0)), b.y, b.z)
    hov = info.get("hover", 0.0)
    root.location.z = hov * (0.5 + 0.5 * math.sin(tw))
    breath = info.get("breath", 0.006)
    root.scale = (1.0, 1.0, 1.0 + breath * math.sin(tw))


def light_rig(sc, hero=False):
    C.world(sc, top=(0.30, 0.34, 0.55), bottom=(0.55, 0.48, 0.42), strength=0.35 if hero else 0.5)
    C.sun(sc, energy=2.4 if hero else 3.2, color=(1.0, 0.88, 0.74), rot=(40, 15, -30), name="Key")
    C.sun(sc, energy=(2.4 if (hero and KEY == "elowen_moonwhisper") else 1.1), color=(0.60, 0.70, 1.0), rot=(60, 0, 160), name="Rim")
    if hero:
        a = bpy.data.lights.new("Fill", "AREA"); a.energy = 45; a.size = 2.0; a.color = (0.85, 0.9, 1.0)
        o = bpy.data.objects.new("Fill", a); o.location = (2.0, -2.5, 1.6); o.rotation_euler = (math.radians(70), 0, math.radians(40)); sc.collection.objects.link(o)
        a2 = bpy.data.lights.new("Kick", "AREA"); a2.energy = 90; a2.size = 1.0; a2.color = (1.0, 0.8, 0.95)
        o2 = bpy.data.objects.new("Kick", a2); o2.location = (-1.4, 1.8, 2.0); o2.rotation_euler = (math.radians(-60), 0, math.radians(-145)); sc.collection.objects.link(o2)


def persp_camera(sc, target, dist, az, el, lens, w, h, name="Cam"):
    cd = bpy.data.cameras.new(name); cd.lens = lens
    cam = bpy.data.objects.new(name, cd); sc.collection.objects.link(cam)
    a, e = math.radians(az), math.radians(el)
    cam.location = Vector(target) + Vector((math.sin(a) * math.cos(e), -math.cos(a) * math.cos(e), math.sin(e))) * dist
    d = Vector(target) - cam.location
    cam.rotation_euler = d.to_track_quat("-Z", "Y").to_euler()
    sc.camera = cam; sc.render.resolution_x = w; sc.render.resolution_y = h
    return cam


def main():
    sc = C.reset()
    col = bpy.data.collections.new(KEY.upper()); sc.collection.children.link(col)
    info = BUILD[KEY](col)
    root = bpy.data.objects.new("NPC_ROOT", None); col.objects.link(root)
    holder = root
    if info.get("scale"):
        holder = bpy.data.objects.new("NPC_SCALE", None); col.objects.link(holder)
        holder.parent = root; holder.scale = (info["scale"],) * 3
    for o in list(col.objects):
        if o.parent is None and o not in (root, holder):
            o.parent = holder
    base = f"{OUT}/renders/npc/{KEY}"
    pv = "_preview" if PREVIEW else ""
    if MODE in ("hero", "all"):
        light_rig(sc, hero=True)
        set_phase(root, 0.15, info)
        C.cycles(sc, samples=32 if PREVIEW else max(SAMPLES, 128), w=2048, h=2048, transparent=True)
        if PREVIEW:
            sc.render.resolution_percentage = 40
        tz = info.get("hero_target_z", 0.95)
        cam = persp_camera(sc, (0, 0, tz), info.get("hero_dist", info["height"] * 3.25), 22, 6, 85, 2048, 2048)
        C.render(sc, f"{base}/hero{pv}.png")
        bpy.data.objects.remove(cam)
    if MODE in ("portrait", "all"):
        if not any(o.name == "Key" for o in sc.objects):
            light_rig(sc, hero=True)
        set_phase(root, 0.15, info)
        C.cycles(sc, samples=32 if PREVIEW else max(SAMPLES, 128), w=1536, h=1536, transparent=True)
        if PREVIEW:
            sc.render.resolution_percentage = 40
        pz = info.get("portrait_z", 1.42)
        cam = persp_camera(sc, (0, -0.02, pz), info.get("portrait_dist", 1.55), 16, 4, 85, 1536, 1536, name="PCam")
        C.render(sc, f"{base}/portrait_bust{pv}.png")
        bpy.data.objects.remove(cam)
    if MODE in ("sprites", "all"):
        for o in list(sc.objects):
            if o.type == "LIGHT" and o.name in ("Fill", "Kick"):
                bpy.data.objects.remove(o)
        for o in list(sc.objects):
            if o.type == "LIGHT" and o.data.type == "SUN":
                bpy.data.objects.remove(o)
        light_rig(sc, hero=False)
        cat = C.shadow_catcher("catcher", 6, (0, 0, 0), col)
        cam, ppm = sprite_camera(sc, h_px=175.6, height_m=1.0)   # constant 175.6 px/m at 4x for every NPC
        C.cycles(sc, samples=24 if PREVIEW else SAMPLES, w=384, h=512, transparent=True)
        rots = {"s": 0, "e": 90, "n": 180, "w": -90}
        for f in FACINGS:
            root.rotation_euler = (0, 0, math.radians(rots[f]))
            frames = [0] if PREVIEW else range(FRAMES)
            for k in frames:
                set_phase(root, k / FRAMES, info)
                C.render(sc, f"{base}/sprite_4x{pv}/{f}/f{k:02d}.png")
    print("DONE", KEY, flush=True)


main()
