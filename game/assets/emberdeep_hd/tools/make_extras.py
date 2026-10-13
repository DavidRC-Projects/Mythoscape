"""Lava flow texture + trims cut from the graded wall bake + torch sconce strip."""
import os, sys, numpy as np
from PIL import Image
sys.path.insert(0, os.path.dirname(__file__))
from make_textures import fbm, blur, smooth, sconce, OUT
N = 512
# lava: periodic cooled-crust plates over bright molten channels
a = fbm(N, 3.2, 901); b = fbm(N, 2.4, 902); c = fbm(N, 3.0, 903); d = fbm(N, 2.0, 904)
ridge = 1 - np.abs(a - 0.5) * 2              # channels where a ~ 0.5
ridge2 = 1 - np.abs(d - 0.5) * 2
hot = np.maximum(smooth(0.86, 0.985, ridge), 0.55 * smooth(0.93, 0.995, ridge2)) * (0.75 + 0.25 * b)
crust = 1 - hot
col = np.stack([0.16 + 0.10 * b, 0.06 + 0.03 * b, 0.035 + 0.01 * b], -1) * (0.6 + 0.6 * c)[..., None] + blur(hot, 14)[..., None] * np.array([0.55, 0.12, 0.0])
molten = np.stack([np.ones_like(hot), 0.35 + 0.5 * hot ** 2, 0.05 + 0.4 * hot ** 4], -1)
glow = blur(hot, 6)[..., None] * np.array([0.6, 0.18, 0.02])
rgb = np.clip(col * crust[..., None] + molten * hot[..., None] + glow, 0, 1)
Image.fromarray((rgb * 255).astype(np.uint8)).save(os.path.join(OUT, "lava_flow.png"), optimize=True)
# trims from the graded wall_b (horizontally periodic crops)
w = np.asarray(Image.open(os.path.join(OUT, "wall_stone_b.png")).convert("RGB")).astype(float) / 255
def band(y0, hgt, kind):
    s = w[y0:y0 + hgt].copy()
    v = np.linspace(0, 1, hgt)[:, None, None]
    if kind == "base":
        s = s * 0.95
        s = s * (1 - 0.45 * smooth(0.45, 1.0, v))           # grime toward the floor
        s[:4] = s[:4] * 0.6 + 0.10                          # chamfer catch-light on the top lip
        s[4:8] *= 0.45                                       # shadow under the lip
    else:
        s = s * (1 - 0.5 * smooth(0.7, 0.0, v))              # soot on the cornice
        s[-6:] *= 0.35                                       # dark under-cut
        s[:3] = s[:3] * 0.6 + 0.08
    return s
Image.fromarray((np.clip(band(140, 96, "base"), 0, 1) * 255).astype(np.uint8)).save(os.path.join(OUT, "wall_base_trim.png"), optimize=True)
Image.fromarray((np.clip(band(300, 64, "cap"), 0, 1) * 255).astype(np.uint8)).save(os.path.join(OUT, "wall_cap_trim.png"), optimize=True)
sconce("torch_sconce_strip.png")
print("extras done")
