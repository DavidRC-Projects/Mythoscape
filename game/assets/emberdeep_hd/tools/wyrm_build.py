"""Emberdeep Wyrm: procedural Blender model, rig, poses and sprite renders.

blender -b -P wyrm_build.py -- test <out.png>                 # low-res contact sheet of key poses
blender -b -P wyrm_build.py -- render <worker> <nworkers>     # resumable frame renders
Frames: dragon/frames/<anim>_<facing>_<i>.png, 768x512, transparent, feet at FEET_PX.
Model faces -Y (south). Facings rotate the model: s 0, e +90, n 180, w -90 degrees about Z.
"""
import bpy, bmesh, math, os, sys, random
from mathutils import Vector, Matrix, Quaternion

ROOT = "/workspace/emberdeep_hd/dragon"
FRAMES = os.path.join(ROOT, "frames")
W, H = 768, 512
ORTHO = 11.6            # world units across 768 px  (66.2 px per unit)
FEET_PX = (384, 330)    # where the ground origin lands on the canvas
ANIMS = {"idle": 4, "walk": 8, "breath": 8, "hit": 3, "death": 8}
FACINGS = {"s": 0.0, "e": 90.0, "n": 180.0, "w": -90.0}
argv = sys.argv[sys.argv.index("--") + 1:]
MODE = argv[0]

bpy.ops.wm.read_factory_settings(use_empty=True)
sc = bpy.context.scene

# ---------------------------------------------------------------- skeleton
X = 1
def L(v):  # mirror helper
    return Vector(v)
BONES = {}   # name -> (head, tail, parent, deform)
def bone(name, head, tail, parent=None, deform=True):
    BONES[name] = (Vector(head), Vector(tail), parent, deform)

bone("root", (0, 0, 0), (0, 0, 0.6), None, False)
bone("hips", (0, 1.3, 1.45), (0, 0.4, 1.55), "root")
bone("spine", (0, 0.4, 1.55), (0, -0.6, 1.62), "hips")
bone("chest", (0, -0.6, 1.62), (0, -1.3, 1.78), "spine")
NECK = [(0, -1.3, 1.78), (0, -1.85, 2.18), (0, -2.25, 2.62), (0, -2.6, 3.02), (0, -2.9, 3.25)]
for i in range(4):
    bone(f"neck{i+1}", NECK[i], NECK[i + 1], "chest" if i == 0 else f"neck{i}")
bone("head", (0, -2.9, 3.25), (0, -4.15, 3.0), "neck4")
bone("jaw", (0, -3.0, 2.98), (0, -3.95, 2.78), "head")
TAIL = [(0, 1.3, 1.45), (0, 2.2, 1.22), (0, 3.0, 0.95), (0, 3.8, 0.7), (0, 4.6, 0.52), (0, 5.4, 0.42), (0, 6.25, 0.36)]
for i in range(6):
    bone(f"tail{i+1}", TAIL[i], TAIL[i + 1], "hips" if i == 0 else f"tail{i}")
for s, sx in (("L", 1), ("R", -1)):
    bone(f"fl_up.{s}", (sx * 0.62, -1.15, 1.38), (sx * 0.82, -1.0, 0.78), "chest")
    bone(f"fl_lo.{s}", (sx * 0.82, -1.0, 0.78), (sx * 0.84, -1.25, 0.2), f"fl_up.{s}")
    bone(f"fl_ft.{s}", (sx * 0.84, -1.25, 0.2), (sx * 0.88, -1.65, 0.06), f"fl_lo.{s}")
    bone(f"hl_up.{s}", (sx * 0.64, 1.25, 1.3), (sx * 0.88, 0.72, 0.78), "hips")
    bone(f"hl_lo.{s}", (sx * 0.88, 0.72, 0.78), (sx * 0.9, 1.22, 0.32), f"hl_up.{s}")
    bone(f"hl_ft.{s}", (sx * 0.9, 1.22, 0.32), (sx * 0.92, 0.88, 0.06), f"hl_lo.{s}")
    bone(f"w_hum.{s}", (sx * 0.45, -0.9, 2.1), (sx * 1.75, -0.55, 2.95), "chest")
    bone(f"w_fore.{s}", (sx * 1.75, -0.55, 2.95), (sx * 3.05, 0.15, 2.72), f"w_hum.{s}")
    bone(f"w_f1.{s}", (sx * 3.05, 0.15, 2.72), (sx * 4.45, 0.8, 1.95), f"w_fore.{s}")
    bone(f"w_f2.{s}", (sx * 3.05, 0.15, 2.72), (sx * 3.95, 1.7, 1.45), f"w_fore.{s}")
    bone(f"w_f3.{s}", (sx * 3.05, 0.15, 2.72), (sx * 3.05, 2.2, 1.42), f"w_fore.{s}")

arm_data = bpy.data.armatures.new("rig")
rig = bpy.data.objects.new("rig", arm_data)
sc.collection.objects.link(rig)
bpy.context.view_layer.objects.active = rig
bpy.ops.object.mode_set(mode="EDIT")
for name, (h, t, p, d) in BONES.items():
    eb = arm_data.edit_bones.new(name)
    eb.head, eb.tail = h, t
    eb.use_deform = d
    if abs((t - h).normalized().z) > 0.9:
        eb.align_roll(Vector((0, -1, 0)))
    else:
        eb.align_roll(Vector((0, 0, 1)))
for name, (h, t, p, d) in BONES.items():
    if p:
        arm_data.edit_bones[name].parent = arm_data.edit_bones[p]
