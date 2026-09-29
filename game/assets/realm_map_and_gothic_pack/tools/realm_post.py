"""realm_post.py - 1x sprites, pack JSON merge, realm map preview, per-floor previews, overview image, gate gif."""
import json, os, sys
from PIL import Image, ImageDraw, ImageFont
HERE = os.path.dirname(os.path.abspath(__file__)); WK = os.path.join(HERE, "..")
G = os.path.join(WK, "gothic"); J = os.path.join(WK, "json"); OUTD = os.path.join(WK, "..")
sys.path.insert(0, HERE)
import realm_data as rd
try:
    F = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 16)
    FS = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 12)
    FB = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 26)
except Exception:
    F = FS = FB = ImageFont.load_default()

# 1x sprites
s2, s1 = os.path.join(G, "sprites", "2x"), os.path.join(G, "sprites", "1x")
for root, _, files in os.walk(s2):
    for fn in files:
        if fn.endswith(".png"):
            im = Image.open(os.path.join(root, fn)); dst = os.path.join(s1, os.path.relpath(os.path.join(root, fn), s2))
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            im.resize((im.width // 2, im.height // 2), Image.LANCZOS).save(dst, optimize=True)
fd = os.path.join(G, "floors"); os.makedirs(os.path.join(fd, "1x"), exist_ok=True)
for i in range(1, 5):
    im = Image.open(os.path.join(fd, "gothic_f%d.png" % i)); im.resize((im.width // 2, im.height // 2), Image.LANCZOS).save(os.path.join(fd, "1x", "gothic_f%d.png" % i), optimize=True)

# merge render info into castle data
ri = json.load(open(os.path.join(G, "json", "render_info.json")))
fri = json.load(open(os.path.join(fd, "floors_render_info.json")))
gd = json.load(open(os.path.join(J, "gothic_castle.json")))
o2 = ri["origin_2x"]
gd["tile_px"] = 40
gd["sprite_2x"] = {"size": ri["size_2x"], "origin_px": o2}
gd["sprite_1x"] = {"size": [ri["size_2x"][0] // 2, ri["size_2x"][1] // 2], "origin_px": [o2[0] // 2, o2[1] // 2]}
gd["anchor_note"] = "identical convention to castle_v2.json: origin_px = pixel of the NW corner of footprint tile (x0,y0) in every full-size layer"
gd["layers"] = [{"name": n, "file": "sprites/1x/gothic_%s.png" % n} for n in ("ground", "back", "posts", "front", "cutaway")]
gd["layer_order_note"] = "draw exactly like castle_v2 (ground after floor tiles; back/posts/front in the entity pass; cutaway when the player is inside the walls)"
gd["gate"] = {"frames": [{"file": "sprites/1x/gate/gate_%02d.png" % f["frame"], "ms": f["ms"], "bridge_deg": f["bridge_deg"],
                          "portcullis_up_m": f["portcullis_z_m"]} for f in ri["frames"]],
              "crop_2x": ri["gate_crop_2x"], "crop_1x": [v // 2 for v in ri["gate_crop_2x"]]}
for f in gd["floors"]:
    r = fri[f["plane"]]
    f["sprite_size_2x"] = r["size_2x"]; f["origin_px_2x"] = r["origin_2x"]; f["origin_px_1x"] = [v // 2 for v in r["origin_2x"]]
    f["tris"] = r["tris"]
gd["triangles"] = {"exterior": ri["tris_total"], "floors": {k: v["tris"] for k, v in fri.items()}}
gd["camera"] = {"type": "orthographic", "azimuth_deg": 0, "elevation_deg": 32, "tile_locked": True, "tile_m": 1.487, "same_as": "castle_v2"}
json.dump(gd, open(os.path.join(J, "gothic_castle.json"), "w"), indent=1)

# realm map preview
realm = json.load(open(os.path.join(J, "castle_realm_map.json")))
COL = {".": (92, 128, 64), "=": (170, 150, 110), "T": (40, 78, 36), "#": (58, 52, 46), "~": (60, 110, 150), "P": (170, 80, 230),
       "S": (255, 240, 120), "o": (190, 182, 160), "f": (200, 120, 160), "c": (40, 38, 44), "r": (120, 150, 90), "l": (255, 210, 90)}
PX = 4
rows = realm["rows"]; Wd, Hd = realm["width"], realm["height"]
mp = Image.new("RGB", (Wd * PX, Hd * PX))
d = ImageDraw.Draw(mp)
for y, r in enumerate(rows):
    for x, ch in enumerate(r):
        d.rectangle([x * PX, y * PX, x * PX + PX - 1, y * PX + PX - 1], fill=COL[ch])
cg_grid = gd["walkability"]; fx0, fy0 = gd["footprint"]["x0"], gd["footprint"]["y0"]
GC = {"M": (35, 58, 60), "W": (50, 49, 56), "K": (28, 27, 32), "F": (95, 94, 98), "A": (70, 69, 76), "P": (120, 118, 124),
      "G": (150, 60, 50), "B": (130, 95, 60), "D": (220, 40, 40)}
for y, r in enumerate(cg_grid):
    for x, ch in enumerate(r):
        X, Y = (fx0 + x) * PX, (fy0 + y) * PX
        d.rectangle([X, Y, X + PX - 1, Y + PX - 1], fill=GC[ch])
for c in realm["castles"]:
    px0, py0, px1, py1 = c["plot"]
    d.rectangle([px0 * PX, py0 * PX, px1 * PX + PX - 1, py1 * PX + PX - 1], outline=(255, 255, 255) if c["status"] == "built" else (230, 230, 150), width=2)
    fx, fy, fx1, fy1 = c["footprint"]
    if c["status"] != "built":
        d.rectangle([fx * PX, fy * PX, fx1 * PX + PX - 1, fy1 * PX + PX - 1], outline=(60, 80, 40), width=2)
    txt = "%s  (phase %d, %s)" % (c["name"], c["phase"], c["status"])
    d.text((px0 * PX + 6, py0 * PX + 4), txt, fill=(255, 255, 255), font=F, stroke_width=2, stroke_fill=(0, 0, 0))
    d.text((px0 * PX + 6, py0 * PX + 24), "footprint %dx%d  (%.2gx original area)" % (fx1 - fx + 1, fy1 - fy + 1, c["size_vs_original"]),
           fill=(235, 235, 235), font=FS, stroke_width=2, stroke_fill=(0, 0, 0))
h = realm["hub"]
d.text((h["x0"] * PX - 40, h["y0"] * PX - 44), "Portal Plaza (arrival)", fill=(255, 255, 255), font=F, stroke_width=2, stroke_fill=(0, 0, 0))
rp = realm["return_portal"]
d.ellipse([rp["x"] * PX - 8, rp["y"] * PX - 8, rp["x"] * PX + 12, rp["y"] * PX + 12], outline=(220, 120, 255), width=3)
mp.save(os.path.join(WK, "previews", "realm_map_preview.png")) if os.path.isdir(os.path.join(WK, "previews")) else None
os.makedirs(os.path.join(WK, "previews"), exist_ok=True); mp.save(os.path.join(WK, "previews", "realm_map_preview.png"))

# per-floor previews (1x sprite + room labels + transitions)
MK = {"D": ((255, 200, 60), "door"), "U": ((80, 220, 255), "stairs up"), "V": ((80, 140, 255), "stairs down"), "E": ((120, 255, 120), "exit to bailey")}
chk = json.load(open(os.path.join(J, "realm_check.json")))
for f in gd["floors"]:
    im = Image.open(os.path.join(fd, "gothic_f%d.png" % f["level"])).convert("RGBA")   # 2x for clarity
    ppt = 80; ox, oy = f["origin_px_2x"]
    base = Image.new("RGBA", (im.width, im.height + 150), (22, 20, 26, 255)); base.alpha_composite(im, (0, 0))
    dd = ImageDraw.Draw(base)
    for y, r in enumerate(f["rows"]):
        for x, ch in enumerate(r):
            if ch in MK:
                X, Y = ox + x * ppt, oy + y * ppt
                dd.rectangle([X + 3, Y + 3, X + ppt - 4, Y + ppt - 4], outline=MK[ch][0], width=4)
                dd.text((X + 8, Y + 6), ch, fill=MK[ch][0], font=F, stroke_width=2, stroke_fill=(0, 0, 0))
    for rm in f["rooms"]:
        x0, y0, x1, y1 = rm["rect"]
        cx = ox + (x0 + x1 + 1) / 2 * ppt; cy = oy + (y0 + y1 + 1) / 2 * ppt
        if rm["kind"] == "roof_walk":
            cy = oy + (y0 + 0.5) * ppt
        tw = dd.textlength(rm["name"], font=F)
        dd.text((cx - tw / 2, cy - 10), rm["name"], fill=(255, 255, 255), font=F, stroke_width=3, stroke_fill=(0, 0, 0))
    line = [l for l in chk["log"] if l.startswith("floor %d" % f["level"])][0]
    dd.text((16, im.height + 12), "Duskspire Keep  -  Floor %d / 4 : %s   (plane %s, %dx%d tiles)" % (f["level"], f["name"], f["plane"], f["width"], f["height"]), fill=(255, 255, 255), font=FB)
    dd.text((16, im.height + 56), "checker: " + line.split("  ", 1)[-1].strip() + ("   PASS" if chk["pass"] else "   FAIL"), fill=(140, 255, 140), font=F)
    xx = 16
    for ch, (c_, name) in MK.items():
        dd.rectangle([xx, im.height + 96, xx + 22, im.height + 118], outline=c_, width=4); dd.text((xx + 30, im.height + 98), "%s = %s" % (ch, name), fill=c_, font=F); xx += 230
    base.save(os.path.join(WK, "previews", "gothic_floor%d_preview.png" % f["level"]))

# game-view composite (ground+back+posts+front, gate frame) for gothic and original
def composite(sp, pre, frame):
    lay = [Image.open(os.path.join(sp, pre + n + ".png")).convert("RGBA") for n in ("ground", "back", "posts", "front")]
    c = Image.new("RGBA", lay[0].size, (0, 0, 0, 0))
    for l in lay:
        c.alpha_composite(l)
    return c
full_g = Image.open(os.path.join(G, "renders", "full_direct_open_2x.png")).convert("RGBA")
full_o = Image.open("/workspace/castle/renders/full_direct_open_2x.png").convert("RGBA")
hero = Image.open(os.path.join(G, "concepts", "hero_34.png")).convert("RGBA")
Hh = 1000
def fit(im, h):
    return im.resize((int(im.width * h / im.height), h), Image.LANCZOS)
a = fit(full_o, int(Hh * full_o.height / full_g.height)); b = fit(full_g, Hh)
mpp = fit(mp.convert("RGBA"), Hh)
hh = fit(hero, 560)
Wt = mpp.width + a.width + b.width + 80
ov = Image.new("RGBA", (Wt, Hh + 140 + 580), (24, 22, 28, 255))
od = ImageDraw.Draw(ov)
od.text((20, 14), "CASTLE REALM - phase 1: realm map + Duskspire Keep (gothic castle #1)   |   flag USE_CASTLE_REALM", fill=(255, 255, 255), font=FB)
x = 20
for im, t in ((mpp, "Castle Realm map 300x200 (4 plots, 51-58+ tile gaps, portal plaza, roads)"),
              (a, "BEFORE: Stonehaven castle (castle_pack)"), (b, "AFTER: Duskspire Keep, same 24x24 footprint")):
    ov.alpha_composite(im, (x, 70)); od.text((x, 70 + Hh + 8), t, fill=(230, 230, 230), font=F); x += im.width + 20
ov.alpha_composite(hh, (20, Hh + 120))
fl = [Image.open(os.path.join(WK, "previews", "gothic_floor%d_preview.png" % i)).convert("RGBA") for i in range(1, 5)]
fx = 20 + hh.width + 20
for im in fl:
    t = fit(im, 270)
    idx = fl.index(im)
    ov.alpha_composite(t, (fx + (idx % 2) * (t.width + 10), Hh + 120 + (idx // 2) * 285))
ov.convert("RGB").save(os.path.join(OUTD, "castle_realm_overview.png"), optimize=True)

# gate gif
fr = []
gp = os.path.join(G, "sprites", "1x", "gate")
for i in range(len(ri["frames"])):
    im = Image.open(os.path.join(gp, "gate_%02d.png" % i)).convert("RGBA")
    bg = Image.new("RGBA", im.size, (35, 58, 60, 255)); bg.alpha_composite(im); fr.append(bg.convert("P"))
fr[0].save(os.path.join(WK, "previews", "gothic_gate.gif"), save_all=True, append_images=fr[1:], duration=[f["ms"] for f in ri["frames"]], loop=0)
print("post done")
