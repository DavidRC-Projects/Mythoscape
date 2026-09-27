"""
World-space iso cottages — matches cottage_test_scene_iso.png / Panda prototype.

Camera orbits; buildings never billboard, mirror, or flip.
WORLD faces: FRONT=S, BACK=N, LEFT=W, RIGHT=E, TOP=roof.
Door is cut into the SOUTH wall (not a separate box in front).

See .cursor/rules/building-architecture.mdc
"""
from __future__ import annotations

import math

import pygame

import building_textures as btex

FACE_S, FACE_W, FACE_N, FACE_E = 0, 1, 2, 3

# Exact Panda cottage palette (cottage.py / cottage_test_scene_iso.png)
STONE = (158, 160, 165)
STONE_SIDE = (128, 130, 136)
STONE_DARK = (100, 102, 108)
FOUNDATION = (92, 94, 100)
TIMBER = (78, 52, 34)
TIMBER_DARK = (56, 36, 24)
ROOF = (128, 84, 52)
ROOF_DARK = (96, 60, 36)
BRICK = (148, 92, 72)
BRICK_LT = (172, 118, 92)
BRICK_DK = (108, 66, 50)
DOOR = (72, 46, 28)
DOOR_LT = (96, 64, 40)
DOOR_DK = (48, 30, 18)
WINDOW_GLASS = (155, 180, 190)
WINDOW_FRAME = (48, 34, 24)
CHIMNEY = (138, 140, 146)
CHIMNEY_CAP = (220, 222, 226)

# Material variants — same cottage geometry, recolored
WALL_WOOD = (168, 128, 82)
WALL_WOOD_SIDE = (138, 100, 62)
WALL_RED = (168, 92, 68)
WALL_RED_SIDE = (138, 72, 52)
WALL_DARK = (72, 74, 82)
WALL_DARK_SIDE = (52, 54, 60)
ROOF_SLATE = (78, 82, 90)
ROOF_SLATE_DARK = (52, 54, 60)


def visible_roles(yaw: int):
    """Camera yaw → which WORLD faces sit in screen front / right / left roles."""
    yaw = int(yaw) % 4
    return yaw, (yaw - 1) % 4, (yaw + 1) % 4, (yaw + 2) % 4


def _shade(rgb, d):
    return tuple(max(0, min(255, int(c) + d)) for c in rgb[:3])


def _materials(material: str | None, kind: str):
    """Iso cottage looks: stone (reference), wood, red_brick, dark_stone."""
    mat = (material or "stone").lower()
    if kind == "smithy" and mat in ("brick", "wood", "stone"):
        mat = "red_brick"
    if kind == "crypt" or mat in ("dark_stone", "basalt"):
        return {
            "wall": WALL_DARK, "wall_side": WALL_DARK_SIDE, "wall_dark": _shade(WALL_DARK, -16),
            "found": FOUNDATION, "roof": ROOF_SLATE, "roof_dark": ROOF_SLATE_DARK,
            "chimney": False, "tall": False,
            "wall_tex": "rock_scale", "roof_tex": "roof_slate", "tex_detail": 0.7,
        }
    if mat in ("brick", "red_brick"):
        return {
            "wall": WALL_RED, "wall_side": WALL_RED_SIDE, "wall_dark": _shade(WALL_RED, -20),
            "found": FOUNDATION, "roof": ROOF_SLATE, "roof_dark": ROOF_SLATE_DARK,
            "chimney": True, "tall": False,
            "wall_tex": "brick", "roof_tex": "roof_slate", "tex_detail": 0.92,
            "brick_overlay": True,
        }
    if mat == "wood":
        return {
            "wall": WALL_WOOD, "wall_side": WALL_WOOD_SIDE, "wall_dark": _shade(WALL_WOOD, -18),
            "found": FOUNDATION, "roof": ROOF, "roof_dark": ROOF_DARK,
            "chimney": True, "tall": False,
            "wall_tex": "wood_planks", "roof_tex": "roof_terracotta", "tex_detail": 0.68,
        }
    # stone / default — match cottage_test_scene_iso.png
    return {
        "wall": STONE, "wall_side": STONE_SIDE, "wall_dark": STONE_DARK,
        "found": FOUNDATION, "roof": ROOF, "roof_dark": ROOF_DARK,
        "chimney": True, "tall": kind == "castle",
        "wall_tex": "rock_scale", "roof_tex": "roof_terracotta", "tex_detail": 0.62,
    }


def _poly(surf, color, pts, outline=None, width=1):
    if len(pts) < 3:
        return
    pygame.draw.polygon(surf, color, pts)
    pygame.draw.polygon(surf, outline or _shade(color, -36), pts, width)


def _face(surf, pts, color, tex_name, detail=0.65, uv=(0, 0), brick_overlay=False):
    """Textured wall/roof face with flat-color fallback."""
    if len(pts) < 3:
        return
    # Brick: finer UV repeat so mortar courses read at cottage scale
    scale = 0.42 if brick_overlay else 1.0
    used = btex.fill_polygon_tinted(
        surf, pts, tex_name, color, uv_origin=uv, detail=detail, scale=scale,
    )
    if not used:
        _poly(surf, color, pts)
    else:
        pygame.draw.polygon(surf, _shade(color, -40), pts, 1)
    if brick_overlay:
        _brick_face_overlay(surf, pts, color)


