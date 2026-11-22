"""First-person throne room walk-in + AI coronation video (David t664u-t668u).

After the win card: a slow dolly down the carpet into assets/victory/throne_room_fp.jpg split into three
soft depth layers (back throne / mid hall / foreground pillars) that zoom at different rates, with a
head-bob, flickering braziers and a vignette. It stops near the dais with a 'Sit on the throne' button;
clicking plays assets/victory/coronation.mp4 full screen (cv2; the video's audio is muted so
'Coronation of the Realm' keeps playing). Esc/click at the end returns to the game.
kcs_victory_scene falls back to its old procedural cutscene when anything here fails.
"""
from __future__ import annotations

import math
import os
import random
import time

import pygame

_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets", "victory")
IMAGE = os.path.join(_DIR, "throne_room_fp.jpg")
VIDEO = os.path.join(_DIR, "coronation.mp4")
WALK = 7.5                     # seconds of walk-in
VANISH = (0.5, 0.60)           # carpet vanishing point (fraction of the image) - the dais
ZOOM = {"back": 1.32, "mid": 1.45, "fore": 1.62}   # end zoom per layer
BRAZIERS = ((143, 283, "fore"), (892, 283, "fore"), (310, 322, "mid"), (722, 322, "mid"),
            (378, 338, "back"), (656, 338, "back"), (517, 18, "back"))
_CACHE = {}


def available() -> bool:
    return os.path.isfile(IMAGE)


def _layers():
    if "layers" in _CACHE:
        return _CACHE["layers"]
    import numpy as np
    base = pygame.image.load(IMAGE).convert()
    w, h = base.get_size()
    xs = (np.arange(w)[:, None] / w - .5) * np.ones((1, h))
    ys = np.ones((w, 1)) * (np.arange(h)[None, :] / h - VANISH[1])
    r = np.sqrt((xs * 1.0) ** 2 + (ys * 0.9) ** 2)
    def make(alpha):
        s = base.convert_alpha()
        a = pygame.surfarray.pixels_alpha(s)
        a[:, :] = (np.clip(alpha, 0, 1) * 255).astype("uint8")
        del a
        return s
    mid = np.clip((r - .17) / .10, 0, 1)                          # everything but the throne/back wall
    fore = np.clip((np.abs(xs) - .33) / .06, 0, 1)               # outer pillars + front braziers
    fore = np.maximum(fore, np.clip((ys - .30) / .08, 0, 1) * np.clip((np.abs(xs) - .22) / .06, 0, 1))
    _CACHE["layers"] = (base, make(mid), make(fore))
    return _CACHE["layers"]


def _vignette(size):
    key = ("vig", size)
    if key not in _CACHE:
        import numpy as np
        w, h = size
        xs = (np.arange(w)[:, None] / w - .5) * 2
        ys = (np.arange(h)[None, :] / h - .5) * 2
        d = np.clip(np.sqrt(xs ** 2 + ys ** 2) - .55, 0, 1)
        s = pygame.Surface(size, pygame.SRCALPHA)
        s.fill((0, 0, 0, 0))
        a = pygame.surfarray.pixels_alpha(s)
        a[:, :] = (np.clip(d * 1.4, 0, .85) * 255).astype("uint8")
        del a
        _CACHE[key] = s
    return _CACHE[key]


def _ease(x):
    x = max(0.0, min(1.0, x))
    return 1 - (1 - x) ** 3


def _blit_layer(screen, src, zoom, bob, cover):
    """Crop the part of the image that a zoom about the vanishing point shows, scale it to the screen."""
    sw, sh = screen.get_size()
    iw, ih = src.get_size()
    vx, vy = iw * VANISH[0], ih * VANISH[1]
    k = cover * zoom                                   # screen px per image px
    cw, ch = sw / k, sh / k
    x0 = vx - cw / 2
    y0 = vy - ch * VANISH[1] - bob / k
    rect = pygame.Rect(int(x0), int(y0), max(1, int(cw)), max(1, int(ch))).clip(src.get_rect())
    if rect.w < 2 or rect.h < 2:
        return
    part = pygame.transform.smoothscale(src.subsurface(rect), (max(1, int(rect.w * k)), max(1, int(rect.h * k))))
    screen.blit(part, (int((rect.x - x0) * k), int((rect.y - y0) * k)))
    return x0, y0, k


