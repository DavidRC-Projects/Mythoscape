"""Billboard the Emberdeep creature pack. Idle contact strips are not drawn."""
from __future__ import annotations

import os

import pygame

import feature_flags

_ROOT = os.path.normpath(os.path.join(
    os.path.dirname(__file__), "..", "assets", "emberdeep_creatures",
))
_CACHE = {}
_POSES = {
    "ember_imp": "quad",
    "bile_toad": "quad",
    "cinder_bitch": "quad",
    "ash_warlock": "quad",
    "troll_cook": "quad",
    "mistress_of_cinders": "quad",
    "emberdeep_wyrm": "wyrm",
}
_WYRM_SCALE = 2.5


def _load(rel):
    if rel not in _CACHE:
        img = pygame.image.load(os.path.join(_ROOT, rel))
        if pygame.display.get_surface() is not None:
            img = img.convert_alpha()
        _CACHE[rel] = img
    return _CACHE[rel]


def _pose_name(facing):
    if facing == "back":
        return "back"
    if facing == "front":
        return "front"
    try:
        if float(facing) < 0:
            return "side_west"
    except (TypeError, ValueError):
        pass
    return "side_east"


def _frame(creature_id, facing, breathing):
    pose = _pose_name(facing)
    if creature_id == "emberdeep_wyrm":
        # The wyrm stays facing south. The breath uses the front sheet.
        name = "fire_breath_front.png" if breathing else "idle_front.png"
        return _load(os.path.join("emberdeep_wyrm", name))
    return _load(os.path.join(creature_id, f"{pose}.png"))


def _blit(screen, img, cx, cy, height):
    height = max(8, int(height))
    width = max(8, int(height * img.get_width() / max(1, img.get_height())))
    scaled = pygame.transform.smoothscale(img, (width, height))
    screen.blit(scaled, (int(cx - width / 2), int(cy - height)))


def draw_creature(screen, creature_id, cx, cy, tile, facing=1, breathing=False):
    """Draw one pack creature at its feet. False leaves the normal monster chain."""
    if not feature_flags.USE_EMBERDEEP_CREATURES or creature_id not in _POSES:
        return False
    img = _frame(creature_id, facing, breathing)
    height = tile * (1.35 * _WYRM_SCALE if creature_id == "emberdeep_wyrm" else 1.35)
    _blit(screen, img, cx, cy, height)
    return True


def draw_prop(screen, key, cx, cy, tile):
    if not feature_flags.USE_EMBERDEEP_CREATURES:
        return False
    path = os.path.join(_ROOT, "props", f"{key}.png")
    if not os.path.isfile(path):
        return False
    _blit(screen, _load(os.path.join("props", f"{key}.png")), cx, cy, tile * 1.2)
    return True


def draw_cone(screen, cx, cy, tile):
    if not feature_flags.USE_EMBERDEEP_CREATURES:
        return
    img = _load(os.path.join("fx", "fire_cone.png"))
    _blit(screen, img, cx, cy, tile * 2.2)
