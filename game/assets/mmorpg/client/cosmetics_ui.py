"""Mythos Outfitters: one customisation screen for new characters and the shop."""
import os

import pygame

NAVY = (12, 18, 34)
NAVY_CARD = (20, 28, 48)
NAVY_HI = (32, 42, 68)
GOLD = (212, 175, 90)
GOLD_DIM = (120, 96, 52)
INK = (232, 226, 210)
MUTED = (150, 160, 180)
SAFE_GREEN = (72, 180, 110)

_BASE = os.path.join(os.path.dirname(__file__), "..", "..", "player_hd", "assets")
_CATALOGUE = None
_TABS = (
    ("body", "Body"),
    ("face", "Face"),
    ("hair", "Hair"),
    ("hair_colour", "Hair colour"),
    ("top", "Tops"),
    ("bottom", "Bottoms"),
    ("shoes", "Shoes"),
    ("outfit", "Outfits"),
    ("accessory", "Accessories"),
)
_FACINGS = (("s", "Front"), ("e", "Side"), ("n", "Back"))
_CROPS = {
    "hair": (0.15, 0.0, 0.7, 0.38),
    "top": (0.18, 0.22, 0.64, 0.38),
    "bottom": (0.22, 0.48, 0.56, 0.32),
    "shoes": (0.25, 0.72, 0.5, 0.26),
    "outfit": (0.12, 0.08, 0.76, 0.84),
    "skin": (0.2, 0.12, 0.6, 0.7),
    "accessory": (0.15, 0.18, 0.7, 0.5),
}


def _catalogue():
    global _CATALOGUE
    if _CATALOGUE is None:
        import json
        path = os.path.join(_BASE, "catalogue.json")
        if os.path.isfile(path):
            with open(path, encoding="utf-8") as handle:
                _CATALOGUE = json.load(handle)
        else:
            _CATALOGUE = {}
    return _CATALOGUE


def _items(slot):
    return [item for item in _catalogue().get("items", []) if item.get("slot") == slot]


def _by_id(item_id):
    for item in _catalogue().get("items", []):
        if item.get("id") == item_id:
            return item
    return None


