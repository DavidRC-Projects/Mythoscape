"""Crownfall Arena barracks — painted restyle (matches Equipment / Stats / Teleport).

Drawn by mercenaries_ui.draw(); any exception falls back to the legacy board there.
Click handling stays in mercenaries_ui.click(): this module fills client.barracks_rects
with the same keys the legacy board used, plus duel:/confirm_* keys.
"""
from __future__ import annotations

import os

import pygame

import equipment_ui_v2 as E
import teleport_ui as T

# Palette (ARENA_UI_STYLE_SPEC.md)
FRAME = (42, 30, 20)
PANEL = (43, 34, 25)
CELL = (40, 31, 24)
CELL_HOT = (52, 40, 30)
PLAQUE = (28, 21, 15)
GOLD = (179, 148, 101)
GOLD_HI = (230, 203, 142)
TITLE = (206, 174, 115)
GLOW = (242, 193, 78)
GLOW2 = (255, 211, 107)
TEXT = (234, 219, 192)
MUTED = (168, 154, 132)
BRONZE = (140, 90, 43)
GAIN = (63, 125, 58)
AMBER = (217, 150, 46)
LOSS = (158, 43, 37)
LILAC = (185, 166, 232)
SAND = (201, 163, 107)
METAL = {
    "bronze": (140, 90, 43), "iron": (138, 143, 150), "steel": (184, 194, 204),
    "mithril": (127, 167, 201), "adamant": (94, 140, 106), "mythos": LILAC,
}
ART_TIER = {"mythos": "crownforged"}

TABS = (("roster", "Roster"), ("formation", "Formation"), ("recruit", "Recruit"), ("practice", "Practice"),
        ("champions", "Champions"), ("ladder", "Ladder"))

# Portrait geometry (spec HARD RULE: art clipped in frame, >= 8px headroom)
CHAMP_FRAME, CHAMP_INNER = 96, 88
BUST_FRAME, BUST_INNER = 72, 64
NICHE = (248, 312)
NICHE_INNER = (240, 304)
HEADROOM = 8
ACTION_W = 140

_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets", "ui", "arena")
_ART = {}
_CACHE = {}


# ------------------------------------------------------------------ helpers
def fight_label(army_cl, foe_cl):
    """(label, colour) from army CL vs foe CL. Border and pill always share the colour."""
    army, foe = int(army_cl or 0), max(1, int(foe_cl or 0))
    ratio = army / foe
    if army > 0 and ratio >= 1.15:
        return "You should win", GAIN
    if army > 0 and ratio >= 0.85:
        return "Risky — close fight", AMBER
    return "Likely loss", LOSS


