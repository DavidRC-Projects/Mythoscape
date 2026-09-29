"""The Depths v2 tile art: crypt floors, bone walls, sarcophagi, and grasping hands.

Fog, zone banners, parchment, and the boss bar are the shared Void overlay.
This module only draws what is crypt-specific.
"""
import math
import sys

import pygame

import procedural_sprites_finished as sprites
import prop_sprites
import rs_style as rs

FLOOR_PAL = {
    "chapel": ((96, 98, 88), (86, 88, 78), (104, 106, 94), (78, 80, 72)),
    "ossuary": ((112, 104, 88), (100, 92, 78), (120, 112, 96), (92, 84, 72)),
    "catacomb": ((70, 80, 70), (62, 72, 62), (78, 88, 76), (56, 66, 58)),
    "tomb": ((84, 86, 90), (76, 78, 82), (92, 94, 98), (70, 72, 76)),
    "mausoleum": ((88, 82, 74), (78, 72, 66), (96, 90, 80), (70, 64, 58)),
    "wyrm": ((92, 76, 60), (82, 68, 54), (100, 84, 66), (74, 60, 48)),
    "arena": ((64, 60, 58), (58, 54, 52), (70, 66, 62), (52, 48, 46)),
    "bridge": ((150, 140, 116), (140, 130, 108), (158, 148, 122), (132, 122, 100)),
}
WALL_PAL = {
    "chapel": (70, 74, 66), "ossuary": (120, 110, 90), "catacomb": (52, 62, 54), "tomb": (62, 64, 70),
    "mausoleum": (66, 60, 54), "wyrm": (70, 56, 44), "arena": (44, 40, 40), "bridge": (40, 36, 34),
}
CANDLE = (255, 190, 90)


def _seed(x, y, n):
    fn = getattr(sprites, "_seeded", None)
    if fn:
        return fn(x, y, n)
    return ((x * 13 + y * 7 + n * 3) % 1000) / 1000.0


def _tile(client):
    main = sys.modules.get("__main__")
    if main is not None and hasattr(main, "TILE"):
        return main.TILE
    return 32


def _glow(surf, cx, cy, r, col, a):
    r = max(2, int(r))
    g = pygame.Surface((r * 2, r * 2), pygame.SRCALPHA)
    for k in range(4):
        pygame.draw.circle(g, (*col, int(a * (k + 1) / 4)), (r, r), int(r * (1 - k * 0.22)))
    surf.blit(g, (int(cx - r), int(cy - r)))


def style_at(d, x, y):
    decor = (d.get("decor") or {}).get(f"{x},{y}", "")
    if decor in ("bridge", "pit", "deep", "shallow"):
        return "bridge"
    found = "arena"
    for zone in d.get("zones") or []:
        if zone.get("id") == "stair":
            continue
        x0, y0, x1, y1 = zone["rect"]
        if x0 <= x <= x1 and y0 <= y <= y1:
            found = zone.get("style") or found
            break
    return found


def draw_tile(client, rect, tile_id, wx, wy, t):
    import world_map as wm
    d = client.dungeon
    decor = (d.get("decor") or {}).get(f"{wx},{wy}", "")
    style = style_at(d, wx, wy)
    hands = _hands_here(d, wx, wy)
    if decor == "pit":
        draw_abyss(client.screen, rect, wx, wy, t)
        return
    if decor == "deep":
        draw_deep_water(client.screen, rect, wx, wy, t)
        return
    if decor == "bridge":
        draw_bridge(client.screen, rect, wx, wy, t, hands=hands)
        return
    if tile_id == wm.WALL:
        draw_wall_top(client.screen, rect, wx, wy, style, decor, t)
        return
    draw_floor(client.screen, rect, wx, wy, style, t)
    if decor == "shallow":
        draw_shallow_water(client.screen, rect, wx, wy, t)
    _prop(client, rect, decor, style, wx, wy, t)
    if hands:
        draw_grasping_hands(client.screen, rect, t, telegraph=True)


