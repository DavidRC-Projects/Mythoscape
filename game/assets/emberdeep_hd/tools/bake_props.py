"""Blender 4.2 / Cycles: Emberdeep props.
blender -b -P bake_props.py -- <mode> <seed> <out.png>
mode: trim_base (512x96, tiles in x) | trim_cap (512x64, tiles in x) | door (512x1024 gate pillar)
      | torch (4 frames written as out_0..3.png at 192x320, transparent)"""
import bpy, sys, math, random, bmesh, os
argv = sys.argv[sys.argv.index("--") + 1:]
mode, seed, out = argv[0], int(argv[1]), argv[2]
R = random.Random(seed)
bpy.ops.wm.read_factory_settings(use_empty=True)
sc = bpy.context.scene
sc.render.engine = "CYCLES"; sc.cycles.device = "CPU"; sc.cycles.samples = 48
sc.cycles.use_denoising = True
sc.render.threads_mode = "FIXED"; sc.render.threads = 3
sc.view_settings.view_transform = "Standard"
lava = mode == "door"
# reuse the stone + mortar materials from bake_stones2 (no edits to that file while queues run)
src = open(os.path.join(os.path.dirname(__file__), "bake_stones2.py")).read()
seg = src[src.index("def stone_mat"):src.index("SM, MM =")]
exec(seg)
SM, MM = stone_mat(), mortar_mat()

def stone_block(coll, x0, y0, w, h, depth, rough=0.012, chip=0.009, top_chamfer=0.0, bot_chamfer=0.0, vox=0.0045):
    me = bpy.data.meshes.new("s"); ob = bpy.data.objects.new("s", me); coll.objects.link(ob)
    bm = bmesh.new(); bmesh.ops.create_cube(bm, size=1.0)
    for v in bm.verts:
        v.co.x *= w; v.co.y *= h; v.co.z = (v.co.z + 0.5) * depth
    bm.to_mesh(me); bm.free()
    # profile chamfers: pull the front-top / front-bottom edges back
    for v in me.vertices:
        if v.co.z > depth * 0.5:
            if v.co.y > 0 and top_chamfer: v.co.y -= top_chamfer
            if v.co.y < 0 and bot_chamfer: v.co.y += bot_chamfer
            v.co.x *= R.uniform(0.985, 0.998)
    ob.location = (x0 + w / 2, y0 + h / 2, 0)
    bv = ob.modifiers.new("b", "BEVEL"); bv.width = min(w, h) * R.uniform(0.04, 0.07); bv.segments = 3
    rm = ob.modifiers.new("r", "REMESH"); rm.mode = "VOXEL"; rm.voxel_size = vox; rm.use_smooth_shade = True
    t1 = bpy.data.textures.new("c", "CLOUDS"); t1.noise_scale = R.uniform(0.05, 0.08); t1.noise_depth = 4
    d1 = ob.modifiers.new("d1", "DISPLACE"); d1.texture = t1; d1.texture_coords = "OBJECT"; d1.strength = rough; d1.mid_level = 0.55
    t2 = bpy.data.textures.new("v", "VORONOI"); t2.noise_scale = R.uniform(0.035, 0.06)
    t2.color_mode = "INTENSITY"; t2.weight_1 = 1.0; t2.weight_2 = 0.0
    d2 = ob.modifiers.new("d2", "DISPACE".replace("DISPACE", "DISPLACE")); d2.texture = t2; d2.texture_coords = "OBJECT"; d2.strength = chip; d2.mid_level = 0.6
    me.materials.append(SM); ob.color = (1, 1, 1, 1)
    return ob

