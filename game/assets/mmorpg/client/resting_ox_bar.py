"""The Resting Ox tavern (client): first-person painted views, entered from the inn's arched door.

Views (assets/resting_ox/tavern/*.jpg, no player body baked in, spec s0): bar (Bram behind the counter),
left (Old Wenna by the fire), right (Tobin and Sable), table (a table for four), board (notice board),
trophy (trophy wall) and bard (Elric the bard). The first visit plays the entry film (tavern_intro.py).
Keys: A/D turn on the stool, T talk to whoever you face, 1-9 pick a dialogue line, O order an ale,
Space drink, S sit at a table / back to the bar, B notice board, W trophy wall, M the bard,
Enter type at a table / in a form, Esc close the panel, or leave. Every key has a button too.
Rules live server side (server/tavern.py via server/resting_ox_inn.py); this draws and sends.
"""
import math
import os
HELM_FRONT_W, HELM_BACK_W, HELM_FRONT_UP, HELM_BACK_UP = 1.42, 1.50, 0.05, 0.02
import time

import pygame

_DIR = os.path.join(os.path.dirname(__file__), "assets", "resting_ox")
_TAV = os.path.join(_DIR, "tavern")
_ART = {"bar": "tavern/bar_bram.jpg", "left": "tavern/woman_left.jpg", "right": "tavern/ranger_right.jpg",
        "table": "tavern/table4.jpg", "board": "tavern/notice_board.jpg", "trophy": "tavern/trophy_wall.jpg",
        "bard": "tavern/bard.jpg"}
# Old art (bakes a player body in) is only an error fallback if a new painting fails to load.
_FALLBACK = {"bar": "bar_counter.jpg", "left": "bar_left.jpg", "right": "bar_right.jpg", "table": "table.jpg"}
_ORDER = ("left", "bar", "right")
_FACE_LABEL = {"left": "Sable, at the end of the bar", "bar": "Bram, Innkeeper of the Crossroads",
               "right": "A ranger, back to the wall", "table": "A table for four", "board": "The notice board",
               "trophy": "The trophy wall", "bard": "Elric the bard"}
GOLD = (212, 175, 90)
INK = (238, 228, 205)
MUTED = (170, 160, 140)
PAPER = (226, 212, 178)
PAPER_INK = (48, 34, 22)
RED = (170, 52, 40)
DRINK_S = 2.2
FADE_S = 0.6
# Seats on the far side of table4.jpg (fractions of the painting): x, head-top y, figure height (full standing
# height the seated upper body is cut from). Sitters face you; the table edge hides them from the chest down.
SEATS = ((0.285, 0.335, 0.98), (0.50, 0.300, 1.04), (0.715, 0.335, 0.98))
TABLE_TOP = (0.145, 0.685, 0.73, 0.33)      # ellipse (x, y, w, h) of the table top, redrawn over sitters
FRAMES = {"kills": (113, 125, 183, 213), "champ": (193, 125, 262, 213), "crown": (272, 98, 387, 230),
          "guild": (398, 125, 467, 213), "legend": (476, 125, 541, 213)}   # trophy_wall.jpg at 640x360
CORK = (100, 50, 428, 292)
YOU_X = {"bar": 0.25}   # over-the-shoulder only facing Bram; side views and the table are first person
# Painted busts on table4.jpg's three chairs: chair x, head-top y, bust height (fractions of the painting).
CHAIR_SEATS = ((0.115, 0.285, 0.42), (0.483, 0.300, 0.37), (0.885, 0.285, 0.42))   # sat tall: chest above the rim                  # notice_board.jpg at 640x360


_SKIN_TONE = {"tone_1": (1.08, 1.04, 1.02), "tone_2": (1.03, 1.0, 0.98), "tone_3": (1.0, 1.0, 1.0),
              "tone_4": (0.88, 0.82, 0.78), "tone_5": (0.74, 0.64, 0.58), "tone_6": (0.58, 0.48, 0.42)}


