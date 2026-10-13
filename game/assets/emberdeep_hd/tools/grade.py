"""Post-grade a Cycles stone bake: per-stone tint (periodic labelling), mottling, volcanic palette.
python3 grade.py in.png out.png kind"""
import sys, numpy as np
from PIL import Image
sys.path.insert(0, __file__.rsplit("/", 1)[0])
from make_textures import fbm, blur
src, dst, kind = sys.argv[1], sys.argv[2], sys.argv[3]
seed = {"wall": 3, "wall_b": 4, "lava": 5, "floor": 6, "top": 7}.get(kind, 1)
img = np.asarray(Image.open(src).convert("RGB")).astype(float) / 255
n = img.shape[0]
lum = img @ np.array([0.3, 0.59, 0.11])
emit = np.clip((img[..., 0] - img[..., 2]) - 0.25, 0, 1) * (img[..., 0] > 0.6)  # lava glow pixels
# stones = bright connected regions (mortar is dark); periodic min-label propagation
thr = np.percentile(lum, 22)
mask = blur(lum, 1.5) > thr
lab = np.where(mask, np.arange(n * n).reshape(n, n), n * n + 1).astype(np.int64)
for _ in range(600):
    prev = lab
    m = lab
    for ax in (0, 1):
        for sh in (1, -1):
            m = np.minimum(m, np.roll(lab, sh, ax))
    lab = np.where(mask, m, n * n + 1)
    flat = np.append(lab.ravel(), n * n + 1)
    for _j in range(4):  # pointer jumping
        lab = np.where(mask, flat[np.minimum(lab, n * n)], n * n + 1)
        flat = np.append(lab.ravel(), n * n + 1)
    if np.array_equal(lab, prev):
        break
ids, inv = np.unique(lab, return_inverse=True)
inv = inv.reshape(n, n)
r = np.random.default_rng(seed)
bright = r.uniform(0.62, 1.22, len(ids))
warm = r.uniform(-0.10, 0.10, len(ids))
B = bright[inv]; W = warm[inv]
B = np.where(mask, B, 0.85); W = np.where(mask, W, 0)
big = fbm(n, 2.4, seed + 10); mid = fbm(n, 1.9, seed + 11)
mott = 0.78 + 0.42 * big
pal = {"wall": (0.92, 0.80, 0.70), "wall_b": (0.85, 0.80, 0.76), "lava": (0.95, 0.76, 0.64),
       "floor": (0.98, 0.86, 0.74), "top": (0.80, 0.74, 0.70)}[kind]
base = lum[..., None] ** 1.35 * np.array(pal)[None, None] * (B * mott)[..., None]
base[..., 0] *= 1 + W; base[..., 2] *= 1 - W
# lift the mortar joints: gritty, dusty, still in shadow (not black holes)
grit = fbm(n, 1.4, seed + 12)
joint = (~mask).astype(float)
joint = blur(joint, 1.0)
mcol = np.array([0.30, 0.265, 0.23]) * (0.65 + 0.7 * grit)[..., None]
mshade = np.clip(lum / max(1e-3, np.percentile(lum, 20)), 0.25, 1.0)[..., None]
base = base * (1 - joint[..., None]) + np.maximum(base, mcol * mshade * 0.55) * joint[..., None]
# soot / mineral staining in low mid-noise
stain = np.clip((mid - 0.55) * 3, 0, 1)[..., None]
base = base * (1 - 0.35 * stain)
# local contrast
base = np.clip(base + (base - blur(base.mean(-1), 6)[..., None]) * 0.35, 0, 1)
if kind == "lava":
    import os
    em = blur((emit > 0.02).astype(float), 0.8)
    lt = np.asarray(Image.open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "textures", "lava_flow.png")).convert("RGB")).astype(float) / 255
    lt = np.tile(lt, (2, 2, 1))
    lt = np.asarray(Image.fromarray((lt * 255).astype(np.uint8)).resize((n, n), Image.LANCZOS)).astype(float) / 255
    core = np.clip(blur(em, 4) * 1.6 - 0.35, 0, 1)[..., None]
    rim = np.array([0.42, 0.06, 0.01])
    lavac = lt * (0.75 + 0.6 * core) * (0.55 + 0.45 * core) + rim * (1 - core) * 0.6
    halo = blur(em, 9)[..., None] * np.array([0.50, 0.15, 0.02])
    halo2 = blur(em, 3)[..., None] * np.array([0.35, 0.09, 0.01])
    base = base * (1 - em[..., None]) + np.clip(lavac, 0, 1) * em[..., None]
    base = np.clip(base + (halo + halo2) * (1 - em[..., None]), 0, 1)
out = Image.fromarray((np.clip(base, 0, 1) * 255).astype(np.uint8)).resize((512, 512), Image.LANCZOS)
out.save(dst, optimize=True)
print("graded", dst, len(ids), "stones")
