"""Composite painted flames onto the Blender sconce -> textures/torch_sconce_strip.png (4 x 96x160 RGBA)."""
import numpy as np, os
from PIL import Image
D = os.path.dirname(os.path.abspath(__file__)) + "/.."
sc = np.asarray(Image.open(f"{D}/work/p_torch_0.png").convert("RGBA")).astype(float) / 255
H, W = sc.shape[:2]  # 320 x 192
rng = np.random.default_rng(7)
def vnoise(shape, cells, seed):
    r = np.random.default_rng(seed); g = r.random((cells[0] + 3, cells[1] + 3))
    y = np.linspace(0, cells[0], shape[0], endpoint=False); x = np.linspace(0, cells[1], shape[1], endpoint=False)
    yi, xi = y.astype(int), x.astype(int); fy, fx = (y - yi)[:, None], (x - xi)[None]
    fy = fy * fy * (3 - 2 * fy); fx = fx * fx * (3 - 2 * fx)
    a = g[yi][:, xi]; b = g[yi][:, xi + 1]; c = g[yi + 1][:, xi]; d = g[yi + 1][:, xi + 1]
    return (a * (1 - fx) + b * fx) * (1 - fy) + (c * (1 - fx) + d * fx) * fy
# tall scrolling noise; each frame samples a window lower down => flames rise
big = sum(vnoise((H * 3, W), (6 * 2 ** o * 3, 4 * 2 ** o), 11 + o) / 2 ** o for o in range(4)) / 1.875
base_y, top_y, cx = 150.0, 22.0, 96.0  # flame root sits inside the cup
yy, xx = np.mgrid[0:H, 0:W].astype(float)
ramp = [(0.0, (0.35, 0.02, 0.0)), (0.35, (0.85, 0.18, 0.02)), (0.6, (1.0, 0.48, 0.06)), (0.82, (1.0, 0.78, 0.30)), (1.0, (1.0, 0.95, 0.75))]
def colour(t):
    out = np.zeros(t.shape + (3,))
    for (p0, c0), (p1, c1) in zip(ramp, ramp[1:]):
        k = np.clip((t - p0) / (p1 - p0), 0, 1)[..., None]
        m = ((t >= p0) & (t <= p1))[..., None]
        out = np.where(m, np.array(c0) * (1 - k) + np.array(c1) * k, out)
    return out
frames = []
for f in range(4):
    off = int(f * H * 0.18)
    n = big[H * 2 - off - H:H * 2 - off] if True else None
    n2 = big[H - off // 2 - 40:H - off // 2 - 40 + H]
    v = np.clip((base_y - yy) / (base_y - top_y), -0.2, 1.3)       # 0 at root, 1 at tip
    sway = (n2 - 0.5) * 34 * np.clip(v, 0, 1) ** 1.2 + 3 * np.sin(f * 1.7) * v
    width = 33 * np.clip(np.sin(np.clip(v, 0, 1) * np.pi * 0.92 + 0.25), 0, 1) * (1 - np.clip(v, 0, 1)) ** 0.55
    d = np.abs(xx - cx - sway) / np.maximum(width, 1e-3)
    dens = np.clip(1 - d, 0, 1) * (0.55 + 0.9 * n) - 0.18 * np.clip(v, 0, 1) - 0.25 * np.clip(v - 0.75, 0, 1) * 4 * (1 - n)
    dens = np.where(v < 0, dens * np.clip(1 + v * 8, 0, 1), dens)
    dens = np.clip(dens, 0, 1)
    t = np.clip(dens * 1.25 - 0.05 * v, 0, 1)
    col = colour(t)
    a = np.clip(dens * 2.2, 0, 1)
    # soft glow halo
    gl = np.exp(-(((xx - cx) / 40) ** 2 + ((yy - 95) / 62) ** 2)) * 0.22
    fr = sc.copy()
    # glow behind everything, flame over the sconce except in front of the cup lip
    ga = gl * (1 - fr[..., 3])
    fr[..., :3] = fr[..., :3] * (1 - ga[..., None]) + np.array([1.0, 0.45, 0.1]) * ga[..., None]
    fr[..., 3] = fr[..., 3] + ga
    lip = (yy > 136) & (sc[..., 3] > 0.5)
    a = np.where(lip, a * 0.15, a)
    fr[..., :3] = fr[..., :3] * (1 - a[..., None]) + col * a[..., None]
    fr[..., 3] = np.clip(fr[..., 3] * (1 - a) + a, 0, 1)
    # firelight on the iron, flickering per frame
    lit = np.exp(-(((xx - cx) / 60) ** 2 + ((yy - 150) / 50) ** 2)) * (0.35 + 0.1 * np.sin(f * 2.1))
    fr[..., :3] = np.clip(fr[..., :3] + lit[..., None] * np.array([0.5, 0.2, 0.05]) * sc[..., 3:4] * (1 - a[..., None]), 0, 1)
    im = Image.fromarray((fr * 255).astype(np.uint8), "RGBA").resize((96, 160), Image.LANCZOS)
    frames.append(im)
strip = Image.new("RGBA", (384, 160))
for i, im in enumerate(frames):
    strip.paste(im, (i * 96, 0))
strip.save(f"{D}/textures/torch_sconce_strip.png", optimize=True)
print("torch ok")
