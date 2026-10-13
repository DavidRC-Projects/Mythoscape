"""Meadow grass and packed-earth lanes for the overworld.

Guided by the fairy glade (soft variation, several tiles that meet cleanly,
grass creeping onto the road) but not the same: sunlit blades instead of
clover, and earth with pebbles instead of petals.

Writes assets/village_ground/meadow_v*_*.png and lane_v*_*.png.
"""
from __future__ import annotations

import math
import os

import numpy as np
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.normpath(os.path.join(HERE, "..", "assets", "village_ground"))
N = 160
VARIANTS = 5
BAND = 0.16


def _upsample(grid, n):
    s = grid.shape[0]
    g = np.pad(grid, ((0, 1), (0, 1)), mode="wrap")
    ys = np.linspace(0, s, n, endpoint=False)
    xs = np.linspace(0, s, n, endpoint=False)
    y0 = np.floor(ys).astype(np.int32)
    x0 = np.floor(xs).astype(np.int32)
    fy = (ys - y0)[:, None]
    fx = (xs - x0)[None, :]
    ia = g[y0][:, x0]
    ib = g[y0][:, x0 + 1]
    ic = g[y0 + 1][:, x0]
    id_ = g[y0 + 1][:, x0 + 1]
    return ia * (1 - fy) * (1 - fx) + ib * (1 - fy) * fx + ic * fy * (1 - fx) + id_ * fy * fx


def fbm(n, rng, scales, weights):
    acc = np.zeros((n, n), np.float32)
    total = 0.0
    for scale, weight in zip(scales, weights):
        acc += _upsample(rng.random((scale, scale)).astype(np.float32), n) * weight
        total += weight
    return acc / total


def _blend(shared, unique, n):
    yy, xx = np.mgrid[0:n, 0:n]
    dist = np.minimum(np.minimum(xx, n - 1 - xx), np.minimum(yy, n - 1 - yy)).astype(np.float32)
    t = np.clip(dist / (n * BAND), 0, 1)
    w = (t * t * (3 - 2 * t))[..., None]
    return shared * (1 - w) + unique * w


def _mix(img, x, y, color, cover):
    x %= N
    y %= N
    img[y, x] = img[y, x] * (1 - cover) + color * cover


def _blade(img, x, y, ang, length, color, cover=0.85):
    dx, dy = math.cos(ang), math.sin(ang)
    steps = max(2, int(length))
    for i in range(steps):
        px = int(round(x + dx * i))
        py = int(round(y + dy * i))
        fade = 1 - 0.45 * (i / steps)
        _mix(img, px, py, color * fade, cover)
        if i < steps * 0.55:
            _mix(img, px + 1, py, color * fade * 0.9, cover * 0.55)


