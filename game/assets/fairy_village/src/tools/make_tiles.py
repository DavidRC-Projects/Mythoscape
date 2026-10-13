"""Seamless HD ground tiles (wrap-around periodic noise + wrap-drawn details). 160 px master -> 80/40."""
import numpy as np, random, math
from PIL import Image, ImageDraw, ImageFilter
OUT = "/workspace/fairy_village/assets/tiles"
N = 640   # master supersample (4x of 160) for crisp detail, downsampled


def pnoise(n, cells, rng):
    g = rng.random((cells, cells))
    x = np.arange(n) * cells / n
    i0 = np.floor(x).astype(int); f = x - i0; i1 = (i0 + 1) % cells
    f = f * f * (3 - 2 * f)
    a = g[i0][:, i0]; b = g[i0][:, i1]; c = g[i1][:, i0]; d = g[i1][:, i1]
    fx = f[None, :]; fy = f[:, None]
    return (a * (1 - fx) + b * fx) * (1 - fy) + (c * (1 - fx) + d * fx) * fy


def fbm(n, rng, oct=(4, 8, 16, 32, 64), amps=(0.5, 0.25, 0.13, 0.07, 0.05)):
    return sum(a * pnoise(n, c, rng) for c, a in zip(oct, amps)) / sum(amps)


def ramp(v, stops):
    v = np.clip(v, 0, 1)
    out = np.zeros(v.shape + (3,))
    xs = [s[0] for s in stops]
    for ch in range(3):
        out[..., ch] = np.interp(v, xs, [s[1][ch] for s in stops])
    return out


def wrap_draw(img, fn):
    for dx in (-N, 0, N):
        for dy in (-N, 0, N):
            fn(dx, dy)


def shade(rgb, h, strength=1.6):
    gy, gx = np.gradient(h)
    light = np.clip(1 + (-gx * 0.7 - gy * 0.7) * N * strength / 40, 0.6, 1.4)
    return rgb * light[..., None]


def save(img, name):
    img = img.convert("RGB")
    for px in (160, 80, 40):
        img.resize((px, px), Image.LANCZOS).save(f"{OUT}/{name}_{px}.png", optimize=True)


def moss(seed):
    rng = np.random.default_rng(seed); r = random.Random(seed)
    h = fbm(N, rng); d = fbm(N, rng, (16, 32, 64, 128), (0.4, 0.3, 0.2, 0.1))
    v = 0.55 * h + 0.45 * d
    rgb = ramp(v, [(0.0, (22, 52, 22)), (0.35, (40, 86, 32)), (0.6, (70, 120, 44)), (0.85, (112, 150, 62)), (1.0, (150, 170, 90))])
    teal = pnoise(N, 4, rng)
    rgb = rgb * (1 - 0.18 * teal[..., None]) + np.array((40, 110, 100)) * 0.18 * teal[..., None]
    rgb = shade(rgb, v)
    img = Image.fromarray(np.clip(rgb, 0, 255).astype(np.uint8)).convert("RGBA")
    d2 = ImageDraw.Draw(img)
    for i in range(60):   # clover / moss tufts
        x, y = r.random() * N, r.random() * N; s = r.uniform(10, 18); c = r.choice([(60, 130, 50), (90, 160, 60), (44, 104, 40)])
        def f(dx, dy, x=x, y=y, s=s, c=c):
            for k in range(3):
                a = k * 2.1 + x
                d2.ellipse((x + dx + math.cos(a) * s * 0.7 - s / 2, y + dy + math.sin(a) * s * 0.7 - s / 2, x + dx + math.cos(a) * s * 0.7 + s / 2, y + dy + math.sin(a) * s * 0.7 + s / 2), fill=c + (230,))
        wrap_draw(img, f)
    for i in range(10):    # tiny glowing flowers
        x, y = r.random() * N, r.random() * N; c = r.choice([(255, 210, 240), (200, 220, 255), (255, 240, 170)])
        def f(dx, dy, x=x, y=y, c=c):
            for k in range(5):
                a = k * 1.2566
                d2.ellipse((x + dx + math.cos(a) * 5 - 4, y + dy + math.sin(a) * 5 - 4, x + dx + math.cos(a) * 5 + 4, y + dy + math.sin(a) * 5 + 4), fill=c + (255,))
            d2.ellipse((x + dx - 3, y + dy - 3, x + dx + 3, y + dy + 3), fill=(255, 220, 90, 255))
        wrap_draw(img, f)
    return img


