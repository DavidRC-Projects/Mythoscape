"""2D interior props from the props pack.

Yaw 0 uses the match-width sprite (same width as the old drawer).
Yaw 1–3 use the baked s/w/n/e views, scaled to that same width.
_SIZE multiplies that width for props that should read larger than the old icons.
"""
from __future__ import annotations

import json
import os

import pygame

_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets", "props")
_YAW = ("s", "w", "n", "e")
# json/<key>.json → game.old_base_offset_px (contact shadow below the tile centre)
_BASE_PX = {
    "bank_booth": 25,
    "vault_chest": 9,
    "furnace": 30,
    "anvil": 21,
    "workbench": 13,
    "weapon_rack": 13,
    "quench_bucket": 8,
    "wishing_well": 69,
    "fountain": 15,
    "market_stall": 13,
    "shop_counter": 13,
    "hearth": 17,
    "barrel": 10,
    "throne": 16,
    "banner_stand": 11,
    "banquet_table": 12,
    "castle_chair": 10,
    "brazier": 9,
    "cage_cat": 12,
    "cage_skeleton": 12,
    "pet_bed": 8,
}
# Match-width is the old icon size. These read as furniture next to the player.
# The wishing well's old drawing is already several tiles wide, so it stays nearer that size.
_SIZE = {
    "bank_booth": 1.75,
    "furnace": 1.75,
    "anvil": 1.75,
    "workbench": 1.75,
    "weapon_rack": 1.75,
    "quench_bucket": 1.75,
    "wishing_well": 1.15,
    "fountain": 1.75,
    "market_stall": 1.75,
    "shop_counter": 1.75,
    "hearth": 1.75,
    "barrel": 1.75,
    "throne": 1.75,
    "banner_stand": 1.75,
    "banquet_table": 1.75,
    "castle_chair": 1.75,
    "brazier": 1.75,
    "cage_cat": 1.75,
    "cage_skeleton": 1.75,
    "pet_bed": 1.75,
    "goblin_campfire": 1.75,
    "goblin_loot": 1.75,
    "wolf_bone_pile": 1.75,
    "wolf_den_bed": 1.75,
    "spider_cocoons": 1.75,
    "spider_egg_sacs": 1.75,
    "giant_throne": 1.75,
    "giant_table": 1.75,
    "dragon_hoard": 1.75,
    "dragon_egg_nest": 1.75,
    "crypt_sarcophagus": 1.75,
    "crypt_candelabra": 1.75,
    "void_altar": 1.75,
    "void_crystals": 1.75,
}

_meta: dict[str, dict | None] = {}
_images: dict[str, pygame.Surface | None] = {}
_scaled: dict[tuple, pygame.Surface] = {}


def _pack(key: str):
    if key in _meta:
        return _meta[key]
    path = os.path.join(_DIR, f"{key}.json")
    if not os.path.isfile(path):
        _meta[key] = None
        return None
    with open(path, encoding="utf-8") as f:
        _meta[key] = json.load(f)
    return _meta[key]


def _image(filename: str):
    if filename in _images:
        return _images[filename]
    path = os.path.join(_DIR, filename)
    if not os.path.isfile(path):
        _images[filename] = None
        return None
    _images[filename] = pygame.image.load(path).convert_alpha()
    return _images[filename]


def _entry(key: str, filename: str):
    pack = _pack(key)
    if not pack:
        return None
    info = (pack.get("images") or {}).get(filename)
    img = _image(filename)
    if not info or img is None:
        return None
    return img, info


def facing_yaw(facing, camera_yaw=0) -> int:
    """Sprite index for a chair. facing 1 faces east, -1 faces west."""
    if facing in (1, "1", "e", "east"):
        base = 3
    elif facing in (-1, "-1", "w", "west"):
        base = 1
    elif facing in ("back", "n", "north", 2):
        base = 2
    else:
        base = 0
    return (base + int(camera_yaw or 0)) % 4


def draw_prop(surf, key, cx, cy, tile, yaw=0) -> bool:
    """Blit a prop. Returns False if the sprite is missing (caller uses the old drawer)."""
    yaw = int(yaw or 0) % 4
    match = _entry(key, f"{key}_match.png")
    if match is None:
        # Dungeon props have no old drawing, so the true-scale sprite is the base.
        match = _entry(key, f"{key}_1x.png")
    if match is None:
        return False
    match_img, match_info = match
    size = _SIZE.get(key, 1.0)
    if yaw == 0:
        img, info = match_img, match_info
        scale = float(tile) / 40.0 * size
    else:
        yaw_name = f"{key}_{_YAW[yaw]}_1x.png"
        yaw_entry = _entry(key, yaw_name)
        if yaw_entry is None:
            img, info = match_img, match_info
            scale = float(tile) / 40.0 * size
        else:
            img, info = yaw_entry
            # Keep the same on-screen width as the match sprite at this tile size.
            match_w = max(1, int(round(match_img.get_width() * float(tile) / 40.0 * size)))
            scale = match_w / float(img.get_width())
    dw = max(1, int(round(img.get_width() * scale)))
    dh = max(1, int(round(img.get_height() * scale)))
    cache_key = (key, yaw, dw, dh)
    scaled = _scaled.get(cache_key)
    if scaled is None:
        scaled = pygame.transform.smoothscale(img, (dw, dh))
        _scaled[cache_key] = scaled
    ox, oy = info["origin_px"]
    base = _BASE_PX.get(key, 0) * float(tile) / 40.0
    left = int(round(cx - ox * scale))
    top = int(round(cy + base - oy * scale))
    surf.blit(scaled, (left, top))
    return True
