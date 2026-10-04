"""Behind-and-above view inside a castle room.

Off unless USE_CASTLE_INTERIOR_FOLLOW is set. The castle grounds stay
top-down. Stone faces use castle_stone_wall.png, not the Emberdeep rock.
"""
from __future__ import annotations

import math
import os
import sys

import pygame

import feature_flags
import world_map as wm

_STONE = os.path.normpath(os.path.join(
    os.path.dirname(__file__), "..", "assets", "castle_interior", "castle_stone_wall.png",
))
_TEX = None
_FOV = math.radians(74)
_EYE_BACK = 1.05
_HORIZON = 0.42
_CAM_Z = 0.55


def _map_size():
    main = sys.modules.get("__main__")
    if main is not None and hasattr(main, "MAP_W"):
        return int(main.MAP_W), int(main.MAP_H)
    return 900, 640


def active(client):
    """True while the behind-the-player room view is showing."""
    dungeon = client.dungeon or {}
    plane = dungeon.get("plane")
    return bool(
        feature_flags.USE_CASTLE_INTERIOR_FOLLOW
        and dungeon.get("id") == "castle_realm"
        and plane not in (None, "", "realm")
        and client.player
    )


def _active(client):
    return active(client)


def _stone():
    global _TEX
    if _TEX is None:
        image = pygame.image.load(_STONE)
        if pygame.display.get_surface() is not None:
            image = image.convert()
        _TEX = image
    return _TEX


def _sample(tex, u, v):
    tw, th = tex.get_size()
    tx = int(u * tw) % tw
    ty = int((v % 1.0) * th) % th
    return tex.get_at((tx, ty))


def _solid(tiles, x, y):
    if y < 0 or x < 0 or y >= len(tiles) or x >= len(tiles[0]):
        return True
    return tiles[y][x] == wm.WALL


def _face_vector(face):
    if face == "front":
        return 0.0, 1.0
    try:
        if float(face) < 0:
            return -1.0, 0.0
        if float(face) > 0:
            return 1.0, 0.0
    except (TypeError, ValueError):
        pass
    return 0.0, -1.0


def _face_from_delta(dx, dy):
    if abs(dx) >= abs(dy) and dx != 0:
        return 1 if dx > 0 else -1
    if dy > 0:
        return "front"
    return "back"


def _sync_look(client):
    """Keep the camera on the last step that actually happened.

    A key pressed into a wall must not spin the room.
    """
    player = client.player
    here = (int(player["x"]), int(player["y"]))
    prev = getattr(client, "_castle_anchor", None)
    intent = getattr(client, "_castle_intent", "forward")
    if prev is not None and prev != here and intent != "back":
        dx, dy = here[0] - prev[0], here[1] - prev[1]
        if abs(dx) + abs(dy) == 1:
            client._castle_look = _face_from_delta(dx, dy)
    if getattr(client, "_castle_look", None) is None:
        client._castle_look = client._entity_facing.get(("p", player["id"]), "back")
    client._castle_anchor = here


def _look(client):
    _sync_look(client)
    return _face_vector(client._castle_look)


def arrow_delta(client, sx, sy):
    """Screen arrow into one world step. Up is forward, along the camera."""
    _sync_look(client)
    lx, ly = _face_vector(client._castle_look)
    rx, ry = _right(lx, ly)
    wx = rx * sx + lx * (-sy)
    wy = ry * sx + ly * (-sy)
    if abs(wx) >= abs(wy):
        dx, dy = (1 if wx > 0 else -1), 0
    else:
        dx, dy = 0, (1 if wy > 0 else -1)
    if sx == 0 and sy > 0:
        client._castle_intent = "back"
    elif sx == 0:
        client._castle_intent = "forward"
    else:
        client._castle_intent = "strafe"
    return dx, dy


