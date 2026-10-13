"""Blender 4.2 / Cycles: seamless Emberdeep stone textures from real geometry.
blender -b -P bake_stones.py -- <kind> <seed> <out.png>
kind: wall | lava | floor | top
One tile [0,1]^2 of stones is built in a collection and instanced 3x3, so the
centre view is exactly periodic (procedural noise uses each stone's own object space)."""
import bpy, sys, math, random
argv = sys.argv[sys.argv.index("--") + 1:]
kind, seed, out = argv[0], int(argv[1]), argv[2]
R = random.Random(seed)
bpy.ops.wm.read_factory_settings(use_empty=True)
sc = bpy.context.scene
sc.render.engine = "CYCLES"; sc.cycles.device = "CPU"; sc.cycles.samples = 64
sc.cycles.use_denoising = True
sc.render.resolution_x = sc.render.resolution_y = 1024
sc.view_settings.view_transform = "Standard"; sc.view_settings.look = "None"
tile = bpy.data.collections.new("tile"); sc.collection.children.link(tile)

def node_mat(name, build):
    m = bpy.data.materials.new(name); m.use_nodes = True
    build(m.node_tree); return m

def stone_mat(nt, dark, light, emit=False):
    N, L = nt.nodes, nt.links
    b = N["Principled BSDF"]; b.inputs["Roughness"].default_value = 0.78
    oi = N.new("ShaderNodeObjectInfo")
    tc = N.new("ShaderNodeTexCoord")
    noi = N.new("ShaderNodeTexNoise"); noi.inputs["Scale"].default_value = 14; noi.inputs["Detail"].default_value = 8
    noi.inputs["Roughness"].default_value = 0.62
    L.new(tc.outputs["Object"], noi.inputs["Vector"])
    mix = N.new("ShaderNodeMath"); mix.operation = "MULTIPLY_ADD"
    mix.inputs[1].default_value = 0.9
    L.new(oi.outputs["Color"], mix.inputs[0]); L.new(noi.outputs["Fac"], mix.inputs[2])
    ramp = N.new("ShaderNodeValToRGB")
    ramp.color_ramp.elements[0].position = 0.30; ramp.color_ramp.elements[0].color = dark
    ramp.color_ramp.elements[1].position = 1.25; ramp.color_ramp.elements[1].color = light
    mid_el = ramp.color_ramp.elements.new(0.78); mid_el.color = (light[0] * 0.62, light[1] * 0.52, light[2] * 0.46, 1)
    L.new(mix.outputs[0], ramp.inputs["Fac"])
    # edge wear: lighter on convex edges, darker in cavities
    geo = N.new("ShaderNodeNewGeometry")
    pr = N.new("ShaderNodeValToRGB")
    pr.color_ramp.elements[0].position = 0.46; pr.color_ramp.elements[0].color = (0.55, 0.55, 0.55, 1)
    pr.color_ramp.elements[1].position = 0.56; pr.color_ramp.elements[1].color = (1.35, 1.3, 1.25, 1)
    L.new(geo.outputs["Pointiness"], pr.inputs["Fac"])
    mul = N.new("ShaderNodeMix"); mul.data_type = "RGBA"; mul.blend_type = "MULTIPLY"
    mul.inputs["Factor"].default_value = 1.0
    L.new(ramp.outputs["Color"], mul.inputs[6]); L.new(pr.outputs["Color"], mul.inputs[7])
    # fine speckle
    vor = N.new("ShaderNodeTexVoronoi"); vor.inputs["Scale"].default_value = 140
    L.new(tc.outputs["Object"], vor.inputs["Vector"])
    sp = N.new("ShaderNodeMix"); sp.data_type = "RGBA"; sp.blend_type = "MULTIPLY"
    sp.inputs["Factor"].default_value = 0.25
    L.new(mul.outputs[2], sp.inputs[6]); L.new(vor.outputs["Distance"], sp.inputs[7])
    L.new(sp.outputs[2], b.inputs["Base Color"])
    bump = N.new("ShaderNodeBump"); bump.inputs["Strength"].default_value = 0.45; bump.inputs["Distance"].default_value = 0.006
    noi2 = N.new("ShaderNodeTexNoise"); noi2.inputs["Scale"].default_value = 60; noi2.inputs["Detail"].default_value = 10
    L.new(tc.outputs["Object"], noi2.inputs["Vector"])
    L.new(noi2.outputs["Fac"], bump.inputs["Height"]); L.new(bump.outputs["Normal"], b.inputs["Normal"])

