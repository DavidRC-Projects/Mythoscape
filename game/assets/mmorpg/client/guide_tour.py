"""Seraphine's first-5-minutes tour (GUIDE_AND_SEWER_PROPOSAL.md v2, section 4).

A pop-up guide: portrait bottom-left, parchment speech line, the screen dimmed with ONE
target ringed in gold, and the tour waits for that one action. Text only (no voice).
Seraphine teaches buttons and how-to; story and quests stay with the village NPCs.

The server owns progress (player["guide_tour"]): 0 = not started, 1..11 = current step,
100 done, 101 skipped, 102 "I've played before". The client only asks to move on
(GUIDE_TOUR action=advance, step=n); the server checks it and gives the bronze set once.
Order: throne vision -> character creator -> this tour (it waits for both to finish).
"""
import math
import os
import time

import pygame

import equipment_ui_v2 as E

STEPS = 11
DONE_STATES = (100, 101, 102)
NUDGE_S = 15.0
LOOK_S = 2.6           # step 8's "Look at you" beat before moving on
PARCH = (232, 217, 181)
PARCH_DK = (196, 172, 128)
INK = (58, 38, 22)
INK_SOFT = (110, 82, 52)
LILAC = (186, 150, 226)
DIM_A = 165
DIM_WORLD_A = 95       # walking steps keep the world readable
DIM_PANEL_A = 28       # panel steps: light wash — inventory/equipment must stay readable
TAMSIN = "warden_tamsin"
TAMSIN_NAME = "Warden Tamsin"
# Gift set Seraphine hands over (must match server GUIDE_BRONZE_SET).
BRONZE_GIFT = ("bronze_helmet", "bronze_body", "bronze_legs", "bronze_sword", "bronze_shield")

# step -> (target, lines, kind). kind: walk | talk | click | equip_body | equip_all | eat | sewer
STEP_DEFS = {
    1: ("marker", ("Ah, you're awake. Walk with me, I don't bite.",
                   "Click the glowing spot to walk there."), "walk"),
    2: ("npc", ("See the gold trail? Follow it. The Warden's waiting.",
                "Walk to Warden Tamsin."), "walk_npc"),
    3: ("npc", ("Talk to the Warden. Nod politely, she loves that.",
                "Click Warden Tamsin to talk."), "talk"),
    4: ("quests", ("Every task she gives you lands here.",
                   "Open your quest log."), "click"),
    5: ("inventory", ("A gift from me. Full bronze. Don't tell the Warden.",
                      "Open your inventory."), "click"),
    6: ("equipment", ("Now let's see what you're wearing. Nothing, sadly.",
                      "Open Equipment."), "click"),
    7: ("chestplate", ("Tap it to wear it.",
                       "One click on the Bronze Platebody."), "equip_body"),
    8: ("equip_all", ("Lovely. Now the rest, all at once.",
                      "Press Equip all."), "equip_all"),
    9: ("eat", ("Red bar is you. Food heals, eat before you need to.",
                "Press Eat (or click your bread)."), "eat"),
    10: ("skills", ("Skills grow here. Train them on your road to the throne.",
                    "Open Skills."), "click"),
    11: (None, ("Hear that squeaking? Fancy a little fight?",
                     "Rats below the village. Sewer tutorial now?"), "sewer"),
}
LOOK_LINE = "Look at you. Defence up, ego up."
NUDGE_LINE = "Go on, darling. The glowing one."
INTRO_LINES = ("Hello, darling. I'm Seraphine, of the Fairy Glade.",
               "Five minutes, and you'll know every button. Shall we?")
FAREWELL = "That's the tour. Replay me any time in Settings."

_ART = {}


# ---------------------------------------------------------------- state helpers
def _server_step(client):
    p = getattr(client, "player", None) or {}
    try:
        return int(p.get("guide_tour", 100))
    except (TypeError, ValueError):
        return 100