def _field(rng, meadow):
    tone = fbm(N, rng, (4, 8, 16, 32), (0.45, 0.28, 0.17, 0.10))
    fine = fbm(N, rng, (24, 48, 80), (0.4, 0.35, 0.25))
    if meadow:
        deep = np.array([38, 74, 30], np.float32)
        mid = np.array([78, 124, 48], np.float32)
        lit = np.array([138, 168, 70], np.float32)
        sun = np.array([168, 184, 92], np.float32)
    else:
        deep = np.array([108, 78, 48], np.float32)
        mid = np.array([154, 116, 74], np.float32)
        lit = np.array([186, 150, 104], np.float32)
        sun = np.array([204, 174, 128], np.float32)
    t = tone[..., None]
    base = deep * (1 - t) + mid * t
    base = base * (0.92 + 0.16 * fine[..., None])
    # Broad sun patches.
    sun_w = np.clip((tone - 0.62) / 0.28, 0, 1)[..., None]
    base = base * (1 - sun_w * 0.35) + sun * sun_w * 0.35
    img = np.clip(base, 0, 255)
    if meadow:
        count = 520
        for _ in range(count):
            x = rng.random() * N
            y = rng.random() * N
            ang = -math.pi / 2 + rng.uniform(-0.7, 0.7)
            length = rng.uniform(7, 16)
            if rng.random() < 0.45:
                color = lit + rng.uniform(-8, 8)
            else:
                color = deep + np.array([8, 16, 4]) + rng.uniform(-6, 6)
            _blade(img, x, y, ang, length, color, cover=0.72)
        # A few seed heads. Not clover.
        for _ in range(18):
            x = int(rng.random() * N)
            y = int(rng.random() * N)
            gold = np.array([214, 186, 78], np.float32)
            for dy in range(-1, 2):
                for dx in range(-1, 2):
                    if dx * dx + dy * dy <= 2:
                        _mix(img, x + dx, y + dy, gold, 0.8)
    else:
        # Pebbles and worn speckles. No petals.
        for _ in range(70):
            x = int(rng.random() * N)
            y = int(rng.random() * N)
            rad = int(rng.uniform(1, 3.2))
            pebble = np.array([128, 118, 104], np.float32) + rng.uniform(-12, 12)
            shade = pebble - np.array([28, 24, 18], np.float32)
            for dy in range(-rad, rad + 1):
                for dx in range(-rad, rad + 1):
                    if dx * dx + dy * dy <= rad * rad:
                        col = shade if dx + dy > 0 else pebble
                        _mix(img, x + dx, y + dy, col, 0.9)
        speck = fbm(N, rng, (20, 40), (0.5, 0.5))
        darken = (speck < 0.28)[..., None]
        img = img * np.where(darken, 0.86, 1.0)
        # Short grass flecks so the lane belongs in the meadow.
        sprout = np.array([86, 120, 48], np.float32)
        for _ in range(40):
            x = rng.random() * N
            y = rng.random() * N
            _blade(img, x, y, -math.pi / 2 + rng.uniform(-0.4, 0.4), rng.uniform(4, 8), sprout, cover=0.55)
    return np.clip(img, 0, 255)


def _make(kind, meadow):
    shared_rng = np.random.default_rng(41027 if meadow else 41091)
    shared = _field(shared_rng, meadow)
    tiles = []
    for i in range(VARIANTS):
        rng = np.random.default_rng((41027 if meadow else 41091) + 100 + i * 17)
        unique = _field(rng, meadow)
        tiles.append(_blend(shared, unique, N))
    return tiles


def _save(tiles, stem):
    os.makedirs(OUT, exist_ok=True)
    for i, tile in enumerate(tiles, start=1):
        master = Image.fromarray(tile.astype(np.uint8), "RGB")
        for size in (160, 80, 40):
            image = master if size == 160 else master.resize((size, size), Image.Resampling.LANCZOS)
            image.save(os.path.join(OUT, f"{stem}_v{i}_{size}.png"))


_NOISE = None


def _noise_table():
    global _NOISE
    if _NOISE is None:
        rng = np.random.default_rng(90210)
        raw = rng.random(64).astype(np.float32)
        _NOISE = np.concatenate([raw, raw[:1]])
    return _NOISE


def _sample(pos):
    tab = _noise_table()
    period = len(tab) - 1
    x = np.mod(pos / 9.0, period)
    i0 = np.floor(x).astype(np.int32) % period
    f = x - np.floor(x)
    f = f * f * (3 - 2 * f)
    return tab[i0] * (1 - f) + tab[i0 + 1] * f


