"""Fairy Village buildings + fountains. One asset per Blender process.

  blender -b -P fv_buildings.py -- --key queens_tree_hall --mode sprite|hero|both [--samples 96] [--preview]
"""
import bpy, bmesh, math, os, random, sys, json
from mathutils import Vector, Euler, Matrix, noise
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import fv_common as C

OUT = "/workspace/fairy_village"
KEY = C.arg("--key", "queens_tree_hall")
MODE = C.arg("--mode", "both")
SAMPLES = int(C.arg("--samples", 96))
PREVIEW = bool(C.arg("--preview", False))
FRAMES = int(C.arg("--frames", 10))
FRAME_ONLY = C.arg("--frame")

SPECS = {
    "queens_tree_hall": {"W": 9, "D": 9, "name": "The Queen's Tree-Hall", "door": (4, 8)},
    "moonpetal_inn": {"W": 10, "D": 8, "name": "The Moonpetal Inn", "door": (4, 7)},
    "mushroom_apothecary": {"W": 7, "D": 7, "name": "Tumbleroot's Mushroom Apothecary", "door": (3, 6)},
    "moonstone_fountain": {"W": 5, "D": 5, "name": "Moonstone Fountain", "anim": True},
    "lily_fountain": {"W": 3, "D": 3, "name": "Lily Fountain", "anim": True},
}
SP = SPECS[KEY]
W, D = SP["W"] * C.T, SP["D"] * C.T
CX, CY = W / 2, -D / 2
random.seed(hash(KEY) % 10007)


def col_new(name):
    c = bpy.data.collections.new(name); bpy.context.scene.collection.children.link(c); return c


# ============================================================ shared decorations
def lantern(name, loc, col, scale=1.0, hang=0.0, glow=(1.0, 0.72, 0.35), strength=14.0, light=True):
    s = scale
    parts = []
    gold = C.gold_mat()
    cage_top = C.lathe(name + "_top", [(0.001, 0.36 * s), (0.10 * s, 0.33 * s), (0.16 * s, 0.27 * s), (0.17 * s, 0.25 * s)],
                       segs=16, mat=gold, col=col)
    base = C.cyl(name + "_base", 0.13 * s, 0.04 * s, (0, 0, -0.02 * s), segs=16, mat=gold, col=col)
    glass = C.uvsphere(name + "_glow", 0.12 * s, (0, 0, 0.12 * s), segs=20, rings=12, mat=C.glow_mat("FV_LanternGlow", glow, strength), col=col,
                       scale=(1, 1, 1.25))
    bars = []
    for i in range(6):
        a = i * math.pi / 3
        bars.append(C.cyl(f"{name}_bar{i}", 0.008 * s, 0.27 * s, (0.15 * s * math.cos(a), 0.15 * s * math.sin(a), 0.125 * s), segs=6, mat=gold, col=col))
    ring = C.torus(name + "_ring", 0.035 * s, 0.008 * s, (0, 0, 0.39 * s), mat=gold, col=col, segs=12, rsegs=6, rot=(math.pi / 2, 0, 0))
    o = C.join([cage_top, base, glass] + bars + [ring], name)
    o.location = loc
    if hang > 0:
        ch = C.tube_curve(name + "_chain", [(loc[0], loc[1], loc[2] + 0.4 * s), (loc[0], loc[1], loc[2] + 0.4 * s + hang / 2),
                                            (loc[0], loc[1], loc[2] + 0.4 * s + hang)], radius=0.008 * s, mat=gold, col=col)
    if light:
        L = bpy.data.lights.new(name + "_L", "POINT"); L.energy = 25 * s * s; L.color = glow; L.shadow_soft_size = 0.15
        lo = bpy.data.objects.new(name + "_L", L); lo.location = (loc[0], loc[1], loc[2] + 0.13 * s); col.objects.link(lo)
    return o


def lamp_post(name, loc, col, h=2.2, side=1):
    gold = C.gold_mat()
    wood = C.bark_mat("FV_BarkLight", (0.22, 0.14, 0.08), (0.45, 0.32, 0.2))
    # curling living-wood post
    sd = side
    pts = [(loc[0], loc[1], 0), (loc[0] + 0.05 * sd, loc[1], h * 0.4), (loc[0] - 0.04 * sd, loc[1], h * 0.75), (loc[0] + 0.1 * sd, loc[1], h * 0.95),
           (loc[0] + 0.32 * sd, loc[1], h * 1.02), (loc[0] + 0.42 * sd, loc[1], h * 0.92)]
    post = C.tube_curve(name + "_post", pts, radius=0.07, mat=wood, col=col, radii=[1.4, 1.0, 0.9, 0.7, 0.55, 0.4])
    lantern(name + "_lan", (loc[0] + 0.42 * sd, loc[1], h * 0.92 - 0.5), col, scale=1.1, hang=0.1)
    leaves(name + "_lv", (loc[0], loc[1], h * 0.95), 0.25, col, n=40)


_LEAF = {}


def leaf_proto(col, kind="leaf"):
    if kind in _LEAF:
        return _LEAF[kind]
    bm = bmesh.new(); uvl = bm.loops.layers.uv.new("UVMap")
    if kind == "leaf":
        pts = [(0, 0), (0.25, 0.32), (0.6, 0.38), (1.0, 0.0), (0.6, -0.38), (0.25, -0.32)]
        mat = C.leafcard_mat()
        s = 0.16
    else:
        pts = [(0, 0), (0.35, 0.4), (0.8, 0.42), (1.0, 0.0), (0.8, -0.42), (0.35, -0.4)]
        if kind == "blossom_l":
            mat = C.petal_mat("FV_BlossomCardL", (0.62, 0.48, 1.0), (0.95, 0.9, 1.0), glow=(0.7, 0.6, 1.0), glow_strength=0.35)
        else:
            mat = C.petal_mat("FV_BlossomCard", (1.0, 0.45, 0.72), (1.0, 0.90, 0.95), glow=(1.0, 0.6, 0.85), glow_strength=0.3)
        s = 0.1
    vs = [bm.verts.new((u * s, w * s * 0.6, 0.15 * s * u * u)) for (u, w) in pts]
    f = bm.faces.new(vs)
    for lp, (u, w) in zip(f.loops, pts):
        lp[uvl].uv = (w + 0.5, u)
    o = C.obj_from_bm(bm, "PROTO_" + kind, mat, col)
    o.hide_render = True; o.hide_viewport = True
    _LEAF[kind] = o
    return o


def foliage(target, count, col, kind="leaf", size=1.0, seed=1):
    """Instance real leaf cards over the surface of `target` (particle hair, rendered as objects)."""
    proto = leaf_proto(col, kind)
    ps = target.modifiers.new(f"Fol_{kind}", "PARTICLE_SYSTEM")
    st = ps.particle_system.settings
    st.type = "HAIR"; st.count = count; st.hair_length = 1.0; st.use_advanced_hair = True
    st.render_type = "OBJECT"; st.instance_object = proto
    st.particle_size = size; st.size_random = 0.5
    st.use_rotations = True; st.rotation_mode = "NOR_TAN"; st.phase_factor_random = 2.0; st.rotation_factor_random = 0.85
    st.use_rotation_instance = True
    st.emit_from = "FACE"; st.use_emit_random = True
    ps.particle_system.seed = seed
    target.show_instancer_for_render = True
    return ps


def leaves(name, loc, r, col, n=60):
    blob = C.ico(name, r, loc, sub=2, mat=C.leaf_mat(), col=col, scale=(1, 1, 0.8))
    C.displace(blob, r * 0.35, r * 0.8)
    foliage(blob, n, col, size=r * 2.2)
    return blob


def scatter_flowers(col, n, rect_fn, seed=3, glow_some=True, palette=None):
    rnd = random.Random(seed)
    palette = palette or [((1.0, 0.62, 0.82), (1, 0.93, 0.97)), ((0.72, 0.62, 1.0), (0.95, 0.92, 1.0)),
                          ((1.0, 0.95, 0.75), (1, 1, 0.95)), ((0.55, 0.85, 1.0), (0.95, 1, 1))]
    out = []
    for i in range(n):
        p = rect_fn(rnd)
        if p is None:
            continue
        cb, ct = palette[rnd.randrange(len(palette))]
        glow = (cb[0], cb[1], cb[2]) if (glow_some and rnd.random() < 0.3) else None
        f = C.flower(f"flw{seed}_{i}", (p[0], p[1], p[2] if len(p) > 2 else 0.12 + rnd.random() * 0.1), r=0.07 + rnd.random() * 0.07,
                     petals=rnd.choice([5, 6, 8]), c_base=cb, c_tip=ct, col=col, glow=glow, rot=rnd.random() * 6.28,
                     tilt=rnd.uniform(-0.3, 0.3))
        # stem
        C.tube_curve(f"stm{seed}_{i}", [(p[0], p[1], 0), (p[0] + 0.01, p[1], f.location.z * 0.5), (p[0], p[1], f.location.z)],
                     radius=0.008, mat=C.principled("FV_Stem", (0.2, 0.42, 0.12), rough=0.6), col=col, res=4, bevel_res=2)
        out.append(f)
    return out


def grass_tufts(col, n, rect_fn, seed=5):
    rnd = random.Random(seed)
    mat = C.principled("FV_Grass", (0.22, 0.45, 0.12), rough=0.55, sss=0.2)
    for i in range(n):
        p = rect_fn(rnd)
        if p is None:
            continue
        bm = bmesh.new()
        for k in range(7):
            a = rnd.random() * 6.28; h = 0.12 + rnd.random() * 0.18; lean = rnd.uniform(0.02, 0.1)
            b0 = bm.verts.new((math.cos(a) * 0.015, math.sin(a) * 0.015, 0)); b1 = bm.verts.new((math.cos(a + 1.5) * 0.015, math.sin(a + 1.5) * 0.015, 0))
            tip = bm.verts.new((math.cos(a) * lean, math.sin(a) * lean, h))
            bm.faces.new((b0, b1, tip))
        o = C.obj_from_bm(bm, f"tuft{seed}_{i}", mat, col)
        o.location = (p[0], p[1], 0)


def rock(name, loc, r, col, mat=None, squash=0.6):
    o = C.ico(name, r, loc, sub=3, mat=mat or C.stone_mat("FV_Rock", (0.5, 0.52, 0.55), (0.75, 0.75, 0.78), moss_amt=0.5),
              col=col, scale=(1, 0.9, squash))
    C.displace(o, r * 0.35, r * 1.2)
    o.rotation_euler = (0, 0, random.random() * 6.28)
    return o