def _st(client):
    st = client.__dict__.get("_tour")
    if st is None:
        st = {"step": None, "t0": time.time(), "sent": None, "confirm_skip": False, "look_t": None,
              "marker": None, "clicked": False, "hp0": None, "bread0": None, "farewell": 0.0,
              "rects": {}}
        client._tour = st
    return st


def blocked_by_other_screens(client):
    if getattr(client, "state", None) != "GAME":
        return True
    if getattr(getattr(client, "outfitters", None), "active", False):
        return True
    if getattr(client, "needs_appearance", False):
        return True
    return False


def visible(client):
    """True while a tour pop-up is on screen (intro, a step, or the skip confirm)."""
    if blocked_by_other_screens(client):
        return False
    step = _server_step(client)
    if step == 0:
        return True
    if 1 <= step <= STEPS:
        # Steps after the talk wait for the conversation to finish.
        if step >= 4 and getattr(client, "dialogue", None):
            return False
        return True
    return False


def active(client):
    step = _server_step(client)
    return 0 <= step <= STEPS and not blocked_by_other_screens(client)


def send(client, action, **kw):
    try:
        client.net.send("GUIDE_TOUR", action=action, **kw)
    except Exception:
        pass


def on_state(client, msg):
    """GUIDE_TOUR_STATE from the server."""
    if client.player is not None:
        client.player["guide_tour"] = int(msg.get("step", 100))
        client.player["guide_bronze"] = bool(msg.get("bronze"))
        client.player["sewer_choice"] = msg.get("sewer_choice") or ""
    st = _st(client)
    st["sent"] = None
    if msg.get("gift"):
        play_chime()
        st["gift_t"] = time.time()
    if int(msg.get("step", 0)) in DONE_STATES and st.get("step") not in (None, 0) and st.get("step") not in DONE_STATES:
        st["farewell"] = time.time()


def replay(client):
    send(client, "replay")
    client.show_help = False


# ---------------------------------------------------------------- art
def play_chime():
    snd = _ART.get("chime")
    if snd is None:
        try:
            path = os.path.join(os.path.dirname(__file__), "..", "assets", "sounds", "guide_chime.wav")
            snd = pygame.mixer.Sound(path)
        except Exception:
            snd = False
        _ART["chime"] = snd
    if snd:
        try:
            snd.play()
        except Exception:
            pass


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
        base = E._grain(w, h, PARCH, 7, streak=False)
        surf.blit(base, (0, 0))
        tint = pygame.Surface((w, h), pygame.SRCALPHA)
        for i in range(18):   # darker, burnt edges
            pygame.draw.rect(tint, (120, 84, 40, 10), tint.get_rect().inflate(-i * 2, -i * 2), 2, border_radius=6)
        surf.blit(tint, (0, 0))
        _ART[key] = surf
    return _ART[key]


def _wood_frame(scr, r, corners=True):
    pygame.draw.rect(scr, (0, 0, 0), r.inflate(10, 10).move(0, 4), border_radius=8)
    outer = r.inflate(14, 14)
    scr.blit(E._grain(outer.w, outer.h, E.WOOD, 3), outer.topleft)
    pygame.draw.rect(scr, E.WOOD_DK, outer, 2, border_radius=6)
    pygame.draw.rect(scr, E.GOLD, r.inflate(4, 4), 2, border_radius=3)
    pygame.draw.rect(scr, E.GOLD_HI, r.inflate(8, 8), 1, border_radius=4)
    if corners:
        for cx, cy, fx, fy in ((outer.x, outer.y, 1, 1), (outer.right, outer.y, -1, 1),
                               (outer.x, outer.bottom, 1, -1), (outer.right, outer.bottom, -1, -1)):
            E._filigree(scr, cx, cy, fx, fy, size=34)


def _button(scr, r, label, hot=False, primary=False):
    if hot or primary:
        g = pygame.Surface((r.w + 14, r.h + 14), pygame.SRCALPHA)
        for i in range(7):
            pygame.draw.rect(g, (*E.GLOW, max(0, (80 if hot else 45) - i * 11)),
                             g.get_rect().inflate(-i * 2, -i * 2), 2, border_radius=8)
        scr.blit(g, (r.x - 7, r.y - 7))
    E._plaque(scr, r, rim=E.GOLD_HI if hot else E.GOLD)
    E._text(scr, label, E.font("title", 16), E.GOLD_HI if hot else E.TITLE_GOLD,
            (r.centerx, r.centery + 1), anchor="center")


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


