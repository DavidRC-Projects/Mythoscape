"""Overworld day/night tint and rain/snow particles (all outdoor zones)."""
from __future__ import annotations

import math
import random

import pygame

import world_map as wm

_PHASE_TINT = {
    "dawn": (255, 200, 160, 28),
    "day": (255, 245, 220, 0),
    "dusk": (255, 140, 80, 36),
    "night": (40, 55, 110, 72),
}
_MAX_RAIN = 160
_MAX_SNOW = 140
_pool = []
_mode = None
_surf = None
_surf_size = (0, 0)


def _env(client):
    return getattr(client, "env", None) or {}


def outdoors(client):
    """True on the shared overworld map (not private dungeon / castle-realm floors)."""
    if getattr(client, "dungeon", None):
        return False
    return bool(client.player)


# Back-compat alias
in_village = outdoors


def _indoor(client):
    if not client.player:
        return False
    px, py = int(client.player["x"]), int(client.player["y"])
    tiles = getattr(client, "tiles", None)
    if tiles and 0 <= py < len(tiles) and 0 <= px < getattr(client, "world_w", 0):
        if tiles[py][px] == wm.FLOOR:
            return True
    for b in getattr(client, "buildings", None) or []:
        if (
            b.get("floor_x0", 0) <= px <= b.get("floor_x1", -1)
            and b.get("floor_y0", 0) <= py <= b.get("floor_y1", -1)
        ):
            return True
    return False


def _ensure_pool(kind, w, h, intensity, indoor):
    global _pool, _mode
    cap = int((_MAX_RAIN if kind == "rain" else _MAX_SNOW) * (0.35 + 0.65 * intensity))
    if indoor:
        cap = max(8, int(cap * 0.3))
    if _mode != kind or len(_pool) != cap:
        _mode = kind
        rng = random.Random(7)
        _pool = []
        for _ in range(cap):
            _pool.append({
                "x": rng.uniform(0, w),
                "y": rng.uniform(-h * 0.2, h),
                "z": rng.uniform(0.6, 1.4),
                "w": rng.uniform(-0.35, 0.55),
            })


def _overlay_surface(w, h):
    global _surf, _surf_size
    if _surf is None or _surf_size != (w, h):
        _surf = pygame.Surface((w, h), pygame.SRCALPHA)
        _surf_size = (w, h)
    else:
        _surf.fill((0, 0, 0, 0))
    return _surf


def draw_phase_tint(client, map_w, map_h):
    if not outdoors(client):
        return
    env = _env(client)
    phase = env.get("phase") or "day"
    rgba = _PHASE_TINT.get(phase, _PHASE_TINT["day"])
    if rgba[3] <= 0:
        return
    overlay = _overlay_surface(map_w, map_h)
    overlay.fill(rgba)
    client.screen.blit(overlay, (0, 0))


def draw_precipitation(client, map_w, map_h, dt=1 / 60):
    if not outdoors(client):
        return
    env = _env(client)
    weather = env.get("weather") or "clear"
    intensity = float(env.get("intensity") or 0.0)
    if weather in ("clear", "windy_clear") or intensity <= 0.05:
        return
    kind = "snow" if "snow" in weather else "rain"
    indoor = _indoor(client)
    _ensure_pool(kind, map_w, map_h, intensity, indoor)
    overlay = _overlay_surface(map_w, map_h)
    wind = 0.55 if weather == "windy_clear" else (0.25 if kind == "rain" else 0.12)
    for p in _pool:
        z = p["z"]
        if kind == "rain":
            p["x"] += (40 + 90 * z) * wind * dt * 60 * 0.016
            p["y"] += (220 + 280 * z) * dt
            if p["y"] > map_h + 20 or p["x"] > map_w + 40:
                p["x"] = random.uniform(-20, map_w)
                p["y"] = random.uniform(-40, -4)
            length = int(8 + 10 * z)
            alpha = int(90 + 100 * intensity * min(1.0, z))
            col = (170, 190, 220, alpha)
            x0, y0 = int(p["x"]), int(p["y"])
            pygame.draw.line(overlay, col, (x0, y0), (x0 + int(3 * wind * 8), y0 + length), 1)
        else:
            p["x"] += (p["w"] * 28 + 18 * wind) * dt
            p["y"] += (28 + 50 * z) * dt
            if p["y"] > map_h + 10 or p["x"] < -10 or p["x"] > map_w + 10:
                p["x"] = random.uniform(0, map_w)
                p["y"] = random.uniform(-30, -2)
            r = max(1, int(1.2 + 1.8 * z))
            alpha = int(140 + 80 * intensity)
            pygame.draw.circle(overlay, (245, 250, 255, alpha), (int(p["x"]), int(p["y"])), r)
    client.screen.blit(overlay, (0, 0))


def draw(client, map_w, map_h):
    """Phase tint under weather particles. Call after world entities."""
    draw_phase_tint(client, map_w, map_h)
    draw_precipitation(client, map_w, map_h)
