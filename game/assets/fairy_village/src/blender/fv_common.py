"""Shared Blender helpers for the Fairy Village pack (Cycles, consistent lighting, game camera)."""
import bpy, bmesh, math, os, random, json
from mathutils import Vector, Euler, Matrix, noise

GAME_PX_PER_M = 26.9                 # Mythoscape buildings pack: TILE 40 px ~ 1.487 m
T = 40.0 / GAME_PX_PER_M             # metres per tile
EL = math.radians(32.0)              # game elevation (buildings pack)
SIN, COS = math.sin(EL), math.cos(EL)
ZEX = 1.4                            # buildings pack sprite height exaggeration
PPT_HD = 160                         # 4x master (1x = 40 px / tile)

ARGS = []
import sys
if "--" in sys.argv:
    ARGS = sys.argv[sys.argv.index("--") + 1:]


def arg(name, default=None):
    if name in ARGS:
        i = ARGS.index(name)
        return ARGS[i + 1] if i + 1 < len(ARGS) and not ARGS[i + 1].startswith("--") else True
    return default


def reset():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    sc = bpy.context.scene
    sc.unit_settings.system = "METRIC"
    return sc


def cycles(sc, samples=96, w=1024, h=1024, transparent=True, denoise=True):
    sc.render.engine = "CYCLES"
    sc.cycles.device = "CPU"
    sc.cycles.samples = samples
    sc.cycles.use_adaptive_sampling = True
    sc.cycles.adaptive_threshold = 0.02
    sc.cycles.use_denoising = denoise
    try:
        sc.cycles.denoiser = "OPENIMAGEDENOISE"
    except Exception:
        pass
    sc.cycles.max_bounces = 8
    sc.cycles.transparent_max_bounces = 16
    sc.cycles.transmission_bounces = 8
    sc.cycles.caustics_reflective = False
    sc.cycles.caustics_refractive = False
    sc.cycles.blur_glossy = 1.0
    sc.render.resolution_x, sc.render.resolution_y = w, h
    sc.render.resolution_percentage = 100
    sc.render.film_transparent = transparent
    sc.render.image_settings.file_format = "PNG"
    sc.render.image_settings.color_mode = "RGBA"
    sc.render.image_settings.color_depth = "8"
    sc.view_settings.view_transform = "AgX"
    try:
        sc.view_settings.look = "AgX - Medium High Contrast"
    except Exception:
        pass
    sc.view_settings.exposure = 0.0
    sc.render.threads_mode = "AUTO"


def world(sc, top=(0.42, 0.50, 0.78), bottom=(0.95, 0.80, 0.62), strength=0.55):
    w = bpy.data.worlds.new("FV_World"); w.use_nodes = True
    nt = w.node_tree; n = nt.nodes; l = nt.links
    n.clear()
    out = n.new("ShaderNodeOutputWorld")
    bg = n.new("ShaderNodeBackground"); bg.inputs["Strength"].default_value = strength
    tc = n.new("ShaderNodeTexCoord"); sep = n.new("ShaderNodeSeparateXYZ")
    ramp = n.new("ShaderNodeValToRGB")
    ramp.color_ramp.elements[0].position = 0.35; ramp.color_ramp.elements[0].color = (*bottom, 1)
    ramp.color_ramp.elements[1].position = 0.75; ramp.color_ramp.elements[1].color = (*top, 1)
    mr = n.new("ShaderNodeMapRange"); mr.inputs["From Min"].default_value = -1; mr.inputs["From Max"].default_value = 1
    l.new(tc.outputs["Generated"], sep.inputs[0])
    l.new(sep.outputs["Z"], mr.inputs["Value"]); l.new(mr.outputs["Result"], ramp.inputs["Fac"])
    l.new(ramp.outputs["Color"], bg.inputs["Color"]); l.new(bg.outputs[0], out.inputs[0])
    sc.world = w
    return w


def sun(sc, energy=4.2, color=(1.0, 0.86, 0.68), rot=(40, 15, -30), angle=2.5, name="Key"):
    d = bpy.data.lights.new(name, "SUN"); d.energy = energy; d.color = color
    d.angle = math.radians(angle)
    o = bpy.data.objects.new(name, d); o.rotation_euler = Euler([math.radians(a) for a in rot], "XYZ")
    sc.collection.objects.link(o)
    return o


def rig(sc):
    """Standard Fairy Village light rig: warm late-afternoon key + cool magical rim."""
    world(sc)
    sun(sc)
    sun(sc, energy=0.9, color=(0.62, 0.70, 1.0), rot=(55, -20, 150), angle=8, name="Rim")


# ----------------------------------------------------------------- materials
def _mat(name):
    m = bpy.data.materials.get(name)
    if m:
        return m, None
    m = bpy.data.materials.new(name); m.use_nodes = True
    return m, m.node_tree


def principled(name, color, rough=0.6, metal=0.0, emit=None, emit_strength=0.0, sss=0.0, trans=0.0, alpha=1.0,
               spec=0.5, coat=0.0, sheen=0.0):
    m, nt = _mat(name)
    if nt is None:
        return m
    b = nt.nodes["Principled BSDF"]
    b.inputs["Base Color"].default_value = (*color, 1)
    b.inputs["Roughness"].default_value = rough
    b.inputs["Metallic"].default_value = metal
    b.inputs["Specular IOR Level"].default_value = spec
    if emit:
        b.inputs["Emission Color"].default_value = (*emit, 1)
        b.inputs["Emission Strength"].default_value = emit_strength
    if sss:
        b.inputs["Subsurface Weight"].default_value = sss
        b.inputs["Subsurface Radius"].default_value = (1.0, 0.45, 0.25)
        b.inputs["Subsurface Scale"].default_value = 0.05
    if trans:
        b.inputs["Transmission Weight"].default_value = trans
    if coat:
        b.inputs["Coat Weight"].default_value = coat
    if sheen:
        b.inputs["Sheen Weight"].default_value = sheen
    if alpha < 1:
        b.inputs["Alpha"].default_value = alpha
    return m


