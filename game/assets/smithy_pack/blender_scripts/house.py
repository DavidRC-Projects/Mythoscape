"""house.py - build + render + export ONE bigger Mythoscape house.

    ~/bin/blender -b -P house.py -- --key general_store [--out /workspace/buildings] [--fast]

Outputs: models/<key>.blend|.glb, sprites/2x/<key>/{ground,body,cutaway}.png, concepts/hero/<key>.png,
json/render/<key>.json (camera, 2x origin, tris).  1x sprites + metadata: tools/houses_post.py.
Camera = castle pack: ortho, az 0 (looking north), el 32, scene Y pre-stretched by 1/sin32 so ground
rows are tile-locked (40 px per tile at 1x, 80 at 2x).
"""
import bpy, bmesh, json, math, os, sys
from mathutils import Matrix, Vector, Euler
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
ARGS = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
KEY = ARGS[ARGS.index("--key") + 1]
OUT = ARGS[ARGS.index("--out") + 1] if "--out" in ARGS else "/workspace/buildings/smithy/work"
FAST = "--fast" in ARGS
sys.argv = sys.argv[:1]          # keep osrs_kit.parse_args quiet
import houses_geo as hg  # noqa: E402
import smithy_design as hd  # noqa: E402
T = hg.T
PPT2 = 80
PPM2 = PPT2 / T
EL = math.radians(32.0)
COS, SIN = math.cos(EL), math.sin(EL)
ZEX = 1.4                     # sprite-only vertical exaggeration (matches the old template: door ~93 px at TILE 40)
S = Matrix.Diagonal((1.0, 1.0 / SIN, ZEX, 1.0))

bid, name, X0, Y0, W, D, DX, FLOOR = hd.SPECS[KEY]
k = hg.HK(KEY, hg.PAL, seed=abs(hash(KEY)) % 1000, title=name, emissive=hg.EMISSIVE)
meta = hd.BUILD[KEY](k, W, D, DX)
k.figure((0, 0, 0))
k.palette.update({"ref_legs": "#3d4a63", "ref_shirt": "#8f2f2a", "ref_skin": "#d2a47c", "ref_hair": "#4a3526",
                  "ref_ground": "#6f7a4a", "hero_grass": "#5f7a3e"})
parts = k.all_parts()
mats = k._materials()
scene = bpy.context.scene
scene.name = "MAIN"
col = bpy.data.collections.new(KEY.upper())
scene.collection.children.link(col)
OBJ, tri = {}, {}
for pn, (verts, faces) in parts.items():
    if faces:
        OBJ[pn] = k._make_object(f"{KEY}_{pn}", verts, faces, mats, col)
        tri[pn] = len(OBJ[pn].data.polygons)
print(f"[{KEY}] tris", tri)


def uv(p):
    return p.x, p.y + p.z * COS


pts = [Matrix.Diagonal((1, 1, ZEX, 1)) @ (o.matrix_world @ v.co) for o in OBJ.values() for v in o.data.vertices]   # unstretched: uv() = projection of the stretched point
us = [uv(p)[0] for p in pts]; vs = [uv(p)[1] for p in pts]
L_T = math.floor(min(us) / T - 0.25); R_T = math.ceil(max(us) / T + 0.25)
TOP_T = math.ceil(max(vs) / T + 0.25); BOT_T = math.floor(min(vs) / T - 0.25)
U0, U1, V0, V1 = L_T * T, R_T * T, BOT_T * T, TOP_T * T
W2, H2 = int(round((R_T - L_T) * PPT2)), int(round((TOP_T - BOT_T) * PPT2))
ORIGIN2 = (-L_T * PPT2, TOP_T * PPT2)


def make_world(sc, c=(0.34, 0.32, 0.28), strength=1.0):
    w = bpy.data.worlds.new("W_" + sc.name); w.use_nodes = True
    bg = w.node_tree.nodes["Background"]; bg.inputs["Color"].default_value = (*c, 1); bg.inputs["Strength"].default_value = strength
    sc.world = w