# ============================================================ The Queen's Tree-Hall
def build_tree_hall(col):
    bark = C.bark_mat("FV_Bark", (0.17, 0.10, 0.06), (0.43, 0.30, 0.19), (0.22, 0.38, 0.10))
    rootbark = C.bark_mat("FV_BarkRoot", (0.16, 0.10, 0.06), (0.40, 0.28, 0.18), (0.30, 0.22, 0.14))
    stone = C.stone_mat("FV_Moonstone", moss_amt=0.0, emit_veins=(0.45, 0.75, 1.0))
    wood = C.wood_mat()
    gold = C.gold_mat()
    tx, ty = CX, -D + 0.9 + 2.35    # trunk centre: door face sits in the footprint's south row
    # ---------- trunk (lathe with lobes + twist)
    segs, rings = 96, 56
    H = 9.2
    prof = []
    for k in range(rings + 1):
        z = H * k / rings
        t = z / H
        r = 2.55 + 1.9 * math.exp(-z * 1.6) - 0.35 * t + 0.25 * math.exp(-((z - 7.6) ** 2) / 1.2)
        prof.append((r, z))
    bm = bmesh.new()
    grid = []
    for k, (r, z) in enumerate(prof):
        row = []
        for i in range(segs):
            a = 2 * math.pi * i / segs + 0.35 * z / H          # twist
            lobe = 0.13 * math.sin(5 * a + 0.8) * (1.0 - 0.6 * z / H) + 0.05 * math.sin(11 * a + z)
            n3 = noise.noise(Vector((math.cos(a) * 1.3, math.sin(a) * 1.3, z * 0.45))) * 0.12
            groove = 0.035 * math.sin(38 * a + 3.0 * noise.noise(Vector((math.cos(a) * 3, math.sin(a) * 3, z * 0.3))))
            rr = r * (1 + lobe + n3 + groove)
            row.append(bm.verts.new((tx + rr * math.cos(a), ty + rr * math.sin(a), z - 0.15)))
        grid.append(row)
    for k in range(rings):
        for i in range(segs):
            j = (i + 1) % segs
            bm.faces.new((grid[k][i], grid[k][j], grid[k + 1][j], grid[k + 1][i]))
    bm.faces.new(list(reversed(grid[-1])))
    bm.faces.new(grid[0])
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    trunk = C.obj_from_bm(bm, "trunk", bark, col)
    C.add_mod_subsurf(trunk, 1)
    C.displace(trunk, 0.08, 0.35)
    # door cut (arched)
    front_r = 2.55 + 1.9 * math.exp(-0.0) * 0.6
    dw, dh = 1.7, 2.9
    cut = bmesh.new()
    prof2 = []
    for i in range(17):
        a = math.pi * i / 16
        prof2.append((dw / 2 * math.cos(a), dh - dw / 2 + dw / 2 * math.sin(a)))
    pts = [(dw / 2, 0)] + prof2 + [(-dw / 2, 0)]
    vf = [cut.verts.new((tx + x, ty - 6.0, z - 0.2)) for x, z in pts]
    vb = [cut.verts.new((tx + x, ty - 1.2, z - 0.2)) for x, z in pts]
    cut.faces.new(vf); cut.faces.new(list(reversed(vb)))
    n = len(pts)
    for i in range(n):
        j = (i + 1) % n
        cut.faces.new((vf[i], vb[i], vb[j], vf[j]))
    cutter = C.obj_from_bm(cut, "door_cutter", None, col, smooth=False)
    cutter.hide_render = True; cutter.display_type = "WIRE"
    bo = trunk.modifiers.new("DoorCut", "BOOLEAN"); bo.object = cutter; bo.solver = "EXACT"
    # find the trunk's front surface y at door height
    fy = ty - (prof[3][0] * (1 + 0.13 * math.sin(5 * (-math.pi / 2) + 0.8)))
    door_y = ty - 2.35
    # inner recess walls (warm interior), door leaves
    recess = C.box("door_recess_back", (dw, 0.1, dh), (tx, door_y + 0.05, dh / 2 - 0.2), C.principled("FV_DoorDark", (0.05, 0.03, 0.02)), col)
    # double door with planks and gold hinges, ajar glow
    for side in (-1, 1):
        planks = []
        for p in range(4):
            x = tx + side * (0.11 + p * 0.205)
            hgt = dh - 0.2 - (abs(side * (0.11 + p * 0.205)) ** 2) * 0.45
            planks.append(C.box(f"plank{side}{p}", (0.19, 0.07, hgt), (x, door_y - 0.03, hgt / 2 - 0.2), wood, col, bevel=0.015))
        for hz in (0.5, 1.9):
            C.box(f"hinge{side}{hz}", (0.62, 0.02, 0.07), (tx + side * 0.45, door_y - 0.08, hz), gold, col, bevel=0.01)
        C.uvsphere(f"knob{side}", 0.045, (tx + side * 0.13, door_y - 0.1, 1.05), mat=gold, col=col)
    # glowing gap
    C.box("door_gap", (0.035, 0.03, dh - 0.4), (tx, door_y - 0.02, dh / 2 - 0.35), C.glow_mat("FV_WarmGlow", (1.0, 0.65, 0.3), 12), col)
    # moonstone arch frame (blocks)
    for i in range(15):
        a = math.pi * i / 14
        x = (dw / 2 + 0.2) * math.cos(a); z = dh - dw / 2 - 0.2 + (dw / 2 + 0.2) * math.sin(a)
        b = C.box(f"arch{i}", (0.34, 0.5, 0.26), (tx + x, door_y - 0.25, z), stone, col, bevel=0.04, rot=(0, -a + math.pi / 2, 0))
    for side in (-1, 1):
        for k in range(4):
            C.box(f"jamb{side}{k}", (0.32, 0.5, 0.42), (tx + side * (dw / 2 + 0.2), door_y - 0.25, 0.05 + k * 0.44), stone, col, bevel=0.04)
    # keystone crescent emblem
    cres_a = C.cyl("cres_a", 0.36, 0.08, (0, 0, 0), segs=48, mat=gold, col=col)
    cres_b = C.cyl("cres_b", 0.31, 0.3, (0.13, 0, 0.0), segs=48, mat=None, col=col)
    cres_b.hide_render = True
    bb = cres_a.modifiers.new("cr", "BOOLEAN"); bb.object = cres_b; bb.solver = "EXACT"
    cres_a.rotation_euler = (math.pi / 2, 0, 0); cres_a.location = (tx, door_y - 0.52, dh + 0.45)
    cres_b.parent = cres_a
    C.ico("moongem", 0.11, (tx - 0.08, door_y - 0.58, dh + 0.45), sub=3, mat=C.glow_mat("FV_MoonGem", (0.55, 0.85, 1.0), 9), col=col)
    # steps
    for k in range(3):
        C.box(f"step{k}", (2.6 - k * 0.35, 0.55, 0.16), (tx, door_y - 0.75 - (2 - k) * 0.5, 0.08 + k * 0.16 - 0.16), stone, col, bevel=0.04)
    # ---------- windows (round, warm)
    for i, (ang, z, r) in enumerate([(-115, 3.9, 0.45), (-62, 5.2, 0.42), (-92, 6.6, 0.38), (-140, 6.0, 0.33), (-35, 3.2, 0.34)]):
        a = math.radians(ang)
        rr = 2.55 + 1.9 * math.exp(-z * 1.6) - 0.35 * z / H + 0.18
        px, py = tx + rr * math.cos(a), ty + rr * math.sin(a)
        rot = (math.pi / 2, 0, a + math.pi / 2)
        C.torus(f"win_fr{i}", r, 0.06, (px, py, z), mat=wood, col=col, rot=rot)
        g = C.cyl(f"win_gl{i}", r, 0.05, (px, py, z), segs=32, mat=C.window_mat(), col=col)
        g.rotation_euler = rot
        bar = C.box(f"win_bar{i}", (r * 2, 0.04, 0.04), (px, py, z), wood, col); bar.rotation_euler = (0, 0, a + math.pi / 2)
        bar2 = C.box(f"win_bar2{i}", (0.04, 0.04, r * 2), (px, py, z), wood, col); bar2.rotation_euler = (0, 0, a + math.pi / 2)
        # flower box under each window
        fb = C.box(f"win_box{i}", (r * 2.2, 0.32, 0.22), (px + 0.2 * math.cos(a), py + 0.2 * math.sin(a), z - r - 0.15), wood, col, bevel=0.02)
        fb.rotation_euler = (0, 0, a + math.pi / 2)
        for k in range(5):
            u = (k - 2) / 2 * r * 0.9
            fx = px + 0.3 * math.cos(a) + u * math.cos(a + math.pi / 2)
            fyy = py + 0.3 * math.sin(a) + u * math.sin(a + math.pi / 2)
            C.flower(f"wf{i}{k}", (fx, fyy, z - r - 0.0), r=0.09, c_base=[(1, 0.6, 0.8), (0.75, 0.6, 1), (1, 0.95, 0.7)][k % 3],
                     c_tip=(1, 0.97, 0.98), col=col)
    # ---------- glowing bracket fungi + ivy strands on the trunk
    rndf = random.Random(41)
    for i in range(16):
        a = math.radians(rndf.uniform(-200, 20)); z = rndf.uniform(1.0, 7.0)
        if abs(math.degrees(a) + 90) < 22 and z < 4:
            continue
        rr = 2.55 + 1.9 * math.exp(-z * 1.6) - 0.35 * z / H + 0.1
        for q in range(rndf.randint(1, 3)):
            sz = rndf.uniform(0.18, 0.36)
            sz *= 0.7
            f = C.lathe(f"fung{i}_{q}", [(0.001, 0.05), (sz * 0.6, 0.06), (sz, 0.02), (sz * 0.98, -0.03), (sz * 0.5, -0.04), (0.001, -0.03)],
                        segs=24, mat=C.principled("FV_Fungus", (0.85, 0.55, 0.30), rough=0.5, emit=(1.0, 0.6, 0.25), emit_strength=0.5, sss=0.4),
                        col=col)
            f.scale = (1, 0.65, 1)
            f.location = (tx + rr * math.cos(a), ty + rr * math.sin(a), z - q * 0.22)
            f.rotation_euler = (0, 0, a)
    ivy_mat = C.leafcard_mat("FV_Ivy", ((0.05, 0.2, 0.05), (0.15, 0.4, 0.1), (0.3, 0.55, 0.15)))
    for i in range(9):
        a0 = math.radians(rndf.uniform(-200, 20))
        if abs(math.degrees(a0) + 90) < 25:
            continue
        pts = []
        for k in range(10):
            z = 7.6 - k * rndf.uniform(0.45, 0.7)
            a = a0 + 0.08 * math.sin(k)
            rr = 2.55 + 1.9 * math.exp(-max(z, 0) * 1.6) - 0.35 * z / H + 0.12
            pts.append((tx + rr * math.cos(a), ty + rr * math.sin(a), max(z, 0.2)))
        iv = C.tube_curve(f"ivy{i}", pts, radius=0.025, mat=C.principled("FV_Vine", (0.15, 0.25, 0.08)), col=col)
        iv2 = C.apply_mods(iv)
        foliage(iv2, 160 if not PREVIEW else 60, col, "leaf", size=1.3, seed=200 + i)
    # ---------- spiral stair with railing on the east side
    for k in range(30):
        t = k / 29
        a = math.radians(-40 + 200 * t)
        z = 0.15 + 5.2 * t
        rr = 2.55 + 1.9 * math.exp(-z * 1.6) - 0.35 * z / H + 0.75
        px, py = tx + rr * math.cos(a), ty + rr * math.sin(a)
        pl = C.box(f"stair{k}", (1.05, 0.34, 0.08), (px, py, z), wood, col, bevel=0.012)
        pl.rotation_euler = (0, 0, a)
        if k % 3 == 0:
            ox, oy = tx + (rr + 0.48) * math.cos(a), ty + (rr + 0.48) * math.sin(a)
            C.cyl(f"rail_p{k}", 0.035, 0.9, (ox, oy, z + 0.45), segs=8, mat=wood, col=col)
    rail = []
    for k in range(31):
        t = k / 30; a = math.radians(-40 + 200 * t); z = 0.15 + 5.2 * t
        rr = 2.55 + 1.9 * math.exp(-z * 1.6) - 0.35 * z / H + 1.23
        rail.append((tx + rr * math.cos(a), ty + rr * math.sin(a), z + 0.9))
    C.tube_curve("rail", rail, radius=0.04, mat=wood, col=col, res=4)
    # small balcony at the top of the stair
    a = math.radians(160); z = 5.35
    rr = 2.55 + 1.9 * math.exp(-z * 1.6) - 0.35 * z / H + 0.9
    bal = C.cyl("balcony", 1.2, 0.12, (tx + rr * math.cos(a), ty + rr * math.sin(a), z), segs=40, mat=wood, col=col)
    C.torus("balcony_rail", 1.15, 0.035, (tx + rr * math.cos(a), ty + rr * math.sin(a), z + 0.8), mat=wood, col=col)
    # ---------- roots
    rnd = random.Random(11)
    for i in range(11):
        a = 2 * math.pi * i / 11 + rnd.uniform(-0.15, 0.15)
        if abs(math.degrees(a) % 360 - 270) < 22:
            continue          # keep the door clear
        L = rnd.uniform(2.6, 4.2)
        r0 = 3.3
        ca, sa = math.cos(a), math.sin(a)
        lim = min([((W - 0.2 - tx) / ca) if ca > 1e-3 else 99, ((0.2 - tx) / ca) if ca < -1e-3 else 99,
                   ((-0.2 - ty) / sa) if sa > 1e-3 else 99, ((-D + 0.2 - ty) / sa) if sa < -1e-3 else 99])
        L = max(1.2, min(L, lim - r0 * 0.75))
        pts = []
        for k in range(6):
            t = k / 5
            rr = r0 * 0.75 + L * t
            z = 1.2 * (1 - t) ** 1.5 + 0.25 * math.sin(t * math.pi) - 0.25 * t
            aa = a + 0.25 * math.sin(t * 3 + i)
            pts.append((tx + rr * math.cos(aa), ty + rr * math.sin(aa), z))
        C.tube_curve(f"root{i}", pts, radius=0.55, mat=rootbark, col=col, radii=[1.0, 0.8, 0.6, 0.42, 0.28, 0.12])
    # ---------- branches + canopy
    canopy = []
    rnd = random.Random(21)
    clusters = []
    for i in range(9):
        a = 2 * math.pi * i / 9 + 0.3
        dist = rnd.uniform(3.6, 5.6)
        h = rnd.uniform(9.0, 10.6)
        clusters.append((tx + dist * math.cos(a), ty + 2.2 + dist * math.sin(a) * 0.8, h, rnd.uniform(2.3, 2.9)))
    for i in range(5):
        a = 2 * math.pi * i / 5 + 1.0
        clusters.append((tx + 2.0 * math.cos(a), ty + 2.4 + 2.0 * math.sin(a), rnd.uniform(11.0, 12.0), rnd.uniform(2.4, 2.9)))
    clusters.append((tx, ty + 2.3, 12.6, 2.6))
    for i, (x, y, z, r) in enumerate(clusters):
        # branch
        a = math.atan2(y - ty, x - tx)
        pts = [(tx + 1.3 * math.cos(a), ty + 1.3 * math.sin(a), 7.4), ((tx + x) / 2, (ty + y) / 2, (7.6 + z) / 2 + 0.4), (x, y, z - r * 0.4)]
        C.tube_curve(f"branch{i}", pts, radius=0.55, mat=bark, col=col, radii=[1.0, 0.6, 0.25])
        cl = C.ico(f"canopy{i}", r, (x, y, z), sub=3, mat=C.leaf_mat("FV_CanopyCore", (0.04, 0.13, 0.03), (0.16, 0.32, 0.07), bl_amt=0.05),
                   col=col, scale=(1.1, 1.0, 0.72))
        C.displace(cl, r * 0.45, 0.9, tex_type="VORONOI")
        foliage(cl, 6500 if not PREVIEW else 2500, col, "leaf", size=2.4, seed=i + 1)
        foliage(cl, 1400 if not PREVIEW else 450, col, "blossom" if i % 3 else "blossom_l", size=2.8, seed=i + 101)
        canopy.append(cl)
    # wisteria drapes (glowing lilac / pink blossoms hanging from the canopy rim)
    wis = [C.petal_mat("FV_Wisteria_a", (0.62, 0.45, 1.0), (0.92, 0.85, 1.0), glow=(0.6, 0.45, 1.0), glow_strength=0.6),
           C.petal_mat("FV_Wisteria_b", (1.0, 0.55, 0.8), (1.0, 0.9, 0.96), glow=(1.0, 0.5, 0.8), glow_strength=0.5)]
    rndw = random.Random(31)
    for i, (x, y, z, r) in enumerate(clusters[:9]):
        for k in range(5):
            a = rndw.random() * 6.28
            sx, sy, sz = x + r * 0.8 * math.cos(a), y + r * 0.75 * math.sin(a), z - r * 0.45
            L = rndw.uniform(1.2, 2.6)
            bm = bmesh.new(); uvl = bm.loops.layers.uv.new("UVMap")
            nfl = int(L * 14)
            for j in range(nfl):
                t = j / nfl
                cz = sz - L * t
                rad = 0.22 * (1 - t) + 0.05
                for q in range(3):
                    aa = rndw.random() * 6.28
                    cx2, cy2 = sx + rad * math.cos(aa) * rndw.random(), sy + rad * math.sin(aa) * rndw.random()
                    sz2 = 0.06 * (1 - 0.5 * t)
                    vs = [bm.verts.new((cx2 + dx * sz2, cy2 + dy * sz2 * 0.4, cz + dz * sz2)) for dx, dy, dz in
                          ((0, 0, 0.6), (0.6, 0, 0), (0, 0, -0.6), (-0.6, 0, 0))]
                    f = bm.faces.new(vs)
                    for lp, uv in zip(f.loops, ((0.5, 1), (1, 0.5), (0.5, 0), (0, 0.5))):
                        lp[uvl].uv = uv
            o = C.obj_from_bm(bm, f"wis{i}_{k}", wis[(i + k) % 2], col)
    # hanging lanterns + fairy-light strands from the canopy edge
    for i, (x, y, z, r) in enumerate(clusters[:9]):
        if i % 2 == 0:
            lantern(f"hl{i}", (x * 0.9 + tx * 0.1, y * 0.9 + ty * 0.1, z - r * 0.72 - 0.9), col, scale=1.25, hang=0.8)
    lights = C.glow_mat("FV_FairyLight", (1.0, 0.85, 0.55), 18)
    for i in range(len(clusters[:9])):
        x0, y0, z0, r0 = clusters[i]; x1, y1, z1, r1 = clusters[(i + 1) % 9]
        pts = []
        for k in range(14):
            t = k / 13
            x = x0 + (x1 - x0) * t; y = y0 + (y1 - y0) * t
            z = (z0 - r0 * 0.6) * (1 - t) + (z1 - r1 * 0.6) * t - 1.1 * math.sin(t * math.pi)
            pts.append((x, y, z))
        C.tube_curve(f"strand{i}", pts, radius=0.01, mat=C.principled("FV_String", (0.2, 0.15, 0.1)), col=col, res=3, bevel_res=1)
        for k in range(1, 13, 2):
            C.uvsphere(f"fl{i}_{k}", 0.05, pts[k], segs=8, rings=6, mat=lights, col=col)
    # door lanterns, flanking posts
    lamp_post("post_l", (tx - 1.9, door_y - 0.75), col, side=-1)
    lamp_post("post_r", (tx + 1.9, door_y - 0.75), col, side=1)
    # moss skirt at the base + scatter
    skirt = C.lathe("moss_skirt", [(4.6, -0.05), (4.0, 0.1), (3.2, 0.32), (2.9, 0.5), (2.7, 0.62)], segs=64,
                    mat=C.leaf_mat("FV_Moss", (0.12, 0.28, 0.06), (0.32, 0.52, 0.14), blossom=(0.75, 0.9, 1.0), bl_amt=0.06), col=col)
    skirt.location = (tx, ty, 0)
    bmk = bmesh.new(); bmk.from_mesh(skirt.data)
    kill = [f for f in bmk.faces if abs(math.degrees(math.atan2(f.calc_center_median().y, f.calc_center_median().x)) + 90) < 30]
    bmesh.ops.delete(bmk, geom=kill, context="FACES"); bmk.to_mesh(skirt.data); bmk.free()
    C.displace(skirt, 0.18, 0.5)
    foliage(skirt, 1500 if not PREVIEW else 300, col, "leaf", size=1.3, seed=77)

    def in_fp(rnd):
        a = rnd.random() * 6.28; rr = rnd.uniform(3.4, 7.2)
        x, y = tx + rr * math.cos(a), ty + 1.5 + rr * math.sin(a) * 0.9
        if not (0.4 < x < W - 0.4 and -D + 0.4 < y < -0.4):
            return None
        if abs(x - tx) < 1.8 and y < ty - 2.0:
            return None          # door path
        return (x, y)
    scatter_flowers(col, 70 if not PREVIEW else 15, in_fp, seed=7)
    grass_tufts(col, 120 if not PREVIEW else 20, in_fp)
    rnd = random.Random(5)
    for i in range(14):
        p = in_fp(rnd)
        if p:
            C.mushroom(f"shr{i}", (p[0], p[1], 0), h=rnd.uniform(0.25, 0.6), cap_r=rnd.uniform(0.15, 0.32),
                       cap_col=rnd.choice([(0.55, 0.25, 0.85), (0.25, 0.55, 0.9), (0.9, 0.35, 0.55)]),
                       glow=rnd.choice([(0.6, 0.4, 1.0), (0.35, 0.8, 1.0)]), col=col, lean=rnd.uniform(-0.2, 0.2))
    for i in range(6):
        p = in_fp(rnd)
        if p:
            rock(f"rk{i}", (p[0], p[1], 0.05), rnd.uniform(0.25, 0.5), col)
    # petal path in front of the door
    pet = C.petal_mat("FV_PathPetal", (1.0, 0.75, 0.88), (1.0, 0.95, 0.98))
    for i in range(70):
        x = tx + rnd.uniform(-1.0, 1.0); y = rnd.uniform(-D + 0.3, door_y - 1.6)
        C.flower(f"pp{i}", (x, y, 0.02), r=0.06, petals=1, c_base=(1, 0.72, 0.86), c_tip=(1, 0.95, 0.98), col=col,
                 rot=rnd.random() * 6.28, cup=0.1)
    for i in range(9):
        y = door_y - 1.7 - i * 0.62
        if y < -D + 0.35:
            break
        C.box(f"ps{i}", (rnd.uniform(0.6, 0.85), 0.5, 0.1), (tx + rnd.uniform(-0.25, 0.25), y, 0.02), stone, col, bevel=0.025,
              rot=(0, 0, rnd.uniform(-0.3, 0.3)))
    return {"door_face_y": door_y}



