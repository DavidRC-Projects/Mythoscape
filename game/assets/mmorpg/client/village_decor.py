"""Light dressing for the village meadows (31 Oct 2026, round 4).

Bush clumps, wildflower patches, a few trees, mossy rocks and fence runs on the
big grass plots, and barrels / logs / haystacks / a cart beside buildings.
Purely visual and non-blocking (no tile changes), Y-sorted with everything else;
a sprite covering the player fades. Keeps clear of roads (1 tile), building
footprints, NPC / interactable / spawn points and the sewer grate (2 tiles).
Missing art just draws nothing.
"""
import math
import os
import random

import pygame

import vale_ring as VR
import world_map as wm

_DIR = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "assets", "village_decor"))
# sprite -> (width in tiles, foot anchor as fraction of height)
SIZE = 1.2   # reads at overview scale

KIT = {
    "tree": ("decor_1", 3.6, 0.93), "bush_l": ("decor_2", 1.8, 0.92), "flowers": ("decor_3", 2.0, 0.88),
    "hay": ("decor_4", 1.5, 0.9), "bush_s": ("decor_5", 1.2, 0.9), "fence": ("decor_6", 2.1, 0.92),
    "flowers2": ("decor_7", 1.9, 0.88), "bush_m": ("decor_8", 1.6, 0.92), "rocks": ("decor_9", 1.3, 0.9),
    "barrels": ("decor_10", 1.1, 0.93), "cart": ("decor_11", 1.7, 0.92), "logs": ("decor_12", 1.3, 0.9),
}
REGION = (5, 3, 92, 51)
_IMG, _SC, _S = {}, {}, {}


def _img(stem):
    if stem not in _IMG:
        try:
            _IMG[stem] = pygame.image.load(os.path.join(_DIR, stem + ".png")).convert_alpha()
        except Exception:
            _IMG[stem] = None
    return _IMG[stem]