def node_mat(name):
    m, nt = _mat(name)
    return m, nt


def link(nt, a, b):
    nt.links.new(a, b)


def bark_mat(name="FV_Bark", c1=(0.20, 0.12, 0.07), c2=(0.42, 0.29, 0.18), moss=(0.20, 0.36, 0.09), scale=1.0):
    m, nt = node_mat(name)
    if nt is None:
        return m
    n = nt.nodes; b = n["Principled BSDF"]
    tc = n.new("ShaderNodeTexCoord")
    mp = n.new("ShaderNodeMapping"); mp.inputs["Scale"].default_value = (1.4 * scale, 1.4 * scale, 0.35 * scale)
    link(nt, tc.outputs["Object"], mp.inputs["Vector"])
    nz = n.new("ShaderNodeTexNoise"); nz.inputs["Scale"].default_value = 3.0; nz.inputs["Detail"].default_value = 8
    nz.inputs["Distortion"].default_value = 0.6
    link(nt, mp.outputs[0], nz.inputs["Vector"])
    wv = n.new("ShaderNodeTexWave"); wv.wave_type = "BANDS"; wv.bands_direction = "X"
    wv.inputs["Scale"].default_value = 3.5; wv.inputs["Distortion"].default_value = 9.0
    wv.inputs["Detail"].default_value = 6; wv.inputs["Detail Scale"].default_value = 1.5
    link(nt, mp.outputs[0], wv.inputs["Vector"])
    mix = n.new("ShaderNodeMath"); mix.operation = "MULTIPLY"
    link(nt, wv.outputs["Fac"], mix.inputs[0]); link(nt, nz.outputs["Fac"], mix.inputs[1])
    ramp = n.new("ShaderNodeValToRGB")
    ramp.color_ramp.elements[0].color = (*c1, 1); ramp.color_ramp.elements[1].color = (*c2, 1)
    ramp.color_ramp.elements[0].position = 0.08; ramp.color_ramp.elements[1].position = 0.55
    link(nt, mix.outputs[0], ramp.inputs["Fac"])
    # moss on up-facing surfaces
    geo = n.new("ShaderNodeNewGeometry"); sep = n.new("ShaderNodeSeparateXYZ")
    link(nt, geo.outputs["Normal"], sep.inputs[0])
    mn = n.new("ShaderNodeTexNoise"); mn.inputs["Scale"].default_value = 6; mn.inputs["Detail"].default_value = 6
    link(nt, mp.outputs[0], mn.inputs["Vector"])
    add = n.new("ShaderNodeMath"); add.operation = "ADD"
    link(nt, sep.outputs["Z"], add.inputs[0]); link(nt, mn.outputs["Fac"], add.inputs[1])
    mr = n.new("ShaderNodeMapRange"); mr.inputs["From Min"].default_value = 1.18; mr.inputs["From Max"].default_value = 1.38
    link(nt, add.outputs[0], mr.inputs["Value"])
    mixc = n.new("ShaderNodeMix"); mixc.data_type = "RGBA"
    link(nt, mr.outputs[0], mixc.inputs["Factor"]); link(nt, ramp.outputs[0], mixc.inputs[6])
    mixc.inputs[7].default_value = (*moss, 1)
    link(nt, mixc.outputs[2], b.inputs["Base Color"])
    b.inputs["Roughness"].default_value = 0.85
    bump = n.new("ShaderNodeBump"); bump.inputs["Strength"].default_value = 1.0; bump.inputs["Distance"].default_value = 0.12
    link(nt, mix.outputs[0], bump.inputs["Height"]); link(nt, bump.outputs[0], b.inputs["Normal"])
    return m


