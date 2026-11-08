"""Client side of the optional sewer tutorial (Below the Village).

Draws the sewer tiles/props, the overworld grate, Seraphine's speech
bubble, the eat-now prompt, the rescue fade and the reward panel.
"""
import math
import os
import time

import pygame

import world_map as wm

SEWER_ID = "sewer"

STONE = (74, 68, 58)
STONE_D = (52, 47, 40)
STONE_L = (98, 90, 76)
MOSS = (64, 86, 44)
WATER = (40, 58, 38)
WATER_L = (78, 102, 60)
WALL = (58, 52, 44)
WALL_D = (34, 30, 26)
MORTAR = (40, 36, 31)
WOOD = (104, 72, 40)
WOOD_D = (66, 44, 24)
IRON = (46, 44, 42)
WEB = (214, 214, 206)
FIRE = (255, 196, 90)


# ---------------------------------------------------------------- painted HD art (assets/sewer)
# Procedural drawing below is kept only as the error fallback when a PNG is missing.
_ART_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "assets", "sewer")
_RAW = {}
_SCALED = {}
TEX_TILES = 4   # one texture repeat spans 4x4 tiles


def _raw(name):
    if name not in _RAW:
        try:
            img = pygame.image.load(os.path.join(_ART_DIR, f"sewer_{name}.png"))
            _RAW[name] = img.convert_alpha() if pygame.display.get_surface() else img
        except Exception:
            _RAW[name] = None
    return _RAW[name]


def _tex(name, tw):
    """Texture scaled so TEX_TILES tiles span it; opaque (no alpha) for macOS."""
    key = ("tex", name, tw)
    if key not in _SCALED:
        r = _raw(name)
        if r is None:
            _SCALED[key] = None
        else:
            sc = pygame.transform.smoothscale(r, (tw * TEX_TILES, tw * TEX_TILES))
            out = pygame.Surface(sc.get_size()).convert() if pygame.display.get_surface() else pygame.Surface(sc.get_size())
            out.blit(sc, (0, 0))
            _SCALED[key] = out
    return _SCALED[key]


def _blit_tex(surf, name, rect, wx, wy):
    tex = _tex(name, rect.w)
    if tex is None:
        return False
    ox = (wx % TEX_TILES) * rect.w
    oy = (wy % TEX_TILES) * rect.h
    surf.blit(tex, rect.topleft, pygame.Rect(ox, oy, rect.w, rect.h))
    return True


def _sprite(name, width):
    key = ("spr", name, int(width))
    if key not in _SCALED:
        r = _raw(name)
        if r is None:
            _SCALED[key] = None
        else:
            w = max(4, int(width))
            h = max(4, int(r.get_height() * w / r.get_width()))
            _SCALED[key] = pygame.transform.smoothscale(r, (w, h))
    return _SCALED[key]


def _blit_sprite(surf, name, width, midbottom):
    sp = _sprite(name, width)
    if sp is None:
        return None
    r = sp.get_rect(midbottom=(int(midbottom[0]), int(midbottom[1])))
    surf.blit(sp, r)
    return r


_GLOW = {}


def _glow(radius):
    radius = max(8, int(radius))
    if radius not in _GLOW:
        g = pygame.Surface((radius * 2, radius * 2))
        g.fill((0, 0, 0))
        for i in range(radius, 0, -2):
            k = (1 - i / radius) ** 1.6
            pygame.draw.circle(g, (int(165 * k), int(98 * k), int(34 * k)), (radius, radius), i)
        _GLOW[radius] = g
    return _GLOW[radius]


def active(client):
    d = getattr(client, "dungeon", None)
    return bool(d and d.get("id") == SEWER_ID)


def _st(client):
    return (client.dungeon or {}).setdefault("sewer", {}) if client.dungeon else {}


def _h(x, y, k=0):
    n = (x * 73856093) ^ (y * 19349663) ^ (k * 83492791)
    n = (n ^ (n >> 13)) * 1274126177
    return (n & 0xFFFF) / 65535.0


def _shade(c, f):
    return tuple(max(0, min(255, int(v * f))) for v in c)


def _xy_in(lst, wx, wy):
    return any(int(p[0]) == wx and int(p[1]) == wy for p in (lst or []))


# ---------------------------------------------------------------- tiles
_FX = {}


def _fx(key, size, painter):
    k = (key, size)
    if k not in _FX:
        s = pygame.Surface((size, size), pygame.SRCALPHA)
        painter(s, size)
        _FX[k] = s
    return _FX[k]


def _paint_grime(s, n):
    for i in range(14):
        r = int(n * (0.10 + 0.22 * _h(i, n, 1)))
        x, y = int(n * _h(i, n, 2)), int(n * _h(i, n, 3))
        pygame.draw.circle(s, (8, 10, 6, 10 + int(16 * _h(i, n, 4))), (x, y), r)


def _paint_moss(s, n):
    for i in range(26):
        x, y = int(n * (0.2 + 0.6 * _h(i, 7, n))), int(n * (0.2 + 0.6 * _h(i, 8, n)))
        c = (48 + int(30 * _h(i, 9)), 72 + int(40 * _h(i, 10)), 28, 120 + int(80 * _h(i, 11)))
        pygame.draw.circle(s, c, (x, y), max(2, int(n * 0.06 * (0.6 + _h(i, 12)))))


