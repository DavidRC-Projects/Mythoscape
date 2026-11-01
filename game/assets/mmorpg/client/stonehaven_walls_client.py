"""Style B Stonehaven fort walls — AI kit sprites on the city shell.

Server collision stays on WALL tiles (world_map.is_stonehaven_fort_wall).
World-space props only: no billboarding, no camera-facing rotates of front art.
East/west curtains use authored EW sprites (not rotated NS art).
North ring has no city gate/curtain (castle approach stays open).
South gate is an open arch between spaced towers; no west/east side gates.

HD painted kit (assets/props/stonehaven_walls/hd/, 40 px per tile) is drawn
from world_map.stonehaven_wall_layout() — the same table the server stamps
WALL from — so collision matches the art exactly. The legacy sprites above
remain only as the error fallback when the HD kit cannot load.
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
    """Ground under fort WALL tiles (sprites carry the Style B look)."""
    if not enabled(client) or not wm.is_stonehaven_fort_wall(wx, wy):
        return False
    import procedural_sprites_finished as sprites
    cx0, cy0, cx1, cy1 = wm.city_bounds()
    outside = wy > cy1 or wx < cx0 or wx > cx1 or wy < cy0
    if outside and _hd_ok():
        # Tower bases that stand proud of the curtain sit on the meadow.
        paint = getattr(client, "_paint_meadow", None)
        if not (paint and paint(rect, wx, wy, "village")):
            sprites.draw_grass(client.screen, rect, wx, wy)
        return True
    sprites.draw_stone_floor(client.screen, rect, wx, wy)
    if _hd_ok():
        # HD kit: no dark pads — the painted footing band carries the base.
        return True
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


# --------------------------------------------------------------------- HD kit
HD = os.path.join(PACK, "hd")
_HD_NAMES = ("wall_h", "wall_v", "tower", "gate_s", "footing_h", "footing_v", "footing_disc")
_HD_RAW = {}
_HD_SCALED = {}
_HD_STRIP = {}
# Anchor pixels in the 40 px/tile art.
_TOWER_CX, _TOWER_BASE = 76, 476      # tower.png: centre column, ground base row
_WALLH_BASE = 184                      # wall_h.png: wall foot row
_GATE_WALL_BASE = 416                  # gate_s.png: row that sits on the wall base line


def _hd_raw(name):
    if name not in _HD_RAW:
        try:
            _HD_RAW[name] = pygame.image.load(os.path.join(HD, f"{name}.png")).convert_alpha()
        except Exception as exc:
            print("[stonehaven_walls] hd", name, exc)
            _HD_RAW[name] = None
    return _HD_RAW[name]


def _hd_ok():
    return all(_hd_raw(n) is not None for n in _HD_NAMES)


def _hd(name, tile):
    key = (name, int(tile))
    if key not in _HD_SCALED:
        src = _hd_raw(name)
        if src is None:
            return None
        k = tile / 40.0
        if int(tile) == 40:
            img = src
        else:
            img = pygame.transform.smoothscale(
                src, (max(1, round(src.get_width() * k)), max(1, round(src.get_height() * k))))
        for old in [kk for kk in _HD_SCALED if kk[1] != int(tile)]:
            _HD_SCALED.pop(old, None)
            _HD_STRIP.clear()
        _HD_SCALED[key] = img
    return _HD_SCALED[key]


def _tiled(name, tile, w, h, axis):
    """A run-long strip built by repeating one seamless HD tile."""
    key = (name, int(tile), int(w), int(h))
    if key in _HD_STRIP:
        return _HD_STRIP[key]
    src = _hd(name, tile)
    if src is None:
        return None
    surf = pygame.Surface((max(1, w), max(1, h)), pygame.SRCALPHA)
    if axis == "x":
        for x in range(0, w, src.get_width()):
            surf.blit(src, (x, 0))
    else:
        for y in range(0, h, src.get_height()):
            surf.blit(src, (0, y))
    _HD_STRIP[key] = surf
    return surf


_PILLAR_SCALE = 0.62
_PILLAR = {}


def _pillar(tile, name="tower"):
    """Scaled-down tower used as a side-gate end pillar."""
    key = (name, int(tile))
    if key not in _PILLAR:
        src = _hd(name, tile)
        if src is None:
            return None
        if any(kk[1] != int(tile) for kk in _PILLAR):
            _PILLAR.clear()
        _PILLAR[key] = pygame.transform.smoothscale(
            src, (max(1, round(src.get_width() * _PILLAR_SCALE)),
                  max(1, round(src.get_height() * _PILLAR_SCALE))))
    return _PILLAR[key]


def _queue_hd(client, draw_list, cam_x, cam_y, tile, lay=None):
    """Painted curtain from the shared layout (art == collision)."""
    if int(getattr(client, "camera_yaw", 0) or 0) % 4:
        return False  # authored for the default camera; legacy art handles yaw
    if lay is None:
        lay = wm.stonehaven_wall_layout()
    ox, oy = client.world_to_view_offset(0, 0, cam_x, cam_y)

    def px(wx, wy):
        return int(round((ox + wx) * tile)), int(round((oy + wy) * tile))

    view = client.screen.get_rect().inflate(tile * 4, tile * 14)
    t = tile
    k = tile / 40.0
    ground = []   # footing decals, drawn before every object

    def add(sort_y, img, pos, area=None):
        r = pygame.Rect(pos, (area.w, area.h) if area else img.get_size())
        if not r.colliderect(view):
            return
        draw_list.append((sort_y, 2, lambda img=img, pos=pos, area=area:
                          client.screen.blit(img, pos, area)))

    # South / north facing curtain strips
    for base, x0, x1 in lay["h_runs"]:
        w = int((x1 - x0) * t)
        h_img = _hd("wall_h", t)
        strip = _tiled("wall_h", t, w, h_img.get_height(), "x")
        fx, fy = px(x0, base)
        add(fy, strip, (fx, fy - int(_WALLH_BASE * k)))
        foot = _tiled("footing_h", t, w, _hd("footing_h", t).get_height(), "x")
        ground.append((foot, (fx, fy - int(foot.get_height() * 0.45))))
    # Flat east / west curtain + castle spurs: one slice per tile row so
    # walkers sort correctly against it.
    for xc, y0, y1 in list(lay["v_runs"]) + list(lay.get("spurs", ())):
        col = _hd("wall_v", t)
        hgt = int((y1 - y0) * t)
        strip = _tiled("wall_v", t, col.get_width(), hgt, "y")
        sx, sy = px(xc, y0)
        sx -= col.get_width() // 2
        for i in range(int(y1 - y0)):
            area = pygame.Rect(0, i * t, col.get_width(), t)
            add(sy + (i + 1) * t, strip, (sx, sy + i * t), area)
        fv = _tiled("footing_v", t, _hd("footing_v", t).get_width(), hgt, "y")
        ground.append((fv, (sx + col.get_width() // 2 - fv.get_width() // 2, sy)))
    # Towers (no wall stubs of their own — the strip runs behind them)
    tw = _hd("tower", t)
    disc = _hd("footing_disc", t)
    for cx, base in list(lay["towers"]):
        bx, by = px(cx, base)
        add(by, tw, (bx - int(_TOWER_CX * k), by - int(_TOWER_BASE * k)))
        ground.append((disc, (bx - disc.get_width() // 2, by - int(disc.get_height() * 0.7))))
    # End pillars where a side curtain stops at a side gate (art only — the
    # collision is the run itself): a slim capped tower on each bare end.
    corners = {round(b) for _, b in lay["towers"]}
    pil = _pillar(t)
    if pil is not None:
        pk = k * _PILLAR_SCALE
        for xc, y0, y1 in lay["v_runs"]:
            for ey, base in ((y0, y0 + 0.9), (y1, y1 + 0.1)):
                if any(abs(ey - b) < 3 for b in corners):
                    continue  # corner/flank tower already caps this end
                bx, by = px(xc, base)
                add(by, pil, (bx - int(_TOWER_CX * pk), by - int(_TOWER_BASE * pk)))
                ds = _pillar(t, "footing_disc")
                if ds is not None:
                    ground.append((ds, (bx - ds.get_width() // 2, by - int(ds.get_height() * 0.7))))
    if lay.get("gate_s"):
        gl, gbase = lay["gate_s"]
        gs = _hd("gate_s", t)
        gx, gy = px(gl, gbase)
        add(gy + int(1.7 * t), gs, (gx, gy - int(_GATE_WALL_BASE * k)))
    for cx, base in lay["gate_towers"]:
        bx, by = px(cx, base)
        ground.append((disc, (bx - disc.get_width() // 2, by - int(disc.get_height() * 0.7))))

    def _ground(items=ground):
        for img, pos in items:
            client.screen.blit(img, pos)

    draw_list.append((-10 ** 9, 0, _ground))
    return True


def queue(client, draw_list, cam_x, cam_y, tile):
    if not enabled(client):
        return
    try:
        if _hd_ok() and _queue_hd(client, draw_list, cam_x, cam_y, tile):
            _queue_hd(client, draw_list, cam_x, cam_y, tile, wm.estate_wall_layout())
            return
    except Exception as exc:  # HD art is primary; legacy sprites are the fallback
        print("[stonehaven_walls] hd queue failed, legacy fallback:", exc)
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
