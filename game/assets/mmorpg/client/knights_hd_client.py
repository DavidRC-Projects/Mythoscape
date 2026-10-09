"""HD attackable knights (Mythoscape): 6 knight types with idle/walk/attack/hit/death states.

Permanent always-on. Replaces legacy knight visuals for these IDs:
knight, shadow_knight, knight_captain_vorn, barrow_knight, sir_aldric, magma_knight
"""
from __future__ import annotations

import json
import os
from typing import Optional

import pygame

_DIR = os.path.normpath(os.path.join(
    os.path.dirname(__file__), "..", "..", "knights_hd", "assets",
))

KNIGHTS_HD = {
    "knight",
    "shadow_knight",
    "knight_captain_vorn",
    "barrow_knight",
    "sir_aldric",
    "magma_knight",
}

_META = {}
_IMAGES = {}
_CACHE_LIMIT = 512


def handles(mtype: str) -> bool:
    """Check if this module handles the given monster type."""
    return mtype in KNIGHTS_HD


def _load_meta(knight_id: str) -> dict:
    """Load meta.json for a knight."""
    if knight_id not in _META:
        path = os.path.join(_DIR, knight_id, "meta.json")
        if not os.path.isfile(path):
            _META[knight_id] = {}
            return {}
        with open(path, encoding="utf-8") as f:
            _META[knight_id] = json.load(f)
    return _META[knight_id]


def _load_image(path: str):
    """Load and cache a sprite image."""
    if path in _IMAGES:
        return _IMAGES[path]
    if not os.path.isfile(path):
        _IMAGES[path] = None
        return None
    img = pygame.image.load(path).convert_alpha()
    _IMAGES[path] = img
    
    # Clear cache if it gets too large
    if len(_IMAGES) > _CACHE_LIMIT:
        keys = list(_IMAGES.keys())
        for k in keys[:len(keys) // 4]:  # Remove 25%
            _IMAGES.pop(k, None)
    
    return img


def _scaled(path: str, size: int, base: int):
    """Get a scaled version of an image."""
    img = _load_image(path)
    if img is None:
        return None
    if size == base:
        return img
    
    cache_key = (path, size)
    if cache_key not in _IMAGES:
        w = max(1, int(round(img.get_width() * size / float(base))))
        h = max(1, int(round(img.get_height() * size / float(base))))
        _IMAGES[cache_key] = pygame.transform.smoothscale(img, (w, h))
    
    return _IMAGES[cache_key]


def _facing_str(face) -> str:
    """Convert game facing to sprite facing string."""
    if face == "back":
        return "n"
    if face == "front":
        return "s"
    if isinstance(face, (int, float)):
        return "w" if face < 0 else "e"
    return "s"


def _frame_for_state(meta: dict, state: str, t: float, attacking: float, hit_t: float, death_t: float) -> int:
    """Compute the frame index for a given state and time."""
    if state == "idle":
        return int(((t * 1.5) % 1) * 4) % 4
    elif state == "walk":
        return int(((t * 1.15) % 1) * 8) % 8
    elif state == "attack":
        # Use frame_starts from meta
        frame_starts = meta.get("states", {}).get("attack", {}).get("frame_starts", [0, .14, .30, .42, .60, .80])
        for i in range(len(frame_starts) - 1, -1, -1):
            if attacking >= frame_starts[i]:
                return i
        return 0
    elif state == "hit":
        return min(2, int(hit_t / 0.12))
    elif state == "death":
        return min(5, int(death_t / 0.15))
    return 0


def draw(
    screen,
    mtype: str,
    cx: int,
    foot_y: int,
    size: int,
    t: float,
    facing=1,
    moving=False,
    attacking=-1.0,
    hurt=False,
    hit_t=-1.0,
    death_t=-1.0,
    alpha=255,
) -> bool:
    """Draw an HD knight. Returns True if drawn, False if not handled."""
    if mtype not in KNIGHTS_HD:
        return False
    
    meta = _load_meta(mtype)
    if not meta or not meta.get("complete"):
        return False
    
    # Pick scale tag
    tag, base = ("2x", 80) if size >= 80 else ("1x", 40)
    k = size / float(base)
    
    # Determine state
    if death_t >= 0:
        state = "death"
    elif attacking >= 0:
        state = "attack"
    elif 0 <= hit_t < 0.36:
        state = "hit"
    elif moving:
        state = "walk"
    else:
        state = "idle"
    
    # Get facing
    face_str = _facing_str(facing)
    
    # Get frame
    frame = _frame_for_state(meta, state, t, attacking, hit_t, death_t)
    
    # Load sprite
    sprite_path = os.path.join(_DIR, mtype, f"sprite_{tag}", state, face_str, f"f{frame:02d}.png")
    img = _scaled(sprite_path, size, base)
    
    if img is None:
        return False
    
    # Get feet anchor
    feet_px = meta.get("feet_px", {}).get(tag, [64, 132] if tag == "1x" else [128, 264])
    fx, fy = feet_px[0] * k, feet_px[1] * k
    
    # Position
    left = int(cx - fx)
    top = int(foot_y - fy)
    
    # Apply hurt tint if needed
    if hurt:
        hurt_surf = img.copy()
        hurt_surf.fill((255, 80, 80, 80), special_flags=pygame.BLEND_RGBA_MULT)
        img = hurt_surf
    
    # Apply alpha if needed
    if alpha < 255:
        img = img.copy()
        img.set_alpha(alpha)
    
    screen.blit(img, (left, top))
    return True


def head_top_dy(mtype: str, size: int) -> int:
    """Get the Y offset from feet to head top (for HP bar positioning)."""
    meta = _load_meta(mtype)
    if not meta:
        return -size
    
    offset_1x = meta.get("healthbar_y_offset_1x", -40)
    return int(offset_1x * size / 40.0)


def anchor(mtype: str, size: int, facing, state: str, frame: int, name: str) -> tuple[int, int]:
    """Get an anchor point offset from feet (for hitsplats, weapon tips, etc.)."""
    meta = _load_meta(mtype)
    if not meta:
        return (0, 0)
    
    # Get scale factor
    tag, base = ("2x", 80) if size >= 80 else ("1x", 40)
    k = size / float(base)
    
    # Look up anchor in 4x coordinates
    face_str = _facing_str(facing)
    anchor_key = f"{state}/{face_str}/{frame:02d}"
    anchors_4x = meta.get("anchors_4x", {})
    
    if anchor_key in anchors_4x and name in anchors_4x[anchor_key]:
        ax_4x, ay_4x = anchors_4x[anchor_key][name]
        # Convert 4x to current scale
        scale_4x = 4.0
        ax = ax_4x * k / scale_4x
        ay = ay_4x * k / scale_4x
        return (int(ax), int(ay))
    
    return (0, 0)


def portrait(mtype: str, height: int = 96):
    """Get a scaled portrait for UI."""
    if mtype not in KNIGHTS_HD:
        return None
    
    path = os.path.join(_DIR, mtype, "portrait_bust_512.png")
    img = _load_image(path)
    if img is None:
        return None
    
    cache_key = (path, "portrait", height)
    if cache_key not in _IMAGES:
        w = max(1, int(round(img.get_width() * height / float(img.get_height()))))
        _IMAGES[cache_key] = pygame.transform.smoothscale(img, (w, height))
    
    return _IMAGES[cache_key]
