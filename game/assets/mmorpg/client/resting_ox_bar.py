"""The Resting Ox bar: over-the-shoulder third-person interior scene, entered from the inn's arched door.

Views (painted key art in assets/resting_ox/): bar (facing Barnaby and the shelves), left (Old Tam),
right (Wren the Minstrel), table (seated at a table). Controls: A/Left and D/Right turn on the stool,
T talk to whoever you face, O order an ale (bar only), Space drink, S sit at a table / back to the bar,
Esc leave to the village. Buttons on the bottom bar do the same. The server (server/resting_ox_inn.py)
checks the door, charges for ale and moves you back out.
"""
import os
import time

import pygame

_DIR = os.path.join(os.path.dirname(__file__), "assets", "resting_ox")
_ART = {"bar": "bar_counter.jpg", "drink": "bar_drink.jpg", "left": "bar_left.jpg", "right": "bar_right.jpg",
        "table": "table.jpg", "table_drink": "table_drink.jpg"}
_FACING = {"left": "old_tam", "bar": "barman", "right": "wren"}
_ORDER = ("left", "bar", "right")
GOLD = (212, 175, 90)
INK = (238, 228, 205)
MUTED = (170, 160, 140)
DRINK_S = 2.2          # full stein animation: lift 0.4, sip 1.2, lower 0.6
FADE_S = 0.6


