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
