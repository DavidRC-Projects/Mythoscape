"""Load and chroma-key painted sprites for the isolated M3 renderer."""

from __future__ import annotations

from pathlib import Path
from typing import Dict, Optional, Tuple

import pygame

SPRITE_DIR = Path(__file__).resolve().parent.parent / "assets" / "sprites"

_keyed: Dict[str, pygame.Surface] = {}
_scaled: Dict[Tuple[str, int, int], pygame.Surface] = {}


def _chroma_key(src: pygame.Surface) -> pygame.Surface:
    """Remove magenta / painted-pink studio backgrounds and crop to alpha bounds."""
    rgb = pygame.surfarray.array3d(src).astype("int16")  # x, y, 3
    r, g, b = rgb[:, :, 0], rgb[:, :, 1], rgb[:, :, 2]
    # Generator "magenta" landed as hot pink ~ (224, 5, 105), not #FF00FF.
    studio = (r >= 148) & (g <= 95) & (b >= 38) & ((r - g) >= 65)
    true_magenta = (r >= 165) & (g <= 115) & (b >= 145)
    # Edge-similar to the actual corner colour (handles painted rose backdrops).
    ref = rgb[4, 4]
    dist = abs(r - int(ref[0])) + abs(g - int(ref[1])) + abs(b - int(ref[2]))
    near_corner = (dist <= 95) & (g <= 110) & ((r - g) >= 50)
    mask = studio | true_magenta | near_corner

    out = src.convert_alpha()
    alpha = pygame.surfarray.pixels_alpha(out)
    alpha[mask] = 0
    near = (~mask) & (r >= 140) & (g <= 100) & ((r - g) >= 50) & (b >= 40)
    alpha[near] = 50
    del alpha

    # Crop to opaque bounds
    am = pygame.surfarray.array_alpha(out)
    ys = (am.max(axis=0) > 18).nonzero()[0]
    xs = (am.max(axis=1) > 18).nonzero()[0]
    if len(xs) == 0 or len(ys) == 0:
        return out
    x0, x1 = int(xs[0]), int(xs[-1]) + 1
    y0, y1 = int(ys[0]), int(ys[-1]) + 1
    cropped = out.subsurface(pygame.Rect(x0, y0, x1 - x0, y1 - y0)).copy()
    return cropped


def load(name: str) -> pygame.Surface:
    if name not in _keyed:
        path = SPRITE_DIR / f"{name}.png"
        if not path.is_file():
            path = SPRITE_DIR / f"{name}.jpg"
        if not path.is_file():
            raise FileNotFoundError(name)
        raw = pygame.image.load(str(path))
        ground = {"grass", "court", "water", "road", "grass_fine", "road_fine",
                  "court_fine", "planks", "keep_floor", "wall_top", "parapet_ns"}
        if name in ground:
            _keyed[name] = raw.convert()
        elif name == "keep":
            _keyed[name] = _erode_fringe(_strip_studio_pink(_chroma_key(raw)))
        elif name in {"postern_west", "postern"}:
            _keyed[name] = _erode_fringe(_strip_studio_pink(_chroma_key(raw)))
        else:
            _keyed[name] = fade_foot(_chroma_key(raw), 0.045)
        if name == "player_e" and "player_e" not in _keyed:
            pass
    return _keyed[name]


def load_player_east() -> pygame.Surface:
    if "player_e" not in _keyed:
        _keyed["player_e"] = pygame.transform.flip(load("player_w"), True, False)
    return _keyed["player_e"]


def load_postern_east() -> pygame.Surface:
    if "postern_e" not in _keyed:
        _keyed["postern_e"] = pygame.transform.flip(load("postern_west"), True, False)
    return _keyed["postern_e"]


def scaled(name: str, w: int, h: int) -> pygame.Surface:
    w, h = max(1, int(w)), max(1, int(h))
    key = (name, w, h)
    if key not in _scaled:
        if name == "player_e":
            src = load_player_east()
        elif name == "postern_e":
            src = load_postern_east()
        else:
            src = load(name)
        _scaled[key] = pygame.transform.smoothscale(src, (w, h))
    return _scaled[key]


def tint(src: pygame.Surface, rgb: Tuple[int, int, int], alpha: int = 150) -> pygame.Surface:
    out = src.copy()
    veil = pygame.Surface(out.get_size(), pygame.SRCALPHA)
    veil.fill((*rgb, 90))
    out.blit(veil, (0, 0), special_flags=pygame.BLEND_RGBA_ADD)
    out.set_alpha(alpha)
    return out


