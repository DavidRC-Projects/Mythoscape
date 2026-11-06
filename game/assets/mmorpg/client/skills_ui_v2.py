"""Skills modal v2 — wood/gold carved window matching Equipment & Stats.

Drawn over the map. Keeps the old skills_scroll / skills_scroll_meta /
_kingdom_rect contracts so client.py input handling stays unchanged.
"""
from __future__ import annotations

import math
import os
import random
import time

import pygame

import combat
from content import XP_SKILLS, SKILL_DISPLAY_NAMES

# ---- palette (Equipment / Sidebars v2) ----
WOOD = (42, 30, 20)
WOOD_DK = (18, 12, 8)
WOOD_HI = (90, 70, 48)
WINDOW_BG = (26, 20, 14)
PANEL = (43, 34, 25)
PANEL_RIM = (90, 70, 48)
GOLD = (179, 148, 101)
GOLD_HI = (230, 203, 142)
TITLE_GOLD = (206, 174, 115)
PLAQUE = (28, 21, 15)
ROW_A = (36, 28, 21)
ROW_B = (31, 24, 18)
ROW_BOOST_A = (40, 48, 28)
ROW_BOOST_B = (34, 42, 24)
TEXT = (234, 219, 192)
MUTED = (168, 154, 132)
INK = (43, 33, 24)
BOOST = (110, 255, 130)
BOOST_TAG = (255, 200, 90)
XP_TOP = (255, 211, 107)
XP_BOT = (122, 84, 24)
TRACK = (40, 30, 20)
THUMB = (179, 148, 101)
THUMB_HI = (230, 203, 142)

WIN_W, WIN_H = 680, 560
MAP_W, MAP_H = 900, 640

_FONTS = {}
_ART = {}
_FONT_DIR = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", "assets", "fonts"))


def _opaque(w, h):
    """RGB surface with no alpha mask — avoids solid-bar text on macOS/pygame 2.6."""
    return pygame.Surface((max(1, int(w)), max(1, int(h))), 0, 32, (0xFF0000, 0x00FF00, 0x0000FF, 0))


def _font(kind, size):
    """Title = Cinzel; body/numbers = Arial via Font(path) for readable digits."""
    key = (kind, size)
    if key in _FONTS:
        return _FONTS[key]
    f = None
    if kind == "title":
        path = os.path.join(_FONT_DIR, "Cinzel.ttf")
        try:
            f = pygame.font.Font(path, size)
            f.set_bold(True)
            f.render("Ag", True, (255, 255, 255))
        except Exception:
            f = None
    if f is None:
        path = pygame.font.match_font("arial,helvetica,segoe ui,dejavu sans")
        try:
            f = pygame.font.Font(path, size) if path else pygame.font.Font(None, size + 2)
            if kind == "title":
                f.set_bold(True)
        except Exception:
            f = pygame.font.Font(None, size + 2)
    _FONTS[key] = f
    return f


def _text(surf, txt, f, col, pos, shadow=True, anchor="topleft"):
    img = f.render(str(txt), True, col)
    r = img.get_rect(**{anchor: pos})
    if shadow:
        surf.blit(f.render(str(txt), True, (0, 0, 0)), r.move(1, 1))
    surf.blit(img, r)
    return r


