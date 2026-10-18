"""Idle logout, client side: report local-only input, show the 4:30 warning, handle the server's idle logout.

The server owns the timer. The client only tells it about input that sent nothing (panning, opening panels) with
an INPUT_PING every 30 s, and the server caps how much that ping can extend past the last real action.
"""
import time

import pygame

MESSAGE_TYPES = frozenset(("IDLE_WARNING", "IDLE_CLEAR", "LOGGED_OUT"))
PING_INTERVAL_S = 30.0
IDLE_LOGOUT_TEXT = "You were logged out after 5 minutes of inactivity."
_INPUT_EVENTS = (pygame.KEYDOWN, pygame.MOUSEBUTTONDOWN, pygame.MOUSEWHEEL)
_chime = None


def _state(client):
    st = getattr(client, "_idle", None)
    if st is None:
        st = client._idle = {"last_input": time.time(), "last_ping": time.time(), "input_since_ping": False,
                             "warn_until": 0.0}
    return st


def note_event(client, event):
    if event.type not in _INPUT_EVENTS:
        return
    st = _state(client)
    st["last_input"] = time.time()
    st["input_since_ping"] = True
    st["warn_until"] = 0.0          # the banner goes the moment you touch anything


def tick(client, now=None):
    if getattr(client, "state", None) != "GAME":
        return
    st = _state(client)
    now = time.time() if now is None else now
    if not st["input_since_ping"] or now - st["last_ping"] < PING_INTERVAL_S:
        return
    st["last_ping"] = now
    st["input_since_ping"] = False
    try:
        client.net.send("INPUT_PING", last_input_ms_ago=int(max(0.0, now - st["last_input"]) * 1000))
    except Exception:
        pass


def _play_chime():
    global _chime
    try:
        if not pygame.mixer.get_init():
            return
        if _chime is None:
            import array
            import math
            rate, channels = pygame.mixer.get_init()[0], abs(pygame.mixer.get_init()[2])
            samples = array.array("h")
            n = int(rate * 0.35)
            for i in range(n):
                env = min(1.0, i / 400.0) * (1.0 - i / n)
                freq = 660.0 if i < n // 2 else 880.0
                v = int(6000 * env * math.sin(2 * math.pi * freq * i / rate))
                samples.extend([v] * channels)
            _chime = pygame.mixer.Sound(buffer=samples.tobytes())
        _chime.play()
    except Exception:
        pass


def on_message(client, msg):
    st = _state(client)
    t = msg.get("type")
    if t == "IDLE_WARNING":
        st["warn_until"] = time.time() + float(msg.get("seconds") or 30)
        _play_chime()
    elif t == "IDLE_CLEAR":
        st["warn_until"] = 0.0
    elif t == "LOGGED_OUT":
        st["warn_until"] = 0.0
        client.logout()     # same path as the Log out button: clears caches, reconnects when the socket closes
        if msg.get("reason") == "idle":
            client.login_error = IDLE_LOGOUT_TEXT


def warning_seconds(client, now=None):
    st = _state(client)
    left = st["warn_until"] - (time.time() if now is None else now)
    return int(left + 0.999) if left > 0 else 0


def draw(client):
    secs = warning_seconds(client)
    if not secs or getattr(client, "state", None) != "GAME":
        return
    screen = client.screen
    font = getattr(client, "font", None) or pygame.font.SysFont(None, 24)
    text = font.render(f"You'll be logged out in {secs} s for inactivity", True, (255, 236, 170))
    pad = 14
    box = pygame.Rect(0, 0, text.get_width() + pad * 2, text.get_height() + pad * 2)
    box.center = (screen.get_width() // 2, screen.get_height() // 2)
    panel = pygame.Surface(box.size, pygame.SRCALPHA)
    panel.fill((20, 14, 8, 215))
    screen.blit(panel, box.topleft)
    pygame.draw.rect(screen, (196, 150, 70), box, 2)
    screen.blit(text, (box.x + pad, box.y + pad))
