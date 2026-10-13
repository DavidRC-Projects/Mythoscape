"""Blender 4.2 / Cycles v2: seamless Emberdeep stone textures from real, uniformly remeshed stones.
blender -b -P bake_stones2.py -- <kind> <seed> <out.png> [res]
kind: wall | lava | floor | top
One tile [0,1]^2 of stones lives in a collection that is instanced 3x3, so the centre view is
exactly periodic (all noise is in each stone's own object space)."""
import bpy, sys, math, random, bmesh
argv = sys.argv[sys.argv.index("--") + 1:]
kind, seed, out = argv[0], int(argv[1]), argv[2]
res = int(argv[3]) if len(argv) > 3 else 1024
R = random.Random(seed)
bpy.ops.wm.read_factory_settings(use_empty=True)
sc = bpy.context.scene
sc.render.engine = "CYCLES"; sc.cycles.device = "CPU"; sc.cycles.samples = 32
sc.cycles.use_denoising = True
sc.render.threads_mode = "FIXED"; sc.render.threads = 3
sc.render.resolution_x = sc.render.resolution_y = res
sc.view_settings.view_transform = "Standard"
tile = bpy.data.collections.new("tile"); sc.collection.children.link(tile)
lava = kind == "lava"

def stone_mat():
    m = bpy.data.materials.new("stone"); m.use_nodes = True
    N, L = m.node_tree.nodes, m.node_tree.links
    b = N["Principled BSDF"]; b.inputs["Roughness"].default_value = 0.86
    tc = N.new("ShaderNodeTexCoord")
    # grain colour: two-tone basalt speckle; per-stone tint is added in grade.py
    n1 = N.new("ShaderNodeTexNoise"); n1.inputs["Scale"].default_value = 22; n1.inputs["Detail"].default_value = 12
    n1.inputs["Roughness"].default_value = 0.7
    L.new(tc.outputs["Object"], n1.inputs["Vector"])
    v1 = N.new("ShaderNodeTexVoronoi"); v1.inputs["Scale"].default_value = 260
    L.new(tc.outputs["Object"], v1.inputs["Vector"])
    ramp = N.new("ShaderNodeValToRGB")
    e = ramp.color_ramp.elements
    e[0].position = 0.30; e[0].color = (0.035, 0.030, 0.027, 1)
    e[1].position = 0.75; e[1].color = (0.20, 0.17, 0.15, 1)
    L.new(n1.outputs["Fac"], ramp.inputs["Fac"])
    sp = N.new("ShaderNodeMix"); sp.data_type = "RGBA"; sp.blend_type = "MULTIPLY"; sp.inputs["Factor"].default_value = 0.35
    L.new(ramp.outputs["Color"], sp.inputs[6]); L.new(v1.outputs["Distance"], sp.inputs[7])
    # cavity dirt (AO) and edge wear (pointiness)
    ao = N.new("ShaderNodeAmbientOcclusion"); ao.inputs["Distance"].default_value = 0.02
    aor = N.new("ShaderNodeValToRGB"); aor.color_ramp.elements[0].position = 0.35
    aor.color_ramp.elements[0].color = (0.35, 0.33, 0.31, 1); aor.color_ramp.elements[1].color = (1, 1, 1, 1)
    L.new(ao.outputs["AO"], aor.inputs["Fac"])
    geo = N.new("ShaderNodeNewGeometry")
    pr = N.new("ShaderNodeValToRGB")
    pr.color_ramp.elements[0].position = 0.50; pr.color_ramp.elements[0].color = (0.9, 0.9, 0.9, 1)
    pr.color_ramp.elements[1].position = 0.58; pr.color_ramp.elements[1].color = (1.6, 1.5, 1.4, 1)
    L.new(geo.outputs["Pointiness"], pr.inputs["Fac"])
    m1 = N.new("ShaderNodeMix"); m1.data_type = "RGBA"; m1.blend_type = "MULTIPLY"; m1.inputs["Factor"].default_value = 1
    L.new(sp.outputs[2], m1.inputs[6]); L.new(aor.outputs["Color"], m1.inputs[7])
    m2 = N.new("ShaderNodeMix"); m2.data_type = "RGBA"; m2.blend_type = "MULTIPLY"; m2.inputs["Factor"].default_value = 1
    L.new(m1.outputs[2], m2.inputs[6]); L.new(pr.outputs["Color"], m2.inputs[7])
    L.new(m2.outputs[2], b.inputs["Base Color"])
    # micro grain bump + hairline cracks
    n2 = N.new("ShaderNodeTexNoise"); n2.inputs["Scale"].default_value = 140; n2.inputs["Detail"].default_value = 8
    L.new(tc.outputs["Object"], n2.inputs["Vector"])
    cr = N.new("ShaderNodeTexVoronoi"); cr.feature = "DISTANCE_TO_EDGE"; cr.inputs["Scale"].default_value = 7
    L.new(tc.outputs["Object"], cr.inputs["Vector"])
    crr = N.new("ShaderNodeMapRange"); crr.inputs["From Min"].default_value = 0.0; crr.inputs["From Max"].default_value = 0.025
    L.new(cr.outputs["Distance"], crr.inputs["Value"])
    hsum = N.new("ShaderNodeMath"); hsum.operation = "MULTIPLY"
    L.new(n2.outputs["Fac"], hsum.inputs[0]); L.new(crr.outputs["Result"], hsum.inputs[1])
    bump = N.new("ShaderNodeBump"); bump.inputs["Strength"].default_value = 0.55; bump.inputs["Distance"].default_value = 0.004
    L.new(hsum.outputs[0], bump.inputs["Height"]); L.new(bump.outputs["Normal"], b.inputs["Normal"])
    return m

