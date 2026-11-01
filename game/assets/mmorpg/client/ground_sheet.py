"""Map-wide painted ground (31 Oct 2026): the village sheet look everywhere.

The overworld outside the village and the King's Realm get the same treatment
as client/village_sheet.py: a blurred, noise-wobbled "meadow" field decides
where grass meets dirt (big rounded corners, wavy edges, worn verges), the dirt
is procedural with rotated photo detail, ruts and pebbles, and the grass is the
shared world-aligned meadow sheet.

The map is too big for one sheet, so the smooth fields are computed once for the
whole map at 4 px per tile and each 16x16-tile chunk is baked at 32 px per tile
on first use (LRU cache, plus one scaled copy per zoom level). Because every
chunk samples the same global fields and world-aligned textures, chunk borders
do not show.
Visual only: tiles and walkability are untouched; road cores stay dirt and grass
centres stay grass. Any failure returns False and the old painter draws instead.
"""
import os
from collections import OrderedDict

import numpy as np
import pygame

import world_map as wm

P = 32            # baked pixels per tile
Q = 4             # global field pixels per tile
CH = 16           # chunk size in tiles
PAD = 3           # tiles of field context around a chunk when upsampling
_MAX_CHUNKS = 48
_MAX_SCALED = 96
_F = {}           # source key -> global fields
_C = OrderedDict()
_SC = OrderedDict()
_STATE = {}
_SKIP_ZONES = ("village", "city", "volcano", "shadow_crypt", "fairy_village", "mine")
REALM_PATH = "=PSol"
REALM_PAVE = "oPSl"        # spawn plaza paving (rounded into the roads like the dirt into grass)
_PAVE_IMG = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets", "housing", "estate_plaza",
                         "plaza_ground_hd.png")


def _smooth(e0, e1, x):
    t = np.clip((x - e0) / (e1 - e0), 0.0, 1.0)
    return t * t * (3 - 2 * t)


def _noise(rng, shape, sigma):
    from scipy.ndimage import gaussian_filter
    n = gaussian_filter(rng.standard_normal(shape).astype(np.float32), sigma, mode="wrap")
    return n / max(1e-6, float(np.abs(n).max()))


# ------------------------------------------------------------------ sources
def _realm(client):
    d = getattr(client, "dungeon", None) or {}
    return d.get("id") == "castle_realm" and d.get("plane") == "realm"


def _source(client):
    """(key, path grid [x, y] bool) for the ground the client is standing on, or None."""
    tiles = getattr(client, "tiles", None)
    if not tiles:
        return None
    if _realm(client):
        import castle_realm_renderer as crr
        rows = crr.REALM_ROWS
        if not rows:
            return None
        key = ("realm", id(rows))
        if key not in _F:
            W, H = len(rows[0]), len(rows)
            path = np.zeros((W, H), bool)
            pave = np.zeros((W, H), bool)
            for y, row in enumerate(rows):
                for x, ch in enumerate(row):
                    path[x, y] = ch in REALM_PATH
                    pave[x, y] = ch in REALM_PAVE
            _F[key] = _fields(path, 7331, pave)
        return key
    if getattr(client, "dungeon", None):
        return None
    key = ("ow", id(tiles))
    if key not in _F:
        for k in [k for k in _F if k[0] == "ow"]:
            del _F[k]
        H, W = len(tiles), len(tiles[0])
        path = np.zeros((W, H), bool)
        for y in range(H):
            row = tiles[y]
            for x in range(W):
                path[x, y] = row[x] == wm.PATH
        _F[key] = _fields(path, 5150)
    return key


def covers(client, wx, wy):
    if client is None or int(getattr(client, "camera_yaw", 0)) % 4:
        return False
    if _realm(client):
        return True
    if getattr(client, "dungeon", None):
        return False
    try:
        return wm.get_zone(int(wx), int(wy)) not in _SKIP_ZONES
    except Exception:
        return False


