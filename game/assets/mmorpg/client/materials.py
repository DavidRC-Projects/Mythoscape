"""Tileable ground materials: meadow turf, worn earth, and the blend.

Why materials instead of per-tile drawing
-----------------------------------------
Painting detail with pygame primitives per tile is the wrong level of detail:
32 px is too small to hold blades or pebbles that survive scaling, and anything
placed per tile forms a lattice the eye reads as wallpaper.

So the detail lives in two large, seamless 256 px textures generated once:

* ``meadow()``  — dense turf: layered value noise, clumped blades on a jittered
  grid, clover, a little dry straw, occasional thin patches showing soil.
* ``earth()``   — compacted lane: grain, two wheel ruts, embedded pebbles,
  scuffs and a worn crown.

At runtime each tile chooses a world-aligned sub-rectangle of each material and
blends them with the lane coverage field. Because the textures are seamless and
sampled by world position, the ground never tiles visibly and never has a seam.
"""
from __future__ import annotations

import math

import numpy as np
import pygame

SIZE = 256
_CACHE = {}
_PERIOD = 8          # lattice period, in texture pixels, for tileable noise


# ---------------------------------------------------------------------------
# Tileable noise
# ---------------------------------------------------------------------------

def _periodic_noise(n, cells, seed):
    """Seamless value noise on an n x n grid, `cells` lattice cells per side."""
    rng = np.random.default_rng(seed)
    lat = rng.random((cells + 1, cells + 1)).astype(np.float32)
    # Wrap the last row/column onto the first so the tile joins itself.
    lat[cells, :] = lat[0, :]
    lat[:, cells] = lat[:, 0]
    ys = np.linspace(0, cells, n, endpoint=False, dtype=np.float32)
    xs = np.linspace(0, cells, n, endpoint=False, dtype=np.float32)
    x0 = np.floor(xs).astype(int)
    y0 = np.floor(ys).astype(int)
    fx = xs - x0
    fy = ys - y0
    fx = fx * fx * (3 - 2 * fx)
    fy = fy * fy * (3 - 2 * fy)
    a = lat[np.ix_(y0, x0)]
    b = lat[np.ix_(y0, x0 + 1)]
    c = lat[np.ix_(y0 + 1, x0)]
    d = lat[np.ix_(y0 + 1, x0 + 1)]
    top = a + (b - a) * fx[None, :]
    bot = c + (d - c) * fx[None, :]
    return top + (bot - top) * fy[:, None]


def _fbm(n, base_cells, octaves, seed, persistence=0.5):
    total = np.zeros((n, n), np.float32)
    amp, norm, cells = 1.0, 0.0, base_cells
    for o in range(octaves):
        total += _periodic_noise(n, cells, seed + o * 131) * amp
        norm += amp
        amp *= persistence
        cells *= 2
    return total / norm


def _tile_smooth(arr, radius):
    """Box-blur that wraps at the edges, so the result stays tileable."""
    if radius <= 0:
        return arr
    k = radius * 2 + 1
    padded = np.pad(arr, radius, mode="wrap")
    out = np.zeros_like(arr)
    for dy in range(k):
        for dx in range(k):
            out += padded[dy:dy + arr.shape[0], dx:dx + arr.shape[1]]
    return out / (k * k)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _rgb(base, delta):
    """base (r,g,b) plus a float delta array -> uint8 image array (h,w,3)."""
    out = np.empty(delta.shape + (3,), dtype=np.float32)
    for i in range(3):
        out[..., i] = base[i] + delta
    return np.clip(out, 0, 255).astype(np.uint8)


def _to_surface(arr, alpha=None):
    """(h, w, 3) uint8 array -> pygame surface, oriented x=w, y=h."""
    if alpha is None:
        surf = pygame.Surface((arr.shape[1], arr.shape[0]))
        pygame.surfarray.blit_array(surf, np.transpose(arr, (1, 0, 2)))
        return surf
    surf = pygame.Surface((arr.shape[1], arr.shape[0]), pygame.SRCALPHA)
    rgba = np.dstack([arr, np.clip(alpha, 0, 255).astype(np.uint8)])
    pygame.surfarray.blit_array(surf, np.transpose(rgba, (1, 0, 2)))
    return surf