class RestingOxBar:
    def __init__(self, client):
        self.client = client
        self.active = False
        self.view = "bar"
        self.seat = "bar"
        self.line = ""
        self.speaker = ""
        self.choices = []            # [(label, action tuple)]
        self.has_ale = False
        self.ale_name = "ale"
        self.drink_t = None
        self.sips = 0
        self.opened_at = 0.0
        self.turn_from = None
        self.turn_t = 0.0
        self.hit = []
        self._img = {}
        self._fonts = {}
        self.state = {}
        self.buffs = {}
        self.buffs_at = 0.0
        self.board = None
        self.board_tab = "jobs"
        self.form = None             # {"kind", "fields": {name: text}, "focus", "escrow"}
        self.trophies = None
        self.bard = None
        self.bard_at = 0.0
        self.table = None
        self.tables = []
        self.typing = None           # table chat text being typed
        self.intro = None
        self._fig_scale = {}

    # ---- art / fonts ------------------------------------------------------------------------------
    def _art(self, key, size):
        k = (key, size)
        if k not in self._img:
            img = None
            for path in (_ART.get(key), _FALLBACK.get(key)):
                if not path:
                    continue
                try:
                    raw = pygame.image.load(os.path.join(_DIR, path))
                    raw = raw.convert() if pygame.display.get_surface() else raw
                    img = pygame.transform.smoothscale(raw, size)
                    break
                except (pygame.error, FileNotFoundError, OSError) as e:
                    print("resting ox art:", e)
            self._img[k] = img
        return self._img[k]

    def _portrait(self, size):
        k = ("portrait", size)
        if k not in self._img:
            try:
                raw = pygame.image.load(os.path.join(_TAV, "bram_portrait.jpg"))
                self._img[k] = pygame.transform.smoothscale(raw, (size, size))
            except (pygame.error, FileNotFoundError, OSError):
                self._img[k] = None
        return self._img[k]

    def _font(self, size, bold=False):
        k = (size, bold)
        if k not in self._fonts:
            self._fonts[k] = pygame.font.SysFont("georgia,serif", size, bold=bold)
        return self._fonts[k]

    # ---- network ----------------------------------------------------------------------------------
    def request_enter(self):
        self.client.net.send("BAR_ENTER")

    WALK_IN_COOLDOWN_S = 1.5

    def is_arch(self, x, y):
        if getattr(self.client, "dungeon", None):
            return False
        for spot in getattr(self.client, "interactables", None) or []:
            if spot.get("bar") and (int(spot["x"]), int(spot["y"])) == (int(x), int(y)):
                return True
        return False

    def walk_in(self, x, y):
        """Walking into the arched door enters the bar just like clicking it. A short cooldown after
        leaving (and only stepping onto the arch, never off it) keeps it from re-triggering in a loop."""
        if self.active or not self.is_arch(x, y):
            return False
        if time.time() - getattr(self, "left_at", 0.0) < self.WALK_IN_COOLDOWN_S:
            return False
        if time.time() - getattr(self, "_walk_sent", 0.0) < 1.0:
            return False
        self._walk_sent = time.time()
        self.client._ox_enter_sent = time.time()      # shared with client._maybe_walk_into_resting_ox
        self.request_enter()
        return True

    def _send(self, t, **kw):
        self.client.net.send(t, **kw)

    def _set_coins(self, msg):
        p = self.client.player
        if p is not None and "coins" in msg:
            p["coins"] = msg["coins"]

    def _set_buffs(self, b):
        if b is not None:
            self.buffs, self.buffs_at = b, time.time()

    def on_message(self, t, msg):
        if t == "BAR_STATE":
            first = not self.active
            self.state.update(msg.get("bar") or {})
            self.seat = self.state.get("seat", "bar")
            self._set_buffs(self.state.get("buffs"))
            self.tables = self.state.get("tables") or self.tables
            if first:
                self.active = True
                self.view = "bar" if self.seat == "bar" else "table"
                self.opened_at = time.time()
                self.has_ale, self.drink_t, self.sips = False, None, 0
                self.choices, self.board, self.trophies, self.bard, self.table = [], None, None, None, None
                if msg.get("intro"):
                    self._start_intro()
            elif self.seat == "bar" and self.view == "table":
                self.view, self.table = "bar", None
            if msg.get("line"):
                self.speaker, self.line = msg.get("speaker") or "", msg["line"]
        elif t == "BAR_LINE":
            self._set_coins(msg)
            self._set_buffs(msg.get("buffs"))
            self.speaker, self.line = msg.get("speaker") or "", msg.get("line") or ""
            self._choices_from(msg)
        elif t == "BAR_SERVED":
            self._set_coins(msg)
            self._set_buffs(msg.get("buffs"))
            if msg.get("drink"):
                self.has_ale, self.sips, self.ale_name = True, 0, msg.get("name") or "ale"
            self.state["free_left"] = msg.get("free_left", 0)
            self.speaker, self.line = msg.get("speaker") or "", msg.get("line") or ""
            cost = "free" if msg.get("free") or not msg.get("price") else f"{msg['price']}c"
            self.line += f"  ({msg.get('name')}, {cost})"
            self.choices = []
        elif t == "BAR_BUFFS":
            self._set_buffs(msg.get("buffs"))
        elif t == "BAR_BOARD_STATE":
            self.board = msg.get("board") or {}
        elif t == "BAR_TROPHY_STATE":
            self.trophies = msg.get("trophies") or {}
        elif t == "BAR_BARD_STATE":
            self.bard, self.bard_at = msg.get("bard") or {}, time.time()
        elif t == "BAR_TABLE":
            self.table = msg.get("table")
        elif t == "BAR_TABLES":
            self.tables = msg.get("tables") or []
        elif t == "BAR_LEFT":
            self.active = False
            self.left_at = time.time()
            self.intro = None
            p = self.client.player
            if p is not None:
                p["x"], p["y"] = msg.get("x", p.get("x")), msg.get("y", p.get("y"))
                live = (getattr(self.client, "players", None) or {}).get(p.get("id"))
                if live:
                    live["x"], live["y"] = p["x"], p["y"]
            if hasattr(self.client, "clear_walk"):
                self.client.clear_walk()

    def _start_intro(self, replay=False):
        try:
            import tavern_intro
        except Exception:
            return
        if not tavern_intro.available() and not tavern_intro.reduced_motion(self.client):
            return

        def done():
            self.intro = None
            self.opened_at = time.time() - FADE_S + 0.3      # 0.3 s fade in to the seated bar view
            if not replay:                                     # a replay leaves intro_seen alone
                self._send("BAR_INTRO_SEEN")
        self.intro = tavern_intro.TavernIntro(self.client, done)

    # ---- dialogue choices -------------------------------------------------------------------------
    def _bram_menu(self):
        return [("Drinks", ("menu", "drink")), ("Food", ("menu", "food")), ("Any rumours?", ("rumour", False)),
                ("Tell me about...", ("about_menu",)), ("Watch the entry film again", ("replay_intro",)),
                ("Leave him to it", ("close",))]

    def _choices_from(self, msg):
        pat = msg.get("patron")
        if msg.get("offer", {}) and (msg.get("offer") or {}).get("kind") == "sable_drink":
            price = msg["offer"].get("price", 5)
            self.choices = [(f"Buy her an ale ({price}c)", ("sable",)), ("Not now", ("close",))]
        elif msg.get("close"):
            self.choices = []
        elif pat == "barman" and "rumour" in msg:
            if msg.get("rumour"):
                self.choices = [("Another? (tip 5c)", ("rumour", True)), ("Back", ("bram",))]
            else:
                self.choices = [("Tip Bram 5c for another", ("rumour", True)), ("Back", ("bram",))]
        elif pat == "barman" and msg.get("choices"):
            self.choices = self._bram_menu()
        elif pat in ("wenna", "tobin", "sable", "hale") and msg.get("choices"):
            self.choices = [(label, ("choice", pat, i)) for i, label in enumerate(msg["choices"])]
        elif pat == "barman":
            self.choices = [("Back", ("bram",))]

    def _menu_choices(self, kind):
        out = []
        free = int(self.state.get("free_left", 0) or 0)
        for m in self.state.get("menu") or []:
            if m["kind"] != kind:
                continue
            price = "free" if m["price"] == 0 else f"{m['price']}c"
            tag = "  * today's special" if m.get("special") else ""
            out.append((f"{m['name']}  {price}  ({m['desc']}){tag}", ("order", m["id"])))
        out.append(("Back", ("bram",)))
        if kind == "drink" and free:
            self.speaker, self.line = "Bram", (f"{self.line.split('  (')[0]}  You've {free} on the house."
                                              if free < 90 else "Anything you like, Your Grace. No coin.")
        elif kind == "food":
            self.speaker, self.line = "Bram", "Stew's been on since dawn. Bread's from this morning."
        return out

    def _do(self, a):
        k = a[0]
        if k == "menu":
            self.choices = self._menu_choices(a[1])
        elif k == "order":
            self.view = "bar" if self.seat == "bar" else self.view
            if a[1] in ("village_ale", "honeyed_mead", "dwarven_stout", "spiced_cider", "ox_reserve", "water") \
                    and self.has_ale:
                self.speaker, self.line = "Bram", "Finish the one you've got first."
                return
            self._send("BAR_ORDER", item=a[1])
        elif k == "rumour":
            self._send("BAR_RUMOUR", tip=bool(a[1]))
        elif k == "replay_intro":                              # Bram's "Watch the entry film again" (client-only)
            self.choices = []
            self._start_intro(replay=True)
        elif k == "about_menu":
            self.choices = [("The arena", ("about", "arena")), ("The King", ("about", "king")),
                            ("The guilds", ("about", "guilds")), ("This place", ("about", "place")),
                            ("Back", ("bram",))]
        elif k == "about":
            self._send("BAR_ABOUT", topic=a[1])
        elif k == "choice":
            self._send("BAR_CHOICE", patron=a[1], choice=a[2])
        elif k == "sable":
            self._send("BAR_SABLE_DRINK")
        elif k == "bram":
            self._send("BAR_TALK", patron="barman")
        elif k == "talk_patron":
            self._send("BAR_TALK", patron=a[1])
        elif k == "close":
            self.choices = []
        elif k == "sit_table":
            self.choices, self.line, self.speaker = [], "", ""
            self.seat, self.view = "table", "table"
            self.turn_from, self.turn_t = "bar", time.time()
            self._send("BAR_SIT", seat="table", table=a[1])
        elif k == "queue":
            self.choices = []
            self._send("BAR_QUEUE", table=a[1])
        elif k == "tab":
            self.board_tab, self.form = a[1], None
        elif k == "job":
            self._send("BAR_JOB", action=a[1], id=a[2])
        elif k == "post_act":
            self._send("BAR_POST_ACT", action=a[1], id=a[2])
        elif k == "form":
            self._open_form(a[1])
        elif k == "focus":
            if self.form:
                self.form["focus"] = a[1]
        elif k == "submit":
            self._submit_form()
        elif k == "song":
            self._send("BAR_BARD_REQ", song=a[1], jump=bool(a[2]))

    def _open_form(self, kind):
        board = self.board or {}
        if kind.startswith("royal:"):
            tpl = kind.split(":", 1)[1]
            text = (board.get("proclaim_templates") or {}).get(tpl, "")
            fields = ["value"] if "{value}" in text else []
            self.form = {"kind": kind, "fields": {f: "" for f in fields + ["note"]}, "order": fields + ["note"],
                         "focus": (fields + ["note"])[0]}
            return
        import re
        tpl = (board.get("templates") or {}).get(kind, "")
        names = re.findall(r"{(\w+)}", tpl)
        order = names + ["note"] + (["escrow"] if kind == "wanted" else [])
        self.form = {"kind": kind, "fields": {f: "" for f in order}, "order": order, "focus": order[0]}

    def _submit_form(self):
        f = self.form
        if not f:
            return
        vals = dict(f["fields"])
        if f["kind"].startswith("royal:"):
            self._send("BAR_PROCLAIM", template=f["kind"].split(":", 1)[1], value=vals.get("value", ""),
                       note=vals.get("note", ""))
        else:
            esc = vals.pop("escrow", "") or "0"
            note = vals.pop("note", "")
            self._send("BAR_POST", kind=f["kind"], fields=vals, note=note,
                       escrow=int(esc) if str(esc).isdigit() else 0)
        self.form = None

    # ---- actions / input --------------------------------------------------------------------------
    def _turn(self, step):
        if self.seat != "bar" or self.drinking() or self.view not in _ORDER:
            return
        i = max(0, min(2, _ORDER.index(self.view) + step))
        if _ORDER[i] != self.view:
            self.turn_from, self.turn_t = self.view, time.time()
            self.view = _ORDER[i]
            self.choices = []

    def _go(self, view):
        if view != self.view:
            self.turn_from, self.turn_t = self.view, time.time()
        self.view, self.choices, self.form = view, [], None
        if view in ("board", "trophy", "bard", "table"):
            self.line, self.speaker = "", ""

    def _home(self):
        return "table" if self.seat == "table" else "bar"

    def _act(self, kind):
        if isinstance(kind, tuple):
            self._do(kind)
            return
        if kind == "left":
            self._turn(-1)
        elif kind == "right":
            self._turn(1)
        elif kind == "talk":
            if self.view == "left":
                self.speaker, self.line = "", "Sable watches you over her tankard. Old Wenna dozes by the fire."
                self.choices = [("Talk to Sable", ("talk_patron", "sable")),
                                ("Talk to Old Wenna (by the fire)", ("talk_patron", "wenna"))]
            elif self.view == "right":
                self.speaker, self.line = "", "The ranger keeps one eye on the door. Tobin fidgets at the end of the bar."
                self.choices = [("Talk to the ranger", ("talk_patron", "hale")),
                                ("Talk to Tobin (end of the bar)", ("talk_patron", "tobin"))]
            elif self.view == "bard":
                self._send("BAR_BARD")
            else:
                self._send("BAR_TALK", patron="barman")
        elif kind == "order":
            if self.seat == "bar" and not self.has_ale:
                self._go("bar")
                self._send("BAR_ORDER", item="village_ale")
        elif kind == "drink":
            if self.has_ale and not self.drinking():
                if self.view in ("left", "right"):
                    self._go("bar")
                self.drink_t = time.time()
        elif kind == "sit":
            if self.seat == "bar":
                self._send("BAR_TABLES")
                tabs = self.tables or [{"id": i, "taken": 0, "seats": 4, "locked": False} for i in (1, 2, 3)]
                self.speaker, self.line = "", "Pick a table."
                self.choices = []
                for tb in tabs:
                    full = tb["taken"] >= tb["seats"]
                    lab = f"Table {tb['id']}  ({tb['taken']}/{tb['seats']})" + ("  locked" if tb.get("locked") else "")
                    if tb.get("names"):
                        lab += "  " + ", ".join(tb["names"][:3])
                    self.choices.append((lab + ("  full: wait for a seat" if full else ""),
                                         ("queue", tb["id"]) if full else ("sit_table", tb["id"])))
                self.choices.append(("Stay at the bar", ("close",)))
            else:
                self.seat, self.table, self.typing = "bar", None, None
                self._go("bar")
                self._send("BAR_SIT", seat="bar")
        elif kind == "board":
            self._go("board")
            self._send("BAR_BOARD")
        elif kind == "trophy":
            self._go("trophy")
            self._send("BAR_TROPHIES")
        elif kind == "bard":
            self._go("bard")
            self._send("BAR_BARD")
        elif kind == "back":
            self._go(self._home())
        elif kind == "toast":
            self._send("BAR_TOAST")
        elif kind == "toast_join":
            self._send("BAR_TOAST_JOIN")
        elif kind == "round":
            self._send("BAR_ROUND")
        elif kind == "lock":
            self._send("BAR_TABLE_LOCK", locked=not (self.table or {}).get("locked"))
        elif kind == "chat":
            self.typing = ""
        elif kind == "leave":
            self._send("BAR_LEAVE")

    def drinking(self):
        return self.drink_t is not None and time.time() - self.drink_t < DRINK_S

    def _escape(self):
        if self.form:
            self.form = None
        elif self.choices:
            self.choices = []
        elif self.view in ("board", "trophy", "bard"):
            self._act("back")
        else:
            self._act("leave")

    def _type_key(self, event, text):
        if event.key == pygame.K_BACKSPACE:
            return text[:-1], None
        if event.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
            return text, "submit"
        if event.key == pygame.K_ESCAPE:
            return text, "cancel"
        if event.key == pygame.K_TAB:
            return text, "tab"
        ch = getattr(event, "unicode", "") or ""
        if ch and ch.isprintable() and len(text) < 120:
            text += ch
        return text, None

    def handle_event(self, event):
        if self.intro is not None:
            self.intro.handle_event(event)
            return
        if event.type == pygame.KEYDOWN and self.typing is not None:
            self.typing, cmd = self._type_key(event, self.typing)
            if cmd == "submit":
                if self.typing.strip():
                    self._send("BAR_TABLE_CHAT", text=self.typing.strip())
                self.typing = None
            elif cmd == "cancel":
                self.typing = None
            return
        if event.type == pygame.KEYDOWN and self.form:
            f = self.form
            text, cmd = self._type_key(event, f["fields"][f["focus"]])
            f["fields"][f["focus"]] = text
            if cmd == "submit":
                self._submit_form()
            elif cmd == "cancel":
                self.form = None
            elif cmd == "tab":
                o = f["order"]
                f["focus"] = o[(o.index(f["focus"]) + 1) % len(o)]
            return
        if event.type == pygame.KEYDOWN:
            if pygame.K_1 <= event.key <= pygame.K_9 and self.choices:
                i = event.key - pygame.K_1
                if i < len(self.choices):
                    self._do(self.choices[i][1])
                return
            if event.key == pygame.K_ESCAPE:
                self._escape()
                return
            if event.key in (pygame.K_RETURN, pygame.K_KP_ENTER) and self.view == "table":
                self._act("chat")
                return
            keys = {pygame.K_a: "left", pygame.K_LEFT: "left", pygame.K_d: "right", pygame.K_RIGHT: "right",
                    pygame.K_t: "talk", pygame.K_o: "order", pygame.K_SPACE: "drink", pygame.K_s: "sit",
                    pygame.K_b: "board", pygame.K_w: "trophy", pygame.K_m: "bard"}
            if event.key in keys:
                self._act(keys[event.key])
        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            for kind, rect in reversed(self.hit):
                if rect.collidepoint(event.pos):
                    self._act(kind)
                    return

    # ---- drawing helpers --------------------------------------------------------------------------
    def _drink_phase(self):
        """0 = stein down, 1 = stein at your lips. Lift 0.4 s, sip 1.2 s, lower 0.6 s."""
        if self.drink_t is None:
            return 0.0
        e = time.time() - self.drink_t
        if e >= DRINK_S:
            self.drink_t = None
            self.sips += 1
            if self.sips >= 3:
                self.has_ale = False
                self.speaker, self.line = "", "You drain the tankard. Bram nods at the empty pewter."
            return 0.0
        if e < 0.4:
            return e / 0.4
        if e < 1.6:
            return 1.0
        return max(0.0, 1.0 - (e - 1.6) / 0.6)

    def _wrap(self, text, font, width):
        rows, row = [], ""
        for w in str(text).split():
            t = (row + " " + w).strip()
            if font.size(t)[0] > width and row:
                rows.append(row)
                row = w
            else:
                row = t
        if row:
            rows.append(row)
        return rows

    def _panel(self, surf, rect, alpha=215, border=GOLD, fill=(14, 9, 5)):
        bx = pygame.Surface(rect.size, pygame.SRCALPHA)
        bx.fill((*fill, alpha))
        surf.blit(bx, rect.topleft)
        pygame.draw.rect(surf, border, rect, 1, border_radius=8)

    def _button(self, surf, rect, label, kind, enabled=True, size=15):
        pygame.draw.rect(surf, (26, 18, 12), rect, border_radius=8)
        pygame.draw.rect(surf, GOLD if enabled else (90, 74, 50), rect, 1, border_radius=8)
        t = self._font(size, True).render(label, True, INK if enabled else MUTED)
        surf.blit(t, t.get_rect(center=rect.center))
        if enabled:
            self.hit.append((kind, rect))

    def _paper_button(self, surf, rect, label, kind):
        pygame.draw.rect(surf, (92, 52, 30), rect, border_radius=5)
        t = self._font(13, True).render(label, True, PAPER)
        surf.blit(t, t.get_rect(center=rect.center))
        self.hit.append((kind, rect))

    def _tankard(self, height, tilt):
        key = ("_tank", height, tilt)
        if key not in self._img:
            im = None
            try:
                raw = pygame.image.load(os.path.join(_TAV, "tankard.png"))
                raw = raw.convert_alpha() if pygame.display.get_surface() else raw
                k = height / raw.get_height()
                im = pygame.transform.smoothscale(raw, (max(1, int(raw.get_width() * k)), height))
                if tilt:
                    im = pygame.transform.rotozoom(im, -tilt, 1.0)
            except (pygame.error, FileNotFoundError, OSError) as e:
                print("resting ox tankard:", e)
            self._img[key] = im
        return self._img[key]

    def _stein(self, surf, cx, base_y, height, tilt=0.0, foam=True):
        """Your tankard (first person: only the cup), matching the painted ones: oak staves, iron hoops,
        firelit from the left. Drawn 2x and smooth-scaled for soft edges; foam head until the 2nd sip."""
        key = ("_stein", height, round(tilt), foam)
        im = self._img.get(key)
        if im is None:
            S = 2
            h = int(height * S)
            w = int(h * 0.72)
            pad = int(h * 0.42)
            s = pygame.Surface((w + pad, h + pad // 2), pygame.SRCALPHA)
            top = int(h * 0.12)
            body = pygame.Rect(0, top, w, h - top)
            for i in range(w):                                   # cylinder: lit from the fire (left)
                u = i / max(1, w - 1)
                lit = math.cos((u - 0.32) * math.pi * 0.95)
                lit = max(0.0, lit) ** 1.4
                r = int(44 + 104 * lit + (22 if 0.20 < u < 0.27 else 0))
                g = int(26 + 62 * lit + (14 if 0.20 < u < 0.27 else 0))
                bl = int(16 + 40 * lit + (8 if 0.20 < u < 0.27 else 0))
                pygame.draw.line(s, (min(255, r), min(255, g), min(255, bl), 255),
                                 (i, body.y + int(h * 0.03)), (i, body.bottom - int(h * 0.03)))
            for k in range(1, 7):                                # staves
                xx = int(w * k / 7)
                pygame.draw.line(s, (30, 18, 10, 255), (xx, body.y + 4), (xx, body.bottom - 4), max(1, S))
            ew = int(h * 0.07)
            for yy in (body.y + int(h * 0.06), body.bottom - int(h * 0.08)):     # hoops
                for i in range(w):
                    u = i / max(1, w - 1)
                    lit = max(0.0, math.cos((u - 0.32) * math.pi * 0.95)) ** 1.2
                    c = int(40 + 110 * lit)
                    pygame.draw.line(s, (c // 2 + 10, c // 2 + 8, c // 2 + 6, 255), (i, yy - ew // 2), (i, yy + ew // 2))
            pygame.draw.ellipse(s, (34, 30, 28, 255), (0, body.bottom - int(h * 0.07), w, int(h * 0.07)))
            hcx, hcy = w - int(w * 0.04), body.y + int(h * 0.40)         # handle: a thick C off the right side
            hrx, hry, th = int(w * 0.30), int(h * 0.25), max(3, int(h * 0.05))
            for k in range(61):
                ang = -math.pi / 2 + math.pi * k / 60
                px, py = hcx + hrx * math.cos(ang), hcy + hry * math.sin(ang)
                pygame.draw.circle(s, (34, 30, 28, 255), (int(px) + 2, int(py) + 3), th)
            for k in range(61):
                ang = -math.pi / 2 + math.pi * k / 60
                px, py = hcx + hrx * math.cos(ang), hcy + hry * math.sin(ang)
                lit = 0.5 + 0.5 * -math.sin(ang)
                c = int(70 + 70 * lit)
                pygame.draw.circle(s, (c, int(c * 0.62), int(c * 0.34), 255), (int(px), int(py)), th)
            pygame.draw.rect(s, (90, 84, 76, 255), (w - int(w * 0.06), hcy - hry - th, int(w * 0.08), th * 2))
            rim = pygame.Rect(-1, body.y - int(h * 0.05), w + 2, int(h * 0.11))
            pygame.draw.ellipse(s, (96, 90, 84, 255), rim)
            pygame.draw.ellipse(s, (40, 26, 12, 255), rim.inflate(-int(w * 0.08), -int(h * 0.03)))
            if foam:
                fr = rim.inflate(-int(w * 0.06), -int(h * 0.02)).move(0, -int(h * 0.03))
                pygame.draw.ellipse(s, (226, 206, 160, 255), fr)
                rnd = __import__("random").Random(7)
                for _ in range(26):
                    bx = fr.x + rnd.randint(4, fr.w - 4)
                    by = fr.y + rnd.randint(-int(h * 0.03), fr.h // 2)
                    rr = rnd.randint(int(h * 0.018), int(h * 0.045))
                    shade = rnd.randint(228, 250)
                    pygame.draw.circle(s, (shade, shade - 10, shade - 40, 255), (bx, by), rr)
                pygame.draw.ellipse(s, (240, 228, 196, 255), (fr.x + int(w * 0.1), body.y + int(h * 0.02),
                                                              int(w * 0.08), int(h * 0.12)))   # drip
            im = pygame.transform.smoothscale(s, (s.get_width() // S, s.get_height() // S))
            if tilt:
                im = pygame.transform.rotozoom(im, -tilt, 1.0)
            self._img[key] = im
        r = im.get_rect(midbottom=(cx, base_y))
        surf.blit(im, r)

    def _dialogue(self, surf, sw, sh):
        if not self.line and not self.choices:
            return
        f = self._font(15)
        rows = self._wrap(self.line, f, 560)[:3] if self.line else []
        ch_h = 24 * len(self.choices)
        box = pygame.Rect(sw // 2 - 380, 0, 760, 18 + (20 if self.speaker else 0) + 19 * len(rows) + ch_h + 10)
        box.bottom = sh - 64
        self._panel(surf, box)
        x = box.x + 14
        if self.speaker in ("Bram", "Bram, Innkeeper of the Crossroads"):
            pic = self._portrait(72)
            if pic is not None:
                frame = pygame.Rect(box.x + 10, box.y + 10, 76, 76)
                surf.blit(pic, (frame.x + 2, frame.y + 2))
                pygame.draw.rect(surf, GOLD, frame, 2, border_radius=4)
                x = frame.right + 12
        elif self.speaker:
            c = pygame.Rect(box.x + 12, box.y + 12, 44, 44)
            pygame.draw.circle(surf, (44, 28, 18), c.center, 22)
            pygame.draw.circle(surf, GOLD, c.center, 22, 2)
            ini = self._font(20, True).render(self.speaker[:1], True, GOLD)
            surf.blit(ini, ini.get_rect(center=c.center))
            x = c.right + 12
        y = box.y + 9
        if self.speaker:
            surf.blit(self._font(15, True).render(self.speaker, True, GOLD), (x, y))
            y += 20
        for r in rows:
            surf.blit(f.render(r, True, INK), (x, y))
            y += 19
        y += 4
        for i, (label, action) in enumerate(self.choices):
            rr = pygame.Rect(x - 4, y, box.right - x - 10, 22)
            if rr.collidepoint(pygame.mouse.get_pos()):
                pygame.draw.rect(surf, (60, 40, 22), rr, border_radius=4)
            t = self._font(14, True).render(f"{i + 1}.  {label}", True, (236, 214, 150))
            surf.blit(t, (rr.x + 4, rr.y + 3))
            self.hit.append((action, rr))
            y += 24

    def _buff_chips(self, surf, x, y):
        b = self.buffs or {}
        gone = time.time() - self.buffs_at
        chips = []
        d = b.get("drink")
        if d and d.get("left", 0) - gone > 0:
            bits = []
            if d.get("xp_pct"):
                bits.append(f"+{d['xp_pct']}% XP")
            if d.get("hp_pct"):
                bits.append(f"+{d['hp_pct']}% HP")
            if d.get("regen"):
                bits.append("regen")
            chips.append(f"{d['name']}: {', '.join(bits)}  {int((d['left'] - gone) // 60) + 1}m")
        if b.get("tipsy_left", 0) - gone > 0:
            chips.append("Tipsy")
        if b.get("toast_left", 0) - gone > 0:
            chips.append("Toast: +1% XP")
        for c in chips:
            t = self._font(13, True).render(c, True, INK)
            r = pygame.Rect(x, y, t.get_width() + 18, 24)
            self._panel(surf, r, 200, (150, 120, 60))
            surf.blit(t, (r.x + 9, r.y + 4))
            y += 28

    def tipsy(self):
        b = self.buffs or {}
        return b.get("tipsy_left", 0) - (time.time() - self.buffs_at) > 0

    # ---- view overlays ----------------------------------------------------------------------------
    @staticmethod
    def _r640(box, size, oy):
        sw, sh = size
        x0, y0, x1, y1 = box
        return pygame.Rect(int(x0 / 640 * sw), oy + int(y0 / 360 * sh), int((x1 - x0) / 640 * sw),
                           int((y1 - y0) / 360 * sh))

    def _figure(self, look, height, facing=1):
        """A live HD player render (idle) scaled to `height` px, drawn natively at that size (no upscaling).
        Cached by look + size + facing + idle frame."""
        import json
        facing = {"front": "s", "back": "n", 1: "s"}.get(facing, facing)   # player_hd_client wants s/e/n/w
        key = (json.dumps(look, sort_keys=True, default=str), height, str(facing), int(time.time() * 6) % 12)
        cache = self._img.setdefault("_fig", {})
        if key in cache:
            return cache[key]
        if len(cache) > 48:
            cache.clear()
        try:
            import player_hd_client as hd
        except Exception:
            return None

        def draw(tile):
            probe = pygame.Surface((tile * 4, tile * 6), pygame.SRCALPHA)
            hd.draw_player(probe, look.get("sex") or "male", look.get("appearance") or {}, tile * 2, tile * 5,
                           tile, time.time(), anim="idle", facing=facing, equipment=look.get("equipment") or {})
            return probe
        try:
            ratio = self._img.get(("_figratio", str(facing)))
            if ratio is None:
                bb0 = draw(100).get_bounding_rect(min_alpha=8)
                ratio = self._img[("_figratio", str(facing))] = max(0.5, bb0.h / 100.0)
            probe = draw(max(16, int(height / ratio)))
        except Exception:
            return None
        bb = probe.get_bounding_rect(min_alpha=8)
        if bb.h < 8:
            return None
        fig = probe.subsurface(bb).copy()
        if abs(bb.h - height) > 2:
            k = height / bb.h
            fig = pygame.transform.smoothscale(fig, (max(1, int(bb.w * k)), max(1, int(bb.h * k))))
        cache[key] = fig
        return fig

    def _look_colours(self, look):
        """(hair rgb, garment rgb) for a look: hair from the catalogue hair palette, garment sampled from the
        live layered HD render of your back (so every outfit, palette and cloak drives the painted layer)."""
        try:
            import player_hd_client as hd
            hair = hd._parse_hair_colour((look.get("appearance") or {}).get("hair_colour")
                                         or ("chestnut" if look.get("sex") == "female" else "dark_brown"))
        except Exception:
            hair = (70, 46, 30)
        cloth = (92, 78, 62)
        fig = self._figure(look, 120, "back")
        if fig is not None:
            import numpy as np
            w, h = fig.get_size()
            rgb = pygame.surfarray.array3d(fig)[:, int(h * 0.30):int(h * 0.55)].reshape(-1, 3)
            al = pygame.surfarray.array_alpha(fig)[:, int(h * 0.30):int(h * 0.55)].reshape(-1)
            px = rgb[al > 200]
            if len(px) > 20:
                cloth = tuple(int(c) for c in np.median(px, axis=0))
        return hair, cloth

    def _back_figure(self, look, height):
        """You, seen from behind (third person): a painted back-view bust for your sex + hairstyle
        (assets/resting_ox/tavern/back/), its hair layer tinted to your hair colour and its garment layer to your
        outfit's colour, graded into the firelight. Falls back to the HD sprite only if the painting fails."""
        import json
        key = ("_back", json.dumps(look, sort_keys=True, default=str), height)
        if key in self._img:
            return self._img[key]
        im = None
        try:
            im = self._wear_hat(look, self._painted_back(look, height), False)
        except Exception as e:                                   # error fallback: the scaled HD sprite
            print("resting ox back layer:", e)
            fig = self._figure(look, min(height, 560), "back")
            if fig is not None:
                k = height / fig.get_height()
                im = pygame.transform.smoothscale(fig, (max(1, int(fig.get_width() * k)), height))
                im.fill((178, 146, 116, 255), special_flags=pygame.BLEND_RGBA_MULT)
        self._img[key] = im
        return im

    def _painted_back(self, look, height, front=False):
        import numpy as np
        sex = "f" if look.get("sex") == "female" else "m"
        hair_id = (look.get("appearance") or {}).get("hair") or ("hair_ponytail" if sex == "f" else "hair_crop")
        pre = "front_" if front else ""
        base = os.path.join(_TAV, "back", f"{pre}{sex}_{hair_id}")
        if not os.path.exists(base + ".png"):
            base = os.path.join(_TAV, "back", f"{pre}{sex}_{'hair_ponytail' if sex == 'f' else 'hair_crop'}")
        raw = pygame.image.load(base + ".png")
        msk = pygame.image.load(base + "_mask.png")
        hair, cloth = self._look_colours(look)
        rgb = pygame.surfarray.array3d(raw).astype(np.float32) / 255
        m = pygame.surfarray.array3d(msk).astype(np.float32) / 255
        lum = rgb.mean(axis=2, keepdims=True)
        hcol = np.array(hair, np.float32) / 255
        ccol = np.array(cloth, np.float32) / 255
        h_layer = np.clip(lum * hcol * 1.45, 0, 1)
        c_layer = np.clip(lum * ccol * 2.1, 0, 1)
        mh, mc, ms = m[..., 0:1], m[..., 1:2], m[..., 2:3]
        tone = _SKIN_TONE.get((look.get("appearance") or {}).get("skin_tone"), (1.0, 1.0, 1.0))
        rgb = rgb * (1 - ms) + np.clip(rgb * np.array(tone, np.float32), 0, 1) * ms      # their skin tone
        out = rgb * np.clip(1 - mh - mc, 0, 1) + h_layer * mh + c_layer * mc
        out *= np.array([0.70, 0.60, 0.50] if not front else [0.74, 0.62, 0.50], np.float32)   # firelit, gritty
        ys = np.linspace(1.0, 0.45 if not front else 0.8, out.shape[1], dtype=np.float32)[None, :, None]
        out *= ys                                                    # falls into shadow below the shoulders
        out += np.random.default_rng(7).normal(0, 0.018, out.shape[:2] + (1,)).astype(np.float32)   # grain
        surf = pygame.Surface(raw.get_size(), pygame.SRCALPHA)
        pygame.surfarray.blit_array(surf, (np.clip(out, 0, 1) * 255).astype(np.uint8))
        alpha = pygame.surfarray.array_alpha(raw)
        pygame.surfarray.pixels_alpha(surf)[:] = alpha
        bb = surf.get_bounding_rect(min_alpha=8)
        surf = surf.subsurface(bb).copy()
        k = height / surf.get_height()
        w = max(1, int(surf.get_width() * k))
        if front:
            vary = int(look.get("_vary") or 0)                 # same painting, different person: mirror + build
            w = max(1, int(w * (0.95, 1.0, 1.04, 0.98)[vary % 4]))
            out_s = pygame.transform.smoothscale(surf, (w, height))
            return pygame.transform.flip(out_s, True, False) if (vary // 4) % 2 else out_s
        small = pygame.transform.smoothscale(surf, (max(1, w // 2), max(1, height // 2)))   # foreground: soft focus
        return pygame.transform.smoothscale(small, (w, height))

    def _hat_layer(self, look, facing):
        """The hat / crown / helm a look wears, lifted off the live HD render (with-hat minus without-hat),
        plus the HD head box it sits on: (surface, head_left, head_top, head_w) or None if bare-headed."""
        app = dict(look.get("appearance") or {})
        eq = dict(look.get("equipment") or {})
        if not (app.get("head") or any(eq.get(k) for k in ("helmet", "head", "hat"))):
            return None
        import json
        key = ("_hat", json.dumps([app.get("head"), eq.get("helmet"), eq.get("head"), eq.get("hat"),
                                   look.get("sex")], default=str), facing)
        if key in self._img:
            return self._img[key]
        out = None
        try:
            import numpy as np
            import player_hd_client as hd
            bare = dict(look, appearance=dict(app, head=None),
                        equipment={k: v for k, v in eq.items() if k not in ("helmet", "head", "hat")})
            T = 420

            def render(lk):
                pr = pygame.Surface((T * 4, T * 6), pygame.SRCALPHA)
                hd.draw_player(pr, lk.get("sex") or "male", lk.get("appearance") or {}, T * 2, T * 5, T, 0.0,
                               anim="idle", facing=facing, equipment=lk.get("equipment") or {})
                return pr
            a, b = render(look), render(bare)
            bb = b.get_bounding_rect(min_alpha=8)
            ra, rb = pygame.surfarray.array3d(a).astype(np.int16), pygame.surfarray.array3d(b).astype(np.int16)
            aa, ab = pygame.surfarray.array_alpha(a).astype(np.int16), pygame.surfarray.array_alpha(b).astype(np.int16)
            diff = (np.abs(ra - rb).max(axis=2) > 28) | (np.abs(aa - ab) > 40)
            diff &= aa > 40
            diff[:, bb.top + int(bb.h * 0.16):] = False          # only the head: never the cloak / shoulders
            if diff.sum() < 30:
                self._img[key] = None
                return None
            hat = pygame.Surface(a.get_size(), pygame.SRCALPHA)
            hat.blit(a, (0, 0))
            al = pygame.surfarray.pixels_alpha(hat)
            al[~diff] = 0
            del al
            hb = hat.get_bounding_rect(min_alpha=8)
            row = bb.top + int(bb.h * 0.045)                     # a third of the way down the head (7.5 heads tall)
            cols = np.where(ab[:, row] > 60)[0]
            hl, hw = (int(cols[0]), int(cols[-1] - cols[0] + 1)) if len(cols) > 4 else (bb.centerx - 10, 20)
            out = (hat.subsurface(hb).copy(), hb.x - hl, hb.y - bb.top, hw)
        except Exception as e:
            print("resting ox hat layer:", e)
            out = None
        self._img[key] = out
        return out

    def _wear_hat(self, look, bust, front):
        """Sit the look's hat on a painted bust, scaled to the bust's head and graded into the firelight."""
        if bust is None:
            return bust
        helm = self._helm_id(look)
        if helm:
            return self._wear_helm(helm, bust, front)
        hl = self._hat_layer(look, "s" if front else "n")
        if hl is None:
            return bust
        hat, dx, dy, hw = hl
        import numpy as np
        al = pygame.surfarray.array_alpha(bust)
        rows = np.where(al.max(axis=0) > 60)[0]
        if len(rows) < 8:
            return bust
        top = int(rows[0])
        H = bust.get_height()
        probe = min(H - 1, top + max(2, int(H * (0.15 if front else 0.08))))   # a third of the way down the head
        cols = np.where(al[:, probe] > 60)[0]
        if len(cols) < 4:
            return bust
        bw = int(cols[-1] - cols[0] + 1)
        if front:
            bw = min(bw, int(bust.get_width() * 0.34))          # long hair widens the outline: use the face
            left = int(bust.get_width() // 2 - bw // 2)
        else:
            left = int(cols[0])
        k = bw / float(max(1, hw)) * (1.32 if front else 1.12)   # painted heads carry more hair than the doll
        hs = pygame.transform.smoothscale(hat, (max(1, int(hat.get_width() * k)), max(1, int(hat.get_height() * k))))
        hs.fill((182, 156, 128, 255) if not front else (198, 168, 136, 255), special_flags=pygame.BLEND_RGBA_MULT)
        out = bust.copy()
        x = (left + bw // 2 - hs.get_width() // 2) if front else (left + int(dx * k))
        out.blit(hs, (x, top + int(dy * k) + (int(hs.get_height() * 0.10) if front else 0)))
        return out

    _HELM_TINT = {"bronze": (1.18, 0.86, 0.58), "iron": (0.82, 0.80, 0.78), "steel": (1.0, 1.0, 1.03),
                  "mithril": (0.80, 0.90, 1.22), "adamant": (0.72, 1.00, 0.78), "eclipse": (0.62, 0.56, 0.86),
                  "mythos": (1.22, 1.02, 0.62)}

    @staticmethod
    def _helm_id(look):
        eq = dict(look.get("equipment") or {})
        for k in ("helmet", "head", "hat"):
            v = eq.get(k)
            if isinstance(v, dict):
                v = v.get("id")
            if v and "helm" in str(v):
                return str(v)
        return None

    def _helm_art(self, helm, front):
        """Bust-scale painted helm (front full/open-face, or back), tinted to the item's tier and the firelight."""
        style = "back" if not front else ("med_front" if "med" in helm else "full_front")
        tier = next((t for t in self._HELM_TINT if t in helm), "steel")
        key = ("_helmart", style, tier)
        if key not in self._img:
            path = os.path.join(_TAV, "helms", "helm_%s.png" % style)
            try:
                import numpy as np
                im = pygame.image.load(path).convert_alpha()
                rgb = pygame.surfarray.pixels3d(im)
                t = np.array(self._HELM_TINT[tier]) * (np.array((1.0, 0.88, 0.72)) if front else np.array((0.92, 0.80, 0.66)))
                rgb[...] = np.clip(rgb.astype(np.float32) * t, 0, 255).astype(np.uint8)
                del rgb
                self._img[key] = im
            except Exception as e:
                print("resting ox helm art:", e)
                self._img[key] = None
        return self._img[key]

    def _wear_helm(self, helm, bust, front):
        art = self._helm_art(helm, front)
        if art is None:
            return bust
        import numpy as np
        al = pygame.surfarray.array_alpha(bust)
        rows = np.where(al.max(axis=0) > 60)[0]
        if len(rows) < 8:
            return bust
        top, H, W = int(rows[0]), bust.get_height(), bust.get_width()
        probe = min(H - 1, top + int(H * (0.10 if front else 0.12)))
        cols = np.where(al[:, probe] > 60)[0]
        if len(cols) < 4:
            return bust
        cx = int(cols[0] + cols[-1]) // 2
        hw = min(int(cols[-1] - cols[0] + 1), int(W * (0.30 if front else 0.36)))
        k = hw * (HELM_FRONT_W if front else HELM_BACK_W) / float(art.get_width())
        hs = pygame.transform.smoothscale(art, (max(1, int(art.get_width() * k)), max(1, int(art.get_height() * k))))
        out = bust.copy()
        out.blit(hs, (cx - hs.get_width() // 2, top - int(hs.get_height() * (HELM_FRONT_UP if front else HELM_BACK_UP))))
        return out

    def _has_busts(self):
        return os.path.exists(os.path.join(_TAV, "back", "front_m_hair_crop.png"))

    def _draw_you(self, surf, size, oy, sway=0):
        look = self.state.get("look")
        fx = YOU_X.get(self.view)
        if not look or fx is None:
            return
        sw, h = size
        fh = int(h * (0.88 if self.view != "table" else 0.74)) // 8 * 8
        fig = self._back_figure(look, fh)
        if fig is None:
            return
        top = oy + int(h * (0.31 if self.view != "table" else 0.40))
        surf.blit(fig, fig.get_rect(midtop=(int(sw * fx) + sway, top)))

    def _seated(self, look, height, keep):
        """Seated upper body for the table view: the front-facing HD render cut at `keep` px from the top,
        graded to the firelit painting (warm multiply, soft edges, the table's shadow on the chest)."""
        import json
        key = ("_seat", json.dumps(look, sort_keys=True, default=str), height, keep, int(time.time() * 6) % 12)
        cache = self._img.setdefault("_seatc", {})
        if key in cache:
            return cache[key]
        if len(cache) > 48:
            cache.clear()
        fig = None
        try:                                          # painted seated bust (sex + hairstyle, tinted to the look)
            fig = self._wear_hat(look, self._painted_back(look, int(height * 0.42), front=True), True)
            painted = True
        except Exception as e:
            print("resting ox seated bust:", e)
        if fig is None:                               # error fallback: the HD sprite
            painted = False
            fig = self._figure(look, height, "front")
        if fig is None:
            return None
        keep = max(1, min(fig.get_height(), keep))
        up = fig.subsurface(pygame.Rect(0, 0, fig.get_width(), keep)).copy()
        w, h = up.get_size()
        soft = up if painted else pygame.transform.smoothscale(
            pygame.transform.smoothscale(up, (max(1, int(w * 0.8)), max(1, int(h * 0.8)))), (w, h))
        if not painted:
            soft.fill((236, 196, 156, 255), special_flags=pygame.BLEND_RGBA_MULT)  # firelight grade
        shade = pygame.Surface((w, h), pygame.SRCALPHA)
        for y in range(h):                                                           # table shadow on the chest
            k = min(1.0, max(0.0, (y - h * 0.5) / (h * 0.5)))
            k = k * k * (3 - 2 * k)
            shade.fill((int(255 - 110 * k),) * 3 + (255,), pygame.Rect(0, y, w, 1))
        soft.blit(shade, (0, 0), special_flags=pygame.BLEND_RGBA_MULT)
        if painted:                                   # lap falls into the chair's shadow: no hard cut line
            fade = pygame.Surface((w, h), pygame.SRCALPHA)
            fade.fill((255, 255, 255, 255))
            for y in range(int(h * 0.80), h):
                u = min(1.0, max(0.0, (y - h * 0.80) / (h * 0.20)))
                a = int(255 * (1 - u * u * (3 - 2 * u)))
                fade.fill((255, 255, 255, a), pygame.Rect(0, y, w, 1))
            soft.blit(fade, (0, 0), special_flags=pygame.BLEND_RGBA_MULT)
        cache[key] = soft
        return soft

    def _draw_table(self, surf, img, size, oy):
        sw, sh = size
        t = self.table or {}
        me = (self.client.player or {}).get("id")
        others = [s for s in (t.get("seats") or []) if s and s.get("id") != me]
        ex, ey, ew, eh = TABLE_TOP
        rim = oy + int(ey * sh)
        busts = self._has_busts()
        for seat, (fx, head_y, hfrac) in zip(others, CHAIR_SEATS if busts else SEATS):
            top = oy + int(head_y * sh)
            if busts:                                   # painted bust sat on the chair, chair back behind it
                if abs(fx - 0.5) > 0.3:
                    hfrac *= 0.84                       # side chairs sit a touch further back
                h = int(hfrac * sh / 0.42)
                keep = int(hfrac * sh) if abs(fx - 0.5) > 0.3 else rim - top + int(0.03 * sh)
            else:
                h = int(hfrac * sh)
                keep = rim - top + int(0.03 * sh)
            cx = int(fx * sw)
            look = dict(seat.get("look") or {})
            look["_vary"] = (int(seat.get("id") or 0) * 2654435761) >> 7 & 7
            fig = self._seated(look, h, keep)
            if fig is not None:
                surf.blit(fig, (cx - fig.get_width() // 2, top))
            tag = self._font(13, True).render(f"{seat['name']}  (CL {seat.get('cl', '?')})", True, INK)
            tr = pygame.Rect(0, 0, tag.get_width() + 14, 22)
            tr.midbottom = (cx, top - 6)
            self._panel(surf, tr, 180, (120, 96, 50))
            surf.blit(tag, (tr.x + 7, tr.y + 3))
        if others and img is not None:          # the table top goes back over the sitters' chests
            mask = pygame.Surface((sw, sh), pygame.SRCALPHA)
            pygame.draw.ellipse(mask, (255, 255, 255, 255), (int(ex * sw), int(ey * sh), int(ew * sw), int(eh * sh)))
            top_art = img.convert_alpha() if pygame.display.get_surface() else img.copy().convert_alpha()
            top_art.blit(mask, (0, 0), special_flags=pygame.BLEND_RGBA_MIN)
            surf.blit(top_art, (0, oy))
        # table chat + toast state, left side
        box = pygame.Rect(18, oy + 10, 330, 100)
        self._panel(surf, box, 170)
        y = box.y + 8
        head = f"Table {t.get('id', '?')}  {t.get('taken', 1)}/{t.get('max', 4)}" + ("  locked" if t.get("locked") else "")
        surf.blit(self._font(14, True).render(head, True, GOLD), (box.x + 10, y))
        y += 22
        if not t.get("chat"):
            surf.blit(self._font(13).render("Press Enter to talk to the table.", True, MUTED), (box.x + 10, y))
        for c in (t.get("chat") or [])[-3:]:
            for row in self._wrap(f"{c['from']}: {c['text']}", self._font(13), box.w - 20)[:2]:
                surf.blit(self._font(13).render(row, True, INK), (box.x + 10, y))
                y += 17
        if self.typing is not None:
            tr = pygame.Rect(box.x, box.bottom + 6, box.w, 26)
            self._panel(surf, tr, 220)
            cur = "|" if int(time.time() * 2) % 2 else ""
            surf.blit(self._font(14).render(self.typing + cur, True, INK), (tr.x + 8, tr.y + 4))
        toast = t.get("toast")
        if toast:
            msg = f"{toast['by']} raises a toast!  {toast['left']:.0f}s"
            tt = self._font(18, True).render(msg, True, GOLD)
            r = tt.get_rect(midtop=(sw // 2, oy + 72))
            self._panel(surf, r.inflate(24, 12), 200)
            surf.blit(tt, r)

    def _draw_trophies(self, surf, size, oy):
        tr = self.trophies
        if tr is None:
            return
        f, fb = self._font(13), self._font(14, True)

        def lines_in(key, rows, title):
            r = self._r640(FRAMES[key], size, oy).inflate(-10, -12)
            dark = pygame.Surface(r.size, pygame.SRCALPHA)
            dark.fill((10, 6, 4, 150))
            surf.blit(dark, r.topleft)
            body = [p for row in rows for p in self._wrap(row, f, r.w - 6)[:3]]
            y = max(r.y + 4, r.centery - (18 + 15 * len(body)) // 2)
            t = fb.render(title, True, GOLD)
            surf.blit(t, (r.centerx - t.get_width() // 2, y))
            y += 18
            for row in rows:
                for part in self._wrap(row, f, r.w - 6)[:3]:
                    if y > r.bottom - 14:
                        return
                    im = f.render(part, True, INK)
                    surf.blit(im, (r.centerx - im.get_width() // 2, y))
                    y += 15

        crown = tr.get("crown") or {}
        cr = self._r640(FRAMES["crown"], size, oy).inflate(-14, -16)
        look = crown.get("look")
        fig = self._figure(look, int(cr.h * 0.92)) if look else None
        if fig is not None:
            back = pygame.Surface(cr.size, pygame.SRCALPHA)
            back.fill((40, 26, 16, 230))
            surf.blit(back, cr.topleft)
            surf.blit(fig, (cr.centerx - fig.get_width() // 2, cr.bottom - fig.get_height()))
        else:
            sub = [crown.get("name") or "The throne"]
            if crown.get("days") is not None:
                sub.append(f"{crown['days']} days")
            if crown.get("guild"):
                sub.append(crown["guild"])
            lines_in("crown", sub, "The Crown")
        plate = self._font(13, True).render(f"{crown.get('name') or ''}", True, (40, 26, 14))
        pr = self._r640((306, 236, 356, 247), size, oy)
        surf.blit(plate, plate.get_rect(center=pr.center))
        champs = [f"{c['rank']}. {c['name']} ({c['wins']}W)" for c in tr.get("champions") or []] or ["No champion yet"]
        lines_in("champ", champs, "Champions")
        kills = [f"{k['name']}: {k['killer']}" + (" (first!)" if k.get("first") else "") for k in tr.get("kills") or []]
        lines_in("kills", kills or ["No great kills yet"], "Great Kills")
        guilds = [f"{g['name']} ({g['members']})" + (" - Crown" if g.get("throne") else "") for g in tr.get("guilds") or []]
        lines_in("guild", guilds or ["No guilds yet"], "Guilds")
        lines_in("legend", [(tr.get("legends") or {}).get("note", "")], "Legends")

    def _draw_board(self, surf, size, oy):
        b = self.board
        if b is None:
            return
        cork = self._r640(CORK, size, oy)
        tabs = [("jobs", "Jobs"), ("requests", "Requests"), ("arena", "Arena"), ("royal", "Royal")]
        x = cork.x + 6
        for key, lab in tabs:
            r = pygame.Rect(x, cork.y + 6, 96, 26)
            pygame.draw.rect(surf, (236, 222, 186) if key == self.board_tab else (196, 176, 136), r, border_radius=4)
            pygame.draw.rect(surf, (90, 60, 30), r, 1, border_radius=4)
            t = self._font(14, True).render(lab, True, (50, 30, 16))
            surf.blit(t, t.get_rect(center=r.center))
            self.hit.append((("tab", key), r))
            x += 102
        area = pygame.Rect(cork.x + 6, cork.y + 38, cork.w - 12, cork.h - 44)
        f, fb, ink = self._font(13), self._font(14, True), (48, 30, 16)

        def note(r, title, body, buttons=()):
            pygame.draw.rect(surf, PAPER, r, border_radius=3)
            pygame.draw.rect(surf, (140, 110, 70), r, 1, border_radius=3)
            pygame.draw.circle(surf, (170, 40, 30), (r.centerx, r.y + 5), 4)
            yy = r.y + 10
            for row in self._wrap(title, fb, r.w - 12)[:2]:
                surf.blit(fb.render(row, True, ink), (r.x + 6, yy))
                yy += 17
            for row in self._wrap(body, f, r.w - 12)[:3]:
                surf.blit(f.render(row, True, ink), (r.x + 6, yy))
                yy += 15
            bx = r.x + 6
            for lab, act in buttons:
                br = pygame.Rect(bx, r.bottom - 26, self._font(13, True).size(lab)[0] + 16, 22)
                self._paper_button(surf, br, lab, act)
                bx = br.right + 6

        if self.form:
            self._draw_form(surf, area)
            return
        tab = self.board_tab
        if tab == "jobs":
            head = f"Held {len(b.get('held') or [])}/{b.get('hold_max', 3)}   Done today {b.get('done_today', 0)}/{b.get('daily_max', 6)}"
            surf.blit(fb.render(head, True, PAPER), (area.x, area.y))
            jobs = b.get("jobs") or []
            w, h = (area.w - 12) // 3, min(118, (area.h - 30) // 2)
            for i, j in enumerate(jobs[:6]):
                r = pygame.Rect(area.x + (i % 3) * (w + 6), area.y + 22 + (i // 3) * (h + 6), w, h)
                body = f"Reward {j.get('reward', 0)}c" + (f", {j['xp']} XP" if j.get("xp") else "")
                if j.get("held"):
                    body += f"   ({j.get('have', 0)}/{j.get('qty', 1)})"
                    btns = [("Turn in", ("job", "turn_in", j["id"])), ("Drop", ("job", "drop", j["id"]))]
                else:
                    btns = [("Accept", ("job", "accept", j["id"]))]
                note(r, j.get("title", "Job"), body, btns)
        elif tab == "requests":
            posts = b.get("requests") or []
            x = area.x
            for key in ("wanted", "selling", "guild", "lfg", "spar"):
                r = pygame.Rect(x, area.y, 84, 22)
                self._paper_button(surf, r, f"+ {key}", ("form", key))
                x += 90
            surf.blit(f.render(f"Posting costs {b.get('post_fee', 10)}c, lasts 48 h", True, PAPER), (x + 4, area.y + 4))
            w, h = (area.w - 12) // 3, min(118, (area.h - 36) // 2)
            for i, p in enumerate(posts[:6]):
                r = pygame.Rect(area.x + (i % 3) * (w + 6), area.y + 28 + (i // 3) * (h + 6), w, h)
                mine = p.get("player_id") == b.get("me")
                btns = ([("Cancel", ("post_act", "cancel", p["id"]))]
                        + ([] if p.get("renewed") else [("Renew", ("post_act", "renew", p["id"]))])
                        if mine else [("Report", ("post_act", "report", p["id"]))])
                body = (p.get("note") or "") + (f"  Escrow {p['escrow']}c" if p.get("escrow") else "") + f"  {p['hours_left']}h left"
                note(r, f"{p['body']}  - {p['poster']}", body, btns)
            if not posts:
                surf.blit(fb.render("No requests pinned up. Be the first.", True, PAPER), (area.x, area.y + 40))
        elif tab == "arena":
            items = b.get("arena") or []
            w = (area.w - 6 * (len(items) - 1)) // max(1, len(items))
            for i, p in enumerate(items):
                note(pygame.Rect(area.x + i * (w + 6), area.y, w, area.h // 2), p["title"], p["body"])
        elif tab == "royal":
            pr = b.get("royal")
            r = pygame.Rect(area.x + area.w // 6, area.y, area.w * 2 // 3, area.h - 40)
            pygame.draw.rect(surf, (238, 222, 176), r, border_radius=4)
            pygame.draw.rect(surf, GOLD, r, 2, border_radius=4)
            title = self._font(18, True).render("Royal Proclamation", True, (90, 20, 20))
            surf.blit(title, title.get_rect(midtop=(r.centerx, r.y + 10)))
            yy = r.y + 40
            text = (f"{pr['body']}  {pr.get('note') or ''}" if pr else "No proclamation. The Crown is quiet.")
            for row in self._wrap(text, self._font(15), r.w - 30)[:5]:
                im = self._font(15).render(row, True, ink)
                surf.blit(im, im.get_rect(midtop=(r.centerx, yy)))
                yy += 20
            if pr:
                sig = self._font(13, True).render(f"- {pr['by']}, {pr['date']}", True, (90, 20, 20))
                surf.blit(sig, sig.get_rect(midbottom=(r.centerx, r.bottom - 10)))
                pygame.draw.circle(surf, (150, 24, 24), (r.right - 30, r.bottom - 26), 14)
            if b.get("is_monarch"):
                x = area.x
                for key in (b.get("proclaim_templates") or {}):
                    br = pygame.Rect(x, area.bottom - 30, 110, 24)
                    self._paper_button(surf, br, f"Proclaim {key}", ("form", "royal:" + key))
                    x += 116

    def _draw_form(self, surf, area):
        f = self.form
        r = pygame.Rect(area.x + 40, area.y + 4, area.w - 80, area.h - 8)
        pygame.draw.rect(surf, PAPER, r, border_radius=4)
        pygame.draw.rect(surf, (120, 80, 40), r, 2, border_radius=4)
        ink = (48, 30, 16)
        kind = f["kind"]
        title = ("Royal proclamation: " + kind.split(":", 1)[1]) if kind.startswith("royal:") else f"New post: {kind}"
        surf.blit(self._font(16, True).render(title, True, ink), (r.x + 12, r.y + 10))
        y = r.y + 40
        for name in f["order"]:
            surf.blit(self._font(13, True).render(name, True, ink), (r.x + 12, y + 4))
            box = pygame.Rect(r.x + 90, y, r.w - 110, 24)
            pygame.draw.rect(surf, (252, 246, 228), box)
            pygame.draw.rect(surf, (170, 40, 30) if name == f["focus"] else (150, 120, 80), box, 1)
            cur = "|" if name == f["focus"] and int(time.time() * 2) % 2 else ""
            surf.blit(self._font(14).render(f["fields"][name] + cur, True, ink), (box.x + 6, box.y + 4))
            self.hit.append((("focus", name), box))
            y += 30
        self._paper_button(surf, pygame.Rect(r.x + 12, r.bottom - 32, 90, 24), "Pin it up", ("submit",))
        self._paper_button(surf, pygame.Rect(r.x + 110, r.bottom - 32, 80, 24), "Cancel", ("close",))
        surf.blit(self._font(12).render("Tab: next field   Enter: post   Esc: cancel", True, ink), (r.x + 200, r.bottom - 28))

    def _draw_bard(self, surf, size, oy):
        b = self.bard
        sw, sh = size
        if b is None:
            return
        box = pygame.Rect(sw - 400, oy + 60, 380, min(sh - 140, 520))
        self._panel(surf, box)
        x, y = box.x + 14, box.y + 10
        now = b.get("now") or {}
        el = now.get("elapsed", 0) + (time.time() - self.bard_at)
        surf.blit(self._font(16, True).render("Elric the bard", True, GOLD), (x, y))
        y += 24
        playing = f"Now: {now.get('title', '...')}" + (f"  (for {now['by']})" if now.get("by") else "")
        surf.blit(self._font(14).render(playing, True, INK), (x, y))
        y += 18
        frac = max(0.0, min(1.0, el / max(1, now.get("secs", 1))))
        pygame.draw.rect(surf, (60, 44, 28), (x, y, box.w - 28, 6))
        pygame.draw.rect(surf, GOLD, (x, y, int((box.w - 28) * frac), 6))
        y += 14
        if not b.get("audio_ready"):
            surf.blit(self._font(12).render("(lute recordings coming soon - words shown)", True, MUTED), (x, y))
            y += 16
        q = b.get("queue") or []
        surf.blit(self._font(13, True).render(f"Queue {len(q)}/{b.get('max', 8)}", True, GOLD), (x, y))
        y += 18
        for it in q[:3]:
            surf.blit(self._font(13).render(f"- {it.get('title')} ({it.get('by') or ''})", True, INK), (x, y))
            y += 16
        y += 6
        tip, jump = b.get("tip", 5), b.get("jump", 25)
        for s in (b.get("songs") or []) + (b.get("ballads") or []):
            if y > box.bottom - 26:
                break
            price = s.get("price", tip)
            surf.blit(self._font(13).render(f"{s['title']}  {price}c", True, INK), (x, y + 3))
            self._button(surf, pygame.Rect(box.right - 120, y, 50, 20), "Ask", ("song", s["id"], False), size=12)
            self._button(surf, pygame.Rect(box.right - 64, y, 50, 20), f"+{jump}", ("song", s["id"], True), size=12)
            y += 23

    # ---- frame ------------------------------------------------------------------------------------
    def _actions(self):
        v = self.view
        if v in ("board", "trophy", "bard"):
            return [("Back (Esc)", "back")]
        acts = []
        if v in _ORDER:
            acts += [("< A", "left"), ("D >", "right")]
        if v != "table":
            acts.append(("Talk (T)", "talk"))
        if self.seat == "bar" and not self.has_ale:
            acts.append(("Ale 5c (O)" if not self.state.get("free_left") else "Ale (O)", "order"))
        if self.has_ale:
            acts.append(("Drink (Space)", "drink"))
        acts.append(("Sit (S)" if self.seat == "bar" else "To the bar (S)", "sit"))
        if v == "table":
            acts += [("Chat (Enter)", "chat")]
            t = self.table or {}
            acts.append(("Join toast" if t.get("toast") else "Toast", "toast_join" if t.get("toast") else "toast"))
            acts.append(("Buy a round", "round"))
            if t.get("owner") == (self.client.player or {}).get("id"):
                acts.append(("Unlock" if t.get("locked") else "Lock", "lock"))
        acts += [("Board (B)", "board"), ("Trophies (W)", "trophy"), ("Bard (M)", "bard"), ("Leave (Esc)", "leave")]
        return acts

    def render(self, screen):
        self.hit = []
        sw, sh = screen.get_size()
        if self.intro is not None:
            still = self._art("bar", (sw, sw * 9 // 16))
            if self.intro.render(screen, still) is not False:
                return
        h = sw * 9 // 16
        oy = (sh - h) // 2
        size = (sw, h)
        screen.fill((8, 5, 3))
        sway = 0
        if self.tipsy():
            sway = int(6 * math.sin(time.time() * 1.3))
        img = self._art(self.view, size)
        if img is not None:
            screen.blit(img, (sway, oy))
            if sway:
                ghost = img.copy()
                ghost.set_alpha(40)
                screen.blit(ghost, (-sway * 2, oy + 2))
        tt = time.time() - self.turn_t
        if self.turn_from and tt < 0.35:
            prev = self._art(self.turn_from, size)
            if prev is not None:
                p = prev.copy()
                p.set_alpha(int(255 * (1 - tt / 0.35)))
                screen.blit(p, (sway, oy))
        if self.view == "table":
            self._draw_table(screen, img, size, oy)
        elif self.view == "trophy":
            self._draw_trophies(screen, size, oy)
        elif self.view == "board":
            self._draw_board(screen, size, oy)
        elif self.view == "bard":
            self._draw_bard(screen, size, oy)
        if self.view in YOU_X:
            self._draw_you(screen, size, oy, sway)
        # your stein
        ph = self._drink_phase()
        if self.has_ale and self.view in ("bar", "table", "left", "right"):
            e = ph * ph * (3 - 2 * ph)                     # smoothstep: stein comes up to your lips
            hgt = int(sh * (0.19 + 0.21 * e))
            cx = int(sw * (0.76 - 0.24 * e)) + sway
            base = int(sh * (0.965 + 0.22 * e))             # near the lips it runs off the bottom edge
            tk = self._tankard(hgt // 4 * 4, int(20 * e) // 4 * 4)
            if tk is not None:
                screen.blit(tk, tk.get_rect(midbottom=(cx, base)))
            else:                                          # error fallback: the drawn tankard
                self._stein(screen, cx, base, hgt // 4 * 4, tilt=int(20 * e) // 4 * 4, foam=self.sips < 2)
        # header
        lab = self._font(18, True).render(_FACE_LABEL.get(self.view, ""), True, GOLD)
        hr = pygame.Rect(16, 14, lab.get_width() + 24, 32)
        self._panel(screen, hr, 190)
        screen.blit(lab, (hr.x + 12, hr.y + 6))
        p = self.client.player or {}
        coin = self._font(15, True).render(f"{p.get('coins', 0)}c", True, GOLD)
        cr = pygame.Rect(sw - coin.get_width() - 40, 14, coin.get_width() + 24, 30)
        self._panel(screen, cr, 190)
        screen.blit(coin, (cr.x + 12, cr.y + 6))
        tier = self.state.get("tier_name")
        if tier:
            tt_ = self._font(13).render(tier, True, INK)
            screen.blit(tt_, (cr.right - tt_.get_width(), cr.bottom + 4))
        self._buff_chips(screen, 16, 54)
        if self.view not in ("board", "trophy", "bard"):
            self._dialogue(screen, sw, sh)
        # action bar
        acts = self._actions()
        f = self._font(14, True)
        widths = [f.size(a[0])[0] + 22 for a in acts]
        x = max(8, (sw - sum(widths) - 6 * (len(acts) - 1)) // 2)
        for (label, kind), w in zip(acts, widths):
            self._button(screen, pygame.Rect(x, sh - 48, w, 34), label, kind, size=14)
            x += w + 6
        # fade in
        fade = time.time() - self.opened_at
        if fade < FADE_S:
            veil = pygame.Surface((sw, sh))
            veil.fill((0, 0, 0))
            veil.set_alpha(int(255 * (1 - fade / FADE_S)))
            screen.blit(veil, (0, 0))
