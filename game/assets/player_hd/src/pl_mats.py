"""Detailed procedural materials: cloth weave + folds, leather grain, tintable metal (AOV 'tint'), skin, hair, stitching."""
import bpy, math
import fv_common as C

TINT_AOV = "tint"


def _nt(name):
    m = bpy.data.materials.get(name)
    if m:
        return m, None
    m = bpy.data.materials.new(name); m.use_nodes = True
    return m, m.node_tree


def _aov(nt, val):
    o = nt.nodes.new("ShaderNodeOutputAOV"); o.aov_name = TINT_AOV
    o.inputs["Value"].default_value = val
    return o


def _n(nt, t, **kw):
    n = nt.nodes.new(t)
    for k, v in kw.items():
        if k in n.inputs:
            n.inputs[k].default_value = v
        else:
            setattr(n, k, v)
    return n


def _L(nt, a, b):
    nt.links.new(a, b)


def cloth(name, color, kind="linen", color2=None, tint=0.0, scale=1.0):
    """kind: linen | wool | knit | velvet | leather | suede | silk | canvas | fur"""
    m, nt = _nt(name)
    if nt is None:
        return m
    b = nt.nodes["Principled BSDF"]
    P = dict(linen=(0.85, 0.25, 520, 0.012, 0.30), wool=(0.92, 0.55, 300, 0.018, 0.45), knit=(0.95, 0.6, 140, 0.03, 0.4),
             velvet=(0.65, 1.0, 700, 0.006, 0.35), leather=(0.48, 0.0, 0, 0.0, 0.5), suede=(0.9, 0.3, 0, 0.0, 0.5),
             silk=(0.32, 0.35, 900, 0.004, 0.25), canvas=(0.88, 0.2, 380, 0.016, 0.35), fur=(0.95, 0.8, 0, 0.0, 0.6))[kind]
    rough, sheen, weave_sc, weave_amt, fold_amt = P
    tc = _n(nt, "ShaderNodeTexCoord")
    # colour variation (dye unevenness / wear) + optional second colour along height
    nz = _n(nt, "ShaderNodeTexNoise", Scale=9.0 * scale, Detail=6.0, Roughness=0.55)
    _L(nt, tc.outputs["Object"], nz.inputs["Vector"])
    base = _n(nt, "ShaderNodeRGB"); base.outputs[0].default_value = (*color, 1)
    mul = _n(nt, "ShaderNodeMix", data_type="RGBA", blend_type="OVERLAY"); mul.inputs["Factor"].default_value = 0.22
    _L(nt, base.outputs[0], mul.inputs["A"]); _L(nt, nz.outputs["Color"], mul.inputs["B"])
    col_out = mul.outputs["Result"]
    height = None
    bumpsum = None
    if weave_sc:
        acc = None
        for ax in ("X", "Y", "Z"):
            w = _n(nt, "ShaderNodeTexWave", wave_type="BANDS", bands_direction=ax)
            w.inputs["Scale"].default_value = weave_sc * scale; w.inputs["Distortion"].default_value = 0.6
            _L(nt, tc.outputs["Object"], w.inputs["Vector"])
            if acc is None:
                acc = w.outputs["Fac"]
            else:
                ad = _n(nt, "ShaderNodeMath", operation="MULTIPLY"); _L(nt, acc, ad.inputs[0]); _L(nt, w.outputs["Fac"], ad.inputs[1]); acc = ad.outputs[0]
        weave = acc
        # weave darkens colour slightly in the gaps
        wm = _n(nt, "ShaderNodeMix", data_type="RGBA", blend_type="MULTIPLY"); wm.inputs["Factor"].default_value = 0.18
        _L(nt, col_out, wm.inputs["A"]); _L(nt, weave, wm.inputs["B"]); col_out = wm.outputs["Result"]
        bw = _n(nt, "ShaderNodeBump", Strength=weave_amt * 8, Distance=0.0006)
        _L(nt, weave, bw.inputs["Height"]); bumpsum = bw
    if kind in ("leather", "suede"):
        vo = _n(nt, "ShaderNodeTexVoronoi"); vo.inputs["Scale"].default_value = 260 * scale
        _L(nt, tc.outputs["Object"], vo.inputs["Vector"])
        bw = _n(nt, "ShaderNodeBump", Strength=0.35 if kind == "leather" else 0.15, Distance=0.0008, invert=True)
        _L(nt, vo.outputs["Distance"], bw.inputs["Height"]); bumpsum = bw
        wear = _n(nt, "ShaderNodeTexNoise", Scale=4.0, Detail=8.0); _L(nt, tc.outputs["Object"], wear.inputs["Vector"])
        cr = _n(nt, "ShaderNodeValToRGB"); cr.color_ramp.elements[0].position = 0.45; cr.color_ramp.elements[1].position = 0.75
        _L(nt, wear.outputs["Fac"], cr.inputs["Fac"])
        lm = _n(nt, "ShaderNodeMix", data_type="RGBA"); lm.inputs["Factor"].default_value = 0.3
        _L(nt, cr.outputs["Color"], lm.inputs["Factor"]); _L(nt, col_out, lm.inputs["A"])
        lm.inputs["B"].default_value = (*(c * 1.45 for c in color), 1)
        col_out = lm.outputs["Result"]
        b.inputs["Coat Weight"].default_value = 0.25 if kind == "leather" else 0.0
        b.inputs["Coat Roughness"].default_value = 0.35
    if kind == "fur":
        fz = _n(nt, "ShaderNodeTexNoise", Scale=900.0, Detail=2.0); _L(nt, tc.outputs["Object"], fz.inputs["Vector"])
        bw = _n(nt, "ShaderNodeBump", Strength=0.8, Distance=0.002); _L(nt, fz.outputs["Fac"], bw.inputs["Height"]); bumpsum = bw
    # large soft folds (creases run roughly horizontal on limbs / vertical on skirts)
    if fold_amt:
        # soft creases: stretched low-frequency noise (no regular banding)
        fm = _n(nt, "ShaderNodeMapping"); fm.inputs["Scale"].default_value = (1.0, 1.0, 3.2)
        _L(nt, tc.outputs["Object"], fm.inputs["Vector"])
        fw = _n(nt, "ShaderNodeTexNoise", Scale=7.0 * scale, Detail=3.0, Roughness=0.5)
        fw.inputs["Distortion"].default_value = 0.4
        _L(nt, fm.outputs["Vector"], fw.inputs["Vector"])
        fb = _n(nt, "ShaderNodeBump", Strength=fold_amt * 0.45, Distance=0.01)
        _L(nt, fw.outputs["Fac"], fb.inputs["Height"])
        if bumpsum is not None:
            _L(nt, bumpsum.outputs["Normal"], fb.inputs["Normal"])
        bumpsum = fb
    if color2 is not None:
        sep = _n(nt, "ShaderNodeSeparateXYZ"); _L(nt, tc.outputs["Object"], sep.inputs[0])
        mr = _n(nt, "ShaderNodeMapRange"); mr.inputs["From Min"].default_value = 0.3; mr.inputs["From Max"].default_value = 1.4
        _L(nt, sep.outputs["Z"], mr.inputs["Value"])
        g = _n(nt, "ShaderNodeMix", data_type="RGBA"); _L(nt, mr.outputs["Result"], g.inputs["Factor"])
        g.inputs["A"].default_value = (*color2, 1); _L(nt, col_out, g.inputs["B"]); col_out = g.outputs["Result"]
    col_out = edge_wear(nt, col_out, b, amt=0.10, ao=True, ao_dist=0.025)
    _L(nt, col_out, b.inputs["Base Color"])
    if bumpsum is not None:
        _L(nt, bumpsum.outputs["Normal"], b.inputs["Normal"])
    b.inputs["Roughness"].default_value = rough
    b.inputs["Sheen Weight"].default_value = sheen
    b.inputs["Sheen Roughness"].default_value = 0.4
    b.inputs["Specular IOR Level"].default_value = 0.35
    _aov(nt, tint)
    return m


