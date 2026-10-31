"""
stats_screen_v2.py: "Choose your starting stats" restyle (ONBOARDING/stats_screen/STATS_SCREEN_STYLE_SPEC.md).

Same look as the Equipment & Stats screen (equipment_ui_v2): a gold-framed wood window over a blurred,
candle-lit throne hall with a vignette. Content and server rules are unchanged (10 points, ALLOCATE_STATS).

* Logical window 900x680, centred and scaled evenly; below a 0.7 scale the columns stack (body on top)
  and the whole stacked canvas is fitted to the screen, so Confirm never needs scrolling.
* Click targets are kept in screen space in client.stat_alloc_rects / client.stat_preset_rects
  (same keys as before, so older tools keep working).
* Pure rule helpers (can_minus / can_plus / apply_preset / edit / ready / display_name) carry the
  allocation rules and are unit-tested in tools/test_stats_screen.py.
* client_screens.draw_stat_alloc / handle_stat_alloc_event call in here; if anything raises, the old
  flat screen is drawn instead (error fallback only).
"""
import math
import os
import time
import pygame

import equipment_ui_v2 as E

SKILLS = ("attack", "strength", "defence", "archery")
POINTS = 10
MAX_LEVEL = 40           # server/server.py handle_allocate_stats refuses a level above 40
BASE_W, BASE_H = 900, 680
STACK_W, STACK_H = 560, 880
STACK_SCALE = 0.7
EDGE = 16
SHIMMER_S = 0.8
PRESET_TIPS = {
    "Balanced": "A bit of everything. Good if unsure.",
    "Warrior": "Hit hard, take hits. Melee first.",
    "Ranger": "Strike from afar with bow and arrow.",
}
PATH_LINE = "Your path is chosen later in the village."
WAX = (142, 31, 31)
WAX_HI = (184, 67, 58)
SEAL_TXT = (243, 230, 207)
PARCH = (202, 174, 135)
PARCH_DK = (150, 122, 86)
INK = (43, 33, 24)
NAVY = (27, 34, 56)
NAVY_HI = (40, 50, 80)
BRONZE = (107, 74, 43)
PLUS_IN = (47, 74, 42)
PIP_ON = (255, 211, 107)
PIP_OFF = (58, 46, 34)
DELTA = (224, 177, 62)
_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets", "ui", "stats_screen")
_ART = {}


# ---------------------------------------------------------------- rules (pure, tested)
def presets():
    from client_screens import STAT_PRESETS
    return STAT_PRESETS


def remaining(alloc, points=POINTS):
    return points - sum(int(v) for v in alloc.values())


def stat_max_bonus(skill, base_levels):
    return MAX_LEVEL - int((base_levels or {}).get(skill, 1))


def can_minus(alloc, skill):
    return int(alloc.get(skill, 0)) > 0


def can_plus(alloc, skill, base_levels, points=POINTS):
    return remaining(alloc, points) > 0 and int(alloc.get(skill, 0)) < stat_max_bonus(skill, base_levels)


def plus_block_reason(alloc, skill, base_levels, points=POINTS):
    if remaining(alloc, points) <= 0:
        return "No points left"
    if int(alloc.get(skill, 0)) >= stat_max_bonus(skill, base_levels):
        return "Max for now"
    return ""


def ready(alloc, points=POINTS):
    return remaining(alloc, points) == 0


