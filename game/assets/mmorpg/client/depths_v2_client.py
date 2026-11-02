"""The Depths v2 tile art: crypt floors, bone walls, sarcophagi, and grasping hands.

Fog, zone banners, parchment, and the boss bar are the shared Void overlay.
This module only draws what is crypt-specific — plus AI zone plates.
"""
import math
import os
import sys
import time

import pygame

import procedural_sprites_finished as sprites
import prop_sprites
import rs_style as rs

_ZONES = os.path.join(os.path.dirname(__file__), "assets", "depths", "zones")
# Bumped when zone / wall / water art changes so a long-lived client drops stale sheets.
_ART_REV = 8
_plate_cache = {}
# Water repeats every N tiles so pools read as one continuous surface.
_WATER_PERIOD = 16

FLOOR_PAL = {
    "chapel": ((96, 98, 88), (86, 88, 78), (104, 106, 94), (78, 80, 72)),
    "ossuary": ((112, 104, 88), (100, 92, 78), (120, 112, 96), (92, 84, 72)),
    "catacomb": ((70, 80, 70), (62, 72, 62), (78, 88, 76), (56, 66, 58)),
    "tomb": ((84, 86, 90), (76, 78, 82), (92, 94, 98), (70, 72, 76)),
    "mausoleum": ((88, 82, 74), (78, 72, 66), (96, 90, 80), (70, 64, 58)),
    "wyrm": ((92, 76, 60), (82, 68, 54), (100, 84, 66), (74, 60, 48)),
    "arena": ((64, 60, 58), (58, 54, 52), (70, 66, 62), (52, 48, 46)),
    "bridge": ((150, 140, 116), (140, 130, 108), (158, 148, 122), (132, 122, 100)),
}
WALL_PAL = {
    "chapel": (70, 74, 66), "ossuary": (120, 110, 90), "catacomb": (52, 62, 54), "tomb": (62, 64, 70),
    "mausoleum": (66, 60, 54), "wyrm": (70, 56, 44), "arena": (44, 40, 40), "bridge": (40, 36, 34),
}
CANDLE = (255, 190, 90)
ZONE_LIGHT = {
    "chapel": (255, 186, 110, 16),
    "ossuary": (214, 196, 160, 12),
    "catacomb": (30, 110, 100, 20),
    "tomb": (150, 170, 210, 16),
    "mausoleum": (196, 176, 140, 12),
    "wyrm": (180, 90, 40, 18),
    "bridge": (8, 10, 16, 26),
    "arena": (120, 24, 24, 18),
}
_fog_cache = {}


def _seed(x, y, n):
    fn = getattr(sprites, "_seeded", None)
    if fn:
        return fn(x, y, n)
    return ((x * 13 + y * 7 + n * 3) % 1000) / 1000.0


def _tile(client):
    main = sys.modules.get("__main__")
    if main is not None and hasattr(main, "TILE"):
        return main.TILE
    return 32


def _glow(surf, cx, cy, r, col, a):
    r = max(2, int(r))
    g = pygame.Surface((r * 2, r * 2), pygame.SRCALPHA)
    for k in range(4):
        pygame.draw.circle(g, (*col, int(a * (k + 1) / 4)), (r, r), int(r * (1 - k * 0.22)))
    surf.blit(g, (int(cx - r), int(cy - r)))


# Overlay corridors share floor with the room they cross. They must not paint
# a second background through the middle of an area.
_OVERLAY_ZONES = {"stair", "bridge"}
# One mirrored repeat of an area's floor. Small enough that the stone reads as
# pavement, large enough that the repeat is not a stamp.
_AREA_PERIOD = 8


def style_at(d, x, y):
    decor = (d.get("decor") or {}).get(f"{x},{y}", "")
    if decor in ("bridge", "pit", "deep", "shallow"):
        return "bridge"
    found = "arena"
    for zone in d.get("zones") or []:
        if zone.get("id") == "stair":
            continue
        x0, y0, x1, y1 = zone["rect"]
        if x0 <= x <= x1 and y0 <= y <= y1:
            found = zone.get("style") or found
            break
    return found


def floor_style(d, x, y):
    """The area that owns this floor. Overlay zones do not cut a new room."""
    for zone in (d or {}).get("zones") or []:
        if zone.get("id") in _OVERLAY_ZONES:
            continue
        rect = zone.get("rect") or ()
        if len(rect) != 4:
            continue
        x0, y0, x1, y1 = (int(v) for v in rect)
        if x0 <= int(x) <= x1 and y0 <= int(y) <= y1:
            return zone.get("style") or "arena"
    return None


def _load_tex(name):
    """Load a named AI texture once (wall / water / zone plate source)."""
    key = ("raw", _ART_REV, name)
    hit = _plate_cache.get(key)
    if hit is not None or key in _plate_cache:
        return hit
    path = os.path.join(_ZONES, f"{name}.png")
    if not os.path.isfile(path):
        _plate_cache[key] = None
        return None
    try:
        # convert() → opaque Surface so walls/water never punch through.
        raw = pygame.image.load(path).convert()
    except Exception:
        _plate_cache[key] = None
        return None
    _plate_cache[key] = raw
    return raw


def _cell(name, tile_px, wx, wy):
    """Opaque tile-sized blit from an AI texture, stable per world cell."""
    key = ("cell", _ART_REV, name, int(tile_px))
    sheet = _plate_cache.get(key)
    if sheet is None and key not in _plate_cache:
        raw = _load_tex(name)
        if raw is None:
            _plate_cache[key] = None
            return None
        tw = max(8, int(tile_px))
        # 8×8 tile sheet so neighbouring cells look varied, not one stamp.
        sheet = pygame.transform.smoothscale(raw, (tw * 8, tw * 8))
        _plate_cache[key] = sheet
    if sheet is None:
        return None
    tw = max(8, int(tile_px))
    sx = (int(wx) % 8) * tw
    sy = (int(wy) % 8) * tw
    return sheet.subsurface(pygame.Rect(sx, sy, tw, tw))


def _blit_cell(screen, rect, name, wx, wy):
    cell = _cell(name, rect.w, wx, wy)
    if cell is None:
        return False
    screen.blit(cell, rect.topleft)
    return True


def _water_cell(name, tile_px, wx, wy):
    """Continuous AI water sample — adjacent cells share one seamless sheet."""
    period = _WATER_PERIOD
    tw = max(8, int(tile_px))
    key = ("water", _ART_REV, name, tw, period)
    sheet = _plate_cache.get(key)
    if sheet is None and key not in _plate_cache:
        raw = _load_tex(name)
        if raw is None:
            _plate_cache[key] = None
            return None
        sheet = pygame.transform.smoothscale(raw, (tw * period, tw * period))
        _plate_cache[key] = sheet
    if sheet is None:
        return None
    sx = (int(wx) % period) * tw
    sy = (int(wy) % period) * tw
    return sheet.subsurface(pygame.Rect(sx, sy, tw, tw))


