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

_LEGS = {
    "ash_imp": "biped",
    "magma_knight": "biped",
    "crucible_beast": "quad",
    "ember_wolf": "quad",
}
_PACK = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", "..", "emberdeep_v2_pack"))
_APRON = (176, 58, 198, 94)  # inclusive world tiles
_IMAGES = {}
_SCALED = {}
_TEX_DIR = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", "..", "emberdeep_hd", "textures"))
_VIEW = None
_VIEW_KEY = None
_FRAME = {}
_RENDER_MS = []
_INTERNAL_SCALE = 0.42
_PRESETS = (0.0, 0.5, 1.0)
_PRESET_NAMES = ("Near", "Mid", "Far")


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
    z = float(getattr(client, "ember_zoom", 0.35) or 0.0)
    return min(range(len(_PRESETS)), key=lambda i: abs(_PRESETS[i] - z))


def adjust_zoom(client, delta):
    """delta < 0 zooms out (raises the camera)."""
    import time
    current = getattr(client, "ember_zoom", 0.35)
    if not isinstance(current, float):
        current = _PRESETS[max(0, min(2, int(current or 0)))]
    target = max(0.0, min(1.0, float(current) - float(delta) * 0.10))
    client.ember_zoom = target
    client._zoom_toast_until = time.time() + 1.2


def set_zoom(client, level):
    import time
    level = max(0, min(2, int(level)))
    client.ember_zoom = _PRESETS[level]
    client._zoom_toast_until = time.time() + 1.2


def zoom_label(client):
    return _PRESET_NAMES[zoom_level(client)]


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
    for level in range(len(_PRESETS) - 1, -1, -1):
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
            label = _PRESET_NAMES[action]
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


# One key press turns the view this far. The drawn yaw eases toward it.
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
    """Outline a floor tile using the follow camera."""
    cam = _VIEW
    if cam is None:
        return
    screen_pts = []
    scale_x = mw / float(getattr(cam, "_last", (rw, rh))[0] or rw)
    scale_y = mh / float(getattr(cam, "_last", (rw, rh))[1] or rh)
    for cx, cy in ((tile_x, tile_y), (tile_x + 1, tile_y), (tile_x + 1, tile_y + 1), (tile_x, tile_y + 1)):
        hit = cam.project(cx, cy, 0.02)
        if hit is None:
            return
        _depth, sx, sy, _px = hit
        screen_pts.append((int(sx * scale_x), int(sy * scale_y)))
    for i in range(4):
        p1 = screen_pts[i]
        p2 = screen_pts[(i + 1) % 4]
        pygame.draw.line(view, color, p1, p2, thickness)


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


def _ensure_view(client):
    global _VIEW, _VIEW_KEY
    tiles = client.tiles
    if not tiles:
        return None
    boss = (client.dungeon or {}).get("boss_door")
    key = (id(tiles), tuple(boss) if isinstance(boss, (list, tuple)) else boss)
    if _VIEW is None or _VIEW_KEY != key:
        from emberdeep_view3d import EmberView3D
        _VIEW = EmberView3D(
            tiles, _TEX_DIR,
            lambda tile: tile == wm.WALL,
            lambda tile: tile == wm.WATER,
            boss_door=boss,
        )
        _VIEW_KEY = key
        _FRAME.clear()
    return _VIEW


def _ease_follow(client, pose, now):
    """Smooth focus, yaw and zoom. Returns focus, drawn yaw, zoom and dt."""
    current = getattr(client, "ember_zoom", 0.35)
    if not isinstance(current, float):
        current = 0.35
    client.ember_zoom = max(0.0, min(1.0, float(current)))
    prev = float(getattr(client, "_ember_cam_t", now) or now)
    dt = max(0.0, min(0.1, now - prev))
    client._ember_cam_t = now
    zoom = float(getattr(client, "_ember_zoom_cur", client.ember_zoom))
    zoom += (client.ember_zoom - zoom) * (1 - math.exp(-dt * 10.0))
    want_x, want_y = pose["x"] + 0.5, pose["y"] + 0.5
    foe = (getattr(client, "monsters", None) or {}).get(getattr(client, "combat_target_id", None))
    if foe and foe.get("alive", True):
        if max(abs(foe["x"] - pose["x"]), abs(foe["y"] - pose["y"])) <= 3:
            want_x = want_x * 0.65 + (foe["x"] + 0.5) * 0.35
            want_y = want_y * 0.65 + (foe["y"] + 0.5) * 0.35
            zoom = max(zoom, 0.25)
    client._ember_zoom_cur = zoom
    fx, fy = want_x, want_y
    ox, oy = getattr(client, "_ember_focus", (fx, fy))
    kf = 1 - math.exp(-dt / 0.12) if dt else 1.0
    fx = ox + (fx - ox) * kf
    fy = oy + (fy - oy) * kf
    client._ember_focus = (fx, fy)
    target = float(getattr(client, "_ember_yaw", 0.0))
    yaw = float(getattr(client, "_ember_yaw_draw", target))
    delta = (target - yaw + math.pi) % (2 * math.pi) - math.pi
    yaw += delta * kf
    client._ember_yaw_draw = yaw
    return fx, fy, yaw, zoom, dt


def _heights_settling(view):
    gap = view.heights_target - view.heights
    return bool((abs(gap) > 0.02).any())


