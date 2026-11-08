"""M8 angled gameplay renderer.

One SSW orthographic camera for ground, curtain, towers, keep, engines and
the avatar. Ground is the existing tile-accurate terrain warped onto the
shared plane; architecture is extruded from the live collision grid so
openings, breaches and wall-walks stay aligned. This is still the Pygame
runtime — not a new engine.
"""

from __future__ import annotations

import hashlib
import json
import math
import time
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple

import numpy as np
import cv2
import pygame

from . import angled_proj as P
from . import art
from . import world_view as WV
from .constants import HEIGHT, WIDTH
from .layout import Battlefield, Rect
from .placement import PlacedEngine, PlacementResult, SPECS, rotated_size

CAPTION = "DUMMY pygame | isolated King's Castle M21 angled | NOT live GUI | NOT the shipped game client"
HINTS = "R Rotate   Enter Place   Esc Cancel   [ ] Cycle engine"

WALL_H = 10.2
TOWER_H = 16.5
KEEP_H = 22.0
GATE_H = 13.4
MERLON_H = 1.25
PLAYER_W, PLAYER_H = 0.74, 1.88
ENGINE_H = {"ram": 1.7, "trebuchet": 3.6, "siege_tower": 6.2, "ladder": 3.4}

LAST_METRICS: Dict[str, float] = {}

CACHE_CELL = 12
CACHE_PAD = 1.40
CACHE_LIMIT = 5
CACHE_MARGIN = 48
CACHE_FOLLOW = 36
TOPO_TP = 8


_tex_cache: Dict[str, np.ndarray] = {}
_face_cache: Dict[tuple, list] = {}
_view_cache: Dict[tuple, tuple] = {}
_topo_cache: Dict[int, tuple] = {}
_scale_cache: Dict[tuple, pygame.Surface] = {}
_font_cache: Dict[int, pygame.font.Font] = {}
BAKED_DIR = Path(__file__).resolve().parent.parent / "assets" / "baked_m9"
_baked: Dict[str, tuple] = {}
_baked_rev = 0


def _font(size: int) -> pygame.font.Font:
    if size not in _font_cache:
        _font_cache[size] = pygame.font.Font(None, size)
    return _font_cache[size]


def load_baked(name: str):
    if name not in _baked:
        img = pygame.image.load(str(BAKED_DIR / f"{name}.png")).convert_alpha()
        meta = json.loads((BAKED_DIR / f"{name}.json").read_text())
        _baked[name] = (img, meta)
    return _baked[name]


def invalidate_static_visuals() -> None:
    """Drop cached static iso layers and scaled baked sprites.

    `draw_baked_buildings` paints towers/walls into `_view_cache`. The cache key
    is camera/zoom/gate-state, not sprite identity, so a hot-swap of `_baked`
    would otherwise keep showing the previous paint (same look = cache hit).
    Gameplay never swaps sprites; tests and specimen harnesses must call this
    (or `replace_baked`) after changing baked art.
    """
    global _baked_rev
    _baked_rev += 1
    _view_cache.clear()
    _scale_cache.clear()


def replace_baked(name: str, img, meta: dict) -> None:
    """In-memory baked-sprite swap for experiments/tests. Invalidates static cache."""
    _baked[name] = (img, meta)
    invalidate_static_visuals()


def _px_per_tile(meta: dict) -> float:
    if meta.get("px_per_tile"):
        return float(meta["px_per_tile"])
    res = meta.get("res") or meta.get("size")
    ortho = float(meta.get("ortho_scale") or 0.0)
    if res and ortho:
        return float(res[0]) / ortho
    return float(meta.get("bake_scale") or 36.0)


def blit_baked(dest, name, wx, wy, origin, scale, screen_o, tint=None, clip=None):
    img, meta = load_baked(name)
    sx, sy, depth = P.project(wx, wy, 0.0, origin, scale, screen_o)
    f = scale / _px_per_tile(meta)
    fpx, fpy = meta["foot_px"]
    w = max(2, int(round(img.get_width() * f)))
    h = max(2, int(round(img.get_height() * f)))
    sk = (name, w, h)
    spr = _scale_cache.get(sk)
    if spr is None:
        spr = pygame.transform.smoothscale(img, (w, h))
        _scale_cache[sk] = spr
        while len(_scale_cache) > 48:
            _scale_cache.pop(next(iter(_scale_cache)))
    dx = int(sx - fpx * f)
    dy = int(sy - fpy * f)
    if clip is not None:
        cx, cy, cw, ch = clip
        if dx + w < cx or dy + h < cy or dx > cx + cw or dy > cy + ch:
            return depth
    if tint is not None:
        veil = pygame.Surface(spr.get_size(), pygame.SRCALPHA)
        veil.fill((*tint, 90))
        spr = spr.copy()
        spr.blit(veil, (0, 0), special_flags=pygame.BLEND_RGBA_ADD)
    dest.blit(spr, (dx, dy))
    return depth


def draw_baked_buildings(dest, bf, states, origin, scale, screen_o, clip=None):
    for key in ("nw_tower", "ne_tower", "sw_tower", "se_tower"):
        rec = bf.plane.landmarks[key].rect
        cx = (rec[0] + rec[2] + 1) / 2.0
        cy = (rec[1] + rec[3] + 1) / 2.0
        blit_baked(dest, "tower", cx, cy, origin, scale, screen_o, clip=clip)
    kr = bf.keep_rect
    kname = "keep_open" if states.get("keep_doors", "intact") == "destroyed" and (BAKED_DIR / "keep_open.png").is_file() else "keep"
    blit_baked(dest, kname, (kr[0] + kr[2] + 1) / 2.0, (kr[1] + kr[3] + 1) / 2.0, origin, scale, screen_o, clip=clip)
    rec = bf.plane.openings["main_gate"].rect
    gname = "gatehouse_destroyed" if states.get("main_gate", "intact") == "destroyed" else "gatehouse"
    blit_baked(dest, gname, (rec[0] + rec[2] + 1) / 2.0, (rec[1] + rec[3] + 1) / 2.0, origin, scale, screen_o, clip=clip)
    wx0, wy0, wx1, wy1 = bf.wall_box
    gcx = (rec[0] + rec[2] + 1) / 2.0
    cy = wy1 - 2.0
    if (BAKED_DIR / "wall_south_long.png").is_file():
        blit_baked(dest, "wall_south_long", gcx - 32.0, cy, origin, scale, screen_o, clip=clip)
        blit_baked(dest, "wall_south_long", gcx + 32.0, cy, origin, scale, screen_o, clip=clip)
    else:
        gx0, gx1 = gcx - 14.0, gcx + 14.0
        x = wx0 + 14.0
        while x + 3.5 <= wx1 - 10.0:
            if not (gx0 <= x <= gx1):
                blit_baked(dest, "wall_south", x, cy, origin, scale, screen_o, clip=clip)
            x += 8.0
    # Other curtains: tiled 16-tile spans, leaving posterns and corner towers.
    def _tile_span(name, ax, ay0, step, limit, skip=None):
        if not (BAKED_DIR / f"{name}.png").is_file():
            return
        a = ay0
        while a + 6 <= limit:
            if skip and skip[0] <= a <= skip[1]:
                a += step
                continue
            if name in {"wall_west", "wall_east"}:
                blit_baked(dest, name, ax, a, origin, scale, screen_o, clip=clip)
            else:
                blit_baked(dest, name, a, ax, origin, scale, screen_o, clip=clip)
            a += step
    wg = bf.plane.openings["west_gate"].rect
    eg = bf.plane.openings["east_gate"].rect
    ng = bf.plane.openings["north_gate"].rect
    _tile_span("wall_west", wx0 + 2.0, wy0 + 14.0, 16.0, wy1 - 10.0, (wg[1] - 3, wg[3] + 3))
    _tile_span("wall_east", wx1 - 2.0, wy0 + 14.0, 16.0, wy1 - 10.0, (eg[1] - 3, eg[3] + 3))
    _tile_span("wall_north", wy0 + 2.0, wx0 + 14.0, 16.0, wx1 - 10.0, (ng[0] - 3, ng[2] + 3))