def _scaled(stem, w_px, flip, alpha):
    key = (stem, w_px, flip, alpha)
    s = _SC.get(key)
    if s is None:
        src = _img(stem)
        if src is None:
            return None
        h = max(1, src.get_height() * w_px // src.get_width())
        s = pygame.transform.smoothscale(src, (w_px, h))
        if flip:
            s = pygame.transform.flip(s, True, False)
        if alpha < 255:
            s = s.copy(); s.fill((255, 255, 255, alpha), special_flags=pygame.BLEND_RGBA_MULT)
        if len(_SC) > 400:
            _SC.clear()
        _SC[key] = s
    return s


def placements(client):
    if _S.get("grid") is client.tiles:
        return _S["place"]
    tiles = client.tiles
    H, W = len(tiles), len(tiles[0])
    fps = getattr(wm, "_BUILDING_FOOTPRINTS", [])
    blocked = set()
    for (px, py) in VR._key_points():
        for dy in range(-2, 3):
            for dx in range(-2, 3):
                blocked.add((px + dx, py + dy))
    def in_fp(x, y, m=0):
        return any(a - m <= x <= c + m and b - m <= y <= d + m for a, b, c, d in fps)
    def grass(x, y):
        return 0 <= y < H and 0 <= x < W and tiles[y][x] == wm.GRASS
    def near_path(x, y, r=1):
        return any(0 <= y + dy < H and 0 <= x + dx < W and tiles[y + dy][x + dx] in (wm.PATH, wm.STONE, wm.FLOOR, wm.WATER)
                   for dy in range(-r, r + 1) for dx in range(-r, r + 1))
    rng = random.Random(9137)
    out, used = [], set()
    x0, y0, x1, y1 = REGION
    def free(x, y, r):
        return all((x + dx, y + dy) not in used for dy in range(-r, r + 1) for dx in range(-r, r + 1))
    def put(kind, x, y, r=0, jitter=0.25):
        out.append((kind, x + 0.5 + rng.uniform(-jitter, jitter), y + 0.85 + rng.uniform(-0.1, 0.1),
                    rng.random() < 0.5, rng.uniform(0.9, 1.12)))
        for dy in range(-r, r + 1):
            for dx in range(-r, r + 1):
                used.add((x + dx, y + dy))
    cells = [(x, y) for y in range(y0, y1) for x in range(x0, x1)]
    rng.shuffle(cells)
    for (x, y) in cells:
        try:
            if wm.get_zone(x, y) != "village":
                continue
        except Exception:
            continue
        if not grass(x, y) or (x, y) in blocked or in_fp(x, y, 1) or VR.is_cliff(x, y):
            continue
        # Keep bushes/flowers off the Endless Depths mouth (NW cliffs).
        mx, my = getattr(wm, "ENDLESS_MOUTH", (15, 9))
        if max(abs(x - mx), abs(y - my)) <= 12:
            continue
        if near_path(x, y, 1):
            # beside a building (but off the road): yard clutter
            if in_fp(x, y, 2) and not near_path(x, y, 0) and free(x, y, 3) and rng.random() < 0.10:
                put(rng.choice(("barrels", "logs", "hay", "barrels")), x, y, 3, 0.15)
            continue
        if not free(x, y, 1):
            continue
        r = rng.random()
        deep = not near_path(x, y, 1) and not in_fp(x, y, 2)
        # Decorative "tree" sprites used to look choppable but had no resource
        # node — woodcutting is on real TREE tiles + hd_trees art instead.
        # Meadow copses still get bush clumps so the plots do not look bare.
        if deep and r < 0.06 and free(x, y, 3):
            put(rng.choice(("bush_l", "bush_m")), x, y, 2)
            for _ in range(2):
                bx, by = x + rng.choice((-1, 1)), y + rng.choice((0, 1))
                if grass(bx, by) and (bx, by) not in blocked:
                    put(rng.choice(("bush_s", "bush_m", "flowers")), bx, by, 0, 0.3)
        elif r < 0.22:
            put(rng.choice(("bush_l", "bush_m", "bush_s")), x, y, 1)
            _buddy(rng, put, grass, blocked, near_path, x, y, ("bush_s", "bush_m", "flowers"))
        elif r < 0.34:
            put(rng.choice(("flowers", "flowers2")), x, y, 1)
            _buddy(rng, put, grass, blocked, near_path, x, y, ("flowers", "flowers2", "bush_s"))
        elif r < 0.37:
            put("rocks", x, y, 1)
    # a few fence runs along the north side of plots that face a road
    runs = 0
    for y in range(y0 + 1, y1):
        x = x0
        while x < x1 - 4 and runs < 7:
            ok = all(grass(x + i, y) and tiles[y - 1][x + i] == wm.PATH and (x + i, y) not in blocked
                     and not in_fp(x + i, y, 1) and wm.get_zone(x + i, y) == "village" for i in range(4))
            if ok and rng.random() < 0.08:
                for i in (0, 2):
                    out.append(("fence", x + i + 1.0, y + 0.55, False, 1.0))
                runs += 1
                x += 10
            x += 1
    _S["grid"] = tiles
    _S["place"] = out
    return out


def _buddy(rng, put, grass, blocked, near_path, x, y, kinds):
    # a neighbour so props read as clumps rather than lone dots
    if rng.random() < 0.65:
        bx, by = x + rng.choice((-1, 1)), y + rng.choice((0, 1))
        if grass(bx, by) and (bx, by) not in blocked and not near_path(bx, by, 0):
            put(rng.choice(kinds), bx, by, 0, 0.25)


def queue(client, draw_list, cam_x, cam_y, tile, screen_xy, player_rect):
    view = client.screen.get_rect()
    for kind, wx, wy, flip, sc in placements(client):
        stem, wt, anchor = KIT[kind]
        w_px = max(6, int(wt * sc * SIZE * tile))
        img = _scaled(stem, w_px, flip, 255)
        if img is None:
            continue
        bx, by = screen_xy(client, wx, wy, cam_x, cam_y, tile)
        left, top = int(bx - img.get_width() / 2), int(by - img.get_height() * anchor)
        r = pygame.Rect(left, top, img.get_width(), img.get_height())
        if not r.colliderect(view):
            continue
        faded = bool(player_rect and player_rect[1] < wy and r.colliderect(player_rect[0]) and kind in ("tree", "hay", "cart"))

        def _draw(stem=stem, w_px=w_px, flip=flip, pos=(left, top), faded=faded, w=img.get_width(), h=img.get_height(), anchor=anchor):
            im = _scaled(stem, w_px, flip, 120 if faded else 255)
            sh = pygame.Surface((int(w * 0.8), max(3, int(w * 0.22))), pygame.SRCALPHA)
            pygame.draw.ellipse(sh, (20, 26, 10, 60), sh.get_rect())
            client.screen.blit(sh, (pos[0] + int(w * 0.1), int(pos[1] + h * anchor - sh.get_height() * 0.55)))
            client.screen.blit(im, pos)
        draw_list.append((int(by), 1, _draw))
