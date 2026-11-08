"""Painted world / Castle Realm map helpers — soft terrain, place portraits, cards."""
from __future__ import annotations

import os
from pathlib import Path

import pygame

_ROOT = Path(__file__).resolve().parent / "assets" / "map_atlas" / "places"
_RAW = {}
_SCALED = {}
_SOFT = {}

# Destination id → portrait stem (files are <stem>.jpg under places/).
PORTRAIT_FOR = {
    "crossroads": "crossroads",
    "bank": "bank",
    "stonehaven_bank": "bank",
    "dungeon_bank": "bank",
    "smithy": "smithy",
    "anvil": "smithy",
    "inn_hearth": "inn",
    "lake": "lake",
    "stonehaven": "stonehaven",
    "mira_market": "stonehaven",
    "stonehaven_castle": "stonehaven",
    "dungeon_gate": "crypt",
    "goblins": "crypt",
    "skeletons": "crypt",
    "giants": "crypt",
    "big_skeletons": "crypt",
    "spiders": "crypt",
    "dragon": "crypt",
    "harbourreach": "harbour",
    "harbour_pier": "harbour",
    "harbour_tackle": "harbour",
    "tidehollow": "harbour",
    "quest_scout_elena": "fairy",
    "wishing_well": "well",
    "realm": "realm",
    "castle_realm": "realm",
    "gothic": "gothic",
    "king": "king",
    "rose": "rose",
    "sky": "sky",
    "arena": "arena",
    "emberdeep": "emberdeep",
    "void_sanctum": "void",
    "shades": "void",
    "crypt_ghouls": "void",
    "void_imps": "void",
    "obsidian_colossi": "void",
    "shadow_knights": "void",
    "void_horror": "void",
    "endless_depths": "endless",
    "quest_endless_chronicler": "endless",
    "mountain_pass": "harbour",  # rugged approach — reuse coastal hills tone
    "wolves": "harbour",
    "outfitters": "crossroads",
    "general_store": "crossroads",
    "bag_shop": "crossroads",
    "jewelry_shop": "crossroads",
    "bow_shop": "crossroads",
    "pet_shop": "inn",
    "estate_agent": "village",
    "kings_row_homes": "king",
    "mad_scientist": "lake",
    "quest_scout_bren": "harbour",
    "quest_hermit_cole": "crypt",
    "quest_cook_nell": "harbour",
    "quest_herald_rowan": "stonehaven",
    "guards": "stonehaven",
    "knights": "king",
    "mythos_champion": "king",
    "eclipse_champion": "gothic",
    "rats": "emberdeep",
    "copper_vein": "emberdeep",
}

WORLD_MAP_SCALE_MIN = 3
WORLD_MAP_SCALE_MAX = 18
WORLD_MAP_SCALE_DEFAULT = 6


def portrait_path(dest_id: str) -> Path | None:
    stem = PORTRAIT_FOR.get(dest_id)
    if not stem:
        return None
    for ext in (".jpg", ".jpeg", ".png"):
        path = _ROOT / f"{stem}{ext}"
        if path.is_file():
            return path
    return None


def portrait(dest_id: str, size: int = 72):
    """Cached smoothscaled place portrait, or None."""
    path = portrait_path(dest_id)
    if path is None:
        return None
    size = max(16, int(size))
    key = (str(path), size)
    img = _SCALED.get(key)
    if img is not None:
        return img
    raw = _RAW.get(str(path))
    if raw is None:
        try:
            raw = pygame.image.load(str(path)).convert()
        except pygame.error:
            return None
        _RAW[str(path)] = raw
    img = pygame.transform.smoothscale(raw, (size, size))
    if len(_SCALED) > 96:
        _SCALED.clear()
    _SCALED[key] = img
    return img