def _brush(alpha, cx, cy, radius, strength):
    """Add a soft round blob to an alpha/height field, wrapping at the edges."""
    n = alpha.shape[0]
    x0, x1 = int(cx - radius) - 1, int(cx + radius) + 2
    y0, y1 = int(cy - radius) - 1, int(cy + radius) + 2
    if x1 <= x0 or y1 <= y0:
        return
    ys = np.arange(y0, y1)
    xs = np.arange(x0, x1)
    dx = xs[None, :] - cx
    dy = ys[:, None] - cy
    d2 = (dx * dx + dy * dy) / max(1e-3, radius * radius)
    blob = np.clip(1.0 - d2, 0, 1) ** 1.6 * strength
    ys_w = ys % n
    xs_w = xs % n
    # Accumulate with wrap (np.add.at handles repeated wrapped indices).
    idx = np.ix_(ys_w, xs_w)
    alpha[idx] += blob


# ---------------------------------------------------------------------------
# Materials
# ---------------------------------------------------------------------------

MEADOW_BASE = (62, 84, 48)      # desaturated turf green, not olive
EARTH_BASE = (106, 90, 70)      # cool, dusty earth rather than orange


def meadow():
    """Dense, seamless turf texture."""
    key = "meadow"
    if key in _CACHE:
        return _CACHE[key]
    n = SIZE

    # Broad tonal variation: sunlit and shaded swathes, plus dry straw.
    broad = _fbm(n, 2, 3, 11)
    mid = _fbm(n, 6, 4, 23)
    fine = _fbm(n, 26, 3, 37)
    vfine = _fbm(n, 60, 2, 61)
    dry = np.clip((_fbm(n, 3, 2, 51) - 0.62) * 3.2, 0, 1)
    # Strong broad variation plus fine grain: real turf has large sunlit and
    # shaded patches and looks broken up at pixel scale. A wash with only the
    # mid frequency reads as painted felt. Each octave is stretched to its own
    # full range first, or the amplitudes buy far less contrast than they say.
    def _stretch(a, spread):
        lo, hi = float(a.min()), float(a.max())
        return ((a - lo) / max(1e-6, hi - lo) - 0.5) * spread

    delta = _stretch(broad, 30.0)
    delta = delta + _stretch(mid, 22.0)
    delta = delta + _stretch(fine, 20.0)
    delta = delta + _stretch(vfine, 16.0)
    arr = _rgb(MEADOW_BASE, delta)
    # Dry patches pull toward straw, and lose a little blue.
    straw = np.array([104, 102, 66], np.float32)
    arr = (arr.astype(np.float32) * (1 - dry[..., None] * 0.45)
           + straw * (dry[..., None] * 0.45)).astype(np.uint8)
    # Break the single-hue green: cooler, bluer clumps where the turf is thick
    # and damp, warmer where it is thin. Without this the meadow is one flat
    # green however good the noise is; this is the colour variation that makes
    # a field look like a field.
    damp = np.clip((broad - 0.58) * 3.0, 0, 1)
    warm = np.clip((0.42 - broad) * 3.0, 0, 1)
    cool_rgb = np.array([54, 80, 52], np.float32)
    warm_rgb = np.array([88, 96, 54], np.float32)
    arr = (arr.astype(np.float32)
           * (1 - damp[..., None] * 0.42 - warm[..., None] * 0.34)
           + cool_rgb * (damp[..., None] * 0.42)
           + warm_rgb * (warm[..., None] * 0.34)).astype(np.uint8)

    surf = pygame.Surface((n, n))
    pygame.surfarray.blit_array(surf, np.transpose(arr, (1, 0, 2)))

    # --- blades ---------------------------------------------------------
    # Jittered lattice of clumps: exactly one clump per 16-px cell, offset by a
    # coprime amount so there is no row/column alignment.
    rng = np.random.default_rng(7)
    cell = 7
    for gy in range(0, n, cell):
        for gx in range(0, n, cell):
            if rng.random() > 0.55:
                continue
            cx = gx + rng.random() * cell
            cy = gy + rng.random() * cell
            blades = int(6 + rng.random() * 7)
            # Not every clump is the same height: a mix of short turf and the
            # odd taller tussock is what stops the texture reading as felt.
            tall = rng.random()
            for _ in range(blades):
                bx = cx + (rng.random() - 0.5) * 10
                by = cy + (rng.random() - 0.5) * 6
                h = 3 + tall * 4 + rng.random() * 7
                lean = (rng.random() - 0.5) * (3 + tall * 3)
                # A dark base pixel under each blade, and a second one beside
                # it: turf is dark where blades meet the soil, and that shadow
                # is most of what makes grass look dense.
                hx, hy = int(bx), int(by)
                for dx, dy in ((0, 0), (1, 0), (0, 1)):
                    surf.set_at(((hx + dx) % n, (hy + dy) % n),
                                (max(0, MEADOW_BASE[0] - 30), max(0, MEADOW_BASE[1] - 26),
                                 max(0, MEADOW_BASE[2] - 24)))
                shade = int(-10 + rng.random() * 16)
                col = (max(0, MEADOW_BASE[0] + shade - 2),
                       max(0, MEADOW_BASE[1] + shade + 3),
                       max(0, MEADOW_BASE[2] + shade - 2))
                # 2 px thick at the base tapering to a 1 px tip: a single
                # hairline disappears at gameplay zoom.
                pygame.draw.line(surf, col, (hx, hy), (hx, hy - 1), 1)
                pygame.draw.line(surf, col, (int(bx + lean * 0.5), int(by - h * 0.5)),
                                 (int(bx + lean), int(by - h)), 1)
                if rng.random() < 0.22:
                    lit = (min(255, MEADOW_BASE[0] + 22),
                           min(255, MEADOW_BASE[1] + 28),
                           min(255, MEADOW_BASE[2] + 12))
                    pygame.draw.line(surf, lit, (int(bx + lean * 0.5), int(by - h * 0.45)),
                                     (int(bx + lean), int(by - h)), 1)

    # --- clover ---------------------------------------------------------
    for _ in range(26):
        cx, cy = rng.random() * n, rng.random() * n
        for _k in range(4):
            ox = cx + (rng.random() - 0.5) * 13
            oy = cy + (rng.random() - 0.5) * 10
            r = 1 + int(rng.random() * 2)
            pygame.draw.ellipse(surf, (56, 88, 46),
                                (int(ox - r), int(oy - r * 0.8), r * 2, int(r * 1.6)))
            pygame.draw.ellipse(surf, (68, 104, 56),
                                (int(ox - r * 0.5), int(oy - r * 0.5), r, max(1, int(r * 0.9))))

    # --- a few wildflowers ---------------------------------------------
    flowers = ((206, 196, 150), (188, 170, 200), (200, 188, 140))
    for _ in range(9):
        cx, cy = rng.random() * n, rng.random() * n
        col = flowers[int(rng.random() * len(flowers))]
        pygame.draw.circle(surf, col, (int(cx), int(cy)), 1)
        pygame.draw.circle(surf, (60, 78, 48), (int(cx), int(cy)), 1, 1)

    _CACHE[key] = surf
    return surf


