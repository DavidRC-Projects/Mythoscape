"""
teleport_ui.py: Teleport window restyle (ONBOARDING/teleport_screen/TELEPORT_SCREEN_STYLE_SPEC.md).

Same look as Equipment & Stats (equipment_ui_v2): gold-framed wood window, plaque title, ribbon
section banners, medallion cards, gold scrollbar and a bronze Close plaque. David's decisions:
no search field; every place is listed, unvisited ones locked ("Walk there to unlock"); the place
you stand at shows "You are here" and is disabled; height min(760, screen - 48); a 0.8s rune cast.

client.draw_teleport_modal / draw_teleport_fx call in here; if anything raises, the old flat window
and veil are drawn instead (error fallback only). Click targets stay in client.teleport_row_rects
as (kind, rect, payload) with kind in close / walk / dest / locked / here.
"""
import math
import os
import time
import pygame

import equipment_ui_v2 as E

WIN_W, WIN_H, EDGE = 520, 760, 16
CARD_H, CARD_GAP, RIBBON_H = 60, 6, 34
CAST_S, ARRIVE_S, FLASH_OUT_S, WAIT_S = 0.8, 1.3, 0.45, 2.0
HERE_RADIUS = 6                      # Chebyshev tiles from a landing that count as "here"
SUBTITLE = "Places you have walked to are unlocked."
LOCKED_LINE = "Walk there to unlock"
BG = (26, 20, 14)
FRAME = (42, 30, 20)
GOLD = (179, 148, 101)
GOLD_HI = (230, 203, 142)
TITLE = (206, 174, 115)
GLOW = (255, 211, 107)
GLOW2 = (242, 193, 78)
CARD = (31, 24, 18)
CARD_HOT = (42, 32, 24)
CARD_DOWN = (23, 17, 12)
CARD_RIM = (58, 46, 34)
PLAQUE = (28, 21, 15)
CLOTH = (58, 36, 24)
RAIL = (90, 70, 48)
TEXT = (234, 219, 192)
MUTED = (168, 154, 132)
LILAC = (185, 166, 232)
LOCK = (158, 43, 37)
MED_BG = (40, 31, 24)
ICONS = {
    "home": "home", "village": "village", "bank": "bank", "outfitters": "outfitters",
    "void": "void", "stonehaven": "stonehaven", "keep": "keep", "harbour": "harbour",
    "estate": "estate", "kings_row_south": "kings_row", "realm": "realm",
    # King's Realm castles share the keep medallion; the arena uses the plaza fountain.
    "gothic": "keep", "king": "keep", "rose": "keep", "sky": "keep", "arena": "realm",
}
_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets", "ui", "teleport")
_ART = {}
_CACHE = {}