# ------------------------------------------------------------------ global fields
def _fields(path, seed, pave=None):
    from scipy.ndimage import gaussian_filter
    W, H = path.shape
    rng = np.random.default_rng(seed)
    meadow = np.kron((~path).astype(np.float32), np.ones((Q, Q), np.float32))
    f = gaussian_filter(meadow, Q * 0.85, mode="nearest")
    shape = f.shape
    f += 0.24 * _noise(rng, shape, Q * 2.2) + 0.12 * _noise(rng, shape, Q * 0.9) + 0.06 * _noise(rng, shape, Q * 0.45)
    lo = _noise(rng, shape, Q * 1.6)
    mid = _noise(rng, shape, max(1.0, Q * 0.25))
    rutn = np.clip(_noise(rng, shape, Q * 0.8) + 0.5, 0, 1)
    pv = None
    if pave is not None and pave.any():
        pv = gaussian_filter(np.kron(pave.astype(np.float32), np.ones((Q, Q), np.float32)), Q * 0.85, mode="nearest")
        pv += 0.10 * _noise(rng, shape, Q * 1.2)
        pv = pv.astype(np.float32)
    return {"pave": pv, "pmask": pave, "path": path, "f": f.astype(np.float32), "lo": lo.astype(np.float32),
            "mid": mid.astype(np.float32), "rut": rutn.astype(np.float32), "W": W, "H": H}


