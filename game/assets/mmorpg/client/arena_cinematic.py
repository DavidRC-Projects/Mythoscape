"""Arena finishing-move cinematics (in-engine, pygame only).

Built from a few painted key shots per boss (assets/castle_realm/arena/cinematic/<boss>/)
in the throne-vision film's look: low camera behind the barrier, golden backlight, dust.
The engine adds letterbox bars, slow push-ins / punch-ins, camera shake, flash cuts,
slow-motion, sparks / dust / petals, the announcer line, crowd roar and impacts.

render(surface, script, t_ms) is pure (deterministic) so tools/render_cinematic.py
exports the exact frames players see.
"""
from __future__ import annotations

import math
import os
import random

import pygame

_HERE = os.path.dirname(os.path.abspath(__file__))
CIN_DIR = os.path.join(_HERE, "assets", "castle_realm", "arena", "cinematic")
FONT_DIR = os.path.join(_HERE, "..", "assets", "fonts")

# Shot keys: img (plate when layers are given), t0/t1 ms, camera a->b = (zoom, cx, cy) in source
# fractions, ease, and fx. "layers" are subject cut-outs (tools/cinematic_layers.py) that move on
# their own over the plate: (file, (dx, dy, scale, rot) at start, ... at end, ease) with dx/dy in
# screen fractions -- the hero lunges, the champion is knocked back or sinks to a knee.
SCRIPTS = {
    ("unbroken", "blade"): {
        "length": 8800,
        "shots": [
            {"img": "v2/s01_standoff_plate.jpg", "t0": 0, "t1": 1600, "a": (1.06, 0.50, 0.52),
             "b": (1.16, 0.52, 0.50), "ease": "out", "dust": True,
             "layers": [("v2/s01_standoff_fgL.png", (-0.012, 0, 1.0, 0), (0.006, 0, 1.015, 0), "inout"),
                        ("v2/s01_standoff_fgR.png", (0.012, 0, 1.0, 0), (-0.008, 0, 1.02, 0), "inout")]},
            {"img": "v2/s02_clash.jpg", "t0": 1600, "t1": 3200, "a": (1.18, 0.48, 0.42), "b": (1.36, 0.48, 0.38),
             "ease": "slowmo", "flash_in": 140, "shake": (1600, 420, 10), "sparks": (0.477, 0.35)},
            {"img": "v2/s03_strike_plate.jpg", "t0": 3200, "t1": 4800, "a": (1.0, 0.50, 0.50),
             "b": (1.08, 0.50, 0.50), "ease": "slowmo", "flash_in": 120, "shake": (3200, 380, 12),
             "burst": (0.62, 0.84), "sparks": (0.66, 0.42),
             "layers": [("v2/s03_strike_fgL.png", (-0.05, 0.01, 0.98, 0), (0.012, 0, 1.03, 0), "out"),
                        ("v2/s03_strike_fgR.png", (-0.015, 0, 1.0, 2), (0.02, 0.005, 1.0, -4), "out")]},
            {"img": "v2/s04_kneel_plate.jpg", "t0": 4800, "t1": 6600, "a": (1.02, 0.50, 0.46),
             "b": (1.14, 0.46, 0.44), "ease": "inout", "dust": True,
             "layers": [("v2/s04_kneel_fgL.png", (0, 0.02, 0.99, 0), (0, 0, 1.03, 0), "out"),
                        ("v2/s04_kneel_fgR.png", (0.01, -0.05, 1.02, 3), (0, 0, 1.0, 0), "out")]},
            {"img": "v2/s05_victory_plate.jpg", "t0": 6600, "t1": 8800, "a": (1.12, 0.42, 0.40),
             "b": (1.0, 0.50, 0.45), "ease": "out", "flash_in": 220, "shake": (6600, 300, 6), "petals": True,
             "layers": [("v2/s05_victory_fgL.png", (0, 0.015, 0.97, 0), (0, 0, 1.04, 0), "out"),
                        ("v2/s05_victory_fgR.png", (0, 0, 1.0, 0), (0, 0, 1.0, 0), "out")]},
        ],
        "captions": [(4900, 6500, "FINISHING MOVE", "Sunbreaker"),
                     (6900, 8800, None, "\u201cThe Unbroken is broken! Hail the new Grand Champion!\u201d")],
        "sfx": [(0, "whoosh"), (1600, "impact"), (3150, "whoosh"), (3200, "impact"), (6600, "impact"),
                (6650, "crowd_roar")],
    },
    ("unbroken", "arrow"): {
        "length": 8600,
        "shots": [
            {"img": "v2/r01_standoff_plate.jpg", "t0": 0, "t1": 1500, "a": (1.0, 0.50, 0.50),
             "b": (1.04, 0.50, 0.52), "ease": "out", "dust": True,
             "layers": [("v2/r01_standoff_fgL.png", (0, 0.075, 1.0, 0), (0.004, 0.075, 1.01, 0), "inout"),
                        ("v2/r01_standoff_fgR.png", (0.03, 0, 0.97, 0), (-0.02, 0, 1.03, 0), "inout")]},
            {"img": "v2/r02_draw_plate.jpg", "t0": 1500, "t1": 3400, "a": (1.04, 0.50, 0.48),
             "b": (1.22, 0.56, 0.45), "ease": "slowmo", "flash_in": 100, "glint": (2300, 3400, (0.82, 0.37)),
             "layers": [("v2/r02_draw_fgR.png", (0.02, 0, 0.96, 0), (-0.01, 0, 1.06, 0), "inout"),
                        ("v2/r02_draw_fgL.png", (0.006, 0, 1.0, 0), (-0.008, 0, 1.0, 0), "out")]},
            {"img": "v2/r01_standoff_plate.jpg", "t0": 3400, "t1": 4300, "a": (1.04, 0.50, 0.52),
             "b": (1.10, 0.56, 0.54), "ease": "slowmo", "slowmo_arrow": True,
             "arrow": (3400, 4300, (0.30, 0.45), (0.72, 0.42)),
             "layers": [("v2/r01_standoff_fgL.png", (0, 0.075, 1.0, 0), (0, 0.075, 1.0, 0), "out"),
                        ("v2/r01_standoff_fgR.png", (-0.02, 0, 1.03, 0), (-0.025, 0, 1.035, 0), "out")]},
            {"img": "v2/r03_impact_plate.jpg", "t0": 4300, "t1": 5900, "a": (1.0, 0.50, 0.50),
             "b": (1.05, 0.52, 0.53), "ease": "slowmo", "flash_in": 160, "shake": (4300, 450, 14),
             "sparks": (0.535, 0.42), "burst": (0.54, 0.45),
             "layers": [("v2/r03_impact_fgR.png", (-0.02, 0, 1.03, 3), (0.04, 0.01, 1.0, -6), "out")]},
            {"img": "v2/r04_victory_plate.jpg", "t0": 5900, "t1": 8600, "a": (1.0, 0.50, 0.50),
             "b": (1.04, 0.46, 0.52), "ease": "out", "flash_in": 200, "shake": (5900, 300, 6), "petals": True,
             "layers": [("v2/r04_victory_fgR.png", (0, 0, 1.0, 0), (0, 0, 1.0, 0), "out"),
                        ("v2/r04_victory_fgL.png", (0, 0.075, 0.97, 0), (0, 0.06, 1.0, 0), "out")]},
        ],
        "captions": [(1700, 3300, "FINISHING SHOT", "Sunpiercer"),
                     (6200, 8600, None, "\u201cOne arrow! The Unbroken falls! Hail the new Grand Champion!\u201d")],
        "sfx": [(0, "whoosh"), (3400, "arrow"), (4300, "impact"), (5900, "impact"), (5950, "crowd_roar")],
    },
}


