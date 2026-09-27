"""Pygame adapter: blit monster animation strips from server/monsters/anim_strips.

Each strip is 5 frames side-by-side (320×320), baked by anim_test.py:
  0=idle, 1=walk-a, 2=walk-b, 3=attack, 4=death

Strips are front-facing only — we flip horizontally for west. No Panda3D at runtime.
Unused strip keys (no content monster yet) are left unmapped for later.
"""
from __future__ import annotations

import os

import pygame
from PIL import Image

# content.py monster type → anim_strip basename (without _anim.png)
TYPE_MAP = {
    "goblin": "goblin_grunt",
    "skeleton": "skeleton_warrior",
    "big_skeleton": "skeleton_mage",
    "spider": "spider_giant",
    "giant": "giant_hill",
    "wolf": "wolf_grey",
    "ember_wolf": "wolf_dire",
    "shade": "barrow_wraith",
    "crypt_ghoul": "rot_ghoul",
    "void_imp": "void_spawn",
    "void_horror": "void_brute",
    "obsidian_colossus": "stone_golem",
}

# Relative height in tiles (player ~2 tiles, dragon sheet ~6.5).
# Giants stay the tallest thing on the map.
_DRAW_TILES = {
    "goblin_grunt": 4.8,
    "skeleton_warrior": 5.2,
    "skeleton_mage": 5.8,
    "spider_giant": 4.6,
    "wolf_grey": 4.2,
    "wolf_dire": 4.8,
    "barrow_wraith": 5.4,
    "rot_ghoul": 5.2,
    "void_spawn": 4.4,
    "void_brute": 7.6,
    "stone_golem": 8.0,
    "giant_hill": 9.5,
}

FRAMES = 5
CELL = 320
# Bake background from ShowBase set_background_color(0.62, 0.60, 0.56)
_BG = (158, 153, 143)
_BG_TOL = 28

_STRIPS_DIR = os.path.normpath(os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    "..", "server", "monsters", "anim_strips",
))

_cache: dict[str, list[pygame.Surface]] = {}
_scaled: dict[tuple, pygame.Surface] = {}


def sheet_key_for_monster_type(mtype: str) -> str | None:
    return TYPE_MAP.get(mtype)


def click_radius_tiles(mtype: str) -> int:
    """Soft click radius for oversized strip sprites (keep tight to allow flee)."""
    if sheet_key_for_monster_type(mtype):
        return 1
    return 0


def _chroma_pil(cell: Image.Image) -> pygame.Surface:
    """Knock out the flat bake background so strips composite cleanly."""
    rgba = cell.convert("RGBA")
    px = rgba.load()
    br, bg, bb = _BG
    w, h = rgba.size
    for y in range(h):
        for x in range(w):
            r, g, b, a = px[x, y]
            if (abs(r - br) <= _BG_TOL
                    and abs(g - bg) <= _BG_TOL
                    and abs(b - bb) <= _BG_TOL):
                px[x, y] = (0, 0, 0, 0)
    return pygame.image.fromstring(rgba.tobytes(), rgba.size, "RGBA").convert_alpha()


def _load_key(key: str) -> list[pygame.Surface] | None:
    if key in _cache:
        return _cache[key]
    path = os.path.join(_STRIPS_DIR, f"{key}_anim.png")
    if not os.path.isfile(path):
        _cache[key] = None  # type: ignore[assignment]
        return None
    strip = Image.open(path).convert("RGB")
    frames = []
    for i in range(FRAMES):
        cell = strip.crop((i * CELL, 0, (i + 1) * CELL, CELL))
        frames.append(_chroma_pil(cell))
    _cache[key] = frames
    return frames


def _pick_frame(attacking: float, moving: bool, t: float) -> int:
    if attacking is not None and attacking >= 0.0:
        return 3  # attack
    if moving:
        # Alternate walk-a / walk-b ~6 fps
        return 1 + (int(t * 6.0) % 2)
    return 0  # idle


def draw_anim_strip_monster(
    surf: pygame.Surface,
    mtype: str,
    cx: float,
    cy: float,
    tile: int,
    t: float,
    hurt: bool = False,
    attacking: float = -1.0,
    facing=1,
    moving: bool = False,
    foe_cx: float | None = None,
    drop_down: bool = False,
) -> bool:
    """Blit one strip frame. Returns False if missing (caller falls back).

    foe_cx: optional screen-x of the foe — shifts the sprite so side-by-side reads clearly.
    drop_down: shift south so the tall sprite shares the player's baseline.
    """
    key = sheet_key_for_monster_type(mtype)
    if key is None:
        return False
    frames = _load_key(key)
    if not frames:
        return False

    fi = _pick_frame(attacking, moving, t)
    cell = frames[fi]
    tiles_h = _DRAW_TILES.get(key, 3.4)
    draw_h = max(24, int(tile * tiles_h))
    draw_w = draw_h
    flip = facing == -1 or (
        isinstance(facing, (int, float)) and facing not in ("front", "back") and float(facing) < 0
    )
    cache_key = (key, fi, draw_w, draw_h, flip)
    scaled = _scaled.get(cache_key)
    if scaled is None:
        scaled = pygame.transform.smoothscale(cell, (draw_w, draw_h))
        if flip:
            scaled = pygame.transform.flip(scaled, True, False)
        _scaled[cache_key] = scaled
        if len(_scaled) > 512:
            _scaled.clear()

    # Stable offsets only (no attack-toggled bob) — matches dragon lineup.
    # Strips are full camera frames; the feet sit above the cell bottom.
    ox = 0
    if foe_cx is not None and abs(foe_cx - cx) > 1:
        ox = int(tile * 0.55) if cx >= foe_cx else -int(tile * 0.55)
    foot = int(draw_h * 0.24)
    oy = int(tile * 0.35) if drop_down else 0
    rect = scaled.get_rect(midbottom=(int(cx + ox), int(cy + tile * 0.30 + oy + foot)))
    if hurt:
        tint = scaled.copy()
        tint.fill((255, 80, 80, 70), special_flags=pygame.BLEND_RGBA_MULT)
        surf.blit(scaled, rect)
        surf.blit(tint, rect)
    else:
        surf.blit(scaled, rect)
    return True