# ============================================================ Tumbleroot's Mushroom Apothecary
def potion(name, loc, col, h=0.28, liquid=(0.3, 1.0, 0.5), shape=0):
    glass = C.principled("FV_Glass", (0.9, 0.95, 1.0), rough=0.05, trans=1.0)
    prof = [[(0.001, 0), (0.09, 0.005), (0.11, 0.08), (0.10, 0.16), (0.04, 0.2), (0.035, 0.27), (0.045, 0.28)],
            [(0.001, 0), (0.07, 0.005), (0.075, 0.18), (0.035, 0.22), (0.03, 0.28), (0.04, 0.29)],
            [(0.001, 0), (0.12, 0.01), (0.12, 0.05), (0.05, 0.16), (0.03, 0.26), (0.04, 0.27)]][shape % 3]
    sc = h / 0.28
    b = C.lathe(name, [(r * sc, z * sc) for r, z in prof], segs=20, mat=glass, col=col, close_bottom=True)
    lq = C.lathe(name + "_lq", [(r * sc * 0.88, z * sc) for r, z in prof[:3]] + [(0.001, prof[2][1] * sc)], segs=20,
                 mat=C.glow_mat(f"FV_Potion_{int(liquid[0]*9)}{int(liquid[1]*9)}{int(liquid[2]*9)}", liquid, 3.0), col=col, close_bottom=True)
    cork = C.cyl(name + "_cork", 0.03 * sc, 0.05 * sc, (0, 0, prof[-1][1] * sc + 0.01), segs=10, mat=C.wood_mat("FV_Cork", (0.5, 0.35, 0.2), (0.7, 0.5, 0.3)), col=col)
    lq.parent = b; cork.parent = b
    b.location = loc
    return b


