"""Moonpetal Glade sprites. Buildings, fountains, and fairies use the pack
art. Tiles are the seamless moss, petal, and moonstone set.
"""
from __future__ import annotations

import os

import pygame

import world_map as wm

_DIR = os.path.normpath(os.path.join(
    os.path.dirname(__file__), "..", "assets", "fairy_village",
))
_BUILDINGS = (
    ("queens_tree_hall", 4, 77, 12, 85, "The Queen's Tree-Hall"),
    ("moonpetal_inn", 16, 77, 25, 84, "The Moonpetal Inn"),
    ("mushroom_apothecary", 34, 58, 40, 64, "Tumbleroot's Apothecary"),
)
_FOUNTAINS = (
    ("moonstone_fountain", 26, 61, 30, 65, (28, 65)),
    ("lily_fountain", 32, 77, 34, 79, (33, 79)),
)
FAIRY_NPCS = {
    "elowen_moonwhisper": (180, 140, 220),
    "warden_thorne": (90, 120, 70),
    "tumbleroot": (160, 110, 60),
    "pip_dewdrop": (120, 190, 220),
}
_IMAGES = {}
_TILES = {}


def _load(path):
    if path in _IMAGES:
        return _IMAGES[path]
    if not os.path.isfile(path):
        _IMAGES[path] = None
        return None
    image = pygame.image.load(path).convert_alpha()
    _IMAGES[path] = image
    return image


def _scale_for(tile):
    if tile >= 80:
        return "2x", 80
    return "1x", 40


def _building(key, tile):
    tag, base = _scale_for(tile)
    path = os.path.join(_DIR, "buildings", key, f"{key}_{tag}.png")
    image = _load(path)
    if image is None or tile == base:
        return image
    w = max(1, int(image.get_width() * tile / base))
    h = max(1, int(image.get_height() * tile / base))
    cache = (path, tile)
    if cache not in _IMAGES:
        _IMAGES[cache] = pygame.transform.smoothscale(image, (w, h))
    return _IMAGES[cache]


def _origin(key, tile):
    tag, base = _scale_for(tile)
    path = os.path.join(_DIR, "buildings", key, "meta.json")
    import json
    meta = _load_meta(path)
    origin = (meta.get("origin_px") or {}).get(tag) or [0, 0]
    if not isinstance(origin, (list, tuple)):
        origin = [0, 0]
    scale = tile / float(base)
    return origin[0] * scale, origin[1] * scale


_META = {}


def _load_meta(path):
    if path not in _META:
        if not os.path.isfile(path):
            _META[path] = {}
        else:
            import json
            with open(path, encoding="utf-8") as handle:
                _META[path] = json.load(handle)
    return _META[path]


def _ground(kind, wx, wy, tile):
    tag, base = _scale_for(tile)
    variant = ((wx * 3 + wy * 5) % 3) + 1
    names = {
        wm.GRASS: "fairy_moss",
        wm.PATH: "petal_path",
        wm.STONE: "moonstone_paving",
    }
    stem = names.get(kind)
    if not stem:
        return None
    path = os.path.join(_DIR, "tiles", f"{stem}_v{variant}_{base}.png")
    image = _load(path)
    if image is None:
        return None
    if tile == base:
        return image
    cache = (path, tile)
    if cache not in _IMAGES:
        _IMAGES[cache] = pygame.transform.smoothscale(image, (tile, tile))
    return _IMAGES[cache]


def draw_terrain(screen, rect, tile_id, wx, wy):
    image = _ground(tile_id, wx, wy, rect.w)
    if image is None:
        return False
    screen.blit(image, rect.topleft)
    return True


def _scaled(path, tile, base):
    image = _load(path)
    if image is None or tile == base:
        return image
    cache = (path, tile)
    if cache not in _IMAGES:
        w = max(1, int(round(image.get_width() * tile / float(base))))
        h = max(1, int(round(image.get_height() * tile / float(base))))
        _IMAGES[cache] = pygame.transform.smoothscale(image, (w, h))
    return _IMAGES[cache]


