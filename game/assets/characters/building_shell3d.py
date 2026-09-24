"""
Connected ¾-view (oblique) building shells for Mythoscape.

Draw order produces a sealed box: ground shadow → side wall → front wall →
roof volumes → eaves cast → windows/door/chimney. Side plane shares the front
wall's right edge so nothing floats or gaps.
"""
from __future__ import annotations

import math

import pygame

import building_textures as btex


def _clamp(v, lo, hi):
    return max(lo, min(hi, v))


def _shade(rgb, d):
    return tuple(_clamp(c + d, 0, 255) for c in rgb[:3])


def _fill_poly(surf, pts, tex_name, shade=0, flat=None, alpha=255, uv=(0, 0), outline=True):
    if not pts or len(pts) < 3:
        return
    flat = flat or (120, 90, 60)
    xs = [p[0] for p in pts]
    ys = [p[1] for p in pts]
    minx, maxx = int(min(xs)), int(max(xs)) + 1
    miny, maxy = int(min(ys)), int(max(ys)) + 1
    w, h = max(1, maxx - minx), max(1, maxy - miny)
    piece = pygame.Surface((w, h), pygame.SRCALPHA)
    local = [(p[0] - minx, p[1] - miny) for p in pts]
    # Opaque base then texture on top
    pygame.draw.polygon(piece, (*flat, 255), local)
    btex.fill_polygon_textured(piece, local, tex_name, alpha=255, uv_origin=uv)
    if shade:
        ov = pygame.Surface((w, h), pygame.SRCALPHA)
        c = _clamp(128 + shade, 0, 255)
        ov.fill((c, c, c, 255))
        piece.blit(ov, (0, 0), special_flags=pygame.BLEND_RGBA_MULT)
        mask = pygame.Surface((w, h), pygame.SRCALPHA)
        pygame.draw.polygon(mask, (255, 255, 255, 255), local)
        piece.blit(mask, (0, 0), special_flags=pygame.BLEND_RGBA_MULT)
    # Force every drawn pixel to full opacity (no ghost walls)
    try:
        import pygame.surfarray as sa
        rgb = sa.pixels3d(piece)
        a = sa.pixels_alpha(piece)
        a[:] = 255 * ((rgb[:, :, 0] | rgb[:, :, 1] | rgb[:, :, 2]) > 0)
        del rgb, a
    except Exception:
        pass
    surf.blit(piece, (minx, miny))
    # Optional subtle outline (skip for internal walls to avoid gaps)
    if outline:
        pygame.draw.polygon(surf, (18, 12, 10), pts, 1)


def _key_light(surf, rect, left=55, right=70, alpha=255):
    if rect.w < 4 or rect.h < 4:
        return
    wash = pygame.Surface((rect.w, rect.h), pygame.SRCALPHA)
    for x in range(rect.w):
        t = x / max(1, rect.w - 1)
        if t < 0.42:
            a = int(left * ((0.42 - t) / 0.42) ** 1.05)
            col = (255, 245, 220, a)
        else:
            a = int(right * ((t - 0.42) / 0.58) ** 1.2)
            col = (14, 10, 8, a)
        pygame.draw.line(wash, col, (x, 0), (x, rect.h))
    if alpha < 255:
        wash.set_alpha(alpha)
    surf.blit(wash, rect.topleft)


def _ao_band(surf, x, y, w, h, strength=120, falloff="down"):
    if w < 2 or h < 2:
        return
    band = pygame.Surface((int(w), int(h)), pygame.SRCALPHA)
    for i in range(int(h)):
        t = (1.0 - i / max(1, h - 1)) if falloff == "down" else (i / max(1, h - 1))
        a = int(strength * (t ** 1.25))
        pygame.draw.line(band, (12, 8, 6, a), (0, i), (int(w), i))
    surf.blit(band, (int(x), int(y)))


