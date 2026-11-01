"""Boss duel v2: stage, fighters, HUD, input and the pre-duel film (client side of server/arena_duel.py).

Controls (learnable in 30 s; the action bar is clickable too):
  Q or left-click      tap = quick strike / shot, HOLD = heavy blow / charged shot (release to swing)
  F or right-click     parry (gold tells)            Space   dodge (red tells)
  hold A / D           step back / step in, smoothly  R       finishing move when the crowd demands it
  1 / 2 / 3            pick Sword / Axe / Bow before the duel (or click a card)
Input is buffered: a press during your own recovery fires on the first free step (server queue).

Rendering: the stage is composed on its own opaque surface (the Mac window is ARGB: per-pixel
alpha blitted straight onto it showed black boxes), fighters are the painted HD duel poses with
layered transforms (eased tweens, breathing, anticipation / strike / follow-through, knockback,
hit flash, dodge hop, stagger, KO), cross-faded pose changes, hit-stop, screen shake, sparks,
dust and sand kicked up by steps.  The player fighter is their own character: gender + full armour
set of their tier (or the arena steel set) + the weapon they picked.  Old rig art = error fallback only.
"""
from __future__ import annotations

import math
import os
import random

import pygame

KEYS = {pygame.K_q: "light", pygame.K_e: "heavy", pygame.K_f: "parry", pygame.K_SPACE: "dodge",
        pygame.K_a: "back", pygame.K_d: "forward", pygame.K_r: "finish"}
CALLOUTS = {"parried": ("PARRY", (255, 220, 120)), "dodged": ("DODGE", (170, 220, 255)),
            "guard_break": ("GUARD BROKEN", (255, 170, 90)), "second_wind": ("SECOND WIND!", (255, 120, 90)),
            "rolled_past": ("ROLLED PAST", (170, 220, 255)), "cornered": ("NO ROOM", (230, 120, 110)),
            "no_stamina": ("OUT OF STAMINA", (230, 160, 120))}
GOLD = (220, 178, 92)
HOLD_MS = 260            # attack key held this long = heavy (bow: charged shot)
MOVE_REPEAT_MS = 200     # held A / D re-sends one step per duel step
WEAPONS = (("sword", "Sword", "Balanced. Quick cuts,", "the best parry window."),
           ("axe", "Axe", "Slow, brutal. Heavy blows", "break guards. Weak parry."),
           ("bow", "Bow", "Hold to draw, release.", "Kite with A/D. Weak up close."))
TIER_NAME = {"arena": "Arena steel", "bronze": "Bronze", "iron": "Iron", "steel": "Steel", "mithril": "Mithril",
             "adamant": "Adamant", "rune": "Rune", "mythos": "Dragon Mythos", "eclipse": "Eclipse"}


def duel(client):
    m = getattr(client, "arena_match", None) or {}
    return m.get("duel") if m.get("active") else None


def _preview_duel(client):
    m = getattr(client, "arena_match", None) or {}
    if m.get("active") and (m.get("phase") or "preview") == "preview":
        return (m.get("hud") or {}).get("duel")
    return None


def _fx(m):
    v = m.get("_v2")
    if v is None:
        v = m["_v2"] = {"hero": Fighter("hero"), "boss": Fighter("boss"), "parts": [], "shake": 0.0,
                        "shake_t": 0, "freeze": 0, "clock": 0.0, "last": None, "arrows": [],
                        "press": {}, "move_next": 0, "tel_t": 0, "tel": None, "began": None}
    return v


def on_message(client, msg):
    m = getattr(client, "arena_match", None)
    if not m:
        return
    prev = m.get("duel") or {}
    m["duel"] = msg.get("duel") or {}
    now = pygame.time.get_ticks()
    fx = m.setdefault("duel_fx", [])
    v = _fx(m)
    tel = m["duel"].get("telegraph")
    if tel:
        v["tel"], v["tel_t"] = dict(tel), now
    else:
        v["tel"] = None
    for e in msg.get("events") or []:
        k = e.get("kind")
        if k in CALLOUTS:
            text, col = CALLOUTS[k]
            if e.get("perfect"):
                text = "PERFECT " + text
            fx.append({"t": now, "text": text, "col": col})
        elif k == "boss_hit" and "counter" in str(e.get("tag")):
            fx.append({"t": now, "text": "COUNTER!", "col": (255, 236, 160)})
        elif k == "boss_hit" and "crit" in str(e.get("tag")):
            fx.append({"t": now, "text": "CRITICAL!", "col": (255, 200, 120)})
        try:
            _react(v, m["duel"], e, _anow(v, now))
        except Exception:
            pass
    del fx[:-4]
    _ = now
    _commentary(client, m, msg.get("events") or [])


def _commentary(client, m, events):
    """Keep the log strip and chat in step with the live exchange (not the pre-fight prompt)."""
    try:
        import sys, os as _os
        sd = _os.path.join(_os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))), "server")
        if sd not in sys.path:
            sys.path.append(sd)
        from arena_duel import exchange_line
    except Exception:
        exchange_line = None
    foe = str(m.get("foe_name") or (m.get("hud") or {}).get("foe_name") or "The champion")
    hud = m.setdefault("hud", {})
    log = list(hud.get("log") or [])
    if not m.get("duel_began"):
        m["duel_began"] = True
        log = [l for l in log if "salutes" not in l and "Start Duel" not in l]
        if not log:
            log.append(f"Duel on vs {foe}!")
        if hasattr(client, "add_chat") and not any(exchange_line and exchange_line(e, foe) for e in events):
            client.add_chat("Arena: " + log[-1], color=(255, 220, 90))
    for e in events:
        line = exchange_line(e, foe) if exchange_line else None
        if not line:
            continue
        log.append(line)
        if hasattr(client, "add_chat") and e.get("kind") not in ("whiff", "boss_miss"):
            client.add_chat("Arena: " + line, color=(255, 220, 90))
    hud["log"] = log[-24:]


# ---------------------------------------------------------------------------------------------
# Input
# ---------------------------------------------------------------------------------------------
def _send(client, m, mv):
    d = m.get("duel") or {}
    if mv == "parry" and d.get("style") == "bow":
        mv = "dodge"
    client.net.send("BARRACKS", action="duel_move", move=mv)
    now = pygame.time.get_ticks()
    m["last_move"] = (mv, now)
    try:
        _local_anim(_fx(m), d, mv, _anow(_fx(m), now))
    except Exception:
        pass


