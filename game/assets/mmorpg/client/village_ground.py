"""Overworld meadow and packed-earth lanes.

The fairy glade keeps its moss and petal tiles. Everywhere else, grass is a
sunlit meadow and roads are worn earth, with the meadow growing over the
road edge. Collision is unchanged.
"""
from __future__ import annotations

import math
import os

import numpy as np
import pygame

import ground_paint
import world_map as wm

_DIR = os.path.normpath(os.path.join(
    os.path.dirname(__file__), "..", "assets", "village_ground",
))
_IMAGES = {}
_EDGES = {}
_NOISE = None
# Overworld meadow uses grass_world.jpg everywhere except void/volcano fills.
# "dungeon" is an overworld zone box (farm/outfitters), not an instance — it
# must use the same grass sheet as the village or the seam looks like "old grass".
_SKIP_GRASS = ("shadow_crypt", "volcano")
# Overworld dirt lanes use dirt_world.jpg (one year-round look). Only volcano
# keeps its own ground; city/dungeon/shadow_crypt outdoor roads use dirt too.
_SKIP_PATH = ("volcano",)
# N NE E SE S SW W NW
_NEIGH = (
    (0, -1, 1), (1, -1, 2), (1, 0, 4), (1, 1, 8),
    (0, 1, 16), (-1, 1, 32), (-1, 0, 64), (-1, -1, 128),
)
_DIAG = {2: (1, 4), 8: (4, 16), 32: (16, 64), 128: (1, 64)}


def variant(x, y):
    h = (int(x) * 73856093) ^ (int(y) * 19349663)
    h = (h ^ (h >> 13)) * 1274126177 & 0xFFFFFFFF
    return (h >> 8) % 5 + 1


def _source_px(tile):
    if tile <= 40:
        return 40
    if tile <= 80:
        return 80
    return 160


def _scaled(stem, which, tile):
    src = _source_px(tile)
    path = os.path.join(_DIR, f"{stem}_v{which}_{src}.png")
    key = (path, tile)
    if key in _IMAGES:
        return _IMAGES[key]
    if path not in _IMAGES:
        if not os.path.isfile(path):
            _IMAGES[path] = None
        else:
            _IMAGES[path] = pygame.image.load(path).convert()
    raw = _IMAGES.get(path)
    if raw is None:
        _IMAGES[key] = None
        return None
    if raw.get_width() != tile:
        # Fast scale keeps zoom changes from hitching on every grass/path tile.
        raw = pygame.transform.scale(raw, (tile, tile))
    _IMAGES[key] = raw
    return raw


def _noise():
    global _NOISE
    if _NOISE is None:
        rng = np.random.default_rng(90210)
        raw = rng.random(64).astype(np.float32)
        _NOISE = np.concatenate([raw, raw[:1]])
    return _NOISE


def _sample(pos):
    tab = _noise()
    period = len(tab) - 1
    x = np.mod(pos / 9.0, period)
    i0 = np.floor(x).astype(np.int32) % period
    f = x - np.floor(x)
    f = f * f * (3 - 2 * f)
    return tab[i0] * (1 - f) + tab[i0 + 1] * f


def fringe_alpha(mask, n, ox, oy):
    """Grass growing onto a road. ox, oy keep a long road's edge continuous."""
    alpha = np.zeros((n, n), np.float32)
    local = np.arange(n, dtype=np.float32)
    span = np.arange(n)[None, :]

    def band(pos, flip):
        depth = np.clip(n * (0.10 + 0.28 * _sample(pos)), 1, n * 0.42)[:, None]
        t = (n - 1 - span) if flip else span
        solid = depth * 0.62
        fade = np.where(t <= solid, 1.0, 1.0 - (t - solid) / np.maximum(1.0, depth - solid))
        return np.where(t < depth, np.clip(fade, 0, 1), 0)

    if mask & 1:
        alpha = np.maximum(alpha, band(ox + local, False))
    if mask & 16:
        alpha = np.maximum(alpha, band(ox + local + 180, True))
    if mask & 4:
        alpha = np.maximum(alpha, band(oy + local + 90, True).T)
    if mask & 64:
        alpha = np.maximum(alpha, band(oy + local + 270, False).T)
    corners = {2: (n - 1, 0), 8: (n - 1, n - 1), 32: (0, n - 1), 128: (0, 0)}
    for bit, (cx, cy) in corners.items():
        if not (mask & bit):
            continue
        ys, xs = np.mgrid[0:n, 0:n]
        dist = np.hypot(xs - cx, ys - cy)
        rad = n * 0.34
        corner = np.where(dist < rad * 0.55, 1.0, np.where(
            dist < rad, 1.0 - (dist - rad * 0.55) / (rad * 0.45), 0.0))
        alpha = np.maximum(alpha, corner.T)
    return (np.clip(alpha, 0, 1) * 255).astype(np.uint8)


