"""Grade the Blender gate-pillar render -> textures/door_boss.png (512x1024)."""
import sys, os, numpy as np
from PIL import Image
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from make_textures import fbm, blur
D = os.path.dirname(os.path.abspath(__file__)) + "/.."
img = np.asarray(Image.open(f"{D}/work/p_door.png").convert("RGB")).astype(float) / 255
h, w = img.shape[:2]
yy, xx = np.mgrid[0:h, 0:w]
lum = img @ np.array([0.3, 0.59, 0.11])
emit = np.clip((img[..., 0] - img[..., 2]) - 0.2, 0, 1) * (img[..., 0] > 0.5)
panel = (xx > w * 0.245) & (xx < w * 0.755) & (yy > h * 0.33) & (yy < h * 0.85)
inner = (xx > w * 0.27) & (xx < w * 0.73) & (yy > h * 0.345) & (yy < h * 0.83)
rune = emit * inner
joint = np.clip(emit * ~inner * 3, 0, 1)
g1 = fbm(1024, 2.4, 41)[:, :512] if False else fbm(512, 2.4, 41, m=1024)
g2 = fbm(512, 1.4, 42, m=1024)
# stone: wall palette with per-course tint from big noise
base = np.clip(lum, 0, 1)[..., None] ** 1.35 * np.array([0.92, 0.80, 0.70]) * (0.78 + 0.42 * g1)[..., None]
# panel slightly darker basalt, sooty toward the bottom
base = np.where(panel[..., None], base * np.array([0.78, 0.74, 0.72]) * (1 - 0.25 * (yy / h))[..., None], base)
# mortar joints: dark grit, not glowing
mcol = np.array([0.075, 0.062, 0.052]) * (0.6 + 0.8 * g2)[..., None]
jj = blur(joint, 0.8)[..., None]
base = base * (1 - jj) + mcol * jj
# runes: deep ember glow with a hot core and a soft bleed into the carving
cover = np.clip(rune * 1.4, 0, 1)
er = (rune > 0.25).astype(float)
for _ in range(2):
    er = np.minimum.reduce([er, np.roll(er, 1, 0), np.roll(er, -1, 0), np.roll(er, 1, 1), np.roll(er, -1, 1)])
hot = np.clip(blur(er, 1.2) * 1.5, 0, 1) * (0.6 + 0.6 * g2)   # hotter in the middle of the groove, flickering crust
crust = np.clip((g2 - 0.62) * 4, 0, 1) * 0.5                               # cooled flecks in the channel
glow = blur(rune, 6)
col = (np.array([0.62, 0.10, 0.015]) + np.array([0.4, 0.3, 0.05]) * hot[..., None] + np.array([0.0, 0.3, 0.15]) * np.clip(hot - 0.5, 0, 1)[..., None]) * (1 - crust[..., None])
core = cover
col = col * core[..., None]
scorch = np.clip(blur(rune, 2.5) * 2, 0, 1) * (1 - cover)
base = base * (1 - 0.55 * scorch[..., None])
base = base * (1 - core[..., None]) + col + glow[..., None] * np.array([0.45, 0.12, 0.02])
base = np.clip(base + (base - blur(base.mean(-1), 6)[..., None]) * 0.3, 0, 1)
Image.fromarray((base * 255).astype(np.uint8)).save(f"{D}/textures/door_boss.png", optimize=True)
print("door ok")
