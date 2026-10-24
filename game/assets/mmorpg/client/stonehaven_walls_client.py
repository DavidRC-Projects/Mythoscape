"""Style B Stonehaven fort walls — AI kit sprites on the city shell.

Server collision stays on WALL tiles (world_map.is_stonehaven_fort_wall).
World-space props only: no billboarding, no camera-facing rotates of front art.
East/west curtains use authored EW sprites (not rotated NS art).
North ring has no city gate/curtain (castle approach stays open).
South gate is an open arch between spaced towers; no west/east side gates.
"""
from __future__ import annotations

import os

import pygame

import world_map as wm

PACK = os.path.join(os.path.dirname(__file__), "assets", "props", "stonehaven_walls")
_RAW = {}
_SCALED = {}

# Footprint widths in tiles for placement / culling.
_SPAN = {
    "wall_segment_ns": 5,
    "wall_segment_ew": 2,
    "wall_tower": 6,
    "gate_south_open": 10,
}

SOUTH_GATE_X = 119
# Flank towers sit well outside the arch so the entrance reads wide.
SOUTH_TOWER_DX = 9


def enabled(client):
    return (
        not getattr(client, "dungeon", None)
        and os.path.isdir(PACK)
        and os.path.isfile(os.path.join(PACK, "wall_segment_ns.png"))
        and os.path.isfile(os.path.join(PACK, "wall_tower.png"))
    )


def _raw(name):
    if name not in _RAW:
        path = os.path.join(PACK, f"{name}.png")
        try:
            _RAW[name] = pygame.image.load(path).convert_alpha()
        except Exception as exc:
            print("[stonehaven_walls]", exc)
            _RAW[name] = None
    return _RAW[name]


def _scaled(name, tile, flip_x=False, scale=1.0):
    key = (name, int(tile), bool(flip_x), round(float(scale), 2))
    if key in _SCALED:
        return _SCALED[key]
    src = _raw(name)
    if src is None:
        _SCALED[key] = None
        return None
    span = _SPAN.get(name, 4)
    if name == "wall_tower":
        target_w = max(8, int(tile * 5.5 * scale))
        target_h = max(target_w, int(tile * 5.8 * scale))
    elif name == "gate_south_open":
        # Wide open arch between the spaced flank towers.
        target_w = max(8, int(span * tile * scale))
        target_h = max(8, int(tile * 5.6 * scale))
    elif name == "wall_segment_ew":
        target_w = max(8, int(tile * 2.6 * scale))
        target_h = max(8, int(tile * 4.2 * scale))
    else:
        target_w = max(8, int(span * tile * scale))
        target_h = max(8, int(src.get_height() * target_w / max(1, src.get_width())))
        target_h = max(target_h, int(tile * 2.2 * scale))
    img = pygame.transform.smoothscale(src, (target_w, target_h))
    if flip_x:
        img = pygame.transform.flip(img, True, False)
    _SCALED[key] = img
    for old in [k for k in _SCALED if k[1] != int(tile)][:-8]:
        _SCALED.pop(old, None)
    return img


def draw_ground(client, rect, wx, wy):
    """Dark stone strip under fort WALL tiles (sprites carry the Style B look)."""
    if not enabled(client) or not wm.is_stonehaven_fort_wall(wx, wy):
        return False
    import procedural_sprites_finished as sprites
    sprites.draw_stone_floor(client.screen, rect, wx, wy)
    shade = pygame.Surface((rect.w, rect.h), pygame.SRCALPHA)
    shade.fill((20, 18, 24, 70))
    client.screen.blit(shade, rect.topleft)
    return True


def castle_bridge_x():
    try:
        import castle_v2
        if castle_v2.active():
            gx, _ = castle_v2.w(111, 55)
            return gx
    except Exception:
        pass
    return None


def _pieces(client):
    """World anchors: south gate + continuous west/east curtains (no side gates)."""
    cx0, cy0, cx1, cy1 = wm.city_bounds()
    out = []
    # Corner round towers
    for wx, wy in ((cx0, cy0), (cx1, cy0), (cx0, cy1), (cx1, cy1)):
        out.append(("wall_tower", wx, wy, False, "tower", 1.0))

    # South: spaced flank towers + wide open arch between them
    out.append(("wall_tower", SOUTH_GATE_X - SOUTH_TOWER_DX, cy1, False, "tower", 1.2))
    out.append(("wall_tower", SOUTH_GATE_X + SOUTH_TOWER_DX, cy1, False, "tower", 1.2))
    out.append(("gate_south_open", SOUTH_GATE_X, cy1, False, "gate_s", 1.15))

    def _seg_row(y, x0, x1, skip_centers, skip_r):
        x = x0
        while x <= x1:
            if any(abs(x - sx) <= skip_r for sx in skip_centers):
                x += 1
                continue
            if abs(x - cx0) < 4 or abs(x - cx1) < 4:
                x += 1
                continue
            out.append(("wall_segment_ns", x, y, False, "seg_ns", 1.0))
            x += 3

    def _seg_col(x, y0, y1, flip=False):
        y = y0
        while y <= y1:
            if abs(y - cy0) < 4 or abs(y - cy1) < 4:
                y += 1
                continue
            out.append(("wall_segment_ew", x, y, flip, "seg_ew", 1.0))
            y += 3

    # Skip arch + flank towers on the south curtain
    _seg_row(
        cy1,
        cx0 + 4,
        cx1 - 4,
        [SOUTH_GATE_X, SOUTH_GATE_X - SOUTH_TOWER_DX, SOUTH_GATE_X + SOUTH_TOWER_DX],
        4,
    )
    # Continuous west/east walls (no side entrances)
    _seg_col(cx0, cy0 + 4, cy1 - 4, flip=False)
    _seg_col(cx1, cy0 + 4, cy1 - 4, flip=True)
    return out


def queue(client, draw_list, cam_x, cam_y, tile):
    if not enabled(client):
        return
    scr = client.screen.get_rect()
    view = scr.inflate(tile * 8, tile * 8)
    try:
        px, py = client.player_xy() if getattr(client, "player", None) else (0, 0)
    except Exception:
        px, py = 0, 0
    for name, wx, wy, flip, kind, scale in _pieces(client):
        if max(abs(wx - px), abs(wy - py)) > 58:
            continue
        img = _scaled(name, tile, flip_x=flip, scale=scale)
        if img is None:
            continue
        sx, sy = client.world_to_view_offset(wx, wy, cam_x, cam_y)
        cx = int(sx * tile + tile // 2)
        feet = int(sy * tile + tile * 0.95)
        box = pygame.Rect(
            cx - img.get_width() // 2,
            feet - img.get_height(),
            img.get_width(),
            img.get_height(),
        )
        if not box.colliderect(view):
            continue
        if kind == "gate_s":
            sort_y = feet + tile // 2
        elif kind == "tower":
            sort_y = feet + tile // 3
        else:
            sort_y = feet

        def _draw(img=img, box=box):
            client.screen.blit(img, box.topleft)

        draw_list.append((sort_y, 2, _draw))
