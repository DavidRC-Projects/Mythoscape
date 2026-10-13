"""Composite a transparent hero render onto a painted twilight backdrop with soft bokeh fireflies."""
import sys, random, math
from PIL import Image, ImageDraw, ImageFilter
import numpy as np


def backdrop(w, h, seed=3, top=(46, 52, 98), mid=(132, 104, 150), bot=(236, 178, 140)):
    y = np.linspace(0, 1, h)[:, None]
    def lerp(a, b, t):
        return np.array(a)[None, None, :] * (1 - t[..., None]) + np.array(b)[None, None, :] * t[..., None]
    t1 = np.clip(y / 0.6, 0, 1) * np.ones((h, w))
    t2 = np.clip((y - 0.6) / 0.4, 0, 1) * np.ones((h, w))
    img = np.where((y < 0.6)[..., None] * np.ones((h, w, 1), bool), lerp(top, mid, t1), lerp(mid, bot, t2))
    xx = np.linspace(-1, 1, w)[None, :]; yy = np.linspace(-1, 1, h)[:, None]
    vig = 1 - 0.35 * np.clip(xx ** 2 + yy ** 2 - 0.3, 0, 1)
    img = img * vig[..., None]
    base = Image.fromarray(np.clip(img, 0, 255).astype(np.uint8)).convert("RGBA")
    glow = Image.new("RGBA", (w, h), (0, 0, 0, 0)); d = ImageDraw.Draw(glow)
    rnd = random.Random(seed)
    for i in range(int(w * h / 26000)):
        x, yv = rnd.random() * w, rnd.random() * h * 0.85
        r = rnd.uniform(0.004, 0.018) * w
        c = rnd.choice([(255, 220, 150), (200, 180, 255), (170, 230, 255)])
        d.ellipse((x - r, yv - r, x + r, yv + r), fill=(*c, rnd.randint(18, 60)))
    glow = glow.filter(ImageFilter.GaussianBlur(w * 0.004))
    base.alpha_composite(glow)
    return base


def forest(w, h, seed=3):
    """Dark enchanted-forest plate: deep teal->near-black, blurred trunk silhouettes, a moon shaft, warm fireflies."""
    rnd = random.Random(seed)
    y = np.linspace(0, 1, h)[:, None] * np.ones((1, w))
    top, mid, bot = np.array((10, 22, 30)), np.array((22, 48, 52)), np.array((14, 26, 22))
    img = np.where((y < 0.55)[..., None], top + (mid - top) * (y / 0.55)[..., None], mid + (bot - mid) * ((y - 0.55) / 0.45)[..., None])
    base = Image.fromarray(np.clip(img, 0, 255).astype(np.uint8)).convert("RGBA")
    for layer, (blur, shade, n) in enumerate(((0.012, (16, 34, 38), 9), (0.006, (8, 18, 20), 6))):
        lay = Image.new("RGBA", (w, h), (0, 0, 0, 0)); d = ImageDraw.Draw(lay)
        for i in range(n):
            x = rnd.uniform(-0.05, 1.05) * w
            if 0.3 * w < x < 0.7 * w and layer == 1:
                continue
            tw = rnd.uniform(0.03, 0.08) * w * (1.6 if layer else 1.0)
            d.polygon([(x - tw / 2, h), (x - tw * 0.32, 0), (x + tw * 0.32, 0), (x + tw / 2, h)], fill=(*shade, 255))
            for k in range(3):
                by = rnd.uniform(0.1, 0.6) * h; bx = x + rnd.choice((-1, 1)) * rnd.uniform(0.05, 0.15) * w
                d.line([(x, by + 0.08 * h), (bx, by)], fill=(*shade, 255), width=max(1, int(tw * 0.25)))
        base.alpha_composite(lay.filter(ImageFilter.GaussianBlur(w * blur)))
    sh = Image.new("RGBA", (w, h), (0, 0, 0, 0)); d = ImageDraw.Draw(sh)
    d.polygon([(0.18 * w, 0), (0.42 * w, 0), (0.78 * w, h), (0.30 * w, h)], fill=(150, 190, 255, 34))
    d.ellipse((0.15 * w, 0.80 * h, 0.85 * w, 1.05 * h), fill=(90, 160, 140, 40))
    base.alpha_composite(sh.filter(ImageFilter.GaussianBlur(w * 0.05)))
    glow = Image.new("RGBA", (w, h), (0, 0, 0, 0)); d = ImageDraw.Draw(glow)
    for i in range(int(w * h / 30000)):
        x, yv = rnd.random() * w, rnd.uniform(0.15, 0.95) * h
        r = rnd.uniform(0.002, 0.012) * w
        c = rnd.choice([(255, 214, 120), (255, 190, 90), (170, 255, 200), (190, 200, 255)])
        d.ellipse((x - r, yv - r, x + r, yv + r), fill=(*c, rnd.randint(40, 120)))
    base.alpha_composite(glow.filter(ImageFilter.GaussianBlur(w * 0.003)))
    xx = np.linspace(-1, 1, w)[None, :]; yy = np.linspace(-1, 1, h)[:, None]
    vig = (1 - 0.5 * np.clip(xx ** 2 + yy ** 2 - 0.25, 0, 1))[..., None]
    arr = np.asarray(base).astype(np.float32); arr[..., :3] *= vig
    return Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8))


def comp(src, dst, seed=3, style="twilight"):
    im = Image.open(src).convert("RGBA")
    bg = forest(*im.size, seed=seed) if style == "forest" else backdrop(*im.size, seed=seed)
    # soft magical bloom from bright pixels
    arr = np.asarray(im).astype(np.float32)
    lum = arr[..., :3].mean(-1)
    bright = np.clip((lum - 200) / 55, 0, 1)[..., None] * arr[..., :3]
    bl = Image.fromarray(np.clip(bright, 0, 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(im.size[0] * 0.006))
    bg.alpha_composite(im)
    out = np.asarray(bg).astype(np.float32)
    out[..., :3] = np.clip(out[..., :3] + np.asarray(bl).astype(np.float32) * 0.6, 0, 255)
    Image.fromarray(out.astype(np.uint8)).convert("RGB").save(dst, quality=95)


if __name__ == "__main__":
    comp(sys.argv[1], sys.argv[2], int(sys.argv[3]) if len(sys.argv) > 3 else 3, sys.argv[4] if len(sys.argv) > 4 else "twilight")