def leafcard_mat(name="FV_LeafCard", greens=((0.07, 0.24, 0.05), (0.22, 0.48, 0.09), (0.50, 0.68, 0.18)), sss=0.35):
    """Per-instance colour variation (Object Info random) + vein bump + translucency."""
    m, nt = node_mat(name)
    if nt is None:
        return m
    n = nt.nodes; b = n["Principled BSDF"]
    oi = n.new("ShaderNodeObjectInfo")
    ramp = n.new("ShaderNodeValToRGB")
    ramp.color_ramp.elements[0].color = (*greens[0], 1); ramp.color_ramp.elements[1].color = (*greens[2], 1)
    e = ramp.color_ramp.elements.new(0.5); e.color = (*greens[1], 1)
    tc = n.new("ShaderNodeTexCoord"); sep = n.new("ShaderNodeSeparateXYZ"); link(nt, tc.outputs["UV"], sep.inputs[0])
    mix = n.new("ShaderNodeMath"); mix.operation = "MULTIPLY_ADD"; mix.inputs[1].default_value = 0.35
    link(nt, sep.outputs["Y"], mix.inputs[0]); link(nt, oi.outputs["Random"], mix.inputs[2])
    link(nt, mix.outputs[0], ramp.inputs["Fac"])
    # patchy hue variation by instance location (moon-silver / golden patches) + AO darkening in the canopy gaps
    nz = n.new("ShaderNodeTexNoise"); nz.inputs["Scale"].default_value = 0.35; nz.inputs["Detail"].default_value = 2
    link(nt, oi.outputs["Location"], nz.inputs[0])
    pr = n.new("ShaderNodeValToRGB")
    pr.color_ramp.elements[0].position = 0.3; pr.color_ramp.elements[0].color = (0.16, 0.42, 0.36, 1)
    pr.color_ramp.elements[1].position = 0.7; pr.color_ramp.elements[1].color = (0.62, 0.62, 0.16, 1)
    e2 = pr.color_ramp.elements.new(0.5); e2.color = (0.5, 0.5, 0.5, 1)
    link(nt, nz.outputs["Fac"], pr.inputs[0])
    ov = n.new("ShaderNodeMix"); ov.data_type = "RGBA"; ov.blend_type = "OVERLAY"; ov.inputs["Factor"].default_value = 0.55
    link(nt, ramp.outputs[0], ov.inputs[6]); link(nt, pr.outputs[0], ov.inputs[7])
    ao = n.new("ShaderNodeAmbientOcclusion"); ao.inputs["Distance"].default_value = 0.9; ao.samples = 8
    aor = n.new("ShaderNodeMapRange"); aor.inputs["To Min"].default_value = 0.25
    link(nt, ao.outputs["AO"], aor.inputs["Value"])
    mul = n.new("ShaderNodeMix"); mul.data_type = "RGBA"; mul.blend_type = "MULTIPLY"; mul.inputs["Factor"].default_value = 1.0
    link(nt, ov.outputs[2], mul.inputs[6]); link(nt, aor.outputs[0], mul.inputs[7])
    link(nt, mul.outputs[2], b.inputs["Base Color"])
    b.inputs["Roughness"].default_value = 0.5
    b.inputs["Subsurface Weight"].default_value = sss
    b.inputs["Subsurface Radius"].default_value = (0.5, 1.0, 0.2)
    b.inputs["Subsurface Scale"].default_value = 0.05
    b.inputs["Sheen Weight"].default_value = 0.5
    b.inputs["Coat Weight"].default_value = 0.15
    wv = n.new("ShaderNodeTexWave"); wv.bands_direction = "X"; wv.inputs["Scale"].default_value = 3
    link(nt, tc.outputs["UV"], wv.inputs[0])
    bump = n.new("ShaderNodeBump"); bump.inputs["Strength"].default_value = 0.3
    link(nt, wv.outputs["Fac"], bump.inputs["Height"]); link(nt, bump.outputs[0], b.inputs["Normal"])
    return m


def stone_mat(name="FV_Moonstone", c1=(0.50, 0.50, 0.55), c2=(0.74, 0.73, 0.77), moss=(0.24, 0.40, 0.12),
              moss_amt=0.35, scale=1.0, emit_veins=None):
    m, nt = node_mat(name)
    if nt is None:
        return m
    n = nt.nodes; b = n["Principled BSDF"]
    tc = n.new("ShaderNodeTexCoord")
    mp = n.new("ShaderNodeMapping"); mp.inputs["Scale"].default_value = (scale, scale, scale)
    link(nt, tc.outputs["Object"], mp.inputs["Vector"])
    nz = n.new("ShaderNodeTexNoise"); nz.inputs["Scale"].default_value = 4.5; nz.inputs["Detail"].default_value = 10
    link(nt, mp.outputs[0], nz.inputs["Vector"])
    ramp = n.new("ShaderNodeValToRGB")
    ramp.color_ramp.elements[0].color = (*c1, 1); ramp.color_ramp.elements[1].color = (*c2, 1)
    ramp.color_ramp.elements[0].position = 0.3; ramp.color_ramp.elements[1].position = 0.7
    link(nt, nz.outputs["Fac"], ramp.inputs["Fac"])
    geo = n.new("ShaderNodeNewGeometry"); sep = n.new("ShaderNodeSeparateXYZ")
    link(nt, geo.outputs["Normal"], sep.inputs[0])
    mn = n.new("ShaderNodeTexNoise"); mn.inputs["Scale"].default_value = 3; mn.inputs["Detail"].default_value = 8
    link(nt, mp.outputs[0], mn.inputs["Vector"])
    add = n.new("ShaderNodeMath"); add.operation = "MULTIPLY_ADD"
    link(nt, mn.outputs["Fac"], add.inputs[0]); add.inputs[1].default_value = 1.0
    link(nt, sep.outputs["Z"], add.inputs[2])
    mr = n.new("ShaderNodeMapRange")
    mr.inputs["From Min"].default_value = 1.55 - moss_amt; mr.inputs["From Max"].default_value = 1.75 - moss_amt
    link(nt, add.outputs[0], mr.inputs["Value"])
    mixc = n.new("ShaderNodeMix"); mixc.data_type = "RGBA"
    link(nt, mr.outputs[0], mixc.inputs["Factor"]); link(nt, ramp.outputs[0], mixc.inputs[6])
    mixc.inputs[7].default_value = (*moss, 1)
    link(nt, mixc.outputs[2], b.inputs["Base Color"])
    b.inputs["Roughness"].default_value = 0.55
    b.inputs["Subsurface Weight"].default_value = 0.15
    b.inputs["Subsurface Radius"].default_value = (0.6, 0.7, 1.0)
    b.inputs["Subsurface Scale"].default_value = 0.03
    vor = n.new("ShaderNodeTexVoronoi"); vor.feature = "DISTANCE_TO_EDGE"; vor.inputs["Scale"].default_value = 2.0
    link(nt, mp.outputs[0], vor.inputs["Vector"])
    bump = n.new("ShaderNodeBump"); bump.inputs["Strength"].default_value = 0.35; bump.inputs["Distance"].default_value = 0.02
    link(nt, nz.outputs["Fac"], bump.inputs["Height"]); link(nt, bump.outputs[0], b.inputs["Normal"])
    if emit_veins:
        mr2 = n.new("ShaderNodeMapRange"); mr2.inputs["From Min"].default_value = 0.0; mr2.inputs["From Max"].default_value = 0.015
        mr2.inputs["To Min"].default_value = 0.6; mr2.inputs["To Max"].default_value = 0.0
        link(nt, vor.outputs["Distance"], mr2.inputs["Value"])
        b.inputs["Emission Color"].default_value = (*emit_veins, 1)
        link(nt, mr2.outputs[0], b.inputs["Emission Strength"])
    return m