bpy.ops.object.mode_set(mode="OBJECT")

def seg_dist(p, a, b):
    ab = b - a
    t = max(0.0, min(1.0, (p - a).dot(ab) / max(1e-9, ab.dot(ab))))
    return (p - (a + ab * t)).length

def weight_mesh(ob, allowed, power=6, top=3):
    for n in allowed:
        ob.vertex_groups.new(name=n)
    segs = [(n, BONES[n][0], BONES[n][1]) for n in allowed]
    for v in ob.data.vertices:
        p = ob.matrix_world @ v.co
        ds = sorted(((seg_dist(p, a, b), n) for n, a, b in segs))[:top]
        ws = [(1.0 / (d + 0.03) ** power, n) for d, n in ds]
        tot = sum(w for w, _ in ws)
        for w, n in ws:
            ob.vertex_groups[n].add([v.index], w / tot, "REPLACE")
    mod = ob.modifiers.new("arm", "ARMATURE"); mod.object = rig

def rigid(ob, bone_name):
    ob.parent = rig; ob.parent_type = "BONE"; ob.parent_bone = bone_name
    # keep world placement: bone parenting puts the child at the bone tail
    bm = rig.data.bones[bone_name]
    mw = rig.matrix_world @ bm.matrix_local @ Matrix.Translation((0, bm.length, 0))
    ob.matrix_parent_inverse = mw.inverted()

def skin_mesh(name, pts, edges, roots=(0,), subdiv=2):
    me = bpy.data.meshes.new(name)
    me.from_pydata([p[0] for p in pts], edges, [])
    ob = bpy.data.objects.new(name, me); sc.collection.objects.link(ob)
    sk = ob.modifiers.new("skin", "SKIN"); sk.use_smooth_shade = True; sk.branch_smoothing = 0.6
    for i, p in enumerate(pts):
        r = p[1] if isinstance(p[1], tuple) else (p[1], p[1])
        ob.data.skin_vertices[0].data[i].radius = r
        ob.data.skin_vertices[0].data[i].use_root = i in roots
    ss = ob.modifiers.new("sub", "SUBSURF"); ss.levels = ss.render_levels = subdiv
    bpy.context.view_layer.objects.active = ob
    for m in list(ob.modifiers):
        bpy.ops.object.modifier_apply(modifier=m.name)
    ob.data.shade_smooth() if hasattr(ob.data, "shade_smooth") else None
    for poly in ob.data.polygons:
        poly.use_smooth = True
    return ob

# ---------------------------------------------------------------- body
pts, edges = [], []
def P(co, r):
    pts.append((co, r)); return len(pts) - 1
spine_pts = [
    ((0, 6.25, 0.36), 0.05), ((0, 5.4, 0.42), 0.12), ((0, 4.6, 0.52), 0.19), ((0, 3.8, 0.7), 0.27),
    ((0, 3.0, 0.95), 0.37), ((0, 2.2, 1.22), 0.5), ((0, 1.3, 1.45), (0.64, 0.58)), ((0, 0.4, 1.55), (0.74, 0.7)),
    ((0, -0.6, 1.62), (0.8, 0.76)), ((0, -1.3, 1.78), (0.66, 0.64)), ((0, -1.85, 2.18), (0.46, 0.44)),
    ((0, -2.25, 2.62), (0.38, 0.37)), ((0, -2.6, 3.02), (0.34, 0.33)), ((0, -2.9, 3.25), (0.36, 0.34)),
    ((0, -3.35, 3.2), (0.3, 0.27)), ((0, -3.8, 3.07), (0.21, 0.17)), ((0, -4.15, 3.0), (0.11, 0.09)),
]
ids = [P(c, r) for c, r in spine_pts]
for a, b in zip(ids, ids[1:]):
    edges.append((a, b))
HIPS_I, CHEST_I = ids[6], ids[9]
for sx in (1, -1):
    a = P((sx * 0.6, -1.15, 1.35), 0.34); edges.append((CHEST_I, a))
    b = P((sx * 0.82, -1.0, 0.78), 0.22); edges.append((a, b))
    c = P((sx * 0.84, -1.25, 0.2), 0.15); edges.append((b, c))
    d = P((sx * 0.88, -1.62, 0.07), (0.17, 0.07)); edges.append((c, d))
    a = P((sx * 0.62, 1.25, 1.22), 0.44); edges.append((HIPS_I, a))
    b = P((sx * 0.88, 0.72, 0.78), 0.3); edges.append((a, b))
    c = P((sx * 0.9, 1.22, 0.32), 0.16); edges.append((b, c))
    d = P((sx * 0.92, 0.9, 0.07), (0.18, 0.07)); edges.append((c, d))
body = skin_mesh("body", pts, edges, roots=(ids[8],), subdiv=2)
non_wing = [n for n in BONES if BONES[n][3] and not n.startswith("w_") and n != "jaw"]
weight_mesh(body, non_wing)

jaw = skin_mesh("jaw", [((0, -3.0, 2.98), (0.27, 0.16)), ((0, -3.5, 2.84), (0.2, 0.11)), ((0, -3.98, 2.8), (0.1, 0.06))],
                [(0, 1), (1, 2)], roots=(0,), subdiv=2)
rigid(jaw, "jaw")

