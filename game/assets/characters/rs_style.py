"""
Stylized low-poly fantasy visual language for Mythoscape.

Procedural pygame primitives only. Emphasizes form, directional light,
material values, cast shadows, and controlled silhouette variation —
not decorative noise or extra polygons for their own sake.
"""
from __future__ import annotations

import math
import pygame

TAU = math.pi * 2

# ---------------------------------------------------------------------------
# Global scale — early-2000s fantasy MMORPG proportions
# ---------------------------------------------------------------------------
TILE_SIZE = 40

ART_SCALE = 1.0
CHARACTER_SCALE = 2.5
OBJECT_SCALE = 2.55
MONSTER_SCALE = 2.5
PET_SCALE = 2.05
BUILDING_SCALE = 1.0
TREE_SCALE = 1.72

_SCALE_MIN, _SCALE_MAX = 0.6, 4.0


def set_scales(*, art=None, character=None, object_=None, monster=None, pet=None, tile_size=None, tree=None):
    global ART_SCALE, CHARACTER_SCALE, OBJECT_SCALE, MONSTER_SCALE, PET_SCALE, TILE_SIZE, TREE_SCALE
    if art is not None:
        ART_SCALE = _clamp(float(art), _SCALE_MIN, _SCALE_MAX)
    if character is not None:
        CHARACTER_SCALE = _clamp(float(character), 1.0, 5.0)
    if object_ is not None:
        OBJECT_SCALE = _clamp(float(object_), 1.0, 5.0)
    if monster is not None:
        MONSTER_SCALE = _clamp(float(monster), 1.0, 5.0)
    if pet is not None:
        PET_SCALE = _clamp(float(pet), 0.8, 4.0)
    if tile_size is not None:
        TILE_SIZE = max(24, int(tile_size))
    if tree is not None:
        TREE_SCALE = _clamp(float(tree), 1.0, 3.0)


def _clamp(v, lo, hi):
    return max(lo, min(hi, v))


def unit(tile, kind="character"):
    """Pixels per design-unit for a given art category."""
    base = (tile / 32.0) * ART_SCALE
    mult = {
        "character": CHARACTER_SCALE,
        "object": OBJECT_SCALE,
        "monster": MONSTER_SCALE,
        "pet": PET_SCALE,
        "building": BUILDING_SCALE,
        "terrain": 1.0,
    }.get(kind, CHARACTER_SCALE)
    return base * mult


def label_lift(tile, kind="character"):
    """Pixels above entity foot-anchor (cy) to clear the head for HP bars."""
    s = unit(tile, kind)
    # Characters: head top ~15.5s; leave a gap for the bar itself.
    mult = {
        "character": 18.0,
        "monster": 16.5,
        "pet": 13.0,
    }.get(kind, 16.0)
    return int(mult * s)


# ---------------------------------------------------------------------------
# Limited material palettes (base, mid/shadow, highlight, outline)
# ---------------------------------------------------------------------------
GRASS_PALETTE = ((52, 98, 48), (38, 74, 36), (72, 118, 58), (24, 44, 22))
DIRT_PALETTE = ((128, 100, 68), (100, 76, 50), (152, 122, 86), (58, 42, 28))
STONE_PALETTE = ((108, 104, 112), (76, 72, 82), (142, 138, 148), (34, 32, 40))
WOOD_PALETTE = ((112, 74, 40), (82, 52, 26), (146, 104, 58), (40, 26, 14))
METAL_PALETTE = ((160, 160, 170), (100, 100, 112), (210, 210, 220), (40, 40, 48))
SKIN_PALETTE = ((216, 172, 132), (180, 134, 96), (240, 204, 168), (68, 46, 32))
CLOTH_PALETTE = ((66, 104, 158), (46, 74, 112), (104, 142, 188), (26, 34, 48))
FOLIAGE_PALETTE = ((40, 100, 44), (26, 72, 30), (68, 136, 56), (16, 38, 18))
WATER_PALETTE = ((40, 92, 142), (26, 66, 110), (84, 150, 180), (16, 44, 72))
BONE_PALETTE = ((228, 220, 200), (180, 172, 150), (248, 242, 228), (70, 64, 52))
FIRE_PALETTE = ((220, 100, 30), (160, 50, 16), (255, 200, 70), (80, 24, 10))

OUTLINE = (22, 18, 14)

# ---------------------------------------------------------------------------
# Coherent lighting — upper-left key light (screen: +x right, +y down)
# ---------------------------------------------------------------------------
LIGHT_DIR = (-0.58, -0.81)  # toward the light
AMBIENT = 0.38
DIRECT = 0.62


def shade(color, delta):
    return tuple(max(0, min(255, c + delta)) for c in color[:3])


def lerp_color(a, b, t):
    t = max(0.0, min(1.0, t))
    return tuple(int(a[i] + (b[i] - a[i]) * t) for i in range(3))


