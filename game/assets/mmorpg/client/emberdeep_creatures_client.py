"""Billboard the Emberdeep creature pack. Idle contact strips are not drawn."""
from __future__ import annotations

import math
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
# How tall each creature is, compared with one floor tile.
_BODY = {
    "ember_imp": 0.78,
    "bile_toad": 0.92,
    "cinder_bitch": 1.05,
    "ash_warlock": 1.15,
    "troll_cook": 1.32,
    "mistress_of_cinders": 1.45,
    "emberdeep_wyrm": 2.05,
    "magma_slug": 0.42,
}
_CAP = {
    "ember_imp": 88,
    "bile_toad": 100,
    "cinder_bitch": 118,
    "ash_warlock": 128,
    "troll_cook": 148,
    "mistress_of_cinders": 160,
    "emberdeep_wyrm": 280,
    "magma_slug": 36,
}


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


def _blit(screen, img, cx, cy, height, squash=1.0, rock=0.0):
    height = max(8, int(height * squash))
    width = max(8, int(height * img.get_width() / max(1, img.get_height()) / max(0.75, squash)))
    scaled = pygame.transform.smoothscale(img, (width, height))
    if abs(rock) > 0.4:
        scaled = pygame.transform.rotate(scaled, rock)
    rect = scaled.get_rect(midbottom=(int(cx), int(cy)))
    screen.blit(scaled, rect)


def creature_height(creature_id, tile):
    """Pixel height for one creature. Imps stay small. The wyrm stays the largest."""
    scale = _BODY.get(creature_id, 1.0)
    cap = _CAP.get(creature_id, 96)
    return max(8, min(cap, int(tile * scale)))


# Slugs and the wyrm do not take steps. Toads hop. The rest plant one foot, then the other.
_GAIT = {
    "ember_imp": "biped",
    "cinder_bitch": "quad",
    "ash_warlock": "biped",
    "troll_cook": "biped",
    "mistress_of_cinders": "biped",
    "bile_toad": "hop",
}


def _step(kind, now, tile, facing):
    """Foot plant for a legged creature. Returns sway, bob, rock, squash."""
    side = 1.4 if facing not in ("front", "back") else 0.75
    if kind == "hop":
        phase = (now * 3.1) % 1.0
        lift = math.sin(phase * math.pi)
        squash = 0.84 if phase > 0.84 else 1.08 if phase < 0.16 else 1.0
        return 0, int(lift * tile * 0.2), 0.0, squash
    speed = 9.0 if kind == "quad" else 6.4
    rock_deg = 5.0 if kind == "quad" else 8.0
    step = math.sin(now * speed)
    # Highest between plants, lowest when a foot is down.
    bob = int((1.0 - abs(step)) * tile * (0.045 if kind == "quad" else 0.07))
    sway = int(step * tile * (0.06 if kind == "quad" else 0.09) * side)
    return sway, bob, step * rock_deg, 1.0


def draw_creature(screen, creature_id, cx, cy, tile, facing=1, breathing=False, moving=False, attacking=0.0):
    """Draw one pack creature at its feet. False leaves the normal monster chain."""
    if not feature_flags.USE_EMBERDEEP_CREATURES or creature_id not in _POSES:
        return False
    import time
    img = _frame(creature_id, facing, breathing)
    now = time.time()
    sway, bob, rock, squash = 0, 0, 0.0, 1.0
    kind = _GAIT.get(creature_id)
    if moving and kind:
        sway, bob, rock, squash = _step(kind, now, tile, facing)
    atk = max(0.0, min(1.0, float(attacking or 0)))
    if atk > 0 and creature_id != "emberdeep_wyrm":
        strike = math.sin(atk * math.pi)
        bob -= int(strike * max(4, tile * 0.16))
        squash = 1.0 + 0.16 * strike
        rock = 0.0
        sway = int(strike * max(3, tile * 0.08))
    height = creature_height(creature_id, tile)
    _blit(screen, img, cx + sway, cy - bob, height, squash, rock)
    return True


_PROP_SCALE = {
    "dragon_egg": 1.15,
    "dragon_egg_b": 1.05,
    "dragon_egg_c": 1.25,
    "ash_urn": 0.95,
    "candle_cluster": 0.72,
    "coin_heap": 0.9,
    "chain_stake": 1.15,
    "toadstool": 0.8,
    "cinder_vent": 0.7,
    "egg_cluster": 1.05,
}


def draw_prop(screen, key, cx, cy, tile):
    if not feature_flags.USE_EMBERDEEP_CREATURES:
        return False
    path = os.path.join(_ROOT, "props", f"{key}.png")
    if not os.path.isfile(path):
        return False
    scale = _PROP_SCALE.get(key, 1.05)
    _blit(screen, _load(os.path.join("props", f"{key}.png")), cx, cy, tile * scale)
    return True


def draw_cone(screen, cx, cy, tile):
    if not feature_flags.USE_EMBERDEEP_CREATURES:
        return
    img = _load(os.path.join("fx", "fire_cone.png"))
    _blit(screen, img, cx, cy, tile * 2.2)
