"""Pre-rendered unique house layers. One building at a time."""
import os
import time

import pygame

import buildings_v2
import feature_flags

_DIR = os.path.join(os.path.dirname(__file__), "assets", "buildings", "v2")
_cache = {}


def ready(building_id):
    info = buildings_v2.meta(building_id) if buildings_v2.enabled(building_id) else None
    if not info:
        return False
    rel = info["layers"][0]["file"]
    return os.path.isfile(os.path.join(_DIR, "1x", rel))


def _bucket(tile):
    return ("2x", 80) if tile > 40 else ("1x", 40)


def _pattern_floor_fill(img, scale):
    """Boards or flagstones on the big flat interior fill. Doors and trim stay put."""
    w, h = img.get_size()
    data = bytearray(pygame.image.tobytes(img, "RGBA"))
    buckets = {}
    step = 3
    for y in range(0, h, step):
        row = y * w * 4
        for x in range(0, w, step):
            i = row + x * 4
            if data[i + 3] < 200:
                continue
            key = (data[i] // 16 * 16, data[i + 1] // 16 * 16, data[i + 2] // 16 * 16)
            buckets[key] = buckets.get(key, 0) + 1
    if not buckets:
        return img
    total = sum(buckets.values())
    floor_keys = [k for k, n in buckets.items() if n >= total * 0.08]
    if not floor_keys:
        floor_keys = [max(buckets, key=buckets.get)]
    pitch = 14 * scale
    cell_w = 34 * scale
    cell_h = 22 * scale
    span = 78 * scale

    def is_floor(r, g, b):
        for kr, kg, kb in floor_keys:
            if abs(r - kr) <= 22 and abs(g - kg) <= 22 and abs(b - kb) <= 22:
                return True
        return False

    def stone_pixel(r, g, b):
        return max(r, g, b) - min(r, g, b) < 28

    def clamp(v):
        return 0 if v < 0 else 255 if v > 255 else v

    for y in range(h):
        row = y * w * 4
        band = y // pitch
        seam = (y % pitch) < max(1, scale)
        for x in range(w):
            i = row + x * 4
            if data[i + 3] < 200:
                continue
            r, g, b = data[i], data[i + 1], data[i + 2]
            if not is_floor(r, g, b):
                continue
            if stone_pixel(r, g, b):
                grout = (x % cell_w) < max(1, scale) or (y % cell_h) < max(1, scale)
                if grout:
                    delta = -28
                elif ((x // cell_w) + (y // cell_h)) % 2 == 0:
                    delta = 10
                else:
                    delta = -6
            else:
                joint = (x % span) == ((band * 37) % span)
                if seam or joint:
                    delta = -36
                elif band % 2:
                    delta = 14
                else:
                    delta = -10
            data[i] = clamp(r + delta)
            data[i + 1] = clamp(g + delta)
            data[i + 2] = clamp(b + delta)
    out = pygame.image.frombytes(bytes(data), (w, h), "RGBA")
    return out.convert_alpha()


def _surface(rel, tile):
    key = (rel, int(tile))
    if key in _cache:
        return _cache[key]
    bucket, base = _bucket(tile)
    path = os.path.join(_DIR, bucket, rel)
    if not os.path.isfile(path):
        _cache[key] = None
        return None
    img = pygame.image.load(path).convert_alpha()
    # The smithy art already has its yard and forge floor. Don't restamp it.
    if (rel.endswith("ground.png") or rel.endswith("cutaway.png")) and not rel.startswith("smithy/"):
        img = _pattern_floor_fill(img, 2 if bucket == "2x" else 1)
    tw = max(1, int(round(img.get_width() * tile / base)))
    th = max(1, int(round(img.get_height() * tile / base)))
    if (tw, th) != img.get_size():
        img = pygame.transform.smoothscale(img, (tw, th))
    _cache[key] = img
    return img


def _origin(building_id, tile_nw_x, tile_nw_y, tile):
    info = buildings_v2.meta(building_id)
    if tile > 40:
        ox, oy = info["sprite_2x"]["origin_px"]
        base = 80
    else:
        ox, oy = info["sprite_1x"]["origin_px"]
        base = 40
    scale = tile / float(base)
    return tile_nw_x - ox * scale, tile_nw_y - oy * scale


def _layer_file(building_id, name):
    info = buildings_v2.meta(building_id)
    for layer in info["layers"]:
        if layer["name"] == name:
            return layer["file"]
    return None


def _fx_file(building_id, kind, now):
    info = buildings_v2.meta(building_id) or {}
    fx = (info.get("fx") or {}).get(kind)
    if not fx:
        return None
    seq = fx["sequence"]
    idx = seq[int(now * float(fx["fps"])) % len(seq)]
    return fx["files"][idx]


def queue(client, draw_list, cam_x, cam_y, tile):
    if not client.buildings:
        return
    px = py = None
    if client.player:
        px, py = client.player_xy()
    for b in client.buildings:
        bid = b.get("id")
        if not ready(bid):
            continue
        if bid == "smithy" and int(getattr(client, "camera_yaw", 0)) % 4 != 0:
            continue
        x0, y0, x1, y1 = buildings_v2.footprint(bid)
        sx, sy = client.world_to_view_offset(x0, y0, cam_x, cam_y)
        ox, oy = _origin(bid, sx * tile, sy * tile, tile)
        inside = px is not None and client.player_inside_building(b)
        screen = client.screen
        ground = _layer_file(bid, "ground")
        body = _layer_file(bid, "cutaway" if inside else "body")
        smoke = None
        if bid == "smithy" and not inside and feature_flags.SMITHY_FX:
            now = time.time()
            body = _fx_file(bid, "glow", now) or body
            smoke = _fx_file(bid, "smoke", now)
        name = b.get("name") or ""

        def blit(rel, _ox=ox, _oy=oy, _tile=tile):
            img = _surface(rel, _tile)
            if img is not None:
                screen.blit(img, (_ox, _oy))

        def row_bottom(wy, _x0=x0):
            _sx, vsy = client.world_to_view_offset(_x0, wy, cam_x, cam_y)
            return vsy * tile + tile

        # Bind draw now. A bare blit lookup would use the last house in the loop.
        draw_list.append((-10 ** 9, 0, lambda rel=ground, draw=blit: draw(rel)))
        # Outside, the shell sorts at the door so it covers the room.
        # Inside, the cutaway is behind every person and prop in the room.
        sort_y = -(10 ** 8) if inside else row_bottom(y1)
        draw_list.append((sort_y, 0, lambda rel=body, draw=blit: draw(rel)))
        if smoke:
            draw_list.append((sort_y, 1, lambda rel=smoke, draw=blit: draw(rel)))
        if name and not inside and bid == "smithy":
            _sx, plaque_sy = client.world_to_view_offset(x0, y1 - 7, cam_x, cam_y)
            plaque_y = plaque_sy * tile

            def _plaque(_ox=ox, _name=name, _w=(x1 - x0 + 1) * tile, _y=plaque_y):
                text = client.font_small.render(_name, True, (255, 230, 180))
                screen.blit(text, (_ox + _w * 0.5 - text.get_width() / 2, _y))
            draw_list.append((sort_y, 4, _plaque))
        elif name and not inside:
            def _label(_ox=ox, _oy=oy, _name=name, _w=(x1 - x0 + 1) * tile):
                text = client.font_small.render(_name, True, (255, 230, 180))
                screen.blit(text, (_ox + _w * 0.5 - text.get_width() / 2, _oy + 8))
            draw_list.append((sort_y, 4, _label))
