"""Cached full-set siege player strips for the King's Castle map.

Versioned sword/axe/bow full-set strips. Existing fixtures remain a fallback.
"""
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Dict, Optional, Tuple

import pygame

_ROOT: Optional[Path] = None
_INDEX = None
_MANIFESTS: Dict[Tuple[str, str], dict] = {}
_STRIPS: Dict[Tuple[str, str, str, str], pygame.Surface] = {}
_CACHE_LIMIT = 48
_SCALED = {}

TIERS = ("bronze", "iron", "steel", "mithril", "adamant", "mythos", "eclipse")
FACINGS = ("s", "e", "n", "w")
WALK_HZ = 1.15
MELEE_S = 1.05
HIT_S = 0.36
DEATH_S = 1.2
CONTACT_PROGRESS = 0.48


def configure(assets_root: Path) -> None:
    global _ROOT, _INDEX
    if _ROOT == Path(assets_root) and _INDEX is not None:
        return
    _MANIFESTS.clear()
    _STRIPS.clear()
    _SCALED.clear()
    _ROOT = Path(assets_root)
    index = _ROOT / "siege_players" / "index.json"
    _INDEX = json.loads(index.read_text()) if index.is_file() else {"sets": []}


def _players_root() -> Optional[Path]:
    if _ROOT is not None:
        new = _ROOT / "siege_players_v2"
        return new if (new / "index.json").is_file() else _ROOT / "siege_players"
    # Default: beside baked_m9 under the linked fixtures.
    here = Path(__file__).resolve().parents[1] / "server" / "kcs_parity" / "assets" / "siege_players"
    return here if here.is_dir() else None


def full_tier(equipment) -> Optional[str]:
    """Strip tier for this loadout. A strict full set wins; otherwise the full body armour's tier
    (David t628u/t632u: body covers legs, so iron..eclipse bodies must not drop to the placeholder),
    then the helmet's tier."""
    try:
        from kcs_gear import full_armour_tier
        tier = full_armour_tier(equipment)
        if tier:
            return tier
    except Exception:
        pass
    eq = equipment or {}
    for slot, kinds in (("body", ("body", "chainbody")), ("helmet", ("helmet",))):
        s = str(eq.get(slot) or "")
        if s.startswith("recruit_"):
            s = s[len("recruit_"):]
        for tier in TIERS:
            if s in {f"{tier}_{k}" for k in kinds}:
                return tier
    return None


def weapon_family(equipment):
    from kcs_animation import weapon_family as classify
    return classify(equipment)


def weapon_supported(equipment) -> bool:
    # Unknown melee weapons retain a full-set generic melee presentation instead
    # of regressing to a tiny placeholder. No invented crossbow catalogue items.
    return True


def _manifest(kind: str, tier: str, weapon="sword") -> Optional[dict]:
    key = (kind, tier, weapon)
    if key in _MANIFESTS:
        return _MANIFESTS[key]
    root = _players_root()
    if root is None:
        return None
    path = root / kind / tier / weapon / "manifest.json"
    if not path.is_file():
        path = root / kind / tier / "manifest.json"
    if not path.is_file():
        return None
    data = json.loads(path.read_text())
    _MANIFESTS[key] = data
    return data


def _strip(kind: str, tier: str, anim: str, facing: str, weapon="sword") -> Optional[pygame.Surface]:
    key = (kind, tier, weapon, anim, facing)
    if key in _STRIPS:
        return _STRIPS[key]
    root = _players_root()
    if root is None:
        return None
    path = root / kind / tier / weapon / f"{anim}_{facing}.png"
    if not path.is_file():
        path = root / kind / tier / f"{anim}_{facing}.png"
    if not path.is_file():
        return None
    if len(_STRIPS) >= _CACHE_LIMIT:
        _STRIPS.pop(next(iter(_STRIPS)))
    surf = pygame.image.load(str(path)).convert_alpha()
    _STRIPS[key] = surf
    return surf


def frame_surface(kind: str, tier: str, anim: str, facing: str, frame: int, weapon="sword") -> Optional[pygame.Surface]:
    strip = _strip(kind, tier, anim, facing, weapon)
    man = _manifest(kind, tier, weapon)
    if strip is None or man is None:
        return None
    cw, ch = (man.get("cell") or [144, 144])[:2]
    frames = int((man.get("animations") or {}).get(anim, {}).get("frames") or 1)
    frame = max(0, min(frames - 1, int(frame)))
    rect = pygame.Rect(frame * int(cw), 0, int(cw), int(ch))
    if rect.right > strip.get_width() or rect.bottom > strip.get_height():
        return None
    return strip.subsurface(rect)


