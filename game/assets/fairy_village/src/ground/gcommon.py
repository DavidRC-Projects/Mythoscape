"""Shared helpers for the fairy ground pack (periodic noise, band masks, paths).

Image-space convention everywhere: x -> east (right), y -> south (down), tile = [0,1)^2.
Master resolution N = 640 px per tile (4x of the 160 px asset).
"""
import numpy as np, os
F = "/workspace/fairy_village"
WORK = F + "/work/ground"
TILES = F + "/assets/tiles"
N = 640
os.makedirs(WORK, exist_ok=True)

# shared-border scheme: every variant of a set is pixel-identical for dist_to_border < BAND_IN,
# blends to its own interior by BAND_OUT. Objects centred closer than OBJ_SHARED are shared by all variants.
BAND_IN, BAND_OUT = 0.02, 0.07
OBJ_SHARED = 0.08


def grid(n=N):
    c = (np.arange(n) + 0.5) / n
    return np.meshgrid(c, c)            # X[y,x], Y[y,x]


def border_dist(n=N):
    X, Y = grid(n)
    return np.minimum(np.minimum(X, 1 - X), np.minimum(Y, 1 - Y))


def smooth(e0, e1, v):
    t = np.clip((v - e0) / (e1 - e0), 0, 1)
    return t * t * (3 - 2 * t)


def pnoise(n, cells, rng):
    g = rng.random((cells, cells))
    x = np.arange(n) * cells / n
    i0 = np.floor(x).astype(int); f = x - i0; i1 = (i0 + 1) % cells
    f = f * f * (3 - 2 * f)
    a = g[i0][:, i0]; b = g[i0][:, i1]; c = g[i1][:, i0]; d = g[i1][:, i1]
    fx = f[None, :]; fy = f[:, None]
    return (a * (1 - fx) + b * fx) * (1 - fy) + (c * (1 - fx) + d * fx) * fy


def fbm(n, rng, octs=(4, 8, 16, 32, 64), amps=(0.5, 0.25, 0.13, 0.07, 0.05)):
    v = sum(a * pnoise(n, c, rng) for c, a in zip(octs, amps)) / sum(amps)
    return (v - v.min()) / (v.max() - v.min() + 1e-9)


def ramp(v, stops):
    v = np.clip(v, 0, 1)
    out = np.zeros(v.shape + (3,))
    xs = [s[0] for s in stops]
    for ch in range(3):
        out[..., ch] = np.interp(v, xs, [s[1][ch] for s in stops])
    return out


def pdist(X, Y, px, py):
    dx = np.abs(X - px); dx = np.minimum(dx, 1 - dx)
    dy = np.abs(Y - py); dy = np.minimum(dy, 1 - dy)
    return np.sqrt(dx * dx + dy * dy)


def bdist_pt(x, y):
    return min(x, 1 - x, y, 1 - y)


def poisson(rng, r, k=30, region=None, start=()):
    """Periodic Poisson-disc in [0,1)^2. region(x,y)->bool filters candidates."""
    pts = list(start)
    tries = 0
    while tries < 4000:
        x, y = rng.random(), rng.random()
        tries += 1
        if region and not region(x, y):
            continue
        ok = True
        for (qx, qy) in pts:
            dx = abs(x - qx); dx = min(dx, 1 - dx); dy = abs(y - qy); dy = min(dy, 1 - dy)
            if dx * dx + dy * dy < r * r:
                ok = False; break
        if ok:
            pts.append((x, y)); tries = 0
    return pts[len(start):]
