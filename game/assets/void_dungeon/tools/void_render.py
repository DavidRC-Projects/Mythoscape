"""Headless concept renders for the Void Sanctum v2 design.

Uses the game's own drawers (procedural_sprites_finished, prop_sprites,
anim_strip_sprites, rs_humanoid) plus a few prototype tile drawers that are
proposed for the new dungeon (void_tiles below). Run with the pygame venv:

  SDL_VIDEODRIVER=dummy MYTHO_REPO=<clone> python void_render.py <out_dir>
"""
import math
import os
import random
import sys

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
REPO = os.environ.get("MYTHO_REPO", "/workspace/void_clone")
A = os.path.join(REPO, "game", "assets")
for p in (os.path.join(A, "characters"), os.path.join(A, "mmorpg", "client"),
          os.path.join(A, "mmorpg", "server"), os.path.join(A, "mmorpg", "shared")):
    sys.path.insert(0, p)
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "reference_code"))

import pygame  # noqa: E402

pygame.init()
pygame.display.set_mode((1, 1))
import procedural_sprites_finished as sprites  # noqa: E402
import rs_style as rs  # noqa: E402
import prop_sprites  # noqa: E402
import anim_strip_sprites  # noqa: E402
import rs_humanoid  # noqa: E402
import void_map  # noqa: E402

OUT = sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, "..")
F = {s: pygame.font.SysFont("dejavusans", s, bold=True) for s in (10, 11, 12, 13, 14, 16, 18, 22, 28, 34)}
SEED = sprites._seeded

MAP = void_map.build()
G = [list(r) for r in MAP["grid"]]
W, H = MAP["width"], MAP["height"]
BLOCKED = set("#~ABCXSoiw")  # '#'-like for walkability (S is wall until searched)
FLOORISH = set(".=aPEHclg$rbhkv")

ZONE_OF = {}
for zid, name, band, (x0, y0, x1, y1), style in MAP["zones"]:
    for y in range(y0, y1 + 1):
        for x in range(x0, x1 + 1):
            ZONE_OF.setdefault((x, y), style)


ALL_HIDDEN = set()
for _sid, _sp in MAP["secrets"].items():
    for (_x0, _y0, _x1, _y1) in _sp["reveal"]:
        for _yy in range(_y0, _y1 + 1):
            for _xx in range(_x0, _x1 + 1):
                ALL_HIDDEN.add((_xx, _yy))


def style_at(x, y):
    if G[y][x] in "=a":
        return "bridge"
    return ZONE_OF.get((x, y), "entry")


# ---------------------------------------------------------------------------
# Prototype tile drawers (proposed void_tiles.py) — flat 2-tone facets, lit
# from the upper left, like the rest of the low-poly OSRS pass.
# ---------------------------------------------------------------------------
FLOOR_PAL = {
    "entry":    ((70, 60, 88), (62, 53, 80), (78, 68, 96), (56, 48, 72)),
    "gallery":  ((84, 78, 92), (74, 68, 82), (92, 86, 100), (66, 60, 74)),
    "barracks": ((82, 70, 64), (72, 62, 56), (90, 78, 70), (64, 54, 50)),
    "crystal":  ((52, 58, 92), (46, 50, 82), (60, 66, 104), (40, 44, 72)),
    "rift":     ((44, 32, 58), (38, 28, 50), (52, 38, 66), (32, 24, 44)),
    "arena":    ((30, 26, 38), (26, 22, 34), (36, 30, 46), (22, 18, 30)),
    "bridge":   ((40, 36, 52), (36, 32, 48), (44, 40, 58), (34, 30, 44)),
}
WALL_PAL = {
    "entry": (46, 40, 60), "gallery": (58, 54, 66), "barracks": (56, 46, 42),
    "crystal": (36, 40, 70), "rift": (30, 22, 42), "arena": (22, 18, 30), "bridge": (22, 18, 30),
}


