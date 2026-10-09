"""Render a few Emberdeep follow-camera frames and print how long each took."""
from __future__ import annotations

import os
import sys
import time

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(_HERE, "..", "server"))
sys.path.insert(0, os.path.join(_HERE, "..", "client"))

import pygame

import emberdeep
from emberdeep_view3d import EmberView3D
from world_map import WALL, WATER


def main():
    pygame.init()
    tiles = emberdeep.generate_floor_tiles(1)
    tex = os.path.normpath(os.path.join(_HERE, "..", "..", "emberdeep_hd", "textures"))
    view = EmberView3D(
        tiles, tex,
        lambda tile: tile == WALL,
        lambda tile: tile == WATER,
        boss_door=emberdeep.v2_marks().get("boss"),
    )
    sx, sy = emberdeep.DUNGEON_SPAWN
    shots = []
    for zoom in (0.0, 0.5, 1.0):
        shots.append((f"spawn_z{zoom}", sx + 0.5, sy + 0.5, zoom))
        shots.append((f"lair_z{zoom}", 22.5, 7.5, zoom))
    rw, rh = 378, 269
    for name, fx, fy, zoom in shots:
        view.set_camera(fx, fy, 0.0, zoom)
        view.heights[:] = view.heights_target
        started = time.perf_counter()
        rgb, _depth = view.render(rw, rh, now=1.0)
        ms = (time.perf_counter() - started) * 1000.0
        surf = pygame.surfarray.make_surface(rgb.swapaxes(0, 1))
        path = f"/tmp/ember_{name}.png"
        pygame.image.save(surf, path)
        print(f"{name}: {ms:.1f} ms -> {path}")


if __name__ == "__main__":
    main()