def _px(meta, field, tile, fallback):
    tag, base = _scale_for(tile)
    point = (meta.get(field) or {}).get(tag) or fallback
    scale = tile / float(base)
    return point[0] * scale, point[1] * scale


def _sheet_facing(face, moving):
    """Pack sheets are the yaw-0 camera: s toward the camera."""
    if not moving:
        return "s"
    if face in ("back", "n"):
        return "n"
    if face in (-1, "-1", "w"):
        return "w"
    if face in (1, "1", "e"):
        return "e"
    return "s"


def queue(client, draw_list, cam_x, cam_y, tile, t=0.0):
    if client.dungeon:
        return
    for key, x0, y0, x1, y1, label in _BUILDINGS:
        image = _building(key, tile)
        if image is None:
            continue
        sx, sy = client.world_to_view_offset(x0, y0, cam_x, cam_y)
        ox, oy = _origin(key, tile)
        left, top = sx * tile - ox, sy * tile - oy
        _sx, south = client.world_to_view_offset(x0, y1, cam_x, cam_y)
        sort_y = south * tile + tile

        def _blit(image=image, left=left, top=top, label=label):
            client.screen.blit(image, (left, top))
            client.blit_nameplate(label, left + image.get_width() // 2, top + 8, (220, 200, 255))

        draw_list.append((sort_y, 1, _blit))
    for key, x0, y0, x1, y1, _interact in _FOUNTAINS:
        _sx, south = client.world_to_view_offset(x0, y1, cam_x, cam_y)
        sort_y = south * tile + tile

        def _fountain(x0=x0, y0=y0, key=key):
            _draw_fountain(client, cam_x, cam_y, tile, x0, y0, key, t)

        draw_list.append((sort_y, 1, _fountain))


def _draw_fountain(client, cam_x, cam_y, tile, x0, y0, key, t):
    tag, base = _scale_for(tile)
    meta = _load_meta(os.path.join(_DIR, "fountains", key, "meta.json"))
    frames = max(1, int(meta.get("frames") or 10))
    fps = float(meta.get("fps") or 10)
    idx = int(t * fps) % frames
    path = os.path.join(_DIR, "fountains", key, f"frames_{tag}", f"f{idx:02d}.png")
    image = _scaled(path, tile, base)
    if image is None:
        return
    sx, sy = client.world_to_view_offset(x0, y0, cam_x, cam_y)
    ox, oy = _px(meta, "origin_px", tile, [0, 0])
    client.screen.blit(image, (sx * tile - ox, sy * tile - oy))


def draw_npc(client, n, cx, cy, tile, t, face="s", moving=False):
    """Wing-flutter frames from the pack. Not the humanoid walk cycle."""
    tag, base = _scale_for(tile)
    meta = _load_meta(os.path.join(_DIR, "npcs", n["id"], "meta.json"))
    frames = max(1, int(meta.get("frames") or 8))
    fps = float(meta.get("fps") or 8)
    idx = int(t * fps) % frames
    facing = _sheet_facing(face, moving)
    path = os.path.join(
        _DIR, "npcs", n["id"], f"sprite_{tag}", facing, f"f{idx:02d}.png",
    )
    image = _scaled(path, tile, base)
    if image is None:
        return
    fx, fy = _px(meta, "feet_px", tile, [48, 118])
    foot_y = cy + tile // 2
    left = cx - fx
    top = foot_y - fy
    client.screen.blit(image, (left, top))
    client.blit_nameplate(n["name"], cx, int(top) - 2, (255, 230, 200))


def portrait(client, npc_id, height=96):
    """Elowen's bust, if the pack includes one. None for the other fairies."""
    if not npc_id:
        return None
    path = os.path.join(_DIR, "npcs", npc_id, "portrait_bust_512.png")
    image = _load(path)
    if image is None:
        return None
    cache = (path, "portrait", height)
    if cache not in _IMAGES:
        w = max(1, int(round(image.get_width() * height / float(image.get_height()))))
        _IMAGES[cache] = pygame.transform.smoothscale(image, (w, height))
    return _IMAGES[cache]
