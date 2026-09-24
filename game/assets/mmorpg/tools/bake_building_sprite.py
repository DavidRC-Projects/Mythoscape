#!/usr/bin/env python3
"""
Bake connected ¾-view building shell PNGs for the pygame client.

Uses building_shell3d (same drawer as runtime) so baked art matches live
procedural shells under camera yaw.

Usage:
  SDL_VIDEODRIVER=dummy python bake_building_sprite.py --all
  SDL_VIDEODRIVER=dummy python bake_building_sprite.py cottage_nw
"""
from __future__ import annotations

import argparse
import json
import os
import sys

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

import pygame

_HERE = os.path.dirname(os.path.abspath(__file__))
_CLIENT = os.path.normpath(os.path.join(_HERE, "..", "client"))
_SERVER = os.path.normpath(os.path.join(_HERE, "..", "server"))
_CHARS = os.path.normpath(os.path.join(_HERE, "..", "..", "characters"))
_TEX = os.path.join(_CLIENT, "textures")
_OUT = os.path.join(_CLIENT, "assets", "buildings")

sys.path.insert(0, _SERVER)
sys.path.insert(0, _CHARS)
sys.path.insert(0, _CLIENT)

import building_textures as btex  # noqa: E402
import building_shell3d as shell  # noqa: E402
from content import BUILDINGS, INTERACTABLES  # noqa: E402

PPT = 64
# Padding: roof peak above footprint; side depth is inset so little right pad
PAD_X = 0.08
PAD_RIGHT = 0.10
PAD_TOP = 0.55
PAD_BOT = 0.08
DEPTH = 0.22


def _door_frac(b: dict) -> float:
    x0, x1 = int(b["x0"]), int(b["x1"])
    y1 = int(b["y1"])
    span = max(1, x1 - x0)
    for spot in INTERACTABLES:
        if spot.get("kind") != "door":
            continue
        if int(spot.get("y", -1)) == y1 and x0 <= int(spot.get("x", -1)) <= x1:
            return (int(spot["x"]) - x0 + 0.5) / span
    return 0.5


def bake_building(b: dict) -> str:
    bid = b["id"]
    kind = b.get("kind") or "house"
    tw = b["x1"] - b["x0"] + 1
    th = b["y1"] - b["y0"] + 1
    fw = tw * PPT
    fh = th * PPT
    pad_x = int(fw * PAD_X)
    pad_right = int(fw * PAD_RIGHT)
    pad_top = int(fh * PAD_TOP)
    pad_bot = int(fh * PAD_BOT)
    W = fw + pad_x + pad_right
    H = fh + pad_top + pad_bot
    surf = pygame.Surface((W, H), pygame.SRCALPHA)

    foot = pygame.Rect(pad_x, pad_top, fw, fh)
    door_frac = _door_frac(b)

    if kind == "volcano":
        import procedural_sprites_finished as sprites
        sprites._draw_volcano_mountain(surf, foot, alpha=255)
    elif kind == "castle":
        import procedural_sprites_finished as sprites
        sprites._draw_castle_keep(surf, foot, alpha=255)
    else:
        material = b.get("material")
        style = int(b.get("style") or 0)
        shell.draw_building_shell(
            surf, foot, kind=kind, material=material, style=style, alpha=255,
            door_frac=door_frac,
        )

    os.makedirs(_OUT, exist_ok=True)
    out_png = os.path.join(_OUT, f"{bid}.png")
    pygame.image.save(surf, out_png)
    meta = {
        "id": bid,
        "name": b.get("name"),
        "source": "bake_building_sprite.py + building_shell3d",
        "pad_x": PAD_X,
        "pad_x_right": PAD_RIGHT,
        "pad_y_top": PAD_TOP,
        "pad_y_bot": PAD_BOT,
        "depth": DEPTH,
        "ppt": PPT,
        "pixels": [W, H],
        "footprint_tiles": [tw, th],
    }
    with open(os.path.join(_OUT, f"{bid}.json"), "w", encoding="utf-8") as f:
        json.dump(meta, f, indent=2)
    return out_png


def main():
    pygame.init()
    try:
        pygame.display.set_mode((1, 1))
    except pygame.error:
        pass
    btex.set_texture_dir(_TEX)

    ap = argparse.ArgumentParser()
    ap.add_argument("building_id", nargs="?")
    ap.add_argument("--all", action="store_true")
    args = ap.parse_args()
    by_id = {b["id"]: b for b in BUILDINGS}

    if args.all:
        targets = list(BUILDINGS)
    elif args.building_id:
        if args.building_id not in by_id:
            print("Unknown:", args.building_id, file=sys.stderr)
            sys.exit(1)
        targets = [by_id[args.building_id]]
    else:
        targets = [by_id["cottage_nw"]]

    for b in targets:
        path = bake_building(b)
        print(f"baked {b['id']} → {path}")


if __name__ == "__main__":
    main()
