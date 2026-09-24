"""
Load and blit CC0 photoreal textures (ambientCG) for buildings / roofs / piers.

Textures live in mmorpg/client/textures/ — see ATTRIBUTION.txt.
"""
import os

import pygame

_TEXTURE_DIR = None
_CACHE = {}
_FAILED = set()


def set_texture_dir(path):
    """Point at the folder containing wood_planks.png, brick.png, etc."""
    global _TEXTURE_DIR
    _TEXTURE_DIR = path
    _CACHE.clear()
    _FAILED.clear()


def _default_texture_dir():
    # characters/ → mmorpg/client/textures
    here = os.path.dirname(os.path.abspath(__file__))
    return os.path.normpath(os.path.join(here, "..", "mmorpg", "client", "textures"))


def get_texture(name):
    """Return a cached pygame Surface for a texture key, or None."""
    if name in _FAILED:
        return None
    if name in _CACHE:
        return _CACHE[name]
    folder = _TEXTURE_DIR or _default_texture_dir()
    path = os.path.join(folder, f"{name}.png")
    if not os.path.isfile(path):
        path = os.path.join(folder, f"{name}.jpg")
    if not os.path.isfile(path):
        _FAILED.add(name)
        return None
    try:
        surf = pygame.image.load(path).convert()
    except pygame.error:
        _FAILED.add(name)
        return None
    _CACHE[name] = surf
    return surf


def blit_wrapped(dest, dest_rect, src, src_x, src_y, alpha=255):
    """Tile `src` into dest_rect, starting UV at (src_x, src_y) with wrap."""
    if src is None or dest_rect.w <= 0 or dest_rect.h <= 0:
        return False
    sw, sh = src.get_size()
    dw, dh = int(dest_rect.w), int(dest_rect.h)
    sx = int(src_x) % sw
    sy = int(src_y) % sh
    buf = pygame.Surface((dw, dh))
    y = -sy
    while y < dh:
        x = -sx
        while x < dw:
            buf.blit(src, (x, y))
            x += sw
        y += sh
    if alpha < 255:
        buf.set_alpha(alpha)
    dest.blit(buf, dest_rect.topleft)
    return True


def blit_texture_tile(surf, rect, name, world_x, world_y, alpha=255):
    """Fill a world tile rect with a seamlessly tiled texture."""
    tex = get_texture(name)
    if tex is None:
        return False
    # One world tile ≈ this many texels (keeps detail readable at TILE≈40)
    cell = max(24, min(64, rect.w * 2))
    return blit_wrapped(surf, rect, tex, world_x * cell, world_y * cell, alpha=alpha)


def fill_polygon_textured(surf, pts, name, alpha=255, uv_origin=(0, 0)):
    """Fill a polygon with a wrapped texture (masked)."""
    tex = get_texture(name)
    if tex is None or len(pts) < 3:
        return False
    xs = [p[0] for p in pts]
    ys = [p[1] for p in pts]
    minx, maxx = int(min(xs)), int(max(xs)) + 1
    miny, maxy = int(min(ys)), int(max(ys)) + 1
    w, h = max(1, maxx - minx), max(1, maxy - miny)
    temp = pygame.Surface((w, h), pygame.SRCALPHA)
    blit_wrapped(temp, pygame.Rect(0, 0, w, h), tex, uv_origin[0], uv_origin[1], alpha=255)
    mask = pygame.Surface((w, h), pygame.SRCALPHA)
    local = [(p[0] - minx, p[1] - miny) for p in pts]
    pygame.draw.polygon(mask, (255, 255, 255, 255), local)
    temp.blit(mask, (0, 0), special_flags=pygame.BLEND_RGBA_MULT)
    if alpha < 255:
        # Scale overall alpha
        a_surf = pygame.Surface((w, h), pygame.SRCALPHA)
        a_surf.fill((255, 255, 255, alpha))
        temp.blit(a_surf, (0, 0), special_flags=pygame.BLEND_RGBA_MULT)
    surf.blit(temp, (minx, miny))
    return True


def fill_polygon_tinted(surf, pts, name, tint, uv_origin=(0, 0), detail=0.55):
    """
    Fill a polygon with photo texture colorized by `tint`.

    Textures are stored desaturated so multiplying by tint preserves silhouette
    colors (skin, cloth, fur) while adding real surface detail.
    detail: 0 = flat tint only, 1 = full texture contrast.
    """
    tex = get_texture(name)
    if tex is None or len(pts) < 3:
        return False
    xs = [int(p[0]) for p in pts]
    ys = [int(p[1]) for p in pts]
    minx, maxx = min(xs), max(xs) + 1
    miny, maxy = min(ys), max(ys) + 1
    w, h = max(1, maxx - minx), max(1, maxy - miny)
    if w > 400 or h > 400:
        # Safety for huge polys — skip texture
        return False
    local = [(p[0] - minx, p[1] - miny) for p in pts]

    # Tiled detail
    detail_buf = pygame.Surface((w, h))
    blit_wrapped(detail_buf, pygame.Rect(0, 0, w, h), tex, uv_origin[0], uv_origin[1], alpha=255)

    # Mix flat mid color with textured detail, then multiply by tint
    flat = pygame.Surface((w, h))
    flat.fill((168, 168, 168))
    detail_buf.set_alpha(int(max(0, min(1.0, detail)) * 255))
    flat.blit(detail_buf, (0, 0))

    tint_rgb = tuple(max(0, min(255, int(c))) for c in tint[:3])
    colorizer = pygame.Surface((w, h))
    colorizer.fill(tint_rgb)
    flat.blit(colorizer, (0, 0), special_flags=pygame.BLEND_RGB_MULT)

    # Mask to polygon
    out = pygame.Surface((w, h), pygame.SRCALPHA)
    out.blit(flat, (0, 0))
    mask = pygame.Surface((w, h), pygame.SRCALPHA)
    pygame.draw.polygon(mask, (255, 255, 255, 255), local)
    out.blit(mask, (0, 0), special_flags=pygame.BLEND_RGBA_MULT)
    surf.blit(out, (minx, miny))
    return True
