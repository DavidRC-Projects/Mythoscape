"""Deepdelve Mine painter (MINE_SPEC.md): painted rock ground, ore sprites, props, lifts,
ore-bank chests and per-floor darkness with torch light.

Called from client.draw_map:
    paint_ground(client, tile)              after the terrain pass (overworld box + mine instances)
    queue(client, draw_list, cam_x, cam_y, tile, t)   y-sorted props / lifts
    draw_rock(screen, rtype, cx, cy, tile, wx, wy)    -> True when the mine drew the rock
    draw_chest(screen, spot, cx, cy, tile)            -> True for variant 'mine_chest'
    light(client, tile)                     after the draw_list pass, before projectiles
Every entry point returns quietly (False / no-op) if an asset is missing, so the old art
stays as the error fallback.
"""
from __future__ import annotations

import math
import os

import pygame

import world_map as wm
import deepdelve_layout as L

_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets", "mine")
_RAW: dict = {}
_CACHE: dict = {}
_CACHE_LIMIT = 900

ORE_ART = {
    "copper_rock": "copper", "tin_rock": "tin", "iron_rock": "iron", "coal_rock": "coal",
    "mithril_rock": "mithril", "adamantite_rock": "adamantite", "gem_vein": "gem", "heart_vein": "heart",
}
ROCK_XY = {(x, y): t for x, y, t in L.ALL_ROCKS}
_LIFT_LABEL = {f: f"Lift: {L.FLOOR_NAMES[f]} (Mining {L.FLOOR_GATE[f]})" for f in (1, 2, 3)}
# Region -> texture suffix (floor 2/3 have their own stone).
_TEX = {"yard": "", 0: "", 1: "", 2: "_f2", 3: "_f3"}
# How tall each prop stands, in tiles (sprite is scaled to this height, feet on the tile).
PROP_H = {"timber": 2.1, "torch": 1.35, "lantern": 1.3, "cart": 1.15, "barrel": 1.05,
          "crates": 1.2, "rope": 0.8, "lift": 2.3, "chest": 1.0,
          "signpost": 3.0, "crystals": 1.15, "shaft_down": 1.9}
# v2 levels: labels for the ways down / up (shown when the player is close).
_UP_LABEL = {1: "Lift: up to the Upper Drift", 2: "Climb up: Ground Level", 3: "Climb up: Level 2"}
_DOWN_LABEL = f"Way down: Level 2 - Mithril (Mining {L.FLOOR_GATE[2]})"
_SHAFT_LABEL = f"Ladder down: Level 3 - Adamantite (Mining {L.FLOOR_GATE[3]})"


def _raw(rel):
    if rel not in _RAW:
        path = os.path.join(_DIR, rel)
        try:
            _RAW[rel] = pygame.image.load(path).convert_alpha() if os.path.isfile(path) else None
        except pygame.error:
            _RAW[rel] = None
    return _RAW[rel]