def _is_path_tile_cb(client):
    """Is (x, y) a lane? Uses the live tile grid, read through the client."""
    if client is None:
        return lambda x, y: False
    tiles = client.tiles
    w = getattr(client, "world_w", 0)
    dungeon = bool(getattr(client, "dungeon", None))
    if dungeon or not tiles:
        return lambda x, y: False

    def is_path(x, y):
        ix, iy = int(math.floor(x)), int(math.floor(y))
        if not (0 <= iy < len(tiles) and 0 <= ix < w):
            return False
        tid = tiles[iy][ix]
        if tid == wm.PATH:
            return True
        # Trees, grass and trees-with-ground cover all count as meadow.
        return False

    return is_path


def _paint(client, rect, wx, wy, is_path):
    """Continuous, world-space ground painting (shared fields across tiles).

    `client` is only used for the path field, so the lane/meadow boundary is
    computed from the real tile grid and agrees on both sides of a seam.
    """
    if rect.w <= 4:
        return False
    screen = getattr(client, "screen", None)
    if screen is None:
        return False
    is_path_fn = _is_path_tile_cb(client)
    try:
        # paint() wants the *predicate*, so it can sample the neighbours around
        # this tile and keep the lane edge continuous across the seam. Passing
        # is_path_fn(...) here handed it a bool, which raised on every tile —
        # and the bare except below hid it, so the game silently kept drawing
        # the old textures.
        surf = ground_paint.paint(rect.w, int(wx), int(wy), is_path_fn)
    except Exception:
        # Keep the old art as a fallback, but never silently: a broken painter
        # should be visible in the log instead of costing hours to spot.
        if not getattr(_paint, "_warned", False):
            _paint._warned = True
            import traceback
            traceback.print_exc()
            print("[village_ground] ground painter failed; falling back to the old tiles")
        return False
    if surf is None:
        return False
    screen.blit(surf, rect.topleft)
    return True


# Work in progress. The world-space painter is not finished: the lane surface
# is flat, the edge is too soft and it costs ~9 ms a tile. It is left in the
# tree behind this switch so the work is not lost, but the game draws its
# original ground tiles until it is worth showing.
USE_WORLD_GROUND = False


# Seamless painted meadow: one 24x24-tile texture with built-in light and
# colour drift, sampled by view-space tile so neighbouring tiles always join
# with no seam at any camera yaw. One blit per tile, cached per tile size.
_WORLD_GRASS = "grass_world.jpg"
_GRASS_PERIOD = 24
_GRASS_TEX = {}
_SEASON_TEX = {}  # (kind, season, tile) -> Surface


def clear_season_cache():
    """Drop graded textures when the Crownfall season changes."""
    _SEASON_TEX.clear()
    # Drop season-keyed wraps; keep unseasoned base dirt/water if present.
    doomed = [k for k in _TEX if isinstance(k, tuple) and len(k) >= 3 and k[2]]
    for k in doomed:
        _TEX.pop(k, None)
    doomed_o = [k for k in _OVER if isinstance(k, tuple) and len(k) >= 7 and k[6]]
    for k in doomed_o:
        _OVER.pop(k, None)


