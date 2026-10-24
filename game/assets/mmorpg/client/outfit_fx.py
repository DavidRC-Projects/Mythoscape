"""Elemental outfit effect layers (ELEMENTAL_EFFECTS_SPEC.md).

Each collection outfit with "fx" in the catalogue ships fx_back_<facing>.png / fx_front_<facing>.png
(16 frames, or 12 for Storm, 8 fps) in its layer folder plus fx.json. Back draws under the figure,
front over it (face already cut out of the strip). Modes: full / reduced / off, plus a separate
switch for other players' outfits. Reduced = 40% alpha, no ground tint, every other front frame.
Reduced is forced with more than 8 players on screen or in combat. Shop preview always plays Full.
A full armour set keeps only the back layer at 40% with no tint; Eclipse turns outfit fx off."""
import json
import os

import pygame

FPS = 8
MODES = ("full", "reduced", "off")
_SETTINGS = os.path.expanduser("~/.crownfall_client.json")
state = {"mode": "full", "others": True, "crowd": 0, "in_combat": False}
_CACHE = {}


def load_settings():
    try:
        with open(_SETTINGS) as f:
            d = json.load(f)
        if d.get("outfit_fx") in MODES:
            state["mode"] = d["outfit_fx"]
        state["others"] = bool(d.get("outfit_fx_others", True))
    except (OSError, ValueError):
        pass


def save_settings():
    try:
        d = {}
        if os.path.isfile(_SETTINGS):
            with open(_SETTINGS) as f:
                d = json.load(f)
        d["outfit_fx"], d["outfit_fx_others"] = state["mode"], state["others"]
        with open(_SETTINGS, "w") as f:
            json.dump(d, f)
    except (OSError, ValueError):
        pass


def cycle_mode():
    state["mode"] = MODES[(MODES.index(state["mode"]) + 1) % len(MODES)]
    save_settings()


def toggle_others():
    state["others"] = not state["others"]
    save_settings()


def set_context(players_on_screen=0, in_combat=False):
    state["crowd"], state["in_combat"] = int(players_on_screen), bool(in_combat)


def effective(is_self=True, preview=False, full_armour=False, eclipse=False):
    """-> (mode, back_alpha, front_on, tint_on) or None."""
    if eclipse:
        return None
    if preview:
        mode = "full"
    else:
        if not is_self and not state["others"]:
            return None
        mode = state["mode"]
        if mode == "off":
            return None
        if state["crowd"] > 8 or state["in_combat"]:
            mode = "reduced"
    if full_armour:
        return mode, 0.7, False, False
    if mode == "reduced":
        return mode, 0.7, True, False
    return mode, 1.0, True, True


GLOW = 0.55     # extra additive pass so the flow reads at normal zoom


def glow_surface(fr, strength=GLOW):
    """Blurred, brightened copy of an fx frame for an additive halo pass."""
    key = ("g", id(fr), fr.get_size(), strength)
    if key not in _CACHE:
        w, h = fr.get_size()
        pm = pygame.Surface((w, h)); pm.fill((0, 0, 0)); pm.blit(fr, (0, 0))   # premultiplied, opaque black
        small = pygame.transform.smoothscale(pm, (max(1, w // 4), max(1, h // 4)))
        g = pygame.transform.smoothscale(small, (w, h))
        g.fill((int(255 * strength),) * 3, special_flags=pygame.BLEND_RGB_MULT)
        g = g.convert() if pygame.display.get_surface() else g
        if len(_CACHE) > 600:
            _CACHE.clear()
        _CACHE[key] = g
    return _CACHE[key]


def frame_for(t, frames, mode, front):
    i = int((t or 0.0) * FPS) % max(1, frames)
    if front and mode == "reduced":
        i -= i % 2          # half the front frames
    return i


def _alpha(s, a):
    if s is None or a >= 0.999:
        return s
    key = ("a", id(s), round(a, 2))
    if key not in _CACHE:
        c = s.copy()
        c.fill((255, 255, 255, int(255 * a)), special_flags=pygame.BLEND_RGBA_MULT)
        _CACHE[key] = c
    return _CACHE[key]


def tint_surface(w, h, rgb, a=90):
    """Soft ground pool in the element colour (David, 24 Oct 2026: boosted so it reads at normal zoom)."""
    key = ("t", w, h, tuple(rgb), a)
    if key not in _CACHE:
        s = pygame.Surface((w, h), pygame.SRCALPHA)
        for i in range(4):
            r = s.get_rect().inflate(-int(w * 0.18 * i), -int(h * 0.18 * i))
            pygame.draw.ellipse(s, (*rgb, int(a * (0.35 + 0.22 * i))), r)
        _CACHE[key] = s
    return _CACHE[key]


load_settings()