def handle_event(client, event) -> bool:
    m = getattr(client, "arena_match", None) or {}
    if _intro_active(m):
        if event.type in (pygame.KEYDOWN, pygame.MOUSEBUTTONDOWN):
            if event.type == pygame.MOUSEBUTTONDOWN or event.key in (pygame.K_SPACE, pygame.K_ESCAPE, pygame.K_RETURN):
                if pygame.time.get_ticks() - _INTRO.get("start", 0) > 300:
                    _intro_end(client, m)
            return True
        return event.type in (pygame.KEYUP, pygame.MOUSEBUTTONUP)
    pd = _preview_duel(client)
    if pd is not None:
        pick = None
        if event.type == pygame.KEYDOWN and event.key in (pygame.K_1, pygame.K_2, pygame.K_3):
            pick = ("sword", "axe", "bow")[event.key - pygame.K_1]
        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            for st, r in (m.get("pick_rects") or {}).items():
                if r.collidepoint(event.pos):
                    pick = st
        if pick:
            if pick != pd.get("style"):
                client.net.send("BARRACKS", action="duel_style", style=pick)
                m["picked"] = (pick, pygame.time.get_ticks())
            return True
        return False
    d = duel(client)
    if not d or (m.get("phase") or "fight") != "fight":
        return False
    v = _fx(m)
    now = pygame.time.get_ticks()
    btns = m.get("duel_btns") or {}
    # attack: tap / hold on Q, E (always heavy), left mouse on the stage
    if event.type == pygame.KEYDOWN and event.key == pygame.K_q:
        if "atk" not in v["press"]:
            v["press"]["atk"] = now
            _local_anim(v, d, "charge", _anow(v, now))
        return True
    if event.type == pygame.KEYUP and event.key == pygame.K_q:
        t0 = v["press"].pop("atk", None)
        if t0 is not None:
            _send(client, m, "heavy" if now - t0 >= HOLD_MS else "light")
        return True
    if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
        for mv, r in btns.items():
            if r.collidepoint(event.pos):
                if mv == "attack":
                    v["press"]["atk"] = now
                    v["press"]["mouse"] = True
                    _local_anim(v, d, "charge", _anow(v, now))
                elif mv == "move":
                    _send(client, m, "back" if event.pos[0] < r.centerx else "forward")
                else:
                    _send(client, m, mv)
                return True
        for r in (getattr(client, "arena_hud_rects", {}) or {}).values():
            if hasattr(r, "collidepoint") and r.collidepoint(event.pos):
                return False
        if event.pos[1] < (m.get("stage_bottom") or 10 ** 6):
            v["press"]["atk"] = now
            v["press"]["mouse"] = True
            _local_anim(v, d, "charge", _anow(v, now))
            return True
        return False
    if event.type == pygame.MOUSEBUTTONUP and event.button == 1 and v["press"].pop("mouse", None):
        t0 = v["press"].pop("atk", None)
        if t0 is not None:
            _send(client, m, "heavy" if now - t0 >= HOLD_MS else "light")
        return True
    if event.type == pygame.MOUSEBUTTONDOWN and event.button == 3:
        _send(client, m, "parry")
        return True
    if event.type == pygame.KEYDOWN and event.key in KEYS:
        mv = KEYS[event.key]
        if mv in ("back", "forward"):
            v["move_next"] = now + MOVE_REPEAT_MS + 60   # first step now, then repeat while held
        _send(client, m, mv)
        return True
    if event.type == pygame.KEYUP and event.key in KEYS:
        return True
    return False


def _poll_held(client, m, d, now):
    """Held A / D walk smoothly: one step per duel step while the key is down."""
    v = _fx(m)
    try:
        keys = pygame.key.get_pressed()
    except Exception:
        return
    mv = "back" if keys[pygame.K_a] and not keys[pygame.K_d] else ("forward" if keys[pygame.K_d] and not keys[pygame.K_a] else None)
    if mv and now >= v["move_next"]:
        v["move_next"] = now + MOVE_REPEAT_MS
        _send(client, m, mv)


# ---------------------------------------------------------------------------------------------
# Fighter animation (client-side layered transforms over the painted poses)
# ---------------------------------------------------------------------------------------------
def _ease_out(u):
    return 1 - (1 - u) ** 3


def _ease_in_out(u):
    return 3 * u * u - 2 * u * u * u


def _back(u, s=1.7):
    u -= 1
    return u * u * ((s + 1) * u + s) + 1


# which painted pose each action shows
_POSES = {
    "sword": {"windup": "block", "strike": "attack", "heavy": "attack", "parry": "block", "charge": "block"},
    "axe": {"windup": "attack", "strike": "attack", "heavy": "attack", "parry": "block", "charge": "attack"},
    "bow": {"windup": "attack", "strike": "attack", "heavy": "attack", "parry": "block", "charge": "attack"},
    "boss": {"windup": "idle", "strike": "attack", "heavy": "attack", "parry": "block", "charge": "idle"},
}


class Fighter:
    def __init__(self, side):
        self.side = side
        self.x = None
        self.act = ("idle", 0, 1)
        self.kx = 0.0          # knockback offset (springs back)
        self.kv = 0.0
        self.flash = (0, (255, 255, 255))
        self.walk = 0.0        # step phase while moving
        self.moving = 0.0
        self.pose = "idle"
        self.prev = None       # (surface, t) for the pose cross-fade
        self.ko = None
        self.tell = None       # (kind, start, dur) boss wind-up variant

    def play(self, act, now, dur):
        if self.ko is not None:
            return
        self.act = (act, now, dur)

    def busy(self, now, kinds=None):
        a, t0, dur = self.act
        return now - t0 < dur and (kinds is None or a in kinds)

    def hit(self, now, power=1.0, col=(255, 255, 255)):
        self.play("hit", now, 360)
        self.kv = -(380 + 260 * power)
        self.flash = (now, col)

    def update(self, target, dt):
        if self.x is None:
            self.x = float(target)
        dx = target - self.x
        k = 1 - math.exp(-dt * 9.0)          # critically damped ease toward the server spot
        step = dx * k
        self.x += step
        sp = abs(step) / max(1e-3, dt)
        self.moving = min(1.0, sp / 120.0)
        self.walk += dt * (6.0 + sp / 30.0) * (1 if self.moving > 0.05 else 0)
        # knockback spring
        self.kv += (-self.kx * 120.0 - self.kv * 16.0) * dt
        self.kx += self.kv * dt

    def transform(self, now, style):
        """-> pose, dx (forward +), dy (up -), rot (forward lean +, degrees), sx, sy."""
        a, t0, dur = self.act
        u = max(0.0, min(1.0, (now - t0) / float(max(1, dur))))
        live = now - t0 < dur
        P = _POSES["boss" if self.side == "boss" else style]
        breathe = math.sin(now / 520.0 + (1.3 if self.side == "boss" else 0))
        pose, dx, dy, rot, sx, sy = "idle", 0.0, 0.0, 0.6 * breathe, 1 - 0.006 * breathe, 1 + 0.012 * breathe
        if self.moving > 0.05 and not live:
            ph = math.sin(self.walk * 2)
            dy = -abs(ph) * 5 * self.moving
            rot += 2.5 * self.moving
            sy *= 1 - 0.015 * abs(ph)
        if self.ko is not None:
            k = min(1.0, (now - self.ko) / 750.0)
            e = k * k
            return "hit", -30 * _ease_out(k), 18 * e, -82 * e, 1.0, 1.0 - 0.05 * e
        if not live:
            return pose, dx, dy, rot, sx, sy
        if a in ("strike", "heavy"):
            lunge = 54 if a == "heavy" else 36
            ant = 0.26 if a == "heavy" else 0.2
            if u < ant:
                e = _ease_out(u / ant)
                pose = P["windup"] if a == "heavy" else P["strike"]
                dx, rot, sy, sx = -12 * e, -5 * e, 1 - 0.02 * e, 1 + 0.015 * e
            elif u < 0.55:
                e = _back((u - ant) / (0.55 - ant))
                pose = P["strike"]
                dx, rot = -12 + (lunge + 12) * e, -5 + 13 * e
                sx, sy = 1 + 0.03 * (1 - e), 1 - 0.01
            else:
                e = _ease_in_out((u - 0.55) / 0.45)
                pose = P["strike"] if u < 0.8 else "idle"
                dx, rot = lunge * (1 - e), 8 * (1 - e)
        elif a == "charge":       # holding the attack key / boss wind-up
            e = _ease_out(min(1.0, u * 1.6))
            pose = P["charge"] if self.side != "boss" else "idle"
            tr = math.sin(now / 28.0) * 1.2 * e
            dx, rot, sy, sx = -14 * e + tr, -7 * e, 1 - 0.025 * e, 1 + 0.02 * e
            if self.side == "boss" and self.tell:
                kind = self.tell
                if kind == "throw":
                    dx, rot = -20 * e, -11 * e
                elif kind == "charge":
                    dx, rot, sy, sx = -8 * e, 9 * e, 1 - 0.07 * e, 1 + 0.05 * e
                elif kind == "spin":
                    rot = 6 * math.sin(now / 70.0) * e
                    dx = 0
        elif a == "parry":
            pose = P["parry"]
            e = math.sin(math.pi * u)
            dx, rot = -8 * e, -3 * e
        elif a == "parry_ok":
            pose = P["parry"]
            e = math.sin(math.pi * min(1.0, u * 1.3))
            dx, rot, sx, sy = -16 * e, -6 * e, 1 + 0.03 * e, 1 - 0.02 * e
        elif a == "dodge":
            pose = "dodge"
            e = math.sin(math.pi * u)
            dx, dy, rot = -34 * e, -46 * e, -12 * e
            sy = 1 + 0.03 * e
        elif a == "hit":
            pose = "hit" if u < 0.75 else "idle"
            e = 1 - _ease_out(u)
            rot, sy, sx = -9 * e, 1 - 0.03 * e, 1 + 0.02 * e
        elif a == "stagger":
            pose = "hit"
            e = 1 - u
            rot = -6 * e + 4 * math.sin(now / 55.0) * e
            dx = -6 * e
        elif a == "whiff":
            pose = P["strike"]
            e = math.sin(math.pi * u)
            dx, rot = 26 * e, 10 * e
        return pose, dx, dy, rot, sx, sy


