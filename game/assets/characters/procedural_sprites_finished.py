"""
Procedural "pixel-art-ish" sprite rendering for the MMORPG client.

Nothing here is loaded from an image file -- every sprite (characters,
monsters, trees, rocks, water, buildings, item icons) is drawn with plain
pygame primitives. That keeps the client dependency-free and avoids any
question of using someone else's art, while looking far better than flat
colored circles.

All draw_* functions take a pygame Surface and a center point / rect and
are deterministic given (position, time) so animation is smooth but
consistent across frames.
"""
import math
import pygame

TAU = math.pi * 2

# ---------------------------------------------------------------------------
# Art scale
# ---------------------------------------------------------------------------
# The original renderer was designed around small 32px-ish sprites.  For a
# more RuneScape-like presentation, keep the world/tile grid intact but make
# actors, resources, monsters and buildings occupy substantially more pixels.
# 1.60 is the default; 1.75-1.90 gives an even closer, chunkier presentation.
ART_SCALE = 2.0


def _shade(color, delta):
    return tuple(max(0, min(255, c + delta)) for c in color)


def _seeded(x, y, salt=0):
    """Cheap deterministic pseudo-random in [0,1) from a tile position."""
    n = (x * 92821 + y * 68917 + salt * 2311) & 0xFFFFFFFF
    n = (n ^ (n >> 13)) * 1274126177 & 0xFFFFFFFF
    return (n % 10000) / 10000.0


# ---------------------------------------------------------------------------
# Terrain
# ---------------------------------------------------------------------------
def draw_grass(surf, rect, seed_x, seed_y):
    r1 = _seeded(seed_x, seed_y, 1)
    base = (48, 98, 52) if r1 < 0.33 else ((56, 110, 58) if r1 < 0.66 else (42, 90, 48))
    pygame.draw.rect(surf, base, rect)
    # soft highlight patch
    hi = (62, 122, 64)
    inset = rect.inflate(-rect.w * 0.25, -rect.h * 0.3)
    inset.x += int((_seeded(seed_x, seed_y, 4) - 0.5) * 4)
    pygame.draw.rect(surf, hi, inset)
    for i in range(4):
        rx = _seeded(seed_x, seed_y, 10 + i)
        ry = _seeded(seed_x, seed_y, 20 + i)
        bx = rect.x + rx * rect.w
        by = rect.y + ry * rect.h
        col = (78, 140, 72) if i % 2 == 0 else (36, 78, 40)
        pygame.draw.line(surf, col, (bx, by + 5), (bx + (i % 3) - 1, by - 4), 2)


def draw_path(surf, rect, seed_x, seed_y):
    pygame.draw.rect(surf, (146, 122, 88), rect)
    r1 = _seeded(seed_x, seed_y, 2)
    speck = (128, 106, 74) if r1 < 0.5 else (162, 138, 100)
    for i in range(4):
        rx = _seeded(seed_x, seed_y, 30 + i)
        ry = _seeded(seed_x, seed_y, 40 + i)
        px = rect.x + rx * rect.w
        py = rect.y + ry * rect.h
        pygame.draw.circle(surf, speck, (int(px), int(py)), 1)


def draw_floor(surf, rect, seed_x, seed_y, zone=None):
    """Stone / plank floor; zone tints village smithy vs dungeon vs mine."""
    if zone == "village":
        base, line, speck = (118, 96, 72), (92, 72, 52), (98, 78, 56)
    elif zone == "dungeon":
        base, line, speck = (58, 52, 64), (40, 36, 46), (48, 42, 54)
    elif zone == "mine":
        base, line, speck = (78, 70, 62), (58, 52, 46), (66, 58, 50)
    else:
        base, line, speck = (72, 66, 78), (60, 55, 66), (52, 48, 58)
    pygame.draw.rect(surf, base, rect)
    # subtle tile seams
    mid_x = rect.x + rect.w // 2
    mid_y = rect.y + rect.h // 2
    pygame.draw.line(surf, line, (mid_x, rect.y), (mid_x, rect.bottom), 1)
    pygame.draw.line(surf, line, (rect.x, mid_y), (rect.right, mid_y), 1)
    pygame.draw.rect(surf, line, rect, 1)
    if _seeded(seed_x, seed_y, 3) < 0.2:
        pygame.draw.circle(surf, speck, rect.center, max(1, int(rect.w * 0.12)))


def draw_wall(surf, rect, zone, seed_x, seed_y):
    if zone == "village":
        draw_building_wall(surf, rect, seed_x, seed_y)
    elif zone == "mine":
        draw_cave_wall(surf, rect)
    elif zone == "dungeon":
        draw_dungeon_wall(surf, rect, seed_x, seed_y)
    else:
        pygame.draw.rect(surf, (35, 33, 38), rect)
        pygame.draw.rect(surf, (22, 20, 24), rect, 1)


def draw_building_wall(surf, rect, seed_x, seed_y):
    pygame.draw.rect(surf, (150, 118, 78), rect)
    for i in range(0, rect.h, 6):
        pygame.draw.line(surf, (128, 98, 62), (rect.x, rect.y + i), (rect.x + rect.w, rect.y + i), 1)
    pygame.draw.rect(surf, (96, 70, 44), rect, 2)


def draw_cave_wall(surf, rect):
    pygame.draw.rect(surf, (78, 72, 68), rect)
    pygame.draw.polygon(surf, (94, 88, 82), [
        (rect.x, rect.bottom), (rect.x + rect.w * 0.4, rect.y + rect.h * 0.2),
        (rect.x + rect.w * 0.7, rect.bottom)])
    pygame.draw.rect(surf, (54, 50, 48), rect, 1)


def draw_dungeon_wall(surf, rect, seed_x, seed_y):
    pygame.draw.rect(surf, (46, 44, 54), rect)
    brick_h = rect.h // 2
    offset = brick_h if int(seed_y) % 2 == 0 else 0
    pygame.draw.line(surf, (32, 30, 38), (rect.x, rect.y + brick_h), (rect.right, rect.y + brick_h), 1)
    bx = rect.x + offset
    pygame.draw.line(surf, (32, 30, 38), (bx, rect.y), (bx, rect.bottom), 1)


def draw_water(surf, rect, t):
    pygame.draw.rect(surf, (36, 84, 150), rect)
    phase = t * 3 + rect.x * 0.3 + rect.y * 0.2
    for i, frac in enumerate((0.35, 0.65)):
        y = rect.y + rect.h * frac + math.sin(phase + i) * 2
        pygame.draw.line(surf, (70, 130, 200), (rect.x + 2, y), (rect.right - 2, y), 1)
    pygame.draw.rect(surf, (28, 66, 120), rect, 1)


TERRAIN_DRAWERS = {}  # populated by client after importing world_map ids


# ---------------------------------------------------------------------------
# Resource nodes
# ---------------------------------------------------------------------------
def draw_tree(surf, cx, cy, tile, big=False, dark=False):
    trunk_h = tile * (0.34 if not big else 0.30)
    trunk_w = tile * 0.14
    trunk_color = (92, 62, 34)
    pygame.draw.rect(surf, trunk_color, (cx - trunk_w / 2, cy + tile * 0.08, trunk_w, trunk_h))
    canopy_r = tile * (0.36 if not big else 0.46)
    base_g = (26, 92, 34) if not dark else (18, 66, 26)
    mid_g = (34, 116, 42) if not dark else (24, 84, 34)
    top_g = (48, 140, 56) if not dark else (34, 100, 44)
    cy0 = cy - tile * 0.12
    pygame.draw.circle(surf, base_g, (cx - canopy_r * 0.35, cy0), canopy_r * 0.8)
    pygame.draw.circle(surf, base_g, (cx + canopy_r * 0.35, cy0), canopy_r * 0.8)
    pygame.draw.circle(surf, mid_g, (cx, cy0 - canopy_r * 0.25), canopy_r)
    pygame.draw.circle(surf, top_g, (cx - canopy_r * 0.2, cy0 - canopy_r * 0.5), canopy_r * 0.5)


def draw_rock_node(surf, cx, cy, tile, color, highlight):
    r = tile * 0.34
    pts = []
    n = 7
    for i in range(n):
        ang = TAU * i / n
        rr = r * (0.8 + 0.2 * ((i * 37) % 5) / 4)
        pts.append((cx + math.cos(ang) * rr, cy + math.sin(ang) * rr * 0.85 + r * 0.15))
    pygame.draw.polygon(surf, color, pts)
    pygame.draw.polygon(surf, (30, 28, 26), pts, 1)
    pygame.draw.polygon(surf, highlight, [
        (cx - r * 0.3, cy - r * 0.5), (cx + r * 0.15, cy - r * 0.6), (cx, cy - r * 0.1)])


def draw_fishing_spot(surf, cx, cy, tile, t):
    r = tile * 0.3
    phase = t * 4 + cx * 0.1
    for i in range(3):
        rr = r * (0.4 + 0.3 * i) + math.sin(phase + i) * 1.5
        alpha_col = (110 + i * 20, 180, 230)
        pygame.draw.circle(surf, alpha_col, (cx, cy), max(1, int(rr)), 1)


# ---------------------------------------------------------------------------
# Buildings (decorative roof drawn above the wall blocks -- handled per-tile
# by draw_wall, this just adds a roofline on the top row of a block from the
# client if desired; kept simple, wall texture already reads as a building).
# ---------------------------------------------------------------------------
def draw_ground_item(surf, rect, t):
    """Bobbing coin/loot sparkle — reads clearly as clickable gold."""
    bob = math.sin(t * 4) * 2
    cx, cy = rect.center
    cy += bob
    # soft shadow
    pygame.draw.ellipse(surf, (30, 25, 10), (cx - 8, cy + 6, 16, 5))
    # coin stack
    for i, col in enumerate(((170, 130, 30), (220, 180, 50), (255, 220, 90))):
        oy = 3 - i * 2
        pygame.draw.ellipse(surf, col, (cx - 7, cy - 3 + oy, 14, 10))
        pygame.draw.ellipse(surf, (140, 100, 20), (cx - 7, cy - 3 + oy, 14, 10), 1)
    pygame.draw.circle(surf, (255, 240, 160), (cx - 2, cy - 2), 2)


