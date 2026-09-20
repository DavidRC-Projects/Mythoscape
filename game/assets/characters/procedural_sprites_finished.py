"""
Procedural sprite rendering for the MMORPG client — early-2000s fantasy MMORPG
visual language (chunky low-poly silhouettes, limited palettes, hard shading).

Everything is drawn with pygame primitives (no external image assets).
Scale is centralized via rs_style (TILE vs CHARACTER/OBJECT/MONSTER scales).
"""
import math
import pygame

import rs_style as rs

TAU = math.pi * 2

# Re-export scale knobs so older callers keep working
ART_SCALE = rs.ART_SCALE
TILE_SIZE_DEFAULT = rs.TILE_SIZE


def _shade(color, delta):
    return rs.shade(color, delta)


def _seeded(x, y, salt=0):
    return rs.seeded(x, y, salt)


def _poly(surf, color, pts, outline=None, width=1):
    rs.draw_poly(surf, color, pts, outline if outline is not None else rs.OUTLINE, width)


def _s(tile, kind="character"):
    return rs.unit(tile, kind)


# ---------------------------------------------------------------------------
# Terrain
# ---------------------------------------------------------------------------
def draw_grass(surf, rect, seed_x, seed_y):
    """Subtle procedural grassland — mottles that soft-bridge tile seams."""
    base, dark, light, outline = rs.GRASS_PALETTE
    # World-space base (neighboring tiles share similar value → less grid)
    r_world = _seeded(seed_x // 2, seed_y // 2, 1)
    r1 = _seeded(seed_x, seed_y, 1)
    fill = _shade(base, int((r_world - 0.5) * 6 + (r1 - 0.5) * 4))
    pygame.draw.rect(surf, fill, rect)
    # Soft value patches that can spill toward edges (breaks tile diamonds)
    for i in range(3):
        if _seeded(seed_x, seed_y, 10 + i) < 0.75:
            wash = _shade(fill, 6 if i % 2 == 0 else -7)
            ox = int(rect.w * (-0.15 + 0.9 * _seeded(seed_x, seed_y, 20 + i)))
            oy = int(rect.h * (-0.15 + 0.9 * _seeded(seed_x, seed_y, 30 + i)))
            rw = max(5, int(rect.w * (0.4 + 0.35 * _seeded(seed_x, seed_y, 40 + i))))
            rh = max(4, int(rect.h * (0.35 + 0.3 * _seeded(seed_x, seed_y, 50 + i))))
            pts = rs.irregular_ring(
                rect.x + ox + rw // 2, rect.y + oy + rh // 2,
                rw * 0.55, rh * 0.5, n=6, seed=seed_x * 17 + seed_y + i, jitter=0.25,
            )
            rs.draw_poly(surf, wash, pts, None, 0)
    # Grass blade clusters
    if _seeded(seed_x, seed_y, 40) < 0.48:
        tx = rect.x + int(rect.w * _seeded(seed_x, seed_y, 41))
        ty = rect.y + int(rect.h * (0.45 + 0.4 * _seeded(seed_x, seed_y, 42)))
        blade = _shade(dark, -6)
        lit_blade = _shade(light, -8)
        for j, dx in enumerate((-3, -1, 1, 3)):
            col = lit_blade if j % 2 == 0 else blade
            pygame.draw.line(surf, col, (tx + dx, ty + 4), (tx + dx // 2, ty - 5), 1)
    if _seeded(seed_x, seed_y, 60) < 0.14:
        sx = rect.x + int(rect.w * _seeded(seed_x, seed_y, 61))
        sy = rect.y + int(rect.h * _seeded(seed_x, seed_y, 62))
        pygame.draw.ellipse(surf, _shade(dark, -4), (sx - 4, sy - 1, 8, 3))
    if _seeded(seed_x, seed_y, 50) < 0.11:
        px = rect.x + int(rect.w * _seeded(seed_x, seed_y, 51))
        py = rect.y + int(rect.h * _seeded(seed_x, seed_y, 52))
        pygame.draw.circle(surf, (100, 98, 88), (px, py), 2)
        pygame.draw.circle(surf, (130, 128, 118), (px - 1, py - 1), 1)


def draw_path(surf, rect, seed_x, seed_y):
    """Worn dirt path — irregular edges, footprints, stone flecks."""
    base, dark, light, _ = rs.DIRT_PALETTE
    r1 = _seeded(seed_x, seed_y, 2)
    fill = _shade(base, int((r1 - 0.5) * 14))
    pygame.draw.rect(surf, fill, rect)
    # Soft mottles
    if _seeded(seed_x, seed_y, 4) < 0.6:
        pygame.draw.ellipse(
            surf, _shade(fill, 8),
            (rect.x + rect.w * 0.15, rect.y + rect.h * 0.2, rect.w * 0.5, rect.h * 0.4),
        )
    # Edge wear (darker banks)
    if _seeded(seed_x, seed_y, 3) < 0.65:
        pygame.draw.line(surf, dark, (rect.left, rect.top + 1), (rect.right, rect.top + 1), 1)
        pygame.draw.line(surf, _shade(dark, -10), (rect.left + 1, rect.bottom - 1), (rect.right - 1, rect.bottom - 1), 1)
    for i in range(5):
        rx = _seeded(seed_x, seed_y, 30 + i)
        ry = _seeded(seed_x, seed_y, 40 + i)
        px = int(rect.x + rx * rect.w)
        py = int(rect.y + ry * rect.h)
        col = light if i % 2 else dark
        pygame.draw.circle(surf, col, (px, py), 1 if i < 3 else 2)
    # Footprint wear
    if _seeded(seed_x, seed_y, 55) < 0.28:
        pygame.draw.ellipse(
            surf, _shade(fill, -16),
            (rect.x + rect.w * 0.2, rect.y + rect.h * 0.3, rect.w * 0.5, rect.h * 0.32),
        )
    # Small embedded stones
    if _seeded(seed_x, seed_y, 70) < 0.18:
        px = rect.x + int(rect.w * _seeded(seed_x, seed_y, 71))
        py = rect.y + int(rect.h * _seeded(seed_x, seed_y, 72))
        pygame.draw.circle(surf, (120, 110, 95), (px, py), 2)
        pygame.draw.circle(surf, (150, 140, 120), (px - 1, py - 1), 1)


def draw_floor(surf, rect, seed_x, seed_y, zone=None):
    """Flagstone / plank floor with lit top edge."""
    r0 = _seeded(seed_x, seed_y, 1)
    if zone == "village":
        shades = ((124, 98, 70), (110, 86, 60), (138, 112, 82), (96, 74, 50))
        line = (72, 52, 34)
    elif zone == "dungeon":
        shades = ((64, 58, 72), (52, 46, 60), (74, 66, 84), (42, 38, 50))
        line = (28, 24, 34)
    elif zone == "mine":
        shades = ((82, 74, 64), (70, 62, 54), (96, 86, 74), (56, 50, 44))
        line = (40, 36, 30)
    else:
        shades = ((76, 70, 84), (64, 58, 72), (90, 84, 98), (48, 44, 56))
        line = (34, 30, 40)
    base = shades[int(r0 * 4) % 4]
    hi, mid, sh, _ = rs.material(base)
    pygame.draw.rect(surf, mid, rect)
    # Lit top / left edges
    pygame.draw.line(surf, hi, (rect.left + 1, rect.top + 1), (rect.right - 2, rect.top + 1), 1)
    pygame.draw.line(surf, hi, (rect.left + 1, rect.top + 1), (rect.left + 1, rect.bottom - 2), 1)
    pygame.draw.line(surf, sh, (rect.left + 1, rect.bottom - 1), (rect.right - 1, rect.bottom - 1), 1)
    pygame.draw.rect(surf, line, rect, 1)
    if _seeded(seed_x, seed_y, 3) < 0.18:
        pygame.draw.circle(surf, sh, rect.center, max(1, rect.w // 9))
    if zone == "dungeon" and _seeded(seed_x, seed_y, 11) < 0.14:
        glow = pygame.Surface((rect.w, rect.h), pygame.SRCALPHA)
        pygame.draw.circle(glow, (255, 150, 50, 28), (rect.w // 3, rect.h // 3), rect.w // 2)
        surf.blit(glow, rect.topleft)


def draw_wall(surf, rect, zone, seed_x, seed_y, material=None):
    if zone == "village":
        draw_building_wall(surf, rect, seed_x, seed_y, material=material or "wood")
    elif zone == "mine":
        draw_cave_wall(surf, rect)
    elif zone == "dungeon":
        draw_dungeon_wall(surf, rect, seed_x, seed_y)
    else:
        pygame.draw.rect(surf, (35, 33, 38), rect)
        pygame.draw.rect(surf, (22, 20, 24), rect, 1)


def _fill_brick_face(surf, rect, seed_x=0, seed_y=0, alpha=255):
    """Grey masonry courses with mortar joints and slight brick variation."""
    mortar = (72, 74, 78) if alpha >= 248 else (72, 74, 78, alpha)
    bricks = ((124, 122, 128), (112, 112, 118), (132, 130, 134), (104, 106, 112), (118, 116, 122))
    if alpha >= 248:
        pygame.draw.rect(surf, mortar[:3], rect)
    else:
        pygame.draw.rect(surf, mortar, rect)
    bh = max(5, min(8, rect.h // 4))
    bw = max(9, min(14, rect.w // 2 + 2))
    row = 0
    y = rect.y
    while y < rect.bottom:
        offset = (bw // 2) if (row % 2) else 0
        x = rect.x - offset
        while x < rect.right:
            bx = max(rect.x, x) + 1
            by = y + 1
            rw = min(bw - 2, rect.right - bx - 1)
            rh = min(bh - 2, rect.bottom - by - 1)
            if rw > 2 and rh > 2:
                col = bricks[int(_seeded(seed_x + x, seed_y + y, 20 + row) * len(bricks)) % len(bricks)]
                hi, mid, sh, deep = rs.material(col)
                if alpha < 248:
                    mid = (*mid, alpha)
                    hi = (*hi, alpha)
                    sh = (*sh, alpha)
                pygame.draw.rect(surf, mid, (bx, by, rw, rh))
                pygame.draw.line(surf, hi, (bx, by), (bx + rw - 1, by), 1)
                pygame.draw.line(surf, sh, (bx, by + rh - 1), (bx + rw - 1, by + rh - 1), 1)
                # Tiny chip variation
                if _seeded(seed_x, seed_y, 40 + row + x) < 0.12:
                    pygame.draw.circle(surf, sh, (bx + rw // 2, by + rh // 2), 1)
            x += bw
        y += bh
        row += 1


def _fill_wood_face(surf, rect, seed_x=0, seed_y=0, alpha=255):
    """Vertical timber planks with beams, posts, and grain hints."""
    wood = (148, 112, 70)
    hi, mid, sh, deep = rs.material(wood)
    trim = (78, 52, 30)
    if alpha < 248:
        mid = (*mid, alpha)
        hi = (*hi, alpha)
        sh = (*sh, alpha)
        deep = (*deep, alpha)
        trim = (*trim, alpha)
        found = (90, 84, 76, alpha)
    else:
        found = (90, 84, 76)
    # Foundation strip
    found_h = max(3, rect.h // 6)
    pygame.draw.rect(surf, found, (rect.x, rect.bottom - found_h, rect.w, found_h))
    body = pygame.Rect(rect.x, rect.y, rect.w, rect.h - found_h)
    pygame.draw.rect(surf, mid, body)
    # Vertical planks
    plank_w = max(5, body.w // 5)
    for i, x in enumerate(range(body.x, body.right, plank_w)):
        pw = min(plank_w - 1, body.right - x - 1)
        if pw < 2:
            continue
        shade = hi if i % 2 == 0 else sh
        if alpha < 248 and len(shade) == 3:
            shade = (*shade, alpha)
        pygame.draw.rect(surf, shade if i % 3 != 1 else mid, (x + 1, body.y + 1, max(1, pw - 1), body.h - 2))
        pygame.draw.line(surf, deep, (x + pw, body.y + 1), (x + pw, body.bottom - 2), 1)
        # Grain ticks
        if _seeded(seed_x, seed_y, 60 + i) < 0.55:
            gy = body.y + 3 + int(_seeded(seed_x, seed_y, 70 + i) * max(4, body.h - 8))
            pygame.draw.line(surf, deep, (x + 2, gy), (x + pw - 1, gy), 1)
    # Corner posts
    pw = max(3, body.w // 7)
    pygame.draw.rect(surf, hi, (body.x, body.y, pw, body.h))
    pygame.draw.rect(surf, deep, (body.right - pw, body.y, pw, body.h))
    # Cross beam
    beam_y = body.y + body.h // 2
    pygame.draw.line(surf, trim, (body.x + 1, beam_y), (body.right - 2, beam_y), 2)
    pygame.draw.line(surf, hi, (body.x + 1, beam_y - 1), (body.right - 2, beam_y - 1), 1)
    # Top plate
    pygame.draw.line(surf, trim, (body.x, body.y + 1), (body.right - 1, body.y + 1), 2)


def draw_building_wall(surf, rect, seed_x, seed_y, material="wood"):
    """Village exterior wall tile — grey brick or timber planks."""
    if material == "brick":
        _fill_brick_face(surf, rect, seed_x, seed_y, alpha=255)
        # Darker foundation course
        found_h = max(3, rect.h // 5)
        pygame.draw.rect(surf, (58, 60, 66), (rect.x, rect.bottom - found_h, rect.w, found_h))
        pygame.draw.line(surf, (42, 44, 48), (rect.x, rect.bottom - found_h), (rect.right, rect.bottom - found_h), 1)
        # Lit left / dark right edge for thickness
        pw = max(2, rect.w // 8)
        pygame.draw.rect(surf, (150, 148, 154), (rect.x, rect.y, pw, rect.h - found_h), 1)
        pygame.draw.rect(surf, (70, 72, 78), (rect.right - pw, rect.y, pw, rect.h - found_h), 1)
        pygame.draw.rect(surf, (48, 50, 54), rect, 1)
    else:
        _fill_wood_face(surf, rect, seed_x, seed_y, alpha=255)
        pygame.draw.rect(surf, (52, 36, 22), rect, 2)


def draw_cave_wall(surf, rect):
    base = (78, 72, 68)
    hi, mid, sh, deep = rs.material(base)
    pygame.draw.rect(surf, mid, rect)
    rs.draw_volume(surf, base, [
        (rect.x, rect.bottom), (rect.x + rect.w * 0.35, rect.y + rect.h * 0.15),
        (rect.x + rect.w * 0.7, rect.y + rect.h * 0.4), (rect.right, rect.bottom),
    ], deep, 1)
    pygame.draw.rect(surf, deep, rect, 1)


def draw_dungeon_wall(surf, rect, seed_x, seed_y):
    r0 = _seeded(seed_x, seed_y, 2)
    base = (42, 40, 52) if r0 < 0.5 else (38, 36, 48)
    hi, mid, sh, mortar = rs.material(base)
    mortar = (24, 22, 30)
    pygame.draw.rect(surf, mid, rect)
    brick_h = max(6, rect.h // 2)
    for row, y in enumerate(range(rect.y, rect.bottom, brick_h)):
        offset = (brick_h // 2) if row % 2 else 0
        pygame.draw.line(surf, mortar, (rect.x, y), (rect.right, y), 1)
        for x in range(rect.x - offset, rect.right + brick_h, brick_h):
            pygame.draw.line(surf, mortar, (x, y), (x, min(y + brick_h, rect.bottom)), 1)
            # lit top of each brick
            if y + 1 < rect.bottom:
                pygame.draw.line(surf, hi, (max(rect.x, x) + 1, y + 1), (min(rect.right, x + brick_h) - 1, y + 1), 1)
    pygame.draw.line(surf, hi, (rect.x, rect.y + 1), (rect.right, rect.y + 1), 1)
    pygame.draw.rect(surf, mortar, rect, 1)


def draw_water(surf, rect, t):
    draw_water_detailed(surf, rect, t)


def draw_water_detailed(surf, rect, t, seed_x=0, seed_y=0, shores=None):
    """
    Layered water: depth fill, wave bands, specular, optional shore foam.
    shores: optional dict with keys N/E/S/W True when adjacent tile is land.
    """
    base, dark, light, outline = rs.WATER_PALETTE
    shores = shores or {}
    # Depth: darker toward center of water body, lighter near shore
    shore_count = sum(1 for k in ("N", "E", "S", "W") if shores.get(k))
    depth_shift = -14 if shore_count == 0 else (6 if shore_count >= 2 else -4)
    fill = _shade(base, depth_shift)
    pygame.draw.rect(surf, fill, rect)
    # Soft deep pocket
    pygame.draw.ellipse(
        surf, _shade(fill, -16),
        (rect.x + rect.w * 0.15, rect.y + rect.h * 0.2, rect.w * 0.7, rect.h * 0.55),
    )
    phase = t * 1.8 + seed_x * 0.55 + seed_y * 0.4
    # Animated wave bands (world-space phase so tiles stitch)
    for i in range(4):
        frac = (i + math.sin(phase + i * 0.9) * 0.1) / 4.0
        y = rect.y + int(rect.h * max(0.05, min(0.92, frac)))
        col = _shade(light, -28 + i * 5) if i % 2 else _shade(dark, 8 + i * 3)
        h = max(2, rect.h // 6)
        pygame.draw.rect(surf, col, (rect.x, y, rect.w, h))
    # Diagonal caustic / reflected light
    for i in range(2):
        yy = rect.centery + int(math.sin(phase * 1.3 + i * 2) * rect.h * 0.22)
        pygame.draw.line(
            surf, _shade(light, 10),
            (rect.x, yy), (rect.right, yy + int(math.sin(phase + i) * 3)), 1,
        )
    # Specular sparkle
    if _seeded(seed_x, seed_y, 8) < 0.5:
        gx = rect.x + int(rect.w * (0.2 + 0.55 * abs(math.sin(phase * 0.7))))
        gy = rect.y + int(rect.h * (0.22 + 0.15 * abs(math.cos(phase))))
        pygame.draw.circle(surf, (220, 240, 255), (gx, gy), 1)
        pygame.draw.circle(surf, (255, 255, 255), (gx - 1, gy - 1), 1)
    # Shoreline foam / darker edge against land
    foam = _shade(light, 35)
    edge_d = _shade(dark, -10)
    if shores.get("N"):
        pygame.draw.line(surf, edge_d, (rect.left, rect.top + 1), (rect.right, rect.top + 1), 2)
        for i in range(3):
            fx = rect.x + int(rect.w * (0.15 + 0.3 * i + 0.05 * math.sin(phase + i)))
            pygame.draw.circle(surf, foam, (fx, rect.top + 3), 2)
    if shores.get("S"):
        pygame.draw.line(surf, edge_d, (rect.left, rect.bottom - 2), (rect.right, rect.bottom - 2), 2)
        for i in range(2):
            fx = rect.x + int(rect.w * (0.25 + 0.35 * i))
            pygame.draw.circle(surf, foam, (fx, rect.bottom - 4), 2)
    if shores.get("W"):
        pygame.draw.line(surf, edge_d, (rect.left + 1, rect.top), (rect.left + 1, rect.bottom), 2)
    if shores.get("E"):
        pygame.draw.line(surf, edge_d, (rect.right - 2, rect.top), (rect.right - 2, rect.bottom), 2)


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


def draw_ground_loot_pad(surf, rect, t):
    """Soft pad under non-coin ground loot (no solid black box)."""
    bob = math.sin(t * 3.5 + rect.x * 0.1) * 1.2
    pad = rect.inflate(4, 4)
    pad.y += int(bob)
    shadow = pygame.Surface((pad.w, pad.h), pygame.SRCALPHA)
    pygame.draw.ellipse(shadow, (0, 0, 0, 90), (2, pad.h - 10, pad.w - 4, 9))
    pygame.draw.ellipse(shadow, (40, 36, 28, 140), (4, 4, pad.w - 8, pad.h - 10))
    surf.blit(shadow, pad.topleft)
    return pygame.Rect(pad.x + 4, pad.y + 2, pad.w - 8, pad.h - 10)


# ---------------------------------------------------------------------------
# Characters (players + humanoid NPCs)
# ---------------------------------------------------------------------------
def draw_humanoid(surf, cx, cy, tile, body_color, skin_color, hair_color,
                   weapon=None, shield=False, moving=False, t=0.0, robe=False):
    scale = _s(tile, 'monster')
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
    """Low quadruped: haunch, long snout, pink ears, whip tail."""
    s = _s(tile, "monster") * 0.95
    bob = math.sin(t * 7) * 0.6
    body = (150, 55, 50) if hurt else (118, 112, 108)
    hi, mid, sh, deep = rs.material(body)
    pink = (210, 140, 150)
    cy += bob
    atk = max(0.0, min(1.0, float(attacking or 0)))
    lunge = math.sin(atk * math.pi) * 5 * s
    rs.draw_cast_shadow(surf, cx, cy + 9 * s, 14 * s, 3.5 * s, 110)
    # Hind haunch
    rs.draw_volume(surf, body, [
        (cx - 12 * s, cy + 2 * s), (cx - 4 * s, cy - 4 * s),
        (cx + 2 * s, cy - 2 * s), (cx + 1 * s, cy + 7 * s),
        (cx - 10 * s, cy + 8 * s),
    ], deep, 1)
    # Body barrel
    rs.draw_volume(surf, body, [
        (cx - 6 * s, cy + 1 * s), (cx + 8 * s + lunge * 0.3, cy - 3 * s),
        (cx + 12 * s + lunge, cy + 1 * s), (cx + 8 * s, cy + 7 * s),
        (cx - 4 * s, cy + 7 * s),
    ], deep, 1)
    # Legs
    for ox, oy in ((-8, 6), (-3, 7), (4, 6), (9, 5)):
        pygame.draw.line(surf, sh, (cx + ox * s, cy + oy * s), (cx + ox * s + 1 * s, cy + 10 * s), max(2, int(2.2 * s)))
    # Head / snout
    head = (cx + 11 * s + lunge, cy - 1 * s)
    rs.draw_volume(surf, body, [
        (head[0] - 4 * s, head[1] + 2 * s), (head[0] - 2 * s, head[1] - 3 * s),
        (head[0] + 6 * s, head[1] - 1 * s), (head[0] + 7 * s, head[1] + 1.5 * s),
        (head[0] + 2 * s, head[1] + 3 * s),
    ], deep, 1)
    pygame.draw.circle(surf, (30, 28, 26), (int(head[0] + 1 * s), int(head[1] - 1 * s)), max(1, int(0.9 * s)))
    pygame.draw.circle(surf, pink, (int(head[0] + 6.5 * s), int(head[1])), max(1, int(1.1 * s)))
    # Ears
    for ox in (-1.5, 2.5):
        rs.draw_poly(surf, pink, [
            (head[0] + ox * s, head[1] - 2 * s),
            (head[0] + ox * s - 2 * s, head[1] - 6 * s),
            (head[0] + ox * s + 2 * s, head[1] - 5.5 * s),
        ], deep, 1)
        pygame.draw.circle(surf, (180, 100, 120), (int(head[0] + ox * s), int(head[1] - 4.5 * s)), max(1, int(1.2 * s)))
    # Tail
    pygame.draw.lines(surf, sh, False, [
        (cx - 11 * s, cy + 3 * s), (cx - 16 * s, cy - 2 * s), (cx - 18 * s, cy + 4 * s),
    ], max(2, int(1.8 * s)))


def draw_skeleton(surf, cx, cy, tile, t, hurt=False, attacking=0.0):
    """Thin bone frame: ribs, joints, skull with sockets."""
    s = _s(tile, "monster")
    bob = math.sin(t * 5) * 0.8
    bone = (200, 70, 70) if hurt else (228, 220, 200)
    hi, mid, sh, deep = rs.material(bone)
    cy += bob
    atk = max(0.0, min(1.0, float(attacking or 0)))
    lunge = math.sin(atk * math.pi) * 7 * s
    rs.draw_cast_shadow(surf, cx, cy + 13 * s, 9 * s, 3 * s, 100)
    # Legs with joint knobs
    for side in (-1, 1):
        hip = (cx + side * 3.2 * s, cy + 1 * s)
        knee = (cx + side * 4.5 * s, cy + 7 * s)
        foot = (cx + side * 5.2 * s, cy + 13 * s)
        rs.draw_volume_limb(surf, *hip, *knee, 1.1 * s, bone, deep)
        rs.draw_volume_limb(surf, *knee, *foot, 0.95 * s, bone, deep)
        pygame.draw.circle(surf, mid, (int(knee[0]), int(knee[1])), max(2, int(1.6 * s)))
        pygame.draw.circle(surf, sh, (int(foot[0]), int(foot[1])), max(2, int(1.8 * s)))
    # Pelvis + spine
    pygame.draw.line(surf, mid, (cx - 5 * s, cy + 1 * s), (cx + 5 * s, cy + 1 * s), max(3, int(2.8 * s)))
    pygame.draw.line(surf, mid, (cx, cy + 1 * s), (cx, cy - 9 * s), max(3, int(2.6 * s)))
    # Ribs
    for i in range(4):
        yy = cy - 7.5 * s + i * 2.0 * s
        w = 6.2 * s - i * 0.35 * s
        pygame.draw.arc(surf, mid, (cx - w, yy - 1.2 * s, w * 2, 3.5 * s), 0.15, math.pi - 0.15, max(2, int(1.6 * s)))
    # Arms + sword
    pygame.draw.line(surf, mid, (cx - 4.5 * s, cy - 6 * s), (cx - 11 * s, cy + 2 * s), max(2, int(2.2 * s)))
    hand = (cx + 11 * s + lunge, cy - 1 * s - lunge * 0.3)
    pygame.draw.line(surf, mid, (cx + 4.5 * s, cy - 6 * s), hand, max(2, int(2.2 * s)))
    tip = (hand[0] + 7 * s + lunge * 0.4, hand[1] - 18 * s)
    rs.draw_volume(surf, (170, 175, 185), [
        hand, (hand[0] + 2 * s, hand[1] - 1 * s), tip, (hand[0] - 1 * s, hand[1] - 2 * s),
    ], deep, 1)
    pygame.draw.line(surf, (100, 70, 40), (hand[0] - 3 * s, hand[1] + 1 * s), (hand[0] + 3 * s, hand[1] + 2 * s), max(2, int(2.4 * s)))
    # Skull
    head = (cx, cy - 12 * s)
    rs.draw_volume(surf, bone, [
        (head[0] - 4.5 * s, head[1] + 1 * s), (head[0] - 4 * s, head[1] - 3.5 * s),
        (head[0], head[1] - 5.2 * s), (head[0] + 4 * s, head[1] - 3.5 * s),
        (head[0] + 4.5 * s, head[1] + 1 * s), (head[0] + 2 * s, head[1] + 3.2 * s),
        (head[0] - 2 * s, head[1] + 3.2 * s),
    ], deep, 1)
    for ox in (-1.8, 1.8):
        pygame.draw.ellipse(surf, (18, 16, 14), (head[0] + ox * s - 1.4 * s, head[1] - 1.6 * s, 2.8 * s, 3.0 * s))
        pygame.draw.circle(surf, (50, 170, 70), (int(head[0] + ox * s), int(head[1] - 0.4 * s)), max(1, int(0.55 * s)))
    # Jaw teeth
    pygame.draw.rect(surf, sh, (head[0] - 2.4 * s, head[1] + 2.4 * s, 4.8 * s, 1.5 * s))
    for i in range(-2, 3):
        pygame.draw.line(surf, deep, (head[0] + i * 0.9 * s, head[1] + 2.4 * s), (head[0] + i * 0.9 * s, head[1] + 3.8 * s), 1)


def draw_goblin(surf, cx, cy, tile, t, hurt=False, attacking=0.0):
    """Hunched long-armed goblin — angular head, distinct silhouette."""
    s = _s(tile, 'monster') * 0.95
    bob = math.sin(t * 6) * 0.7
    skin = (140, 40, 40) if hurt else (68, 112, 50)
    hi, mid, sh, deep = rs.material(skin)
    cloth = (86, 66, 44)
    cy += bob
    atk = max(0.0, min(1.0, float(attacking or 0)))
    lunge = math.sin(atk * math.pi) * 7 * s
    rs.draw_cast_shadow(surf, cx, cy + 13 * s, 10 * s, 3.2 * s, 115)
    # Bow legs
    rs.draw_volume_limb(surf, cx - 2.5 * s, cy + 3 * s, cx - 5.5 * s, cy + 13 * s, 1.5 * s, cloth, deep)
    rs.draw_volume_limb(surf, cx + 2.5 * s, cy + 3 * s, cx + 5 * s, cy + 13 * s, 1.5 * s, cloth, deep)
    # Stooped torso
    rs.draw_volume(surf, cloth, [
        (cx - 6.5 * s, cy - 0.5 * s), (cx + 5.5 * s, cy - 5 * s),
        (cx + 7.5 * s, cy + 5.5 * s), (cx - 7.5 * s, cy + 6.5 * s),
    ], deep, 1)
    # Long arms
    rs.draw_volume_limb(surf, cx - 5 * s, cy, cx - 11 * s, cy + 7 * s, 1.2 * s, skin, deep)
    club_hand = (cx + 6.5 * s + lunge * 0.3, cy - 2 * s)
    club_tip = (cx + 14 * s + lunge, cy - 13 * s)
    rs.draw_volume_limb(surf, cx + 4 * s, cy - 3 * s, *club_hand, 1.2 * s, skin, deep)
    rs.draw_volume_limb(surf, *club_hand, *club_tip, 1.4 * s, (100, 72, 42), deep)
    pygame.draw.circle(surf, (82, 58, 34), (int(club_tip[0]), int(club_tip[1])), max(3, int(3.2 * s)))
    # Angular head seated on shoulders
    head = (cx + 2 * s, cy - 7.2 * s)
    rs.draw_volume(surf, skin, [
        (head[0] - 4.5 * s, head[1] + 2 * s), (head[0] - 3.8 * s, head[1] - 3.2 * s),
        (head[0], head[1] - 5.2 * s), (head[0] + 4 * s, head[1] - 3 * s),
        (head[0] + 4.8 * s, head[1] + 1.2 * s), (head[0] + 1.5 * s, head[1] + 3.4 * s),
        (head[0] - 1.5 * s, head[1] + 3.4 * s),
    ], deep, 1)
    rs.draw_poly(surf, hi, [
        (head[0] - 2.5 * s, head[1] - 2 * s), (head[0], head[1] - 4.2 * s),
        (head[0] + 1.8 * s, head[1] - 1.5 * s),
    ], None, 0)
    # Ears up
    for side in (-1, 1):
        rs.draw_poly(surf, mid, [
            (head[0] + side * 3.5 * s, head[1] - 1 * s),
            (head[0] + side * 7.2 * s, head[1] - 5.8 * s),
            (head[0] + side * 2.5 * s, head[1] - 2.5 * s),
        ], deep, 1)
    for ox in (-1.4, 1.5):
        pygame.draw.rect(surf, (210, 200, 60), (head[0] + ox * s - 0.55 * s, head[1] - 0.7 * s, 1.1 * s, 0.95 * s))
        pygame.draw.circle(surf, (18, 16, 14), (int(head[0] + ox * s), int(head[1] - 0.25 * s)), max(1, int(0.4 * s)))
    for ox in (-0.9, 0.9):
        rs.draw_poly(surf, (230, 230, 220), [
            (head[0] + ox * s - 0.35 * s, head[1] + 1.8 * s),
            (head[0] + ox * s + 0.35 * s, head[1] + 1.8 * s),
            (head[0] + ox * s, head[1] + 3.5 * s),
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
    ink = (28, 24, 20)

    def stroke_poly(col, pts, width=1):
        pygame.draw.polygon(surf, col, pts)
        pygame.draw.polygon(surf, ink, pts, max(1, width))

    if item_id == "coins":
        pygame.draw.circle(surf, (230, 190, 60), (cx, cy), int(s * 0.26))
        pygame.draw.circle(surf, (255, 230, 120), (cx - int(s * 0.06), cy - int(s * 0.06)), max(1, int(s * 0.08)))
        pygame.draw.circle(surf, ink, (cx, cy), int(s * 0.26), 1)
        return
    if item.get("type") == "pet":
        if "cat" in item_id:
            pygame.draw.ellipse(surf, (220, 140, 70), (cx - s * 0.22, cy - s * 0.08, s * 0.4, s * 0.28))
            pygame.draw.circle(surf, (220, 140, 70), (int(cx + s * 0.12), int(cy - s * 0.12)), int(s * 0.14))
        elif "husky" in item_id:
            pygame.draw.ellipse(surf, (240, 240, 245), (cx - s * 0.22, cy - s * 0.06, s * 0.42, s * 0.28))
            pygame.draw.circle(surf, (230, 230, 235), (int(cx + s * 0.14), int(cy - s * 0.1)), int(s * 0.15))
            pygame.draw.circle(surf, (40, 40, 45), (int(cx + s * 0.1), int(cy - s * 0.1)), int(s * 0.05))
        elif "skeleton" in item_id:
            pygame.draw.circle(surf, (236, 232, 218), (cx, cy - s * 0.08), s * 0.16)
            pygame.draw.line(surf, (236, 232, 218), (cx, cy), (cx, cy + s * 0.2), max(2, int(s * 0.08)))
        else:
            pygame.draw.ellipse(surf, (45, 140, 80), (cx - s * 0.2, cy - s * 0.1, s * 0.4, s * 0.28))
            pygame.draw.circle(surf, (255, 200, 60), (int(cx + s * 0.12), int(cy - s * 0.12)), int(s * 0.06))
        return
    if itype == "weapon" or (item.get("tool_for") in ("woodcutting",) and "axe" in item_id):
        gold = (230, 200, 55)
        blade = (90, 95, 105) if "iron" in item_id else (
            (120, 140, 160) if "steel" in item_id else (
                (200, 150, 75) if "bronze" in item_id else (
                    (100, 180, 220) if "mithril" in item_id else (
                        (70, 200, 120) if "adamant" in item_id else (
                            (210, 160, 255) if "mythos" in item_id or "eclipse" in item_id else (180, 180, 190)
                        )
                    )
                )
            )
        )
        if "dagger" in item_id:
            stroke_poly(blade, [
                (cx - s * 0.06, cy + s * 0.1), (cx + s * 0.1, cy + s * 0.06),
                (cx + s * 0.26, cy - s * 0.26), (cx + s * 0.08, cy - s * 0.28)])
            pygame.draw.line(surf, gold, (cx - s * 0.14, cy + s * 0.12), (cx + s * 0.16, cy + s * 0.06), max(2, int(s * 0.08)))
            pygame.draw.circle(surf, gold, (int(cx - s * 0.02), int(cy + s * 0.2)), max(2, int(s * 0.055)))
        elif "battleaxe" in item_id or "cleaver" in item_id:
            pygame.draw.line(surf, (110, 75, 45), (cx - s * 0.05, cy + s * 0.24), (cx + s * 0.05, cy - s * 0.12), max(3, int(s * 0.1)))
            stroke_poly(blade, [
                (cx - s * 0.02, cy - s * 0.18), (cx + s * 0.32, cy - s * 0.30),
                (cx + s * 0.30, cy - s * 0.08), (cx + s * 0.05, cy - s * 0.05)])
            stroke_poly(blade, [
                (cx - s * 0.02, cy - s * 0.08), (cx + s * 0.30, cy + s * 0.10),
                (cx + s * 0.24, cy + s * 0.20), (cx + s * 0.02, cy + s * 0.05)])
        elif "axe" in item_id:
            pygame.draw.line(surf, (110, 75, 45), (cx - s * 0.05, cy + s * 0.24), (cx + s * 0.08, cy - s * 0.2), max(2, int(s * 0.08)))
            stroke_poly(blade, [
                (cx + s * 0.02, cy - s * 0.24), (cx + s * 0.28, cy - s * 0.18),
                (cx + s * 0.22, cy - s * 0.02), (cx + s * 0.05, cy - s * 0.06)])
        else:
            stroke_poly(blade, [
                (cx - s * 0.06, cy + s * 0.12), (cx + s * 0.08, cy + s * 0.08),
                (cx + s * 0.22, cy - s * 0.26), (cx + s * 0.05, cy - s * 0.28)])
            pygame.draw.line(surf, (220, 225, 235), (cx, cy + s * 0.05), (cx + s * 0.14, cy - s * 0.18), 1)
            pygame.draw.line(surf, gold, (cx - s * 0.18, cy + s * 0.14), (cx + s * 0.18, cy + s * 0.06), max(2, int(s * 0.09)))
            pygame.draw.circle(surf, gold, (int(cx - s * 0.05), int(cy + s * 0.22)), max(2, int(s * 0.06)))
        return
    if item.get("tool_for") == "mining":
        pygame.draw.line(surf, (120, 85, 50), (cx - s * 0.05, cy + s * 0.25), (cx + s * 0.05, cy - s * 0.2), max(2, int(s * 0.08)))
        pygame.draw.line(surf, (150, 150, 160), (cx - s * 0.22, cy - s * 0.15), (cx + s * 0.2, cy - s * 0.2), max(2, int(s * 0.09)))
        return
    if item.get("tool_for") == "fishing":
        pygame.draw.circle(surf, (210, 210, 220), (cx, cy), int(s * 0.24), max(1, int(s * 0.06)))
        return
    if item.get("equip_slot") == "shield":
        mid = (150, 155, 165) if "iron" in item_id else (
            (120, 140, 160) if "steel" in item_id else (
                (100, 180, 220) if "mithril" in item_id else (
                    (70, 200, 120) if "adamant" in item_id else (
                        (180, 130, 70) if "bronze" in item_id else (140, 100, 55)
                    )
                )
            )
        )
        dark = tuple(max(0, c - 45) for c in mid)
        light = tuple(min(255, c + 35) for c in mid)
        if "sq" in item_id:
            pygame.draw.rect(surf, dark, (cx - s * 0.22, cy - s * 0.24, s * 0.44, s * 0.48), border_radius=2)
            pygame.draw.rect(surf, mid, (cx - s * 0.18, cy - s * 0.2, s * 0.36, s * 0.4), border_radius=2)
            pygame.draw.rect(surf, light, (cx - s * 0.16, cy - s * 0.18, s * 0.14, s * 0.14))
            pygame.draw.circle(surf, dark, (int(cx), int(cy + s * 0.02)), max(2, int(s * 0.08)))
            pygame.draw.rect(surf, ink, (cx - s * 0.22, cy - s * 0.24, s * 0.44, s * 0.48), 1, border_radius=2)
        else:
            pts = [
                (cx - s * 0.22, cy - s * 0.2), (cx + s * 0.22, cy - s * 0.2),
                (cx + s * 0.2, cy + s * 0.1), (cx, cy + s * 0.28), (cx - s * 0.2, cy + s * 0.1),
            ]
            stroke_poly(mid, pts)
            pygame.draw.polygon(surf, light, [
                (cx - s * 0.16, cy - s * 0.16), (cx + s * 0.06, cy - s * 0.16),
                (cx + s * 0.08, cy + s * 0.02), (cx - s * 0.14, cy + s * 0.04),
            ])
            if "wood" not in item_id:
                red = (190, 40, 40)
                pygame.draw.line(surf, red, (cx, cy - s * 0.16), (cx, cy + s * 0.22), max(2, int(s * 0.07)))
                pygame.draw.line(surf, red, (cx - s * 0.16, cy), (cx + s * 0.16, cy), max(2, int(s * 0.07)))
        return
    if itype == "armor":
        if "helmet" in item_id or "cowl" in item_id or "helm" in item_id:
            col = (148, 102, 62) if "leather" in item_id else (
                (150, 155, 165) if "iron" in item_id else (
                    (120, 140, 160) if "steel" in item_id else (
                        (100, 180, 220) if "mithril" in item_id else (
                            (70, 200, 120) if "adamant" in item_id else (180, 130, 70)
                        )
                    )
                )
            )
            dark = tuple(max(0, c - 50) for c in col)
            light = tuple(min(255, c + 40) for c in col)
            pygame.draw.ellipse(surf, col, (cx - s * 0.22, cy - s * 0.26, s * 0.44, s * 0.4))
            pygame.draw.ellipse(surf, light, (cx - s * 0.14, cy - s * 0.24, s * 0.16, s * 0.12))
            pygame.draw.ellipse(surf, ink, (cx - s * 0.22, cy - s * 0.26, s * 0.44, s * 0.4), 1)
            if "leather" not in item_id and "cowl" not in item_id:
                pygame.draw.rect(surf, dark, (cx - s * 0.26, cy - s * 0.02, s * 0.52, s * 0.1))
                pygame.draw.rect(surf, (25, 22, 20), (cx - s * 0.14, cy - s * 0.06, s * 0.28, s * 0.06))
                pygame.draw.rect(surf, dark, (cx - s * 0.035, cy - s * 0.02, s * 0.07, s * 0.18))
            return
        if "legs" in item_id or "chaps" in item_id:
            col = (150, 155, 165) if "iron" in item_id else (
                (120, 140, 160) if "steel" in item_id else (
                    (100, 180, 220) if "mithril" in item_id else (
                        (70, 200, 120) if "adamant" in item_id else (
                            (180, 130, 70) if "bronze" in item_id else (130, 90, 55)
                        )
                    )
                )
            )
            pygame.draw.rect(surf, col, (cx - s * 0.2, cy - s * 0.1, s * 0.16, s * 0.32))
            pygame.draw.rect(surf, col, (cx + s * 0.04, cy - s * 0.1, s * 0.16, s * 0.32))
            pygame.draw.rect(surf, ink, (cx - s * 0.2, cy - s * 0.1, s * 0.16, s * 0.32), 1)
            pygame.draw.rect(surf, ink, (cx + s * 0.04, cy - s * 0.1, s * 0.16, s * 0.32), 1)
            return
        col = (150, 155, 165) if "iron" in item_id else (
            (120, 140, 160) if "steel" in item_id else (
                (100, 180, 220) if "mithril" in item_id else (
                    (70, 200, 120) if "adamant" in item_id else (
                        (180, 130, 70) if "bronze" in item_id else (
                            (148, 102, 62) if "leather" in item_id else (110, 130, 90)
                        )
                    )
                )
            )
        )
        light = tuple(min(255, c + 30) for c in col)
        torso = [
            (cx - s * 0.2, cy - s * 0.18), (cx + s * 0.2, cy - s * 0.18),
            (cx + s * 0.24, cy + s * 0.22), (cx - s * 0.24, cy + s * 0.22),
        ]
        stroke_poly(col, torso)
        pygame.draw.polygon(surf, light, [
            (cx - s * 0.16, cy - s * 0.14), (cx - s * 0.02, cy - s * 0.14),
            (cx - s * 0.02, cy + s * 0.08), (cx - s * 0.16, cy + s * 0.08),
        ])
        pygame.draw.circle(surf, col, (int(cx - s * 0.2), int(cy - s * 0.14)), max(2, int(s * 0.08)))
        pygame.draw.circle(surf, col, (int(cx + s * 0.2), int(cy - s * 0.14)), max(2, int(s * 0.08)))
        return
    if item_id in ("logs", "oak_logs"):
        color = (140, 95, 55) if item_id == "logs" else (90, 60, 35)
        end = (200, 170, 130) if item_id == "logs" else (160, 130, 90)
        for oy in (-0.1, 0.0, 0.1):
            x0 = cx - s * 0.22
            y0 = cy + oy * s
            pygame.draw.ellipse(surf, color, (x0, y0 - s * 0.08, s * 0.44, s * 0.16))
            pygame.draw.ellipse(surf, end, (x0 + s * 0.34, y0 - s * 0.06, s * 0.1, s * 0.12))
            pygame.draw.ellipse(surf, ink, (x0, y0 - s * 0.08, s * 0.44, s * 0.16), 1)
        return
    if item_id == "tinderbox":
        # Small metal box + flint
        pygame.draw.rect(surf, (90, 95, 105), (cx - s * 0.18, cy - s * 0.08, s * 0.36, s * 0.22))
        pygame.draw.rect(surf, (150, 155, 165), (cx - s * 0.18, cy - s * 0.08, s * 0.36, s * 0.06))
        pygame.draw.rect(surf, ink, (cx - s * 0.18, cy - s * 0.08, s * 0.36, s * 0.22), 1)
        pygame.draw.polygon(surf, (180, 185, 195), [
            (cx + s * 0.08, cy - s * 0.18), (cx + s * 0.22, cy - s * 0.02),
            (cx + s * 0.12, cy),
        ])
        pygame.draw.circle(surf, (255, 160, 60), (int(cx - s * 0.06), int(cy - s * 0.16)), max(1, int(s * 0.05)))
        return
    if "ore" in item_id:
        colors = {
            "copper_ore": (200, 120, 60), "tin_ore": (170, 170, 180), "iron_ore": (140, 90, 70),
            "mithril_ore": (100, 180, 220), "adamantite_ore": (70, 200, 120),
        }
        col = colors.get(item_id, (150, 150, 150))
        stroke_poly(col, [
            (cx - s * 0.2, cy + s * 0.15), (cx - s * 0.08, cy - s * 0.2),
            (cx + s * 0.15, cy - s * 0.15), (cx + s * 0.2, cy + s * 0.1), (cx, cy + s * 0.24)])
        pygame.draw.circle(surf, tuple(min(255, c + 40) for c in col), (int(cx - s * 0.02), int(cy - s * 0.04)), max(1, int(s * 0.06)))
        return

    if "shrimp" in item_id or "sardine" in item_id or "fish" in item_id:
        if "burnt" in item_id:
            color = (55, 45, 40)
        elif "cooked" in item_id:
            color = (210, 140, 90)
        else:
            color = (150, 170, 210)
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
    if item_id in ("bones", "big_bones", "dragon_bones"):
        color = (230, 225, 210)
        if item_id == "big_bones":
            color = (210, 200, 175)
            s_bone = s * 1.15
        elif item_id == "dragon_bones":
            color = (200, 160, 120)
            s_bone = s * 1.25
        else:
            s_bone = s
        pygame.draw.line(surf, color, (cx - s_bone * 0.2, cy), (cx + s_bone * 0.2, cy), max(2, int(s_bone * 0.07)))
        pygame.draw.circle(surf, color, (cx - s_bone * 0.2, cy), s_bone * 0.08)
        pygame.draw.circle(surf, color, (cx + s_bone * 0.2, cy), s_bone * 0.08)
        if item_id != "bones":
            pygame.draw.line(surf, color, (cx, cy - s_bone * 0.12), (cx, cy + s_bone * 0.12), max(2, int(s_bone * 0.05)))
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



def draw_tree_detailed(surf, cx, cy, tile, variant=0, t=0.0, alpha=255):
    """
    Volumetric tree — NOT layered circles.
    Tapered irregular trunk, visible forks, overlapping foliage masses
    with dark interior + lit crowns, anchored roots + cast shadow.

    alpha < 255 draws the tree ghosted (player can see through canopy).
    """
    if alpha < 248:
        w = max(80, int(tile * 6.5))
        h = max(100, int(tile * 7.5))
        tmp = pygame.Surface((w, h), pygame.SRCALPHA)
        ox, oy = w // 2, int(h * 0.72)
        draw_tree_detailed(tmp, ox, oy, tile, variant=variant, t=t, alpha=255)
        tmp.set_alpha(max(55, min(240, int(alpha))))
        surf.blit(tmp, (int(cx - ox), int(cy - oy)))
        return

    s = _s(tile, "object") * getattr(rs, "TREE_SCALE", 1.72)
    oak = (variant % 3 == 1)
    pine = (variant % 3 == 2)
    if oak:
        s *= 1.12
    elif pine:
        s *= 0.95
    seed = variant * 17 + int(cx) * 3 + int(cy)
    trunk = (96, 68, 38) if not oak else (78, 52, 28)
    if pine:
        trunk = (88, 62, 36)
    foliage = (36, 98, 40) if not oak else (28, 78, 32)
    if pine:
        foliage = (32, 88, 42)
    feet = cy + 12 * s
    sway = math.sin(t * 0.85 + variant) * 0.55 * s
    lean = (_seeded(seed, 0, 1) - 0.5) * 2.4 * s

    # Irregular ground shadow
    rs.draw_cast_shadow(
        surf, cx + 5 * s, feet + 1.5 * s,
        (20 if oak else 15) * s, 5 * s, 130,
        irregular=True, seed=seed,
    )
    rs.draw_contact_shadow(surf, cx, feet, 7 * s, 2.5 * s, 100)

    # Roots — irregular flares
    for side, sc in ((-1, 0), (1, 1)):
        rx = 4.5 + 1.5 * _seeded(seed, sc, 2)
        rs.draw_volume(surf, trunk, [
            (cx + side * 1.5 * s, feet - 2.5 * s),
            (cx + side * rx * s, feet + 0.5 * s),
            (cx + side * (rx - 1.2) * s, feet + 1.2 * s),
            (cx + side * 0.8 * s, feet - 0.5 * s),
        ], rs.OUTLINE, 1)

    # Trunk — irregular tapered polygon with lit/shade planes
    tw_base = 3.4 if oak else (2.2 if pine else 2.6)
    tw_top = tw_base * 0.45
    top_y = cy - (14 if oak else (18 if pine else 15)) * s
    # Shade (right) plane
    rs.draw_poly(surf, rs.shade(trunk, -42), [
        (cx + tw_base * 0.1 * s + lean * 0.4, feet - 2 * s),
        (cx + tw_base * 1.05 * s + lean, feet - 2 * s),
        (cx + tw_top * 0.9 * s + lean, top_y),
        (cx + tw_top * 0.05 * s + lean * 0.5, top_y),
    ], None, 0)
    # Front irregular trunk (not a rectangle)
    j0 = 0.15 * _seeded(seed, 3, 1)
    j1 = 0.2 * (_seeded(seed, 4, 1) - 0.5)
    trunk_pts = [
        (cx - tw_base * (0.95 + j0) * s + lean * 0.2, feet - 1.5 * s),
        (cx - tw_base * 0.4 * s + lean * 0.3, feet - 2 * s),
        (cx + tw_base * 0.35 * s + lean * 0.5, feet - 2 * s),
        (cx + tw_base * (0.85 + j1) * s + lean, feet - 1.5 * s),
        (cx + tw_top * 0.7 * s + lean, top_y + 1 * s),
        (cx - tw_top * 0.55 * s + lean * 0.5, top_y),
    ]
    rs.draw_volume(surf, trunk, trunk_pts, rs.OUTLINE, max(1, int(s * 0.4)))
    # Lit left edge
    rs.draw_poly(surf, rs.shade(trunk, 38), [
        (cx - tw_base * 1.05 * s + lean * 0.15, feet - 2 * s),
        (cx - tw_base * 0.45 * s + lean * 0.25, feet - 2 * s),
        (cx - tw_top * 0.35 * s + lean * 0.45, top_y),
        (cx - tw_top * 0.85 * s + lean * 0.25, top_y + 0.5 * s),
    ], None, 0)
    # Bark grooves
    for i in range(4):
        bx = cx + (_seeded(seed, i, 5) - 0.5) * tw_base * 0.7 * s + lean * 0.4
        pygame.draw.line(
            surf, rs.shade(trunk, -28),
            (bx, feet - 3 * s), (bx + lean * 0.3 + (_seeded(seed, i, 6) - 0.5) * s, top_y + 3 * s),
            max(1, int(s * 0.28)),
        )

    # Branch forks — different thicknesses, natural angles
    forks = [(-1.0, 0.0, 1.0), (1.05, -0.1, 0.9)]
    if oak:
        forks = [(-1.15, -0.15, 1.15), (0.15, -0.55, 0.85), (1.1, -0.05, 1.0)]
    elif pine:
        forks = [(-0.7, 0.2, 0.7), (0.75, 0.15, 0.7), (-0.4, -0.4, 0.55), (0.45, -0.35, 0.55)]
    branch_tips = []
    for bi, (side, yoff, thick) in enumerate(forks):
        ax = cx + lean * 0.45
        ay = top_y + (5 + yoff * 8) * s
        blen = (6.5 + 2.5 * oak + 1.5 * _seeded(seed, bi, 8)) * s
        bx = ax + side * blen + sway * 0.35
        by = ay - (4.5 + oak * 2 + pine) * s + sway
        rs.draw_volume_limb(surf, ax, ay, bx, by, thick * 1.15 * s, trunk, rs.OUTLINE, taper=0.55, bulge=0.05)
        branch_tips.append((bx, by))
        # Secondary twig
        if oak or _seeded(seed, bi, 9) > 0.4:
            tx = bx + side * 3.5 * s
            ty = by - 2.5 * s + sway * 0.2
            rs.draw_volume_limb(surf, bx, by, tx, ty, 0.55 * s, trunk, None, taper=0.5, bulge=0.0)
            branch_tips.append((tx, ty))

    # Foliage: dark interior mass first, then mid lobes, then lit crowns
    # NEVER perfect circles — irregular_ring only
    dark_f = rs.shade(foliage, -40)
    mid_f = foliage
    lit_f = rs.shade(foliage, 45)
    canopy_y = top_y + 2 * s

    if pine:
        # Dense layered conical tiers with needle skirts
        for ti, (oy, rx, ry) in enumerate((
            (0, 13, 6), (-5, 11.5, 5.5), (-10, 9.5, 5), (-14.5, 7, 4.2), (-18, 4.5, 3.2), (-21, 2.5, 2.2),
        )):
            col = dark_f if ti < 2 else (mid_f if ti < 4 else lit_f)
            pts = []
            n = 10
            for k in range(n):
                ang = TAU * k / n + ti * 0.15
                rr = 0.65 + 0.35 * _seeded(seed, ti, k)
                # Pointed top bias
                if math.sin(ang) < -0.2:
                    rr *= 0.55
                px = cx + sway * 0.25 + math.cos(ang) * rx * s * rr
                py = canopy_y + oy * s + math.sin(ang) * ry * s * rr * 0.7
                if math.sin(ang) > 0.4:
                    py += 2.2 * s  # drooping skirt
                pts.append((px, py))
            pts.insert(len(pts) // 2, (cx + sway * 0.2, canopy_y + (oy - ry) * s))
            if col == lit_f:
                rs.draw_poly(surf, col, pts, None, 0)
            else:
                rs.draw_volume(surf, col, pts, rs.OUTLINE if ti == 0 else None, 1 if ti == 0 else 0)
    else:
        # Interior dark volume
        interior = rs.irregular_ring(cx + sway * 0.2, canopy_y - 2 * s, 14 * s, 10 * s, n=10, seed=seed, jitter=0.18)
        rs.draw_poly(surf, dark_f, interior, None, 0)
        # Mid overlapping masses (anchored near branch tips + canopy)
        masses = [
            (dark_f, -10, -1, 11, 8, 9),
            (dark_f, 9, 0, 10, 7.5, 8),
            (mid_f, -6, -8, 10, 8.5, 9),
            (mid_f, 5, -10, 11, 9, 9),
            (mid_f, 0, -3, 9, 7, 8),
            (mid_f, -12, -5, 8, 7, 7),
            (lit_f, -2, -15, 7.5, 6.5, 8),
            (lit_f, 7, -13, 6.5, 5.5, 7),
            (lit_f, -9, -11, 6.5, 5.5, 7),
        ]
        if oak:
            masses += [
                (mid_f, -14, -7, 9, 7.5, 8),
                (lit_f, 2, -17, 6.5, 5.5, 7),
                (mid_f, 12, -6, 8, 7, 7),
            ]
        for i, (col, ox, oy, rx, ry, n) in enumerate(masses):
            bx = cx + ox * s + sway
            by = canopy_y + oy * s
            # Pull a couple masses toward branch tips for cohesion
            if i < len(branch_tips) and i % 2 == 0:
                tip = branch_tips[i % len(branch_tips)]
                bx = (bx + tip[0]) * 0.5
                by = (by + tip[1]) * 0.5
            pts = rs.irregular_ring(bx, by, rx * s, ry * s, n=n, seed=seed + i * 7, jitter=0.3)
            if col == lit_f:
                rs.draw_poly(surf, col, pts, None, 0)
                # Tiny leaf-cluster highlights
                if _seeded(seed, i, 20) > 0.55:
                    pygame.draw.circle(surf, rs.shade(lit_f, 25), (int(bx - 1.5 * s), int(by - 1.2 * s)), max(1, int(1.2 * s)))
            else:
                rs.draw_volume(surf, col, pts, rs.OUTLINE if i < 2 else None, 1 if i < 2 else 0)


def draw_rock_detailed(surf, cx, cy, tile, variant=0, ore_type=None):
    """
    Faceted rock volume communicating 3D form:
    irregular silhouette, top plane, lit face, shade face, underside,
    cracks, ore flecks, tight contact shadow.
    """
    s = _s(tile, "object") * 0.72
    seed = variant * 11 + int(cx) + int(cy) * 2
    base = (108, 104, 96)
    if ore_type == "coal_rock":
        base = (58, 58, 62)
    hi, mid, sh, deep = rs.material(base)
    vein = (190, 160, 90)
    if ore_type == "copper_rock":
        vein = (220, 140, 70)
    elif ore_type == "tin_rock":
        vein = (200, 205, 215)
    elif ore_type == "iron_rock":
        vein = (170, 90, 60)
    elif ore_type == "coal_rock":
        vein = (140, 140, 150)
    elif ore_type == "mithril_rock":
        vein = (120, 190, 230)
    elif ore_type == "adamantite_rock":
        vein = (80, 200, 120)

    rs.draw_cast_shadow(surf, cx + 2 * s, cy + 6.5 * s, 11 * s, 3.0 * s, 105)
    rs.draw_contact_shadow(surf, cx, cy + 7 * s, 9 * s, 2.2 * s, 130)

    jitter = lambda i, lo, hi_v: lo + (hi_v - lo) * _seeded(seed, i, 7)

    # Outer silhouette — controlled irregular mass with variant-specific lean
    lean_r = (variant % 3 - 1) * 2.5 * s
    tall = 1.0 + 0.15 * (variant % 2)
    wide = 1.0 + 0.12 * ((variant + 1) % 3)
    sil = [
        (cx - 11.5 * s * wide, cy + 5.8 * s),
        (cx - 9.5 * s * wide - jitter(1, 0, 1.5) * s, cy + 1 * s),
        (cx - 8 * s * wide + lean_r * 0.2, cy - 2.5 * s * tall),
        (cx - 3.5 * s - jitter(2, -0.5, 1) * s + lean_r * 0.4, cy - 7.2 * s * tall),
        (cx + 2.5 * s + jitter(3, -1, 1.5) * s + lean_r, cy - 10 * s * tall),
        (cx + 8 * s * wide + lean_r * 0.5, cy - 6.5 * s * tall),
        (cx + 11.5 * s * wide + jitter(4, -0.5, 1) * s, cy - 2 * s),
        (cx + 12.5 * s * wide, cy + 2.5 * s),
        (cx + 8 * s * wide, cy + 7.2 * s),
        (cx - 1 * s, cy + 7.8 * s),
        (cx - 6 * s * wide, cy + 7.2 * s),
    ]
    rs.draw_poly(surf, mid, sil, deep, max(1, int(s * 0.55)))

    # Underside / ground contact darkening
    under = [
        (cx - 10 * s, cy + 4 * s),
        (cx + 10 * s, cy + 3.5 * s),
        (cx + 8 * s, cy + 7 * s),
        (cx - 1 * s, cy + 7.5 * s),
        (cx - 6 * s, cy + 7 * s),
    ]
    rs.draw_poly(surf, deep, under, None, 0)

    # Top plane (receives most light)
    top = [
        (cx - 6.5 * s, cy - 2.5 * s),
        (cx - 3 * s, cy - 7.5 * s),
        (cx + 3 * s, cy - 9.2 * s),
        (cx + 7.5 * s, cy - 5 * s),
        (cx + 3 * s, cy - 1.5 * s),
        (cx - 2 * s, cy - 0.8 * s),
    ]
    rs.draw_poly(surf, hi, top, None, 0)
    # Soft top edge specular
    pygame.draw.line(surf, rs.shade(hi, 30), (cx - 4 * s, cy - 5 * s), (cx + 2 * s, cy - 8 * s), max(1, int(s * 0.4)))

    # Lit left face
    lit_face = [
        (cx - 10.5 * s, cy + 3.5 * s),
        (cx - 8.5 * s, cy - 1.5 * s),
        (cx - 3 * s, cy - 7 * s),
        (cx - 6 * s, cy - 2.5 * s),
        (cx - 4.5 * s, cy + 3.5 * s),
    ]
    rs.draw_poly(surf, rs.shade(mid, 22), lit_face, None, 0)

    # Shade right face
    shade_face = [
        (cx + 3 * s, cy - 8.5 * s),
        (cx + 8 * s, cy - 5.5 * s),
        (cx + 11 * s, cy - 1.5 * s),
        (cx + 11 * s, cy + 3 * s),
        (cx + 5.5 * s, cy + 5 * s),
        (cx + 2.5 * s, cy - 1 * s),
    ]
    rs.draw_poly(surf, sh, shade_face, None, 0)

    # Mid ridge plane (separates top from shade)
    ridge = [
        (cx - 1 * s, cy - 1 * s),
        (cx + 3 * s, cy - 8 * s),
        (cx + 5 * s, cy - 3 * s),
        (cx + 1 * s, cy + 1 * s),
    ]
    rs.draw_poly(surf, mid, ridge, None, 0)

    # Cracks
    pygame.draw.line(surf, deep, (cx - 5.5 * s, cy + 1.5 * s), (cx + 2.5 * s, cy - 5.5 * s), max(1, int(s * 0.4)))
    pygame.draw.line(surf, deep, (cx + 0.5 * s, cy - 2 * s), (cx + 7 * s, cy + 1.5 * s), max(1, int(s * 0.32)))
    pygame.draw.line(surf, rs.shade(deep, 15), (cx - 2 * s, cy - 4 * s), (cx + 4 * s, cy - 1 * s), 1)

    # Ore flecks — sit on lit/top faces
    for i, (ox, oy) in enumerate(((-3.5, -3.5), (1.2, -6.5), (5, -2.5), (-1.5, 0.5), (3.5, 2.2), (-6, 1))):
        col = vein if i < 4 else rs.shade(vein, -25)
        r = max(1, int((1.25 + (i % 3) * 0.4) * s))
        pygame.draw.circle(surf, col, (int(cx + ox * s), int(cy + oy * s)), r)
        if i < 4:
            pygame.draw.circle(surf, rs.shade(vein, 45), (int(cx + ox * s - 0.4 * s), int(cy + oy * s - 0.4 * s)), max(1, int(0.45 * s)))


def draw_furnace(surf, cx, cy, tile, t=0.0):
    """Stone furnace — roughly chest-high (smithing screenshots)."""
    s = _s(tile, "object") * 0.95
    glow = int(40 + 30 * abs(math.sin(t * 4)))
    rs.draw_shadow(surf, cx, cy + 9 * s, 12 * s, 3.5 * s)
    # stone body
    _poly(surf, (105, 98, 88), [
        (cx - 11 * s, cy + 10 * s), (cx + 11 * s, cy + 10 * s),
        (cx + 10 * s, cy - 2 * s), (cx - 10 * s, cy - 2 * s),
    ], (55, 50, 44), max(1, int(s)))
    _poly(surf, (125, 118, 105), [
        (cx - 9 * s, cy - 1 * s), (cx + 4 * s, cy - 1 * s),
        (cx + 4 * s, cy + 5 * s), (cx - 9 * s, cy + 5 * s),
    ], None, 0)
    # fire mouth
    pygame.draw.rect(surf, (35, 22, 16), (cx - 6 * s, cy + 2 * s, 12 * s, 6 * s))
    pygame.draw.rect(surf, (230, 120 + glow // 2, 40), (cx - 5 * s, cy + 3 * s, 10 * s, 4 * s))
    # chimney
    pygame.draw.rect(surf, (80, 74, 66), (cx - 3 * s, cy - 14 * s, 6 * s, 12 * s))
    pygame.draw.rect(surf, (55, 50, 44), (cx - 4 * s, cy - 15 * s, 8 * s, 3 * s))
    pygame.draw.circle(surf, (100, 100, 105), (int(cx + 2 * s), int(cy - 16 * s + math.sin(t * 3) * s)), max(2, int(2.5 * s)))


def draw_anvil(surf, cx, cy, tile, t=0.0):
    """Heavy iron anvil — knee-high (smithing screenshots)."""
    s = _s(tile, "object") * 0.72
    rs.draw_shadow(surf, cx, cy + 7 * s, 10 * s, 3 * s)
    pygame.draw.rect(surf, (90, 60, 35), (cx - 5 * s, cy + 2 * s, 10 * s, 7 * s))
    pygame.draw.rect(surf, (60, 40, 22), (cx - 5 * s, cy + 2 * s, 10 * s, 7 * s), 1)
    _poly(surf, (130, 135, 145), [
        (cx - 11 * s, cy - 3 * s), (cx + 8 * s, cy - 3 * s),
        (cx + 9 * s, cy + 2 * s), (cx - 10 * s, cy + 2 * s),
    ], (70, 72, 80), 1)
    _poly(surf, (150, 155, 165), [
        (cx + 8 * s, cy - 2 * s), (cx + 15 * s, cy), (cx + 8 * s, cy + 2 * s),
    ], (70, 72, 80), 1)
    pygame.draw.line(surf, (190, 195, 205), (cx - 8 * s, cy - 2 * s), (cx + 5 * s, cy - 2 * s), max(2, int(s)))


def draw_forge(surf, cx, cy, tile, t=0.0):
    """Backward-compatible combined forge mark (prefer draw_furnace / draw_anvil)."""
    draw_furnace(surf, cx - tile * 0.15, cy, tile, t)
    draw_anvil(surf, cx + tile * 0.35, cy, tile * 0.85, t)


def draw_house(surf, rect, style=0, t=0.0, material=None):
    """
    Architectural building — foundation, textured wood or grey-brick walls,
    roof overhang, recessed windows, thick door, chimney, cast shadow.
    """
    x, y, w, h = rect if not hasattr(rect, "x") else (rect.x, rect.y, rect.w, rect.h)
    if material is None:
        material = "wood" if (style % 2 == 0) else "brick"
    wood = material != "brick"
    wall = (158, 118, 74) if wood else (118, 116, 122)
    roof = (96, 52, 42) if wood else (68, 72, 80)
    thatch = wood and style % 4 == 0
    if thatch:
        roof = (130, 110, 55)
    trim = (68, 46, 32) if wood else (55, 56, 62)
    hi, mid, sh, deep = rs.material(wall)
    r_hi, r_mid, r_sh, r_deep = rs.material(roof)

    # Ground shadow (directional)
    rs.draw_cast_shadow(surf, x + w * 0.55, y + h - 2, w * 0.55, h * 0.12, 120, irregular=True, seed=style * 9)

    # Foundation
    found_h = h * 0.08
    found_col = (82, 78, 70) if wood else (64, 66, 72)
    pygame.draw.rect(surf, found_col, (x - 2, y + h - found_h, w + 4, found_h + 3))
    pygame.draw.line(surf, (55, 52, 48), (x - 2, y + h - found_h), (x + w + 2, y + h - found_h), 1)

    # Wall body with perspective: front plane + darker right side plane
    wall_top = y + h * 0.32
    wall_h = h - found_h - h * 0.32
    side_w = max(4, int(w * 0.08))
    rs.draw_poly(surf, sh, [
        (x + w, wall_top),
        (x + w + side_w, wall_top + 4),
        (x + w + side_w, y + h - found_h + 2),
        (x + w, y + h - found_h),
    ], deep, 1)
    # Textured front wall
    wall_rect = pygame.Rect(int(x), int(wall_top), int(w), int(wall_h))
    if wood:
        _fill_wood_face(surf, wall_rect, seed_x=int(x), seed_y=int(y), alpha=255)
    else:
        _fill_brick_face(surf, wall_rect, seed_x=int(x), seed_y=int(y), alpha=255)
    # Lit left edge
    pygame.draw.rect(surf, hi, (x, wall_top, max(3, int(w * 0.05)), wall_h), 1)

    # Roof with overhang (sits ON walls)
    overhang = 8
    ridge_y = y + 2
    eave_y = wall_top + 4
    rs.draw_poly(surf, r_sh, [
        (x + w * 0.5, ridge_y),
        (x + w + overhang + side_w, eave_y),
        (x + w + overhang + side_w - 2, eave_y + h * 0.12),
        (x + w * 0.5 + 2, eave_y + h * 0.08),
    ], r_deep, 1)
    roof_pts = [
        (x - overhang, eave_y),
        (x + w * 0.5, ridge_y),
        (x + w + overhang, eave_y),
        (x + w + overhang - 3, eave_y + h * 0.14),
        (x - overhang + 3, eave_y + h * 0.14),
    ]
    rs.draw_volume(surf, roof, roof_pts, r_deep, 2)
    pygame.draw.line(surf, r_hi, (x + w * 0.5, ridge_y + 2), (x + w * 0.35, eave_y), 2)
    # Roof courses
    for i in range(4):
        yy = eave_y + 3 + i * max(3, int(h * 0.03))
        inset = 2 + i * 2
        pygame.draw.line(surf, r_sh, (x - overhang + inset, yy), (x + w + overhang - inset, yy), 1)
    if thatch:
        for i in range(5):
            yy = eave_y + 4 + i * 3
            pygame.draw.line(surf, r_sh, (x - 4 + i, yy), (x + w + 4 - i, yy), 1)

    # Chimney
    if style % 3 != 2:
        chx = x + w * 0.72
        ch_col = (90, 84, 78) if wood else (100, 98, 104)
        pygame.draw.rect(surf, ch_col, (chx, ridge_y + h * 0.08, w * 0.12, h * 0.28))
        pygame.draw.rect(surf, (60, 56, 52), (chx - 2, ridge_y + h * 0.06, w * 0.16, 4))
        pygame.draw.rect(surf, hi, (chx, ridge_y + h * 0.08, 2, h * 0.2))

    # Recessed windows with frames
    for wx in (x + w * 0.16, x + w * 0.62):
        wy, ww, wh = y + h * 0.48, w * 0.16, h * 0.16
        pygame.draw.rect(surf, deep, (wx - 2, wy - 2, ww + 4, wh + 4))
        pygame.draw.rect(surf, (40, 70, 95), (wx, wy, ww, wh))
        pygame.draw.rect(surf, (70, 110, 140), (wx + 1, wy + 1, ww * 0.4, wh * 0.35))
        pygame.draw.line(surf, trim, (wx + ww * 0.5, wy), (wx + ww * 0.5, wy + wh), 1)
        pygame.draw.line(surf, trim, (wx, wy + wh * 0.5), (wx + ww, wy + wh * 0.5), 1)

    # Door with thickness
    door_w, door_h = w * 0.18, h * 0.36
    dx = x + w * 0.41
    dy = y + h - found_h - door_h
    pygame.draw.rect(surf, deep, (dx - 2, dy - 2, door_w + 5, door_h + 2))
    pygame.draw.rect(surf, (78, 52, 34), (dx, dy, door_w, door_h))
    pygame.draw.rect(surf, (100, 70, 45), (dx + 2, dy + 2, door_w * 0.55, door_h * 0.4))
    for yy in (dy + door_h * 0.3, dy + door_h * 0.55):
        pygame.draw.line(surf, (55, 36, 24), (dx + 2, yy), (dx + door_w - 2, yy), 1)
    pygame.draw.circle(surf, (210, 170, 70), (int(dx + door_w * 0.78), int(dy + door_h * 0.5)), max(2, int(w * 0.022)))


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
    """Chunky skeletal adventurer (RS-era silhouette)."""
    from rs_humanoid import draw_skeletal_humanoid
    draw_skeletal_humanoid(
        surf, cx, cy, tile,
        body_color=body_color, skin_color=skin_color, hair_color=hair_color,
        weapon=weapon, shield=shield, moving=moving, t=t,
        robe=robe, facing=facing, equipment=equipment, attacking=attacking,
    )



def draw_orc(surf, cx, cy, tile, t, hurt=False, attacking=0.0):
    """Broad-shouldered brute — thick limbs, heavy jaw, cleaver."""
    s = _s(tile, 'monster') * 1.18
    bob = math.sin(t * 4.5) * 0.6
    skin = (175, 55, 45) if hurt else (64, 98, 54)
    hi, mid, sh, deep = rs.material(skin)
    cloth = (70, 55, 40)
    cy += bob
    atk = max(0.0, min(1.0, float(attacking or 0)))
    lunge = math.sin(atk * math.pi) * 6 * s
    rs.draw_cast_shadow(surf, cx, cy + 14 * s, 13 * s, 3.8 * s, 120)
    rs.draw_volume_limb(surf, cx - 3.5 * s, cy + 2 * s, cx - 6.5 * s, cy + 14 * s, 2.0 * s, cloth, deep)
    rs.draw_volume_limb(surf, cx + 3.5 * s, cy + 2 * s, cx + 6.5 * s, cy + 14 * s, 2.0 * s, cloth, deep)
    # Broad torso
    rs.draw_volume(surf, cloth, [
        (cx - 10 * s, cy - 5 * s), (cx + 10 * s, cy - 6.5 * s),
        (cx + 11 * s, cy + 6.5 * s), (cx - 11 * s, cy + 7.5 * s),
    ], deep, 1)
    # Thick arms
    rs.draw_volume_limb(surf, cx - 9 * s, cy - 2 * s, cx - 14 * s, cy + 7 * s, 1.7 * s, skin, deep)
    hand = (cx + 10 * s + lunge * 0.25, cy - 1 * s)
    tip = (cx + 19 * s + lunge, cy - 14 * s)
    rs.draw_volume_limb(surf, cx + 8 * s, cy - 3 * s, *hand, 1.7 * s, skin, deep)
    rs.draw_volume_limb(surf, *hand, *tip, 1.5 * s, (110, 75, 42), deep)
    rs.draw_volume(surf, (175, 175, 170), [
        (tip[0] - 1 * s, tip[1] + 2 * s), (tip[0] + 8.5 * s, tip[1] + 1 * s),
        (tip[0] + 7.5 * s, tip[1] + 6.5 * s), (tip[0], tip[1] + 5.5 * s),
    ], deep, 1)
    # Heavy jaw head
    head = (cx + 1 * s, cy - 8.2 * s)
    rs.draw_volume(surf, skin, [
        (head[0] - 6 * s, head[1] + 2.5 * s), (head[0] - 5 * s, head[1] - 4 * s),
        (head[0], head[1] - 5.8 * s), (head[0] + 5.5 * s, head[1] - 3.5 * s),
        (head[0] + 6.2 * s, head[1] + 2 * s), (head[0] + 2 * s, head[1] + 4.5 * s),
        (head[0] - 2 * s, head[1] + 4.5 * s),
    ], deep, 1)
    rs.draw_poly(surf, hi, [
        (head[0] - 3 * s, head[1] - 2.2 * s), (head[0], head[1] - 4.5 * s),
        (head[0] + 2.2 * s, head[1] - 1.5 * s),
    ], None, 0)
    for side in (-1, 1):
        rs.draw_poly(surf, mid, [
            (head[0] + side * 4.5 * s, head[1] - 1 * s),
            (head[0] + side * 8.5 * s, head[1] - 4.5 * s),
            (head[0] + side * 3.5 * s, head[1] - 2.5 * s),
        ], deep, 1)
    for ox in (-1.7, 1.8):
        pygame.draw.rect(surf, (220, 200, 55), (head[0] + ox * s - 0.7 * s, head[1] - 0.8 * s, 1.4 * s, 1.15 * s))
        pygame.draw.circle(surf, (18, 16, 14), (int(head[0] + ox * s), int(head[1] - 0.25 * s)), max(1, int(0.45 * s)))
    for ox in (-2.0, 2.0):
        rs.draw_poly(surf, (235, 225, 190), [
            (head[0] + ox * s - 0.55 * s, head[1] + 2.2 * s),
            (head[0] + ox * s + 0.55 * s, head[1] + 2.2 * s),
            (head[0] + ox * s * 1.1, head[1] + 4.8 * s),
        ])


def draw_slime(surf, cx, cy, tile, t, hurt=False, attacking=0.0):
    """Gelatinous mass — translucent layers, ground contact, internal variation."""
    s = _s(tile, "monster")
    body = (200, 70, 75) if hurt else (74, 160, 106)
    hi = (235, 225, 150) if hurt else (140, 220, 165)
    deep = rs.shade(body, -50)
    bounce = abs(math.sin(t * 5)) * 2.2 * s
    squash = 1.0 + 0.08 * math.sin(t * 5 + 1.2)
    rs.draw_contact_shadow(surf, cx, cy + 9 * s, 12 * s * squash, 3.2 * s, 130)
    # Dark base puddle contact
    base_pts = rs.irregular_ring(cx, cy + 7.5 * s, 11 * s * squash, 3.5 * s, n=8, seed=int(cx) + 3, jitter=0.15)
    rs.draw_poly(surf, deep, base_pts, None, 0)
    # Main gelatin body
    body_pts = rs.irregular_ring(cx, cy + 1 * s - bounce, 11 * s * squash, 9.5 * s, n=10, seed=int(cx), jitter=0.22)
    rs.draw_volume(surf, body, body_pts, deep, max(1, int(s)))
    # Inner translucent core (lighter)
    core = rs.irregular_ring(cx - 0.5 * s, cy - bounce, 6 * s, 5.5 * s, n=7, seed=int(cx) + 1, jitter=0.15)
    rs.draw_poly(surf, rs.shade(body, 25), core, None, 0)
    # Specular highlight band
    pygame.draw.arc(
        surf, hi,
        (cx - 7 * s, cy - 7 * s - bounce, 14 * s, 10 * s),
        math.pi * 1.05, math.pi * 1.85, max(2, int(1.2 * s)),
    )
    pygame.draw.circle(surf, (255, 255, 230), (int(cx - 3 * s), int(cy - 4 * s - bounce)), max(2, int(1.8 * s)))
    # Eyes floating inside
    for ox in (-3.2, 3.2):
        pygame.draw.circle(surf, (25, 35, 30), (int(cx + ox * s), int(cy - 0.5 * s - bounce)), max(2, int(1.3 * s)))
        pygame.draw.circle(surf, (220, 240, 200), (int(cx + ox * s - 0.3 * s), int(cy - 0.8 * s - bounce)), max(1, int(0.45 * s)))


def draw_giant(surf, cx, cy, tile, t, hurt=False):
    """Massive humanoid — heavy shoulders, thick limbs, tree-trunk club."""
    s = _s(tile, 'monster') * 1.55
    bob = math.sin(t * 3.5) * 0.7
    skin = (175, 55, 45) if hurt else (150, 118, 92)
    hi, mid, sh, deep = rs.material(skin)
    tunic = (82, 62, 48)
    hair = (48, 34, 24)
    cy += bob
    rs.draw_cast_shadow(surf, cx + 2 * s, cy + 18 * s, 17 * s, 5 * s, 130)
    # Legs
    rs.draw_volume_limb(surf, cx - 5 * s, cy + 5 * s, cx - 7 * s, cy + 18 * s, 2.8 * s, (50, 38, 28), deep)
    rs.draw_volume_limb(surf, cx + 5 * s, cy + 5 * s, cx + 7 * s, cy + 18 * s, 2.8 * s, (50, 38, 28), deep)
    # Torso with shoulder mass
    rs.draw_volume(surf, tunic, [
        (cx - 10 * s, cy - 10 * s), (cx + 10 * s, cy - 10 * s),
        (cx + 12 * s, cy + 10 * s), (cx - 12 * s, cy + 10 * s),
    ], deep, 1)
    rs.draw_poly(surf, rs.shade(tunic, 22), [
        (cx - 8 * s, cy - 9 * s), (cx - 0.5 * s, cy - 9 * s),
        (cx - 0.5 * s, cy + 3 * s), (cx - 8 * s, cy + 3 * s),
    ], None, 0)
    pygame.draw.circle(surf, tunic, (int(cx - 9 * s), int(cy - 7 * s)), max(3, int(3.5 * s)))
    pygame.draw.circle(surf, tunic, (int(cx + 9 * s), int(cy - 7 * s)), max(3, int(3.5 * s)))
    # Free arm
    rs.draw_volume_limb(surf, cx - 9 * s, cy - 5 * s, cx - 15 * s, cy + 5 * s, 2.2 * s, skin, deep)
    pygame.draw.circle(surf, hi, (int(cx - 15 * s), int(cy + 5 * s)), max(3, int(2.6 * s)))
    # Club arm
    rs.draw_volume_limb(surf, cx + 9 * s, cy - 4 * s, cx + 15 * s, cy - 1 * s, 2.2 * s, skin, deep)
    rs.draw_volume_limb(surf, cx + 15 * s, cy - 1 * s, cx + 21 * s, cy - 18 * s, 2.0 * s, (95, 65, 38), deep)
    pygame.draw.circle(surf, (70, 48, 26), (int(cx + 21 * s), int(cy - 19 * s)), int(5.2 * s))
    # Neck + head
    rs.draw_volume(surf, skin, [
        (cx - 2.2 * s, cy - 12 * s), (cx + 2.2 * s, cy - 12 * s),
        (cx + 2 * s, cy - 15 * s), (cx - 2 * s, cy - 15 * s),
    ], deep, 1)
    head = (cx, cy - 18 * s)
    rs.draw_volume(surf, skin, [
        (head[0] - 6 * s, head[1] + 2 * s), (head[0] - 5 * s, head[1] - 4 * s),
        (head[0], head[1] - 6 * s), (head[0] + 5.5 * s, head[1] - 4 * s),
        (head[0] + 6 * s, head[1] + 2 * s), (head[0], head[1] + 4 * s),
    ], deep, 1)
    rs.draw_poly(surf, hair, [
        (head[0] - 5.5 * s, head[1] - 0.5 * s), (head[0] - 1 * s, head[1] - 6.5 * s),
        (head[0] + 4 * s, head[1] - 5.5 * s), (head[0] + 5.5 * s, head[1] - 0.2 * s),
    ])
    for ox in (-2.0, 2.0):
        pygame.draw.ellipse(surf, (240, 240, 245), (head[0] + ox * s - 0.8 * s, head[1] - 0.7 * s, 1.6 * s, 1.2 * s))
        pygame.draw.circle(surf, (35, 50, 70), (int(head[0] + ox * s), int(head[1] - 0.2 * s)), max(1, int(0.45 * s)))
    pygame.draw.line(surf, sh, (head[0] - 2.2 * s, head[1] + 1.8 * s), (head[0] + 2.2 * s, head[1] + 1.8 * s), max(1, int(s)))


def draw_big_skeleton(surf, cx, cy, tile, t, hurt=False, attacking=0.0):
    """Larger, heavier skeleton — mithril cavern elite."""
    # Temporarily boost art scale relative to tile for a bulkier silhouette
    draw_skeleton(surf, cx, cy - 4, int(tile * 1.35), t, hurt=hurt, attacking=attacking)


def draw_spider(surf, cx, cy, tile, t, hurt=False, attacking=0.0):
    """Giant dungeon spider — round abdomen, cephalothorax, eight jointed legs."""
    s = _s(tile, "monster") * 0.95
    body = (120, 50, 50) if hurt else (48, 42, 52)
    hi, mid, sh, deep = rs.material(body)
    abdomen = (150, 60, 55) if hurt else (62, 52, 68)
    a_hi, a_mid, a_sh, a_deep = rs.material(abdomen)
    atk = max(0.0, min(1.0, float(attacking or 0)))
    bob = math.sin(t * 5.5) * 0.6 * s
    lunge = math.sin(atk * math.pi) * 4.5 * s
    cy_base = cy + bob

    rs.draw_contact_shadow(surf, cx, cy + 8 * s, 16 * s, 4.2 * s, 140)
    rs.draw_cast_shadow(surf, cx + 2 * s, cy + 8.5 * s, 17 * s, 4.5 * s, 95)

    # Eight legs (4 per side) — far pair first
    gait = t * 7.0
    for side in (-1, 1):
        for i, (ox, reach, phase) in enumerate((
            (-2.5, 14, 0.0),
            (-0.5, 16, 1.2),
            (2.0, 15, 2.4),
            (4.5, 12, 3.5),
        )):
            lift = max(0.0, math.sin(gait + phase + (0.8 if side > 0 else 0))) * (1.8 * s if atk < 0.2 else 0.6 * s)
            hip = (cx + ox * s + lunge * 0.15, cy_base + 1 * s)
            knee = (hip[0] + side * reach * 0.55 * s, hip[1] + 2 * s - lift)
            foot = (hip[0] + side * reach * s, cy_base + 7.5 * s - lift * 0.3)
            rs.draw_volume_limb(surf, *hip, *knee, 1.05 * s, mid, deep, taper=0.7, bulge=0.0)
            rs.draw_volume_limb(surf, *knee, *foot, 0.85 * s, sh, deep, taper=0.65, bulge=0.0)
            pygame.draw.circle(surf, deep, (int(foot[0]), int(foot[1])), max(1, int(0.9 * s)))

    # Abdomen (rear bulb)
    ax = cx - 6 * s + lunge * 0.1
    ay = cy_base + 0.5 * s
    rs.draw_volume(surf, abdomen, [
        (ax - 7 * s, ay + 2 * s), (ax - 5 * s, ay - 5 * s),
        (ax + 2 * s, ay - 6 * s), (ax + 5 * s, ay - 1 * s),
        (ax + 3 * s, ay + 5 * s), (ax - 4 * s, ay + 6 * s),
    ], a_deep, 1)
    # Markings
    pygame.draw.line(surf, a_sh, (ax - 2 * s, ay - 3 * s), (ax + 1 * s, ay + 2 * s), max(1, int(s)))
    pygame.draw.circle(surf, a_hi, (int(ax - 1 * s), int(ay - 1 * s)), max(2, int(1.6 * s)))

    # Cephalothorax
    hx = cx + 4 * s + lunge * 0.4
    hy = cy_base - 1 * s
    rs.draw_volume(surf, body, [
        (hx - 5 * s, hy + 2 * s), (hx - 4 * s, hy - 4 * s),
        (hx + 3 * s, hy - 5 * s), (hx + 6 * s, hy - 1 * s),
        (hx + 4 * s, hy + 3.5 * s), (hx - 2 * s, hy + 4 * s),
    ], deep, 1)

    # Eyes cluster
    for ox, oy in ((-1.2, -1.5), (0.6, -2.0), (2.2, -1.2), (0.2, -0.2)):
        pygame.draw.circle(surf, (220, 60, 50) if not hurt else (255, 200, 80),
                           (int(hx + ox * s), int(hy + oy * s)), max(1, int(0.85 * s)))
        pygame.draw.circle(surf, (20, 10, 10), (int(hx + ox * s + 0.2 * s), int(hy + oy * s)), max(1, int(0.3 * s)))

    # Fangs / chelicerae
    fang_reach = 3.5 * s + abs(math.sin(atk * math.pi)) * 2.5 * s
    for side in (-1, 1):
        tip = (hx + 5 * s + fang_reach * 0.3, hy + side * 2.2 * s + 1 * s)
        rs.draw_poly(surf, deep, [
            (hx + 3 * s, hy + side * 1.2 * s),
            tip,
            (hx + 3.5 * s, hy + side * 2.5 * s),
        ], None, 0)

    # Pedipalps
    for side in (-1, 1):
        pygame.draw.line(surf, mid,
                         (hx + 4 * s, hy + side * 2 * s),
                         (hx + 8 * s + lunge * 0.2, hy + side * 4 * s),
                         max(2, int(1.2 * s)))


def draw_dragon(surf, cx, cy, tile, t, hurt=False, attacking=0.0):
    """Quadrapedal dragon — wings, scaled body, horned head, coiled tail."""
    s = _s(tile, "monster") * 1.2
    bob = math.sin(t * 3.2) * 1.0
    body = (55, 40, 40) if hurt else (42, 115, 68)
    hi, mid, sh, deep = rs.material(body)
    wing = (32, 85, 52) if not hurt else (70, 40, 40)
    belly = (175, 155, 85) if not hurt else (160, 100, 70)
    cy += bob
    atk = max(0.0, min(1.0, float(attacking or 0)))
    lunge = math.sin(atk * math.pi) * 6 * s

    rs.draw_cast_shadow(surf, cx + 2 * s, cy + 15 * s, 22 * s, 5.5 * s, 130, irregular=True, seed=int(cx))
    # Wings (membrane + bone spars)
    flap = math.sin(t * 4) * 3.5 * s
    for side in (-1, 1):
        spar = [
            (cx + side * 3 * s, cy - 1 * s),
            (cx + side * 26 * s, cy - 16 * s - flap * side * 0.3),
            (cx + side * 20 * s, cy + 1 * s),
            (cx + side * 6 * s, cy + 3 * s),
        ]
        rs.draw_volume(surf, wing, spar, deep, 1)
        pygame.draw.line(surf, deep, (cx + side * 3 * s, cy - 1 * s), (cx + side * 24 * s, cy - 14 * s - flap * 0.2), max(2, int(1.5 * s)))
        pygame.draw.line(surf, deep, (cx + side * 8 * s, cy), (cx + side * 18 * s, cy - 6 * s), max(1, int(s)))
    # Body barrel + belly
    rs.draw_volume(surf, body, [
        (cx - 13 * s, cy + 3 * s),
        (cx - 9 * s, cy - 7 * s),
        (cx + 10 * s + lunge * 0.3, cy - 9 * s),
        (cx + 15 * s + lunge, cy + 1 * s),
        (cx + 9 * s, cy + 10 * s),
        (cx - 9 * s, cy + 10 * s),
    ], deep, 1)
    rs.draw_poly(surf, belly, [
        (cx - 5 * s, cy + 2 * s), (cx + 8 * s, cy + 1 * s),
        (cx + 6 * s, cy + 8 * s), (cx - 4 * s, cy + 8 * s),
    ], None, 0)
    # Scale ridges
    for i in range(4):
        yy = cy - 5 * s + i * 2.5 * s
        pygame.draw.line(surf, sh, (cx - 6 * s, yy), (cx + 8 * s, yy), 1)
    # Legs
    for ox in (-6, 4):
        rs.draw_volume_limb(surf, cx + ox * s, cy + 6 * s, cx + ox * s + 2 * s, cy + 14 * s, 1.6 * s, deep, deep, taper=0.7, bulge=0.05)
        pygame.draw.circle(surf, sh, (int(cx + (ox + 2) * s), int(cy + 14 * s)), max(2, int(1.8 * s)))
    # Neck + head
    rs.draw_volume_limb(surf, cx + 10 * s, cy - 5 * s, cx + 20 * s + lunge, cy - 13 * s, 2.4 * s, body, deep, taper=0.75, bulge=0.08)
    head = (cx + 22 * s + lunge, cy - 15 * s)
    rs.draw_volume(surf, body, [
        (head[0] - 4 * s, head[1] + 2 * s), (head[0] - 3 * s, head[1] - 3 * s),
        (head[0] + 5 * s, head[1] - 4 * s), (head[0] + 9 * s, head[1]),
        (head[0] + 5 * s, head[1] + 3 * s), (head[0] - 1 * s, head[1] + 3.5 * s),
    ], deep, 1)
    pygame.draw.circle(surf, (255, 210, 50), (int(head[0] + 2 * s), int(head[1] - 1 * s)), max(2, int(1.5 * s)))
    pygame.draw.circle(surf, (20, 18, 14), (int(head[0] + 2.3 * s), int(head[1] - 0.8 * s)), max(1, int(0.6 * s)))
    # Jaws
    rs.draw_poly(surf, deep, [
        (head[0] + 5 * s, head[1] + 0.5 * s),
        (head[0] + 13 * s, head[1] - 1 * s),
        (head[0] + 5 * s, head[1] + 3 * s),
    ], None, 0)
    if atk > 0.25:
        flame = (255, 140 + int(40 * atk), 40)
        pygame.draw.circle(surf, flame, (int(head[0] + 15 * s), int(head[1])), max(2, int(3.5 * s * atk)))
        pygame.draw.circle(surf, (255, 230, 120), (int(head[0] + 14 * s), int(head[1])), max(1, int(1.5 * s * atk)))
    # Horns
    for ox, oy in ((0, -3), (4, -2.5)):
        pygame.draw.line(surf, (220, 210, 175), (head[0] + ox * s, head[1] + oy * s), (head[0] + (ox - 1) * s, head[1] - 9 * s), max(2, int(1.6 * s)))
    # Tail with barb
    pygame.draw.lines(surf, sh, False, [
        (cx - 12 * s, cy + 4 * s), (cx - 20 * s, cy + 2 * s), (cx - 26 * s, cy + 8 * s),
    ], max(3, int(2.8 * s)))
    rs.draw_poly(surf, hi, [
        (cx - 25 * s, cy + 7 * s), (cx - 30 * s, cy + 6 * s), (cx - 26 * s, cy + 11 * s),
    ], deep, 1)


def draw_pet_cat(surf, cx, cy, tile, t, hurt=False, attacking=0.0, moving=False, facing=1):
    """Orange tabby — volumetric body, walk gait, arched attack pounce."""
    facing = 1 if facing >= 0 else -1
    s = _s(tile, "pet") * 0.98
    fur = (200, 90, 70) if hurt else (218, 138, 68)
    hi, mid, sh, deep = rs.material(fur)
    cream = (242, 210, 170)
    atk = max(0.0, min(1.0, float(attacking or 0)))
    gait = (t * 11.0) if moving else (t * 2.2)
    bob = abs(math.sin(gait)) * (1.4 if moving else 0.35) * s
    lunge = math.sin(atk * math.pi) * 5.5 * s * facing
    lean = math.sin(atk * math.pi) * 0.15
    cy_base = cy + bob
    rs.draw_contact_shadow(surf, cx, cy + 9.5 * s, 11 * s, 3.2 * s, 135)
    rs.draw_cast_shadow(surf, cx + 1.5 * s * facing, cy + 10 * s, 12 * s, 3.4 * s, 90)

    # Walking legs (alternating lift)
    lifts = [math.sin(gait + i * 1.6) for i in range(4)]
    for i, ox in enumerate((-5.5, -1.5, 2.5, 6.0)):
        lift = max(0.0, lifts[i]) * (2.2 * s if moving else 0.3 * s)
        fx = cx + ox * s * facing + lunge * 0.15
        fy = cy_base + 4.2 * s - lift
        rs.draw_volume_limb(surf, fx, fy, fx + 0.4 * s * facing, fy + 5.2 * s + lift * 0.3,
                            1.15 * s, deep, deep, taper=0.75, bulge=0.05)
        pygame.draw.circle(surf, sh, (int(fx + 0.5 * s * facing), int(fy + 5.4 * s + lift * 0.2)), max(1, int(1.1 * s)))

    # Body barrel + belly
    bx = cx + lunge * 0.25
    rs.draw_volume(surf, fur, [
        (bx - 8.5 * s * facing, cy_base + 1 * s),
        (bx - 7 * s * facing, cy_base - 3.5 * s - lean * 4 * s),
        (bx + 6 * s * facing, cy_base - 4 * s - lean * 3 * s),
        (bx + 8.5 * s * facing, cy_base + 1.5 * s),
        (bx + 5 * s * facing, cy_base + 5.5 * s),
        (bx - 5 * s * facing, cy_base + 5.5 * s),
    ], deep, 1)
    rs.draw_poly(surf, cream, [
        (bx - 3 * s * facing, cy_base + 1.5 * s),
        (bx + 4 * s * facing, cy_base + 1.2 * s),
        (bx + 3 * s * facing, cy_base + 4.5 * s),
        (bx - 2.5 * s * facing, cy_base + 4.5 * s),
    ], None, 0)
    # Stripe marks
    for i in range(3):
        yy = cy_base - 2.5 * s + i * 1.8 * s
        pygame.draw.line(surf, sh, (bx - 5 * s * facing, yy), (bx + 4 * s * facing, yy), max(1, int(s * 0.35)))

    # Head
    hx = bx + 7.2 * s * facing + lunge * 0.35
    hy = cy_base - 4.2 * s - lean * 5 * s
    rs.draw_volume(surf, fur, [
        (hx - 4.2 * s, hy + 1.5 * s), (hx - 3.5 * s, hy - 3.5 * s),
        (hx + 1.5 * s * facing, hy - 4.5 * s), (hx + 4.5 * s * facing, hy - 2 * s),
        (hx + 4.8 * s * facing, hy + 2 * s), (hx + 1 * s * facing, hy + 3.8 * s),
        (hx - 2.5 * s, hy + 3.5 * s),
    ], deep, 1)
    # Ears
    for side, ox in ((-1, -2.2), (1, 2.0)):
        tip_x = hx + (ox + side * 2.8) * s * facing
        tip_y = hy - 8.5 * s + (0.4 if side > 0 else 0) * s
        rs.draw_poly(surf, mid, [
            (hx + ox * s * facing, hy - 2.5 * s),
            (tip_x, tip_y),
            (hx + (ox + side * 1.6) * s * facing, hy - 2.2 * s),
        ], deep, 1)
        rs.draw_poly(surf, (255, 165, 150), [
            (hx + ox * s * facing, hy - 2.8 * s),
            (hx + (ox + side * 1.5) * s * facing, tip_y + 2.5 * s),
            (hx + (ox + side * 0.6) * s * facing, hy - 2.5 * s),
        ], None, 0)
    # Face
    for ox in (-1.5, 1.6):
        ex = hx + ox * s * facing
        pygame.draw.ellipse(surf, (55, 210, 90), (ex - 1.1 * s, hy - 0.9 * s, 2.2 * s, 2.5 * s))
        pygame.draw.circle(surf, (18, 18, 16), (int(ex + 0.15 * s * facing), int(hy)), max(1, int(0.55 * s)))
        pygame.draw.circle(surf, (255, 255, 255), (int(ex - 0.35 * s), int(hy - 0.45 * s)), max(1, int(0.25 * s)))
    rs.draw_poly(surf, (50, 35, 30), [
        (hx - 0.5 * s, hy + 1.4 * s), (hx + 0.5 * s, hy + 1.4 * s), (hx, hy + 2.6 * s),
    ], None, 0)
    for side in (-1, 1):
        pygame.draw.line(surf, deep, (hx + side * 0.8 * s, hy + 1.8 * s), (hx + side * 4.5 * s, hy + 0.6 * s), 1)
        pygame.draw.line(surf, deep, (hx + side * 0.8 * s, hy + 2.2 * s), (hx + side * 4.5 * s, hy + 2.8 * s), 1)
    # Tail sway
    sway = math.sin(t * 3.5 + (1.5 if moving else 0)) * 3.5 * s
    pygame.draw.lines(surf, sh, False, [
        (bx - 7.5 * s * facing, cy_base + 1 * s),
        (bx - 12 * s * facing + sway * 0.3, cy_base - 4 * s),
        (bx - 11 * s * facing + sway, cy_base - 1 * s),
    ], max(2, int(2.0 * s)))
    pygame.draw.circle(surf, mid, (int(bx - 11 * s * facing + sway), int(cy_base - 1 * s)), max(2, int(1.5 * s)))


def draw_pet_husky(surf, cx, cy, tile, t, hurt=False, attacking=0.0, moving=False, facing=1):
    """White husky — thick fur volumes, trotting gait, lunging bite."""
    facing = 1 if facing >= 0 else -1
    s = _s(tile, "pet") * 1.05
    fur = (200, 155, 155) if hurt else (242, 244, 248)
    hi, mid, sh, deep = rs.material(fur)
    grey = (155, 160, 170)
    atk = max(0.0, min(1.0, float(attacking or 0)))
    gait = (t * 10.0) if moving else (t * 2.0)
    bob = abs(math.sin(gait)) * (1.5 if moving else 0.4) * s
    lunge = math.sin(atk * math.pi) * 6 * s * facing
    cy_base = cy + bob
    rs.draw_contact_shadow(surf, cx, cy + 10 * s, 13 * s, 3.4 * s, 140)
    rs.draw_cast_shadow(surf, cx + 2 * s * facing, cy + 10.5 * s, 14 * s, 3.6 * s, 95)

    lifts = [math.sin(gait + i * 1.55) for i in range(4)]
    for i, ox in enumerate((-6.5, -1.5, 3.5, 8.0)):
        lift = max(0.0, lifts[i]) * (2.4 * s if moving else 0.25 * s)
        fx = cx + ox * s * facing + lunge * 0.12
        fy = cy_base + 5 * s - lift
        rs.draw_volume_limb(surf, fx, fy, fx + 0.5 * s * facing, fy + 5.5 * s + lift * 0.25,
                            1.35 * s, grey, deep, taper=0.7, bulge=0.06)
        pygame.draw.circle(surf, deep, (int(fx + 0.6 * s * facing), int(fy + 5.7 * s)), max(2, int(1.3 * s)))

    bx = cx + lunge * 0.2
    # Solid bushy plume (filled curl) drawn under the body, then sealed over the rear outline
    sway = math.sin(t * 3.2 + (1.0 if moving else 0)) * 0.8 * s
    tail_chain = [
        (bx - 8.0 * s * facing, cy_base + 1.2 * s, 3.4 * s),
        (bx - 9.0 * s * facing + sway * 0.1, cy_base - 1.5 * s, 3.3 * s),
        (bx - 9.2 * s * facing + sway * 0.2, cy_base - 4.0 * s, 3.2 * s),
        (bx - 8.0 * s * facing + sway * 0.35, cy_base - 6.2 * s, 3.1 * s),
        (bx - 6.0 * s * facing + sway * 0.45, cy_base - 7.5 * s, 3.0 * s),
        (bx - 4.0 * s * facing + sway * 0.4, cy_base - 7.0 * s, 2.9 * s),
        (bx - 3.0 * s * facing + sway * 0.3, cy_base - 5.2 * s, 2.8 * s),
        (bx - 4.0 * s * facing + sway * 0.2, cy_base - 3.2 * s, 2.7 * s),
        (bx - 5.5 * s * facing + sway * 0.15, cy_base - 2.0 * s, 2.8 * s),
        (bx - 6.5 * s * facing + sway * 0.1, cy_base - 0.5 * s, 2.6 * s),
    ]
    for tx, ty, rad in tail_chain:
        pygame.draw.circle(surf, mid, (int(tx), int(ty)), max(2, int(rad)))
        pygame.draw.circle(surf, hi, (int(tx - 0.3 * s), int(ty - 0.4 * s)), max(1, int(rad * 0.32)))

    rs.draw_volume(surf, fur, [
        (bx - 10 * s * facing, cy_base + 2 * s),
        (bx - 8 * s * facing, cy_base - 4 * s),
        (bx + 7 * s * facing, cy_base - 5 * s),
        (bx + 10 * s * facing, cy_base + 1.5 * s),
        (bx + 6 * s * facing, cy_base + 6.5 * s),
        (bx - 6 * s * facing, cy_base + 6.5 * s),
    ], deep, 1)
    rs.draw_poly(surf, grey, [
        (bx - 4 * s * facing, cy_base + 1 * s),
        (bx + 5 * s * facing, cy_base + 0.8 * s),
        (bx + 4 * s * facing, cy_base + 5 * s),
        (bx - 3 * s * facing, cy_base + 5 * s),
    ], None, 0)
    # Seal rear outline into the plume
    for ox, oy, rad in (
        (-10.2, 2.0, 3.0), (-9.5, 0.0, 2.9), (-9.0, -2.0, 2.8),
        (-8.5, -4.0, 2.7), (-7.5, -5.5, 2.6), (-6.0, -6.0, 2.5),
    ):
        pygame.draw.circle(
            surf, mid,
            (int(bx + ox * s * facing + sway * 0.1), int(cy_base + oy * s)),
            max(2, int(rad * s)),
        )

    hx = bx + 8.5 * s * facing + lunge * 0.4
    hy = cy_base - 4.5 * s
    rs.draw_volume(surf, fur, [
        (hx - 5 * s, hy + 2 * s), (hx - 4 * s, hy - 4 * s),
        (hx + 2 * s * facing, hy - 5.5 * s), (hx + 5.5 * s * facing, hy - 2 * s),
        (hx + 5.2 * s * facing, hy + 2.5 * s), (hx, hy + 4 * s),
    ], deep, 1)
    # Pointed ears
    for ox, tip in ((-3.5, -3.5), (2.5, 4.5)):
        rs.draw_poly(surf, grey, [
            (hx + ox * s * facing, hy - 2 * s),
            (hx + (ox + tip * 0.15) * s * facing, hy - 10 * s),
            (hx + (ox + 2.2) * s * facing, hy - 2.5 * s),
        ], deep, 1)
    # Face mask + ice-blue eyes
    rs.draw_poly(surf, (32, 34, 40), [
        (hx - 1.5 * s * facing, hy - 1 * s),
        (hx + 4.5 * s * facing, hy - 1.5 * s),
        (hx + 4 * s * facing, hy + 2.5 * s),
        (hx - 0.5 * s * facing, hy + 2.8 * s),
    ], None, 0)
    for ox in (-0.3, 2.8):
        ex = hx + ox * s * facing
        pygame.draw.circle(surf, (90, 185, 255), (int(ex), int(hy - 0.2 * s)), max(2, int(1.35 * s)))
        pygame.draw.circle(surf, (20, 28, 40), (int(ex + 0.2 * s * facing), int(hy - 0.1 * s)), max(1, int(0.5 * s)))
        pygame.draw.circle(surf, (255, 255, 255), (int(ex - 0.35 * s), int(hy - 0.5 * s)), max(1, int(0.3 * s)))
    # Tongue / open mouth on attack
    if atk > 0.3:
        rs.draw_poly(surf, (220, 90, 100), [
            (hx + 3 * s * facing, hy + 2.2 * s),
            (hx + 6.5 * s * facing, hy + 2.8 * s),
            (hx + 3.2 * s * facing, hy + 3.8 * s),
        ], None, 0)


def draw_pet_skeleton(surf, cx, cy, tile, t, hurt=False, attacking=0.0, moving=False, facing=1):
    """Compact bone companion — ribs, skull, jointed limbs with walk + swing."""
    facing = 1 if facing >= 0 else -1
    s = _s(tile, "pet") * 0.92
    bone = (200, 70, 70) if hurt else (230, 222, 200)
    hi, mid, sh, deep = rs.material(bone)
    atk = max(0.0, min(1.0, float(attacking or 0)))
    gait = (t * 10.5) if moving else (t * 2.4)
    bob = abs(math.sin(gait)) * (1.2 if moving else 0.5) * s
    swing = math.sin(atk * math.pi) * 1.4 * facing
    cy_base = cy + bob
    rs.draw_contact_shadow(surf, cx, cy + 11 * s, 9 * s, 2.8 * s, 120)

    # Legs
    for side, phase in ((-1, 0), (1, math.pi)):
        hip = (cx + side * 2.8 * s, cy_base + 1 * s)
        ang = rs.DOWN + math.sin(gait + phase) * (0.45 if moving else 0.08) + side * 0.05
        knee = rs.joint(*hip, ang, 4.5 * s)
        foot = rs.joint(*knee, ang + 0.08, 4.2 * s)
        rs.draw_volume_limb(surf, *hip, *knee, 0.95 * s, bone, deep, taper=0.8, bulge=0.0)
        rs.draw_volume_limb(surf, *knee, *foot, 0.85 * s, bone, deep, taper=0.75, bulge=0.0)
        pygame.draw.circle(surf, mid, (int(knee[0]), int(knee[1])), max(2, int(1.3 * s)))

    # Spine + ribs
    pygame.draw.line(surf, mid, (cx, cy_base + 1 * s), (cx, cy_base - 7.5 * s), max(2, int(2.2 * s)))
    for i in range(4):
        yy = cy_base - 6.5 * s + i * 1.6 * s
        w = 5.2 * s - i * 0.3 * s
        pygame.draw.arc(surf, mid, (cx - w, yy - 1 * s, w * 2, 2.8 * s), 0.2, math.pi - 0.2, max(1, int(1.3 * s)))
    # Arms + bone blade
    sh_l = (cx - 3.5 * s, cy_base - 5 * s)
    sh_r = (cx + 3.5 * s, cy_base - 5 * s)
    hand_l = rs.joint(*sh_l, rs.DOWN + 0.4 * facing, 6 * s)
    hand_r = rs.joint(*sh_r, rs.DOWN - 0.2 * facing + swing, 6.5 * s)
    rs.draw_volume_limb(surf, *sh_l, *hand_l, 0.85 * s, bone, deep)
    rs.draw_volume_limb(surf, *sh_r, *hand_r, 0.85 * s, bone, deep)
    tip = (hand_r[0] + 4 * s * facing + math.sin(atk * math.pi) * 3 * s * facing,
           hand_r[1] - 10 * s - abs(math.sin(atk * math.pi)) * 2 * s)
    rs.draw_volume(surf, (175, 180, 188), [hand_r, (hand_r[0] + 1.5 * s * facing, hand_r[1]), tip,
                                           (hand_r[0] - 0.8 * s * facing, hand_r[1] - 1.5 * s)], deep, 1)
    # Skull
    head = (cx + 0.3 * s * facing, cy_base - 10 * s)
    rs.draw_volume(surf, bone, [
        (head[0] - 3.8 * s, head[1] + 1 * s), (head[0] - 3.2 * s, head[1] - 3 * s),
        (head[0], head[1] - 4.5 * s), (head[0] + 3.2 * s, head[1] - 3 * s),
        (head[0] + 3.8 * s, head[1] + 1 * s), (head[0] + 1.5 * s, head[1] + 2.8 * s),
        (head[0] - 1.5 * s, head[1] + 2.8 * s),
    ], deep, 1)
    for ox in (-1.5, 1.5):
        pygame.draw.ellipse(surf, (16, 14, 12), (head[0] + ox * s - 1.2 * s, head[1] - 1.4 * s, 2.4 * s, 2.6 * s))
        pygame.draw.circle(surf, (60, 200, 90), (int(head[0] + ox * s), int(head[1] - 0.3 * s)), max(1, int(0.45 * s)))
    pygame.draw.rect(surf, sh, (head[0] - 2 * s, head[1] + 2 * s, 4 * s, 1.2 * s))


def draw_pet_dragon(surf, cx, cy, tile, t, hurt=False, attacking=0.0, moving=False, facing=1):
    """Mini dragon companion — wings flap, trot, fire breath on attack."""
    facing = 1 if facing >= 0 else -1
    s = _s(tile, "pet") * 0.72
    body = (55, 40, 40) if hurt else (48, 125, 72)
    hi, mid, sh, deep = rs.material(body)
    wing_c = (35, 95, 55) if not hurt else (80, 45, 45)
    belly = (185, 165, 95) if not hurt else (160, 100, 70)
    atk = max(0.0, min(1.0, float(attacking or 0)))
    gait = (t * 9.0) if moving else (t * 3.5)
    bob = math.sin(gait) * (1.3 if moving else 0.8) * s
    lunge = math.sin(atk * math.pi) * 5 * s * facing
    flap = math.sin(t * (7 if moving else 4.5)) * 3.2 * s
    cy_base = cy + bob
    rs.draw_contact_shadow(surf, cx, cy + 11 * s, 14 * s, 3.5 * s, 130)
    rs.draw_cast_shadow(surf, cx + 2 * s * facing, cy + 11.5 * s, 15 * s, 3.8 * s, 95)

    # Wings
    for side in (-1, 1):
        rs.draw_volume(surf, wing_c, [
            (cx + side * 2 * s, cy_base - 1 * s),
            (cx + side * 16 * s, cy_base - 12 * s - flap * side * 0.4),
            (cx + side * 13 * s, cy_base + 1 * s),
            (cx + side * 4 * s, cy_base + 2 * s),
        ], deep, 1)
        pygame.draw.line(surf, deep, (cx + side * 2 * s, cy_base), (cx + side * 14 * s, cy_base - 10 * s - flap * 0.2), max(1, int(s)))

    # Body
    bx = cx + lunge * 0.25
    rs.draw_volume(surf, body, [
        (bx - 9 * s * facing, cy_base + 2 * s),
        (bx - 6 * s * facing, cy_base - 5 * s),
        (bx + 7 * s * facing, cy_base - 6 * s),
        (bx + 10 * s * facing, cy_base + 1 * s),
        (bx + 6 * s * facing, cy_base + 7 * s),
        (bx - 5 * s * facing, cy_base + 7 * s),
    ], deep, 1)
    rs.draw_poly(surf, belly, [
        (bx - 3 * s * facing, cy_base + 0.5 * s),
        (bx + 5 * s * facing, cy_base),
        (bx + 4 * s * facing, cy_base + 5 * s),
        (bx - 2 * s * facing, cy_base + 5 * s),
    ], None, 0)
    # Legs
    for ox in (-4, 4):
        lift = max(0.0, math.sin(gait + ox)) * (1.8 * s if moving else 0.2 * s)
        rs.draw_volume_limb(surf, bx + ox * s * facing, cy_base + 4 * s,
                            bx + (ox + 1) * s * facing, cy_base + 10 * s - lift,
                            1.2 * s, deep, deep, taper=0.7, bulge=0.0)

    # Neck + head
    hx = bx + 11 * s * facing + lunge * 0.4
    hy = cy_base - 8 * s
    rs.draw_volume_limb(surf, bx + 6 * s * facing, cy_base - 3 * s, hx, hy, 1.7 * s, body, deep, taper=0.75, bulge=0.05)
    rs.draw_volume(surf, body, [
        (hx - 2.5 * s, hy + 1.5 * s), (hx - 2 * s, hy - 2.5 * s),
        (hx + 3 * s * facing, hy - 3 * s), (hx + 5.5 * s * facing, hy),
        (hx + 3 * s * facing, hy + 2 * s), (hx, hy + 2.5 * s),
    ], deep, 1)
    pygame.draw.circle(surf, (255, 215, 60), (int(hx + 1.2 * s * facing), int(hy - 0.5 * s)), max(2, int(1.2 * s)))
    pygame.draw.circle(surf, (20, 18, 14), (int(hx + 1.4 * s * facing), int(hy - 0.4 * s)), max(1, int(0.45 * s)))
    # Horns
    pygame.draw.line(surf, (220, 210, 175), (hx, hy - 2 * s), (hx - 1 * s * facing, hy - 6.5 * s), max(2, int(1.2 * s)))
    pygame.draw.line(surf, (220, 210, 175), (hx + 2 * s * facing, hy - 2 * s), (hx + 3.5 * s * facing, hy - 6.5 * s), max(2, int(1.2 * s)))
    # Fire breath
    if atk > 0.25:
        flame = (255, 145 + int(35 * atk), 45)
        fx = hx + (8 + 4 * atk) * s * facing
        fy = hy + 0.5 * s
        pygame.draw.circle(surf, flame, (int(fx), int(fy)), max(2, int(2.8 * s * atk)))
        pygame.draw.circle(surf, (255, 230, 120), (int(fx - 1 * s * facing), int(fy)), max(1, int(1.4 * s * atk)))
    # Tail
    sway = math.sin(t * 4) * 2 * s
    pygame.draw.lines(surf, sh, False, [
        (bx - 8 * s * facing, cy_base + 2 * s),
        (bx - 14 * s * facing, cy_base + sway * 0.3),
        (bx - 17 * s * facing + sway * 0.2, cy_base + 4 * s),
    ], max(2, int(2.0 * s)))
    rs.draw_poly(surf, hi, [
        (bx - 16 * s * facing, cy_base + 3.5 * s),
        (bx - 20 * s * facing, cy_base + 3 * s),
        (bx - 17 * s * facing, cy_base + 6 * s),
    ], deep, 1)


def draw_pet(surf, sprite, cx, cy, tile, t, hurt=False, attacking=0.0, moving=False, facing=1):
    drawers = {
        "pet_cat": draw_pet_cat,
        "cat": draw_pet_cat,
        "pet_husky": draw_pet_husky,
        "husky": draw_pet_husky,
        "pet_skeleton": draw_pet_skeleton,
        "skeleton_pet": draw_pet_skeleton,
        "pet_dragon": draw_pet_dragon,
        "dragon_pet": draw_pet_dragon,
    }
    fn = drawers.get(sprite, draw_pet_cat)
    try:
        fn(surf, cx, cy, tile, t, hurt=hurt, attacking=attacking, moving=moving, facing=facing)
    except TypeError:
        fn(surf, cx, cy, tile, t, hurt=hurt, attacking=attacking)


MONSTER_DRAWERS.update({
    "orc": draw_orc,
    "slime": draw_slime,
    "giant": draw_giant,
    "big_skeleton": draw_big_skeleton,
    "spider": draw_spider,
    "dragon": draw_dragon,
})


def draw_building_roof(surf, rect, kind="house", style=0, alpha=245, material=None):
    """Roof overlay for enterable buildings — textured wood/brick facade + roof."""
    x, y, w, h = rect.x, rect.y, rect.w, rect.h
    roof_surf = pygame.Surface((max(1, int(w + 28)), max(1, int(h + 32))), pygame.SRCALPHA)
    ox, oy = 14, 16

    if material is None:
        if kind == "smithy":
            material = "brick"
        else:
            material = "brick" if (style % 2 == 1) else "wood"

    wood = material != "brick"
    if wood:
        roof = (102, 58, 42)
        chimney = style % 3 != 2
    else:
        roof = (68, 72, 80)  # slate grey
        chimney = True
    if kind == "smithy":
        roof = (62, 58, 64)
        chimney = True

    r_hi = tuple(min(255, c + 40) for c in roof)
    r_sh = tuple(max(0, c - 35) for c in roof)

    # Textured upper walls under eaves
    wall_rect = pygame.Rect(ox, int(oy + h * 0.28), int(w), int(h * 0.42))
    if wood:
        _fill_wood_face(roof_surf, wall_rect, seed_x=int(x), seed_y=int(y), alpha=alpha)
    else:
        _fill_brick_face(roof_surf, wall_rect, seed_x=int(x), seed_y=int(y), alpha=alpha)
        # Stone sill under eaves
        pygame.draw.rect(
            roof_surf, (90, 92, 98, alpha),
            (ox, int(oy + h * 0.28), w, max(3, int(h * 0.04))),
        )

    # Side depth plane
    side_w = max(5, int(w * 0.07))
    side_col = (110, 84, 52, alpha) if wood else (88, 90, 96, alpha)
    _poly(roof_surf, side_col, [
        (ox + w, oy + h * 0.28),
        (ox + w + side_w, oy + h * 0.32),
        (ox + w + side_w, oy + h * 0.70),
        (ox + w, oy + h * 0.70),
    ], (40, 30, 28, min(255, alpha + 20)), 1)

    # Roof shade plane (right)
    shade_pts = [
        (ox + w * 0.5, oy - 2),
        (ox + w + 10 + side_w, oy + h * 0.34),
        (ox + w + 8 + side_w, oy + h * 0.52),
        (ox + w * 0.5 + 2, oy + h * 0.42),
    ]
    _poly(roof_surf, (*r_sh, alpha), shade_pts, (40, 30, 28, min(255, alpha + 20)), 1)

    # Main roof body
    pts = [
        (ox - 10, oy + h * 0.34),
        (ox + w * 0.5, oy - 6),
        (ox + w + 10, oy + h * 0.34),
        (ox + w + 6, oy + h * 0.52),
        (ox - 6, oy + h * 0.52),
    ]
    _poly(roof_surf, (*roof, alpha), pts, (40, 30, 28, min(255, alpha + 20)), 2)

    # Shingle / slate courses
    for i in range(5):
        t = 0.18 + i * 0.12
        yy = oy - 4 + (oy + h * 0.50 - (oy - 4)) * t
        inset = 8 + i * 3
        col = (*r_sh, alpha) if i % 2 else (*(max(0, c - 18) for c in roof), alpha)
        pygame.draw.line(
            roof_surf, col,
            (ox - 8 + inset, yy), (ox + w + 8 - inset, yy),
            1 if wood else 2,
        )
        if not wood and i < 4:
            # Vertical slate joints
            for j in range(4):
                xx = ox + w * (0.15 + j * 0.18)
                pygame.draw.line(
                    roof_surf, (*r_hi, min(180, alpha)),
                    (xx, yy), (xx + 2, yy + h * 0.08), 1,
                )

    # Ridge highlight + ridge beam
    pygame.draw.line(
        roof_surf, (*r_hi, alpha),
        (ox + w * 0.5, oy - 4), (ox + w * 0.32, oy + h * 0.30), 2,
    )
    pygame.draw.circle(roof_surf, (*r_hi, alpha), (int(ox + w * 0.5), int(oy - 2)), 3)

    # Eave underside shadow
    pygame.draw.line(
        roof_surf, (20, 16, 14, min(200, alpha)),
        (ox - 8, oy + h * 0.50), (ox + w + 8, oy + h * 0.50), 3,
    )

    # Simple windows peeking under eaves
    for wx_frac in (0.18, 0.62):
        wx = ox + w * wx_frac
        wy = oy + h * 0.42
        ww, wh = w * 0.14, h * 0.14
        pygame.draw.rect(roof_surf, (30, 28, 26, alpha), (wx - 2, wy - 2, ww + 4, wh + 4))
        pygame.draw.rect(roof_surf, (55, 95, 120, alpha), (wx, wy, ww, wh))
        pygame.draw.rect(roof_surf, (110, 160, 180, min(220, alpha)), (wx + 1, wy + 1, ww * 0.4, wh * 0.35))
        frame = (70, 48, 28, alpha) if wood else (50, 52, 56, alpha)
        pygame.draw.line(roof_surf, frame, (wx + ww * 0.5, wy), (wx + ww * 0.5, wy + wh), 1)
        pygame.draw.line(roof_surf, frame, (wx, wy + wh * 0.5), (wx + ww, wy + wh * 0.5), 1)

    if chimney:
        chx = ox + w * 0.72
        brick_c = (96, 94, 100, alpha) if not wood else (88, 72, 58, alpha)
        pygame.draw.rect(roof_surf, brick_c, (chx, oy + h * 0.02, w * 0.12, h * 0.30))
        pygame.draw.rect(roof_surf, (70, 72, 78, alpha), (chx - 2, oy, w * 0.16, 5))
        pygame.draw.rect(roof_surf, (150, 148, 152, alpha), (chx, oy + h * 0.02, 2, h * 0.22))
        # Brick lines on chimney
        for i in range(3):
            yy = oy + h * 0.08 + i * h * 0.07
            pygame.draw.line(roof_surf, (55, 56, 60, alpha), (chx, yy), (chx + w * 0.12, yy), 1)

    surf.blit(roof_surf, (x - ox, y - oy))


def draw_dungeon_entrance(surf, cx, cy, tile, t=0.0):
    """Stone arch — large landmark but not screen-filling (RS dungeon mouths)."""
    s = _s(tile, 'object') * 0.72
    # wide shadowed mouth
    pygame.draw.ellipse(surf, (12, 10, 16), (cx - 28 * s, cy - 4 * s, 56 * s, 22 * s))
    # pillars
    for ox in (-24, 16):
        pygame.draw.rect(surf, (88, 82, 78), (cx + ox * s, cy - 18 * s, 9 * s, 28 * s))
        pygame.draw.rect(surf, (55, 50, 48), (cx + ox * s, cy - 18 * s, 9 * s, 28 * s), max(1, int(s)))
        pygame.draw.rect(surf, (120, 110, 100), (cx + ox * s - 1 * s, cy - 20 * s, 11 * s, 4 * s))
    # arch top
    _poly(surf, (95, 88, 82), [
        (cx - 26 * s, cy - 14 * s),
        (cx - 12 * s, cy - 28 * s),
        (cx + 12 * s, cy - 28 * s),
        (cx + 26 * s, cy - 14 * s),
        (cx + 20 * s, cy - 10 * s),
        (cx - 20 * s, cy - 10 * s),
    ], (50, 45, 42), 2)
    # glowing interior
    pulse = int(20 + 15 * abs(math.sin(t * 2)))
    pygame.draw.ellipse(surf, (40 + pulse, 30, 70 + pulse), (cx - 12 * s, cy - 8 * s, 24 * s, 14 * s))
    # torch flickers on pillars
    for ox in (-18, 18):
        pygame.draw.circle(surf, (255, 160 + pulse, 40), (int(cx + ox * s), int(cy - 12 * s)), max(2, int(2.2 * s)))
    for ox in (-6, 0, 6):
        pygame.draw.circle(surf, (180, 140, 255), (int(cx + ox * s), int(cy - 18 * s)), max(1, int(1.0 * s)))


def draw_bank_booth(surf, cx, cy, tile, t=0.0):
    """Counter / booth — desk height vs player (RS bank counters)."""
    s = _s(tile, 'object') * 0.78
    # desk body
    pygame.draw.rect(surf, (92, 68, 48), (cx - 14 * s, cy - 2 * s, 28 * s, 12 * s))
    pygame.draw.rect(surf, (60, 42, 28), (cx - 14 * s, cy - 2 * s, 28 * s, 12 * s), max(1, int(s)))
    # top ledge
    pygame.draw.rect(surf, (140, 110, 78), (cx - 16 * s, cy - 6 * s, 32 * s, 5 * s))
    # brass plaque
    pygame.draw.rect(surf, (200, 170, 70), (cx - 8 * s, cy - 1 * s, 16 * s, 4 * s))
    pulse = int(20 + 10 * abs(math.sin(t * 3)))
    pygame.draw.circle(surf, (255, 220, 80), (int(cx - 10 * s), int(cy - 10 * s)), max(2, int(2.0 * s)))
    pygame.draw.circle(surf, (255, 200 + pulse // 2, 40), (int(cx - 6 * s), int(cy - 12 * s)), max(2, int(1.6 * s)))
    pygame.draw.rect(surf, (40, 44, 55), (cx - 11 * s, cy - 18 * s, 22 * s, 11 * s))
    for i in range(4):
        pygame.draw.line(
            surf, (90, 100, 120),
            (cx - 9 * s + i * 5.5 * s, cy - 16 * s),
            (cx - 9 * s + i * 5.5 * s, cy - 8 * s),
            max(1, int(s)),
        )


def draw_door(surf, cx, cy, tile, open_=False, t=0.0):
    """Wooden door with stone jamb — ~1.1× character height."""
    s = _s(tile, "object") * 0.85
    jam, jam_d = (118, 112, 104), (70, 66, 60)
    pygame.draw.rect(surf, jam, (cx - 9.5 * s, cy - 14 * s, 3 * s, 26 * s))
    pygame.draw.rect(surf, jam, (cx + 6.5 * s, cy - 14 * s, 3 * s, 26 * s))
    pygame.draw.rect(surf, jam, (cx - 9.5 * s, cy - 16 * s, 19 * s, 3.5 * s))
    pygame.draw.rect(surf, jam_d, (cx - 9.5 * s, cy - 16 * s, 19 * s, 3.5 * s), 1)
    pygame.draw.rect(surf, (72, 50, 34), (cx - 6.5 * s, cy - 13 * s, 13 * s, 23 * s), border_radius=1)
    pygame.draw.rect(surf, (45, 30, 20), (cx - 6.5 * s, cy - 13 * s, 13 * s, 23 * s), max(1, int(s)), border_radius=1)
    if open_:
        pygame.draw.rect(surf, (25, 20, 18), (cx - 5 * s, cy - 11 * s, 10 * s, 19 * s))
        pygame.draw.rect(surf, (95, 65, 42), (cx + 3 * s, cy - 11 * s, 4 * s, 19 * s))
    else:
        pygame.draw.rect(surf, (118, 82, 52), (cx - 5 * s, cy - 11 * s, 10 * s, 19 * s))
        for yy in (-7, -2, 3):
            pygame.draw.line(surf, (85, 58, 36), (cx - 4.5 * s, cy + yy * s), (cx + 4.5 * s, cy + yy * s), 1)
        pygame.draw.line(surf, (85, 58, 36), (cx - 1.5 * s, cy - 10 * s), (cx - 1.5 * s, cy + 7 * s), 1)
        pygame.draw.line(surf, (85, 58, 36), (cx + 1.5 * s, cy - 10 * s), (cx + 1.5 * s, cy + 7 * s), 1)
        pygame.draw.rect(surf, (90, 90, 98), (cx - 5 * s, cy - 9 * s, 10 * s, 1.4 * s))
        pygame.draw.rect(surf, (90, 90, 98), (cx - 5 * s, cy + 4 * s, 10 * s, 1.4 * s))
        pygame.draw.circle(surf, (210, 175, 70), (int(cx + 3.2 * s), int(cy)), max(2, int(1.3 * s)))
        pygame.draw.circle(surf, (140, 110, 40), (int(cx + 3.2 * s), int(cy)), max(1, int(0.55 * s)))


# ---------------------------------------------------------------------------
# Indoor furniture / decor (visual props; walkable tiles)
# ---------------------------------------------------------------------------

def draw_table(surf, cx, cy, tile, t=0.0):
    s = _s(tile, "object") * 0.62
    rs.draw_contact_shadow(surf, cx, cy + 6 * s, 12 * s, 3 * s, 120)
    wood, dark = (138, 98, 58), (72, 48, 28)
    for ox in (-7, 7):
        pygame.draw.rect(surf, dark, (cx + ox * s - 1.2 * s, cy - 1 * s, 2.4 * s, 8 * s))
    pygame.draw.rect(surf, wood, (cx - 11 * s, cy - 5 * s, 22 * s, 5 * s), border_radius=1)
    pygame.draw.rect(surf, dark, (cx - 11 * s, cy - 5 * s, 22 * s, 5 * s), 1, border_radius=1)
    pygame.draw.line(surf, rs.shade(wood, 35), (cx - 9 * s, cy - 4 * s), (cx + 9 * s, cy - 4 * s), 1)


def draw_chair(surf, cx, cy, tile, t=0.0, facing=1):
    s = _s(tile, "object") * 0.55
    facing = 1 if facing >= 0 else -1
    wood, dark = (120, 84, 50), (60, 40, 24)
    rs.draw_contact_shadow(surf, cx, cy + 6 * s, 7 * s, 2.4 * s, 110)
    pygame.draw.rect(surf, wood, (cx - 4 * s, cy + 1 * s, 8 * s, 2.5 * s))
    for ox in (-3.2, 3.2):
        pygame.draw.rect(surf, dark, (cx + ox * s - 0.8 * s, cy + 2 * s, 1.6 * s, 5 * s))
    # Backrest
    pygame.draw.rect(surf, wood, (cx - 4 * s * facing, cy - 8 * s, 2.2 * s, 10 * s))
    pygame.draw.rect(surf, dark, (cx - 4 * s * facing, cy - 8 * s, 2.2 * s, 10 * s), 1)
    pygame.draw.line(surf, rs.shade(wood, 30), (cx - 3 * s * facing, cy - 7 * s), (cx - 3 * s * facing, cy), 1)


def draw_bed(surf, cx, cy, tile, t=0.0):
    s = _s(tile, "object") * 0.7
    rs.draw_contact_shadow(surf, cx, cy + 5 * s, 14 * s, 3.2 * s, 125)
    frame, sheet, pillow = (92, 62, 38), (210, 205, 190), (235, 230, 220)
    pygame.draw.rect(surf, frame, (cx - 12 * s, cy - 2 * s, 24 * s, 8 * s), border_radius=1)
    pygame.draw.rect(surf, (55, 36, 22), (cx - 12 * s, cy - 2 * s, 24 * s, 8 * s), 1, border_radius=1)
    pygame.draw.rect(surf, sheet, (cx - 10 * s, cy - 4 * s, 16 * s, 6 * s))
    pygame.draw.rect(surf, pillow, (cx + 5 * s, cy - 5 * s, 6 * s, 5 * s), border_radius=2)
    pygame.draw.line(surf, (180, 175, 160), (cx - 9 * s, cy - 1 * s), (cx + 4 * s, cy - 1 * s), 1)
    # Headboard
    pygame.draw.rect(surf, frame, (cx + 10 * s, cy - 10 * s, 3 * s, 12 * s))


def draw_chest(surf, cx, cy, tile, t=0.0):
    s = _s(tile, "object") * 0.58
    rs.draw_contact_shadow(surf, cx, cy + 5 * s, 10 * s, 2.8 * s, 120)
    wood, band = (118, 78, 42), (160, 150, 70)
    pygame.draw.rect(surf, wood, (cx - 9 * s, cy - 3 * s, 18 * s, 9 * s), border_radius=2)
    pygame.draw.rect(surf, (60, 38, 20), (cx - 9 * s, cy - 3 * s, 18 * s, 9 * s), 1, border_radius=2)
    pygame.draw.rect(surf, rs.shade(wood, -20), (cx - 9 * s, cy - 6 * s, 18 * s, 4 * s), border_radius=2)
    pygame.draw.line(surf, band, (cx - 8 * s, cy), (cx + 8 * s, cy), max(2, int(s)))
    pygame.draw.circle(surf, band, (int(cx), int(cy + 1 * s)), max(2, int(1.4 * s)))
    pygame.draw.circle(surf, (40, 32, 18), (int(cx), int(cy + 1 * s)), max(1, int(0.55 * s)))


def draw_barrel(surf, cx, cy, tile, t=0.0):
    s = _s(tile, "object") * 0.55
    rs.draw_contact_shadow(surf, cx, cy + 6 * s, 7 * s, 2.5 * s, 115)
    wood, band = (130, 88, 48), (70, 55, 40)
    pygame.draw.ellipse(surf, wood, (cx - 6 * s, cy - 8 * s, 12 * s, 14 * s))
    pygame.draw.ellipse(surf, (55, 36, 20), (cx - 6 * s, cy - 8 * s, 12 * s, 14 * s), 1)
    pygame.draw.ellipse(surf, rs.shade(wood, 25), (cx - 5 * s, cy - 8.5 * s, 10 * s, 3.5 * s))
    for yy in (-4, 0, 4):
        pygame.draw.line(surf, band, (cx - 5.5 * s, cy + yy * s), (cx + 5.5 * s, cy + yy * s), max(1, int(s)))


def draw_crate(surf, cx, cy, tile, t=0.0):
    s = _s(tile, "object") * 0.55
    rs.draw_contact_shadow(surf, cx, cy + 5 * s, 8 * s, 2.5 * s, 110)
    wood = (148, 112, 68)
    pygame.draw.rect(surf, wood, (cx - 7 * s, cy - 5 * s, 14 * s, 11 * s))
    pygame.draw.rect(surf, (70, 50, 28), (cx - 7 * s, cy - 5 * s, 14 * s, 11 * s), 1)
    pygame.draw.line(surf, (90, 65, 35), (cx - 7 * s, cy), (cx + 7 * s, cy), 1)
    pygame.draw.line(surf, (90, 65, 35), (cx, cy - 5 * s), (cx, cy + 6 * s), 1)
    pygame.draw.line(surf, rs.shade(wood, 30), (cx - 5 * s, cy - 3 * s), (cx + 5 * s, cy - 3 * s), 1)


def draw_bookshelf(surf, cx, cy, tile, t=0.0):
    s = _s(tile, "object") * 0.72
    rs.draw_contact_shadow(surf, cx, cy + 8 * s, 10 * s, 2.8 * s, 110)
    wood = (98, 68, 42)
    pygame.draw.rect(surf, wood, (cx - 8 * s, cy - 16 * s, 16 * s, 24 * s))
    pygame.draw.rect(surf, (50, 34, 20), (cx - 8 * s, cy - 16 * s, 16 * s, 24 * s), 1)
    colors = ((140, 50, 50), (50, 80, 140), (60, 110, 70), (160, 120, 50), (90, 60, 110))
    for row, yy in enumerate((-12, -5, 2)):
        pygame.draw.line(surf, (60, 40, 24), (cx - 7 * s, cy + yy * s), (cx + 7 * s, cy + yy * s), max(2, int(s)))
        for i in range(4):
            col = colors[(row * 4 + i) % len(colors)]
            pygame.draw.rect(surf, col, (cx - 6.5 * s + i * 3.4 * s, cy + yy * s - 5.5 * s, 2.8 * s, 5 * s))


def draw_shelf(surf, cx, cy, tile, t=0.0):
    """Shop wall shelf with jars / goods."""
    s = _s(tile, "object") * 0.65
    wood = (110, 78, 48)
    pygame.draw.rect(surf, wood, (cx - 11 * s, cy - 2 * s, 22 * s, 2.5 * s))
    pygame.draw.rect(surf, wood, (cx - 11 * s, cy - 10 * s, 22 * s, 2.5 * s))
    for i, col in enumerate(((180, 80, 60), (70, 120, 160), (200, 170, 70), (90, 140, 80))):
        ox = -7.5 + i * 5
        pygame.draw.ellipse(surf, col, (cx + ox * s - 2 * s, cy - 8 * s, 4 * s, 5.5 * s))
        pygame.draw.rect(surf, rs.shade(col, -30), (cx + ox * s - 1.5 * s, cy - 9 * s, 3 * s, 1.5 * s))


def draw_counter(surf, cx, cy, tile, t=0.0):
    s = _s(tile, "object") * 0.7
    rs.draw_contact_shadow(surf, cx, cy + 6 * s, 13 * s, 3 * s, 120)
    wood, top = (108, 74, 46), (150, 118, 78)
    pygame.draw.rect(surf, wood, (cx - 12 * s, cy - 1 * s, 24 * s, 8 * s))
    pygame.draw.rect(surf, (55, 36, 22), (cx - 12 * s, cy - 1 * s, 24 * s, 8 * s), 1)
    pygame.draw.rect(surf, top, (cx - 13 * s, cy - 5 * s, 26 * s, 4.5 * s), border_radius=1)
    pygame.draw.rect(surf, (200, 170, 80), (cx - 4 * s, cy - 0.5 * s, 8 * s, 3 * s))


def draw_fireplace(surf, cx, cy, tile, t=0.0):
    s = _s(tile, "object") * 0.78
    glow = int(35 + 30 * abs(math.sin(t * 5)))
    stone = (105, 98, 90)
    rs.draw_contact_shadow(surf, cx, cy + 7 * s, 12 * s, 3 * s, 115)
    pygame.draw.rect(surf, stone, (cx - 11 * s, cy - 8 * s, 22 * s, 16 * s))
    pygame.draw.rect(surf, (55, 50, 46), (cx - 11 * s, cy - 8 * s, 22 * s, 16 * s), 1)
    pygame.draw.rect(surf, (28, 20, 16), (cx - 7 * s, cy - 2 * s, 14 * s, 8 * s))
    pygame.draw.polygon(surf, (240, 120 + glow // 2, 40), [
        (cx - 4 * s, cy + 5 * s), (cx, cy - 3 * s - glow * 0.04 * s), (cx + 4 * s, cy + 5 * s),
    ])
    pygame.draw.circle(surf, (255, 200, 80), (int(cx), int(cy + 2 * s)), max(2, int(2.2 * s)))
    pygame.draw.rect(surf, (80, 74, 68), (cx - 3 * s, cy - 16 * s, 6 * s, 9 * s))
    pygame.draw.circle(surf, (90, 90, 95), (int(cx + 1 * s), int(cy - 17 * s + math.sin(t * 2) * s)), max(2, int(2 * s)))


def draw_campfire(surf, cx, cy, tile, t=0.0):
    """Open campfire lit from logs — cookable hearth on the ground."""
    s = _s(tile, "object") * 0.62
    flicker = abs(math.sin(t * 6.5 + cx * 0.05))
    glow = int(40 + 35 * flicker)
    rs.draw_contact_shadow(surf, cx, cy + 5 * s, 11 * s, 3.2 * s, 130)
    # Crossed logs
    wood = (110, 72, 40)
    pygame.draw.line(surf, wood, (cx - 8 * s, cy + 3 * s), (cx + 8 * s, cy + 1 * s), max(3, int(2.2 * s)))
    pygame.draw.line(surf, wood, (cx - 7 * s, cy + 1 * s), (cx + 7 * s, cy + 4 * s), max(3, int(2.2 * s)))
    pygame.draw.line(surf, rs.shade(wood, -20), (cx - 8 * s, cy + 3 * s), (cx + 8 * s, cy + 1 * s), 1)
    # Flames
    pygame.draw.polygon(surf, (220, 70, 25), [
        (cx - 5 * s, cy + 2 * s),
        (cx - 1 * s, cy - 6 * s - glow * 0.05 * s),
        (cx + 5 * s, cy + 2 * s),
    ])
    pygame.draw.polygon(surf, (255, 150 + glow // 3, 40), [
        (cx - 3 * s, cy + 1.5 * s),
        (cx, cy - 9 * s - glow * 0.06 * s),
        (cx + 3 * s, cy + 1.5 * s),
    ])
    pygame.draw.circle(surf, (255, 230, 140), (int(cx), int(cy - 1 * s)), max(2, int(2.4 * s)))
    # Smoke puffs
    for i, ox in enumerate((-2.5, 1.5, 0)):
        sy = cy - 10 * s - i * 2.5 * s - math.sin(t * 2 + i) * s
        pygame.draw.circle(
            surf, (90, 90, 95),
            (int(cx + ox * s + math.sin(t * 1.5 + i) * s), int(sy)),
            max(1, int((1.6 - i * 0.3) * s)),
        )


def draw_candle(surf, cx, cy, tile, t=0.0):
    s = _s(tile, "object") * 0.4
    flicker = int(20 + 25 * abs(math.sin(t * 7 + cx * 0.1)))
    pygame.draw.rect(surf, (210, 200, 170), (cx - 1.2 * s, cy - 4 * s, 2.4 * s, 7 * s))
    pygame.draw.rect(surf, (90, 70, 40), (cx - 2.5 * s, cy + 2 * s, 5 * s, 2 * s))
    pygame.draw.circle(surf, (255, 180 + flicker // 2, 60), (int(cx), int(cy - 5.5 * s)), max(2, int(1.8 * s)))
    pygame.draw.circle(surf, (255, 240, 180), (int(cx), int(cy - 6 * s)), max(1, int(0.8 * s)))


def draw_rug(surf, cx, cy, tile, t=0.0, color=(140, 50, 50)):
    s = _s(tile, "object") * 0.85
    pygame.draw.ellipse(surf, rs.shade(color, -25), (cx - 14 * s, cy - 2 * s, 28 * s, 10 * s))
    pygame.draw.ellipse(surf, color, (cx - 12 * s, cy - 1 * s, 24 * s, 7 * s))
    pygame.draw.ellipse(surf, rs.shade(color, 30), (cx - 6 * s, cy, 12 * s, 3.5 * s), 1)


def draw_weapon_rack(surf, cx, cy, tile, t=0.0):
    s = _s(tile, "object") * 0.7
    wood, steel = (90, 60, 36), (170, 175, 185)
    pygame.draw.rect(surf, wood, (cx - 9 * s, cy - 14 * s, 18 * s, 3 * s))
    pygame.draw.rect(surf, wood, (cx - 9 * s, cy + 2 * s, 18 * s, 3 * s))
    for i, ox in enumerate((-5, 0, 5)):
        pygame.draw.line(surf, steel, (cx + ox * s, cy + 2 * s), (cx + ox * s + (i - 1) * 1.5 * s, cy - 14 * s), max(2, int(1.4 * s)))
        pygame.draw.polygon(surf, steel, [
            (cx + ox * s + (i - 1) * 1.5 * s, cy - 14 * s),
            (cx + ox * s + (i - 1) * 1.5 * s + 2 * s, cy - 12 * s),
            (cx + ox * s + (i - 1) * 1.5 * s - 1 * s, cy - 11 * s),
        ])
    rs.draw_contact_shadow(surf, cx, cy + 6 * s, 10 * s, 2.5 * s, 100)


def draw_workbench(surf, cx, cy, tile, t=0.0):
    s = _s(tile, "object") * 0.68
    rs.draw_contact_shadow(surf, cx, cy + 6 * s, 12 * s, 3 * s, 120)
    wood, top = (100, 70, 42), (130, 100, 65)
    for ox in (-8, 8):
        pygame.draw.rect(surf, wood, (cx + ox * s - 1.5 * s, cy, 3 * s, 7 * s))
    pygame.draw.rect(surf, top, (cx - 12 * s, cy - 4 * s, 24 * s, 5 * s))
    pygame.draw.rect(surf, (55, 38, 22), (cx - 12 * s, cy - 4 * s, 24 * s, 5 * s), 1)
    # Tools on bench
    pygame.draw.line(surf, (160, 160, 170), (cx - 6 * s, cy - 5 * s), (cx - 2 * s, cy - 2 * s), max(2, int(s)))
    pygame.draw.circle(surf, (80, 55, 30), (int(cx + 4 * s), int(cy - 3 * s)), max(2, int(1.5 * s)))


def draw_quench_bucket(surf, cx, cy, tile, t=0.0):
    s = _s(tile, "object") * 0.48
    rs.draw_contact_shadow(surf, cx, cy + 5 * s, 6 * s, 2.2 * s, 110)
    pygame.draw.ellipse(surf, (70, 75, 85), (cx - 5 * s, cy - 4 * s, 10 * s, 9 * s))
    pygame.draw.ellipse(surf, (40, 90, 140), (cx - 4 * s, cy - 4.5 * s, 8 * s, 3.5 * s))
    pygame.draw.arc(surf, (120, 125, 135), (cx - 5 * s, cy - 8 * s, 10 * s, 8 * s), 0.2, math.pi - 0.2, max(1, int(s)))


def draw_pet_bed(surf, cx, cy, tile, t=0.0):
    s = _s(tile, "object") * 0.6
    rs.draw_contact_shadow(surf, cx, cy + 4 * s, 10 * s, 2.8 * s, 110)
    cushion = (160, 100, 70)
    pygame.draw.ellipse(surf, (90, 60, 40), (cx - 9 * s, cy - 1 * s, 18 * s, 7 * s))
    pygame.draw.ellipse(surf, cushion, (cx - 7 * s, cy - 2 * s, 14 * s, 5 * s))
    pygame.draw.ellipse(surf, rs.shade(cushion, 25), (cx - 4 * s, cy - 1 * s, 8 * s, 2.5 * s))


def draw_pet_cage(surf, cx, cy, tile, t=0.0):
    s = _s(tile, "object") * 0.62
    rs.draw_contact_shadow(surf, cx, cy + 6 * s, 9 * s, 2.5 * s, 110)
    wood, bar = (100, 72, 46), (150, 155, 165)
    pygame.draw.rect(surf, wood, (cx - 8 * s, cy - 10 * s, 16 * s, 16 * s), 2)
    for i in range(5):
        x = cx - 6 * s + i * 3 * s
        pygame.draw.line(surf, bar, (x, cy - 9 * s), (x, cy + 5 * s), max(1, int(s)))
    pygame.draw.rect(surf, wood, (cx - 8 * s, cy + 4 * s, 16 * s, 2.5 * s))
    # Tiny critter silhouette
    pygame.draw.ellipse(surf, (180, 140, 100), (cx - 2 * s, cy - 1 * s, 5 * s, 3.5 * s))
    pygame.draw.circle(surf, (180, 140, 100), (int(cx + 3 * s), int(cy - 2 * s)), max(2, int(1.6 * s)))


def draw_stool(surf, cx, cy, tile, t=0.0):
    s = _s(tile, "object") * 0.45
    wood = (120, 85, 50)
    rs.draw_contact_shadow(surf, cx, cy + 5 * s, 5 * s, 2 * s, 100)
    for ox in (-2.5, 2.5):
        pygame.draw.line(surf, (70, 48, 28), (cx + ox * s, cy + 1 * s), (cx + ox * 1.4 * s, cy + 5 * s), max(2, int(s)))
    pygame.draw.ellipse(surf, wood, (cx - 4 * s, cy - 2 * s, 8 * s, 3.5 * s))
    pygame.draw.ellipse(surf, (70, 48, 28), (cx - 4 * s, cy - 2 * s, 8 * s, 3.5 * s), 1)


def draw_building(surf, rect, building_type="house", style=0, t=0.0):
    """Legacy full building silhouette (used for non-enterable props)."""
    if hasattr(rect, "x"):
        r = (rect.x, rect.y, rect.w, rect.h)
    else:
        r = rect
    if building_type == "smithy":
        draw_house(surf, r, style=1, t=t)
        x, y, w, h = r
        pygame.draw.rect(surf, (55, 48, 43), (x + w * 0.70, y + h * 0.15, w * 0.12, h * 0.25))
    else:
        draw_house(surf, r, style=style, t=t)


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
    """Set global art scale multiplier (character/object/monster scales stay relative)."""
    global ART_SCALE
    rs.set_scales(art=scale)
    ART_SCALE = rs.ART_SCALE


def get_art_scale():
    return rs.ART_SCALE


def set_render_profile(tile_size=None, character=None, object_=None, monster=None, pet=None, art=None, tree=None):
    """Configure the full RS-era scale profile from the client."""
    global ART_SCALE
    rs.set_scales(
        art=art, character=character, object_=object_,
        monster=monster, pet=pet, tile_size=tile_size, tree=tree,
    )
    ART_SCALE = rs.ART_SCALE
