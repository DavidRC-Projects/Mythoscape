"""Stone-ring sprite for the Castle Realm portal.

Flag off, or missing files, leaves the caller on the old purple circle.
"""
from __future__ import annotations

import json
from pathlib import Path

import pygame

_ROOT = Path(__file__).resolve().parent / "assets" / "castle_realm" / "portal"
_META = None
_CACHE = {}


def _meta():
    global _META
    if _META is None:
        path = _ROOT / "json" / "castle_realm_portal.json"
        if not path.is_file():
            _META = {}
        else:
            _META = json.loads(path.read_text(encoding="utf-8"))
    return _META


def ready() -> bool:
    meta = _meta()
    images = meta.get("images") or {}
    return (_ROOT / "sprites" / "castle_realm_portal_1x.png").is_file() and bool(images)


def _surface(relative: str, scale: float):
    path = _ROOT / relative
    if not path.is_file():
        return None
    key = (relative, round(scale, 4))
    image = _CACHE.get(key)
    if image is None:
        raw = pygame.image.load(str(path)).convert_alpha()
        w = max(1, int(round(raw.get_width() * scale)))
        h = max(1, int(round(raw.get_height() * scale)))
        if w == raw.get_width() and h == raw.get_height():
            image = raw
        elif scale > 1.0:
            # Nearest keeps the ring edges sharp. Smooth upscaling is what blurred it.
            image = pygame.transform.scale(raw, (w, h))
        else:
            image = pygame.transform.smoothscale(raw, (w, h))
        _CACHE[key] = image
    return image


def _frame_file(t: float) -> tuple[str, tuple[int, int]] | None:
    """Always the double-resolution frame. Its pixels are already twice the 1x art."""
    meta = _meta()
    images = meta.get("images") or {}
    still = images.get("castle_realm_portal_2x.png") or {}
    origin = still.get("origin_px") or (0, 0)
    anim = meta.get("anim") or {}
    frames = anim.get("glow") or []
    if frames:
        fps = float(anim.get("fps") or 8)
        name = frames[int(t * fps) % len(frames)]
        path = _ROOT / "anim" / name
        if path.is_file():
            return f"anim/{name}", (int(origin[0]), int(origin[1]))
    if still:
        return "sprites/castle_realm_portal_2x.png", (int(origin[0]), int(origin[1]))
    return None


def draw(surf, cx, cy, tile, t=0.0):
    """Blit the portal at twice its original size. Returns the sprite top, or None.

    The 2x artwork is the source, so this is a same-size or smaller blit at the
    usual zoom steps instead of stretching the small frame.
    """
    if not ready():
        return None
    picked = _frame_file(t)
    if picked is None:
        return None
    relative, origin = picked
    # Old size was the 1x frame at tile/40. The 2x frame at that same factor is twice as big.
    scale = float(tile) / 40.0
    image = _surface(relative, scale)
    if image is None:
        return None
    left = int(round(cx - origin[0] * scale))
    top = int(round(cy - origin[1] * scale))
    surf.blit(image, (left, top))
    return top