def warmup() -> None:
    """Decode every gameplay sprite once (metrics-friendly)."""
    for name in (
        "player_s", "player_w", "player_n", "ram", "trebuchet", "siege_tower",
        "ladder", "wall_south", "tower", "gatehouse", "gate_open", "keep",
        "tree", "postern", "postern_west", "bush", "tent", "rock", "grass_fine", "court_fine",
        "road_fine", "planks", "water", "keep_floor", "wall_top", "parapet_ns",
    ):
        load(name)
    load_player_east()
    load_postern_east()


def _is_studio_pink(r, g, b) -> bool:
    return (int(r) >= 140 and int(g) <= 115 and (int(r) - int(g)) >= 48 and int(b) >= 35)


def _fill_down_foot(src: pygame.Surface) -> pygame.Surface:
    """Extend each opaque column of a 3/4 building down to its baseline so
    courtyard tiles do not show through as a rectangular bite under the keep."""
    out = src.convert_alpha()
    rgb = pygame.surfarray.pixels3d(out)
    alpha = pygame.surfarray.pixels_alpha(out)
    h = out.get_height()
    w = out.get_width()
    stone = (62, 56, 50)
    for x in range(w):
        opaque = (alpha[x] > 40).nonzero()[0]
        if len(opaque) == 0:
            continue
        y_last = int(opaque.max())
        color = None
        for y in range(y_last, -1, -1):
            if alpha[x, y] < 80:
                continue
            r, g, b = (int(rgb[x, y, 0]), int(rgb[x, y, 1]), int(rgb[x, y, 2]))
            if _is_studio_pink(r, g, b):
                continue
            color = (r, g, b)
            break
        if color is None:
            color = stone
        if y_last >= h - 1:
            continue
        for y in range(y_last + 1, h):
            fade = (y - y_last) / max(1, h - y_last)
            rgb[x, y, 0] = int(color[0] * (1.0 - 0.12 * fade))
            rgb[x, y, 1] = int(color[1] * (1.0 - 0.12 * fade))
            rgb[x, y, 2] = int(color[2] * (1.0 - 0.12 * fade))
            alpha[x, y] = 240
    del rgb, alpha
    return out


def _strip_studio_pink(src: pygame.Surface) -> pygame.Surface:
    out = src.convert_alpha()
    rgb = pygame.surfarray.pixels3d(out)
    alpha = pygame.surfarray.pixels_alpha(out)
    r, g, b = rgb[:, :, 0], rgb[:, :, 1], rgb[:, :, 2]
    mask = (r >= 140) & (g <= 115) & ((r.astype("int16") - g.astype("int16")) >= 48) & (b >= 35)
    alpha[mask] = 0
    del rgb, alpha
    return out


def _erode_fringe(src: pygame.Surface) -> pygame.Surface:
    """Eat a 1px halo of leftover studio colour along transparent edges."""
    import numpy as np
    out = src.convert_alpha()
    rgb = pygame.surfarray.pixels3d(out)
    alpha = pygame.surfarray.pixels_alpha(out)
    a = alpha.astype("int16")
    # transparent neighbor
    neigh = np.minimum.reduce([
        np.pad(a, ((1, 0), (0, 0)), constant_values=0)[:-1, :],
        np.pad(a, ((0, 1), (0, 0)), constant_values=0)[1:, :],
        np.pad(a, ((0, 0), (1, 0)), constant_values=0)[:, :-1],
        np.pad(a, ((0, 0), (0, 1)), constant_values=0)[:, 1:],
    ])
    r, g, b = rgb[:, :, 0], rgb[:, :, 1], rgb[:, :, 2]
    fringe = (a > 20) & (neigh < 30) & ((r.astype("int16") - g.astype("int16") >= 35) | (r >= 160))
    alpha[fringe] = 0
    del rgb, alpha
    return out


def fade_foot(src: pygame.Surface, frac: float = 0.04) -> pygame.Surface:



    """Soften the bottom of a keyed sprite so it meets the ground without a hard card edge."""
    out = src.convert_alpha()
    h = out.get_height()
    band = max(2, int(h * frac))
    alpha = pygame.surfarray.pixels_alpha(out)
    for i in range(band):
        # alpha columns: surfarray x,y ; y=0 is top
        y = h - 1 - i
        fade = int(255 * (i + 1) / (band + 1))
        col = alpha[:, y]
        alpha[:, y] = (col.astype("int16") * fade // 255).astype("uint8")
    del alpha
    return out


def clear_caches() -> None:
    _keyed.clear()
    _scaled.clear()