def fringe_alpha(mask, n, ox=0, oy=0):
    """Ragged grass overlap. Bits: N=1 E=4 S=16 W=64, corners NE=2 SE=8 SW=32 NW=128.

    ox, oy are the tile origin in pixels so a long road keeps one continuous edge.
    """
    alpha = np.zeros((n, n), np.uint8)
    local = np.arange(n)

    def paint_down(pos, y_of):
        depth = np.clip(n * (0.10 + 0.28 * _sample(pos)), 1, n * 0.42)
        for i in range(n):
            d = int(depth[i])
            solid = int(d * 0.62)
            for t in range(d):
                fade = 1.0 if t <= solid else 1.0 - (t - solid) / max(1, d - solid)
                y = y_of(t)
                if 0 <= y < n:
                    alpha[i, y] = max(alpha[i, y], int(255 * max(0.0, fade)))

    def paint_side(pos, x_of):
        depth = np.clip(n * (0.10 + 0.28 * _sample(pos)), 1, n * 0.42)
        for i in range(n):
            d = int(depth[i])
            solid = int(d * 0.62)
            for t in range(d):
                fade = 1.0 if t <= solid else 1.0 - (t - solid) / max(1, d - solid)
                x = x_of(t)
                if 0 <= x < n:
                    alpha[x, i] = max(alpha[x, i], int(255 * max(0.0, fade)))

    if mask & 1:
        paint_down(ox + local, lambda t: t)
    if mask & 16:
        paint_down(ox + local + 180, lambda t: n - 1 - t)
    if mask & 4:
        paint_side(oy + local + 90, lambda t: n - 1 - t)
    if mask & 64:
        paint_side(oy + local + 270, lambda t: t)
    # Corner tufts only when that diagonal was kept (both sides are road).
    corners = {2: (n - 1, 0), 8: (n - 1, n - 1), 32: (0, n - 1), 128: (0, 0)}
    for bit, (cx, cy) in corners.items():
        if not (mask & bit):
            continue
        rad = int(n * 0.34)
        for y in range(n):
            for x in range(n):
                d = math.hypot(x - cx, y - cy)
                if d < rad * 0.55:
                    alpha[x, y] = 255
                elif d < rad:
                    alpha[x, y] = max(alpha[x, y], int(255 * (1 - (d - rad * 0.55) / (rad * 0.45))))
    return alpha


def _preview(meadows, lanes):
    """A road and a crossing through mixed meadow tiles."""
    s = 80
    cols, rows = 8, 6
    sheet = Image.new("RGBA", (cols * s, rows * s))
    road = {(x, 2) for x in range(cols)} | {(3, y) for y in range(rows)}
    for y in range(rows):
        for x in range(cols):
            tile = lanes[(x + y) % VARIANTS] if (x, y) in road else meadows[(x * 2 + y) % VARIANTS]
            image = Image.fromarray(tile.astype(np.uint8), "RGB").resize((s, s), Image.Resampling.LANCZOS)
            sheet.paste(image.convert("RGBA"), (x * s, y * s))
    meadow = np.array(Image.fromarray(meadows[0].astype(np.uint8), "RGB").resize((s, s), Image.Resampling.LANCZOS))
    pix = np.array(sheet)
    for y in range(rows):
        for x in range(cols):
            if (x, y) not in road:
                continue
            mask = 0
            if (x, y - 1) not in road:
                mask |= 1
            if (x + 1, y) not in road:
                mask |= 4
            if (x, y + 1) not in road:
                mask |= 16
            if (x - 1, y) not in road:
                mask |= 64
            alpha = fringe_alpha(mask, s, x * s, y * s)
            block = pix[y * s:(y + 1) * s, x * s:(x + 1) * s]
            # alpha is x, y; image rows are y, x
            a = alpha.T.astype(np.float32) / 255.0
            grass = meadow.astype(np.float32)
            block[:, :, :3] = grass * a[..., None] + block[:, :, :3] * (1 - a[..., None])
            pix[y * s:(y + 1) * s, x * s:(x + 1) * s] = block
    Image.fromarray(pix.astype(np.uint8), "RGBA").convert("RGB").save("/tmp/village_ground_preview.png")


def main():
    meadows = _make("meadow", True)
    lanes = _make("lane", False)
    _save(meadows, "meadow")
    _save(lanes, "lane")
    _preview(meadows, lanes)
    print("wrote", OUT)


if __name__ == "__main__":
    main()