def earth():
    """Compacted, wheel-rutted earth, seamless.

    Everything here is done in float arrays and written in one pass. Ruts are
    wide, soft compressions with grain inside them - not a dark line beside a
    bright line, which is a bevel and reads as moulded plastic. Pebbles are
    close in value to the soil; only a handful, most half-buried.
    """
    key = "earth"
    if key in _CACHE:
        return _CACHE[key]
    n = SIZE

    grain = _fbm(n, 12, 4, 71)
    broad = _fbm(n, 2, 3, 83)
    mid = _fbm(n, 5, 3, 89)
    fine = _fbm(n, 52, 2, 97)
    # Large damp/dry patches, mid-scale clods, then pixel grain. All three are
    # needed: broad alone is a smooth gradient, fine alone is noise.
    #
    # Each band is normalised to its own full range first. Averaged fbm values
    # cluster tightly around 0.5, so multiplying by an amplitude gives far less
    # contrast than the number suggests — that is why the soil came out as a
    # flat brown wash with a standard deviation of about 7 levels.
    def _stretch(a, spread):
        lo, hi = float(a.min()), float(a.max())
        return ((a - lo) / max(1e-6, hi - lo) - 0.5) * spread

    delta = _stretch(broad, 34.0)
    delta = delta + _stretch(mid, 30.0)
    delta = delta + _stretch(grain, 26.0)
    delta = delta + _stretch(fine, 22.0)
    # Per-pixel grit. Value noise cannot go this high-frequency without
    # becoming pure random, so add exactly that: white noise, tileable by
    # construction. This is what makes soil look crumbly instead of smooth.
    _rng_grit = np.random.default_rng(991)
    delta = delta + (_rng_grit.random((n, n)).astype(np.float32) - 0.5) * 26.0
    img = _rgb(EARTH_BASE, delta).astype(np.float32)

    # NO ruts in the material.
    #
    # Ruts used to be baked in as two horizontal bands. That only works on a
    # road running left-right; on a north-south lane, or round a bend, the
    # band becomes a smear across the surface. Ruts belong to the road, not to
    # the texture, so they are painted per pixel at draw time from the lane
    # centre-line field (see ground_paint._ground_colour).
    #
    # What stays is the compaction itself: a broad, very soft darkening so the
    # lane reads as firmer and slightly sunken, independent of direction.
    sink = _tile_smooth(np.clip((_fbm(n, 2, 2, 401) - 0.45) * 1.6, 0, 1), 6)
    img[..., 0] -= sink * 5.0
    img[..., 1] -= sink * 5.0
    img[..., 2] -= sink * 4.0

    img = np.clip(img, 0, 255)
    surf = pygame.Surface((n, n))
    pygame.surfarray.blit_array(surf, np.transpose(img.astype(np.uint8), (1, 0, 2)))

    # --- pebbles --------------------------------------------------------
    rng = np.random.default_rng(31)
    for _ in range(34):
        x, y = int(rng.random() * n), int(rng.random() * n)
        r = 1 + int(rng.random() * 2)
        # Not all stones are alike: a few are pale, most are within a shade or
        # two of the soil, and some are dark. Uniform brightness is what made
        # these read as confetti.
        lift = -6 + int(rng.random() * 18)
        col = (EARTH_BASE[0] + 10 + lift, EARTH_BASE[1] + 9 + lift, EARTH_BASE[2] + 7 + lift)
        pygame.draw.ellipse(surf, (78, 64, 48), (x - r, y + 1, r * 2, max(1, r)))
        pygame.draw.circle(surf, col, (x, y), r)
        if r > 1 and lift > 4:
            # Only the raised stones catch a highlight.
            surf.set_at(((x - 1) % n, (y - 1) % n),
                        (min(255, col[0] + 10), min(255, col[1] + 10), min(255, col[2] + 9)))
    # Coarse grit, barely darker than the earth.
    for _ in range(320):
        x, y = int(rng.random() * n), int(rng.random() * n)
        d = int(rng.random() * 14) - 6
        surf.set_at((x, y), (max(0, EARTH_BASE[0] + d - 4),
                             max(0, EARTH_BASE[1] + d - 4),
                             max(0, EARTH_BASE[2] + d - 3)))

    _CACHE[key] = surf
    return surf


def clear():
    _CACHE.clear()
