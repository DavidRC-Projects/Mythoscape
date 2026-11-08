"""Seraphine walks you from the village to the Royal Herald (War for the Crown guide).

Starts only after the first-5-minutes tour is finished. The Herald stands outside
the King's Castle approach (King's Realm portal). Talking through his guide pages
completes this walk.
"""
from __future__ import annotations

import math
import os
import time

import pygame

import equipment_ui_v2 as E

HERALD_ID = "royal_herald"
HERALD_TILE = (12, 21)
DONE = (100, 101)
PARCH = (232, 217, 181)
INK = (58, 38, 22)
INK_SOFT = (110, 82, 52)
LILAC = (186, 150, 226)
DIM_A = 120

_ART = {}


def _server_step(client):
    p = getattr(client, "player", None) or {}
    try:
        return int(p.get("crown_guide", 0))
    except (TypeError, ValueError):
        return 0


def _guide_tour_done(client):
    p = getattr(client, "player", None) or {}
    try:
        return int(p.get("guide_tour", 100)) in (100, 101, 102)
    except (TypeError, ValueError):
        return True


def _st(client):
    st = client.__dict__.get("_crown_guide")
    if st is None:
        st = {"sent": None, "t0": time.time(), "rects": {}, "confirm_skip": False}
        client._crown_guide = st
    return st


def send(client, action, **kw):
    try:
        client.net.send("CROWN_GUIDE", action=action, **kw)
    except Exception:
        pass


def on_state(client, msg):
    if client.player is not None:
        client.player["crown_guide"] = int(msg.get("step", 0))
    st = _st(client)
    st["sent"] = None


def replay(client):
    send(client, "replay")
    client.show_help = False


def blocked(client):
    if getattr(client, "state", None) != "GAME":
        return True
    if getattr(client, "needs_appearance", False):
        return True
    try:
        import guide_tour
        if guide_tour.active(client):
            return True
    except Exception:
        pass
    return False


def available_offer(client):
    """Show Seraphine's village offer when the first tour is done and crown guide is 0."""
    if blocked(client):
        return False
    if not _guide_tour_done(client):
        return False
    # Don't offer inside dungeons / castle realm — start in the village overworld.
    if getattr(client, "dungeon", None):
        return False
    return _server_step(client) == 0


def active(client):
    if blocked(client):
        return False
    step = _server_step(client)
    return step in (0, 1, 2) and (_guide_tour_done(client) or step in (1, 2))


def visible(client):
    if not active(client):
        return False
    if getattr(client, "dialogue", None) and _server_step(client) >= 2:
        return False
    return True


def trail_target(client):
    """Golden trail destination while Seraphine is walking you to the Herald."""
    if _server_step(client) in (1, 2) and not blocked(client):
        return {"kind": "npc", "id": HERALD_ID, "x": HERALD_TILE[0], "y": HERALD_TILE[1],
                "label": "Royal Herald (outside King's Castle)"}
    return None


