"""World-space ground painting for the overworld: meadow, worn lane, and the
blend between them.

Why this exists
---------------
The old meadow/lane tiles were a handful of pre-baked images stamped per tile.
The same variant repeats on a visible grid, the lane edge was a grass copy
pasted on top (so it could only blend *into* the tile it sat on), and every
tile re-stamped the same rut lines — which is why the paths read as a row of
brown squares.

This module paints from continuous world-space fields instead:

* Every colour, mottle and the grass/path boundary comes from smooth value
  noise in *world* coordinates, so neighbouring tiles agree along their shared
  edge. No seams, no tile grid.
* The lane is a soft signed-distance band: compacted crown, darker shoulders,
  gravel that spills into the meadow, grass blades that grow into the lane.
* Lane features (ruts, pebbles, footprints) are placed from world hashes, not
  per-tile seeds, so they cross tile borders and never line up in rows.
* A relief pass (light from the upper left) gives the ground some volume.

Anything that is not a lane (water, trees, buildings) keeps its own renderer.
The fairy glade never reaches here — it keeps its own painter.
"""
from __future__ import annotations

import math

import numpy as np
import pygame

import ground_fields as gf

_CACHE = {}
_CACHE_MAX = 1600
_GRID = 4          # one colour sample per 4 screen px


# ---------------------------------------------------------------------------
# Hash + noise
# ---------------------------------------------------------------------------

def _hash(x, y, salt=0):
    h = (int(x) * 374761393 + int(y) * 668265263 + int(salt) * 2246822519) & 0xFFFFFFFF
    h = ((h ^ (h >> 13)) * 1274126177) & 0xFFFFFFFF
    return (h ^ (h >> 16)) & 0xFFFFFFFF


def rnd(x, y, salt=0):
    return (_hash(x, y, salt) & 0xFFFFFF) / float(0xFFFFFF)


def _fade(t):
    return t * t * (3.0 - 2.0 * t)


def noise(x, y, scale, salt=0):
    """Smooth value noise, ~0..1. Continuous across cells, so seams vanish."""
    fx, fy = x / scale, y / scale
    x0, y0 = math.floor(fx), math.floor(fy)
    tx, ty = _fade(fx - x0), _fade(fy - y0)
    a = rnd(x0, y0, salt)
    b = rnd(x0 + 1, y0, salt)
    c = rnd(x0, y0 + 1, salt)
    d = rnd(x0 + 1, y0 + 1, salt)
    top = a + (b - a) * tx
    bot = c + (d - c) * tx
    return top + (bot - top) * ty


def fbm(x, y, scale, salt=0, octaves=2):
    total, amp, norm, s = 0.0, 1.0, 0.0, scale
    for o in range(octaves):
        total += noise(x, y, s, salt + o * 101) * amp
        norm += amp
        amp *= 0.5
        s *= 0.5
    return total / norm


# ---------------------------------------------------------------------------
# Palettes — muted and slightly cool so nothing looks like plastic.
# ---------------------------------------------------------------------------
GRASS_A = (78, 101, 53)
GRASS_B = (62, 86, 48)
GRASS_DRY = (114, 114, 70)
GRASS_DEEP = (43, 62, 35)
GRASS_LIT = (139, 160, 82)
CLOVER = (56, 90, 47)
SOIL = (104, 84, 62)
SOIL_LIT = (139, 116, 86)
SOIL_DARK = (70, 56, 42)
GRAVEL = (138, 132, 118)
FLOWER = ((231, 226, 188), (208, 178, 200), (226, 204, 150), (188, 202, 226))

BAND = 0.9   # width (tiles) of the meadow/lane blend band


def _c(v):
    return 0 if v < 0 else (255 if v > 255 else int(v))


def mix(a, b, t):
    if t <= 0:
        return a
    if t >= 1:
        return b
    return (int(a[0] + (b[0] - a[0]) * t),
            int(a[1] + (b[1] - a[1]) * t),
            int(a[2] + (b[2] - a[2]) * t))


def shade(col, d):
    return (_c(col[0] + d), _c(col[1] + d), _c(col[2] + d))


def _clamp01(v):
    return 0.0 if v < 0 else (1.0 if v > 1 else v)


