"""Bake Crownfall Arena layers from the campus painting.

Writes soft-edged PNGs so the landmark fades into the realm ground and soldiers
can y-sort between a back wall and a front lip (castle-style):

  client/assets/castle_realm/arena/sprites/{1x,2x}/
    arena_ground.png   — sand floor (no sports oval / mid-line)
    arena_back.png     — north seating + outer wall (pit punched out)
    arena_front.png    — south seating + gatehouse (pit punched out)
    arena_gate_closed.png / arena_gate_open.png — reserve entry gates
"""
from __future__ import annotations

import os

import numpy as np
from PIL import Image, ImageChops, ImageDraw, ImageFilter

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(
    os.path.join(HERE, "..", "client", "assets", "castle_realm", "arena", "sprites")
)
SRC = os.path.join(ROOT, "1x", "arena_campus.jpg")
N = 1024


def _soft_disk(n, rx, ry, feather):
    yy, xx = np.mgrid[0:n, 0:n]
    cx = cy = (n - 1) / 2.0
    dist = np.sqrt(((xx - cx) / rx) ** 2 + ((yy - cy) / ry) ** 2)
    # 1 inside, 0 outside, with a soft rim.
    return np.clip((1.0 - dist) / max(1e-6, feather) + 1.0, 0.0, 1.0)


