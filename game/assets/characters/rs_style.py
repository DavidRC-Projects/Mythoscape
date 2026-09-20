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
PET_SCALE = 1.65
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


def draw_volume(surf, base, pts, outline=OUTLINE, width=1):
    """
    Filled polygon with directional volume:
    mid fill + lower-right shade + upper-left highlight facet.
    """
    if len(pts) < 3:
        return
    hi, mid, sh, deep = material(base)
    ip = [(int(p[0]), int(p[1])) for p in pts]
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
        pygame.draw.polygon(surf, sh, shade_pts)
    # Deep underside hint
    deep_pts = []
    for x, y in ip:
        if y > cy + 0.15 * (max(abs(p[1] - cy) for p in ip) + 1):
            deep_pts.append((x, y))
        else:
            deep_pts.append((int(cx + (x - cx) * 0.2), int(cy + (y - cy) * 0.55)))
    if len(deep_pts) >= 3 and len({p for p in deep_pts}) >= 3:
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
            pygame.draw.polygon(surf, hi, hi_pts)
    if outline and width:
        pygame.draw.polygon(surf, outline, ip, max(1, int(width)))


def draw_organic_mass(surf, base, cx, cy, rx, ry, seed=0, n=9, outline=OUTLINE, lit=True):
    """Irregular foliage/rock mass with interior dark + lit crown."""
    pts = irregular_ring(cx, cy, rx, ry, n=n, seed=seed, jitter=0.32)
    if lit:
        draw_volume(surf, base, pts, outline, 1)
    else:
        draw_poly(surf, shade(base, -30), pts, outline, 1)
    return pts


