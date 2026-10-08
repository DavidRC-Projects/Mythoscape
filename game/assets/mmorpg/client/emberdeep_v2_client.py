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
_APRON = (176, 58, 198, 94)  # inclusive world tiles
_IMAGES = {}
_SCALED = {}
_TEX = {}
_FOV = math.radians(78)
# Each step lifts the eye and opens the view. 100 is the normal camera.
# The body size is not tied to these.
_ZOOMS = (
    {"back": 1.55, "horizon": 0.28, "z": 2.05, "fov": 78, "label": "100"},
    {"back": 4.8, "horizon": 0.15, "z": 7.5, "fov": 120, "label": "40"},
    {"back": 9.0, "horizon": 0.08, "z": 16.0, "fov": 145, "label": "15"},
)


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


def zoom_level(client):
    return max(0, min(len(_ZOOMS) - 1, int(getattr(client, "ember_zoom", 0) or 0)))


def apply_zoom(client):
    """Use the Emberdeep zoom step for this frame. The player sprite is unchanged."""
    global _EYE_BACK, _HORIZON, _CAM_Z, _FOV
    step = _ZOOMS[zoom_level(client)]
    _EYE_BACK = step["back"]
    _HORIZON = step["horizon"]
    _CAM_Z = step["z"]
    _FOV = math.radians(step["fov"])


def adjust_zoom(client, delta):
    """Match the world controls: delta < 0 zooms out."""
    level = zoom_level(client)
    if delta < 0:
        level += 1
    elif delta > 0:
        level -= 1
    set_zoom(client, level)


def set_zoom(client, level):
    import time
    level = max(0, min(len(_ZOOMS) - 1, int(level)))
    if getattr(client, "ember_zoom", None) == level:
        return
    client.ember_zoom = level
    client._zoom_toast_until = time.time() + 1.2
    apply_zoom(client)


def zoom_label(client):
    return f"Zoom {_ZOOMS[zoom_level(client)]['label']}%"


def zoom_control_layout():
    """Same corner as the world map: zoom out, each step, zoom in."""
    main = sys.modules.get("__main__")
    map_h = int(getattr(main, "MAP_H", 640))
    bh = 26
    gap = 4
    y = map_h - bh - 10
    x = 10
    items = [(pygame.Rect(x, y, 28, bh), "out")]
    x += 28 + gap
    for level in range(len(_ZOOMS) - 1, -1, -1):
        items.append((pygame.Rect(x, y, 36, bh), level))
        x += 36 + gap
    items.append((pygame.Rect(x, y, 28, bh), "in"))
    return items


