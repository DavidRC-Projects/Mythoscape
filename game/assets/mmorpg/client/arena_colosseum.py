"""Crownfall Colosseum life layer (5 Nov 2026).

Drawn on top of the painted arena bowl (castle_realm_renderer._queue_arena):
  * animated spectators (the baked crowd is static; ~1.7k of them cheer live),
  * house pennants waving on the parapet, brazier flame glow + sparks,
  * worn sand: blood stains, scuffs, footprints, weapon gouges,
  * sun shafts and drifting dust over the pit,
  * battle feedback: hit flashes, dust kicks, death bursts with a lasting stain,
  * role glyphs under arena soldiers (tank / duelist / skirmisher / medic / line),
  * a short skippable battle intro card and a victory crowd roar.

Pure presentation: it reads client.arena_match / hud and never sends anything,
so rewards, combat timing and results are untouched.
"""
from __future__ import annotations

import json
import math
import os
import random
import time

import pygame

_HERE = os.path.dirname(os.path.abspath(__file__))
_DIR = os.path.join(_HERE, "assets", "castle_realm", "arena")
_META = None
_CACHE: dict = {}
_FX: dict = {"hits": [], "stains": [], "prev": {}, "match": None, "intro_t0": 0.0,
             "intro_skip": False, "won_t0": 0.0, "result_key": None}

ROLE_OF = {"levy": "fodder", "man_at_arms": "line", "veteran": "line", "skirmisher": "flank",
           "bulwark": "tank", "zealot": "glass", "duelist": "elite", "medic": "support", "mythos_guard": "elite"}


def meta():
    global _META
    if _META is None:
        try:
            with open(os.path.join(_DIR, "colosseum.json")) as fh:
                _META = json.load(fh)
        except (OSError, ValueError):
            _META = {}
    return _META


def _sheet(tile):
    res = "2x" if tile > 40 else "1x"
    key = ("sheet", res, tile)
    if key in _CACHE:
        return _CACHE[key]
    path = os.path.join(_DIR, "sprites", res, "crowd_sheet.png")
    try:
        raw = pygame.image.load(path).convert_alpha()
    except (pygame.error, OSError, FileNotFoundError):
        _CACHE[key] = None
        return None
    cw, ch = meta().get("cell_1x", [14, 20])
    cols = int(meta().get("sheet_cols") or 1)
    n = raw.get_height() // (ch * (2 if res == "2x" else 1))
    sc = tile / 40.0
    tw, th = max(2, int(cw * sc)), max(2, int(ch * sc))
    big = pygame.transform.smoothscale(raw, (tw * 3 * cols, th * n))
    _CACHE[key] = (big, tw, th, cols)
    return _CACHE[key]


def _excitement(client):
    m = getattr(client, "arena_match", None) or {}
    now = time.time()
    if _FX["won_t0"] and now - _FX["won_t0"] < 9:
        return 1.0
    if not m.get("active"):
        return 0.22
    hud = m.get("hud") or {}
    if (m.get("phase") or hud.get("phase")) == "preview":
        return 0.45
    return 0.35 + 0.6 * min(1.0, max(0.0, float(hud.get("crowd") or 50) / 100.0))


def _art_to_screen(client, ax, ay, art, cam_x, cam_y, tile):
    wx = art[0] + ax / 40.0
    wy = art[1] + ay / 40.0
    sx, sy = client.world_to_view_offset(wx, wy, cam_x, cam_y)
    return sx * tile, sy * tile


def queue(client, draw_list, cam_x, cam_y, tile, hd, arena):
    """Add the colosseum layers to the world draw list. Cheap when off-screen."""
    m = meta()
    art = (hd or {}).get("art_tiles") or []
    if not m or len(art) < 4:
        return
    view = client.screen.get_rect()
    ox, oy = _art_to_screen(client, 0, 0, art, cam_x, cam_y, tile)
    span_w, span_h = (art[2] - art[0]) * tile, (art[3] - art[1]) * tile
    if ox > view.w or oy > view.h or ox + span_w < 0 or oy + span_h < 0:
        return
    pit = arena.get("pit") or []
    if len(pit) >= 4:
        px0, py0, px1, py1 = (int(v) for v in pit)
        back_sy = client.world_to_view_offset(px0, py0 + 1, cam_x, cam_y)[1] * tile
        front_row = max(py1, int(arena.get("front_sort_row") or py1))
        front_sy = client.world_to_view_offset(px0, front_row, cam_x, cam_y)[1] * tile + tile
    else:
        back_sy, front_sy = oy, oy + span_h
    t = time.time()
    k = tile / 40.0
    draw_list.append((back_sy, 40.5, lambda: _draw_sand(client, cam_x, cam_y, tile, pit)))
    draw_list.append((back_sy, 41, lambda: _draw_crowd(client, 0, ox, oy, k, tile, view, t)))
    draw_list.append((front_sy, 46, lambda: _draw_crowd(client, 1, ox, oy, k, tile, view, t)))
    draw_list.append((back_sy, 42, lambda: _draw_braziers(client, ox, oy, k, tile, view, t)))
    draw_list.append((back_sy, 43, lambda: _draw_pennants(client, 0, ox, oy, k, view, t)))
    draw_list.append((front_sy, 47, lambda: _draw_pennants(client, 1, ox, oy, k, view, t)))
    draw_list.append((10**9 - 5, 0, lambda: _draw_air(client, cam_x, cam_y, tile, pit, view, t)))
    if getattr(client, "arena_match", None):
        march_update(client)
        draw_list.append((10**9 - 6, 0, lambda: _draw_battle_fx(client, cam_x, cam_y, tile, view)))
        _queue_standards(client, draw_list, cam_x, cam_y, tile, t)