# wings: membrane + finger bones
for s, sx in (("L", 1), ("R", -1)):
    A = Vector((sx * 0.5, -0.95, 2.02)); E = BONES[f"w_hum.{s}"][1]; Wr = BONES[f"w_fore.{s}"][1]
    F1, F2, F3 = BONES[f"w_f1.{s}"][1], BONES[f"w_f2.{s}"][1], BONES[f"w_f3.{s}"][1]
    B = Vector((sx * 0.6, 1.15, 1.72))
    def sag(p, q, k=0.28):
        m = (p + q) / 2
        return m + (Wr - m) * k
    loop = [A, E, Wr, F1, sag(F1, F2), F2, sag(F2, F3), F3, sag(F3, B, 0.18), B]
    me = bpy.data.meshes.new("wing" + s); bm = bmesh.new()
    vs = [bm.verts.new(v) for v in loop]
    bm.faces.new(vs)
    bmesh.ops.triangulate(bm, faces=bm.faces[:])
    bmesh.ops.subdivide_edges(bm, edges=bm.edges[:], cuts=4, use_grid_fill=True)
    bm.to_mesh(me); bm.free()
    ob = bpy.data.objects.new("wing" + s, me); sc.collection.objects.link(ob)
    so = ob.modifiers.new("sol", "SOLIDIFY"); so.thickness = 0.03; so.offset = 0
    bpy.context.view_layer.objects.active = ob
    bpy.ops.object.modifier_apply(modifier="sol")
    for poly in ob.data.polygons:
        poly.use_smooth = True
    weight_mesh(ob, [f"w_hum.{s}", f"w_fore.{s}", f"w_f1.{s}", f"w_f2.{s}", f"w_f3.{s}", "chest", "hips"], power=4)
    # finger struts
    fp = [(A, 0.09), (E, 0.08), (Wr, 0.07), (F1, 0.025), (F2, 0.025), (F3, 0.025)]
    fe = [(0, 1), (1, 2), (2, 3), (2, 4), (2, 5)]
    fing = skin_mesh("finger" + s, [(tuple(p), r) for p, r in fp], fe, roots=(0,), subdiv=1)
    weight_mesh(fing, [f"w_hum.{s}", f"w_fore.{s}", f"w_f1.{s}", f"w_f2.{s}", f"w_f3.{s}"], power=8)
    fing["mat"] = "horn"; ob["mat"] = "membrane"

# horns, spikes, eyes, teeth
def cone(name, base, tip, r, bone_name, mat="horn", bend=0.0):
    me = bpy.data.meshes.new(name); bm = bmesh.new()
    bmesh.ops.create_cone(bm, cap_ends=True, segments=10, radius1=r, radius2=0.004, depth=1.0)
    bm.to_mesh(me); bm.free()
    ob = bpy.data.objects.new(name, me); sc.collection.objects.link(ob)
    d = Vector(tip) - Vector(base)
    ob.location = (Vector(base) + Vector(tip)) / 2
    ob.rotation_mode = "QUATERNION"; ob.rotation_quaternion = Vector((0, 0, 1)).rotation_difference(d.normalized())
    ob.scale = (1, 1, d.length)
    if bend:
        sd = ob.modifiers.new("b", "SIMPLE_DEFORM"); sd.deform_method = "BEND"; sd.angle = bend; sd.deform_axis = "X"
    for poly in ob.data.polygons:
        poly.use_smooth = True
    ob["mat"] = mat
    bpy.context.view_layer.update()
    rigid(ob, bone_name)
    return ob

for sx in (1, -1):
    cone("hornA", (sx * 0.18, -2.85, 3.45), (sx * 0.42, -2.2, 3.95), 0.09, "head", bend=0.5)
    cone("hornB", (sx * 0.26, -2.95, 3.3), (sx * 0.62, -2.45, 3.55), 0.06, "head", bend=0.4)
    cone("cheek", (sx * 0.28, -3.15, 3.05), (sx * 0.52, -2.95, 2.95), 0.04, "head")
    for k in range(5):
        y = -3.25 - k * 0.17
        cone("tooth", (sx * 0.13, y, 2.94 - k * 0.025), (sx * 0.13, y, 2.82 - k * 0.025), 0.022, "head", mat="tooth")
    me = bpy.data.meshes.new("eye"); bm = bmesh.new(); bmesh.ops.create_uvsphere(bm, u_segments=12, v_segments=8, radius=0.055)
    bm.to_mesh(me); bm.free()
    ey = bpy.data.objects.new("eye", me); sc.collection.objects.link(ey); ey.location = (sx * 0.2, -3.42, 3.3); ey["mat"] = "eye"
    bpy.context.view_layer.update(); rigid(ey, "head")
for sx in (1, -1):
    for k, (y, z) in enumerate(((-1.7, 0.47), (-1.0, 0.62))):
        pass
spk = [("neck1", (0, -1.55, 2.38), 0.2), ("neck2", (0, -2.05, 2.8), 0.17), ("neck3", (0, -2.45, 3.2), 0.14),
       ("chest", (0, -0.95, 2.38), 0.32), ("spine", (0, -0.1, 2.26), 0.36), ("spine", (0, 0.45, 2.22), 0.34),
       ("hips", (0, 1.0, 2.04), 0.3), ("tail1", (0, 1.75, 1.72), 0.26), ("tail2", (0, 2.6, 1.35), 0.21),
       ("tail3", (0, 3.4, 1.0), 0.17), ("tail4", (0, 4.2, 0.74), 0.13), ("tail5", (0, 5.0, 0.56), 0.1)]
for bn, (x, y, z), r in spk:
    cone("spike", (x, y + 0.08, z - 0.15), (x, y + 0.32, z + r * 1.6), r * 0.42, bn)
