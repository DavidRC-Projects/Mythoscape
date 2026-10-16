"""Worn-gear sparkle overlay (client-side, runtime only; sprites are untouched).

Eclipse (gold) sparkles with ANY Eclipse piece equipped. Dragon Mythos (light red),
Adamantite (light green) and Mithril (light blue) sparkle only with the full
helmet + body + legs set of that tier. Bronze, Iron, Steel, NPCs, monsters and
pets get nothing. Every tier uses the same algorithm; only colours change.
"""
from __future__ import annotations

import math
import random
import zlib
from collections import OrderedDict

import pygame

# Order = rank, highest first. Exact item ids only (never prefix matches).
SPARKLE_TIERS = {
    "eclipse": {
        "any_piece": True,
        "ids": {"eclipse_helmet", "eclipse_body", "eclipse_legs", "eclipse_shield",
                "eclipse_sword", "eclipse_cleaver"},
        "aura": (255, 190, 70), "star": (255, 215, 90), "core": (255, 245, 210),   # gold
    },
    "mythos": {
        "ids": {"mythos_helmet", "mythos_body", "mythos_legs", "mythos_shield", "mythos_longsword"},
        "full_set": {"helmet": {"mythos_helmet"}, "body": {"mythos_body"}, "legs": {"mythos_legs"}},
        "aura": (255, 110, 100), "star": (255, 140, 130), "core": (255, 225, 220),  # light red
    },
    "adamant": {
        "ids": {"adamant_helmet", "adamant_body", "adamant_legs", "adamant_chainbody", "adamant_chainlegs",
                "adamant_shield", "adamant_sq_shield", "adamant_sword", "adamant_battleaxe"},
        "full_set": {"helmet": {"adamant_helmet"}, "body": {"adamant_body", "adamant_chainbody"},
                     "legs": {"adamant_legs", "adamant_chainlegs"}},
        "aura": (120, 230, 130), "star": (150, 245, 160), "core": (225, 255, 228),  # light green
    },
    "mithril": {
        "ids": {"mithril_helmet", "mithril_body", "mithril_legs", "mithril_chainbody", "mithril_chainlegs",
                "mithril_shield", "mithril_sq_shield", "mithril_sword", "mithril_battleaxe"},
        "full_set": {"helmet": {"mithril_helmet"}, "body": {"mithril_body", "mithril_chainbody"},
                     "legs": {"mithril_legs", "mithril_chainlegs"}},
        "aura": (120, 180, 255), "star": (150, 200, 255), "core": (225, 238, 255),  # light blue
    },
}

_AURA_CACHE: "OrderedDict[tuple, pygame.Surface]" = OrderedDict()
_AURA_CACHE_MAX = 256


def fx_tier(equipment):
    """SPARKLE_TIERS key for this equipment dict, or None."""
    eq = equipment or {}
    worn = {v for v in eq.values() if v}
    for tier, spec in SPARKLE_TIERS.items():
        if spec.get("any_piece"):
            if worn & spec["ids"]:
                return tier
            continue
        full = spec.get("full_set") or {}
        if full and all(eq.get(slot) in ids for slot, ids in full.items()):
            return tier
    return None


def _blur(surf, radius):
    """Cheap blur: smoothscale down then up (pygame 2.x has no gaussian_blur)."""
    w, h = surf.get_size()
    f = max(1.0, radius)
    small = pygame.transform.smoothscale(surf, (max(1, int(w / f)), max(1, int(h / f))))
    small = pygame.transform.smoothscale(small, (max(1, int(w / f * 2)), max(1, int(h / f * 2))))
    return pygame.transform.smoothscale(small, (w, h))


def _mask_surface(sprite):
    mask = pygame.mask.from_surface(sprite, 170)   # > 170 drops the soft floor shadow
    return mask.to_surface(setcolor=(255, 255, 255, 255), unsetcolor=(0, 0, 0, 0))


def aura_surface(sprite_surface, zoom, tier, key=None):
    """Soft tier-coloured glow from the sprite alpha. Cached (LRU 256)."""
    if key is None:
        key = (zlib.crc32(pygame.image.tobytes(sprite_surface, "RGBA")), sprite_surface.get_size())
    ck = (tier, round(float(zoom), 3), key)
    hit = _AURA_CACHE.get(ck)
    if hit is not None:
        _AURA_CACHE.move_to_end(ck)
        return hit
    base = _mask_surface(sprite_surface)
    dil = base.copy()
    d = 2
    for dx, dy in ((-d, 0), (d, 0), (0, -d), (0, d), (-d, -d), (d, d), (-d, d), (d, -d)):
        dil.blit(base, (dx, dy), special_flags=pygame.BLEND_RGBA_MAX)
    blurred = _blur(dil, max(2.5, 4.0 * float(zoom)))
    rgb = SPARKLE_TIERS[tier]["aura"]
    tint = pygame.Surface(blurred.get_size(), pygame.SRCALPHA)
    tint.fill((rgb[0], rgb[1], rgb[2], int(255 * 0.62)))
    blurred.blit(tint, (0, 0), special_flags=pygame.BLEND_RGBA_MULT)
    _AURA_CACHE[ck] = blurred
    if len(_AURA_CACHE) > _AURA_CACHE_MAX:
        _AURA_CACHE.popitem(last=False)
    return blurred


def player_seed(player_id):
    return zlib.crc32(str(player_id).encode("utf-8")) & 0xFFFF


def draw_sparkles(screen, bbox, t, zoom, seed, tier, n=10):
    """Tiny 4-point stars drifting around bbox; never inside the face/grille box."""
    spec = SPARKLE_TIERS[tier]
    x0, y0, w, h = bbox
    if w <= 0 or h <= 0:
        return
    x1, y1 = x0 + w, y0 + h
    cx = x0 + w / 2.0
    face = (x0 + w * 0.25, y0 + h * 0.04, x1 - w * 0.25, y0 + h * 0.20)
    lw = 2 if zoom > 1.2 else 1
    rnd = random.Random(seed)
    for _ in range(n):
        ph = rnd.random() * 6.283
        sp = 0.6 + rnd.random() * 0.6
        life = (t * 0.25 * sp + rnd.random()) % 1.0
        ang = ph + t * 0.9 * sp
        x = cx + math.cos(ang) * w * (0.45 + 0.15 * rnd.random())
        y = y1 - h * (0.15 + 0.8 * ((rnd.random() + life * 0.35) % 1.0))
        if face[0] < x < face[2] and face[1] < y < face[3]:
            continue
        tw = max(0.0, math.sin(math.pi * life)) * (0.6 + 0.4 * math.sin(t * 7 + ph))
        if tw < 0.15:
            continue
        r = max(2.5, 3.6 * zoom) * (0.6 + 0.6 * tw)
        al = int(235 * tw)
        size = int(r * 2 + 6)
        star = pygame.Surface((size, size), pygame.SRCALPHA)
        c = size / 2.0
        col = (*spec["star"], al)
        pygame.draw.line(star, col, (c - r, c), (c + r, c), lw)
        pygame.draw.line(star, col, (c, c - r), (c, c + r), lw)
        pygame.draw.circle(star, (*spec["core"], al), (int(c), int(c)), 1.5)
        screen.blit(star, (int(x - c), int(y - c)))