def metal(name, base=(0.66, 0.66, 0.68), rough=0.26, tint=1.0, hammered=0.25):
    """Neutral steel; runtime multiplies the tint-mask region by the tier colour (bronze/iron/steel/mithril/adamant/rune...)."""
    m, nt = _nt(name)
    if nt is None:
        return m
    b = nt.nodes["Principled BSDF"]
    tc = _n(nt, "ShaderNodeTexCoord")
    bc = _n(nt, "ShaderNodeRGB"); bc.outputs[0].default_value = (*base, 1)
    _L(nt, edge_wear(nt, bc.outputs[0], b, amt=0.45, ao=True, ao_dist=0.02), b.inputs["Base Color"])
    b.inputs["Metallic"].default_value = 1.0
    sc = _n(nt, "ShaderNodeTexNoise", Scale=60.0, Detail=10.0, Roughness=0.7); _L(nt, tc.outputs["Object"], sc.inputs["Vector"])
    mp = _n(nt, "ShaderNodeMapRange"); mp.inputs["To Min"].default_value = rough * 0.6; mp.inputs["To Max"].default_value = rough * 1.6
    _L(nt, sc.outputs["Fac"], mp.inputs["Value"]); _L(nt, mp.outputs["Result"], b.inputs["Roughness"])
    # fine scratches: highly stretched noise
    mpg = _n(nt, "ShaderNodeMapping"); mpg.inputs["Scale"].default_value = (1.0, 1.0, 40.0)
    _L(nt, tc.outputs["Object"], mpg.inputs["Vector"])
    scr = _n(nt, "ShaderNodeTexNoise", Scale=180.0, Detail=4.0); _L(nt, mpg.outputs["Vector"], scr.inputs["Vector"])
    vo = _n(nt, "ShaderNodeTexVoronoi"); vo.inputs["Scale"].default_value = 90.0; _L(nt, tc.outputs["Object"], vo.inputs["Vector"])
    hm = _n(nt, "ShaderNodeMath", operation="ADD"); _L(nt, scr.outputs["Fac"], hm.inputs[0]); _L(nt, vo.outputs["Distance"], hm.inputs[1])
    bp = _n(nt, "ShaderNodeBump", Strength=hammered, Distance=0.0015); _L(nt, hm.outputs[0], bp.inputs["Height"])
    _L(nt, bp.outputs["Normal"], b.inputs["Normal"])
    b.inputs["Anisotropic"].default_value = 0.3
    _aov(nt, tint)
    return m