_SEASON_MULT = {
    "spring": (0.90, 1.10, 0.92),
    "summer": (1.06, 1.02, 0.86),
    "autumn": (1.18, 0.82, 0.48),
    "winter": (0.72, 0.82, 1.08),
}
# Stronger dirt grades so each Crownfall season reads on the road, not only
# the meadow (city used to skip dirt_world and stay flat cobble grey).
_PATH_MULT = {
    "spring": (0.82, 0.95, 0.78),   # cool damp earth
    "summer": (1.22, 1.05, 0.78),   # warm dry dust
    "autumn": (1.28, 0.78, 0.42),   # russet packed clay
    "winter": (0.62, 0.72, 0.92),   # cold grey-brown
}


def _world_season(client, wx=None, wy=None):
    """Seasonal meadow/path look on the overworld (not inside dungeons)."""
    if client is None or getattr(client, "dungeon", None):
        return None
    env = getattr(client, "env", None) or {}
    season = env.get("season")
    return season if season in _SEASON_MULT else None


# Back-compat alias used by older call sites
_village_season = _world_season


def _grade_surface(base, mult):
    """Return a color-graded copy of an opaque texture (cached by caller)."""
    surf = base.copy()
    arr = pygame.surfarray.pixels3d(surf)
    for i, m in enumerate(mult):
        col = arr[:, :, i].astype(np.float32) * m
        arr[:, :, i] = np.clip(col, 0, 255).astype(np.uint8)
    del arr
    return surf


def _grass_texture(tile, season=None):
    key = (season or "base", tile)
    tex = _SEASON_TEX.get(("grass",) + key)
    if tex is not None or ("grass",) + key in _SEASON_TEX:
        return tex
    path = os.path.join(_DIR, _WORLD_GRASS)
    tex = None
    if os.path.isfile(path):
        try:
            raw = pygame.image.load(path).convert()
            size = _GRASS_PERIOD * tile
            tex = pygame.transform.smoothscale(raw, (size, size))
            if season in _SEASON_MULT:
                tex = _grade_surface(tex, _SEASON_MULT[season])
        except pygame.error:
            tex = None
    if len(_SEASON_TEX) > 16:
        _SEASON_TEX.clear()
    _SEASON_TEX[("grass",) + key] = tex
    # Keep legacy cache warm for non-season callers
    if season is None:
        _GRASS_TEX[tile] = tex
    return tex


def _speckle_grass(screen, rect, wx, wy, season):
    """Stable leaf / snow dust on village meadow tiles."""
    if season not in ("autumn", "winter"):
        return
    h = (int(wx) * 73856093) ^ (int(wy) * 19349663)
    n = 3 if season == "autumn" else 5
    for i in range(n):
        hh = (h ^ (i * 2654435761)) & 0xFFFFFFFF
        px = rect.x + (hh % max(1, rect.w - 2))
        py = rect.y + ((hh >> 8) % max(1, rect.h - 2))
        if season == "autumn":
            col = ((180, 90, 40), (200, 120, 50), (140, 60, 30))[hh % 3]
            screen.fill(col, (px, py, 2, 1))
        else:
            col = (235, 240, 250)
            screen.fill(col, (px, py, 2, 2))


def draw_world_grass(screen, rect, wx, wy, client=None):
    tile = rect.w
    if tile <= 0 or rect.h != tile:
        return False
    # One meadow sheet map-wide (no seasonal grade) so village and wilderness match.
    tex = _grass_texture(tile, season=None)
    if tex is None:
        return False
    vx, vy = wx, wy
    if client is not None and hasattr(client, "world_to_view"):
        try:
            vx, vy = client.world_to_view(wx, wy)
        except Exception:
            pass
    ox = (int(vx) % _GRASS_PERIOD) * tile
    oy = (int(vy) % _GRASS_PERIOD) * tile
    screen.blit(tex, rect.topleft, pygame.Rect(ox, oy, tile, tile))
    return True


def draw_grass(screen, rect, wx, wy, client=None):
    if USE_WORLD_GROUND and client is not None and _paint(client, rect, wx, wy, False):
        return True
    if draw_world_grass(screen, rect, wx, wy, client):
        return True
    image = _scaled("meadow", variant(wx, wy), rect.w)
    if image is None:
        return False
    screen.blit(image, rect.topleft)
    return True


