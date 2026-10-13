"""Grade the Blender trim strips (periodic in x) to the wall palette. python3 grade_trim.py in.png out.png W H seed"""
import sys, numpy as np
from PIL import Image
sys.path.insert(0, __file__.rsplit("/", 1)[0])
from make_textures import fbm, blur
src, dst, OW, OH, seed = sys.argv[1], sys.argv[2], int(sys.argv[3]), int(sys.argv[4]), int(sys.argv[5])
split = float(sys.argv[6])  # image-space row fraction between the two block courses
img = np.asarray(Image.open(src).convert("RGB")).astype(float) / 255
h, w = img.shape[:2]
lum = img @ np.array([0.3, 0.59, 0.11])
big = fbm(w, 2.4, seed)[:h]; mid = fbm(w, 1.9, seed + 1)[:h]; grit = fbm(w, 1.4, seed + 2)[:h]
# per-block tint: dark vertical joints split blocks; tint by column segments of each sub-band
mask = blur(lum, 1.5) > np.percentile(lum, 22)
r = np.random.default_rng(seed)
tint = np.ones((h, w)); warm = np.zeros((h, w))
for y0, y1 in ((0, int(h * split)), (int(h * split), h)):
    col = mask[y0:y1].mean(0) < 0.45
    seg = np.cumsum(np.diff(np.concatenate([[col[-1]], col]).astype(int)) == 1)
    seg = seg % (seg.max() + 1) if seg.max() > 0 else seg
    if col[0] == 0 and seg.max() > 0:  # wrap: first and last segment are the same block
        seg = np.where(seg == seg.max(), 0, seg)
    vals = r.uniform(0.72, 1.18, seg.max() + 2); wv = r.uniform(-0.08, 0.08, seg.max() + 2)
    tint[y0:y1] = vals[seg][None]; warm[y0:y1] = wv[seg][None]
base = lum[..., None] ** 1.35 * np.array([0.92, 0.80, 0.70]) * ((0.78 + 0.42 * big) * tint)[..., None]
base[..., 0] *= 1 + warm; base[..., 2] *= 1 - warm
joint = blur((~mask).astype(float), 1.0)
mcol = np.array([0.30, 0.265, 0.23]) * (0.65 + 0.7 * grit)[..., None]
mshade = np.clip(lum / max(1e-3, np.percentile(lum, 20)), 0.25, 1.0)[..., None]
base = base * (1 - joint[..., None]) + np.maximum(base, mcol * mshade * 0.55) * joint[..., None]
base = base * (1 - 0.35 * np.clip((mid - 0.55) * 3, 0, 1))[..., None]
base = np.clip(base + (base - blur(base.mean(-1), 6)[..., None]) * 0.35, 0, 1)
Image.fromarray((base * 255).astype(np.uint8)).resize((OW, OH), Image.LANCZOS).save(dst, optimize=True)
print("trim", dst)