# ---------------------------------------------------------------------------
# Characters (players + humanoid NPCs)
# ---------------------------------------------------------------------------
def draw_humanoid(surf, cx, cy, tile, body_color, skin_color, hair_color,
                   weapon=None, shield=False, moving=False, t=0.0, robe=False):
    scale = tile / 32.0 * ART_SCALE
    bob = math.sin(t * 6) * 1.2 * ART_SCALE if moving else 0
    feet_y = cy + tile * 0.30

    # shadow
    shadow_r = tile * 0.28
    shadow = pygame.Surface((int(shadow_r * 2), int(shadow_r * 0.9)), pygame.SRCALPHA)
    pygame.draw.ellipse(shadow, (0, 0, 0, 90), shadow.get_rect())
    surf.blit(shadow, (cx - shadow_r, feet_y - shadow_r * 0.45))

    # legs
    leg_w = 4 * scale
    leg_h = 8 * scale
    swing = math.sin(t * 10) * 2 * scale if moving else 0
    pygame.draw.rect(surf, (60, 55, 90), (cx - 5 * scale, feet_y - leg_h + bob - swing, leg_w, leg_h))
    pygame.draw.rect(surf, (60, 55, 90), (cx + 1 * scale, feet_y - leg_h + bob + swing, leg_w, leg_h))

    # body / robe
    body_h = tile * 0.34
    body_w = tile * 0.40
    body_rect = pygame.Rect(0, 0, body_w, body_h)
    body_rect.center = (cx, cy + bob)
    if robe:
        pygame.draw.polygon(surf, body_color, [
            (cx - body_w * 0.35, body_rect.top), (cx + body_w * 0.35, body_rect.top),
            (cx + body_w * 0.55, body_rect.bottom), (cx - body_w * 0.55, body_rect.bottom)])
    else:
        pygame.draw.rect(surf, body_color, body_rect, border_radius=int(3 * scale))
    pygame.draw.rect(surf, tuple(max(0, c - 35) for c in body_color), body_rect, max(1, int(scale)), border_radius=int(3 * scale))

    # shield (left arm)
    if shield:
        sx, sy = cx - body_w * 0.55, cy + bob
        pygame.draw.ellipse(surf, (150, 150, 160), (sx - 4 * scale, sy - 6 * scale, 8 * scale, 12 * scale))
        pygame.draw.ellipse(surf, (90, 90, 100), (sx - 4 * scale, sy - 6 * scale, 8 * scale, 12 * scale), 1)

    # weapon (right arm)
    if weapon == "sword":
        wx, wy = cx + body_w * 0.5, cy + bob
        pygame.draw.line(surf, (200, 200, 210), (wx, wy + 6 * scale), (wx + 10 * scale, wy - 10 * scale), max(2, int(2 * scale)))
        pygame.draw.line(surf, (150, 110, 60), (wx, wy + 6 * scale), (wx - 2 * scale, wy + 9 * scale), max(2, int(2 * scale)))
    elif weapon == "axe":
        wx, wy = cx + body_w * 0.5, cy + bob
        pygame.draw.line(surf, (120, 85, 50), (wx, wy + 6 * scale), (wx + 8 * scale, wy - 8 * scale), max(2, int(2 * scale)))
        pygame.draw.polygon(surf, (160, 160, 170), [
            (wx + 6 * scale, wy - 10 * scale), (wx + 13 * scale, wy - 9 * scale), (wx + 7 * scale, wy - 3 * scale)])
    elif weapon == "pickaxe":
        wx, wy = cx + body_w * 0.5, cy + bob
        pygame.draw.line(surf, (120, 85, 50), (wx, wy + 6 * scale), (wx + 8 * scale, wy - 8 * scale), max(2, int(2 * scale)))
        pygame.draw.line(surf, (140, 140, 150), (wx + 4 * scale, wy - 11 * scale), (wx + 12 * scale, wy - 5 * scale), max(2, int(2 * scale)))
    elif weapon == "dagger":
        wx, wy = cx + body_w * 0.5, cy + bob
        pygame.draw.line(surf, (190, 190, 200), (wx, wy + 3 * scale), (wx + 6 * scale, wy - 5 * scale), max(2, int(2 * scale)))

    # head
    head_r = tile * 0.17
    head_c = (cx, cy - body_h * 0.55 + bob)
    pygame.draw.circle(surf, skin_color, head_c, head_r)
    # hair cap
    pygame.draw.arc(surf, hair_color, (head_c[0] - head_r, head_c[1] - head_r, head_r * 2, head_r * 2),
                     math.pi * 0.05, math.pi * 0.95, max(2, int(head_r * 0.5)))
    _draw_character_face(surf, head_c, head_r, scale, skin_color, hair_color, facing=1)

PLAYER_PALETTES = [
    ((70, 120, 210), (235, 195, 150), (70, 45, 30)),
    ((210, 90, 90), (230, 180, 140), (40, 30, 20)),
    ((90, 180, 120), (245, 210, 170), (25, 20, 15)),
    ((190, 150, 60), (220, 170, 130), (60, 40, 25)),
    ((150, 90, 190), (235, 195, 150), (15, 15, 20)),
]


def palette_for(entity_id):
    return PLAYER_PALETTES[entity_id % len(PLAYER_PALETTES)]


# ---------------------------------------------------------------------------
# Monsters
# ---------------------------------------------------------------------------
def draw_giant_rat(surf, cx, cy, tile, t, hurt=False, attacking=0.0):
    s = tile / 32.0 * ART_SCALE
    bob = math.sin(t * 8) * 1.5 * ART_SCALE
    body = (160, 70, 70) if hurt else (128, 112, 100)
    body_d = _shade(body, -35)
    body_l = _shade(body, 25)
    cy += bob
    pygame.draw.ellipse(surf, (20, 18, 16), (cx - 10 * s, cy + 8 * s, 22 * s, 5 * s))
    # pinkish rope tail
    pygame.draw.lines(surf, (170, 140, 130), False, [
        (cx + 8 * s, cy + 3 * s), (cx + 14 * s, cy + 6 * s), (cx + 18 * s, cy + 4 * s),
    ], max(2, int(1.8 * s)))
    pygame.draw.circle(surf, (190, 120, 120), (cx + 18 * s, cy + 4 * s), max(1, int(1.2 * s)))
    # body + belly
    pygame.draw.ellipse(surf, body, (cx - 11 * s, cy - 7 * s, 22 * s, 15 * s))
    pygame.draw.ellipse(surf, body_l, (cx - 8 * s, cy - 6 * s, 12 * s, 7 * s))
    pygame.draw.ellipse(surf, (180, 160, 145), (cx - 6 * s, cy - 1 * s, 10 * s, 6 * s))
    # ears
    for ox, oy in ((-7, -10), (-1, -11)):
        pygame.draw.circle(surf, body_l, (cx + ox * s, cy + oy * s), 3.5 * s)
        pygame.draw.circle(surf, (200, 140, 140), (cx + ox * s, cy + oy * s), 1.8 * s)
    # snout + nose + whiskers
    pygame.draw.ellipse(surf, body, (cx - 14 * s, cy - 6 * s, 12 * s, 10 * s))
    _poly(surf, body_l, [
        (cx - 14 * s, cy - 1 * s), (cx - 18 * s, cy + 1 * s), (cx - 13 * s, cy + 3 * s),
    ], body_d, 1)
    pygame.draw.circle(surf, (40, 20, 20), (cx - 12 * s, cy - 3 * s), max(2, int(1.3 * s)))
    pygame.draw.circle(surf, (220, 60, 40), (cx - 12.2 * s, cy - 3.1 * s), max(1, int(0.6 * s)))
    # beady eye
    pygame.draw.ellipse(surf, (255, 240, 180), (cx - 9 * s, cy - 5.5 * s, 3.2 * s, 2.8 * s))
    pygame.draw.circle(surf, (20, 18, 16), (cx - 7.5 * s, cy - 4.2 * s), max(1, int(0.9 * s)))
    for wy in (-1, 1, 2):
        pygame.draw.line(surf, (40, 35, 30), (cx - 16 * s, cy + wy * s), (cx - 20 * s, cy + (wy - 1) * s), 1)


def draw_skeleton(surf, cx, cy, tile, t, hurt=False, attacking=0.0):
    s = tile / 32.0 * ART_SCALE
    bob = math.sin(t * 5) * 1.0 * ART_SCALE
    bone = (200, 70, 70) if hurt else (236, 232, 218)
    bone_d = (160, 50, 50) if hurt else (170, 162, 145)
    cy += bob
    atk = max(0.0, min(1.0, float(attacking or 0)))
    lunge = math.sin(atk * math.pi) * 8 * s
    pygame.draw.ellipse(surf, (20, 18, 22), (cx - 8 * s, cy + 11 * s, 16 * s, 4 * s))
    for side in (-1, 1):
        pygame.draw.line(surf, bone, (cx + side * 3.5 * s, cy + 1 * s), (cx + side * 5 * s, cy + 12 * s), max(2, int(2.4 * s)))
        pygame.draw.circle(surf, bone_d, (cx + side * 4.2 * s, cy + 6 * s), 1.4 * s)
        pygame.draw.circle(surf, bone_d, (cx + side * 5 * s, cy + 12.5 * s), 1.8 * s)
    pygame.draw.line(surf, bone, (cx - 5 * s, cy + 1 * s), (cx + 5 * s, cy + 1 * s), max(2, int(2.2 * s)))
    pygame.draw.line(surf, bone, (cx, cy + 1 * s), (cx, cy - 9 * s), max(2, int(2.2 * s)))
    for i in range(4):
        yy = cy - 7 * s + i * 2.2 * s
        w = 5.5 * s - i * 0.3 * s
        pygame.draw.line(surf, bone, (cx - w, yy), (cx + w, yy), max(1, int(1.6 * s)))
    # left arm idle; right arm / sword lunges on attack
    pygame.draw.line(surf, bone, (cx - 5 * s, cy - 6 * s), (cx - 11 * s, cy + 3 * s), max(2, int(2 * s)))
    sword_hand = (cx + 11 * s + lunge, cy - 2 * s - lunge * 0.35)
    pygame.draw.line(surf, bone, (cx + 5 * s, cy - 6 * s), sword_hand, max(2, int(2 * s)))
    tip = (sword_hand[0] + 5 * s + lunge * 0.6, sword_hand[1] - 15 * s + lunge * 0.2)
    pygame.draw.line(surf, (150, 155, 165), sword_hand, tip, max(2, int(2.4 * s)))
    pygame.draw.line(surf, (110, 80, 50),
                     (sword_hand[0] - 1 * s, sword_hand[1] + 1 * s),
                     (sword_hand[0] + 2 * s, sword_hand[1] + 3 * s), max(2, int(2 * s)))
    if atk > 0.2:
        pygame.draw.line(surf, (220, 220, 200),
                         (sword_hand[0], sword_hand[1] - 2 * s), tip, max(1, int(s)))
    head = (cx, cy - 12 * s)
    pygame.draw.circle(surf, bone, head, 6.2 * s)
    pygame.draw.circle(surf, bone_d, head, 6.2 * s, max(1, int(s)))
    pygame.draw.arc(surf, bone_d, (head[0] - 5 * s, head[1] - 4 * s, 10 * s, 6 * s), 0.2, math.pi - 0.2, max(2, int(1.5 * s)))
    for ox in (-2.6, 1.6):
        pygame.draw.ellipse(surf, (18, 16, 14), (head[0] + ox * s, head[1] - 1.8 * s, 2.8 * s, 3.2 * s))
        pygame.draw.circle(surf, (180, 40, 40) if hurt else (60, 200, 90),
                           (head[0] + (ox + 1.2) * s, head[1] - 0.2 * s), max(1, int(0.7 * s)))
    _poly(surf, (30, 28, 26), [
        (head[0] - 0.8 * s, head[1] + 0.5 * s),
        (head[0] + 0.8 * s, head[1] + 0.5 * s),
        (head[0], head[1] + 2.8 * s),
    ])
    pygame.draw.rect(surf, bone_d, (head[0] - 2.8 * s, head[1] + 3.2 * s, 5.6 * s, 2.2 * s))
    for i in range(-2, 3):
        pygame.draw.line(surf, (30, 28, 26),
                         (head[0] + i * 1.2 * s, head[1] + 3.2 * s),
                         (head[0] + i * 1.2 * s, head[1] + 5.2 * s), 1)


def draw_goblin(surf, cx, cy, tile, t, hurt=False, attacking=0.0):
    s = tile / 32.0 * ART_SCALE
    bob = math.sin(t * 6) * 1.2 * ART_SCALE
    skin = (140, 40, 40) if hurt else (88, 138, 68)
    skin_d = _shade(skin, -40)
    skin_l = _shade(skin, 30)
    cy += bob
    atk = max(0.0, min(1.0, float(attacking or 0)))
    lunge = math.sin(atk * math.pi) * 7 * s
    pygame.draw.ellipse(surf, (20, 18, 22), (cx - 9 * s, cy + 11 * s, 18 * s, 4 * s))
    pygame.draw.rect(surf, (70, 58, 40), (cx - 6.5 * s, cy + 4 * s, 4.5 * s, 8 * s))
    pygame.draw.rect(surf, (70, 58, 40), (cx + 2 * s, cy + 4 * s, 4.5 * s, 8 * s))
    _poly(surf, (95, 78, 52), [
        (cx - 8 * s, cy - 5 * s), (cx + 8 * s, cy - 5 * s),
        (cx + 9 * s, cy + 6 * s), (cx - 9 * s, cy + 6 * s),
    ], (55, 45, 30), 1)
    # club swings forward on attack
    club_tip = (cx + 15 * s + lunge, cy - 13 * s - lunge * 0.25)
    pygame.draw.line(surf, (110, 80, 50), (cx + 8 * s, cy - 1 * s), club_tip, max(2, int(2.5 * s)))
    pygame.draw.circle(surf, (90, 70, 45), club_tip, 3.2 * s)
    if atk > 0.2:
        pygame.draw.line(surf, (180, 150, 100),
                         (cx + 10 * s, cy - 3 * s), club_tip, max(1, int(s)))
    head = (cx, cy - 11 * s)
    pygame.draw.circle(surf, skin, head, 7 * s)
    pygame.draw.circle(surf, skin_l, (head[0] - 1.5 * s, head[1] - 1 * s), 3 * s)
    pygame.draw.circle(surf, skin_d, head, 7 * s, 1)
    _poly(surf, skin, [(head[0] - 6 * s, head[1]), (head[0] - 13 * s, head[1] - 6 * s), (head[0] - 5 * s, head[1] - 3 * s)], skin_d, 1)
    _poly(surf, skin, [(head[0] + 6 * s, head[1]), (head[0] + 13 * s, head[1] - 6 * s), (head[0] + 5 * s, head[1] - 3 * s)], skin_d, 1)
    pygame.draw.line(surf, skin_d, (head[0] - 4 * s, head[1] - 2.5 * s), (head[0] - 1 * s, head[1] - 3 * s), max(2, int(s)))
    pygame.draw.line(surf, skin_d, (head[0] + 1 * s, head[1] - 3 * s), (head[0] + 4 * s, head[1] - 2.5 * s), max(2, int(s)))
    for ox in (-2.4, 2.4):
        pygame.draw.ellipse(surf, (255, 240, 80), (head[0] + ox * s - 1.6 * s, head[1] - 1.2 * s, 3.2 * s, 2.8 * s))
        pygame.draw.circle(surf, (20, 20, 18), (head[0] + ox * s, head[1] - 0.2 * s), max(1, int(0.9 * s)))
    _poly(surf, skin_d, [
        (head[0] - 1 * s, head[1] + 1 * s), (head[0] + 1 * s, head[1] + 1 * s), (head[0], head[1] + 3 * s),
    ])
    pygame.draw.line(surf, (40, 30, 20), (head[0] - 2.5 * s, head[1] + 4.2 * s), (head[0] + 2.5 * s, head[1] + 4.2 * s), max(2, int(s)))
    for ox in (-1.5, 1.5):
        _poly(surf, (240, 240, 230), [
            (head[0] + ox * s - 0.5 * s, head[1] + 4.2 * s),
            (head[0] + ox * s + 0.5 * s, head[1] + 4.2 * s),
            (head[0] + ox * s, head[1] + 6 * s),
        ])


