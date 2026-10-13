"""Step 3: turn Blender renders into game tiles + autotile edge overlays + seam tests.

* band unification: every variant takes v1's pixels in the outer border band (feathered), so any
  variant sits seamlessly next to any other (renders are already periodic on their own).
* downsample 640 -> 160/80/40 with an area (box) filter on a wrapped 3x3 copy; light unsharp at 80/40.
* edges: 47-mask "blob" overlays (grass drawn ON TOP of a path / paving tile). Their opaque border
  pixels are copied from fairy_moss_v1 at the same size, so they match whatever grass tile is next door.
Run: python3 src/ground/post.py [tiles] [edges] [seams]
"""
import sys, os, json
import numpy as np
from PIL import Image, ImageFilter
sys.path.insert(0, os.path.dirname(__file__))
from gcommon import *

SETS = {"fairy_moss": (BAND_IN, BAND_OUT), "petal_path": (BAND_IN, BAND_OUT), "moonstone_paving": (0.0015, 0.004)}
NV = 5
SIZES = (160, 80, 40)
EDGES = F + "/assets/tiles/edges"
BITS = {"N": 1, "NE": 2, "E": 4, "SE": 8, "S": 16, "SW": 32, "W": 64, "NW": 128}


def wrap_resize(img, px, sharpen=True):
    """resize a periodic tile using a 3x3 wrapped copy (no clamped edges), box filter, then crop."""
    a = np.asarray(img)
    big = Image.fromarray(np.tile(a, (3, 3, 1)))
    small = big.resize((px * 3, px * 3), Image.BOX)
    if sharpen and px <= 80:
        small = small.filter(ImageFilter.UnsharpMask(radius=0.8 if px == 40 else 1.0, percent=55 if px == 40 else 40, threshold=0))
    return small.crop((px, px, 2 * px, 2 * px))


def load_render(name):
    return np.asarray(Image.open(f"{WORK}/{name}_render.png").convert("RGB"), float)


MACRO = {"moonstone_paving": 4}
GRADE = {"moonstone_paving": (0.86, 0.87, 0.91)}      # sets cut from one seamless M x M macro texture (no band unification)


def nvar(s):
    return MACRO[s] ** 2 if s in MACRO else NV


def tiles_macro(s, M):
    rows = [np.concatenate([load_render(f"{s}_v{j * M + i + 1}") for i in range(M)], 1) for j in range(M)]
    # grade: a touch darker / cooler than the render so the cream fountain stone and white plinths read on it
    arr = np.concatenate(rows, 0) * np.array(GRADE.get(s, (1, 1, 1)))
    # tonal variation across the plaza (periodic over the macro): darker weathered patches + cool/warm drift
    rng = np.random.default_rng(4242); NMs = N * M
    lf = fbm(NMs, rng, (2 * M, 3 * M, 6 * M), (0.5, 0.3, 0.2))
    warm = fbm(NMs, rng, (2 * M, 4 * M), (0.6, 0.4))
    arr = arr * (0.80 + 0.30 * lf)[..., None]
    arr = arr * (1 + np.stack([0.05, 0.01, -0.05]) * (warm - 0.5)[..., None] * 2)
    mosaic = Image.fromarray(np.clip(arr + 0.5, 0, 255).astype(np.uint8))
    for j in range(M):
        for i in range(M):
            mosaic.crop((i * N, j * N, (i + 1) * N, (j + 1) * N)).save(f"{WORK}/{s}_v{j * M + i + 1}_final640.png")
    for px in SIZES:
        small = wrap_resize(mosaic, px * M)
        for j in range(M):
            for i in range(M):
                small.crop((i * px, j * px, (i + 1) * px, (j + 1) * px)).save(f"{TILES}/{s}_v{j * M + i + 1}_{px}.png", optimize=True)
    print("tiles", s, "(macro", M, "x", M, ")")


