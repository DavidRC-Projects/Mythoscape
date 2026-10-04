"""castle.py - build, animate, render and export the new Stonehaven Castle Keep.

    ~/bin/blender -b -P castle.py -- [--out /workspace/castle] [--no-render] [--fast]

Outputs (under --out):
  models/realm_kings_castle.blend|.glb   (gate parts separate + keyframed 'gate_open', frames 1-12)
  sprites/2x/*.png                         (80 px per tile; 1x made by tools/postprocess.py)
  concepts/hero_34.png, concepts/hero_gate.png
  json/render_info.json                    (camera, crops, anchors, frame transforms, tris)
"""
import bpy
import bmesh
import json
import math
import os
import sys
from mathutils import Matrix, Vector, Euler

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import sky_geo as cg  # noqa: E402
from sky_geo import T, M  # noqa: E402

ARGS = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
OUT = ARGS[ARGS.index("--out") + 1] if "--out" in ARGS else "/workspace/castle_realm/phase4/work/sky"
RENDER = "--no-render" not in ARGS
FAST = "--fast" in ARGS
PPT2 = 80                       # sprite px per tile at 2x
PPM2 = PPT2 / T
EL = math.radians(32.0)
COS, SIN = math.cos(EL), math.sin(EL)
S = Matrix.Diagonal((1.0, 1.0 / SIN, 1.0, 1.0))      # tile-locked stretch (ground rows = 40 px)

# ------------------------------------------------------------------ animation table
BRIDGE_DEG = [-88, -84, -74, -58, -38, -16, 0, 0, 0, 0, 0, 0]
PORT_Z = [0, 0, 0, 0, 0, 0, 0] + [round(cg.PORT_RISE * t, 3) for t in (0.18, 0.42, 0.67, 0.87, 1.0)]
DUR_MS = [220, 80, 80, 80, 80, 80, 140, 90, 90, 90, 90, 200]
NF = len(BRIDGE_DEG)

k = cg.PartKit("realm_sky_anchor", cg.PAL, seed=44, title="Sky-Anchor Citadel (Castle Realm #4)",
               emissive=cg.EMISSIVE, ground="#8a8a86")
info = cg.build(k)
GX, GFACE = info["gate_centre_x_m"], info["gate_face_y_m"]
HINGE = Vector((GX, GFACE, 0.1))
PORT0 = Vector((GX, -cg.PORT_LY * T, 0.0))
PULL = [Vector((GX + sx * cg.PULLEY[0], GFACE + cg.PULLEY[1], cg.PULLEY[2])) for sx in (-1, 1)]
TIP_LOCAL = [Vector((sx * 1.5, -cg.BRIDGE_L + 0.12, 0.05)) for sx in (-1, 1)]

# reference figure (1.8 m) for scale renders
k.figure((0, 0, 0))
k.palette.update({"ref_legs": "#3d4a63", "ref_shirt": "#8f2f2a", "ref_skin": "#d2a47c",
                  "ref_hair": "#4a3526", "ref_ground": "#6f7a4a", "hero_grass": "#5f7a3e",
                  "hero_plaza": "#8f8b82"})
parts = k.all_parts()
mats = k._materials()

scene = bpy.context.scene
scene.name = "MAIN"
col_castle = bpy.data.collections.new("CASTLE")
col_static = bpy.data.collections.new("CASTLE_STATIC")
col_gate = bpy.data.collections.new("CASTLE_GATE")
col_coll = bpy.data.collections.new("COLLISION")
scene.collection.children.link(col_castle)
col_castle.children.link(col_static)
col_castle.children.link(col_gate)
scene.collection.children.link(col_coll)
col_fx = bpy.data.collections.new("WATERFALL_FRAMES")
col_castle.children.link(col_fx)

OBJ = {}
tri = {}
for name, (verts, faces) in parts.items():
    if not faces:
        continue
    coll = col_gate if name in ("bridge", "portcullis", "chain_l", "chain_r") else col_static
    if name.startswith("wfall_") and name != "wfall_0":
        coll = col_fx
    ob = k._make_object("castle_" + name, verts, faces, mats, coll)
    OBJ[name] = ob
    tri[name] = len(ob.data.polygons)
print("[castle] tris per part:", tri, "total", sum(tri.values()))