# Other champions: 4-shot blade (standoff, strike, kneel, victory) and 5-beat arrow
# (standoff, shared ranger draw, arrow flight, impact, victory). Axe finishers use "blade".
_BOSS_CIN = {
    "varro": ("Netbreaker", "Piercing Gale", "\u201cThe Net is cut! Varro falls!\u201d", "\u201cOne arrow through the net! Varro falls!\u201d", (0.56, 0.42)),
    "brutus": ("Ironsplitter", "Ironpiercer", "\u201cIronhide yields! The crowd roars!\u201d", "\u201cRight past the scutum! Brutus falls!\u201d", (0.55, 0.42)),
    "crixus": ("Red Ruin", "Crimson Flight", "\u201cThe Red is beaten! What a finish!\u201d", "\u201cOne arrow! Crixus the Red goes down!\u201d", (0.58, 0.34)),
    "sabina": ("Sandstorm", "Desert Wind", "\u201cBoth blades fall silent! Sabina yields!\u201d", "\u201cA perfect shot! Sabina of the Sands falls!\u201d", (0.52, 0.38)),
    "ignatius": ("Lionfall", "Lion's Bane", "\u201cThe Lion kneels! A new champion rises!\u201d", "\u201cThrough the mane! The Lion falls!\u201d", (0.53, 0.34)),
}


