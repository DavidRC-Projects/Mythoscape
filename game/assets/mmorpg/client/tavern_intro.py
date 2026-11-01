"""Resting Ox entry film (tavern_entry_v2.mp4), played the first time a character walks into the bar.

The client has no video decoder, so the film ships pre-extracted like throne_vision:
assets/tavern_intro/frames/0001.jpg ... (1280x720, 24 fps), audio.ogg and meta.json (subtitle timing).
The audio is the clock; a slow frame is dropped rather than drifting. "Skip >" shows after 0.5 s and any
key or click then skips. The film ends with a 0.3 s fade into the seated bar view. With reduced motion on
(client.reduced_motion or CROWNFALL_REDUCED_MOTION=1) a 2 s still of the bar is shown instead.
"""
from __future__ import annotations

import json
import os
import time

import pygame

DIR = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", "assets", "tavern_intro"))
SKIP_AFTER_S = 0.5
FADE_S = 0.3
STILL_S = 2.0
_META = None


def meta():
    global _META
    if _META is None:
        try:
            with open(os.path.join(DIR, "meta.json")) as f:
                _META = json.load(f)
        except (OSError, ValueError):
            _META = {}
    return _META


def frame_path(i):
    return os.path.join(DIR, meta().get("frame_pattern", "frames/%04d.jpg") % i)


def available():
    return bool(meta()) and os.path.isfile(frame_path(1))


def reduced_motion(client):
    return bool(getattr(client, "reduced_motion", False)) or os.environ.get("CROWNFALL_REDUCED_MOTION") == "1"


class TavernIntro:
    def __init__(self, client, on_done):
        self.client = client
        self.on_done = on_done
        self.still = reduced_motion(client)
        self.start = time.time()
        self.ending = None          # time the fade-out began
        self.frame = 0
        self.scaled = None
        self.channel = None
        self.skip_rect = None
        if not self.still:
            try:
                if pygame.mixer.get_init():
                    snd = pygame.mixer.Sound(os.path.join(DIR, meta().get("audio", "audio.ogg")))
                    self.channel = snd.play()
            except Exception:
                self.channel = None

    def elapsed(self):
        return time.time() - self.start

    def duration(self):
        return STILL_S if self.still else float(meta().get("duration", 13.5))

    def frame_for(self, sec):
        n = int(meta().get("frames", 1))
        return max(1, min(n, int(sec * float(meta().get("fps", 24))) + 1))

    def skip(self):
        if self.ending is None:
            self.ending = time.time()
            try:
                if self.channel is not None:
                    self.channel.fadeout(int(FADE_S * 1000))
            except Exception:
                pass

    def handle_event(self, event):
        if event.type in (pygame.KEYDOWN, pygame.MOUSEBUTTONDOWN) and self.elapsed() >= SKIP_AFTER_S:
            self.skip()
            return True
        return event.type in (pygame.KEYDOWN, pygame.MOUSEBUTTONDOWN)

    def done(self):
        return self.ending is not None and time.time() - self.ending >= FADE_S

    def render(self, surf, still_img=None):
        """Draw the film (or still). Returns False once finished (caller then draws the bar)."""
        if self.ending is None and self.elapsed() >= self.duration():
            self.skip()
        if self.done():
            if callable(self.on_done):
                cb, self.on_done = self.on_done, None
                cb()
            return False
        sw, sh = surf.get_size()
        surf.fill((0, 0, 0))
        if self.still:
            img = still_img
        else:
            i = self.frame_for(min(self.elapsed(), self.duration()))
            if i != self.frame:
                try:
                    raw = pygame.image.load(frame_path(i))
                    k = min(sw / raw.get_width(), sh / raw.get_height())
                    self.scaled = pygame.transform.smoothscale(
                        raw, (max(1, int(raw.get_width() * k)), max(1, int(raw.get_height() * k))))
                    self.frame = i
                except Exception:
                    pass
            img = self.scaled
        if img is not None:
            surf.blit(img, ((sw - img.get_width()) // 2, (sh - img.get_height()) // 2))
        m = meta()
        e = self.elapsed()
        font = pygame.font.SysFont("georgia,serif", 22)
        if not self.still and m.get("subtitle") and m.get("subtitle_start", 99) <= e <= m.get("subtitle_end", 0):
            self._subtitle(surf, font, m["subtitle"])
        if e >= SKIP_AFTER_S and self.ending is None:
            small = pygame.font.SysFont("georgia,serif", 18, bold=True)
            label = small.render("Skip  >", True, (240, 228, 200))
            r = pygame.Rect(0, 0, label.get_width() + 32, label.get_height() + 14)
            r.bottomright = (sw - 18, sh - 14)
            pygame.draw.rect(surf, (20, 18, 24), r, border_radius=14)
            pygame.draw.rect(surf, (212, 175, 90), r, 1, border_radius=14)
            surf.blit(label, (r.x + 16, r.y + 7))
            self.skip_rect = r
        if self.ending is not None:
            k = min(1.0, (time.time() - self.ending) / FADE_S)
            veil = pygame.Surface((sw, sh))
            veil.fill((0, 0, 0))
            veil.set_alpha(int(255 * k))
            surf.blit(veil, (0, 0))
        return True

    @staticmethod
    def _subtitle(surf, font, text):
        sw, sh = surf.get_size()
        words, rows, row = text.split(), [], ""
        for w in words:
            t = (row + " " + w).strip()
            if font.size(t)[0] > sw * 0.7:
                rows.append(row)
                row = w
            else:
                row = t
        rows.append(row)
        y = sh - 70 - len(rows) * 28
        for r in rows:
            img = font.render(r, True, (245, 238, 220))
            sh_ = font.render(r, True, (0, 0, 0))
            x = (sw - img.get_width()) // 2
            surf.blit(sh_, (x + 2, y + 2))
            surf.blit(img, (x, y))
            y += 28
