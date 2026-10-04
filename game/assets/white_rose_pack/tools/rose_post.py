"""rose_post.py - phase 2 post: 1x sprites, JSON merge, realm preview (2 castles), floor previews, overview, gifs."""
import json, os, sys
from PIL import Image, ImageDraw, ImageFont
HERE = os.path.dirname(os.path.abspath(__file__)); WK = os.path.join(HERE, "..")
G = os.path.join(WK, "rose"); J = os.path.join(WK, "json"); OUTD = os.path.join(WK, "..")
PV = os.path.join(WK, "previews"); os.makedirs(PV, exist_ok=True)
F = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 16)
FS = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 12)
FB = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 26)
FH = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 34)

s2, s1 = os.path.join(G, "sprites", "2x"), os.path.join(G, "sprites", "1x")
for root, _, files in os.walk(s2):
    for fn in files:
        if fn.endswith(".png"):
            im = Image.open(os.path.join(root, fn)); dst = os.path.join(s1, os.path.relpath(os.path.join(root, fn), s2))
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            im.resize((im.width // 2, im.height // 2), Image.LANCZOS).save(dst, optimize=True)
fd = os.path.join(G, "floors"); os.makedirs(os.path.join(fd, "1x"), exist_ok=True)
for i in range(1, 5):
    im = Image.open(os.path.join(fd, "rose_f%d.png" % i)); im.resize((im.width // 2, im.height // 2), Image.LANCZOS).save(os.path.join(fd, "1x", "rose_f%d.png" % i), optimize=True)

ri = json.load(open(os.path.join(G, "json", "render_info.json")))
fri = json.load(open(os.path.join(fd, "floors_render_info.json")))
gd = json.load(open(os.path.join(J, "white_rose_castle.json")))
o2 = ri["origin_2x"]
gd["tile_px"] = 40
gd["sprite_2x"] = {"size": ri["size_2x"], "origin_px": o2}
gd["sprite_1x"] = {"size": [ri["size_2x"][0] // 2, ri["size_2x"][1] // 2], "origin_px": [o2[0] // 2, o2[1] // 2]}
gd["anchor_note"] = "identical convention to castle_v2.json / gothic_castle.json: origin_px = pixel of the NW corner of footprint tile (x0,y0)"
gd["layers"] = [{"name": n, "file": "sprites/1x/rose_%s.png" % n} for n in ("ground", "back", "posts", "front", "cutaway")]
gd["layer_order_note"] = "same as castle_v2; fountain frames are blitted right after the back layer"
gd["gate"] = {"frames": [{"file": "sprites/1x/gate/gate_%02d.png" % f["frame"], "ms": f["ms"], "bridge_deg": f["bridge_deg"],
                          "portcullis_up_m": f["portcullis_z_m"]} for f in ri["frames"]],
              "crop_2x": ri["gate_crop_2x"], "crop_1x": [v // 2 for v in ri["gate_crop_2x"]]}
gd["fountain"] = {"frames": [{"file": "sprites/1x/fountain/fountain_%02d.png" % f["frame"], "ms": f["ms"]} for f in ri["fountain_frames"]],
                  "crop_2x": ri["fountain_crop_2x"], "crop_1x": [v // 2 for v in ri["fountain_crop_2x"]], "loop": True,
                  "note": "always animating (ambient); blit at crop_1x offset relative to the full layer, after the back layer"}
for f in gd["floors"]:
    r = fri[f["plane"]]
    f["sprite_size_2x"] = r["size_2x"]; f["origin_px_2x"] = r["origin_2x"]; f["origin_px_1x"] = [v // 2 for v in r["origin_2x"]]; f["tris"] = r["tris"]
gd["triangles"] = {"exterior": ri["tris_total"], "floors": {k: v["tris"] for k, v in fri.items()}}
gd["camera"] = {"type": "orthographic", "azimuth_deg": 0, "elevation_deg": 32, "tile_locked": True, "tile_m": 1.487, "same_as": "castle_v2"}
json.dump(gd, open(os.path.join(J, "white_rose_castle.json"), "w"), indent=1)

# realm map preview (both built castles drawn from their grids)
realm = json.load(open(os.path.join(J, "castle_realm_map.json")))
COL = {".": (92, 128, 64), "=": (170, 150, 110), "T": (40, 78, 36), "#": (58, 52, 46), "~": (60, 110, 150), "P": (170, 80, 230),
       "S": (255, 240, 120), "o": (190, 182, 160), "f": (200, 120, 160), "c": (40, 38, 44), "r": (120, 150, 90), "l": (255, 210, 90)}
GCOL = {"gothic": {"M": (35, 58, 60), "W": (50, 49, 56), "K": (28, 27, 32), "F": (95, 94, 98), "A": (70, 69, 76), "P": (120, 118, 124),
                   "G": (150, 60, 50), "B": (130, 95, 60), "D": (220, 40, 40)},
        "white_rose": {"M": (76, 144, 184), "W": (215, 210, 198), "K": (185, 132, 136), "F": (222, 214, 192), "A": (200, 195, 185),
                       "P": (200, 195, 180), "G": (90, 90, 96), "B": (150, 110, 70), "D": (60, 110, 58), "N": (150, 210, 235), "H": (80, 130, 60)}}
PX = 4
mp = Image.new("RGB", (realm["width"] * PX, realm["height"] * PX)); d = ImageDraw.Draw(mp)
for y, r in enumerate(realm["rows"]):
    for x, ch in enumerate(r):
        d.rectangle([x * PX, y * PX, x * PX + PX - 1, y * PX + PX - 1], fill=COL[ch])
for c in realm["castles"]:
    if c["status"] == "built":
        cd = json.load(open(os.path.join(J, c["data"])))
        fx0, fy0 = cd["footprint"]["x0"], cd["footprint"]["y0"]
        for y, r in enumerate(cd["walkability"]):
            for x, ch in enumerate(r):
                X, Y = (fx0 + x) * PX, (fy0 + y) * PX
                d.rectangle([X, Y, X + PX - 1, Y + PX - 1], fill=GCOL[c["id"]][ch])
for c in realm["castles"]:
    px0, py0, px1, py1 = c["plot"]
    d.rectangle([px0 * PX, py0 * PX, px1 * PX + PX - 1, py1 * PX + PX - 1], outline=(255, 255, 255) if c["status"] == "built" else (230, 230, 150), width=2)
    fx, fy, fx1, fy1 = c["footprint"]
    d.text((px0 * PX + 6, py0 * PX + 4), "%s  (phase %d, %s)" % (c["name"], c["phase"], c["status"]), fill=(255, 255, 255), font=F, stroke_width=2, stroke_fill=(0, 0, 0))
    d.text((px0 * PX + 6, py0 * PX + 24), "footprint %dx%d  (%.2gx original area)" % (fx1 - fx + 1, fy1 - fy + 1, c["size_vs_original"]),
           fill=(235, 235, 235), font=FS, stroke_width=2, stroke_fill=(0, 0, 0))
h = realm["hub"]
d.text((h["x0"] * PX - 40, h["y0"] * PX - 44), "Portal Plaza (arrival)", fill=(255, 255, 255), font=F, stroke_width=2, stroke_fill=(0, 0, 0))
mp.save(os.path.join(PV, "realm_map_preview.png"))

# per-floor previews
MK = {"D": ((255, 170, 40), "door"), "U": ((40, 200, 90), "stairs up"), "V": ((60, 120, 255), "stairs down"), "E": ((230, 60, 160), "exit to bailey")}
chk = json.load(open(os.path.join(J, "realm_check.json")))
for f in gd["floors"]:
    im = Image.open(os.path.join(fd, "rose_f%d.png" % f["level"])).convert("RGBA")
    ppt = 80; ox, oy = f["origin_px_2x"]
    base = Image.new("RGBA", (im.width, im.height + 150), (30, 32, 36, 255)); base.alpha_composite(im, (0, 0))
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
        if rm["kind"] == "terrace":
            cx, cy = ox + 3 * ppt, oy + 9.5 * ppt
        tw = dd.textlength(rm["name"], font=F)
        dd.text((cx - tw / 2, cy - 10), rm["name"], fill=(255, 255, 255), font=F, stroke_width=3, stroke_fill=(0, 0, 0))
    line = [l for l in chk["log"] if l.startswith("white_rose floor %d" % f["level"])][0]
    dd.text((16, im.height + 12), "White Rose Castle - Floor %d / 4 : %s   (plane %s, %dx%d tiles = keep exterior)" % (f["level"], f["name"], f["plane"], f["width"], f["height"]), fill=(255, 255, 255), font=FB)
    dd.text((16, im.height + 56), "checker: " + line.split("  ", 1)[-1].strip() + ("   PASS" if chk["pass"] else "   FAIL"), fill=(140, 255, 140), font=F)
    xx = 16
    for ch, (c_, name) in MK.items():
        dd.rectangle([xx, im.height + 96, xx + 22, im.height + 118], outline=c_, width=4); dd.text((xx + 30, im.height + 98), "%s = %s" % (ch, name), fill=c_, font=F); xx += 230
    base.save(os.path.join(PV, "rose_floor%d_preview.png" % f["level"]))

# overview: realm map | before (original, same px scale) | after (white rose) ; hero shots + floors below
def fit(im, h):
    return im.resize((max(1, int(im.width * h / im.height)), h), Image.LANCZOS)
full_r = Image.open(os.path.join(G, "renders", "full_direct_open_2x.png")).convert("RGBA")
full_o = Image.open("/workspace/castle/renders/full_direct_open_2x.png").convert("RGBA")
Hh = 1100
sc = Hh / full_r.height
b = fit(full_r, Hh); a = full_o.resize((int(full_o.width * sc), int(full_o.height * sc)), Image.LANCZOS)
mpp = fit(mp.convert("RGBA"), Hh)
heroes = [Image.open(os.path.join(G, "concepts", n)).convert("RGBA") for n in ("hero_34.png", "hero_garden.png", "hero_gate.png") if os.path.exists(os.path.join(G, "concepts", n))]
Wt = mpp.width + a.width + b.width + 80
ov = Image.new("RGBA", (Wt, Hh + 170 + 620), (26, 28, 32, 255)); od = ImageDraw.Draw(ov)
od.text((20, 14), "CASTLE REALM - phase 2: White Rose Castle (48x48 = 4x area)   |   flag USE_CASTLE_REALM   |   checker PASS" if chk["pass"] else "FAIL", fill=(255, 255, 255), font=FH)
x = 20
for im, t in ((mpp, "Castle Realm map (White Rose now built, NE plot)"), (a, "BEFORE: Stonehaven (same pixel scale)"), (b, "AFTER: White Rose Castle (gate open, fountain frame 0)")):
    ov.alpha_composite(im, (x, 80 + (Hh - im.height))); od.text((x, 80 + Hh + 8), t, fill=(230, 230, 230), font=F); x += im.width + 20
yb = Hh + 130
hx = 20
for hm in heroes[:2]:
    t = fit(hm, 600); ov.alpha_composite(t, (hx, yb)); hx += t.width + 16
fl = [Image.open(os.path.join(PV, "rose_floor%d_preview.png" % i)).convert("RGBA") for i in range(1, 5)]
for i, im in enumerate(fl):
    t = fit(im, 290)
    ov.alpha_composite(t, (hx + (i % 2) * (t.width + 10), yb + (i // 2) * 305))
ov = ov.crop((0, 0, max(Wt, hx + 2 * (fit(fl[0], 290).width + 10)), ov.height))
ov.convert("RGB").save(os.path.join(OUTD, "white_rose_overview.png"), optimize=True)

def gif(folder, n, name, ms, bgc):
    fr = []
    for i in range(n):
        im = Image.open(os.path.join(folder, "%s_%02d.png" % (name, i))).convert("RGBA")
        bg = Image.new("RGBA", im.size, bgc); bg.alpha_composite(im); fr.append(bg.convert("P"))
    fr[0].save(os.path.join(PV, "rose_%s.gif" % name), save_all=True, append_images=fr[1:], duration=ms, loop=0)
gif(os.path.join(s1, "gate"), len(ri["frames"]), "gate", [f["ms"] for f in ri["frames"]], (76, 144, 184, 255))
# fountain gif composited over the back layer crop so it reads in context
back = Image.open(os.path.join(s1, "rose_back.png")).convert("RGBA"); gr = Image.open(os.path.join(s1, "rose_ground.png")).convert("RGBA")
cx0, cy0, cx1, cy1 = [v // 2 for v in ri["fountain_crop_2x"]]
ctx = Image.new("RGBA", (cx1 - cx0, cy1 - cy0), (0, 0, 0, 255)); ctx.alpha_composite(gr.crop((cx0, cy0, cx1, cy1))); ctx.alpha_composite(back.crop((cx0, cy0, cx1, cy1)))
fr = []
for i in range(len(ri["fountain_frames"])):
    im = Image.open(os.path.join(s1, "fountain", "fountain_%02d.png" % i)).convert("RGBA")
    c = ctx.copy(); c.alpha_composite(im.resize(c.size)); c = c.resize((c.width * 2, c.height * 2), Image.NEAREST); fr.append(c.convert("P"))
fr[0].save(os.path.join(PV, "rose_fountain.gif"), save_all=True, append_images=fr[1:], duration=110, loop=0)
print("post done")