def choose_anim(moving: bool, melee_until: float, hit_until: float, dead: bool, now: float) -> Tuple[str, float]:
    if dead:
        return "death", DEATH_S
    if now < hit_until:
        return "hit", HIT_S
    if now < melee_until:
        return "melee", MELEE_S
    if moving:
        return "walk", 1.0 / WALK_HZ
    return "idle", 0.8


def shield_cell(kind, weapon, shield, anim, facing, progress, scale, frame=None):
    """(scaled shield cell, foot px, frame index, frame count) for the siege shield strip, or None."""
    if not shield or weapon == "bow" or _ROOT is None:
        return None
    folder = _ROOT / "siege_shields_v2" / kind / weapon / str(shield)
    meta_key = ("shield", kind, weapon, shield)
    man = _MANIFESTS.get(meta_key)
    if man is None:
        path = folder / "manifest.json"
        if not path.is_file():
            return None
        man = _MANIFESTS[meta_key] = json.loads(path.read_text())
    desc = man["animations"].get(anim)
    if desc is None:
        return None
    n = desc["frames"]
    if frame is None:
        frame = min(n-1, max(0, int(progress*n) if desc.get("loop") else round(progress*(n-1))))
    frame = max(0, min(n - 1, int(frame)))
    key = ("shield", kind, weapon, shield, anim, facing, frame, round(scale, 3))
    cached = _SCALED.get(key)
    if cached is None:
        skey = ("shield", kind, weapon, shield, anim, facing)
        strip = _STRIPS.get(skey)
        if strip is None:
            path = folder / f"{anim}_{facing}.png"
            if not path.is_file():
                return None
            if len(_STRIPS) >= _CACHE_LIMIT:
                _STRIPS.pop(next(iter(_STRIPS)))
            strip = _STRIPS[skey] = pygame.image.load(str(path)).convert_alpha()
        w, h = man["cell"]
        cell = strip.subsurface(pygame.Rect(frame*w, 0, w, h))
        if scale != 1:
            cell = pygame.transform.smoothscale(cell, (max(1,int(w*scale)), max(1,int(h*scale))))
        foot = [man["foot_px"][0]*scale, man["foot_px"][1]*scale]
        cached = (cell, foot)
        if len(_SCALED) >= 256:
            _SCALED.pop(next(iter(_SCALED)))
        _SCALED[key] = cached
    return cached[0], cached[1], frame, n


def _shield_blit(dest, kind, weapon, shield, anim, facing, progress, foot_screen, scale):
    got = shield_cell(kind, weapon, shield, anim, facing, progress, scale)
    if got is None:
        return
    cell, foot = got[0], got[1]
    dest.blit(cell, (int(foot_screen[0]-foot[0]), int(foot_screen[1]-foot[1])))


def actor_blit(
    dest,
    *,
    kind: str,
    tier: str,
    facing: str,
    anim: str,
    progress: float,
    foot_screen: Tuple[int, int],
    scale: float = 1.0,
    weapon: str = "sword",
    shield: str = None,
) -> bool:
    man = _manifest(kind, tier, weapon)
    if man is None:
        return False
    frames = int((man.get("animations") or {}).get(anim, {}).get("frames") or 1)
    progress = max(0.0, min(1.0, progress))
    loop = (man.get("animations") or {}).get(anim, {}).get("loop", False)
    # Non-looping strips include t=0 AND t=1; loops intentionally omit duplicate
    # end frames. Old sword strips had irregular sample times, not uniform ones.
    times = man.get("melee_progress") if anim == "melee" and man.get("version", 1) < 2 else None
    frame = max((i for i, t in enumerate(times) if t <= progress), default=0) if times else min(frames-1, int(progress*frames) if loop else round(progress*(frames-1)))
    cache_key = (kind, tier, weapon, anim, facing, frame, round(scale, 3))
    cached = _SCALED.get(cache_key)
    if cached is not None:
        cell, foot = cached
        dest.blit(cell, (int(foot_screen[0]-foot[0]), int(foot_screen[1]-foot[1])))
        _shield_blit(dest, kind, weapon, shield, anim, facing, progress, foot_screen, scale)
        return True
    cell = frame_surface(kind, tier, anim, facing, frame, weapon)
    if cell is None:
        return False
    foot = man.get("foot_px") or [72, 124]
    if scale != 1.0:
        cell = pygame.transform.smoothscale(
            cell, (max(1, int(cell.get_width() * scale)), max(1, int(cell.get_height() * scale)))
        )
        foot = [foot[0] * scale, foot[1] * scale]
    if len(_SCALED) >= 256:
        _SCALED.pop(next(iter(_SCALED)))
    _SCALED[cache_key] = (cell, foot)
    dest.blit(cell, (int(foot_screen[0] - foot[0]), int(foot_screen[1] - foot[1])))
    _shield_blit(dest, kind, weapon, shield, anim, facing, progress, foot_screen, scale)
    return True
