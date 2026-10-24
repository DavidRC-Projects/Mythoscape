"""
Slung gear: equipped weapons and shields drawn on a painted figure's back while idle or walking.

David, 23 Oct 2026: weapons and tools are painted into the action strips only. When the player is idle or
walking, the equipped weapon and shield show slung on the back of every painted figure (outfits and armour
sets). One small painted sprite per weapon kind and tier (player_hd/assets/slung/<kind>_<tier>_{back,side}.png),
anchored per frame from the strip's own mask (shoulder line and torso centre / back edge), so it rides the
walk cycle. South: behind the body. North: over it. East/west: the side sliver at the back edge.
Hidden during actions (those strips paint the gear in the hands).
"""
import os

import pygame

SLUNG_ANIMS = ("idle", "walk")
TIERS = ("bronze", "iron", "steel", "mithril", "adamant", "mythos", "eclipse")
_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "player_hd", "assets", "slung")

# size as a fraction of figure height, rotation (deg, counter-clockwise) in the back view
_SIZE = {"sword": 0.40, "axe": 0.36, "shield": 0.30}
_ANGLE = {"sword": -28.0, "axe": 26.0, "shield": 0.0}
_CENTRE_Y = {"sword": 0.29, "axe": 0.29, "shield": 0.37}   # sprite centre below the head top, x figure height

_SPRITES = {}
_ANCHORS = {}
_SCALED = {}


def item_kind(item_id):
    """(kind, tier) for a weapon / shield item id, else None. Unknown weapons (bows, staves, tools) don't sling."""
    s = str(item_id or "")
    if s.startswith("recruit_"):
        s = s[len("recruit_"):]
    tier = s.split("_", 1)[0]
    if tier not in TIERS:
        return None
    rest = s[len(tier) + 1:]
    if "shield" in rest:
        return "shield", tier
    if "pickaxe" in rest:
        return None
    if "axe" in rest or "cleaver" in rest:
        return "axe", tier
    if "sword" in rest or "scimitar" in rest or "dagger" in rest:
        return "sword", tier
    return None


def _sprite(kind, tier, view):
    key = (kind, tier, view)
    if key not in _SPRITES:
        surf = None
        for t in (tier, "bronze"):   # a tier without its own sprite yet borrows bronze's shape
            p = os.path.join(_DIR, f"{kind}_{t}_{view}.png")
            if os.path.isfile(p):
                surf = pygame.image.load(p)
                try:
                    surf = surf.convert_alpha()
                except pygame.error:
                    pass
                break
        _SPRITES[key] = surf
    return _SPRITES[key]


def frame_anchor(frame):
    """Per-frame back anchor from the strip mask: head top, figure height, torso centre x, back-edge x for
    a right-facing side view. Cached per frame surface."""
    key = id(frame)
    hit = _ANCHORS.get(key)
    if hit is not None and hit[0] is frame:
        return hit[1]
    import numpy as np
    a = pygame.surfarray.pixels_alpha(frame)
    m = np.asarray(a).T > 128          # rows = y
    del a
    rows = np.where(m.any(1))[0]
    if len(rows) < 8:
        _ANCHORS[key] = (frame, None)
        return None
    top, bot = int(rows[0]), int(rows[-1])
    h = bot - top
    y0, y1 = top + int(0.18 * h), top + int(0.42 * h)
    band = m[y0:y1]
    ys, xs = np.nonzero(band)
    cx = float(xs.mean()) if len(xs) else frame.get_width() / 2.0
    lefts = [np.argmax(r) for r in band if r.any()]
    rights = [len(r) - 1 - np.argmax(r[::-1]) for r in band if r.any()]
    anc = {"top": top, "h": h, "cx": cx,
           "left": float(np.median(lefts)) if lefts else cx, "right": float(np.median(rights)) if rights else cx}
    _ANCHORS[key] = (frame, anc)
    if len(_ANCHORS) > 4000:
        _ANCHORS.clear()
    return anc


def _scaled(kind, tier, view, fig_h, flip):
    src = _sprite(kind, tier, view)
    if src is None:
        return None
    length = max(4, int(round(_SIZE[kind] * fig_h)))
    key = (kind, tier, view, length, flip)
    out = _SCALED.get(key)
    if out is None:
        w = max(1, int(round(src.get_width() * length / float(src.get_height()))))
        out = pygame.transform.smoothscale(src, (w, length))
        ang = _ANGLE[kind] if view == "back" else _ANGLE[kind] * 0.25
        if flip:
            ang = -ang
            out = pygame.transform.flip(out, True, False)
        if ang:
            out = pygame.transform.rotozoom(out, ang, 1.0)
        _SCALED[key] = out
    return out


def slung_items(equipment):
    """Weapon first, then shield (the shield sits over the weapon on the back)."""
    out = []
    for slot in ("weapon", "shield"):
        k = item_kind((equipment or {}).get(slot))
        if k:
            out.append(k)
    return out


def draw(dest, frame, pos, visual_facing, equipment, phase):
    """phase 'under' (before the body is blitted) or 'over' (after). South draws under; n/e/w draw over."""
    items = slung_items(equipment)
    if not items or frame is None:
        return
    if (phase == "under") != (visual_facing == "s"):
        return
    anc = frame_anchor(frame)
    if not anc:
        return
    fx, fy = pos
    h = anc["h"]
    for kind, tier in items:
        cy = fy + anc["top"] + _CENTRE_Y[kind] * h
        if visual_facing in ("n", "s"):
            # seen from the front (s) the back is mirrored: the hilt peeks over the other shoulder
            spr = _scaled(kind, tier, "back", h, visual_facing == "s")
            if spr is None:
                continue
            cx = fx + anc["cx"]
            if kind != "shield" and len(items) > 1:
                cx += (0.03 * h) * (1 if visual_facing == "n" else -1)
        else:
            spr = _scaled(kind, tier, "side", h, visual_facing == "w")
            if spr is None:
                continue
            inset = (0.035 if kind == "shield" else 0.05) * h
            # east-facing figures carry their back on the left edge, west on the right
            cx = fx + (anc["left"] + inset if visual_facing == "e" else anc["right"] - inset)
        dest.blit(spr, (int(cx - spr.get_width() / 2.0), int(cy - spr.get_height() / 2.0)))
