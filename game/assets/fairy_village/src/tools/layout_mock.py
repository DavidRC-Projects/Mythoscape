"""Village layout mock at game scale (1x = 40 px/tile) from the planned grid, with sprites, crypt and labels."""
import json, pickle, os, sys, glob
from PIL import Image, ImageDraw, ImageFont
F = "/workspace/fairy_village"
sys.path.insert(0, F + "/src"); import layout as L
g = pickle.load(open(F + "/ref/grid_fairy.pkl", "rb"))
X0, Y0, X1, Y1 = 0, 34, 62, 112
T = 40
W, H = (X1 - X0) * T, (Y1 - Y0) * T
COL = {0: (74, 120, 52), 1: (38, 78, 34), 2: (60, 110, 170), 3: (150, 100, 60), 4: (92, 90, 96), 5: (170, 146, 102), 6: (122, 106, 88),
       7: (46, 90, 40), 8: (128, 118, 120), 13: (158, 158, 168)}
img = Image.new("RGBA", (W, H), (0, 0, 0, 255))
tiles = {k: [Image.open(f"{F}/assets/tiles/{n}_v{i}_40.png").convert("RGBA") for i in (1, 2, 3)] for k, n in ((0, "fairy_moss"), (5, "petal_path"), (13, "moonstone_paving"))}
fz = L.FAIRY_ZONE
for y in range(Y0, Y1):
    for x in range(X0, X1):
        t = g[y][x]
        px, py = (x - X0) * T, (y - Y0) * T
        if fz[0] <= x <= fz[2] and fz[1] <= y <= fz[3] and t in tiles:
            img.paste(tiles[t][(x * 7 + y * 13) % 3], (px, py))
        else:
            c = COL.get(t, (200, 0, 200))
            if t == 0 and (x + y) % 2:
                c = tuple(int(v * 0.96) for v in c)
            img.paste(c + (255,), (px, py, px + T, py + T))
d = ImageDraw.Draw(img)
try:
    font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 30)
    small = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 20)
except Exception:
    font = small = ImageFont.load_default()
# quarry ore markers
for o in L.MINE["ore"]:
    px, py = (o["x"] - X0) * T, (o["y"] - Y0) * T
    d.ellipse((px + 8, py + 8, px + 32, py + 32), fill=(190, 120, 70) if o["tile"] == "ORE" else (170, 170, 180), outline=(40, 30, 20), width=2)
# sprites: (blit_x, blit_y, sort_y, image)
draws = []
def struct(key, kind, fp):
    d0 = f"{F}/assets/{kind}/{key}"
    meta = json.load(open(f"{d0}/meta.json")) if os.path.exists(f"{d0}/meta.json") else None
    if not meta:
        return
    p = f"{d0}/{meta['files']['1x']}" if "frames" not in meta else f"{d0}/frames_1x/f00.png"
    im = Image.open(p).convert("RGBA")
    ox, oy = meta["origin_px"]["1x"]
    draws.append(((fp[0] - X0) * T - ox, (fp[1] - Y0) * T - oy, fp[3], im))
for k, v in L.BUILDINGS.items():
    struct(k, "buildings", v["footprint"])
for k, v in L.FOUNTAINS.items():
    struct(k, "fountains", v["footprint"])
for k, v in L.NPCS.items():
    p = f"{F}/assets/npcs/{k}/sprite_1x/s/f00.png"
    if os.path.exists(p):
        im = Image.open(p).convert("RGBA")
        draws.append(((v["x"] - X0) * T + 20 - 48, (v["y"] - Y0) * T + 30 - 118, v["y"], im))
crypt = Image.open(F + "/ref/skeleton_crypt_512.png").convert("RGBA")
cw = 11 * T; crypt = crypt.resize((cw, int(crypt.height * cw / crypt.width)), Image.LANCZOS)
ex, ey = L.DUNGEON["new"]["x"], L.DUNGEON["new"]["y"]
draws.append(((ex - X0) * T + 20 - cw // 2, int((ey - Y0 - 10.5) * T), ey, crypt))
for bx, by, sy, im in sorted(draws, key=lambda t: t[2]):
    img.alpha_composite(im, (int(bx), int(by))) if bx >= 0 and by >= 0 else img.paste(im, (int(bx), int(by)), im)
# old positions (dashed) + labels
def dashed(r, col):
    x0, y0, x1, y1 = [(r[0] - X0) * T, (r[1] - Y0) * T, (r[2] - X0 + 1) * T, (r[3] - Y0 + 1) * T]
    for x in range(x0, x1, 24):
        d.line((x, y0, min(x + 12, x1), y0), fill=col, width=4); d.line((x, y1, min(x + 12, x1), y1), fill=col, width=4)
    for y in range(y0, y1, 24):
        d.line((x0, y, x0, min(y + 12, y1)), fill=col, width=4); d.line((x1, y, x1, min(y + 12, y1)), fill=col, width=4)
dashed(L.FAIRY_ZONE, (255, 220, 120))
dashed(L.NEW_MINE, (255, 160, 80))
o = L.DUNGEON["old"]; dashed((o["x"] - 1, o["y"] - 1, o["x"] + 1, o["y"]), (255, 90, 90))
def label(x, y, text, f=font, col=(255, 255, 255)):
    px, py = (x - X0) * T, (y - Y0) * T
    bb = d.textbbox((px, py), text, font=f)
    d.rectangle((bb[0] - 8, bb[1] - 6, bb[2] + 8, bb[3] + 6), fill=(0, 0, 0, 170))
    d.text((px, py), text, font=f, fill=col)
label(14, 36, "Starting village (north)")
label(2, 56.2, "Moonpetal Glade: Fairy Village (1,56)-(40,88)", col=(255, 225, 140))
label(44.5, 64.5, "Dungeon entrance (new) (46,80)", small, (255, 200, 200))
label(47.5, 71.2, "old (46,71)", small, (255, 120, 120))
label(30, 99.2, "Mine / quarry (new) (31,90)-(43,98)", small, (255, 190, 120))
label(2, 100.5, "King's Row player houses", small)
img = img.convert("RGB")
img.save(F + "/previews/village_layout_full.png", optimize=True)
s = 1600 / img.height
img.resize((int(img.width * s), 1600), Image.LANCZOS).save(F + "/previews/village_layout.png", optimize=True)
print("layout ok", img.size)
