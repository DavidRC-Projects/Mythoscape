"""Sidebars v2 materials (SIDEBARS_STYLE_SPEC.md section 9): carved wood, worn gold leaf,
3D raised / inset buttons, glossy bars with gem caps, keycaps, painted-shape icons.

Every glyph (arrows, ticks, icons) is drawn as shapes: the Mac font shows boxes for symbols.
hud_v2 calls these; on any exception it falls back to its old flat drawing.
"""
from __future__ import annotations

import math
import os
import random

import pygame

def _c(h):
    return tuple(int(h[i:i + 2], 16) for i in (1, 3, 5))

WOOD = _c("#2A1E14"); WOOD_DK = _c("#120C08"); BEVEL = _c("#5A4630")
BASE = _c("#1A140E"); SLOT = _c("#281F18"); SLOT_IN = _c("#3A2E22")
GOLD = _c("#B39465"); GOLD_HI = _c("#E6CB8E"); TITLE = _c("#CEAE73")
GLOW = _c("#F2C14E"); PULSE = _c("#FFD36B"); PARCH = _c("#CAAE87"); INK = _c("#2B2118")
ACTIVE_TXT = _c("#FFF1CF"); IDLE_TXT = _c("#CEAE73"); MUTED = _c("#A8987A")
HP_TOP, HP_BOT = _c("#8EE06A"), _c("#1F5A1A"); HP_LOW = _c("#9E2B25")
XP_TOP, XP_BOT = _c("#FFD36B"), _c("#7A5418")
DANGER_TOP, DANGER_BOT, DANGER_TXT = _c("#8A2C24"), _c("#3E1310"), _c("#F3C9BF")
ARC_TOP, ARC_BOT, ARC_GLOW, ARC_TXT = _c("#46186E"), _c("#281046"), _c("#B07CFF"), _c("#F2E6FF")
SAFE, SAFE_TXT = _c("#22401E"), _c("#9FE08A")
RARITY = {"common": _c("#8A6A3E"), "uncommon": _c("#3F9D4A"), "rare": _c("#3E7FD0"),
          "epic": _c("#8A3FC0"), "legendary": _c("#C08A2E")}

_FONT_DIR = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", "assets", "fonts"))
_FONTS, _CACHE = {}, {}


def font(kind, size):
    key = (kind, size)
    if key not in _FONTS:
        name = "EBGaramond.ttf" if kind == "body" else "Cinzel.ttf"
        try:
            f = pygame.font.Font(os.path.join(_FONT_DIR, name), size)
        except Exception:
            f = pygame.font.Font(None, size + 4)
        if kind == "title":
            f.set_bold(True)
        _FONTS[key] = f
    return _FONTS[key]


def text(surf, s, f, col, pos, anchor="topleft", shadow=True):
    img = f.render(str(s), True, col)
    r = img.get_rect(**{anchor: pos})
    if shadow:
        surf.blit(f.render(str(s), True, (0, 0, 0)), r.move(1, 1))
    surf.blit(img, r)
    return r


def fit(f, s, w):
    s = str(s)
    if f.size(s)[0] <= w:
        return s
    while s and f.size(s + "...")[0] > w:
        s = s[:-1]
    return s.rstrip() + "..."


def _lerp(a, b, t):
    return tuple(int(a[i] + (b[i] - a[i]) * t) for i in range(3))


def _mask(w, h, r):
    key = ("mask", w, h, r)
    if key not in _CACHE:
        m = pygame.Surface((w, h), pygame.SRCALPHA)
        pygame.draw.rect(m, (255, 255, 255, 255), (0, 0, w, h), border_radius=r)
        _CACHE[key] = m
    return _CACHE[key]


def _clip_round(img, r):
    out = pygame.Surface(img.get_size(), pygame.SRCALPHA)
    out.blit(img, (0, 0))
    out.blit(_mask(*img.get_size(), r), (0, 0), special_flags=pygame.BLEND_RGBA_MIN)
    return out


def _grad(w, h, top, bot):
    key = ("grad", w, h, top, bot)
    if key not in _CACHE:
        s = pygame.Surface((max(1, w), max(1, h)))
        for i in range(h):
            s.fill(_lerp(top, bot, i / max(1, h - 1)), (0, i, w, 1))
        _CACHE[key] = s
    return _CACHE[key]


