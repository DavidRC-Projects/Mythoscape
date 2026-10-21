"""Continuous world-space fields used to paint the overworld ground.

Everything here is a pure function of a world position (float tiles) and the
live path predicate. Nothing is quantised to a tile, which is what keeps the
grass/lane boundary a curve rather than a staircase, and keeps two tiles that
share an edge in agreement along it.
"""
from __future__ import annotations

import math

_GRID_CACHE = {}


def _hash(x, y, salt=0):
    h = (int(x) * 374761393 + int(y) * 668265263 + int(salt) * 2246822519) & 0xFFFFFFFF
    h = ((h ^ (h >> 13)) * 1274126177) & 0xFFFFFFFF
    return (h ^ (h >> 16)) & 0xFFFFFFFF


def rnd(x, y, salt=0):
    return (_hash(x, y, salt) & 0xFFFFFF) / float(0xFFFFFF)


def _fade(t):
    return t * t * (3.0 - 2.0 * t)


def noise(x, y, scale, salt=0):
    """Smooth value noise, ~0..1, continuous everywhere."""
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
# Lane coverage
# ---------------------------------------------------------------------------

# Cached blurred mask per predicate. The blur used to be evaluated per
# *pixel*, which cost ~440 predicate calls and 5 ms per tile: a full screen of
# ground took 4.6 s to appear on login. The mask only depends on which tiles
# are lanes, so it is built once per predicate (and remembered by a cheap
# fingerprint) and then sampled by bilinear lookup.
_BLUR_CACHE = {}
# Radius of each box pass, in tiles. Two passes per axis give an effective
# influence of about 2*radius. At radius 3 that is six tiles either side —
# wider than a lane, so the blur averaged the road into its own shoulders and
# the centre never reached full coverage. Radius 1 (effective ~2) keeps a road
# solid down the middle and still softens the edge across tile boundaries.
BLUR_RADIUS = 1          # in tiles
_BLUR_KEY = [None]


def _fingerprint(is_path, x0, y0, w, h):
    """Cheap content hash of the tile range the blur will read."""
    hsh = 2166136261
    for j in range(y0, y0 + h):
        for i in range(x0, x0 + w):
            hsh = ((hsh ^ (1 if is_path(i, j) else 0)) * 16777619) & 0xFFFFFFFF
    return hsh


def _blurred_mask(is_path, tx0, ty0, tw, th):
    """Lane coverage sampled per tile, blurred by a separable box blur.

    Built over the requested tile range plus a margin, so edge samples read
    real neighbours instead of zeros. Returns (mask, x0, y0).
    """
    import numpy as np
    r = BLUR_RADIUS
    x0, y0 = tx0 - r, ty0 - r
    w, h = tw + r * 2, th + r * 2
    key = (x0, y0, w, h, _fingerprint(is_path, x0, y0, w, h))
    hit = _BLUR_CACHE.get(key)
    if hit is not None:
        return hit[0], x0, y0
    raw = np.zeros((h, w), dtype=np.float32)
    for j in range(h):
        row = raw[j]
        yy = y0 + j
        for i in range(w):
            if is_path(x0 + i, yy):
                row[i] = 1.0
    # Separable box blur, run twice: a 2x box approximates a Gaussian well
    # enough and stays O(n) per axis.
    for _ in range(2):
        raw = _box_blur_axis(raw, r, 1)
        raw = _box_blur_axis(raw, r, 0)
    # Break the boundary up *here*, once per mask, not per sample. The wobble
    # used to be evaluated inside lane_coverage for every lookup, which came to
    # 2.6 million hash calls for a few tiles. Baking it into the cached mask is
    # the same picture for a fraction of the cost.
    import numpy as np
    gx = np.arange(w, dtype=np.float32)[None, :] + x0
    gy = np.arange(h, dtype=np.float32)[:, None] + y0
    wob = (np.sin(gx * 1.7 + gy * 0.9) * 0.5 + np.sin(gx * 0.41 - gy * 1.3) * 0.5) * 0.06
    wob += (np.sin(gx * 7.3 + gy * 5.1) * 0.5) * 0.02
    raw = raw + wob
    if len(_BLUR_CACHE) > 6:
        _BLUR_CACHE.clear()
    _BLUR_CACHE[key] = (raw,)
    return raw, x0, y0