def mortar_mat(nt, lava):
    N, L = nt.nodes, nt.links
    b = N["Principled BSDF"]; b.inputs["Roughness"].default_value = 0.95
    tc = N.new("ShaderNodeTexCoord")
    noi = N.new("ShaderNodeTexNoise"); noi.inputs["Scale"].default_value = 80; noi.inputs["Detail"].default_value = 6
    L.new(tc.outputs["Object"], noi.inputs["Vector"])
    ramp = N.new("ShaderNodeValToRGB")
    ramp.color_ramp.elements[0].color = (0.035, 0.03, 0.028, 1); ramp.color_ramp.elements[1].color = (0.10, 0.085, 0.075, 1)
    L.new(noi.outputs["Fac"], ramp.inputs["Fac"]); L.new(ramp.outputs["Color"], b.inputs["Base Color"])
    if lava:
        big = N.new("ShaderNodeTexNoise"); big.inputs["Scale"].default_value = 3.0; big.inputs["Detail"].default_value = 3
        L.new(tc.outputs["Object"], big.inputs["Vector"])
        er = N.new("ShaderNodeValToRGB")
        er.color_ramp.elements[0].position = 0.50; er.color_ramp.elements[0].color = (0, 0, 0, 1)
        er.color_ramp.elements[1].position = 0.62; er.color_ramp.elements[1].color = (1.0, 0.32, 0.04, 1)
        L.new(big.outputs["Fac"], er.inputs["Fac"])
        L.new(er.outputs["Color"], b.inputs["Emission Color"])
        b.inputs["Emission Strength"].default_value = 5.0

def add_stone(x0, y0, w, h, depth, mat, bevel, rough, round_top=False):
    bpy.ops.mesh.primitive_cube_add(size=1)
    ob = bpy.context.active_object
    for c in list(ob.users_collection):
        c.objects.unlink(ob)
    tile.objects.link(ob)
    ob.scale = (w / 2 * 2, h / 2 * 2, depth)
    ob.location = (x0 + w / 2, y0 + h / 2, depth / 2 * (0.6 if round_top else 1))
    ob.rotation_euler = (math.radians(R.uniform(-1.4, 1.4)), math.radians(R.uniform(-1.4, 1.4)), math.radians(R.uniform(-2.5, 2.5)))
    bpy.context.view_layer.objects.active = ob
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    bv = ob.modifiers.new("b", "BEVEL"); bv.width = bevel; bv.segments = 3; bv.limit_method = "NONE"
    ss = ob.modifiers.new("s", "SUBSURF"); ss.subdivision_type = "SIMPLE"; ss.levels = ss.render_levels = (3 if kind == "top" else 4)
    if round_top:
        ss2 = ob.modifiers.new("s2", "SUBSURF"); ss2.levels = ss2.render_levels = 1
    t = bpy.data.textures.new(f"t{len(bpy.data.textures)}", "CLOUDS")
    t.noise_scale = 0.06 + R.uniform(-0.015, 0.015); t.noise_type = "HARD_NOISE"; t.noise_depth = 5
    t.noise_basis = "VORONOI_F2_F1" if R.random() < 0.5 else "VORONOI_CRACKLE"
    d = ob.modifiers.new("d", "DISPLACE"); d.texture = t; d.texture_coords = "OBJECT"; d.strength = rough * 0.6
    d.direction = "NORMAL"
    t2 = bpy.data.textures.new(f"n{len(bpy.data.textures)}", "CLOUDS"); t2.noise_scale = 0.05; t2.noise_depth = 4
    d2 = ob.modifiers.new("d2", "DISPLACE"); d2.texture = t2; d2.texture_coords = "OBJECT"; d2.strength = rough * 0.8
    rv = R.random(); ob.color = (rv, rv, rv, 1)
    ob.data.materials.append(mat)
    bpy.ops.object.shade_smooth()
    return ob

