"""Seven-page comic shown once, before a new game enters the world.

Off unless USE_OPENING_COMIC is set. page_01.ogg … page_07.ogg in the
same folder play with that page. A page_NN.wav is used when the ogg
is not there. If neither file exists, the line is shown with no sound.
"""
from __future__ import annotations

import os

import pygame

import feature_flags

_DIR = os.path.normpath(os.path.join(
    os.path.dirname(__file__), "..", "assets", "opening_comic",
))
LINES = (
    "The king does not rule this land. He eats it. Carts leave the village full, and the folk left in the mud come home with nowt. You've a sword, lad. It will not fill a belly.",
    "So they barred the deep, and the gold can't walk back out. Wagons of it, all night, into a vault you could drown in. Every coin down there belongs to him now.",
    "Dig in the ruins, if you've the stomach. The stone shows a guild stood round a castle. Earn both. Only then may you challenge the crown.",
    "Armour first, or you won't see the week out. Then the board in the market, and the levels it pays. Then find folk daft enough to walk that road with you.",
    "Quests fill the purse. Dungeons spend the courage. There's a dragon under that hill, and a key past its teeth. Come back up, and both are yours.",
    "Give the guild a table, then a castle, then a flag. Do that and he can't call you a villager any more. The king has a problem.",
    "Not today. The road in front of you is for learning, and for gathering the clan. When they're ready, it runs straight at his gates, and the war begins.",
)
_PAGES = []
_VOICE = None
_BAR_MIN = 84
_SCALED = {}


def begin(client):
    client.opening_comic_page = 0
    _load()
    _play(1)


def handle_event(client, event):
    if event.type == pygame.KEYDOWN:
        if event.key == pygame.K_ESCAPE:
            finish(client)
        elif event.key in (pygame.K_SPACE, pygame.K_RETURN):
            advance(client)
    elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
        skip = getattr(client, "opening_comic_skip", None)
        if skip is not None and skip.collidepoint(event.pos):
            finish(client)
        else:
            advance(client)


def advance(client):
    page = int(getattr(client, "opening_comic_page", 0))
    if page >= len(LINES) - 1:
        finish(client)
        return
    client.opening_comic_page = page + 1
    _play(page + 2)


def finish(client):
    _stop()
    client.opening_comic_pending = False
    client.state = "GAME"
    if getattr(client, "arrival_guide", False):
        import new_player_guide
        new_player_guide.start(client)


def draw(client):
    screen = client.screen
    screen.fill((6, 5, 8))
    _load()
    page = int(getattr(client, "opening_comic_page", 0))
    page = max(0, min(len(LINES) - 1, page))
    sw, sh = screen.get_size()
    lines = _wrap(client, LINES[page], sw - 160)
    bar_h = max(_BAR_MIN, 28 + len(lines) * 26)
    img = _PAGES[page] if page < len(_PAGES) else None
    if img is not None:
        avail_h = max(1, sh - bar_h)
        placed = _fitted(page, img, sw, avail_h)
        if placed is not None:
            scaled, origin = placed
            screen.blit(scaled, origin)
    bar = pygame.Rect(0, sh - bar_h, sw, bar_h)
    pygame.draw.rect(screen, (12, 10, 12), bar)
    pygame.draw.line(screen, (90, 70, 40), (0, bar.y), (sw, bar.y), 2)
    _blit_wrapped(client, lines, pygame.Rect(bar.x, bar.y, bar.w, bar.h - 22))
    mark = client.font_tiny.render(
        f"{page + 1} / {len(LINES)}    Click or Space    Esc skips",
        True, (180, 160, 120),
    )
    screen.blit(mark, (28, bar.bottom - 22))
    skip = pygame.Rect(sw - 118, bar.y + 8, 96, 36)
    client.opening_comic_skip = skip
    pygame.draw.rect(screen, (36, 28, 22), skip)
    pygame.draw.rect(screen, (180, 140, 70), skip, 2)
    label = client.font.render("Skip", True, (240, 220, 180))
    screen.blit(label, (skip.centerx - label.get_width() // 2, skip.centery - label.get_height() // 2))


def _fitted(page, img, sw, avail_h):
    key = (page, sw, avail_h, img.get_size())
    hit = _SCALED.get(key)
    if hit is not None:
        return hit
    scale = min(sw / img.get_width(), avail_h / img.get_height())
    w = max(1, int(img.get_width() * scale))
    h = max(1, int(img.get_height() * scale))
    scaled = pygame.transform.smoothscale(img, (w, h))
    placed = (scaled, ((sw - w) // 2, (avail_h - h) // 2))
    _SCALED.clear()
    _SCALED[key] = placed
    return placed


def _wrap(client, text, limit):
    words = text.split()
    lines = []
    current = ""
    for word in words:
        trial = word if not current else current + " " + word
        if client.font.size(trial)[0] <= limit:
            current = trial
        else:
            if current:
                lines.append(current)
            current = word
    if current:
        lines.append(current)
    return lines


def _blit_wrapped(client, lines, bar):
    total = len(lines) * 26
    y = bar.y + (bar.height - total) // 2
    for line in lines:
        surf = client.font.render(line, True, (236, 224, 196))
        client.screen.blit(surf, (28, y))
        y += 26


def _load():
    if _PAGES:
        return
    for index in range(1, len(LINES) + 1):
        path = os.path.join(_DIR, f"page_{index:02d}.jpg")
        if not os.path.isfile(path):
            _PAGES.append(None)
            continue
        img = pygame.image.load(path)
        if pygame.display.get_surface() is not None:
            img = img.convert()
        _PAGES.append(img)


def _voice_path(number):
    stem = os.path.join(_DIR, f"page_{number:02d}")
    for ext in ("ogg", "wav"):
        path = stem + "." + ext
        if os.path.isfile(path):
            return path
    return None


def _play(number):
    _stop()
    if not feature_flags.USE_OPENING_COMIC:
        return
    path = _voice_path(number)
    if path is None:
        return
    global _VOICE
    try:
        if not pygame.mixer.get_init():
            pygame.mixer.init()
        _VOICE = pygame.mixer.Sound(path)
        _VOICE.play()
    except Exception:
        _VOICE = None


def _stop():
    global _VOICE
    if _VOICE is None:
        return
    try:
        _VOICE.stop()
    except Exception:
        pass
    _VOICE = None
