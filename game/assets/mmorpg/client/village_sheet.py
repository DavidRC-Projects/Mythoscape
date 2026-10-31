"""Village ground as one painted sheet (31 Oct 2026, round 4).

The village's grass plots and dirt roads are composited once into a big
world-aligned image: a blurred, noise-wobbled "meadow" field decides where
grass meets dirt (large-radius corners, wavy long edges, varying road width,
worn verges), and the dirt is painted procedurally (multi-octave colour noise,
detail from the old dirt photo in two rotations so its diagonal stripe cancels
out, wheel ruts that follow the road curves, scattered small stones).
Visual only: the tile grid and walkability are unchanged. Road tile cores always
stay dirt and grass tile centres always stay grass, so the map still reads true.
Any failure returns False and the old per-tile painter draws instead.
"""
import os

import numpy as np
import pygame

import world_map as wm

P = 32                       # sheet pixels per tile
REGION = (0, 0, 104, 56)     # tiles x0, y0, x1, y1 (exclusive)
_S = {}


def _smooth(e0, e1, x):
    t = np.clip((x - e0) / (e1 - e0), 0.0, 1.0)
    return t * t * (3 - 2 * t)


def _noise(rng, shape, sigma):
    from scipy.ndimage import gaussian_filter
    n = gaussian_filter(rng.standard_normal(shape).astype(np.float32), sigma, mode="wrap")
    return n / max(1e-6, float(np.abs(n).max()))


def _covers(client, wx, wy):
    x0, y0, x1, y1 = REGION
    if not (x0 <= wx < x1 and y0 <= wy < y1):
        return False
    if int(getattr(client, "camera_yaw", 0)) % 4 or getattr(client, "dungeon", None):
        return False
    try:
        return wm.get_zone(wx, wy) == "village"
    except Exception:
        return False


def _build(client):
    from scipy.ndimage import gaussian_filter, zoom
    import village_ground as vg
    x0, y0, x1, y1 = REGION
    W, H = x1 - x0, y1 - y0
    tiles = client.tiles
    path = np.zeros((W, H), np.float32)          # [x, y]
    for y in range(H):
        for x in range(W):
            wx, wy = x0 + x, y0 + y
            if 0 <= wy < len(tiles) and 0 <= wx < len(tiles[0]) and tiles[wy][wx] == wm.PATH:
                path[x, y] = 1.0
    rng = np.random.default_rng(5150)
    big = np.kron(1.0 - path, np.ones((P, P), np.float32))            # 1 = meadow
    f = gaussian_filter(big, P * 0.85, mode="nearest")                 # big rounded corners
    f += 0.20 * _noise(rng, f.shape, P * 2.2) + 0.07 * _noise(rng, f.shape, P * 0.45)
    # keep the map honest: road cores dirt, grass centres grass
    yy, xx = np.meshgrid(np.arange(H * P), np.arange(W * P))
    fx, fy = (xx % P) / P, (yy % P) / P
    core = (np.abs(fx - 0.5) < 0.30) & (np.abs(fy - 0.5) < 0.30)
    centre = (np.abs(fx - 0.5) < 0.18) & (np.abs(fy - 0.5) < 0.18)
    pathpx = np.kron(path, np.ones((P, P), np.float32)) > 0.5
    f = np.where(pathpx & core, np.minimum(f, 0.30), f)
    f = np.where(~pathpx & centre, np.maximum(f, 0.72), f)
    g = _smooth(0.44, 0.56, f)                                         # grass alpha

    # --- dirt: procedural colour + rotated photo detail, ruts, stones
    lo = _noise(rng, f.shape, P * 1.6)
    mid = _noise(rng, f.shape, P * 0.25)
    fine = rng.standard_normal(f.shape).astype(np.float32) * 0.5
    base = np.stack([np.full(f.shape, 128.0), np.full(f.shape, 101.0), np.full(f.shape, 72.0)], -1)
    shade = 1.0 + 0.10 * lo + 0.07 * mid
    dirt = base * shade[..., None] + (fine * 9.0)[..., None]
    photo = pygame.image.load(os.path.join(vg._DIR, "dirt_world.jpg")).convert()
    per = 24 * P
    photo = pygame.transform.smoothscale(photo, (per, per))
    pa = pygame.surfarray.array3d(photo).astype(np.float32)
    pb = np.rot90(pa, 1, (0, 1))
    def tile_to(arr):
        reps = (W * P // per + 2, H * P // per + 2, 1)
        return np.tile(arr, reps)[: W * P, : H * P]
    detail = 0.5 * tile_to(pa) + 0.5 * tile_to(pb)
    detail = detail - detail.mean(axis=(0, 1))
    dirt += 0.45 * detail
    # wheel ruts: contour lines deep inside the road field follow every curve
    rut = np.exp(-((f - 0.15) / 0.018) ** 2) * (1.0 - g)
    rut *= 0.6 + 0.4 * np.clip(_noise(rng, f.shape, P * 0.8) + 0.5, 0, 1)
    dirt *= (1.0 - 0.13 * rut)[..., None]
    # pebbles
    m = rng.random(f.shape) < 0.0007
    peb = gaussian_filter(m.astype(np.float32), 1.1) * 18
    dirt += (np.clip(peb, 0, 1)[..., None] * np.array([34.0, 28.0, 20.0]))
    dirt = np.clip(dirt, 0, 255)

    # --- grass: the shared meadow sheet (world aligned, same as outside the village)
    gt = vg._grass_texture(P, season=None)
    gper = vg._GRASS_PERIOD * P
    ga = pygame.surfarray.array3d(gt).astype(np.float32)[:gper, :gper]
    reps = (W * P // gper + 2, H * P // gper + 2, 1)
    off = ((x0 % vg._GRASS_PERIOD) * P, (y0 % vg._GRASS_PERIOD) * P)
    grass = np.tile(ga, reps)[off[0]: off[0] + W * P, off[1]: off[1] + H * P]
    # worn verge: trampled grass a short way past the edge
    worn = _smooth(0.50, 0.58, f) * (1.0 - _smooth(0.60, 0.82, f)) * np.clip(0.6 + 0.6 * mid, 0, 1)
    grass = grass * (1 - 0.45 * worn[..., None]) + dirt * (0.45 * worn[..., None])
    # gentle light/dark meadow variation on the big plots
    grass *= (1.0 + 0.06 * lo)[..., None]
    out = grass * g[..., None] + dirt * (1.0 - g[..., None])
    surf = pygame.Surface((W * P, H * P))
    pygame.surfarray.blit_array(surf, np.clip(out, 0, 255).astype(np.uint8))
    return surf.convert()


def draw(screen, rect, wx, wy, client):
    if client is None or not getattr(client, "tiles", None) or not _covers(client, wx, wy):
        return False
    tile = rect.w
    try:
        if _S.get("grid") is not client.tiles:
            _S.clear()
            _S["grid"] = client.tiles
            _S["base"] = _build(client)
        if _S.get("tile") != tile:
            b = _S["base"]
            _S["scaled"] = b if tile == P else pygame.transform.smoothscale(
                b, (b.get_width() * tile // P, b.get_height() * tile // P))
            _S["tile"] = tile
        x0, y0 = REGION[:2]
        screen.blit(_S["scaled"], rect.topleft, pygame.Rect((wx - x0) * tile, (wy - y0) * tile, tile, tile))
        return True
    except Exception as exc:
        if not _S.get("warned"):
            print("[village_sheet]", exc)
            _S["warned"] = True
        _S["grid"] = client.tiles
        _S.setdefault("base", None)
        return False