def tiles():
    for s, (b0, b1) in SETS.items():
        if s in MACRO:
            tiles_macro(s, MACRO[s]); continue
        ref = load_render(f"{s}_v1")
        # make v1 strictly periodic at its very edge (kills render-noise steps): average opposite edge rows
        for k in range(2):
            avg = (ref[k, :] + ref[N - 1 - k, :]) / 2 if False else None
        w = smooth(b0, b1, border_dist())[..., None]
        for v in range(1, NV + 1):
            r = load_render(f"{s}_v{v}")
            out = ref * (1 - w) + r * w
            im = Image.fromarray(np.clip(out + 0.5, 0, 255).astype(np.uint8))
            im.save(f"{WORK}/{s}_v{v}_final640.png")
            for px in SIZES:
                wrap_resize(im, px).save(f"{TILES}/{s}_v{v}_{px}.png", optimize=True)
        print("tiles", s)


# ------------------------------------------------------------------ autotile edges
def reduce_mask(m):
    for d, a, b in (("NE", "N", "E"), ("SE", "S", "E"), ("SW", "S", "W"), ("NW", "N", "W")):
        if m & BITS[d] and (m & BITS[a] or m & BITS[b]):
            m &= ~BITS[d]
    return m


ALL_MASKS = sorted({reduce_mask(m) for m in range(256)})
assert len(ALL_MASKS) == 47, len(ALL_MASKS)


def dist_field(m, X, Y):
    d = np.full(X.shape, 9.0)
    if m & 1: d = np.minimum(d, Y)
    if m & 16: d = np.minimum(d, 1 - Y)
    if m & 64: d = np.minimum(d, X)
    if m & 4: d = np.minimum(d, 1 - X)
    if m & 2: d = np.minimum(d, np.hypot(1 - X, Y))
    if m & 128: d = np.minimum(d, np.hypot(X, Y))
    if m & 8: d = np.minimum(d, np.hypot(1 - X, 1 - Y))
    if m & 32: d = np.minimum(d, np.hypot(X, 1 - Y))
    return np.maximum(d, 0)


FAM = {   # family: (base set, reach W, noise amp, shadow, moss stain)
    "path_grass_edge": ("petal_path", 0.46, 0.90, 0.42, 0.0),
    "paving_grass_edge": ("moonstone_paving", 0.36, 0.85, 0.38, 0.38),
}


def edge_layers(m, Wr, amp, rng_seed=77):
    rng = np.random.default_rng(rng_seed)
    n = 0.55 * fbm(N, rng, (4, 8), (0.6, 0.4)) + 0.45 * fbm(N, rng, (16, 32, 64, 128), (0.35, 0.3, 0.2, 0.15))
    X, Y = grid()
    g = 1 - dist_field(m, X, Y) / Wr + amp * (n - 0.5)
    a = smooth(0.45, 0.55, g)
    sh = int(0.016 * N)
    Xs, Ys = X - 0.016, Y - 0.016
    gs = 1 - dist_field(m, Xs, Ys) / Wr + amp * (np.roll(n, (sh, sh), (0, 1)) - 0.5)
    s = np.clip(smooth(0.40, 0.55, gs) - a, 0, 1)
    stain = smooth(0.20, 0.47, g) * (1 - a)
    return a, s, stain


def box_down(arr, px):
    return np.asarray(Image.fromarray((np.clip(arr, 0, 1) * 65535).astype(np.uint16)).resize((px, px), Image.BOX), float) / 65535


def edges():
    os.makedirs(EDGES, exist_ok=True)
    grass = {px: np.asarray(Image.open(f"{TILES}/fairy_moss_v1_{px}.png").convert("RGB"), float) for px in SIZES}
    index = {}
    for fam, (base, Wr, amp, shadow, stain_k) in FAM.items():
        for m in ALL_MASKS:
            if m == 0:
                continue
            a, s, st = edge_layers(m, Wr, amp)
            for px in SIZES:
                A = box_down(a, px)[..., None]; S = box_down(s, px)[..., None] * shadow; M = box_down(st, px)[..., None] * stain_k
                # composite (premultiplied): moss stain, then contact shadow, then grass on top
                moss = np.array((70, 108, 54), float)
                rgb = moss * M; al = M
                rgb = rgb * (1 - S); al = S + al * (1 - S)          # black shadow over
                rgb = grass[px] * A + rgb * (1 - A); al = A + al * (1 - A)
                out = np.zeros((px, px, 4))
                out[..., :3] = np.where(al > 1e-4, rgb / np.maximum(al, 1e-4), 0)
                out[..., 3] = al[..., 0] * 255
                Image.fromarray(np.clip(out + 0.5, 0, 255).astype(np.uint8), "RGBA").save(f"{EDGES}/{fam}_{m:03d}_{px}.png", optimize=True)
            index.setdefault(fam, []).append(m)
        print("edges", fam)
    json.dump({"bits": BITS, "masks": ALL_MASKS[1:], "families": FAM}, open(f"{WORK}/edges_index.json", "w"))