def _box_blur_axis(a, r, axis):
    import numpy as np
    pad = [(0, 0), (0, 0)]
    pad[axis] = (r, r)
    p = np.pad(a, pad, mode="edge")
    c = np.cumsum(p, axis=axis)
    zero = np.zeros_like(np.take(c, [0], axis=axis))
    c = np.concatenate([zero, c], axis=axis)
    n = a.shape[axis]
    hi = np.take(c, np.arange(2 * r + 1, 2 * r + 1 + n), axis=axis)
    lo = np.take(c, np.arange(0, n), axis=axis)
    return (hi - lo) / float(2 * r + 1)


_WARM = {"range": None, "fp": None}
# The mask block lane_coverage() should read: (mask, x0, y0).
_CURRENT = [None]


def prewarm_lane_mask(is_path, tx, ty, block=12):
    """Make sure the blurred mask covers a block around (tx, ty).

    Called once per tile by the ground painter. It rebuilds only when the tile
    falls outside the block already cached (or the tiles changed), so a screen
    of ground costs one blur pass instead of one per tile.
    """
    rng = _WARM["range"]
    if rng and rng[0] <= tx < rng[2] and rng[1] <= ty < rng[3]:
        # Tiles rarely change; only re-key when the local ones might have.
        fp = _fingerprint(is_path, tx - 2, ty - 2, 5, 5)
        if fp == _WARM["fp"]:
            _CURRENT[0] = _WARM["mask"]
            return
    x0 = tx - block
    y0 = ty - block
    size = block * 2 + 1
    mask, mx0, my0 = _blurred_mask(is_path, x0, y0, size, size)
    _WARM["range"] = (x0, y0, x0 + size, y0 + size)
    _WARM["fp"] = _fingerprint(is_path, tx - 2, ty - 2, 5, 5)
    _WARM["mask"] = (mask, mx0, my0)
    _CURRENT[0] = _WARM["mask"]


def _covers(block, bx, by):
    """True when the cached mask has samples on all sides of this tile."""
    if block is None:
        return False
    mask, mx0, my0 = block
    i0, j0 = bx - mx0, by - my0
    if i0 < 0 or j0 < 0:
        return False
    if j0 + 1 >= mask.shape[0] or i0 + 1 >= mask.shape[1]:
        return False
    return True


def lane_coverage(x, y, is_path):
    """0 in meadow .. 1 in the middle of a lane, smoothed at world scale.

    Reads a pre-blurred mask (built once per tile grid) and interpolates, so
    the boundary is continuous across seams without paying for a blur per
    sample.
    """
    bx, by = math.floor(x), math.floor(y)
    # Use the prewarmed block, but only while this sample is actually inside
    # it. Reading a block that does not cover the point returns whatever the
    # array happens to hold there, which shredded the lane into blobs.
    block = _CURRENT[0]
    if block is None or not _covers(block, bx, by):
        prewarm_lane_mask(is_path, bx, by)
        block = _CURRENT[0]
        if block is None or not _covers(block, bx, by):
            prewarm_lane_mask(is_path, bx, by, block=24)
            block = _CURRENT[0]
    mask, mx0, my0 = block
    # Bilinear between the four surrounding tile samples.
    fx, fy = x - bx, y - by
    j0 = by - my0
    i0 = bx - mx0
    m00 = mask[j0, i0]
    m10 = mask[j0, i0 + 1]
    m01 = mask[j0 + 1, i0]
    m11 = mask[j0 + 1, i0 + 1]
    top = m00 + (m10 - m00) * fx
    bot = m01 + (m11 - m01) * fx
    cov = float(top + (bot - top) * fy)
    # Ragged shoulders, then a hard-ish remap: a road edge is a fairly crisp
    # line with grass overhanging it, not a gradient.
    #
    # Three octaves at decreasing amplitude, not two large ones. A single
    # mid-scale wobble displaces the boundary by the same amount everywhere,
    # which turns the road into a row of rounded lobes ("brain coral"). Fine
    # octaves break those lobes into grit-sized irregularity, and as the
    # amplitudes fall geometrically no single scale dominates the silhouette.
    # The wobble must be small next to the distance from "fully road" to
    # "fully meadow". These amplitudes used to sum to +/-0.28 and were then
    # multiplied by 2.9, which could push the middle of a narrow road below
    # zero and shatter it into blobs. Keep it to a shoulder-sized nudge.
    # (The ragged-edge wobble is baked into the cached mask above.)
    cov = (cov - 0.5) * 2.2 + 0.5
    return 0.0 if cov < 0 else (1.0 if cov > 1 else cov)