def gold(name, tint=0.0):
    m = metal(name, base=(0.95, 0.72, 0.32), rough=0.22, tint=tint, hammered=0.12)
    return m


def wood(name, c1=(0.30, 0.17, 0.08), c2=(0.55, 0.36, 0.19)):
    m = C.wood_mat(name, c1, c2)
    if m.node_tree and not any(n.type == "OUTPUT_AOV" for n in m.node_tree.nodes):
        _aov(m.node_tree, 0.0)
    return m


def stitch(name, color=(0.85, 0.80, 0.65), dash=55.0, tint=0.0):
    """Dashed thread for hem/seam tubes (UV.x runs along the tube length)."""
    m, nt = _nt(name)
    if nt is None:
        return m
    b = nt.nodes["Principled BSDF"]
    b.inputs["Base Color"].default_value = (*color, 1); b.inputs["Roughness"].default_value = 0.7
    tc = _n(nt, "ShaderNodeTexCoord"); sep = _n(nt, "ShaderNodeSeparateXYZ"); _L(nt, tc.outputs["UV"], sep.inputs[0])
    mul = _n(nt, "ShaderNodeMath", operation="MULTIPLY"); mul.inputs[1].default_value = dash; _L(nt, sep.outputs["X"], mul.inputs[0])
    fr = _n(nt, "ShaderNodeMath", operation="FRACT"); _L(nt, mul.outputs[0], fr.inputs[0])
    gt = _n(nt, "ShaderNodeMath", operation="LESS_THAN"); gt.inputs[1].default_value = 0.6; _L(nt, fr.outputs[0], gt.inputs[0])
    tr = _n(nt, "ShaderNodeBsdfTransparent")
    mx = _n(nt, "ShaderNodeMixShader"); _L(nt, gt.outputs[0], mx.inputs["Fac"]); _L(nt, tr.outputs[0], mx.inputs[1]); _L(nt, b.outputs[0], mx.inputs[2])
    out = nt.nodes["Material Output"]; _L(nt, mx.outputs[0], out.inputs["Surface"])
    _aov(nt, tint)
    return m


