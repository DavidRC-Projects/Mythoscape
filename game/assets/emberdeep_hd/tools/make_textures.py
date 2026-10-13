"""Emberdeep HD tileable textures (numpy + PIL). Every map is periodic, so it tiles seamlessly.
Run: python3 make_textures.py  -> ../textures/*.png
"""
import os, numpy as np
from PIL import Image

OUT = os.path.join(os.path.dirname(__file__), "..", "textures")
N = 512
rng = np.random.default_rng(7)

def fbm(n=N, beta=2.0, seed=None, m=None):
    r = np.random.default_rng(seed)
    m = m or n
    f = np.fft.fft2(r.standard_normal((m, n)))
    ky = np.fft.fftfreq(m)[:, None]; kx = np.fft.fftfreq(n)[None, :]
    k = np.sqrt(kx * kx + ky * ky); k[0, 0] = 1
    out = np.real(np.fft.ifft2(f / k ** (beta / 2)))
    out -= out.min(); out /= out.max()
    return out

def blur(a, sigma):
    m, n = a.shape
    ky = np.fft.fftfreq(m)[:, None]; kx = np.fft.fftfreq(n)[None, :]
    g = np.exp(-2 * (np.pi * sigma) ** 2 * (kx * kx + ky * ky))
    return np.real(np.fft.ifft2(np.fft.fft2(a) * g))

def smooth(e0, e1, x):
    t = np.clip((x - e0) / (e1 - e0), 0, 1)
    return t * t * (3 - 2 * t)

def shade(h, albedo, strength=6.0, light=(-0.55, -0.65, 0.55), ao_r=10, ao_k=2.2, emissive=None):
    gx = (np.roll(h, -1, 1) - np.roll(h, 1, 1)) * strength
    gy = (np.roll(h, -1, 0) - np.roll(h, 1, 0)) * strength
    nz = np.ones_like(h)
    norm = np.sqrt(gx * gx + gy * gy + 1)
    nx, ny, nz = -gx / norm, -gy / norm, nz / norm
    L = np.array(light, float); L /= np.linalg.norm(L)
    # light comes from upper-left: vector toward light = -L
    diff = np.clip(nx * -L[0] + ny * -L[1] + nz * L[2], 0, 1)
    cav = np.clip(1 - (blur(h, ao_r) - h) * ao_k, 0.35, 1.08)
    # periodic cast shadows marched toward the light (upper-left)
    sh = np.ones_like(h)
    hs = h * strength * 14.0
    dx, dy = -L[0], -L[1]
    dn = np.hypot(dx, dy); dx, dy = dx / dn, dy / dn
    slope = L[2] / np.hypot(L[0], L[1])
    for k in range(1, 40):
        ox, oy = int(round(-dx * k)), int(round(-dy * k))
        other = np.roll(np.roll(hs, oy, 0), ox, 1)
        sh = np.minimum(sh, np.clip(1 - (other - hs - k * slope) * 0.25, 0.0, 1))
    sh = 0.45 + 0.55 * blur(sh, 1.2)
    convex = np.clip((h - blur(h, 3)) * 6, -0.2, 0.25)
    lit = (0.28 + 0.9 * diff * sh) * cav * (1 + convex)
    col = albedo * lit[..., None]
    # tiny spec on raised stone
    spec = (np.clip(diff, 0, 1) ** 18 * 0.10 * (h > 0.3))[..., None]
    col = col + spec
    if emissive is not None:
        col = col + emissive
    return np.clip(col, 0, 1)

MAPS = os.path.join(os.path.dirname(__file__), "..", "maps")

def save_maps(name, h, alb, em=None):
    os.makedirs(MAPS, exist_ok=True)
    stem = name[:-4]
    hh = (np.clip((h - h.min()) / (np.ptp(h) + 1e-9), 0, 1) * 65535).astype(np.uint16)
    Image.fromarray(hh).save(os.path.join(MAPS, stem + "_height.png"))
    Image.fromarray((np.clip(alb, 0, 1) * 255).astype(np.uint8)).save(os.path.join(MAPS, stem + "_albedo.png"))
    if em is not None:
        Image.fromarray((np.clip(em, 0, 1) * 255).astype(np.uint8)).save(os.path.join(MAPS, stem + "_emit.png"))

def save(name, rgb, alpha=None):
    a = (np.clip(rgb, 0, 1) * 255).astype(np.uint8)
    if alpha is not None:
        img = Image.fromarray(np.dstack([a, (np.clip(alpha, 0, 1) * 255).astype(np.uint8)]), "RGBA")
    else:
        img = Image.fromarray(a, "RGB")
    img.save(os.path.join(OUT, name), optimize=True)
    print("saved", name, img.size)

