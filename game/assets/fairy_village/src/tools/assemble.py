"""Assemble final game assets from renders/: 4x/2x/1x sprites, meta.json, heroes (transparent + composited)."""
import json, os, glob, shutil, sys
from PIL import Image
sys.path.insert(0, os.path.dirname(__file__))
import backdrop
R = "/workspace/fairy_village/renders"; A = "/workspace/fairy_village/assets"; J = "/workspace/fairy_village/json"
BUILD = ["queens_tree_hall", "moonpetal_inn", "mushroom_apothecary"]
FOUNT = ["moonstone_fountain", "lily_fountain"]
NPCS = ["elowen_moonwhisper", "warden_thorne", "tumbleroot", "pip_dewdrop"]


def save_png(im, path):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    im.save(path, optimize=True)


def clean_slabs(im, minrun=120):
    """Remove opaque pure-black render slabs (geometry under the shadow catcher) and leave a soft shadow instead."""
    import numpy as np
    a = np.array(im)
    m = (a[..., :3].max(-1) < 4) & (a[..., 3] > 250)
    hit = 0
    for y in range(m.shape[0]):
        row = m[y]
        if row.sum() < minrun:
            continue
        d = np.diff(np.concatenate([[0], row.astype(np.int8), [0]]))
        for st, en in zip(np.nonzero(d == 1)[0], np.nonzero(d == -1)[0]):
            if en - st >= minrun:
                a[y, st:en] = (0, 0, 0, 45); hit += en - st
    if hit:
        print("  cleaned black slab px:", hit)
    return Image.fromarray(a)


def scales(im4):
    w, h = im4.size
    return {"4x": im4, "2x": im4.resize((w // 2, h // 2), Image.LANCZOS), "1x": im4.resize((w // 4, h // 4), Image.LANCZOS)}


def hero(src, dst_dir, key, style, seed):
    if not os.path.exists(src):
        return None
    im = Image.open(src).convert("RGBA")
    save_png(im, f"{dst_dir}/{key}_hero_2048.png")
    backdrop.comp(src, f"{dst_dir}/{key}_hero_2048_bg.jpg", seed, style)
    return f"{key}_hero_2048.png"


def struct(key, kind):
    meta = json.load(open(f"{R}/meta/{key}.json"))
    col = json.load(open(f"{J}/collision/{key}.json"))
    d = f"{A}/{kind}/{key}"
    os.makedirs(d, exist_ok=True)
    info = meta["sprite_4x"]
    out = {"key": key, "name": meta["name"], "footprint_tiles": meta["footprint_tiles"], "footprint": col["footprint"],
           "projection": meta["projection"], "tile_px": {"1x": 40, "2x": 80, "4x": 160},
           "origin_px": {k: [info["origin_px"][0] // f, info["origin_px"][1] // f] for k, f in (("4x", 1), ("2x", 2), ("1x", 4))},
           "origin_note": "pixel of the footprint's NW corner (tile x0,y0 top-left). Blit at (tile_x0*tile_px - origin_px.x, tile_y0*tile_px - origin_px.y) in world pixels.",
           "overhang_tiles": None, "canvas_extent_tiles_from_nw_corner_y_up": info["tiles"], "collision": f"json/collision/{key}.json",
           "interaction_tile": col.get("interaction_tile"), "stand_tile": col.get("stand_tile"), "door_tile": col.get("door_tile")}
    _src = sorted(glob.glob(f"{R}/sprite_4x/{key}/f*.png"))[0] if meta.get("frames") else None
    _W, _H = Image.open(_src or f"{R}/sprite_4x/{key}.png").size
    _ox, _oy = info["origin_px"]; _fw = out["footprint"]["w"]; _fh = out["footprint"]["h"]
    out["overhang_tiles"] = {"left": round(_ox / 160, 2), "top": round(_oy / 160, 2), "right": round(_W / 160 - _ox / 160 - _fw, 2), "bottom": round(_H / 160 - _oy / 160 - _fh, 2)}
    if meta.get("frames"):
        files = sorted(glob.glob(f"{R}/sprite_4x/{key}/f*.png"))
        for fp in files:
            for k, im in scales(clean_slabs(Image.open(fp).convert("RGBA"))).items():
                save_png(im, f"{d}/frames_{k}/{os.path.basename(fp)}")
        out.update({"frames": len(files), "fps": meta.get("fps_suggested", 10), "loop": True,
                    "files": {k: f"frames_{k}/f00.png .. f{len(files)-1:02d}.png" for k in ("1x", "2x", "4x")}})
    else:
        for k, im in scales(clean_slabs(Image.open(f"{R}/sprite_4x/{key}.png").convert("RGBA"))).items():
            save_png(im, f"{d}/{key}_{k}.png")
        out["files"] = {k: f"{key}_{k}.png" for k in ("1x", "2x", "4x")}
    out["hero"] = hero(f"{R}/hero/{key}.png", d, key, "twilight", 3)
    json.dump(out, open(f"{d}/meta.json", "w"), indent=1)
    return out


def npc(key):
    src = f"{R}/npc/{key}"; d = f"{A}/npcs/{key}"
    os.makedirs(d, exist_ok=True)
    spawns = {n["id"]: n for n in json.load(open(f"{J}/npc_spawns.json"))["npcs"]}
    nfr = 0
    for f in ("s", "e", "n", "w"):
        for fp in sorted(glob.glob(f"{src}/sprite_4x/{f}/f*.png")):
            for k, im in scales(Image.open(fp).convert("RGBA")).items():
                save_png(im, f"{d}/sprite_{k}/{f}/{os.path.basename(fp)}")
            nfr = max(nfr, int(os.path.basename(fp)[1:3]) + 1)
    out = {"id": key, "name": spawns[key]["name"], "tile": [spawns[key]["x"], spawns[key]["y"]], "role": spawns[key]["role"],
           "facings": {"s": "toward camera (south)", "e": "east / screen right", "n": "away (north)", "w": "west / screen left"},
           "canvas": {"1x": [96, 128], "2x": [192, 256], "4x": [384, 512]}, "feet_px": {"1x": [48, 118], "2x": [96, 236], "4x": [192, 472]},
           "scale_note": "constant 175.6 px per metre at 4x (43.9 at 1x) for every NPC, so the gnome and child read smaller",
           "frames": nfr, "fps": 8, "loop": True, "idle_frame": 0,
           "files": "sprite_{1x,2x,4x}/{s,e,n,w}/f00.png .. f%02d.png" % max(0, nfr - 1)}
    out["hero"] = hero(f"{src}/hero.png", d, key, "forest", 7)
    if os.path.exists(f"{src}/portrait_bust.png"):
        p = Image.open(f"{src}/portrait_bust.png").convert("RGBA")
        save_png(p, f"{d}/portrait_bust.png")
        save_png(p.resize((512, 512), Image.LANCZOS), f"{d}/portrait_bust_512.png")
        backdrop.comp(f"{src}/portrait_bust.png", f"{d}/portrait_bust_bg.jpg", 9, "forest")
        out["portrait"] = "portrait_bust.png (1536, transparent) + portrait_bust_512.png + portrait_bust_bg.jpg"
    json.dump(out, open(f"{d}/meta.json", "w"), indent=1)
    return out


if __name__ == "__main__":
    which = sys.argv[1:] or BUILD + FOUNT + NPCS
    for k in which:
        if k in BUILD:
            struct(k, "buildings")
        elif k in FOUNT:
            struct(k, "fountains")
        elif k in NPCS:
            npc(k)
        print("assembled", k, flush=True)