def material(base):
    """Return (highlight, mid, shade, deep) — 4 deliberate values."""
    mid = tuple(int(c) for c in base[:3])
    hi = shade(mid, 48)
    sh = shade(mid, -42)
    deep = shade(mid, -78)
    return hi, mid, sh, deep


def lit_from_normal(base, nx, ny, ambient=None, strength=None):
    """Shade a base color by a screen-space surface normal."""
    ambient = AMBIENT if ambient is None else ambient
    strength = DIRECT if strength is None else strength
    lx, ly = LIGHT_DIR
    length = math.hypot(nx, ny) or 1.0
    nx, ny = nx / length, ny / length
    ndotl = max(0.0, nx * lx + ny * ly)
    t = ambient + strength * ndotl
    hi, mid, sh, deep = material(base)
    if t >= 0.72:
        return lerp_color(mid, hi, (t - 0.72) / 0.28)
    if t >= 0.45:
        return lerp_color(sh, mid, (t - 0.45) / 0.27)
    return lerp_color(deep, sh, t / 0.45)


def seeded(x, y, salt=0):
    n = (int(x) * 92821 + int(y) * 68917 + int(salt) * 2311) & 0xFFFFFFFF
    n = (n ^ (n >> 13)) * 1274126177 & 0xFFFFFFFF
    return (n % 10000) / 10000.0


def seeded_range(x, y, salt, lo, hi):
    return lo + (hi - lo) * seeded(x, y, salt)


def irregular_ring(cx, cy, rx, ry, n=8, seed=0, jitter=0.28, phase=0.0):
    """Controlled irregular closed silhouette (never a perfect ellipse)."""
    pts = []
    for i in range(n):
        ang = phase + TAU * i / n
        # Neighbor-correlated jitter keeps silhouette organic but stable
        r = 0.72 + 0.28 * seeded(seed, i, 3) + jitter * (seeded(seed, i, 9) - 0.5)
        # Slight flattening on underside for ground-contact masses
        yy = math.sin(ang)
        if yy > 0.35:
            r *= 0.92
        pts.append((cx + math.cos(ang) * rx * r, cy + yy * ry * r))
    return pts


def guess_surface_detail(base, hint=None):
    """Pick a photo texture key for a fill color / material hint."""
    if hint is False or hint == "flat" or hint == "none":
        return None
    if hint:
        return hint
    r, g, b = (int(c) for c in base[:3])
    mx, mn = max(r, g, b), min(r, g, b)
    sat = mx - mn
    # Cool near-white (husky fur) vs warm bone
    if sat < 35 and mx > 200:
        return "fur" if b >= g - 2 else "rock_scale"
    # Skin / flesh tones
    if r > 150 and g > 100 and b > 70 and r >= g and g >= b - 20 and sat < 120:
        return "skin"
    # Cool / warm greys → metal
    if sat < 28 and mx > 90:
        return "metal_armor"
    # Greens (orc/slime) → bark/mossy
    if g > r + 15 and g > b + 10:
        return "bark"
    # Browns → leather / fur
    if r > 70 and g > 40 and b < g and r >= g and sat > 20:
        if mx < 140:
            return "fur"
        return "leather"
    # Bright cloth colors
    if sat > 40:
        return "cloth"
    return "fabric"