def _blade_script(move, quote):
    return {
        "length": 8000,
        "shots": [
            {"img": "v2/s01_standoff_plate.jpg", "t0": 0, "t1": 1800, "a": (1.04, 0.50, 0.52),
             "b": (1.12, 0.52, 0.50), "ease": "out", "dust": True,
             "layers": [("v2/s01_standoff_fgL.png", (-0.012, 0, 1.0, 0), (0.006, 0, 1.015, 0), "inout"),
                        ("v2/s01_standoff_fgR.png", (0.012, 0, 1.0, 0), (-0.008, 0, 1.02, 0), "inout")]},
            {"img": "v2/s03_strike_plate.jpg", "t0": 1800, "t1": 3800, "a": (1.0, 0.50, 0.50),
             "b": (1.08, 0.52, 0.48), "ease": "slowmo", "flash_in": 120, "shake": (1800, 380, 12),
             "burst": (0.62, 0.80), "sparks": (0.62, 0.42),
             "layers": [("v2/s03_strike_fgL.png", (-0.05, 0.01, 0.98, 0), (0.012, 0, 1.03, 0), "out"),
                        ("v2/s03_strike_fgR.png", (-0.015, 0, 1.0, 2), (0.02, 0.005, 1.0, -4), "out")]},
            {"img": "v2/s04_kneel_plate.jpg", "t0": 3800, "t1": 5800, "a": (1.0, 0.50, 0.48),
             "b": (1.08, 0.50, 0.46), "ease": "inout", "dust": True,
             "layers": [("v2/s04_kneel_fgL.png", (0, 0.02, 0.99, 0), (0, 0, 1.03, 0), "out"),
                        ("v2/s04_kneel_fgR.png", (0.01, -0.05, 1.02, 3), (0, 0, 1.0, 0), "out")]},
            {"img": "v2/s05_victory_plate.jpg", "t0": 5800, "t1": 8000, "a": (1.08, 0.44, 0.42),
             "b": (1.0, 0.50, 0.47), "ease": "out", "flash_in": 220, "shake": (5800, 300, 6), "petals": True,
             "layers": [("v2/s05_victory_fgL.png", (0, 0.015, 0.97, 0), (0, 0, 1.03, 0), "out"),
                        ("v2/s05_victory_fgR.png", (0, 0, 1.0, 0), (0, 0, 1.0, 0), "out")]},
        ],
        "captions": [(3900, 5700, "FINISHING MOVE", move), (6100, 8000, None, quote)],
        "sfx": [(0, "whoosh"), (1750, "whoosh"), (1800, "impact"), (5800, "impact"), (5850, "crowd_roar")],
    }