# claws: three per foot so the feet read in every facing
for sx in (1, -1):
    for dx in (-0.09, 0.0, 0.09):
        cone("claw", (sx * 0.88 + dx, -1.6, 0.07), (sx * 0.88 + dx * 1.3, -1.86, 0.015), 0.035, f"fl_ft.{'L' if sx > 0 else 'R'}", mat="tooth")
        cone("claw", (sx * 0.92 + dx, 0.84, 0.07), (sx * 0.92 + dx * 1.3, 0.6, 0.015), 0.035, f"hl_ft.{'L' if sx > 0 else 'R'}", mat="tooth")
# tail blade
cone("blade", (0, 6.0, 0.4), (0, 6.75, 0.42), 0.16, "tail6")
# mouth glow (seen when the jaw opens) and the breath flame
me = bpy.data.meshes.new("mouth"); bm = bmesh.new(); bmesh.ops.create_uvsphere(bm, u_segments=12, v_segments=8, radius=0.16)
bm.to_mesh(me); bm.free()
mouth = bpy.data.objects.new("mouth", me); sc.collection.objects.link(mouth); mouth.location = (0, -3.5, 2.9); mouth["mat"] = "mouth"
bpy.context.view_layer.update(); rigid(mouth, "head")
me = bpy.data.meshes.new("flame"); bm = bmesh.new()
bmesh.ops.create_cone(bm, cap_ends=False, segments=24, radius1=0.08, radius2=0.95, depth=3.2)
bmesh.ops.subdivide_edges(bm, edges=bm.edges[:], cuts=6, use_grid_fill=False)
bm.to_mesh(me); bm.free()
flame = bpy.data.objects.new("flame", me); sc.collection.objects.link(flame)
flame.rotation_euler = (math.radians(90), 0, 0)   # cone axis -> -Y
flame.location = (0, -4.15 - 1.6, 2.85)
tex = bpy.data.textures.new("fl", "CLOUDS"); tex.noise_scale = 0.35
fd = flame.modifiers.new("d", "DISPLACE"); fd.texture = tex; fd.strength = 0.25
flame["mat"] = "flame"
bpy.context.view_layer.update(); rigid(flame, "head")
body["mat"] = "scale"; jaw["mat"] = "scale"

# ---------------------------------------------------------------- materials
def mat_scale():
    m = bpy.data.materials.new("scale"); m.use_nodes = True
    N, Lk = m.node_tree.nodes, m.node_tree.links
    b = N["Principled BSDF"]; b.inputs["Roughness"].default_value = 0.42
    b.inputs["Coat Weight"].default_value = 0.1
    at = N.new("ShaderNodeAttribute"); at.attribute_name = "rest"
    v = N.new("ShaderNodeTexVoronoi"); v.feature = "DISTANCE_TO_EDGE"; v.inputs["Scale"].default_value = 9.0
    Lk.new(at.outputs["Vector"], v.inputs["Vector"])
    vf = N.new("ShaderNodeTexVoronoi"); vf.inputs["Scale"].default_value = 9.0
    Lk.new(at.outputs["Vector"], vf.inputs["Vector"])
    n = N.new("ShaderNodeTexNoise"); n.inputs["Scale"].default_value = 1.4; n.inputs["Detail"].default_value = 4
    Lk.new(at.outputs["Vector"], n.inputs["Vector"])
    geo = N.new("ShaderNodeNewGeometry")
    sep = N.new("ShaderNodeSeparateXYZ"); Lk.new(geo.outputs["Normal"], sep.inputs[0])
    belly = N.new("ShaderNodeMapRange"); belly.inputs["From Min"].default_value = -0.2; belly.inputs["From Max"].default_value = -0.65
    Lk.new(sep.outputs["Z"], belly.inputs["Value"])
    top = N.new("ShaderNodeValToRGB")
    top.color_ramp.elements[0].color = (0.014, 0.008, 0.008, 1); top.color_ramp.elements[1].color = (0.10, 0.026, 0.018, 1)
    Lk.new(n.outputs["Fac"], top.inputs["Fac"])
    cb = N.new("ShaderNodeMix"); cb.data_type = "RGBA"; cb.inputs[7].default_value = (0.32, 0.17, 0.07, 1)
    Lk.new(belly.outputs["Result"], cb.inputs["Factor"]); Lk.new(top.outputs["Color"], cb.inputs[6])
    # per-scale value jitter
    jit = N.new("ShaderNodeMix"); jit.data_type = "RGBA"; jit.blend_type = "MULTIPLY"; jit.inputs["Factor"].default_value = 0.55
    bw = N.new("ShaderNodeMapRange"); bw.inputs["To Min"].default_value = 0.55; bw.inputs["To Max"].default_value = 1.15
    Lk.new(vf.outputs["Distance"], bw.inputs["Value"])
    Lk.new(cb.outputs[2], jit.inputs[6]); Lk.new(bw.outputs["Result"], jit.inputs[7])
    Lk.new(jit.outputs[2], b.inputs["Base Color"])
    # scale relief
    ed = N.new("ShaderNodeMapRange"); ed.inputs["From Min"].default_value = 0.0; ed.inputs["From Max"].default_value = 0.18
    Lk.new(v.outputs["Distance"], ed.inputs["Value"])
    bump = N.new("ShaderNodeBump"); bump.inputs["Strength"].default_value = 0.7; bump.inputs["Distance"].default_value = 0.03
    Lk.new(ed.outputs["Result"], bump.inputs["Height"]); Lk.new(bump.outputs["Normal"], b.inputs["Normal"])
    # ember glow in the seams, stronger on chest/throat; driven per frame via "ember" value node
    ember = N.new("ShaderNodeValue"); ember.name = "ember"; ember.outputs[0].default_value = 0.6
    seam = N.new("ShaderNodeMapRange"); seam.inputs["From Min"].default_value = 0.018; seam.inputs["From Max"].default_value = 0.0
    Lk.new(v.outputs["Distance"], seam.inputs["Value"])
    mask = N.new("ShaderNodeMath"); mask.operation = "MULTIPLY"
    Lk.new(seam.outputs["Result"], mask.inputs[0]); Lk.new(belly.outputs["Result"], mask.inputs[1])
    msk2 = N.new("ShaderNodeMath"); msk2.operation = "MULTIPLY_ADD"; msk2.inputs[1].default_value = 0.06
    Lk.new(seam.outputs["Result"], msk2.inputs[0]); Lk.new(mask.outputs[0], msk2.inputs[2])
    em = N.new("ShaderNodeMath"); em.operation = "MULTIPLY"
    Lk.new(msk2.outputs[0], em.inputs[0]); Lk.new(ember.outputs[0], em.inputs[1])
    b.inputs["Emission Color"].default_value = (1.0, 0.28, 0.04, 1)
    em2 = N.new("ShaderNodeMath"); em2.operation = "MULTIPLY"; em2.inputs[1].default_value = 3.0
    Lk.new(em.outputs[0], em2.inputs[0]); Lk.new(em2.outputs[0], b.inputs["Emission Strength"])
    return m