def _window(surf, wx, wy, ww, wh, wood=True, alpha=255):
    pygame.draw.rect(surf, (12, 8, 6, alpha), (wx - 5, wy - 5, ww + 10, wh + 12))
    frame = (160, 128, 90) if wood else (138, 140, 146)
    dark = (55, 40, 28) if wood else (48, 50, 56)
    pygame.draw.rect(surf, (*frame, alpha), (wx - 3, wy - 3, ww + 6, wh + 6))
    pygame.draw.rect(surf, (*dark, alpha), (wx - 3, wy + wh + 1, ww + 6, 3))
    pygame.draw.rect(surf, (8, 6, 8, alpha), (wx, wy, ww, wh))
    pygame.draw.rect(surf, (95, 72, 48, alpha) if wood else (88, 90, 96, alpha), (wx, wy, 3, wh))
    pygame.draw.rect(surf, (18, 12, 10, alpha), (wx + ww - 3, wy, 3, wh))
    gx, gy = wx + 3, wy + 3
    gw, gh = ww - 6, wh - 6
    pygame.draw.rect(surf, (48, 95, 135, alpha), (gx, gy, gw, gh))
    pygame.draw.rect(surf, (220, 240, 255, min(220, alpha)), (gx + 1, gy + 1, max(2, gw // 3), max(2, gh // 3)))
    pygame.draw.line(surf, (*dark, alpha), (gx + gw // 2, gy), (gx + gw // 2, gy + gh), 2)
    pygame.draw.line(surf, (*dark, alpha), (gx, gy + gh // 2), (gx + gw, gy + gh // 2), 2)
    # Projecting sill
    sx, sy = wx - 4, wy + wh + 2
    pygame.draw.polygon(surf, (200, 170, 125, alpha) if wood else (175, 177, 182, alpha), [
        (sx, sy), (sx + ww + 8, sy), (sx + ww + 5, sy + 3), (sx + 3, sy + 3),
    ])
    pygame.draw.polygon(surf, (130, 100, 70, alpha) if wood else (115, 117, 122, alpha), [
        (sx + 3, sy + 3), (sx + ww + 5, sy + 3), (sx + ww + 3, sy + 7), (sx + 5, sy + 7),
    ])


def _door_cut(surf, dx, dy, dw, dh, wood=True, alpha=255, arch=True):
    """Backward-compatible wrapper — prefers recessed entrance geometry."""
    _recessed_entrance(surf, dx, dy, dw, dh, wood=wood, alpha=alpha, arch=arch)


def _recessed_entrance(
    surf, dx, dy, dw, dh, *, wood=True, alpha=255, arch=True, stone=False, glow=None,
):
    """
    Door carved INTO the front wall — not a box pasted in front.

    Stone path punches a hole through the facade, then draws wall-thickness
    jambs inside that hole. Wood path keeps a timber surround for cottages.
    """
    stone = stone or (not wood)
    # VERY DEEP recess with WIDE interior surfaces (to match target reference)
    depth = max(28, min(45, int(dw * 0.4)))  # 28-45px recess (40% of door width)
    jamb = max(16, min(28, depth - 4))       # 16-28px wide visible interior walls

    if stone:
        # --- Carve a hole (no proud frame, no silver box) ---
        throat = (6, 4, 12, alpha)
        if glow:
            throat = (max(4, glow[0] // 12), max(2, glow[1] // 14), max(10, glow[2] // 5), alpha)

        # VERY deep reveal for prominent wall thickness
        depth = max(24, min(40, int(dw * 0.35)))  # Deep stone recess
        jamb = max(18, min(32, depth - 2))        # Wide interior surfaces

        # Arch mask: opaque where opening exists
        hole = pygame.Surface((dw, dh), pygame.SRCALPHA)
        hole.fill((0, 0, 0, 0))
        if arch:
            body_top = int(dh * 0.36)
            pygame.draw.rect(hole, (255, 255, 255, 255), (0, body_top, dw, dh - body_top))
            pygame.draw.ellipse(hole, (255, 255, 255, 255), (0, 0, dw, body_top * 2))
        else:
            pygame.draw.rect(hole, (255, 255, 255, 255), (0, 0, dw, dh))

        fill = pygame.Surface((dw, dh), pygame.SRCALPHA)
        fill.fill(throat)
        fill.blit(hole, (0, 0), special_flags=pygame.BLEND_RGBA_MULT)
        surf.blit(fill, (dx, dy))

        # Left reveal — warm stone matching facade (lit edge of wall thickness)
        for i in range(jamb):
            t = i / max(1, jamb - 1)
            col = (
                int(160 * (1 - t) + 70 * t),
                int(140 * (1 - t) + 58 * t),
                int(120 * (1 - t) + 55 * t),
                alpha,
            )
            strip = pygame.Surface((1, dh), pygame.SRCALPHA)
            strip.fill(col)
            strip.blit(hole, (-i, 0), special_flags=pygame.BLEND_RGBA_MULT)
            surf.blit(strip, (dx + i, dy))
        edge = pygame.Surface((1, dh), pygame.SRCALPHA)
        edge.fill((210, 195, 170, alpha))
        edge.blit(hole, (0, 0), special_flags=pygame.BLEND_RGBA_MULT)
        surf.blit(edge, (dx, dy))

        # Right reveal — shadowed warm stone
        for i in range(jamb):
            t = i / max(1, jamb - 1)
            col = (
                int(55 * (1 - t) + 18 * t),
                int(42 * (1 - t) + 12 * t),
                int(38 * (1 - t) + 14 * t),
                alpha,
            )
            strip = pygame.Surface((1, dh), pygame.SRCALPHA)
            strip.fill(col)
            strip.blit(hole, (-(dw - 1 - i), 0), special_flags=pygame.BLEND_RGBA_MULT)
            surf.blit(strip, (dx + dw - 1 - i, dy))

        # Top soffit
        soff_n = max(3, depth // 2)
        for i in range(soff_n):
            shade = 24 + i * 6
            col = (shade + 8, shade, shade - 2, alpha)
            band = pygame.Surface((dw, 1), pygame.SRCALPHA)
            band.fill(col)
            band.blit(hole, (0, -i), special_flags=pygame.BLEND_RGBA_MULT)
            surf.blit(band, (dx, dy + i))

        # Mortar cut-line only (no surround plate)
        if arch:
            pygame.draw.arc(
                surf, (70, 58, 48, alpha),
                (dx, dy, dw, int(dh * 0.70)),
                0.08, math.pi - 0.08, 2,
            )

        # Door leaf deep inside — leave visible throat margin
        inset_x = max(4, jamb + 2)
        inset_y = max(4, soff_n + 2)
        pdx = dx + inset_x
        pdy = dy + inset_y
        pdw = max(5, dw - inset_x * 2)
        pdh = max(6, dh - inset_y - 2)
        panel = (48, 32, 24, alpha)
        if arch:
            door_hole = pygame.Surface((pdw, pdh), pygame.SRCALPHA)
            bt = int(pdh * 0.32)
            pygame.draw.rect(door_hole, panel, (0, bt, pdw, pdh - bt))
            pygame.draw.ellipse(door_hole, panel, (0, 0, pdw, bt * 2))
            clip = pygame.Surface((pdw, pdh), pygame.SRCALPHA)
            clip.blit(hole, (-inset_x, -inset_y))
            door_hole.blit(clip, (0, 0), special_flags=pygame.BLEND_RGBA_MULT)
            surf.blit(door_hole, (pdx, pdy))
        else:
            pygame.draw.rect(surf, panel, (pdx, pdy, pdw, pdh))

        pygame.draw.line(surf, (28, 18, 14, alpha), (pdx + pdw // 2, pdy + 3), (pdx + pdw // 2, pdy + pdh - 3), 1)
        pygame.draw.circle(
            surf, (200, 170, 60, alpha),
            (int(pdx + pdw * 0.78), int(pdy + pdh * 0.55)),
            max(2, pdw // 12),
        )
        pygame.draw.rect(surf, (22, 18, 24, alpha), (dx + 3, dy + dh - 3, dw - 6, 3))

        if glow:
            gw, gh = max(1, pdw - 8), max(1, int(pdh * 0.32))
            g = pygame.Surface((gw, gh), pygame.SRCALPHA)
            pulse = glow if len(glow) == 4 else (*glow[:3], 60)
            pygame.draw.ellipse(g, pulse, g.get_rect())
            surf.blit(g, (pdx + 4, pdy + 3))
        return

    # Wood entrance with VERY DEEP recess and wide visible interior
    depth = max(28, min(45, int(dw * 0.4)))  # Match deep recess (40% of door width)
    jamb = max(16, min(28, depth - 4))       # Wide jamb interior surfaces
    frame = max(7, int(dw * 0.12))           # Prominent outer frame
    surround = (100, 78, 52)
    ox, oy = dx - frame - 2, dy - frame - 4
    ow, oh = dw + (frame + 2) * 2, dh + frame + 6
    pygame.draw.rect(surf, (*_shade(surround, -18), alpha), (ox, oy, ow, oh))
    lip = (150, 120, 85)
    pygame.draw.rect(surf, (*lip, alpha), (dx - frame, dy - frame - 2, dw + frame * 2, dh + frame + 2), max(2, frame // 2))
    pygame.draw.line(surf, (220, 195, 150, alpha), (dx - frame + 1, dy - frame), (dx + dw + frame - 1, dy - frame), 2)

    cavity = (8, 5, 6, alpha)
    pygame.draw.rect(surf, cavity, (dx - 1, dy - 1, dw + 2, dh + 1))

    left_lit = (175, 145, 105, alpha)
    left_mid = (120, 95, 68, alpha)
    for i in range(jamb):
        t = i / max(1, jamb - 1)
        col = tuple(int(left_lit[c] * (1 - t) + left_mid[c] * t) for c in range(3)) + (alpha,)
        pygame.draw.line(surf, col, (dx + i, dy), (dx + i, dy + dh - 1), 1)
    pygame.draw.line(surf, (230, 210, 170, alpha), (dx, dy), (dx, dy + dh - 1), 2)

    right_dark = (28, 18, 14, alpha)
    right_mid = (48, 36, 28, alpha)
    for i in range(jamb):
        t = i / max(1, jamb - 1)
        col = tuple(int(right_mid[c] * (1 - t) + right_dark[c] * t) for c in range(3)) + (alpha,)
        x = dx + dw - 1 - i
        pygame.draw.line(surf, col, (x, dy), (x, dy + dh - 1), 1)

    soffit = (40, 28, 20, alpha)
    for i in range(max(3, depth // 2)):
        pygame.draw.line(surf, soffit, (dx + jamb, dy + i), (dx + dw - jamb, dy + i), 1)
    lintel = (115, 88, 58)
    pygame.draw.rect(surf, (*lintel, alpha), (dx - frame, dy - frame - 2, dw + frame * 2, max(4, frame)))
    pygame.draw.line(surf, (200, 175, 130, alpha), (dx - frame + 2, dy - frame), (dx + dw + frame - 2, dy - frame), 2)

    inset = max(3, depth // 2)
    pdx = dx + inset
    pdy = dy + max(2, depth // 3)
    pdw = max(6, dw - inset * 2)
    pdh = max(8, dh - max(2, depth // 3))
    panel = (92, 62, 38, alpha)

    if arch:
        pygame.draw.rect(surf, panel, (pdx, pdy, pdw, pdh))
        arch_h = int(pdh * 0.34)
        for yy in range(pdy, pdy + arch_h):
            for xx in range(pdx, pdx + pdw):
                rel = (xx - pdx) / max(1, pdw - 1)
                top = pdy + int((1.0 - math.sin(max(0.0, min(1.0, rel)) * math.pi)) * arch_h)
                if yy < top:
                    surf.set_at((xx, yy), cavity)
        pygame.draw.arc(
            surf, (*lintel, alpha),
            (dx - 2, dy - max(4, depth // 2), dw + 4, int(dh * 0.55)),
            0.08, math.pi - 0.08, max(2, dw // 16),
        )
    else:
        pygame.draw.rect(surf, panel, (pdx, pdy, pdw, pdh))

    mid = (70, 48, 30, alpha)
    pygame.draw.line(surf, mid, (pdx + pdw // 2, pdy + 2), (pdx + pdw // 2, pdy + pdh - 2), 1)
    pygame.draw.line(surf, mid, (pdx + 2, pdy + pdh // 2), (pdx + pdw - 2, pdy + pdh // 2), 1)
    pygame.draw.circle(
        surf, (220, 185, 70, alpha),
        (int(pdx + pdw * 0.78), int(pdy + pdh * 0.52)),
        max(2, pdw // 12),
    )
    pygame.draw.rect(surf, (45, 34, 26, alpha), (dx - 2, dy + dh - 2, dw + 4, 4))
    pygame.draw.line(surf, (90, 70, 50, alpha), (dx, dy + dh - 1), (dx + dw, dy + dh - 1), 1)



def _fill_side_wall(surf, fr, sr_top, sr_bot, br, wood, alpha, flat, wall_tex=None):
    """Opaque parallelogram side using the SAME material texture as the front."""
    pts = [fr, sr_top, sr_bot, br]
    base = tuple(flat[:3])
    tex = wall_tex or ("wood_planks" if wood else "brick")
    # Textured fill matching the front facade, then darkened for side plane
    # Skip outline on shared front edge to avoid visible seam
    _fill_poly(surf, pts, tex, shade=-48, flat=_shade(base, -28), alpha=255, uv=(fr[0] * 3, fr[1]), outline=False)
    # Soft vertical AO toward the far (right) edge
    n = max(5, (br[1] - fr[1]) // 12)
    for i in range(1, n):
        t = i / n
        x0 = fr[0] + (br[0] - fr[0]) * t
        y0 = fr[1] + (br[1] - fr[1]) * t
        x1 = sr_top[0] + (sr_bot[0] - sr_top[0]) * t
        y1 = sr_top[1] + (sr_bot[1] - sr_top[1]) * t
        pygame.draw.line(surf, (18, 12, 10) if wood else (22, 20, 26), (x0, y0), (x1, y1), 1)
    # Depth studs / mortar columns
    cols = 3 if wood else 4
    for i in range(1, cols):
        t = i / cols
        x0 = fr[0] + (sr_top[0] - fr[0]) * t
        y0 = fr[1] + (sr_top[1] - fr[1]) * t
        x1 = br[0] + (sr_bot[0] - br[0]) * t
        y1 = br[1] + (sr_bot[1] - br[1]) * t
        pygame.draw.line(surf, (14, 10, 8) if wood else (18, 16, 22), (x0, y0), (x1, y1), 1)
    # External edge outline only (not the shared front edge)
    pygame.draw.line(surf, (14, 10, 8), sr_top, sr_bot, 1)
    pygame.draw.line(surf, (14, 10, 8), sr_bot, br, 1)
    pygame.draw.line(surf, (14, 10, 8), sr_top, fr, 1)
    # Lit top bevel on external edge
    pygame.draw.line(surf, (200, 185, 160) if wood else (165, 168, 175), fr, sr_top, 3)
    # Dark crease on front/side join (subtle, not a black gap)
    pygame.draw.line(surf, (40, 32, 24) if wood else (36, 38, 44), fr, br, 1)
    # Depth edge shadow
    pygame.draw.line(
        surf, (50, 40, 32) if wood else (44, 46, 52),
        (sr_top[0] - 1, sr_top[1] + 2), (sr_bot[0] - 1, sr_bot[1] - 2), 2,
    )


def draw_house_shell(
    dest,
    footprint: pygame.Rect,
    *,
    wood: bool = True,
    kind: str = "house",
    alpha: int = 255,
    chimney: bool = True,
    door: bool = True,
    door_frac: float = 0.5,
):
    """
    Sealed ¾-view house with ADDITIVE side depth.
    
    Front wall uses ~75% of footprint width, then side depth ADDS beyond that.
    Map can expand to accommodate the deeper geometry - prefer correct 3D over 
    fitting old footprint constraints.
    """
    # Never allow ghost walls — shell must seal the footprint
    alpha = 255
    fx, fy, fw, fh = footprint.x, footprint.y, footprint.w, footprint.h
    if fw < 8 or fh < 8:
        return

    # ADDITIVE DEPTH MODEL (not inset) - front stays full, depth adds beyond
    # Front wall: use 75% of footprint width for solid facade
    front_w = max(8, int(fw * 0.75))
    # Side depth: ADD 50% more depth for strong extrusion (extends beyond footprint)
    side_w = max(24, int(fw * 0.50))
    # TALL vertical rise for dramatic 3/4 view (40% of height)
    dy = max(22, int(fh * 0.40))

    wall_top = fy + int(fh * 0.12)
    ground = fy + fh
    wall_h = ground - wall_top

    # Front face - uses front_w
    fl = (fx, wall_top)
    fr = (fx + front_w, wall_top)
    br = (fx + front_w, ground)
    bl = (fx, ground)
    # Side face - extends BEYOND footprint by side_w for real depth
    sr_top = (fx + front_w + side_w, wall_top - dy)
    sr_bot = (fx + front_w + side_w, ground)
    # Side face ends at footprint right edge — no overhang into walkable tiles
    sr_top = (fx + fw, wall_top - dy)
    sr_bot = (fx + fw, ground)

    if kind == "smithy":
        wood = False
    wall_tex = "wood_planks" if wood else "brick"
    roof_tex = "roof_terracotta" if (wood and kind != "smithy") else "roof_slate"
    flat_wall = (148, 110, 72) if wood else (118, 120, 126)
    flat_roof = (150, 78, 48) if wood else (78, 82, 90)
    flat_side = _shade(flat_wall, -42)

    # Ground contact covering full building depth (front + additive side)
    total_w = front_w + side_w
    pygame.draw.ellipse(
        dest, (10, 8, 6, 90),
        (fx + total_w * 0.06, ground - 4, total_w * 0.88, max(6, fh * 0.07)),
    )
    for grow, a in ((4, 28), (1, 48)):
        pygame.draw.polygon(dest, (14, 10, 8, a), [
            (bl[0] - grow, ground),
            (sr_bot[0] + grow, ground),
            (sr_bot[0] + grow, ground + max(3, fh // 18)),
            (bl[0] - grow, ground + max(3, fh // 18)),
        ])

    # Side first (behind front join) — same wood/stone texture as front
    _fill_side_wall(dest, fr, sr_top, sr_bot, br, wood, alpha, flat_side, wall_tex=wall_tex)

    # Front wall — fully opaque textured, skip outline on shared edge
    front_pts = [fl, fr, br, bl]
    _fill_poly(dest, front_pts, wall_tex, shade=8, flat=flat_wall, alpha=255, uv=(fx, fy), outline=False)
    # External edges only
    pygame.draw.line(dest, (18, 12, 8), fl, bl, 1)
    pygame.draw.line(dest, (18, 12, 8), bl, br, 1)
    pygame.draw.line(dest, (18, 12, 8), fl, fr, 1)
    # Lighting and details
    _key_light(dest, pygame.Rect(fx, wall_top, front_w, wall_h), left=62, right=82, alpha=255)
    pygame.draw.line(dest, (240, 220, 180, 255) if wood else (205, 208, 214, 255),
                     (fx + 1, wall_top + 2), (fx + 1, ground - 3), max(3, fw // 45))
    # Subtle crease at front/side join
    pygame.draw.line(dest, (34, 26, 20, 160) if wood else (32, 34, 40, 160),
                     (fr[0] - 1, wall_top), (br[0] - 1, ground - 1), 1)
    _ao_band(dest, fr[0] - max(6, front_w // 14), wall_top, max(6, front_w // 12), wall_h, strength=110)

    # Foundation across full building width (front + side depth)
    found_h = max(7, int(fh * 0.09))
    found_y = ground - found_h
    found = (58, 46, 34) if wood else (46, 48, 54)
    total_w = front_w + side_w
    pygame.draw.rect(dest, (*found, 255), (fx - 2, found_y, total_w + 2, found_h + 1))
    pygame.draw.polygon(dest, (*_shade(found, -16), 255), [
        (fr[0], found_y),
        (sr_top[0], found_y - dy),
        sr_bot,
        br,
    ])
    pygame.draw.line(dest, (135, 112, 85, 255) if wood else (115, 117, 122, 255),
                     (fx - 1, found_y), (fx + front_w + side_w, found_y), 2)
    _ao_band(dest, fx, found_y - max(5, fh // 18), front_w + side_w, max(7, fh // 12), strength=100, falloff="up")

    # Dramatic roof covering full extruded depth (including additive side depth)
    overhang = max(10, int(front_w * 0.15))  # Larger eaves
    peak_h = max(28, int(fh * 0.50))  # Very tall peak
    pf = (fx + front_w // 2, wall_top - peak_h)
    # Back ridge extends to cover FULL depth (front_w + side_w)
    pb = (fx + front_w + side_w - 2, pf[1] - int(dy * 0.70))
    left_eave = (fx - overhang, wall_top)
    right_eave = (fx + front_w + max(6, overhang // 2), wall_top)
    right_back = (fx + front_w + side_w, wall_top - dy)
    soffit = max(10, int(fh * 0.12))

    _fill_poly(dest, [pf, pb, right_back, right_eave], roof_tex, shade=-70,
               flat=_shade(flat_roof, -55), alpha=255, uv=(fx + front_w + side_w, fy))
    pygame.draw.line(dest, (40, 28, 22, 200), pb, right_back, 2)

    _fill_poly(dest, [pf, left_eave, (left_eave[0] + 4, wall_top + soffit),
                      (pf[0], wall_top + soffit)], roof_tex, shade=18,
               flat=flat_roof, alpha=255, uv=(fx, fy))
    _fill_poly(dest, [pf, right_eave, (right_eave[0] - 4, wall_top + soffit),
                      (pf[0], wall_top + soffit)], roof_tex, shade=-8,
               flat=_shade(flat_roof, -12), alpha=255, uv=(fx + front_w // 2, fy))

    pygame.draw.line(dest, (255, 240, 205, 255), pf, pb, 3)
    pygame.draw.circle(dest, (255, 248, 220, 255), (int(pf[0]), int(pf[1])), 3)

    pygame.draw.polygon(dest, (26, 16, 12, 255), [
        (left_eave[0] + 3, wall_top + soffit),
        (right_eave[0] - 3, wall_top + soffit),
        (right_eave[0] - 6, wall_top + soffit + max(3, fh // 22)),
        (left_eave[0] + 6, wall_top + soffit + max(3, fh // 22)),
    ])

    cast_y = wall_top + soffit + 2
    _ao_band(dest, fx, cast_y, front_w, max(14, int(fh * 0.14)), strength=160)
    _ao_band(dest, fx + front_w // 10, cast_y, int(front_w * 0.8), max(10, int(fh * 0.10)), strength=75)
    pygame.draw.line(dest, (8, 4, 2, 200), (fx, cast_y), (fx + front_w, cast_y), 3)

    for i in range(4):
        t = (i + 1) / 5.0
        y_line = int(wall_top + soffit * t)
        inset = int(overhang * (1.0 - t) * 0.4)
        pygame.draw.line(
            dest, (40, 26, 18, 75),
            (left_eave[0] + 8 + inset, y_line),
            (right_eave[0] - 8 - inset, y_line), 1,
        )

    win_h = max(14, int(fh * 0.125))
    win_w = max(12, int(front_w * 0.12))
    win_y = cast_y + max(8, int(fh * 0.05))
    for frac in (0.12, 0.62):
        wx = fx + int(front_w * frac)
        if abs((wx + win_w / 2) - (fx + front_w / 2)) < front_w * 0.14:
            continue
        if win_y + win_h < ground - int(fh * 0.30):
            _window(dest, wx, win_y, win_w, win_h, wood=wood, alpha=255)

    if kind == "smithy":
        gx = fx + int(front_w * 0.70)
        gy = win_y
        pygame.draw.rect(dest, (20, 10, 6, 255), (gx - 3, gy - 3, win_w + 6, win_h + 6))
        pygame.draw.rect(dest, (255, 110, 28, 255), (gx + 1, gy + 1, win_w - 2, win_h - 2))
        pygame.draw.rect(dest, (255, 210, 70, 230), (gx + 3, gy + 3, win_w // 3, win_h // 3))

    if chimney and kind != "volcano":
        chw = max(10, front_w // 11)
        chh = max(16, int(fh * 0.28))
        chx = fx + int(front_w * (0.70 if kind != "smithy" else 0.78))
        chy = pf[1] + int(peak_h * 0.22)
        # Keep chimney within footprint
        chx = min(chx, fx + fw - chw - side_w // 2)
        pygame.draw.rect(dest, (108, 110, 116, 255), (chx, chy, chw, chh))
        pygame.draw.polygon(dest, (68, 70, 74, 255), [
            (chx + chw, chy),
            (min(fx + fw - 2, chx + chw + max(4, chw // 2)), chy - max(2, dy // 6)),
            (min(fx + fw - 2, chx + chw + max(4, chw // 2)), chy + chh - 4),
            (chx + chw, chy + chh),
        ])
        pygame.draw.rect(dest, (52, 54, 58, 255), (chx - 3, chy - 2, chw + 6, 7))
        pygame.draw.line(dest, (180, 182, 188, 255), (chx + 1, chy + 2), (chx + 1, chy + chh - 3), 2)

    if door:
        door_w = max(14, int(front_w * 0.16))
        door_h = max(22, int(fh * 0.36))
        # Position door within the front wall (not across full footprint including side depth)
        frac = max(0.12, min(0.88, float(door_frac)))
        ddx = int(fx + front_w * frac - door_w * 0.5)
        ddx = max(fx + 2, min(fx + front_w - door_w - 2, ddx))
        ddy = ground - door_h
        _door_cut(dest, ddx, ddy, door_w, door_h, wood=wood, alpha=255, arch=True)



def draw_crypt_shell(dest, footprint, alpha=255, door_frac: float = 0.5):
    """
    Void Sanctum / dungeon as ONE continuous extruded stone volume.

    ADDITIVE depth model: front wall uses ~75% of footprint, side depth ADDS
    beyond that for real extrusion. Map can expand to accommodate geometry.
    Recessed entrance carved INTO the front wall - never pasted in front.
    """
    alpha = 255
    fx, fy, fw, fh = footprint.x, footprint.y, footprint.w, footprint.h
    if fw < 8 or fh < 8:
        return

    # ADDITIVE DEPTH MODEL matching house shell
    # Front wall: 75% of footprint for solid stone facade
    front_w = max(8, int(fw * 0.75))
    # Side depth: ADD 50% beyond front for deep extrusion
    side_w = max(24, int(fw * 0.50))
    # TALL vertical rise for dramatic 3/4 view (40% of height)
    dy = max(22, int(fh * 0.40))

    wall_top = fy + int(fh * 0.12)
    ground = fy + fh
    wall_h = ground - wall_top

    fl = (fx, wall_top)
    fr = (fx + front_w, wall_top)
    br = (fx + front_w, ground)
    bl = (fx, ground)
    # Side extends BEYOND footprint for real depth
    sr_top = (fx + front_w + side_w, wall_top - dy)
    sr_bot = (fx + front_w + side_w, ground)

    wall_tex = "brick"
    flat_wall = (52, 48, 64)
    flat_side = _shade(flat_wall, -36)
    flat_roof = (36, 32, 48)
    flat_found = (28, 26, 34)

    # Ground contact covering full building depth (front + additive side)
    total_w = front_w + side_w
    pygame.draw.ellipse(
        dest, (8, 6, 12, 100),
        (fx + total_w * 0.05, ground - 4, total_w * 0.90, max(6, fh * 0.08)),
    )
    for grow, a in ((4, 32), (1, 55)):
        pygame.draw.polygon(dest, (10, 8, 14, a), [
            (bl[0] - grow, ground),
            (sr_bot[0] + grow, ground),
            (sr_bot[0] + grow, ground + max(3, fh // 18)),
            (bl[0] - grow, ground + max(3, fh // 18)),
        ])

    # Side wall first — continuous stone with front (shared fr/br edge)
    _fill_side_wall(dest, fr, sr_top, sr_bot, br, False, alpha, flat_side, wall_tex=wall_tex)
    # No heavy outline on shared edge - just a subtle crease
    pygame.draw.line(dest, (32, 28, 40, 140), fr, br, 1)
    pygame.draw.line(dest, (90, 75, 130, 120), fr, sr_top, 1)

    # Front facade - skip outline to avoid gap with side wall
    front_pts = [fl, fr, br, bl]
    _fill_poly(dest, front_pts, wall_tex, shade=-12, flat=flat_wall, alpha=255, uv=(fx, fy), outline=False)
    # External edges only (not shared edge with side)
    pygame.draw.line(dest, (18, 14, 24), fl, bl, 1)
    pygame.draw.line(dest, (18, 14, 24), bl, br, 1)
    pygame.draw.line(dest, (18, 14, 24), fl, fr, 1)
    # Lighting and details
    _key_light(dest, pygame.Rect(fx, wall_top, front_w, wall_h), left=40, right=95, alpha=255)
    pygame.draw.line(dest, (140, 130, 160, 255), (fx + 1, wall_top + 2), (fx + 1, ground - 3), max(3, total_w // 45))
    # Subtle join crease with side
    pygame.draw.line(dest, (28, 24, 36, 180), (fr[0] - 1, wall_top), (br[0] - 1, ground - 1), 1)
    _ao_band(dest, fr[0] - max(5, front_w // 16), wall_top, max(5, front_w // 14), wall_h, strength=90)

    # Violet ribbing on front (Void identity, not fake depth)
    for i in range(4):
        rx = fx + int(front_w * (0.16 + i * 0.20))
        if abs(rx - (fx + front_w * 0.5)) < front_w * 0.10:
            continue
        pygame.draw.line(dest, (55, 42, 85, 180), (rx, wall_top + 6), (rx, ground - 10), 2)

    # Foundation follows full building width (front + side depth)
    found_h = max(8, int(fh * 0.10))
    found_y = ground - found_h
    pygame.draw.rect(dest, (*flat_found, 255), (fx - 2, found_y, total_w + 2, found_h + 1))
    # Side foundation parallelogram — continuous with front base around the corner
    side_found = [
        (fr[0] - 1, found_y),
        (sr_bot[0], found_y - max(2, dy // 8)),
        sr_bot,
        (br[0], ground),
    ]
    pygame.draw.polygon(dest, (*_shade(flat_found, -18), 255), side_found)
    pygame.draw.line(dest, (95, 90, 110, 255), (fx - 1, found_y), (fr[0], found_y), 2)
    pygame.draw.line(dest, (70, 66, 82, 255), (fr[0], found_y), (sr_bot[0], found_y - max(2, dy // 8)), 2)
    _ao_band(dest, fx, found_y - max(5, fh // 18), total_w, max(7, fh // 12), strength=110, falloff="up")

    # Flat stone parapet roof spanning the extruded volume (front + side depth)
    rim_h = max(7, int(fh * 0.06))
    deck_y = wall_top - max(3, fh // 28)
    # Top deck: continuous plane over front + side depth
    deck = [
        (fx - 2, deck_y),
        (fx + front_w + 2, deck_y),
        (fx + front_w + side_w, deck_y - dy),
        (fx + max(6, side_w // 4), deck_y - dy - max(3, dy // 5)),
    ]
    _fill_poly(dest, deck, "roof_slate", shade=-55, flat=flat_roof, alpha=255, uv=(fx, fy))

    # Raised parapet — rises ABOVE the deck (not a stripe painted down the facade)
    front_rim = [
        (fx - 3, deck_y - rim_h),
        (fx + front_w + 3, deck_y - rim_h),
        (fx + front_w + 2, deck_y),
        (fx - 2, deck_y),
    ]
    _fill_poly(dest, front_rim, "brick", shade=-8, flat=_shade(flat_wall, -8), alpha=255, uv=(fx, fy - 40))
    side_rim = [
        (fx + front_w + 2, deck_y - rim_h),
        (fx + front_w + side_w, deck_y - dy - rim_h),
        (fx + front_w + side_w, deck_y - dy),
        (fx + front_w + 2, deck_y),
    ]
    _fill_poly(dest, side_rim, "brick", shade=-42, flat=_shade(flat_wall, -36), alpha=255, uv=(fx + front_w, fy))
    # Lit top edge of parapet
    pygame.draw.line(dest, (175, 168, 190, 230), (fx - 2, deck_y - rim_h), (fx + front_w + 2, deck_y - rim_h), 2)
    pygame.draw.line(dest, (120, 100, 155, 200), (fx + front_w + 2, deck_y - rim_h), (fx + front_w + side_w, deck_y - dy - rim_h), 2)
    # Underside cast onto facade
    _ao_band(dest, fx, wall_top, front_w, max(12, int(fh * 0.11)), strength=155)
    pygame.draw.line(dest, (6, 4, 10, 210), (fx, wall_top), (fx + front_w, wall_top), 2)

    # Gothic spike accents on parapet (style, not structure)
    for i in range(5):
        sx = fx + int(front_w * (0.12 + i * 0.19))
        base = deck_y - rim_h
        tip = base - (10 if i % 2 == 0 else 5)
        pygame.draw.polygon(dest, (150, 90, 230, 255), [
            (sx - 4, base + 1), (sx, tip), (sx + 4, base + 1),
        ])
        pygame.draw.line(dest, (220, 180, 255, 200), (sx, tip), (sx, tip + 3), 1)

    # Narrow violet windows (integrated into facade, clear of door)
    win_h = max(12, int(fh * 0.14))
    win_w = max(10, int(front_w * 0.10))
    win_y = wall_top + max(14, int(fh * 0.08))
    for frac in (0.14, 0.70):
        wx = fx + int(front_w * frac)
        if win_y + win_h < ground - int(fh * 0.32):
            pygame.draw.rect(dest, (12, 8, 20, 255), (wx - 3, win_y - 3, win_w + 6, win_h + 6))
            pygame.draw.rect(dest, (70, 72, 80, 255), (wx - 2, win_y - 2, win_w + 4, win_h + 4))
            pygame.draw.rect(dest, (8, 4, 14, 255), (wx, win_y, win_w, win_h))
            pygame.draw.rect(dest, (110, 50, 190, 255), (wx + 2, win_y + 2, win_w - 4, win_h - 4))
            pygame.draw.rect(dest, (190, 120, 255, 200), (wx + 3, win_y + 3, max(2, win_w // 3), max(2, win_h // 3)))

    # Recessed entrance — carved into front wall of THIS volume
    door_w = max(18, int(front_w * 0.20))
    door_h = max(28, int(fh * 0.40))
    # Position door within the front wall (not across full footprint including side depth)
    frac = max(0.12, min(0.88, float(door_frac)))
    ddx = int(fx + front_w * frac - door_w * 0.5)
    ddx = max(fx + 6, min(fx + front_w - door_w - 6, ddx))
    ddy = ground - door_h
    _recessed_entrance(
        dest, ddx, ddy, door_w, door_h,
        wood=False, stone=True, alpha=255, arch=True,
        glow=(90, 40, 160, 100),
    )


def draw_building_shell(dest, footprint, *, kind="house", material=None, style=0, alpha=255,
                        door_frac: float = 0.5):
    """Entry point used by bake + runtime."""
    if kind == "volcano":
        return False
    if kind == "crypt" or material == "dark_stone":
        draw_crypt_shell(dest, footprint, alpha=alpha, door_frac=door_frac)
        return True
    if kind == "castle":
        return False
    wood = (material or ("brick" if style % 2 else "wood")) != "brick"
    if kind == "smithy":
        wood = False
    draw_house_shell(
        dest, footprint,
        wood=wood, kind=kind, alpha=alpha,
        chimney=True, door=True, door_frac=door_frac,
    )
    return True
