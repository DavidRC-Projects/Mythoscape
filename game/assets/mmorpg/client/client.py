"""
MMORPG v0.1 client. Run with:  python client.py [server_host]

Requires: pip install pygame websockets
"""
import sys
import os
import time

import pygame

from network import NetworkClient

# Reuse the server's static content module for item names/icons/etc so the
# client doesn't have to duplicate a second copy of the game data.
_HERE = os.path.dirname(__file__)
sys.path.insert(0, os.path.join(_HERE, "..", "server"))
sys.path.insert(0, os.path.join(_HERE, "..", "..", "characters"))
from content import ITEMS  # noqa: E402
import world_map as wm  # noqa: E402
import procedural_sprites_finished as sprites  # noqa: E402

SERVER_HOST = sys.argv[1] if len(sys.argv) > 1 else "localhost"
SERVER_URI = f"ws://{SERVER_HOST}:8765"

SCREEN_W, SCREEN_H = 1100, 760
MAP_W, MAP_H = 820, 600
SIDEBAR_X = MAP_W
TILE = 22

WHITE = (240, 240, 240)
BLACK = (10, 10, 10)
RED = (220, 60, 60)
GREEN = (70, 210, 90)
YELLOW = (230, 210, 60)
GREY = (150, 150, 150)
PANEL_BG = (28, 28, 34)
PANEL_LINE = (60, 60, 70)

ROCK_LOOK = {
    "copper_rock": ((190, 120, 60), (230, 180, 100)),
    "tin_rock": ((160, 160, 170), (210, 210, 220)),
    "iron_rock": ((130, 90, 70), (180, 140, 100)),
}
ROBED_NPC_IDS = {
    "elder_miriam", "priest_cedric", "monk_healer", "mysterious_traveler",
}


def weapon_style(item_id):
    if not item_id:
        return None
    if "dagger" in item_id:
        return "dagger"
    if "pickaxe" in item_id:
        return "pickaxe"
    if "axe" in item_id:
        return "axe"
    if "sword" in item_id:
        return "sword"
    return "sword"


