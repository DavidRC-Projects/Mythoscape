"""HD cat and white husky. Always on. No 2D fallback for these two."""
from __future__ import annotations

import json
import os

import pygame

_DIR = os.path.normpath(os.path.join(
    os.path.dirname(__file__), "..", "..", "pets_hd",
))

_FOLDER = {
    "pet_cat": "pet_cat",
    "cat": "pet_cat",
    "pet_husky": "pet_husky",
    "husky": "pet_husky",
}

PETS_HD = {"pet_cat", "pet_husky"}

_META = {}
_IMAGES = {}
_CACHE_LIMIT = 256


def handles(sprite: str) -> bool:
    return sprite in _FOLDER


def baked_px(sprite: str, tile: int):
    if not handles(sprite):
        return None
    if not _load_meta(sprite).get("scale_baked"):
        return None
    return max(8, int(round(float(tile) * 1.1)))


def _folder(sprite: str) -> str:
    return _FOLDER.get(sprite, sprite)


def _load_meta(sprite: str) -> dict:
    folder = _folder(sprite)
    if folder not in _META:
        path = os.path.join(_DIR, folder, "meta.json")
        if not os.path.isfile(path):
            _META[folder] = {}
            return {}
        with open(path, encoding="utf-8") as f:
            _META[folder] = json.load(f)
    return _META[folder]


