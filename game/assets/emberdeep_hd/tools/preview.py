import sys, time, math, os, numpy as np
from PIL import Image, ImageDraw, ImageFont
sys.path.insert(0, "/workspace/emberdeep_hd/reference")
from emberdeep_view3d import EmberView3D
rows = [l.rstrip("\n") for l in open("/workspace/ember_review/emberdeep_v2_pack/interior/emberdeep_v2_floor.txt") if l.strip()]
W = max(len(r) for r in rows)
tiles = [[{"#": 1, "L": 2}.get(ch, 0) for ch in r.ljust(W, "#")] for r in rows]
TEX = "/workspace/emberdeep_hd/textures"
v = EmberView3D(tiles, TEX, lambda t: t == 1, lambda t: t == 2, boss_door=(22, 7))
PH = "/workspace/player_hd/assets/male/2x"
def layer(name, anim, fr=0):
    p = f"{PH}/{name}/{anim}.png"
    if not os.path.exists(p):
        return None
    im = Image.open(p).convert("RGBA"); return im.crop((fr * 288, 0, fr * 288 + 288, 288))
import json
CAT = json.load(open("/workspace/player_hd/assets/catalogue.json"))
ZC = {it["layer"]: it["z"] for it in CAT["items"] if "layer" in it}
ZC.update({a["layer"]: a["z"] for a in CAT["armour_layers"]}); ZC.update({w["layer"]: w["z"] for w in CAT["weapon_layers"]})
ZC["shadow"] = {"s": 0, "e": 0, "n": 0, "w": 0}; ZC["brows"] = {"s": 12, "e": 12, "n": 12, "w": 12}
HAIR = tuple(c / 255 for c in next(p["mul"] for p in CAT["hair_palette"] if p["id"] == "dark_brown"))
STEEL = tuple(min(1.0, c / 255 * CAT["tier_tint_gain"]) for c in CAT["tier_tints"]["steel"])
LOOK = ("body_light", "brows", "hair_side_part", "top_noble_doublet", "bottom_noble_hose", "shoes_riding_boots", "acc_satchel", "wpn_sword")
def player(anim="idle_n", fr=0):
    """Compose exactly like player_hd_client: z-sorted layers, *_tint parts multiplied by hair colour / tier tint."""
    face = anim.rsplit("_", 1)[1]
    out = Image.new("RGBA", (288, 288))
    for n in sorted(("shadow",) + LOOK, key=lambda l: ZC.get(l, {"s": 50, "e": 50, "n": 50, "w": 50})[face]):
        l = layer(n, anim, fr)
        if l is not None:
            out.alpha_composite(l)
        t = layer(n, anim + "_tint", fr)
        if t is not None:
            col = HAIR if (n.startswith("hair") or n == "brows") else STEEL
            a = np.asarray(t).astype(np.float32) / 255
            a[..., :3] *= np.array(col, np.float32)
            out.alpha_composite(Image.fromarray((a * 255).astype(np.uint8), "RGBA"))
    return out
CR = "/workspace/emberdeep/creatures"
WYRM_TILES_H = 4.8   # the full 512 px dragon canvas spans this many tiles (see dragon/meta.json)
OCC = {}
def put(img, spr, feet, scale, anchor_y=1.0, feet_px=None):
    w, h = spr.size
    s = spr.resize((max(1, int(w * scale)), max(1, int(h * scale))), Image.LANCZOS)
    if feet_px:
        fx, fy = feet_px[0] * scale, feet_px[1] * scale
    else:
        fx, fy = s.size[0] / 2, s.size[1] * anchor_y
    img.alpha_composite(s, (int(feet[0] - fx), int(feet[1] - fy)))