def _tell_kind(atk):
    a = str(atk or "")
    if any(k in a for k in ("throw", "spear", "net")):
        return "throw"
    if any(k in a for k in ("charge", "rush", "pounce", "leap", "bash")):
        return "charge"
    if any(k in a for k in ("roar", "stomp", "sweep", "spin")):
        return "spin"
    return "lean"


def _local_anim(v, d, mv, now):
    h = v["hero"]
    if mv == "charge":
        h.play("charge", now, 4000)
    elif mv in ("light", "finish"):
        h.play("strike", now, 380)
        if d.get("style") == "bow":
            v["arrows"].append({"t": now + 120, "dur": 170, "heavy": False})
    elif mv == "heavy":
        h.play("heavy", now, 560)
        if d.get("style") == "bow":
            v["arrows"].append({"t": now + 200, "dur": 150, "heavy": True})
    elif mv == "parry":
        h.play("parry", now, 420)
    elif mv == "dodge":
        h.play("dodge", now, 430)
        _dust(v, "hero", 10)


def _react(v, d, e, now):
    k = e.get("kind")
    h, b = v["hero"], v["boss"]
    tag = str(e.get("tag") or "")
    if k == "boss_hit":
        heavy = tag.startswith("heavy") or "crit" in tag or "counter" in tag
        if not h.busy(now, ("strike", "heavy")):
            h.play("heavy" if tag.startswith("heavy") else "strike", now - 110, 560 if heavy else 380)
        b.hit(now, 1.4 if heavy else 0.8)
        v["freeze"] = pygame.time.get_ticks() + (95 if heavy else 55)
        _shake(v, now, 9 if heavy else 4)
        _spark(v, "boss", 26 if heavy else 14, (255, 236, 190))
    elif k == "player_hit":
        b.play("strike", now - 120, 420)
        h.hit(now, 1.2, (255, 120, 100))
        v["freeze"] = pygame.time.get_ticks() + 85
        _shake(v, now, 8)
        _spark(v, "hero", 16, (255, 170, 130))
    elif k == "parried":
        h.play("parry_ok", now, 460)
        b.play("stagger", now, 700)
        v["freeze"] = pygame.time.get_ticks() + 110
        _shake(v, now, 6)
        _spark(v, "clash", 34 if e.get("perfect") else 22, (255, 220, 120))
    elif k == "dodged":
        if not h.busy(now, ("dodge",)):
            h.play("dodge", now - 80, 430)
        b.play("whiff", now, 420)
        _dust(v, "hero", 12)
    elif k == "boss_windup":
        b.tell = _tell_kind(e.get("atk"))
        b.play("charge", now, int(e.get("steps") or 3) * 200 + 120)
        if b.tell == "charge":
            _dust(v, "boss", 8)
    elif k == "boss_miss":
        b.play("whiff", now, 420)
    elif k == "player_windup":
        h.play("charge", now, 800)
    elif k == "guard_break":
        b.play("stagger", now, 700)
        _spark(v, "boss", 20, (255, 190, 110))
        _shake(v, now, 6)
    elif k == "whiff":
        h.play("whiff", now, 380)
    elif k == "end":
        loser = b if e.get("won") else h
        loser.ko = now
        _dust(v, "boss" if e.get("won") else "hero", 26)
        _shake(v, now, 10)


def _anow(v, t=None):
    """Animation clock: real ticks minus time spent in hit-stop."""
    return (pygame.time.get_ticks() if t is None else t) - int(v.get("frozen", 0))


def _shake(v, now, amp):
    now = pygame.time.get_ticks()          # shake decays on real time
    v["shake"] = max(v["shake"] * max(0.0, 1 - (now - v["shake_t"]) / 260.0), amp)
    v["shake_t"] = now


def _spark(v, where, n, col):
    v["parts"].append({"spawn": where, "n": n, "col": col, "kind": "spark"})


def _dust(v, where, n):
    v["parts"].append({"spawn": where, "n": n, "col": (196, 160, 110), "kind": "dust"})


# ---------------------------------------------------------------------------------------------
# Painted sprite frames
# ---------------------------------------------------------------------------------------------
_SPR_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets", "castle_realm", "arena", "duel_sprites")
_SPR = {}
FIGHTER_H = 0.46      # grounded fighter height as a fraction of map height
RIM_COL = (255, 178, 92)
STAGE_FEET = 0.70
HERO_TILE = 158
PX_PER_GAP = 52
# full-set tint over the painted steel plate (TIERS_SPEC base colours); arena = the plain issue set
TIER_TINT = {"arena": None, "bronze": ((176, 122, 60), 0.62), "iron": ((150, 146, 140), 0.35),
             "steel": ((150, 170, 196), 0.30), "mithril": ((110, 160, 230), 0.55),
             "adamant": ((63, 140, 90), 0.58), "rune": ((70, 170, 190), 0.55),
             "mythos": ((190, 44, 36), 0.62), "eclipse": ((30, 26, 22), 0.70)}


def _lit(img, rim_dir):
    """Warm grade + soft rim light on the side facing the arena sun."""
    import numpy as np
    rgb = pygame.surfarray.array3d(img).astype(np.float32)
    a = pygame.surfarray.array_alpha(img).astype(np.float32) / 255.0
    rgb *= np.array([1.04, 0.98, 0.90], np.float32)
    dx = 4 * rim_dir
    sh = np.zeros_like(a)
    if dx > 0:
        sh[dx:, :] = a[:-dx, :]
    else:
        sh[:dx, :] = a[-dx:, :]
    sh2 = np.zeros_like(a); sh2[:, 3:] = a[:, :-3]
    edge = np.clip(a - np.minimum(sh, sh2), 0, 1)[..., None]
    rgb = rgb * (1 - 0.55 * edge) + np.array(RIM_COL, np.float32) * 0.55 * edge * 1.25
    out = img.copy()
    pygame.surfarray.blit_array(out, np.clip(rgb, 0, 255).astype(np.uint8))
    pa = pygame.surfarray.pixels_alpha(out)
    pa[:] = (a * 255).astype(np.uint8)
    del pa
    return out


def _tint(img, tier):
    """Re-colour the plate (low-saturation metal pixels) to the armour tier; skin, hair, tabard stay."""
    spec = TIER_TINT.get(tier)
    if not spec:
        return img
    import numpy as np
    col, amt = spec
    rgb = pygame.surfarray.array3d(img).astype(np.float32)
    mx, mn = rgb.max(axis=2), rgb.min(axis=2)
    sat = (mx - mn) / np.maximum(mx, 1)
    warm = (rgb[..., 0] > rgb[..., 1] + 8) & (rgb[..., 1] > rgb[..., 2])
    metal = np.clip((0.30 - sat) / 0.12, 0, 1) * (mx > 22) * np.where(warm & (sat > 0.18), 0, 1)
    lum = rgb.mean(axis=2, keepdims=True) / 128.0
    tgt = np.clip(lum * np.array(col, np.float32) * (1.25 if tier != "eclipse" else 1.0), 0, 255)
    if tier == "eclipse":     # black plate, gold edges on the highlights
        hi = np.clip((lum - 0.9) / 0.5, 0, 1)
        tgt = tgt * (1 - hi) + np.array((222, 182, 92), np.float32) * hi * lum
    w = (metal * amt)[..., None]
    out = img.copy()
    pygame.surfarray.blit_array(out, np.clip(rgb * (1 - w) + tgt * w, 0, 255).astype(np.uint8))
    pa = pygame.surfarray.pixels_alpha(out)
    pa[:] = pygame.surfarray.array_alpha(img)
    del pa
    return out