def _grain(w, h, base, seed=7, strength=1.0):
    """Carved-wood grain: sine-warped streaks plus fine noise (cached per size)."""
    key = ("grain", w, h, base, seed, strength)
    if key in _CACHE:
        return _CACHE[key]
    s = pygame.Surface((max(1, w), max(1, h)))
    s.fill(base)
    rng = random.Random(seed + w * 7 + h)
    lines = pygame.Surface((max(1, w), max(1, h)), pygame.SRCALPHA)
    for k in range(max(3, h // 3)):
        y0 = rng.uniform(0, h)
        amp = rng.uniform(0.6, 2.4)
        freq = rng.uniform(0.01, 0.04)
        ph = rng.uniform(0, 6.3)
        dark = rng.random() < 0.6
        a = int(rng.randint(14, 34) * strength)
        col = (0, 0, 0, a) if dark else (255, 220, 170, a // 2)
        pts = [(x, y0 + amp * math.sin(x * freq + ph) + 0.6 * math.sin(x * freq * 3.3)) for x in range(0, w + 6, 6)]
        if len(pts) > 1:
            pygame.draw.lines(lines, col, False, pts, 1)
    s.blit(lines, (0, 0))
    for _ in range(w * h // 14):
        x, y = rng.randrange(max(1, w)), rng.randrange(max(1, h))
        n = rng.randint(-10, 10)
        c = s.get_at((x, y))
        s.set_at((x, y), (max(0, min(255, c[0] + n)), max(0, min(255, c[1] + n)), max(0, min(255, c[2] + n))))
    _CACHE[key] = s
    return s


def _inner_shadow(surf, rect, r, depth=6, alpha=170):
    sh = pygame.Surface(rect.size, pygame.SRCALPHA)
    for i in range(depth):
        a = int(alpha * (1 - i / depth) ** 2)
        pygame.draw.rect(sh, (0, 0, 0, a), (i, i, rect.w - 2 * i, rect.h - 2 * i), 1, border_radius=max(0, r - i))
    surf.blit(sh, rect.topleft)


def gold_rim(surf, rect, r, width=3, reverse=False):
    """Worn gold leaf: vertical sheen #E6CB8E -> #5A4020 with a rubbed-noise multiply."""
    key = ("rim", rect.w, rect.h, r, width, reverse)
    if key not in _CACHE:
        top, bot = (_c("#E6CB8E"), _c("#5A4020")) if not reverse else (_c("#5A4020"), _c("#E6CB8E"))
        g = pygame.Surface(rect.size, pygame.SRCALPHA)
        g.blit(_grad(rect.w, rect.h, top, bot), (0, 0))
        rng = random.Random(rect.w * 31 + rect.h)
        for _ in range(max(4, (rect.w + rect.h) // 3)):
            x, y = rng.randrange(rect.w), rng.randrange(rect.h)
            pygame.draw.circle(g, (60, 40, 20), (x, y), 1)
        ring = pygame.Surface(rect.size, pygame.SRCALPHA)
        pygame.draw.rect(ring, (255, 255, 255, 255), (0, 0, rect.w, rect.h), width, border_radius=r)
        g.blit(ring, (0, 0), special_flags=pygame.BLEND_RGBA_MIN)
        _CACHE[key] = g
    surf.blit(_CACHE[key], rect.topleft)
    pygame.draw.rect(surf, WOOD_DK, rect.inflate(-2 * width, -2 * width), 1, border_radius=max(0, r - width))


def glow(surf, rect, col, rad=8, alpha=100, r=8):
    g = pygame.Surface((rect.w + rad * 2, rect.h + rad * 2), pygame.SRCALPHA)
    for i in range(rad, 0, -1):
        a = int(alpha * (1 - i / rad) ** 1.6)
        pygame.draw.rect(g, (*col, a), (rad - i, rad - i, rect.w + 2 * i, rect.h + 2 * i), 2, border_radius=r + i)
    surf.blit(g, (rect.x - rad, rect.y - rad))


def card(surf, rect, r=8, ornate=False, base=WOOD, highlight=False):
    """Carved wood frame card with a gold-leaf rim and an inner shadow well."""
    if rect.w < 6 or rect.h < 6:
        return
    sh = pygame.Surface((rect.w + 6, rect.h + 6), pygame.SRCALPHA)
    pygame.draw.rect(sh, (0, 0, 0, 120), (3, 4, rect.w, rect.h), border_radius=r)
    surf.blit(sh, (rect.x - 3, rect.y - 2))
    surf.blit(_clip_round(_grain(rect.w, rect.h, base), r), rect.topleft)
    _inner_shadow(surf, rect.inflate(-4, -4), max(0, r - 2), 6, 150)
    gold_rim(surf, rect, r, 2 if rect.h < 60 else 3)
    if highlight:
        pygame.draw.rect(surf, GOLD_HI, rect, 1, border_radius=r)
    if ornate and rect.w >= 100 and rect.h >= 48:
        for cx, cy, sx, sy in ((rect.x, rect.y, 1, 1), (rect.right - 1, rect.y, -1, 1),
                               (rect.x, rect.bottom - 1, 1, -1), (rect.right - 1, rect.bottom - 1, -1, -1)):
            corner(surf, cx, cy, sx, sy, 14)


def corner(surf, cx, cy, sx, sy, n=14):
    pts = [(cx, cy), (cx + sx * n, cy), (cx + sx * (n - 4), cy + sy * 3), (cx + sx * 3, cy + sy * 3),
           (cx + sx * 3, cy + sy * (n - 4)), (cx, cy + sy * n)]
    pygame.draw.polygon(surf, GOLD, pts)
    pygame.draw.polygon(surf, WOOD_DK, pts, 1)
    pygame.draw.line(surf, GOLD_HI, (cx + sx, cy + sy), (cx + sx * (n - 3), cy + sy), 1)
    diamond(surf, cx + sx * 5, cy + sy * 5, 3, TITLE, WOOD_DK)


def diamond(surf, cx, cy, r, fill, edge=None):
    pts = [(cx, cy - r), (cx + r, cy), (cx, cy + r), (cx - r, cy)]
    pygame.draw.polygon(surf, fill, pts)
    if edge:
        pygame.draw.polygon(surf, edge, pts, 1)


def well(surf, rect, r=5, fill=(10, 7, 4)):
    pygame.draw.rect(surf, fill, rect, border_radius=r)
    _inner_shadow(surf, rect, r, 4, 200)
    pygame.draw.rect(surf, BEVEL, rect, 1, border_radius=r)


FACES = {
    "idle": (_c("#3E3022"), _c("#1C150E")),
    "active": (_c("#6E5430"), _c("#3E2E18")),
    "primary": (_c("#C49A4E"), _c("#6A4A1E")),
    "danger": (DANGER_TOP, DANGER_BOT),
    "arcane": (ARC_TOP, ARC_BOT),
    "safe": (_c("#3C7A34"), _c("#1C3A18")),
    "off": (_c("#3A2A20"), _c("#1E140E")),
}


def button(surf, rect, kind="idle", inset=False, hover=False, disabled=False, r=6):
    """Raised 3D button; inset=True is the active/pressed state (reversed rim, inner shadow, underglow)."""
    if rect.w < 6 or rect.h < 6:
        return
    top, bot = FACES.get(kind, FACES["idle"])
    if inset:
        top, bot = bot, top
    if hover and not disabled:
        top, bot = _lerp(top, (255, 255, 255), 0.08), _lerp(bot, (255, 255, 255), 0.08)
        glow(surf, rect, GLOW, 6, 90, r)
    if not inset:
        sh = pygame.Surface((rect.w, rect.h), pygame.SRCALPHA)
        pygame.draw.rect(sh, (0, 0, 0, 200), (0, 0, rect.w, rect.h), border_radius=r)
        surf.blit(sh, (rect.x, rect.y + 3))
    face = pygame.Surface(rect.size, pygame.SRCALPHA)
    face.blit(_grad(rect.w, rect.h, top, bot), (0, 0))
    gr = _grain(rect.w, rect.h, (150, 150, 150), seed=3, strength=1.3)
    face.blit(gr, (0, 0), special_flags=pygame.BLEND_RGB_MULT)
    tint = _grad(rect.w, rect.h, top, bot).copy()
    tint.set_alpha(150)
    face.blit(tint, (0, 0))
    surf.blit(_clip_round(face, r), rect.topleft)
    if not inset:
        hl = pygame.Surface((rect.w - 6, max(1, rect.h // 2 - 2)), pygame.SRCALPHA)
        for i in range(hl.get_height()):
            hl.fill((255, 255, 255, int(46 * (1 - i / max(1, hl.get_height())))), (0, i, hl.get_width(), 1))
        surf.blit(hl, (rect.x + 3, rect.y + 3))
        pygame.draw.line(surf, _c("#FFECBE"), (rect.x + r, rect.y + 2), (rect.right - r - 1, rect.y + 2))
        pygame.draw.line(surf, (8, 5, 3), (rect.x + r, rect.bottom - 2), (rect.right - r - 1, rect.bottom - 2), 2)
    else:
        _inner_shadow(surf, rect.inflate(-2, -2), r, 5, 190)
        pygame.draw.line(surf, PULSE, (rect.x + r + 2, rect.bottom - 3), (rect.right - r - 3, rect.bottom - 3), 1)
    rim_w = 2 if rect.h < 30 else 3
    gold_rim(surf, rect, r, rim_w, reverse=inset)
    if hover and not disabled:
        pygame.draw.rect(surf, GOLD_HI, rect, 1, border_radius=r)
    if kind == "arcane":
        pygame.draw.rect(surf, ARC_GLOW, rect.inflate(-2 * rim_w - 2, -2 * rim_w - 2), 1, border_radius=max(1, r - 3))
    if rect.w > 60 and rect.h > 40:
        for x in (rect.x + 6, rect.right - 7):
            for y in (rect.y + 6, rect.bottom - 7):
                pygame.draw.circle(surf, GOLD, (x, y), 2)
                pygame.draw.circle(surf, GOLD_HI, (x - 1, y - 1), 1)
    if disabled:
        veil = pygame.Surface(rect.size, pygame.SRCALPHA)
        pygame.draw.rect(veil, (40, 36, 32, 120), (0, 0, rect.w, rect.h), border_radius=r)
        surf.blit(veil, rect.topleft)


def label_color(kind, inset=False):
    return {"primary": INK, "danger": DANGER_TXT, "arcane": ARC_TXT, "safe": SAFE_TXT}.get(
        kind, ACTIVE_TXT if inset else IDLE_TXT)


def bar(surf, rect, pct, kind="hp", low=False, ticks=True, t=0.0):
    """Recessed gold trough + glossy liquid fill + meniscus + faceted gem end caps."""
    if rect.w < 10 or rect.h < 4:
        return
    pct = max(0.0, min(1.0, pct))
    capw = max(5, rect.h // 2 + 2)
    trough = pygame.Rect(rect.x + capw - 2, rect.y, rect.w - 2 * capw + 4, rect.h)
    gold_rim(surf, trough, rect.h // 2, 2)
    inner = trough.inflate(-4, -4)
    pygame.draw.rect(surf, (6, 4, 3), inner, border_radius=max(1, inner.h // 2))
    pygame.draw.line(surf, (0, 0, 0), (inner.x + 2, inner.y), (inner.right - 3, inner.y))
    if kind == "hp":
        top, bot = (HP_LOW, _c("#4E1210")) if low else (HP_TOP, HP_BOT)
    elif kind == "zoom":
        top, bot = _c("#B8C77A"), _c("#3E5A22")
    else:
        top, bot = XP_TOP, XP_BOT
    fw = int(inner.w * pct)
    if fw > 1:
        fr = pygame.Rect(inner.x, inner.y, fw, inner.h)
        if low:
            a = 0.5 + 0.5 * math.sin(t * 6)
            top = _lerp(top, (255, 120, 100), 0.25 * a)
        glow(surf, fr, top, 4, 70, inner.h // 2)
        fill = pygame.Surface(fr.size, pygame.SRCALPHA)
        h = fr.h
        for i in range(h):
            u = i / max(1, h - 1)
            core = 1 - abs(u - 0.35) * 1.6
            col = _lerp(bot, top, max(0.0, min(1.0, 0.35 + core)))
            fill.fill(col, (0, i, fr.w, 1))
        streak = pygame.Surface((fr.w, max(1, h // 3)), pygame.SRCALPHA)
        streak.fill((255, 255, 255, 70))
        fill.blit(streak, (0, max(0, h // 6)))
        rng = random.Random(fr.w)
        for _ in range(fr.w // 3):
            fill.set_at((rng.randrange(fr.w), rng.randrange(h)), (*_lerp(top, (255, 255, 255), 0.4), 90))
        surf.blit(_clip_round(fill, max(1, h // 2)), fr.topleft)
        pygame.draw.line(surf, _lerp(top, (255, 255, 255), 0.6), (fr.right - 1, fr.y + 1), (fr.right - 1, fr.bottom - 2))
    if ticks and inner.w > 60:
        for k in range(1, 10):
            x = inner.x + inner.w * k // 10
            pygame.draw.line(surf, (0, 0, 0), (x, inner.y + 1), (x, inner.y + max(2, inner.h // 3)))
    gem = top if fw > 1 else (90, 80, 60)
    for cx in (rect.x + capw // 2 + 1, rect.right - capw // 2 - 2):
        cy = rect.centery
        rr = max(4, rect.h // 2 + 1)
        pts = [(cx, cy - rr), (cx + rr - 1, cy), (cx, cy + rr), (cx - rr + 1, cy)]
        pygame.draw.polygon(surf, GOLD, pts)
        pygame.draw.polygon(surf, WOOD_DK, pts, 1)
        pygame.draw.line(surf, GOLD_HI, pts[0], pts[3])
        g = max(2, rr - 3)
        diamond(surf, cx, cy, g, gem, WOOD_DK)
        pygame.draw.circle(surf, (255, 255, 255), (cx - 1, cy - 1), 1)


def keycap(surf, center, label, small=False):
    f = font("title" if label.isalnum() else "body", (10 if small else 11) + (0 if label.isalnum() else 3))
    w = max(13 if small else 15, f.size(label)[0] + 6)
    h = 12 if small else 14
    r = pygame.Rect(0, 0, w, h)
    r.center = center
    pygame.draw.rect(surf, (20, 14, 8), r.move(0, 1), border_radius=3)
    pygame.draw.rect(surf, PARCH, r, border_radius=3)
    pygame.draw.line(surf, (240, 226, 196), (r.x + 2, r.y + 1), (r.right - 3, r.y + 1))
    pygame.draw.rect(surf, _c("#6A5236"), r, 1, border_radius=3)
    if label in ("[", "]"):  # bracket drawn as lines (font glyph unreliable on Mac)
        x = r.centerx - 1 if label == "[" else r.centerx + 1
        d = 3 if label == "[" else -3
        pygame.draw.lines(surf, INK, False, [(x + d, r.y + 2), (x, r.y + 2), (x, r.bottom - 3), (x + d, r.bottom - 3)], 2)
    else:
        text(surf, label, f, INK, (r.centerx, r.centery + 1), "center", shadow=False)
    return r


def notify_dot(surf, cx, cy):
    pygame.draw.circle(surf, (40, 24, 6), (cx, cy + 1), 6)
    pygame.draw.circle(surf, GLOW, (cx, cy), 5)
    pygame.draw.line(surf, INK, (cx, cy - 3), (cx, cy), 2)
    pygame.draw.circle(surf, INK, (cx, cy + 2), 1)


# ---------------------------------------------------------------- icons (all shapes)
def medallion(surf, cx, cy, r, fill=SLOT):
    pygame.draw.circle(surf, (0, 0, 0), (cx, cy + 1), r + 1)
    pygame.draw.circle(surf, GOLD, (cx, cy), r)
    pygame.draw.circle(surf, GOLD_HI, (cx, cy), r, 1)
    pygame.draw.circle(surf, fill, (cx, cy), r - 2)
    pygame.draw.circle(surf, WOOD_DK, (cx, cy), r - 2, 1)


def icon(surf, kind, cx, cy, s=10, col=None):
    """Nav / currency / weather icons drawn with polygons and lines (s = half size)."""
    c = col or GOLD_HI
    dk = WOOD_DK
    if kind == "scroll":
        body = pygame.Rect(cx - s + 2, cy - s + 3, 2 * s - 4, 2 * s - 6)
        pygame.draw.rect(surf, PARCH, body)
        for yy in (body.y, body.bottom):
            pygame.draw.ellipse(surf, c, (body.x - 3, yy - 3, body.w + 6, 6))
            pygame.draw.ellipse(surf, dk, (body.x - 3, yy - 3, body.w + 6, 6), 1)
        for k in range(3):
            y = body.y + 4 + k * 4
            pygame.draw.line(surf, INK, (body.x + 3, y), (body.right - 4 - (k == 2) * 4, y))
    elif kind == "pennant":
        pygame.draw.line(surf, c, (cx - s + 3, cy - s), (cx - s + 3, cy + s), 2)
        pts = [(cx - s + 4, cy - s + 1), (cx + s, cy - s + 5), (cx - s + 4, cy + 2)]
        pygame.draw.polygon(surf, _c("#B0302A"), pts)
        pygame.draw.polygon(surf, dk, pts, 1)
    elif kind == "party":
        for dx, sc in ((-s // 2 - 1, 0.85), (s // 2 + 1, 1.0)):
            hr = max(2, int(s * 0.3 * sc))
            pygame.draw.circle(surf, c, (cx + dx, cy - s // 3), hr)
            pygame.draw.ellipse(surf, c, (cx + dx - hr - 2, cy - s // 3 + hr, 2 * hr + 4, int(s * 1.1)))
            pygame.draw.circle(surf, dk, (cx + dx, cy - s // 3), hr, 1)
    elif kind == "guild":
        pts = [(cx - s + 1, cy - s + 1), (cx + s - 1, cy - s + 1), (cx + s - 1, cy), (cx, cy + s), (cx - s + 1, cy)]
        pygame.draw.polygon(surf, _c("#2E4C8A"), pts)
        pygame.draw.polygon(surf, c, pts, 2)
        pygame.draw.line(surf, c, (cx, cy - s + 4), (cx, cy + s - 4), 2)
        pygame.draw.line(surf, c, (cx - s + 5, cy - 2), (cx + s - 5, cy - 2), 2)
    elif kind == "map":
        w = s * 2 - 2
        x0 = cx - s + 1
        pts = [(x0, cy - s + 3), (x0 + w // 3, cy - s + 1), (x0 + 2 * w // 3, cy - s + 3), (x0 + w, cy - s + 1),
               (x0 + w, cy + s - 3), (x0 + 2 * w // 3, cy + s - 1), (x0 + w // 3, cy + s - 3), (x0, cy + s - 1)]
        pygame.draw.polygon(surf, PARCH, pts)
        pygame.draw.polygon(surf, dk, pts, 1)
        for k in (1, 2):
            x = x0 + k * w // 3
            pygame.draw.line(surf, _c("#8A6A3E"), (x, cy - s + 2), (x, cy + s - 2))
        pygame.draw.line(surf, _c("#B0302A"), (cx - 3, cy - 1), (cx + 1, cy + 3), 2)
        pygame.draw.line(surf, _c("#B0302A"), (cx + 1, cy - 1), (cx - 3, cy + 3), 2)
    elif kind == "swords":
        for sx in (-1, 1):
            a, b = (cx - sx * (s - 2), cy + s - 2), (cx + sx * (s - 2), cy - s + 2)
            pygame.draw.line(surf, (220, 224, 230), a, b, 3)
            pygame.draw.line(surf, dk, a, b, 1)
            gx, gy = cx - sx * (s - 6), cy + s - 6
            pygame.draw.line(surf, c, (gx - 3, gy - 3 * sx * -1), (gx + 3, gy + 3 * sx * -1), 2)
    elif kind == "rune":
        pygame.draw.circle(surf, ARC_GLOW, (cx, cy), s, 2)
        pygame.draw.circle(surf, ARC_TXT, (cx, cy), s - 4, 1)
        for k in range(6):
            a = k * math.pi / 3
            pygame.draw.line(surf, ARC_TXT, (cx + math.cos(a) * (s - 4), cy + math.sin(a) * (s - 4)),
                             (cx + math.cos(a) * s, cy + math.sin(a) * s), 1)
        diamond(surf, cx, cy, max(2, s // 3), ARC_GLOW)
    elif kind == "coin":
        pygame.draw.circle(surf, (110, 76, 20), (cx, cy + 1), s)
        pygame.draw.circle(surf, _c("#E3B23C"), (cx, cy), s)
        pygame.draw.circle(surf, _c("#FFE08A"), (cx, cy), s, 1)
        pygame.draw.circle(surf, _c("#9C7020"), (cx, cy), max(2, s - 3), 1)
        pygame.draw.circle(surf, (255, 246, 200), (cx - s // 3, cy - s // 3), max(1, s // 4))
    elif kind == "copper":
        pygame.draw.circle(surf, (70, 36, 14), (cx, cy + 1), s)
        pygame.draw.circle(surf, _c("#B87333"), (cx, cy), s)
        pygame.draw.circle(surf, _c("#E8A36A"), (cx, cy), s, 1)
        pygame.draw.rect(surf, (90, 46, 18), (cx - s // 3, cy - s // 3, 2 * (s // 3) + 1, 2 * (s // 3) + 1), 1)
    elif kind == "gem":
        pts = [(cx - s + 1, cy - s // 3), (cx - s // 2, cy - s + 2), (cx + s // 2, cy - s + 2),
               (cx + s - 1, cy - s // 3), (cx, cy + s - 1)]
        pygame.draw.polygon(surf, _c("#3E8FD8"), pts)
        pygame.draw.polygon(surf, (170, 220, 255), [pts[0], pts[1], pts[2], pts[3], (cx, cy - s // 3)], 1)
        pygame.draw.line(surf, (200, 235, 255), (cx, cy - s // 3), pts[4])
        pygame.draw.polygon(surf, (16, 40, 80), pts, 1)
    elif kind == "moon":
        pygame.draw.circle(surf, (240, 232, 200), (cx, cy), s)
        pygame.draw.circle(surf, col or (24, 18, 12), (cx + s // 2, cy - s // 3), s)
    elif kind == "sun":
        for k in range(8):
            a = k * math.pi / 4
            pygame.draw.line(surf, PULSE, (cx + math.cos(a) * (s - 2), cy + math.sin(a) * (s - 2)),
                             (cx + math.cos(a) * (s + 3), cy + math.sin(a) * (s + 3)), 2)
        pygame.draw.circle(surf, PULSE, (cx, cy), s - 3)
        pygame.draw.circle(surf, (255, 246, 200), (cx - 1, cy - 1), max(1, s // 3))
    elif kind == "gear":
        for k in range(8):
            a = k * math.pi / 4
            pygame.draw.line(surf, c, (cx, cy), (cx + math.cos(a) * s, cy + math.sin(a) * s), 3)
        pygame.draw.circle(surf, c, (cx, cy), s - 3)
        pygame.draw.circle(surf, dk, (cx, cy), max(1, s // 3))
    elif kind == "power":
        pygame.draw.arc(surf, c, (cx - s + 2, cy - s + 3, 2 * s - 4, 2 * s - 4), math.radians(120), math.radians(420), 2)
        pygame.draw.line(surf, c, (cx, cy - s + 1), (cx, cy - 1), 2)


def tri(surf, center, up=True, s=4, col=GOLD_HI):
    cx, cy = center
    pts = [(cx - s, cy + s // 2), (cx + s, cy + s // 2), (cx, cy - s // 2 - 1)] if up else \
          [(cx - s, cy - s // 2), (cx + s, cy - s // 2), (cx, cy + s // 2 + 1)]
    pygame.draw.polygon(surf, col, pts)


def chevron_left(surf, center, s=4, col=GOLD_HI):
    cx, cy = center
    pygame.draw.lines(surf, col, False, [(cx + s // 2, cy - s), (cx - s // 2, cy), (cx + s // 2, cy + s)], 2)


# ---------------------------------------------------------------- composite pieces
def shield_badge(surf, rect, kind, title, sub):
    """Hanging shield banner on a gold rod; colour by zone kind (safe / pvp / dungeon)."""
    fill = {"safe": SAFE, "pvp": _c("#5E1E1A"), "dungeon": _c("#2A2A3A")}.get(kind, SAFE)
    subc = {"safe": SAFE_TXT, "pvp": DANGER_TXT, "dungeon": (190, 190, 220)}.get(kind, SAFE_TXT)
    rod_y = rect.y + 3
    pygame.draw.line(surf, (0, 0, 0), (rect.x - 2, rod_y + 1), (rect.right + 2, rod_y + 1), 3)
    pygame.draw.line(surf, GOLD, (rect.x - 2, rod_y), (rect.right + 2, rod_y), 3)
    for x in (rect.x - 3, rect.right + 3):
        pygame.draw.circle(surf, GOLD_HI, (x, rod_y), 3)
    body = pygame.Rect(rect.x + 2, rod_y + 2, rect.w - 4, rect.h - 8)
    tip = rect.bottom
    pts = [(body.x, body.y), (body.right, body.y), (body.right, body.bottom - 8), (body.centerx, tip), (body.x, body.bottom - 8)]
    sh = [(x + 2, y + 3) for x, y in pts]
    pygame.draw.polygon(surf, (0, 0, 0), sh)
    g = pygame.Surface(rect.size, pygame.SRCALPHA)
    g.blit(_grad(rect.w, rect.h, _lerp(fill, (255, 255, 255), 0.12), _lerp(fill, (0, 0, 0), 0.35)), (0, 0))
    m = pygame.Surface(rect.size, pygame.SRCALPHA)
    pygame.draw.polygon(m, (255, 255, 255, 255), [(x - rect.x, y - rect.y) for x, y in pts])
    g.blit(m, (0, 0), special_flags=pygame.BLEND_RGBA_MIN)
    surf.blit(g, rect.topleft)
    pygame.draw.polygon(surf, GOLD, pts, 2)
    pygame.draw.lines(surf, GOLD_HI, False, pts[:2], 1)
    text(surf, title, font("title", 13), GOLD_HI, (body.centerx, body.y + 11), "center")
    text(surf, sub, font("body", 12), subc, (body.centerx, body.y + 25), "center")


def parchment(surf, rect, plaque=None):
    """Quest scroll: parchment between two wooden rollers with gold finials, plaque on the top roller.
    Returns the safe text rect (>= 11px padding at 1x)."""
    roll_h = 9
    paper = pygame.Rect(rect.x + 6, rect.y + roll_h // 2, rect.w - 12, rect.h - roll_h)
    sh = pygame.Surface(paper.size, pygame.SRCALPHA)
    sh.fill((0, 0, 0, 110))
    surf.blit(sh, paper.move(2, 3).topleft)
    key = ("parch", paper.w, paper.h)
    if key not in _CACHE:
        p = pygame.Surface(paper.size)
        p.blit(_grad(paper.w, paper.h, _c("#D9C29A"), _c("#BFA27A")), (0, 0))
        rng = random.Random(11)
        for _ in range(paper.w * paper.h // 10):
            x, y = rng.randrange(paper.w), rng.randrange(paper.h)
            n = rng.randint(-14, 8)
            cc = p.get_at((x, y))
            p.set_at((x, y), (max(0, cc[0] + n), max(0, cc[1] + n), max(0, cc[2] + n)))
        v = pygame.Surface(paper.size, pygame.SRCALPHA)
        for i in range(10):
            pygame.draw.rect(v, (110, 70, 30, int(60 * (1 - i / 10))), (i, 0, paper.w - 2 * i, paper.h), 1)
        p.blit(v, (0, 0))
        _CACHE[key] = p
    surf.blit(_CACHE[key], paper.topleft)
    for yy in (rect.y, rect.bottom - roll_h):
        roller = pygame.Rect(rect.x + 2, yy, rect.w - 4, roll_h)
        surf.blit(_clip_round(_grad(roller.w, roller.h, _c("#7A5634"), _c("#2A1A0E")), 4), roller.topleft)
        pygame.draw.rect(surf, WOOD_DK, roller, 1, border_radius=4)
        pygame.draw.line(surf, (160, 120, 80), (roller.x + 4, roller.y + 2), (roller.right - 5, roller.y + 2))
        for fx in (rect.x + 1, rect.right - 2):
            pygame.draw.circle(surf, GOLD, (fx, yy + roll_h // 2), 5)
            pygame.draw.circle(surf, GOLD_HI, (fx - 1, yy + roll_h // 2 - 1), 2)
            pygame.draw.circle(surf, WOOD_DK, (fx, yy + roll_h // 2), 5, 1)
    if plaque:
        f = font("title", 11)
        w = f.size(plaque)[0] + 26
        pl = pygame.Rect(rect.centerx - w // 2, rect.y - 6, w, 18)
        pts = [(pl.x - 6, pl.centery), (pl.x, pl.y), (pl.right, pl.y), (pl.right + 6, pl.centery), (pl.right, pl.bottom), (pl.x, pl.bottom)]
        pygame.draw.polygon(surf, _c("#1C150F"), pts)
        pygame.draw.polygon(surf, GOLD, pts, 1)
        text(surf, plaque, f, TITLE, (pl.centerx, pl.centery + 1), "center")
    return paper.inflate(-22, -2 * 6).move(0, 4)


def slot(surf, rect, rarity=None, filled=True, selected=False, hover=False):
    """Inventory slot: recessed fill, rarity rim + soft backlight behind the icon."""
    rim = RARITY.get(rarity or "common")
    pygame.draw.rect(surf, SLOT, rect, border_radius=6)
    _inner_shadow(surf, rect, 6, 5, 170)
    if filled:
        key = ("back", rect.w, rim)
        if key not in _CACHE:
            g = pygame.Surface(rect.size, pygame.SRCALPHA)
            warm = _lerp(rim, (255, 200, 120), 0.45)
            for i in range(rect.w // 2, 0, -1):
                a = int(70 * (1 - i / (rect.w / 2)) ** 1.3)
                pygame.draw.circle(g, (*warm, a), (rect.w // 2, rect.h // 2), i)
            _CACHE[key] = g
        surf.blit(_CACHE[key], rect.topleft)
    pygame.draw.rect(surf, rim if filled else SLOT_IN, rect, 2, border_radius=6)
    pygame.draw.rect(surf, WOOD_DK, rect.inflate(-4, -4), 1, border_radius=4)
    if selected or hover:
        pygame.draw.rect(surf, GOLD_HI if selected else GLOW, rect, 2, border_radius=6)


def count_chip(surf, rect, qty):
    f = font("title", 10)
    s = f"{qty:,}" if qty < 100000 else f"{qty // 1000}k"
    w = f.size(s)[0] + 8
    r = pygame.Rect(rect.right - w - 2, rect.bottom - 14, w, 12)
    pygame.draw.rect(surf, WOOD_DK, r, border_radius=4)
    pygame.draw.rect(surf, GOLD, r, 1, border_radius=4)
    text(surf, s, f, PULSE, (r.centerx, r.centery + 1), "center", shadow=False)


TIER_RARITY = (("mythos", "legendary"), ("crownforged", "legendary"), ("dragon", "epic"), ("eclipse", "epic"),
               ("rune", "epic"), ("adamant", "rare"), ("mithril", "uncommon"), ("steel", "uncommon"))


def rarity_of(item_id, item=None):
    r = (item or {}).get("rarity")
    if r in RARITY:
        return r
    iid = str(item_id or "")
    for k, v in TIER_RARITY:
        if iid.startswith(k + "_") or f"_{k}_" in iid:
            return v
    return "common"


def brighten_dark(img):
    """Auto-brighten very dark icons so black helmets / axes read on the dark slot."""
    try:
        import pygame.surfarray as sa
        avg = pygame.transform.average_color(img, None, True)
        lum = 0.3 * avg[0] + 0.59 * avg[1] + 0.11 * avg[2]
        if lum < 70:
            out = img.copy()
            add = int(min(60, (70 - lum) * 0.9))
            out.fill((add, add, add, 0), special_flags=pygame.BLEND_RGBA_ADD)
            return out
    except Exception:
        pass
    return img


# ---------------------------------------------------------------- world-chrome widgets (client.py hooks)
def teleport_button(client):
    """Arcane purple Teleport button with rune icon and T keycap (spec 3.4)."""
    rect = pygame.Rect(8, 322, 116, 34)
    surf = client.screen
    hover = rect.collidepoint(pygame.mouse.get_pos())
    glow(surf, rect, ARC_GLOW, 7, 120 if hover else 70, 7)
    button(surf, rect, "arcane", hover=hover)
    medallion(surf, rect.x + 19, rect.centery, 13, fill=_c("#1E0C34"))
    icon(surf, "rune", rect.x + 19, rect.centery, 9)
    text(surf, "Teleport", font("title", 12), ARC_TXT, (rect.x + 37, rect.centery + 1), "midleft")
    keycap(surf, (rect.right - 12, rect.centery), "T", small=True)
    return rect


def zoom_controls(client, panel, track):
    """Zoom frame + Area View button in wood / gold; bar fill uses the glossy bar."""
    import sys
    mod = sys.modules[type(client).__module__]
    zmin, zmax = mod.ZOOM_MIN, mod.ZOOM_MAX
    s = client.screen
    card(s, panel, 7)
    f = font("title", 11)
    text(s, "ZOOM", f, TITLE, (panel.x + 9, panel.y + 6))
    hint = client.font_tiny
    y2 = panel.y + 6 + client.font_tiny.get_height() + 2
    x = panel.x + 9
    for cap, words in (("[", "out"), ("]", "in")):
        r = keycap(s, (x + 7, y2 + 7), cap, small=True)
        x = r.right + 4
        lab = text(s, ("-  " if cap == "[" else "+  ") + "zoom " + words, hint, MUTED, (x, y2))
        x = lab.right + 10
    if getattr(client, "_area_view", False):
        shown = client._snap_zoom(getattr(client, "_zoom_before_area", mod.ZOOM_DEFAULT))
    else:
        shown = client._zoom_goal if getattr(client, "_zoom_drag", False) else client.zoom_pct
    t = (shown - zmin) / max(1, zmax - zmin)
    bar(s, track, t, "zoom", ticks=True)
    kx = track.x + int(round(track.w * t))
    knob = pygame.Rect(0, 0, 9, track.h + 6)
    knob.center = (kx, track.centery)
    button(s, knob, "primary", r=3)
    text(s, f"{client._zoom_ui_pct(shown)}%", client.font_tiny, ACTIVE_TXT,
         (track.right + 8, track.centery), "midleft")
    btn = client.area_view_button_rect()
    active = bool(getattr(client, "_area_view", False))
    hover = btn.collidepoint(pygame.mouse.get_pos())
    button(s, btn, "active" if active else "idle", inset=active, hover=hover)
    text(s, "Area View", font("title", 11), label_color("idle", active or hover), btn.center, "center")


def clock_widget(client, rect, phase, season, weather, date, weekday, phase_key):
    """Time-of-day plaque: carved frame, sun/moon medallion, Cinzel phase, body-font details."""
    s = client.screen
    frame = rect.inflate(6, 6)
    card(s, frame, 9, ornate=True)
    cx, cy = rect.x + 22, rect.y + 24
    medallion(s, cx, cy, 15, fill=_c("#141026") if phase_key == "night" else _c("#3A2A16"))
    if phase_key in ("night", "dusk"):
        icon(s, "moon", cx, cy, 8, col=_c("#141026") if phase_key == "night" else _c("#3A2A16"))
    else:
        icon(s, "sun", cx, cy, 8)
    text(s, phase, font("title", 15), GOLD_HI, (rect.x + 44, rect.y + 6))
    sub = fit(client.font_tiny, f"{season}  |  {weather}", rect.w - 52)
    text(s, sub, client.font_tiny, ACTIVE_TXT, (rect.x + 44, rect.y + 28))
    date_line = date if not weekday else f"{weekday}, {date}"
    if client.font_tiny.size(date_line)[0] > rect.w - 18:
        date_line = date
    pygame.draw.line(s, GOLD, (rect.x + 10, rect.y + 48), (rect.right - 10, rect.y + 48))
    diamond(s, rect.centerx, rect.y + 48, 3, GOLD_HI, WOOD_DK)
    text(s, fit(client.font_tiny, date_line, rect.w - 18), client.font_tiny, MUTED,
         (rect.centerx, rect.y + 62), "center")