def mat_simple(name, col, rough=0.5, emit=None, strength=0.0):
    m = bpy.data.materials.new(name); m.use_nodes = True
    b = m.node_tree.nodes["Principled BSDF"]
    b.inputs["Base Color"].default_value = col; b.inputs["Roughness"].default_value = rough
    if emit:
        b.inputs["Emission Color"].default_value = emit; b.inputs["Emission Strength"].default_value = strength
    return m

def mat_horn():
    m = bpy.data.materials.new("horn"); m.use_nodes = True
    N, Lk = m.node_tree.nodes, m.node_tree.links
    b = N["Principled BSDF"]; b.inputs["Roughness"].default_value = 0.45
    tc = N.new("ShaderNodeTexCoord"); sep = N.new("ShaderNodeSeparateXYZ"); Lk.new(tc.outputs["Generated"], sep.inputs[0])
    r = N.new("ShaderNodeValToRGB")
    r.color_ramp.elements[0].color = (0.30, 0.25, 0.18, 1); r.color_ramp.elements[1].color = (0.02, 0.015, 0.012, 1)
    Lk.new(sep.outputs["Z"], r.inputs["Fac"]); Lk.new(r.outputs["Color"], b.inputs["Base Color"])
    n = N.new("ShaderNodeTexNoise"); n.inputs["Scale"].default_value = 30
    bump = N.new("ShaderNodeBump"); bump.inputs["Strength"].default_value = 0.4
    Lk.new(n.outputs["Fac"], bump.inputs["Height"]); Lk.new(bump.outputs["Normal"], b.inputs["Normal"])
    return m

def mat_membrane():
    m = bpy.data.materials.new("membrane"); m.use_nodes = True
    N, Lk = m.node_tree.nodes, m.node_tree.links
    b = N["Principled BSDF"]; b.inputs["Roughness"].default_value = 0.55
    at = N.new("ShaderNodeAttribute"); at.attribute_name = "rest"
    n = N.new("ShaderNodeTexNoise"); n.inputs["Scale"].default_value = 2.5; n.inputs["Detail"].default_value = 6
    Lk.new(at.outputs["Vector"], n.inputs["Vector"])
    vein = N.new("ShaderNodeTexWave"); vein.wave_type = "RINGS"; vein.inputs["Scale"].default_value = 1.2
    vein.inputs["Distortion"].default_value = 6
    Lk.new(at.outputs["Vector"], vein.inputs["Vector"])
    r = N.new("ShaderNodeValToRGB")
    r.color_ramp.elements[0].color = (0.05, 0.012, 0.01, 1); r.color_ramp.elements[1].color = (0.24, 0.05, 0.03, 1)
    Lk.new(n.outputs["Fac"], r.inputs["Fac"])
    mx = N.new("ShaderNodeMix"); mx.data_type = "RGBA"; mx.blend_type = "MULTIPLY"; mx.inputs["Factor"].default_value = 0.35
    Lk.new(r.outputs["Color"], mx.inputs[6]); Lk.new(vein.outputs["Color"], mx.inputs[7])
    Lk.new(mx.outputs[2], b.inputs["Base Color"])
    b.inputs["Subsurface Weight"].default_value = 0.0
    b.inputs["Transmission Weight"].default_value = 0.0
    tr = N.new("ShaderNodeBsdfTranslucent"); tr.inputs["Color"].default_value = (0.5, 0.08, 0.03, 1)
    mixs = N.new("ShaderNodeMixShader"); mixs.inputs[0].default_value = 0.3
    out = N["Material Output"]
    Lk.new(b.outputs["BSDF"], mixs.inputs[1]); Lk.new(tr.outputs["BSDF"], mixs.inputs[2]); Lk.new(mixs.outputs[0], out.inputs["Surface"])
    return m

