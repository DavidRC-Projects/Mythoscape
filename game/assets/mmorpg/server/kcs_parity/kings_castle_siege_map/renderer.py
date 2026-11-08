"""Pygame dummy renderer for the isolated King's Castle prototype (M2).

Scenic plates are visual direction. The walking camera draws the actual
collision grid so perimeter movement is not a stretched frontal painting.
Player-built engines are overlaid as entities, separate from landscape art.
"""

from __future__ import annotations

from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple

import pygame

from .constants import HEIGHT, MAP_TITLE, TILE_METERS, WIDTH
from .layout import Battlefield, Rect, build_battlefield, walkable
from .placement import PlacedEngine, PlacementResult, SPECS

ASSETS = Path(__file__).resolve().parent.parent / "assets" / "plates"
M2 = ASSETS / "m2"
MAT_DIR = M2 / "materials"
MAT_FOR = {
    ".": "mat_grass.jpg",
    "=": "mat_road.jpg",
    ",": "mat_court.jpg",
    "#": "mat_wall.jpg",
    "H": "mat_wall.jpg",
    "~": "mat_water.jpg",
    "G": "mat_timber.jpg",
    "P": "mat_timber.jpg",
    "T": "mat_grass.jpg",
}
_raw_mats: Dict[str, Optional[pygame.Surface]] = {}
_scaled_mats: Dict[Tuple[str, int], Optional[pygame.Surface]] = {}


def _raw_mat(name: str) -> Optional[pygame.Surface]:
    if name not in _raw_mats:
        path = MAT_DIR / name
        _raw_mats[name] = pygame.image.load(str(path)).convert() if path.is_file() else None
    return _raw_mats[name]


def _scaled_mat(ch: str, tile_px: int) -> Optional[pygame.Surface]:
    key = (ch, tile_px)
    if key not in _scaled_mats:
        fname = MAT_FOR.get(ch)
        raw = _raw_mat(fname) if fname else None
        if raw is None:
            _scaled_mats[key] = None
        else:
            side = max(64, tile_px * 8)
            _scaled_mats[key] = pygame.transform.smoothscale(raw, (side, side))
    return _scaled_mats[key]


