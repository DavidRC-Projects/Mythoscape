"""Bake Crownfall Arena pit-floor textures (worn sand oval, soft mid-line, gate stains).

Writes:
  client/assets/castle_realm/arena/sprites/1x/arena_pit_floor.png
  client/assets/castle_realm/arena/sprites/2x/arena_pit_floor.png
"""
from __future__ import annotations

import math
import os

import numpy as np
from PIL import Image, ImageDraw, ImageEnhance, ImageFilter

HERE = os.path.dirname(os.path.abspath(__file__))
OUT_ROOT = os.path.normpath(
    os.path.join(HERE, "..", "client", "assets", "castle_realm", "arena", "sprites")
)
N = 640


def fbm(n, scales, weights, seed):
    r = np.random.default_rng(seed)
    acc = np.zeros((n, n), np.float32)
    total = 0.0
    for scale, weight in zip(scales, weights):
        g = r.random((scale, scale)).astype(np.float32)
        yy = np.linspace(0, scale - 1e-6, n)
        xx = np.linspace(0, scale - 1e-6, n)
        y0 = np.floor(yy).astype(np.int32)
        x0 = np.floor(xx).astype(np.int32)
        y1 = np.minimum(y0 + 1, scale - 1)
        x1 = np.minimum(x0 + 1, scale - 1)
        fy = (yy - y0)[:, None]
        fx = (xx - x0)[None, :]
        ia = g[y0][:, x0]
        ib = g[y0][:, x1]
        ic = g[y1][:, x0]
        id_ = g[y1][:, x1]
        up = (
            ia * (1 - fy) * (1 - fx)
            + ib * (1 - fy) * fx
            + ic * fy * (1 - fx)
            + id_ * fy * fx
        )
        acc += up * weight
        total += weight
    return acc / total


def bake():
    tone = fbm(N, (4, 8, 16, 32, 64), (0.32, 0.26, 0.2, 0.14, 0.08), 7)
    fine = fbm(N, (40, 80, 160), (0.4, 0.35, 0.25), 11)
    scuff = fbm(N, (6, 12, 24), (0.45, 0.35, 0.2), 19)
    streak = fbm(N, (3, 6, 12), (0.5, 0.3, 0.2), 31)

    deep = np.array([158, 122, 64], np.float32)
    mid = np.array([198, 164, 92], np.float32)
    lite = np.array([226, 196, 124], np.float32)
    shadow = np.array([132, 102, 58], np.float32)

    t = np.clip(tone * 0.65 + fine * 0.35, 0, 1)
    img = deep * (1 - t)[..., None] + mid * t[..., None]
    bright = np.clip((fine - 0.52) * 2.0, 0, 1)
    img = img * (1 - bright[..., None] * 0.28) + lite * (bright[..., None] * 0.28)
    dark = np.clip((scuff - 0.58) * 2.6, 0, 1)
    img = img * (1 - dark[..., None] * 0.2) + shadow * (dark[..., None] * 0.12)
    drag = np.clip((streak - 0.55) * 1.8, 0, 1)
    img = img * (1 - drag[..., None] * 0.08)

    yy, xx = np.mgrid[0:N, 0:N]
    cx = cy = (N - 1) / 2.0
    rx, ry = N * 0.44, N * 0.40
    dist = np.sqrt(((xx - cx) / rx) ** 2 + ((yy - cy) / ry) ** 2)
    pack = np.clip(1.0 - dist / 0.75, 0, 1) ** 1.4
    img = img * (1 - pack[..., None] * 0.06) + lite * (pack[..., None] * 0.06)
    rim = np.clip((dist - 0.78) / 0.22, 0, 1)
    img = img * (1 - rim[..., None] * 0.22) + shadow * (rim[..., None] * 0.18)

    rgba = np.zeros((N, N, 4), np.float32)
    rgba[..., :3] = img
    rgba[..., 3] = 255
    pil = Image.fromarray(np.clip(rgba, 0, 255).astype(np.uint8), "RGBA")
    draw = ImageDraw.Draw(pil)

    sand_line = (112, 88, 52, 95)
    sand_soft = (128, 100, 58, 55)
    sand_dash = (118, 92, 54, 70)

    def oval(r_scale, width, color, dash=False, gap=16, dash_len=9):
        if not dash:
            box = [
                cx - rx * r_scale,
                cy - ry * r_scale,
                cx + rx * r_scale,
                cy + ry * r_scale,
            ]
            draw.ellipse(box, outline=color, width=width)
            return
        for a0 in range(0, 360, gap):
            pts = []
            for a in range(a0, a0 + dash_len + 1):
                rad = math.radians(a)
                pts.append(
                    (
                        cx + rx * r_scale * math.cos(rad),
                        cy + ry * r_scale * math.sin(rad),
                    )
                )
            if len(pts) >= 2:
                draw.line(pts, fill=color, width=width)

    oval(0.94, 4, sand_line)
    oval(0.80, 2, sand_dash, dash=True)
    cr = N * 0.095
    draw.ellipse(
        [cx - cr, cy - cr, cx + cr, cy + cr], outline=sand_line, width=3
    )
    draw.line(
        [(cx, cy - ry * 0.76), (cx, cy + ry * 0.76)],
        fill=sand_soft,
        width=2,
    )

    overlay = Image.new("RGBA", (N, N), (0, 0, 0, 0))
    od = ImageDraw.Draw(overlay)
    for side, col in ((-1, (55, 95, 150, 38)), (1, (150, 55, 48, 38))):
        gx = cx + side * rx * 0.72
        od.ellipse([gx - 36, cy - 55, gx + 36, cy + 55], fill=col)
        od.rectangle(
            [gx - 3, cy - 30, gx + 3, cy + 30],
            fill=(col[0], col[1], col[2], 70),
        )
    pil = Image.alpha_composite(pil, overlay)

    for ang in (40, 140, 220, 320):
        rad = math.radians(ang)
        px = cx + rx * 0.91 * math.cos(rad)
        py = cy + ry * 0.91 * math.sin(rad)
        draw.ellipse([px - 6, py - 5, px + 6, py + 5], fill=(105, 90, 70, 110))
        draw.ellipse([px - 3, py - 2, px + 3, py + 2], fill=(145, 130, 105, 90))

    pil = pil.filter(ImageFilter.GaussianBlur(radius=0.6))
    pil = ImageEnhance.Color(pil).enhance(1.05)

    out1 = os.path.join(OUT_ROOT, "1x")
    out2 = os.path.join(OUT_ROOT, "2x")
    os.makedirs(out1, exist_ok=True)
    os.makedirs(out2, exist_ok=True)
    path1 = os.path.join(out1, "arena_pit_floor.png")
    path2 = os.path.join(out2, "arena_pit_floor.png")
    pil.save(path1, optimize=True)
    pil.resize((N * 2, N * 2), Image.Resampling.LANCZOS).save(path2, optimize=True)
    print("wrote", path1)
    print("wrote", path2)


if __name__ == "__main__":
    bake()
