"""Fairy Glade on the client: glowing tree ring, banner, minimap.

The server grid marks every trunk as WALL (fairy_glade.ring_cells). Here the
trunk tile is painted as the glade ground and a painted glowing tree stands on
it (y-sorted with players and NPCs). Canopies stay solid — they do not ghost
when the player walks the lanes. The two hidden lanes are ordinary PATH tiles
under the canopies. Missing art -> False everywhere, so the old drawing runs.
"""
from __future__ import annotations

import math
import os
import time

import pygame

import fairy_glade as FG
import world_map as wm

_DIR = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", "assets", "hd_trees"))
_NAMES = ("glade_tree_a", "glade_tree_b")
_HEIGHT_TILES = 4.6
FADE_ALPHA = 70       # mostly see-through
FADE_RADIUS = 2.8     # tiles: trees this close to a player on/near a lane fade
LANE_SCALE = 0.62     # trees right beside a lane are smaller so the path stays readable
_ARCH = "glade_arch"
_ARCH_SPAN = 0.64     # post feet sit at 18 % and 82 % of the arch art width
BANNER_SECONDS = 3.2
_RAW = {}
_CACHE = {}
_GLOW = {}
_state = {"zone": None, "until": 0.0}


def _raw(name):
    if name not in _RAW:
        path = os.path.join(_DIR, name + ".png")
        try:
            _RAW[name] = pygame.image.load(path).convert_alpha() if os.path.isfile(path) else None
        except pygame.error:
            _RAW[name] = None
    return _RAW[name]


def ready():
    return all(_raw(n) is not None for n in _NAMES)


def active(client):
    return ready() and not getattr(client, "dungeon", None)


def _variant(x, y):
    h = (int(x) * 73856093) ^ (int(y) * 19349663)
    return (h ^ (h >> 13)) & 0xFFFF


def _sprite(kind, tile, flip, size_q, faded, small=False):
    key = (kind, tile, flip, size_q, faded, small)
    img = _CACHE.get(key)
    if img is not None:
        return img
    raw = _raw(_NAMES[kind])
    h = max(8, int(tile * _HEIGHT_TILES * (0.9 + 0.05 * size_q) * (LANE_SCALE if small else 1.0)))
    w = max(4, round(raw.get_width() * h / raw.get_height()))
    img = pygame.transform.smoothscale(raw, (w, h))
    if flip:
        img = pygame.transform.flip(img, True, False)
    if faded:
        img = img.copy()
        img.fill((255, 255, 255, FADE_ALPHA), special_flags=pygame.BLEND_RGBA_MULT)
    if len(_CACHE) > 320:
        _CACHE.clear()
    _CACHE[key] = img
    return img


def _glow(r, colour):
    """Additive (BLEND_ADD) fairy light: black background, soft coloured core."""
    key = (r, colour)
    s = _GLOW.get(key)
    if s is None:
        s = pygame.Surface((r * 2, r * 2))
        s.fill((0, 0, 0))
        for i in range(r, 0, -1):
            k = (1 - i / r) ** 2.0 * 0.95
            pygame.draw.circle(s, tuple(int(c * k) for c in colour), (r, r), i)
        _GLOW[key] = s
    return s


def draw_ground(client, rect, wx, wy):
    """Trunk tiles paint as the surrounding ground; the tree sprite covers them."""
    if not active(client) or not _glade_ground(wx, wy):
        return False
    client.draw_terrain_tile(rect, wm.GRASS, wx, wy, 0.0)
    return True


def _glade_ground(x, y):
    """WALL tiles that must still show ground: tree trunks, plus any lane tile
    the server reports as WALL (a server still running an older glade layout
    than this client). Without this those tiles drew as bare dark wall."""
    return FG.is_trunk(x, y) or FG.is_lane(x, y)


def hides_wall(x, y):
    return ready() and _glade_ground(x, y)