def _sand_ground(n):
    """Warm packed sand plate — grit only, no pitch markings."""
    rng = np.random.default_rng(21)
    tone = rng.random((n // 8, n // 8)).astype(np.float32)
    tone = np.array(
        Image.fromarray((tone * 255).astype(np.uint8), "L").resize((n, n), Image.Resampling.BILINEAR)
    ).astype(np.float32) / 255.0
    fine = rng.random((n // 2, n // 2)).astype(np.float32)
    fine = np.array(
        Image.fromarray((fine * 255).astype(np.uint8), "L").resize((n, n), Image.Resampling.BILINEAR)
    ).astype(np.float32) / 255.0
    deep = np.array([158, 122, 64], np.float32)
    mid = np.array([198, 164, 92], np.float32)
    lite = np.array([226, 196, 124], np.float32)
    t = np.clip(tone * 0.7 + fine * 0.3, 0, 1)
    rgb = deep * (1 - t)[..., None] + mid * t[..., None]
    bright = np.clip((fine - 0.55) * 2.0, 0, 1)
    rgb = rgb * (1 - bright[..., None] * 0.22) + lite * (bright[..., None] * 0.22)
    # Soft oval that matches the stamped sand pit (slightly inset).
    alpha = _soft_disk(n, n * 0.36, n * 0.32, 0.12)
    rgba = np.zeros((n, n, 4), np.float32)
    rgba[..., :3] = rgb
    rgba[..., 3] = alpha * 235
    return Image.fromarray(np.clip(rgba, 0, 255).astype(np.uint8), "RGBA")


def _split_campus(campus: Image.Image):
    """Soft exterior fade + pit punch; split into back (north) and front (south)."""
    arr = np.array(campus.convert("RGBA"), dtype=np.float32)
    n = arr.shape[0]
    # Outer stadium body — keep seating/walls, fade rocky square edges away.
    body = _soft_disk(n, n * 0.46, n * 0.46, 0.10)
    # Pit hole so tile sand / ground layer reads under soldiers.
    pit = _soft_disk(n, n * 0.30, n * 0.27, 0.08)
    keep = np.clip(body * (1.0 - pit * 0.98), 0, 1)
    arr[..., 3] *= keep

    # Vertical split: north wall behind actors, south lip in front.
    yy = np.linspace(0, 1, n, dtype=np.float32)[:, None]
    # Soft band so the join isn't a hard cut across the seats.
    back_w = np.clip((0.58 - yy) / 0.10, 0, 1)
    front_w = np.clip((yy - 0.42) / 0.10, 0, 1)

    back = arr.copy()
    front = arr.copy()
    back[..., 3] *= back_w
    front[..., 3] *= front_w
    return (
        Image.fromarray(np.clip(back, 0, 255).astype(np.uint8), "RGBA"),
        Image.fromarray(np.clip(front, 0, 255).astype(np.uint8), "RGBA"),
    )


def _gate_sprite(open_: bool, size=160):
    """Stone side gate — closed holds a portcullis; open leaves the arch clear."""
    stone = (118, 108, 96, 245)
    lip = (158, 148, 132, 255)
    dark = (70, 62, 54, 255)
    # Draw solid post + arch, then punch the doorway with a mask.
    base = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    bd = ImageDraw.Draw(base)
    # Left / right pillars
    bd.rounded_rectangle([size * 0.12, size * 0.18, size * 0.32, size * 0.95], radius=8, fill=stone)
    bd.rounded_rectangle([size * 0.68, size * 0.18, size * 0.88, size * 0.95], radius=8, fill=stone)
    # Arch crown
    bd.pieslice([size * 0.12, size * 0.05, size * 0.88, size * 0.70], 180, 0, fill=stone)
    bd.rectangle([size * 0.12, size * 0.34, size * 0.88, size * 0.48], fill=stone)
    # Punch doorway
    door = Image.new("L", (size, size), 0)
    dd = ImageDraw.Draw(door)
    dd.pieslice([size * 0.30, size * 0.18, size * 0.70, size * 0.62], 180, 0, fill=255)
    dd.rectangle([size * 0.30, size * 0.38, size * 0.70, size * 0.96], fill=255)
    # Keep alpha where door is black
    alpha = base.split()[-1]
    alpha = ImageChops.subtract(alpha, door)
    base.putalpha(alpha)
    d = ImageDraw.Draw(base)
    d.arc([size * 0.30, size * 0.18, size * 0.70, size * 0.62], 180, 0, fill=lip, width=3)
    d.line([(size * 0.30, size * 0.40), (size * 0.30, size * 0.95)], fill=lip, width=2)
    d.line([(size * 0.70, size * 0.40), (size * 0.70, size * 0.95)], fill=lip, width=2)
    # Team banners on the posts
    d.rectangle([size * 0.16, size * 0.22, size * 0.28, size * 0.48], fill=(55, 95, 150, 230))
    d.rectangle([size * 0.72, size * 0.22, size * 0.84, size * 0.48], fill=(150, 38, 36, 230))
    if not open_:
        for i in range(5):
            x = int(size * (0.34 + i * 0.08))
            d.line([(x, int(size * 0.32)), (x, int(size * 0.92))], fill=dark, width=3)
        for j in range(4):
            y = int(size * (0.40 + j * 0.12))
            d.line([(int(size * 0.32), y), (int(size * 0.68), y)], fill=dark, width=2)
    else:
        for i in range(5):
            x = int(size * (0.34 + i * 0.08))
            d.line([(x, int(size * 0.18)), (x, int(size * 0.34))], fill=(90, 80, 70, 180), width=2)
    return base.filter(ImageFilter.GaussianBlur(radius=0.35))


def bake():
    if not os.path.isfile(SRC):
        raise SystemExit(f"missing campus art: {SRC}")
    campus = Image.open(SRC)
    ground = _sand_ground(N)
    back, front = _split_campus(campus)
    # Soften layer silhouettes a touch.
    back = back.filter(ImageFilter.GaussianBlur(radius=0.5))
    front = front.filter(ImageFilter.GaussianBlur(radius=0.5))
    gate_closed = _gate_sprite(False)
    gate_open = _gate_sprite(True)

    for scale, folder in ((1, "1x"), (2, "2x")):
        out = os.path.join(ROOT, folder)
        os.makedirs(out, exist_ok=True)
        pairs = (
            ("arena_ground.png", ground),
            ("arena_back.png", back),
            ("arena_front.png", front),
            ("arena_gate_closed.png", gate_closed),
            ("arena_gate_open.png", gate_open),
        )
        for name, im in pairs:
            path = os.path.join(out, name)
            if scale == 1:
                im.save(path, optimize=True)
            else:
                w, h = im.size
                im.resize((w * 2, h * 2), Image.Resampling.LANCZOS).save(path, optimize=True)
            print("wrote", path)


if __name__ == "__main__":
    bake()
