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
ART_SCALE = 1.60


def _seeded(x, y, salt=0):
    """Cheap deterministic pseudo-random in [0,1) from a tile position."""
    n = (x * 92821 + y * 68917 + salt * 2311) & 0xFFFFFFFF
    n = (n ^ (n >> 13)) * 1274126177 & 0xFFFFFFFF
    return (n % 10000) / 10000.0


# ---------------------------------------------------------------------------
# Terrain
# ---------------------------------------------------------------------------
def draw_grass(surf, rect, seed_x, seed_y):
    base = (52, 104, 56)
    pygame.draw.rect(surf, base, rect)
    r1 = _seeded(seed_x, seed_y, 1)
    shade = (46, 96, 50) if r1 < 0.5 else (60, 112, 62)
    pygame.draw.rect(surf, shade, rect, 0, border_radius=0)
    pygame.draw.rect(surf, base, rect.inflate(-rect.w * 0.15, -rect.h * 0.15))
    # a few blades of grass
    for i in range(3):
        rx = _seeded(seed_x, seed_y, 10 + i)
        ry = _seeded(seed_x, seed_y, 20 + i)
        bx = rect.x + rx * rect.w
        by = rect.y + ry * rect.h
        pygame.draw.line(surf, (72, 130, 70), (bx, by + 4), (bx, by - 3), 2)


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


def draw_floor(surf, rect, seed_x, seed_y):
    base = (72, 66, 78)
    pygame.draw.rect(surf, base, rect)
    pygame.draw.rect(surf, (60, 55, 66), rect, 1)
    if _seeded(seed_x, seed_y, 3) < 0.15:
        pygame.draw.circle(surf, (52, 48, 58), rect.center, rect.w * 0.15)


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
    bob = math.sin(t * 4) * 2
    cx, cy = rect.center
    cy += bob
    pygame.draw.polygon(surf, (235, 200, 60), [
        (cx, cy - 7), (cx + 7, cy), (cx, cy + 7), (cx - 7, cy)])
    pygame.draw.polygon(surf, (255, 230, 120), [
        (cx, cy - 7), (cx + 7, cy), (cx, cy)], 0)
    pygame.draw.polygon(surf, (140, 110, 20), [
        (cx, cy - 7), (cx + 7, cy), (cx, cy + 7), (cx - 7, cy)], 1)


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
    # hair
    pygame.draw.arc(surf, hair_color, (head_c[0] - head_r, head_c[1] - head_r, head_r * 2, head_r * 2),
                     math.pi * 0.05, math.pi * 0.95, max(2, int(head_r * 0.5)))
    # simple face
    pygame.draw.circle(surf, (30, 30, 30), (head_c[0] - head_r * 0.35, head_c[1] - head_r * 0.05), max(1, int(head_r * 0.12)))
    pygame.draw.circle(surf, (30, 30, 30), (head_c[0] + head_r * 0.35, head_c[1] - head_r * 0.05), max(1, int(head_r * 0.12)))


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
def draw_giant_rat(surf, cx, cy, tile, t, hurt=False):
    scale = tile / 32.0 * ART_SCALE
    bob = math.sin(t * 8) * 1.5 * ART_SCALE
    body_color = (150, 60, 60) if hurt else (120, 108, 100)
    cy += bob
    # tail
    pygame.draw.line(surf, (170, 150, 140), (cx + 8 * scale, cy + 4 * scale), (cx + 16 * scale, cy + 10 * scale), max(1, int(scale)))
    # body
    pygame.draw.ellipse(surf, body_color, (cx - 10 * scale, cy - 6 * scale, 20 * scale, 13 * scale))
    # ears
    pygame.draw.circle(surf, (150, 130, 120), (cx - 6 * scale, cy - 9 * scale), 3 * scale)
    pygame.draw.circle(surf, (150, 130, 120), (cx - 1 * scale, cy - 10 * scale), 3 * scale)
    # head/nose
    pygame.draw.circle(surf, body_color, (cx - 9 * scale, cy - 2 * scale), 5 * scale)
    pygame.draw.circle(surf, (30, 30, 30), (cx - 12 * scale, cy - 2 * scale), max(1, int(scale)))


