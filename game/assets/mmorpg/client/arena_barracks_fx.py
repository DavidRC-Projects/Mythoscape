"""Barracks presentation helpers (5 Nov): recruit gladiator portraits, illustrated
practice commanders + army previews, try-on gear preview, training / level-up feedback.

Visual only — reads client.barracks payloads, never sends anything. Every helper
returns None / False when its art is missing so the caller keeps the previous look.
"""
from __future__ import annotations

import os
import time

import pygame

_HERE = os.path.dirname(os.path.abspath(__file__))
_CMD_DIR = os.path.join(_HERE, "assets", "castle_realm", "arena", "commanders")
_CACHE: dict = {}


# ---------------------------------------------------------------- portraits
def gladiator_bust(template_id, inner, headroom=8, gender="male"):
    """Head-and-shoulders crop of the template's arena gladiator sheet (what it looks like in the pit)."""
    k = ("glad", template_id, inner, gender)
    if k in _CACHE:
        return _CACHE[k]
    out = None
    try:
        import arena_battles_ui as ABU
        gid = ABU.gladiator_type({"template_id": template_id}, gender)
        got = ABU.gladiator_surface(gid, "s", 96, gender) if gid else None
        if got is not None:
            img = got[0]
            bb = img.get_bounding_rect(min_alpha=60)
            if bb.w > 4 and bb.h > 4:
                side = int(bb.w * 1.05)
                crop = pygame.Surface((side, side), pygame.SRCALPHA)
                crop.blit(img, (0, 0), pygame.Rect(bb.centerx - side // 2, bb.top, side, side))
                sc = pygame.transform.smoothscale(crop, (inner - 6, inner - 6))
                out = pygame.Surface((inner, inner), pygame.SRCALPHA)
                out.blit(sc, (3, headroom + 2))
    except Exception:  # noqa: BLE001
        out = None
    _CACHE[k] = out
    return out


def commander_portrait(foe_id, inner):
    k = ("cmd", foe_id, inner)
    if k in _CACHE:
        return _CACHE[k]
    out = None
    path = os.path.join(_CMD_DIR, f"{foe_id}.png")
    if os.path.isfile(path):
        try:
            out = pygame.transform.smoothscale(pygame.image.load(path).convert_alpha(), (inner, inner))
        except Exception:  # noqa: BLE001
            out = None
    _CACHE[k] = out
    return out


def army_strip(s, x, y, army, size=24, max_n=10, gap=2):
    """Row of tiny gladiator heads for a house army (template, gear) — returns width drawn."""
    drawn = 0
    for t, _g in list(army or [])[:max_n]:
        img = gladiator_bust(t, size, headroom=1)
        r = pygame.Rect(x + drawn, y, size, size)
        pygame.draw.rect(s, (24, 18, 12), r, border_radius=4)
        if img is not None:
            s.blit(img, r.topleft)
        pygame.draw.rect(s, (120, 96, 60), r, 1, border_radius=4)
        drawn += size + gap
    return drawn


# ---------------------------------------------------------------- training / level-up feedback
_PREV: dict = {}      # soldier id -> (levels, combat level)
FX: dict = {}         # soldier id -> {"t0", "gains": [(label, old, new)], "cl": (old, new)}
TOAST: dict = {"t0": 0.0, "text": ""}
FX_LIFE = 2.8
_LABEL = {"attack": "Attack", "strength": "Strength", "defence": "Defence", "hitpoints": "Hitpoints"}


def update(data):
    """Compare the latest roster with the last one seen; record gains for the glow + toast."""
    roster = (data or {}).get("roster") or []
    now = time.time()
    lines = []
    seen = set()
    for sol in roster:
        sid = sol.get("id")
        seen.add(sid)
        lv = dict(sol.get("levels") or {})
        cl = int(sol.get("combat_level") or 0)
        prev = _PREV.get(sid)
        _PREV[sid] = (lv, cl)
        if prev is None:
            continue
        gains = [(_LABEL.get(k, k), int(prev[0].get(k) or 0), int(v or 0)) for k, v in lv.items()
                 if int(v or 0) > int(prev[0].get(k) or 0)]
        if not gains:
            continue
        FX[sid] = {"t0": now, "gains": gains, "cl": (prev[1], cl)}
        bit = ", ".join(f"{g[0]} {g[1]} to {g[2]}" for g in gains[:2])
        if cl > prev[1]:
            bit += f" · CL {cl}!"
        lines.append(f"{sol.get('name')}: {bit}")
    for sid in list(_PREV):
        if sid not in seen:
            _PREV.pop(sid, None)
    if lines:
        more = f"  (+{len(lines) - 2} more)" if len(lines) > 2 else ""
        TOAST.update(t0=now, text="Trained — " + " · ".join(lines[:2]) + more)


def active(sid):
    f = FX.get(sid)
    if not f:
        return None
    age = time.time() - f["t0"]
    if age > FX_LIFE:
        FX.pop(sid, None)
        return None
    return f, age


def glow_chip(s, rect, age):
    """Gold pulse around a stat chip that just went up."""
    a = max(0.0, 1.0 - age / FX_LIFE)
    pulse = 0.6 + 0.4 * abs(((age * 3.0) % 2.0) - 1.0)
    col = (255, 214, 90)
    g = pygame.Surface((rect.w + 12, rect.h + 12), pygame.SRCALPHA)
    pygame.draw.rect(g, (*col, int(120 * a * pulse)), g.get_rect(), border_radius=8)
    s.blit(g, (rect.x - 6, rect.y - 6))
    pygame.draw.rect(s, col, rect.inflate(4, 4), 2, border_radius=6)


def float_text(s, font, text, center, age, col=(255, 222, 110), rise=26):
    a = max(0.0, 1.0 - age / FX_LIFE)
    img = font.render(text, True, col)
    img.set_alpha(int(255 * a))
    s.blit(img, img.get_rect(center=(center[0], int(center[1] - rise * min(1.0, age / 1.2)))))


def draw_toast(s, font, box):
    if not TOAST["text"]:
        return
    age = time.time() - TOAST["t0"]
    if age > 3.6:
        return
    a = 255 if age < 3.0 else int(255 * (3.6 - age) / 0.6)
    img = font.render(TOAST["text"][:110], True, (255, 226, 130))
    pad = pygame.Surface((img.get_width() + 28, img.get_height() + 14), pygame.SRCALPHA)
    pad.fill((40, 28, 12, 230))
    pygame.draw.rect(pad, (226, 190, 96), pad.get_rect(), 2, border_radius=8)
    pad.blit(img, (14, 7))
    pad.set_alpha(a)
    s.blit(pad, pad.get_rect(midbottom=(box.centerx, box.bottom - 30)))
