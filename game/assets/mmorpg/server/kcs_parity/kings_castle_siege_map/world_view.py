"""2.5D gameplay renderer: layered sprites aligned to the collision grid.

The orthogonal nav grid remains authoritative underneath. Walls, towers,
gatehouses, the keep, engines and the player are painted sprites with
height and Y-sort occlusion — not a per-tile brick mosaic and not a
static cinematic plate disconnected from the camera.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional, Sequence, Tuple

import pygame

from . import art
from .constants import HEIGHT, MAP_TITLE, WIDTH
from .layout import Battlefield, Rect
from .placement import PlacedEngine, PlacementResult, SPECS, rotated_size

Coord = Tuple[int, int]
CAPTION = "DUMMY pygame | isolated King's Castle M7 | NOT live GUI | NOT the shipped game client"
CHUNK = 16
# Shared world units: 1 tile = 1.6 m. Ground textures were baked for 8 m = 5 tiles.
TEX_TILES = 5.0
WALL_VIS_H = 5.2
PLAYER_W, PLAYER_H = 0.74, 1.88
KEEP_VIS_H = 24.0
GATEHOUSE_VIS_H = 10.0
POSTERN_VIS_H = 8.0
TOWER_VIS_H = 11.5
TENT_W, TENT_H = 3.85, 2.95
ENGINE_VIS = {
    "ram": (3.0, 2.05),
    "trebuchet": (3.4, 3.05),
    "siege_tower": (2.45, 3.9),
    "ladder": (1.25, 2.55),
}

HINTS = "R Rotate   Enter Place   Esc Cancel   [ ] Cycle engine"

LAST_METRICS: Dict[str, float] = {}
_CAM: Dict[str, object] = {"origin": (0.0, 0.0), "tp": 32.0, "view": (1600, 786)}
_static_cache: Dict[tuple, list] = {}
_biome_cache: Dict[tuple, dict] = {}
_font_cache: Dict[int, pygame.font.Font] = {}
_shadow_cache: Dict[tuple, pygame.Surface] = {}
_tree_cache: Dict[int, list] = {}
_label_cache: Dict[tuple, pygame.Surface] = {}


def _cam_screen(x: float, y: float) -> Tuple[int, int]:
    return world_to_screen(_CAM["origin"], float(_CAM["tp"]), x, y)  # type: ignore[arg-type]


def _on_screen(foot_x: float, foot_y: float, margin: float = 28.0) -> bool:
    tp = float(_CAM["tp"])
    vw, vh = _CAM["view"]  # type: ignore[misc]
    sx, sy = _cam_screen(foot_x, foot_y)
    pad = margin * tp
    return -pad <= sx <= vw + pad and -pad <= sy <= vh + pad



@dataclass
class DrawItem:
    layer: int
    foot_y: float
    foot_x: float
    blit: Callable[[pygame.Surface], None]


def _font(size: int) -> pygame.font.Font:
    f = _font_cache.get(size)
    if f is None:
        f = pygame.font.Font(None, size)
        _font_cache[size] = f
    return f


def world_to_screen(origin: Tuple[float, float], tile_px: float, x: float, y: float) -> Tuple[int, int]:
    """Integer projection that keeps adjacent world tiles gapless for any origin."""
    return int(x * tile_px) - int(origin[0] * tile_px), int(y * tile_px) - int(origin[1] * tile_px)


def camera_origin(player: Tuple[float, float], tile_px: float, view: Tuple[int, int]) -> Tuple[float, float]:
    return player[0] - (view[0] / tile_px) / 2 + 0.5, player[1] - (view[1] / tile_px) / 2 + 0.5


def _inside(rect: Rect, x: int, y: int) -> bool:
    return rect[0] <= x <= rect[2] and rect[1] <= y <= rect[3]


def _fill_wrapped(dest: pygame.Surface, tex: pygame.Surface, origin_px: Tuple[int, int]) -> None:
    tw, th = tex.get_size()
    dw, dh = dest.get_size()
    ox = origin_px[0] % tw
    oy = origin_px[1] % th
    y = -oy
    while y < dh:
        x = -ox
        while x < dw:
            dest.blit(tex, (x, y))
            x += tw
        y += th


def _overlay_mask(dest: pygame.Surface, tex: pygame.Surface, mask: List[List[bool]],
                  origin_px: Tuple[int, int], tp: int) -> None:
    """Stamp a wrapped texture only where mask[ty][tx] is true, as one pass per run."""
    h = len(mask)
    w = len(mask[0]) if h else 0
    tw, th = tex.get_size()
    for ty in range(h):
        tx = 0
        while tx < w:
            if not mask[ty][tx]:
                tx += 1
                continue
            run = tx
            while run < w and mask[ty][run]:
                run += 1
            width = (run - tx) * tp
            piece = pygame.Surface((width, tp))
            # world pixel at this run
            wx = origin_px[0] + tx * tp
            wy = origin_px[1] + ty * tp
            _fill_wrapped(piece, tex, (wx, wy))
            dest.blit(piece, (tx * tp, ty * tp))
            tx = run


_chunk_cache: Dict[Tuple[int, int, int], pygame.Surface] = {}
_chunk_sig: Optional[int] = None


def clear_chunk_cache() -> None:
    _chunk_cache.clear()
    _biome_cache.clear()
    _static_cache.clear()


def _ensure_chunks(bf: Battlefield) -> None:
    global _chunk_sig
    sig = id(bf.plane)
    if _chunk_sig != sig:
        _chunk_cache.clear()
        _chunk_sig = sig


def _tex(name: str, tp: int) -> pygame.Surface:
    tiles = TEX_TILES
    if name == "water":
        tiles = 8.0
    elif name == "court_fine":
        # ~8 m of paving so 30–50 cm flags stay human-scale vs the player
        tiles = 5.0
    elif name == "grass_fine":
        tiles = 6.5
    elif name == "road_fine":
        tiles = 5.2
    elif name == "wall_top":
        tiles = 3.8
    side = max(32, int(tiles * tp))
    return art.scaled(name, side, side)


def _mask_up(flags, tp: int):
    """flags: CHUNK x CHUNK floats 0..1 (row-major y,x) -> (width,height) alpha."""
    import numpy as np
    import pygame.surfarray as sa
    small = pygame.Surface((CHUNK, CHUNK))
    rgb = sa.pixels3d(small)
    v = (np.clip(flags, 0, 1).T * 255.0).astype("uint8")
    rgb[:, :, 0] = v
    rgb[:, :, 1] = v
    rgb[:, :, 2] = v
    del rgb
    big = pygame.transform.smoothscale(small, (CHUNK * tp, CHUNK * tp))
    return sa.array3d(big)[:, :, 0]  # uint8 0..255


def _wrap_layer(tex: pygame.Surface, origin_px, size) -> pygame.Surface:
    surf = pygame.Surface(size)
    _fill_wrapped(surf, tex, origin_px)
    return surf


def _dilate_mask(src, rings=((0.95, 0.72), (0.68, 0.46), (0.40, 0.22))):
    """Spread a 0/1 tile mask into neighbours so biome edges are not hard rectangles."""
    import numpy as np
    cur = src.copy()
    for thresh, val in rings:
        padded = np.pad(cur, 1, mode="edge")
        neigh = np.maximum.reduce([
            padded[0:-2, 1:-1], padded[2:, 1:-1], padded[1:-1, 0:-2], padded[1:-1, 2:],
            padded[0:-2, 0:-2], padded[0:-2, 2:], padded[2:, 0:-2], padded[2:, 2:],
        ])
        grow = (cur < val) & (neigh >= thresh)
        nxt = cur.copy()
        nxt[grow] = np.maximum(nxt[grow], val)
        cur = nxt
    return cur


def _irregularize(flags, x0: int, y0: int, holes: bool = False, amp: float = 0.16):
    """Break axis-aligned biome edges and flat road slabs with world-space noise."""
    import numpy as np
    yy, xx = np.mgrid[0:CHUNK, 0:CHUNK].astype(np.float32)
    wx, wy = x0 + xx, y0 + yy
    noise = (
        0.55 * np.sin(wx * 0.73 + wy * 0.41)
        + 0.35 * np.sin(wx * 0.29 - wy * 0.67 + 1.3)
        + 0.25 * np.sin(wx * 1.51 + wy * 1.18)
    )
    edge = (flags > 0.04) & (flags < 0.96)
    out = np.clip(flags + noise * amp * edge, 0.0, 1.0)
    if holes:
        mott = np.maximum(0.0, np.sin(wx * 0.37 + 1.7) * np.cos(wy * 0.33) - 0.18)
        out = np.clip(out - 0.42 * mott * (out > 0.55), 0.0, 1.0)
        mott2 = np.maximum(0.0, np.sin(wx * 0.13 + wy * 0.11) - 0.35)
        out = np.clip(out - 0.20 * mott2 * (out > 0.6), 0.0, 1.0)
    return out.astype(np.float32)


def _lane_ruts(bf: Battlefield, x0: int, y0: int, n: int):
    """Cart ruts only along long road corridors, never on grass."""
    import numpy as np
    rut = np.zeros((n, n), np.float32)
    grid = bf.plane.grid

    def run(x, y, dx, dy):
        c = 0
        while 0 <= x < WIDTH and 0 <= y < HEIGHT and grid[y][x] == "=":
            c += 1
            x += dx
            y += dy
        return c

    for ty in range(n):
        gy = y0 + ty
        if not (0 <= gy < HEIGHT):
            continue
        for tx in range(n):
            gx = x0 + tx
            if not (0 <= gx < WIDTH) or grid[gy][gx] != "=":
                continue
            left = run(gx, gy, -1, 0)
            right = run(gx, gy, 1, 0)
            up = run(gx, gy, 0, -1)
            down = run(gx, gy, 0, 1)
            sx, sy_ = left + right - 1, up + down - 1
            if sx < 3 and sy_ < 3:
                continue
            if sy_ >= 8 and sy_ >= sx - 1:
                pos = (left - 0.5) / max(1, sx)
                if sx >= 10:
                    d = min(abs(pos - 0.34), abs(pos - 0.66))
                    if d < 0.05:
                        rut[ty, tx] = 1.0 - d / 0.05 * 0.4
                elif 5 <= sx <= 9:
                    d = abs(pos - 0.5)
                    if d < 0.16:
                        rut[ty, tx] = 0.8
            elif sx >= 10 and sx > sy_:
                pos = (up - 0.5) / max(1, sy_)
                if sy_ >= 8:
                    d = min(abs(pos - 0.35), abs(pos - 0.65))
                    if d < 0.08:
                        rut[ty, tx] = 1.0 - d / 0.08 * 0.4
                elif sy_ >= 4:
                    d = abs(pos - 0.5)
                    if d < 0.22:
                        rut[ty, tx] = 0.75
    return rut


def _burn_lane_ruts(out, bf: Battlefield, x0: int, y0: int, tp: int) -> None:
    """Thin wheel ruts in pixel space so they do not become tile-wide smudges."""
    import numpy as np
    h, w = out.shape[1], out.shape[0]  # surfarray is x,y
    grid = bf.plane.grid
    sigma = max(1.2, 0.16 * tp)
    inv = 1.0 / (2.0 * sigma * sigma)

    def run(x, y, dx, dy):
        c = 0
        while 0 <= x < WIDTH and 0 <= y < HEIGHT and grid[y][x] == "=":
            c += 1
            x += dx
            y += dy
        return c

    # NS ruts: columns
    for ty in range(CHUNK):
        gy = y0 + ty
        if not (0 <= gy < HEIGHT):
            continue
        tx = 0
        while tx < CHUNK:
            gx = x0 + tx
            if not (0 <= gx < WIDTH) or grid[gy][gx] != "=":
                tx += 1
                continue
            left = run(gx, gy, -1, 0)
            right = run(gx, gy, 1, 0)
            sx = left + right - 1
            run0 = gx - (left - 1)
            # consume this horizontal run inside the chunk
            t1 = tx
            while t1 < CHUNK and 0 <= x0 + t1 < WIDTH and grid[gy][x0 + t1] == "=":
                t1 += 1
            up = run(gx, gy, 0, -1)
            down = run(gx, gy, 0, 1)
            sy_ = up + down - 1
            mg = bf.plane.openings["main_gate"].rect
            approach = gy > bf.wall_box[3] and mg[0] - 10 <= gx <= mg[2] + 10 and sy_ >= 8
            if approach and sx > 28:
                run0, sx = mg[0], mg[2] - mg[0] + 1
                fracs = (0.34, 0.66)
            elif sy_ >= 8 and sy_ >= sx - 1 and sx >= 5:
                fracs = (0.34, 0.66) if sx >= 10 else (0.5,)
            else:
                fracs = ()
            if fracs:
                ypix0 = ty * tp
                ypix1 = min(h, (ty + 1) * tp)
                for fr in fracs:
                    wx = (run0 + fr * sx - x0) * tp + 0.11 * tp * __import__("math").sin((gy + 0.5) * 0.45)
                    x0i = max(0, int(wx - 3 * sigma))
                    x1i = min(w, int(wx + 3 * sigma) + 1)
                    if x1i <= x0i:
                        continue
                    xs = np.arange(x0i, x1i)
                    fall = np.exp(-((xs - wx) ** 2) * inv)
                    for yp in range(int(ypix0), int(ypix1)):
                        col = out[x0i:x1i, yp].astype("float32")
                        out[x0i:x1i, yp] = np.clip(col * (1.0 - 0.28 * fall[:, None]), 0, 255)
            tx = t1

    # EW ruts: rows on wide east-west aprons
    for tx in range(CHUNK):
        gx = x0 + tx
        if not (0 <= gx < WIDTH):
            continue
        ty = 0
        while ty < CHUNK:
            gy = y0 + ty
            if not (0 <= gy < HEIGHT) or grid[gy][gx] != "=":
                ty += 1
                continue
            up = run(gx, gy, 0, -1)
            down = run(gx, gy, 0, 1)
            sy_ = up + down - 1
            left = run(gx, gy, -1, 0)
            right = run(gx, gy, 1, 0)
            sx = left + right - 1
            run0 = gy - (up - 1)
            t1 = ty
            while t1 < CHUNK and 0 <= y0 + t1 < HEIGHT and grid[y0 + t1][gx] == "=":
                t1 += 1
            if sx >= 10 and sx > sy_ and sy_ >= 4:
                fracs = (0.35, 0.65) if sy_ >= 8 else (0.5,)
                xpix0 = tx * tp
                xpix1 = min(w, (tx + 1) * tp)
                for fr in fracs:
                    wy = (run0 + fr * sy_ - y0) * tp
                    y0i = max(0, int(wy - 3 * sigma))
                    y1i = min(h, int(wy + 3 * sigma) + 1)
                    if y1i <= y0i:
                        continue
                    ys = np.arange(y0i, y1i)
                    fall = np.exp(-((ys - wy) ** 2) * inv)
                    for xp in range(int(xpix0), int(xpix1)):
                        col = out[xp, y0i:y1i].astype("float32")
                        out[xp, y0i:y1i] = np.clip(col * (1.0 - 0.28 * fall[:, None]), 0, 255)
            ty = t1


def _chunk_surface(bf: Battlefield, cx: int, cy: int, tp: int) -> pygame.Surface:



    import numpy as np
    import pygame.surfarray as sa
    key = (cx, cy, tp)
    cached = _chunk_cache.get(key)
    if cached is not None:
        return cached
    pad = 2
    n = CHUNK + pad * 2
    x0, y0 = cx * CHUNK, cy * CHUNK
    road_f = np.zeros((n, n), np.float32)
    court_f = np.zeros((n, n), np.float32)
    water_f = np.zeros((n, n), np.float32)
    plank_f = np.zeros((n, n), np.float32)
    keep_f = np.zeros((n, n), np.float32)
    wall_f = np.zeros((n, n), np.float32)
    kr = bf.keep_rect
    for ty in range(n):
        gy = y0 + ty - pad
        for tx in range(n):
            gx = x0 + tx - pad
            ch = bf.plane.grid[gy][gx] if (0 <= gx < WIDTH and 0 <= gy < HEIGHT) else "."
            if ch == "=":
                road_f[ty, tx] = 1.0
            elif ch == ",":
                court_f[ty, tx] = 1.0
            elif ch == "~":
                water_f[ty, tx] = 1.0
            elif ch == "H":
                plank_f[ty, tx] = 1.0
            elif ch == "#" and _inside(kr, gx, gy):
                keep_f[ty, tx] = 1.0
            elif ch == "G" and kr[0] - 1 <= gx <= kr[2] + 1 and kr[1] <= gy <= kr[3] + 4:
                # keep_doors threshold: continue courtyard paving up to the plinth
                court_f[ty, tx] = 1.0
            elif ch == "#":
                wall_f[ty, tx] = 1.0
    water_core = water_f.copy()
    road_f = _dilate_mask(road_f)
    court_f = _dilate_mask(court_f)
    # Keep the moat as a continuous channel, not a wide oval smear.
    water_f = _dilate_mask(water_f, rings=((0.95, 0.35),))
    bank_f = _dilate_mask(water_core, rings=((0.95, 0.72), (0.62, 0.40), (0.32, 0.16)))
    plank_f = _dilate_mask(plank_f)
    # do not dilate keep floor — it painted a detached dirt mat in front of the plinth
    keep_f = keep_f
    wall_f = _dilate_mask(wall_f, rings=((0.95, 0.40),))
    sl = slice(pad, pad + CHUNK)
    road_f, court_f = road_f[sl, sl], court_f[sl, sl]
    water_f, plank_f = water_f[sl, sl], plank_f[sl, sl]
    keep_f, wall_f = keep_f[sl, sl], wall_f[sl, sl]
    bank_f = np.clip(bank_f[sl, sl] - water_f * 0.9, 0, 1)
    road_f = _irregularize(road_f, x0, y0, holes=True, amp=0.26)
    court_f = _irregularize(court_f, x0, y0, holes=False, amp=0.06)
    water_f = _irregularize(water_f, x0, y0, holes=False, amp=0.07)
    bank_f = _irregularize(bank_f, x0, y0, holes=False, amp=0.16)
    size = (CHUNK * tp, CHUNK * tp)
    origin_px = (x0 * tp, y0 * tp)
    grass = _wrap_layer(_tex("grass_fine", tp), origin_px, size)
    out = sa.array3d(grass).copy()
    for name, flags in (
        ("road_fine", road_f),
        ("court_fine", court_f),
        ("keep_floor", keep_f),
        ("wall_top", wall_f),
        ("bank", bank_f),
        ("water", water_f),
        ("planks", plank_f),
    ):
        if float(flags.max()) < 0.01:
            continue
        src_name = "road_fine" if name == "bank" else name
        lay = sa.array3d(_wrap_layer(_tex(src_name, tp), origin_px, size)).astype("float32")
        if name == "bank":
            lay *= (0.55, 0.50, 0.38)
            lay = np.clip(lay, 0, 255)
        a = _mask_up(flags, tp)[:, :, None].astype("float32")
        out = (out.astype("float32") * (255.0 - a) + lay * a) / 255.0
    out = np.clip(out, 0, 255).astype("uint8")
    if float(wall_f.max()) > 0.01:
        wm = _mask_up(wall_f, tp).astype("int16")
        neigh = np.minimum.reduce([
            np.pad(wm, ((1, 0), (0, 0)), constant_values=0)[:-1, :],
            np.pad(wm, ((0, 1), (0, 0)), constant_values=0)[1:, :],
            np.pad(wm, ((0, 0), (1, 0)), constant_values=0)[:, :-1],
            np.pad(wm, ((0, 0), (0, 1)), constant_values=0)[:, 1:],
        ])
        shade = np.clip((wm - neigh).astype("float32") / 255.0, 0, 1)
        out = np.clip(out.astype("float32") * (1.0 - 0.28 * shade[:, :, None]), 0, 255).astype("uint8")
    dest = pygame.Surface(size)
    sa.blit_array(dest, out)
    _chunk_cache[key] = dest
    return dest


def _draw_ground(dest: pygame.Surface, bf: Battlefield, origin: Tuple[float, float], tp: float) -> int:
    _ensure_chunks(bf)
    itp = max(4, int(tp))
    w, h = dest.get_size()
    x0 = int(origin[0])
    y0 = int(origin[1])
    x1 = int(origin[0] + w / tp) + 2
    y1 = int(origin[1] + h / tp) + 2
    n = 0
    for cy in range(max(0, y0 // CHUNK), min((HEIGHT - 1) // CHUNK, y1 // CHUNK) + 1):
        for cx in range(max(0, x0 // CHUNK), min((WIDTH - 1) // CHUNK, x1 // CHUNK) + 1):
            chunk = _chunk_surface(bf, cx, cy, itp)
            sx, sy = world_to_screen(origin, tp, cx * CHUNK, cy * CHUNK)
            dest.blit(chunk, (sx, sy))
            n += 1
    return n


def _structure_tiles(bf: Battlefield) -> set:
    tiles = set()
    for name in ("keep", "nw_tower", "ne_tower", "sw_tower", "se_tower"):
        rec = bf.plane.landmarks[name].rect
        for y in range(rec[1], rec[3] + 1):
            for x in range(rec[0], rec[2] + 1):
                tiles.add((x, y))
    return tiles


def _gate_tiles(bf: Battlefield, include_breaches: bool = False) -> set:
    names = ["main_gate", "north_gate", "west_gate", "east_gate"]
    if include_breaches:
        names.extend(k for k in bf.plane.openings if "breach" in k)
    tiles = set()
    for name in names:
        rec = bf.plane.openings[name].rect
        for y in range(rec[1], rec[3] + 1):
            for x in range(rec[0], rec[2] + 1):
                tiles.add((x, y))
    return tiles


def _keep_door_tiles(bf: Battlefield) -> set:
    rec = bf.plane.openings["keep_doors"].rect
    tiles = set()
    for y in range(rec[1], rec[3] + 1):
        for x in range(rec[0], rec[2] + 1):
            tiles.add((x, y))
    return tiles


def _gate_door_tiles(bf: Battlefield) -> set:
    """Center passage of the main gate, so curtain can overlap the towers but
    not run behind the doors (fade-foot would otherwise reveal the wall)."""
    rec = bf.plane.openings["main_gate"].rect
    inset = 7
    tiles = set()
    for y in range(rec[1], rec[3] + 1):
        for x in range(rec[0] + inset, rec[2] - inset + 1):
            tiles.add((x, y))
    return tiles


def _destroyed_opening_tiles(bf: Battlefield, states: Dict[str, str]) -> set:
    tiles = set()
    for oid, op in bf.plane.openings.items():
        if states.get(oid, op.default_state) != "destroyed":
            continue
        rec = op.rect
        for y in range(rec[1], rec[3] + 1):
            for x in range(rec[0], rec[2] + 1):
                tiles.add((x, y))
    return tiles


def _ns_face_runs(bf: Battlefield, skip: set, side: str) -> List[Tuple[int, int, int]]:
    """Return (x, y0, y1) inclusive vertical runs on the west or east outer/inner face."""
    runs: List[Tuple[int, int, int]] = []
    wallish = {"#", "H", "G"}
    dx = -1 if side == "west" else 1
    for x in range(WIDTH):
        y = 0
        while y < HEIGHT:
            ch = bf.plane.grid[y][x]
            nx = x + dx
            neigh = bf.plane.grid[y][nx] if 0 <= nx < WIDTH else "."
            if ch in wallish and neigh not in wallish and (x, y) not in skip:
                y0 = y
                while y < HEIGHT:
                    ch = bf.plane.grid[y][x]
                    neigh = bf.plane.grid[y][nx] if 0 <= nx < WIDTH else "."
                    if not (ch in wallish and neigh not in wallish and (x, y) not in skip):
                        break
                    y += 1
                runs.append((x, y0, y - 1))
            else:
                y += 1
    return runs


def _west_face_runs(bf: Battlefield, skip: set) -> List[Tuple[int, int, int]]:
    return _ns_face_runs(bf, skip, "west")


def _east_face_runs(bf: Battlefield, skip: set) -> List[Tuple[int, int, int]]:
    return _ns_face_runs(bf, skip, "east")


def _south_face_runs(bf: Battlefield, skip: set) -> List[Tuple[int, int, int]]:
    """Return (x0, x1, y) inclusive runs where a wall has open ground to the south."""
    runs = []
    wallish = {"#", "H", "G"}
    for y in range(HEIGHT):
        x = 0
        while x < WIDTH:
            ch = bf.plane.grid[y][x]
            south = bf.plane.grid[y + 1][x] if y + 1 < HEIGHT else "."
            if ch in wallish and south not in wallish and (x, y) not in skip:
                x0 = x
                while x < WIDTH:
                    ch = bf.plane.grid[y][x]
                    south = bf.plane.grid[y + 1][x] if y + 1 < HEIGHT else "."
                    if not (ch in wallish and south not in wallish and (x, y) not in skip):
                        break
                    x += 1
                runs.append((x0, x - 1, y))
            else:
                x += 1
    return runs


def _shadow(dest: pygame.Surface, cx: int, cy: int, rw: int, rh: int) -> None:
    rw, rh = max(2, int(rw)), max(2, int(rh))
    el = _shadow_cache.get((rw, rh))
    if el is None:
        el = pygame.Surface((rw, rh), pygame.SRCALPHA)
        pygame.draw.ellipse(el, (20, 16, 10, 90), el.get_rect())
        _shadow_cache[(rw, rh)] = el
    dest.blit(el, (cx - rw // 2, cy - rh // 2))


def _blit(dest, img, anchor_x, anchor_y, foot=True) -> None:
    r = img.get_rect()
    if foot:
        r.midbottom = (anchor_x, anchor_y)
    else:
        r.topleft = (anchor_x, anchor_y)
    dest.blit(img, r)


def _trees(bf: Battlefield):
    sig = id(bf.plane)
    cached = _tree_cache.get(sig)
    if cached is None:
        found = []
        for y in range(HEIGHT):
            row = bf.plane.grid[y]
            for x, ch in enumerate(row):
                if ch == "T":
                    found.append((x, y))
        _tree_cache[sig] = found
        cached = found
    return cached


def _scatter_props(bf: Battlefield):
    """Visual-only landscape and camp dressing; does not change collision."""
    sig = id(bf.plane)
    key = ("props", sig)
    cached = _tree_cache.get(key)  # reuse dict as small intern cache
    if cached is not None:
        return cached
    props = []
    grid = bf.plane.grid
    # Sparse hash scatter on open grass, away from the inner bailey.
    wx0, wy0, wx1, wy1 = bf.wall_box
    for y in range(9, HEIGHT - 9, 6):
        for x in range(7, WIDTH - 8, 7):
            if grid[y][x] != ".":
                continue
            inside = wx0 - 2 <= x <= wx1 + 2 and wy0 - 2 <= y <= wy1 + 2
            if inside:
                continue
            h = (x * 73 + y * 19 + x * y) % 100
            if h < 5:
                props.append(("tree", x, y, 2.7, 3.6))
            elif h < 9:
                props.append(("rock", x, y, 1.15, 0.9))
            elif h < 11:
                props.append(("bush", x, y, 1.55, 1.35))
    # Extra dressing around the south approach and west verge (walkable tiles only).
    extras = [
        # South approach: a west-verge cluster, not a mirrored pair
        ("tree", 118, 197, 3.0, 3.9), ("tree", 113, 203, 2.6, 3.4),
        ("rock", 123, 194, 1.2, 0.92), ("bush", 120, 200, 1.55, 1.32),
        ("tree", 161, 202, 2.55, 3.35), ("rock", 154, 190, 1.05, 0.8),
        ("bush", 167, 208, 1.4, 1.25),
        # West flank: loose group north-west of the player, plus one south rock
        ("tree", 46, 141, 2.9, 3.7), ("tree", 53, 133, 2.4, 3.2),
        ("rock", 59, 155, 1.15, 0.88), ("bush", 44, 158, 1.5, 1.3),
        ("rock", 67, 171, 1.0, 0.78),
        # Camp east of south staging, offset, not a twin
        ("tent", 108, 234, 3.7, 2.85), ("tent", 149, 242, 3.3, 2.55),
        ("tree", 102, 228, 2.8, 3.6), ("rock", 141, 230, 1.2, 0.9),
    ]
    for kind, x, y, w, h in extras:
        if 0 <= x < WIDTH and 0 <= y < HEIGHT and grid[y][x] in {".", "="}:
            props.append((kind, x, y, w, h))
    _tree_cache[key] = props
    return props


def _build_static(bf: Battlefield, tp: float, gate_states: Dict[str, str]) -> List[DrawItem]:
    items: List[DrawItem] = []
    # Intact gates stay in the south-face runs so the curtain continues *behind*
    # the winged gatehouse (fills the hard vertical cut). Destroyed openings are
    # skipped so the breach hole is not papered over with wall.
    skip = _structure_tiles(bf) | _destroyed_opening_tiles(bf, gate_states) | _gate_door_tiles(bf) | _keep_door_tiles(bf)

    for x0, x1, y in _south_face_runs(bf, skip):
        if x1 - x0 < 1:
            continue
        width = int((x1 - x0 + 1) * tp)
        height = int(WALL_VIS_H * tp)
        img = art.scaled("wall_south", width, height)

        def draw_facade(dest, img=img, x0=x0, x1=x1, y=y):
            sx, sy = _cam_screen(x0, y + 1)
            dest.blit(img, (sx, sy - img.get_height()))

        items.append(DrawItem(1, y + 0.48, (x0 + x1) / 2, draw_facade))

    # Outer NS coping: tile a top-down parapet (merlons on the outer edge)
    # instead of stretching a south elevation along the whole curtain.
    skip_ns = skip | _gate_tiles(bf)
    wx0, wy0, wx1, wy1 = bf.wall_box
    cope_w = max(8, int(1.35 * tp))
    west_tex = art.scaled("parapet_ns", cope_w, cope_w)
    east_tex = pygame.transform.flip(west_tex, True, False)
    for x, y0, y1 in _west_face_runs(bf, skip_ns):
        if x > wx0 + 1:
            continue
        h = max(8, int((y1 - y0 + 1) * tp))
        strip = pygame.Surface((cope_w, h))
        _fill_wrapped(strip, west_tex, (int(x * tp), int(y0 * tp)))

        def draw_west(dest, img=strip, x=x, y1=y1):
            sx, sy = _cam_screen(x - 0.15, y1 + 1)
            dest.blit(img, (sx, sy - img.get_height()))

        items.append(DrawItem(1, y1 + 0.35, x + 0.2, draw_west))
    for x, y0, y1 in _east_face_runs(bf, skip_ns):
        if x < wx1 - 1:
            continue
        h = max(8, int((y1 - y0 + 1) * tp))
        strip = pygame.Surface((cope_w, h))
        _fill_wrapped(strip, east_tex, (int(x * tp), int(y0 * tp)))

        def draw_east(dest, img=strip, x=x, y1=y1):
            sx, sy = _cam_screen(x + 1 + 0.15, y1 + 1)
            dest.blit(img, (sx - img.get_width(), sy - img.get_height()))

        items.append(DrawItem(1, y1 + 0.35, x + 0.8, draw_east))

    def add_building(name: str, rect: Rect, sprite: str, visual_h: float, layer: int = 1, foot: float = 0.2):
        bw = (rect[2] - rect[0] + 1) * tp
        # visual_h is sprite height in tiles (not the north-south footprint depth)
        bh = visual_h * tp
        img = art.scaled(sprite, max(8, int(bw * 1.02)), max(8, int(bh)))
        foot_y = rect[3] + foot
        foot_x = (rect[0] + rect[2]) / 2

        def draw(dest, img=img, rect=rect, foot_y=foot_y, foot_x=foot_x):
            sx, sy = _cam_screen(foot_x, foot_y)
            _blit(dest, img, sx, sy)

        items.append(DrawItem(layer, foot_y, foot_x, draw))

    add_building("keep", bf.keep_rect, "keep", KEEP_VIS_H)
    for key, sprite_extra in (
        ("nw_tower", 8), ("ne_tower", 8), ("sw_tower", 8), ("se_tower", 8),
    ):
        add_building(key, bf.plane.landmarks[key].rect, "tower", TOWER_VIS_H)

    # Gatehouses
    main = bf.plane.openings["main_gate"].rect
    main_sprite = "gate_open" if gate_states.get("main_gate") == "destroyed" else "gatehouse"
    add_building("main_gate", (main[0] - 5, main[1], main[2] + 5, main[3]), main_sprite, GATEHOUSE_VIS_H, foot=0.92)
    for oid in ("north_gate", "west_gate", "east_gate"):
        rec = bf.plane.openings[oid].rect
        # Expand tiny wall-thickness rects so the postern reads as a building
        if rec[2] - rec[0] < rec[3] - rec[1]:
            # Side posterns: stand them up like the south gatehouse (same 2.5D
            # south-up language), sized to the 3/4 sprite aspect, not a top-down plan.
            rec = (rec[0] - 3, rec[1] + 2, rec[2] + 5, rec[3] - 2)
        else:
            rec = (rec[0], rec[1] - 2, rec[2], rec[3] + 2)
        sprite = {"west_gate": "postern_west", "east_gate": "postern_e", "north_gate": "postern"}.get(oid, "postern")
        vis_h = GATEHOUSE_VIS_H if oid in {"west_gate", "east_gate"} else POSTERN_VIS_H
        add_building(oid, rec, sprite, vis_h, foot=0.85)

    for x, y in _trees(bf):
        img_w, img_h = int(2.4 * tp), int(3.3 * tp)

        def draw_tree(dest, x=x, y=y, img_w=img_w, img_h=img_h):
            img = art.scaled("tree", img_w, img_h)
            sx, sy = _cam_screen(x + 0.5, y + 1)
            _shadow(dest, sx, sy, int(1.6 * tp), int(0.45 * tp))
            _blit(dest, img, sx, sy)

        items.append(DrawItem(1, y + 0.9, x + 0.5, draw_tree))

    # Station tents (landmarks — empty, not simulated agents)
    for key in ("heal_attack", "eng_attack", "res_attack", "heal_defend"):
        rec = bf.plane.landmarks[key].rect
        cx, cy = (rec[0] + rec[2]) / 2, rec[3] + 0.1
        if key == "heal_defend":
            # Visual marker only: sit west of the keep-door axis so the
            # approach in front of the doors stays walkable and readable.
            cx = rec[0] - 1.8
            cy = rec[3] - 0.15

        def draw_tent(dest, cx=cx, cy=cy):
            img = art.scaled("tent", int(TENT_W * tp), int(TENT_H * tp))
            sx, sy = _cam_screen(cx, cy)
            _shadow(dest, sx, sy, int(1.6 * tp), int(0.5 * tp))
            _blit(dest, img, sx, sy)

        items.append(DrawItem(1, cy, cx, draw_tent))

    # A few bushes near staging, visual only (walkable ground underneath)
    for x, y in ((30, 230), (50, 220), (230, 228), (40, 40), (240, 36), (36, 150), (244, 150)):
        if not (0 <= x < WIDTH and 0 <= y < HEIGHT):
            continue
        if bf.plane.grid[y][x] not in {".", "="}:
            continue

        def draw_bush(dest, x=x, y=y):
            img = art.scaled("bush", int(1.5 * tp), int(1.35 * tp))
            sx, sy = _cam_screen(x + 0.5, y + 0.9)
            _blit(dest, img, sx, sy)

        items.append(DrawItem(1, y + 0.7, x + 0.5, draw_bush))

    for kind, x, y, pw, ph in _scatter_props(bf):
        def draw_prop(dest, kind=kind, x=x, y=y, pw=pw, ph=ph):
            img = art.scaled(kind, int(pw * tp), int(ph * tp))
            sx, sy = _cam_screen(x + 0.5, y + 0.95)
            if kind == "tree":
                _shadow(dest, sx, sy, int(1.5 * tp), int(0.42 * tp))
            elif kind == "tent":
                _shadow(dest, sx, sy, int(2.2 * tp), int(0.55 * tp))
            _blit(dest, img, sx, sy)

        items.append(DrawItem(1, y + 0.85, x + 0.5, draw_prop))
    return items


def collect_world(
    bf: Battlefield,
    origin: Tuple[float, float],
    tp: float,
    engines: Sequence[PlacedEngine],
    player: Tuple[int, int],
    facing: str,
    gate_states: Dict[str, str],
    ghosts: Optional[Sequence[Tuple[PlacementResult, bool, str]]] = None,
) -> List[DrawItem]:
    _CAM["origin"] = origin
    _CAM["tp"] = tp
    key = (id(bf.plane), int(tp), tuple(sorted(gate_states.items())))
    static = _static_cache.get(key)
    if static is None:
        static = _build_static(bf, tp, gate_states)
        _static_cache[key] = static
    items = [it for it in static if _on_screen(it.foot_x, it.foot_y)]

    # Engines
    for eng in engines:
        w, h = eng.size()
        vw, vh = ENGINE_VIS.get(eng.engine_type, (3.0, 2.2))
        iw, ih = int(vw * tp), int(vh * tp)
        sprite = eng.engine_type
        if sprite not in {"ram", "trebuchet", "siege_tower", "ladder"}:
            sprite = "ram"
        foot_x = eng.x + w / 2
        foot_y = eng.y + h - 0.05

        def draw_eng(dest, sprite=sprite, iw=iw, ih=ih, foot_x=foot_x, foot_y=foot_y, rot=eng.rotation):
            img = art.scaled(sprite, iw, ih)
            if rot in (90, 270) and sprite != "trebuchet":
                img = pygame.transform.rotate(img, 0)  # already sized to rotated footprint
            sx, sy = _cam_screen(foot_x, foot_y)
            _shadow(dest, sx, sy, int(iw * 0.7), int(ih * 0.16))
            _blit(dest, img, sx, sy)

        items.append(DrawItem(1, foot_y, foot_x, draw_eng))

    # Ghosts — sprites tinted, footprint aligned
    for ghost in ghosts or ():
        result, valid, _kind = ghost
        if not result.tiles:
            continue
        xs = [t[0] for t in result.tiles]
        ys = [t[1] for t in result.tiles]
        x0, y0, x1, y1 = min(xs), min(ys), max(xs), max(ys)
        w, h = x1 - x0 + 1, y1 - y0 + 1
        kind = _kind if _kind in {"ram", "trebuchet", "siege_tower", "ladder"} else "ram"
        vw, vh = ENGINE_VIS.get(kind, (3.0, 2.2))
        iw, ih = int(vw * tp), int(vh * tp)
        col = (50, 190, 80) if valid else (210, 50, 40)
        foot_x, foot_y = (x0 + x1 + 1) / 2, y1 + 0.05

        def draw_ghost(dest, kind=kind, iw=iw, ih=ih, col=col, foot_x=foot_x, foot_y=foot_y,
                       x0=x0, y0=y0, w=w, h=h, valid=valid):
            img = art.tint(art.scaled(kind, iw, ih), col, 165)
            sx, sy = _cam_screen(foot_x, foot_y)
            fx, fy = _cam_screen(x0, y0)
            rec = pygame.Rect(fx, fy, int(w * tp), int(h * tp))
            overlay = pygame.Surface(rec.size, pygame.SRCALPHA)
            overlay.fill((*col, 45))
            dest.blit(overlay, rec.topleft)
            pygame.draw.rect(dest, col, rec, max(2, int(tp / 10)))
            _blit(dest, img, sx, sy)

        items.append(DrawItem(1, foot_y + 0.01, foot_x, draw_ghost))

    # Player
    px, py = player
    on_walk = bf.plane.cell(px, py) == "H"
    facing = facing if facing in {"n", "s", "e", "w"} else "s"
    pname = {"n": "player_n", "s": "player_s", "e": "player_e", "w": "player_w"}[facing]
    pw, ph = int(PLAYER_W * tp), int(PLAYER_H * tp)
    # Stand on wall-walk: raise the sprite toward the facade top
    elevate = WALL_VIS_H * 0.62 if on_walk else 0.0
    foot_y = py + 0.92
    layer = 2 if on_walk else 1

    def draw_player(dest, pname=pname, pw=pw, ph=ph, px=px, py=py, elevate=elevate):
        img = art.scaled(pname, pw, ph)
        sx, sy = _cam_screen(px + 0.5, py + 0.92)
        sy -= int(elevate * tp)
        _shadow(dest, sx, sy + int(0.05 * tp), int(1.3 * tp), int(0.4 * tp))
        _blit(dest, img, sx, sy)

    items.append(DrawItem(layer, foot_y + (0.4 if on_walk else 0), px + 0.5, draw_player))
    return items


def _marker(dest, origin, tp, x, y, label: str) -> None:
    sx, sy = world_to_screen(origin, tp, x, y)
    pygame.draw.polygon(dest, (232, 196, 96), [(sx, sy - 14), (sx - 7, sy - 2), (sx + 7, sy - 2)])
    pygame.draw.polygon(dest, (40, 28, 16), [(sx, sy - 14), (sx - 7, sy - 2), (sx + 7, sy - 2)], 1)
    img = _font(18).render(label, True, (255, 230, 186))
    back = pygame.Surface((img.get_width() + 10, img.get_height() + 4), pygame.SRCALPHA)
    back.fill((18, 12, 10, 170))
    dest.blit(back, (sx - back.get_width() // 2, sy - 34))
    dest.blit(img, (sx - img.get_width() // 2, sy - 32))


def render_world(
    bf: Battlefield,
    player: Tuple[int, int],
    engines: Sequence[PlacedEngine],
    title: str,
    subtitle: str,
    size: Tuple[int, int] = (1600, 900),
    tile_px: float = 30,
    facing: str = "s",
    ghosts: Optional[Sequence[Tuple[PlacementResult, bool, str]]] = None,
    ghost_reason: str = "",
    build_ui: bool = False,
    gate_states: Optional[Dict[str, str]] = None,
    markers: bool = True,
) -> pygame.Surface:
    t0 = time.perf_counter()
    states = gate_states or bf.gate_states
    surf = pygame.Surface(size)
    surf.fill((18, 24, 16))
    hud_top, hud_bot = 58, 56
    world = pygame.Surface((size[0], size[1] - hud_top - hud_bot))
    origin = camera_origin((player[0], player[1]), tile_px, world.get_size())
    _CAM["origin"] = origin
    _CAM["tp"] = tile_px
    _CAM["view"] = world.get_size()
    n_chunks = _draw_ground(world, bf, origin, tile_px)
    t1 = time.perf_counter()
    items = collect_world(bf, origin, tile_px, engines, player, facing, states, ghosts)
    items.sort(key=lambda it: (it.layer, it.foot_y, it.foot_x))
    drawn = 0
    for it in items:
        if not _on_screen(it.foot_x, it.foot_y):
            continue
        it.blit(world)
        drawn += 1
    t2 = time.perf_counter()

    if markers:
        for oid, label in (
            ("main_gate", "Main Gate"),
            ("north_gate", "North Postern"),
            ("west_gate", "West Postern"),
            ("east_gate", "East Postern"),
        ):
            rec = bf.plane.openings[oid].rect
            _marker(world, origin, tile_px, (rec[0] + rec[2]) / 2, rec[3] + 1.2, label)
        rec = bf.plane.landmarks["heal_defend"].rect
        _marker(world, origin, tile_px, (rec[0] + rec[2]) / 2, rec[3] + 0.6, "Healing")

    surf.blit(world, (0, hud_top))

    # HUD
    top = pygame.Surface((size[0], hud_top), pygame.SRCALPHA)
    top.fill((8, 8, 12, 210))
    surf.blit(top, (0, 0))
    surf.blit(_font(30).render(title, True, (255, 236, 190)), (16, 8))
    surf.blit(_font(20).render(subtitle, True, (220, 200, 160)), (16, 34))

    bot = pygame.Surface((size[0], hud_bot), pygame.SRCALPHA)
    bot.fill((8, 8, 10, 220))
    surf.blit(bot, (0, size[1] - hud_bot))
    extra = HINTS if build_ui else f"gameplay camera {tile_px:.0f}px/tile · player {player}"
    surf.blit(_font(20).render(f"{CAPTION}  ·  {extra}", True, (255, 228, 176)), (14, size[1] - 36))

    if build_ui:
        panel = pygame.Surface((520, 86), pygame.SRCALPHA)
        panel.fill((16, 12, 10, 200))
        if ghosts:
            valids = [g for g in ghosts if g[1]]
            invalids = [g for g in ghosts if not g[1]]
            y = 8
            if valids:
                panel.blit(_font(24).render(
                    f"VALID  ·  {SPECS.get(valids[0][2], SPECS['ram']).name}", True, (120, 220, 130)
                ), (12, y)); y += 24
            if invalids:
                reason = ghost_reason or invalids[0][0].reason
                panel.blit(_font(22).render(f"INVALID  ·  {reason}", True, (230, 110, 90)), (12, y)); y += 24
        panel.blit(_font(20).render(HINTS, True, (210, 190, 150)), (12, 64))
        surf.blit(panel, (16, hud_top + 12))

    # Minimap
    mm = 168
    mini = pygame.Surface((mm, mm))
    mini.fill((22, 26, 20))
    sx, sy = mm / WIDTH, mm / HEIGHT
    rec = bf.wall_box
    pygame.draw.rect(mini, (120, 110, 90), pygame.Rect(int(rec[0]*sx), int(rec[1]*sy),
                     int((rec[2]-rec[0]+1)*sx), int((rec[3]-rec[1]+1)*sy)), 1)
    rec = bf.keep_rect
    pygame.draw.rect(mini, (80, 80, 86), pygame.Rect(int(rec[0]*sx), int(rec[1]*sy),
                     int((rec[2]-rec[0]+1)*sx), int((rec[3]-rec[1]+1)*sy)))
    pygame.draw.circle(mini, (80, 140, 255), (int(player[0]*sx), int(player[1]*sy)), 3)
    surf.blit(mini, (size[0] - mm - 16, hud_top + 12))
    pygame.draw.rect(surf, (200, 160, 70), pygame.Rect(size[0] - mm - 16, hud_top + 12, mm, mm), 1)

    LAST_METRICS.clear()
    LAST_METRICS.update({
        "ground_ms": round((t1 - t0) * 1000, 2),
        "sprites_ms": round((t2 - t1) * 1000, 2),
        "total_ms": round((time.perf_counter() - t0) * 1000, 2),
        "chunks": n_chunks,
        "draw_items": len(items),
        "drawn_items": drawn,
        "tile_px": tile_px,
        "cached_chunks": len(_chunk_cache),
        "hud_ms": round((time.perf_counter() - t2) * 1000, 2),
    })
    return surf


def profile_walk(
    bf: Battlefield,
    path: Sequence[Tuple[int, int]],
    engines: Sequence[PlacedEngine],
    tile_px: float = 32,
    size: Tuple[int, int] = (1600, 900),
    facing: str = "n",
    prewarm: bool = True,
) -> dict:
    """Steady-state camera walk at a fixed zoom. Prefills visible ground chunks
    along the path, then times each full render_world call (not a reused surface)."""
    dummy = pygame.Surface(size)
    if prewarm:
        for pos in path:
            origin = camera_origin((pos[0], pos[1]), tile_px, (size[0], size[1] - 114))
            _draw_ground(dummy, bf, origin, tile_px)
        # one full frame to fill sprite / font / static caches
        render_world(bf, path[0], engines, "walk", "prewarm", size=size, tile_px=tile_px, facing=facing, markers=False)
    times = []
    parts = []
    for pos in path:
        render_world(bf, pos, engines, "walk", "steady", size=size, tile_px=tile_px, facing=facing, markers=False)
        times.append(float(LAST_METRICS["total_ms"]))
        parts.append((float(LAST_METRICS["ground_ms"]), float(LAST_METRICS["sprites_ms"]), float(LAST_METRICS.get("hud_ms", 0))))
    srt = sorted(times)

    def pct(p):
        if not srt:
            return 0.0
        idx = min(len(srt) - 1, max(0, int(round((p / 100.0) * (len(srt) - 1)))))
        return srt[idx]

    return {
        "n": len(times),
        "tile_px": tile_px,
        "size": size,
        "mean_ms": round(sum(times) / max(1, len(times)), 2),
        "p50_ms": round(pct(50), 2),
        "p95_ms": round(pct(95), 2),
        "min_ms": round(min(times), 2) if times else 0.0,
        "max_ms": round(max(times), 2) if times else 0.0,
        "mean_ground_ms": round(sum(g for g, _, _ in parts) / max(1, len(parts)), 2),
        "mean_sprites_ms": round(sum(s for _, s, _ in parts) / max(1, len(parts)), 2),
        "mean_hud_ms": round(sum(h for _, _, h in parts) / max(1, len(parts)), 2),
        "cached_chunks": len(_chunk_cache),
    }


def visual_scale() -> dict:
    """Documented world-unit sizes for tests and review."""
    return {
        "tile_meters": 1.6,
        "tex_tiles": TEX_TILES,
        "player_w_tiles": PLAYER_W,
        "player_h_tiles": PLAYER_H,
        "ram_vis_tiles": ENGINE_VIS["ram"],
        "wall_h_tiles": WALL_VIS_H,
        "keep_h_tiles": KEEP_VIS_H,
        "ram_to_player_w": round(ENGINE_VIS["ram"][0] / PLAYER_W, 2),
    }