class GameClient:
    def __init__(self):
        pygame.init()
        pygame.display.set_caption("Tiny MMORPG v0.1")
        self.screen = pygame.display.set_mode((SCREEN_W, SCREEN_H))
        self.clock = pygame.time.Clock()
        self.font = pygame.font.SysFont("consolas", 15)
        self.font_small = pygame.font.SysFont("consolas", 12)
        self.font_big = pygame.font.SysFont("consolas", 22, bold=True)

        self.net = NetworkClient(SERVER_URI)
        self.net.start()

        self.state = "LOGIN"
        self.login_mode = "login"  # or "register"
        self.fields = {"username": "", "password": "", "char_name": ""}
        self.active_field = "username"
        self.login_error = ""

        # world / game state
        self.tiles = []
        self.world_w = self.world_h = 0
        self.npcs = []
        self.resources = {}  # "x,y" -> type
        self.players = {}    # id -> public state
        self.monsters = {}   # id -> public state
        self.ground_items = {}
        self.player = None   # full state dict (self)
        self.quests = {}

        self.chat_log = []
        self.chat_typing = False
        self.chat_text = ""

        self.dialogue = None       # {"npc_id","npc_name","lines","shop_id","quest":{...}}
        self.shop = None           # {"shop_id","name","stock","your_coins"}
        self.show_shop_panel = False
        self.trade_incoming = None  # {"from_player_id","from_name"}
        self.trade_state = None     # {"other_name","your_offer","other_offer",...}

        self.floaters = []  # floating combat text: [x,y,text,color,expire_time]
        self.show_inventory = True
        self.show_stats = True
        self.show_quests = False
        self._prev_entity_pos = {}  # id -> (x, y) for walk animation

        self.running = True
        pygame.key.set_repeat(180, 120)

    # ------------------------------------------------------------------
    def run(self):
        while self.running:
            self.handle_network()
            self.handle_events()
            self.draw()
            self.clock.tick(60)
        pygame.quit()

    # ------------------------------------------------------------------
    def handle_network(self):
        for msg in self.net.poll():
            self.process_message(msg)

    def process_message(self, msg):
        t = msg.get("type")
        if t == "_CONN_ERROR":
            self.login_error = msg["message"]
        elif t == "_DISCONNECTED":
            if self.state == "GAME":
                self.login_error = "Disconnected from server."
                self.state = "LOGIN"
        elif t == "LOGIN_FAIL":
            self.login_error = msg["reason"]
        elif t == "LOGIN_OK":
            self.player = msg["player"]
            self.state = "GAME"
            self.login_error = ""
        elif t == "WORLD_STATE":
            self.tiles = msg["tiles"]
            self.world_w, self.world_h = msg["width"], msg["height"]
            self.npcs = msg["npcs"]
            self.resources = msg["resources"]
        elif t == "STATE_UPDATE":
            self.players = {p["id"]: p for p in msg["players"]}
            self.monsters = {m["id"]: m for m in msg["monsters"]}
            self.ground_items = msg.get("ground_items", {})
            if "resources" in msg:
                self.resources = msg["resources"]
            # Keep local player coords in sync so the camera can follow.
            if self.player and self.player["id"] in self.players:
                live = self.players[self.player["id"]]
                self.player["x"] = live["x"]
                self.player["y"] = live["y"]
                self.player["hp"] = live["hp"]
                self.player["max_hp"] = live["max_hp"]
        elif t == "PLAYER_UPDATE":
            self.player = msg["player"]
            # Mirror into the shared players dict so sprites stay consistent.
            if self.player:
                self.players[self.player["id"]] = {
                    "id": self.player["id"],
                    "name": self.player["name"],
                    "x": self.player["x"],
                    "y": self.player["y"],
                    "hp": self.player["hp"],
                    "max_hp": self.player["max_hp"],
                    "equipment": self.player.get("equipment"),
                }
        elif t == "CHAT_MSG":
            self.chat_log.append(f"{msg['from']}: {msg['text']}")
            self.chat_log = self.chat_log[-8:]
        elif t == "COMBAT_EVENT":
            self.handle_combat_event(msg)
        elif t == "DEATH":
            if msg["entity_kind"] == "player" and msg["entity_id"] == (self.player or {}).get("id"):
                self.chat_log.append("*** You have died and respawned in the village. ***")
        elif t == "LOOT_DROPPED":
            pass
        elif t == "SKILL_XP":
            if msg.get("leveled_up"):
                self.chat_log.append(f"Congratulations! {msg['skill'].title()} level up: {msg['level']}!")
        elif t == "DIALOGUE":
            self.dialogue = {
                "npc_id": msg["npc_id"], "npc_name": msg["npc_name"], "lines": msg["lines"],
                "shop_id": msg.get("shop_id"), "quest": msg.get("quest"),
            }
            self.show_shop_panel = False
        elif t == "SHOP_STATE":
            self.shop = msg
        elif t == "QUEST_LOG":
            self.quests = msg["quests"]
        elif t == "QUEST_COMPLETE":
            self.chat_log.append(f"Quest complete: {msg['quest_id'].replace('_',' ').title()}!")
        elif t == "TRADE_REQUEST_IN":
            self.trade_incoming = msg
        elif t == "TRADE_STATE":
            self.trade_state = msg
            self.trade_incoming = None
        elif t == "TRADE_DONE":
            self.chat_log.append("Trade completed.")
            self.trade_state = None
        elif t == "TRADE_CANCELLED":
            self.chat_log.append(f"Trade cancelled: {msg.get('reason','')}")
            self.trade_state = None
        elif t == "ERROR":
            self.chat_log.append(f"[!] {msg['message']}")
            self.chat_log = self.chat_log[-8:]

    def handle_combat_event(self, msg):
        target_kind = "monster" if msg["defender_id"] in self.monsters else "player"
        x = y = None
        if target_kind == "monster" and msg["defender_id"] in self.monsters:
            m = self.monsters[msg["defender_id"]]
            x, y = m["x"], m["y"]
        elif msg["defender_id"] in self.players:
            p = self.players[msg["defender_id"]]
            x, y = p["x"], p["y"]
        if x is not None:
            text = str(msg["damage"]) if msg["damage"] > 0 else "miss"
            color = YELLOW if msg["damage"] > 0 else GREY
            self.floaters.append([x, y, text, color, time.time() + 0.8])

    # ------------------------------------------------------------------
    def handle_events(self):
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.running = False
            elif self.state == "LOGIN":
                self.handle_login_event(event)
            elif self.state == "GAME":
                self.handle_game_event(event)

    def set_login_mode(self, mode):
        if mode == self.login_mode:
            return
        self.login_mode = mode
        self.login_error = ""
        if mode == "login" and self.active_field == "char_name":
            self.active_field = "username"

    def handle_login_event(self, event):
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_TAB:
                order = ["username", "password"] + (["char_name"] if self.login_mode == "register" else [])
                idx = order.index(self.active_field)
                self.active_field = order[(idx + 1) % len(order)]
            elif event.key == pygame.K_F2:
                self.set_login_mode("register" if self.login_mode == "login" else "login")
            elif event.key == pygame.K_RETURN:
                self.submit_login()
            elif event.key == pygame.K_BACKSPACE:
                self.fields[self.active_field] = self.fields[self.active_field][:-1]
            else:
                if event.unicode and event.unicode.isprintable():
                    self.fields[self.active_field] += event.unicode
        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            mx, my = event.pos
            login_tab = pygame.Rect(350, 200, 190, 34)
            register_tab = pygame.Rect(550, 200, 200, 34)
            if login_tab.collidepoint(mx, my):
                self.set_login_mode("login")
                return
            if register_tab.collidepoint(mx, my):
                self.set_login_mode("register")
                return
            if 350 <= mx <= 750:
                if 250 <= my <= 285:
                    self.active_field = "username"
                elif 300 <= my <= 335:
                    self.active_field = "password"
                elif self.login_mode == "register" and 350 <= my <= 385:
                    self.active_field = "char_name"
            submit_y = 410 if self.login_mode == "register" else 360
            submit_btn = pygame.Rect(350, submit_y, 400, 40)
            if submit_btn.collidepoint(mx, my):
                self.submit_login()

    def submit_login(self):
        u, p, c = self.fields["username"].strip(), self.fields["password"], self.fields["char_name"].strip()
        if not u or not p:
            self.login_error = "Enter a username and password."
            return
        if self.login_mode == "register":
            if not c:
                self.login_error = "Enter a character name."
                return
            self.net.send("CREATE_CHARACTER", username=u, password=p, char_name=c)
        else:
            self.net.send("LOGIN", username=u, password=p)

    def handle_game_event(self, event):
        if event.type == pygame.KEYDOWN:
            if self.chat_typing:
                self.handle_chat_typing(event)
                return
            if self.trade_incoming:
                if event.key == pygame.K_y:
                    self.net.send("TRADE_RESPOND", accept=True, from_player_id=self.trade_incoming["from_player_id"])
                elif event.key == pygame.K_n:
                    self.net.send("TRADE_RESPOND", accept=False, from_player_id=self.trade_incoming["from_player_id"])
                    self.trade_incoming = None
                return
            if self.trade_state:
                if event.key == pygame.K_RETURN:
                    self.net.send("TRADE_CONFIRM")
                elif event.key == pygame.K_ESCAPE:
                    self.net.send("TRADE_CANCEL")
                    self.trade_state = None
                return
            if self.dialogue:
                self.handle_dialogue_key(event)
                return

            if event.key == pygame.K_RETURN:
                self.chat_typing = True
                self.chat_text = ""
            elif event.key == pygame.K_UP:
                self.try_move(0, -1)
            elif event.key == pygame.K_DOWN:
                self.try_move(0, 1)
            elif event.key == pygame.K_LEFT:
                self.try_move(-1, 0)
            elif event.key == pygame.K_RIGHT:
                self.try_move(1, 0)
            elif event.key == pygame.K_i:
                self.show_inventory = not self.show_inventory
            elif event.key == pygame.K_TAB:
                self.show_stats = not self.show_stats
            elif event.key == pygame.K_q:
                self.show_quests = not self.show_quests
            elif event.key == pygame.K_g:
                self.net.send("PICKUP")
            elif event.key == pygame.K_SPACE:
                self.try_attack_nearest()
        elif event.type == pygame.MOUSEBUTTONDOWN:
            self.handle_mouse_click(event)

    def try_attack_nearest(self):
        """Attack the closest adjacent (or same-tile) living monster. Space bar."""
        if not self.player:
            return
        px, py = self.player["x"], self.player["y"]
        live = self.players.get(self.player["id"])
        if live:
            px, py = live["x"], live["y"]

        best = None
        best_dist = None
        for m in self.monsters.values():
            if not m["alive"]:
                continue
            dist = max(abs(m["x"] - px), abs(m["y"] - py))
            if dist > 1:
                continue
            # Prefer exact tile, then nearer Chebyshev distance, then lower id for stability.
            score = (dist, m["id"])
            if best is None or score < best_dist:
                best = m
                best_dist = score
        if best:
            self.net.send("ATTACK", target_id=best["id"])

    def handle_chat_typing(self, event):
        if event.key == pygame.K_RETURN:
            if self.chat_text.strip():
                self.net.send("CHAT", text=self.chat_text.strip())
            self.chat_typing = False
            self.chat_text = ""
        elif event.key == pygame.K_ESCAPE:
            self.chat_typing = False
            self.chat_text = ""
        elif event.key == pygame.K_BACKSPACE:
            self.chat_text = self.chat_text[:-1]
        elif event.unicode and event.unicode.isprintable():
            self.chat_text += event.unicode

    def handle_dialogue_key(self, event):
        quest = self.dialogue.get("quest")
        if event.key == pygame.K_ESCAPE:
            self.dialogue = None
            self.show_shop_panel = False
        elif event.key == pygame.K_b and self.dialogue.get("shop_id"):
            self.show_shop_panel = True
        elif event.key == pygame.K_a and quest and quest["state"] == "offerable":
            self.net.send("QUEST_ACCEPT", quest_id=quest["quest_id"])
            self.dialogue = None
        elif event.key == pygame.K_t and quest and quest["state"] == "ready":
            self.net.send("QUEST_TURNIN", quest_id=quest["quest_id"])
            self.dialogue = None

    def try_move(self, dx, dy):
        self.net.send("MOVE", dx=dx, dy=dy)

    # -- mouse interaction on the map -----------------------------------
    def screen_to_tile(self, mx, my):
        if not self.player:
            return None
        cam_x, cam_y = self.camera_origin()
        tx = cam_x + mx // TILE
        ty = cam_y + my // TILE
        return tx, ty

    def camera_origin(self):
        """Center the viewport on the player, clamped to the world bounds."""
        px, py = self.player["x"], self.player["y"]
        # Prefer the live tick position if available (slightly fresher mid-frame).
        live = self.players.get(self.player["id"])
        if live:
            px, py = live["x"], live["y"]
        vis_w, vis_h = MAP_W // TILE, MAP_H // TILE
        max_cam_x = max(0, self.world_w - vis_w)
        max_cam_y = max(0, self.world_h - vis_h)
        cam_x = max(0, min(px - vis_w // 2, max_cam_x))
        cam_y = max(0, min(py - vis_h // 2, max_cam_y))
        return cam_x, cam_y

    def handle_mouse_click(self, event):
        mx, my = event.pos
        if mx >= SIDEBAR_X or my >= MAP_H:
            self.handle_sidebar_click(mx, my, event.button)
            return
        if not self.player:
            return
        tile = self.screen_to_tile(mx, my)
        if tile is None:
            return
        tx, ty = tile

        # monster?
        for m in self.monsters.values():
            if m["alive"] and m["x"] == tx and m["y"] == ty:
                self.net.send("ATTACK", target_id=m["id"])
                return
        # npc?
        for n in self.npcs:
            if n["x"] == tx and n["y"] == ty:
                self.net.send("TALK", npc_id=n["id"])
                return
        # other player -> trade request
        for p in self.players.values():
            if p["id"] != self.player["id"] and p["x"] == tx and p["y"] == ty:
                self.net.send("TRADE_REQUEST", target_player_id=p["id"])
                return
        # resource node?
        if f"{tx},{ty}" in self.resources:
            self.net.send("GATHER", x=tx, y=ty)
            return

    def handle_sidebar_click(self, mx, my, button):
        if self.trade_state:
            self.handle_trade_inventory_click(mx, my)
            return
        if self.show_shop_panel and self.shop:
            self.handle_shop_click(mx, my, button)
            return
        if self.show_inventory:
            self.handle_inventory_click(mx, my, button)

    def inventory_slot_rects(self):
        rects = {}
        cols, rows = 4, 6
        ox, oy = SIDEBAR_X + 16, 300
        size = 46
        for slot in range(cols * rows):
            col, row = slot % cols, slot // cols
            rects[slot] = pygame.Rect(ox + col * (size + 4), oy + row * (size + 4), size, size)
        return rects

    def handle_inventory_click(self, mx, my, button):
        if not self.player:
            return
        for slot, rect in self.inventory_slot_rects().items():
            if rect.collidepoint(mx, my):
                entry = self.player["inventory"].get(str(slot)) or self.player["inventory"].get(slot)
                if not entry:
                    return
                item = ITEMS[entry["item_id"]]
                if button == 3:  # right click = drop 1
                    self.net.send("DROP", slot_index=slot, qty=1)
                elif item.get("equip_slot"):
                    self.net.send("EQUIP", slot_index=slot)
                elif item["type"] == "food":
                    self.net.send("USE_ITEM", slot_index=slot)
                return

    def handle_shop_click(self, mx, my, button):
        items = list(self.shop["stock"].items())
        ox, oy = SIDEBAR_X + 16, 130
        for i, (item_id, info) in enumerate(items):
            rect = pygame.Rect(ox, oy + i * 22, 260, 20)
            if rect.collidepoint(mx, my):
                self.net.send("SHOP_BUY", shop_id=self.shop["shop_id"], item_id=item_id, qty=1)
                return
        # sell your inventory: click any inventory slot while shop panel open
        for slot, rect in self.inventory_slot_rects().items():
            shifted = pygame.Rect(rect.x, rect.y + 40, rect.w, rect.h)
            if shifted.collidepoint(mx, my):
                entry = self.player["inventory"].get(str(slot)) or self.player["inventory"].get(slot)
                if entry:
                    self.net.send("SHOP_SELL", shop_id=self.shop["shop_id"], item_id=entry["item_id"], qty=1)
                return

    def handle_trade_inventory_click(self, mx, my):
        for slot, rect in self.inventory_slot_rects().items():
            if rect.collidepoint(mx, my):
                entry = self.player["inventory"].get(str(slot)) or self.player["inventory"].get(slot)
                if entry:
                    self.net.send("TRADE_OFFER", items=[{"slot_index": slot, "qty": entry["qty"]}])
                return

    # ------------------------------------------------------------------
    def draw(self):
        self.screen.fill(BLACK)
        if self.state == "LOGIN":
            self.draw_login()
        else:
            self.draw_game()
        pygame.display.flip()

    def draw_login(self):
        title = self.font_big.render("Tiny MMORPG v0.1", True, WHITE)
        self.screen.blit(title, (SCREEN_W // 2 - title.get_width() // 2, 140))

        self.draw_mode_tab("Login", pygame.Rect(350, 200, 190, 34), self.login_mode == "login")
        self.draw_mode_tab("Create Account", pygame.Rect(550, 200, 200, 34), self.login_mode == "register")

        self.draw_text_field("Username", "username", 250)
        self.draw_text_field("Password", "password", 300, mask=True)
        if self.login_mode == "register":
            self.draw_text_field("Character name", "char_name", 350)

        submit_y = 410 if self.login_mode == "register" else 360
        submit_label = "Create Account" if self.login_mode == "register" else "Login"
        self.draw_button(submit_label, pygame.Rect(350, submit_y, 400, 40), primary=True)

        hint = self.font_small.render("Tab: switch field   Enter: submit   F2: toggle mode", True, GREY)
        self.screen.blit(hint, (350, submit_y + 55))
        if self.login_error:
            err = self.font.render(self.login_error, True, RED)
            self.screen.blit(err, (350, submit_y + 80))

    def draw_mode_tab(self, label, rect, active):
        bg = (50, 90, 55) if active else PANEL_BG
        border = GREEN if active else PANEL_LINE
        pygame.draw.rect(self.screen, bg, rect)
        pygame.draw.rect(self.screen, border, rect, 2)
        text = self.font.render(label, True, WHITE if active else GREY)
        self.screen.blit(text, (rect.x + (rect.w - text.get_width()) // 2,
                                rect.y + (rect.h - text.get_height()) // 2))

    def draw_button(self, label, rect, primary=False):
        bg = (45, 100, 55) if primary else PANEL_BG
        pygame.draw.rect(self.screen, bg, rect)
        pygame.draw.rect(self.screen, GREEN if primary else PANEL_LINE, rect, 2)
        text = self.font.render(label, True, WHITE)
        self.screen.blit(text, (rect.x + (rect.w - text.get_width()) // 2,
                                rect.y + (rect.h - text.get_height()) // 2))

    def draw_text_field(self, label, key, y, mask=False):
        lbl = self.font_small.render(label, True, GREY)
        self.screen.blit(lbl, (350, y - 18))
        rect = pygame.Rect(350, y, 400, 35)
        color = WHITE if self.active_field == key else GREY
        pygame.draw.rect(self.screen, PANEL_BG, rect)
        pygame.draw.rect(self.screen, color, rect, 2)
        text = self.fields[key]
        if mask:
            text = "*" * len(text)
        txt_surf = self.font.render(text, True, WHITE)
        self.screen.blit(txt_surf, (rect.x + 8, rect.y + 8))

    # -- main game drawing ------------------------------------------------
    def draw_game(self):
        if not self.player:
            return
        self.draw_map()
        self.draw_sidebar()
        self.draw_chat()
        if self.dialogue:
            self.draw_dialogue()
        if self.show_shop_panel and self.shop:
            self.draw_shop()
        if self.trade_incoming:
            self.draw_trade_incoming()
        if self.trade_state:
            self.draw_trade()

    def draw_map(self):
        cam_x, cam_y = self.camera_origin()
        vis_w, vis_h = MAP_W // TILE, MAP_H // TILE
        t = time.time()
        now_pos = {}

        for sy in range(vis_h + 1):
            for sx in range(vis_w + 1):
                wx, wy = cam_x + sx, cam_y + sy
                if 0 <= wx < self.world_w and 0 <= wy < len(self.tiles) and wy < self.world_h:
                    tile_id = self.tiles[wy][wx]
                else:
                    tile_id = wm.WALL
                rect = pygame.Rect(sx * TILE, sy * TILE, TILE, TILE)
                self.draw_terrain_tile(rect, tile_id, wx, wy, t)

        # resource nodes (trees, rocks, fishing spots)
        for key, rtype in self.resources.items():
            x, y = map(int, key.split(","))
            sx, sy = x - cam_x, y - cam_y
            if 0 <= sx <= vis_w and 0 <= sy <= vis_h:
                cx, cy = sx * TILE + TILE // 2, sy * TILE + TILE // 2
                self.draw_resource_sprite(rtype, cx, cy, t)

        # ground items
        for key, items in self.ground_items.items():
            if not items:
                continue
            x, y = map(int, key.split(","))
            sx, sy = x - cam_x, y - cam_y
            if 0 <= sx <= vis_w and 0 <= sy <= vis_h:
                r = pygame.Rect(sx * TILE + 4, sy * TILE + 4, TILE - 8, TILE - 8)
                sprites.draw_ground_item(self.screen, r, t)

        # npcs
        for n in self.npcs:
            sx, sy = n["x"] - cam_x, n["y"] - cam_y
            if 0 <= sx <= vis_w and 0 <= sy <= vis_h:
                cx, cy = sx * TILE + TILE // 2, sy * TILE + TILE // 2
                nid = abs(hash(n["id"]))
                body, skin, hair = sprites.palette_for(nid)
                sprites.draw_humanoid_detailed(
                    self.screen, cx, cy, TILE, body, skin, hair,
                    robe=n["id"] in ROBED_NPC_IDS, t=t,
                )
                self.blit_label(n["name"], cx, cy - TILE // 2 - 4)

        # monsters
        for m in self.monsters.values():
            if not m["alive"]:
                continue
            sx, sy = m["x"] - cam_x, m["y"] - cam_y
            if 0 <= sx <= vis_w and 0 <= sy <= vis_h:
                cx, cy = sx * TILE + TILE // 2, sy * TILE + TILE // 2
                hurt = m["hp"] < m["max_hp"]
                sprites.draw_monster(self.screen, m["type"], cx, cy, TILE, t, hurt=hurt)
                self.blit_label(m["name"], cx, cy - TILE // 2 - 12)
                self.draw_hp_bar(cx, cy - TILE // 2 - 6, m["hp"], m["max_hp"])
            now_pos[("m", m["id"])] = (m["x"], m["y"])

        # players
        for p in self.players.values():
            sx, sy = p["x"] - cam_x, p["y"] - cam_y
            if 0 <= sx <= vis_w and 0 <= sy <= vis_h:
                cx, cy = sx * TILE + TILE // 2, sy * TILE + TILE // 2
                is_self = self.player and p["id"] == self.player["id"]
                if is_self:
                    body, skin, hair = (70, 210, 90), (235, 195, 150), (70, 45, 30)
                    eq = self.player.get("equipment") or {}
                else:
                    body, skin, hair = sprites.palette_for(p["id"])
                    eq = p.get("equipment") or {}
                key = ("p", p["id"])
                moving = self._prev_entity_pos.get(key) not in (None, (p["x"], p["y"]))
                sprites.draw_humanoid_detailed(
                    self.screen, cx, cy, TILE, body, skin, hair,
                    weapon=weapon_style(eq.get("weapon")),
                    shield=bool(eq.get("shield")),
                    moving=moving, t=t,
                )
                self.blit_label(p["name"], cx, cy - TILE // 2 - 12)
                self.draw_hp_bar(cx, cy - TILE // 2 - 6, p["hp"], p["max_hp"])
            now_pos[("p", p["id"])] = (p["x"], p["y"])

        self._prev_entity_pos = now_pos

        # floating combat text
        now = time.time()
        self.floaters = [f for f in self.floaters if f[4] > now]
        for (wx, wy, text, color, expire) in self.floaters:
            sx, sy = wx - cam_x, wy - cam_y
            if 0 <= sx <= vis_w and 0 <= sy <= vis_h:
                lift = int((expire - now) * -20) + 20
                surf = self.font.render(text, True, color)
                self.screen.blit(surf, (sx * TILE + TILE // 2 - surf.get_width() // 2, sy * TILE - lift))

        pygame.draw.rect(self.screen, PANEL_LINE, (0, 0, MAP_W, MAP_H), 2)
        zone = wm.get_zone(self.player["x"], self.player["y"])
        zone_label = self.font.render(zone.title(), True, WHITE)
        self.screen.blit(zone_label, (10, 10))

    def draw_terrain_tile(self, rect, tile_id, wx, wy, t):
        zone = wm.get_zone(wx, wy) if self.world_w else "wilderness"
        if tile_id in (wm.TREE, wm.OAK_TREE, wm.FISH_SPOT):
            sprites.draw_grass(self.screen, rect, wx, wy)
        elif tile_id in (wm.ORE, wm.IRON_ORE):
            sprites.draw_floor(self.screen, rect, wx, wy)
        elif tile_id == wm.GRASS:
            sprites.draw_grass(self.screen, rect, wx, wy)
        elif tile_id == wm.PATH:
            sprites.draw_path(self.screen, rect, wx, wy)
        elif tile_id == wm.FLOOR:
            sprites.draw_floor(self.screen, rect, wx, wy)
        elif tile_id == wm.WALL:
            sprites.draw_wall(self.screen, rect, zone, wx, wy)
        elif tile_id == wm.WATER:
            sprites.draw_water_detailed(self.screen, rect, t, wx, wy)
        else:
            sprites.draw_grass(self.screen, rect, wx, wy)

    def draw_resource_sprite(self, rtype, cx, cy, t):
        if rtype == "tree":
            sprites.draw_tree_detailed(self.screen, cx, cy, TILE, variant=0, t=t)
        elif rtype == "oak_tree":
            sprites.draw_tree_detailed(self.screen, cx, cy, TILE, variant=1, t=t)
        elif rtype in ROCK_LOOK:
            sprites.draw_rock_detailed(self.screen, cx, cy, TILE, variant=sum(ord(c) for c in rtype) % 3)
        elif rtype.startswith("fishing_spot"):
            sprites.draw_fishing_spot(self.screen, cx, cy, TILE, t)
        else:
            sprites.draw_tree(self.screen, cx, cy, TILE)
    def blit_label(self, text, cx, top_y):
        surf = self.font_small.render(text, True, WHITE)
        self.screen.blit(surf, (cx - surf.get_width() // 2, top_y - 10))

    def draw_hp_bar(self, cx, y, hp, max_hp):
        w = 30
        pct = max(0, hp) / max(1, max_hp)
        pygame.draw.rect(self.screen, (60, 20, 20), (cx - w // 2, y, w, 4))
        pygame.draw.rect(self.screen, GREEN if pct > 0.3 else RED, (cx - w // 2, y, int(w * pct), 4))

    # -- sidebar: stats + inventory + quests ------------------------------
    def draw_sidebar(self):
        pygame.draw.rect(self.screen, PANEL_BG, (SIDEBAR_X, 0, SCREEN_W - SIDEBAR_X, SCREEN_H))
        y = 12
        name = self.font_big.render(self.player["name"], True, WHITE)
        self.screen.blit(name, (SIDEBAR_X + 16, y))
        y += 34
        coins = self.font.render(f"Coins: {self.player['coins']}", True, YELLOW)
        self.screen.blit(coins, (SIDEBAR_X + 16, y))
        y += 26

        hp_txt = self.font.render(f"HP: {self.player['hp']} / {self.player['max_hp']}", True, WHITE)
        self.screen.blit(hp_txt, (SIDEBAR_X + 16, y))
        y += 24

        levels = self.player["levels"]
        for skill in ["attack", "strength", "defence", "hitpoints", "woodcutting", "mining", "fishing"]:
            row = self.font_small.render(f"{skill.title():<12} {levels[skill]:>2}", True, GREY)
            self.screen.blit(row, (SIDEBAR_X + 16, y))
            y += 18

        y += 8
        eq = self.player["equipment"]
        eq_txt = self.font_small.render(
            "Weapon: " + (ITEMS.get(eq.get("weapon"), {}).get("name", "-") if eq.get("weapon") else "-"),
            True, GREY)
        self.screen.blit(eq_txt, (SIDEBAR_X + 16, y))
        y += 16
        body_txt = self.font_small.render(
            "Body: " + (ITEMS.get(eq.get("body"), {}).get("name", "-") if eq.get("body") else "-"),
            True, GREY)
        self.screen.blit(body_txt, (SIDEBAR_X + 16, y))

        # inventory grid
        inv_label = self.font.render("Inventory (click=use/equip, right-click=drop)", True, WHITE)
        self.screen.blit(inv_label, (SIDEBAR_X + 16, 272))
        for slot, rect in self.inventory_slot_rects().items():
            entry = self.player["inventory"].get(str(slot)) or self.player["inventory"].get(slot)
            pygame.draw.rect(self.screen, (45, 45, 55), rect)
            pygame.draw.rect(self.screen, PANEL_LINE, rect, 1)
            if entry:
                sprites.draw_item_icon(self.screen, rect.inflate(-4, -4), entry["item_id"], ITEMS)
                if entry["qty"] > 1:
                    qty = self.font_small.render(str(entry["qty"]), True, YELLOW)
                    self.screen.blit(qty, (rect.x + rect.w - qty.get_width() - 3, rect.y + rect.h - 16))

        # quest log (toggle with Q)
        qy = 550
        q_label = self.font.render("Quests (Q to toggle)" if not self.show_quests else "Quests:", True, WHITE)
        self.screen.blit(q_label, (SIDEBAR_X + 16, qy))
        if self.show_quests:
            qy += 22
            for qid, info in self.quests.items():
                color = {"not_started": GREY, "active": WHITE, "ready": YELLOW, "complete": GREEN}[info["status"]]
                txt = self.font_small.render(f"{qid.replace('_',' ').title()}: {info['status']}", True, color)
                self.screen.blit(txt, (SIDEBAR_X + 16, qy))
                qy += 16

        controls = self.font_small.render(
            "Arrow keys move  Space attack  G pickup  click=attack/talk/gather", True, GREY)
        self.screen.blit(controls, (SIDEBAR_X + 10, SCREEN_H - 18))

    # -- chat ---------------------------------------------------------------
    def draw_chat(self):
        box = pygame.Rect(0, MAP_H, MAP_W, SCREEN_H - MAP_H)
        pygame.draw.rect(self.screen, PANEL_BG, box)
        y = MAP_H + 6
        for line in self.chat_log[-6:]:
            surf = self.font_small.render(line[:110], True, WHITE)
            self.screen.blit(surf, (8, y))
            y += 17
        input_rect = pygame.Rect(4, SCREEN_H - 26, MAP_W - 8, 22)
        pygame.draw.rect(self.screen, (45, 45, 55), input_rect)
        pygame.draw.rect(self.screen, PANEL_LINE if not self.chat_typing else GREEN, input_rect, 1)
        prompt = ("> " + self.chat_text) if self.chat_typing else "Press Enter to chat"
        surf = self.font_small.render(prompt, True, WHITE if self.chat_typing else GREY)
        self.screen.blit(surf, (input_rect.x + 4, input_rect.y + 4))

    # -- modals ---------------------------------------------------------------
    def draw_dialogue(self):
        box = pygame.Rect(150, 480, MAP_W - 300, 200)
        pygame.draw.rect(self.screen, (25, 25, 35), box)
        pygame.draw.rect(self.screen, WHITE, box, 2)
        name = self.font.render(self.dialogue["npc_name"], True, YELLOW)
        self.screen.blit(name, (box.x + 12, box.y + 10))
        y = box.y + 36
        for line in self.dialogue["lines"]:
            surf = self.font_small.render(line, True, WHITE)
            self.screen.blit(surf, (box.x + 12, y))
            y += 18
        quest = self.dialogue.get("quest")
        if quest:
            y += 6
            qsurf = self.font_small.render(f"Quest: {quest['name']} - {quest['description']}", True, (200, 200, 255))
            self.screen.blit(qsurf, (box.x + 12, y))
            y += 20
            if quest["state"] == "offerable":
                hint = "Press A to accept this quest"
            elif quest["state"] == "active":
                hint = "Quest in progress..."
            elif quest["state"] == "ready":
                hint = "Press T to turn in this quest!"
            else:
                hint = "Quest already completed."
            self.screen.blit(self.font_small.render(hint, True, GREEN), (box.x + 12, y))
        if self.dialogue.get("shop_id"):
            self.screen.blit(self.font_small.render("Press B to browse the shop", True, (255, 210, 120)),
                              (box.x + 12, box.y + box.h - 40))
        self.screen.blit(self.font_small.render("Esc to close", True, GREY), (box.x + 12, box.y + box.h - 20))

    def draw_shop(self):
        box = pygame.Rect(SIDEBAR_X, 100, SCREEN_W - SIDEBAR_X, 480)
        pygame.draw.rect(self.screen, (20, 25, 35), box)
        pygame.draw.rect(self.screen, WHITE, box, 2)
        title = self.font.render(f"{self.shop['name']} (coins: {self.shop['your_coins']})", True, YELLOW)
        self.screen.blit(title, (box.x + 12, box.y + 6))
        y = box.y + 30
        for item_id, info in self.shop["stock"].items():
            txt = self.font_small.render(f"{info['name']:<18} {info['price']:>4}c  (stock {info['qty']})", True, WHITE)
            self.screen.blit(txt, (box.x + 16, y))
            y += 22
        hint = self.font_small.render("Click item to buy 1. Click your inventory slot below to sell 1. Esc closes dialogue.", True, GREY)
        self.screen.blit(hint, (box.x + 12, box.y + box.h - 20))

    def draw_trade_incoming(self):
        box = pygame.Rect(300, 300, 500, 100)
        pygame.draw.rect(self.screen, (25, 25, 35), box)
        pygame.draw.rect(self.screen, WHITE, box, 2)
        txt = self.font.render(f"{self.trade_incoming['from_name']} wants to trade. Y/N?", True, WHITE)
        self.screen.blit(txt, (box.x + 12, box.y + 40))

    def draw_trade(self):
        box = pygame.Rect(SIDEBAR_X, 100, SCREEN_W - SIDEBAR_X, 420)
        pygame.draw.rect(self.screen, (20, 25, 35), box)
        pygame.draw.rect(self.screen, WHITE, box, 2)
        title = self.font.render(f"Trading with {self.trade_state['other_name']}", True, YELLOW)
        self.screen.blit(title, (box.x + 12, box.y + 6))

        y = box.y + 34
        self.screen.blit(self.font_small.render("Your offer:", True, WHITE), (box.x + 12, y))
        y += 18
        for slot, qty in self.trade_state["your_offer"].items():
            entry = self.player["inventory"].get(str(slot)) or self.player["inventory"].get(slot)
            if entry:
                self.screen.blit(self.font_small.render(f"  {ITEMS[entry['item_id']]['name']} x{qty}", True, WHITE), (box.x + 12, y))
                y += 16
        y += 10
        self.screen.blit(self.font_small.render("Their offer:", True, WHITE), (box.x + 12, y))
        y += 18
        for slot, qty in self.trade_state["other_offer"].items():
            self.screen.blit(self.font_small.render(f"  slot {slot} x{qty}", True, WHITE), (box.x + 12, y))
            y += 16

        status = f"You: {'READY' if self.trade_state['your_confirmed'] else 'not ready'}   Them: {'READY' if self.trade_state['other_confirmed'] else 'not ready'}"
        self.screen.blit(self.font_small.render(status, True, GREEN), (box.x + 12, box.y + box.h - 60))
        self.screen.blit(self.font_small.render("Click inventory slots to offer them. Enter=confirm  Esc=cancel", True, GREY),
                          (box.x + 12, box.y + box.h - 20))


if __name__ == "__main__":
    GameClient().run()