def _arrow_script(move, quote, hit):
    return {
        "length": 8600,
        "shots": [
            {"img": "v2/r01_standoff_plate.jpg", "t0": 0, "t1": 1500, "a": (1.0, 0.50, 0.50),
             "b": (1.04, 0.50, 0.52), "ease": "out", "dust": True,
             "layers": [("v2/r01_standoff_fgL.png", (0, 0.09, 0.97, 0), (0.004, 0.09, 0.98, 0), "inout"),
                        ("v2/r01_standoff_fgR.png", (0.03, 0, 0.97, 0), (-0.02, 0, 1.03, 0), "inout")]},
            {"img": "v2/r02_draw_plate.jpg", "t0": 1500, "t1": 3400, "a": (1.04, 0.50, 0.48),
             "b": (1.18, 0.54, 0.45), "ease": "slowmo", "flash_in": 100,
             "layers": [("v2/r02_draw_fgL.png", (0.006, 0, 1.0, 0), (-0.008, 0, 1.0, 0), "out")]},
            {"img": "v2/r01_standoff_plate.jpg", "t0": 3400, "t1": 4300, "a": (1.04, 0.50, 0.52),
             "b": (1.10, 0.56, 0.54), "ease": "slowmo", "slowmo_arrow": True,
             "arrow": (3400, 4300, (0.30, 0.45), (0.72, 0.42)),
             "layers": [("v2/r01_standoff_fgL.png", (0, 0.09, 0.98, 0), (0, 0.09, 0.98, 0), "out"),
                        ("v2/r01_standoff_fgR.png", (-0.02, 0, 1.03, 0), (-0.025, 0, 1.035, 0), "out")]},
            {"img": "v2/r03_impact_plate.jpg", "t0": 4300, "t1": 5900, "a": (1.0, 0.50, 0.50),
             "b": (1.05, 0.52, 0.53), "ease": "slowmo", "flash_in": 160, "shake": (4300, 450, 14),
             "sparks": hit, "burst": (hit[0] + 0.005, hit[1] + 0.03),
             "layers": [("v2/r03_impact_fgR.png", (-0.02, 0, 1.03, 3), (0.04, 0.01, 1.0, -6), "out")]},
            {"img": "v2/r04_victory_plate.jpg", "t0": 5900, "t1": 8600, "a": (1.0, 0.50, 0.50),
             "b": (1.04, 0.46, 0.52), "ease": "out", "flash_in": 200, "shake": (5900, 300, 6), "petals": True,
             "layers": [("v2/r04_victory_fgR.png", (0, 0, 1.0, 0), (0, 0, 1.0, 0), "out"),
                        ("v2/r04_victory_fgL.png", (0, 0.075, 0.97, 0), (0, 0.06, 1.0, 0), "out")]},
        ],
        "captions": [(1700, 3300, "FINISHING SHOT", move), (6200, 8600, None, quote)],
        "sfx": [(0, "whoosh"), (3400, "arrow"), (4300, "impact"), (5900, "impact"), (5950, "crowd_roar")],
    }


for _b, (_bm, _am, _bq, _aq, _hit) in _BOSS_CIN.items():
    SCRIPTS[(_b, "blade")] = _blade_script(_bm, _bq)
    SCRIPTS[(_b, "arrow")] = _arrow_script(_am, _aq, _hit)

LETTERBOX = 0.115   # bar height as share of screen height
BAR_IN_MS = 450

_img_cache: dict = {}
_font_cache: dict = {}
_sfx_cache: dict = {}


def has(boss_id, kind):
    s = SCRIPTS.get((boss_id, kind))
    if not s:
        return False
    files = [sh["img"] for sh in s["shots"]] + [ly[0] for sh in s["shots"] for ly in sh.get("layers", ())]
    return all(os.path.exists(os.path.join(CIN_DIR, boss_id, f)) for f in files)


def _img(boss, name):
    key = (boss, name)
    if key not in _img_cache:
        im = pygame.image.load(os.path.join(CIN_DIR, boss, name))
        if pygame.display.get_surface():
            im = im.convert_alpha() if name.endswith(".png") else im.convert()
        _img_cache[key] = im
    return _img_cache[key]


def _font(name, size):
    key = (name, size)
    if key not in _font_cache:
        p = os.path.join(FONT_DIR, name)
        _font_cache[key] = pygame.font.Font(p if os.path.exists(p) else None, size)
    return _font_cache[key]


def _ease(kind, u):
    u = max(0.0, min(1.0, u))
    if kind == "out":
        return 1 - (1 - u) ** 3
    if kind == "inout":
        return u * u * (3 - 2 * u)
    if kind == "slowmo":
        # fast punch then a long held drift: reads as slow motion
        return 0.55 * (1 - (1 - min(1, u / 0.18)) ** 3) + 0.45 * max(0, (u - 0.18) / 0.82)
    return u


