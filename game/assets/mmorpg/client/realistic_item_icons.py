"""Inventory and ground sprites from the realistic item icon pack."""
from __future__ import annotations

import math
import os
import time

import pygame

_DIR = os.path.join(os.path.dirname(__file__), "..", "assets", "items", "realistic")
_LEGACY = os.path.join(_DIR, "legacy")
_RAW = {}
_SCALED = {}
# Items whose pack icon hasn't been painted yet: (source icon, RGB multiply). Real files win.
_STAND_IN = {
    "mythos_battleaxe": ("adamant_battleaxe", (255, 120, 110)),
    "mythos_ore": ("adamantite_ore", (255, 120, 110)),
    "mythos_bar": ("adamantite_bar", (255, 120, 110)),
}


def _load(path):
    if not os.path.isfile(path):
        return None
    try:
        return pygame.image.load(path).convert_alpha()
    except Exception:
        return None


def _raw(item_id):
    if item_id in _RAW:
        return _RAW[item_id]
    image = _load(os.path.join(_DIR, f"{item_id}.png"))
    if image is None:
        # Old pre-Eclipse-style icon, kept only for when the new file is missing or broken.
        image = _load(os.path.join(_LEGACY, f"{item_id}.png"))
    if image is None and item_id in _STAND_IN:
        src_id, rgb = _STAND_IN[item_id]
        src = _raw(src_id)
        if src is not None:
            image = src.copy()
            image.fill((*rgb, 255), special_flags=pygame.BLEND_RGBA_MULT)
    if image is None:
        try:
            from content import ITEMS as _items
            base = (_items.get(item_id) or {}).get("art_as")
        except Exception:
            base = None
        if base and base != item_id:
            image = _raw(base)          # e.g. the Recruit's Bronze kit uses the bronze icons
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


def _is_key(item_id) -> bool:
    try:
        from content import ITEMS as _items
        meta = _items.get(item_id) or {}
        if meta.get("type") == "key":
            return True
    except Exception:
        pass
    name = str(item_id or "")
    return (
        "key" in name
        or name.endswith("_seal")
        or name.endswith("_sigil")
        or "rift_sigil" in name
    )