def draw_volume(surf, base, pts, outline=OUTLINE, width=1, detail=None):
    """
    Filled polygon with directional volume:
    mid fill + lower-right shade + upper-left highlight facet.
    Optional photo `detail` texture (or auto-guess from color).
    """
    if len(pts) < 3:
        return
    hi, mid, sh, deep = material(base)
    ip = [(int(p[0]), int(p[1])) for p in pts]
    tex_name = guess_surface_detail(base, detail)
    textured = False
    if tex_name:
        try:
            import building_textures as btex
            ox = int(sum(p[0] for p in ip) / len(ip))
            oy = int(sum(p[1] for p in ip) / len(ip))
            textured = btex.fill_polygon_tinted(
                surf, ip, tex_name, mid, uv_origin=(ox, oy), detail=0.62,
            )
        except Exception:
            textured = False
    if not textured:
        pygame.draw.polygon(surf, mid, ip)
    cx = sum(p[0] for p in ip) / len(ip)
    cy = sum(p[1] for p in ip) / len(ip)
    # Shade wedge (lower-right of centroid)
    shade_pts = []
    for x, y in ip:
        if (x - cx) * 0.55 + (y - cy) * 0.85 > 0:
            shade_pts.append((x, y))
        else:
            shade_pts.append((int(cx + (x - cx) * 0.32), int(cy + (y - cy) * 0.32)))
    if len(shade_pts) >= 3:
        # Soft shade overlay so texture still shows through
        if textured:
            _blit_poly_alpha(surf, shade_pts, sh, 110)
        else:
            pygame.draw.polygon(surf, sh, shade_pts)
    # Deep underside hint
    deep_pts = []
    for x, y in ip:
        if y > cy + 0.15 * (max(abs(p[1] - cy) for p in ip) + 1):
            deep_pts.append((x, y))
        else:
            deep_pts.append((int(cx + (x - cx) * 0.2), int(cy + (y - cy) * 0.55)))
    if len(deep_pts) >= 3 and len({p for p in deep_pts}) >= 3:
        if textured:
            _blit_poly_alpha(surf, deep_pts, deep, 80)
        else:
            pygame.draw.polygon(surf, deep, deep_pts)
    # Highlight facet (upper-left)
    hi_pts = []
    for x, y in ip:
        if (x - cx) * LIGHT_DIR[0] + (y - cy) * LIGHT_DIR[1] > 0.12 * (abs(x - cx) + abs(y - cy) + 1):
            hi_pts.append((x, y))
    if len(hi_pts) >= 3:
        hi_pts = [
            (int(cx + (x - cx) * 0.68 - 1), int(cy + (y - cy) * 0.68 - 1))
            for x, y in hi_pts
        ]
        if len(hi_pts) >= 3:
            if textured:
                _blit_poly_alpha(surf, hi_pts, hi, 90)
            else:
                pygame.draw.polygon(surf, hi, hi_pts)
    if outline and width:
        pygame.draw.polygon(surf, outline, ip, max(1, int(width)))


def _blit_poly_alpha(surf, pts, color, alpha):
    """Draw a translucent polygon without allocating a full-screen surface."""
    if len(pts) < 3:
        return
    xs = [p[0] for p in pts]
    ys = [p[1] for p in pts]
    minx, maxx = int(min(xs)), int(max(xs)) + 1
    miny, maxy = int(min(ys)), int(max(ys)) + 1
    w, h = max(1, maxx - minx), max(1, maxy - miny)
    overlay = pygame.Surface((w, h), pygame.SRCALPHA)
    local = [(p[0] - minx, p[1] - miny) for p in pts]
    pygame.draw.polygon(overlay, (*color[:3], alpha), local)
    surf.blit(overlay, (minx, miny))


def draw_organic_mass(surf, base, cx, cy, rx, ry, seed=0, n=9, outline=OUTLINE, lit=True):
    """Irregular foliage/rock mass with interior dark + lit crown."""
    pts = irregular_ring(cx, cy, rx, ry, n=n, seed=seed, jitter=0.32)
    if lit:
        draw_volume(surf, base, pts, outline, 1)
    else:
        draw_poly(surf, shade(base, -30), pts, outline, 1)
    return pts


def draw_volume_limb(surf, ax, ay, bx, by, half_w, base, outline=OUTLINE, taper=0.78, bulge=0.12, detail=None):
    """
    Anatomical limb segment: thicker at A, taper at B, slight mid bulge,
    lit/shade halves from LIGHT_DIR. Optional photo detail texture.
    """
    dx, dy = bx - ax, by - ay
    length = math.hypot(dx, dy) or 1.0
    nx, ny = -dy / length, dx / length
    # Mid-point bulge for muscle/cloth read
    mx = ax + dx * 0.48
    my = ay + dy * 0.48
    half_m = half_w * (1.0 + bulge)
    half_b = half_w * taper
    pts = [
        (ax + nx * half_w, ay + ny * half_w),
        (mx + nx * half_m, my + ny * half_m),
        (bx + nx * half_b, by + ny * half_b),
        (bx - nx * half_b, by - ny * half_b),
        (mx - nx * half_m, my - ny * half_m),
        (ax - nx * half_w, ay - ny * half_w),
    ]
    lx, ly = LIGHT_DIR
    lit_n = (nx * lx + ny * ly) >= 0
    hi, mid, sh, _ = material(base)
    # Textured body of the limb, then lit/shade facets on top
    draw_volume(surf, base, pts, outline=None, width=0, detail=detail)
    if outline:
        ip = [(int(p[0]), int(p[1])) for p in pts]
        pygame.draw.polygon(surf, outline, ip, max(1, int(half_w * 0.22)))
    if lit_n:
        _blit_poly_alpha(surf, [
            (ax + nx * half_w * 0.12, ay + ny * half_w * 0.12),
            (ax + nx * half_w, ay + ny * half_w),
            (mx + nx * half_m, my + ny * half_m),
            (bx + nx * half_b, by + ny * half_b),
            (bx + nx * half_b * 0.12, by + ny * half_b * 0.12),
        ], hi, 95)
        _blit_poly_alpha(surf, [
            (ax - nx * half_w * 0.08, ay - ny * half_w * 0.08),
            (ax - nx * half_w, ay - ny * half_w),
            (mx - nx * half_m, my - ny * half_m),
            (bx - nx * half_b, by - ny * half_b),
            (bx - nx * half_b * 0.08, by - ny * half_b * 0.08),
        ], sh, 100)
    else:
        _blit_poly_alpha(surf, [
            (ax - nx * half_w * 0.12, ay - ny * half_w * 0.12),
            (ax - nx * half_w, ay - ny * half_w),
            (mx - nx * half_m, my - ny * half_m),
            (bx - nx * half_b, by - ny * half_b),
            (bx - nx * half_b * 0.12, by - ny * half_b * 0.12),
        ], hi, 95)
        _blit_poly_alpha(surf, [
            (ax + nx * half_w * 0.08, ay + ny * half_w * 0.08),
            (ax + nx * half_w, ay + ny * half_w),
            (mx + nx * half_m, my + ny * half_m),
            (bx + nx * half_b, by + ny * half_b),
            (bx + nx * half_b * 0.08, by + ny * half_b * 0.08),
        ], sh, 100)