def _portrait(w, h):
    key = ("portrait", w, h)
    if key not in _ART:
        surf = E._opaque(w, h)
        surf.fill((60, 44, 70))
        try:
            path = os.path.join(os.path.dirname(__file__), "..", "assets", "ui", "seraphine_portrait.jpg")
            img = pygame.image.load(path).convert()
            iw, ih = img.get_size()
            s = max(w / iw, h / ih)
            img = pygame.transform.smoothscale(img, (int(iw * s) + 1, int(ih * s) + 1))
            surf.blit(img, ((w - img.get_width()) // 2, 0))
        except Exception:
            pass
        _ART[key] = surf
    return _ART[key]


def _parchment(w, h):
    key = ("parch", w, h)
    if key not in _ART:
        surf = E._opaque(w, h)
        surf.blit(E._grain(w, h, PARCH, 7, streak=False), (0, 0))
        _ART[key] = surf
    return _ART[key]


def _wrap(text, f, width):
    words, lines, cur = text.split(), [], ""
    for w in words:
        t = (cur + " " + w).strip()
        if f.size(t)[0] <= width or not cur:
            cur = t
        else:
            lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    return lines


def _npc(client):
    for n in getattr(client, "npcs", None) or []:
        if n.get("id") == HERALD_ID:
            return n
    return None


def _near_herald(client):
    p = client.player or {}
    n = _npc(client)
    if n:
        return max(abs(int(p.get("x", 0)) - int(n["x"])),
                   abs(int(p.get("y", 0)) - int(n["y"]))) <= 2
    return max(abs(int(p.get("x", 0)) - HERALD_TILE[0]),
               abs(int(p.get("y", 0)) - HERALD_TILE[1])) <= 2


def tick(client):
    if not active(client):
        return
    step = _server_step(client)
    st = _st(client)
    if step == 1 and _near_herald(client) and st.get("sent") != "arrived":
        st["sent"] = "arrived"
        send(client, "arrived")


def handle_click(client, event):
    if not visible(client):
        return False
    st = _st(client)
    pos = event.pos
    R = st.get("rects") or {}
    if st.get("confirm_skip"):
        if R.get("skip_yes") and R["skip_yes"].collidepoint(pos):
            send(client, "skip")
            st["confirm_skip"] = False
            return True
        if R.get("skip_no") and R["skip_no"].collidepoint(pos):
            st["confirm_skip"] = False
            return True
        return True
    if R.get("start") and R["start"].collidepoint(pos):
        send(client, "start")
        return True
    if R.get("skip") and R["skip"].collidepoint(pos):
        st["confirm_skip"] = True
        return True
    return False


def handle_event(client, event):
    if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
        return handle_click(client, event)
    return False


def _lines_for(step):
    if step == 0:
        return (
            "Hello again, darling. The throne isn't won by a quiet stroll anymore.",
            "Walk with me to the Royal Herald — he waits outside the King's Castle "
            "approach, by the gold portal west of the wishing well. Shall we?",
        )
    if step == 1:
        return (
            "Follow the gold trail. He stands outside the castle approach — not inside "
            "the keep — so travellers can't miss him.",
            "Walk to the Royal Herald.",
        )
    return (
        "There he is. Click the Royal Herald and choose How the War for the Crown works.",
        "Listen through every page — then you'll know the monthly war.",
    )


def draw(client):
    if not visible(client) and not available_offer(client):
        # Still draw while walking even if offer helper is false.
        if not visible(client):
            return
    if not visible(client):
        return
    scr = client.screen
    st = _st(client)
    step = _server_step(client)
    # Soft dim
    dim = pygame.Surface(scr.get_size(), pygame.SRCALPHA)
    dim.fill((10, 8, 16, DIM_A if step == 0 else 70))
    scr.blit(dim, (0, 0))

    # Ring the Herald when visible on screen.
    n = _npc(client)
    if n and step in (1, 2):
        try:
            r = pygame.Rect(client.map_screen_rect(int(n["x"]), int(n["y"])))
            pulse = 0.5 + 0.5 * math.sin(time.time() * 4)
            pygame.draw.ellipse(
                scr, (255, 210, 90, int(140 + 80 * pulse)),
                r.inflate(18, 18), 3,
            )
        except Exception:
            pass

    # Portrait + parchment (bottom-left), matching Seraphine's first tour feel.
    pw, ph = 110, 128
    plate = pygame.Rect(18, scr.get_height() - ph - 24, pw, ph)
    speech = pygame.Rect(plate.right + 14, plate.y + 8, min(520, scr.get_width() - plate.right - 40), ph - 16)
    scr.blit(_portrait(pw, ph), plate.topleft)
    pygame.draw.rect(scr, (212, 175, 90), plate, 2, border_radius=6)
    scr.blit(_parchment(speech.w, speech.h), speech.topleft)
    pygame.draw.rect(scr, (148, 108, 48), speech, 2, border_radius=6)
    E._text(scr, "Seraphine", E.font("title", 15), E.TITLE_GOLD,
            (plate.centerx, plate.bottom + 2), anchor="midtop")

    title, detail = _lines_for(step)
    f = E.font("body", 15)
    y = speech.y + 10
    for ln in _wrap(title, f, speech.w - 24):
        E._text(scr, ln, f, INK, (speech.x + 12, y), anchor="topleft")
        y += f.get_height() + 2
    y += 6
    for ln in _wrap(detail, f, speech.w - 24):
        E._text(scr, ln, f, INK_SOFT, (speech.x + 12, y), anchor="topleft")
        y += f.get_height() + 2

    R = {}
    if step == 0:
        start = pygame.Rect(speech.right - 200, speech.bottom - 36, 90, 28)
        skip = pygame.Rect(speech.right - 100, speech.bottom - 36, 88, 28)
        E._plaque(scr, start, rim=E.GOLD_HI)
        E._text(scr, "Let's go", E.font("title", 14), E.GOLD_HI, start.center, anchor="center")
        E._plaque(scr, skip, rim=E.GOLD)
        E._text(scr, "Not now", E.font("title", 14), E.TITLE_GOLD, skip.center, anchor="center")
        R["start"], R["skip"] = start, skip
    else:
        skip = pygame.Rect(speech.right - 100, speech.bottom - 36, 88, 28)
        E._plaque(scr, skip, rim=E.GOLD)
        E._text(scr, "Skip", E.font("title", 14), E.TITLE_GOLD, skip.center, anchor="center")
        R["skip"] = skip

    if st.get("confirm_skip"):
        box = pygame.Rect(0, 0, 360, 120)
        box.center = scr.get_rect().center
        pygame.draw.rect(scr, (28, 22, 34), box, border_radius=8)
        pygame.draw.rect(scr, (212, 175, 90), box, 2, border_radius=8)
        E._text(scr, "Skip the War for the Crown walk?", E.font("title", 16), E.GOLD_HI,
                (box.centerx, box.y + 28), anchor="center")
        yes = pygame.Rect(box.x + 40, box.bottom - 44, 120, 28)
        no = pygame.Rect(box.right - 160, box.bottom - 44, 120, 28)
        E._plaque(scr, yes, rim=E.GOLD_HI)
        E._plaque(scr, no, rim=E.GOLD)
        E._text(scr, "Skip", E.font("title", 14), E.GOLD_HI, yes.center, anchor="center")
        E._text(scr, "Keep going", E.font("title", 14), E.TITLE_GOLD, no.center, anchor="center")
        R["skip_yes"], R["skip_no"] = yes, no

    st["rects"] = R
