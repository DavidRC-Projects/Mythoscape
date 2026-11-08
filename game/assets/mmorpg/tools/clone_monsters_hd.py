#!/usr/bin/env python3
"""Clone an existing monsters_hd pack into a new id with optional colour multiply.

Usage:
  python3 tools/clone_monsters_hd.py --src giant_rat --dst sewer_rat --rgb 170,210,180 \\
      --name "Sewer Rat" --look "filthy green-grey sewer rat..."
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import sys

from PIL import Image, ImageChops

ROOT = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", ".."))
HD = os.path.join(ROOT, "monsters_hd")


def _mul(img: Image.Image, rgb) -> Image.Image:
    r, g, b = rgb
    out = img.convert("RGBA")
    tint = Image.new("RGBA", out.size, (r, g, b, 255))
    mixed = ImageChops.multiply(out, tint)
    # Keep original alpha (multiply would also darken A).
    rr, gg, bb, _aa = mixed.split()
    _or, _og, _ob, oa = out.split()
    return Image.merge("RGBA", (rr, gg, bb, oa))


def clone(src: str, dst: str, rgb=None, name=None, look=None, level=None):
    src_dir = os.path.join(HD, src)
    dst_dir = os.path.join(HD, dst)
    if not os.path.isdir(src_dir):
        raise SystemExit(f"missing source pack: {src_dir}")
    if os.path.exists(dst_dir):
        shutil.rmtree(dst_dir)
    shutil.copytree(src_dir, dst_dir)

    meta_path = os.path.join(dst_dir, "meta.json")
    with open(meta_path, encoding="utf-8") as f:
        meta = json.load(f)
    meta["id"] = dst
    if name:
        meta["name"] = name
    if look:
        meta["look"] = look
    if level is not None:
        meta["level"] = int(level)
    meta["cloned_from"] = src
    if rgb:
        meta["colour_multiply"] = list(rgb)
    with open(meta_path, "w", encoding="utf-8") as f:
        json.dump(meta, f, indent=1)
        f.write("\n")

    if not rgb:
        print(f"cloned {src} -> {dst} (no tint)")
        return

    n = 0
    for root, _dirs, files in os.walk(dst_dir):
        for fn in files:
            if not fn.lower().endswith(".png"):
                continue
            path = os.path.join(root, fn)
            img = Image.open(path)
            _mul(img, rgb).save(path, optimize=True)
            n += 1
    print(f"cloned {src} -> {dst} ({n} frames tinted {rgb})")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", required=True)
    ap.add_argument("--dst", required=True)
    ap.add_argument("--rgb", default=None, help="R,G,B multiply 0-255")
    ap.add_argument("--name", default=None)
    ap.add_argument("--look", default=None)
    ap.add_argument("--level", type=int, default=None)
    args = ap.parse_args()
    rgb = None
    if args.rgb:
        parts = [int(x.strip()) for x in args.rgb.split(",")]
        if len(parts) != 3:
            raise SystemExit("--rgb needs R,G,B")
        rgb = tuple(parts)
    clone(args.src, args.dst, rgb=rgb, name=args.name, look=args.look, level=args.level)


if __name__ == "__main__":
    main()
