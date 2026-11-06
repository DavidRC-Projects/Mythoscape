#!/usr/bin/env python3
"""Bake painted husky walk frames for n/e/s/w.

Reads pets_hd/pet_husky/painted/{n,e,s,w}.png and writes
pets_hd/pet_husky/painted/walk/{face}/f00..f07.png via mesh warps that keep
the painted look while adding a diagonal trot / paw-lift gait.
"""
from __future__ import annotations

import math
import os
import sys

import numpy as np
from PIL import Image

ROOT = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", "..", "pets_hd", "pet_husky"))
SRC = os.path.join(ROOT, "painted")
OUT = os.path.join(SRC, "walk")
FRAMES = 8


def load(path: str) -> np.ndarray:
    return np.asarray(Image.open(path).convert("RGBA"))


def save(arr: np.ndarray, path: str) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    Image.fromarray(arr.astype(np.uint8), "RGBA").save(path)


def sample(src: np.ndarray, ys: np.ndarray, xs: np.ndarray) -> np.ndarray:
    h, w = src.shape[:2]
    xs = np.clip(xs, 0, w - 1.001)
    ys = np.clip(ys, 0, h - 1.001)
    x0 = np.floor(xs).astype(np.int32)
    y0 = np.floor(ys).astype(np.int32)
    x1 = np.minimum(x0 + 1, w - 1)
    y1 = np.minimum(y0 + 1, h - 1)
    fx = xs - x0
    fy = ys - y0
    out = np.zeros(src.shape, np.float32)
    for c in range(4):
        channel = src[:, :, c]
        top = channel[y0, x0] * (1 - fx) + channel[y0, x1] * fx
        bot = channel[y1, x0] * (1 - fx) + channel[y1, x1] * fx
        out[:, :, c] = top * (1 - fy) + bot * fy
    return np.clip(out, 0, 255).astype(np.uint8)


def _bbox(src: np.ndarray):
    opaque = src[..., 3] > 20
    rows = np.where(opaque.any(1))[0]
    cols = np.where(opaque.any(0))[0]
    return int(rows[0]), int(rows[-1]), int(cols[0]), int(cols[-1])


def _smooth(t: np.ndarray) -> np.ndarray:
    t = np.clip(t, 0.0, 1.0)
    return t * t * (3.0 - 2.0 * t)


def warp_side(src: np.ndarray, phase: float, face: str) -> np.ndarray:
    """Side trot. Head, chest and rump stay the painted husky; only paws and the tail curl move."""
    h, w = src.shape[:2]
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    y0, y1, x0, x1 = _bbox(src)
    bh = max(1.0, float(y1 - y0))
    bw = max(1.0, float(x1 - x0))
    ry = (yy - y0) / bh
    rx = (xx - x0) / bw
    # Two footfalls per cycle. The whole dog rises together so the face never stretches.
    bob = (math.sin(phase * 4 * math.pi) ** 2) * 0.012 * bh
    step = math.sin(phase * 2 * math.pi)
    step_r = math.sin(phase * 2 * math.pi + math.pi)
    # Paws only — the knee line is low so the chest and head are copied 1:1.
    paw = _smooth((ry - 0.72) / 0.28)
    if face == "e":
        front = _smooth((rx - 0.55) / 0.35)
        rear = _smooth((0.42 - rx) / 0.32)
        tail = _smooth((0.22 - rx) / 0.22) * _smooth((0.48 - ry) / 0.36)
        sign = 1.0
    else:
        front = _smooth((0.45 - rx) / 0.35)
        rear = _smooth((rx - 0.58) / 0.32)
        tail = _smooth((rx - 0.78) / 0.22) * _smooth((0.48 - ry) / 0.36)
        sign = -1.0
    tail = tail * (1.0 - paw)
    lift_f = max(0.0, step) * 0.10 * bh
    lift_r = max(0.0, step_r) * 0.092 * bh
    stride_f = step * 0.07 * bw * sign
    stride_r = step_r * 0.062 * bw * sign
    wag = math.sin(phase * 4 * math.pi) * 0.035 * bw * sign
    dx = (stride_f * front + stride_r * rear) * paw + wag * tail
    # Positive lift samples from below, so the paw art moves up without scaling the head.
    sy = yy + bob - (lift_f * front + lift_r * rear) * paw
    return sample(src, sy, xx - dx)


def warp_front_back(src: np.ndarray, phase: float, face: str) -> np.ndarray:
    """Front / back trot. No chest sway and no head nod — those were widening the dog and growing the face."""
    h, w = src.shape[:2]
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    y0, y1, x0, x1 = _bbox(src)
    bh = max(1.0, float(y1 - y0))
    bw = max(1.0, float(x1 - x0))
    ry = (yy - y0) / bh
    rx = (xx - x0) / bw
    bob = (math.sin(phase * 4 * math.pi) ** 2) * 0.010 * bh
    step = math.sin(phase * 2 * math.pi)
    step_r = math.sin(phase * 2 * math.pi + math.pi)
    paw = _smooth((ry - 0.74) / 0.26)
    left = _smooth((0.46 - rx) / 0.34)
    right = _smooth((rx - 0.54) / 0.34)
    lift_l = max(0.0, step) * 0.095 * bh
    lift_r = max(0.0, step_r) * 0.095 * bh
    # A few pixels of plant, not a stance that spreads the chest.
    plant = 0.010 * bw
    dx = (-max(0.0, -step) * plant * left + max(0.0, -step_r) * plant * right) * paw
    if face == "n":
        tail = _smooth((0.34 - ry) / 0.34) * _smooth(1.0 - np.abs(rx - 0.5) * 2.8)
    else:
        tail = _smooth((0.22 - ry) / 0.22) * _smooth(1.0 - np.abs(rx - 0.5) * 3.4)
    # North/south canvases are narrow, so a fraction of width was only a pixel or two.
    dx = dx + math.sin(phase * 4 * math.pi) * 8.0 * tail * (1.0 - paw)
    sy = yy + bob - (lift_l * left + lift_r * right) * paw
    return sample(src, sy, xx - dx)


def bake() -> None:
    warps = {
        "n": warp_front_back,
        "s": warp_front_back,
        "e": warp_side,
        "w": warp_side,
    }
    for face, fn in warps.items():
        src_path = os.path.join(SRC, f"{face}.png")
        if not os.path.isfile(src_path):
            raise SystemExit(f"missing painted base: {src_path}")
        src = load(src_path)
        for fi in range(FRAMES):
            # Half-frame offset so no sample lands on the standing pose (that hitch froze the cycle).
            save(fn(src, (fi + 0.5) / float(FRAMES), face), os.path.join(OUT, face, f"f{fi:02d}.png"))
        print(f"baked {face} -> {OUT}/{face}/")


if __name__ == "__main__":
    bake()
    sys.stdout.flush()
