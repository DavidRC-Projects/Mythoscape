"""Low-poly pets and leftover monsters.

Used only when USE_NEW_PETS_AND_MONSTERS is on. Reused creatures point at
the existing skeleton strip and dragon sheets. New ones blit this pack's
previews. Magma Knight stays on the procedural drawer.
"""
from __future__ import annotations

import math
import os

import pygame
from PIL import Image

import anim_strip_sprites
import lowpoly_dragon_sprites as dragons

_DIR = os.path.join(os.path.dirname(__file__), "assets", "sprites", "legacy")
_BG = (158, 153, 143)
_BG_TOL = 28

# sprite argument from draw_pet → preview file
_PET_PREVIEW = {
    "pet_cat": "pet_cat",
    "cat": "pet_cat",
    "pet_dragon_frost": "pet_dragon_frost",
    "dragon_frost": "pet_dragon_frost",
    "pet_dragon_mythic": "pet_dragon_mythic",
    "dragon_mythic": "pet_dragon_mythic",
}
# Existing skeleton warrior sheet, drawn smaller.
_PET_STRIP = {
    "pet_skeleton": 0.65,
    "skeleton_pet": 0.65,
}
# Existing dragon sheets. Crimson uses red, shadow uses black.
_PET_DRAGON = {
    "pet_dragon": "dragon_green",
    "dragon_pet": "dragon_green",
    "pet_dragon_crimson": "dragon_red",
    "dragon_crimson": "dragon_red",
    "pet_dragon_shadow": "dragon_black",
    "dragon_shadow": "dragon_black",
}
_PET_DRAGON_SCALE = 0.55

# content visual → preview file. Magma knight is intentionally absent.
_MONSTER_PREVIEW = {
    "giant_rat": "giant_rat",
    "guard": "guard",
    "mythos_champion": "mythos_champion",
    "magma_slug": "magma_slug",
    "ash_imp": "ash_imp",
    "crucible_beast": "crucible_beast",
}
_HEIGHT = {
    "pet_cat": 1.8,
    "pet_husky": 2.4,
    "pet_dragon_frost": 4.4,
    "pet_dragon_mythic": 4.8,
    "giant_rat": 2.2,
    "guard": 3.96,
    "castle_knight": 4.4,
    "mythos_champion": 4.84,
    "magma_slug": 2.4,
    "ash_imp": 3.0,
    "crucible_beast": 5.4,
}

_cache: dict[str, pygame.Surface] = {}
_scaled: dict[tuple, pygame.Surface] = {}


def handles_monster(visual: str) -> bool:
    return visual in _MONSTER_PREVIEW


def _chroma(path: str) -> pygame.Surface | None:
    cached = _cache.get(path)
    if cached is not None:
        return cached
    if not os.path.isfile(path):
        return None
    image = Image.open(path).convert("RGBA")
    px = image.load()
    br, bg, bb = _BG
    w, h = image.size
    for y in range(h):
        for x in range(w):
            r, g, b, a = px[x, y]
            if abs(r - br) <= _BG_TOL and abs(g - bg) <= _BG_TOL and abs(b - bb) <= _BG_TOL:
                px[x, y] = (0, 0, 0, 0)
    bbox = image.getbbox()
    if bbox:
        image = image.crop(bbox)
    surf = pygame.image.fromstring(image.tobytes(), image.size, "RGBA").convert_alpha()
    _cache[path] = surf
    return surf


def _flip(facing) -> bool:
    if facing == -1:
        return True
    if isinstance(facing, (int, float)) and facing not in ("front", "back") and float(facing) < 0:
        return True
    return False


def _blit_preview(surf, key, cx, cy, tile, facing, hurt, moving=False, t=0.0):
    image = _chroma(os.path.join(_DIR, f"{key}.png"))
    if image is None:
        return False
    draw_h = max(16, int(tile * _HEIGHT.get(key, 3.0)))
    draw_w = max(8, int(image.get_width() * draw_h / max(1, image.get_height())))
    flip = _flip(facing)
    bob = 0
    rock = 0
    if moving:
        # Two feet per cycle. Lift on each step and rock toward the leading paw.
        step = math.sin(float(t) * 8.0)
        bob = int(abs(step) * tile * 0.12)
        rock = int(round(step * 5))
        draw_h = max(16, int(draw_h * (0.94 if abs(step) < 0.35 else 1.0)))
        draw_w = max(8, int(image.get_width() * draw_h / max(1, image.get_height())))
    cache_key = (key, draw_w, draw_h, flip, rock)
    scaled = _scaled.get(cache_key)
    if scaled is None:
        scaled = pygame.transform.smoothscale(image, (draw_w, draw_h))
        if flip:
            scaled = pygame.transform.flip(scaled, True, False)
        if rock:
            scaled = pygame.transform.rotate(scaled, rock)
        _scaled[cache_key] = scaled
        if len(_scaled) > 256:
            _scaled.clear()
    sway = int(math.sin(float(t) * 8.0) * tile * 0.05) if moving else 0
    rect = scaled.get_rect(midbottom=(int(cx + sway), int(cy + tile * 0.35 - bob)))
    surf.blit(scaled, rect)
    if hurt:
        tint = scaled.copy()
        tint.fill((255, 80, 80, 80), special_flags=pygame.BLEND_RGBA_MULT)
        surf.blit(tint, rect)
    return True