def window_rect(sw, sh):
    w, h = min(1000, sw - 24), min(760, sh - 32)
    r = pygame.Rect(0, 0, w, h)
    r.center = (sw // 2, sh // 2)
    return r


def _art(name):
    if name not in _ART:
        try:
            _ART[name] = pygame.image.load(os.path.join(_DIR, f"{name}.png")).convert_alpha()
        except Exception as e:
            E._log_once(f"arena art {name}", e)
            _ART[name] = None
    return _ART[name]


def _scaled(name, size, grey=False):
    k = (name, size, grey)
    if k not in _CACHE:
        img = _art(name)
        if img is not None:
            img = pygame.transform.smoothscale(img, size)
            if grey:
                g = img.copy()
                px = pygame.surfarray.pixels3d(g)
                lum = (px[..., 0] * 0.3 + px[..., 1] * 0.59 + px[..., 2] * 0.11) * 0.6
                px[..., 0] = lum; px[..., 1] = lum; px[..., 2] = lum
                del px
                img = g
        _CACHE[k] = img
    return _CACHE[k]


def _tier_art(tier):
    t = tier if tier in METAL else "bronze"
    return ART_TIER.get(t, t)


def _f(kind, size):
    return E.font(kind, size)


def _txt(s, text, kind, size, col, pos, anchor="topleft", maxw=None):
    f = _f(kind, size)
    text = str(text)
    if maxw:
        if f.size(text)[0] > maxw:
            while len(text) > 1 and f.size(text + "…")[0] > maxw:
                text = text[:-1]
            text = text.rstrip(" ·,") + "…"
    t = f.render(text, True, col)
    r = t.get_rect(**{anchor: pos})
    s.blit(t, r)
    return r


def _wrap(text, f, maxw):
    words, lines, cur = str(text).split(), [], ""
    for w in words:
        nxt = (cur + " " + w).strip()
        if f.size(nxt)[0] <= maxw or not cur:
            cur = nxt
        else:
            lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    return lines


def _arrow(s, x, cy, col, w=14):
    pygame.draw.line(s, col, (x, cy), (x + w - 4, cy), 2)
    pygame.draw.polygon(s, col, [(x + w, cy), (x + w - 6, cy - 4), (x + w - 6, cy + 4)])


def _check(s, x, cy, col, size=12):
    pts = [(x, cy), (x + size * 0.38, cy + size * 0.4), (x + size, cy - size * 0.5)]
    pygame.draw.lines(s, col, False, pts, 3)


def _coin(s, cx, cy, r=7):
    pygame.draw.circle(s, (120, 84, 30), (cx, cy), r)
    pygame.draw.circle(s, (226, 182, 82), (cx, cy), r - 1)
    pygame.draw.circle(s, (176, 130, 50), (cx, cy), r - 3, 1)
    pygame.draw.line(s, (255, 236, 170), (cx - 2, cy - r + 3), (cx - r + 3, cy - 2), 1)


def _padlock(s, x, y, col=(200, 186, 160), scale=1.0):
    w, h = int(14 * scale), int(10 * scale)
    pygame.draw.arc(s, col, pygame.Rect(x + int(2 * scale), y, w - int(4 * scale), int(12 * scale)), 0, 3.1416, max(2, int(2 * scale)))
    body = pygame.Rect(x, y + int(6 * scale), w, h)
    pygame.draw.rect(s, (96, 86, 72), body, border_radius=2)
    pygame.draw.rect(s, col, body, 1, border_radius=2)
    pygame.draw.circle(s, (30, 24, 18), (body.centerx, body.centery - 1), max(1, int(2 * scale)))


def _cell(s, rect, rim=None, fill=CELL, width=1, radius=6):
    pygame.draw.rect(s, fill, rect, border_radius=radius)
    pygame.draw.rect(s, (22, 16, 11), rect.inflate(-2, -2), 1, border_radius=radius)
    pygame.draw.rect(s, rim or (70, 55, 38), rect, width, border_radius=radius)


def _glow(s, rect, col=GLOW2):
    g = pygame.Surface((rect.w + 16, rect.h + 16), pygame.SRCALPHA)
    for i in range(4):
        pygame.draw.rect(g, (*col, 28), g.get_rect().inflate(-i * 4, -i * 4), 2, border_radius=10)
    s.blit(g, (rect.x - 8, rect.y - 8))
    pygame.draw.rect(s, col, rect, 2, border_radius=6)


def _grad(s, rect, top, bot):
    for i in range(rect.h):
        u = i / max(1, rect.h - 1)
        c = tuple(int(top[k] + (bot[k] - top[k]) * u) for k in range(3))
        pygame.draw.line(s, c, (rect.x + 2, rect.y + i), (rect.right - 3, rect.y + i))


BTN_STYLES = {
    "bronze": ((150, 98, 48), (92, 60, 30), GOLD, (243, 230, 207)),
    "green": ((70, 120, 60), (38, 74, 34), (190, 200, 120), (226, 240, 200)),
    "red": ((130, 44, 36), (78, 24, 20), (196, 110, 90), (246, 222, 210)),
    "steel": ((44, 58, 80), (26, 34, 50), (120, 160, 210), (210, 226, 250)),
    "dark": ((48, 38, 28), (32, 25, 18), (110, 92, 66), TEXT),
    "off": ((40, 34, 28), (30, 25, 20), (80, 68, 52), (120, 110, 96)),
}


def button(s, rects, key, rect, label, style="bronze", hot=False, size=16, outline=False, icon=None):
    top, bot, rim, fg = BTN_STYLES[style]
    if outline:
        pygame.draw.rect(s, (30, 23, 16), rect, border_radius=4)
        if hot:
            pygame.draw.rect(s, (44, 34, 24), rect, border_radius=4)
        pygame.draw.rect(s, GLOW2 if hot else GOLD, rect, 1, border_radius=4)
        fg = GOLD_HI
    else:
        _grad(s, rect, tuple(min(255, v + (18 if hot else 0)) for v in top), bot)
        pygame.draw.rect(s, GLOW2 if hot and style != "off" else rim, rect, 1, border_radius=4)
        pygame.draw.line(s, tuple(min(255, v + 40) for v in top), (rect.x + 4, rect.y + 1), (rect.right - 5, rect.y + 1))
    f = _f("title", size)
    t = f.render(label, True, fg)
    extra = 18 if icon else 0
    x = rect.centerx - (t.get_width() + extra) // 2
    if icon == "lock":
        _padlock(s, x, rect.centery - 9, fg)
    s.blit(t, (x + extra, rect.centery - t.get_height() // 2 - 1))
    if rects is not None and key:
        rects[key] = rect
    return rect


def _round_frame(s, center, outer, inner, art=None, rim=GOLD, grey=False, record=None):
    """Gold ring frame; art (surface, sized so its top sits inside with headroom) clipped to the inner circle."""
    cx, cy = center
    pygame.draw.circle(s, (18, 13, 9), center, outer // 2 + 2)
    pygame.draw.circle(s, rim, center, outer // 2)
    pygame.draw.circle(s, (70, 52, 30), center, outer // 2 - 2, 1)
    pygame.draw.circle(s, (24, 18, 13), center, inner // 2)
    if art is not None:
        disc = pygame.Surface((inner, inner), pygame.SRCALPHA)
        disc.blit(art, (0, 0))
        mask = pygame.Surface((inner, inner), pygame.SRCALPHA)
        pygame.draw.circle(mask, (255, 255, 255, 255), (inner // 2, inner // 2), inner // 2)
        disc.blit(mask, (0, 0), special_flags=pygame.BLEND_RGBA_MIN)
        if grey:
            disc.fill((120, 120, 120, 255), special_flags=pygame.BLEND_RGBA_MULT)
        s.blit(disc, (cx - inner // 2, cy - inner // 2))
        if record is not None:
            bb = art.get_bounding_rect(min_alpha=60).move(cx - inner // 2, cy - inner // 2)
            record.append({"kind": "bust", "inner": pygame.Rect(cx - inner // 2, cy - inner // 2, inner, inner), "art": bb})
    pygame.draw.circle(s, (230, 203, 142), center, inner // 2 + 1, 1)


def _bust_surface(tier, inner):
    """Painted bust for a kit tier sized to the inner circle with >= HEADROOM px above the helmet."""
    k = ("bust", tier, inner)
    if k in _CACHE:
        return _CACHE[k]
    img = _art(f"bust_{_tier_art(tier)}")
    out = None
    if img is not None:
        sc = pygame.transform.smoothscale(img, (inner, inner))
        bb = sc.get_bounding_rect(min_alpha=60)
        out = pygame.Surface((inner, inner), pygame.SRCALPHA)
        dy = max(0, HEADROOM + 2 - bb.top)
        out.blit(sc, (0, dy))
    _CACHE[k] = out
    return out


def _champ_surface(boss_id, inner):
    """Head-to-waist crop of the HD champion sheet, headroom 10px, clipped to the inner square."""
    k = ("champ", boss_id, inner)
    if k in _CACHE:
        return _CACHE[k]
    out = None
    try:
        import arena_battles_ui as AB
        got = AB.boss_surface(boss_id, "s", 80)
        if got:
            img = got[0]
            bb = img.get_bounding_rect(min_alpha=60)
            if bb.h:
                fig = img.subsurface(bb).copy()
                want_h = inner * 2.0            # full figure scaled so head..waist fills the frame
                sc = want_h / fig.get_height()
                fig = pygame.transform.smoothscale(fig, (max(1, int(fig.get_width() * sc)), max(1, int(want_h))))
                # centre on the head: columns used by the top 10% of the figure
                top_band = fig.subsurface((0, 0, fig.get_width(), max(1, int(fig.get_height() * 0.1))))
                hb = top_band.get_bounding_rect(min_alpha=60)
                hx = hb.centerx if hb.w else fig.get_width() // 2
                out = pygame.Surface((inner, inner), pygame.SRCALPHA)
                out.blit(fig, (inner // 2 - hx, 10))
    except Exception as e:
        E._log_once(f"champ portrait {boss_id}", e)
    _CACHE[k] = out
    return out


def _square_frame(s, rect, inner_size, art, rim=GOLD, grey=False, record=None, kind="champ"):
    pygame.draw.rect(s, (18, 13, 9), rect.inflate(4, 4), border_radius=4)
    pygame.draw.rect(s, rim, rect, border_radius=4)
    inner = pygame.Rect(0, 0, inner_size[0], inner_size[1])
    inner.center = rect.center
    pygame.draw.rect(s, (22, 17, 12), inner)
    if art is not None:
        prev = s.get_clip()
        s.set_clip(inner.clip(prev) if prev else inner)
        a = art
        if grey:
            a = art.copy()
            a.fill((110, 110, 110, 255), special_flags=pygame.BLEND_RGBA_MULT)
        s.blit(a, inner.topleft)
        s.set_clip(prev)
        if record is not None:
            record.append({"kind": kind, "inner": inner.copy(),
                           "art": art.get_bounding_rect(min_alpha=60).move(inner.topleft)})
    pygame.draw.rect(s, (230, 203, 142), inner.inflate(2, 2), 1)
    for x, y in (rect.topleft, (rect.right - 1, rect.y), (rect.x, rect.bottom - 1), (rect.right - 1, rect.bottom - 1)):
        T._diamond(s, x, y, 4, GOLD_HI)
    return inner


def _medallion(s, center, text, rim=GOLD, crown=False, dim=False):
    cx, cy = center
    pygame.draw.circle(s, (16, 12, 8), center, 25)
    pygame.draw.circle(s, rim if not dim else (100, 88, 70), center, 23)
    pygame.draw.circle(s, (34, 26, 19), center, 19)
    pygame.draw.circle(s, GOLD_HI if not dim else (120, 108, 88), center, 19, 1)
    for a in range(4):
        dx, dy = ((0, -1), (1, 0), (0, 1), (-1, 0))[a]
        T._diamond(s, cx + dx * 23, cy + dy * 23, 3, GOLD_HI if not dim else (120, 108, 88))
    if crown:
        pts = [(cx - 11, cy + 6), (cx - 11, cy - 5), (cx - 5, cy + 0), (cx, cy - 9), (cx + 5, cy + 0),
               (cx + 11, cy - 5), (cx + 11, cy + 6)]
        pygame.draw.polygon(s, GLOW2, pts)
        pygame.draw.polygon(s, (120, 84, 30), pts, 1)
    else:
        _txt(s, text, "title", 17, TEXT if not dim else MUTED, center, "center")


def _banner(s, x, y, h, tier, col, dim=False):
    w = 40
    pygame.draw.line(s, GOLD, (x - 3, y), (x + w + 3, y), 3)
    pts = [(x, y + 2), (x + w, y + 2), (x + w, y + h - 12), (x + w // 2, y + h), (x, y + h - 12)]
    c = col if not dim else tuple(int(v * 0.55) for v in col)
    pygame.draw.polygon(s, c, pts)
    pygame.draw.polygon(s, GOLD if not dim else (110, 96, 74), pts, 2)
    pygame.draw.line(s, tuple(min(255, v + 30) for v in c), (x + 5, y + 6), (x + 5, y + h - 16), 1)
    _txt(s, f"T{tier}", "title", 16, TEXT if not dim else MUTED, (x + w // 2, y + h // 2 - 4), "center")


BANNER_COL = {1: (36, 48, 88), 2: (36, 48, 88), 3: (36, 48, 88), 4: (120, 34, 28), 5: (40, 44, 56), 6: (176, 128, 40)}


# ------------------------------------------------------------------ header
def _stat_chip(s, rect, label, value):
    _cell(s, rect, (96, 76, 50), PLAQUE)
    _txt(s, label, "body", 14, MUTED, (rect.centerx, rect.y + 3), "midtop")
    _txt(s, value, "title", 17, GOLD_HI, (rect.centerx, rect.bottom - 3), "midbottom")


def _draw_header(client, s, box, data, rects, mouse, tab):
    # title plaque
    narrow = box.w < 720
    f = _f("title", 19 if narrow else 26)
    t = f.render("Crownfall Arena · Barracks", True, TITLE)
    pr = pygame.Rect(0, 0, t.get_width() + 64, 44)
    pr.midtop = (box.centerx, box.y + 14)
    pygame.draw.rect(s, PLAQUE, pr, border_radius=4)
    pygame.draw.rect(s, GOLD, pr, 1, border_radius=4)
    pygame.draw.rect(s, (60, 46, 32), pr.inflate(-6, -6), 1, border_radius=3)
    for side in (-1, 1):
        x = pr.left if side < 0 else pr.right
        T._diamond(s, x, pr.centery, 7, GOLD)
        T._diamond(s, x, pr.centery, 3, PLAQUE)
    s.blit(t, (pr.centerx - t.get_width() // 2, pr.centery - t.get_height() // 2 - 1))
    # Close: own top-right corner, 90x34 bronze
    cr = pygame.Rect(box.right - 24 - 90, box.y + 18, 90, 34)
    button(s, rects, "close", cr, "Close", "bronze", cr.collidepoint(mouse))
    # House crest, top-left corner (clear of title + Close)
    house = data.get("personal_house") or {}
    if house.get("name") and narrow:
        br = pygame.Rect(box.x + 24, box.y + 16, 30, 38)
        try:
            import mercenaries_ui
            mercenaries_ui.draw_house_banner(s, house.get("banner"), br)
        except Exception as e:
            E._log_once("arena house banner", e)
        rects["house_banner"] = br
        rects["customize_banner"] = br
    elif house.get("name"):
        br = pygame.Rect(box.x + 26, box.y + 14, 34, 42)
        try:
            import mercenaries_ui
            mercenaries_ui.draw_house_banner(s, house.get("banner"), br)
        except Exception as e:
            E._log_once("arena house banner", e)
        rects["house_banner"] = br
        maxw = pr.left - br.right - 22
        _txt(s, house["name"], "title", 14, GOLD_HI, (br.right + 8, br.y), maxw=maxw)
        cb = pygame.Rect(br.right + 8, br.y + 20, min(132, maxw), 22)
        button(s, rects, "customize_banner", cb, "Customise banner", "dark", cb.collidepoint(mouse), size=12)
    y = box.y + 66
    cmd = int(data.get("command_level") or 1)
    total = int(data.get("roster_total_cl") or 0)
    purse = int(data.get("coins") or 0)
    bank = int(data.get("bank_coins") or 0)
    daily = data.get("daily_fights") or {}
    if tab == "roster":
        fights = f"{daily.get('used', 0)}/{daily.get('cap', 10)}" if daily else "—"
        chips = (("Command", str(cmd)), ("Army CL", f"{total:,}"), ("Purse", f"{purse:,}"),
                 ("Bank", f"{bank:,}"), ("Fights", fights))
        gap = 10
        cw = min(150, (box.w - 60 - gap * 4) // 5)
        x = box.centerx - (cw * 5 + gap * 4) // 2
        for label, val in chips:
            _stat_chip(s, pygame.Rect(x, y, cw, 44), label, val)
            x += cw + gap
        y += 52
        y = _draw_next_unlock(client, s, box, data, rects, mouse, y)
    else:
        r1 = _txt(s, f"Army CL {total:,}", "body", 18, TEXT, (box.centerx - 14, y + 2), "topright")
        _txt(s, f"Bank {bank:,}", "body", 18, TEXT, (box.centerx + 14, y + 2), "topleft")
        T._diamond(s, box.centerx, r1.centery, 4, GOLD)
        y += 30
    # tabs — exactly one active
    gap = 8 if not narrow else 4
    tw = min(150, (box.w - 48 - gap * (len(TABS) - 1)) // len(TABS))
    x = box.centerx - (tw * len(TABS) + gap * (len(TABS) - 1)) // 2
    for tid, label in TABS:
        r = pygame.Rect(x, y, tw, 34)
        sel = tid == tab
        hot = r.collidepoint(mouse) and not sel
        if sel:
            _grad(s, r, (92, 70, 40), (58, 42, 24))
            pygame.draw.rect(s, GLOW2, r, 2, border_radius=4)
            col = GLOW2
        else:
            _grad(s, r, (40, 32, 24) if not hot else (52, 42, 30), (28, 22, 16))
            pygame.draw.rect(s, (110, 90, 62), r, 1, border_radius=4)
            col = TEXT
        _txt(s, label, "title", 16 if tw >= 120 else 13, col, r.center, "center")
        rects[f"tab:{tid}"] = r
        x += tw + gap
    y += 42
    flash = data.get("flash")
    if flash:
        good = any(k in str(flash) for k in ("Victory", "Recruited", "Fitted", "Trained", "→", "banner", "Deployed", "Recalled", "Outfit"))
        _txt(s, flash, "body", 16, (150, 200, 130) if good else TEXT, (box.centerx, y), "midtop", maxw=box.w - 80)
    y += 20
    return y


def _draw_next_unlock(client, s, box, data, rects, mouse, y):
    cmd = int(data.get("command_level") or 1)
    nxt = data.get("next_unlock")
    bar = pygame.Rect(box.x + 40, y, 220, 14)
    if nxt:
        lvl = int(nxt.get("level") or cmd)
        frac = max(0.0, min(1.0, cmd / max(1, lvl)))
        _txt(s, "Next unlock", "title", 14, TITLE, (bar.x, y - 3))
        bar.x += 104
        pygame.draw.rect(s, PLAQUE, bar, border_radius=7)
        fill = bar.copy(); fill.w = max(4, int(bar.w * frac))
        pygame.draw.rect(s, BRONZE, fill, border_radius=7)
        pygame.draw.rect(s, GOLD, bar, 1, border_radius=7)
        _txt(s, f"Cmd {cmd}/{lvl}", "body", 13, TEXT, bar.center, "center")
        f = _f("body", 15)
        tx = bar.right + 12
        lines = _wrap(nxt.get("text") or "", f, box.right - 40 - tx)[:2]
        for i, ln in enumerate(lines):
            s.blit(f.render(ln, True, TEXT), (tx, y - 3 + i * 17))
        hit = pygame.Rect(box.x + 40, y - 4, box.w - 80, 20 + 17 * (len(lines) - 1))
        rects["next_unlock"] = hit
        if hit.collidepoint(mouse):
            tip = [f"Cmd {cmd}/{lvl}: {nxt.get('text')}"]
            if not data.get("mythos_soldier_ready"):
                tip.append(f"Later goal: Crown Guard at Command 80 ({max(0, 80 - cmd)} left)")
            client._barracks_tooltip = (mouse, tip)
        y += max(20, 17 * len(lines)) + 6
    else:
        _txt(s, "All Command unlocks earned — Crown Guard ready.", "body", 15, LILAC, (box.centerx, y - 2), "midtop")
        y += 22
    return y


# ------------------------------------------------------------------ tabs
def _soldier_stats(sol):
    lv = sol.get("levels") or {}
    return f"Att {lv.get('attack')} · Str {lv.get('strength')} · Def {lv.get('defence')} · HP {lv.get('hitpoints')}"


def _cl_badge(s, x, y, cl):
    pts = [(x, y), (x + 54, y), (x + 54, y + 16), (x + 27, y + 24), (x, y + 16)]
    pygame.draw.polygon(s, (50, 38, 26), pts)
    pygame.draw.polygon(s, GOLD, pts, 1)
    _txt(s, f"CL {cl}", "title", 12, GOLD_HI, (x + 27, y + 10), "center")


def _tag(s, x, y, text, col, fill=(36, 30, 24), size=14, light=False):
    f = _f("body", size)
    t = f.render(text, True, tuple(min(255, int(v * 0.55 + 255 * 0.45)) for v in col) if light else col)
    r = pygame.Rect(x, y, t.get_width() + 16, 20)
    pygame.draw.rect(s, fill, r, border_radius=9)
    pygame.draw.rect(s, col, r, 1, border_radius=9)
    s.blit(t, (r.x + 8, r.centery - t.get_height() // 2))
    return r


def _kit_btn(s, rects, key, r, kit, hot):
    locked = bool(kit.get("locked"))
    label = kit["label"].replace(" kit", "")
    if locked:
        _cell(s, r, (80, 70, 56), (34, 30, 26))
    else:
        _grad(s, r, (52, 42, 30) if not hot else (66, 52, 36), (34, 27, 19))
        pygame.draw.rect(s, GLOW2 if hot else METAL.get(kit["tier"], GOLD), r, 1, border_radius=4)
    icon = _scaled(f"helm_{_tier_art(kit['tier'])}", (20, 20), grey=locked)
    x = r.x + 6
    if icon is not None:
        s.blit(icon, (x, r.centery - 10))
    if locked:
        _padlock(s, x + 9, r.centery - 3, (220, 206, 180), 0.8)
    _txt(s, label, "body", 14, MUTED if locked else TEXT, (x + 24, r.centery), "midleft", maxw=r.w - 32)
    rects[key] = r


def _draw_roster(client, s, body, data, rects, scroll, mouse):
    y = body.y + 8 - scroll
    w = body.w - 24
    x0 = body.x + 4
    soldiers = data.get("roster") or []
    # Outfit-all / train-all plaque
    strip = pygame.Rect(x0, y, w, 78)
    _cell(s, strip, (96, 76, 50), PLAQUE)
    _txt(s, "Outfit all", "title", 15, TITLE, (strip.x + 14, strip.y + 9))
    x = strip.x + 120
    kits = data.get("kits") or []
    kw = min(122, (strip.right - 12 - x - 6 * 5) // max(1, len(kits)))
    for kit in kits:
        r = pygame.Rect(x, strip.y + 6, kw, 28)
        key = f"kit_all:{kit['tier']}" if not kit.get("locked") else f"kit_all_locked:{kit['tier']}"
        _kit_btn(s, rects, key, r, kit, r.collidepoint(mouse) and not kit.get("locked"))
        x += kw + 6
    cap = int(data.get("daily_train_cap") or 10)
    _txt(s, f"Train all (+1 · {cap}/day each)", "title", 15, TITLE, (strip.x + 14, strip.y + 48))
    x = strip.x + 260
    for skill, short in (("attack", "Att"), ("strength", "Str"), ("defence", "Def"), ("hitpoints", "HP")):
        r = pygame.Rect(x, strip.y + 44, 80, 26)
        button(s, rects, f"train_all:{skill}", r, short, "dark", r.collidepoint(mouse), size=14)
        x += 86
    y += 86
    in_realm = bool(data.get("in_castle_realm"))
    dep = int(data.get("deployed_count") or 0)
    row = pygame.Rect(x0, y, w, 40)
    _cell(s, row, (96, 76, 50), PLAQUE)
    hint = (f"Field squad · {dep} deployed · follow you in King's Realm" if in_realm
            else "Field squad · enter King's Realm to deploy")
    _txt(s, hint, "body", 16, TEXT if in_realm else MUTED, (row.x + 14, row.centery), "midleft")
    if in_realm:
        r1 = pygame.Rect(row.right - 232, row.y + 6, 112, 28)
        r2 = pygame.Rect(row.right - 112, row.y + 6, 100, 28)
        button(s, rects, "deploy_all", r1, "Deploy all", "green", r1.collidepoint(mouse), size=14)
        button(s, rects, "recall_all", r2, "Recall", "bronze", r2.collidepoint(mouse), size=14)
    y += 48
    if not soldiers:
        _txt(s, "No soldiers yet — open Recruit, or talk to Marshal Branna on the sand.", "body", 17, MUTED,
             (x0 + 14, y + 12))
        return y + 40 + scroll - body.y
    _txt(s, "Click a soldier to kit, train, promote, deploy, or dismiss.", "body", 15, MUTED, (x0 + 6, y))
    y += 24
    portraits = client._barracks_portraits
    for sol in soldiers:
        card = pygame.Rect(x0, y, w, 88)
        y += 94
        if card.bottom < body.y or card.top > body.bottom:
            continue
        hot = card.collidepoint(mouse) and body.collidepoint(mouse)
        _cell(s, card, (90, 72, 48), CELL_HOT if hot else CELL)
        if hot:
            _glow(s, card)
        _round_frame(s, (card.x + 48, card.centery), BUST_FRAME, BUST_INNER,
                     _bust_surface(sol.get("gear_tier") or "bronze", BUST_INNER),
                     rim=METAL.get(sol.get("gear_tier"), GOLD), record=portraits)
        tx = card.x + 96
        nr = _txt(s, sol.get("name") or "", "title", 19, GOLD_HI, (tx, card.y + 8))
        _cl_badge(s, nr.right + 12, card.y + 8, sol.get("combat_level"))
        _tag(s, nr.right + 76, card.y + 9, sol.get("template_name") or sol.get("role") or "", SAND)
        daily = sol.get("trains_today") or {}
        left = daily.get("remaining", cap)
        _txt(s, f"{_soldier_stats(sol)} · {(sol.get('gear_tier') or '').replace('mythos', 'crownforged').title()} · "
                f"{sol.get('ability_label') or '—'} · trains {left}/{cap}", "body", 15, MUTED, (tx, card.y + 38),
             maxw=card.right - tx - 16)
        up = sol.get("upgrade")
        if sol.get("deployed"):
            line, col = "Deployed — following you in the King's Realm", (150, 200, 130)
        elif up and not up.get("locked"):
            line, col = f"Promote to {up.get('to_name')} · {int(up.get('cost') or 0):,}c (keeps battle XP)", (150, 200, 130)
        elif up:
            line, col = f"Next: {up.get('to_name')} · need Command {up.get('command_req')}", MUTED
        else:
            line, col = str(sol.get("blurb") or ""), MUTED
        _txt(s, line, "body", 15, col, (tx, card.y + 60), maxw=card.right - tx - 16)
        rects[f"select:{sol['id']}"] = card
    return y + scroll - body.y


_ROLE_OF = {"levy": "fodder", "man_at_arms": "line", "veteran": "line", "skirmisher": "flank",
            "bulwark": "tank", "zealot": "glass", "duelist": "elite", "medic": "support", "mythos_guard": "elite"}


def _draw_recruit(client, s, body, data, rects, scroll, mouse):
    y = body.y + 8 - scroll
    w = body.w - 24
    x0 = body.x + 4
    purse = int(data.get("coins") or 0) + int(data.get("bank_coins") or 0)
    for t in data.get("recruit") or []:
        card = pygame.Rect(x0, y, w, 92)
        y += 98
        if card.bottom < body.y or card.top > body.bottom:
            continue
        locked = bool(t.get("locked"))
        _cell(s, card, (70, 62, 50) if locked else (90, 72, 48), (32, 28, 24) if locked else CELL)
        import arena_barracks_fx as FXB
        _round_frame(s, (card.x + 48, card.centery), BUST_FRAME, BUST_INNER,
                     FXB.gladiator_bust(t.get("id"), BUST_INNER, HEADROOM) or _bust_surface(t.get("default_gear") or "bronze", BUST_INNER),
                     rim=(100, 88, 70) if locked else METAL.get(t.get("default_gear"), GOLD), grey=locked,
                     record=client._barracks_portraits)
        tx = card.x + 96
        nr = _txt(s, t["name"], "title", 19, MUTED if locked else GOLD_HI, (tx, card.y + 8))
        _cl_badge(s, nr.right + 12, card.y + 8, t.get("combat_level"))
        if t.get("role"):
            role_icon(s, card.x + 78, card.bottom - 16, t["role"], r=8)
        cr = _txt(s, f"{int(t.get('cost') or 0):,}c", "title", 15, MUTED if locked else GOLD_HI, (nr.right + 98, card.y + 11))
        _coin(s, cr.x - 11, cr.centery)
        ab = t.get("ability_label") if t.get("ability_label") not in (None, "—") else "No ability"
        _txt(s, f"{ab} · train ×{t.get('train_speed')}", "body", 15, MUTED, (tx, card.y + 38))
        up_from = t.get("upgrade_from")
        if up_from and not locked:
            line, col = (f"Or promote {up_from.get('soldier_name')} ({up_from.get('from_name')}) for "
                         f"{int(up_from.get('cost') or 0):,}c — keeps battle XP", (150, 200, 130))
        else:
            line, col = str(t.get("blurb") or ""), MUTED
        _txt(s, line, "body", 15, col, (tx, card.y + 60), maxw=card.right - tx - ACTION_W - 24)
        ax = card.right - ACTION_W - 10
        if locked:
            _padlock(s, ax + 6, card.y + 22, MUTED, 1.3)
            _txt(s, f"Command {t.get('command_req')}", "title", 15, MUTED, (ax + 30, card.y + 26))
        else:
            r = pygame.Rect(ax, card.y + 12, ACTION_W, 32)
            button(s, rects, f"recruit:{t['id']}", r, "Recruit", "bronze" if purse >= int(t.get("cost") or 0) else "dark",
                   r.collidepoint(mouse), size=15)
            if up_from:
                r2 = pygame.Rect(ax, card.y + 50, ACTION_W, 28)
                button(s, rects, f"upgrade:{up_from['soldier_id']}", r2,
                       f"Upgrade {int(up_from.get('cost') or 0):,}c", "dark", r2.collidepoint(mouse), size=13, outline=True)
    return y + scroll - body.y


def _house_card(client, s, rects, card, foe, army_cl, remaining, mouse, show_banner=True):
    unlocked = bool(foe.get("unlocked"))
    tier = int(foe.get("tier") or 0)
    king = tier == 6
    foe_cl = int(foe.get("foe_combat_level") or 0)
    label, col = fight_label(army_cl, foe_cl)
    if king:
        _cell(s, card, GLOW2 if unlocked else (150, 120, 60), (58, 44, 22))
        _glow(s, card, GLOW2)
    elif unlocked:
        _cell(s, card, col, CELL, width=2)
    else:
        _cell(s, card, (70, 62, 50), (30, 27, 23))
    if show_banner:
        _banner(s, card.x - 52, card.y - 4, card.h + 4, tier, BANNER_COL.get(tier, (36, 48, 88)), dim=not unlocked and not king)
    mc = (card.x + 40, card.centery)
    import arena_barracks_fx as FXB
    face = FXB.commander_portrait(foe.get("id"), BUST_INNER) if (unlocked or king) else None
    if face is not None:
        _round_frame(s, mc, BUST_FRAME, BUST_INNER, face, rim=GLOW2 if king else GOLD)
        _tag(s, mc[0] - 14, card.bottom - 22, f"T{tier}", GOLD, (36, 30, 24), size=13, light=True)
    elif unlocked or king:
        _medallion(s, mc, f"T{tier}", crown=king, rim=GLOW2 if king else GOLD)
    else:
        _padlock(s, mc[0] - 13, mc[1] - 14, MUTED, 1.9)
    tx = card.x + 80
    ncol = GOLD_HI if unlocked else MUTED
    nr = _txt(s, foe.get("name") or "", "title", 19, ncol, (tx, card.y + 8))
    det = f"{int(foe.get('foe_soldiers') or 10)} soldiers · foe CL {foe_cl:,} · rec {foe.get('recommend_cl')}"
    room = card.right - ACTION_W - 24 - (nr.right + 16)
    if _f("body", 16).size(det)[0] <= room:
        _txt(s, det, "body", 16, TEXT if unlocked else MUTED, (nr.right + 16, card.y + 11))
    else:   # narrow: details go in the reward line
        foe["_det_inline"] = det
    reward = f"win +{foe.get('command_xp_win')} Cmd / {int(foe.get('coin_win') or 0):,}c"
    if foe.pop("_det_inline", None):
        reward = f"foe CL {foe_cl:,} · " + reward
    if unlocked:
        _tag(s, tx, card.y + 36, label, col, tuple(int(v * 0.32) for v in col), size=15, light=True)
    else:
        _txt(s, "Beat the previous house to unlock", "body", 15, MUTED, (tx, card.y + 37))
    rw = _txt(s, reward, "body", 14, MUTED, (tx, card.y + 60), maxw=card.right - ACTION_W - 24 - tx)
    prev_army = foe.get("army_preview") or []
    if prev_army and unlocked:
        sz = 22
        need = min(10, len(prev_army)) * (sz + 2)
        ax0 = card.right - ACTION_W - 28 - need
        if ax0 > max(tx + 250, (rw.right if rw else tx) + 12):
            FXB.army_strip(s, ax0, card.y + 34, prev_army, size=sz)
    ar = pygame.Rect(card.right - ACTION_W - 14, card.centery - 17, ACTION_W, 34)
    if unlocked and remaining > 0:
        button(s, rects, f"practice:{foe['id']}", ar, "Battle", "bronze", ar.collidepoint(mouse))
    elif unlocked:
        button(s, None, None, ar, "No fights left", "off", size=13)
    else:
        button(s, None, None, ar, "Locked", "off", icon="lock", size=15)
    return label, col


def _draw_practice(client, s, body, data, rects, scroll, mouse):
    y = body.y + 8 - scroll
    w = body.w - 24
    x0 = body.x + 4
    res = data.get("practice_result")
    if res:
        won = bool(res.get("won"))
        card = pygame.Rect(x0, y, w, 52)
        _cell(s, card, GAIN if won else LOSS, CELL, width=2)
        text = (f"{'Victory' if won else 'Defeat'} vs {res.get('foe_name')} — +{res.get('command_xp')} Command"
                + (f", +{res.get('coins'):,}c" if res.get("coins") else "")
                + (" · Mythos ore!" if res.get("mythos_ore") else ""))
        _txt(s, text, "title", 18, (170, 220, 150) if won else (230, 150, 130), card.center, "center", maxw=w - 30)
        y += 60
    daily = data.get("daily_fights") or {}
    remaining, cap = int(daily.get("remaining", 10)), int(daily.get("cap", 10))
    meter = pygame.Rect(x0, y, w, 58)
    _cell(s, meter, (96, 76, 50), PLAQUE)
    _txt(s, "Practice bouts", "title", 18, TITLE, (meter.x + 14, meter.y + 8))
    _txt(s, f"Your army CL {data.get('roster_total_cl', 0):,} · foes field 10 (5 front / 5 rear) · "
            f"{remaining}/{cap} fights left today", "body", 15, MUTED if remaining else (230, 150, 130),
         (meter.x + 14, meter.y + 33))
    pip_x = meter.right - 16 - cap * 18
    for i in range(cap):
        c = (pip_x + i * 18 + 7, meter.centery)
        pygame.draw.circle(s, GOLD if i < remaining else (60, 50, 38), c, 6)
        pygame.draw.circle(s, (20, 15, 10), c, 6, 1)
    y += 66
    board = [f for f in (data.get("practice") or []) if f.get("unlocked")]
    army = int(data.get("roster_total_cl") or 0)
    if board:
        best = board[-1]
        for f in board:
            if fight_label(army, f.get("foe_combat_level"))[1] != GAIN:
                best = f
                break
        _txt(s, "Recommended spar", "title", 16, TITLE, (x0 + 6, y))
        y += 26
        card = pygame.Rect(x0, y, w, 82)
        _house_card(client, s, rects, card, best, army, remaining, mouse, show_banner=False)
        y += 92
    lines = ("Spar against a house army to earn Command XP and coins. Win to unlock the next house.",
             "The full house ladder (T1 Squire Aiden to T6 King of Crownfall) lives on the Ladder tab;",
             "one-on-one champion bouts are on the Champions tab.")
    for ln in lines:
        _txt(s, ln, "body", 15, MUTED, (x0 + 6, y))
        y += 20
    return y + 10 + scroll - body.y


def _draw_champions(client, s, body, data, rects, scroll, mouse):
    a = data.get("arena") or {}
    y = body.y + 8 - scroll
    w = body.w - 24
    x0 = body.x + 4
    remaining = int((data.get("daily_fights") or {}).get("remaining", 10))
    bar = pygame.Rect(x0, y, w, 52)
    _cell(s, bar, (96, 76, 50), PLAQUE)
    _txt(s, f"Arena Renown {a.get('renown', 0)} · {a.get('renown_title', 'Tiro')}", "title", 18, TITLE, (bar.x + 14, bar.y + 6))
    _txt(s, "Renown raises your Standing (nobility). Beat The Unbroken for a King's Row deed.", "body", 14, MUTED,
         (bar.x + 14, bar.y + 30))
    y += 60
    for b in a.get("bosses") or []:
        card = pygame.Rect(x0 + 2, y, w - 2, 112)
        y += 118
        if card.bottom < body.y or card.top > body.bottom:
            continue
        un = bool(b.get("unlocked"))
        beaten = bool(b.get("beaten"))
        layer = pygame.Surface(card.size, pygame.SRCALPHA)
        lr = layer.get_rect()
        hot = un and card.collidepoint(mouse)
        _cell(layer, lr, GAIN if beaten else (GOLD if un else (90, 80, 64)), CELL_HOT if hot else CELL, width=2 if un else 1)
        _medallion(layer, (lr.x + 34, lr.centery), f"T{b.get('tier')}", dim=not un)
        pf = pygame.Rect(lr.x + 70, lr.y + 8, CHAMP_FRAME, CHAMP_FRAME)
        rec = [] if True else None
        _square_frame(layer, pf, (CHAMP_INNER, CHAMP_INNER), _champ_surface(b.get("boss_id") or "", CHAMP_INNER),
                      rim=GOLD if un else (100, 88, 70), grey=not un, record=rec)
        for r in rec:
            r["inner"] = r["inner"].move(card.topleft)
            r["art"] = r["art"].move(card.topleft)
            client._barracks_portraits.append(r)
        tx = pf.right + 16
        _txt(layer, f"T{b.get('tier')} {b.get('name')}", "title", 19, GOLD_HI if un else MUTED, (tx, lr.y + 12))
        _txt(layer, (b.get("title") or "") + ("  · Defeated" if beaten else ""), "body", 16,
             (150, 200, 130) if beaten else (230, 203, 142), (tx, lr.y + 40))
        rw = 72
        slot = pygame.Rect(lr.right - ACTION_W - 24 - rw - 40, lr.y + 10, rw, rw)
        _txt(layer, b.get("ability") or "", "body", 15, MUTED, (tx, lr.y + 66), maxw=slot.x - tx - 16)
        _cell(layer, slot, GOLD if un else (90, 80, 64), PLAQUE)
        try:
            import arena_battles_ui as AB
            AB._icon(layer, slot.inflate(-10, -10), b.get("drop_id"))
        except Exception as e:
            E._log_once("champ reward icon", e)
        _txt(layer, b.get("drop") or "", "body", 13, (230, 203, 142) if un else MUTED, (slot.centerx, slot.bottom + 2),
             "midtop", maxw=rw + 60)
        if not un:
            layer.set_alpha(140)                    # dimmed to 55%
        s.blit(layer, card.topleft)
        ax = card.right - ACTION_W - 14
        if un:
            r1 = pygame.Rect(ax, card.y + 22, ACTION_W, 34)
            r2 = pygame.Rect(ax, card.y + 62, ACTION_W, 28)
            if remaining > 0:
                button(s, rects, f"practice:{b['id']}", r1, "Challenge", "bronze", r1.collidepoint(mouse))
                button(s, rects, f"duel:{b['id']}", r2, "Duel 1v1", "dark", r2.collidepoint(mouse), size=14, outline=True)
            else:
                button(s, None, None, r1, "No fights left", "off", size=13)
        else:
            _padlock(s, ax + ACTION_W // 2 - 10, card.y + 26, MUTED, 1.4)
            f = _f("body", 14)
            for i, ln in enumerate(_wrap("Beat the previous house first", f, ACTION_W)):
                _txt(s, ln, "body", 14, MUTED, (ax + ACTION_W // 2, card.y + 56 + i * 17), "midtop")
    return y + scroll - body.y


def _draw_ladder(client, s, body, data, rects, scroll, mouse):
    y = body.y + 8 - scroll
    x0 = body.x + 4
    w = body.w - 24
    army = int(data.get("roster_total_cl") or 0)
    daily = data.get("daily_fights") or {}
    remaining = int(daily.get("remaining", 10))
    _txt(s, f"Your army CL {army:,} · foes field 10 (5 front / 5 rear) · {remaining}/{daily.get('cap', 10)} fights left today",
         "body", 15, MUTED, (x0 + 6, y))
    y += 26
    labels = {}
    for foe in data.get("practice") or []:
        card = pygame.Rect(x0 + 58, y, w - 58, 84)
        y += 92
        if card.bottom < body.y - 10 or card.top > body.bottom + 10:
            continue
        labels[int(foe.get("tier") or 0)] = _house_card(client, s, rects, card, foe, army, remaining, mouse)
    client._barracks_ladder_labels = labels
    # Ranked season + rival commanders (kept from the old Ladder tab)
    a = data.get("arena") or {}
    lad = a.get("ladder") or {}
    y += 6
    card = pygame.Rect(x0, y, w, 96)
    _cell(s, card, (96, 76, 50), PLAQUE)
    import time as _t
    left = max(0, int(lad.get("ends_at", 0) - _t.time()))
    _txt(s, f"Ranked Season {lad.get('season', '')}", "title", 18, TITLE, (card.x + 14, card.y + 8))
    _txt(s, f"Resets in {left // 86400}d {left % 86400 // 3600}h · soft reset to halfway to 1000", "body", 14, MUTED,
         (card.right - 14, card.y + 12), "topright")
    _txt(s, f"Rating {lad.get('rating', 1000)} · {lad.get('band', 'Iron')} band · W {lad.get('wins', 0)} / L {lad.get('losses', 0)}",
         "body", 17, TEXT, (card.x + 14, card.y + 38))
    _txt(s, "Season rewards: Gold 1600+ 60k · Silver 1400+ 25k · Bronze 1200+ 10k · Iron 2k (+renown)", "body", 14,
         (230, 203, 142), (card.x + 14, card.y + 66))
    y += 104
    _txt(s, "Rival commanders (their saved rosters, AI-led)", "title", 16, TITLE, (x0 + 6, y))
    y += 26
    rivals = a.get("rivals") or []
    if not rivals:
        _txt(s, "No rival rosters yet — every fight you finish saves yours for others.", "body", 15, MUTED, (x0 + 6, y))
        y += 28
    for r in rivals:
        row = pygame.Rect(x0, y, w, 56)
        y += 62
        _cell(s, row)
        _txt(s, f"{r['name']} · {r['soldiers']} soldiers · CL {r['roster_cl']}", "title", 16, GOLD_HI, (row.x + 14, row.y + 6))
        _txt(s, f"Rating {r['rating']} · win {r['elo_win']:+d} / loss {r['elo_loss']:+d}", "body", 14, MUTED, (row.x + 14, row.y + 32))
        if remaining > 0:
            br = pygame.Rect(row.right - ACTION_W - 14, row.y + 11, ACTION_W, 34)
            button(s, rects, f"practice:{r['id']}", br, "Ranked fight", "steel", br.collidepoint(mouse), size=15)
    y += 6
    lb = a.get("leaderboard") or []
    if lb:
        _txt(s, "This week's top commanders", "title", 16, TITLE, (x0 + 6, y))
        y += 26
        for e in lb:
            col = GLOW2 if e["rank"] == 1 else TEXT
            _txt(s, f"#{e['rank']}  {e['name'][:22]}", "body", 15, col, (x0 + 18, y))
            _txt(s, f"{e['rating']}   {e['wins']}-{e['losses']}", "body", 15, col, (x0 + 320, y))
            y += 22
    return y + 10 + scroll - body.y


# ------------------------------------------------------------------ soldier panel
def _selected(client, data):
    sid = getattr(client, "barracks_selected", None)
    for sol in data.get("roster") or []:
        if sol.get("id") == sid:
            return sol
    return None


def _draw_soldier(client, s, box, data, rects, mouse):
    sol = _selected(client, data)
    if not sol:
        client.barracks_selected = None
        return
    veil = pygame.Surface(s.get_size(), pygame.SRCALPHA)
    veil.fill((0, 0, 0, 150))
    s.blit(veil, (0, 0))
    card = pygame.Rect(0, 0, min(920, box.w - 40), min(700, box.h - 40))
    card.center = box.center
    T._frame(s, card)
    rects["detail"] = card
    role = sol.get("template_name") or sol.get("role") or ""
    # title ribbon
    f = _f("title", 24)
    t = f.render(f"{sol.get('name')} · {role}", True, TITLE)
    rr = pygame.Rect(card.x + 30, card.y + 20, t.get_width() + 40, 40)
    pygame.draw.rect(s, PLAQUE, rr, border_radius=4)
    pygame.draw.rect(s, GOLD, rr, 1, border_radius=4)
    T._diamond(s, rr.right, rr.centery, 6, GOLD)
    s.blit(t, (rr.x + 20, rr.centery - t.get_height() // 2 - 1))
    back = pygame.Rect(card.right - 30 - 90, card.y + 22, 90, 34)
    button(s, rects, "detail_back", back, "Back", "bronze", back.collidepoint(mouse))
    # niche
    niche = pygame.Rect(card.x + 30, card.y + 72, NICHE[0], NICHE[1])
    tier = sol.get("gear_tier") or "bronze"
    # Try-on: hovering a kit row previews that kit on the soldier (worn kit otherwise).
    show_tier = tier
    _gx, _gy = niche.right + 40, card.y + 102
    for _kit in data.get("kits") or []:
        if pygame.Rect(_gx, _gy, card.right - 30 - _gx, 40).collidepoint(mouse) and _kit["tier"] != tier:
            show_tier = _kit["tier"]
        _gy += 46
    full = _scaled(f"full_{_tier_art(show_tier)}", NICHE_INNER)
    inner = _square_frame(s, niche, NICHE_INNER, None, rim=GOLD)
    _niche_bg(s, inner)
    if full is not None:
        prev = s.get_clip()
        s.set_clip(inner)
        s.blit(full, inner.topleft)
        s.set_clip(prev)
        client._barracks_portraits.append({"kind": "full", "inner": inner.copy(),
                                           "art": full.get_bounding_rect(min_alpha=60).move(inner.topleft)})
    else:
        try:
            import mercenaries_ui
            prev = s.get_clip(); s.set_clip(inner)
            mercenaries_ui.draw_soldier_portrait(s, sol, inner.centerx, inner.bottom - 40, tile=80)
            s.set_clip(prev)
        except Exception as e:
            E._log_once("soldier niche fallback", e)
    pygame.draw.rect(s, GOLD_HI, inner.inflate(2, 2), 1)
    if show_tier != tier:
        _tag(s, inner.x + 8, inner.y + 8, f"Preview: {show_tier.replace('mythos', 'crownforged').title()} kit",
             GLOW2, (40, 30, 14), size=14, light=True)
    ly = niche.bottom + 8
    tname = tier.replace("mythos", "crownforged").title()
    _txt(s, f"CL {sol.get('combat_level')} · {tname}", "title", 20, GOLD_HI, (niche.centerx, ly), "midtop")
    ly += 30
    lv = sol.get("levels") or {}
    px = niche.x - 6
    import arena_barracks_fx as FXB
    fx = FXB.active(sol.get("id"))
    up = {g[0].lower(): g for g in (fx[0]["gains"] if fx else [])}
    for short, key in (("Att", "attack"), ("Str", "strength"), ("Def", "defence"), ("HP", "hitpoints")):
        r = pygame.Rect(px, ly, 60, 28)
        if key in up:
            FXB.glow_chip(s, r, fx[1])
        _cell(s, r, GOLD, PLAQUE, radius=4)
        _txt(s, f"{short} {lv.get(key)}", "body", 15, TEXT, r.center, "center")
        if key in up:
            FXB.float_text(s, _f("title", 14), f"+{up[key][2] - up[key][1]}", (r.right - 4, r.y + 2), fx[1],
                           col=(150, 240, 130), rise=10)
        px += 65
    if fx and fx[0]["cl"][1] > fx[0]["cl"][0]:
        FXB.float_text(s, _f("title", 22), f"Level up! CL {fx[0]['cl'][1]}", (niche.centerx, niche.y + 30), fx[1])
    ly += 36
    daily = sol.get("trains_today") or {}
    cap = int(daily.get("cap") or data.get("daily_train_cap") or 10)
    trains_left = int(daily.get("remaining", cap))
    purse = int(data.get("coins") or 0)
    bank = int(data.get("bank_coins") or 0)
    for ln, col in ((f"{sol.get('ability_label') or '—'}", TEXT),
                    (f"train ×{sol.get('train_speed')} · {trains_left}/{cap} trains today", MUTED if trains_left else (230, 150, 130)),
                    (f"Purse {purse:,} · Bank {bank:,}", MUTED)):
        _txt(s, ln, "body", 15, col, (niche.centerx, ly), "midtop", maxw=NICHE[0] + 20)
        ly += 19
    # gear
    gx = niche.right + 40
    gw = card.right - 30 - gx
    _txt(s, "Gear", "title", 20, TITLE, (gx, card.y + 72))
    gy = card.y + 102
    for kit in data.get("kits") or []:
        locked = bool(kit.get("locked"))
        worn = kit["tier"] == tier
        r = pygame.Rect(gx, gy, gw, 40)
        gy += 46
        hot = r.collidepoint(mouse) and not locked and not worn
        if worn:
            _grad(s, r, (96, 72, 36), (62, 44, 22))
            _glow(s, r)
        elif locked:
            _cell(s, r, (70, 62, 50), (30, 27, 23))
        else:
            _grad(s, r, (34, 40, 58) if not hot else (44, 52, 74), (24, 28, 42))
            pygame.draw.rect(s, GLOW2 if hot else METAL.get(kit["tier"], GOLD), r, 1, border_radius=4)
        icon = _scaled(f"helm_{_tier_art(kit['tier'])}", (32, 32), grey=locked)
        if icon is not None:
            s.blit(icon, (r.x + 10, r.centery - 16))
        if locked:
            _padlock(s, r.x + 52, r.centery - 9, MUTED)
        name = kit["label"]
        cx = r.centerx + 10
        if locked:
            _txt(s, f"{name} · Command {kit.get('command_req')}", "body", 17, MUTED, (cx, r.centery), "center")
        elif worn:
            f1 = _f("body", 17)
            a1 = f1.render(name, True, GOLD_HI)
            a2 = f1.render("Equipped", True, GOLD_HI)
            tw = a1.get_width() + 30 + a2.get_width()
            x = cx - tw // 2
            s.blit(a1, (x, r.centery - a1.get_height() // 2))
            _check(s, x + a1.get_width() + 8, r.centery, GLOW2, 13)
            s.blit(a2, (x + a1.get_width() + 30, r.centery - a2.get_height() // 2))
            _check(s, r.right - 34, r.centery, GLOW2, 16)
        else:
            f1 = _f("body", 17)
            a1 = f1.render(name, True, TEXT)
            cost = f"{int(kit['cost']):,}c"
            a2 = _f("title", 15).render(cost, True, GOLD_HI)
            tw = a1.get_width() + 34 + a2.get_width()
            x = cx - tw // 2
            s.blit(a1, (x, r.centery - a1.get_height() // 2))
            _coin(s, x + a1.get_width() + 20, r.centery)
            s.blit(a2, (x + a1.get_width() + 32, r.centery - a2.get_height() // 2))
        key = f"kit:{kit['tier']}" if not locked and not worn else f"kit_locked:{kit['tier']}"
        rects[key] = r
    # flash
    flash = data.get("flash")
    if flash:
        good = any(k in str(flash) for k in ("Fitted", "Trained", "→", "Equipped", "Outfit"))
        _txt(s, flash, "body", 15, (150, 200, 130) if good else TEXT, (gx + gw // 2, gy + 2), "midtop", maxw=gw)
    # train
    ty = max(gy + 24, ly + 10)
    ty = min(ty, card.bottom - 30 - 36 - 14 - 84)
    _txt(s, "Train (+1 level)", "title", 19, TITLE, (card.x + 30, ty))
    cost = int(sol.get("train_cost") or 0)
    funds = purse + bank
    _txt(s, f"{trains_left}/{cap} left · ~{cost:,}c next Att · purse then bank", "body", 15,
         MUTED if trains_left else (230, 150, 130), (card.x + 220, ty + 4))
    ty += 30
    bw = (card.w - 60 - 3 * 12) // 4
    bx = card.x + 30
    for skill in ("attack", "strength", "defence", "hitpoints"):
        cur = int(lv.get(skill, 1))
        r = pygame.Rect(bx, ty, bw, 54)
        bx += bw + 12
        ok = trains_left > 0 and funds >= cost
        hot = ok and r.collidepoint(mouse)
        if ok:
            _grad(s, r, (40, 50, 74) if not hot else (52, 64, 92), (24, 30, 46))
            pygame.draw.rect(s, GLOW2 if hot else GOLD, r, 1, border_radius=4)
        else:
            _cell(s, r, (70, 62, 50), (30, 27, 23), radius=4)
        col = TEXT if ok else (120, 110, 96)
        f1 = _f("body", 17)
        a = f1.render(f"{skill.title()} {cur}", True, col)
        b = f1.render(str(cur + 1), True, col)
        tw = a.get_width() + 26 + b.get_width()
        x = r.centerx - tw // 2
        s.blit(a, (x, r.y + 5))
        _arrow(s, x + a.get_width() + 6, r.y + 5 + a.get_height() // 2, col)
        s.blit(b, (x + a.get_width() + 26, r.y + 5))
        if trains_left <= 0:
            _txt(s, "No trains left today", "body", 14, (120, 110, 96), (r.centerx, r.bottom - 6), "midbottom")
        else:
            ct = _f("title", 14).render(f"{cost:,}c", True, GOLD_HI if ok else (200, 130, 110))
            cx = r.centerx - (ct.get_width() + 18) // 2
            _coin(s, cx + 6, r.bottom - 15)
            s.blit(ct, (cx + 18, r.bottom - 15 - ct.get_height() // 2))
        rects[f"train:{skill}" if ok else (f"train_cap:{skill}" if trains_left <= 0 else f"train_poor:{skill}")] = r
    # bottom row
    by = card.bottom - 30 - 36
    in_realm = bool(data.get("in_castle_realm"))
    dr = pygame.Rect(card.x + 30, by, 170, 36)
    if sol.get("deployed"):
        button(s, rects, f"recall:{sol['id']}", dr, "Recall", "bronze", dr.collidepoint(mouse))
    elif in_realm:
        button(s, rects, f"deploy:{sol['id']}", dr, "Deploy", "green", dr.collidepoint(mouse))
    else:
        button(s, None, None, dr, "Deploy", "off")
        _txt(s, "Enter King's Realm to deploy", "body", 13, MUTED, (dr.centerx, dr.bottom + 2), "midtop")
    up = sol.get("upgrade")
    pr = pygame.Rect(0, 0, 380, 36)
    pr.midtop = (card.centerx, by)
    if up:
        if up.get("locked"):
            button(s, None, None, pr, f"Promote — need Command {up.get('command_req')}", "off", size=15)
            rects[f"upgrade_locked:{sol['id']}"] = pr
        else:
            button(s, rects, f"upgrade:{sol['id']}", pr,
                   f"Promote to {up.get('to_name')} · {int(up.get('cost') or 0):,}c", "bronze", pr.collidepoint(mouse), size=15)
    xr = pygame.Rect(card.right - 30 - 170, by, 170, 36)
    button(s, rects, f"dismiss:{sol['id']}", xr, "Dismiss", "red", xr.collidepoint(mouse))


def _niche_bg(s, inner):
    k = ("niche", inner.size)
    if k not in _CACHE:
        bg = pygame.Surface(inner.size)
        for y in range(inner.h):
            u = y / max(1, inner.h - 1)
            c = (int(30 + 14 * (1 - abs(u - 0.4) * 1.6)), int(23 + 10 * (1 - abs(u - 0.4) * 1.6)), int(17 + 6 * (1 - abs(u - 0.4) * 1.6)))
            pygame.draw.line(bg, tuple(max(0, v) for v in c), (0, y), (inner.w, y))
        pygame.draw.ellipse(bg, (18, 13, 9), (inner.w // 2 - 70, inner.h - 22, 140, 16))
        _CACHE[k] = bg
    s.blit(_CACHE[k], inner.topleft)


# ------------------------------------------------------------------ confirm
def draw_confirm(client, s, rects, mouse):
    sid = getattr(client, "barracks_confirm", None)
    if sid is None:
        return
    data = getattr(client, "barracks", None) or {}
    sol = next((x for x in data.get("roster") or [] if x.get("id") == sid), None)
    if sol is None:
        client.barracks_confirm = None
        return
    veil = pygame.Surface(s.get_size(), pygame.SRCALPHA)
    veil.fill((0, 0, 0, 120))
    s.blit(veil, (0, 0))
    box = pygame.Rect(0, 0, 460, 190)
    box.center = s.get_rect().center
    T._frame(s, box)
    rects["confirm"] = box
    _txt(s, f"Dismiss {sol.get('name')}?", "title", 22, TITLE, (box.centerx, box.y + 32), "midtop")
    _txt(s, "This can't be undone.", "body", 17, TEXT, (box.centerx, box.y + 66), "midtop")
    c = pygame.Rect(box.centerx - 150, box.bottom - 66, 136, 36)
    d = pygame.Rect(box.centerx + 14, box.bottom - 66, 136, 36)
    button(s, rects, "confirm_cancel", c, "Cancel", "dark", c.collidepoint(mouse))
    button(s, rects, f"confirm_dismiss:{sid}", d, "Dismiss", "red", d.collidepoint(mouse))


# ------------------------------------------------------------------ tooltip / scrollbar
def _tooltip(s, client):
    tt = getattr(client, "_barracks_tooltip", None)
    if not tt:
        return
    (mx, my), lines = tt
    f = _f("body", 15)
    w = max(f.size(l)[0] for l in lines) + 24
    r = pygame.Rect(mx + 14, my + 16, w, 10 + 19 * len(lines))
    r.clamp_ip(s.get_rect())
    pygame.draw.rect(s, PLAQUE, r, border_radius=5)
    pygame.draw.rect(s, GOLD, r, 1, border_radius=5)
    for i, l in enumerate(lines):
        s.blit(f.render(l, True, TEXT), (r.x + 12, r.y + 5 + i * 19))


def _scroll(s, body, scroll, content_h, mouse):
    view_h = body.h
    max_scroll = max(0, content_h - view_h)
    if max_scroll <= 0:
        return {"track": None, "thumb": None, "max_scroll": 0, "view_h": view_h, "content_h": content_h}
    track = pygame.Rect(body.right - 12, body.y + 6, 10, body.h - 12)
    th = max(32, min(track.h, int(track.h * view_h / max(1, content_h))))
    thumb = pygame.Rect(track.x, track.y + int((track.h - th) * scroll / max_scroll), track.w, th)
    T._scrollbar(s, track, thumb, thumb.collidepoint(mouse))
    return {"track": track, "thumb": thumb, "max_scroll": max_scroll, "view_h": track.h, "content_h": content_h}


# ------------------------------------------------------------------ entry


# ------------------------------------------------------------------ formation tab (5 Nov)
ROLE_STYLE = {   # role -> (label, colour, glyph)
    "tank": ("Tank", (96, 140, 196), "shield"), "line": ("Line", (184, 160, 110), "sword"),
    "fodder": ("Levy", (150, 136, 112), "sword"), "flank": ("Skirmisher", (92, 170, 92), "swords"),
    "glass": ("Zealot", (206, 96, 70), "axe"), "elite": ("Duelist", (226, 180, 72), "swords"),
    "support": ("Medic", (226, 226, 226), "cross"),
}


def role_icon(s, cx, cy, role, r=9):
    """Small heraldic role glyph: shield / sword / bow / axe / crossed swords / cross."""
    _lab, col, g = ROLE_STYLE.get(role, ("", GOLD, "sword"))
    pygame.draw.circle(s, (24, 18, 12), (cx, cy), r + 2)
    pygame.draw.circle(s, col, (cx, cy), r + 2, 2)
    if g == "shield":
        pts = [(cx - r * .6, cy - r * .6), (cx + r * .6, cy - r * .6), (cx + r * .6, cy), (cx, cy + r * .75), (cx - r * .6, cy)]
        pygame.draw.polygon(s, col, pts)
    elif g == "cross":
        pygame.draw.rect(s, (200, 40, 40), (cx - 2, cy - r * .65, 4, r * 1.3))
        pygame.draw.rect(s, (200, 40, 40), (cx - r * .65, cy - 2, r * 1.3, 4))
    elif g == "bow":
        pygame.draw.arc(s, col, (cx - r * .7, cy - r * .7, r * 1.4, r * 1.4), -1.4, 1.4, 2)
        pygame.draw.line(s, col, (cx + 1, cy - r * .7), (cx + 1, cy + r * .7), 1)
    elif g == "axe":
        pygame.draw.line(s, col, (cx - r * .5, cy + r * .6), (cx + r * .3, cy - r * .6), 2)
        pygame.draw.circle(s, col, (int(cx + r * .3), int(cy - r * .35)), int(r * .4))
    elif g == "swords":
        pygame.draw.line(s, col, (cx - r * .6, cy + r * .6), (cx + r * .6, cy - r * .6), 2)
        pygame.draw.line(s, col, (cx + r * .6, cy + r * .6), (cx - r * .6, cy - r * .6), 2)
    else:
        pygame.draw.line(s, col, (cx, cy + r * .7), (cx, cy - r * .7), 2)
        pygame.draw.line(s, col, (cx - r * .4, cy + r * .3), (cx + r * .4, cy + r * .3), 2)


def stat_bars(s, x, y, w, levels, h=5):
    """Att / Str / Def / HP as coloured bars (level / 99)."""
    for i, (k, col) in enumerate((("attack", (200, 70, 60)), ("strength", (90, 170, 80)),
                                  ("defence", (90, 130, 200)), ("hitpoints", (220, 190, 80)))):
        v = int((levels or {}).get(k) or 1)
        r = pygame.Rect(x, y + i * (h + 2), w, h)
        pygame.draw.rect(s, (22, 17, 12), r)
        pygame.draw.rect(s, col, (r.x, r.y, max(2, int(w * min(99, v) / 99)), h))


def formation_draft(client, data):
    """Local editable copy of the saved slots; reset when the server sends a new state."""
    f = data.get("formation") or {}
    src = list(f.get("slots") or [])
    key = tuple(src)
    if getattr(client, "_formation_src", None) != key or not isinstance(getattr(client, "formation_draft", None), list):
        client._formation_src = key
        client.formation_draft = (src + [None] * 10)[:10]
        client.formation_pick = None
    return client.formation_draft


def _slot_card(client, s, rects, key, r, sol, hot, picked):
    _cell(s, r, GLOW if picked else (96, 76, 50), CELL_HOT if hot else CELL, width=2 if picked else 1)
    if picked or hot:
        _glow(s, r)
    if sol is None:
        _txt(s, "empty", "body", 14, MUTED, r.center, "center")
    else:
        inner = min(r.w - 20, 60)
        _round_frame(s, (r.centerx, r.y + 8 + inner // 2 + 4), inner + 8, inner,
                     _bust_surface(sol.get("gear_tier") or "bronze", inner),
                     rim=METAL.get(sol.get("gear_tier"), GOLD))
        role_icon(s, r.right - 14, r.y + 14, sol.get("role"))
        _txt(s, sol.get("name") or "", "title", 14, GOLD_HI, (r.centerx, r.y + inner + 22), "midtop", maxw=r.w - 8)
        _txt(s, f"CL {sol.get('combat_level')} · {ROLE_STYLE.get(sol.get('role'), (sol.get('template_name') or '',))[0]}",
             "body", 12, MUTED, (r.centerx, r.y + inner + 40), "midtop", maxw=r.w - 8)
        stat_bars(s, r.x + 10, r.bottom - 34, r.w - 20, sol.get("levels"))
    rects[key] = r


def _draw_formation(client, s, body, data, rects, scroll, mouse):
    y = body.y + 8 - scroll
    x0, w = body.x + 4, body.w - 24
    roster = {int(x["id"]): x for x in (data.get("roster") or [])}
    draft = formation_draft(client, data)
    pick = getattr(client, "formation_pick", None)
    f = data.get("formation") or {}
    head = pygame.Rect(x0, y, w, 52)
    _cell(s, head, (96, 76, 50), PLAQUE)
    _txt(s, "Battle formation", "title", 17, TITLE, (head.x + 14, head.y + 6))
    _txt(s, "Click a soldier, then a slot to place or swap. Front five clash first; rear five hold until a soldier falls.",
         "body", 13, MUTED, (head.x + 14, head.y + 30), maxw=head.w - 300)
    for i, (k, lab, st) in enumerate((("formation_save", "Save", "green"), ("formation_reset", "Default", "bronze"))):
        r = pygame.Rect(head.right - 220 + i * 108, head.y + 12, 100, 28)
        button(s, rects, k, r, lab, st, r.collidepoint(mouse), size=14)
    y += 60
    cw = (w - 4 * 8) // 5
    ch = 150
    for rank, (lab, off) in enumerate((("Front rank — clashes first", 0), ("Rear rank — reserves", 5))):
        _txt(s, lab, "title", 15, (230, 120, 90) if off == 0 else (120, 170, 230), (x0 + 4, y))
        y += 22
        for i in range(5):
            slot = off + i
            r = pygame.Rect(x0 + i * (cw + 8), y, cw, ch)
            sid = draft[slot]
            _slot_card(client, s, rects, f"fslot:{slot}", r, roster.get(sid) if sid is not None else None,
                       r.collidepoint(mouse), pick == ("slot", slot))
        y += ch + 10
    bench = [sid for sid in roster if sid not in draft]
    _txt(s, f"Not placed ({len(bench)}) — they still fight, after the placed soldiers", "title", 15, TITLE, (x0 + 4, y))
    y += 22
    for j, sid in enumerate(bench):
        r = pygame.Rect(x0 + (j % 5) * (cw + 8), y + (j // 5) * (ch + 8), cw, ch)
        _slot_card(client, s, rects, f"fbench:{sid}", r, roster[sid], r.collidepoint(mouse), pick == ("bench", sid))
    if bench:
        y += ((len(bench) + 4) // 5) * (ch + 8)
    note = "Mounts and ranged troops are not in the arena yet — every soldier fights on foot in melee."
    _txt(s, note, "body", 13, MUTED, (x0 + 4, y + 4), maxw=w)
    saved = "Saved formation in use." if f.get("saved") else "No saved formation — roster order is used."
    dirty = list(draft) != list((f.get("slots") or []) + [None] * 10)[:10]
    _txt(s, saved + ("  (unsaved changes)" if dirty else ""), "body", 13, AMBER if dirty else GAIN, (x0 + 4, y + 24))
    return y + 52 + scroll - body.y


def formation_click(client, key) -> bool:
    """Select-then-place / swap. Returns True when handled. Saving goes to the server."""
    data = client.barracks or {}
    draft = formation_draft(client, data)
    pick = getattr(client, "formation_pick", None)
    if key == "formation_save":
        client.net.send("BARRACKS", action="formation_save", slots=list(draft))
        return True
    if key == "formation_reset":
        client.net.send("BARRACKS", action="formation_reset")
        return True
    kind, val = key.split(":", 1)
    val = int(val)
    here = ("slot", val) if kind == "fslot" else ("bench", val)
    if pick is None:
        if kind == "fslot" and draft[val] is None:
            return True
        client.formation_pick = here
        return True
    if pick == here:
        client.formation_pick = None
        return True
    if pick[0] == "bench" and here[0] == "slot":
        draft[here[1]] = pick[1]                      # bench -> slot (old occupant to bench)
    elif pick[0] == "slot" and here[0] == "slot":
        draft[pick[1]], draft[here[1]] = draft[here[1]], draft[pick[1]]
    elif pick[0] == "slot" and here[0] == "bench":
        draft[pick[1]] = here[1]
    else:
        client.formation_pick = here
        return True
    client.formation_pick = None
    return True


def formation_content_height(data) -> int:
    n = len(data.get("roster") or [])
    placed = sum(1 for s in ((data.get("formation") or {}).get("slots") or []) if s is not None)
    bench = max(0, n - placed)
    return 60 + 2 * (22 + 160) + 22 + ((bench + 4) // 5) * 158 + 60


_DRAW = {"formation": _draw_formation, "roster": _draw_roster, "recruit": _draw_recruit, "practice": _draw_practice,
         "champions": _draw_champions, "ladder": _draw_ladder}


def draw(client):
    data = client.barracks
    s = client.screen
    sw, sh = s.get_size()
    mouse = pygame.mouse.get_pos()
    blocked = getattr(client, "barracks_selected", None) is not None or getattr(client, "barracks_confirm", None) is not None
    hover = (-1, -1) if blocked else mouse
    client._barracks_tooltip = None
    client._barracks_portraits = []
    try:
        import arena_barracks_fx as FXB
        FXB.update(data)
    except Exception as exc:  # noqa: BLE001
        E._log_once("barracks fx update", exc)
    tab = data.get("tab") or "roster"
    if tab in ("kits", "train"):
        tab = data["tab"] = "roster"
    if tab not in _DRAW:
        tab = "roster"
    s.blit(T._vignette(sw, sh), (0, 0))
    box = window_rect(sw, sh)
    T._frame(s, box)
    rects = {"panel": box}
    top = _draw_header(client, s, box, data, rects, hover, tab)
    body = pygame.Rect(box.x + 24, top, box.w - 48, box.bottom - 22 - top)
    pygame.draw.rect(s, PANEL, body, border_radius=6)
    pygame.draw.rect(s, (70, 55, 38), body, 1, border_radius=6)
    inner = body.inflate(-8, -8)
    scroll = int(getattr(client, "barracks_scroll", 0) or 0)
    prev = s.get_clip()
    # measure (off-screen pass caches nothing heavy) then clamp scroll
    s.set_clip(inner)
    meas = getattr(client, "barracks_scroll_meta", None) or {}
    content_h = int(meas.get("content_h") or 0) if meas.get("tab") == tab else 0
    max_scroll = max(0, content_h - inner.h)
    scroll = max(0, min(max_scroll, scroll))
    client.barracks_scroll = scroll
    body_rects = {}
    content_h = _DRAW[tab](client, s, inner, data, body_rects, scroll, hover if inner.collidepoint(mouse) else (-1, -1))
    s.set_clip(prev)
    for k, r in body_rects.items():          # only keep hit boxes that are visible
        if r.colliderect(inner):
            rects[k] = r.clip(inner)
    meta = _scroll(s, inner, scroll, int(content_h), hover)
    meta["tab"] = tab
    client.barracks_scroll_meta = meta
    rects["scroll_track"] = meta.get("track")
    rects["scroll_thumb"] = meta.get("thumb")
    if getattr(client, "barracks_selected", None) is not None:
        _draw_soldier(client, s, box, data, rects, mouse if getattr(client, "barracks_confirm", None) is None else (-1, -1))
    draw_confirm(client, s, rects, mouse)
    try:
        import arena_barracks_fx as FXB
        FXB.draw_toast(s, _f("title", 17), box)
    except Exception as exc:  # noqa: BLE001
        E._log_once("barracks toast", exc)
    if not blocked:
        _tooltip(s, client)
    client.barracks_rects = rects
