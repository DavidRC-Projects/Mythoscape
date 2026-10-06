"""Moonpetal Glade ground: moss, petal path, moonstone paving, grass edges, decals.

Visual only. Collision stays on the server. A WALL tile listed in ground_under.json
is still unwalkable; this module only paints the ground that was under it.
"""
import json
import os

import pygame

import world_map as wm

_DIR = os.path.join(os.path.dirname(__file__), "..", "assets", "fairy_village")
_DATA = os.path.join(_DIR, "data")
_KIND = {"GRASS": "fairy_moss", "PATH": "petal_path", "STONE": "moonstone_paving"}
_EDGE = {"petal_path": "path_grass_edge", "moonstone_paving": "paving_grass_edge"}
# N NE E SE S SW W NW
_NEIGH = (
    (0, -1, 1), (1, -1, 2), (1, 0, 4), (1, 1, 8),
    (0, 1, 16), (-1, 1, 32), (-1, 0, 64), (-1, -1, 128),
)
# A diagonal stays only when both of its orthogonal neighbours are clear.
_DIAG = {2: (1, 4), 8: (4, 16), 32: (16, 64), 128: (1, 64)}

_IMAGES = {}
_UNDER = None
_DECALS = None
_CONTACT = None
_ZONE = None


def fairy_variant(x, y):
    h = (x * 73856093) ^ (y * 19349663)
    h = (h ^ (h >> 13)) * 1274126177 & 0xFFFFFFFF
    return (h >> 8) % 5 + 1


def paving_variant(x, y):
    return (y % 4) * 4 + (x % 4) + 1


def hides_wall(x, y):
    """True when this WALL is a fairy building or fountain footprint."""
    return f"{x},{y}" in _under()


def _zone():
    global _ZONE
    if _ZONE is None:
        _ZONE = wm.ZONES["fairy_village"]
    return _ZONE


def _load(name):
    path = os.path.join(_DATA, name)
    if not os.path.exists(path):
        return {}
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def _under():
    global _UNDER
    if _UNDER is None:
        _UNDER = _load("ground_under.json").get("tiles", {})
    return _UNDER


def _decals():
    global _DECALS
    if _DECALS is None:
        _DECALS = _load("ground_decals.json").get("decals", [])
    return _DECALS


def _contact():
    global _CONTACT
    if _CONTACT is None:
        _CONTACT = _load("contact_decals.json").get("contact_decals", [])
    return _CONTACT


def _source_px(tile):
    if tile <= 40:
        return 40
    if tile <= 80:
        return 80
    return 160


def _scaled(path, tile, alpha):
    key = (path, tile, alpha)
    image = _IMAGES.get(key)
    if image is not None:
        return image
    if path not in _IMAGES:
        if not os.path.exists(path):
            _IMAGES[path] = None
        else:
            raw = pygame.image.load(path)
            _IMAGES[path] = raw.convert_alpha() if alpha else raw.convert()
    raw = _IMAGES.get(path)
    if raw is None:
        return None
    if raw.get_width() != tile or raw.get_height() != tile:
        raw = pygame.transform.smoothscale(raw, (tile, tile))
    _IMAGES[key] = raw
    return raw


def _decal_image(decal_id, tile, origin):
    """1x art at TILE <= 40, 2x above. Returns (image, origin_x, origin_y) in blit pixels."""
    tag, base = ("1x", 40) if tile <= 40 else ("2x", 80)
    path = os.path.join(_DIR, "decals", decal_id, f"{decal_id}_{tag}.png")
    key = (path, tile)
    image = _IMAGES.get(key)
    if image is None and path not in _IMAGES:
        if not os.path.exists(path):
            _IMAGES[path] = None
        else:
            raw = pygame.image.load(path).convert_alpha()
            if base != tile:
                factor = tile / float(base)
                raw = pygame.transform.smoothscale(
                    raw, (max(1, int(round(raw.get_width() * factor))),
                          max(1, int(round(raw.get_height() * factor)))))
            _IMAGES[path] = raw
            _IMAGES[key] = raw
        image = _IMAGES.get(key) or _IMAGES.get(path)
    ox, oy = origin.get(tag, origin.get("1x", [0, 0]))
    factor = tile / float(base)
    return image, ox * factor, oy * factor