def leaf_mat(name="FV_Leaves", c1=(0.10, 0.30, 0.06), c2=(0.42, 0.62, 0.16), blossom=(1.0, 0.72, 0.86), bl_amt=0.18):
    m, nt = node_mat(name)
    if nt is None:
        return m
    n = nt.nodes; b = n["Principled BSDF"]
    tc = n.new("ShaderNodeTexCoord")
    vor = n.new("ShaderNodeTexVoronoi"); vor.inputs["Scale"].default_value = 9.0
    link(nt, tc.outputs["Object"], vor.inputs["Vector"])
    nz = n.new("ShaderNodeTexNoise"); nz.inputs["Scale"].default_value = 2.5; nz.inputs["Detail"].default_value = 5
    link(nt, tc.outputs["Object"], nz.inputs["Vector"])
    ramp = n.new("ShaderNodeValToRGB")
    ramp.color_ramp.elements[0].color = (*c1, 1); ramp.color_ramp.elements[1].color = (*c2, 1)
    mul = n.new("ShaderNodeMath"); mul.operation = "MULTIPLY"
    link(nt, vor.outputs["Distance"], mul.inputs[0]); link(nt, nz.outputs["Fac"], mul.inputs[1])
    mul2 = n.new("ShaderNodeMath"); mul2.operation = "MULTIPLY"; mul2.inputs[1].default_value = 2.2
    link(nt, mul.outputs[0], mul2.inputs[0]); link(nt, mul2.outputs[0], ramp.inputs["Fac"])
    # blossoms: voronoi cells with random colour above a threshold
    vb = n.new("ShaderNodeTexVoronoi"); vb.inputs["Scale"].default_value = 14.0
    link(nt, tc.outputs["Object"], vb.inputs["Vector"])
    sep = n.new("ShaderNodeSeparateColor"); link(nt, vb.outputs["Color"], sep.inputs[0])
    gt = n.new("ShaderNodeMath"); gt.operation = "GREATER_THAN"; gt.inputs[1].default_value = 1.0 - bl_amt
    link(nt, sep.outputs[0], gt.inputs[0])
    lt = n.new("ShaderNodeMath"); lt.operation = "LESS_THAN"; lt.inputs[1].default_value = 0.22
    link(nt, vb.outputs["Distance"], lt.inputs[0])
    andn = n.new("ShaderNodeMath"); andn.operation = "MULTIPLY"
    link(nt, gt.outputs[0], andn.inputs[0]); link(nt, lt.outputs[0], andn.inputs[1])
    mixc = n.new("ShaderNodeMix"); mixc.data_type = "RGBA"
    link(nt, andn.outputs[0], mixc.inputs["Factor"]); link(nt, ramp.outputs[0], mixc.inputs[6])
    mixc.inputs[7].default_value = (*blossom, 1)
    link(nt, mixc.outputs[2], b.inputs["Base Color"])
    b.inputs["Roughness"].default_value = 0.6
    b.inputs["Subsurface Weight"].default_value = 0.25
    b.inputs["Subsurface Radius"].default_value = (0.4, 1.0, 0.2)
    b.inputs["Subsurface Scale"].default_value = 0.1
    b.inputs["Sheen Weight"].default_value = 0.3
    bump = n.new("ShaderNodeBump"); bump.inputs["Strength"].default_value = 1.0; bump.inputs["Distance"].default_value = 0.08
    link(nt, vor.outputs["Distance"], bump.inputs["Height"]); link(nt, bump.outputs[0], b.inputs["Normal"])
    return m


def glow_mat(name, color, strength=6.0):
    m, nt = node_mat(name)
    if nt is None:
        return m
    n = nt.nodes; b = n["Principled BSDF"]
    b.inputs["Base Color"].default_value = (*color, 1)
    b.inputs["Emission Color"].default_value = (*color, 1)
    b.inputs["Emission Strength"].default_value = strength
    b.inputs["Roughness"].default_value = 0.3
    return m


def window_mat(name="FV_Window", color=(1.0, 0.42, 0.10), strength=9.0):
    m, nt = node_mat(name)
    if nt is None:
        return m
    n = nt.nodes; b = n["Principled BSDF"]
    tc = n.new("ShaderNodeTexCoord")
    gr = n.new("ShaderNodeTexGradient"); gr.gradient_type = "SPHERICAL"
    mp = n.new("ShaderNodeMapping"); mp.inputs["Scale"].default_value = (1.2, 1.2, 1.2)
    link(nt, tc.outputs["Generated"], mp.inputs[0])
    mp.inputs["Location"].default_value = (-0.1, -0.1, -0.1)
    link(nt, mp.outputs[0], gr.inputs[0])
    mr = n.new("ShaderNodeMapRange"); mr.inputs["To Min"].default_value = strength * 0.45; mr.inputs["To Max"].default_value = strength
    link(nt, gr.outputs["Fac"], mr.inputs["Value"])
    b.inputs["Base Color"].default_value = (*color, 1)
    b.inputs["Emission Color"].default_value = (*color, 1)
    link(nt, mr.outputs[0], b.inputs["Emission Strength"])
    b.inputs["Roughness"].default_value = 0.08
    b.inputs["Coat Weight"].default_value = 1.0
    return m


