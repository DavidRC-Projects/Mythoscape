"""Overworld meadow and packed-earth lanes.

The fairy glade keeps its moss and petal tiles. Everywhere else, grass is a
sunlit meadow and roads are worn earth, with the meadow growing over the
road edge. Collision is unchanged.
"""
from __future__ import annotations

import os

import numpy as np
import pygame

import world_map as wm

_DIR = os.path.normpath(os.path.join(
    os.path.dirname(__file__), "..", "assets", "village_ground",
))
_IMAGES = {}
_EDGES = {}
_NOISE = None
_SKIP_GRASS = ("shadow_crypt", "volcano", "dungeon")
_SKIP_PATH = ("shadow_crypt", "volcano", "dungeon", "city")
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
        raw = pygame.transform.smoothscale(raw, (tile, tile))
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


def draw_grass(screen, rect, wx, wy):
    image = _scaled("meadow", variant(wx, wy), rect.w)
    if image is None:
        return False
    screen.blit(image, rect.topleft)
    return True


def draw_path(screen, rect, wx, wy):
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