def draw_path(screen, rect, wx, wy, client=None):
    if USE_WORLD_GROUND and client is not None and _paint(client, rect, wx, wy, True):
        return True
    image = _scaled("lane", variant(wx, wy), rect.w)
    if image is None:
        return False
    screen.blit(image, rect.topleft)
    return True


def _grass_like(client, x, y):
    tiles = client.tiles
    if not (0 <= y < len(tiles) and 0 <= x < client.world_w):
        return False
    tid = tiles[y][x]
    return tid == wm.GRASS or tid in wm.TREE_TILES


def _edge_mask(client, wx, wy):
    bits = 0
    for dx, dy, bit in _NEIGH:
        if _grass_like(client, wx + dx, wy + dy):
            bits |= bit
    for bit, (a, b) in _DIAG.items():
        if bits & bit and (bits & a or bits & b):
            bits &= ~bit
    return bits


def _overlay(mask, tile, wx, wy):
    key = (mask, tile, int(wx), int(wy))
    image = _EDGES.get(key)
    if image is not None:
        return image
    meadow = _scaled("meadow", variant(wx, wy), tile)
    if meadow is None:
        return None
    surf = meadow.convert_alpha()
    alpha = pygame.surfarray.pixels_alpha(surf)
    alpha[:, :] = fringe_alpha(mask, tile, int(wx) * tile, int(wy) * tile)
    del alpha
    _EDGES[key] = surf
    return surf


def draw_edge(client, rect, wx, wy):
    mask = _edge_mask(client, wx, wy)
    if not mask:
        return
    image = _overlay(mask, rect.w, wx, wy)
    if image is not None:
        client.screen.blit(image, rect.topleft)


def paints_grass(zone):
    return zone not in _SKIP_GRASS


def paints_path(zone):
    return zone not in _SKIP_PATH


# ---------------------------------------------------------------------------
# Painted dirt roads and water, sampled in view space like the meadow.
# Roads: one seamless 24-tile dirt texture; the meadow grows over each road
# edge with a soft, noisy fringe (no square corners). Water: a seamless
# 12-tile painted lake that drifts slowly, with two glint layers flowing in
# different directions, and a soft land bleed plus a foam / wet-sand line on
# every shore. Fishing-spot effects draw on top later and are untouched.
# ---------------------------------------------------------------------------
_TEX = {}
_OVER = {}
_FOAM = {}
_WATER_PERIOD = 12


def _wrap_texture(name, period, tile, margin=1, alpha=False, season=None, path_grade=False):
    key = (name, tile, season or "", bool(path_grade))
    if key in _TEX:
        return _TEX[key]
    path = os.path.join(_DIR, name)
    tex = None
    if os.path.isfile(path):
        try:
            raw = pygame.image.load(path)
            raw = raw.convert_alpha() if alpha else raw.convert()
            size = period * tile
            base = pygame.transform.smoothscale(raw, (size, size))
            if season and not alpha:
                mult = (_PATH_MULT if path_grade else _SEASON_MULT).get(season)
                if mult:
                    base = _grade_surface(base, mult)
            tex = pygame.Surface((size + margin * tile, size + margin * tile)).convert()
            for ox in (0, size):
                for oy in (0, size):
                    tex.blit(base, (ox, oy))
        except pygame.error:
            tex = None
    if len(_TEX) > 24:
        _TEX.clear()
    _TEX[key] = tex
    return tex


def _view_xy(client, wx, wy):
    if client is not None and hasattr(client, "world_to_view"):
        try:
            return client.world_to_view(wx, wy)
        except Exception:
            pass
    return wx, wy


def _view_mask(client, vx, vy, pred):
    """8-neighbour bits (N NE E SE S SW W NW) in *view* space, so edges stay right at any yaw."""
    bits = 0
    to_world = getattr(client, "view_to_world", None)
    for dx, dy, bit in _NEIGH:
        nx, ny = vx + dx, vy + dy
        if to_world is not None:
            try:
                nx, ny = to_world(nx, ny)
            except Exception:
                pass
        if pred(nx, ny):
            bits |= bit
    for bit, (a, b) in _DIAG.items():
        if bits & bit and (bits & a or bits & b):
            bits &= ~bit
    return bits