def build_apothecary(col):
    rnd = random.Random(8)
    sx, sy = CX, -D + 3.1                     # stem centre
    stemm = C.node_mat("FV_ShroomHouse")[0]
    m, nt = C.node_mat("FV_ShroomHouse2")
    if nt is not None:
        n = nt.nodes; b = n["Principled BSDF"]
        tc = n.new("ShaderNodeTexCoord"); mp = n.new("ShaderNodeMapping"); mp.inputs["Scale"].default_value = (2, 2, 0.4)
        C.link(nt, tc.outputs["Object"], mp.inputs[0])
        wv = n.new("ShaderNodeTexWave"); wv.bands_direction = "Z"; wv.inputs["Scale"].default_value = 3; wv.inputs["Distortion"].default_value = 4
        wv.wave_type = "BANDS"; wv.bands_direction = "X"
        C.link(nt, mp.outputs[0], wv.inputs[0])
        ramp = n.new("ShaderNodeValToRGB"); ramp.color_ramp.elements[0].color = (0.78, 0.70, 0.56, 1); ramp.color_ramp.elements[1].color = (0.96, 0.92, 0.82, 1)
        C.link(nt, wv.outputs["Fac"], ramp.inputs[0]); C.link(nt, ramp.outputs[0], b.inputs["Base Color"])
        b.inputs["Roughness"].default_value = 0.65
        b.inputs["Subsurface Weight"].default_value = 0.3; b.inputs["Subsurface Radius"].default_value = (1.0, 0.7, 0.5)
        b.inputs["Subsurface Scale"].default_value = 0.08
        bump = n.new("ShaderNodeBump"); bump.inputs["Strength"].default_value = 0.4
        C.link(nt, wv.outputs["Fac"], bump.inputs["Height"]); C.link(nt, bump.outputs[0], b.inputs["Normal"])
    stem = C.lathe("stem", [(2.45, -0.05), (2.35, 0.4), (2.15, 1.5), (2.05, 2.6), (2.1, 3.5), (1.9, 4.2), (0.001, 4.3)], segs=72,
                   mat=m, col=col, close_bottom=True)
    stem.location = (sx, sy, 0)
    C.add_mod_subsurf(stem, 1)
    C.displace(stem, 0.06, 0.6)
    bmr = bmesh.new()
    for k in range(9):
        a = 2 * math.pi * k / 9 + 0.3
        if abs(math.cos(a)) < 0.35 and math.sin(a) < 0:
            continue
        r0 = 2.3
        C.tube_curve(f"aroot{k}", [(sx + r0 * math.cos(a), sy + r0 * math.sin(a), 0.7), (sx + (r0 + 0.5) * math.cos(a + 0.1), sy + (r0 + 0.5) * math.sin(a + 0.1), 0.15),
                     (sx + (r0 + 0.8) * math.cos(a + 0.15), sy + (r0 + 0.8) * math.sin(a + 0.15), -0.05)], radius=0.3, mat=C.bark_mat("FV_ShroomRoot", (0.30, 0.24, 0.18), (0.55, 0.47, 0.36)), col=col, radii=[1.0, 0.75, 0.35])
    # cap: violet -> teal, glowing spots, gills underneath
    capm, nt = C.node_mat("FV_BigCap")
    if nt is not None:
        n = nt.nodes; b = n["Principled BSDF"]
        tc = n.new("ShaderNodeTexCoord"); sep = n.new("ShaderNodeSeparateXYZ"); C.link(nt, tc.outputs["Object"], sep.inputs[0])
        ramp = n.new("ShaderNodeValToRGB")
        ramp.color_ramp.elements[0].color = (0.05, 0.02, 0.18, 1); ramp.color_ramp.elements[1].color = (0.30, 0.04, 0.36, 1)
        e = ramp.color_ramp.elements.new(0.55); e.color = (0.17, 0.04, 0.34, 1)
        e2 = ramp.color_ramp.elements.new(0.85); e2.color = (0.42, 0.07, 0.36, 1)
        mr = n.new("ShaderNodeMapRange"); mr.inputs["From Min"].default_value = 3.6; mr.inputs["From Max"].default_value = 7.4
        C.link(nt, sep.outputs["Z"], mr.inputs["Value"]); C.link(nt, mr.outputs[0], ramp.inputs[0])
        nz = n.new("ShaderNodeTexNoise"); nz.inputs["Scale"].default_value = 2.2; nz.inputs["Detail"].default_value = 10
        C.link(nt, tc.outputs["Object"], nz.inputs[0])
        mx = n.new("ShaderNodeMix"); mx.data_type = "RGBA"; mx.blend_type = "OVERLAY"; mx.inputs["Factor"].default_value = 0.3
        C.link(nt, ramp.outputs[0], mx.inputs[6]); C.link(nt, nz.outputs["Color"], mx.inputs[7])
        C.link(nt, mx.outputs[2], b.inputs["Base Color"])
        b.inputs["Roughness"].default_value = 0.44; b.inputs["Coat Weight"].default_value = 0.25
        b.inputs["Subsurface Weight"].default_value = 0.12; b.inputs["Subsurface Radius"].default_value = (0.7, 0.4, 1.0)
        b.inputs["Subsurface Scale"].default_value = 0.1
        v = n.new("ShaderNodeTexVoronoi"); v.inputs["Scale"].default_value = 1.0; v.inputs["Randomness"].default_value = 1.0
        C.link(nt, tc.outputs["Object"], v.inputs[0])
        mr2 = n.new("ShaderNodeMapRange"); mr2.inputs["From Min"].default_value = 0.13; mr2.inputs["From Max"].default_value = 0.19
        mr2.inputs["To Min"].default_value = 1.0; mr2.inputs["To Max"].default_value = 0.0
        C.link(nt, v.outputs["Distance"], mr2.inputs["Value"])
        spot = n.new("ShaderNodeMix"); spot.data_type = "RGBA"
        C.link(nt, mr2.outputs[0], spot.inputs["Factor"]); C.link(nt, mx.outputs[2], spot.inputs[6])
        spot.inputs[7].default_value = (0.75, 1.0, 0.98, 1)
        C.link(nt, spot.outputs[2], b.inputs["Base Color"])
        em = n.new("ShaderNodeMath"); em.operation = "MULTIPLY"; em.inputs[1].default_value = 2.2
        C.link(nt, mr2.outputs[0], em.inputs[0])
        b.inputs["Emission Color"].default_value = (0.35, 0.95, 1.0, 1)
        C.link(nt, em.outputs[0], b.inputs["Emission Strength"])
        bump = n.new("ShaderNodeBump"); bump.inputs["Strength"].default_value = 0.3
        C.link(nt, mr2.outputs[0], bump.inputs["Height"])
        nz2 = n.new("ShaderNodeTexNoise"); nz2.inputs["Scale"].default_value = 6.0; nz2.inputs["Detail"].default_value = 8; nz2.inputs["Roughness"].default_value = 0.6
        C.link(nt, tc.outputs["Object"], nz2.inputs[0])
        bump2 = n.new("ShaderNodeBump"); bump2.inputs["Strength"].default_value = 0.22; bump2.inputs["Distance"].default_value = 0.05
        C.link(nt, nz2.outputs["Fac"], bump2.inputs["Height"]); C.link(nt, bump.outputs[0], bump2.inputs["Normal"])
        C.link(nt, bump2.outputs[0], b.inputs["Normal"])
    cap = C.lathe("cap", [(1.6, 3.55), (3.5, 3.5), (4.65, 3.75), (4.75, 3.95), (4.55, 4.6), (4.0, 5.6), (3.0, 6.55), (1.6, 7.15), (0.001, 7.35)],
                  segs=96, mat=capm, col=col, close_bottom=False)
    cap.location = (sx, sy + 0.9, 0)
    C.add_mod_subsurf(cap, 2)
    bm = bmesh.new(); bm.from_mesh(cap.data)
    for v in bm.verts:
        a = math.atan2(v.co.y, v.co.x)
        v.co.z += 0.18 * math.sin(3 * a + 0.5) * (math.hypot(v.co.x, v.co.y) / 4.7) ** 2
    bm.to_mesh(cap.data); bm.free()
    gill = C.principled("FV_Gills", (0.86, 0.72, 0.62), rough=0.7, sss=0.3, emit=(1.0, 0.7, 0.45), emit_strength=0.25)
    for i in range(72):
        a = 2 * math.pi * i / 72
        g = C.box(f"gill{i}", (2.3, 0.025, 0.12), (sx + 2.75 * math.cos(a), sy + 0.9 + 2.75 * math.sin(a), 3.62), gill, col)
        g.rotation_euler = (0, 0, a)
    # chimney with glowing potion smoke
    ch_pts = [(sx + 1.8, sy + 2.2, 5.6), (sx + 2.0, sy + 2.3, 7.0), (sx + 2.3, sy + 2.2, 7.8), (sx + 2.15, sy + 2.0, 8.4)]
    C.tube_curve("chimney", ch_pts, radius=0.32, mat=C.stone_mat("FV_ChimStone", (0.30, 0.27, 0.28), (0.48, 0.44, 0.42), moss_amt=0.25), col=col, radii=[1.0, 0.9, 0.85, 1.05])
    smoke = C.principled("FV_Smoke", (0.4, 0.9, 0.55), rough=0.5, emit=(0.3, 1.0, 0.5), emit_strength=0.9, alpha=0.22)
    smoke.surface_render_method = "BLENDED"
    for k in range(5):
        C.ico(f"fume{k}", 0.07 + 0.02 * (k % 3), (sx + 2.15 + 0.3 * math.sin(k * 1.9), sy + 2.0 + 0.2 * math.cos(k * 1.3), 8.7 + k * 0.45), sub=2,
              mat=C.glow_mat("FV_Brew", (0.35, 1.0, 0.4), 5.0), col=col)
    # round door + porch
    dy = sy - 2.3
    wood = C.wood_mat("FV_WoodPlum", (0.25, 0.12, 0.12), (0.45, 0.24, 0.20))
    gold = C.gold_mat()
    door = C.cyl("door", 0.75, 0.12, (sx, dy - 0.02, 1.05), segs=48, mat=wood, col=col)
    door.rotation_euler = (math.pi / 2, 0, 0); door.scale = (1, 1.4, 1)
    C.torus("door_frame", 0.8, 0.09, (sx, dy - 0.06, 1.05), mat=C.stone_mat("FV_Moonstone", moss_amt=0.0), col=col, rot=(math.pi / 2, 0, 0)).scale = (1, 1.4, 1)
    C.uvsphere("door_knob", 0.06, (sx + 0.4, dy - 0.15, 0.95), mat=gold, col=col)
    C.ico("door_gem", 0.09, (sx, dy - 0.14, 1.75), sub=2, mat=C.glow_mat("FV_TealGem", (0.3, 1.0, 0.9), 6), col=col)
    for k in range(3):
        C.box(f"astep{k}", (1.8 - k * 0.3, 0.45, 0.14), (sx, dy - 0.45 - (2 - k) * 0.42, 0.07 + k * 0.14), C.stone_mat("FV_StepStone", (0.34, 0.33, 0.36), (0.52, 0.50, 0.53), moss_amt=0.08), col, bevel=0.03)
    # fairy-light strand under the cap rim
    for i in range(44):
        a = 2 * math.pi * i / 44
        C.ico(f"rimbulb{i}", 0.05, (sx + 4.35 * math.cos(a), sy + 0.9 + 4.35 * math.sin(a), 3.55 - 0.12 * abs(math.sin(i * 1.7))), sub=1,
              mat=C.glow_mat("FV_RimBulb" + "AB"[i % 2], [(1.0, 0.75, 0.4), (0.6, 0.9, 1.0)][i % 2], 9), col=col)
    # ivy up the stem
    for k in range(5):
        a0 = math.radians(-150 + k * 32)
        pts = [(sx + 2.25 * math.cos(a0 + t * 0.5), sy + 2.25 * math.sin(a0 + t * 0.5), t * 0.85) for t in range(5)]
        if abs(math.cos(a0)) < 0.25 and math.sin(a0) < 0:
            continue
        iv = C.tube_curve(f"ivy{k}", pts, radius=0.03, mat=C.wood_mat("FV_IvyStem", (0.12, 0.18, 0.05), (0.2, 0.3, 0.08)), col=col)
    C.apply_mods(stem)
    # windows
    for i, (ang, z, r) in enumerate([(-55, 2.1, 0.42), (-125, 2.4, 0.38), (-90, 3.05, 0.3), (-20, 1.6, 0.34), (-160, 1.5, 0.32)]):
        a = math.radians(ang); rr = 2.2
        px, py = sx + rr * math.cos(a), sy + rr * math.sin(a)
        rot = (math.pi / 2, 0, a + math.pi / 2)
        C.torus(f"aw_fr{i}", r, 0.055, (px, py, z), mat=wood, col=col, rot=rot)
        g = C.cyl(f"aw_gl{i}", r, 0.05, (px, py, z), segs=32, mat=C.window_mat("FV_WindowGreen", (0.55, 1.0, 0.45), 7.0) if i % 2 else C.window_mat(), col=col)
        g.rotation_euler = rot
    # shelf of potions beside the door
    shelf_x = sx + 1.55
    for k, z in enumerate((0.45, 1.0)):
        sh = C.box(f"shelf{k}", (1.0, 0.32, 0.06), (shelf_x, dy - 0.05, z), wood, col, bevel=0.01); sh.rotation_euler = (0, 0, 0.45)
        for q in range(4):
            potion(f"pot{k}{q}", (shelf_x - 0.38 + q * 0.25, dy - 0.05 - 0.1 + q * 0.05, z + 0.03), col, h=0.2 + 0.08 * ((q + k) % 2),
                   liquid=[(0.3, 1.0, 0.5), (1.0, 0.35, 0.6), (0.4, 0.6, 1.0), (1.0, 0.8, 0.3)][(q + k) % 4], shape=q + k)
    # cauldron
    cx2, cy2 = sx - 2.4, dy - 0.9
    caul = C.lathe("cauldron", [(0.001, 0.12), (0.45, 0.15), (0.62, 0.4), (0.6, 0.72), (0.5, 0.82), (0.55, 0.86)], segs=40,
                   mat=C.principled("FV_Iron", (0.08, 0.08, 0.09), rough=0.45, metal=0.8), col=col, close_bottom=True)
    caul.location = (cx2, cy2, 0)
    brew = C.cyl("brew", 0.5, 0.04, (cx2, cy2, 0.76), segs=40, mat=C.glow_mat("FV_Brew", (0.35, 1.0, 0.4), 5.0), col=col)
    for k in range(6):
        C.ico(f"bubble{k}", 0.06 + 0.03 * (k % 3), (cx2 + 0.3 * math.cos(k * 1.1), cy2 + 0.3 * math.sin(k * 1.1), 0.82 + 0.05 * k), sub=2,
              mat=C.glow_mat("FV_Brew", (0.35, 1.0, 0.4), 5.0), col=col)
    for k in range(3):
        a = 2 * math.pi * k / 3
        C.cyl(f"leg{k}", 0.05, 0.25, (cx2 + 0.45 * math.cos(a), cy2 + 0.45 * math.sin(a), 0.1), segs=8, mat=C.principled("FV_Iron", (0.08, 0.08, 0.09)), col=col)
    Lb = bpy.data.lights.new("brewL", "POINT"); Lb.energy = 60; Lb.color = (0.4, 1.0, 0.5)
    lo = bpy.data.objects.new("brewL", Lb); lo.location = (cx2, cy2, 1.2); col.objects.link(lo)
    # hanging sign
    arm = C.box("sign_arm", (1.1, 0.07, 0.07), (sx - 1.4, dy + 0.1, 3.0), wood, col)
    sign = C.box("sign", (0.75, 0.06, 0.5), (sx - 1.7, dy + 0.05, 2.55), wood, col, bevel=0.02)
    potion("sign_pot", (sx - 1.7, dy - 0.02, 2.38), col, h=0.32, liquid=(0.3, 1.0, 0.6), shape=0).rotation_euler = (0, 0, 0)
    # small mushrooms cluster, crates, lantern
    for i in range(18):
        a = rnd.uniform(0, 6.28); rr = rnd.uniform(2.6, 4.6)
        x, y = sx + rr * math.cos(a), sy + 0.8 + rr * math.sin(a)
        if not (0.3 < x < W - 0.3 and -D + 0.3 < y < -0.3) or (abs(x - sx) < 1.2 and y < sy - 1.5):
            continue
        C.mushroom(f"ms{i}", (x, y, 0), h=rnd.uniform(0.3, 0.9), cap_r=rnd.uniform(0.18, 0.5),
                   cap_col=rnd.choice([(0.5, 0.22, 0.8), (0.25, 0.5, 0.9), (0.85, 0.3, 0.6)]), glow=(0.4, 0.95, 1.0), col=col,
                   lean=rnd.uniform(-0.25, 0.25))
    for k in range(2):
        C.box(f"crate{k}", (0.55, 0.55, 0.5), (sx + 2.6, dy - 0.4 + k * 0.1, 0.25 + k * 0.5), C.wood_mat(), col, bevel=0.03,
              rot=(0, 0, 0.2 * k))
    lamp_post("apost", (sx + 1.3, dy - 1.4), col, h=2.0, side=1)

    def in_fp(rnd):
        x, y = rnd.uniform(0.3, W - 0.3), rnd.uniform(-D + 0.3, -0.3)
        if math.hypot(x - sx, y - sy) < 2.6 or (abs(x - sx) < 1.0 and y < sy):
            return None
        return (x, y)
    scatter_flowers(col, 40 if not PREVIEW else 10, in_fp, seed=9)
    grass_tufts(col, 70 if not PREVIEW else 15, in_fp, seed=10)
    return {}