def _blit_continuous(screen, rect, name, wx, wy):
    """World-aligned sample so neighbouring tiles are one surface."""
    cell = _water_cell(name, rect.w, wx, wy)
    if cell is None:
        return False
    screen.blit(cell, rect.topleft)
    return True


def _water_edges(d, wx, wy):
    dec = (d or {}).get("decor") or {}

    def wet(x, y):
        return dec.get(f"{x},{y}") in ("deep", "shallow")

    return {
        "N": not wet(wx, wy - 1),
        "S": not wet(wx, wy + 1),
        "W": not wet(wx - 1, wy),
        "E": not wet(wx + 1, wy),
    }


def _caustic_sheet(tw):
    """One seamless light-web. Two scrolls of it are the whole pool's caustics.

    Still dungeon water (a pond, not a sea) is a dark body plus a slow caustic
    network. The network is shared in world space so neighbouring tiles are
    one surface.
    """
    tw = max(8, int(tw))
    key = ("caustic", tw)
    hit = _plate_cache.get(key)
    if hit is not None or key in _plate_cache:
        return hit
    try:
        import numpy as np
        side = 8 * tw
        axis = np.linspace(0, 2 * np.pi, side, endpoint=False)
        x, y = np.meshgrid(axis, axis, indexing="ij")
        field = (
            np.sin(x * 2.0 + y * 1.2)
            + np.sin(x * 3.0 - y * 1.7)
            + 0.55 * np.sin((x + y) * 4.0)
        )
        field = (field - field.min()) / (float(field.max() - field.min()) + 1e-6)
        field = np.clip((field - 0.58) * 2.6, 0, 1) ** 1.5
        rgb = np.zeros((side, side, 3), np.uint8)
        rgb[..., 0] = (field * 46).astype(np.uint8)
        rgb[..., 1] = (field * 88).astype(np.uint8)
        rgb[..., 2] = (field * 92).astype(np.uint8)
        surf = pygame.Surface((side, side))
        pygame.surfarray.blit_array(surf, rgb)
        surf = surf.convert()
    except Exception:
        surf = None
    _plate_cache[key] = surf
    return surf


def _blit_wrapped(dest, dest_rect, sheet, sx, sy, flags=0):
    """Blit a window of a tiling sheet, wrapping so the scroll has no seam."""
    side_w, side_h = sheet.get_size()
    tw, th = dest_rect.size
    sx %= side_w
    sy %= side_h
    w1 = min(tw, side_w - sx)
    h1 = min(th, side_h - sy)

    def piece(dx, dy, w, h, ssx, ssy):
        dest.blit(
            sheet, (dest_rect.x + dx, dest_rect.y + dy),
            pygame.Rect(ssx, ssy, w, h), special_flags=flags,
        )

    piece(0, 0, w1, h1, sx, sy)
    if w1 < tw:
        piece(w1, 0, tw - w1, h1, 0, sy)
    if h1 < th:
        piece(0, h1, w1, th - h1, sx, 0)
    if w1 < tw and h1 < th:
        piece(w1, h1, tw - w1, th - h1, 0, 0)


def _solid(size, color):
    key = ("solid", size, color)
    hit = _plate_cache.get(key)
    if hit is None and key not in _plate_cache:
        surf = pygame.Surface(size)
        surf.fill(color)
        hit = surf.convert()
        _plate_cache[key] = hit
    return hit


def _shore_strip(length, depth, vertical):
    """Soft wet lip. Feathered, so a straight shore is one line, not a tile box."""
    length = max(1, int(length))
    depth = max(2, int(depth))
    key = ("shore", length, depth, bool(vertical))
    hit = _plate_cache.get(key)
    if hit is not None or key in _plate_cache:
        return hit
    if vertical:
        surf = pygame.Surface((depth, length), pygame.SRCALPHA)
        for i in range(depth):
            fade = (1.0 - i / float(depth)) ** 2
            pygame.draw.line(surf, (176, 206, 200, int(90 * fade)), (i, 0), (i, length - 1))
    else:
        surf = pygame.Surface((length, depth), pygame.SRCALPHA)
        for i in range(depth):
            fade = (1.0 - i / float(depth)) ** 2
            pygame.draw.line(surf, (176, 206, 200, int(90 * fade)), (0, i), (length - 1, i))
    _plate_cache[key] = surf
    return surf


def _shore_edge(length, depth, side):
    """Cached wet lip for one side, so a shoreline is not rebuilt every frame."""
    key = ("shore-edge", int(length), int(depth), side)
    hit = _plate_cache.get(key)
    if hit is not None or key in _plate_cache:
        return hit
    base = _shore_strip(length, depth, side in ("W", "E"))
    if base is None:
        _plate_cache[key] = None
        return None
    if side == "S":
        hit = pygame.transform.flip(base, False, True)
    elif side == "E":
        hit = pygame.transform.flip(base, True, False)
    else:
        hit = base
    _plate_cache[key] = hit
    return hit


