"""Emberdeep v2 backdrop and optional first-person view.

USE_EMBERDEEP_V2 draws the mountain picture over the volcano apron and
leaves the existing dragon-lair mouth on top. USE_EMBERDEEP_FIRST_PERSON
replaces the map only while the player is inside Emberdeep. Both flags
default on and are independent.
"""
from __future__ import annotations

import math
import os
import sys

import pygame

import feature_flags
import world_map as wm

_PACK = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", "..", "emberdeep_v2_pack"))
_APRON = (154, 58, 190, 94)  # inclusive world tiles
_IMAGES = {}
_SCALED = {}
_TEX = {}
_FOV = math.radians(66)


def _map_size():
    main = sys.modules.get("__main__")
    if main is not None and hasattr(main, "MAP_W"):
        return int(main.MAP_W), int(main.MAP_H)
    return 900, 640


def _tile():
    main = sys.modules.get("__main__")
    if main is not None and hasattr(main, "TILE"):
        return int(main.TILE)
    return 32


def _load(path):
    img = pygame.image.load(path)
    if pygame.display.get_surface() is not None:
        img = img.convert()
    return img


def _backdrop_image(kind):
    if kind not in _IMAGES:
        name = "mountain_topdown.png" if kind == "topdown" else "mountain_front.png"
        _IMAGES[kind] = _load(os.path.join(_PACK, "backdrop", name))
    return _IMAGES[kind]


def _texture(name):
    if name not in _TEX:
        _TEX[name] = _load(os.path.join(_PACK, "fp", name))
    return _TEX[name]


def skip_apron_tile(client, wx, wy):
    """The mountain picture replaces the flat volcano tiles."""
    if client.dungeon or not feature_flags.USE_EMBERDEEP_V2:
        return False
    x0, y0, x1, y1 = _APRON
    return x0 <= int(wx) <= x1 and y0 <= int(wy) <= y1


def _apron_screen_rect(client):
    """Axis-aligned screen rect of the volcano apron, including the south edge."""
    cam_x, cam_y = client.camera_origin()
    tile = _tile()
    x0, y0, x1, y1 = _APRON
    xs, ys = [], []
    for wx, wy in ((x0, y0), (x1 + 1, y0), (x0, y1 + 1), (x1 + 1, y1 + 1)):
        vx, vy = client.world_to_view(wx, wy)
        xs.append((vx - cam_x) * tile)
        ys.append((vy - cam_y) * tile)
    left, right = min(xs), max(xs)
    top, bottom = min(ys), max(ys)
    return pygame.Rect(int(left), int(top), int(right - left), int(bottom - top))


def blit_backdrop(client):
    """Cover the apron. Yaw 0 uses the top-down mesh; any other yaw uses the south view."""
    if client.dungeon or not feature_flags.USE_EMBERDEEP_V2:
        return
    rect = _apron_screen_rect(client)
    if rect.w < 2 or rect.h < 2:
        return
    yaw = int(getattr(client, "camera_yaw", 0)) % 4
    kind = "topdown" if yaw == 0 else "front"
    img = _backdrop_image(kind)
    key = (kind, rect.w, rect.h)
    scaled = _SCALED.get(key)
    if scaled is None:
        scale = max(rect.w / img.get_width(), rect.h / img.get_height())
        size = (max(1, int(img.get_width() * scale)), max(1, int(img.get_height() * scale)))
        scaled = pygame.transform.smoothscale(img, size)
        _SCALED[key] = scaled
    # South-center of the picture sits on the south-center of the apron.
    dest = pygame.Rect(0, 0, scaled.get_width(), scaled.get_height())
    dest.midbottom = rect.midbottom
    mw, mh = _map_size()
    clip = rect.clip(pygame.Rect(0, 0, mw, mh))
    if clip.w < 1 or clip.h < 1:
        return
    src = clip.move(-dest.x, -dest.y)
    client.screen.blit(scaled, clip.topleft, area=src)