# ---------------------------------------------------------------------------
# Lane field — a soft signed distance, wobbled by noise.
# ---------------------------------------------------------------------------

_EDGE = {}   # tile -> nearest lane/meadow boundary point, or None


def _nearest_edge(cx, cy, is_path, reach=3):
    """Nearest boundary point (world coords) between lane and meadow.

    The search runs on a fixed quarter-tile lattice around the *tile*, not a
    stencil relative to each query. Two samples on opposite sides of a seam
    therefore find the same point, so the blend lines up across tiles instead
    of stepping at every boundary.
    """
    key = (cx, cy)
    if key in _EDGE:
        return _EDGE[key]
    q = 4
    inside = bool(is_path(cx, cy))
    best_d = 1e9
    acc_x = acc_y = acc_n = 0.0
    for j in range(-reach * q, reach * q + 1):
        sy = cy + (j + 0.5) / q
        iy = int(math.floor(sy))
        for i in range(-reach * q, reach * q + 1):
            sx = cx + (i + 0.5) / q
            ix = int(math.floor(sx))
            if bool(is_path(ix, iy)) == inside:
                continue
            d = (sx - cx) ** 2 + (sy - cy) ** 2
            if d < best_d - 1e-9:
                best_d = d
                acc_x, acc_y, acc_n = sx, sy, 1.0
            elif abs(d - best_d) < 1e-6:
                acc_x += sx
                acc_y += sy
                acc_n += 1.0
    if len(_EDGE) > 60000:
        _EDGE.clear()
    # Mid-lane the north and south edges are equally near: average them, or
    # the chosen side flips tile to tile and the field tears along the grid.
    edge = (acc_x / acc_n, acc_y / acc_n) if acc_n else None
    _EDGE[key] = edge
    return edge


def _path_distance(wx, wy, is_path, reach=2.6):
    """Signed distance in tiles to the lane edge. >0 lane, <0 meadow.

    Measured from the sample point to the tile's shared boundary point — not
    from the tile centre. Using the centre makes the value jump a full tile
    when a query crosses a seam, which is exactly the staircase we are here to
    remove.
    """
    inside = bool(is_path(int(wx), int(wy)))
    qx, qy = int(math.floor(wx)) + 0.5, int(math.floor(wy)) + 0.5
    edge = _nearest_edge(int(wx), int(wy), is_path)
    if edge is None:
        return reach if inside else -reach
    bound_d = math.hypot(edge[0] - qx, edge[1] - qy)
    d = bound_d - math.hypot(wx - qx, wy - qy)
    return max(-reach, min(reach, d))


def lane_coverage(wx, wy, is_path):
    return gf.lane_coverage(wx, wy, is_path)
    """0 = meadow, 1 = lane, smooth in between; the boundary wobbles.

    Positive = inside the lane, so coverage rises with it. The boundary is
    wobbled by two noise scales: a broad meander plus a fine grain that keeps
    it from looking drawn with a ruler.
    """
    d = _path_distance(wx, wy, is_path)
    wobble = (fbm(wx, wy, 1.7, 17, 2) - 0.5) * 0.9 + (noise(wx, wy, 0.45, 23) - 0.5) * 0.35
    return _clamp01(0.5 + (d + wobble) / BAND * 1.5)


# ---------------------------------------------------------------------------
# Per-sample colour (meadow and lane blended by coverage)
# ---------------------------------------------------------------------------