def _brick_face_overlay(surf, pts, color):
    """Extra mortar courses + grain so brick walls read clearly at cottage scale."""
    xs = [int(p[0]) for p in pts]
    ys = [int(p[1]) for p in pts]
    minx, maxx = min(xs), max(xs)
    miny, maxy = min(ys), max(ys)
    w, h = maxx - minx, maxy - miny
    if w < 12 or h < 12:
        return
    # Clip mortar lines to the face via a temp mask
    temp = pygame.Surface((w, h), pygame.SRCALPHA)
    local = [(p[0] - minx, p[1] - miny) for p in pts]
    mask = pygame.Surface((w, h), pygame.SRCALPHA)
    pygame.draw.polygon(mask, (255, 255, 255, 255), local)
    mortar = (*_shade(color, -45)[:3], 110)
    course = max(6, h // 14)
    brick_w = max(8, w // 8)
    for row, yy in enumerate(range(2, h - 2, course)):
        pygame.draw.line(temp, mortar, (0, yy), (w, yy), 1)
        off = (brick_w // 2) if row % 2 else 0
        for xx in range(off, w, brick_w):
            pygame.draw.line(temp, mortar, (xx, yy), (xx, min(yy + course, h - 1)), 1)
    # Speckle within bounds
    dk = (*_shade(color, -28)[:3], 90)
    lt = (*_shade(color, 22)[:3], 70)
    for i in range(0, w * h // 40):
        xx = (i * 37 + minx * 3) % max(1, w - 1)
        yy = (i * 53 + miny * 5) % max(1, h - 1)
        col = dk if (i & 1) else lt
        temp.set_at((xx, yy), col)
    temp.blit(mask, (0, 0), special_flags=pygame.BLEND_RGBA_MULT)
    surf.blit(temp, (minx, miny))


def _project(footprint: pygame.Rect, *, tall: bool = False):
    """
    3/4 iso projector matching the Panda cottage test scene.

    Screen roles (yaw remaps which world face fills them):
      front = large face toward camera
      right = depth face to the right / up
      roof  = gable planes
    """
    fx, fy, fw, fh = footprint.x, footprint.y, footprint.w, footprint.h
    # Leave headroom above footprint for roof + chimney
    ground = fy + fh - max(2, fh // 40)
    # Side depth band (~28% of width) — readable 3/4 volume
    side_w = max(22, int(fw * 0.28))
    front_w = max(28, fw - side_w - max(4, fw // 40))
    ox = fx + max(2, fw // 50)
    # Wall top sits mid-rect; taller for castle
    wall_h = int(fh * (0.48 if tall else 0.42))
    wall_top = ground - wall_h
    # Depth lift of the far corner
    dy = max(16, int(fh * 0.22))

    fl = (ox, wall_top)
    fr = (ox + front_w, wall_top)
    br = (ox + front_w, ground)
    bl = (ox, ground)
    # Right face recedes up-right
    sr_top = (ox + front_w + side_w, wall_top - dy)
    sr_bot = (ox + front_w + side_w, ground - max(4, dy // 5))

    front_pts = [fl, fr, br, bl]
    right_pts = [fr, sr_top, sr_bot, br]

    # Gable peak over front midpoint; back peak over right ridge
    peak_h = max(26, int(fh * (0.36 if tall else 0.32)))
    overhang = max(6, front_w // 16)
    pf = (ox + front_w // 2, wall_top - peak_h)
    pb = (ox + front_w + side_w // 2, wall_top - peak_h - int(dy * 0.55))
    left_eave = (ox - overhang, wall_top + 3)
    right_eave = (ox + front_w + overhang, wall_top + 3)
    right_back = (ox + front_w + side_w + overhang // 2, wall_top - dy + 2)

    roof_near = [pf, left_eave, right_eave]          # front gable face
    roof_far = [pf, right_eave, right_back, pb]       # long roof slope

    return {
        "fx": fx, "fy": fy, "fw": fw, "fh": fh,
        "ox": ox, "front_w": front_w, "side_w": side_w,
        "wall_top": wall_top, "ground": ground, "dy": dy, "peak_h": peak_h,
        "fl": fl, "fr": fr, "br": br, "bl": bl,
        "sr_top": sr_top, "sr_bot": sr_bot,
        "front_pts": front_pts, "right_pts": right_pts,
        "pf": pf, "pb": pb,
        "left_eave": left_eave, "right_eave": right_eave, "right_back": right_back,
        "roof_near": roof_near, "roof_far": roof_far,
        "overhang": overhang,
    }


def _foundation(dest, v, found):
    fx, fw, ground, fh = v["fx"], v["fw"], v["ground"], v["fh"]
    h = max(6, int(fh * 0.07))
    y = ground - h
    pygame.draw.rect(dest, found, (fx + 2, y, fw - 4, h + 1))
    # Right foundation step
    fr, sr_bot = v["fr"], v["sr_bot"]
    _poly(dest, _shade(found, -14), [
        (fr[0], y), (sr_bot[0], y - max(2, v["dy"] // 10)), sr_bot, (fr[0], ground),
    ])
    pygame.draw.line(dest, _shade(found, 20), (fx + 2, y), (fx + fw - 4, y), 2)


def _timber_posts(dest, v):
    """Chunky corner posts like the Panda cottage."""
    fl, fr, bl, br = v["fl"], v["fr"], v["bl"], v["br"]
    sr_top, sr_bot = v["sr_top"], v["sr_bot"]
    beam = max(4, v["front_w"] // 28)
    for a, b in ((fl, bl), (fr, br)):
        pygame.draw.line(dest, TIMBER, a, b, beam)
    pygame.draw.line(dest, TIMBER, fr, sr_top, max(3, beam - 1))
    pygame.draw.line(dest, TIMBER, br, sr_bot, max(3, beam - 1))
    # Top plates
    pygame.draw.line(dest, TIMBER_DARK, fl, fr, max(3, beam - 1))
    pygame.draw.line(dest, TIMBER_DARK, fr, sr_top, max(3, beam - 1))
    pygame.draw.line(dest, TIMBER_DARK, bl, br, max(2, beam - 2))


def _window(surf, x, y, w, h):
    """Square leaded window — reference cottage style."""
    pygame.draw.rect(surf, (10, 8, 10), (x - 2, y - 2, w + 4, h + 4))
    pygame.draw.rect(surf, WINDOW_FRAME, (x - 1, y - 1, w + 2, h + 2))
    pygame.draw.rect(surf, WINDOW_GLASS, (x + 1, y + 1, w - 2, h - 2))
    # Cross mullion
    pygame.draw.line(surf, WINDOW_FRAME, (x + w // 2, y), (x + w // 2, y + h), 2)
    pygame.draw.line(surf, WINDOW_FRAME, (x, y + h // 2), (x + w, y + h // 2), 2)
    # Specular
    pygame.draw.rect(surf, (210, 230, 240), (x + 2, y + 2, max(2, w // 4), max(2, h // 4)))


def _brick_speckle(surf, x, y, w, h, base):
    """Fine grain / chip marks on a brick face."""
    if w < 3 or h < 3:
        return
    dk = _shade(base, -22)
    lt = _shade(base, 18)
    step = 3
    for i, yy in enumerate(range(y + 1, y + h - 1, step)):
        for j, xx in enumerate(range(x + 1, x + w - 1, step)):
            # Deterministic scatter from position (no RNG flicker)
            n = (xx * 17 + yy * 31 + i * 7 + j * 13) & 7
            if n == 0:
                pygame.draw.rect(surf, dk, (xx, yy, 1, 1))
            elif n == 1:
                pygame.draw.rect(surf, lt, (xx, yy, 1, 1))
            elif n == 2 and w > 5:
                pygame.draw.line(surf, dk, (xx, yy), (min(xx + 2, x + w - 2), yy), 1)


def _draw_brick_block(surf, x, y, w, h, base, mortar=(72, 58, 48)):
    """One brick with mortar lip and granular face detail."""
    if w < 2 or h < 2:
        return
    pygame.draw.rect(surf, mortar, (x, y, w, h))
    inset = 1 if min(w, h) > 4 else 0
    bx, by, bw, bh = x + inset, y + inset, w - inset * 2, h - inset - max(0, inset - 0)
    if bw < 1 or bh < 1:
        return
    # Slight per-brick tint from position
    tint = ((x * 3 + y * 5) % 17) - 8
    col = _shade(base, tint)
    pygame.draw.rect(surf, col, (bx, by, bw, bh))
    pygame.draw.line(surf, _shade(col, 20), (bx, by), (bx + bw - 1, by), 1)
    pygame.draw.line(surf, _shade(col, -18), (bx, by + bh - 1), (bx + bw - 1, by + bh - 1), 1)
    _brick_speckle(surf, bx, by, bw, bh, col)


def _entrance_arch(surf, x, y, w, h):
    """Brick arched entrance with an arched wooden door that fills the opening."""
    rim = max(5, w // 6)
    void = (18, 14, 16)
    mortar = (78, 62, 52)
    r = max(8, w // 2)
    body_top = y + r

    # ---- Brick jambs (stacked courses with grain) ----
    course = max(5, rim)
    for side in (0, 1):
        sx = x if side == 0 else x + w - rim
        yy = body_top
        row = 0
        while yy < y + h:
            bh = min(course, y + h - yy)
            # Alternate stretcher offset for running bond
            off = (course // 2) if (row % 2) else 0
            if off and rim > 6:
                _draw_brick_block(surf, sx, yy, rim, bh // 2, BRICK if side == 0 else BRICK_DK, mortar)
                _draw_brick_block(surf, sx, yy + bh // 2, rim, bh - bh // 2, BRICK_LT if side == 0 else BRICK, mortar)
            else:
                base = BRICK_LT if side == 0 else BRICK_DK
                _draw_brick_block(surf, sx, yy, rim, bh, base, mortar)
            yy += course
            row += 1

    # ---- Voussoir ring (arched brick head) ----
    # Outer brick arch mass
    pygame.draw.ellipse(surf, mortar, (x, y, w, r * 2))
    pygame.draw.ellipse(surf, BRICK, (x + 1, y + 1, w - 2, r * 2 - 2))
    # Individual wedge-ish bricks along the semicircle
    cx = x + w / 2
    cy = y + r
    outer_r = r - 1
    inner_r = max(4, r - rim)
    n_wedges = max(7, w // 8)
    for i in range(n_wedges):
        a0 = math.pi + (math.pi * i / n_wedges)
        a1 = math.pi + (math.pi * (i + 1) / n_wedges)
        am = (a0 + a1) * 0.5
        # Midpoint on outer ring for a small brick chip
        mx = int(cx + math.cos(am) * (outer_r + inner_r) * 0.5)
        my = int(cy + math.sin(am) * (outer_r + inner_r) * 0.5)
        bw = max(4, rim - 1)
        bh = max(3, rim // 2 + 1)
        tinted = BRICK_LT if i % 2 == 0 else BRICK
        if i % 3 == 0:
            tinted = BRICK_DK
        _draw_brick_block(surf, mx - bw // 2, my - bh // 2, bw, bh, tinted, mortar)
    # Keystone
    kx = x + w // 2 - max(3, rim // 2)
    _draw_brick_block(surf, kx, y + 1, max(6, rim), max(4, rim // 2 + 1), BRICK_LT, mortar)

    # Punch inner opening (arch)
    ix = x + rim
    iw = max(8, w - rim * 2)
    ir = max(5, iw // 2)
    iy = y + rim
    ibody = iy + ir
    pygame.draw.rect(surf, void, (ix, ibody, iw, max(4, h - rim - ir)))
    pygame.draw.ellipse(surf, void, (ix, iy, iw, ir * 2))

    # ---- Arched wooden door leaf (matches opening curve) ----
    leaf_m = max(1, rim // 5)
    lx = ix + leaf_m
    lw = max(8, iw - leaf_m * 2)
    lr = max(5, lw // 2)
    ly = iy + leaf_m
    thresh = max(2, rim // 2)
    body_y = ly + lr
    leaf_h = max(10, y + h - body_y - thresh)
    # Door silhouette = rect + half-ellipse (same language as the arch)
    pygame.draw.rect(surf, DOOR, (lx, body_y, lw, leaf_h))
    pygame.draw.ellipse(surf, DOOR, (lx, ly, lw, lr * 2))
    # Soft rim shade under the arch
    pygame.draw.arc(surf, DOOR_DK, (lx, ly, lw, lr * 2), math.pi, 2 * math.pi, 2)
    pygame.draw.line(surf, DOOR_DK, (lx, body_y), (lx, body_y + leaf_h - 1), 2)
    pygame.draw.line(surf, DOOR_LT, (lx + lw - 1, body_y), (lx + lw - 1, body_y + leaf_h - 1), 1)
    # Panels (body only — stay under the curve)
    pad = max(2, lw // 9)
    mid = lx + lw // 2
    top_panel_y = body_y + pad
    top_panel_h = max(6, leaf_h // 2 - pad)
    pygame.draw.rect(
        surf, DOOR_LT,
        (lx + pad, top_panel_y, max(4, mid - lx - pad * 2), top_panel_h), 1,
    )
    pygame.draw.rect(
        surf, DOOR_LT,
        (mid + pad // 2, top_panel_y, max(4, lx + lw - mid - pad * 2), top_panel_h), 1,
    )
    bot_y = body_y + leaf_h // 2 + pad // 2
    pygame.draw.rect(
        surf, DOOR_DK,
        (lx + pad, bot_y, max(4, lw - pad * 2), max(6, leaf_h // 2 - pad * 2)), 1,
    )
    pygame.draw.line(surf, DOOR_DK, (mid, top_panel_y), (mid, body_y + leaf_h - pad), 2)
    # Handle
    hx = lx + int(lw * 0.78)
    hy = body_y + leaf_h // 2
    pygame.draw.circle(surf, (36, 34, 32), (hx, hy), max(2, w // 18))
    pygame.draw.circle(surf, (80, 78, 70), (hx, hy), max(1, w // 28))
    # Threshold
    pygame.draw.rect(surf, (32, 24, 20), (ix, y + h - thresh, iw, thresh))
    pygame.draw.line(surf, mortar, (ix, y + h - thresh), (ix + iw, y + h - thresh), 1)


def _chimney(dest, v):
    pf, peak_h = v["pf"], v["peak_h"]
    ox, front_w, side_w = v["ox"], v["front_w"], v["side_w"]
    chw = max(8, front_w // 12)
    chh = max(14, int(v["fh"] * 0.14))
    chx = ox + front_w + max(2, side_w // 4) - chw // 2
    chy = pf[1] + int(peak_h * 0.35)
    pygame.draw.rect(dest, CHIMNEY, (chx, chy, chw, chh))
    pygame.draw.rect(dest, STONE_DARK, (chx + chw - 2, chy, 3, chh))
    pygame.draw.rect(dest, CHIMNEY_CAP, (chx - 2, chy - 3, chw + 4, 5))
    pygame.draw.ellipse(dest, (200, 202, 208), (chx + 1, chy - 9, max(4, chw - 2), 7))


def _decorate(dest, face, role, v, *, door_frac, door_width_frac, m):
    """Put door on SOUTH world face lined up with the entrance tiles."""
    if role == "front":
        ox, front_w = v["ox"], v["front_w"]
        fx, fw = v["fx"], v["fw"]
        wall_top, ground = v["wall_top"], v["ground"]
        wall_h = ground - wall_top
        win = max(10, front_w // 9)
        wy = wall_top + max(10, int(wall_h * 0.22))
        if face == FACE_S:
            frac = max(0.05, min(0.95, float(door_frac)))
            wfrac = max(0.08, min(0.5, float(door_width_frac)))
            # Map through full footprint so the door sits on the tile gap
            # (front_w is only ~70% of fw — using it alone shifts doors west).
            dw = max(14, int(fw * wfrac))
            dh = max(28, int(wall_h * 0.62))
            cx = fx + fw * frac
            dx = int(cx - dw / 2)
            dx = max(fx + 2, min(fx + fw - dw - 2, dx))
            left_win = ox + int(front_w * 0.18) - win // 2
            right_win = ox + int(front_w * 0.82) - win // 2
            if left_win + win < dx - 4:
                _window(dest, left_win, wy, win, win)
            if right_win > dx + dw + 4:
                _window(dest, right_win, wy, win, win)
            _entrance_arch(dest, dx, ground - dh, dw, dh)
        elif face == FACE_N:
            _window(dest, ox + int(front_w * 0.28) - win // 2, wy, win, win)
            _window(dest, ox + int(front_w * 0.72) - win // 2, wy, win, win)
        else:
            _window(dest, ox + front_w // 2 - win // 2, wy, win, win)
    elif role == "right":
        pts = v["right_pts"]
        xs = [p[0] for p in pts]
        ys = [p[1] for p in pts]
        x0, x1 = min(xs), max(xs)
        y0, y1 = min(ys), max(ys)
        bw, bh = max(8, x1 - x0), max(8, y1 - y0)
        if bw > 18 and face in (FACE_E, FACE_W, FACE_N, FACE_S):
            ww = max(8, bw // 4)
            wh = max(10, int(bh * 0.22))
            _window(dest, x0 + bw // 2 - ww // 2, y0 + int(bh * 0.28), ww, wh)


def _path_apron(dest, v, door_frac, door_width_frac=0.2):
    """Path stub under the south door, same centre as the entrance tiles."""
    fx, fw, ground = v["fx"], v["fw"], v["ground"]
    frac = max(0.05, min(0.95, float(door_frac)))
    wfrac = max(0.08, min(0.5, float(door_width_frac)))
    cx = int(fx + fw * frac)
    pw = max(10, int(fw * wfrac))
    ph = max(8, v["fh"] // 14)
    pygame.draw.rect(dest, (58, 40, 28), (cx - pw // 2, ground, pw, ph))
    pygame.draw.rect(dest, (40, 28, 20), (cx - pw // 2, ground, pw, ph), 1)


def draw_house_volume(
    dest, footprint: pygame.Rect, *, yaw: int = 0, door_frac: float = 0.5,
    door_width_frac: float = 0.22, material: str | None = "stone",
    kind: str = "house", cutaway: bool = False,
):
    """
    Draw one iso cottage into footprint.
    door_frac / door_width_frac line the painted door up with the tile entrance.
    cutaway=True omits the roof (player inside).
    """
    if footprint.w < 20 or footprint.h < 20:
        return

    m = _materials(material, kind)
    front, side_r, side_l, _back = visible_roles(yaw)
    v = _project(footprint, tall=m["tall"])

    pygame.draw.ellipse(
        dest, (12, 10, 8, 110),
        (v["fx"] + v["fw"] * 0.06, v["ground"] - 4, v["fw"] * 0.88, max(6, v["fh"] * 0.07)),
    )

    front_col = m["wall"] if front == FACE_S else (
        m["wall_side"] if front in (FACE_E, FACE_W) else _shade(m["wall"], -10)
    )
    right_col = m["wall_side"] if side_r in (FACE_E, FACE_W) else m["wall_dark"]
    if side_r == FACE_N:
        right_col = _shade(m["wall"], -14)

    detail = m.get("tex_detail", 0.65)
    wtex = m.get("wall_tex", "rock_scale")
    rtex = m.get("roof_tex", "roof_terracotta")
    brick_ov = bool(m.get("brick_overlay"))
    _face(dest, v["right_pts"], right_col, wtex, detail=detail, uv=(40, 20), brick_overlay=brick_ov)
    _face(dest, v["front_pts"], front_col, wtex, detail=detail, uv=(0, 0), brick_overlay=brick_ov)
    _timber_posts(dest, v)
    _foundation(dest, v, m["found"])

    if not cutaway:
        _face(dest, v["roof_far"], m["roof_dark"], rtex, detail=detail * 0.9, uv=(10, 30))
        _face(dest, v["roof_near"], m["roof"], rtex, detail=detail * 0.9, uv=(0, 0))
        pygame.draw.line(dest, TIMBER_DARK, v["pf"], v["pb"], 2)
        pygame.draw.line(
            dest, (20, 12, 8),
            (v["ox"], v["wall_top"] + 4), (v["ox"] + v["front_w"], v["wall_top"] + 4), 2,
        )
        if m["chimney"]:
            _chimney(dest, v)

    _decorate(
        dest, front, "front", v,
        door_frac=door_frac, door_width_frac=door_width_frac, m=m,
    )
    _decorate(
        dest, side_r, "right", v,
        door_frac=door_frac, door_width_frac=door_width_frac, m=m,
    )

    if front == FACE_S and not cutaway:
        _path_apron(dest, v, door_frac, door_width_frac)


def draw_farmhouse_volume(dest, footprint, *, yaw=0, door_frac=0.5, door_width_frac=0.22):
    draw_house_volume(
        dest, footprint, yaw=yaw, door_frac=door_frac,
        door_width_frac=door_width_frac, material="wood", kind="house",
    )


def _keep_battlements_rect(surf, x, y, w, color):
    """Chunky crenellations along the top of a square wall."""
    merlon_w = max(8, w // 9)
    merlon_h = max(10, merlon_w)
    gap = max(4, merlon_w // 3)
    # Walkway lip under merlons
    pygame.draw.rect(surf, _shade(color, 12), (x - 2, y - 3, w + 4, 5))
    pygame.draw.rect(surf, _shade(color, -30), (x - 2, y - 3, w + 4, 5), 1)
    xx = x
    while xx + merlon_w <= x + w:
        pygame.draw.rect(surf, color, (xx, y - merlon_h, merlon_w, merlon_h))
        pygame.draw.rect(surf, _shade(color, 18), (xx + 1, y - merlon_h + 1, merlon_w - 2, 3))
        pygame.draw.rect(surf, _shade(color, -28), (xx, y - merlon_h, merlon_w, merlon_h), 1)
        # Embrasure notch shadow
        pygame.draw.line(surf, (20, 18, 22), (xx + merlon_w, y - merlon_h + 2), (xx + merlon_w + gap, y - 2), 2)
        _brick_speckle(surf, xx, y - merlon_h, merlon_w, merlon_h, color)
        xx += merlon_w + gap


def _round_tower(surf, cx, ground, radius, shaft_h, wall, wall_side, wall_dk, wtex, detail):
    """Tall circular flanking tower — cylinder shaft, battlements, dark conical roof."""
    # Cylinder as rounded-rect (taller, less bulbous than a full ellipse)
    top = ground - shaft_h
    body = pygame.Rect(cx - radius, top + radius // 2, radius * 2, shaft_h - radius // 2)
    # Shaft fill
    pygame.draw.rect(surf, wall_side, body)
    pygame.draw.rect(surf, wall, (body.x + 2, body.y, int(body.w * 0.68), body.h))
    btex.fill_polygon_tinted(
        surf,
        [body.topleft, body.topright, body.bottomright, body.bottomleft],
        wtex, wall, detail=detail, scale=0.48,
    )
    # Round top & bottom caps
    pygame.draw.ellipse(surf, wall, (cx - radius, top, radius * 2, radius))
    pygame.draw.ellipse(surf, wall_side, (cx - radius + int(radius * 0.55), top, int(radius * 1.1), radius))
    btex.fill_polygon_tinted(
        surf,
        [(cx - radius, top + radius // 2), (cx, top), (cx + radius, top + radius // 2), (cx, top + radius)],
        wtex, wall, detail=detail, scale=0.5,
    )
    pygame.draw.ellipse(surf, _shade(wall_dk, -8), (cx - radius - 1, ground - 8, radius * 2 + 2, 12))
    pygame.draw.line(surf, wall_dk, (body.left, body.top), (body.left, body.bottom), 2)
    pygame.draw.line(surf, _shade(wall, 20), (body.left + 3, body.top), (body.left + 3, body.bottom - 4), 1)
    # Horizontal stone courses
    course = max(7, shaft_h // 10)
    for yy in range(body.top + course, body.bottom - 4, course):
        pygame.draw.line(surf, (*_shade(wall_dk, -10)[:3], 100), (body.left + 2, yy), (body.right - 2, yy), 1)
    # Arrow slits (cross-shaped)
    for frac in (0.35, 0.62):
        sy = top + int(shaft_h * frac)
        pygame.draw.rect(surf, (12, 10, 14), (cx - 2, sy, 4, max(12, shaft_h // 8)))
        pygame.draw.rect(surf, (12, 10, 14), (cx - 6, sy + max(4, shaft_h // 20), 12, 3))
        pygame.draw.rect(surf, WINDOW_FRAME, (cx - 7, sy - 1, 14, max(14, shaft_h // 8) + 2), 1)
    # Battlement ring
    merlon_w = max(4, radius // 4)
    merlon_h = max(7, radius // 3)
    n = max(8, radius // 3)
    for i in range(n):
        ang = 2 * math.pi * i / n - math.pi / 2
        if math.sin(ang) < -0.35:
            continue  # skip far-back merlons
        mx = int(cx + math.cos(ang) * (radius - 2))
        my = int(top + radius // 2 + math.sin(ang) * 3)
        pygame.draw.rect(surf, wall_dk, (mx - merlon_w // 2, my - merlon_h, merlon_w, merlon_h))
        pygame.draw.rect(surf, _shade(wall_dk, -22), (mx - merlon_w // 2, my - merlon_h, merlon_w, merlon_h), 1)
    # Dark conical roof
    roof = ROOF_SLATE_DARK
    peak = (cx, top - max(14, radius))
    pygame.draw.polygon(surf, roof, [
        peak,
        (cx - radius - 2, top + radius // 3),
        (cx + radius + 2, top + radius // 3),
    ])
    pygame.draw.polygon(surf, _shade(roof, 25), [
        peak,
        (cx - radius // 3, top + radius // 4),
        (cx - radius - 2, top + radius // 3),
    ])
    pygame.draw.polygon(surf, _shade(roof, -30), [peak, (cx - radius - 2, top + radius // 3), (cx + radius + 2, top + radius // 3)], 1)
    # Flagpole + banner
    pygame.draw.line(surf, (60, 50, 40), peak, (peak[0], peak[1] - 14), 2)
    ban = [(peak[0], peak[1] - 12), (peak[0] + 14, peak[1] - 8), (peak[0], peak[1] - 4)]
    pygame.draw.polygon(surf, (160, 40, 48), ban)
    pygame.draw.polygon(surf, (100, 24, 30), ban, 1)


def _castle_banner(surf, x, y, w, h, color=(160, 40, 48)):
    """Hanging heraldic banner."""
    pygame.draw.line(surf, (50, 40, 32), (x, y - 2), (x + w, y - 2), 2)
    pts = [(x, y), (x + w, y), (x + w, y + h - 6), (x + w // 2, y + h), (x, y + h - 6)]
    pygame.draw.polygon(surf, color, pts)
    pygame.draw.polygon(surf, _shade(color, -40), pts, 1)
    # Simple charge
    cx, cy = x + w // 2, y + h // 3
    pygame.draw.circle(surf, (220, 190, 80), (cx, cy), max(2, w // 5))
    pygame.draw.circle(surf, _shade(color, -20), (cx, cy), max(2, w // 5), 1)


def _portcullis(surf, x, y, w, h, *, open_amt=0.0):
    """Iron gate — fully hidden when standing in front / entering."""
    open_amt = max(0.0, min(1.0, float(open_amt)))
    if open_amt >= 0.9:
        return
    lift = int(h * open_amt * 0.95)
    bar_col = (42, 44, 50)
    bar_lt = (70, 74, 82)
    gy = y - lift
    gap = max(6, w // 8)
    for bx in range(x + 3, x + w - 3, gap):
        pygame.draw.line(surf, bar_col, (bx, max(y, gy)), (bx, y + h - 2), 3)
        pygame.draw.line(surf, bar_lt, (bx - 1, max(y, gy)), (bx - 1, y + h - 2), 1)
    for i, fy in enumerate(range(max(y + 6, gy + 6), y + h - 4, max(10, h // 5))):
        pygame.draw.line(surf, bar_col, (x + 2, fy), (x + w - 3, fy), 3)
        if i == 0 and open_amt < 0.5:
            pygame.draw.circle(surf, (30, 30, 32), (x + w // 2, fy), max(4, w // 16))
            pygame.draw.circle(surf, (90, 90, 70), (x + w // 2, fy), max(2, w // 22), 1)


def draw_interior_outline(
    dest, footprint: pygame.Rect, *, material: str | None = "stone",
    kind: str = "house", door_frac: float = 0.5, door_width_frac: float = 0.22,
):
    """
    Wall outline of the building footprint — only drawn while the player is inside.
    Leaves the south entrance gap open.
    """
    if footprint.w < 16 or footprint.h < 16:
        return
    m = _materials(material, kind or "house")
    fx, fy, fw, fh = footprint.x, footprint.y, footprint.w, footprint.h
    # Indoor outline hugs the floor rectangle (inset from outer footprint)
    inset = max(4, min(fw, fh) // 16)
    x0, y0 = fx + inset, fy + inset
    x1, y1 = fx + fw - inset, fy + fh - inset
    thick = max(3, min(fw, fh) // 28)
    col = m["wall_dark"]
    col_lt = m["wall"]
    # North, west, east walls
    pygame.draw.rect(dest, col, (x0, y0, x1 - x0, thick))
    pygame.draw.rect(dest, col_lt, (x0, y0, thick, y1 - y0))
    pygame.draw.rect(dest, col, (x1 - thick, y0, thick, y1 - y0))
    # South wall with door gap
    frac = max(0.15, min(0.85, float(door_frac)))
    wfrac = max(0.1, min(0.45, float(door_width_frac)))
    gap_w = max(thick * 3, int((x1 - x0) * wfrac))
    gap_cx = int(x0 + (x1 - x0) * frac)
    gap_l = max(x0 + thick, gap_cx - gap_w // 2)
    gap_r = min(x1 - thick, gap_cx + gap_w // 2)
    # Left and right south segments
    if gap_l > x0 + thick:
        pygame.draw.rect(dest, col, (x0, y1 - thick, gap_l - x0, thick))
    if gap_r < x1 - thick:
        pygame.draw.rect(dest, col, (gap_r, y1 - thick, x1 - gap_r, thick))
    # Corner posts
    for px, py in ((x0, y0), (x1 - thick, y0), (x0, y1 - thick), (x1 - thick, y1 - thick)):
        pygame.draw.rect(dest, TIMBER_DARK, (px, py, thick, thick))
    # Soft inner lip so the outline reads as walls
    lip = (*_shade(col, 30)[:3], 90)
    pygame.draw.rect(dest, lip, (x0 + thick, y0 + thick, x1 - x0 - thick * 2, y1 - y0 - thick * 2), 1)


def draw_keep_volume(
    dest, footprint: pygame.Rect, *, yaw: int = 0, door_frac: float = 0.5,
    door_width_frac: float = 0.22, material: str | None = "stone",
    cutaway: bool = False, gate_open: float = 0.0,
):
    """
    Castle: square curtain wall + large gate + two tall circular towers.
    Portcullis disappears when standing in front.
    """
    if footprint.w < 24 or footprint.h < 24:
        return
    m = _materials(material or "stone", "castle")
    fx, fy, fw, fh = footprint.x, footprint.y, footprint.w, footprint.h
    ground = fy + fh - max(2, fh // 50)
    wall = m["wall"]
    wall_side = m["wall_side"]
    wall_dk = m["wall_dark"]
    detail = m.get("tex_detail", 0.7)
    wtex = m.get("wall_tex", "rock_scale")

    layer = pygame.Surface((fw + 16, fh + 20), pygame.SRCALPHA)
    ox, oy = fx - 8, fy - 10
    lground = ground - oy

    # Layout — taller towers, wider curtain wall
    tower_r = max(22, int(min(fw, fh) * 0.15))
    shaft_h = int(fh * 0.62)
    body_w = max(64, int(fw * 0.55))
    body_h = int(fh * 0.48)
    body_x = (fw + 16 - body_w) // 2
    body_top = lground - body_h - max(6, fh // 35)
    left_cx = max(tower_r + 4, body_x - tower_r + max(8, tower_r // 4))
    right_cx = min(fw + 12 - tower_r, body_x + body_w + tower_r - max(8, tower_r // 4))

    # Contact shadow
    pygame.draw.ellipse(
        layer, (12, 10, 8, 120),
        (left_cx - tower_r, lground - 6, right_cx - left_cx + tower_r * 2, max(10, fh // 12)),
    )

    # ---- Curtain wall (square front) ----
    body = pygame.Rect(body_x, body_top, body_w, body_h)
    depth = max(16, int(fw * 0.09))
    right_pts = [
        (body.right, body.top),
        (body.right + depth, body.top - depth // 2),
        (body.right + depth, body.bottom - depth // 2),
        (body.right, body.bottom),
    ]
    _face(layer, right_pts, wall_side, wtex, detail=detail, uv=(30, 10))
    front_pts = [body.topleft, body.topright, body.bottomright, body.bottomleft]
    _face(layer, front_pts, wall, wtex, detail=detail, uv=(0, 0))
    # Mortar courses across the curtain
    course = max(8, body_h // 12)
    for yy in range(body.top + course, body.bottom - 4, course):
        pygame.draw.line(
            layer, (*_shade(wall_dk, -5)[:3], 90),
            (body.left + 3, yy), (body.right - 3, yy), 1,
        )
    pygame.draw.rect(layer, wall_dk, body, 2)
    # Corbel / machicolation line under parapet
    pygame.draw.rect(layer, wall_dk, (body.x - 3, body.top - 2, body.w + 6, 6))
    for cxb in range(body.x + 4, body.right - 4, max(8, body_w // 10)):
        pygame.draw.rect(layer, _shade(wall_dk, -15), (cxb, body.top + 2, 4, 5))
    # Battlements
    _keep_battlements_rect(layer, body.x + 2, body.top, body.w - 4, wall_dk)
    pygame.draw.line(layer, wall_dk, right_pts[0], right_pts[1], 3)

    # Upper lancet windows (taller, castle-like)
    win_w = max(8, body_w // 16)
    win_h = max(14, int(body_h * 0.16))
    for wx in (body.x + int(body_w * 0.18), body.x + int(body_w * 0.82) - win_w):
        wy = body.top + int(body_h * 0.22)
        pygame.draw.rect(layer, (10, 8, 12), (wx - 2, wy - 2, win_w + 4, win_h + 6))
        pygame.draw.rect(layer, WINDOW_FRAME, (wx - 1, wy - 1, win_w + 2, win_h + 2))
        pygame.draw.rect(layer, WINDOW_GLASS, (wx + 1, wy + 1, win_w - 2, win_h - 2))
        pygame.draw.ellipse(layer, WINDOW_GLASS, (wx, wy - win_w // 2, win_w, win_w))
        pygame.draw.line(layer, WINDOW_FRAME, (wx + win_w // 2, wy), (wx + win_w // 2, wy + win_h), 2)

    # Heraldic banners flanking the gate
    ban_w = max(10, body_w // 14)
    ban_h = max(28, int(body_h * 0.28))
    _castle_banner(layer, body.x + int(body_w * 0.08), body.top + int(body_h * 0.32), ban_w, ban_h)
    _castle_banner(layer, body.right - int(body_w * 0.08) - ban_w, body.top + int(body_h * 0.32), ban_w, ban_h)

    # ---- Large south gate (~60% of curtain width) ----
    gw = max(64, int(body_w * 0.58))
    gh = max(64, int(body_h * 0.82))
    gx = body.centerx - gw // 2
    gx = max(body.x + 6, min(body.right - gw - 6, gx))
    gy = body.bottom - gh
    rim = max(8, gw // 11)
    # Gatehouse projection (slight step forward)
    proj = max(4, gw // 16)
    pygame.draw.rect(layer, wall_dk, (gx - proj - 2, gy - 4, gw + proj * 2 + 4, gh + 6))
    pygame.draw.rect(layer, wall, (gx - proj, gy - 2, gw + proj * 2, gh + 2))
    btex.fill_polygon_tinted(
        layer,
        [(gx - proj, gy - 2), (gx + gw + proj, gy - 2),
         (gx + gw + proj, gy + gh), (gx - proj, gy + gh)],
        wtex, wall, detail=detail, scale=0.45,
    )
    # Brick arch surround (thick)
    r = max(14, gw // 2)
    pygame.draw.rect(layer, BRICK, (gx, gy + r, gw, gh - r))
    pygame.draw.ellipse(layer, BRICK, (gx, gy, gw, r * 2))
    for side in (0, 1):
        sx = gx if side == 0 else gx + gw - rim
        yy = gy + r
        while yy < gy + gh:
            bh = min(rim, gy + gh - yy)
            _draw_brick_block(layer, sx, yy, rim, bh, BRICK_LT if side == 0 else BRICK_DK)
            yy += rim
    # Voussoirs across the arch
    for i in range(7):
        t = (i + 0.5) / 7
        ang = math.pi + math.pi * t
        mx = int(gx + gw / 2 + math.cos(ang) * (gw / 2 - rim / 2))
        my = int(gy + r + math.sin(ang) * (r - rim / 2))
        _draw_brick_block(layer, mx - rim // 2, my - rim // 3, rim, max(4, rim // 2),
                          BRICK_LT if i % 2 == 0 else BRICK)
    kx = gx + gw // 2 - rim // 2
    _draw_brick_block(layer, kx, gy + 2, rim, max(5, rim // 2 + 2), BRICK_LT)
    # Torch sconces beside the arch
    for tx in (gx - proj - 6, gx + gw + proj + 2):
        pygame.draw.rect(layer, (50, 40, 30), (tx, gy + int(gh * 0.35), 5, 10))
        pygame.draw.circle(layer, (255, 160, 60), (tx + 2, gy + int(gh * 0.35) - 2), 4)
        pygame.draw.circle(layer, (255, 220, 120), (tx + 2, gy + int(gh * 0.35) - 3), 2)
    # Punch transparent gate opening
    ix, iy = gx + rim, gy + rim
    iw = max(16, gw - rim * 2)
    ir = max(8, iw // 2)
    clear = (0, 0, 0, 0)
    pygame.draw.rect(layer, clear, (ix, iy + ir, iw, max(6, gh - rim - ir)))
    pygame.draw.ellipse(layer, clear, (ix, iy, iw, ir * 2))
    # Threshold
    pygame.draw.rect(layer, (40, 36, 34), (ix, gy + gh - 4, iw, 4))
    if not cutaway:
        _portcullis(layer, ix, iy + ir // 5, iw, gh - rim - ir // 5, open_amt=gate_open)

    # ---- Twin circular towers ----
    _round_tower(
        layer, left_cx, lground, tower_r, shaft_h,
        wall, wall_side, wall_dk, wtex, detail,
    )
    _round_tower(
        layer, right_cx, lground, tower_r, shaft_h,
        wall, wall_side, wall_dk, wtex, detail,
    )

    dest.blit(layer, (ox, oy))


def draw_world_volume(
    dest, footprint, *, kind="house", yaw=0, door_frac=0.5, door_width_frac=0.22,
    material=None, cutaway=False, gate_open: float = 0.0, interior_outline: bool = False,
):
    """Client entry — cottages / castle keep; optional indoor wall outline."""
    if kind == "volcano":
        return False
    mat = material if material is not None else "stone"
    if interior_outline:
        draw_interior_outline(
            dest, footprint, material=mat, kind=kind or "house",
            door_frac=door_frac, door_width_frac=door_width_frac,
        )
        return True
    if kind == "castle":
        draw_keep_volume(
            dest, footprint, yaw=yaw, door_frac=door_frac,
            door_width_frac=door_width_frac, material=mat,
            cutaway=cutaway, gate_open=gate_open,
        )
        return True
    draw_house_volume(
        dest, footprint, yaw=yaw, door_frac=door_frac,
        door_width_frac=door_width_frac,
        material=mat, kind=kind or "house", cutaway=cutaway,
    )
    return True