def ashlar(seed, rows=4, n=N, mortar=7, bevel=16):
    """Periodic coursed ashlar: block id map, edge distance, per-block random."""
    r = np.random.default_rng(seed)
    yy, xx = np.mgrid[0:n, 0:n].astype(float)
    # warp coordinates for chipped, hand-cut edges (periodic)
    wx = (fbm(n, 2.8, seed + 1) - 0.5) * 10 + (fbm(n, 2.0, seed + 11) - 0.5) * 2
    wy = (fbm(n, 2.8, seed + 2) - 0.5) * 10 + (fbm(n, 2.0, seed + 12) - 0.5) * 2
    X = (xx + wx) % n; Y = (yy + wy) % n
    hs = r.uniform(0.8, 1.2, rows); hs = hs / hs.sum() * n
    yb = np.concatenate([[0], np.cumsum(hs)])
    row = np.clip(np.searchsorted(yb, Y, side="right") - 1, 0, rows - 1)
    dy = np.minimum(Y - yb[row], yb[row + 1] - Y)
    dx = np.zeros_like(X); bid = np.zeros_like(X, dtype=int)
    for ri in range(rows):
        ws = []
        tot = 0
        while tot < n - 150:
            w = r.uniform(120, 230); ws.append(w); tot += w
        ws.append(n - tot)
        if ws[-1] < 90:
            ws[-2] += ws[-1]; ws.pop()
        off = r.uniform(0, n)
        xb = np.concatenate([[0], np.cumsum(ws)])
        m = row == ri
        xs = (X[m] - off) % n
        k = np.clip(np.searchsorted(xb, xs, side="right") - 1, 0, len(ws) - 1)
        dx[m] = np.minimum(xs - xb[k], xb[k + 1] - xs)
        bid[m] = ri * 100 + k
    d = np.minimum(dx, dy)
    return d, bid, row

def wall(name, seed, lava=False):
    d, bid, row = ashlar(seed)
    ids = np.unique(bid)
    r = np.random.default_rng(seed + 5)
    tint = {i: r.uniform(0.72, 1.18) for i in ids}
    hue = {i: r.uniform(-0.08, 0.08) for i in ids}
    bump = {i: r.uniform(-0.10, 0.10) for i in ids}
    T = np.vectorize(tint.get)(bid); Hh = np.vectorize(hue.get)(bid); B = np.vectorize(bump.get)(bid)
    big = fbm(N, 2.2, seed + 20); mid = fbm(N, 1.9, seed + 21); fine = fbm(N, 1.5, seed + 22)
    chip = fbm(N, 2.4, seed + 23); chip2 = fbm(N, 1.7, seed + 24)
    edge = 3.0 + 7.0 * smooth(0.45, 0.85, chip)
    face = smooth(edge, edge + 7, d)
    dome = smooth(0, 70, d)
    pits = smooth(0.70, 0.84, fine * 0.4 + mid * 0.6)
    cr = fbm(N, 2.0, seed + 30)
    cracks = smooth(0.010, 0.0, np.abs(cr - 0.5)) * (mid > 0.58)
    nicks = (1 - smooth(4, 34, d)) * smooth(0.52, 0.72, chip2)
    h = face * (0.70 + 0.06 * dome + 0.16 * big + 0.12 * mid + 0.03 * fine + B) \
        - 0.06 * pits * face - 0.12 * cracks * face - 0.30 * nicks * face
    h += (1 - face) * (0.03 * fine)
    base = np.array([0.33, 0.285, 0.25])
    stone = base[None, None, :] * T[..., None] * (0.78 + 0.42 * big[..., None])
    stone[..., 0] *= 1 + Hh; stone[..., 2] *= 1 - Hh
    stone = stone * (0.90 + 0.18 * mid[..., None]) * (1 - 0.25 * nicks[..., None])
    mortar = np.array([0.12, 0.105, 0.095])[None, None, :] * (0.8 + 0.4 * fine[..., None])
    alb = stone * face[..., None] + mortar * (1 - face[..., None])
    streak = smooth(0.58, 0.88, fbm(N, 2.8, seed + 40))[..., None]
    alb = alb * (1 - 0.32 * streak)
    em = None
    if lava:
        seam = (1 - face) * smooth(0.55, 0.75, big)        # only some joints carry lava
        vein = np.clip(seam + cracks * smooth(0.5, 0.7, big) * 1.5, 0, 1)
        glow = blur(vein, 4.0) * 1.3
        em = np.stack([0.95 * glow, 0.33 * glow, 0.05 * glow], -1) + np.stack([vein * 0.85, vein * 0.5, vein * 0.1], -1)
        heat = blur(vein, 14)[..., None]
        alb = alb * (1 - 0.2 * vein[..., None]) + np.array([0.10, 0.03, 0.0]) * np.clip(heat * 3, 0, 1)
    save_maps(name, h, alb, em)
    rgb = shade(h, alb, strength=4.2, emissive=em)
    save(name, rgb)
    return h