def _put(key, val):
    if len(_CACHE) > _CACHE_LIMIT:
        for k in list(_CACHE)[: _CACHE_LIMIT // 3]:
            _CACHE.pop(k, None)
    _CACHE[key] = val
    return val


def _by_height(rel, h):
    h = max(4, int(h))
    key = ("h", rel, h)
    if key in _CACHE:
        return _CACHE[key]
    img = _raw(rel)
    if img is None:
        return None
    w = max(1, int(round(img.get_width() * h / float(img.get_height()))))
    return _put(key, pygame.transform.smoothscale(img, (w, h)))


def _by_width(rel, w):
    w = max(4, int(w))
    key = ("w", rel, w)
    if key in _CACHE:
        return _CACHE[key]
    img = _raw(rel)
    if img is None:
        return None
    h = max(1, int(round(img.get_height() * w / float(img.get_width()))))
    return _put(key, pygame.transform.smoothscale(img, (w, h)))


def _tex_cell(name, wx, wy, tile):
    """One tile of a 256px seamless texture that spans 4x4 world tiles."""
    key = ("t", name, wx % 4, wy % 4, tile)
    if key in _CACHE:
        return _CACHE[key]
    img = _raw(name + ".png")
    if img is None:
        return None
    sub = img.subsurface(pygame.Rect((wx % 4) * 64, (wy % 4) * 64, 64, 64))
    return _put(key, pygame.transform.smoothscale(sub, (tile, tile)))


def _shade(tile, alpha, top=False):
    key = ("sh", tile, alpha, top)
    if key in _CACHE:
        return _CACHE[key]
    s = pygame.Surface((tile, tile), pygame.SRCALPHA)
    for i in range(tile):
        f = (1.0 - i / float(tile)) if top else (i / float(tile))
        pygame.draw.line(s, (6, 4, 6, int(alpha * f)), (0, i), (tile, i))
    return _put(key, s)


def _glow(r, rgb, k):
    """Soft radial glow for BLEND_RGB_ADD (black = no change)."""
    key = ("glow", r, rgb, k)
    if key in _CACHE:
        return _CACHE[key]
    r = max(2, r)
    s = pygame.Surface((r * 2, r * 2))
    s.fill((0, 0, 0))
    for i in range(r, 0, -1):
        f = (1.0 - i / float(r)) ** 1.6 * k
        pygame.draw.circle(s, (int(rgb[0] * f), int(rgb[1] * f), int(rgb[2] * f)), (r, r), i)
    return _put(key, s)


def ready():
    return _raw("tex_floor.png") is not None and _raw("tex_wall.png") is not None


# --------------------------------------------------------------------------- helpers
def _instance(client):
    d = getattr(client, "dungeon", None) or {}
    return d.get("deepdelve") if d.get("id") == "deepdelve" else None


def _visible_cells(client, tile):
    """(sx, sy, wx, wy) for every on-screen cell, honouring the camera's yaw."""
    cam_x, cam_y = client.camera_origin()
    map_w, map_h = _map_size()
    vis_w, vis_h = map_w // tile, map_h // tile
    for sy in range(vis_h + 2):
        for sx in range(vis_w + 2):
            wx, wy = client.view_to_world(cam_x + sx, cam_y + sy)
            yield sx, sy, wx, wy


def _map_size():
    import sys
    main = sys.modules.get("__main__")
    if main is not None and hasattr(main, "MAP_W"):
        return int(main.MAP_W), int(main.MAP_H)
    try:
        import client as _c
        return int(_c.MAP_W), int(_c.MAP_H)
    except Exception:
        return 900, 640


def _tile_at(client, x, y):
    tiles = getattr(client, "tiles", None) or []
    if 0 <= y < len(tiles) and 0 <= x < len(tiles[0]):
        return tiles[y][x]
    return None


def _ground_cell(screen, rect, tid, suffix, wx, wy, below_floor):
    if tid == wm.WALL:
        img = _tex_cell("tex_wall" + suffix, wx, wy, rect.w)
        if img is None:
            return False
        screen.blit(img, rect)
        if below_floor:
            # Lit rock lip: the wall's south face meets the floor.
            screen.blit(_shade(rect.w, 150), rect)   # v4: ragged rock edges (dress) replace the straight lip
        return True
    img = _tex_cell("tex_floor" + suffix, wx, wy, rect.w)
    if img is None:
        return False
    screen.blit(img, rect)
    return True


# --------------------------------------------------------------------------- ground
def paint_ground(client, tile):
    """Paint the mine square (overworld) or a mine instance over the default terrain."""
    if not ready():
        return
    screen = client.screen
    inst = _instance(client)
    if getattr(client, "dungeon", None) and inst is None:
        return
    resources = getattr(client, "resources", None) or {}
    bx0, by0, bx1, by1 = L.BOX
    floor = (inst or {}).get("mine_floor") or 1
    for sx, sy, wx, wy in _visible_cells(client, tile):
        if inst is None and not (bx0 <= wx <= bx1 and by0 <= wy <= by1):
            continue
        tid = _tile_at(client, wx, wy)
        rect = pygame.Rect(sx * tile, sy * tile, tile, tile)
        if tid is None:
            if inst is not None:                        # beyond the instance: solid rock, not a void
                img = _tex_cell("tex_wall" + ("" if inst.get("kind") == "colossus" else _TEX.get(floor, "")), wx, wy, tile)
                if img is not None:
                    screen.blit(img, rect)
            continue
        if inst is None:
            reg = L.region(wx, wy)
            if reg is None:
                reg = 0
            suffix = _TEX.get(reg, "")
            # Rocks, chests and blocking props stand on floor stone.
            if (wx, wy) in ROCK_XY or (wx, wy) in _PROP_BLOCK or (wx, wy) in _CHEST_XY:
                tid = wm.FLOOR
        else:
            suffix = "" if inst.get("kind") == "colossus" else _TEX.get(floor, "")
        below = tid == wm.WALL and _tile_at(client, wx, wy + 1) not in (None, wm.WALL)
        if inst is None and below and (wx, wy + 1) in ROCK_XY:
            below = True
        _ground_cell(screen, rect, tid, suffix, wx, wy, below)
        if inst is None and (wx, wy) in ROCK_XY and f"{wx},{wy}" not in resources:
            img = _by_width("ores/depleted.png", tile * 1.05)
            if img is not None:
                screen.blit(img, img.get_rect(midbottom=(rect.centerx, rect.bottom + tile // 8)))
    try:
        dress(client, tile)
    except Exception as e:                      # dressing is optional; the painted ground stays
        print("deepdelve dress:", e)
    if inst is None:
        _paint_rails(client, tile)
        _paint_shaft(client, tile)


def _paint_rails(client, tile):
    screen = client.screen
    cam_x, cam_y = client.camera_origin()
    pts = set(L.RAILS)
    w = max(1, tile // 14)
    for x, y in L.RAILS:
        sx, sy = client.world_to_view_offset(x, y, cam_x, cam_y)
        r = pygame.Rect(sx * tile, sy * tile, tile, tile)
        horiz = (x - 1, y) in pts or (x + 1, y) in pts
        if (x - 1, y) in pts and (x, y - 1) in pts and (x + 1, y) not in pts and (x, y + 1) not in pts:
            _rail_corner(screen, r, tile, w)
            continue
        if horiz:
            for k in range(3):
                tx = r.x + int((k + 0.5) * tile / 3)
                pygame.draw.line(screen, (64, 44, 30), (tx, r.y + tile // 4), (tx, r.bottom - tile // 4), max(2, tile // 8))
            for oy in (tile // 3, tile * 2 // 3):
                pygame.draw.line(screen, (118, 112, 108), (r.x, r.y + oy), (r.right, r.y + oy), w)
        else:
            for k in range(3):
                ty = r.y + int((k + 0.5) * tile / 3)
                pygame.draw.line(screen, (64, 44, 30), (r.x + tile // 4, ty), (r.right - tile // 4, ty), max(2, tile // 8))
            for ox in (tile // 3, tile * 2 // 3):
                pygame.draw.line(screen, (118, 112, 108), (r.x + ox, r.y), (r.x + ox, r.bottom), w)


def _rail_corner(screen, r, tile, w):
    """Curved junction: the B0 spur (from the west) turns north up the ramp."""
    for k in range(3):                                  # ties, fanned around the bend
        a = (k + 0.5) / 3.0 * (math.pi / 2)
        c, s_ = math.cos(a), math.sin(a)
        p0 = (r.x + c * tile * 0.22, r.y + s_ * tile * 0.22)
        p1 = (r.x + c * tile * 0.80, r.y + s_ * tile * 0.80)
        pygame.draw.line(screen, (64, 44, 30), p0, p1, max(2, tile // 8))
    for rad in (tile // 3, tile * 2 // 3):
        box = pygame.Rect(r.x - rad, r.y - rad, rad * 2, rad * 2)
        pygame.draw.arc(screen, (118, 112, 108), box, -math.pi / 2, 0, max(1, w))


def _signpost(client, tile, x, y):
    """Painted plank signpost with the text written onto the arrow board (cached)."""
    entry = next((e for e in getattr(L, "SIGNPOSTS", []) if (e[0], e[1]) == (x, y)), None)
    if entry is None:
        return None
    key = ("sign", x, y, tile)
    if key in _CACHE:
        return _CACHE[key]
    base = _by_height("props/signpost.png", tile * PROP_H["signpost"])
    if base is None:
        return None
    img = base.copy()
    W, H = img.get_size()
    # The arrow plank is tilted ~12 deg up to the right, centred near (50 %, 19 %) of the art.
    try:
        f1 = pygame.font.Font(None, max(11, int(H * 0.12)))
    except Exception:
        return _put(key, img)
    f1.set_bold(True)
    t1 = f1.render(entry[2], True, (255, 236, 170))       # pale lantern-lit paint
    hi = f1.render(entry[2], True, (22, 12, 6))           # dark outline
    maxw = int(W * 0.70)
    if t1.get_width() > maxw:
        size = (maxw, max(1, int(t1.get_height() * maxw / float(t1.get_width()))))
        t1, hi = pygame.transform.smoothscale(t1, size), pygame.transform.smoothscale(hi, size)
    t1, hi = pygame.transform.rotozoom(t1, 12, 1.0), pygame.transform.rotozoom(hi, 12, 1.0)
    c = (int(W * 0.50), int(H * 0.195))
    for ox, oy in ((-1, 0), (1, 0), (0, -1), (0, 1), (1, 1), (-1, 1)):
        img.blit(hi, hi.get_rect(center=(c[0] + ox, c[1] + oy)))
    img.blit(t1, t1.get_rect(center=c))
    return _put(key, img)


def _paint_shaft(client, tile):
    """The ramp down from the yard: painted shaft mouth over the ramp rect."""
    img_raw = _raw("shaft_mouth.png")
    if img_raw is None:
        return
    cam_x, cam_y = client.camera_origin()
    x0, y0, x1, y1 = L.RAMP
    sx0, sy0 = client.world_to_view_offset(x0, y0, cam_x, cam_y)
    sx1, sy1 = client.world_to_view_offset(x1, y1, cam_x, cam_y)
    left, right = min(sx0, sx1) * tile, (max(sx0, sx1) + 1) * tile
    top, bot = min(sy0, sy1) * tile, (max(sy0, sy1) + 1) * tile
    w, h = right - left, bot - top
    if w <= 0 or h <= 0:
        return
    key = ("shaft", w, h)
    img = _CACHE.get(key) or _put(key, pygame.transform.smoothscale(img_raw, (w, h)))
    client.screen.blit(img, (left, top))
    # v2: the shaft is the way down -- a cold draught of darkness in its throat + a label up close.
    if getattr(client, "player", None):
        px, py = client.player_xy()
        if L.RAMP[0] - 3 <= px <= L.RAMP[2] + 3 and L.RAMP[1] - 3 <= py <= L.RAMP[3] + 3:
            bp = getattr(client, "blit_nameplate", None)
            if bp:
                bp(_DOWN_LABEL, (left + right) // 2, top + h // 2 - tile // 2, (255, 226, 150))


# --------------------------------------------------------------------------- sprites
def draw_rock(screen, rtype, cx, cy, tile, wx, wy):
    if (wx, wy) not in ROCK_XY:
        return False
    name = ORE_ART.get(rtype) or ORE_ART.get(ROCK_XY[(wx, wy)])
    img = _by_width(f"ores/{name}.png", tile * 1.15) if name else None
    if img is None:
        return False
    screen.blit(img, img.get_rect(midbottom=(cx, cy + tile // 2 + tile // 10)))
    if name == "heart":
        import time
        k = 0.55 + 0.25 * math.sin(time.time() * 2.4)
        r = int(tile * 0.6)
        g = _glow(r, (150, 34, 20), round(k, 1))
        screen.blit(g, (cx - r, cy - r - tile // 6), special_flags=pygame.BLEND_RGB_ADD)
    return True


def draw_chest(screen, spot, cx, cy, tile):
    if spot.get("variant") != "mine_chest":
        return False
    img = _by_width("props/chest.png", tile * 1.1)
    if img is None:
        return False
    screen.blit(img, img.get_rect(midbottom=(cx, cy + tile // 2 + tile // 10)))
    return True


_PROP_BLOCK = {(x, y) for x, y, _k, b in L.PROPS if b}
_CHEST_XY = {(x, y) for _i, x, y in L.BANK_CHESTS}


def queue(client, draw_list, cam_x, cam_y, tile, t):
    if not ready():
        return
    screen = client.screen
    map_w, map_h = _map_size()
    vis_w, vis_h = map_w // tile, map_h // tile
    inst = _instance(client)
    items = []
    if inst is None:
        if getattr(client, "dungeon", None):
            return
        items = [(x, y, k) for x, y, k, _b in L.PROPS]
        items += [(x, y, "lift") for x, y in L.LIFT_PADS.values()]
        items += [(x, y, "lift") for x, y in L.LIFT_UP.values()]
        items += [(x, y, "signpost") for x, y, *_r in getattr(L, "SIGNPOSTS", [])]
        items += [(x, y, "crystals") for lv in (2, 3) for x, y in getattr(L, "CRYSTALS", {}).get(lv, [])]
        if hasattr(L, "SHAFT_DOWN"):
            items.append((L.SHAFT_DOWN[0], L.SHAFT_DOWN[1], "shaft_down"))
    elif inst.get("kind") == "gauntlet":
        cx_, cy_ = inst.get("cage") or (43, 4)
        items = [(cx_, cy_ - 1, "lift"), (2, 2, "torch"), (41, 3, "torch"), (5, 3, "timber"),
                 (17, 3, "timber"), (28, 3, "timber"), (39, 3, "timber")]
        items += [(x, y, "brazier") for x, y in _gauntlet_braziers(inst)]
        items += [(3, 2, "barrel"), (40, 5, "crates"), (12, 7, "rope")]
    elif inst.get("kind") == "colossus":
        items = [(x, y, "brazier") for x, y in C_BRAZIERS] + [(x, y, "crystal") for x, y in C_CRYSTALS]
    px, py = client.player_xy() if getattr(client, "player", None) else (None, None)
    for x, y, kind in items:
        sx, sy = client.world_to_view_offset(x, y, cam_x, cam_y)
        if not (-2 <= sx <= vis_w + 2 and -3 <= sy <= vis_h + 3):
            continue
        cx = sx * tile + tile // 2
        foot = sy * tile + tile
        rel = f"props/{kind}.png"
        label = None
        if kind == "lift" and inst is None:
            for f, pad in L.LIFT_PADS.items():
                if (x, y) == tuple(pad):
                    label = _LIFT_LABEL[f]
            for f, pad in L.LIFT_UP.items():
                if (x, y) == tuple(pad):
                    label = _UP_LABEL.get(f, "Lift up")
        if kind == "shaft_down":
            label = _SHAFT_LABEL
        near = px is not None and max(abs(x - px), abs(y - py)) <= 3

        def _draw(cx=cx, foot=foot, rel=rel, kind=kind, label=label, near=near, x=x, y=y):
            if kind == "signpost":
                img = _signpost(client, tile, x, y)
                if img is not None:
                    r_ = img.get_rect(midbottom=(cx + tile // 4, foot))
                    screen.blit(img, r_)
                    ent = next((e for e in L.SIGNPOSTS if (e[0], e[1]) == (x, y)), None)
                    bp = getattr(client, "blit_nameplate", None)
                    if ent and bp:                       # crisp UI text for the detail line
                        bp(ent[3], cx, r_.top - 4, (255, 226, 150))
                return
            if kind == "shaft_down":
                img = _by_width("props/shaft_down.png", tile * 2.1)
                if img is not None:
                    screen.blit(img, img.get_rect(midbottom=(cx, foot + tile // 2)))
                    if near:
                        bp = getattr(client, "blit_nameplate", None)
                        if bp:
                            bp(label, cx, foot - img.get_height() + tile // 2 - 6, (255, 226, 150))
                return
            if kind == "brazier":
                img = _brazier(tile, int(t * 8 + x * 3) % 6)
                screen.blit(img, img.get_rect(midbottom=(cx, foot)))
                return
            if kind == "crystal":
                img = _crystal(tile, x * 7 + y)
                screen.blit(img, img.get_rect(midbottom=(cx, foot)))
                return
            img = _by_height(rel, tile * PROP_H.get(kind, 1.2))
            if img is None:
                return
            alpha_img = img
            if kind == "lift":
                # A cage you step into: keep it see-through so the miner stays visible.
                key = ("lift_a", img.get_size())
                alpha_img = _CACHE.get(key)
                if alpha_img is None:
                    alpha_img = img.copy()
                    alpha_img.set_alpha(215)
                    _put(key, alpha_img)
            screen.blit(alpha_img, alpha_img.get_rect(midbottom=(cx, foot)))
            if kind in ("torch", "lantern"):
                fl = 0.8 + 0.2 * math.sin(t * 9.0 + cx * 0.37)
                r = int(tile * 0.7)
                glow = _glow(r, (120, 70, 24), round(fl, 1))
                top = foot - img.get_height() + int(tile * 0.18)
                screen.blit(glow, (cx - r, top - r), special_flags=pygame.BLEND_RGB_ADD)
            if label and near:
                bp = getattr(client, "blit_nameplate", None)
                if bp:
                    bp(label, cx, foot - img.get_height() - 8, (255, 226, 150))
        sort_y = foot - tile // 2 + tile // 3
        if kind == "shaft_down":
            sort_y = foot - tile * 2                     # a hole in the floor: under everyone
        draw_list.append((sort_y, 1, _draw))


# --------------------------------------------------------------------------- light
def _lights_for(client, inst):
    if inst is None:
        cry = [p for lv in (2, 3) for p in getattr(L, "CRYSTALS", {}).get(lv, [])]
        signs = [(e[0], e[1] - 0.4) for e in getattr(L, "SIGNPOSTS", [])]   # each sign carries a lantern
        return list(L.TORCH_LIGHTS) + [tuple(p) for p in L.LIFT_PADS.values()] + cry + signs
    if inst.get("kind") == "gauntlet":
        return [(2, 2.6), (41, 3.6)] + [(x, y + 0.6) for x, y in _gauntlet_braziers(inst)]
    return [(x, y + 0.6) for x, y in C_BRAZIERS]


def light(client, tile):
    """Per-floor darkness with soft torch pools and a small light around the player."""
    inst = _instance(client)
    if getattr(client, "dungeon", None) and inst is None:
        return
    map_w, map_h = _map_size()
    vis_w, vis_h = map_w // tile + 2, map_h // tile + 2
    bx0, by0, bx1, by1 = L.BOX
    lights = _lights_for(client, inst)
    px, py = client.player_xy() if getattr(client, "player", None) else (None, None)
    floor = (inst or {}).get("mine_floor") or 3
    small = pygame.Surface((vis_w, vis_h), pygame.SRCALPHA)
    small.fill((0, 0, 0, 0))
    any_dark = False
    for sx, sy, wx, wy in _visible_cells(client, tile):
        if sx >= vis_w or sy >= vis_h:
            continue
        if inst is None:
            if not (bx0 <= wx <= bx1 and by0 <= wy <= by1):
                continue
            reg = L.region(wx, wy)
            if reg in (None, "yard"):
                continue
            amb = L.AMBIENT.get(reg, 0.7)
            if reg in (2, 3):                              # v2: deeper levels are darker
                amb *= 0.88
        else:
            amb = 0.42 if inst.get("kind") == "colossus" else max(0.5, L.AMBIENT.get(floor, 0.3))
        base = (1.0 - amb) * (0.46 if inst is not None else (0.6 if reg not in (2, 3) else 0.66))
        d = min([math.hypot(wx - lx, wy - ly) for lx, ly in lights] or [99.0])
        lit = max(0.0, 1.0 - d / 5.0)
        if px is not None:
            lit = max(lit, max(0.0, 1.0 - math.hypot(wx - px, wy - py) / 5.5))
        a = int(255 * base * (1.0 - 0.9 * lit))
        if _is_wall(client, wx, wy):                   # rock mass fades into the dark away from the floor
            r1 = any(not _is_wall(client, wx + dx, wy + dy) for dx in (-1, 0, 1) for dy in (-1, 0, 1))
            if not r1:
                r2 = any(not _is_wall(client, wx + dx, wy + dy) for dx in (-2, -1, 0, 1, 2) for dy in (-2, -1, 0, 1, 2))
                if inst is None and (wx in (bx0, bx1) or wy in (by0, by1)):
                    r2 = True
                a = min(235, a + (55 if r2 else 120))
        if a > 0:
            any_dark = True
            small.set_at((sx, sy), (10, 7, 14, a))
    if not any_dark:
        return
    big = pygame.transform.smoothscale(small, (vis_w * tile, vis_h * tile))
    client.screen.blit(big, (-tile // 2, -tile // 2))
    try:
        _warm(client, tile, inst, lights)
    except Exception as e:
        print("deepdelve warm light:", e)
    if inst is None:
        try:
            _mask_levels(client, tile)
        except Exception as e:
            print("deepdelve level mask:", e)
    _level_fade(client, inst)


def _in_rect_pad(x, y, r, pad):
    return r[0] - pad <= x <= r[2] + pad and r[1] - pad <= y <= r[3] + pad


def _masked(cur, wx, wy):
    """True if world tile (wx, wy) belongs to another mine level than `cur` and must not show."""
    if cur in (2, 3):
        return not _in_rect_pad(wx, wy, L.CHAMBERS[cur], 1)
    if cur == 1:
        return any(_in_rect_pad(wx, wy, L.CHAMBERS[k], 0) for k in (2, 3))
    return False


def _player_level(client):
    if not getattr(client, "player", None):
        return None
    px, py = client.player_xy()
    return L.level_at(int(px), int(py))


def _masked_strict(cur, wx, wy):
    if cur in (2, 3):
        return not _in_rect_pad(wx, wy, L.CHAMBERS[cur], 0)
    return _masked(cur, wx, wy)


def _drop_masked_labels(client, tile, cur):
    """Queued name tags (ore, chests, pets, signs) standing on another level must not float in the rock."""
    s2t = getattr(client, "screen_to_tile", None)
    if s2t is None:
        return

    def hidden(cx, y):
        t_ = s2t(int(cx), int(y))
        return t_ is None or _masked_strict(cur, int(t_[0]), int(t_[1]))

    q = getattr(client, "_nameplate_queue", None)
    if q:
        keep = []
        for item in q:
            try:
                cx, ty = item[1], item[2]
                if all(hidden(cx, ty + tile * k) for k in (0.6, 1.6, 2.6)):
                    continue
            except Exception:
                pass
            keep.append(item)
        q[:] = keep
    q2 = getattr(client, "_np_queue", None)
    if q2:
        keep = []
        for p in q2:
            try:
                if hidden(p["cx"], p["feet"] - tile * 0.3):
                    continue
            except Exception:
                pass
            keep.append(p)
        q2[:] = keep


def _mask_levels(client, tile):
    """v2: each mine level reads as its own place.  On Levels 2/3 everything outside that cavern is
    solid deep rock; on the ground level the deeper caverns are hidden in the rock."""
    if not getattr(client, "player", None):
        return
    px, py = client.player_xy()
    cur = L.level_at(int(px), int(py))
    if cur is None:
        return
    screen = client.screen
    suffix = _TEX.get(cur, "") if cur in (2, 3) else ""
    shade = _depth_shade(tile, 236 if cur in (2, 3) else 190)
    for sx, sy, wx, wy in _visible_cells(client, tile):
        if not _masked(cur, wx, wy):
            continue
        rect = pygame.Rect(sx * tile, sy * tile, tile, tile)
        img = _tex_cell("tex_wall" + suffix, wx, wy, tile)
        if img is not None:
            screen.blit(img, rect)
        screen.blit(shade, rect)
    _drop_masked_labels(client, tile, cur)


_FADE = {"level": None, "t": 0.0}


def _level_fade(client, inst):
    """Short fade-through-black and a level title when the player changes mine level."""
    import time
    if inst is not None or not getattr(client, "player", None):
        return
    px, py = client.player_xy()
    lv = L.level_at(int(px), int(py))
    now = time.time()
    prev = getattr(client, "_mine_level_prev", None)
    client._mine_level_prev = lv
    if lv is not None and prev is not None and lv != prev and (lv >= 2 or prev >= 2):
        client._mine_fade = (now, lv)
    fade = getattr(client, "_mine_fade", None)
    if not fade:
        return
    dt = now - fade[0]
    if dt > 2.2:
        client._mine_fade = None
        return
    W, H = _map_size()
    a = int(255 * max(0.0, 1.0 - dt / 0.7))
    if a > 0:
        veil = pygame.Surface((W, H), pygame.SRCALPHA)
        veil.fill((4, 3, 6, a))
        client.screen.blit(veil, (0, 0))
    ta = int(255 * min(1.0, dt / 0.3) * max(0.0, min(1.0, (2.2 - dt) / 0.6)))
    if ta > 0:
        try:
            f = pygame.font.Font(None, 40)
        except Exception:
            return
        name = L.LEVEL_NAMES.get(fade[1], "")
        txt = f.render(name, True, (240, 222, 180))
        sh = f.render(name, True, (0, 0, 0))
        txt.set_alpha(ta)
        sh.set_alpha(ta)
        r = txt.get_rect(center=(W // 2, int(H * 0.28)))
        client.screen.blit(sh, r.move(2, 2))
        client.screen.blit(txt, r)


def _warm(client, tile, inst, lights):
    """Warm pools of fire light (and the Colossus's red heart glow), added after the darkness."""
    import time
    t = time.time()
    screen = client.screen
    W, H = screen.get_size()
    if inst is None:
        cry = {p for lv in (2, 3) for p in getattr(L, "CRYSTALS", {}).get(lv, [])}
        for cx_, cy_ in cry:
            x, y = _world_to_screen(client, tile, cx_, cy_ - 0.3)
            r = int(tile * 2.0)
            if -r < x < W + r and -r < y < H + r:
                k = round(0.8 + 0.2 * math.sin(t * 1.7 + cx_ * 1.3), 1)
                screen.blit(_glow(r, (40, 60, 120), k), (x - r, y - r), special_flags=pygame.BLEND_RGB_ADD)
        lights = [p for p in lights if p not in cry]
        lights = [p for p in lights if L.region(int(p[0]), int(p[1])) not in (None, "yard")]
    for lx, ly in lights:
        x, y = _world_to_screen(client, tile, lx, ly)
        r = int(tile * 2.4)
        if -r < x < W + r and -r < y < H + r:
            fl = round(0.85 + 0.15 * math.sin(t * 7.0 + lx * 1.7), 1)
            screen.blit(_glow(r, (64, 36, 14), fl), (x - r, y - r), special_flags=pygame.BLEND_RGB_ADD)
            r2 = int(tile * 0.7)
            screen.blit(_glow(r2, (150, 90, 30), fl), (x - r2, y - tile * 1.6 - r2), special_flags=pygame.BLEND_RGB_ADD)
    if inst is None:                                   # v5: ore veins give the dark floors a cold shine
        for fl_ in (2, 3):
            col = _ORE_GLINT[fl_]
            for rx, ry, *_ in L.CHAMBER_ROCKS.get(fl_, []):
                x, y = _world_to_screen(client, tile, rx, ry)
                r = int(tile * 1.9)
                if -r < x < W + r and -r < y < H + r:
                    k = round(0.75 + 0.25 * math.sin(t * 1.3 + rx * 0.9 + ry), 1)
                    screen.blit(_glow(r, tuple(c // 3 for c in col), k), (x - r, y - r),
                                special_flags=pygame.BLEND_RGB_ADD)
    elif inst.get("kind") == "gauntlet" and int(inst.get("mine_floor") or 0) >= 3:
        for lx, ly in lights[2:]:                      # v5: brazier light spills wide across the elite floor
            x, y = _world_to_screen(client, tile, lx, ly + 1.4)
            r = int(tile * 3.4)
            if -r < x < W + r and -r < y < H + r:
                screen.blit(_glow(r, (46, 28, 12), 1.0), (x - r, y - r), special_flags=pygame.BLEND_RGB_ADD)
    if inst is not None and inst.get("kind") == "colossus":
        k = round(0.7 + 0.3 * math.sin(t * 2.0), 1)
        for pts in _cracks():
            for fx, fy in pts[1::2]:
                if math.hypot(fx - 8, fy - 4.6) < 1.6:
                    continue
                x, y = _world_to_screen(client, tile, fx, fy)
                r = int(tile * 0.8)
                screen.blit(_glow(r, (120, 22, 10), k), (x - r, y - r), special_flags=pygame.BLEND_RGB_ADD)
        for cx_, cy_ in C_CRYSTALS:
            x, y = _world_to_screen(client, tile, cx_, cy_ - 0.2)
            r = int(tile * 1.3)
            screen.blit(_glow(r, (110, 14, 26), k), (x - r, y - r), special_flags=pygame.BLEND_RGB_ADD)
        x, y = _world_to_screen(client, tile, 8, 5.2)
        r = int(tile * 2.2)
        screen.blit(_glow(r, (70, 14, 8), k), (x - r, y - r), special_flags=pygame.BLEND_RGB_ADD)


def draw_exit(client, cx, cy, tile):
    """Mine instances leave by lift cage, not a cave mouth."""
    img = _by_height("props/lift.png", tile * PROP_H["lift"])
    if img is None:
        return False
    client.screen.blit(img, img.get_rect(midbottom=(cx, cy + tile // 2)))
    bp = getattr(client, "blit_nameplate", None)
    if bp:
        bp("LIFT UP", cx, cy - img.get_height() + tile // 2 - 8, (255, 220, 90))
    return True


# --------------------------------------------------------------------------- v4 cave dressing
import random as _random

_ORE_GLINT = {"yard": (214, 130, 70), 0: (214, 130, 70), 1: (226, 140, 72), 2: (170, 196, 230),
              3: (120, 230, 140), "heart": (255, 70, 50)}


def _h(x, y, s=0):
    v = (x * 73856093) ^ (y * 19349663) ^ (s * 83492791)
    return (v ^ (v >> 13)) & 0xFFFFFFFF


def _decal(kind, var, tile, glint):
    """Painted floor detail for one tile: crack, rubble or ore glints (SRCALPHA, cached)."""
    key = ("dec", kind, var, tile, glint)
    if key in _CACHE:
        return _CACHE[key]
    rnd = _random.Random(var * 977 + len(kind))
    s = pygame.Surface((tile, tile), pygame.SRCALPHA)
    if kind == "crack":
        x, y = rnd.uniform(0.15, 0.85) * tile, rnd.uniform(0.15, 0.85) * tile
        ang = rnd.uniform(0, math.tau)
        pts = [(x, y)]
        for _ in range(rnd.randint(3, 5)):
            ang += rnd.uniform(-0.9, 0.9)
            x += math.cos(ang) * tile * 0.16
            y += math.sin(ang) * tile * 0.16
            pts.append((x, y))
        w = max(1, tile // 26)
        pygame.draw.lines(s, (170, 150, 128, 50), False, [(a + 1, b + 1) for a, b in pts], w)
        pygame.draw.lines(s, (18, 12, 10, 170), False, pts, w)
        bx, by = pts[len(pts) // 2]
        ang2 = ang + 1.4
        pygame.draw.line(s, (18, 12, 10, 120), (bx, by),
                         (bx + math.cos(ang2) * tile * 0.18, by + math.sin(ang2) * tile * 0.18), max(1, w - 1))
    elif kind == "rubble":
        for _ in range(rnd.randint(3, 7)):
            r = rnd.uniform(0.035, 0.09) * tile
            x, y = rnd.uniform(0.15, 0.85) * tile, rnd.uniform(0.2, 0.85) * tile
            g = rnd.randint(70, 118)
            rect = pygame.Rect(0, 0, int(r * 2.3), int(r * 1.6))
            rect.center = (int(x), int(y + r * 0.5))
            pygame.draw.ellipse(s, (8, 6, 6, 110), rect)              # contact shadow
            rect.center = (int(x), int(y))
            pygame.draw.ellipse(s, (g, int(g * 0.88), int(g * 0.76), 255), rect)
            hl = rect.inflate(-rect.w // 2, -rect.h // 2).move(-rect.w // 8, -rect.h // 6)
            pygame.draw.ellipse(s, (min(255, g + 55), min(255, int(g * 0.9) + 50), min(255, int(g * 0.8) + 40), 200), hl)
    elif kind == "glint":
        for _ in range(rnd.randint(2, 4)):
            x, y = int(rnd.uniform(0.15, 0.85) * tile), int(rnd.uniform(0.15, 0.85) * tile)
            r = max(1, int(tile * rnd.uniform(0.02, 0.04)))
            pygame.draw.polygon(s, glint + (235,), [(x, y - r * 2), (x + r, y), (x, y + r * 2), (x - r, y)])
            pygame.draw.circle(s, (255, 250, 230, 120), (x, y - r // 2), max(1, r // 3))
    return _put(key, s)


def _edge(d, var, tile, suffix):
    """Ragged rock spilling from the wall on side d ('n','s','w','e') onto a floor tile."""
    key = ("edge", d, var, tile, suffix)
    if key in _CACHE:
        return _CACHE[key]
    s = pygame.Surface((tile, tile), pygame.SRCALPHA)
    # ambient occlusion away from the wall
    depth = int(tile * (0.55 if d == "n" else 0.38))
    for i in range(depth):
        a = int(190 * (1 - i / float(depth)) ** 1.6)
        if d == "n":
            r = pygame.Rect(0, i, tile, 1)
        elif d == "s":
            r = pygame.Rect(0, tile - 1 - i, tile, 1)
        elif d == "w":
            r = pygame.Rect(i, 0, 1, tile)
        else:
            r = pygame.Rect(tile - 1 - i, 0, 1, tile)
        s.fill((6, 4, 6, a), r)
    wall = _tex_cell("tex_wall" + suffix, var % 4, (var // 4) % 4, tile)
    rnd = _random.Random(var * 31 + ord(d))
    for k in range(rnd.randint(2, 3)):
        along = (k + rnd.uniform(0.15, 0.85)) / 3.0 * tile
        rr = rnd.uniform(0.2, 0.34) * tile
        into = rnd.uniform(-0.25, 0.25) * rr
        if d == "n":
            c = (along, into)
        elif d == "s":
            c = (along, tile - into)
        elif d == "w":
            c = (into, along)
        else:
            c = (tile - into, along)
        b = pygame.Rect(0, 0, int(rr * 2.2), int(rr * 1.8))
        b.center = (int(c[0]), int(c[1] + rr * 0.35))
        pygame.draw.ellipse(s, (6, 4, 6, 120), b)                     # shadow on the floor
        b.center = (int(c[0]), int(c[1]))
        m = pygame.Surface(b.size, pygame.SRCALPHA)
        pts = []
        n = 9
        for j in range(n):
            ang = j / float(n) * math.tau
            f = rnd.uniform(0.78, 1.0)
            pts.append((b.w / 2 + math.cos(ang) * b.w / 2 * f, b.h / 2 + math.sin(ang) * b.h / 2 * f))
        pygame.draw.polygon(m, (255, 255, 255, 255), pts)
        if wall is not None:
            tex = pygame.Surface(b.size, pygame.SRCALPHA)
            tex.blit(wall, (-(b.x % tile), -(b.y % tile)))
            tex.blit(wall, (tile - (b.x % tile), -(b.y % tile)))
            tex.fill((205, 190, 175, 255), special_flags=pygame.BLEND_RGBA_MULT)
            tex.blit(m, (0, 0), special_flags=pygame.BLEND_RGBA_MIN)
        else:
            tex = m
            tex.fill((84, 72, 62, 255), special_flags=pygame.BLEND_RGBA_MULT)
        # lit top rim, dark lower half
        rim = pygame.Surface(b.size, pygame.SRCALPHA)
        for y in range(b.h):
            f = y / float(max(1, b.h))
            if f < 0.35:
                rim.fill((255, 240, 220, int(70 * (1 - f / 0.35))), pygame.Rect(0, y, b.w, 1))
            elif f > 0.55:
                rim.fill((0, 0, 0, int(120 * (f - 0.55) / 0.45)), pygame.Rect(0, y, b.w, 1))
        rim.blit(m, (0, 0), special_flags=pygame.BLEND_RGBA_MIN)
        tex.blit(rim, (0, 0))
        s.blit(tex, b.topleft)
    return _put(key, s)


def _depth_shade(tile, a):
    key = ("deep", tile, a)
    if key in _CACHE:
        return _CACHE[key]
    s = pygame.Surface((tile, tile), pygame.SRCALPHA)
    s.fill((8, 5, 8, a))
    return _put(key, s)


def _brazier(tile, frame):
    """Iron brazier on a tripod with a live coal fire (procedural, cached per flicker frame)."""
    key = ("braz", tile, frame)
    if key in _CACHE:
        return _CACHE[key]
    w, h = int(tile * 1.15), int(tile * 1.85)
    s = pygame.Surface((w, h), pygame.SRCALPHA)
    cx = w // 2
    bowl_y = int(h * 0.52)
    iron, iron_hi = (34, 28, 26), (92, 80, 70)
    lw = max(2, tile // 16)
    for fx in (-0.36, 0.0, 0.36):                                      # tripod legs
        pygame.draw.line(s, iron, (cx + int(fx * w * 0.5), bowl_y), (cx + int(fx * w * 1.05), h - 2), lw)
    pygame.draw.ellipse(s, (0, 0, 0, 90), (cx - w * 0.4, h - tile * 0.12, w * 0.8, tile * 0.12))
    bowl = pygame.Rect(0, 0, int(w * 0.82), int(h * 0.2))
    bowl.midtop = (cx, bowl_y - bowl.h // 2)
    pygame.draw.ellipse(s, iron, bowl)
    pygame.draw.rect(s, iron, (bowl.x, bowl.y, bowl.w, bowl.h // 2))
    pygame.draw.ellipse(s, iron_hi, (bowl.x, bowl.y - bowl.h // 4, bowl.w, bowl.h // 2), max(1, lw // 2))
    pygame.draw.ellipse(s, (210, 90, 30), (bowl.x + 3, bowl.y - bowl.h // 5, bowl.w - 6, bowl.h // 2.6))
    for k in range(5):                                                 # glowing coals
        x = bowl.x + 6 + k * (bowl.w - 12) // 4
        pygame.draw.circle(s, (255, 190, 80), (x, bowl.y - 1), max(1, tile // 24))
    rnd = _random.Random(frame * 17)
    base_y = bowl.y - 2
    for layer, (col, sc) in enumerate((((230, 80, 20), 1.0), ((255, 150, 40), 0.72), ((255, 230, 150), 0.42))):
        fh = h * 0.42 * sc * rnd.uniform(0.85, 1.12)
        fw = bowl.w * 0.42 * sc
        lean = rnd.uniform(-0.12, 0.12) * w
        pts = []
        for j in range(25):                                            # teardrop with a licking tip
            u = j / 24.0 * math.pi
            yy = base_y - fh * (1 - math.cos(u)) / 2.0
            k = (1 - (1 - math.cos(u)) / 2.0)
            xx = math.sin(u) * 0 + fw * math.sqrt(max(0.0, k)) * (1.0 - 0.15 * math.sin(u * 3 + frame))
            pts.append((cx - xx + lean * (1 - k), yy))
        pts += [(2 * cx - px + 2 * lean * (1 - ((base_y - py) / fh if fh else 0)) * 0, py) for px, py in reversed(pts)]
        pygame.draw.polygon(s, col + (220,), pts)
    return _put(key, s)


def _crystal(tile, var):
    """Red heart-crystal cluster (procedural)."""
    key = ("cry", tile, var)
    if key in _CACHE:
        return _CACHE[key]
    rnd = _random.Random(var * 131)
    w, h = int(tile * 1.0), int(tile * 1.2)
    s = pygame.Surface((w, h), pygame.SRCALPHA)
    pygame.draw.ellipse(s, (0, 0, 0, 100), (w * 0.12, h - tile * 0.18, w * 0.76, tile * 0.16))
    for k in range(rnd.randint(3, 5)):
        bx = w * rnd.uniform(0.28, 0.72)
        ang = rnd.uniform(-0.55, 0.55)
        ln = h * rnd.uniform(0.45, 0.85)
        sw = w * rnd.uniform(0.07, 0.12)
        base = (bx, h - tile * 0.1)
        tip = (bx + math.sin(ang) * ln, base[1] - math.cos(ang) * ln)
        nx, ny = math.cos(ang) * sw, math.sin(ang) * sw
        mid = (base[0] + (tip[0] - base[0]) * 0.8, base[1] + (tip[1] - base[1]) * 0.8)
        left = [(base[0] - nx, base[1] - ny), (mid[0] - nx, mid[1] - ny), tip, mid]
        right = [(base[0] + nx, base[1] + ny), (mid[0] + nx, mid[1] + ny), tip, mid]
        pygame.draw.polygon(s, (150, 20, 34, 245), right)
        pygame.draw.polygon(s, (226, 58, 66, 245), left)
        pygame.draw.line(s, (255, 170, 170, 230), (base[0], base[1]), tip, 1)
    return _put(key, s)


def _cracks():
    """World-space heart-vein cracks radiating from the Colossus's seat."""
    if "_cracks" in _CACHE:
        return _CACHE["_cracks"]
    rnd = _random.Random(9)
    lines = []
    for k in range(8):
        ang = k / 8.0 * math.tau + rnd.uniform(-0.25, 0.25)
        x, y = 8.0, 4.6
        pts = [(x, y)]
        for step in range(rnd.randint(6, 9)):
            ang += rnd.uniform(-0.45, 0.45)
            x += math.cos(ang) * rnd.uniform(0.55, 0.9)
            y += math.sin(ang) * rnd.uniform(0.45, 0.75)
            if not (1.6 < x < 14.4 and 1.6 < y < 10.4):
                break
            pts.append((x, y))
            if step == 2 and rnd.random() < 0.6:
                a2, bx, by = ang + rnd.choice((-1, 1)) * 0.9, x, y
                br = [(bx, by)]
                for _ in range(3):
                    bx += math.cos(a2) * 0.6
                    by += math.sin(a2) * 0.5
                    br.append((bx, by))
                lines.append(br)
        lines.append(pts)
    return _put("_cracks", lines)


C_CRYSTALS = [(3, 3), (13, 3), (2, 5), (14, 6), (2, 8), (14, 8), (5, 10), (11, 10), (6, 1), (10, 1)]
C_BRAZIERS = [(4, 2), (12, 2), (3, 9), (13, 9)]


def _gauntlet_braziers(inst):
    out = []
    for r in inst.get("rooms") or []:
        out += [(r[0] + 1, r[1]), (r[2] - 1, r[1])]
    return out


def _world_to_screen(client, tile, fx, fy):
    cam_x, cam_y = client.camera_origin()
    ax, ay = client.world_to_view_offset(0, 0, cam_x, cam_y)
    bx, by = client.world_to_view_offset(1, 0, cam_x, cam_y)
    cx, cy = client.world_to_view_offset(0, 1, cam_x, cam_y)
    sx = ax + fx * (bx - ax) + fy * (cx - ax)
    sy = ay + fx * (by - ay) + fy * (cy - ay)
    return sx * tile + tile / 2.0, sy * tile + tile / 2.0


def _is_wall(client, x, y):
    if not _instance(client) and ((x, y) in ROCK_XY or (x, y) in _PROP_BLOCK or (x, y) in _CHEST_XY):
        return False                               # rocks, chests and props stand on floor stone
    t = _tile_at(client, x, y)
    return t is None or t == wm.WALL


def dress(client, tile):
    """v4: rubble, cracks, ore glints, ragged rock edges and deep-rock shading (after paint_ground)."""
    if not ready():
        return
    inst = _instance(client)
    if getattr(client, "dungeon", None) and inst is None:
        return
    screen = client.screen
    bx0, by0, bx1, by1 = L.BOX
    floor = (inst or {}).get("mine_floor") or 1
    colossus = bool(inst) and inst.get("kind") == "colossus"
    skip = set(ROCK_XY) | _PROP_BLOCK | _CHEST_XY | set(L.RAILS)
    rx0, ry0, rx1, ry1 = L.RAMP
    tint = _CACHE.get(("ctint", tile)) or _put(("ctint", tile), _solid(tile, (236, 196, 188)))
    for sx, sy, wx, wy in _visible_cells(client, tile):
        if inst is None:
            if not (bx0 <= wx <= bx1 and by0 <= wy <= by1):
                continue
            reg = L.region(wx, wy)
            reg = 0 if reg is None else reg
            suffix = _TEX.get(reg, "")
        else:
            reg = floor
            suffix = "" if colossus else _TEX.get(floor, "")
        tid = _tile_at(client, wx, wy)
        if tid is None:
            continue
        rect = pygame.Rect(sx * tile, sy * tile, tile, tile)
        if colossus:
            screen.blit(tint, rect, special_flags=pygame.BLEND_RGB_MULT)
        if tid == wm.WALL:
            continue                                   # deep-rock falloff lives in light() (smooth)
        if inst is not None and not colossus and floor >= 2:       # deep floors: lift the dark stone a touch
            screen.blit(_CACHE.get(("lift", tile)) or _put(("lift", tile), _solid(tile, (16, 15, 12))), rect,
                        special_flags=pygame.BLEND_RGB_ADD)
        if (wx, wy) in skip or (rx0 <= wx <= rx1 and ry0 <= wy <= ry1):
            continue
        hv = _h(wx, wy, floor)
        roll = hv % 100
        var = (hv >> 8) % 6
        glint = _ORE_GLINT["heart" if colossus else reg]
        if roll < 16:
            screen.blit(_decal("crack", var, tile, glint), rect)
        elif roll < 36:
            screen.blit(_decal("rubble", var, tile, glint), rect)
        elif roll < 46:
            screen.blit(_decal("glint", var, tile, glint), rect)
        for d, dx, dy in (("n", 0, -1), ("s", 0, 1), ("w", -1, 0), ("e", 1, 0)):
            if _is_wall(client, wx + dx, wy + dy) and (inst is not None or reg != "yard" or d != "n" or wy - 1 > by0):
                screen.blit(_edge(d, (hv >> (12 + len(d))) % 16, tile, suffix), rect)
    if colossus:
        _paint_cracks(client, tile)
    if inst is None and _player_level(client) not in (2, 3):
        _yard_fringe(client, tile)


def _solid(tile, rgb):
    s = pygame.Surface((tile, tile))
    s.fill(rgb)
    return s


def _paint_cracks(client, tile):
    import time
    k = 0.75 + 0.25 * math.sin(time.time() * 2.0)
    screen = client.screen
    for pts in _cracks():
        sp = [_world_to_screen(client, tile, x, y) for x, y in pts]
        if len(sp) < 2:
            continue
        pygame.draw.lines(screen, (22, 6, 6), False, sp, max(3, tile // 7))
        pygame.draw.lines(screen, (int(200 * k), int(40 * k), 24), False, sp, max(2, tile // 12))
        pygame.draw.lines(screen, (255, int(150 * k), 90), False, sp, max(1, tile // 28))


def _yard_fringe(client, tile):
    """Soften the straight grass-to-rock line on the mine's outer ring: grass spills over ragged stone."""
    screen = client.screen
    bx0, by0, bx1, by1 = L.BOX
    W, H = screen.get_size()
    for sx, sy, wx, wy in _visible_cells(client, tile):
        if not (bx0 <= wx <= bx1 and by0 <= wy <= by1):
            continue
        for d, dx, dy in (("n", 0, -1), ("w", -1, 0), ("e", 1, 0), ("s", 0, 1)):
            ox, oy = wx + dx, wy + dy
            if bx0 <= ox <= bx1 and by0 <= oy <= by1:
                continue
            if _tile_at(client, ox, oy) in (None, wm.WALL):
                continue
            # the neighbour's on-screen cell (may differ under camera yaw)
            cam_x, cam_y = client.camera_origin()
            nsx, nsy = client.world_to_view_offset(ox, oy, cam_x, cam_y)
            src = pygame.Rect(nsx * tile, nsy * tile, tile, tile)
            if not screen.get_rect().contains(src):
                continue
            ddx, ddy = nsx - sx, nsy - sy
            side = {(0, -1): "n", (0, 1): "s", (-1, 0): "w", (1, 0): "e"}.get((ddx, ddy))
            if side is None:
                continue
            grass = screen.subsurface(src).copy().convert_alpha()
            m = _fringe_mask(side, _h(wx, wy, 5) % 8, tile)
            grass.blit(m, (0, 0), special_flags=pygame.BLEND_RGBA_MIN)
            dst = pygame.Rect(sx * tile, sy * tile, tile, tile)
            screen.blit(_fringe_shadow(side, _h(wx, wy, 5) % 8, tile), dst)
            screen.blit(grass, dst)


def _fringe_profile(var, tile):
    rnd = _random.Random(var * 53 + 1)
    ph = [rnd.uniform(0, math.tau) for _ in range(3)]
    return [tile * (0.30 + 0.12 * math.sin(i / tile * math.tau * 1.0 + ph[0])
                    + 0.08 * math.sin(i / tile * math.tau * 2.0 + ph[1])
                    + 0.05 * math.sin(i / tile * math.tau * 5.0 + ph[2])) for i in range(tile)]


def _orient(s, side):
    if side == "n":
        return s
    if side == "s":
        return pygame.transform.flip(s, False, True)
    if side == "w":
        return pygame.transform.rotate(s, 90)
    return pygame.transform.rotate(s, -90)


def _fringe_mask(side, var, tile):
    key = ("fmask", side, var, tile)
    if key in _CACHE:
        return _CACHE[key]
    prof = _fringe_profile(var, tile)
    s = pygame.Surface((tile, tile), pygame.SRCALPHA)
    rnd = _random.Random(var)
    for x in range(tile):
        L_ = int(prof[x])
        for y in range(min(tile, L_ + 4)):
            a = 255 if y < L_ - 3 else max(0, int(255 * (L_ + 4 - y) / 7.0))
            s.set_at((x, y), (255, 255, 255, a))
        if rnd.random() < 0.22:                                           # grass blades over the lip
            bl = int(tile * rnd.uniform(0.05, 0.14))
            for y in range(L_, min(tile, L_ + bl)):
                s.set_at((x, y), (255, 255, 255, 230))
    return _put(key, _orient(s, side))


def _fringe_shadow(side, var, tile):
    key = ("fshad", side, var, tile)
    if key in _CACHE:
        return _CACHE[key]
    prof = _fringe_profile(var, tile)
    s = pygame.Surface((tile, tile), pygame.SRCALPHA)
    for x in range(tile):
        L_ = int(prof[x])
        for y in range(L_, min(tile, L_ + int(tile * 0.22))):
            a = int(140 * (1 - (y - L_) / (tile * 0.22)))
            s.set_at((x, y), (10, 8, 4, a))
    return _put(key, _orient(s, side))