# ---------------------------------------------------------------- crowd
def _draw_crowd(client, layer, ox, oy, k, tile, view, t):
    sh = _sheet(tile)
    if sh is None:
        return
    img, tw, th, cols = sh
    e = _excitement(client)
    screen = client.screen
    vx0, vy0, vx1, vy1 = -tw, -th, view.w + tw, view.h + th
    speed = 1.3 + 2.2 * e
    thresh = 1.0 - 2.0 * e
    for ax, ay, ly, vi, ph in meta().get("crowd") or ():
        if ly != layer:
            continue
        x = ox + ax * k
        y = oy + ay * k
        if x < vx0 or x > vx1 or y < vy0 or y > vy1:
            continue
        c = math.sin((t * speed + ph * 7.0) * 2.1 + ph * 40)
        fr = 2 if c > thresh + (1 - thresh) * .55 else (1 if c > thresh else 0)
        bob = int(-abs(c) * 1.5 * k) if fr else 0
        screen.blit(img, (int(x - tw / 2), int(y - th + 4 * k + bob)),
                    pygame.Rect(((vi % cols) * 3 + fr) * tw, (vi // cols) * th, tw, th))


# ---------------------------------------------------------------- pennants
def _draw_pennants(client, layer, ox, oy, k, view, t):
    houses = meta().get("houses") or [[(150, 30, 30), (220, 180, 70)]]
    screen = client.screen
    for i, (ax, ay, hi, ly) in enumerate(meta().get("pennants") or ()):
        if ly != layer:
            continue
        x, y = ox + ax * k, oy + ay * k
        if x < -80 * k or x > view.w + 80 * k or y < -120 * k or y > view.h + 40 * k:
            continue
        base, trim = houses[hi % len(houses)]
        pole_h = 70 * k
        top = (x, y - pole_h)
        pygame.draw.line(screen, (60, 44, 28), (x, y), top, max(1, int(3 * k)))
        pygame.draw.circle(screen, (226, 196, 110), (int(top[0]), int(top[1])), max(1, int(3 * k)))
        L, Hh = 46 * k, 20 * k
        pts_top, pts_bot = [], []
        for j in range(9):
            u = j / 8.0
            w = math.sin(t * 3.2 + i * 0.9 - u * 4.0) * (2 + 6 * u) * k
            pts_top.append((top[0] + 2 * k + u * L, top[1] + 3 * k + w))
            pts_bot.append((top[0] + 2 * k + u * L, top[1] + 3 * k + Hh * (1 - .45 * u) + w))
        poly = pts_top + list(reversed(pts_bot))
        pygame.draw.polygon(screen, base, poly)
        shade = tuple(max(0, int(c * .7)) for c in base)
        for j in range(1, 8, 2):
            pygame.draw.line(screen, shade, pts_top[j], pts_bot[j], max(1, int(2 * k)))
        pygame.draw.lines(screen, trim, False, pts_top, max(1, int(2 * k)))
        mid = pts_top[3][0], (pts_top[3][1] + pts_bot[3][1]) / 2
        pygame.draw.circle(screen, trim, (int(mid[0]), int(mid[1])), max(1, int(4 * k)))


# ---------------------------------------------------------------- fire
def _glow(radius, col):
    """Additive radial glow (RGB, black outside) — BLEND_ADD ignores alpha."""
    key = ("glow", radius, col)
    s = _CACHE.get(key)
    if s is None:
        s = pygame.Surface((radius * 2, radius * 2))
        s.fill((0, 0, 0))
        steps = 18
        for i in range(steps, 0, -1):
            r = int(radius * i / steps)
            f = (1 - i / steps) ** 2 * 0.55
            pygame.draw.circle(s, tuple(int(c * f) for c in col), (radius, radius), r)
        _CACHE[key] = s
    return s


def _draw_braziers(client, ox, oy, k, tile, view, t):
    screen = client.screen
    for i, (ax, ay) in enumerate(meta().get("braziers") or ()):
        x, y = ox + ax * k, oy + ay * k
        if x < -200 or x > view.w + 200 or y < -200 or y > view.h + 200:
            continue
        fl = 0.8 + 0.2 * math.sin(t * 9 + i) + 0.1 * math.sin(t * 23 + i * 3)
        r = max(6, int(52 * k * fl))
        g = _glow(r, (255, 160, 60))
        screen.blit(g, (int(x - r), int(y - r - 10 * k)), special_flags=pygame.BLEND_ADD)
        rnd = random.Random(i * 97 + int(t * 10))
        for n in range(4):
            age = ((t * 0.9 + n * 0.25 + i * 0.13) % 1.0)
            sx = x + math.sin(n * 2.1 + t * 2 + i) * 6 * k
            sy = y - 14 * k - age * 46 * k
            a = int(255 * (1 - age))
            pygame.draw.circle(screen, (255, 200 - int(age * 120), 80), (int(sx), int(sy)), max(1, int(1.6 * k * (1 - age) + .5)))


# ---------------------------------------------------------------- sand
def _sand_surface(pit, tile):
    key = ("sand", tuple(pit), tile)
    if key in _CACHE:
        return _CACHE[key]
    px0, py0, px1, py1 = pit
    w, h = (px1 - px0 + 1) * tile, (py1 - py0 + 1) * tile
    s = pygame.Surface((w, h), pygame.SRCALPHA)
    rnd = random.Random(1187)
    cx, cy, a, b = w / 2, h / 2, w / 2 * .92, h / 2 * .92

    def inside(x, y):
        return ((x - cx) / a) ** 2 + ((y - cy) / b) ** 2 < 1

    k = tile / 40.0
    # scuffed ring where fighters circle
    for _ in range(int(260 * (w * h) / (1480 * 1240))):
        x, y = rnd.uniform(0, w), rnd.uniform(0, h)
        if not inside(x, y):
            continue
        rr = rnd.uniform(10, 30) * k
        pygame.draw.ellipse(s, (120, 86, 52, rnd.randint(14, 30)), (x - rr, y - rr * .45, rr * 2, rr * .9))
    # dried blood stains
    for _ in range(26):
        x, y = rnd.uniform(.2, .8) * w, rnd.uniform(.25, .8) * h
        for j in range(rnd.randint(4, 9)):
            rr = rnd.uniform(3, 14) * k
            dx, dy = rnd.gauss(0, 10 * k), rnd.gauss(0, 6 * k)
            pygame.draw.ellipse(s, (96 + rnd.randint(-10, 10), 24, 18, rnd.randint(70, 140)),
                                (x + dx - rr, y + dy - rr * .6, rr * 2, rr * 1.2))
        if rnd.random() < .6:   # drag smear
            ang = rnd.uniform(0, math.tau)
            L = rnd.uniform(20, 50) * k
            pygame.draw.line(s, (90, 30, 22, 60), (x, y), (x + math.cos(ang) * L, y + math.sin(ang) * L * .6), max(2, int(5 * k)))
    # footprints in pairs heading across the sand
    for _ in range(22):
        x, y = rnd.uniform(.15, .85) * w, rnd.uniform(.2, .85) * h
        ang = rnd.uniform(0, math.tau)
        for st in range(rnd.randint(4, 9)):
            off = (st % 2 * 2 - 1) * 4 * k
            fx = x + math.cos(ang) * st * 11 * k - math.sin(ang) * off
            fy = y + (math.sin(ang) * st * 11 * k + math.cos(ang) * off) * .6
            if inside(fx, fy):
                pygame.draw.ellipse(s, (98, 70, 42, 70), (fx - 2.5 * k, fy - 1.6 * k, 5 * k, 3.2 * k))
    # weapon gouges
    for _ in range(30):
        x, y = rnd.uniform(.15, .85) * w, rnd.uniform(.2, .85) * h
        if not inside(x, y):
            continue
        ang = rnd.uniform(-.6, .6) + (math.pi if rnd.random() < .5 else 0)
        L = rnd.uniform(10, 26) * k
        e = (x + math.cos(ang) * L, y + math.sin(ang) * L * .5)
        pygame.draw.line(s, (84, 58, 34, 120), (x, y), e, max(1, int(2 * k)))
        pygame.draw.line(s, (230, 200, 150, 70), (x, y + 1), (e[0], e[1] + 1), 1)
    _CACHE[key] = s
    return s


def _draw_sand(client, cam_x, cam_y, tile, pit):
    if len(pit) < 4:
        return
    s = _sand_surface([int(v) for v in pit], tile)
    sx, sy = client.world_to_view_offset(int(pit[0]), int(pit[1]), cam_x, cam_y)
    client.screen.blit(s, (sx * tile, sy * tile))
    for st in _FX["stains"]:
        x, y = client.world_to_view_offset(st[0], st[1], cam_x, cam_y)
        r = st[2] * tile
        pygame.draw.ellipse(client.screen, (110, 22, 16), (x * tile + tile / 2 - r, y * tile + tile * .8 - r * .5, r * 2, r))


# ---------------------------------------------------------------- air
def _beams(w, h):
    key = ("beams", w, h)
    s = _CACHE.get(key)
    if s is None:
        s = pygame.Surface((w, h), pygame.SRCALPHA)
        for i, (x, ww) in enumerate(((0.12, .16), (0.42, .10), (0.66, .2))):
            poly = [(w * x, 0), (w * (x + ww), 0), (w * (x + ww + .38), h), (w * (x + .30), h)]
            pygame.draw.polygon(s, (255, 236, 180, 16 + i * 4), poly)
        _CACHE[key] = s
    return s


def _near_pit(client, cam_x, cam_y, pit):
    if len(pit) < 4:
        return False
    return pit[0] - 10 <= cam_x <= pit[2] + 10 and pit[1] - 12 <= cam_y <= pit[3] + 12


def _draw_air(client, cam_x, cam_y, tile, pit, view, t):
    if not _near_pit(client, cam_x, cam_y, pit):
        return
    screen = client.screen
    b = _beams(view.w, view.h)
    b.set_alpha(int(160 + 60 * math.sin(t * .35)))
    screen.blit(b, (0, 0))
    k = tile / 40.0
    for i in range(46):
        rnd = random.Random(i * 31)
        x = (rnd.random() * view.w + t * (8 + rnd.random() * 14) * k) % view.w
        y = (rnd.random() * view.h - t * (3 + rnd.random() * 5) * k + math.sin(t + i) * 6) % view.h
        pygame.draw.circle(screen, (255, 238, 200), (int(x), int(y)), max(1, int((.8 + rnd.random()) * k)))
    if _FX["won_t0"] and time.time() - _FX["won_t0"] < 7:
        _draw_petals(screen, view, time.time() - _FX["won_t0"])


def _draw_petals(screen, view, age):
    for i in range(120):
        rnd = random.Random(i * 7 + 3)
        x = (rnd.random() * view.w + math.sin(age * 2 + i) * 30) % view.w
        y = (rnd.random() * -view.h + age * (120 + rnd.random() * 140)) % (view.h + 40) - 20
        col = rnd.choice([(220, 40, 40), (240, 200, 80), (250, 250, 240), (60, 110, 210)])
        pygame.draw.ellipse(screen, col, (int(x), int(y), 5, 3))


# ---------------------------------------------------------------- battle fx
def _draw_battle_fx(client, cam_x, cam_y, tile, view):
    m = client.arena_match or {}
    if m is not _FX["match"]:
        _FX.update(match=m, hits=[], stains=[], prev={}, intro_t0=time.time(), intro_skip=False)
    units = m.get("units") or {}
    now = time.time()
    prev = _FX["prev"]
    for uid, u in units.items():
        hp = int(u.get("hp") or 0)
        alive = bool(u.get("alive", True)) and hp > 0
        p = prev.get(uid)
        if p is not None:
            if hp < p[0]:
                _FX["hits"].append([float(u.get("x", 0)), float(u.get("y", 0)), now, "hit", u.get("side")])
            if p[1] and not alive:
                _FX["hits"].append([float(u.get("x", 0)), float(u.get("y", 0)), now, "death", u.get("side")])
                if len(_FX["stains"]) < 40:
                    _FX["stains"].append((float(u.get("x", 0)), float(u.get("y", 0)), 0.32 + random.random() * .2))
        prev[uid] = (hp, alive)
    screen = client.screen
    k = tile / 40.0
    keep = []
    for h in _FX["hits"]:
        age = now - h[2]
        life = 0.45 if h[3] == "hit" else 1.1
        if age > life:
            continue
        keep.append(h)
        sx, sy = client.world_to_view_offset(h[0], h[1], cam_x, cam_y)
        x, y = sx * tile + tile / 2, sy * tile + tile * .55
        f = age / life
        if h[3] == "hit":
            r = int((10 + 22 * f) * k)
            pygame.draw.circle(screen, (255, 250, 220), (int(x), int(y - 22 * k)), max(1, int((1 - f) * 9 * k)))
            for j in range(6):
                a = j / 6 * math.tau + h[2]
                pygame.draw.line(screen, (255, 230, 150), (x + math.cos(a) * r * .4, y - 22 * k + math.sin(a) * r * .4),
                                 (x + math.cos(a) * r, y - 22 * k + math.sin(a) * r), max(1, int(2 * k)))
            pygame.draw.ellipse(screen, (190, 150, 100), (x - r, y + 6 * k - r * .25, r * 2, r * .5), max(1, int(2 * k)))
        else:
            for j in range(10):
                a = j / 10 * math.tau
                d = (8 + 40 * f) * k
                pygame.draw.circle(screen, (176, 140, 96), (int(x + math.cos(a) * d), int(y + 8 * k + math.sin(a) * d * .4)),
                                   max(1, int((1 - f) * 7 * k)))
    _FX["hits"] = keep
    # role glyphs under every living soldier
    import arena_barracks_v2 as AB
    for uid, u in units.items():
        if not u.get("alive", True) or u.get("boss") or u.get("duel_player"):
            continue
        role = ROLE_OF.get(u.get("template_id") or "", "line")
        sx, sy = client.world_to_view_offset(float(u.get("x", 0)), float(u.get("y", 0)), cam_x, cam_y)
        AB.role_icon(screen, int(sx * tile + tile / 2 + 16 * k), int(sy * tile + tile * .95), role, r=max(4, int(6 * k)))


# ---------------------------------------------------------------- screen overlays
def draw_intro(client):
    """Battle intro card while armies stand in preview: names, banners, real army counts."""
    m = getattr(client, "arena_match", None) or {}
    if not m.get("active"):
        return
    hud = m.get("hud") or {}
    if (m.get("phase") or hud.get("phase")) != "preview" or hud.get("duel") or m.get("foe_id", "").startswith("boss:"):
        return
    if m is not _FX["match"]:
        _FX.update(match=m, hits=[], stains=[], prev={}, intro_t0=time.time(), intro_skip=False)
    age = time.time() - _FX["intro_t0"]
    if _FX["intro_skip"] or age > 6.5:
        return
    a = 255 if age < 5.5 else int(255 * (6.5 - age))
    sw, sh = client.screen.get_size()
    w, h = min(620, sw - 40), 150
    card = pygame.Surface((w, h), pygame.SRCALPHA)
    card.fill((22, 16, 10, 225))
    pygame.draw.rect(card, (200, 160, 90), card.get_rect(), 2)
    font = pygame.font.Font(None, 24)
    big = pygame.font.Font(None, 40)
    you_c = client._arena_team_colors("you")[0] if hasattr(client, "_arena_team_colors") else (55, 140, 230)
    foe_c = client._arena_team_colors("foe")[0] if hasattr(client, "_arena_team_colors") else (210, 55, 50)
    house = ((getattr(client, "player", None) or {}).get("char_name") or "Your") + "'s House"
    for side, col, x in (("you", you_c, 40), ("foe", foe_c, w - 40)):
        pole = pygame.Rect(0, 0, 34, 70); pole.midtop = (x, 26)
        pygame.draw.polygon(card, col, [pole.topleft, pole.topright, (pole.right, pole.bottom - 12), (pole.centerx, pole.bottom), (pole.left, pole.bottom - 12)])
        pygame.draw.polygon(card, (230, 200, 120), [pole.topleft, pole.topright, (pole.right, pole.bottom - 12), (pole.centerx, pole.bottom), (pole.left, pole.bottom - 12)], 2)
    t1 = font.render("CROWNFALL ARENA · PRACTICE BOUT", True, (220, 190, 120))
    card.blit(t1, t1.get_rect(midtop=(w // 2, 12)))
    vs = big.render(f"{house}  vs  {m.get('foe_name') or hud.get('foe_name') or 'Challenger'}", True, (250, 236, 200))
    if vs.get_width() > w - 120:
        vs = pygame.transform.smoothscale(vs, (w - 120, int(vs.get_height() * (w - 120) / vs.get_width())))
    card.blit(vs, vs.get_rect(midtop=(w // 2, 40)))
    line = (f"{hud.get('your_total', 0)} soldiers · {hud.get('your_max_hp', 0)} HP     vs     "
            f"{hud.get('foe_total', 0)} soldiers · {hud.get('foe_max_hp', 0)} HP")
    s2 = font.render(line, True, (230, 220, 200))
    card.blit(s2, s2.get_rect(midtop=(w // 2, 84)))
    s3 = font.render(("The armies enter through the Gate of Kings · click to skip" if not _MARCH["done"] else
                       "Press Start Battle when ready · click to dismiss"), True, (170, 150, 120))
    card.blit(s3, s3.get_rect(midtop=(w // 2, 116)))
    card.set_alpha(a)
    rect = card.get_rect(midtop=(sw // 2 - 120, 70))
    client.screen.blit(card, rect)
    client._arena_intro_rect = rect


def click_intro(client, mx, my) -> bool:
    r = getattr(client, "_arena_intro_rect", None)
    if r and r.collidepoint(mx, my) and not _FX["intro_skip"]:
        _FX["intro_skip"] = True
        _MARCH["skip"] = True
        client._arena_intro_rect = None
        return True
    return False


def on_result(client, match):
    """Victory roar: crowd cheers and petals rain (visual only)."""
    res = (match or {}).get("result") or {}
    key = id(res)
    if key != _FX["result_key"]:
        _FX["result_key"] = key
        if res.get("won"):
            _FX["won_t0"] = time.time()


def draw_result_fx(client, match):
    on_result(client, match)
    res = (match or {}).get("result") or {}
    card = _result_card_rect(client, res)
    if res.get("won"):
        try:
            _draw_champion(client, match, card)
        except Exception as exc:  # noqa: BLE001
            report(client, "champion", exc)
    _draw_reward_reveal(client, res, card)
    if _FX["won_t0"]:
        age = time.time() - _FX["won_t0"]
        if age < 7:
            _draw_petals(client.screen, client.screen.get_rect(), age)


# ---------------------------------------------------------------- visible failures
_REPORTED: set = set()


def report(client, where, exc):
    """Never swallow a colosseum failure silently: full traceback to stderr + the
    arena log file once per distinct error, one chat line in game, and a running list
    on client._colosseum_errors (inspected by tests / proofs)."""
    import traceback
    key = (where, type(exc).__name__, str(exc)[:120])
    errs = getattr(client, "_colosseum_errors", None)
    if errs is None:
        errs = []
        try:
            client._colosseum_errors = errs
        except Exception:  # noqa: BLE001
            pass
    errs.append(key)
    if key in _REPORTED:
        return
    _REPORTED.add(key)
    tb = "".join(traceback.format_exception(type(exc), exc, exc.__traceback__))
    import sys
    print(f"[arena_colosseum:{where}] {exc}\n{tb}", file=sys.stderr, flush=True)
    try:
        logp = os.path.join(os.path.expanduser("~"), ".crownfall_arena_errors.log")
        with open(logp, "a") as fh:
            fh.write(time.strftime("%Y-%m-%d %H:%M:%S ") + where + "\n" + tb + "\n")
    except Exception:  # noqa: BLE001
        pass
    try:
        client.add_chat(f"Arena visuals error ({where}): {exc} — fallback art in use, details in the log.",
                        color=(255, 140, 90))
    except Exception:  # noqa: BLE001
        pass


# ---------------------------------------------------------------- march-in through the gate
MARCH_SPEED = 6.5   # tiles / second
MARCH_GAP = 0.32    # seconds between soldiers leaving the tunnel
_MARCH: dict = {"match": None, "t0": 0.0, "plan": {}, "done": True, "skip": False, "order": {}, "arrived": set()}


def _gate(m):
    pit = m.get("pit") or [178, 113, 214, 143]
    c = m.get("center") or [(pit[0] + pit[2]) // 2, (pit[1] + pit[3]) // 2]
    return int(c[0]), int(pit[3])


def _is_duel(m):
    hud = m.get("hud") or {}
    return bool(hud.get("duel")) or str(m.get("foe_id") or "").startswith("boss:")


def _march_plan(m):
    units = [u for u in (m.get("units") or {}).values() if u.get("alive", True)]
    gx, gy = _gate(m)

    def key(u):
        sl = u.get("slot")
        return (sl if isinstance(sl, int) else 99, str(u.get("id")))
    sides = {"you": sorted([u for u in units if u.get("side") == "you"], key=key),
             "foe": sorted([u for u in units if u.get("side") != "you"], key=key)}
    plan, order = {}, {}
    n = max(len(sides["you"]), len(sides["foe"]))
    k = 0
    for i in range(n):
        for side in ("foe", "you"):            # challengers file in first, the home house answers
            if i >= len(sides[side]):
                continue
            u = sides[side][i]
            tx, ty = int(u["x"]), int(u["y"])
            lane = gx - 1 if side == "you" else gx + 1
            pts = [(lane, gy + 3), (lane, ty), (tx, ty)]   # start inside the gate tunnel
            plan[u["id"]] = (k * MARCH_GAP, pts)
            order.setdefault(side, []).append(u["id"])
            k += 1
    return plan, order


def _walk(pts, d):
    x, y = pts[0]
    for (ax, ay), (bx, by) in zip(pts, pts[1:]):
        seg = abs(bx - ax) + abs(by - ay)
        if d <= seg:
            f = 0 if seg == 0 else d / seg
            px, py = ax + (bx - ax) * f, ay + (by - ay) * f
            face = ("n" if by < ay else "s") if bx == ax else ("e" if bx > ax else "w")
            return int(round(px)), int(round(py)), face, False
        d -= seg
        x, y = bx, by
    return x, y, None, True


def march_active(client):
    return not _MARCH["done"] and _MARCH["match"] is getattr(client, "arena_match", None)


def _march_finish(client, m):
    for uid, u in (m.get("units") or {}).items():
        if u.get("alive", True) and int(u.get("hp") or 0) > 0:
            client.monsters[uid] = u
    _MARCH["done"] = True


MARCH_STALL_S = 0.25   # longer gaps between intro frames are treated as stalls


def march_update(client):
    """Client-only parade: both armies walk in through the south gate to the spots the
    server already gave them. Server positions are never changed or sent."""
    m = getattr(client, "arena_match", None) or {}
    now = time.time()
    phase = m.get("phase") or (m.get("hud") or {}).get("phase")
    if m is not _MARCH["match"]:
        fresh = bool(m.get("active")) and phase == "preview" and not _is_duel(m)
        plan, order = _march_plan(m) if fresh else ({}, {})
        _MARCH.update(match=m, t0=now, plan=plan, order=order, done=not fresh, skip=False, arrived=set(), last=now)
    if _MARCH["done"]:
        return
    # Presentation clock only: a frame stall (art loading right after the match starts)
    # must not eat the royal-box opening or jump the parade. Server timing is untouched.
    gap = now - _MARCH.get("last", now)
    if gap > MARCH_STALL_S:
        _MARCH["t0"] += gap - 1.0 / 60.0
    _MARCH["last"] = now
    if not m.get("active") or phase != "preview" or _MARCH["skip"] or now - _MARCH["t0"] > 15:
        _march_finish(client, m)
        return
    units = m.get("units") or {}
    pending = False
    for uid, (delay, pts) in _MARCH["plan"].items():
        u = units.get(uid)
        if not u or not u.get("alive", True):
            continue
        d = (now - _MARCH["t0"] - delay) * MARCH_SPEED
        if d < 0:
            client.monsters.pop(uid, None)
            pending = True
            continue
        x, y, face, arrived = _walk(pts, d)
        if arrived:
            client.monsters[uid] = u
            _MARCH["arrived"].add(uid)
            continue
        pending = True
        client.monsters[uid] = dict(u, x=x, y=y, facing=face, attacking=0)
    if not pending:
        _march_finish(client, m)


# ---------------------------------------------------------------- house standards
def _house_label(client, side):
    m = getattr(client, "arena_match", None) or {}
    if side == "you":
        p = getattr(client, "player", None) or {}
        h = p.get("personal_house") or {}
        name = (h.get("name") if isinstance(h, dict) else None) or p.get("char_name") or "You"
    else:
        name = m.get("foe_name") or "Foe"
    for pre in ("House ", "the ", "The "):
        if name.startswith(pre):
            name = name[len(pre):]
    return (name.strip()[:1] or "?").upper()


def _standard_spots(client):
    m = getattr(client, "arena_match", None) or {}
    out = []
    for side in ("you", "foe"):
        shown = [client.monsters.get(uid) for uid in (m.get("units") or {})
                 if (m["units"][uid].get("side") == "you") == (side == "you")]
        shown = [u for u in shown if u and u.get("alive", True)]
        if not shown:
            continue
        if march_active(client):
            lead = None
            # the bearer walks at the head of the column still on the move
            for uid in _MARCH["order"].get(side, []):
                if uid in client.monsters and uid not in _MARCH["arrived"]:
                    lead = client.monsters[uid]
                    break
            if lead is not None:
                out.append((side, float(lead["x"]) + (-0.45 if side == "you" else 0.45), float(lead["y"]) - 0.1, True))
                continue
        if True:
            xs = [float(u["x"]) for u in shown]
            ys = [float(u["y"]) for u in shown]
            x = (min(xs) - 2.0) if side == "you" else (max(xs) + 2.0)
            out.append((side, x, sum(ys) / len(ys), False))
    return out


def _queue_standards(client, draw_list, cam_x, cam_y, tile, t):
    m = getattr(client, "arena_match", None) or {}
    if not m.get("active") or _is_duel(m):
        return
    for side, wx, wy, carried in _standard_spots(client):
        sx, sy = client.world_to_view_offset(wx, wy, cam_x, cam_y)
        x, feet = sx * tile + tile / 2, sy * tile + tile
        draw_list.append((feet + 1, 4.5, lambda side=side, x=x, feet=feet, carried=carried:
                          _draw_standard(client, side, x, feet, tile, t, carried)))


def _draw_standard(client, side, x, feet, tile, t, carried):
    try:
        fill, rim = client._arena_team_colors(side)
    except Exception:  # noqa: BLE001
        fill, rim = ((55, 140, 230), (120, 200, 255)) if side == "you" else ((210, 55, 50), (255, 120, 100))
    k = tile / 40.0
    screen = client.screen
    h = (2.5 if carried else 2.9) * tile
    top = feet - h
    pole_c = (74, 52, 30)
    if not carried:   # planted: small cross-footed base
        pygame.draw.line(screen, pole_c, (x - 8 * k, feet), (x + 8 * k, feet), max(2, int(3 * k)))
    pygame.draw.line(screen, pole_c, (x, feet), (x, top), max(2, int(3 * k)))
    pygame.draw.circle(screen, (226, 190, 96), (int(x), int(top)), max(2, int(4 * k)))
    d = 1 if side == "you" else -1
    w, hh = 30 * k, 40 * k
    pts = []
    n = 8
    for i in range(n + 1):           # top edge waving
        f = i / n
        pts.append((x + d * w * f, top + 5 * k + math.sin(t * 4 + f * 4) * 3 * k * f))
    tail = top + 5 * k + hh
    pts += [(x + d * w, tail + math.sin(t * 4 + 4) * 3 * k), (x + d * w * .55, tail - 10 * k + math.sin(t * 4 + 2.4) * 2 * k),
            (x + d * w * .2, tail), (x, tail)]
    pygame.draw.polygon(screen, fill, pts)
    pygame.draw.polygon(screen, (226, 190, 96), pts, max(1, int(2 * k)))
    # charge: a pale chevron and the house initial
    cx = x + d * w * .45
    cy = top + 5 * k + hh * .42
    pygame.draw.lines(screen, rim, False, [(cx - 9 * k, cy - 2 * k), (cx, cy - 10 * k), (cx + 9 * k, cy - 2 * k)], max(1, int(3 * k)))
    f = _font(max(10, int(17 * k)))
    lab = f.render(_house_label(client, side), True, (250, 240, 214))
    screen.blit(lab, lab.get_rect(center=(int(cx), int(cy + 7 * k))))


_FONTS: dict = {}


def _font(px, bold=False):
    key = (px, bold)
    if key not in _FONTS:
        f = pygame.font.Font(None, px)
        f.set_bold(bold)
        _FONTS[key] = f
    return _FONTS[key]


# ---------------------------------------------------------------- camera framing
def frame_camera(client, match, cx, cy, living, half_h):
    """Battle framing. Keep every fighter on screen but push the frame north so the
    stands and royal balcony sit above the line instead of empty sand; open on the
    royal box while the armies parade in, and look up at the king after the bout."""
    pit = match.get("pit") or [178, 113, 214, 143]
    c = match.get("center") or [(pit[0] + pit[2]) / 2, (pit[1] + pit[3]) / 2]
    royal = (float(c[0]), float(pit[1]) - 3.0)
    if match.get("awaiting_result") or (match.get("result") and not match.get("active")):
        return royal
    if march_active(client):
        age = time.time() - _MARCH["t0"]
        if age < 1.4:
            return royal
        shown = [client.monsters.get(uid) for uid in _MARCH["plan"] if uid in client.monsters]
        if shown:
            mx = sum(float(u["x"]) for u in shown) / len(shown)
            my = sum(float(u["y"]) for u in shown) / len(shown)
            return 0.5 * mx + 0.5 * float(c[0]), min(my, float(c[1]))
        return float(c[0]), float(pit[3]) - 4.0
    if not living:
        return cx, cy
    maxy = max(float(u["y"]) for u in living)
    want = cy - 8.0
    floor_y = maxy - (half_h - 1.6)      # lowest fighter keeps ~1.6 tiles of margin
    return cx, min(cy, max(want, floor_y))


# ---------------------------------------------------------------- victory: champion + spoils
def _result_card_rect(client, res):
    try:
        import arena_battles_ui
        n = len(arena_battles_ui.result_lines(res))
    except Exception:  # noqa: BLE001
        n = 0
    sw, sh = client.screen.get_size()
    card = pygame.Rect(0, 0, 560, 300 + 22 * n)
    card.center = (sw // 2, sh // 2)
    return card


def champion_of(match):
    units = [u for u in ((match or {}).get("units") or {}).values()
             if u.get("side") == "you" and not u.get("boss") and u.get("alive", True) and int(u.get("hp") or 0) > 0]
    if not units:
        return None
    return max(units, key=lambda u: (int(u.get("level") or 0), int(u.get("hp") or 0), str(u.get("name"))))


def _draw_champion(client, match, card):
    u = champion_of(match)
    if not u:
        return
    screen = client.screen
    k = 2.6
    tile = 40
    tile_px = int(tile * k * 1.1)
    cx = max(90, card.x - 80)
    feet = card.centery + 70
    t = time.time()
    glow = _glow(int(70), (90, 70, 20))
    screen.blit(glow, glow.get_rect(center=(cx, feet - 60)), special_flags=pygame.BLEND_RGB_ADD)
    pygame.draw.ellipse(screen, (60, 44, 26), (cx - 62, feet - 14, 124, 30))
    pygame.draw.ellipse(screen, (226, 190, 96), (cx - 62, feet - 14, 124, 30), 2)
    eq = u.get("equipment") or {}
    gender = str(u.get("gender") or "male")
    # Weapon raised to the king: the swing frame at the top of the arc, held.
    raise_t = 0.30 + 0.03 * math.sin(t * 3)
    drawn = client._draw_arena_soldier_hd(dict(u, facing="s", attacking=raise_t), cx, feet, tile_px, t,
                                          "melee", raise_t, raise_t, "s", eq, gender)
    if not drawn:
        raise RuntimeError("champion doll did not draw")
    f = _font(22, True)
    lab = f.render("CHAMPION OF THE DAY", True, (240, 206, 110))
    screen.blit(lab, lab.get_rect(midtop=(cx, feet + 18)))
    f2 = _font(20)
    nm = f2.render(f"{u.get('name')} · Lv {u.get('level')}", True, (236, 226, 206))
    screen.blit(nm, nm.get_rect(midtop=(cx, feet + 38)))


REVEAL_T = 2.6


def _draw_reward_reveal(client, res, card):
    """Spoils reveal on the real summary numbers, played exactly once per result."""
    if not res or res.get("_revealed"):
        return
    st = _FX.get("reveal")
    if not st or st[0] is not res:
        st = _FX["reveal"] = (res, time.time())
    age = time.time() - st[1]
    if age >= REVEAL_T + 0.4:
        res["_revealed"] = True
        return
    xp = int(res.get("command_xp") or 0)
    coins = int(res.get("coins") or 0)
    renown = int(res.get("renown_gain") or 0)
    f = min(1.0, age / (REVEAL_T * 0.75))
    ease = 1 - (1 - f) ** 3
    alpha = 255 if age < REVEAL_T else int(255 * max(0.0, 1 - (age - REVEAL_T) / 0.4))
    band = pygame.Surface((card.w - 24, 92), pygame.SRCALPHA)
    band.fill((30, 20, 8, 238))
    pygame.draw.rect(band, (226, 190, 96), band.get_rect(), 2, border_radius=8)
    title = _font(24, True).render("SPOILS OF THE ARENA", True, (226, 190, 96))
    band.blit(title, title.get_rect(midtop=(band.get_width() // 2, 6)))
    bits = [(f"+{int(xp * ease):,}", "Command XP", (255, 214, 90))]
    if coins:
        bits.append((f"+{int(coins * ease):,}", "coins", (250, 230, 160)))
    if renown:
        bits.append((f"+{int(renown * ease):,}", "renown", (200, 180, 255)))
    if res.get("mythos_ore") and f > 0.6:
        bits.append(("1", "Mythos ore!", (140, 230, 255)))
    colw = band.get_width() // len(bits)
    for i, (num, lab, col) in enumerate(bits):
        x = colw * i + colw // 2
        pop = 1.0 + (0.25 * math.sin(min(1.0, f * 1.4) * math.pi) if f < 1 else 0)
        n = _font(int(34 * pop), True).render(num, True, col)
        band.blit(n, n.get_rect(midtop=(x, 30)))
        l2 = _font(20).render(lab, True, (220, 206, 180))
        band.blit(l2, l2.get_rect(midtop=(x, 64)))
    band.set_alpha(alpha)
    client.screen.blit(band, (card.x + 12, card.y + 92))
