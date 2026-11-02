"""The Moon Petal Inn (MOON_PETAL_INN_SPEC.md v1): entry film, first-person room, 9 talkable fairies.

Door = content.py interactable "moonpetal_inn_door" (21,82) in Moonpetal Glade.
Film + room POV are client-local; quests, friendship, compliments and the house
secret go through MOONPETAL_* server messages (fairy_friendship.py).
"""
from __future__ import annotations

import json
import math
import os
import random
import time

import pygame

import hud_skin as S

DIR = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", "assets", "moon_petal_inn"))
DOOR_ID = "moonpetal_inn_door"
SKIP_AFTER_S = 0.5
FADE_S = 0.3
STILL_S = 2.0
TYPE_CPS = 48.0
PREFS = os.path.join(os.path.expanduser("~"), ".crownfall", "moon_petal.json")
LOFT = ("Aerin", "Rhosyn")

# Display titles only — long dialogue lives on the server now.
FAIRIES = {
    "Selune": ("Hostess of the Moon Petal",),
    "Ivria": ("The Archivist",),
    "Maelis": ("The Moonbloom Keeper",),
    "Aerin": ("The Watcher on the Balcony",),
    "Rhosyn": ("The Harpist",),
    "Tamsin": ("The Moon Bar",),
    "Nyx": ("The Hearthwitch",),
    "Kaede": ("The Letter-Writer",),
    "Bryony": ("The Crystal Reader",),
}
FRIEND_MAX = 100
FRIEND_ID = {
    "Selune": "selune", "Ivria": "ivria", "Maelis": "maelis", "Aerin": "aerin",
    "Rhosyn": "rhosyn", "Tamsin": "tamsin_moon", "Kaede": "kaede",
    "Bryony": "bryony", "Nyx": "nyx",
}


def _load_json(path, default):
    try:
        with open(path) as f:
            return json.load(f)
    except (OSError, ValueError):
        return default


_META = None


def meta():
    global _META
    if _META is None:
        _META = _load_json(os.path.join(DIR, "meta.json"), {})
    return _META


def hotspots():
    return _load_json(os.path.join(DIR, "hotspots.json"), [])


def frame_path(i):
    return os.path.join(DIR, meta().get("frame_pattern", "frames/%04d.jpg") % i)


def film_available():
    return bool(meta()) and os.path.isfile(frame_path(1))


def reduced_motion(client):
    return bool(getattr(client, "reduced_motion", False)) or os.environ.get("CROWNFALL_REDUCED_MOTION") == "1"


def tab_order(spots):
    """Left to right on the floor, then the loft (spec 2)."""
    floor = sorted((s for s in spots if s["name"] not in LOFT), key=lambda s: s["x"])
    loft = sorted((s for s in spots if s["name"] in LOFT), key=lambda s: s["x"])
    return floor + loft


def wrap(font, text, width):
    """Word-wrap; blank lines from \\n become empty rows for paragraph breaks."""
    rows = []
    for para in str(text or "").split("\n"):
        if not para.strip():
            rows.append("")
            continue
        row = ""
        for w in para.split():
            t = (row + " " + w).strip()
            if font.size(t)[0] > width and row:
                rows.append(row)
                row = w
            else:
                row = t
        if row:
            rows.append(row)
    return rows