def _cam_view(dst, src, zoom, cx, cy, shake=(0, 0)):
    """Source rect shown in the letterboxed viewport + mapping helpers."""
    FW, FH = dst.get_size()
    top = int(FH * LETTERBOX)
    W, H = FW, FH - 2 * top
    sw, sh = src.get_size()
    scale = max(W / sw, H / sh) * zoom
    vw, vh = W / scale, H / scale
    x = cx * sw - vw / 2 + shake[0] / scale
    y = cy * sh - vh / 2 + shake[1] / scale
    x = max(0, min(sw - vw, x))
    y = max(0, min(sh - vh, y))
    return x, y, vw, vh, scale, top, W, H


def _cam_blit(dst, src, zoom, cx, cy, shake=(0, 0)):
    """Frame src into the letterboxed viewport (between the bars)."""
    x, y, vw, vh, scale, top, W, H = _cam_view(dst, src, zoom, cx, cy, shake)
    rect = pygame.Rect(int(x), int(y), max(1, int(vw)), max(1, int(vh)))
    dst.blit(pygame.transform.smoothscale(src.subsurface(rect), (W, H)), (0, top))
    sw, sh = src.get_size()
    return lambda fx, fy: ((fx * sw - x) * scale, top + (fy * sh - y) * scale)


def _cam_layer(dst, src, zoom, cx, cy, shake, tr):
    """A cut-out subject layer under the same camera, with its own move (dx, dy, scale, rot)."""
    dx, dy, sc, rot = tr
    x, y, vw, vh, scale, top, W, H = _cam_view(dst, src, zoom, cx, cy, shake)
    rect = pygame.Rect(int(x), int(y), max(1, int(vw)), max(1, int(vh))).clip(src.get_rect())
    lay = pygame.transform.smoothscale(src.subsurface(rect), (int(W * sc), int(H * sc)))
    if abs(rot) > 0.05:
        lay = pygame.transform.rotate(lay, rot)
    cxp = W / 2 + dx * W
    cyp = top + H / 2 + dy * H
    dst.blit(lay, (int(cxp - lay.get_width() / 2), int(cyp - lay.get_height() / 2)))


def _lerp_tr(a, b, u):
    return tuple(a[i] + (b[i] - a[i]) * u for i in range(4))