def blit_terrain(surf: pygame.Surface, ch: str, rx: int, ry: int, tile_px: float, x: int, y: int, colour) -> None:
    tp = max(1, int(tile_px) + 1)
    rec = pygame.Rect(rx, ry, tp, tp)
    mat = _scaled_mat(ch, max(4, int(tile_px))) if tile_px >= 3 else None
    if mat is not None:
        mw, mh = mat.get_size()
        ox = (x * tp) % max(1, mw - tp)
        oy = (y * tp) % max(1, mh - tp)
        if ch == "=":
            inner0 = int(mw * 0.32)
            innerw = max(tp + 1, int(mw * 0.36))
            ox = inner0 + (x * tp) % max(1, innerw - tp)
            oy = (y * tp) % max(1, mh - tp)
        surf.blit(mat, rec.topleft, pygame.Rect(ox, oy, tp, tp))
        if ch == "H":
            veil = pygame.Surface((tp, tp), pygame.SRCALPHA)
            veil.fill((220, 190, 120, 70))
            surf.blit(veil, rec.topleft)
        elif ch == "T":
            pygame.draw.circle(surf, (28, 62, 30), rec.center, max(2, tp // 3))
    else:
        pygame.draw.rect(surf, colour, rec)

PLATE_FILES = {
    "overview": "overview.jpg",
    "allsides": "m2/allsides_overview.jpg",
    "approach": "approach.jpg",
    "north_rear": "m2/north_rear.jpg",
    "east_flank": "m2/east_flank.jpg",
    "west_flank": "m2/west_flank.jpg",
    "gate_intact": "gate_intact.jpg",
    "gate_damaged": "gate_damaged.jpg",
    "gate_destroyed": "gate_destroyed.jpg",
    "courtyard": "courtyard.jpg",
    "keep": "keep.jpg",
    "throne": "throne.jpg",
}

CAPTION = "DUMMY pygame | isolated King's Castle M2 | NOT live GUI | NOT the shipped game client"

TERRAIN_RGB = {
    ".": (74, 104, 56),
    "=": (138, 108, 64),
    ",": (142, 134, 118),
    "#": (112, 108, 102),
    "H": (168, 150, 118),
    "~": (52, 92, 120),
    "T": (40, 78, 42),
    "G": (196, 160, 70),
    "P": (98, 70, 44),
}

ENGINE_RGB = {
    "ram": (160, 92, 40),
    "trebuchet": (120, 72, 38),
    "siege_tower": (96, 78, 52),
    "ladder": (176, 140, 70),
}


def asset_path(name: str) -> Path:
    rel = PLATE_FILES[name]
    return ASSETS / rel


def load_plate(name: str) -> pygame.Surface:
    path = asset_path(name)
    if not path.is_file():
        raise FileNotFoundError(path)
    return pygame.image.load(str(path)).convert()


def _font(size: int) -> pygame.font.Font:
    return pygame.font.Font(None, size)


def _caption(surf: pygame.Surface, extra: str) -> None:
    h = 52
    bar = pygame.Surface((surf.get_width(), h), pygame.SRCALPHA)
    bar.fill((8, 8, 10, 220))
    surf.blit(bar, (0, surf.get_height() - h))
    text = _font(20).render(f"{CAPTION}  ·  {extra}", True, (255, 228, 176))
    surf.blit(text, (14, surf.get_height() - 34))


def _title(surf: pygame.Surface, title: str, subtitle: str = "") -> None:
    bar = pygame.Surface((surf.get_width(), 56 if subtitle else 40), pygame.SRCALPHA)
    bar.fill((8, 8, 12, 200))
    surf.blit(bar, (0, 0))
    surf.blit(_font(30).render(title, True, (255, 236, 190)), (16, 8))
    if subtitle:
        surf.blit(_font(20).render(subtitle, True, (220, 200, 160)), (16, 34))


def _chip(surf: pygame.Surface, xy: Tuple[int, int], label: str, fill=(24, 18, 28), border=(200, 160, 70)) -> None:
    img = _font(20).render(label, True, (255, 230, 176))
    pad = 8
    rect = pygame.Rect(0, 0, img.get_width() + pad * 2, img.get_height() + pad)
    rect.center = xy
    pygame.draw.rect(surf, fill, rect, border_radius=8)
    pygame.draw.rect(surf, border, rect, 2, border_radius=8)
    surf.blit(img, (rect.x + pad, rect.y + pad // 2))


def render_plate_view(plate_name: str, title: str, subtitle: str,
                      size: Tuple[int, int] = (1600, 900),
                      chips: Optional[list] = None) -> pygame.Surface:
    raw = load_plate(plate_name)
    surf = pygame.Surface(size)
    surf.blit(pygame.transform.smoothscale(raw, size), (0, 0))
    _title(surf, title, subtitle)
    for chip in chips or []:
        _chip(surf, chip[0], chip[1])
    _caption(surf, f"scenic plate {raw.get_width()}x{raw.get_height()} (visual direction, not the collision mesh)")
    return surf


def render_allsides_overview(size: Tuple[int, int] = (1200, 1200)) -> pygame.Surface:
    return render_plate_view(
        "allsides",
        f"{MAP_TITLE} — all-sides battlefield (scenic overview)",
        "Land on north, south, east and west. Keep sits inside the courtyard. Painted south engines are landscape examples, not placed entities.",
        size,
        chips=[
            ((size[0] // 2, int(size[1] * 0.108)), "North rear field"),
            ((size[0] // 2, int(size[1] * 0.325)), "Keep in courtyard"),
            ((size[0] // 2, int(size[1] * 0.455)), "South gatehouse"),
            ((int(size[0] * 0.12), int(size[1] * 0.36)), "West flank"),
            ((int(size[0] * 0.88), int(size[1] * 0.36)), "East flank"),
        ],
    )


def _world_to_screen(tile_px: float, origin: Tuple[float, float], x: float, y: float) -> Tuple[int, int]:
    ox, oy = origin
    return int((x - ox) * tile_px), int((y - oy) * tile_px)


def draw_world(
    surf: pygame.Surface,
    bf: Battlefield,
    origin: Tuple[float, float],
    tile_px: float,
    engines: Optional[Sequence[PlacedEngine]] = None,
    ghosts: Optional[Sequence[Tuple[PlacementResult, bool]]] = None,
    player: Optional[Tuple[int, int]] = None,
    gate_states: Optional[Dict[str, str]] = None,
) -> None:
    """Draw the real nav grid into a camera window."""
    w, h = surf.get_size()
    cols = int(w / tile_px) + 3
    rows = int(h / tile_px) + 3
    x0 = max(0, int(origin[0]) - 1)
    y0 = max(0, int(origin[1]) - 1)
    states = gate_states or bf.gate_states
    for y in range(y0, min(HEIGHT, y0 + rows)):
        row = bf.plane.grid[y]
        for x in range(x0, min(WIDTH, x0 + cols)):
            ch = row[x]
            colour = TERRAIN_RGB.get(ch, (80, 80, 80))
            if ch == "G" and states.get(_opening_at(bf, x, y), "intact") == "destroyed":
                colour = (90, 78, 64)
                ch = ","
            rx, ry = _world_to_screen(tile_px, origin, x, y)
            blit_terrain(surf, ch, rx, ry, tile_px, x, y, colour)
            if (x, y) in bf.circulation and ch == "=":
                pygame.draw.rect(surf, (170, 140, 80), (rx, ry, int(tile_px) + 1, int(tile_px) + 1), 1)

    for eng in engines or ():
        colour = ENGINE_RGB.get(eng.engine_type, (200, 120, 60))
        w0, h0 = eng.size()
        rx, ry = _world_to_screen(tile_px, origin, eng.x, eng.y)
        rec = pygame.Rect(rx, ry, int(w0 * tile_px), int(h0 * tile_px))
        body = pygame.Surface(rec.size, pygame.SRCALPHA)
        body.fill((*colour, 210))
        surf.blit(body, rec.topleft)
        pygame.draw.rect(surf, (255, 230, 180), rec, max(1, int(tile_px // 8)))
        label = _font(max(14, int(tile_px))).render(eng.engine_type, True, (255, 240, 210))
        surf.blit(label, (rec.x + 3, rec.y + 2))

    for result, valid in ghosts or ():
        if not result.tiles:
            continue
        xs = [t[0] for t in result.tiles]
        ys = [t[1] for t in result.tiles]
        rx, ry = _world_to_screen(tile_px, origin, min(xs), min(ys))
        rec = pygame.Rect(
            rx, ry,
            int((max(xs) - min(xs) + 1) * tile_px),
            int((max(ys) - min(ys) + 1) * tile_px),
        )
        col = (60, 190, 90, 110) if valid else (200, 50, 40, 130)
        ghost = pygame.Surface(rec.size, pygame.SRCALPHA)
        ghost.fill(col)
        surf.blit(ghost, rec.topleft)
        pygame.draw.rect(surf, col[:3], rec, 2)

    if player:
        px, py = _world_to_screen(tile_px, origin, player[0] + 0.5, player[1] + 0.5)
        r = max(4, int(tile_px * 0.4))
        pygame.draw.circle(surf, (40, 50, 160), (px, py), r)
        pygame.draw.circle(surf, (255, 236, 190), (px, py), r, 2)


def _opening_at(bf: Battlefield, x: int, y: int) -> Optional[str]:
    for oid, op in bf.plane.openings.items():
        r = op.rect
        if r[0] <= x <= r[2] and r[1] <= y <= r[3]:
            return oid
    return None


def camera_origin_centered(player: Tuple[int, int], tile_px: float, view: Tuple[int, int]) -> Tuple[float, float]:
    vw, vh = view
    return player[0] - (vw / tile_px) / 2, player[1] - (vh / tile_px) / 2


def render_walk_frame(
    bf: Battlefield,
    player: Tuple[int, int],
    engines: Sequence[PlacedEngine],
    title: str,
    subtitle: str,
    size: Tuple[int, int] = (1600, 900),
    tile_px: float = 18,
    ghosts=None,
    gate_states=None,
) -> pygame.Surface:
    surf = pygame.Surface(size)
    surf.fill((18, 22, 18))
    origin = camera_origin_centered(player, tile_px, (size[0], size[1] - 110))
    world = surf.subsurface(pygame.Rect(0, 58, size[0], size[1] - 110))
    draw_world(world, bf, origin, tile_px, engines, ghosts, player, gate_states)
    _title(surf, title, subtitle)
    # Mini-map
    mm = 180
    mini = pygame.Surface((mm, mm))
    mini.fill((20, 24, 20))
    sx, sy = mm / WIDTH, mm / HEIGHT
    for name, col in (("ring_route", (170, 140, 80)), ("courtyard", (140, 132, 118)),
                      ("keep", (70, 70, 76)), ("staging_south", (160, 70, 50)),
                      ("staging_north", (160, 70, 50))):
        rec = bf.plane.landmarks[name].rect
        pygame.draw.rect(mini, col, pygame.Rect(
            int(rec[0] * sx), int(rec[1] * sy),
            int((rec[2] - rec[0] + 1) * sx), int((rec[3] - rec[1] + 1) * sy),
        ), 1)
    pygame.draw.circle(mini, (80, 120, 255), (int(player[0] * sx), int(player[1] * sy)), 3)
    surf.blit(mini, (size[0] - mm - 16, 70))
    pygame.draw.rect(surf, (200, 160, 70), pygame.Rect(size[0] - mm - 16, 70, mm, mm), 1)
    _caption(surf, f"walk camera {tile_px:.0f}px/tile · player {player} · engines are placed entities")
    return surf


def render_labelled_layout(bf: Optional[Battlefield] = None, size: Tuple[int, int] = (1400, 1400),
                           engines: Optional[Sequence[PlacedEngine]] = None) -> pygame.Surface:
    bf = bf or build_battlefield()
    margin_x, margin_top, margin_bot = 24, 70, 58
    tile = min((size[0] - margin_x * 2) / WIDTH, (size[1] - margin_top - margin_bot) / HEIGHT)
    ox, oy = margin_x, margin_top
    surf = pygame.Surface(size)
    surf.fill((18, 22, 20))
    for y, row in enumerate(bf.plane.grid):
        for x, ch in enumerate(row):
            blit_terrain(
                surf, ch, int(ox + x * tile), int(oy + y * tile), tile, x, y,
                TERRAIN_RGB.get(ch, (80, 80, 80)),
            )
    if engines:
        world = surf.subsurface(pygame.Rect(0, 0, size[0], size[1]))
        # draw engines in full-map space
        for eng in engines:
            colour = ENGINE_RGB.get(eng.engine_type, (200, 120, 60))
            w0, h0 = eng.size()
            rec = pygame.Rect(int(ox + eng.x * tile), int(oy + eng.y * tile), int(w0 * tile), int(h0 * tile))
            pygame.draw.rect(surf, colour, rec)
            pygame.draw.rect(surf, (255, 230, 180), rec, 1)

    def label(rect: Rect, name: str):
        cx = int(ox + ((rect[0] + rect[2]) / 2) * tile)
        cy = int(oy + ((rect[1] + rect[3]) / 2) * tile)
        img = _font(18).render(name, True, (255, 240, 210))
        surf.blit(img, (cx - img.get_width() // 2, cy - img.get_height() // 2))

    for key, name in (
        ("staging_south", "South staging"), ("staging_north", "North staging"),
        ("staging_west", "West staging"), ("staging_east", "East staging"),
        ("courtyard", "Courtyard"), ("keep", "Keep"),
        ("north_inner", "North inner passage"),
        ("center_lane", "South lane"), ("north_lane", "North lane"),
        ("west_lane", "West lane"), ("east_lane", "East lane"),
    ):
        label(bf.plane.landmarks[key].rect, name)
    for oid, op in bf.plane.openings.items():
        if oid != "keep_doors":
            label(op.rect, op.name.split()[0])
    _title(surf, f"{MAP_TITLE} — full-perimeter play-space ({WIDTH}×{HEIGHT})",
           "Collision grid. Gold/tan ring is reserved circulation. Keep does not touch the north battlefield.")
    _caption(surf, f"tile {TILE_METERS}m · wall-walk pale · water ditches with crossings")
    return surf


def render_placement_preview(bf: Battlefield, engines: Sequence[PlacedEngine],
                             valid_ghost: PlacementResult, invalid_ghost: PlacementResult,
                             size: Tuple[int, int] = (1600, 1000)) -> pygame.Surface:
    # Overview camera centered on castle
    ww, wn, we, ws = bf.wall_box
    player = ((ww + we) // 2, (wn + ws) // 2)
    surf = render_walk_frame(
        bf, player, engines,
        f"{MAP_TITLE} — player-built engines + ghost placement",
        "Green ghost = valid   Red ghost = rejected   Timber rectangles = placed entities (not landscape art)",
        size, tile_px=8,
        ghosts=[(valid_ghost, True), (invalid_ghost, False)],
    )
    legend = [
        "Valid ghost: legal exterior footprint",
        f"Invalid: {invalid_ghost.reason}",
        f"Placed sample: {len(engines)} engines on multiple sides (demo, not a cap)",
    ]
    y = 70
    for line in legend:
        img = _font(22).render(line, True, (255, 230, 176))
        pygame.draw.rect(surf, (16, 12, 10), img.get_rect(topleft=(16, y)).inflate(12, 6))
        surf.blit(img, (22, y + 2))
        y += 28
    return surf