def display_name(player):
    """Character / display name; a raw numeric account name never shows ('Traveller' instead)."""
    p = player or {}
    for key in ("char_name", "display_name", "name"):
        v = str(p.get(key) or "").strip()
        if not v or v.lower() == "adventurer":
            continue
        digits = sum(ch.isdigit() for ch in v)
        if digits >= max(1, len(v) // 2):
            continue
        return v[:24]
    return "Traveller"


def mode_label(client):
    """Selected preset name, 'Custom' after a manual edit, or '' when untouched."""
    m = getattr(client, "stat_alloc_mode", "") or ""
    if m and m != "Custom":
        for name, pts in presets():
            if name == m and dict(pts) == dict(client.stat_alloc):
                return m
        return "Custom" if any(client.stat_alloc.values()) else ""
    return m if any(client.stat_alloc.values()) else ""


def apply_preset(client, name):
    for n, pts in presets():
        if n == name:
            client.stat_alloc = dict(pts)
            client.stat_alloc_mode = n
            client.stat_alloc_error = ""
            client.stat_skill_desc = ""
            _note_ready(client)
            return True
    return False


def edit(client, skill, action):
    """Manual - / +; returns True when the value changed. Any change switches the mode to Custom."""
    base = getattr(client, "stat_alloc_base", {}) or {}
    pts = int(getattr(client, "stat_alloc_points", POINTS) or POINTS)
    if action == "plus" and can_plus(client.stat_alloc, skill, base, pts):
        client.stat_alloc[skill] += 1
    elif action == "minus" and can_minus(client.stat_alloc, skill):
        client.stat_alloc[skill] -= 1
    else:
        return False
    client.stat_alloc_mode = "Custom"
    client.stat_skill_desc = skill
    client.stat_alloc_error = ""
    client._stats_pop = (skill, time.time())
    _note_ready(client)
    return True


def reset(client):
    client.stat_alloc = {s: 0 for s in client.stat_alloc}
    client.stat_alloc_mode = ""
    client.stat_alloc_error = ""
    client._stats_ready_t = None


def _note_ready(client):
    pts = int(getattr(client, "stat_alloc_points", POINTS) or POINTS)
    if ready(client.stat_alloc, pts):
        if not getattr(client, "_stats_ready_t", None):
            client._stats_ready_t = time.time()       # one shimmer per time it becomes ready
    else:
        client._stats_ready_t = None


# ---------------------------------------------------------------- layout
def layout(sw, sh):
    s = min(1.0, (sw - 2 * EDGE) / BASE_W, (sh - 2 * EDGE) / BASE_H)
    if s >= STACK_SCALE:
        w, h = int(BASE_W * s), int(BASE_H * s)
        return {"mode": "full", "scale": s, "ox": (sw - w) // 2, "oy": (sh - h) // 2, "w": w, "h": h,
                "canvas": (BASE_W, BASE_H)}
    s2 = min(1.0, (sw - 2 * EDGE) / STACK_W, (sh - 2 * EDGE) / STACK_H)
    w, h = int(STACK_W * s2), int(STACK_H * s2)
    return {"mode": "stack", "scale": s2, "ox": (sw - w) // 2, "oy": (sh - h) // 2, "w": w, "h": h,
            "canvas": (STACK_W, STACK_H)}


def geometry(mode):
    """Canvas-space rects for one mode."""
    R = pygame.Rect
    if mode == "full":
        W = BASE_W
        g = {"title": R(W // 2 - 240, 20, 480, 50), "scroll": R(W // 2 - 290, 80, 580, 38),
             "seal": R(W // 2 - 150, 128, 300, 44), "body_label": (180, 182),
             "cards": [R(65, 200, 110, 140), R(185, 200, 110, 140)],
             "preview": R(40, 350, 280, 256), "rows_x": 350, "rows_y": 184, "row_h": 56, "row_gap": 6,
             "desc_y": 428, "hint_y": 448, "rule_y": 488, "presets_y": 496, "banner": (120, 86),
             "path_y": 600, "confirm": R(W // 2 - 210, 618, 420, 50), "row_w": 520}
    else:
        W = STACK_W
        g = {"title": R(W // 2 - 230, 20, 460, 50), "scroll": R(W // 2 - 250, 80, 500, 38),
             "seal": R(W // 2 - 150, 128, 300, 44), "body_label": (138, 196),
             "cards": [R(30, 210, 100, 128), R(146, 210, 100, 128)],
             "preview": R(290, 186, 240, 176), "rows_x": 20, "rows_y": 372, "row_h": 56, "row_gap": 6,
             "desc_y": 622, "hint_y": 642, "rule_y": 682, "presets_y": 690, "banner": (120, 90),
             "path_y": 796, "confirm": R(W // 2 - 210, 812, 420, 50), "row_w": 520}
    rows = []
    for i, sk in enumerate(SKILLS):
        y = g["rows_y"] + i * (g["row_h"] + g["row_gap"])
        row = R(g["rows_x"], y, g["row_w"], g["row_h"])
        rows.append((sk, row, R(row.x + 266, row.centery - 20, 40, 40), R(row.x + 316, row.centery - 20, 40, 40)))
    g["rows"] = rows
    bw, bh = g["banner"]
    n = len(presets())
    gap = 44
    cx = g["rows_x"] + g["row_w"] // 2
    x0 = cx - (n * bw + (n - 1) * gap) // 2
    g["banners"] = [R(x0 + i * (bw + gap), g["presets_y"], bw, bh) for i in range(n)]
    g["reset"] = R(g["seal"].right + 14, g["seal"].centery - 12, 70, 24)
    return g


def _to_screen(L, r):
    s = L["scale"]
    return pygame.Rect(L["ox"] + int(r.x * s), L["oy"] + int(r.y * s), max(1, int(r.w * s)), max(1, int(r.h * s)))


def _to_canvas(L, pos):
    return ((pos[0] - L["ox"]) / L["scale"], (pos[1] - L["oy"]) / L["scale"])


# ---------------------------------------------------------------- art
def _img(name, alpha=True):
    if name not in _ART:
        try:
            im = pygame.image.load(os.path.join(_DIR, name))
            _ART[name] = im.convert_alpha() if alpha else im.convert()
        except Exception as e:
            E._log_once(f"stats art {name}", e)
            _ART[name] = None
    return _ART[name]


def _backdrop(sw, sh):
    key = ("bg", sw, sh)
    if key in _ART:
        return _ART[key]
    out = E._opaque(sw, sh)
    out.fill((10, 8, 6))
    bg = _img("throne_hall_bg.jpg", alpha=False)
    if bg is not None:
        bw, bh = bg.get_size()
        k = max(sw / bw, sh / bh)
        big = pygame.transform.smoothscale(bg, (int(bw * k) + 1, int(bh * k) + 1))
        small = pygame.transform.smoothscale(big, (max(1, big.get_width() // 6), max(1, big.get_height() // 6)))
        blur = pygame.transform.smoothscale(small, big.get_size())      # ~6px blur at 1x
        out.blit(blur, ((sw - big.get_width()) // 2, (sh - big.get_height()) // 2))
        dim = pygame.Surface((sw, sh), pygame.SRCALPHA)
        dim.fill((0, 0, 0, 92))                                         # brightness ~0.45
        out.blit(dim, (0, 0))
    vig = pygame.Surface((sw, sh), pygame.SRCALPHA)
    cx, cy = sw / 2, sh / 2
    # radial vignette via per-row alpha (fast enough, cached)
    try:
        import numpy as np
        yy, xx = np.mgrid[0:sh, 0:sw]
        d = np.hypot((xx - cx) / (sw / 2), (yy - cy) / (sh / 2)) / math.sqrt(2)
        a = np.clip((d - 0.35) / 0.65, 0, 1) ** 1.4 * 190
        arr = pygame.surfarray.pixels_alpha(vig)
        arr[...] = a.T.astype("uint8")
        del arr
        vig.fill((2, 3, 5, 0), special_flags=pygame.BLEND_RGBA_MAX)
    except Exception as e:
        E._log_once("stats vignette", e)
    out.blit(vig, (0, 0))
    _ART[key] = out
    return out


def _figure(sex):
    key = ("fig", sex)
    if key in _ART:
        return _ART[key]
    fig = None
    try:
        import player_hd_client as P
        look = P.starter_outfit_look(P.get_default_appearance(sex), sex)
        pad = 300
        canvas = pygame.Surface((pad * 2, pad * 2), pygame.SRCALPHA)
        P.draw_player(canvas, sex, look, pad, pad + 80, 160, 0.0, anim="idle", facing="s", equipment=None,
                      fx_ctx={"preview": True})
        try:                                   # drop the ground-shadow layer (near-black, semi-clear)
            import numpy as np
            a = pygame.surfarray.pixels_alpha(canvas)
            rgb = pygame.surfarray.pixels3d(canvas)
            a[(a < 235) & (rgb.max(axis=2) < 40)] = 0
            del a, rgb
        except Exception as e:
            E._log_once("stats figure shadow", e)
        box = canvas.get_bounding_rect(min_alpha=40)
        if box.w > 8 and box.h > 8:
            fig = canvas.subsurface(box).copy()
    except Exception as e:
        E._log_once(f"stats figure {sex}", e)
    _ART[key] = fig
    return fig


def _portrait(sex, size):
    key = ("portrait", sex, size)
    if key in _ART:
        return _ART[key]
    fig = _figure(sex)
    out = None
    if fig is not None:
        w, h = fig.get_size()
        side = int(w * 0.62)
        top = max(0, int(h * 0.0))
        crop = pygame.Rect((w - side) // 2, top, side, min(side, h))
        out = pygame.transform.smoothscale(fig.subsurface(crop.clip(fig.get_rect())), (size, size))
    _ART[key] = out
    return out


# ---------------------------------------------------------------- drawing pieces
def _arrow(c, x, cy, col, w=18):
    """Level arrow drawn as a shape (Mac fonts show the arrow glyph as a box)."""
    pygame.draw.rect(c, col, (x, cy - 1, w - 7, 3))
    pygame.draw.polygon(c, col, [(x + w - 9, cy - 6), (x + w, cy), (x + w - 9, cy + 6)])


def _title(c, r, text):
    E._plaque(c, r, rim=E.GOLD, fill=E.PLAQUE, radius=6)
    for sx in (-1, 1):
        x = r.centerx + sx * (r.w // 2 + 2)
        pygame.draw.polygon(c, E.WOOD_DK, [(x, r.centery), (x - sx * 16, r.y + 4), (x - sx * 16, r.bottom - 4)])
        pygame.draw.polygon(c, E.GOLD, [(x, r.centery), (x - sx * 16, r.y + 4), (x - sx * 16, r.bottom - 4)], 1)
    E._text(c, text, E.font("title", 28), E.TITLE_GOLD, r.center, anchor="center")


def _scroll(c, r, text):
    for sx in (r.x - 10, r.right - 4):          # rolled ends
        end = pygame.Rect(sx, r.y - 3, 14, r.h + 6)
        pygame.draw.rect(c, PARCH_DK, end, border_radius=6)
        pygame.draw.rect(c, (95, 72, 46), end, 1, border_radius=6)
    pygame.draw.rect(c, (0, 0, 0), r.move(0, 2), border_radius=3)
    pygame.draw.rect(c, PARCH, r, border_radius=3)
    for i in range(0, r.w, 3):                    # fibre streaks
        a = (i * 37) % 11
        if a < 2:
            pygame.draw.line(c, (192, 163, 124), (r.x + i, r.y + 3), (r.x + i, r.bottom - 4))
    pygame.draw.rect(c, PARCH_DK, r, 1, border_radius=3)
    E._text(c, text, E.font("body", 19), INK, r.center, shadow=False, anchor="center")


def _seal(c, r, left, custom, now, reset_rect, reset_hot):
    rib = r.inflate(-30, -8).move(14, 0)
    pygame.draw.rect(c, (0, 0, 0), rib.move(0, 2), border_radius=4)
    pygame.draw.rect(c, (110, 24, 24), rib, border_radius=4)
    pygame.draw.polygon(c, (110, 24, 24), [(rib.right, rib.y), (rib.right + 16, rib.centery), (rib.right, rib.bottom)])
    pygame.draw.rect(c, (60, 12, 12), rib, 1, border_radius=4)
    cx, cy = r.x + 22, r.centery
    pulse = 0.0 if left == 0 else 0.5 + 0.5 * math.sin(now * 2 * math.pi / 1.6)
    rad = 24 + int(2 * pulse)
    for k in range(10):                          # wavy wax edge
        a = k * math.pi / 5
        pygame.draw.circle(c, WAX, (int(cx + math.cos(a) * (rad - 4)), int(cy + math.sin(a) * (rad - 4))), 7)
    pygame.draw.circle(c, WAX, (cx, cy), rad - 3)
    pygame.draw.circle(c, WAX_HI, (cx - 6, cy - 7), 6)
    pygame.draw.circle(c, (96, 18, 18), (cx, cy), rad - 9, 2)
    E._diamond(c, cx, cy, 6, (196, 90, 70))
    if left == 0:
        pygame.draw.circle(c, E.FLASH, (cx, cy), rad + 1, 2)
    E._text(c, f"Points left: {left}", E.font("title", 22), SEAL_TXT, (rib.centerx + 10, rib.centery), anchor="center")
    if custom:
        tag = pygame.Rect(0, 0, 64, 20)
        tag.midtop = (rib.centerx + 10, rib.bottom - 2)
        pygame.draw.rect(c, E.PLAQUE, tag, border_radius=4)
        pygame.draw.rect(c, E.GOLD, tag, 1, border_radius=4)
        E._text(c, "Custom", E.font("title", 13), E.GOLD_HI, tag.center, anchor="center")
    col = E.GOLD_HI if reset_hot else E.GOLD
    rr = E._text(c, "Reset", E.font("body", 17), col, reset_rect.center, anchor="center")
    pygame.draw.line(c, col, (rr.x, rr.bottom - 1), (rr.right, rr.bottom - 1))


def _card(c, r, sex, label, selected, hot):
    pygame.draw.rect(c, (0, 0, 0), r.move(0, 3), border_radius=4)
    if selected:
        glow = pygame.Surface((r.w + 24, r.h + 24), pygame.SRCALPHA)
        for i in range(12):
            pygame.draw.rect(glow, (242, 193, 78, 10 + i * 4), glow.get_rect().inflate(-2 * i, -2 * i), 2, border_radius=10)
        c.blit(glow, (r.x - 12, r.y - 12))
    pygame.draw.rect(c, E.CELL, r, border_radius=4)
    pic = _portrait(sex, r.w - 8)
    inner = pygame.Rect(r.x + 4, r.y + 4, r.w - 8, r.h - 30)
    if pic is not None:
        c.set_clip(inner)
        c.blit(pic, (inner.x, inner.y))
        c.set_clip(None)
    shade = pygame.Surface((r.w, 26), pygame.SRCALPHA)
    shade.fill((14, 10, 7, 230))
    c.blit(shade, (r.x, r.bottom - 26))
    rim = E.FLASH if selected else (E.GOLD_HI if hot else (138, 106, 62))
    pygame.draw.rect(c, rim, r, 2, border_radius=4)
    E._text(c, label, E.font("title", 14), E.FLASH if selected else E.TEXT, (r.centerx, r.bottom - 13), anchor="center")


def _preview(c, r, sex):
    ring = pygame.Surface((r.w, 60), pygame.SRCALPHA)
    for i in range(20):
        a = int(70 * (1 - i / 20))
        pygame.draw.ellipse(ring, (206, 174, 115, a), pygame.Rect(i * 5, i * 1.3, r.w - i * 10, 60 - i * 2.6))
    c.blit(ring, (r.x, r.bottom - 46))
    pygame.draw.ellipse(c, (230, 190, 110), pygame.Rect(r.centerx - 90, r.bottom - 26, 180, 22), 1)
    fig = _figure(sex)
    if fig is None:
        return
    fw, fh = fig.get_size()
    k = min((r.h - 10) / fh, (r.w - 20) / fw)
    img = pygame.transform.smoothscale(fig, (max(1, int(fw * k)), max(1, int(fh * k))))
    c.blit(img, (r.centerx - img.get_width() // 2, r.bottom - 14 - img.get_height()))


def _medal(c, r, kind, enabled, hot, popped):
    s = 1.05 if (hot and enabled) else 1.0
    rad = int(r.w / 2 * s)
    cx, cy = r.center
    surf = pygame.Surface((rad * 2 + 6, rad * 2 + 6), pygame.SRCALPHA)
    o = rad + 3
    pygame.draw.circle(surf, (0, 0, 0, 160), (o, o + 2), rad)
    if kind == "minus":
        pygame.draw.circle(surf, BRONZE, (o, o), rad)
        pygame.draw.circle(surf, (138, 96, 58), (o - 4, o - 5), rad // 2)
        pygame.draw.circle(surf, BRONZE, (o, o), rad - 5)
    else:
        for i in range(rad, 0, -1):
            t = i / rad
            col = tuple(int(E.GOLD[j] + (E.GOLD_HI[j] - E.GOLD[j]) * (1 - t)) for j in range(3))
            pygame.draw.circle(surf, col, (o, o - (rad - i) // 4), i)
        pygame.draw.circle(surf, PLUS_IN, (o, o), rad - 6)
    pygame.draw.circle(surf, E.GOLD_HI if (hot and enabled) else E.GOLD, (o, o), rad, 2)
    g = SEAL_TXT
    pygame.draw.rect(surf, g, (o - 9, o - 2, 18, 4))
    if kind == "plus":
        pygame.draw.rect(surf, g, (o - 2, o - 9, 4, 18))
    if not enabled:
        surf.set_alpha(90)
    c.blit(surf, (cx - o, cy - o))


def _icon(c, skill, r):
    im = _img(f"icon_{skill}.png")
    if im is None:
        E._glyph(c, {"attack": "att", "strength": "str", "defence": "def"}.get(skill, "rng"), r.centerx, r.centery, (140, 90, 43))
        return
    c.blit(pygame.transform.smoothscale(im, r.size), r.topleft)


def _row(c, client, sk, row, minus, plus, hover, now, focused):
    alloc, base_l = client.stat_alloc, getattr(client, "stat_alloc_base", {}) or {}
    pts = int(getattr(client, "stat_alloc_points", POINTS) or POINTS)
    pygame.draw.rect(c, (0, 0, 0), row.move(0, 2), border_radius=6)
    c.blit(E._grain(row.w, row.h, (31, 24, 18), 70 + SKILLS.index(sk), streak=True), row.topleft)
    pygame.draw.rect(c, E.FLASH if focused else (58, 46, 34), row, 2 if focused else 1, border_radius=6)
    ib = pygame.Rect(row.x + 8, row.centery - 20, 40, 40)
    pygame.draw.rect(c, (24, 18, 13), ib, border_radius=5)
    pygame.draw.rect(c, (90, 70, 48), ib, 1, border_radius=5)
    _icon(c, sk, ib.inflate(-4, -4))
    base = int(base_l.get(sk, 1))
    bonus = int(alloc.get(sk, 0))
    x = row.x + 60
    nr = E._text(c, f"{sk.title()}:", E.font("body", 19), E.TEXT, (x, row.centery), anchor="midleft")
    br = E._text(c, str(base), E.font("body", 19), E.MUTED, (nr.right + 10, row.centery), anchor="midleft")
    _arrow(c, br.right + 8, row.centery + 1, E.GOLD)
    E._text(c, str(base + bonus), E.font("bold", 20), E.FLASH if bonus else E.TEXT, (br.right + 34, row.centery), anchor="midleft")
    pop = getattr(client, "_stats_pop", None)
    popped = bool(pop and pop[0] == sk and now - pop[1] < 0.15)
    _medal(c, minus, "minus", can_minus(alloc, sk), minus.collidepoint(hover) if hover else False, popped)
    _medal(c, plus, "plus", can_plus(alloc, sk, base_l, pts), plus.collidepoint(hover) if hover else False, popped)
    px = plus.right + 14
    for i in range(min(10, bonus)):              # one pip per point added
        rad = 5 + (1 if popped and i == bonus - 1 else 0)
        pygame.draw.circle(c, (90, 62, 20), (px + i * 13 + 5, row.centery + 1), 5)
        pygame.draw.circle(c, PIP_ON, (px + i * 13 + 5, row.centery), rad)
    tx = px + min(10, bonus) * 13 + 4 if bonus else px
    E._text(c, f"+{bonus}", E.font("body", 16), DELTA if bonus else E.MUTED, (tx, row.centery), anchor="midleft")


def _banner(c, r, name, selected, hot):
    dy = 4 if selected else 0
    rod = pygame.Rect(r.x - 8, r.y + dy, r.w + 16, 6)
    cloth = [(r.x, r.y + 4 + dy), (r.right, r.y + 4 + dy), (r.right, r.bottom - 18 + dy), (r.centerx, r.bottom + dy),
             (r.x, r.bottom - 18 + dy)]
    if selected or hot:
        glow = pygame.Surface((r.w + 30, r.h + 30), pygame.SRCALPHA)
        pts = [(x - r.x + 15, y - r.y + 15) for x, y in cloth]
        for i in range(8, 0, -1):
            pygame.draw.polygon(glow, (242, 193, 78, 14 if selected else 8), pts, i * 2)
        c.blit(glow, (r.x - 15, r.y - 15))
    pygame.draw.polygon(c, (0, 0, 0), [(x + 2, y + 3) for x, y in cloth])
    pygame.draw.polygon(c, NAVY_HI if hot else NAVY, cloth)
    trim = E.FLASH if selected else E.GOLD
    pygame.draw.polygon(c, trim, cloth, 2)
    inner = [(r.x + 6, r.y + 10 + dy), (r.right - 6, r.y + 10 + dy), (r.right - 6, r.bottom - 21 + dy),
             (r.centerx, r.bottom - 7 + dy), (r.x + 6, r.bottom - 21 + dy)]
    pygame.draw.polygon(c, (trim[0] // 2, trim[1] // 2, trim[2] // 2), inner, 1)
    pygame.draw.rect(c, E.WOOD_DK, rod.move(0, 1), border_radius=3)
    pygame.draw.rect(c, E.GOLD, rod, border_radius=3)
    for x in (rod.x, rod.right):
        pygame.draw.circle(c, E.GOLD_HI, (x, rod.centery), 5)
    E._text(c, name, E.font("title", 17), E.FLASH if selected else E.TEXT, (r.centerx, r.centery - 4 + dy), anchor="center")
    E._diamond(c, r.centerx, r.bottom - 22 + dy, 4, trim)


def _confirm(c, r, enabled, hot, ready_t, now):
    rr = r.move(0, 2) if (hot and enabled and pygame.mouse.get_pressed()[0]) else r
    pygame.draw.rect(c, (0, 0, 0), rr.move(0, 3), border_radius=6)
    surf = pygame.Surface(rr.size, pygame.SRCALPHA)
    top, bot = (E.GOLD_HI, E.GOLD) if enabled else ((112, 104, 92), (80, 74, 66))
    for y in range(rr.h):
        t = y / max(1, rr.h - 1)
        col = tuple(int(top[j] + (bot[j] - top[j]) * t) for j in range(3))
        if hot and enabled:
            col = tuple(min(255, v + 18) for v in col)
        pygame.draw.line(surf, col, (0, y), (rr.w, y))
    if enabled and ready_t is not None and 0 <= now - ready_t <= SHIMMER_S:   # one-time shimmer sweep
        f = (now - ready_t) / SHIMMER_S
        sx = int(-80 + (rr.w + 160) * f)
        sh = pygame.Surface(rr.size)                 # additive light band (alpha lines would punch holes)
        for i in range(60):
            a = int(110 * (1 - abs(i - 30) / 30))
            pygame.draw.line(sh, (a, a, int(a * 0.85)), (sx + i, 0), (sx + i - 24, rr.h))
        surf.blit(sh, (0, 0), special_flags=pygame.BLEND_RGB_ADD)
    mask = pygame.Surface(rr.size, pygame.SRCALPHA)
    pygame.draw.rect(mask, (255, 255, 255, 255), mask.get_rect(), border_radius=6)
    surf.blit(mask, (0, 0), special_flags=pygame.BLEND_RGBA_MIN)
    c.blit(surf, rr.topleft)
    pygame.draw.rect(c, (90, 70, 48), rr, 2, border_radius=6)
    pygame.draw.rect(c, (255, 236, 180) if enabled else (130, 122, 110), rr.inflate(-6, -6), 1, border_radius=5)
    for sx in (-1, 1):
        x = rr.centerx + sx * (rr.w // 2 + 3)
        pygame.draw.polygon(c, E.GOLD if enabled else (100, 92, 80), [(x, rr.centery), (x - sx * 14, rr.y + 6), (x - sx * 14, rr.bottom - 6)])
    E._text(c, "Confirm & Enter World", E.font("title", 20), INK if enabled else (52, 48, 42), rr.center,
            shadow=False, anchor="center")


def _tooltip(c, text, anchor_rect, cw):
    f = E.font("body", 15)
    tw = f.size(text)[0] + 20
    r = pygame.Rect(0, 0, tw, 28)
    r.midbottom = (anchor_rect.centerx, anchor_rect.y - 6)
    r.x = max(10, min(cw - tw - 10, r.x))
    if r.y < 10:
        r.top = anchor_rect.bottom + 6
    E._plaque(c, r, rim=E.GOLD_HI)
    E._text(c, text, f, E.TEXT, r.center, anchor="center")


# ---------------------------------------------------------------- main entry points
def _mouse(client):
    p = getattr(client, "_stats_mouse", None)        # proofs / tests can pin a hover position
    return p if p is not None else pygame.mouse.get_pos()


def draw(client):
    scr = client.screen
    sw, sh = scr.get_size()
    now = time.time()
    if not hasattr(client, "stat_alloc_mode"):
        client.stat_alloc_mode = ""
    pts = int(getattr(client, "stat_alloc_points", POINTS) or POINTS)
    _note_ready(client)
    L = layout(sw, sh)
    G = geometry(L["mode"])
    cw, ch = L["canvas"]
    scr.blit(_backdrop(sw, sh), (0, 0))
    c = E._opaque(cw, ch)
    E._draw_frame(c, cw, ch)
    mx, my = _mouse(client)
    hover = _to_canvas(L, (mx, my))
    hover = (int(hover[0]), int(hover[1]))
    left = remaining(client.stat_alloc, pts)
    label = mode_label(client)
    _title(c, G["title"], "Choose your starting stats")
    _scroll(c, G["scroll"], f"Welcome, {display_name(client.player)}. Distribute {pts} points.")
    _seal(c, G["seal"], left, label == "Custom", now, G["reset"], G["reset"].collidepoint(hover))
    E._text(c, "Body", E.font("title", 16), E.TITLE_GOLD, G["body_label"], anchor="center")
    sex = getattr(client, "stat_gender", "male") or "male"
    for r, sx, lab in zip(G["cards"], ("male", "female"), ("Male", "Female")):
        _card(c, r, sx, lab, sex == sx, r.collidepoint(hover))
    _preview(c, G["preview"], sex)
    focus = getattr(client, "stat_focus", None)
    tip = None
    for sk, row, minus, plus in G["rows"]:
        _row(c, client, sk, row, minus, plus, hover, now, focus == sk)
        if plus.collidepoint(hover):
            why = plus_block_reason(client.stat_alloc, sk, client.stat_alloc_base, pts)
            if why:
                tip = (why, plus)
        if minus.collidepoint(hover) and not can_minus(client.stat_alloc, sk):
            tip = ("Nothing added yet", minus)
    cx = G["rows_x"] + G["row_w"] // 2
    err = client.stat_alloc_error or getattr(client, "login_error", "")
    if err:
        E._text(c, err, E.font("body", 16), (225, 95, 85), (cx, G["desc_y"]), anchor="center")
    else:
        desc = {}
        try:
            from client_screens import SKILL_DESCRIPTIONS as desc
        except Exception:
            pass
        d = desc.get(getattr(client, "stat_skill_desc", "") or "", "")
        if d:
            E._text(c, d, E.font("body", 15), E.GOLD_HI, (cx, G["desc_y"]), anchor="center")
    E._text(c, f"Each point raises that skill by 1 level. Confirm when all {pts} are spent.",
            E.font("body", 15), E.MUTED, (cx, G["hint_y"]), anchor="center")
    E._text(c, "Not sure? Pick a preset \u2013 you can train any skill later.",
            E.font("body", 15), E.MUTED, (cx, G["hint_y"] + 20), anchor="center")
    rule = pygame.Surface((G["row_w"] - 60, 1), pygame.SRCALPHA)
    rule.fill((*E.GOLD, 102))
    c.blit(rule, (G["rows_x"] + 30, G["rule_y"]))
    for (name, _p), br in zip(presets(), G["banners"]):
        h = br.collidepoint(hover)
        _banner(c, br, name, label == name, h)
        if h:
            tip = (PRESET_TIPS.get(name, name), br)
    E._text(c, PATH_LINE, E.font("body", 15), E.TITLE_GOLD, (cx, G["path_y"]), anchor="center")
    ok = left == 0
    _confirm(c, G["confirm"], ok, G["confirm"].collidepoint(hover), getattr(client, "_stats_ready_t", None), now)
    if G["confirm"].collidepoint(hover) and not ok:
        tip = (f"Spend all {pts} points", G["confirm"])
    if tip:
        _tooltip(c, tip[0], tip[1], cw)
    if L["scale"] != 1.0:
        c = pygame.transform.smoothscale(c, (L["w"], L["h"]))
    scr.blit(c, (L["ox"], L["oy"]))
    # screen-space click targets (same shape as before)
    rects = {("gender", "male"): _to_screen(L, G["cards"][0]), ("gender", "female"): _to_screen(L, G["cards"][1])}
    for sk, _row_r, minus, plus in G["rows"]:
        rects[(sk, "minus")] = _to_screen(L, minus)
        rects[(sk, "plus")] = _to_screen(L, plus)
    rects[("reset", "reset")] = _to_screen(L, G["reset"])
    client.stat_alloc_rects = rects
    client.stat_preset_rects = [(_to_screen(L, br), dict(p)) for (n, p), br in zip(presets(), G["banners"])]
    client.stat_preset_names = [n for n, _p in presets()]
    client.stat_confirm_rect = _to_screen(L, G["confirm"])
    client._stats_layout = L


def handle_event(client, event):
    """Returns True when the event was used."""
    if not hasattr(client, "stat_alloc_mode"):
        client.stat_alloc_mode = ""
    if event.type == pygame.KEYDOWN:
        if event.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
            client.submit_stat_alloc()
            return True
        if event.key == pygame.K_ESCAPE:
            client.stat_alloc_error = f"Spend all {client.stat_alloc_points} points, then click Confirm."
            return True
        if event.key in (pygame.K_UP, pygame.K_DOWN):
            cur = getattr(client, "stat_focus", None)
            i = SKILLS.index(cur) if cur in SKILLS else (-1 if event.key == pygame.K_DOWN else len(SKILLS))
            i = (i + (1 if event.key == pygame.K_DOWN else -1)) % len(SKILLS)
            client.stat_focus = SKILLS[i]
            client.stat_skill_desc = SKILLS[i]
            return True
        if event.key in (pygame.K_LEFT, pygame.K_RIGHT) and getattr(client, "stat_focus", None) in SKILLS:
            edit(client, client.stat_focus, "plus" if event.key == pygame.K_RIGHT else "minus")
            return True
        return False
    if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
        pos = event.pos
        for key, rect in (getattr(client, "stat_alloc_rects", None) or {}).items():
            if not rect.collidepoint(pos):
                continue
            a, b = key
            if a == "gender":
                client.stat_gender = b
                client.stat_alloc_error = ""
            elif a == "reset":
                reset(client)
            else:
                client.stat_focus = a
                if not edit(client, a, b):
                    client.stat_skill_desc = a
            return True
        names = getattr(client, "stat_preset_names", None) or [n for n, _p in presets()]
        for (rect, _pts), name in zip(getattr(client, "stat_preset_rects", None) or [], names):
            if rect.collidepoint(pos):
                apply_preset(client, name)
                return True
        cr = getattr(client, "stat_confirm_rect", None)
        if cr is not None and cr.collidepoint(pos):
            client.submit_stat_alloc()
            return True
    return False
