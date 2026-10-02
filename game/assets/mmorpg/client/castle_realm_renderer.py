"""Client renderer for the flag-gated Castle Realm."""
from __future__ import annotations

import json
import time
from pathlib import Path

import pygame

import world_map as wm
import procedural_sprites_finished as sprites

_HERE = Path(__file__).resolve().parent
_ROOT = _HERE / "assets" / "castle_realm"
_CACHE = {}
_GATES = {}


def _json(path):
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


def _load_built():
    castles = {}
    floors = {}
    realm = _json(_ROOT / "json" / "castle_realm_map.json")
    for entry in realm.get("castles", []):
        if entry.get("status") != "built":
            continue
        path = _ROOT / "json" / entry.get("data", "")
        if not path.is_file():
            continue
        blob = _json(path)
        root = _ROOT / entry["id"]
        blob["_root"] = root
        castles[entry["id"]] = blob
        for floor in blob.get("floors", []):
            floor["_root"] = root
            floors[floor["plane"]] = floor
    return realm, castles, floors


REALM, CASTLE_DATA, FLOORS = _load_built()
REALM_ROWS = REALM.get("rows", [])
GOTHIC = CASTLE_DATA.get("gothic", {})


def ready():
    return any(_castle_ready(blob) for blob in CASTLE_DATA.values())


def _castle_ready(blob):
    root = blob.get("_root")
    return bool(root) and all((root / layer["file"]).is_file() for layer in blob.get("layers", []))


def _realm(client):
    return bool(client.dungeon and client.dungeon.get("id") == "castle_realm" and client.dungeon.get("plane") == "realm")


def _interior(client):
    return bool(client.dungeon and client.dungeon.get("id") == "castle_realm" and client.dungeon.get("plane") in FLOORS)


def _plane(client):
    return (client.dungeon or {}).get("plane", "realm")


def _surface(root, relative, tile):
    base = 80 if "/2x/" in str(relative) else 40
    key = (str(root), relative, int(tile))
    if key in _CACHE:
        return _CACHE[key]
    path = root / relative
    if not path.is_file() and "/2x/" in str(relative):
        path = root / str(relative).replace("/2x/", "/1x/")
        base = 40
    if not path.is_file():
        _CACHE[key] = None
        return None
    image = pygame.image.load(str(path)).convert_alpha()
    image = pygame.transform.smoothscale(image, (max(1, round(image.get_width() * tile / base)), max(1, round(image.get_height() * tile / base))))
    _CACHE[key] = image
    return image


def _gate_state(castle_id):
    return _GATES.setdefault(castle_id, {"frame": 0, "acc": 0.0, "dir": 0, "off_ms": None, "last": None})


def _gate_tiles(blob):
    result = set()
    for group in blob.get("trigger_tiles", {}).values():
        if isinstance(group, list):
            result.update((int(x), int(y)) for x, y in group)
    return result


def _gate_frame(castle_id, blob, px, py):
    state = _gate_state(castle_id)
    now = time.time() * 1000.0
    if state["last"] is None:
        state["last"] = now
    dt = max(0.0, min(80.0, now - state["last"]))
    state["last"] = now
    frames = blob.get("gate", {}).get("frames", [])
    if not frames:
        return 0
    delay = float(blob.get("gate", {}).get("close_delay_ms", 450))
    if (int(px), int(py)) in _gate_tiles(blob):
        state["off_ms"] = None
        state["dir"] = 1 if state["frame"] < len(frames) - 1 else 0
    else:
        state["off_ms"] = 0.0 if state["off_ms"] is None else state["off_ms"] + dt
        state["dir"] = -1 if state["off_ms"] >= delay and state["frame"] else 0
    if not state["dir"]:
        return state["frame"]
    state["acc"] += dt
    while state["dir"]:
        duration = float(frames[state["frame"]].get("ms", 80))
        if state["acc"] < duration:
            break
        state["acc"] -= duration
        nxt = state["frame"] + state["dir"]
        if nxt < 0 or nxt >= len(frames):
            state["frame"] = 0 if nxt < 0 else len(frames) - 1
            state["dir"] = 0
            break
        state["frame"] = nxt
    return state["frame"]


def _anim_frame(frames):
    """Loop an ambient frame list by each frame's ms value."""
    if not frames:
        return 0
    durations = [float(frame.get("ms", 110)) for frame in frames]
    total = sum(durations)
    if total <= 0:
        return 0
    cursor = (time.time() * 1000.0) % total
    acc = 0.0
    for index, duration in enumerate(durations):
        acc += duration
        if cursor < acc:
            return index
    return len(frames) - 1


