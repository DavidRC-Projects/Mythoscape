"""Petaldeep mouth, full-screen room plates, and open north arch."""
from __future__ import annotations

import math
import os
import time

import pygame

import world_map as wm

_PATH = os.path.join(os.path.dirname(__file__), "assets", "petaldeep", "mouth.png")
_ROOMS = os.path.join(os.path.dirname(__file__), "assets", "petaldeep", "rooms")
MOUTH = (8, 65)
INFECT_R = 3
_cache = {}


def active(client):
    d = getattr(client, "dungeon", None) or {}
    return d.get("id") == "petaldeep"


def _extra(client):
    return (getattr(client, "dungeon", None) or {}).get("petaldeep") or {}


def _sprite():
    mtime = 0.0
    try:
        mtime = os.path.getmtime(_PATH)
    except OSError:
        pass
    hit = _cache.get("img")
    if hit is not None and _cache.get("mtime") == mtime:
        return hit
    if not os.path.isfile(_PATH):
        _cache["img"] = None
        _cache["mtime"] = mtime
        return None
    try:
        img = pygame.image.load(_PATH).convert_alpha()
    except Exception:
        img = None
    _cache.clear()
    _cache["img"] = img
    _cache["mtime"] = mtime
    return img


def _scaled(tile, height_tiles):
    img = _sprite()
    if img is None:
        return None
    key = ("scaled", tile, height_tiles)
    hit = _cache.get(key)
    if hit is not None:
        return hit
    h = max(8, int(tile * height_tiles))
    w = max(8, int(img.get_width() * (h / img.get_height())))
    surf = pygame.transform.smoothscale(img, (w, h))
    _cache[key] = surf
    return surf


def _room_plate(art, pixel_w, pixel_h):
    key = ("room_px", art, pixel_w, pixel_h)
    hit = _cache.get(key)
    if hit is not None or key in _cache:
        return hit
    path = os.path.join(_ROOMS, f"{art}.png")
    if not os.path.isfile(path):
        _cache[key] = None
        return None
    try:
        raw = pygame.image.load(path).convert()
    except Exception:
        _cache[key] = None
        return None
    surf = pygame.transform.smoothscale(raw, (max(8, int(pixel_w)), max(8, int(pixel_h))))
    _cache[key] = surf
    return surf


def infects(x, y):
    return max(abs(int(x) - MOUTH[0]), abs(int(y) - MOUTH[1])) <= INFECT_R


def infect_surface(surf):
    key = ("infect", id(surf))
    hit = _cache.get(key)
    if hit is not None:
        return hit
    out = surf.copy()
    out.fill((35, 0, 55, 0), special_flags=pygame.BLEND_RGBA_ADD)
    out.fill((190, 160, 210, 255), special_flags=pygame.BLEND_RGBA_MULT)
    _cache[key] = out
    return out


def queue_corner(client, draw_list, cam_x, cam_y, tile):
    return


def _portal_glow(screen, cx, cy, tile, t):
    pulse = 0.55 + 0.45 * math.sin(t * 3.2)
    for i, (mul, alpha) in enumerate(((2.4, 55), (1.7, 90), (1.1, 140))):
        r = max(6, int(tile * mul * (0.85 + 0.15 * pulse)))
        glow = pygame.Surface((r * 2, r * 2), pygame.SRCALPHA)
        colour = (255, 90 + i * 20, 220, int(alpha * (0.7 + 0.3 * pulse)))
        pygame.draw.circle(glow, colour, (r, r), r)
        screen.blit(glow, (cx - r, cy - int(tile * 1.55) - r), special_flags=pygame.BLEND_ADD)


def draw_mouth(screen, cx, cy, tile, t=None):
    if t is None:
        t = time.time()
    _portal_glow(screen, cx, cy, tile, t)
    surf = _scaled(tile, 5.2)
    if surf is None:
        return cy - tile
    rect = surf.get_rect()
    rect.midbottom = (cx, cy + tile // 5)
    screen.blit(surf, rect)
    rim = max(10, tile // 2)
    pygame.draw.ellipse(
        screen, (255, 170, 255),
        pygame.Rect(cx - rim, cy - int(tile * 1.7), rim * 2, max(8, tile)),
        2,
    )
    return rect.top


def draw_exit(screen, cx, cy, tile):
    surf = _scaled(tile, 2.6)
    if surf is None:
        return False
    rect = surf.get_rect()
    rect.midbottom = (cx, cy + tile // 4)
    screen.blit(surf, rect)
    return True


def draw_room_backdrop(client, cam_x, cam_y, tile):
    """Paint the AI hall plate across the map panel (and chat strip) — no void."""
    if not active(client):
        return False
    art = _extra(client).get("art") or "room1_orchard"
    try:
        import client as client_mod
        panel_w = int(getattr(client_mod, "MAP_W", 900))
        panel_h = int(getattr(client_mod, "MAP_H", 640))
        screen_h = int(getattr(client_mod, "SCREEN_H", panel_h + 80))
    except Exception:
        panel_w, panel_h, screen_h = 900, 640, 720
    w = int(getattr(client, "world_w", 0) or 22)
    h = int(getattr(client, "world_h", 0) or 16)
    # Cover map + chat strip so the hall never ends in a black band.
    px_w = max(panel_w, w * tile)
    px_h = max(screen_h, h * tile)
    plate = _room_plate(art, px_w, px_h)
    if plate is None:
        return False
    sx, sy = client.world_to_view_offset(0, 0, cam_x, cam_y)
    if w * tile >= panel_w - tile and h * tile >= panel_h - tile:
        client.screen.blit(plate, (int(sx * tile), int(sy * tile)))
    else:
        client.screen.blit(plate, (0, 0))
    return True


def draw_tile(client, rect, tile_id, wx, wy, t):
    """Very light wash — plate carries the look; sprites stay readable."""
    if not active(client):
        return False
    extra = _extra(client)
    door = {(int(p[0]), int(p[1])) for p in (extra.get("door") or extra.get("arch") or []) if len(p) >= 2}
    on_door = (int(wx), int(wy)) in door
    if tile_id == wm.WALL:
        # Soft rim only — do not paint a heavy box over the plate.
        veil = pygame.Surface(rect.size, pygame.SRCALPHA)
        veil.fill((14, 8, 20, 55))
        client.screen.blit(veil, rect.topleft)
        return True
    # Open north arch: gentle pulse so the way deeper is obvious.
    if on_door:
        glow = pygame.Surface(rect.size, pygame.SRCALPHA)
        pulse = 0.55 + 0.45 * math.sin((t or time.time()) * 3.0)
        glow.fill((180, 90, 255, int(40 + 35 * pulse)))
        client.screen.blit(glow, rect.topleft, special_flags=pygame.BLEND_ADD)
        return True
    # Floor stays almost clear so the plate fills the eye.
    return True


def handle_click(client, tx, ty):
    extra = _extra(client)
    door = {(int(p[0]), int(p[1])) for p in (extra.get("door") or extra.get("arch") or []) if len(p) >= 2}
    if (int(tx), int(ty)) not in door:
        return False
    # Always walk onto the arch — halls are never sealed.
    goals = {(int(tx), int(ty))}
    client.walk_and_act(goals, {"type": "DUNGEON_INTERACT", "x": int(tx), "y": int(ty)})
    return True