def mat_flame():
    m = bpy.data.materials.new("flame"); m.use_nodes = True
    N, Lk = m.node_tree.nodes, m.node_tree.links
    for nd in list(N):
        if nd.type != "OUTPUT_MATERIAL":
            N.remove(nd)
    out = N["Material Output"]
    tc = N.new("ShaderNodeTexCoord")
    n = N.new("ShaderNodeTexNoise"); n.inputs["Scale"].default_value = 3.0; n.inputs["Detail"].default_value = 6
    n.name = "fnoise"
    Lk.new(tc.outputs["Object"], n.inputs["Vector"])
    sep = N.new("ShaderNodeSeparateXYZ"); Lk.new(tc.outputs["Generated"], sep.inputs[0])
    r = N.new("ShaderNodeValToRGB")
    e = r.color_ramp.elements
    e[0].position = 0.0; e[0].color = (1.0, 0.42, 0.04, 1); e[1].position = 1.0; e[1].color = (0.35, 0.02, 0.0, 1)
    e2 = r.color_ramp.elements.new(0.3); e2.color = (0.9, 0.14, 0.01, 1)
    Lk.new(sep.outputs["Z"], r.inputs["Fac"])
    emi = N.new("ShaderNodeEmission"); emi.inputs["Strength"].default_value = 1.6
    Lk.new(r.outputs["Color"], emi.inputs["Color"])
    # alpha: noisy, fading toward the far end
    fade = N.new("ShaderNodeMath"); fade.operation = "SUBTRACT"; fade.inputs[0].default_value = 1.15
    Lk.new(sep.outputs["Z"], fade.inputs[1])
    a = N.new("ShaderNodeMath"); a.operation = "MULTIPLY"
    Lk.new(fade.outputs[0], a.inputs[0]); Lk.new(n.outputs["Fac"], a.inputs[1])
    a2 = N.new("ShaderNodeMapRange"); a2.inputs["From Min"].default_value = 0.2; a2.inputs["From Max"].default_value = 0.34
    Lk.new(a.outputs[0], a2.inputs["Value"])
    tr = N.new("ShaderNodeBsdfTransparent")
    mixs = N.new("ShaderNodeMixShader")
    Lk.new(a2.outputs["Result"], mixs.inputs[0]); Lk.new(tr.outputs["BSDF"], mixs.inputs[1]); Lk.new(emi.outputs["Emission"], mixs.inputs[2])
    Lk.new(mixs.outputs[0], out.inputs["Surface"])
    m.blend_method = "BLEND"
    return m

MATS = {
    "scale": mat_scale(), "horn": mat_horn(), "membrane": mat_membrane(), "flame": mat_flame(),
    "tooth": mat_simple("tooth", (0.7, 0.62, 0.5, 1), 0.4),
    "eye": mat_simple("eye", (1, 0.6, 0.1, 1), 0.2, (1.0, 0.55, 0.08, 1), 12.0),
    "mouth": mat_simple("mouth", (1, 0.3, 0.05, 1), 0.5, (1.0, 0.35, 0.05, 1), 4.0),
}
for ob in list(sc.objects):
    if ob.type == "MESH":
        key = ob.get("mat", "scale")
        ob.data.materials.clear(); ob.data.materials.append(MATS[key])
        # rest-position attribute so procedural textures stick to the skin
        a = ob.data.attributes.new("rest", "FLOAT_VECTOR", "POINT")
        mw = ob.matrix_world
        for i, v in enumerate(ob.data.vertices):
            a.data[i].vector = mw @ v.co
        if ob.parent is None and not any(m.type == "ARMATURE" for m in ob.modifiers):
            pass
        if not ob.parent and ob.name != "rig":
            ob.parent = rig if any(m.type == "ARMATURE" for m in ob.modifiers) else ob.parent
MOUTH_MAT = MATS["mouth"].node_tree.nodes["Principled BSDF"]
EMBER = MATS["scale"].node_tree.nodes["ember"]
FNOISE = MATS["flame"].node_tree.nodes["fnoise"]
FNOISE.noise_dimensions = "4D"

# ---------------------------------------------------------------- scene, camera, lights
sc.render.engine = "CYCLES"; sc.cycles.device = "CPU"
sc.render.film_transparent = True
sc.render.resolution_x, sc.render.resolution_y = W, H
sc.view_settings.view_transform = "AgX"
try:
    sc.view_settings.look = "AgX - Medium High Contrast"
except TypeError:
    pass
sc.render.threads_mode = "FIXED"; sc.render.threads = 3
cam_d = bpy.data.cameras.new("cam"); cam_d.type = "ORTHO"; cam_d.ortho_scale = ORTHO
cam = bpy.data.objects.new("cam", cam_d); sc.collection.objects.link(cam); sc.camera = cam
el = math.radians(30)
fwd = Vector((0, math.cos(el), -math.sin(el))); up = Vector((0, math.sin(el), math.cos(el)))
px_per_u = W / ORTHO
off_u = (FEET_PX[1] - H / 2) / px_per_u        # origin sits this far below the centre
target = Vector((0, 0, 0)) + up * off_u
cam.location = target - fwd * 30
cam.rotation_euler = (math.radians(60), 0, 0)
cam_d.clip_end = 100
def sun(name, energy, rot, color=(1, 1, 1), angle=6):
    l = bpy.data.lights.new(name, "SUN"); l.energy = energy; l.color = color; l.angle = math.radians(angle)
    o = bpy.data.objects.new(name, l); sc.collection.objects.link(o); o.rotation_euler = [math.radians(a) for a in rot]