def _up(arr, x0, y0, n):
    """Field values for tiles [x0, x0+n) x [y0, y0+n) at P px per tile (bilinear, padded)."""
    from scipy.ndimage import zoom
    hi = (PAD + n) * Q
    a = np.pad(arr, ((PAD * Q, hi), (PAD * Q, hi)), mode="edge")
    sub = a[x0 * Q: (x0 + n + 2 * PAD) * Q, y0 * Q: (y0 + n + 2 * PAD) * Q]
    big = zoom(sub, P // Q, order=1, mode="nearest", grid_mode=True)
    o = PAD * P
    return big[o: o + n * P, o: o + n * P]


def _textures():
    if "dirt" in _STATE:
        return _STATE["dirt"], _STATE["grass"], _STATE["gper"]
    import village_ground as vg
    photo = pygame.image.load(os.path.join(vg._DIR, "dirt_world.jpg")).convert()
    per = 24 * P
    photo = pygame.transform.smoothscale(photo, (per, per))
    pa = pygame.surfarray.array3d(photo).astype(np.float32)
    detail = 0.5 * pa + 0.5 * np.rot90(pa, 1, (0, 1))
    detail -= detail.mean(axis=(0, 1))
    gt = vg._grass_texture(P, season=None)
    gper = vg._GRASS_PERIOD * P
    grass = pygame.surfarray.array3d(gt).astype(np.float32)[:gper, :gper]
    _STATE.update(dirt=detail, grass=grass, gper=gper)
    return detail, grass, gper


def _pave_tex():
    t = _STATE.get("pave")
    if t is None:
        img = pygame.image.load(_PAVE_IMG).convert()
        crop = img.subsurface(pygame.Rect(0, 0, 1800, 1500))
        sm = pygame.transform.smoothscale(crop, (432, 360))                # ~8 px courses at 32 px/tile
        a = pygame.surfarray.array3d(sm).astype(np.float32)
        a = np.concatenate([a, a[::-1]], 0)                               # mirror tile: no seam
        a = np.concatenate([a, a[:, ::-1]], 1)
        t = a * np.array([0.92, 0.90, 0.88], np.float32)
        _STATE["pave"] = t
    return t


def _wrap_take(tex, px0, py0, n):
    per_x, per_y = tex.shape[0], tex.shape[1]
    ix = (np.arange(px0, px0 + n) % per_x)
    iy = (np.arange(py0, py0 + n) % per_y)
    return tex[ix][:, iy]


def _bake(key, cx, cy):
    from scipy.ndimage import gaussian_filter
    F = _F[key]
    W, H = F["W"], F["H"]
    x0, y0 = cx * CH, cy * CH
    n = CH
    N = n * P
    f = _up(F["f"], x0, y0, n)
    lo = _up(F["lo"], x0, y0, n)
    mid = _up(F["mid"], x0, y0, n)
    rutn = _up(F["rut"], x0, y0, n)
    # keep the map honest: road cores dirt, grass centres grass
    pth = np.zeros((n, n), bool)
    xs, ys = slice(x0, min(W, x0 + n)), slice(y0, min(H, y0 + n))
    blk = F["path"][xs, ys]
    pth[: blk.shape[0], : blk.shape[1]] = blk
    xx, yy = np.meshgrid(np.arange(N), np.arange(N), indexing="ij")
    fx, fy = (xx % P) / P, (yy % P) / P
    core = (np.abs(fx - 0.5) < 0.30) & (np.abs(fy - 0.5) < 0.30)
    centre = (np.abs(fx - 0.5) < 0.18) & (np.abs(fy - 0.5) < 0.18)
    pathpx = np.kron(pth, np.ones((P, P), bool))
    f = np.where(pathpx & core, np.minimum(f, 0.30), f)
    f = np.where(~pathpx & centre, np.maximum(f, 0.72), f)
    g = _smooth(0.44, 0.56, f)
    rng = np.random.default_rng((1 if key[0] == "realm" else 2) * 100003 + cx * 7919 + cy)
    detail, grass_t, gper = _textures()
    fine = rng.standard_normal((N, N)).astype(np.float32) * 0.5
    base = np.array([128.0, 101.0, 72.0], np.float32)
    shade = 1.0 + 0.10 * lo + 0.07 * mid
    dirt = base[None, None, :] * shade[..., None] + (fine * 9.0)[..., None]
    dirt += 0.45 * _wrap_take(detail, x0 * P, y0 * P, N)
    rut = np.exp(-((f - 0.15) / 0.018) ** 2) * (1.0 - g) * (0.6 + 0.4 * rutn)
    dirt *= (1.0 - 0.08 * rut)[..., None]
    peb = gaussian_filter((rng.random((N, N)) < 0.0007).astype(np.float32), 1.1) * 18
    dirt += np.clip(peb, 0, 1)[..., None] * np.array([34.0, 28.0, 20.0], np.float32)
    dirt = np.clip(dirt, 0, 255)
    grass = _wrap_take(grass_t, x0 * P, y0 * P, N)
    worn = _smooth(0.50, 0.58, f) * (1.0 - _smooth(0.60, 0.82, f)) * np.clip(0.6 + 0.6 * mid, 0, 1)
    grass = grass * (1 - 0.45 * worn[..., None]) + dirt * (0.45 * worn[..., None])
    grass *= (1.0 + 0.06 * lo)[..., None]
    out = grass * g[..., None] + dirt * (1.0 - g[..., None])
    if F.get("pave") is not None:
        pv = _up(F["pave"], x0, y0, n)
        pm = np.zeros((n, n), bool)
        b2 = F["pmask"][xs, ys]
        pm[: b2.shape[0], : b2.shape[1]] = b2
        pmpx = np.kron(pm, np.ones((P, P), bool))
        pv = np.where(pmpx & core, np.maximum(pv, 0.8), pv)
        pv = np.where(~pmpx & centre, np.minimum(pv, 0.2), pv)
        a = _smooth(0.40, 0.60, pv) * np.clip(1.0 - g * 1.15, 0.0, 1.0)
        if float(a.max()) > 0.0:
            stones = _wrap_take(_pave_tex(), x0 * P, y0 * P, N) * (1.0 + 0.05 * lo)[..., None]
            edge = a * (1 - a) * 4                         # dusty mortar where the paving meets the road
            stones = stones * (1 - 0.25 * edge[..., None]) + dirt * (0.25 * edge[..., None])
            out = out * (1 - a[..., None]) + stones * a[..., None]
    surf = pygame.Surface((N, N))
    pygame.surfarray.blit_array(surf, np.clip(out, 0, 255).astype(np.uint8))
    return surf.convert()


def _chunk(key, cx, cy, tile):
    ck = (key, cx, cy)
    base = _C.get(ck)
    if base is None:
        base = _bake(key, cx, cy)
        _C[ck] = base
        while len(_C) > _MAX_CHUNKS:
            _C.popitem(last=False)
    else:
        _C.move_to_end(ck)
    if tile == P:
        return base
    sk = (ck, tile)
    s = _SC.get(sk)
    if s is None:
        s = pygame.transform.smoothscale(base, (CH * tile, CH * tile))
        _SC[sk] = s
        while len(_SC) > _MAX_SCALED:
            _SC.popitem(last=False)
    else:
        _SC.move_to_end(sk)
    return s


def draw(screen, rect, wx, wy, client):
    """Blit the baked ground for one grass or path tile. False -> caller uses the old painter."""
    tile = rect.w
    if tile <= 0 or rect.h != tile or not covers(client, wx, wy):
        return False
    try:
        key = _source(client)
        if key is None:
            return False
        F = _F[key]
        wx, wy = int(wx), int(wy)
        if not (0 <= wx < F["W"] and 0 <= wy < F["H"]):
            return False
        cx, cy = wx // CH, wy // CH
        surf = _chunk(key, cx, cy, tile)
        screen.blit(surf, rect.topleft, pygame.Rect((wx - cx * CH) * tile, (wy - cy * CH) * tile, tile, tile))
        return True
    except Exception as exc:
        if not _STATE.get("warned"):
            print("[ground_sheet]", exc)
            _STATE["warned"] = True
        return False


# ------------------------------------------------------------------ rock outcrops
_ROCK = OrderedDict()


def draw_soft_rock(client, rect, wx, wy, painter):
    """A wall/rock tile beside meadow: meadow underneath, the rock sprite cut to a rounded,
    wobbly outline (same gaussian field as the lake shores). False -> draw the plain tile."""
    tile = rect.w
    if tile <= 0 or rect.h != tile or not covers(client, wx, wy):
        return False
    try:
        import village_ground as vg
        tiles = client.tiles
        H, W = len(tiles), len(tiles[0])

        def rock(x, y):
            return not (0 <= x < W and 0 <= y < H) or tiles[y][x] == wm.WALL

        if all(rock(wx + dx, wy + dy) for dx in (-1, 0, 1) for dy in (-1, 0, 1)):
            return False
        bits = 0
        i = 0
        for dy in range(-2, 3):
            for dx in range(-2, 3):
                if rock(wx + dx, wy + dy):
                    bits |= 1 << i
                i += 1
        if not vg.draw_world_grass(client.screen, rect, wx, wy, client=client):
            return False
        key = (bits, tile, wx, wy)
        mask = _ROCK.get(key)
        if mask is None:
            f = vg.shore_field(bits, tile, wx, wy, wobble=0.35, freq=5.0)
            mask = (_smooth(0.42, 0.58, f) * 255).astype(np.uint8)
            _ROCK[key] = mask
            while len(_ROCK) > 3000:
                _ROCK.popitem(last=False)
        tmp = pygame.Surface((tile, tile), pygame.SRCALPHA)
        painter(tmp, pygame.Rect(0, 0, tile, tile), wx, wy)
        al = pygame.surfarray.pixels_alpha(tmp)
        al[:, :] = (al.astype(np.uint16) * mask // 255).astype(np.uint8)
        del al
        client.screen.blit(tmp, rect.topleft)
        return True
    except Exception as exc:
        if not _STATE.get("rock_warned"):
            print("[ground_sheet rock]", exc)
            _STATE["rock_warned"] = True
        return False