# ============================================================ The Moonpetal Inn
def rounded_rect_profile(w, d, r, n=10):
    pts = []
    for cx, cy, a0 in ((w / 2 - r, d / 2 - r, 0), (-w / 2 + r, d / 2 - r, 90), (-w / 2 + r, -d / 2 + r, 180), (w / 2 - r, -d / 2 + r, 270)):
        for i in range(n + 1):
            a = math.radians(a0 + 90 * i / n)
            pts.append((cx + r * math.cos(a), cy + r * math.sin(a)))
    return pts


def extrude_profile(name, pts, z0, z1, mat, col, inset_top=0.0):
    bm = bmesh.new()
    lo = [bm.verts.new((x, y, z0)) for x, y in pts]
    hi = [bm.verts.new((x * (1 - inset_top), y * (1 - inset_top), z1)) for x, y in pts]
    n = len(pts)
    for i in range(n):
        j = (i + 1) % n
        bm.faces.new((lo[i], lo[j], hi[j], hi[i]))
    bm.faces.new(list(reversed(lo))); bm.faces.new(hi)
    return C.obj_from_bm(bm, name, mat, col)


def petal_mesh(name, length, width, curl, mat, col, segs_l=14, segs_w=8):
    bm = bmesh.new(); uvl = bm.loops.layers.uv.new("UVMap")
    grid = []
    for i in range(segs_l + 1):
        t = i / segs_l
        wid = width * math.sin(math.pi * min(1, t * 1.05)) ** 0.7 * (1 - 0.25 * t)
        row = []
        for j in range(segs_w + 1):
            u = j / segs_w - 0.5
            x = u * wid
            y = length * t
            z = curl * (t ** 2) * length + 0.18 * width * (u * 2) ** 2
            row.append(bm.verts.new((x, y, z)))
        grid.append(row)
    for i in range(segs_l):
        for j in range(segs_w):
            f = bm.faces.new((grid[i][j], grid[i][j + 1], grid[i + 1][j + 1], grid[i + 1][j]))
            for lp, (a, b) in zip(f.loops, ((j, i), (j + 1, i), (j + 1, i + 1), (j, i + 1))):
                lp[uvl].uv = (a / segs_w, b / segs_l)
    o = C.obj_from_bm(bm, name, mat, col)
    so = o.modifiers.new("Sol", "SOLIDIFY"); so.thickness = 0.06
    C.add_mod_subsurf(o, 1)
    return o



def petal_between(name, B, E, tang, width, bulge, mat, col, nl=14, nw=8):
    """Broad rounded petal from base B to tip E (world coords), cupped, bulging outward along its normal."""
    spine = E - B
    nrm = spine.cross(tang).normalized()
    if nrm.z < 0:
        nrm = -nrm
    bm = bmesh.new(); uvl = bm.loops.layers.uv.new("UVMap")
    grid = []
    for i in range(nl + 1):
        t = i / nl
        wv = width * max(0.0, 1 - abs(2 * t - 1.1) ** 3) ** 0.5 * (0.55 + 0.45 * math.sin(math.pi * min(1, t * 0.9 + 0.1)))
        if t > 0.95:
            wv *= (1 - t) / 0.05 * 0.6 + 0.4 * (1 - t) / 0.05
        ctr = B + spine * t + nrm * (bulge * 4 * t * (1 - t))
        row = []
        for j in range(nw + 1):
            u = j / nw - 0.5
            p = ctr + tang * (u * wv) + nrm * (0.22 * wv * (2 * u) ** 2) - nrm * 0.0
            row.append(bm.verts.new(p))
        grid.append(row)
    for i in range(nl):
        for j in range(nw):
            f = bm.faces.new((grid[i][j], grid[i][j + 1], grid[i + 1][j + 1], grid[i + 1][j]))
            for lp, (a, b) in zip(f.loops, ((j, i), (j + 1, i), (j + 1, i + 1), (j, i + 1))):
                lp[uvl].uv = (a / nw, b / nl)
    o = C.obj_from_bm(bm, name, mat, col)
    so = o.modifiers.new("Sol", "SOLIDIFY"); so.thickness = 0.07
    C.add_mod_subsurf(o, 1)
    return o


def block_mat(name, c1, c2):
    m, nt = C.node_mat(name)
    if nt is None:
        return m
    n = nt.nodes; b = n["Principled BSDF"]
    tc = n.new("ShaderNodeTexCoord"); sep = n.new("ShaderNodeSeparateXYZ"); C.link(nt, tc.outputs["Object"], sep.inputs[0])
    add = n.new("ShaderNodeMath"); add.operation = "ADD"; C.link(nt, sep.outputs["X"], add.inputs[0]); C.link(nt, sep.outputs["Y"], add.inputs[1])
    comb = n.new("ShaderNodeCombineXYZ"); C.link(nt, add.outputs[0], comb.inputs["X"]); C.link(nt, sep.outputs["Z"], comb.inputs["Y"])
    br = n.new("ShaderNodeTexBrick"); br.inputs["Scale"].default_value = 1.0; br.inputs["Mortar Size"].default_value = 0.025
    br.inputs["Brick Width"].default_value = 0.9; br.inputs["Row Height"].default_value = 0.35; br.offset = 0.5
    br.inputs["Color1"].default_value = (*c1, 1); br.inputs["Color2"].default_value = (*c2, 1); br.inputs["Mortar"].default_value = (0.25, 0.24, 0.26, 1)
    C.link(nt, comb.outputs[0], br.inputs["Vector"])
    nz = n.new("ShaderNodeTexNoise"); nz.inputs["Scale"].default_value = 3; nz.inputs["Detail"].default_value = 8
    C.link(nt, tc.outputs["Object"], nz.inputs[0])
    mx = n.new("ShaderNodeMix"); mx.data_type = "RGBA"; mx.blend_type = "MULTIPLY"; mx.inputs["Factor"].default_value = 0.35
    C.link(nt, br.outputs["Color"], mx.inputs[6]); C.link(nt, nz.outputs["Color"], mx.inputs[7])
    C.link(nt, mx.outputs[2], b.inputs["Base Color"])
    b.inputs["Roughness"].default_value = 0.85
    h = n.new("ShaderNodeMath"); h.operation = "MULTIPLY_ADD"; h.inputs[1].default_value = 0.3
    C.link(nt, br.outputs["Fac"], h.inputs[0]); C.link(nt, nz.outputs["Fac"], h.inputs[2])
    bump = n.new("ShaderNodeBump"); bump.inputs["Strength"].default_value = 0.6; bump.invert = True
    C.link(nt, br.outputs["Fac"], bump.inputs["Height"]); C.link(nt, bump.outputs[0], b.inputs["Normal"])
    return m


def plaster_mat(name, c1=(0.80, 0.70, 0.56), c2=(0.93, 0.86, 0.74)):
    m, nt = C.node_mat(name)
    if nt is None:
        return m
    n = nt.nodes; b = n["Principled BSDF"]
    tc = n.new("ShaderNodeTexCoord")
    nz = n.new("ShaderNodeTexNoise"); nz.inputs["Scale"].default_value = 1.2; nz.inputs["Detail"].default_value = 6; nz.inputs["Roughness"].default_value = 0.5
    C.link(nt, tc.outputs["Object"], nz.inputs[0])
    ramp = n.new("ShaderNodeValToRGB"); ramp.color_ramp.elements[0].color = (*c1, 1); ramp.color_ramp.elements[1].color = (*c2, 1)
    ramp.color_ramp.elements[0].position = 0.35; ramp.color_ramp.elements[1].position = 0.65
    C.link(nt, nz.outputs["Fac"], ramp.inputs[0]); C.link(nt, ramp.outputs[0], b.inputs["Base Color"])
    b.inputs["Roughness"].default_value = 0.9
    bump = n.new("ShaderNodeBump"); bump.inputs["Strength"].default_value = 0.06
    C.link(nt, nz.outputs["Fac"], bump.inputs["Height"]); C.link(nt, bump.outputs[0], b.inputs["Normal"])
    return m