def soft_terrain_surface(client, ox, oy, view_w, view_h, canvas_w, canvas_h, in_realm=False):
    """Build a soft (blurred / painted) terrain plate instead of chunky 1px tiles."""
    view_w = max(1, int(view_w))
    view_h = max(1, int(view_h))
    canvas_w = max(1, int(canvas_w))
    canvas_h = max(1, int(canvas_h))
    key = (
        id(client.tiles),
        int(ox), int(oy), view_w, view_h, canvas_w, canvas_h,
        bool(in_realm), int(getattr(client, "camera_yaw", 0) or 0),
    )
    cached = _SOFT.get(key)
    if cached is not None:
        return cached

    # Paint at 2× tile resolution then smoothscale up — reads as painted, not pixels.
    tw = max(2, min(4, max(2, canvas_w // max(1, view_w))))
    base = pygame.Surface((view_w * tw, view_h * tw))
    base.fill((18, 28, 18))
    rows = None
    if in_realm:
        try:
            import castle_realm_renderer as crr
            rows = crr.REALM_ROWS
        except Exception:
            rows = None
    tiles = client.tiles or []
    world_h = len(tiles)
    for ty in range(view_h):
        wy = oy + ty
        if wy < 0 or wy >= world_h:
            continue
        row = tiles[wy]
        world_w = len(row)
        for tx in range(view_w):
            wx = ox + tx
            if wx < 0 or wx >= world_w:
                continue
            col = client.minimap_tile_color(row[wx])
            if rows is not None and 0 <= wy < len(rows) and 0 <= wx < len(rows[wy]):
                ch = rows[wy][wx]
                if ch == "s":
                    col = (220, 175, 55)
                elif ch == "A":
                    col = (165, 150, 130)
                elif ch == "c":
                    col = (90, 85, 100)
                elif ch == "~":
                    col = (50, 110, 170)
                elif ch == "T":
                    col = (40, 90, 45)
                elif ch in "=PSol":
                    col = (150, 130, 90)
            pygame.draw.rect(base, col, (tx * tw, ty * tw, tw, tw))

    # Soften block edges.
    soft = pygame.transform.smoothscale(base, (canvas_w, canvas_h))
    soft = pygame.transform.smoothscale(
        pygame.transform.smoothscale(soft, (max(1, canvas_w // 2), max(1, canvas_h // 2))),
        (canvas_w, canvas_h),
    )
    # Warm parchment wash so it feels like a chart, not a grid.
    wash = pygame.Surface((canvas_w, canvas_h), pygame.SRCALPHA)
    wash.fill((40, 32, 18, 35))
    soft.blit(wash, (0, 0))
    if len(_SOFT) > 12:
        _SOFT.clear()
    _SOFT[key] = soft
    return soft


def clear_soft_cache():
    _SOFT.clear()


def nearest_places(dests, px, py, limit=6):
    """Closest named places to the player (for the side card rail)."""
    scored = []
    for d in dests:
        try:
            dx = int(d["x"]) - int(px)
            dy = int(d["y"]) - int(py)
        except (KeyError, TypeError, ValueError):
            continue
        scored.append((dx * dx + dy * dy, d))
    scored.sort(key=lambda t: t[0])
    return [d for _dist, d in scored[:limit]]


def draw_place_card(screen, fonts, rect, dest, portrait_img, *, here=False, hover=False):
    """Compact card: thumb + name + blurb."""
    bg = (36, 42, 58) if not hover else (48, 58, 78)
    if here:
        bg = (48, 62, 48)
    pygame.draw.rect(screen, bg, rect, border_radius=8)
    border = (120, 200, 130) if here else ((200, 180, 110) if hover else (90, 110, 140))
    pygame.draw.rect(screen, border, rect, 2 if here or hover else 1, border_radius=8)

    pad = 6
    thumb = max(28, rect.h - pad * 2)
    if portrait_img is not None:
        img = portrait_img
        if img.get_width() != thumb:
            img = portrait(dest.get("id") or "", thumb) or img
        screen.blit(img, (rect.x + pad, rect.y + (rect.h - thumb) // 2))
        pygame.draw.rect(
            screen, (20, 18, 14),
            (rect.x + pad, rect.y + (rect.h - thumb) // 2, thumb, thumb),
            1,
        )
        text_x = rect.x + pad + thumb + 8
    else:
        # Colour chip fallback
        chip = pygame.Rect(rect.x + pad, rect.y + pad, thumb, thumb)
        kind = dest.get("kind") or "place"
        pygame.draw.rect(screen, (210, 80, 70) if kind == "monster" else (220, 190, 100), chip, border_radius=4)
        text_x = chip.right + 8

    font = fonts.get("small") or fonts.get("tiny")
    tiny = fonts.get("tiny") or font
    if font is None:
        return
    label = dest.get("label") or dest.get("id") or "Place"
    if here:
        label = "You · " + label
    name = font.render(label[:28], True, (255, 240, 210) if here else (235, 230, 215))
    screen.blit(name, (text_x, rect.y + 6))
    blurb = (dest.get("blurb") or "").strip()
    if blurb and tiny is not None:
        b = tiny.render(blurb[:36], True, (170, 175, 185))
        screen.blit(b, (text_x, rect.y + 6 + name.get_height() + 2))


def draw_portrait_pin(screen, dest_id, cx, cy, size=28, here=False):
    """Circular place portrait pin on the map canvas."""
    img = portrait(dest_id, size)
    r = size // 2 + 2
    if img is None:
        return False
    # Soft shadow
    shadow = pygame.Surface((r * 2 + 4, r * 2 + 4), pygame.SRCALPHA)
    pygame.draw.circle(shadow, (0, 0, 0, 90), (r + 2, r + 3), r)
    screen.blit(shadow, (cx - r - 2, cy - r - 1))
    # Circular crop
    circ = pygame.Surface((size, size), pygame.SRCALPHA)
    circ.blit(img, (0, 0))
    mask = pygame.Surface((size, size), pygame.SRCALPHA)
    pygame.draw.circle(mask, (255, 255, 255, 255), (size // 2, size // 2), size // 2)
    circ.blit(mask, (0, 0), special_flags=pygame.BLEND_RGBA_MULT)
    screen.blit(circ, (cx - size // 2, cy - size // 2))
    ring = (120, 220, 140) if here else (255, 220, 120)
    pygame.draw.circle(screen, ring, (cx, cy), size // 2 + 1, 2)
    pygame.draw.circle(screen, (30, 24, 14), (cx, cy), size // 2 + 1, 1)
    return True