def _tile_at(client, x, y):
    tiles = client.tiles
    if 0 <= y < len(tiles) and 0 <= x < client.world_w:
        return tiles[y][x]
    return None


def _overlay_from(tex_name, period, mask, tile, vx, vy, shrink=1.0, season=None):
    key = (tex_name, mask, tile, int(vx), int(vy), shrink, season or "")
    surf = _OVER.get(key)
    if surf is not None:
        return surf
    tex = _wrap_texture(tex_name, period, tile, season=season, path_grade=False)
    if tex is None:
        return None
    ox, oy = (int(vx) % period) * tile, (int(vy) % period) * tile
    surf = tex.subsurface(pygame.Rect(ox, oy, tile, tile)).convert_alpha()
    # fringe_alpha already returns 0..255 uint8
    a = np.asarray(fringe_alpha(mask, tile, int(vx) * tile, int(vy) * tile), np.float32)
    if shrink != 1.0:
        a = np.clip(a * shrink, 0, 255)
    px = pygame.surfarray.pixels_alpha(surf)
    px[:, :] = np.clip(a, 0, 255).astype(np.uint8)
    del px
    if len(_OVER) > 2500:
        _OVER.clear()
    _OVER[key] = surf
    return surf


def _is_path(client, x, y):
    return _tile_at(client, x, y) == wm.PATH


def _fairy_path_dirs(client, wx, wy):
    """Cardinal dirs whose neighbour is a petal-avenue PATH (fairy_village zone)."""
    if client is None or not getattr(client, "tiles", None):
        return []
    out = []
    for dx, dy in ((0, -1), (1, 0), (0, 1), (-1, 0)):
        nx, ny = wx + dx, wy + dy
        if not _is_path(client, nx, ny):
            continue
        if wm.get_zone(nx, ny) == "fairy_village":
            out.append((dx, dy))
    return out


def _merge_alpha(tile, dirs):
    """Soft wipe toward fairy neighbours — dirt gives way to petal on that edge."""
    a = np.zeros((tile, tile), dtype=np.float32)
    yy, xx = np.mgrid[0:tile, 0:tile]
    fx = (xx + 0.5) / tile
    fy = (yy + 0.5) / tile
    # Cheap value noise so the seam is not a ruler line.
    n = (
        np.sin(xx * 0.55 + yy * 0.37) * 0.12
        + np.sin(xx * 0.21 - yy * 0.49) * 0.08
    )
    for dx, dy in dirs:
        if dy < 0:      # fairy north → stronger petal at top
            a = np.maximum(a, np.clip(1.15 - fy * 1.7 + n, 0, 1))
        elif dy > 0:
            a = np.maximum(a, np.clip(fy * 1.7 - 0.15 + n, 0, 1))
        elif dx > 0:
            a = np.maximum(a, np.clip(fx * 1.7 - 0.15 + n, 0, 1))
        elif dx < 0:
            a = np.maximum(a, np.clip(1.15 - fx * 1.7 + n, 0, 1))
    return a


def _blit_petal_merge(screen, rect, wx, wy, dirs):
    """Overlay petal tiles onto village dirt where the two roads meet."""
    tile = rect.w
    if tile <= 0 or not dirs:
        return
    try:
        from fairy_ground import fairy_variant, _source_px, _scaled, _DIR
        src = _source_px(tile)
        variant = fairy_variant(wx, wy)
        path = os.path.join(_DIR, "tiles", f"petal_path_v{variant}_{src}.png")
        image = _scaled(path, tile, False)
        if image is None:
            return
        surf = image.convert_alpha()
        alpha = _merge_alpha(tile, dirs)
        px = pygame.surfarray.pixels_alpha(surf)
        px[:, :] = (alpha.T * 220).astype(np.uint8)
        del px
        screen.blit(surf, rect.topleft)
    except Exception:
        return


