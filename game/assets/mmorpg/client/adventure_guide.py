"""Adventure Guide — parchment quest journal.

Opens from the Quests button / Q, and when a quest is newly given (unless the
player has turned guidance off). Shows one quest at a time: objective, next
destination, one instruction, optional tutorial progress, Go, Hide, and turn
off guidance. The golden trail respects the same preference.
"""
from __future__ import annotations

import json
import math
import os

import pygame

from content import QUESTS, NPCS

_DIR = os.path.join(os.path.dirname(__file__), "assets", "ui")
_PLATE = os.path.join(_DIR, "adventure_guide_plate.jpg")
_PREFS = os.path.join(os.path.expanduser("~"), ".crownfall", "adventure_guide.json")

INK = (43, 33, 24)
INK_SOFT = (90, 70, 48)
GOLD = (148, 108, 48)
GOLD_HI = (212, 175, 90)
CREAM = (236, 222, 190)
MUTED = (120, 100, 72)
PANEL = (58, 38, 24)
PANEL_HI = (92, 58, 32)
SAFE = (56, 120, 70)
SAFE_HI = (120, 200, 140)

_open = False
_selected = None
_rects = {}
_plate = None
_plate_scaled = None
_prefs = None
_prev_statuses = {}


def active(client=None):
    return _open


def guidance_off():
    return bool(_load_prefs().get("guidance_off"))


def set_guidance_off(on):
    prefs = _load_prefs()
    prefs["guidance_off"] = bool(on)
    _save_prefs(prefs)


def toggle(client, qid=None):
    if _open:
        close(client)
    else:
        open_panel(client, qid=qid)


def open_panel(client, qid=None):
    global _open, _selected
    _open = True
    _selected = qid or _default_qid(client)
    _rects.clear()
    try:
        client.show_world_map = False
    except Exception:
        pass


def close(client=None):
    global _open
    _open = False
    _rects.clear()


def on_quest_log(client, previous, current):
    """Open when a quest newly becomes active or ready, unless guidance is off.

    The first QUEST_LOG of a session is ignored so logging in with active
    quests does not force the journal open.
    """
    global _prev_statuses
    prev = previous or {}
    cur = current or {}
    _prev_statuses = {
        qid: (state or {}).get("status") or "not_started"
        for qid, state in cur.items()
    }
    if guidance_off():
        return
    if not prev:
        return
    for qid, state in cur.items():
        status = (state or {}).get("status") or "not_started"
        if status not in ("active", "ready"):
            continue
        before = (prev.get(qid) or {}).get("status") or "not_started"
        if before not in ("active", "ready"):
            open_panel(client, qid=qid)
            return


def handle_event(client, event):
    if not _open:
        return False
    # Seraphine's tour and Settings own their clicks; an auto-opened journal
    # must not swallow intro / step / Replay Tour clicks (module _open persists).
    if getattr(client, "show_help", False):
        return False
    try:
        import guide_tour
        if guide_tour.visible(client) or guide_tour.active(client):
            if _open:
                close(client)
            return False
    except Exception:
        pass
    if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
        close(client)
        return True
    if event.type != pygame.MOUSEBUTTONDOWN or getattr(event, "button", 1) != 1:
        return _open  # swallow while open so the world doesn't get clicks
    mx, my = event.pos
    panel = _rects.get("panel")
    if panel is None or not panel.collidepoint(mx, my):
        close(client)
        return False  # dismiss without eating the click (Equip all / Settings / world)

    if _hit("go", mx, my):
        _do_go(client)
        return True
    if _hit("hide", mx, my):
        close(client)
        return True
    if _hit("guidance", mx, my):
        set_guidance_off(not guidance_off())
        if guidance_off():
            try:
                import new_player_guide
                new_player_guide.clear_waypoint(client)
            except Exception:
                pass
            client.add_chat(
                "Guidance off. Quests still open from the Quests button.",
                color=GOLD_HI, highlight=True,
            )
        else:
            client.add_chat("Guidance on. The trail will lead you again.", color=GOLD_HI)
        return True
    for qid, rect in (_rects.get("rows") or {}).items():
        if rect.collidepoint(mx, my):
            global _selected
            _selected = qid
            if hasattr(client, "track_quest"):
                try:
                    client.track_quest(qid)
                except Exception:
                    client.tracked_quest_id = qid
            else:
                client.tracked_quest_id = qid
            return True
    return True