def _view_scan_radius(client, tile):
    """How far (in world tiles) to scan for trees.

    Area view uses a smaller TILE so many more tiles fit on screen; a fixed
    radius made trees vanish at the glade entrance when zoomed out.
    """
    try:
        from client import MAP_W, MAP_H
        map_w, map_h = MAP_W, MAP_H
    except Exception:
        map_w, map_h = 900, 640
    tile = max(8, int(tile or 40))
    # Cover the whole map viewport (half-width/height), plus canopy overhang.
    return max(28, map_w // tile // 2 + 8, map_h // tile // 2 + 8)


def queue(client, draw_list, cam_x, cam_y, tile, t=0.0):
    """Queue every visible glade tree. Yaw-safe: scans world tiles near the player."""
    if not active(client) or not getattr(client, "player", None):
        return
    _track_zone(client)
    px, py = client.player_xy()
    r = _view_scan_radius(client, tile)
    if not (px - r <= 44 and px + r >= 0 and py - r <= 100 and py + r >= 48):
        return
    # Cull against the map viewport (not the full window with sidebar).
    try:
        from client import MAP_W, MAP_H
        view = pygame.Rect(0, 0, MAP_W, MAP_H)
    except Exception:
        view = client.screen.get_rect()
    now = time.time()
    _queue_arches(client, draw_list, cam_x, cam_y, tile, px, py, view, now, r)
    # Margin in screen pixels — scale with tile so small tiles still keep off-screen trees
    # that lean into the viewport with tall canopies.
    margin_x = max(tile * 3, 80)
    margin_y_top = max(tile, 40)
    margin_y_bot = max(tile * 5, 120)
    for (x, y) in FG.tree_cells():
        if abs(x - px) > r or abs(y - py) > r:
            continue
        sx, sy = client.world_to_view_offset(x, y, cam_x, cam_y)
        cx = int(sx * tile + tile // 2)
        cy = int(sy * tile + tile // 2)
        if cx < view.left - margin_x or cx > view.right + margin_x or cy < view.top - margin_y_top or cy > view.bottom + margin_y_bot:
            continue
        v = _variant(x, y)
        kind = v & 1
        flip = bool(v & 2)
        size_q = (v >> 2) % 5
        jx = ((v >> 5) % 7 - 3) * tile // 18
        jy = ((v >> 8) % 5 - 2) * tile // 18
        small = FG.near_lane(x, y)
        if small:
            jx = jy = 0

        def _draw(cx=cx + jx, cy=cy + jy, kind=kind, flip=flip, size_q=size_q, v=v, small=small):
            img = _sprite(kind, tile, flip, size_q, False, small)
            feet = cy + int(tile * 0.38)
            box = pygame.Rect(cx - img.get_width() // 2, feet - img.get_height(), img.get_width(), img.get_height())
            client.screen.blit(img, box.topleft)
            # Soft fairy-light glow drifting in the canopy.
            ph = (v % 628) / 100.0
            for i in range(2):
                a = ph + now * (0.7 + 0.25 * i) + i * 2.1
                gx = box.centerx + int(math.cos(a) * box.w * 0.22)
                gy = box.top + int(box.h * (0.28 + 0.12 * i) + math.sin(a * 1.3) * box.h * 0.06)
                col = (255, 214, 140) if kind == 0 else (170, 230, 255)
                g = _glow(max(4, tile // 4), col)
                client.screen.blit(g, (gx - g.get_width() // 2, gy - g.get_height() // 2),
                                   special_flags=pygame.BLEND_ADD)
        draw_list.append((cy + tile // 3, 1, _draw))


def _arch_sprite(tile, span_tiles):
    raw = _raw(_ARCH)
    if raw is None:
        return None
    w = max(8, int(tile * span_tiles / _ARCH_SPAN))
    key = ("arch", tile, w)
    img = _CACHE.get(key)
    if img is None:
        img = pygame.transform.smoothscale(raw, (w, max(8, round(raw.get_height() * w / raw.get_width() * ARCH_TALL))))
        _CACHE[key] = img
    return img


ARCH_TALL = 1.18     # arch art stretched a little taller so it reads as a gateway
_SIGN = {}


def _sign(tile, font):
    key = (tile, id(font))
    img = _SIGN.get(key)
    if img is None:
        text = font.render("Fairy Glade", True, (255, 236, 190))
        bw, bh = text.get_width() + tile // 2, text.get_height() + tile // 4
        h = bh + int(tile * 1.1)
        img = pygame.Surface((bw + 4, h), pygame.SRCALPHA)
        pole = pygame.Rect(bw // 2 - tile // 12, bh - 2, max(3, tile // 6), h - bh + 2)
        pygame.draw.rect(img, (78, 52, 34), pole, border_radius=2)
        board = pygame.Rect(2, 0, bw, bh)
        pygame.draw.rect(img, (112, 74, 140), board, border_radius=max(3, tile // 8))
        pygame.draw.rect(img, (232, 196, 255), board, 2, border_radius=max(3, tile // 8))
        img.blit(text, (board.x + (bw - text.get_width()) // 2, board.y + (bh - text.get_height()) // 2))
        _SIGN[key] = img
    return img


def _queue_arches(client, draw_list, cam_x, cam_y, tile, px, py, view, now=0.0, scan_r=30):
    """Entrance / exit arches. The posts are WALL tiles on the server; the 3-wide
    lane between them is open. The arch sorts just below its own row, so a player
    in the arch row or north of it walks under the span, one south of it in front.
    Lanterns glow on both posts and along the span; a 'Fairy Glade' signpost
    stands on the outside of each gate."""
    font = getattr(client, "font_label", None) or getattr(client, "font_small", None)
    arch_r = max(30, int(scan_r or 30))
    for name, (ax, ay), (bx, by) in getattr(FG, "ARCHES", ()):
        if abs(ax - px) > arch_r or abs(ay - py) > arch_r:
            continue
        img = _arch_sprite(tile, bx - ax)
        if img is None:
            return
        s1 = client.world_to_view_offset(ax, ay, cam_x, cam_y)
        s2 = client.world_to_view_offset(bx, by, cam_x, cam_y)
        sx, sy = (s1[0] + s2[0]) / 2.0, (s1[1] + s2[1]) / 2.0
        cx = int(sx * tile + tile // 2)
        feet = int(sy * tile + tile * 0.92)
        box = pygame.Rect(cx - img.get_width() // 2, feet - img.get_height(), img.get_width(), img.get_height())
        if not box.colliderect(view.inflate(tile * 4, tile * 4)):
            continue

        def _draw(img=img, box=box, name=name):
            client.screen.blit(img, box.topleft)
            pulse = 0.75 + 0.25 * math.sin(now * 2.2 + (0 if name == "north" else 1.7))
            r = max(6, int(tile * 0.55 * pulse))
            spots = [(0.18, 0.55), (0.82, 0.55), (0.24, 0.30), (0.76, 0.30), (0.50, 0.12),
                     (0.36, 0.17), (0.64, 0.17)]
            for i, (fx, fy) in enumerate(spots):
                col = (255, 210, 130) if i < 2 else (200, 150, 255) if i % 2 else (150, 230, 255)
                g = _glow(r if i < 2 else max(4, r * 2 // 3), col)
                gx, gy = box.x + int(box.w * fx), box.y + int(box.h * fy)
                client.screen.blit(g, (gx - g.get_width() // 2, gy - g.get_height() // 2),
                                   special_flags=pygame.BLEND_ADD)

        draw_list.append((int(sy * tile + tile * 0.98), 2, _draw))
        if font is not None:
            # Signpost on the outside, just beyond the left post.
            out = -1 if name == "north" else 1
            sxy = client.world_to_view_offset((ax - 1) if name == "north" else (bx + 1), ay + out, cam_x, cam_y)
            sg = _sign(tile, font)
            spx = int(sxy[0] * tile + tile // 2) - sg.get_width() // 2
            spy = int(sxy[1] * tile + tile * 0.85) - sg.get_height()
            draw_list.append((int(sxy[1] * tile + tile * 0.9), 2,
                              lambda sg=sg, pos=(spx, spy): client.screen.blit(sg, pos)))


# ---- banner -----------------------------------------------------------------
def _in_glade(x, y):
    x0, y0, x1, y1 = FG.ZONE
    return x0 <= x <= x1 and y0 <= y <= y1


def _track_zone(client):
    px, py = client.player_xy()
    inside = _in_glade(int(px), int(py))
    was = _state["zone"]
    if was is False and inside:
        _state["until"] = time.time() + BANNER_SECONDS
    _state["zone"] = inside


def banner_text():
    return "Entering Fairy Glade"


def draw_banner(client):
    if getattr(client, "dungeon", None) or not getattr(client, "player", None):
        return
    if _state["zone"] is None:
        _track_zone(client)
    left = _state["until"] - time.time()
    if left <= 0:
        return
    font = getattr(client, "font_label", None) or pygame.font.SysFont("georgia", 26, bold=True)
    alpha = int(255 * min(1.0, left / 0.6, (BANNER_SECONDS - left) / 0.4 + 0.01))
    text = font.render(banner_text(), True, (246, 232, 255))
    w, h = text.get_width() + 56, text.get_height() + 18
    panel = pygame.Surface((w, h), pygame.SRCALPHA)
    pygame.draw.rect(panel, (38, 18, 64, 210), panel.get_rect(), border_radius=12)
    pygame.draw.rect(panel, (214, 170, 255, 230), panel.get_rect(), 2, border_radius=12)
    panel.blit(text, (28, 9))
    for i, ox in enumerate((14, w - 14)):
        pygame.draw.circle(panel, (255, 226, 150, 230), (ox, h // 2), 4)
    panel.set_alpha(max(0, min(255, alpha)))
    sw = client.screen.get_width()
    map_w = min(sw, 900)
    client.screen.blit(panel, ((map_w - w) // 2, 70))


# ---- minimap ------------------------------------------------------------------
def minimap(client, surf, mm_w, mm_h, vw, vh):
    if not ready():
        return
    for cells, col in ((FG.ring_cells(), (96, 54, 150)), (FG.lane_cells(), (196, 170, 120))):
        for (wx, wy) in cells:
            vx, vy = client.world_to_view(wx, wy)
            x0, y0 = int(vx * mm_w / vw), int(vy * mm_h / vh)
            x1, y1 = max(x0 + 1, int((vx + 1) * mm_w / vw)), max(y0 + 1, int((vy + 1) * mm_h / vh))
            surf.fill(col, (x0, y0, x1 - x0, y1 - y0))
    try:
        font = pygame.font.SysFont("arial", 10, bold=True)
        lab = font.render("Fairy Glade", True, (236, 214, 255))
        x0, y0, x1, y1 = FG.ZONE
        vx, vy = client.world_to_view((x0 + x1) // 2, (y0 + y1) // 2)
        lx = int(vx * mm_w / vw) - lab.get_width() // 2
        lx = max(2, min(surf.get_width() - lab.get_width() - 2, lx))
        surf.blit(lab, (lx, int(vy * mm_h / vh)))
    except Exception:
        pass