def draw_world_path(screen, rect, wx, wy, client=None):
    tile = rect.w
    if tile <= 0 or rect.h != tile:
        return False
    # One consistent dirt look year-round (no seasonal grade / wash).
    tex = _wrap_texture("dirt_world.jpg", _GRASS_PERIOD, tile, season=None, path_grade=False)
    if tex is None:
        return False
    vx, vy = _view_xy(client, wx, wy)
    ox, oy = (int(vx) % _GRASS_PERIOD) * tile, (int(vy) % _GRASS_PERIOD) * tile
    screen.blit(tex, rect.topleft, pygame.Rect(ox, oy, tile, tile))
    if client is not None and getattr(client, "tiles", None):
        mask = _view_mask(client, vx, vy, lambda x, y: _grass_like(client, x, y))
        if mask:
            over = _overlay_from(
                "grass_world.jpg", _GRASS_PERIOD, mask, tile, vx, vy, season=None,
            )
            if over is not None:
                screen.blit(over, rect.topleft)
        fairy_dirs = _fairy_path_dirs(client, wx, wy)
        if fairy_dirs:
            _blit_petal_merge(screen, rect, wx, wy, fairy_dirs)
    return True


def _foam(mask, tile, vx, vy):
    key = (mask, tile, int(vx), int(vy))
    surf = _FOAM.get(key)
    if surf is not None:
        return surf
    a = np.asarray(fringe_alpha(mask, tile, int(vx) * tile + 37, int(vy) * tile + 11), np.float32)
    foam = np.clip(1 - np.abs(a - 0.35) / 0.2, 0, 1) * 0.75     # bright line just off the bank
    sand = np.clip(1 - np.abs(a - 0.62) / 0.25, 0, 1) * 0.55     # wet sand under the bleed
    surf = pygame.Surface((tile, tile), pygame.SRCALPHA)
    rgb = pygame.surfarray.pixels3d(surf)
    w = foam / np.maximum(foam + sand, 1e-3)
    for c, (fc, sc) in enumerate(zip((232, 242, 240), (140, 122, 84))):
        rgb[:, :, c] = (w * fc + (1 - w) * sc).astype(np.uint8)
    del rgb
    al = pygame.surfarray.pixels_alpha(surf)
    al[:, :] = (np.maximum(foam, sand) * 255).astype(np.uint8)
    del al
    if len(_FOAM) > 2500:
        _FOAM.clear()
    _FOAM[key] = surf
    return surf


def draw_world_water(screen, rect, wx, wy, t, client=None):
    tile = rect.w
    if tile <= 0 or rect.h != tile:
        return False
    tex = _wrap_texture("water_world.jpg", _WATER_PERIOD, tile)
    glint = _wrap_texture("water_glint.png", _WATER_PERIOD, tile)
    if tex is None:
        return False
    vx, vy = _view_xy(client, wx, wy)
    span = _WATER_PERIOD * tile
    drift = t * tile * 0.10
    ox = int((int(vx) % _WATER_PERIOD) * tile + drift) % span
    oy = int((int(vy) % _WATER_PERIOD) * tile + drift * 0.4) % span
    screen.blit(tex, rect.topleft, pygame.Rect(ox, oy, tile, tile))
    if glint is not None:
        for sx, sy, k in ((0.31, -0.17, 0), (-0.23, 0.29, 5)):
            gx = int((int(vx + k) % _WATER_PERIOD) * tile + t * tile * sx) % span
            gy = int((int(vy + k) % _WATER_PERIOD) * tile + t * tile * sy) % span
            screen.blit(glint, rect.topleft, pygame.Rect(gx, gy, tile, tile),
                        special_flags=pygame.BLEND_ADD)
    if client is not None and getattr(client, "tiles", None):
        bits = _shore_bits(client, vx, vy)
        if bits:
            grassy = _view_mask(client, vx, vy, lambda x, y: _grass_like(client, x, y))
            kind = bool(grassy)
            if not grassy and _view_mask(client, vx, vy, lambda x, y: _is_rock(client, x, y)):
                kind = "rock"
            land_tex, fx = _shore_water_layers(bits, tile, vx, vy, kind)
            if fx is not None:
                screen.blit(fx, rect.topleft)
            if land_tex is not None:
                screen.blit(land_tex, rect.topleft)
    return True