def hair_grey(name, shade=0.78):
    """Principled Hair BSDF, neutral grey (runtime colour multiply)."""
    m, nt = _nt(name)
    if nt is None:
        return m
    out = nt.nodes["Material Output"]
    for n in list(nt.nodes):
        if n.type == "BSDF_PRINCIPLED":
            nt.nodes.remove(n)
    hb = nt.nodes.new("ShaderNodeBsdfHairPrincipled")
    try:
        hb.parametrization = "COLOR"
    except Exception:
        pass
    hb.inputs["Color"].default_value = (shade, shade, shade, 1)
    hb.inputs["Roughness"].default_value = 0.32
    hb.inputs["Radial Roughness"].default_value = 0.45
    hb.inputs["Coat"].default_value = 0.1
    hb.inputs["Random Roughness"].default_value = 0.3
    rnd = nt.nodes.new("ShaderNodeHairInfo")
    ramp = nt.nodes.new("ShaderNodeValToRGB")
    ramp.color_ramp.elements[0].color = (shade * 0.72, shade * 0.72, shade * 0.72, 1)
    ramp.color_ramp.elements[1].color = (shade * 1.08, shade * 1.08, shade * 1.08, 1)
    _L(nt, rnd.outputs["Random"], ramp.inputs["Fac"])
    # root-to-tip value: darker roots, sun-lightened tips (reads as depth instead of a flat helmet)
    rt = nt.nodes.new("ShaderNodeValToRGB"); e = rt.color_ramp.elements
    e[0].position = 0.0; e[0].color = (0.62, 0.62, 0.62, 1); e[1].position = 1.0; e[1].color = (1.12, 1.12, 1.12, 1)
    mid = e.new(0.35); mid.color = (0.92, 0.92, 0.92, 1)
    _L(nt, rnd.outputs["Intercept"], rt.inputs["Fac"])
    mm = nt.nodes.new("ShaderNodeMix"); mm.data_type = "RGBA"; mm.blend_type = "MULTIPLY"; mm.inputs["Factor"].default_value = 1.0
    _L(nt, ramp.outputs["Color"], mm.inputs[6]); _L(nt, rt.outputs["Color"], mm.inputs[7])
    _L(nt, mm.outputs[2], hb.inputs["Color"])
    _L(nt, hb.outputs[0], out.inputs["Surface"])
    _aov(nt, 1.0)
    return m


def gem(name, color=(0.25, 0.55, 1.0)):
    m, nt = _nt(name)
    if nt is None:
        return m
    b = nt.nodes["Principled BSDF"]
    b.inputs["Base Color"].default_value = (*color, 1); b.inputs["Roughness"].default_value = 0.05
    b.inputs["Transmission Weight"].default_value = 0.6; b.inputs["Coat Weight"].default_value = 1.0
    b.inputs["Emission Color"].default_value = (*color, 1); b.inputs["Emission Strength"].default_value = 1.2
    _aov(nt, 0.0)
    return m


def edge_wear(nt, col_sock, b, amt=0.35, ao=True, ao_dist=0.03):
    """Edge highlight (pointiness) + local AO cavity darkening -> seams, folds, bevels read at small sizes."""
    geo = _n(nt, "ShaderNodeNewGeometry")
    mr = _n(nt, "ShaderNodeMapRange"); mr.inputs["From Min"].default_value = 0.52; mr.inputs["From Max"].default_value = 0.62
    _L(nt, geo.outputs["Pointiness"], mr.inputs["Value"])
    hi = _n(nt, "ShaderNodeMix", data_type="RGBA", blend_type="SCREEN"); _L(nt, mr.outputs["Result"], hi.inputs["Factor"])
    hi.inputs["B"].default_value = (amt, amt, amt, 1); _L(nt, col_sock, hi.inputs["A"])
    out = hi.outputs["Result"]
    if ao:
        a = _n(nt, "ShaderNodeAmbientOcclusion"); a.inputs["Distance"].default_value = ao_dist; a.only_local = True; a.samples = 8
        am = _n(nt, "ShaderNodeMapRange"); am.inputs["To Min"].default_value = 0.45; _L(nt, a.outputs["AO"], am.inputs["Value"])
        mm = _n(nt, "ShaderNodeMix", data_type="RGBA", blend_type="MULTIPLY"); mm.inputs["Factor"].default_value = 1.0
        _L(nt, out, mm.inputs["A"]); _L(nt, am.outputs["Result"], mm.inputs["B"]); out = mm.outputs["Result"]
    return out


def scalp_grey(name, shade=0.42):
    m = C.principled(name, (shade, shade, shade), rough=0.6)
    _aov(m.node_tree, 1.0)
    return m


def setup_aov(sc):
    vl = sc.view_layers[0]
    if not any(a.name == TINT_AOV for a in vl.aovs):
        a = vl.aovs.add(); a.name = TINT_AOV; a.type = "VALUE"