def draw_goblin(surf, cx, cy, tile, t, hurt=False):
    scale = tile / 32.0 * ART_SCALE
    bob = math.sin(t * 6) * 1.2 * ART_SCALE
    skin = (140, 40, 40) if hurt else (90, 140, 70)
    cy += bob
    # legs
    pygame.draw.rect(surf, (70, 60, 40), (cx - 6 * scale, cy + 4 * scale, 4 * scale, 8 * scale))
    pygame.draw.rect(surf, (70, 60, 40), (cx + 2 * scale, cy + 4 * scale, 4 * scale, 8 * scale))
    # body
    pygame.draw.rect(surf, (80, 70, 50), (cx - 8 * scale, cy - 6 * scale, 16 * scale, 12 * scale), border_radius=2)
    # crude club
    pygame.draw.line(surf, (110, 80, 50), (cx + 8 * scale, cy - 2 * scale), (cx + 14 * scale, cy - 12 * scale), max(2, int(2 * scale)))
    # head
    head_c = (cx, cy - 11 * scale)
    pygame.draw.circle(surf, skin, head_c, 6 * scale)
    # ears (pointed)
    pygame.draw.polygon(surf, skin, [(head_c[0] - 6 * scale, head_c[1]), (head_c[0] - 10 * scale, head_c[1] - 3 * scale), (head_c[0] - 5 * scale, head_c[1] - 3 * scale)])
    pygame.draw.polygon(surf, skin, [(head_c[0] + 6 * scale, head_c[1]), (head_c[0] + 10 * scale, head_c[1] - 3 * scale), (head_c[0] + 5 * scale, head_c[1] - 3 * scale)])
    pygame.draw.circle(surf, (255, 220, 40), (head_c[0] - 2 * scale, head_c[1]), max(1, int(scale)))
    pygame.draw.circle(surf, (255, 220, 40), (head_c[0] + 2 * scale, head_c[1]), max(1, int(scale)))


def draw_skeleton(surf, cx, cy, tile, t, hurt=False):
    scale = tile / 32.0 * ART_SCALE
    bob = math.sin(t * 5) * 1.0 * ART_SCALE
    bone = (200, 70, 70) if hurt else (225, 222, 210)
    cy += bob
    # legs
    pygame.draw.line(surf, bone, (cx - 3 * scale, cy + 2 * scale), (cx - 4 * scale, cy + 12 * scale), max(2, int(2 * scale)))
    pygame.draw.line(surf, bone, (cx + 3 * scale, cy + 2 * scale), (cx + 4 * scale, cy + 12 * scale), max(2, int(2 * scale)))
    # ribcage
    pygame.draw.rect(surf, bone, (cx - 6 * scale, cy - 8 * scale, 12 * scale, 11 * scale), max(1, int(2 * scale)), border_radius=2)
    for i in range(3):
        yy = cy - 6 * scale + i * 3 * scale
        pygame.draw.line(surf, bone, (cx - 5 * scale, yy), (cx + 5 * scale, yy), 1)
    # arms + weapon
    pygame.draw.line(surf, bone, (cx - 6 * scale, cy - 4 * scale), (cx - 10 * scale, cy + 4 * scale), max(1, int(2 * scale)))
    pygame.draw.line(surf, bone, (cx + 6 * scale, cy - 4 * scale), (cx + 11 * scale, cy - 12 * scale), max(1, int(2 * scale)))
    pygame.draw.line(surf, (170, 170, 180), (cx + 8 * scale, cy - 4 * scale), (cx + 13 * scale, cy - 16 * scale), max(2, int(2 * scale)))
    # skull
    head_c = (cx, cy - 12 * scale)
    pygame.draw.circle(surf, bone, head_c, 5 * scale)
    pygame.draw.circle(surf, (30, 30, 30), (head_c[0] - 2 * scale, head_c[1]), max(1, int(scale)))
    pygame.draw.circle(surf, (30, 30, 30), (head_c[0] + 2 * scale, head_c[1]), max(1, int(scale)))
    pygame.draw.line(surf, (30, 30, 30), (head_c[0] - 1.5 * scale, head_c[1] + 3 * scale), (head_c[0] + 1.5 * scale, head_c[1] + 3 * scale), 1)