# ------------------------------------------------------------------ seam test sheet
def vhash(x, y, n=NV):
    h = (x * 73856093) ^ (y * 19349663)
    h = (h ^ (h >> 13)) * 1274126177 & 0xFFFFFFFF
    return (h >> 8) % n


def seams():
    from PIL import ImageDraw, ImageFont
    font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 18)
    small = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 14)
    rows = []
    report = {}
    for s in SETS:
        panels = []
        for px, mode in ((40, "mixed"), (40, "same"), (80, "mixed")):
            t = {v: Image.open(f"{TILES}/{s}_v{v}_{px}.png").convert("RGB") for v in range(1, nvar(s) + 1)}
            g = Image.new("RGB", (6 * px, 6 * px))
            for x in range(6):
                for y in range(6):
                    if s in MACRO:
                        M = MACRO[s]; X_, Y_ = x + 3, y + 7
                        v = (Y_ % M) * M + (X_ % M) + 1 if mode == "mixed" else ((y % M) * M + (x % M) + 1)
                    else:
                        v = 1 + vhash(x + 3, y + 7) if mode == "mixed" else 1
                    g.paste(t[v], (x * px, y * px))
            arr = np.asarray(g, float)
            # seam metric: mean abs step across tile borders vs. inside tiles
            dx = np.abs(np.diff(arr, axis=1)).mean(axis=(0, 2)); cols = np.arange(len(dx))
            seam = dx[(cols % px) == px - 1].mean(); inner = dx[(cols % px) != px - 1].mean()
            report[f"{s}_{px}_{mode}"] = round(float(seam / inner), 3)
            panels.append(g.resize((480, 480), Image.NEAREST) if px == 40 else g)
        row = Image.new("RGB", (3 * 480 + 4 * 12, 480 + 40), (24, 24, 30))
        d = ImageDraw.Draw(row)
        labs = (("6x6 @40 px, 4x4 macro rule (y%4)*4+x%4+1 (shown 2x)", "6x6 @40 px, macro rule from origin (0,0) (shown 2x)", "6x6 @80 px, macro rule")
                if s in MACRO else ("6x6 @40 px, variants mixed by hash(x,y) (shown 2x)", "6x6 @40 px, v1 only (shown 2x)", "6x6 @80 px, variants mixed"))
        for k, (p, lab) in enumerate(zip(panels, labs)):
            row.paste(p, (12 + k * 492, 34))
            d.text((12 + k * 492, 10), lab, font=small, fill=(220, 220, 230))
        d.text((12, 0), "", font=font)
        rows.append((s, row))
    H = sum(r.height + 30 for _, r in rows) + 50
    sheet = Image.new("RGB", (rows[0][1].width, H), (16, 16, 20)); d = ImageDraw.Draw(sheet)
    d.text((12, 12), "Fairy ground: 6x6 seam tests (no grid lines drawn; any visible line would be a seam)", font=font, fill=(255, 230, 160))
    y = 50
    for s, r in rows:
        d.text((12, y), f"{s}  (seam/inner step ratio @40 mixed = {report[s + '_40_mixed']})", font=font, fill=(255, 255, 255))
        sheet.paste(r, (0, y + 24)); y += r.height + 30
    sheet.save(F + "/previews/ground_seam_tests.png", optimize=True)
    json.dump(report, open(f"{WORK}/seam_report.json", "w"), indent=1)
    print("seams", report)


if __name__ == "__main__":
    what = sys.argv[1:] or ["tiles", "edges", "seams"]
    if "tiles" in what: tiles()
    if "edges" in what: edges()
    if "seams" in what: seams()
