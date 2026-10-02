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
        image = pygame.transform.smoothscale(raw, (w, h))
        _CACHE[key] = image
    return image


def _frame_file(tile: int, t: float) -> tuple[str, tuple[int, int]] | None:
    meta = _meta()
    images = meta.get("images") or {}
    hi = tile > 40
    still_name = "castle_realm_portal_2x.png" if hi else "castle_realm_portal_1x.png"
    still = images.get(still_name) or {}
    origin = still.get("origin_px") or (0, 0)
    anim = meta.get("anim") or {}
    frames = anim.get("glow") or []
    if frames:
        fps = float(anim.get("fps") or 8)
        index = int(t * fps) % len(frames)
        name = frames[index]
        if not hi:
            stem, dot, ext = name.rpartition(".")
            name = f"{stem}_1x{dot}{ext}" if dot else name
        path = _ROOT / "anim" / name
        if path.is_file():
            return f"anim/{name}", (int(origin[0]), int(origin[1]))
    if still:
        return f"sprites/{still_name}", (int(origin[0]), int(origin[1]))
    return None


def draw(surf, cx, cy, tile, t=0.0):
    """Blit the portal with its tile-centre origin. Returns the sprite top, or None."""
    if not ready():
        return None
    picked = _frame_file(tile, t)
    if picked is None:
        return None
    relative, origin = picked
    scale = float(tile) / (80.0 if tile > 40 else 40.0)
    image = _surface(relative, scale)
    if image is None:
        return None
    left = int(round(cx - origin[0] * scale))
    top = int(round(cy - origin[1] * scale))
    surf.blit(image, (left, top))
    return top