def _tex(name: str) -> np.ndarray:
    """RGB uint8 array in cv2 layout (y, x, 3)."""
    if name not in _tex_cache:
        if name == "masonry":
            pref = art.SPRITE_DIR / "masonry_m12.png"
            alt = art.SPRITE_DIR / "masonry_m11.png"
            surf = pygame.image.load(str(pref if pref.is_file() else alt if alt.is_file() else art.SPRITE_DIR / "masonry_m8.png")).convert()
        elif name == "timber":
            surf = pygame.image.load(str(art.SPRITE_DIR / "timber_m8.png")).convert()
        elif name == "door_wood":
            # Readable daylight oak for portal leaves. timber_m8 mean~41 is near-black
            # once west/north shade is applied, which made posterns look like solid slabs.
            h = w = 256
            yy, xx = np.indices((h, w))
            plank = xx // 36
            base = np.array([138.0, 100.0, 72.0], dtype=np.float32)
            jitter = ((plank * 37 + 13) % 19 - 9).astype(np.float32)
            rgb = base + jitter[..., None] * np.array([2.4, 1.7, 1.1], dtype=np.float32)
            rgb += (np.sin(yy * 0.31 + plank * 0.8) * 7.0)[..., None]
            seam = (xx % 36) < 2
            rgb[seam] *= 0.58
            rail = ((yy % 72) < 3) | ((yy % 72) > 69)
            rgb[rail] *= 0.72
            _tex_cache[name] = np.ascontiguousarray(np.clip(rgb, 0, 255).astype(np.uint8))
            return _tex_cache[name]
        elif name == "wall_top":
            surf = art.load("wall_top")
        elif name == "planks":
            surf = art.load("planks")
        else:
            surf = pygame.image.load(str(art.SPRITE_DIR / "masonry_m8.png")).convert()
        arr = pygame.surfarray.array3d(surf)  # x,y,3
        _tex_cache[name] = np.ascontiguousarray(np.transpose(arr, (1, 0, 2)))
    return _tex_cache[name]


def _shade_for_normal(nx: float, ny: float, nz: float) -> Tuple[float, float, float]:
    # Light from the south-southwest and above — warm on south faces, cooler on west/north.
    lx, ly, lz = -0.18, 0.52, 0.84
    ndot = max(0.0, nx * lx + ny * ly + nz * lz)
    amb = 0.52
    s = amb + (1.0 - amb) * ndot
    if ny > 0.5:  # south
        tint = (1.08, 0.98, 0.88)
    elif nx < -0.5:  # west
        tint = (0.90, 0.92, 0.98)
    elif nx > 0.5:  # east
        tint = (1.02, 0.97, 0.88)
    elif ny < -0.5:  # north
        tint = (0.78, 0.80, 0.86)
    else:  # top
        tint = (0.94, 0.92, 0.88)
    return (s * tint[0], s * tint[1], s * tint[2])


class Face:
    __slots__ = ("pts", "u_span", "v_span", "tex", "shade", "bias")

    def __init__(self, pts, u_span, v_span, tex, shade, bias=0.0):
        self.pts = pts  # 4 x (x,y,z) BL, BR, TR, TL
        self.u_span = float(u_span)
        self.v_span = float(v_span)
        self.tex = tex
        self.shade = shade
        self.bias = bias


def _face(pts, tex, nx, ny, nz, bias=0.0) -> Face:
    # u along p0->p1, v along p0->p3 (or height)
    p0, p1, p2, p3 = pts
    u = math.dist(p0, p1)
    v = math.dist(p0, p3)
    return Face(pts, max(0.25, u), max(0.25, v), tex, _shade_for_normal(nx, ny, nz), bias)


def _box_faces(x0, y0, x1, y1, z0, z1, tex="masonry", top_tex=None) -> List[Face]:
    top_tex = top_tex or tex
    faces = [
        _face([(x0, y1, z0), (x1, y1, z0), (x1, y1, z1), (x0, y1, z1)], tex, 0, 1, 0),   # S
        _face([(x1, y0, z0), (x0, y0, z0), (x0, y0, z1), (x1, y0, z1)], tex, 0, -1, 0),  # N
        _face([(x0, y0, z0), (x0, y1, z0), (x0, y1, z1), (x0, y0, z1)], tex, -1, 0, 0),  # W
        _face([(x1, y1, z0), (x1, y0, z0), (x1, y0, z1), (x1, y1, z1)], tex, 1, 0, 0),   # E
        _face([(x0, y0, z1), (x1, y0, z1), (x1, y1, z1), (x0, y1, z1)], top_tex, 0, 0, 1),
    ]
    return faces


def _merlons_on_box(x0, y0, x1, y1, z, step=1.8) -> List[Face]:
    out: List[Face] = []
    # south edge
    x = x0 + 0.15
    while x + 0.7 <= x1:
        out.extend(_box_faces(x, y1 - 0.45, min(x + 0.7, x1), y1, z, z + MERLON_H))
        x += step
    # north
    x = x0 + 0.15
    while x + 0.7 <= x1:
        out.extend(_box_faces(x, y0, min(x + 0.7, x1), y0 + 0.45, z, z + MERLON_H))
        x += step
    return out


def _rect_tiles(rec: Rect) -> List[Tuple[int, int]]:
    return [(x, y) for y in range(rec[1], rec[3] + 1) for x in range(rec[0], rec[2] + 1)]


def _opening_tiles(bf: Battlefield, states: Dict[str, str], only_destroyed: bool = False) -> set:
    tiles = set()
    for oid, op in bf.plane.openings.items():
        st = states.get(oid, op.default_state)
        if only_destroyed and st != "destroyed":
            continue
        if not only_destroyed and st == "destroyed":
            continue
        for y in range(op.rect[1], op.rect[3] + 1):
            for x in range(op.rect[0], op.rect[2] + 1):
                tiles.add((x, y))
    return tiles



def _lift_door_shade(faces: list) -> list:
    """West/north Lambertian shade would crush even mid-brown wood to near-black."""
    for f in faces:
        if f.tex == "door_wood":
            f.shade = (
                min(1.48, f.shade[0] * 1.30 + 0.08),
                min(1.36, f.shade[1] * 1.20 + 0.05),
                min(1.24, f.shade[2] * 1.08 + 0.02),
            )
    return faces


def _paneled_leaf(x0, y0, x1, y1, z0, z1, inset_dir: str) -> list:
    """Two-panel timber leaf: frame plus recessed boards, not a flat slab."""
    out = _box_faces(x0, y0, x1, y1, z0, z1, "door_wood", "door_wood")
    zh = z1 - z0
    z_rail = z0 + zh * 0.48
    if inset_dir == "+x":
        ix0 = x0 + 0.08
        out += _box_faces(ix0, y0 + 0.13, x1, y1 - 0.13, z0 + 0.20, z_rail - 0.10, "door_wood")
        out += _box_faces(ix0, y0 + 0.13, x1, y1 - 0.13, z_rail + 0.10, z1 - 0.26, "door_wood")
    elif inset_dir == "-x":
        ix1 = x1 - 0.08
        out += _box_faces(x0, y0 + 0.13, ix1, y1 - 0.13, z0 + 0.20, z_rail - 0.10, "door_wood")
        out += _box_faces(x0, y0 + 0.13, ix1, y1 - 0.13, z_rail + 0.10, z1 - 0.26, "door_wood")
    elif inset_dir == "+y":
        iy0 = y0 + 0.08
        out += _box_faces(x0 + 0.13, iy0, x1 - 0.13, y1, z0 + 0.20, z_rail - 0.10, "door_wood")
        out += _box_faces(x0 + 0.13, iy0, x1 - 0.13, y1, z_rail + 0.10, z1 - 0.26, "door_wood")
    else:
        iy1 = y1 - 0.08
        out += _box_faces(x0 + 0.13, y0, x1 - 0.13, iy1, z0 + 0.20, z_rail - 0.10, "door_wood")
        out += _box_faces(x0 + 0.13, y0, x1 - 0.13, iy1, z_rail + 0.10, z1 - 0.26, "door_wood")
    return _lift_door_shade(out)