sun("key", 3.2, (34, 0, -30), (1.0, 0.93, 0.85))
sun("rim", 4.0, (-60, 0, 160), (1.0, 0.55, 0.25))
sun("fill", 0.7, (70, 0, 60), (0.6, 0.65, 0.8), 30)
lv = bpy.data.lights.new("lava", "AREA"); lv.energy = 300; lv.size = 8; lv.color = (1.0, 0.35, 0.08)
lo = bpy.data.objects.new("lava", lv); sc.collection.objects.link(lo); lo.location = (0, -6, -1.5); lo.rotation_euler = (math.radians(-110), 0, 0)
w = bpy.data.worlds.new("w"); sc.world = w; w.use_nodes = True
w.node_tree.nodes["Background"].inputs["Color"].default_value = (0.25, 0.22, 0.22, 1)
w.node_tree.nodes["Background"].inputs["Strength"].default_value = 0.35
bpy.ops.mesh.primitive_plane_add(size=40, location=(0, 0, 0))
ground = bpy.context.active_object; ground.is_shadow_catcher = True

# ---------------------------------------------------------------- posing
PB = rig.pose.bones
REST = {b.name: b.matrix_local.to_3x3() for b in rig.data.bones}
for pb in PB:
    pb.rotation_mode = "QUATERNION"

def reset():
    for pb in PB:
        pb.rotation_quaternion = Quaternion(); pb.location = (0, 0, 0); pb.scale = (1, 1, 1)
    rig.rotation_euler = (0, 0, 0)

def rot(name, axis, deg):
    """Rotate bone about a rig-space axis (X lateral +left-wing, Y back, Z up), composed in its chain."""
    M = REST[name]
    q = (M.inverted() @ Matrix.Rotation(math.radians(deg), 3, Vector(axis)) @ M).to_quaternion()
    pb = PB[name]; pb.rotation_quaternion = q @ pb.rotation_quaternion

def wings(lift, spread=0.0, fold=0.0, pitch=28.0):
    for s, sx in (("L", 1), ("R", -1)):
        rot(f"w_hum.{s}", (1, 0, 0), pitch)            # sweep the membrane up behind the shoulders
        rot(f"w_hum.{s}", (0, 1, 0), -sx * lift)       # raise the arm
        rot(f"w_hum.{s}", (0, 0, 1), sx * spread)      # swing forward
        rot(f"w_fore.{s}", (0, 0, 1), -sx * fold)      # fold toward the body
        rot(f"w_f1.{s}", (0, 0, 1), -sx * fold * 0.6)
        rot(f"w_f2.{s}", (0, 0, 1), -sx * fold * 0.5)
        rot(f"w_f3.{s}", (0, 0, 1), -sx * fold * 0.4)

def tail_wave(ph, amp=7.0, lift=0.0):
    for i in range(1, 7):
        rot(f"tail{i}", (0, 0, 1), amp * math.sin(2 * math.pi * (ph - i * 0.11)) * (0.6 + i * 0.12))
        if lift:
            rot(f"tail{i}", (1, 0, 0), lift)

def leg(prefix, s, swing, lift):
    """swing: + = foot forward. lift 0..1 raises the foot."""
    sx = 1
    rot(f"{prefix}_up.{s}", (1, 0, 0), -swing)
    if prefix == "fl":
        rot(f"fl_lo.{s}", (1, 0, 0), 38 * lift)
        rot(f"fl_ft.{s}", (1, 0, 0), 25 * lift)
    else:
        rot(f"hl_lo.{s}", (1, 0, 0), -30 * lift)
        rot(f"hl_ft.{s}", (1, 0, 0), 30 * lift)