def mortar_plane(coll, x0, y0, w, h, z=0.006):
    bpy.ops.mesh.primitive_plane_add(size=1, location=(x0 + w / 2, y0 + h / 2, z))
    pl = bpy.context.active_object; pl.scale = (w, h, 1)
    for c in list(pl.users_collection): c.objects.unlink(pl)
    coll.objects.link(pl); pl.data.materials.append(MM)
    sd = pl.modifiers.new("s", "SUBSURF"); sd.subdivision_type = "SIMPLE"; sd.levels = sd.render_levels = 5
    tm = bpy.data.textures.new("m", "CLOUDS"); tm.noise_scale = 0.01
    dm = pl.modifiers.new("d", "DISPLACE"); dm.texture = tm; dm.texture_coords = "OBJECT"; dm.strength = 0.006
    return pl

def lights(elev=38, az=225, key=4.2):
    sun = bpy.data.lights.new("s", "SUN"); sun.energy = key; sun.angle = math.radians(5)
    so = bpy.data.objects.new("s", sun); sc.collection.objects.link(so)
    so.rotation_euler = (math.radians(90 - elev), 0, math.radians(az))
    fill = bpy.data.lights.new("f", "SUN"); fill.energy = 0.45; fill.angle = math.radians(50)
    fo = bpy.data.objects.new("f", fill); sc.collection.objects.link(fo); fo.rotation_euler = (math.radians(35), 0, math.radians(40))
    w = bpy.data.worlds.new("w"); sc.world = w; w.use_nodes = True
    w.node_tree.nodes["Background"].inputs["Color"].default_value = (0.30, 0.28, 0.27, 1)
    w.node_tree.nodes["Background"].inputs["Strength"].default_value = 0.25

def ortho_cam(cx, cy, scale, rx, ry):
    sc.render.resolution_x, sc.render.resolution_y = rx, ry
    cam = bpy.data.cameras.new("c"); cam.type = "ORTHO"; cam.ortho_scale = scale
    co = bpy.data.objects.new("c", cam); sc.collection.objects.link(co); co.location = (cx, cy, 3); sc.camera = co

def instance_x(coll):
    for dx in (-1, 0, 1):
        e = bpy.data.objects.new(f"i{dx}", None); e.instance_type = "COLLECTION"; e.instance_collection = coll
        e.location = (dx, 0, 0); sc.collection.objects.link(e)
    bpy.context.view_layer.layer_collection.children[coll.name].exclude = True

def blocks_row(coll, y0, h, depth, wmin, wmax, gap, **kw):
    x = R.uniform(0, 0.2); ws = []; t = 0
    while t < 1 - wmax * 0.8:
        w = R.uniform(wmin, wmax); ws.append(w); t += w
    ws.append(1 - t)
    if ws[-1] < wmin * 0.6: ws[-2] += ws[-1]; ws.pop()
    for w in ws:
        g = gap * R.uniform(0.8, 1.3)
        stone_block(coll, x + g / 2, y0, w - g, h, depth, **kw)
        x += w

if mode in ("trim_base", "trim_cap"):
    coll = bpy.data.collections.new("tile"); sc.collection.children.link(coll)
    if mode == "trim_base":
        H = 96 / 512
        # plinth course: deep blocks with a chamfered top edge, a thin weathered drip ledge above
        blocks_row(coll, 0.0, H * 0.78, 0.09, 0.28, 0.5, 0.012, top_chamfer=0.022)
        blocks_row(coll, H * 0.80, H * 0.20, 0.05, 0.35, 0.6, 0.010, top_chamfer=0.008)
        mortar_plane(coll, 0, -0.05, 1, H + 0.1)
        ortho_cam(0.5, H / 2, 1.0, 512 * 2, 96 * 2)
    else:
        H = 64 / 512
        # cornice: dentil-like lower band and an overhanging capstone with a chamfered underside
        blocks_row(coll, 0.0, H * 0.34, 0.05, 0.08, 0.12, 0.012)
        blocks_row(coll, H * 0.36, H * 0.64, 0.095, 0.3, 0.55, 0.012, bot_chamfer=0.02)
        mortar_plane(coll, 0, -0.05, 1, H + 0.1)
        ortho_cam(0.5, H / 2, 1.0, 512 * 2, 64 * 2)
    instance_x(coll)
    lights(elev=40, az=180 + 20)  # light from above so ledges read
    sc.render.filepath = out
    bpy.ops.render.render(write_still=True)