def floor(name, seed):
    """Worn rectangular flagstones, 2x2 game tiles per texture (4 courses, staggered)."""
    d, bid, row = ashlar(seed, rows=4)
    ids = np.unique(bid)
    r = np.random.default_rng(seed + 5)
    tint = {i: r.uniform(0.78, 1.15) for i in ids}
    tx = {i: r.uniform(-1, 1) for i in ids}; ty = {i: r.uniform(-1, 1) for i in ids}
    T = np.vectorize(tint.get)(bid)
    yy, xx = np.mgrid[0:N, 0:N].astype(float)
    tilt = (np.vectorize(tx.get)(bid) * np.sin(xx / N * 2 * np.pi) + np.vectorize(ty.get)(bid) * np.sin(yy / N * 2 * np.pi)) * 0.03
    big = fbm(N, 2.2, seed + 3); mid = fbm(N, 1.9, seed + 4); fine = fbm(N, 1.5, seed + 5)
    chip = fbm(N, 2.6, seed + 6)
    edge = 2.5 + 7 * smooth(0.5, 0.85, chip)
    face = smooth(edge, edge + 6, d)
    wear = smooth(0.5, 0.9, mid)
    cr = fbm(N, 2.0, seed + 7)
    cracks = smooth(0.009, 0.0, np.abs(cr - 0.5)) * (big > 0.55) * face
    h = face * (0.75 + 0.10 * big + 0.05 * mid + tilt - 0.04 * wear) + (1 - face) * 0.04 * fine - cracks * 0.12
    base = np.array([0.36, 0.31, 0.27])
    alb = base[None, None] * T[..., None] * (0.80 + 0.32 * big[..., None]) * (1 - 0.14 * wear[..., None])
    alb = alb * (0.93 + 0.14 * fine[..., None])
    grout = np.array([0.12, 0.105, 0.095])[None, None] * (0.8 + 0.4 * fine[..., None])
    alb = alb * face[..., None] + grout * (1 - face[..., None])
    ash = smooth(0.62, 0.9, fbm(N, 2.6, seed + 8))[..., None]
    alb = alb * (1 - 0.22 * ash) + 0.04 * ash
    save_maps(name, h, alb)
    rgb = shade(h, alb, strength=3.2, light=(-0.45, -0.55, 0.70))
    save(name, rgb)

def wall_top(name, seed):
    r = np.random.default_rng(seed); n = N
    pts = r.uniform(0, n, (60, 2))
    yy, xx = np.mgrid[0:n, 0:n].astype(float)
    wx = (fbm(n, 2.4, seed + 1) - 0.5) * 10; wy = (fbm(n, 2.4, seed + 2) - 0.5) * 10
    X = xx + wx; Y = yy + wy
    f1 = np.full((n, n), 1e9); f2 = np.full((n, n), 1e9); idx = np.zeros((n, n), int)
    for i, (px, py) in enumerate(pts):
        for ox in (-n, 0, n):
            for oy in (-n, 0, n):
                dd = np.hypot(X - (px + ox), Y - (py + oy))
                sm = dd < f1
                f2 = np.where(sm, f1, np.minimum(f2, dd)); idx = np.where(sm, i, idx); f1 = np.where(sm, dd, f1)
    e = (f2 - f1) / 2
    big = fbm(n, 2.2, seed + 3); fine = fbm(n, 1.6, seed + 4)
    h = smooth(1, 18, e) ** 0.6 * (0.7 + 0.3 * r.uniform(0.6, 1, len(pts))[idx]) + 0.1 * big + 0.03 * fine
    alb = np.array([0.23, 0.20, 0.18])[None, None] * r.uniform(0.7, 1.2, len(pts))[idx][..., None] * (0.8 + 0.3 * big[..., None])
    save_maps(name, h, alb)
    rgb = shade(h, alb, strength=5.0, light=(-0.45, -0.55, 0.70), ao_r=6, ao_k=3)
    save(name, rgb)