class RestingOxBar:
    def __init__(self, client):
        self.client = client
        self.active = False
        self.view = "bar"
        self.seat = "bar"
        self.line = ""
        self.speaker = ""
        self.has_ale = False
        self.drink_t = None
        self.sips = 0
        self.opened_at = 0.0
        self.turn_from = None
        self.turn_t = 0.0
        self.hit = []
        self._img = {}
        self._fonts = {}
        self.state = {}

    # ---- art --------------------------------------------------------------------------------------
    def _art(self, key, size):
        k = (key, size)
        if k not in self._img:
            try:
                raw = pygame.image.load(os.path.join(_DIR, _ART[key]))
                raw = raw.convert() if pygame.display.get_surface() else raw
                self._img[k] = pygame.transform.smoothscale(raw, size)
            except (pygame.error, FileNotFoundError, OSError) as e:
                print("resting ox art:", e)
                self._img[k] = None
        return self._img[k]

    def _font(self, size, bold=False):
        k = (size, bold)
        if k not in self._fonts:
            self._fonts[k] = pygame.font.SysFont("georgia,serif", size, bold=bold)
        return self._fonts[k]

    # ---- flow -------------------------------------------------------------------------------------
    def request_enter(self):
        self.client.net.send("BAR_ENTER")

    def on_message(self, t, msg):
        if t == "BAR_STATE":
            first = not self.active
            self.state = msg.get("bar") or {}
            self.seat = self.state.get("seat", "bar")
            if first:
                self.active = True
                self.view = "bar" if self.seat == "bar" else "table"
                self.opened_at = time.time()
                self.has_ale, self.drink_t, self.sips = False, None, 0
            if msg.get("line"):
                self.speaker, self.line = msg.get("speaker") or "", msg["line"]
        elif t == "BAR_LINE":
            self.speaker, self.line = msg.get("speaker") or "", msg.get("line") or ""
        elif t == "BAR_SERVED":
            self.has_ale, self.sips = True, 0
            self.speaker, self.line = msg.get("speaker") or "", msg.get("line") or ""
            if self.client.player is not None and "coins" in msg:
                self.client.player["coins"] = msg["coins"]
        elif t == "BAR_LEFT":
            self.active = False
            p = self.client.player
            if p is not None:
                p["x"], p["y"] = msg.get("x", p.get("x")), msg.get("y", p.get("y"))
                live = (getattr(self.client, "players", None) or {}).get(p.get("id"))
                if live:
                    live["x"], live["y"] = p["x"], p["y"]
            if hasattr(self.client, "clear_walk"):
                self.client.clear_walk()

    def _turn(self, step):
        if self.seat != "bar" or self.drinking():
            return
        i = max(0, min(2, _ORDER.index(self.view) + step))
        if _ORDER[i] != self.view:
            self.turn_from, self.turn_t = self.view, time.time()
            self.view = _ORDER[i]

    def _act(self, kind):
        net = self.client.net
        if kind == "left":
            self._turn(-1)
        elif kind == "right":
            self._turn(1)
        elif kind == "talk":
            who = _FACING.get(self.view) if self.seat == "bar" else "barman"
            net.send("BAR_TALK", patron=who)
        elif kind == "order":
            if self.seat == "bar" and not self.has_ale:
                self.view = "bar"
                net.send("BAR_ORDER")
        elif kind == "drink":
            if self.has_ale and not self.drinking():
                if self.view in ("left", "right"):          # turn back to your stein first
                    self.turn_from, self.turn_t = self.view, time.time()
                    self.view = "bar"
                self.drink_t = time.time()
        elif kind == "sit":
            self.seat = "table" if self.seat == "bar" else "bar"
            self.turn_from, self.turn_t = self.view, time.time()
            self.view = "table" if self.seat == "table" else "bar"
            net.send("BAR_SIT", seat=self.seat)
        elif kind == "leave":
            net.send("BAR_LEAVE")

    def drinking(self):
        return self.drink_t is not None and time.time() - self.drink_t < DRINK_S

    def handle_event(self, event):
        if event.type == pygame.KEYDOWN:
            keys = {pygame.K_a: "left", pygame.K_LEFT: "left", pygame.K_d: "right", pygame.K_RIGHT: "right",
                    pygame.K_t: "talk", pygame.K_o: "order", pygame.K_SPACE: "drink", pygame.K_s: "sit",
                    pygame.K_ESCAPE: "leave"}
            if event.key in keys:
                self._act(keys[event.key])
        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            for kind, rect in self.hit:
                if rect.collidepoint(event.pos):
                    self._act(kind)
                    return

    # ---- drawing ----------------------------------------------------------------------------------
    def _drink_phase(self):
        """0 = stein down, 1 = stein at lips. Lift, hold for the sip, lower."""
        if self.drink_t is None:
            return 0.0
        e = time.time() - self.drink_t
        if e >= DRINK_S:
            self.drink_t = None
            self.sips += 1
            if self.sips >= 3:
                self.has_ale = False
                self.speaker, self.line = "", "You drain the stein. Barnaby nods at the empty pewter."
            return 0.0
        if e < 0.4:
            return e / 0.4
        if e < 1.6:
            return 1.0
        return max(0.0, 1.0 - (e - 1.6) / 0.6)

    def _scene(self, size):
        key = self.view
        img = self._art(key, size)
        if img is None:
            surf = pygame.Surface(size)
            surf.fill((40, 26, 18))
            return surf
        base = img.copy()
        ph = self._drink_phase()
        frame = {"bar": "drink", "table": "table_drink"}.get(key)
        if frame and ph > 0:
            drink = self._art(frame, size)
            if drink is not None:
                # few-frame stein lift: dissolve into the painted drinking pose, hold the sip, lower
                drink = drink.copy()
                drink.set_alpha(int(255 * min(1.0, ph * 1.4)))
                base.blit(drink, (0, 0))
        return base

    def _button(self, surf, rect, label, kind, enabled=True):
        pygame.draw.rect(surf, (26, 18, 12), rect, border_radius=8)
        pygame.draw.rect(surf, GOLD if enabled else (90, 74, 50), rect, 1, border_radius=8)
        t = self._font(15, True).render(label, True, INK if enabled else MUTED)
        surf.blit(t, t.get_rect(center=rect.center))
        if enabled:
            self.hit.append((kind, rect))

    def render(self, surf):
        self.hit = []
        sw, sh = surf.get_size()
        scene_h = int(sw * 9 / 16)
        if scene_h > sh:
            scene_h = sh
        size = (sw, scene_h)
        img = self._scene(size)
        surf.fill((8, 6, 4))
        oy = (sh - scene_h) // 2
        surf.blit(img, (0, oy))
        # turning: brief slide of the previous view so the head-turn reads
        if self.turn_from and time.time() - self.turn_t < 0.35:
            k = (time.time() - self.turn_t) / 0.35
            prev = self._art(self.turn_from, size)
            if prev is not None:
                prev = prev.copy()
                prev.set_alpha(int(255 * (1 - k)))
                surf.blit(prev, (0, oy))
        # warm vignette
        vig = pygame.Surface((sw, sh), pygame.SRCALPHA)
        for i in range(14):
            pygame.draw.rect(vig, (10, 5, 0, 12), (i * 6, i * 6, sw - i * 12, sh - i * 12), 8, border_radius=24)
        surf.blit(vig, (0, 0))
        # title plate
        title = self._font(26, True).render("The Resting Ox", True, GOLD)
        plate = pygame.Rect(0, 0, title.get_width() + 40, 44)
        plate.midtop = (sw // 2, 14)
        pl = pygame.Surface(plate.size, pygame.SRCALPHA)
        pl.fill((14, 9, 5, 190))
        surf.blit(pl, plate.topleft)
        pygame.draw.rect(surf, GOLD, plate, 1, border_radius=6)
        surf.blit(title, title.get_rect(center=plate.center))
        # facing label
        face = {"left": "Old Tam", "bar": "Barnaby the barman", "right": "Wren the Minstrel",
                "table": "Your table"}.get(self.view, "")
        ft = self._font(15).render(face, True, INK)
        surf.blit(ft, (sw // 2 - ft.get_width() // 2, plate.bottom + 6))
        # turn arrows at the bar
        if self.seat == "bar":
            for kind, cx, glyph, ok in (("left", 40, "<", self.view != "left"), ("right", sw - 40, ">", self.view != "right")):
                r = pygame.Rect(0, 0, 48, 48)
                r.center = (cx, sh // 2)
                if ok:
                    pygame.draw.circle(surf, (20, 12, 6), r.center, 24)
                    pygame.draw.circle(surf, GOLD, r.center, 24, 2)
                    g = self._font(24, True).render(glyph, True, GOLD)
                    surf.blit(g, g.get_rect(center=r.center))
                    self.hit.append((kind, r))
        # dialogue box
        if self.line:
            box = pygame.Rect(sw // 2 - 360, sh - 168, 720, 74)
            bx = pygame.Surface(box.size, pygame.SRCALPHA)
            bx.fill((14, 9, 5, 215))
            surf.blit(bx, box.topleft)
            pygame.draw.rect(surf, GOLD, box, 1, border_radius=8)
            y = box.y + 8
            if self.speaker:
                surf.blit(self._font(15, True).render(self.speaker, True, GOLD), (box.x + 14, y))
                y += 20
            words, row, rows = self.line.split(), "", []
            f = self._font(15)
            for w in words:
                test = (row + " " + w).strip()
                if f.size(test)[0] > box.w - 28:
                    rows.append(row)
                    row = w
                else:
                    row = test
            rows.append(row)
            for r in rows[:2]:
                surf.blit(f.render(r, True, INK), (box.x + 14, y))
                y += 19
        # action bar
        bar_y = sh - 52
        coins = int((self.client.player or {}).get("coins") or 0)
        labels = [("talk", "Talk (T)", True)]
        if self.seat == "bar":
            price = "free" if self.state.get("free_ale", True) and not self.has_ale and self.sips == 0 else \
                f"{self.state.get('ale_price', 2)}c"
            labels.append(("order", f"Order ale ({price}) (O)", not self.has_ale))
        labels += [("drink", "Drink (Space)", self.has_ale and not self.drinking()),
                   ("sit", "Sit at table (S)" if self.seat == "bar" else "Back to bar (S)", True),
                   ("leave", "Leave (Esc)", True)]
        widths = [self._font(15, True).size(l)[0] + 30 for _k, l, _e in labels]
        x = sw // 2 - (sum(widths) + 10 * (len(widths) - 1)) // 2
        for (kind, label, en), w in zip(labels, widths):
            self._button(surf, pygame.Rect(x, bar_y, w, 36), label, kind, en)
            x += w + 10
        ct = self._font(14).render(f"{coins:,} coins", True, GOLD)
        surf.blit(ct, (sw - ct.get_width() - 20, 20))
        # entry fade (through the arched door)
        e = time.time() - self.opened_at
        if e < FADE_S:
            sh_ = pygame.Surface((sw, sh))
            sh_.fill((0, 0, 0))
            sh_.set_alpha(int(255 * (1 - e / FADE_S)))
            surf.blit(sh_, (0, 0))