MONSTER_DRAWERS = {
    "giant_rat": draw_giant_rat,
    "goblin": draw_goblin,
    "skeleton": draw_skeleton,
}


def draw_monster(surf, mtype, cx, cy, tile, t, hurt=False):
    fn = MONSTER_DRAWERS.get(mtype, draw_giant_rat)
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
        blade = (200, 200, 210) if "iron" in item_id else (180, 130, 70)
        pygame.draw.line(surf, blade, (cx - s * 0.2, cy + s * 0.22), (cx + s * 0.22, cy - s * 0.22), max(2, int(s * 0.08)))
        pygame.draw.line(surf, (110, 80, 50), (cx - s * 0.24, cy + s * 0.26), (cx - s * 0.1, cy + s * 0.1), max(2, int(s * 0.09)))
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
        pygame.draw.ellipse(surf, (160, 160, 170), (cx - s * 0.2, cy - s * 0.26, s * 0.4, s * 0.5))
        pygame.draw.ellipse(surf, (100, 100, 110), (cx - s * 0.2, cy - s * 0.26, s * 0.4, s * 0.5), 1)
        return
    if itype == "armor":
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


def draw_rock_detailed(surf, cx, cy, tile, variant=0):
    """Faceted rock with cracks and small ground shadow."""
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
    _poly(surf, (91, 89, 84), world, (39, 38, 36), max(1, int(s)))
    _poly(surf, (126, 123, 113), [
        (cx-6*s, cy-5*s), (cx-1*s, cy-9*s),
        (cx+5*s, cy-5*s), (cx+1*s, cy-2*s)
    ])
    pygame.draw.line(surf, (57, 55, 52),
                     (cx-2*s, cy-2*s), (cx-5*s, cy+4*s), max(1, int(s)))
    pygame.draw.line(surf, (57, 55, 52),
                     (cx-5*s, cy+4*s), (cx-1*s, cy+6*s), max(1, int(s)))


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