def draw_zoom_controls(client):
    import time
    level = zoom_level(client)
    for rect, action in zoom_control_layout():
        active = action == level
        fill = (72, 42, 28) if active else (28, 18, 16)
        edge = (230, 150, 70) if active else (140, 90, 50)
        pygame.draw.rect(client.screen, fill, rect, border_radius=5)
        pygame.draw.rect(client.screen, edge, rect, 1, border_radius=5)
        if action == "out":
            label = "−"
        elif action == "in":
            label = "+"
        else:
            label = _ZOOMS[action]["label"]
        text = client.font_tiny.render(label, True, (240, 220, 190))
        client.screen.blit(text, (rect.centerx - text.get_width() // 2, rect.centery - text.get_height() // 2))
    if time.time() < getattr(client, "_zoom_toast_until", 0):
        ztxt = client.font_small.render(zoom_label(client), True, (240, 220, 190))
        zr = pygame.Rect(10, 38, ztxt.get_width() + 16, 22)
        pygame.draw.rect(client.screen, (28, 18, 16), zr, border_radius=6)
        pygame.draw.rect(client.screen, (230, 150, 70), zr, 1, border_radius=6)
        client.screen.blit(ztxt, (zr.x + 8, zr.y + 3))


def _in_emberdeep(client):
    return bool(
        feature_flags.USE_EMBERDEEP_FIRST_PERSON
        and client.dungeon
        and client.dungeon.get("id") == "emberdeep"
        and client.player
    )


# Eye sits back and above the player, pitched down so the corridor is seen
# from over their head. Horizon stays high; the body stays in the lower middle.
# These are the active step. adjust_zoom writes them from _ZOOMS.
_EYE_BACK = _ZOOMS[0]["back"]
_HORIZON = _ZOOMS[0]["horizon"]
_CAM_Z = _ZOOMS[0]["z"]
# One key press turns the view this far. The player owns the yaw.
_YAW_STEP = math.radians(15)


def _look_vector(face):
    """World look from an existing pose: back north, front south, ±1 east/west."""
    if face == "back":
        return 0.0, -1.0
    if face == "front":
        return 0.0, 1.0
    try:
        if float(face) < 0:
            return -1.0, 0.0
    except (TypeError, ValueError):
        pass
    return 1.0, 0.0


def _face_from_delta(dx, dy):
    if abs(dx) >= abs(dy) and dx != 0:
        return 1 if dx > 0 else -1
    if abs(dy) > abs(dx) and dy != 0:
        return "back" if dy < 0 else "front"
    return None


def _walk_look(client, key, x, y):
    """Direction the player is walking. None when they are standing still."""
    path = getattr(client, "walk_path", None) or []
    if path:
        nx, ny = path[0]
        face = _face_from_delta(nx - x, ny - y)
        if face is not None:
            client._ember_walk_face = face
            return face
    prev = client._prev_entity_pos.get(key)
    if prev is not None and prev != (x, y):
        face = _face_from_delta(x - prev[0], y - prev[1])
        if face is not None:
            client._ember_walk_face = face
            return face
    if time_now() < client._entity_moving_until.get(key, 0.0):
        return getattr(client, "_ember_walk_face", None) or client._entity_facing.get(key)
    return None


def time_now():
    import time
    return time.time()


def _sprite_face(client, key, x, y, anim_id=None):
    """Same facing rules as the top-down player and monster blocks."""
    my_id = (client.player or {}).get("id")
    is_local = key == ("p", my_id)
    prev = client._prev_entity_pos.get(key)
    moving_now = prev is not None and prev != (x, y)
    traveling = bool(
        is_local and (
            getattr(client, "walk_path", None)
            or moving_now
            or time_now() < client._entity_moving_until.get(key, 0.0)
        )
    )
    if traveling:
        path = getattr(client, "walk_path", None) or []
        if path:
            nx, ny = path[0]
            face = _face_from_delta(nx - x, ny - y)
            if face is not None:
                client._entity_facing[key] = face
                return face
        if prev is not None:
            face = _face_from_delta(x - prev[0], y - prev[1])
            if face is not None:
                client._entity_facing[key] = face
                return face
        return client._entity_facing.get(key, 1)
    aid = anim_id if anim_id is not None else key
    if isinstance(aid, tuple):
        aid = aid[1] if len(aid) > 1 else aid[0]
    expire = client.attack_anims.get(aid)
    if expire and expire > time_now() and aid in client.attack_face:
        face = client.attack_face[aid]
        if face in ("front", "back"):
            face = 1
        elif isinstance(face, (int, float)) and abs(float(face)) >= 1.5:
            face = 1 if float(face) > 0 else -1
        client._entity_facing[key] = face
        return face
    if is_local and client.combat_target_id is not None:
        m = client.monsters.get(client.combat_target_id)
        if m and m.get("alive"):
            return client.face_toward_target(x, y, m["x"], m["y"], key=key)
    face = client._entity_facing.get(key, 1)
    if prev is not None:
        faced = _face_from_delta(x - prev[0], y - prev[1])
        if faced is not None:
            face = faced
    client._entity_facing[key] = face
    return face


def _mark_moving(client, key, x, y):
    prev = client._prev_entity_pos.get(key)
    now = time_now()
    if prev is not None and prev != (x, y):
        client._entity_moving_until[key] = now + 0.55
    return now < client._entity_moving_until.get(key, 0.0)


def _weapon_style(item_id):
    main = sys.modules.get("__main__")
    fn = getattr(main, "weapon_style", None) if main is not None else None
    if fn is not None:
        return fn(item_id)
    if not item_id:
        return None
    text = str(item_id)
    if "bow" in text:
        return "bow"
    if "dagger" in text:
        return "dagger"
    if "pickaxe" in text:
        return "pickaxe"
    if "battleaxe" in text or "cleaver" in text:
        return "battleaxe"
    if "axe" in text:
        return "axe"
    if "sword" in text:
        return "sword"
    return "sword"


def _face_from_vector(lx, ly):
    if abs(lx) > abs(ly):
        return 1 if lx > 0 else -1
    return "back" if ly < 0 else "front"


def _draw_tile_highlight(view, ex, ey, lx, ly, rx, ry, tile_x, tile_y, rw, rh, mw, mh, color, thickness=2):
    """Draw an outline around a floor tile at (tile_x, tile_y)."""
    corners = [
        (tile_x, tile_y),
        (tile_x + 1, tile_y),
        (tile_x + 1, tile_y + 1),
        (tile_x, tile_y + 1),
    ]
    screen_pts = []
    for cx, cy in corners:
        vx, vy = cx - ex, cy - ey
        along = vx * lx + vy * ly
        if along < 0.3:
            return
        side = vx * rx + vy * ry
        angle = math.atan2(side, along)
        if abs(angle) > _FOV * 0.6:
            return
        sx = int((0.5 + angle / _FOV) * rw)
        sy = _feet_y(along, rh, mh)
        screen_pts.append((sx, sy))
    if len(screen_pts) == 4:
        for i in range(4):
            p1 = screen_pts[i]
            p2 = screen_pts[(i + 1) % 4]
            for t in range(thickness):
                pygame.draw.line(view, color, (p1[0], p1[1] + t), (p2[0], p2[1] + t), 1)


def fp_active(client):
    return _in_emberdeep(client)


def turn(client, direction):
    """Rotate the Emberdeep view one small step. Left is -1, right is +1."""
    now = time_now()
    if now < getattr(client, "_ember_turn_at", 0.0):
        return
    client._ember_yaw = getattr(client, "_ember_yaw", 0.0) + direction * _YAW_STEP
    client._ember_turn_at = now + 0.16


def step_delta(client, forward):
    """One tile along the way the player is looking, or back the other way."""
    yaw = float(getattr(client, "_ember_yaw", 0.0))
    lx, ly = math.sin(yaw), -math.cos(yaw)
    if abs(lx) >= abs(ly):
        dx, dy = (1 if lx > 0 else -1), 0
    else:
        dx, dy = 0, (1 if ly > 0 else -1)
    if forward < 0:
        dx, dy = -dx, -dy
    return dx, dy


def strafe_delta(client, right):
    """One tile perpendicular to look direction. Right is +1, left is -1."""
    yaw = float(getattr(client, "_ember_yaw", 0.0))
    rx, ry = math.cos(yaw), math.sin(yaw)
    if abs(rx) >= abs(ry):
        dx, dy = (1 if rx > 0 else -1), 0
    else:
        dx, dy = 0, (1 if ry > 0 else -1)
    if right < 0:
        dx, dy = -dx, -dy
    return dx, dy


def _local_draw_args(client, t):
    """Facing and equipment for the local player. Look is the player's yaw."""
    p = client.player
    key = ("p", p["id"])
    x, y = p["x"], p["y"]
    moving = _mark_moving(client, key, x, y)
    atk = client._attack_progress(p["id"], t)
    if atk > 0:
        moving = False
    yaw = float(getattr(client, "_ember_yaw", 0.0))
    lx, ly = math.sin(yaw), -math.cos(yaw)
    strafe_dir = getattr(client, "_ember_strafe", None)
    if moving and strafe_dir is not None:
        face = strafe_dir
    elif moving and getattr(client, "_ember_reverse", False):
        face = "front"
    else:
        face = "back"
    client._entity_facing[key] = face
    action = None
    gather = p.get("gathering")
    if gather and isinstance(gather, dict) and gather.get("skill") and atk <= 0:
        action = gather["skill"]
        moving = False
    return {
        "x": x, "y": y, "key": key,
        "face": face, "moving": moving, "atk": atk, "action": action,
        "lx": lx, "ly": ly,
        "eq": p.get("equipment") or {},
        "gender": p.get("gender") or "male",
    }


def _advance_camera(client, tiles, pose, now):
    """Sit on the current tile. No glide, so the room does not keep sliding."""
    px, py = pose["x"] + 0.5, pose["y"] + 0.5
    want_lx, want_ly = pose["lx"], pose["ly"]
    dungeon_id = (client.dungeon or {}).get("id")
    client._ember_cam_t = now
    eye = _eye(tiles, px, py, want_lx, want_ly)
    client._ember_cam = {
        "dungeon": dungeon_id,
        "bx": px, "by": py,
        "fx": px, "fy": py,
        "lx": want_lx, "ly": want_ly,
        "ex": eye[0], "ey": eye[1],
    }


def _eye(tiles, px, py, lx, ly):
    """Step back along the look until a wall."""
    ex, ey = px, py
    steps = max(8, int(_EYE_BACK * 4))
    for i in range(1, steps + 1):
        dist = _EYE_BACK * i / steps
        nx, ny = px - lx * dist, py - ly * dist
        if _tile_at(tiles, int(nx), int(ny)) != wm.FLOOR:
            break
        ex, ey = nx, ny
    return ex, ey


def _right(lx, ly):
    return -ly, lx


def _feet_y(dist, rh, mh):
    horizon = rh * _HORIZON
    yb = horizon * (1.0 + _CAM_Z / max(0.2, dist))
    return int(yb * (mh / float(rh)))


def _tile_px(dist, mh):
    return max(24, int((mh / max(0.45, dist)) * 0.12))


def _project(ex, ey, lx, ly, rx, ry, wx, wy, depths, rw, rh, mw, mh, reveal=False):
    vx, vy = wx - ex, wy - ey
    along = vx * lx + vy * ly
    side = vx * rx + vy * ry
    if along < 0.2:
        return None
    angle = math.atan2(side, along)
    limit = _FOV * (0.85 if reveal else 0.75)
    if abs(angle) > limit:
        return None
    col = int((0.5 + angle / _FOV) * rw)
    col = max(0, min(rw - 1, col))
    if depths is not None and not reveal and depths[col] < along - 0.25:
        return None
    sx = int((0.5 + max(-0.48, min(0.48, angle / _FOV))) * mw)
    sy = _feet_y(along, rh, mh)
    return along, sx, sy, _tile_px(along, mh)


def _cone_spots(monster):
    spots = set()
    for spot in (monster or {}).get("cone_tiles") or []:
        if isinstance(spot, dict):
            spots.add((int(spot["x"]), int(spot["y"])))
        else:
            spots.add((int(spot[0]), int(spot[1])))
    return spots


def wyrm_swing_tiles(monster):
    """Breath tiles, plus one step to either side. Matches the server."""
    spots = _cone_spots(monster)
    if not spots:
        return spots
    xs = [p[0] for p in spots]
    lo, hi = min(xs), max(xs)
    for y in {p[1] for p in spots}:
        spots.add((lo - 1, y))
        spots.add((hi + 1, y))
    return spots


def wyrm_approach_goals(monster):
    """Stand beside the flame. The breath tiles still count once you are there."""
    swing = wyrm_swing_tiles(monster)
    safe = swing - _cone_spots(monster)
    return safe or swing


def _sprite_world(monster):
    """Feet of a billboard. The wyrm is drawn in the open floor, not on the back wall."""
    x = monster["x"] + 0.5
    y = monster["y"] + 0.5
    if monster.get("type") == "emberdeep_wyrm":
        y += 1.55
    return x, y


def _open_between(tiles, x0, y0, x1, y1):
    """True when no wall stands strictly between the two tiles."""
    x0, y0, x1, y1 = int(x0), int(y0), int(x1), int(y1)
    steps = max(abs(x1 - x0), abs(y1 - y0))
    if steps <= 1:
        return True
    for i in range(1, steps):
        x = x0 + (x1 - x0) * i // steps
        y = y0 + (y1 - y0) * i // steps
        if _tile_at(tiles, x, y) == wm.WALL:
            return False
    return True


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
    return dist, map_x, map_y, tex, side, step_x, step_y


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


def _sample_floor(tex, tiles, fx, fy):
    """One flagstone per tile, with grout, so the floor reads as laid stones."""
    tw, th = tex.get_size()
    ix, iy = math.floor(fx), math.floor(fy)
    fu, fv = fx - ix, fy - iy
    ix, iy = int(ix), int(iy)
    if _tile_at(tiles, ix, iy) == wm.WATER:
        n = (ix * 13 + iy * 7) & 31
        return pygame.Color(min(255, 200 + n), 70 + n, 18)
    lava = None
    for dx, dy in ((0, 1), (0, -1), (1, 0), (-1, 0)):
        if _tile_at(tiles, ix + dx, iy + dy) == wm.WATER:
            lava = (dx, dy)
            break
    if lava is None and (fu < 0.05 or fu > 0.95 or fv < 0.05 or fv > 0.95):
        shade = 22 + ((ix * 13 + iy * 7) & 12)
        return pygame.Color(shade, max(0, shade - 4), max(0, shade - 8))
    cell = 4
    cx = (ix * 3 + iy) % cell
    if lava is None:
        cy = (ix + iy * 2) % cell
        uu = 0.07 + fu * 0.86
        vv = 0.07 + fv * 0.86
        tx = int((cx + uu) / cell * tw) % tw
        ty = int((cy + vv) / cell * th) % th
    else:
        sx, sy = lava
        if sy > 0:
            u, v = fu, fv
        elif sy < 0:
            u, v = 1.0 - fu, 1.0 - fv
        elif sx > 0:
            u, v = fv, fu
        else:
            u, v = 1.0 - fv, 1.0 - fu
        if v >= 0.72:
            tx = int(u * tw) % tw
            ty = int((0.75 + (v - 0.72) / 0.28 * 0.25) * th) % th
        else:
            cy = (ix + iy) % 3
            uu = 0.08 + u * 0.84
            vv = v / 0.72
            tx = int((cx + uu) / cell * tw) % tw
            ty = int((cy + vv) / 3.0 * (th * 0.75)) % th
    color = tex.get_at((tx, ty))
    vary = 90 + ((ix * 17 + iy * 11) & 28)
    return pygame.Color(
        min(255, color.r * vary // 100),
        min(255, color.g * vary // 100),
        min(255, color.b * vary // 100),
    )


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


_LIGHT = {}
_ROOMS = {}
_THEMES = {}
# Legged bodies take a step. The slug and the wyrm do not.
_LEGS = {
    "ash_imp": "biped",
    "magma_knight": "biped",
    "crucible_beast": "quad",
    "ember_wolf": "quad",
}
_ROOM_THEME = {
    "ember_imp": "soot",
    "ash_imp": "soot",
    "bile_toad": "moss",
    "cinder_bitch": "claws",
    "ember_wolf": "claws",
    "ash_warlock": "runes",
    "troll_cook": "grease",
    "mistress_of_cinders": "banner",
    "emberdeep_wyrm": "scorch",
    "crucible_beast": "scorch",
    "magma_knight": "scorch",
    "magma_slug": "cracks",
}
_THEME_RANK = {
    "scorch": 0, "banner": 1, "runes": 2, "claws": 3,
    "grease": 4, "moss": 5, "soot": 6, "cracks": 7,
}


def _room_block(tiles, x, y):
    """True when this floor tile belongs to a room, not a one-tile corridor."""
    def floor(nx, ny):
        return _tile_at(tiles, nx, ny) == wm.FLOOR

    if not floor(x, y):
        return False
    for dx, dy in ((0, 0), (-1, 0), (0, -1), (-1, -1)):
        if all(floor(x + dx + a, y + dy + b) for a in (0, 1) for b in (0, 1)):
            return True
    return False


def _rooms(tiles):
    """Floor tile -> room origin. Corridors are left out."""
    key = id(tiles)
    if _ROOMS.get("key") == key:
        return _ROOMS["grid"]
    h = len(tiles)
    w = len(tiles[0]) if h else 0
    grid = {}
    for y in range(h):
        for x in range(w):
            if (x, y) in grid or not _room_block(tiles, x, y):
                continue
            seen = {(x, y)}
            queue = [(x, y)]
            i = 0
            while i < len(queue):
                cx, cy = queue[i]
                i += 1
                for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                    nx, ny = cx + dx, cy + dy
                    if (nx, ny) in seen or not _room_block(tiles, nx, ny):
                        continue
                    seen.add((nx, ny))
                    queue.append((nx, ny))
            origin = min(seen)
            for spot in seen:
                grid[spot] = origin
    _ROOMS.clear()
    _ROOMS["key"] = key
    _ROOMS["grid"] = grid
    return grid


def _sconces(tiles):
    """Candle tiles along the corridors, and how bright each map tile is."""
    key = id(tiles)
    if _LIGHT.get("key") == key:
        return _LIGHT["glow"], _LIGHT["sconces"]
    h = len(tiles)
    w = len(tiles[0]) if h else 0
    glow = [[0.0] * w for _ in range(h)]
    sconces = set()
    for y in range(h):
        for x in range(w):
            if _tile_at(tiles, x, y) != wm.FLOOR or _room_block(tiles, x, y):
                continue
            if (x + y * 3) % 5 != 0:
                continue
            sconces.add((x, y))
            for dy in range(-3, 4):
                for dx in range(-3, 4):
                    nx, ny = x + dx, y + dy
                    if ny < 0 or nx < 0 or ny >= h or nx >= w:
                        continue
                    dist = math.hypot(dx, dy)
                    if dist > 3.1:
                        continue
                    glow[ny][nx] = max(glow[ny][nx], 1.0 - dist / 3.1)
    _LIGHT.clear()
    _LIGHT["key"] = key
    _LIGHT["glow"] = glow
    _LIGHT["sconces"] = sconces
    return glow, sconces


def _paint_theme(name):
    """A copy of the rock wall with marks for one kind of creature room."""
    base = _texture("wall_rock.png").copy()
    w, h = base.get_size()
    paint = pygame.Surface((w, h), pygame.SRCALPHA)
    if name == "soot":
        pygame.draw.ellipse(paint, (20, 12, 10, 150), (w // 5, h // 6, w // 2, h // 3))
        pygame.draw.line(paint, (210, 90, 30, 200), (w // 4, h // 3), (w // 2, h // 2), 2)
        pygame.draw.line(paint, (180, 60, 20, 160), (w // 2, h // 2), (3 * w // 5, 2 * h // 3), 2)
    elif name == "moss":
        pygame.draw.ellipse(paint, (48, 120, 40, 200), (w // 10, int(h * 0.62), w // 3, h // 4))
        pygame.draw.ellipse(paint, (36, 96, 32, 190), (w // 2, int(h * 0.7), w // 3, h // 5))
        pygame.draw.ellipse(paint, (70, 140, 50, 160), (w // 3, int(h * 0.8), w // 6, h // 8))
    elif name == "claws":
        for i, x0 in enumerate((w // 5, w // 3, w // 2)):
            pygame.draw.line(paint, (190, 170, 140, 180), (x0, h // 4), (x0 + w // 8, 3 * h // 5), 2)
    elif name == "runes":
        pygame.draw.circle(paint, (160, 120, 60, 170), (w // 2, h // 2), w // 6, 2)
        pygame.draw.line(paint, (170, 130, 70, 180), (w // 3, h // 2), (2 * w // 3, h // 2), 2)
        pygame.draw.line(paint, (170, 130, 70, 180), (w // 2, h // 3), (w // 2, 2 * h // 3), 2)
    elif name == "grease":
        for x0 in (w // 5, w // 2, 3 * w // 4):
            pygame.draw.line(paint, (120, 78, 28, 210), (x0, h // 8), (x0 - 6, int(h * 0.72)), 4)
            pygame.draw.circle(paint, (90, 56, 20, 180), (x0 - 6, int(h * 0.74)), max(3, w // 18))
    elif name == "banner":
        pygame.draw.rect(paint, (90, 24, 22, 160), (w // 3, h // 10, w // 8, 4 * h // 5))
        pygame.draw.rect(paint, (40, 12, 12, 180), (w // 3 + w // 10, h // 10, w // 16, 4 * h // 5))
    elif name == "scorch":
        pygame.draw.ellipse(paint, (12, 8, 8, 170), (w // 6, h // 5, 2 * w // 3, h // 2))
        pygame.draw.line(paint, (220, 80, 20, 210), (w // 4, h // 3), (w // 2, 2 * h // 3), 2)
        pygame.draw.line(paint, (200, 60, 16, 180), (w // 2, h // 4), (3 * w // 5, h // 2), 2)
    else:
        pygame.draw.line(paint, (70, 60, 52, 180), (w // 5, h // 4), (3 * w // 5, 3 * h // 4), 2)
        pygame.draw.line(paint, (60, 52, 46, 160), (2 * w // 3, h // 5), (w // 3, 4 * h // 5), 2)
    base.blit(paint, (0, 0))
    return base


def _theme_tex(name):
    if name not in _THEMES:
        _THEMES[name] = _paint_theme(name)
    return _THEMES[name]


def _theme_at(client, tiles, x, y):
    """Wall marks for the creature room this floor tile belongs to."""
    rooms = _rooms(tiles)
    origin = rooms.get((int(x), int(y)))
    if origin is None:
        return None
    key = id(tiles)
    if _ROOMS.get("theme_key") != key:
        chosen = {}
        for monster in (getattr(client, "monsters", None) or {}).values():
            if not monster.get("alive", True):
                continue
            spot = rooms.get((int(monster["x"]), int(monster["y"])))
            if spot is None:
                continue
            theme = _ROOM_THEME.get(monster.get("type"), "cracks")
            prev = chosen.get(spot)
            if prev is None or _THEME_RANK[theme] < _THEME_RANK[prev]:
                chosen[spot] = theme
        _ROOMS["theme_key"] = key
        _ROOMS["themes"] = chosen
    return _ROOMS["themes"].get(origin)


def _warm(color, glow):
    if glow <= 0.04:
        return color
    return (
        min(255, int(color[0] + 110 * glow)),
        min(255, int(color[1] + 58 * glow)),
        min(255, int(color[2] + 16 * glow)),
    )


def _candle(color, tex_u, v, flicker):
    """A sconce on the wall face: iron cup, flame, and a warm halo."""
    across = abs(tex_u - 0.5)
    if across > 0.22 or not (0.16 <= v <= 0.58):
        return color
    halo = max(0.0, 1.0 - across / 0.22) * flicker
    color = (
        min(255, int(color[0] + 90 * halo)),
        min(255, int(color[1] + 42 * halo)),
        int(color[2]),
    )
    if across < 0.07 and 0.38 <= v <= 0.52:
        return (62, 44, 32)
    if across < 0.045 * max(0.6, flicker) and 0.24 <= v <= 0.4:
        return (255, int(160 + 80 * flicker), 48)
    return color


def _stride(kind, now, tile, facing):
    """Screen step for a legged body that is not a pack sprite."""
    import emberdeep_creatures_client
    sway, bob, _rock, _squash = emberdeep_creatures_client._step(kind, now, tile, facing)
    return sway, bob


def _view(client, advance=False):
    """Eye, look, and the local pose. The drawn body can lead the camera."""
    import time
    tiles = client.tiles or []
    pose = _local_draw_args(client, time.time())
    if advance and tiles:
        _advance_camera(client, tiles, pose, time.time())
    state = getattr(client, "_ember_cam", None)
    if state and tiles:
        lx, ly = state["lx"], state["ly"]
        ex, ey = state["ex"], state["ey"]
        pose["draw_x"] = state["bx"]
        pose["draw_y"] = state["by"]
    else:
        lx, ly = pose["lx"], pose["ly"]
        ex, ey = _eye(tiles, pose["x"] + 0.5, pose["y"] + 0.5, lx, ly)
        pose["draw_x"] = pose["x"] + 0.5
        pose["draw_y"] = pose["y"] + 0.5
    rx, ry = _right(lx, ly)
    return tiles, pose, ex, ey, lx, ly, rx, ry


def _monster_pose(client, m, t):
    key = ("m", m["id"])
    x, y = m["x"], m["y"]
    px = client.player["x"]
    py = client.player["y"]
    face = _sprite_face(client, key, x, y, anim_id=m["id"])
    moving = _mark_moving(client, key, x, y)
    atk = client._attack_progress(m["id"], t)
    near = max(abs(x - px), abs(y - py)) <= 5
    from content import MONSTERS
    side_fight = bool((MONSTERS.get(m.get("type")) or {}).get("side_by_side"))
    if m["x"] != px and (atk > 0 or (side_fight and near)):
        face = 1 if px > m["x"] else -1
        client.attack_face[m["id"]] = face
    elif side_fight and m["x"] == px and near:
        face = client.attack_face.get(m["id"], 1)
        if face in ("front", "back"):
            face = 1
        client.attack_face[m["id"]] = face
    face = client.facing_for_view(face)
    swinging = m["id"] in client.attack_anims or str(m["id"]) in client.attack_anims
    if swinging:
        moving = False
    return face, moving and not swinging, atk, near, bool(side_fight and near)


def _draw_monster_sprite(client, m, cx, cy, tile_px, t, face, moving, atk, player_sx, drop_down=False):
    """The top-down monster chain, drawn at a projected foot point."""
    import procedural_sprites_finished as sprites
    import lowpoly_dragon_sprites
    import anim_strip_sprites
    import legacy_creature_sprites
    from content import MONSTERS
    main = sys.modules.get("__main__")
    lowpoly_on = getattr(main, "USE_LOWPOLY_DRAGONS", True)
    strip_on = getattr(main, "USE_ANIM_STRIP_MONSTERS", True)
    hurt = m["hp"] < m["max_hp"]
    mdef = MONSTERS.get(m["type"]) or {}
    vis = mdef.get("visual") or m["type"]
    scale = float(mdef.get("scale") or 1.0)
    ts = max(8, int(tile_px * scale))
    import time
    import emberdeep_creatures_client
    breathing = time.time() < (getattr(client, "ember_cone", None) or {}).get("until", 0)
    if moving and m.get("type") in _LEGS:
        step_x, step_y = _stride(_LEGS[m["type"]], t, ts, face)
        cx += step_x
        cy -= step_y
    # Static preview sheets have no walk or strike. Draw the animated body instead.
    animated = {"magma_slug": 34, "ash_imp": 46, "crucible_beast": 62}
    if vis in animated:
        ts = max(16, min(ts, animated[vis]))
        sprites.draw_monster(
            client.screen, vis, cx, cy, ts, t,
            hurt=hurt, attacking=atk, facing=face, moving=moving,
        )
        return
    if emberdeep_creatures_client.draw_creature(
        client.screen, m["type"], cx, cy, ts, facing=face, breathing=breathing,
        moving=moving, attacking=atk,
    ):
        return
    lowpoly = lowpoly_on and lowpoly_dragon_sprites.sheet_key_for_monster_type(m["type"])
    strip = (not lowpoly) and strip_on and anim_strip_sprites.sheet_key_for_monster_type(m["type"])
    if m.get("frozen"):
        pygame.draw.circle(client.screen, (140, 210, 255), (cx, cy), ts // 2 + 4, 2)
    atk_arg = atk if (m["id"] in client.attack_anims or str(m["id"]) in client.attack_anims) else -1.0
    if mdef.get("humanoid"):
        eq = mdef.get("equipment") or {}
        face_h = 1 if client.player["x"] >= m["x"] else -1
        sprites.draw_humanoid_detailed(
            client.screen, cx, cy, ts,
            (55, 70, 95), (220, 175, 140), (35, 28, 22),
            weapon=_weapon_style(eq.get("weapon")),
            shield=bool(eq.get("shield")),
            moving=moving, t=t, facing=face_h,
            equipment=eq, attacking=atk, gender="male",
        )
    elif lowpoly and lowpoly_dragon_sprites.draw_lowpoly_dragon(
        client.screen, vis, cx, cy, ts, t,
        hurt=hurt, attacking=atk_arg, facing=face, moving=moving,
        foe_cx=player_sx, drop_down=drop_down,
    ):
        pass
    elif strip and anim_strip_sprites.draw_anim_strip_monster(
        client.screen, vis, cx, cy, ts, t,
        hurt=hurt, attacking=atk_arg, facing=face, moving=moving,
        foe_cx=player_sx, drop_down=drop_down,
    ):
        pass
    elif feature_flags.USE_NEW_PETS_AND_MONSTERS and legacy_creature_sprites.draw_monster(
        client.screen, vis, cx, cy, ts, t,
        hurt=hurt, attacking=atk_arg, facing=face, moving=moving,
    ):
        pass
    else:
        sprites.draw_monster(
            client.screen, vis, cx, cy, ts, t,
            hurt=hurt, attacking=atk, facing=face, moving=moving,
        )
    if mdef.get("visual"):
        import void_v2_client
        void_v2_client.tint_and_halo(client, m, cx, cy, ts)


def _label_anchor(cy, tile_px, kind):
    import rs_style
    lift = rs_style.label_lift(tile_px, kind)
    hp_y = cy - lift
    return hp_y - 16, hp_y


def _draw_local_player(client, pose, sx, sy, tile_px, t):
    import procedural_sprites_finished as sprites
    sprites.draw_humanoid_detailed(
        client.screen, sx, sy, tile_px,
        (70, 210, 90), (235, 195, 150), (70, 45, 30),
        weapon=_weapon_style(pose["eq"].get("weapon")),
        shield=bool(pose["eq"].get("shield")),
        moving=pose["moving"], t=t, facing=pose["face"],
        equipment=pose["eq"], attacking=pose["atk"], action=pose["action"],
        gender=pose["gender"],
    )


def _draw_billboards(client, pose, ex, ey, lx, ly, rx, ry, depths, rw, rh, mw, mh):
    import time
    t = time.time()
    bills = []
    client._ember_screen_anchor = {}
    client._ember_nest_drop = 0
    player_sx = mw // 2
    bx = pose.get("draw_x", pose["x"] + 0.5)
    by = pose.get("draw_y", pose["y"] + 0.5)
    projected = _project(ex, ey, lx, ly, rx, ry, bx, by, None, rw, rh, mw, mh)
    if projected is None:
        along_p = max(0.35, (bx - ex) * lx + (by - ey) * ly)
        side_p = (bx - ex) * rx + (by - ey) * ry
        angle_p = math.atan2(side_p, max(0.2, along_p))
        psx = int((0.5 + angle_p / _FOV) * mw)
        psy = min(mh - 8, _feet_y(along_p, rh, mh))
        ptile = _tile_px(along_p, mh)
        projected = (along_p, psx, psy, ptile)
    along_p, psx, psy, ptile = projected
    player_sx = psx
    # The eye stays above and behind. The body keeps a full size in the lower frame.
    player_sy = min(mh - 8, max(psy, int(mh * 0.74)))
    player_tile = max(ptile, int(mh * 0.11))
    bills.append((max(0.2, along_p), "player", psx, player_sy, player_tile, None))
    seen = {pose["key"]: (pose["x"], pose["y"])}
    floor = client.tiles or []
    fighting = []
    for m in (client.monsters or {}).values():
        if not m.get("alive", True):
            continue
        _face, moving, atk, near, drop_down = _monster_pose(client, m, t)
        seen[("m", m["id"])] = (m["x"], m["y"])
        dist = max(abs(m["x"] - pose["x"]), abs(m["y"] - pose["y"]))
        targeted = client.combat_target_id == m["id"]
        # The wyrm stays in its chamber. Everyone else steps forward only
        # when you are standing on the next tile, so the room stays visible.
        beside = dist <= 1 and m.get("type") != "emberdeep_wyrm"
        if beside and _open_between(floor, pose["x"], pose["y"], m["x"], m["y"]):
            fighting.append((0 if targeted else dist, m, moving, atk, drop_down))
            continue
        wx, wy = _sprite_world(m)
        proj = _project(
            ex, ey, lx, ly, rx, ry, wx, wy,
            depths, rw, rh, mw, mh,
        )
        if proj is None:
            continue
        along, sx, sy, tile_px = proj
        if m.get("type") == "emberdeep_wyrm":
            # The north of the lair collapses onto the back wall. Drop the
            # body into the open floor so it stands in the middle of the room.
            want = int(mh * 0.60)
            client._ember_nest_drop = max(0, want - sy)
            sy = max(sy, want)
        face = _face_from_vector(pose["x"] - m["x"], pose["y"] - m["y"])
        bills.append((along, "monster", sx, sy, tile_px, (m, face, moving, atk, near or targeted, drop_down)))
    dungeon = client.dungeon or {}
    if dungeon.get("id") == "emberdeep":
        for prop in dungeon.get("props") or []:
            if prop.get("pack") != "emberdeep_creatures":
                continue
            proj = _project(
                ex, ey, lx, ly, rx, ry,
                int(prop["x"]) + 0.5, int(prop["y"]) + 0.5,
                depths, rw, rh, mw, mh,
            )
            if proj is None:
                continue
            along, sx, sy, tile_px = proj
            key = prop.get("key") or ""
            if key.startswith("dragon_egg") and 18 <= int(prop["x"]) <= 26 and int(prop["y"]) <= 6:
                sy += int(getattr(client, "_ember_nest_drop", 0) * 0.92)
            bills.append((along, "pack_prop", sx, sy, tile_px, key))
    bills.sort(key=lambda item: -item[0])
    for along, kind, sx, sy, tile_px, extra in bills:
        if kind == "player":
            _draw_local_player(client, pose, sx, sy, tile_px, t)
            anchors = getattr(client, "_ember_screen_anchor", None)
            if not isinstance(anchors, dict):
                anchors = {}
                client._ember_screen_anchor = anchors
            pid = pose.get("key", (None, None))[1]
            anchors[("p", pid)] = (sx, sy, tile_px)
            anchors[("p", str(pid))] = (sx, sy, tile_px)
            p = client.player or {}
            client.draw_hp_bar(sx, sy - tile_px - 8, p.get("hp", 1), p.get("max_hp", 1), show_value=True)
            continue
        if kind == "pack_prop":
            import emberdeep_creatures_client
            # Distant props were specks. Keep them big enough to read as objects.
            emberdeep_creatures_client.draw_prop(
                client.screen, extra, sx, sy, max(tile_px, 78),
            )
            continue
        m, face, moving, atk, show, drop_down = extra
        # Distant sprites were a few pixels tall. Keep a readable floor, then let body scale separate them.
        # The wyrm is capped so its body sits in the lair instead of covering the back wall.
        if m.get("type") == "emberdeep_wyrm":
            tile_px = min(max(tile_px, 64), 72)
        elif m.get("type") == "magma_slug":
            tile_px = max(tile_px, 28)
        else:
            tile_px = max(tile_px, 72)
        _draw_monster_sprite(client, m, sx, sy, tile_px, t, face, moving, atk, player_sx, drop_down)
        import emberdeep_creatures_client
        height = emberdeep_creatures_client.creature_height(m["type"], tile_px)
        anchors = getattr(client, "_ember_screen_anchor", None)
        if isinstance(anchors, dict):
            anchors[("m", m["id"])] = (sx, sy, height)
            anchors[("m", str(m["id"]))] = (sx, sy, height)
        bar_y = max(22, min(mh - 28, sy - height - 6))
        client.draw_hp_bar(sx, bar_y, m["hp"], m["max_hp"])
        if not show:
            continue
        client.blit_nameplate(m["name"], sx, bar_y - 14)
        level = int(m.get("level") or 1)
        client.blit_combat_level(level, sx, bar_y - 28, client.monster_threat_color(level))
    _draw_opponents(client, pose, fighting, mw, mh, t, psx, player_sy, player_tile)
    _draw_projectiles(client, ex, ey, lx, ly, rx, ry, rw, rh, mw, mh)
    _draw_hitsplats(client, ex, ey, lx, ly, rx, ry, depths, rw, rh, mw, mh)
    prev = dict(getattr(client, "_prev_entity_pos", {}) or {})
    prev.update(seen)
    client._prev_entity_pos = prev
    _draw_corner_map(client, lx, ly)
    return True


def _draw_opponents(client, pose, fighting, mw, mh, t, player_sx, player_sy, player_tile):
    """Line up whoever is in reach just in front of the player."""
    client._ember_fight_hits = []
    if not fighting:
        return
    fighting = sorted(fighting, key=lambda item: (item[0], item[1]["id"]))[:3]
    count = len(fighting)
    tile = max(96, int(player_tile * 2.4))
    import emberdeep_creatures_client
    widths = [
        max(tile, emberdeep_creatures_client.creature_height(m["type"], tile))
        for _dist, m, _moving, _atk, _drop in fighting
    ]
    gap = int(max(widths) * 1.15) if widths else tile * 2
    origin = player_sx - (count - 1) * gap // 2
    feet = max(tile + 8, player_sy - int(player_tile * 1.35))
    anchors = getattr(client, "_ember_screen_anchor", None)
    if not isinstance(anchors, dict):
        anchors = {}
        client._ember_screen_anchor = anchors
    hits = []
    for index, (_dist, m, moving, atk, drop_down) in enumerate(fighting):
        sx = origin + index * gap
        face = _face_from_vector(pose["x"] - m["x"], pose["y"] - m["y"])
        _draw_monster_sprite(client, m, sx, feet, tile, t, face, moving, atk, player_sx, drop_down)
        height = emberdeep_creatures_client.creature_height(m["type"], tile)
        anchors[("m", m["id"])] = (sx, feet, height)
        anchors[("m", str(m["id"]))] = (sx, feet, height)
        hits.append((
            pygame.Rect(sx - height // 2, feet - height, height, height),
            (int(m["x"]), int(m["y"])),
        ))
        bar_y = feet - height - 6
        client.draw_hp_bar(sx, bar_y, m["hp"], m["max_hp"])
        client.blit_nameplate(m["name"], sx, bar_y - 14)
        level = int(m.get("level") or 1)
        client.blit_combat_level(level, sx, bar_y - 28, client.monster_threat_color(level))
    client._ember_fight_hits = hits


def _draw_corner_map(client, lx, ly):
    """Small floor plan in the corner. Up on the map is north."""
    tiles = client.tiles or []
    if not tiles or not client.player:
        client._ember_map_rect = None
        return
    height = len(tiles)
    width = len(tiles[0]) if height else 0
    if width <= 0:
        return
    size = 156
    mw, _mh = _map_size()
    rect = pygame.Rect(mw - size - 12, 12, size, size)
    client._ember_map_rect = rect
    surf = pygame.Surface((size, size))
    surf.fill((16, 12, 14))
    for y in range(height):
        y0 = int(y * size / height)
        y1 = max(y0 + 1, int((y + 1) * size / height))
        row = tiles[y]
        for x in range(width):
            tile = row[x]
            if tile == wm.WALL:
                color = (42, 28, 26)
            elif tile == wm.WATER:
                color = (176, 64, 22)
            else:
                color = (92, 74, 58)
            x0 = int(x * size / width)
            x1 = max(x0 + 1, int((x + 1) * size / width))
            surf.fill(color, (x0, y0, x1 - x0, y1 - y0))
    px, py = int(client.player["x"]), int(client.player["y"])

    def _dot(tx, ty):
        return int((tx + 0.5) * size / width), int((ty + 0.5) * size / height)

    for mon in (client.monsters or {}).values():
        if not mon.get("alive", True):
            continue
        mx, my = _dot(mon["x"], mon["y"])
        fought = client.combat_target_id == mon["id"]
        pygame.draw.circle(surf, (255, 214, 90) if fought else (214, 64, 52), (mx, my), 3 if fought else 2)
    sx, sy = _dot(px, py)
    pygame.draw.line(
        surf, (150, 230, 130),
        (sx, sy),
        (int(sx + lx * 10), int(sy + ly * 10)),
        2,
    )
    pygame.draw.circle(surf, (40, 40, 40), (sx, sy), 4)
    pygame.draw.circle(surf, (90, 220, 110), (sx, sy), 3)
    frame = rect.inflate(4, 4)
    pygame.draw.rect(client.screen, (12, 10, 12), frame)
    pygame.draw.rect(client.screen, (180, 120, 60), frame, 2)
    client.screen.blit(surf, rect.topleft)


def _screen_of(ex, ey, lx, ly, rx, ry, wx, wy, rw, rh, mw, mh):
    proj = _project(ex, ey, lx, ly, rx, ry, wx, wy, None, rw, rh, mw, mh)
    if proj is None:
        return None
    return proj


def _draw_hitsplats(client, ex, ey, lx, ly, rx, ry, depths, rw, rh, mw, mh):
    import time
    now = time.time()
    client._flush_pending_floaters(now)
    client.floaters = [f for f in client.floaters if f["expire"] > now]
    anchors = getattr(client, "_ember_screen_anchor", None) or {}
    my_id = (client.player or {}).get("id")
    for floater in client.floaters:
        follow = floater.get("follow_id")
        if follow is not None:
            xy = client._entity_world_xy(follow)
            if xy is not None:
                floater["x"], floater["y"] = xy
        placed = None
        if follow is not None:
            if follow == my_id:
                placed = anchors.get(("p", my_id))
            else:
                placed = anchors.get(("m", follow))
                if placed is None:
                    try:
                        placed = anchors.get(("m", int(follow)))
                    except (TypeError, ValueError):
                        placed = None
        if placed is not None:
            sx, sy, tile_px = placed
        else:
            proj = _project(
                ex, ey, lx, ly, rx, ry,
                floater["x"] + 0.5, floater["y"] + 0.5,
                None, rw, rh, mw, mh, reveal=True,
            )
            if proj is None and follow == my_id:
                placed = anchors.get(("p", my_id))
                if placed is None:
                    continue
                sx, sy, tile_px = placed
            elif proj is None:
                continue
            else:
                _along, sx, sy, tile_px = proj
        age_left = floater["expire"] - now
        lift = int((1.0 - min(1.0, age_left / 1.3)) * 22)
        py = sy - max(28, int(tile_px) + 16) - lift
        kind = floater.get("kind")
        if kind in ("hit_red", "hit_green", "hit_blue", "hit_miss", "hit_crit", "hit_thorns"):
            client.draw_hit_star(sx, py, floater["text"], floater["color"], kind=kind)
        elif kind == "level_up":
            client.draw_level_up_floater(sx, py - 18, floater["text"], floater["color"], age_left)
        else:
            font = client.font_big if kind == "stat_boost" else client.font
            surf = font.render(floater["text"], True, floater["color"])
            client.screen.blit(surf, (sx - surf.get_width() // 2, py - 8))


def _draw_projectiles(client, ex, ey, lx, ly, rx, ry, rw, rh, mw, mh):
    import time
    now = time.time()
    keep = []
    for proj in client.projectiles:
        ff, ft = proj.get("follow_from"), proj.get("follow_to")
        if ff is not None:
            xy = client._entity_world_xy(ff)
            if xy:
                proj["ax"], proj["ay"] = xy
        if ft is not None:
            xy = client._entity_world_xy(ft)
            if xy:
                proj["tx"], proj["ty"] = xy
        start = proj["start"]
        dur = max(0.05, proj["dur"])
        if now < start:
            keep.append(proj)
            continue
        u = (now - start) / dur
        if u >= 1.0:
            continue
        ease = 1.0 - (1.0 - u) * (1.0 - u)
        ax, ay = proj["ax"], proj["ay"]
        tx, ty = proj["tx"], proj["ty"]
        wx = ax + (tx - ax) * ease
        wy = ay + (ty - ay) * ease
        spot = _screen_of(ex, ey, lx, ly, rx, ry, wx + 0.5, wy + 0.5, rw, rh, mw, mh)
        if spot is None:
            keep.append(proj)
            continue
        _along, sx, sy, _tile = spot
        arc = math.sin(ease * math.pi) * 18
        sy = int(sy - arc)
        kind = proj.get("kind") or "arrow"
        if kind == "dragonfire":
            for col, rad in (((255, 120, 40), 14), ((255, 180, 50), 9), ((255, 240, 160), 5)):
                pygame.draw.circle(client.screen, col, (sx, sy), rad)
        else:
            dx, dy = (tx - ax), (ty - ay)
            length = max(0.01, math.hypot(dx, dy))
            ux, uy = dx / length, dy / length
            tip = (sx + ux * 10, sy + uy * 10)
            tail = (sx - ux * 8, sy - uy * 8)
            pygame.draw.line(client.screen, (150, 105, 55), tail, tip, 3)
            pygame.draw.line(client.screen, (210, 175, 120), tail, tip, 1)
            pygame.draw.circle(client.screen, (190, 195, 205), (int(tip[0]), int(tip[1])), 3)
            fx, fy = -uy, ux
            pygame.draw.line(
                client.screen, (245, 245, 250),
                (tail[0] + fx * 4, tail[1] + fy * 4),
                (tail[0] - fx * 4, tail[1] - fy * 4),
                2,
            )
        keep.append(proj)
    client.projectiles = keep


def draw_magic(client):
    """Project spell bursts onto the follow view. False keeps the top-down pass."""
    if not _in_emberdeep(client) or not client.magic_fx:
        return False
    tiles, _pose, ex, ey, lx, ly, rx, ry = _view(client)
    if not tiles:
        return False
    import time
    now = time.time()
    mw, mh = _map_size()
    rw, rh = max(160, mw // 2), max(120, mh // 2)
    for fx in client.magic_fx:
        spot = _screen_of(ex, ey, lx, ly, rx, ry, fx["x"] + 0.5, fx["y"] + 0.5, rw, rh, mw, mh)
        if spot is None:
            continue
        _along, sx, sy, _tile = spot
        effect = fx.get("effect") or "lightning"
        life = max(0.05, fx["until"] - now)
        u = 1.0 - min(1.0, life / 0.85)
        if effect == "fire":
            col = (255, 120 + int(80 * (1 - u)), 40)
            for i in range(5):
                pygame.draw.circle(
                    client.screen, col,
                    (sx + int(math.sin(u * 9 + i) * 10), sy - int(u * 28) - i * 4),
                    max(2, 8 - i),
                )
        elif effect == "freeze":
            col = (160, 220, 255)
            pygame.draw.circle(client.screen, col, (sx, sy), int(10 + u * 18), 2)
            pygame.draw.circle(client.screen, (200, 240, 255), (sx, sy - 4), 4)
        else:
            col = (200, 230, 255)
            pts = [(sx, sy - 28), (sx + 6, sy - 14), (sx - 4, sy - 10), (sx + 8, sy), (sx, sy + 6)]
            pygame.draw.lines(client.screen, col, False, pts, 2)
        if fx.get("damage"):
            dmg = client.font_small.render(str(fx["damage"]), True, (236, 198, 72))
            client.screen.blit(dmg, (sx - dmg.get_width() // 2, sy - 40 - int(u * 12)))
    return True


def draw_first_person(client):
    """Follow the player through Emberdeep. Returns False when the top-down map should draw."""
    import time
    if not _in_emberdeep(client):
        client._ember_cam = None
        return False
    apply_zoom(client)
    tiles, pose, ex, ey, lx, ly, rx, ry = _view(client, advance=True)
    if not tiles:
        return False
    mw, mh = _map_size()
    rw, rh = max(160, mw // 2), max(120, mh // 2)
    view = pygame.Surface((rw, rh))
    boss = client.dungeon.get("boss_door")
    horizon = int(rh * _HORIZON)
    depths = [1e9] * rw
    pix = pygame.PixelArray(view)
    ceiling = _texture("ceiling_dark.png")
    glow, sconces = _sconces(tiles)
    flicker = 0.72 + 0.28 * abs(math.sin(time.time() * 9.0))
    breath = set()
    for mon in (client.monsters or {}).values():
        if mon.get("alive", True) and mon.get("type") == "emberdeep_wyrm":
            breath |= _cone_spots(mon)
    cone = getattr(client, "ember_cone", None) or {}
    hot = breath if time.time() < cone.get("until", 0) else set()
    for col in range(rw):
        cam = (col / max(1, rw - 1) - 0.5) * _FOV
        rdx = lx * math.cos(cam) + rx * math.sin(cam)
        rdy = ly * math.cos(cam) + ry * math.sin(cam)
        dist, wx, wy, tex_u, side, step_x, step_y = _cast(tiles, ex, ey, rdx, rdy)
        depths[col] = dist
        # A higher eye would still fill the screen with the nearest wall.
        # Shrink that face with the lift so the floor and the hall beyond show.
        wall_scale = (2.05 / max(2.05, _CAM_Z)) ** 0.55
        wall_h = min(rh, int(rh / max(0.2, dist) * wall_scale))
        # Plant the wall on the raised camera's floor line instead of the horizon.
        floor_y = int(horizon * (1.0 + _CAM_Z / max(0.2, dist)))
        bot = min(rh - 1, max(horizon + 4, floor_y))
        top = max(0, bot - wall_h)
        face_x = wx - step_x if side == 0 else wx
        face_y = wy if side == 0 else wy - step_y
        wall_name = _wall_name(tiles, wx, wy, boss)
        theme = None
        if wall_name == "wall_rock.png":
            theme = _theme_at(client, tiles, face_x, face_y)
        wall_tex = _theme_tex(theme) if theme else _texture(wall_name)
        sconce = (face_x, face_y) in sconces
        face_glow = 0.0
        if 0 <= face_y < len(glow) and 0 <= face_x < len(glow[0]):
            face_glow = glow[face_y][face_x]
        for y in range(rh):
            if top <= y <= bot:
                v = (y - top) / max(1, bot - top)
                color = _sample(wall_tex, tex_u, v)
                # Near stone is lit; the far face and the side grain fall off.
                light = min(255, int(150 + 110 / max(0.4, dist)))
                if side == 1:
                    light = int(light * 0.78)
                light = int(light * (0.72 + 0.28 * (1.0 - v)))
                color = (
                    min(255, color.r * light // 200),
                    min(255, color.g * light // 200),
                    min(255, color.b * light // 200),
                )
                if sconce:
                    color = _candle(color, tex_u, v, flicker)
                color = _warm(color, max(face_glow, 0.35 if sconce else face_glow))
            elif y < horizon:
                row = (horizon - y) / max(1, horizon)
                current = _CAM_Z / max(0.05, row)
                fx = ex + rdx * current
                fy = ey + rdy * current
                color = _sample(ceiling, fx, fy)
                color = (color.r // 2, color.g // 2, color.b // 2)
                ix, iy = int(fx), int(fy)
                if 0 <= iy < len(glow) and 0 <= ix < len(glow[0]):
                    color = _warm(color, glow[iy][ix] * 0.65)
            else:
                row = (y - horizon) / max(1, horizon)
                current = _CAM_Z / max(0.05, row)
                fx = ex + rdx * current
                fy = ey + rdy * current
                floor_tex = _texture(_floor_name(tiles, int(fx), int(fy)))
                color = _sample_floor(floor_tex, tiles, fx, fy)
                floor_dist_fade = min(240, int(140 + 100 / max(0.5, current)))
                color = (
                    min(255, (color.r * 3 + 50) // 4 * floor_dist_fade // 255),
                    min(255, (color.g * 3 + 35) // 4 * floor_dist_fade // 255),
                    min(255, (color.b * 3 + 20) // 4 * floor_dist_fade // 255)
                )
                ix, iy = int(fx), int(fy)
                if (ix, iy) in breath:
                    heat = 0.72 if (ix, iy) in hot else 0.4
                    color = (
                        min(255, int(color[0] * (1 - heat) + 220 * heat)),
                        min(255, int(color[1] * (1 - heat) + 90 * heat)),
                        min(255, int(color[2] * (1 - heat) + 24 * heat)),
                    )
                if 0 <= iy < len(glow) and 0 <= ix < len(glow[0]):
                    color = _warm(color, glow[iy][ix])
            pix[col, y] = color
    del pix
    px, py = int(pose["x"]), int(pose["y"])
    _draw_tile_highlight(view, ex, ey, lx, ly, rx, ry, px, py, rw, rh, mw, mh, (180, 200, 120), 2)
    next_dx, next_dy = 0, 0
    if abs(lx) >= abs(ly):
        next_dx = 1 if lx > 0 else -1
    else:
        next_dy = 1 if ly > 0 else -1
    next_x, next_y = px + next_dx, py + next_dy
    if _tile_at(tiles, next_x, next_y) == wm.FLOOR:
        _draw_tile_highlight(view, ex, ey, lx, ly, rx, ry, next_x, next_y, rw, rh, mw, mh, (150, 170, 100), 1)
    scaled = pygame.transform.scale(view, (mw, mh))
    client.screen.blit(scaled, (0, 0))
    _draw_billboards(client, pose, ex, ey, lx, ly, rx, ry, depths, rw, rh, mw, mh)
    draw_zoom_controls(client)
    return True


def _sprite_hit(mx, my, sx, sy, tile_px):
    height = int(tile_px * 1.6)
    width = int(tile_px * 0.9)
    rect = pygame.Rect(sx - width // 2, sy - height, width, height)
    return rect.collidepoint(mx, my)


def pick_tile(client, mx, my):
    """Map a follow-view click onto a dungeon tile. None keeps the top-down picker."""
    if not _in_emberdeep(client):
        return None
    apply_zoom(client)
    mw, mh = _map_size()
    if mx < 0 or my < 0 or mx >= mw or my >= mh:
        return None
    box = getattr(client, "_ember_map_rect", None)
    if box is not None and box.collidepoint(mx, my):
        return int(client.player["x"]), int(client.player["y"])
    tiles, _pose, ex, ey, lx, ly, rx, ry = _view(client)
    if not tiles:
        return None
    rw, rh = max(160, mw // 2), max(120, mh // 2)
    for rect, tile in getattr(client, "_ember_fight_hits", None) or []:
        if rect.collidepoint(mx, my):
            return tile
    best = None
    best_d = 1e9
    px, py = int(client.player["x"]), int(client.player["y"])
    body = _project(ex, ey, lx, ly, rx, ry, px + 0.5, py + 0.5, None, rw, rh, mw, mh)
    player_sx = body[1] if body else mw // 2
    player_tile = max(16, int((body[3] if body else 32) * 0.55))
    for mon in (client.monsters or {}).values():
        if not mon.get("alive", True):
            continue
        dist = max(abs(mon["x"] - px), abs(mon["y"] - py))
        fighting = client.combat_target_id == mon["id"] or dist <= 2
        wx, wy = _sprite_world(mon)
        proj = _project(
            ex, ey, lx, ly, rx, ry, wx, wy,
            None, rw, rh, mw, mh, reveal=fighting or mon.get("type") == "emberdeep_wyrm",
        )
        if proj is None:
            continue
        along, sx, sy, tile_px = proj
        if fighting and mon.get("type") != "emberdeep_wyrm":
            tile_px = max(tile_px, int(player_tile * 1.15))
            if abs(sx - player_sx) < player_tile:
                sx = player_sx + (player_tile if (int(mon["id"]) % 2 == 0) else -player_tile)
        if mon.get("type") == "emberdeep_wyrm":
            import emberdeep_creatures_client
            height = emberdeep_creatures_client.creature_height("emberdeep_wyrm", min(max(tile_px, 64), 72))
            width = int(height * 1.5)
            hit = pygame.Rect(sx - width // 2, sy - height, width, height).collidepoint(mx, my)
        else:
            hit = _sprite_hit(mx, my, sx, sy, tile_px)
        if hit and along < best_d:
            best = (int(mon["x"]), int(mon["y"]))
            best_d = along
    if best:
        return best
    cam = (mx / max(1, mw - 1) - 0.5) * _FOV
    rdx = lx * math.cos(cam) + rx * math.sin(cam)
    rdy = ly * math.cos(cam) + ry * math.sin(cam)
    length = math.hypot(rdx, rdy) or 1.0
    rdx /= length
    rdy /= length
    dist, _wx, _wy, _tex, _side, _step_x, _step_y = _cast(tiles, ex, ey, rdx, rdy)
    travel = max(0.75, dist - 0.4)
    tx = int(ex + rdx * travel)
    ty = int(ey + rdy * travel)
    if _tile_at(tiles, tx, ty) != wm.FLOOR:
        tx = int(ex + rdx * 0.75)
        ty = int(ey + rdy * 0.75)
    return tx, ty