def setup_render(sc, w, h, transparent=True, samples=None):
    sc.render.engine = "BLENDER_EEVEE_NEXT"
    sc.render.resolution_x, sc.render.resolution_y = w, h
    sc.render.resolution_percentage = 100
    sc.render.film_transparent = transparent
    sc.render.image_settings.file_format = "PNG"; sc.render.image_settings.color_mode = "RGBA"
    sc.view_settings.view_transform = "Standard"
    sc.eevee.taa_render_samples = samples or (8 if FAST else 20)


def add_sun(sc):
    sun = bpy.data.lights.new("Sun_" + sc.name, "SUN"); sun.energy = 3.2; sun.color = (1.0, 0.95, 0.86)
    sun.angle = math.radians(3)
    so = bpy.data.objects.new("Sun_" + sc.name, sun)
    so.rotation_euler = Euler((math.radians(40), math.radians(15), math.radians(-30)), "XYZ")
    sc.collection.objects.link(so)


def ortho_cam(sc):
    cam = bpy.data.cameras.new("Cam"); cam.type = "ORTHO"; cam.ortho_scale = max(U1 - U0, V1 - V0)
    cam.clip_start, cam.clip_end = 1.0, 600
    co = bpy.data.objects.new("Cam", cam)
    up = Vector((0, SIN, COS)); fwd = Vector((0, COS, -SIN))
    co.location = Vector(((U0 + U1) / 2, 0, 0)) + up * ((V0 + V1) / 2) - fwd * 250.0
    co.rotation_euler = Euler((math.radians(58), 0, 0), "XYZ")
    sc.collection.objects.link(co); sc.camera = co


spr = bpy.data.scenes.new("SPRITE")
make_world(spr); setup_render(spr, W2, H2); add_sun(spr); ortho_cam(spr)
sc_col = bpy.data.collections.new("SPR"); spr.collection.children.link(sc_col)
ST = {}
for pn, o in OBJ.items():
    me = o.data.copy(); me.transform(S)
    ST[pn] = bpy.data.objects.new("S_" + pn, me); sc_col.objects.link(ST[pn])
# cutaway: body cut at 1.6 m
me = OBJ["body"].data.copy()
bm = bmesh.new(); bm.from_mesh(me)
bmesh.ops.bisect_plane(bm, geom=bm.verts[:] + bm.edges[:] + bm.faces[:], dist=1e-4, plane_co=(0, 0, 1.6),
                       plane_no=(0, 0, 1), clear_outer=True)
edges = [e for e in bm.edges if e.is_boundary and all(abs(v.co.z - 1.6) < 1e-3 for v in e.verts)]
bmesh.ops.holes_fill(bm, edges=edges, sides=0)
bm.to_mesh(me); bm.free(); me.transform(S)
ST["cut"] = bpy.data.objects.new("S_cut", me); sc_col.objects.link(ST["cut"])
for pn in ST:
    if pn.startswith("smoke"):
        ST[pn].visible_shadow = False
FORGE = bpy.data.lights.new("Forge", "POINT"); FORGE.energy = 900.0; FORGE.color = (1.0, 0.5, 0.18)
FORGE.shadow_soft_size = 0.4
fo_ = bpy.data.objects.new("Forge", FORGE)
fo_.location = (13.0 * T, -12.6 * T / SIN, 1.9 * ZEX)
sc_col.objects.link(fo_)


def show(vis, hold=()):
    for pn, o in ST.items():
        o.visible_camera = pn in vis or pn in hold
        o.is_holdout = pn in hold
    ST["cut"].visible_shadow = "cut" in vis
    ST["body"].visible_shadow = "cut" not in vis


def render(path):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    spr.render.filepath = path
    bpy.ops.render.render(write_still=True, scene=spr.name)


SP = os.path.join(OUT, "sprites", "2x", KEY)
show({"ground"}); render(os.path.join(SP, "ground.png"))
show({"body"}); render(os.path.join(SP, "body.png"))
show({"cut"}); render(os.path.join(SP, "cutaway.png"))
show({"ground", "body"}); render(os.path.join(OUT, "renders", KEY + "_full_2x.png"))
# forge-glow frames (emission + forge light pulse) and smoke frames
EMI = {m: mats[m].node_tree.nodes["Principled BSDF"].inputs["Emission Strength"] for m in ("ember", "hot", "fire", "window")}
BASE = {m: v.default_value for m, v in EMI.items()}
for i, f in enumerate((0.55, 1.0, 1.5)):
    for m, v in EMI.items():
        v.default_value = BASE[m] * (f if m != "window" else (0.85 + 0.15 * f))
    FORGE.energy = 900.0 * f
    show({"body"}); render(os.path.join(SP, f"body_glow{i}.png"))