MONSTER_DRAWERS = {
    "giant_rat": draw_giant_rat,
    "goblin": draw_goblin,
    "skeleton": draw_skeleton,
}


def draw_monster(surf, mtype, cx, cy, tile, t, hurt=False, attacking=0.0):
    fn = MONSTER_DRAWERS.get(mtype, draw_giant_rat)
    try:
        fn(surf, cx, cy, tile, t, hurt=hurt, attacking=attacking)
    except TypeError:
        fn(surf, cx, cy, tile, t, hurt=hurt)


# ---------------------------------------------------------------------------
# Item icons (for inventory / shop panels)
# ---------------------------------------------------------------------------
def draw_item_icon(surf, rect, item_id, items_db):
    item = items_db.get(item_id, {})
    itype = item.get("type", "misc")
    cx, cy = rect.center
    s = rect.w

    if item_id == "coins":
        pygame.draw.circle(surf, (230, 190, 60), (cx, cy), s * 0.26)
        pygame.draw.circle(surf, (170, 130, 30), (cx, cy), s * 0.26, 1)
        return
    if itype == "weapon" or item.get("tool_for") in ("woodcutting",) and "axe" in item_id:
        gold = (230, 200, 55)
        blade = (90, 95, 105) if "iron" in item_id else (
            (120, 140, 160) if "steel" in item_id else (
                (180, 130, 70) if "bronze" in item_id else (
                    (160, 90, 230) if "eclipse" in item_id else (180, 180, 190)
                )
            )
        )
        if "dagger" in item_id:
            pygame.draw.polygon(surf, blade, [
                (cx - s * 0.08, cy + s * 0.18), (cx + s * 0.08, cy + s * 0.12),
                (cx + s * 0.22, cy - s * 0.22), (cx, cy - s * 0.18)])
            pygame.draw.line(surf, gold, (cx - s * 0.16, cy + s * 0.16), (cx + s * 0.14, cy + s * 0.1), max(2, int(s * 0.08)))
        elif "battleaxe" in item_id or "cleaver" in item_id:
            pygame.draw.line(surf, (110, 75, 45) if "eclipse" not in item_id else (50, 30, 70),
                             (cx - s * 0.05, cy + s * 0.24), (cx + s * 0.05, cy - s * 0.12), max(3, int(s * 0.1)))
            pygame.draw.polygon(surf, blade, [
                (cx - s * 0.02, cy - s * 0.18), (cx + s * 0.32, cy - s * 0.30),
                (cx + s * 0.30, cy - s * 0.08), (cx + s * 0.05, cy - s * 0.05)])
            pygame.draw.polygon(surf, blade, [
                (cx - s * 0.02, cy - s * 0.08), (cx + s * 0.30, cy + s * 0.10),
                (cx + s * 0.24, cy + s * 0.20), (cx + s * 0.02, cy + s * 0.05)])
            if "eclipse" in item_id:
                pygame.draw.circle(surf, gold, (int(cx + s * 0.04), int(cy - s * 0.02)), max(2, int(s * 0.07)))
                pygame.draw.circle(surf, (200, 160, 255), (int(cx + s * 0.04), int(cy - s * 0.02)), max(1, int(s * 0.04)))
        elif "axe" in item_id:
            pygame.draw.line(surf, (110, 75, 45), (cx - s * 0.05, cy + s * 0.24), (cx + s * 0.08, cy - s * 0.2), max(2, int(s * 0.08)))
            pygame.draw.polygon(surf, blade, [
                (cx + s * 0.02, cy - s * 0.24), (cx + s * 0.28, cy - s * 0.18),
                (cx + s * 0.22, cy - s * 0.02), (cx + s * 0.05, cy - s * 0.06)])
        else:
            # sword — dark blade, gold guard
            pygame.draw.polygon(surf, blade, [
                (cx - s * 0.06, cy + s * 0.12), (cx + s * 0.08, cy + s * 0.08),
                (cx + s * 0.22, cy - s * 0.26), (cx + s * 0.05, cy - s * 0.28)])
            pygame.draw.line(surf, (200, 205, 215), (cx, cy + s * 0.05), (cx + s * 0.14, cy - s * 0.18), 1)
            pygame.draw.line(surf, gold, (cx - s * 0.18, cy + s * 0.14), (cx + s * 0.18, cy + s * 0.06), max(2, int(s * 0.09)))
            pygame.draw.circle(surf, gold, (int(cx - s * 0.05), int(cy + s * 0.22)), max(2, int(s * 0.06)))
        return
    if item.get("tool_for") == "mining":
        pygame.draw.line(surf, (120, 85, 50), (cx - s * 0.05, cy + s * 0.25), (cx + s * 0.05, cy - s * 0.2), max(2, int(s * 0.08)))
        pygame.draw.line(surf, (150, 150, 160), (cx - s * 0.22, cy - s * 0.15), (cx + s * 0.2, cy - s * 0.2), max(2, int(s * 0.09)))
        return
    if item.get("tool_for") == "fishing":
        pygame.draw.circle(surf, (210, 210, 220), (cx, cy), s * 0.24, max(1, int(s * 0.06)))
        pygame.draw.line(surf, (210, 210, 220), (cx - s * 0.12, cy - s * 0.12), (cx + s * 0.12, cy + s * 0.12), 1)
        pygame.draw.line(surf, (210, 210, 220), (cx - s * 0.12, cy + s * 0.12), (cx + s * 0.12, cy - s * 0.12), 1)
        return
    if item.get("equip_slot") == "shield":
        mid = (150, 155, 165) if "iron" in item_id else (
            (120, 140, 160) if "steel" in item_id else ((180, 130, 70) if "bronze" in item_id else (140, 100, 55))
        )
        if "sq" in item_id:
            pygame.draw.rect(surf, mid, (cx - s * 0.2, cy - s * 0.22, s * 0.4, s * 0.44), border_radius=2)
            pygame.draw.rect(surf, tuple(max(0, c - 40) for c in mid),
                             (cx - s * 0.2, cy - s * 0.22, s * 0.4, s * 0.44), 1, border_radius=2)
            pygame.draw.circle(surf, (40, 40, 45), (cx, cy), max(2, int(s * 0.07)))
        else:
            pts = [
                (cx - s * 0.22, cy - s * 0.2), (cx + s * 0.22, cy - s * 0.2),
                (cx + s * 0.2, cy + s * 0.1), (cx, cy + s * 0.28), (cx - s * 0.2, cy + s * 0.1),
            ]
            pygame.draw.polygon(surf, mid, pts)
            if "wood" not in item_id:
                red = (190, 40, 40)
                pygame.draw.line(surf, red, (cx, cy - s * 0.18), (cx, cy + s * 0.24), max(2, int(s * 0.07)))
                pygame.draw.line(surf, red, (cx - s * 0.18, cy), (cx + s * 0.18, cy), max(2, int(s * 0.07)))
                pygame.draw.polygon(surf, red, pts, max(1, int(s * 0.06)))
            else:
                pygame.draw.polygon(surf, (90, 60, 30), pts, 1)
        return
    if itype == "armor":
        if "helmet" in item_id or "cowl" in item_id or "helm" in item_id:
            col = (148, 102, 62) if "leather" in item_id else (
                (150, 155, 165) if "iron" in item_id else (
                    (120, 140, 160) if "steel" in item_id else (180, 130, 70)
                )
            )
            pygame.draw.ellipse(surf, col, (cx - s * 0.2, cy - s * 0.2, s * 0.4, s * 0.36))
            pygame.draw.rect(surf, tuple(max(0, c - 45) for c in col),
                             (cx - s * 0.22, cy - s * 0.02, s * 0.44, s * 0.14))
            if "steel" in item_id:
                pygame.draw.polygon(surf, (200, 40, 45), [
                    (cx - s * 0.02, cy - s * 0.22), (cx + s * 0.04, cy - s * 0.38),
                    (cx + s * 0.14, cy - s * 0.28), (cx + s * 0.06, cy - s * 0.16)])
            return
        if "legs" in item_id or "chaps" in item_id:
            col = (150, 155, 165) if "iron" in item_id else (
                (120, 140, 160) if "steel" in item_id else ((180, 130, 70) if "bronze" in item_id else (130, 90, 55))
            )
            pygame.draw.rect(surf, col, (cx - s * 0.2, cy - s * 0.1, s * 0.16, s * 0.32))
            pygame.draw.rect(surf, col, (cx + s * 0.04, cy - s * 0.1, s * 0.16, s * 0.32))
            pygame.draw.rect(surf, tuple(max(0, c - 40) for c in col), (cx - s * 0.2, cy - s * 0.1, s * 0.4, s * 0.1))
            if "chain" in item_id:
                for i in range(3):
                    pygame.draw.circle(surf, tuple(min(255, c + 30) for c in col),
                                       (int(cx - s * 0.12), int(cy + i * s * 0.08)), max(1, int(s * 0.04)), 1)
            return
        # body armour
        if "chain" in item_id or item_id == "goblin_mail":
            col = (150, 155, 165) if "iron" in item_id else (
                (120, 140, 160) if "steel" in item_id else ((180, 130, 70) if "bronze" in item_id else (110, 130, 90))
            )
            pygame.draw.polygon(surf, col, [
                (cx - s * 0.18, cy - s * 0.2), (cx + s * 0.18, cy - s * 0.2),
                (cx + s * 0.22, cy + s * 0.24), (cx - s * 0.22, cy + s * 0.24)])
            for row in range(4):
                for col_i in range(-2, 3):
                    pygame.draw.circle(
                        surf, tuple(min(255, c + 25) for c in col),
                        (int(cx + col_i * s * 0.07), int(cy - s * 0.08 + row * s * 0.08)),
                        max(1, int(s * 0.035)), 1,
                    )
            return
        if "iron" in item_id or "steel" in item_id:
            pygame.draw.polygon(surf, (242, 242, 246), [
                (cx - s * 0.2, cy - s * 0.22), (cx + s * 0.2, cy - s * 0.22),
                (cx + s * 0.24, cy + s * 0.26), (cx - s * 0.24, cy + s * 0.26)])
            star = (230, 200, 55)
            pygame.draw.polygon(surf, star, [
                (cx, cy - s * 0.12), (cx + s * 0.04, cy - s * 0.02),
                (cx + s * 0.14, cy), (cx + s * 0.04, cy + s * 0.02),
                (cx, cy + s * 0.12), (cx - s * 0.04, cy + s * 0.02),
                (cx - s * 0.14, cy), (cx - s * 0.04, cy - s * 0.02)])
            pygame.draw.circle(surf, (160, 165, 175), (cx, cy - s * 0.28), s * 0.1)
            pygame.draw.polygon(surf, (200, 40, 40), [
                (cx - s * 0.02, cy - s * 0.34), (cx + s * 0.04, cy - s * 0.48), (cx + s * 0.1, cy - s * 0.36)])
        elif "bronze" in item_id:
            color = (180, 130, 70)
            pygame.draw.polygon(surf, color, [
                (cx - s * 0.2, cy - s * 0.22), (cx + s * 0.2, cy - s * 0.22),
                (cx + s * 0.24, cy + s * 0.26), (cx - s * 0.24, cy + s * 0.26)])
            pygame.draw.circle(surf, (160, 110, 55), (cx - s * 0.18, cy - s * 0.12), s * 0.08)
            pygame.draw.circle(surf, (160, 110, 55), (cx + s * 0.18, cy - s * 0.12), s * 0.08)
        else:
            color = (150, 100, 60) if "leather" in item_id else (110, 130, 90)
            pygame.draw.polygon(surf, color, [
                (cx - s * 0.2, cy - s * 0.22), (cx + s * 0.2, cy - s * 0.22),
                (cx + s * 0.24, cy + s * 0.26), (cx - s * 0.24, cy + s * 0.26)])
        return
    if item_id in ("logs", "oak_logs"):
        color = (140, 95, 55) if item_id == "logs" else (90, 60, 35)
        for i in range(3):
            pygame.draw.circle(surf, color, (int(cx - s * 0.18 + i * s * 0.18), cy), s * 0.1)
            pygame.draw.circle(surf, (200, 170, 130), (int(cx - s * 0.18 + i * s * 0.18), cy), s * 0.04)
        return
    if "ore" in item_id:
        colors = {"copper_ore": (200, 120, 60), "tin_ore": (170, 170, 180), "iron_ore": (140, 90, 70)}
        pygame.draw.polygon(surf, colors.get(item_id, (150, 150, 150)), [
            (cx - s * 0.2, cy + s * 0.15), (cx - s * 0.08, cy - s * 0.2),
            (cx + s * 0.15, cy - s * 0.15), (cx + s * 0.2, cy + s * 0.1), (cx, cy + s * 0.24)])
        return
    if "shrimp" in item_id or "sardine" in item_id or "fish" in item_id:
        cooked = "cooked" in item_id
        color = (210, 140, 90) if cooked else (150, 170, 210)
        pygame.draw.ellipse(surf, color, (cx - s * 0.24, cy - s * 0.12, s * 0.4, s * 0.24))
        pygame.draw.polygon(surf, color, [(cx + s * 0.14, cy), (cx + s * 0.28, cy - s * 0.1), (cx + s * 0.28, cy + s * 0.1)])
        return
    if item_id == "bread":
        pygame.draw.ellipse(surf, (200, 150, 90), (cx - s * 0.22, cy - s * 0.16, s * 0.44, s * 0.32))
        pygame.draw.arc(surf, (150, 100, 50), (cx - s * 0.18, cy - s * 0.12, s * 0.36, s * 0.24), 0.3, 2.8, 1)
        return
    if item_id == "health_potion":
        pygame.draw.rect(surf, (150, 200, 230), (cx - s * 0.1, cy - s * 0.22, s * 0.2, s * 0.1))
        pygame.draw.polygon(surf, (220, 60, 70), [
            (cx - s * 0.16, cy - s * 0.1), (cx + s * 0.16, cy - s * 0.1),
            (cx + s * 0.14, cy + s * 0.24), (cx - s * 0.14, cy + s * 0.24)])
        return
    if item_id == "gold_ring":
        pygame.draw.circle(surf, (230, 190, 60), (cx, cy), s * 0.2, max(2, int(s * 0.06)))
        return
    if item_id == "bones":
        pygame.draw.line(surf, (230, 225, 210), (cx - s * 0.2, cy), (cx + s * 0.2, cy), max(2, int(s * 0.07)))
        pygame.draw.circle(surf, (230, 225, 210), (cx - s * 0.2, cy), s * 0.08)
        pygame.draw.circle(surf, (230, 225, 210), (cx + s * 0.2, cy), s * 0.08)
        return
    if "bar" in item_id:
        color = (180, 120, 60) if "bronze" in item_id else (160, 160, 170)
        pygame.draw.rect(surf, color, (cx - s * 0.22, cy - s * 0.1, s * 0.44, s * 0.2), border_radius=2)
        pygame.draw.rect(surf, tuple(max(0, c - 40) for c in color),
                         (cx - s * 0.22, cy - s * 0.1, s * 0.44, s * 0.2), 1, border_radius=2)
        return
    # default: small gem
    pygame.draw.polygon(surf, (150, 200, 230), [
        (cx, cy - s * 0.22), (cx + s * 0.2, cy), (cx, cy + s * 0.22), (cx - s * 0.2, cy)])
    pygame.draw.polygon(surf, (90, 140, 180), [
        (cx, cy - s * 0.22), (cx + s * 0.2, cy), (cx, cy + s * 0.22), (cx - s * 0.2, cy)], 1)