def _render_cached(view, mw, mh, now, fx, fy, yaw, zoom):
    global _INTERNAL_SCALE
    rw = max(96, int(round(mw * _INTERNAL_SCALE)))
    rh = max(64, int(round(mh * _INTERNAL_SCALE)))
    state = _FRAME.get("state")
    if state and _FRAME.get("surf") is not None:
        cfx, cfy, cyaw, cz, ct = state
        if (
            abs(fx - cfx) < 0.005 and abs(fy - cfy) < 0.005
            and abs(yaw - cyaw) < 0.002 and abs(zoom - cz) < 0.002
            and now - ct < (1.0 / 15.0)
            and not _heights_settling(view)
            and _FRAME.get("rw") == rw
        ):
            return _FRAME["surf"], rw, rh
    import time
    started = time.perf_counter()
    rgb, _depth = view.render(rw, rh, now)
    elapsed = (time.perf_counter() - started) * 1000.0
    _RENDER_MS.append(elapsed)
    if len(_RENDER_MS) > 30:
        del _RENDER_MS[:-30]
    if len(_RENDER_MS) >= 30 and sum(_RENDER_MS) / len(_RENDER_MS) > 45.0 and _INTERNAL_SCALE > 0.30:
        _INTERNAL_SCALE = max(0.30, _INTERNAL_SCALE - 0.04)
    surf = pygame.surfarray.make_surface(rgb.swapaxes(0, 1))
    _FRAME["surf"] = surf
    _FRAME["state"] = (fx, fy, yaw, zoom, now)
    _FRAME["rw"] = rw
    _FRAME["rh"] = rh
    return surf, rw, rh


def _project(ex, ey, lx, ly, rx, ry, wx, wy, depths, rw, rh, mw, mh, reveal=False):
    """World point -> (depth, map x, map y, px per tile)."""
    cam = _VIEW
    if cam is None or not hasattr(cam, "_last"):
        return None
    hit = cam.project(float(wx), float(wy), 0.0)
    if hit is None:
        return None
    depth, sx, sy, px = hit
    last_w, last_h = cam._last[0], cam._last[1]
    return depth, sx * mw / float(last_w), sy * mh / float(last_h), px * mw / float(last_w)


def _cone_spots(monster):
    spots = set()
    for spot in (monster or {}).get("cone_tiles") or []:
        if isinstance(spot, dict):
            spots.add((int(spot["x"]), int(spot["y"])))
        else:
            spots.add((int(spot[0]), int(spot[1])))
    return spots


def wyrm_swing_tiles(monster):
    """Breath tiles plus the ring around the body. Matches the server."""
    import emberdeep_creatures
    ax, ay = int(monster["x"]), int(monster["y"])
    return emberdeep_creatures.swing_tiles(
        monster.get("cone_tiles") or [],
        emberdeep_creatures.footprint(ax, ay),
    )


def wyrm_approach_goals(monster):
    """Stand in front of the head, not on the right flank."""
    ax, ay = int(monster["x"]), int(monster["y"])
    facing = str(monster.get("facing") or "s")
    if facing in ("e", "east"):
        goals = {(ax + 3, ay), (ax + 3, ay - 1), (ax + 3, ay + 1)}
    elif facing in ("w", "west"):
        goals = {(ax - 3, ay), (ax - 3, ay - 1), (ax - 3, ay + 1)}
    else:
        goals = {(ax, ay + 2), (ax - 1, ay + 2), (ax + 1, ay + 2)}
    swing = wyrm_swing_tiles(monster)
    front = {spot for spot in goals if spot in swing}
    return front or goals or swing


def _sprite_world(monster):
    """Feet of a billboard."""
    return monster["x"] + 0.5, monster["y"] + 0.5


def _wyrm_glide(client, monster, now):
    """Slide the wyrm between server tiles over one tick."""
    glides = getattr(client, "_wyrm_glide", None)
    if not isinstance(glides, dict):
        glides = {}
        client._wyrm_glide = glides
    tile = (int(monster["x"]), int(monster["y"]))
    rec = glides.get(monster["id"])
    if rec is None or rec.get("tile") != tile:
        origin = rec["pos"] if rec else (tile[0] + 0.5, tile[1] + 0.5)
        rec = {"tile": tile, "from": origin, "t0": now}
        glides[monster["id"]] = rec
    u = min(1.0, (now - rec["t0"]) / 0.6)
    x = rec["from"][0] + (tile[0] + 0.5 - rec["from"][0]) * u
    y = rec["from"][1] + (tile[1] + 0.5 - rec["from"][1]) * u
    rec["pos"] = (x, y)
    return x, y, u < 1.0


def _tile_at(tiles, x, y):
    if y < 0 or x < 0 or y >= len(tiles) or x >= len(tiles[0]):
        return wm.WALL
    return tiles[y][x]


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


def _stride(kind, now, tile, facing):
    """Screen step for a legged body that is not a pack sprite."""
    import emberdeep_creatures_client
    sway, bob, _rock, _squash = emberdeep_creatures_client._step(kind, now, tile, facing)
    return sway, bob


def _right(lx, ly):
    return -ly, lx


def _view(client, advance=False):
    """Eye, look, and the local pose. The drawn body can lead the camera."""
    import time
    tiles = client.tiles or []
    pose = _local_draw_args(client, time.time())
    pose["draw_x"] = pose["x"] + 0.5
    pose["draw_y"] = pose["y"] + 0.5
    lx, ly = pose["lx"], pose["ly"]
    rx, ry = _right(lx, ly)
    return tiles, pose, pose["draw_x"], pose["draw_y"], lx, ly, rx, ry


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