def trim(name, seed, height, kind):
    """Horizontally tileable band: base plinth or top cornice."""
    w, hgt = N, height
    yy, xx = np.mgrid[0:hgt, 0:w].astype(float)
    big = fbm(w, 2.2, seed, m=hgt) if False else fbm(N, 2.2, seed)[:hgt]
    fine = fbm(N, 1.0, seed + 1)[:hgt]
    # blocks every 256 px with chiselled chamfer
    bx = xx % 256
    dx = np.minimum(bx, 256 - bx)
    v = yy / hgt
    if kind == "base":
        prof = smooth(0.0, 0.10, v) * (0.85 + 0.15 * smooth(0.12, 0.2, v)) - 0.25 * smooth(0.82, 1.0, v) * 0 
        top_ch = smooth(0.0, 0.16, v)             # chamfered top edge
        h = top_ch * smooth(3, 12, dx) * (0.85 + 0.1 * big + 0.04 * fine)
        alb = np.array([0.32, 0.27, 0.235])[None, None] * (0.82 + 0.3 * big[..., None])
        dirt = smooth(0.55, 1.0, v)[..., None]      # grime toward the floor
        alb = alb * (1 - 0.45 * dirt)
    else:
        bead = np.exp(-((v - 0.72) / 0.07) ** 2) * 0.35
        h = (smooth(0.0, 0.2, v) * 0.7 + bead) * smooth(3, 12, dx) * (0.85 + 0.1 * big + 0.04 * fine)
        alb = np.array([0.30, 0.26, 0.23])[None, None] * (0.82 + 0.3 * big[..., None])
        soot = smooth(0.6, 0.0, v)[..., None]
        alb = alb * (1 - 0.4 * soot)
    # periodic only horizontally; vertical gradient is intended
    rgb = shade(h, alb, strength=6.0)
    save(name, rgb)

def sconce(name):
    """4 frames of an iron wall torch, RGBA, 96x160 each, as one strip."""
    W, H = 96, 160
    frames = []
    for f in range(4):
        yy, xx = np.mgrid[0:H, 0:W].astype(float)
        a = np.zeros((H, W)); col = np.zeros((H, W, 3))
        cx = W / 2
        # wall plate
        plate = (np.abs(xx - cx) < 13) & (np.abs(yy - 112) < 22)
        # bracket arm
        arm = (np.abs(xx - cx) < 4) & (yy > 84) & (yy < 112)
        # cup
        cup = (np.abs(xx - cx) < 15 - (yy - 70) * 0.35) & (yy > 70) & (yy < 86)
        iron = plate | arm | cup
        lit = 0.5 + 0.5 * np.clip((cx - xx) / 20 + 0.4, 0, 1)
        col[iron] = (np.array([0.16, 0.14, 0.13]) * 1.0)[None] * lit[iron][:, None] + np.array([0.18, 0.08, 0.02]) * (yy[iron] < 90)[:, None]
        rivet = ((xx - cx) ** 2 + (yy - 104) ** 2 < 6) | ((xx - cx) ** 2 + (yy - 122) ** 2 < 6)
        col[rivet] = [0.35, 0.3, 0.27]
        a[iron | rivet] = 1
        # flame
        r = np.random.default_rng(100 + f)
        sway = [0, 2.5, -1.5, 1.0][f]
        fy = (70 - yy) / 52.0
        width = 15 * np.clip(1 - fy, 0, 1) ** 0.7 * np.clip(fy * 3 + 0.5, 0, 1)
        fx = xx - cx - sway * np.clip(fy, 0, None) ** 1.5 * 3
        flame = np.clip(1 - np.abs(fx) / np.maximum(width, 0.01), 0, 1) * (fy > -0.05) * (fy < 1)
        n = fbm(64, 1.6, 200 + f)
        noise = np.array(Image.fromarray((n * 255).astype(np.uint8)).resize((W, H)), float) / 255
        flame = np.clip(flame * (0.75 + 0.5 * noise), 0, 1)
        core = flame ** 2.5
        fc = np.stack([np.ones_like(flame), 0.45 + 0.5 * core, 0.08 + 0.7 * core ** 2], -1)
        glow = np.exp(-(((xx - cx) / 30) ** 2 + ((yy - 48) / 34) ** 2)) * 0.45
        gc = np.array([1.0, 0.55, 0.15])
        out = col * a[..., None]
        fa = np.clip(flame * 1.4, 0, 1)
        out = out * (1 - fa[..., None]) + fc * fa[..., None]
        a2 = np.maximum(a, fa)
        ga = glow * (1 - a2)
        out = out + gc * ga[..., None]
        a2 = np.clip(a2 + ga, 0, 1)
        rgb = np.where(a2[..., None] > 0, out / np.maximum(a2[..., None], 1e-3), 0)
        frames.append((rgb, a2))
    strip_rgb = np.concatenate([f[0] for f in frames], 1)
    strip_a = np.concatenate([f[1] for f in frames], 1)
    save(name, strip_rgb, strip_a)

if __name__ == "__main__":
    os.makedirs(OUT, exist_ok=True)
    wall("wall_stone.png", 11)
    wall("wall_stone_b.png", 23)
    wall("wall_stone_lava.png", 37, lava=True)
    floor("floor_flagstone.png", 51)
    wall_top("wall_top.png", 61)
    trim("wall_base_trim.png", 71, 96, "base")
    trim("wall_cap_trim.png", 81, 64, "cap")
    sconce("torch_sconce_strip.png")