def _hands_here(d, wx, wy):
    for mark in d.get("telegraphs") or []:
        if mark.get("kind") != "hands":
            continue
        for pair in mark.get("tiles") or []:
            if int(pair[0]) == wx and int(pair[1]) == wy:
                return True
    return False


def draw_floor(surf, rect, x, y, style, t=0.0):
    pal = FLOOR_PAL.get(style, FLOOR_PAL["tomb"])
    base = pal[int(_seed(x, y, 1) * 4) % 4]
    hi, mid, sh, deep = rs.material(base)
    pygame.draw.rect(surf, mid, rect)
    pygame.draw.line(surf, hi, (rect.left + 1, rect.top + 1), (rect.right - 2, rect.top + 1))
    pygame.draw.line(surf, hi, (rect.left + 1, rect.top + 1), (rect.left + 1, rect.bottom - 2))
    pygame.draw.line(surf, sh, (rect.left + 1, rect.bottom - 1), (rect.right - 1, rect.bottom - 1))
    pygame.draw.rect(surf, deep, rect, 1)
    w = rect.w
    r = _seed(x, y, 5)
    if style in ("chapel", "catacomb", "mausoleum") and r < 0.28:
        for k in range(3):
            mx = rect.x + int(w * (0.2 + 0.6 * _seed(x, y, 20 + k)))
            my = rect.y + int(w * (0.2 + 0.6 * _seed(x, y, 30 + k)))
            pygame.draw.circle(surf, (70, 100, 50), (mx, my), max(1, w // 12))
    if style == "ossuary" and r < 0.22:
        bx = rect.x + int(w * (0.2 + 0.5 * _seed(x, y, 6)))
        by = rect.y + int(w * (0.3 + 0.4 * _seed(x, y, 7)))
        pygame.draw.line(surf, (226, 216, 190), (bx, by), (bx + w // 3, by + w // 8), max(1, w // 14))
    if style == "tomb" and (x + y) % 3 == 0:
        pygame.draw.rect(surf, sh, rect.inflate(-w // 4, -w // 4), 1)
    if style == "arena" and r < 0.14:
        pygame.draw.circle(surf, (120, 30, 30), (rect.x + int(w * 0.6), rect.y + int(w * 0.4)), max(1, w // 9))


def draw_wall_top(surf, rect, x, y, style, decor, t):
    base = WALL_PAL.get(style, (60, 60, 60))
    hi, mid, _sh, _deep = rs.material(base)
    cap = pygame.Rect(rect.x, rect.y, rect.w, max(4, rect.h // 3))
    pygame.draw.rect(surf, rs.shade(mid, 8), cap)
    pygame.draw.line(surf, hi, cap.topleft, (cap.right - 1, cap.top))
    if decor == "skull":
        draw_skull_niche(surf, rect, t)
    if decor == "secret":
        pygame.draw.rect(surf, (170, 164, 150), rect.inflate(-rect.w // 5, -rect.h // 5), 1)


def draw_wall_face(surf, rect, x, y, style, decor, t=0.0):
    base = WALL_PAL.get(style, (60, 60, 60))
    hi, mid, sh, deep = rs.material(base)
    face = pygame.Rect(rect.x, rect.y + rect.h // 3, rect.w, rect.h - rect.h // 3)
    pygame.draw.rect(surf, mid, face)
    w = rect.w
    if style == "ossuary" or decor == "skull":
        pygame.draw.rect(surf, (96, 86, 70), face)
        for i in range(2):
            yy = face.y + i * face.h // 2 + face.h // 4
            for k in range(2):
                sx = face.x + int(w * (0.28 + 0.44 * k))
                rr = max(2, w // 8)
                pygame.draw.circle(surf, (222, 212, 186), (sx, yy), rr)
                pygame.draw.circle(surf, (40, 34, 28), (sx - rr // 2, yy - 1), max(1, rr // 3))
                pygame.draw.circle(surf, (40, 34, 28), (sx + rr // 2, yy - 1), max(1, rr // 3))
    else:
        rows = 3
        bh = max(2, face.h // rows)
        for i in range(rows):
            yy = face.y + i * bh
            pygame.draw.line(surf, sh, (face.x, yy), (face.right - 1, yy))
            off = (face.w // 2) if (i + x) % 2 else 0
            for bx in range(face.x - off, face.right, max(4, face.w // 2)):
                if face.x < bx < face.right:
                    pygame.draw.line(surf, sh, (bx, yy), (bx, yy + bh - 1))
        if style in ("chapel", "catacomb", "mausoleum") and _seed(x, y, 15) < 0.4:
            mx = face.x + int(w * _seed(x, y, 16))
            pygame.draw.line(surf, (74, 110, 56), (mx, face.y), (mx, face.y + face.h // 2), max(1, w // 12))
    pygame.draw.line(surf, deep, (face.x, face.bottom - 1), (face.right - 1, face.bottom - 1))
    pygame.draw.line(surf, hi, face.topleft, (face.right - 1, face.top))
    if decor == "secret":
        for k in range(2):
            br = pygame.Rect(face.x + w // 6 + k * w // 3, face.y + face.h // 4 + k * face.h // 4, w // 3, face.h // 4)
            pygame.draw.rect(surf, rs.shade(mid, 22), br)
            pygame.draw.rect(surf, (20, 18, 16), br, 1)
    if decor == "skull":
        draw_skull_niche(surf, face, t)
    if decor and decor.startswith("seal"):
        key = decor.split(":")[-1]
        col = {"A": (210, 180, 120), "B": (80, 160, 150), "C": (180, 60, 50)}.get(key, (180, 170, 140))
        pygame.draw.rect(surf, col, face.inflate(-w // 3, -face.h // 3))
        pygame.draw.rect(surf, (30, 24, 18), face.inflate(-w // 3, -face.h // 3), 1)


def draw_skull_niche(surf, rect, t=0.0):
    w = rect.w
    nr = rect.inflate(-w // 4, -w // 4)
    pygame.draw.rect(surf, (22, 24, 20), nr)
    pygame.draw.rect(surf, (90, 86, 76), nr, 1)
    for k, (fx, fy) in enumerate(((0.3, 0.35), (0.7, 0.35), (0.5, 0.72))):
        sx, sy = rect.x + int(w * fx), rect.y + int(w * fy)
        rr = max(2, w // 9)
        pygame.draw.circle(surf, (224, 214, 188), (sx, sy), rr)
        if k == 2:
            p = 0.6 + 0.4 * math.sin(t * 3)
            pygame.draw.circle(surf, (int(255 * p), int(210 * p), 90), (sx + rr // 2, sy - 1), max(1, rr // 3))
        else:
            pygame.draw.circle(surf, (30, 26, 22), (sx - rr // 2, sy - 1), max(1, rr // 3))
            pygame.draw.circle(surf, (30, 26, 22), (sx + rr // 2, sy - 1), max(1, rr // 3))


def draw_abyss(surf, rect, x, y, t=0.0):
    pygame.draw.rect(surf, (10, 10, 9), rect)
    rnd = __import__("random").Random(x * 131 + y * 17)
    if rnd.random() < 0.35:
        px = rect.x + rnd.randrange(max(1, rect.w))
        py = rect.y + rnd.randrange(max(1, rect.h))
        pygame.draw.line(surf, (70, 66, 56), (px, py), (px + rect.w // 5, py + 1))
    mist = 0.5 + 0.5 * math.sin(x * 0.4 + y * 0.25 + t)
    ov = pygame.Surface(rect.size, pygame.SRCALPHA)
    ov.fill((150, 160, 140, int(22 * mist)))
    surf.blit(ov, rect.topleft)


def draw_bridge(surf, rect, x, y, t=0.0, hands=False):
    draw_abyss(surf, rect, x, y, t)
    slab = rect.inflate(-max(2, rect.w // 8), 0)
    pygame.draw.rect(surf, (178, 168, 140), slab)
    for k in range(3):
        yy = slab.y + int(slab.h * (0.2 + 0.3 * k))
        pygame.draw.line(surf, (226, 216, 190), (slab.x, yy), (slab.right - 1, yy), max(1, rect.w // 12))
    if hands:
        draw_grasping_hands(surf, rect, t, telegraph=True)


def draw_grasping_hands(surf, rect, t=0.0, telegraph=True):
    w = rect.w
    if telegraph:
        ov = pygame.Surface(rect.size, pygame.SRCALPHA)
        ov.fill((120, 255, 150, 60))
        surf.blit(ov, rect.topleft)
        pygame.draw.rect(surf, (140, 255, 170), rect, max(1, w // 16))
    for side in (-1, 1):
        bx = rect.centerx + side * int(w * 0.28)
        by = rect.bottom - 2
        col = (230, 222, 196)
        pygame.draw.line(surf, col, (bx, by), (rect.centerx + side * 2, rect.centery), max(1, w // 10))


def draw_deep_water(surf, rect, x, y, t=0.0):
    try:
        sprites.draw_water_detailed(surf, rect, t, x, y, shores={})
    except Exception:
        pygame.draw.rect(surf, (30, 60, 70), rect)
    ov = pygame.Surface(rect.size, pygame.SRCALPHA)
    ov.fill((20, 50, 30, 120))
    surf.blit(ov, rect.topleft)


def draw_shallow_water(surf, rect, x, y, t=0.0):
    ov = pygame.Surface(rect.size, pygame.SRCALPHA)
    ov.fill((50, 110, 110, 90))
    surf.blit(ov, rect.topleft)


def draw_sarcophagus(surf, cx, cy, tile, state="closed", t=0.0):
    s = tile / 40.0 * 1.3
    body = pygame.Rect(0, 0, int(30 * s), int(22 * s))
    body.center = (cx, cy - int(2 * s))
    pygame.draw.rect(surf, (104, 106, 112), body)
    pygame.draw.rect(surf, (70, 72, 78), body, max(1, int(2 * s)))
    lid = body.inflate(-int(4 * s), -int(6 * s))
    if state in ("", "closed"):
        pygame.draw.rect(surf, (138, 140, 146), lid)
        pygame.draw.circle(surf, (170, 172, 178), (lid.centerx, lid.y + int(5 * s)), max(2, int(3 * s)))
    else:
        pygame.draw.rect(surf, (18, 16, 16), lid)
        slid = lid.move(int(10 * s), -int(6 * s))
        pygame.draw.rect(surf, (138, 140, 146), slid)
        if state == "loot":
            _glow(surf, lid.centerx, lid.centery, int(16 * s), (255, 210, 110), 50)
        elif state == "ambush":
            _glow(surf, lid.centerx, lid.centery, int(18 * s), (120, 255, 150), 60)


def draw_bone_crown(surf, cx, cy, tile):
    s = max(0.4, tile / 40.0)
    base = pygame.Rect(0, 0, int(26 * s), int(6 * s))
    base.center = (cx, cy)
    pygame.draw.rect(surf, (220, 186, 80), base)
    for k in range(5):
        px = base.x + int(k * base.w / 4)
        pygame.draw.polygon(surf, (236, 200, 90), [(px - 3 * s, base.y), (px, base.y - 9 * s), (px + 3 * s, base.y)])
    pygame.draw.circle(surf, (120, 255, 150), (int(cx), int(base.centery)), max(2, int(2.5 * s)))


def _prop(client, rect, decor, style, x, y, t):
    surf = client.screen
    cx, cy = rect.centerx, rect.centery
    tile = rect.w
    if decor == "candle":
        try:
            if not prop_sprites.draw_prop(surf, "crypt_candelabra", cx, cy, tile):
                sprites.draw_brazier(surf, cx, cy, tile, t)
        except Exception:
            sprites.draw_brazier(surf, cx, cy, tile, t)
        _glow(surf, cx, cy - tile * 0.35, int(tile * 0.85), CANDLE, 48)
    elif decor.startswith("sarcophagus"):
        state = decor.split(":", 1)[1] if ":" in decor else "closed"
        draw_sarcophagus(surf, cx, cy, tile, state, t)
    elif decor == "shrine":
        s = tile / 40.0
        pygame.draw.rect(surf, (200, 196, 180), (cx - 1.5 * s, cy - 18 * s, 3 * s, 16 * s))
        pygame.draw.rect(surf, (200, 196, 180), (cx - 7 * s, cy - 14 * s, 14 * s, 3 * s))
        _glow(surf, cx, cy - 12 * s, int(28 * s), (255, 230, 160), 50)
    elif decor == "clutter":
        pygame.draw.circle(surf, (120, 100, 80), (cx, cy), max(3, tile // 6))
    elif decor == "chest":
        pygame.draw.rect(surf, (110, 72, 36), pygame.Rect(cx - tile // 4, cy - tile // 6, tile // 2, tile // 3))
    elif decor == "chest_open":
        pygame.draw.rect(surf, (70, 48, 28), pygame.Rect(cx - tile // 4, cy - tile // 6, tile // 2, tile // 3))
    elif decor in ("cache", "cache_open", "loot", "pedestal", "lore", "lever", "warning"):
        pygame.draw.circle(surf, (180, 160, 110), (cx, cy), max(2, tile // 7))


def queue_wall_faces(client, draw_list, cam_x, cam_y, vis_w, vis_h, t):
    import world_map as wm
    for sy in range(vis_h + 1):
        for sx in range(vis_w + 1):
            vx, vy = cam_x + sx, cam_y + sy
            wx, wy = client.view_to_world(vx, vy)
            if not (0 <= wy < len(client.tiles) and 0 <= wx < client.world_w):
                continue
            if client.tiles[wy][wx] != wm.WALL:
                continue
            decor = (client.dungeon.get("decor") or {}).get(f"{wx},{wy}", "")
            if decor in ("pit", "deep"):
                continue
            if wy + 1 >= len(client.tiles) or client.tiles[wy + 1][wx] == wm.WALL:
                if decor not in ("secret", "skull") and not (decor or "").startswith("seal"):
                    continue
            style = style_at(client.dungeon, wx, wy)

            def _face(sx=sx, sy=sy, style=style, decor=decor, wx=wx, wy=wy):
                tw = _tile(client)
                rect = pygame.Rect(sx * tw, sy * tw, tw, tw)
                draw_wall_face(client.screen, rect, wx, wy, style, decor, t)
                label = _hover_label(client, decor, wx, wy)
                if label and hasattr(client, "blit_nameplate"):
                    mx, my = pygame.mouse.get_pos()
                    if rect.collidepoint(mx, my):
                        client.blit_nameplate(label, rect.centerx, rect.y - 4, (230, 220, 190))

            draw_list.append(((sy + 1) * _tile(client), 2, _face))


def _hover_label(client, decor, wx, wy):
    d = client.dungeon or {}
    if decor == "secret" or decor == "skull":
        return (d.get("secret_hints") or {}).get(f"{wx},{wy}") or "Search the wall"
    if decor and decor.startswith("seal"):
        key = decor.split(":")[-1]
        return (d.get("door_hints") or {}).get(key) or "Locked"
    return ""


def handle_click(client, tx, ty):
    import void_v2_client
    return void_v2_client.handle_click(client, tx, ty)


def draw_overlay(client, t):
    import void_v2_client
    void_v2_client.draw_overlay(client, t)
