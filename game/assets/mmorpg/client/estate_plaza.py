"""King's Row Estate plaza: painted flagstone walks to every house door,
street lamps and planters, and a lamp glow that follows the day/night phase.

Purely visual. The estate tiles stay GRASS on the server (walkable), so the
walks never change collision. If the plaza art is missing or fails to load,
nothing is drawn and the estate looks as it did before.
"""
from __future__ import annotations

import math
import os

try:
    import pygame
except Exception:  # pragma: no cover - layout helpers work without pygame
    pygame = None

_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets", "housing", "estate_plaza")
ORIGIN = (0, 97)          # world tile at plaza_ground_hd.png pixel (0, 0)
SIZE = (45, 58)           # tiles covered by the ground art
BASE = 40                 # px per tile in the art

# Walk rectangles in world tiles, inclusive (x0, y0, x1, y1).
WALKS = (
    (12, 97, 15, 114),    # entry lane from the north road
    (12, 115, 15, 118),   # walk-in entrance through the north curtain
    (3, 117, 42, 118),    # inner walk behind the north curtain
    (3, 113, 42, 114),    # north walk
    (24, 116, 24, 129),   # lane between Cedar Townhouse and Crown Villa
    (40, 116, 41, 150),   # east lane
    (2, 130, 43, 131),    # north promenade (front doors of the north row)
    (9, 128, 9, 129),     # King's Folly door
    (20, 129, 20, 129),   # Cedar Townhouse door
    (32, 129, 32, 129),   # Crown Villa door
    (14, 132, 15, 150),   # lane west of Meadow House
    (24, 132, 25, 150),   # lane east of Meadow House
    (37, 132, 38, 150),   # lane east of Stonehaven Row
    (2, 149, 43, 150),    # south promenade
    (20, 147, 20, 148),   # Meadow House door
    (8, 149, 8, 149),     # Riverview Estate door (exit tile on the promenade)
    (31, 149, 31, 149),   # Stonehaven Row door
)
ROSETTE = (22.5, 132.9, 2.25)   # centre x, centre y, radius (tiles)

# Props: (kind, world x, world y) — x/y are the foot point in tiles.
LAMPS = (
    (6.0, 132.2), (12.6, 132.2), (27.0, 132.2), (36.0, 132.2), (42.6, 132.2),
    (6.0, 151.3), (18.0, 151.3), (28.0, 151.3), (35.0, 151.3), (42.6, 151.3),
    (17.0, 112.6), (31.0, 112.6), (11.4, 109.5), (16.6, 109.5), (6.0, 103.5), (28.0, 103.5), (38.0, 103.5),
    (19.7, 133.6), (25.3, 133.6),
)
PLANTERS = (
    (3.2, 132.6), (10.5, 132.6), (29.5, 132.6), (39.4, 132.6),
    (3.2, 151.4), (12.5, 151.4), (26.8, 151.4), (39.4, 151.4),
    (21.0, 112.6), (35.5, 112.6), (8.0, 112.6),
    (3.2, 103.6), (33.0, 103.6), (41.0, 103.6),
)


def walk_tiles():
    """Every tile the painted walks cover (rectangles plus the rosette)."""
    out = set()
    for x0, y0, x1, y1 in WALKS:
        for y in range(y0, y1 + 1):
            for x in range(x0, x1 + 1):
                out.add((x, y))
    cx, cy, r = ROSETTE
    for y in range(int(cy - r) - 1, int(cy + r) + 2):
        for x in range(int(cx - r) - 1, int(cx + r) + 2):
            if (x + 0.5 - cx) ** 2 + (y + 0.5 - cy) ** 2 <= r * r:
                out.add((x, y))
    return out


def glow_strength(phase):
    return {"night": 1.0, "dusk": 0.55, "dawn": 0.3}.get(phase or "day", 0.0)


_CACHE = {}
_LAST = {}


def _raw(name):
    key = ("raw", name)
    if key not in _CACHE:
        img = None
        path = os.path.join(_DIR, name)
        if pygame is not None and os.path.isfile(path):
            try:
                img = pygame.image.load(path).convert_alpha()
            except Exception:
                img = None
        _CACHE[key] = img
    return _CACHE[key]


def _scaled(name, tile):
    key = (name, int(tile))
    if key not in _CACHE:
        img = _raw(name)
        if img is not None and int(tile) != BASE:
            w = max(1, round(img.get_width() * tile / BASE))
            h = max(1, round(img.get_height() * tile / BASE))
            img = pygame.transform.smoothscale(img, (w, h))
        _CACHE[key] = img
    return _CACHE[key]


def available():
    return _raw("plaza_ground_hd.png") is not None


def _phase(client):
    return ((getattr(client, "env", None) or {}).get("phase")) or "day"


def queue(client, draw_list, cam_x, cam_y, tile):
    """Queue the plaza ground decal and the lamp / planter props."""
    if getattr(client, "dungeon", None) or not available():
        return False
    screen = client.screen
    _LAST.update(cam=(cam_x, cam_y), tile=tile, client=client)
    sx, sy = client.world_to_view_offset(ORIGIN[0], ORIGIN[1], cam_x, cam_y)
    vw, vh = screen.get_width() / tile, screen.get_height() / tile
    if sx > vw + 2 or sy > vh + 2 or sx + SIZE[0] < -2 or sy + SIZE[1] < -2:
        return False

    def ground(_x=sx * tile, _y=sy * tile):
        img = _scaled("plaza_ground_hd.png", tile)
        if img is not None:
            screen.blit(img, (_x, _y))

    draw_list.append((-(10 ** 9) + 1, 0, ground))
    lamp_name = "lamp_lit.png" if glow_strength(_phase(client)) > 0.4 else "lamp_day.png"
    for name, spots in ((lamp_name, LAMPS), ("planter.png", PLANTERS)):
        for wx, wy in spots:
            px, py = client.world_to_view_offset(wx, wy, cam_x, cam_y)

            def prop(_n=name, _x=px * tile, _y=py * tile):
                img = _scaled(_n, tile)
                if img is not None:
                    screen.blit(img, (_x - img.get_width() / 2, _y - img.get_height()))

            draw_list.append((py * tile, 1, prop))
    return True


def draw_glow(client):
    """Warm lamp light, drawn after the night tint so it reads as light."""
    strength = glow_strength(_phase(client))
    if strength <= 0 or _LAST.get("client") is not client or getattr(client, "dungeon", None):
        return
    tile = _LAST["tile"]
    cam_x, cam_y = _LAST["cam"]
    glow = _scaled("glow.png", tile)
    if glow is None:
        return
    if strength < 1.0:
        glow = glow.copy()
        glow.fill((int(255 * strength),) * 3 + (255,), special_flags=pygame.BLEND_RGBA_MULT)
    head = 3.05   # lamp head height above the foot, tiles
    w, h = client.screen.get_size()
    for wx, wy in LAMPS:
        px, py = client.world_to_view_offset(wx, wy - head, cam_x, cam_y)
        x, y = px * tile - glow.get_width() / 2, py * tile - glow.get_height() / 2
        if -glow.get_width() < x < w and -glow.get_height() < y < h:
            client.screen.blit(glow, (x, y), special_flags=pygame.BLEND_RGB_ADD)

