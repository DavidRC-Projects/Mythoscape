"""Pygame adapter: blit pre-baked low-poly dragon sprite sheets.

Sheets from monsters_lowpoly/tools/render_sprites.py:
  <key>_<anim>.png — rows = 8 directions, cols = 8 frames, cell = SIZE x SIZE.
  Direction 0 = facing camera (south); rows increase clockwise.

No Panda3D at runtime.
"""
from __future__ import annotations

import os

import pygame

# Combat type "dragon" (Adamant Dragon) -> green low-poly sheet set.
DRAGON_TYPE_MAP = {
    "dragon": "dragon_green",
}

ANIMS = ("idle", "walk", "attack", "death")
DIRS = 8
FRAMES = 8
CELL = 128

# facing from client: 1=east/right, -1=west/left, "front", "back"
# Sheet rows: 0=S(front), then CCW in Panda heading → 2=E(right), 4=N(back), 6=W(left)
_FACING_TO_DIR = {
    "front": 0,
    1: 2,
    "back": 4,
    -1: 6,
}

_SPRITES_DIR = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    "assets", "sprites", "dragons",
)

_cache: dict[str, dict[str, pygame.Surface]] = {}
_scaled: dict[tuple, pygame.Surface] = {}


def _load_key(key: str) -> dict[str, pygame.Surface]:
    if key in _cache:
        return _cache[key]
    sheets = {}
    for anim in ANIMS:
        path = os.path.join(_SPRITES_DIR, f"{key}_{anim}.png")
        if not os.path.isfile(path):
            continue
        sheets[anim] = pygame.image.load(path).convert_alpha()
    _cache[key] = sheets
    return sheets


def sheet_key_for_monster_type(mtype: str) -> str | None:
    return DRAGON_TYPE_MAP.get(mtype)


def click_radius_tiles(mtype: str) -> int:
    """How far from the foot tile a click still selects this monster.

    Keep this tight (1) so nearby ground clicks still walk away instead of
    re-engaging the oversized dragon sprite.
    """
    if sheet_key_for_monster_type(mtype):
        return 1
    return 0


def _pick_anim(attacking: float, moving: bool) -> str:
    # attacking is 0..1 while a swing is active, or < 0 when idle.
    # Do not use truthiness — progress can be 0.0 at the start of a swing.
    if attacking is not None and attacking >= 0.0:
        return "attack"
    if moving:
        return "walk"
    return "idle"


def _dir_index(facing) -> int:
    if facing in _FACING_TO_DIR:
        return _FACING_TO_DIR[facing]
    try:
        return _FACING_TO_DIR[1 if float(facing) >= 0 else -1]
    except (TypeError, ValueError):
        return 0


def _frame_index(anim: str, t: float, attacking: float) -> int:
    if anim == "attack" and attacking is not None and attacking >= 0.0:
        return min(FRAMES - 1, max(0, int(float(attacking) * FRAMES)))
    # idle ~2.0s, walk ~0.9s per cycle (matches bake ANIM_LEN)
    period = 2.0 if anim == "idle" else 0.9
    return int((t % period) / period * FRAMES) % FRAMES


def _cell(sheet: pygame.Surface, direction: int, frame: int) -> pygame.Surface:
    x = frame * CELL
    y = direction * CELL
    return sheet.subsurface(pygame.Rect(x, y, CELL, CELL))


def draw_lowpoly_dragon(
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
    """Blit a low-poly dragon frame. Returns False if sheets missing (caller falls back).

    attacking: 0..1 swing progress while attacking; pass < 0 when not attacking.
    foe_cx: optional screen-x of the foe — shifts the sprite away so side-by-side reads clearly.
    drop_down: shift the sprite south a few tiles so it shares the player's baseline.
    """
    key = sheet_key_for_monster_type(mtype)
    if key is None:
        return False
    sheets = _load_key(key)
    anim = _pick_anim(attacking, moving)
    sheet = sheets.get(anim) or sheets.get("idle")
    if sheet is None:
        return False

    direction = _dir_index(facing)
    frame = _frame_index(anim, t, attacking)

    # Same on-screen height as the hill giant (anim_strip_sprites giant_hill).
    draw_h = max(24, int(tile * 9.5))
    draw_w = draw_h
    cache_key = (key, anim, direction, frame, draw_w, draw_h)
    scaled = _scaled.get(cache_key)
    if scaled is None:
        cell = _cell(sheet, direction, frame)
        scaled = pygame.transform.smoothscale(cell, (draw_w, draw_h))
        _scaled[cache_key] = scaled
        if len(_scaled) > 512:
            _scaled.clear()

    # Stable offsets only (no attack-toggled bob).
    ox = 0
    if foe_cx is not None and abs(foe_cx - cx) > 1:
        ox = int(tile * 0.8) if cx >= foe_cx else -int(tile * 0.8)
    # Drop a few tiles so the large sprite lines up with the player on the same row.
    oy = int(tile * 2.5) if drop_down else 0
    rect = scaled.get_rect(midbottom=(int(cx + ox), int(cy + tile * 0.35 + oy)))
    surf.blit(scaled, rect)
    return True