def _frame(cid, state, h, tier=None):
    key = (cid, state, h, tier)
    if key not in _SPR:
        path = os.path.join(_SPR_DIR, cid, state + ".png")
        if not os.path.isfile(path) and cid.endswith("_f"):
            path = os.path.join(_SPR_DIR, cid[:-2], state + ".png")
        img = pygame.image.load(path).convert_alpha()
        sc = h / 380.0
        img = pygame.transform.smoothscale(img, (max(1, int(img.get_width() * sc)), max(1, int(img.get_height() * sc))))
        if tier:
            img = _tint(img, tier)
        if src_facing(cid, state) != want_facing(cid):
            img = pygame.transform.flip(img, True, False)
            _MIRRORED.add(key)
        _SPR[key] = _lit(img, 1 if cid.startswith("hero") else -1)
    return _SPR[key]


_FACING = None
_MIRRORED = set()


def src_facing(cid, state):
    """Which way the painted PNG faces ("r"/"l"), from duel_sprites/facing.json."""
    global _FACING
    if _FACING is None:
        try:
            import json
            with open(os.path.join(_SPR_DIR, "facing.json")) as fh:
                _FACING = json.load(fh)
        except Exception:
            _FACING = {}
    row = _FACING.get(cid) or (_FACING.get(cid[:-2]) if cid.endswith("_f") else None) or {}
    return row.get(state, "r" if cid.startswith("hero") else "l")


def want_facing(cid):
    """The hero stands on the left and must face right; every champion stands right and faces left."""
    return "r" if cid.startswith("hero") else "l"


def drawn_facing(cid, state):
    """Facing of the frame as it is put on screen (after any mirror) - always toward the opponent."""
    s = src_facing(cid, state)
    if any(k[0] == cid and k[1] == state for k in _MIRRORED):
        return "l" if s == "r" else "r"
    return s


def hero_id(client, style):
    p = client.player or {}
    sex = str((p.get("appearance") or {}).get("sex") or p.get("gender") or p.get("sex") or "male").lower()
    base = "hero_" + (style if style in ("sword", "axe", "bow") else "sword")
    return base + ("_f" if sex.startswith("f") else "")


_SHADOW = {}