def _inside_keep(blob, px, py):
    fp = blob.get("footprint") or {}
    rect = blob.get("keep_rect_local")
    if rect:
        x0 = int(fp.get("x0", 0)) + int(rect[0])
        y0 = int(fp.get("y0", 0)) + int(rect[1])
        x1 = int(fp.get("x0", 0)) + int(rect[2])
        y1 = int(fp.get("y0", 0)) + int(rect[3])
    else:
        x0, y0 = int(fp.get("x0", 0)), int(fp.get("y0", 0))
        x1, y1 = int(fp.get("x1", 0)), int(fp.get("y1", 0))
    return px is not None and x0 <= px <= x1 and y0 <= py <= y1


def draw_terrain_tile(client, rect, tile_id, wx, wy, t):
    if not (_realm(client) or _interior(client)):
        return False
    if _realm(client):
        char = REALM_ROWS[wy][wx] if 0 <= wy < len(REALM_ROWS) and 0 <= wx < len(REALM_ROWS[wy]) else "."
        if char == "T":
            sprites.draw_grass(client.screen, rect, wx, wy)
            client.draw_resource_sprite("tree", rect.centerx, rect.centery, t)
        elif char == "~":
            sprites.draw_water_detailed(client.screen, rect, t, wx, wy)
        elif char in "=PSol":
            sprites.draw_path(client.screen, rect, wx, wy, zone="realm")
        else:
            sprites.draw_grass(client.screen, rect, wx, wy)
        return True
    if tile_id == wm.WATER:
        sprites.draw_water_detailed(client.screen, rect, t, wx, wy)
    elif tile_id == wm.WALL:
        sprites.draw_wall(client.screen, rect, "dungeon", wx, wy)
    else:
        sprites.draw_floor(client.screen, rect, wx, wy, zone="dungeon", interior=True)
    return True


def draw_floor_plane(client, cam_x, cam_y, tile):
    if not _interior(client):
        return
    plane = _plane(client)
    floor = FLOORS[plane]
    relative = floor.get("sprite_1x" if tile <= 40 else "sprite_2x")
    image = _surface(floor.get("_root"), relative, tile) if relative else None
    if image is None:
        return
    sx, sy = client.world_to_view_offset(0, 0, cam_x, cam_y)
    origin = floor.get("origin_px_1x" if tile <= 40 else "origin_px_2x", (0, 0))
    scale = tile / (40.0 if tile <= 40 else 80.0)
    client.screen.blit(image, (sx * tile - origin[0] * scale, sy * tile - origin[1] * scale))


def return_portal_xy():
    portal = REALM.get("return_portal") or {}
    return int(portal.get("x", 150)), int(portal.get("y", 186))


def queue(client, draw_list, cam_x, cam_y, tile):
    if not _realm(client) or not ready():
        return
    px, py = client.player_xy() if client.player else (None, None)
    for castle_id, blob in CASTLE_DATA.items():
        if not _castle_ready(blob):
            continue
        _queue_castle(client, draw_list, cam_x, cam_y, tile, castle_id, blob, px, py)


