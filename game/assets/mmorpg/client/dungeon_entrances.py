"""2D dungeon-entrance sprites from the Blender pack (front-facing view).

Sprites are a fixed camera bake — they are not rotated when the view yaw changes.
"""
from __future__ import annotations

import json
import os

import pygame

# Player reads about 2 tiles tall for a 1.8 m figure (rs-style profile).
_PLAYER_TILES = 2.0
_PLAYER_METRES = 1.8
_SIZE = "512"

_DIR = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    "assets", "dungeons", "front34",
)

_cache: dict[str, tuple[pygame.Surface, dict] | None] = {}
_scaled: dict[tuple, pygame.Surface] = {}


def _load(key: str):
    if key in _cache:
        return _cache[key]
    png = os.path.join(_DIR, f"{key}_{_SIZE}.png")
    meta_path = os.path.join(_DIR, f"{key}.json")
    if not (os.path.isfile(png) and os.path.isfile(meta_path)):
        _cache[key] = None
        return None
    with open(meta_path, encoding="utf-8") as f:
        meta = json.load(f)
    size = (meta.get("sizes") or {}).get(_SIZE)
    if not size:
        _cache[key] = None
        return None
    surf = pygame.image.load(png).convert_alpha()
    _cache[key] = (surf, size)
    return _cache[key]


def _px_per_metre(tile: int) -> float:
    return (_PLAYER_TILES * tile) / _PLAYER_METRES


def _placed(key: str, cx, cy, tile):
    """Return (scaled surface, left, top) or None."""
    if not key:
        return None
    loaded = _load(key)
    if not loaded:
        return None
    sheet, size = loaded
    metres_per_px = float(size.get("metres_per_px") or 0)
    if metres_per_px <= 0:
        return None
    scale = _px_per_metre(tile) * metres_per_px
    dw = max(1, int(round(sheet.get_width() * scale)))
    dh = max(1, int(round(sheet.get_height() * scale)))
    cache_key = (key, dw, dh)
    scaled = _scaled.get(cache_key)
    if scaled is None:
        scaled = pygame.transform.smoothscale(sheet, (dw, dh))
        _scaled[cache_key] = scaled
    ox, oy = size["origin_px"]
    ground_x = cx
    ground_y = cy + tile * 0.30
    left = int(ground_x - ox * scale)
    top = int(ground_y - oy * scale)
    return scaled, left, top


def draw_pack(surf, pack_key, cx, cy, tile, yaw=0):
    """Blit a pack sprite. Returns the sprite's top Y, or None if not drawn."""
    if int(yaw or 0) % 4 != 0:
        return None
    placed = _placed(pack_key, cx, cy, tile)
    if not placed:
        return None
    scaled, left, top = placed
    surf.blit(scaled, (left, top))
    return top


def sprite_rect(pack_key, cx, cy, tile, yaw=0):
    """Screen rect of a pack sprite, or None."""
    if int(yaw or 0) % 4 != 0:
        return None
    placed = _placed(pack_key, cx, cy, tile)
    if not placed:
        return None
    scaled, left, top = placed
    return pygame.Rect(left, top, scaled.get_width(), scaled.get_height())
