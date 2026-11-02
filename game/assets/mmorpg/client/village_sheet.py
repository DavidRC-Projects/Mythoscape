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

The sheet is built off the draw thread. Until it is ready, draw() returns False
and the per-tile painter covers the frame, so entering the world does not freeze.
"""
import os
import threading

import numpy as np
import pygame

import world_map as wm

P = 32                       # sheet pixels per tile
_K = 4                       # low-frequency fields are built at P/_K, then scaled up
REGION = (0, 0, 104, 56)     # tiles x0, y0, x1, y1 (exclusive)
_S = {}
_TEX = {}
_LOCK = threading.Lock()
_JOB = {"gen": 0, "pending": None, "ready": None, "failed": None}


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


def _detail():
    """Photo and meadow arrays. Pygame, so this stays on the draw thread."""
    if "pa" in _TEX:
        return _TEX["pa"], _TEX["pb"], _TEX["grass"], _TEX["gper"]
    import village_ground as vg
    photo = pygame.image.load(os.path.join(vg._DIR, "dirt_world.jpg")).convert()
    per = 24 * P
    photo = pygame.transform.smoothscale(photo, (per, per))
    pa = np.array(pygame.surfarray.array3d(photo), dtype=np.float32, copy=True)
    pb = np.rot90(pa, 1, (0, 1)).copy()
    gt = vg._grass_texture(P, season=None)
    gper = vg._GRASS_PERIOD * P
    ga = np.array(pygame.surfarray.array3d(gt)[:gper, :gper], dtype=np.float32, copy=True)
    _TEX.update(pa=pa, pb=pb, grass=ga, gper=gper)
    return pa, pb, ga, gper


def _path_mask(tiles):
    x0, y0, x1, y1 = REGION
    W, H = x1 - x0, y1 - y0
    path = np.zeros((W, H), np.float32)          # [x, y]
    for y in range(H):
        row = tiles[y0 + y]
        for x in range(W):
            if row[x0 + x] == wm.PATH:
                path[x, y] = 1.0
    return path


def _compose(path, pa, pb, ga, gper):
    """Full-resolution sheet pixels. No pygame — safe on a worker thread."""
    from scipy.ndimage import gaussian_filter, zoom
    x0 = REGION[0]
    W, H = path.shape
    Pc = P // _K
    rng = np.random.default_rng(5150)
    big = np.kron(1.0 - path, np.ones((Pc, Pc), np.float32))
    f = gaussian_filter(big, Pc * 0.85, mode="nearest")
    f = f + 0.20 * _noise(rng, f.shape, Pc * 2.2) + 0.07 * _noise(rng, f.shape, max(0.5, Pc * 0.45))
    lo = _noise(rng, f.shape, Pc * 1.6)
    mid = _noise(rng, f.shape, max(0.5, Pc * 0.25))
    rutn = np.clip(_noise(rng, f.shape, max(0.5, Pc * 0.8)) + 0.5, 0, 1)

    def up(a):
        z = zoom(a, _K, order=1)
        return z[: W * P, : H * P]

    f, lo, mid, rutn = up(f), up(lo), up(mid), up(rutn)
    # keep the map honest: road cores dirt, grass centres grass
    yy, xx = np.meshgrid(np.arange(H * P), np.arange(W * P))
    fx, fy = (xx % P) / P, (yy % P) / P
    core = (np.abs(fx - 0.5) < 0.30) & (np.abs(fy - 0.5) < 0.30)
    centre = (np.abs(fx - 0.5) < 0.18) & (np.abs(fy - 0.5) < 0.18)
    pathpx = np.kron(path, np.ones((P, P), np.float32)) > 0.5
    f = np.where(pathpx & core, np.minimum(f, 0.30), f)
    f = np.where(~pathpx & centre, np.maximum(f, 0.72), f)
    g = _smooth(0.44, 0.56, f)

    fine = rng.standard_normal(f.shape).astype(np.float32) * 0.5
    base = np.stack([np.full(f.shape, 128.0), np.full(f.shape, 101.0), np.full(f.shape, 72.0)], -1)
    shade = 1.0 + 0.10 * lo + 0.07 * mid
    dirt = base * shade[..., None] + (fine * 9.0)[..., None]
    per = pa.shape[0]

    def tile_to(arr):
        reps = (W * P // per + 2, H * P // per + 2, 1)
        return np.tile(arr, reps)[: W * P, : H * P]

    detail = 0.5 * tile_to(pa) + 0.5 * tile_to(pb)
    detail = detail - detail.mean(axis=(0, 1))
    dirt = dirt + 0.45 * detail
    rut = np.exp(-((f - 0.15) / 0.018) ** 2) * (1.0 - g)
    rut = rut * (0.6 + 0.4 * rutn)
    dirt = dirt * (1.0 - 0.13 * rut)[..., None]
    peb = gaussian_filter((rng.random(f.shape) < 0.0007).astype(np.float32), 1.1) * 18
    dirt = np.clip(dirt + np.clip(peb, 0, 1)[..., None] * np.array([34.0, 28.0, 20.0]), 0, 255)

    reps = (W * P // gper + 2, H * P // gper + 2, 1)
    off = ((x0 % (gper // P)) * P, (REGION[1] % (gper // P)) * P)
    grass = np.tile(ga, reps)[off[0]: off[0] + W * P, off[1]: off[1] + H * P]
    worn = _smooth(0.50, 0.58, f) * (1.0 - _smooth(0.60, 0.82, f)) * np.clip(0.6 + 0.6 * mid, 0, 1)
    grass = grass * (1 - 0.45 * worn[..., None]) + dirt * (0.45 * worn[..., None])
    grass = grass * (1.0 + 0.06 * lo)[..., None]
    out = grass * g[..., None] + dirt * (1.0 - g[..., None])
    return np.clip(out, 0, 255).astype(np.uint8)


def _kick(client):
    tiles = client.tiles
    if _S.get("grid") is tiles and _S.get("base") is not None:
        return
    if _JOB.get("failed") == id(tiles):
        return
    with _LOCK:
        ready = _JOB.get("ready")
        if _JOB.get("pending") == id(tiles) or (ready and ready[1] is tiles):
            return
        _JOB["gen"] += 1
        gen = _JOB["gen"]
        _JOB["pending"] = id(tiles)
        _JOB["ready"] = None
    path = _path_mask(tiles)
    pa, pb, ga, gper = _detail()
    tiles_ref = tiles

    def run():
        try:
            arr = _compose(path, pa, pb, ga, gper)
        except Exception as exc:
            with _LOCK:
                if gen == _JOB["gen"]:
                    _JOB["failed"] = id(tiles_ref)
                    _JOB["pending"] = None
                    _JOB["exc"] = exc
            return
        with _LOCK:
            if gen == _JOB["gen"]:
                _JOB["ready"] = (arr, tiles_ref)
                _JOB["pending"] = None

    threading.Thread(target=run, name="village-sheet", daemon=True).start()


def _install():
    """Turn a finished array into a Surface. Draw thread only."""
    with _LOCK:
        ready = _JOB.get("ready")
        exc = _JOB.get("exc")
        if ready is None:
            if exc is not None and not _S.get("warned"):
                print("[village_sheet]", exc)
                _S["warned"] = True
            return False
        arr, tiles = ready
        _JOB["ready"] = None
    surf = pygame.Surface((arr.shape[0], arr.shape[1]))
    pygame.surfarray.blit_array(surf, arr)
    _S["grid"] = tiles
    _S["base"] = surf.convert()
    _S.pop("scaled", None)
    _S.pop("tile", None)
    return _S.get("grid") is not None


def draw(screen, rect, wx, wy, client):
    if client is None or not getattr(client, "tiles", None) or not _covers(client, wx, wy):
        return False
    tile = rect.w
    try:
        if _S.get("grid") is not client.tiles or _S.get("base") is None:
            _kick(client)
            if not _install():
                return False
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
        _JOB["failed"] = id(client.tiles)
        return False