def _particles(dst, kind, t, seed, origin=None):
    W, H = dst.get_size()
    rng = random.Random(seed)
    if kind == "sparks":
        ox, oy = origin[0] * W, origin[1] * H
        for i in range(70):
            ang = rng.uniform(0, 2 * math.pi)
            sp = rng.uniform(0.25, 1.0) * W * 0.00045
            life = rng.uniform(500, 1500)
            if t > life:
                continue
            k = t / life
            d = sp * t * (1 - 0.35 * k)
            x, y = ox + math.cos(ang) * d, oy + math.sin(ang) * d + 0.00012 * H * (t / 10) ** 2 / 10
            a = int(255 * (1 - k))
            L = max(2, int(10 * (1 - k)))
            col = (255, 220 - int(80 * k), 120 - int(100 * k))
            pygame.draw.line(dst, col, (x, y), (x - math.cos(ang) * L, y - math.sin(ang) * L), 2)
            if a > 120:
                pygame.draw.circle(dst, (255, 250, 220), (int(x), int(y)), 1)
    elif kind == "dust":
        layer = pygame.Surface((W, H), pygame.SRCALPHA)
        for i in range(40):
            x = (rng.uniform(0, W) + t * rng.uniform(0.01, 0.04)) % W
            y = H * rng.uniform(0.55, 0.95) - t * rng.uniform(0.003, 0.01)
            r = int(rng.uniform(40, 110))
            for k in range(4):
                pygame.draw.circle(layer, (230, 190, 130, int(rng.uniform(3, 6))), (int(x), int(y)), r - k * r // 5)
        dst.blit(layer, (0, 0))
    elif kind == "petals":
        for i in range(55):
            x0 = rng.uniform(-0.1, 1.1) * W
            fall = rng.uniform(0.05, 0.12) * H / 1000
            y = (rng.uniform(-0.6, 0.4) * H + fall * t) % (H * 1.2) - H * 0.1
            x = x0 + math.sin(t / 380 + i) * 24
            s = rng.uniform(3, 7)
            ang = t / 200 + i
            pts = [(x + math.cos(ang) * s * 1.6, y + math.sin(ang) * s * 1.6),
                   (x + math.cos(ang + 1.8) * s * 0.7, y + math.sin(ang + 1.8) * s * 0.7),
                   (x - math.cos(ang) * s * 1.6, y - math.sin(ang) * s * 1.6),
                   (x + math.cos(ang - 1.8) * s * 0.7, y + math.sin(ang - 1.8) * s * 0.7)]
            pygame.draw.polygon(dst, (205, 40 + i % 30, 60), pts)


def _arrow(dst, u, p0, p1):
    """Slow-motion arrow: long glowing streak, motion-blurred shaft, bright head."""
    W, H = dst.get_size()
    x = p0[0] + (p1[0] - p0[0]) * u
    y = p0[1] + (p1[1] - p0[1]) * u
    dx, dy = p1[0] - p0[0], p1[1] - p0[1]
    n = math.hypot(dx, dy) or 1
    dx, dy = dx / n, dy / n
    k = W / 1280
    trail_len = min(n * u, 760 * k)
    glow = pygame.Surface((W, H), pygame.SRCALPHA)
    steps = 26
    for i in range(steps):
        f0, f1 = i / steps, (i + 1) / steps
        a = int(190 * (1 - f0) ** 1.6)
        for wdt, col in ((int(56 * k * (1 - f0)) + 3, (255, 200, 110, a // 4)),
                         (int(22 * k * (1 - f0)) + 2, (255, 225, 160, a // 2)),
                         (int(8 * k * (1 - f0)) + 2, (255, 250, 230, a))):
            pygame.draw.line(glow, col, (x - dx * trail_len * f0, y - dy * trail_len * f0),
                             (x - dx * trail_len * f1, y - dy * trail_len * f1), max(1, wdt))
    dst.blit(glow, (0, 0))
    L = 190 * k
    pygame.draw.line(dst, (60, 38, 20), (x - dx * L, y - dy * L), (x, y), max(3, int(6 * k)))
    pygame.draw.line(dst, (150, 110, 70), (x - dx * L, y - dy * L - 1), (x, y - 1), max(1, int(2 * k)))
    hs = 30 * k
    pygame.draw.polygon(dst, (235, 235, 240), [(x + dx * hs, y + dy * hs), (x - dy * hs * 0.45, y + dx * hs * 0.45),
                                               (x + dy * hs * 0.45, y - dx * hs * 0.45)])
    for sgn in (-1, 1):
        pygame.draw.polygon(dst, (225, 60, 50), [(x - dx * (L - 4), y - dy * (L - 4)),
                                                (x - dx * (L + 26 * k) + sgn * dy * 16 * k, y - dy * (L + 26 * k) - sgn * dx * 16 * k),
                                                (x - dx * (L - 30 * k), y - dy * (L - 30 * k))])
    hot = pygame.Surface((int(90 * k), int(90 * k)), pygame.SRCALPHA)
    for r in range(int(45 * k), 0, -3):
        pygame.draw.circle(hot, (255, 240, 200, int(90 * (1 - r / (45 * k)))), (int(45 * k), int(45 * k)), r)
    dst.blit(hot, (int(x - 45 * k), int(y - 45 * k)))


def _burst(dst, t, origin, seed=3):
    """Sand / debris burst at an impact point (screen px)."""
    if t > 1100:
        return
    rng = random.Random(seed)
    W, H = dst.get_size()
    lay = pygame.Surface((W, H), pygame.SRCALPHA)
    for i in range(60):
        ang = rng.uniform(math.pi * 0.95, math.pi * 2.05)
        sp = rng.uniform(0.2, 1.0) * W * 0.0007
        d = sp * t
        gx = origin[0] + math.cos(ang) * d
        gy = origin[1] + math.sin(ang) * d * 0.6 + 0.0000009 * H * t * t
        a = int(200 * max(0, 1 - t / 1100))
        r = int(rng.uniform(2, 6) * W / 1280)
        pygame.draw.circle(lay, (120, 90, 60, a), (int(gx), int(gy)), r)
    for i in range(6):
        rr = int((40 + i * 26) * (0.4 + t / 700) * W / 1280)
        pygame.draw.circle(lay, (230, 195, 140, int(26 * max(0, 1 - t / 1100))), (int(origin[0]), int(origin[1])), rr)
    dst.blit(lay, (0, 0))


def _glint(dst, k, p):
    W = dst.get_width()
    s = (0.5 + 0.5 * math.sin(k * math.pi)) * W / 1280
    g = pygame.Surface((int(160 * s) + 2, int(160 * s) + 2), pygame.SRCALPHA)
    c = g.get_width() // 2
    for r in range(c, 0, -2):
        pygame.draw.circle(g, (255, 240, 190, int(120 * (1 - r / c))), (c, c), r)
    pygame.draw.line(g, (255, 250, 230, 220), (0, c), (2 * c, c), 2)
    pygame.draw.line(g, (255, 250, 230, 160), (c, c // 3), (c, 2 * c - c // 3), 2)
    dst.blit(g, (int(p[0] - c), int(p[1] - c)))


def _grade(dst, strength=14):
    """Warm golden lift + radial vignette, like the film."""
    W, H = dst.get_size()
    over = pygame.Surface((W, H), pygame.SRCALPHA)
    over.fill((255, 190, 110, strength))
    dst.blit(over, (0, 0))
    dst.blit(_vignette(W, H), (0, 0))


_vig_cache = {}


def _vignette(W, H):
    if (W, H) not in _vig_cache:
        small = pygame.Surface((64, 36), pygame.SRCALPHA)
        for y in range(36):
            for x in range(64):
                r = min(1.0, math.hypot((x - 31.5) / 32, (y - 17.5) / 18))
                small.set_at((x, y), (12, 6, 0, int(190 * max(0, r - 0.55) / 0.45)))
        _vig_cache[(W, H)] = pygame.transform.smoothscale(small, (W, H))
    return _vig_cache[(W, H)]


def _text(dst, text, font, size, color, center, shadow=True):
    f = _font(font, size)
    s = f.render(text, True, color)
    r = s.get_rect(center=center)
    if shadow:
        sh = f.render(text, True, (0, 0, 0))
        for o in ((2, 2), (0, 2), (2, 0)):
            dst.blit(sh, r.move(*o))
    dst.blit(s, r)


def render(dst, boss_id, kind, t):
    """Draw the cinematic frame at t ms into dst."""
    sc = SCRIPTS[(boss_id, kind)]
    W, H = dst.get_size()
    dst.fill((0, 0, 0))
    shot = next((s for s in sc["shots"] if s["t0"] <= t < s["t1"]), sc["shots"][-1])
    u = _ease(shot.get("ease"), (t - shot["t0"]) / max(1, shot["t1"] - shot["t0"]))
    a, b = shot["a"], shot["b"]
    zoom = a[0] + (b[0] - a[0]) * u
    cx = a[1] + (b[1] - a[1]) * u
    cy = a[2] + (b[2] - a[2]) * u
    sx = sy = 0.0
    if shot.get("shake"):
        s0, dur, amp = shot["shake"]
        if s0 <= t < s0 + dur:
            k = 1 - (t - s0) / dur
            sx = math.sin(t * 0.13) * amp * k * W / 1280
            sy = math.cos(t * 0.17) * amp * k * W / 1280
    plate = _img(boss_id, shot["img"])
    to_screen = _cam_blit(dst, plate, zoom, cx, cy, (sx, sy))
    lt = t - shot["t0"]
    span = max(1, shot["t1"] - shot["t0"])
    if shot.get("dust"):
        _particles(dst, "dust", lt, 11)
    for ly in shot.get("layers", ()):
        lu = _ease(ly[3], lt / span)
        _cam_layer(dst, _img(boss_id, ly[0]), zoom, cx, cy, (sx, sy), _lerp_tr(ly[1], ly[2], lu))
    if shot.get("sparks"):
        _particles(dst, "sparks", lt, 7, tuple(v / d for v, d in zip(to_screen(*shot["sparks"]), dst.get_size())))
    if shot.get("burst"):
        _burst(dst, lt, to_screen(*shot["burst"]))
    if shot.get("glint"):
        g0, g1, gp = shot["glint"]
        if g0 <= t < g1:
            _glint(dst, (t - g0) / (g1 - g0), to_screen(*gp))
    if shot.get("petals"):
        _particles(dst, "petals", lt, 5)
    if shot.get("arrow"):
        a0, a1, p0, p1 = shot["arrow"]
        if a0 <= t < a1:
            uu = (t - a0) / (a1 - a0)
            _arrow(dst, 1 - (1 - uu) ** 1.4, to_screen(*p0), to_screen(*p1))
    _grade(dst)
    # Flash cut
    fi = shot.get("flash_in")
    if fi and lt < fi:
        fl = pygame.Surface((W, H))
        fl.fill((255, 244, 220))
        fl.set_alpha(int(255 * (1 - lt / fi) ** 1.5))
        dst.blit(fl, (0, 0))
    # Fade in / out of the whole piece
    L = sc["length"]
    fade = min(1.0, t / 250.0, max(0.0, (L - t) / 400.0))
    if fade < 1:
        blk = pygame.Surface((W, H))
        blk.fill((0, 0, 0))
        blk.set_alpha(int(255 * (1 - fade)))
        dst.blit(blk, (0, 0))
    # Letterbox (slides in)
    bar = int(H * LETTERBOX * min(1.0, t / BAR_IN_MS))
    pygame.draw.rect(dst, (0, 0, 0), (0, 0, W, bar))
    pygame.draw.rect(dst, (0, 0, 0), (0, H - bar, W, bar))
    # Captions in the lower bar
    for c0, c1, title, line in sc["captions"]:
        if c0 <= t < c1:
            k = min(1.0, (t - c0) / 300.0, (c1 - t) / 300.0)
            col = lambda c: tuple(int(v * k) for v in c)  # noqa: E731
            if title:
                band = pygame.Surface((int(W * 0.56), int(H * 0.19)), pygame.SRCALPHA)
                for yy in range(band.get_height()):
                    a = int(150 * k * (1 - abs(yy / band.get_height() - 0.5) * 2) ** 0.6)
                    pygame.draw.line(band, (0, 0, 0, a), (0, yy), (band.get_width(), yy))
                dst.blit(band, band.get_rect(center=(W // 2, int(H * 0.775))))
                _text(dst, "  ".join(title), "Cinzel.ttf", max(16, int(H * 0.042)), col((255, 205, 120)),
                      (W // 2, int(H * 0.725)))
                _text(dst, line, "Cinzel.ttf", max(20, int(H * 0.085)), col((255, 236, 190)),
                      (W // 2, int(H * 0.81)))
            else:
                _text(dst, line, "EBGaramond.ttf", max(16, int(H * 0.042)), col((250, 235, 205)),
                      (W // 2, H - bar // 2), shadow=False)
    return dst


# --- Player in the client -------------------------------------------------------------------
class Player:
    def __init__(self, boss_id, kind, on_done=None):
        self.boss_id, self.kind, self.on_done = boss_id, kind, on_done
        self.t0 = pygame.time.get_ticks()
        self.length = SCRIPTS[(boss_id, kind)]["length"]
        self._fired = set()
        self.done = False

    def elapsed(self):
        return pygame.time.get_ticks() - self.t0

    def _sfx(self, t):
        for i, (at, name) in enumerate(SCRIPTS[(self.boss_id, self.kind)]["sfx"]):
            if t >= at and i not in self._fired:
                self._fired.add(i)
                try:
                    if not pygame.mixer.get_init():
                        continue
                    if name not in _sfx_cache:
                        _sfx_cache[name] = pygame.mixer.Sound(os.path.join(CIN_DIR, "sfx", name + ".wav"))
                    _sfx_cache[name].play()
                except Exception:
                    pass

    def handle_event(self, event):
        if event.type == pygame.KEYDOWN and event.key in (pygame.K_ESCAPE, pygame.K_SPACE, pygame.K_RETURN):
            self.finish()
            return True
        if event.type == pygame.MOUSEBUTTONDOWN and self.elapsed() > 600:
            self.finish()
            return True
        return False

    def finish(self):
        if not self.done:
            self.done = True
            if self.on_done:
                self.on_done()

    def draw(self, surface):
        t = self.elapsed()
        if t >= self.length:
            self.finish()
            return
        self._sfx(t)
        try:
            render(surface, self.boss_id, self.kind, t)
            if t > 900:
                _text(surface, "Space to skip", "EBGaramond.ttf", 14, (150, 130, 100),
                      (surface.get_width() - 70, 12), shadow=False)
        except Exception:
            self.finish()