class Outfitters:
    """Creator mode for a new account, shop mode when talking to Mae."""

    def __init__(self, client):
        self.client = client
        self.active = False
        self.mode = "shop"
        self.tab = "hair"
        self.sex = "male"
        self.facing_i = 0
        self.look = {}
        self.saved = {}
        self.scroll = 0
        self.dragging = False
        self.drag_x = 0
        self.hit = []
        self._thumbs = {}

    def open(self, mode="shop"):
        player = self.client.player or {}
        self.mode = "creator" if mode == "creator" else "shop"
        self.active = True
        self.sex = player.get("gender") or "male"
        self.tab = "hair" if self.mode == "creator" else "top"
        self.facing_i = 0
        self.scroll = 0
        import player_hd_client
        base = player.get("appearance") or player_hd_client.get_default_appearance(self.sex)
        self.look = {
            "skin": base.get("skin") or "skin_light",
            "hair": base.get("hair"),
            "hair_colour": base.get("hair_colour") or "dark_brown",
            "top": base.get("top"),
            "bottom": base.get("bottom"),
            "shoes": base.get("shoes"),
            "outfit": base.get("outfit"),
            "accessories": list(base.get("accessories") or []),
        }
        self.saved = dict(self.look)
        self.saved["accessories"] = list(self.look["accessories"])

    def close(self):
        if self.mode == "creator":
            return
        self.active = False
        self.dragging = False

    def handle_event(self, event):
        if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
            self.close()
            return
        if event.type == pygame.MOUSEWHEEL:
            self.scroll = max(0, self.scroll - int(event.y) * 40)
            return
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            self._click(event.pos)
        elif event.type == pygame.MOUSEMOTION and self.dragging:
            dx = event.pos[0] - self.drag_x
            if abs(dx) > 36:
                self.facing_i = (self.facing_i + (1 if dx > 0 else -1)) % 3
                self.drag_x = event.pos[0]
        elif event.type == pygame.MOUSEBUTTONUP and event.button == 1:
            self.dragging = False

    def _click(self, pos):
        mx, my = pos
        stage = pygame.Rect(60, 136, 400, 554)
        if stage.collidepoint(mx, my) and my < 210:
            self._toggle_sex()
            return
        if stage.collidepoint(mx, my):
            self.dragging = True
            self.drag_x = mx
        for kind, rect, payload in self.hit:
            if not rect.collidepoint(mx, my):
                continue
            self._activate(kind, payload)
            return

    def _toggle_sex(self):
        self.sex = "female" if self.sex == "male" else "male"
        import player_hd_client
        fresh = player_hd_client.get_default_appearance(self.sex)
        for key in ("hair", "top", "bottom", "shoes"):
            item = _by_id(self.look.get(key))
            if item and item.get("gender_exclusive") not in (None, self.sex):
                self.look[key] = fresh.get(key)
        if self.mode == "creator":
            self.client.net.send("SET_GENDER", gender=self.sex)
        self._thumbs.clear()

    def _activate(self, kind, payload):
        if kind == "close":
            self.close()
        elif kind == "tab":
            self.tab = payload
            self.scroll = 0
        elif kind == "turn":
            self.facing_i = (self.facing_i + payload) % 3
        elif kind == "item":
            self._pick_item(payload)
        elif kind == "colour":
            self.look["hair_colour"] = payload
        elif kind == "random":
            self._randomise()
        elif kind == "reset":
            self.look = dict(self.saved)
            self.look["accessories"] = list(self.saved.get("accessories") or [])
        elif kind == "skip":
            import player_hd_client
            look = player_hd_client.get_default_appearance(self.sex)
            self.client.needs_appearance = False
            self.client.net.send("UPDATE_APPEARANCE", appearance=look)
            self.active = False
        elif kind == "confirm":
            self.client.needs_appearance = False
            self.client.net.send("UPDATE_APPEARANCE", appearance=self._payload())
            self.active = False
        elif kind == "buy":
            ids, _cost = self._pending_purchase()
            if ids:
                self.client.net.send("BUY_COSMETICS", items=ids, appearance=self._payload())
            else:
                self.client.net.send("UPDATE_APPEARANCE", appearance=self._payload())
            self.saved = dict(self.look)
            self.saved["accessories"] = list(self.look["accessories"])
        elif kind == "save_slot":
            self.client.net.send("SAVE_OUTFIT", slot=int(payload), appearance=self._payload())
        elif kind == "wear_slot":
            outfits = (self.client.player or {}).get("saved_outfits") or []
            if 0 <= int(payload) < len(outfits) and outfits[int(payload)]:
                worn = outfits[int(payload)]
                self.look = dict(worn)
                self.look["accessories"] = list(worn.get("accessories") or [])
                self.client.net.send("UPDATE_APPEARANCE", appearance=self._payload())
        elif kind == "save_current":
            self.client.net.send("SAVE_OUTFIT", slot=0, appearance=self._payload())

    def _payload(self):
        return {
            "skin": self.look.get("skin"),
            "hair": self.look.get("hair"),
            "hair_colour": self.look.get("hair_colour"),
            "top": self.look.get("top"),
            "bottom": self.look.get("bottom"),
            "shoes": self.look.get("shoes"),
            "outfit": self.look.get("outfit"),
            "accessories": list(self.look.get("accessories") or []),
        }

    def _owned(self):
        raw = (self.client.player or {}).get("owned_cosmetics") or []
        return set(raw)

    def _pick_item(self, item):
        if self.mode == "creator" and not item.get("starter"):
            return
        slot = item.get("slot")
        if slot == "accessory":
            acc = list(self.look.get("accessories") or [])
            if item["id"] in acc:
                acc.remove(item["id"])
            else:
                limit = int(_catalogue().get("accessory_max") or 2)
                if len(acc) >= limit:
                    acc = acc[1:]
                acc.append(item["id"])
            self.look["accessories"] = acc
            return
        if slot == "outfit" and self.look.get("outfit") == item["id"]:
            self.look["outfit"] = None
            return
        self.look[slot] = item["id"]

    def _randomise(self):
        import random
        import player_hd_client
        owned = self._owned()
        for slot, key in (
            ("skin", "skin"), ("hair", "hair"), ("top", "top"),
            ("bottom", "bottom"), ("shoes", "shoes"),
        ):
            pool = []
            for item in _items(slot):
                if item.get("gender_exclusive") not in (None, self.sex):
                    continue
                if self.mode == "creator" and not item.get("starter"):
                    continue
                if self.mode == "shop" and not item.get("starter") and item["id"] not in owned:
                    continue
                pool.append(item)
            if not pool:
                pool = [item for item in _items(slot) if item.get("starter")]
            if pool:
                self.look[key] = random.choice(pool)["id"]
        colours = _catalogue().get("hair_palette") or []
        if colours:
            self.look["hair_colour"] = random.choice(colours)["id"]
        self.look["outfit"] = None
        self.look["accessories"] = []
        if not self.look.get("skin"):
            self.look.update(player_hd_client.get_default_appearance(self.sex))

    def _selected_ids(self):
        ids = []
        for key in ("skin", "hair", "top", "bottom", "shoes", "outfit"):
            if self.look.get(key):
                ids.append(self.look[key])
        ids.extend(self.look.get("accessories") or [])
        return ids

    def _pending_purchase(self):
        owned = self._owned()
        names = []
        cost = 0
        ids = []
        for item_id in self._selected_ids():
            item = _by_id(item_id)
            if not item or item.get("starter") or item_id in owned:
                continue
            ids.append(item_id)
            names.append(item.get("name") or item_id)
            cost += int(item.get("price") or 0)
        return ids, cost, names

    def render(self, surf):
        self.hit = []
        shade = pygame.Surface((1200, 800), pygame.SRCALPHA)
        shade.fill((4, 6, 14, 190))
        surf.blit(shade, (0, 0))
        panel = pygame.Rect(40, 30, 1120, 740)
        pygame.draw.rect(surf, NAVY, panel, border_radius=14)
        pygame.draw.rect(surf, GOLD, panel, 2, border_radius=14)
        inner = panel.inflate(-8, -8)
        pygame.draw.rect(surf, GOLD_DIM, inner, 1, border_radius=12)
        font = self.client.font_big
        small = self.client.font_small
        tiny = self.client.font_tiny
        if self.mode == "creator":
            title, sub = "Create your adventurer", "Choose how you look. You can change it later at Mythos Outfitters."
        else:
            title, sub = "Mythos Outfitters", "Hair, clothing and outfits. Try anything on before you buy."
        surf.blit(font.render(title, True, GOLD), (72, 50))
        surf.blit(tiny.render(sub, True, MUTED), (72, 86))
        if self.mode != "creator":
            close = pygame.Rect(1088, 48, 36, 32)
            pygame.draw.rect(surf, NAVY_CARD, close, border_radius=6)
            pygame.draw.rect(surf, GOLD_DIM, close, 1, border_radius=6)
            mark = small.render("X", True, INK)
            surf.blit(mark, (close.centerx - mark.get_width() // 2, close.y + 6))
            self.hit.append(("close", close, None))
        pygame.draw.line(surf, GOLD_DIM, (60, 120), (1140, 120), 1)
        self._draw_stage(surf)
        self._draw_tabs(surf)
        self._draw_grid(surf)
        self._draw_swatches(surf)
        pygame.draw.line(surf, GOLD_DIM, (60, 702), (1140, 702), 1)
        self._draw_footer(surf)

    def _draw_stage(self, surf):
        stage = pygame.Rect(60, 136, 400, 554)
        pygame.draw.rect(surf, NAVY_CARD, stage, border_radius=12)
        pygame.draw.rect(surf, GOLD_DIM, stage, 1, border_radius=12)
        glow = pygame.Surface((220, 220), pygame.SRCALPHA)
        pygame.draw.circle(glow, (80, 90, 130, 70), (110, 110), 100)
        surf.blit(glow, (stage.centerx - 110, stage.y + 150))
        plinth = pygame.Rect(stage.centerx - 70, stage.bottom - 150, 140, 28)
        pygame.draw.ellipse(surf, GOLD_DIM, plinth, 2)
        import player_hd_client
        face = _FACINGS[self.facing_i][0]
        player_hd_client.draw_player(
            surf, self.sex, self.look, stage.centerx, plinth.centery, 216, 0.0,
            anim="idle", facing=face, equipment=None,
        )
        pill = pygame.Rect(stage.centerx - 78, stage.y + 16, 156, 32)
        pygame.draw.rect(surf, NAVY, pill, border_radius=16)
        pygame.draw.rect(surf, GOLD_DIM, pill, 1, border_radius=16)
        male = pygame.Rect(pill.x + 4, pill.y + 4, 72, 24)
        female = pygame.Rect(pill.x + 80, pill.y + 4, 72, 24)
        on = male if self.sex == "male" else female
        pygame.draw.rect(surf, GOLD, on, border_radius=12)
        tiny = self.client.font_tiny
        for rect, label, sex in ((male, "Male", "male"), (female, "Female", "female")):
            colour = NAVY if self.sex == sex else INK
            text = tiny.render(label, True, colour)
            surf.blit(text, (rect.centerx - text.get_width() // 2, rect.y + 4))
        left = pygame.Rect(stage.x + 24, stage.bottom - 58, 36, 36)
        right = pygame.Rect(stage.right - 60, stage.bottom - 58, 36, 36)
        for rect, step in ((left, -1), (right, 1)):
            pygame.draw.circle(surf, NAVY, rect.center, 16)
            pygame.draw.circle(surf, GOLD, rect.center, 16, 1)
            self.hit.append(("turn", rect, step))
        surf.blit(tiny.render("<", True, GOLD), (left.x + 12, left.y + 8))
        surf.blit(tiny.render(">", True, GOLD), (right.x + 12, right.y + 8))
        label = _FACINGS[self.facing_i][1]
        hint = tiny.render("Drag or use arrows to turn", True, MUTED)
        surf.blit(hint, (stage.centerx - hint.get_width() // 2, stage.bottom - 70))
        names = tiny.render("Front    Side    Back", True, MUTED)
        surf.blit(names, (stage.centerx - names.get_width() // 2, stage.bottom - 50))
        current = tiny.render(label, True, GOLD)
        surf.blit(current, (stage.centerx - current.get_width() // 2, stage.bottom - 32))

    def _tabs(self):
        tabs = list(_TABS)
        if self.mode == "shop":
            tabs.append(("wardrobe", "Wardrobe"))
        return tabs

    def _draw_tabs(self, surf):
        y = 136
        small = self.client.font_small
        for key, label in self._tabs():
            rect = pygame.Rect(480, y, 150, 44)
            active = key == self.tab
            pygame.draw.rect(surf, NAVY_HI if active else NAVY_CARD, rect, border_radius=8)
            pygame.draw.rect(surf, GOLD if active else GOLD_DIM, rect, 1, border_radius=8)
            if active:
                pygame.draw.rect(surf, GOLD, (rect.x, rect.y + 8, 4, rect.h - 16))
            text = small.render(label, True, INK if active else MUTED)
            surf.blit(text, (rect.x + 16, rect.centery - text.get_height() // 2))
            self.hit.append(("tab", rect, key))
            y += 50

    def _draw_grid(self, surf):
        grid = pygame.Rect(650, 136, 490, 484)
        pygame.draw.rect(surf, NAVY_CARD, grid, border_radius=12)
        pygame.draw.rect(surf, GOLD_DIM, grid, 1, border_radius=12)
        title = self.client.font_small.render(dict(self._tabs()).get(self.tab, ""), True, GOLD)
        surf.blit(title, (grid.x + 16, grid.y + 10))
        if self.tab == "wardrobe":
            self._draw_wardrobe(surf, grid)
            return
        if self.tab == "hair_colour":
            return
        slot = {"body": "skin", "face": "skin"}.get(self.tab, self.tab)
        items = [
            item for item in _items(slot)
            if item.get("gender_exclusive") in (None, self.sex)
        ]
        if self.tab == "outfit":
            items = [{"id": None, "slot": "outfit", "name": "No outfit", "price": 0, "starter": True}] + items
        cols, card_w, card_h, gap = 4, 108, 132, 12
        origin_y = grid.y + 40 - self.scroll
        clip = surf.get_clip()
        surf.set_clip(pygame.Rect(grid.x + 8, grid.y + 36, grid.w - 16, grid.h - 44))
        for i, item in enumerate(items):
            col, row = i % cols, i // cols
            rect = pygame.Rect(grid.x + 14 + col * (card_w + gap), origin_y + row * (card_h + gap), card_w, card_h)
            if rect.bottom < grid.y + 36 or rect.top > grid.bottom:
                continue
            selected = self._is_selected(item)
            pygame.draw.rect(surf, NAVY, rect, border_radius=8)
            pygame.draw.rect(surf, GOLD if selected else GOLD_DIM, rect, 3 if selected else 1, border_radius=8)
            if item.get("id"):
                thumb = self._thumb(item)
                if thumb:
                    surf.blit(thumb, (rect.centerx - thumb.get_width() // 2, rect.y + 8))
            name = self.client.font_tiny.render(self._fit(item.get("name") or "", 16), True, INK)
            surf.blit(name, (rect.centerx - name.get_width() // 2, rect.bottom - 36))
            price = self._price_label(item)
            colour = SAFE_GREEN if price in ("Free", "Owned") else (MUTED if price == "In shop" else GOLD)
            line = self.client.font_tiny.render(price, True, colour)
            surf.blit(line, (rect.centerx - line.get_width() // 2, rect.bottom - 20))
            if selected:
                tick = self.client.font_tiny.render("ok", True, GOLD)
                surf.blit(tick, (rect.right - 22, rect.y + 6))
            if item.get("id"):
                self.hit.append(("item", rect, item))
            elif self.tab == "outfit":
                self.hit.append(("item", rect, {"id": None, "slot": "outfit", "starter": True, "name": "No outfit"}))
        surf.set_clip(clip)

    def _draw_wardrobe(self, surf, grid):
        tiny = self.client.font_tiny
        outfits = (self.client.player or {}).get("saved_outfits") or []
        y = grid.y + 44
        for i in range(3):
            rect = pygame.Rect(grid.x + 16, y, grid.w - 32, 44)
            pygame.draw.rect(surf, NAVY, rect, border_radius=8)
            pygame.draw.rect(surf, GOLD_DIM, rect, 1, border_radius=8)
            surf.blit(tiny.render(f"Outfit {i + 1}", True, INK), (rect.x + 12, rect.y + 12))
            save = pygame.Rect(rect.right - 150, rect.y + 8, 64, 28)
            wear = pygame.Rect(rect.right - 78, rect.y + 8, 64, 28)
            for button, label, kind in ((save, "Save", "save_slot"), (wear, "Wear", "wear_slot")):
                pygame.draw.rect(surf, NAVY_HI, button, border_radius=6)
                pygame.draw.rect(surf, GOLD_DIM, button, 1, border_radius=6)
                text = tiny.render(label, True, INK)
                surf.blit(text, (button.centerx - text.get_width() // 2, button.y + 6))
                self.hit.append((kind, button, i))
            y += 52
        owned = self._owned()
        surf.blit(tiny.render("Owned pieces", True, MUTED), (grid.x + 16, y + 6))

    def _draw_swatches(self, surf):
        colours = _catalogue().get("hair_palette") or []
        tiny = self.client.font_tiny
        surf.blit(tiny.render("Hair colour", True, INK), (660, 632))
        x = 760
        for colour in colours:
            rect = pygame.Rect(x, 628, 22, 22)
            pygame.draw.circle(surf, tuple(colour.get("mul") or (80, 80, 80)), rect.center, 9)
            if self.look.get("hair_colour") == colour.get("id"):
                pygame.draw.circle(surf, GOLD, rect.center, 11, 2)
            self.hit.append(("colour", rect, colour.get("id")))
            x += 26
        if self.tab == "hair_colour":
            grid = pygame.Rect(670, 180, 450, 400)
            gx, gy = grid.x, grid.y
            for colour in colours:
                rect = pygame.Rect(gx, gy, 72, 72)
                pygame.draw.circle(surf, tuple(colour.get("mul") or (80, 80, 80)), rect.center, 24)
                if self.look.get("hair_colour") == colour.get("id"):
                    pygame.draw.circle(surf, GOLD, rect.center, 28, 3)
                self.hit.append(("colour", rect, colour.get("id")))
                gx += 88
                if gx > grid.right - 72:
                    gx = grid.x
                    gy += 88

    def _draw_footer(self, surf):
        tiny = self.client.font_tiny
        small = self.client.font_small
        if self.mode == "creator":
            note = tiny.render("Everything here is free. More styles at Mythos Outfitters in the village.", True, MUTED)
            surf.blit(note, (60, 716))
            note2 = tiny.render("Skip uses the basic look for your body type.", True, MUTED)
            surf.blit(note2, (60, 736))
            buttons = (("random", "Randomise", False), ("reset", "Reset", False), ("skip", "Skip", False), ("confirm", "Confirm look", True))
        else:
            coins = int((self.client.player or {}).get("coins") or 0)
            pygame.draw.circle(surf, GOLD, (78, 732), 10)
            surf.blit(small.render(f"{coins:,} coins", True, INK), (96, 722))
            ids, cost, names = self._pending_purchase()
            if names:
                trying = "Trying on: " + ", ".join(names[:3])
                extra = tiny.render(f"Total {cost:,} coins. Owned items are free to wear.", True, MUTED)
            else:
                trying = "Trying on: nothing new"
                extra = tiny.render("Owned items are free to wear.", True, MUTED)
            surf.blit(tiny.render(trying, True, INK), (280, 716))
            surf.blit(extra, (280, 736))
            buy = f"Buy & wear {cost:,}" if cost else "Wear"
            buttons = (("random", "Randomise", False), ("reset", "Reset", False), ("save_current", "Save outfit", False), ("buy", buy, True))
        x = 700 if self.mode == "creator" else 620
        for kind, label, primary in buttons:
            width = 150 if primary else 110
            rect = pygame.Rect(x, 718, width, 36)
            pygame.draw.rect(surf, GOLD if primary else NAVY_HI, rect, border_radius=8)
            pygame.draw.rect(surf, GOLD, rect, 1, border_radius=8)
            text = small.render(label, True, NAVY if primary else INK)
            surf.blit(text, (rect.centerx - text.get_width() // 2, rect.centery - text.get_height() // 2))
            self.hit.append((kind, rect, None))
            x += width + 10

    def _is_selected(self, item):
        if item.get("slot") == "accessory":
            return item.get("id") in (self.look.get("accessories") or [])
        if item.get("slot") == "outfit" and not item.get("id"):
            return not self.look.get("outfit")
        return self.look.get(item.get("slot")) == item.get("id")

    def _price_label(self, item):
        if not item.get("id"):
            return "Free"
        if self.mode == "creator":
            return "Free" if item.get("starter") else "In shop"
        if item.get("starter") or item["id"] in self._owned():
            return "Owned" if not item.get("starter") else "Free"
        return f"{int(item.get('price') or 0):,} coins"

    def _fit(self, text, limit):
        if len(text) <= limit:
            return text
        return text[: limit - 1] + "."

    def _thumb(self, item):
        key = (self.sex, item.get("id"), self.look.get("hair_colour"), self.look.get("skin"))
        cached = self._thumbs.get(key)
        if cached is not None:
            return cached
        import player_hd_client
        look = dict(self.look)
        look["accessories"] = list(self.look.get("accessories") or [])
        slot = item.get("slot")
        if slot == "accessory":
            look["accessories"] = [item["id"]]
        elif slot:
            look[slot] = item["id"]
        canvas = pygame.Surface((160, 200), pygame.SRCALPHA)
        player_hd_client.draw_player(canvas, self.sex, look, 80, 170, 80, 0.0, anim="idle", facing="s")
        box = canvas.get_bounding_rect()
        if box.w < 4 or box.h < 4:
            self._thumbs[key] = None
            return None
        crop = _CROPS.get(slot, (0.2, 0.1, 0.6, 0.7))
        rect = pygame.Rect(
            box.x + int(box.w * crop[0]),
            box.y + int(box.h * crop[1]),
            max(8, int(box.w * crop[2])),
            max(8, int(box.h * crop[3])),
        )
        rect = rect.clamp(canvas.get_rect())
        image = canvas.subsurface(rect).copy()
        image = pygame.transform.smoothscale(image, (72, 64))
        self._thumbs[key] = image
        return image