def pose(anim, i):
    reset()
    # proud S-neck: head carried high so it reads above the shoulders in the front view
    rot("neck1", (1, 0, 0), -24); rot("neck2", (1, 0, 0), -10); rot("neck4", (1, 0, 0), 12); rot("head", (1, 0, 0), 20)
    n = ANIMS[anim]
    ph = i / n
    ember, mouth, flame_k = 0.55, 0.0, 0.0
    if anim == "idle":
        b = math.sin(2 * math.pi * ph)
        PB["chest"].scale = (1 + 0.025 * b, 1, 1 + 0.03 * b)
        PB["root"].location = (0, 0, 0)
        rot("neck1", (1, 0, 0), -4 + 2 * b); rot("neck3", (1, 0, 0), 3 * b); rot("head", (1, 0, 0), -2 * b)
        tail_wave(ph, 5)
        wings(22 + 4 * b, 8, 30, 30 + 3 * b)
    elif anim == "walk":
        for prefix, s, off in (("hl", "L", 0.0), ("fl", "L", 0.25), ("hl", "R", 0.5), ("fl", "R", 0.75)):
            a = 2 * math.pi * (ph + off)
            leg(prefix, s, 22 * math.cos(a), max(0.0, math.sin(a)))
        PB["root"].location = (0, 0.06 * math.cos(4 * math.pi * ph), 0)   # bone-local Y is world up for root
        rot("hips", (0, 1, 0), 3 * math.sin(2 * math.pi * ph)); rot("chest", (0, 1, 0), -3 * math.sin(2 * math.pi * ph))
        rot("spine", (0, 0, 1), 4 * math.sin(2 * math.pi * ph))
        rot("neck1", (0, 0, 1), -5 * math.sin(2 * math.pi * ph)); rot("neck2", (1, 0, 0), 3 * math.cos(4 * math.pi * ph))
        tail_wave(ph, 9)
        wings(18 + 3 * math.sin(4 * math.pi * ph), 6, 34, 26)
    elif anim == "breath":
        # 0-3 rear back and inhale (telegraph), 4 release on the beat, 5-6 full gout, 7 recover
        rear = [0.25, 0.6, 0.9, 1.0, 0.1, -0.15, -0.1, 0.3][i]
        open_ = [0, 0, 0.15, 0.35, 1.0, 1.0, 0.85, 0.3][i]
        flame_k = [0, 0, 0, 0, 0.55, 1.0, 0.85, 0.25][i]
        glow = [0.2, 0.45, 0.75, 1.0, 1.0, 0.9, 0.7, 0.4][i]
        rot("neck1", (1, 0, 0), -14 * rear); rot("neck2", (1, 0, 0), -10 * rear); rot("neck3", (1, 0, 0), 8 * rear)
        rot("head", (1, 0, 0), 12 * rear + 10 * open_ * (1 - rear))
        rot("jaw", (1, 0, 0), 28 * open_)
        PB["chest"].scale = (1 + 0.06 * glow, 1, 1 + 0.07 * glow)
        rot("chest", (1, 0, 0), -4 * rear)
        wings(22 + 9 * max(rear, 0), 10, 22 - 10 * max(rear, 0), 30 + 5 * max(rear, 0))
        tail_wave(ph, 6, lift=2 * max(rear, 0))
        for s in ("L", "R"):
            leg("fl", s, -4 * rear, 0)
        ember, mouth = 0.55 + 1.2 * glow, 2 + 10 * glow
    elif anim == "hit":
        k = [1.0, 0.55, 0.2][i]
        rot("neck1", (1, 0, 0), -12 * k); rot("neck2", (1, 0, 0), -8 * k); rot("head", (1, 0, 0), 14 * k)
        rot("jaw", (1, 0, 0), 14 * k)
        rot("spine", (0, 1, 0), 5 * k)
        PB["root"].location = (0, 0, 0.18 * k)  # rock back
        wings(18 * k + 22, 14 * k, 28 - 16 * k, 30)
        tail_wave(0.25, 8 * k)
        ember = 0.55 + 0.8 * k
    elif anim == "death":
        k = [0.0, 0.12, 0.3, 0.5, 0.68, 0.84, 0.95, 1.0][i]
        st = math.sin(min(1, k * 3) * math.pi) * (1 - k)
        PB["root"].location = (0, -1.05 * k, 0)                # sink
        rot("root", (0, 1, 0), 58 * k ** 1.3)                    # roll onto the side
        rot("neck1", (1, 0, 0), 18 * k - 10 * st); rot("neck2", (1, 0, 0), 14 * k); rot("neck3", (1, 0, 0), 10 * k)
        rot("neck2", (0, 0, 1), 22 * k); rot("head", (1, 0, 0), 12 * k); rot("jaw", (1, 0, 0), 12 * k)
        for s in ("L", "R"):
            rot(f"fl_up.{s}", (1, 0, 0), -30 * k); rot(f"fl_lo.{s}", (1, 0, 0), 60 * k)
            rot(f"hl_up.{s}", (1, 0, 0), 25 * k); rot(f"hl_lo.{s}", (1, 0, 0), -55 * k)
        wings(22 + 30 * st - 40 * k, 20 * k, 30 - 25 * k, 30 * (1 - k))
        tail_wave(0.1, 10 * (1 - k))
        for t in range(1, 7):
            rot(f"tail{t}", (0, 0, 1), 6 * k)
        ember = 0.55 * (1 - k) + 0.05
        mouth = 0
    EMBER.outputs[0].default_value = ember
    MOUTH_MAT.inputs["Emission Strength"].default_value = mouth
    flame.hide_render = flame_k <= 0.01
    flame.scale = (0.35 + 0.65 * flame_k, max(0.05, flame_k), 0.35 + 0.65 * flame_k)
    FNOISE.inputs["W"].default_value = i * 0.37
    bpy.context.view_layer.update()

def face(f):
    rig.rotation_euler = (0, 0, math.radians(FACINGS[f]))

def jobs():
    out = []
    for f in FACINGS:
        for a, n in ANIMS.items():
            for i in range(n):
                out.append((a, f, i))
    return out

os.makedirs(FRAMES, exist_ok=True)
if MODE == "test":
    target_png = argv[1]
    sc.cycles.samples = 12; sc.cycles.use_denoising = True
    sc.render.resolution_percentage = 50
    tests = [("idle", "s", 0), ("idle", "e", 0), ("idle", "n", 0), ("walk", "e", 2), ("breath", "s", 5), ("breath", "e", 5), ("hit", "e", 0), ("death", "e", 7)]
    tmp = []
    for a, f, i in tests:
        pose(a, i); face(f)
        p = f"/tmp/wyrm_test_{a}_{f}_{i}.png"; sc.render.filepath = p
        bpy.ops.render.render(write_still=True); tmp.append(p)
    print("TESTS", tmp)
else:
    k, nw = int(argv[1]), int(argv[2])
    sc.cycles.samples = 40; sc.cycles.use_denoising = True
    for j, (a, f, i) in enumerate(jobs()):
        if j % nw != k:
            continue
        p = os.path.join(FRAMES, f"{a}_{f}_{i}.png")
        if os.path.exists(p):
            continue
        pose(a, i); face(f)
        sc.render.filepath = p + ".tmp.png"
        bpy.ops.render.render(write_still=True)
        os.replace(p + ".tmp.png", p)
        print("DONE", p, flush=True)