def _ground_colour(wx, wy, is_path, cover=None):
    """Base colour at one world position: meadow, earth, or the mix of both."""
    if cover is None:
        cover = lane_coverage(wx, wy, is_path)
    n_big = fbm(wx, wy, 3.4, 5, 3)
    n_mid = fbm(wx, wy, 1.1, 41, 3)
    n_fine = noise(wx, wy, 0.30, 97)

    # --- meadow ---------------------------------------------------------
    # Three-way blend: cool shaded turf, sunlit turf, and dry straw-green where
    # the soil is thin. The dry patches follow a different noise seed so they
    # cross the shaded patches instead of sitting inside them (which reads as
    # blobs). Value is pushed with a fine term so the surface never looks flat.
    lit = fbm(wx, wy, 1.9, 211, 2)
    grass = mix(GRASS_B, GRASS_A, _clamp01((n_big - 0.40) * 1.5))
    grass = mix(grass, GRASS_DRY, _clamp01((lit - 0.66) * 2.4))
    grass = mix(grass, GRASS_DEEP, _clamp01((0.30 - n_big) * 2.2))
    grass = shade(grass, int((n_mid - 0.5) * 12 + (n_fine - 0.5) * 16))

    # --- lane -----------------------------------------------------------
    # Compacted crown: firmer and lighter down the middle, loose and darker at
    # the shoulders where traffic has pushed it out. Two noise scales give it
    # grain instead of a flat fill; the fine one reads as grit at this size.
    crown = _clamp01((cover - 0.35) / 0.65)
    grain = fbm(wx, wy, 0.55, 88, 3)
    soil = mix(SOIL_DARK, SOIL, _clamp01(0.20 + crown * 1.3))
    soil = mix(soil, SOIL_LIT, _clamp01((grain - 0.52) * 2.0) * (0.35 + crown * 0.55))
    # Damp, darker toward the edge of the track
    soil = shade(soil, int((grain - 0.5) * 22 + (n_fine - 0.5) * 18 - (1.0 - crown) * 9))

    # --- wheel ruts -----------------------------------------------------
    # Painted per pixel from a world-space field, so the two worn tracks run
    # the whole length of the road and follow its bends in any direction.
    # (Baking them into the material tied them to a fixed axis; drawing them
    # as lines made a ladder of bars per tile.)
    if cover > 0.28:
        rut = gf.rut_field(wx, wy, is_path)
        if rut > 0.01:
            soil = shade(soil, -int(rut * 18))
            # The compacted tracks are slightly smoother, so they pick up a
            # touch of the sky: a faint cool lightening, not a bright edge.
            soil = mix(soil, (SOIL_LIT[0], SOIL_LIT[1] + 4, SOIL_LIT[2] + 8), rut * 0.12)

    # --- seam -----------------------------------------------------------
    # Earth creeps into the turf and turf overhangs the earth; a narrow mix
    # keeps the line crisp while the noise above makes it ragged.
    return mix(grass, soil, _clamp01((cover - 0.5) * 2.2 + 0.5))


# ---------------------------------------------------------------------------
# Base tile
# ---------------------------------------------------------------------------

SEAM_BAND = (0.22, 0.78)   # coverage range refined at full pixel resolution
# Material pixels per world tile.
#
# This must be about one screen pixel per material pixel. A 40 px tile sampled
# at 128 px of material steps 3.2 material pixels for every screen pixel, so
# the grit and blades — the detail that makes the surface read as ground — are
# skipped over entirely and only the smooth low-frequency layer survives. That
# is why both textures came out as flat noise. 40 keeps the sampling 1:1 and
# lets a 256 px material cover 6.4 tiles before it repeats.
TEX_PER_TILE = 40.0        # material pixels per world tile (see _paint_tile)