def wood_mat(name="FV_Wood", c1=(0.30, 0.17, 0.08), c2=(0.55, 0.36, 0.19)):
    m, nt = node_mat(name)
    if nt is None:
        return m
    n = nt.nodes; b = n["Principled BSDF"]
    tc = n.new("ShaderNodeTexCoord")
    mp = n.new("ShaderNodeMapping"); mp.inputs["Scale"].default_value = (6, 6, 0.6)
    link(nt, tc.outputs["Object"], mp.inputs[0])
    wv = n.new("ShaderNodeTexWave"); wv.inputs["Scale"].default_value = 2.0; wv.inputs["Distortion"].default_value = 6
    wv.inputs["Detail"].default_value = 4
    link(nt, mp.outputs[0], wv.inputs[0])
    ramp = n.new("ShaderNodeValToRGB")
    ramp.color_ramp.elements[0].color = (*c1, 1); ramp.color_ramp.elements[1].color = (*c2, 1)
    link(nt, wv.outputs["Fac"], ramp.inputs["Fac"]); link(nt, ramp.outputs[0], b.inputs["Base Color"])
    b.inputs["Roughness"].default_value = 0.55
    b.inputs["Coat Weight"].default_value = 0.25
    bump = n.new("ShaderNodeBump"); bump.inputs["Strength"].default_value = 0.25
    link(nt, wv.outputs["Fac"], bump.inputs["Height"]); link(nt, bump.outputs[0], b.inputs["Normal"])
    return m


def gold_mat(name="FV_Gold", color=(1.0, 0.76, 0.36)):
    return principled(name, color, rough=0.28, metal=1.0)


def water_mat(name="FV_Water", tint=(0.55, 0.85, 1.0), glow=(0.35, 0.75, 1.0), glow_strength=0.6, phase=0.0,
              ring_scale=6.0):
    """Clear magical water. `phase` (0..1) animates the ripple rings and loops perfectly."""
    m, nt = node_mat(name)
    if nt is None:
        return m
    n = nt.nodes; b = n["Principled BSDF"]
    b.inputs["Base Color"].default_value = (*tint, 1)
    b.inputs["Roughness"].default_value = 0.03
    b.inputs["Transmission Weight"].default_value = 1.0
    b.inputs["IOR"].default_value = 1.33
    b.inputs["Emission Color"].default_value = (*glow, 1)
    b.inputs["Emission Strength"].default_value = glow_strength
    tc = n.new("ShaderNodeTexCoord")
    wv = n.new("ShaderNodeTexWave"); wv.wave_type = "RINGS"; wv.rings_direction = "SPHERICAL"
    wv.inputs["Scale"].default_value = ring_scale; wv.inputs["Distortion"].default_value = 1.5
    wv.inputs["Detail"].default_value = 2
    wv.inputs["Phase Offset"].default_value = -phase * 2 * math.pi
    link(nt, tc.outputs["Object"], wv.inputs[0])
    nz = n.new("ShaderNodeTexNoise"); nz.inputs["Scale"].default_value = 8.0
    nz.noise_dimensions = "4D"
    nz.inputs["W"].default_value = math.sin(phase * 2 * math.pi) * 0.3
    link(nt, tc.outputs["Object"], nz.inputs[0])
    mx = n.new("ShaderNodeMath"); mx.operation = "MULTIPLY_ADD"; mx.inputs[1].default_value = 0.3
    link(nt, nz.outputs["Fac"], mx.inputs[0]); link(nt, wv.outputs["Fac"], mx.inputs[2])
    bump = n.new("ShaderNodeBump"); bump.inputs["Strength"].default_value = 0.25; bump.inputs["Distance"].default_value = 0.02
    link(nt, mx.outputs[0], bump.inputs["Height"]); link(nt, bump.outputs[0], b.inputs["Normal"])
    return m


def petal_mat(name, c_base, c_tip, glow=None, glow_strength=0.0):
    m, nt = node_mat(name)
    if nt is None:
        return m
    n = nt.nodes; b = n["Principled BSDF"]
    tc = n.new("ShaderNodeTexCoord")
    sep = n.new("ShaderNodeSeparateXYZ"); link(nt, tc.outputs["UV"], sep.inputs[0])
    ramp = n.new("ShaderNodeValToRGB")
    ramp.color_ramp.elements[0].color = (*c_base, 1); ramp.color_ramp.elements[1].color = (*c_tip, 1)
    link(nt, sep.outputs["Y"], ramp.inputs["Fac"]); link(nt, ramp.outputs[0], b.inputs["Base Color"])
    wv = n.new("ShaderNodeTexWave"); wv.bands_direction = "X"; wv.inputs["Scale"].default_value = 18
    wv.inputs["Distortion"].default_value = 2
    link(nt, tc.outputs["UV"], wv.inputs[0])
    bump = n.new("ShaderNodeBump"); bump.inputs["Strength"].default_value = 0.2
    link(nt, wv.outputs["Fac"], bump.inputs["Height"]); link(nt, bump.outputs[0], b.inputs["Normal"])
    b.inputs["Roughness"].default_value = 0.45
    b.inputs["Subsurface Weight"].default_value = 0.4
    b.inputs["Subsurface Radius"].default_value = (1.0, 0.5, 0.6)
    b.inputs["Subsurface Scale"].default_value = 0.05
    b.inputs["Sheen Weight"].default_value = 0.6
    b.inputs["Transmission Weight"].default_value = 0.15
    if glow:
        b.inputs["Emission Color"].default_value = (*glow, 1)
        b.inputs["Emission Strength"].default_value = glow_strength
    return m


# ----------------------------------------------------------------- mesh helpers
def obj_from_bm(bm, name, mat=None, col=None, smooth=True):
    me = bpy.data.meshes.new(name); bm.to_mesh(me); bm.free()
    if smooth:
        for p in me.polygons:
            p.use_smooth = True
    o = bpy.data.objects.new(name, me)
    (col or bpy.context.scene.collection).objects.link(o)
    if mat:
        me.materials.append(mat)
    return o


