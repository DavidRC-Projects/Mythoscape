"""
Helmet overlay on outfit figures.

David, 23 Oct 2026: a helmet worn with an outfit keeps the outfit figure and paints that tier's helmet on top,
over the hair. One painted helmet per tier, male and female (the female one is the fitted, smaller helmet cut
from the female armour set), for s/e/n (w mirrors e). Anchored per frame to the head from the strip's own mask:
crown at the head top, centred on the head column, scaled by figure height.
Sprites: player_hd/assets/helmets/helmet_<tier>_<sex>_<view>.png + helmet_meta.json (crown row, source body
height, head centre x in sprite px).
"""
import json
import os

import pygame

HELMET_ANIMS = ("idle", "walk", "hit")
TIERS = ("bronze", "iron", "steel", "mithril", "adamant", "mythos", "eclipse")
_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "player_hd", "assets", "helmets")
_LIFT = 0.012          # crown sits this far (x figure height) above the hair top
_FEMALE_W = 0.94       # a touch narrower still on the female figure

_META = None
_SPRITES = {}
_SCALED = {}
_HEADS = {}


def helmet_tier(equipment):
    s = str((equipment or {}).get("helmet") or "")
    if s.startswith("recruit_"):
        s = s[len("recruit_"):]
    tier = s.split("_", 1)[0]
    return tier if tier in TIERS and ("helm" in s) else None


def _meta():
    global _META
    if _META is None:
        try:
            with open(os.path.join(_DIR, "helmet_meta.json")) as f:
                _META = json.load(f)
        except (OSError, ValueError):
            _META = {}
    return _META


def _sprite(key):
    if key not in _SPRITES:
        p = os.path.join(_DIR, f"helmet_{key}.png")
        surf = None
        if os.path.isfile(p):
            surf = pygame.image.load(p)
            try:
                surf = surf.convert_alpha()
            except pygame.error:
                pass
        _SPRITES[key] = surf
    return _SPRITES[key]


def head_anchor(frame):
    """(head top y, head centre x, figure height) from the frame mask; cached per frame surface."""
    hit = _HEADS.get(id(frame))
    if hit is not None and hit[0] is frame:
        return hit[1]
    import numpy as np
    a = pygame.surfarray.pixels_alpha(frame)
    m = np.asarray(a).T > 128
    del a
    rows = np.where(m.any(1))[0]
    res = None
    if len(rows) >= 8:
        top, bot = int(rows[0]), int(rows[-1])
        h = bot - top
        band = m[top + int(0.02 * h): top + int(0.07 * h) + 1]
        ys, xs = np.nonzero(band)
        if len(xs):
            res = (top, float(xs.mean()), h)
    _HEADS[id(frame)] = (frame, res)
    return res


def draw(dest, frame, pos, sex, visual_facing, equipment):
    tier = helmet_tier(equipment)
    if not tier or frame is None:
        return False
    view = {"s": "s", "e": "e", "w": "e", "n": "n"}.get(visual_facing, "s")
    key = f"{tier}_{sex}_{view}"
    meta = _meta().get(key)
    src = _sprite(key)
    anc = head_anchor(frame)
    if not meta or src is None or anc is None:
        return False
    top, hcx, h = anc
    flip = visual_facing == "w"
    # the facing anchor for w is measured on the already-mirrored frame; the sprite mirrors to match
    scale = h / float(meta["Hb"])
    sw = max(1, int(round(src.get_width() * scale * (_FEMALE_W if sex == "female" else 1.0))))
    sh = max(1, int(round(src.get_height() * scale)))
    ck = (key, sw, sh, flip)
    surf = _SCALED.get(ck)
    if surf is None:
        surf = pygame.transform.smoothscale(src, (sw, sh))
        if flip:
            surf = pygame.transform.flip(surf, True, False)
        _SCALED[ck] = surf
    mcx = meta["cx"] * sw / src.get_width()
    if flip:
        mcx = sw - mcx
    x = pos[0] + hcx - mcx
    y = pos[1] + top - _LIFT * h - meta["crown"] * scale
    dest.blit(surf, (int(round(x)), int(round(y))))
    return True


# ---- actions (David, 23 Oct 2026): the helmet stays on mid-swing ---------------------------------------
# A raised weapon breaks the head-top anchor, so action frames use per-frame head anchors precomputed by
# tools/helm_anchors.py (idle head matched into each action frame, guided by the face/skin): helmets/action_anchors.json.
_ACT = None


def _act():
    global _ACT
    if _ACT is None:
        try:
            with open(os.path.join(_DIR, "action_anchors.json")) as f:
                _ACT = json.load(f)
        except (OSError, ValueError):
            _ACT = {}
    return _ACT


def action_anchor(sex, layer, anim, file_facing, frame_idx, cell_w, cell_h):
    """(head top y, head centre x, figure height) in the unflipped frame, or None."""
    lst = _act().get(f"{sex}/{layer}/{anim}_{file_facing}")
    if not lst:
        return None
    a = lst[max(0, min(int(frame_idx), len(lst) - 1))]
    if not a:
        return None
    return a[0] * cell_h, a[1] * cell_w, a[2] * cell_h


def draw_action(dest, pos, sex, visual_facing, equipment, layer, anim, file_facing, frame_idx, frame, flip):
    if not helmet_tier(equipment) or frame is None:
        return False
    w, h = frame.get_size()
    anc = action_anchor(sex, layer, anim, file_facing, frame_idx, w, h)
    if anc is None:
        return False
    top, hcx, fh = anc
    if flip:
        hcx = w - hcx
    return _blit(dest, pos, sex, visual_facing, equipment, top, hcx, fh)


def _blit(dest, pos, sex, visual_facing, equipment, top, hcx, h):
    tier = helmet_tier(equipment)
    view = {"s": "s", "e": "e", "w": "e", "n": "n"}.get(visual_facing, "s")
    key = f"{tier}_{sex}_{view}"
    meta = _meta().get(key)
    src = _sprite(key)
    if not meta or src is None:
        return False
    flip = visual_facing == "w"
    scale = h / float(meta["Hb"])
    sw = max(1, int(round(src.get_width() * scale * (_FEMALE_W if sex == "female" else 1.0))))
    sh = max(1, int(round(src.get_height() * scale)))
    ck = (key, sw, sh, flip)
    surf = _SCALED.get(ck)
    if surf is None:
        surf = pygame.transform.smoothscale(src, (sw, sh))
        if flip:
            surf = pygame.transform.flip(surf, True, False)
        _SCALED[ck] = surf
    mcx = meta["cx"] * sw / src.get_width()
    if flip:
        mcx = sw - mcx
    dest.blit(surf, (int(round(pos[0] + hcx - mcx)), int(round(pos[1] + top - _LIFT * h - meta["crown"] * scale))))
    return True