# ---- rounded shorelines ----------------------------------------------------------
# A smooth "land-ness" field is built from the 5x5 neighbourhood of tile centres
# (gaussian weights), so straight banks sit exactly on the tile seam while
# corners round off like a lake shore, on both the water and the land side.
# Purely visual: collision stays per tile.
_SHORE_SIGMA = 0.62
_SHORE = {}
_SHORE_LAND = {}


def _is_land(client, x, y):
    import world_map as _wm
    tid = _tile_at(client, x, y)
    if tid in (_wm.WATER, None):
        return False
    pier = getattr(client, "_is_pier_tile", None)
    return not (pier is not None and pier(x, y))


def _is_rock(client, x, y):
    """Cliff / wall tiles: water meeting them gets a wet-rock bank, not dirt."""
    import world_map as _wm
    return _tile_at(client, x, y) == _wm.WALL


def _shore_bits(client, vx, vy, pred=None):
    """25-bit land mask of the 5x5 view-space neighbourhood (bit 12 = centre)."""
    pred = pred or (lambda x, y: _is_land(client, x, y))
    to_world = getattr(client, "view_to_world", None)
    bits = 0
    i = 0
    for dy in range(-2, 3):
        for dx in range(-2, 3):
            nx, ny = vx + dx, vy + dy
            if to_world is not None:
                try:
                    nx, ny = to_world(nx, ny)
                except Exception:
                    pass
            if pred(nx, ny):
                bits |= 1 << i
            i += 1
    return bits


def shore_field(bits, n, vx, vy):
    """n x n float field ([x, y] like surfarray), 1 = land, 0 = water."""
    c = (np.arange(n, dtype=np.float32) + 0.5) / n
    xs, ys = c[:, None], c[None, :]
    num = np.zeros((n, n), np.float32)
    den = np.zeros((n, n), np.float32)
    k = 1.0 / (2 * _SHORE_SIGMA * _SHORE_SIGMA)
    i = 0
    for dy in range(-2, 3):
        for dx in range(-2, 3):
            g = np.exp(-(((xs - (dx + 0.5)) ** 2) + ((ys - (dy + 0.5)) ** 2)) * k)
            den += g
            if bits >> i & 1:
                num += g
            i += 1
    f = num / np.maximum(den, 1e-6)
    # Gentle, world-continuous wobble so long banks are not ruler-straight.
    px = (int(vx) * n + np.arange(n, dtype=np.float32))[:, None] * (7.0 / n)
    py = (int(vy) * n + np.arange(n, dtype=np.float32))[None, :] * (7.0 / n)
    wob = (0.5 * (_sample(px + py * 0.37 + 5.0) + _sample(py - px * 0.29 + 400.0)) - 0.5
           + 0.35 * (_sample(px * 2.7 - py + 90.0) - 0.5))
    return np.clip(f + 0.30 * wob, 0.0, 1.0)


def _smooth(e0, e1, x):
    t = np.clip((x - e0) / (e1 - e0), 0, 1)
    return t * t * (3 - 2 * t)


def _bump(x, c, w):
    t = np.clip(1 - np.abs(x - c) / w, 0, 1)
    return t * t * (3 - 2 * t)