def lathe(name, profile, segs=48, mat=None, col=None, smooth=True, close_top=False, close_bottom=False):
    """profile: list of (r, z). Revolve around Z."""
    bm = bmesh.new()
    rings = []
    for r, z in profile:
        ring = [bm.verts.new((r * math.cos(2 * math.pi * i / segs), r * math.sin(2 * math.pi * i / segs), z))
                for i in range(segs)]
        rings.append(ring)
    for a, b in zip(rings[:-1], rings[1:]):
        for i in range(segs):
            j = (i + 1) % segs
            try:
                bm.faces.new((a[i], a[j], b[j], b[i]))
            except ValueError:
                pass
    if close_bottom:
        bm.faces.new(list(reversed(rings[0])))
    if close_top:
        bm.faces.new(rings[-1])
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=1e-5)
    bm.normal_update()
    return obj_from_bm(bm, name, mat, col, smooth)


def add_mod_subsurf(o, lv=2, render=None):
    m = o.modifiers.new("Sub", "SUBSURF"); m.levels = lv; m.render_levels = render or lv
    return m


def displace(o, strength=0.1, scale=1.0, tex_type="CLOUDS", mid=0.5, name=None, noise_depth=4):
    t = bpy.data.textures.new(name or (o.name + "_dtex"), tex_type)
    if tex_type == "CLOUDS":
        t.noise_scale = scale; t.noise_depth = noise_depth
    elif tex_type == "VORONOI":
        t.noise_scale = scale
    m = o.modifiers.new("Disp", "DISPLACE"); m.texture = t; m.strength = strength; m.mid_level = mid
    m.texture_coords = "OBJECT" if False else "LOCAL"
    return m


def tube_curve(name, pts, radius=0.1, taper=None, mat=None, col=None, res=12, bevel_res=6, radii=None):
    cu = bpy.data.curves.new(name, "CURVE"); cu.dimensions = "3D"
    cu.bevel_depth = radius; cu.bevel_resolution = bevel_res; cu.resolution_u = res
    cu.use_fill_caps = True
    sp = cu.splines.new("NURBS"); sp.points.add(len(pts) - 1)
    for i, p in enumerate(pts):
        sp.points[i].co = (*p, 1)
        if radii:
            sp.points[i].radius = radii[i]
    sp.use_endpoint_u = True; sp.order_u = min(4, len(pts))
    o = bpy.data.objects.new(name, cu)
    (col or bpy.context.scene.collection).objects.link(o)
    if mat:
        cu.materials.append(mat)
    return o


def ico(name, r, loc, sub=3, mat=None, col=None, scale=(1, 1, 1), smooth=True):
    bm = bmesh.new(); bmesh.ops.create_icosphere(bm, subdivisions=sub, radius=r)
    o = obj_from_bm(bm, name, mat, col, smooth); o.location = loc; o.scale = scale
    return o


def uvsphere(name, r, loc, segs=32, rings=16, mat=None, col=None, scale=(1, 1, 1)):
    bm = bmesh.new(); bmesh.ops.create_uvsphere(bm, u_segments=segs, v_segments=rings, radius=r)
    o = obj_from_bm(bm, name, mat, col); o.location = loc; o.scale = scale
    return o


def cyl(name, r, h, loc, segs=32, mat=None, col=None, r2=None, smooth=True, caps=True):
    bm = bmesh.new()
    bmesh.ops.create_cone(bm, cap_ends=caps, segments=segs, radius1=r, radius2=r if r2 is None else r2, depth=h)
    o = obj_from_bm(bm, name, mat, col, smooth); o.location = loc
    return o


def box(name, size, loc, mat=None, col=None, bevel=0.0, rot=(0, 0, 0)):
    bm = bmesh.new(); bmesh.ops.create_cube(bm, size=1.0)
    for v in bm.verts:
        v.co = Vector((v.co.x * size[0], v.co.y * size[1], v.co.z * size[2]))
    o = obj_from_bm(bm, name, mat, col, smooth=False); o.location = loc; o.rotation_euler = rot
    if bevel:
        m = o.modifiers.new("Bev", "BEVEL"); m.width = bevel; m.segments = 3; m.limit_method = "ANGLE"
        o.data.polygons.foreach_set("use_smooth", [True] * len(o.data.polygons))
        try:
            o.data.set_sharp_from_angle(angle=math.radians(40))
        except Exception:
            pass
    return o


def torus(name, R, r, loc, mat=None, col=None, segs=48, rsegs=12, rot=(0, 0, 0)):
    bm = bmesh.new()
    verts = []
    for i in range(segs):
        a = 2 * math.pi * i / segs
        ring = []
        for j in range(rsegs):
            b = 2 * math.pi * j / rsegs
            ring.append(bm.verts.new(((R + r * math.cos(b)) * math.cos(a), (R + r * math.cos(b)) * math.sin(a), r * math.sin(b))))
        verts.append(ring)
    for i in range(segs):
        for j in range(rsegs):
            bm.faces.new((verts[i][j], verts[(i + 1) % segs][j], verts[(i + 1) % segs][(j + 1) % rsegs], verts[i][(j + 1) % rsegs]))
    o = obj_from_bm(bm, name, mat, col); o.location = loc; o.rotation_euler = rot
    return o


def join(objs, name):
    objs = [o for o in objs if o]
    ctx = bpy.context
    for o in ctx.selected_objects:
        o.select_set(False)
    for o in objs:
        o.select_set(True)
    ctx.view_layer.objects.active = objs[0]
    bpy.ops.object.join()
    objs[0].name = name
    return objs[0]


def apply_mods(o):
    ctx = bpy.context
    for s in ctx.selected_objects:
        s.select_set(False)
    o.select_set(True); ctx.view_layer.objects.active = o
    if o.type == "CURVE":
        bpy.ops.object.convert(target="MESH")
        return ctx.view_layer.objects.active
    for m in list(o.modifiers):
        bpy.ops.object.modifier_apply(modifier=m.name)
    return o


