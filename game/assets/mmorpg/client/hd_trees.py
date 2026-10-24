"""Painted HD trees and stumps.

Six woodcutting trees share one look per type, drawn from painted sprites in
assets/hd_trees. A chopped tree (tree tile with no live resource) shows a
stump until it grows back. Footprint and collision are the server's tile and
are not changed here; returns False when the art is missing so the old
procedural tree still draws.
"""
from __future__ import annotations

import os

import pygame

_DIR = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", "assets", "hd_trees"))
TREE_TYPES = ("tree", "oak_tree", "willow_tree", "maple_tree", "yew_tree", "magic_tree")
# Height in tiles; bigger tiers stand taller, as before.
_HEIGHT = {"tree": 4.5, "oak_tree": 4.9, "willow_tree": 4.7, "maple_tree": 5.0,
           "yew_tree": 5.3, "magic_tree": 5.5, "stump": 1.25}
_RAW = {}
_SCALED = {}
_SHADOW = {}


def _raw(name):
    if name not in _RAW:
        path = os.path.join(_DIR, name + ".png")
        try:
            _RAW[name] = pygame.image.load(path).convert_alpha() if os.path.isfile(path) else None
        except pygame.error:
            _RAW[name] = None
    return _RAW[name]


def ready():
    return all(_raw(n) is not None for n in TREE_TYPES + ("stump",))


def _variant(x, y):
    h = (int(x) * 73856093) ^ (int(y) * 19349663)
    return (h ^ (h >> 11)) & 0xFF


def _sprite(name, tile, flip, size_q, alpha):
    key = (name, tile, flip, size_q, alpha)
    s = _SCALED.get(key)
    if s is not None:
        return s
    raw = _raw(name)
    if raw is None:
        return None
    h = max(8, int(tile * _HEIGHT[name] * (0.92 + 0.04 * size_q)))
    w = max(4, round(raw.get_width() * h / raw.get_height()))
    s = pygame.transform.smoothscale(raw, (w, h))
    if flip:
        s = pygame.transform.flip(s, True, False)
    if alpha < 255:
        s = s.copy()
        s.set_alpha(alpha)
    if len(_SCALED) > 400:
        _SCALED.clear()
    _SCALED[key] = s
    return s


def _shadow(w, h):
    key = (w, h)
    s = _SHADOW.get(key)
    if s is None:
        s = pygame.Surface((w, h), pygame.SRCALPHA)
        for i in range(6):
            f = 1 - i / 6
            r = pygame.Rect(0, 0, int(w * f), int(h * f))
            r.center = (w // 2, h // 2)
            pygame.draw.ellipse(s, (10, 22, 8, 22), r)
        _SHADOW[key] = s
    return s


def draw(screen, name, cx, cy, tile, wx=0, wy=0, alpha=255):
    """Draw tree/stump `name` standing on tile centre (cx, cy)."""
    if not ready():
        return False
    v = _variant(wx, wy)
    flip = bool(v & 1) and name != "stump"
    size_q = (v >> 1) % 5  # 5 size steps, +-8%
    a = 255 if alpha >= 248 else max(55, min(240, int(alpha)))
    img = _sprite(name, tile, flip, size_q, a)
    if img is None:
        return False
    feet = cy + int(tile * (0.36 if name != "stump" else 0.30))
    sw = int(img.get_width() * (0.62 if name != "stump" else 0.95))
    sh = int(tile * (0.85 if name != "stump" else 0.4))
    screen.blit(_shadow(sw, sh), (cx - sw // 2 + int(tile * 0.12), feet - sh // 2))
    screen.blit(img, (cx - img.get_width() // 2, feet - img.get_height()))
    return True