class EntryFilm:
    """Same playback model as tavern_intro.TavernIntro (audio is the clock, frames dropped not drifted)."""

    def __init__(self, client, on_done, skip_after=SKIP_AFTER_S):
        self.client, self.on_done, self.skip_after = client, on_done, skip_after
        self.still = reduced_motion(client) or not film_available()
        self.start = time.time()
        self.ending = None
        self.frame = 0
        self.scaled = None
        self.channel = None
        self.skip_rect = None
        if not self.still:
            try:
                if pygame.mixer.get_init():
                    self.channel = pygame.mixer.Sound(os.path.join(DIR, meta().get("audio", "audio.ogg"))).play()
            except Exception:
                self.channel = None

    def elapsed(self):
        return time.time() - self.start

    def duration(self):
        return STILL_S if self.still else float(meta().get("duration", 14.1))

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
        if event.type in (pygame.KEYDOWN, pygame.MOUSEBUTTONDOWN) and self.elapsed() >= self.skip_after:
            self.skip()
        return event.type in (pygame.KEYDOWN, pygame.MOUSEBUTTONDOWN)

    def done(self):
        return self.ending is not None and time.time() - self.ending >= FADE_S

    def render(self, surf, still_img=None):
        if self.ending is None and self.elapsed() >= self.duration():
            self.skip()
        if self.done():
            if callable(self.on_done):
                cb, self.on_done = self.on_done, None
                cb()
            return False
        sw, sh = surf.get_size()
        surf.fill((0, 0, 0))
        img = still_img
        if not self.still:
            i = self.frame_for(min(self.elapsed(), self.duration()))
            if i != self.frame:
                try:
                    raw = pygame.image.load(frame_path(i))
                    k = min(sw / raw.get_width(), sh / raw.get_height())
                    self.scaled = pygame.transform.smoothscale(raw, (int(raw.get_width() * k), int(raw.get_height() * k)))
                    self.frame = i
                except Exception:
                    pass
            img = self.scaled
        if img is not None:
            surf.blit(img, ((sw - img.get_width()) // 2, (sh - img.get_height()) // 2))
        m, e = meta(), self.elapsed()
        if m.get("subtitle") and (self.still or m.get("subtitle_start", 99) <= e <= m.get("subtitle_end", 0)):
            f = S.font("body", 24)
            rows = wrap(f, m["subtitle"], int(sw * 0.7))
            y = sh - 70 - len(rows) * 30
            for r in rows:
                S.text(surf, r, f, (245, 238, 220), (sw // 2, y), anchor="midtop")
                y += 30
        if e >= self.skip_after and self.ending is None:
            small = S.font("title", 16)
            label = small.render("Skip", True, (240, 228, 200))
            r = pygame.Rect(0, 0, label.get_width() + 46, label.get_height() + 14)
            r.bottomright = (sw - 18, sh - 14)
            pygame.draw.rect(surf, (20, 18, 24), r, border_radius=14)
            pygame.draw.rect(surf, S.GOLD, r, 1, border_radius=14)
            surf.blit(label, (r.x + 14, r.y + 7))
            _play_tri(surf, r.right - 20, r.centery)
            self.skip_rect = r
        if self.ending is not None:
            veil = pygame.Surface((sw, sh))
            veil.set_alpha(int(255 * min(1.0, (time.time() - self.ending) / FADE_S)))
            surf.blit(veil, (0, 0))
        return True


def _play_tri(surf, cx, cy, s=5, col=S.GOLD_HI):
    pygame.draw.polygon(surf, col, [(cx - s + 1, cy - s), (cx + s, cy), (cx - s + 1, cy + s)])


def _check(surf, cx, cy, col):
    pygame.draw.lines(surf, col, False, [(cx - 5, cy), (cx - 2, cy + 3), (cx + 5, cy - 4)], 2)


class MoonPetalInn:
    def __init__(self, client):
        self.client = client
        self.active = False
        self.mode = None            # "film" | "room" | "talk"
        self.film = None
        self.spots = tab_order(hotspots())
        self.hover = None           # index into self.spots
        self.focus = None           # keyboard focus index
        self.talk = None            # fairy name
        self.page = "greeting"      # server page hint: greeting | quest | compliments | social | secret
        self.quest_line = None
        self.quest_choices = []
        self.quest_payload = None
        self.friendship = {}        # fairy_id -> 0..100
        self.friend_max = FRIEND_MAX
        self.friend_detail = None   # public_state for current fairy
        self.secret_unlocked = False
        self.last_gained = 0
        self.menu_kind = "greeting"  # greeting | compliments | social | secret | quest
        self.waiting_line = False
        self.type_start = 0.0
        self.room_start = 0.0
        self.burst = None           # (x, y, t0)
        self.leave_rect = None
        self.reply_rects = []
        self._img = {}
        self._session_seen = False
        self.reply_focus = None
        self.hover_reply = None
        rng = random.Random(9)
        self.motes = [(rng.random(), rng.random(), rng.uniform(0.01, 0.04), rng.uniform(1.0, 2.6), rng.random() * 6.28)
                      for _ in range(46)]

    # ---- prefs -------------------------------------------------------------------------
    def _who(self):
        p = getattr(self.client, "player", None) or {}
        return str(p.get("name") or p.get("id") or "anon")

    def prefs(self):
        return _load_json(PREFS, {"replay": "session", "seen": []})

    def _save(self, prefs):
        try:
            os.makedirs(os.path.dirname(PREFS), exist_ok=True)
            with open(PREFS, "w") as f:
                json.dump(prefs, f)
        except OSError:
            pass

    def first_view(self):
        return self._who() not in self.prefs().get("seen", [])

    def should_play(self):
        return True     # David: the fairy inn film plays every time you walk to the door (skippable at once)
        if self.first_view():
            return True
        mode = self.prefs().get("replay", "session")
        return mode == "always" or (mode == "session" and not self._session_seen)

    # ---- enter / leave -----------------------------------------------------------------
    def is_door(self, x, y):
        if getattr(self.client, "dungeon", None):
            return False
        for spot in getattr(self.client, "interactables", None) or []:
            if spot.get("id") == DOOR_ID and (int(spot["x"]), int(spot["y"])) == (int(x), int(y)):
                return True
        return False

    def enter(self):
        if self.active:
            return
        self.active = True
        self.talk = None
        self.hover = self.focus = None
        self.quest_line = None
        self.quest_choices = []
        self.quest_payload = None
        self.friend_detail = None
        self.last_gained = 0
        self.waiting_line = False
        try:
            self.client.net.send("MOONPETAL_ENTER", id=DOOR_ID)
        except Exception:
            pass
        if self.should_play():
            first = self.first_view()
            self.mode = "film"
            self.film = EntryFilm(self.client, self._film_done, 0.0)   # Space / Esc / click skips at once
            prefs = self.prefs()
            if first:
                prefs.setdefault("seen", []).append(self._who())
                self._save(prefs)
            self._session_seen = True
        else:
            self._film_done()

    def _film_done(self):
        self.film = None
        self.mode = "room"
        self.room_start = time.time()

    def leave(self):
        set_cursor(None)
        self.active = False
        self.mode = self.talk = self.film = None
        self.quest_line = None
        self.quest_choices = []
        self.quest_payload = None
        self.friend_detail = None
        self.waiting_line = False
        try:
            self.client.net.send("MOONPETAL_LEAVE")
        except Exception:
            pass
        c = self.client
        try:  # outside the door, facing away from it
            c._entity_facing[("p", c.player.get("id"))] = "front"
        except Exception:
            pass

    def open_talk(self, name):
        self.talk = name
        self.page = "greeting"
        self.menu_kind = "greeting"
        self.reply_focus = None
        self.mode = "talk"
        self.type_start = time.time()
        self.quest_line = "…"
        self.quest_choices = []
        self.quest_payload = None
        self.waiting_line = True
        try:
            self.client.net.send("MOONPETAL_TALK", fairy=name)
        except Exception:
            self.waiting_line = False

    def _apply_friendship(self, payload):
        if not isinstance(payload, dict):
            return
        bag = payload.get("friendship")
        if isinstance(bag, dict):
            for k, v in bag.items():
                try:
                    self.friendship[k] = int(v)
                except (TypeError, ValueError):
                    pass
        if payload.get("value") is not None and payload.get("fairy_id"):
            try:
                self.friendship[payload["fairy_id"]] = int(payload["value"])
            except (TypeError, ValueError):
                pass
        self.friend_max = int(payload.get("max") or FRIEND_MAX)
        self.secret_unlocked = bool(payload.get("secret_unlocked"))
        self.friend_detail = payload

    def on_message(self, t, msg):
        if t == "MOONPETAL_LINE":
            if msg.get("fairy"):
                self.talk = msg["fairy"]
            self.quest_line = msg.get("line") or ""
            self.quest_choices = list(msg.get("choices") or [])
            self.quest_payload = msg.get("quest")
            self._apply_friendship(msg.get("friendship") or {})
            self.last_gained = int(msg.get("gained") or 0)
            self.menu_kind = str(msg.get("page") or "greeting")
            self.page = self.menu_kind
            self.mode = "talk"
            self.waiting_line = False
            self.type_start = time.time()
            self.reply_focus = None
            if msg.get("close") and not self.quest_choices:
                self.mode, self.talk = "room", None
            return True
        if t == "MOONPETAL_STATE":
            if msg.get("inside"):
                self._apply_friendship(msg.get("friendship") or {})
            return True
        return False

    def friend_of(self, name):
        fid = FRIEND_ID.get(name) or ""
        return int(self.friendship.get(fid) or 0)

    # ---- geometry ----------------------------------------------------------------------
    def _cover(self, sw, sh):
        k = max(sw / 1280.0, sh / 720.0)
        ox, oy = (sw - 1280 * k) / 2, (sh - 720 * k) / 2
        return k, ox, oy

    def hit_rect(self, spot, sw, sh):
        """Ellipse bounds: radius x1.0 wide, x1.8 tall, centred slightly above the point; min 44 px target."""
        k, ox, oy = self._cover(sw, sh)
        r = spot["hit_radius"] * k
        cx, cy = ox + spot["x"] * k, oy + (spot["y"] - spot["hit_radius"] * 0.45) * k
        w, h = max(44, 2 * r), max(44, 2 * r * 1.8)
        return pygame.Rect(int(cx - w / 2), int(cy - h / 2), int(w), int(h))

    def spot_at(self, pos, sw, sh):
        best = None
        for i, s in enumerate(self.spots):
            r = self.hit_rect(s, sw, sh)
            dx, dy = (pos[0] - r.centerx) / (r.w / 2.0), (pos[1] - r.centery) / (r.h / 2.0)
            d = dx * dx + dy * dy
            if d <= 1.0 and (best is None or d < best[0]):
                best = (d, i)
        return None if best is None else best[1]

    # ---- dialogue model ----------------------------------------------------------------
    def body(self):
        if self.waiting_line and not self.quest_line:
            return "…"
        return self.quest_line or "…"

    def replies(self):
        """[(label, action, state)] state: new | seen | None."""
        if self.waiting_line and not self.quest_choices:
            return []
        out = []
        for i, lab in enumerate(self.quest_choices or []):
            state = "seen" if str(lab).endswith(" ✓") else ("new" if "Compliment" in str(lab) or "Ask about" in str(lab) else None)
            if str(lab).endswith(" ✓"):
                state = "seen"
            out.append((lab, ("server_choice", i), state))
        return out

    def typed_all(self):
        return (time.time() - self.type_start) * TYPE_CPS >= len(self.body())

    def choose(self, idx):
        rs = self.replies()
        if not (0 <= idx < len(rs)):
            return
        act = rs[idx][1]
        if not (isinstance(act, tuple) and act and act[0] == "server_choice"):
            return
        choice = int(act[1])
        self.waiting_line = True
        menu = self.menu_kind or "greeting"
        if menu in ("quest", "quest_offer"):
            menu = ""
        try:
            self.client.net.send(
                "MOONPETAL_CHOICE", fairy=self.talk, choice=choice, menu=menu,
            )
        except Exception:
            self.waiting_line = False
        self.reply_focus = None

    # ---- events ------------------------------------------------------------------------
    def handle_event(self, event):
        sw, sh = self.client.screen.get_size()
        if self.mode == "film" and self.film is not None:
            self.film.handle_event(event)
            return True
        if self.mode == "room":
            if event.type == pygame.MOUSEMOTION:
                self.hover = self.spot_at(event.pos, sw, sh)
            elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                if self.leave_rect and self.leave_rect.collidepoint(event.pos):
                    self.leave()
                    return True
                i = self.spot_at(event.pos, sw, sh)
                if i is not None:
                    self.burst = (event.pos[0], event.pos[1], time.time())
                    self.open_talk(self.spots[i]["name"])
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    self.leave()
                elif event.key == pygame.K_TAB:
                    n = len(self.spots)
                    step = -1 if event.mod & pygame.KMOD_SHIFT else 1
                    self.focus = (0 if step > 0 else n - 1) if self.focus is None else (self.focus + step) % n
                elif event.key in (pygame.K_RETURN, pygame.K_KP_ENTER) and self.focus is not None:
                    self.open_talk(self.spots[self.focus]["name"])
            return True
        if self.mode == "talk":
            if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                for i, r in enumerate(self.reply_rects):
                    if r.collidepoint(event.pos):
                        self.choose(i)
                        return True
                if not self.typed_all():
                    self.type_start = 0.0
            elif event.type == pygame.MOUSEMOTION:
                self.hover_reply = next((i for i, r in enumerate(self.reply_rects) if r.collidepoint(event.pos)), None)
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    self.mode, self.talk = "room", None
                    self.waiting_line = False
                elif pygame.K_1 <= event.key <= pygame.K_9:
                    self.choose(event.key - pygame.K_1)
                elif event.key in (pygame.K_RETURN, pygame.K_KP_ENTER, pygame.K_SPACE):
                    if not self.typed_all():
                        self.type_start = 0.0
                    else:
                        self.choose(self.reply_focus or 0)
                elif event.key == pygame.K_TAB:
                    n = len(self.replies())
                    if n:
                        self.reply_focus = 0 if self.reply_focus is None else (self.reply_focus + 1) % n
            return True
        return True

    # ---- drawing -----------------------------------------------------------------------
    def _image(self, rel, size=None):
        key = (rel, size)
        if key not in self._img:
            try:
                im = pygame.image.load(os.path.join(DIR, rel)).convert()
                if size:
                    im = pygame.transform.smoothscale(im, size)
            except Exception:
                im = None
            self._img[key] = im
        return self._img[key]

    def render(self, screen):
        sw, sh = screen.get_size()
        if self.mode == "film" and self.film is not None:
            still = self._image("room_pov.jpg", (sw, int(sw * 720 / 1280)))
            if self.film.render(screen, still) is not False:
                return
        if self.mode in ("room", "talk"):
            self._draw_room(screen, sw, sh)
            set_cursor("talk" if self.mode == "room" and self.hover is not None else None)
        if self.mode == "talk":
            self._draw_talk(screen, sw, sh)

    def _draw_room(self, screen, sw, sh):
        t = time.time()
        k, ox, oy = self._cover(sw, sh)
        bw, bh = int(1280 * k) + 6, int(720 * k) + 6
        bg = self._image("room_pov.jpg", (bw, bh))
        dx = 3 * math.sin(t * 0.21) if not reduced_motion(self.client) else 0
        dy = 2 * math.sin(t * 0.17 + 1) if not reduced_motion(self.client) else 0
        screen.fill((6, 6, 14))
        if bg is not None:
            screen.blit(bg, (int(ox - 3 + dx), int(oy - 3 + dy)))
        # drifting petal motes + candle flicker
        mot = pygame.Surface((sw, sh), pygame.SRCALPHA)
        for (mx, my, sp, sz, ph) in self.motes:
            y = (my + t * sp) % 1.0
            x = mx + 0.015 * math.sin(t * 0.7 + ph)
            a = int(110 + 80 * math.sin(t * 1.3 + ph))
            pygame.draw.circle(mot, (255, 236, 200, max(0, a)), (int(x * sw), int(y * sh)), int(sz))
        screen.blit(mot, (0, 0))
        fl = max(0, int(6 + 5 * math.sin(t * 9.0) * math.sin(t * 3.3)))   # candle flicker
        warm = pygame.Surface((sw, sh))
        warm.fill((fl, int(fl * 0.6), 0))
        screen.blit(warm, (0, 0), special_flags=pygame.BLEND_RGB_ADD)
        # hotspots
        lit = self.hover if self.hover is not None else self.focus
        f_name, f_sub = S.font("title", 15), S.font("body", 15)
        for i, s in enumerate(self.spots):
            r = self.hit_rect(s, sw, sh)
            hov = (i == lit) and self.mode == "room"
            foot = (int(ox + s["x"] * k), int(oy + (s["y"] + s["hit_radius"] * 0.35) * k))
            ring = pygame.Rect(0, 0, max(30, int(r.w * 0.9)), max(10, int(r.w * 0.26)))
            ring.center = foot
            ov = pygame.Surface((ring.w + 24, ring.h + 24), pygame.SRCALPHA)
            rr = pygame.Rect(12, 12, ring.w, ring.h)
            if hov:
                screen.blit(self._lift(r), r.topleft, special_flags=pygame.BLEND_RGB_ADD)
                for g in range(8, 0, -2):
                    pygame.draw.ellipse(ov, (255, 211, 107, 26), rr.inflate(g * 2, g), 3)
                pygame.draw.ellipse(ov, (255, 211, 107, 235), rr, 2)
            else:
                pygame.draw.ellipse(ov, (230, 203, 142, 90), rr, 2)
            screen.blit(ov, (ring.x - 12, ring.y - 12))
            # plaque above the fairy (+ friendship %)
            fpct = self.friend_of(s["name"])
            name = f_name.render(f"{s['name']}  {fpct}%", True, S.ACTIVE_TXT if hov else S.TITLE)
            pr = pygame.Rect(0, 0, name.get_width() + 22, name.get_height() + 8)
            pr.midbottom = (r.centerx, r.y + 2)
            pr.clamp_ip(screen.get_rect().inflate(-8, -8))
            plate = pygame.Surface(pr.size, pygame.SRCALPHA)
            pygame.draw.rect(plate, (18, 12, 8, 200), plate.get_rect(), border_radius=6)
            screen.blit(plate, pr.topleft)
            rim = S.GLOW if fpct >= FRIEND_MAX else (S.GLOW if hov else S.GOLD)
            pygame.draw.rect(screen, rim, pr, 2 if hov or fpct >= FRIEND_MAX else 1, border_radius=6)
            screen.blit(name, (pr.x + 11, pr.y + 4))
            if hov:
                title = (FAIRIES.get(s["name"]) or ("Fairy",))[0]
                tip = f"{title} · Friendship {fpct}/{FRIEND_MAX} · Click to talk"
                if self.secret_unlocked:
                    tip += " · House trusts you"
                sub = f_sub.render(tip, True, (240, 226, 196))
                sr = sub.get_rect(midtop=(pr.centerx, pr.bottom + 3))
                sr.clamp_ip(screen.get_rect().inflate(-8, -8))
                bgs = pygame.Surface(sr.inflate(14, 6).size, pygame.SRCALPHA)
                pygame.draw.rect(bgs, (10, 8, 6, 190), bgs.get_rect(), border_radius=5)
                screen.blit(bgs, sr.inflate(14, 6).topleft)
                screen.blit(sub, sr)
        if self.burst and t - self.burst[2] < 0.2:
            bx, by, t0 = self.burst
            p = (t - t0) / 0.2
            for j in range(10):
                a = j * 0.628
                pygame.draw.circle(screen, (255, 220, 236), (int(bx + math.cos(a) * 34 * p), int(by + math.sin(a) * 34 * p)), 3)
        # leave button + safe zone badge
        self.leave_rect = pygame.Rect(18, sh - 60, 176, 42)
        hovl = self.leave_rect.collidepoint(pygame.mouse.get_pos()) and self.mode == "room"
        S.button(screen, self.leave_rect, "idle", hover=hovl)
        S.text(screen, "Leave the inn", S.font("title", 15), S.label_color("idle"), self.leave_rect.center, anchor="center")
        S.keycap(screen, (self.leave_rect.right + 26, self.leave_rect.centery), "Esc", small=True)
        try:
            sub = "House trusts you" if self.secret_unlocked else "Moon Petal Inn"
            S.shield_badge(screen, pygame.Rect(sw - 214, 14, 200, 44), "safe", "Safe zone", sub)
        except Exception:
            pass
        # House-wide friendship strip (how many fairies are fully trusted)
        maxed = sum(1 for n in FAIRIES if self.friend_of(n) >= FRIEND_MAX)
        strip = pygame.Rect(18, 14, 260, 44)
        S.card(screen, strip, 6)
        S.text(screen, f"Inn trust  {maxed}/9", S.font("title", 15), S.TITLE, (strip.x + 12, strip.y + 6))
        bar = pygame.Rect(strip.x + 12, strip.bottom - 16, strip.w - 24, 8)
        pygame.draw.rect(screen, (20, 14, 10), bar, border_radius=3)
        if maxed:
            pygame.draw.rect(
                screen, (255, 211, 107) if maxed >= 9 else (120, 190, 255),
                pygame.Rect(bar.x, bar.y, int(bar.w * (maxed / 9.0)), bar.h), border_radius=3,
            )
        pygame.draw.rect(screen, S.GOLD, bar, 1, border_radius=3)
        if self.mode == "room" and time.time() - self.room_start < FADE_S:
            veil = pygame.Surface((sw, sh))
            veil.set_alpha(int(255 * (1 - (time.time() - self.room_start) / FADE_S)))
            screen.blit(veil, (0, 0))

    def _lift(self, r):
        s = pygame.Surface(r.size)
        s.fill((15, 15, 15))  # ~6% brightness lift
        return s

    def _portrait(self, name):
        return self._image(os.path.join("portraits", name.lower() + ".jpg"), (290, 360))

    def _draw_friend_bar(self, screen, rect, value, gained=0):
        """Friendship meter under the portrait nameplate."""
        v = max(0, min(self.friend_max, int(value)))
        pygame.draw.rect(screen, (20, 14, 10), rect, border_radius=5)
        pygame.draw.rect(screen, S.GOLD, rect, 1, border_radius=5)
        inner = rect.inflate(-6, -6)
        if inner.w > 0 and inner.h > 0:
            fill_w = int(inner.w * (v / float(self.friend_max or 100)))
            if fill_w > 0:
                fill = pygame.Rect(inner.x, inner.y, fill_w, inner.h)
                col = (120, 190, 255) if v < self.friend_max else (255, 211, 107)
                pygame.draw.rect(screen, col, fill, border_radius=3)
        label = f"Friendship  {v}/{self.friend_max}"
        if gained:
            label += f"  (+{gained})"
        S.text(screen, label, S.font("body", 13), S.ACTIVE_TXT if v >= self.friend_max else S.MUTED,
               (rect.centerx, rect.centery), anchor="center")

    def _draw_talk(self, screen, sw, sh):
        veil = pygame.Surface((sw, sh), pygame.SRCALPHA)
        veil.fill((4, 4, 12, 150))
        screen.blit(veil, (0, 0))
        title = (FAIRIES.get(self.talk) or ("Fairy",))[0]
        W, H = min(sw - 60, 1040), min(sh - 50, 520)
        box = pygame.Rect((sw - W) // 2, sh - H - 28, W, H)
        # portrait: gold double rim, diamond corners
        pr = pygame.Rect(box.x, box.y, 290, 360)
        img = self._portrait(self.talk)
        pygame.draw.rect(screen, (8, 6, 4), pr.inflate(16, 16))
        if img is not None:
            screen.blit(img, pr.topleft)
        S.gold_rim(screen, pr.inflate(16, 16), 4, 4)
        pygame.draw.rect(screen, S.GOLD_HI, pr.inflate(4, 4), 1)
        for cx, cy in (pr.inflate(16, 16).topleft, pr.inflate(16, 16).topright, pr.inflate(16, 16).bottomleft, pr.inflate(16, 16).bottomright):
            S.diamond(screen, cx, cy, 7, S.GOLD_HI, S.WOOD_DK)
        npl = pygame.Rect(pr.x - 8, pr.bottom + 10, pr.w + 16, 72)
        S.card(screen, npl, 6)
        S.text(screen, S.fit(S.font("title", 22), self.talk or "", npl.w - 20), S.font("title", 22), S.TITLE, (npl.centerx, npl.y + 8), anchor="midtop")
        S.text(screen, title, S.font("body", 14), S.MUTED, (npl.centerx, npl.y + 42), anchor="midtop")
        bar = pygame.Rect(npl.x, npl.bottom + 8, npl.w, 22)
        self._draw_friend_bar(screen, bar, self.friend_of(self.talk), self.last_gained)
        if self.secret_unlocked:
            S.text(screen, "House secret unlocked", S.font("body", 12), S.GOLD_HI,
                   (bar.centerx, bar.bottom + 10), anchor="midtop")
        # dialogue box
        db = pygame.Rect(pr.right + 30, box.y, box.right - pr.right - 30, H)
        S.card(screen, db, 8, ornate=True)
        plq = pygame.Rect(0, 0, 300, 34)
        plq.midtop = (db.centerx, db.y - 14)
        S.button(screen, plq, "active", r=5)
        S.text(screen, "THE MOON PETAL INN", S.font("title", 15), S.ACTIVE_TXT, plq.center, anchor="center")
        body = self.body()
        n = int((time.time() - self.type_start) * TYPE_CPS)
        shown = body[:max(0, n)]
        f = S.font("body", 20)
        rs = self.replies()
        rh, gap = 34, 6
        reply_block = len(rs) * (rh + gap) + 28
        text_bottom = db.bottom - reply_block - 8
        y = db.y + 28
        for row in wrap(f, shown, db.w - 56):
            if y + 26 > text_bottom:
                break
            S.text(screen, row, f, (240, 226, 196), (db.x + 28, y))
            y += 26
        # replies
        self.reply_rects = []
        ry = db.bottom - 22 - len(rs) * (rh + gap) + gap
        mouse = pygame.mouse.get_pos()
        rf = S.font("body", 18)
        focus = self.reply_focus
        for i, (lab, act, state) in enumerate(rs):
            r = pygame.Rect(db.x + 20, ry + i * (rh + gap), db.w - 40, rh)
            hov = r.collidepoint(mouse) or focus == i
            muted = state == "seen"
            S.button(screen, r, "idle", hover=hov, r=5)
            S.keycap(screen, (r.x + 18, r.centery), str(i + 1), small=True)
            col = S.MUTED if muted else (S.ACTIVE_TXT if hov else S.label_color("idle"))
            lr = S.text(screen, S.fit(rf, lab, r.w - 70), rf, col, (r.x + 38, r.centery), anchor="midleft")
            if muted:
                _check(screen, min(r.right - 18, lr.right + 14), r.centery, S.MUTED)
            elif state == "new":
                S.notify_dot(screen, min(r.right - 14, lr.right + 12), r.centery)
            self.reply_rects.append(r)
        hint = "1-9 choose  ·  Tab / Enter  ·  Esc back to room"
        S.text(screen, hint, S.font("body", 13), S.MUTED, (db.right - 16, db.bottom - 6), anchor="bottomright")


# ---- cursors (drawn shapes) -------------------------------------------------------------
_CURSOR = {"kind": None, "cache": {}}


def _cursor_surface(kind):
    surf = pygame.Surface((32, 32), pygame.SRCALPHA)
    if kind == "talk":   # speech bubble
        pygame.draw.ellipse(surf, (20, 14, 8), (1, 3, 28, 20))
        pygame.draw.ellipse(surf, (246, 232, 200), (3, 5, 24, 16))
        pygame.draw.polygon(surf, (20, 14, 8), [(8, 18), (5, 29), (15, 20)])
        pygame.draw.polygon(surf, (246, 232, 200), [(9, 18), (7, 26), (14, 19)])
        for x in (10, 15, 20):
            pygame.draw.circle(surf, (120, 90, 40), (x, 13), 2)
        return surf, (6, 28)
    # door: arched door with a gold rim
    pygame.draw.rect(surf, (20, 14, 8), (7, 9, 18, 21))
    pygame.draw.ellipse(surf, (20, 14, 8), (7, 2, 18, 16))
    pygame.draw.rect(surf, (120, 76, 40), (9, 11, 14, 18))
    pygame.draw.ellipse(surf, (120, 76, 40), (9, 4, 14, 14))
    pygame.draw.ellipse(surf, (242, 193, 78), (7, 2, 18, 16), 2)
    pygame.draw.line(surf, (242, 193, 78), (7, 10), (7, 29), 2)
    pygame.draw.line(surf, (242, 193, 78), (24, 10), (24, 29), 2)
    pygame.draw.circle(surf, (242, 193, 78), (19, 19), 2)
    return surf, (16, 16)


def set_cursor(kind):
    """kind: "talk" | "door" | None (system arrow). Only calls pygame on a change."""
    if kind == _CURSOR["kind"]:
        return
    _CURSOR["kind"] = kind
    try:
        if kind is None:
            pygame.mouse.set_cursor(pygame.SYSTEM_CURSOR_ARROW)
        else:
            if kind not in _CURSOR["cache"]:
                img, hot = _cursor_surface(kind)
                _CURSOR["cache"][kind] = pygame.cursors.Cursor(hot, img)
            pygame.mouse.set_cursor(_CURSOR["cache"][kind])
    except Exception:
        pass


def draw_door_hover(client, rect):
    """Overworld door hover: #F2C14E rim glow + tooltip (spec 1.1)."""
    S.glow(client.screen, rect, S.GLOW, 8, 140, 6)
    pygame.draw.rect(client.screen, S.GLOW, rect, 2, border_radius=6)
    f = S.font("body", 17)
    img = f.render("Enter the Moon Petal Inn", True, S.ACTIVE_TXT)
    tr = img.get_rect(midbottom=(rect.centerx, rect.y - 8))
    tr.clamp_ip(client.screen.get_rect())
    bg = tr.inflate(16, 8)
    pygame.draw.rect(client.screen, (18, 12, 8), bg, border_radius=5)
    pygame.draw.rect(client.screen, S.GOLD, bg, 1, border_radius=5)
    client.screen.blit(img, tr)