def draw_void_floor(surf, rect, x, y, style, t=0.0):
    pal = FLOOR_PAL[style]
    base = pal[int(SEED(x, y, 1) * 4) % 4]
    hi, mid, sh, deep = rs.material(base)
    pygame.draw.rect(surf, mid, rect)
    pygame.draw.line(surf, hi, (rect.left + 1, rect.top + 1), (rect.right - 2, rect.top + 1))
    pygame.draw.line(surf, hi, (rect.left + 1, rect.top + 1), (rect.left + 1, rect.bottom - 2))
    pygame.draw.line(surf, sh, (rect.left + 1, rect.bottom - 1), (rect.right - 1, rect.bottom - 1))
    pygame.draw.rect(surf, deep, rect, 1)
    w = rect.w
    r = SEED(x, y, 5)
    if style == "gallery" and r < 0.35:          # shattered: crack line
        a = (rect.x + int(w * 0.2), rect.y + int(w * (0.2 + 0.5 * SEED(x, y, 6))))
        b = (rect.x + int(w * 0.55), rect.y + int(w * 0.5))
        c = (rect.x + int(w * 0.85), rect.y + int(w * (0.3 + 0.5 * SEED(x, y, 7))))
        pygame.draw.lines(surf, deep, False, [a, b, c], 1)
    elif style == "barracks":                     # plank-ish flagstones
        pygame.draw.line(surf, sh, (rect.x + 2, rect.centery), (rect.right - 3, rect.centery))
        if r < 0.12:
            pygame.draw.circle(surf, (110, 40, 40), (rect.x + int(w * 0.6), rect.y + int(w * 0.35)), max(1, w // 8))
    elif style == "crystal" and r < 0.22:         # crystal glint
        cx, cy = rect.x + int(w * (0.25 + 0.5 * SEED(x, y, 8))), rect.y + int(w * (0.25 + 0.5 * SEED(x, y, 9)))
        s = max(2, w // 7)
        pygame.draw.polygon(surf, (150, 170, 255), [(cx, cy - s), (cx + s // 2, cy), (cx, cy + s), (cx - s // 2, cy)])
    elif style == "rift" and r < 0.30:            # glowing violet fissure
        a = (rect.x + int(w * 0.1), rect.y + int(w * SEED(x, y, 10)))
        b = (rect.x + int(w * 0.5), rect.y + int(w * 0.5))
        c = (rect.x + int(w * 0.9), rect.y + int(w * SEED(x, y, 11)))
        pulse = 0.6 + 0.4 * math.sin(t * 2.0 + x)
        pygame.draw.lines(surf, (int(150 * pulse), 60, int(230 * pulse)), False, [a, b, c], max(1, w // 16))
    elif style == "arena":
        # gold eclipse ring inlay centred on the throne
        bx, by = MAP["boss_spawn"]
        d = math.hypot(x - bx, (y - by) * 1.4)
        if False:
            pygame.draw.rect(surf, (150, 118, 50), rect.inflate(-2, -2))
            pygame.draw.line(surf, (220, 180, 90), (rect.left + 2, rect.top + 2), (rect.right - 3, rect.top + 2))
    elif style == "entry" and r < 0.10:
        pygame.draw.circle(surf, sh, rect.center, max(1, w // 9))


def draw_hidden_floor(surf, rect, x, y, style, revealed):
    draw_void_floor(surf, rect, x, y, style)
    tint = pygame.Surface(rect.size, pygame.SRCALPHA)
    tint.fill((255, 210, 120, 34) if revealed else (0, 0, 0, 120))
    surf.blit(tint, rect.topleft)


def draw_wall_top(surf, rect, x, y, style, edges=None, cracked=False, t=0.0):
    """Wall seen from above: dressed stone blocks, lit rim where it meets floor."""
    base = WALL_PAL.get(style, (40, 34, 52))
    hi, mid, sh, deep = rs.material(base)
    edges = edges or {}
    near = any(edges.values())
    body = rs.shade(mid, -6) if near else rs.shade(mid, -26)
    pygame.draw.rect(surf, body, rect)
    if near:
        bh = max(3, rect.h // 3)
        for i in range(3):
            yy = rect.y + i * bh
            pygame.draw.line(surf, rs.shade(body, -18), (rect.x, yy), (rect.right - 1, yy))
            off = rect.w // 2 if (i + x) % 2 else 0
            bx = rect.x + off
            if rect.x < bx < rect.right:
                pygame.draw.line(surf, rs.shade(body, -18), (bx, yy), (bx, yy + bh - 1))
        rim = max(1, rect.w // 12)
        if edges.get("E"):
            pygame.draw.rect(surf, hi, (rect.right - rim - 1, rect.y, rim + 1, rect.h))
        if edges.get("W"):
            pygame.draw.rect(surf, sh, (rect.x, rect.y, rim + 1, rect.h))
        if edges.get("N"):
            pygame.draw.rect(surf, hi, (rect.x, rect.y, rect.w, rim + 1))
    elif SEED(x, y, 3) < 0.3:
        pygame.draw.circle(surf, sh, (rect.x + int(rect.w * SEED(x, y, 4)), rect.y + int(rect.h * SEED(x, y, 5))), 1)
    if cracked:
        c = (14, 10, 20)
        w = rect.w
        # the loose blocks are a touch lighter than their neighbours
        pygame.draw.rect(surf, rs.shade(body, 14), rect.inflate(-max(2, w // 8), -max(2, w // 8)))
        pygame.draw.rect(surf, rs.shade(body, -10), rect.inflate(-max(2, w // 8), -max(2, w // 8)), 1)
        pts = [(0.5, 0.05), (0.42, 0.3), (0.58, 0.52), (0.46, 0.75), (0.55, 0.97)]
        pygame.draw.lines(surf, c, False, [(rect.x + int(a * w), rect.y + int(b * w)) for a, b in pts], max(2, w // 10))
        pygame.draw.line(surf, c, (rect.x + int(0.58 * w), rect.y + int(0.52 * w)), (rect.x + int(0.8 * w), rect.y + int(0.42 * w)), 1)
        pygame.draw.line(surf, hi, (rect.x + int(0.52 * w), rect.y + int(0.06 * w)), (rect.x + int(0.44 * w), rect.y + int(0.3 * w)), 1)
        # chips on the floor side + a faint draught
        for k, (ox, oy) in enumerate(((1.12, 0.7), (1.25, 0.82), (1.08, 0.9))):
            sx = rect.x + int(ox * w) if edges.get("E") else rect.x - int((ox - 1.0) * w) - 2
            pygame.draw.circle(surf, rs.shade(mid, 20), (sx, rect.y + int(oy * w)), max(1, w // 18))
        for k in range(3):
            ph = (t * 0.7 + k / 3.0) % 1.0
            mx = rect.x + (w + int(ph * w * 0.6) if edges.get("E") else -int(ph * w * 0.6))
            my = rect.y + int(w * (0.3 + 0.15 * k))
            m = pygame.Surface((4, 4), pygame.SRCALPHA)
            pygame.draw.circle(m, (220, 220, 255, int(150 * (1 - ph))), (2, 2), 1)
            surf.blit(m, (mx, my))


def draw_wall_face(surf, rect, x, y, style, cracked=False, t=0.0, hint_pulse=True):
    """Front face of a wall whose south neighbour is floor: brick courses + rune veins."""
    base = WALL_PAL.get(style, (40, 34, 52))
    hi, mid, sh, deep = rs.material(base)
    face = pygame.Rect(rect.x, rect.y + rect.h // 3, rect.w, rect.h - rect.h // 3)
    cap = pygame.Rect(rect.x, rect.y, rect.w, rect.h // 3)
    pygame.draw.rect(surf, rs.shade(mid, 10), cap)
    pygame.draw.line(surf, hi, cap.topleft, (cap.right - 1, cap.top))
    pygame.draw.rect(surf, mid, face)
    rows = 3
    bh = max(2, face.h // rows)
    for i in range(rows):
        yy = face.y + i * bh
        pygame.draw.line(surf, sh, (face.x, yy), (face.right - 1, yy))
        off = (face.w // 2) if i % 2 else 0
        for bx in range(face.x - off, face.right, max(4, face.w // 2)):
            if face.x < bx < face.right:
                pygame.draw.line(surf, sh, (bx, yy), (bx, yy + bh - 1))
    pygame.draw.line(surf, deep, (face.x, face.bottom - 1), (face.right - 1, face.bottom - 1))
    if style == "crystal" and SEED(x, y, 12) < 0.35:
        cx = face.x + int(face.w * 0.5)
        pygame.draw.polygon(surf, (120, 140, 240), [(cx, face.y - face.h // 3), (cx + face.w // 8, face.y + face.h // 2), (cx - face.w // 8, face.y + face.h // 2)])
    if style in ("rift", "arena") and SEED(x, y, 13) < 0.3:
        pulse = 0.6 + 0.4 * math.sin(t * 2 + x * 0.7)
        pygame.draw.line(surf, (int(170 * pulse), 70, int(240 * pulse)), (face.x + face.w // 3, face.y + 2), (face.x + face.w // 2, face.bottom - 3), max(1, face.w // 14))
    if style == "entry" and SEED(x, y, 14) < 0.2:   # violet torch sconce
        sx = face.centerx
        pygame.draw.rect(surf, (40, 30, 30), (sx - 1, face.y + 2, 3, max(3, face.h // 3)))
        glow = pygame.Surface((face.w, face.w), pygame.SRCALPHA)
        pygame.draw.circle(glow, (190, 120, 255, 38), (face.w // 2, face.w // 2), face.w // 2)
        surf.blit(glow, (sx - face.w // 2, face.y - face.w // 2 + 2), )
        pygame.draw.circle(surf, (230, 180, 255), (sx, face.y + 1), max(1, face.w // 12))
    if cracked:
        # Subtle hint: a jagged crack, a few fallen chips below, faint draught motes.
        c = (18, 12, 24)
        pts = [(face.x + face.w * 0.30, face.y + 1), (face.x + face.w * 0.45, face.y + face.h * 0.35),
               (face.x + face.w * 0.38, face.y + face.h * 0.6), (face.x + face.w * 0.55, face.bottom - 2)]
        pygame.draw.lines(surf, c, False, [(int(a), int(b)) for a, b in pts], max(1, face.w // 16))
        pygame.draw.line(surf, c, (int(face.x + face.w * 0.45), int(face.y + face.h * 0.35)),
                         (int(face.x + face.w * 0.68), int(face.y + face.h * 0.28)), 1)
        pygame.draw.line(surf, hi, (int(face.x + face.w * 0.32), face.y + 1), (int(face.x + face.w * 0.47), int(face.y + face.h * 0.35)), 1)
        if hint_pulse:
            for k in range(3):
                ph = (t * 0.7 + k / 3.0) % 1.0
                mx = face.x + face.w * (0.35 + 0.1 * k)
                my = face.bottom - ph * face.h * 0.9
                s = pygame.Surface((4, 4), pygame.SRCALPHA)
                pygame.draw.circle(s, (220, 220, 255, int(140 * (1 - ph))), (2, 2), 1)
                surf.blit(s, (int(mx), int(my)))


def draw_abyss(surf, rect, x, y, t=0.0, edge_n=False):
    pygame.draw.rect(surf, (8, 5, 14), rect)
    rnd = random.Random(x * 131 + y * 17)
    for _ in range(2):
        if rnd.random() < 0.5:
            px, py = rect.x + rnd.randrange(max(1, rect.w)), rect.y + rnd.randrange(max(1, rect.h))
            v = rnd.randint(90, 200)
            surf.set_at((px, py), (v, int(v * 0.7), 255))
    sw = 0.5 + 0.5 * math.sin(x * 0.45 + y * 0.3 + t)
    ov = pygame.Surface(rect.size, pygame.SRCALPHA)
    ov.fill((70, 20, 110, int(40 * sw)))
    surf.blit(ov, rect.topleft)
    if edge_n:   # cliff lip where floor drops into the abyss
        lip = pygame.Rect(rect.x, rect.y, rect.w, max(3, rect.h // 3))
        pygame.draw.rect(surf, (34, 26, 44), lip)
        pygame.draw.line(surf, (60, 48, 76), lip.topleft, (lip.right - 1, lip.top))
        for i in range(0, rect.w, max(3, rect.w // 4)):
            pygame.draw.polygon(surf, (26, 20, 34), [(rect.x + i, lip.bottom), (rect.x + i + rect.w // 8, lip.bottom + rect.h // 4), (rect.x + i + rect.w // 4, lip.bottom)])


def draw_bridge(surf, rect, x, y, anchor=False, t=0.0):
    draw_abyss(surf, rect, x, y, t)
    slab = rect.inflate(-max(2, rect.w // 8), 0)
    hi, mid, sh, deep = rs.material((58, 52, 70))
    pygame.draw.rect(surf, mid, slab)
    pygame.draw.line(surf, hi, slab.topleft, (slab.right - 1, slab.top))
    pygame.draw.line(surf, hi, slab.topleft, (slab.left, slab.bottom - 1))
    pygame.draw.line(surf, deep, (slab.right - 1, slab.top), (slab.right - 1, slab.bottom - 1))
    pygame.draw.line(surf, sh, (slab.left, slab.bottom - 1), (slab.right - 1, slab.bottom - 1))
    if anchor:
        p = 0.65 + 0.35 * math.sin(t * 3)
        c = (int(250 * p), int(200 * p), 90)
        r = max(2, rect.w // 4)
        pygame.draw.circle(surf, c, slab.center, r, max(1, rect.w // 14))
        pygame.draw.line(surf, c, (slab.centerx, slab.centery - r), (slab.centerx, slab.centery + r), 1)
        pygame.draw.line(surf, c, (slab.centerx - r, slab.centery), (slab.centerx + r, slab.centery), 1)


def draw_pylon(surf, cx, cy, tile, t=0.0, lit=True):
    s = tile / 40.0
    base = [(cx - 9 * s, cy + 6 * s), (cx + 9 * s, cy + 6 * s), (cx + 6 * s, cy - 2 * s), (cx - 6 * s, cy - 2 * s)]
    pygame.draw.polygon(surf, (40, 34, 50), base)
    shaft = [(cx - 5 * s, cy - 2 * s), (cx + 5 * s, cy - 2 * s), (cx + 3 * s, cy - 34 * s), (cx - 3 * s, cy - 34 * s)]
    pygame.draw.polygon(surf, (58, 50, 72), shaft)
    pygame.draw.polygon(surf, (36, 30, 46), [(cx, cy - 2 * s), (cx + 5 * s, cy - 2 * s), (cx + 3 * s, cy - 34 * s), (cx, cy - 34 * s)])
    if lit:
        p = 0.7 + 0.3 * math.sin(t * 2.4)
        glow = pygame.Surface((int(60 * s), int(60 * s)), pygame.SRCALPHA)
        pygame.draw.circle(glow, (255, 210, 110, int(70 * p)), (int(30 * s), int(30 * s)), int(28 * s))
        surf.blit(glow, (cx - 30 * s, cy - 66 * s), )
        pygame.draw.circle(surf, (255, 225, 140), (int(cx), int(cy - 37 * s)), max(2, int(5 * s)))
        pygame.draw.circle(surf, (40, 20, 60), (int(cx + 2 * s), int(cy - 38 * s)), max(1, int(3.5 * s)))


def draw_lever(surf, cx, cy, tile, pulled=False):
    s = tile / 40.0
    pygame.draw.rect(surf, (60, 56, 64), (cx - 8 * s, cy - 2 * s, 16 * s, 8 * s))
    pygame.draw.rect(surf, (90, 86, 96), (cx - 8 * s, cy - 2 * s, 16 * s, 2 * s))
    ang = -0.6 if not pulled else 0.6
    ex, ey = cx + math.sin(ang) * 18 * s, cy - math.cos(ang) * 18 * s
    pygame.draw.line(surf, (70, 50, 30), (cx, cy), (ex, ey), max(2, int(3 * s)))
    pygame.draw.circle(surf, (170, 60, 60), (int(ex), int(ey)), max(2, int(4 * s)))


def draw_seal_door(surf, cx, cy, tile, key_col, open_=False, t=0.0):
    """Locked void seal: iron-bound door (game drawer) + a glowing key-coloured sigil."""
    sprites.draw_door(surf, cx, cy, tile, open_=open_, t=t)
    if open_:
        return
    s = tile / 40.0
    p = 0.7 + 0.3 * math.sin(t * 2.2)
    glow = pygame.Surface((int(40 * s), int(40 * s)), pygame.SRCALPHA)
    pygame.draw.circle(glow, (*key_col, int(55 * p)), (int(20 * s), int(20 * s)), int(18 * s))
    surf.blit(glow, (cx - 20 * s, cy - 24 * s), )
    r = int(8 * s)
    pygame.draw.circle(surf, (30, 20, 40), (int(cx), int(cy - 4 * s)), r + 2)
    pygame.draw.circle(surf, key_col, (int(cx), int(cy - 4 * s)), r, max(2, int(2 * s)))
    pygame.draw.circle(surf, key_col, (int(cx), int(cy - 6 * s)), max(1, int(2.5 * s)))
    pygame.draw.polygon(surf, key_col, [(cx - 2 * s, cy - 5 * s), (cx + 2 * s, cy - 5 * s), (cx + 1 * s, cy + 1 * s), (cx - 1 * s, cy + 1 * s)])
    # chains across the door
    for sgn in (-1, 1):
        for k in range(4):
            px = cx + sgn * (10 + k * 3) * s
            pygame.draw.circle(surf, (120, 118, 126), (int(px), int(cy - 4 * s + k * s)), max(1, int(1.6 * s)), 1)


KEY_COL = {"A": (190, 120, 255), "B": (140, 150, 170), "C": (255, 120, 90)}


def draw_key_icon(surf, cx, cy, size, col):
    s = size / 32.0
    pygame.draw.circle(surf, (20, 14, 24), (int(cx - 7 * s), int(cy)), int(8 * s))
    pygame.draw.circle(surf, col, (int(cx - 7 * s), int(cy)), int(7 * s), max(2, int(3 * s)))
    pygame.draw.rect(surf, (20, 14, 24), (cx - 1 * s, cy - 2.5 * s, 16 * s, 5 * s))
    pygame.draw.rect(surf, col, (cx - 1 * s, cy - 1.5 * s, 15 * s, 3 * s))
    for bx in (9, 13):
        pygame.draw.rect(surf, col, (cx + bx * s, cy, 2 * s, 5 * s))
    pygame.draw.circle(surf, (255, 255, 255), (int(cx - 9 * s), int(cy - 3 * s)), max(1, int(1.5 * s)))


def draw_scroll(surf, cx, cy, tile):
    s = tile / 40.0
    pygame.draw.rect(surf, (214, 196, 150), (cx - 8 * s, cy - 5 * s, 16 * s, 9 * s))
    pygame.draw.rect(surf, (150, 120, 80), (cx - 9 * s, cy - 6 * s, 3 * s, 11 * s))
    pygame.draw.rect(surf, (150, 120, 80), (cx + 6 * s, cy - 6 * s, 3 * s, 11 * s))
    for k in range(3):
        pygame.draw.line(surf, (110, 90, 70), (cx - 5 * s, cy - 3 * s + k * 2.5 * s), (cx + 4 * s, cy - 3 * s + k * 2.5 * s))
    pygame.draw.circle(surf, (160, 60, 200), (int(cx + 2 * s), int(cy + 3 * s)), max(1, int(2 * s)))


def draw_cache(surf, cx, cy, tile):
    s = tile / 40.0
    pygame.draw.rect(surf, (104, 76, 46), (cx - 10 * s, cy - 8 * s, 20 * s, 14 * s))
    pygame.draw.rect(surf, (140, 106, 66), (cx - 10 * s, cy - 8 * s, 20 * s, 3 * s))
    pygame.draw.line(surf, (70, 50, 30), (cx - 10 * s, cy - 1 * s), (cx + 10 * s, cy - 1 * s))
    pygame.draw.circle(surf, (200, 40, 40), (int(cx - 3 * s), int(cy - 11 * s)), max(2, int(3 * s)))
    pygame.draw.circle(surf, (90, 200, 90), (int(cx + 3 * s), int(cy - 11 * s)), max(2, int(3 * s)))


def draw_loot_pile(surf, cx, cy, tile):
    s = tile / 40.0
    for k, (dx, dy) in enumerate(((-4, 2), (3, 3), (0, -1), (5, -2))):
        pygame.draw.circle(surf, (230, 190, 70), (int(cx + dx * s), int(cy + dy * s)), max(1, int(3 * s)))
        pygame.draw.circle(surf, (150, 110, 40), (int(cx + dx * s), int(cy + dy * s)), max(1, int(3 * s)), 1)
    pygame.draw.circle(surf, (120, 200, 255), (int(cx - 1 * s), int(cy + 4 * s)), max(1, int(2 * s)))


def draw_rift_pool(surf, cx, cy, tile, t=0.0):
    s = tile / 40.0
    r = pygame.Rect(0, 0, 30 * s, 16 * s)
    r.center = (cx, cy)
    pygame.draw.ellipse(surf, (30, 10, 50), r)
    p = 0.6 + 0.4 * math.sin(t * 3)
    pygame.draw.ellipse(surf, (int(150 * p), 60, int(240 * p)), r.inflate(-6 * s, -5 * s), max(1, int(2 * s)))


def draw_warning_stone(surf, cx, cy, tile):
    s = tile / 40.0
    pygame.draw.polygon(surf, (70, 64, 80), [(cx - 9 * s, cy + 5 * s), (cx + 9 * s, cy + 5 * s), (cx + 7 * s, cy - 18 * s), (cx - 6 * s, cy - 20 * s)])
    pygame.draw.polygon(surf, (50, 44, 60), [(cx, cy + 5 * s), (cx + 9 * s, cy + 5 * s), (cx + 7 * s, cy - 18 * s), (cx, cy - 19 * s)])
    pygame.draw.circle(surf, (240, 200, 90), (int(cx), int(cy - 8 * s)), max(2, int(4.5 * s)), max(1, int(1.5 * s)))
    pygame.draw.circle(surf, (40, 20, 60), (int(cx + 1.5 * s), int(cy - 8.5 * s)), max(1, int(3 * s)))


def draw_shrine(surf, cx, cy, tile, t=0.0):
    prop_sprites.draw_prop(surf, "void_altar", cx, cy, tile) or sprites.draw_brazier(surf, cx, cy, tile, t)
    s = tile / 40.0
    p = 0.7 + 0.3 * math.sin(t * 2)
    glow = pygame.Surface((int(70 * s), int(70 * s)), pygame.SRCALPHA)
    pygame.draw.circle(glow, (120, 255, 170, int(60 * p)), (int(35 * s), int(35 * s)), int(33 * s))
    surf.blit(glow, (cx - 35 * s, cy - 50 * s), )


# ---------------------------------------------------------------------------
# Monsters
# ---------------------------------------------------------------------------
VISUAL = {"gallery_warden": "crypt_ghoul", "void_crawler": "void_imp", "knight_captain_vorn": "shadow_knight",
          "rift_wraith": "shade", "nyxarath": "void_horror"}
LEVEL = {"shade": 55, "crypt_ghoul": 62, "gallery_warden": 68, "void_imp": 70, "obsidian_colossus": 78,
         "void_crawler": 82, "shadow_knight": 88, "rift_wraith": 91, "knight_captain_vorn": 92,
         "void_horror": 95, "nyxarath": 110}
NAMES = {"shade": "Shade", "crypt_ghoul": "Crypt Ghoul", "gallery_warden": "Gallery Warden", "void_imp": "Void Imp",
         "obsidian_colossus": "Obsidian Colossus", "void_crawler": "Void Crawler", "shadow_knight": "Shadow Knight",
         "rift_wraith": "Rift Wraith", "knight_captain_vorn": "Knight-Captain Vorn", "void_horror": "Void Horror",
         "nyxarath": "Nyxarath, the Hollow Eclipse"}
TINT = {"void_crawler": (80, 120, 255), "rift_wraith": (170, 60, 255), "gallery_warden": (255, 200, 90),
        "knight_captain_vorn": (255, 80, 60)}


def threat_col(lvl, player=90):
    d = lvl - player
    if d <= -10:
        return (90, 220, 90)
    if d <= 0:
        return (240, 200, 60)
    if d <= 8:
        return (255, 140, 50)
    return (255, 70, 60)


def draw_mon(surf, mtype, cx, cy, tile, t, facing=1, scale=1.0):
    vis = VISUAL.get(mtype, mtype)
    if scale != 1.0:
        big = pygame.Surface((int(tile * 4 * scale), int(tile * 4 * scale)), pygame.SRCALPHA)
        bcx, bcy = big.get_width() // 2, int(big.get_height() * 0.8)
        _draw_mon_raw(big, vis, bcx, bcy, int(tile * scale), t, facing)
        surf.blit(big, (cx - bcx, cy - bcy))
    else:
        _draw_mon_raw(surf, vis, cx, cy, tile, t, facing)
    tint = TINT.get(mtype)
    if tint:
        glow = pygame.Surface((int(tile * 1.2), int(tile * 0.45)), pygame.SRCALPHA)
        pygame.draw.ellipse(glow, (*tint, 28), glow.get_rect())
        pygame.draw.ellipse(glow, (*tint, 60), glow.get_rect(), max(1, tile // 20))
        surf.blit(glow, (cx - glow.get_width() // 2, cy - glow.get_height() // 2), )


def _draw_mon_raw(surf, vis, cx, cy, tile, t, facing):
    ok = False
    try:
        ok = anim_strip_sprites.draw_anim_strip_monster(surf, vis, cx, cy, tile, t, facing=facing)
    except Exception:
        ok = False
    if not ok:
        sprites.draw_monster(surf, vis, cx, cy, tile, t, facing=facing)


def badge(surf, text, cx, top, col, font=None):
    font = font or F[11]
    img = font.render(text, True, col)
    r = img.get_rect(midtop=(int(cx), int(top)))
    bg = r.inflate(8, 4)
    pygame.draw.rect(surf, (16, 12, 22), bg, border_radius=4)
    pygame.draw.rect(surf, col, bg, 1, border_radius=4)
    surf.blit(img, r)
    return bg


def nameplate(surf, text, cx, top, col=(255, 255, 255), font=None):
    font = font or F[12]
    img = font.render(text, True, col)
    sh = font.render(text, True, (0, 0, 0))
    r = img.get_rect(midtop=(int(cx), int(top)))
    surf.blit(sh, r.move(1, 1))
    surf.blit(img, r)


# ---------------------------------------------------------------------------
# Scene renderer
# ---------------------------------------------------------------------------
def walk_state(opened=()):
    """Return a char grid where secrets/doors in `opened` are floor."""
    g = [row[:] for row in G]
    return g


def render_region(x0, y0, x1, y1, tile, t=0.3, opened_secrets=(), opened_doors=(), show_mons=True,
                  mon_labels=True, fog=None, markers=False, player=None, lever_pulled=False):
    wpx, hpx = (x1 - x0 + 1) * tile, (y1 - y0 + 1) * tile
    surf = pygame.Surface((wpx, hpx))
    surf.fill((10, 8, 14))
    revealed = set()
    for sid in opened_secrets:
        for (rx0, ry0, rx1, ry1) in MAP["secrets"][sid]["reveal"]:
            for yy in range(ry0, ry1 + 1):
                for xx in range(rx0, rx1 + 1):
                    revealed.add((xx, yy))
    secret_walls_open = {tuple(MAP["secrets"][s]["wall"]) for s in opened_secrets}

    def ch_at(x, y):
        if not (0 <= x < W and 0 <= y < H):
            return "#"
        c = G[y][x]
        if (x, y) in secret_walls_open:
            return "."
        if (c == "h" or (x, y) in ALL_HIDDEN) and (x, y) not in revealed:
            return "#"
        if c in "hk" and (x, y) in revealed:
            return c
        return c

    def walk(x, y):
        c = ch_at(x, y)
        if c in "ABC" and c in opened_doors:
            return True
        if c == "X" and lever_pulled:
            return True
        return c not in BLOCKED

    objs = []
    for y in range(y0, y1 + 1):
        for x in range(x0, x1 + 1):
            rect = pygame.Rect((x - x0) * tile, (y - y0) * tile, tile, tile)
            c = ch_at(x, y)
            st = style_at(x, y)
            cx, cy = rect.centerx, rect.centery
            if c == "~":
                draw_abyss(surf, rect, x, y, t, edge_n=walk(x, y - 1) and ch_at(x, y - 1) not in "=a")
            elif c in "=a":
                draw_bridge(surf, rect, x, y, anchor=(c == "a"), t=t)
            elif c in "#S" or (c in "ABCX" and False):
                south_open = walk(x, y + 1) or ch_at(x, y + 1) in "ABCX~"
                if south_open and ch_at(x, y + 1) != "~":
                    draw_wall_face(surf, rect, x, y, st, cracked=(c == "S"), t=t)
                else:
                    edges = {"E": walk(x + 1, y), "W": walk(x - 1, y), "N": walk(x, y - 1)}
                    draw_wall_top(surf, rect, x, y, st, edges, cracked=(c == "S"), t=t)
            else:
                if (x, y) in revealed or (x, y) in secret_walls_open:
                    draw_hidden_floor(surf, rect, x, y, st, True)
                else:
                    draw_void_floor(surf, rect, x, y, st, t)
                if c in "ABC":
                    objs.append((cy, lambda cx=cx, cy=cy, c=c: draw_seal_door(surf, cx, cy + tile // 4, tile, KEY_COL[c], open_=c in opened_doors, t=t)))
                elif c == "X":
                    objs.append((cy, lambda cx=cx, cy=cy: sprites.draw_door(surf, cx, cy + tile // 4, tile, open_=lever_pulled, gate=False)))
                elif c == "E":
                    objs.append((cy, lambda cx=cx, cy=cy: sprites.draw_cave_entrance(surf, cx, cy, tile, t)))
                elif c == "c":
                    objs.append((cy, lambda cx=cx, cy=cy: sprites.draw_chest(surf, cx, cy + tile // 6, tile, t)))
                elif c == "k":
                    objs.append((cy, lambda cx=cx, cy=cy: (pygame.draw.rect(surf, (70, 64, 80), (cx - tile * 0.25, cy - tile * 0.1, tile * 0.5, tile * 0.45)),
                                                         draw_key_icon(surf, cx, cy - tile * 0.25, tile * 0.7, KEY_COL["B"]))))
                elif c == "l":
                    objs.append((cy, lambda cx=cx, cy=cy: draw_scroll(surf, cx, cy, tile)))
                elif c == "g":
                    objs.append((cy, lambda cx=cx, cy=cy: draw_cache(surf, cx, cy + tile // 6, tile)))
                elif c == "$":
                    objs.append((cy, lambda cx=cx, cy=cy: draw_loot_pile(surf, cx, cy, tile)))
                elif c == "H":
                    objs.append((cy, lambda cx=cx, cy=cy: draw_shrine(surf, cx, cy + tile // 4, tile, t)))
                elif c == "v":
                    objs.append((cy, lambda cx=cx, cy=cy: draw_lever(surf, cx, cy + tile // 4, tile, lever_pulled)))
                elif c == "o":
                    objs.append((cy, lambda cx=cx, cy=cy: draw_pylon(surf, cx, cy + tile // 4, tile, t)))
                elif c == "r":
                    draw_rift_pool(surf, cx, cy, tile, t)
                elif c == "w":
                    objs.append((cy, lambda cx=cx, cy=cy: draw_warning_stone(surf, cx, cy + tile // 4, tile)))
                elif c == "i":
                    if st == "crystal" or st == "rift":
                        objs.append((cy, lambda cx=cx, cy=cy: prop_sprites.draw_prop(surf, "void_crystals", cx, cy, tile)))
                    elif st == "barracks":
                        objs.append((cy, lambda cx=cx, cy=cy: prop_sprites.draw_prop(surf, "weapon_rack", cx, cy, tile)))
                    elif st == "gallery":
                        objs.append((cy, lambda cx=cx, cy=cy: prop_sprites.draw_prop(surf, "crypt_sarcophagus", cx, cy, tile)))
                    else:
                        objs.append((cy, lambda cx=cx, cy=cy: prop_sprites.draw_prop(surf, "crypt_candelabra", cx, cy, tile)))
            # wall AO on floors
            if c not in "#S~=a" and tile >= 16:
                nb = {"N": ch_at(x, y - 1) in "#S", "S": False, "W": ch_at(x - 1, y) in "#S", "E": ch_at(x + 1, y) in "#S"}
                sprites.draw_tile_wall_ao(surf, rect, nb, alpha=90)
    bx, by = MAP["boss_spawn"]
    if x0 <= bx <= x1 and y0 <= by + 6 and by - 6 <= y1:
        ccx, ccy = (bx - x0) * tile + tile // 2, (by - y0) * tile + tile // 2
        for rx, lw in ((6.2, 0.22), (11.0, 0.18)):
            r = pygame.Rect(0, 0, int(rx * 2 * tile), int(rx * 2 * tile / 1.4))
            r.center = (ccx, ccy)
            pygame.draw.ellipse(surf, (120, 92, 40), r.inflate(4, 4), max(2, int(tile * lw) + 2))
            pygame.draw.ellipse(surf, (214, 172, 84), r, max(1, int(tile * lw)))
        # crescent-and-sun eclipse sigil under the throne
        rr = int(tile * 2.2)
        pygame.draw.circle(surf, (214, 172, 84), (ccx, ccy), rr, max(1, tile // 10))
        for k in range(12):
            a = k * math.pi / 6
            pygame.draw.line(surf, (214, 172, 84), (ccx + math.cos(a) * rr, ccy + math.sin(a) * rr * 0.72),
                             (ccx + math.cos(a) * rr * 1.35, ccy + math.sin(a) * rr * 0.97), max(1, tile // 12))
        pygame.draw.circle(surf, (14, 8, 22), (ccx + rr // 3, ccy - rr // 6), int(rr * 0.8))
    if show_mons:
        for mtype, mx, my in MAP["spawns"]:
            if not (x0 <= mx <= x1 and y0 <= my <= y1):
                continue
            cx, cy = (mx - x0) * tile + tile // 2, (my - y0) * tile + int(tile * 0.8)
            lvl = LEVEL[mtype]
            if markers:
                col = threat_col(lvl)
                boss = mtype in void_map.NO_RESPAWN
                r = max(3, tile // 3) + (2 if boss else 0)
                objs.append((cy + 1000, lambda cx=cx, cy=cy, col=col, r=r, boss=boss: (
                    pygame.draw.circle(surf, (0, 0, 0), (cx, cy - tile // 3), r + 1),
                    pygame.draw.circle(surf, col, (cx, cy - tile // 3), r),
                    boss and pygame.draw.circle(surf, (255, 230, 120), (cx, cy - tile // 3), r + 2, 1))))
                continue
            scale = 1.9 if mtype == "nyxarath" else (1.2 if mtype in ("gallery_warden", "knight_captain_vorn") else 1.0)

            def _dm(mtype=mtype, cx=cx, cy=cy, lvl=lvl, scale=scale):
                if mtype == "nyxarath":
                    halo = pygame.Surface((tile * 4, tile * 4), pygame.SRCALPHA)
                    pygame.draw.circle(halo, (255, 200, 90, 120), (tile * 2, tile * 2), int(tile * 1.5), max(2, tile // 10))
                    pygame.draw.circle(halo, (10, 4, 16, 230), (int(tile * 2.35), int(tile * 1.9)), int(tile * 1.35))
                    surf.blit(halo, (cx - tile * 2, cy - tile * 3.6))
                draw_mon(surf, mtype, cx, cy, tile, t, facing=-1 if mx > 32 else 1, scale=scale)
                if mon_labels:
                    top = cy - int(tile * (1.55 * scale + 0.25))
                    badge(surf, str(lvl), cx, top, threat_col(lvl), F[11] if tile < 36 else F[13])
            objs.append((cy, _dm))
    if player:
        px, py = player
        pcx, pcy = (px - x0) * tile + tile // 2, (py - y0) * tile + int(tile * 0.8)
        objs.append((pcy, lambda: rs_humanoid.draw_skeletal_humanoid(surf, pcx, pcy, tile, body_color=(60, 110, 70),
                                                                   equipment={"body": "mithril_body", "legs": "mithril_legs", "helmet": "mithril_helmet", "weapon": "mithril_sword", "shield": "mithril_shield"},
                                                                   weapon="mithril_sword", shield=True, t=t, facing=1)))
    for _, fn in sorted(objs, key=lambda o: o[0]):
        try:
            fn()
        except Exception as e:  # keep renders going; report once
            print("draw error", e)
    if fog is not None:
        fog_s = pygame.Surface((wpx, hpx), pygame.SRCALPHA)
        fog_s.fill((4, 2, 8, 235))
        fx, fy, fr = fog
        for rr, a in ((fr + 2, 150), (fr + 1, 80), (fr, 0)):
            pygame.draw.circle(fog_s, (4, 2, 8, a), ((fx - x0) * tile + tile // 2, (fy - y0) * tile + tile // 2), rr * tile)
        surf.blit(fog_s, (0, 0))
    return surf


def bfs(start, opened_doors=(), opened_secrets=(), lever=False):
    revealed = set()
    for sid in opened_secrets:
        revealed.add(tuple(MAP["secrets"][sid]["wall"]))
        for (rx0, ry0, rx1, ry1) in MAP["secrets"][sid]["reveal"]:
            for yy in range(ry0, ry1 + 1):
                for xx in range(rx0, rx1 + 1):
                    revealed.add((xx, yy))
    seen = {start}
    q = [start]
    while q:
        x, y = q.pop()
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            nx, ny = x + dx, y + dy
            if not (0 <= nx < W and 0 <= ny < H) or (nx, ny) in seen:
                continue
            c = G[ny][nx]
            ok = c in FLOORISH and c not in "hk" or ((nx, ny) in revealed) or (c in opened_doors) or (c == "X" and lever)
            if c in "hk" and (nx, ny) not in revealed:
                ok = False
            if ok:
                seen.add((nx, ny))
                q.append((nx, ny))
    return seen


def validate():
    msgs = []
    for mtype, x, y in MAP["spawns"]:
        if G[y][x] not in ".b":
            msgs.append(f"spawn {mtype} at {x},{y} on '{G[y][x]}'")
    start = tuple(MAP["spawn"])
    r0 = bfs(start)
    rA = bfs(start, "A")
    rAB = bfs(start, "AB")
    rall = bfs(start, "ABC", ("reliquary", "quartermaster", "starwell"))
    checks = {
        "no keys: boss unreachable": tuple(MAP["boss_spawn"]) not in r0,
        "no keys: barracks unreachable": (30, 42) not in r0,
        "door A only: crystal unreachable": (30, 53) not in rA,
        "A+B: rift unreachable": (32, 66) not in rAB,
        "all open: boss reachable": tuple(MAP["boss_spawn"]) in rall,
        "all open: every chest reachable": all(tuple(map(int, k.split(","))) in rall for k in MAP["chests"]),
        "Obsidian key pedestal needs secret": (5, 42) not in bfs(start, "AB"),
        "shortcut: rift reachable from entry with lever only": (32, 66) in bfs(start, "", (), True),
        "gallery warden reachable without keys": (51, 28) in r0,
        "Vorn reachable with A+B": (8, 56) in rAB,
    }
    return msgs, checks


if __name__ == "__main__":
    os.makedirs(OUT, exist_ok=True)
    msgs, checks = validate()
    print("spawn issues:", msgs)
    for k, v in checks.items():
        print(("PASS " if v else "FAIL ") + k)