for m, v in EMI.items():
    v.default_value = BASE[m]
FORGE.energy = 900.0
for i in range(4):
    show({f"smoke{i}"}, hold=("body",)); render(os.path.join(SP, f"smoke{i}.png"))
for pn, o in OBJ.items():
    if pn.startswith("smoke") and pn != "smoke1":
        o.hide_render = True
    if pn.startswith("smoke"):
        o.visible_shadow = False

# hero 3/4 (true 3D)
hs = bpy.data.scenes.new("HERO")
hs.collection.children.link(col)
make_world(hs, (0.55, 0.62, 0.72), 0.9); setup_render(hs, 1200, 900, transparent=False, samples=8 if FAST else 24); add_sun(hs)
hc = bpy.data.collections.new("HX"); hs.collection.children.link(hc)
gm = bpy.data.meshes.new("g"); gw = W * T
gm.from_pydata([(-30, 30, -0.01), (gw + 30, 30, -0.01), (gw + 30, -D * T - 30, -0.01), (-30, -D * T - 30, -0.01)], [], [(0, 1, 2, 3)])
gm.materials.append(mats["hero_grass"]); hc.objects.link(bpy.data.objects.new("g", gm))
fv, ff = k._ref[0]
fo = k._make_object("HERO_fig", fv, ff, mats, hc); fo.location = ((DX + 1.6) * T, -(D - 0.3) * T, 0.0)
cam = bpy.data.cameras.new("HC"); cam.lens = 35; cam.clip_end = 800
co = bpy.data.objects.new("HC", cam)
tgt = Vector((W * T / 2, -D * T / 2, 3.0)); dist = max(W, D) * T * 1.9
az, el = math.radians(30), math.radians(28)
co.location = tgt + dist * Vector((math.sin(az) * math.cos(el), -math.cos(az) * math.cos(el), math.sin(el)))
co.rotation_euler = (tgt - co.location).to_track_quat("-Z", "Y").to_euler()
hs.collection.objects.link(co); hs.camera = co
hs.render.filepath = os.path.join(OUT, "concepts", "hero", KEY + ".png")
bpy.ops.render.render(write_still=True, scene=hs.name)

for sc in list(bpy.data.scenes):
    if sc.name != "MAIN":
        bpy.data.scenes.remove(sc)
for o in list(bpy.data.objects):
    if o.name.startswith(("S_", "HERO_", "g")) and o.name not in [x.name for x in col.objects]:
        bpy.data.objects.remove(o, do_unlink=True)
md = os.path.join(OUT, "models"); os.makedirs(md, exist_ok=True)
bpy.ops.wm.save_as_mainfile(filepath=os.path.join(md, KEY + ".blend"))
vl = bpy.context.view_layer
vl.active_layer_collection = vl.layer_collection.children[col.name]
bpy.ops.export_scene.gltf(filepath=os.path.join(md, KEY + ".glb"), export_format="GLB", use_active_collection=True,
                          export_apply=True, export_texcoords=False, export_normals=True, export_materials="EXPORT",
                          export_cameras=False, export_lights=False, export_yup=True, export_animations=False)
os.makedirs(os.path.join(OUT, "json", "render"), exist_ok=True)
json.dump({"key": KEY, "building_id": bid, "name": name, "ppt_2x": PPT2, "size_2x": [W2, H2], "origin_2x": list(ORIGIN2),
           "tiles": {"left": L_T, "right": R_T, "top": TOP_T, "bottom": BOT_T}, "tris": tri,
           "tris_total": sum(tri.values()), "door_face_ly": meta["door_face_ly"], "sprite_z_exaggeration": ZEX},
          open(os.path.join(OUT, "json", "render", KEY + ".json"), "w"), indent=1)
print(f"[{KEY}] done size2x", W2, H2)
