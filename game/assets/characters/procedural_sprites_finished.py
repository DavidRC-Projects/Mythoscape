"""
Procedural sprite rendering for the MMORPG client — early-2000s fantasy MMORPG
visual language (chunky low-poly silhouettes, limited palettes, hard shading).

Most entities are drawn with pygame primitives. Building walls/roofs (and the
harbour pier) optionally sample CC0 photoreal textures from ambientCG.
"""
import math
import pygame

import rs_style as rs
import building_textures as btex

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


def draw_path(surf, rect, seed_x, seed_y, zone=None):
    """Worn dirt path — or cobbled city street when zone is city."""
    if zone == "city":
        draw_city_street(surf, rect, seed_x, seed_y)
        return
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


def draw_city_street(surf, rect, seed_x, seed_y):
    """Cobbled city street — grey stones matching the plaza, not dirt."""
    shades = ((128, 126, 132), (118, 116, 122), (138, 136, 142), (108, 108, 114))
    base = shades[int(_seeded(seed_x, seed_y, 1) * 4) % 4]
    hi, mid, sh, _ = rs.material(base)
    pygame.draw.rect(surf, mid, rect)
    pygame.draw.line(surf, hi, (rect.left + 1, rect.top + 1), (rect.right - 2, rect.top + 1), 1)
    pygame.draw.line(surf, sh, (rect.left + 1, rect.bottom - 1), (rect.right - 1, rect.bottom - 1), 1)
    # Cobble seams
    pygame.draw.line(surf, (78, 78, 84), (rect.centerx, rect.top + 1), (rect.centerx, rect.bottom - 1), 1)
    pygame.draw.line(surf, (78, 78, 84), (rect.left + 1, rect.centery), (rect.right - 1, rect.centery), 1)
    if _seeded(seed_x, seed_y, 5) < 0.35:
        pygame.draw.circle(surf, sh, (rect.centerx - 3, rect.centery + 2), 1)