def _shadow(surf, x, feet, w, lift):
    """Soft blurred ground shadow (pre-rendered, scaled with height off the ground)."""
    k = max(0.45, 1.0 - lift / 160.0)
    w = max(8, int(w * k))
    key = w // 4
    if key not in _SHADOW:
        ww = key * 4
        hh = max(6, int(ww * 0.22))
        small = pygame.Surface((ww // 4 + 8, hh // 4 + 8), pygame.SRCALPHA)
        for i in range(6):
            a = 30 + i * 18
            r = pygame.Rect(0, 0, int((ww // 4) * (1 - i * 0.12)), int((hh // 4) * (1 - i * 0.12)))
            r.center = small.get_rect().center
            pygame.draw.ellipse(small, (20, 10, 4, a), r)
        big = pygame.transform.smoothscale(small, (ww + 32, hh + 32))
        _SHADOW[key] = big
    img = _SHADOW[key]
    if k < 0.99:
        img = img.copy()
        img.set_alpha(int(255 * k))
    surf.blit(img, img.get_rect(center=(x, feet + 2)))


def _put(surf, img, x, feet, align=None):
    r = img.get_rect(midbottom=(x, feet))
    surf.blit(img, r)
    return r


def _xform(img, rot, sx, sy, flip_rot):
    """Scale + rotate around the feet; returns (surface, offset of the feet point from its topleft)."""
    w, h = img.get_size()
    if abs(sx - 1) > 0.004 or abs(sy - 1) > 0.004:
        img = pygame.transform.smoothscale(img, (max(1, int(w * sx)), max(1, int(h * sy))))
        w, h = img.get_size()
    ang = -rot if not flip_rot else rot
    if abs(ang) < 0.25:
        return img, (w / 2.0, float(h))
    out = pygame.transform.rotozoom(img, ang, 1.0)
    c = pygame.math.Vector2(w / 2.0, h / 2.0)
    pivot = pygame.math.Vector2(w / 2.0, float(h)) - c
    pr = pivot.rotate(-ang)
    oc = pygame.math.Vector2(out.get_width() / 2.0, out.get_height() / 2.0)
    p = oc + pr
    return out, (p.x, p.y)


def _flash(img, col, k):
    k = max(0.0, min(1.0, k))
    f = img.copy()
    f.fill((int(col[0] * k), int(col[1] * k), int(col[2] * k), 0), special_flags=pygame.BLEND_RGBA_ADD)
    return f


def _draw_fighter(surf, F, cid, style, h, x, feet, now, tier=None, scale=1.0):
    pose, dx, dy, rot, sx, sy = F.transform(now, style)
    fwd = 1 if F.side == "hero" else -1
    try:
        img = _frame(cid, pose, int(h * scale), tier)
    except Exception:
        img = _frame(cid, "idle", int(h * scale), tier)
        pose = "idle"
    lift = max(0.0, -dy) + img.get_height() - img.get_bounding_rect().bottom
    px = x + fwd * (dx + F.kx)
    _shadow(surf, px, feet, int(h * 0.58), lift)
    # cross-fade on pose change
    rt = pygame.time.get_ticks()          # cross-fade runs on real time (not frozen by hit-stop)
    if pose != F.pose:
        F.prev = (F.pose, rt)
        F.pose = pose
    out, (fx, fy) = _xform(img, rot, sx, sy, F.side == "boss")
    if F.prev and rt - F.prev[1] < 60:
        try:
            pimg = _frame(cid, F.prev[0], int(h * scale), tier)
            po, (pfx, pfy) = _xform(pimg, rot, sx, sy, F.side == "boss")
            po = po.copy()
            po.set_alpha(int(150 * (1 - (rt - F.prev[1]) / 60.0)))
            surf.blit(po, (px - pfx, feet + dy - pfy))
        except Exception:
            pass
    ft, fcol = F.flash
    if now - ft < 140:
        out = _flash(out, fcol, 0.42 * (1 - (now - ft) / 140.0))
    r = surf.blit(out, (px - fx, feet + dy - fy))
    return r, px


def _draw_tell(surf, v, d, rect, now, small_font):
    """Gold = parry it, red = dodge it.  Ring closes to the strike; NOW lights for the timing window."""
    tel = v.get("tel")
    if not tel or v["boss"].ko is not None:
        return
    step_ms = float(d.get("step_ms") or 200)
    left_ms = float(tel.get("left") or 0) * step_ms - (now - v["tel_t"])
    parry = bool(tel.get("parry")) and d.get("style") != "bow"
    col = (255, 205, 90) if parry else (240, 76, 60)
    window = 520 if parry else 400
    cx, cy = rect.centerx, max(rect.top + 30, 150)
    k = max(0.0, min(1.0, left_ms / 1400.0))
    rad = int(12 + 34 * k)
    now_on = left_ms <= window
    ring = pygame.Surface((110, 110), pygame.SRCALPHA)
    pygame.draw.circle(ring, col + (90,), (55, 55), 14)
    pygame.draw.circle(ring, col + (255,), (55, 55), min(52, rad), 4)
    if now_on:
        pygame.draw.circle(ring, (255, 255, 255, 230), (55, 55), 14, 3)
    surf.blit(ring, (cx - 55, cy - 55))
    # glow outline around the champion
    try:
        mask = pygame.mask.from_surface(v.get("_boss_img"), 60)
        ol = mask.outline(3)
        if len(ol) > 8:
            ox, oy = v.get("_boss_pos", (0, 0))
            pul = 0.55 + 0.45 * math.sin(now / 70.0)
            g = pygame.Surface(rect.size, pygame.SRCALPHA)
            pts = [(p[0] + ox - rect.x, p[1] + oy - rect.y) for p in ol]
            pygame.draw.lines(g, col + (int(150 * pul),), True, pts, 5)
            pygame.draw.lines(g, (255, 250, 230, int(110 * pul)), True, pts, 2)
            surf.blit(g, rect.topleft)
    except Exception:
        pass
    name = str(tel.get("id") or "").replace("_", " ").upper()
    verb = ("PARRY  F" if parry else "DODGE  SPACE")
    f = font(20)
    txt = f"{name} — {'NOW! ' if now_on else ''}{verb}"
    s = f.render(txt, True, (255, 255, 255) if now_on else col)
    sh = f.render(txt, True, (12, 6, 2))
    r = s.get_rect(midtop=(surf.get_width() // 2, 118))
    for o in ((-1, 0), (1, 0), (0, -1), (0, 2), (2, 2)):
        surf.blit(sh, r.move(*o))
    surf.blit(s, r)


def _update_parts(surf, v, dt, pos, feet):
    rng = random
    for spec in [p for p in v["parts"] if "spawn" in p]:
        v["parts"].remove(spec)
        where = spec["spawn"]
        hx, bx, top_h, top_b = pos
        if where == "clash":
            x0, y0 = (hx + bx) / 2, feet - 170
        elif where == "boss":
            x0, y0 = bx - 30, feet - 150
        else:
            x0, y0 = hx + 20, feet - 150
        if spec["kind"] == "dust":
            x0, y0 = (hx if where == "hero" else bx), feet - 4
        for _ in range(spec["n"]):
            if spec["kind"] == "spark":
                a = rng.uniform(0, 2 * math.pi)
                sp = rng.uniform(160, 520)
                v["parts"].append({"k": "spark", "x": x0, "y": y0, "vx": math.cos(a) * sp, "vy": math.sin(a) * sp - 80,
                                   "life": rng.uniform(0.18, 0.42), "age": 0.0, "col": spec["col"]})
            else:
                v["parts"].append({"k": "dust", "x": x0 + rng.uniform(-40, 40), "y": y0 + rng.uniform(-4, 4),
                                   "vx": rng.uniform(-60, 60), "vy": rng.uniform(-50, -10),
                                   "life": rng.uniform(0.5, 0.9), "age": 0.0, "col": spec["col"],
                                   "r": rng.uniform(6, 14)})
    alive = []
    for p in v["parts"]:
        p["age"] += dt
        if p["age"] >= p["life"]:
            continue
        u = p["age"] / p["life"]
        p["x"] += p["vx"] * dt
        p["y"] += p["vy"] * dt
        if p["k"] == "spark":
            p["vy"] += 900 * dt
            l = 0.025
            x2, y2 = p["x"] - p["vx"] * l, p["y"] - p["vy"] * l
            c = tuple(int(cc * (1 - 0.4 * u)) for cc in p["col"])
            pygame.draw.line(surf, c, (int(p["x"]), int(p["y"])), (int(x2), int(y2)), 2)
        else:
            p["vx"] *= 0.96
            r = int(p["r"] * (1 + 1.4 * u))
            s = pygame.Surface((r * 2 + 2, r * 2 + 2), pygame.SRCALPHA)
            pygame.draw.circle(s, p["col"] + (int(110 * (1 - u)),), (r + 1, r + 1), r)
            surf.blit(s, (p["x"] - r, p["y"] - r))
        alive.append(p)
    v["parts"] = alive[-260:]


def _sand_steps(v, F, feet, which):
    if F.moving > 0.25 and random.random() < 0.35 * F.moving:
        v["parts"].append({"k": "dust", "x": F.x + random.uniform(-14, 14), "y": feet - 2, "vx": random.uniform(-40, 40),
                           "vy": random.uniform(-40, -10), "life": 0.5, "age": 0.0, "col": (200, 166, 116),
                           "r": random.uniform(3, 7)})


def _draw_arrows(surf, v, now, hx, bx, feet):
    keep = []
    for a in v["arrows"]:
        u = (now - a["t"]) / float(a["dur"])
        if u > 1.0:
            continue
        keep.append(a)
        if u < 0:
            continue
        x = hx + 60 + (bx - 40 - hx - 60) * u
        y = feet - 190 - math.sin(math.pi * u) * 10
        pygame.draw.line(surf, (70, 50, 30), (x - 44, y), (x, y), 3 if a["heavy"] else 2)
        pygame.draw.polygon(surf, (200, 200, 205), [(x, y - 4), (x + 10, y), (x, y + 4)])
        pygame.draw.line(surf, (230, 220, 200), (x - 44, y - 4), (x - 36, y), 2)
        pygame.draw.line(surf, (230, 220, 200), (x - 44, y + 4), (x - 36, y), 2)
    v["arrows"] = keep


# ---------------------------------------------------------------------------------------------
# Stage
# ---------------------------------------------------------------------------------------------
_BG = {}
_FONTS = {}
_STYLE_GEAR = {
    "sword": {"weapon": "steel_sword", "body": "steel_body", "legs": "steel_legs"},
    "axe": {"weapon": "steel_battleaxe", "body": "steel_body", "legs": "steel_legs"},
    "bow": {"weapon": "maple_longbow", "body": "leather_body", "legs": "leather_chaps"},
}


def font(size, serif=False):
    k = (size, serif)
    if k not in _FONTS:
        here = os.path.dirname(os.path.abspath(__file__))
        path = os.path.join(here, "..", "assets", "fonts", "EBGaramond.ttf" if serif else "Cinzel.ttf")
        try:
            _FONTS[k] = pygame.font.Font(path, size)
        except Exception:
            _FONTS[k] = pygame.font.Font(None, size + 4)
    return _FONTS[k]


def _bg(w, h):
    k = (w, h)
    if k not in _BG:
        try:
            here = os.path.dirname(os.path.abspath(__file__))
            img = pygame.image.load(os.path.join(here, "assets", "castle_realm", "arena", "duel_bg.jpg"))
            iw, ih = img.get_size()
            s = max(w / iw, h / ih)
            img = pygame.transform.smoothscale(img, (int(iw * s) + 1, int(ih * s) + 1))
            out = pygame.Surface((w, h), 0, 24)          # opaque, no alpha channel (see module doc)
            out.blit(img, ((w - img.get_width()) // 2, (h - img.get_height()) // 2))
            vg = pygame.Surface((w, h), pygame.SRCALPHA)
            for i in range(24):
                a = int(7 * (24 - i) / 24 * 2)
                pygame.draw.rect(vg, (0, 0, 0, a), (i * 6, i * 4, w - i * 12, h - i * 8), 6)
            out.blit(vg, (0, 0))
            _BG[k] = out
        except Exception:
            _BG[k] = None
    return _BG[k]


def hero_gear(client, style):
    eq = dict(((client.player or {}).get("equipment") or {}))
    gear = dict(_STYLE_GEAR.get(style, _STYLE_GEAR["sword"]))
    for k in ("body", "legs", "helmet", "shield", "cape"):
        if eq.get(k):
            gear[k] = eq[k]
    w = eq.get("weapon") or ""
    if (style == "bow") == ("bow" in str(w)) and w:
        gear["weapon"] = w
    if style == "bow":
        gear.pop("shield", None)
    return gear


def _states(client, d, m, t, style):
    """Legacy pose picker (kept for tools); v2 draws through Fighter.transform."""
    last = m.get("last_move") or ("", 0)
    age = t - last[1]
    hs, hdx = "idle", 0
    if last[0] in ("light", "heavy", "finish") and age < 420:
        hs, hdx = "attack", int(18 * math.sin(math.pi * min(1.0, age / 420.0)))
    elif last[0] in ("dodge", "back") and age < 420:
        hs, hdx = "dodge", -int(26 * math.sin(math.pi * min(1.0, age / 420.0)))
    elif last[0] == "parry" and age < 450:
        hs = "block"
    bst = d.get("boss_state") or "think"
    bs, bdx = ("hit", 10) if bst == "stagger" else (("attack", -16) if bst == "land" else ("idle", 0))
    return hs, hdx, bs, bdx


def _draw_painted(client, d, m, surf, t, style, feet, hero_x, boss_x, map_h):
    v = _fx(m)
    dt = max(0.0, min(0.05, (t - (v["last"] or t)) / 1000.0))
    v["last"] = t
    if t < v["freeze"]:                    # hit-stop: the pose clock holds
        v["frozen"] = v.get("frozen", 0) + (t - v.get("_t_prev", t))
        dt_anim = 0.0
    else:
        dt_anim = dt
    v["_t_prev"] = t
    now = _anow(v, t)
    hid = hero_id(client, style)
    bid = d.get("boss_id") or "varro"
    h = int(map_h * FIGHTER_H)
    H, B = v["hero"], v["boss"]
    H.update(hero_x, dt_anim)
    B.update(boss_x, dt_anim)
    _sand_steps(v, H, feet, "hero")
    _sand_steps(v, B, feet, "boss")
    # boss behind when he lunges past; draw order: the striker in front
    order = [("boss", B, bid, None, 1.06), ("hero", H, hid, d.get("armour") or "arena", 1.0)]
    if B.busy(now, ("strike", "heavy")):
        order.reverse()
    rects = {}
    for side, F, cid, tier, sc in order:
        r, px = _draw_fighter(surf, F, cid, style, h, F.x, feet, now, tier, sc)
        rects[side] = (r, px)
        if side == "boss":
            try:
                v["_boss_img"] = _frame(cid, F.pose, int(h * sc))
                v["_boss_pos"] = (r.x, r.y)
            except Exception:
                pass
    _draw_arrows(surf, v, now, H.x, B.x, feet)
    _update_parts(surf, v, dt, (H.x, B.x, 0, 0), feet)
    br = rects["boss"][0]
    client._duel_boss_screen = (int(B.x), br.top - 10)
    return rects


def _draw_rig(client, d, m, surf, t, style, feet, hero_x, boss_x):
    # boss
    import arena_battles_ui as ABU
    bstate = d.get("boss_state") or "think"
    tel = d.get("telegraph")
    banim, bp = "melee", 0.1
    if bstate == "land":
        banim, bp = "melee", 0.8
    elif tel:
        banim, bp = "melee", 0.2
    bm = {"boss_id": d.get("boss_id"), "facing": "w", "side": "foe", "stunned": bstate == "stagger"}
    head = None
    try:
        head = ABU.draw_boss(surf, bm, boss_x, feet, 96, t / 1000.0, banim, bp, 0, "w")
    except Exception:
        head = None
    if head is None:
        head = feet - 300
    client._duel_boss_screen = (boss_x, head - 30)
    last = m.get("last_move") or ("", 0)
    age = t - last[1]
    anim, prog = "idle", None
    if last[0] in ("light", "heavy", "finish") and age < 420:
        anim, prog = ("ranged" if style == "bow" else "melee"), min(1.0, age / 420.0)
    elif style == "bow":
        anim, prog = "ranged", 0.2
    try:
        import player_hd_client
        look = player_hd_client.get_default_appearance("male", starter=False)
        app = (client.player or {}).get("appearance") or {}
        look.update({k: v for k, v in app.items() if v})
        look["outfit"] = None
        player_hd_client.draw_player(surf, app.get("sex") or "male", look, hero_x, feet, HERO_TILE, t / 1000.0,
                                     anim=anim, progress=prog, facing=1, equipment=hero_gear(client, style),
                                     starter=False)
    except Exception:
        pass


def _layout(d, map_w, map_h):
    gap = float(d.get("gap") or 2.0)
    feet = int(map_h * STAGE_FEET)
    half = (150 + gap * PX_PER_GAP) / 2.0
    cx = map_w * 0.5
    return feet, int(cx - half), int(cx + half)


def draw_stage(client, map_w=900, map_h=640):
    """Returns True when the stage was drawn (the HUD draws on top)."""
    m = getattr(client, "arena_match", None) or {}
    if _intro_due(m):
        _intro_start(client, m)
    if _intro_active(m):
        return _intro_draw(client, m, map_w, map_h)
    d = duel(client) or _preview_duel(client)
    if not d:
        return False
    bg = _bg(map_w, map_h)
    if bg is None:
        return False
    surf = client.screen
    t = pygame.time.get_ticks()
    style = d.get("style") or "sword"
    if duel(client):
        _poll_held(client, m, d, t)
    stage = bg.copy()
    feet, hero_x, boss_x = _layout(d, map_w, map_h)
    m["stage_bottom"] = feet + 30
    try:
        _draw_painted(client, d, m, stage, t, style, feet, hero_x, boss_x, map_h)
        if duel(client):
            v = _fx(m)
            _draw_tell(stage, v, d, pygame.Rect(int(v["boss"].x) - 160, feet - int(map_h * FIGHTER_H * 1.06), 320,
                                                int(map_h * FIGHTER_H * 1.06)), t, None)
            _draw_charge(stage, v, d, t, int(v["hero"].x), feet - int(map_h * FIGHTER_H) - 26)
    except Exception:
        if not m.get("_v2_err"):
            import traceback
            m["_v2_err"] = True
            traceback.print_exc()
        stage = bg.copy()
        _draw_rig(client, d, m, stage, t, style, feet, hero_x, boss_x)
    v = _fx(m)
    amp = v["shake"] * max(0.0, 1 - (t - v["shake_t"]) / 260.0)
    ox = int(random.uniform(-amp, amp)) if amp > 0.5 else 0
    oy = int(random.uniform(-amp, amp) * 0.6) if amp > 0.5 else 0
    if ox or oy:
        surf.fill((0, 0, 0), (0, 0, map_w, map_h))
    surf.blit(stage, (ox, oy))
    # the window surface is ARGB on the Mac: keep the stage fully opaque
    surf.fill((0, 0, 0, 255), (0, 0, map_w, map_h), special_flags=pygame.BLEND_RGBA_MAX)
    return True


def _draw_charge(surf, v, d, now, x, y):
    t0 = v["press"].get("atk")
    if t0 is None:
        return
    k = min(1.0, (now - t0) / float(HOLD_MS))
    full = k >= 1.0
    col = (255, 214, 110) if full else (230, 230, 220)
    r = 16
    pygame.draw.circle(surf, (20, 12, 6), (x, y), r + 3)
    pygame.draw.arc(surf, col, (x - r, y - r, 2 * r, 2 * r), math.pi / 2, math.pi / 2 + 2 * math.pi * k, 4)
    lab = ("CHARGED" if d.get("style") == "bow" else "HEAVY") if full else ("DRAW" if d.get("style") == "bow" else "HOLD")
    s = font(13).render(lab, True, col)
    surf.blit(s, s.get_rect(midbottom=(x, y - r - 4)))


# ---------------------------------------------------------------------------------------------
# HUD (painted: carved wood, gold leaf, glossy bars, keycaps — hud_skin)
# ---------------------------------------------------------------------------------------------
def _gloss_bar(surf, rect, frac, top, bot, glow_on=False, t=0):
    import hud_skin as K
    pygame.draw.rect(surf, (8, 5, 3), rect, border_radius=rect.h // 2)
    inner = rect.inflate(-4, -4)
    w = int(inner.w * max(0.0, min(1.0, frac)))
    if w > 2:
        fr = pygame.Rect(inner.x, inner.y, w, inner.h)
        g = pygame.Surface(fr.size, pygame.SRCALPHA)
        for yy in range(fr.h):
            u = yy / max(1, fr.h - 1)
            c = tuple(int(top[i] * (1 - u) + bot[i] * u) for i in range(3))
            pygame.draw.line(g, c + (255,), (0, yy), (fr.w, yy))
        pygame.draw.line(g, (255, 255, 255, 90), (2, 1), (fr.w - 3, 1))
        mk = pygame.Surface(fr.size, pygame.SRCALPHA)
        pygame.draw.rect(mk, (255, 255, 255, 255), mk.get_rect(), border_radius=fr.h // 2)
        g.blit(mk, (0, 0), special_flags=pygame.BLEND_RGBA_MIN)
        if glow_on:
            K.glow(surf, fr, top, 6, int(90 + 70 * math.sin(t / 120.0)), fr.h // 2)
        surf.blit(g, fr.topleft)
    K.gold_rim(surf, rect, rect.h // 2, 2)


def _caption(surf, text, pos, col=(242, 226, 190), size=15, anchor="bottomleft"):
    f = font(size)
    s = f.render(text, True, col)
    sh = f.render(text, True, (8, 5, 3))
    r = s.get_rect(**{anchor: pos})
    for o in ((-1, 0), (1, 0), (0, -1), (0, 1), (1, 2)):
        surf.blit(sh, r.move(*o))
    surf.blit(s, r)
    return r


def _btn(surf, r, key, label, sub, lit, hover, small):
    import hud_skin as K
    K.button(surf, r, "active" if lit else "idle", inset=lit, hover=hover, r=7)
    kr = K.keycap(surf, (r.x + 8 + max(8, small.size(key)[0] // 2 + 4), r.y + 12), key)
    _caption(surf, label, (kr.right + 6, r.y + 4), (255, 240, 205) if lit else (238, 220, 180), 14, "topleft")
    if sub:
        s = small.render(sub, True, (190, 170, 130))
        surf.blit(s, s.get_rect(midbottom=(r.centerx, r.bottom - 3)))


def draw(client, map_w=900, map_h=640):
    m = getattr(client, "arena_match", None) or {}
    if _intro_active(m):
        return
    pd = _preview_duel(client)
    if pd is not None:
        try:
            _draw_picker(client, m, pd, map_w, map_h)
        except Exception:
            pass
        return
    d = duel(client)
    if not d:
        return
    try:
        _draw_hud_v2(client, m, d, map_w, map_h)
    except Exception:
        _draw_hud_plain(client, m, d, map_w, map_h)


def _draw_hud_v2(client, m, d, map_w, map_h):
    import hud_skin as K
    surf = client.screen
    t = pygame.time.get_ticks()
    bow = d.get("style") == "bow"
    small = font(11, serif=True) if True else client.font_small
    mouse = pygame.mouse.get_pos()
    # --- bottom card: name, gear, stamina, crowd ---
    W = 560
    card = pygame.Rect(map_w // 2 - W // 2, map_h - 148, W, 62)
    K.card(surf, card, r=9)
    name = str((client.player or {}).get("char_name") or (client.player or {}).get("name") or "You")
    gear = f"{TIER_NAME.get(d.get('armour') or 'arena', 'Arena steel')} plate · {(d.get('style') or 'sword').title()}"
    nr = _caption(surf, name.upper(), (card.x + 14, card.y + 5), (255, 236, 196), 16, "topleft")
    _caption(surf, gear, (nr.right + 10, card.y + 8), (236, 214, 160), 13, "topleft")
    sta_max = float(d.get("sta_max") or 100.0)
    sr = pygame.Rect(card.x + 14, card.y + 36, W // 2 - 26, 14)
    _gloss_bar(surf, sr, float(d.get("sta") or 0) / sta_max, (150, 226, 120), (36, 96, 30))
    _caption(surf, "STAMINA", (sr.x + 4, sr.y - 1), (214, 236, 200), 11)
    mr = pygame.Rect(card.centerx + 8, card.y + 36, W // 2 - 22, 14)
    mom = float(d.get("momentum") or 0) / 100.0
    _gloss_bar(surf, mr, mom, (255, 214, 110), (140, 80, 20), glow_on=bool(d.get("finisher_ready")) or mom >= 1, t=t)
    _caption(surf, "CROWD", (mr.x + 4, mr.y - 1), (250, 222, 160), 11)
    foe = str(m.get("foe_name") or (m.get("hud") or {}).get("foe_name") or "")
    if foe:
        _caption(surf, f"vs {foe} · {TIER_NAME.get(d.get('boss_tier') or 'steel', '')}", (card.right - 14, card.y + 8),
                 (246, 186, 140), 13, "topright")
    # --- action buttons ---
    specs = [("attack", "Q", "Shot" if bow else "Attack", "tap · hold = " + ("charged" if bow else "heavy"), 150),
             ("dodge", "Spc", "Dodge", "red tells", 104),
             ("move", "A D", "Move", "hold to walk", 120)]
    if not bow:
        specs.insert(1, ("parry", "F", "Parry", "gold tells · R-click", 128))
    gap = 8
    total = sum(s[4] for s in specs) + gap * (len(specs) - 1)
    x = map_w // 2 - total // 2
    y = map_h - 80
    btns = {}
    last = m.get("last_move") or ("", 0)
    v = _fx(m)
    for mv, key, lab, sub, w in specs:
        r = pygame.Rect(x, y, w, 40)
        lit = (last[0] == mv or (mv == "attack" and last[0] in ("light", "heavy"))
               or (mv == "move" and last[0] in ("back", "forward"))) and t - last[1] < 200
        if mv == "attack" and "atk" in v["press"]:
            lit = True
        _btn(surf, r, key, lab, sub, lit, r.collidepoint(mouse), small)
        btns[mv] = r
        x += w + gap
    m["duel_btns"] = btns
    # finisher
    if d.get("finisher_ready"):
        pulse = 0.5 + 0.5 * math.sin(t / 120.0)
        fr = pygame.Rect(0, 0, 300, 44)
        fr.midtop = (map_w // 2, 58)
        K.glow(surf, fr, (255, 180, 80), 10, int(100 + 100 * pulse), 9)
        K.button(surf, fr, "danger", r=9)
        K.keycap(surf, (fr.x + 22, fr.centery), "R")
        _caption(surf, "FINISHING " + ("SHOT" if bow else "MOVE"), (fr.centerx + 10, fr.centery + 1), (255, 240, 210), 18, "center")
        btns["finish"] = fr
    # first-duel hint (30 s)
    began = v.get("began") or t
    v["began"] = began
    if t - began < 30000:
        a = 255 if t - began < 27000 else int(255 * (30000 - (t - began)) / 3000.0)
        hint = ("Tap Q to shoot, hold to draw a charged shot · Space dodges red tells · A/D keep your range" if bow else
                "Tap Q to strike, hold Q for a heavy · F parries GOLD tells · Space dodges RED tells · hold A/D to move")
        s = font(12, serif=True).render(hint, True, (246, 232, 200))
        bgp = pygame.Surface((s.get_width() + 24, s.get_height() + 8), pygame.SRCALPHA)
        pygame.draw.rect(bgp, (14, 9, 5, 170), bgp.get_rect(), border_radius=8)
        bgp.blit(s, (12, 4))
        bgp.set_alpha(a)
        surf.blit(bgp, bgp.get_rect(midbottom=(map_w // 2, card.y - 8)))
    # callouts
    for i, f in enumerate(list(m.get("duel_fx") or [])):
        age = t - f["t"]
        if age > 900:
            continue
        a = 1 - age / 900.0
        sc = 1.0 + 0.25 * max(0.0, 1 - age / 140.0)
        s = font(int(26 * sc)).render(f["text"], True, f["col"])
        sh = font(int(26 * sc)).render(f["text"], True, (10, 6, 3))
        s.set_alpha(int(255 * a)); sh.set_alpha(int(200 * a))
        r = s.get_rect(center=(map_w // 2, map_h // 2 - 120 - int(age / 20) - i * 6))
        surf.blit(sh, r.move(2, 2))
        surf.blit(s, r)
    for flag, text in (("rooted", "NETTED — can't move"), ("stunned", "STUNNED")):
        if d.get(flag):
            _caption(surf, text, (map_w // 2, card.y - 34), (255, 150, 120), 18, "midbottom")
    surf.fill((0, 0, 0, 255), (0, 0, map_w, map_h), special_flags=pygame.BLEND_RGBA_MAX)


def _draw_hud_plain(client, m, d, map_w, map_h):
    """Error fallback: flat bars and buttons (no hud_skin)."""
    surf = client.screen
    small = client.font_small
    labels = [("attack", "Q", "Attack"), ("parry", "F", "Parry"), ("dodge", "Spc", "Dodge"), ("move", "A D", "Move")]
    bw, bh, gap = 90, 36, 6
    total = len(labels) * bw + (len(labels) - 1) * gap
    x0, y0 = map_w // 2 - total // 2, map_h - 80
    btns = {}
    for i, (mv, key, lab) in enumerate(labels):
        r = pygame.Rect(x0 + i * (bw + gap), y0, bw, bh)
        pygame.draw.rect(surf, (24, 18, 12), r, border_radius=6)
        pygame.draw.rect(surf, (120, 96, 56), r, 1, border_radius=6)
        surf.blit(small.render(f"{key} {lab}", True, (240, 226, 196)), (r.x + 6, r.y + 10))
        btns[mv] = r
    m["duel_btns"] = btns


# ---------------------------------------------------------------------------------------------
# Weapon picker (preview phase)
# ---------------------------------------------------------------------------------------------
def _draw_picker(client, m, pd, map_w, map_h):
    import hud_skin as K
    surf = client.screen
    t = pygame.time.get_ticks()
    mouse = pygame.mouse.get_pos()
    panel = pygame.Rect(0, 0, 640, 300)
    panel.midtop = (map_w // 2, 70)
    K.card(surf, panel, r=12, ornate=True)
    _caption(surf, "CHOOSE YOUR WEAPON", (panel.centerx, panel.y + 12), (240, 210, 140), 22, "midtop")
    tier = pd.get("armour") or "arena"
    _caption(surf, f"{TIER_NAME.get(tier, tier)} plate · keys 1 2 3 or click", (panel.centerx, panel.y + 42),
             (200, 182, 140), 12, "midtop")
    rects = {}
    cw, chh = 190, 216
    x = panel.centerx - (3 * cw + 2 * 14) // 2
    cur = pd.get("style") or "sword"
    for i, (st, title, l1, l2) in enumerate(WEAPONS):
        r = pygame.Rect(x + i * (cw + 14), panel.y + 66, cw, chh)
        sel = st == cur
        hov = r.collidepoint(mouse)
        if sel:
            K.glow(surf, r, (255, 200, 90), 10, int(110 + 60 * math.sin(t / 200.0)), 10)
        K.card(surf, r, r=10, base=(46, 34, 22) if sel else K.WOOD, highlight=sel or hov)
        try:
            img = _frame(hero_id(client, st), "idle", 132, tier)
            surf.blit(img, img.get_rect(midbottom=(r.centerx, r.y + 146)))
        except Exception:
            pass
        K.keycap(surf, (r.x + 16, r.y + 14), str(i + 1))
        _caption(surf, title.upper(), (r.centerx, r.y + 150), (255, 236, 190) if sel else (226, 204, 160), 17, "midtop")
        for j, line in enumerate((l1, l2)):
            s = font(12, serif=True).render(line, True, (214, 196, 160))
            surf.blit(s, s.get_rect(midtop=(r.centerx, r.y + 174 + j * 16)))
        rects[st] = r
    m["pick_rects"] = rects
    surf.fill((0, 0, 0, 255), (0, 0, map_w, map_h), special_flags=pygame.BLEND_RGBA_MAX)


# ---------------------------------------------------------------------------------------------
# Pre-duel film (same playback as throne_vision: pre-extracted JPEG frames, the audio is the clock)
# ---------------------------------------------------------------------------------------------
INTRO_DIR = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "assets", "arena_intro"))
_INTRO = {}
_INTRO_META = {}


def _intro_meta():
    if not _INTRO_META:
        try:
            import json
            with open(os.path.join(INTRO_DIR, "meta.json")) as f:
                _INTRO_META.update(json.load(f))
        except (OSError, ValueError):
            _INTRO_META["frames"] = 0
    return _INTRO_META


def intro_available():
    mt = _intro_meta()
    return bool(mt.get("frames")) and os.path.isfile(os.path.join(INTRO_DIR, mt.get("frame_pattern", "frames/%04d.jpg") % 1))


def _intro_due(m):
    return (m.get("active") and (m.get("phase") == "fight") and not m.get("intro_done")
            and bool((m.get("hud") or {}).get("duel") or m.get("duel")) and not m.get("duel"))


def _intro_active(m):
    return bool(_INTRO.get("on")) and _INTRO.get("match") is m


def _intro_start(client, m):
    m["intro_done"] = True              # once per duel start, whatever happens next
    if not intro_available():
        _release(client)
        return
    _INTRO.clear()
    _INTRO.update(on=True, match=m, start=pygame.time.get_ticks(), frame=0, surf=None, scaled=None, channel=None)
    try:
        if pygame.mixer.get_init():
            snd = pygame.mixer.Sound(os.path.join(INTRO_DIR, _intro_meta().get("audio", "audio.ogg")))
            _INTRO["channel"] = snd.play()
            _INTRO["sound"] = snd
    except Exception:
        _INTRO["channel"] = None


def _release(client):
    try:
        client.net.send("BARRACKS", action="duel_ready")
    except Exception:
        pass


def _intro_end(client, m):
    ch = _INTRO.get("channel")
    try:
        if ch is not None:
            ch.fadeout(250)
    except Exception:
        pass
    _INTRO.clear()
    _release(client)


def _intro_draw(client, m, map_w, map_h):
    mt = _intro_meta()
    n = int(mt.get("frames") or 0)
    ms = pygame.time.get_ticks() - _INTRO["start"]
    i = max(1, min(n, int(ms * float(mt.get("fps", 24)) / 1000.0) + 1))
    if ms * float(mt.get("fps", 24)) / 1000.0 >= n + 6:
        _intro_end(client, m)
        return draw_stage(client, map_w, map_h)
    surf = client.screen
    if i != _INTRO.get("frame"):
        try:
            img = pygame.image.load(os.path.join(INTRO_DIR, mt.get("frame_pattern", "frames/%04d.jpg") % i))
            sw, sh = surf.get_size()
            s = min(sw / img.get_width(), sh / img.get_height())
            _INTRO["scaled"] = pygame.transform.smoothscale(img, (int(img.get_width() * s), int(img.get_height() * s)))
            _INTRO["frame"] = i
        except Exception:
            pass
    surf.fill((0, 0, 0))
    sc = _INTRO.get("scaled")
    if sc is not None:
        surf.blit(sc, sc.get_rect(center=surf.get_rect().center))
    # fade in / out
    fade = min(1.0, ms / 350.0, max(0.0, (n / float(mt.get("fps", 24)) * 1000 - ms) / 450.0))
    if fade < 1:
        ov = pygame.Surface(surf.get_size(), pygame.SRCALPHA)
        ov.fill((0, 0, 0, int(255 * (1 - fade))))
        surf.blit(ov, (0, 0))
    foe = str(m.get("foe_name") or (m.get("hud") or {}).get("foe_name") or "")
    if foe and ms > 4800:
        a = min(1.0, (ms - 4800) / 500.0)
        f = font(30)
        txt = f"{str((client.player or {}).get('char_name') or 'YOU').upper()}  vs  {foe.upper()}"
        s = f.render(txt, True, (250, 226, 170)); s.set_alpha(int(255 * a))
        shd = f.render(txt, True, (0, 0, 0)); shd.set_alpha(int(200 * a))
        r = s.get_rect(midbottom=(surf.get_width() // 2, surf.get_height() - 70))
        surf.blit(shd, r.move(2, 2)); surf.blit(s, r)
    hint = font(13).render("SPACE · ESC · CLICK  to skip", True, (230, 214, 180))
    surf.blit(hint, hint.get_rect(bottomright=(surf.get_width() - 18, surf.get_height() - 14)))
    surf.fill((0, 0, 0, 255), None, special_flags=pygame.BLEND_RGBA_MAX)
    return True
