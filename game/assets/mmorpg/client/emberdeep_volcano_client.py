"""AI Style B volcano floor + props around the Emberdeep overworld mouth."""
from __future__ import annotations

import os

import pygame

import world_map as wm

PACK = os.path.join(os.path.dirname(__file__), "assets", "props", "emberdeep_volcano")
_RAW = {}
_SCALED = {}
_FLOOR_TILE = None

# Props removed — keep basalt floor overlay only.
_PROPS = ()


def enabled(client):
    return (
        not getattr(client, "dungeon", None)
        and os.path.isfile(os.path.join(PACK, "basalt_floor.png"))
    )


def _raw(name):
    if name not in _RAW:
        path = os.path.join(PACK, f"{name}.png")
        try:
            _RAW[name] = pygame.image.load(path).convert_alpha()
        except Exception as exc:
            print("[emberdeep_volcano]", exc)
            _RAW[name] = None
    return _RAW[name]


def _floor_cell(tile):
    global _FLOOR_TILE
    key = int(tile)
    if _FLOOR_TILE is not None and _FLOOR_TILE[0] == key:
        return _FLOOR_TILE[1]
    src = _raw("basalt_floor")
    if src is None:
        return None
    # Sample a tile-sized patch from the big texture (seeded by world xy later).
    img = pygame.transform.smoothscale(src, (tile * 8, tile * 8))
    _FLOOR_TILE = (key, img)
    return img


def _prop(name, tile, scale=1.0):
    key = (name, int(tile), round(float(scale), 2))
    if key in _SCALED:
        return _SCALED[key]
    src = _raw(name)
    if src is None:
        _SCALED[key] = None
        return None
    if name == "lava_pool":
        tw = max(8, int(tile * 2.4 * scale))
    elif name == "fumarole":
        tw = max(8, int(tile * 2.0 * scale))
    elif name == "ash_stump":
        tw = max(8, int(tile * 2.6 * scale))
    else:
        tw = max(8, int(tile * 2.8 * scale))
    th = max(8, int(src.get_height() * tw / max(1, src.get_width())))
    img = pygame.transform.smoothscale(src, (tw, th))
    _SCALED[key] = img
    return img


def draw_ground(client, rect, wx, wy):
    """Paint AI basalt over scorched STONE/PATH in the Emberdeep field."""
    if not enabled(client) or not wm.is_emberdeep_volcano_field(wx, wy):
        return False
    if getattr(client, "tiles", None) is None:
        return False
    try:
        tid = client.tiles[int(wy)][int(wx)]
    except Exception:
        return False
    if tid not in (wm.STONE, wm.PATH, wm.GRASS):
        return False
    sheet = _floor_cell(rect.w)
    if sheet is None:
        return False
    # Stable UV offset from world coords
    sw, sh = sheet.get_size()
    ox = (int(wx) * 37) % max(1, sw - rect.w)
    oy = (int(wy) * 53) % max(1, sh - rect.h)
    client.screen.blit(sheet, rect.topleft, area=pygame.Rect(ox, oy, rect.w, rect.h))
    # Slight warm shade so PATH mouth reads hotter
    if tid == wm.PATH:
        glow = pygame.Surface((rect.w, rect.h), pygame.SRCALPHA)
        glow.fill((255, 90, 30, 35))
        client.screen.blit(glow, rect.topleft)
    return True


def queue(client, draw_list, cam_x, cam_y, tile):
    if not enabled(client):
        return
    mx, my = wm.EMBERDEEP_MOUTH
    scr = client.screen.get_rect()
    view = scr.inflate(tile * 6, tile * 6)
    try:
        px, py = client.player_xy() if getattr(client, "player", None) else (mx, my)
    except Exception:
        px, py = mx, my
    for name, dx, dy, scale in _PROPS:
        wx, wy = mx + dx, my + dy
        if max(abs(wx - px), abs(wy - py)) > 40:
            continue
        # Don't plant props on the mouth / enter path
        if abs(wx - mx) <= 2 and my <= wy <= my + 3:
            continue
        img = _prop(name, tile, scale=scale)
        if img is None:
            continue
        sx, sy = client.world_to_view_offset(wx, wy, cam_x, cam_y)
        cx = int(sx * tile + tile // 2)
        feet = int(sy * tile + tile * 0.92)
        box = pygame.Rect(
            cx - img.get_width() // 2,
            feet - img.get_height(),
            img.get_width(),
            img.get_height(),
        )
        if not box.colliderect(view):
            continue
        sort_y = feet + (tile // 5 if name == "lava_pool" else 0)

        def _draw(img=img, box=box):
            client.screen.blit(img, box.topleft)

        draw_list.append((sort_y, 2, _draw))
