"""
2.5D shadow helpers for Mythoscape buildings / scenery.

Research-backed approach (isometric style guides + pygame ShadowEffects):
- One fixed key light (upper-left) for the whole game
- Soft contact ellipse under the footprint (grounds the object)
- Squashed silhouette cast shadow offset away from the light
- Low opacity, warm-dark (not pure black) so the palette stays readable
"""
from __future__ import annotations

import math

import pygame

# Key light from upper-left → cast shadows fall lower-right
LIGHT_DX = 1.0
LIGHT_DY = 0.55


def _warm_dark(alpha: int):
    """Desaturated warm shadow — avoids muddy pure black."""
    a = max(0, min(255, int(alpha)))
    return (18, 14, 12, a)


def draw_contact_ellipse(surf, cx, cy, rx, ry, alpha=100):
    """Tight ground plant shadow under a footprint."""
    rx, ry = max(3, int(rx)), max(2, int(ry))
    sh = pygame.Surface((rx * 2 + 4, ry * 2 + 4), pygame.SRCALPHA)
    # Soft outer + denser core
    pygame.draw.ellipse(sh, _warm_dark(max(30, alpha // 2)), (0, 0, rx * 2 + 4, ry * 2 + 4))
    pygame.draw.ellipse(sh, _warm_dark(alpha), (2, 2, rx * 2, ry * 2))
    surf.blit(sh, (int(cx - rx - 2), int(cy - ry - 2)))


def draw_cast_blob(surf, cx, cy, rx, ry, alpha=85):
    """Directional ground blob elongated away from the key light."""
    ox = LIGHT_DX * rx * 0.35
    oy = LIGHT_DY * ry * 0.55
    draw_contact_ellipse(surf, cx + ox, cy + oy, rx * 1.15, max(2, ry * 0.75), alpha)


def make_silhouette_shadow(image: pygame.Surface, strength: float = 0.55) -> pygame.Surface:
    """
    Alpha-mask silhouette tinted warm-dark (pygame ShadowEffects pattern).
    strength 0..1 — higher = darker shadow.
    """
    strength = max(0.05, min(1.0, float(strength)))
    sh = image.copy()
    # Keep alpha, crush RGB toward warm dark
    sh.fill((22, 16, 14, 255), special_flags=pygame.BLEND_RGBA_MULT)
    if strength < 0.99:
        # Fade overall opacity
        fade = pygame.Surface(sh.get_size(), pygame.SRCALPHA)
        fade.fill((255, 255, 255, int(255 * strength)))
        sh.blit(fade, (0, 0), special_flags=pygame.BLEND_RGBA_MULT)
    return sh


def draw_silhouette_cast(
    surf,
    image: pygame.Surface,
    x: int,
    y: int,
    *,
    scale_x: float = 1.0,
    scale_y: float = 0.38,
    offset_x: float = None,
    offset_y: float = None,
    strength: float = 0.42,
):
    """
    Squash the sprite silhouette onto the ground and offset it with the key light.
    Drawn *before* the building so it sits under the facade.
    """
    if image.get_width() < 2 or image.get_height() < 2:
        return
    w = max(2, int(image.get_width() * scale_x))
    h = max(2, int(image.get_height() * scale_y))
    try:
        scaled = pygame.transform.smoothscale(image, (w, h))
    except pygame.error:
        scaled = pygame.transform.scale(image, (w, h))
    shadow = make_silhouette_shadow(scaled, strength=strength)
    if offset_x is None:
        offset_x = LIGHT_DX * image.get_width() * 0.08
    if offset_y is None:
        offset_y = image.get_height() * (1.0 - scale_y) * 0.92 + LIGHT_DY * 6
    surf.blit(shadow, (int(x + offset_x), int(y + offset_y)))


def draw_wall_base_ao(surf, rect, alpha=70):
    """Darken the south edge of a footprint — ambient occlusion at ground contact."""
    if rect.w < 2 or rect.h < 2:
        return
    band_h = max(3, rect.h // 10)
    ao = pygame.Surface((rect.w, band_h), pygame.SRCALPHA)
    for i in range(band_h):
        a = int(alpha * (1.0 - i / max(1, band_h - 1)))
        pygame.draw.line(ao, _warm_dark(a), (0, i), (rect.w, i))
    surf.blit(ao, (rect.x, rect.bottom - band_h))


def draw_corner_ao(surf, rect, corner="SW", size=None, alpha=55):
    """Soft AO wedge where wall planes meet the ground / side face."""
    size = size or max(8, min(rect.w, rect.h) // 5)
    ao = pygame.Surface((size, size), pygame.SRCALPHA)
    for i in range(size):
        for j in range(size):
            # Distance from corner
            if corner == "SW":
                d = math.hypot(i / size, (size - 1 - j) / size)
            elif corner == "SE":
                d = math.hypot((size - 1 - i) / size, (size - 1 - j) / size)
            else:
                d = math.hypot(i / size, j / size)
            if d < 1.0:
                a = int(alpha * (1.0 - d) ** 1.4)
                ao.set_at((i, j), _warm_dark(a))
    if corner == "SW":
        surf.blit(ao, (rect.x, rect.bottom - size))
    elif corner == "SE":
        surf.blit(ao, (rect.right - size, rect.bottom - size))
    else:
        surf.blit(ao, (rect.x, rect.y))


def draw_footprint_cast(surf, rect, height_hint=None, alpha=78):
    """
    Skewed parallelogram cast matching the building footprint.
    Light from upper-left → shadow slides lower-right (TheoTown / pixel-art rule).
    height_hint: approximate building height in px — longer cast for taller shells.
    """
    if rect.w < 4 or rect.h < 4:
        return
    h = float(height_hint if height_hint is not None else rect.h * 0.55)
    # Keep cast short so it doesn't swallow the apron / player
    skew_x = int(min(rect.w * 0.28, h * 0.22 * LIGHT_DX))
    skew_y = int(min(rect.h * 0.22, h * 0.12 * LIGHT_DY + 2))
    x0, y0 = rect.x + 2, rect.bottom - max(2, rect.h // 18)
    x1, y1 = rect.right - 2, y0
    pts = [
        (x0, y0),
        (x1, y1),
        (x1 + skew_x, y1 + skew_y),
        (x0 + skew_x, y0 + skew_y),
    ]
    for grow, a in ((4, max(12, alpha // 4)), (1, max(20, alpha // 2)), (0, alpha)):
        expanded = [
            (pts[0][0] - grow, pts[0][1] - grow // 2),
            (pts[1][0] + grow, pts[1][1] - grow // 2),
            (pts[2][0] + grow, pts[2][1] + grow // 2),
            (pts[3][0] - grow, pts[3][1] + grow // 2),
        ]
        sh = pygame.Surface((surf.get_width(), surf.get_height()), pygame.SRCALPHA)
        pygame.draw.polygon(sh, _warm_dark(a), expanded)
        surf.blit(sh, (0, 0))
    # Hard contact line under the south wall
    pygame.draw.line(
        surf, _warm_dark(min(160, alpha + 30)),
        (x0 + 1, y0), (x1 - 1, y0), 2,
    )


def draw_eave_cast(surf, x, y, w, h, alpha=100):
    """Trapezoid shadow the roof overhang drops onto the facade."""
    if w < 4 or h < 2:
        return
    band = pygame.Surface((int(w), int(h)), pygame.SRCALPHA)
    for i in range(int(h)):
        t = 1.0 - i / max(1, h - 1)
        # Stronger in the middle (deeper under peak), softer at edges
        a = int(alpha * (t ** 1.15))
        pygame.draw.line(band, _warm_dark(a), (0, i), (int(w), i))
    # Soft left/right fade so it doesn't look like a stamp
    for i in range(min(12, w // 6)):
        fade = pygame.Surface((1, int(h)), pygame.SRCALPHA)
        fade.fill((255, 255, 255, int(255 * (i / max(1, min(12, w // 6))))))
        band.blit(fade, (i, 0), special_flags=pygame.BLEND_RGBA_MULT)
        band.blit(fade, (int(w) - 1 - i, 0), special_flags=pygame.BLEND_RGBA_MULT)
    surf.blit(band, (int(x), int(y)))
