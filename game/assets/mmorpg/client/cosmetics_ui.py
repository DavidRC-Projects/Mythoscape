"""
Cosmetics UI Module: Character Creator, Hair Salon, Clothing Shop, Wardrobe

Handles all HD player appearance customization UIs.
"""
import os
import pygame

_BASE = os.path.join(os.path.dirname(__file__), "..", "..", "player_hd", "assets")
_CATALOGUE_PATH = os.path.join(_BASE, "catalogue.json")
_CATALOGUE = None


def _load_catalogue():
    global _CATALOGUE
    if _CATALOGUE is None:
        if not os.path.isfile(_CATALOGUE_PATH):
            _CATALOGUE = {}
        else:
            import json
            with open(_CATALOGUE_PATH, encoding="utf-8") as f:
                _CATALOGUE = json.load(f)
    return _CATALOGUE


def _items_by_slot(slot_name):
    """Return list of items for a slot (skin, hair, top, bottom, shoes, outfit, accessory)."""
    cat = _load_catalogue()
    return [item for item in cat.get("items", []) if item.get("slot") == slot_name]


def _hair_colours():
    """Return list of hair colour dicts."""
    cat = _load_catalogue()
    return cat.get("hair_colours", [])


def _starter_items(gender):
    """Return list of starter items for character creator (free, no purchase)."""
    cat = _load_catalogue()
    items = []
    for item in cat.get("items", []):
        if item.get("starter") and (item.get("gender_exclusive") is None or item.get("gender_exclusive") == gender):
            items.append(item)
    return items


# --- Character Creator (First Login) ---