lava = kind == "lava"
if kind in ("wall", "lava"):
    smat = node_mat("stone", lambda nt: stone_mat(nt, (0.022, 0.018, 0.016, 1), (0.15, 0.118, 0.098, 1)))
    rows = 4; gap = 0.014
    hs = [R.uniform(0.8, 1.2) for _ in range(rows)]; s = sum(hs); hs = [v / s for v in hs]
    y = 0.0
    for rh in hs:
        off = R.uniform(0, 1); x = 0.0
        widths = []
        while x < 0.72:
            w = R.uniform(0.24, 0.44); widths.append(w); x += w
        widths.append(1 - x)
        if widths[-1] < 0.16:
            widths[-2] += widths[-1]; widths.pop()
        x = off
        for w in widths:
            add_stone(x + gap / 2, y + gap / 2, w - gap, rh - gap, R.uniform(0.05, 0.085), smat, R.uniform(0.008, 0.03), 0.022)
            x += w
        y += rh
elif kind == "floor":
    smat = node_mat("stone", lambda nt: stone_mat(nt, (0.03, 0.025, 0.022, 1), (0.19, 0.155, 0.13, 1)))
    rows = 4; gap = 0.010
    hs = [R.uniform(0.85, 1.15) for _ in range(rows)]; s = sum(hs); hs = [v / s for v in hs]
    y = 0.0
    for rh in hs:
        off = R.uniform(0, 1); x = 0.0; widths = []
        while x < 0.66:
            w = R.uniform(0.26, 0.5); widths.append(w); x += w
        widths.append(1 - x)
        if widths[-1] < 0.16:
            widths[-2] += widths[-1]; widths.pop()
        x = off
        for w in widths:
            add_stone(x + gap / 2, y + gap / 2, w - gap, rh - gap, R.uniform(0.03, 0.04), smat, R.uniform(0.01, 0.025), 0.012)
            x += w
        y += rh
else:  # top: rubble cap
    smat = node_mat("stone", lambda nt: stone_mat(nt, (0.018, 0.015, 0.013, 1), (0.10, 0.085, 0.075, 1)))
    for i in range(70):
        w = R.uniform(0.08, 0.2); h = w * R.uniform(0.7, 1.3)
        add_stone(R.uniform(0, 1), R.uniform(0, 1), w, h, R.uniform(0.03, 0.07), smat, w * 0.3, 0.02, round_top=True)
mmat = node_mat("mortar", lambda nt: mortar_mat(nt, lava))
bpy.ops.mesh.primitive_plane_add(size=1, location=(0.5, 0.5, 0.004))
pl = bpy.context.active_object
for c in list(pl.users_collection):
    c.objects.unlink(pl)
tile.objects.link(pl); pl.data.materials.append(mmat)
for dx in (-1, 0, 1):
    for dy in (-1, 0, 1):
        e = bpy.data.objects.new(f"i{dx}{dy}", None); e.instance_type = "COLLECTION"; e.instance_collection = tile
        e.location = (dx, dy, 0); sc.collection.objects.link(e)
lc = bpy.context.view_layer.layer_collection.children["tile"]; lc.exclude = True
cam = bpy.data.cameras.new("c"); cam.type = "ORTHO"; cam.ortho_scale = 1.0
co = bpy.data.objects.new("c", cam); sc.collection.objects.link(co); co.location = (0.5, 0.5, 3); sc.camera = co
elev = 40 if kind != "floor" else 52
sun = bpy.data.lights.new("s", "SUN"); sun.energy = 4.5; sun.angle = math.radians(6)
so = bpy.data.objects.new("s", sun); sc.collection.objects.link(so)
so.rotation_euler = (math.radians(90 - elev), 0, math.radians(135 + 90))
fill = bpy.data.lights.new("f", "SUN"); fill.energy = 0.5; fill.angle = math.radians(45)
fo = bpy.data.objects.new("f", fill); sc.collection.objects.link(fo); fo.rotation_euler = (math.radians(30), 0, math.radians(30))
w = bpy.data.worlds.new("w"); sc.world = w; w.use_nodes = True
w.node_tree.nodes["Background"].inputs["Color"].default_value = (0.30, 0.28, 0.27, 1)
w.node_tree.nodes["Background"].inputs["Strength"].default_value = 0.22
sc.render.filepath = out
bpy.ops.render.render(write_still=True)
