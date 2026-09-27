"""Pre-rendered Stonehaven castle layers and the client-only gate animation."""
import os
import time

import pygame

import castle_v2

_DIR = os.path.join(os.path.dirname(__file__), "assets", "buildings", "castle_v2")
_cache = {}
_gate = {"frame": 0, "acc": 0.0, "dir": 0, "off_ms": None, "last": None}


def ready():
    return castle_v2.active() and os.path.isfile(
        os.path.join(_DIR, "1x", "castle_ground.png")
    )


def _bucket(tile):
    return ("2x", 80) if tile > 40 else ("1x", 40)


def _surface(name, tile):
    key = (name, int(tile))
    if key in _cache:
        return _cache[key]
    bucket, base = _bucket(tile)
    path = os.path.join(_DIR, bucket, name)
    if not os.path.isfile(path):
        _cache[key] = None
        return None
    img = pygame.image.load(path).convert_alpha()
    tw = max(1, int(round(img.get_width() * tile / base)))
    th = max(1, int(round(img.get_height() * tile / base)))
    if (tw, th) != img.get_size():
        img = pygame.transform.smoothscale(img, (tw, th))
    _cache[key] = img
    return img


def _origin(tile_nw_x, tile_nw_y, tile):
    info = castle_v2.meta()
    if tile > 40:
        ox, oy = info["sprite_2x"]["origin_px"]
        base = 80
    else:
        ox, oy = info["sprite_1x"]["origin_px"]
        base = 40
    s = tile / float(base)
    return tile_nw_x - ox * s, tile_nw_y - oy * s


def _gate_offset(tile):
    info = castle_v2.meta()
    layer = next(item for item in info["layers"] if item["name"] == "gate")
    if tile > 40:
        crop = layer["crop_2x"]
        base = 80
    else:
        crop = layer["crop_1x"]
        base = 40
    s = tile / float(base)
    return crop[0] * s, crop[1] * s


def lift_px(x, y, tile):
    if (int(x), int(y)) in castle_v2.wall_walk_tiles():
        return int(round(118 * tile / 40.0))
    return 0


def _player_inside(client, px, py):
    for b in client.buildings or []:
        if b.get("id") != "stonehaven_castle":
            continue
        if (
            b["floor_x0"] <= px <= b["floor_x1"]
            and b["floor_y0"] <= py <= b["floor_y1"]
        ):
            return True
    for spot in client.interactables or []:
        if spot.get("kind") != "door":
            continue
        if "castle_gate" not in (spot.get("id") or ""):
            continue
        if px == spot["x"] and py == spot["y"]:
            return True
    return False


def update(px, py):
    """Advance the drawbridge / portcullis. Local player only."""
    g = _gate
    now = time.time() * 1000.0
    if g["last"] is None:
        g["last"] = now
    dt = max(0.0, min(80.0, now - g["last"]))
    g["last"] = now
    frames = castle_v2.meta()["gate"]["frames"]
    delay = float(castle_v2.meta()["gate"]["close_delay_ms"])
    triggered = px is not None and (int(px), int(py)) in castle_v2.trigger_tiles()
    if triggered:
        g["off_ms"] = None
        g["dir"] = 1 if g["frame"] < 11 else 0
    else:
        if g["off_ms"] is None:
            g["off_ms"] = 0.0
        else:
            g["off_ms"] += dt
        if g["off_ms"] >= delay and g["frame"] > 0:
            g["dir"] = -1
        else:
            g["dir"] = 0
    if g["dir"] == 0:
        return g["frame"]
    g["acc"] += dt
    while g["dir"]:
        dur = float(frames[g["frame"]]["ms"])
        if g["acc"] < dur:
            break
        g["acc"] -= dur
        nxt = g["frame"] + g["dir"]
        if nxt < 0 or nxt > 11:
            g["frame"] = 0 if nxt < 0 else 11
            g["dir"] = 0
            g["acc"] = 0.0
            break
        g["frame"] = nxt
    return g["frame"]


def queue(client, draw_list, cam_x, cam_y, tile):
    if not ready():
        return
    x0, y0, x1, y1 = castle_v2.footprint_tiles()
    sx, sy = client.world_to_view_offset(x0, y0, cam_x, cam_y)
    ox, oy = _origin(sx * tile, sy * tile, tile)
    px = py = None
    if client.player:
        px, py = client.player_xy()
    inside = _player_inside(client, px, py) if px is not None else False
    frame = update(px, py)
    gx, gy = _gate_offset(tile)
    screen = client.screen

    def blit(name, extra=None, _ox=ox, _oy=oy):
        img = _surface(name, tile)
        if img is None:
            return
        if extra is None:
            screen.blit(img, (_ox, _oy))
        else:
            screen.blit(img, (_ox + extra[0], _oy + extra[1]))

    def row_bottom(wy, _x0=x0):
        _sx, vsy = client.world_to_view_offset(_x0, wy, cam_x, cam_y)
        return vsy * tile + tile

    draw_list.append((-10 ** 9, 0, lambda: blit("castle_ground.png")))
    back_sort = row_bottom(y0 - 1)
    if inside:
        draw_list.append((back_sort, 40, lambda: blit("castle_cutaway.png")))
    else:
        draw_list.append((back_sort, 40, lambda: blit("castle_back.png")))
    gate_name = f"gate/gate_{frame:02d}.png"
    draw_list.append((back_sort, 41, lambda name=gate_name: blit(name, (gx, gy))))
    draw_list.append((row_bottom(y1), 30, lambda: blit("castle_posts.png")))
    if not inside:
        draw_list.append((10 ** 9, 0, lambda: blit("castle_front.png")))
        draw_list.append((10 ** 9, 1, lambda: _label()))

    def _label():
        text = client.font_small.render("Castle Keep", True, (255, 230, 180))
        screen.blit(text, (ox + (x1 - x0 + 1) * tile * 0.5 - text.get_width() / 2, oy + 6))