def draw_pedestal_key(surf, tile_rect, item_id, taken=False, label=None, blit_nameplate=None):
    """Stone plinth + oversized key (or bare plinth once taken)."""
    cx, cy = tile_rect.centerx, tile_rect.centery
    tw = tile_rect.w
    # Raised stone base
    base = pygame.Rect(0, 0, max(10, tw * 5 // 8), max(6, tw // 5))
    base.center = (cx, cy + tw // 8)
    pygame.draw.rect(surf, (72, 70, 66), base, border_radius=3)
    pygame.draw.rect(surf, (120, 118, 110), base, 1, border_radius=3)
    top = pygame.Rect(0, 0, max(8, tw // 2), max(4, tw // 10))
    top.midbottom = (cx, base.top + 2)
    pygame.draw.rect(surf, (96, 94, 88), top, border_radius=2)
    if taken or not item_id:
        if blit_nameplate is not None:
            blit_nameplate("Empty pedestal", cx, base.y - 4, (180, 170, 150))
        return False
    # Oversized float so flooded catacomb floors cannot swallow the Tide Key.
    key_rect = pygame.Rect(0, 0, int(tw * 1.55), int(tw * 1.55))
    key_rect.center = (cx, cy - tw // 3)
    draw_ground(surf, key_rect, item_id)
    draw_key_sparkle(surf, key_rect)
    if blit_nameplate is not None:
        from content import ITEMS
        name = label or (ITEMS.get(item_id) or {}).get("name") or "Key"
        blit_nameplate(f"KEY · {name}", cx, key_rect.y - 6, (255, 250, 120))
    return True


def draw_key_sparkle(surf, tile_rect):
    """Bright pulsing halo + orbiting sparks so dungeon keys are hard to miss."""
    now = time.time()
    bob = int(2.5 * math.sin(now * 3.2))
    cx = tile_rect.centerx
    cy = tile_rect.centery - max(2, tile_rect.h // 10) + bob
    pulse = 0.60 + 0.40 * (0.5 + 0.5 * math.sin(now * 5.0))
    size = max(26, int(tile_rect.w * 1.35))
    glow = pygame.Surface((size * 2, size * 2), pygame.SRCALPHA)
    pygame.draw.circle(glow, (255, 190, 60, int(70 * pulse)), (size, size), int(size * 0.72))
    pygame.draw.circle(glow, (255, 220, 100, int(110 * pulse)), (size, size), int(size * 0.48))
    pygame.draw.circle(glow, (255, 245, 170, int(150 * pulse)), (size, size), max(7, size // 4))
    pygame.draw.circle(glow, (255, 255, 240, int(190 * pulse)), (size, size), max(4, size // 7))
    surf.blit(glow, (cx - size, cy - size), special_flags=pygame.BLEND_ADD)
    # Outer spark ring
    for i in range(10):
        ang = now * 4.2 + i * (math.pi * 2 / 10)
        rad = tile_rect.w * (0.42 + 0.14 * math.sin(now * 6.0 + i))
        sx = cx + int(math.cos(ang) * rad)
        sy = cy + int(math.sin(ang) * rad * 0.70)
        lit = 0.5 + 0.5 * math.sin(now * 10.0 + i * 1.1)
        r = 3 if lit > 0.45 else 2
        pygame.draw.circle(surf, (255, 245, 160), (sx, sy), r)
        if lit > 0.55:
            pygame.draw.circle(surf, (255, 255, 255), (sx, sy), 1)
    # Vertical shimmer flashes through the key
    if math.sin(now * 7.5) > 0.35:
        flash = pygame.Surface((max(6, tile_rect.w // 5), max(14, tile_rect.h // 2)), pygame.SRCALPHA)
        flash.fill((255, 255, 220, int(90 * pulse)))
        surf.blit(flash, flash.get_rect(center=(cx, cy)), special_flags=pygame.BLEND_ADD)


def draw_ground(surf, tile_rect, item_id) -> bool:
    """Same icon as inventory, sitting on the tile with a soft shadow. No loot pad."""
    if _keep_old(item_id):
        return False
    key_item = _is_key(item_id)
    if key_item:
        draw_key_sparkle(surf, tile_rect)
    # Keys are oversized on the floor so crypt/void paving cannot swallow them.
    ground_scale = 1.85 if key_item else 1.1
    icon_scale = 1.35 if key_item else 0.78
    ground = _fit(
        f"{item_id}_ground",
        max(8, int(tile_rect.w * ground_scale)),
        max(8, int(tile_rect.h * ground_scale)),
    )
    if ground is not None:
        bob = int(2.0 * math.sin(time.time() * 3.2)) if key_item else 0
        dest = ground.get_rect(center=(tile_rect.centerx, tile_rect.centery + bob))
        surf.blit(ground, dest)
        if key_item:
            draw_key_sparkle(surf, tile_rect)
        return True
    side = max(8, int(tile_rect.w * icon_scale))
    image = _fit(item_id, side, side)
    if image is None:
        return False
    cx = tile_rect.centerx
    foot = tile_rect.centery + tile_rect.h // 5
    if key_item:
        foot += int(2.0 * math.sin(time.time() * 3.2))
    shadow = pygame.Surface((image.get_width(), max(4, image.get_height() // 6)), pygame.SRCALPHA)
    pygame.draw.ellipse(shadow, (0, 0, 0, 80), shadow.get_rect())
    surf.blit(shadow, shadow.get_rect(midbottom=(cx, foot + 2)))
    surf.blit(image, image.get_rect(midbottom=(cx, foot)))
    if key_item:
        draw_key_sparkle(surf, tile_rect)
    return True