def draw_pier(surf, rect, seed_x, seed_y):
    """Wooden pier planks over water — photo texture when available."""
    used = btex.blit_texture_tile(surf, rect, "wood_dark", seed_x, seed_y, alpha=255)
    if not used:
        plank_a = (148, 112, 68)
        plank_b = (128, 96, 56)
        nail = (70, 55, 40)
        gap = (55, 42, 30)
        pygame.draw.rect(surf, gap, rect)
        n = max(3, rect.h // 5)
        ph = max(3, rect.h // n)
        for i in range(n):
            y = rect.y + i * ph
            col = plank_a if (i + seed_x) % 2 == 0 else plank_b
            hi, mid, sh, _ = rs.material(col)
            pygame.draw.rect(surf, mid, (rect.x + 1, y + 1, rect.w - 2, max(2, ph - 2)))
            pygame.draw.line(surf, hi, (rect.x + 2, y + 1), (rect.right - 3, y + 1), 1)
            pygame.draw.line(surf, sh, (rect.x + 2, y + ph - 2), (rect.right - 3, y + ph - 2), 1)
            if _seeded(seed_x, seed_y + i, 9) < 0.7:
                pygame.draw.circle(surf, nail, (rect.x + 4, y + ph // 2), 1)
                pygame.draw.circle(surf, nail, (rect.right - 5, y + ph // 2), 1)
    # Outer rim so pier reads above water
    pygame.draw.rect(surf, (90, 70, 42), rect, 1)
    pygame.draw.line(surf, (170, 140, 95), (rect.left + 1, rect.top + 1), (rect.right - 2, rect.top + 1), 1)


def draw_floor(surf, rect, seed_x, seed_y, zone=None):
    """Flagstone / plank floor with lit top edge."""
    if zone == "volcano":
        draw_volcano_floor(surf, rect, seed_x, seed_y)
        return
    r0 = _seeded(seed_x, seed_y, 1)
    if zone == "village":
        shades = ((124, 98, 70), (110, 86, 60), (138, 112, 82), (96, 74, 50))
        line = (72, 52, 34)
    elif zone == "fishing_village":
        shades = ((118, 100, 78), (104, 88, 66), (130, 112, 88), (90, 76, 56))
        line = (68, 52, 36)
    elif zone == "city":
        shades = ((136, 134, 140), (124, 122, 128), (146, 144, 150), (112, 112, 118))
        line = (88, 88, 94)
    elif zone == "dungeon":
        shades = ((64, 58, 72), (52, 46, 60), (74, 66, 84), (42, 38, 50))
        line = (28, 24, 34)
    elif zone == "shadow_crypt":
        shades = ((40, 32, 58), (32, 26, 48), (52, 40, 72), (24, 18, 38))
        line = (16, 12, 28)
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
    if zone != "city" and _seeded(seed_x, seed_y, 3) < 0.18:
        pygame.draw.circle(surf, sh, rect.center, max(1, rect.w // 9))
    if zone == "dungeon" and _seeded(seed_x, seed_y, 11) < 0.14:
        glow = pygame.Surface((rect.w, rect.h), pygame.SRCALPHA)
        pygame.draw.circle(glow, (255, 150, 50, 28), (rect.w // 3, rect.h // 3), rect.w // 2)
        surf.blit(glow, rect.topleft)
    if zone == "city":
        # Quiet flagstone seams (no polka-dot rivets)
        if (seed_x + seed_y) % 2 == 0:
            pygame.draw.line(surf, line, (rect.centerx, rect.top + 2), (rect.centerx, rect.bottom - 2), 1)
        else:
            pygame.draw.line(surf, line, (rect.left + 2, rect.centery), (rect.right - 2, rect.centery), 1)
        if _seeded(seed_x, seed_y, 8) < 0.22:
            pygame.draw.line(surf, hi, (rect.left + 3, rect.top + 3), (rect.left + rect.w * 0.4, rect.top + 3), 1)


def draw_tile_wall_ao(surf, rect, neighbors, alpha=70):
    """
    Ambient occlusion on a walkable tile where it meets WALL neighbors.
    Darkens the receiving floor at the seam (isometric AO accent, not a new light).
    neighbors: dict with optional True for N/E/S/W.
    """
    if not neighbors or rect.w < 3 or rect.h < 3:
        return
    band = max(2, min(rect.w, rect.h) // 5)
    ao = pygame.Surface((rect.w, rect.h), pygame.SRCALPHA)
    warm = (16, 12, 10)

    def _fade_rows(y0, y1, from_edge):
        for i in range(band):
            t = 1.0 - i / max(1, band - 1)
            a = int(alpha * (t ** 1.4))
            if from_edge == "N":
                yy = i
            else:
                yy = rect.h - 1 - i
            if 0 <= yy < rect.h:
                pygame.draw.line(ao, (*warm, a), (0, yy), (rect.w, yy))

    def _fade_cols(from_edge):
        for i in range(band):
            t = 1.0 - i / max(1, band - 1)
            a = int(alpha * (t ** 1.4))
            xx = i if from_edge == "W" else rect.w - 1 - i
            if 0 <= xx < rect.w:
                pygame.draw.line(ao, (*warm, a), (xx, 0), (xx, rect.h))

    if neighbors.get("N"):
        _fade_rows(0, band, "N")
    if neighbors.get("S"):
        _fade_rows(0, band, "S")
    if neighbors.get("W"):
        _fade_cols("W")
    if neighbors.get("E"):
        _fade_cols("E")
    # Corner boost where two walls meet
    for corner, (nx, ny) in (
        ("NW", ("N", "W")), ("NE", ("N", "E")),
        ("SW", ("S", "W")), ("SE", ("S", "E")),
    ):
        if neighbors.get(nx) and neighbors.get(ny):
            size = band + 1
            for i in range(size):
                for j in range(size):
                    if corner == "NW":
                        px, py = i, j
                        d = math.hypot(i / size, j / size)
                    elif corner == "NE":
                        px, py = rect.w - 1 - i, j
                        d = math.hypot(i / size, j / size)
                    elif corner == "SW":
                        px, py = i, rect.h - 1 - j
                        d = math.hypot(i / size, j / size)
                    else:
                        px, py = rect.w - 1 - i, rect.h - 1 - j
                        d = math.hypot(i / size, j / size)
                    if d < 1.0 and 0 <= px < rect.w and 0 <= py < rect.h:
                        a = int(alpha * 0.85 * (1.0 - d) ** 1.3)
                        prev = ao.get_at((px, py))
                        ao.set_at((px, py), (*warm, max(prev[3], a)))
    surf.blit(ao, rect.topleft)


def draw_stone_floor(surf, rect, seed_x, seed_y):
    """City plaza flagstones — cooler grey than dungeon floor."""
    draw_floor(surf, rect, seed_x, seed_y, zone="city")


def draw_wall(surf, rect, zone, seed_x, seed_y, material=None):
    if zone == "village":
        draw_building_wall(surf, rect, seed_x, seed_y, material=material or "wood")
    elif zone == "city":
        draw_building_wall(surf, rect, seed_x, seed_y, material=material or "brick")
    elif zone == "mine":
        draw_cave_wall(surf, rect)
    elif zone == "dungeon":
        draw_dungeon_wall(surf, rect, seed_x, seed_y)
    elif zone == "shadow_crypt":
        draw_void_crypt_wall(surf, rect, seed_x, seed_y)
    elif zone == "volcano":
        draw_volcano_wall(surf, rect, seed_x, seed_y)
    elif zone == "mountains":
        draw_mountain_rock(surf, rect, seed_x, seed_y)
    elif zone == "fishing_village":
        draw_building_wall(surf, rect, seed_x, seed_y, material=material or "wood")
    else:
        pygame.draw.rect(surf, (35, 33, 38), rect)
        pygame.draw.rect(surf, (22, 20, 24), rect, 1)


def draw_void_crypt_wall(surf, rect, seed_x, seed_y):
    """Near-black mystical stone with violet flecks."""
    base = (32, 28, 42)
    hi = (55, 48, 78)
    sh = (18, 14, 26)
    pygame.draw.rect(surf, base, rect)
    for i in range(4):
        ox = int(_seeded(seed_x, seed_y, 20 + i) * max(2, rect.w - 4))
        oy = int(_seeded(seed_x, seed_y, 30 + i) * max(2, rect.h - 4))
        col = hi if i % 2 == 0 else (70, 40, 120)
        pygame.draw.circle(surf, col, (rect.x + ox, rect.y + oy), 1 + (i % 2))
    pygame.draw.rect(surf, sh, rect, 1)


def draw_mountain_rock(surf, rect, seed_x, seed_y):
    """Cliff / peak face — layered ridges, scree, and occasional snow caps."""
    # Cooler high-altitude stone
    base = (86, 82, 78)
    mid = (112, 106, 98)
    hi = (148, 142, 132)
    sh = (52, 48, 44)
    deep = (34, 32, 30)
    pygame.draw.rect(surf, base, rect)
    # Tall peak facets that read as mountain silhouette
    peaks = 2 + int(_seeded(seed_x, seed_y, 7) * 2)
    for i in range(peaks):
        ox = int(_seeded(seed_x, seed_y, 30 + i) * max(2, rect.w - 8))
        tip_h = int(rect.h * (0.55 + 0.35 * _seeded(seed_x, seed_y, 50 + i)))
        rw = max(6, int(rect.w * (0.35 + 0.25 * _seeded(seed_x, seed_y, 60 + i))))
        left = rect.x + ox
        tip = (left + rw // 2, rect.y + max(1, rect.h - tip_h))
        base_l = (left, rect.bottom - 1)
        base_r = (left + rw, rect.bottom - 1)
        col = mid if i % 2 == 0 else hi
        pygame.draw.polygon(surf, col, [tip, base_l, base_r])
        # Lit edge
        pygame.draw.line(surf, hi, tip, base_l, 1)
        pygame.draw.line(surf, sh, tip, base_r, 1)
        # Snow cap on taller peaks
        if tip_h > rect.h * 0.7 and _seeded(seed_x, seed_y, 80 + i) > 0.45:
            snow_y = tip[1] + max(2, tip_h // 5)
            pygame.draw.polygon(surf, (230, 232, 236), [
                tip,
                (tip[0] - rw // 5, snow_y),
                (tip[0] + rw // 5, snow_y),
            ])
    # Scree / rubble along the bottom
    for i in range(3):
        rx = rect.x + int(_seeded(seed_x, seed_y, 90 + i) * max(2, rect.w - 5))
        ry = rect.bottom - 3 - int(_seeded(seed_x, seed_y, 100 + i) * 4)
        pygame.draw.circle(surf, deep if i % 2 else sh, (rx, ry), 1 + (i % 2))
    pygame.draw.rect(surf, deep, rect, 1)


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
    """Village exterior wall tile — photo texture when available, else procedural."""
    tex_name = "brick" if material == "brick" else "wood_planks"
    used = btex.blit_texture_tile(surf, rect, tex_name, seed_x, seed_y, alpha=255)
    if not used:
        if material == "brick":
            _fill_brick_face(surf, rect, seed_x, seed_y, alpha=255)
        else:
            _fill_wood_face(surf, rect, seed_x, seed_y, alpha=255)
    if material == "brick":
        # Darker foundation course
        found_h = max(3, rect.h // 5)
        shade = pygame.Surface((rect.w, found_h), pygame.SRCALPHA)
        shade.fill((20, 18, 16, 90))
        surf.blit(shade, (rect.x, rect.bottom - found_h))
        pygame.draw.line(surf, (42, 44, 48), (rect.x, rect.bottom - found_h), (rect.right, rect.bottom - found_h), 1)
        pw = max(2, rect.w // 8)
        pygame.draw.rect(surf, (150, 148, 154), (rect.x, rect.y, pw, rect.h - found_h), 1)
        pygame.draw.rect(surf, (70, 72, 78), (rect.right - pw, rect.y, pw, rect.h - found_h), 1)
        pygame.draw.rect(surf, (48, 50, 54), rect, 1)
    else:
        # Soft edge darkening so timber panels read as blocks
        edge = pygame.Surface((rect.w, rect.h), pygame.SRCALPHA)
        pygame.draw.rect(edge, (0, 0, 0, 45), edge.get_rect(), 2)
        surf.blit(edge, rect.topleft)
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
    """Stone block wall with lit top course, shade bottom, and mortar depth."""
    r0 = _seeded(seed_x, seed_y, 2)
    base = (46, 44, 58) if r0 < 0.5 else (40, 38, 52)
    hi, mid, sh, deep = rs.material(base)
    mortar = (20, 18, 26)
    pygame.draw.rect(surf, mid, rect)
    brick_h = max(6, rect.h // 2)
    for row, y in enumerate(range(rect.y, rect.bottom, brick_h)):
        offset = (brick_h // 2) if row % 2 else 0
        pygame.draw.line(surf, mortar, (rect.x, y), (rect.right, y), 1)
        for x in range(rect.x - offset, rect.right + brick_h, brick_h):
            pygame.draw.line(surf, mortar, (x, y), (x, min(y + brick_h, rect.bottom)), 1)
            if y + 1 < rect.bottom:
                pygame.draw.line(surf, hi, (max(rect.x, x) + 1, y + 1), (min(rect.right, x + brick_h) - 1, y + 1), 1)
            # Right edge of each brick slightly darker (volume)
            bx1 = min(rect.right - 1, x + brick_h - 1)
            if rect.x <= bx1 < rect.right:
                pygame.draw.line(surf, sh, (bx1, y + 1), (bx1, min(y + brick_h - 1, rect.bottom - 1)), 1)
    # Top bevel (sky-facing) + bottom AO (ground contact)
    pygame.draw.line(surf, hi, (rect.x + 1, rect.y + 1), (rect.right - 2, rect.y + 1), 2)
    pygame.draw.line(surf, hi, (rect.x + 1, rect.y + 1), (rect.x + 1, rect.bottom - 2), 1)
    bot = pygame.Surface((rect.w, max(3, rect.h // 4)), pygame.SRCALPHA)
    for i in range(bot.get_height()):
        a = int(90 * ((i + 1) / bot.get_height()))
        pygame.draw.line(bot, (12, 10, 16, a), (0, i), (rect.w, i))
    surf.blit(bot, (rect.x, rect.bottom - bot.get_height()))
    # Ceiling vignette near top of taller stacks
    top_v = pygame.Surface((rect.w, max(2, rect.h // 5)), pygame.SRCALPHA)
    for i in range(top_v.get_height()):
        a = int(55 * (1.0 - i / max(1, top_v.get_height() - 1)))
        pygame.draw.line(top_v, (8, 6, 14, a), (0, i), (rect.w, i))
    surf.blit(top_v, (rect.x, rect.y))
    pygame.draw.rect(surf, mortar, rect, 1)


def draw_dungeon_cliff(surf, cx, cy, tile, seed_x=0, seed_y=0, t=0.0):
    """Tall stone face for dungeon corridors — stronger ¾ volume."""
    s = tile / 40.0
    h = int(52 * s + (_seeded(seed_x, seed_y, 3) * 16 * s))
    w = int(tile * (0.92 + 0.08 * _seeded(seed_x, seed_y, 5)))
    depth = max(6, int(tile * 0.22))
    rs.draw_contact_shadow(surf, cx, cy + tile // 5, w * 0.48, max(2, tile * 0.09), 110)
    rs.draw_cast_shadow(surf, cx + w * 0.1, cy + tile // 4, w * 0.5, max(2, tile * 0.1), 70)
    left = cx - w // 2
    top = cy - h + tile // 4
    mid_x = cx
    # Back edge (depth plane)
    pygame.draw.polygon(surf, (32, 30, 42), [
        (mid_x + depth // 2, top - 4),
        (left + w + depth // 3, cy + tile // 6),
        (left + w, cy + tile // 5),
        (mid_x, top),
    ])
    # Lit left / shaded right front planes
    pygame.draw.polygon(surf, (78, 74, 96), [(mid_x, top), (left, cy + tile // 5), (mid_x - 1, cy + tile // 5)])
    pygame.draw.polygon(surf, (42, 40, 56), [(mid_x, top), (left + w, cy + tile // 5), (mid_x + 1, cy + tile // 5)])
    pygame.draw.line(surf, (130, 125, 150), (mid_x, top), (left + 3, cy), 2)
    pygame.draw.line(surf, (22, 18, 28), (mid_x, top), (left + w - 2, cy), 2)
    # Mortar courses
    for i in range(4):
        yy = top + int(h * (0.18 + i * 0.18))
        pygame.draw.line(surf, (28, 26, 36), (left + 4, yy), (left + w - 4, yy), 1)
    if _seeded(seed_x, seed_y, 11) < 0.4:
        pygame.draw.circle(surf, (48, 70, 52), (int(mid_x - 4 * s), int(top + h * 0.55)), max(1, int(2 * s)))
    ao_h = max(4, tile // 6)
    ao = pygame.Surface((w + 6, ao_h), pygame.SRCALPHA)
    for i in range(ao_h):
        a = int(95 * (1.0 - i / max(1, ao_h - 1)))
        pygame.draw.line(ao, (10, 8, 14, a), (0, i), (w + 6, i))
    surf.blit(ao, (left - 3, cy + tile // 5 - 1))



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
def draw_giant_rat(surf, cx, cy, tile, t, hurt=False, attacking=0.0, facing=1):
    """Low quadruped: haunch, long snout, pink ears, whip tail."""
    facing = 1 if facing >= 0 else -1
    s = _s(tile, "monster") * 0.95
    bob = math.sin(t * 7) * 0.6
    body = (150, 55, 50) if hurt else (118, 112, 108)
    hi, mid, sh, deep = rs.material(body)
    pink = (210, 140, 150)
    cy += bob
    lunge_w, crouch, strike = rs.attack_impulse(attacking)
    lunge = lunge_w * 6.5 * s * facing
    cy += crouch * 1.8 * s
    rs.draw_cast_shadow(surf, cx, cy + 9 * s, 14 * s, 3.5 * s, 110)
    # Hind haunch
    rs.draw_volume(surf, body, [
        (cx - 12 * s * facing, cy + 2 * s), (cx - 4 * s * facing, cy - 4 * s),
        (cx + 2 * s * facing, cy - 2 * s), (cx + 1 * s * facing, cy + 7 * s),
        (cx - 10 * s * facing, cy + 8 * s),
    ], deep, 1)
    # Body barrel
    rs.draw_volume(surf, body, [
        (cx - 6 * s * facing, cy + 1 * s), (cx + 8 * s * facing + lunge * 0.3, cy - 3 * s),
        (cx + 12 * s * facing + lunge, cy + 1 * s), (cx + 8 * s * facing, cy + 7 * s),
        (cx - 4 * s * facing, cy + 7 * s),
    ], deep, 1)
    # Legs
    for ox, oy in ((-8, 6), (-3, 7), (4, 6), (9, 5)):
        pygame.draw.line(
            surf, sh,
            (cx + ox * s * facing, cy + oy * s),
            (cx + ox * s * facing + 1 * s * facing, cy + 10 * s),
            max(2, int(2.2 * s)),
        )
    # Head / snout
    head = (cx + 11 * s * facing + lunge, cy - 1 * s)
    rs.draw_volume(surf, body, [
        (head[0] - 4 * s * facing, head[1] + 2 * s), (head[0] - 2 * s * facing, head[1] - 3 * s),
        (head[0] + 6 * s * facing, head[1] - 1 * s), (head[0] + 7 * s * facing, head[1] + 1.5 * s),
        (head[0] + 2 * s * facing, head[1] + 3 * s),
    ], deep, 1)
    pygame.draw.circle(surf, (30, 28, 26), (int(head[0] + 1 * s * facing), int(head[1] - 1 * s)), max(1, int(0.9 * s)))
    pygame.draw.circle(surf, pink, (int(head[0] + 6.5 * s * facing), int(head[1])), max(1, int(1.1 * s)))
    # Ears
    for ox in (-1.5, 2.5):
        rs.draw_poly(surf, pink, [
            (head[0] + ox * s * facing, head[1] - 2 * s),
            (head[0] + (ox - 2) * s * facing, head[1] - 6 * s),
            (head[0] + (ox + 2) * s * facing, head[1] - 5.5 * s),
        ], deep, 1)
        pygame.draw.circle(surf, (180, 100, 120), (int(head[0] + ox * s * facing), int(head[1] - 4.5 * s)), max(1, int(1.2 * s)))
    # Tail
    pygame.draw.lines(surf, sh, False, [
        (cx - 11 * s * facing, cy + 3 * s), (cx - 16 * s * facing, cy - 2 * s), (cx - 18 * s * facing, cy + 4 * s),
    ], max(2, int(1.8 * s)))
    if strike > 0.55:
        pygame.draw.circle(surf, (255, 240, 200), (int(head[0] + 5 * s * facing), int(head[1])), max(2, int(1.2 * s * strike)))


def draw_skeleton(surf, cx, cy, tile, t, hurt=False, attacking=0.0, facing=1):
    """Thin bone frame: ribs, joints, skull with sockets."""
    facing = 1 if facing >= 0 else -1
    s = _s(tile, "monster")
    bob = math.sin(t * 5) * 0.8
    bone = (200, 70, 70) if hurt else (228, 220, 200)
    hi, mid, sh, deep = rs.material(bone)
    cy += bob
    lunge_w, crouch, strike = rs.attack_impulse(attacking)
    lunge = lunge_w * 8 * s * facing
    cy += crouch * 1.2 * s
    rs.draw_cast_shadow(surf, cx, cy + 13 * s, 9 * s, 3 * s, 100)
    # Legs with joint knobs — lead foot steps through on commit
    for side in (-1, 1):
        step = (lunge_w * 2.5 * s * facing) if side == facing else (-lunge_w * 1.2 * s * facing)
        hip = (cx + side * 3.2 * s, cy + 1 * s)
        knee = (cx + side * 4.5 * s + step * 0.4, cy + 7 * s - max(0.0, lunge_w) * 0.8 * s)
        foot = (cx + side * 5.2 * s + step, cy + 13 * s)
        rs.draw_volume_limb(surf, *hip, *knee, 1.1 * s, bone, deep)
        rs.draw_volume_limb(surf, *knee, *foot, 0.95 * s, bone, deep)
        pygame.draw.circle(surf, mid, (int(knee[0]), int(knee[1])), max(2, int(1.6 * s)))
        pygame.draw.circle(surf, sh, (int(foot[0]), int(foot[1])), max(2, int(1.8 * s)))
    # Pelvis + spine
    pygame.draw.line(surf, mid, (cx - 5 * s, cy + 1 * s), (cx + 5 * s, cy + 1 * s), max(3, int(2.8 * s)))
    pygame.draw.line(surf, mid, (cx, cy + 1 * s), (cx + lunge * 0.08, cy - 9 * s), max(3, int(2.6 * s)))
    # Ribs
    for i in range(4):
        yy = cy - 7.5 * s + i * 2.0 * s
        w = 6.2 * s - i * 0.35 * s
        pygame.draw.arc(surf, mid, (cx - w + lunge * 0.05, yy - 1.2 * s, w * 2, 3.5 * s), 0.15, math.pi - 0.15, max(2, int(1.6 * s)))
    # Arms + sword
    pygame.draw.line(surf, mid, (cx - 4.5 * s * facing, cy - 6 * s), (cx - 11 * s * facing, cy + 2 * s), max(2, int(2.2 * s)))
    # Wind-up raises blade, strike drives it down/forward
    hand = (cx + 11 * s * facing + lunge, cy - 1 * s - crouch * 4 * s - strike * 2 * s)
    pygame.draw.line(surf, mid, (cx + 4.5 * s * facing, cy - 6 * s), hand, max(2, int(2.2 * s)))
    tip = (hand[0] + (7 * s + lunge_w * 5 * s) * facing, hand[1] - 18 * s + strike * 10 * s)
    rs.draw_volume(surf, (170, 175, 185), [
        hand, (hand[0] + 2 * s * facing, hand[1] - 1 * s), tip, (hand[0] - 1 * s * facing, hand[1] - 2 * s),
    ], deep, 1)
    pygame.draw.line(surf, (100, 70, 40), (hand[0] - 3 * s, hand[1] + 1 * s), (hand[0] + 3 * s, hand[1] + 2 * s), max(2, int(2.4 * s)))
    if strike > 0.7:
        pygame.draw.line(surf, (255, 250, 220), hand, tip, max(1, int(s)))
    # Skull
    head = (cx + lunge * 0.12, cy - 12 * s)
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


def draw_imp(surf, cx, cy, tile, t, hurt=False, attacking=0.0, facing=1, moving=False, variant="ash"):
    """Small demonic imp — bat wings, horns, tail, hunched posture."""
    facing = 1 if facing >= 0 else -1
    s = _s(tile, 'monster') * 0.75  # Smaller than other monsters
    bob = math.sin(t * 8) * 0.8
    
    # Color variants
    if variant == "void":
        skin = (90, 70, 120) if not hurt else (140, 40, 100)
        wing = (50, 40, 70)
    else:  # ash
        skin = (120, 60, 50) if not hurt else (180, 40, 30)
        wing = (80, 50, 45)
    
    hi, mid, sh, deep = rs.material(skin)
    cy += bob
    
    lunge_w, crouch, strike = rs.attack_impulse(attacking)
    lunge = lunge_w * 7 * s * facing
    cy += crouch * 1.2 * s
    
    rs.draw_cast_shadow(surf, cx, cy + 11 * s, 8 * s, 2.8 * s, 100)
    
    # Bat wings (behind body)
    wing_flap = math.sin(t * 10) * 0.3 + 0.3
    for side in (-1, 1):
        wing_pts = [
            (cx + side * 2 * s * facing, cy - 2 * s),
            (cx + side * (8 + wing_flap * 3) * s * facing, cy - 4 * s),
            (cx + side * (9 + wing_flap * 4) * s * facing, cy + 2 * s),
            (cx + side * 3 * s * facing, cy + 1 * s),
        ]
        rs.draw_poly(surf, wing, wing_pts, deep, 1)
        # Wing membrane detail
        pygame.draw.line(surf, deep, wing_pts[0], wing_pts[2], 1)
    
    # Hunched body
    rs.draw_volume(surf, skin, [
        (cx - 3.5 * s * facing, cy - 1 * s),
        (cx + 3 * s * facing + lunge * 0.2, cy - 3 * s),
        (cx + 4 * s * facing + lunge * 0.15, cy + 4 * s),
        (cx - 3 * s * facing, cy + 5 * s),
    ], deep, 1)
    
    # Thin legs
    for ox, oy in ((-1.5, 3), (2, 3.5)):
        leg_end = (cx + ox * s * facing, cy + 10 * s)
        rs.draw_volume_limb(surf, cx + ox * s * facing, cy + oy * s, *leg_end, 0.9 * s, skin, deep)
        # Clawed feet
        pygame.draw.circle(surf, deep, (int(leg_end[0]), int(leg_end[1])), max(2, int(1.2 * s)))
    
    # Clawed arms
    claw_pos = (cx + 5 * s * facing + lunge, cy - 1 * s - crouch * 2 * s)
    rs.draw_volume_limb(surf, cx + 2.5 * s * facing, cy - 1 * s, *claw_pos, 0.9 * s, skin, deep)
    # Claw
    for i in range(3):
        claw_tip = (claw_pos[0] + (i - 1) * 0.8 * s, claw_pos[1] + 2 * s + strike * 3 * s)
        pygame.draw.line(surf, deep, claw_pos, claw_tip, max(1, int(0.6 * s)))
    
    # Head with horns
    head = (cx + 1.5 * s * facing + lunge * 0.1, cy - 5 * s)
    rs.draw_volume(surf, skin, [
        (head[0] - 2.5 * s, head[1] + 1 * s),
        (head[0] - 2 * s, head[1] - 2.5 * s),
        (head[0] + 2.5 * s, head[1] - 2 * s),
        (head[0] + 3 * s, head[1] + 1.5 * s),
        (head[0], head[1] + 2 * s),
    ], deep, 1)
    
    # Horns
    for side in (-1, 1):
        horn_pts = [
            (head[0] + side * 1.8 * s, head[1] - 1.8 * s),
            (head[0] + side * 2.5 * s, head[1] - 5 * s),
            (head[0] + side * 1.2 * s, head[1] - 2.2 * s),
        ]
        rs.draw_poly(surf, deep, horn_pts, None, 0)
        pygame.draw.line(surf, (20, 18, 22), horn_pts[0], horn_pts[1], max(1, int(1.2 * s)))
    
    # Glowing eyes
    eye_color = (160, 100, 200) if variant == "void" else (255, 140, 60)
    for ox in (-1, 1):
        pygame.draw.circle(surf, eye_color, (int(head[0] + ox * s), int(head[1] - 0.5 * s)), max(2, int(0.8 * s)))
        pygame.draw.circle(surf, (255, 255, 240), (int(head[0] + ox * s - 0.3 * s), int(head[1] - 0.8 * s)), max(1, int(0.4 * s)))
    
    # Tail
    tail_pts = [
        (cx - 2 * s * facing, cy + 3 * s),
        (cx - 6 * s * facing, cy + 1 * s),
        (cx - 9 * s * facing, cy - 2 * s),
    ]
    pygame.draw.lines(surf, sh, False, tail_pts, max(2, int(1.5 * s)))
    # Tail spade
    pygame.draw.polygon(surf, deep, [
        (tail_pts[2][0], tail_pts[2][1]),
        (tail_pts[2][0] - 1.5 * s * facing, tail_pts[2][1] - 2 * s),
        (tail_pts[2][0] + 1.5 * s * facing, tail_pts[2][1] - 2 * s),
    ])
    
    if strike > 0.6:
        pygame.draw.circle(surf, (255, 200, 100, int(200 * strike)), (int(claw_pos[0]), int(claw_pos[1])), max(3, int(2.5 * s * strike)), 1)


def draw_ash_imp(surf, cx, cy, tile, t, hurt=False, attacking=0.0, facing=1, moving=False):
    """Ash imp - fiery variant."""
    draw_imp(surf, cx, cy, tile, t, hurt, attacking, facing, moving, variant="ash")


def draw_void_imp(surf, cx, cy, tile, t, hurt=False, attacking=0.0, facing=1, moving=False):
    """Void imp - dark variant."""
    draw_imp(surf, cx, cy, tile, t, hurt, attacking, facing, moving, variant="void")


def draw_goblin(surf, cx, cy, tile, t, hurt=False, attacking=0.0, facing=1):
    """Hunched long-armed goblin — angular head, distinct silhouette."""
    facing = 1 if facing >= 0 else -1
    s = _s(tile, 'monster') * 0.95
    bob = math.sin(t * 6) * 0.7
    skin = (140, 40, 40) if hurt else (68, 112, 50)
    hi, mid, sh, deep = rs.material(skin)
    cloth = (86, 66, 44)
    cy += bob
    lunge_w, crouch, strike = rs.attack_impulse(attacking)
    lunge = lunge_w * 8 * s * facing
    cy += crouch * 1.5 * s
    rs.draw_cast_shadow(surf, cx, cy + 13 * s, 10 * s, 3.2 * s, 115)
    # Bow legs — weight shift into the swing
    back = -lunge_w * 1.8 * s * facing
    fwd = lunge_w * 3.2 * s * facing
    rs.draw_volume_limb(surf, cx - 2.5 * s * facing, cy + 3 * s, cx - 5.5 * s * facing + back, cy + 13 * s, 1.5 * s, cloth, deep)
    rs.draw_volume_limb(surf, cx + 2.5 * s * facing, cy + 3 * s, cx + 5 * s * facing + fwd, cy + 13 * s, 1.5 * s, cloth, deep)
    # Stooped torso
    rs.draw_volume(surf, cloth, [
        (cx - 6.5 * s * facing + lunge * 0.1, cy - 0.5 * s), (cx + 5.5 * s * facing + lunge * 0.2, cy - 5 * s),
        (cx + 7.5 * s * facing + lunge * 0.15, cy + 5.5 * s), (cx - 7.5 * s * facing, cy + 6.5 * s),
    ], deep, 1)
    # Long arms
    rs.draw_volume_limb(surf, cx - 5 * s * facing, cy, cx - 11 * s * facing, cy + 7 * s, 1.2 * s, skin, deep)
    club_hand = (cx + 6.5 * s * facing + lunge * 0.45, cy - 2 * s - crouch * 3 * s)
    club_tip = (cx + 14 * s * facing + lunge, cy - 13 * s + strike * 8 * s)
    rs.draw_volume_limb(surf, cx + 4 * s * facing, cy - 3 * s, *club_hand, 1.2 * s, skin, deep)
    rs.draw_volume_limb(surf, *club_hand, *club_tip, 1.4 * s, (100, 72, 42), deep)
    pygame.draw.circle(surf, (82, 58, 34), (int(club_tip[0]), int(club_tip[1])), max(3, int(3.2 * s)))
    if strike > 0.65:
        pygame.draw.circle(surf, (255, 230, 160), (int(club_tip[0]), int(club_tip[1])), max(2, int(2.2 * s * strike)), 1)
    # Angular head seated on shoulders
    head = (cx + 2 * s * facing + lunge * 0.15, cy - 7.2 * s)
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
    # Existing full implementations
    "giant_rat": draw_giant_rat,
    "goblin": draw_goblin,
    "skeleton": draw_skeleton,
    "spider": draw_spider,
    "dragon": draw_dragon,
    "wolf": draw_wolf,
    "shade": draw_shade,
    "knight": draw_knight,
    
    # New imp types
    "ash_imp": draw_ash_imp,
    "void_imp": draw_void_imp,
    
    # Variants using existing base functions
    "big_skeleton": draw_skeleton,  # TODO: scale up or add more detail
    "ember_wolf": draw_wolf,  # TODO: add fire effects
    "shadow_knight": draw_knight,  # TODO: darken and add shadow effects
    "magma_knight": draw_knight,  # TODO: add fire/magma effects
    "guard": draw_knight,  # TODO: lighter armor, guard theme
    "crypt_ghoul": draw_skeleton,  # TODO: add flesh/decay
    "void_horror": draw_shade,  # TODO: add tentacles/horror elements
    "mythos_champion": draw_knight,  # TODO: elite armor, mythic effects
    
    # New types needed - using similar for now
    "giant": draw_knight,  # PLACEHOLDER: need new giant type (scaled up knight)
    "obsidian_colossus": draw_knight,  # PLACEHOLDER: need new colossus type
    "magma_slug": draw_giant_rat,  # PLACEHOLDER: need new slug type
    "crucible_beast": draw_wolf,  # PLACEHOLDER: need new beast type
}


def draw_monster(surf, mtype, cx, cy, tile, t, hurt=False, attacking=0.0, facing=1, moving=False):
    fn = MONSTER_DRAWERS.get(mtype, draw_giant_rat)
    try:
        fn(surf, cx, cy, tile, t, hurt=hurt, attacking=attacking, facing=facing, moving=moving)
    except TypeError:
        try:
            fn(surf, cx, cy, tile, t, hurt=hurt, attacking=attacking, facing=facing)
        except TypeError:
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
    if item.get("type") == "gem" or item_id in (
        "opal", "jade", "topaz", "sapphire", "emerald", "ruby", "diamond", "onyx",
    ):
        col = tuple(item.get("gem_color") or (150, 200, 230))
        dark = tuple(max(0, c - 50) for c in col)
        light = tuple(min(255, c + 40) for c in col)
        pts = [
            (cx, cy - s * 0.24), (cx + s * 0.18, cy - s * 0.04),
            (cx + s * 0.14, cy + s * 0.18), (cx, cy + s * 0.24),
            (cx - s * 0.14, cy + s * 0.18), (cx - s * 0.18, cy - s * 0.04),
        ]
        pygame.draw.polygon(surf, col, pts)
        pygame.draw.polygon(surf, dark, [
            (cx, cy - s * 0.24), (cx + s * 0.18, cy - s * 0.04), (cx, cy + s * 0.02),
            (cx - s * 0.18, cy - s * 0.04),
        ])
        pygame.draw.line(surf, light, (cx - s * 0.06, cy - s * 0.10), (cx + s * 0.04, cy + s * 0.06), 1)
        pygame.draw.polygon(surf, ink, pts, 1)
        return

    if item.get("equip_slot") == "ring" or item.get("type") == "jewelry" and "ring" in item_id:
        band = (230, 190, 60) if "gold" in item_id or "bronze" in item_id else (200, 200, 210)
        if "void" in item_id or "onyx" in item_id:
            band = (70, 60, 90)
        gem = tuple(item.get("gem_color") or band)
        pygame.draw.circle(surf, band, (cx, cy), int(s * 0.20), max(2, int(s * 0.07)))
        pygame.draw.circle(surf, ink, (cx, cy), int(s * 0.20), 1)
        if item_id != "gold_ring":
            pygame.draw.circle(surf, gem, (cx, cy - int(s * 0.02)), max(2, int(s * 0.08)))
            pygame.draw.circle(surf, ink, (cx, cy - int(s * 0.02)), max(2, int(s * 0.08)), 1)
            pygame.draw.circle(surf, (255, 255, 255), (cx - int(s * 0.03), cy - int(s * 0.05)), max(1, int(s * 0.025)))
        else:
            pygame.draw.circle(surf, (255, 230, 120), (cx - int(s * 0.06), cy - int(s * 0.06)), max(1, int(s * 0.04)))
        return

    if item_id in ("tidehollow_medal", "tidehollow_amulet") or item.get("equip_slot") == "amulet":
        # Amulet on a cord — gem face tinted by gem_color when present
        cord = (90, 70, 45)
        pygame.draw.arc(surf, cord, (cx - int(s * 0.18), cy - int(s * 0.32), int(s * 0.36), int(s * 0.28)), 3.6, 5.8, max(2, int(s * 0.04)))
        metal = (210, 170, 55)
        if "void" in item_id or "onyx" in item_id:
            metal = (90, 70, 120)
        elif "bronze" in item_id:
            metal = (180, 120, 60)
        pygame.draw.circle(surf, metal, (cx, cy + int(s * 0.04)), int(s * 0.22))
        pygame.draw.circle(surf, tuple(min(255, c + 40) for c in metal), (cx, cy + int(s * 0.04)), int(s * 0.17))
        gem = tuple(item.get("gem_color") or (40, 90, 120))
        pygame.draw.circle(surf, gem, (cx, cy + int(s * 0.05)), int(s * 0.10))
        pygame.draw.arc(
            surf, (min(255, gem[0] + 80), min(255, gem[1] + 80), min(255, gem[2] + 80)),
            (cx - int(s * 0.10), cy - int(s * 0.01), int(s * 0.20), int(s * 0.16)),
            3.4, 6.0, max(1, int(s * 0.035)),
        )
        pygame.draw.circle(surf, ink, (cx, cy + int(s * 0.04)), int(s * 0.22), 1)
        pygame.draw.circle(surf, (180, 140, 50), (cx, cy - int(s * 0.14)), max(2, int(s * 0.05)), 1)
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
        elif "crimson" in item_id:
            pygame.draw.ellipse(surf, (160, 40, 40), (cx - s * 0.2, cy - s * 0.1, s * 0.4, s * 0.28))
            pygame.draw.circle(surf, (255, 120, 40), (int(cx + s * 0.12), int(cy - s * 0.12)), int(s * 0.06))
        elif "frost" in item_id:
            pygame.draw.ellipse(surf, (70, 140, 200), (cx - s * 0.2, cy - s * 0.1, s * 0.4, s * 0.28))
            pygame.draw.circle(surf, (200, 240, 255), (int(cx + s * 0.12), int(cy - s * 0.12)), int(s * 0.06))
        elif "shadow" in item_id:
            pygame.draw.ellipse(surf, (50, 30, 80), (cx - s * 0.2, cy - s * 0.1, s * 0.4, s * 0.28))
            pygame.draw.circle(surf, (180, 80, 255), (int(cx + s * 0.12), int(cy - s * 0.12)), int(s * 0.06))
        elif "mythic" in item_id:
            pygame.draw.ellipse(surf, (200, 160, 50), (cx - s * 0.2, cy - s * 0.1, s * 0.4, s * 0.28))
            pygame.draw.circle(surf, (255, 100, 220), (int(cx + s * 0.12), int(cy - s * 0.12)), int(s * 0.06))
        else:
            pygame.draw.ellipse(surf, (45, 140, 80), (cx - s * 0.2, cy - s * 0.1, s * 0.4, s * 0.28))
            pygame.draw.circle(surf, (255, 200, 60), (int(cx + s * 0.12), int(cy - s * 0.12)), int(s * 0.06))
        return
    # --- Fletching / archery gear (clear inventory silhouettes) ---
    if item_id == "knife" or item.get("tool_for") == "fletching":
        # Carving knife — wood grip, rivets, sharp blade
        wood, wood_l = (118, 78, 42), (160, 115, 70)
        steel, steel_l, steel_d = (190, 195, 205), (235, 238, 245), (110, 115, 125)
        # Grip
        pygame.draw.polygon(surf, wood, [
            (cx - s * 0.08, cy + s * 0.08), (cx + s * 0.10, cy + s * 0.04),
            (cx + s * 0.12, cy + s * 0.28), (cx - s * 0.10, cy + s * 0.32),
        ])
        pygame.draw.polygon(surf, wood_l, [
            (cx - s * 0.04, cy + s * 0.10), (cx + s * 0.06, cy + s * 0.07),
            (cx + s * 0.07, cy + s * 0.22), (cx - s * 0.03, cy + s * 0.24),
        ])
        for ry in (0.14, 0.22):
            pygame.draw.circle(surf, (70, 55, 40), (int(cx + s * 0.01), int(cy + s * ry)), max(1, int(s * 0.03)))
        # Blade
        pygame.draw.polygon(surf, steel_d, [
            (cx - s * 0.06, cy + s * 0.06), (cx + s * 0.08, cy + s * 0.02),
            (cx + s * 0.04, cy - s * 0.30), (cx - s * 0.02, cy - s * 0.28),
        ])
        pygame.draw.polygon(surf, steel, [
            (cx - s * 0.02, cy + s * 0.04), (cx + s * 0.05, cy + s * 0.01),
            (cx + s * 0.02, cy - s * 0.28), (cx - s * 0.01, cy - s * 0.26),
        ])
        pygame.draw.line(surf, steel_l, (cx + s * 0.01, cy + s * 0.02), (cx + s * 0.015, cy - s * 0.26), max(1, int(s * 0.03)))
        pygame.draw.polygon(surf, ink, [
            (cx - s * 0.06, cy + s * 0.06), (cx + s * 0.08, cy + s * 0.02),
            (cx + s * 0.04, cy - s * 0.30), (cx - s * 0.02, cy - s * 0.28),
        ], 1)
        return
    if item_id == "feather":
        # Quill feather
        vane = (245, 245, 250)
        vane_d = (200, 205, 215)
        tip = (255, 230, 140)
        pygame.draw.polygon(surf, vane_d, [
            (cx - s * 0.02, cy - s * 0.30), (cx + s * 0.18, cy - s * 0.02),
            (cx + s * 0.04, cy + s * 0.26), (cx - s * 0.16, cy + s * 0.02),
        ])
        pygame.draw.polygon(surf, vane, [
            (cx, cy - s * 0.26), (cx + s * 0.12, cy - s * 0.02),
            (cx + s * 0.02, cy + s * 0.18), (cx - s * 0.10, cy + s * 0.02),
        ])
        # Spine
        pygame.draw.line(surf, tip, (cx - s * 0.02, cy - s * 0.28), (cx + s * 0.02, cy + s * 0.24), max(2, int(s * 0.04)))
        for i in range(4):
            t = -0.18 + i * 0.09
            pygame.draw.line(surf, vane_d, (cx, cy + t * s), (cx + s * 0.12, cy + (t + 0.04) * s), 1)
            pygame.draw.line(surf, vane_d, (cx, cy + t * s), (cx - s * 0.10, cy + (t + 0.04) * s), 1)
        return
    if item_id == "bow_string":
        # Hank / coil of string
        coil = (230, 220, 185)
        coil_d = (170, 155, 110)
        for i, (ox, oy, rad) in enumerate(((-0.06, -0.04, 0.16), (0.05, 0.02, 0.15), (0.0, 0.10, 0.12))):
            pygame.draw.circle(surf, coil_d if i else coil, (int(cx + ox * s), int(cy + oy * s)), max(3, int(rad * s)))
            pygame.draw.circle(surf, coil, (int(cx + ox * s - 1), int(cy + oy * s - 1)), max(2, int(rad * s * 0.55)))
        pygame.draw.arc(surf, coil_d, (cx - s * 0.2, cy - s * 0.18, s * 0.4, s * 0.36), 0.2, 5.5, max(2, int(s * 0.04)))
        return
    if item_id == "arrow_shaft":
        # Bundle of wooden shafts
        wood = (150, 105, 55)
        wood_l = (190, 145, 90)
        for i, ang in enumerate((-0.25, 0.0, 0.25)):
            dx, dy = math.sin(ang) * s * 0.08, 0
            pygame.draw.line(surf, wood, (cx + dx - s * 0.02, cy + s * 0.26), (cx + dx + s * 0.04, cy - s * 0.26), max(2, int(s * 0.05)))
            pygame.draw.line(surf, wood_l, (cx + dx, cy + s * 0.18), (cx + dx + s * 0.03, cy - s * 0.18), 1)
        return
    if item_id == "arrow_quiver":
        # Leather quiver with fletched arrows peeking out
        leather, leather_l = (118, 78, 42), (160, 115, 70)
        pygame.draw.ellipse(surf, leather, (cx - s * 0.18, cy - s * 0.02, s * 0.36, s * 0.34))
        pygame.draw.ellipse(surf, leather_l, (cx - s * 0.14, cy + s * 0.02, s * 0.22, s * 0.18))
        pygame.draw.ellipse(surf, ink, (cx - s * 0.18, cy - s * 0.02, s * 0.36, s * 0.34), 1)
        for ox, tip in ((-0.08, (200, 150, 75)), (0.0, (150, 152, 160)), (0.08, (100, 170, 210))):
            pygame.draw.line(
                surf, (180, 175, 160),
                (cx + ox * s, cy + s * 0.06), (cx + ox * s, cy - s * 0.28), max(1, int(s * 0.05)),
            )
            pygame.draw.polygon(surf, tip, [
                (cx + ox * s, cy - s * 0.34),
                (cx + (ox - 0.05) * s, cy - s * 0.22),
                (cx + (ox + 0.05) * s, cy - s * 0.22),
            ])
        return
    if item_id == "arrowtip_box":
        # Small wooden chest with metal tip glints
        wood, wood_l = (110, 78, 42), (150, 112, 70)
        pygame.draw.rect(surf, wood, (cx - s * 0.22, cy - s * 0.10, s * 0.44, s * 0.28), border_radius=max(2, int(s * 0.04)))
        pygame.draw.rect(surf, wood_l, (cx - s * 0.20, cy - s * 0.08, s * 0.40, s * 0.10), border_radius=2)
        pygame.draw.rect(surf, ink, (cx - s * 0.22, cy - s * 0.10, s * 0.44, s * 0.28), 1, border_radius=max(2, int(s * 0.04)))
        pygame.draw.line(surf, (90, 70, 40), (cx - s * 0.22, cy + s * 0.02), (cx + s * 0.22, cy + s * 0.02), 1)
        pygame.draw.circle(surf, (200, 170, 70), (cx, cy + s * 0.04), max(2, int(s * 0.05)))
        for ox, tip in ((-0.10, (200, 150, 75)), (0.0, (150, 152, 160)), (0.10, (100, 170, 210))):
            pygame.draw.polygon(surf, tip, [
                (cx + ox * s, cy - s * 0.22),
                (cx + (ox - 0.05) * s, cy - s * 0.08),
                (cx + (ox + 0.05) * s, cy - s * 0.08),
            ])
        return
    if item_id == "food_bag":
        # Soft satchel with cooked fish glints
        cloth, cloth_l = (140, 95, 55), (180, 135, 85)
        pygame.draw.ellipse(surf, cloth, (cx - s * 0.22, cy - s * 0.06, s * 0.44, s * 0.30))
        pygame.draw.ellipse(surf, cloth_l, (cx - s * 0.16, cy - s * 0.02, s * 0.28, s * 0.14))
        pygame.draw.ellipse(surf, ink, (cx - s * 0.22, cy - s * 0.06, s * 0.44, s * 0.30), 1)
        pygame.draw.arc(surf, (100, 70, 40), (cx - s * 0.10, cy - s * 0.22, s * 0.20, s * 0.18), 0.2, 2.9, max(2, int(s * 0.04)))
        for ox, col in ((-0.08, (230, 160, 90)), (0.06, (210, 140, 80))):
            pygame.draw.ellipse(surf, col, (cx + ox * s - s * 0.06, cy + s * 0.02, s * 0.12, s * 0.08))
        return
    if item_id == "raw_food_bag":
        # Cooler-toned satchel with raw fish silhouette
        cloth, cloth_l = (70, 100, 120), (110, 145, 165)
        pygame.draw.ellipse(surf, cloth, (cx - s * 0.22, cy - s * 0.06, s * 0.44, s * 0.30))
        pygame.draw.ellipse(surf, cloth_l, (cx - s * 0.16, cy - s * 0.02, s * 0.28, s * 0.14))
        pygame.draw.ellipse(surf, ink, (cx - s * 0.22, cy - s * 0.06, s * 0.44, s * 0.30), 1)
        pygame.draw.arc(surf, (50, 70, 90), (cx - s * 0.10, cy - s * 0.22, s * 0.20, s * 0.18), 0.2, 2.9, max(2, int(s * 0.04)))
        pygame.draw.ellipse(surf, (160, 190, 210), (cx - s * 0.10, cy, s * 0.20, s * 0.10))
        pygame.draw.circle(surf, (40, 50, 60), (cx + int(s * 0.06), cy + int(s * 0.04)), max(1, int(s * 0.03)))
        return
    if item_id == "mining_bag":
        # Sturdy ore sack with copper/iron glints
        cloth, cloth_l = (90, 75, 55), (130, 110, 80)
        pygame.draw.ellipse(surf, cloth, (cx - s * 0.22, cy - s * 0.04, s * 0.44, s * 0.28))
        pygame.draw.ellipse(surf, cloth_l, (cx - s * 0.14, cy, s * 0.28, s * 0.12))
        pygame.draw.ellipse(surf, ink, (cx - s * 0.22, cy - s * 0.04, s * 0.44, s * 0.28), 1)
        pygame.draw.arc(surf, (60, 50, 35), (cx - s * 0.10, cy - s * 0.20, s * 0.20, s * 0.16), 0.2, 2.9, max(2, int(s * 0.04)))
        for ox, col in ((-0.08, (180, 110, 60)), (0.06, (140, 145, 150))):
            pygame.draw.polygon(surf, col, [
                (cx + ox * s, cy - s * 0.02),
                (cx + (ox - 0.06) * s, cy + s * 0.10),
                (cx + (ox + 0.06) * s, cy + s * 0.10),
            ])
        return
    if item_id == "log_bag":
        cloth, cloth_l = (100, 70, 40), (140, 105, 65)
        pygame.draw.ellipse(surf, cloth, (cx - s * 0.22, cy - s * 0.04, s * 0.44, s * 0.28))
        pygame.draw.ellipse(surf, cloth_l, (cx - s * 0.14, cy, s * 0.28, s * 0.12))
        pygame.draw.ellipse(surf, ink, (cx - s * 0.22, cy - s * 0.04, s * 0.44, s * 0.28), 1)
        pygame.draw.arc(surf, (70, 50, 30), (cx - s * 0.10, cy - s * 0.20, s * 0.20, s * 0.16), 0.2, 2.9, max(2, int(s * 0.04)))
        pygame.draw.rect(surf, (120, 85, 45), (cx - s * 0.10, cy, s * 0.20, s * 0.08), border_radius=2)
        pygame.draw.line(surf, (80, 55, 30), (cx - s * 0.02, cy), (cx - s * 0.02, cy + s * 0.08), 1)
        return
    if item_id == "fletch_pouch":
        cloth, cloth_l = (80, 95, 60), (120, 140, 90)
        pygame.draw.ellipse(surf, cloth, (cx - s * 0.20, cy - s * 0.04, s * 0.40, s * 0.26))
        pygame.draw.ellipse(surf, cloth_l, (cx - s * 0.12, cy, s * 0.24, s * 0.12))
        pygame.draw.ellipse(surf, ink, (cx - s * 0.20, cy - s * 0.04, s * 0.40, s * 0.26), 1)
        pygame.draw.line(surf, (200, 200, 210), (cx - s * 0.08, cy + s * 0.02), (cx + s * 0.10, cy - s * 0.10), max(2, int(s * 0.04)))
        pygame.draw.circle(surf, (240, 230, 180), (cx + int(s * 0.08), cy - int(s * 0.02)), max(2, int(s * 0.04)))
        return
    if item_id == "potion_pouch":
        cloth, cloth_l = (90, 60, 110), (130, 95, 155)
        pygame.draw.ellipse(surf, cloth, (cx - s * 0.20, cy - s * 0.04, s * 0.40, s * 0.26))
        pygame.draw.ellipse(surf, cloth_l, (cx - s * 0.12, cy, s * 0.24, s * 0.12))
        pygame.draw.ellipse(surf, ink, (cx - s * 0.20, cy - s * 0.04, s * 0.40, s * 0.26), 1)
        pygame.draw.rect(surf, (160, 80, 200), (cx - s * 0.04, cy - s * 0.02, s * 0.08, s * 0.12), border_radius=2)
        pygame.draw.rect(surf, (200, 160, 230), (cx - s * 0.03, cy - s * 0.06, s * 0.06, s * 0.04), border_radius=1)
        return
    if item_id == "gem_bag":
        # Soft velvet pouch with sapphire / ruby / emerald glints
        cloth, cloth_l = (55, 70, 100), (90, 115, 150)
        pygame.draw.ellipse(surf, cloth, (cx - s * 0.20, cy - s * 0.04, s * 0.40, s * 0.26))
        pygame.draw.ellipse(surf, cloth_l, (cx - s * 0.12, cy, s * 0.24, s * 0.12))
        pygame.draw.ellipse(surf, ink, (cx - s * 0.20, cy - s * 0.04, s * 0.40, s * 0.26), 1)
        pygame.draw.arc(surf, (40, 50, 70), (cx - s * 0.09, cy - s * 0.20, s * 0.18, s * 0.16), 0.2, 2.9, max(2, int(s * 0.04)))
        for ox, col in ((-0.07, (50, 90, 210)), (0.0, (200, 40, 50)), (0.07, (40, 170, 90))):
            pygame.draw.polygon(surf, col, [
                (cx + ox * s, cy - s * 0.04),
                (cx + (ox - 0.045) * s, cy + s * 0.08),
                (cx + (ox + 0.045) * s, cy + s * 0.08),
            ])
            pygame.draw.circle(surf, tuple(min(255, c + 60) for c in col),
                               (cx + int(ox * s), cy + int(s * 0.01)), max(1, int(s * 0.025)))
        return
    if item_id == "headless_arrow":
        wood = (140, 95, 50)
        vane = (240, 240, 245)
        pygame.draw.line(surf, wood, (cx - s * 0.18, cy + s * 0.18), (cx + s * 0.22, cy - s * 0.22), max(2, int(s * 0.05)))
        pygame.draw.polygon(surf, vane, [
            (cx - s * 0.18, cy + s * 0.18), (cx - s * 0.28, cy + s * 0.08), (cx - s * 0.10, cy + s * 0.10),
        ])
        pygame.draw.polygon(surf, vane, [
            (cx - s * 0.18, cy + s * 0.18), (cx - s * 0.08, cy + s * 0.28), (cx - s * 0.10, cy + s * 0.10),
        ])
        return
    if item_id.endswith("_arrowtips") or item_id.endswith("arrowtips"):
        tip = (175, 178, 188)
        if "bronze" in item_id:
            tip = (200, 150, 75)
        elif "iron" in item_id:
            tip = (150, 152, 160)
        elif "steel" in item_id:
            tip = (170, 175, 185)
        elif "mithril" in item_id:
            tip = (100, 170, 210)
        elif "adamant" in item_id:
            tip = (70, 190, 120)
        tip_l = tuple(min(255, c + 40) for c in tip)
        # Stack of arrowheads
        for i, (ox, oy) in enumerate(((-0.08, 0.06), (0.02, -0.02), (0.10, 0.08))):
            base = (cx + ox * s, cy + oy * s)
            pygame.draw.polygon(surf, tip, [
                (base[0], base[1] - s * 0.18),
                (base[0] - s * 0.08, base[1] + s * 0.06),
                (base[0] + s * 0.08, base[1] + s * 0.06),
            ])
            pygame.draw.polygon(surf, tip_l, [
                (base[0], base[1] - s * 0.16),
                (base[0] - s * 0.03, base[1] - s * 0.02),
                (base[0] + s * 0.03, base[1] - s * 0.02),
            ])
        return
    if itype == "ammo" or (item_id.endswith("_arrow") and "tip" not in item_id):
        tip = (175, 178, 188)
        if "bronze" in item_id:
            tip = (200, 150, 75)
        elif "iron" in item_id:
            tip = (150, 152, 160)
        elif "steel" in item_id:
            tip = (170, 175, 185)
        elif "mithril" in item_id:
            tip = (100, 170, 210)
        elif "adamant" in item_id:
            tip = (70, 190, 120)
        wood = (130, 90, 45)
        vane = (245, 245, 250)
        # Diagonal arrow
        pygame.draw.line(surf, wood, (cx - s * 0.20, cy + s * 0.18), (cx + s * 0.18, cy - s * 0.18), max(2, int(s * 0.055)))
        pygame.draw.polygon(surf, tip, [
            (cx + s * 0.26, cy - s * 0.26), (cx + s * 0.10, cy - s * 0.22), (cx + s * 0.18, cy - s * 0.08),
        ])
        pygame.draw.polygon(surf, vane, [
            (cx - s * 0.20, cy + s * 0.18), (cx - s * 0.30, cy + s * 0.06), (cx - s * 0.12, cy + s * 0.10),
        ])
        pygame.draw.polygon(surf, vane, [
            (cx - s * 0.20, cy + s * 0.18), (cx - s * 0.08, cy + s * 0.28), (cx - s * 0.12, cy + s * 0.10),
        ])
        return
    if "shortbow" in item_id or (itype == "weapon" and item.get("weapon_type") == "bow"):
        # Curved bow with (or without) string
        wood = (120, 82, 42)
        if "oak" in item_id:
            wood = (100, 68, 32)
        elif "willow" in item_id:
            wood = (140, 115, 55)
        elif "maple" in item_id:
            wood = (160, 90, 40)
        elif "yew" in item_id:
            wood = (70, 50, 28)
        elif "magic" in item_id:
            wood = (90, 70, 130)
        wood_l = tuple(min(255, c + 35) for c in wood)
        rect = (cx - int(s * 0.22), cy - int(s * 0.30), int(s * 0.36), int(s * 0.60))
        pygame.draw.arc(surf, wood, rect, 0.55, 2.6, max(3, int(s * 0.07)))
        pygame.draw.arc(surf, wood_l, rect, 0.7, 2.4, max(1, int(s * 0.03)))
        if "unstrung" not in item_id:
            pygame.draw.line(
                surf, (220, 210, 175),
                (cx - int(s * 0.08), cy + int(s * 0.26)),
                (cx + int(s * 0.10), cy - int(s * 0.26)),
                max(1, int(s * 0.035)),
            )
        else:
            # Unstrung: show stave nocks only
            pygame.draw.circle(surf, wood_l, (cx - int(s * 0.06), cy + int(s * 0.26)), max(2, int(s * 0.04)))
            pygame.draw.circle(surf, wood_l, (cx + int(s * 0.08), cy - int(s * 0.26)), max(2, int(s * 0.04)))
        return
    if itype == "weapon" or (item.get("tool_for") in ("woodcutting",) and "axe" in item_id):
        # Detailed inventory silhouettes — bevelled blade, guard, wrap, pommel
        if "iron" in item_id:
            blade, blade_l, blade_d = (150, 152, 160), (200, 202, 210), (90, 92, 100)
        elif "steel" in item_id:
            blade, blade_l, blade_d = (170, 175, 185), (220, 225, 235), (100, 105, 115)
        elif "bronze" in item_id:
            blade, blade_l, blade_d = (200, 150, 75), (235, 195, 120), (140, 95, 45)
        elif "mithril" in item_id:
            blade, blade_l, blade_d = (100, 170, 210), (160, 220, 245), (55, 100, 140)
        elif "adamant" in item_id:
            blade, blade_l, blade_d = (70, 190, 120), (140, 235, 170), (35, 110, 70)
        elif "mythos" in item_id:
            blade, blade_l, blade_d = (190, 40, 48), (255, 110, 100), (95, 12, 18)
        elif "eclipse" in item_id:
            blade, blade_l, blade_d = (42, 42, 50), (95, 95, 105), (12, 12, 16)
        else:
            blade, blade_l, blade_d = (175, 178, 188), (220, 222, 230), (110, 112, 120)
        gold, gold_d = (228, 196, 70), (160, 120, 40)
        wood, wood_l = (110, 75, 42), (145, 105, 65)

        def icon_sword(short=False):
            tip = cy - s * (0.30 if short else 0.34)
            base_y = cy + s * 0.10
            hw = s * (0.07 if short else 0.09)
            # Blade body
            stroke_poly(blade_d, [
                (cx - hw, base_y), (cx + hw * 1.15, base_y - s * 0.02),
                (cx + hw * 0.35, tip + s * 0.04), (cx, tip),
                (cx - hw * 0.35, tip + s * 0.04), (cx - hw * 1.05, base_y - s * 0.02),
            ])
            pygame.draw.polygon(surf, blade, [
                (cx - hw * 0.55, base_y - s * 0.02), (cx + hw * 0.7, base_y - s * 0.04),
                (cx + hw * 0.2, tip + s * 0.06), (cx, tip + s * 0.02),
            ])
            pygame.draw.polygon(surf, blade_l, [
                (cx - hw * 0.15, base_y - s * 0.04), (cx + hw * 0.35, base_y - s * 0.06),
                (cx + hw * 0.12, tip + s * 0.1), (cx - hw * 0.05, tip + s * 0.08),
            ])
            # Fuller
            pygame.draw.line(surf, blade_d, (cx, base_y - s * 0.02), (cx, tip + s * 0.08), 1)
            # Crossguard
            gw = s * (0.18 if short else 0.22)
            stroke_poly(gold_d, [
                (cx - gw, base_y + s * 0.01), (cx + gw, base_y - s * 0.01),
                (cx + gw + s * 0.02, base_y + s * 0.06), (cx - gw - s * 0.02, base_y + s * 0.08),
            ])
            pygame.draw.line(surf, gold, (cx - gw + 2, base_y + s * 0.03), (cx + gw - 2, base_y + s * 0.03), 1)
            # Grip wrap
            gy0, gy1 = base_y + s * 0.08, base_y + s * (0.22 if short else 0.26)
            pygame.draw.rect(surf, wood, (cx - s * 0.045, gy0, s * 0.09, gy1 - gy0))
            for i in range(3):
                yy = gy0 + (i + 0.5) * (gy1 - gy0) / 3
                pygame.draw.line(surf, wood_l, (cx - s * 0.04, yy), (cx + s * 0.04, yy), 1)
            # Pommel
            pygame.draw.circle(surf, gold_d, (int(cx), int(gy1 + s * 0.035)), max(2, int(s * 0.055)))
            pygame.draw.circle(surf, gold, (int(cx - 1), int(gy1 + s * 0.02)), max(1, int(s * 0.03)))

        if "dagger" in item_id:
            icon_sword(short=True)
        elif "battleaxe" in item_id or "cleaver" in item_id:
            # Classic battleaxe icon — slim haft, crescent bit + rear fluke
            eclipse = "eclipse" in item_id
            haft = (28, 28, 34) if eclipse else wood
            haft_l = (70, 70, 78) if eclipse else wood_l
            pygame.draw.line(surf, haft, (cx - s * 0.01, cy + s * 0.30), (cx + s * 0.02, cy - s * 0.28), max(2, int(s * 0.07)))
            pygame.draw.line(surf, haft_l, (cx, cy + s * 0.24), (cx + s * 0.015, cy - s * 0.22), max(1, int(s * 0.03)))
            # Top spike
            pygame.draw.polygon(surf, blade_d, [
                (cx - s * 0.03, cy - s * 0.26), (cx + s * 0.05, cy - s * 0.26), (cx + s * 0.01, cy - s * 0.36),
            ])
            if eclipse:
                pygame.draw.polygon(surf, gold, [
                    (cx - s * 0.015, cy - s * 0.27), (cx + s * 0.035, cy - s * 0.27), (cx + s * 0.01, cy - s * 0.33),
                ])
            # Crescent cutting bit
            stroke_poly(blade_d, [
                (cx + s * 0.02, cy - s * 0.24), (cx + s * 0.26, cy - s * 0.30),
                (cx + s * 0.30, cy - s * 0.16), (cx + s * 0.24, cy - s * 0.04),
                (cx + s * 0.10, cy - s * 0.06), (cx + s * 0.03, cy - s * 0.14),
            ])
            pygame.draw.polygon(surf, blade_l, [
                (cx + s * 0.05, cy - s * 0.24), (cx + s * 0.22, cy - s * 0.28),
                (cx + s * 0.26, cy - s * 0.16), (cx + s * 0.18, cy - s * 0.08),
                (cx + s * 0.07, cy - s * 0.12),
            ])
            edge_col = gold if eclipse else (245, 245, 250)
            pygame.draw.line(surf, edge_col, (cx + s * 0.25, cy - s * 0.28), (cx + s * 0.28, cy - s * 0.12), 1)
            # Rear fluke
            stroke_poly(blade, [
                (cx - s * 0.01, cy - s * 0.22), (cx - s * 0.16, cy - s * 0.26),
                (cx - s * 0.18, cy - s * 0.16), (cx - s * 0.08, cy - s * 0.12),
            ])
            pygame.draw.circle(surf, gold, (int(cx + s * 0.02), int(cy - s * 0.16)), max(2, int(s * 0.04)))
            if eclipse:
                # Mini dragon emblem
                pygame.draw.circle(surf, gold_d, (int(cx + s * 0.12), int(cy - s * 0.16)), max(2, int(s * 0.055)))
                pygame.draw.circle(surf, (20, 20, 24), (int(cx + s * 0.12), int(cy - s * 0.16)), max(1, int(s * 0.04)))
                pygame.draw.polygon(surf, gold, [
                    (cx + s * 0.08, cy - s * 0.16), (cx + s * 0.11, cy - s * 0.22),
                    (cx + s * 0.18, cy - s * 0.15), (cx + s * 0.12, cy - s * 0.12),
                ])
        elif "axe" in item_id:
            pygame.draw.line(surf, wood, (cx - s * 0.04, cy + s * 0.26), (cx + s * 0.08, cy - s * 0.24), max(2, int(s * 0.09)))
            pygame.draw.line(surf, wood_l, (cx - s * 0.01, cy + s * 0.2), (cx + s * 0.06, cy - s * 0.18), 1)
            stroke_poly(blade_d, [
                (cx + s * 0.02, cy - s * 0.26), (cx + s * 0.30, cy - s * 0.22),
                (cx + s * 0.26, cy - s * 0.02), (cx + s * 0.04, cy - s * 0.06),
            ])
            pygame.draw.polygon(surf, blade_l, [
                (cx + s * 0.06, cy - s * 0.24), (cx + s * 0.22, cy - s * 0.20),
                (cx + s * 0.20, cy - s * 0.08), (cx + s * 0.08, cy - s * 0.10),
            ])
            pygame.draw.line(surf, (245, 245, 250), (cx + s * 0.28, cy - s * 0.22), (cx + s * 0.24, cy - s * 0.04), 1)
            pygame.draw.circle(surf, gold_d, (int(cx + s * 0.04), int(cy - s * 0.08)), max(2, int(s * 0.045)))
        else:
            icon_sword(short=False)
        return
    if item.get("tool_for") == "mining":
        # Pickaxe — wood haft + metal head tinted by ore tier
        mid, dark, light, _ = rs.metal_palette(item_id)
        wood, wood_l = (118, 78, 42), (160, 115, 70)
        pygame.draw.line(surf, wood, (cx - s * 0.02, cy + s * 0.28), (cx + s * 0.04, cy - s * 0.08), max(3, int(s * 0.09)))
        pygame.draw.line(surf, wood_l, (cx, cy + s * 0.2), (cx + s * 0.03, cy - s * 0.02), 1)
        # Curved pick head
        stroke_poly(mid, [
            (cx - s * 0.26, cy - s * 0.06), (cx - s * 0.02, cy - s * 0.22),
            (cx + s * 0.22, cy - s * 0.28), (cx + s * 0.18, cy - s * 0.14),
            (cx + s * 0.02, cy - s * 0.10), (cx - s * 0.18, cy + s * 0.04),
        ])
        pygame.draw.polygon(surf, light, [
            (cx - s * 0.08, cy - s * 0.18), (cx + s * 0.12, cy - s * 0.24),
            (cx + s * 0.10, cy - s * 0.16), (cx - s * 0.04, cy - s * 0.12),
        ])
        # Point tip
        pygame.draw.polygon(surf, dark, [
            (cx + s * 0.18, cy - s * 0.26), (cx + s * 0.30, cy - s * 0.22),
            (cx + s * 0.16, cy - s * 0.16),
        ])
        return
    if item.get("tool_for") == "fishing":
        wood, wood_l = (118, 78, 42), (160, 115, 70)
        if "net" in item_id:
            # Hand net — wooden hoop + mesh
            pygame.draw.circle(surf, wood, (cx, cy + int(s * 0.02)), int(s * 0.22), max(2, int(s * 0.06)))
            pygame.draw.circle(surf, wood_l, (cx - int(s * 0.04), cy - int(s * 0.02)), int(s * 0.18), 1)
            mesh = (190, 200, 215)
            for i in range(-2, 3):
                pygame.draw.line(surf, mesh, (cx + i * s * 0.07, cy - s * 0.16), (cx + i * s * 0.07, cy + s * 0.20), 1)
                pygame.draw.line(surf, mesh, (cx - s * 0.16, cy + i * s * 0.07), (cx + s * 0.16, cy + i * s * 0.07), 1)
            # Handle
            pygame.draw.line(surf, wood, (cx + s * 0.12, cy + s * 0.16), (cx + s * 0.26, cy + s * 0.28), max(2, int(s * 0.05)))
        elif "pot" in item_id:
            # Lobster pot — woven basket with lid ring
            bask, bask_d = (130, 100, 55), (90, 70, 40)
            pygame.draw.ellipse(surf, bask, (cx - s * 0.22, cy - s * 0.06, s * 0.44, s * 0.30))
            pygame.draw.ellipse(surf, bask_d, (cx - s * 0.18, cy - s * 0.14, s * 0.36, s * 0.14), max(2, int(s * 0.04)))
            for i in range(4):
                xx = cx - s * 0.14 + i * s * 0.09
                pygame.draw.line(surf, bask_d, (xx, cy - s * 0.08), (xx, cy + s * 0.18), 1)
            pygame.draw.ellipse(surf, (60, 100, 140), (cx - s * 0.10, cy - s * 0.12, s * 0.20, s * 0.10))
            pygame.draw.ellipse(surf, ink, (cx - s * 0.22, cy - s * 0.06, s * 0.44, s * 0.30), 1)
        elif "harpoon" in item_id:
            # Barbed harpoon — long haft + multi-prong tip
            pygame.draw.line(surf, wood, (cx - s * 0.22, cy + s * 0.22), (cx + s * 0.14, cy - s * 0.18), max(2, int(s * 0.06)))
            pygame.draw.line(surf, wood_l, (cx - s * 0.18, cy + s * 0.16), (cx + s * 0.10, cy - s * 0.12), 1)
            steel = (190, 195, 205)
            tip = (cx + s * 0.14, cy - s * 0.18)
            for ox, oy in ((0.14, -0.04), (0.10, 0.02), (0.06, 0.08)):
                pygame.draw.polygon(surf, steel, [
                    tip, (cx + ox * s, cy + oy * s), (cx + (ox - 0.04) * s, cy + (oy + 0.04) * s),
                ])
            pygame.draw.circle(surf, (200, 170, 60), (int(cx - s * 0.02), int(cy + s * 0.02)), max(1, int(s * 0.035)))
        else:
            # fishing / fly rod with reel
            pygame.draw.line(surf, wood, (cx - s * 0.24, cy + s * 0.22), (cx + s * 0.22, cy - s * 0.24), max(2, int(s * 0.05)))
            pygame.draw.line(surf, wood_l, (cx - s * 0.18, cy + s * 0.14), (cx + s * 0.16, cy - s * 0.16), 1)
            # Reel
            pygame.draw.circle(surf, (90, 95, 105), (int(cx - s * 0.06), int(cy + s * 0.08)), max(3, int(s * 0.07)))
            pygame.draw.circle(surf, (150, 155, 165), (int(cx - s * 0.06), int(cy + s * 0.08)), max(2, int(s * 0.04)))
            # Line + hook / fly
            pygame.draw.line(surf, (200, 200, 210), (cx + s * 0.22, cy - s * 0.24), (cx + s * 0.14, cy + s * 0.06), 1)
            if "fly" in item_id:
                pygame.draw.circle(surf, (80, 180, 120), (int(cx + s * 0.14), int(cy + s * 0.06)), max(2, int(s * 0.04)))
                pygame.draw.circle(surf, (255, 200, 80), (int(cx + s * 0.16), int(cy + s * 0.04)), max(1, int(s * 0.02)))
            else:
                pygame.draw.polygon(surf, (180, 185, 195), [
                    (cx + s * 0.14, cy + s * 0.06), (cx + s * 0.20, cy + s * 0.12),
                    (cx + s * 0.10, cy + s * 0.12),
                ])
        return
    if item.get("equip_slot") == "shield":
        if "eclipse" in item_id:
            # Eclipse Aegis — black steel, gold rim, eclipse disc + dragon crest
            black, face, face_l = (12, 12, 16), (42, 42, 50), (90, 90, 100)
            gold, gold_d, gold_l = (228, 196, 78), (160, 120, 40), (255, 230, 140)
            pts = [
                (cx - s * 0.24, cy - s * 0.22), (cx + s * 0.24, cy - s * 0.22),
                (cx + s * 0.22, cy + s * 0.08), (cx, cy + s * 0.30), (cx - s * 0.22, cy + s * 0.08),
            ]
            stroke_poly(face, pts)
            pygame.draw.polygon(surf, face_l, [
                (cx - s * 0.16, cy - s * 0.18), (cx + s * 0.06, cy - s * 0.18),
                (cx + s * 0.08, cy), (cx - s * 0.14, cy + s * 0.02),
            ])
            pygame.draw.polygon(surf, gold_d, pts, max(2, int(s * 0.06)))
            pygame.draw.polygon(surf, gold, pts, max(1, int(s * 0.03)))
            for ox, oy in ((-0.18, -0.18), (0.18, -0.18), (0.2, 0.02), (0.0, 0.24), (-0.2, 0.02)):
                pygame.draw.circle(surf, gold_d, (int(cx + ox * s), int(cy + oy * s)), max(1, int(s * 0.025)))
            pygame.draw.circle(surf, gold_d, (int(cx), int(cy + s * 0.01)), max(3, int(s * 0.11)))
            pygame.draw.circle(surf, gold, (int(cx), int(cy + s * 0.01)), max(3, int(s * 0.11)), max(1, int(s * 0.025)))
            pygame.draw.circle(surf, black, (int(cx), int(cy + s * 0.01)), max(2, int(s * 0.08)))
            pygame.draw.circle(surf, gold, (int(cx - s * 0.03), int(cy - s * 0.01)), max(2, int(s * 0.05)), 1)
            # Mini dragon
            pygame.draw.polygon(surf, gold, [
                (cx - s * 0.05, cy + s * 0.01), (cx - s * 0.02, cy - s * 0.07),
                (cx + s * 0.06, cy - s * 0.02), (cx + s * 0.02, cy + s * 0.05),
            ])
            pygame.draw.circle(surf, (255, 70, 45), (int(cx + s * 0.01), int(cy - s * 0.02)), max(1, int(s * 0.015)))
            pygame.draw.circle(surf, gold_l, (int(cx), int(cy + s * 0.24)), max(1, int(s * 0.03)))
            return
        mid = (178, 28, 38) if "mythos" in item_id else (
            (150, 155, 165) if "iron" in item_id else (
                (120, 140, 160) if "steel" in item_id else (
                    (100, 180, 220) if "mithril" in item_id else (
                        (70, 200, 120) if "adamant" in item_id else (
                            (180, 130, 70) if "bronze" in item_id else (140, 100, 55)
                        )
                    )
                )
            )
        )
        dark = tuple(max(0, c - 45) for c in mid)
        light = tuple(min(255, c + 35) for c in mid)
        if "mythos" in item_id:
            light, dark = (245, 95, 88), (88, 10, 16)
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
            if "eclipse" in item_id:
                # Grillhelm — black dome, gold crown, barred face
                black, face, face_l = (12, 12, 16), (42, 42, 50), (90, 90, 100)
                gold, gold_d, gold_l = (228, 196, 78), (160, 120, 40), (255, 230, 140)
                pygame.draw.ellipse(surf, face, (cx - s * 0.18, cy - s * 0.2, s * 0.36, s * 0.38))
                pygame.draw.ellipse(surf, face_l, (cx - s * 0.1, cy - s * 0.18, s * 0.12, s * 0.1))
                pygame.draw.ellipse(surf, ink, (cx - s * 0.18, cy - s * 0.2, s * 0.36, s * 0.38), 1)
                pygame.draw.rect(surf, gold_d, (cx - s * 0.19, cy - s * 0.06, s * 0.38, s * 0.07))
                pygame.draw.rect(surf, gold, (cx - s * 0.17, cy - s * 0.05, s * 0.34, s * 0.045))
                pygame.draw.rect(surf, black, (cx - s * 0.14, cy + s * 0.01, s * 0.28, s * 0.14))
                for ox in (-0.1, -0.05, 0, 0.05, 0.1):
                    pygame.draw.line(surf, gold, (cx + ox * s, cy + s * 0.02), (cx + ox * s, cy + s * 0.14), 1)
                for i, yy in enumerate((0.04, 0.08, 0.12)):
                    pygame.draw.line(surf, gold_d if i % 2 else gold, (cx - s * 0.13, cy + yy * s), (cx + s * 0.13, cy + yy * s), 1)
                # Crescent crest
                pygame.draw.polygon(surf, gold, [
                    (cx - s * 0.05, cy - s * 0.18), (cx + s * 0.05, cy - s * 0.18),
                    (cx, cy - s * 0.30),
                ])
                pygame.draw.circle(surf, black, (int(cx + s * 0.02), int(cy - s * 0.24)), max(1, int(s * 0.03)))
                return
            if "mythos" in item_id:
                # Dragon helm icon — crimson dome, horns, gold brow
                col, dark, light = (178, 28, 38), (88, 10, 16), (245, 95, 88)
                gold = (232, 188, 72)
                pygame.draw.ellipse(surf, col, (cx - s * 0.18, cy - s * 0.18, s * 0.36, s * 0.34))
                pygame.draw.ellipse(surf, light, (cx - s * 0.1, cy - s * 0.16, s * 0.12, s * 0.1))
                pygame.draw.ellipse(surf, ink, (cx - s * 0.18, cy - s * 0.18, s * 0.36, s * 0.34), 1)
                for side in (-1, 1):
                    pygame.draw.polygon(surf, col, [
                        (cx + side * s * 0.1, cy - s * 0.12),
                        (cx + side * s * 0.22, cy - s * 0.28),
                        (cx + side * s * 0.16, cy - s * 0.08),
                    ])
                    pygame.draw.circle(surf, gold, (int(cx + side * s * 0.22), int(cy - s * 0.28)), max(1, int(s * 0.04)))
                pygame.draw.rect(surf, dark, (cx - s * 0.14, cy - s * 0.02, s * 0.28, s * 0.07))
                pygame.draw.polygon(surf, col, [
                    (cx - s * 0.06, cy + s * 0.02), (cx + s * 0.06, cy + s * 0.02),
                    (cx, cy + s * 0.18),
                ])
                pygame.draw.circle(surf, gold, (int(cx), int(cy - s * 0.1)), max(1, int(s * 0.045)))
                return
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
            # Smaller, snug helm silhouette
            pygame.draw.ellipse(surf, col, (cx - s * 0.17, cy - s * 0.2, s * 0.34, s * 0.32))
            pygame.draw.ellipse(surf, light, (cx - s * 0.1, cy - s * 0.18, s * 0.12, s * 0.09))
            pygame.draw.ellipse(surf, ink, (cx - s * 0.17, cy - s * 0.2, s * 0.34, s * 0.32), 1)
            if "leather" not in item_id and "cowl" not in item_id:
                pygame.draw.rect(surf, dark, (cx - s * 0.18, cy - s * 0.02, s * 0.36, s * 0.07))
                pygame.draw.rect(surf, (25, 22, 20), (cx - s * 0.1, cy - s * 0.04, s * 0.2, s * 0.045))
                pygame.draw.rect(surf, dark, (cx - s * 0.025, cy, s * 0.05, s * 0.12))
            return
        if "legs" in item_id or "chaps" in item_id:
            if "eclipse" in item_id:
                face, dark, light = (42, 42, 50), (12, 12, 16), (90, 90, 100)
                gold, gold_d = (228, 196, 78), (160, 120, 40)
                for ox in (-0.14, 0.06):
                    pygame.draw.rect(surf, dark, (cx + ox * s - s * 0.02, cy - s * 0.12, s * 0.18, s * 0.36), border_radius=2)
                    pygame.draw.rect(surf, face, (cx + ox * s, cy - s * 0.1, s * 0.14, s * 0.32), border_radius=2)
                    pygame.draw.line(surf, gold, (cx + ox * s + 1, cy - s * 0.08), (cx + ox * s + 1, cy + s * 0.14), 1)
                    pygame.draw.circle(surf, gold_d, (int(cx + (ox + 0.07) * s), int(cy + s * 0.06)), max(2, int(s * 0.05)))
                    pygame.draw.circle(surf, gold, (int(cx + (ox + 0.07) * s), int(cy + s * 0.06)), max(2, int(s * 0.05)), 1)
                    pygame.draw.line(surf, gold, (cx + ox * s, cy + s * 0.18), (cx + (ox + 0.14) * s, cy + s * 0.18), 1)
                    pygame.draw.rect(surf, ink, (cx + ox * s - s * 0.02, cy - s * 0.12, s * 0.18, s * 0.36), 1, border_radius=2)
                return
            col = (178, 28, 38) if "mythos" in item_id else (
                (150, 155, 165) if "iron" in item_id else (
                    (120, 140, 160) if "steel" in item_id else (
                        (100, 180, 220) if "mithril" in item_id else (
                            (70, 200, 120) if "adamant" in item_id else (
                                (180, 130, 70) if "bronze" in item_id else (130, 90, 55)
                            )
                        )
                    )
                )
            )
            dark = tuple(max(0, c - 45) for c in col)
            light = tuple(min(255, c + 35) for c in col)
            if "mythos" in item_id:
                light, dark = (245, 95, 88), (88, 10, 16)
            for ox in (-0.14, 0.06):
                pygame.draw.rect(surf, dark, (cx + ox * s - s * 0.02, cy - s * 0.12, s * 0.18, s * 0.36), border_radius=2)
                pygame.draw.rect(surf, col, (cx + ox * s, cy - s * 0.1, s * 0.14, s * 0.32), border_radius=2)
                pygame.draw.rect(surf, light, (cx + ox * s + 1, cy - s * 0.08, s * 0.05, s * 0.12))
                # Knee pad
                pygame.draw.circle(surf, light, (int(cx + (ox + 0.07) * s), int(cy + s * 0.06)), max(2, int(s * 0.045)))
                pygame.draw.rect(surf, ink, (cx + ox * s - s * 0.02, cy - s * 0.12, s * 0.18, s * 0.36), 1, border_radius=2)
            return
        col = (42, 42, 50) if "eclipse" in item_id else (
            (178, 28, 38) if "mythos" in item_id else (
            (150, 155, 165) if "iron" in item_id else (
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
        )
        )
        light = tuple(min(255, c + 30) for c in col)
        dark = tuple(max(0, c - 40) for c in col)
        if "eclipse" in item_id:
            light, dark = (90, 90, 100), (12, 12, 16)
        elif "mythos" in item_id:
            light, dark = (245, 95, 88), (88, 10, 16)
        torso = [
            (cx - s * 0.18, cy - s * 0.18), (cx + s * 0.18, cy - s * 0.18),
            (cx + s * 0.26, cy - s * 0.06), (cx + s * 0.22, cy + s * 0.22),
            (cx - s * 0.22, cy + s * 0.22), (cx - s * 0.26, cy - s * 0.06),
        ]
        stroke_poly(col, torso)
        pygame.draw.polygon(surf, light, [
            (cx - s * 0.14, cy - s * 0.14), (cx - s * 0.02, cy - s * 0.14),
            (cx - s * 0.02, cy + s * 0.08), (cx - s * 0.14, cy + s * 0.08),
        ])
        # Belt line for body silhouette
        pygame.draw.line(surf, dark, (cx - s * 0.18, cy + s * 0.14), (cx + s * 0.18, cy + s * 0.14), max(1, int(s * 0.04)))
        # Plate ridges / belt
        if "eclipse" in item_id:
            gold, gold_d = (228, 196, 78), (160, 120, 40)
            for i in range(4):
                yy = cy - s * 0.08 + i * s * 0.07
                pygame.draw.line(surf, gold_d, (cx - s * 0.16, yy), (cx + s * 0.16, yy), 1)
            pygame.draw.line(surf, gold, (cx - s * 0.02, cy - s * 0.1), (cx - s * 0.02, cy + s * 0.14), 1)
            pygame.draw.line(surf, gold, (cx + s * 0.02, cy - s * 0.1), (cx + s * 0.02, cy + s * 0.14), 1)
            pygame.draw.circle(surf, gold_d, (int(cx), int(cy + s * 0.02)), max(2, int(s * 0.07)))
            pygame.draw.circle(surf, (12, 12, 16), (int(cx), int(cy + s * 0.02)), max(2, int(s * 0.05)))
            pygame.draw.circle(surf, gold, (int(cx - s * 0.015), int(cy + s * 0.01)), max(1, int(s * 0.03)), 1)
            pygame.draw.circle(surf, gold_d, (int(cx - s * 0.2), int(cy - s * 0.14)), max(2, int(s * 0.09)))
            pygame.draw.circle(surf, gold, (int(cx - s * 0.2), int(cy - s * 0.14)), max(2, int(s * 0.09)), 1)
            return
        if "chain" in item_id:
            # Ring-mail dots — clearly different from plate ridges
            for i in range(4):
                yy = cy - s * 0.08 + i * s * 0.07
                for j in range(5):
                    xx = cx - s * 0.14 + j * s * 0.07
                    pygame.draw.circle(surf, dark, (int(xx), int(yy)), max(1, int(s * 0.025)), 1)
        elif "leather" in item_id or "goblin" in item_id:
            pygame.draw.line(surf, dark, (cx - s * 0.12, cy), (cx + s * 0.12, cy), 1)
            pygame.draw.circle(surf, dark, (int(cx), int(cy)), max(1, int(s * 0.03)))
        else:
            # Platebody (bronze_body, iron_body, etc.) — horizontal ridges + center seam
            for i in range(3):
                yy = cy - s * 0.06 + i * s * 0.08
                pygame.draw.line(surf, dark, (cx - s * 0.16, yy), (cx + s * 0.16, yy), 1)
            pygame.draw.line(surf, dark, (cx, cy - s * 0.1), (cx, cy + s * 0.14), 1)
        pygame.draw.circle(surf, col, (int(cx - s * 0.2), int(cy - s * 0.14)), max(2, int(s * 0.09)))
        pygame.draw.circle(surf, light, (int(cx - s * 0.22), int(cy - s * 0.16)), max(1, int(s * 0.04)))
        pygame.draw.circle(surf, col, (int(cx + s * 0.2), int(cy - s * 0.14)), max(2, int(s * 0.09)))
        if "mythos" in item_id:
            # Gold trim + tiny dragon emblem on inventory icon
            gold, gold_l, gold_d = (232, 188, 72), (255, 230, 140), (150, 100, 32)
            pygame.draw.polygon(surf, gold, torso, max(1, int(s * 0.05)))
            pygame.draw.circle(surf, gold_d, (int(cx), int(cy + s * 0.02)), max(2, int(s * 0.08)))
            pygame.draw.circle(surf, gold, (int(cx), int(cy + s * 0.02)), max(2, int(s * 0.065)))
            # Mini head silhouette
            pygame.draw.polygon(surf, gold_l, [
                (cx - s * 0.04, cy + s * 0.01),
                (cx - s * 0.02, cy - s * 0.05),
                (cx + s * 0.06, cy - s * 0.01),
                (cx + s * 0.05, cy + s * 0.03),
                (cx, cy + s * 0.05),
            ])
            pygame.draw.circle(surf, (255, 60, 40), (int(cx + s * 0.01), int(cy - s * 0.01)), max(1, int(s * 0.015)))
            # Winged pauldrons accents
            pygame.draw.polygon(surf, gold, [
                (cx - s * 0.2, cy - s * 0.14), (cx - s * 0.32, cy - s * 0.22),
                (cx - s * 0.28, cy - s * 0.08),
            ])
            pygame.draw.polygon(surf, gold, [
                (cx + s * 0.2, cy - s * 0.14), (cx + s * 0.32, cy - s * 0.22),
                (cx + s * 0.28, cy - s * 0.08),
            ])
        return
    if item_id.endswith("_logs") or item_id in ("logs", "oak_logs"):
        colors = {
            "logs": ((140, 95, 55), (200, 170, 130)),
            "oak_logs": ((90, 60, 35), (160, 130, 90)),
            "willow_logs": ((150, 125, 60), (210, 190, 130)),
            "maple_logs": ((150, 75, 40), (200, 130, 80)),
            "yew_logs": ((70, 48, 28), (120, 90, 55)),
            "magic_logs": ((80, 60, 120), (140, 120, 200)),
        }
        color, end = colors.get(item_id, ((140, 95, 55), (200, 170, 130)))
        for i, oy in enumerate((-0.12, 0.0, 0.12)):
            x0 = cx - s * 0.22 + i * s * 0.02
            y0 = cy + oy * s
            pygame.draw.ellipse(surf, color, (x0, y0 - s * 0.08, s * 0.44, s * 0.16))
            # Bark rings
            pygame.draw.ellipse(surf, end, (x0 + s * 0.34, y0 - s * 0.06, s * 0.10, s * 0.12))
            pygame.draw.ellipse(surf, color, (x0 + s * 0.36, y0 - s * 0.04, s * 0.06, s * 0.08))
            pygame.draw.ellipse(surf, ink, (x0, y0 - s * 0.08, s * 0.44, s * 0.16), 1)
            if "magic" in item_id:
                pygame.draw.circle(surf, (180, 140, 255), (int(x0 + s * 0.2), int(y0)), max(1, int(s * 0.03)))
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
    if item_id == "coal" or "ore" in item_id:
        # Faceted rock lump with large mineral crystals (readable at 32–40px)
        if item_id == "coal":
            rock, fleck, fleck2 = (38, 38, 42), (95, 95, 100), (18, 18, 20)
        else:
            veins = {
                "copper_ore": ((210, 115, 50), (255, 190, 100)),
                "tin_ore": ((175, 178, 190), (230, 232, 240)),
                "iron_ore": ((150, 85, 60), (200, 140, 100)),
                "mithril_ore": ((70, 155, 210), (150, 220, 255)),
                "adamantite_ore": ((45, 170, 95), (130, 240, 160)),
            }
            fleck, fleck2 = veins.get(item_id, ((150, 150, 150), (200, 200, 200)))
            rock = (95, 88, 80)
        stroke_poly(rock, [
            (cx - s * 0.24, cy + s * 0.14), (cx - s * 0.18, cy - s * 0.16),
            (cx + s * 0.04, cy - s * 0.28), (cx + s * 0.24, cy - s * 0.08),
            (cx + s * 0.22, cy + s * 0.18), (cx, cy + s * 0.28),
        ])
        pygame.draw.polygon(surf, tuple(min(255, c + 28) for c in rock), [
            (cx - s * 0.14, cy - s * 0.12), (cx + s * 0.06, cy - s * 0.20),
            (cx + s * 0.04, cy + s * 0.04), (cx - s * 0.12, cy + s * 0.06),
        ])
        # Big ore crystals — primary identifier
        crystals = (
            (-0.06, -0.04, 0.11), (0.08, -0.10, 0.09), (0.00, 0.10, 0.10),
            (-0.12, 0.08, 0.07), (0.12, 0.06, 0.07),
        )
        for ox, oy, sc in crystals:
            pygame.draw.polygon(surf, fleck, [
                (cx + ox * s, cy + (oy - sc) * s),
                (cx + (ox + sc * 0.85) * s, cy + oy * s),
                (cx + ox * s, cy + (oy + sc * 0.7) * s),
                (cx + (ox - sc * 0.85) * s, cy + oy * s),
            ])
            pygame.draw.polygon(surf, fleck2, [
                (cx + ox * s, cy + (oy - sc * 0.55) * s),
                (cx + (ox + sc * 0.35) * s, cy + oy * s),
                (cx + ox * s, cy + (oy + sc * 0.25) * s),
            ])
        if item_id == "coal":
            # Extra dark facets so coal reads as charcoal, not rock+dots
            for ox, oy in ((-0.02, -0.08), (0.10, 0.02), (-0.10, 0.06)):
                pygame.draw.circle(surf, fleck2, (int(cx + ox * s), int(cy + oy * s)), max(2, int(s * 0.045)))
        return

    if (
        "shrimp" in item_id or "sardine" in item_id or "trout" in item_id
        or "salmon" in item_id or "tuna" in item_id or "swordfish" in item_id
        or "lobster" in item_id or "fish" in item_id
    ):
        cooked = "cooked" in item_id
        burnt = "burnt" in item_id
        raw = not cooked and not burnt

        def fish_cols(raw_c, cook_c):
            if burnt:
                return (55, 45, 40), (35, 30, 28)
            if cooked:
                return cook_c, tuple(min(255, c + 40) for c in cook_c)
            return raw_c, tuple(min(255, c + 35) for c in raw_c)

        if "lobster" in item_id:
            body, hi = fish_cols((200, 70, 55), (230, 95, 45))
            pygame.draw.ellipse(surf, body, (cx - s * 0.08, cy - s * 0.12, s * 0.34, s * 0.26))
            for i in range(4):
                pygame.draw.ellipse(surf, body, (cx - s * 0.24 + i * s * 0.055, cy - s * 0.05, s * 0.12, s * 0.14))
                pygame.draw.line(surf, hi, (cx - s * 0.18 + i * s * 0.055, cy - s * 0.02), (cx - s * 0.18 + i * s * 0.055, cy + s * 0.06), 1)
            for side in (-1, 1):
                pygame.draw.line(surf, body, (cx - s * 0.06, cy), (cx - s * 0.30, cy + side * s * 0.16), max(3, int(s * 0.06)))
                pygame.draw.polygon(surf, hi, [
                    (cx - s * 0.30, cy + side * s * 0.16),
                    (cx - s * 0.38, cy + side * s * 0.10),
                    (cx - s * 0.36, cy + side * s * 0.22),
                ])
            pygame.draw.line(surf, body, (cx + s * 0.20, cy - s * 0.04), (cx + s * 0.32, cy - s * 0.20), 1)
            pygame.draw.line(surf, body, (cx + s * 0.20, cy + s * 0.04), (cx + s * 0.32, cy + s * 0.18), 1)
            pygame.draw.circle(surf, ink, (int(cx + s * 0.18), int(cy)), max(1, int(s * 0.035)))
            return

        if "shrimp" in item_id:
            body, hi = fish_cols((220, 160, 130), (235, 145, 85))
            for i, (ox, oy) in enumerate(((-0.10, 0.06), (0.0, -0.06), (0.10, 0.08))):
                pygame.draw.ellipse(surf, body, (cx + ox * s - s * 0.09, cy + oy * s - s * 0.05, s * 0.18, s * 0.11))
                # Legs
                for j in range(3):
                    pygame.draw.line(
                        surf, hi,
                        (cx + (ox - 0.02) * s, cy + (oy + 0.02) * s),
                        (cx + (ox - 0.10) * s, cy + (oy + 0.08 + j * 0.03) * s),
                        1,
                    )
                pygame.draw.line(surf, hi, (cx + (ox + 0.06) * s, cy + oy * s), (cx + (ox + 0.14) * s, cy + (oy - 0.08) * s), 1)
            return

        if "swordfish" in item_id:
            body, hi = fish_cols((70, 110, 150), (130, 105, 70))
            pygame.draw.ellipse(surf, body, (cx - s * 0.18, cy - s * 0.10, s * 0.36, s * 0.20))
            pygame.draw.polygon(surf, body, [
                (cx - s * 0.16, cy), (cx - s * 0.30, cy - s * 0.10), (cx - s * 0.30, cy + s * 0.10),
            ])
            # Bill pointing right
            pygame.draw.polygon(surf, hi, [
                (cx + s * 0.16, cy), (cx + s * 0.40, cy - s * 0.025), (cx + s * 0.16, cy + s * 0.025),
            ])
            pygame.draw.polygon(surf, hi, [
                (cx - s * 0.02, cy - s * 0.10), (cx + s * 0.12, cy - s * 0.24), (cx + s * 0.14, cy - s * 0.08),
            ])
            pygame.draw.polygon(surf, body, [
                (cx - s * 0.04, cy + s * 0.08), (cx + s * 0.06, cy + s * 0.18), (cx + s * 0.08, cy + s * 0.06),
            ])
            pygame.draw.circle(surf, ink, (int(cx + s * 0.08), int(cy - s * 0.02)), max(1, int(s * 0.03)))
            pygame.draw.line(surf, hi, (cx - s * 0.08, cy), (cx + s * 0.08, cy), 1)
            return

        if "tuna" in item_id:
            body, hi = fish_cols((55, 95, 140), (120, 100, 65))
            pygame.draw.ellipse(surf, body, (cx - s * 0.20, cy - s * 0.12, s * 0.40, s * 0.24))
            pygame.draw.polygon(surf, body, [
                (cx - s * 0.18, cy), (cx - s * 0.32, cy - s * 0.12), (cx - s * 0.32, cy + s * 0.12),
            ])
            pygame.draw.polygon(surf, hi, [
                (cx, cy - s * 0.12), (cx + s * 0.10, cy - s * 0.22), (cx + s * 0.08, cy - s * 0.08),
            ])
            pygame.draw.circle(surf, ink, (int(cx + s * 0.10), int(cy - s * 0.02)), max(1, int(s * 0.03)))
            for ox in (-0.06, 0.02, 0.10):
                pygame.draw.arc(surf, hi, (cx + ox * s - s * 0.04, cy - s * 0.04, s * 0.08, s * 0.08), 3.5, 5.5, 1)
            return

        if "salmon" in item_id:
            body, hi = fish_cols((200, 110, 95), (230, 135, 75))
            pygame.draw.ellipse(surf, body, (cx - s * 0.20, cy - s * 0.10, s * 0.38, s * 0.20))
            pygame.draw.polygon(surf, body, [
                (cx - s * 0.18, cy), (cx - s * 0.30, cy - s * 0.10), (cx - s * 0.30, cy + s * 0.10),
            ])
            pygame.draw.polygon(surf, hi, [
                (cx - s * 0.02, cy - s * 0.10), (cx + s * 0.08, cy - s * 0.20), (cx + s * 0.06, cy - s * 0.08),
            ])
            for ox, oy in ((-0.06, -0.02), (0.02, 0.04), (0.08, -0.04), (0.0, -0.04)):
                pygame.draw.circle(surf, hi, (int(cx + ox * s), int(cy + oy * s)), max(1, int(s * 0.028)))
            pygame.draw.circle(surf, ink, (int(cx + s * 0.10), int(cy - s * 0.02)), max(1, int(s * 0.028)))
            return

        if "trout" in item_id:
            body, hi = fish_cols((90, 145, 100), (210, 145, 75))
            pygame.draw.ellipse(surf, body, (cx - s * 0.18, cy - s * 0.10, s * 0.36, s * 0.20))
            pygame.draw.polygon(surf, body, [
                (cx - s * 0.16, cy), (cx - s * 0.28, cy - s * 0.09), (cx - s * 0.28, cy + s * 0.09),
            ])
            pygame.draw.polygon(surf, hi, [
                (cx, cy - s * 0.10), (cx + s * 0.08, cy - s * 0.20), (cx + s * 0.06, cy - s * 0.08),
            ])
            spot = (40, 60, 40) if raw else (120, 80, 40)
            for ox in (-0.04, 0.04, 0.10):
                pygame.draw.circle(surf, spot, (int(cx + ox * s), int(cy)), max(1, int(s * 0.025)))
            pygame.draw.circle(surf, ink, (int(cx + s * 0.08), int(cy - s * 0.02)), max(1, int(s * 0.028)))
            return

        if "sardine" in item_id:
            body, hi = fish_cols((140, 165, 195), (210, 150, 90))
            pygame.draw.ellipse(surf, body, (cx - s * 0.22, cy - s * 0.07, s * 0.40, s * 0.14))
            pygame.draw.polygon(surf, body, [
                (cx - s * 0.20, cy), (cx - s * 0.32, cy - s * 0.07), (cx - s * 0.32, cy + s * 0.07),
            ])
            pygame.draw.line(surf, hi, (cx - s * 0.14, cy), (cx + s * 0.12, cy), 1)
            pygame.draw.polygon(surf, hi, [
                (cx + s * 0.02, cy - s * 0.07), (cx + s * 0.10, cy - s * 0.14), (cx + s * 0.08, cy - s * 0.05),
            ])
            pygame.draw.circle(surf, ink, (int(cx + s * 0.08), int(cy - s * 0.01)), max(1, int(s * 0.022)))
            return

        body, hi = fish_cols((150, 170, 210), (210, 140, 90))
        pygame.draw.ellipse(surf, body, (cx - s * 0.20, cy - s * 0.11, s * 0.38, s * 0.22))
        pygame.draw.polygon(surf, body, [
            (cx - s * 0.18, cy), (cx - s * 0.30, cy - s * 0.10), (cx - s * 0.30, cy + s * 0.10),
        ])
        pygame.draw.circle(surf, ink, (int(cx + s * 0.08), int(cy - s * 0.02)), max(1, int(s * 0.03)))
        if cooked:
            pygame.draw.line(surf, hi, (cx - s * 0.08, cy + s * 0.02), (cx + s * 0.10, cy + s * 0.02), 1)
        return

    if item_id == "bread":
        crust, crumb = (190, 130, 70), (230, 200, 140)
        pygame.draw.ellipse(surf, crust, (cx - s * 0.24, cy - s * 0.14, s * 0.48, s * 0.30))
        pygame.draw.ellipse(surf, crumb, (cx - s * 0.16, cy - s * 0.08, s * 0.32, s * 0.18))
        for ox in (-0.08, 0.0, 0.08):
            pygame.draw.arc(surf, (140, 90, 40), (cx + ox * s - s * 0.06, cy - s * 0.12, s * 0.12, s * 0.14), 0.4, 2.7, 1)
        pygame.draw.ellipse(surf, ink, (cx - s * 0.24, cy - s * 0.14, s * 0.48, s * 0.30), 1)
        return

    if item_id == "health_potion" or itype == "potion" or item.get("boost_skill"):
        skill = item.get("boost_skill", "") if item_id != "health_potion" else "hitpoints"
        super_ = "super" in item_id
        if item_id == "health_potion" or skill == "hitpoints":
            liquid = (220, 55, 70)
            mark = (255, 180, 180)
            letter = "H"
        elif skill == "attack":
            liquid = (50, 110, 255) if not super_ else (30, 70, 255)
            mark, letter = (180, 200, 255), "A"
        elif skill == "strength":
            liquid = (220, 80, 50) if not super_ else (255, 45, 25)
            mark, letter = (255, 200, 160), "S"
        elif skill == "defence":
            liquid = (60, 190, 100) if not super_ else (25, 170, 70)
            mark, letter = (180, 255, 200), "D"
        else:
            liquid, mark, letter = (180, 100, 220), (230, 200, 255), "?"
        glass = (200, 220, 235)
        pygame.draw.rect(surf, (120, 80, 40), (cx - s * 0.07, cy - s * 0.32, s * 0.14, s * 0.06), border_radius=1)
        pygame.draw.rect(surf, glass, (cx - s * 0.08, cy - s * 0.26, s * 0.16, s * 0.10))
        body = [
            (cx - s * 0.15, cy - s * 0.16), (cx + s * 0.15, cy - s * 0.16),
            (cx + s * 0.19, cy + s * 0.24), (cx - s * 0.19, cy + s * 0.24),
        ]
        stroke_poly(liquid, body)
        hi = tuple(min(255, c + 55) for c in liquid)
        pygame.draw.polygon(surf, hi, [
            (cx - s * 0.11, cy - s * 0.12), (cx - s * 0.02, cy - s * 0.12),
            (cx - s * 0.02, cy + s * 0.12), (cx - s * 0.13, cy + s * 0.12),
        ])
        pygame.draw.rect(surf, (240, 230, 210), (cx - s * 0.12, cy + s * 0.02, s * 0.24, s * 0.10), border_radius=2)
        pygame.draw.rect(surf, mark, (cx - s * 0.12, cy + s * 0.02, s * 0.24, s * 0.10), 1, border_radius=2)
        ink_l = (50, 35, 25)
        if letter == "H":
            pygame.draw.line(surf, ink_l, (cx - s * 0.05, cy + s * 0.04), (cx - s * 0.05, cy + s * 0.10), 2)
            pygame.draw.line(surf, ink_l, (cx + s * 0.05, cy + s * 0.04), (cx + s * 0.05, cy + s * 0.10), 2)
            pygame.draw.line(surf, ink_l, (cx - s * 0.05, cy + s * 0.07), (cx + s * 0.05, cy + s * 0.07), 2)
        elif letter == "A":
            pygame.draw.lines(surf, ink_l, False, [
                (cx - s * 0.05, cy + s * 0.10), (cx, cy + s * 0.03), (cx + s * 0.05, cy + s * 0.10),
            ], 2)
            pygame.draw.line(surf, ink_l, (cx - s * 0.03, cy + s * 0.07), (cx + s * 0.03, cy + s * 0.07), 2)
        elif letter == "S":
            # Clear S from three strokes (arcs are unreadable at tiny size)
            pygame.draw.line(surf, ink_l, (cx + s * 0.05, cy + s * 0.04), (cx - s * 0.04, cy + s * 0.04), 2)
            pygame.draw.line(surf, ink_l, (cx - s * 0.04, cy + s * 0.04), (cx + s * 0.04, cy + s * 0.07), 2)
            pygame.draw.line(surf, ink_l, (cx + s * 0.04, cy + s * 0.07), (cx - s * 0.05, cy + s * 0.10), 2)
        elif letter == "D":
            pygame.draw.line(surf, ink_l, (cx - s * 0.04, cy + s * 0.04), (cx - s * 0.04, cy + s * 0.10), 2)
            pygame.draw.arc(surf, ink_l, (cx - s * 0.04, cy + s * 0.04, s * 0.10, s * 0.06), 4.8, 1.5, 2)
        if super_:
            pygame.draw.circle(surf, (255, 230, 80), (int(cx + s * 0.10), int(cy - s * 0.06)), max(2, int(s * 0.045)))
            pygame.draw.circle(surf, (255, 255, 200), (int(cx + s * 0.10), int(cy - s * 0.06)), max(1, int(s * 0.02)))
        return

    if item_id == "gold_ring":
        # Handled by generic jewelry ring path above when type/slot set;
        # keep legacy fallback for old defs.
        pygame.draw.circle(surf, (230, 190, 60), (cx, cy), int(s * 0.20), max(2, int(s * 0.07)))
        pygame.draw.circle(surf, (255, 230, 120), (cx - int(s * 0.06), cy - int(s * 0.06)), max(1, int(s * 0.04)))
        pygame.draw.circle(surf, ink, (cx, cy), int(s * 0.20), 1)
        return

    if item_id == "lost_locket":
        # Heart locket on a thin chain
        chain = (180, 160, 90)
        for i in range(4):
            pygame.draw.circle(surf, chain, (cx - int(s * 0.08) + i * int(s * 0.05), cy - int(s * 0.22) + i), max(1, int(s * 0.03)), 1)
        heart = (200, 60, 70)
        pygame.draw.circle(surf, heart, (cx - int(s * 0.06), cy - int(s * 0.02)), max(3, int(s * 0.09)))
        pygame.draw.circle(surf, heart, (cx + int(s * 0.06), cy - int(s * 0.02)), max(3, int(s * 0.09)))
        pygame.draw.polygon(surf, heart, [
            (cx - int(s * 0.14), cy), (cx + int(s * 0.14), cy), (cx, cy + int(s * 0.18)),
        ])
        pygame.draw.circle(surf, (255, 200, 120), (cx, cy + int(s * 0.02)), max(1, int(s * 0.04)))
        return

    if item_id == "rat_tail":
        # Pinkish tapering tail with tuft
        skin, tip = (200, 140, 150), (160, 100, 110)
        pts = [
            (cx - s * 0.22, cy + s * 0.10), (cx - s * 0.08, cy - s * 0.06),
            (cx + s * 0.18, cy - s * 0.16), (cx + s * 0.22, cy - s * 0.08),
            (cx + s * 0.04, cy + s * 0.04), (cx - s * 0.14, cy + s * 0.16),
        ]
        stroke_poly(skin, pts)
        pygame.draw.polygon(surf, tip, [
            (cx + s * 0.14, cy - s * 0.14), (cx + s * 0.26, cy - s * 0.20),
            (cx + s * 0.20, cy - s * 0.06),
        ])
        return

    if item_id == "spider_silk":
        # White silk bundle with web threads
        silk, silk_d = (240, 240, 245), (180, 185, 195)
        pygame.draw.ellipse(surf, silk_d, (cx - s * 0.18, cy - s * 0.10, s * 0.36, s * 0.24))
        pygame.draw.ellipse(surf, silk, (cx - s * 0.14, cy - s * 0.08, s * 0.28, s * 0.16))
        for ang in (0.3, 1.2, 2.1, 3.0, 4.0, 5.0):
            pygame.draw.line(
                surf, silk_d,
                (cx, cy),
                (cx + int(math.cos(ang) * s * 0.22), cy + int(math.sin(ang) * s * 0.18)),
                1,
            )
        pygame.draw.circle(surf, (255, 255, 255), (cx - int(s * 0.04), cy - int(s * 0.04)), max(1, int(s * 0.04)))
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
        # Femur shape
        pygame.draw.line(surf, color, (cx - s_bone * 0.18, cy + s_bone * 0.04), (cx + s_bone * 0.18, cy - s_bone * 0.04), max(3, int(s_bone * 0.08)))
        pygame.draw.circle(surf, color, (int(cx - s_bone * 0.20), int(cy + s_bone * 0.02)), max(3, int(s_bone * 0.09)))
        pygame.draw.circle(surf, color, (int(cx - s_bone * 0.14), int(cy + s_bone * 0.08)), max(2, int(s_bone * 0.06)))
        pygame.draw.circle(surf, color, (int(cx + s_bone * 0.20), int(cy - s_bone * 0.02)), max(3, int(s_bone * 0.09)))
        pygame.draw.circle(surf, color, (int(cx + s_bone * 0.14), int(cy - s_bone * 0.08)), max(2, int(s_bone * 0.06)))
        if item_id == "dragon_bones":
            pygame.draw.line(surf, (160, 100, 70), (cx - s_bone * 0.06, cy - s_bone * 0.12), (cx + s_bone * 0.06, cy + s_bone * 0.12), max(2, int(s_bone * 0.05)))
        return

    if "bar" in item_id:
        # Classic RS-style metal ingot — thick brick with bevel + stamped face
        mid, dark, light, _ = rs.metal_palette(item_id)
        # Shadow under
        pygame.draw.ellipse(surf, (20, 18, 16), (cx - s * 0.20, cy + s * 0.14, s * 0.40, s * 0.10))
        # Top face (lit)
        top = [
            (cx - s * 0.20, cy - s * 0.08), (cx + s * 0.12, cy - s * 0.16),
            (cx + s * 0.24, cy - s * 0.02), (cx - s * 0.08, cy + s * 0.06),
        ]
        # Front face
        face = [
            (cx - s * 0.08, cy + s * 0.06), (cx + s * 0.24, cy - s * 0.02),
            (cx + s * 0.20, cy + s * 0.16), (cx - s * 0.12, cy + s * 0.22),
        ]
        # Right side
        side = [
            (cx + s * 0.24, cy - s * 0.02), (cx + s * 0.12, cy - s * 0.16),
            (cx + s * 0.08, cy - s * 0.02), (cx + s * 0.20, cy + s * 0.16),
        ]
        pygame.draw.polygon(surf, light, top)
        pygame.draw.polygon(surf, mid, face)
        pygame.draw.polygon(surf, dark, side)
        pygame.draw.polygon(surf, ink, top, 1)
        pygame.draw.polygon(surf, ink, face, 1)
        # Bevel ridge + stamp
        pygame.draw.line(surf, dark, (cx - s * 0.04, cy + s * 0.08), (cx + s * 0.14, cy + s * 0.02), 1)
        pygame.draw.line(surf, light, (cx - s * 0.14, cy - s * 0.04), (cx + s * 0.06, cy - s * 0.12), 1)
        pygame.draw.rect(surf, dark, (cx - s * 0.02, cy + s * 0.08, s * 0.10, s * 0.06), border_radius=1)
        return

    # default: small gem (unknown misc)
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
    kind = variant % 6  # 0 normal, 1 oak, 2 willow, 3 maple, 4 yew, 5 magic
    oak = kind == 1
    willow = kind == 2
    maple = kind == 3
    yew = kind == 4
    magic = kind == 5
    pine = False  # legacy unused
    if oak:
        s *= 1.12
    elif willow:
        s *= 1.05
    elif maple:
        s *= 1.18
    elif yew:
        s *= 1.28
    elif magic:
        s *= 1.35
    seed = variant * 17 + int(cx) * 3 + int(cy)
    trunk = (96, 68, 38)
    foliage = (36, 98, 40)
    if oak:
        trunk, foliage = (78, 52, 28), (28, 78, 32)
    elif willow:
        trunk, foliage = (110, 95, 55), (70, 120, 55)
    elif maple:
        trunk, foliage = (88, 58, 32), (160, 70, 35)
    elif yew:
        trunk, foliage = (60, 42, 28), (20, 55, 28)
    elif magic:
        trunk, foliage = (70, 55, 90), (80, 140, 200)
    feet = cy + 12 * s
    sway = math.sin(t * 0.85 + variant) * 0.55 * s
    lean = (_seeded(seed, 0, 1) - 0.5) * 2.4 * s

    # Irregular ground shadow
    canopy_w = 22 if (maple or yew or magic) else (20 if oak else (18 if willow else 15))
    rs.draw_cast_shadow(
        surf, cx + 5 * s, feet + 1.5 * s,
        canopy_w * s, 5 * s, 130,
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
    tw_base = 3.4 if oak or maple else (2.8 if yew or magic else (2.0 if willow else 2.6))
    tw_top = tw_base * 0.45
    top_y = cy - (18 if yew or magic else (16 if maple else (17 if willow else (14 if oak else 15)))) * s
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

    # Recessed windows on the wall (before roof so eaves can overhang them)
    for wx in (x + w * 0.14, x + w * 0.58):
        wy, ww, wh = wall_top + wall_h * 0.32, w * 0.15, wall_h * 0.26
        if abs((wx + ww * 0.5) - (x + w * 0.5)) < w * 0.14:
            continue
        pygame.draw.rect(surf, deep, (wx - 2, wy - 2, ww + 4, wh + 4))
        pygame.draw.rect(surf, (40, 70, 95), (wx, wy, ww, wh))
        pygame.draw.rect(surf, (70, 110, 140), (wx + 1, wy + 1, ww * 0.4, wh * 0.35))
        pygame.draw.line(surf, trim, (wx + ww * 0.5, wy), (wx + ww * 0.5, wy + wh), 1)
        pygame.draw.line(surf, trim, (wx, wy + wh * 0.5), (wx + ww, wy + wh * 0.5), 1)
        pygame.draw.rect(surf, trim, (wx - 2, wy - 2, ww + 4, wh + 4), 1)

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
        return (110, 110, 122), (48, 48, 55), (16, 16, 20), (232, 188, 72)
    if "mythos" in item_id:
        return (245, 95, 88), (178, 28, 38), (88, 10, 16), (232, 188, 72)
    if "adamant" in item_id:
        return (140, 230, 160), (70, 180, 110), (40, 110, 70), (230, 200, 55)
    if "mithril" in item_id:
        return (160, 210, 240), (100, 160, 200), (55, 100, 140), (230, 200, 55)
    if "iron" in item_id:
        return (188, 192, 198), (148, 152, 160), (98, 102, 110), (230, 200, 55)
    if "steel" in item_id:
        return (170, 185, 200), (120, 140, 160), (70, 88, 105), (230, 200, 55)
    if "bronze" in item_id or "copper" in item_id:
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
    if item_id and "eclipse" in item_id:
        gold, gold_d, gold_l = (228, 196, 78), (160, 120, 40), (255, 230, 140)
        black = (12, 12, 16)
        _poly(surf, mid, pts, dark, 1)
        _poly(surf, light, [
            (cx - 4.5 * s, cy - 3.8 * s), (cx + 1.5 * s, cy - 3.8 * s),
            (cx + 2.2 * s, cy + 0.5 * s), (cx - 4.2 * s, cy + 1.2 * s),
        ])
        pygame.draw.polygon(surf, gold_d, pts, max(2, int(1.8 * s)))
        pygame.draw.polygon(surf, gold, pts, max(1, int(1.0 * s)))
        for ox, oy in ((-5.5, -4.2), (5.5, -4.2), (6.0, 1.5), (0, 8.5), (-6.0, 1.5)):
            pygame.draw.circle(surf, gold_d, (cx + int(ox * s), cy + int(oy * s)), max(1, int(0.85 * s)))
            pygame.draw.circle(surf, gold_l, (cx + int(ox * s) - 1, cy + int(oy * s) - 1), max(1, int(0.35 * s)))
        pygame.draw.circle(surf, gold_d, (cx, cy + int(0.5 * s)), max(3, int(2.8 * s)))
        pygame.draw.circle(surf, gold, (cx, cy + int(0.5 * s)), max(3, int(2.8 * s)), max(1, int(0.7 * s)))
        pygame.draw.circle(surf, black, (cx, cy + int(0.5 * s)), max(2, int(2.1 * s)))
        pygame.draw.circle(surf, gold, (cx - int(0.6 * s), cy + int(0.2 * s)), max(2, int(1.3 * s)), max(1, int(0.55 * s)))
        # Dragon crest
        pygame.draw.polygon(surf, gold, [
            (cx - int(1.4 * s), cy + int(0.4 * s)), (cx - int(0.6 * s), cy - int(1.6 * s)),
            (cx + int(1.6 * s), cy - int(0.2 * s)), (cx + int(0.4 * s), cy + int(1.4 * s)),
        ])
        pygame.draw.circle(surf, (255, 70, 45), (cx + int(0.2 * s), cy - int(0.3 * s)), max(1, int(0.4 * s)))
        return
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
    """Classic battleaxe — slim haft, crescent bit + rear fluke."""
    light, mid, dark, gold = _metal_palette(item_id) or ((180, 180, 185), (140, 140, 150), (90, 90, 100), (230, 200, 55))
    eclipse = bool(item_id and "eclipse" in item_id)
    if eclipse:
        light, mid, dark = (95, 95, 105), (42, 42, 50), (12, 12, 16)
        gold = (232, 188, 72)
    reach = 1.0 + 0.12 * math.sin(max(0.0, min(1.0, swing)) * math.pi)
    tip_x = hx + facing * 2 * s
    tip_y = hy - 15 * s * reach
    shaft = (28, 28, 34) if eclipse else (95, 65, 40)
    pygame.draw.line(surf, shaft, (hx, hy + 2 * s), (tip_x, tip_y + 1 * s), max(2, int(2.2 * s)))
    # Top spike
    _poly(surf, dark, [
        (tip_x - facing * 0.8 * s, tip_y + 1 * s),
        (tip_x + facing * 0.8 * s, tip_y + 1 * s),
        (tip_x, tip_y - 3.5 * s),
    ], dark, 1)
    if eclipse:
        _poly(surf, gold, [
            (tip_x - facing * 0.35 * s, tip_y),
            (tip_x + facing * 0.35 * s, tip_y),
            (tip_x, tip_y - 2.6 * s),
        ], None, 0)
    # Crescent bit
    _poly(surf, mid, [
        (tip_x + facing * 0.6 * s, tip_y + 0.5 * s),
        (tip_x + facing * 8.5 * s, tip_y - 3.2 * s),
        (tip_x + facing * 9.5 * s, tip_y + 0.5 * s),
        (tip_x + facing * 7.5 * s, tip_y + 4.2 * s),
        (tip_x + facing * 2.5 * s, tip_y + 3.0 * s),
        (tip_x + facing * 0.8 * s, tip_y + 1.8 * s),
    ], dark, 1)
    _poly(surf, light, [
        (tip_x + facing * 1.2 * s, tip_y + 0.2 * s),
        (tip_x + facing * 7.2 * s, tip_y - 2.4 * s),
        (tip_x + facing * 8.0 * s, tip_y + 0.4 * s),
        (tip_x + facing * 5.0 * s, tip_y + 1.8 * s),
    ], None, 0)
    # Rear fluke
    _poly(surf, mid, [
        (tip_x - facing * 0.4 * s, tip_y + 0.6 * s),
        (tip_x - facing * 4.5 * s, tip_y - 1.5 * s),
        (tip_x - facing * 5.0 * s, tip_y + 1.0 * s),
        (tip_x - facing * 2.5 * s, tip_y + 2.2 * s),
    ], dark, 1)
    pygame.draw.circle(surf, gold, (tip_x, tip_y + 1.5 * s), max(1, int(1.4 * s)))
    if eclipse:
        # Gold rim + tiny dragon disc
        pygame.draw.circle(surf, gold, (tip_x + facing * 3.5 * s, tip_y + 0.8 * s), max(2, int(1.6 * s)), max(1, int(0.6 * s)))
        pygame.draw.circle(surf, (20, 20, 24), (tip_x + facing * 3.5 * s, tip_y + 0.8 * s), max(1, int(1.1 * s)))
        pygame.draw.polygon(surf, gold, [
            (tip_x + facing * 3.0 * s, tip_y + 0.8 * s),
            (tip_x + facing * 3.4 * s, tip_y - 0.2 * s),
            (tip_x + facing * 4.3 * s, tip_y + 0.7 * s),
            (tip_x + facing * 3.5 * s, tip_y + 1.3 * s),
        ])


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

    if item_id and "eclipse" in item_id:
        gold, gold_d = (228, 196, 78), (160, 120, 40)
        black = (12, 12, 16)
        _poly(surf, mid, [
            (head[0] - hr * 1.0, head[1] + hr * 0.2),
            (head[0] - hr * 0.55, head[1] - hr * 1.05),
            (head[0] + hr * 0.55, head[1] - hr * 1.1),
            (head[0] + hr * 1.05, head[1] + hr * 0.15),
            (head[0] + hr * 0.9, head[1] + hr * 0.95),
            (head[0] - hr * 0.9, head[1] + hr * 0.95),
        ], dark, 1)
        pygame.draw.rect(surf, gold_d, (head[0] - hr * 0.95, head[1] - hr * 0.25, hr * 1.9, hr * 0.35))
        pygame.draw.rect(surf, gold, (head[0] - hr * 0.85, head[1] - hr * 0.18, hr * 1.7, hr * 0.2))
        pygame.draw.rect(surf, black, (head[0] - hr * 0.75, head[1] + hr * 0.05, hr * 1.5, hr * 0.75))
        for i in (-0.5, -0.25, 0, 0.25, 0.5):
            pygame.draw.line(surf, gold,
                             (head[0] + i * hr, head[1] + hr * 0.08),
                             (head[0] + i * hr, head[1] + hr * 0.75), max(1, int(1.2 * s)))
        for yy in (0.2, 0.4, 0.6):
            pygame.draw.line(surf, gold_d,
                             (head[0] - hr * 0.7, head[1] + yy * hr),
                             (head[0] + hr * 0.7, head[1] + yy * hr), 1)
        _poly(surf, gold, [
            (head[0] - hr * 0.2, head[1] - hr * 0.95),
            (head[0] + hr * 0.2, head[1] - hr * 0.95),
            (head[0], head[1] - hr * 1.55),
        ], gold_d, 1)
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
                           robe=False, facing=1, equipment=None, attacking=0.0,
                           action=None, gender="male"):
    """Chunky skeletal adventurer (RS-era silhouette)."""
    from rs_humanoid import draw_skeletal_humanoid
    draw_skeletal_humanoid(
        surf, cx, cy, tile,
        body_color=body_color, skin_color=skin_color, hair_color=hair_color,
        weapon=weapon, shield=shield, moving=moving, t=t,
        robe=robe, facing=facing, equipment=equipment, attacking=attacking,
        action=action, gender=gender,
    )



def draw_orc(surf, cx, cy, tile, t, hurt=False, attacking=0.0, facing=1):
    """Broad-shouldered brute — thick limbs, heavy jaw, cleaver."""
    facing = 1 if facing >= 0 else -1
    s = _s(tile, 'monster') * 1.18
    bob = math.sin(t * 4.5) * 0.6
    skin = (175, 55, 45) if hurt else (64, 98, 54)
    hi, mid, sh, deep = rs.material(skin)
    cloth = (70, 55, 40)
    cy += bob
    lunge_w, crouch, strike = rs.attack_impulse(attacking)
    lunge = lunge_w * 7 * s * facing
    cy += crouch * 1.4 * s
    rs.draw_cast_shadow(surf, cx, cy + 14 * s, 13 * s, 3.8 * s, 120)
    rs.draw_volume_limb(surf, cx - 3.5 * s * facing, cy + 2 * s, cx - 6.5 * s * facing - lunge_w * 1.5 * s * facing, cy + 14 * s, 2.0 * s, cloth, deep)
    rs.draw_volume_limb(surf, cx + 3.5 * s * facing, cy + 2 * s, cx + 6.5 * s * facing + lunge_w * 2.5 * s * facing, cy + 14 * s, 2.0 * s, cloth, deep)
    # Broad torso
    rs.draw_volume(surf, cloth, [
        (cx - 10 * s * facing + lunge * 0.1, cy - 5 * s), (cx + 10 * s * facing + lunge * 0.15, cy - 6.5 * s),
        (cx + 11 * s * facing + lunge * 0.1, cy + 6.5 * s), (cx - 11 * s * facing, cy + 7.5 * s),
    ], deep, 1)
    # Thick arms
    rs.draw_volume_limb(surf, cx - 9 * s * facing, cy - 2 * s, cx - 14 * s * facing, cy + 7 * s, 1.7 * s, skin, deep)
    hand = (cx + 10 * s * facing + lunge * 0.35, cy - 1 * s - crouch * 2 * s)
    tip = (cx + 19 * s * facing + lunge, cy - 14 * s + strike * 7 * s)
    rs.draw_volume_limb(surf, cx + 8 * s * facing, cy - 3 * s, *hand, 1.7 * s, skin, deep)
    rs.draw_volume_limb(surf, *hand, *tip, 1.5 * s, (110, 75, 42), deep)
    rs.draw_volume(surf, (175, 175, 170), [
        (tip[0] - 1 * s * facing, tip[1] + 2 * s), (tip[0] + 8.5 * s * facing, tip[1] + 1 * s),
        (tip[0] + 7.5 * s * facing, tip[1] + 6.5 * s), (tip[0], tip[1] + 5.5 * s),
    ], deep, 1)
    if strike > 0.65:
        pygame.draw.circle(surf, (255, 235, 180), (int(tip[0]), int(tip[1])), max(2, int(2.5 * s * strike)), 1)
    # Heavy jaw head
    head = (cx + 1 * s * facing + lunge * 0.12, cy - 8.2 * s)
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


def draw_slime(surf, cx, cy, tile, t, hurt=False, attacking=0.0, facing=1):
    """Gelatinous mass — translucent layers, ground contact, internal variation."""
    facing = 1 if facing >= 0 else -1
    s = _s(tile, "monster")
    body = (200, 70, 75) if hurt else (74, 160, 106)
    hi = (235, 225, 150) if hurt else (140, 220, 165)
    deep = rs.shade(body, -50)
    bounce = abs(math.sin(t * 5)) * 2.2 * s
    squash = 1.0 + 0.08 * math.sin(t * 5 + 1.2)
    lunge_w, crouch, strike = rs.attack_impulse(attacking)
    lunge = lunge_w * 5 * s * facing
    bounce += crouch * 1.5 * s
    squash *= 1.0 + crouch * 0.25 - strike * 0.08
    rs.draw_contact_shadow(surf, cx + lunge * 0.2, cy + 9 * s, 12 * s * squash, 3.2 * s, 130)
    # Dark base puddle contact
    base_pts = rs.irregular_ring(cx + lunge * 0.2, cy + 7.5 * s, 11 * s * squash, 3.5 * s, n=8, seed=int(cx) + 3, jitter=0.15)
    rs.draw_poly(surf, deep, base_pts, None, 0)
    # Main gelatin body
    body_pts = rs.irregular_ring(cx + lunge * 0.5, cy + 1 * s - bounce, 11 * s * squash, 9.5 * s, n=10, seed=int(cx), jitter=0.22)
    rs.draw_volume(surf, body, body_pts, deep, max(1, int(s)))
    # Inner translucent core (lighter)
    core = rs.irregular_ring(cx - 0.5 * s + lunge * 0.5, cy - bounce, 6 * s, 5.5 * s, n=7, seed=int(cx) + 1, jitter=0.15)
    rs.draw_poly(surf, rs.shade(body, 25), core, None, 0)
    # Specular highlight band
    pygame.draw.arc(
        surf, hi,
        (cx - 7 * s + lunge * 0.5, cy - 7 * s - bounce, 14 * s, 10 * s),
        math.pi * 1.05, math.pi * 1.85, max(2, int(1.2 * s)),
    )
    pygame.draw.circle(surf, (255, 255, 230), (int(cx - 3 * s + lunge * 0.5), int(cy - 4 * s - bounce)), max(2, int(1.8 * s)))
    # Eyes floating inside
    for ox in (-3.2, 3.2):
        pygame.draw.circle(surf, (25, 35, 30), (int(cx + ox * s + lunge * 0.5), int(cy - 0.5 * s - bounce)), max(2, int(1.3 * s)))
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


def draw_big_skeleton(surf, cx, cy, tile, t, hurt=False, attacking=0.0, facing=1):
    """Larger, heavier skeleton — mithril cavern elite."""
    draw_skeleton(surf, cx, cy - 4, int(tile * 1.35), t, hurt=hurt, attacking=attacking, facing=facing)


def draw_spider(surf, cx, cy, tile, t, hurt=False, attacking=0.0, facing=1):
    """Giant dungeon spider — round abdomen, cephalothorax, eight jointed legs."""
    facing = 1 if facing >= 0 else -1
    s = _s(tile, "monster") * 0.95
    body = (120, 50, 50) if hurt else (48, 42, 52)
    hi, mid, sh, deep = rs.material(body)
    abdomen = (150, 60, 55) if hurt else (62, 52, 68)
    a_hi, a_mid, a_sh, a_deep = rs.material(abdomen)
    lunge_w, crouch, strike = rs.attack_impulse(attacking)
    bob = math.sin(t * 5.5) * 0.6 * s
    lunge = lunge_w * 5.5 * s * facing
    cy_base = cy + bob + crouch * 1.2 * s

    rs.draw_contact_shadow(surf, cx, cy + 8 * s, 16 * s, 4.2 * s, 140)
    rs.draw_cast_shadow(surf, cx + 2 * s * facing, cy + 8.5 * s, 17 * s, 4.5 * s, 95)

    # Eight legs (4 per side) — far pair first
    gait = t * 7.0
    for side in (-1, 1):
        for i, (ox, reach, phase) in enumerate((
            (-2.5, 14, 0.0),
            (-0.5, 16, 1.2),
            (2.0, 15, 2.4),
            (4.5, 12, 3.5),
        )):
            lift = max(0.0, math.sin(gait + phase + (0.8 if side > 0 else 0))) * (1.8 * s if abs(lunge_w) < 0.2 else 0.6 * s)
            hip = (cx + ox * s * facing + lunge * 0.15, cy_base + 1 * s)
            knee = (hip[0] + side * reach * 0.55 * s, hip[1] + 2 * s - lift)
            foot = (hip[0] + side * reach * s, cy_base + 7.5 * s - lift * 0.3)
            rs.draw_volume_limb(surf, *hip, *knee, 1.05 * s, mid, deep, taper=0.7, bulge=0.0)
            rs.draw_volume_limb(surf, *knee, *foot, 0.85 * s, sh, deep, taper=0.65, bulge=0.0)
            pygame.draw.circle(surf, deep, (int(foot[0]), int(foot[1])), max(1, int(0.9 * s)))

    # Abdomen (rear bulb)
    ax = cx - 6 * s * facing + lunge * 0.1
    ay = cy_base + 0.5 * s
    rs.draw_volume(surf, abdomen, [
        (ax - 7 * s * facing, ay + 2 * s), (ax - 5 * s * facing, ay - 5 * s),
        (ax + 2 * s * facing, ay - 6 * s), (ax + 5 * s * facing, ay - 1 * s),
        (ax + 3 * s * facing, ay + 5 * s), (ax - 4 * s * facing, ay + 6 * s),
    ], a_deep, 1)
    # Markings
    pygame.draw.line(surf, a_sh, (ax - 2 * s * facing, ay - 3 * s), (ax + 1 * s * facing, ay + 2 * s), max(1, int(s)))
    pygame.draw.circle(surf, a_hi, (int(ax - 1 * s * facing), int(ay - 1 * s)), max(2, int(1.6 * s)))

    # Cephalothorax
    hx = cx + 4 * s * facing + lunge * 0.4
    hy = cy_base - 1 * s
    rs.draw_volume(surf, body, [
        (hx - 5 * s * facing, hy + 2 * s), (hx - 4 * s * facing, hy - 4 * s),
        (hx + 3 * s * facing, hy - 5 * s), (hx + 6 * s * facing, hy - 1 * s),
        (hx + 4 * s * facing, hy + 3.5 * s), (hx - 2 * s * facing, hy + 4 * s),
    ], deep, 1)

    # Eyes cluster
    for ox, oy in ((-1.2, -1.5), (0.6, -2.0), (2.2, -1.2), (0.2, -0.2)):
        pygame.draw.circle(surf, (220, 60, 50) if not hurt else (255, 200, 80),
                           (int(hx + ox * s * facing), int(hy + oy * s)), max(1, int(0.85 * s)))
        pygame.draw.circle(surf, (20, 10, 10), (int(hx + ox * s * facing + 0.2 * s * facing), int(hy + oy * s)), max(1, int(0.3 * s)))

    # Fangs / chelicerae
    fang_reach = 3.5 * s + strike * 3.2 * s
    for side in (-1, 1):
        tip = (hx + 5 * s * facing + fang_reach * 0.3 * facing, hy + side * 2.2 * s + 1 * s)
        rs.draw_poly(surf, deep, [
            (hx + 3 * s * facing, hy + side * 1.2 * s),
            tip,
            (hx + 3.5 * s * facing, hy + side * 2.5 * s),
        ], None, 0)

    # Pedipalps
    for side in (-1, 1):
        pygame.draw.line(surf, mid,
                         (hx + 4 * s * facing, hy + side * 2 * s),
                         (hx + 8 * s * facing + lunge * 0.2, hy + side * 4 * s),
                         max(2, int(1.2 * s)))


def draw_dragon(surf, cx, cy, tile, t, hurt=False, attacking=0.0, facing=1):
    """Quadrapedal dragon — wings, scaled body, horned head, coiled tail."""
    facing = 1 if facing >= 0 else -1
    s = _s(tile, "monster") * 1.2
    bob = math.sin(t * 3.2) * 1.0
    body = (55, 40, 40) if hurt else (42, 115, 68)
    hi, mid, sh, deep = rs.material(body)
    wing = (32, 85, 52) if not hurt else (70, 40, 40)
    belly = (175, 155, 85) if not hurt else (160, 100, 70)
    cy += bob
    lunge_w, crouch, strike = rs.attack_impulse(attacking)
    lunge = lunge_w * 7 * s * facing
    cy += crouch * 1.5 * s

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
        rs.draw_volume(surf, wing, spar, deep, 1, detail="bark")
        pygame.draw.line(surf, deep, (cx + side * 3 * s, cy - 1 * s), (cx + side * 24 * s, cy - 14 * s - flap * 0.2), max(2, int(1.5 * s)))
        pygame.draw.line(surf, deep, (cx + side * 8 * s, cy), (cx + side * 18 * s, cy - 6 * s), max(1, int(s)))
    # Body barrel + belly
    rs.draw_volume(surf, body, [
        (cx - 13 * s * facing, cy + 3 * s),
        (cx - 9 * s * facing, cy - 7 * s),
        (cx + 10 * s * facing + lunge * 0.3, cy - 9 * s),
        (cx + 15 * s * facing + lunge, cy + 1 * s),
        (cx + 9 * s * facing, cy + 10 * s),
        (cx - 9 * s * facing, cy + 10 * s),
    ], deep, 1, detail="rock_scale")
    rs.draw_poly(surf, belly, [
        (cx - 5 * s * facing, cy + 2 * s), (cx + 8 * s * facing, cy + 1 * s),
        (cx + 6 * s * facing, cy + 8 * s), (cx - 4 * s * facing, cy + 8 * s),
    ], None, 0)
    # Scale ridges
    for i in range(4):
        yy = cy - 5 * s + i * 2.5 * s
        pygame.draw.line(surf, sh, (cx - 6 * s * facing, yy), (cx + 8 * s * facing, yy), 1)
    # Legs
    for ox in (-6, 4):
        rs.draw_volume_limb(surf, cx + ox * s * facing, cy + 6 * s, cx + (ox + 2) * s * facing, cy + 14 * s, 1.6 * s, deep, deep, taper=0.7, bulge=0.05)
        pygame.draw.circle(surf, sh, (int(cx + (ox + 2) * s * facing), int(cy + 14 * s)), max(2, int(1.8 * s)))
    # Neck + head
    rs.draw_volume_limb(surf, cx + 10 * s * facing, cy - 5 * s, cx + 20 * s * facing + lunge, cy - 13 * s, 2.4 * s, body, deep, taper=0.75, bulge=0.08)
    head = (cx + 22 * s * facing + lunge, cy - 15 * s)
    rs.draw_volume(surf, body, [
        (head[0] - 4 * s * facing, head[1] + 2 * s), (head[0] - 3 * s * facing, head[1] - 3 * s),
        (head[0] + 5 * s * facing, head[1] - 4 * s), (head[0] + 9 * s * facing, head[1]),
        (head[0] + 5 * s * facing, head[1] + 3 * s), (head[0] - 1 * s * facing, head[1] + 3.5 * s),
    ], deep, 1)
    pygame.draw.circle(surf, (255, 210, 50), (int(head[0] + 2 * s * facing), int(head[1] - 1 * s)), max(2, int(1.5 * s)))
    pygame.draw.circle(surf, (20, 18, 14), (int(head[0] + 2.3 * s * facing), int(head[1] - 0.8 * s)), max(1, int(0.6 * s)))
    # Jaws
    rs.draw_poly(surf, deep, [
        (head[0] + 5 * s * facing, head[1] + 0.5 * s),
        (head[0] + 13 * s * facing, head[1] - 1 * s),
        (head[0] + 5 * s * facing, head[1] + 3 * s),
    ], None, 0)
    if strike > 0.25:
        flame = (255, 140 + int(40 * strike), 40)
        pygame.draw.circle(surf, flame, (int(head[0] + 15 * s * facing), int(head[1])), max(2, int(3.5 * s * strike)))
        pygame.draw.circle(surf, (255, 230, 120), (int(head[0] + 14 * s * facing), int(head[1])), max(1, int(1.5 * s * strike)))
    # Horns
    for ox, oy in ((0, -3), (4, -2.5)):
        pygame.draw.line(surf, (220, 210, 175), (head[0] + ox * s * facing, head[1] + oy * s), (head[0] + (ox - 1) * s * facing, head[1] - 9 * s), max(2, int(1.6 * s)))
    # Tail with barb
    pygame.draw.lines(surf, sh, False, [
        (cx - 12 * s * facing, cy + 4 * s), (cx - 20 * s * facing, cy + 2 * s), (cx - 26 * s * facing, cy + 8 * s),
    ], max(3, int(2.8 * s)))
    rs.draw_poly(surf, hi, [
        (cx - 25 * s * facing, cy + 7 * s), (cx - 30 * s * facing, cy + 6 * s), (cx - 26 * s * facing, cy + 11 * s),
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
    lunge_w, crouch, strike = rs.attack_impulse(atk)
    lunge = lunge_w * 6.5 * s * facing
    lean = crouch * 0.22 + strike * 0.08
    cy_base = cy + bob + crouch * 1.1 * s
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
    lunge_w, crouch, strike = rs.attack_impulse(atk)
    lunge = lunge_w * 7 * s * facing
    cy_base = cy + bob + crouch * 1.15 * s
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

    # Arms — outward in screen space so raises/chops never cross the ribs
    arm_amp = 0.28 if moving else 0.06
    arm_l_off = max(-math.sin(gait) * arm_amp, -0.08)
    arm_r_off = min(-math.sin(gait + math.pi) * arm_amp, 0.08)

    # Attack: raise blade up-out, then chop down-forward along facing
    raise_amt = 0.0
    chop = 0.0
    brace = 0.0
    if atk > 0.01:
        if atk < 0.42:
            u = atk / 0.42
            ease = u * u * (3 - 2 * u)
            raise_amt = 0.85 * ease
            brace = 0.22 * ease
        else:
            u = (atk - 0.42) / 0.58
            ease = u * u * (3 - 2 * u)
            raise_amt = 0.85 * (1.0 - ease) + 0.10 * ease
            chop = 0.40 * ease
            brace = 0.22 * (1.0 - 0.5 * ease)

    out_far = 0.48 + brace + arm_l_off
    out_near = 0.40 + raise_amt - arm_r_off
    elbow_sign = 1 if facing >= 0 else -1

    sh_l = (cx - 3.8 * s, cy_base - 5 * s)
    sh_r = (cx + 3.8 * s, cy_base - 5 * s)
    if facing >= 0:
        sh_far, sh_near = sh_l, sh_r
        ang_far = rs.DOWN + out_far
        ang_near = rs.DOWN - out_near
    else:
        sh_far, sh_near = sh_r, sh_l
        ang_far = rs.DOWN - out_far
        ang_near = rs.DOWN + out_near

    el_far = rs.joint(*sh_far, ang_far, 3.0 * s)
    hand_far = rs.joint(*el_far, ang_far + 0.18 * elbow_sign, 2.8 * s)
    el_near = rs.joint(*sh_near, ang_near, 3.1 * s)
    hand_near = rs.joint(*el_near, ang_near - 0.06 * elbow_sign, 3.0 * s)
    hand_near = (
        hand_near[0] + chop * 2.2 * s * facing,
        hand_near[1] + chop * 1.5 * s,
    )

    rs.draw_volume_limb(surf, *sh_far, *el_far, 0.85 * s, bone, deep, taper=0.85, bulge=0.0)
    rs.draw_volume_limb(surf, *el_far, *hand_far, 0.75 * s, bone, deep, taper=0.8, bulge=0.0)
    rs.draw_volume_limb(surf, *sh_near, *el_near, 0.85 * s, bone, deep, taper=0.85, bulge=0.0)
    rs.draw_volume_limb(surf, *el_near, *hand_near, 0.75 * s, bone, deep, taper=0.8, bulge=0.0)
    pygame.draw.circle(surf, mid, (int(el_far[0]), int(el_far[1])), max(1, int(1.1 * s)))
    pygame.draw.circle(surf, mid, (int(el_near[0]), int(el_near[1])), max(1, int(1.1 * s)))

    # Bone blade — tip tracks raise/chop on the weapon side
    tip = (
        hand_near[0] + (4.2 * s + chop * 2.5 * s) * facing,
        hand_near[1] - (10 * s - raise_amt * 2.5 * s + chop * 6 * s),
    )
    rs.draw_volume(
        surf, (175, 180, 188),
        [
            hand_near,
            (hand_near[0] + 1.4 * s * facing, hand_near[1]),
            tip,
            (hand_near[0] - 0.7 * s * facing, hand_near[1] - 1.4 * s),
        ],
        deep, 1,
    )

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


def draw_pet_dragon(surf, cx, cy, tile, t, hurt=False, attacking=0.0, moving=False, facing=1,
                    body_rgb=(48, 125, 72), wing_rgb=(35, 95, 55), belly_rgb=(185, 165, 95),
                    scale=0.82, flame_rgb=(255, 145, 45)):
    """Mini dragon companion — wings flap, trot, fire breath on attack."""
    facing = 1 if facing >= 0 else -1
    s = _s(tile, "pet") * scale
    body = (55, 40, 40) if hurt else body_rgb
    hi, mid, sh, deep = rs.material(body)
    wing_c = (80, 45, 45) if hurt else wing_rgb
    belly = (160, 100, 70) if hurt else belly_rgb
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
    # Breath
    if atk > 0.25:
        flame = flame_rgb
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


def draw_pet_dragon_crimson(surf, cx, cy, tile, t, hurt=False, attacking=0.0, moving=False, facing=1):
    draw_pet_dragon(
        surf, cx, cy, tile, t, hurt=hurt, attacking=attacking, moving=moving, facing=facing,
        body_rgb=(150, 42, 38), wing_rgb=(100, 28, 30), belly_rgb=(210, 150, 90),
        scale=0.88, flame_rgb=(255, 90, 30),
    )


def draw_pet_dragon_frost(surf, cx, cy, tile, t, hurt=False, attacking=0.0, moving=False, facing=1):
    draw_pet_dragon(
        surf, cx, cy, tile, t, hurt=hurt, attacking=attacking, moving=moving, facing=facing,
        body_rgb=(70, 130, 180), wing_rgb=(50, 100, 150), belly_rgb=(200, 230, 245),
        scale=0.92, flame_rgb=(160, 230, 255),
    )


def draw_pet_dragon_shadow(surf, cx, cy, tile, t, hurt=False, attacking=0.0, moving=False, facing=1):
    draw_pet_dragon(
        surf, cx, cy, tile, t, hurt=hurt, attacking=attacking, moving=moving, facing=facing,
        body_rgb=(48, 32, 72), wing_rgb=(28, 18, 50), belly_rgb=(120, 70, 160),
        scale=0.96, flame_rgb=(170, 80, 255),
    )


def draw_pet_dragon_mythic(surf, cx, cy, tile, t, hurt=False, attacking=0.0, moving=False, facing=1):
    pulse = 0.5 + 0.5 * math.sin(t * 3.5)
    gold = (int(180 + 50 * pulse), int(140 + 40 * pulse), int(50 + 30 * pulse))
    draw_pet_dragon(
        surf, cx, cy, tile, t, hurt=hurt, attacking=attacking, moving=moving, facing=facing,
        body_rgb=gold, wing_rgb=(90, 50, 140), belly_rgb=(255, 230, 140),
        scale=1.05, flame_rgb=(255, 120, 220),
    )


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
        "pet_dragon_crimson": draw_pet_dragon_crimson,
        "dragon_crimson": draw_pet_dragon_crimson,
        "pet_dragon_frost": draw_pet_dragon_frost,
        "dragon_frost": draw_pet_dragon_frost,
        "pet_dragon_shadow": draw_pet_dragon_shadow,
        "dragon_shadow": draw_pet_dragon_shadow,
        "pet_dragon_mythic": draw_pet_dragon_mythic,
        "dragon_mythic": draw_pet_dragon_mythic,
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


def draw_wolf(surf, cx, cy, tile, t, hurt=False, attacking=0.0, moving=False, facing=1):
    """Lean grey mountain wolf — darker, sharper than the husky pet."""
    facing = 1 if facing >= 0 else -1
    s = _s(tile, "pet") * 1.08
    fur = (160, 90, 90) if hurt else (95, 100, 108)
    hi, mid, sh, deep = rs.material(fur)
    muzzle = (180, 175, 170)
    atk = max(0.0, min(1.0, float(attacking or 0)))
    gait = (t * 11.0) if moving else (t * 2.2)
    bob = abs(math.sin(gait)) * (1.6 if moving else 0.35) * s
    lunge_w, crouch, strike = rs.attack_impulse(atk)
    lunge = lunge_w * 8 * s * facing
    cy_base = cy + bob + crouch * 1.2 * s
    rs.draw_contact_shadow(surf, cx, cy + 10 * s, 12 * s, 3.2 * s, 145)
    lifts = [math.sin(gait + i * 1.55) for i in range(4)]
    for i, ox in enumerate((-6.0, -1.2, 3.2, 7.5)):
        lift = max(0.0, lifts[i]) * (2.2 * s if moving else 0.2 * s)
        fx = cx + ox * s * facing + lunge * 0.12
        fy = cy_base + 5 * s - lift
        rs.draw_volume_limb(surf, fx, fy, fx + 0.5 * s * facing, fy + 5.2 * s + lift * 0.2,
                            1.2 * s, mid, deep, taper=0.65, bulge=0.05)
    bx = cx + lunge * 0.25
    # Slim tail
    sway = math.sin(t * 3.5) * 0.6 * s
    for i, (tx, ty, rad) in enumerate([
        (bx - 8 * s * facing, cy_base + 1 * s, 2.0 * s),
        (bx - 9.5 * s * facing + sway, cy_base - 1 * s, 1.8 * s),
        (bx - 10 * s * facing + sway * 1.2, cy_base - 3.5 * s, 1.5 * s),
    ]):
        pygame.draw.circle(surf, mid, (int(tx), int(ty)), max(2, int(rad)))
    rs.draw_volume(surf, fur, [
        (bx - 9 * s * facing, cy_base + 2 * s),
        (bx - 7 * s * facing, cy_base - 3.5 * s),
        (bx + 2 * s * facing, cy_base - 4.5 * s),
        (bx + 8 * s * facing, cy_base - 1 * s),
        (bx + 6 * s * facing, cy_base + 3 * s),
        (bx - 4 * s * facing, cy_base + 4 * s),
    ])
    # Head
    hx = bx + 7 * s * facing + lunge * 0.15
    hy = cy_base - 3 * s
    rs.draw_volume(surf, fur, [
        (hx - 3 * s * facing, hy + 2 * s),
        (hx - 2 * s * facing, hy - 3 * s),
        (hx + 4 * s * facing, hy - 2.5 * s),
        (hx + 5 * s * facing, hy + 1 * s),
    ])
    # Ears
    pygame.draw.polygon(surf, mid, [
        (hx - 1 * s * facing, hy - 3 * s), (hx - 3 * s * facing, hy - 7 * s), (hx + 1 * s * facing, hy - 3.5 * s),
    ])
    pygame.draw.polygon(surf, mid, [
        (hx + 1.5 * s * facing, hy - 3 * s), (hx + 0.5 * s * facing, hy - 6.5 * s), (hx + 3.5 * s * facing, hy - 2.5 * s),
    ])
    # Snout + eyes
    pygame.draw.ellipse(surf, muzzle, (hx + 2 * s * facing - 2, hy - 1 * s, 5 * s, 3 * s))
    eye = (220, 60, 50) if strike > 0.2 or atk > 0.15 else (240, 220, 80)
    pygame.draw.circle(surf, eye, (int(hx + 2 * s * facing), int(hy - 2 * s)), max(1, int(1.2 * s)))
    if strike > 0.35:
        pygame.draw.polygon(surf, (240, 240, 245), [
            (hx + 4 * s * facing, hy + 1 * s),
            (hx + 7 * s * facing, hy + 0.5 * s),
            (hx + 4 * s * facing, hy + 2 * s),
        ])


MONSTER_DRAWERS["wolf"] = draw_wolf


def draw_shade(surf, cx, cy, tile, t, hurt=False, attacking=0.0, facing=1, moving=False):
    """Hooded void wraith — ragged cloak, pale skull, trailing mist."""
    facing = 1 if facing >= 0 else -1
    s = _s(tile, "monster") * 0.92
    pulse = 0.55 + 0.45 * abs(math.sin(t * 2.6))
    cloak = (48, 36, 72) if not hurt else (90, 40, 55)
    mist = (110, 80, 160)
    bone = (210, 205, 190) if not hurt else (200, 150, 140)
    hi, mid, sh, deep = rs.material(cloak)
    bob = math.sin(t * 3.0) * 2.2 * s
    cyb = cy + bob
    lunge_w, crouch, strike = rs.attack_impulse(attacking)
    lunge = lunge_w * 5 * s * facing
    layer = pygame.Surface((int(56 * s), int(64 * s)), pygame.SRCALPHA)
    ox, oy = int(28 * s), int(36 * s)
    # Trailing mist ribbons
    for i in range(4):
        ang = t * 1.8 + i * 0.9
        mx = ox - 10 * s * facing - i * 3 * s * facing + math.cos(ang) * 2 * s
        my = oy + 6 * s + i * 3 * s + math.sin(ang * 1.3) * 2 * s
        pygame.draw.ellipse(
            layer, (*mist, int(40 + 30 * pulse - i * 6)),
            (mx - 5 * s, my - 3 * s, 12 * s, 7 * s),
        )
    # Ragged cloak body
    pts = [
        (ox - 9 * s + lunge * 0.1, oy - 10 * s),
        (ox + 8 * s + lunge * 0.15, oy - 11 * s),
        (ox + 11 * s, oy + 4 * s),
        (ox + 7 * s, oy + 16 * s),
        (ox - 2 * s, oy + 12 * s),
        (ox - 10 * s, oy + 16 * s),
        (ox - 12 * s, oy + 2 * s),
    ]
    rs.draw_poly(layer, (*mid, int(200 + 40 * pulse)), pts, (*deep, 220), 1)
    # Hood
    rs.draw_poly(layer, (*hi, 230), [
        (ox - 6 * s + lunge * 0.1, oy - 8 * s),
        (ox + 1 * s * facing + lunge * 0.12, oy - 18 * s),
        (ox + 7 * s + lunge * 0.1, oy - 8 * s),
        (ox + 5 * s, oy - 4 * s),
        (ox - 5 * s, oy - 4 * s),
    ], (*deep, 240), 1)
    # Skull face in shadow
    hx = ox + 1.5 * s * facing + lunge * 0.12
    hy = oy - 9 * s
    pygame.draw.ellipse(layer, (*bone, 230), (hx - 4 * s, hy - 3 * s, 8 * s, 7 * s))
    for ex in (-1.6, 1.6):
        pygame.draw.ellipse(layer, (20, 8, 28, 240), (hx + ex * s - 1.2 * s, hy - 1.5 * s, 2.4 * s, 2.0 * s))
        pygame.draw.circle(layer, (180, 120, 255, 220), (int(hx + ex * s), int(hy - 0.6 * s)), max(1, int(0.7 * s)))
    # Skeletal hands reaching
    hand = (ox + 10 * s * facing + lunge, oy - 2 * s - crouch * 2 * s)
    rs.draw_volume_limb(layer, ox + 6 * s * facing, oy - 4 * s, *hand, 1.2 * s, bone, deep)
    for claw in (-1.5, 0, 1.5):
        pygame.draw.line(
            layer, (*bone, 230),
            (hand[0], hand[1]),
            (hand[0] + (3 + strike * 2) * s * facing, hand[1] + claw * s),
            max(1, int(s)),
        )
    if strike > 0.35:
        pygame.draw.circle(layer, (160, 90, 255, 160), (int(hand[0] + 4 * s * facing), int(hand[1])), max(2, int(3 * s * strike)))
    surf.blit(layer, (cx - ox, cyb - oy))


def draw_crypt_ghoul(surf, cx, cy, tile, t, hurt=False, attacking=0.0, facing=1, moving=False):
    """Hunched crypt scavenger — mottled hide, long claws, yellow eyes."""
    facing = 1 if facing >= 0 else -1
    s = _s(tile, "monster") * 0.95
    skin = (98, 118, 78) if not hurt else (150, 90, 80)
    hi, mid, sh, deep = rs.material(skin)
    cloth = (55, 48, 40)
    bob = abs(math.sin(t * (7.5 if moving else 2.2))) * (1.4 if moving else 0.35) * s
    cyb = cy + bob
    lunge_w, crouch, strike = rs.attack_impulse(attacking)
    lunge = lunge_w * 6 * s * facing
    rs.draw_contact_shadow(surf, cx, cy + 13 * s, 11 * s, 3.2 * s, 145)
    # Crouched legs
    rs.draw_volume_limb(surf, cx - 3 * s, cyb + 2 * s, cx - 7 * s - lunge_w * s, cyb + 13 * s, 1.8 * s, cloth, deep)
    rs.draw_volume_limb(surf, cx + 3 * s, cyb + 2 * s, cx + 6 * s + lunge_w * s, cyb + 13 * s, 1.8 * s, cloth, deep)
    # Torso hunched forward
    rs.draw_volume(surf, skin, [
        (cx - 8 * s + lunge * 0.1, cyb - 2 * s),
        (cx + 7 * s + lunge * 0.15, cyb - 5 * s),
        (cx + 8 * s + lunge * 0.1, cyb + 5 * s),
        (cx - 7 * s, cyb + 7 * s),
    ], deep, 1)
    # Long arms
    rs.draw_volume_limb(surf, cx - 7 * s, cyb - 1 * s, cx - 12 * s, cyb + 8 * s, 1.5 * s, skin, deep)
    hand = (cx + 9 * s * facing + lunge * 0.4, cyb + 1 * s - crouch * 2 * s)
    rs.draw_volume_limb(surf, cx + 6 * s * facing, cyb - 2 * s, *hand, 1.5 * s, skin, deep)
    for claw in (-2, 0, 2):
        pygame.draw.line(
            surf, deep,
            (hand[0], hand[1]),
            (hand[0] + (5 + strike * 3) * s * facing, hand[1] + claw * 0.8 * s),
            max(2, int(1.3 * s)),
        )
    # Head — low, jaw-heavy
    hx = cx + 2 * s * facing + lunge * 0.15
    hy = cyb - 9 * s
    rs.draw_volume(surf, skin, [
        (hx - 5 * s, hy + 2 * s), (hx - 4 * s, hy - 4 * s),
        (hx + 2 * s * facing, hy - 5 * s), (hx + 6 * s * facing, hy - 1 * s),
        (hx + 5 * s * facing, hy + 4 * s), (hx - 2 * s, hy + 4 * s),
    ], deep, 1)
    # Ear nubs / mane tufts
    pygame.draw.polygon(surf, mid, [
        (hx - 2 * s, hy - 3 * s), (hx - 4 * s, hy - 8 * s), (hx, hy - 4 * s),
    ])
    eye = (240, 210, 70) if strike < 0.3 else (255, 80, 60)
    pygame.draw.circle(surf, eye, (int(hx + 2.5 * s * facing), int(hy - 1.5 * s)), max(2, int(1.6 * s)))
    pygame.draw.circle(surf, (20, 12, 10), (int(hx + 2.8 * s * facing), int(hy - 1.3 * s)), max(1, int(0.7 * s)))
    # Teeth
    for ox in (-1.5, 0.2, 1.8):
        pygame.draw.polygon(surf, (230, 225, 210), [
            (hx + ox * s * facing, hy + 1.5 * s),
            (hx + (ox + 0.7) * s * facing, hy + 1.5 * s),
            (hx + (ox + 0.35) * s * facing, hy + 3.8 * s),
        ])


def draw_void_imp(surf, cx, cy, tile, t, hurt=False, attacking=0.0, facing=1, moving=False):
    """Bat-winged void sprite — lithe body, hooked horns, ember eyes."""
    facing = 1 if facing >= 0 else -1
    s = _s(tile, "monster") * 0.78
    body = (72, 38, 110) if not hurt else (140, 50, 80)
    hi, mid, sh, deep = rs.material(body)
    wing = (35, 18, 60)
    bob = math.sin(t * 5.5) * 2.4 * s
    cyb = cy + bob
    flap = math.sin(t * 9.5) * 4 * s
    lunge_w, crouch, strike = rs.attack_impulse(attacking)
    lunge = lunge_w * 4 * s * facing
    rs.draw_contact_shadow(surf, cx, cy + 9 * s, 9 * s, 2.6 * s, 120)
    # Wings (behind)
    for side in (-1, 1):
        tip_x = cx + side * (14 + abs(flap) * 0.15) * s
        tip_y = cyb - 10 * s - flap * side * 0.3
        rs.draw_poly(surf, wing, [
            (cx + side * 2 * s, cyb - 2 * s),
            (tip_x, tip_y),
            (cx + side * 8 * s, cyb + 4 * s),
            (cx + side * 3 * s, cyb + 2 * s),
        ], deep, 1)
        # Membrane ribs
        pygame.draw.line(surf, deep, (cx + side * 2 * s, cyb - 2 * s), (tip_x, tip_y), max(1, int(0.8 * s)))
    # Tail
    sway = math.sin(t * 4) * 2 * s
    rs.draw_volume_limb(
        surf, cx - 2 * s * facing, cyb + 4 * s,
        cx - 10 * s * facing + sway, cyb + 2 * s, 1.0 * s, body, deep,
    )
    pygame.draw.polygon(surf, mid, [
        (cx - 10 * s * facing + sway, cyb + 2 * s),
        (cx - 13 * s * facing + sway, cyb),
        (cx - 10 * s * facing + sway, cyb + 4 * s),
    ])
    # Body
    rs.draw_volume(surf, body, [
        (cx - 5 * s + lunge * 0.1, cyb + 5 * s),
        (cx - 4 * s, cyb - 4 * s),
        (cx + 4 * s + lunge * 0.1, cyb - 5 * s),
        (cx + 5 * s + lunge * 0.1, cyb + 4 * s),
    ], deep, 1)
    # Arms
    hand = (cx + 7 * s * facing + lunge, cyb + 1 * s)
    rs.draw_volume_limb(surf, cx + 3 * s * facing, cyb - 1 * s, *hand, 1.1 * s, body, deep)
    rs.draw_volume_limb(surf, cx - 3 * s, cyb - 1 * s, cx - 7 * s, cyb + 5 * s, 1.1 * s, body, deep)
    # Head
    hx = cx + 1 * s * facing + lunge * 0.1
    hy = cyb - 7 * s
    pygame.draw.ellipse(surf, mid, (hx - 4.5 * s, hy - 3.5 * s, 9 * s, 8 * s))
    pygame.draw.ellipse(surf, deep, (hx - 4.5 * s, hy - 3.5 * s, 9 * s, 8 * s), max(1, int(s)))
    # Hooked horns
    for side in (-1, 1):
        pygame.draw.lines(surf, (210, 190, 90), False, [
            (hx + side * 2 * s, hy - 3 * s),
            (hx + side * 4 * s, hy - 8 * s),
            (hx + side * 6 * s, hy - 7 * s),
        ], max(2, int(1.3 * s)))
    eye = (255, 140, 255) if strike < 0.25 else (255, 80, 120)
    pygame.draw.circle(surf, eye, (int(hx + 2 * s * facing), int(hy - 1 * s)), max(2, int(1.7 * s)))
    pygame.draw.circle(surf, (15, 8, 20), (int(hx + 2.4 * s * facing), int(hy - 0.8 * s)), max(1, int(0.7 * s)))
    if strike > 0.3:
        pygame.draw.circle(surf, (200, 100, 255), (int(hand[0]), int(hand[1])), max(2, int(2.5 * s * strike)))


def draw_obsidian_colossus(surf, cx, cy, tile, t, hurt=False, attacking=0.0, facing=1, moving=False):
    """Massive volcanic stone construct — cracked basalt plates, molten core light."""
    facing = 1 if facing >= 0 else -1
    s = _s(tile, "monster") * 1.12
    stone = (42, 40, 48) if not hurt else (90, 45, 50)
    hi, mid, sh, deep = rs.material(stone)
    magma = (255, 120, 40)
    glow = (180, 70, 255)
    pulse = 0.5 + 0.5 * abs(math.sin(t * 2.1))
    bob = abs(math.sin(t * (4 if moving else 1.2))) * (0.8 if moving else 0.2) * s
    cyb = cy + bob
    lunge_w, crouch, strike = rs.attack_impulse(attacking)
    lunge = lunge_w * 5 * s * facing
    rs.draw_contact_shadow(surf, cx, cy + 16 * s, 16 * s, 4.5 * s, 155)
    # Pillar legs
    for ox in (-6, 6):
        rs.draw_volume(surf, stone, [
            (cx + ox * s - 4 * s, cyb + 2 * s),
            (cx + ox * s + 4 * s, cyb + 2 * s),
            (cx + ox * s + 5 * s, cyb + 15 * s),
            (cx + ox * s - 5 * s, cyb + 15 * s),
        ], deep, 1)
        # Knee plate
        pygame.draw.rect(surf, mid, (cx + ox * s - 3 * s, cyb + 6 * s, 6 * s, 3 * s))
    # Heavy torso plates
    rs.draw_volume(surf, stone, [
        (cx - 12 * s + lunge * 0.05, cyb - 12 * s),
        (cx + 12 * s + lunge * 0.1, cyb - 13 * s),
        (cx + 13 * s + lunge * 0.08, cyb + 4 * s),
        (cx - 13 * s, cyb + 5 * s),
    ], deep, 1)
    # Shoulder slabs
    for side in (-1, 1):
        rs.draw_volume(surf, stone, [
            (cx + side * 8 * s, cyb - 12 * s),
            (cx + side * 16 * s, cyb - 14 * s),
            (cx + side * 15 * s, cyb - 6 * s),
            (cx + side * 9 * s, cyb - 5 * s),
        ], deep, 1)
    # Arms
    rs.draw_volume_limb(surf, cx - 12 * s, cyb - 8 * s, cx - 16 * s, cyb + 6 * s, 2.4 * s, stone, deep)
    fist = (cx + 14 * s * facing + lunge, cyb - 2 * s - crouch * 2 * s)
    rs.draw_volume_limb(surf, cx + 11 * s * facing, cyb - 9 * s, *fist, 2.4 * s, stone, deep)
    pygame.draw.ellipse(surf, mid, (fist[0] - 4 * s, fist[1] - 3 * s, 8 * s, 7 * s))
    # Head block
    hx, hy = cx + lunge * 0.08, cyb - 18 * s
    rs.draw_volume(surf, stone, [
        (hx - 7 * s, hy + 4 * s), (hx - 6 * s, hy - 4 * s),
        (hx + 6 * s, hy - 5 * s), (hx + 7 * s, hy + 4 * s),
    ], deep, 1)
    # Molten cracks (not "runes")
    crack_col = tuple(int(c * (0.6 + 0.4 * pulse)) for c in magma)
    for (ax, ay, bx, by) in (
        (-4, -2, 5, 1), (-2, 4, 6, 6), (0, -8, 3, -2), (-6, 0, -1, 3),
    ):
        pygame.draw.line(
            surf, crack_col,
            (cx + ax * s, cyb + ay * s), (cx + bx * s, cyb + by * s),
            max(1, int(1.2 * s)),
        )
    # Chest core
    pygame.draw.circle(surf, (*glow,), (int(cx), int(cyb - 4 * s)), max(2, int(3 * s * pulse)))
    pygame.draw.circle(surf, magma, (int(cx), int(cyb - 4 * s)), max(1, int(1.5 * s)))
    # Visor slit
    pygame.draw.rect(surf, (255, 90, 40), (hx - 4 * s, hy - 1 * s, 8 * s, 1.6 * s))
    if strike > 0.25:
        pygame.draw.circle(surf, magma, (int(fist[0]), int(fist[1])), max(3, int(5 * s * strike)), 2)


def draw_shadow_knight(surf, cx, cy, tile, t, hurt=False, attacking=0.0, facing=1, moving=False):
    """Armoured void knight — layered plate, torn cape, violet-eyed helm."""
    facing = 1 if facing >= 0 else -1
    s = _s(tile, "monster") * 1.0
    armor = (32, 30, 42) if not hurt else (90, 40, 50)
    hi, mid, sh, deep = rs.material(armor)
    steel = (120, 118, 135)
    cape = (55, 20, 70)
    bob = abs(math.sin(t * (6.5 if moving else 1.4))) * (1.1 if moving else 0.25) * s
    cyb = cy + bob
    lunge_w, crouch, strike = rs.attack_impulse(attacking)
    lunge = lunge_w * 7 * s * facing
    rs.draw_contact_shadow(surf, cx, cy + 14 * s, 12 * s, 3.4 * s, 150)
    # Cape
    sway = math.sin(t * 2.8) * 2 * s
    rs.draw_poly(surf, cape, [
        (cx - 2 * s * facing, cyb - 10 * s),
        (cx - 12 * s * facing + sway, cyb + 2 * s),
        (cx - 10 * s * facing + sway, cyb + 12 * s),
        (cx - 1 * s * facing, cyb + 4 * s),
    ], deep, 1)
    # Legs
    rs.draw_volume_limb(surf, cx - 3 * s, cyb + 2 * s, cx - 5 * s, cyb + 13 * s, 1.9 * s, armor, deep)
    rs.draw_volume_limb(surf, cx + 3 * s, cyb + 2 * s, cx + 5 * s, cyb + 13 * s, 1.9 * s, armor, deep)
    # Sabatons
    pygame.draw.ellipse(surf, mid, (cx - 7 * s, cyb + 12 * s, 5 * s, 2.5 * s))
    pygame.draw.ellipse(surf, mid, (cx + 2 * s, cyb + 12 * s, 5 * s, 2.5 * s))
    # Cuirass
    rs.draw_volume(surf, armor, [
        (cx - 8 * s + lunge * 0.08, cyb - 9 * s),
        (cx + 8 * s + lunge * 0.12, cyb - 10 * s),
        (cx + 9 * s + lunge * 0.1, cyb + 4 * s),
        (cx - 9 * s, cyb + 5 * s),
    ], deep, 1)
    # Chest ridge
    pygame.draw.line(surf, steel, (cx, cyb - 8 * s), (cx, cyb + 2 * s), max(1, int(s)))
    # Shield arm
    rs.draw_volume_limb(surf, cx - 7 * s * facing, cyb - 6 * s, cx - 12 * s * facing, cyb + 2 * s, 1.6 * s, armor, deep)
    shx = cx - 11 * s * facing
    shy = cyb
    rs.draw_volume(surf, armor, [
        (shx - 2 * s, shy - 6 * s), (shx + 5 * s * facing, shy - 7 * s),
        (shx + 4 * s * facing, shy + 5 * s), (shx - 3 * s, shy + 4 * s),
    ], deep, 1)
    # Sword arm
    hand = (cx + 9 * s * facing + lunge * 0.35, cyb - 2 * s - crouch * 2 * s)
    tip = (cx + 16 * s * facing + lunge, cyb - 16 * s + strike * 8 * s)
    rs.draw_volume_limb(surf, cx + 7 * s * facing, cyb - 7 * s, *hand, 1.6 * s, armor, deep)
    rs.draw_volume_limb(surf, *hand, *tip, 1.3 * s, steel, deep)
    # Crossguard
    pygame.draw.line(surf, steel, (hand[0] - 3 * s, hand[1]), (hand[0] + 3 * s, hand[1]), max(2, int(1.4 * s)))
    # Greathelm
    hx = cx + 1 * s * facing + lunge * 0.1
    hy = cyb - 14 * s
    rs.draw_volume(surf, armor, [
        (hx - 5 * s, hy + 3 * s), (hx - 4 * s, hy - 5 * s),
        (hx, hy - 8 * s), (hx + 5 * s, hy - 4 * s),
        (hx + 5 * s, hy + 3 * s),
    ], deep, 1)
    # Visor glow
    pygame.draw.rect(surf, (160, 60, 255), (hx - 3 * s * facing, hy - 1 * s, 5 * s, 1.5 * s))
    pygame.draw.circle(surf, (200, 120, 255), (int(hx + 1 * s * facing), int(hy - 0.5 * s)), max(1, int(1.1 * s)))
    if strike > 0.4:
        pygame.draw.line(surf, (200, 120, 255), (tip[0], tip[1]), (tip[0] + 8 * s * facing, tip[1] - 4 * s), max(2, int(2 * s)))


def draw_void_horror(surf, cx, cy, tile, t, hurt=False, attacking=0.0, facing=1, moving=False):
    """Boss — many-eyed void leviathan with thrashing tendrils and a split maw."""
    facing = 1 if facing >= 0 else -1
    s = _s(tile, "monster") * 1.28
    pulse = 0.5 + 0.5 * abs(math.sin(t * 2.0))
    flesh = (48, 18, 72) if not hurt else (110, 35, 55)
    hi, mid, sh, deep = rs.material(flesh)
    bob = math.sin(t * 2.3) * 2.2 * s
    cyb = cy + bob
    lunge_w, crouch, strike = rs.attack_impulse(attacking)
    lunge = lunge_w * 4 * s * facing
    rs.draw_contact_shadow(surf, cx, cy + 18 * s, 20 * s, 5.5 * s, 165)
    # Thrashing tendrils (behind body)
    for i in range(7):
        ang = t * 1.7 + i * (math.pi * 2 / 7)
        length = (16 + 4 * pulse + (3 if i % 2 else 0)) * s
        tx = cx + math.cos(ang) * length + lunge * 0.05
        ty = cyb + math.sin(ang) * length * 0.55
        mid_x = cx + math.cos(ang) * length * 0.5
        mid_y = cyb + math.sin(ang) * length * 0.3
        rs.draw_volume_limb(surf, cx, cyb, mid_x, mid_y, 2.2 * s, flesh, deep)
        rs.draw_volume_limb(surf, mid_x, mid_y, tx, ty, 1.6 * s, flesh, deep)
        # Sucker tip
        pygame.draw.circle(surf, mid, (int(tx), int(ty)), max(2, int(2.2 * s)))
        pygame.draw.circle(surf, (20, 8, 30), (int(tx), int(ty)), max(1, int(1.0 * s)))
    # Main body mass
    rs.draw_volume(surf, flesh, [
        (cx - 14 * s + lunge * 0.08, cyb + 8 * s),
        (cx - 12 * s, cyb - 8 * s),
        (cx - 2 * s, cyb - 14 * s),
        (cx + 10 * s + lunge * 0.1, cyb - 10 * s),
        (cx + 14 * s + lunge * 0.1, cyb + 2 * s),
        (cx + 10 * s, cyb + 12 * s),
        (cx - 4 * s, cyb + 14 * s),
    ], deep, 1)
    # Core glow
    pygame.draw.ellipse(surf, (90, 40, 140), (cx - 8 * s, cyb - 6 * s, 16 * s, 12 * s))
    pygame.draw.circle(surf, (170, 80, 255), (int(cx), int(cyb - 1 * s)), max(3, int(5 * s * pulse)))
    pygame.draw.circle(surf, (255, 210, 255), (int(cx), int(cyb - 1 * s)), max(2, int(2.2 * s)))
    # Ring of eyes
    for i, (ex, ey) in enumerate(((-7, -8), (-3, -11), (2, -12), (6, -9), (-6, -3), (7, -4), (0, -6))):
        blink = 0.85 + 0.15 * math.sin(t * 3 + i)
        er = max(2, int(2.2 * s * blink))
        pygame.draw.circle(surf, (255, 50, 80), (int(cx + ex * s), int(cyb + ey * s)), er)
        pygame.draw.circle(surf, (20, 8, 12), (int(cx + ex * s + 0.4 * s * facing), int(cyb + ey * s)), max(1, int(0.9 * s)))
    # Split maw
    maw_y = cyb + 4 * s
    rs.draw_poly(surf, (25, 8, 20), [
        (cx - 6 * s, maw_y - 2 * s),
        (cx + 6 * s * facing, maw_y - 1 * s),
        (cx + 4 * s * facing, maw_y + 5 * s),
        (cx - 5 * s, maw_y + 4 * s),
    ], deep, 1)
    for ox in (-3, -1, 1, 3):
        pygame.draw.polygon(surf, (230, 220, 200), [
            (cx + ox * s, maw_y),
            (cx + (ox + 0.8) * s, maw_y),
            (cx + (ox + 0.4) * s, maw_y + 3.5 * s),
        ])
    if strike > 0.2:
        pygame.draw.circle(surf, (160, 60, 255), (int(cx + 8 * s * facing), int(cyb - 16 * s)), max(3, int(7 * s * strike)))


# Keep old id aliased in case any leftover save references it
draw_rune_golem = draw_obsidian_colossus

MONSTER_DRAWERS.update({
    "shade": draw_shade,
    "crypt_ghoul": draw_crypt_ghoul,
    "void_imp": draw_void_imp,
    "obsidian_colossus": draw_obsidian_colossus,
    "rune_golem": draw_obsidian_colossus,  # legacy alias
    "shadow_knight": draw_shadow_knight,
    "void_horror": draw_void_horror,
})


def draw_magma_slug(surf, cx, cy, tile, t, hurt=False, attacking=0.0, facing=1, moving=False):
    """Blob of living magma — orange core, dark crust, drip sparks."""
    facing = 1 if facing >= 0 else -1
    s = _s(tile, "monster") * 1.05
    pulse = 0.5 + 0.5 * abs(math.sin(t * 3.2))
    bob = abs(math.sin(t * (8 if moving else 2))) * (1.2 if moving else 0.3) * s
    atk = max(0.0, min(1.0, float(attacking or 0)))
    stretch = 1.0 + atk * 0.25
    crust = (90, 40, 28) if not hurt else (160, 70, 50)
    core = (255, int(120 + 80 * pulse), 40)
    rs.draw_contact_shadow(surf, cx, cy + 8 * s, 11 * s, 3 * s, 140)
    pygame.draw.ellipse(surf, crust, (cx - 11 * s, cy - 4 * s + bob, 22 * s, 14 * s * stretch))
    pygame.draw.ellipse(surf, core, (cx - 7 * s, cy - 1 * s + bob, 14 * s, 9 * s * stretch))
    pygame.draw.ellipse(surf, (255, 220, 120), (cx - 3 * s, cy + 1 * s + bob, 6 * s, 4 * s))
    pygame.draw.circle(surf, (20, 10, 8), (int(cx - 3 * s * facing), int(cy - 1 * s + bob)), max(1, int(1.4 * s)))
    pygame.draw.circle(surf, (20, 10, 8), (int(cx + 2 * s * facing), int(cy - 1 * s + bob)), max(1, int(1.4 * s)))
    for i, ox in enumerate((-8, 0, 7)):
        ey = cy - (6 + 4 * abs(math.sin(t * 4 + i))) * s + bob
        pygame.draw.circle(surf, (255, 160, 50), (int(cx + ox * s), int(ey)), max(1, int(1.1 * s)))


def draw_ash_imp(surf, cx, cy, tile, t, hurt=False, attacking=0.0, facing=1, moving=False):
    """Small winged ash demon — soot body, ember eyes, jagged wings."""
    facing = 1 if facing >= 0 else -1
    s = _s(tile, "monster") * 0.95
    bob = math.sin(t * (10 if moving else 4)) * 1.5 * s
    atk = max(0.0, min(1.0, float(attacking or 0)))
    body = (55, 48, 52) if not hurt else (120, 70, 60)
    hi, mid, sh, deep = rs.material(body)
    rs.draw_contact_shadow(surf, cx, cy + 9 * s, 8 * s, 2.5 * s, 130)
    flap = math.sin(t * 9) * 3 * s
    for side in (-1, 1):
        pygame.draw.polygon(surf, mid, [
            (cx, cy - 2 * s + bob),
            (cx + side * (10 + atk * 2) * s, cy - 8 * s + bob - flap * side),
            (cx + side * 6 * s, cy + 2 * s + bob),
        ])
    rs.draw_volume(surf, body, [
        (cx - 4 * s, cy + 4 * s + bob),
        (cx - 5 * s, cy - 4 * s + bob),
        (cx + 5 * s, cy - 4 * s + bob),
        (cx + 4 * s, cy + 4 * s + bob),
    ])
    pygame.draw.circle(surf, mid, (int(cx), int(cy - 7 * s + bob)), max(2, int(3.5 * s)))
    pygame.draw.polygon(surf, deep, [
        (cx - 2 * s, cy - 9 * s + bob), (cx - 4 * s, cy - 14 * s + bob), (cx - 0.5 * s, cy - 9 * s + bob),
    ])
    pygame.draw.polygon(surf, deep, [
        (cx + 2 * s, cy - 9 * s + bob), (cx + 4 * s, cy - 14 * s + bob), (cx + 0.5 * s, cy - 9 * s + bob),
    ])
    eye = (255, 120, 40)
    pygame.draw.circle(surf, eye, (int(cx - 1.5 * s * facing), int(cy - 7 * s + bob)), max(1, int(1.2 * s)))
    pygame.draw.circle(surf, eye, (int(cx + 1.8 * s * facing), int(cy - 7 * s + bob)), max(1, int(1.2 * s)))


def draw_ember_wolf(surf, cx, cy, tile, t, hurt=False, attacking=0.0, facing=1, moving=False):
    """Charred wolf with molten underbelly and ember eyes."""
    facing = 1 if facing >= 0 else -1
    s = _s(tile, "pet") * 1.1
    fur = (180, 70, 50) if hurt else (70, 42, 38)
    hi, mid, sh, deep = rs.material(fur)
    atk = max(0.0, min(1.0, float(attacking or 0)))
    gait = (t * 11.0) if moving else (t * 2.2)
    bob = abs(math.sin(gait)) * (1.6 if moving else 0.35) * s
    lunge_w, crouch, strike = rs.attack_impulse(atk)
    lunge = lunge_w * 8 * s * facing
    cy_base = cy + bob + crouch * 1.2 * s
    rs.draw_contact_shadow(surf, cx, cy + 10 * s, 12 * s, 3.2 * s, 145)
    lifts = [math.sin(gait + i * 1.55) for i in range(4)]
    for i, ox in enumerate((-6.0, -1.2, 3.2, 7.5)):
        lift = max(0.0, lifts[i]) * (2.2 * s if moving else 0.2 * s)
        fx = cx + ox * s * facing + lunge * 0.12
        fy = cy_base + 5 * s - lift
        rs.draw_volume_limb(surf, fx, fy, fx + 0.5 * s * facing, fy + 5.2 * s + lift * 0.2,
                            1.2 * s, mid, deep, taper=0.65, bulge=0.05)
    bx = cx + lunge * 0.25
    rs.draw_volume(surf, fur, [
        (bx - 9 * s * facing, cy_base + 2 * s),
        (bx - 7 * s * facing, cy_base - 3.5 * s),
        (bx + 2 * s * facing, cy_base - 4.5 * s),
        (bx + 8 * s * facing, cy_base - 1 * s),
        (bx + 6 * s * facing, cy_base + 3 * s),
        (bx - 4 * s * facing, cy_base + 4 * s),
    ])
    pygame.draw.ellipse(surf, (220, 90, 30), (bx - 4 * s * facing, cy_base, 8 * s, 3.5 * s))
    hx = bx + 7 * s * facing + lunge * 0.15
    hy = cy_base - 3 * s
    rs.draw_volume(surf, fur, [
        (hx - 3 * s * facing, hy + 2 * s),
        (hx - 2 * s * facing, hy - 3 * s),
        (hx + 4 * s * facing, hy - 2.5 * s),
        (hx + 5 * s * facing, hy + 1 * s),
    ])
    pygame.draw.polygon(surf, mid, [
        (hx - 1 * s * facing, hy - 3 * s), (hx - 3 * s * facing, hy - 7 * s), (hx + 1 * s * facing, hy - 3.5 * s),
    ])
    pygame.draw.polygon(surf, mid, [
        (hx + 1.5 * s * facing, hy - 3 * s), (hx + 0.5 * s * facing, hy - 6.5 * s), (hx + 3.5 * s * facing, hy - 2.5 * s),
    ])
    eye = (255, 160, 40)
    pygame.draw.circle(surf, eye, (int(hx + 2 * s * facing), int(hy - 2 * s)), max(1, int(1.3 * s)))
    if strike > 0.35:
        pygame.draw.polygon(surf, (255, 200, 80), [
            (hx + 4 * s * facing, hy + 1 * s),
            (hx + 7 * s * facing, hy + 0.5 * s),
            (hx + 4 * s * facing, hy + 2 * s),
        ])


def draw_magma_knight(surf, cx, cy, tile, t, hurt=False, attacking=0.0, facing=1, moving=False):
    """Armored knight with molten cracks in the plate."""
    facing = 1 if facing >= 0 else -1
    s = _s(tile, "monster") * 1.05
    bob = abs(math.sin(t * (9 if moving else 2))) * (1.0 if moving else 0.2) * s
    atk = max(0.0, min(1.0, float(attacking or 0)))
    plate = (90, 55, 48) if not hurt else (160, 80, 60)
    hi, mid, sh, deep = rs.material(plate)
    rs.draw_contact_shadow(surf, cx, cy + 12 * s, 9 * s, 2.8 * s, 140)
    for ox in (-3.5, 3.5):
        pygame.draw.rect(surf, mid, (cx + ox * s - 2 * s, cy + 2 * s + bob, 4 * s, 9 * s))
    pygame.draw.rect(surf, mid, (cx - 6 * s, cy - 8 * s + bob, 12 * s, 12 * s), border_radius=2)
    pygame.draw.line(surf, (255, 100, 30), (cx - 4 * s, cy - 6 * s + bob), (cx + 3 * s, cy + 1 * s + bob), max(1, int(s)))
    pygame.draw.line(surf, (255, 160, 50), (cx + 2 * s, cy - 7 * s + bob), (cx - 1 * s, cy + 2 * s + bob), 1)
    pygame.draw.rect(surf, deep, (cx - 4.5 * s, cy - 15 * s + bob, 9 * s, 8 * s), border_radius=2)
    pygame.draw.rect(surf, (255, 140, 40), (cx - 3 * s, cy - 12 * s + bob, 6 * s, 2 * s))
    arm_x = cx + 7 * s * facing + atk * 4 * s * facing
    pygame.draw.line(surf, mid, (cx + 5 * s * facing, cy - 4 * s + bob), (arm_x, cy - 2 * s + bob), max(2, int(2 * s)))
    pygame.draw.line(surf, (200, 200, 210), (arm_x, cy - 10 * s + bob), (arm_x, cy + 6 * s + bob), max(2, int(1.6 * s)))
    pygame.draw.polygon(surf, (255, 180, 60), [
        (arm_x - 2 * s, cy - 10 * s + bob),
        (arm_x + 2 * s, cy - 10 * s + bob),
        (arm_x, cy - 14 * s + bob),
    ])


def draw_crucible_beast(surf, cx, cy, tile, t, hurt=False, attacking=0.0, facing=1, moving=False):
    """Broad lava brute — thick arms, glowing core, horned skull."""
    facing = 1 if facing >= 0 else -1
    s = _s(tile, "monster") * 1.25
    bob = abs(math.sin(t * (7 if moving else 1.8))) * (1.4 if moving else 0.3) * s
    atk = max(0.0, min(1.0, float(attacking or 0)))
    rock = (70, 38, 32) if not hurt else (150, 70, 50)
    hi, mid, sh, deep = rs.material(rock)
    rs.draw_contact_shadow(surf, cx, cy + 14 * s, 14 * s, 4 * s, 150)
    for ox in (-5, 5):
        pygame.draw.rect(surf, mid, (cx + ox * s - 3 * s, cy + 4 * s + bob, 6 * s, 10 * s))
    rs.draw_volume(surf, rock, [
        (cx - 12 * s, cy + 4 * s + bob),
        (cx - 10 * s, cy - 10 * s + bob),
        (cx + 10 * s, cy - 10 * s + bob),
        (cx + 12 * s, cy + 4 * s + bob),
    ])
    pygame.draw.ellipse(surf, (255, 110, 30), (cx - 5 * s, cy - 4 * s + bob, 10 * s, 8 * s))
    pygame.draw.ellipse(surf, (255, 200, 80), (cx - 2.5 * s, cy - 2 * s + bob, 5 * s, 4 * s))
    swing = atk * 6 * s * facing
    for side in (-1, 1):
        ax = cx + side * 12 * s + (swing if side == facing else 0)
        pygame.draw.line(surf, mid, (cx + side * 8 * s, cy - 6 * s + bob), (ax, cy + 6 * s + bob), max(3, int(3.2 * s)))
        pygame.draw.circle(surf, deep, (int(ax), int(cy + 7 * s + bob)), max(2, int(3.5 * s)))
    pygame.draw.circle(surf, mid, (int(cx), int(cy - 14 * s + bob)), max(3, int(5.5 * s)))
    pygame.draw.polygon(surf, deep, [
        (cx - 4 * s, cy - 16 * s + bob), (cx - 7 * s, cy - 24 * s + bob), (cx - 1 * s, cy - 17 * s + bob),
    ])
    pygame.draw.polygon(surf, deep, [
        (cx + 4 * s, cy - 16 * s + bob), (cx + 7 * s, cy - 24 * s + bob), (cx + 1 * s, cy - 17 * s + bob),
    ])
    eye = (255, 180, 50)
    pygame.draw.circle(surf, eye, (int(cx - 2 * s * facing), int(cy - 14 * s + bob)), max(1, int(1.6 * s)))
    pygame.draw.circle(surf, eye, (int(cx + 2.5 * s * facing), int(cy - 14 * s + bob)), max(1, int(1.6 * s)))


MONSTER_DRAWERS.update({
    "magma_slug": draw_magma_slug,
    "ash_imp": draw_ash_imp,
    "ember_wolf": draw_ember_wolf,
    "magma_knight": draw_magma_knight,
    "crucible_beast": draw_crucible_beast,
})


def draw_guard(surf, cx, cy, tile, t, hurt=False, attacking=0.0, facing=1, moving=False):
    """City watch — full steel harness, kite shield, crimson cloak tones."""
    skin = (210, 120, 110) if hurt else (225, 185, 145)
    eq = {
        "helmet": "steel_helmet",
        "body": "steel_body",
        "legs": "steel_legs",
        "weapon": "steel_longsword",
        "shield": "steel_shield",
    }
    draw_humanoid_detailed(
        surf, cx, cy, tile,
        body_color=(148, 32, 38), skin_color=skin, hair_color=(50, 40, 35),
        moving=bool(moving),
        t=t, facing=facing, equipment=eq, attacking=attacking,
    )


def draw_knight(surf, cx, cy, tile, t, hurt=False, attacking=0.0, facing=1, moving=False):
    """Castle knight — adamant plate, kite shield, commanding presence."""
    skin = (210, 120, 110) if hurt else (235, 195, 150)
    eq = {
        "helmet": "adamant_helmet",
        "body": "adamant_body",
        "legs": "adamant_legs",
        "weapon": "adamant_sword",
        "shield": "adamant_shield",
    }
    draw_humanoid_detailed(
        surf, cx, cy, int(tile * 1.08),
        body_color=(90, 140, 100), skin_color=skin, hair_color=(40, 35, 30),
        moving=bool(moving),
        t=t, facing=facing, equipment=eq, attacking=attacking,
    )


def draw_mythos_champion(surf, cx, cy, tile, t, hurt=False, attacking=0.0, facing=1, moving=False):
    """Level-90 castle champion — full Mythos dragon plate."""
    skin = (210, 120, 110) if hurt else (240, 200, 160)
    eq = {
        "helmet": "mythos_helmet",
        "body": "mythos_body",
        "legs": "mythos_legs",
        "weapon": "mythos_longsword",
        "shield": "mythos_shield",
        "amulet": "tidehollow_medal",
    }
    draw_humanoid_detailed(
        surf, cx, cy, int(tile * 1.14),
        body_color=(160, 40, 48), skin_color=skin, hair_color=(30, 22, 18),
        moving=bool(moving),
        t=t, facing=facing, equipment=eq, attacking=attacking,
    )


MONSTER_DRAWERS["guard"] = draw_guard
MONSTER_DRAWERS["knight"] = draw_knight
MONSTER_DRAWERS["mythos_champion"] = draw_mythos_champion


def _draw_castle_keep(surf, rect, alpha=245):
    """Stone keep — towers, battlements, and a south gatehouse with seated doors."""
    x, y, w, h = rect.x, rect.y, rect.w, rect.h
    keep = pygame.Surface((max(1, int(w + 28)), max(1, int(h + 36))), pygame.SRCALPHA)
    ox, oy = 14, 18
    # Opaque shell over the full footprint so the hall isn't visible from outside
    wall = pygame.Rect(ox, int(oy + h * 0.12), int(w), int(h * 0.82))
    pygame.draw.rect(keep, (96, 98, 104, alpha), wall)
    if not btex.blit_texture_tile(keep, wall, "brick", int(x // 40), int(y // 40), alpha=alpha):
        _fill_brick_face(keep, wall, seed_x=int(x), seed_y=int(y), alpha=alpha)
    # Soft foundation shadow under the keep
    pygame.draw.ellipse(
        keep, (20, 18, 22, min(110, alpha // 2)),
        (ox - 4, oy + h * 0.86, w + 8, h * 0.12),
    )
    # Battlement merlons
    merlon_w = max(7, int(w * 0.07))
    gap = max(3, int(merlon_w * 0.55))
    mx = ox
    while mx < ox + w - 2:
        pygame.draw.rect(keep, (118, 120, 126, alpha), (mx, oy + h * 0.06, merlon_w, h * 0.14))
        pygame.draw.rect(keep, (68, 70, 76, alpha), (mx, oy + h * 0.06, merlon_w, h * 0.14), 1)
        pygame.draw.line(keep, (160, 162, 168, alpha), (mx + 1, oy + h * 0.07), (mx + merlon_w - 2, oy + h * 0.07), 1)
        mx += merlon_w + gap
    # Corner towers with caps
    for tx in (ox - 6, ox + w - 12):
        tw, th = 18, int(h * 0.88)
        pygame.draw.rect(keep, (104, 106, 112, alpha), (tx, oy, tw, th))
        pygame.draw.rect(keep, (64, 66, 72, alpha), (tx, oy, tw, th), 1)
        pygame.draw.line(keep, (150, 152, 158, alpha), (tx + 1, oy + 2), (tx + 1, oy + th - 4), 2)
        for i in range(4):
            pygame.draw.rect(keep, (128, 130, 136, alpha), (tx + 1 + i * 4, oy - 5, 3, 9))
            pygame.draw.rect(keep, (70, 72, 78, alpha), (tx + 1 + i * 4, oy - 5, 3, 9), 1)
        # Arrow slits
        for ay in (0.28, 0.48, 0.68):
            pygame.draw.rect(keep, (28, 26, 30, alpha), (tx + tw // 2 - 1, oy + h * ay, 3, 8))
    # Narrow windows on the facade (mid wall, clear of battlements and gate)
    for wx_frac in (0.22, 0.78):
        wx = int(ox + w * wx_frac)
        wy = int(oy + h * 0.36)
        pygame.draw.rect(keep, (28, 26, 32, alpha), (wx - 3, wy - 2, 10, 18))
        pygame.draw.rect(keep, (70, 110, 140, alpha), (wx - 1, wy, 6, 14))
        pygame.draw.line(keep, (140, 180, 200, min(200, alpha)), (wx, wy + 1), (wx + 2, wy + 4), 1)
        pygame.draw.line(keep, (50, 52, 56, alpha), (wx + 2, wy), (wx + 2, wy + 14), 1)
    # Twin banners flanking the gate
    for bx_frac, flip in ((0.34, 1), (0.66, -1)):
        bx = ox + w * bx_frac
        pygame.draw.line(keep, (55, 45, 35, alpha), (bx, oy + h * 0.22), (bx, oy + h * 0.48), 2)
        pygame.draw.polygon(keep, (168, 36, 42, alpha), [
            (bx, oy + h * 0.24),
            (bx + 12 * flip, oy + h * 0.30),
            (bx, oy + h * 0.38),
        ])
        pygame.draw.circle(keep, (210, 180, 70, alpha), (int(bx + 4 * flip), int(oy + h * 0.30)), 2)
    # Gatehouse projecting bay
    gate_w = max(30, int(w * 0.18))
    gate_h = max(30, int(h * 0.38))
    gx = int(ox + w * 0.5 - gate_w * 0.5)
    gy = int(oy + h * 0.58)
    # Bay stone surround
    pygame.draw.rect(keep, (92, 94, 100, alpha), (gx - 8, gy - 10, gate_w + 16, gate_h + 12))
    pygame.draw.rect(keep, (60, 62, 68, alpha), (gx - 8, gy - 10, gate_w + 16, gate_h + 12), 1)
    # Cut arch opening (transparent so interior/floor shows through)
    for yy in range(gy, min(keep.get_height(), gy + gate_h)):
        for xx in range(gx, min(keep.get_width(), gx + gate_w)):
            rel = (xx - gx) / max(1, gate_w - 1)
            arch_top = gy + int((1.0 - math.sin(max(0.0, min(1.0, rel)) * math.pi)) * gate_h * 0.28)
            if yy >= arch_top:
                keep.set_at((xx, yy), (0, 0, 0, 0))
    # Stone arch ring + deep jambs
    arch_col = (118, 120, 126, alpha)
    dark = (42, 40, 46, alpha)
    pygame.draw.arc(
        keep, arch_col,
        (gx - 6, gy - 4, gate_w + 12, int(gate_h * 0.62)),
        0.02, math.pi - 0.02, max(4, gate_w // 8),
    )
    pygame.draw.rect(keep, dark, (gx - 5, gy + 8, 6, gate_h - 10))
    pygame.draw.rect(keep, dark, (gx + gate_w - 1, gy + 8, 6, gate_h - 10))
    # Portcullis teeth along the arch
    for i in range(6):
        tx = gx + 3 + i * max(4, gate_w // 7)
        pygame.draw.rect(keep, (70, 72, 78, alpha), (tx, gy + 2, 2, 7))
    # Wooden gate doors seated in the opening
    wood, wood_d, wood_h = (118, 82, 48, alpha), (68, 44, 26, alpha), (150, 110, 70, alpha)
    leaf_w = gate_w // 2 - 3
    for leaf_i, lx in enumerate((gx + 2, gx + gate_w // 2 + 1)):
        pygame.draw.rect(keep, wood, (lx, gy + 10, leaf_w, gate_h - 14))
        pygame.draw.rect(keep, wood_d, (lx, gy + 10, leaf_w, gate_h - 14), 1)
        for yy in range(3):
            pygame.draw.line(
                keep, wood_d,
                (lx + 2, gy + 16 + yy * (gate_h // 5)),
                (lx + leaf_w - 3, gy + 16 + yy * (gate_h // 5)), 1,
            )
        pygame.draw.line(keep, wood_h, (lx + 2, gy + 12), (lx + leaf_w - 3, gy + 12), 1)
        pygame.draw.circle(keep, (210, 175, 70, alpha), (lx + leaf_w // 2, gy + gate_h // 2 + 4), 3)
        pygame.draw.circle(keep, (90, 70, 30, alpha), (lx + leaf_w // 2, gy + gate_h // 2 + 4), 1)
    surf.blit(keep, (x - ox, y - oy))


def _draw_volcano_mountain(surf, rect, alpha=245, t=0.0):
    """Tall conical volcano massif — layered slopes, glowing crater, south mouth."""
    x, y, w, h = rect.x, rect.y, rect.w, rect.h
    pad_x, pad_y = 28, 90
    keep = pygame.Surface((max(1, int(w + pad_x * 2)), max(1, int(h + pad_y + 24))), pygame.SRCALPHA)
    ox, oy = pad_x, pad_y
    pulse = abs(math.sin((t or 0.0) * 1.8))
    glow = int(40 + 55 * pulse)

    # Ground contact + cast (upper-left key light → shadow lower-right)
    rs.draw_contact_shadow(surf, x + w * 0.5, y + h - 2, w * 0.52, max(6, h * 0.08), 150)
    rs.draw_cast_shadow(surf, x + w * 0.55, y + h + 2, w * 0.58, max(6, h * 0.10), 100)

    def layer(frac_top, frac_bot, inset, col, shade):
        top_y = oy + int(h * frac_top) - int((1.0 - frac_top) * 55)
        bot_y = oy + int(h * frac_bot)
        left = ox + int(w * inset)
        right = ox + int(w * (1.0 - inset))
        mid = ox + w // 2
        # Lit left face / shaded right face for volume
        pygame.draw.polygon(keep, (*col, alpha), [
            (mid, top_y),
            (left, bot_y),
            (mid, bot_y + 4),
        ])
        pygame.draw.polygon(keep, (*shade, alpha), [
            (mid, top_y),
            (right, bot_y),
            (mid, bot_y + 4),
        ])
        # Ridge highlight
        pygame.draw.line(keep, (min(255, col[0] + 40), min(255, col[1] + 30), min(255, col[2] + 25), alpha),
                         (mid, top_y), (left + 8, bot_y - 2), 2)

    # Stacked cone bands (dark basalt → warmer near crater)
    layer(0.02, 0.38, 0.02, (48, 36, 34), (28, 20, 20))
    layer(0.10, 0.52, 0.08, (62, 42, 38), (34, 24, 22))
    layer(0.20, 0.68, 0.16, (78, 48, 40), (40, 28, 26))
    layer(0.32, 0.82, 0.24, (92, 52, 42), (48, 32, 28))
    layer(0.44, 0.94, 0.32, (70, 40, 34), (36, 24, 22))

    # Crater rim + magma throat near the peak
    rim_y = oy + int(h * 0.08) - 48
    rim_w = max(28, int(w * 0.28))
    rim_x = ox + w // 2 - rim_w // 2
    pygame.draw.ellipse(keep, (28, 18, 16, alpha), (rim_x - 6, rim_y, rim_w + 12, 28))
    pygame.draw.ellipse(
        keep, (180 + glow // 2, 55 + glow // 3, 18, alpha),
        (rim_x, rim_y + 6, rim_w, 18),
    )
    pygame.draw.ellipse(
        keep, (255, 170 + glow // 2, 40, min(255, alpha)),
        (rim_x + rim_w // 4, rim_y + 9, rim_w // 2, 10),
    )
    # Rising smoke / embers from crater
    for i in range(7):
        ex = ox + w // 2 + int(math.sin(i * 1.7 + (t or 0) * 2) * rim_w * 0.28)
        ey = rim_y - 8 - int((i * 7 + abs(math.sin((t or 0) * 2.2 + i)) * 10))
        col = (90, 90, 95, max(30, alpha - 80 - i * 12)) if i % 2 == 0 else (255, 140, 50, max(40, alpha - 40))
        pygame.draw.circle(keep, col, (ex, ey), max(2, 5 - i // 2))

    # South mouth — cut a glowing tunnel so the entrance reads in 3D
    mouth_w = max(36, int(w * 0.22))
    mouth_h = max(40, int(h * 0.42))
    mx = ox + w // 2 - mouth_w // 2
    my = oy + h - mouth_h + 6
    # Rock arch frame
    pygame.draw.ellipse(keep, (22, 14, 12, alpha), (mx - 10, my - 18, mouth_w + 20, mouth_h + 10))
    # Cut opening (transparent)
    for yy in range(max(0, my - 8), min(keep.get_height(), my + mouth_h)):
        for xx in range(max(0, mx), min(keep.get_width(), mx + mouth_w)):
            rel = (xx - mx) / max(1, mouth_w - 1)
            arch = my - 8 + int((1.0 - math.sin(max(0.0, min(1.0, rel)) * math.pi)) * mouth_h * 0.35)
            if yy >= arch:
                keep.set_at((xx, yy), (0, 0, 0, 0))
    # Magma glow inside the mouth
    glow_s = pygame.Surface((mouth_w, mouth_h), pygame.SRCALPHA)
    pygame.draw.ellipse(
        glow_s, (255, 100 + glow // 2, 30, 90),
        (mouth_w // 6, mouth_h // 4, mouth_w * 2 // 3, mouth_h // 2),
    )
    keep.blit(glow_s, (mx, my))
    # Arch rim highlight
    pygame.draw.arc(
        keep, (120, 70, 50, alpha),
        (mx - 8, my - 16, mouth_w + 16, int(mouth_h * 0.7)),
        0.05, math.pi - 0.05, 4,
    )
    # Nameplate shelf
    pygame.draw.ellipse(keep, (55, 32, 26, alpha), (ox + int(w * 0.15), oy + h - 8, int(w * 0.7), 16))
    # Soft AO along base of cone (seam with ground)
    base_ao = pygame.Surface((keep.get_width(), max(8, h // 10)), pygame.SRCALPHA)
    for i in range(base_ao.get_height()):
        a = int(90 * (1.0 - i / max(1, base_ao.get_height() - 1)))
        pygame.draw.line(base_ao, (16, 10, 8, a), (ox, i), (ox + w, i))
    keep.blit(base_ao, (0, oy + h - base_ao.get_height()))

    surf.blit(keep, (x - ox, y - oy))


def _draw_void_sanctum(surf, rect, alpha=245):
    """Fallback crypt facade — delegates to shell3d inset volume when available."""
    try:
        import building_shell3d as shell3d
        shell3d.draw_crypt_shell(surf, rect, alpha=alpha)
        return
    except Exception:
        pass
    # Minimal last-resort flat (should rarely run)
    x, y, w, h = rect.x, rect.y, rect.w, rect.h
    pygame.draw.rect(surf, (28, 24, 40, alpha), (x, y + int(h * 0.12), w, int(h * 0.82)))
    pygame.draw.rect(surf, (18, 14, 28, alpha), (x, y + int(h * 0.12), w, int(h * 0.82)), 2)


def draw_building_roof(surf, rect, kind="house", style=0, alpha=245, material=None, yaw=0,
                       door_frac: float = 0.5):
    """
    Opaque building shell locked to footprint rect.
    Always camera-facing (door at bottom of rect). Never rotate the surface.
    """
    if kind == "castle":
        _draw_castle_keep(surf, rect, alpha=alpha)
        return
    if kind == "volcano" or material == "basalt":
        _draw_volcano_mountain(surf, rect, alpha=alpha)
        return
    try:
        import building_shell3d as shell3d
        if shell3d.draw_building_shell(
            surf, rect, kind=kind, material=material, style=style, alpha=alpha,
            door_frac=door_frac,
        ):
            return
    except Exception:
        pass
    if kind == "crypt" or material == "dark_stone":
        _draw_void_sanctum(surf, rect, alpha=alpha)



def draw_building_cutaway(surf, rect, kind="house", style=0, material=None, yaw=0, alpha=255,
                          door_frac: float = 0.5):
    """
    Interior cutaway — opaque perimeter walls; south wall opens at the door.
    """
    x, y, w, h = rect.x, rect.y, rect.w, rect.h
    if kind in ("volcano", "castle"):
        return
    wood = (material or ("brick" if style % 2 else "wood")) != "brick"
    wall = (118, 90, 60) if wood else (96, 98, 104)
    shade = (78, 58, 40) if wood else (62, 64, 70)
    thick = max(10, w // 9)
    back_h = max(14, int(h * 0.16))
    # Opaque back strip (north)
    pygame.draw.rect(surf, wall, (x + 2, y + int(h * 0.04), w - 4, back_h))
    pygame.draw.rect(surf, (40, 28, 20), (x + 2, y + int(h * 0.04) + back_h - 3, w - 4, 3))
    # Opaque left / right walls
    side_h = int(h * 0.78)
    pygame.draw.rect(surf, shade, (x + 1, y + int(h * 0.04), thick, side_h))
    pygame.draw.rect(surf, shade, (x + w - thick - 1, y + int(h * 0.04), thick, side_h))
    pygame.draw.line(surf, (175, 140, 100) if wood else (150, 152, 158),
                     (x + thick, y + int(h * 0.06)), (x + thick, y + int(h * 0.04) + side_h - 4), 2)
    pygame.draw.line(surf, (30, 22, 16),
                     (x + w - thick - 1, y + int(h * 0.06)),
                     (x + w - thick - 1, y + int(h * 0.04) + side_h - 4), 2)
    # South wall with door gap aligned to world door
    south_y = y + int(h * 0.82)
    south_h = max(8, int(h * 0.14))
    frac = max(0.12, min(0.88, float(door_frac)))
    door_w = max(16, int(w * 0.18))
    door_cx = int(x + w * frac)
    gap0 = max(x + thick, door_cx - door_w // 2)
    gap1 = min(x + w - thick, door_cx + door_w // 2)
    # Left south segment
    if gap0 > x + thick:
        pygame.draw.rect(surf, wall, (x + thick, south_y, gap0 - (x + thick), south_h))
    # Right south segment
    if gap1 < x + w - thick:
        pygame.draw.rect(surf, wall, (gap1, south_y, (x + w - thick) - gap1, south_h))
    # Door jambs
    pygame.draw.rect(surf, (55, 40, 28) if wood else (48, 50, 56), (gap0 - 3, south_y - 4, 4, south_h + 6))
    pygame.draw.rect(surf, (30, 20, 14), (gap1 - 1, south_y - 4, 4, south_h + 6))
    # Eave lip
    pygame.draw.rect(surf, (48, 34, 24), (x, y + int(h * 0.03), w, max(5, h // 18)))
    rs.draw_contact_shadow(surf, x + w * 0.5, y + h - 2, w * 0.4, max(3, h * 0.05), 90)


def draw_dungeon_entrance(surf, cx, cy, tile, t=0.0, yaw=0):
    """Stone arch — rotates with camera yaw so the mouth stays world-aligned."""
    s = _s(tile, 'object') * 0.72
    pad = int(70 * s)
    tmp = pygame.Surface((pad * 2, pad * 2), pygame.SRCALPHA)
    ox, oy = pad, pad
    # wide shadowed mouth (opens "south" / +y on temp)
    pygame.draw.ellipse(tmp, (12, 10, 16), (ox - 28 * s, oy - 4 * s, 56 * s, 22 * s))
    for oxp in (-24, 16):
        pygame.draw.rect(tmp, (88, 82, 78), (ox + oxp * s, oy - 18 * s, 9 * s, 28 * s))
        pygame.draw.rect(tmp, (55, 50, 48), (ox + oxp * s, oy - 18 * s, 9 * s, 28 * s), max(1, int(s)))
        pygame.draw.rect(tmp, (120, 110, 100), (ox + oxp * s - 1 * s, oy - 20 * s, 11 * s, 4 * s))
    _poly(tmp, (95, 88, 82), [
        (ox - 26 * s, oy - 14 * s),
        (ox - 12 * s, oy - 28 * s),
        (ox + 12 * s, oy - 28 * s),
        (ox + 26 * s, oy - 14 * s),
        (ox + 20 * s, oy - 10 * s),
        (ox - 20 * s, oy - 10 * s),
    ], (50, 45, 42), 2)
    pulse = int(20 + 15 * abs(math.sin(t * 2)))
    pygame.draw.ellipse(tmp, (40 + pulse, 30, 70 + pulse), (ox - 12 * s, oy - 8 * s, 24 * s, 14 * s))
    for oxp in (-18, 18):
        pygame.draw.circle(tmp, (255, 160 + pulse, 40), (int(ox + oxp * s), int(oy - 12 * s)), max(2, int(2.2 * s)))
    for oxp in (-6, 0, 6):
        pygame.draw.circle(tmp, (180, 140, 255), (int(ox + oxp * s), int(oy - 18 * s)), max(1, int(1.0 * s)))
    yaw = int(yaw or 0) % 4
    if yaw:
        tmp = pygame.transform.rotate(tmp, yaw * 90)
    surf.blit(tmp, (cx - tmp.get_width() // 2, cy - tmp.get_height() // 2))


def draw_warning_sign(surf, cx, cy, tile, t=0.0):
    """Standing warning plaque — skull + danger text plate."""
    s = _s(tile, "object") * 0.7
    pulse = int(10 + 8 * abs(math.sin(t * 2.4)))
    # Post
    pygame.draw.rect(surf, (70, 50, 30), (cx - 1.5 * s, cy - 2 * s, 3 * s, 14 * s))
    # Board
    pygame.draw.rect(surf, (40, 18, 18), (cx - 12 * s, cy - 16 * s, 24 * s, 14 * s), border_radius=2)
    pygame.draw.rect(surf, (180 + pulse // 2, 60, 50), (cx - 12 * s, cy - 16 * s, 24 * s, 14 * s), max(1, int(s)), border_radius=2)
    # Skull mark
    pygame.draw.circle(surf, (230, 220, 200), (int(cx), int(cy - 11 * s)), max(3, int(3.2 * s)))
    pygame.draw.circle(surf, (20, 12, 12), (int(cx - 1.5 * s), int(cy - 11.5 * s)), max(1, int(1.0 * s)))
    pygame.draw.circle(surf, (20, 12, 12), (int(cx + 1.5 * s), int(cy - 11.5 * s)), max(1, int(1.0 * s)))
    pygame.draw.rect(surf, (20, 12, 12), (cx - 1.2 * s, cy - 9 * s, 2.4 * s, 1.4 * s))


def draw_cave_entrance(surf, cx, cy, tile, t=0.0, yaw=0):
    """Sea-cave mouth — wet rock; rotates with camera yaw."""
    s = _s(tile, 'object') * 1.35
    pulse = int(12 + 10 * abs(math.sin(t * 1.7)))
    pad = int(80 * s)
    tmp = pygame.Surface((pad * 2, pad * 2), pygame.SRCALPHA)
    ox, oy = pad, pad
    pygame.draw.ellipse(tmp, (58, 62, 68), (ox - 36 * s, oy - 10 * s, 72 * s, 32 * s))
    pygame.draw.ellipse(tmp, (42, 46, 52), (ox - 30 * s, oy - 4 * s, 60 * s, 22 * s))
    pygame.draw.ellipse(tmp, (10, 12, 18), (ox - 20 * s, oy - 14 * s, 40 * s, 28 * s))
    pygame.draw.ellipse(tmp, (18 + pulse // 2, 28 + pulse, 48 + pulse), (ox - 12 * s, oy - 8 * s, 24 * s, 16 * s))
    for dx, dy in ((-22, -6), (18, -4), (-10, 6), (14, 8)):
        pygame.draw.circle(tmp, (90, 110, 130), (int(ox + dx * s), int(oy + dy * s)), max(1, int(1.5 * s)))
    yaw = int(yaw or 0) % 4
    if yaw:
        tmp = pygame.transform.rotate(tmp, yaw * 90)
    surf.blit(tmp, (cx - tmp.get_width() // 2, cy - tmp.get_height() // 2))


def draw_volcano_entrance(surf, cx, cy, tile, t=0.0, yaw=0):
    """Crater mouth — rotates with camera yaw."""
    s = _s(tile, "object") * 1.55
    pulse = abs(math.sin(t * 2.1))
    glow = int(40 + 50 * pulse)
    pad = int(100 * s)
    tmp = pygame.Surface((pad * 2, pad * 2), pygame.SRCALPHA)
    ox, oy = pad, pad
    rs.draw_contact_shadow(tmp, ox, oy + 14 * s, 36 * s, 6 * s, 145)
    rs.draw_cast_shadow(tmp, ox + 4 * s, oy + 16 * s, 40 * s, 7 * s, 95)
    pygame.draw.polygon(tmp, (36, 26, 28), [
        (ox - 48 * s, oy + 16 * s),
        (ox - 22 * s, oy - 36 * s),
        (ox, oy - 58 * s),
        (ox + 22 * s, oy - 36 * s),
        (ox + 48 * s, oy + 16 * s),
    ])
    pygame.draw.polygon(tmp, (58, 40, 36), [
        (ox - 36 * s, oy + 12 * s),
        (ox - 14 * s, oy - 28 * s),
        (ox, oy - 48 * s),
        (ox + 14 * s, oy - 28 * s),
        (ox + 36 * s, oy + 12 * s),
    ])
    pygame.draw.line(tmp, (110, 75, 60), (ox, oy - 48 * s), (ox - 36 * s, oy + 12 * s), max(2, int(2.5 * s)))
    pygame.draw.ellipse(tmp, (14, 10, 12), (ox - 20 * s, oy - 22 * s, 40 * s, 32 * s))
    pygame.draw.ellipse(tmp, (180 + glow // 2, 60 + glow // 3, 20), (ox - 13 * s, oy - 14 * s, 26 * s, 18 * s))
    pygame.draw.ellipse(tmp, (255, 180 + glow // 2, 40), (ox - 7 * s, oy - 8 * s, 14 * s, 9 * s))
    for i, dx in enumerate((-12, -4, 5, 12)):
        ey = oy - (28 + 14 * abs(math.sin(t * 2.4 + i))) * s
        col = (255, 140 + i * 15, 40) if i % 2 == 0 else (110, 110, 118)
        pygame.draw.circle(tmp, col, (int(ox + dx * s), int(ey)), max(1, int((1.5 + 0.4 * abs(math.sin(t * 3 + i))) * s)))
    pygame.draw.ellipse(tmp, (70, 40, 28), (ox - 28 * s, oy + 8 * s, 56 * s, 14 * s))
    yaw = int(yaw or 0) % 4
    if yaw:
        tmp = pygame.transform.rotate(tmp, yaw * 90)
    surf.blit(tmp, (cx - tmp.get_width() // 2, cy - tmp.get_height() // 2))



def draw_volcano_wall(surf, rect, seed_x, seed_y):
    """Dark basalt with molten veins — used for volcano overworld + Emberdeep."""
    r0 = _seeded(seed_x, seed_y, 2)
    shades = ((52, 36, 34), (40, 28, 28), (64, 44, 40), (32, 22, 24))
    base = shades[int(r0 * 4) % 4]
    hi, mid, sh, _ = rs.material(base)
    pygame.draw.rect(surf, mid, rect)
    # Key light: left brighter, right darker
    wash = pygame.Surface((rect.w, rect.h), pygame.SRCALPHA)
    for i in range(rect.w):
        if i < rect.w * 0.4:
            a = int(40 * (1.0 - i / max(1, rect.w * 0.4)))
            pygame.draw.line(wash, (255, 180, 120, a), (i, 0), (i, rect.h))
        else:
            a = int(55 * ((i - rect.w * 0.4) / max(1, rect.w * 0.6)))
            pygame.draw.line(wash, (10, 6, 6, a), (i, 0), (i, rect.h))
    surf.blit(wash, rect.topleft)
    pygame.draw.line(surf, hi, (rect.left + 1, rect.top + 1), (rect.right - 2, rect.top + 1), 2)
    pygame.draw.line(surf, hi, (rect.left + 1, rect.top + 1), (rect.left + 1, rect.bottom - 2), 1)
    pygame.draw.line(surf, sh, (rect.left + 1, rect.bottom - 1), (rect.right - 1, rect.bottom - 1), 1)
    # Magma crack
    if _seeded(seed_x, seed_y, 7) < 0.35:
        gx = rect.left + 2 + int(_seeded(seed_x, seed_y, 9) * (rect.w - 4))
        pygame.draw.line(
            surf, (220, 90, 30),
            (gx, rect.top + 2), (gx + int((_seeded(seed_x, seed_y, 11) - 0.5) * 6), rect.bottom - 2),
            max(1, rect.w // 10),
        )
        pygame.draw.line(
            surf, (255, 180, 60),
            (gx, rect.top + 3), (gx + 1, rect.centery),
            1,
        )
    # Base AO
    bot = pygame.Surface((rect.w, max(3, rect.h // 4)), pygame.SRCALPHA)
    for i in range(bot.get_height()):
        a = int(80 * ((i + 1) / bot.get_height()))
        pygame.draw.line(bot, (8, 4, 4, a), (0, i), (rect.w, i))
    surf.blit(bot, (rect.x, rect.bottom - bot.get_height()))
    pygame.draw.rect(surf, (18, 12, 12), rect, 1)


def draw_volcano_cliff(surf, cx, cy, tile, seed_x=0, seed_y=0, t=0.0):
    """Tall overhanging basalt face — gives mountain tiles real height."""
    s = tile / 40.0
    h = int(72 * s + (_seeded(seed_x, seed_y, 3) * 28 * s))
    w = int(tile * (0.95 + 0.2 * _seeded(seed_x, seed_y, 5)))
    pulse = abs(math.sin(t * 1.6 + seed_x * 0.2))
    # Soft contact plant + directional cast (warm-dark, upper-left key light)
    rs.draw_contact_shadow(surf, cx, cy + tile // 4, w * 0.52, max(3, tile * 0.12), 155)
    rs.draw_cast_shadow(surf, cx + w * 0.08, cy + tile // 3, w * 0.55, max(3, tile * 0.14), 100)
    # Main cliff body (lit left / shaded right)
    left = cx - w // 2
    top = cy - h + tile // 3
    mid_x = cx
    pts_lit = [(mid_x, top), (left, cy + tile // 4), (mid_x - 2, cy + tile // 4)]
    pts_sh = [(mid_x, top), (left + w, cy + tile // 4), (mid_x + 2, cy + tile // 4)]
    pygame.draw.polygon(surf, (78, 52, 44), pts_lit)
    pygame.draw.polygon(surf, (42, 28, 26), pts_sh)
    pygame.draw.line(surf, (130, 90, 70), (mid_x, top), (left + 4, cy), 2)
    # Magma vein
    if _seeded(seed_x, seed_y, 9) < 0.55:
        pygame.draw.line(
            surf, (255, int(90 + 80 * pulse), 30),
            (mid_x - 4, top + h * 0.25), (left + w * 0.35, cy),
            max(1, int(2 * s)),
        )
    # Peak tip
    pygame.draw.polygon(surf, (95, 65, 55), [
        (mid_x, top - int(10 * s)),
        (mid_x - int(8 * s), top + int(6 * s)),
        (mid_x + int(8 * s), top + int(6 * s)),
    ])
    # Soft AO along the base seam
    ao_h = max(4, tile // 6)
    ao = pygame.Surface((w + 4, ao_h), pygame.SRCALPHA)
    for i in range(ao_h):
        a = int(90 * (1.0 - i / max(1, ao_h - 1)))
        pygame.draw.line(ao, (16, 10, 8, a), (0, i), (w + 4, i))
    surf.blit(ao, (left - 2, cy + tile // 4 - 2))


def draw_volcano_floor(surf, rect, seed_x, seed_y):
    """Ash / scorched stone with faint heat shimmer tint."""
    r0 = _seeded(seed_x, seed_y, 1)
    shades = ((72, 48, 40), (58, 38, 34), (86, 56, 44), (48, 32, 30))
    line = (36, 22, 20)
    base = shades[int(r0 * 4) % 4]
    hi, mid, sh, _ = rs.material(base)
    pygame.draw.rect(surf, mid, rect)
    pygame.draw.line(surf, hi, (rect.left + 1, rect.top + 1), (rect.right - 2, rect.top + 1), 1)
    pygame.draw.line(surf, sh, (rect.left + 1, rect.bottom - 1), (rect.right - 1, rect.bottom - 1), 1)
    pygame.draw.rect(surf, line, rect, 1)
    if _seeded(seed_x, seed_y, 5) < 0.22:
        glow = pygame.Surface((rect.w, rect.h), pygame.SRCALPHA)
        pygame.draw.circle(glow, (255, 100, 30, 36), (rect.w // 2, rect.h // 2), rect.w // 2)
        surf.blit(glow, rect.topleft)
    if _seeded(seed_x, seed_y, 13) < 0.16:
        pygame.draw.circle(surf, (180, 70, 30), (rect.centerx, rect.centery), max(1, rect.w // 8))


def draw_lava(surf, rect, t=0.0, seed_x=0, seed_y=0):
    """Animated magma pool — used for crater pits and Emberdeep rivers."""
    phase = t * 2.4 + seed_x * 0.4 + seed_y * 0.3
    pulse = 0.5 + 0.5 * abs(math.sin(phase))
    deep = (120, 30, 10)
    mid = (200, 70, 20)
    bright = (255, int(140 + 80 * pulse), 40)
    pygame.draw.rect(surf, deep, rect)
    pygame.draw.ellipse(
        surf, mid,
        (rect.x + 2, rect.y + 2, max(4, rect.w - 4), max(4, rect.h - 4)),
    )
    # Hot core
    cw = max(4, int(rect.w * (0.35 + 0.1 * pulse)))
    ch = max(3, int(rect.h * (0.3 + 0.1 * pulse)))
    pygame.draw.ellipse(
        surf, bright,
        (rect.centerx - cw // 2, rect.centery - ch // 2, cw, ch),
    )
    # Crust plates
    for i in range(3):
        yy = rect.y + int(rect.h * (0.2 + 0.25 * i + 0.05 * math.sin(phase + i)))
        pygame.draw.line(surf, (80, 25, 12), (rect.x + 2, yy), (rect.right - 2, yy + 1), 1)
    # Ember sparks
    if _seeded(seed_x, seed_y, 4) < 0.7:
        sx = rect.x + int(rect.w * abs(math.sin(phase * 0.8)))
        sy = rect.y + int(rect.h * (0.2 + 0.3 * abs(math.cos(phase))))
        pygame.draw.circle(surf, (255, 220, 100), (sx, sy), 1)
    # Hot rim
    pygame.draw.rect(surf, (255, 120, 40), rect, 1)


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


def draw_door(surf, cx, cy, tile, open_=False, t=0.0, gate=False):
    """Wooden door with stone jamb — larger portcullis-style gate when gate=True."""
    if gate:
        draw_castle_gate(surf, cx, cy, tile, open_=open_, t=t)
        return
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


def draw_castle_gate(surf, cx, cy, tile, open_=False, t=0.0):
    """Wide castle gate — stone arch + wooden doors / open passage."""
    s = _s(tile, "object") * 1.05
    stone, stone_d = (118, 118, 126), (70, 72, 78)
    # Jambs + lintel
    pygame.draw.rect(surf, stone, (cx - 14 * s, cy - 18 * s, 5 * s, 30 * s))
    pygame.draw.rect(surf, stone, (cx + 9 * s, cy - 18 * s, 5 * s, 30 * s))
    pygame.draw.rect(surf, stone, (cx - 14 * s, cy - 20 * s, 28 * s, 5 * s))
    pygame.draw.rect(surf, stone_d, (cx - 14 * s, cy - 20 * s, 28 * s, 5 * s), 1)
    # Arch curve suggestion
    pygame.draw.arc(surf, stone_d, (cx - 12 * s, cy - 22 * s, 24 * s, 16 * s), 0.15, math.pi - 0.15, max(2, int(2 * s)))
    if open_:
        # Open passage — dark recess, not a flat black blob
        pygame.draw.rect(surf, (32, 30, 36), (cx - 9 * s, cy - 15 * s, 18 * s, 24 * s))
        pygame.draw.rect(surf, (48, 44, 40), (cx - 9 * s, cy - 15 * s, 5 * s, 24 * s))
        pygame.draw.rect(surf, (48, 44, 40), (cx + 4 * s, cy - 15 * s, 5 * s, 24 * s))
    else:
        wood = (110, 78, 48)
        wood_d = (70, 48, 28)
        pygame.draw.rect(surf, wood, (cx - 9 * s, cy - 15 * s, 8.5 * s, 24 * s))
        pygame.draw.rect(surf, wood, (cx + 0.5 * s, cy - 15 * s, 8.5 * s, 24 * s))
        pygame.draw.rect(surf, wood_d, (cx - 9 * s, cy - 15 * s, 8.5 * s, 24 * s), 1)
        pygame.draw.rect(surf, wood_d, (cx + 0.5 * s, cy - 15 * s, 8.5 * s, 24 * s), 1)
        for leaf_ox in (-4.5, 5):
            for yy in (-10, -4, 2, 6):
                pygame.draw.line(
                    surf, wood_d,
                    (cx + (leaf_ox - 3.5) * s, cy + yy * s),
                    (cx + (leaf_ox + 3.5) * s, cy + yy * s), 1,
                )
            pygame.draw.circle(surf, (210, 175, 70), (int(cx + leaf_ox * s), int(cy + 1 * s)), max(2, int(1.2 * s)))
        # Portcullis teeth along the top
        for i in range(5):
            tx = cx - 7 * s + i * 3.5 * s
            pygame.draw.rect(surf, (80, 82, 88), (tx, cy - 15 * s, 1.6 * s, 4 * s))


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


def draw_wishing_well(surf, cx, cy, tile, t=0.0):
    """Stone wishing well with shimmering water and wooden roof."""
    s = _s(tile, "object") * 1.55
    stone = (118, 118, 128)
    hi, mid, sh, deep = rs.material(stone)
    wood = (110, 74, 42)
    wood_d = (78, 50, 28)
    bob = math.sin(t * 2.4) * 0.4 * s
    rs.draw_contact_shadow(surf, cx, cy + 14 * s, 18 * s, 5 * s, 140)
    # Base ring
    rs.draw_volume(surf, stone, [
        (cx - 14 * s, cy + 2 * s), (cx + 14 * s, cy + 2 * s),
        (cx + 15 * s, cy + 12 * s), (cx - 15 * s, cy + 12 * s),
    ], deep, 1, detail="rock_scale")
    # Inner water
    pygame.draw.ellipse(surf, (40, 90, 140), (cx - 10 * s, cy + 1 * s + bob * 0.2, 20 * s, 8 * s))
    pygame.draw.ellipse(surf, (90, 180, 220), (cx - 5 * s, cy + 2 * s + bob * 0.3, 7 * s, 3.5 * s))
    # Posts + roof
    for ox in (-10, 10):
        pygame.draw.rect(surf, wood, (cx + ox * s - 1.6 * s, cy - 18 * s, 3.2 * s, 20 * s))
        pygame.draw.rect(surf, wood_d, (cx + ox * s - 1.6 * s, cy - 18 * s, 3.2 * s, 20 * s), 1)
    roof = [
        (cx - 15 * s, cy - 14 * s), (cx, cy - 24 * s), (cx + 15 * s, cy - 14 * s),
        (cx + 12 * s, cy - 11 * s), (cx - 12 * s, cy - 11 * s),
    ]
    rs.draw_volume(surf, (140, 70, 55), roof, deep, 1)
    # Bucket / rope
    pygame.draw.line(surf, (60, 50, 40), (cx, cy - 14 * s), (cx + 1 * s, cy + 2 * s + bob), max(1, int(s * 0.6)))
    pygame.draw.rect(surf, wood, (cx - 2.5 * s, cy + 1 * s + bob, 5 * s, 4.5 * s))
    # Coin sparkle
    if math.sin(t * 5) > 0.7:
        pygame.draw.circle(surf, (255, 230, 120), (int(cx - 3 * s), int(cy + 4 * s)), max(1, int(1.2 * s)))


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


def draw_throne(surf, cx, cy, tile, t=0.0):
    """Castle throne — raised seat with crimson cushion and gold finials."""
    s = _s(tile, "object") * 0.72
    rs.draw_contact_shadow(surf, cx, cy + 7 * s, 14 * s, 3.5 * s, 130)
    wood, dark, gold = (92, 62, 38), (50, 32, 18), (210, 175, 70)
    crimson = (150, 36, 48)
    # Backrest
    pygame.draw.rect(surf, wood, (cx - 9 * s, cy - 16 * s, 18 * s, 18 * s), border_radius=2)
    pygame.draw.rect(surf, dark, (cx - 9 * s, cy - 16 * s, 18 * s, 18 * s), 1, border_radius=2)
    pygame.draw.rect(surf, crimson, (cx - 7 * s, cy - 13 * s, 14 * s, 10 * s), border_radius=1)
    pygame.draw.line(surf, rs.shade(crimson, 30), (cx - 6 * s, cy - 12 * s), (cx + 6 * s, cy - 12 * s), 1)
    # Seat
    pygame.draw.rect(surf, wood, (cx - 10 * s, cy - 2 * s, 20 * s, 6 * s), border_radius=1)
    pygame.draw.rect(surf, crimson, (cx - 8 * s, cy - 3 * s, 16 * s, 3.5 * s))
    # Arms + legs
    for ox in (-10, 8):
        pygame.draw.rect(surf, dark, (cx + ox * s, cy - 6 * s, 2.5 * s, 12 * s))
    for ox in (-8, 6):
        pygame.draw.rect(surf, dark, (cx + ox * s, cy + 3 * s, 2.2 * s, 5 * s))
    # Crown finials
    for ox in (-7, 0, 7):
        pygame.draw.circle(surf, gold, (int(cx + ox * s), int(cy - 16 * s)), max(2, int(1.4 * s)))
        pygame.draw.circle(surf, (140, 110, 40), (int(cx + ox * s), int(cy - 16 * s)), max(1, int(0.6 * s)))


def draw_banner_stand(surf, cx, cy, tile, t=0.0, color=None):
    """Floor banner on a pole."""
    s = _s(tile, "object") * 0.6
    color = tuple(color) if color else (160, 40, 48)
    rs.draw_contact_shadow(surf, cx, cy + 6 * s, 4 * s, 2 * s, 90)
    pygame.draw.line(surf, (70, 55, 40), (cx, cy - 14 * s), (cx, cy + 6 * s), max(2, int(1.5 * s)))
    sway = math.sin(t * 1.4) * 1.2 * s
    pygame.draw.polygon(surf, color, [
        (cx, cy - 13 * s),
        (cx + 9 * s + sway, cy - 10 * s),
        (cx + 8 * s + sway, cy - 4 * s),
        (cx, cy - 6 * s),
    ])
    pygame.draw.circle(surf, (210, 180, 70), (int(cx + 3 * s + sway * 0.4), int(cy - 9 * s)), max(1, int(s)))


def draw_fountain(surf, cx, cy, tile, t=0.0):
    """City plaza fountain — stone basin with animated spray."""
    s = _s(tile, "object") * 0.78
    rs.draw_contact_shadow(surf, cx, cy + 6 * s, 16 * s, 4 * s, 120)
    stone, dark = (148, 146, 152), (70, 68, 74)
    water = (70, 140, 190)
    pygame.draw.ellipse(surf, stone, (cx - 14 * s, cy - 2 * s, 28 * s, 12 * s))
    pygame.draw.ellipse(surf, dark, (cx - 14 * s, cy - 2 * s, 28 * s, 12 * s), 2)
    pygame.draw.ellipse(surf, water, (cx - 11 * s, cy - 1 * s, 22 * s, 8 * s))
    pygame.draw.ellipse(surf, (150, 210, 240), (cx - 8 * s, cy - 0.5 * s, 10 * s, 3 * s))
    # Pedestal + spout
    pygame.draw.rect(surf, stone, (cx - 3 * s, cy - 10 * s, 6 * s, 10 * s))
    pygame.draw.rect(surf, dark, (cx - 3 * s, cy - 10 * s, 6 * s, 10 * s), 1)
    pygame.draw.circle(surf, stone, (int(cx), int(cy - 11 * s)), max(3, int(3.2 * s)))
    pygame.draw.circle(surf, dark, (int(cx), int(cy - 11 * s)), max(3, int(3.2 * s)), 1)
    # Spray
    for i in range(6):
        ang = t * 2.4 + i * 1.05
        px = cx + math.cos(ang) * (2.5 + (i % 3)) * s
        py = cy - 12 * s - abs(math.sin(t * 3 + i)) * 5 * s
        pygame.draw.circle(surf, (210, 235, 250), (int(px), int(py)), max(1, int(1.2 * s)))


def draw_market_stall(surf, cx, cy, tile, t=0.0):
    """Canvas market stall with crate goods."""
    s = _s(tile, "object") * 0.7
    rs.draw_contact_shadow(surf, cx, cy + 6 * s, 14 * s, 3.2 * s, 115)
    wood, dark = (120, 84, 50), (60, 40, 24)
    canvas = (180, 70, 55)
    # Posts + counter
    for ox in (-9, 9):
        pygame.draw.rect(surf, dark, (cx + ox * s - 1 * s, cy - 12 * s, 2 * s, 16 * s))
    pygame.draw.rect(surf, wood, (cx - 11 * s, cy - 1 * s, 22 * s, 5 * s))
    pygame.draw.rect(surf, dark, (cx - 11 * s, cy - 1 * s, 22 * s, 5 * s), 1)
    # Awning
    pygame.draw.polygon(surf, canvas, [
        (cx - 12 * s, cy - 8 * s),
        (cx + 12 * s, cy - 8 * s),
        (cx + 10 * s, cy - 14 * s),
        (cx - 10 * s, cy - 14 * s),
    ])
    pygame.draw.line(surf, (220, 200, 170), (cx - 10 * s, cy - 13 * s), (cx + 10 * s, cy - 13 * s), 1)
    for i, col in enumerate(((200, 160, 60), (70, 130, 70), (180, 60, 50))):
        pygame.draw.ellipse(surf, col, (cx - 8 * s + i * 6 * s, cy - 5 * s, 5 * s, 3.5 * s))


def draw_brazier(surf, cx, cy, tile, t=0.0):
    """Castle hall brazier with flicker."""
    s = _s(tile, "object") * 0.55
    rs.draw_contact_shadow(surf, cx, cy + 5 * s, 7 * s, 2.4 * s, 110)
    iron = (70, 68, 74)
    pygame.draw.rect(surf, iron, (cx - 2 * s, cy - 2 * s, 4 * s, 8 * s))
    pygame.draw.ellipse(surf, iron, (cx - 6 * s, cy - 6 * s, 12 * s, 6 * s))
    pygame.draw.ellipse(surf, (40, 38, 42), (cx - 6 * s, cy - 6 * s, 12 * s, 6 * s), 1)
    flicker = 0.85 + 0.15 * math.sin(t * 9)
    pygame.draw.polygon(surf, (255, int(140 * flicker), 40), [
        (cx - 3 * s, cy - 5 * s),
        (cx + 3 * s, cy - 5 * s),
        (cx, cy - (12 + 2 * math.sin(t * 11)) * s),
    ])
    pygame.draw.polygon(surf, (255, 220, 120), [
        (cx - 1.5 * s, cy - 5 * s),
        (cx + 1.5 * s, cy - 5 * s),
        (cx, cy - (8 + math.sin(t * 13)) * s),
    ])


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