# ----------------------------------------------------------------- flowers / scatter
def flower(name, loc, r=0.12, petals=6, c_base=(1, 0.75, 0.9), c_tip=(1, 0.95, 1), center=(1.0, 0.8, 0.2),
           col=None, glow=None, tilt=0.0, rot=0.0, cup=0.35):
    bm = bmesh.new()
    uvl = bm.loops.layers.uv.new("UVMap")
    for i in range(petals):
        a = rot + 2 * math.pi * i / petals
        ca, sa = math.cos(a), math.sin(a)
        pts = [(0.0, 0.0), (0.35, 0.33), (0.75, 0.38), (1.0, 0.0), (0.75, -0.38), (0.35, -0.33)]
        vs = []
        for (u, w) in pts:
            x = u * r; y = w * r * 0.55
            z = cup * r * (u ** 2)
            vs.append(bm.verts.new((x * ca - y * sa, x * sa + y * ca, z)))
        f = bm.faces.new(vs)
        for lp, (u, w) in zip(f.loops, pts):
            lp[uvl].uv = (w + 0.5, u)
    o = obj_from_bm(bm, name, petal_mat(f"FV_Petal_{name[:10]}_{int(c_base[0]*9)}{int(c_base[1]*9)}{int(c_base[2]*9)}", c_base, c_tip, glow, 1.5 if glow else 0), col)
    sol = o.modifiers.new("Sol", "SOLIDIFY"); sol.thickness = r * 0.04
    add_mod_subsurf(o, 1)
    c = ico(name + "_c", r * 0.22, (0, 0, r * 0.05), sub=2, mat=glow_mat(f"FV_FlowerC_{int(center[0]*9)}{int(center[1]*9)}{int(center[2]*9)}", center, 2.5), col=col)
    c.parent = o
    o.location = loc; o.rotation_euler = (tilt, 0, 0)
    return o


def mushroom(name, loc, h=0.35, cap_r=0.22, cap_col=(0.55, 0.25, 0.85), glow=(0.6, 0.4, 1.0), col=None, lean=0.0,
             spots=True, strength=3.0):
    stem = lathe(name + "_stem", [(cap_r * 0.28, 0), (cap_r * 0.24, h * 0.5), (cap_r * 0.2, h * 0.92), (0.001, h * 0.95)],
                 segs=20, mat=principled("FV_ShroomStem", (0.92, 0.88, 0.78), rough=0.6, sss=0.3), col=col, close_bottom=True)
    capm, nt = node_mat(f"FV_ShroomCap_{int(cap_col[0]*9)}{int(cap_col[1]*9)}{int(cap_col[2]*9)}")
    if nt is not None:
        n = nt.nodes; b = n["Principled BSDF"]
        b.inputs["Base Color"].default_value = (*cap_col, 1)
        b.inputs["Roughness"].default_value = 0.35
        b.inputs["Coat Weight"].default_value = 0.6
        b.inputs["Subsurface Weight"].default_value = 0.4
        b.inputs["Subsurface Radius"].default_value = (0.8, 0.4, 1.0)
        b.inputs["Subsurface Scale"].default_value = 0.04
        tc = n.new("ShaderNodeTexCoord"); v = n.new("ShaderNodeTexVoronoi"); v.inputs["Scale"].default_value = 7
        link(nt, tc.outputs["Object"], v.inputs[0])
        mr = n.new("ShaderNodeMapRange"); mr.inputs["From Min"].default_value = 0.12; mr.inputs["From Max"].default_value = 0.2
        mr.inputs["To Min"].default_value = strength; mr.inputs["To Max"].default_value = 0.15
        link(nt, v.outputs["Distance"], mr.inputs["Value"])
        b.inputs["Emission Color"].default_value = (*glow, 1)
        link(nt, mr.outputs[0], b.inputs["Emission Strength"])
    cap = lathe(name + "_cap", [(cap_r * 0.2, h * 0.86), (cap_r, h * 0.82), (cap_r * 0.96, h * 0.92), (cap_r * 0.75, h * 1.08),
                                (cap_r * 0.4, h * 1.18), (0.001, h * 1.21)], segs=28, mat=capm, col=col, close_bottom=True)
    cap.parent = stem
    stem.location = loc; stem.rotation_euler = (lean, lean * 0.5, random.random() * 6.28)
    return stem


# ----------------------------------------------------------------- cameras / rendering
def game_root(col=None):
    e = bpy.data.objects.new("GAME_XFORM", None)
    (col or bpy.context.scene.collection).objects.link(e)
    return e


def project_uv(p):
    """World point (metres, model space) -> sprite plane (u, v) in metres."""
    return p.x, p.y + p.z * ZEX * COS