def _eye(tiles, px, py, lx, ly):
    ex, ey = px, py
    for step in range(1, 9):
        dist = _EYE_BACK * step / 8.0
        nx, ny = px - lx * dist, py - ly * dist
        if _solid(tiles, int(nx), int(ny)):
            break
        ex, ey = nx, ny
    return ex, ey


def _right(lx, ly):
    return -ly, lx


def _cast(tiles, px, py, rdx, rdy):
    height = len(tiles)
    width = len(tiles[0]) if height else 0
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
    for _ in range(80):
        if side_x < side_y:
            side_x += delta_x
            map_x += step_x
            side = 0
        else:
            side_y += delta_y
            map_y += step_y
            side = 1
        if map_y < 0 or map_x < 0 or map_y >= height or map_x >= width or tiles[map_y][map_x] == wm.WALL:
            break
    if side == 0 and abs(rdx) > 1e-8:
        dist = (map_x - px + (1 - step_x) / 2) / rdx
        tex = py + dist * rdy
    elif abs(rdy) > 1e-8:
        dist = (map_y - py + (1 - step_y) / 2) / rdy
        tex = px + dist * rdx
    else:
        dist, tex = 1.0, 0.0
    return max(0.05, dist), tex - math.floor(tex)


def _feet_y(dist, rh, mh):
    horizon = rh * _HORIZON
    yb = horizon * (1.0 + _CAM_Z / max(0.25, dist))
    return int(yb * (mh / float(rh)))


def _project(ex, ey, lx, ly, rx, ry, wx, wy, depths, rw, rh, mw, mh):
    along = (wx - ex) * lx + (wy - ey) * ly
    side = (wx - ex) * rx + (wy - ey) * ry
    if along < 0.25:
        return None
    angle = math.atan2(side, along)
    if abs(angle) > _FOV * 0.55:
        return None
    col = max(0, min(rw - 1, int((0.5 + angle / _FOV) * rw)))
    if depths is not None and depths[col] < along - 0.2:
        return None
    sx = int((0.5 + angle / _FOV) * mw)
    sy = _feet_y(along, rh, mh)
    tile = max(16, int((mh / max(0.5, along)) * 0.11))
    return along, sx, sy, tile


def _pose(client, now):
    player = client.player
    key = ("p", player["id"])
    face = client.facing_for_view(client._entity_facing.get(key, "back"))
    moving = now < client._entity_moving_until.get(key, 0.0)
    atk = client._attack_progress(player["id"], now)
    if atk > 0:
        moving = False
    action = None
    gather = player.get("gathering")
    if gather and isinstance(gather, dict) and gather.get("skill") and atk <= 0:
        action = gather["skill"]
        moving = False
    return face, moving, atk, action


def _draw_player(client, sx, sy, tile, now):
    import procedural_sprites_finished as sprites
    face, moving, atk, action = _pose(client, now)
    # The camera sits behind the body, so forward is the walk-away pose.
    if getattr(client, "_castle_intent", "forward") == "back" and moving:
        face = "front"
    else:
        face = "back"
    player = client.player
    eq = player.get("equipment") or {}
    main = sys.modules.get("__main__")
    weapon = main.weapon_style(eq.get("weapon")) if main is not None and hasattr(main, "weapon_style") else None
    sprites.draw_humanoid_detailed(
        client.screen, sx, sy, tile,
        (70, 210, 90), (235, 195, 150), (70, 45, 30),
        weapon=weapon, shield=bool(eq.get("shield")),
        moving=moving, t=now, facing=face,
        equipment=eq, attacking=atk, action=action,
        gender=player.get("gender") or "male",
    )


def _view(client):
    tiles = client.tiles or []
    px = client.player["x"] + 0.5
    py = client.player["y"] + 0.5
    lx, ly = _look(client)
    ex, ey = _eye(tiles, px, py, lx, ly)
    rx, ry = _right(lx, ly)
    return tiles, ex, ey, lx, ly, rx, ry


