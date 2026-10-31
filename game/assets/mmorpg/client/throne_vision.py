"""Throne vision: the 42 s intro film, played once at a new account's first login and
replayable from Settings.

The client has no video decoder (no ffmpeg / opencv), so the film ships pre-extracted:
assets/throne_vision/frames/0001.jpg … (1280x720, 24 fps, from throne_vision_v4.mp4) and
audio.ogg. The audio plays on its own mixer channel and is the clock: each draw shows the
frame for the time since the audio started, so a slow frame is dropped rather than letting
the picture drift from the sound. Frames are decoded one at a time (about 5 ms each) and
scaled to fit the window, letterboxed.

Any key, any click, or the Skip button ends it. The first viewing tells the server
(THRONE_VISION_SEEN), which keeps the played flag per account.
Music: "Five Armies" by Kevin MacLeod (incompetech.com), CC BY 4.0.
"""
from __future__ import annotations

import json
import os

import pygame

DIR = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", "assets", "throne_vision"))
CREDIT = "Five Armies by Kevin MacLeod (incompetech.com), CC BY 4.0"
INPUT_GRACE_MS = 300          # a key still held from the login screen must not skip it
_META = None
_SOUND = None
_STATE = {}


def meta():
    global _META
    if _META is None:
        try:
            with open(os.path.join(DIR, "meta.json")) as f:
                _META = json.load(f)
        except (OSError, ValueError):
            _META = {}
    return _META


def available():
    m = meta()
    return bool(m) and os.path.isfile(_frame_path(1))


def _frame_path(i):
    pat = meta().get("frame_pattern", "frames/%04d.jpg")
    return os.path.join(DIR, pat % i)


def frame_count():
    return int(meta().get("frames", 0))


def fps():
    return float(meta().get("fps", 24))


def frame_for_ms(ms):
    """1-based frame index shown at ms since the start (clamped to the film)."""
    n = frame_count()
    return max(1, min(n, int(ms * fps() / 1000.0) + 1)) if n else 1


def begin(client, replay=False):
    """Switch the client to the film. replay=True: from Settings (no server flag)."""
    global _SOUND
    if not available():
        client.throne_vision_prev = getattr(client, "state", "GAME") if replay else "GAME"
        _done(client, replay, played=False)
        return False
    _STATE.clear()
    _STATE.update(replay=bool(replay), start=None, frame=0, surf=None, scaled=None, channel=None)
    # first viewing comes straight from the login (state LOGIN / STAT_ALLOC): it ends in the world
    client.throne_vision_prev = getattr(client, "state", "GAME") if replay else "GAME"
    client.state = "THRONE_VISION"
    client.throne_vision_skip_rect = None
    try:
        if pygame.mixer.get_init():
            pygame.mixer.music.stop()          # area music; it comes back when the film ends
            if _SOUND is None:
                _SOUND = pygame.mixer.Sound(os.path.join(DIR, meta().get("audio", "audio.ogg")))
    except Exception:
        _SOUND = None
    return True


def _start_clock():
    now = pygame.time.get_ticks()
    _STATE["start"] = now
    if _SOUND is not None:
        try:
            _STATE["channel"] = _SOUND.play()
        except Exception:
            _STATE["channel"] = None


def elapsed_ms():
    st = _STATE.get("start")
    return 0 if st is None else pygame.time.get_ticks() - st


def handle_event(client, event):
    if event.type not in (pygame.KEYDOWN, pygame.MOUSEBUTTONDOWN):
        return
    if _STATE.get("start") is not None and elapsed_ms() < INPUT_GRACE_MS:
        return
    skip(client)


def abort():
    """Connection lost mid-film: stop the sound, no flag (it plays again next login)."""
    ch = _STATE.get("channel")
    try:
        if ch is not None:
            ch.stop()
    except Exception:
        pass
    _STATE.clear()


def skip(client):
    finish(client)


def finish(client):
    ch = _STATE.get("channel")
    try:
        if ch is not None:
            ch.stop()
        elif _SOUND is not None:
            _SOUND.stop()
    except Exception:
        pass
    replay = bool(_STATE.get("replay"))
    _STATE.clear()
    _done(client, replay, played=True)


def _done(client, replay, played):
    client.throne_vision_skip_rect = None
    prev = getattr(client, "throne_vision_prev", "GAME")
    client.state = prev if prev not in ("THRONE_VISION", None) else "GAME"
    if replay:
        return
    # first viewing: the server keeps the flag (validated there); mirror it locally
    if played:
        if isinstance(getattr(client, "player", None), dict):
            client.player["throne_vision_seen"] = True
        net = getattr(client, "net", None)
        if net is not None:
            try:
                net.send("THRONE_VISION_SEEN")
            except Exception:
                pass
    after = getattr(client, "_after_throne_vision", None)
    if callable(after):
        after()


def update(client):
    """Per frame: start the clock on the first draw, end at the last frame."""
    if _STATE.get("start") is None:
        _start_clock()
    dur = float(meta().get("duration", frame_count() / max(1.0, fps())))
    if elapsed_ms() >= dur * 1000.0 + 200:
        finish(client)
        return False
    return True


def draw(client):
    screen = client.screen
    screen.fill((0, 0, 0))
    if client.state != "THRONE_VISION" or not update(client):
        return
    i = frame_for_ms(elapsed_ms())
    sw, sh = screen.get_size()
    if i != _STATE.get("frame"):
        try:
            img = pygame.image.load(_frame_path(i))
            k = min(sw / img.get_width(), sh / img.get_height())
            size = (max(1, int(img.get_width() * k)), max(1, int(img.get_height() * k)))
            _STATE["scaled"] = pygame.transform.smoothscale(img, size)
            _STATE["frame"] = i
        except Exception:
            pass
    s = _STATE.get("scaled")
    if s is not None:
        screen.blit(s, ((sw - s.get_width()) // 2, (sh - s.get_height()) // 2))
    font = getattr(client, "font_small", None) or pygame.font.SysFont(None, 20)
    label = font.render("Skip  >", True, (240, 228, 200))
    r = pygame.Rect(0, 0, label.get_width() + 32, label.get_height() + 14)
    r.bottomright = (sw - 18, sh - 14)
    pygame.draw.rect(screen, (20, 18, 24), r, border_radius=14)
    pygame.draw.rect(screen, (212, 175, 90), r, 1, border_radius=14)
    screen.blit(label, (r.x + 16, r.y + 7))
    client.throne_vision_skip_rect = r
    hint = font.render("Press any key or click to skip", True, (150, 140, 120))
    screen.blit(hint, (18, sh - 14 - hint.get_height()))