def _draw_dragon_key(surf, key, cx, cy, tile, t, attacking, facing, moving):
    sheets = dragons._load_key(key)
    anim = dragons._pick_anim(attacking, moving)
    sheet = sheets.get(anim) or sheets.get("idle")
    if sheet is None:
        return False
    direction = dragons._dir_index(facing)
    frame = dragons._frame_index(anim, t, attacking)
    draw_h = max(16, int(tile * 9.5))
    cell = dragons._cell(sheet, direction, frame)
    scaled = pygame.transform.smoothscale(cell, (draw_h, draw_h))
    rect = scaled.get_rect(midbottom=(int(cx), int(cy + tile * 0.35)))
    surf.blit(scaled, rect)
    return True


_HEAD_FRAC: dict[str, float] = {}


def _cell_top(sprite, cy, tile):
    """Geometric top of the blit rect, and that rect's height. None if unknown."""
    if sprite in _PET_STRIP:
        inner = max(8, int(tile * _PET_STRIP[sprite]))
        tiles_h = anim_strip_sprites._DRAW_TILES.get("skeleton_warrior", 5.2)
        draw_h = max(24, int(inner * tiles_h))
        foot = int(draw_h * 0.24)
        bottom = cy + inner * 0.30 + foot
        return int(bottom - draw_h), draw_h
    if sprite in _PET_DRAGON:
        inner = max(8, int(tile * _PET_DRAGON_SCALE))
        draw_h = max(16, int(inner * 9.5))
        return int(cy + inner * 0.35 - draw_h), draw_h
    preview = _PET_PREVIEW.get(sprite)
    if preview:
        draw_h = max(16, int(tile * _HEIGHT.get(preview, 3.0)))
        return int(cy + tile * 0.35 - draw_h), draw_h
    return None


def _head_frac(sprite) -> float:
    """How far down the blit rect the visible pixels start. Cached."""
    cached = _HEAD_FRAC.get(sprite)
    if cached is not None:
        return cached
    side = 280
    chip = pygame.Surface((side, side), pygame.SRCALPHA)
    cy, tile = 160, 32
    cell = _cell_top(sprite, cy, tile)
    if cell is None or not draw_pet(
        chip, sprite, side // 2, cy, tile, 0.0, facing=1, attacking=-1.0, moving=False,
    ):
        _HEAD_FRAC[sprite] = 0.0
        return 0.0
    geo, draw_h = cell
    bbox = chip.get_bounding_rect()
    frac = 0.0 if draw_h <= 0 else max(0.0, min(0.6, (bbox.top - geo) / draw_h))
    _HEAD_FRAC[sprite] = frac
    return frac


def pet_top_y(sprite, cy, tile) -> int | None:
    """Screen y of the visible top of the pet, at rest."""
    if sprite in ("pet_husky", "husky"):
        return int(cy - tile * 1.15)
    cell = _cell_top(sprite, cy, tile)
    if cell is None:
        return None
    geo, draw_h = cell
    return int(geo + draw_h * _head_frac(sprite))


def blit_pet_icon(surf, sprite, rect, t, facing=1) -> bool:
    """Draw a pet fitted inside rect, feet toward the bottom. Nothing spills out."""
    side = 220
    chip = pygame.Surface((side, side), pygame.SRCALPHA)
    if not draw_pet(
        chip, sprite, side // 2, side - 8, 36, t,
        facing=facing, attacking=-1.0, moving=False,
    ):
        return False
    bbox = chip.get_bounding_rect()
    if bbox.width < 2 or bbox.height < 2:
        return False
    cropped = chip.subsurface(bbox).copy()
    pad = 3
    avail_w = max(1, rect.w - pad * 2)
    avail_h = max(1, rect.h - pad * 2)
    scale = min(avail_w / cropped.get_width(), avail_h / cropped.get_height())
    fitted = pygame.transform.smoothscale(
        cropped,
        (max(1, int(cropped.get_width() * scale)), max(1, int(cropped.get_height() * scale))),
    )
    dest = fitted.get_rect(midbottom=(rect.centerx, rect.bottom - pad))
    surf.blit(fitted, dest)
    return True


def draw_pet(surf, sprite, cx, cy, tile, t, hurt=False, attacking=-1.0, moving=False, facing=1) -> bool:
    if sprite in _PET_STRIP:
        return anim_strip_sprites.draw_anim_strip_monster(
            surf, "skeleton", cx, cy, max(8, int(tile * _PET_STRIP[sprite])), t,
            hurt=hurt, attacking=attacking, facing=facing, moving=moving,
        )
    if sprite in _PET_DRAGON:
        return _draw_dragon_key(
            surf, _PET_DRAGON[sprite], cx, cy, max(8, int(tile * _PET_DRAGON_SCALE)), t,
            attacking, facing, moving,
        )
    preview = _PET_PREVIEW.get(sprite)
    if preview:
        if sprite in ("pet_cat", "cat") and facing in ("front", "back"):
            return False
        return _blit_preview(surf, preview, cx, cy, tile, facing, hurt, moving=moving, t=t)
    return False


def draw_monster(surf, visual, cx, cy, tile, t, hurt=False, attacking=0.0, facing=1, moving=False) -> bool:
    preview = _MONSTER_PREVIEW.get(visual)
    if not preview:
        return False
    return _blit_preview(surf, preview, cx, cy, tile, facing, hurt)