def build_inn(col):
    rnd = random.Random(12)
    stone = block_mat("FV_InnBlocks", (0.46, 0.44, 0.50), (0.66, 0.64, 0.70))
    plaster = plaster_mat("FV_Plaster")
    wood = C.wood_mat("FV_LivingWood", (0.22, 0.13, 0.07), (0.42, 0.28, 0.16))
    ix, iy = CX, CY - 0.3
    w0, d0 = W - 1.6, D - 2.4
    base_pts = [(ix + x, iy + y) for x, y in rounded_rect_profile(w0, d0, 2.2)]
    extrude_profile("ground_floor", [(x, y) for x, y in base_pts], 0, 3.0, stone, col)
    # stone block bands
    for z in (0.5, 1.2, 1.9, 2.6):
        band = extrude_profile(f"band{z}", [(ix + (x - ix) * 1.01, iy + (y - iy) * 1.012) for x, y in base_pts], z - 0.05, z + 0.03, stone, col)
    up_pts = [(ix + x, iy + 0.3 + y) for x, y in rounded_rect_profile(w0 - 1.4, d0 - 1.4, 1.8)]
    extrude_profile("upper_floor", up_pts, 3.0, 5.4, plaster, col)
    extrude_profile("floor_ledge", [(ix + (x - ix) * 1.04, iy + (y - iy) * 1.05) for x, y in base_pts], 2.95, 3.15, wood, col)
    # curved living-wood beams on the upper floor
    for i, (x, y) in enumerate(up_pts[::3]):
        C.tube_curve(f"beam{i}", [(x, y, 3.1), (x + 0.1 * (x - ix) / 6, y + 0.08 * (y - iy) / 6, 4.2), (x, y, 5.35)], radius=0.14, mat=wood, col=col)
    # front door (arched) on the south face, at door tile column 4 (centre x = 4.5 tiles)
    dx = 4.5 * C.T
    front_y = iy - d0 / 2
    door = C.box("inn_door", (1.5, 0.16, 2.3), (dx, front_y - 0.02, 1.15), C.wood_mat("FV_DoorWood", (0.32, 0.18, 0.09), (0.52, 0.32, 0.17)), col, bevel=0.03)
    arch = C.torus("inn_arch", 0.85, 0.14, (dx, front_y - 0.1, 2.3), mat=stone, col=col, rot=(math.pi / 2, 0, 0))
    for side in (-1, 1):
        C.box(f"inn_jamb{side}", (0.28, 0.32, 2.3), (dx + side * 0.86, front_y - 0.1, 1.15), stone, col, bevel=0.03)
    C.box("inn_gap", (0.03, 0.05, 1.9), (dx, front_y - 0.12, 1.1), C.glow_mat("FV_WarmGlow", (1.0, 0.65, 0.3), 12), col)
    # petal awning over the door
    porch_m = C.petal_mat("FV_InnPetal", (0.97, 0.86, 0.93), (0.86, 0.38, 0.62), glow=(1.0, 0.6, 0.8), glow_strength=0.06)
    for k in range(5):
        xx = dx + (k - 2) * 0.48
        petal_between(f"porch{k}", Vector((xx, front_y + 0.05, 3.05)), Vector((dx + (k - 2) * 0.62, front_y - 1.05, 2.55)), Vector((1, 0, 0)), 0.75, 0.15, porch_m, col)
    for k in range(3):
        C.box(f"inn_step{k}", (2.4 - k * 0.4, 0.45, 0.14), (dx, front_y - 0.5 - (2 - k) * 0.42, 0.07 + k * 0.14 - 0.14), stone, col, bevel=0.03)
    # windows (ground: arched warm; upper: round)
    for k, x in enumerate([ix - 4.6, ix - 2.6, ix + 2.4, ix + 4.6]):
        if abs(x - dx) < 1.4:
            continue
        g = C.box(f"gw{k}", (0.9, 0.08, 1.2), (x, front_y - 0.02, 1.5), C.window_mat(), col)
        C.torus(f"gwa{k}", 0.47, 0.07, (x, front_y - 0.06, 2.1), mat=wood, col=col, rot=(math.pi / 2, 0, 0))
        fb = C.box(f"fbox{k}", (1.1, 0.3, 0.22), (x, front_y - 0.2, 0.8), wood, col, bevel=0.02)
        for q in range(4):
            C.flower(f"ifl{k}{q}", (x - 0.38 + q * 0.25, front_y - 0.22, 0.96), r=0.1, c_base=[(1, 0.55, 0.75), (0.7, 0.55, 1), (1, 0.9, 0.6)][q % 3],
                     c_tip=(1, 0.97, 0.98), col=col)
    up_front = iy + 0.3 - (d0 - 1.4) / 2
    for k, x in enumerate([ix - 3.4, ix - 1.1, ix + 1.2, ix + 3.5]):
        g = C.cyl(f"uw{k}", 0.42, 0.06, (x, up_front - 0.03, 4.2), segs=32, mat=C.window_mat(), col=col); g.rotation_euler = (math.pi / 2, 0, 0)
        C.torus(f"uwf{k}", 0.44, 0.06, (x, up_front - 0.05, 4.2), mat=wood, col=col, rot=(math.pi / 2, 0, 0))
    # ROOF: a closed moonpetal bloom draped over the upper floor (broad overlapping petals)
    rx, ry = ix, iy + 0.3
    erx, ery = (w0 - 1.4) / 2 + 0.25, (d0 - 1.4) / 2 + 0.25
    pm = [C.petal_mat("FV_RoofPetalA", (0.96, 0.80, 0.90), (0.80, 0.26, 0.52), glow=(1.0, 0.6, 0.8), glow_strength=0.06),
          C.petal_mat("FV_RoofPetalB", (0.97, 0.85, 0.95), (0.70, 0.34, 0.74), glow=(0.95, 0.7, 1.0), glow_strength=0.06),
          C.petal_mat("FV_RoofPetalC", (1.0, 0.95, 0.98), (0.92, 0.55, 0.75), glow=(1.0, 0.75, 0.9), glow_strength=0.08),
          C.petal_mat("FV_RoofPetalD", (0.82, 0.72, 1.0), (0.98, 0.92, 1.0), glow=(0.75, 0.65, 1.0), glow_strength=0.35)]
    layers = [  # n, base frac, base z, tip frac, tip z, width, bulge, mat, ang offset
        (22, 0.52, 7.0, 1.13, 5.05, 2.6, 0.75, pm[0], 0.0),
        (16, 0.30, 7.9, 0.88, 6.15, 2.4, 0.65, pm[1], 0.5),
        (11, 0.08, 8.5, 0.60, 7.25, 1.9, 0.5, pm[2], 0.25),
        (7, 0.02, 8.45, 0.30, 9.5, 0.95, -0.15, pm[3], 0.1),
    ]
    for li, (n, bf, bz, tf, tz, wd, bulge, mat, off) in enumerate(layers):
        for k in range(n):
            ang = 2 * math.pi * (k + off) / n
            ca, sa = math.cos(ang), math.sin(ang)
            B = Vector((rx + erx * bf * ca, ry + ery * bf * sa, bz))
            E = Vector((rx + erx * tf * ca * rnd.uniform(0.97, 1.03), ry + ery * tf * sa * rnd.uniform(0.97, 1.03), tz + rnd.uniform(-0.1, 0.1)))
            tang = Vector((-erx * sa, ery * ca, 0)).normalized()
            petal_between(f"roof{li}_{k}", B, E, tang, wd * (0.6 + 0.4 * math.hypot(erx * ca, ery * sa) / erx), bulge, mat, col)
    pist = C.lathe("pistil", [(0.35, 8.3), (0.25, 8.9), (0.1, 9.5), (0.001, 9.75)], segs=24, mat=C.glow_mat("FV_Pistil", (1.0, 0.85, 0.45), 4.0), col=col)
    pist.location = (rx, ry, 0)
    for k in range(10):
        a2 = 2 * math.pi * k / 10
        C.tube_curve(f"stamen{k}", [(rx, ry, 8.6), (rx + 0.35 * math.cos(a2), ry + 0.35 * math.sin(a2), 9.3), (rx + 0.55 * math.cos(a2), ry + 0.55 * math.sin(a2), 9.5)],
                     radius=0.025, mat=C.principled("FV_StamenStalk", (0.9, 0.8, 0.5)), col=col)
        C.ico(f"anther{k}", 0.08, (rx + 0.55 * math.cos(a2), ry + 0.55 * math.sin(a2), 9.52), sub=2, mat=C.glow_mat("FV_Anther", (1.0, 0.75, 0.3), 6), col=col)
    # fairy lights along the floor ledge
    for i, (x, y) in enumerate(base_pts[::2]):
        C.ico(f"ledgebulb{i}", 0.05, (ix + (x - ix) * 1.05, iy + (y - iy) * 1.06, 2.92), sub=1,
              mat=C.glow_mat("FV_RimBulb" + "AB"[i % 2], [(1.0, 0.75, 0.4), (0.6, 0.9, 1.0)][i % 2], 9), col=col)
    # climbing roses on the ground floor corners
    for k, (x, y) in enumerate([(ix - w0 / 2 + 0.4, front_y - 0.05), (ix + w0 / 2 - 0.4, front_y - 0.05)]):
        pts = [(x + 0.1 * math.sin(t * 1.7), y - 0.06, 0.1 + t * 0.55) for t in range(6)]
        C.tube_curve(f"vine{k}", pts, radius=0.035, mat=C.wood_mat("FV_IvyStem", (0.12, 0.18, 0.05), (0.2, 0.3, 0.08)), col=col)
        leaves(f"vinelv{k}", (x, y - 0.1, 1.6), 0.55, col, n=90)
        for q in range(9):
            C.flower(f"rose{k}{q}", (x + rnd.uniform(-0.45, 0.45), y - 0.25, rnd.uniform(0.6, 2.7)), r=0.08, petals=7,
                     c_base=(0.9, 0.3, 0.5), c_tip=(1, 0.8, 0.88), col=col, tilt=1.4)
    # sign, lanterns, barrels, bench
    signb = C.box("inn_sign", (1.3, 0.08, 0.6), (dx + 2.0, front_y - 0.55, 2.5), wood, col, bevel=0.03)
    C.box("inn_sign_arm", (0.08, 0.6, 0.08), (dx + 2.0, front_y - 0.25, 2.9), wood, col)
    cres = C.torus("inn_sign_moon", 0.18, 0.05, (dx + 2.0, front_y - 0.6, 2.5), mat=C.gold_mat(), col=col, rot=(math.pi / 2, 0, 0))
    for side in (-1, 1):
        lantern(f"inn_lan{side}", (dx + side * 1.25, front_y - 0.3, 2.35), col, scale=1.1)
    for k in range(3):
        b = C.lathe(f"barrel{k}", [(0.32, 0), (0.38, 0.35), (0.32, 0.7)], segs=24, mat=C.wood_mat(), col=col, close_bottom=True, close_top=True)
        b.location = (ix + 5.2 + (k % 2) * 0.5, front_y - 0.5 - (k // 2) * 0.6, 0)
        for z in (0.12, 0.58):
            C.torus(f"hoop{k}{z}", 0.35, 0.02, (b.location.x, b.location.y, z), mat=C.principled("FV_Iron", (0.1, 0.1, 0.1), metal=0.8), col=col)
    bench = C.box("bench", (1.6, 0.4, 0.08), (ix - 3.8, front_y - 0.7, 0.45), wood, col, bevel=0.02)
    for side in (-1, 1):
        C.box(f"benchleg{side}", (0.08, 0.35, 0.45), (ix - 3.8 + side * 0.65, front_y - 0.7, 0.22), wood, col)
    lamp_post("ipost", (ix - 5.6, front_y - 0.9), col, side=1)

    for k in range(9):
        bx = ix - w0 / 2 + 0.9 + k * (w0 - 1.8) / 8
        if abs(bx - dx) < 1.5 or abs(bx - (ix - 3.8)) < 0.9:
            continue
        bush = leaves(f"bed{k}", (bx, front_y - 0.45, 0.25), 0.42, col, n=70)
        for q in range(5):
            C.flower(f"bedfl{k}{q}", (bx + rnd.uniform(-0.35, 0.35), front_y - 0.55 + rnd.uniform(-0.2, 0.2), rnd.uniform(0.35, 0.6)), r=0.075,
                     c_base=[(1.0, 0.5, 0.75), (0.65, 0.5, 1.0), (1.0, 0.85, 0.5)][(k + q) % 3], c_tip=(1, 0.97, 1), col=col, glow=(1, 0.8, 0.9) if q == 0 else None)
    for side in (-1, 1):
        hb = lantern(f"basket_l{side}", (dx + side * 2.6, front_y - 0.35, 2.55), col, scale=0.8, hang=0.25, glow=(1.0, 0.8, 0.5))

    def in_fp(rnd):
        x, y = rnd.uniform(0.3, W - 0.3), rnd.uniform(-D + 0.3, -0.3)
        if (abs(x - ix) < w0 / 2 + 0.2 and abs(y - iy) < d0 / 2 + 0.2) or (abs(x - dx) < 1.0 and y < front_y):
            return None
        return (x, y)
    scatter_flowers(col, 45 if not PREVIEW else 10, in_fp, seed=13)
    grass_tufts(col, 80 if not PREVIEW else 15, in_fp, seed=14)
    return {}

# ============================================================ Fountains (animated)
ANIM = {"waters": [], "curtains": [], "sparkles": []}


def curtain_mat(name, tint=(0.75, 0.92, 1.0), glow=(0.45, 0.85, 1.0)):
    m, nt = C.node_mat(name)
    n = nt.nodes; b = n["Principled BSDF"]
    b.inputs["Base Color"].default_value = (*tint, 1); b.inputs["Roughness"].default_value = 0.05
    b.inputs["Transmission Weight"].default_value = 0.85; b.inputs["IOR"].default_value = 1.33
    b.inputs["Emission Color"].default_value = (*glow, 1)
    tc = n.new("ShaderNodeTexCoord")
    wv = n.new("ShaderNodeTexWave"); wv.wave_type = "BANDS"; wv.bands_direction = "Z"
    wv.inputs["Scale"].default_value = 4.0; wv.inputs["Distortion"].default_value = 9.0; wv.inputs["Detail"].default_value = 4
    wv.inputs["Detail Scale"].default_value = 1.5
    C.link(nt, tc.outputs["Object"], wv.inputs[0])
    ramp = n.new("ShaderNodeValToRGB"); ramp.color_ramp.elements[0].position = 0.45; ramp.color_ramp.elements[1].position = 0.95
    C.link(nt, wv.outputs["Fac"], ramp.inputs[0])
    al = n.new("ShaderNodeMath"); al.operation = "MULTIPLY_ADD"; al.inputs[1].default_value = 0.6; al.inputs[2].default_value = 0.22
    C.link(nt, ramp.outputs[0], al.inputs[0]); C.link(nt, al.outputs[0], b.inputs["Alpha"])
    em = n.new("ShaderNodeMath"); em.operation = "MULTIPLY"; em.inputs[1].default_value = 0.45
    C.link(nt, ramp.outputs[0], em.inputs[0]); C.link(nt, em.outputs[0], b.inputs["Emission Strength"])
    bump = n.new("ShaderNodeBump"); bump.inputs["Strength"].default_value = 0.35
    C.link(nt, wv.outputs["Fac"], bump.inputs["Height"]); C.link(nt, bump.outputs[0], b.inputs["Normal"])
    ANIM["curtains"].append(wv)
    return m


def anim_water(name, **kw):
    m = C.water_mat(name, **kw)
    ANIM["waters"].append(m)
    return m


def star_mesh(name, r, mat, col):
    bm = bmesh.new()
    c = bm.verts.new((0, 0, 0))
    ring = []
    for i in range(8):
        a = math.pi * i / 4; rr = r if i % 2 == 0 else r * 0.28
        ring.append(bm.verts.new((rr * math.cos(a), 0, rr * math.sin(a))))
    for i in range(8):
        bm.faces.new((c, ring[i], ring[(i + 1) % 8]))
    o = C.obj_from_bm(bm, name, mat, col, smooth=False)
    core = C.ico(name + "_c", r * 0.22, (0, 0, 0), sub=1, mat=mat, col=col)
    return C.join([o, core], name)


def sparkles(prefix, n, centre, r0, r1, z0, z1, col, seed=4, size=0.07, colors=((0.8, 0.95, 1.0), (1.0, 0.85, 0.55), (0.9, 0.7, 1.0))):
    rnd = random.Random(seed)
    for i in range(n):
        c = colors[i % len(colors)]
        o = star_mesh(f"{prefix}{i}", size * rnd.uniform(0.6, 1.4), C.glow_mat(f"FV_Spark{i % len(colors)}", c, 14), col)
        ANIM["sparkles"].append((o, dict(cx=centre[0], cy=centre[1], r0=r0, r1=r1, z0=z0, z1=z1, off=rnd.random(),
                                         a0=rnd.uniform(0, 6.283), turns=rnd.choice((-1, 1)), base=o.scale.copy(), spin=rnd.randint(1, 2))))


def set_phase(ph):
    for m in ANIM["waters"]:
        for nd in m.node_tree.nodes:
            if nd.type == "TEX_WAVE":
                nd.inputs["Phase Offset"].default_value = -ph * 2 * math.pi
            if nd.type == "TEX_NOISE":
                nd.inputs["W"].default_value = math.sin(ph * 2 * math.pi) * 0.3
    for wv in ANIM["curtains"]:
        wv.inputs["Phase Offset"].default_value = ph * 2 * math.pi * 2
    for o, d in ANIM["sparkles"]:
        t = (d["off"] + ph) % 1.0
        a = d["a0"] + d["turns"] * 2 * math.pi * ph
        r = d["r0"] + (d["r1"] - d["r0"]) * t
        o.location = (d["cx"] + r * math.cos(a), d["cy"] + r * math.sin(a), d["z0"] + (d["z1"] - d["z0"]) * t)
        k = math.sin(math.pi * t) ** 0.8 * (0.75 + 0.25 * math.cos(2 * math.pi * (ph * 3 + d["off"])))
        o.scale = (k, k, k)
        o.rotation_euler = (0, 0, a + math.pi / 2)


def octo_ring(name, r_out, r_in, z0, z1, mat, col, lip=0.12):
    o = C.lathe(name, [(r_in, z1), (r_in, z0 + 0.1), (r_out, z0), (r_out, z1 - 0.12), (r_out + lip, z1 - 0.06), (r_out + lip, z1), (r_in, z1)],
                segs=8, mat=mat, col=col, smooth=False)
    o.rotation_euler = (0, 0, math.pi / 8)
    bv = o.modifiers.new("Bv", "BEVEL"); bv.width = 0.03; bv.segments = 2
    return o


def build_moonstone_fountain(col):
    rnd = random.Random(21)
    ms = C.stone_mat("FV_FountainStone", (0.44, 0.46, 0.54), (0.66, 0.67, 0.75), moss_amt=0.04, emit_veins=(0.25, 0.5, 0.8))
    dark = C.stone_mat("FV_FountainDark", (0.30, 0.31, 0.37), (0.46, 0.47, 0.53), moss_amt=0.3)
    gold = C.gold_mat()
    cx, cy = CX, CY
    pl = C.cyl("plinth", 3.55, 0.16, (cx, cy, 0.0), segs=8, mat=dark, col=col, smooth=False); pl.rotation_euler = (0, 0, math.pi / 8)
    pl2 = C.cyl("plinth2", 3.4, 0.1, (cx, cy, 0.16), segs=8, mat=ms, col=col, smooth=False); pl2.rotation_euler = (0, 0, math.pi / 8)
    ring = octo_ring("basin", 3.2, 2.9, 0.2, 0.95, ms, col)
    ring.location = (cx, cy, 0)
    # glowing runes on each outer face + gold trim
    for i in range(8):
        a = math.pi / 4 * i
        fx, fy = cx + 3.2 * math.cos(a) * math.cos(math.pi / 8), cy + 3.2 * math.sin(a) * math.cos(math.pi / 8)
        for k in (-1, 0, 1):
            rx = fx + k * 0.42 * -math.sin(a); ry = fy + k * 0.42 * math.cos(a)
            rn = C.box(f"rune{i}{k}", (0.16 if k else 0.24, 0.03, 0.22 if k else 0.3), (rx + 0.01 * math.cos(a), ry + 0.01 * math.sin(a), 0.58),
                       C.glow_mat("FV_Rune", (0.25, 0.7, 1.0), 1.6), col)
            rn.rotation_euler = (0, 0, a + math.pi / 2)
            if k == 0:
                rn.rotation_euler = (0, math.pi / 4, a + math.pi / 2)
    C.torus("trim", 3.29, 0.035, (cx, cy, 0.95), mat=gold, col=col, segs=8, rsegs=6, rot=(0, 0, math.pi / 8))
    floor = C.cyl("basin_floor", 2.92, 0.1, (cx, cy, 0.2), segs=8, mat=C.principled("FV_PoolFloor", (0.05, 0.22, 0.30), rough=0.6,
                  emit=(0.08, 0.45, 0.65), emit_strength=0.2), col=col)
    floor.rotation_euler = (0, 0, math.pi / 8)
    for i in range(26):
        a = rnd.uniform(0, 6.28); r = rnd.uniform(1.7, 2.75)
        if i < 14:
            c = C.cyl(f"coin{i}", 0.06, 0.012, (cx + r * math.cos(a), cy + r * math.sin(a), 0.31), segs=12, mat=gold, col=col)
            c.rotation_euler = (rnd.uniform(-0.3, 0.3), rnd.uniform(-0.3, 0.3), 0)
        else:
            C.ico(f"mgem{i}", rnd.uniform(0.05, 0.1), (cx + r * math.cos(a), cy + r * math.sin(a), 0.32), sub=1,
                  mat=C.glow_mat("FV_MoonGem", (0.6, 0.85, 1.0), 6), col=col)
    water = C.cyl("water", 2.91, 0.02, (cx, cy, 0.78), segs=64, mat=anim_water("FV_WaterMain", ring_scale=3.0, glow_strength=0.08, tint=(0.45, 0.78, 0.92)), col=col)
    # pedestal and bowls
    ped = C.lathe("pedestal", [(0.75, 0.2), (0.62, 0.45), (0.45, 0.6), (0.38, 1.2), (0.45, 1.5), (0.7, 1.7), (0.001, 1.72)], segs=48, mat=ms, col=col,
                  close_bottom=True)
    ped.location = (cx, cy, 0)
    for k in range(12):
        a = 2 * math.pi * k / 12
        fl = C.cyl(f"flute{k}", 0.05, 0.6, (cx + 0.4 * math.cos(a), cy + 0.4 * math.sin(a), 0.9), segs=8, mat=ms, col=col)
    bowl = C.lathe("bowl1", [(0.001, 1.62), (0.6, 1.66), (1.25, 1.88), (1.5, 2.08), (1.55, 2.16), (1.42, 2.16), (1.2, 2.0), (0.001, 1.92)], segs=64,
                   mat=ms, col=col)
    bowl.location = (cx, cy, 0)
    C.torus("bowl1_trim", 1.5, 0.03, (cx, cy, 2.12), mat=gold, col=col, segs=64)
    C.cyl("water1", 1.43, 0.02, (cx, cy, 2.1), segs=64, mat=anim_water("FV_WaterBowl", ring_scale=5.0, glow_strength=0.08, tint=(0.45, 0.78, 0.92)), col=col)
    cur = C.lathe("curtain1", [(1.56, 2.14), (1.62, 1.95), (1.75, 1.5), (1.95, 1.05), (2.15, 0.78)], segs=72,
                  mat=curtain_mat("FV_Curtain1"), col=col)
    cur.location = (cx, cy, 0)
    stem2 = C.lathe("stem2", [(0.3, 2.0), (0.18, 2.3), (0.2, 2.7), (0.42, 2.85), (0.001, 2.86)], segs=32, mat=ms, col=col)
    stem2.location = (cx, cy, 0)
    bowl2 = C.lathe("bowl2", [(0.001, 2.8), (0.5, 2.88), (0.72, 3.02), (0.76, 3.08), (0.68, 3.08), (0.001, 2.96)], segs=48, mat=ms, col=col)
    bowl2.location = (cx, cy, 0)
    C.cyl("water2", 0.69, 0.02, (cx, cy, 3.04), segs=48, mat=anim_water("FV_WaterBowl", ring_scale=5.0, glow_strength=0.08, tint=(0.45, 0.78, 0.92)), col=col)
    cur2 = C.lathe("curtain2", [(0.77, 3.06), (0.82, 2.85), (0.92, 2.5), (1.02, 2.12)], segs=48, mat=curtain_mat("FV_Curtain2"), col=col)
    cur2.location = (cx, cy, 0)
    # crescent moon crown holding a moon orb
    cr = C.torus("crescent", 0.78, 0.16, (0, 0, 0), mat=ms, col=col, segs=64, rsegs=16, rot=(0, 0, 0))
    bm = bmesh.new(); bm.from_mesh(cr.data)
    dels = [v for v in bm.verts if math.atan2(v.co.y, v.co.x) > math.radians(-35) and math.atan2(v.co.y, v.co.x) < math.radians(35)]
    for v in bm.verts:
        a = math.atan2(v.co.y, v.co.x)
        taper = min(1.0, (abs(abs(a) - math.pi)) / 2.6) if True else 1
        fac = 0.35 + 0.65 * math.sin(min(math.pi, max(0.0, (abs(a) - math.radians(35)) / math.radians(145) * math.pi / 2 + math.pi / 2)))
    bmesh.ops.delete(bm, geom=dels, context="VERTS"); bm.to_mesh(cr.data); bm.free()
    cr.rotation_euler = (math.pi / 2, math.radians(-90), 0)
    cr.location = (cx, cy, 3.85)
    C.torus("crescent_gold", 0.78, 0.04, (cx, cy - 0.15, 3.85), mat=gold, col=col, segs=64, rot=(math.pi / 2, 0, 0)).scale = (0.98, 0.98, 0.98)
    orb = C.ico("moon_orb", 0.36, (cx, cy, 3.82), sub=4, mat=C.glow_mat("FV_MoonOrb", (0.62, 0.8, 1.0), 3.2), col=col)
    halo = C.ico("orb_halo", 0.5, (cx, cy, 3.82), sub=3, mat=C.principled("FV_Halo", (0.7, 0.85, 1.0), emit=(0.6, 0.85, 1.0), emit_strength=0.5, alpha=0.12), col=col)
    Lo = bpy.data.lights.new("orbL", "POINT"); Lo.energy = 90; Lo.color = (0.6, 0.82, 1.0); Lo.shadow_soft_size = 0.3
    lo = bpy.data.objects.new("orbL", Lo); lo.location = (cx, cy, 3.72); col.objects.link(lo)
    Lw = bpy.data.lights.new("poolL", "POINT"); Lw.energy = 25; Lw.color = (0.35, 0.8, 1.0)
    lw = bpy.data.objects.new("poolL", Lw); lw.location = (cx, cy - 1.8, 1.2); col.objects.link(lw)
    # lily pads + lotus in the basin
    pad_m = C.principled("FV_LilyPad", (0.16, 0.46, 0.12), rough=0.35, sss=0.2)
    for i in range(7):
        a = rnd.uniform(0, 6.28); r = rnd.uniform(1.8, 2.6)
        pd = C.cyl(f"pad{i}", rnd.uniform(0.18, 0.3), 0.015, (cx + r * math.cos(a), cy + r * math.sin(a), 0.8), segs=24, mat=pad_m, col=col)
        pd.rotation_euler = (0, 0, rnd.uniform(0, 6.28))
        if i % 2 == 0:
            C.flower(f"lotus{i}", (cx + r * math.cos(a), cy + r * math.sin(a), 0.82), r=0.15, petals=8, c_base=(1.0, 0.55, 0.78), c_tip=(1, 0.95, 0.98),
                     col=col, glow=(1.0, 0.6, 0.85), cup=0.6)
    # corner planters (outside the octagon, inside the 5x5 tile square)
    for i, (ox, oy) in enumerate(((-1, -1), (1, -1), (-1, 1), (1, 1))):
        px, py = cx + ox * (W / 2 - 0.55), cy + oy * (D / 2 - 0.55)
        urn = C.lathe(f"urn{i}", [(0.001, 0), (0.25, 0.02), (0.18, 0.15), (0.3, 0.45), (0.36, 0.55), (0.3, 0.58)], segs=24, mat=ms, col=col,
                      close_bottom=True)
        urn.location = (px, py, 0)
        for q in range(7):
            aa = 2 * math.pi * q / 7
            C.flower(f"urnfl{i}{q}", (px + 0.18 * math.cos(aa), py + 0.18 * math.sin(aa), 0.6 + 0.05 * (q % 2)), r=0.09,
                     c_base=[(0.75, 0.6, 1.0), (1.0, 0.6, 0.8), (0.6, 0.85, 1.0)][q % 3], c_tip=(1, 1, 1), col=col, glow=(0.8, 0.8, 1.0))
        leaves(f"urnlv{i}", (px, py, 0.62), 0.22, col, n=30)
    sparkles("spk", 46, (cx, cy), 0.35, 2.6, 2.2, 5.4, col, seed=22)
    sparkles("spl", 18, (cx, cy), 1.6, 2.9, 0.85, 1.8, col, seed=23, size=0.05)
    return {"anim": True}


def build_lily_fountain(col):
    rnd = random.Random(31)
    ms = C.stone_mat("FV_FountainStone", (0.44, 0.46, 0.54), (0.66, 0.67, 0.75), moss_amt=0.04, emit_veins=(0.25, 0.5, 0.8))
    cx, cy = CX, CY
    prof = [(1.5, 0.48), (1.5, 0.08), (1.95, 0.0), (1.98, 0.38), (2.07, 0.5), (2.0, 0.56), (1.5, 0.56)]
    basin = C.lathe("lbasin", prof, segs=96, mat=ms, col=col)
    bm = bmesh.new(); bm.from_mesh(basin.data)
    for v in bm.verts:
        a = math.atan2(v.co.y, v.co.x); r = math.hypot(v.co.x, v.co.y)
        k = 1 + 0.055 * math.cos(8 * a) * (r / 2.0)
        v.co.x *= k; v.co.y *= k
    bm.to_mesh(basin.data); bm.free()
    basin.location = (cx, cy, 0)
    C.cyl("lfloor", 1.55, 0.05, (cx, cy, 0.06), segs=48, mat=C.principled("FV_PoolFloor", (0.05, 0.22, 0.30), emit=(0.08, 0.45, 0.65), emit_strength=0.2), col=col)
    C.cyl("lwater", 1.56, 0.02, (cx, cy, 0.44), segs=64, mat=anim_water("FV_WaterLily", ring_scale=4.0, glow_strength=0.08, tint=(0.45, 0.78, 0.92)), col=col)
    stalk = C.lathe("lstalk", [(0.22, 0.05), (0.13, 0.4), (0.11, 0.8), (0.16, 0.95), (0.001, 0.97)], segs=24, mat=ms, col=col)
    stalk.location = (cx, cy, 0)
    stone_petal = C.petal_mat("FV_StonePetal", (0.62, 0.62, 0.72), (0.88, 0.84, 0.94), glow=(0.7, 0.8, 1.0), glow_strength=0.04)
    for layer, (n, L, Wd, tilt, z) in enumerate(((8, 0.62, 0.36, 62, 0.92), (6, 0.48, 0.3, 40, 0.95))):
        for k in range(n):
            a = 2 * math.pi * k / n + layer * 0.4
            pt = petal_mesh(f"lp{layer}_{k}", L, Wd, 0.3, stone_petal, col)
            pt.rotation_mode = "ZXY"; pt.rotation_euler = (math.radians(tilt), 0, a - math.pi / 2)
            pt.location = (cx, cy, z)
    C.ico("lcore", 0.12, (cx, cy, 1.02), sub=3, mat=C.glow_mat("FV_LilyCore", (1.0, 0.85, 0.5), 7), col=col)
    # three water arcs
    arc_m = curtain_mat("FV_ArcWater")
    for k in range(3):
        a = 2 * math.pi * k / 3 + 0.5
        pts = [(cx, cy, 1.08), (cx + 0.45 * math.cos(a), cy + 0.45 * math.sin(a), 1.45), (cx + 0.95 * math.cos(a), cy + 0.95 * math.sin(a), 1.2),
               (cx + 1.25 * math.cos(a), cy + 1.25 * math.sin(a), 0.45)]
        C.tube_curve(f"arc{k}", pts, radius=0.045, mat=arc_m, col=col, radii=[0.6, 1.0, 1.0, 1.3])
    pad_m = C.principled("FV_LilyPad", (0.16, 0.46, 0.12), rough=0.35, sss=0.2)
    for i in range(6):
        a = 2 * math.pi * i / 6 + rnd.uniform(-0.2, 0.2); r = rnd.uniform(0.75, 1.3)
        pd = C.cyl(f"lpad{i}", rnd.uniform(0.16, 0.25), 0.012, (cx + r * math.cos(a), cy + r * math.sin(a), 0.46), segs=24, mat=pad_m, col=col)
        if i % 2:
            C.flower(f"llotus{i}", (cx + r * math.cos(a), cy + r * math.sin(a), 0.48), r=0.12, petals=8, c_base=(1.0, 0.5, 0.75), c_tip=(1, 0.95, 1),
                     col=col, glow=(1.0, 0.55, 0.8), cup=0.6)
    Lw = bpy.data.lights.new("lpoolL", "POINT"); Lw.energy = 15; Lw.color = (0.4, 0.85, 1.0)
    lw = bpy.data.objects.new("lpoolL", Lw); lw.location = (cx, cy - 0.8, 1.3); col.objects.link(lw)
    for i in range(10):
        a = rnd.uniform(0, 6.28); r = rnd.uniform(2.05, 2.15)
        x, y = cx + r * math.cos(a), cy + r * math.sin(a)
        if 0.1 < x < W - 0.1 and -D + 0.1 < y < -0.1 and not (abs(x - cx) < 0.7 and y < cy):
            C.flower(f"lfl{i}", (x, y, 0), r=0.08, c_base=(0.75, 0.6, 1.0), c_tip=(1, 1, 1), col=col)
    sparkles("lsp", 26, (cx, cy), 0.2, 1.5, 0.6, 2.4, col, seed=32, size=0.05)
    return {"anim": True}


BUILDERS = {"queens_tree_hall": build_tree_hall, "mushroom_apothecary": build_apothecary, "moonpetal_inn": build_inn,
            "moonstone_fountain": build_moonstone_fountain, "lily_fountain": build_lily_fountain}


# ============================================================ main
def fireflies(col, n, zmax, seed=77):
    rnd = random.Random(seed)
    mats = [C.glow_mat("FV_Firefly", (1.0, 0.82, 0.40), 18), C.glow_mat("FV_FireflyB", (0.65, 1.0, 0.75), 14)]
    for i in range(n):
        x, y = rnd.uniform(0.2, W - 0.2), rnd.uniform(-D + 0.2, -0.2)
        C.ico(f"firefly{i}", rnd.uniform(0.025, 0.05), (x, y, rnd.uniform(0.4, zmax)), sub=1, mat=mats[i % 2], col=col)


def main():
    sc = C.reset()
    C.rig(sc)
    col = col_new(KEY.upper())
    meta = BUILDERS[KEY](col) or {}
    if not SP.get("anim"):
        fireflies(col, 45 if KEY == "queens_tree_hall" else 28, 9.0 if KEY == "queens_tree_hall" else 5.0)
    objs = [o for o in col.all_objects if o.type in ("MESH", "CURVE") and not o.hide_render]
    out_meta = {"key": KEY, "name": SP["name"], "footprint_tiles": [SP["W"], SP["D"]], "tile_m": round(C.T, 4),
                "projection": "oblique: ortho camera el 32 deg az 0 on a (1, 1/sin32, 1.4) scaled model (buildings/housing pack)",
                "z_exaggeration": C.ZEX}
    if MODE in ("hero", "both"):
        sc2 = sc
        if meta.get("anim"):
            set_phase(0.0)
        cat = C.hero_ground("hero_ground", max(W, D) * (1.25 if meta.get("anim") else 0.95), (CX, CY, -0.01), col, fade=0.3)
        C.cycles(sc, samples=24 if PREVIEW else SAMPLES, w=2048, h=2048, transparent=True)
        if PREVIEW:
            sc.render.resolution_percentage = 35
        big = max(W, D)
        tz = {"queens_tree_hall": 5.2, "moonstone_fountain": 1.7, "lily_fountain": 0.7}.get(KEY, 3.0)
        cam = C.hero_camera(sc, (CX, CY - 0.3, tz), big * (2.1 if SP.get("anim") else 1.75), az=24, el=(30 if SP.get("anim") else 22), lens=50)
        C.render(sc, f"{OUT}/renders/hero/{KEY}{'_preview' if PREVIEW else ''}.png")
        bpy.data.objects.remove(cam, do_unlink=True)
        bpy.data.objects.remove(cat, do_unlink=True)
    if MODE in ("sprite", "both"):
        root = C.game_root(col)
        for o in col.all_objects:
            if o.parent is None and o is not root:
                o.parent = root
        for o in bpy.context.scene.collection.objects:
            if o.parent is None and o.type == "LIGHT" and o.data.type != "SUN":
                o.parent = root
        root.scale = (1.0, 1.0 / C.SIN, C.ZEX)
        bpy.context.view_layer.update()
        cat = C.shadow_catcher("catcher", 60, (CX, CY, 0.0), col)
        cat.parent = root
        info = C.game_camera(sc, objs)
        C.cycles(sc, samples=24 if PREVIEW else SAMPLES, w=info["size"][0], h=info["size"][1], transparent=True)
        if PREVIEW:
            sc.render.resolution_percentage = 50
        if meta.get("anim"):
            frames = range(FRAMES) if FRAME_ONLY is None else [int(x) for x in FRAME_ONLY.split(",")]
            for f in frames:
                set_phase(f / FRAMES)
                C.render(sc, f"{OUT}/renders/sprite_4x/{KEY}{'_preview' if PREVIEW else ''}/f{f:02d}.png")
                print("FRAME", f, flush=True)
            out_meta.update({"frames": FRAMES, "loop": True, "fps_suggested": 10})
        else:
            C.render(sc, f"{OUT}/renders/sprite_4x/{KEY}{'_preview' if PREVIEW else ''}.png")
        out_meta.update({"sprite_4x": info})
        C.save_json(f"{OUT}/renders/meta/{KEY}.json", out_meta)
    print("DONE", KEY, flush=True)


main()