def _in_emberdeep(client):
    return bool(
        feature_flags.USE_EMBERDEEP_FIRST_PERSON
        and client.dungeon
        and client.dungeon.get("id") == "emberdeep"
        and client.player
    )


def _basis(yaw):
    look = ((0.0, -1.0), (1.0, 0.0), (0.0, 1.0), (-1.0, 0.0))[int(yaw) % 4]
    lx, ly = look
    return lx, ly, -ly, lx


def _cast(tiles, px, py, rdx, rdy):
    h = len(tiles)
    w = len(tiles[0]) if h else 0
    map_x, map_y = int(px), int(py)
    delta_x = abs(1.0 / rdx) if abs(rdx) > 1e-8 else 1e30
    delta_y = abs(1.0 / rdy) if abs(rdy) > 1e-8 else 1e30
    if rdx < 0:
        step_x, side_x = -1, (px - map_x) * delta_x
    else:
        step_x, side_x = 1, (map_x + 1.0 - px) * delta_x
    if rdy < 0:
        step_y, side_y = -1, (py - map_y) * delta_y
    else:
        step_y, side_y = 1, (map_y + 1.0 - py) * delta_y
    side = 0
    for _ in range(96):
        if side_x < side_y:
            side_x += delta_x
            map_x += step_x
            side = 0
        else:
            side_y += delta_y
            map_y += step_y
            side = 1
        if map_y < 0 or map_x < 0 or map_y >= h or map_x >= w or tiles[map_y][map_x] == wm.WALL:
            break
    if side == 0 and abs(rdx) > 1e-8:
        dist = (map_x - px + (1 - step_x) / 2) / rdx
        tex = py + dist * rdy
    elif abs(rdy) > 1e-8:
        dist = (map_y - py + (1 - step_y) / 2) / rdy
        tex = px + dist * rdx
    else:
        dist, tex = 1.0, 0.0
    dist = max(0.05, dist)
    tex -= math.floor(tex)
    return dist, map_x, map_y, tex


def _tile_at(tiles, x, y):
    if y < 0 or x < 0 or y >= len(tiles) or x >= len(tiles[0]):
        return wm.WALL
    return tiles[y][x]


def _floor_name(tiles, x, y):
    here = _tile_at(tiles, x, y)
    if here == wm.WATER:
        return "wall_lava.png"
    for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
        if _tile_at(tiles, x + dx, y + dy) == wm.WATER:
            return "floor_lava_edge.png"
    return "floor_stone.png"


def _wall_name(tiles, x, y, boss):
    if boss and int(y) == int(boss[1]) and abs(int(x) - int(boss[0])) <= 2:
        return "door_boss.png"
    for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
        if _tile_at(tiles, x + dx, y + dy) == wm.WATER:
            return "wall_lava.png"
    return "wall_rock.png"


def _sample(tex, u, v):
    tw, th = tex.get_size()
    tx = int(u * tw) % tw
    ty = int(v * th) % th
    return tex.get_at((tx, ty))