def draw_cast_shadow(surf, cx, cy, rx, ry, alpha=110, irregular=False, seed=0):
    """Ground contact shadow elongated away from the key light."""
    lx, ly = LIGHT_DIR
    ox, oy = -lx * rx * 0.45, -ly * ry * 0.35
    alpha = min(200, int(alpha * 1.25))
    if irregular:
        sh = pygame.Surface((int(rx * 2.8) + 4, int(ry * 2.6) + 4), pygame.SRCALPHA)
        scx, scy = rx * 1.4 + 2, ry * 1.3 + 2
        pts = irregular_ring(scx, scy, rx * 1.2, ry * 0.95, n=10, seed=seed, jitter=0.22)
        ip = [(int(p[0]), int(p[1])) for p in pts]
        if len(ip) >= 3:
            pygame.draw.polygon(sh, (0, 0, 0, alpha), ip)
            pygame.draw.polygon(sh, (0, 0, 0, max(40, alpha // 2)), [
                (int(scx + (x - scx) * 1.18), int(scy + (y - scy) * 1.18)) for x, y in ip
            ])
        surf.blit(sh, (int(cx + ox - scx), int(cy + oy - scy)))
    else:
        draw_shadow(surf, cx + ox, cy + oy, rx * 1.2, ry * 0.9, alpha)


def draw_contact_shadow(surf, cx, cy, rx, ry, alpha=160):
    """Tight ellipse under feet / rock base — communicates ground plant."""
    draw_shadow(surf, cx, cy, rx, max(2, ry * 0.6), min(210, alpha))


# ---------------------------------------------------------------------------
# Drawing primitives
# ---------------------------------------------------------------------------
def draw_shadow(surf, cx, cy, rx, ry, alpha=100):
    rx, ry = max(2, int(rx)), max(2, int(ry))
    sh = pygame.Surface((rx * 2 + 2, ry * 2 + 2), pygame.SRCALPHA)
    pygame.draw.ellipse(sh, (0, 0, 0, alpha), (1, 1, rx * 2, ry * 2))
    surf.blit(sh, (int(cx - rx), int(cy - ry)))


def draw_poly(surf, color, pts, outline=OUTLINE, width=1):
    if len(pts) < 3:
        return
    ip = [(int(p[0]), int(p[1])) for p in pts]
    # Support RGBA via temp surface
    if len(color) == 4:
        minx = min(p[0] for p in ip)
        miny = min(p[1] for p in ip)
        maxx = max(p[0] for p in ip)
        maxy = max(p[1] for p in ip)
        w, h = max(1, maxx - minx + 2), max(1, maxy - miny + 2)
        tmp = pygame.Surface((w, h), pygame.SRCALPHA)
        local = [(p[0] - minx, p[1] - miny) for p in ip]
        pygame.draw.polygon(tmp, color, local)
        if outline and width:
            oc = outline if len(outline) == 4 else (*outline[:3], color[3])
            pygame.draw.polygon(tmp, oc, local, max(1, int(width)))
        surf.blit(tmp, (minx, miny))
        return
    pygame.draw.polygon(surf, color, ip)
    if outline and width:
        pygame.draw.polygon(surf, outline, ip, max(1, int(width)))


def draw_poly_layer(surf, faces):
    for face in faces:
        if len(face) == 2:
            color, pts = face
            draw_poly(surf, color, pts)
        elif len(face) == 3:
            color, pts, outline = face
            draw_poly(surf, color, pts, outline)
        else:
            color, pts, outline, width = face
            draw_poly(surf, color, pts, outline, width)


def rot(px, py, ang):
    c, s = math.cos(ang), math.sin(ang)
    return px * c - py * s, px * s + py * s


def bone_quad(ax, ay, bx, by, half_w):
    dx, dy = bx - ax, by - ay
    length = math.hypot(dx, dy) or 1.0
    nx, ny = -dy / length * half_w, dx / length * half_w
    return [
        (ax + nx, ay + ny), (ax - nx, ay - ny),
        (bx - nx, by - ny), (bx + nx, by + ny),
    ]


def joint(ox, oy, angle, length):
    return ox + math.cos(angle) * length, oy + math.sin(angle) * length


# ---------------------------------------------------------------------------
# Skeletal pose / animation — key poses with weight
# ---------------------------------------------------------------------------
DOWN = math.pi / 2


def _lerp_pose(a, b, t):
    t = max(0.0, min(1.0, t))
    return {k: a[k] + (b[k] - a[k]) * t for k in a}


def pose_idle(t, facing=1):
    breath = math.sin(t * 2.0) * 0.028
    sway = math.sin(t * 1.1) * 0.02
    # Arms hang by the sides (same rest as stand)
    return {
        "root_bob": math.sin(t * 2.0) * 0.22,
        "torso": DOWN + breath,
        "head": DOWN - 0.04 * facing + sway,
        "arm_l": DOWN + 0.04 * facing + breath * 0.2,
        "arm_r": DOWN - 0.04 * facing - breath * 0.2,
        "leg_l": DOWN + 0.05,
        "leg_r": DOWN - 0.05,
        "weapon": 0.0,
        "cape": math.sin(t * 1.4) * 0.08,
        "knee_l": 0.08,
        "knee_r": 0.08,
        "foot_lift_l": 0.0,
        "foot_lift_r": 0.0,
        "hip_sway": sway * 0.5,
        "stride": 0.0,
    }


def pose_stand(t, facing=1):
    """Arms by the sides — equipment paperdoll / formal stand."""
    breath = math.sin(t * 1.6) * 0.015
    return {
        "root_bob": breath * 0.4,
        "torso": DOWN + breath * 0.3,
        "head": DOWN - 0.02 * facing,
        "arm_l": DOWN + 0.10 * facing,   # hang at side
        "arm_r": DOWN - 0.10 * facing,
        "leg_l": DOWN + 0.04,
        "leg_r": DOWN - 0.04,
        "weapon": 0.0,
        "cape": 0.0,
        "knee_l": 0.06,
        "knee_r": 0.06,
        "foot_lift_l": 0.0,
        "foot_lift_r": 0.0,
        "hip_sway": 0.0,
        "stride": 0.0,
    }


def pose_walk(t, facing=1):
    """
    Side-view walk: modest stride; arms hang beside the body with a *small*
    opposite front/back shift (never a bilateral out/in flare).
    """
    cadence = TAU * 1.15
    ph = t * cadence
    hip_amp = 0.20

    hip_l = math.sin(ph) * hip_amp
    hip_r = math.sin(ph + math.pi) * hip_amp

    swing_l = max(0.0, math.cos(ph)) ** 1.15
    swing_r = max(0.0, math.cos(ph + math.pi)) ** 1.15

    knee_l = 0.05 + swing_l * 0.28
    knee_r = 0.05 + swing_r * 0.28
    knee_l += max(0.0, -math.cos(ph)) * 0.05
    knee_r += max(0.0, -math.cos(ph + math.pi)) * 0.05

    foot_lift_l = swing_l * 0.55
    foot_lift_r = swing_r * 0.55

    root_bob = 0.22 + 0.40 * (1.0 - abs(math.cos(ph)))
    hip_sway = math.sin(ph) * 0.03
    lean = 0.04 + 0.02 * abs(math.sin(ph))

    # Fixed hang beside the torso (no oscillating shoulder flare).
    # hand_shift: +1 ⇒ left arm slightly back, right arm slightly forward
    # (contralateral to legs: sin>0 left-leg-fwd ⇒ left-arm-back).
    hand_shift = math.sin(ph)

    fwd = -facing

    return {
        "root_bob": root_bob,
        "torso": DOWN + lean * 0.55 * facing + hip_sway * 0.35 * facing,
        "head": DOWN + lean * 0.25 * facing + math.sin(ph * 0.5) * 0.02,
        # Steady hang — swing is applied as a hand offset in the humanoid drawer
        "arm_l": DOWN + 0.08 * facing,
        "arm_r": DOWN - 0.08 * facing,
        "leg_l": DOWN + hip_l * fwd,
        "leg_r": DOWN + hip_r * fwd,
        "weapon": hand_shift * 0.04,
        "cape": math.sin(ph) * 0.28,
        "knee_l": knee_l,
        "knee_r": knee_r,
        "foot_lift_l": foot_lift_l,
        "foot_lift_r": foot_lift_r,
        "hip_sway": hip_sway,
        "stride": abs(hip_l),
        "hand_shift": hand_shift,
    }


def pose_ranged(progress, facing=1):
    """
    Archery draw → aim → release → recover.
    Arms pull the string back, bow stays upright; release snaps the draw hand forward.
    """
    p = max(0.0, min(1.0, float(progress or 0)))
    if p < 0.18:          # nock / raise bow
        u = p / 0.18
        draw = 0.15 * u
        lean = 0.04 * u
        aim = 0.2 * u
    elif p < 0.48:        # draw string back
        u = (p - 0.18) / 0.30
        ease = u * u * (3 - 2 * u)
        draw = 0.15 + 0.95 * ease
        lean = 0.04 + 0.08 * ease
        aim = 0.2 + 0.35 * ease
    elif p < 0.58:        # hold at full draw
        u = (p - 0.48) / 0.10
        draw = 1.10
        lean = 0.12
        aim = 0.55
    elif p < 0.72:        # release
        u = (p - 0.58) / 0.14
        ease = u * u * (3 - 2 * u)
        draw = 1.10 - 1.25 * ease
        lean = 0.12 - 0.18 * ease
        aim = 0.55 - 0.15 * ease
    else:                 # recover
        u = (p - 0.72) / 0.28
        ease = u * u * (3 - 2 * u)
        draw = max(0.0, -0.15 * (1.0 - ease))
        lean = -0.06 * (1.0 - ease)
        aim = 0.4 * (1.0 - ease)

    release = 1.0 if 0.56 <= p <= 0.70 else 0.0
    return {
        "root_bob": abs(math.sin(min(1.0, p * 1.1) * math.pi)) * 0.55,
        "torso": DOWN + lean * facing,
        "head": DOWN + aim * 0.35 * facing,
        # Off-hand braces the bow stave forward
        "arm_l": DOWN + (0.55 + aim * 0.45) * facing,
        # Draw hand pulls back then snaps forward on release
        "arm_r": DOWN - (0.15 + draw * 0.95) * facing,
        "leg_l": DOWN + 0.12 * facing,
        "leg_r": DOWN - 0.08 * facing,
        "weapon": draw,   # bow draw amount 0..1.1 (used by bow renderer)
        "cape": draw * 0.18 * facing,
        "knee_l": 0.12,
        "knee_r": 0.14 + lean * 0.2,
        "foot_lift_l": 0.0,
        "foot_lift_r": 0.0,
        "hip_sway": -lean * 0.2,
        "stride": 0.05,
        "bow_draw": draw,
        "bow_release": release,
    }


def pose_attack(progress, facing=1):
    """
    Melee: wind-up back → strike forward toward facing (the enemy).
    Shield / off-hand stays planted; only the weapon arm swings.
    """
    p = max(0.0, min(1.0, float(progress or 0)))

    # blade: negative = wind-up behind, positive = strike toward enemy
    if p < 0.12:          # brace
        u = p / 0.12
        blade = -0.12 * u
        lean = 0.05 * u
        step = -0.06 * u
        front_lift = 0.0
    elif p < 0.34:        # wind-up (blade back)
        u = (p - 0.12) / 0.22
        ease = u * u * (3 - 2 * u)
        blade = -0.12 - 0.95 * ease
        lean = 0.05 + 0.10 * ease
        step = -0.06 - 0.08 * ease
        front_lift = 0.10 * ease
    elif p < 0.48:        # commit — weapon drives toward enemy
        u = (p - 0.34) / 0.14
        ease = u * u * (3 - 2 * u)
        blade = -1.07 + 2.25 * ease       # → ~+1.18 forward
        lean = 0.15 - 0.32 * ease
        step = -0.14 + 0.42 * ease
        front_lift = 0.10 * (1 - ease)
    elif p < 0.62:        # impact hold
        u = (p - 0.48) / 0.14
        blade = 1.18 - 0.10 * u
        lean = -0.16 + 0.04 * u
        step = 0.28 - 0.04 * u
        front_lift = 0.0
    elif p < 0.80:        # follow-through
        u = (p - 0.62) / 0.18
        blade = 1.08 - 0.40 * u
        lean = -0.12 + 0.07 * u
        step = 0.24 - 0.12 * u
        front_lift = 0.0
    else:                 # recover
        u = (p - 0.80) / 0.20
        ease = u * u * (3 - 2 * u)
        blade = 0.68 * (1.0 - ease)
        lean = -0.06 * (1.0 - ease)
        step = 0.12 * (1.0 - ease)
        front_lift = 0.0

    impact = 0.0
    if 0.46 <= p <= 0.58:
        impact = math.sin((p - 0.46) / 0.12 * math.pi) * 0.55

    fwd = -facing
    return {
        "root_bob": abs(math.sin(min(1.0, p * 1.15) * math.pi)) * 0.95 + impact * 0.35,
        "torso": DOWN + lean * facing,
        "head": DOWN + lean * 0.45 * facing,
        # Shield / off-hand stays put beside the body
        "arm_l": DOWN + 0.28 * facing,
        # Weapon hand: +blade pulls the grip toward the enemy (along facing)
        "arm_r": DOWN - 0.06 * facing - blade * 0.85 * facing,
        "leg_l": DOWN + (0.18 - step * 0.55) * fwd,
        "leg_r": DOWN + (-0.12 + step) * fwd,
        "weapon": blade,
        "cape": -blade * 0.35,
        "knee_l": 0.14 + max(0.0, -step) * 0.35,
        "knee_r": 0.12 + max(0.0, step) * 0.45 + front_lift * 0.4,
        "foot_lift_l": 0.0,
        "foot_lift_r": front_lift * 1.6,
        "hip_sway": -lean * 0.25,
        "stride": abs(step),
    }


def resolve_pose(moving, t, attacking=0.0, facing=1, action=None, weapon_kind=None):
    atk = float(attacking or 0.0)
    if atk > 0.02:
        if weapon_kind == "bow" or action == "archery":
            return pose_ranged(atk, facing)
        return pose_attack(atk, facing)
    if action == "woodcutting":
        return pose_chop(t, facing)
    if action == "mining":
        return pose_mine(t, facing)
    if action == "fishing":
        return pose_fish(t, facing)
    if action == "stand":
        return pose_stand(t, facing)
    if moving:
        return pose_walk(t, facing)
    return pose_idle(t, facing)


def pose_chop(t, facing=1):
    """Looping axe swing — wind up overhead then chop into the tree."""
    # ~1.1 swings/sec aligned with gather ticks (~0.6s) so impact lands mid-tick
    ph = (t * 1.1) % 1.0
    if ph < 0.35:
        u = ph / 0.35
        ease = u * u * (3 - 2 * u)
        swing = -0.2 - 1.55 * ease          # raise axe
        lean = 0.08 * ease
        crouch = 0.05 * ease
    elif ph < 0.55:
        u = (ph - 0.35) / 0.20
        ease = u * u
        swing = -1.75 + 3.4 * ease          # drive down
        lean = 0.08 - 0.35 * ease
        crouch = 0.05 + 0.12 * ease
    else:
        u = (ph - 0.55) / 0.45
        ease = u * u * (3 - 2 * u)
        swing = 1.65 * (1.0 - ease)
        lean = -0.27 * (1.0 - ease)
        crouch = 0.17 * (1.0 - ease)
    impact = 1.0 if 0.48 <= ph <= 0.58 else 0.0
    fwd = -facing
    return {
        "root_bob": crouch * 2.2 + impact * 0.35,
        "torso": DOWN + lean * facing,
        "head": DOWN + lean * 0.4 * facing,
        "arm_l": DOWN + (0.45 + 0.2 * abs(lean)) * facing,
        "arm_r": DOWN - 0.08 * facing + swing * facing,
        "leg_l": DOWN + 0.12 * fwd,
        "leg_r": DOWN - 0.08 * fwd + lean * 0.15 * fwd,
        "weapon": swing,
        "cape": -swing * 0.25,
        "knee_l": 0.12,
        "knee_r": 0.18 + crouch * 0.4,
        "foot_lift_l": 0.0,
        "foot_lift_r": 0.0,
        "hip_sway": -lean * 0.15,
        "stride": 0.15,
        "action_impact": impact,
    }


def pose_mine(t, facing=1):
    """Looping pickaxe — coil back then jab at the rock."""
    ph = (t * 1.05) % 1.0
    if ph < 0.38:
        u = ph / 0.38
        ease = u * u * (3 - 2 * u)
        swing = -0.15 - 1.25 * ease
        lean = 0.12 * ease
        crouch = 0.18 * ease
    elif ph < 0.58:
        u = (ph - 0.38) / 0.20
        ease = u * u * (3 - 2 * u)
        swing = -1.4 + 2.9 * ease
        lean = 0.12 - 0.38 * ease
        crouch = 0.18 - 0.05 * ease
    else:
        u = (ph - 0.58) / 0.42
        ease = u * u * (3 - 2 * u)
        swing = 1.5 * (1.0 - ease)
        lean = -0.26 * (1.0 - ease)
        crouch = 0.13 * (1.0 - ease)
    impact = 1.0 if 0.50 <= ph <= 0.60 else 0.0
    fwd = -facing
    return {
        "root_bob": crouch * 2.6 + impact * 0.4,
        "torso": DOWN + lean * facing,
        "head": DOWN + lean * 0.5 * facing + 0.06,
        "arm_l": DOWN + 0.55 * facing,
        "arm_r": DOWN + swing * facing,
        "leg_l": DOWN + 0.18 * fwd,
        "leg_r": DOWN - 0.15 * fwd,
        "weapon": swing * 0.95,
        "cape": -swing * 0.2,
        "knee_l": 0.22 + crouch * 0.35,
        "knee_r": 0.28 + crouch * 0.5,
        "foot_lift_l": 0.0,
        "foot_lift_r": 0.0,
        "hip_sway": 0.0,
        "stride": 0.1,
        "action_impact": impact,
    }


def pose_fish(t, facing=1):
    """Cast / bob loop — plant feet on shore, rod reaches out over the water."""
    ph = t * TAU * 0.55
    bob = math.sin(ph) * 0.18
    tug = max(0.0, math.sin(ph * 0.5 + 0.8)) ** 2
    yank = max(0.0, math.sin(ph * 0.35 - 0.4)) ** 4
    # Strong forward lean and extended casting arm (reads as fishing, not idle)
    lean = 0.22 + bob * 0.1 + yank * 0.12
    arm_swing = 0.95 + bob * 0.25 + tug * 0.35 + yank * 0.4
    fwd = -facing
    return {
        "root_bob": 0.2 + abs(bob) * 0.25 + yank * 0.35,
        "torso": DOWN + lean * facing,
        "head": DOWN + (lean * 0.45 + 0.1) * facing,
        # Off-hand near reel; rod arm fully extended toward water
        "arm_l": DOWN + (0.35 + tug * 0.12) * facing,
        "arm_r": DOWN + arm_swing * facing,
        # Planted stance — no walk bob, slight brace
        "leg_l": DOWN + 0.06 * fwd,
        "leg_r": DOWN - 0.16 * fwd,
        "weapon": 0.55 + bob * 0.2 + yank * 0.35,
        "cape": bob * 0.25,
        "knee_l": 0.12,
        "knee_r": 0.22,
        "foot_lift_l": 0.0,
        "foot_lift_r": 0.0,
        "hip_sway": bob * 0.03,
        "stride": 0.0,
        "action_impact": yank,
    }


def attack_impulse(progress):
    """
    Shared melee envelope for monsters/pets (0..1).

    Returns (lunge, crouch, strike) where:
      lunge  — forward body translation weight (−back … +forward)
      crouch — vertical squash / coil
      strike — 0..1 peak at impact (for flashes / teeth / weapon tip)
    """
    p = max(0.0, min(1.0, float(progress or 0)))
    if p < 0.18:          # coil / wind-up
        u = p / 0.18
        ease = u * u * (3 - 2 * u)
        return (-0.35 * ease, 0.55 * ease, 0.0)
    if p < 0.48:          # commit
        u = (p - 0.18) / 0.30
        ease = u * u * (3 - 2 * u)
        return (-0.35 + 1.55 * ease, 0.55 * (1.0 - ease * 0.7), ease * 0.85)
    if p < 0.62:          # impact hold
        u = (p - 0.48) / 0.14
        return (1.15 - 0.15 * u, 0.12, 1.0 - 0.35 * u)
    if p < 0.82:          # follow
        u = (p - 0.62) / 0.20
        return (1.0 - 0.75 * u, 0.08 * (1.0 - u), 0.55 * (1.0 - u))
    u = (p - 0.82) / 0.18
    ease = u * u * (3 - 2 * u)
    return (0.25 * (1.0 - ease), 0.0, 0.0)


# ---------------------------------------------------------------------------
# Metal / cloth helpers from item ids
# ---------------------------------------------------------------------------
def metal_palette(item_id):
    if not item_id:
        return METAL_PALETTE
    if "mythos" in item_id:
        # Crimson dragon-plate with gold-leaning highlight
        return ((178, 28, 38), (88, 10, 16), (245, 95, 88), (42, 6, 10))
    if "eclipse" in item_id:
        # Black steel with cool highlight (gold accents drawn separately)
        return ((48, 48, 55), (16, 16, 20), (110, 110, 122), (8, 8, 10))
    if "adamant" in item_id:
        return ((70, 180, 110), (40, 110, 70), (140, 230, 160), (20, 50, 30))
    if "mithril" in item_id:
        return ((100, 160, 200), (55, 100, 140), (160, 210, 240), (30, 50, 70))
    if "steel" in item_id:
        return ((170, 175, 185), (110, 115, 125), (220, 225, 235), (40, 42, 48))
    if "iron" in item_id:
        return ((140, 140, 150), (90, 90, 100), (190, 190, 200), (40, 40, 48))
    if "bronze" in item_id or "copper" in item_id:
        return ((200, 150, 75), (140, 95, 45), (235, 195, 120), (55, 35, 18))
    if "leather" in item_id or "chaps" in item_id:
        return ((140, 95, 55), (95, 60, 35), (180, 130, 80), (50, 30, 16))
    return METAL_PALETTE