def draw_humanoid_detailed(surf, cx, cy, tile, body_color=(70,120,210),
                           skin_color=(235,195,150), hair_color=(70,45,30),
                           weapon=None, shield=False, moving=False, t=0.0,
                           robe=False, facing=1):
    """More readable player/NPC sprite: head, torso, arms, legs and equipment."""
    s = tile / 32.0 * ART_SCALE
    bob = math.sin(t*6)*1.0 if moving else 0
    feet = cy + 11*s + bob
    dark_body = tuple(max(0, c-38) for c in body_color)

    pygame.draw.ellipse(surf, (25,25,27,110),
                        (cx-9*s, feet+1*s, 18*s, 5*s))

    swing = math.sin(t*10)*2*s if moving else 0
    for side, sw in [(-1, -swing), (1, swing)]:
        pygame.draw.rect(surf, (55,52,70),
                         (cx+side*2*s-2*s, feet-8*s+sw, 4*s, 8*s))

    body_top = cy-3*s+bob
    if robe:
        _poly(surf, body_color, [
            (cx-6*s, body_top), (cx+6*s, body_top),
            (cx+9*s, body_top+12*s), (cx-9*s, body_top+12*s)
        ], dark_body, max(1, int(s)))
    else:
        pygame.draw.rect(surf, body_color,
                         (cx-6*s, body_top, 12*s, 11*s),
                         border_radius=max(1, int(2*s)))
        pygame.draw.rect(surf, dark_body,
                         (cx-6*s, body_top, 12*s, 11*s),
                         max(1, int(s)), border_radius=max(1, int(2*s)))

    # arms
    pygame.draw.line(surf, skin_color,
                     (cx-6*s, body_top+3*s), (cx-9*s, body_top+8*s),
                     max(2, int(2*s)))
    pygame.draw.line(surf, skin_color,
                     (cx+6*s, body_top+3*s), (cx+9*s, body_top+8*s),
                     max(2, int(2*s)))

    if shield:
        pygame.draw.ellipse(surf, (155,158,165),
                            (cx-12*s, body_top+2*s, 6*s, 9*s))
        pygame.draw.line(surf, (92,94,100),
                         (cx-12*s, body_top+6.5*s), (cx-6*s, body_top+6.5*s), 1)

    if weapon:
        hand = (cx+9*s, body_top+7*s)
        if weapon == "sword":
            pygame.draw.line(surf, (215,218,225), hand,
                             (hand[0]+facing*8*s, hand[1]-12*s), max(2,int(2*s)))
            pygame.draw.line(surf, (143,99,55), hand,
                             (hand[0]-facing*2*s, hand[1]+3*s),
                             max(2,int(2*s)))
        elif weapon == "axe":
            pygame.draw.line(surf, (126,86,49), hand,
                             (hand[0]+facing*6*s, hand[1]-11*s), max(2,int(2*s)))
            _poly(surf, (178,180,185), [
                (hand[0]+facing*5*s, hand[1]-12*s),
                (hand[0]+facing*13*s, hand[1]-10*s),
                (hand[0]+facing*8*s, hand[1]-4*s)
            ])
        elif weapon == "bow":
            pygame.draw.arc(
                surf, (145,95,55),
                (hand[0]-4*s, hand[1]-11*s, 12*s, 18*s),
                -math.pi/2, math.pi/2, max(1,int(s))
            )
        elif weapon == "staff":
            pygame.draw.line(surf, (105,72,45), hand,
                             (hand[0]+facing*2*s, hand[1]-16*s), max(2,int(2*s)))
            pygame.draw.circle(surf, (120,190,225),
                               (hand[0]+facing*2*s, hand[1]-17*s), max(2,int(2*s)))

    head_r = 5.5*s
    head = (cx, cy-10*s+bob)
    pygame.draw.circle(surf, skin_color, head, head_r)
    # hair cap
    pygame.draw.arc(surf, hair_color,
                    (head[0]-head_r, head[1]-head_r,
                     head_r*2, head_r*2), math.pi, TAU, max(2,int(1.5*s)))
    eye_y = head[1]-0.3*s
    pygame.draw.circle(surf, (28,28,28),
                       (head[0]-1.9*s, eye_y), max(1,int(.65*s)))
    pygame.draw.circle(surf, (28,28,28),
                       (head[0]+1.9*s, eye_y), max(1,int(.65*s)))


def draw_orc(surf, cx, cy, tile, t, hurt=False):
    """Broad, asymmetric brute silhouette distinct from the goblin."""
    s = tile/32.0 * ART_SCALE
    skin = (175,55,45) if hurt else (83,116,65)
    dark = (53,68,43)
    pygame.draw.ellipse(surf, (25,25,25,100),
                        (cx-11*s, cy+10*s, 22*s, 5*s))
    pygame.draw.rect(surf, dark, (cx-9*s, cy-2*s, 18*s, 14*s),
                     border_radius=max(1,int(3*s)))
    pygame.draw.circle(surf, skin, (cx, cy-8*s), 8*s)
    # tusks and heavy ears
    _poly(surf, skin, [(cx-7*s,cy-7*s),(cx-13*s,cy-4*s),(cx-7*s,cy-3*s)])
    _poly(surf, skin, [(cx+7*s,cy-7*s),(cx+13*s,cy-4*s),(cx+7*s,cy-3*s)])
    _poly(surf, (235,220,180), [(cx-4*s,cy-4*s),(cx-2*s,cy-1*s),(cx-1*s,cy-5*s)])
    _poly(surf, (235,220,180), [(cx+4*s,cy-4*s),(cx+2*s,cy-1*s),(cx+1*s,cy-5*s)])
    pygame.draw.circle(surf, (245,210,45), (cx-3*s,cy-9*s), max(1,int(s)))
    pygame.draw.circle(surf, (245,210,45), (cx+3*s,cy-9*s), max(1,int(s)))
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


MONSTER_DRAWERS.update({
    "orc": draw_orc,
    "slime": draw_slime,
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