elif mode == "door":
    # carved gate pillar 1x2 units: ashlar courses either side of a recessed rune panel with ember-lit grooves
    coll = sc.collection
    W, H = 1.0, 2.0
    # big ashlar courses
    y = 0.0
    for i, hh in enumerate([0.30, 0.26, 0.26, 0.26, 0.26, 0.30, 0.36]):
        if 1 <= i <= 4:
            stone_block(coll, 0.0, y, 0.23, hh - 0.012, 0.11, top_chamfer=0.0)
            stone_block(coll, 0.77, y, 0.23, hh - 0.012, 0.11)
        else:
            stone_block(coll, 0.0, y, 1.0, hh - 0.012, 0.12, top_chamfer=0.03 if i == 6 else 0.0)
        y += hh
    # panel heightmap: dragon-eye sigil and rune columns, drawn in python into an image
    import numpy as np
    PW, PH = 256, 512
    yy, xx = np.mgrid[0:PH, 0:PW].astype(float)
    hgt = np.ones((PH, PW))
    def groove(mask, d=1.0):
        global hgt
        hgt = np.minimum(hgt, 1 - d * mask)
    cx, cy = PW / 2, PH * 0.55
    r = np.hypot(xx - cx, yy - cy)
    groove(((r > 70) & (r < 80)).astype(float))
    groove(((r > 54) & (r < 58)).astype(float), 0.6)
    eye = ((xx - cx) / 46) ** 2 + ((yy - cy) / 22) ** 2
    groove(((eye < 1) & (eye > 0.72)).astype(float))
    groove((((xx - cx) / 7) ** 2 + ((yy - cy) / 20) ** 2 < 1).astype(float))
    for k in range(8):
        a = k * math.pi / 4 + math.pi / 8
        px, py = cx + 92 * math.cos(a), cy + 92 * math.sin(a)
        groove((np.hypot(xx - px, yy - py) < 6).astype(float), 0.8)
    rr = random.Random(seed)
    for col in (40, PW - 40):
        for j in range(7):
            gy = 30 + j * 30
            if gy > cy - 100: break
            for _ in range(3):
                x1, y1 = col + rr.uniform(-12, 12), gy + rr.uniform(-10, 10)
                x2, y2 = col + rr.uniform(-12, 12), gy + rr.uniform(-10, 10)
                t = np.clip(((xx - x1) * (x2 - x1) + (yy - y1) * (y2 - y1)) / ((x2 - x1) ** 2 + (y2 - y1) ** 2 + 1e-6), 0, 1)
                dd = np.hypot(xx - (x1 + t * (x2 - x1)), yy - (y1 + t * (y2 - y1)))
                groove((dd < 2.6).astype(float), 0.9)
    # soften groove walls
    from numpy.fft import fft2, ifft2
    k = np.exp(-((np.fft.fftfreq(PH)[:, None] ** 2 + np.fft.fftfreq(PW)[None] ** 2) * (2 * math.pi * 1.4) ** 2 / 2))
    hgt = np.real(ifft2(fft2(hgt) * k))
    img = bpy.data.images.new("panel", PW, PH, float_buffer=True)
    px = np.zeros((PH, PW, 4), np.float32); px[..., 0] = px[..., 1] = px[..., 2] = hgt[::-1]; px[..., 3] = 1
    img.pixels = px.ravel(); img.pack()
    # panel slab
    bpy.ops.mesh.primitive_plane_add(size=1, location=(0.5, 0.30 + 1.04 / 2, 0.075))
    pn = bpy.context.active_object; pn.scale = (0.52, 1.02, 1)
    sd = pn.modifiers.new("s", "SUBSURF"); sd.subdivision_type = "SIMPLE"; sd.levels = sd.render_levels = 9
    tx = bpy.data.textures.new("ph", "IMAGE"); tx.image = img; tx.extension = "EXTEND"
    dp = pn.modifiers.new("d", "DISPLACE"); dp.texture = tx; dp.texture_coords = "UV"; dp.strength = 0.03; dp.mid_level = 1.0
    t1 = bpy.data.textures.new("pc", "CLOUDS"); t1.noise_scale = 0.06
    d1 = pn.modifiers.new("d1", "DISPLACE"); d1.texture = t1; d1.texture_coords = "OBJECT"; d1.strength = 0.004
    pm = SM.copy(); pn.data.materials.append(pm)
    N, L = pm.node_tree.nodes, pm.node_tree.links
    b = N["Principled BSDF"]
    it = N.new("ShaderNodeTexImage"); it.image = img; it.extension = "EXTEND"
    uv = N.new("ShaderNodeTexCoord"); L.new(uv.outputs["UV"], it.inputs["Vector"])
    er = N.new("ShaderNodeValToRGB")
    er.color_ramp.elements[0].position = 0.25; er.color_ramp.elements[0].color = (1.0, 0.32, 0.04, 1)
    er.color_ramp.elements[1].position = 0.75; er.color_ramp.elements[1].color = (0, 0, 0, 1)
    L.new(it.outputs["Color"], er.inputs["Fac"])
    L.new(er.outputs["Color"], b.inputs["Emission Color"]); b.inputs["Emission Strength"].default_value = 3.0
    # recess frame (darker mortar behind)
    mortar_plane(coll, -0.1, -0.1, 1.2, 2.2, z=0.006)
    # iron bands across the top course
    iron = bpy.data.materials.new("iron"); iron.use_nodes = True
    ib = iron.node_tree.nodes["Principled BSDF"]; ib.inputs["Base Color"].default_value = (0.05, 0.045, 0.042, 1)
    ib.inputs["Metallic"].default_value = 0.85; ib.inputs["Roughness"].default_value = 0.55
    for yb in (1.43, 1.51):
        bpy.ops.mesh.primitive_cube_add(size=1, location=(0.5, yb, 0.13)); o = bpy.context.active_object
        o.scale = (0.56, 0.035, 0.012); o.data.materials.append(iron)
        bv = o.modifiers.new("b", "BEVEL"); bv.width = 0.004
        for xr in (0.27, 0.5, 0.73):
            bpy.ops.mesh.primitive_uv_sphere_add(radius=0.012, location=(xr, yb, 0.137)); bpy.context.active_object.data.materials.append(iron)
    ortho_cam(0.5, 1.0, 2.0, 512, 1024)
    lights(elev=40, az=200)
    pt = bpy.data.lights.new("p", "POINT"); pt.energy = 18; pt.color = (1.0, 0.45, 0.15); pt.shadow_soft_size = 0.2
    po = bpy.data.objects.new("p", pt); sc.collection.objects.link(po); po.location = (0.5, -0.4, 0.6)
    sc.render.filepath = out
    bpy.ops.render.render(write_still=True)