def petal_path(seed):
    rng = np.random.default_rng(seed); r = random.Random(seed)
    h = fbm(N, rng, (8, 16, 32, 64, 128), (0.4, 0.25, 0.15, 0.12, 0.08))
    rgb = ramp(h, [(0.0, (92, 70, 52)), (0.45, (140, 112, 84)), (0.75, (176, 148, 112)), (1.0, (206, 182, 146))])
    rgb = shade(rgb, h, 1.0)
    img = Image.fromarray(np.clip(rgb, 0, 255).astype(np.uint8)).convert("RGBA")
    d2 = ImageDraw.Draw(img)
    for i in range(70):   # pebbles
        x, y = r.random() * N, r.random() * N; s = r.uniform(5, 13); g = r.randint(120, 190)
        def f(dx, dy, x=x, y=y, s=s, g=g):
            d2.ellipse((x + dx - s, y + dy - s * 0.7, x + dx + s, y + dy + s * 0.7), fill=(g, g - 8, g - 20, 255))
            d2.ellipse((x + dx - s * 0.6, y + dy - s * 0.6, x + dx + s * 0.2, y + dy - s * 0.05), fill=(min(255, g + 40),) * 3 + (200,))
        wrap_draw(img, f)
    for i in range(60):   # petals
        x, y = r.random() * N, r.random() * N; a = r.uniform(0, 6.28); s = r.uniform(14, 24)
        c = r.choice([(250, 170, 205), (245, 205, 225), (225, 175, 245), (255, 228, 240)])
        def f(dx, dy, x=x, y=y, a=a, s=s, c=c):
            pts = [(x + dx + math.cos(a + t) * s * (0.5 if abs(t) > 1 else 1), y + dy + math.sin(a + t) * s * 0.45) for t in (-2.6, -1.2, 0, 1.2, 2.6, 3.14)]
            d2.polygon(pts, fill=c + (245,))
        wrap_draw(img, f)
    return img


def moonstone(seed):
    rng = np.random.default_rng(seed); r = random.Random(seed)
    pts = np.array([[r.random() * N, r.random() * N] for _ in range(11)])
    yy, xx = np.mgrid[0:N, 0:N].astype(np.float32)
    d1 = np.full((N, N), 1e9); d2 = np.full((N, N), 1e9); idx = np.zeros((N, N), int)
    for k, (px, py) in enumerate(pts):
        dx = np.abs(xx - px); dx = np.minimum(dx, N - dx)
        dy = np.abs(yy - py); dy = np.minimum(dy, N - dy)
        d = np.sqrt(dx * dx + dy * dy)
        m = d < d1
        d2 = np.where(m, d1, np.minimum(d2, d)); idx = np.where(m, k, idx); d1 = np.where(m, d, d1)
    edge = d2 - d1
    tone = np.array([r.uniform(0.85, 1.12) for _ in pts])[idx]
    n = fbm(N, rng, (8, 16, 32, 64, 128), (0.3, 0.25, 0.2, 0.15, 0.1))
    base = ramp(n, [(0.0, (96, 100, 116)), (0.5, (140, 143, 160)), (1.0, (184, 186, 200))]) * tone[..., None]
    vein = np.clip(1 - np.abs(pnoise(N, 6, rng) - 0.5) * 30, 0, 1) * 0.5
    base = base + np.array((90, 140, 200)) * vein[..., None] * 0.6
    bevel = np.clip(edge / 22, 0, 1)
    hgt = bevel * (0.8 + 0.2 * n)
    rgb = shade(base, hgt, 2.4)
    mortar = edge < 7
    moss_n = fbm(N, rng, (16, 32, 64), (0.5, 0.3, 0.2))
    mc = ramp(moss_n, [(0, (30, 60, 28)), (1, (80, 120, 50))])
    rgb = np.where(mortar[..., None], mc * 0.85, rgb)
    rgb = np.where(((edge < 9) & (moss_n > 0.62))[..., None], mc, rgb)
    return Image.fromarray(np.clip(rgb, 0, 255).astype(np.uint8)).convert("RGBA")


for i in range(3):
    save(moss(10 + i), f"fairy_moss_v{i+1}")
    save(petal_path(20 + i), f"petal_path_v{i+1}")
    save(moonstone(30 + i), f"moonstone_paving_v{i+1}")
# seam proof: 3x3 tiled previews
for name in ("fairy_moss_v1", "petal_path_v1", "moonstone_paving_v1"):
    t = Image.open(f"{OUT}/{name}_160.png"); g = Image.new("RGB", (480, 480))
    for x in range(3):
        for y in range(3):
            g.paste(t, (x * 160, y * 160))
    g.save(f"/workspace/fairy_village/previews/tile_{name}_3x3.png")
print("tiles ok")