def _portal_faces(rec, side: str, destroyed: bool) -> list:
    """Recessed postern: masonry jambs/lintel and inset paneled leaves, not a full-height slab."""
    x0, y0 = rec[0], rec[1]
    x1, y1 = rec[2] + 1, rec[3] + 1
    z_d, z_w = 5.35, WALL_H
    jamb = 0.72
    inset = 0.34
    thick = 0.28
    out: list = []
    if side == "w":
        out += _box_faces(x0 - 0.16, y0 - 0.10, x0 + 0.58, y0 + jamb, 0, z_w, "masonry")
        out += _box_faces(x0 - 0.16, y1 - jamb, x0 + 0.58, y1 + 0.10, 0, z_w, "masonry")
        out += _box_faces(x0 - 0.16, y0, x0 + 0.58, y1, z_d, z_w, "masonry")
        out += _box_faces(x0, y0, x1, y0 + 0.36, 0.0, z_d, "masonry")
        out += _box_faces(x0, y1 - 0.36, x1, y1, 0.0, z_d, "masonry")
        out += _box_faces(x0, y0, x1, y1, z_d - 0.26, z_d, "masonry")
        if not destroyed:
            mid = 0.5 * (y0 + y1)
            out += _paneled_leaf(x0 + inset, y0 + jamb * 0.72, x0 + inset + thick, mid - 0.04, 0.08, z_d - 0.14, "+x")
            out += _paneled_leaf(x0 + inset, mid + 0.04, x0 + inset + thick, y1 - jamb * 0.72, 0.08, z_d - 0.14, "+x")
    elif side == "e":
        out += _box_faces(x1 - 0.58, y0 - 0.10, x1 + 0.16, y0 + jamb, 0, z_w, "masonry")
        out += _box_faces(x1 - 0.58, y1 - jamb, x1 + 0.16, y1 + 0.10, 0, z_w, "masonry")
        out += _box_faces(x1 - 0.58, y0, x1 + 0.16, y1, z_d, z_w, "masonry")
        out += _box_faces(x0, y0, x1, y0 + 0.36, 0.0, z_d, "masonry")
        out += _box_faces(x0, y1 - 0.36, x1, y1, 0.0, z_d, "masonry")
        out += _box_faces(x0, y0, x1, y1, z_d - 0.26, z_d, "masonry")
        if not destroyed:
            mid = 0.5 * (y0 + y1)
            out += _paneled_leaf(x1 - inset - thick, y0 + jamb * 0.72, x1 - inset, mid - 0.04, 0.08, z_d - 0.14, "-x")
            out += _paneled_leaf(x1 - inset - thick, mid + 0.04, x1 - inset, y1 - jamb * 0.72, 0.08, z_d - 0.14, "-x")
    elif side == "n":
        out += _box_faces(x0 - 0.10, y0 - 0.16, x0 + jamb, y0 + 0.58, 0, z_w, "masonry")
        out += _box_faces(x1 - jamb, y0 - 0.16, x1 + 0.10, y0 + 0.58, 0, z_w, "masonry")
        out += _box_faces(x0, y0 - 0.16, x1, y0 + 0.58, z_d, z_w, "masonry")
        out += _box_faces(x0, y0, x0 + 0.36, y1, 0.0, z_d, "masonry")
        out += _box_faces(x1 - 0.36, y0, x1, y1, 0.0, z_d, "masonry")
        out += _box_faces(x0, y0, x1, y1, z_d - 0.26, z_d, "masonry")
        if not destroyed:
            mid = 0.5 * (x0 + x1)
            out += _paneled_leaf(x0 + jamb * 0.72, y0 + inset, mid - 0.04, y0 + inset + thick, 0.08, z_d - 0.14, "+y")
            out += _paneled_leaf(mid + 0.04, y0 + inset, x1 - jamb * 0.72, y0 + inset + thick, 0.08, z_d - 0.14, "+y")
    return out


def _collect_static_faces(bf: Battlefield, states: Dict[str, str]) -> List[Face]:
    key = (id(bf.plane), tuple(sorted(states.items())))
    cached = _face_cache.get(key)
    if cached is not None:
        return cached

    grid = bf.plane.grid
    kr = bf.keep_rect
    structure = WV._structure_tiles(bf)
    destroyed = _opening_tiles(bf, states, only_destroyed=True)
    intact_g = _opening_tiles(bf, states, only_destroyed=False)

    def inb(x, y):
        return 0 <= x < WIDTH and 0 <= y < HEIGHT

    def is_keep(x, y):
        return kr[0] <= x <= kr[2] and kr[1] <= y <= kr[3] and inb(x, y) and grid[y][x] == "#"

    def solid(x, y):
        if not inb(x, y) or (x, y) in destroyed:
            return False
        if (x, y) in structure:
            return True
        ch = grid[y][x]
        if ch in {"#", "H"}:
            return True
        if (x, y) in intact_g:
            return True
        return False

    faces: List[Face] = []

    def style(x, y, axis):
        if not solid(x, y) or (x, y) in structure or is_keep(x, y):
            return None
        for oid, op in bf.plane.openings.items():
            if states.get(oid, op.default_state) == "destroyed":
                continue
            rec = op.rect
            if not (rec[0] <= x <= rec[2] and rec[1] <= y <= rec[3]):
                continue
            if oid in {"main_gate", "keep_doors", "west_gate", "east_gate", "north_gate"}:
                return None
        # Baked curtains replace the outer extrusion on each side.
        if axis == "s" and y >= bf.wall_box[3] - 6:
            return None
        if axis == "n" and y <= bf.wall_box[1] + 5:
            return None
        if axis == "w" and x <= bf.wall_box[0] + 5:
            return None
        if axis == "e" and x >= bf.wall_box[2] - 5:
            return None
        return ("masonry", WALL_H)

    def scan(axis: str):
        if axis in {"s", "n"}:
            for y in range(HEIGHT):
                x = 0
                ny = y + 1 if axis == "s" else y - 1
                while x < WIDTH:
                    k = style(x, y, axis)
                    if k is None or solid(x, ny):
                        x += 1
                        continue
                    x0 = x
                    while x < WIDTH and style(x, y, axis) == k and not solid(x, ny) and (x - x0) < 18:
                        x += 1
                    tex, z1 = k
                    if axis == "s":
                        faces.append(_face([(x0, y + 1, 0), (x, y + 1, 0), (x, y + 1, z1), (x0, y + 1, z1)], tex, 0, 1, 0))
                    else:
                        faces.append(_face([(x, y, 0), (x0, y, 0), (x0, y, z1), (x, y, z1)], tex, 0, -1, 0))
        else:
            for x in range(WIDTH):
                y = 0
                nx = x - 1 if axis == "w" else x + 1
                while y < HEIGHT:
                    k = style(x, y, axis)
                    if k is None or solid(nx, y):
                        y += 1
                        continue
                    y0 = y
                    while y < HEIGHT and style(x, y, axis) == k and not solid(nx, y) and (y - y0) < 18:
                        y += 1
                    tex, z1 = k
                    if axis == "w":
                        faces.append(_face([(x, y0, 0), (x, y, 0), (x, y, z1), (x, y0, z1)], tex, -1, 0, 0))
                    else:
                        faces.append(_face([(x + 1, y, 0), (x + 1, y0, 0), (x + 1, y0, z1), (x + 1, y, z1)], tex, 1, 0, 0))

    scan("s")
    scan("n")
    scan("w")
    scan("e")

    for oid, side in (("west_gate", "w"), ("east_gate", "e"), ("north_gate", "n")):
        op = bf.plane.openings[oid]
        dest = states.get(oid, op.default_state) == "destroyed"
        faces.extend(_portal_faces(op.rect, side, dest))

    # Tops (merged runs) — wall-walk / cap
    for y in range(HEIGHT):
        x = 0
        while x < WIDTH:
            if not solid(x, y) or (x, y) in structure or is_keep(x, y) or y >= bf.wall_box[3] - 5:
                x += 1
                continue
            if grid[y][x] == "G":
                x += 1
                continue
            gate = False
            x0 = x
            while x < WIDTH and solid(x, y) and (x, y) not in structure and not is_keep(x, y) and ((grid[y][x] == "G") == gate):
                x += 1
            z1 = GATE_H if gate else WALL_H
            faces.append(_face([(x0, y, z1), (x, y, z1), (x, y + 1, z1), (x0, y + 1, z1)], "wall_top", 0, 0, 1))

    _face_cache[key] = faces
    return faces


_lut_cache: Dict[tuple, np.ndarray] = {}
_PATCH_PAD = 3


def _shade_lut(shade) -> np.ndarray:
    key = tuple(float(s) for s in shade)
    lut = _lut_cache.get(key)
    if lut is None:
        v = np.arange(256, dtype=np.float32)[:, None]
        s = np.array(key, dtype=np.float32)[None, :]
        lut = np.clip(v * s, 0, 255).astype(np.uint8).reshape(1, 256, 3)
        _lut_cache[key] = lut
    return lut