def _queue_castle(client, draw_list, cam_x, cam_y, tile, castle_id, blob, px, py):
    fp = blob["footprint"]
    x0, y0, x1, y1 = int(fp["x0"]), int(fp["y0"]), int(fp["x1"]), int(fp["y1"])
    sx, sy = client.world_to_view_offset(x0, y0, cam_x, cam_y)
    sprite = blob.get("sprite_1x" if tile <= 40 else "sprite_2x") or blob.get("sprite_1x") or {}
    origin = sprite.get("origin_px", (0, 0))
    scale = tile / (40.0 if tile <= 40 or "sprite_2x" not in blob else 80.0)
    left, top = sx * tile - origin[0] * scale, sy * tile - origin[1] * scale
    root = blob["_root"]
    layers = {layer["name"]: layer["file"] for layer in blob.get("layers", [])}
    # A cutaway layer hides the roof of a keep you are standing inside.
    # Sky-Anchor has none: the keep is airborne, so the sort layer stays up.
    inside = _inside_keep(blob, px, py) and "cutaway" in layers
    # The 24-tile gothic keep stays one sprite sorted at its south edge.
    # A taller bailey, or a castle with sort layers, sorts the back wall at
    # the north edge so people in the yard draw in front of it. The gate,
    # posts and front lip stay at the south edge.
    if blob.get("sort_layers") or (y1 - y0) > 24:
        back_row = sy * tile
        south_row = (sy + (y1 - y0)) * tile
    else:
        back_row = (sy + 24) * tile
        south_row = back_row
    screen = client.screen

    def _blit(relative, x=left, y=top, n=tile, castle_root=root):
        image = _surface(castle_root, relative, n)
        if image is not None:
            screen.blit(image, (x, y))

    ground = layers.get("ground")
    if ground:
        draw_list.append((-10**9, 0, lambda g=ground: _blit(g)))
    back_name = "cutaway" if inside and "cutaway" in layers else "back"
    back = layers.get(back_name)
    if back:
        draw_list.append((back_row, 40, lambda g=back: _blit(g)))
    fountain = blob.get("fountain") or {}
    fountain_frames = fountain.get("frames") or []
    if fountain_frames:
        rel = fountain_frames[_anim_frame(fountain_frames)].get("file")
        crop = fountain.get("crop_1x") or (0, 0)
        fx = left + int(crop[0]) * scale
        fy = top + int(crop[1]) * scale
        tile_px = float(blob.get("tile_px") or 40)
        origin_y = float(origin[1]) if origin else 0.0
        if len(crop) >= 4:
            mid_y = (int(crop[1]) + int(crop[3])) / 2.0
        else:
            mid_y = float(crop[1])
        fountain_sy = sy + (mid_y - origin_y) / tile_px
        draw_list.append((fountain_sy * tile + tile // 2, 42, lambda g=rel, x=fx, y=fy: _blit(g, x, y)))
    posts = layers.get("posts")
    if posts:
        draw_list.append((south_row, 30, lambda g=posts: _blit(g)))
    frames = blob.get("gate", {}).get("frames", [])
    if frames:
        frame = _gate_frame(castle_id, blob, px or -1, py or -1)
        gate = frames[frame].get("file") or f"sprites/1x/gate/gate_{frame:02d}.png"
        crop = (blob.get("gate") or {}).get("crop_1x") or (0, 0)
        gx = left + int(crop[0]) * scale
        gy = top + int(crop[1]) * scale
        draw_list.append((south_row, 41, lambda g=gate, x=gx, y=gy: _blit(g, x, y)))
    if not inside:
        for sort_layer in blob.get("sort_layers", []):
            rel = sort_layer.get("file")
            sort_row = int(sort_layer.get("sort_row_world", y0))
            _sx, sort_sy = client.world_to_view_offset(x0, sort_row, cam_x, cam_y)
            sort_y = sort_sy * tile + tile // 2
            draw_list.append((sort_y, 35, lambda g=rel: _blit(g)))
        front = layers.get("front")
        if front:
            draw_list.append((10**9, 0, lambda g=front: _blit(g)))
    # Waterfalls sit with the floating rock, just after its sort layer.
    waterfall = blob.get("waterfall") or {}
    waterfall_frames = waterfall.get("frames") or []
    if waterfall_frames:
        rel = waterfall_frames[_anim_frame(waterfall_frames)].get("file")
        crop = waterfall.get("crop_1x") or (0, 0)
        wx = left + int(crop[0]) * scale
        wy = top + int(crop[1]) * scale
        sort_rows = [int(layer.get("sort_row_world", y0)) for layer in blob.get("sort_layers", [])]
        fall_row = max(sort_rows) if sort_rows else y0
        _sx, fall_sy = client.world_to_view_offset(x0, fall_row, cam_x, cam_y)
        draw_list.append((fall_sy * tile + tile // 2, 36, lambda g=rel, x=wx, y=wy: _blit(g, x, y)))


def draw_overlay(client):
    if not _interior(client):
        return
    mx, my = pygame.mouse.get_pos()
    if mx >= 900 or my >= 640:
        return
    tile = client.screen_to_tile(mx, my)
    if not tile:
        return
    wx, wy = tile
    for room in FLOORS[_plane(client)].get("rooms", []):
        x0, y0, x1, y1 = room["rect"]
        if x0 <= wx <= x1 and y0 <= wy <= y1:
            text = client.font_small.render(room.get("name", ""), True, (255, 230, 170))
            client.screen.blit(text, (mx + 12, my + 12))
            return