"""Client-only Emberdeep attack, hit and death motion. Timing stays on the server."""
from __future__ import annotations

import math
import os

import pygame

_CONE = os.path.normpath(os.path.join(
    os.path.dirname(__file__), "..", "..", "emberdeep_creatures_pack", "fx", "fire_cone.png",
))
_CONE_IMG = None


def _toward(monster, player):
    vx = (player["x"] + 0.5) - (monster["x"] + 0.5)
    vy = (player["y"] + 0.5) - (monster["y"] + 0.5)
    length = math.hypot(vx, vy) or 1.0
    return vx / length, vy / length


def attack_pose(client, monster, now):
    """World-tile offset and squash for a swing. Contact stays at progress 0.48."""
    progress = client._attack_progress(monster["id"], now)
    if progress <= 0 or not client.player:
        return 0.0, 0.0, 1.0
    vx, vy = _toward(monster, client.player)
    if progress < 0.30:
        u = progress / 0.30
        return -vx * 0.08 * u, -vy * 0.08 * u, 1.0 - 0.06 * u
    if progress < 0.48:
        u = (progress - 0.30) / 0.18
        return vx * 0.28 * u, vy * 0.28 * u, 1.0 + 0.06 * u
    u = min(1.0, (progress - 0.48) / 0.52)
    return vx * 0.28 * (1.0 - u), vy * 0.28 * (1.0 - u), 1.0 + 0.06 * (1.0 - u)


def contact(client, monster, now):
    progress = client._attack_progress(monster["id"], now)
    return 0.48 <= progress <= 0.56


def hit_pose(client, monster, now):
    """Knock-back and flash strength for 0.25s after the strike."""
    start = (getattr(client, "monster_hit_at", None) or {}).get(monster["id"])
    if start is None or now < start or now > start + 0.25 or not client.player:
        return 0.0, 0.0, 0.0
    u = (now - start) / 0.25
    vx, vy = _toward(monster, client.player)
    return -vx * 0.12 * (1.0 - u), -vy * 0.12 * (1.0 - u), 0.6 * (1.0 - u)


def shake_offset(client, now):
    start = getattr(client, "_ember_shake_from", 0.0)
    until = getattr(client, "_ember_shake_until", 0.0)
    if now < start or now > until:
        return 0, 0
    return (2, 0) if int(now * 40) % 2 == 0 else (-2, 0)


def flash_surface(surface, strength):
    if strength <= 0.01:
        return surface
    tinted = surface.copy()
    gain = strength / 0.6
    tinted.fill(
        (int(110 * gain), int(40 * gain), int(30 * gain)),
        special_flags=pygame.BLEND_RGB_ADD,
    )
    return tinted


def draw_embers(screen, x, y, age):
    for i in range(6):
        rise = age * (18 + i * 6)
        px = int(x + math.sin(age * 8 + i) * (6 + i))
        py = int(y - rise)
        radius = max(1, 4 - int(age * 3))
        pygame.draw.circle(screen, (255, 120 + i * 12, 40), (px, py), radius)


def _cone_image():
    global _CONE_IMG
    if _CONE_IMG is None and os.path.isfile(_CONE):
        _CONE_IMG = pygame.image.load(_CONE).convert_alpha()
    return _CONE_IMG