# ---------------------------------------------------------------------------
# Expanded procedural sprites
# ---------------------------------------------------------------------------

def _poly(surf, color, pts, outline=None, width=1):
    pygame.draw.polygon(surf, color, pts)
    if outline:
        pygame.draw.polygon(surf, outline, pts, width)


def draw_tree_detailed(surf, cx, cy, tile, variant=0, t=0.0):
    """Layered tree with trunk, branches, foliage clusters and bark marks."""
    s = tile / 32.0 * ART_SCALE
    trunk = (88, 57, 32) if variant % 2 == 0 else (104, 66, 34)
    dark = (53, 72, 31)
    mid = (35, 105, 40)
    light = (67, 138, 55)

    pygame.draw.ellipse(
        surf, (34, 48, 30),
        (cx - 11*s, cy + 8*s, 22*s, 6*s)
    )
    pygame.draw.polygon(surf, trunk, [
        (cx-4*s, cy+10*s), (cx+4*s, cy+10*s),
        (cx+3*s, cy-5*s), (cx+7*s, cy-12*s),
        (cx+4*s, cy-13*s), (cx, cy-6*s),
        (cx-5*s, cy-12*s), (cx-7*s, cy-11*s),
        (cx-2*s, cy-4*s)
    ])
    pygame.draw.line(surf, (133, 88, 45),
                     (cx-1*s, cy+7*s), (cx+1*s, cy-7*s), max(1, int(s)))
    pygame.draw.line(surf, (62, 40, 25),
                     (cx+2*s, cy+5*s), (cx+4*s, cy-4*s), max(1, int(s)))

    offset = math.sin(t * 0.8 + variant) * 0.6
    clusters = [
        (-8, -9, 8, dark), (7, -9, 8, dark),
        (-3, -15, 9, mid), (8, -15, 7, mid),
        (-1, -21, 7, light), (-10, -17, 6, mid),
    ]
    for ox, oy, rr, col in clusters:
        pygame.draw.circle(surf, col, (cx + (ox+offset)*s, cy + oy*s), rr*s)

    for ox, oy in [(-5, -18), (1, -23), (8, -13), (-11, -12)]:
        pygame.draw.circle(surf, (91, 158, 67),
                           (cx+ox*s, cy+oy*s), max(1, int(1.5*s)))


def draw_rock_detailed(surf, cx, cy, tile, variant=0, ore_type=None):
    """Faceted rock with cracks and small ground shadow.

    ore_type: 'copper_rock' | 'tin_rock' | 'iron_rock' — tints the rock so
    players can tell ores apart at a glance.
    """
    s = tile / 32.0 * ART_SCALE
    r = 10*s
    pygame.draw.ellipse(surf, (39, 38, 34),
                        (cx-r*1.1, cy+r*.35, r*2.2, r*.55))

    if variant % 3 == 0:
        pts = [(-10,4), (-7,-7), (-1,-11), (8,-7), (11,2), (5,10), (-5,9)]
    elif variant % 3 == 1:
        pts = [(-11,1), (-5,-9), (4,-10), (11,-2), (8,8), (-3,11), (-10,6)]
    else:
        pts = [(-9,6), (-8,-4), (0,-11), (10,-5), (9,5), (1,10)]

    world = [(cx+x*s, cy+y*s) for x, y in pts]
    base = (91, 89, 84)
    hi = (126, 123, 113)
    vein = None
    if ore_type == "copper_rock":
        base, hi, vein = (150, 95, 55), (210, 145, 80), (230, 160, 70)
    elif ore_type == "tin_rock":
        base, hi, vein = (145, 150, 160), (200, 205, 215), (230, 230, 240)
    elif ore_type == "iron_rock":
        base, hi, vein = (110, 75, 60), (165, 120, 90), (190, 100, 70)
    elif ore_type == "coal_rock":
        base, hi, vein = (48, 48, 52), (90, 90, 98), (140, 140, 150)

    _poly(surf, base, world, (39, 38, 36), max(1, int(s)))
    _poly(surf, hi, [
        (cx-6*s, cy-5*s), (cx-1*s, cy-9*s),
        (cx+5*s, cy-5*s), (cx+1*s, cy-2*s)
    ])
    if vein:
        pygame.draw.line(surf, vein,
                         (cx-4*s, cy-1*s), (cx+5*s, cy+3*s), max(2, int(1.5*s)))
        pygame.draw.line(surf, vein,
                         (cx+1*s, cy-6*s), (cx+4*s, cy+1*s), max(1, int(s)))
    pygame.draw.line(surf, (57, 55, 52),
                     (cx-2*s, cy-2*s), (cx-5*s, cy+4*s), max(1, int(s)))
    pygame.draw.line(surf, (57, 55, 52),
                     (cx-5*s, cy+4*s), (cx-1*s, cy+6*s), max(1, int(s)))