# ---------------------------------------------------------------- targets
def _bag_rect(client, item_id):
    p = client.player or {}
    inv = p.get("inventory") or {}
    try:
        cells = client.inventory_slot_rects() or {}
    except Exception:
        cells = {}
    for idx, rect in cells.items():
        e = inv.get(str(idx)) or inv.get(idx)
        if e and e.get("item_id") == item_id:
            return rect
    return None


def _npc(client, npc_id):
    for n in getattr(client, "npcs", None) or []:
        if n.get("id") == npc_id:
            return n
    return None


def _tile_rect(client, x, y):
    """World tile -> on-screen rect, including the view zoom (scaled about the player)."""
    try:
        r = pygame.Rect(client.map_screen_rect(x, y))
        k = float(client._zoom_view_scale())
    except Exception:
        return None
    if abs(k - 1.0) > 1e-3 and client.player:
        pc = pygame.Rect(client.map_screen_rect(int(client.player["x"]), int(client.player["y"]))).center
        cx = pc[0] + (r.centerx - pc[0]) * k
        cy = pc[1] + (r.centery - pc[1]) * k
        r = pygame.Rect(0, 0, max(1, int(r.w * k)), max(1, int(r.h * k)))
        r.center = (int(cx), int(cy))
    return r


def _busy_tiles(client):
    """Tiles with something clickable on them (wells, boards, NPCs, trees): never put the marker there."""
    busy = set()
    for group in (getattr(client, "interactables", None) or [], getattr(client, "npcs", None) or [],
                  getattr(client, "resources", None) or []):
        for o in group:
            try:
                ox, oy = int(o.get("x")), int(o.get("y"))
            except (TypeError, ValueError, AttributeError):
                continue
            for dx in (-1, 0, 1):
                for dy in (-2, -1, 0, 1):
                    busy.add((ox + dx, oy + dy))
    return busy


def _landmark(client, c):
    try:
        return client.resolve_landmark_click(*c) is not None
    except Exception:
        return False


def _pick_marker(client):
    p = client.player or {}
    px, py = int(p.get("x", 0)), int(p.get("y", 0))
    n = _npc(client, TAMSIN)
    tx, ty = (int(n["x"]), int(n["y"])) if n else (px + 6, py)
    dx, dy = tx - px, ty - py
    d = max(1.0, math.hypot(dx, dy))
    busy = _busy_tiles(client)
    walkable = getattr(client, "tile_walkable", None)
    ux, uy = dx / d, dy / d
    for dist in (3, 2, 4):
        for side in (0, 1, -1, 2, -2):
            c = (px + int(round(ux * dist - uy * side)), py + int(round(uy * dist + ux * side)))
            if c == (px, py) or c in busy or _landmark(client, c):
                continue
            try:
                if walkable and not walkable(*c):
                    continue
            except Exception:
                pass
            return c
    return (px + 2, py)