def _grain(w, h, base, seed=7):
    key = ("grain", w, h, base, seed)
    if key in _ART:
        return _ART[key]
    s = _opaque(w, h)
    s.fill(base)
    rng = random.Random(seed + w * 7 + h)
    for _ in range(max(2, h // 5)):
        y0 = rng.uniform(0, h)
        amp = rng.uniform(0.4, 1.6)
        freq = rng.uniform(0.01, 0.035)
        ph = rng.uniform(0, 6.3)
        dark = rng.random() < 0.55
        t = (rng.randint(8, 20)) / 255.0
        if dark:
            col = tuple(max(0, int(c * (1 - t))) for c in base)
        else:
            hi = (255, 220, 170)
            col = tuple(min(255, int(c * (1 - t / 2) + hi[i] * (t / 2))) for i, c in enumerate(base))
        pts = [(x, y0 + amp * math.sin(x * freq + ph)) for x in range(0, w + 6, 6)]
        if len(pts) > 1:
            pygame.draw.lines(s, col, False, pts, 1)
    for _ in range(max(4, w * h // 90)):
        x, y = rng.randrange(max(1, w)), rng.randrange(max(1, h))
        n = rng.randint(-5, 5)
        c = s.get_at((x, y))
        s.set_at((x, y), (max(0, min(255, c[0] + n)), max(0, min(255, c[1] + n)), max(0, min(255, c[2] + n))))
    _ART[key] = s
    return s


def _diamond(surf, cx, cy, r, col):
    pygame.draw.polygon(surf, col, [(cx, cy - r), (cx + r, cy), (cx, cy + r), (cx - r, cy)])


def _filigree(surf, cx, cy, fx, fy, size=56):
    def P(x, y):
        return (int(cx + fx * x), int(cy + fy * y))
    for col, off in ((WOOD_DK, 1), (GOLD, 0)):
        o = off
        pygame.draw.lines(surf, col, False, [P(4 + o, size + o), P(4 + o, 4 + o), P(size + o, 4 + o)], 2)
        pygame.draw.lines(
            surf, col, False,
            [P(10 + o, size * 0.65 + o), P(10 + o, 10 + o), P(size * 0.65 + o, 10 + o)], 1,
        )
    pygame.draw.circle(surf, GOLD_HI, P(18, 18), 2)


def _plaque(surf, rect, rim=GOLD, fill=PLAQUE, radius=4):
    pygame.draw.rect(surf, (0, 0, 0), rect.move(0, 2), border_radius=radius)
    pygame.draw.rect(surf, fill, rect, border_radius=radius)
    pygame.draw.rect(surf, rim, rect, 1, border_radius=radius)
    pygame.draw.rect(surf, (rim[0] // 3, rim[1] // 3, rim[2] // 3), rect.inflate(-4, -4), 1, border_radius=radius)


def _chip(surf, rect, label, value):
    _plaque(surf, rect, rim=GOLD_HI)
    _text(surf, label, _font("body", 11), MUTED, (rect.x + 10, rect.centery), anchor="midleft", shadow=False)
    _text(surf, str(value), _font("body", 16), TITLE_GOLD, (rect.right - 12, rect.centery),
          anchor="midright", shadow=True)


def _xp_bar(surf, rect, pct):
    """Opaque gold XP trough — no SRCALPHA overlays."""
    pct = max(0.0, min(1.0, pct))
    pygame.draw.rect(surf, WOOD_DK, rect.inflate(2, 2), border_radius=4)
    pygame.draw.rect(surf, TRACK, rect, border_radius=3)
    fw = int(rect.w * pct)
    if fw > 1:
        fill = pygame.Rect(rect.x, rect.y, fw, rect.h)
        for i in range(fill.h):
            u = i / max(1, fill.h - 1)
            col = (
                int(XP_BOT[0] + (XP_TOP[0] - XP_BOT[0]) * (1 - abs(u - 0.35))),
                int(XP_BOT[1] + (XP_TOP[1] - XP_BOT[1]) * (1 - abs(u - 0.35))),
                int(XP_BOT[2] + (XP_TOP[2] - XP_BOT[2]) * (1 - abs(u - 0.35))),
            )
            pygame.draw.line(surf, col, (fill.x, fill.y + i), (fill.right - 1, fill.y + i))
        pygame.draw.line(surf, GOLD_HI, (fill.x + 1, fill.y + 1), (fill.right - 2, fill.y + 1))
    pygame.draw.rect(surf, GOLD, rect, 1, border_radius=3)


def _draw_frame(c, w, h):
    c.blit(_grain(w, h, WINDOW_BG, 11), (0, 0))
    r = c.get_rect()
    pygame.draw.rect(c, WOOD, r, 6)
    pygame.draw.rect(c, WOOD_HI, r.inflate(-2, -2), 1)
    pygame.draw.rect(c, WOOD_DK, r.inflate(-10, -10), 2)
    pygame.draw.rect(c, GOLD, r.inflate(-14, -14), 1)
    for x, y, fx, fy in ((2, 2, 1, 1), (w - 3, 2, -1, 1), (2, h - 3, 1, -1), (w - 3, h - 3, -1, -1)):
        _filigree(c, x, y, fx, fy)
    cx = w // 2
    _diamond(c, cx, 7, 7, WOOD_DK)
    _diamond(c, cx, 7, 5, GOLD)
    _diamond(c, cx, 7, 2, GOLD_HI)


def _window_origin(client):
    """Center over the map viewport when possible."""
    try:
        sw = int(getattr(client, "screen").get_width())
        # Prefer map area (left 900×640); fall back to full screen centre.
        ox = max(8, (MAP_W - WIN_W) // 2)
        oy = max(8, (MAP_H - WIN_H) // 2)
        if sw < MAP_W:
            ox = max(8, (sw - WIN_W) // 2)
        return ox, oy
    except Exception:
        return 110, 40


def draw(client):
    """Draw the Skills modal onto client.screen."""
    screen = client.screen
    ox, oy = _window_origin(client)

    # Soft dim over the world (map + a touch of the sidebar).
    dim = pygame.Surface(screen.get_size(), pygame.SRCALPHA)
    dim.fill((8, 6, 10, 150))
    screen.blit(dim, (0, 0))

    canvas = getattr(client, "_skills_canvas", None)
    if canvas is None or canvas.get_size() != (WIN_W, WIN_H):
        canvas = _opaque(WIN_W, WIN_H)
        client._skills_canvas = canvas
    canvas.fill(WINDOW_BG)
    _draw_frame(canvas, WIN_W, WIN_H)

    # Title plaque
    title_r = pygame.Rect(WIN_W // 2 - 90, 16, 180, 36)
    _plaque(canvas, title_r, rim=GOLD_HI)
    _text(canvas, "SKILLS", _font("title", 22), TITLE_GOLD, (title_r.centerx, title_r.centery + 1),
          anchor="center")
    for sx in (title_r.x + 12, title_r.right - 12):
        _diamond(canvas, sx, title_r.centery, 4, GOLD)

    # Combat / Total chips
    cmb = client.player_combat_level()
    tot = client.player_total_level()
    _chip(canvas, pygame.Rect(24, 60, 150, 32), "Combat", cmb)
    _chip(canvas, pygame.Rect(184, 60, 150, 32), "Total", tot)

    # Standing / work / property (right meta)
    p = client.player or {}
    standing = f"Standing: {p.get('rep_tier', 'Neutral')} ({int(p.get('reputation') or 0)})"
    _text(canvas, standing, _font("body", 12), (185, 166, 232),
          (WIN_W - 24, 64), anchor="topright", shadow=False)

    work = p.get("work") or {}
    job, prop = work.get("job"), work.get("property")
    meta_lines = [
        (f"Work: {job['workplace']} {job['today']}/{job['cap']} today · wages {job['last_wages']}"
         if job else "Work: none"),
        (f"Property: {prop['kind']} {prop['workers']}/{prop['slots']} · {prop['fee']}/day"
         f" · +{prop['last_income']}" if prop else "Property: none"),
    ]
    wy = 82
    for line in meta_lines:
        _text(canvas, line, _font("body", 11), (170, 190, 150),
              (WIN_W - 24, wy), anchor="topright", shadow=False)
        wy += 14

    # Kingdom + hint
    client._kingdom_rect = None
    if p.get("kingdom"):
        ktxt = str(p["kingdom"]) + "  (click for details)"
        kr = _text(canvas, ktxt, _font("body", 11), (185, 166, 232),
                   (24, 98), anchor="topleft", shadow=False)
        # Screen-space hit target for kingdom details.
        client._kingdom_rect = kr.move(ox, oy)
    _text(canvas, "Scroll wheel / Up-Down / drag bar  ·  Esc / Tab closes",
          _font("body", 11), MUTED, (24, 114), anchor="topleft", shadow=False)

    # Column headers
    header_y = 136
    headers = [("Skill", 40), ("Level", 188), ("XP", 260), ("XP for level", 360), ("To next", 500)]
    for label, x in headers:
        _text(canvas, label, _font("body", 12), GOLD, (x, header_y), shadow=False)
    pygame.draw.line(canvas, GOLD, (24, header_y + 20), (WIN_W - 24, header_y + 20), 1)
    pygame.draw.line(canvas, WOOD_DK, (24, header_y + 21), (WIN_W - 24, header_y + 21), 1)

    # Scrollable list
    levels = p.get("levels") or {}
    xp_map = p.get("xp") or {}
    pot = p.get("stat_boosts") or {}
    row_h = 42
    skill_rows = ["hitpoints"] + list(XP_SKILLS)
    n_skills = len(skill_rows)
    list_top_local = header_y + 26
    list_bottom_local = WIN_H - 40
    view_h = max(40, list_bottom_local - list_top_local)
    content_h = n_skills * row_h
    max_scroll = max(0, content_h - view_h)
    client.skills_scroll = max(0, min(float(getattr(client, "skills_scroll", 0) or 0), max_scroll))

    list_top = oy + list_top_local
    client.skills_scroll_meta = {
        "list_top": list_top,
        "view_h": view_h,
        "max_scroll": max_scroll,
        "track": pygame.Rect(ox + WIN_W - 22, list_top, 10, view_h),
    }

    # Clip on canvas for the row list
    prev_clip = canvas.get_clip()
    canvas.set_clip(pygame.Rect(20, list_top_local, WIN_W - 44, view_h))

    y = list_top_local - client.skills_scroll
    for i, skill in enumerate(skill_rows):
        row_top = y
        y += row_h
        if row_top + row_h < list_top_local or row_top > list_bottom_local:
            continue
        row = pygame.Rect(24, int(row_top), WIN_W - 52, row_h - 4)

        if skill == "hitpoints":
            lvl = int(p.get("max_hp") or 1)
            hp_now = int(p.get("hp") or 0)
            tone, _pct = client.hp_tone(hp_now, lvl)
            canvas.blit(_grain(row.w, row.h, ROW_A if i % 2 == 0 else ROW_B, 20 + i), row.topleft)
            pygame.draw.rect(canvas, PANEL_RIM, row, 1, border_radius=5)
            _text(canvas, "Hitpoints", _font("body", 15), TEXT, (row.x + 10, row.y + 10), shadow=False)
            _text(canvas, str(lvl), _font("body", 15), tone, (row.x + 160, row.y + 10), shadow=False)
            _text(canvas, f"{hp_now}/{lvl}", _font("body", 13), tone, (row.x + 232, row.y + 12), shadow=False)
            _text(canvas, "—", _font("body", 13), MUTED, (row.x + 340, row.y + 12), shadow=False)
            _text(canvas, "—", _font("body", 13), MUTED, (row.x + 480, row.y + 12), shadow=False)
            continue

        lvl = int(levels.get(skill, 1))
        boost = 0
        buff = pot.get(skill) if skill in ("attack", "strength", "defence") else None
        if buff:
            boost = int(buff.get("amount") or 0)
            until = float(buff.get("until") or 0)
            if until and until <= time.time():
                boost = 0
        eff = lvl + boost
        xp = int(xp_map.get(skill, 0))
        to_next = combat.xp_to_next_level(xp)
        xp_at_level = combat.xp_for_level(lvl)
        name = SKILL_DISPLAY_NAMES.get(skill, skill.title())

        if boost > 0:
            base = ROW_BOOST_A if i % 2 == 0 else ROW_BOOST_B
        else:
            base = ROW_A if i % 2 == 0 else ROW_B
        canvas.blit(_grain(row.w, row.h, base, 30 + i), row.topleft)
        pygame.draw.rect(canvas, GOLD if boost else PANEL_RIM, row, 1, border_radius=5)

        if to_next > 0:
            next_thresh = combat.xp_for_level(lvl + 1)
            span = max(1, next_thresh - xp_at_level)
            done = max(0.0, min(1.0, (xp - xp_at_level) / span))
        else:
            done = 1.0
        _xp_bar(canvas, pygame.Rect(row.x + 232, row.y + 26, 110, 7), done)

        _text(canvas, name, _font("body", 15), TEXT, (row.x + 10, row.y + 8), shadow=False)
        if boost > 0:
            _text(canvas, str(eff), _font("body", 15), BOOST, (row.x + 160, row.y + 8), shadow=False)
            _text(canvas, f"+{boost}", _font("body", 11), BOOST_TAG, (row.x + 192, row.y + 11), shadow=False)
        else:
            _text(canvas, str(lvl), _font("body", 15), TEXT, (row.x + 160, row.y + 8), shadow=False)
        _text(canvas, f"{xp:,}", _font("body", 13), TITLE_GOLD, (row.x + 232, row.y + 4), shadow=False)
        _text(canvas, f"{xp_at_level:,}", _font("body", 13), MUTED, (row.x + 340, row.y + 10), shadow=False)
        next_txt = "MAX" if to_next <= 0 else f"{to_next:,}"
        _text(canvas, next_txt, _font("body", 13), MUTED, (row.x + 480, row.y + 10), shadow=False)

    canvas.set_clip(prev_clip)

    # Scrollbar (screen-space track already stored)
    if max_scroll > 0:
        track_local = pygame.Rect(WIN_W - 22, list_top_local, 10, view_h)
        pygame.draw.rect(canvas, TRACK, track_local, border_radius=4)
        pygame.draw.rect(canvas, WOOD_DK, track_local, 1, border_radius=4)
        thumb_h = max(28, int(view_h * view_h / content_h))
        thumb_y = list_top_local + int((view_h - thumb_h) * client.skills_scroll / max_scroll)
        thumb_local = pygame.Rect(track_local.x, thumb_y, track_local.w, thumb_h)
        pygame.draw.rect(canvas, THUMB, thumb_local, border_radius=4)
        pygame.draw.rect(canvas, THUMB_HI, thumb_local, 1, border_radius=4)
        client.skills_scroll_meta["thumb"] = thumb_local.move(ox, oy)
    else:
        client.skills_scroll_meta["thumb"] = None

    # Footer tip
    foot = pygame.Rect(24, WIN_H - 32, WIN_W - 48, 22)
    _plaque(canvas, foot, rim=GOLD, fill=PLAQUE, radius=3)
    _text(
        canvas,
        "Green levels are potion boosts (temporary).  Combat = Att/Str/Def/HP + Archery.",
        _font("body", 11), MUTED, (foot.centerx, foot.centery + 1),
        anchor="center", shadow=False,
    )

    # Drop shadow + blit
    shadow = pygame.Surface((WIN_W + 24, WIN_H + 24), pygame.SRCALPHA)
    for i in range(12):
        pygame.draw.rect(shadow, (0, 0, 0, 10), shadow.get_rect().inflate(-i * 2, -i * 2), border_radius=10)
    screen.blit(shadow, (ox - 10, oy - 4))
    screen.blit(canvas, (ox, oy))