def mortar_mat():
    m = bpy.data.materials.new("mortar"); m.use_nodes = True
    N, L = m.node_tree.nodes, m.node_tree.links
    b = N["Principled BSDF"]; b.inputs["Roughness"].default_value = 0.97
    tc = N.new("ShaderNodeTexCoord")
    n = N.new("ShaderNodeTexNoise"); n.inputs["Scale"].default_value = 90; n.inputs["Detail"].default_value = 10
    L.new(tc.outputs["Object"], n.inputs["Vector"])
    r = N.new("ShaderNodeValToRGB")
    r.color_ramp.elements[0].color = (0.02, 0.018, 0.016, 1); r.color_ramp.elements[1].color = (0.075, 0.065, 0.058, 1)
    L.new(n.outputs["Fac"], r.inputs["Fac"]); L.new(r.outputs["Color"], b.inputs["Base Color"])
    bump = N.new("ShaderNodeBump"); bump.inputs["Strength"].default_value = 0.8; bump.inputs["Distance"].default_value = 0.003
    L.new(n.outputs["Fac"], bump.inputs["Height"]); L.new(bump.outputs["Normal"], b.inputs["Normal"])
    if lava:
        big = N.new("ShaderNodeTexNoise"); big.inputs["Scale"].default_value = 2.6; big.inputs["Detail"].default_value = 4
        L.new(tc.outputs["Object"], big.inputs["Vector"])
        er = N.new("ShaderNodeValToRGB")
        er.color_ramp.elements[0].position = 0.52; er.color_ramp.elements[0].color = (0, 0, 0, 1)
        er.color_ramp.elements[1].position = 0.64; er.color_ramp.elements[1].color = (1.0, 0.30, 0.03, 1)
        L.new(big.outputs["Fac"], er.inputs["Fac"])
        L.new(er.outputs["Color"], b.inputs["Emission Color"]); b.inputs["Emission Strength"].default_value = 6.0
    return m

SM, MM = stone_mat(), mortar_mat()

def add_stone(x0, y0, w, h, depth, rough, chip, round_top=False):
    me = bpy.data.meshes.new("s"); ob = bpy.data.objects.new("s", me); tile.objects.link(ob)
    bm = bmesh.new(); bmesh.ops.create_cube(bm, size=1.0)
    for v in bm.verts:
        v.co.x *= w; v.co.y *= h; v.co.z = (v.co.z + 0.5) * depth
        if v.co.z > depth * 0.5:  # irregular, slightly tapered top face
            v.co.x *= R.uniform(0.94, 0.99); v.co.y *= R.uniform(0.93, 0.99)
            v.co.z += R.uniform(-0.25, 0.15) * depth
    bm.to_mesh(me); bm.free()
    ob.location = (x0 + w / 2, y0 + h / 2, 0)
    ob.rotation_euler = (0, 0, math.radians(R.uniform(-2.2, 2.2)))
    bv = ob.modifiers.new("b", "BEVEL"); bv.width = min(w, h) * R.uniform(0.04, 0.09); bv.segments = 3
    rm = ob.modifiers.new("r", "REMESH"); rm.mode = "VOXEL"; rm.voxel_size = 0.0045; rm.use_smooth_shade = True
    t1 = bpy.data.textures.new("c", "CLOUDS"); t1.noise_scale = R.uniform(0.05, 0.08); t1.noise_depth = 4
    d1 = ob.modifiers.new("d1", "DISPLACE"); d1.texture = t1; d1.texture_coords = "OBJECT"; d1.strength = rough; d1.mid_level = 0.55
    t2 = bpy.data.textures.new("v", "VORONOI"); t2.noise_scale = R.uniform(0.035, 0.06); t2.distance_metric = "DISTANCE"
    t2.color_mode = "INTENSITY"; t2.weight_1 = 1.0; t2.weight_2 = 0.0
    d2 = ob.modifiers.new("d2", "DISPLACE"); d2.texture = t2; d2.texture_coords = "OBJECT"; d2.strength = chip; d2.mid_level = 0.6
    t3 = bpy.data.textures.new("f", "CLOUDS"); t3.noise_scale = 0.006; t3.noise_depth = 2
    d3 = ob.modifiers.new("d3", "DISPLACE"); d3.texture = t3; d3.texture_coords = "OBJECT"; d3.strength = 0.0018
    me.materials.append(SM)
    return ob