def target_rect(client, step):
    """Screen rect of the ONE thing to press this step (None = nothing to ring)."""
    st = _st(client)
    rects = getattr(client, "hud_rects", None) or {}
    world = getattr(client, "hud_world_rects", None) or {}
    target = STEP_DEFS[step][0]
    if target == "marker":
        if st["marker"] is None:
            st["marker"] = _pick_marker(client)
        r = _tile_rect(client, *st["marker"])
        return r.inflate(8, 8) if r else None
    if target == "npc":
        n = _npc(client, TAMSIN)
        if not n:
            return None
        r = _tile_rect(client, n["x"], n["y"])
        if r is None or not pygame.Rect(0, 0, 900, 640).colliderect(r):
            return None
        return pygame.Rect(r.x - r.w // 4, r.y - int(r.h * 1.6), int(r.w * 1.5), int(r.h * 2.6)) if r else None
    if target == "quests":
        return (world.get("nav") or {}).get("quests")
    if target == "inventory":
        return (rects.get("systems") or {}).get("inventory")
    if target == "equipment":
        return rects.get("equipment")
    if target == "chestplate":
        if not getattr(client, "show_equipment", False):
            return rects.get("equipment")
        return _bag_rect(client, "bronze_body") or (rects.get("systems") or {}).get("inventory")
    if target == "equip_all":
        if not getattr(client, "show_equipment", False):
            return rects.get("equipment")
        return getattr(client, "equip_all_rect", None)
    if target == "eat":
        return (world.get("actions") or {}).get("eat")
    if target == "skills":
        return rects.get("skills") or getattr(client, "skills_btn_rect", None)
    return None


def extra_rects(client, step):
    """Secondary glows (not click targets): the Body slot on step 7, the stats on step 8."""
    out = []
    if step == 7 and getattr(client, "show_equipment", False):
        r = (getattr(client, "equip_slot_rects", None) or {}).get("body")
        if r:
            out.append(r)
        # Glow every bronze piece still in the bag so the set is easy to spot.
        for item_id in BRONZE_GIFT:
            if item_id == "bronze_body":
                continue
            br = _bag_rect(client, item_id)
            if br:
                out.append(br)
    if step == 8 and getattr(client, "show_equipment", False):
        for item_id in BRONZE_GIFT:
            br = _bag_rect(client, item_id)
            if br:
                out.append(br)
        if _st(client).get("look_t"):
            r = getattr(client, "_equip_doll_rect", None)
            if r:
                out.append(pygame.Rect(r))
    if step == 9:
        hp = getattr(client, "hud_hp_rect", None)
        if hp:
            out.append(hp)
        b = _bag_rect(client, "bread")
        if b:
            out.append(b)
    return out


def _hud_edges(client):
    """Right sidebar / chat strip edges — keep in sync with client.SIDEBAR_X / MAP_H."""
    try:
        import hud_v2
        _mw, mh, sx, _sw, _sh = hud_v2._layout()
        return int(sx), int(mh)
    except Exception:
        pass
    sw, sh = client.screen.get_size()
    return max(0, sw - 300), min(640, sh)


def _on_hud_chrome(client, mx, my):
    """True for the right bag column or the chat strip under the map."""
    sx, mh = _hud_edges(client)
    return mx >= sx or my >= mh


def _panel_clear_rects(client, step):
    """Larger undimmed areas so inventory / equipment stay bright on panel steps."""
    out = []
    rects = getattr(client, "hud_rects", None) or {}
    kind = STEP_DEFS.get(step, (None, (), ""))[2]
    # Any panel step that rings a HUD control: keep the whole right column bright.
    # (The old 5–9-only hole made bag buttons look live while clicks were still blocked.)
    if kind in ("click", "equip_body", "equip_all", "eat"):
        sx, _mh = _hud_edges(client)
        sw, sh = client.screen.get_size()
        out.append(pygame.Rect(sx, 0, max(1, sw - sx), sh))
    if step in (6, 7, 8) and getattr(client, "show_equipment", False):
        L = getattr(client, "_equip_layout", None) or {}
        vp = L.get("vp")
        if vp is not None:
            # Equipment window itself (already bright, but clear its shadow too).
            out.append(pygame.Rect(vp).inflate(24, 24))
        else:
            eq = rects.get("equipment")
            if eq:
                out.append(pygame.Rect(eq).inflate(20, 20))
    if step == 5:
        inv = (rects.get("systems") or {}).get("inventory")
        if inv:
            out.append(pygame.Rect(inv).inflate(16, 16))
    return out


# ---------------------------------------------------------------- progress
def _bread(client):
    inv = (client.player or {}).get("inventory") or {}
    return sum(int(e.get("qty") or 1) for e in inv.values() if e and e.get("item_id") == "bread")


def _done(client, step):
    st = _st(client)
    kind = STEP_DEFS[step][2]
    p = client.player or {}
    eq = p.get("equipment") or {}
    if kind == "walk":
        if st["marker"] is None:
            return False
        return max(abs(int(p.get("x", 0)) - st["marker"][0]), abs(int(p.get("y", 0)) - st["marker"][1])) <= 1
    if kind == "walk_npc":
        n = _npc(client, TAMSIN)
        if not n:
            return True
        return max(abs(int(p.get("x", 0)) - int(n["x"])), abs(int(p.get("y", 0)) - int(n["y"]))) <= 3
    if kind == "talk":
        d = getattr(client, "dialogue", None) or {}
        return d.get("npc_id") == TAMSIN
    if kind == "click":
        # Prefer live panel state so a GUIDE_TOUR_STATE refresh that clears
        # st["clicked"] cannot strand the step after the player already opened it.
        if step == 4:
            return st["clicked"] or bool(getattr(client, "show_quests", False))
        if step == 5:
            return st["clicked"] or bool(getattr(client, "show_inventory", False))
        if step == 6:
            return bool(getattr(client, "show_equipment", False))
        if step == 10:
            return st["clicked"] or bool(getattr(client, "show_skills", False))
        return st["clicked"]
    if kind == "equip_body":
        return eq.get("body") == "bronze_body"
    if kind == "equip_all":
        full = all(eq.get(s) for s in ("helmet", "body", "legs", "weapon", "shield"))
        if full and st["look_t"] is None:
            st["look_t"] = time.time()
        return full and time.time() - st["look_t"] >= LOOK_S
    if kind == "eat":
        hp = int(p.get("hp") or 0)
        if st["hp0"] is None:
            st["hp0"], st["bread0"] = hp, _bread(client)
            return False
        return hp > st["hp0"] or _bread(client) < (st["bread0"] or 0)
    return False


def tick(client):
    if blocked_by_other_screens(client):
        return
    step = _server_step(client)
    st = _st(client)
    if st["step"] != step:
        st.update(step=step, t0=time.time(), clicked=False, look_t=None, hp0=None, bread0=None,
                  confirm_skip=False)
        if step == 1:
            st["marker"] = None
    if not (1 <= step <= STEPS) or STEP_DEFS[step][2] == "sewer":
        return
    if step >= 4 and getattr(client, "dialogue", None):
        st["t0"] = time.time()   # don't nudge while she waits for the talk to end
        return
    if st["sent"] != step and _done(client, step):
        st["sent"] = step
        send(client, "advance", step=step)


# ---------------------------------------------------------------- input
def _panel_buttons(client):
    return _st(client).get("rects") or {}


def handle_click(client, event):
    """Return True if the tour used (or blocked) this click."""
    if not visible(client) or getattr(event, "button", 1) != 1:
        return False
    mx, my = event.pos
    st = _st(client)
    step = _server_step(client)
    b = _panel_buttons(client)

    def hit(k):
        r = b.get(k)
        return r is not None and r.collidepoint(mx, my)

    if st["confirm_skip"]:
        if hit("skip_yes"):
            send(client, "skip")
            st["confirm_skip"] = False
        elif hit("skip_no"):
            st["confirm_skip"] = False
        return True
    if hit("skip"):
        st["confirm_skip"] = True
        return True
    if step == 0:
        if hit("start"):
            send(client, "start")
        elif hit("played"):
            send(client, "played_before")
        return True
    kind = STEP_DEFS[step][2]
    if kind == "sewer":
        if hit("go"):
            send(client, "sewer", choice="go")
        elif hit("later"):
            send(client, "sewer", choice="later")
        return True
    if b.get("panel") and b["panel"].collidepoint(mx, my):
        return True
    tr = target_rect(client, step)
    if tr is not None and tr.collidepoint(mx, my):
        st["clicked"] = True
        return False     # let the game handle the real click
    # One-action panel steps: chrome that is NOT the target stays swallowed
    # (Skills must not open during Quests; inventory/equipment targets already
    # returned above). Walk/talk leave the world — and chrome — clickable.
    if _on_hud_chrome(client, mx, my):
        if kind in ("click", "equip_body", "equip_all", "eat"):
            return True
        return False
    if kind in ("walk", "walk_npc", "talk"):
        return False     # walking steps leave the world clickable
    if kind == "eat":
        br = _bag_rect(client, "bread")
        if br and br.collidepoint(mx, my):
            return False
    for r in extra_rects(client, step):
        if r is not None and getattr(r, "collidepoint", None) and r.collidepoint(mx, my):
            return False
    # one action at a time: everything else is dimmed and ignored
    return True


# ---------------------------------------------------------------- draw
def _dim(scr, holes, alpha):
    """Dim the screen, punching clear holes so tutorial targets stay bright."""
    w, h = scr.get_size()
    sh = pygame.Surface((w, h), pygame.SRCALPHA)
    sh.fill((2, 3, 5, alpha))
    if holes is None:
        holes = []
    elif not isinstance(holes, (list, tuple)):
        holes = [holes]
    for hole in holes:
        if hole is None:
            continue
        hr = hole.inflate(12, 12)
        pygame.draw.rect(sh, (0, 0, 0, 0), hr, border_radius=10)
        for i in range(6):   # soft feather (lighter than before so panels don't re-darken)
            pygame.draw.rect(
                sh, (2, 3, 5, max(0, alpha - 22 * (6 - i))),
                hr.inflate(i * 2, i * 2), 2, border_radius=10 + i,
            )
    scr.blit(sh, (0, 0))


def _ring(scr, r, t, strong=False, soft=False):
    pulse = 0.5 + 0.5 * math.sin(t * (6.0 if strong else 3.6))
    grow = int(4 + pulse * (10 if strong else 5))
    rr = r.inflate(grow * 2, grow * 2)
    g = pygame.Surface((rr.w + 24, rr.h + 24), pygame.SRCALPHA)
    base = 70 if soft else 150
    for i in range(10):
        pygame.draw.rect(g, (*E.GLOW, max(0, int(base * (1 - i / 10.0) * (0.6 + 0.4 * pulse)))),
                         pygame.Rect(12 - i, 12 - i, rr.w + i * 2, rr.h + i * 2), 2, border_radius=10 + i)
    scr.blit(g, (rr.x - 12, rr.y - 12))
    if not soft:
        pygame.draw.rect(scr, E.GOLD_HI, rr, 3, border_radius=10)
        pygame.draw.rect(scr, (120, 84, 30), rr.inflate(6, 6), 1, border_radius=12)


def _pointer(scr, r, t):
    """A small gold arrow bobbing above the target."""
    bob = int(6 * math.sin(t * 5))
    cx = r.centerx
    tip_y = r.y - 10 + bob
    if tip_y < 40:
        tip_y = r.bottom + 10 - bob
        pts = [(cx, tip_y), (cx - 12, tip_y + 18), (cx + 12, tip_y + 18)]
    else:
        pts = [(cx, tip_y), (cx - 12, tip_y - 18), (cx + 12, tip_y - 18)]
    pygame.draw.polygon(scr, (0, 0, 0), [(x + 2, y + 2) for x, y in pts])
    pygame.draw.polygon(scr, E.GOLD_HI, pts)
    pygame.draw.polygon(scr, (120, 84, 30), pts, 2)


def _marker(client, scr, t):
    st = _st(client)
    if not st.get("marker"):
        return
    r = _tile_rect(client, *st["marker"])
    if not r:
        return
    pulse = 0.5 + 0.5 * math.sin(t * 4)
    g = pygame.Surface((r.w * 2, r.h), pygame.SRCALPHA)
    gr = g.get_rect()
    for i in range(6):
        pygame.draw.ellipse(g, (*E.GLOW, int((90 - i * 14) * (0.6 + 0.4 * pulse))), gr.inflate(-i * 6, -i * 3), 3)
    scr.blit(g, (r.centerx - r.w, r.centery - r.h // 2 + r.h // 4))


def _layout_panel(scr, avoid):
    w, h = scr.get_size()
    pw, ph = 150, 200
    port = pygame.Rect(22, h - ph - 26, pw, ph)
    speech = pygame.Rect(port.right + 22, h - 150, 380, 112)
    group = port.union(speech).inflate(30, 30)
    if avoid is not None and group.colliderect(avoid):
        port.y = 64
        speech.y = port.y + 40
    return port, speech


def draw(client):
    if not visible(client):
        _draw_farewell(client)
        return
    scr = client.screen
    t = time.time()
    st = _st(client)
    step = _server_step(client)
    rects = {}
    if step == 0:
        _dim(scr, None, DIM_A)
        port, speech = _layout_panel(scr, None)
        lines = INTRO_LINES
        kind = "intro"
        tr = None
    else:
        target, lines, kind = STEP_DEFS[step]
        tr = target_rect(client, step)
        if kind == "equip_all" and st.get("look_t"):
            lines = (LOOK_LINE, "Defence up. Every slot filled.")
            tr = None
        world_step = kind in ("walk", "walk_npc", "talk")
        holes = []
        if tr is not None:
            holes.append(tr)
        if not world_step:
            holes.extend(_panel_clear_rects(client, step))
            holes.extend(extra_rects(client, step))
        _dim(scr, holes, DIM_WORLD_A if world_step else DIM_PANEL_A)
        if step == 1:
            _marker(client, scr, t)
        for er in extra_rects(client, step):
            _ring(scr, er, t, soft=True)
        nudge = t - st["t0"] > NUDGE_S
        if tr is not None:
            _ring(scr, tr, t, strong=nudge)
            _pointer(scr, tr, t)
        if nudge and kind != "sewer":
            lines = (lines[0], NUDGE_LINE)
        port, speech = _layout_panel(scr, tr)
    # portrait
    _wood_frame(scr, port)
    scr.blit(_portrait(port.w, port.h), port.topleft)
    glow = pygame.Surface(port.size, pygame.SRCALPHA)
    pygame.draw.rect(glow, (*LILAC, 40), glow.get_rect(), 3)
    scr.blit(glow, port.topleft)
    plate = pygame.Rect(0, 0, 132, 26)
    plate.midtop = (port.centerx, port.bottom - 6)
    E._plaque(scr, plate)
    E._text(scr, "Seraphine", E.font("title", 16), E.TITLE_GOLD, (plate.centerx, plate.centery + 1), anchor="center")
    # speech parchment
    if kind in ("sewer", "intro"):
        speech = speech.inflate(0, 44).move(0, -44)
    _wood_frame(scr, speech, corners=False)
    scr.blit(_parchment(speech.w, speech.h), speech.topleft)
    # little tail pointing at her
    tail = [(speech.x, speech.y + 34), (speech.x - 16, speech.y + 44), (speech.x, speech.y + 54)]
    pygame.draw.polygon(scr, PARCH, tail)
    y = speech.y + 12
    fmain = E.font("body", 22)
    for ln in _wrap(lines[0], fmain, speech.w - 28):
        E._text(scr, ln, fmain, INK, (speech.x + 14, y), shadow=False)
        y += 25
    fsub = E.font("body", 17)
    E._text(scr, lines[1], fsub, INK_SOFT, (speech.x + 14, y + 2), shadow=False)
    if 1 <= step <= STEPS:
        E._text(scr, f"{step} / {STEPS}", E.font("title", 13), INK_SOFT, (speech.right - 10, speech.y + 8),
                shadow=False, anchor="topright")
    mx, my = pygame.mouse.get_pos()
    by = speech.bottom - 42
    if kind == "intro":
        rects["start"] = pygame.Rect(speech.x + 14, by, 170, 32)
        rects["played"] = pygame.Rect(speech.x + 196, by, 170, 32)
        _button(scr, rects["start"], "Show me around", rects["start"].collidepoint(mx, my), primary=True)
        _button(scr, rects["played"], "I've played before", rects["played"].collidepoint(mx, my))
    elif kind == "sewer":
        rects["go"] = pygame.Rect(speech.x + 14, by, 170, 32)
        rects["later"] = pygame.Rect(speech.x + 196, by, 170, 32)
        _button(scr, rects["go"], "Go now", rects["go"].collidepoint(mx, my), primary=True)
        _button(scr, rects["later"], "Not now", rects["later"].collidepoint(mx, my))
    rects["skip"] = pygame.Rect(speech.x, speech.bottom + 14, 108, 30)
    if 1 <= step <= STEPS or step == 0:
        _button(scr, rects["skip"], "Skip", rects["skip"].collidepoint(mx, my))
    rects["panel"] = port.union(speech).inflate(16, 16)
    if t - st.get("gift_t", 0) < 2.5:
        _gift_toast(client, scr, t - st["gift_t"])
    if st["confirm_skip"]:
        _confirm(client, scr, rects, mx, my)
    st["rects"] = rects


def _gift_toast(client, scr, age):
    a = 255 if age < 2.0 else int(255 * (2.5 - age) / 0.5)
    w, _h = scr.get_size()
    f = E.font("title", 20)
    txt = "Gift: full Bronze set + bread"
    r = pygame.Rect(0, 0, f.size(txt)[0] + 40, 40)
    r.midtop = (min(w - 300, 900) // 2 if w > 900 else w // 2, 70 - int(max(0, 0.3 - age) * 60))
    s = pygame.Surface(r.size, pygame.SRCALPHA)
    E._plaque(s, s.get_rect())
    E._text(s, txt, f, E.GOLD_HI, (r.w // 2, r.h // 2 + 1), anchor="center")
    s.set_alpha(max(0, a))
    scr.blit(s, r.topleft)


def _confirm(client, scr, rects, mx, my):
    w, h = scr.get_size()
    sh = pygame.Surface((w, h), pygame.SRCALPHA)
    sh.fill((2, 3, 5, 120))
    scr.blit(sh, (0, 0))
    box = pygame.Rect(0, 0, 380, 150)
    box.center = (min(w, 900) // 2, h // 2)
    _wood_frame(scr, box)
    scr.blit(E._grain(box.w, box.h, E.PANEL, 11, streak=False), box.topleft)
    pygame.draw.rect(scr, E.GOLD, box, 1)
    E._text(scr, "Skip the tour?", E.font("title", 22), E.TITLE_GOLD, (box.centerx, box.y + 30), anchor="center")
    E._text(scr, "You keep the bronze set. Replay it in Settings.", E.font("body", 18), E.TEXT,
            (box.centerx, box.y + 64), anchor="center")
    rects["skip_yes"] = pygame.Rect(box.x + 40, box.bottom - 50, 130, 32)
    rects["skip_no"] = pygame.Rect(box.right - 170, box.bottom - 50, 130, 32)
    _button(scr, rects["skip_yes"], "Skip tour", rects["skip_yes"].collidepoint(mx, my))
    _button(scr, rects["skip_no"], "Keep going", rects["skip_no"].collidepoint(mx, my), primary=True)


def _draw_farewell(client):
    st = client.__dict__.get("_tour")
    if not st or not st.get("farewell") or blocked_by_other_screens(client):
        return
    age = time.time() - st["farewell"]
    if age > 4.0:
        return
    scr = client.screen
    f = E.font("body", 21)
    r = pygame.Rect(0, 0, f.size(FAREWELL)[0] + 40, 44)
    r.midtop = (min(scr.get_width(), 900) // 2, 64)
    s = pygame.Surface(r.size, pygame.SRCALPHA)
    s.blit(_parchment(r.w, r.h), (0, 0))
    pygame.draw.rect(s, E.GOLD, s.get_rect(), 2)
    E._text(s, FAREWELL, f, INK, (r.w // 2, r.h // 2), shadow=False, anchor="center")
    s.set_alpha(255 if age < 3.4 else int(255 * (4.0 - age) / 0.6))
    scr.blit(s, r.topleft)
