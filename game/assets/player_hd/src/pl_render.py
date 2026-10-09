"""Batch sprite renderer (resumable). Usage:
blender -b --factory-startup -noaudio --python pl_render.py -- <male|female> <2x|4x> [layer,layer,...] [anim,anim]
Raw frames -> /workspace/player_hd/renders/<kind>/<scale>/<layer>/<anim>_<facing>_<kk>.png (+ _m.png tint mask)."""
import bpy, sys, os, time, math, shutil
sys.path.insert(0, "/workspace/player_hd/src")
import pl_scene as S
import pl_rig as R
import pl_items as I
C, H = S.C, S.H

argv = sys.argv[sys.argv.index("--") + 1:]
kind, scale = argv[0], argv[1]
only_layers = set(argv[2].split(",")) if len(argv) > 2 and argv[2] not in ("", "all") else None
only_anims = set(argv[3].split(",")) if len(argv) > 3 else None
ROOT = f"/workspace/player_hd/renders/{kind}/{scale}"
os.makedirs(ROOT, exist_ok=True)

TINT_LAYERS = {"brows"} | {c[0] for c in I.CATALOGUE if c[5]} | {a[0] for a in I.ARMOUR} | {w[0] for w in I.WEAPONS}
WEAPON_ANIMS = {w[0]: set(w[3]) for w in I.WEAPONS}


def layer_list(ctx):
    L = [("shadow", None), ("body_light", "light"), ("body_tan", "tan"), ("body_deep", "deep"), ("brows", None)]
    for cid, slot, *_ in I.CATALOGUE:
        if slot != "skin":
            L.append((cid, None))
    L += [(a[0], None) for a in I.ARMOUR] + [(w[0], None) for w in I.WEAPONS]
    L = [x for x in L if only_layers is None or x[0] in only_layers]
    sh = os.environ.get("PL_SHARD")           # "i/n": this worker takes every n-th layer
    if sh:
        i, n = map(int, sh.split("/"))
        L = [x for j, x in enumerate(L) if j % n == i]
    return L


def frames_for(lid):
    out = []
    for anim, (n, facings, loop, doc) in R.ANIMS.items():
        if only_anims and anim not in only_anims:
            continue
        if lid in WEAPON_ANIMS and anim not in WEAPON_ANIMS[lid]:
            continue
        if scale == "4x":
            if anim != "idle":
                continue
            n = 1
        for f in facings:
            for k in range(n):
                out.append((anim, f, k))
    return out


def setup_comp(sc):
    sc.use_nodes = True
    nt = sc.node_tree
    for n in list(nt.nodes):
        nt.nodes.remove(n)
    rl = nt.nodes.new("CompositorNodeRLayers")
    comp = nt.nodes.new("CompositorNodeComposite")
    nt.links.new(rl.outputs["Image"], comp.inputs["Image"])
    fo = nt.nodes.new("CompositorNodeOutputFile")
    fo.base_path = "/tmp/pl_aov_" + kind + scale + "_" + str(os.getpid())
    fo.format.file_format = "PNG"; fo.format.color_mode = "BW"; fo.format.color_depth = "8"
    fo.file_slots[0].path = "m_"
    nt.links.new(rl.outputs["tint"], fo.inputs[0])
    return fo


def main():
    t_start = time.time()
    want = {lid for lid, _ in layer_list(None) if not (lid.startswith("body_") or lid in ("shadow", "brows"))}
    sc, ctx = S.build(kind, only=want, hero=False)     # build only this shard's layers (memory)
    if scale == "2x":
        H.sprite_camera(sc, h_px=87.8, height_m=1.0, w=288, hgt=288, feet=(144, 248))
        C.cycles(sc, samples=16, w=288, h=288)
    else:
        H.sprite_camera(sc, h_px=175.6, height_m=1.0, w=576, hgt=576, feet=(288, 496))
        C.cycles(sc, samples=64, w=576, h=576)
    sc.render.use_persistent_data = True
    cy = sc.cycles
    cy.use_light_tree = False
    cy.max_bounces = 4; cy.diffuse_bounces = 2; cy.glossy_bounces = 2; cy.transmission_bounces = 3
    cy.volume_bounces = 0; cy.transparent_max_bounces = 8
    nthreads = int(os.environ.get("PL_THREADS", "0"))
    if nthreads:
        sc.render.threads_mode = "FIXED"; sc.render.threads = nthreads
    sc.render.film_transparent = True
    sc.view_settings.view_transform = "AgX"
    sc.frame_current = 1
    catcher = C.shadow_catcher("ShadowCatcher", 6.0, (0, 0, 0), ctx.col)
    fo = setup_comp(sc)
    layers = layer_list(ctx)
    print(f"[plan] {kind} {scale} layers={len(layers)} errors={list(ctx.errors)}", flush=True)
    for li, (lid, skin) in enumerate(layers):
        out_dir = f"{ROOT}/{lid}"; os.makedirs(out_dir, exist_ok=True)
        done_flag = f"{out_dir}/DONE"
        frames = frames_for(lid)
        if os.path.exists(done_flag):
            print(f"[skip] {lid} DONE", flush=True); continue
        src = "body" if lid.startswith("body_") or lid == "shadow" else lid
        if src not in ctx.layers:
            print(f"[miss] {lid} not built", flush=True); continue
        # visibility
        S.show(ctx, ["body"] if src == "body" else [src], skin=skin or "light", holdout_body=(src != "body"))
        catcher.hide_render = lid != "shadow"
        for o in ctx.layers["body"]:
            o.visible_camera = lid != "shadow"
        if lid == "shadow":
            for o in ctx.layers["body"]:
                o.hide_render = False; o.is_holdout = False
        fo.mute = lid not in TINT_LAYERS
        sc.cycles.samples = 8 if lid == "shadow" else (16 if scale == "2x" else 64)
        sc.cycles.adaptive_threshold = 0.012
        ctx.cur_layer = lid
        t0 = time.time(); n_new = 0
        for anim, f, k in frames:
            png = f"{out_dir}/{anim}_{f}_{k:02d}.png"
            mpng = png[:-4] + "_m.png"
            if os.path.exists(png) and (lid not in TINT_LAYERS or os.path.exists(mpng)):
                continue
            S.pose(ctx, anim, k, f)
            C.render(sc, png)
            if lid in TINT_LAYERS:
                shutil.move(f"{fo.base_path}/m_0001.png", mpng)
            n_new += 1
        open(done_flag, "w").write(f"{len(frames)} frames\n")
        dt = time.time() - t0
        print(f"[layer] {li+1}/{len(layers)} {lid} frames={len(frames)} new={n_new} {dt:.0f}s ({dt/max(1,n_new):.2f}s/f) elapsed={time.time()-t_start:.0f}s", flush=True)
    print(f"[done] {kind} {scale} total {time.time()-t_start:.0f}s", flush=True)


main()
