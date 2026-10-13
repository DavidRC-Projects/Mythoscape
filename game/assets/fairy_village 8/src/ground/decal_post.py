"""Decal post: 4x Blender render -> assets/decals/<id>/<id>_{4x,2x,1x}.png + meta.json.
Adds the soft painted layers Blender can't put in a transparent PNG: lantern / glow-stone light pools,
the tree-hall soil+moss stain, and the damp rim stain round the fountains (all under the 3D render).
python3 src/ground/decal_post.py [names...]
"""
import sys, os, json, math
import numpy as np
from PIL import Image
sys.path.insert(0, os.path.dirname(__file__))
from gcommon import F, WORK, pnoise, fbm, smooth

OUT = F + "/assets/decals"
PPT = 160
M_PER_TILE = 40.0 / 26.9


def under(rgba, layer):
    """composite `layer` (H,W,4 float 0..1, straight alpha) UNDER rgba."""
    a = rgba[..., 3:4]; b = layer[..., 3:4]
    out_a = a + b * (1 - a)
    out_rgb = (rgba[..., :3] * a + layer[..., :3] * b * (1 - a)) / np.maximum(out_a, 1e-5)
    return np.concatenate([out_rgb, out_a], -1)


def tile_coords(meta, shape):
    H, W = shape[:2]
    ox, oy = meta["origin_px"]
    xs = (np.arange(W) + 0.5 - ox) / PPT; ys = (np.arange(H) + 0.5 - oy) / PPT
    return np.meshgrid(xs, ys)     # tile units from footprint NW corner, y south


def noise_like(shape, seed, cells=(6, 12, 24)):
    rng = np.random.default_rng(seed)
    n = max(shape[:2])
    f = fbm(n, rng, cells, (0.5, 0.3, 0.2))
    return f[:shape[0], :shape[1]]


def pool(meta, shape, cx, cy, rad, col, amax):
    U, V = tile_coords(meta, shape)
    d = np.hypot(U - cx, (V - cy) * 1.0) / rad
    a = amax * np.clip(1 - d, 0, 1) ** 2
    lay = np.zeros(shape[:2] + (4,)); lay[..., :3] = np.array(col) / 255; lay[..., 3] = a
    return lay


def tree_stain(meta, shape):
    U, V = tile_coords(meta, shape)
    tx, ty = 4.5, (9 * M_PER_TILE - 0.9 - 2.35) / M_PER_TILE
    r = np.hypot(U - tx, V - ty)
    n = noise_like(shape, 5)
    ang = np.degrees(np.arctan2(-(V - ty), U - tx)) % 360          # 270 = south (door)
    door = 1 - 0.75 * smooth(0, 1, 1 - np.abs(ang - 270) / 30)
    a = (1 - smooth(3.2, 5.0 + 0.6 * n, r)) * 0.55 * door
    col = np.zeros(shape[:2] + (3,))
    moss = np.array((44, 70, 32)) / 255; soil = np.array((58, 44, 30)) / 255
    t = smooth(0.35, 0.65, n)[..., None]
    col = soil * (1 - t) + moss * t
    return np.concatenate([col, a[..., None]], -1)


def rim_stain(meta, shape, cx, cy, R_m, octagon):
    U, V = tile_coords(meta, shape)
    x, y = U - cx, -(V - cy)
    R = R_m / M_PER_TILE
    if octagon:
        d = np.max(np.stack([x * math.cos(k * math.pi / 4) + y * math.sin(k * math.pi / 4) for k in range(8)]), 0)
        r0 = R * math.cos(math.pi / 8)
    else:
        d = np.hypot(x, y); r0 = R
    n = noise_like(shape, 9, (8, 16, 32))
    s = d - r0
    a = smooth(-0.15, 0.0, s) * (1 - smooth(0.05, 0.55 + 0.25 * n, s)) * 0.42
    col = np.zeros(shape[:2] + (3,)); col[:] = np.array((46, 58, 76)) / 255
    lay = np.concatenate([col, a[..., None]], -1)
    # a few wet glints just outside the rim
    rng = np.random.default_rng(3)
    g = np.zeros(shape[:2])
    for k in range(40):
        ang = rng.uniform(0, 6.283); rr = r0 + rng.uniform(0.05, 0.35)
        gx, gy = cx + rr * math.cos(ang), cy - rr * math.sin(ang)
        g = np.maximum(g, np.clip(1 - np.hypot(U - gx, V - gy) / rng.uniform(0.03, 0.06), 0, 1))
    glint = np.zeros(shape[:2] + (4,)); glint[..., :3] = np.array((210, 228, 255)) / 255; glint[..., 3] = g * 0.35
    return lay, glint


def over(a, b):
    """b over a (straight alpha)."""
    return under(b, a)


EXTRA = {
    "fairy_lantern": lambda m, s, im: under(im, pool(m, s, 0.5 + 0.16 / M_PER_TILE, 0.55, 0.65, (255, 206, 130), 0.32)),
    "glow_stones": lambda m, s, im: under(im, pool(m, s, 0.5, 0.5, 0.55, (150, 200, 255), 0.25)),
    "mushroom_ring": lambda m, s, im: under(im, pool(m, s, 1.0, 1.0, 1.1, (40, 70, 34), 0.18)),
    "queens_tree_hall_skirt": lambda m, s, im: under(im, tree_stain(m, s)),
}


def fountain(cx, R, octa):
    def f(m, s, im):
        lay, glint = rim_stain(m, s, cx, cx, R, octa)
        return under(im, over(lay, glint))
    return f


EXTRA["moonstone_fountain_rim"] = fountain(2.5, 3.55, True)
EXTRA["lily_fountain_rim"] = fountain(1.5, 2.15, False)


def run(name):
    meta = json.load(open(f"{WORK}/decal_{name}_meta.json"))
    im = np.asarray(Image.open(f"{WORK}/decal_{name}_4x.png").convert("RGBA"), float) / 255
    if name in EXTRA:
        im = EXTRA[name](meta, im.shape, im)
    img = Image.fromarray(np.clip(im * 255 + 0.5, 0, 255).astype(np.uint8), "RGBA")
    d = f"{OUT}/{name}"; os.makedirs(d, exist_ok=True)
    W, H = img.size
    files = {}
    for s, k in (("4x", 1), ("2x", 2), ("1x", 4)):
        out = img if k == 1 else img.convert("RGBa").resize((W // k, H // k), Image.LANCZOS).convert("RGBA")
        out.save(f"{d}/{name}_{s}.png", optimize=True); files[s] = f"{name}_{s}.png"
    ox, oy = meta["origin_px"]
    m = {"id": name, "footprint_tiles": meta["footprint_tiles"], "tile_px": {"1x": 40, "2x": 80, "4x": 160},
         "origin_px": {"4x": [ox, oy], "2x": [ox // 2, oy // 2], "1x": [ox // 4, oy // 4]},
         "origin_note": "pixel of the footprint's NW corner; blit at (x0*TILE - origin.x, y0*TILE - origin.y)",
         "canvas_tiles": meta["tiles"], "files": files, "blocking": False,
         "projection": "oblique el 32 deg, (1, 1/sin32, 1.4) model scale - same as the buildings pack"}
    json.dump(m, open(f"{d}/meta.json", "w"), indent=1)
    print("decal", name, img.size)


if __name__ == "__main__":
    names = sys.argv[1:] or [n[6:-7] for n in sorted(os.listdir(WORK)) if n.startswith("decal_") and n.endswith("_4x.png")]
    for n in names:
        run(n)