def _load_image(path: str):
    if path in _IMAGES:
        return _IMAGES[path]
    if not os.path.isfile(path):
        _IMAGES[path] = None
        return None
    img = pygame.image.load(path).convert_alpha()
    _IMAGES[path] = img
    if len(_IMAGES) > _CACHE_LIMIT:
        for key in list(_IMAGES.keys())[: len(_IMAGES) // 4]:
            _IMAGES.pop(key, None)
    return img


def _scaled(path: str, size: int, base: int):
    img = _load_image(path)
    if img is None:
        return None
    if size == base:
        return img
    cache_key = (path, size)
    if cache_key not in _IMAGES:
        w = max(1, int(round(img.get_width() * size / float(base))))
        h = max(1, int(round(img.get_height() * size / float(base))))
        _IMAGES[cache_key] = pygame.transform.smoothscale(img, (w, h))
    return _IMAGES[cache_key]


def _facing_str(face) -> str:
    if face in ("n", "e", "s", "w"):
        return face
    if face == "back":
        return "n"
    if face == "front":
        return "s"
    if isinstance(face, (int, float)):
        return "w" if face < 0 else "e"
    return "s"


def _frame_for_state(meta: dict, state: str, t: float, attacking: float, hit_t: float) -> int:
    if state == "idle":
        return int(((t * 1.5) % 1) * 4) % 4
    if state == "walk":
        return int(((t * 1.15) % 1) * 8) % 8
    if state == "attack":
        starts = meta.get("states", {}).get("attack", {}).get(
            "frame_starts", [0, 0.14, 0.30, 0.42, 0.60, 0.80],
        )
        for i in range(len(starts) - 1, -1, -1):
            if attacking >= starts[i]:
                return i
        return 0
    if state == "hit":
        return min(2, int(hit_t / 0.12))
    return 0


# v2 (mine_deeper): the 3D-rendered husky read as a flat grey blob in game.  A painted HD husky
# (pets_hd/pet_husky/painted/{n,e,s,w}.png, feet at bottom centre) replaces it, animated in code.
_PAINTED = {"pet_husky": {"n": 1.08, "e": 1.15, "s": 1.2, "w": 1.15}}   # height as a fraction of size


def _painted(sprite, face, h):
    folder = _folder(sprite)
    rel = _PAINTED.get(folder)
    if not rel:
        return None
    path = os.path.join(_DIR, folder, "painted", f"{face}.png")
    key = ("painted", path, h)
    if key in _IMAGES:
        return _IMAGES[key]
    img = _load_image(path)
    if img is None:
        return None
    w = max(1, int(round(img.get_width() * h / float(img.get_height()))))
    out = pygame.transform.smoothscale(img, (w, max(1, h)))
    _IMAGES[key] = out
    return out


def _draw_painted(screen, sprite, cx, foot_y, size, t, face, state, attacking, hit_t):
    import math
    frac = _PAINTED[_folder(sprite)].get(face, 1.0)
    h = int(round(size * frac))
    if state == "idle":
        h = int(round(h * (1.0 + 0.012 * math.sin(t * 2.6))))           # breathing
    img = _painted(sprite, face, h)
    if img is None:
        return False
    dx = dy = 0.0
    ang = 0.0
    if state == "walk":
        ph = t * 9.0
        dy = -abs(math.sin(ph)) * size * 0.05                               # trot bob
        if face in ("e", "w"):
            ang = math.sin(ph) * 2.5
    elif state == "attack":
        lunge = math.sin(min(1.0, max(0.0, attacking)) * math.pi)
        d = {"e": (1, 0), "w": (-1, 0), "n": (0, -0.5), "s": (0, 0.5)}[face]
        dx, dy = d[0] * lunge * size * 0.22, d[1] * lunge * size * 0.22 - lunge * size * 0.04
    if ang:
        img = pygame.transform.rotozoom(img, ang if face == "w" else -ang, 1.0)
    # soft contact shadow so the dog sits on the ground
    sw = int(img.get_width() * (0.8 if face in ("e", "w") else 0.9))
    sh = max(3, int(size * 0.14))
    key = ("pshadow", sw, sh)
    shadow = _IMAGES.get(key)
    if shadow is None:
        shadow = pygame.Surface((sw, sh), pygame.SRCALPHA)
        for i in range(sh // 2, 0, -1):
            a = int(70 * (1 - i / (sh / 2.0)) + 20)
            pygame.draw.ellipse(shadow, (0, 0, 0, a), (sw // 2 - i * sw // sh, sh // 2 - i, 2 * i * sw // sh, 2 * i))
        _IMAGES[key] = shadow
    screen.blit(shadow, shadow.get_rect(center=(int(cx), int(foot_y - sh * 0.15))))
    r = img.get_rect(midbottom=(int(cx + dx), int(foot_y + dy + size * 0.03)))
    screen.blit(img, r)
    if 0 <= hit_t < 0.36:
        flash = img.copy()
        flash.fill((255, 80, 80, 0), special_flags=pygame.BLEND_RGBA_MAX)
        flash.set_alpha(int(110 * (1 - hit_t / 0.36)))
        screen.blit(flash, r)
    return True


def draw(
    screen,
    sprite: str,
    cx: int,
    foot_y: int,
    size: int,
    t: float,
    facing=1,
    moving=False,
    attacking=-1.0,
    hit_t=-1.0,
) -> bool:
    if not handles(sprite):
        return False
    meta = _load_meta(sprite)
    if not meta or not meta.get("complete"):
        return False
    tag, base = ("2x", 80) if size > 40 else ("1x", 40)
    k = size / float(base)
    if attacking >= 0:
        state = "attack"
    elif 0 <= hit_t < 0.36:
        state = "hit"
    elif moving:
        state = "walk"
    else:
        state = "idle"
    face = _facing_str(facing)
    if _folder(sprite) in _PAINTED and _draw_painted(screen, sprite, cx, foot_y, size, t, face, state, attacking, hit_t):
        return True
    frame = _frame_for_state(meta, state, t, attacking, hit_t)
    path = os.path.join(_DIR, _folder(sprite), f"sprite_{tag}", state, face, f"f{frame:02d}.png")
    img = _scaled(path, size, base)
    if img is None:
        return False
    feet = meta.get("feet_px", {}).get(tag, [64, 132] if tag == "1x" else [128, 264])
    fx, fy = feet[0] * k, feet[1] * k
    screen.blit(img, (int(cx - fx), int(foot_y - fy)))
    return True


def head_top_dy(sprite: str, size: int, facing=1, state: str = "idle", frame: int = 0) -> int:
    """Screen y of the head, relative to the feet. Negative is above the feet."""
    meta = _load_meta(sprite)
    if not meta:
        return -size
    face = _facing_str(facing)
    if _folder(sprite) in _PAINTED and _painted(sprite, face, max(8, size)) is not None:
        return -int(round(size * _PAINTED[_folder(sprite)].get(face, 1.0)))
    anchors = meta.get("anchors_4x") or {}
    head = (anchors.get(f"{state}/{face}/{frame:02d}") or anchors.get("idle/s/00") or {}).get("head_top")
    feet = (meta.get("feet_px") or {}).get("4x") or [256, 528]
    if not head:
        return -max(8, size // 2)
    tag, base = ("2x", 80) if size > 40 else ("1x", 40)
    div = 4 if tag == "1x" else 2
    k = size / float(base)
    return int(round((head[1] - feet[1]) / div * k))


def blit_icon(surf, sprite: str, rect, facing=1) -> bool:
    """Idle frame fitted inside rect, feet toward the bottom."""
    if not handles(sprite):
        return False
    path = os.path.join(_DIR, _folder(sprite), "sprite_1x", "idle", _facing_str(facing), "f00.png")
    if _folder(sprite) in _PAINTED:
        pp = os.path.join(_DIR, _folder(sprite), "painted", _facing_str(facing) + ".png")
        if os.path.isfile(pp):
            path = pp
    img = _load_image(path)
    if img is None:
        return False
    bbox = img.get_bounding_rect()
    if bbox.width < 2 or bbox.height < 2:
        return False
    cropped = img.subsurface(bbox).copy()
    pad = 3
    avail_w = max(1, rect.w - pad * 2)
    avail_h = max(1, rect.h - pad * 2)
    scale = min(avail_w / cropped.get_width(), avail_h / cropped.get_height())
    fitted = pygame.transform.smoothscale(
        cropped,
        (max(1, int(cropped.get_width() * scale)), max(1, int(cropped.get_height() * scale))),
    )
    dest = fitted.get_rect(midbottom=(rect.centerx, rect.bottom - pad))
    surf.blit(fitted, dest)
    return True
