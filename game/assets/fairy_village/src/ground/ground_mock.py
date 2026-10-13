"""In-context mock of the fairy village ground, built from the real planned grid (ref/grid_fairy.pkl).

Implements exactly the draw rules of GROUND_DETAIL_CURSOR_PROMPT.md so the preview = what Cursor should get:
  1. terrain: inside ZONES['fairy_village'] GRASS/PATH/STONE -> fairy_moss / petal_path / moonstone_paving,
     variant = 1 + vhash(x, y) % 5 (paving: (y%4)*4 + x%4 + 1, 4x4 macro); WALL tiles listed in json/ground_under.json draw their ground instead
     of the dark wall tile. Outside the zone: a PIL port of the game's draw_grass / draw_path.
  2. edge overlays on PATH / STONE tiles (8-bit mask of GRASS-like neighbours, reduced to 47).
  3. contact skirts (tree hall roots/moss, fountain damp rims) - after terrain, before sprites.
  4. ground decals from json/ground_decals.json.
  5. buildings / fountains / NPCs / crypt y-sorted (as src/tools/layout_mock.py).
python3 src/ground/ground_mock.py   -> previews/ground_village_mock.png + previews/ground_before_after.png
"""
import json, os, sys, pickle, math
import numpy as np
from PIL import Image, ImageDraw, ImageFont
sys.path.insert(0, os.path.dirname(__file__)); sys.path.insert(0, "/workspace/fairy_village/src")
from gcommon import F
import layout as L

G = pickle.load(open(F + "/ref/grid_fairy.pkl", "rb"))
GU = {tuple(map(int, k.split(","))): v for k, v in json.load(open(F + "/json/ground_under.json"))["tiles"].items()}
DEC = json.load(open(F + "/json/ground_decals.json"))
CON = json.load(open(F + "/json/contact_decals.json"))["contact_decals"]
ZONE = L.FAIRY_ZONE
GRASS, PATH, STONE, WALL = 0, 5, 13, 4
SETNAME = {GRASS: "fairy_moss", PATH: "petal_path", STONE: "moonstone_paving"}
SCALE_OF = {40: "1x", 80: "2x", 160: "4x"}
BITS = [(0, -1, 1), (1, -1, 2), (1, 0, 4), (1, 1, 8), (0, 1, 16), (-1, 1, 32), (-1, 0, 64), (-1, -1, 128)]
FONT = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"


def vhash(x, y):
    h = (x * 73856093) ^ (y * 19349663)
    h = (h ^ (h >> 13)) * 1274126177 & 0xFFFFFFFF
    return (h >> 8) % 5


def seeded(x, y, salt=0):        # rs_style.seeded
    n = (int(x) * 92821 + int(y) * 68917 + int(salt) * 2311) & 0xFFFFFFFF
    n = (n ^ (n >> 13)) * 1274126177 & 0xFFFFFFFF
    return (n % 10000) / 10000.0


def shade(c, d):
    return tuple(max(0, min(255, v + d)) for v in c)