def _blit_face(dest_rgb: np.ndarray, face: Face, origin, scale, screen_o, view) -> None:
    import cv2
    pts = []
    for p in face.pts:
        sx, sy, _ = P.project(p[0], p[1], p[2], origin, scale, screen_o)
        pts.append((sx, sy))
    xs = [p[0] for p in pts]
    ys = [p[1] for p in pts]
    minx = int(math.floor(min(xs))) - 1
    maxx = int(math.ceil(max(xs))) + 1
    miny = int(math.floor(min(ys))) - 1
    maxy = int(math.ceil(max(ys))) + 1
    if len(view) == 4:
        vx, vy, vw, vh = view
    else:
        vx, vy, vw, vh = 0, 0, view[0], view[1]
    if maxx < vx or maxy < vy or minx >= vx + vw or miny >= vy + vh:
        return
    minx = max(vx, minx)
    miny = max(vy, miny)
    maxx = min(vx + vw, maxx)
    maxy = min(vy + vh, maxy)
    pw, ph = maxx - minx, maxy - miny
    if pw < 2 or ph < 2:
        return
    tw = max(12, min(256, int(face.u_span * 96)))
    th = max(12, min(256, int(face.v_span * 96)))
    src = _tex(face.tex)
    sh, sw = src.shape[0], src.shape[1]
    # wrap-crop a tw x th window
    ox = int(abs(hash((round(face.pts[0][0], 1), round(face.pts[0][1], 1), face.tex))) % max(1, sw))
    oy = int(abs(hash((round(face.pts[0][2], 1), face.tex, 7))) % max(1, sh))
    src_tri = np.float32([[0, th - 1], [tw - 1, th - 1], [0, 0]])
    dst_tri = np.float32([
        [pts[0][0] - minx, pts[0][1] - miny],
        [pts[1][0] - minx, pts[1][1] - miny],
        [pts[3][0] - minx, pts[3][1] - miny],
    ])
    M = cv2.getAffineTransform(src_tri, dst_tri)
    # Only texels that the clipped destination can sample need to be shaded.
    # M is unchanged, so warpAffine reads exactly the same values as before
    # (bit-identical output); untouched texels are never sampled.
    u0, v0, u1, v1 = 0, 0, tw, th
    det = float(M[0, 0] * M[1, 1] - M[0, 1] * M[1, 0])
    if abs(det) > 1e-9:
        Mi = cv2.invertAffineTransform(M)
        cx = np.array([0.0, pw - 1.0, 0.0, pw - 1.0])
        cy = np.array([0.0, 0.0, ph - 1.0, ph - 1.0])
        su = Mi[0, 0] * cx + Mi[0, 1] * cy + Mi[0, 2]
        sv = Mi[1, 0] * cx + Mi[1, 1] * cy + Mi[1, 2]
        u0 = max(0, int(math.floor(su.min())) - _PATCH_PAD)
        u1 = min(tw, int(math.ceil(su.max())) + _PATCH_PAD + 1)
        v0 = max(0, int(math.floor(sv.min())) - _PATCH_PAD)
        v1 = min(th, int(math.ceil(sv.max())) + _PATCH_PAD + 1)
        if u1 <= u0 or v1 <= v0:
            u0, v0, u1, v1 = 0, 0, tw, th
    full = (u1 - u0) * (v1 - v0) >= int(0.7 * tw * th)
    if full:
        u0, v0, u1, v1 = 0, 0, tw, th
    ys0, xs0 = oy + v0, ox + u0
    hh, ww = v1 - v0, u1 - u0
    if ys0 + hh <= sh and xs0 + ww <= sw:
        raw = src[ys0:ys0 + hh, xs0:xs0 + ww]
    else:
        yy = (np.arange(v0, v1) + oy) % sh
        xx = (np.arange(u0, u1) + ox) % sw
        raw = src[np.ix_(yy, xx)]
    # Exact per-channel LUT of clip(float32(v) * float32(shade)) -> uint8.
    shaded = cv2.LUT(np.ascontiguousarray(raw), _shade_lut(face.shade))
    if full:
        patch = shaded
    else:
        patch = np.zeros((th, tw, 3), np.uint8)
        patch[v0:v1, u0:u1] = shaded
    warped = cv2.warpAffine(patch, M, (pw, ph), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_CONSTANT)
    mask = np.zeros((ph, pw), np.uint8)
    poly = np.int32([[(p[0] - minx, p[1] - miny) for p in pts]])
    cv2.fillConvexPoly(mask, poly, 255)
    # dest_rgb is (x,y,3)
    roi = dest_rgb[minx:maxx, miny:maxy]
    # Masked in-place copy (same result as roi[mk] = wr[mk], ~4x cheaper).
    np.copyto(roi, warped.transpose(1, 0, 2), where=(mask.T > 0)[:, :, None])


def _draw_sky(surf: pygame.Surface) -> None:
    _draw_sky_rect(surf, (0, 0, surf.get_width(), surf.get_height()))


def _draw_sky_rect(surf: pygame.Surface, rect) -> None:
    x, y, w, h = [int(v) for v in rect]
    if w < 1 or h < 1:
        return
    arr = pygame.surfarray.pixels3d(surf)
    H = max(1, surf.get_height() - 1)
    ys = (np.arange(y, y + h, dtype=np.float32) / H)
    top = np.array([62, 68, 76], dtype=np.float32)
    bot = np.array([88, 86, 80], dtype=np.float32)
    col = (top[None, :] * (1 - ys[:, None]) + bot[None, :] * ys[:, None]).astype(np.uint8)
    arr[x:x + w, y:y + h] = col[None, :, :]
    del arr