def _fx_surface(f, n, rock=False):
    """Wet sand just off the bank, a bright foam line and a faint outer ripple.
    Against rock: a dark wet-stone shadow band instead of sand, softer foam."""
    if rock:
        sand = _bump(f, 0.42, 0.10) * 0.70
        foam = _bump(f, 0.33, 0.045) * 0.55 + _bump(f, 0.24, 0.035) * 0.22
    else:
        sand = _bump(f, 0.44, 0.07) * 0.75
        foam = _bump(f, 0.365, 0.05) * 0.80 + _bump(f, 0.27, 0.035) * 0.28
    a = np.maximum(sand, foam)
    if float(a.max()) < 0.02:
        return None
    w = foam / np.maximum(foam + sand, 1e-4)
    surf = pygame.Surface((n, n), pygame.SRCALPHA)
    rgb = pygame.surfarray.pixels3d(surf)
    sand_rgb = (22, 30, 34) if rock else (124, 106, 74)
    for ch, (fc, sc) in enumerate(zip((236, 246, 244), sand_rgb)):
        rgb[:, :, ch] = (w * fc + (1 - w) * sc).astype(np.uint8)
    del rgb
    al = pygame.surfarray.pixels_alpha(surf)
    al[:, :] = (np.clip(a, 0, 1) * 255).astype(np.uint8)
    del al
    return surf


def _shore_water_layers(bits, tile, vx, vy, grassy):
    key = (bits, tile, int(vx), int(vy), grassy)
    hit = _SHORE.get(key)
    if hit is not None:
        return hit
    f = shore_field(bits, tile, vx, vy)
    land = None
    la = _smooth(0.47, 0.53, f)
    if float(la.max()) > 0.01:
        name = ("wet_rock_world.jpg" if grassy == "rock"
                else "grass_world.jpg" if grassy else "dirt_world.jpg")
        tex = _wrap_texture(name, _GRASS_PERIOD, tile)
        if tex is not None:
            ox, oy = (int(vx) % _GRASS_PERIOD) * tile, (int(vy) % _GRASS_PERIOD) * tile
            land = tex.subsurface(pygame.Rect(ox, oy, tile, tile)).convert_alpha()
            al = pygame.surfarray.pixels_alpha(land)
            al[:, :] = (la * 255).astype(np.uint8)
            del al
    out = (land, _fx_surface(f, tile, rock=(grassy == "rock")))
    if len(_SHORE) > 3000:
        _SHORE.clear()
    _SHORE[key] = out
    return out


def _shore_land_layers(bits, tile, vx, vy):
    key = (bits, tile, int(vx), int(vy))
    if key in _SHORE_LAND:
        return _SHORE_LAND[key]
    f = shore_field(bits, tile, vx, vy)
    wa = 1.0 - _smooth(0.47, 0.53, f)
    out = None
    if float(wa.max()) > 0.01:
        mask = pygame.Surface((tile, tile), pygame.SRCALPHA)
        mask.fill((255, 255, 255, 255))
        al = pygame.surfarray.pixels_alpha(mask)
        al[:, :] = (wa * 255).astype(np.uint8)
        del al
        out = (mask, _fx_surface(f, tile))
    if len(_SHORE_LAND) > 3000:
        _SHORE_LAND.clear()
    _SHORE_LAND[key] = out
    return out


def draw_shore_land(screen, rect, wx, wy, t, client=None):
    """Round a land tile's corner where water wraps around it. True if drawn."""
    tile = rect.w
    if client is None or tile <= 0 or rect.h != tile or not getattr(client, "tiles", None):
        return False
    vx, vy = _view_xy(client, wx, wy)
    # Cheap reject: no water among the 8 neighbours.
    if not _view_mask(client, vx, vy, lambda x, y: not _is_land(client, x, y)):
        return False
    bits = _shore_bits(client, vx, vy)
    layers = _shore_land_layers(bits, tile, vx, vy)
    if layers is None:
        return False
    mask, fx = layers
    tex = _wrap_texture("water_world.jpg", _WATER_PERIOD, tile)
    if tex is None:
        return False
    span = _WATER_PERIOD * tile
    drift = t * tile * 0.10
    ox = int((int(vx) % _WATER_PERIOD) * tile + drift) % span
    oy = int((int(vy) % _WATER_PERIOD) * tile + drift * 0.4) % span
    water = pygame.Surface((tile, tile), pygame.SRCALPHA)
    water.blit(tex, (0, 0), pygame.Rect(ox, oy, tile, tile))
    water.blit(mask, (0, 0), special_flags=pygame.BLEND_RGBA_MULT)
    screen.blit(water, rect.topleft)
    if fx is not None:
        screen.blit(fx, rect.topleft)
    return True
