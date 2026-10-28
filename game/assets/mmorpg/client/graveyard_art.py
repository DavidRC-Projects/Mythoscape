"""Scary AI graveyard props: textured perimeter walls + headstone sprites."""
from __future__ import annotations

import os

import pygame

_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets", "graveyard")

_wall_tile: pygame.Surface | None = None
_wall_face: pygame.Surface | None = None
_stones: list[pygame.Surface] = []
_scaled: dict[tuple, pygame.Surface] = {}


def _load():
    global _wall_tile, _wall_face, _stones
    if _wall_tile is not None:
        return
    tile_p = os.path.join(_DIR, "wall_tile.png")
    face_p = os.path.join(_DIR, "wall_face.png")
    _wall_tile = pygame.image.load(tile_p).convert() if os.path.isfile(tile_p) else None
    _wall_face = pygame.image.load(face_p).convert() if os.path.isfile(face_p) else None
    _stones = []
    for i in range(8):
        p = os.path.join(_DIR, f"headstone_{i}.png")
        if os.path.isfile(p):
            _stones.append(pygame.image.load(p).convert_alpha())


def _scale(surf: pygame.Surface, size: tuple[int, int]) -> pygame.Surface:
    key = (id(surf), size)
    hit = _scaled.get(key)
    if hit is None:
        hit = pygame.transform.smoothscale(surf, size)
        _scaled[key] = hit
    return hit


def draw_wall(surf: pygame.Surface, rect: pygame.Rect, wx: int, wy: int) -> bool:
    """Blit dark stone wall tile into a world tile rect. Returns True if drawn."""
    _load()
    if _wall_tile is None:
        return False
    # Pick a stable UV offset from tile coords so neighbours don't look identical.
    tw, th = _wall_tile.get_width(), _wall_tile.get_height()
    ox = (wx * 37) % max(1, tw - 8)
    oy = (wy * 53) % max(1, th - 8)
    # Build a rect-sized patch by scrolling the seamless tile.
    patch = pygame.Surface((rect.w, rect.h))
    for y in range(-oy, rect.h + th, th):
        for x in range(-ox, rect.w + tw, tw):
            patch.blit(_wall_tile, (x, y))
    # Soft top bevel + bottom AO so walls read as low parapets.
    hi = pygame.Surface((rect.w, max(2, rect.h // 5)), pygame.SRCALPHA)
    for i in range(hi.get_height()):
        a = int(70 * (1.0 - i / max(1, hi.get_height() - 1)))
        pygame.draw.line(hi, (210, 200, 180, a), (0, i), (rect.w, i))
    patch.blit(hi, (0, 0), special_flags=pygame.BLEND_RGBA_ADD)
    ao = pygame.Surface((rect.w, max(3, rect.h // 4)), pygame.SRCALPHA)
    for i in range(ao.get_height()):
        a = int(110 * ((i + 1) / ao.get_height()))
        pygame.draw.line(ao, (8, 6, 12, a), (0, i), (rect.w, i))
    patch.blit(ao, (0, rect.h - ao.get_height()))
    # Slight face overlay for depth on taller-looking tiles.
    if _wall_face is not None and rect.h >= 20:
        face = _scale(_wall_face, (rect.w, rect.h))
        face.set_alpha(90)
        patch.blit(face, (0, 0))
    surf.blit(patch, rect.topleft)
    pygame.draw.rect(surf, (18, 14, 20), rect, 1)
    return True


def draw_headstone(surf: pygame.Surface, rect: pygame.Rect, wx: int, wy: int) -> bool:
    """Blit a scary weathered headstone into the grave tile. Returns True if drawn."""
    _load()
    if not _stones:
        return False
    stone = _stones[(wx * 3 + wy * 7) % len(_stones)]
    # Fit inside the tile with a little ground padding.
    max_h = max(8, int(rect.h * 0.92))
    max_w = max(6, int(rect.w * 0.72))
    s = min(max_h / stone.get_height(), max_w / stone.get_width())
    dw = max(4, int(stone.get_width() * s))
    dh = max(6, int(stone.get_height() * s))
    scaled = _scale(stone, (dw, dh))
    x = rect.centerx - dw // 2
    y = rect.bottom - dh - max(1, rect.h // 12)
    # Soft contact shadow
    sh = pygame.Surface((dw + 4, max(3, dh // 8)), pygame.SRCALPHA)
    pygame.draw.ellipse(sh, (0, 0, 0, 110), sh.get_rect())
    surf.blit(sh, (x - 2, rect.bottom - sh.get_height() - 1))
    surf.blit(scaled, (x, y))
    return True


def tint_grounds(surf: pygame.Surface, rect: pygame.Rect) -> None:
    """Dim meadow grass inside the yard so the crypt reads as night-haunted."""
    veil = pygame.Surface((rect.w, rect.h), pygame.SRCALPHA)
    veil.fill((18, 22, 16, 95))
    surf.blit(veil, rect.topleft)