def _fbm_yx(h, w, rng, octaves=5, base=18.0):
    # Build at half res then upsample — same look, much cheaper on first load.
    hh, ww = max(8, (h + 1) // 2), max(8, (w + 1) // 2)
    acc = np.zeros((hh, ww), dtype=np.float32)
    amp = 1.0
    tot = 0.0
    scale = float(base)
    for _ in range(octaves):
        sh = (max(4, int(hh / scale)), max(4, int(ww / scale)))
        n = rng.randn(*sh).astype(np.float32)
        acc += amp * cv2.resize(n, (ww, hh), interpolation=cv2.INTER_LINEAR)
        tot += amp
        amp *= 0.52
        scale = max(3.0, scale * 0.48)
    acc /= max(tot, 1e-6)
    return cv2.resize(acc, (w, h), interpolation=cv2.INTER_LINEAR)


def _sample_wrap(img, map_x, map_y):
    return cv2.remap(img, map_x, map_y, interpolation=cv2.INTER_LINEAR, borderMode=cv2.BORDER_WRAP)


def _soft_mask(tile, tp, edge_n, feather=1.15):
    """tile: (HEIGHT, WIDTH) float; returns (hpx, wpx) 0..1 with noise-warped edges."""
    hpx, wpx = tile.shape[0] * tp, tile.shape[1] * tp
    raw = cv2.resize(tile.astype(np.float32), (wpx, hpx), interpolation=cv2.INTER_LINEAR)
    binary = (raw > 0.45).astype(np.uint8)
    if int(binary.max()) == 0:
        return raw * 0.0
    dist_in = cv2.distanceTransform(binary, cv2.DIST_L2, 3)
    dist_out = cv2.distanceTransform(1 - binary, cv2.DIST_L2, 3)
    sd = (dist_in - dist_out) / float(tp) + 0.42 * edge_n
    return 1.0 / (1.0 + np.exp(-np.clip(sd * (2.4 / feather), -12.0, 12.0)))


def _topo_disk_paths():
    root = Path(__file__).resolve().parent.parent / "assets" / "sprites"
    return root / "terrain_topo_v1.png", root / "terrain_topo_v1.json"


def _topo_fingerprint(bf: Battlefield) -> str:
    grid = np.asarray(bf.plane.grid)
    payload = grid.tobytes() + repr(tuple(bf.wall_box)).encode() + f"|tp{TOPO_TP}|seed19".encode()
    return hashlib.sha1(payload).hexdigest()


def _try_load_topo_disk(bf: Battlefield):
    png, meta_p = _topo_disk_paths()
    if not png.is_file() or not meta_p.is_file():
        return None
    try:
        meta = json.loads(meta_p.read_text())
    except Exception:
        return None
    if meta.get("sha") != _topo_fingerprint(bf):
        return None
    if int(meta.get("tp", -1)) != TOPO_TP:
        return None
    import cv2
    arr = cv2.imread(str(png), cv2.IMREAD_COLOR)
    if arr is None:
        return None
    arr = cv2.cvtColor(arr, cv2.COLOR_BGR2RGB)
    want = (HEIGHT * TOPO_TP, WIDTH * TOPO_TP, 3)
    if arr.shape != want:
        return None
    n = (WIDTH // 16) * (HEIGHT // 16)
    return np.ascontiguousarray(arr), TOPO_TP, n


def _write_topo_disk(bf: Battlefield, arr) -> None:
    png, meta_p = _topo_disk_paths()
    png.parent.mkdir(parents=True, exist_ok=True)
    import cv2
    cv2.imwrite(str(png), cv2.cvtColor(arr, cv2.COLOR_RGB2BGR))
    meta_p.write_text(json.dumps({
        "sha": _topo_fingerprint(bf),
        "tp": TOPO_TP,
        "shape": list(arr.shape),
        "note": "Derived M17 terrain cache; identical to runtime _terrain_topo output.",
    }, indent=2))


def _terrain_topo(bf: Battlefield):
    """Non-periodic muddy battlefield; roads as packed earth with centerline ruts."""
    key = id(bf.plane)
    cached = _topo_cache.get(key)
    if cached is not None:
        return cached
    disk = _try_load_topo_disk(bf)
    if disk is not None:
        _topo_cache[key] = disk
        return disk
    import cv2
    from PIL import Image
    from . import art as _art
    tp = TOPO_TP
    hpx, wpx = HEIGHT * tp, WIDTH * tp
    rng = np.random.RandomState(19)
    # Tile class masks (y, x)
    grid = bf.plane.grid
    chars = np.asarray(grid)
    road_t = ((chars == "=") | (chars == "G")).astype(np.float32)
    court_t = (chars == ",").astype(np.float32)
    water_t = (chars == "~").astype(np.float32)
    n1 = _fbm_yx(hpx, wpx, rng, octaves=6, base=22.0)
    n2 = _fbm_yx(hpx, wpx, np.random.RandomState(21), octaves=5, base=14.0)
    n3 = _fbm_yx(hpx, wpx, np.random.RandomState(27), octaves=4, base=9.0)
    road_w = _soft_mask(road_t, tp, n2, feather=1.25)
    court_w = _soft_mask(court_t, tp, n3, feather=1.05)
    water_w = _soft_mask(water_t, tp, n1, feather=1.85)
    # Large-period dirt (existing organic plate), domain-warped so one period
    # spans many tiles — not the old 5.2-tile waffle wrap.
    dirt_path = _art.SPRITE_DIR / "road_fine.png"
    dirt_u8 = np.array(Image.open(dirt_path).convert("RGB"))
    dh, dw = dirt_u8.shape[:2]
    xs = np.arange(wpx, dtype=np.float32)
    ys = np.arange(hpx, dtype=np.float32)
    period = 52.0 * tp
    map_x = np.mod(xs[None, :] * 0.83 + 0.21 * n2 * period + 180.0, period) * (dw / period)
    map_y = np.mod(ys[:, None] * 0.83 + 0.21 * n1 * period + 90.0, period) * (dh / period)
    sampled = _sample_wrap(dirt_u8, map_x.astype(np.float32), map_y.astype(np.float32)).astype(np.float32)
    del map_x, map_y
    lf = 0.30 * sampled[:, :, 0] + 0.50 * sampled[:, :, 1] + 0.20 * sampled[:, :, 2]
    rgb = np.empty_like(sampled)
    rgb[:, :, 0] = lf * 0.38 + sampled[:, :, 0] * 0.12 + 36
    rgb[:, :, 1] = lf * 0.34 + sampled[:, :, 1] * 0.11 + 34
    rgb[:, :, 2] = lf * 0.28 + sampled[:, :, 2] * 0.10 + 30
    del sampled, lf
    hollow = np.clip(n1 * 0.62 + n3 * 0.38, -1.0, 1.0)
    rgb *= (0.86 + 0.18 * hollow)[:, :, None]
    wet = np.clip(-hollow, 0, 1)
    rgb = rgb * (1.0 - 0.22 * wet)[:, :, None] + np.array([46.0, 44.0, 40.0]) * (0.22 * wet)[:, :, None]
    del hollow, wet
    rgb[:, :, 0] += 4.0 * n2
    rgb[:, :, 1] += 3.2 * n2
    rgb[:, :, 2] += 2.4 * n3
    map_x = np.mod(xs[None, :] + 0.16 * n1 * period, period) * (dw / period)
    map_y = np.mod(ys[:, None] + 0.16 * n2 * period, period) * (dh / period)
    sampled = _sample_wrap(dirt_u8, map_x.astype(np.float32), map_y.astype(np.float32)).astype(np.float32)
    del map_x, map_y, dirt_u8
    lr = 0.30 * sampled[:, :, 0] + 0.50 * sampled[:, :, 1] + 0.20 * sampled[:, :, 2]
    road = np.empty_like(sampled)
    road[:, :, 0] = lr * 0.34 + sampled[:, :, 0] * 0.12 + 32
    road[:, :, 1] = lr * 0.30 + sampled[:, :, 1] * 0.11 + 30
    road[:, :, 2] = lr * 0.25 + sampled[:, :, 2] * 0.10 + 27
    road *= (0.94 + 0.08 * n3)[:, :, None]
    rw = np.clip(road_w, 0, 1)[:, :, None]
    rgb = rgb * (1.0 - rw) + road * rw
    court = np.empty_like(sampled)
    court[:, :, 0] = lr * 0.36 + sampled[:, :, 0] * 0.12 + 40
    court[:, :, 1] = lr * 0.32 + sampled[:, :, 1] * 0.11 + 36
    court[:, :, 2] = lr * 0.26 + sampled[:, :, 2] * 0.10 + 32
    del sampled, lr, road
    cw = np.clip(court_w * (1.0 - road_w * 0.35), 0, 1)[:, :, None]
    rgb = rgb * (1.0 - cw) + court * cw
    del court, rw, cw
    ww = np.clip(water_w, 0, 1)
    rgb[:, :, 0] = rgb[:, :, 0] * (1.0 - ww) + (40.0 + 7.0 * n2) * ww
    rgb[:, :, 1] = rgb[:, :, 1] * (1.0 - ww) + (46.0 + 5.0 * n3) * ww
    rgb[:, :, 2] = rgb[:, :, 2] * (1.0 - ww) + (44.0 + 4.0 * n1) * ww
    del ww

    # Centerline ruts: follow each corridor, never stamp a per-tile lattice.
    eq = road_t > 0.5
    def ns_run(x, y):
        y0 = y
        while y0 > 0 and eq[y0 - 1, x]:
            y0 -= 1
        y1 = y
        while y1 < HEIGHT - 1 and eq[y1 + 1, x]:
            y1 += 1
        return y1 - y0 + 1

    track = np.zeros((hpx, wpx), dtype=np.float32)
    xs_t = xs / float(tp)
    ys_t = ys / float(tp)
    for y in range(HEIGHT):
        row = eq[y]
        x = 0
        while x < WIDTH:
            if not row[x]:
                x += 1
                continue
            x1 = x
            while x1 < WIDTH and row[x1]:
                x1 += 1
            width = x1 - x
            mid = min(WIDTH - 1, (x + x1) // 2)
            nsl = ns_run(mid, y)
            if nsl >= 8 and nsl >= width - 4:
                cx = 0.5 * (x + x1) + 0.52 * np.sin(y * 0.23 + mid * 0.045) + 0.22 * np.sin(y * 0.67)
                sep = float(np.clip(width * 0.155, 0.55, 1.45))
                sig = 0.24
                d1 = xs_t - (cx - sep)
                d2 = xs_t - (cx + sep)
                wgt = np.exp(-0.5 * (d1 / sig) ** 2) + np.exp(-0.5 * (d2 / sig) ** 2)
                py0, py1 = y * tp, (y + 1) * tp
                track[py0:py1, :] = np.maximum(track[py0:py1, :], wgt[None, :])
            x = x1
    # EW bands: consecutive rows whose span is clearly an east-west corridor
    ew_spans = [None] * HEIGHT
    for y in range(HEIGHT):
        row = eq[y]
        spans = []
        x = 0
        while x < WIDTH:
            if not row[x]:
                x += 1
                continue
            x1 = x
            while x1 < WIDTH and row[x1]:
                x1 += 1
            width = x1 - x
            mid = min(WIDTH - 1, (x + x1) // 2)
            nsl = ns_run(mid, y)
            if width >= 8 and width > nsl + 2:
                spans.append((x, x1))
            x = x1
        if spans:
            ew_spans[y] = spans
    y = 0
    while y < HEIGHT:
        if not ew_spans[y]:
            y += 1
            continue
        yb = y
        while yb < HEIGHT and ew_spans[yb]:
            yb += 1
        cy = 0.5 * (y + yb - 1) + 0.42 * np.sin(y * 0.19) + 0.18 * np.sin(y * 0.61)
        band_h = yb - y
        sep = float(np.clip(band_h * 0.16, 0.50, 1.35))
        sig = 0.24
        d1 = ys_t - (cy - sep)
        d2 = ys_t - (cy + sep)
        wgt_y = np.exp(-0.5 * (d1 / sig) ** 2) + np.exp(-0.5 * (d2 / sig) ** 2)
        for yy in range(y, yb):
            py0, py1 = yy * tp, (yy + 1) * tp
            row_w = wgt_y[py0:py1, None]
            for x0, x1 in ew_spans[yy]:
                px0, px1 = x0 * tp, x1 * tp
                sl = track[py0:py1, px0:px1]
                track[py0:py1, px0:px1] = np.maximum(sl, row_w)
        y = yb
    rgb = rgb * (1.0 - 0.24 * track[:, :, None])

    # Wall-foot contact and sparse clods — thresholded mid-freq, not confetti or squares.
    wx0, wy0, wx1, wy1 = bf.wall_box
    col = (np.arange(wpx, dtype=np.float32) / tp)[None, :]
    rowp = (np.arange(hpx, dtype=np.float32) / tp)[:, None]
    dx = np.maximum(wx0 - col, 0) + np.maximum(col - (wx1 + 1), 0)
    dy = np.maximum(wy0 - rowp, 0) + np.maximum(rowp - (wy1 + 1), 0)
    outside = np.sqrt(dx * dx + dy * dy)
    band = np.clip(1.0 - outside / 16.0, 0, 1) * (outside > 0.15)
    inside = (col >= wx0) & (col <= wx1 + 1) & (rowp >= wy0) & (rowp <= wy1 + 1)
    dist_in = np.minimum(np.minimum(col - wx0, wx1 + 1 - col), np.minimum(rowp - wy0, wy1 + 1 - rowp))
    inner = inside.astype(np.float32) * np.clip(1.0 - dist_in / 7.0, 0, 1)
    wear = (band * 0.20 + inner * 0.09) * (1.0 - 0.75 * road_w)
    rgb = rgb * (1.0 - wear[:, :, None]) + np.array([52.0, 48.0, 44.0]) * wear[:, :, None]
    clod = (n3 > 0.58) & (n2 > 0.12) & (road_w < 0.28) & (water_w < 0.4) & (band > 0.08)
    rock = (92 + 22 * n1).astype(np.float32)
    rgb[:, :, 0] = np.where(clod, rock, rgb[:, :, 0])
    rgb[:, :, 1] = np.where(clod, rock * 0.90, rgb[:, :, 1])
    rgb[:, :, 2] = np.where(clod, rock * 0.80, rgb[:, :, 2])
    rgb = np.clip(rgb, 0, 255).astype(np.uint8)
    arr = np.ascontiguousarray(rgb)
    n = (WIDTH // 16) * (HEIGHT // 16)
    del n1, n2, n3, road_w, court_w, water_w, track, wear, band, clod, rock
    _topo_cache[key] = (arr, tp, n)
    try:
        _write_topo_disk(bf, arr)
    except Exception:
        pass
    return _topo_cache[key]


def _draw_ground_plane(dest: pygame.Surface, bf: Battlefield, origin, scale, screen_o, clip=None) -> int:
    """Warp prebuilt terrain onto the angled ground plane, optionally a dirty rect."""
    import cv2
    vw, vh = dest.get_size()
    if clip is None:
        sx0, sy0, cw, ch = 0, 0, vw, vh
    else:
        sx0, sy0, cw, ch = [int(v) for v in clip]
        if cw < 2 or ch < 2:
            return 0
    corners = [(sx0, sy0), (sx0 + cw, sy0), (sx0 + cw, sy0 + ch), (sx0, sy0 + ch)]
    world = [P.unproject(sx, sy, origin, scale, screen_o, 0.0) for sx, sy in corners]
    minx = int(math.floor(min(p[0] for p in world))) - 6
    maxx = int(math.ceil(max(p[0] for p in world))) + 6
    miny = int(math.floor(min(p[1] for p in world))) - 6
    maxy = int(math.ceil(max(p[1] for p in world))) + 6
    minx = max(0, minx)
    miny = max(0, miny)
    maxx = min(WIDTH, maxx)
    maxy = min(HEIGHT, maxy)
    if maxx <= minx or maxy <= miny:
        return 0
    topo, tp, n = _terrain_topo(bf)
    p00 = P.project(minx, miny, 0, origin, scale, screen_o)
    p10 = P.project(maxx, miny, 0, origin, scale, screen_o)
    p01 = P.project(minx, maxy, 0, origin, scale, screen_o)
    src = np.float32([[minx * tp, miny * tp], [maxx * tp - 1, miny * tp], [minx * tp, maxy * tp - 1]])
    dst = np.float32([
        [p00[0] - sx0, p00[1] - sy0],
        [p10[0] - sx0, p10[1] - sy0],
        [p01[0] - sx0, p01[1] - sy0],
    ])
    M = cv2.getAffineTransform(src, dst)
    warped = cv2.warpAffine(topo, M, (cw, ch), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_CONSTANT)
    mask = warped.sum(axis=2) > 0
    dest_rgb = pygame.surfarray.pixels3d(dest)
    wr = np.transpose(warped, (1, 0, 2))
    mk = mask.T
    dest_rgb[sx0:sx0 + cw, sy0:sy0 + ch][mk] = wr[mk]
    del dest_rgb
    return n


def _sort_key(face: Face, origin) -> float:
    cx = sum(p[0] for p in face.pts) / 4.0
    cy = sum(p[1] for p in face.pts) / 4.0
    cz = sum(p[2] for p in face.pts) / 4.0
    return P.depth_of(cx, cy, origin) - 0.08 * cz + face.bias


def _draw_faces(dest: pygame.Surface, faces: Sequence[Face], origin, scale, screen_o, clip=None) -> int:
    rgb = pygame.surfarray.pixels3d(dest)
    view = clip if clip is not None else (0, 0, dest.get_width(), dest.get_height())
    ordered = sorted(faces, key=lambda f: _sort_key(f, origin), reverse=True)
    n = 0
    for face in ordered:
        _blit_face(rgb, face, origin, scale, screen_o, view)
        n += 1
    del rgb
    return n


def _engine_faces(eng: PlacedEngine, tint=None) -> List[Face]:
    rec = eng.rect()
    h = ENGINE_H.get(eng.engine_type, 2.4)
    faces = _box_faces(rec[0], rec[1], rec[2] + 1, rec[3] + 1, 0, h, "timber", "timber")
    if tint:
        faces = [
            Face(f.pts, f.u_span, f.v_span, f.tex,
                 (f.shade[0] * tint[0], f.shade[1] * tint[1], f.shade[2] * tint[2]), f.bias)
            for f in faces
        ]
    return faces


_bb_scale_cache: Dict[tuple, pygame.Surface] = {}


def _scaled_bb(img: pygame.Surface, w: int, h: int) -> pygame.Surface:
    key = (id(img), int(w), int(h))
    spr = _bb_scale_cache.get(key)
    if spr is None:
        spr = pygame.transform.smoothscale(img, (w, h))
        _bb_scale_cache[key] = spr
        while len(_bb_scale_cache) > 64:
            _bb_scale_cache.pop(next(iter(_bb_scale_cache)))
    return spr


def _draw_billboard(dest, origin, scale, screen_o, x, y, z0, z1, img, depth_bias=0.0, alpha=255, x_off=0.0):
    sx, sy, _ = P.project(x, y, z0, origin, scale, screen_o)
    _, sy1, _ = P.project(x, y, z1, origin, scale, screen_o)
    h = max(6, int(sy - sy1))
    w = max(4, int(img.get_width() * h / max(1, img.get_height())))
    spr = _scaled_bb(img, w, h)
    if alpha < 255:
        spr = spr.copy()
        spr.fill((255, 255, 255, max(0, min(255, int(alpha)))), special_flags=pygame.BLEND_RGBA_MULT)
    dest.blit(spr, (int(sx - w / 2 + x_off), int(sy - h)))
    return P.depth_of(x, y, origin) - 0.08 * ((z0 + z1) * 0.5) + depth_bias


_fx_cache: Dict[str, pygame.Surface] = {}
_glow_cache: Dict[tuple, pygame.Surface] = {}
FX_TIME_OVERRIDE: Optional[float] = None


def fx_now() -> float:
    if FX_TIME_OVERRIDE is not None:
        return float(FX_TIME_OVERRIDE)
    return pygame.time.get_ticks() * 0.001


def _trim_surface(surf: pygame.Surface, pad: int = 4) -> pygame.Surface:
    mask = pygame.mask.from_surface(surf, 12)
    rects = mask.get_bounding_rects()
    if not rects:
        return surf
    r = rects[0]
    for extra in rects[1:]:
        r.union_ip(extra)
    r = r.inflate(pad * 2, pad * 2).clip(surf.get_rect())
    return surf.subsurface(r).copy()


def _neutralize_pink(surf: pygame.Surface) -> pygame.Surface:
    """Drop studio-magenta fringe and pull leftover pink toward ash grey."""
    s = surf.copy()
    rgb = pygame.surfarray.pixels3d(s)
    al = pygame.surfarray.pixels_alpha(s)
    r = rgb[:, :, 0].astype(np.int16)
    g = rgb[:, :, 1].astype(np.int16)
    b = rgb[:, :, 2].astype(np.int16)
    pink = ((r > 145) & (b > 135) & (g + 28 < r) & (g + 18 < b)) | ((r > 190) & (b > 190) & (g < 170))
    al[pink] = 0
    cast = (r > g + 10) & (b > g + 8) & (al > 0)
    rgb[:, :, 0][cast] = np.clip(r[cast] * 0.42 + g[cast] * 0.58, 0, 255).astype(np.uint8)
    rgb[:, :, 2][cast] = np.clip(b[cast] * 0.38 + g[cast] * 0.62, 0, 255).astype(np.uint8)
    del rgb, al
    # 1px alpha erode of remaining fringe
    al = pygame.surfarray.array_alpha(s)
    work = (al > 12).astype(np.uint8)
    kern = np.ones((3, 3), dtype=np.uint8)
    eroded = cv2.erode(work, kern, iterations=1)
    al2 = pygame.surfarray.pixels_alpha(s)
    al2[eroded == 0] = 0
    del al2
    return s


def _fx(name: str) -> pygame.Surface:
    if name not in _fx_cache:
        png = art.SPRITE_DIR / f"{name}.png"
        path = png if png.is_file() else art.SPRITE_DIR / f"{name}.jpg"
        raw = pygame.image.load(str(path))
        if path.suffix.lower() == ".png":
            surf = raw.convert_alpha()
        else:
            surf = art._erode_fringe(art._strip_studio_pink(art._chroma_key(raw.convert())))
        if "smoke" in name:
            surf = _neutralize_pink(surf)
        _fx_cache[name] = _trim_surface(surf)
    return _fx_cache[name]


def _radial_glow(radius: int, rgb: Tuple[int, int, int], peak: int) -> pygame.Surface:
    key = (int(radius), rgb, int(peak))
    cached = _glow_cache.get(key)
    if cached is not None:
        return cached
    radius = max(6, int(radius))
    d = radius * 2 + 3
    surf = pygame.Surface((d, d), pygame.SRCALPHA)
    cx = cy = d // 2
    for r in range(radius, 0, -2):
        u = 1.0 - r / radius
        a = int(peak * (u * u) * (1.6 - 0.6 * u))
        if a <= 0:
            continue
        pygame.draw.circle(surf, (*rgb, min(255, a)), (cx, cy), r)
    _glow_cache[key] = surf
    return surf


def _draw_fire(dest, origin, scale, screen_o, rec: Rect) -> None:
    """Layered breach fire: feathered ground warmth, side flames, drifting smoke, embers.

    Drawn in the dynamic pass (elapsed time). Not a flat colored ellipse and not combat.
    """
    cx = (rec[0] + rec[2] + 1) / 2.0
    cy = rec[3] + 0.35
    t = fx_now()
    fire = _fx("fx_fire_m9")
    smoke = _fx("fx_smoke_m9")

    # Small quadratic-falloff warmth under each pile — respects nearby stone/ground.
    for ox, oy, peak, rad_t in (
        (-2.35, 0.18, 40, 1.55),
        (2.40, 0.12, 36, 1.40),
        (-1.55, 0.70, 22, 1.05),
    ):
        gx, gy, _ = P.project(cx + ox, cy + oy, 0.04, origin, scale, screen_o)
        glow = _radial_glow(int(scale * rad_t), (255, 118, 46), peak)
        dest.blit(glow, (int(gx - glow.get_width() / 2), int(gy - glow.get_height() * 0.42)))
        hot = _radial_glow(int(scale * rad_t * 0.42), (255, 188, 88), min(70, peak + 14))
        dest.blit(hot, (int(gx - hot.get_width() / 2), int(gy - hot.get_height() * 0.46)))

    # Side flames (center of the arch stays a clear passage).
    for i, (ox, oy, h0, seed) in enumerate((
        (-2.35, 0.20, 3.15, 0.4),
        (2.42, 0.14, 2.75, 1.9),
        (-1.58, 0.78, 2.15, 3.3),
    )):
        flick = 1.0 + 0.07 * math.sin(t * 7.1 + seed) + 0.04 * math.sin(t * 12.4 + seed * 1.7)
        sway = 0.10 * math.sin(t * 3.4 + seed)
        _draw_billboard(dest, origin, scale, screen_o, cx + ox + sway * 0.15, cy + oy,
                        0.08, max(1.4, h0 * flick), fire, -0.05)

    # Wisps rise from the side fires so the arch opening stays readable.
    for i, (ox, oy, h0, delay, drift) in enumerate((
        (-2.30, 0.12, 5.6, 0.00, 0.55),
        (2.38, 0.10, 6.0, 0.45, -0.48),
        (-2.62, 0.42, 5.0, 1.10, 0.85),
        (2.68, 0.30, 5.4, 1.75, -0.75),
        (-2.05, 0.58, 4.6, 2.40, 0.30),
    )):
        cycle = 5.6
        phase = ((t * 0.22 + delay) % cycle) / cycle
        z0 = 1.55 + phase * 5.2
        rise = h0 * (0.85 + 0.40 * phase)
        fade = math.sin(phase * math.pi)
        alpha = int(175 * fade * (0.82 + 0.18 * math.sin(t * 0.9 + delay)))
        if alpha < 10:
            continue
        x = cx + ox + drift * phase * 0.90 + 0.20 * math.sin(t * 0.8 + delay)
        y = cy + oy
        _draw_billboard(dest, origin, scale, screen_o, x, y, z0, z0 + rise, smoke,
                        0.12, alpha=alpha, x_off=7 * math.sin(t * 0.65 + delay))

    # Sparks / embers — bounded, time-driven.
    ember = pygame.Surface((5, 5), pygame.SRCALPHA)
    for i in range(16):
        seed = i * 19.17
        life = 1.35 + (i % 5) * 0.12
        phase = (t * (0.62 + (i % 4) * 0.05) + seed) % life / life
        side = -2.3 if i % 2 == 0 else 2.35
        x = cx + side + 0.55 * math.sin(seed) + 0.22 * math.sin(t * 4.2 + seed)
        y = cy + 0.15 + 0.25 * math.cos(seed * 1.3)
        z = 0.25 + phase * 4.2
        sx, sy, _ = P.project(x, y, z, origin, scale, screen_o)
        a = int(230 * (1.0 - phase) ** 1.15)
        if a < 12:
            continue
        rad = 2 if phase < 0.45 else 1
        pygame.draw.circle(ember, (0, 0, 0, 0), (2, 2), 2)
        pygame.draw.circle(ember, (255, 210 - int(80 * phase), 70, a), (2, 2), rad)
        dest.blit(ember, (int(sx - 2), int(sy - 2)))


def camera_look(player: Tuple[float, float], view: Tuple[int, int], scale: float) -> Tuple[Tuple[float, float], Tuple[float, float]]:
    """Look slightly north of the player; put the avatar in the lower third."""
    origin = (player[0] + 0.5, player[1] + 0.5)
    screen_o = (view[0] * 0.50, view[1] * 0.70)
    return origin, screen_o



def _blit_offset(corigin, cso, origin, screen_o, scale):
    dsx = ((corigin[0] - origin[0]) * P.COS_Y + (corigin[1] - origin[1]) * P.SIN_Y) * scale + (screen_o[0] - cso[0])
    ddepth = (corigin[0] - origin[0]) * P.SIN_Y - (corigin[1] - origin[1]) * P.COS_Y
    dsy = -ddepth * scale * P.SIN_P + (screen_o[1] - cso[1])
    return dsx, dsy


def _layer_covers(dsx, dsy, lw, lh, vw, vh, margin):
    return (dsx <= -margin and dsy <= -margin and
            dsx + lw >= vw + margin and dsy + lh >= vh + margin)


def _uncovered_rects(w, h, iox, ioy):
    rects = []
    if iox > 0:
        rects.append((0, 0, iox, h))
    elif iox < 0:
        rects.append((w + iox, 0, -iox, h))
    x0 = max(0, iox)
    bw = w - abs(iox)
    if bw > 0:
        if ioy > 0:
            rects.append((x0, 0, bw, ioy))
        elif ioy < 0:
            rects.append((x0, h + ioy, bw, -ioy))
    return [(x, y, rw, rh) for (x, y, rw, rh) in rects if rw >= 2 and rh >= 2]


def _paint_static(layer, bf, states, corigin, scale, cso, clip=None) -> tuple:
    if clip is None:
        _draw_sky(layer)
        chunks = _draw_ground_plane(layer, bf, corigin, scale, cso)
        faces = _collect_static_faces(bf, states)
        nfaces = _draw_faces(layer, faces, corigin, scale, cso)
        draw_baked_buildings(layer, bf, states, corigin, scale, cso)
        return chunks, nfaces
    chunks = 0
    nfaces = 0
    faces = _collect_static_faces(bf, states)
    for rect in clip:
        _draw_sky_rect(layer, rect)
        chunks += _draw_ground_plane(layer, bf, corigin, scale, cso, clip=rect)
        nfaces += _draw_faces(layer, faces, corigin, scale, cso, clip=rect)
        layer.set_clip(pygame.Rect(rect))
        draw_baked_buildings(layer, bf, states, corigin, scale, cso, clip=rect)
        layer.set_clip(None)
    return chunks, nfaces


def _ensure_static(bf, player, states, origin, screen_o, scale, world_size):
    """Sliding prebuilt isometric layer: reuse, incrementally scroll+fill, or full rebuild."""
    key = (id(bf.plane), int(scale), tuple(sorted(states.items())), world_size, _baked_rev)
    pad = (max(64, int(world_size[0] * CACHE_PAD)), max(64, int(world_size[1] * CACHE_PAD)))
    cached = _view_cache.get(key)
    if cached is not None:
        layer, corigin, cso, extra = cached
        dsx, dsy = _blit_offset(corigin, cso, origin, screen_o, scale)
        new_corigin, new_cso = camera_look(player, pad, scale)
        ox, oy = _blit_offset(corigin, cso, new_corigin, new_cso, scale)
        iox, ioy = int(round(ox)), int(round(oy))
        covered = _layer_covers(dsx, dsy, layer.get_width(), layer.get_height(),
                                world_size[0], world_size[1], CACHE_MARGIN)
        follow = abs(iox) >= CACHE_FOLLOW or abs(ioy) >= CACHE_FOLLOW
        if covered and not follow:
            return layer, corigin, cso, extra, "hit"
        lw, lh = layer.get_size()
        if (iox or ioy) and abs(iox) <= int(lw * 0.55) and abs(ioy) <= int(lh * 0.55):
            # In-place scroll: no extra full-size copy. Fill only vacated strips.
            layer.scroll(iox, ioy)
            dirty = _uncovered_rects(lw, lh, iox, ioy)
            extra = _paint_static(layer, bf, states, new_corigin, scale, new_cso, clip=dirty)
            _view_cache[key] = (layer, new_corigin, new_cso, extra)
            return layer, new_corigin, new_cso, extra, "incr"
        if abs(iox) == 0 and abs(ioy) == 0:
            return layer, corigin, cso, extra, "hit"
    # Full rebuild (first look at this zoom/state, or a long teleport).
    corigin, cso = camera_look(player, pad, scale)
    layer = pygame.Surface(pad)
    extra = _paint_static(layer, bf, states, corigin, scale, cso)
    _view_cache[key] = (layer, corigin, cso, extra)
    while len(_view_cache) > CACHE_LIMIT:
        _view_cache.pop(next(iter(_view_cache)))
    return layer, corigin, cso, extra, "full"


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
    scale = float(tile_px)
    surf = pygame.Surface(size)
    surf.fill((16, 14, 12))
    hud_top, hud_bot = 58, 56
    world = pygame.Surface((size[0], size[1] - hud_top - hud_bot))
    origin, screen_o = camera_look(player, world.get_size(), scale)

    layer, corigin, cso, extra, cache_mode = _ensure_static(
        bf, player, states, origin, screen_o, scale, world.get_size())
    cache_hit = cache_mode == "hit"
    dsx, dsy = _blit_offset(corigin, cso, origin, screen_o, scale)
    bx, by = int(round(dsx)), int(round(dsy))
    # The static layer already contains sky; only paint it when the layer does
    # not cover the whole viewport (otherwise it is overwritten pixel-for-pixel).
    if not (bx <= 0 and by <= 0 and bx + layer.get_width() >= world.get_width()
            and by + layer.get_height() >= world.get_height()):
        _draw_sky(world)
    world.blit(layer, (bx, by))
    t1 = time.perf_counter()
    fx_ms = 0.0
    if states.get("main_gate", "intact") == "destroyed":
        tf0 = time.perf_counter()
        _draw_fire(world, origin, scale, screen_o, bf.plane.openings["main_gate"].rect)
        fx_ms = (time.perf_counter() - tf0) * 1000.0

    # Dynamics: engines, ghosts, player (depth-sorted among themselves vs nearest walls is approximate:
    # we redraw them after the cached static, which is correct when they stand in front of the castle).
    for eng in engines:
        rec = eng.rect()
        cx = (rec[0] + rec[2] + 1) / 2.0
        cy = (rec[1] + rec[3] + 1) / 2.0
        sprite = eng.engine_type if (BAKED_DIR / f"{eng.engine_type}.png").is_file() else None
        if sprite:
            blit_baked(world, sprite, cx, cy, origin, scale, screen_o)
    if ghosts:
        for res, ok, kind in ghosts:
            if not res.tiles:
                continue
            xs = [t[0] for t in res.tiles]
            ys = [t[1] for t in res.tiles]
            x0, y0, x1, y1 = min(xs), min(ys), max(xs) + 1, max(ys) + 1
            cx, cy = (x0 + x1) / 2.0, (y0 + y1) / 2.0
            tint = (40, 180, 70) if ok else (200, 40, 36)
            if (BAKED_DIR / f"{kind}.png").is_file():
                blit_baked(world, kind, cx, cy, origin, scale, screen_o, tint=tint)
            cols = [(x0, y0, 0.05), (x1, y0, 0.05), (x1, y1, 0.05), (x0, y1, 0.05)]
            sp = [P.project(*c, origin, scale, screen_o)[:2] for c in cols]
            color = (70, 210, 90) if ok else (210, 60, 55)
            pygame.draw.polygon(world, color, [(int(p[0]), int(p[1])) for p in sp], max(2, int(scale / 14)))

    # Player billboard
    px, py = player[0] + 0.5, player[1] + 0.85
    on_walk = bf.plane.cell(player[0], player[1]) == "H"
    z0 = WALL_H + 0.05 if on_walk else 0.0
    facing = facing if facing in {"n", "s", "e", "w"} else "s"
    pname = {"n": "player_n", "s": "player_s", "e": "player_e", "w": "player_w"}[facing]
    src = art.load(pname) if pname != "player_e" else art.load_player_east()
    _draw_billboard(world, origin, scale, screen_o, px, py, z0, z0 + PLAYER_H, src, -0.2)

    if markers:
        for oid, label in (("main_gate", "Main Gate"), ("west_gate", "West Postern"),
                           ("east_gate", "East Postern"), ("north_gate", "North Postern"),
                           ("keep_doors", "Keep Door")):
            rec = bf.plane.openings[oid].rect
            cx, cy = (rec[0] + rec[2] + 1) / 2, rec[3] + 0.4
            sx, sy, _ = P.project(cx, cy, 0.2, origin, scale, screen_o)
            pygame.draw.polygon(world, (232, 196, 96), [(sx, sy - 14), (sx - 7, sy - 2), (sx + 7, sy - 2)])
            img = _font(18).render(label, True, (255, 230, 186))
            world.blit(img, (sx - img.get_width() / 2, sy - 34))

    t2 = time.perf_counter()

    surf.blit(world, (0, hud_top))
    surf.fill((18, 14, 12), pygame.Rect(0, 0, size[0], hud_top))
    surf.fill((14, 12, 10), pygame.Rect(0, size[1] - hud_bot, size[0], hud_bot))
    surf.blit(_font(32).render(title, True, (236, 214, 168)), (16, 10))
    surf.blit(_font(20).render(subtitle, True, (188, 174, 150)), (16, 36))
    extra_txt = f"gameplay camera {int(scale)}px/tile · player {player}"
    if build_ui:
        extra_txt += "  ·  " + HINTS
        if ghost_reason:
            banner = _font(22).render(ghost_reason, True, (255, 196, 160))
            surf.blit(banner, (16, hud_top + 8))
            tag = _font(22).render("VALID" if (ghosts and ghosts[0][1]) else "INVALID", True,
                                   (140, 220, 150) if (ghosts and ghosts[0][1]) else (230, 110, 100))
            surf.blit(tag, (16, hud_top + 30))
    surf.blit(_font(18).render(f"{CAPTION}  ·  {extra_txt}", True, (255, 228, 176)), (14, size[1] - 36))
    # Mini-map (neutral, not mockup chrome)
    mm = pygame.Surface((150, 150))
    mm.fill((20, 24, 18))
    sxm = 150 / WIDTH
    sym = 150 / HEIGHT
    pygame.draw.rect(mm, (70, 68, 62), pygame.Rect(int(bf.wall_box[0] * sxm), int(bf.wall_box[1] * sym),
                     int((bf.wall_box[2] - bf.wall_box[0]) * sxm), int((bf.wall_box[3] - bf.wall_box[1]) * sym)), 1)
    pygame.draw.circle(mm, (80, 180, 255), (int(player[0] * sxm), int(player[1] * sym)), 3)
    surf.blit(mm, (size[0] - 162, 4))
    t3 = time.perf_counter()
    LAST_METRICS.clear()
    LAST_METRICS.update({
        "ground_ms": round((t1 - t0) * 1000, 2),
        "sprites_ms": round((t2 - t1) * 1000, 2),
        "total_ms": round((t3 - t0) * 1000, 2),
        "hud_ms": round((t3 - t2) * 1000, 2),
        "tile_px": scale,
        "cached": 1 if cache_hit else 0,
        "cache_hit": 1 if cache_hit else 0,
        "cache_mode": {"hit": 0, "incr": 1, "full": 2}[cache_mode],
        "layer_px": int(layer.get_width() * layer.get_height()),
        "cache_entries": len(_view_cache),
        "faces": int(extra[1]) if extra else 0,
        "chunks": int(extra[0]) if extra else 0,
        "draw_items": int(extra[1]) if extra else 0,
        "drawn_items": int(extra[1]) if extra else 0,
        "fx_ms": round(fx_ms, 2),
    })
    return surf


def profile_walk(bf, path, engines, tile_px=32, size=(1600, 900), facing="n", prewarm=True, gate_states=None):
    dummy = pygame.Surface(size)
    if prewarm:
        for pos in path:
            render_world(bf, pos, engines, "walk", "prewarm", size=size, tile_px=tile_px, facing=facing, markers=False, gate_states=gate_states)
    times = []
    parts = []
    fx = []
    for pos in path:
        render_world(bf, pos, engines, "walk", "steady", size=size, tile_px=tile_px, facing=facing, markers=False, gate_states=gate_states)
        times.append(float(LAST_METRICS["total_ms"]))
        parts.append((float(LAST_METRICS["ground_ms"]), float(LAST_METRICS["sprites_ms"]), float(LAST_METRICS.get("hud_ms", 0))))
        fx.append(float(LAST_METRICS.get("fx_ms", 0)))
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
        "mean_fx_ms": round(sum(fx) / max(1, len(fx)), 2) if fx else 0.0,
        "max_fx_ms": round(max(fx), 2) if fx else 0.0,
    }


def visual_scale() -> dict:
    return {
        "tile_meters": 1.6,
        "yaw_deg": P.YAW_DEG,
        "pitch_deg": P.PITCH_DEG,
        "wall_h_tiles": WALL_H,
        "tower_h_tiles": TOWER_H,
        "keep_h_tiles": KEEP_H,
        "player_h_tiles": PLAYER_H,
        "player_w_tiles": PLAYER_W,
    }