elif mode == "torch":
    sc.render.film_transparent = True
    coll = sc.collection
    iron = bpy.data.materials.new("iron"); iron.use_nodes = True
    N, L = iron.node_tree.nodes, iron.node_tree.links
    ib = N["Principled BSDF"]; ib.inputs["Metallic"].default_value = 0.9; ib.inputs["Roughness"].default_value = 0.5
    tc = N.new("ShaderNodeTexCoord"); nz = N.new("ShaderNodeTexNoise"); nz.inputs["Scale"].default_value = 40; nz.inputs["Detail"].default_value = 10
    L.new(tc.outputs["Object"], nz.inputs["Vector"])
    rp = N.new("ShaderNodeValToRGB"); rp.color_ramp.elements[0].color = (0.035, 0.03, 0.028, 1)
    rp.color_ramp.elements[1].color = (0.16, 0.08, 0.04, 1); rp.color_ramp.elements[0].position = 0.45
    L.new(nz.outputs["Fac"], rp.inputs["Fac"]); L.new(rp.outputs["Color"], ib.inputs["Base Color"])
    bm_ = N.new("ShaderNodeBump"); bm_.inputs["Strength"].default_value = 0.4; L.new(nz.outputs["Fac"], bm_.inputs["Height"]); L.new(bm_.outputs["Normal"], ib.inputs["Normal"])
    def add(op, mat, **kw):
        op(**kw); o = bpy.context.active_object; o.data.materials.append(mat); return o
    # units: 1 unit = 32 px at 96x160 (camera 3 x 5 units). y up, z towards camera.
    plate = add(bpy.ops.mesh.primitive_cube_add, iron, size=1, location=(0, -1.1, 0.05)); plate.scale = (0.75, 1.35, 0.1)
    b = plate.modifiers.new("b", "BEVEL"); b.width = 0.06; b.segments = 3
    for yy in (-0.6, -1.6):
        add(bpy.ops.mesh.primitive_uv_sphere_add, iron, radius=0.09, location=(0, yy, 0.12))
    arm = add(bpy.ops.mesh.primitive_cylinder_add, iron, radius=0.09, depth=0.9, location=(0, -0.35, 0.45))
    arm.rotation_euler = (math.radians(-35), 0, 0)
    ring = add(bpy.ops.mesh.primitive_torus_add, iron, major_radius=0.42, minor_radius=0.06, location=(0, 0.1, 0.7))
    ring.rotation_euler = (math.radians(-72), 0, 0)
    cup = add(bpy.ops.mesh.primitive_cone_add, iron, radius1=0.2, radius2=0.5, depth=0.5, location=(0, -0.05, 0.7))
    cup.rotation_euler = (math.radians(-90), 0, 0)
    sb = cup.modifiers.new("s", "SOLIDIFY"); sb.thickness = 0.04
    for a in range(4):  # cage prongs
        ang = a * math.pi / 2 + math.pi / 4
        p = add(bpy.ops.mesh.primitive_cylinder_add, iron, radius=0.035, depth=0.55, location=(0.42 * math.cos(ang), 0.35, 0.7 + 0.42 * math.sin(ang)))
        p.rotation_euler = (math.radians(-90), 0, 0)
    # coals
    coal = bpy.data.materials.new("coal"); coal.use_nodes = True
    cb = coal.node_tree.nodes["Principled BSDF"]; cb.inputs["Base Color"].default_value = (0.02, 0.015, 0.012, 1)
    cb.inputs["Emission Color"].default_value = (1.0, 0.25, 0.03, 1); cb.inputs["Emission Strength"].default_value = 2.5
    for i in range(7):
        add(bpy.ops.mesh.primitive_ico_sphere_add, coal, subdivisions=1, radius=R.uniform(0.1, 0.16),
            location=(R.uniform(-0.25, 0.25), 0.22, 0.7 + R.uniform(-0.2, 0.2)))
    # flame: tapered emission volume shell, noise-cut alpha, animated through 4D noise W
    fm = bpy.data.materials.new("flame"); fm.use_nodes = True; fm.blend_method = "BLEND"
    N, L = fm.node_tree.nodes, fm.node_tree.links
    N.remove(N["Principled BSDF"]); outn = N["Material Output"]
    tc = N.new("ShaderNodeTexCoord")
    nz = N.new("ShaderNodeTexNoise"); nz.noise_dimensions = "4D"; nz.inputs["Scale"].default_value = 2.2; nz.inputs["Detail"].default_value = 6
    mp = N.new("ShaderNodeMapping"); mp.inputs["Scale"].default_value = (1.6, 0.7, 1.6)
    L.new(tc.outputs["Object"], mp.inputs["Vector"]); L.new(mp.outputs["Vector"], nz.inputs["Vector"])
    sep = N.new("ShaderNodeSeparateXYZ"); L.new(tc.outputs["Generated"], sep.inputs["Vector"])
    # density falls off with height (generated z of the flame = its local up, we use y as up)
    h = N.new("ShaderNodeMath"); h.operation = "SUBTRACT"; h.inputs[0].default_value = 1.15
    L.new(sep.outputs["Z"], h.inputs[1])
    mul = N.new("ShaderNodeMath"); mul.operation = "MULTIPLY"; L.new(nz.outputs["Fac"], mul.inputs[0]); L.new(h.outputs[0], mul.inputs[1])
    rmp = N.new("ShaderNodeValToRGB"); e = rmp.color_ramp.elements
    e[0].position = 0.30; e[0].color = (0, 0, 0, 1)
    e[1].position = 0.75; e[1].color = (1.0, 0.85, 0.45, 1)
    e2 = rmp.color_ramp.elements.new(0.45); e2.color = (0.9, 0.22, 0.02, 1)
    e3 = rmp.color_ramp.elements.new(0.58); e3.color = (1.0, 0.55, 0.10, 1)
    L.new(mul.outputs[0], rmp.inputs["Fac"])
    em = N.new("ShaderNodeEmission"); em.inputs["Strength"].default_value = 5.0; L.new(rmp.outputs["Color"], em.inputs["Color"])
    al = N.new("ShaderNodeMapRange"); al.inputs["From Min"].default_value = 0.30; al.inputs["From Max"].default_value = 0.42
    L.new(mul.outputs[0], al.inputs["Value"])
    tr = N.new("ShaderNodeBsdfTransparent"); mix = N.new("ShaderNodeMixShader")
    L.new(al.outputs["Result"], mix.inputs[0]); L.new(tr.outputs[0], mix.inputs[1]); L.new(em.outputs[0], mix.inputs[2])
    L.new(mix.outputs[0], outn.inputs["Surface"])
    W = nz.inputs["W"]
    flames = []
    for k in range(5):  # stacked translucent shells give depth
        bpy.ops.mesh.primitive_uv_sphere_add(radius=1, segments=32, ring_count=24, location=(0, 1.15, 0.7 - k * 0.03))
        f = bpy.context.active_object
        for v in f.data.vertices:
            t = (v.co.z + 1) / 2
            v.co.x *= 0.38 * (1 - t) ** 0.7; v.co.y *= 0.38 * (1 - t) ** 0.7; v.co.z = v.co.z
        f.rotation_euler = (math.radians(-90), 0, 0)
        f.scale = (1 - k * 0.12, 1 - k * 0.12, 1.15 - k * 0.1)
        f.data.materials.append(fm); flames.append(f)
    pt = bpy.data.lights.new("p", "POINT"); pt.energy = 25; pt.color = (1.0, 0.5, 0.18); pt.shadow_soft_size = 0.3
    po = bpy.data.objects.new("p", pt); sc.collection.objects.link(po); po.location = (0, 1.0, 0.9)
    key = bpy.data.lights.new("k", "SUN"); key.energy = 1.2
    ko = bpy.data.objects.new("k", key); sc.collection.objects.link(ko); ko.rotation_euler = (math.radians(30), math.radians(-25), 0)
    w = bpy.data.worlds.new("w"); sc.world = w; w.use_nodes = True
    w.node_tree.nodes["Background"].inputs["Strength"].default_value = 0.15
    ortho_cam(0, 0.0, 5.0, 192, 320)
    sc.camera.location = (0, 0.0, 6)
    base = out[:-4] if out.endswith(".png") else out
    for f in flames:
        f.hide_render = True  # flames are painted per frame in make_torch.py (cleaner, controllable flicker)
    for fr in range(1):
        W.default_value = fr * 0.33 + seed * 0.1
        sc.render.filepath = f"{base}_{fr}.png"
        bpy.ops.render.render(write_still=True)