def gate_pose(f):
    """World matrices of the gate parts for animation frame f (0 = closed, NF-1 = open)."""
    a = math.radians(BRIDGE_DEG[f])
    mb = Matrix.Translation(HINGE) @ Matrix.Rotation(a, 4, "X")
    mp = Matrix.Translation(PORT0 + Vector((0, 0, PORT_Z[f])))
    out = {"bridge": mb, "portcullis": mp}
    for i, nm in enumerate(("chain_l", "chain_r")):
        tip = mb @ TIP_LOCAL[i]
        d = (PULL[i] - tip).normalized()
        q = Vector((0, 0, 1)).rotation_difference(d)
        out[nm] = Matrix.Translation(tip) @ q.to_matrix().to_4x4()
    return out


def set_pose(f):
    for nm, m in gate_pose(f).items():
        ob = OBJ[nm]
        ob.rotation_mode = "QUATERNION"
        ob.matrix_world = m


set_pose(NF - 1)

# ------------------------------------------------------------------ colliders / triggers (3D use)
def colbox(name, lx0, ly0, lx1, ly1, z0=-1.0, z1=7.0, role="solid"):
    a, b = M(lx0, ly0), M(lx1, ly1)
    c = ((a[0] + b[0]) / 2, (a[1] + b[1]) / 2, (z0 + z1) / 2)
    bpy.ops.mesh.primitive_cube_add(size=1.0, location=c)
    o = bpy.context.active_object
    o.name = name
    o.scale = (abs(b[0] - a[0]), abs(b[1] - a[1]), z1 - z0)
    o.display_type = "WIRE"
    o.hide_render = True
    try:
        bpy.ops.rigidbody.object_add(type="PASSIVE")
        o.rigid_body.collision_shape = "BOX"
    except Exception as exc:
        print("[castle] rigid body skipped", exc)
    o["prop_role"] = role
    for cc in list(o.users_collection):
        cc.objects.unlink(o)
    col_coll.objects.link(o)


for cb in cg.COLBOXES:
    colbox(*cb[:7], **({"role": cb[7]} if len(cb) > 7 else {}))

# ------------------------------------------------------------------ sprite projection bounds
def uv(p):
    return p.x, p.y + p.z * COS


def all_points():
    pts = []
    for nm, ob in OBJ.items():
        if nm in ("bridge", "portcullis", "chain_l", "chain_r"):
            continue
        pts += [ob.matrix_world @ v.co for v in ob.data.vertices]
    for f in range(NF):
        for nm, m in gate_pose(f).items():
            ob = OBJ[nm]
            pts += [m @ v.co for i, v in enumerate(ob.data.vertices) if i % 3 == 0]
    return pts


pts = all_points()
us = [uv(p)[0] for p in pts]
vs = [uv(p)[1] for p in pts]
L_T = math.floor(min(us) / T - 0.25)
R_T = math.ceil(max(us) / T + 0.25)
TOP_T = math.ceil(max(vs) / T + 0.25)
BOT_T = math.floor(min(vs) / T - 0.25)
U0, U1, V0, V1 = L_T * T, R_T * T, BOT_T * T, TOP_T * T
W2, H2 = int(round((R_T - L_T) * PPT2)), int(round((TOP_T - BOT_T) * PPT2))
ORIGIN2 = (-L_T * PPT2, TOP_T * PPT2)          # px of footprint NW corner (tile 100,31) at 2x
print("[castle] sprite tiles L,R,TOP,BOT", L_T, R_T, TOP_T, BOT_T, "size2x", W2, H2)


def px2(p):
    u, v = uv(p)
    return (u - U0) * PPM2, (V1 - v) * PPM2


# ------------------------------------------------------------------ SPRITE scene
def make_world(sc, col=(0.34, 0.32, 0.28), strength=1.0):
    w = bpy.data.worlds.new("W_" + sc.name)
    w.use_nodes = True
    bg = w.node_tree.nodes["Background"]
    bg.inputs["Color"].default_value = (*col, 1)
    bg.inputs["Strength"].default_value = strength
    sc.world = w


def setup_render(sc, w, h, transparent=True):
    sc.render.engine = "BLENDER_EEVEE_NEXT"
    sc.render.resolution_x, sc.render.resolution_y = w, h
    sc.render.resolution_percentage = 100
    sc.render.film_transparent = transparent
    sc.render.image_settings.file_format = "PNG"
    sc.render.image_settings.color_mode = "RGBA"
    sc.view_settings.view_transform = "Standard"
    sc.eevee.taa_render_samples = 16 if FAST else 24
    try:
        sc.eevee.use_shadows = True
        sc.eevee.shadow_resolution_scale = 1.0
    except Exception:
        pass