# ---------------------------------------------------------------- pure helpers (tested)
def window_rect(sw, sh):
    w = min(WIN_W, sw - EDGE)
    h = min(WIN_H, sh - 48)
    return pygame.Rect((sw - w) // 2, max(0, (sh - h) // 2), w, h)


def current_dest_id(client, entries):
    """The landing the player stands at (same realm side, within HERE_RADIUS), else None."""
    p = client.player or {}
    if "x" not in p:
        return None
    in_realm = bool(getattr(client, "_in_castle_realm", lambda: False)())
    in_dungeon = bool(getattr(client, "dungeon", None)) and not in_realm
    if in_dungeon:
        return None
    best, best_d = None, HERE_RADIUS + 1
    for d in entries:
        if (d.get("where") == "castle") != in_realm:
            continue
        dist = max(abs(int(p["x"]) - int(d["x"])), abs(int(p["y"]) - int(d["y"])))
        if dist < best_d:
            best, best_d = d["id"], dist
    return best


def entries(client, all_dests):
    """Home (if owned) first, then every destination in content order, each with a state."""
    marks = client._teleport_marks()
    out = []
    home = client._home_destination()
    if home:
        out.append({"id": "home", "label": home["label"], "blurb": home["blurb"], "where": "overworld",
                    "x": home["x"], "y": home["y"], "home": True})
    out += [dict(d) for d in all_dests if d.get("id") != "home"]
    here = current_dest_id(client, out)
    for d in out:
        if d["id"] == here:
            d["state"] = "here"
        elif d["id"] == "home" or d["id"] in marks:
            d["state"] = "open"
        else:
            d["state"] = "locked"
    return out


def groups(items):
    kingdom = [d for d in items if d.get("where") != "castle"]
    realm = [d for d in items if d.get("where") == "castle"]
    return [g for g in (("The Kingdom", kingdom), ("King's Realm", realm)) if g[1]]


def toast(client, text):
    client.teleport_toast = {"text": text, "until": time.time() + 2.2}


# ---------------------------------------------------------------- art
def _icon(key, size, grey=False):
    k = (key, size, grey)
    if k in _CACHE:
        return _CACHE[k]
    img = None
    try:
        if key not in _ART:
            _ART[key] = pygame.image.load(os.path.join(_DIR, f"{key}.png")).convert_alpha()
        img = pygame.transform.smoothscale(_ART[key], (size, size))
        if grey:
            g = img.copy()
            px = pygame.surfarray.pixels3d(g)
            lum = (px[..., 0] * 0.3 + px[..., 1] * 0.59 + px[..., 2] * 0.11) * 0.6
            px[..., 0] = lum; px[..., 1] = lum; px[..., 2] = lum
            del px
            img = g
    except Exception as e:                       # missing art: plain medallion, logged once
        E._log_once(f"teleport icon {key}", e)
        img = None
    _CACHE[k] = img
    return img


def _wood(w, h):
    k = ("wood", w, h)
    if k not in _CACHE:
        s = pygame.Surface((w, h))
        s.fill(BG)
        for y in range(0, h, 3):
            v = int(6 * math.sin(y * 0.21) + 4 * math.sin(y * 0.047 + 1.3))
            pygame.draw.line(s, (max(0, 26 + v), max(0, 20 + v), max(0, 14 + v // 2)), (0, y), (w, y))
        for i in range(40):
            y = (i * 97) % h
            pygame.draw.line(s, (32, 24, 17), (0, y), (w, y + (i % 5) - 2), 1)
        _CACHE[k] = s
    return _CACHE[k]


def _vignette(sw, sh):
    k = ("vig", sw, sh)
    if k not in _CACHE:
        small = pygame.Surface((64, 64), pygame.SRCALPHA)
        for y in range(64):
            for x in range(64):
                r = math.hypot((x - 31.5) / 32, (y - 31.5) / 32) / 1.414
                a = 0 if r < 0.3 else min(1.0, (r - 0.3) / 0.7)
                small.set_at((x, y), (2, 3, 5, int(70 + 121 * a)))
        _CACHE[k] = pygame.transform.smoothscale(small, (sw, sh))
    return _CACHE[k]


def _corner(s, x, y, dx, dy):
    pygame.draw.polygon(s, FRAME, [(x, y), (x + dx * 40, y), (x, y + dy * 40)])
    for i, ln in enumerate((44, 30)):
        o = 4 + i * 6
        pygame.draw.line(s, GOLD, (x + dx * o, y + dy * o), (x + dx * (o + ln), y + dy * o), 2 - i)
        pygame.draw.line(s, GOLD, (x + dx * o, y + dy * o), (x + dx * o, y + dy * (o + ln)), 2 - i)
    pygame.draw.circle(s, GOLD_HI, (x + dx * 12, y + dy * 12), 4)
    pygame.draw.circle(s, FRAME, (x + dx * 12, y + dy * 12), 2)
    pygame.draw.arc(s, GOLD, pygame.Rect(x + dx * 16 - (14 if dx < 0 else 0), y + dy * 16 - (14 if dy < 0 else 0), 14, 14), 0, math.tau, 1)


def _diamond(s, cx, cy, r, col, fill=True):
    pts = [(cx, cy - r), (cx + r, cy), (cx, cy + r), (cx - r, cy)]
    pygame.draw.polygon(s, col, pts, 0 if fill else 1)


def _frame(s, box):
    s.blit(_wood(box.w, box.h), box.topleft)
    pygame.draw.rect(s, (14, 10, 7), box.inflate(4, 4), 2)
    pygame.draw.rect(s, FRAME, box, 9)
    pygame.draw.rect(s, (66, 48, 32), box.inflate(-4, -4), 1)
    pygame.draw.rect(s, GOLD, box, 1)
    pygame.draw.rect(s, GOLD, box.inflate(-18, -18), 1)
    pygame.draw.rect(s, (12, 9, 6), box.inflate(-20, -20), 1)
    for cx, cy, dx, dy in ((box.left, box.top, 1, 1), (box.right - 1, box.top, -1, 1),
                           (box.left, box.bottom - 1, 1, -1), (box.right - 1, box.bottom - 1, -1, -1)):
        _corner(s, cx, cy, dx, dy)


def _plaque(s, cx, top, text):
    f = E.font("title", 30)
    t = f.render(text, True, TITLE)
    r = pygame.Rect(0, 0, t.get_width() + 80, 50)
    r.midtop = (cx, top)
    pygame.draw.rect(s, PLAQUE, r, border_radius=4)
    pygame.draw.rect(s, GOLD, r, 1, border_radius=4)
    pygame.draw.rect(s, (60, 46, 32), r.inflate(-6, -6), 1, border_radius=3)
    for side in (-1, 1):
        x = r.left if side < 0 else r.right
        _diamond(s, x, r.centery, 8, GOLD)
        _diamond(s, x, r.centery, 4, PLAQUE)
        pygame.draw.line(s, GOLD, (x + side * 10, r.centery), (x + side * 30, r.centery), 1)
        _diamond(s, x + side * 34, r.centery, 3, GOLD)
    s.blit(t, (r.centerx - t.get_width() // 2, r.centery - t.get_height() // 2 - 1))
    return r


def _ribbon(s, rect, text):
    f = E.font("title", 18)
    t = f.render(text, True, GOLD_HI)
    w = t.get_width() + 70
    r = pygame.Rect(0, 0, w, RIBBON_H - 6)
    r.center = rect.center
    line = pygame.Surface((rect.w, 1), pygame.SRCALPHA)
    line.fill((*GOLD, 153))
    s.blit(line, (rect.x, rect.centery))
    for side in (-1, 1):
        x = r.left - 22 if side < 0 else r.right + 22
        _diamond(s, x, rect.centery, 5, GOLD, False)
        _diamond(s, rect.x + 8 if side < 0 else rect.right - 8, rect.centery, 3, GOLD)
    pts = [(r.left - 14, r.centery), (r.left, r.top), (r.right, r.top), (r.right + 14, r.centery),
           (r.right, r.bottom), (r.left, r.bottom)]
    pygame.draw.polygon(s, CLOTH, pts)
    pygame.draw.polygon(s, GOLD, pts, 1)
    pygame.draw.line(s, (90, 58, 38), (r.left + 2, r.top + 3), (r.right - 2, r.top + 3), 1)
    s.blit(t, (r.centerx - t.get_width() // 2, r.centery - t.get_height() // 2 - 1))


def _home_badge(s, cx, cy):
    pts = [(cx, cy - 25), (cx + 20, cy - 13), (cx + 20, cy + 16), (cx - 20, cy + 16), (cx - 20, cy - 13)]
    pygame.draw.polygon(s, (74, 50, 30), pts)
    pygame.draw.polygon(s, GOLD, pts, 2)
    star = []
    for i in range(10):
        a = -math.pi / 2 + i * math.pi / 5
        rr = 8 if i % 2 == 0 else 3.5
        star.append((cx + rr * math.cos(a), cy - 7 + rr * math.sin(a)))
    pygame.draw.polygon(s, GLOW, star)
    t = E.font("body", 12).render("Home", True, TEXT)
    s.blit(t, (cx - t.get_width() // 2, cy + 1))


def _padlock(s, x, y):
    pygame.draw.arc(s, (210, 190, 170), pygame.Rect(x + 2, y, 10, 11), 0, math.pi, 2)
    body = pygame.Rect(x, y + 6, 14, 10)
    pygame.draw.rect(s, LOCK, body, border_radius=2)
    pygame.draw.rect(s, (40, 12, 10), body, 1, border_radius=2)
    pygame.draw.circle(s, (30, 10, 8), (x + 7, y + 10), 2)


def _card(s, rect, d, hot, down, now):
    state = d.get("state")
    layer = pygame.Surface(rect.size, pygame.SRCALPHA)
    r = layer.get_rect()
    active = state == "open"
    bg = CARD_DOWN if (active and down) else CARD_HOT if (active and hot) else CARD
    pygame.draw.rect(layer, bg, r, border_radius=6)
    pygame.draw.rect(layer, CARD_RIM, r, 1, border_radius=6)
    # medallion
    mc = (r.x + 36, r.centery)
    pygame.draw.circle(layer, MED_BG, mc, 23)
    img = _icon(ICONS.get(d["id"], "village"), 42, grey=(state == "locked"))
    if img is not None:
        layer.blit(img, (mc[0] - 21, mc[1] - 21))
    pygame.draw.circle(layer, GOLD if state != "locked" else (110, 96, 74), mc, 23, 2)
    if state == "locked":
        _padlock(layer, mc[0] + 10, mc[1] + 6)
    name_col = GOLD_HI if state != "locked" else (150, 136, 112)
    name = E.font("title", 19).render(d["label"], True, name_col)
    layer.blit(name, (r.x + 70, r.y + 7))
    sub_text = LOCKED_LINE if state == "locked" else d.get("blurb", "")
    sub = E.font("body", 16).render(sub_text, True, MUTED if state != "locked" else (140, 120, 104))
    layer.blit(sub, (r.x + 70, r.y + 33))
    if d.get("home"):
        _home_badge(layer, r.right - 34, r.centery + 3)
    if state == "here":
        tag = E.font("body", 14).render("You are here", True, LILAC)
        tr = pygame.Rect(0, 0, tag.get_width() + 18, 24)
        tr.midright = (r.right - 12, r.centery)
        pygame.draw.rect(layer, (36, 30, 48), tr, border_radius=10)
        pygame.draw.rect(layer, LILAC, tr, 1, border_radius=10)
        layer.blit(tag, (tr.x + 9, tr.centery - tag.get_height() // 2))
        layer.set_alpha(140)                        # opacity .55
    dy = 1 if (active and down) else 0
    if active and hot:
        glow = pygame.Surface((rect.w + 24, rect.h + 24), pygame.SRCALPHA)
        for i in range(6):
            pygame.draw.rect(glow, (*GLOW2, 22), glow.get_rect().inflate(-i * 4, -i * 4), 2, border_radius=12)
        s.blit(glow, (rect.x - 12, rect.y - 12 + dy))
    s.blit(layer, (rect.x, rect.y + dy))
    if active and hot:
        pygame.draw.rect(s, GLOW, rect.move(0, dy), 2, border_radius=6)
        for x, side in ((rect.left, -1), (rect.right, 1)):
            cy = rect.centery + dy
            pygame.draw.polygon(s, GLOW, [(x + side * 7, cy), (x - side * 2, cy - 7), (x - side * 2, cy + 7)])


def _scrollbar(s, track, thumb, hot):
    pygame.draw.rect(s, PLAQUE, track, border_radius=4)
    pygame.draw.line(s, RAIL, (track.centerx, track.top + 4), (track.centerx, track.bottom - 4), 2)
    for y in (track.top, track.bottom):
        _diamond(s, track.centerx, y, 5, GOLD)
    col = GOLD_HI if hot else GOLD
    pygame.draw.rect(s, col, thumb, border_radius=4)
    _diamond(s, thumb.centerx, thumb.centery, 4, (90, 66, 40))


def _button(s, rect, text, hot):
    top, bot = (140, 90, 43), (90, 58, 30)
    for i in range(rect.h):
        u = i / max(1, rect.h - 1)
        c = tuple(int(top[k] + (bot[k] - top[k]) * u) for k in range(3))
        if hot:
            c = tuple(min(255, v + 18) for v in c)
        pygame.draw.line(s, c, (rect.x + 2, rect.y + i), (rect.right - 3, rect.y + i))
    pygame.draw.rect(s, GLOW if hot else GOLD, rect, 1, border_radius=4)
    t = E.font("title", 17).render(text, True, (243, 230, 207))
    s.blit(t, (rect.centerx - t.get_width() // 2, rect.centery - t.get_height() // 2 - 1))


def _toast(s, client, box, now):
    tt = getattr(client, "teleport_toast", None)
    if not tt or now > tt["until"]:
        return
    t = E.font("body", 16).render(tt["text"], True, TEXT)
    r = pygame.Rect(0, 0, t.get_width() + 30, 34)
    r.midbottom = (box.centerx, box.bottom - 70)
    pygame.draw.rect(s, PLAQUE, r, border_radius=6)
    pygame.draw.rect(s, GOLD, r, 1, border_radius=6)
    s.blit(t, (r.centerx - t.get_width() // 2, r.centery - t.get_height() // 2))


# ---------------------------------------------------------------- window
def draw(client, all_dests, taught):
    scr = client.screen
    sw, sh = scr.get_size()
    now = time.time()
    box = window_rect(sw, sh)
    client.teleport_box = box
    client.teleport_row_rects = []
    client.teleport_scroll_meta = None
    mouse = pygame.mouse.get_pos()
    down = pygame.mouse.get_pressed()[0]
    scr.blit(_vignette(sw, sh), (0, 0))
    _frame(scr, box)
    plaque = _plaque(scr, box.centerx, box.y + 16, "Teleport")
    close = pygame.Rect(0, 0, 140, 44)
    close.bottomright = (box.right - 22, box.bottom - 16)
    _button(scr, close, "Close", close.collidepoint(mouse))
    client.teleport_row_rects.append(("close", close, None))
    body = E.font("body", 15)
    if not taught:
        lines = ["Wizard Elowen can teach you this spell.",
                 "She stands on the grass just northwest of the village crossroads.",
                 "Talk to her for the Village and the King's Realm,",
                 "then walk the map to unlock more places."]
        y = plaque.bottom + 24
        for ln in lines:
            t = body.render(ln, True, TEXT)
            if t.get_width() > box.w - 40:
                t = pygame.transform.smoothscale(t, (box.w - 40, t.get_height()))
            scr.blit(t, (box.centerx - t.get_width() // 2, y))
            y += 24
        walk = pygame.Rect(0, 0, 200, 44)
        walk.bottomleft = (box.x + 22, box.bottom - 16)
        _button(scr, walk, "Walk to Elowen", walk.collidepoint(mouse))
        client.teleport_row_rects.append(("walk", walk, None))
        _toast(scr, client, box, now)
        return
    sub = E.font("body", 16).render(SUBTITLE, True, TEXT)
    sub.set_alpha(217)
    scr.blit(sub, (box.centerx - sub.get_width() // 2, plaque.bottom + 8))

    items = entries(client, all_dests)
    grouped = groups(items)
    list_top = plaque.bottom + 36
    list_bottom = close.top - 10
    view_h = max(40, list_bottom - list_top)
    clip = pygame.Rect(box.x + 14, list_top, box.w - 28, view_h)
    content_h, starts = 0, []
    for title, ds in grouped:
        starts.append(content_h)
        content_h += RIBBON_H + 4 + len(ds) * (CARD_H + CARD_GAP)
    max_scroll = max(0, content_h - view_h)
    client.teleport_scroll = max(0, min(max_scroll, int(client.teleport_scroll or 0)))
    scroll = client.teleport_scroll
    card_x = box.x + 26
    card_w = box.w - 52 - (16 if max_scroll > 0 else 0)
    track = thumb = None
    if max_scroll > 0:
        track = pygame.Rect(box.right - 30, list_top + 6, 8, view_h - 12)
        th = max(36, int(track.h * view_h / max(1, content_h)))
        ty = track.y + int((track.h - th) * (scroll / max_scroll))
        thumb = pygame.Rect(track.x, ty, track.w, th)
        _scrollbar(scr, track, thumb, thumb.collidepoint(mouse) or bool(getattr(client, "teleport_drag", None)))
    client.teleport_scroll_meta = {"clip": clip, "track": track, "thumb": thumb, "list_top": list_top,
                                   "view_h": view_h, "max_scroll": max_scroll}
    prev = scr.get_clip()
    scr.set_clip(clip)
    y = list_top - scroll
    for (title, ds), start in zip(grouped, starts):
        rib = pygame.Rect(card_x, y, card_w, RIBBON_H)
        if rib.bottom >= list_top and rib.top <= list_bottom:
            _ribbon(scr, rib, title)
        y += RIBBON_H + 4
        for d in ds:
            row = pygame.Rect(card_x, y, card_w, CARD_H)
            if row.bottom >= list_top and row.top <= list_bottom:
                hot = row.collidepoint(mouse) and clip.collidepoint(mouse)
                _card(scr, row, d, hot, hot and down, now)
                kind = {"open": "dest", "locked": "locked", "here": "here"}[d["state"]]
                client.teleport_row_rects.append((kind, row, d["id"]))
            y += CARD_H + CARD_GAP
    # sticky ribbon: the section being scrolled keeps its banner at the top of the list
    for i, (title, ds) in enumerate(grouped):
        nxt = starts[i + 1] if i + 1 < len(starts) else content_h
        if starts[i] < scroll < nxt:
            ry = min(list_top, list_top + nxt - scroll - RIBBON_H)
            band = pygame.Rect(clip.x, ry, clip.w, RIBBON_H)
            scr.blit(_wood(box.w, box.h).subsurface(pygame.Rect(band.x - box.x, max(0, band.y - box.y), band.w, band.h)), band.topleft)
            _ribbon(scr, pygame.Rect(card_x, ry, card_w, RIBBON_H), title)
    scr.set_clip(prev)
    _toast(scr, client, box, now)


# ---------------------------------------------------------------- cast / arrival fx
def start_cast(client, dest_id, label):
    now = time.time()
    p = client.player or {}
    # Freeze screen feet at cast start. Leaving castle realm swaps the map mid-spell;
    # re-querying world coords then parks the rune in a corner of the overworld view.
    client.teleport_fx = {
        "phase": "cast", "start": now, "until": now + CAST_S, "label": label,
        "dest": dest_id, "pos": (p.get("x"), p.get("y")),
        "feet": _feet(client),
    }


def start_arrive(client, label):
    now = time.time()
    client.teleport_fx = {"phase": "arrive", "start": now, "until": now + ARRIVE_S, "label": label or ""}


def _feet(client):
    """Player foot pixel in the map panel, or panel centre if off-screen / unknown."""
    import client as C
    mid = (C.MAP_W // 2, C.MAP_H // 2)
    if not client.player:
        return mid
    try:
        px, py = client.player_xy()
        cam_x, cam_y = client.camera_origin()
        sx, sy = client.world_to_view_offset(px, py, cam_x, cam_y)
        fx = int(sx * C.TILE + C.TILE // 2)
        fy = int(sy * C.TILE + C.TILE * 0.8)
    except Exception:
        return mid
    if not (0 <= fx < C.MAP_W and 0 <= fy < C.MAP_H):
        return mid
    return fx, fy


def _rune_circle(s, c, u, now):
    cx, cy = c
    R = 68
    layer = pygame.Surface((R * 2 + 40, R + 40), pygame.SRCALPHA)
    ox, oy = R + 20, R // 2 + 20
    sweep = min(1.0, u * 1.4)
    glow_a = int(150 * min(1.0, u * 2))
    for k in range(5):
        g = pygame.Rect(0, 0, (R - 6) * 2 - k * 18, R - 6 - k * 9)
        g.center = (ox, oy)
        pygame.draw.ellipse(layer, (*LILAC, glow_a // 5), g)
    for rr, w in ((R + 2, 1), (R, 3), (R - 13, 2), (R - 30, 1)):
        rect = pygame.Rect(ox - rr, oy - rr // 2, rr * 2, rr)
        pygame.draw.arc(layer, (*GLOW, 90 if w == 1 else 245), rect, -math.pi / 2, -math.pi / 2 + math.tau * sweep, w)
    n = 12
    for i in range(int(n * sweep)):
        a = i * math.tau / n + now * 1.6
        x = ox + math.cos(a) * (R - 6.5)
        y = oy + math.sin(a) * (R - 6.5) / 2
        pygame.draw.line(layer, (*GLOW, 240), (x - 4, y - 2), (x + 4, y + 2), 2)
        pygame.draw.line(layer, (*GLOW, 240), (x, y - 3), (x, y + 3), 1)
    if sweep > 0.4:
        for off in (0, math.pi / 3):
            tri = [(ox + math.cos(a) * (R - 14), oy + math.sin(a) * (R - 14) / 2)
                   for a in (now * -1.2 + off + k * math.tau / 3 for k in range(3))]
            pygame.draw.polygon(layer, (*GLOW, int(220 * min(1, (sweep - 0.4) / 0.4))), tri, 1)
    s.blit(layer, (cx - ox, cy - oy))
    # rising motes
    beam = pygame.Surface((R * 2, 150), pygame.SRCALPHA)
    for k in range(16):
        ph = (now * 0.9 + k * 0.137) % 1.0
        x = R + math.cos(k * 2.4) * R * 0.75
        y = 150 - ph * 140 * (0.4 + u)
        pygame.draw.circle(beam, (*GLOW, int(230 * (1 - ph))), (int(x), int(y)), 2 if k % 3 else 3)
    col = pygame.Surface((R, 140), pygame.SRCALPHA)
    for yy in range(140):
        pygame.draw.line(col, (*LILAC, int(70 * u * (yy / 140))), (0, yy), (R, yy))
    beam.blit(col, (R // 2, 10))
    s.blit(beam, (cx - R, cy - 150))


def draw_fx(client):
    fx = client.teleport_fx
    if not fx:
        return
    now = time.time()
    phase = fx.get("phase", "arrive")
    s = client.screen
    sw, sh = s.get_size()
    if phase == "cast":
        p = client.player or {}
        if fx.get("pos") != (p.get("x"), p.get("y")):
            client.teleport_fx = None
            toast(client, "Teleport cancelled.")
            client.chat_log.append("[!] Teleport cancelled — you moved.")
            return
        u = min(1.0, (now - fx["start"]) / CAST_S)
        _rune_circle(s, fx.get("feet") or _feet(client), u, now)
        if u > 0.85:                                  # white-gold flash builds over the last 0.12s
            a = int(210 * (u - 0.85) / 0.15)
            veil = pygame.Surface((sw, sh), pygame.SRCALPHA)
            veil.fill((255, 240, 205, a))
            s.blit(veil, (0, 0))
        if now >= fx["until"]:
            client.net.send("TELEPORT", dest=fx["dest"])
            client.teleport_fx = {"phase": "wait", "start": now, "until": now + WAIT_S, "label": fx["label"]}
        return
    if phase == "wait":
        if now >= fx["until"]:
            client.teleport_fx = None
            return
        veil = pygame.Surface((sw, sh), pygame.SRCALPHA)
        veil.fill((255, 240, 205, 200))
        s.blit(veil, (0, 0))
        return
    if now >= fx["until"]:
        client.teleport_fx = None
        return
    u = (now - fx["start"]) / ARRIVE_S
    veil = pygame.Surface((sw, sh), pygame.SRCALPHA)
    el = now - fx["start"]
    if el < FLASH_OUT_S:
        veil.fill((255, 240, 205, int(200 * (1 - el / FLASH_OUT_S))))
        s.blit(veil, (0, 0))
    if fx.get("label"):
        f = E.font("title", 26)
        t = f.render(fx["label"], True, TITLE)
        r = pygame.Rect(0, 0, t.get_width() + 70, 46)
        import client as C
        r.center = (C.MAP_W // 2, C.MAP_H // 2 - 70)
        band = pygame.Surface(r.size, pygame.SRCALPHA)
        a = int(255 * min(1.0, (1 - u) * 3.0))
        band.fill((*PLAQUE, int(a * 0.9)))
        pygame.draw.rect(band, (*GOLD, a), band.get_rect(), 1)
        t.set_alpha(a)
        band.blit(t, (35, r.h // 2 - t.get_height() // 2 - 1))
        s.blit(band, r.topleft)