def default_tile(tid, x, y, T):
    """PIL approximation of procedural_sprites_finished.draw_grass / draw_path (outside the fairy zone)."""
    im = Image.new("RGB", (T, T)); d = ImageDraw.Draw(im)
    if tid in (PATH,):
        base, dark, light = (128, 100, 68), (100, 76, 50), (152, 122, 86)
        fill = shade(base, int((seeded(x, y, 2) - 0.5) * 14)); d.rectangle((0, 0, T, T), fill=fill)
        if seeded(x, y, 4) < 0.6:
            d.ellipse((T * .15, T * .2, T * .65, T * .6), fill=shade(fill, 8))
        if seeded(x, y, 3) < 0.65:
            d.line((0, 1, T, 1), fill=dark)
        for i in range(5):
            px, py = int(seeded(x, y, 30 + i) * T), int(seeded(x, y, 40 + i) * T)
            r = 1 if i < 3 else 2
            d.ellipse((px - r, py - r, px + r, py + r), fill=light if i % 2 else dark)
        return im
    if tid in (GRASS, 1, 7, 9) or tid > 20:
        base, dark, light = (52, 98, 48), (38, 74, 36), (72, 118, 58)
        fill = shade(base, int((seeded(x // 2, y // 2, 1) - 0.5) * 6 + (seeded(x, y, 1) - 0.5) * 4)); d.rectangle((0, 0, T, T), fill=fill)
        for i in range(3):
            if seeded(x, y, 10 + i) < 0.75:
                wash = shade(fill, 6 if i % 2 == 0 else -7)
                ox = int(T * (-0.15 + 0.9 * seeded(x, y, 20 + i))); oy = int(T * (-0.15 + 0.9 * seeded(x, y, 30 + i)))
                rw = max(5, int(T * (0.4 + 0.35 * seeded(x, y, 40 + i)))); rh = max(4, int(T * (0.35 + 0.3 * seeded(x, y, 50 + i))))
                d.ellipse((ox, oy, ox + rw, oy + rh), fill=wash)
        if seeded(x, y, 40) < 0.48:
            tx, ty = int(T * seeded(x, y, 41)), int(T * (0.45 + 0.4 * seeded(x, y, 42)))
            for j, dx in enumerate((-3, -1, 1, 3)):
                d.line((tx + dx, ty + 4, tx + dx // 2, ty - 5), fill=shade(light, -8) if j % 2 == 0 else shade(dark, -6))
        return im
    col = {4: (86, 82, 78), 6: (122, 106, 88), 3: (150, 100, 60), 8: (128, 118, 120), 13: (128, 126, 132), 2: (60, 110, 170)}.get(tid, (200, 0, 200))
    d.rectangle((0, 0, T, T), fill=col)
    return im


class Assets:
    def __init__(self, T, old=False):
        self.T = T; self.old = old; self.c = {}

    def tile(self, setname, v):
        k = ("t", setname, v)
        if k not in self.c:
            if self.old:
                p = f"{F}/work/old_tiles/{setname}_v{(v % 3) + 1}_{self.T}.png"
            else:
                p = f"{F}/assets/tiles/{setname}_v{v + 1}_{self.T}.png"
            self.c[k] = Image.open(p).convert("RGBA")
        return self.c[k]

    def edge(self, fam, m):
        k = ("e", fam, m)
        if k not in self.c:
            self.c[k] = Image.open(f"{F}/assets/tiles/edges/{fam}_{m:03d}_{self.T}.png").convert("RGBA")
        return self.c[k]

    def decal(self, did):
        k = ("d", did)
        if k not in self.c:
            meta = json.load(open(f"{F}/assets/decals/{did}/meta.json"))
            s = SCALE_OF[self.T]
            self.c[k] = (Image.open(f"{F}/assets/decals/{did}/{did}_{s}.png").convert("RGBA"), meta["origin_px"][s])
        return self.c[k]


def tile_variant(setname, x, y, old=False):
    """0-based variant index. moss/path: hash of (x, y) over 5 variants.  paving: position in the seamless
    4x4 macro (v = (y % 4) * 4 + (x % 4) + 1), so joints run across tile borders."""
    if setname == "moonstone_paving" and not old and os.path.exists(f"{F}/assets/tiles/moonstone_paving_v16_40.png"):
        return (y % 4) * 4 + (x % 4)
    return vhash(x, y) % 5


def in_zone(x, y):
    return ZONE[0] <= x <= ZONE[2] and ZONE[1] <= y <= ZONE[3]


def ground_kind(x, y):
    t = G[y][x]
    if t == WALL and (x, y) in GU:
        return {"GRASS": GRASS, "STONE": STONE, "PATH": PATH}[GU[(x, y)]]
    return t


def grassy(x, y):
    if not (0 <= y < len(G) and 0 <= x < len(G[0])):
        return False
    return ground_kind(x, y) in (GRASS, 1, 7)


def reduce_mask(m):
    for d, a, b in ((2, 1, 4), (8, 16, 4), (32, 16, 64), (128, 1, 64)):
        if m & d and (m & a or m & b):
            m &= ~d
    return m


def render(X0, Y0, X1, Y1, T, mode="new", labels=False):
    """mode: 'new' (pack), 'old' (previous tiles, dark WALL blocks, no edges / decals / skirts)."""
    A = Assets(T, old=(mode == "old"))
    W, H = (X1 - X0) * T, (Y1 - Y0) * T
    img = Image.new("RGBA", (W, H), (0, 0, 0, 255))
    for y in range(Y0, Y1):
        for x in range(X0, X1):
            px, py = (x - X0) * T, (y - Y0) * T
            t = G[y][x]
            if in_zone(x, y):
                k = ground_kind(x, y) if mode == "new" else t
                if k in SETNAME:
                    img.paste(A.tile(SETNAME[k], tile_variant(SETNAME[k], x, y, A.old)), (px, py))
                    if mode == "new" and k in (PATH, STONE) and t != WALL:
                        m = 0
                        for dx, dy, b in BITS:
                            if grassy(x + dx, y + dy):
                                m |= b
                        m = reduce_mask(m)
                        if m:
                            fam = "path_grass_edge" if k == PATH else "paving_grass_edge"
                            img.alpha_composite(A.edge(fam, m), (px, py))
                elif t == WALL:      # the game's fallback dark wall tile (the bug in David's screenshots)
                    d = ImageDraw.Draw(img); d.rectangle((px, py, px + T - 1, py + T - 1), fill=(35, 33, 38), outline=(22, 20, 24))
                else:
                    img.paste(default_tile(t, x, y, T), (px, py))
            else:
                img.paste(default_tile(t, x, y, T), (px, py))
    def blit(im, bx, by):
        tmp = Image.new("RGBA", img.size, (0, 0, 0, 0)); tmp.paste(im, (int(bx), int(by)), im)
        img.alpha_composite(tmp)
    s = SCALE_OF[T]
    if mode == "new":
        for c in CON:
            im, (ox, oy) = A.decal(c["id"])
            blit(im, (c["anchor_tile"][0] - X0) * T - ox, (c["anchor_tile"][1] - Y0) * T - oy)
        for e in DEC["decals"]:
            im, (ox, oy) = A.decal(e["id"])
            blit(im, (e["x"] - X0) * T - ox, (e["y"] - Y0) * T - oy)
    draws = []
    k = T // 40
    for key, kind, spec in [(a, "buildings", b) for a, b in L.BUILDINGS.items()] + [(a, "fountains", b) for a, b in L.FOUNTAINS.items()]:
        d0 = f"{F}/assets/{kind}/{key}"; meta = json.load(open(f"{d0}/meta.json"))
        p = f"{d0}/{meta['files'][s]}" if kind == "buildings" else f"{d0}/frames_{s}/f00.png"
        im = Image.open(p).convert("RGBA"); ox, oy = meta["origin_px"][s]; fp = spec["footprint"]
        draws.append(((fp[0] - X0) * T - ox, (fp[1] - Y0) * T - oy, fp[3], im))
    for key, v in L.NPCS.items():
        p = f"{F}/assets/npcs/{key}/sprite_{s}/s/f00.png"
        if os.path.exists(p):
            im = Image.open(p).convert("RGBA")
            draws.append(((v["x"] - X0) * T + T // 2 - im.width // 2, (v["y"] - Y0) * T + int(T * 0.75) - int(118 * k), v["y"], im))
    crypt = Image.open(F + "/ref/skeleton_crypt_512.png").convert("RGBA")
    cw = 11 * T; crypt = crypt.resize((cw, int(crypt.height * cw / crypt.width)), Image.LANCZOS)
    ex, ey = L.DUNGEON["new"]["x"], L.DUNGEON["new"]["y"]
    draws.append(((ex - X0) * T + T // 2 - cw // 2, int((ey - Y0 - 10.5) * T), ey, crypt))
    for bx, by, sy, im in sorted(draws, key=lambda t: t[2]):
        blit(im, bx, by)
    return img.convert("RGB")


def label(img, text, xy=(12, 10), size=22, col=(255, 235, 170)):
    d = ImageDraw.Draw(img); f = ImageFont.truetype(FONT, size)
    bb = d.textbbox(xy, text, font=f)
    d.rectangle((bb[0] - 8, bb[1] - 5, bb[2] + 8, bb[3] + 5), fill=(0, 0, 0))
    d.text(xy, text, font=f, fill=col)


def main():
    # full village mock (1x = real game scale)
    full = render(0, 53, 50, 92, 40, "new")
    full.save(F + "/previews/ground_village_mock.png", optimize=True)
    # before / after
    ss = 64 / 80
    def crop2x(x0, y0, w_t, h_t):
        X0, Y0 = int(math.floor(x0)), int(math.floor(y0))
        im = render(X0, Y0, X0 + int(math.ceil(w_t)) + 2, Y0 + int(math.ceil(h_t)) + 2, 80, "new")
        ox, oy = (x0 - X0) * 80, (y0 - Y0) * 80
        return im.crop((int(ox), int(oy), int(ox + w_t * 80), int(oy + h_t * 80)))
    rows = []
    for shot, (x0, y0), title in (("ingame_fountain_dark_blocks.png", (24.0, 59.83), "Moonstone Fountain plaza"),
                                  ("ingame_treehall_dark_blocks.png", (3.27, 77.7), "Queen's Tree-Hall + South Walk")):
        before = Image.open(F + "/ref/" + shot).convert("RGB")
        w_t, h_t = before.width / 64, before.height / 64
        after = crop2x(x0, y0, w_t, h_t).resize(before.size, Image.LANCZOS)
        rows.append((title, before, after))
    # village-wide crop, old pack vs new pack, at game scale
    bx = (14, 56, 41, 76)
    b_old = render(*bx, 40, "old"); b_new = render(*bx, 40, "new")
    rows.append(("Village centre at game scale (1x, 40 px/tile)", b_old, b_new))
    Wd = max(b.width + a.width for _, b, a in rows) + 60
    Ht = sum(max(b.height, a.height) + 70 for _, b, a in rows) + 70
    sheet = Image.new("RGB", (Wd, Ht), (18, 18, 24)); d = ImageDraw.Draw(sheet)
    f = ImageFont.truetype(FONT, 26); fs = ImageFont.truetype(FONT, 20)
    d.text((20, 18), "Fairy village ground: BEFORE (left)  vs  AFTER (right)", font=f, fill=(255, 235, 170))
    y = 70
    for title, b, a in rows:
        d.text((20, y), title, font=fs, fill=(255, 255, 255))
        sheet.paste(b, (20, y + 30)); sheet.paste(a, (40 + b.width, y + 30))
        lb = "before: in-game screenshot (dark WALL blocks, plain gravel path)" if "Village" not in title else "before: previous tiles + dark WALL fallback"
        label(sheet, lb, (28, y + 38), 15, (255, 170, 170))
        label(sheet, "after: new tiles, ground_under, edges, skirts, decals", (48 + b.width, y + 38), 15, (170, 255, 190))
        y += max(b.height, a.height) + 70
    sheet.save(F + "/previews/ground_before_after.png", optimize=True)
    print("mock ok", full.size, sheet.size)


if __name__ == "__main__":
    main()