def draw_furnace(surf, cx, cy, tile, t=0.0):
    """Stone furnace with a glowing fire mouth (smelting station)."""
    s = tile / 32.0 * ART_SCALE
    glow = int(40 + 30 * abs(math.sin(t * 4)))
    pygame.draw.ellipse(surf, (30, 28, 26), (cx-10*s, cy+7*s, 20*s, 5*s))
    pygame.draw.rect(surf, (95, 90, 82), (cx-8*s, cy-2*s, 16*s, 12*s), border_radius=max(1, int(2*s)))
    pygame.draw.rect(surf, (60, 56, 50), (cx-8*s, cy-2*s, 16*s, 12*s), max(1, int(s)), border_radius=max(1, int(2*s)))
    pygame.draw.rect(surf, (40, 28, 22), (cx-5*s, cy+2*s, 10*s, 5*s))
    pygame.draw.rect(surf, (230, 120 + glow // 2, 40), (cx-4*s, cy+3*s, 8*s, 3*s))
    pygame.draw.rect(surf, (72, 68, 62), (cx-2*s, cy-11*s, 5*s, 9*s))
    # smoke puff
    pygame.draw.circle(surf, (90, 90, 95), (cx + 2*s, cy - 13*s + math.sin(t*3)*s), max(1, int(2*s)))


def draw_anvil(surf, cx, cy, tile, t=0.0):
    """Heavy iron anvil for smithing weapons and armour."""
    s = tile / 32.0 * ART_SCALE
    pygame.draw.ellipse(surf, (30, 28, 26), (cx-9*s, cy+7*s, 18*s, 4*s))
    # stump/base
    pygame.draw.rect(surf, (90, 60, 35), (cx-4*s, cy+2*s, 8*s, 6*s))
    pygame.draw.rect(surf, (60, 40, 22), (cx-4*s, cy+2*s, 8*s, 6*s), 1)
    # anvil body
    pygame.draw.rect(surf, (120, 125, 135), (cx-8*s, cy-2*s, 16*s, 5*s), border_radius=1)
    pygame.draw.rect(surf, (80, 85, 95), (cx-8*s, cy-2*s, 16*s, 5*s), 1, border_radius=1)
    # horn
    pygame.draw.polygon(surf, (130, 135, 145), [
        (cx+8*s, cy-1*s), (cx+13*s, cy), (cx+8*s, cy+2*s)
    ])
    # highlight
    pygame.draw.line(surf, (180, 185, 195), (cx-6*s, cy-1*s), (cx+5*s, cy-1*s), max(1, int(s)))


def draw_forge(surf, cx, cy, tile, t=0.0):
    """Backward-compatible combined forge mark (prefer draw_furnace / draw_anvil)."""
    draw_furnace(surf, cx - tile * 0.15, cy, tile, t)
    draw_anvil(surf, cx + tile * 0.35, cy, tile * 0.85, t)


def draw_water_detailed(surf, rect, t, seed_x=0, seed_y=0):
    """Textured water tile with deterministic ripples plus animated highlights."""
    pygame.draw.rect(surf, (31, 78, 142), rect)
    for row in range(3):
        y = rect.y + (row + 0.5) * rect.h / 3
        phase = t * (2.0 + row*.25) + seed_x*.7 + seed_y*.31 + row
        for j in range(2):
            x = rect.x + (j + .15) * rect.w / 2
            length = rect.w * (.24 + .08 * _seeded(seed_x, seed_y, 70+row*2+j))
            yy = y + math.sin(phase+j*1.7) * 1.8
            pygame.draw.line(surf, (72, 139, 205),
                             (x, yy), (min(rect.right-2, x+length), yy),
                             max(1, int(rect.h/18)))
    pygame.draw.rect(surf, (24, 57, 108), rect, 1)


def draw_house(surf, rect, style=0, t=0.0):
    """Standalone building sprite for village/decorative structures."""
    x, y, w, h = rect
    wall = (164, 122, 78) if style % 2 == 0 else (132, 105, 82)
    roof = (92, 53, 43) if style % 2 == 0 else (63, 67, 72)
    trim = (72, 48, 34)

    pygame.draw.rect(surf, (42, 38, 35), (x+3, y+h-3, w-6, 6))
    pygame.draw.rect(surf, wall, (x, y+h*.30, w, h*.70))
    pygame.draw.rect(surf, trim, (x, y+h*.30, w, h*.70), 2)

    _poly(surf, roof, [
        (x-5, y+h*.32), (x+w*.5, y), (x+w+5, y+h*.32)
    ], (47, 34, 31), 2)

    # timber framing / stone courses
    if style % 2 == 0:
        pygame.draw.line(surf, trim, (x+w*.5, y+h*.34),
                         (x+w*.5, y+h), 2)
        pygame.draw.line(surf, trim, (x, y+h*.62),
                         (x+w, y+h*.62), 2)
    else:
        for yy in range(int(y+h*.45), int(y+h), 8):
            pygame.draw.line(surf, (103, 79, 64), (x+2, yy), (x+w-2, yy), 1)

    # door
    door_w, door_h = w*.20, h*.40
    pygame.draw.rect(surf, (70, 45, 32),
                     (x+w*.40, y+h-door_h, door_w, door_h))
    pygame.draw.circle(surf, (210, 170, 70),
                       (x+w*.40+door_w*.78, y+h-door_h*.52), max(1, int(w*.025)))

    # windows
    for wx in (x+w*.18, x+w*.64):
        pygame.draw.rect(surf, (45, 78, 105),
                         (wx, y+h*.48, w*.15, h*.18))
        pygame.draw.rect(surf, (205, 177, 105),
                         (wx, y+h*.48, w*.15, h*.18), 1)
        pygame.draw.line(surf, (205, 177, 105),
                         (wx+w*.075, y+h*.48), (wx+w*.075, y+h*.66), 1)


def _draw_character_face(surf, head, hr, s, skin_color, hair_color, facing=1):
    """Readable low-poly face: eyes, brows, nose, mouth, ears — drawn after hair bangs."""
    hx, hy = head
    outline = (40, 28, 22)
    skin_d = _shade(skin_color, -35)
    skin_l = _shade(skin_color, 18)
    # ears
    for side in (-1, 1):
        ex = hx + side * hr * 0.95
        _poly(surf, skin_color, [
            (hx + side * hr * 0.7, hy - hr * 0.15),
            (ex + side * hr * 0.15, hy),
            (hx + side * hr * 0.7, hy + hr * 0.35),
        ], outline, 1)
        pygame.draw.line(surf, skin_d, (hx + side * hr * 0.75, hy), (ex, hy + hr * 0.05), 1)

    # cheek blush / shade
    pygame.draw.circle(surf, _shade(skin_color, -12), (hx - hr * 0.55, hy + hr * 0.25), max(1, int(hr * 0.18)))
    pygame.draw.circle(surf, skin_l, (hx + hr * 0.15, hy - hr * 0.05), max(1, int(hr * 0.22)))

    # eyebrows
    brow = _shade(hair_color, -10)
    for side, ox in ((-1, -0.38), (1, 0.32)):
        bx = hx + ox * hr
        by = hy - hr * 0.22
        pygame.draw.line(surf, brow,
                         (bx - hr * 0.18, by + hr * 0.04),
                         (bx + hr * 0.18, by - hr * 0.02),
                         max(2, int(1.4 * s)))

    # eyes — white sclera + iris + pupil (large enough to read at ART_SCALE)
    eye_y = hy - hr * 0.02
    for ox in (-0.34, 0.30):
        ex = hx + ox * hr
        ew, eh = hr * 0.28, hr * 0.32
        pygame.draw.ellipse(surf, (245, 245, 248), (ex - ew, eye_y - eh * 0.55, ew * 2, eh * 1.1))
        pygame.draw.ellipse(surf, outline, (ex - ew, eye_y - eh * 0.55, ew * 2, eh * 1.1), max(1, int(s * 0.6)))
        iris = (70, 110, 160)
        pygame.draw.circle(surf, iris, (ex + facing * hr * 0.04, eye_y), max(2, int(hr * 0.14)))
        pygame.draw.circle(surf, (20, 18, 16), (ex + facing * hr * 0.05, eye_y), max(1, int(hr * 0.07)))
        # highlight
        pygame.draw.circle(surf, (255, 255, 255), (ex - hr * 0.04, eye_y - hr * 0.06), max(1, int(hr * 0.04)))

    # nose (small facet)
    _poly(surf, skin_d, [
        (hx - hr * 0.02, hy - hr * 0.05),
        (hx + hr * 0.14, hy + hr * 0.22),
        (hx - hr * 0.12, hy + hr * 0.22),
    ])
    pygame.draw.line(surf, outline, (hx, hy + hr * 0.05), (hx + hr * 0.08, hy + hr * 0.22), 1)

    # mouth
    my = hy + hr * 0.42
    pygame.draw.line(surf, (120, 70, 70), (hx - hr * 0.22, my), (hx + hr * 0.22, my), max(2, int(1.2 * s)))
    pygame.draw.arc(surf, (160, 90, 90),
                    (hx - hr * 0.22, my - hr * 0.12, hr * 0.44, hr * 0.28),
                    math.pi * 1.05, math.pi * 1.95, max(1, int(s)))


def _metal_palette(item_id):
    """Return (light, mid, dark, accent) for bronze / iron / wood / leather gear."""
    if not item_id:
        return None
    if "eclipse" in item_id:
        return (230, 210, 255), (110, 55, 180), (28, 12, 48), (255, 215, 90)
    if "iron" in item_id:
        return (188, 192, 198), (148, 152, 160), (98, 102, 110), (230, 200, 55)
    if "steel" in item_id:
        return (170, 185, 200), (120, 140, 160), (70, 88, 105), (230, 200, 55)
    if "bronze" in item_id:
        return (196, 140, 72), (160, 108, 52), (110, 72, 34), (230, 190, 70)
    if "wood" in item_id:
        return (160, 118, 70), (120, 82, 45), (78, 52, 28), (200, 160, 60)
    if "leather" in item_id or "goblin" in item_id:
        return (148, 102, 62), (110, 72, 42), (72, 48, 28), (180, 140, 70)
    return (170, 174, 180), (130, 134, 142), (88, 90, 98), (220, 190, 60)


def _draw_kite_shield(surf, cx, cy, s, item_id):
    """Heater / kite shield — red cross + border for metal, wood grain for wooden."""
    light, mid, dark, accent = _metal_palette(item_id) or ((150, 150, 155), (110, 110, 118), (70, 70, 78), (200, 50, 50))
    # kite outline points (point at bottom)
    pts = [
        (cx - 7 * s, cy - 5 * s),
        (cx + 7 * s, cy - 5 * s),
        (cx + 6.5 * s, cy + 4 * s),
        (cx, cy + 10 * s),
        (cx - 6.5 * s, cy + 4 * s),
    ]
    if item_id and "wood" in item_id:
        _poly(surf, mid, pts, dark, max(1, int(s)))
        pygame.draw.line(surf, dark, (cx, cy - 4 * s), (cx, cy + 8 * s), max(1, int(s)))
        pygame.draw.line(surf, accent, (cx - 4 * s, cy), (cx + 4 * s, cy), 1)
        return
    # metal face
    _poly(surf, mid, pts, dark, 1)
    # red cross
    red = (190, 40, 40)
    pygame.draw.line(surf, red, (cx, cy - 4.5 * s), (cx, cy + 8.5 * s), max(2, int(2.2 * s)))
    pygame.draw.line(surf, red, (cx - 5.5 * s, cy + 0.5 * s), (cx + 5.5 * s, cy + 0.5 * s), max(2, int(2.2 * s)))
    # red border
    pygame.draw.polygon(surf, red, pts, max(2, int(1.8 * s)))
    # boss
    pygame.draw.circle(surf, dark, (cx, cy + 0.5 * s), max(1, int(1.2 * s)))


def _draw_square_shield(surf, cx, cy, s, item_id):
    """Rectangular square shield with rivets — distinct from kite shields."""
    light, mid, dark, _ = _metal_palette(item_id) or ((150, 150, 155), (110, 110, 118), (70, 70, 78), (200, 50, 50))
    pts = [
        (cx - 6.5 * s, cy - 6 * s),
        (cx + 6.5 * s, cy - 6 * s),
        (cx + 6.5 * s, cy + 7 * s),
        (cx - 6.5 * s, cy + 7 * s),
    ]
    _poly(surf, mid, pts, dark, max(1, int(s)))
    _poly(surf, light, [
        (cx - 5.5 * s, cy - 5 * s), (cx + 1 * s, cy - 5 * s),
        (cx + 1 * s, cy + 1 * s), (cx - 5.5 * s, cy + 1 * s),
    ])
    for ox, oy in ((-3.5, -3), (3.5, -3), (-3.5, 3.5), (3.5, 3.5)):
        pygame.draw.circle(surf, dark, (cx + ox * s, cy + oy * s), max(1, int(0.9 * s)))
    pygame.draw.circle(surf, light, (cx, cy + 0.5 * s), max(2, int(1.8 * s)))
    pygame.draw.circle(surf, dark, (cx, cy + 0.5 * s), max(2, int(1.8 * s)), 1)


def _draw_shield(surf, cx, cy, s, item_id):
    if item_id and "sq" in item_id:
        _draw_square_shield(surf, cx, cy, s, item_id)
    else:
        _draw_kite_shield(surf, cx, cy, s, item_id)


def _draw_sword(surf, hx, hy, s, facing, item_id, swing=0.0):
    """Straight blade + gold crossguard. swing 0..1 arcs the cut."""
    light, mid, dark, gold = _metal_palette(item_id) or ((200, 200, 210), (160, 160, 170), (100, 100, 110), (230, 200, 55))
    blade = dark if "iron" in (item_id or "") else mid
    # Idle tip up-right; during swing wind up overhead then slash across.
    if swing > 0:
        # phase: 0 raise, 0.45 impact forward, 1 recover
        ang = -1.55 + swing * 2.6  # radians from vertical-ish to horizontal slash
        reach = 16 * s
        tip_x = hx + facing * math.sin(ang) * reach
        tip_y = hy - math.cos(ang) * reach
        mid_x = hx + facing * math.sin(ang) * reach * 0.45
        mid_y = hy - math.cos(ang) * reach * 0.45
    else:
        tip_x = hx + facing * 10 * s
        tip_y = hy - 15 * s
        mid_x = hx + facing * 4 * s
        mid_y = hy - 6 * s
    # blade (wide polygon)
    _poly(surf, blade, [
        (hx + facing * 1.2 * s, hy - 1 * s),
        (hx + facing * 2.8 * s, hy - 1.5 * s),
        (tip_x + facing * 0.5 * s, tip_y),
        (tip_x - facing * 0.8 * s, tip_y + 1.5 * s),
        (hx + facing * 0.4 * s, hy + 0.5 * s),
    ], _shade(blade, -30), 1)
    # fuller / motion streak
    pygame.draw.line(surf, light, (mid_x, mid_y),
                     (tip_x - facing * 0.5 * s, tip_y + 3 * s), 1)
    if swing > 0.15 and swing < 0.75:
        streak = max(1, int(2 * s))
        pygame.draw.line(surf, (255, 255, 220, 180),
                         (hx + facing * 2 * s, hy - 2 * s), (tip_x, tip_y), streak)
    # gold crossguard
    _poly(surf, gold, [
        (hx - facing * 3.5 * s, hy + 0.5 * s),
        (hx + facing * 3.5 * s, hy - 0.5 * s),
        (hx + facing * 3.5 * s, hy + 2 * s),
        (hx - facing * 3.5 * s, hy + 3 * s),
    ], _shade(gold, -40), 1)
    # grip
    pygame.draw.line(surf, _shade(gold, -20), (hx, hy + 2 * s), (hx - facing * 1.5 * s, hy + 6 * s), max(2, int(2.2 * s)))
    # pommel
    pygame.draw.circle(surf, gold, (hx - facing * 1.5 * s, hy + 6.5 * s), max(1, int(1.6 * s)))


def _draw_dagger(surf, hx, hy, s, facing, item_id):
    light, mid, dark, gold = _metal_palette(item_id) or ((200, 200, 210), (160, 160, 170), (100, 100, 110), (230, 200, 55))
    tip = (hx + facing * 7 * s, hy - 9 * s)
    _poly(surf, mid, [
        (hx, hy), (hx + facing * 1.5 * s, hy - 0.5 * s), tip, (hx - facing * 0.5 * s, hy + 0.5 * s),
    ], dark, 1)
    pygame.draw.line(surf, gold, (hx - facing * 2 * s, hy + 0.5 * s), (hx + facing * 2 * s, hy), max(2, int(1.8 * s)))


def _draw_axe(surf, hx, hy, s, facing, item_id):
    light, mid, dark, gold = _metal_palette(item_id) or ((180, 180, 185), (140, 140, 150), (90, 90, 100), (150, 100, 50))
    pygame.draw.line(surf, (110, 75, 45), (hx, hy), (hx + facing * 7 * s, hy - 13 * s), max(2, int(2.4 * s)))
    _poly(surf, mid, [
        (hx + facing * 5 * s, hy - 14 * s),
        (hx + facing * 14 * s, hy - 12 * s),
        (hx + facing * 13 * s, hy - 6 * s),
        (hx + facing * 7 * s, hy - 5 * s),
    ], dark, 1)


def _draw_battleaxe(surf, hx, hy, s, facing, item_id, swing=0.0):
    """Large double-bit battleaxe — heavier silhouette than a woodcutting axe."""
    light, mid, dark, gold = _metal_palette(item_id) or ((180, 180, 185), (140, 140, 150), (90, 90, 100), (230, 200, 55))
    eclipse = bool(item_id and "eclipse" in item_id)
    scale = 1.35 if eclipse else 1.0
    reach = (1.0 + 0.15 * math.sin(max(0.0, min(1.0, swing)) * math.pi)) * scale
    tip_x = hx + facing * 10 * s * reach
    tip_y = hy - 14 * s * reach
    shaft = (40, 25, 55) if eclipse else (95, 65, 40)
    pygame.draw.line(surf, shaft, (hx, hy + 1 * s), (tip_x - facing * 1 * s, tip_y + 2 * s), max(3, int((3.4 if eclipse else 2.8) * s)))
    # twin crescent blades
    _poly(surf, mid, [
        (tip_x - facing * 2 * s, tip_y + 1 * s),
        (tip_x + facing * (10 if eclipse else 8) * s, tip_y - (6 if eclipse else 4) * s),
        (tip_x + facing * (9 if eclipse else 7) * s, tip_y + 2 * s),
        (tip_x + facing * 2 * s, tip_y + 4 * s),
    ], dark, 1)
    _poly(surf, light, [
        (tip_x - facing * 2 * s, tip_y + 1 * s),
        (tip_x + facing * (9 if eclipse else 7) * s, tip_y + (10 if eclipse else 8) * s),
        (tip_x + facing * (7 if eclipse else 5) * s, tip_y + (12 if eclipse else 10) * s),
        (tip_x + facing * 1 * s, tip_y + 5 * s),
    ], dark, 1)
    pygame.draw.circle(surf, gold, (tip_x - facing * 1.5 * s, tip_y + 3 * s), max(1, int((2.4 if eclipse else 1.6) * s)))
    if eclipse:
        glow = (180, 120, 255)
        pygame.draw.circle(surf, glow, (tip_x - facing * 1.5 * s, tip_y + 3 * s), max(1, int(1.2 * s)))
        # rune notches on the upper blade
        for i in range(3):
            ox = tip_x + facing * (3 + i * 2) * s
            oy = tip_y - (2 - i * 0.6) * s
            pygame.draw.circle(surf, gold, (ox, oy), max(1, int(0.9 * s)))
        # trailing spark near the pommel
        pygame.draw.circle(surf, glow, (hx + facing * 1 * s, hy - 2 * s), max(1, int(1.4 * s)))


def _draw_pickaxe(surf, hx, hy, s, facing, item_id):
    pygame.draw.line(surf, (110, 75, 45), (hx, hy), (hx + facing * 7 * s, hy - 12 * s), max(2, int(2.2 * s)))
    light, mid, dark, _ = _metal_palette(item_id) or ((170, 170, 175), (130, 130, 140), (90, 90, 100), (0, 0, 0))
    pygame.draw.line(surf, mid, (hx + facing * 2 * s, hy - 14 * s), (hx + facing * 12 * s, hy - 5 * s), max(2, int(2.4 * s)))
    pygame.draw.circle(surf, dark, (hx + facing * 12 * s, hy - 5 * s), max(1, int(1.5 * s)))


def _draw_helmet(surf, head, hr, s, item_id):
    """Helmet / cowl worn from the helmet equipment slot."""
    light, mid, dark, accent = _metal_palette(item_id) or ((188, 192, 198), (148, 152, 160), (98, 102, 110), (220, 50, 50))
    leather = bool(item_id and "leather" in item_id)
    if leather:
        # soft leather cowl / hood
        _poly(surf, mid, [
            (head[0] - hr * 1.05, head[1] + hr * 0.35),
            (head[0] - hr * 0.55, head[1] - hr * 0.95),
            (head[0] + hr * 0.55, head[1] - hr * 1.0),
            (head[0] + hr * 1.05, head[1] + hr * 0.35),
            (head[0] + hr * 0.85, head[1] + hr * 0.95),
            (head[0] - hr * 0.85, head[1] + hr * 0.95),
        ], dark, 1)
        _poly(surf, light, [
            (head[0] - hr * 0.4, head[1] - hr * 0.7),
            (head[0], head[1] - hr * 1.05),
            (head[0] + hr * 0.45, head[1] - hr * 0.7),
            (head[0], head[1] - hr * 0.35),
        ])
        # open face
        pygame.draw.ellipse(surf, (235, 195, 150),
                            (head[0] - hr * 0.45, head[1] - hr * 0.05, hr * 0.9, hr * 0.85))
        pygame.draw.circle(surf, (30, 28, 28), (head[0] - hr * 0.18, head[1] + hr * 0.25), max(1, int(hr * 0.1)))
        pygame.draw.circle(surf, (30, 28, 28), (head[0] + hr * 0.18, head[1] + hr * 0.25), max(1, int(hr * 0.1)))
        return

    # metal dome
    _poly(surf, light, [
        (head[0] - hr * 0.95, head[1] + hr * 0.15),
        (head[0] - hr * 0.5, head[1] - hr * 0.95),
        (head[0] + hr * 0.55, head[1] - hr * 1.0),
        (head[0] + hr * 1.0, head[1] + hr * 0.1),
        (head[0] + hr * 0.85, head[1] + hr * 0.85),
        (head[0] - hr * 0.85, head[1] + hr * 0.85),
    ], dark, 1)
    # right facet darker
    _poly(surf, mid, [
        (head[0], head[1] - hr * 0.9),
        (head[0] + hr * 0.55, head[1] - hr * 1.0),
        (head[0] + hr * 1.0, head[1] + hr * 0.1),
        (head[0] + hr * 0.85, head[1] + hr * 0.85),
        (head[0], head[1] + hr * 0.7),
    ])
    # visor band with eye glow
    pygame.draw.rect(surf, dark, (head[0] - hr * 0.85, head[1] - hr * 0.15, hr * 1.7, hr * 0.55))
    for i in (-0.4, 0, 0.4):
        pygame.draw.line(surf, (20, 18, 18),
                         (head[0] + i * hr, head[1] - hr * 0.1),
                         (head[0] + i * hr, head[1] + hr * 0.35), max(1, int(1.2 * s)))
    for ox in (-0.35, 0.35):
        pygame.draw.ellipse(surf, (40, 55, 70),
                            (head[0] + ox * hr - hr * 0.18, head[1] - hr * 0.05, hr * 0.36, hr * 0.28))
        pygame.draw.circle(surf, (90, 200, 255), (head[0] + ox * hr, head[1] + hr * 0.08), max(1, int(hr * 0.1)))
    # red plume on steel / full metal helms
    if item_id and ("steel" in item_id or "full" in item_id):
        plume = (200, 35, 40)
        plume_d = (140, 20, 25)
        _poly(surf, plume, [
            (head[0] - hr * 0.15, head[1] - hr * 0.85),
            (head[0] + hr * 0.1, head[1] - hr * 1.85),
            (head[0] + hr * 0.55, head[1] - hr * 1.55),
            (head[0] + hr * 0.35, head[1] - hr * 0.75),
        ], plume_d, 1)
        _poly(surf, _shade(plume, 30), [
            (head[0], head[1] - hr * 0.9),
            (head[0] + hr * 0.15, head[1] - hr * 1.6),
            (head[0] + hr * 0.35, head[1] - hr * 1.35),
        ])


def draw_humanoid_detailed(surf, cx, cy, tile, body_color=(70,120,210),
                           skin_color=(235,195,150), hair_color=(70,45,30),
                           weapon=None, shield=False, moving=False, t=0.0,
                           robe=False, facing=1, equipment=None, attacking=0.0):
    """Classic low-poly adventurer; equipment drives plate / leather / weapons.

    attacking: 0 idle, or 0..1 swing progress for a visible weapon strike.
    """
    equipment = equipment or {}
    body_id = equipment.get("body")
    legs_id = equipment.get("legs")
    shield_id = equipment.get("shield")
    weapon_id = equipment.get("weapon")
    helmet_id = equipment.get("helmet")
    if weapon_id and not weapon:
        if "dagger" in weapon_id:
            weapon = "dagger"
        elif "pickaxe" in weapon_id:
            weapon = "pickaxe"
        elif "battleaxe" in weapon_id or "cleaver" in weapon_id:
            weapon = "battleaxe"
        elif "axe" in weapon_id:
            weapon = "axe"
        elif "sword" in weapon_id:
            weapon = "sword"
        else:
            weapon = "sword"
    if shield_id:
        shield = True

    leather_body = bool(body_id and "leather" in body_id)
    chain_body = bool(body_id and ("chain" in body_id or body_id == "goblin_mail"))
    plate_body = bool(body_id and not leather_body and not chain_body and (
        "plate" in body_id or body_id.endswith("_body")
    ))
    leather_legs = bool(legs_id and ("leather" in legs_id or "chaps" in legs_id))
    chain_legs = bool(legs_id and "chain" in legs_id)
    plate_legs = bool(legs_id and not leather_legs and not chain_legs and (
        "plate" in legs_id or any(m in legs_id for m in ("bronze", "iron", "steel"))
    ))

    s = tile / 32.0 * ART_SCALE
    bob = math.sin(t * 6) * 1.0 * s if moving else 0
    swing = math.sin(t * 10) * 2.2 * s if moving else 0
    feet = cy + 12 * s + bob
    dark = _shade(body_color, -45)
    mid = _shade(body_color, -22)
    light = _shade(body_color, 28)
    outline = (28, 24, 22)
    gold = (230, 200, 55)

    # metal / leather palettes for armour
    if plate_body or chain_body:
        m_light, m_mid, m_dark, _ = _metal_palette(body_id)
    elif leather_body:
        m_light, m_mid, m_dark, _ = _metal_palette(body_id)
    else:
        m_light, m_mid, m_dark = light, mid, dark

    if plate_legs or chain_legs:
        p_light, p_mid, p_dark, _ = _metal_palette(legs_id)
        pants, pants_d = p_mid, p_dark
    elif leather_legs:
        p_light, p_mid, p_dark, _ = _metal_palette(legs_id)
        pants, pants_d = p_mid, p_dark
    else:
        pants, pants_d = (72, 74, 82), (48, 50, 58)
        p_light, p_mid, p_dark = light, mid, dark

    boots = (92, 62, 38)
    boots_d = (64, 42, 24)
    shirt = (242, 242, 246)

    # ground shadow
    sh = pygame.Surface((int(20 * s), int(7 * s)), pygame.SRCALPHA)
    pygame.draw.ellipse(sh, (0, 0, 0, 95), sh.get_rect())
    surf.blit(sh, (cx - 10 * s, feet + 1 * s))

    # --- boots ---
    for side, sw in ((-1, -swing * 0.4), (1, swing * 0.4)):
        bx = cx + side * 3.2 * s
        by = feet - 2.5 * s + sw
        _poly(surf, boots, [
            (bx - 2.6 * s, by), (bx + 2.8 * s, by),
            (bx + 3.2 * s, by + 3.2 * s), (bx - 2.2 * s, by + 3.2 * s),
        ], outline, 1)
        pygame.draw.line(surf, boots_d, (bx - 1.5 * s, by + 1.5 * s), (bx + 2 * s, by + 1.5 * s), 1)

    # --- legs ---
    for side, sw in ((-1, -swing), (1, swing)):
        px = cx + side * 2.8 * s
        top = feet - 9.5 * s + sw * 0.15
        col = pants if side < 0 else pants_d
        _poly(surf, col, [
            (px - 3.2 * s, top), (px + 3.2 * s, top),
            (px + 2.6 * s, feet - 2.2 * s + sw), (px - 2.4 * s, feet - 2.2 * s + sw),
        ], outline, 1)
        if plate_legs:
            # greave ridge
            pygame.draw.line(surf, p_light if side < 0 else p_mid,
                             (px - 1 * s, top + 1 * s), (px - 0.5 * s, feet - 3 * s + sw), 1)
        elif chain_legs:
            # chainmail links on thighs
            for i in range(3):
                yy = top + 2 * s + i * 2.2 * s
                pygame.draw.circle(surf, p_light if side < 0 else p_mid,
                                   (px, yy), max(1, int(1.1 * s)), 1)
    pygame.draw.line(surf, pants_d, (cx, feet - 9 * s), (cx, feet - 5 * s), max(1, int(s)))

    body_top = cy - 4 * s + bob
    body_bot = body_top + 12 * s

    if robe:
        _poly(surf, body_color, [
            (cx - 6.5 * s, body_top), (cx + 6.5 * s, body_top),
            (cx + 10 * s, body_bot + 2 * s), (cx - 10 * s, body_bot + 2 * s),
        ], dark, max(1, int(s)))
        pygame.draw.line(surf, light, (cx - 4 * s, body_top + 2 * s), (cx - 4 * s, body_bot), 1)
    elif plate_body:
        # full plate chest under tabard
        _poly(surf, m_light, [
            (cx - 7 * s, body_top + 1 * s), (cx - 0.3 * s, body_top),
            (cx - 0.3 * s, body_bot), (cx - 7.5 * s, body_bot - 1 * s),
        ])
        _poly(surf, m_mid, [
            (cx - 0.3 * s, body_top), (cx + 7 * s, body_top + 1 * s),
            (cx + 7.5 * s, body_bot - 1 * s), (cx - 0.3 * s, body_bot),
        ])
        # white tabard over plate (iron/steel) / bronze ridge
        if "iron" in body_id or "steel" in body_id:
            tabard = shirt
            _poly(surf, tabard, [
                (cx - 5.5 * s, body_top + 0.5 * s), (cx + 5.5 * s, body_top + 0.5 * s),
                (cx + 6 * s, body_bot + 1 * s), (cx - 6 * s, body_bot + 1 * s),
            ], (180, 180, 185), 1)
            # yellow 4-point star
            star_y = body_top + 5.5 * s
            star = gold
            _poly(surf, star, [
                (cx, star_y - 3.2 * s), (cx + 0.7 * s, star_y - 0.7 * s),
                (cx + 3.2 * s, star_y), (cx + 0.7 * s, star_y + 0.7 * s),
                (cx, star_y + 3.2 * s), (cx - 0.7 * s, star_y + 0.7 * s),
                (cx - 3.2 * s, star_y), (cx - 0.7 * s, star_y - 0.7 * s),
            ])
            # belt
            pygame.draw.rect(surf, (140, 100, 45), (cx - 5.5 * s, body_bot - 3.5 * s, 11 * s, 1.8 * s))
            pygame.draw.circle(surf, gold, (cx, body_bot - 2.6 * s), max(1, int(1.1 * s)))
        else:
            # bronze plate: metal breastplate with ridge
            pygame.draw.line(surf, _shade(m_light, 20), (cx, body_top + 1 * s), (cx, body_bot - 2 * s), max(1, int(s)))
            pygame.draw.rect(surf, (120, 80, 40), (cx - 5 * s, body_bot - 3.5 * s, 10 * s, 1.6 * s))
        # pauldrons
        for side in (-1, 1):
            px = cx + side * 7.5 * s
            col = m_light if side < 0 else m_mid
            _poly(surf, col, [
                (px - side * 1 * s, body_top + 0.5 * s),
                (px + side * 4 * s, body_top + 1.5 * s),
                (px + side * 3.5 * s, body_top + 5 * s),
                (px - side * 0.5 * s, body_top + 4 * s),
            ], m_dark, 1)
    elif chain_body:
        # chainmail — tighter torso with link texture, no heavy pauldrons
        _poly(surf, m_mid, [
            (cx - 6.5 * s, body_top + 1.5 * s), (cx - 0.4 * s, body_top + 0.5 * s),
            (cx - 0.4 * s, body_bot), (cx - 7 * s, body_bot - 0.5 * s),
        ])
        _poly(surf, m_dark, [
            (cx - 0.4 * s, body_top + 0.5 * s), (cx + 6.5 * s, body_top + 1.5 * s),
            (cx + 7 * s, body_bot - 0.5 * s), (cx - 0.4 * s, body_bot),
        ])
        for row in range(5):
            yy = body_top + 2.5 * s + row * 1.8 * s
            for col_i in range(-2, 3):
                ox = col_i * 2.2 * s + (row % 2) * 1.1 * s
                pygame.draw.circle(surf, m_light, (cx + ox, yy), max(1, int(1.0 * s)), 1)
        pygame.draw.rect(surf, (90, 70, 45), (cx - 5 * s, body_bot - 2.8 * s, 10 * s, 1.4 * s))
    elif leather_body:
        _poly(surf, m_light, [
            (cx - 7 * s, body_top + 1.5 * s), (cx - 0.5 * s, body_top),
            (cx - 0.5 * s, body_bot), (cx - 7.5 * s, body_bot - 1 * s),
        ])
        _poly(surf, m_mid, [
            (cx - 0.5 * s, body_top), (cx + 7 * s, body_top + 1.5 * s),
            (cx + 7.5 * s, body_bot - 1 * s), (cx - 0.5 * s, body_bot),
        ])
        pygame.draw.line(surf, m_dark, (cx - 5 * s, body_top + 4 * s), (cx + 5 * s, body_top + 4 * s), 1)
        pygame.draw.rect(surf, (90, 60, 35), (cx - 5 * s, body_bot - 3 * s, 10 * s, 1.5 * s))
    else:
        # default jacket
        _poly(surf, light, [
            (cx - 7 * s, body_top + 1.5 * s), (cx - 0.5 * s, body_top),
            (cx - 0.5 * s, body_bot), (cx - 7.5 * s, body_bot - 1 * s),
        ])
        _poly(surf, mid, [
            (cx - 0.5 * s, body_top), (cx + 7 * s, body_top + 1.5 * s),
            (cx + 7.5 * s, body_bot - 1 * s), (cx - 0.5 * s, body_bot),
        ])
        _poly(surf, shirt, [
            (cx - 1.8 * s, body_top + 0.5 * s), (cx + 1.8 * s, body_top + 0.5 * s),
            (cx, body_top + 7 * s),
        ])
        _poly(surf, dark, [
            (cx - 6.5 * s, body_top + 0.2 * s), (cx - 1.5 * s, body_top - 0.5 * s),
            (cx - 0.8 * s, body_top + 3 * s), (cx - 5.5 * s, body_top + 4 * s),
        ])
        _poly(surf, dark, [
            (cx + 1.5 * s, body_top - 0.5 * s), (cx + 6.5 * s, body_top + 0.2 * s),
            (cx + 5.5 * s, body_top + 4 * s), (cx + 0.8 * s, body_top + 3 * s),
        ])
        _poly(surf, dark, [
            (cx - 7 * s, body_top + 1.5 * s), (cx - 0.5 * s, body_top),
            (cx + 7 * s, body_top + 1.5 * s), (cx + 7.5 * s, body_bot - 1 * s),
            (cx - 7.5 * s, body_bot - 1 * s),
        ], outline, max(1, int(s)))

    # --- arms ---
    arm_y = body_top + 3.5 * s
    atk = max(0.0, min(1.0, float(attacking or 0)))
    # Right-arm lunge during a swing
    atk_ox = facing * (math.sin(atk * math.pi) * 7 * s) if atk else 0
    atk_oy = (-math.sin(atk * math.pi) * 5 * s) if atk else 0
    if plate_body:
        # armored arms
        _poly(surf, m_mid, [
            (cx - 7 * s, arm_y), (cx - 5 * s, arm_y + 1.5 * s),
            (cx - 9.5 * s, arm_y + 7 * s), (cx - 11.5 * s, arm_y + 5.5 * s),
        ], m_dark, 1)
        _poly(surf, m_light, [
            (cx + 7 * s, arm_y), (cx + 5 * s, arm_y + 1.5 * s),
            (cx + 9.5 * s + atk_ox, arm_y + 7 * s + atk_oy),
            (cx + 11.5 * s + atk_ox, arm_y + 5.5 * s + atk_oy),
        ], m_dark, 1)
        # gold gauntlets
        pygame.draw.circle(surf, gold, (cx - 10.8 * s, arm_y + 8 * s), 2.3 * s)
        pygame.draw.circle(surf, _shade(gold, -40), (cx - 10.8 * s, arm_y + 8 * s), 2.3 * s, 1)
        hand = (cx + 10.8 * s + atk_ox, arm_y + 8 * s + atk_oy)
        pygame.draw.circle(surf, gold, hand, 2.3 * s)
        pygame.draw.circle(surf, _shade(gold, -40), hand, 2.3 * s, 1)
    else:
        arm_col_l = m_mid if (leather_body or chain_body) else mid
        arm_col_r = m_light if (leather_body or chain_body) else light
        cuff = m_dark if (leather_body or chain_body) else dark
        _poly(surf, arm_col_l, [
            (cx - 7 * s, arm_y), (cx - 5.5 * s, arm_y + 1.5 * s),
            (cx - 9.5 * s, arm_y + 7 * s), (cx - 11 * s, arm_y + 5.5 * s),
        ], outline, 1)
        pygame.draw.rect(surf, cuff, (cx - 11.2 * s, arm_y + 5.2 * s, 3.2 * s, 2.2 * s))
        pygame.draw.circle(surf, skin_color, (cx - 10.5 * s, arm_y + 8.2 * s), 2.0 * s)
        _poly(surf, arm_col_r, [
            (cx + 7 * s, arm_y), (cx + 5.5 * s, arm_y + 1.5 * s),
            (cx + 9.5 * s + atk_ox, arm_y + 7 * s + atk_oy),
            (cx + 11 * s + atk_ox, arm_y + 5.5 * s + atk_oy),
        ], outline, 1)
        pygame.draw.rect(surf, cuff, (cx + 8.2 * s + atk_ox, arm_y + 5.2 * s + atk_oy, 3.2 * s, 2.2 * s))
        hand = (cx + 10.5 * s + atk_ox, arm_y + 8.2 * s + atk_oy)
        pygame.draw.circle(surf, skin_color, hand, 2.0 * s)

    # shield behind / beside left arm
    if shield:
        _draw_shield(surf, cx - 11 * s, body_top + 5 * s, s, shield_id or "iron_shield")

    # weapon in right hand
    if weapon:
        hx, hy = hand
        if weapon == "sword":
            _draw_sword(surf, hx, hy, s, facing, weapon_id, swing=atk)
        elif weapon == "dagger":
            _draw_dagger(surf, hx, hy, s, facing, weapon_id)
        elif weapon == "battleaxe":
            _draw_battleaxe(surf, hx, hy, s, facing, weapon_id, swing=atk)
        elif weapon == "axe":
            _draw_axe(surf, hx, hy, s, facing, weapon_id)
        elif weapon == "pickaxe":
            _draw_pickaxe(surf, hx, hy, s, facing, weapon_id)
        elif weapon == "bow":
            pygame.draw.arc(surf, (145, 95, 55),
                            (hx - 4 * s, hy - 12 * s, 12 * s, 18 * s),
                            -math.pi / 2, math.pi / 2, max(1, int(s)))
        elif weapon == "staff":
            pygame.draw.line(surf, (105, 72, 45), (hx, hy),
                             (hx + facing * 2 * s, hy - 17 * s), max(2, int(2 * s)))
            pygame.draw.circle(surf, (120, 190, 225),
                               (hx + facing * 2 * s, hy - 18 * s), max(2, int(2 * s)))

    # --- head ---
    head = (cx + 0.4 * s * facing, cy - 11 * s + bob)
    hr = 5.8 * s
    if helmet_id:
        _draw_helmet(surf, head, hr, s, helmet_id)
    else:
        # neck
        pygame.draw.rect(surf, _shade(skin_color, -15),
                         (head[0] - hr * 0.28, head[1] + hr * 0.55, hr * 0.56, hr * 0.45))
        # head facets
        _poly(surf, _shade(skin_color, 10), [
            (head[0] - hr * 0.85, head[1] - hr * 0.2),
            (head[0] - hr * 0.15, head[1] - hr),
            (head[0] - hr * 0.1, head[1] + hr * 0.75),
            (head[0] - hr * 0.9, head[1] + hr * 0.45),
        ])
        _poly(surf, skin_color, [
            (head[0] - hr * 0.15, head[1] - hr),
            (head[0] + hr * 0.85, head[1] - hr * 0.25),
            (head[0] + hr * 0.75, head[1] + hr * 0.55),
            (head[0] - hr * 0.1, head[1] + hr * 0.75),
        ], outline, 1)
        # hair cap (keeps fringe above the eyes)
        hair_dark = _shade(hair_color, -25)
        _poly(surf, hair_color, [
            (head[0] - hr * 0.95, head[1] - hr * 0.05),
            (head[0] - hr * 0.55, head[1] - hr * 1.1),
            (head[0] + hr * 0.2, head[1] - hr * 1.2),
            (head[0] + hr * 0.95, head[1] - hr * 0.25),
            (head[0] + hr * 0.75, head[1] + hr * 0.05),
            (head[0] - hr * 0.75, head[1] + hr * 0.05),
        ], hair_dark, 1)
        # short bangs — stop above the eyebrows / eyes
        bangs = [
            (head[0] - hr * 0.7, head[1] - hr * 0.55, head[0] - hr * 0.5, head[1] - hr * 0.28),
            (head[0] - hr * 0.3, head[1] - hr * 0.65, head[0] - hr * 0.1, head[1] - hr * 0.32),
            (head[0] + hr * 0.05, head[1] - hr * 0.62, head[0] + hr * 0.22, head[1] - hr * 0.30),
            (head[0] + hr * 0.4, head[1] - hr * 0.55, head[0] + hr * 0.55, head[1] - hr * 0.28),
        ]
        for x0, y0, x1, y1 in bangs:
            _poly(surf, hair_color, [
                (x0, y0), (x1, y0 - 0.25 * s), (x1 + 0.4 * s, y1), (x0 - 0.2 * s, y1 - 0.1 * s),
            ])
        _draw_character_face(surf, head, hr, s, skin_color, hair_color, facing=facing)

    # mitten fingers on unarmored hands
    if not plate_body:
        for hx, hy in ((cx - 10.5 * s, arm_y + 8.2 * s), hand):
            for i, fox in enumerate((-0.8, 0.0, 0.8)):
                pygame.draw.circle(surf, _shade(skin_color, -10),
                                   (hx + fox * s, hy + 1.2 * s), max(1, int(0.7 * s)))


def draw_orc(surf, cx, cy, tile, t, hurt=False):
    """Broad, asymmetric brute silhouette distinct from the goblin."""
    s = tile/32.0 * ART_SCALE
    skin = (175,55,45) if hurt else (83,116,65)
    skin_d = _shade(skin, -30)
    dark = (53,68,43)
    pygame.draw.ellipse(surf, (25,25,25,100),
                        (cx-11*s, cy+10*s, 22*s, 5*s))
    pygame.draw.rect(surf, dark, (cx-9*s, cy-2*s, 18*s, 14*s),
                     border_radius=max(1,int(3*s)))
    head = (cx, cy-8*s)
    pygame.draw.circle(surf, skin, head, 8*s)
    pygame.draw.circle(surf, _shade(skin, 25), (head[0]-2*s, head[1]-2*s), 3*s)
    _poly(surf, skin, [(cx-7*s,cy-7*s),(cx-13*s,cy-4*s),(cx-7*s,cy-3*s)])
    _poly(surf, skin, [(cx+7*s,cy-7*s),(cx+13*s,cy-4*s),(cx+7*s,cy-3*s)])
    _poly(surf, (235,220,180), [(cx-4*s,cy-4*s),(cx-2*s,cy-1*s),(cx-1*s,cy-5*s)])
    _poly(surf, (235,220,180), [(cx+4*s,cy-4*s),(cx+2*s,cy-1*s),(cx+1*s,cy-5*s)])
    for ox in (-3, 3):
        pygame.draw.ellipse(surf, (255, 230, 60), (cx+ox*s-1.8*s, cy-10*s, 3.6*s, 3.2*s))
        pygame.draw.circle(surf, (20, 18, 16), (cx+ox*s, cy-8.5*s), max(1, int(s)))
    pygame.draw.line(surf, skin_d, (cx-3*s, cy-5*s), (cx+3*s, cy-5*s), max(2, int(s)))
    pygame.draw.line(surf, (120,82,46), (cx+8*s,cy+2*s),
                     (cx+15*s,cy-12*s), max(2,int(2*s)))
    pygame.draw.line(surf, (185,185,180), (cx+12*s,cy-13*s),
                     (cx+17*s,cy-10*s), max(2,int(2*s)))


def draw_slime(surf, cx, cy, tile, t, hurt=False):
    """Low, wide monster silhouette with translucent-looking highlight bands."""
    s = tile/32.0 * ART_SCALE
    body = (200,70,75) if hurt else (74,160,106)
    hi = (235,225,150) if hurt else (120,210,150)
    bounce = abs(math.sin(t*5))*2*s
    _poly(surf, body, [
        (cx-11*s,cy+8*s), (cx-10*s,cy-1*s-bounce),
        (cx-6*s,cy-8*s-bounce), (cx,cy-11*s-bounce),
        (cx+7*s,cy-7*s-bounce), (cx+10*s,cy+1*s-bounce),
        (cx+11*s,cy+8*s)
    ], (40,80,55), max(1,int(s)))
    pygame.draw.arc(surf, hi,
                    (cx-7*s,cy-7*s-bounce,14*s,10*s),
                    math.pi*1.05, math.pi*1.85, max(1,int(s)))
    pygame.draw.circle(surf, (25,35,30),
                       (cx-3*s,cy-1*s-bounce), max(1,int(s)))
    pygame.draw.circle(surf, (25,35,30),
                       (cx+3*s,cy-1*s-bounce), max(1,int(s)))


def draw_giant(surf, cx, cy, tile, t, hurt=False):
    """Large peaceful humanoid — bigger than an orc, club over shoulder."""
    s = tile / 32.0 * ART_SCALE * 1.25
    bob = math.sin(t * 4) * 0.8 * ART_SCALE
    skin = (175, 55, 45) if hurt else (150, 120, 95)
    skin_d = _shade(skin, -35)
    skin_l = _shade(skin, 25)
    tunic = (90, 70, 55)
    dark = (60, 45, 35)
    hair = (55, 40, 30)
    cy += bob
    pygame.draw.ellipse(surf, (20, 18, 16), (cx - 12 * s, cy + 12 * s, 24 * s, 5 * s))
    pygame.draw.rect(surf, dark, (cx - 7 * s, cy + 4 * s, 5 * s, 10 * s))
    pygame.draw.rect(surf, dark, (cx + 2 * s, cy + 4 * s, 5 * s, 10 * s))
    _poly(surf, tunic, [
        (cx - 10 * s, cy - 4 * s), (cx + 10 * s, cy - 4 * s),
        (cx + 11 * s, cy + 8 * s), (cx - 11 * s, cy + 8 * s),
    ], dark, 1)
    pygame.draw.line(surf, (100, 70, 40), (cx + 9 * s, cy), (cx + 16 * s, cy - 14 * s), max(3, int(3 * s)))
    pygame.draw.circle(surf, (80, 55, 30), (cx + 16 * s, cy - 15 * s), 4 * s)
    head = (cx, cy - 10 * s)
    hr = 7.5 * s
    pygame.draw.circle(surf, skin, head, hr)
    pygame.draw.circle(surf, skin_l, (head[0] - 1.5 * s, head[1] - 1.5 * s), 3 * s)
    pygame.draw.circle(surf, dark, head, hr, 1)
    # hair tuft
    _poly(surf, hair, [
        (head[0] - hr * 0.7, head[1] - hr * 0.3),
        (head[0] - hr * 0.2, head[1] - hr * 1.05),
        (head[0] + hr * 0.5, head[1] - hr * 0.9),
        (head[0] + hr * 0.7, head[1] - hr * 0.2),
    ])
    _draw_character_face(surf, head, hr * 0.85, s, skin, hair, facing=1)


MONSTER_DRAWERS.update({
    "orc": draw_orc,
    "slime": draw_slime,
    "giant": draw_giant,
})


def draw_building(surf, rect, building_type="house", style=0, t=0.0):
    """Dispatch decorative building silhouettes.

    Buildings deliberately overhang their logical footprint, giving the
    world the larger, more readable visual scale of a classic MMORPG.
    """
    cx, cy = rect.center
    w0, h0 = rect.size
    w = w0 * 1.30
    h = h0 * 1.30
    rect = (cx - w/2, cy - h/2, w, h)

    if building_type == "house":
        draw_house(surf, rect, style=style, t=t)
        return

    x, y, w, h = rect
    if building_type == "tower":
        pygame.draw.rect(surf, (110,105,98), (x+w*.2, y+h*.2, w*.6, h*.8))
        _poly(surf, (65,58,57), [
            (x+w*.12,y+h*.22), (x+w*.5,y),
            (x+w*.88,y+h*.22)
        ], (40,36,36), 2)
        for yy in (y+h*.40, y+h*.62):
            pygame.draw.rect(surf, (40,65,80),
                             (x+w*.40, yy, w*.20, h*.11))
    elif building_type == "smithy":
        draw_house(surf, rect, style=1, t=t)
        pygame.draw.rect(surf, (55,48,43),
                         (x+w*.70, y+h*.15, w*.12, h*.25))
        pygame.draw.line(surf, (150,150,150),
                         (x+w*.76, y+h*.10), (x+w*.76, y+h*.18), 2)


def draw_world_object(surf, kind, *args, **kwargs):
    """Single entry point useful to the client renderer."""
    table = {
        "tree": draw_tree_detailed,
        "rock": draw_rock_detailed,
        "water": draw_water_detailed,
        "building": draw_building,
        "humanoid": draw_humanoid_detailed,
        "monster": draw_monster,
        "item": draw_item_icon,
    }
    fn = table.get(kind)
    if fn is None:
        raise ValueError(f"Unknown world object kind: {kind}")
    return fn(surf, *args, **kwargs)



def set_art_scale(scale):
    """Set global sprite scale for the current client.

    Typical values:
      1.35 = modest enlargement
      1.60 = recommended large MMORPG presentation
      1.80 = very chunky / close camera
    """
    global ART_SCALE
    if scale < 0.75 or scale > 3.0:
        raise ValueError("art scale must be between 0.75 and 3.0")
    ART_SCALE = float(scale)


def get_art_scale():
    return ART_SCALE