def draw_first_person(client):
    """Raycast the Emberdeep floor. Returns False when the top-down map should draw."""
    if not _in_emberdeep(client):
        return False
    tiles = client.tiles or []
    if not tiles:
        return False
    mw, mh = _map_size()
    rw, rh = max(160, mw // 2), max(120, mh // 2)
    view = pygame.Surface((rw, rh))
    px = client.player["x"] + 0.5
    py = client.player["y"] + 0.5
    lx, ly, rx, ry = _basis(client.camera_yaw)
    boss = client.dungeon.get("boss_door")
    horizon = rh // 2
    depths = [1e9] * rw
    pix = pygame.PixelArray(view)
    ceiling = _texture("ceiling_dark.png")
    for col in range(rw):
        cam = (col / max(1, rw - 1) - 0.5) * _FOV
        rdx = lx * math.cos(cam) + rx * math.sin(cam)
        rdy = ly * math.cos(cam) + ry * math.sin(cam)
        dist, wx, wy, tex_u = _cast(tiles, px, py, rdx, rdy)
        depths[col] = dist
        wall_h = min(rh, int(rh / dist))
        top = max(0, horizon - wall_h // 2)
        bot = min(rh - 1, horizon + wall_h // 2)
        wall_tex = _texture(_wall_name(tiles, wx, wy, boss))
        shade = 180 if (wx + wy) % 2 == 0 else 230
        for y in range(0, rh, 2):
            if top <= y <= bot:
                v = (y - (horizon - wall_h / 2)) / max(1, wall_h)
                color = _sample(wall_tex, tex_u, v)
                color = (color.r * shade // 255, color.g * shade // 255, color.b * shade // 255)
            elif y < horizon:
                row = (horizon - y) / max(1, horizon)
                current = 0.35 / max(0.05, row)
                fx = px + rdx * current
                fy = py + rdy * current
                color = _sample(ceiling, fx, fy)
                color = (color.r // 2, color.g // 2, color.b // 2)
            else:
                row = (y - horizon) / max(1, horizon)
                current = 0.35 / max(0.05, row)
                fx = px + rdx * current
                fy = py + rdy * current
                color = _sample(_texture(_floor_name(tiles, int(fx), int(fy))), fx, fy)
            pix[col, y] = color
            if y + 1 < rh:
                pix[col, y + 1] = color
    del pix
    monsters = []
    for mon in (client.monsters or {}).values():
        if not mon.get("alive", True):
            continue
        vx = mon["x"] + 0.5 - px
        vy = mon["y"] + 0.5 - py
        along = vx * lx + vy * ly
        side = vx * rx + vy * ry
        if along < 0.35:
            continue
        angle = math.atan2(side, along)
        if abs(angle) > _FOV * 0.5:
            continue
        col = int((0.5 + angle / _FOV) * rw)
        col = max(0, min(rw - 1, col))
        if depths[col] < along:
            continue
        size = max(8, int(rh / max(0.4, along)))
        sx = int(col * (mw / rw))
        sy = mh // 2 - size // 2
        monsters.append((along, pygame.Rect(sx - size // 4, sy, size // 2, size)))
    scaled = pygame.transform.scale(view, (mw, mh))
    client.screen.blit(scaled, (0, 0))
    for _dist, rect in monsters:
        pygame.draw.rect(client.screen, (150, 50, 30), rect)
        pygame.draw.rect(client.screen, (255, 170, 80), rect, 2)
    return True


def pick_tile(client, mx, my):
    """Map a first-person click back onto a dungeon tile. None keeps the top-down picker."""
    if not _in_emberdeep(client):
        return None
    mw, mh = _map_size()
    if mx < 0 or my < 0 or mx >= mw or my >= mh:
        return None
    tiles = client.tiles or []
    if not tiles:
        return None
    px = client.player["x"] + 0.5
    py = client.player["y"] + 0.5
    lx, ly, rx, ry = _basis(client.camera_yaw)
    cam = (mx / max(1, mw - 1) - 0.5) * _FOV
    rdx = lx * math.cos(cam) + rx * math.sin(cam)
    rdy = ly * math.cos(cam) + ry * math.sin(cam)
    length = math.hypot(rdx, rdy) or 1.0
    rdx /= length
    rdy /= length
    dist, _wx, _wy, _tex = _cast(tiles, px, py, rdx, rdy)
    best = None
    best_d = dist
    for mon in (client.monsters or {}).values():
        if not mon.get("alive", True):
            continue
        vx = mon["x"] + 0.5 - px
        vy = mon["y"] + 0.5 - py
        along = vx * rdx + vy * rdy
        perp = abs(vx * rdy - vy * rdx)
        if 0.4 <= along < best_d and perp < 0.55:
            best = (int(mon["x"]), int(mon["y"]))
            best_d = along
    if best:
        return best
    travel = max(0.75, dist - 0.4)
    tx = int(px + rdx * travel)
    ty = int(py + rdy * travel)
    if _tile_at(tiles, tx, ty) != wm.FLOOR:
        tx = int(px + rdx * 0.75)
        ty = int(py + rdy * 0.75)
    return tx, ty