def add_sun(sc):
    sun = bpy.data.lights.new("Sun_" + sc.name, "SUN")
    sun.energy = 3.2
    sun.color = (1.0, 0.95, 0.86)
    sun.angle = math.radians(3)
    so = bpy.data.objects.new("Sun_" + sc.name, sun)
    so.rotation_euler = Euler((math.radians(40), math.radians(15), math.radians(-30)), "XYZ")
    sc.collection.objects.link(so)
    return so


def ortho_cam(sc, u0, u1, v0, v1, name="Cam"):
    cam = bpy.data.cameras.new(name)
    cam.type = "ORTHO"
    cam.ortho_scale = max(u1 - u0, v1 - v0)
    cam.clip_start = 1.0
    cam.clip_end = 600
    co = bpy.data.objects.new(name, cam)
    up = Vector((0, SIN, COS))
    fwd = Vector((0, COS, -SIN))
    uc, vc = (u0 + u1) / 2, (v0 + v1) / 2
    # the stretched point P'=(u, ?, ?) projects to v = P'.up; place the camera on the view axis
    co.location = Vector((uc, 0, 0)) + up * vc - fwd * 250.0
    co.rotation_euler = Euler((math.radians(58), 0, 0), "XYZ")
    sc.collection.objects.link(co)
    sc.camera = co
    return co


spr = bpy.data.scenes.new("SPRITE")
make_world(spr)
setup_render(spr, W2, H2)
add_sun(spr)
ortho_cam(spr, U0, U1, V0, V1)
spr_col = bpy.data.collections.new("SPRITE_COPIES")
spr.collection.children.link(spr_col)


def baked(src_ob, m, name):
    me = src_ob.data.copy()
    me.transform(S @ m)
    o = bpy.data.objects.new(name, me)
    spr_col.objects.link(o)
    return o


STATIC = {nm: baked(OBJ[nm], OBJ[nm].matrix_world, "S_" + nm)
          for nm in OBJ if nm not in ("bridge", "portcullis", "chain_l", "chain_r") and not nm.startswith("wfall_")}


def cut_copy(src_ob, z=1.6, name="S_cut"):
    me = src_ob.data.copy()
    bm = bmesh.new()
    bm.from_mesh(me)
    geom = bm.verts[:] + bm.edges[:] + bm.faces[:]
    bmesh.ops.bisect_plane(bm, geom=geom, dist=1e-4, plane_co=(0, 0, z), plane_no=(0, 0, 1), clear_outer=True)
    edges = [e for e in bm.edges if e.is_boundary and all(abs(v.co.z - z) < 1e-3 for v in e.verts)]
    res = bmesh.ops.holes_fill(bm, edges=edges, sides=0)
    fill_idx = 0
    for i, mt in enumerate(me.materials):
        if mt and mt.name.startswith("ctrim"):
            fill_idx = i
            break
    for f in res.get("faces", []):
        f.material_index = fill_idx
    bm.to_mesh(me)
    bm.free()
    me.transform(S)
    o = bpy.data.objects.new(name, me)
    spr_col.objects.link(o)
    return o


CUT = {}      # no cutaway: the keep is airborne and its interiors are separate planes
for o in CUT.values():
    o.visible_camera = False

GATE_COPIES = []


def show(vis, hold=(), extra=()):
    for nm, o in list(STATIC.items()) + [("cut_" + n, o) for n, o in CUT.items()] + list(extra):
        o.visible_camera = (nm in vis) or (nm in hold)     # holdout only works on camera-visible objects
        o.is_holdout = nm in hold
        if nm.startswith("cut_") and nm not in vis:
            o.visible_shadow = False
        elif nm.startswith("cut_"):
            o.visible_shadow = True
    for nm in ("body", "front", "posts", "court", "sort_24"):
        if nm in STATIC:
            STATIC[nm].visible_shadow = not any(n.startswith("cut_") for n in vis)


