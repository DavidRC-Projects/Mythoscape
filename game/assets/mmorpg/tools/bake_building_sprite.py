#!/usr/bin/env python3
"""Bake iso cottage sprites via building_volume (replaces old shell3d baker)."""
from __future__ import annotations

import argparse
import json
import os
import sys

import pygame

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.normpath(os.path.join(_HERE, ".."))
_CHARS = os.path.normpath(os.path.join(_ROOT, "..", "characters"))
sys.path.insert(0, _CHARS)
sys.path.insert(0, os.path.join(_ROOT, "server"))

import building_volume as bvol  # noqa: E402
from content import BUILDINGS  # noqa: E402

_OUT = os.path.join(_ROOT, "client", "assets", "buildings")


def bake_one(b, yaw=0, pad=40):
    w = (int(b["x1"]) - int(b["x0"]) + 1) * 40 + pad * 2
    h = (int(b["y1"]) - int(b["y0"]) + 1) * 40 + pad * 2
    surf = pygame.Surface((w, h), pygame.SRCALPHA)
    rect = pygame.Rect(pad, pad, w - pad * 2, h - pad * 2)
    bvol.draw_world_volume(
        surf, rect,
        kind=b.get("kind", "house"),
        yaw=yaw,
        material=b.get("material"),
        door_frac=0.5,
    )
    return surf


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--id", default=None, help="Single building id")
    args = ap.parse_args()
    pygame.init()
    os.makedirs(_OUT, exist_ok=True)
    yaw_names = {0: "s", 1: "w", 2: "n", 3: "e"}
    for b in BUILDINGS:
        bid = b["id"]
        if args.id and bid != args.id:
            continue
        if b.get("kind") == "volcano":
            continue
        for yaw in range(4):
            surf = bake_one(b, yaw=yaw)
            name = f"{bid}_{yaw_names[yaw]}.png" if yaw else f"{bid}.png"
            if yaw == 0:
                path = os.path.join(_OUT, f"{bid}.png")
                pygame.image.save(surf, path)
            path = os.path.join(_OUT, f"{bid}_{yaw_names[yaw]}.png")
            pygame.image.save(surf, path)
            meta = {"source": "bake_building_sprite.py + building_volume", "yaw": yaw}
            with open(path.replace(".png", ".json"), "w") as f:
                json.dump(meta, f, indent=2)
        print("baked", bid)
    print("done →", _OUT)


if __name__ == "__main__":
    main()
