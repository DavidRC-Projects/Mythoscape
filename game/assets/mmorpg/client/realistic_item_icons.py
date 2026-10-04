"""Inventory and ground sprites from the realistic item icon pack."""
from __future__ import annotations

import os

import pygame

_DIR = os.path.join(os.path.dirname(__file__), "..", "assets", "items", "realistic")
_RAW = {}
_SCALED = {}


def _raw(item_id):
    if item_id in _RAW:
        return _RAW[item_id]
    path = os.path.join(_DIR, f"{item_id}.png")
    image = pygame.image.load(path).convert_alpha() if os.path.isfile(path) else None
    _RAW[item_id] = image
    return image


def _fit(item_id, width, height):
    key = (item_id, int(width), int(height))
    if key in _SCALED:
        return _SCALED[key]
    image = _raw(item_id)
    if image is None:
        _SCALED[key] = None
        return None
    bounds = image.get_bounding_rect(min_alpha=8)
    if bounds.w > 1 and bounds.h > 1:
        image = image.subsurface(bounds).copy()
    scale = min(width / image.get_width(), height / image.get_height())
    size = (max(1, int(image.get_width() * scale)), max(1, int(image.get_height() * scale)))
    fitted = pygame.transform.smoothscale(image, size)
    _SCALED[key] = fitted
    if len(_SCALED) > 512:
        _SCALED.clear()
        _SCALED[key] = fitted
    return fitted


def _keep_old(item_id) -> bool:
    """Pets stay on the original inventory art."""
    return str(item_id or "").startswith("pet_")


def draw_icon(surf, rect, item_id) -> bool:
    """Blit the pack icon inside rect. False if this item has no file."""
    if _keep_old(item_id):
        return False
    pad = max(1, rect.w // 10)
    image = _fit(item_id, max(1, rect.w - pad * 2), max(1, rect.h - pad * 2))
    if image is None:
        return False
    dest = image.get_rect(center=rect.center)
    surf.blit(image, dest)
    return True


def draw_ground(surf, tile_rect, item_id) -> bool:
    """Same icon as inventory, sitting on the tile with a soft shadow. No loot pad."""
    if _keep_old(item_id):
        return False
    side = max(8, int(tile_rect.w * 0.78))
    image = _fit(item_id, side, side)
    if image is None:
        return False
    cx = tile_rect.centerx
    foot = tile_rect.centery + tile_rect.h // 5
    shadow = pygame.Surface((image.get_width(), max(4, image.get_height() // 6)), pygame.SRCALPHA)
    pygame.draw.ellipse(shadow, (0, 0, 0, 80), shadow.get_rect())
    surf.blit(shadow, shadow.get_rect(midbottom=(cx, foot + 2)))
    surf.blit(image, image.get_rect(midbottom=(cx, foot)))
    return True