def _draw_monster_sprite(client, m, cx, cy, tile_px, t, face, moving, atk, player_sx, drop_down=False, dest=None):
    """The top-down monster chain, drawn at a projected foot point."""
    import procedural_sprites_finished as sprites
    import lowpoly_dragon_sprites
    import anim_strip_sprites
    import legacy_creature_sprites
    from content import MONSTERS
    screen = dest if dest is not None else client.screen
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
    if m.get("type") == "emberdeep_wyrm" and m.get("facing"):
        face = m["facing"]
    import knights_hd_client
    hit_t = t - client.knight_hit_at.get(m["id"], t - 999) if hasattr(client, "knight_hit_at") else -1.0
    if knights_hd_client.draw(
        screen, m["type"], cx, cy, ts, t,
        facing=face, moving=moving, attacking=atk, hurt=hurt,
        hit_t=hit_t if 0 <= hit_t < 0.36 else -1.0,
    ):
        return
    lowpoly = lowpoly_on and lowpoly_dragon_sprites.sheet_key_for_monster_type(m["type"])
    strip = (not lowpoly) and strip_on and anim_strip_sprites.sheet_key_for_monster_type(m["type"])
    atk_arg = atk if (m["id"] in client.attack_anims or str(m["id"]) in client.attack_anims) else -1.0
    if lowpoly and lowpoly_dragon_sprites.draw_lowpoly_dragon(
        screen, vis, cx, cy, ts, t,
        hurt=hurt, attacking=atk_arg, facing=face, moving=moving,
        foe_cx=player_sx, drop_down=drop_down,
    ):
        return
    if strip and anim_strip_sprites.draw_anim_strip_monster(
        screen, vis, cx, cy, ts, t,
        hurt=hurt, attacking=atk_arg, facing=face, moving=moving,
        foe_cx=player_sx, drop_down=drop_down,
    ):
        return
    if emberdeep_creatures_client.draw_creature(
        screen, m["type"], cx, cy, ts, facing=face, breathing=breathing,
        moving=moving, attacking=atk,
    ):
        return
    if moving and m.get("type") in _LEGS:
        step_x, step_y = _stride(_LEGS[m["type"]], t, ts, face)
        cx += step_x
        cy -= step_y
    if m.get("frozen"):
        pygame.draw.circle(screen, (140, 210, 255), (cx, cy), ts // 2 + 4, 2)
    if mdef.get("humanoid"):
        eq = mdef.get("equipment") or {}
        face_h = 1 if client.player["x"] >= m["x"] else -1
        sprites.draw_humanoid_detailed(
            screen, cx, cy, ts,
            (55, 70, 95), (220, 175, 140), (35, 28, 22),
            weapon=_weapon_style(eq.get("weapon")),
            shield=bool(eq.get("shield")),
            moving=moving, t=t, facing=face_h,
            equipment=eq, attacking=atk, gender="male",
        )
    elif feature_flags.USE_NEW_PETS_AND_MONSTERS and legacy_creature_sprites.draw_monster(
        screen, vis, cx, cy, ts, t,
        hurt=hurt, attacking=atk_arg, facing=face, moving=moving,
    ):
        pass
    else:
        sprites.draw_monster(
            screen, vis, cx, cy, ts, t,
            hurt=hurt, attacking=atk, facing=face, moving=moving,
        )
    if dest is None and mdef.get("visual"):
        import void_v2_client
        void_v2_client.tint_and_halo(client, m, cx, cy, ts)


def _label_anchor(cy, tile_px, kind):
    import rs_style
    lift = rs_style.label_lift(tile_px, kind)
    hp_y = cy - lift
    return hp_y - 16, hp_y


def _target_point(client, target):
    """Tile centre to face: the wyrm body tile nearest the player, else the anchor."""
    if target.get("type") == "emberdeep_wyrm":
        import time
        import emberdeep_creatures
        gx, gy, _sliding = _wyrm_glide(client, target, time.time())
        ax, ay = gx - 0.5, gy - 0.5
        p = client.player or {}
        px = float(p.get("x", 0)) + 0.5
        py = float(p.get("y", 0)) + 0.5
        best = None
        best_d = None
        for x, y in emberdeep_creatures.footprint(round(ax), round(ay)):
            cx, cy = x + 0.5, y + 0.5
            dist = (cx - px) ** 2 + (cy - py) ** 2
            if best_d is None or dist < best_d:
                best_d = dist
                best = (cx, cy)
        if best is not None:
            return best
    return (target["x"] + 0.5, target["y"] + 0.5)


def _combat_facing(client, pose, sx, tile_px, player_depth):
    """Side-on to the live target. Attack sheets exist only for the side view."""
    del sx, player_depth
    target = (client.monsters or {}).get(getattr(client, "combat_target_id", None))
    if not target or not target.get("alive", True):
        return pose["face"]
    tx, ty = _target_point(client, target)
    feet_x = pose.get("draw_x", pose["x"] + 0.5)
    feet_y = pose.get("draw_y", pose["y"] + 0.5)
    mw, mh = _map_size()
    hit = _project(0, 0, 0, 0, 0, 0, tx, ty, None, 1, 1, mw, mh)
    feet = _project(0, 0, 0, 0, 0, 0, feet_x, feet_y, None, 1, 1, mw, mh)
    side = getattr(client, "_ember_fight_side", 1)
    if side not in (1, -1):
        side = 1
    if hit is not None and feet is not None:
        dxs = hit[1] - feet[1]
        if abs(dxs) > 0.12 * tile_px:
            side = 1 if dxs > 0 else -1
            client._ember_fight_side = side
    return side


def _wyrm_fight_facing(client, monster):
    """Mouth toward the player when they stand in front of the wyrm."""
    p = client.player or {}
    dx = p.get("x", monster["x"]) - monster["x"]
    dy = p.get("y", monster["y"]) - monster["y"]
    if dy >= 0 and abs(dx) <= max(2, dy):
        return "s"
    if abs(dx) >= abs(dy):
        return "e" if dx >= 0 else "w"
    return "s" if dy >= 0 else ("w" if dx < 0 else "e")


def _draw_local_player(client, pose, sx, sy, tile_px, t, player_depth=1.0):
    import procedural_sprites_finished as sprites
    face = _combat_facing(client, pose, sx, tile_px, player_depth)
    pose["face"] = face
    client._entity_facing[pose["key"]] = face
    p = client.player or {}
    gender = pose["gender"]
    eq = pose["eq"]
    hd_on = p.get("hd_player", True)
    appearance = p.get("appearance") or {
        "skin": "skin_light",
        "hair": "hair_side_part" if gender == "male" else "hair_ponytail",
        "hair_colour": "dark_brown",
        "top": "top_linen_shirt",
        "bottom": "bottom_work_trousers" if gender == "male" else "bottom_long_skirt",
        "shoes": "shoes_leather",
        "outfit": None,
        "accessories": [],
    }
    hit_t = t - client.player_hit_at.get(p.get("id"), t - 999)
    death_t = t - client.player_death_at.get(p.get("id"), t - 999)
    drawn = False
    if hd_on:
        import player_hd_client
        weapon_id = (eq or {}).get("weapon") or ""
        ranged = client.attack_anim_kind.get(p.get("id")) == "ranged" or "bow" in str(weapon_id)
        # Progress is exactly 0 on the first beat, while the swing is still in attack_anims.
        pid = p.get("id")
        in_swing = pose["atk"] > 0 or pid in client.attack_anims or str(pid) in client.attack_anims
        attacking = in_swing and not pose["action"]
        if attacking:
            anim = "ranged" if ranged else "melee"
        else:
            anim = pose["action"] or ("walk" if pose["moving"] else "idle")
        body_px = int(round(tile_px * 1.1))
        # A hit flash must not swap the swing for hit frames. The tint still shows.
        swing_hit = -1.0 if attacking else (hit_t if 0 <= hit_t < 0.36 else -1.0)
        drawn = player_hd_client.draw_player(
            client.screen, gender, appearance, sx, sy, body_px, t,
            anim=anim, progress=pose["atk"] if attacking else None, facing=face,
            hit_t=swing_hit,
            death_t=death_t if 0 <= death_t < 1.2 else -1.0,
            equipment=eq,
        )
        if not drawn:
            drawn = player_hd_client.draw_player(
                client.screen, gender, appearance, sx, sy, min(80, body_px), t,
                anim="idle", facing=face, equipment=eq,
            )
    if hd_on:
        return
    if not drawn:
        sprites.draw_humanoid_detailed(
            client.screen, sx, sy, tile_px,
            (70, 210, 90), (235, 195, 150), (70, 45, 30),
            weapon=_weapon_style(eq.get("weapon")),
            shield=bool(eq.get("shield")),
            moving=pose["moving"], t=t, facing=face,
            equipment=eq, attacking=pose["atk"], action=pose["action"],
            gender=gender,
        )


def _blit_torch(client, sx, sy, tile_px, spot, now):
    strip = _torch_strip()
    tx, ty = spot
    frame = (int(now * 8) + int(tx * 3 + ty * 5)) % 4
    src = strip.subsurface((frame * 96, 0, 96, 160))
    height = max(6, int(tile_px * 0.9))
    width = max(4, int(height * 96 / 160))
    img = pygame.transform.smoothscale(src, (width, height))
    client.screen.blit(img, img.get_rect(center=(int(sx), int(sy))))


_TORCH_STRIP = None


def _torch_strip():
    global _TORCH_STRIP
    if _TORCH_STRIP is None:
        img = pygame.image.load(os.path.join(_TEX_DIR, "torch_sconce_strip.png"))
        if pygame.display.get_surface() is not None:
            img = img.convert_alpha()
        _TORCH_STRIP = img
    return _TORCH_STRIP


def _separate_feet(client, pose, monster, player_depth, player_sx, player_tile):
    """Nudge a drawn body so it does not cover the player. The server tile stays put."""
    wx, wy = _sprite_world(monster)
    px, py = pose["x"] + 0.5, pose["y"] + 0.5
    same = int(monster["x"]) == int(pose["x"]) and int(monster["y"]) == int(pose["y"])
    vx, vy = wx - px, wy - py
    if same or math.hypot(vx, vy) < 0.05:
        cam = _VIEW
        if cam is not None:
            vx, vy = float(cam.r[0]), float(cam.r[1])
        else:
            vx, vy = 1.0, 0.0
    else:
        length = math.hypot(vx, vy) or 1.0
        vx, vy = vx / length, vy / length
    mw, mh = _map_size()
    trial = _project(0, 0, 0, 0, 0, 0, wx, wy, None, 1, 1, mw, mh)
    if trial is None:
        return wx, wy
    depth, sx, _sy, px_per = trial
    body = max(8.0, px_per)
    overlap = min(body, player_tile) and (
        max(0.0, min(sx + body / 2, player_sx + player_tile / 2) - max(sx - body / 2, player_sx - player_tile / 2))
        / min(body, float(player_tile))
    )
    if overlap > 0.35 and abs(depth - player_depth) < 0.6:
        wx += vx * 0.35
        wy += vy * 0.35
    return wx, wy


def _occlude_sprite(client, sx, sy, width, height, depth):
    """Walls nearer than the sprite cover it, using the cached room render."""
    cam = _VIEW
    bg = _FRAME.get("surf")
    render = getattr(client, "_ember_render", None)
    if cam is None or bg is None or not render:
        return
    rw, rh = render
    mw, mh = _map_size()
    rect = pygame.Rect(int(sx - width / 2), int(sy - height), max(1, int(width)), max(1, int(height)))
    rect = rect.clip(pygame.Rect(0, 0, mw, mh))
    if rect.w < 1 or rect.h < 1:
        return
    mask, origin = cam.occluders(
        rect.x * rw / float(mw), rect.y * rh / float(mh),
        rect.right * rw / float(mw), rect.bottom * rh / float(mh),
        depth,
    )
    if mask is None or not getattr(mask, "any", lambda: False)():
        return
    ox, oy = origin
    piece = bg.subsurface((ox, oy, int(mask.shape[1]), int(mask.shape[0]))).convert_alpha()
    alpha = pygame.surfarray.pixels_alpha(piece)
    alpha[:, :] = (mask.swapaxes(0, 1) * 255).astype("uint8")
    del alpha
    if piece.get_size() != rect.size:
        piece = pygame.transform.scale(piece, rect.size)
    client.screen.blit(piece, rect.topleft)


def _draw_billboards(client, pose, ex, ey, lx, ly, rx, ry, depths, rw, rh, mw, mh):
    import time
    t = time.time()
    bills = []
    client._ember_screen_anchor = {}
    player_sx = mw // 2
    bx = pose.get("draw_x", pose["x"] + 0.5)
    by = pose.get("draw_y", pose["y"] + 0.5)
    projected = _project(ex, ey, lx, ly, rx, ry, bx, by, None, rw, rh, mw, mh)
    if projected is None:
        projected = (1.0, mw // 2, int(mh * 0.72), max(32, mh // 12))
    along_p, psx, psy, ptile = projected
    player_sx = psx
    player_sy = psy
    player_tile = max(24, int(ptile))
    bills.append((max(0.2, along_p), "player", psx, player_sy, player_tile, None))
    seen = {pose["key"]: (pose["x"], pose["y"])}
    for m in (client.monsters or {}).values():
        if not m.get("alive", True):
            continue
        _face, moving, atk, near, drop_down = _monster_pose(client, m, t)
        seen[("m", m["id"])] = (m["x"], m["y"])
        targeted = client.combat_target_id == m["id"]
        wx, wy = _separate_feet(client, pose, m, along_p, psx, player_tile)
        if m.get("type") == "emberdeep_wyrm":
            wx, wy, gliding = _wyrm_glide(client, m, t)
            if gliding:
                moving = True
        import ember_combat_fx
        _hx, _hy, flash = ember_combat_fx.hit_pose(client, m, t)
        squash = 1.0
        if m.get("type") != "emberdeep_wyrm":
            ax, ay, squash = ember_combat_fx.attack_pose(client, m, t)
            wx, wy = wx + ax + _hx, wy + ay + _hy
        proj = _project(ex, ey, lx, ly, rx, ry, wx, wy, depths, rw, rh, mw, mh)
        if proj is None:
            continue
        along, sx, sy, tile_px = proj
        face = _face_from_vector(pose["x"] - m["x"], pose["y"] - m["y"])
        bills.append((along, "monster", sx, sy, tile_px * squash, (m, face, moving, atk, near or targeted, drop_down, flash)))
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
            bills.append((along, "pack_prop", sx, sy, tile_px, key))
    for tx, ty, _nx, _ny in (_VIEW.torches if _VIEW is not None else []):
        hit = _project(ex, ey, lx, ly, rx, ry, tx, ty, None, rw, rh, mw, mh)
        if hit is None:
            continue
        along, sx, sy, tile_px = hit
        # The sconce face sits up the wall. Re-project that height for the screen point.
        cam = _VIEW
        high = cam.project(tx, ty, 1.25) if cam is not None else None
        if high is not None:
            last_w, last_h = cam._last[0], cam._last[1]
            along, sx, sy = high[0], high[1] * mw / last_w, high[2] * mh / last_h
        bills.append((along, "torch", sx, sy, tile_px, (tx, ty)))
    bills.sort(key=lambda item: -item[0])
    client._ember_sprite_hits = []
    shx, shy = getattr(client, "_ember_shake_px", (0, 0))
    player_bill = None
    for along, kind, sx, sy, tile_px, extra in bills:
        sx += shx
        sy += shy
        if kind == "player":
            player_bill = (along, sx, sy, tile_px)
            continue
        if kind == "pack_prop":
            import emberdeep_creatures_client
            emberdeep_creatures_client.draw_prop(client.screen, extra, sx, sy, tile_px)
            _occlude_sprite(client, sx, sy, tile_px, tile_px, along)
            continue
        if kind == "torch":
            _blit_torch(client, sx, sy, tile_px, extra, t)
            _occlude_sprite(client, sx, sy, tile_px * 0.6, tile_px * 0.9, along)
            continue
        m, face, moving, atk, show, drop_down, flash = extra
        import emberdeep_creatures_client
        import ember_combat_fx
        if m.get("type") == "emberdeep_wyrm":
            _draw_wyrm_billboard(
                client, m, sx, sy, tile_px, t, moving, atk, flash, along, show, mh,
                (player_sx + shx, player_sy + shy, player_tile),
            )
            continue
        height = emberdeep_creatures_client.creature_height(m["type"], tile_px)
        if flash > 0.01:
            pad = int(height * 1.4)
            temp = pygame.Surface((pad, pad), pygame.SRCALPHA)
            _draw_monster_sprite(
                client, m, pad // 2, pad - 4, tile_px, t, face, moving, atk, player_sx, drop_down, dest=temp,
            )
            temp = ember_combat_fx.flash_surface(temp, flash)
            client.screen.blit(temp, (int(sx - pad // 2), int(sy - (pad - 4))))
        else:
            _draw_monster_sprite(client, m, sx, sy, tile_px, t, face, moving, atk, player_sx, drop_down)
        if ember_combat_fx.contact(client, m, t) and client.player:
            mid = _project(
                ex, ey, lx, ly, rx, ry,
                (m["x"] + client.player["x"]) / 2 + 0.5,
                (m["y"] + client.player["y"]) / 2 + 0.5,
                None, rw, rh, mw, mh,
            )
            if mid:
                pygame.draw.circle(client.screen, (255, 210, 120), (int(mid[1]), int(mid[2])), 7)
                pygame.draw.circle(client.screen, (255, 120, 40), (int(mid[1]), int(mid[2])), 3)
        _occlude_sprite(client, sx, sy, height, height, along)
        hit = pygame.Rect(int(sx - height / 2), int(sy - height), int(height), int(height))
        client._ember_sprite_hits.append((hit, (int(m["x"]), int(m["y"]))))
        anchors = getattr(client, "_ember_screen_anchor", None)
        if isinstance(anchors, dict):
            anchors[("m", m["id"])] = (sx, sy, height)
            anchors[("m", str(m["id"]))] = (sx, sy, height)
        bar_y = max(22, min(mh - 28, sy - height - 6))
        client.draw_hp_bar(sx, bar_y, m["hp"], m["max_hp"])
        if show:
            client.blit_nameplate(m["name"], sx, bar_y - 14)
            level = int(m.get("level") or 1)
            client.blit_combat_level(level, sx, bar_y - 28, client.monster_threat_color(level))
    _draw_ember_corpses(client, t, rw, rh, mw, mh)
    _draw_wyrm_death(client, t, rw, rh, mw, mh)
    _draw_breath(client, t, rw, rh, mw, mh)
    if player_bill is not None:
        _along, sx, sy, tile_px = player_bill
        _draw_local_player(client, pose, sx, sy, tile_px, t, _along)
        anchors = getattr(client, "_ember_screen_anchor", None)
        if not isinstance(anchors, dict):
            anchors = {}
            client._ember_screen_anchor = anchors
        pid = pose.get("key", (None, None))[1]
        anchors[("p", pid)] = (sx, sy, tile_px)
        anchors[("p", str(pid))] = (sx, sy, tile_px)
        p = client.player or {}
        client.draw_hp_bar(sx, sy - tile_px - 8, p.get("hp", 1), p.get("max_hp", 1), show_value=True)
    _draw_projectiles(client, ex, ey, lx, ly, rx, ry, rw, rh, mw, mh)
    _draw_hitsplats(client, ex, ey, lx, ly, rx, ry, depths, rw, rh, mw, mh)
    prev = dict(getattr(client, "_prev_entity_pos", {}) or {})
    prev.update(seen)
    client._prev_entity_pos = prev
    _draw_corner_map(client, lx, ly)
    return True


def _wyrm_bar_y(bar_y, sx, player_sx, player_sy, player_tile, show):
    """Move the wyrm label up when it would cover the player's head."""
    if player_tile <= 0:
        return bar_y
    head = pygame.Rect(
        int(player_sx - player_tile * 0.6),
        int(player_sy - player_tile * 2.2),
        max(1, int(player_tile * 1.2)),
        max(1, int(player_tile * 0.8)),
    )
    top = bar_y - (28 if show else 0)
    label = pygame.Rect(int(sx - 22), int(top), 44, max(1, int(bar_y + 6 - top)))
    if not label.colliderect(head):
        return bar_y
    overlap = label.bottom - head.top
    if overlap <= 0:
        return bar_y
    return bar_y - overlap


def _draw_wyrm_billboard(client, monster, sx, sy, tile_px, now, moving, atk, flash, depth, show, mh, player_screen=None):
    """Rendered wyrm frames. The lunge lives in the art, so only the hit flash is added."""
    import emberdeep_creatures_client
    import ember_combat_fx
    cone = getattr(client, "ember_cone", None) or {}
    breath_t0 = cone.get("t0")
    hit_at = (getattr(client, "monster_hit_at", None) or {}).get(monster["id"])
    facing = monster.get("facing") or "s"
    if breath_t0 is not None or client.combat_target_id == monster.get("id"):
        facing = _wyrm_fight_facing(client, monster)
    if flash > 0.01:
        width, height, feet_x, feet_y = emberdeep_creatures_client.wyrm_canvas(tile_px)
        temp = pygame.Surface((width, height), pygame.SRCALPHA)
        emberdeep_creatures_client.draw_wyrm(
            temp, feet_x, feet_y, tile_px, facing, now,
            moving=moving, attack_p=atk, breath_t0=breath_t0, hit_at=hit_at,
        )
        temp = ember_combat_fx.flash_surface(temp, flash)
        rect = temp.get_rect(topleft=(int(sx - feet_x), int(sy - feet_y)))
        client.screen.blit(temp, rect)
    else:
        rect = emberdeep_creatures_client.draw_wyrm(
            client.screen, sx, sy, tile_px, facing, now,
            moving=moving, attack_p=atk, breath_t0=breath_t0, hit_at=hit_at,
        )
    if rect is None:
        return
    _occlude_sprite(client, rect.centerx, rect.bottom, rect.w, rect.h, depth)
    client._ember_sprite_hits.append((rect, (int(monster["x"]), int(monster["y"]))))
    label = tile_px * 3.0
    anchors = getattr(client, "_ember_screen_anchor", None)
    if isinstance(anchors, dict):
        anchors[("m", monster["id"])] = (sx, sy, label)
        anchors[("m", str(monster["id"]))] = (sx, sy, label)
    bar_y = max(22, min(mh - 28, sy - label - 6))
    if player_screen is not None:
        bar_y = _wyrm_bar_y(bar_y, sx, player_screen[0], player_screen[1], player_screen[2], show)
    client.draw_hp_bar(sx, bar_y, monster["hp"], monster["max_hp"])
    if show:
        client.blit_nameplate(monster["name"], sx, bar_y - 14)
        level = int(monster.get("level") or 1)
        client.blit_combat_level(level, sx, bar_y - 28, client.monster_threat_color(level))


def _draw_wyrm_death(client, now, rw, rh, mw, mh):
    import emberdeep_creatures_client
    death = getattr(client, "wyrm_death", None)
    if not death:
        return
    if now - death["t0"] >= 4.0:
        client.wyrm_death = None
        return
    hit = _project(0, 0, 0, 0, 0, 0, death["x"] + 0.5, death["y"] + 0.5, None, rw, rh, mw, mh)
    if hit is None:
        return
    depth, sx, sy, tile_px = hit
    rect = emberdeep_creatures_client.draw_wyrm(
        client.screen, sx, sy, tile_px, death.get("facing") or "s", now, death_t0=death["t0"],
    )
    if rect is not None:
        _occlude_sprite(client, rect.centerx, rect.bottom, rect.w, rect.h, depth)


def _draw_ember_corpses(client, now, rw, rh, mw, mh):
    import ember_combat_fx
    import emberdeep_creatures_client
    keep = []
    px = (client.player or {}).get("x", 0)
    for corpse in getattr(client, "ember_corpses", None) or []:
        age = now - corpse.get("t0", now)
        if age > 1.0:
            continue
        keep.append(corpse)
        hit = _project(0, 0, 0, 0, 0, 0, corpse["x"] + 0.5, corpse["y"] + 0.5 + 0.2 * age, None, rw, rh, mw, mh)
        if hit is None:
            continue
        _depth, sx, sy, tile_px = hit
        height = emberdeep_creatures_client.creature_height(corpse.get("type"), tile_px)
        pad = max(8, int(height * 1.6))
        temp = pygame.Surface((pad, pad), pygame.SRCALPHA)
        emberdeep_creatures_client.draw_creature(
            temp, corpse.get("type"), pad // 2, pad - 4, tile_px, facing=corpse.get("face", "front"),
        )
        sign = -1 if corpse["x"] >= px else 1
        spun = pygame.transform.rotate(temp, sign * 80 * age)
        if age > 0.5:
            spun.set_alpha(int(255 * (1.0 - (age - 0.5) / 0.5)))
        rect = spun.get_rect(center=(int(sx), int(sy)))
        client.screen.blit(spun, rect)
        ember_combat_fx.draw_embers(client.screen, sx, sy - height * 0.4, age)
    client.ember_corpses = keep


def _draw_breath(client, now, rw, rh, mw, mh):
    cone = getattr(client, "ember_cone", None) or {}
    t0 = cone.get("t0")
    if t0 is None:
        return
    frame = int((now - t0) / 0.15)
    if frame < 0 or frame > 7:
        return
    spots = []
    for spot in cone.get("tiles") or []:
        if isinstance(spot, dict):
            spots.append((int(spot["x"]), int(spot["y"])))
        elif spot:
            spots.append((int(spot[0]), int(spot[1])))
    if not spots:
        return
    released = frame >= 4
    points = []
    for x, y in spots:
        hit = _project(0, 0, 0, 0, 0, 0, x + 0.5, y + 0.5, None, rw, rh, mw, mh)
        if hit is None:
            continue
        points.append(hit)
        if released:
            flick = 0.55 + 0.35 * abs(math.sin(now * 11 + x * 3 + y))
            color = (255, int(80 + 40 * flick), 24)
            radius = max(3, int(hit[3] * 0.28 * flick))
        else:
            color = (120, 24, 18)
            radius = max(2, int(hit[3] * 0.16))
        pygame.draw.circle(client.screen, color, (int(hit[1]), int(hit[2])), radius)
    if not released or not points:
        return
    import ember_combat_fx
    image = ember_combat_fx._cone_image()
    if image is None:
        return
    wyrm = None
    for monster in (client.monsters or {}).values():
        if monster.get("type") == "emberdeep_wyrm":
            wyrm = monster
    p = client.player or {}
    src = dst = None
    if wyrm and p:
        src = _project(0, 0, 0, 0, 0, 0, wyrm["x"] + 0.5, wyrm["y"] + 0.5, None, rw, rh, mw, mh)
        dst = _project(0, 0, 0, 0, 0, 0, p.get("x", 0) + 0.5, p.get("y", 0) + 0.5, None, rw, rh, mw, mh)
    if src and dst:
        vx, vy = dst[1] - src[1], dst[2] - src[2]
        dist = math.hypot(vx, vy) or 1.0
        # The cone art points east. Positive pygame rotation is counter-clockwise,
        # and screen y grows downward, so negate the screen angle.
        angle = -math.degrees(math.atan2(vy, vx))
        length = max(24, int(dist))
        thick = max(18, int((src[3] + dst[3]) * 0.55))
        scaled = pygame.transform.smoothscale(image, (length, thick))
        spun = pygame.transform.rotate(scaled, angle)
        spun.set_alpha(150)
        rect = spun.get_rect(center=(int(src[1] + vx * 0.55), int(src[2] + vy * 0.55)))
        client.screen.blit(spun, rect.topleft)
        return
    facing = _wyrm_fight_facing(client, wyrm) if wyrm else "s"
    # Art points east. South, toward the player in front, is a quarter turn clockwise.
    angle = {"e": 0, "w": 180, "n": 90, "s": -90}.get(facing, -90)
    spun = pygame.transform.rotate(image, angle)
    xs = [pt[1] for pt in points]
    ys = [pt[2] for pt in points]
    span = max(points[0][3] * 2, 24)
    size = (max(24, int(max(xs) - min(xs) + span)), max(24, int(max(ys) - min(ys) + span)))
    spun = pygame.transform.smoothscale(spun, size)
    spun.set_alpha(150)
    client.screen.blit(spun, (int(sum(xs) / len(xs) - size[0] / 2), int(sum(ys) / len(ys) - size[1] / 2)))


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
    tiles, pose, ex, ey, lx, ly, rx, ry = _view(client, advance=True)
    if not tiles:
        return False
    view = _ensure_view(client)
    if view is None:
        return False
    now = time.time()
    fx, fy, yaw, zoom, dt = _ease_follow(client, pose, now)
    view.set_camera(fx, fy, yaw, zoom)
    view.ease(dt)
    mw, mh = _map_size()
    surf, rw, rh = _render_cached(view, mw, mh, now, fx, fy, yaw, zoom)
    import ember_combat_fx
    ox, oy = ember_combat_fx.shake_offset(client, now)
    client._ember_shake_px = (ox, oy)
    scaled = pygame.transform.smoothscale(surf, (mw, mh))
    client.screen.blit(scaled, (ox, oy))
    client._ember_render = (rw, rh)
    px, py = int(pose["x"]), int(pose["y"])
    _draw_tile_highlight(client.screen, ex, ey, lx, ly, rx, ry, px, py, rw, rh, mw, mh, (180, 200, 120), 2)
    if abs(lx) >= abs(ly):
        next_dx, next_dy = (1 if lx > 0 else -1), 0
    else:
        next_dx, next_dy = 0, (1 if ly > 0 else -1)
    next_x, next_y = px + next_dx, py + next_dy
    if _tile_at(tiles, next_x, next_y) == wm.FLOOR:
        _draw_tile_highlight(
            client.screen, ex, ey, lx, ly, rx, ry, next_x, next_y, rw, rh, mw, mh, (150, 170, 100), 1,
        )
    _draw_billboards(client, pose, ex, ey, lx, ly, rx, ry, None, rw, rh, mw, mh)
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
    mw, mh = _map_size()
    if mx < 0 or my < 0 or mx >= mw or my >= mh:
        return None
    box = getattr(client, "_ember_map_rect", None)
    if box is not None and box.collidepoint(mx, my):
        return int(client.player["x"]), int(client.player["y"])
    for rect, tile in getattr(client, "_ember_sprite_hits", None) or []:
        if rect.collidepoint(mx, my):
            return tile
    tiles, _pose, ex, ey, lx, ly, rx, ry = _view(client)
    if not tiles:
        return None
    rw, rh = (getattr(client, "_ember_render", None) or (max(160, mw // 2), max(120, mh // 2)))
    best = None
    best_d = 1e9
    for mon in (client.monsters or {}).values():
        if not mon.get("alive", True):
            continue
        wx, wy = _sprite_world(mon)
        proj = _project(ex, ey, lx, ly, rx, ry, wx, wy, None, rw, rh, mw, mh)
        if proj is None:
            continue
        along, sx, sy, tile_px = proj
        import emberdeep_creatures_client
        height = emberdeep_creatures_client.creature_height(mon["type"], tile_px)
        hit = pygame.Rect(sx - height / 2, sy - height, height, height).collidepoint(mx, my)
        if hit and along < best_d:
            best = (int(mon["x"]), int(mon["y"]))
            best_d = along
    if best:
        return best
    cam = _VIEW
    rw, rh = (getattr(client, "_ember_render", None) or (mw, mh))[:2]
    if cam is None or not hasattr(cam, "_last"):
        return int(client.player["x"]), int(client.player["y"])
    return cam.pick(mx * rw / float(mw), my * rh / float(mh))
