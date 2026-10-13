"""Lava v2: periodic Voronoi crust plates, molten seams with heat gradient, shaded crust relief."""
import os, sys, numpy as np
from PIL import Image
sys.path.insert(0, os.path.dirname(__file__))
from make_textures import fbm, blur, smooth, OUT
N = 512
r = np.random.default_rng(77)
pts = r.uniform(0, N, (34, 2))
yy, xx = np.mgrid[0:N, 0:N].astype(float)
wx = (fbm(N, 2.6, 1) - 0.5) * 34; wy = (fbm(N, 2.6, 2) - 0.5) * 34
X, Y = xx + wx, yy + wy
f1 = np.full((N, N), 1e9); f2 = np.full((N, N), 1e9); idx = np.zeros((N, N), int)
for i, (px, py) in enumerate(pts):
    for ox in (-N, 0, N):
        for oy in (-N, 0, N):
            d = np.hypot(X - px - ox, Y - py - oy)
            s = d < f1
            f2 = np.where(s, f1, np.minimum(f2, d)); idx = np.where(s, i, idx); f1 = np.where(s, d, f1)
edge = (f2 - f1) / 2
big = fbm(N, 2.2, 3); mid = fbm(N, 1.9, 4); fine = fbm(N, 1.5, 5)
seam_w = 3.0 + 7.0 * smooth(0.3, 0.8, big)          # seams widen in hot zones
molten = 1 - smooth(seam_w * 0.4, seam_w, edge)
# crust: domed plates, cracked, cooler in the middle
plate = smooth(0, 40, edge)
h = plate * (0.6 + 0.25 * mid + 0.08 * fine) - 0.12 * smooth(0.012, 0, np.abs(fbm(N, 2.0, 6) - 0.5)) * plate
gx = (np.roll(h, -1, 1) - np.roll(h, 1, 1)) * 6; gy = (np.roll(h, -1, 0) - np.roll(h, 1, 0)) * 6
nrm = np.sqrt(gx * gx + gy * gy + 1)
diff = np.clip((0.5 * gx + 0.6 * gy + 0.62) / nrm, 0, 1)
tint = r.uniform(0.75, 1.2, len(pts))[idx]
crust = np.stack([0.10 + 0.05 * mid, 0.07 + 0.03 * mid, 0.065 + 0.02 * mid], -1) * tint[..., None]
crust = crust * (0.45 + 0.9 * diff)[..., None] * (0.85 + 0.3 * fine)[..., None]
heat = blur(molten, 7)                                 # plates glow near their edges
crust = crust + np.clip(heat * 1.6 - 0.15, 0, 1)[..., None] * np.array([0.55, 0.14, 0.01]) * (1 - plate[..., None] * 0.6)
core = np.clip((1 - smooth(0, seam_w * 0.55, edge)) * (0.7 + 0.3 * fine) * (0.6 + 0.5 * big), 0, 1)
hot = np.stack([0.85 + 0.15 * core, 0.16 + 0.70 * core ** 1.3, 0.02 + 0.45 * core ** 3], -1)
rgb = crust * (1 - molten[..., None]) + hot * molten[..., None] * (0.8 + 0.2 * mid[..., None])
rgb = np.clip(rgb + blur(molten, 3)[..., None] * np.array([0.35, 0.10, 0.0]), 0, 1)
Image.fromarray((rgb * 255).astype(np.uint8)).save(os.path.join(OUT, "lava_flow.png"), optimize=True)
print("lava_flow v2")