def _button_rect(screen):
    sw, sh = screen.get_size()
    r = pygame.Rect(0, 0, 340, 64)
    r.midbottom = (sw // 2, sh - 46)
    return r


def draw(screen, t, state) -> str | None:
    """t = seconds since the walk began. Returns 'done' when the scene is over."""
    if state.get("video") is not None:
        return _draw_video(screen, state)
    sw, sh = screen.get_size()
    back, mid, fore = _layers()
    iw, ih = back.get_size()
    cover = max(sw / iw, sh / ih)
    p = 1.0 if state.get("arrived") else _ease(t / WALK)
    if p >= 1.0:
        state["arrived"] = True
    walking = p < 1.0
    bob = math.sin(t * 2 * math.pi * 0.95) * 5 * (1 - p) if walking else math.sin(t * 1.3) * 1.2
    screen.fill((6, 4, 4))
    geo = {}
    for name, src in (("back", back), ("mid", mid), ("fore", fore)):
        z = 1 + (ZOOM[name] - 1) * p
        geo[name] = _blit_layer(screen, src, z, bob * (0.6 if name == "back" else 1.0 if name == "mid" else 1.6), cover)
    # brazier flicker: additive warm glow over each flame
    glow = pygame.Surface((sw, sh))
    glow.fill((0, 0, 0))
    for bx, by, layer in BRAZIERS:
        g = geo.get(layer)
        if not g:
            continue
        x0, y0, k = g
        sx, sy = (bx - x0) * k, (by - y0) * k
        flick = .65 + .35 * math.sin(t * 9.1 + bx) * math.sin(t * 5.3 + by) + random.uniform(-.08, .08)
        rad = max(6, int(16 * k * (0.85 + .15 * flick)))
        for i, frac in enumerate((1.0, .62, .34)):
            c = int((10 + 12 * i) * flick)
            pygame.draw.circle(glow, (c * 2, int(c * 1.1), c // 3), (int(sx), int(sy)), max(3, int(rad * frac)))
    screen.blit(glow, (0, 0), special_flags=pygame.BLEND_RGB_ADD)
    screen.blit(_vignette((sw, sh)), (0, 0))
    if not walking:
        r = _button_rect(screen)
        pulse = (math.sin(t * 3) + 1) / 2
        halo = pygame.Surface((r.w + 30, r.h + 30), pygame.SRCALPHA)
        pygame.draw.rect(halo, (255, 205, 90, int(50 + 70 * pulse)), halo.get_rect(), border_radius=24)
        screen.blit(halo, (r.x - 15, r.y - 15))
        pygame.draw.rect(screen, (232, 186, 82), r, border_radius=16)
        pygame.draw.rect(screen, (110, 64, 18), r, 3, border_radius=16)
        font = pygame.font.Font(None, 44)
        label = font.render("Sit on the throne", True, (40, 22, 6))
        screen.blit(label, label.get_rect(center=r.center))
    else:
        font = pygame.font.Font(None, 30)
        a = max(0, min(255, int(255 * min(t / 1.0, (WALK - t) / 1.0))))
        txt = font.render("The throne room lies open before you.", True, (244, 226, 180))
        txt.set_alpha(a)
        screen.blit(txt, txt.get_rect(midtop=(sw // 2, 28)))
    if t < .6:
        veil = pygame.Surface((sw, sh), pygame.SRCALPHA)
        veil.fill((0, 0, 0, int(255 * (1 - t / .6))))
        screen.blit(veil, (0, 0))
    return None


def _start_video(state) -> bool:
    try:
        import cv2
        cap = cv2.VideoCapture(VIDEO)
        if not cap.isOpened():
            return False
        state["video"] = {"cap": cap, "fps": float(cap.get(cv2.CAP_PROP_FPS) or 24.0), "t0": time.time(),
                          "index": -1, "frame": None}
        return True
    except Exception:
        return False


def _draw_video(screen, state):
    import cv2
    v = state["video"]
    want = int((time.time() - v["t0"]) * v["fps"])
    while v["index"] < want:
        ok, frame = v["cap"].read()
        if not ok:
            stop_video(state)
            return "done"
        v["index"] += 1
        v["frame"] = frame
    frame = v["frame"]
    if frame is None:
        return None
    sw, sh = screen.get_size()
    fh, fw = frame.shape[:2]
    k = min(sw / fw, sh / fh)
    w, h = int(fw * k), int(fh * k)
    rgb = cv2.cvtColor(cv2.resize(frame, (w, h), interpolation=cv2.INTER_LINEAR), cv2.COLOR_BGR2RGB)
    img = pygame.image.frombuffer(rgb.tobytes(), (w, h), "RGB")
    screen.fill((0, 0, 0))
    screen.blit(img, ((sw - w) // 2, (sh - h) // 2))
    return None


def stop_video(state):
    v = state.pop("video", None)
    if v:
        try:
            v["cap"].release()
        except Exception:
            pass
    state["video"] = None


def handle_event(event, state, screen) -> str | None:
    """'done' = end the whole sequence; 'failed' = video could not play (caller falls back)."""
    if event.type not in (pygame.KEYDOWN, pygame.MOUSEBUTTONDOWN):
        return None
    if state.get("video") is not None:
        stop_video(state)
        return "done"
    if not state.get("arrived"):
        state["arrived"] = True          # click/key during the walk jumps to the dais
        return None
    if event.type == pygame.MOUSEBUTTONDOWN and getattr(event, "button", 1) == 1 and _button_rect(screen).collidepoint(event.pos):
        return None if _start_video(state) else "failed"
    if event.type == pygame.KEYDOWN and event.key in (pygame.K_RETURN, pygame.K_SPACE):
        return None if _start_video(state) else "failed"
    if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
        return "done"
    return None