def _kind_name(tile_id, wx, wy):
    if tile_id == wm.GRASS:
        return "fairy_moss"
    if tile_id == wm.PATH:
        return "petal_path"
    if tile_id == wm.STONE:
        return "moonstone_paving"
    if tile_id == wm.WALL:
        named = _under().get(f"{wx},{wy}")
        return _KIND.get(named)
    return None


def _grass_like(client, x, y):
    tiles = client.tiles
    if not (0 <= y < len(tiles) and 0 <= x < client.world_w):
        return False
    tid = tiles[y][x]
    if tid == wm.GRASS or tid in wm.TREE_TILES:
        return True
    return tid == wm.WALL and _under().get(f"{x},{y}") == "GRASS"


def _edge_mask(client, wx, wy):
    bits = 0
    for dx, dy, bit in _NEIGH:
        if _grass_like(client, wx + dx, wy + dy):
            bits |= bit
    for bit, (a, b) in _DIAG.items():
        if bits & bit and (bits & a or bits & b):
            bits &= ~bit
    return bits


def draw_tile(client, rect, tile_id, wx, wy):
    """Paint one glade tile. False means the caller should draw it the old way."""
    if client.dungeon:
        return False
    x0, y0, x1, y1 = _zone()
    if not (x0 <= wx <= x1 and y0 <= wy <= y1):
        return False
    name = _kind_name(tile_id, wx, wy)
    if name is None:
        return False
    if name == "moonstone_paving":
        variant = paving_variant(wx, wy)
    else:
        variant = fairy_variant(wx, wy)
    tile = rect.w
    src = _source_px(tile)
    path = os.path.join(_DIR, "tiles", f"{name}_v{variant}_{src}.png")
    image = _scaled(path, tile, False)
    if image is None:
        return False
    client.screen.blit(image, rect.topleft)
    edge_name = _EDGE.get(name)
    if edge_name and tile_id != wm.WALL:
        mask = _edge_mask(client, wx, wy)
        if mask:
            edge = os.path.join(
                _DIR, "tiles", "edges", f"{edge_name}_{mask:03d}_{src}.png")
            overlay = _scaled(edge, tile, True)
            if overlay is not None:
                client.screen.blit(overlay, rect.topleft)
    return True


def _blit_decal(client, cam_x, cam_y, view, decal_id, x, y, origin):
    tile = client.map_screen_rect(x, y, cam_x, cam_y).w
    image, ox, oy = _decal_image(decal_id, tile, origin)
    if image is None:
        return
    rect = client.map_screen_rect(x, y, cam_x, cam_y)
    dest = pygame.Rect(int(round(rect.x - ox)), int(round(rect.y - oy)),
                       image.get_width(), image.get_height())
    if not dest.colliderect(view):
        return
    client.screen.blit(image, dest.topleft)


def draw_overlays(client, cam_x, cam_y, vis_w, vis_h):
    """Contact skirts, then scattered decals. Buildings draw later and cover the skirts."""
    if client.dungeon:
        return
    tile = client.map_screen_rect(0, 0, cam_x, cam_y).w
    view = pygame.Rect(0, 0, (vis_w + 1) * tile, (vis_h + 1) * tile)
    for entry in _contact():
        meta = entry.get("meta") or {}
        ax, ay = entry.get("anchor_tile") or (None, None)
        if ax is None:
            continue
        _blit_decal(client, cam_x, cam_y, view, entry["id"], ax, ay,
                    meta.get("origin_px") or {})
    for entry in _decals():
        meta_path = os.path.join(_DIR, "decals", entry["id"], "meta.json")
        meta = _IMAGES.get(meta_path)
        if meta is None and meta_path not in _IMAGES:
            if os.path.exists(meta_path):
                with open(meta_path, encoding="utf-8") as f:
                    meta = json.load(f)
            else:
                meta = {}
            _IMAGES[meta_path] = meta
        meta = _IMAGES.get(meta_path) or {}
        _blit_decal(client, cam_x, cam_y, view, entry["id"], entry["x"], entry["y"],
                    meta.get("origin_px") or {})
