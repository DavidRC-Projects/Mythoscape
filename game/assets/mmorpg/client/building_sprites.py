"""
Pre-rendered building shells (Blender ortho renders or offline bake).

Put PNGs in client/assets/buildings/{building_id}.png
Optional sidecar JSON: {building_id}.json with pad_x / pad_y / source.

IMPORTANT: shells are always drawn camera-facing into the *view* footprint rect.
Never pygame.rotate the PNG for yaw — that displaces the shell and kills the 3D read.
When yaw != 0, prefer procedural camera-facing shells (or dedicated _n/_e/_s/_w art).
"""
from __future__ import annotations

import json
import os

import pygame

import fx_shadows

_DIR = None
_CACHE = {}  # id -> (surface, meta) | None
_FAILED = set()
_SCALED = {}  # (id, dw, dh) -> scaled surface


def set_buildings_dir(path: str):
    global _DIR
    _DIR = path
    _CACHE.clear()
    _FAILED.clear()
    _SCALED.clear()


def _default_dir():
    here = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(here, "assets", "buildings")


def buildings_dir():
    return _DIR or _default_dir()


def has_sprite(building_id: str) -> bool:
    return get_sprite(building_id) is not None


def get_sprite(building_id: str, yaw: int = 0):
    """
    Return (Surface with SRCALPHA, meta dict) or None.
    Prefers {id}_n/_e/_s/_w.png for camera yaw when present; else {id}.png.
    """
    if not building_id:
        return None
    yaw = int(yaw) % 4
    suffix = ("s", "w", "n", "e")[yaw]  # camera-facing world edge
    # Try yaw-specific first, then default south bake
    for key in (f"{building_id}_{suffix}", building_id if yaw == 0 else None):
        if not key:
            continue
        hit = _load_cached(key)
        if hit is not None:
            return hit
    return None


def _load_cached(building_id: str):
    if building_id in _FAILED:
        return None
    if building_id in _CACHE:
        return _CACHE[building_id]
    folder = buildings_dir()
    png = os.path.join(folder, f"{building_id}.png")
    if not os.path.isfile(png):
        _FAILED.add(building_id)
        _CACHE[building_id] = None
        return None
    try:
        raw = pygame.image.load(png)
        try:
            surf = raw.convert_alpha()
        except pygame.error:
            surf = raw
    except pygame.error:
        _FAILED.add(building_id)
        _CACHE[building_id] = None
        return None
    meta = {
        "pad_x": 0.12,
        "pad_x_right": 0.12,
        "pad_y_top": 0.55,
        "pad_y_bot": 0.08,
        "source": "unknown",
    }
    jpath = os.path.join(folder, f"{building_id}.json")
    if os.path.isfile(jpath):
        try:
            with open(jpath, "r", encoding="utf-8") as f:
                meta.update(json.load(f))
        except (OSError, json.JSONDecodeError):
            pass
    if "depth" in meta and "pad_x_right" not in meta:
        meta["pad_x_right"] = float(meta.get("pad_x", 0.12)) + float(meta["depth"])
    _CACHE[building_id] = (surf, meta)
    return _CACHE[building_id]


def _scaled_sprite(cache_id: str, src: pygame.Surface, dw: int, dh: int) -> pygame.Surface:
    key = (cache_id, dw, dh)
    hit = _SCALED.get(key)
    if hit is not None:
        return hit
    try:
        scaled = pygame.transform.smoothscale(src, (max(1, dw), max(1, dh)))
    except pygame.error:
        scaled = pygame.transform.scale(src, (max(1, dw), max(1, dh)))
    if len(_SCALED) > 64:
        _SCALED.clear()
    _SCALED[key] = scaled
    return scaled


def draw_building_sprite(dest, footprint_rect, building_id: str, alpha: int = 245, yaw: int = 0) -> bool:
    """
    Blit shell locked to footprint_rect (already in view/screen space).
    Only uses baked PNG when it matches camera yaw (or yaw==0 default).
    Returns False if caller should draw a procedural camera-facing shell instead.
    """
    yaw = int(yaw) % 4
    # Without dedicated multi-view art, only the default south bake sits correctly at yaw 0
    packed = get_sprite(building_id, yaw=yaw)
    if not packed:
        return False
    # If we only have the default south bake and camera isn't south-facing, refuse —
    # rotating that PNG causes the displacement / flat look the user reported.
    if yaw != 0:
        yaw_png = os.path.join(buildings_dir(), f"{building_id}_{('s','w','n','e')[yaw]}.png")
        if not os.path.isfile(yaw_png):
            return False

    src, meta = packed
    fw = max(1, footprint_rect.w)
    fh = max(1, footprint_rect.h)
    pad_x = float(meta.get("pad_x", 0.08))
    # Side depth is now inset inside the footprint — little/no right pad needed
    pad_right = float(meta.get("pad_x_right", 0.08))
    pad_top = float(meta.get("pad_y_top", 0.55))
    pad_bot = float(meta.get("pad_y_bot", 0.08))
    dw = int(fw * (1.0 + pad_x + pad_right))
    dh = int(fh * (1.0 + pad_top + pad_bot))
    ox = int(fw * pad_x)
    oy = int(fh * pad_top)
    scaled = _scaled_sprite(f"{building_id}@{yaw}", src, dw, dh)

    fx = footprint_rect.centerx
    fy = footprint_rect.bottom - max(2, fh // 18)
    fx_shadows.draw_contact_ellipse(dest, fx, fy, rx=fw * 0.42, ry=max(3, fh * 0.055), alpha=72)
    fx_shadows.draw_footprint_cast(dest, footprint_rect, height_hint=fh * 0.55, alpha=42)
    fx_shadows.draw_wall_base_ao(dest, footprint_rect, alpha=55)

    blit_x = footprint_rect.x - ox
    blit_y = footprint_rect.y - oy
    # Fully opaque blit — never set_alpha (ghosts the side wall)
    dest.blit(scaled, (blit_x, blit_y))
    return True


def draw_building_cutaway(dest, footprint_rect, building_id: str, yaw: int = 0, alpha: int = 190) -> bool:
    """Interior: ghost walls on the footprint — no PNG rotation."""
    # Procedural cutaway handled by caller when this returns False
    return False