class CharacterCreator:
    """
    Modal for new players to pick their first appearance.
    Opened automatically after LOGIN_OK when appearance is None.
    
    Flow:
    1. Pick gender (male/female)
    2. Pick skin tone
    3. Pick hair style
    4. Pick hair colour
    5. Pick starting outfit (free starter items)
    6. Confirm → send UPDATE_APPEARANCE
    """
    
    def __init__(self, client):
        self.client = client
        self.active = False
        self.gender = "male"
        self.appearance = {
            "skin": "skin_light",
            "hair": "hair_side_part",
            "hair_colour": "dark_brown",
            "top": "top_linen_shirt",
            "bottom": "bottom_work_trousers",
            "shoes": "shoes_leather",
            "outfit": None,
            "accessories": [],
        }
        self.stage = "gender"  # gender → skin → hair → hair_colour → outfit → confirm
        self.selected_slot = "skin"
        self.scroll = 0
        self.rects = []  # [(rect, item_id or colour_id), ...]
    
    def open(self, gender="male"):
        self.active = True
        self.gender = gender
        self.appearance = {
            "skin": "skin_light",
            "hair": "hair_side_part" if gender == "male" else "hair_ponytail",
            "hair_colour": "dark_brown",
            "top": "top_linen_shirt",
            "bottom": "bottom_work_trousers" if gender == "male" else "bottom_long_skirt",
            "shoes": "shoes_leather",
            "outfit": None,
            "accessories": [],
        }
        self.stage = "skin"
        self.scroll = 0
    
    def close(self):
        self.active = False
    
    def handle_click(self, mx, my):
        for rect, item_id in self.rects:
            if rect.collidepoint(mx, my):
                if self.stage == "hair_colour":
                    self.appearance["hair_colour"] = item_id
                else:
                    slot = self.stage if self.stage in ("skin", "hair") else "top"
                    self.appearance[self.stage] = item_id
                break
        
        # Next button
        next_btn = pygame.Rect(600, 700, 100, 40)
        if next_btn.collidepoint(mx, my):
            self._next_stage()
        
        # Confirm button (final stage)
        if self.stage == "confirm":
            confirm_btn = pygame.Rect(500, 700, 120, 40)
            if confirm_btn.collidepoint(mx, my):
                self._confirm()
    
    def _next_stage(self):
        stages = ["skin", "hair", "hair_colour", "outfit", "confirm"]
        idx = stages.index(self.stage) if self.stage in stages else 0
        if idx < len(stages) - 1:
            self.stage = stages[idx + 1]
            self.scroll = 0
    
    def _confirm(self):
        self.client.net.send("UPDATE_APPEARANCE", appearance=self.appearance)
        self.close()
    
    def handle_scroll(self, dy):
        self.scroll = max(0, self.scroll + dy)
    
    def render(self, surf):
        # Dark overlay
        overlay = pygame.Surface((1200, 800), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 180))
        surf.blit(overlay, (0, 0))
        
        # Modal box
        box = pygame.Rect(200, 100, 800, 600)
        pygame.draw.rect(surf, (40, 35, 30), box)
        pygame.draw.rect(surf, (200, 180, 140), box, 3)
        
        # Title
        font_big = self.client.font_big
        title_text = {
            "skin": "Choose Skin Tone",
            "hair": "Choose Hair Style",
            "hair_colour": "Choose Hair Colour",
            "outfit": "Choose Starting Outfit",
            "confirm": "Confirm Your Character",
        }.get(self.stage, "Character Creator")
        title = font_big.render(title_text, True, (255, 240, 200))
        surf.blit(title, (600 - title.get_width() // 2, 120))
        
        # Preview (left side)
        preview_x, preview_y = 280, 300
        self._render_preview(surf, preview_x, preview_y)
        
        # Options grid (right side)
        grid_x, grid_y = 520, 200
        self._render_options(surf, grid_x, grid_y)
        
        # Next / Confirm button
        if self.stage != "confirm":
            next_btn = pygame.Rect(600, 700, 100, 40)
            pygame.draw.rect(surf, (80, 120, 80), next_btn)
            pygame.draw.rect(surf, (150, 220, 150), next_btn, 2)
            next_text = self.client.font.render("Next", True, (255, 255, 255))
            surf.blit(next_text, (next_btn.centerx - next_text.get_width() // 2, next_btn.centery - next_text.get_height() // 2))
        else:
            confirm_btn = pygame.Rect(500, 700, 120, 40)
            pygame.draw.rect(surf, (100, 160, 100), confirm_btn)
            pygame.draw.rect(surf, (180, 255, 180), confirm_btn, 2)
            confirm_text = self.client.font.render("Confirm", True, (255, 255, 255))
            surf.blit(confirm_text, (confirm_btn.centerx - confirm_text.get_width() // 2, confirm_btn.centery - confirm_text.get_height() // 2))
    
    def _render_preview(self, surf, cx, cy):
        """Render live preview using player_hd_client."""
        import player_hd_client
        tile = 80  # 2x for nice preview
        player_hd_client.draw_player(
            surf, self.gender, self.appearance, cx, cy, tile, 0.0,
            anim="idle", facing=1,
        )
    
    def _render_options(self, surf, x, y):
        """Render scrollable grid of options."""
        self.rects = []
        if self.stage == "hair_colour":
            colours = _hair_colours()
            for i, hc in enumerate(colours[self.scroll:self.scroll + 12]):
                row, col = i // 4, i % 4
                rect = pygame.Rect(x + col * 110, y + row * 50, 100, 40)
                rgb = tuple(hc.get("rgb", [180, 180, 180]))
                pygame.draw.rect(surf, rgb, rect)
                pygame.draw.rect(surf, (255, 255, 255) if self.appearance["hair_colour"] == hc["id"] else (100, 100, 100), rect, 2)
                label = self.client.font_small.render(hc["name"], True, (0, 0, 0))
                surf.blit(label, (rect.centerx - label.get_width() // 2, rect.centery - label.get_height() // 2))
                self.rects.append((rect, hc["id"]))
        else:
            slot = self.stage if self.stage in ("skin", "hair") else "top"
            items = _starter_items(self.gender)
            items = [it for it in items if it.get("slot") == slot]
            for i, item in enumerate(items[self.scroll:self.scroll + 8]):
                row, col = i // 2, i % 2
                rect = pygame.Rect(x + col * 200, y + row * 60, 190, 50)
                selected = self.appearance.get(slot) == item["id"]
                pygame.draw.rect(surf, (60, 55, 50) if selected else (50, 45, 40), rect)
                pygame.draw.rect(surf, (200, 200, 140) if selected else (120, 110, 100), rect, 2)
                label = self.client.font_small.render(item["name"], True, (255, 240, 200))
                surf.blit(label, (rect.x + 10, rect.centery - label.get_height() // 2))
                self.rects.append((rect, item["id"]))


# --- Hair Salon ---
# (To be implemented: separate style and colour pickers, purchase with coins)

# --- Clothing Shop ---
# (To be implemented: browse all items, try-on preview, purchase)

# --- Wardrobe ---
# (To be implemented: equip owned cosmetics, save outfit slots)