def draw(client):
    if not _open or not getattr(client, "player", None):
        return
    screen = client.screen
    sw, sh = screen.get_size()
    # Soft dim behind the journal.
    dim = pygame.Surface((sw, sh), pygame.SRCALPHA)
    dim.fill((8, 6, 10, 150))
    screen.blit(dim, (0, 0))

    panel_w = min(920, sw - 40)
    panel_h = min(560, sh - 40)
    panel = pygame.Rect((sw - panel_w) // 2, (sh - panel_h) // 2, panel_w, panel_h)
    _rects["panel"] = panel

    plate = _scaled_plate(panel_w, panel_h)
    if plate is not None:
        screen.blit(plate, panel.topleft)
        pygame.draw.rect(screen, GOLD, panel, 2, border_radius=6)
    else:
        try:
            import hud_skin
            hud_skin.parchment(screen, panel, plaque="QUEST")
        except Exception:
            pygame.draw.rect(screen, CREAM, panel, border_radius=8)
            pygame.draw.rect(screen, GOLD, panel, 2, border_radius=8)

    left = pygame.Rect(panel.x + 28, panel.y + 28, int(panel.w * 0.32), panel.h - 56)
    right = pygame.Rect(left.right + 18, panel.y + 36, panel.right - left.right - 40, panel.h - 72)

    _draw_sidebar(client, left)
    _draw_detail(client, right)


# ---------------------------------------------------------------- data
def _default_qid(client):
    import hud_v2
    qid = hud_v2._tracked_quest_id(client)
    if qid:
        return qid
    for qid, state in (client.quests or {}).items():
        if (state or {}).get("status") in ("active", "ready"):
            return qid
    return None


def _entries(client):
    """(active, side, completed) lists of (qid, name, status, blurb)."""
    active, side, done = [], [], []
    quests = client.quests or {}
    for qid, spec in QUESTS.items():
        info = quests.get(qid) or {"status": "not_started", "progress": 0}
        status = info.get("status") or "not_started"
        if status == "not_started" and spec.get("hidden_until_offered"):
            continue
        req = spec.get("requires")
        if status == "not_started" and req:
            needed = req if isinstance(req, (list, tuple)) else [req]
            if any((quests.get(r) or {}).get("status") != "complete" for r in needed):
                continue
        name = spec.get("name") or qid.replace("_", " ").title()
        blurb = (spec.get("description") or "").strip()
        if status in ("active", "ready"):
            active.append((qid, name, status, blurb))
        elif status == "complete":
            done.append((qid, name, status, blurb))
        elif status == "not_started" and not spec.get("optional"):
            side.append((qid, name, status, blurb))
    # Cap side / completed so the left column stays short.
    return active, side[:4], done[:6]


def _selected_state(client):
    qid = _selected or _default_qid(client)
    if not qid:
        return None, None, None, None
    qdef = QUESTS.get(qid) or {}
    state = (client.quests or {}).get(qid) or {}
    return qid, qdef, state, (state.get("status") or "not_started")


def _objective(client, qid, state, status, qdef):
    if status == "ready":
        giver = next((n for n in NPCS if n.get("id") == qdef.get("giver")), {}) or {}
        return f"Return to {giver.get('name') or 'the quest giver'}"
    if hasattr(client, "_quest_objective_text"):
        text = client._quest_objective_text(qid, state) or ""
        if text.strip():
            return text
    return (qdef.get("description") or "").strip() or "Follow the golden trail"


def _destination(client, qid, status):
    if not qid or status not in ("active", "ready"):
        return None
    try:
        import new_player_guide
        return new_player_guide.quest_objective_dest(client, qid)
    except Exception:
        return None


def _instruction(client, qid, status):
    if not qid:
        import hud_v2
        step = hud_v2._no_quest_step(client)
        return (step or {}).get("hint") or "Press Q any time to open this guide."
    import hud_v2
    return hud_v2._quest_finish_hint(client, qid, status)


def _tutorial_line(client):
    try:
        import guide_tour
        step = guide_tour._server_step(client)
        if 0 <= step <= guide_tour.STEPS:
            shown = max(1, step) if step else 0
            if step == 0:
                return "Tutorial ready — Seraphine is waiting"
            return f"Tutorial {shown} of {guide_tour.STEPS}"
    except Exception:
        pass
    return None


def _rewards_bits(client, qdef):
    if hasattr(client, "_format_quest_rewards"):
        return client._format_quest_rewards(qdef) or ""
    return ""


# ---------------------------------------------------------------- draw pieces
def _draw_sidebar(client, area):
    title_f = _font("title", 28)
    small = _font("body", 15)
    tiny = _font("body", 13)
    _text(client, "Quest", title_f, INK, (area.x + 8, area.y), shadow=False)
    y = area.y + 42
    active, side, done = _entries(client)
    rows = {}

    y = _section(client, "Active Quest", area.x, y, area.w, tiny)
    if not active:
        _text(client, "None yet — talk to a quest giver.", tiny, MUTED, (area.x + 6, y))
        y += 22
    for qid, name, status, blurb in active:
        selected = qid == (_selected or _default_qid(client))
        card_h = 64 if selected else 36
        card = pygame.Rect(area.x, y, area.w - 4, card_h)
        fill = PANEL_HI if selected else PANEL
        pygame.draw.rect(client.screen, fill, card, border_radius=6)
        if selected:
            pygame.draw.rect(client.screen, GOLD_HI, card, 2, border_radius=6)
            # Soft glow.
            glow = pygame.Surface((card.w + 8, card.h + 8), pygame.SRCALPHA)
            pygame.draw.rect(glow, (*GOLD_HI, 50), glow.get_rect(), border_radius=8)
            client.screen.blit(glow, (card.x - 4, card.y - 4))
            pygame.draw.rect(client.screen, fill, card, border_radius=6)
            pygame.draw.rect(client.screen, GOLD_HI, card, 2, border_radius=6)
        _star(client.screen, card.x + 14, card.y + 14, 7, GOLD_HI if selected else GOLD)
        _text(client, _fit(small, name, card.w - 40), small, CREAM if selected else (220, 205, 175),
              (card.x + 28, card.y + 6), shadow=False)
        if selected and blurb:
            _text(client, _fit(tiny, blurb, card.w - 36), tiny, (200, 180, 140),
                  (card.x + 28, card.y + 28), shadow=False)
        rows[qid] = card
        y += card_h + 6
        if y > area.bottom - 120:
            break

    if side and y < area.bottom - 100:
        y = _section(client, "Side Quests", area.x, y + 4, area.w, tiny)
        for qid, name, status, blurb in side:
            if y > area.bottom - 80:
                break
            _diamond(client.screen, area.x + 10, y + 8, 4, MUTED)
            _text(client, _fit(tiny, name, area.w - 28), tiny, MUTED, (area.x + 22, y), shadow=False)
            rows[qid] = pygame.Rect(area.x, y, area.w - 4, 18)
            y += 20

    if done and y < area.bottom - 40:
        y = _section(client, "Completed", area.x, y + 6, area.w, tiny)
        for qid, name, status, blurb in done:
            if y > area.bottom - 20:
                break
            _check(client.screen, area.x + 10, y + 8, MUTED)
            _text(client, _fit(tiny, name, area.w - 28), tiny, MUTED, (area.x + 22, y), shadow=False)
            rows[qid] = pygame.Rect(area.x, y, area.w - 4, 18)
            y += 18

    _rects["rows"] = rows


def _draw_detail(client, area):
    title_f = _font("title", 26)
    body = _font("body", 16)
    small = _font("body", 14)
    tiny = _font("body", 13)

    qid, qdef, state, status = _selected_state(client)
    if not qid:
        import hud_v2
        step = hud_v2._no_quest_step(client) or {}
        name = step.get("title") or "Your next step"
        desc = step.get("detail") or ""
        objective = desc
        dest_label = None
        instruction = step.get("hint") or ""
        rewards = ""
        go_npc = step.get("npc")
        go_dest = None
    else:
        name = qdef.get("name") or qid.replace("_", " ").title()
        desc = (qdef.get("description") or "").strip()
        objective = _objective(client, qid, state, status, qdef)
        dest = _destination(client, qid, status)
        dest_label = dest[2] if dest else None
        instruction = _instruction(client, qid, status)
        rewards = _rewards_bits(client, qdef)
        go_npc = qdef.get("giver") if status == "ready" else None
        if qdef.get("type") == "find_npc" and status != "ready":
            go_npc = qdef.get("target")
        go_dest = dest

    # Ribbon title band.
    band = pygame.Rect(area.x + 20, area.y + 4, area.w - 40, 44)
    ribbon = pygame.Surface(band.size, pygame.SRCALPHA)
    pygame.draw.rect(ribbon, (70, 42, 24, 220), ribbon.get_rect(), border_radius=4)
    pygame.draw.rect(ribbon, (*GOLD_HI, 200), ribbon.get_rect(), 2, border_radius=4)
    client.screen.blit(ribbon, band.topleft)
    _text(client, _fit(title_f, name, band.w - 24), title_f, CREAM,
          (band.centerx, band.centery), anchor="center", shadow=True)

    y = band.bottom + 16
    if desc:
        for line in _wrap(body, desc, area.w - 24, max_lines=2):
            _text(client, line, body, INK_SOFT, (area.x + 8, y), shadow=False)
            y += 20
        y += 8

    # Current objective.
    _star(client.screen, area.x + 14, y + 8, 8, GOLD_HI)
    _text(client, "Current objective", small, GOLD, (area.x + 30, y), shadow=False)
    y += 22
    for line in _wrap(body, objective or "—", area.w - 24, max_lines=2):
        _text(client, line, body, INK, (area.x + 30, y), shadow=False)
        y += 20
    y += 10

    # Next destination.
    _text(client, "Next destination", small, GOLD, (area.x + 30, y), shadow=False)
    y += 20
    where = dest_label or "Open Quests after you accept a task"
    _text(client, _fit(body, where, area.w - 40), body, INK, (area.x + 30, y), shadow=False)
    y += 28

    # One short instruction.
    _text(client, "Instruction", small, GOLD, (area.x + 30, y), shadow=False)
    y += 20
    for line in _wrap(body, instruction or "Follow the golden trail.", area.w - 24, max_lines=2):
        _text(client, line, body, INK, (area.x + 30, y), shadow=False)
        y += 20
    y += 8

    tour = _tutorial_line(client)
    if tour:
        _text(client, tour, tiny, MUTED, (area.x + 30, y), shadow=False)
        y += 22

    if rewards:
        _text(client, "Rewards", small, GOLD, (area.x + 30, y), shadow=False)
        y += 18
        _text(client, _fit(tiny, rewards, area.w - 40), tiny, INK_SOFT, (area.x + 30, y), shadow=False)
        y += 24

    # Buttons along the bottom of the detail pane.
    btn_y = area.bottom - 44
    go = pygame.Rect(area.right - 130, btn_y, 110, 36)
    hide = pygame.Rect(area.x + 8, btn_y, 80, 32)
    guide = pygame.Rect(hide.right + 10, btn_y, 170, 32)

    _button(client, go, "Go", SAFE, SAFE_HI, primary=True)
    _button(client, hide, "Hide", PANEL, GOLD)
    label = "Turn guidance on" if guidance_off() else "Turn off guidance"
    _button(client, guide, label, PANEL, GOLD)

    _rects["go"] = {"rect": go, "npc_id": go_npc, "dest": go_dest}
    _rects["hide"] = hide
    _rects["guidance"] = guide


def _do_go(client):
    info = _rects.get("go") or {}
    npc_id = info.get("npc_id")
    dest = info.get("dest")
    import new_player_guide
    npc = next((row for row in NPCS if row.get("id") == npc_id), None)
    if npc:
        new_player_guide.set_waypoint(client, npc["x"], npc["y"], npc.get("name") or "Quest")
        client.walk_and_act(client.adjacent_goals(npc["x"], npc["y"]), {
            "type": "TALK", "npc_id": npc["id"],
        })
    elif dest:
        x, y, label = dest[0], dest[1], dest[2] if len(dest) > 2 else "Objective"
        new_player_guide.set_waypoint(client, x, y, label or "Objective")
        client.travel_to_destination({
            "x": x, "y": y, "label": label or "Objective", "action": None,
        })
    else:
        # Fall back to whatever the trail already knows.
        spot = new_player_guide.quest_objective_dest(client, _selected)
        if spot:
            new_player_guide.set_waypoint(client, spot[0], spot[1], spot[2])
            client.travel_to_destination({
                "x": spot[0], "y": spot[1], "label": spot[2], "action": None,
            })
        else:
            client.add_chat("No destination to go to yet.", color=GOLD_HI)
            return
    close(client)


# ---------------------------------------------------------------- chrome helpers
def _load_prefs():
    global _prefs
    if _prefs is not None:
        return _prefs
    try:
        with open(_PREFS, "r", encoding="utf-8") as f:
            _prefs = json.load(f) or {}
    except Exception:
        _prefs = {}
    return _prefs


def _save_prefs(prefs):
    global _prefs
    _prefs = dict(prefs or {})
    try:
        os.makedirs(os.path.dirname(_PREFS), exist_ok=True)
        with open(_PREFS, "w", encoding="utf-8") as f:
            json.dump(_prefs, f)
    except Exception:
        pass


def _scaled_plate(w, h):
    global _plate, _plate_scaled
    if _plate is None:
        if not os.path.isfile(_PLATE):
            return None
        try:
            _plate = pygame.image.load(_PLATE).convert()
        except Exception:
            return None
    key = (w, h)
    if _plate_scaled is None or _plate_scaled[0] != key:
        _plate_scaled = (key, pygame.transform.smoothscale(_plate, (w, h)))
    return _plate_scaled[1]


def _font(kind, size):
    try:
        import hud_skin
        return hud_skin.font(kind, size)
    except Exception:
        return pygame.font.Font(None, size + 4)


def _text(client, s, font, col, pos, anchor="topleft", shadow=True):
    img = font.render(str(s), True, col)
    r = img.get_rect(**{anchor: pos})
    if shadow:
        client.screen.blit(font.render(str(s), True, (0, 0, 0)), r.move(1, 1))
    client.screen.blit(img, r)
    return r


def _fit(font, s, w):
    s = str(s or "")
    if font.size(s)[0] <= w:
        return s
    while s and font.size(s + "...")[0] > w:
        s = s[:-1]
    return (s.rstrip() + "...") if s else ""


def _wrap(font, text, width, max_lines=3):
    words = (text or "").split()
    if not words:
        return []
    lines, cur = [], ""
    for word in words:
        trial = word if not cur else cur + " " + word
        if font.size(trial)[0] <= width:
            cur = trial
        else:
            if cur:
                lines.append(cur)
            cur = word
            if len(lines) >= max_lines:
                break
    if cur and len(lines) < max_lines:
        lines.append(cur)
    if len(lines) == max_lines and words:
        # Ellipsis if truncated.
        joined = " ".join(words)
        if " ".join(lines) != joined and lines:
            lines[-1] = _fit(font, lines[-1], width)
    return lines


def _section(client, label, x, y, w, font):
    _text(client, label, font, GOLD, (x + 4, y), shadow=False)
    pygame.draw.line(client.screen, (160, 130, 80), (x + 4, y + 18), (x + w - 8, y + 18), 1)
    return y + 24


def _star(surf, cx, cy, r, col):
    pts = []
    for i in range(8):
        ang = -math.pi / 2 + i * math.pi / 4
        rad = r if i % 2 == 0 else r * 0.4
        pts.append((cx + rad * math.cos(ang), cy + rad * math.sin(ang)))
    pygame.draw.polygon(surf, col, pts)


def _diamond(surf, cx, cy, r, col):
    pygame.draw.polygon(surf, col, [(cx, cy - r), (cx + r, cy), (cx, cy + r), (cx - r, cy)], 1)


def _check(surf, cx, cy, col):
    pygame.draw.lines(surf, col, False, [(cx - 4, cy), (cx - 1, cy + 4), (cx + 5, cy - 4)], 2)


def _button(client, rect, label, fill, border, primary=False):
    pygame.draw.rect(client.screen, fill, rect, border_radius=6)
    pygame.draw.rect(client.screen, border, rect, 2 if primary else 1, border_radius=6)
    f = _font("title" if primary else "body", 16 if primary else 13)
    col = CREAM if primary else GOLD_HI
    _text(client, label, f, col, (rect.centerx, rect.centery), anchor="center", shadow=True)


def _hit(key, mx, my):
    r = _rects.get(key)
    if r is None:
        return False
    if isinstance(r, dict):
        r = r.get("rect")
    return r is not None and r.collidepoint(mx, my)