def draw_volume_limb(surf, ax, ay, bx, by, half_w, base, outline=OUTLINE, taper=0.78, bulge=0.12):
    """
    Anatomical limb segment: thicker at A, taper at B, slight mid bulge,
    lit/shade halves from LIGHT_DIR.
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
    draw_poly(surf, mid, pts, outline, max(1, int(half_w * 0.22)))
    if lit_n:
        draw_poly(surf, hi, [
            (ax + nx * half_w * 0.12, ay + ny * half_w * 0.12),
            (ax + nx * half_w, ay + ny * half_w),
            (mx + nx * half_m, my + ny * half_m),
            (bx + nx * half_b, by + ny * half_b),
            (bx + nx * half_b * 0.12, by + ny * half_b * 0.12),
        ], None, 0)
        draw_poly(surf, sh, [
            (ax - nx * half_w * 0.08, ay - ny * half_w * 0.08),
            (ax - nx * half_w, ay - ny * half_w),
            (mx - nx * half_m, my - ny * half_m),
            (bx - nx * half_b, by - ny * half_b),
            (bx - nx * half_b * 0.08, by - ny * half_b * 0.08),
        ], None, 0)
    else:
        draw_poly(surf, hi, [
            (ax - nx * half_w * 0.12, ay - ny * half_w * 0.12),
            (ax - nx * half_w, ay - ny * half_w),
            (mx - nx * half_m, my - ny * half_m),
            (bx - nx * half_b, by - ny * half_b),
            (bx - nx * half_b * 0.12, by - ny * half_b * 0.12),
        ], None, 0)
        draw_poly(surf, sh, [
            (ax + nx * half_w * 0.08, ay + ny * half_w * 0.08),
            (ax + nx * half_w, ay + ny * half_w),
            (mx + nx * half_m, my + ny * half_m),
            (bx + nx * half_b, by + ny * half_b),
            (bx + nx * half_b * 0.08, by + ny * half_b * 0.08),
        ], None, 0)


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
    return {
        "root_bob": math.sin(t * 2.0) * 0.28,
        "torso": DOWN + breath,
        "head": DOWN - 0.04 * facing + sway,
        "arm_l": DOWN + 0.32 * facing + breath,
        "arm_r": DOWN - 0.32 * facing - breath,
        "leg_l": DOWN + 0.06,
        "leg_r": DOWN - 0.06,
        "weapon": 0.0,
        "cape": math.sin(t * 1.4) * 0.08,
    }


def pose_walk(t, facing=1):
    """
    Four-phase gait: CONTACT → DOWN → PASS → UP
    Amplified swings so weight reads at gameplay scale.
    """
    phase = (t * 9.5) % TAU
    u = phase / TAU
    contact = {"leg_l": 0.72, "leg_r": -0.48, "arm_l": -0.55, "arm_r": 0.6, "bob": 0.25}
    down = {"leg_l": 0.35, "leg_r": -0.22, "arm_l": -0.28, "arm_r": 0.35, "bob": 1.55}
    pas = {"leg_l": -0.22, "leg_r": 0.62, "arm_l": 0.48, "arm_r": -0.42, "bob": 0.4}
    up = {"leg_l": -0.55, "leg_r": 0.28, "arm_l": 0.65, "arm_r": -0.58, "bob": 1.05}

    if u < 0.25:
        k0, k1, ft = contact, down, u / 0.25
    elif u < 0.5:
        k0, k1, ft = down, pas, (u - 0.25) / 0.25
    elif u < 0.75:
        k0, k1, ft = pas, up, (u - 0.5) / 0.25
    else:
        k0, k1, ft = up, contact, (u - 0.75) / 0.25

    def L(a, b):
        return a + (b - a) * ft

    swing_l = L(k0["leg_l"], k1["leg_l"])
    swing_r = L(k0["leg_r"], k1["leg_r"])
    return {
        "root_bob": L(k0["bob"], k1["bob"]),
        "torso": DOWN + math.sin(phase) * 0.07,
        "head": DOWN + math.sin(phase * 0.5) * 0.04,
        "arm_l": DOWN + 0.18 * facing + L(k0["arm_l"], k1["arm_l"]) * facing,
        "arm_r": DOWN - 0.18 * facing + L(k0["arm_r"], k1["arm_r"]) * facing,
        "leg_l": DOWN + swing_l,
        "leg_r": DOWN + swing_r,
        "weapon": swing_r * 0.28,
        "cape": math.sin(phase) * 0.3,
    }


def pose_attack(progress, facing=1):
    """READY → WINDUP → STRIKE → FOLLOW-THROUGH → RECOVER."""
    p = max(0.0, min(1.0, float(progress or 0)))
    if p < 0.18:
        u = p / 0.18
        swing = -0.25 * u
        lean = 0.04 * u
    elif p < 0.38:
        u = (p - 0.18) / 0.20
        swing = -0.25 - 1.05 * u
        lean = 0.04 + 0.1 * u
    elif p < 0.52:
        u = (p - 0.38) / 0.14
        swing = -1.3 + 2.85 * u
        lean = 0.14 - 0.22 * u
    elif p < 0.72:
        u = (p - 0.52) / 0.20
        swing = 1.55 - 0.35 * u
        lean = -0.08 + 0.05 * u
    else:
        u = (p - 0.72) / 0.28
        swing = 1.2 * (1.0 - u)
        lean = -0.03 * (1.0 - u)
    return {
        "root_bob": abs(math.sin(p * math.pi)) * 0.75,
        "torso": DOWN + lean * facing,
        "head": DOWN + lean * 0.4 * facing,
        "arm_l": DOWN + 0.5 * facing,
        "arm_r": DOWN - 0.1 * facing + swing * facing,
        "leg_l": DOWN + 0.22,
        "leg_r": DOWN - 0.18,
        "weapon": swing,
        "cape": -swing * 0.35,
    }


def resolve_pose(moving, t, attacking=0.0, facing=1):
    atk = float(attacking or 0.0)
    if atk > 0.02:
        return pose_attack(atk, facing)
    if moving:
        return pose_walk(t, facing)
    return pose_idle(t, facing)


# ---------------------------------------------------------------------------
# Metal / cloth helpers from item ids
# ---------------------------------------------------------------------------
def metal_palette(item_id):
    if not item_id:
        return METAL_PALETTE
    if "mythos" in item_id:
        return ((210, 170, 255), (130, 90, 180), (240, 220, 255), (50, 30, 70))
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