def courses(rows, wmin, wmax, gap, dmin, dmax, rough, chip):
    hs = [R.uniform(0.82, 1.18) for _ in range(rows)]; s = sum(hs); hs = [v / s for v in hs]
    y = 0.0
    for rh in hs:
        off = R.uniform(0, 1); x = 0.0; ws = []
        while x < 1 - wmax * 0.8:
            w = R.uniform(wmin, wmax); ws.append(w); x += w
        ws.append(1 - x)
        if ws[-1] < wmin * 0.6:
            ws[-2] += ws[-1]; ws.pop()
        x = off
        for w in ws:
            g = gap * R.uniform(0.8, 1.3)
            add_stone(x + g / 2, y + g / 2, w - g, rh - g, R.uniform(dmin, dmax), rough, chip)
            x += w
        y += rh

if kind in ("wall", "lava"):
    courses(4, 0.22, 0.42, 0.016, 0.05, 0.08, 0.016, 0.012)
elif kind == "floor":
    courses(4, 0.26, 0.5, 0.012, 0.03, 0.035, 0.008, 0.007)
else:  # top: rough split capstones, 3 courses
    courses(3, 0.3, 0.55, 0.02, 0.04, 0.07, 0.02, 0.016)
bpy.ops.mesh.primitive_plane_add(size=1, location=(0.5, 0.5, 0.006))
pl = bpy.context.active_object
for c in list(pl.users_collection):
    c.objects.unlink(pl)
tile.objects.link(pl); pl.data.materials.append(MM)
sd = pl.modifiers.new("s", "SUBSURF"); sd.subdivision_type = "SIMPLE"; sd.levels = sd.render_levels = 6
tm = bpy.data.textures.new("m", "CLOUDS"); tm.noise_scale = 0.01
dm = pl.modifiers.new("d", "DISPLACE"); dm.texture = tm; dm.texture_coords = "OBJECT"; dm.strength = 0.006
for dx in (-1, 0, 1):
    for dy in (-1, 0, 1):
        e = bpy.data.objects.new(f"i{dx}{dy}", None); e.instance_type = "COLLECTION"; e.instance_collection = tile
        e.location = (dx, dy, 0); sc.collection.objects.link(e)
bpy.context.view_layer.layer_collection.children["tile"].exclude = True
cam = bpy.data.cameras.new("c"); cam.type = "ORTHO"; cam.ortho_scale = 1.0
co = bpy.data.objects.new("c", cam); sc.collection.objects.link(co); co.location = (0.5, 0.5, 3); sc.camera = co
elev = 38 if kind != "floor" else 50
sun = bpy.data.lights.new("s", "SUN"); sun.energy = 4.2; sun.angle = math.radians(5)
so = bpy.data.objects.new("s", sun); sc.collection.objects.link(so)
so.rotation_euler = (math.radians(90 - elev), 0, math.radians(225))
fill = bpy.data.lights.new("f", "SUN"); fill.energy = 0.45; fill.angle = math.radians(50)
fo = bpy.data.objects.new("f", fill); sc.collection.objects.link(fo); fo.rotation_euler = (math.radians(35), 0, math.radians(40))
w = bpy.data.worlds.new("w"); sc.world = w; w.use_nodes = True
w.node_tree.nodes["Background"].inputs["Color"].default_value = (0.30, 0.28, 0.27, 1)
w.node_tree.nodes["Background"].inputs["Strength"].default_value = 0.25
import time; print("BUILD DONE", flush=True)
sc.render.filepath = out
bpy.ops.render.render(write_still=True)