def lane_direction(x, y, is_path, h=1.2):
    """Angle the lane runs through a point, or None in open meadow.

    Taken from an 8-way probe: perpendicular to the coverage gradient is the
    lane direction. Using a whole-tile-wide step keeps it stable instead of
    flipping per tile.
    """
    c0 = lane_coverage(x, y, is_path)
    if c0 < 0.25:
        return None
    dx = lane_coverage(x + h, y, is_path) - lane_coverage(x - h, y, is_path)
    dy = lane_coverage(x, y + h, is_path) - lane_coverage(x, y - h, is_path)
    if abs(dx) < 1e-4 and abs(dy) < 1e-4:
        return None
    return math.atan2(dx, -dy) % math.pi


# ---------------------------------------------------------------------------
# Worn-track fields
#
# Ruts are painted per pixel from distance fields, not drawn as lines. A line
# has to be started somewhere, and starting one per tile makes a ladder of
# disconnected bars; a distance field is a pure function of position, so the
# track is continuous by construction and both tiles along a seam agree.
# ---------------------------------------------------------------------------

def _lane_normal(x, y, is_path, h=1.0):
    """Unit vector pointing across the lane (toward the nearest shoulder)."""
    dx = lane_coverage(x + h, y, is_path) - lane_coverage(x - h, y, is_path)
    dy = lane_coverage(x, y + h, is_path) - lane_coverage(x, y - h, is_path)
    mag = math.hypot(dx, dy)
    if mag < 1e-5:
        return None
    return dx / mag, dy / mag


def lane_centre_offset(x, y, is_path, reach=2.2, step=0.06):
    """Signed distance from a point to the lane's centre-line, in tiles.

    Walks along the lane normal in both directions until coverage drops below
    the shoulder threshold, then centres the two reach distances. Positive and
    negative are the two sides; the magnitude is how far out from the middle
    the point sits. Returned in the range +/- lane half-width.

    Continuous in world space, so ruts drawn from it run unbroken from tile to
    tile and bend with the road.
    """
    cover = lane_coverage(x, y, is_path)
    if cover < 0.30:
        return None
    normal = _lane_normal(x, y, is_path)
    if normal is None:
        return None
    nx, ny = normal
    left = 0.0
    k = 1
    while k * step <= reach:
        if lane_coverage(x + nx * k * step, y + ny * k * step, is_path) < 0.30:
            left = k * step
            break
        k += 1
    else:
        left = reach
    right = 0.0
    k = 1
    while k * step <= reach:
        if lane_coverage(x - nx * k * step, y - ny * k * step, is_path) < 0.30:
            right = k * step
            break
        k += 1
    else:
        right = reach
    # Position between the two shoulders, -1..1, then back into tiles.
    half = (left + right) * 0.5
    pos = (left - right) * 0.5
    if half < 1e-3:
        return None
    return pos


def rut_field(x, y, is_path):
    """0..1 rut intensity: two troughs, a fifth of the road in from each shoulder."""
    off = lane_centre_offset(x, y, is_path)
    if off is None:
        return 0.0
    # The two wheel tracks sit symmetric about the centre-line.
    track = 0.19
    width = 0.13
    dist = abs(abs(off) - track)
    w = max(0.0, 1.0 - (dist / width) ** 2)
    if w <= 0.0:
        return 0.0
    # Worn unevenly along the length.
    w *= 0.55 + 0.45 * fbm(x, y, 1.3, 3033, 2)
    return max(0.0, min(1.0, w))


def rut_grid(out, wx, wy, size, is_path):
    """Fill `out` (size x size, row=y, col=x) with rut intensity for one tile.

    Vectorised inner loop: the per-pixel Python version cost more than the
    whole rest of the tile. Only rows/columns inside the lane are evaluated.
    """
    import numpy as np
    step = 1.0 / size
    for j in range(size):
        fy = wy + (j + 0.5) * step
        for i in range(size):
            fx = wx + (i + 0.5) * step
            if out[j, i] or lane_coverage(fx, fy, is_path) <= 0.55:
                continue
            off = lane_centre_offset(fx, fy, is_path)
            if off is None:
                continue
            dist = abs(abs(off) - 0.19)
            w = 1.0 - (dist / 0.13) ** 2
            if w <= 0.0:
                continue
            out[j, i] = min(1.0, max(0.0, w * (0.55 + 0.45 * fbm(fx, fy, 1.3, 3033, 2))))