def game_camera(sc, objs, ppt=PPT_HD, margin_tiles=0.25, name="GameCam", fixed=None):
    """Oblique game projection identical to the housing/buildings packs. Objects must be parented to a
    GAME_XFORM empty scaled (1, 1/SIN, ZEX). Returns metadata (tiles bounds, size, origin)."""
    us, vs = [], []
    deps = bpy.context.evaluated_depsgraph_get()
    for o in objs:
        if o.type not in ("MESH", "CURVE"):
            continue
        ev = o.evaluated_get(deps)
        try:
            me = ev.to_mesh()
        except Exception:
            continue
        mw = o.matrix_world.copy()
        # matrix_world already includes GAME_XFORM scaling; undo it to project in model space
        root = o
        while root.parent:
            root = root.parent
        inv = root.matrix_world.inverted() if root.name.startswith("GAME_XFORM") else Matrix.Identity(4)
        for v in me.vertices:
            p = inv @ (mw @ v.co)
            u, w = project_uv(p)
            us.append(u); vs.append(w)
        ev.to_mesh_clear()
    if fixed:
        L_T, R_T, BOT_T, TOP_T = fixed
    else:
        L_T = math.floor(min(us) / T - margin_tiles); R_T = math.ceil(max(us) / T + margin_tiles)
        TOP_T = math.ceil(max(vs) / T + margin_tiles); BOT_T = math.floor(min(vs) / T - margin_tiles)
    U0, U1, V0, V1 = L_T * T, R_T * T, BOT_T * T, TOP_T * T
    W, H = int(round((R_T - L_T) * ppt)), int(round((TOP_T - BOT_T) * ppt))
    cam = bpy.data.cameras.new(name); cam.type = "ORTHO"; cam.ortho_scale = max(U1 - U0, V1 - V0)
    cam.clip_start, cam.clip_end = 0.5, 800
    co = bpy.data.objects.new(name, cam)
    up = Vector((0, SIN, COS)); fwd = Vector((0, COS, -SIN))
    co.location = Vector(((U0 + U1) / 2, 0, 0)) + up * ((V0 + V1) / 2) - fwd * 300.0
    co.rotation_euler = Euler((math.radians(58), 0, 0), "XYZ")
    sc.collection.objects.link(co); sc.camera = co
    sc.render.resolution_x, sc.render.resolution_y = W, H
    # non-square: Blender fits ortho_scale to the larger dimension automatically
    return {"tiles": {"left": L_T, "right": R_T, "top": TOP_T, "bottom": BOT_T}, "size": [W, H], "ppt": ppt,
            "origin_px": [-L_T * ppt, TOP_T * ppt],
            "origin_note": "pixel of model (0,0,0) = NW corner of the footprint (tile x0,y0 top-left)"}


def hero_camera(sc, target, dist, az=28, el=26, lens=50, name="HeroCam", w=2048, h=2048):
    cam = bpy.data.cameras.new(name); cam.lens = lens; cam.clip_end = 2000; cam.clip_start = 0.05
    co = bpy.data.objects.new(name, cam)
    a, e = math.radians(az), math.radians(el)
    tgt = Vector(target)
    co.location = tgt + dist * Vector((math.sin(a) * math.cos(e), -math.cos(a) * math.cos(e), math.sin(e)))
    co.rotation_euler = (tgt - co.location).to_track_quat("-Z", "Y").to_euler()
    sc.collection.objects.link(co); sc.camera = co
    sc.render.resolution_x, sc.render.resolution_y = w, h
    return co


def shadow_catcher(name, size, loc=(0, 0, 0), col=None):
    bm = bmesh.new(); bmesh.ops.create_grid(bm, x_segments=1, y_segments=1, size=size / 2)
    o = obj_from_bm(bm, name, principled("FV_Catcher", (0.5, 0.5, 0.5)), col, smooth=False)
    o.location = loc; o.is_shadow_catcher = True
    return o


def hero_ground(name, radius, loc, col=None, fade=0.55):
    """Moss disc whose edge fades to alpha 0 so the hero render composites onto a painted backdrop."""
    bm = bmesh.new(); bmesh.ops.create_circle(bm, cap_ends=True, segments=96, radius=radius)
    o = obj_from_bm(bm, name, None, col, smooth=False); o.location = loc
    m, nt = node_mat("FV_HeroGround")
    if nt is not None:
        n = nt.nodes; b = n["Principled BSDF"]; out = n["Material Output"]
        tc = n.new("ShaderNodeTexCoord")
        nz = n.new("ShaderNodeTexNoise"); nz.inputs["Scale"].default_value = 0.6; nz.inputs["Detail"].default_value = 10
        link(nt, tc.outputs["Object"], nz.inputs[0])
        ramp = n.new("ShaderNodeValToRGB")
        ramp.color_ramp.elements[0].color = (0.035, 0.09, 0.025, 1); ramp.color_ramp.elements[1].color = (0.16, 0.28, 0.07, 1)
        link(nt, nz.outputs["Fac"], ramp.inputs["Fac"]); link(nt, ramp.outputs[0], b.inputs["Base Color"])
        b.inputs["Roughness"].default_value = 0.9
        bump = n.new("ShaderNodeBump"); bump.inputs["Strength"].default_value = 0.6
        nz2 = n.new("ShaderNodeTexNoise"); nz2.inputs["Scale"].default_value = 18; nz2.inputs["Detail"].default_value = 8
        link(nt, tc.outputs["Object"], nz2.inputs[0]); link(nt, nz2.outputs["Fac"], bump.inputs["Height"])
        link(nt, bump.outputs[0], b.inputs["Normal"])
        vl = n.new("ShaderNodeVectorMath"); vl.operation = "LENGTH"
        link(nt, tc.outputs["Object"], vl.inputs[0])
        mr = n.new("ShaderNodeMapRange"); mr.inputs["From Min"].default_value = radius * fade; mr.inputs["From Max"].default_value = radius
        mr.inputs["To Min"].default_value = 1.0; mr.inputs["To Max"].default_value = 0.0
        link(nt, vl.outputs["Value"], mr.inputs["Value"])
        tr = n.new("ShaderNodeBsdfTransparent"); ms = n.new("ShaderNodeMixShader")
        link(nt, mr.outputs[0], ms.inputs[0]); link(nt, tr.outputs[0], ms.inputs[1]); link(nt, b.outputs[0], ms.inputs[2])
        link(nt, ms.outputs[0], out.inputs["Surface"])
    o.data.materials.append(m)
    return o


def render(sc, path):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    sc.render.filepath = path
    bpy.ops.render.render(write_still=True, scene=sc.name)
    print("[render]", path, flush=True)


def save_json(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        json.dump(data, f, indent=1)
