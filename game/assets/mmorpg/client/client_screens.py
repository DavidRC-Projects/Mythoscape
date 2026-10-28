"""Login, help, and the modal screens.

These methods used to live on GameClient. Behavior is unchanged.
The first call copies constants from the running client module, so a
direct `python client.py` and an import see the same values.
"""


_BOUND = False
import math
import time

# Plain-English descriptions shown on the stat allocation screen when a
# beginner clicks the +/- of a skill. Keeps first-time players from guessing.
SKILL_DESCRIPTIONS = {
    "attack": "Attack: how often your melee hits land. Good if you fight with swords.",
    "strength": "Strength: how hard your melee hits land. Good for a brawler build.",
    "defence": "Defence: how often enemies miss you. Keeps you alive longer.",
    "archery": "Archery: lets you fight at range with a bow — safer for new players.",
}

# One-click stat presets. Values are the 10 bonus points per skill.
STAT_PRESETS = (
    ("Balanced", {"attack": 3, "strength": 3, "defence": 2, "archery": 2}),
    ("Warrior", {"attack": 4, "strength": 3, "defence": 3, "archery": 0}),
    ("Ranger", {"attack": 0, "strength": 2, "defence": 2, "archery": 6}),
)


def stat_alloc_layout(screen_w, n_presets=len(STAT_PRESETS)):
    """One vertical stack under the stat box: hint, preset tip, a centred preset row, then Confirm.
    Shared by draw and click so they can never disagree. Logical 1200x800 surface (window scaling
    is done by the caller), so this holds at every window size."""
    import pygame
    gap, pw = 12, 180
    row_w = n_presets * pw + (n_presets - 1) * gap
    x0 = screen_w // 2 - row_w // 2
    return {
        "hint_y": 508, "tip_y": 532, "preset_y": 556,
        "presets": [pygame.Rect(x0 + i * (pw + gap), 556, pw, 32) for i in range(n_presets)],
        "confirm": pygame.Rect(screen_w // 2 - 200, 604, 400, 44),
        "err_y": 662, "login_err_y": 692,
    }


def _shop_buy_tax(cost, rate):
    """Mirror of royal_treasury.buy_tax for display (ceil, min 1 when cost > 0)."""
    import math
    cost, rate = int(cost or 0), float(rate or 0)
    if cost <= 0 or rate <= 0:
        return 0
    return max(1, int(math.ceil(cost * rate - 1e-9)))


def _shop_sell_tax(value, rate):
    import math
    value, rate = int(value or 0), float(rate or 0)
    if value <= 0 or rate <= 0:
        return 0
    return int(math.floor(value * rate + 1e-9))


def _bind_client_globals():
    global _BOUND
    if _BOUND:
        return
    import sys
    mod = sys.modules.get("__main__")
    main_file = getattr(mod, "__file__", "") or ""
    if mod is None or not main_file.endswith("client.py") or not hasattr(mod, "WHITE"):
        import client as mod
    g = globals()
    for key, value in mod.__dict__.items():
        if key.startswith("__") or key in g:
            continue
        g[key] = value
    _BOUND = True


class ScreensMixin:
    def set_login_mode(self, mode):
        _bind_client_globals()
        if mode == self.login_mode:
            return
        self.login_mode = mode
        self.login_error = ""
        self._login_ui_geom_cache = None  # login/register mockups differ in size
        if mode == "login" and self.active_field == "char_name":
            self.active_field = "username"

    def login_layout(self):
        """Hitboxes mapped onto login_ui.png / login_ui_register.png mockups."""
        _bind_client_globals()
        geom = self._login_ui_geom()

        def R(x, y, w, h):
            return geom["map_rect"](x, y, w, h)

        if self.login_mode == "register":
            # Measured from login_ui_register.png (1024×746) + TITLE_PAD top for logo
            pad = self._register_title_pad()
            panel = R(40, pad + 8, 944, 730)
            # ~0.25" extra click padding left and right on Login
            login_tab = R(200 - 28, pad + 99, 310 + 56, 36)
            # Extra ~0.5" click padding to the right of Create Account
            register_tab = R(508, pad + 99, 410 + 55, 36)
            field_x, field_w, field_h = R(200, 0, 620, 42).x, R(200, 0, 620, 42).w, R(0, 0, 1, 42).h
            # Nudge left/down so typed text + focus bands sit inside the mockup slots
            field_x -= 40
            user_y = R(0, pad + 214, 1, 1).y - 2   # username sits a bit higher than the others
            pass_y = R(0, pad + 298, 1, 1).y + 8
            char_y = R(0, pad + 400, 1, 1).y + 8
            user_text_dx = -18  # extra left shift for typed text
            pass_text_dx = -18
            char_text_dx = -18
            # Full ornate gender buttons (match baked female-selected crops)
            male_btn = R(205, pad + 478, 295, 52)
            female_btn = R(500, pad + 478, 315, 52)
            # Full ornate banner. The label sits in the lower half, so a short
            # top-aligned strip misses clicks in the middle of the button.
            submit = R(175, pad + 548, 680, 92)
            # Match login: sit on the visible HiScores face with a generous hit area
            hiscores = R(350, pad + 650, 320, 56)
        else:
            # Measured from login_ui.png (1024×953)
            panel = R(98, 20, 827, 885)
            # ~0.25" extra click padding left and right on Login
            login_tab = R(160 - 28, 240, 340 + 56, 44)
            # Extra ~0.5" click padding to the right of Create Account
            register_tab = R(500, 240, 360 + 55, 44)
            field_x, field_w, field_h = R(166, 0, 690, 71).x, R(166, 0, 690, 71).w, R(0, 0, 1, 71).h
            user_y = R(0, 391, 1, 1).y
            pass_y = R(0, 527, 1, 1).y
            char_y = R(0, 610, 1, 1).y
            user_text_dx = pass_text_dx = char_text_dx = 0
            male_btn = R(166, 690, 330, 40)
            female_btn = R(520, 690, 330, 40)
            # Full ornate banner (gold points through the lower green). The
            # "Enter the World" label sits in the lower half; a short strip
            # ending at the text midline misses clicks in the middle.
            submit = R(150, 626, 730, 104)
            # HiScores art sits lower than the earlier crop estimate; nudge down
            # ~0.5" (~48px) on the 800px-tall window and keep a tall hit strip.
            hiscores = R(350, 768, 320, 56)

        return {
            "panel": panel,
            "login_tab": login_tab,
            "register_tab": register_tab,
            "field_x": field_x,
            "field_w": field_w,
            "field_h": field_h,
            "user_y": user_y,
            "pass_y": pass_y,
            "char_y": char_y,
            "gender_y": male_btn.y,
            "male_btn": male_btn,
            "female_btn": female_btn,
            "submit": submit,
            "hiscores": hiscores,
            "geom": geom,
            "user_text_dx": user_text_dx,
            "pass_text_dx": pass_text_dx,
            "char_text_dx": char_text_dx,
        }

    def _login_hit(self, rect, pad_x=12, pad_y=10):
        """Expand a visual control rect into a friendlier click target."""
        _bind_client_globals()
        hit = rect.inflate(pad_x * 2, pad_y * 2)
        hit.clamp_ip(pygame.Rect(0, 0, SCREEN_W, SCREEN_H))
        return hit

    def _register_title_pad(self):
        """Virtual top padding (source px) so the full logo sits on the scenic backdrop."""
        _bind_client_globals()
        return 110

    def _login_ui_geom(self):
        """Scale/letterbox the active mockup to the window; map image px → screen."""
        _bind_client_globals()
        mode = getattr(self, "login_mode", "login")
        if mode == "register":
            iw, ih = 1024, 746 + self._register_title_pad()
        else:
            iw, ih = 1024, 953
        cache = getattr(self, "_login_ui_geom_cache", None)
        if cache and cache.get("sw") == SCREEN_W and cache.get("mode") == mode:
            return cache
        scale = min(SCREEN_W / iw, SCREEN_H / ih)
        dw, dh = int(iw * scale), int(ih * scale)
        ox, oy = (SCREEN_W - dw) // 2, (SCREEN_H - dh) // 2

        def map_xy(x, y):
            return int(ox + x * scale), int(oy + y * scale)

        def map_rect(x, y, w, h):
            sx, sy = map_xy(x, y)
            return pygame.Rect(sx, sy, max(1, int(w * scale)), max(1, int(h * scale)))

        cache = {
            "sw": SCREEN_W, "sh": SCREEN_H, "scale": scale, "mode": mode,
            "ox": ox, "oy": oy, "dw": dw, "dh": dh, "iw": iw, "ih": ih,
            "map_xy": map_xy, "map_rect": map_rect,
        }
        self._login_ui_geom_cache = cache
        return cache

    def _load_login_ui(self):
        """Load login or register mockup art for the current mode."""
        _bind_client_globals()
        mode = getattr(self, "login_mode", "login")
        attr = "_login_ui_img_register" if mode == "register" else "_login_ui_img"
        img = getattr(self, attr, None)
        if img is not None:
            return img
        name = "login_ui_register.png" if mode == "register" else "login_ui.png"
        path = os.path.join(_HERE, "assets", name)
        try:
            img = pygame.image.load(path).convert()
        except Exception:
            img = None
        if img is not None and mode == "register":
            self._blank_register_gender(img)
        setattr(self, attr, img)
        return img

    def _blank_register_gender(self, img):
        """Cover the Male/Female buttons with the panel fill beside them."""
        _bind_client_globals()
        gutter = pygame.Rect(145, 468, 40, 80)
        dest = pygame.Rect(188, 468, 664, 80)
        try:
            patch = img.subsurface(gutter).copy()
        except ValueError:
            return
        old = img.get_clip()
        img.set_clip(dest)
        x = dest.x
        while x < dest.right:
            img.blit(patch, (x, dest.y))
            x += patch.get_width()
        img.set_clip(old)

    def _register_ui_female_selected(self):
        """
        Bake Female-selected into the register mockup: Female gets the same ornate
        green selected chrome as Male; Male gets the dark idle chrome.
        """
        _bind_client_globals()
        cached = getattr(self, "_login_ui_img_register_female", None)
        if cached is not None:
            return cached
        base = getattr(self, "_login_ui_img_register", None)
        if base is None:
            path = os.path.join(_HERE, "assets", "login_ui_register.png")
            try:
                base = pygame.image.load(path).convert()
            except Exception:
                return None
            self._login_ui_img_register = base

        # Full ornate gender buttons (include pointed gold ends / shadow)
        male_src = pygame.Rect(205, 478, 295, 52)
        female_src = pygame.Rect(500, 478, 315, 52)
        try:
            male_active = base.subsurface(male_src).copy()   # green selected look
            female_idle = base.subsurface(female_src).copy()  # dark idle look
        except ValueError:
            self._login_ui_img_register_female = base.copy()
            return self._login_ui_img_register_female

        img = base.copy()

        # Female selected = Male's green ornate chrome, relabeled
        female_on = pygame.transform.smoothscale(male_active, female_src.size)
        self._stamp_gender_label(female_on, "Female", selected=True)
        img.blit(female_on, female_src.topleft)

        # Male idle = Female's dark chrome, relabeled
        male_off = pygame.transform.smoothscale(female_idle, male_src.size)
        self._stamp_gender_label(male_off, "Male", selected=False)
        img.blit(male_off, male_src.topleft)

        self._login_ui_img_register_female = img
        return img

    def _stamp_gender_label(self, btn, label, selected=True):
        """Clear baked icon/text on a gender button crop and draw the correct label."""
        _bind_client_globals()
        w, h = btn.get_size()
        # Sample fill from a clean band of the chrome (avoid icon/text)
        sample = btn.subsurface(pygame.Rect(int(w * 0.72), max(4, h // 4), max(8, int(w * 0.12)), max(6, h // 2))).copy()
        # Cover icon + label region with tiled chrome texture (keeps marble look)
        wipe = pygame.Rect(int(w * 0.12), 6, int(w * 0.76), h - 12)
        for yy in range(wipe.y, wipe.bottom, sample.get_height()):
            for xx in range(wipe.x, wipe.right, sample.get_width()):
                btn.blit(sample, (xx, yy))

        if selected:
            col = (245, 236, 210)  # cream text like the Male selected mockup
            icon = (230, 200, 90)
        else:
            col = (180, 175, 160)
            icon = col

        gx = int(w * 0.22)
        gy = h // 2
        if label == "Male":
            pygame.draw.circle(btn, icon, (gx, gy + 1), 7, 2)
            pygame.draw.line(btn, icon, (gx + 5, gy - 5), (gx + 12, gy - 12), 2)
            pygame.draw.line(btn, icon, (gx + 12, gy - 12), (gx + 5, gy - 12), 2)
            pygame.draw.line(btn, icon, (gx + 12, gy - 12), (gx + 12, gy - 5), 2)
        else:
            pygame.draw.circle(btn, icon, (gx, gy - 3), 7, 2)
            pygame.draw.line(btn, icon, (gx, gy + 5), (gx, gy + 14), 2)
            pygame.draw.line(btn, icon, (gx - 5, gy + 9), (gx + 5, gy + 9), 2)

        text = self.font_login.render(label, True, col)
        # Match Male mockup: icon left, label centered in remaining space
        tx = int(w * 0.38)
        btn.blit(text, (tx, (h - text.get_height()) // 2))

    def _load_login_title_overlay(self):
        """Crownfall logo with a transparent background (no dark plate)."""
        _bind_client_globals()
        cached = getattr(self, "_login_title_overlay", None)
        if cached is not None:
            return cached
        path = os.path.join(_HERE, "assets", "login_title_crownfall.png")
        try:
            overlay = pygame.image.load(path).convert_alpha()
        except Exception:
            overlay = None
        self._login_title_overlay = overlay
        return overlay

    def _login_chrome(self, key):
        """Crop reusable widgets from the login mockup (source px), cached."""
        _bind_client_globals()
        cache = getattr(self, "_login_chrome_cache", None)
        if cache is None:
            cache = {}
            self._login_chrome_cache = cache
        if key in cache:
            return cache[key]
        ui = self._load_login_ui()
        if ui is None:
            cache[key] = None
            return None
        # Source crops measured from login_ui.png
        regions = {
            "tab_active": (164, 246, 328, 36),
            "tab_idle": (508, 246, 348, 36),
            "field": (166, 391, 690, 71),
            "submit": (168, 639, 686, 54),
            "hiscores": (380, 710, 260, 40),
            "panel_fill": (400, 320, 48, 48),
        }
        x, y, w, h = regions[key]
        piece = ui.subsurface(pygame.Rect(x, y, w, h)).copy()
        cache[key] = piece
        return piece

    def _blit_login_chrome(self, key, rect, label=None, label_color=(255, 230, 140), font=None):
        """Scale mockup chrome into rect; optional centered label (covers baked-in text)."""
        _bind_client_globals()
        piece = self._login_chrome(key)
        if piece is None:
            return False
        scaled = pygame.transform.smoothscale(piece, (rect.w, rect.h))
        self.screen.blit(scaled, rect.topleft)
        if label:
            # Soft wipe over baked mockup text, then draw ours
            wipe = rect.inflate(-int(rect.w * 0.12), -int(rect.h * 0.35))
            if wipe.w > 8 and wipe.h > 6:
                fill = self._login_chrome("panel_fill")
                if fill is not None and key in ("tab_idle", "field", "hiscores"):
                    tile = pygame.transform.smoothscale(fill, (wipe.w, wipe.h))
                    self.screen.blit(tile, wipe.topleft)
                elif key in ("tab_active", "submit"):
                    # Sample green from active chrome center
                    pygame.draw.rect(self.screen, (42, 110, 48), wipe)
                else:
                    pygame.draw.rect(self.screen, (14, 16, 20), wipe)
            f = font or self.font_login_sm
            text = f.render(label, True, label_color)
            self.screen.blit(
                text,
                (rect.centerx - text.get_width() // 2, rect.centery - text.get_height() // 2),
            )
        return True

    def handle_login_event(self, event):
        _bind_client_globals()
        if self.show_leaderboard:
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    self.show_leaderboard = False
                elif event.key == pygame.K_LEFT:
                    self.cycle_leaderboard_skill(-1)
                elif event.key == pygame.K_RIGHT:
                    self.cycle_leaderboard_skill(1)
            elif event.type == pygame.MOUSEWHEEL:
                step = -56 if event.y > 0 else 56
                cap = int(getattr(self, "leaderboard_max_scroll", 0) or 0)
                self.leaderboard_scroll = max(0, min(cap, int(getattr(self, "leaderboard_scroll", 0) or 0) + step))
            elif event.type == pygame.MOUSEBUTTONDOWN and event.button in (4, 5):
                step = -56 if event.button == 4 else 56
                cap = int(getattr(self, "leaderboard_max_scroll", 0) or 0)
                self.leaderboard_scroll = max(0, min(cap, int(getattr(self, "leaderboard_scroll", 0) or 0) + step))
            elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                self.handle_leaderboard_click(event.pos)
            return

        if event.type == pygame.KEYDOWN:
            if event.key == K_TAB:
                order = ["username", "password"] + (["char_name"] if self.login_mode == "register" else [])
                idx = order.index(self.active_field)
                self.active_field = order[(idx + 1) % len(order)]
            elif event.key == pygame.K_F2:
                self.set_login_mode("register" if self.login_mode == "login" else "login")
            elif event.key == pygame.K_F3:
                self.request_leaderboard()
            elif event.key == pygame.K_RETURN:
                self.submit_login()
            elif event.key == pygame.K_BACKSPACE:
                self.fields[self.active_field] = self.fields[self.active_field][:-1]
            elif event.unicode and event.unicode.isprintable():
                self.fields[self.active_field] += event.unicode
        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            mx, my = event.pos
            lay = self.login_layout()
            # Prefer a wider hit for Login (~0.25" left/right)
            login_hit = self._login_hit(lay["login_tab"], 14, 10)
            if login_hit.collidepoint(mx, my):
                self.set_login_mode("login")
                return
            # Prefer a wider right-side hit for Create Account (~0.5" extra)
            reg_hit = self._login_hit(lay["register_tab"], 12, 10)
            reg_hit.width += 20
            if reg_hit.collidepoint(mx, my):
                self.set_login_mode("register")
                return
            # Generous padding around the full banner so the middle of the label hits
            if self._login_hit(lay["submit"], 28, 16).collidepoint(mx, my):
                self.submit_login()
                return
            # Generous padded hit target for HiScores (visual button is easy to miss)
            hs = self._login_hit(lay["hiscores"], 28, 22)
            if hs.collidepoint(mx, my):
                self.request_leaderboard()
                return
            # Fields: pad vertically so clicking near the label/chrome still focuses
            fx, fw = lay["field_x"], lay["field_w"]
            fh = lay.get("field_h", 38)
            pad_y = 8
            if fx - 8 <= mx <= fx + fw + 8:
                if lay["user_y"] - pad_y <= my <= lay["user_y"] + fh + pad_y:
                    self.active_field = "username"
                elif lay["pass_y"] - pad_y <= my <= lay["pass_y"] + fh + pad_y:
                    self.active_field = "password"
                elif self.login_mode == "register" and lay["char_y"] - pad_y <= my <= lay["char_y"] + fh + pad_y:
                    self.active_field = "char_name"

    def request_leaderboard(self):
        _bind_client_globals()
        # Open immediately so the button feels responsive; rows fill in when the
        # server replies (or show the empty state if offline / no players yet).
        self.show_leaderboard = True
        try:
            self.net.send("LEADERBOARD", limit=50)
        except Exception:
            pass

    def cycle_leaderboard_skill(self, delta):
        _bind_client_globals()
        skills = self.leaderboard_skills or list(self.leaderboard.keys())
        if not skills:
            return
        try:
            idx = skills.index(self.leaderboard_skill)
        except ValueError:
            idx = 0
        self.leaderboard_skill = skills[(idx + delta) % len(skills)]
        self.leaderboard_scroll = 0

    def submit_login(self):
        _bind_client_globals()
        u, p, c = self.fields["username"].strip(), self.fields["password"], self.fields["char_name"].strip()
        if not u or not p:
            self.login_error = "Enter a username and password."
            return
        # If the socket is down (server was not running at launch), open a
        # fresh one now. Otherwise the Login press queues into a dead socket
        # and the player sees nothing happen even after starting the server.
        if not self.net.connected:
            self.net.reconnect()
        if self.login_mode == "register":
            if not c:
                self.login_error = "Enter a character name."
                return
            # Match the server's rule so a bad name is rejected before the
            # round trip. Letters, numbers, underscore; password length 8–128.
            import re
            if not re.fullmatch(r"[A-Za-z0-9_]{3,20}", u):
                self.login_error = "Username: 3–20 letters, numbers, or underscores."
                return
            if len(p) < 8:
                self.login_error = "Password must be at least 8 characters."
                return
            if len(p) > 128:
                self.login_error = "Password must be at most 128 characters."
                return
            import feature_flags
            self.opening_comic_pending = bool(feature_flags.USE_OPENING_COMIC)
            self.arrival_guide = True
            self.net.send("CREATE_CHARACTER", username=u, password=p, char_name=c)
        else:
            self.opening_comic_pending = False
            self.arrival_guide = False
            self.net.send("LOGIN", username=u, password=p)

    def handle_dialogue_key(self, event):
        _bind_client_globals()
        quest = self.dialogue.get("quest")
        # Arrows turn the page when there is one. Otherwise the box closes
        # and the same press walks, so a finished line does not trap movement.
        if event.key in (pygame.K_RIGHT, pygame.K_DOWN, pygame.K_KP6, pygame.K_KP2) or event.scancode in (
            pygame.KSCAN_RIGHT, pygame.KSCAN_DOWN, pygame.KSCAN_KP6, pygame.KSCAN_KP2,
        ):
            if self._dialogue_turn_page(1):
                return True
            self.dialogue = None
            return False
        if event.key in (pygame.K_LEFT, pygame.K_UP, pygame.K_KP4, pygame.K_KP8) or event.scancode in (
            pygame.KSCAN_LEFT, pygame.KSCAN_UP, pygame.KSCAN_KP4, pygame.KSCAN_KP8,
        ):
            if self._dialogue_turn_page(-1):
                return True
            self.dialogue = None
            return False
        if event.key == pygame.K_ESCAPE:
            self.dialogue = None
            self.show_shop_panel = False
        elif event.key == pygame.K_b and self.dialogue.get("housing"):
            self.net.send("HOUSING_OPEN")
        elif event.key == pygame.K_b and self.dialogue.get("shop_id"):
            self.show_shop_panel = True
            self.shop_buy_scroll = 0
            self.shop_sell_scroll = 0
            self.dialogue = None  # shop modal replaces dialogue
        elif event.key == pygame.K_b and self.dialogue.get("bank"):
            self.dialogue = None
            self.net.send("BANK_OPEN")
        elif event.key == pygame.K_s and self.dialogue.get("forge"):
            self.dialogue = None
            self.open_forge_at()
        elif (event.key == pygame.K_a and quest and quest["state"] == "offerable"
              and quest.get("type") != "gift"):
            self.net.send("QUEST_ACCEPT", quest_id=quest["quest_id"])
            self.dialogue = None
        elif event.key == pygame.K_t and quest and quest["state"] == "ready":
            self.net.send("QUEST_TURNIN", quest_id=quest["quest_id"])
            self.dialogue = None
        return True

    def _dialogue_box(self):
        """Keep the buttons above the chat strip so clicks are not stolen."""
        _bind_client_globals()
        return pygame.Rect(150, 392, MAP_W - 300, 230)

    def _dialogue_turn_page(self, step):
        pages = (self.dialogue or {}).get("pages") or []
        if not pages:
            return False
        page_i = int(self.dialogue.get("page") or 0) + int(step)
        if page_i < 0 or page_i >= len(pages):
            return False
        self.dialogue["page"] = page_i
        self.dialogue["lines"] = pages[page_i]
        return True

    def handle_dialogue_click(self, mx, my):
        _bind_client_globals()
        if self.dialogue and self.dialogue.get("castle"):
            import castle_owners_client
            castle_owners_client.click_dialogue(self, mx, my)
            return
        box = self._dialogue_box()
        if not box.collidepoint(mx, my):
            self.dialogue = None
            return
        for action, rect in (self.dialogue_btn_rects or {}).items():
            if not rect.collidepoint(mx, my):
                continue
            quest = self.dialogue.get("quest") or {}
            if action == "accept" and quest.get("state") == "offerable":
                self.net.send("QUEST_ACCEPT", quest_id=quest["quest_id"])
                self.dialogue = None
            elif action == "turnin" and quest.get("state") == "ready":
                self.net.send("QUEST_TURNIN", quest_id=quest["quest_id"])
                self.dialogue = None
            elif action == "next":
                self._dialogue_turn_page(1)
            elif action == "back":
                self._dialogue_turn_page(-1)
            elif action == "shop" and self.dialogue.get("shop_id"):
                self.show_shop_panel = True
                self.shop_buy_scroll = 0
                self.shop_sell_scroll = 0
                self.dialogue = None
            elif action == "teleport":
                self.dialogue = None
                if self.player is not None:
                    self.player["knows_teleport"] = True
                self.show_teleport = True
            elif action == "housing" and self.dialogue.get("housing"):
                self.net.send("HOUSING_OPEN")
            elif action == "bank" and self.dialogue.get("bank"):
                self.dialogue = None
                self.net.send("BANK_OPEN")
            elif action == "forge" and self.dialogue.get("forge"):
                self.dialogue = None
                self.open_forge_at()
            elif action.startswith("optx:"):
                why = next((o.get("why") for o in self.dialogue.get("options") or [] if o["id"] == action[5:]), "")
                self.chat_log.append("[!] " + (why or "You can't choose that."))
                self.chat_log = self.chat_log[-8:]
            elif action.startswith("opt:") and self.dialogue.get("npc_id") == "court_event":
                self.net.send("COURT_CHOOSE", choice=action[4:])
                self.dialogue = None
            elif action.startswith("opt:"):
                self.net.send("NPC_OPTION", npc_id=self.dialogue["npc_id"], option=action[4:])
            elif action == "persuade" and self.dialogue.get("persuade"):
                self.net.send("PERSUADE", npc_id=self.dialogue["npc_id"])
            elif action == "close":
                self.dialogue = None
            return

    def handle_stat_alloc_event(self, event):
        _bind_client_globals()
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_RETURN:
                self.submit_stat_alloc()
            elif event.key == pygame.K_ESCAPE:
                # Stay on this screen — must allocate before playing
                self.stat_alloc_error = "Spend all 10 points, then click Confirm."
        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            mx, my = event.pos
            for key, rect in self.stat_alloc_rects.items():
                if not rect.collidepoint(mx, my):
                    continue
                skill, action = key
                if skill == "gender":
                    self.stat_gender = action
                    self.stat_alloc_error = ""
                    return
                if action == "plus" and self.remaining_stat_points() > 0:
                    self.stat_alloc[skill] += 1
                    self.stat_skill_desc = skill
                    self.stat_alloc_error = ""
                elif action == "minus" and self.stat_alloc[skill] > 0:
                    self.stat_alloc[skill] -= 1
                    self.stat_skill_desc = skill
                    self.stat_alloc_error = ""
                return
            for rect, points in self.stat_preset_rects:
                if rect.collidepoint(mx, my):
                    self.stat_alloc = dict(points)
                    self.stat_skill_desc = ""
                    self.stat_alloc_error = ""
                    return
            confirm = stat_alloc_layout(SCREEN_W)["confirm"]
            if confirm.collidepoint(mx, my):
                self.submit_stat_alloc()

    def draw_stat_alloc(self):
        _bind_client_globals()
        title = self.font_big.render("Choose your starting stats", True, WHITE)
        lay = stat_alloc_layout(SCREEN_W)
        self.screen.blit(title, (SCREEN_W // 2 - title.get_width() // 2, 80))
        name = (self.player or {}).get("name", "Adventurer")
        sub = self.font.render(f"Welcome, {name}. Distribute 10 points.", True, YELLOW)
        self.screen.blit(sub, (SCREEN_W // 2 - sub.get_width() // 2, 120))

        left = self.remaining_stat_points()
        pts = self.font_big.render(f"Points left: {left}", True, GREEN if left == 0 else WHITE)
        self.screen.blit(pts, (SCREEN_W // 2 - pts.get_width() // 2, 156))

        body = self.font.render("Body", True, WHITE)
        self.screen.blit(body, (340, 198))
        male = pygame.Rect(430, 190, 200, 40)
        female = pygame.Rect(650, 190, 200, 40)
        for rect, label, selected in (
            (male, "Male", self.stat_gender == "male"),
            (female, "Female", self.stat_gender == "female"),
        ):
            pygame.draw.rect(self.screen, (45, 100, 55) if selected else (28, 30, 38), rect)
            pygame.draw.rect(self.screen, GREEN if selected else PANEL_LINE, rect, 2)
            ctxt = self.font.render(label, True, WHITE if selected else GREY)
            self.screen.blit(ctxt, (rect.centerx - ctxt.get_width() // 2, rect.centery - ctxt.get_height() // 2))

        box = pygame.Rect(340, 248, 520, 250)
        pygame.draw.rect(self.screen, (18, 20, 28), box)
        pygame.draw.rect(self.screen, (120, 190, 255), box, 2)

        self.stat_alloc_rects = {
            ("gender", "male"): male,
            ("gender", "female"): female,
        }
        y = box.y + 24
        for skill in ("attack", "strength", "defence", "archery"):
            base = self.stat_alloc_base.get(skill, 1)
            bonus = self.stat_alloc[skill]
            final = base + bonus
            label = self.font.render(f"{skill.title()}:  {base}  ->  {final}", True, WHITE)
            self.screen.blit(label, (box.x + 28, y + 8))

            minus = pygame.Rect(box.x + 320, y, 44, 36)
            plus = pygame.Rect(box.x + 380, y, 44, 36)
            pygame.draw.rect(self.screen, (50, 40, 40), minus)
            pygame.draw.rect(self.screen, PANEL_LINE, minus, 1)
            pygame.draw.rect(self.screen, (40, 55, 50), plus)
            pygame.draw.rect(self.screen, PANEL_LINE, plus, 1)
            self.screen.blit(self.font_big.render("-", True, WHITE), (minus.x + 16, minus.y + 2))
            self.screen.blit(self.font_big.render("+", True, WHITE), (plus.x + 14, plus.y + 2))
            self.stat_alloc_rects[(skill, "minus")] = minus
            self.stat_alloc_rects[(skill, "plus")] = plus

            spent = self.font_small.render(f"+{bonus}", True, YELLOW if bonus else GREY)
            self.screen.blit(spent, (box.x + 440, y + 10))
            y += 58

        # Plain-English description of the highlighted/last-touched skill
        self.stat_skill_desc = getattr(self, "stat_skill_desc", "")
        desc = SKILL_DESCRIPTIONS.get(self.stat_skill_desc, "")
        if desc:
            d = self.font_small.render(desc, True, (200, 190, 170))
            self.screen.blit(d, (SCREEN_W // 2 - d.get_width() // 2, 486))

        hint = self.font_small.render(
            "Each point raises that skill by 1 level. Confirm when all 10 are spent.",
            True, GREY,
        )
        self.screen.blit(hint, (SCREEN_W // 2 - hint.get_width() // 2, lay["hint_y"]))
        tip = self.font_small.render("Not sure? Pick a preset - you can train any skill later.", True, (200, 190, 170))
        self.screen.blit(tip, (SCREEN_W // 2 - tip.get_width() // 2, lay["tip_y"]))

        # One-click presets in a row under the tip; (rect, points) pairs since pygame.Rect is unhashable.
        self.stat_preset_rects = []
        for (name, points), pr in zip(STAT_PRESETS, lay["presets"]):
            active = dict(self.stat_alloc) == points
            pygame.draw.rect(self.screen, (45, 100, 55) if active else (30, 32, 42), pr, border_radius=6)
            pygame.draw.rect(self.screen, GREEN if active else PANEL_LINE, pr, 1, border_radius=6)
            label = self.font_small.render(name, True, WHITE if active else GREY)
            self.screen.blit(label, (pr.centerx - label.get_width() // 2,
                                     pr.centery - label.get_height() // 2))
            self.stat_preset_rects.append((pr, points))

        confirm = lay["confirm"]
        ready = left == 0
        pygame.draw.rect(self.screen, (45, 100, 55) if ready else (40, 42, 50), confirm)
        pygame.draw.rect(self.screen, GREEN if ready else PANEL_LINE, confirm, 2)
        ctxt = self.font.render("Confirm & Enter World", True, WHITE if ready else GREY)
        self.screen.blit(ctxt, (confirm.x + (confirm.w - ctxt.get_width()) // 2,
                                confirm.y + (confirm.h - ctxt.get_height()) // 2))

        if self.stat_alloc_error:
            err = self.font.render(self.stat_alloc_error, True, RED)
            self.screen.blit(err, (SCREEN_W // 2 - err.get_width() // 2, lay["err_y"]))
        if self.login_error:
            err = self.font.render(self.login_error, True, RED)
            self.screen.blit(err, (SCREEN_W // 2 - err.get_width() // 2, lay["login_err_y"]))

    def _load_login_backdrop(self):
        """Load and cache the adventurous title-screen art."""
        _bind_client_globals()
        if hasattr(self, "_login_bg") and self._login_bg is not None:
            return self._login_bg
        path = os.path.join(_HERE, "assets", "login_backdrop.png")
        try:
            img = pygame.image.load(path).convert()
            if img.get_size() != (SCREEN_W, SCREEN_H):
                img = pygame.transform.smoothscale(img, (SCREEN_W, SCREEN_H))
            self._login_bg = img
        except Exception:
            self._login_bg = None
        return self._login_bg

    def draw_login_backdrop(self, t):
        """Adventurous fantasy title art with soft vignette for the login card."""
        _bind_client_globals()
        bg = self._load_login_backdrop()
        if bg is not None:
            self.screen.blit(bg, (0, 0))
            # Gentle breathing light over the horizon / path (keeps the scene alive)
            if getattr(self, "_login_wash", None) is None or self._login_wash.get_size() != (SCREEN_W, SCREEN_H):
                self._login_wash = pygame.Surface((SCREEN_W, SCREEN_H), pygame.SRCALPHA)
            wash = self._login_wash
            wash.fill((0, 0, 0, 0))
            pulse = 0.5 + 0.5 * math.sin(t * 0.7)
            alpha = int(10 + 8 * pulse)
            pygame.draw.ellipse(
                wash, (255, 190, 110, alpha),
                (-80, SCREEN_H // 2 - 40, SCREEN_W + 160, SCREEN_H // 2 + 80),
            )
            self.screen.blit(wash, (0, 0))
        else:
            # Fallback gradient if the art file is missing
            for i in range(SCREEN_H):
                u = i / SCREEN_H
                r = int(18 + 40 * u)
                g = int(28 + 50 * u)
                b = int(40 + 20 * u)
                pygame.draw.line(self.screen, (r, g, b), (0, i), (SCREEN_W, i))

        # Soft vignette so the center login card stays readable
        if not hasattr(self, "_login_vignette"):
            v = pygame.Surface((SCREEN_W, SCREEN_H), pygame.SRCALPHA)
            for i in range(110):
                a = int(110 * (1 - i / 110) ** 1.4)
                pygame.draw.rect(v, (0, 0, 0, a), (i, i, SCREEN_W - 2 * i, SCREEN_H - 2 * i), 1)
            self._login_vignette = v
        self.screen.blit(self._login_vignette, (0, 0))

    def draw_login(self):
        """Draw login/register from mockup art (pixel-identical to design images)."""
        _bind_client_globals()
        self.draw_login_backdrop(time.time())
        ui = self._load_login_ui()
        geom = self._login_ui_geom()
        if ui is not None:
            if self.login_mode == "register":
                # Form card only. The mockup's side strips are a different landscape
                # than the live backdrop, so they stay out of the crop.
                pad = self._register_title_pad()
                body_y0 = 78  # below clipped title / dark plate in source
                src = pygame.Rect(58, body_y0, 896, ui.get_height() - body_y0)
                src.w = min(src.w, ui.get_width() - src.x)
                src.h = min(src.h, ui.get_height() - src.y)
                panel_img = ui.subsurface(src)
                dw = max(1, int(src.w * geom["scale"]))
                dh = max(1, int(src.h * geom["scale"]))
                scaled = self._scaled_login_piece(("register-body", dw, dh), panel_img, (dw, dh))
                px = geom["ox"] + int(src.x * geom["scale"])
                py = geom["oy"] + int((pad + body_y0) * geom["scale"])
                self.screen.blit(scaled, (px, py))
                title = self._load_login_title_overlay()
                if title is not None:
                    gap = max(4, int(8 * geom["scale"]))
                    max_h = max(48, py - geom["oy"] - gap)
                    max_w = int(geom["dw"] * 0.78)
                    tw, th = self._fit_login_title(title, max_w, max_h)
                    tscaled = self._scaled_login_piece(("register-title", tw, th), title, (tw, th))
                    tx = px + (dw - tw) // 2
                    ty = max(geom["oy"] + 2, py - th - gap)
                    self.screen.blit(tscaled, (tx, ty))
            else:
                # Login form below the title plate so scenery shows behind the logo
                body_y0 = 128  # include the top gold rail; the old name above it is painted out
                src = pygame.Rect(98, body_y0, 873, ui.get_height() - body_y0)
                src.w = min(src.w, ui.get_width() - src.x)
                src.h = min(src.h, ui.get_height() - src.y)
                panel_img = self._login_panel(ui, src)
                dw = max(1, int(src.w * geom["scale"]))
                dh = max(1, int(src.h * geom["scale"]))
                scaled = self._scaled_login_piece(("login-body", dw, dh), panel_img, (dw, dh))
                px = geom["ox"] + int(src.x * geom["scale"])
                py = geom["oy"] + int(src.y * geom["scale"])
                self.screen.blit(scaled, (px, py))
                title = self._load_login_title_overlay()
                if title is not None:
                    gap = max(6, int(10 * geom["scale"]))
                    max_h = max(48, py - gap - 4)
                    max_w = int(dw * 0.92)
                    tw, th = self._fit_login_title(title, max_w, max_h)
                    tscaled = self._scaled_login_piece(("login-title", tw, th), title, (tw, th))
                    tx = px + (dw - tw) // 2
                    ty = max(4, py - th - gap)
                    self.screen.blit(tscaled, (tx, ty))

        lay = self.login_layout()

        if self.login_mode == "register":
            # Gender state is baked into the register mockup (no overlay buttons)
            self._draw_login_field_text(
                "username", lay["user_y"], lay["field_x"], lay["field_w"], lay["field_h"], mask=False,
            )
            self._draw_login_field_text(
                "password", lay["pass_y"], lay["field_x"], lay["field_w"], lay["field_h"], mask=True,
            )
            self._draw_login_field_text(
                "char_name", lay["char_y"], lay["field_x"], lay["field_w"], lay["field_h"], mask=False,
            )
        else:
            self._draw_login_field_text(
                "username", lay["user_y"], lay["field_x"], lay["field_w"], lay["field_h"], mask=False,
            )
            self._draw_login_field_text(
                "password", lay["pass_y"], lay["field_x"], lay["field_w"], lay["field_h"], mask=True,
            )

        if self.login_error:
            err = self.font_small.render(self.login_error, True, (255, 200, 180))
            banner = pygame.Rect(
                lay["panel"].x + 40, max(lay["panel"].y + 8, lay["hiscores"].y - 36),
                lay["panel"].w - 80, 28,
            )
            self._fill_octagon(self.screen, (70, 32, 28), banner, cut=6)
            self._stroke_octagon(self.screen, (200, 80, 70), banner, cut=6, width=1)
            self.screen.blit(err, (banner.centerx - err.get_width() // 2, banner.y + 5))

        hint = self.font_tiny.render(
            "New character: the opening plays once. Then find Elder Miriam in the northwest cottage.",
            True, (210, 200, 170),
        )
        self.screen.blit(hint, ((SCREEN_W - hint.get_width()) // 2, SCREEN_H - 22))

        if self.show_leaderboard:
            self.draw_leaderboard_modal()

    def _reveal_login_backdrop(self, panel):
        """Hide mockup scenery outside the gold frame so the live backdrop shows.

        The frame is a closed border. Only pixels that can be reached from the
        crop edge without crossing that border are cleared, so the panel and
        its buttons stay intact.
        """
        import numpy as np
        from collections import deque

        w, h = panel.get_size()
        rgb = pygame.surfarray.array3d(panel)
        r = rgb[:, :, 0].astype(np.int16)
        gch = rgb[:, :, 1].astype(np.int16)
        b = rgb[:, :, 2].astype(np.int16)
        gold = (r > 80) & (gch > 52) & (r > b + 12) & (gch + 8 > b)

        def flood(mask, seeds):
            seen = np.zeros((w, h), dtype=bool)
            q = deque()
            for x, y in seeds:
                if 0 <= x < w and 0 <= y < h and mask[x, y] and not seen[x, y]:
                    seen[x, y] = True
                    q.append((x, y))
            while q:
                x, y = q.popleft()
                for nx, ny in ((x - 1, y), (x + 1, y), (x, y - 1), (x, y + 1)):
                    if 0 <= nx < w and 0 <= ny < h and mask[nx, ny] and not seen[nx, ny]:
                        seen[nx, ny] = True
                        q.append((nx, ny))
            return seen

        midy, midx = h // 2, w // 2
        xs = np.flatnonzero(gold[:, midy])
        ys = np.flatnonzero(gold[midx, :])
        if xs.size == 0 or ys.size == 0:
            return
        frame = flood(
            gold,
            (
                (int(xs[0]), midy),
                (int(xs[-1]), midy),
                (midx, int(ys[0])),
                (midx, int(ys[-1])),
            ),
        )
        edge = [(x, 0) for x in range(w)] + [(x, h - 1) for x in range(w)]
        edge += [(0, y) for y in range(h)] + [(w - 1, y) for y in range(h)]
        outside = flood(~gold, edge)
        for _ in range(12):
            dil = outside.copy()
            dil[1:, :] |= outside[:-1, :]
            dil[:-1, :] |= outside[1:, :]
            dil[:, 1:] |= outside[:, :-1]
            dil[:, :-1] |= outside[:, 1:]
            hit = gold & ~frame & dil & ~outside
            if not hit.any():
                break
            outside |= hit
        alpha = pygame.surfarray.pixels_alpha(panel)
        alpha[outside] = 0
        del alpha

    def _login_panel(self, ui, src):
        """Crop of the login frame, with the old side scenery removed. Cached."""
        cache = getattr(self, "_login_art_cache", None)
        if cache is None:
            cache = {}
            self._login_art_cache = cache
        key = ("login-panel", src.x, src.y, src.w, src.h)
        found = cache.get(key)
        if found is not None:
            return found
        panel = ui.subsurface(src).copy().convert_alpha()
        self._reveal_login_backdrop(panel)
        cache[key] = panel
        return panel

    def _fit_login_title(self, title, max_w, max_h):
        """Scale the wordmark into the gap above the form without covering it."""
        tw, th = title.get_size()
        if tw < 1 or th < 1:
            return 1, 1
        scale = min(max(1, max_w) / tw, max(1, max_h) / th)
        return max(1, int(tw * scale)), max(1, int(th * scale))

    def _scaled_login_piece(self, key, image, size):
        """Keep a scaled login plate so the title screen does not resample every frame."""
        _bind_client_globals()
        cache = getattr(self, "_login_art_cache", None)
        if cache is None:
            cache = {}
            self._login_art_cache = cache
        size = (max(1, int(size[0])), max(1, int(size[1])))
        found = cache.get(key)
        if found is not None and found.get_size() == size:
            return found
        scaled = pygame.transform.smoothscale(image, size)
        cache[key] = scaled
        return scaled

    def _swap_register_gender_art(self, lay):
        """Deprecated: gender is baked into the register mockup via _load_login_ui()."""
        _bind_client_globals()
        return

    def _draw_login_field_text(self, key, y, x, w, h, mask=False):
        """Overlay typed characters on the mockup input slots."""
        _bind_client_globals()
        active = self.active_field == key
        text = self.fields.get(key, "")
        show = ("•" * len(text)) if mask and text else text
        if not show and not active:
            return
        # Create Account mockup: sit text just after the icon, slightly lower in the slot
        lay = self.login_layout()
        dx_map = {"username": "user_text_dx", "password": "pass_text_dx", "char_name": "char_text_dx"}
        dx = lay.get(dx_map.get(key, ""), 0)
        if self.login_mode == "register":
            text_x = x + max(34, int(w * 0.075)) + dx
            text_y_pad = 2
        else:
            text_x = x + max(48, int(w * 0.105)) + dx
            text_y_pad = 0
        if show:
            # Wipe from the icon gutter across the field so placeholders are fully covered
            wipe_x = x + max(28, int(w * 0.055)) + dx if self.login_mode == "register" else x + max(36, int(w * 0.07)) + dx
            wipe = pygame.Rect(wipe_x, y + 4 + text_y_pad, max(8, w - (wipe_x - x) - 12), max(10, h - 8 - text_y_pad))
            # Same dark slot fill as the password field interior (avoids mismatched samples)
            fill = (7, 15, 26) if self.login_mode == "register" else (14, 14, 18)
            pygame.draw.rect(self.screen, fill, wipe)
            txt = self.font.render(show, True, (235, 230, 220))
            self.screen.blit(txt, (text_x + 2, y + text_y_pad + (h - txt.get_height()) // 2))
        if active and int(time.time() * 2) % 2 == 0:
            cx = text_x + 2 + (self.font.size(show)[0] if show else 0)
            pygame.draw.line(
                self.screen, (235, 230, 220),
                (cx, y + 6 + text_y_pad), (cx, y + h - 6), 2,
            )

    def _fill_octagon(self, surf, color, rect, cut=8):
        _bind_client_globals()
        pygame.draw.polygon(surf, color, self._octagon(rect, cut))

    def _stroke_octagon(self, surf, color, rect, cut=8, width=2):
        _bind_client_globals()
        pygame.draw.polygon(surf, color, self._octagon(rect, cut), width)

    def draw_world_map_modal(self):
        _bind_client_globals()
        box = self.world_map_view_rect()
        canvas = self.world_map_canvas_rect()
        pygame.draw.rect(self.screen, (14, 18, 26), box, border_radius=8)
        pygame.draw.rect(self.screen, (120, 170, 220), box, 2, border_radius=8)
        in_realm = bool(self.dungeon and self.dungeon.get("id") == "castle_realm")
        title = self.font_big.render(
            "Castle Realm Map" if in_realm else "World Map", True, WHITE,
        )
        self.screen.blit(title, (box.x + 20, box.y + 14))
        self.screen.blit(
            self.font_small.render(
                "Scroll / drag to pan  ·  Click a tile to walk there  ·  Esc closes",
                True, GREY,
            ),
            (box.x + 20, box.y + 46),
        )

        self.clamp_world_map_scroll()
        scale = self.world_map_scale
        ox, oy = self.world_map_scroll
        view_w = canvas.w // scale
        view_h = canvas.h // scale

        pygame.draw.rect(self.screen, (10, 12, 18), canvas)
        pygame.draw.rect(self.screen, (70, 90, 120), canvas, 1)

        for ty in range(view_h + 1):
            wy = oy + ty
            if wy < 0 or wy >= self.world_h or wy >= len(self.tiles):
                continue
            row = self.tiles[wy]
            for tx in range(view_w + 1):
                wx = ox + tx
                if wx < 0 or wx >= self.world_w or wx >= len(row):
                    continue
                col = self.minimap_tile_color(row[wx])
                if in_realm and self.dungeon.get("plane") == "realm":
                    try:
                        import castle_realm_renderer as _crr
                        rows = _crr.REALM_ROWS
                        if 0 <= wy < len(rows) and 0 <= wx < len(rows[wy]):
                            ch = rows[wy][wx]
                            if ch == "s":
                                col = (220, 175, 55)
                            elif ch == "A":
                                col = (165, 150, 130)
                    except Exception:
                        pass
                pygame.draw.rect(
                    self.screen, col,
                    (canvas.x + tx * scale, canvas.y + ty * scale, scale, scale),
                )

        prev_clip = self.screen.get_clip()
        self.screen.set_clip(canvas)

        # Destination pins with names; store hover rects so clicking a pin walks exactly there
        self.world_map_pin_rects = []
        mouse = pygame.mouse.get_pos()
        hover_pin = None
        if in_realm:
            # Castle landmarks (teleport landings) — walk-to on the realm plane.
            from content import TELEPORT_DESTINATIONS
            map_dests = [
                {**d, "kind": d.get("kind") or "place"}
                for d in TELEPORT_DESTINATIONS
                if d.get("where") == "castle"
            ]
            home = None
        else:
            map_dests = [d for d in TRAVEL_DESTINATIONS if d.get("where") != "castle"]
            home = self._home_destination() if hasattr(self, "_home_destination") else None
            if home:
                map_dests = [home] + [d for d in map_dests if d.get("id") != "home"]
        for dest in map_dests:
            dx = dest["x"] - ox
            dy = dest["y"] - oy
            if 0 <= dx <= view_w and 0 <= dy <= view_h:
                px = canvas.x + dx * scale + scale // 2
                py = canvas.y + dy * scale + scale // 2
                if dest.get("id") == "castle_realm":
                    self._draw_castle_realm_pin(px, py, short=False)
                elif dest.get("home") or dest.get("id") == "home":
                    pulse = 0.5 + 0.5 * math.sin(time.time() * 2.4)
                    pygame.draw.circle(self.screen, (40, 90, 50), (px, py), 7)
                    pygame.draw.circle(self.screen, (90, 220, 120), (px, py), 5 + int(pulse))
                    pygame.draw.circle(self.screen, (220, 255, 220), (px, py), 2)
                elif dest["kind"] == "monster":
                    mdef = MONSTERS.get(dest.get("monster") or "", {})
                    col = self.monster_threat_color(mdef.get("level", 1))
                    pygame.draw.circle(self.screen, col, (px, py), 4)
                    pygame.draw.circle(self.screen, (20, 20, 20), (px, py), 4, 1)
                else:
                    pygame.draw.rect(self.screen, (255, 220, 120), (px - 2, py - 2, 5, 5))
                    pygame.draw.rect(self.screen, (60, 40, 10), (px - 2, py - 2, 5, 5), 1)
                label = dest["label"]
                if dest["kind"] == "monster":
                    label = f"{label} (Lv {MONSTERS.get(dest.get('monster') or '', {}).get('level', 1)})"
                pin_rect = pygame.Rect(px - 5, py - 5, 10, 10).inflate(6, 6)
                self.world_map_pin_rects.append((pin_rect, dest))
                # Label under the pin, brighter when hovered
                lab_col = (160, 255, 180) if dest.get("home") or dest.get("id") == "home" else (
                    (255, 240, 200) if pin_rect.collidepoint(mouse) else (215, 205, 180)
                )
                lab = self.font_tiny.render(label, True, lab_col)
                bg = pygame.Surface((lab.get_width() + 8, lab.get_height() + 4), pygame.SRCALPHA)
                bg.fill((10, 12, 18, 170))
                lx = min(max(canvas.x + 2, px - lab.get_width() // 2), canvas.right - lab.get_width() - 2)
                ly = min(max(canvas.y + 2, py + 7), canvas.bottom - lab.get_height() - 2)
                self.screen.blit(bg, (lx - 4, ly - 2))
                self.screen.blit(lab, (lx, ly))
                if pin_rect.collidepoint(mouse):
                    hover_pin = dest

        # Player marker + direction/edge arrow so you always know where you are
        if self.player:
            px, py = self.player_xy()
            dx, dy = px - ox, py - oy
            if 0 <= dx <= view_w and 0 <= dy <= view_h:
                mx = canvas.x + dx * scale + scale // 2
                my = canvas.y + dy * scale + scale // 2
                pulse = 0.5 + 0.5 * math.sin(time.time() * 3)
                halo = pygame.Surface((24, 24), pygame.SRCALPHA)
                pygame.draw.circle(halo, (255, 90, 70, int(40 + 50 * pulse)), (12, 12), 10 + int(2 * pulse))
                self.screen.blit(halo, (mx - 12, my - 12))
                pygame.draw.circle(self.screen, (40, 40, 40), (mx, my), 6)
                pygame.draw.circle(self.screen, (255, 80, 70), (mx, my), 5)
                pygame.draw.circle(self.screen, (255, 220, 200), (mx, my), 2)
            else:
                self._map_edge_arrow(canvas, dx, dy, (255, 90, 70), "You")
            # Off-screen home arrow so the deed is never lost
            if home:
                hdx, hdy = home["x"] - ox, home["y"] - oy
                if not (0 <= hdx <= view_w and 0 <= hdy <= view_h):
                    self._map_edge_arrow(canvas, hdx, hdy, (90, 220, 120), "Home")

        self.screen.set_clip(prev_clip)

        # Hover tooltip: what this pin is + how to walk there
        if hover_pin is not None:
            tip = f"Click to walk to {hover_pin['label']}"
            t = self.font_tiny.render(tip, True, (255, 240, 200))
            tw = t.get_width() + 14
            tbox = pygame.Rect(mouse[0] + 12, mouse[1] + 14, tw, t.get_height() + 8)
            tbox.clamp_ip(box)
            bg = pygame.Surface(tbox.size, pygame.SRCALPHA)
            bg.fill((16, 20, 28, 220))
            self.screen.blit(bg, tbox.topleft)
            pygame.draw.rect(self.screen, (120, 170, 220), tbox, 1, border_radius=4)
            self.screen.blit(t, (tbox.x + 7, tbox.y + 4))

        # Recenter-on-player button
        self.world_map_recenter_rect = pygame.Rect(box.right - 108, box.y + 8, 92, 26)
        rb = self.world_map_recenter_rect
        pygame.draw.rect(self.screen, (40, 60, 90), rb, border_radius=6)
        pygame.draw.rect(self.screen, (120, 170, 220), rb, 1, border_radius=6)
        rt = self.font_tiny.render("Center on me", True, WHITE)
        self.screen.blit(rt, (rb.centerx - rt.get_width() // 2, rb.centery - rt.get_height() // 2))

        foot = self.font_tiny.render(
            "Click a named pin to walk there  ·  Scroll / drag to pan  ·  Esc closes  ·  Press M for Travel list",
            True, (140, 138, 120),
        )
        self.screen.blit(foot, (box.x + 20, box.bottom - 28))

    def _map_edge_arrow(self, canvas, dx, dy, color, label):
        """Arrow at the canvas edge pointing toward an off-screen map point."""
        cx, cy = canvas.center
        if dx == 0 and dy == 0:
            return
        margin = 26
        half_w, half_h = canvas.w / 2 - margin, canvas.h / 2 - margin
        k = min(half_w / abs(dx) if dx else 1e9, half_h / abs(dy) if dy else 1e9)
        ax, ay = cx + dx * k, cy + dy * k
        ang = math.atan2(dy, dx)
        size = 13
        tip = (ax + math.cos(ang) * size, ay + math.sin(ang) * size)
        left = (ax + math.cos(ang + 2.5) * size, ay + math.sin(ang + 2.5) * size)
        right = (ax + math.cos(ang - 2.5) * size, ay + math.sin(ang - 2.5) * size)
        pygame.draw.polygon(self.screen, color, (tip, left, right))
        pygame.draw.polygon(self.screen, (20, 20, 20), (tip, left, right), 2)
        lab = self.font_tiny.render(label, True, color)
        bg = pygame.Surface((lab.get_width() + 8, lab.get_height() + 4), pygame.SRCALPHA)
        bg.fill((10, 12, 18, 180))
        lx = int(max(canvas.x + 4, min(canvas.right - lab.get_width() - 4, ax - lab.get_width() / 2)))
        ly = int(max(canvas.y + 4, min(canvas.bottom - lab.get_height() - 4, ay - lab.get_height() / 2)))
        self.screen.blit(bg, (lx - 4, ly - 2))
        self.screen.blit(lab, (lx, ly))

    def _shop_bag_tip(self):
        """One-line hint naming the first unowned container this shop sells."""
        from content import ITEMS
        for item_id, _info in (self.shop.get("stock") or {}).items():
            item = ITEMS.get(item_id) or {}
            if item.get("unique") and not self.owns_shop_item(item_id):
                verb = "Holds" if item_id == "arrow_quiver" else "Frees up your bag"
                return f"{verb}: buy the {item.get('name', item_id)} once — it's permanent"
        return None

    def draw_travel_modal(self):
        _bind_client_globals()
        box = pygame.Rect(140, 40, 720, 580)
        pygame.draw.rect(self.screen, (16, 20, 28), box)
        pygame.draw.rect(self.screen, (120, 170, 220), box, 2)
        in_realm = bool(self.dungeon and self.dungeon.get("id") == "castle_realm")
        title = self.font_big.render(
            "Travel · Castle Realm" if in_realm else "Travel", True, WHITE,
        )
        self.screen.blit(title, (box.x + 20, box.y + 12))
        self.screen.blit(
            self.font_small.render(
                "Click a destination to walk there  ·  Scroll / drag bar  ·  Esc closes",
                True, GREY,
            ),
            (box.x + 20, box.y + 46),
        )

        places = self._travel_places() if hasattr(self, "_travel_places") else [
            d for d in TRAVEL_DESTINATIONS if d["kind"] == "place"
        ]
        monsters = [] if in_realm else [d for d in TRAVEL_DESTINATIONS if d["kind"] == "monster"]
        self.travel_btn_rects = []

        # Leave room for the scrollbar on the right edge of the panel
        if in_realm:
            col_w = box.w - 72
            left_x = box.x + 20
            right_x = None
        else:
            col_w = (box.w - 72) // 2
            left_x = box.x + 20
            right_x = box.x + 36 + col_w
        hdr_y = box.y + 74
        self.screen.blit(
            self.font.render("Castles & landmarks" if in_realm else "Places", True, (255, 220, 140)),
            (left_x, hdr_y),
        )
        if right_x is not None:
            self.screen.blit(self.font.render("Monsters", True, (255, 160, 140)), (right_x, hdr_y))

        row_h = 48
        list_top = hdr_y + 28
        list_bottom = box.bottom - 36
        view_h = max(40, list_bottom - list_top)
        content_h = max(len(places), len(monsters)) * row_h
        max_scroll = max(0, content_h - view_h)
        self.travel_scroll = max(0, min(float(self.travel_scroll), max_scroll))
        self.travel_scroll_meta = {
            "list_top": list_top, "view_h": view_h, "max_scroll": max_scroll,
            "track": pygame.Rect(box.right - 22, list_top, 10, view_h),
            "clip": pygame.Rect(box.x + 12, list_top, box.w - 40, view_h),
        }

        prev_clip = self.screen.get_clip()
        self.screen.set_clip(self.travel_scroll_meta["clip"])

        def draw_btns(items, ox):
            y = list_top - self.travel_scroll
            for dest in items:
                row_top = y
                y += row_h
                if row_top + row_h < list_top or row_top > list_bottom:
                    continue
                row = pygame.Rect(ox, int(row_top), col_w, row_h - 6)
                pygame.draw.rect(self.screen, (32, 40, 54), row, border_radius=6)
                border = (120, 180, 230)
                lvl = None
                if dest["kind"] == "monster":
                    mdef = MONSTERS.get(dest.get("monster") or "", {})
                    lvl = mdef.get("level", 1)
                    border = self.monster_threat_color(lvl)
                if dest.get("id") == "castle_realm":
                    border = (255, 214, 90)
                pygame.draw.rect(self.screen, border, row, 1, border_radius=6)
                self.travel_btn_rects.append((row, dest))
                label = dest["label"]
                if lvl is not None:
                    label = f"{label}  ·  Lv {lvl}"
                self.screen.blit(self.font_small.render(label, True, WHITE), (row.x + 12, row.y + 6))
                blurb = dest.get("blurb") or ""
                self.screen.blit(self.font_tiny.render(blurb, True, GREY), (row.x + 12, row.y + 24))

        draw_btns(places, left_x)
        if right_x is not None:
            draw_btns(monsters, right_x)
        self.screen.set_clip(prev_clip)

        if max_scroll > 0:
            track = self.travel_scroll_meta["track"]
            pygame.draw.rect(self.screen, (28, 32, 42), track, border_radius=4)
            thumb_h = max(28, int(view_h * view_h / content_h))
            thumb_y = list_top + int((view_h - thumb_h) * self.travel_scroll / max_scroll)
            thumb = pygame.Rect(track.x, thumb_y, track.w, thumb_h)
            pygame.draw.rect(self.screen, (110, 160, 210), thumb, border_radius=4)
            self.travel_scroll_meta["thumb"] = thumb
        else:
            self.travel_scroll_meta["thumb"] = None

        foot = self.font_tiny.render(
            f"{len(places)} places · {len(monsters)} camps  ·  Wheel / ↑↓ / drag bar  ·  Right-click minimap for free walk",
            True, (140, 138, 120),
        )
        self.screen.blit(foot, (box.x + 20, box.bottom - 26))

    def draw_sidebar(self):
        _bind_client_globals()
        if USE_HUD_DRAWN_PANELS and USE_NEW_HUD:
            import hud_v2
            hud_v2.draw_sidebar(self)
            return
        if USE_HUD_MOCKUP_PLATES and USE_NEW_HUD:
            import hud_plates
            hud_plates.draw(self)
            return
        if USE_NEW_HUD:
            import hud_v2
            hud_v2.draw_sidebar(self)
            return
        self._sb_fill_panel()
        x0 = SIDEBAR_X + 14
        w = SCREEN_W - SIDEBAR_X - 28
        y = 12
        self.sidebar_bank_btn_rect = None
        self.sidebar_settings_rect = None
        self.skills_view_all_rect = None

        # Header: emblem + name + settings
        self._sb_icon_dragon(x0 + 16, y + 16, r=15)
        name = self.font_login.render(self.player["name"], True, WHITE)
        self.screen.blit(name, (x0 + 38, y + 4))
        gear_r = pygame.Rect(SCREEN_W - 36, y + 4, 22, 22)
        self.sidebar_settings_rect = gear_r
        self._sb_icon_gear(gear_r.centerx, gear_r.centery, r=7)
        y += 34

        coins_txt = self.font_small.render(f"{self.player['coins']:,} coins", True, (255, 230, 160))
        chip = pygame.Rect(x0 + 38, y, coins_txt.get_width() + 28, 20)
        pygame.draw.rect(self.screen, (42, 34, 16), chip, border_radius=10)
        pygame.draw.rect(self.screen, SB_GOLD_DIM, chip, 1, border_radius=10)
        self._sb_icon_coin(chip.x + 10, chip.centery, r=5)
        self.screen.blit(coins_txt, (chip.x + 20, chip.y + 2))
        y += 26

        # Pet row
        pet = self.player.get("pet")
        owned = self.player.get("owned_pets") or []
        self.pets_btn_rect = None
        row = pygame.Rect(x0, y, w, 28)
        if pet or owned:
            self.pets_btn_rect = row
            active = self.show_pets
            self._sb_card(
                row, bg=(32, 48, 64) if active else SB_CARD,
                border=(120, 180, 230) if active else SB_GOLD_DIM, radius=6,
            )
            self._sb_icon_pet(row.x + 14, row.centery)
            if pet:
                label = f"Pet: {pet['name']} Lvl {pet.get('level', 1)}"
                if len(owned) > 1:
                    label += f" ({len(owned)} owned)"
                else:
                    label += f"  {pet['hp']}/{pet['max_hp']}"
            else:
                label = f"Pets ({len(owned)} owned)"
            pet_line = self.font_tiny.render(label, True, (190, 220, 245))
            self.screen.blit(pet_line, (row.x + 28, row.y + 7))
            self._sb_icon_chevron(row.right - 12, row.centery)
        else:
            self._sb_card(row, radius=6)
            tip = self.font_tiny.render("No pet — Pet Emporium (Luna)", True, GREY)
            self.screen.blit(tip, (row.x + 10, row.y + 7))
        y += 32

        # Bank row
        bank_coins = int(self.player.get("bank_coins") or 0)
        row = pygame.Rect(x0, y, w, 28)
        self._sb_card(row, radius=6)
        self._sb_icon_bank(row.x + 14, row.centery)
        bank_lbl = self.font_tiny.render(f"Bank: {bank_coins:,} coins", True, (210, 200, 170))
        self.screen.blit(bank_lbl, (row.x + 28, row.y + 7))
        vb = self.font_tiny.render("View Bank >", True, WHITE)
        vb_rect = pygame.Rect(row.right - vb.get_width() - 14, row.y + 4, vb.get_width() + 10, 20)
        pygame.draw.rect(self.screen, (48, 70, 58), vb_rect, border_radius=5)
        pygame.draw.rect(self.screen, (120, 200, 140), vb_rect, 1, border_radius=5)
        self.screen.blit(vb, (vb_rect.x + 5, vb_rect.y + 3))
        self.sidebar_bank_btn_rect = vb_rect
        y += 32

        # Auto-pickup
        auto = bool(self.player.get("auto_pickup_items"))
        row = pygame.Rect(x0, y, w, 30)
        self.auto_pickup_btn_rect = row
        if auto:
            self._sb_card(row, bg=(36, 92, 52), border=(90, 220, 120), radius=7)
        else:
            self._sb_card(row, bg=(72, 40, 38), border=(170, 90, 70), radius=7)
        self._sb_icon_person(row.x + 14, row.centery)
        auto_txt = self.font_small.render(
            f"Auto coins+bones {'ON' if auto else 'OFF'} (P)", True, WHITE,
        )
        self.screen.blit(auto_txt, (row.x + 28, row.y + 6))
        self._sb_icon_gear(
            row.right - 14, row.centery, r=6,
            col=(200, 210, 200) if auto else (180, 140, 130),
        )
        y += 36

        # Vitality
        y = self._sidebar_section("Vitality", y)
        self._sb_icon_heart(x0 + 6, y + 10, s=6)
        max_hp = max(1, int(self.player["max_hp"]))
        hp = int(self.player["hp"])
        pct = hp / max_hp
        bar = pygame.Rect(x0 + 18, y, w - 18, 20)
        low = pct <= 0.25 and hp > 0
        if low:
            pulse = 0.5 + 0.5 * abs(math.sin(time.time() * 5))
            pygame.draw.rect(
                self.screen, (80 + int(40 * pulse), 20, 20), bar.inflate(4, 4), border_radius=6,
            )
        pygame.draw.rect(self.screen, (36, 24, 28), bar, border_radius=5)
        fill_c = (46, 196, 92) if pct > 0.5 else ((230, 150, 42) if pct > 0.25 else (210, 55, 48))
        if pct > 0:
            fill = pygame.Rect(bar.x + 2, bar.y + 2, max(2, int((bar.w - 4) * pct)), bar.h - 4)
            pygame.draw.rect(self.screen, fill_c, fill, border_radius=4)
            gloss = pygame.Surface((fill.w, max(2, fill.h // 3)), pygame.SRCALPHA)
            gloss.fill((255, 255, 255, 40))
            self.screen.blit(gloss, fill.topleft)
        pygame.draw.rect(self.screen, SB_GOLD_DIM, bar, 1, border_radius=5)
        hp_lbl = self.font_tiny.render(f"{hp} / {max_hp}", True, WHITE)
        self.screen.blit(hp_lbl, (bar.centerx - hp_lbl.get_width() // 2, bar.y + 3))
        y += 26
        if low:
            warn = self.font_small.render(
                "Low health — eat food!",
                True, (255, 120 + int(80 * abs(math.sin(time.time() * 4))), 90),
            )
            self.screen.blit(warn, (x0, y))
            y += 16

        # Skills
        self._sb_icon_chart(x0 + 4, y + 6)
        y = self._sidebar_section(
            "Skills", y, right_label="View All >", right_rect_attr="skills_view_all_rect",
        )
        cmb = self.player_combat_level()
        tot = self.player_total_level()
        btn = pygame.Rect(x0, y, w, 34)
        self.skills_btn_rect = btn
        active = self.show_skills
        self._sb_card(
            btn,
            bg=(40, 56, 78) if active else SB_CARD_HI,
            border=(120, 180, 255) if active else SB_GOLD_DIM,
            radius=7,
        )
        self.screen.blit(self.font_small.render("Skills (Tab)", True, WHITE), (btn.x + 12, btn.y + 3))
        summary = self.font_tiny.render(f"Combat {cmb}  ·  Total {tot}", True, (180, 200, 230))
        self.screen.blit(summary, (btn.x + 12, btn.y + 18))
        self._sb_icon_chevron(btn.right - 12, btn.centery)
        y += 40

        # Travel / Bank / Gear
        self.sidebar_action_rects = {}
        import emberdeep_v2_client
        gear_key = "" if emberdeep_v2_client.fp_active(self) else "E"
        actions = (
            ("travel", "Travel", "M", (42, 78, 130), (130, 190, 255), self._sb_icon_compass),
            ("bank", "Bank", "B", (40, 100, 70), (120, 230, 150), self._sb_icon_chest),
            ("gear", "Gear", gear_key, (110, 72, 42), (240, 180, 100), self._sb_icon_pack),
        )
        gap, aw = 6, (w - 12) // 3
        for i, (key, label, hotkey, bgc, bdc, icon_fn) in enumerate(actions):
            r = pygame.Rect(x0 + i * (aw + gap), y, aw, 40)
            active = (
                (key == "travel" and self.show_travel)
                or (key == "bank" and self.show_bank)
                or (key == "gear" and self.show_equipment)
            )
            self._sb_bevel_button(r, bgc, bdc, active=active, radius=8)
            icon_fn(r.centerx, r.y + 12)
            t1 = self.font_tiny.render(label, True, WHITE)
            t2 = self.font_tiny.render(hotkey, True, bdc)
            self.screen.blit(t1, (r.centerx - t1.get_width() // 2, r.y + 22))
            self.screen.blit(t2, (r.right - t2.get_width() - 5, r.bottom - 13))
            self.sidebar_action_rects[key] = r
        y += 46

        boosts = (self.player.get("stat_boosts") or {})
        if boosts:
            y = self._sidebar_section("Potion boosts", y)
            now = time.time()
            levels = self.player.get("levels") or {}
            for skill in ("attack", "strength", "defence"):
                buff = boosts.get(skill)
                if not buff:
                    continue
                amt = int(buff.get("amount") or 0)
                until = float(buff.get("until") or 0)
                left = max(0, int(until - now + 0.999)) if until else int(buff.get("seconds_left") or 0)
                if left <= 0 or amt <= 0:
                    continue
                base = int(levels.get(skill, 1))
                line = self.font_small.render(
                    f"{skill.title()} {base} → {base + amt}", True, (110, 255, 140),
                )
                self.screen.blit(line, (x0, y))
                timer = self.font_tiny.render(f"+{amt}  ·  {left}s", True, (255, 200, 110))
                self.screen.blit(timer, (x0, y + 14))
                y += 30
            y += 2

        # Tab tiles
        self.sidebar_tab_rects = {}
        tabs = (
            ("inventory", "Inv", self._sb_icon_bag, (90, 78, 55)),
            ("combat", "Combat", self._sb_icon_swords, (70, 55, 45)),
            ("magic", "Magic", self._sb_icon_hat, (40, 55, 95)),
            ("quests", "Quests", self._sb_icon_scroll, (70, 60, 40)),
        )
        tw = w // 4
        for i, (key, label, icon_fn, base_bg) in enumerate(tabs):
            r = pygame.Rect(x0 + i * tw, y, tw - 3, 42)
            active = self.sidebar_tab == key
            bg = tuple(min(255, c + 25) for c in base_bg) if active else base_bg
            border = SB_GOLD_HI if active else SB_GOLD_DIM
            self._sb_bevel_button(r, bg, border, active=active, radius=7)
            if active:
                pygame.draw.rect(self.screen, SB_GOLD, r, 2, border_radius=7)
            icon_fn(r.centerx, r.y + 12)
            txt = self.font_tiny.render(label, True, WHITE if active else (190, 188, 180))
            self.screen.blit(txt, (r.centerx - txt.get_width() // 2, r.y + 22))
            self.sidebar_tab_rects[key] = r
        y += 48

        content_bottom = SCREEN_H - 62
        if self.sidebar_tab == "inventory":
            self._draw_sidebar_inventory_tab(y, content_bottom)
        elif self.sidebar_tab == "combat":
            self._draw_sidebar_combat_tab(y, content_bottom)
        elif self.sidebar_tab == "magic":
            self._draw_sidebar_magic_tab(y, content_bottom)
        else:
            self._draw_sidebar_quests_tab(y, content_bottom)

        logout = pygame.Rect(x0, SCREEN_H - 54, w, 30)
        self.logout_btn_rect = logout
        self._sb_bevel_button(logout, (110, 42, 42), (210, 100, 90), radius=8)
        self._sb_icon_power(logout.x + 18, logout.centery)
        lo_txt = self.font_small.render("Logout", True, WHITE)
        self.screen.blit(lo_txt, (logout.centerx - lo_txt.get_width() // 2 + 6, logout.y + 6))

        controls = self.font_tiny.render(
            "Space attack · R eat · H help", True, (130, 128, 120),
        )
        self.screen.blit(controls, (SIDEBAR_X + 12, SCREEN_H - 18))

    def draw_inventory_tooltip(self, entry, slot_rect):
        """Hover card: full item name, qty, and combat bonuses."""
        _bind_client_globals()
        item = ITEMS.get(entry["item_id"], {})
        name = item.get("name", entry["item_id"])
        lines = [name]
        if entry.get("qty", 1) > 1:
            lines.append(f"Quantity: {entry['qty']}")
        itype = item.get("type", "item")
        lines.append(itype.replace("_", " ").title())
        bits = []
        if item.get("att_bonus"):
            bits.append(f"Att +{item['att_bonus']}")
        if item.get("str_bonus"):
            bits.append(f"Str +{item['str_bonus']}")
        if item.get("def_bonus"):
            bits.append(f"Def +{item['def_bonus']}")
        if item.get("ranged_att") or item.get("ranged_str"):
            bits.append(f"Range +{item.get('ranged_att', 0)}/+{item.get('ranged_str', 0)}")
        if item.get("heal"):
            bits.append(f"Heals {item['heal']}")
        if item.get("regen_hp") and item.get("regen_seconds"):
            bits.append(f"+{item['regen_hp']} HP / {item['regen_seconds']}s while worn")
        if item.get("boost_skill"):
            bits.append(
                f"+{item.get('boost_amount', 0)} {item['boost_skill'].title()} "
                f"for {item.get('boost_seconds', 60)}s"
            )
        if item.get("karma_xp"):
            bits.append(f"Bury: +{item['karma_xp']} Karma XP")
        if item.get("desc"):
            lines.append(item["desc"])
        if item.get("unique"):
            # The bag rule has to be visible where the player meets the item,
            # not only when a sale is refused.
            lines.append("Permanent — buy once, cannot be sold, traded or banked")
        # Jewelry specials (skip if already covered by desc "Special:")
        def _abil_line(name, val, mult=None):
            if name == "lifesteal":
                return f"Lifesteal {int(round(float(val) * 100))}%"
            if name == "crit":
                m = float(mult or 1.5)
                return f"Crit {int(round(float(val) * 100))}% ({m:.1f}×)"
            if name == "dodge":
                return f"Dodge {int(round(float(val) * 100))}%"
            if name == "thorns":
                return f"Thorns {int(round(float(val) * 100))}%"
            if name == "void_strike":
                return f"+{int(val)} flat damage"
            if name == "void_ward":
                return f"−{int(val)} damage taken"
            return None
        # Only add ability lines when desc doesn't already spell them out
        desc_l = (item.get("desc") or "").lower()
        if "lifesteal" not in desc_l and "crit" not in desc_l and "dodge" not in desc_l and "thorns" not in desc_l and "flat" not in desc_l and "ward" not in desc_l and "special:" not in desc_l:
            ab = _abil_line(item.get("ability"), item.get("ability_value"), item.get("ability_mult"))
            if ab:
                bits.append(ab)
            ab2 = _abil_line(item.get("ability2"), item.get("ability2_value"), item.get("ability2_mult"))
            if ab2:
                bits.append(ab2)
        elif item.get("ability") or item.get("ability2"):
            # Compact ability chips when desc is niche text
            for name, val, mult in (
                (item.get("ability"), item.get("ability_value"), item.get("ability_mult")),
                (item.get("ability2"), item.get("ability2_value"), item.get("ability2_mult")),
            ):
                ab = _abil_line(name, val, mult)
                if ab and ab.split()[0].lower() not in desc_l:
                    bits.append(ab)
        if entry["item_id"] == "arrow_quiver":
            qtot = int((self.player or {}).get("quiver_total") or 0)
            cap = int((self.player or {}).get("quiver_capacity") or 1000)
            lines.append(f"Stores {cap} of each arrow type")
            lines.append(f"Loaded: {qtot} arrows · fires best first")
            q = (self.player or {}).get("quiver") or {}
            if q:
                for aid, qty in sorted(q.items(), key=lambda kv: -int(kv[1] or 0))[:4]:
                    an = (ITEMS.get(aid) or {}).get("name", aid)
                    lines.append(f"  {an} ×{qty}")
        elif entry["item_id"] == "arrowtip_box":
            qtot = int((self.player or {}).get("tip_box_total") or 0)
            cap = int((self.player or {}).get("tip_box_capacity") or 200)
            lines.append(f"Stores {cap} of each tip type")
            lines.append(f"Packed: {qtot} tips · used when fletching")
            q = (self.player or {}).get("tip_box") or {}
            if q:
                for tid, qty in sorted(q.items(), key=lambda kv: -int(kv[1] or 0))[:4]:
                    tn = (ITEMS.get(tid) or {}).get("name", tid)
                    lines.append(f"  {tn} ×{qty}")
            lines.append("Click: Pack / Unpack")
        elif entry["item_id"] == "food_bag":
            qtot = int((self.player or {}).get("food_bag_total") or 0)
            cap = int((self.player or {}).get("food_bag_capacity") or 200)
            lines.append(f"Stores {cap} of each cooked fish")
            lines.append(f"Packed: {qtot} · eat highest heal first")
            q = (self.player or {}).get("food_bag") or {}
            if q:
                for fid, qty in sorted(q.items(), key=lambda kv: -int(kv[1] or 0))[:4]:
                    fn = (ITEMS.get(fid) or {}).get("name", fid)
                    lines.append(f"  {fn} ×{qty}")
            lines.append("Click: Eat / Pack / Unpack")
        elif entry["item_id"] == "raw_food_bag":
            qtot = int((self.player or {}).get("raw_bag_total") or 0)
            cap = int((self.player or {}).get("raw_bag_capacity") or 200)
            lines.append(f"Stores {cap} of each raw fish")
            lines.append(f"Packed: {qtot} · used when cooking")
            q = (self.player or {}).get("raw_bag") or {}
            if q:
                for fid, qty in sorted(q.items(), key=lambda kv: -int(kv[1] or 0))[:4]:
                    fn = (ITEMS.get(fid) or {}).get("name", fid)
                    lines.append(f"  {fn} ×{qty}")
            lines.append("Click: Pack / Unpack")
        elif entry["item_id"] == "food_bag":
            qtot = int((self.player or {}).get("food_bag_total") or 0)
            cap = int((self.player or {}).get("food_bag_capacity") or 200)
            lines.append(f"Stores {cap} of each cooked fish")
            lines.append(f"Packed: {qtot} · eat highest heal first")
            q = (self.player or {}).get("food_bag") or {}
            if q:
                for fid, qty in sorted(q.items(), key=lambda kv: -int(kv[1] or 0))[:4]:
                    fn = (ITEMS.get(fid) or {}).get("name", fid)
                    lines.append(f"  {fn} ×{qty}")
            lines.append("Click: Eat / Pack / Unpack")
        elif entry["item_id"] == "raw_food_bag":
            qtot = int((self.player or {}).get("raw_bag_total") or 0)
            cap = int((self.player or {}).get("raw_bag_capacity") or 200)
            lines.append(f"Stores {cap} of each raw fish")
            lines.append(f"Packed: {qtot} · used when cooking")
            q = (self.player or {}).get("raw_bag") or {}
            if q:
                for fid, qty in sorted(q.items(), key=lambda kv: -int(kv[1] or 0))[:4]:
                    fn = (ITEMS.get(fid) or {}).get("name", fid)
                    lines.append(f"  {fn} ×{qty}")
            lines.append("Click: Pack / Unpack")
        elif entry["item_id"] == "mining_bag":
            qtot = int((self.player or {}).get("mining_bag_total") or 0)
            cap = int((self.player or {}).get("resource_bag_capacity") or 200)
            lines.append(f"Stores {cap} of each ore/bar")
            lines.append(f"Packed: {qtot} · used when smithing")
            q = (self.player or {}).get("mining_bag") or {}
            if q:
                for iid, qty in sorted(q.items(), key=lambda kv: -int(kv[1] or 0))[:4]:
                    n = (ITEMS.get(iid) or {}).get("name", iid)
                    lines.append(f"  {n} ×{qty}")
            lines.append("Click: Pack / Unpack")
        elif entry["item_id"] == "gem_bag":
            qtot = int((self.player or {}).get("gem_bag_total") or 0)
            cap = int((self.player or {}).get("resource_bag_capacity") or 200)
            lines.append(f"Stores {cap} of each unset gem")
            lines.append(f"Packed: {qtot} · used when forging jewelry")
            q = (self.player or {}).get("gem_bag") or {}
            if q:
                for iid, qty in sorted(q.items(), key=lambda kv: -int(kv[1] or 0))[:4]:
                    n = (ITEMS.get(iid) or {}).get("name", iid)
                    lines.append(f"  {n} ×{qty}")
            lines.append("Click: Pack / Unpack")
        elif entry["item_id"] == "log_bag":
            qtot = int((self.player or {}).get("log_bag_total") or 0)
            cap = int((self.player or {}).get("resource_bag_capacity") or 200)
            lines.append(f"Stores {cap} of each log type")
            lines.append(f"Packed: {qtot} · firemaking/fletching first")
            q = (self.player or {}).get("log_bag") or {}
            if q:
                for iid, qty in sorted(q.items(), key=lambda kv: -int(kv[1] or 0))[:4]:
                    n = (ITEMS.get(iid) or {}).get("name", iid)
                    lines.append(f"  {n} ×{qty}")
            lines.append("Click: Pack / Unpack")
        elif entry["item_id"] == "fletch_pouch":
            qtot = int((self.player or {}).get("fletch_pouch_total") or 0)
            feather_cap = int((self.player or {}).get("feather_bag_capacity") or 5000)
            lines.append(f"Feathers, shafts, bowstring, headless arrows {feather_cap}")
            lines.append(f"Packed: {qtot} · used when fletching")
            q = (self.player or {}).get("fletch_pouch") or {}
            if q:
                for iid, qty in sorted(q.items(), key=lambda kv: -int(kv[1] or 0))[:4]:
                    n = (ITEMS.get(iid) or {}).get("name", iid)
                    lines.append(f"  {n} ×{qty}")
            lines.append("Click: Pack / Unpack")
        elif entry["item_id"] == "potion_pouch":
            qtot = int((self.player or {}).get("potion_pouch_total") or 0)
            cap = int((self.player or {}).get("resource_bag_capacity") or 200)
            lines.append(f"Stores {cap} of each potion")
            lines.append(f"Packed: {qtot}")
            q = (self.player or {}).get("potion_pouch") or {}
            if q:
                for iid, qty in sorted(q.items(), key=lambda kv: -int(kv[1] or 0))[:4]:
                    n = (ITEMS.get(iid) or {}).get("name", iid)
                    lines.append(f"  {n} ×{qty}")
            lines.append("Click: Pack / Unpack")
        elif item.get("ammo_type") == "arrow":
            bits.append(f"Ranged +{item.get('ranged_att', 0)}/+{item.get('ranged_str', 0)}")
            lines.append("Click: add to quiver or drop")
        elif str(entry["item_id"]).endswith("arrowtips"):
            lines.append("Click: pack into tip box or drop")
        elif is_cooked_fish(entry["item_id"]):
            bits.append(f"Heals {item.get('heal', 0)}")
            lines.append("Click: eat, pack in food bag, or drop")
        elif is_raw_fish(entry["item_id"]):
            lines.append("Click: pack in raw bag or drop")
        elif is_mining_bag_item(entry["item_id"]):
            lines.append("Click: pack in mining bag or drop")
        elif is_gem_item(entry["item_id"]):
            lines.append("Click: pack in gem bag or drop")
        elif is_log_item(entry["item_id"]):
            lines.append("Click: fire, fletch, pack, or drop")
        elif is_fletch_pouch_item(entry["item_id"]):
            lines.append("Click: pack in fletching pouch or drop")
        elif is_potion_item(entry["item_id"]):
            lines.append("Click: drink, pack in pouch, or drop")
        if bits:
            lines.append("  ".join(bits))
        eq = item.get("equip_slot")
        if eq:
            lines.append(f"Wear: {eq}")
        if item.get("tool_for"):
            lines.append(f"Tool: {item['tool_for']}")

        pad_x, pad_y = 10, 8
        line_h = 16
        surfs = [self.font.render(lines[0], True, YELLOW)]
        surfs += [self.font_small.render(ln, True, WHITE) for ln in lines[1:]]
        tw = max(s.get_width() for s in surfs) + pad_x * 2
        th = pad_y * 2 + sum(s.get_height() + 2 for s in surfs)

        mx, my = pygame.mouse.get_pos()
        tip_x = min(mx + 14, SCREEN_W - tw - 8)
        tip_y = max(8, my - th - 8)
        # Prefer above the slot if it fits
        if tip_y + th > slot_rect.y:
            tip_y = max(8, slot_rect.y - th - 6)
        tip = pygame.Rect(tip_x, tip_y, tw, th)
        pygame.draw.rect(self.screen, (22, 24, 34), tip, border_radius=4)
        pygame.draw.rect(self.screen, (230, 200, 80), tip, 2, border_radius=4)
        cy = tip.y + pad_y
        for s in surfs:
            self.screen.blit(s, (tip.x + pad_x, cy))
            cy += s.get_height() + 2

    def draw_dialogue(self):
        _bind_client_globals()
        if self.dialogue.get("castle"):
            import castle_owners_client
            castle_owners_client.draw_dialogue(self)
            return
        box = self._dialogue_box()
        pygame.draw.rect(self.screen, (25, 25, 35), box)
        pygame.draw.rect(self.screen, WHITE, box, 2)
        self.dialogue_btn_rects = {}

        name = self.font.render(self.dialogue["npc_name"], True, YELLOW)
        self.screen.blit(name, (box.x + 12, box.y + 10))
        import fairy_village_client
        import npc_hd_client
        bust = fairy_village_client.portrait(self, self.dialogue.get("npc_id"))
        if bust is None:
            bust = npc_hd_client.portrait(self, self.dialogue.get("npc_id"))
        text_x = box.x + 12
        if bust:
            self.screen.blit(bust, (box.x + 12, box.y + 40))
            text_x = box.x + 20 + bust.get_width()

        # Action buttons along the bottom
        btn_y = box.bottom - 36
        bx = box.x + 12
        quest = self.dialogue.get("quest")

        def add_btn(action, label, color, x):
            tw = max(72, self.font_small.size(label)[0] + 18)
            r = pygame.Rect(x, btn_y, tw, 26)
            pygame.draw.rect(self.screen, color, r, border_radius=5)
            pygame.draw.rect(self.screen, WHITE, r, 1, border_radius=5)
            txt = self.font_small.render(label, True, WHITE)
            self.screen.blit(txt, (r.centerx - txt.get_width() // 2, r.y + 5))
            self.dialogue_btn_rects[action] = r
            return r.right + 8

        # Gift quests grant on talk — no Accept button (bag-full just means try again).
        if quest and quest.get("state") == "offerable" and quest.get("type") != "gift":
            bx = add_btn("accept", "Accept (A)", (50, 110, 60), bx)
        if quest and quest.get("state") == "ready":
            bx = add_btn("turnin", "Turn in (T)", (160, 120, 40), bx)
        if self.dialogue.get("shop_id"):
            bx = add_btn("shop", "Shop (B)", (120, 90, 40), bx)
        if self.dialogue.get("teleport"):
            bx = add_btn("teleport", "Teleport", (96, 48, 150), bx)
        if self.dialogue.get("housing"):
            bx = add_btn("housing", "Homes (B)", (90, 70, 30), bx)
        if self.dialogue.get("bank"):
            bx = add_btn("bank", "Bank (B)", (50, 90, 130), bx)
        if self.dialogue.get("forge"):
            bx = add_btn("forge", "Forge (S)", (140, 80, 40), bx)
        persuade = self.dialogue.get("persuade")
        if persuade:
            bx = add_btn("persuade", f"[Persuade (Charisma {int(persuade.get('req') or 1)})]", (110, 60, 120), bx)
        pages = self.dialogue.get("pages") or []
        page_i = int(self.dialogue.get("page") or 0)
        if pages and page_i > 0:
            bx = add_btn("back", "Back", (70, 80, 110), bx)
        if pages and page_i < len(pages) - 1:
            bx = add_btn("next", "Next", (70, 90, 120), bx)
        add_btn("close", "Close", (60, 60, 70), box.right - 80)

        # Menu options (apprentice masters, estate office) wrap in rows above the buttons
        opts_top = btn_y
        options = self.dialogue.get("options") or []
        if options:
            rows, row, row_w = [], [], 0
            for opt in options:
                w = max(72, self.font_small.size(opt["label"])[0] + 18) + 8
                if row and text_x + row_w + w > box.right - 12:
                    rows.append(row)
                    row, row_w = [], 0
                row.append(opt)
                row_w += w
            if row:
                rows.append(row)
            saved_y = btn_y
            for r_i, row in enumerate(rows):
                btn_y = saved_y - 32 * (len(rows) - r_i)
                ox = text_x
                for opt in row:
                    if opt.get("ok", True):
                        ox = add_btn("opt:" + opt["id"], opt["label"], (60, 80, 70), ox)
                    else:
                        ox = add_btn("optx:" + opt["id"], opt["label"], (62, 62, 62), ox)
            opts_top = saved_y - 32 * len(rows)
            btn_y = saved_y

        # Body text — clipped above buttons
        text_bottom = opts_top - 8
        y = box.y + 36
        max_w = box.right - 12 - text_x
        prev_clip = self.screen.get_clip()
        self.screen.set_clip(pygame.Rect(text_x - 4, box.y + 34, max_w + 8, text_bottom - (box.y + 34)))

        pages = self.dialogue.get("pages") or []
        page_i = int(self.dialogue.get("page") or 0)
        shown = pages[page_i] if pages and 0 <= page_i < len(pages) else (self.dialogue.get("lines") or [])
        for line in shown:
            for wrapped in self._wrap_ui_text(line, self.font_small, max_w):
                if y + 16 > text_bottom:
                    break
                self.screen.blit(self.font_small.render(wrapped, True, WHITE), (text_x, y))
                y += 17
            if y + 16 > text_bottom:
                break

        if quest:
            y += 6
            q_title = f"Quest: {quest.get('name', '?')}"
            self.screen.blit(self.font_small.render(q_title, True, (200, 200, 255)), (text_x, y))
            y += 18
            desc = quest.get("description") or ""
            for wrapped in self._wrap_ui_text(desc, self.font_tiny, max_w):
                if y + 14 > text_bottom:
                    break
                self.screen.blit(self.font_tiny.render(wrapped, True, (180, 185, 210)), (text_x, y))
                y += 15
            obj = quest.get("objective")
            if not obj and quest.get("quest_id"):
                # Fallback from local quest defs + journal progress
                qid = quest["quest_id"]
                info = self.quests.get(qid) or {"status": quest.get("state"), "progress": 0}
                obj = self._quest_objective_text(qid, info)
            if obj and y + 16 <= text_bottom:
                self.screen.blit(
                    self.font_small.render(f"Objective: {obj}", True, (255, 220, 140)),
                    (text_x, y),
                )
                y += 18
            reward_bits = self._format_quest_rewards({
                "quest_points": quest.get("quest_points") or (QUESTS.get(quest.get("quest_id") or "", {}) or {}).get("quest_points"),
                "rewards": quest.get("rewards") or (QUESTS.get(quest.get("quest_id") or "", {}) or {}).get("rewards") or {},
            })
            if reward_bits and y + 14 <= text_bottom:
                for wrapped in self._wrap_ui_text(f"Reward: {reward_bits}", self.font_tiny, max_w):
                    if y + 14 > text_bottom:
                        break
                    self.screen.blit(
                        self.font_tiny.render(wrapped, True, (180, 210, 160)),
                        (text_x, y),
                    )
                    y += 14
            if quest.get("state") == "offerable" and quest.get("type") == "gift":
                hint, hcol = "Free up bag space, then talk again.", YELLOW
            elif quest.get("state") == "offerable":
                hint, hcol = "Accept this quest to begin.", GREEN
            elif quest.get("state") == "active":
                hint, hcol = "Follow the gold trail — then return here.", GREY
            elif quest.get("state") == "ready":
                hint, hcol = "Turn in below for your reward.", YELLOW
            else:
                hint, hcol = "Quest already completed.", GREEN
            if y + 16 <= text_bottom:
                self.screen.blit(self.font_small.render(hint, True, hcol), (text_x, y))

        self.screen.set_clip(prev_clip)

    def draw_shop(self):
        """Centered buy/sell modal — stock on the left, your items to sell on the right."""
        _bind_client_globals()
        box = pygame.Rect(160, 70, 700, 520)
        pygame.draw.rect(self.screen, (18, 20, 28), box)
        pygame.draw.rect(self.screen, (255, 200, 80), box, 2)

        title = self.font_big.render(self.shop["name"], True, WHITE)
        self.screen.blit(title, (box.x + 18, box.y + 12))
        coins = self.font.render(f"Your coins: {self.shop['your_coins']}", True, YELLOW)
        self.screen.blit(coins, (box.x + 18, box.y + 42))

        close = pygame.Rect(box.right - 36, box.y + 10, 26, 26)
        pygame.draw.rect(self.screen, (60, 40, 40), close)
        pygame.draw.rect(self.screen, RED, close, 1)
        self.screen.blit(self.font.render("X", True, WHITE), (close.x + 7, close.y + 2))

        mid_x = box.x + box.w // 2
        pygame.draw.line(self.screen, PANEL_LINE, (mid_x, box.y + 70), (mid_x, box.bottom - 36), 1)

        list_top = box.y + 100
        list_bottom = box.bottom - 36
        view_h = max(40, list_bottom - list_top)
        row_h = 40
        sb_w = 10

        # --- Buy column ---
        self.screen.blit(self.font.render("Buy", True, GREEN), (box.x + 18, box.y + 72))
        # A first-hour player doesn't know what a bag does for them; if one is
        # on the shelf and not yet owned, say so plainly instead of "click to buy".
        bag_tip = self._shop_bag_tip()
        self.screen.blit(
            self.font_small.render(bag_tip or "Click to buy 1 · scroll / drag bar", True,
                                   (150, 220, 150) if bag_tip else GREY),
            (box.x + 60, box.y + 76),
        )
        buy_items = list((self.shop.get("stock") or {}).items())
        buy_content = len(buy_items) * row_h
        buy_max = max(0, buy_content - view_h)
        self.shop_buy_scroll = max(0, min(float(self.shop_buy_scroll), buy_max))
        buy_area = pygame.Rect(box.x + 12, list_top, mid_x - box.x - 28, view_h)
        buy_track = pygame.Rect(mid_x - 18, list_top, sb_w, view_h)

        self.shop_buy_rects = []
        prev_clip = self.screen.get_clip()
        self.screen.set_clip(buy_area)
        y = list_top - self.shop_buy_scroll
        for item_id, info in buy_items:
            row = pygame.Rect(box.x + 14, int(y), mid_x - box.x - 36, 36)
            if row.bottom >= list_top and row.y <= list_bottom:
                pygame.draw.rect(self.screen, (32, 36, 48), row, border_radius=4)
                pygame.draw.rect(self.screen, (70, 80, 100), row, 1, border_radius=4)
                # Bags, pouches and the quiver are one-per-character and never
                # resold: once owned the row goes quiet instead of offering a
                # second copy you could not use.
                owned = self.owns_shop_item(item_id)
                icon = pygame.Rect(row.x + 6, row.y + 4, 28, 28)
                sprites.draw_item_icon(self.screen, icon, item_id, ITEMS)
                name = self.font_small.render(info["name"], True, (130, 140, 160) if owned else WHITE)
                self.screen.blit(name, (row.x + 42, row.y + 4))
                if owned:
                    meta = self.font_small.render("Owned — one per character", True, (140, 200, 140))
                else:
                    btax = _shop_buy_tax(info["price"], self.shop.get("tax_rate", 0))
                    meta = self.font_small.render(
                        f"{info['price']} gp (+{btax} tax)   stock {info['qty']}", True, (180, 200, 140))
                self.screen.blit(meta, (row.x + 42, row.y + 18))
                if not owned:
                    self.shop_buy_rects.append((row, item_id))
            y += row_h
        self.screen.set_clip(prev_clip)

        buy_thumb = None
        if buy_max > 0:
            pygame.draw.rect(self.screen, (40, 44, 54), buy_track, border_radius=4)
            thumb_h = max(18, int(view_h * view_h / max(1, buy_content)))
            thumb_y = list_top + int((view_h - thumb_h) * self.shop_buy_scroll / buy_max)
            buy_thumb = pygame.Rect(buy_track.x, thumb_y, sb_w, thumb_h)
            pygame.draw.rect(self.screen, (120, 140, 170), buy_thumb, border_radius=4)

        # --- Sell column ---
        self.screen.blit(self.font.render("Sell", True, (255, 170, 90)), (mid_x + 14, box.y + 72))
        if self.shop.get("buys", True):
            buy_types = self.shop.get("buys_types") or []
            buy_slots = self.shop.get("buys_slots") or []
            if buy_types or buy_slots:
                hint = "Buys jewelry & gems · click=1 · Shift+click=stack"
            else:
                hint = "Click=sell 1 · Shift+click=stack · scroll"
            self.screen.blit(
                self.font_small.render(hint, True, GREY),
                (mid_x + 70, box.y + 76),
            )
        else:
            self.screen.blit(
                self.font_small.render("This shop does not buy items", True, GREY),
                (mid_x + 14, box.y + 100),
            )

        self.shop_sell_rects = []
        sell_slots = []
        if self.shop.get("buys", True) and self.player:
            inv = self.player.get("inventory") or {}
            for k, entry in inv.items():
                try:
                    sell_slots.append((int(k), entry))
                except (TypeError, ValueError):
                    continue
            sell_slots.sort(key=lambda t: t[0])
            sell_slots = [
                (slot, entry) for slot, entry in sell_slots
                if entry and entry.get("item_id") != "coins"
                and not (ITEMS.get(entry.get("item_id")) or {}).get("unique")
                and self.shop_will_buy_item(entry.get("item_id"))
            ]

        sell_content = len(sell_slots) * row_h
        sell_max = max(0, sell_content - view_h) if self.shop.get("buys", True) else 0
        self.shop_sell_scroll = max(0, min(float(self.shop_sell_scroll), sell_max))
        sell_area = pygame.Rect(mid_x + 10, list_top, box.right - mid_x - 24, view_h)
        sell_track = pygame.Rect(box.right - 22, list_top, sb_w, view_h)
        sell_thumb = None

        if self.shop.get("buys", True) and self.player:
            if not sell_slots:
                empty_msg = "Nothing to sell in your inventory."
                if self.shop.get("buys_types") or self.shop.get("buys_slots"):
                    empty_msg = "No jewelry or gems to sell."
                self.screen.blit(
                    self.font_small.render(empty_msg, True, GREY),
                    (mid_x + 14, box.y + 110),
                )
            else:
                self.screen.set_clip(sell_area)
                y = list_top - self.shop_sell_scroll
                for slot, entry in sell_slots:
                    item_id = entry["item_id"]
                    price = self.sell_price(item_id)
                    row = pygame.Rect(mid_x + 12, int(y), box.right - mid_x - 36, 36)
                    if row.bottom >= list_top and row.y <= list_bottom:
                        pygame.draw.rect(self.screen, (40, 34, 28), row, border_radius=4)
                        pygame.draw.rect(self.screen, (120, 90, 50), row, 1, border_radius=4)
                        icon = pygame.Rect(row.x + 6, row.y + 4, 28, 28)
                        sprites.draw_item_icon(self.screen, icon, item_id, ITEMS)
                        label = ITEMS.get(item_id, {}).get("name", item_id)
                        qty = entry.get("qty", 1)
                        name = self.font_small.render(f"{label}  x{qty}", True, WHITE)
                        self.screen.blit(name, (row.x + 42, row.y + 4))
                        stax = _shop_sell_tax(price, self.shop.get("tax_rate", 0))
                        meta = self.font_small.render(f"sell {price} gp (\u2212{stax} tax) each", True, (255, 200, 120))
                        self.screen.blit(meta, (row.x + 42, row.y + 18))
                        self.shop_sell_rects.append((row, slot, item_id))
                    y += row_h
                self.screen.set_clip(prev_clip)

            sell_thumb = None
            if sell_max > 0:
                pygame.draw.rect(self.screen, (40, 44, 54), sell_track, border_radius=4)
                thumb_h = max(18, int(view_h * view_h / max(1, sell_content)))
                thumb_y = list_top + int((view_h - thumb_h) * self.shop_sell_scroll / sell_max)
                sell_thumb = pygame.Rect(sell_track.x, thumb_y, sb_w, thumb_h)
                pygame.draw.rect(self.screen, (170, 140, 90), sell_thumb, border_radius=4)

        self.shop_scroll_meta = {
            "buy": {
                "max_scroll": buy_max, "list_top": list_top, "view_h": view_h,
                "track": buy_track, "thumb": buy_thumb,
            },
            "sell": {
                "max_scroll": sell_max, "list_top": list_top, "view_h": view_h,
                "track": sell_track, "thumb": sell_thumb,
            },
            "mid_x": mid_x,
            "box": box,
        }

        hint = self.font_small.render("Esc or click X / outside to close", True, GREY)
        self.screen.blit(hint, (box.x + 18, box.bottom - 26))
        rate = float(self.shop.get("tax_rate") or 0)
        rmult = float(self.shop.get("rep_mult") or 1.0)
        rpct = int(round((rmult - 1.0) * 100))
        sign = "+" if rpct > 0 else ("\u2212" if rpct < 0 else "")
        rtxt = f"{sign}{abs(rpct)}%"
        ndisc = float(self.shop.get("noble_discount") or 0)
        ntxt = f" · Rank: {self.shop.get('noble_title')} (\u2212{int(round(ndisc * 100))}%)" if ndisc > 0 else ""
        tax_line = self.font_small.render(
            f"Standing: {self.shop.get('rep_tier', 'Neutral')} ({rtxt}){ntxt}   Royal sales tax: {int(round(rate * 100))}%",
            True, YELLOW)
        self.screen.blit(tax_line, (box.right - tax_line.get_width() - 18, box.bottom - 26))

    def draw_bank(self):
        """Bank vault: deposit/withdraw items and coins — scrollable inv + paged vault grid."""
        _bind_client_globals()
        box = pygame.Rect(120, 50, 780, 560)
        pygame.draw.rect(self.screen, (16, 20, 30), box)
        pygame.draw.rect(self.screen, (120, 190, 255), box, 2)

        title = self.font_big.render("Village Bank", True, WHITE)
        self.screen.blit(title, (box.x + 18, box.y + 10))

        purse = int(self.bank.get("coins", self.player.get("coins", 0) if self.player else 0))
        vault = int(self.bank.get("bank_coins", 0))
        max_purse = int(self.bank.get("max_purse", 65000))
        max_vault = int(self.bank.get("max_bank_coins", 500_000_000))
        slots_n = int(self.bank.get("bank_slots", 96))
        page_size = max(1, int(self.bank_page_size))
        max_page = max(0, (slots_n - 1) // page_size)
        self.bank_page = max(0, min(self.bank_page, max_page))

        meta = self.font.render(
            f"Purse: {purse:,} / {max_purse:,}     Vault: {vault:,} / {max_vault:,}     Slots: {slots_n}",
            True, YELLOW,
        )
        self.screen.blit(meta, (box.x + 18, box.y + 44))

        close = pygame.Rect(box.right - 36, box.y + 10, 26, 26)
        pygame.draw.rect(self.screen, (60, 40, 40), close)
        pygame.draw.rect(self.screen, RED, close, 1)
        self.screen.blit(self.font.render("X", True, WHITE), (close.x + 7, close.y + 2))
        self.bank_btn_rects = {"close": close}

        # Coin buttons
        self.bank_btn_rects["dep_all"] = pygame.Rect(box.x + 18, box.y + 72, 130, 28)
        self.bank_btn_rects["dep_1k"] = pygame.Rect(box.x + 156, box.y + 72, 90, 28)
        self.bank_btn_rects["dep_inv"] = pygame.Rect(box.x + 254, box.y + 72, 140, 28)
        self.bank_btn_rects["wd_all"] = pygame.Rect(box.x + 420, box.y + 72, 140, 28)
        self.bank_btn_rects["wd_1k"] = pygame.Rect(box.x + 568, box.y + 72, 100, 28)
        for key, label in (
            ("dep_all", "Deposit coins"),
            ("dep_1k", "Dep 1k"),
            ("dep_inv", "Deposit inventory"),
            ("wd_all", "Withdraw to cap"),
            ("wd_1k", "Wdr 1k"),
        ):
            r = self.bank_btn_rects[key]
            pygame.draw.rect(self.screen, (40, 55, 70), r, border_radius=4)
            pygame.draw.rect(self.screen, (100, 160, 210), r, 1, border_radius=4)
            txt = self.font_small.render(label, True, WHITE)
            self.screen.blit(txt, (r.x + (r.w - txt.get_width()) // 2, r.y + 6))

        mid_x = box.x + box.w // 2
        pygame.draw.line(self.screen, PANEL_LINE, (mid_x, box.y + 110), (mid_x, box.bottom - 36), 1)

        # --- Inventory (deposit) — scrollable list ---
        self.screen.blit(self.font.render("Your inventory", True, GREEN), (box.x + 18, box.y + 112))
        self.screen.blit(self.font_small.render("Click deposit · Scroll / ↑↓", True, GREY), (box.x + 160, box.y + 116))
        self.bank_inv_rects = []
        inv = (self.bank.get("inventory") if self.bank else None) or (self.player or {}).get("inventory") or {}
        inv_items = [(int(k), v) for k, v in inv.items() if v]
        inv_items.sort(key=lambda kv: kv[0])
        inv_visible = 9
        max_inv_scroll = max(0, len(inv_items) - inv_visible)
        self.bank_inv_scroll = max(0, min(self.bank_inv_scroll, max_inv_scroll))
        y = box.y + 140
        page_items = inv_items[self.bank_inv_scroll:self.bank_inv_scroll + inv_visible]
        for slot, entry in page_items:
            item_id = entry["item_id"]
            row = pygame.Rect(box.x + 14, y, mid_x - box.x - 28, 34)
            pygame.draw.rect(self.screen, (32, 36, 48), row, border_radius=4)
            pygame.draw.rect(self.screen, (70, 80, 100), row, 1, border_radius=4)
            icon = pygame.Rect(row.x + 6, row.y + 3, 26, 26)
            sprites.draw_item_icon(self.screen, icon, item_id, ITEMS)
            label = ITEMS.get(item_id, {}).get("name", item_id)
            name = self.font_small.render(f"{label}  x{entry.get('qty', 1)}", True, WHITE)
            self.screen.blit(name, (row.x + 40, row.y + 8))
            self.bank_inv_rects.append((row, slot))
            y += 38
        if not inv_items:
            self.screen.blit(
                self.font_small.render("Inventory empty.", True, GREY),
                (box.x + 18, box.y + 150),
            )
        elif max_inv_scroll > 0:
            self.bank_btn_rects["inv_up"] = pygame.Rect(mid_x - 70, box.bottom - 58, 28, 22)
            self.bank_btn_rects["inv_down"] = pygame.Rect(mid_x - 38, box.bottom - 58, 28, 22)
            for key, label, enabled in (
                ("inv_up", "▲", self.bank_inv_scroll > 0),
                ("inv_down", "▼", self.bank_inv_scroll < max_inv_scroll),
            ):
                r = self.bank_btn_rects[key]
                pygame.draw.rect(self.screen, (45, 55, 70) if enabled else (28, 30, 36), r, border_radius=3)
                pygame.draw.rect(self.screen, (100, 160, 210) if enabled else PANEL_LINE, r, 1, border_radius=3)
                txt = self.font_small.render(label, True, WHITE if enabled else GREY)
                self.screen.blit(txt, (r.x + (r.w - txt.get_width()) // 2, r.y + 2))
            hint = self.font_tiny.render(
                f"{self.bank_inv_scroll + 1}-{self.bank_inv_scroll + len(page_items)} / {len(inv_items)}",
                True, GREY,
            )
            self.screen.blit(hint, (box.x + 18, box.bottom - 54))

        # --- Bank vault — paged grid of all slots ---
        self.screen.blit(self.font.render("Bank vault", True, (180, 210, 255)), (mid_x + 14, box.y + 112))
        page_lbl = self.font_small.render(
            f"Page {self.bank_page + 1}/{max_page + 1}  ·  click=all  shift=1  ·  ←→",
            True, GREY,
        )
        self.screen.blit(page_lbl, (mid_x + 130, box.y + 116))

        self.bank_slot_rects = []
        bank = self.bank.get("bank") or {}
        cols, rows = 6, 6
        cell = 52
        gap = 6
        grid_x = mid_x + 16
        grid_y = box.y + 142
        start = self.bank_page * page_size
        for i in range(page_size):
            slot = start + i
            if slot >= slots_n:
                break
            col, row = i % cols, i // cols
            if row >= rows:
                break
            cx = grid_x + col * (cell + gap)
            cy = grid_y + row * (cell + gap)
            rect = pygame.Rect(cx, cy, cell, cell)
            entry = bank.get(str(slot)) or bank.get(slot)
            pygame.draw.rect(self.screen, (28, 40, 55) if entry else (22, 26, 34), rect, border_radius=4)
            pygame.draw.rect(
                self.screen,
                (80, 140, 190) if entry else (50, 58, 70),
                rect, 1, border_radius=4,
            )
            # Slot index
            idx = self.font_tiny.render(str(slot + 1), True, (70, 80, 95))
            self.screen.blit(idx, (rect.x + 3, rect.y + 2))
            if entry:
                icon = pygame.Rect(rect.x + 10, rect.y + 8, 32, 32)
                sprites.draw_item_icon(self.screen, icon, entry["item_id"], ITEMS)
                qty = int(entry.get("qty", 1))
                if qty > 1:
                    q = self.font_tiny.render(str(qty), True, WHITE)
                    self.screen.blit(q, (rect.right - q.get_width() - 3, rect.bottom - 12))
            self.bank_slot_rects.append((rect, slot))

        # Page buttons
        self.bank_btn_rects["page_prev"] = pygame.Rect(mid_x + 16, box.bottom - 58, 70, 24)
        self.bank_btn_rects["page_next"] = pygame.Rect(box.right - 90, box.bottom - 58, 70, 24)
        for key, label, enabled in (
            ("page_prev", "◀ Prev", self.bank_page > 0),
            ("page_next", "Next ▶", self.bank_page < max_page),
        ):
            r = self.bank_btn_rects[key]
            pygame.draw.rect(self.screen, (40, 55, 70) if enabled else (28, 30, 36), r, border_radius=4)
            pygame.draw.rect(self.screen, (100, 160, 210) if enabled else PANEL_LINE, r, 1, border_radius=4)
            txt = self.font_small.render(label, True, WHITE if enabled else GREY)
            self.screen.blit(txt, (r.x + (r.w - txt.get_width()) // 2, r.y + 4))

        tip = self.font_small.render(
            "Esc / X close  ·  Wheel scrolls side under cursor  ·  Ore limit 100",
            True, GREY,
        )
        self.screen.blit(tip, (box.x + 18, box.bottom - 26))

    def draw_equipment_modal(self):
        _bind_client_globals()
        import equipment_ui_v2
        equipment_ui_v2.draw(self, ITEMS, karma_slot_bonus, sprites, weapon_style)

    def draw_forge_modal(self):
        _bind_client_globals()
        box = pygame.Rect(100, 40, 620, 560)
        pygame.draw.rect(self.screen, (18, 20, 28), box)
        pygame.draw.rect(self.screen, (255, 160, 80), box, 2)
        if self.forge_station == "furnace" or self.forge_tab == "smelt":
            title_txt = "Furnace — Smelting"
        elif self.forge_station == "anvil" or self.forge_tab == "smith":
            title_txt = "Anvil — Smithing"
        else:
            title_txt = "Gareth's Smithy"
        title = self.font_big.render(title_txt, True, WHITE)
        self.screen.blit(title, (box.x + 16, box.y + 10))
        smith_lvl = (self.player.get("levels") or {}).get("smithing", 1)
        self.screen.blit(
            self.font.render(f"Smithing level: {smith_lvl}", True, YELLOW),
            (box.x + 400, box.y + 16),
        )

        # Locked to the station you clicked — no furnace/anvil tab swap
        self.forge_tab_rects = {}
        if self.forge_station is None:
            tabs = [("smelt", "1 Furnace"), ("smith", "2 Anvil")]
            for i, (key, label) in enumerate(tabs):
                r = pygame.Rect(box.x + 20 + i * 140, box.y + 46, 130, 28)
                self.forge_tab_rects[key] = r
                active = self.forge_tab == key
                pygame.draw.rect(self.screen, (55, 90, 50) if active else (35, 35, 45), r)
                pygame.draw.rect(self.screen, GREEN if active else PANEL_LINE, r, 2)
                txt = self.font.render(label, True, WHITE)
                self.screen.blit(txt, (r.x + (r.w - txt.get_width()) // 2, r.y + 4))
            filter_top = box.y + 82
        else:
            hint = "Smelt ores into bars" if self.forge_tab == "smelt" else "Smith bars into weapons & armour"
            self.screen.blit(self.font_small.render(hint, True, GREY), (box.x + 20, box.y + 48))
            filter_top = box.y + 72

        # Metal + gear type toggles
        self.forge_filter_rects = {}
        metal_opts = [
            ("all", "All"), ("bronze", "Brz"), ("iron", "Irn"), ("steel", "Stl"),
            ("mithril", "Mith"), ("adamant", "Addy"),
        ]
        gear_opts = (
            [("all", "All"), ("bar", "Bars")]
            if self.forge_tab == "smelt"
            else [
                ("all", "All"),
                ("weapon", "Weapons"),
                ("shield", "Shields"),
                ("helmet", "Helms"),
                ("body", "Bodies"),
                ("legs", "Legs"),
                ("jewelry", "Jewelry"),
            ]
        )
        y_filter = filter_top
        self.screen.blit(self.font_small.render("Metal:", True, GREY), (box.x + 20, y_filter + 6))
        x = box.x + 70
        for key, label in metal_opts:
            r = pygame.Rect(x, y_filter, 58, 24)
            self.forge_filter_rects[("metal", key)] = r
            active = self.forge_metal == key
            pygame.draw.rect(self.screen, (70, 60, 40) if active else (32, 34, 42), r)
            pygame.draw.rect(self.screen, (255, 200, 100) if active else PANEL_LINE, r, 1)
            txt = self.font_small.render(label, True, WHITE if active else GREY)
            self.screen.blit(txt, (r.x + (r.w - txt.get_width()) // 2, r.y + 4))
            x += 64

        y_filter2 = y_filter + 30
        self.screen.blit(self.font_small.render("Type:", True, GREY), (box.x + 20, y_filter2 + 6))
        x = box.x + 70
        for key, label in gear_opts:
            r = pygame.Rect(x, y_filter2, 78, 24)
            self.forge_filter_rects[("gear", key)] = r
            active = self.forge_gear == key
            pygame.draw.rect(self.screen, (40, 55, 70) if active else (32, 34, 42), r)
            pygame.draw.rect(self.screen, (140, 190, 255) if active else PANEL_LINE, r, 1)
            txt = self.font_small.render(label, True, WHITE if active else GREY)
            self.screen.blit(txt, (r.x + (r.w - txt.get_width()) // 2, r.y + 4))
            x += 84

        self.forge_recipe_rects = []
        matches = [
            (rid, recipe) for rid, recipe in self.craft_recipes.items()
            if recipe.get("category") == self.forge_tab and self._forge_recipe_matches(rid, recipe)
        ]
        list_top = y_filter2 + 40
        list_bottom = box.bottom - 36
        view_h = max(40, list_bottom - list_top)
        row_h = 48
        content_h = len(matches) * row_h
        max_scroll = max(0, content_h - view_h)
        self.forge_scroll_max = max_scroll
        self.forge_scroll = max(0, min(float(getattr(self, "forge_scroll", 0) or 0), max_scroll))
        list_area = pygame.Rect(box.x + 16, list_top, 588, view_h)
        prev_clip = self.screen.get_clip()
        self.screen.set_clip(list_area)
        y = list_top - self.forge_scroll
        shown = 0
        for rid, recipe in matches:
            row = pygame.Rect(box.x + 20, int(y), 560, 44)
            if row.bottom >= list_top and row.y <= list_bottom:
                pygame.draw.rect(self.screen, (38, 40, 50), row)
                pygame.draw.rect(self.screen, PANEL_LINE, row, 1)
                self.forge_recipe_rects.append((row, rid))

                out_id, out_qty = recipe["output"]
                icon = pygame.Rect(row.x + 8, row.y + 6, 32, 32)
                pygame.draw.rect(self.screen, (28, 28, 34), icon)
                sprites.draw_item_icon(self.screen, icon, out_id, ITEMS)

                need = ", ".join(f"{n}x {ITEMS[i]['name']}" for i, n in recipe["inputs"].items())
                locked = smith_lvl < recipe["level_req"]
                color = GREY if locked else WHITE
                self.screen.blit(self.font.render(recipe["name"], True, color), (row.x + 50, row.y + 4))
                self.screen.blit(
                    self.font_small.render(
                        f"Need: {need}   |  lvl {recipe['level_req']}  +{recipe['xp']} xp",
                        True, (200, 120, 120) if locked else GREY,
                    ),
                    (row.x + 50, row.y + 24),
                )
                shown += 1
            y += row_h
        self.screen.set_clip(prev_clip)

        if shown == 0:
            self.screen.blit(
                self.font.render("No recipes match these filters.", True, GREY),
                (box.x + 20, y_filter2 + 50),
            )

        tip = (
            "Furnace: smelt only · Esc / F closes"
            if self.forge_station == "furnace"
            else "Anvil: scroll for mithril · Esc / F closes"
            if self.forge_station == "anvil"
            else "Click furnace or anvil · Esc / F closes"
        )
        self.screen.blit(
            self.font_small.render(tip, True, GREY),
            (box.x + 20, box.y + box.h - 26),
        )

    def draw_cook_modal(self):
        _bind_client_globals()
        box = pygame.Rect(220, 80, 520, 420)
        pygame.draw.rect(self.screen, (18, 22, 28), box)
        pygame.draw.rect(self.screen, (255, 170, 90), box, 2)
        title = self.font_big.render("Cooking", True, WHITE)
        self.screen.blit(title, (box.x + 16, box.y + 12))
        cook_lvl = (self.player.get("levels") or {}).get("cooking", 1)
        self.screen.blit(
            self.font.render(f"Cooking level: {cook_lvl}", True, YELLOW),
            (box.x + 300, box.y + 18),
        )
        self.screen.blit(
            self.font_small.render(
                "Cook raw fish on a hearth or campfire. Higher Cooking = less burning.",
                True, GREY,
            ),
            (box.x + 16, box.y + 48),
        )

        self.cook_recipe_rects = []
        y = box.y + 80
        shown = 0
        for rid, recipe in self.craft_recipes.items():
            if recipe.get("category") != "cook":
                continue
            row = pygame.Rect(box.x + 16, y, 488, 52)
            pygame.draw.rect(self.screen, (38, 42, 50), row)
            pygame.draw.rect(self.screen, PANEL_LINE, row, 1)
            self.cook_recipe_rects.append((row, rid))

            out_id, _ = recipe["output"]
            icon = pygame.Rect(row.x + 8, row.y + 10, 32, 32)
            pygame.draw.rect(self.screen, (28, 28, 34), icon)
            sprites.draw_item_icon(self.screen, icon, out_id, ITEMS)

            need = ", ".join(f"{n}x {ITEMS[i]['name']}" for i, n in recipe["inputs"].items())
            heal = ITEMS.get(out_id, {}).get("heal", 0)
            locked = cook_lvl < recipe["level_req"]
            color = GREY if locked else WHITE
            burn_pct = int(round(cook_burn_chance(cook_lvl, recipe["level_req"]) * 100))
            self.screen.blit(self.font.render(recipe["name"], True, color), (row.x + 52, row.y + 6))
            self.screen.blit(
                self.font_small.render(
                    f"{need}  |  lvl {recipe['level_req']}  +{recipe['xp']} xp  ·  heals {heal} HP  ·  burn {burn_pct}%",
                    True, (200, 120, 120) if locked else GREY,
                ),
                (row.x + 52, row.y + 28),
            )
            y += 58
            shown += 1

        if shown == 0:
            self.screen.blit(
                self.font.render("No cooking recipes yet.", True, GREY),
                (box.x + 16, box.y + 90),
            )

        self.screen.blit(
            self.font_small.render("Click a recipe · choose Cook 1 or Cook all · Esc / C closes", True, GREY),
            (box.x + 16, box.y + box.h - 28),
        )

    def draw_fletch_modal(self):
        _bind_client_globals()
        box = pygame.Rect(100, 40, 620, 560)
        pygame.draw.rect(self.screen, (18, 24, 22), box)
        pygame.draw.rect(self.screen, (120, 200, 130), box, 2)
        title = self.font_big.render("Fletching", True, WHITE)
        self.screen.blit(title, (box.x + 16, box.y + 10))
        fletch_lvl = (self.player.get("levels") or {}).get("fletching", 1)
        self.screen.blit(
            self.font.render(f"Fletching level: {fletch_lvl}", True, YELLOW),
            (box.x + 380, box.y + 16),
        )
        self.screen.blit(
            self.font_small.render(
                "Knife required. Carve logs → shafts/bows, tip arrows, string bows.",
                True, GREY,
            ),
            (box.x + 16, box.y + 44),
        )

        tabs = [("all", "All"), ("shafts", "Shafts"), ("bows", "Bows"), ("arrows", "Arrows")]
        self.fletch_tab_rects = {}
        for i, (key, label) in enumerate(tabs):
            r = pygame.Rect(box.x + 16 + i * 100, box.y + 70, 92, 26)
            self.fletch_tab_rects[key] = r
            active = self.fletch_tab == key
            pygame.draw.rect(self.screen, (45, 80, 55) if active else (32, 36, 40), r)
            pygame.draw.rect(self.screen, GREEN if active else PANEL_LINE, r, 1)
            txt = self.font_small.render(label, True, WHITE if active else GREY)
            self.screen.blit(txt, (r.x + (r.w - txt.get_width()) // 2, r.y + 5))

        self.fletch_recipe_rects = []
        y = box.y + 108
        shown = 0
        for rid, recipe in self.craft_recipes.items():
            if recipe.get("category") != "fletch":
                continue
            name = recipe.get("name", "").lower()
            tab = self.fletch_tab
            if tab == "shafts" and "shaft" not in name and "headless" not in name:
                continue
            if tab == "bows" and "bow" not in name:
                continue
            if tab == "arrows" and "arrow" not in name:
                continue
            if shown >= 8:
                break
            row = pygame.Rect(box.x + 16, y, 588, 44)
            pygame.draw.rect(self.screen, (34, 42, 38), row)
            pygame.draw.rect(self.screen, PANEL_LINE, row, 1)
            self.fletch_recipe_rects.append((row, rid))

            out_id, out_qty = recipe["output"]
            icon = pygame.Rect(row.x + 8, row.y + 6, 32, 32)
            pygame.draw.rect(self.screen, (28, 28, 34), icon)
            sprites.draw_item_icon(self.screen, icon, out_id, ITEMS)

            need = ", ".join(f"{n}x {ITEMS[i]['name']}" for i, n in recipe["inputs"].items())
            locked = fletch_lvl < recipe["level_req"]
            color = GREY if locked else WHITE
            self.screen.blit(self.font.render(recipe["name"], True, color), (row.x + 50, row.y + 4))
            self.screen.blit(
                self.font_small.render(
                    f"{need}  →  {out_qty}x {ITEMS[out_id]['name']}  |  lvl {recipe['level_req']}  +{recipe['xp']} xp",
                    True, (200, 120, 120) if locked else GREY,
                ),
                (row.x + 50, row.y + 24),
            )
            y += 48
            shown += 1

        if shown == 0:
            self.screen.blit(
                self.font.render("No recipes match this filter.", True, GREY),
                (box.x + 16, box.y + 120),
            )
        self.screen.blit(
            self.font_small.render(
                "Click a recipe to craft 1  ·  Esc / N closes  ·  Talk to Elena (east) for a free kit & bow shop",
                True, GREY,
            ),
            (box.x + 16, box.y + box.h - 28),
        )

    def draw_skills_modal(self):
        _bind_client_globals()
        box = pygame.Rect(140, 40, 680, 560)
        pygame.draw.rect(self.screen, (16, 20, 28), box)
        pygame.draw.rect(self.screen, (120, 180, 255), box, 2)
        title = self.font_big.render("Skills", True, WHITE)
        self.screen.blit(title, (box.x + 20, box.y + 12))

        cmb = self.player_combat_level()
        tot = self.player_total_level()
        header = self.font.render(
            f"Combat level {cmb}    ·    Total level {tot}",
            True, YELLOW,
        )
        self.screen.blit(header, (box.x + 20, box.y + 48))
        standing = self.font_small.render(
            f"Standing: {self.player.get('rep_tier', 'Neutral')} ({int(self.player.get('reputation') or 0)})",
            True, (200, 180, 240),
        )
        self.screen.blit(standing, (box.right - standing.get_width() - 24, box.y + 52))
        # Work & Property (phase 4)
        work = self.player.get("work") or {}
        job, prop = work.get("job"), work.get("property")
        wy = box.y + 72
        for text in (
            f"Work: {job['workplace']} {job['today']}/{job['cap']} today · wages {job['last_wages']}"
            if job else "Work: none",
            f"Property: {prop['kind']} {prop['workers']}/{prop['slots']} · {prop['fee']}/day"
            f" · +{prop['last_income']}" if prop else "Property: none",
        ):
            surf = self.font_tiny.render(text, True, (190, 210, 180))
            self.screen.blit(surf, (box.right - surf.get_width() - 24, wy))
            wy += 13
        if self.player.get("kingdom"):
            ksurf = self.font_tiny.render(self.player["kingdom"] + "  (click for details)", True, (200, 180, 240))
            kpos = (box.x + 20, box.y + 86)
            self.screen.blit(ksurf, kpos)
            self._kingdom_rect = pygame.Rect(kpos, ksurf.get_size())
        hint = self.font_tiny.render(
            "Scroll wheel / ↑↓ / drag bar  ·  Esc / Tab closes",
            True, GREY,
        )
        self.screen.blit(hint, (box.x + 20, box.y + 74))

        header_y = box.y + 98
        headers = [
            ("Skill", 20), ("Level", 168), ("XP", 240),
            ("XP for level", 340), ("To next", 480),
        ]
        for text, ox in headers:
            self.screen.blit(self.font_small.render(text, True, ACCENT), (box.x + ox, header_y))
        pygame.draw.line(
            self.screen, PANEL_LINE,
            (box.x + 16, header_y + 22), (box.right - 16, header_y + 22), 1,
        )

        levels = self.player.get("levels") or {}
        xp_map = self.player.get("xp") or {}
        pot = self.player.get("stat_boosts") or {}
        row_h = 42
        skill_rows = ["hitpoints"] + list(XP_SKILLS)
        n_skills = len(skill_rows)
        list_top = header_y + 28
        list_bottom = box.bottom - 34
        view_h = max(40, list_bottom - list_top)
        content_h = n_skills * row_h
        max_scroll = max(0, content_h - view_h)
        self.skills_scroll = max(0, min(float(self.skills_scroll), max_scroll))
        self.skills_scroll_meta = {
            "list_top": list_top, "view_h": view_h, "max_scroll": max_scroll,
            "track": pygame.Rect(box.right - 22, list_top, 10, view_h),
        }

        prev_clip = self.screen.get_clip()
        self.screen.set_clip(pygame.Rect(box.x + 12, list_top, box.w - 40, view_h))

        y = list_top - self.skills_scroll
        for i, skill in enumerate(skill_rows):
            row_top = y
            y += row_h
            if row_top + row_h < list_top or row_top > list_bottom:
                continue
            if skill == "hitpoints":
                lvl = int((self.player or {}).get("max_hp") or 1)
                hp_now = int((self.player or {}).get("hp") or 0)
                tone, _pct = self.hp_tone(hp_now, lvl)
                row = pygame.Rect(box.x + 16, int(row_top), box.w - 48, row_h - 4)
                pygame.draw.rect(self.screen, (28, 34, 44), row, border_radius=4)
                self.screen.blit(self.font.render("Hitpoints", True, WHITE), (row.x + 8, row.y + 8))
                self.screen.blit(self.font.render(str(lvl), True, tone), (row.x + 156, row.y + 8))
                self.screen.blit(self.font_small.render(f"{hp_now}/{lvl}", True, tone), (row.x + 228, row.y + 8))
                self.screen.blit(self.font_small.render("—", True, GREY), (row.x + 340, row.y + 8))
                self.screen.blit(self.font_small.render("—", True, GREY), (row.x + 480, row.y + 8))
                continue
            lvl = int(levels.get(skill, 1))
            boost = 0
            buff = pot.get(skill) if skill in ("attack", "strength", "defence") else None
            if buff:
                boost = int(buff.get("amount") or 0)
                until = float(buff.get("until") or 0)
                if until and until <= time.time():
                    boost = 0
            eff = lvl + boost
            xp = int(xp_map.get(skill, 0))
            to_next = combat.xp_to_next_level(xp)
            xp_at_level = combat.xp_for_level(lvl)
            name = SKILL_DISPLAY_NAMES.get(skill, skill.title())
            row = pygame.Rect(box.x + 16, int(row_top), box.w - 48, row_h - 4)
            bg = (28, 34, 44) if i % 2 == 0 else (24, 28, 36)
            if boost > 0:
                bg = (36, 48, 32) if i % 2 == 0 else (30, 42, 28)
            pygame.draw.rect(self.screen, bg, row, border_radius=4)

            bar = pygame.Rect(row.x + 232, row.y + 26, 100, 5)
            pygame.draw.rect(self.screen, (40, 44, 54), bar, border_radius=3)
            if to_next > 0:
                next_thresh = combat.xp_for_level(lvl + 1)
                span = max(1, next_thresh - xp_at_level)
                done = max(0, min(1.0, (xp - xp_at_level) / span))
            else:
                done = 1.0
            if done > 0:
                fill = pygame.Rect(bar.x, bar.y, max(2, int(bar.w * done)), bar.h)
                pygame.draw.rect(self.screen, (80, 160, 220), fill, border_radius=3)

            self.screen.blit(self.font.render(name, True, WHITE), (row.x + 8, row.y + 8))
            if boost > 0:
                lvl_col = (110, 255, 130)
                self.screen.blit(self.font.render(str(eff), True, lvl_col), (row.x + 156, row.y + 8))
                self.screen.blit(
                    self.font_tiny.render(f"+{boost}", True, (255, 200, 90)),
                    (row.x + 186, row.y + 10),
                )
            else:
                self.screen.blit(self.font.render(str(lvl), True, (220, 230, 245)), (row.x + 156, row.y + 8))
            self.screen.blit(self.font_small.render(f"{xp:,}", True, (180, 200, 230)), (row.x + 228, row.y + 4))
            self.screen.blit(
                self.font_small.render(f"{xp_at_level:,}", True, GREY),
                (row.x + 340, row.y + 8),
            )
            next_txt = "MAX" if to_next <= 0 else f"{to_next:,}"
            self.screen.blit(self.font_small.render(next_txt, True, GREY), (row.x + 480, row.y + 8))

        self.screen.set_clip(prev_clip)

        if max_scroll > 0:
            track = self.skills_scroll_meta["track"]
            pygame.draw.rect(self.screen, (35, 40, 50), track, border_radius=4)
            thumb_h = max(28, int(view_h * view_h / content_h))
            thumb_y = list_top + int((view_h - thumb_h) * self.skills_scroll / max_scroll)
            thumb = pygame.Rect(track.x, thumb_y, track.w, thumb_h)
            self.skills_scroll_meta["thumb"] = thumb
            pygame.draw.rect(self.screen, (100, 150, 210), thumb, border_radius=4)
        else:
            self.skills_scroll_meta["thumb"] = None

        foot = self.font_tiny.render(
            "Green levels are potion boosts (temporary).  Combat = Att/Str/Def/HP + Archery.",
            True, (140, 138, 120),
        )
        self.screen.blit(foot, (box.x + 20, box.bottom - 28))

    def draw_pets_modal(self):
        _bind_client_globals()
        box = pygame.Rect(260, 100, 520, 420)
        pygame.draw.rect(self.screen, (16, 22, 30), box)
        pygame.draw.rect(self.screen, (120, 180, 230), box, 2)
        title = self.font_big.render("Your Pets", True, WHITE)
        self.screen.blit(title, (box.x + 18, box.y + 14))
        self.screen.blit(
            self.font_small.render(
                "Click to switch  ·  scroll / ↑↓  ·  Esc closes", True, GREY,
            ),
            (box.x + 18, box.y + 48),
        )

        owned = (self.player or {}).get("owned_pets") or []
        self.pet_switch_rects = []
        list_top = box.y + 80
        list_bottom = box.bottom - 36
        view_h = list_bottom - list_top
        row_h = 64
        if not owned:
            self.pets_scroll_meta = {"max_scroll": 0}
            self.screen.blit(
                self.font.render("You don't own any pets yet.", True, GREY),
                (box.x + 18, list_top),
            )
            return

        content_h = len(owned) * row_h
        max_scroll = max(0, content_h - view_h)
        self.pets_scroll = max(0, min(float(getattr(self, "pets_scroll", 0) or 0), max_scroll))
        self.pets_scroll_meta = {
            "list_top": list_top, "view_h": view_h, "max_scroll": max_scroll,
            "content_h": content_h,
            "track": pygame.Rect(box.right - 20, list_top, 10, view_h),
        }

        prev_clip = self.screen.get_clip()
        self.screen.set_clip(pygame.Rect(box.x + 8, list_top, box.w - 36, view_h))
        for i, entry in enumerate(owned):
            y = list_top - self.pets_scroll + i * row_h
            if y + 56 < list_top or y > list_bottom:
                continue
            row = pygame.Rect(box.x + 16, int(y), box.w - 44, 56)
            active = entry.get("active")
            pygame.draw.rect(self.screen, (42, 70, 50) if active else (34, 40, 52), row, border_radius=6)
            pygame.draw.rect(
                self.screen, GREEN if active else PANEL_LINE, row, 1, border_radius=6,
            )
            self.pet_switch_rects.append((row, entry.get("pet_id")))

            icon = pygame.Rect(row.x + 8, row.y + 6, 44, 44)
            pygame.draw.rect(self.screen, (24, 28, 36), icon)
            sprite_id = entry.get("sprite") or entry.get("pet_id")
            import pets_hd_client
            hd_icon = pets_hd_client.handles(sprite_id) and pets_hd_client.blit_icon(
                self.screen, sprite_id, icon, facing=1,
            )
            if not hd_icon and not (
                USE_NEW_PETS_AND_MONSTERS
                and legacy_creature_sprites.blit_pet_icon(
                    self.screen, sprite_id, icon, time.time(), facing=1,
                )
            ):
                icon_clip = self.screen.get_clip()
                self.screen.set_clip(icon.clip(pygame.Rect(box.x + 8, list_top, box.w - 36, view_h)))
                sprites.draw_pet(
                    self.screen, sprite_id,
                    icon.centerx, icon.bottom - 4, 18, time.time(),
                    facing=1,
                )
                self.screen.set_clip(icon_clip)
            name = entry.get("name", "?")
            lvl = entry.get("level", 1)
            status = "ACTIVE" if active else "Switch"
            self.screen.blit(self.font.render(name, True, WHITE), (row.x + 62, row.y + 10))
            self.screen.blit(
                self.font_small.render(f"Level {lvl}  ·  {status}", True, YELLOW if active else GREY),
                (row.x + 62, row.y + 32),
            )
        self.screen.set_clip(prev_clip)

        if max_scroll > 0:
            track = self.pets_scroll_meta["track"]
            pygame.draw.rect(self.screen, (35, 40, 50), track, border_radius=4)
            thumb_h = max(28, int(view_h * view_h / max(1, content_h)))
            thumb_y = list_top + int((view_h - thumb_h) * self.pets_scroll / max_scroll)
            thumb = pygame.Rect(track.x, thumb_y, track.w, thumb_h)
            self.pets_scroll_meta["thumb"] = thumb
            pygame.draw.rect(self.screen, (100, 160, 220), thumb, border_radius=4)
        else:
            self.pets_scroll_meta["thumb"] = None

        pygame.draw.rect(self.screen, (16, 22, 30), pygame.Rect(box.x + 2, box.bottom - 34, box.w - 4, 32))
        self.screen.blit(
            self.font_tiny.render("Buy more at Pet Emporium (Luna). Owned pets stay yours.", True, GREY),
            (box.x + 18, box.bottom - 28),
        )

    def handle_pets_click(self, mx, my):
        _bind_client_globals()
        box = pygame.Rect(260, 100, 520, 420)
        if not box.collidepoint(mx, my):
            self.show_pets = False
            return
        for rect, pet_id in self.pet_switch_rects:
            if rect.collidepoint(mx, my) and pet_id:
                self.net.send("SET_PET", pet_id=pet_id)
                return

    def draw_help_modal(self):
        _bind_client_globals()
        box = pygame.Rect(120, 30, 580, 640)
        pygame.draw.rect(self.screen, (16, 18, 26), box)
        pygame.draw.rect(self.screen, (120, 190, 255), box, 2)
        title = self.font_big.render("Controls", True, WHITE)
        self.screen.blit(title, (box.x + 16, box.y + 14))
        hint = self.font_tiny.render(
            "Scroll wheel / ↑↓ / drag bar  ·  H or Esc closes",
            True, GREY,
        )
        self.screen.blit(hint, (box.x + 16, box.y + 44))
        self.hd_look_rect = None  # old 2D/3D player toggle removed — HD villager only
        follow_on = bool(getattr(self, "ember_follow_behind", False))
        self.ember_follow_rect = pygame.Rect(box.x + 16, box.y + 66, 310, 28)
        pygame.draw.rect(self.screen, (32, 42, 68), self.ember_follow_rect, border_radius=14)
        pygame.draw.rect(self.screen, (212, 175, 90), self.ember_follow_rect, 1, border_radius=14)
        follow = self.font_small.render(
            "Camera follows behind: On" if follow_on else "Camera follows behind: Off",
            True, (232, 226, 210),
        )
        self.screen.blit(follow, (self.ember_follow_rect.x + 12, self.ember_follow_rect.y + 5))
        import outfit_fx
        st = outfit_fx.state
        self.outfit_fx_rect = pygame.Rect(box.x + 16, box.y + 100, 260, 28)
        self.outfit_fx_others_rect = pygame.Rect(box.x + 288, box.y + 100, 270, 28)
        for r, txt in ((self.outfit_fx_rect, "Outfit effects: " + st["mode"].capitalize()),
                       (self.outfit_fx_others_rect, "Others' outfit effects: " + ("On" if st["others"] else "Off"))):
            pygame.draw.rect(self.screen, (32, 42, 68), r, border_radius=14)
            pygame.draw.rect(self.screen, (212, 175, 90), r, 1, border_radius=14)
            self.screen.blit(self.font_small.render(txt, True, (232, 226, 210)), (r.x + 12, r.y + 5))

        sections = [
            ("Start here", [
                ("First talk", "Elder Miriam, northwest cottage — click her, then A"),
                ("Her quest", "Rat Problem: kill 5 giant rats in the mine, then return"),
                ("Walk", "Click the ground, or use the arrow keys for one tile"),
                ("Eat / fight", "R eats food · Space attacks the nearest monster"),
                ("Stuck", "H opens this list · Esc closes windows"),
            ]),
            ("Movement & combat", [
                ("Arrow keys", "Walk one tile (cancels click-walk)"),
                ("Click ground", "Walk there (yellow marker on path)"),
                ("Click monster / NPC", "Walk over, then attack / talk"),
                ("Space", "Run to nearest foe and attack (keeps chasing)"),
                ("R", "Eat strongest food in inventory"),
                ("Att/Str/Def/HP/Arch", "Combat XP style (sidebar or keys 1-5)"),
            ]),
            ("World", [
                ("Click ore / tree", "Walk over and gather (oak→willow→maple→yew→magic)"),
                ("Click shoreline water", "Walk beside it and fish"),
                ("Click door / entrance", "Walk through into the building or dungeon"),
                ("Click furnace", "Smelt ores into bars"),
                ("Click anvil", "Smith bars into weapons, armour & arrowtips"),
                ("Click hearth", "Cook raw fish into food"),
                ("Click campfire", "Cook on a fire you lit with logs + tinderbox"),
                ("Click bank booth", "Walk over and open bank"),
                ("Click loot / player", "Walk over and pick up / trade"),
                ("Use knife / logs", "Open Fletching (N) — shafts, bows, arrows"),
                ("Use logs", "Ask to light a fire with your tinderbox"),
                ("Use tinderbox", "Ask to light logs into a campfire"),
                ("G", "Pick up one stack on your tile"),
                ("Shift+G / Shift+click loot", "Take all items on the pile"),
                ("P / Coins+bones", "Toggle auto-pickup for coins & bones (above ATK/STR/DEF/RNG)"),
                ("X", "Toggle floating XP drops above your head (off = chat XP)"),
                ("Minimap left-click", "Walk toward that area · click again on the frame to hide/show"),
                ("Minimap right-click", "Open the world map (named buildings, click a pin to walk there)"),
                ("Minimap rim arrows", "A gold/white arrow at the edge = that place is off screen that way"),
                ("World map", "\"Center on me\" re-centres on you · red arrow at the edge points to you when panned away"),
            ]),
            ("Panels", [
                ("Travel / Bank / Gear", "Sidebar buttons (also M / B / E)"),
                ("Inventory / Combat / Magic / Quests", "Sidebar tabs"),
                ("E", "Equipment paperdoll + Combat tab (rotate right in Emberdeep)"),
                ("Magic tab", "Quest-point abilities · Auto/Manual toggle"),
                ("Manual magic", "Fight buttons under the map (shorter CD)"),
                ("Auto magic", "Casts strongest ready ability in combat"),
                ("F", "Forge UI (furnace or anvil only)"),
                ("C", "Cooking UI (hearth or campfire)"),
                ("N", "Fletching UI (knife in inventory)"),
                ("B", "Bank (walk to nearest booth / open if beside it)"),
                ("M", "Travel modal + minimap (places & monsters)"),
                ("H", "This help popup"),
                ("Tab", "Skills modal (levels, XP, combat & total)"),
                ("I", "Inventory sidebar tab"),
                ("Q", "Quests sidebar tab (rotate left in Emberdeep)"),
                ("1–5", "Combat XP style (or first-attack popup)"),
                ("Enter", "Open / send chat"),
                ("Scroll chat", "Mouse-wheel over chat to read history"),
                ("Zoom", "Mouse-wheel over map, or - / =  (zoom out shows more world)"),
                ("Esc", "Close popups / dialogue"),
                ("Logout", "Sidebar button — return to login screen"),
            ]),
            ("Dialogue / forge", [
                ("A / T", "Accept / turn in quest"),
                ("B", "Browse shop or open bank"),
                ("S", "Open forge at nearest furnace/anvil (talking to Gareth)"),
                ("Y / N", "Accept or decline trade"),
                ("Elena", "Bow shop east of village — free kit + fletching (B)"),
                ("Mira", "Stonehaven market — food, potions, steel (B)"),
            ]),
            ("Ranged combat", [
                ("Equip bow", "Locks combat to Archery — Att/Str/Def/HP greyed out"),
                ("Arrow Quiver", "Ammo slot — holds 1000 of each arrow type; fires best first"),
                ("Load arrows", "Click arrows or use the quiver to pack them from inventory"),
                ("Range", "Shoot from up to 4+ tiles; keep firing as the monster closes in"),
                ("Archery XP", "Damage & XP scale with Archery level (not Strength)"),
                ("Fletching", "Knife + N: logs→shafts/bows · shafts+feathers→headless · +tips→arrows"),
            ]),
            ("Crypt (early)", [
                ("Entrance", "Graveyard behind the bank — The Depths"),
                ("First quest", "Elder Miriam: Shadows in the Crypt (after Rat Problem)"),
                ("Why here", "Your first real delve — before Harbourreach / Tidehollow"),
            ]),
            ("Tidehollow (midgame)", [
                ("Cave mouth", "Harbourreach — private chamber dungeon (after the Crypt)"),
                ("Per room", "Three different beasts; dragons in the last chamber"),
                ("Clear all", "Open every sealed door; medal drops on completion"),
            ]),
            ("Emberdeep", [
                ("Volcano mouth", "East of Stonehaven — private 8-floor lava dungeon"),
                ("Travel", "Open Travel (T) → Emberdeep Volcano, or walk the east road"),
                ("Clear floor", "New magma beasts; floor 8 = Emberdeep Medal"),
            ]),
            ("Jewelry", [
                ("Shop", "Lira the Jeweler (east of Joe) — common rings/amulets + gems + Gem Bag"),
                ("Quest", "Lira's Lost Locket — find it by the wishing well"),
                ("Buys", "Sells commons only; buys all jewelry & gems (incl. rare) at 40%"),
                ("Craft", "Gem + metal bar at Gareth's anvil (filter: Jewelry); gems from Gem Bag first"),
                ("Niches", "Ruby=crit · Emerald=lifesteal · Diamond=dodge · Void=endgame drops"),
                ("Specials", "Ring+amulet stack; Combat tab shows worn totals"),
            ]),
            ("Limits", [
                ("Purse", "65,000 coins max on you"),
                ("Bank vault", "10,000,000 coins + 96 item slots"),
                ("Inventory", f"{INVENTORY_SIZE} item slots (4 tabs)"),
                ("Ores", "100 ores max in inventory (bank the rest)"),
            ]),
            ("Inventory", [
                ("Left-click", "Equip, eat, drink, use, or open bag Pack/Unpack"),
                ("Drag item", "Rearrange inventory slots"),
                ("Right-click", "Drop items, or bury bones (Bury 1 / Bury all)"),
                ("Shift+right", "Drop the whole stack immediately"),
                ("Bags", "Pack/Unpack storage bags; crafting draws from bags first"),
            ]),
            ("Bank", [
                ("Deposit inventory", "Banks every item you can store, including the Tidehollow Medal"),
                ("Vault click", "Withdraw stack · Shift+click = withdraw 1"),
                ("Shop sell", "Click = sell 1 · Shift+click = sell whole stack"),
                ("Esc", "Closes bank, shops, and most popups"),
            ]),
        ]

        list_top = box.y + 136
        list_bottom = box.bottom - 36
        view_h = max(40, list_bottom - list_top)
        key_w = 150
        desc_x = box.x + 28 + key_w
        desc_max_w = box.right - 36 - desc_x  # leave room for scrollbar

        def wrap_desc(text, max_w):
            words = text.split()
            if not words:
                return [""]
            lines, cur = [], words[0]
            for w in words[1:]:
                trial = f"{cur} {w}"
                if self.font_small.size(trial)[0] <= max_w:
                    cur = trial
                else:
                    lines.append(cur)
                    cur = w
            lines.append(cur)
            return lines

        # Measure full content height (with wrapped descriptions)
        content_h = 0
        layout = []  # (kind, text_or_pair, y_offset)
        for heading, rows in sections:
            layout.append(("heading", heading, content_h))
            content_h += 22
            for key, desc in rows:
                lines = wrap_desc(desc, desc_max_w)
                layout.append(("row", (key, lines), content_h))
                content_h += 17 * len(lines)
            content_h += 8

        max_scroll = max(0, content_h - view_h)
        self.help_scroll = max(0, min(float(self.help_scroll), max_scroll))
        self.help_scroll_meta = {
            "list_top": list_top, "view_h": view_h, "max_scroll": max_scroll,
            "content_h": content_h,
            "track": pygame.Rect(box.right - 20, list_top, 10, view_h),
        }

        prev_clip = self.screen.get_clip()
        self.screen.set_clip(pygame.Rect(box.x + 8, list_top, box.w - 32, view_h))

        for kind, payload, oy in layout:
            y = list_top - self.help_scroll + oy
            if kind == "heading":
                if y + 22 < list_top or y > list_bottom:
                    continue
                self.screen.blit(self.font.render(payload, True, YELLOW), (box.x + 20, int(y)))
            else:
                key, lines = payload
                row_h = 17 * len(lines)
                if y + row_h < list_top or y > list_bottom:
                    continue
                self.screen.blit(
                    self.font_small.render(f"{key:<16}", True, (160, 210, 255)),
                    (box.x + 28, int(y)),
                )
                for i, line in enumerate(lines):
                    self.screen.blit(
                        self.font_small.render(line, True, WHITE),
                        (desc_x, int(y + i * 17)),
                    )

        self.screen.set_clip(prev_clip)

        if max_scroll > 0:
            track = self.help_scroll_meta["track"]
            pygame.draw.rect(self.screen, (35, 40, 50), track, border_radius=4)
            thumb_h = max(28, int(view_h * view_h / max(1, content_h)))
            thumb_y = list_top + int((view_h - thumb_h) * self.help_scroll / max_scroll)
            thumb = pygame.Rect(track.x, thumb_y, track.w, thumb_h)
            self.help_scroll_meta["thumb"] = thumb
            pygame.draw.rect(self.screen, (100, 160, 220), thumb, border_radius=4)
        else:
            self.help_scroll_meta["thumb"] = None

        # Footer bar so text never sits under the close hint
        pygame.draw.rect(self.screen, (16, 18, 26), pygame.Rect(box.x + 2, box.bottom - 34, box.w - 4, 32))
        self.screen.blit(
            self.font_small.render("Press H or Esc to close  ·  click outside to close", True, GREY),
            (box.x + 20, box.y + box.h - 28),
        )

    def draw_leaderboard_modal(self):
        _bind_client_globals()
        box = pygame.Rect(160, 70, 780, 580)
        pygame.draw.rect(self.screen, (14, 16, 24), box)
        pygame.draw.rect(self.screen, (230, 190, 70), box, 2)
        title = self.font_big.render("Hiscores — Top Players & Guilds", True, YELLOW)
        self.screen.blit(title, (box.x + 20, box.y + 14))

        skills = self.leaderboard_skills or list(self.leaderboard.keys()) or (
            ["total", "guild"] + list(XP_SKILLS)
        )
        if not self.leaderboard_skill or self.leaderboard_skill not in skills:
            self.leaderboard_skill = "total" if "total" in skills else skills[0]
        guild_board = self.leaderboard_skill == "guild"
        self.leaderboard_tab_rects = {}
        tx, ty = box.x + 20, box.y + 55
        for skill in skills:
            if skill == "total":
                label = "Total"
            elif skill == "guild":
                label = "Guilds"
            else:
                label = SKILL_DISPLAY_NAMES.get(skill, skill.title())
            short = label if len(label) <= 10 else label[:8]
            tw = max(72, self.font_small.size(short)[0] + 16)
            if tx + tw > box.right - 20:
                tx = box.x + 20
                ty += 30
            r = pygame.Rect(tx, ty, tw, 26)
            self.leaderboard_tab_rects[skill] = r
            active = skill == self.leaderboard_skill
            fill = (70, 90, 40) if active else ((40, 48, 70) if skill == "guild" else (32, 34, 44))
            pygame.draw.rect(self.screen, fill, r)
            pygame.draw.rect(self.screen, YELLOW if active else PANEL_LINE, r, 1)
            txt = self.font_small.render(short, True, WHITE if active else GREY)
            self.screen.blit(txt, (r.x + (r.w - txt.get_width()) // 2, r.y + 5))
            tx += tw + 6

        header_y = ty + 44
        if guild_board:
            skill_name = "Guild"
            level_hdr, xp_hdr, name_hdr = "Σ Levels", "Σ XP", "Guild"
        elif self.leaderboard_skill == "total":
            skill_name = "Total"
            level_hdr, xp_hdr, name_hdr = "Total lvl", "Total XP", "Player"
        else:
            skill_name = SKILL_DISPLAY_NAMES.get(self.leaderboard_skill, self.leaderboard_skill.title())
            level_hdr, xp_hdr, name_hdr = "Level", "XP", "Player"
        skill_title = self.font.render(f"{skill_name} rankings", True, WHITE)
        self.screen.blit(skill_title, (box.x + 24, header_y))
        self.screen.blit(self.font_small.render("Rank", True, GREY), (box.x + 30, header_y + 30))
        self.screen.blit(self.font_small.render(name_hdr, True, GREY), (box.x + 90, header_y + 30))
        if guild_board:
            self.screen.blit(self.font_small.render("Members", True, GREY), (box.x + 320, header_y + 30))
            self.screen.blit(self.font_small.render(level_hdr, True, GREY), (box.x + 420, header_y + 30))
            self.screen.blit(self.font_small.render(xp_hdr, True, GREY), (box.x + 540, header_y + 30))
        else:
            self.screen.blit(self.font_small.render("Guild", True, GREY), (box.x + 280, header_y + 30))
            self.screen.blit(self.font_small.render(level_hdr, True, GREY), (box.x + 430, header_y + 30))
            self.screen.blit(self.font_small.render(xp_hdr, True, GREY), (box.x + 550, header_y + 30))

        rows = self.leaderboard.get(self.leaderboard_skill) or []
        list_top = header_y + 52
        list_bottom = box.bottom - 36
        row_h = 28
        view_h = max(1, list_bottom - list_top)
        max_scroll = max(0, len(rows) * row_h - view_h)
        self.leaderboard_max_scroll = max_scroll
        self.leaderboard_scroll = max(0, min(max_scroll, int(getattr(self, "leaderboard_scroll", 0) or 0)))
        empty = "No guilds yet — found one!" if guild_board else "No players yet — be the first!"
        if not rows:
            self.screen.blit(self.font.render(empty, True, GREY), (box.x + 30, list_top))
        else:
            clip = self.screen.get_clip()
            self.screen.set_clip(pygame.Rect(box.x + 16, list_top, box.w - 40, view_h))
            y = list_top - self.leaderboard_scroll
            for i, entry in enumerate(rows):
                if y + row_h >= list_top and y <= list_bottom:
                    rank_color = YELLOW if i == 0 else (200, 200, 210) if i < 3 else WHITE
                    pygame.draw.rect(self.screen, (28, 30, 40), (box.x + 24, y, 700, row_h - 2))
                    self.screen.blit(self.font_small.render(str(i + 1), True, rank_color), (box.x + 36, y + 4))
                    name = str(entry.get("name") or "?")
                    if len(name) > 22:
                        name = name[:21] + "…"
                    self.screen.blit(self.font_small.render(name, True, WHITE), (box.x + 90, y + 4))
                    if guild_board:
                        members = int(entry.get("members") or 0)
                        self.screen.blit(self.font_small.render(str(members), True, GREY), (box.x + 330, y + 4))
                        self.screen.blit(
                            self.font_small.render(f"{int(entry.get('level', 0) or 0):,}", True, GREEN),
                            (box.x + 430, y + 4),
                        )
                        xp_val = int(entry.get("xp", 0) or 0)
                        self.screen.blit(self.font_small.render(f"{xp_val:,}", True, GREY), (box.x + 540, y + 4))
                    else:
                        gname = str(entry.get("guild") or "—")
                        if len(gname) > 16:
                            gname = gname[:15] + "…"
                        self.screen.blit(
                            self.font_small.render(gname, True, (160, 190, 140) if entry.get("guild") else GREY),
                            (box.x + 280, y + 4),
                        )
                        self.screen.blit(
                            self.font_small.render(str(entry.get("level", 1)), True, GREEN),
                            (box.x + 440, y + 4),
                        )
                        xp_val = int(entry.get("xp", 0) or 0)
                        self.screen.blit(self.font_small.render(f"{xp_val:,}", True, GREY), (box.x + 550, y + 4))
                y += row_h
            self.screen.set_clip(clip)
            if max_scroll:
                track = pygame.Rect(box.right - 18, list_top, 8, view_h)
                pygame.draw.rect(self.screen, (32, 34, 44), track)
                thumb_h = max(24, int(view_h * view_h / (len(rows) * row_h)))
                thumb_y = list_top + int((view_h - thumb_h) * self.leaderboard_scroll / max_scroll)
                pygame.draw.rect(self.screen, (180, 150, 60), (track.x, thumb_y, track.w, thumb_h))

        self.screen.blit(
            self.font_small.render(
                "Scroll  ·  Arrows change tab  ·  Guilds = combined member levels/XP  ·  Esc closes",
                True, GREY,
            ),
            (box.x + 24, box.y + box.h - 28),
        )

    def handle_leaderboard_click(self, pos):
        _bind_client_globals()
        mx, my = pos
        for skill, rect in self.leaderboard_tab_rects.items():
            if rect.collidepoint(mx, my):
                if skill != self.leaderboard_skill:
                    self.leaderboard_scroll = 0
                self.leaderboard_skill = skill
                return
        box = pygame.Rect(160, 70, 780, 580)
        if not box.collidepoint(mx, my):
            self.show_leaderboard = False