def _paint_tile(size, wx, wy, is_path):
    """Composite the meadow and earth materials through the lane field.

    The heavy detail (blades, clods, grit, pebbles) lives in two seamless
    256 px textures sampled by *world* position, so it repeats only every 8
    tiles and never at a tile boundary. Here we only decide, per pixel, how
    much earth versus turf to show.

    Coverage is evaluated on a half-tile grid and interpolated for speed; the
    narrow seam band is then recomputed exactly so the edge cuts cleanly.
    When neither surface is in the band we can copy whole spans of material
    straight across, which is most of the tile.
    """
    import materials
    tex_m = pygame.surfarray.pixels3d(materials.meadow()).astype(np.int16)
    tex_e = pygame.surfarray.pixels3d(materials.earth()).astype(np.int16)
    th, tw = tex_m.shape[0], tex_m.shape[1]

    out = np.empty((size, size, 3), dtype=np.uint8)
    g = max(2, size // 2)
    step = 1.0 / g
    # Build the blurred lane mask for a generous block containing this tile.
    # Each call rebuilds over a larger range only when the tile falls outside
    # the cached block, so a screen of tiles costs one blur, not 750.
    gf.prewarm_lane_mask(is_path, int(wx), int(wy), 12)
    covs = [[lane_coverage(wx + i * step, wy + j * step, is_path) for i in range(g + 1)]
            for j in range(g + 1)]
    lo, hi = SEAM_BAND
    # World position -> texture pixel.
    #
    # This scale is the whole ballgame. One tile maps to TEX_PER_TILE px of
    # material. Sample the 256 px texture too many times per tile and every
    # blade averages into flat colour by the time it reaches 40 px of screen;
    # sample too few and the material shows its own structure. ~1.4x the tile
    # keeps blades, clods and grit visible at gameplay zoom.
    tex_px = TEX_PER_TILE / size

    # Coverage field, bilinearly upsampled to tile pixels (vectorised).
    cov = np.asarray(covs, dtype=np.float32)
    xs = np.clip(np.arange(size) * (g / size), 0, g - 1e-4)
    ix = xs.astype(np.int32)
    fx = (xs - ix)[:, None]
    iy = np.clip(np.arange(size) * (g / size), 0, g - 1e-4).astype(np.int32)
    fy = (np.arange(size) * (g / size) - iy)[:, None]
    v0 = cov[iy][:, ix] * (1 - fx) + cov[iy][:, ix + 1] * fx
    v1 = cov[iy + 1][:, ix] * (1 - fx) + cov[iy + 1][:, ix + 1] * fx
    cover = (v0 * (1 - fy) + v1 * fy)

    # Sample both materials by world position, wrapping at their edges.
    rows = ((wy * TEX_PER_TILE + np.arange(size) * tex_px).astype(np.int32)) % th
    cols = ((wx * TEX_PER_TILE + np.arange(size) * tex_px).astype(np.int32)) % tw
    tm = tex_m[np.ix_(rows, cols)]
    te = tex_e[np.ix_(rows, cols)]

    # Blend: hard material where clearly one surface, mixed in the band.
    #
    # The transition is deliberately tight. A wide blend reads as an airbrushed
    # smudge; real worn ground has a fairly definite line where the turf ends,
    # with texture breaking it up. 4x makes the edge about half a tile wide
    # across the field's own soft shoulder, which is what the ragged wobble in
    # lane_coverage is for.
    # Break the boundary per pixel. This has to be a function of *world*
    # position, not a per-tile random grid: re-seeding per tile gave every tile
    # the same pattern, so the same pixels were cut on each side of a tile edge
    # and a road running near mid-coverage broke into disconnected patches.
    jx = np.arange(size)[:, None] + wx * size
    jy = np.arange(size)[None, :] + wy * size
    jitter = ((np.sin(jx * 12.9898 + jy * 78.233) * 43758.5453) % 1.0 - 0.5) * 0.30
    # A road has an *edge*. At 2.6 this was a 15 px airbrushed gradient, which
    # read as a brown cloud lying on the field. 7 turns it into a two-to-three
    # pixel transition, with the jitter breaking it into clumps and single
    # blades so it is not a clean vector outline either.
    soft = np.clip((cover - 0.5) * 7.0 + 0.5 + jitter, 0.0, 1.0)
    t = soft[..., None]
    blended = tm + (te - tm) * t

    # Wheel ruts. ground_fields already works these out per pixel (two troughs
    # either side of the lane centre-line) but nothing applied the result, so
    # the road was a flat brown fill however good the field was.
    # Wheel ruts. Evaluated on a coarse grid (one sample per ~5 px) and
    # upsampled: the ruts are a wide, soft feature, so per-pixel evaluation is
    # wasted work — at full resolution it cost 230 ms a tile.
    if float(cover.max()) > 0.5:
        # Rut placement without lane_centre_offset. That routine probes across
        # the lane with dozens of coverage lookups per point; run per pixel it
        # dominated the whole tile (~2,800 coverage calls for 40x40 px). The
        # distance-to-edge transform below gives the same "two tracks either
        # side of the middle" from the coverage array we already have.
        inside = cover > 0.5
        dist = _edge_distance(inside)
        # dist is 0 at the road edge and grows toward the centre. Put a track
        # roughly 40% of the way in from the shoulder, 5 px wide.
        band = np.exp(-((dist - 0.42) ** 2) / (2 * 0.13 ** 2)) * inside
        if band.any():
            small = band.astype(np.float32)
            rc = size
            rut = small * t[:, :, 0]        # fade the ruts out with the earth
            blended = blended - rut[..., None] * np.array([14.0, 12.0, 9.0], np.float32)

    # Contact shadow: a few pixels of darkening just outside the road edge, as
    # if the turf stood slightly proud of the worn surface. This is what
    # separates the road from the field instead of letting it float on top.
    edge = ((soft > 0.02) & (soft < 0.22)).astype(np.float32)
    # Roll *with wrap* so a tile edge does not produce a bright/dark line.
    edge = np.clip(edge + np.roll(edge, 1, 0) * 0.7 + np.roll(edge, -1, 0) * 0.7, 0, 1)
    blended = blended - edge[..., None] * np.array([5.0, 4.0, 3.0], np.float32)
    out[:, :, :] = np.clip(blended, 0, 255).astype(np.uint8)
    surf = pygame.Surface((size, size))
    pygame.surfarray.blit_array(surf, out.transpose(1, 0, 2))
    return surf


# ---------------------------------------------------------------------------
# Detail pass — organic features from world hashes, crossing tile borders
# ---------------------------------------------------------------------------

def _lane_at(fx, fy, is_path):
    return lane_coverage(fx, fy, is_path) > 0.72


TUFTS_PER_TILE_SCALE = 1.35   # world-space jitter grid cell, in tiles


def _tufts_world(surf, size, wx, wy, is_path):
    """Draw grass tufts from a jittered world grid covering this tile.

    Cell size is a little over a tile, and each tuft is jittered inside its
    cell, so spacing is irregular and no two tiles get the same layout. A tuft
    whose root falls just outside the tile is still drawn (partly clipped)
    where it overlaps, which is what makes clumps cross tile edges naturally.
    """
    cell = TUFTS_PER_TILE_SCALE
    gx0 = int(math.floor(wx / cell)) - 1
    gy0 = int(math.floor(wy / cell)) - 1
    for cy in range(gy0, gy0 + int(cell) + 3):
        for cx in range(gx0, gx0 + int(cell) + 3):
            if rnd(cx, cy, 2101) > 0.78:
                continue  # not every cell has a tuft
            rx = cx * cell + rnd(cx, cy, 2102) * cell
            ry = cy * cell + rnd(cx, cy, 2103) * cell
            sx = (rx - wx) * size
            sy = (ry - wy) * size
            if sx < -size * 0.25 or sx > size * 1.25 or sy < -size * 0.25 or sy > size * 1.25:
                continue
            if _lane_at(rx, ry, is_path):
                continue
            span = size * (0.06 + rnd(cx, cy, 2104) * 0.06)
            blades = 8 + int(rnd(cx, cy, 2105) * 6)
            seed = cx * 131 + cy * 17
            for i in range(blades):
                spread = (rnd(seed, i, 1) - 0.5) * span * 2.0
                bx = sx + spread
                by = sy + (rnd(seed, i, 2) - 0.5) * size * 0.03
                h = size * (0.055 + rnd(seed, i, 3) * 0.075)
                lean = spread * 1.5 + (rnd(seed, i, 4) - 0.5) * h * 0.5
                tone = mix(GRASS_DEEP, GRASS_B, 0.45)
                top = (int(bx + lean), int(by - h))
                mid = (int(bx + lean * 0.45), int(by - h * 0.5))
                pygame.draw.line(surf, tone, mid, top, 1)
                pygame.draw.line(surf, shade(tone, -4), (int(bx), int(by)), mid, 1)
                if i % 4 == 0:
                    pygame.draw.line(surf, mix(GRASS_A, GRASS_LIT, 0.35), mid, top, 1)


def _meadow_detail(surf, size, wx, wy, is_path):
    """Blade clumps and ground cover.

    Blades are drawn in tight clumps of three to six, not scattered singly:
    single 1-px lines on a 32-px tile read as coloured noise, whereas a clump
    reads as a tuft of grass. They are kept low-contrast so they add texture
    without the "snow" look.
    """
    # Tufts come from a jittered world-space grid, not from a count per tile.
    # A per-tile count puts the same number of marks in every cell, which is
    # exactly the regular lattice that makes ground look wallpapered. Here the
    # grid is 1.4 tiles wide and each point is jittered within its cell, so
    # spacing varies and a tile only draws the tufts that fall inside it.
    _tufts_world(surf, size, wx, wy, is_path)
    # Clover: one patch every few tiles, low-contrast leaves.
    if rnd(wx, wy, 500) < 0.16:
        cx = rnd(wx, wy, 501) * size
        cy = rnd(wx, wy, 502) * size
        for k in range(5):
            ox = cx + (rnd(wx, wy, 510 + k) - 0.5) * size * 0.40
            oy = cy + (rnd(wx, wy, 520 + k) - 0.5) * size * 0.30
            if _lane_at(wx + ox / size, wy + oy / size, is_path):
                continue
            r = max(1, size // 18)
            pygame.draw.ellipse(surf, mix(CLOVER, GRASS_B, 0.25),
                                (int(ox - r), int(oy - r * 0.7), r * 2, max(2, int(r * 1.4))))
            pygame.draw.ellipse(surf, shade(CLOVER, 12),
                                (int(ox - r * 0.6), int(oy - r * 0.5), r, max(1, int(r * 0.9))))
    # Wildflowers: genuinely sparse (about one patch every eight tiles) and
    # desaturated. At this tile size a 1-px pure-white dot is a glint, not a
    # flower, so they are tinted toward the grass and given a dark centre.
    if rnd(wx, wy, 540) < 0.045:
        fx = rnd(wx, wy, 541) * size
        fy = rnd(wx, wy, 542) * size
        for k in range(2):
            ox = fx + (rnd(wx, wy, 550 + k) - 0.5) * size * 0.14
            oy = fy + (rnd(wx, wy, 560 + k) - 0.5) * size * 0.14
            if _lane_at(wx + ox / size, wy + oy / size, is_path):
                continue
            pc = mix(FLOWER[(int(rnd(wx, wy, 570 + k) * 4)) % 4], GRASS_A, 0.30)
            pygame.draw.circle(surf, pc, (int(ox), int(oy)), max(1, size // 34))
            pygame.draw.circle(surf, shade(pc, -55), (int(ox), int(oy)), 1)
    # Thin turf over bare soil. Small and low-contrast: big dark ellipses at
    # this resolution read as stones lying on the grass, not as worn ground.
    if rnd(wx, wy, 600) < 0.07:
        cx = rnd(wx, wy, 601) * size
        cy = rnd(wx, wy, 602) * size
        if not _lane_at(wx + cx / size, wy + cy / size, is_path):
            rw = size * (0.05 + rnd(wx, wy, 603) * 0.05)
            rh = rw * 0.55
            worn = mix(GRASS_B, SOIL, 0.55)
            pygame.draw.ellipse(surf, worn, (int(cx - rw), int(cy - rh), int(rw * 2), int(rh * 2)))
            pygame.draw.ellipse(surf, shade(worn, 8), (int(cx - rw * 0.6), int(cy - rh * 0.6),
                                                       int(rw * 1.2), int(rh * 1.1)))


def _lane_angle(fx, fy, is_path):
    """Direction the lane runs through a world point, from the coverage gradient.

    The gradient points *across* the lane, so travel runs perpendicular to it.
    Sampled over a whole tile's width, not a fraction of one, or the result is
    noise and the ruts restart on every square.
    """
    h = 1.1
    dx = lane_coverage(fx + h, fy, is_path) - lane_coverage(fx - h, fy, is_path)
    dy = lane_coverage(fx, fy + h, is_path) - lane_coverage(fx, fy - h, is_path)
    if abs(dx) < 1e-3 and abs(dy) < 1e-3:
        return None
    return math.atan2(dx, -dy)


def _lane_detail(surf, size, wx, wy, is_path):
    # Pebbles are sparse and close in value to the earth around them. Bright
    # white dots at this size read as litter, not stone: a pebble is a slightly
    # lighter, slightly warmer patch with one small highlight.
    for i in range(1 + int(rnd(wx, wy, 750) * 2)):
        px_ = rnd(wx, wy, 760 + i) * size
        py_ = rnd(wx, wy, 790 + i) * size
        if not _lane_at(wx + px_ / size, wy + py_ / size, is_path):
            continue
        r = max(1, int(size * (0.010 + rnd(wx, wy, 820 + i) * 0.014)))
        base = mix(SOIL, GRAVEL, 0.35 + rnd(wx, wy, 850 + i) * 0.20)
        pygame.draw.ellipse(surf, shade(SOIL_DARK, 2),
                            (int(px_ - r), int(py_ + r * 0.35), r * 2, max(1, r)))
        pygame.draw.circle(surf, base, (int(px_), int(py_)), r)
        # A single warm highlight on the lit side — never pure white.
        pygame.draw.circle(surf, shade(base, 12), (int(px_ - r * 0.3), int(py_ - r * 0.3)), max(1, r - 1))
    if rnd(wx, wy, 870) < 0.22:
        fx = rnd(wx, wy, 871) * size
        fy = rnd(wx, wy, 872) * size
        ang = rnd(wx, wy, 873) * math.pi
        for side in (-1, 1):
            ox = fx + math.cos(ang) * side * size * 0.075
            oy = fy + math.sin(ang) * side * size * 0.035
            if not _lane_at(wx + ox / size, wy + oy / size, is_path):
                continue
            rect = pygame.Rect(int(ox - size * 0.038), int(oy - size * 0.026),
                               max(2, int(size * 0.076)), max(2, int(size * 0.052)))
            pygame.draw.ellipse(surf, shade(SOIL_DARK, -4), rect)
            pygame.draw.ellipse(surf, shade(SOIL, 10), rect.inflate(-1, -1), 1)
    # Loose grit, very low contrast. Dark specks on pale earth read as flies,
    # so keep them within a few shades of the surrounding soil.
    for i in range(3):
        gx = rnd(wx, wy, 900 + i) * size
        gy = rnd(wx, wy, 920 + i) * size
        if _lane_at(wx + gx / size, wy + gy / size, is_path):
            pygame.draw.circle(surf, mix(SOIL, SOIL_DARK, 0.55), (int(gx), int(gy)), 1)


def _edge_distance(mask):
    """Approximate distance (in tiles) from each inside pixel to the edge.

    Repeated 4-neighbour erosion: each pass peels one pixel off the boundary.
    Cheap and adequate for placing ruts, which are a soft, wide feature.
    """
    m = mask.copy()
    dist = np.zeros(m.shape, dtype=np.float32)
    cur = m.copy()
    for step in range(1, 40):
        nxt = cur.copy()
        nxt[1:, :] &= cur[:-1, :]
        nxt[:-1, :] &= cur[1:, :]
        nxt[:, 1:] &= cur[:, :-1]
        nxt[:, :-1] &= cur[:, 1:]
        if not nxt.any():
            break
        dist += nxt
        cur = nxt
    return dist / max(1.0, dist.max()) if dist.max() > 0 else dist


def _relief(surf, size, wx, wy):
    """Subtle directional light: warm from upper left, cool shadow lower right."""
    light = fbm(wx, wy, 1.2, 950, 2) - 0.5
    strip = max(1, size // 6)
    a = int(max(0.0, light) * 34)
    b = int(max(0.0, -light) * 30)
    if a:
        hi = pygame.Surface((size, strip), pygame.SRCALPHA)
        hi.fill((255, 248, 226, a))
        surf.blit(hi, (0, 0))
    if b:
        lo = pygame.Surface((size, strip), pygame.SRCALPHA)
        lo.fill((10, 16, 12, b))
        surf.blit(lo, (0, size - strip))


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def paint(size, wx, wy, is_path):
    """Finished ground tile for this world tile.

    is_path(x, y) -> bool reads the live tile grid. The blend band uses that
    same stencil on both sides of every seam, so tiles connect.
    """
    is_lane = bool(is_path(int(wx), int(wy)))
    key = (int(wx), int(wy), size, is_lane)
    hit = _CACHE.get(key)
    if hit is not None:
        return hit
    surf = _paint_tile(size, int(wx), int(wy), is_path)
    try:
        (_lane_detail if is_lane else _meadow_detail)(surf, size, int(wx), int(wy), is_path)
    except Exception:
        pass
    _relief(surf, size, int(wx), int(wy))
    if len(_CACHE) > _CACHE_MAX:
        _CACHE.clear()
    _CACHE[key] = surf
    return surf


def clear_cache():
    _CACHE.clear()
    _EDGE.clear()