def draw(client):
    """Paint the room. False leaves the top-down map in place."""
    if not _active(client):
        return False
    tiles, ex, ey, lx, ly, rx, ry = _view(client)
    if not tiles:
        return False
    import time
    import castle_interiors_v2
    now = time.time()
    plane = client.dungeon.get("plane")
    theme = castle_interiors_v2._theme(plane)
    markers, rugs = castle_interiors_v2.follow_markers(plane, 32)
    mw, mh = _map_size()
    rw, rh = max(160, mw // 2), max(120, mh // 2)
    view = pygame.Surface((rw, rh))
    horizon = int(rh * _HORIZON)
    depths = [1e9] * rw
    stone = _stone()
    pix = pygame.PixelArray(view)
    for col in range(rw):
        cam = (col / max(1, rw - 1) - 0.5) * _FOV
        rdx = lx * math.cos(cam) + rx * math.sin(cam)
        rdy = ly * math.cos(cam) + ry * math.sin(cam)
        dist, tex_u = _cast(tiles, ex, ey, rdx, rdy)
        depths[col] = dist
        wall_h = min(rh, int(rh / dist))
        top = max(0, horizon - wall_h // 2)
        bot = min(rh - 1, horizon + wall_h // 2)
        shade = 210 if col % 2 == 0 else 185
        for y in range(0, rh, 2):
            if top <= y <= bot:
                v = (y - (horizon - wall_h / 2)) / max(1, wall_h)
                color = _sample(stone, tex_u, v)
                color = (color.r * shade // 255, color.g * shade // 255, color.b * shade // 255)
            elif y < horizon:
                color = (28, 26, 32)
            else:
                row = (y - horizon) / max(1, horizon)
                current = _CAM_Z / max(0.05, row)
                fx = int(ex + rdx * current)
                fy = int(ey + rdy * current)
                if (fx, fy) in rugs:
                    color = theme["rug"]
                else:
                    color = theme["floor"][(fx * 3 + fy * 5) % 3]
            pix[col, y] = color
            if y + 1 < rh:
                pix[col, y + 1] = color
    del pix
    client.screen.blit(pygame.transform.scale(view, (mw, mh)), (0, 0))
    bills = []
    for x, y, image in markers:
        proj = _project(ex, ey, lx, ly, rx, ry, x + 0.5, y + 0.5, depths, rw, rh, mw, mh)
        if proj is not None:
            bills.append((proj[0], proj[1], proj[2], proj[3], image))
    bills.sort(key=lambda item: -item[0])
    for _along, sx, sy, tile_px, image in bills:
        height = max(12, int(tile_px * image.get_height() / 32.0))
        width = max(8, int(height * image.get_width() / max(1, image.get_height())))
        scaled = pygame.transform.smoothscale(image, (width, height))
        client.screen.blit(scaled, (sx - width // 2, sy - height))
    _draw_player(client, mw // 2, int(mh * 0.78), max(28, mh // 9), now)
    return True


def pick_tile(client, mx, my):
    """Floor tile under a click, so doors and stairs still work."""
    if not _active(client):
        return None
    mw, mh = _map_size()
    if mx < 0 or my < 0 or mx >= mw or my >= mh:
        return None
    tiles, ex, ey, lx, ly, rx, ry = _view(client)
    if not tiles:
        return None
    cam = (mx / max(1, mw - 1) - 0.5) * _FOV
    rdx = lx * math.cos(cam) + rx * math.sin(cam)
    rdy = ly * math.cos(cam) + ry * math.sin(cam)
    length = math.hypot(rdx, rdy) or 1.0
    rdx /= length
    rdy /= length
    dist, _tex = _cast(tiles, ex, ey, rdx, rdy)
    travel = max(0.6, dist - 0.35)
    tx, ty = int(ex + rdx * travel), int(ey + rdy * travel)
    if _solid(tiles, tx, ty):
        tx, ty = int(ex + rdx * 0.6), int(ey + rdy * 0.6)
    return tx, ty