def render(path, border=None):
    spr.eevee.taa_render_samples = 8 if border else (16 if FAST else 24)     # cropped anim frames: 8 samples
    spr.render.use_border = border is not None
    spr.render.use_crop_to_border = border is not None
    if border:
        x0, y0, x1, y1 = border
        spr.render.border_min_x, spr.render.border_max_x = x0 / W2, x1 / W2
        spr.render.border_min_y, spr.render.border_max_y = 1 - y1 / H2, 1 - y0 / H2
    spr.render.filepath = path
    os.makedirs(os.path.dirname(path), exist_ok=True)
    bpy.ops.render.render(write_still=True, scene=spr.name)
    print("[castle] wrote", path)


SP = os.path.join(OUT, "sprites", "2x")
render_info = {"ppt_2x": PPT2, "size_2x": [W2, H2], "origin_2x": list(ORIGIN2),
               "tiles": {"left": L_T, "right": R_T, "top": TOP_T, "bottom": BOT_T},
               "tris": tri, "tris_total": sum(tri.values())}

# gate crop rect (union over frames), even-aligned
gp = []
for f in range(NF):
    for nm, m in gate_pose(f).items():
        gp += [px2(m @ v.co) for v in OBJ[nm].data.vertices]
gx0 = max(0, int(min(p[0] for p in gp)) - 12) // 2 * 2
gy0 = max(0, int(min(p[1] for p in gp)) - 12) // 2 * 2
gx1 = min(W2, (int(max(p[0] for p in gp)) + 14) // 2 * 2)
gy1 = min(H2, (int(max(p[1] for p in gp)) + 14) // 2 * 2)
render_info["gate_crop_2x"] = [gx0, gy0, gx1, gy1]
frames = []
for f in range(NF):
    pose = gate_pose(f)
    frames.append({"frame": f, "bridge_deg": BRIDGE_DEG[f], "portcullis_z_m": PORT_Z[f], "ms": DUR_MS[f],
                   "matrices": {nm: [list(r) for r in m] for nm, m in pose.items()}})
render_info["frames"] = frames
render_info["hinge_m"] = list(HINGE)
render_info["portcullis_rest_m"] = list(PORT0)
render_info["pulleys_m"] = [list(p) for p in PULL]

if "--preview" in ARGS:
    wf0 = baked(OBJ["wfall_0"], OBJ["wfall_0"].matrix_world, "WFP")
    pose = gate_pose(NF - 1); ex = [("gate", baked(OBJ[nm], m, "GP_" + nm)) for nm, m in pose.items()] + [("wf", wf0)]
    show({"ground", "water", "body", "court", "posts", "front", "gate", "wf", "sort_24"}, extra=ex)
    spr.render.resolution_percentage = 40
    spr.eevee.taa_render_samples = 8
    spr.render.filepath = "/tmp/sky_prev.png"
    bpy.ops.render.render(write_still=True, scene=spr.name)
    sys.exit(0)
if RENDER:
    show({"ground", "water"})
    render(os.path.join(SP, "sky_ground.png"))
    SORTS = sorted([n for n in STATIC if n.startswith("sort_")])
    show({"body", "court"}, hold={"ground", "water", "posts"} | set(SORTS))
    render(os.path.join(SP, "sky_back.png"))
    show({"posts"})
    render(os.path.join(SP, "sky_posts.png"))
    for sn in SORTS:       # y-sorted building layers (drawn in the entity pass at their sort row)
        show({sn}, hold={"body", "court"} | set(x for x in SORTS if int(x[5:]) > int(sn[5:])))
        render(os.path.join(SP, "sky_%s.png" % sn))
    render_info["sort_layers"] = [{"name": sn, "file": "sky_%s.png" % sn, "sort_row_local": int(sn[5:])} for sn in SORTS]
    show({"front"}, hold={"body"} | set(SORTS))
    render(os.path.join(SP, "sky_front.png"))
    # gate frames
    for f in range(NF):
        for o in GATE_COPIES:
            bpy.data.objects.remove(o, do_unlink=True)
        GATE_COPIES.clear()
        pose = gate_pose(f)
        extra = []
        for nm, m in pose.items():
            o = baked(OBJ[nm], m, "G_" + nm)
            GATE_COPIES.append(o)
            extra.append(("gate", o))
        show({"gate"}, hold={"body", "court", "ground", "water", "posts", "front"} | set(SORTS), extra=extra)
        render(os.path.join(SP, "gate", f"gate_{f:02d}.png"), border=(gx0, gy0, gx1, gy1))
        if f in (0, NF - 1):     # full reference renders (everything visible) for checking the layering
            wf0 = baked(OBJ["wfall_0"], OBJ["wfall_0"].matrix_world, "WF0"); GATE_COPIES.append(wf0); extra.append(("wf", wf0))
            show({"ground", "water", "body", "court", "posts", "front", "gate", "wf"} | set(SORTS), extra=extra)
            render(os.path.join(OUT, "renders", f"full_direct_{'closed' if f == 0 else 'open'}_2x.png"))
    for o in GATE_COPIES:
        bpy.data.objects.remove(o, do_unlink=True)
    GATE_COPIES.clear()
    # waterfall frames (cropped; blitted right after the sort_24 layer)
    fp = [px2(OBJ["wfall_%d" % f].matrix_world @ v.co) for f in range(cg.NWF) for v in OBJ["wfall_%d" % f].data.vertices]
    fx0 = max(0, int(min(p[0] for p in fp)) - 10) // 2 * 2
    fy0 = max(0, int(min(p[1] for p in fp)) - 10) // 2 * 2
    fx1 = min(W2, (int(max(p[0] for p in fp)) + 12) // 2 * 2)
    fy1 = min(H2, (int(max(p[1] for p in fp)) + 12) // 2 * 2)
    render_info["waterfall_crop_2x"] = [fx0, fy0, fx1, fy1]
    render_info["waterfall_frames"] = [{"frame": f, "ms": 110} for f in range(cg.NWF)]
    for f in range(cg.NWF):
        o = baked(OBJ["wfall_%d" % f], OBJ["wfall_%d" % f].matrix_world, "WF")
        show({"wf"}, hold={"body", "court", "posts", "front"} | set(SORTS), extra=[("wf", o)])
        render(os.path.join(SP, "waterfall", f"waterfall_{f:02d}.png"), border=(fx0, fy0, fx1, fy1))
        bpy.data.objects.remove(o, do_unlink=True)

# ------------------------------------------------------------------ player figure sprite (same camera)
fig_v, fig_f = k._ref[0]
fig_ob = k._make_object("REF_player_1p8m", fig_v, fig_f, mats, spr_col)
for o in STATIC.values():
    o.hide_render = True
for o in CUT.values():
    o.hide_render = True
if RENDER:
    fs = bpy.data.scenes.new("FIG")
    make_world(fs)
    setup_render(fs, int(1.4 * PPM2), int(2.4 * PPM2))
    add_sun(fs)
    fc = bpy.data.collections.new("FIGC")
    fs.collection.children.link(fc)
    me = fig_ob.data.copy()
    me.transform(S)
    fo = bpy.data.objects.new("FIGCOPY", me)
    fc.objects.link(fo)
    ortho_cam(fs, -0.7, 0.7, -0.3, 2.1, name="FigCam")
    fs.render.filepath = os.path.join(SP, "player_ref_1p8m.png")
    bpy.ops.render.render(write_still=True, scene=fs.name)
    render_info["player_ref_2x"] = {"size": [int(1.4 * PPM2), int(2.4 * PPM2)],
                                    "feet_px": [0.7 * PPM2, 2.1 * PPM2]}
bpy.data.objects.remove(fig_ob, do_unlink=True)

# ------------------------------------------------------------------ HERO scenes (true 3D, unstretched)
def hero(path, az, el, target, dist, lens=35, res=(1920, 1200), fig_at=None):
    hs = bpy.data.scenes.new("HERO")
    hs.collection.children.link(col_castle)
    make_world(hs, (0.62, 0.70, 0.80), 0.95)
    setup_render(hs, *res, transparent=False)
    hs.eevee.taa_render_samples = 16 if FAST else 48
    add_sun(hs)
    hc = bpy.data.collections.new("HERO_EXTRA")
    hs.collection.children.link(hc)
    # ground: plaza south + grass elsewhere, with a hole for the moat
    def quad(name, x0, y0, x1, y1, z, mat):
        me = bpy.data.meshes.new(name)
        me.from_pydata([(x0, y0, z), (x1, y0, z), (x1, y1, z), (x0, y1, z)], [], [(0, 1, 2, 3)])
        me.materials.append(mats[mat])
        o = bpy.data.objects.new(name, me)
        hc.objects.link(o)
    W = cg.NX * T
    quad("g_n", -60, 0, W + 60, 60, -0.01, "hero_grass")
    quad("g_w", -60, -W, 0, 0, -0.01, "hero_grass")
    quad("g_e", W, -W, W + 60, 0, -0.01, "hero_grass")
    quad("g_s", -60, -W - 60, W + 60, -W, -0.01, "hero_plaza")
    if fig_at:
        fv, ff = k._ref[0]
        fo = k._make_object("HERO_fig", fv, ff, mats, hc)
        fo.location = fig_at
    cam = bpy.data.cameras.new("HeroCam")
    cam.lens = lens
    cam.clip_end = 800
    co = bpy.data.objects.new("HeroCam", cam)
    azr, elr = math.radians(az), math.radians(el)
    tgt = Vector(target)
    co.location = tgt + dist * Vector((math.sin(azr) * math.cos(elr), -math.cos(azr) * math.cos(elr), math.sin(elr)))
    co.rotation_euler = (tgt - co.location).to_track_quat("-Z", "Y").to_euler()
    hs.collection.objects.link(co)
    hs.camera = co
    hs.render.filepath = path
    bpy.ops.render.render(write_still=True, scene=hs.name)
    print("[castle] wrote", path)
    return hs


if RENDER:
    C = cg.NX / 2 * T
    hero(os.path.join(OUT, "concepts", "hero_34.png"), 35, 22, (C, -C, 12.0), 160, lens=35,
         fig_at=(GX + 3.0, -(cg.NY + 0.4) * T, 0.06))
    hero(os.path.join(OUT, "concepts", "hero_lift.png"), -25, 14, (24 * T, -24 * T, 10.0), 70, lens=35,
         res=(1600, 1100), fig_at=(24.3 * T, -25.6 * T, 0.02))

# ------------------------------------------------------------------ keyframes + save + export
for sc in list(bpy.data.scenes):
    if sc.name != "MAIN":
        bpy.data.scenes.remove(sc)
bpy.context.window_manager  # noqa
scene = bpy.data.scenes["MAIN"]
scene.frame_start, scene.frame_end = 1, NF
scene.render.fps = 10
for f in range(NF):
    pose = gate_pose(f)
    for nm, m in pose.items():
        ob = OBJ[nm]
        ob.rotation_mode = "QUATERNION"
        loc, rot, _ = m.decompose()
        ob.location = loc
        ob.rotation_quaternion = rot
        ob.keyframe_insert("location", frame=f + 1)
        ob.keyframe_insert("rotation_quaternion", frame=f + 1)
for nm in ("bridge", "portcullis", "chain_l", "chain_r"):
    ad = OBJ[nm].animation_data
    if ad and ad.action:
        ad.action.name = "gate_open_" + nm
        for fc in ad.action.fcurves:
            for kp in fc.keyframe_points:
                kp.interpolation = "LINEAR"
scene.frame_set(1)
# pivots documented as custom props
OBJ["bridge"]["pivot"] = "hinge line along X at the gate threshold; rot X -88 (closed) .. 0 (open)"
OBJ["portcullis"]["pivot"] = "bottom centre; slides +Z 0 .. %.2f m" % cg.PORT_RISE
for nm in ("chain_l", "chain_r"):
    OBJ[nm]["pivot"] = "bridge tip ring; local +Z aims at the pulley slot (excess passes into the wall)"

md = os.path.join(OUT, "models")
os.makedirs(md, exist_ok=True)
bpy.ops.wm.save_as_mainfile(filepath=os.path.join(md, "realm_sky_anchor.blend"))
vl = bpy.context.view_layer
vl.active_layer_collection = vl.layer_collection.children["CASTLE"]
bpy.ops.export_scene.gltf(filepath=os.path.join(md, "realm_sky_anchor.glb"), export_format="GLB",
                          use_active_collection=True, use_active_collection_with_nested=True,
                          export_apply=True, export_texcoords=False, export_normals=True,
                          export_materials="EXPORT", export_cameras=False, export_lights=False,
                          export_yup=True, export_animations=True, export_frame_range=True,
                          export_animation_mode="ACTIVE_ACTIONS")
os.makedirs(os.path.join(OUT, "json"), exist_ok=True)
with open(os.path.join(OUT, "json", "render_info.json"), "w") as fh:
    json.dump(render_info, fh, indent=1)
print("[castle] done")