def frame(px, py, yaw, zoom, rw=480, rh=300, mons=(), wyrm=None, label=""):
    v.set_camera(px + 0.5, py + 0.5, yaw, zoom)
    v.heights[:] = v.heights_target
    t = time.time(); rgb, depth = v.render(rw, rh, 3.0); dt = time.time() - t
    img = Image.fromarray(rgb).resize((rw * 2, rh * 2), Image.BILINEAR).convert("RGBA")
    bg = img.copy()
    bills = []
    for (mx, my, path, h) in mons:
        p = v.project(mx + 0.5, my + 0.5, 0)
        if p: bills.append((p[0], "m", p, path, h, (mx, my)))
    if wyrm:
        p = v.project(wyrm[0] + 0.5, wyrm[1] + 0.5, 0)
        if p: bills.append((p[0], "w", p, None, 0, wyrm))
    p = v.project(px + 0.5, py + 0.5, 0)
    bills.append((p[0], "p", p, None, 0, (px, py)))
    # torches
    sc = Image.open(f"{TEX}/torch_sconce_strip.png").convert("RGBA").crop((96, 0, 192, 160))
    for (tx, ty, nx, ny) in v.torches:
        q = v.project(tx + nx * 0.06, ty + ny * 0.06, 1.25)
        if q and 0 < q[1] < rw and 0 < q[2] < rh and v.visible(tx + nx * 0.3, ty + ny * 0.3, 1.2):
            bills.append((q[0], "t", q, None, 0, None))
    bills.sort(key=lambda b: -b[0])
    for z, kind, (d, sx, sy, ppt), path, h, pos in bills:
        feet = (sx * 2, sy * 2); ppt2 = ppt * 2
        x0, y0, x1, y1 = sx - ppt * 3, sy - ppt * 5, sx + ppt * 3, sy + ppt * 0.6
        mask, (ox, oy) = v.occluders(x0, y0, x1, y1, z)
        if kind == "p":
            put(img, player(), feet, ppt2 / 80 * 1.0, feet_px=(144, 248))
        elif kind == "m":
            spr = Image.open(path).convert("RGBA")
            put(img, spr, feet, ppt2 * h / spr.size[1], anchor_y=0.93)
        elif kind == "w":
            anim, fi = (wyrm[2], wyrm[3]) if len(wyrm) > 2 else ("idle", 0)
            st = Image.open(f"/workspace/emberdeep_hd/dragon/{anim}_s.png").convert("RGBA")
            spr = st.crop((fi * 768, 0, fi * 768 + 768, 512))
            put(img, spr, feet, ppt2 * WYRM_TILES_H / 512, feet_px=(384, 330))
        elif kind == "t":
            put(img, sc, feet, ppt2 * 0.9 / 160, anchor_y=0.7)
        if mask is not None and mask.any() and kind != "p":
            m = Image.fromarray((mask * 255).astype(np.uint8)).resize((mask.shape[1] * 2, mask.shape[0] * 2))
            img.paste(bg.crop((ox * 2, oy * 2, ox * 2 + m.size[0], oy * 2 + m.size[1])), (ox * 2, oy * 2), m)
    d = ImageDraw.Draw(img)
    try:
        f = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 22)
    except Exception:
        f = None
    d.rectangle((0, 0, rw * 2, 34), fill=(0, 0, 0, 150))
    d.text((12, 6), f"{label}   (render {dt*1000:.0f} ms at {rw}x{rh})", fill=(255, 225, 180), font=f)
    return img.convert("RGB"), dt
if __name__ == "__main__":
    mons = [(14, 23, f"{CR}/bile_toad/front.png", 1.1), (12, 23, f"{CR}/bile_toad/front.png", 1.1)]
    # player in the toad room facing north, toad 1 tile ahead-right
    a, _ = frame(13, 24, 0.0, 0.0, mons=mons, label="Zoom in: close behind the player")
    b, _ = frame(13, 24, 0.0, 0.5, mons=mons, label="Zoom mid")
    c, _ = frame(13, 24, 0.0, 1.0, mons=mons, label="Zoom out: rooms around you")
    w1, _ = frame(22, 6, 0.0, 0.55, wyrm=(22, 3, "idle", 0), label="Wyrm lair, mid zoom (rendered frames)")
    w2, _ = frame(22, 6, 0.0, 0.3, wyrm=(22, 3, "breath", 5), label="Wyrm breath, frame 5 (release on frame 4 = the 0.6 s tick)")
    for name, im in (("cam_close", a), ("cam_mid", b), ("cam_far", c), ("cam_lair", w1), ("cam_lair_breath", w2)):
        im.save(f"/workspace/emberdeep_hd/previews/{name}.png")
    sw, sh = a.size
    sheet = Image.new("RGB", (sw * 2, sh * 3), (0, 0, 0))
    for i, im in enumerate((a, b, c, w1, w2)):
        sheet.paste(im, ((i % 2) * sw, (i // 2) * sh))
    sheet.save("/workspace/emberdeep_hd/previews/emberdeep_camera_zoom_sheet.png", optimize=True)
    print("ok")