def _draw_crypt_water(screen, rect, wx, wy, t, d, deep=True):
    """Pond water: depth tint, one scrolling caustic field, foam only on stone.

    Shallow water keeps the floor (the stone is the 'refraction'). Deep water
    is the same colour with the floor gone, so a channel reads as one body.
    """
    tw, th = rect.w, rect.h
    now = t or time.time()
    if deep:
        pygame.draw.rect(screen, (5, 18, 24), rect)
    else:
        # Cool the stone, then lay a flat wash over it. The floor still tints
        # the pool, but its grout no longer reads as a grid of water tiles.
        tint = _solid(rect.size, (80, 130, 138))
        if tint is not None:
            screen.blit(tint, rect.topleft, special_flags=pygame.BLEND_RGB_MULT)
        veil = _plate_cache.get(("water-veil", rect.size))
        if veil is None:
            veil = pygame.Surface(rect.size, pygame.SRCALPHA)
            veil.fill((8, 36, 44, 128))
            _plate_cache[("water-veil", rect.size)] = veil
        screen.blit(veil, rect.topleft)
    sheet = _caustic_sheet(tw)
    if sheet is not None:
        # Two layers, different speed and direction — the usual stand-in for
        # two scrolling normals. Still water drifts; it does not stripe.
        _blit_wrapped(
            screen, rect, sheet,
            int(wx) * tw + int(now * 14),
            int(wy) * th + int(now * 9),
            flags=pygame.BLEND_RGB_ADD,
        )
        if deep:
            _blit_wrapped(
                screen, rect, sheet,
                int(wx) * tw - int(now * 8),
                int(wy) * th + int(now * 11),
                flags=pygame.BLEND_RGB_ADD,
            )
    edges = _water_edges(d, wx, wy)
    lip = max(4, tw // 7)
    if edges.get("N"):
        screen.blit(_shore_edge(tw, lip, "N"), rect.topleft)
    if edges.get("S"):
        screen.blit(_shore_edge(tw, lip, "S"), (rect.left, rect.bottom - lip))
    if edges.get("W"):
        screen.blit(_shore_edge(th, lip, "W"), rect.topleft)
    if edges.get("E"):
        screen.blit(_shore_edge(th, lip, "E"), (rect.right - lip, rect.top))


def _chasm_bounds(d):
    """World rects for the drop and the stone span, including its parapets."""
    chasm = (d or {}).get("chasm") or {}
    pit = tuple(int(v) for v in (chasm.get("pit") or (12, 79, 54, 91)))
    deck = tuple(int(v) for v in (chasm.get("deck") or (29, 78, 37, 91)))
    return pit, deck


def _span_sheet(name, tile_px, bounds):
    """One AI plate mapped across a world rect so a span reads as a single place."""
    x0, y0, x1, y1 = (int(v) for v in bounds)
    tw = max(8, int(tile_px))
    key = ("span", _ART_REV, name, tw, x0, y0, x1, y1)
    sheet = _plate_cache.get(key)
    if sheet is not None or key in _plate_cache:
        return sheet
    raw = _load_tex(name)
    if raw is None:
        _plate_cache[key] = None
        return None
    pw = max(tw, (x1 - x0 + 1) * tw)
    ph = max(tw, (y1 - y0 + 1) * tw)
    sheet = pygame.transform.smoothscale(raw, (pw, ph))
    _plate_cache[key] = sheet
    return sheet


def _blit_span(screen, rect, name, wx, wy, bounds):
    x0, y0, x1, y1 = (int(v) for v in bounds)
    if not (x0 <= int(wx) <= x1 and y0 <= int(wy) <= y1):
        return False
    sheet = _span_sheet(name, rect.w, bounds)
    if sheet is None:
        return False
    tw = rect.w
    sx = (int(wx) - x0) * tw
    sy = (int(wy) - y0) * tw
    area = pygame.Rect(sx, sy, tw, rect.h)
    if not sheet.get_rect().contains(area):
        return False
    screen.blit(sheet, rect.topleft, area)
    return True


# How many tile-rows the roadway dissolves into the room on either end.
_LIP_TILES = 3


def _lip_alphas(tile_h, wy, y0, y1):
    """0 shows the room, 255 is solid bridge. Smooth over the lips."""
    span = _LIP_TILES * tile_h
    alphas = []
    for py in range(tile_h):
        north = (int(wy) - y0) * tile_h + py
        south = (y1 - int(wy)) * tile_h + (tile_h - 1 - py)
        near = min(north, south)
        if near >= span:
            alphas.append(255)
        else:
            t = near / float(span)
            t = t * t * (3.0 - 2.0 * t)
            alphas.append(int(255 * t))
    return alphas


def _zone_origin(d, style):
    for zone in (d or {}).get("zones") or []:
        if zone.get("style") == style or zone.get("id") == style:
            rect = zone.get("rect") or ()
            if len(rect) == 4:
                return int(rect[0]), int(rect[1])
    return None


def _blit_zone_tile(screen, rect, style, wx, wy, origin):
    """One tile of a room plate, aligned with that zone's backdrop."""
    sheet = _zone_sheet(style, rect.w)
    if sheet is None or not origin:
        return False
    ox, oy = origin
    sw, sh = sheet.get_size()
    tw, th = rect.w, rect.h
    sx = int((int(wx) - ox) * tw) % sw
    sy = int((int(wy) - oy) * th) % sh

    def chunk(dx, dy, w, h, ssx, ssy):
        screen.blit(sheet, (rect.x + dx, rect.y + dy), pygame.Rect(ssx, ssy, w, h))

    w1 = min(tw, sw - sx)
    h1 = min(th, sh - sy)
    chunk(0, 0, w1, h1, sx, sy)
    if w1 < tw:
        chunk(w1, 0, tw - w1, h1, 0, sy)
    if h1 < th:
        chunk(0, h1, w1, th - h1, sx, 0)
    if w1 < tw and h1 < th:
        chunk(w1, h1, tw - w1, th - h1, 0, 0)
    return True


def _blit_zone_tile_alpha(screen, rect, style, wx, wy, origin, alpha):
    """Lay another room's floor over this tile so the join is a fade, not a cut."""
    alpha = int(alpha)
    if alpha <= 4:
        return False
    tile = pygame.Surface(rect.size, pygame.SRCALPHA)
    if not _blit_zone_tile(tile, tile.get_rect(), style, wx, wy, origin):
        return False
    tile.set_alpha(alpha)
    screen.blit(tile, rect.topleft)
    return True


def _fade_into_rooms(screen, rect, wx, wy, d, here):
    """Bleed neighbouring room floors across the boundary."""
    wx, wy = int(wx), int(wy)
    for zone in (d or {}).get("zones") or []:
        if zone.get("id") in ("stair", "bridge"):
            continue
        style = zone.get("style") or ""
        if not style or style == here or style == "bridge":
            continue
        bounds = zone.get("rect") or ()
        if len(bounds) != 4:
            continue
        x0, y0, x1, y1 = (int(v) for v in bounds)
        if x0 <= wx <= x1 and y0 <= wy <= y1:
            continue
        if wx < x0:
            dx = x0 - wx
        elif wx > x1:
            dx = wx - x1
        else:
            dx = 0
        if wy < y0:
            dy = y0 - wy
        elif wy > y1:
            dy = wy - y1
        else:
            dy = 0
        dist = max(dx, dy)
        if dist < 1 or dist > _LIP_TILES:
            continue
        strength = 1.0 - (dist - 1) / float(_LIP_TILES)
        alpha = int(170 * strength * strength)
        _blit_zone_tile_alpha(screen, rect, style, wx, wy, (x0, y0), alpha)


def _blit_deck(screen, rect, wx, wy, deck, d):
    """Stone span. The ends fade into the mausoleum and the throne room."""
    x0, y0, x1, y1 = (int(v) for v in deck)
    alphas = _lip_alphas(rect.h, wy, y0, y1)
    if min(alphas) >= 255:
        return _blit_span(screen, rect, "bridge_deck", wx, wy, deck)
    north = (int(wy) - y0) <= (y1 - int(wy))
    style = "mausoleum" if north else "arena"
    if _blit_zone_tile(screen, rect, style, wx, wy, _zone_origin(d, style)):
        wash = pygame.Surface(rect.size, pygame.SRCALPHA)
        wash.fill((12, 10, 12, 28))
        screen.blit(wash, rect.topleft)
    sheet = _span_sheet("bridge_deck", rect.w, deck)
    if sheet is None:
        return False
    tw = rect.w
    sx = (int(wx) - x0) * tw
    sy = (int(wy) - y0) * tw
    area = pygame.Rect(sx, sy, tw, rect.h)
    if not sheet.get_rect().contains(area):
        return False
    cell = pygame.Surface(rect.size, pygame.SRCALPHA)
    cell.blit(sheet, (0, 0), area)
    fade = pygame.Surface(rect.size, pygame.SRCALPHA)
    for py, alpha in enumerate(alphas):
        if alpha:
            pygame.draw.line(fade, (255, 255, 255, alpha), (0, py), (tw - 1, py))
    cell.blit(fade, (0, 0), special_flags=pygame.BLEND_RGBA_MULT)
    screen.blit(cell, rect.topleft)
    return True


def _blit_full(screen, rect, name):
    """Scale a whole texture onto one tile (doors), not a random crop."""
    tw, th = max(8, rect.w), max(8, rect.h)
    key = ("full", _ART_REV, name, tw, th)
    surf = _plate_cache.get(key)
    if surf is None and key not in _plate_cache:
        raw = _load_tex(name)
        if raw is None:
            _plate_cache[key] = None
            return False
        surf = pygame.transform.smoothscale(raw, (tw, th))
        _plate_cache[key] = surf
    if surf is None:
        return False
    screen.blit(surf, rect.topleft)
    return True


def _fold_tile(i, period):
    """Mirror a tile index so a repeat turns back on itself instead of cutting."""
    span = period * 2
    i = int(i) % span
    if i < 0:
        i += span
    if i >= period:
        i = span - 1 - i
    return i


def _area_sheet(style, tile_px):
    """One area's floor, scaled to a short mirrored repeat. Same art everywhere in that area."""
    tw = max(8, int(tile_px))
    key = ("area", _ART_REV, style, tw)
    sheet = _plate_cache.get(key)
    if sheet is not None or key in _plate_cache:
        return sheet
    raw = _load_tex(style)
    if raw is None:
        _plate_cache[key] = None
        return None
    side = _AREA_PERIOD * tw
    sw, sh = raw.get_size()
    scale = side / float(min(sw, sh))
    dw = max(side, int(round(sw * scale)))
    dh = max(side, int(round(sh * scale)))
    big = pygame.transform.smoothscale(raw, (dw, dh))
    crop = pygame.Rect((dw - side) // 2, (dh - side) // 2, side, side)
    sheet = big.subsurface(crop).copy()
    _plate_cache[key] = sheet
    return sheet


def _blit_area(screen, rect, style, wx, wy):
    """World-aligned sample of this area's floor. Neighbouring tiles continue it."""
    sheet = _area_sheet(style, rect.w)
    if sheet is None:
        pal = FLOOR_PAL.get(style)
        if not pal:
            return False
        pygame.draw.rect(screen, pal[0], rect)
        return True
    tw = rect.w
    sx = _fold_tile(wx, _AREA_PERIOD) * tw
    sy = _fold_tile(wy, _AREA_PERIOD) * tw
    screen.blit(sheet, rect.topleft, pygame.Rect(sx, sy, tw, rect.h))
    return True


def _blit_area_alpha(screen, rect, style, wx, wy, alpha):
    alpha = int(alpha)
    if alpha <= 4:
        return False
    tile = pygame.Surface(rect.size, pygame.SRCALPHA)
    if not _blit_area(tile, tile.get_rect(), style, wx, wy):
        return False
    tile.set_alpha(alpha)
    screen.blit(tile, rect.topleft)
    return True


def _merge_areas(screen, rect, wx, wy, d, here):
    """Dissolve into the next area over a few tiles. The interior of an area stays one floor."""
    wx, wy = int(wx), int(wy)
    best_style = None
    best_alpha = 0
    for dist in range(1, _LIP_TILES + 1):
        strength = 1.0 - (dist - 1) / float(_LIP_TILES)
        alpha = int(150 * strength * strength)
        if alpha <= best_alpha:
            continue
        for dx in range(-dist, dist + 1):
            for dy in range(-dist, dist + 1):
                if max(abs(dx), abs(dy)) != dist:
                    continue
                other = floor_style(d, wx + dx, wy + dy)
                if not other or other == here:
                    continue
                best_style = other
                best_alpha = alpha
                break
            if best_style and best_alpha == alpha:
                break
    if best_style:
        _blit_area_alpha(screen, rect, best_style, wx, wy, best_alpha)


def _zone_sheet(style, tile_px):
    """Room art at its real aspect, repeating. Never stretched to the zone."""
    tw = max(8, int(tile_px))
    key = ("zsheet", _ART_REV, style, tw)
    sheet = _plate_cache.get(key)
    if sheet is not None or key in _plate_cache:
        return sheet
    raw = _load_tex(style)
    if raw is None:
        _plate_cache[key] = None
        return None
    sw, sh = raw.get_size()
    # Wide enough that a crypt room shows the floor once, not a repeating stamp.
    dw = 64 * tw
    dh = max(tw, int(round(dw * (sh / float(sw)))))
    sheet = pygame.transform.smoothscale(raw, (dw, dh))
    _plate_cache[key] = sheet
    return sheet


def draw_zone_backdrop(client, cam_x, cam_y, tile):
    """Dark the panel. Each area's floor is drawn with the tiles, not as a slab per room.

    Painting a zone rectangle here is what cut the stair and the silk nest through
    the rooms as hard bands. Floors now share one texture for the whole area.
    """
    d = getattr(client, "dungeon", None) or {}
    if d.get("v2") != "depths":
        return False
    try:
        import client as client_mod
        panel_w = int(getattr(client_mod, "MAP_W", 900))
        panel_h = int(getattr(client_mod, "MAP_H", 640))
        screen_h = int(getattr(client_mod, "SCREEN_H", panel_h + 80))
    except Exception:
        panel_w, panel_h, screen_h = 900, 640, 720
    client.screen.fill((8, 6, 8), pygame.Rect(0, 0, panel_w, screen_h))
    return True


def draw_tile(client, rect, tile_id, wx, wy, t):
    """Each area is one continuous floor. Walls, water, and the bridge cover it."""
    import world_map as wm
    d = client.dungeon
    decor = (d.get("decor") or {}).get(f"{wx},{wy}", "")
    style = style_at(d, wx, wy)
    hands = _hands_here(d, wx, wy)

    if decor == "pit":
        pit, _deck = _chasm_bounds(d)
        if not _blit_span(client.screen, rect, "abyss", wx, wy, pit):
            pygame.draw.rect(client.screen, (6, 6, 8), rect)
        return
    if decor == "deep":
        _draw_crypt_water(client.screen, rect, wx, wy, t, d, deep=True)
        return
    if decor == "bridge":
        _pit, deck = _chasm_bounds(d)
        if not _blit_deck(client.screen, rect, wx, wy, deck, d):
            pygame.draw.rect(client.screen, (120, 116, 108), rect)
        if hands:
            draw_grasping_hands(client.screen, rect, t, telegraph=True)
        return

    if decor == "rail":
        _pit, deck = _chasm_bounds(d)
        if not _blit_deck(client.screen, rect, wx, wy, deck, d):
            if not _blit_full(client.screen, rect, "bridge_rail"):
                pygame.draw.rect(client.screen, (70, 68, 64), rect)
        if int(wy) % 4 == 0:
            _draw_bridge_post(client.screen, rect)
        return

    if tile_id == wm.WALL:
        # Secret / skull niches read as a trapped stone door, not a wall crop.
        if decor in ("secret", "skull"):
            if not _blit_full(client.screen, rect, "trapped_door"):
                pygame.draw.rect(client.screen, (48, 46, 44), rect)
                draw_skull_niche(client.screen, rect.inflate(-rect.w // 6, -rect.h // 6), t)
            return
        if decor and decor.startswith("seal"):
            if not _blit_full(client.screen, rect, "trapped_door"):
                pygame.draw.rect(client.screen, (40, 36, 34), rect)
            seal = decor.split(":")[-1]
            held = _keys_held(client).get(seal)
            col = (140, 255, 170) if held else (255, 150, 120)
            pygame.draw.rect(client.screen, col, rect, 2)
            return
        # Stone courses: the photo is the face, the joints make it built wall.
        if not _blit_continuous(client.screen, rect, "wall", wx, wy):
            base = WALL_PAL.get(style, (40, 36, 34))
            pygame.draw.rect(client.screen, base, rect)
        shade = pygame.Surface(rect.size, pygame.SRCALPHA)
        shade.fill((0, 0, 0, 36))
        client.screen.blit(shade, rect.topleft)
        _draw_courses(client.screen, rect, wx, wy)
        if decor == "gate":
            face = rect.inflate(-max(3, rect.w // 7), -max(3, rect.h // 7))
            pygame.draw.rect(client.screen, (95, 72, 28), face)
            pygame.draw.rect(client.screen, (230, 190, 100), rect, 3)
        return

    # One floor for the whole area. The next area dissolves in at the join.
    area = floor_style(d, wx, wy) or style
    if not _blit_area(client.screen, rect, area, wx, wy):
        pygame.draw.rect(client.screen, FLOOR_PAL.get(area, FLOOR_PAL["arena"])[0], rect)
    _merge_areas(client.screen, rect, wx, wy, d, area)
    veil = _plate_cache.get(("floor-veil", rect.size))
    if veil is None:
        veil = pygame.Surface(rect.size, pygame.SRCALPHA)
        veil.fill((8, 6, 8, 36))
        _plate_cache[("floor-veil", rect.size)] = veil
    client.screen.blit(veil, rect.topleft)
    if decor == "shallow":
        _draw_crypt_water(client.screen, rect, wx, wy, t, d, deep=False)
    _prop(client, rect, decor, style, wx, wy, t)
    if hands:
        draw_grasping_hands(client.screen, rect, t, telegraph=True)


def _hands_here(d, wx, wy):
    for mark in d.get("telegraphs") or []:
        if mark.get("kind") != "hands":
            continue
        for pair in mark.get("tiles") or []:
            if int(pair[0]) == wx and int(pair[1]) == wy:
                return True
    return False


def draw_floor(surf, rect, x, y, style, t=0.0):
    pal = FLOOR_PAL.get(style, FLOOR_PAL["tomb"])
    base = pal[int(_seed(x, y, 1) * 4) % 4]
    hi, mid, sh, deep = rs.material(base)
    pygame.draw.rect(surf, mid, rect)
    pygame.draw.line(surf, hi, (rect.left + 1, rect.top + 1), (rect.right - 2, rect.top + 1))
    pygame.draw.line(surf, hi, (rect.left + 1, rect.top + 1), (rect.left + 1, rect.bottom - 2))
    pygame.draw.line(surf, sh, (rect.left + 1, rect.bottom - 1), (rect.right - 1, rect.bottom - 1))
    pygame.draw.rect(surf, deep, rect, 1)
    w = rect.w
    r = _seed(x, y, 5)
    if style in ("chapel", "catacomb", "mausoleum") and r < 0.28:
        for k in range(3):
            mx = rect.x + int(w * (0.2 + 0.6 * _seed(x, y, 20 + k)))
            my = rect.y + int(w * (0.2 + 0.6 * _seed(x, y, 30 + k)))
            pygame.draw.circle(surf, (70, 100, 50), (mx, my), max(1, w // 12))
    if style == "ossuary" and r < 0.22:
        bx = rect.x + int(w * (0.2 + 0.5 * _seed(x, y, 6)))
        by = rect.y + int(w * (0.3 + 0.4 * _seed(x, y, 7)))
        pygame.draw.line(surf, (226, 216, 190), (bx, by), (bx + w // 3, by + w // 8), max(1, w // 14))
    if style == "tomb" and (x + y) % 3 == 0:
        pygame.draw.rect(surf, sh, rect.inflate(-w // 4, -w // 4), 1)
    if style == "arena" and r < 0.14:
        pygame.draw.circle(surf, (120, 30, 30), (rect.x + int(w * 0.6), rect.y + int(w * 0.4)), max(1, w // 9))


def draw_wall_top(surf, rect, x, y, style, decor, t):
    base = WALL_PAL.get(style, (60, 60, 60))
    hi, mid, _sh, _deep = rs.material(base)
    cap = pygame.Rect(rect.x, rect.y, rect.w, max(4, rect.h // 3))
    pygame.draw.rect(surf, rs.shade(mid, 8), cap)
    pygame.draw.line(surf, hi, cap.topleft, (cap.right - 1, cap.top))
    if decor == "skull":
        draw_skull_niche(surf, rect, t)
    if decor == "secret":
        pygame.draw.rect(surf, (170, 164, 150), rect.inflate(-rect.w // 5, -rect.h // 5), 1)


def draw_wall_face(surf, rect, x, y, style, decor, t=0.0):
    base = WALL_PAL.get(style, (60, 60, 60))
    hi, mid, sh, deep = rs.material(base)
    face = pygame.Rect(rect.x, rect.y + rect.h // 3, rect.w, rect.h - rect.h // 3)
    pygame.draw.rect(surf, mid, face)
    w = rect.w
    if style == "ossuary" or decor == "skull":
        pygame.draw.rect(surf, (96, 86, 70), face)
        for i in range(2):
            yy = face.y + i * face.h // 2 + face.h // 4
            for k in range(2):
                sx = face.x + int(w * (0.28 + 0.44 * k))
                rr = max(2, w // 8)
                pygame.draw.circle(surf, (222, 212, 186), (sx, yy), rr)
                pygame.draw.circle(surf, (40, 34, 28), (sx - rr // 2, yy - 1), max(1, rr // 3))
                pygame.draw.circle(surf, (40, 34, 28), (sx + rr // 2, yy - 1), max(1, rr // 3))
    else:
        rows = 3
        bh = max(2, face.h // rows)
        for i in range(rows):
            yy = face.y + i * bh
            pygame.draw.line(surf, sh, (face.x, yy), (face.right - 1, yy))
            off = (face.w // 2) if (i + x) % 2 else 0
            for bx in range(face.x - off, face.right, max(4, face.w // 2)):
                if face.x < bx < face.right:
                    pygame.draw.line(surf, sh, (bx, yy), (bx, yy + bh - 1))
        if style in ("chapel", "catacomb", "mausoleum") and _seed(x, y, 15) < 0.4:
            mx = face.x + int(w * _seed(x, y, 16))
            pygame.draw.line(surf, (74, 110, 56), (mx, face.y), (mx, face.y + face.h // 2), max(1, w // 12))
    pygame.draw.line(surf, deep, (face.x, face.bottom - 1), (face.right - 1, face.bottom - 1))
    pygame.draw.line(surf, hi, face.topleft, (face.right - 1, face.top))
    if decor == "secret":
        for k in range(2):
            br = pygame.Rect(face.x + w // 6 + k * w // 3, face.y + face.h // 4 + k * face.h // 4, w // 3, face.h // 4)
            pygame.draw.rect(surf, rs.shade(mid, 22), br)
            pygame.draw.rect(surf, (20, 18, 16), br, 1)
    if decor == "skull":
        draw_skull_niche(surf, face, t)
    if decor and decor.startswith("seal"):
        key = decor.split(":")[-1]
        col = {"A": (210, 180, 120), "B": (80, 160, 150), "C": (180, 60, 50)}.get(key, (180, 170, 140))
        pygame.draw.rect(surf, col, face.inflate(-w // 3, -face.h // 3))
        pygame.draw.rect(surf, (30, 24, 18), face.inflate(-w // 3, -face.h // 3), 1)


def draw_skull_niche(surf, rect, t=0.0):
    w = rect.w
    nr = rect.inflate(-w // 4, -w // 4)
    pygame.draw.rect(surf, (22, 24, 20), nr)
    pygame.draw.rect(surf, (90, 86, 76), nr, 1)
    for k, (fx, fy) in enumerate(((0.3, 0.35), (0.7, 0.35), (0.5, 0.72))):
        sx, sy = rect.x + int(w * fx), rect.y + int(w * fy)
        rr = max(2, w // 9)
        pygame.draw.circle(surf, (224, 214, 188), (sx, sy), rr)
        if k == 2:
            p = 0.6 + 0.4 * math.sin(t * 3)
            pygame.draw.circle(surf, (int(255 * p), int(210 * p), 90), (sx + rr // 2, sy - 1), max(1, rr // 3))
        else:
            pygame.draw.circle(surf, (30, 26, 22), (sx - rr // 2, sy - 1), max(1, rr // 3))
            pygame.draw.circle(surf, (30, 26, 22), (sx + rr // 2, sy - 1), max(1, rr // 3))


def draw_abyss(surf, rect, x, y, t=0.0):
    pygame.draw.rect(surf, (10, 10, 9), rect)
    rnd = __import__("random").Random(x * 131 + y * 17)
    if rnd.random() < 0.35:
        px = rect.x + rnd.randrange(max(1, rect.w))
        py = rect.y + rnd.randrange(max(1, rect.h))
        pygame.draw.line(surf, (70, 66, 56), (px, py), (px + rect.w // 5, py + 1))
    mist = 0.5 + 0.5 * math.sin(x * 0.4 + y * 0.25 + t)
    ov = pygame.Surface(rect.size, pygame.SRCALPHA)
    ov.fill((150, 160, 140, int(22 * mist)))
    surf.blit(ov, rect.topleft)


def draw_bridge(surf, rect, x, y, t=0.0, hands=False):
    draw_abyss(surf, rect, x, y, t)
    slab = rect.inflate(-max(2, rect.w // 8), 0)
    pygame.draw.rect(surf, (178, 168, 140), slab)
    for k in range(3):
        yy = slab.y + int(slab.h * (0.2 + 0.3 * k))
        pygame.draw.line(surf, (226, 216, 190), (slab.x, yy), (slab.right - 1, yy), max(1, rect.w // 12))
    if hands:
        draw_grasping_hands(surf, rect, t, telegraph=True)


def draw_grasping_hands(surf, rect, t=0.0, telegraph=True):
    w = rect.w
    if telegraph:
        ov = pygame.Surface(rect.size, pygame.SRCALPHA)
        ov.fill((120, 255, 150, 60))
        surf.blit(ov, rect.topleft)
        pygame.draw.rect(surf, (140, 255, 170), rect, max(1, w // 16))
    for side in (-1, 1):
        bx = rect.centerx + side * int(w * 0.28)
        by = rect.bottom - 2
        col = (230, 222, 196)
        pygame.draw.line(surf, col, (bx, by), (rect.centerx + side * 2, rect.centery), max(1, w // 10))


def draw_deep_water(surf, rect, x, y, t=0.0):
    try:
        sprites.draw_water_detailed(surf, rect, t, x, y, shores={})
    except Exception:
        pygame.draw.rect(surf, (30, 60, 70), rect)
    ov = pygame.Surface(rect.size, pygame.SRCALPHA)
    ov.fill((20, 50, 30, 120))
    surf.blit(ov, rect.topleft)


def draw_shallow_water(surf, rect, x, y, t=0.0):
    ov = pygame.Surface(rect.size, pygame.SRCALPHA)
    ov.fill((50, 110, 110, 90))
    surf.blit(ov, rect.topleft)


def _draw_courses(screen, rect, wx, wy):
    """Mortar that lines up across tiles, so a wall reads as fitted stone."""
    mortar = (16, 14, 12)
    hi = (84, 78, 70)
    pygame.draw.line(screen, mortar, (rect.left, rect.top), (rect.right - 1, rect.top))
    pygame.draw.line(screen, hi, (rect.left, rect.top + 1), (rect.right - 1, rect.top + 1))
    if (int(wx) + (int(wy) % 2)) % 2 == 0:
        pygame.draw.line(screen, mortar, (rect.left, rect.top), (rect.left, rect.bottom - 1))


def _draw_bridge_post(screen, rect):
    w = rect.w
    post = pygame.Rect(0, 0, max(6, w // 3), max(8, w // 2))
    post.midbottom = (rect.centerx, rect.bottom - 2)
    pygame.draw.rect(screen, (96, 92, 86), post)
    pygame.draw.rect(screen, (36, 34, 30), post, 1)
    cap = pygame.Rect(post.x - 2, post.y - 3, post.w + 4, 4)
    pygame.draw.rect(screen, (118, 112, 104), cap)


def _draw_clutter(surf, rect, style, x, y):
    """Walkable room dressing: pews, bones, webs, or fallen stone."""
    cx, cy, tile = rect.centerx, rect.centery, rect.w
    if style == "chapel":
        body = pygame.Rect(0, 0, int(tile * 0.88), max(4, int(tile * 0.26)))
        body.center = (cx, cy + tile // 10)
        pygame.draw.rect(surf, (64, 42, 26), body)
        pygame.draw.rect(surf, (96, 68, 42), body, 1)
        pygame.draw.rect(surf, (46, 28, 16), (body.x, body.y - 3, body.w, 3))
        return
    if style == "catacomb" and int(y) < 30:
        col = (206, 204, 196)
        pygame.draw.arc(surf, col, rect.inflate(-tile // 5, -tile // 5), 0.4, 2.4, 1)
        pygame.draw.line(surf, col, (rect.left + 4, rect.top + 4), (cx, cy), 1)
        pygame.draw.line(surf, col, (rect.right - 4, rect.top + 6), (cx, cy), 1)
        return
    if style in ("ossuary", "catacomb"):
        for k in range(5):
            bx = int(cx + (_seed(x, y, k) - 0.5) * tile * 0.62)
            by = int(cy + (_seed(x, y, 10 + k) - 0.5) * tile * 0.46)
            pygame.draw.ellipse(surf, (214, 204, 184), (bx, by, max(3, tile // 5), max(2, tile // 12)))
        return
    for k in range(3):
        bx = int(cx + (_seed(x, y, k) - 0.5) * tile * 0.5)
        by = int(cy + (_seed(x, y, 6 + k) - 0.5) * tile * 0.4)
        rw = max(4, int(tile * (0.16 + 0.1 * _seed(x, y, 12 + k))))
        pygame.draw.rect(surf, (132, 124, 112), (bx, by, rw, max(3, rw // 2)))


def draw_sarcophagus(surf, cx, cy, tile, state="closed", t=0.0):
    s = tile / 40.0 * 1.3
    body = pygame.Rect(0, 0, int(30 * s), int(22 * s))
    body.center = (cx, cy - int(2 * s))
    pygame.draw.rect(surf, (104, 106, 112), body)
    pygame.draw.rect(surf, (70, 72, 78), body, max(1, int(2 * s)))
    lid = body.inflate(-int(4 * s), -int(6 * s))
    if state in ("", "closed"):
        pygame.draw.rect(surf, (138, 140, 146), lid)
        pygame.draw.circle(surf, (170, 172, 178), (lid.centerx, lid.y + int(5 * s)), max(2, int(3 * s)))
    else:
        pygame.draw.rect(surf, (18, 16, 16), lid)
        slid = lid.move(int(10 * s), -int(6 * s))
        pygame.draw.rect(surf, (138, 140, 146), slid)
        if state == "loot":
            _glow(surf, lid.centerx, lid.centery, int(16 * s), (255, 210, 110), 50)
        elif state == "ambush":
            _glow(surf, lid.centerx, lid.centery, int(18 * s), (120, 255, 150), 60)


def _prop(client, rect, decor, style, x, y, t):
    surf = client.screen
    cx, cy = rect.centerx, rect.centery
    tile = rect.w
    if decor == "candle":
        try:
            if not prop_sprites.draw_prop(surf, "crypt_candelabra", cx, cy, tile):
                sprites.draw_brazier(surf, cx, cy, tile, t)
        except Exception:
            sprites.draw_brazier(surf, cx, cy, tile, t)
        flicker = 0.72 + 0.28 * math.sin((t or time.time()) * 7.0 + x * 1.7)
        _glow(surf, cx, cy - tile * 0.35, int(tile * 0.9), CANDLE, int(36 + 28 * flicker))
    elif decor.startswith("sarcophagus"):
        state = decor.split(":", 1)[1] if ":" in decor else "closed"
        if not prop_sprites.draw_prop(surf, "crypt_sarcophagus", cx, cy, tile):
            draw_sarcophagus(surf, cx, cy, tile, state, t)
    elif decor == "clutter":
        _draw_clutter(surf, rect, style, x, y)
    elif decor == "chest":
        if not _try_chest(surf, cx, cy, tile, t, open_=False):
            pygame.draw.rect(surf, (110, 72, 36), pygame.Rect(cx - tile // 4, cy - tile // 6, tile // 2, tile // 3))
    elif decor == "chest_open":
        if not _try_chest(surf, cx, cy, tile, t, open_=True):
            pygame.draw.rect(surf, (70, 48, 28), pygame.Rect(cx - tile // 4, cy - tile // 6, tile // 2, tile // 3))
    elif decor == "lore":
        pygame.draw.rect(surf, (214, 196, 150), (cx - tile // 6, cy - tile // 10, tile // 3, tile // 5))
        pygame.draw.line(surf, (120, 90, 50), (cx - tile // 8, cy), (cx + tile // 10, cy), 1)
    elif decor == "lever":
        pygame.draw.rect(surf, (70, 64, 58), (cx - 3, cy - 2, 6, 10))
        pygame.draw.line(surf, (180, 60, 50), (cx, cy - 2), (cx + tile // 6, cy - tile // 4), 3)
    elif decor == "pedestal":
        pygame.draw.rect(surf, (90, 88, 84), (cx - tile // 8, cy - 2, tile // 4, tile // 6))
        _glow(surf, cx, cy - tile // 5, tile // 2, (120, 200, 190), 40)
    elif decor == "warning":
        pygame.draw.polygon(surf, (150, 130, 70), [(cx, cy - tile // 5), (cx - tile // 7, cy + tile // 8), (cx + tile // 7, cy + tile // 8)])
    elif decor in ("cache", "cache_open", "loot"):
        pygame.draw.circle(surf, (210, 180, 80), (cx, cy), max(3, tile // 7))
    elif decor == "shrine":
        s = tile / 40.0
        pygame.draw.rect(surf, (200, 196, 180), (cx - 1.5 * s, cy - 18 * s, 3 * s, 16 * s))
        pygame.draw.rect(surf, (200, 196, 180), (cx - 7 * s, cy - 14 * s, 14 * s, 3 * s))
        _glow(surf, cx, cy - 12 * s, int(28 * s), (255, 230, 160), 50)


def queue_wall_faces(client, draw_list, cam_x, cam_y, vis_w, vis_h, t):
    """No old 3D wall faces — AI plate is the crypt look. Hover hints only."""
    import world_map as wm
    for sy in range(vis_h + 1):
        for sx in range(vis_w + 1):
            vx, vy = cam_x + sx, cam_y + sy
            wx, wy = client.view_to_world(vx, vy)
            if not (0 <= wy < len(client.tiles) and 0 <= wx < client.world_w):
                continue
            if client.tiles[wy][wx] != wm.WALL:
                continue
            decor = (client.dungeon.get("decor") or {}).get(f"{wx},{wy}", "")
            if decor not in ("secret", "skull") and not (decor or "").startswith("seal"):
                continue

            def _hint(sx=sx, sy=sy, decor=decor, wx=wx, wy=wy):
                tw = _tile(client)
                rect = pygame.Rect(sx * tw, sy * tw, tw, tw)
                label = _hover_label(client, decor, wx, wy)
                if label and hasattr(client, "blit_nameplate"):
                    mx, my = pygame.mouse.get_pos()
                    if rect.collidepoint(mx, my):
                        client.blit_nameplate(label, rect.centerx, rect.y - 4, (230, 220, 190))

            draw_list.append(((sy + 1) * _tile(client), 2, _hint))


def _hover_label(client, decor, wx, wy):
    d = client.dungeon or {}
    if decor == "secret" or decor == "skull":
        return (d.get("secret_hints") or {}).get(f"{wx},{wy}") or "Search the wall"
    if decor and decor.startswith("seal"):
        key = decor.split(":")[-1]
        return (d.get("door_hints") or {}).get(key) or "Locked"
    return ""


def handle_click(client, tx, ty):
    import void_v2_client
    return void_v2_client.handle_click(client, tx, ty)


def _inv_has(client, item_id):
    inv = (getattr(client, "player", None) or {}).get("inventory") or {}
    for entry in inv.values() if isinstance(inv, dict) else []:
        if isinstance(entry, dict) and entry.get("item_id") == item_id and int(entry.get("qty") or 0) > 0:
            return True
    # Some payloads use a list of slots.
    if isinstance(inv, list):
        for entry in inv:
            if isinstance(entry, dict) and entry.get("item_id") == item_id and int(entry.get("qty") or 0) > 0:
                return True
    return False


def _keys_held(client):
    d = getattr(client, "dungeon", None) or {}
    server = d.get("keys_held") or {}
    return {
        "A": bool(server.get("A") or _inv_has(client, "depths_bone_key")),
        "B": bool(server.get("B") or _inv_has(client, "depths_tide_key")),
        "C": bool(server.get("C") or _inv_has(client, "depths_knight_seal")),
    }


def draw_key_strip(client):
    """Compact key / door status so players know what opens next."""
    d = getattr(client, "dungeon", None) or {}
    if d.get("v2") != "depths":
        return
    opened = set(d.get("opened") or [])
    held = _keys_held(client)
    d["keys_held"] = held  # keep door glow in sync with inventory
    labels = (
        ("A", "Bone", "depths_bone_key"),
        ("B", "Tide", "depths_tide_key"),
        ("C", "Seal", "depths_knight_seal"),
    )
    font = getattr(client, "font_tiny", None) or pygame.font.SysFont(None, 16)
    x0, y0 = 8, 52
    for i, (ch, short, _item) in enumerate(labels):
        if ch in opened:
            text, col = f"{short} open", (140, 220, 150)
        elif held.get(ch):
            text, col = f"{short} READY", (255, 230, 120)
        else:
            text, col = f"{short} locked", (190, 150, 150)
        surf = font.render(text, True, col)
        client.screen.blit(surf, (x0 + i * 92, y0))


def draw_overlay(client, t):
    import void_v2_client
    void_v2_client.draw_overlay(client, t)
    _atmosphere(client, t or time.time())
    draw_key_strip(client)


def _try_chest(surf, cx, cy, tile, t, open_=False):
    drawer = getattr(sprites, "draw_chest", None)
    if not drawer:
        return False
    try:
        drawer(surf, cx, cy, tile, t or 0)
    except Exception:
        return False
    if open_:
        pygame.draw.rect(surf, (168, 124, 64), (cx - tile // 5, cy - tile // 3, tile // 2, max(3, tile // 10)))
    return True


def _explored(d):
    raw = d.get("explored")
    if isinstance(raw, set):
        return raw
    found = set()
    for pair in raw or []:
        if isinstance(pair, (list, tuple)) and len(pair) >= 2:
            found.add((int(pair[0]), int(pair[1])))
    d["explored"] = found
    return found


def reveal_fog(client, rect, wx, wy):
    """Light a radius around the player and veil the rest. Minimap uses the same set."""
    d = getattr(client, "dungeon", None) or {}
    if d.get("v2") != "depths":
        return
    player = getattr(client, "player", None) or {}
    try:
        px, py = int(player.get("x")), int(player.get("y"))
    except (TypeError, ValueError):
        return
    seen = _explored(d)
    wx, wy = int(wx), int(wy)
    if max(abs(wx - px), abs(wy - py)) <= 8:
        if (wx, wy) not in seen:
            seen.add((wx, wy))
            client._minimap_base = None
        return
    if (wx, wy) in seen:
        return
    key = (rect.w, rect.h)
    fog = _fog_cache.get(key)
    if fog is None:
        fog = pygame.Surface((rect.w, rect.h), pygame.SRCALPHA)
        fog.fill((5, 4, 8, 196))
        _fog_cache[key] = fog
    client.screen.blit(fog, rect.topleft)


def minimap_color(client, wx, wy):
    decor = ((getattr(client, "dungeon", None) or {}).get("decor") or {}).get(f"{wx},{wy}", "")
    if decor == "deep":
        return (16, 72, 80)
    if decor == "shallow":
        return (48, 118, 114)
    if decor == "pit":
        return (6, 6, 8)
    if decor == "bridge" or decor == "rail":
        return (118, 112, 102)
    if decor and str(decor).startswith("seal"):
        return (168, 48, 48)
    if decor == "shrine":
        return (214, 186, 96)
    if decor in ("skull", "secret"):
        return (150, 140, 112)
    return None


def _atmosphere(client, t):
    """One tint and a handful of mist motes for the room the player is standing in."""
    d = getattr(client, "dungeon", None) or {}
    if d.get("v2") != "depths":
        return
    player = getattr(client, "player", None) or {}
    try:
        px, py = int(player.get("x")), int(player.get("y"))
    except (TypeError, ValueError):
        return
    style = style_at(d, px, py)
    phase = str(d.get("boss_phase") or "")
    if style == "arena":
        pulse = 0.55 + 0.45 * math.sin(t * (2.2 if "Collapse" in phase else 1.1))
        tint = (140, 20, 18, int(16 + 18 * pulse))
    else:
        tint = ZONE_LIGHT.get(style)
    if not tint:
        return
    try:
        import client as client_mod
        panel_w = int(getattr(client_mod, "MAP_W", 900))
        panel_h = int(getattr(client_mod, "SCREEN_H", 720))
    except Exception:
        panel_w, panel_h = 900, 720
    wash = pygame.Surface((panel_w, panel_h), pygame.SRCALPHA)
    wash.fill(tint)
    if style in ("catacomb", "bridge", "arena"):
        for i in range(5):
            mx = int((0.15 + 0.18 * i) * panel_w + math.sin(t * 0.35 + i) * 24)
            my = int((0.2 + 0.15 * (i % 3)) * panel_h + math.cos(t * 0.28 + i * 1.3) * 18)
            pygame.draw.circle(wash, (180, 190, 200, 18), (mx, my), 36 + i * 4)
    client.screen.blit(wash, (0, 0))