def _paint_puddle(s, n):
    r = pygame.Rect(int(n * .08), int(n * .3), int(n * .84), int(n * .44))
    pygame.draw.ellipse(s, (10, 14, 12, 210), r)
    pygame.draw.ellipse(s, (26, 36, 30, 200), r.inflate(-6, -6))
    pygame.draw.ellipse(s, (60, 66, 52, 150), r, 2)
    # reflection: soft streak + warm glint
    pygame.draw.line(s, (140, 150, 130, 110), (r.x + r.w * .25, r.y + r.h * .38), (r.x + r.w * .62, r.y + r.h * .30), 2)
    pygame.draw.ellipse(s, (230, 170, 90, 120), (r.x + r.w * .55, r.y + r.h * .45, r.w * .18, r.h * .16))


def _paint_shadow(s, n):
    for i in range(n // 2):
        a = int(170 * (1 - i / (n / 2)) ** 1.8)
        pygame.draw.line(s, (0, 0, 0, a), (0, i), (n, i))


def _wallface(surf, rect, wx, wy_face, half):
    """Painted 2-tile-tall wall face strip (5 tiles long, seamless), offset per row so arches don't line up."""
    r = _raw("wallface")
    if r is None:
        return False
    n = 5
    key = ("wf", rect.w)
    if key not in _SCALED:
        sc = pygame.transform.smoothscale(r, (rect.w * n, rect.w * 2))
        out = pygame.Surface(sc.get_size()).convert() if pygame.display.get_surface() else pygame.Surface(sc.get_size())
        out.blit(sc, (0, 0))
        _SCALED[key] = out
    c = (wx + int(_h(3, wy_face, 77) * n)) % n
    surf.blit(_SCALED[key], rect.topleft, pygame.Rect(c * rect.w, half * rect.w, rect.w, rect.h))
    return True


_VAR = {}


def _blit_var(surf, img, rect, wx, wy, k):
    """One of 6 flipped/scaled variants, jittered inside the tile, so stamps don't read as a grid."""
    v = int(_h(wx, wy, k) * 6)
    key = (id(img), v)
    if key not in _VAR:
        im = pygame.transform.flip(img, v % 2 == 1, v % 3 == 1)
        sc = (0.7, 1.0, 1.25)[v % 3]
        _VAR[key] = pygame.transform.smoothscale(im, (int(im.get_width() * sc), int(im.get_height() * sc * (0.8 + 0.1 * (v % 3)))))
    im = _VAR[key]
    jx = int((_h(wx, wy, k + 1) - 0.5) * rect.w * 0.5)
    jy = int((_h(wx, wy, k + 2) - 0.5) * rect.h * 0.5)
    surf.blit(im, im.get_rect(center=(rect.centerx + jx, rect.centery + jy)))


def _floor_fx(surf, rect, wx, wy, client=None):
    n = rect.w
    if _h(wx, wy, 60) > 0.35:
        surf.blit(_fx("grime", n * 2, _paint_grime), (rect.x - n // 2, rect.y - n // 2))
    if _h(wx, wy, 61) > 0.80:
        _blit_var(surf, _fx("moss", n, _paint_moss), rect, wx, wy, 63)
    if _h(wx, wy, 62) > 0.88:
        _blit_var(surf, _fx("puddle", n, _paint_puddle), rect, wx, wy, 64)
    tiles = getattr(client, "tiles", None) if client else None
    if tiles and wy > 0 and tiles[wy - 1][wx] == wm.WALL:
        surf.blit(_fx("shadow", n, _paint_shadow), rect.topleft)


def _floor(surf, rect, wx, wy, client=None):
    if _blit_tex(surf, "floor", rect, wx, wy):
        _floor_fx(surf, rect, wx, wy, client)
        return
    f = 0.85 + 0.25 * _h(wx, wy)
    surf.fill(_shade(STONE, f), rect)
    # flagstones: 2x2 per tile, offset rows
    half = rect.w // 2
    off = half // 2 if wy % 2 else 0
    for i in range(3):
        x = rect.x + i * half - off
        pygame.draw.line(surf, MORTAR, (x, rect.y), (x, rect.bottom - 1))
    pygame.draw.line(surf, MORTAR, (rect.x, rect.y + half), (rect.right - 1, rect.y + half))
    pygame.draw.line(surf, MORTAR, (rect.x, rect.y), (rect.right - 1, rect.y))
    for k in range(3):
        if _h(wx, wy, k + 5) > 0.62:
            px = rect.x + int(_h(wx, wy, k + 9) * rect.w)
            py = rect.y + int(_h(wx, wy, k + 13) * rect.h)
            pygame.draw.circle(surf, _shade(MOSS, 0.8 + 0.4 * _h(wx, wy, k)), (px, py), max(2, rect.w // 9))
    if _h(wx, wy, 21) > 0.8:  # damp puddle
        pr = pygame.Rect(0, 0, rect.w // 2, rect.h // 4)
        pr.center = (rect.x + int(rect.w * (0.3 + 0.4 * _h(wx, wy, 22))), rect.y + int(rect.h * 0.6))
        pygame.draw.ellipse(surf, (48, 58, 48), pr)


def _wall(surf, rect, wx, wy, client):
    if _blit_tex(surf, "wall", rect, wx, wy):
        below = client.tiles[wy + 1][wx] if wy + 1 < len(client.tiles) else wm.WALL
        below2 = client.tiles[wy + 2][wx] if wy + 2 < len(client.tiles) else wm.WALL
        if below == wm.WALL and below2 != wm.WALL and below2 != wm.WATER and _wallface(surf, rect, wx, wy + 1, 0):
            shade = pygame.Surface(rect.size); shade.fill((0, 0, 0)); shade.set_alpha(70)
            surf.blit(shade, rect.topleft)
            surf.blit(_fx("shadow", rect.w, _paint_shadow), rect.topleft)
            return
        if below == wm.WALL:      # deep wall mass: darker so rooms read as carved out
            shade = pygame.Surface(rect.size); shade.fill((0, 0, 0)); shade.set_alpha(165)
            surf.blit(shade, rect.topleft)
        elif _wallface(surf, rect, wx, wy, 1):   # painted face, bottom half
            surf.blit(_fx("shadow", rect.w, _paint_shadow), rect.topleft)
            pygame.draw.line(surf, (130, 118, 96), (rect.x, rect.bottom - 2), (rect.right - 1, rect.bottom - 2), 2)
        return
    surf.fill(WALL_D, rect)
    bh = max(4, rect.h // 4)
    for row in range(4):
        y = rect.y + row * bh
        off = (bh if (row + wy) % 2 else 0)
        x = rect.x - off
        while x < rect.right:
            w = bh * 2
            br = pygame.Rect(x + 1, y + 1, w - 2, bh - 2).clip(rect)
            if br.w > 0:
                f = 0.8 + 0.35 * _h(wx * 7 + x, wy * 5 + row)
                surf.fill(_shade(WALL, f), br)
            x += w
    # moss creeping down from the top on walls that face a floor
    below = client.tiles[wy + 1][wx] if wy + 1 < len(client.tiles) else wm.WALL
    if below != wm.WALL:
        for k in range(4):
            mx = rect.x + int(_h(wx, wy, 30 + k) * rect.w)
            ln = int(rect.h * (0.3 + 0.5 * _h(wx, wy, 40 + k)))
            pygame.draw.line(surf, MOSS, (mx, rect.bottom - ln), (mx, rect.bottom - 1), max(2, rect.w // 14))
        pygame.draw.rect(surf, (24, 22, 19), (rect.x, rect.bottom - 3, rect.w, 3))


def _water(surf, rect, wx, wy, t):
    if _blit_tex(surf, "water", rect, wx, wy + int(t * 1.2)):
        y = rect.y + int(rect.h * 0.5 + rect.h * 0.3 * math.sin(t * 1.6 + wy * 0.9))
        pygame.draw.line(surf, (96, 116, 80), (rect.x + rect.w // 5, y), (rect.x + rect.w // 2, y), 1)
        pygame.draw.line(surf, (24, 22, 18), (rect.x, rect.y), (rect.x, rect.bottom), 2)
        return
    surf.fill(WATER, rect)
    for k in range(3):
        ph = t * 1.6 + wy * 0.9 + k * 2.1
        y = rect.y + int(rect.h * (0.2 + 0.3 * k)) + int(2 * math.sin(ph))
        x0 = rect.x + int(rect.w * 0.15 * _h(wx, wy, k))
        pygame.draw.line(surf, WATER_L, (x0, y), (x0 + rect.w // 2, y), 1)
    if _h(wx, wy, 50) > 0.7:
        pygame.draw.circle(surf, (96, 110, 70), (rect.x + rect.w // 3, rect.y + rect.h // 2), max(2, rect.w // 12))
    pygame.draw.line(surf, STONE_D, (rect.x, rect.y), (rect.x, rect.bottom), 2)


def _bridge(surf, rect, wx, wy):
    _water(surf, rect, wx, wy, 0)
    for i in range(4):
        pr = pygame.Rect(rect.x, rect.y + i * rect.h // 4 + 1, rect.w, rect.h // 4 - 2)
        surf.fill(_shade(WOOD, 0.85 + 0.25 * _h(wx, wy, i)), pr)
        pygame.draw.rect(surf, WOOD_D, pr, 1)


def _web_gate(surf, rect, wx, wy):
    _floor(surf, rect, wx, wy)
    cx, cy = rect.center
    for a in range(8):
        ang = a * math.pi / 4 + 0.2
        pygame.draw.line(surf, WEB, (cx, cy), (cx + int(math.cos(ang) * rect.w), cy + int(math.sin(ang) * rect.h)), 1)
    for r in (rect.w // 5, rect.w // 3, rect.w // 2):
        pygame.draw.circle(surf, WEB, (cx, cy), r, 1)


def draw_tile(client, rect, tile_id, wx, wy, t):
    """Return True when the tile was drawn as sewer."""
    if not active(client):
        return False
    surf = client.screen
    st = _st(client)
    if _xy_in(st.get("gate"), wx, wy) and not st.get("gate_open"):
        _web_gate(surf, rect, wx, wy)
        return True
    if tile_id == wm.WATER:
        _water(surf, rect, wx, wy, t)
        return True
    if tile_id == wm.WALL:
        nest = st.get("nest") or []
        if _xy_in(nest, wx, wy):
            _floor(surf, rect, wx, wy, client)
            return True
        _wall(surf, rect, wx, wy, client)
        return True
    cx_ = st.get("channel_x") or []
    if wx in cx_ and wy in (st.get("bridge_y") or []):
        _bridge(surf, rect, wx, wy)
        return True
    _floor(surf, rect, wx, wy, client)
    return True


# ---------------------------------------------------------------- props
def _torch(surf, cx, cy, tw, t):
    fl = 1 + 0.08 * math.sin(t * 11 + cx) + 0.05 * math.sin(t * 23 + cy)
    g = _glow(tw * 3.2 * fl)
    surf.blit(g, g.get_rect(center=(cx, cy - tw // 3)), special_flags=pygame.BLEND_RGB_ADD)
    if _blit_sprite(surf, "torch", tw * 0.42, (cx, cy + tw // 6)):
        return
    pygame.draw.rect(surf, IRON, (cx - 2, cy - tw // 3, 4, tw // 2))
    pygame.draw.rect(surf, WOOD_D, (cx - 4, cy - tw // 3 - 4, 8, 6))
    fl = 1 + 0.15 * math.sin(t * 11 + cx)
    glow = pygame.Surface((tw * 2, tw * 2), pygame.SRCALPHA)
    pygame.draw.circle(glow, (255, 170, 70, 46), (tw, tw), int(tw * 0.9 * fl))
    surf.blit(glow, (cx - tw, cy - tw // 3 - 6 - tw))
    pygame.draw.ellipse(surf, FIRE, (cx - 4, cy - tw // 3 - 16 * fl, 8, 14 * fl))
    pygame.draw.ellipse(surf, (255, 240, 180), (cx - 2, cy - tw // 3 - 10, 4, 7))


def _crate(surf, cx, cy, tw, open_=True):
    if _blit_sprite(surf, "crate", tw * 0.95, (cx, cy + tw // 2 - 2)):
        return
    r = pygame.Rect(0, 0, int(tw * 0.7), int(tw * 0.55))
    r.midbottom = (cx, cy + tw // 4)
    surf.fill(WOOD, r)
    pygame.draw.rect(surf, WOOD_D, r, 2)
    pygame.draw.line(surf, WOOD_D, r.topleft, r.bottomright, 2)
    pygame.draw.line(surf, WOOD_D, r.topright, r.bottomleft, 2)
    if open_:
        for i in range(3):  # shrimp peeking out
            pygame.draw.ellipse(surf, (236, 128, 88), (r.x + 4 + i * r.w // 4, r.y - 4, r.w // 4, 7))


def _chest(surf, cx, cy, tw, opened, gold=False):
    name = "chest_open" if opened else ("chest_gold" if gold else "chest")
    if _blit_sprite(surf, name, tw * (1.0 if not opened else 1.05), (cx, cy + tw // 2 - 2)):
        return
    r = pygame.Rect(0, 0, int(tw * 0.72), int(tw * 0.5))
    r.midbottom = (cx, cy + tw // 4)
    body = (122, 82, 44) if not gold else (128, 92, 40)
    surf.fill(body, r)
    pygame.draw.rect(surf, (60, 40, 20), r, 2)
    band = (186, 150, 70) if gold else (90, 86, 80)
    pygame.draw.line(surf, band, (r.x + r.w // 4, r.y), (r.x + r.w // 4, r.bottom), 3)
    pygame.draw.line(surf, band, (r.right - r.w // 4, r.y), (r.right - r.w // 4, r.bottom), 3)
    if opened:
        lid = pygame.Rect(r.x, r.y - r.h // 2, r.w, r.h // 2)
        surf.fill(_shade(body, 0.7), lid)
        pygame.draw.rect(surf, (60, 40, 20), lid, 2)
        pygame.draw.ellipse(surf, (240, 200, 80), (r.x + 6, r.y - 3, r.w - 12, 8))
    else:
        lid = pygame.Rect(r.x, r.y - r.h // 3, r.w, r.h // 3 + 2)
        pygame.draw.ellipse(surf, _shade(body, 1.1), lid)
        pygame.draw.ellipse(surf, (60, 40, 20), lid, 2)
        pygame.draw.rect(surf, (210, 180, 90), (cx - 3, r.y - 2, 6, 7))


def _ladder(surf, cx, cy, tw):
    """Climbable exit prop — wide enough to read, stretched tall up the wall."""
    # Independent W/H so we can make it much taller without a fat silhouette.
    w = max(8, int(tw * 1.25))
    h = max(12, int(tw * 2.85))
    key = ("spr", "ladder", w, h)
    sp = _SCALED.get(key)
    if sp is None:
        raw = _raw("ladder")
        if raw is not None:
            sp = pygame.transform.smoothscale(raw, (w, h))
            _SCALED[key] = sp
    if sp is not None:
        r = sp.get_rect(midbottom=(int(cx), int(cy + tw // 2)))
        surf.blit(sp, r)
        return
    half = tw // 3
    top = cy - int(tw * 2.4)
    bot = cy + tw // 2
    for dx in (-half, half):
        pygame.draw.line(surf, WOOD_D, (cx + dx, top), (cx + dx, bot), 5)
    steps = 9
    for i in range(steps):
        y = top + 6 + i * (bot - top - 12) // (steps - 1)
        pygame.draw.line(surf, WOOD, (cx - half, y), (cx + half, y), 4)
    pygame.draw.circle(surf, (180, 200, 120), (cx, top - 2), 4)


def _bones(surf, cx, cy, tw, k):
    if _blit_sprite(surf, "bones", tw * (0.7 + 0.15 * (k % 2)), (cx, cy + tw // 2 - 4)):
        return
    pygame.draw.circle(surf, (210, 204, 186), (cx - 6, cy + 4), max(3, tw // 9))
    pygame.draw.circle(surf, (30, 26, 22), (cx - 8, cy + 3), 1)
    pygame.draw.line(surf, (200, 194, 176), (cx - 2, cy + 8), (cx + tw // 3, cy + 2 + k % 4), 3)
    pygame.draw.line(surf, (200, 194, 176), (cx, cy + 2), (cx + tw // 4, cy + 10), 2)


def _nest(surf, cx, cy, tw, hits, gone, t):
    """2x2 web nest with eggs; cx,cy is the centre of the 2x2 block."""
    shake = int(3 * math.sin(t * 30)) if hits and not gone else 0
    if _blit_sprite(surf, "nest_gone" if gone else "nest", tw * 2.4, (cx + shake, cy + tw)):
        if hits and not gone:
            for i in range(hits):   # scorch marks per hit
                pygame.draw.line(surf, (70, 30, 12), (cx - tw // 2 + i * tw // 2, cy - tw // 3), (cx - tw // 3 + i * tw // 2, cy + tw // 2), 4)
            g = _glow(tw * 1.2)
            surf.blit(g, g.get_rect(center=(cx, cy)), special_flags=pygame.BLEND_RGB_ADD)
        return
    if gone:
        pygame.draw.ellipse(surf, (40, 36, 30), (cx - tw, cy - tw // 3, tw * 2, tw))
        for i in range(6):
            a = i * 1.05
            pygame.draw.line(surf, (120, 118, 110), (cx, cy), (cx + int(math.cos(a) * tw * .9), cy + int(math.sin(a) * tw * .4)), 1)
        return
    body = pygame.Rect(0, 0, int(tw * 2.0), int(tw * 1.5))
    body.midbottom = (cx, cy + tw // 2)
    pygame.draw.ellipse(surf, (150, 150, 144), body)
    shake = int(2 * math.sin(t * 30)) if hits else 0
    for i in range(9):
        ex = body.x + 10 + int(_h(i, 3) * (body.w - 20)) + shake
        ey = body.y + 10 + int(_h(i, 7) * (body.h - 20))
        er = max(4, tw // 6)
        pygame.draw.circle(surf, (226, 222, 204), (ex, ey), er)
        pygame.draw.circle(surf, (170, 166, 150), (ex, ey), er, 1)
    for a in range(10):
        ang = a * math.pi / 5
        pygame.draw.line(surf, WEB, body.center, (body.centerx + int(math.cos(ang) * tw * 1.3), body.centery + int(math.sin(ang) * tw)), 1)
    for r in (tw // 2, tw):
        pygame.draw.ellipse(surf, WEB, body.inflate(r - tw, r - tw), 1)
    if hits:
        for i in range(hits):
            pygame.draw.line(surf, (60, 20, 10), (body.x + 12 + i * 14, body.y + 6), (body.x + 20 + i * 14, body.bottom - 8), 3)


def _paint_web(s, n):
    """Corner web anchored top-left, heavy and layered."""
    for a in range(9):
        ang = a * (math.pi / 2) / 8
        pygame.draw.line(s, (210, 210, 200, 150), (0, 0), (int(math.cos(ang) * n), int(math.sin(ang) * n)), 1)
    for k in range(1, 9):
        r = n * k / 9
        pts = [(int(math.cos(a * (math.pi / 2) / 8) * r * (0.92 + 0.08 * (a % 2))),
                int(math.sin(a * (math.pi / 2) / 8) * r * (0.92 + 0.08 * (a % 2)))) for a in range(9)]
        pygame.draw.lines(s, (220, 220, 210, 110 + 8 * (9 - k)), False, pts, 1)
    pygame.draw.circle(s, (230, 230, 220, 70), (0, 0), int(n * 0.35))


def _web(surf, x, y, n, flip_x=False, flip_y=False):
    w = _fx("web", n, _paint_web)
    if flip_x or flip_y:
        w = pygame.transform.flip(w, flip_x, flip_y)
    surf.blit(w, (x - (n if flip_x else 0), y - (n if flip_y else 0)))


def _paint_hole(s, n):
    s.fill((255, 255, 255, 255))
    r = n // 2
    for i in range(r, 0, -2):
        a = int(255 * min(1.0, (i / r) ** 2.2 * 1.15))
        pygame.draw.circle(s, (255, 255, 255, a), (r, r), i)


def _darkness(client, surf, lights, base=196):
    w, h = surf.get_size()
    mask = getattr(client, "_sewer_dark", None)
    if mask is None or mask.get_size() != (w, h):
        mask = pygame.Surface((w, h), pygame.SRCALPHA)
        client._sewer_dark = mask
    mask.fill((6, 5, 4, base))
    for cx, cy, r in lights:
        r = max(16, int(r)) // 2 * 2
        mask.blit(_fx("hole", r * 2, _paint_hole), (cx - r, cy - r), special_flags=pygame.BLEND_RGBA_MULT)
    surf.blit(mask, (0, 0))


def queue_props(client, draw_list, cam_x, cam_y, tw, t):
    st = _st(client)
    if not st:
        return
    surf = client.screen

    def _vis(x, y):
        sx, sy = client.world_to_view_offset(x, y, cam_x, cam_y)
        return sx * tw + tw // 2, sy * tw + tw // 2

    def add(x, y, fn, label=None, color=(235, 220, 180)):
        cx, cy = _vis(x, y)
        if cx < -tw * 2 or cy < -tw * 2 or cx > surf.get_width() + tw * 2 or cy > surf.get_height() + tw * 2:
            return

        def _d(cx=cx, cy=cy):
            fn(cx, cy)
            if label:
                mx, my = pygame.mouse.get_pos()
                if abs(mx - cx) < tw // 2 and abs(my - cy) < tw // 2:
                    client.blit_nameplate(label, cx, cy - tw // 2 - 6, color)
        draw_list.append((cy + tw // 3, 1, _d))

    cxs = st.get("channel_x") or []
    if cxs:
        px = (min(cxs) + max(cxs)) / 2.0
        sx, sy = client.world_to_view_offset(px, 1, cam_x, cam_y)
        pcx, pcy = int(sx * tw + tw // 2), int(sy * tw + tw // 2)
        draw_list.append((pcy - tw, 0, lambda pcx=pcx, pcy=pcy: _blit_sprite(surf, "pipe", tw * 1.3, (pcx, pcy + tw // 2 + 6))))
    for x, y in st.get("torches") or []:
        add(x, y, lambda cx, cy: _torch(surf, cx, cy, tw, t))
    for i, (x, y) in enumerate(st.get("bones") or []):
        add(x, y, lambda cx, cy, i=i: _bones(surf, cx, cy, tw, i))
    for x, y in st.get("crates") or []:
        add(x, y, lambda cx, cy: _crate(surf, cx, cy, tw), "Shrimp crate")
    if st.get("chest1"):
        x, y = st["chest1"]
        add(x, y, lambda cx, cy: _chest(surf, cx, cy, tw, st.get("chest1_open")), "Chest")
    if st.get("reward_chest"):
        x, y = st["reward_chest"]
        add(x, y, lambda cx, cy: _chest(surf, cx, cy, tw, st.get("reward_open"), gold=True),
            "Seraphine's chest", (255, 220, 120))
    for key, label in (("ladder", "Ladder up"), ("ladder2", "Ladder up (exit)")):
        if st.get(key):
            x, y = st[key]
            # Tall sprite: use a bigger hover pad so the nameplate still pops.
            cx, cy = _vis(x, y)
            if not (cx < -tw * 2 or cy < -tw * 2 or cx > surf.get_width() + tw * 2 or cy > surf.get_height() + tw * 2):
                def _dl(cx=cx, cy=cy, label=label):
                    _ladder(surf, cx, cy, tw)
                    mx, my = pygame.mouse.get_pos()
                    if abs(mx - cx) < tw * 1.2 and abs(my - (cy - tw)) < tw * 1.8:
                        client.blit_nameplate(label, cx, cy - int(tw * 1.4), (235, 220, 180))
                draw_list.append((cy + tw // 3, 1, _dl))
    nest = st.get("nest") or []
    if nest:
        xs = [n[0] for n in nest]
        ys = [n[1] for n in nest]
        ax, ay = _vis(min(xs), min(ys))
        cx, cy = ax + tw // 2 * (max(xs) - min(xs)), ay + tw // 2 * (max(ys) - min(ys))
        hits = int(st.get("nest_hits") or 0)
        gone = bool(st.get("nest_gone"))

        def _dn(cx=cx, cy=cy):
            _nest(surf, cx, cy, tw, hits, gone, t)
            if not gone:
                mx, my = pygame.mouse.get_pos()
                if abs(mx - cx) < tw and abs(my - cy) < tw:
                    client.blit_nameplate(f"Spider nest ({3 - hits} hits)", cx, cy - tw - 6, (255, 150, 120))
        draw_list.append((cy + tw // 2, 1, _dn))

    # heavy cobwebs: room corners and around the nest
    tiles = getattr(client, "tiles", None) or []
    webs = []
    if tiles:
        x0, y0 = int(cam_x) - 2, int(cam_y) - 2
        vw, vh = surf.get_width() // tw + 5, surf.get_height() // tw + 5
        for yy in range(max(1, y0), min(len(tiles) - 1, y0 + vh)):
            row = tiles[yy]
            for xx in range(max(1, x0), min(len(row) - 1, x0 + vw)):
                if row[xx] == wm.WALL or row[xx] == wm.WATER:
                    continue
                up, dn = tiles[yy - 1][xx] == wm.WALL, tiles[yy + 1][xx] == wm.WALL
                lf, rt = row[xx - 1] == wm.WALL, row[xx + 1] == wm.WALL
                if (up or dn) and (lf or rt) and _h(xx, yy, 70) > 0.15:
                    webs.append((xx, yy, rt, dn))
    if nest and not st.get("nest_gone"):
        for i, (ox, oy, fx_, fy_) in enumerate(((-1, -1, False, False), (2, -1, True, False), (-1, 2, False, True), (2, 2, True, True))):
            webs.append((min(xs) + ox, min(ys) + oy, fx_, fy_))

    def _dw():
        if nest and not st.get("nest_gone"):
            nx, ny = _vis((min(xs) + max(xs)) / 2.0, (min(ys) + max(ys)) / 2.0)
            for k, (ox, oy, sc) in enumerate(((0, 0, 5.6), (-1.6, -1.4, 3.2), (1.8, -1.2, 3.0), (-1.4, 1.5, 2.8))):
                ws = _sprite("websheet", tw * sc)
                if ws is not None:
                    surf.blit(ws, ws.get_rect(center=(int(nx + ox * tw), int(ny + oy * tw))))
        for xx, yy, fx_, fy_ in webs:
            sx, sy = client.world_to_view_offset(xx, yy, cam_x, cam_y)
            px = int(sx * tw) + (tw if fx_ else 0)
            py = int(sy * tw) + (tw if fy_ else 0)
            _web(surf, px, py, int(tw * 1.6), fx_, fy_)
    draw_list.append((-10 ** 6, 0, _dw))

    # pools of darkness: lit only around torches, the player and the nest
    def _dd():
        lights = []
        for x, y in st.get("torches") or []:
            cx, cy = _vis(x, y)
            fl = 1 + 0.06 * math.sin(t * 9 + x)
            lights.append((cx, cy, tw * 6.0 * fl))
        p = getattr(client, "player", None) or {}
        if "x" in p:
            px, py = _vis(p.get("x", 0), p.get("y", 0))
            lights.append((px, py, tw * 5.0))
        if nest:
            lights.append((cx, cy, tw * 3.0))
        for m in (getattr(client, "monsters", None) or {}).values():   # keep foes readable
            if "x" in m and (m.get("hp", 1) or 0) > 0:
                mx, my = _vis(m["x"], m["y"])
                lights.append((mx, my, tw * 1.9))
        _darkness(client, surf, lights)
    draw_list.append((10 ** 9, 9, _dd))


def handle_click(client, tx, ty):
    st = _st(client)
    # Props first — the exit ladder uses a wide click pad that would otherwise
    # swallow Seraphine's chest (3 tiles away) and walk you out of the sewer.
    pts = []
    for key in ("chest1", "reward_chest"):
        if st.get(key):
            pts.append(tuple(st[key]))
    pts += [tuple(c) for c in st.get("crates") or []]
    pts += [tuple(n) for n in st.get("nest") or []]
    if (tx, ty) in pts:
        goals = client.adjacent_goals(tx, ty)
        if client.tile_walkable(tx, ty):
            goals = set(goals) | {(tx, ty)}
        client.walk_and_act(goals, {"type": "DUNGEON_INTERACT", "x": tx, "y": ty})
        return True
    # Room-2 exit ladder: generous click pad, then walk onto the tile (on_step leaves).
    ladder2 = st.get("ladder2")
    if ladder2:
        lx, ly = int(ladder2[0]), int(ladder2[1])
        if max(abs(tx - lx), abs(ty - ly)) <= 3:
            goals = {(lx, ly)} if client.tile_walkable(lx, ly) else client.adjacent_goals(lx, ly)
            client.walk_and_act(goals, None)
            return True
    return False


# ---------------------------------------------------------------- overworld grate
def draw_grate(client, cx, cy, tw, t):
    surf = client.screen
    # stone arch set into the ground, iron grate across the mouth
    arch = pygame.Rect(0, 0, int(tw * 1.5), int(tw * 1.3))
    arch.midbottom = (cx, cy + tw // 2)
    pygame.draw.ellipse(surf, (88, 82, 72), arch.inflate(10, 10))
    for i in range(9):
        a = math.pi + i * math.pi / 8
        bx = arch.centerx + int(math.cos(a) * (arch.w // 2 + 2))
        by = arch.centery + int(math.sin(a) * (arch.h // 2 + 2))
        pygame.draw.circle(surf, _shade((110, 102, 88), 0.85 + 0.2 * _h(i, 1)), (bx, by), max(4, tw // 7))
    mouth = arch.inflate(-tw // 4, -tw // 5)
    pygame.draw.ellipse(surf, (14, 12, 10), mouth)
    painted = _blit_sprite(surf, "grate", mouth.w, mouth.midbottom) is not None
    for i in (range(1, 6) if not painted else ()):
        x = mouth.x + i * mouth.w // 6
        pygame.draw.line(surf, (70, 66, 60), (x, mouth.y + 4), (x, mouth.bottom - 3), 3)
    for j in (range(1, 3) if not painted else ()):
        y = mouth.y + j * mouth.h // 3
        pygame.draw.line(surf, (70, 66, 60), (mouth.x + 4, y), (mouth.right - 4, y), 3)
    # ivy and a trickle of water
    for k in range(5):
        vx = arch.x + int(_h(k, 2) * arch.w)
        pygame.draw.line(surf, MOSS, (vx, arch.y), (vx + 3, arch.y + tw // 3), 3)
    wy = mouth.bottom + int(2 * math.sin(t * 4))
    pygame.draw.ellipse(surf, (70, 96, 90), (cx - tw // 4, wy - 2, tw // 2, 6))
    _torch(surf, arch.right + 4, arch.y + tw // 2, tw, t)
    return arch.y


# ---------------------------------------------------------------- messages
def on_message(client, t, msg):
    """Handle SEWER_* messages. Return True if consumed."""
    if not t.startswith("SEWER_"):
        return False
    now = time.time()
    if t == "SEWER_STATE":
        if client.dungeon is not None and active(client):
            client.dungeon["sewer"] = dict(msg)
    elif t == "SEWER_SAY":
        client._sewer_bubble = (msg.get("text") or "", now + 6.0)
    elif t == "SEWER_EAT_PROMPT":
        client._sewer_eat = (msg.get("text") or "Eat now!", now + max(2.5, float(msg.get("seconds") or 1) + 2.0))
    elif t == "SEWER_RESCUE":
        client._sewer_rescue = now + 1.6
        if getattr(client, "dungeon", None):
            client._sewer_eat = None
    elif t == "SEWER_LOOT":
        client._sewer_loot = (msg, now + 5.0)
    elif t == "SEWER_REWARD":
        client._sewer_reward = (msg, now + 12.0)
    elif t == "SEWER_TRACK":
        try:
            client.tracked_quest_id = "below_the_village"
        except Exception:
            pass
        client.quest_guide = (int(msg.get("x", 0)), int(msg.get("y", 0)), "Sewer grate")
        client._welcome_path = None
    return True


def _panel(surf, rect, border=(170, 140, 80)):
    s = pygame.Surface(rect.size, pygame.SRCALPHA)
    s.fill((22, 18, 14, 225))
    surf.blit(s, rect.topleft)
    pygame.draw.rect(surf, border, rect, 2)


def _font(size, bold=False):
    return pygame.font.SysFont("georgia", size, bold=bold)


def draw_overlay(client, map_w, map_h):
    surf = client.screen
    now = time.time()
    bub = getattr(client, "_sewer_bubble", None)
    if bub and now < bub[1]:
        f = _font(16)
        words, lines, cur = bub[0].split(), [], ""
        for w in words:
            if f.size(cur + " " + w)[0] > 460 and cur:
                lines.append(cur)
                cur = w
            else:
                cur = (cur + " " + w).strip()
        lines.append(cur)
        h = 34 + 20 * len(lines)
        r = pygame.Rect(0, 0, 500, h)
        r.midbottom = (map_w // 2, map_h - 14)   # above the chat, clear of tour toasts
        _panel(surf, r)
        surf.blit(_font(14, True).render("Seraphine", True, (255, 214, 140)), (r.x + 14, r.y + 8))
        for i, ln in enumerate(lines):
            surf.blit(f.render(ln, True, (240, 232, 214)), (r.x + 14, r.y + 28 + 20 * i))
    eat = getattr(client, "_sewer_eat", None)
    if eat and now < eat[1]:
        pulse = 0.5 + 0.5 * math.sin(now * 8)
        r = pygame.Rect(0, 0, 380, 64)
        r.center = (map_w // 2, map_h // 2 - 90)
        _panel(surf, r, (int(200 + 55 * pulse), 70, 50))
        surf.blit(_font(22, True).render("EAT NOW!", True, (255, 120, 90)), (r.x + 16, r.y + 6))
        surf.blit(_font(14).render("Press R or click a cooked shrimp", True, (240, 226, 200)), (r.x + 16, r.y + 38))
    resc = getattr(client, "_sewer_rescue", 0)
    if resc and now < resc:
        a = int(220 * (resc - now) / 1.6)
        fade = pygame.Surface((map_w, map_h), pygame.SRCALPHA)
        fade.fill((10, 8, 6, a))
        surf.blit(fade, (0, 0))
        txt = _font(22, True).render("Seraphine pulls you out. Nothing lost.", True, (255, 230, 190))
        surf.blit(txt, txt.get_rect(center=(map_w // 2, map_h // 2)))
    loot = getattr(client, "_sewer_loot", None)
    if loot and now < loot[1]:
        r = pygame.Rect(0, 0, 300, 58)
        r.topright = (map_w - 14, 120)
        _panel(surf, r)
        coins = sum(int(n) for i, n in loot[0].get("items") or [] if i == "coins")
        surf.blit(_font(15, True).render(f"+{coins} coins", True, (255, 220, 110)), (r.x + 12, r.y + 8))
        surf.blit(_font(13).render("A rat-tail charm glints at the far end...", True, (220, 210, 190)), (r.x + 12, r.y + 32))
    rew = getattr(client, "_sewer_reward", None)
    if rew and now < rew[1]:
        m = rew[0]
        r = pygame.Rect(0, 0, 420, 214)
        r.center = (map_w // 2, map_h // 2 - 40)
        _panel(surf, r, (230, 190, 90))
        surf.blit(_font(22, True).render("Below the Village — complete!", True, (255, 220, 120)), (r.x + 18, r.y + 12))
        surf.blit(_font(16, True).render(f"Title unlocked: {m.get('title', 'Ratcatcher')}", True, (240, 236, 220)), (r.x + 18, r.y + 48))
        y = r.y + 78
        icon = None
        try:
            import realistic_item_icons
            realistic_item_icons.draw_icon(surf, pygame.Rect(r.right - 92, r.y + 72, 72, 72), "ratcatcher_charm")
        except Exception:
            pass
        names = {"ratcatcher_charm": "Rat-Tail Charm", "cooked_shrimp": "Cooked shrimp", "coins": "Coins"}
        for item, n in m.get("items") or []:
            surf.blit(_font(15).render(f"• {names.get(item, item)} ×{n}", True, (230, 222, 200)), (r.x + 26, y))
            y += 22
        mins = int(m.get("boost_seconds") or 900) // 60
        surf.blit(_font(15).render(f"• +10% combat XP for {mins} minutes", True, (170, 230, 150)), (r.x + 26, y))


def start_from_log(client):
    """Journal click on Below the Village: start it and walk to the grate."""
    try:
        client.net.send("SEWER_START")
    except Exception:
        pass
    gx, gy = 25, 30
    for spot in getattr(client, "interactables", []) or []:
        if spot.get("kind") == "sewer_grate":
            gx, gy = spot["x"], spot["y"]
    if not getattr(client, "dungeon", None):
        client.walk_and_act({(gx, gy)}, {"type": "ENTER_DUNGEON", "dungeon_id": SEWER_ID})
