"""
MMORPG v0.1 client. Run with:  python client.py [server_host]

Requires: pip install pygame websockets
"""
import sys
import os
import time
import math

import pygame

from network import NetworkClient

# Reuse the server's static content module for item names/icons/etc so the
# client doesn't have to duplicate a second copy of the game data.
_HERE = os.path.dirname(__file__)
sys.path.insert(0, os.path.join(_HERE, "..", "server"))
sys.path.insert(0, os.path.join(_HERE, "..", "..", "characters"))
from content import (
    ITEMS, RESOURCE_LABELS, karma_slot_bonus, cook_burn_chance,
    XP_SKILLS, SKILL_DISPLAY_NAMES, TRAVEL_DESTINATIONS, MONSTERS,
)  # noqa: E402
import world_map as wm  # noqa: E402
import combat  # noqa: E402
import procedural_sprites_finished as sprites  # noqa: E402

SERVER_HOST = sys.argv[1] if len(sys.argv) > 1 else "localhost"
SERVER_URI = f"ws://{SERVER_HOST}:8765"

SCREEN_W, SCREEN_H = 1200, 800
MAP_W, MAP_H = 900, 640
SIDEBAR_X = MAP_W
# World tile size — RS-era: show plenty of ground around the player
TILE = getattr(sprites, "TILE_SIZE_DEFAULT", 40)

# Calibrated to 2001–2004 RuneScape proportion references
# (character ~2 tiles tall, trees ~2.5–3× character, ore waist-high)
sprites.set_render_profile(
    tile_size=TILE,
    art=1.0,
    character=2.5,
    object_=2.55,
    monster=2.5,
    pet=1.65,
)

WHITE = (240, 236, 228)
BLACK = (10, 10, 10)
RED = (220, 70, 70)
GREEN = (86, 196, 110)
YELLOW = (236, 198, 72)
GREY = (150, 148, 142)
PANEL_BG = (22, 24, 32)
PANEL_BG_2 = (30, 33, 44)
PANEL_LINE = (58, 62, 78)
ACCENT = (196, 150, 72)
ACCENT_DIM = (120, 92, 48)

ROCK_LOOK = {
    "copper_rock": ((190, 120, 60), (230, 180, 100)),
    "tin_rock": ((160, 160, 170), (210, 210, 220)),
    "iron_rock": ((130, 90, 70), (180, 140, 100)),
    "coal_rock": ((45, 45, 50), (90, 90, 100)),
    "mithril_rock": ((70, 140, 180), (120, 200, 240)),
    "adamantite_rock": ((50, 140, 90), (100, 220, 140)),
}
ROBED_NPC_IDS = {
    "elder_miriam", "priest_cedric", "monk_healer", "mysterious_traveler",
}
ORE_LABEL_COLORS = {
    "copper_rock": (255, 170, 90),
    "tin_rock": (200, 210, 230),
    "iron_rock": (220, 150, 120),
    "coal_rock": (160, 160, 170),
    "mithril_rock": (140, 210, 255),
    "adamantite_rock": (120, 255, 160),
}


def weapon_style(item_id):
    if not item_id:
        return None
    if "dagger" in item_id:
        return "dagger"
    if "pickaxe" in item_id:
        return "pickaxe"
    if "battleaxe" in item_id or "cleaver" in item_id:
        return "battleaxe"
    if "axe" in item_id:
        return "axe"
    if "sword" in item_id:
        return "sword"
    return "sword"


class GameClient:
    def __init__(self):
        pygame.init()
        pygame.display.set_caption("Mythoscape — Tiny MMORPG")
        self.screen = pygame.display.set_mode((SCREEN_W, SCREEN_H))
        self.clock = pygame.time.Clock()
        # RS-era UI: compact sans text (chat/log readable, not oversized)
        ui = pygame.font.match_font("arial,helvetica,segoe ui,dejavu sans") or None
        mono = pygame.font.match_font("menlo,consolas,monaco,dejavu sans mono") or None
        self.font = pygame.font.SysFont(ui or mono, 16)
        self.font_small = pygame.font.SysFont(ui or mono, 14)
        self.font_big = pygame.font.SysFont(ui or mono, 24, bold=True)
        self.font_tiny = pygame.font.SysFont(ui or mono, 12)
        self.font_label = pygame.font.SysFont(ui or mono, 13, bold=True)

        self.net = NetworkClient(SERVER_URI)
        self.net.start()

        self.state = "LOGIN"
        self.login_mode = "login"  # or "register"
        self.fields = {"username": "", "password": "", "char_name": ""}
        self.active_field = "username"
        self.login_error = ""
        self.stat_alloc = {"attack": 0, "strength": 0, "defence": 0, "hitpoints": 0}
        self.stat_alloc_points = 10
        self.stat_alloc_base = {"attack": 5, "strength": 5, "defence": 5, "hitpoints": 10}
        self.stat_alloc_error = ""
        self.stat_alloc_rects = {}

        # world / game state
        self.tiles = []
        self.world_w = self.world_h = 0
        self.npcs = []
        self.resources = {}  # "x,y" -> type
        self.players = {}    # id -> public state
        self.monsters = {}   # id -> public state
        self.pets = []       # list of pet public states
        self.ground_items = {}
        self.player = None   # full state dict (self)
        self.quests = {}

        self.chat_log = []
        self.chat_typing = False
        self.chat_text = ""

        self.dialogue = None       # {"npc_id","npc_name","lines","shop_id","quest":{...}}
        self.shop = None           # {"shop_id","name","stock","your_coins","buys"}
        self.show_shop_panel = False
        self.shop_buy_rects = []   # [(rect, item_id), ...]
        self.shop_sell_rects = []  # [(rect, slot_index, item_id), ...]
        self.combat_style = "attack"
        self.combat_style_rects = []  # [(rect, style), ...]
        self.trade_incoming = None  # {"from_player_id","from_name"}
        self.trade_state = None     # {"other_name","your_offer","other_offer",...}
        self.interactables = []
        self.buildings = []
        self.craft_recipes = {}
        self.show_equipment = False
        self.show_forge = False
        self.show_help = False
        self.show_bank = False
        self.bank = None  # BANK_STATE payload
        self.bank_inv_rects = []
        self.bank_slot_rects = []
        self.bank_btn_rects = {}
        self.bank_inv_scroll = 0
        self.bank_page = 0
        self.bank_page_size = 36  # 6x6 grid visible per page
        self.auto_pickup_btn_rect = None
        self.logout_btn_rect = None
        self._logging_out = False
        self.show_leaderboard = False
        self.leaderboard = {}       # skill -> [{name, xp, level}]
        self.leaderboard_skills = []
        self.leaderboard_skill = "total"
        self.leaderboard_tab_rects = {}
        self.forge_tab = "smelt"  # or "smith"
        self.forge_station = None  # "furnace" | "anvil" | None — locks the modal to one station
        self.forge_metal = "all"  # all | bronze | iron | steel
        self.forge_gear = "all"   # all | weapon | shield | body | legs | helmet | bar
        self.forge_recipe_rects = []
        self.forge_filter_rects = {}
        self.show_cook = False
        self.cook_recipe_rects = []
        self.fires = set()  # {"x,y", ...} active campfires from STATE_UPDATE
        self.show_skills = False
        self.skills_btn_rect = None
        self.show_pets = False
        self.pets_btn_rect = None
        self.pet_switch_rects = []
        self.show_travel = False
        self.travel_btn_rects = []
        self.minimap_rect = None
        self._minimap_base = None
        self._minimap_size = (0, 0)

        self.floaters = []  # floating text/hitsplats: dicts with x,y,text,color,expire,kind
        self.attack_anims = {}  # entity_id -> expire timestamp
        self.level_up_until = 0.0  # gold glow / banner while celebrating a level-up
        self.level_up_label = ""
        self.show_inventory = True
        self.show_stats = True
        self.show_xp = False
        self.show_quests = False
        self.inv_hover_slot = None
        self._prev_entity_pos = {}  # id -> (x, y) for walk animation
        self._entity_facing = {}  # id -> 1 | -1

        # Click-to-walk: path of tile coords to step onto, then optional action.
        self.walk_path = []
        self.pending_action = None  # {"type": "ATTACK"|"TALK"|..., ...}
        self._next_walk_at = 0.0

        self.running = True
        pygame.key.set_repeat(180, 120)

    # ------------------------------------------------------------------
    def run(self):
        while self.running:
            self.handle_network()
            self.update_walk()
            self.handle_events()
            self.update_inventory_hover()
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
            if self._logging_out:
                self._logging_out = False
                self.net.reconnect()
                return
            if self.state in ("GAME", "STAT_ALLOC"):
                self.login_error = "Disconnected from server."
                self.state = "LOGIN"
                self.net.reconnect()
        elif t == "LOGIN_FAIL":
            self.login_error = msg["reason"]
            if self.state == "STAT_ALLOC":
                self.state = "LOGIN"
        elif t == "LEADERBOARD":
            self.leaderboard = msg.get("boards") or {}
            self.leaderboard_skills = msg.get("skills") or list(self.leaderboard.keys())
            if self.leaderboard_skills and self.leaderboard_skill not in self.leaderboard_skills:
                self.leaderboard_skill = (
                    "total" if "total" in self.leaderboard_skills else self.leaderboard_skills[0]
                )
            # Only show on the login screen (ignore late replies after logging in).
            if self.state == "LOGIN":
                self.show_leaderboard = True
        elif t == "LOGIN_OK":
            self.player = msg["player"]
            self.combat_style = self.player.get("combat_style") or "attack"
            self.login_error = ""
            self.show_leaderboard = False
            if msg.get("needs_stat_alloc"):
                self.state = "STAT_ALLOC"
                self.stat_alloc = {"attack": 0, "strength": 0, "defence": 0, "hitpoints": 0}
                self.stat_alloc_points = 10
                self.stat_alloc_error = ""
            else:
                self.state = "GAME"
        elif t == "STAT_ALLOC_REQUIRED":
            self.state = "STAT_ALLOC"
            self.stat_alloc_points = int(msg.get("points", 10))
            if msg.get("base_levels"):
                self.stat_alloc_base = dict(msg["base_levels"])
            skills = msg.get("skills") or list(self.stat_alloc.keys())
            self.stat_alloc = {s: 0 for s in skills}
            self.stat_alloc_error = ""
        elif t == "WORLD_STATE":
            self.tiles = msg["tiles"]
            self.world_w, self.world_h = msg["width"], msg["height"]
            self.npcs = msg["npcs"]
            self.resources = msg["resources"]
            self.interactables = msg.get("interactables") or []
            self.craft_recipes = msg.get("craft_recipes") or {}
            self.buildings = msg.get("buildings") or []
            self.state = "GAME"
            self.stat_alloc_error = ""
            self._minimap_base = None  # rebuild when world loads
        elif t == "STATE_UPDATE":
            self.players = {p["id"]: p for p in msg["players"]}
            self.monsters = {m["id"]: m for m in msg["monsters"]}
            self.pets = msg.get("pets") or []
            self.ground_items = msg.get("ground_items", {})
            if "resources" in msg:
                self.resources = msg["resources"]
            self.fires = set(msg.get("fires") or [])
            # Keep local player coords in sync so the camera can follow.
            if self.player and self.player["id"] in self.players:
                live = self.players[self.player["id"]]
                self.player["x"] = live["x"]
                self.player["y"] = live["y"]
                self.player["hp"] = live["hp"]
                self.player["max_hp"] = live["max_hp"]
        elif t == "PLAYER_UPDATE":
            self.player = msg["player"]
            if self.player.get("combat_style"):
                self.combat_style = self.player["combat_style"]
            # Mirror into the shared players dict so sprites stay consistent.
            if self.player:
                self.players[self.player["id"]] = {
                    "id": self.player["id"],
                    "name": self.player["name"],
                    "x": self.player["x"],
                    "y": self.player["y"],
                    "hp": self.player["hp"],
                    "max_hp": self.player["max_hp"],
                    "combat_level": self.player.get("combat_level") or self.player_combat_level(),
                    "equipment": self.player.get("equipment"),
                }
        elif t == "CHAT_MSG":
            self.chat_log.append(f"{msg['from']}: {msg['text']}")
            self.chat_log = self.chat_log[-8:]
        elif t == "COMBAT_EVENT":
            self.handle_combat_event(msg)
        elif t == "DEATH":
            if msg["entity_kind"] == "player" and msg["entity_id"] == (self.player or {}).get("id"):
                lost = int(msg.get("coins_lost") or 0)
                if lost:
                    self.chat_log.append(f"*** You died and lost {lost} coins. ***")
                else:
                    self.chat_log.append("*** You have died and respawned in the village. ***")
                if self.player:
                    self.player["coins"] = 0
        elif t == "LOOT_DROPPED":
            pass
        elif t == "SKILL_XP":
            pid = msg.get("player_id")
            if self.player and (pid is None or pid == self.player["id"]):
                skill = msg["skill"]
                gained = int(msg.get("gained") or 0)
                total = int(msg.get("xp") or 0)
                if "xp" not in self.player:
                    self.player["xp"] = {}
                self.player["xp"][skill] = total
                if "levels" in self.player:
                    self.player["levels"][skill] = msg.get("level", self.player["levels"].get(skill, 1))
                if gained > 0:
                    skill_name = skill.replace("_", " ").title()
                    self.add_chat(f"You gained {gained} {skill_name} XP.")
                if msg.get("leveled_up"):
                    skill_name = skill.replace("_", " ").title()
                    lvl = msg["level"]
                    self.add_chat(
                        f"Congratulations! You leveled up {skill_name} to {lvl}!",
                        color=(255, 230, 90),
                        highlight=True,
                    )
                    self.level_up_until = time.time() + 3.2
                    self.level_up_label = f"Level Up! {skill_name} {lvl}"
                    # gold banner above the head (separate from hitsplats)
                    px, py = self.player["x"], self.player["y"]
                    self.floaters.append({
                        "x": px, "y": py,
                        "text": "Level Up!",
                        "color": (255, 220, 70),
                        "expire": time.time() + 3.0,
                        "kind": "level_up",
                    })
        elif t == "DIALOGUE":
            self.dialogue = {
                "npc_id": msg["npc_id"], "npc_name": msg["npc_name"], "lines": msg["lines"],
                "shop_id": msg.get("shop_id"), "quest": msg.get("quest"),
                "forge": msg.get("forge"), "bank": msg.get("bank"),
            }
            self.show_shop_panel = False
        elif t == "SHOP_STATE":
            self.shop = msg
        elif t == "BANK_STATE":
            self.bank = msg
            self.show_bank = True
            self.show_shop_panel = False
            self.dialogue = None
            self.bank_inv_scroll = 0
            # Keep page in range if vault grew/shrank
            slots_n = int(msg.get("bank_slots", 96))
            max_page = max(0, (slots_n - 1) // max(1, self.bank_page_size))
            self.bank_page = max(0, min(self.bank_page, max_page))
            if self.player:
                if "coins" in msg:
                    self.player["coins"] = msg["coins"]
                if "inventory" in msg:
                    self.player["inventory"] = {
                        str(k): v for k, v in (msg["inventory"] or {}).items()
                    }
                if "bank_coins" in msg:
                    self.player["bank_coins"] = msg["bank_coins"]
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
            if self.state == "STAT_ALLOC":
                self.stat_alloc_error = msg["message"]
                self.login_error = msg["message"]

    def handle_combat_event(self, msg):
        kind = msg.get("kind", "")
        did_hit = msg.get("hit")
        if did_hit is None:
            did_hit = msg.get("damage", 0) > 0

        # Place splat on the defender. Prefer players for monster→player hits so
        # overlapping player/monster IDs can't pin the star on the wrong sprite.
        x = y = None
        def_id = msg.get("defender_id")
        if kind == "monster_hits_player":
            if self.player and def_id == self.player["id"]:
                x, y = self.player["x"], self.player["y"]
            elif def_id in self.players:
                p = self.players[def_id]
                x, y = p["x"], p["y"]
        elif kind == "player_hits_monster":
            m = self.monsters.get(def_id)
            if m:
                x, y = m["x"], m["y"]
        elif kind == "pet_hits_monster":
            m = self.monsters.get(def_id)
            if m:
                x, y = m["x"], m["y"]
        else:
            if def_id in self.players:
                p = self.players[def_id]
                x, y = p["x"], p["y"]
            elif def_id in self.monsters:
                m = self.monsters[def_id]
                x, y = m["x"], m["y"]

        now = time.time()
        self.attack_anims[msg["attacker_id"]] = now + 0.45
        if x is not None:
            if not did_hit:
                text = "MISS"
                splat = "hit_miss"
                color = (90, 180, 255)
                if kind == "monster_hits_player" and self.player and def_id == self.player["id"]:
                    self.add_chat("The monster missed!")
            else:
                text = str(msg["damage"])
                if kind in ("player_hits_monster", "pet_hits_monster"):
                    splat = "hit_red"
                    color = (255, 70, 55)
                elif kind == "monster_hits_player":
                    # Cool blue hitsplat on you when a monster connects
                    splat = "hit_blue"
                    color = (70, 160, 255)
                else:
                    splat = "hit_red"
                    color = (255, 70, 55)
            self.floaters.append({
                "x": x, "y": y, "text": text,
                "color": color, "expire": now + 1.05, "kind": splat,
            })

    # ------------------------------------------------------------------
    def handle_events(self):
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.running = False
            elif self.state == "LOGIN":
                self.handle_login_event(event)
            elif self.state == "STAT_ALLOC":
                self.handle_stat_alloc_event(event)
            elif self.state == "GAME":
                self.handle_game_event(event)

    def update_inventory_hover(self):
        """Track which inventory slot the mouse is over (for tooltips)."""
        self.inv_hover_slot = None
        if self.state != "GAME" or not self.player or not self.show_inventory:
            return
        if self.show_bank or self.show_forge or self.show_cook or self.show_equipment or self.show_help or self.show_shop_panel or self.show_skills or self.show_pets or self.show_travel:
            return
        mx, my = pygame.mouse.get_pos()
        for slot, rect in self.inventory_slot_rects().items():
            if rect.collidepoint(mx, my):
                entry = self.player["inventory"].get(str(slot)) or self.player["inventory"].get(slot)
                if entry:
                    self.inv_hover_slot = slot
                return

    def set_login_mode(self, mode):
        if mode == self.login_mode:
            return
        self.login_mode = mode
        self.login_error = ""
        if mode == "login" and self.active_field == "char_name":
            self.active_field = "username"

    def login_layout(self):
        """Shared rects for login draw + click hit-testing."""
        panel_w, panel_h = 440, 470 if self.login_mode == "register" else 410
        panel = pygame.Rect((SCREEN_W - panel_w) // 2, (SCREEN_H - panel_h) // 2 + 10, panel_w, panel_h)
        tab_y = panel.y + 88
        tab_h = 34
        gap = 8
        tab_w = (panel.w - 48 - gap) // 2
        login_tab = pygame.Rect(panel.x + 24, tab_y, tab_w, tab_h)
        register_tab = pygame.Rect(login_tab.right + gap, tab_y, tab_w, tab_h)
        field_x = panel.x + 36
        field_w = panel.w - 72
        user_y = tab_y + 56
        pass_y = user_y + 62
        char_y = pass_y + 62
        submit_y = (char_y + 58) if self.login_mode == "register" else (pass_y + 58)
        submit = pygame.Rect(field_x, submit_y, field_w, 44)
        hiscores = pygame.Rect(panel.centerx - 70, submit.bottom + 14, 140, 30)
        return {
            "panel": panel,
            "login_tab": login_tab,
            "register_tab": register_tab,
            "field_x": field_x,
            "field_w": field_w,
            "user_y": user_y,
            "pass_y": pass_y,
            "char_y": char_y,
            "submit": submit,
            "hiscores": hiscores,
        }

    def handle_login_event(self, event):
        if self.show_leaderboard:
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    self.show_leaderboard = False
                elif event.key == pygame.K_LEFT:
                    self.cycle_leaderboard_skill(-1)
                elif event.key == pygame.K_RIGHT:
                    self.cycle_leaderboard_skill(1)
            elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                self.handle_leaderboard_click(event.pos)
            return

        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_TAB:
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
            if lay["login_tab"].collidepoint(mx, my):
                self.set_login_mode("login")
                return
            if lay["register_tab"].collidepoint(mx, my):
                self.set_login_mode("register")
                return
            if lay["hiscores"].collidepoint(mx, my):
                self.request_leaderboard()
                return
            if lay["submit"].collidepoint(mx, my):
                self.submit_login()
                return
            fx, fw = lay["field_x"], lay["field_w"]
            if fx <= mx <= fx + fw:
                if lay["user_y"] <= my <= lay["user_y"] + 38:
                    self.active_field = "username"
                elif lay["pass_y"] <= my <= lay["pass_y"] + 38:
                    self.active_field = "password"
                elif self.login_mode == "register" and lay["char_y"] <= my <= lay["char_y"] + 38:
                    self.active_field = "char_name"

    def request_leaderboard(self):
        self.net.send("LEADERBOARD", limit=5)

    def cycle_leaderboard_skill(self, delta):
        skills = self.leaderboard_skills or list(self.leaderboard.keys())
        if not skills:
            return
        try:
            idx = skills.index(self.leaderboard_skill)
        except ValueError:
            idx = 0
        self.leaderboard_skill = skills[(idx + delta) % len(skills)]

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
            if self.show_bank:
                if event.key == pygame.K_ESCAPE:
                    self.show_bank = False
                elif event.key in (pygame.K_LEFT, pygame.K_a, pygame.K_PAGEUP):
                    self.bank_page = max(0, self.bank_page - 1)
                elif event.key in (pygame.K_RIGHT, pygame.K_d, pygame.K_PAGEDOWN):
                    self.bank_page += 1
                elif event.key == pygame.K_UP:
                    self.bank_inv_scroll = max(0, self.bank_inv_scroll - 1)
                elif event.key == pygame.K_DOWN:
                    self.bank_inv_scroll += 1
                return
            if self.show_forge or self.show_cook or self.show_equipment or self.show_help or self.show_skills or self.show_pets or self.show_travel:
                if event.key == pygame.K_ESCAPE:
                    self.show_forge = False
                    self.show_cook = False
                    self.show_equipment = False
                    self.show_help = False
                    self.show_skills = False
                    self.show_pets = False
                    self.show_travel = False
                elif event.key == pygame.K_m:
                    self.toggle_travel_modal()
                elif event.key == pygame.K_h:
                    self.show_help = not self.show_help
                    if self.show_help:
                        self.show_forge = False
                        self.show_cook = False
                        self.show_equipment = False
                        self.show_skills = False
                        self.show_pets = False
                        self.show_travel = False
                elif event.key == pygame.K_e:
                    self.show_equipment = not self.show_equipment
                    if self.show_equipment:
                        self.show_forge = False
                        self.show_cook = False
                        self.show_help = False
                        self.show_skills = False
                        self.show_pets = False
                        self.show_travel = False
                elif event.key == pygame.K_f:
                    self.show_forge = not self.show_forge
                    if self.show_forge:
                        self.show_equipment = False
                        self.show_cook = False
                        self.show_help = False
                        self.show_skills = False
                        self.show_pets = False
                        self.show_travel = False
                elif event.key == pygame.K_c:
                    self.show_cook = False
                elif event.key == pygame.K_TAB:
                    self.toggle_skills_modal()
                # Tab keys only when unlocked (no specific station)
                elif self.show_forge and self.forge_station is None and event.key == pygame.K_1:
                    self.forge_tab = "smelt"
                elif self.show_forge and self.forge_station is None and event.key == pygame.K_2:
                    self.forge_tab = "smith"
                return

            if event.key == pygame.K_RETURN:
                self.chat_typing = True
                self.chat_text = ""
            elif event.key == pygame.K_UP:
                self.clear_walk()
                self.try_move(0, -1)
            elif event.key == pygame.K_DOWN:
                self.clear_walk()
                self.try_move(0, 1)
            elif event.key == pygame.K_LEFT:
                self.clear_walk()
                self.try_move(-1, 0)
            elif event.key == pygame.K_RIGHT:
                self.clear_walk()
                self.try_move(1, 0)
            elif event.key == pygame.K_i:
                self.show_inventory = not self.show_inventory
            elif event.key == pygame.K_TAB:
                self.toggle_skills_modal()
            elif event.key == pygame.K_q:
                self.show_quests = not self.show_quests
            elif event.key == pygame.K_x:
                self.show_xp = not self.show_xp
            elif event.key == pygame.K_p:
                self.toggle_auto_pickup()
            elif event.key == pygame.K_m:
                self.toggle_travel_modal()
            elif event.key == pygame.K_b:
                self.try_open_bank()
            elif event.key == pygame.K_e:
                self.show_equipment = not self.show_equipment
                if self.show_equipment:
                    self.show_forge = False
                    self.show_cook = False
                    self.show_help = False
                    self.show_skills = False
                    self.show_travel = False
                    self.show_pets = False
            elif event.key == pygame.K_c:
                if self.near_range():
                    if self.show_cook:
                        self.show_cook = False
                    else:
                        self.open_cook()
                else:
                    spots = [s for s in self.interactables if s.get("kind") in ("range", "fireplace")]
                    fire_spots = []
                    for key in self.fires:
                        fx, fy = map(int, key.split(","))
                        fire_spots.append({"x": fx, "y": fy})
                    candidates = spots + fire_spots
                    if candidates:
                        px, py = self.player_xy()
                        best = min(candidates, key=lambda s: max(abs(s["x"] - px), abs(s["y"] - py)))
                        goals = self.adjacent_goals(best["x"], best["y"])
                        if self.tile_walkable(best["x"], best["y"]):
                            goals = set(goals) | {(best["x"], best["y"])}
                        self.walk_and_act(goals, {"type": "COOK"})
                    else:
                        self.chat_log.append("[!] Light logs with a tinderbox, or use a cooking hearth.")
                        self.chat_log = self.chat_log[-8:]
            elif event.key == pygame.K_f:
                if self.near_forge():
                    if self.show_forge:
                        self.show_forge = False
                    else:
                        self.open_forge_at()
                else:
                    # Walk to nearest furnace/anvil then open
                    spots = [s for s in self.interactables if s.get("kind") in ("furnace", "anvil", "forge")]
                    if spots:
                        best = min(spots, key=lambda s: max(abs(s["x"] - self.player_xy()[0]), abs(s["y"] - self.player_xy()[1])))
                        goals = self.adjacent_goals(best["x"], best["y"])
                        if self.tile_walkable(best["x"], best["y"]):
                            goals = set(goals) | {(best["x"], best["y"])}
                        self.walk_and_act(goals, {
                            "type": "FORGE", "kind": best.get("kind"),
                        })
                    else:
                        self.chat_log.append("[!] Enter the smithy (east of the path) and stand by the furnace or anvil.")
                        self.chat_log = self.chat_log[-8:]
            elif event.key == pygame.K_h:
                self.show_help = not self.show_help
                if self.show_help:
                    self.show_equipment = False
                    self.show_forge = False
                    self.show_cook = False
                    self.show_skills = False
            elif event.key == pygame.K_g:
                self.clear_walk()
                self.net.send("PICKUP")
            elif event.key == pygame.K_SPACE:
                self.clear_walk()
                self.try_attack_nearest()
            elif event.key in (pygame.K_1, pygame.K_2, pygame.K_3, pygame.K_4):
                styles = ("attack", "strength", "defence", "hitpoints")
                self.set_combat_style(styles[event.key - pygame.K_1])
            elif event.key == pygame.K_ESCAPE:
                self.show_forge = False
                self.show_equipment = False
                self.show_help = False
                self.show_bank = False
                self.show_shop_panel = False
                self.show_skills = False
                self.show_pets = False
                self.show_cook = False
                self.clear_walk()
        elif event.type == pygame.MOUSEWHEEL:
            if self.state == "GAME" and self.show_bank:
                mx, my = pygame.mouse.get_pos()
                box = pygame.Rect(120, 50, 780, 560)
                mid_x = box.x + box.w // 2
                if box.collidepoint(mx, my):
                    if mx < mid_x:
                        self.bank_inv_scroll = max(0, self.bank_inv_scroll - event.y)
                    else:
                        self.bank_page = max(0, self.bank_page - event.y)
        elif event.type == pygame.MOUSEBUTTONDOWN:
            self.handle_mouse_click(event)

    def toggle_auto_pickup(self):
        on = not bool((self.player or {}).get("auto_pickup_items"))
        self.net.send("SET_OPTION", auto_pickup_items=on)
        if self.player is not None:
            self.player["auto_pickup_items"] = on

    def logout(self):
        """Return to the login screen and free the character slot on the server."""
        if self.state not in ("GAME", "STAT_ALLOC"):
            return
        self._logging_out = True
        try:
            self.net.send("LOGOUT")
        except Exception:
            pass
        # Clear session UI / world caches immediately
        self.state = "LOGIN"
        self.login_error = ""
        self.login_mode = "login"
        self.player = None
        self.players = {}
        self.monsters = {}
        self.pets = []
        self.tiles = []
        self.world_w = self.world_h = 0
        self.npcs = []
        self.resources = {}
        self.ground_items = {}
        self.quests = {}
        self.dialogue = None
        self.shop = None
        self.show_shop_panel = False
        self.trade_incoming = None
        self.trade_state = None
        self.show_equipment = False
        self.show_forge = False
        self.show_cook = False
        self.show_help = False
        self.show_skills = False
        self.show_pets = False
        self.show_bank = False
        self.bank = None
        self.chat_typing = False
        self.chat_text = ""
        self.floaters = []
        self.attack_anims = {}
        self.clear_walk()
        self.active_field = "username"
        # If the socket already dropped, reconnect now; otherwise wait for _DISCONNECTED.
        if not self.net.connected:
            self._logging_out = False
            self.net.reconnect()

    def near_bank(self, px=None, py=None):
        if not self.player:
            return False
        if px is None or py is None:
            px, py = self.player_xy()
        for spot in self.interactables:
            if spot.get("kind") == "bank" and max(abs(spot["x"] - px), abs(spot["y"] - py)) <= 1:
                return True
        for n in self.npcs:
            if n.get("bank") and max(abs(n["x"] - px), abs(n["y"] - py)) <= 1:
                return True
            if n.get("id") == "banker_iris" and max(abs(n["x"] - px), abs(n["y"] - py)) <= 1:
                return True
        return False

    def try_open_bank(self):
        if self.near_bank():
            self.net.send("BANK_OPEN")
            return
        spots = [s for s in self.interactables if s.get("kind") == "bank"]
        if spots:
            best = min(spots, key=lambda s: max(abs(s["x"] - self.player_xy()[0]), abs(s["y"] - self.player_xy()[1])))
            goals = self.adjacent_goals(best["x"], best["y"])
            if self.tile_walkable(best["x"], best["y"]):
                goals = set(goals) | {(best["x"], best["y"])}
            self.walk_and_act(goals, {"type": "BANK"})
        else:
            self.chat_log.append("[!] Enter the Village Bank (east of the crossroads) and stand by the booth.")
            self.chat_log = self.chat_log[-8:]

    def near_forge(self, kind=None, px=None, py=None):
        """True if beside a forge station. kind=None accepts furnace or anvil."""
        if not self.player:
            return False
        if px is None or py is None:
            px, py = self.player_xy()
        wanted = {kind} if kind in ("furnace", "anvil", "forge") else {"furnace", "anvil", "forge"}
        for spot in self.interactables:
            if spot.get("kind") in wanted:
                if max(abs(spot["x"] - px), abs(spot["y"] - py)) <= 1:
                    return True
        if kind in (None, "forge"):
            for n in self.npcs:
                if n.get("id") == "blacksmith_gareth" and max(abs(n["x"] - px), abs(n["y"] - py)) <= 1:
                    return True
        return False

    def open_forge_at(self, kind=None):
        self.show_forge = True
        self.show_cook = False
        self.show_equipment = False
        self.show_help = False
        self.show_skills = False
        # Resolve station from argument or nearest neighbour
        if kind not in ("furnace", "anvil"):
            if self.near_forge("furnace"):
                kind = "furnace"
            elif self.near_forge("anvil"):
                kind = "anvil"
            else:
                kind = None
        self.forge_station = kind
        if kind == "furnace":
            self.forge_tab = "smelt"
            self.forge_gear = "bar"
        elif kind == "anvil":
            self.forge_tab = "smith"
            if self.forge_gear == "bar":
                self.forge_gear = "all"
        # Prefer the highest metal you can currently work
        smith_lvl = (self.player.get("levels") or {}).get("smithing", 1) if self.player else 1
        if smith_lvl >= 70:
            self.forge_metal = "adamant"
        elif smith_lvl >= 50:
            self.forge_metal = "mithril"
        elif smith_lvl >= 30:
            self.forge_metal = "steel"
        elif smith_lvl >= 15:
            self.forge_metal = "iron"
        else:
            self.forge_metal = "bronze"

    def near_range(self, px=None, py=None):
        if not self.player:
            return False
        if px is None or py is None:
            px, py = self.player_xy()
        for spot in self.interactables:
            if spot.get("kind") in ("range", "fireplace"):
                if max(abs(spot["x"] - px), abs(spot["y"] - py)) <= 1:
                    return True
        for key in self.fires:
            fx, fy = map(int, key.split(","))
            if max(abs(fx - px), abs(fy - py)) <= 1:
                return True
        return False

    def open_cook(self):
        self.show_cook = True
        self.show_forge = False
        self.show_equipment = False
        self.show_help = False
        self.show_skills = False

    def toggle_skills_modal(self):
        self.show_skills = not self.show_skills
        if self.show_skills:
            self.show_forge = False
            self.show_cook = False
            self.show_equipment = False
            self.show_help = False
            self.show_bank = False
            self.show_shop_panel = False
            self.show_pets = False

    def toggle_pets_modal(self):
        owned = (self.player or {}).get("owned_pets") or []
        if not owned:
            self.chat_log.append("[!] Buy a pet at the Pet Emporium (Luna) first.")
            self.chat_log = self.chat_log[-8:]
            return
        self.show_pets = not self.show_pets
        if self.show_pets:
            self.show_forge = False
            self.show_cook = False
            self.show_equipment = False
            self.show_help = False
            self.show_bank = False
            self.show_shop_panel = False
            self.show_skills = False

    def player_combat_level(self):
        if not self.player:
            return 1
        levels = self.player.get("levels") or {}
        return combat.combat_level(
            levels.get("attack", 1), levels.get("strength", 1),
            levels.get("defence", 1), levels.get("hitpoints", 10),
        )

    def player_total_level(self):
        if not self.player:
            return 0
        levels = self.player.get("levels") or {}
        return sum(int(levels.get(s, 1)) for s in XP_SKILLS)

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
            self.dialogue = None  # shop modal replaces dialogue
        elif event.key == pygame.K_b and self.dialogue.get("bank"):
            self.dialogue = None
            self.net.send("BANK_OPEN")
        elif event.key == pygame.K_s and self.dialogue.get("forge"):
            self.dialogue = None
            self.open_forge_at()
        elif event.key == pygame.K_a and quest and quest["state"] == "offerable":
            self.net.send("QUEST_ACCEPT", quest_id=quest["quest_id"])
            self.dialogue = None
        elif event.key == pygame.K_t and quest and quest["state"] == "ready":
            self.net.send("QUEST_TURNIN", quest_id=quest["quest_id"])
            self.dialogue = None

    def try_move(self, dx, dy):
        self.net.send("MOVE", dx=dx, dy=dy)

    # -- click-to-walk --------------------------------------------------
    def player_xy(self):
        if not self.player:
            return 0, 0
        px, py = self.player["x"], self.player["y"]
        live = self.players.get(self.player["id"])
        if live:
            px, py = live["x"], live["y"]
        return px, py

    def clear_walk(self):
        self.walk_path = []
        self.pending_action = None

    def tile_walkable(self, x, y):
        if not (0 <= y < len(self.tiles) and 0 <= x < self.world_w):
            return False
        return self.tiles[y][x] in wm.WALKABLE_TILES

    def adjacent_goals(self, tx, ty, include_self=False):
        goals = set()
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                if dx == 0 and dy == 0 and not include_self:
                    continue
                nx, ny = tx + dx, ty + dy
                if self.tile_walkable(nx, ny):
                    goals.add((nx, ny))
        return goals

    def find_path(self, sx, sy, goals):
        """BFS shortest path. Returns list of tiles to step onto (excludes start)."""
        if not goals:
            return None
        if (sx, sy) in goals:
            return []
        from collections import deque
        q = deque([(sx, sy)])
        came = {(sx, sy): None}
        found = None
        # Cap search so huge empty clicks stay cheap
        limit = 2500
        visited = 0
        while q and visited < limit:
            x, y = q.popleft()
            visited += 1
            for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                nx, ny = x + dx, y + dy
                if (nx, ny) in came:
                    continue
                if not self.tile_walkable(nx, ny):
                    continue
                came[(nx, ny)] = (x, y)
                if (nx, ny) in goals:
                    found = (nx, ny)
                    q.clear()
                    break
                q.append((nx, ny))
        if found is None:
            return None
        path = []
        cur = found
        while cur != (sx, sy):
            path.append(cur)
            cur = came[cur]
        path.reverse()
        return path

    def can_do_action(self, action, px, py):
        if not action:
            return True
        kind = action["type"]
        if kind == "ATTACK":
            m = self.monsters.get(action["target_id"])
            return bool(m and m["alive"] and max(abs(m["x"] - px), abs(m["y"] - py)) <= 1)
        if kind == "TALK":
            for n in self.npcs:
                if n["id"] == action["npc_id"]:
                    return max(abs(n["x"] - px), abs(n["y"] - py)) <= 1
            return False
        if kind == "TRADE":
            p = self.players.get(action["target_player_id"])
            return bool(p and max(abs(p["x"] - px), abs(p["y"] - py)) <= 1)
        if kind == "GATHER":
            return max(abs(action["x"] - px), abs(action["y"] - py)) <= 1
        if kind == "FORGE":
            return self.near_forge(action.get("kind"), px, py)
        if kind == "COOK":
            return self.near_range(px, py)
        if kind == "BANK":
            return self.near_bank(px, py)
        if kind == "PICKUP":
            # Standing on the loot tile, or adjacent if the tile itself is blocked
            ax, ay = action["x"], action["y"]
            if (px, py) == (ax, ay):
                return True
            return max(abs(ax - px), abs(ay - py)) <= 1 and not self.tile_walkable(ax, ay)
        return False

    def fire_action(self, action):
        if not action:
            return
        kind = action["type"]
        if kind == "ATTACK":
            self.net.send("ATTACK", target_id=action["target_id"])
        elif kind == "TALK":
            self.net.send("TALK", npc_id=action["npc_id"])
        elif kind == "TRADE":
            self.net.send("TRADE_REQUEST", target_player_id=action["target_player_id"])
        elif kind == "GATHER":
            self.net.send("GATHER", x=action["x"], y=action["y"])
        elif kind == "FORGE":
            self.open_forge_at(action.get("kind"))
        elif kind == "COOK":
            self.open_cook()
        elif kind == "BANK":
            self.net.send("BANK_OPEN")
        elif kind == "PICKUP":
            self.net.send("PICKUP")

    def walk_and_act(self, goals, action=None):
        """Path to any tile in goals, then perform action (if any)."""
        px, py = self.player_xy()
        if action and self.can_do_action(action, px, py):
            self.fire_action(action)
            self.clear_walk()
            return
        path = self.find_path(px, py, goals)
        if path is None:
            self.chat_log.append("[!] Can't reach that.")
            self.chat_log = self.chat_log[-8:]
            self.clear_walk()
            return
        self.walk_path = path
        self.pending_action = action
        self._next_walk_at = 0.0  # step immediately
        # Already standing on a goal with no steps
        if not path and action:
            self.fire_action(action)
            self.clear_walk()

    def update_walk(self):
        if self.state != "GAME" or not self.player:
            return
        px, py = self.player_xy()

        # Chase / complete pending action when in range
        if self.pending_action:
            act = self.pending_action
            if act["type"] == "ATTACK":
                m = self.monsters.get(act["target_id"])
                if not m or not m["alive"]:
                    self.clear_walk()
                    return
                if self.can_do_action(act, px, py):
                    self.fire_action(act)
                    self.clear_walk()
                    return
                goals = self.adjacent_goals(m["x"], m["y"])
                need = True
                if self.walk_path and self.walk_path[-1] in goals:
                    need = False
                if need:
                    path = self.find_path(px, py, goals)
                    self.walk_path = path if path is not None else []
            elif self.can_do_action(act, px, py):
                self.fire_action(act)
                self.clear_walk()
                return

        if not self.walk_path:
            if self.pending_action and self.pending_action["type"] != "ATTACK":
                self.chat_log.append("[!] Couldn't reach that.")
                self.chat_log = self.chat_log[-8:]
                self.clear_walk()
            return

        now = time.time()
        if now < self._next_walk_at:
            return

        nx, ny = self.walk_path[0]
        dx, dy = nx - px, ny - py
        if abs(dx) + abs(dy) != 1:
            if self.pending_action and self.pending_action["type"] == "ATTACK":
                m = self.monsters.get(self.pending_action["target_id"])
                goals = self.adjacent_goals(m["x"], m["y"]) if m else set()
            else:
                goals = {self.walk_path[-1]} if self.walk_path else set()
            path = self.find_path(px, py, goals) if goals else None
            self.walk_path = path or []
            return

        self.net.send("MOVE", dx=dx, dy=dy)
        self.walk_path.pop(0)
        self.player["x"], self.player["y"] = nx, ny
        if self.player["id"] in self.players:
            self.players[self.player["id"]]["x"] = nx
            self.players[self.player["id"]]["y"] = ny
        self._next_walk_at = now + 0.2

        if self.pending_action and self.can_do_action(self.pending_action, nx, ny):
            self.fire_action(self.pending_action)
            self.clear_walk()

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
        px, py = self.player_xy()
        vis_w, vis_h = MAP_W // TILE, MAP_H // TILE
        max_cam_x = max(0, self.world_w - vis_w)
        max_cam_y = max(0, self.world_h - vis_h)
        cam_x = max(0, min(px - vis_w // 2, max_cam_x))
        cam_y = max(0, min(py - vis_h // 2, max_cam_y))
        return cam_x, cam_y

    def handle_mouse_click(self, event):
        mx, my = event.pos
        if self.show_bank:
            self.handle_bank_click(mx, my, event.button)
            return
        if self.show_forge:
            self.handle_forge_click(mx, my)
            return
        if self.show_cook:
            self.handle_cook_click(mx, my)
            return
        if self.show_skills:
            box = pygame.Rect(160, 40, 640, 620)
            if not box.collidepoint(mx, my):
                self.show_skills = False
            return
        if self.show_pets:
            self.handle_pets_click(mx, my)
            return
        if self.show_equipment:
            self.handle_equipment_click(mx, my)
            return
        if self.show_shop_panel and self.shop:
            self.handle_shop_click(mx, my, event.button)
            return
        if self.show_help:
            box = pygame.Rect(120, 30, 580, 640)
            if not box.collidepoint(mx, my):
                self.show_help = False
            return
        if mx >= SIDEBAR_X or my >= MAP_H:
            self.handle_sidebar_click(mx, my, event.button)
            return
        if not self.player:
            return
        tile = self.screen_to_tile(mx, my)
        if tile is None:
            return
        tx, ty = tile

        # smithy stations / doors / dungeon / bank — walk then act
        for spot in self.interactables:
            if spot["x"] == tx and spot["y"] == ty:
                kind = spot.get("kind")
                if kind in ("furnace", "anvil", "forge"):
                    goals = self.adjacent_goals(tx, ty)
                    if self.tile_walkable(tx, ty):
                        goals = set(goals) | {(tx, ty)}
                    self.walk_and_act(goals, {"type": "FORGE", "kind": kind})
                    return
                if kind in ("range", "fireplace"):
                    goals = self.adjacent_goals(tx, ty)
                    if self.tile_walkable(tx, ty):
                        goals = set(goals) | {(tx, ty)}
                    self.walk_and_act(goals, {"type": "COOK"})
                    return
                if kind == "bank":
                    goals = self.adjacent_goals(tx, ty)
                    if self.tile_walkable(tx, ty):
                        goals = set(goals) | {(tx, ty)}
                    self.walk_and_act(goals, {"type": "BANK"})
                    return
                if kind in ("door", "dungeon_entrance"):
                    self.click_door(spot)
                    return

        # Player-lit campfire — cook
        if f"{tx},{ty}" in self.fires:
            goals = self.adjacent_goals(tx, ty)
            if self.tile_walkable(tx, ty):
                goals = set(goals) | {(tx, ty)}
            self.walk_and_act(goals, {"type": "COOK"})
            return

        # ground loot first so you can click coins/items on a pile
        key = f"{tx},{ty}"
        if key in self.ground_items and self.ground_items[key]:
            if self.tile_walkable(tx, ty):
                self.walk_and_act({(tx, ty)}, {"type": "PICKUP", "x": tx, "y": ty})
            else:
                self.walk_and_act(self.adjacent_goals(tx, ty), {"type": "PICKUP", "x": tx, "y": ty})
            return
        # monster?
        for m in self.monsters.values():
            if m["alive"] and m["x"] == tx and m["y"] == ty:
                self.walk_and_act(self.adjacent_goals(m["x"], m["y"]), {
                    "type": "ATTACK", "target_id": m["id"],
                })
                return
        # npc?
        for n in self.npcs:
            if n["x"] == tx and n["y"] == ty:
                self.walk_and_act(self.adjacent_goals(n["x"], n["y"]), {
                    "type": "TALK", "npc_id": n["id"],
                })
                return
        # other player -> trade request
        for p in self.players.values():
            if p["id"] != self.player["id"] and p["x"] == tx and p["y"] == ty:
                self.walk_and_act(self.adjacent_goals(p["x"], p["y"]), {
                    "type": "TRADE", "target_player_id": p["id"],
                })
                return
        # resource node (ores, trees, fishing spots on water)
        if key in self.resources:
            self.walk_and_act(self.adjacent_goals(tx, ty), {"type": "GATHER", "x": tx, "y": ty})
            return
        # Click bare water: fish that tile from an adjacent walkable tile
        if (0 <= ty < len(self.tiles) and 0 <= tx < self.world_w
                and self.tiles[ty][tx] == wm.WATER):
            self.walk_and_act(self.adjacent_goals(tx, ty), {"type": "GATHER", "x": tx, "y": ty})
            return
        # Empty ground — walk there
        if self.tile_walkable(tx, ty):
            self.walk_and_act({(tx, ty)}, None)
            return

    def handle_sidebar_click(self, mx, my, button):
        if self.logout_btn_rect and self.logout_btn_rect.collidepoint(mx, my):
            self.logout()
            return
        if self.skills_btn_rect and self.skills_btn_rect.collidepoint(mx, my):
            self.toggle_skills_modal()
            return
        if self.pets_btn_rect and self.pets_btn_rect.collidepoint(mx, my):
            self.toggle_pets_modal()
            return
        if self.auto_pickup_btn_rect and self.auto_pickup_btn_rect.collidepoint(mx, my):
            self.toggle_auto_pickup()
            return
        if self.trade_state:
            self.handle_trade_inventory_click(mx, my)
            return
        for rect, style, _label in self.combat_style_button_rects():
            if rect.collidepoint(mx, my):
                self.set_combat_style(style)
                return
        if self.show_inventory:
            self.handle_inventory_click(mx, my, button)

    def set_combat_style(self, style):
        self.combat_style = style
        self.net.send("SET_COMBAT_STYLE", style=style)

    def inventory_slot_rects(self):
        rects = {}
        cols, rows = 4, 6
        ox = SIDEBAR_X + 16
        oy = getattr(self, "_inventory_oy", 348)
        size = 48
        for slot in range(cols * rows):
            col, row = slot % cols, slot // cols
            rects[slot] = pygame.Rect(ox + col * (size + 4), oy + row * (size + 4), size, size)
        return rects

    def combat_style_button_rects(self):
        """2x2 combat style buttons in the sidebar."""
        styles = ("attack", "strength", "defence", "hitpoints")
        labels = {"attack": "Att", "strength": "Str", "defence": "Def", "hitpoints": "HP"}
        rects = []
        ox = SIDEBAR_X + 16
        oy = getattr(self, "_combat_style_oy", 268)
        bw, bh = 64, 26
        for i, style in enumerate(styles):
            col, row = i % 2, i // 2
            rect = pygame.Rect(ox + col * (bw + 8), oy + row * (bh + 6), bw, bh)
            rects.append((rect, style, labels[style]))
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
                if button == 3:  # right-click
                    if item.get("karma_xp"):
                        self.net.send("USE_ITEM", slot_index=slot)  # bury one
                    else:
                        self.net.send("DROP", slot_index=slot, qty=1)
                elif item.get("equip_slot"):
                    self.net.send("EQUIP", slot_index=slot)
                elif item["type"] == "food":
                    self.net.send("USE_ITEM", slot_index=slot)
                elif item.get("karma_xp"):
                    self.net.send("USE_ITEM", slot_index=slot)  # bury one
                elif entry["item_id"] in ("logs", "oak_logs", "tinderbox"):
                    self.net.send("USE_ITEM", slot_index=slot)  # light fire
                return

    def sell_price(self, item_id):
        return max(1, int(ITEMS.get(item_id, {}).get("value", 0) * 0.4))

    def handle_shop_click(self, mx, my, button):
        box = pygame.Rect(160, 70, 700, 520)
        if not box.collidepoint(mx, my):
            self.show_shop_panel = False
            return
        # Close button
        close = pygame.Rect(box.right - 36, box.y + 10, 26, 26)
        if close.collidepoint(mx, my):
            self.show_shop_panel = False
            return
        for rect, item_id in self.shop_buy_rects:
            if rect.collidepoint(mx, my):
                self.net.send("SHOP_BUY", shop_id=self.shop["shop_id"], item_id=item_id, qty=1)
                return
        if self.shop.get("buys", True):
            for rect, slot, item_id in self.shop_sell_rects:
                if rect.collidepoint(mx, my):
                    self.net.send("SHOP_SELL", shop_id=self.shop["shop_id"], item_id=item_id, qty=1)
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
        elif self.state == "STAT_ALLOC":
            self.draw_stat_alloc()
        else:
            self.draw_game()
        pygame.display.flip()

    def remaining_stat_points(self):
        return self.stat_alloc_points - sum(self.stat_alloc.values())

    def handle_stat_alloc_event(self, event):
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
                if action == "plus" and self.remaining_stat_points() > 0:
                    self.stat_alloc[skill] += 1
                    self.stat_alloc_error = ""
                elif action == "minus" and self.stat_alloc[skill] > 0:
                    self.stat_alloc[skill] -= 1
                    self.stat_alloc_error = ""
                return
            confirm = pygame.Rect(400, 520, 400, 44)
            if confirm.collidepoint(mx, my):
                self.submit_stat_alloc()

    def submit_stat_alloc(self):
        left = self.remaining_stat_points()
        if left != 0:
            self.stat_alloc_error = f"Spend exactly 10 points ({left} left)."
            return
        self.net.send("ALLOCATE_STATS", stats=dict(self.stat_alloc))

    def draw_stat_alloc(self):
        title = self.font_big.render("Choose your starting stats", True, WHITE)
        self.screen.blit(title, (SCREEN_W // 2 - title.get_width() // 2, 80))
        name = (self.player or {}).get("name", "Adventurer")
        sub = self.font.render(f"Welcome, {name}. Distribute 10 points.", True, YELLOW)
        self.screen.blit(sub, (SCREEN_W // 2 - sub.get_width() // 2, 120))

        left = self.remaining_stat_points()
        pts = self.font_big.render(f"Points left: {left}", True, GREEN if left == 0 else WHITE)
        self.screen.blit(pts, (SCREEN_W // 2 - pts.get_width() // 2, 160))

        box = pygame.Rect(340, 210, 520, 280)
        pygame.draw.rect(self.screen, (18, 20, 28), box)
        pygame.draw.rect(self.screen, (120, 190, 255), box, 2)

        self.stat_alloc_rects = {}
        y = box.y + 24
        for skill in ("attack", "strength", "defence", "hitpoints"):
            base = self.stat_alloc_base.get(skill, 1)
            bonus = self.stat_alloc[skill]
            final = base + bonus
            label = self.font.render(f"{skill.title()}:  {base}  →  {final}", True, WHITE)
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

        hint = self.font_small.render(
            "Each point raises that skill by 1 level. Confirm when all 10 are spent.",
            True, GREY,
        )
        self.screen.blit(hint, (SCREEN_W // 2 - hint.get_width() // 2, 500))

        confirm = pygame.Rect(400, 520, 400, 44)
        ready = left == 0
        pygame.draw.rect(self.screen, (45, 100, 55) if ready else (40, 42, 50), confirm)
        pygame.draw.rect(self.screen, GREEN if ready else PANEL_LINE, confirm, 2)
        ctxt = self.font.render("Confirm & Enter World", True, WHITE if ready else GREY)
        self.screen.blit(ctxt, (confirm.x + (confirm.w - ctxt.get_width()) // 2,
                                confirm.y + (confirm.h - ctxt.get_height()) // 2))

        if self.stat_alloc_error:
            err = self.font.render(self.stat_alloc_error, True, RED)
            self.screen.blit(err, (SCREEN_W // 2 - err.get_width() // 2, 580))
        if self.login_error:
            err = self.font.render(self.login_error, True, RED)
            self.screen.blit(err, (SCREEN_W // 2 - err.get_width() // 2, 610))

    def _load_login_backdrop(self):
        """Load and cache the adventurous title-screen art."""
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
        bg = self._load_login_backdrop()
        if bg is not None:
            self.screen.blit(bg, (0, 0))
            # Gentle breathing light over the horizon / path (keeps the scene alive)
            wash = pygame.Surface((SCREEN_W, SCREEN_H), pygame.SRCALPHA)
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
            # Extra darkening behind typical panel area
            band = pygame.Surface((440, 520), pygame.SRCALPHA)
            band.fill((8, 10, 14, 70))
            v.blit(band, (SCREEN_W // 2 - 220, SCREEN_H // 2 - 260))
            self._login_vignette = v
        self.screen.blit(self._login_vignette, (0, 0))

    def draw_login(self):
        t = time.time()
        self.draw_login_backdrop(t)
        lay = self.login_layout()
        panel = lay["panel"]

        # Wooden / stone card
        shadow = panel.move(6, 8)
        pygame.draw.rect(self.screen, (8, 10, 12), shadow, border_radius=16)
        pygame.draw.rect(self.screen, (36, 32, 28), panel, border_radius=16)
        pygame.draw.rect(self.screen, (58, 50, 40), panel.inflate(-10, -10), border_radius=12)
        inner = panel.inflate(-18, -18)
        pygame.draw.rect(self.screen, (28, 30, 38), inner, border_radius=10)
        pygame.draw.rect(self.screen, ACCENT, panel, 2, border_radius=16)

        # Brand
        brand = self.font_big.render("MYTHOSCAPE", True, (255, 230, 170))
        self.screen.blit(brand, (panel.centerx - brand.get_width() // 2, panel.y + 22))
        tag = self.font_tiny.render("tiny mmorpg  ·  grab a pet, bank your loot, poke a dragon", True, (180, 170, 140))
        self.screen.blit(tag, (panel.centerx - tag.get_width() // 2, panel.y + 52))
        # Decorative underline
        ux = panel.centerx
        pygame.draw.line(self.screen, ACCENT, (ux - 70, panel.y + 72), (ux + 70, panel.y + 72), 2)
        pygame.draw.circle(self.screen, ACCENT, (ux, panel.y + 72), 3)

        self.draw_mode_tab("Login", lay["login_tab"], self.login_mode == "login")
        self.draw_mode_tab("Create Account", lay["register_tab"], self.login_mode == "register")

        self.draw_text_field("Username", "username", lay["user_y"],
                             x=lay["field_x"], w=lay["field_w"])
        self.draw_text_field("Password", "password", lay["pass_y"], mask=True,
                             x=lay["field_x"], w=lay["field_w"])
        if self.login_mode == "register":
            self.draw_text_field("Character name", "char_name", lay["char_y"],
                                 x=lay["field_x"], w=lay["field_w"])

        submit_label = "Create Account & Play!" if self.login_mode == "register" else "Enter the World"
        self.draw_button(submit_label, lay["submit"], primary=True)
        self.draw_button("Hiscores", lay["hiscores"], primary=False)

        hint = self.font_tiny.render("Tab fields  ·  Enter go  ·  F2 switch  ·  F3 hiscores", True, (130, 125, 110))
        self.screen.blit(hint, (panel.centerx - hint.get_width() // 2, lay["hiscores"].bottom + 10))

        if self.login_error:
            # Friendly error banner
            err = self.font_small.render(self.login_error, True, (255, 200, 180))
            banner = pygame.Rect(panel.x + 24, panel.bottom - 36, panel.w - 48, 26)
            pygame.draw.rect(self.screen, (70, 32, 28), banner, border_radius=6)
            pygame.draw.rect(self.screen, (200, 80, 70), banner, 1, border_radius=6)
            self.screen.blit(err, (banner.centerx - err.get_width() // 2, banner.y + 5))

        if self.show_leaderboard:
            self.draw_leaderboard_modal()

    def draw_mode_tab(self, label, rect, active):
        bg = (48, 92, 58) if active else (40, 38, 46)
        border = (120, 210, 130) if active else (70, 68, 78)
        pygame.draw.rect(self.screen, bg, rect, border_radius=8)
        pygame.draw.rect(self.screen, border, rect, 2, border_radius=8)
        text = self.font_small.render(label, True, WHITE if active else GREY)
        self.screen.blit(text, (rect.x + (rect.w - text.get_width()) // 2,
                                rect.y + (rect.h - text.get_height()) // 2))

    def draw_button(self, label, rect, primary=False):
        if primary:
            bg, border = (52, 120, 68), (140, 220, 140)
        else:
            bg, border = (42, 40, 50), PANEL_LINE
        pygame.draw.rect(self.screen, bg, rect, border_radius=10)
        pygame.draw.rect(self.screen, border, rect, 2, border_radius=10)
        # Soft top highlight
        hi = pygame.Rect(rect.x + 4, rect.y + 3, rect.w - 8, max(4, rect.h // 3))
        overlay = pygame.Surface((hi.w, hi.h), pygame.SRCALPHA)
        overlay.fill((255, 255, 255, 22 if primary else 12))
        self.screen.blit(overlay, hi.topleft)
        text = self.font.render(label, True, WHITE)
        self.screen.blit(text, (rect.x + (rect.w - text.get_width()) // 2,
                                rect.y + (rect.h - text.get_height()) // 2))

    def draw_text_field(self, label, key, y, mask=False, x=350, w=400):
        active = self.active_field == key
        lbl = self.font_tiny.render(label, True, ACCENT if active else (160, 155, 140))
        self.screen.blit(lbl, (x, y - 16))
        rect = pygame.Rect(x, y, w, 38)
        pygame.draw.rect(self.screen, (18, 20, 28), rect, border_radius=8)
        pygame.draw.rect(self.screen, ACCENT if active else PANEL_LINE, rect, 2, border_radius=8)
        text = self.fields[key]
        if mask:
            text = "•" * len(text)
        txt_surf = self.font.render(text, True, WHITE)
        self.screen.blit(txt_surf, (rect.x + 12, rect.y + 9))
        if active and int(time.time() * 2) % 2 == 0:
            cx = rect.x + 12 + txt_surf.get_width() + 2
            pygame.draw.line(self.screen, WHITE, (cx, rect.y + 8), (cx, rect.bottom - 8), 2)

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
        if self.show_bank and self.bank:
            self.draw_bank()
        if self.trade_incoming:
            self.draw_trade_incoming()
        if self.trade_state:
            self.draw_trade()
        if self.show_equipment:
            self.draw_equipment_modal()
        if self.show_forge:
            self.draw_forge_modal()
        if self.show_cook:
            self.draw_cook_modal()
        if self.show_skills:
            self.draw_skills_modal()
        if self.show_pets:
            self.draw_pets_modal()
        if self.show_help:
            self.draw_help_modal()

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

        # --- World objects: collect then Y-sort for depth ---
        px, py = self.player_xy() if self.player else (None, None)
        draw_list = []  # (sort_y, layer, draw_fn)

        def facing_for(key, x, y):
            prev = self._prev_entity_pos.get(key)
            face = self._entity_facing.get(key, 1)
            if prev is not None:
                dx = x - prev[0]
                if dx > 0:
                    face = 1
                elif dx < 0:
                    face = -1
            self._entity_facing[key] = face
            return face

        def moving_for(key, x, y):
            return self._prev_entity_pos.get(key) not in (None, (x, y))

        # Resources
        for key, rtype in self.resources.items():
            x, y = map(int, key.split(","))
            sx, sy = x - cam_x, y - cam_y
            if 0 <= sx <= vis_w and 0 <= sy <= vis_h:
                cx, cy = sx * TILE + TILE // 2, sy * TILE + TILE // 2
                label = RESOURCE_LABELS.get(rtype)
                near = px is not None and max(abs(x - px), abs(y - py)) <= 3
                color = ORE_LABEL_COLORS.get(rtype, WHITE)
                # Ghost canopy when the player walks under / behind the tree
                tree_alpha = 255
                if rtype in ("tree", "oak_tree") and px is not None:
                    dist = max(abs(x - px), abs(y - py))
                    # Same tile or adjacent (canopy covers nearby ground)
                    if dist == 0:
                        tree_alpha = 95
                    elif dist == 1:
                        tree_alpha = 130
                    elif dist == 2 and y <= py:
                        # Standing just south of the trunk — still under foliage
                        tree_alpha = 170

                def _draw_res(cx=cx, cy=cy, rtype=rtype, label=label, near=near, color=color, tree_alpha=tree_alpha):
                    self.draw_resource_sprite(rtype, cx, cy, t, alpha=tree_alpha)
                    if label and near:
                        self.blit_nameplate(label, cx, cy - TILE // 2 - 2, color)
                draw_list.append((cy + TILE // 3, 1, _draw_res))

        # Interactables
        for spot in self.interactables:
            sx, sy = spot["x"] - cam_x, spot["y"] - cam_y
            if 0 <= sx <= vis_w and 0 <= sy <= vis_h:
                cx, cy = sx * TILE + TILE // 2, sy * TILE + TILE // 2
                kind = spot.get("kind")

                def _draw_spot(cx=cx, cy=cy, spot=spot, kind=kind):
                    if kind == "furnace":
                        sprites.draw_furnace(self.screen, cx, cy, TILE, t)
                        self.blit_nameplate(spot.get("name", "Station"), cx, cy - TILE // 2 - 2)
                    elif kind == "anvil":
                        sprites.draw_anvil(self.screen, cx, cy, TILE, t)
                        self.blit_nameplate(spot.get("name", "Station"), cx, cy - TILE // 2 - 2)
                    elif kind == "forge":
                        sprites.draw_forge(self.screen, cx, cy, TILE, t)
                        self.blit_nameplate(spot.get("name", "Station"), cx, cy - TILE // 2 - 2)
                    elif kind == "door":
                        px2, py2 = self.player_xy() if self.player else (0, 0)
                        near = max(abs(spot["x"] - px2), abs(spot["y"] - py2)) <= 2
                        sprites.draw_door(self.screen, cx, cy, TILE, open_=near, t=t)
                        if near:
                            self.blit_nameplate(spot.get("name", "Door"), cx, cy - TILE // 2 - 6)
                    elif kind == "bank":
                        if spot.get("variant") == "chest":
                            sprites.draw_chest(self.screen, cx, cy, TILE, t)
                        else:
                            sprites.draw_bank_booth(self.screen, cx, cy, TILE, t)
                        self.blit_nameplate(spot.get("name", "Bank"), cx, cy - TILE // 2 - 6)
                    elif kind == "dungeon_entrance":
                        sprites.draw_dungeon_entrance(self.screen, cx, cy, TILE, t)
                        self.blit_nameplate("DUNGEON", cx, cy - TILE - 4, (210, 170, 255))
                    elif kind in ("range", "fireplace"):
                        sprites.draw_fireplace(self.screen, cx, cy, TILE, t)
                        self.blit_nameplate(spot.get("name", "Hearth"), cx, cy - TILE // 2 - 2)
                    else:
                        self.draw_furniture(kind, cx, cy, t, spot)
                # Rugs sit under feet; other furniture Y-sorts normally
                if kind == "rug":
                    draw_list.append((cy - TILE // 2, 0, _draw_spot))
                else:
                    draw_list.append((cy + TILE // 4, 2, _draw_spot))

        # Player-lit campfires
        for key in self.fires:
            x, y = map(int, key.split(","))
            sx, sy = x - cam_x, y - cam_y
            if 0 <= sx <= vis_w and 0 <= sy <= vis_h:
                cx, cy = sx * TILE + TILE // 2, sy * TILE + TILE // 2
                near = px is not None and max(abs(x - px), abs(y - py)) <= 2

                def _draw_fire(cx=cx, cy=cy, near=near):
                    sprites.draw_campfire(self.screen, cx, cy, TILE, t)
                    if near:
                        self.blit_nameplate("Fire", cx, cy - TILE // 2 - 2, (255, 170, 80))
                draw_list.append((cy + TILE // 4, 2, _draw_fire))

        # Ground items
        for key, items in self.ground_items.items():
            if not items:
                continue
            x, y = map(int, key.split(","))
            sx, sy = x - cam_x, y - cam_y
            if 0 <= sx <= vis_w and 0 <= sy <= vis_h:
                r = pygame.Rect(sx * TILE + 6, sy * TILE + 6, TILE - 12, TILE - 12)
                top = items[0]

                def _draw_loot(r=r, items=items, top=top):
                    if top.get("item_id") == "coins":
                        sprites.draw_ground_item(self.screen, r, t)
                    else:
                        icon_r = sprites.draw_ground_loot_pad(self.screen, r, t)
                        sprites.draw_item_icon(self.screen, icon_r, top["item_id"], ITEMS)
                        if len(items) > 1:
                            n = self.font_tiny.render(f"+{len(items) - 1}", True, YELLOW)
                            badge = pygame.Rect(r.right - n.get_width() - 2, r.y - 2, n.get_width() + 4, 12)
                            pygame.draw.rect(self.screen, (20, 18, 14), badge, border_radius=3)
                            self.screen.blit(n, (badge.x + 2, badge.y))
                draw_list.append((r.bottom, 0, _draw_loot))

        # NPCs
        for n in self.npcs:
            if self.entity_hidden_by_roof(n["x"], n["y"]):
                continue
            sx, sy = n["x"] - cam_x, n["y"] - cam_y
            if 0 <= sx <= vis_w and 0 <= sy <= vis_h:
                cx, cy = sx * TILE + TILE // 2, sy * TILE + TILE // 2
                nid = abs(hash(n["id"]))
                body, skin, hair = sprites.palette_for(nid)
                key = ("n", n["id"])
                face = facing_for(key, n["x"], n["y"])
                mov = moving_for(key, n["x"], n["y"])
                now_pos[key] = (n["x"], n["y"])

                def _draw_npc(cx=cx, cy=cy, body=body, skin=skin, hair=hair, n=n, face=face, mov=mov):
                    sprites.draw_humanoid_detailed(
                        self.screen, cx, cy, TILE, body, skin, hair,
                        robe=n["id"] in ROBED_NPC_IDS, t=t, facing=face, moving=mov,
                    )
                    ny, _ = self.entity_anchor(cx, cy, "character")
                    self.blit_nameplate(n["name"], cx, ny, (255, 230, 160))
                draw_list.append((cy + TILE // 2, 3, _draw_npc))

        # Monsters
        for m in self.monsters.values():
            if not m["alive"]:
                continue
            sx, sy = m["x"] - cam_x, m["y"] - cam_y
            if 0 <= sx <= vis_w and 0 <= sy <= vis_h:
                cx, cy = sx * TILE + TILE // 2, sy * TILE + TILE // 2
                hurt = m["hp"] < m["max_hp"]
                atk = self._attack_progress(m["id"], t)
                near = px is not None and max(abs(m["x"] - px), abs(m["y"] - py)) <= 5
                now_pos[("m", m["id"])] = (m["x"], m["y"])

                def _draw_mon(cx=cx, cy=cy, m=m, hurt=hurt, atk=atk, near=near):
                    sprites.draw_monster(self.screen, m["type"], cx, cy, TILE, t, hurt=hurt, attacking=atk)
                    ny, hy = self.entity_anchor(cx, cy, "monster")
                    lvl = int(m.get("level") or 1)
                    lvl_color = self.monster_threat_color(lvl)
                    if hurt or near:
                        self.blit_nameplate(m["name"], cx, ny)
                        self.draw_hp_bar(cx, hy, m["hp"], m["max_hp"])
                        self.blit_combat_level(lvl, cx, ny - 16, lvl_color)
                    else:
                        self.blit_combat_level(lvl, cx, ny, lvl_color)
                draw_list.append((cy + TILE // 2, 4, _draw_mon))

        # Pets
        for pet in self.pets:
            sx, sy = pet["x"] - cam_x, pet["y"] - cam_y
            if 0 <= sx <= vis_w and 0 <= sy <= vis_h:
                if self.entity_hidden_by_roof(pet["x"], pet["y"]):
                    owner_id = pet.get("owner_id")
                    if not (self.player and owner_id == self.player["id"] and self.player_inside_any_building()):
                        continue
                cx, cy = sx * TILE + TILE // 2, sy * TILE + TILE // 2
                hurt = pet["hp"] < pet["max_hp"]
                atk = self._attack_progress(f"pet:{pet.get('owner_id')}", t)
                mine = self.player and pet.get("owner_id") == self.player["id"]
                pkey = ("pet", pet.get("owner_id"), pet.get("pet_id") or pet.get("sprite"))
                mov = moving_for(pkey, pet["x"], pet["y"])
                face = facing_for(pkey, pet["x"], pet["y"])
                now_pos[pkey] = (pet["x"], pet["y"])

                def _draw_pet(cx=cx, cy=cy, pet=pet, hurt=hurt, atk=atk, mine=mine, mov=mov, face=face):
                    sprites.draw_pet(
                        self.screen, pet.get("sprite") or pet["pet_id"], cx, cy, TILE, t,
                        hurt=hurt, attacking=atk, moving=mov, facing=face,
                    )
                    if mine or hurt:
                        ny, hy = self.entity_anchor(cx, cy, "pet")
                        self.blit_nameplate(pet["name"], cx, ny, (180, 220, 255))
                        self.draw_hp_bar(cx, hy, pet["hp"], pet["max_hp"])
                draw_list.append((cy + TILE // 3, 5, _draw_pet))

        # Players
        for p in self.players.values():
            is_self = self.player and p["id"] == self.player["id"]
            if not is_self and self.entity_hidden_by_roof(p["x"], p["y"]):
                continue
            sx, sy = p["x"] - cam_x, p["y"] - cam_y
            if 0 <= sx <= vis_w and 0 <= sy <= vis_h:
                cx, cy = sx * TILE + TILE // 2, sy * TILE + TILE // 2
                if is_self:
                    body, skin, hair = (70, 210, 90), (235, 195, 150), (70, 45, 30)
                    eq = self.player.get("equipment") or {}
                else:
                    body, skin, hair = sprites.palette_for(p["id"])
                    eq = p.get("equipment") or {}
                key = ("p", p["id"])
                mov = moving_for(key, p["x"], p["y"])
                face = facing_for(key, p["x"], p["y"])
                atk = self._attack_progress(p["id"], t)
                now_pos[key] = (p["x"], p["y"])

                def _draw_pl(cx=cx, cy=cy, body=body, skin=skin, hair=hair, eq=eq,
                             mov=mov, face=face, atk=atk, p=p, is_self=is_self):
                    if is_self and time.time() < self.level_up_until:
                        self.draw_level_up_glow(cx, cy, time.time())
                    sprites.draw_humanoid_detailed(
                        self.screen, cx, cy, TILE, body, skin, hair,
                        weapon=weapon_style(eq.get("weapon")),
                        shield=bool(eq.get("shield")),
                        moving=mov, t=t, facing=face,
                        equipment=eq, attacking=atk,
                    )
                    ny, hy = self.entity_anchor(cx, cy, "character")
                    cmb = p.get("combat_level")
                    if is_self:
                        cmb = self.player_combat_level()
                    label = f"{p['name']}  (Lv {cmb})" if cmb else p["name"]
                    self.blit_nameplate(label, cx, ny,
                                        (180, 255, 180) if is_self else WHITE)
                    self.draw_hp_bar(cx, hy, p["hp"], p["max_hp"])
                    if is_self and time.time() < self.level_up_until:
                        self.draw_level_up_banner(cx, ny - 18, time.time())
                draw_list.append((cy + TILE // 2, 6 if is_self else 5, _draw_pl))

        draw_list.sort(key=lambda item: (item[0], item[1]))
        for _, __, fn in draw_list:
            fn()

                # roofs after entities so interiors are covered when you're outside
        self.draw_building_roofs(cam_x, cam_y, vis_w, vis_h)

        self._prev_entity_pos = now_pos

        # floating combat / XP text
        now = time.time()
        self.floaters = [f for f in self.floaters if f["expire"] > now]
        for floater in self.floaters:
            wx, wy = floater["x"], floater["y"]
            sx, sy = wx - cam_x, wy - cam_y
            if 0 <= sx <= vis_w and 0 <= sy <= vis_h:
                age_left = floater["expire"] - now
                lift = int((1.0 - min(1.0, age_left / 1.3)) * 36)
                px = sx * TILE + TILE // 2
                py = sy * TILE - lift - 10
                kind = floater.get("kind")
                if kind in ("hit_red", "hit_green", "hit_blue", "hit_miss"):
                    self.draw_hit_star(px, py, floater["text"], floater["color"], kind=kind)
                elif kind == "level_up":
                    self.draw_level_up_floater(px, py - 18, floater["text"], floater["color"], age_left)
                else:
                    surf = self.font.render(floater["text"], True, floater["color"])
                    self.screen.blit(surf, (px - surf.get_width() // 2, py))

        self.draw_map_vignette()
        pygame.draw.rect(self.screen, ACCENT_DIM, (0, 0, MAP_W, MAP_H), 2)
        zone = wm.get_zone(self.player["x"], self.player["y"])
        # Zone chip
        zone_txt = self.font_small.render(zone.title(), True, WHITE)
        chip_w = zone_txt.get_width() + 16
        chip = pygame.Rect(10, 10, chip_w, 22)
        pygame.draw.rect(self.screen, (28, 26, 36), chip, border_radius=6)
        pygame.draw.rect(self.screen, ACCENT, chip, 1, border_radius=6)
        self.screen.blit(zone_txt, (chip.x + 8, chip.y + 4))

    def player_inside_building(self, b):
        if not self.player:
            return False
        px, py = self.player_xy()
        if (
            b["floor_x0"] <= px <= b["floor_x1"]
            and b["floor_y0"] <= py <= b["floor_y1"]
        ):
            return True
        # Standing on this building's door tile also lifts the roof
        bid = b.get("id")
        for spot in self.interactables:
            if spot.get("kind") == "door" and spot.get("building") == bid:
                if px == spot["x"] and py == spot["y"]:
                    return True
        return False

    def player_inside_any_building(self):
        return any(self.player_inside_building(b) for b in self.buildings)

    def entity_hidden_by_roof(self, x, y):
        """True if (x,y) is under a building roof that is currently drawn."""
        for b in self.buildings:
            if self.player_inside_building(b):
                continue
            if b["x0"] <= x <= b["x1"] and b["y0"] <= y <= b["y1"]:
                return True
        return False

    def building_material_at(self, wx, wy):
        """Wood or brick for a village wall tile belonging to a building."""
        for b in self.buildings:
            if b["x0"] <= wx <= b["x1"] and b["y0"] <= wy <= b["y1"]:
                return b.get("material") or ("brick" if b.get("style", 0) % 2 else "wood")
        return "wood"

    def draw_building_roofs(self, cam_x, cam_y, vis_w, vis_h):
        for b in self.buildings:
            if self.player_inside_building(b):
                continue
            x0, y0, x1, y1 = b["x0"], b["y0"], b["x1"], b["y1"]
            sx0, sy0 = x0 - cam_x, y0 - cam_y
            sx1, sy1 = x1 - cam_x, y1 - cam_y
            if sx1 < 0 or sy1 < 0 or sx0 > vis_w or sy0 > vis_h:
                continue
            rect = pygame.Rect(
                sx0 * TILE, sy0 * TILE,
                (x1 - x0 + 1) * TILE, (y1 - y0 + 1) * TILE,
            )
            sprites.draw_building_roof(
                self.screen, rect, kind=b.get("kind", "house"), style=b.get("style", 0),
                material=b.get("material"),
            )
            # building name on the roof
            name = b.get("name")
            if name:
                label = self.font_small.render(name, True, (255, 230, 180))
                self.screen.blit(
                    label,
                    (rect.centerx - label.get_width() // 2, rect.y + rect.h * 0.22),
                )

    def click_door(self, spot):
        """Walk through a door / dungeon mouth toward the far side."""
        px, py = self.player_xy()
        enter = (spot.get("enter_x", spot["x"]), spot.get("enter_y", spot["y"]))
        exit_ = (spot.get("exit_x", spot["x"]), spot.get("exit_y", spot["y"]))
        # If closer to the entrance side, go inside; otherwise go out
        d_enter = max(abs(px - enter[0]), abs(py - enter[1]))
        d_exit = max(abs(px - exit_[0]), abs(py - exit_[1]))
        target = enter if d_enter >= d_exit else exit_
        if not self.tile_walkable(*target):
            target = enter if self.tile_walkable(*enter) else exit_
        goals = {target}
        if self.tile_walkable(spot["x"], spot["y"]):
            goals.add((spot["x"], spot["y"]))
        self.walk_and_act(goals, None)

    def draw_terrain_tile(self, rect, tile_id, wx, wy, t):
        zone = wm.get_zone(wx, wy) if self.world_w else "wilderness"
        if tile_id in (wm.TREE, wm.OAK_TREE, wm.FISH_SPOT):
            sprites.draw_grass(self.screen, rect, wx, wy)
        elif tile_id in (wm.ORE, wm.IRON_ORE, wm.COAL, wm.MITHRIL_ORE, wm.ADAMANTITE_ORE):
            sprites.draw_floor(self.screen, rect, wx, wy, zone=zone)
        elif tile_id == wm.GRASS:
            sprites.draw_grass(self.screen, rect, wx, wy)
        elif tile_id == wm.PATH:
            sprites.draw_path(self.screen, rect, wx, wy)
        elif tile_id == wm.FLOOR:
            sprites.draw_floor(self.screen, rect, wx, wy, zone=zone)
        elif tile_id == wm.WALL:
            mat = self.building_material_at(wx, wy) if zone == "village" else None
            sprites.draw_wall(self.screen, rect, zone, wx, wy, material=mat)
        elif tile_id == wm.WATER:
            shores = self._water_shores(wx, wy)
            sprites.draw_water_detailed(self.screen, rect, t, wx, wy, shores=shores)
        else:
            sprites.draw_grass(self.screen, rect, wx, wy)

    def _water_shores(self, wx, wy):
        """Land-adjacency flags for shoreline foam on water tiles."""
        def is_land(x, y):
            if not (0 <= y < len(self.tiles) and 0 <= x < self.world_w):
                return True
            return self.tiles[y][x] != wm.WATER
        return {
            "N": is_land(wx, wy - 1),
            "S": is_land(wx, wy + 1),
            "W": is_land(wx - 1, wy),
            "E": is_land(wx + 1, wy),
        }

    def draw_resource_sprite(self, rtype, cx, cy, t, alpha=255):
        if rtype == "tree":
            sprites.draw_tree_detailed(self.screen, cx, cy, TILE, variant=0, t=t, alpha=alpha)
        elif rtype == "oak_tree":
            sprites.draw_tree_detailed(self.screen, cx, cy, TILE, variant=1, t=t, alpha=alpha)
        elif rtype in ROCK_LOOK:
            sprites.draw_rock_detailed(
                self.screen, cx, cy, TILE,
                variant=sum(ord(c) for c in rtype) % 3,
                ore_type=rtype,
            )
        elif rtype.startswith("fishing_spot"):
            sprites.draw_fishing_spot(self.screen, cx, cy, TILE, t)
        else:
            sprites.draw_tree(self.screen, cx, cy, TILE)

    def draw_furniture(self, kind, cx, cy, t, spot=None):
        """Decorative indoor props — visual only, clicks fall through to walk."""
        spot = spot or {}
        drawers = {
            "table": sprites.draw_table,
            "chair": sprites.draw_chair,
            "bed": sprites.draw_bed,
            "chest": sprites.draw_chest,
            "barrel": sprites.draw_barrel,
            "crate": sprites.draw_crate,
            "bookshelf": sprites.draw_bookshelf,
            "shelf": sprites.draw_shelf,
            "counter": sprites.draw_counter,
            "fireplace": sprites.draw_fireplace,
            "range": sprites.draw_fireplace,
            "candle": sprites.draw_candle,
            "rug": sprites.draw_rug,
            "weapon_rack": sprites.draw_weapon_rack,
            "workbench": sprites.draw_workbench,
            "quench_bucket": sprites.draw_quench_bucket,
            "pet_bed": sprites.draw_pet_bed,
            "pet_cage": sprites.draw_pet_cage,
            "stool": sprites.draw_stool,
        }
        fn = drawers.get(kind)
        if fn is None:
            return
        if kind == "chair":
            fn(self.screen, cx, cy, TILE, t, facing=spot.get("facing", 1))
        elif kind == "rug":
            color = spot.get("color") or (140, 50, 50)
            fn(self.screen, cx, cy, TILE, t, color=tuple(color))
        else:
            fn(self.screen, cx, cy, TILE, t)
    def _attack_progress(self, entity_id, now=None):
        """Return 0..1 swing progress while an attack anim is active."""
        expire = self.attack_anims.get(entity_id)
        if not expire:
            return 0.0
        now = now if now is not None else time.time()
        if now >= expire:
            self.attack_anims.pop(entity_id, None)
            return 0.0
        # 0.45s window → progress 0→1
        return max(0.0, min(1.0, 1.0 - (expire - now) / 0.45))

    def draw_hit_star(self, cx, cy, text, color, kind="hit_red"):
        """Polished RS-style hitsplat with soft glow and layered star."""
        # Soft outer glow (compact)
        glow = pygame.Surface((44, 44), pygame.SRCALPHA)
        gcx, gcy = 22, 22
        glow_col = (*color[:3], 50)
        pygame.draw.circle(glow, glow_col, (gcx, gcy), 18)
        pygame.draw.circle(glow, (*color[:3], 85), (gcx, gcy), 13)
        self.screen.blit(glow, (cx - 22, cy - 22))

        outer, inner = 14, 6
        if kind == "hit_miss":
            outer, inner = 13, 5.5
        pts = []
        for i in range(10):
            ang = i * math.pi / 5 - math.pi / 2
            r = outer if i % 2 == 0 else inner
            pts.append((cx + math.cos(ang) * r, cy + math.sin(ang) * r))
        # dark underlay for contrast
        under = []
        for i in range(10):
            ang = i * math.pi / 5 - math.pi / 2
            r = (outer + 2.2) if i % 2 == 0 else (inner + 1.5)
            under.append((cx + math.cos(ang) * r, cy + math.sin(ang) * r))
        pygame.draw.polygon(self.screen, (18, 14, 12), under)
        # main star fill
        pygame.draw.polygon(self.screen, color, pts)
        # bright highlight facet (upper points)
        hi = tuple(min(255, c + 70) for c in color)
        hi_pts = [
            (cx, cy - outer * 0.85),
            (cx + inner * 0.55, cy - inner * 0.15),
            (cx, cy),
            (cx - inner * 0.55, cy - inner * 0.15),
        ]
        pygame.draw.polygon(self.screen, hi, hi_pts)
        # rim
        pygame.draw.polygon(self.screen, (255, 255, 255), pts, 1)
        # creamy center disc
        pygame.draw.circle(self.screen, (255, 252, 240), (cx, cy), 6)
        pygame.draw.circle(self.screen, color, (cx, cy), 6, 1)
        pygame.draw.circle(self.screen, (255, 255, 255), (cx - 2, cy - 2), 1)

        label = str(text)
        font = self.font if len(label) <= 3 else self.font_small
        ink = (25, 22, 20) if kind != "hit_miss" else (25, 45, 90)
        for ox, oy in ((-1, 0), (1, 0), (0, -1), (0, 1)):
            shadow = font.render(label, True, (255, 255, 255))
            self.screen.blit(shadow, (cx - shadow.get_width() // 2 + ox,
                                      cy - shadow.get_height() // 2 + oy))
        surf = font.render(label, True, ink)
        self.screen.blit(surf, (cx - surf.get_width() // 2, cy - surf.get_height() // 2))

    def entity_anchor(self, cx, cy, kind="character"):
        """Return (nameplate_y, hp_y) with the HP bar just above the head."""
        try:
            import rs_style as _rs
            lift = _rs.label_lift(TILE, kind)
        except Exception:
            lift = int(TILE * 1.55)
        hp_y = cy - lift
        # Nameplate sits above the HP bar
        name_y = hp_y - 16
        return name_y, hp_y

    def blit_label(self, text, cx, top_y):
        self.blit_nameplate(text, cx, top_y)

    def blit_nameplate(self, text, cx, top_y, color=WHITE):
        """Readable name tag with soft backdrop."""
        surf = self.font_label.render(str(text), True, color)
        pad_x, pad_y = 6, 3
        box = pygame.Rect(
            cx - surf.get_width() // 2 - pad_x,
            top_y - 10 - pad_y,
            surf.get_width() + pad_x * 2,
            surf.get_height() + pad_y * 2,
        )
        pygame.draw.rect(self.screen, (12, 12, 16), box, border_radius=5)
        pygame.draw.rect(self.screen, (70, 65, 55), box, 1, border_radius=5)
        self.screen.blit(surf, (box.x + pad_x, box.y + pad_y))

    def monster_threat_color(self, mon_level):
        """Green = easier, orange = a bit tougher, red = dangerous."""
        pc = self.player_combat_level() if self.player else 1
        diff = int(mon_level) - int(pc)
        if diff <= 0:
            return (86, 196, 110)      # at or below you
        if diff <= 5:
            return (255, 160, 55)      # a little above
        return (230, 70, 70)           # too high

    def blit_combat_level(self, level, cx, top_y, color):
        """Compact combat-level badge above a monster."""
        surf = self.font_small.render(str(int(level)), True, color)
        pad_x, pad_y = 5, 2
        box = pygame.Rect(
            cx - surf.get_width() // 2 - pad_x,
            top_y - 8 - pad_y,
            surf.get_width() + pad_x * 2,
            surf.get_height() + pad_y * 2,
        )
        pygame.draw.rect(self.screen, (12, 12, 16), box, border_radius=4)
        pygame.draw.rect(self.screen, color, box, 1, border_radius=4)
        self.screen.blit(surf, (box.x + pad_x, box.y + pad_y))

    def draw_hp_bar(self, cx, y, hp, max_hp):
        # Classic RS-style: green remaining + red missing, small bar above head
        w, h = 28, 4
        pct = max(0.0, min(1.0, max(0, hp) / max(1, max_hp)))
        x0 = cx - w // 2
        pygame.draw.rect(self.screen, (0, 0, 0), (x0 - 1, y - 1, w + 2, h + 2))
        pygame.draw.rect(self.screen, (200, 20, 20), (x0, y, w, h))
        if pct > 0:
            pygame.draw.rect(self.screen, (20, 200, 20), (x0, y, max(1, int(w * pct)), h))

    def draw_map_vignette(self):
        """Soft edge darkening so the map reads as a framed playfield."""
        if not hasattr(self, "_vignette") or self._vignette.get_size() != (MAP_W, MAP_H):
            v = pygame.Surface((MAP_W, MAP_H), pygame.SRCALPHA)
            for i in range(48):
                a = int(70 * (1 - i / 48))
                pygame.draw.rect(v, (0, 0, 0, a), (i, i, MAP_W - 2 * i, MAP_H - 2 * i), 1)
            self._vignette = v
        self.screen.blit(self._vignette, (0, 0))

    # -- sidebar: stats + inventory + quests ------------------------------
    def _sidebar_section(self, title, y):
        self.screen.blit(self.font_small.render(title, True, ACCENT), (SIDEBAR_X + 16, y))
        pygame.draw.line(
            self.screen, PANEL_LINE,
            (SIDEBAR_X + 16, y + 16), (SCREEN_W - 16, y + 16), 1,
        )
        return y + 22

    def draw_sidebar(self):
        # Panel background + left accent rail
        pygame.draw.rect(self.screen, PANEL_BG, (SIDEBAR_X, 0, SCREEN_W - SIDEBAR_X, SCREEN_H))
        pygame.draw.rect(self.screen, PANEL_BG_2, (SIDEBAR_X, 0, 4, SCREEN_H))
        pygame.draw.line(self.screen, ACCENT_DIM, (SIDEBAR_X, 0), (SIDEBAR_X, SCREEN_H), 2)

        y = 10
        name = self.font_big.render(self.player["name"], True, WHITE)
        self.screen.blit(name, (SIDEBAR_X + 14, y))
        y += 30

        # Coins chip
        coins_txt = self.font.render(f"{self.player['coins']:,} coins", True, YELLOW)
        chip = pygame.Rect(SIDEBAR_X + 14, y, coins_txt.get_width() + 14, 22)
        pygame.draw.rect(self.screen, (40, 34, 18), chip, border_radius=6)
        pygame.draw.rect(self.screen, ACCENT_DIM, chip, 1, border_radius=6)
        self.screen.blit(coins_txt, (chip.x + 7, chip.y + 3))
        y += 28

        pet = self.player.get("pet")
        owned = self.player.get("owned_pets") or []
        self.pets_btn_rect = None
        if pet or owned:
            label = f"Pet · {pet['name']}  Lv{pet.get('level', 1)}" if pet else "Pets"
            if len(owned) > 1:
                label += f"  ({len(owned)} owned)  click to switch"
            elif pet:
                label += f"  {pet['hp']}/{pet['max_hp']}"
            btn = pygame.Rect(SIDEBAR_X + 14, y, SCREEN_W - SIDEBAR_X - 28, 22)
            self.pets_btn_rect = btn
            active = self.show_pets
            pygame.draw.rect(self.screen, (36, 52, 72) if active else (28, 36, 48), btn, border_radius=5)
            pygame.draw.rect(self.screen, (120, 180, 230) if active else (70, 100, 130), btn, 1, border_radius=5)
            pet_line = self.font_tiny.render(label, True, (170, 210, 245))
            self.screen.blit(pet_line, (btn.x + 8, btn.y + 4))
        else:
            tip = self.font_tiny.render("No pet — Pet Emporium (Luna)", True, GREY)
            self.screen.blit(tip, (SIDEBAR_X + 14, y))
        y += 26

        bank_coins = int(self.player.get("bank_coins") or 0)
        cap_txt = self.font_tiny.render(f"Bank {bank_coins:,}c", True, (160, 155, 130))
        self.screen.blit(cap_txt, (SIDEBAR_X + 14, y))
        y += 18

        auto = bool(self.player.get("auto_pickup_items"))
        btn = pygame.Rect(SIDEBAR_X + 14, y, SCREEN_W - SIDEBAR_X - 28, 26)
        self.auto_pickup_btn_rect = btn
        bg = (36, 78, 48) if auto else (62, 40, 38)
        border = GREEN if auto else (170, 90, 70)
        pygame.draw.rect(self.screen, bg, btn, border_radius=6)
        pygame.draw.rect(self.screen, border, btn, 1, border_radius=6)
        auto_label = f"Auto-pickup  {'ON' if auto else 'OFF'}   (P)"
        auto_txt = self.font_small.render(auto_label, True, WHITE)
        self.screen.blit(auto_txt, (btn.x + 10, btn.y + 5))
        y += 34

        # HP bar
        y = self._sidebar_section("Vitality", y)
        max_hp = max(1, int(self.player["max_hp"]))
        hp = int(self.player["hp"])
        pct = hp / max_hp
        bar = pygame.Rect(SIDEBAR_X + 14, y, SCREEN_W - SIDEBAR_X - 28, 16)
        pygame.draw.rect(self.screen, (40, 28, 28), bar, border_radius=4)
        fill_c = (70, 190, 95) if pct > 0.55 else ((220, 170, 50) if pct > 0.25 else (210, 60, 55))
        if pct > 0:
            fill = pygame.Rect(bar.x, bar.y, max(2, int(bar.w * pct)), bar.h)
            pygame.draw.rect(self.screen, fill_c, fill, border_radius=4)
        pygame.draw.rect(self.screen, PANEL_LINE, bar, 1, border_radius=4)
        hp_lbl = self.font_tiny.render(f"{hp} / {max_hp}", True, WHITE)
        self.screen.blit(hp_lbl, (bar.centerx - hp_lbl.get_width() // 2, bar.y + 2))
        y += 24

        # Skills button — opens full skills modal
        y = self._sidebar_section("Skills", y)
        cmb = self.player_combat_level()
        tot = self.player_total_level()
        btn = pygame.Rect(SIDEBAR_X + 14, y, SCREEN_W - SIDEBAR_X - 28, 36)
        self.skills_btn_rect = btn
        bg = (42, 58, 78) if self.show_skills else (32, 40, 54)
        border = (120, 180, 255) if self.show_skills else (90, 130, 190)
        pygame.draw.rect(self.screen, bg, btn, border_radius=6)
        pygame.draw.rect(self.screen, border, btn, 1, border_radius=6)
        skills_label = self.font_small.render("Open Skills  (Tab)", True, WHITE)
        self.screen.blit(skills_label, (btn.x + 10, btn.y + 4))
        summary = self.font_tiny.render(f"Combat {cmb}   ·   Total {tot}", True, (180, 200, 230))
        self.screen.blit(summary, (btn.x + 10, btn.y + 20))
        y += 44
        tip = self.font_tiny.render("E gear  F forge  C cook  B bank  H help", True, (140, 138, 120))
        self.screen.blit(tip, (SIDEBAR_X + 14, y))
        y += 18

        # Combat style
        y = self._sidebar_section("Combat XP →", y)
        self._combat_style_oy = y
        current = self.combat_style or (self.player.get("combat_style") if self.player else "attack") or "attack"
        self.combat_style_rects = []
        for rect, style, label in self.combat_style_button_rects():
            selected = style == current
            bg = (42, 78, 50) if selected else (36, 38, 50)
            border = GREEN if selected else PANEL_LINE
            pygame.draw.rect(self.screen, bg, rect, border_radius=5)
            pygame.draw.rect(self.screen, border, rect, 1, border_radius=5)
            txt = self.font_small.render(label, True, WHITE if selected else GREY)
            self.screen.blit(txt, (rect.x + (rect.w - txt.get_width()) // 2,
                                   rect.y + (rect.h - txt.get_height()) // 2))
            self.combat_style_rects.append((rect, style))

        inv_y = y + 64
        inv_y = self._sidebar_section("Inventory", inv_y)
        hint = self.font_tiny.render("Hover for name · click use · right bury/drop", True, (140, 138, 120))
        self.screen.blit(hint, (SIDEBAR_X + 14, inv_y - 2))
        self._inventory_oy = inv_y + 14

        hover_entry = None
        hover_rect = None
        for slot, rect in self.inventory_slot_rects().items():
            entry = self.player["inventory"].get(str(slot)) or self.player["inventory"].get(slot)
            hovered = slot == self.inv_hover_slot
            bg = (48, 52, 66) if entry else (32, 34, 44)
            if hovered:
                bg = (62, 78, 48)
            pygame.draw.rect(self.screen, bg, rect, border_radius=5)
            border = ACCENT if hovered else (PANEL_LINE if not entry else (78, 82, 98))
            pygame.draw.rect(self.screen, border, rect, 2 if hovered else 1, border_radius=5)
            if entry:
                sprites.draw_item_icon(self.screen, rect.inflate(-8, -8), entry["item_id"], ITEMS)
                if entry["qty"] > 1:
                    qty = self.font_tiny.render(str(entry["qty"]), True, YELLOW)
                    for ox, oy in ((-1, 0), (1, 0), (0, -1), (0, 1)):
                        shadow = self.font_tiny.render(str(entry["qty"]), True, (0, 0, 0))
                        self.screen.blit(shadow, (rect.x + 3 + ox, rect.y + 2 + oy))
                    self.screen.blit(qty, (rect.x + 3, rect.y + 2))
                if hovered:
                    hover_entry = entry
                    hover_rect = rect

        if hover_entry and hover_rect:
            self.draw_inventory_tooltip(hover_entry, hover_rect)

        # Quests
        qy = SCREEN_H - 186
        q_label = self.font_small.render(
            "Quests (Q)" if not self.show_quests else "Quests", True, ACCENT)
        self.screen.blit(q_label, (SIDEBAR_X + 14, qy))
        if self.show_quests:
            qy += 18
            for qid, info in self.quests.items():
                color = {"not_started": GREY, "active": WHITE, "ready": YELLOW, "complete": GREEN}[info["status"]]
                txt = self.font_tiny.render(
                    f"{qid.replace('_', ' ').title()}: {info['status']}", True, color)
                self.screen.blit(txt, (SIDEBAR_X + 14, qy))
                qy += 14

        # Logout — above the control hint strip
        logout = pygame.Rect(SIDEBAR_X + 14, SCREEN_H - 52, SCREEN_W - SIDEBAR_X - 28, 28)
        self.logout_btn_rect = logout
        pygame.draw.rect(self.screen, (72, 36, 36), logout, border_radius=6)
        pygame.draw.rect(self.screen, (190, 90, 80), logout, 1, border_radius=6)
        lo_txt = self.font_small.render("Logout", True, WHITE)
        self.screen.blit(lo_txt, (logout.centerx - lo_txt.get_width() // 2, logout.y + 6))

        controls = self.font_tiny.render(
            "←↑→↓ move   Space attack   B bank   P loot   H help", True, GREY)
        self.screen.blit(controls, (SIDEBAR_X + 10, SCREEN_H - 16))

    def draw_inventory_tooltip(self, entry, slot_rect):
        """Hover card: full item name, qty, and combat bonuses."""
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
        if item.get("heal"):
            bits.append(f"Heals {item['heal']}")
        if item.get("karma_xp"):
            bits.append(f"Bury: +{item['karma_xp']} Karma XP")
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

    def add_chat(self, text, color=None, highlight=False):
        """Append a chat line; optional color and gold highlight bar."""
        self.chat_log.append({
            "text": text,
            "color": color or WHITE,
            "highlight": highlight,
        })
        self.chat_log = self.chat_log[-12:]

    def draw_level_up_glow(self, cx, cy, now):
        """Soft pulsing gold aura around the player for a few seconds."""
        remaining = max(0.0, self.level_up_until - now)
        fade = min(1.0, remaining / 0.6)  # fade out near the end
        pulse = 0.55 + 0.45 * abs(math.sin(now * 7))
        size = int(70 + 18 * pulse)
        glow = pygame.Surface((size * 2, size * 2), pygame.SRCALPHA)
        for i, alpha in ((0, int(35 * fade)), (1, int(70 * fade * pulse)), (2, int(110 * fade))):
            r = size - i * 10
            if r <= 0:
                continue
            pygame.draw.circle(glow, (255, 210, 60, alpha), (size, size), r)
        # bright core ring
        pygame.draw.circle(glow, (255, 240, 140, int(160 * fade * pulse)), (size, size), max(8, size // 4), 3)
        self.screen.blit(glow, (cx - size, cy - size + 4))

    def draw_level_up_banner(self, cx, top_y, now):
        """Persistent gold skill label while the glow lasts."""
        if not self.level_up_label:
            return
        remaining = max(0.0, self.level_up_until - now)
        fade = min(1.0, remaining / 0.5)
        bob = int(math.sin(now * 6) * 3)
        text = self.level_up_label
        font = self.font
        # outlined gold text
        for ox, oy in ((-1, 0), (1, 0), (0, -1), (0, 1), (-1, -1), (1, 1)):
            shadow = font.render(text, True, (80, 50, 10))
            self.screen.blit(shadow, (cx - shadow.get_width() // 2 + ox, top_y + bob + oy))
        gold = (255, int(215 * fade + 40 * (1 - fade)), int(60 * fade))
        surf = font.render(text, True, gold)
        self.screen.blit(surf, (cx - surf.get_width() // 2, top_y + bob))

    def draw_level_up_floater(self, cx, cy, text, color, age_left):
        """Big gold 'Level Up!' rising above the head."""
        font = self.font_big
        for ox, oy in ((-2, 0), (2, 0), (0, -2), (0, 2)):
            shadow = font.render(text, True, (60, 40, 5))
            self.screen.blit(shadow, (cx - shadow.get_width() // 2 + ox, cy + oy))
        surf = font.render(text, True, color)
        self.screen.blit(surf, (cx - surf.get_width() // 2, cy))
        # sparkle dots
        for i in range(4):
            ang = time.time() * 5 + i * 1.7
            sx = cx + int(math.cos(ang) * (18 + i * 3))
            sy = cy + int(math.sin(ang * 1.3) * 8)
            pygame.draw.circle(self.screen, (255, 245, 160), (sx, sy), 2)

    # -- chat ---------------------------------------------------------------
    def draw_chat(self):
        box = pygame.Rect(0, MAP_H, MAP_W, SCREEN_H - MAP_H)
        pygame.draw.rect(self.screen, PANEL_BG, box)
        pygame.draw.line(self.screen, ACCENT_DIM, (0, MAP_H), (MAP_W, MAP_H), 2)
        y = MAP_H + 8
        for line in self.chat_log[-6:]:
            if isinstance(line, dict):
                text = line.get("text", "")
                color = line.get("color") or WHITE
                highlight = bool(line.get("highlight"))
            else:
                text, color, highlight = line, WHITE, False
            if highlight:
                bar = pygame.Rect(6, y - 1, MAP_W - 16, 16)
                pygame.draw.rect(self.screen, (55, 44, 18), bar, border_radius=4)
                pygame.draw.rect(self.screen, ACCENT, bar, 1, border_radius=4)
            surf = self.font_small.render(str(text)[:110], True, color)
            self.screen.blit(surf, (10, y))
            y += 17
        input_rect = pygame.Rect(6, SCREEN_H - 28, MAP_W - 12, 22)
        pygame.draw.rect(self.screen, (36, 38, 50), input_rect, border_radius=5)
        pygame.draw.rect(
            self.screen,
            ACCENT if self.chat_typing else PANEL_LINE,
            input_rect, 1, border_radius=5,
        )
        prompt = ("> " + self.chat_text) if self.chat_typing else "Press Enter to chat"
        surf = self.font_small.render(prompt, True, WHITE if self.chat_typing else GREY)
        self.screen.blit(surf, (input_rect.x + 8, input_rect.y + 4))

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
            self.screen.blit(self.font_small.render("Press B to open shop (buy & sell)", True, (255, 210, 120)),
                              (box.x + 12, box.y + box.h - 40))
        if self.dialogue.get("bank"):
            self.screen.blit(self.font_small.render("Press B to open your bank", True, (180, 220, 255)),
                              (box.x + 12, box.y + box.h - 40))
        if self.dialogue.get("forge"):
            self.screen.blit(self.font_small.render("Press S to use the nearest furnace or anvil", True, (255, 180, 100)),
                              (box.x + 12, box.y + box.h - 58))
        self.screen.blit(self.font_small.render("Esc to close", True, GREY), (box.x + 12, box.y + box.h - 20))

    def draw_shop(self):
        """Centered buy/sell modal — stock on the left, your items to sell on the right."""
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

        # --- Buy column ---
        self.screen.blit(self.font.render("Buy", True, GREEN), (box.x + 18, box.y + 72))
        self.screen.blit(self.font_small.render("Click an item to buy 1", True, GREY), (box.x + 60, box.y + 76))
        self.shop_buy_rects = []
        y = box.y + 100
        for item_id, info in self.shop["stock"].items():
            row = pygame.Rect(box.x + 14, y, mid_x - box.x - 28, 36)
            pygame.draw.rect(self.screen, (32, 36, 48), row, border_radius=4)
            pygame.draw.rect(self.screen, (70, 80, 100), row, 1, border_radius=4)
            icon = pygame.Rect(row.x + 6, row.y + 4, 28, 28)
            sprites.draw_item_icon(self.screen, icon, item_id, ITEMS)
            name = self.font_small.render(info["name"], True, WHITE)
            self.screen.blit(name, (row.x + 42, row.y + 4))
            meta = self.font_small.render(f"{info['price']}c   stock {info['qty']}", True, (180, 200, 140))
            self.screen.blit(meta, (row.x + 42, row.y + 18))
            self.shop_buy_rects.append((row, item_id))
            y += 40
            if y > box.bottom - 50:
                break

        # --- Sell column ---
        self.screen.blit(self.font.render("Sell", True, (255, 170, 90)), (mid_x + 14, box.y + 72))
        if self.shop.get("buys", True):
            self.screen.blit(
                self.font_small.render("Click an item to sell 1 (40% value)", True, GREY),
                (mid_x + 70, box.y + 76),
            )
        else:
            self.screen.blit(self.font_small.render("This shop does not buy items", True, GREY),
                             (mid_x + 14, box.y + 100))

        self.shop_sell_rects = []
        y = box.y + 100
        if self.shop.get("buys", True) and self.player:
            inv = self.player.get("inventory") or {}
            # Stable order by slot index
            slots = []
            for k, entry in inv.items():
                try:
                    slots.append((int(k), entry))
                except (TypeError, ValueError):
                    continue
            slots.sort(key=lambda t: t[0])
            shown = 0
            for slot, entry in slots:
                if not entry:
                    continue
                item_id = entry["item_id"]
                if item_id == "coins":
                    continue
                price = self.sell_price(item_id)
                row = pygame.Rect(mid_x + 12, y, box.right - mid_x - 26, 36)
                pygame.draw.rect(self.screen, (40, 34, 28), row, border_radius=4)
                pygame.draw.rect(self.screen, (120, 90, 50), row, 1, border_radius=4)
                icon = pygame.Rect(row.x + 6, row.y + 4, 28, 28)
                sprites.draw_item_icon(self.screen, icon, item_id, ITEMS)
                label = ITEMS.get(item_id, {}).get("name", item_id)
                qty = entry.get("qty", 1)
                name = self.font_small.render(f"{label}  x{qty}", True, WHITE)
                self.screen.blit(name, (row.x + 42, row.y + 4))
                meta = self.font_small.render(f"sell {price}c each", True, (255, 200, 120))
                self.screen.blit(meta, (row.x + 42, row.y + 18))
                self.shop_sell_rects.append((row, slot, item_id))
                y += 40
                shown += 1
                if y > box.bottom - 50:
                    break
            if shown == 0:
                self.screen.blit(
                    self.font_small.render("Nothing to sell in your inventory.", True, GREY),
                    (mid_x + 14, box.y + 110),
                )

        hint = self.font_small.render("Esc or click X / outside to close", True, GREY)
        self.screen.blit(hint, (box.x + 18, box.bottom - 26))

    def draw_bank(self):
        """Bank vault: deposit/withdraw items and coins — scrollable inv + paged vault grid."""
        box = pygame.Rect(120, 50, 780, 560)
        pygame.draw.rect(self.screen, (16, 20, 30), box)
        pygame.draw.rect(self.screen, (120, 190, 255), box, 2)

        title = self.font_big.render("Village Bank", True, WHITE)
        self.screen.blit(title, (box.x + 18, box.y + 10))

        purse = int(self.bank.get("coins", self.player.get("coins", 0) if self.player else 0))
        vault = int(self.bank.get("bank_coins", 0))
        max_purse = int(self.bank.get("max_purse", 65000))
        max_vault = int(self.bank.get("max_bank_coins", 10_000_000))
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
        self.bank_btn_rects["dep_all"] = pygame.Rect(box.x + 18, box.y + 72, 150, 28)
        self.bank_btn_rects["dep_1k"] = pygame.Rect(box.x + 178, box.y + 72, 110, 28)
        self.bank_btn_rects["wd_all"] = pygame.Rect(box.x + 420, box.y + 72, 150, 28)
        self.bank_btn_rects["wd_1k"] = pygame.Rect(box.x + 580, box.y + 72, 110, 28)
        for key, label in (
            ("dep_all", "Deposit all coins"),
            ("dep_1k", "Deposit 1k"),
            ("wd_all", "Withdraw to cap"),
            ("wd_1k", "Withdraw 1k"),
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
        self.screen.blit(self.font_small.render("Scroll / ↑↓", True, GREY), (box.x + 160, box.y + 116))
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
            f"Page {self.bank_page + 1}/{max_page + 1}  ·  click / wheel / ←→",
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

    def handle_bank_click(self, mx, my, button):
        box = pygame.Rect(120, 50, 780, 560)
        if self.bank_btn_rects.get("close") and self.bank_btn_rects["close"].collidepoint(mx, my):
            self.show_bank = False
            return
        if not box.collidepoint(mx, my):
            self.show_bank = False
            return
        if not self.bank:
            return
        purse = int(self.bank.get("coins", 0))
        vault = int(self.bank.get("bank_coins", 0))
        max_purse = int(self.bank.get("max_purse", 65000))
        slots_n = int(self.bank.get("bank_slots", 96))
        page_size = max(1, int(self.bank_page_size))
        max_page = max(0, (slots_n - 1) // page_size)

        if self.bank_btn_rects.get("page_prev") and self.bank_btn_rects["page_prev"].collidepoint(mx, my):
            self.bank_page = max(0, self.bank_page - 1)
            return
        if self.bank_btn_rects.get("page_next") and self.bank_btn_rects["page_next"].collidepoint(mx, my):
            self.bank_page = min(max_page, self.bank_page + 1)
            return
        if self.bank_btn_rects.get("inv_up") and self.bank_btn_rects["inv_up"].collidepoint(mx, my):
            self.bank_inv_scroll = max(0, self.bank_inv_scroll - 1)
            return
        if self.bank_btn_rects.get("inv_down") and self.bank_btn_rects["inv_down"].collidepoint(mx, my):
            self.bank_inv_scroll += 1
            return

        if self.bank_btn_rects.get("dep_all") and self.bank_btn_rects["dep_all"].collidepoint(mx, my):
            if purse > 0:
                self.net.send("BANK_DEPOSIT", coins=purse)
            return
        if self.bank_btn_rects.get("dep_1k") and self.bank_btn_rects["dep_1k"].collidepoint(mx, my):
            qty = min(1000, purse)
            if qty > 0:
                self.net.send("BANK_DEPOSIT", coins=qty)
            return
        if self.bank_btn_rects.get("wd_all") and self.bank_btn_rects["wd_all"].collidepoint(mx, my):
            room = max(0, max_purse - purse)
            qty = min(room, vault)
            if qty > 0:
                self.net.send("BANK_WITHDRAW", coins=qty)
            return
        if self.bank_btn_rects.get("wd_1k") and self.bank_btn_rects["wd_1k"].collidepoint(mx, my):
            room = max(0, max_purse - purse)
            qty = min(1000, room, vault)
            if qty > 0:
                self.net.send("BANK_WITHDRAW", coins=qty)
            return
        for rect, slot in self.bank_inv_rects:
            if rect.collidepoint(mx, my):
                self.net.send("BANK_DEPOSIT", slot_index=slot)
                return
        for rect, slot in self.bank_slot_rects:
            if rect.collidepoint(mx, my):
                entry = (self.bank.get("bank") or {}).get(str(slot)) or (self.bank.get("bank") or {}).get(slot)
                if entry:
                    self.net.send("BANK_WITHDRAW", slot_index=slot)
                return

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

    def draw_equipment_modal(self):
        box = pygame.Rect(180, 50, 480, 520)
        pygame.draw.rect(self.screen, (18, 20, 28), box)
        pygame.draw.rect(self.screen, YELLOW, box, 2)
        title = self.font_big.render("Equipment & Stats", True, WHITE)
        self.screen.blit(title, (box.x + 16, box.y + 12))

        eq = self.player.get("equipment") or {}
        karma_lvl = (self.player.get("levels") or {}).get("karma", 1)
        bonuses = {"att_bonus": 0, "str_bonus": 0, "def_bonus": 0}
        y = box.y + 48
        self.equip_slot_rects = {}
        for slot in ("helmet", "weapon", "shield", "body", "legs"):
            item_id = eq.get(slot)
            item = ITEMS.get(item_id) if item_id else None
            name = item["name"] if item else "(empty)"
            row = pygame.Rect(box.x + 20, y, 440, 44)
            pygame.draw.rect(self.screen, (40, 42, 52), row)
            pygame.draw.rect(self.screen, PANEL_LINE, row, 1)
            self.equip_slot_rects[slot] = row
            icon = pygame.Rect(row.x + 8, row.y + 6, 32, 32)
            pygame.draw.rect(self.screen, (30, 30, 38), icon)
            kb = karma_slot_bonus(slot, karma_lvl) if item_id else {"att_bonus": 0, "str_bonus": 0, "def_bonus": 0}
            if item_id:
                sprites.draw_item_icon(self.screen, icon, item_id, ITEMS)
                for k in bonuses:
                    bonuses[k] += item.get(k, 0) + kb.get(k, 0)
            label = self.font.render(f"{slot.title()}: {name}", True, WHITE)
            self.screen.blit(label, (row.x + 50, row.y + 6))
            if item:
                detail = self.font_small.render(
                    f"Att +{item.get('att_bonus', 0)}(+{kb['att_bonus']}k)  "
                    f"Str +{item.get('str_bonus', 0)}(+{kb['str_bonus']}k)  "
                    f"Def +{item.get('def_bonus', 0)}(+{kb['def_bonus']}k)",
                    True, GREY)
                self.screen.blit(detail, (row.x + 50, row.y + 24))
            y += 50

        y += 6
        levels = self.player.get("levels") or {}
        wb = self.player.get("gear_bonuses") or bonuses
        kb = self.player.get("karma_bonuses") or {"att_bonus": 0, "str_bonus": 0, "def_bonus": 0}
        stats = [
            f"Attack {levels.get('attack', 1)}  (+{wb.get('att_bonus', 0)} gear)",
            f"Strength {levels.get('strength', 1)}  (+{wb.get('str_bonus', 0)} gear)",
            f"Defence {levels.get('defence', 1)}  (+{wb.get('def_bonus', 0)} gear)",
            f"Hitpoints {self.player['hp']} / {self.player['max_hp']}",
            f"Karma {levels.get('karma', 1)}  (gear +{kb.get('att_bonus', 0)}a/{kb.get('str_bonus', 0)}s/{kb.get('def_bonus', 0)}d)",
            f"Smithing {levels.get('smithing', 1)}",
            f"Cooking {levels.get('cooking', 1)}",
            f"Firemaking {levels.get('firemaking', 1)}",
            f"Combat {self.player_combat_level()}  ·  Total {self.player_total_level()}",
        ]
        self.screen.blit(self.font.render("Combat summary", True, YELLOW), (box.x + 20, y))
        y += 24
        for line in stats:
            self.screen.blit(self.font_small.render(line, True, WHITE), (box.x + 24, y))
            y += 16

        self.screen.blit(
            self.font_small.render("Right-click bones to bury one. Esc / E to close", True, GREY),
            (box.x + 20, box.y + box.h - 28),
        )

    def handle_equipment_click(self, mx, my):
        for slot, rect in getattr(self, "equip_slot_rects", {}).items():
            if rect.collidepoint(mx, my) and (self.player.get("equipment") or {}).get(slot):
                self.net.send("UNEQUIP", equip_slot=slot)
                return
        # click outside closes
        box = pygame.Rect(180, 50, 480, 520)
        if not box.collidepoint(mx, my):
            self.show_equipment = False

    def draw_forge_modal(self):
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
        y = y_filter2 + 40
        shown = 0
        for rid, recipe in self.craft_recipes.items():
            if recipe.get("category") != self.forge_tab:
                continue
            if not self._forge_recipe_matches(rid, recipe):
                continue
            row = pygame.Rect(box.x + 20, y, 580, 44)
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
            y += 48
            shown += 1
            if y > box.bottom - 44:
                break

        if shown == 0:
            self.screen.blit(
                self.font.render("No recipes match these filters.", True, GREY),
                (box.x + 20, y_filter2 + 50),
            )

        tip = (
            "Furnace: smelt only · Esc / F closes"
            if self.forge_station == "furnace"
            else "Anvil: smith weapons & armour · Esc / F closes"
            if self.forge_station == "anvil"
            else "Click furnace or anvil · Esc / F closes"
        )
        self.screen.blit(
            self.font_small.render(tip, True, GREY),
            (box.x + 20, box.y + box.h - 26),
        )

    def _forge_recipe_metal(self, rid, recipe):
        blob = f"{rid} {recipe.get('name', '')} {recipe.get('output', ('',))[0]}".lower()
        for metal in ("adamant", "mithril", "steel", "iron", "bronze"):
            if metal in blob:
                return metal
        return "other"

    def _forge_recipe_gear(self, rid, recipe):
        if recipe.get("category") == "smelt":
            return "bar"
        out = str(recipe.get("output", ("",))[0]).lower()
        name = str(recipe.get("name", "")).lower()
        blob = f"{rid} {out} {name}"
        if any(k in blob for k in ("dagger", "sword", "battleaxe", "axe", "scimitar", "cleaver")):
            return "weapon"
        if "shield" in blob:
            return "shield"
        if "helmet" in blob or "cowl" in blob or "helm" in blob:
            return "helmet"
        if any(k in blob for k in ("chainbody", "platebody", "_body", "body")):
            return "body"
        if any(k in blob for k in ("chainlegs", "platelegs", "_legs", "legs")):
            return "legs"
        if "bar" in blob:
            return "bar"
        return "other"

    def _forge_recipe_matches(self, rid, recipe):
        if self.forge_metal != "all" and self._forge_recipe_metal(rid, recipe) != self.forge_metal:
            return False
        if self.forge_gear != "all" and self._forge_recipe_gear(rid, recipe) != self.forge_gear:
            return False
        return True

    def handle_forge_click(self, mx, my):
        for key, rect in getattr(self, "forge_tab_rects", {}).items():
            if rect.collidepoint(mx, my):
                # Only when unlocked (no station lock)
                if self.forge_station is not None:
                    return
                self.forge_tab = key
                if key == "smelt":
                    self.forge_gear = "bar" if self.forge_gear not in ("all", "bar") else self.forge_gear
                elif self.forge_gear == "bar":
                    self.forge_gear = "all"
                return
        for (ftype, key), rect in getattr(self, "forge_filter_rects", {}).items():
            if rect.collidepoint(mx, my):
                if ftype == "metal":
                    self.forge_metal = key
                else:
                    self.forge_gear = key
                return
        for rect, rid in self.forge_recipe_rects:
            if rect.collidepoint(mx, my):
                self.net.send("CRAFT", recipe_id=rid)
                return
        box = pygame.Rect(100, 40, 620, 560)
        if not box.collidepoint(mx, my):
            self.show_forge = False

    def draw_cook_modal(self):
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
            self.font_small.render("Click a recipe to cook · Esc / C closes · Left-click cooked food to eat", True, GREY),
            (box.x + 16, box.y + box.h - 28),
        )

    def handle_cook_click(self, mx, my):
        for rect, rid in getattr(self, "cook_recipe_rects", []):
            if rect.collidepoint(mx, my):
                self.net.send("CRAFT", recipe_id=rid)
                return
        box = pygame.Rect(220, 80, 520, 420)
        if not box.collidepoint(mx, my):
            self.show_cook = False

    def draw_skills_modal(self):
        box = pygame.Rect(160, 40, 640, 620)
        pygame.draw.rect(self.screen, (16, 20, 28), box)
        pygame.draw.rect(self.screen, (120, 180, 255), box, 2)
        title = self.font_big.render("Skills", True, WHITE)
        self.screen.blit(title, (box.x + 20, box.y + 14))

        cmb = self.player_combat_level()
        tot = self.player_total_level()
        header = self.font.render(
            f"Combat level {cmb}    ·    Total level {tot}",
            True, YELLOW,
        )
        self.screen.blit(header, (box.x + 20, box.y + 48))
        hint = self.font_tiny.render(
            "Combat from Attack, Strength, Defence & Hitpoints  ·  Esc / Tab closes",
            True, GREY,
        )
        self.screen.blit(hint, (box.x + 20, box.y + 72))

        # Column headers
        y = box.y + 100
        headers = [
            ("Skill", 20), ("Level", 168), ("XP", 240),
            ("XP for level", 340), ("To next", 480),
        ]
        for text, ox in headers:
            self.screen.blit(self.font_small.render(text, True, ACCENT), (box.x + ox, y))
        y += 22
        pygame.draw.line(self.screen, PANEL_LINE, (box.x + 16, y), (box.right - 16, y), 1)
        y += 8

        levels = self.player.get("levels") or {}
        xp_map = self.player.get("xp") or {}
        row_h = 38
        for i, skill in enumerate(XP_SKILLS):
            lvl = int(levels.get(skill, 1))
            xp = int(xp_map.get(skill, 0))
            to_next = combat.xp_to_next_level(xp)
            xp_at_level = combat.xp_for_level(lvl)
            name = SKILL_DISPLAY_NAMES.get(skill, skill.title())
            row = pygame.Rect(box.x + 16, y, box.w - 32, row_h - 4)
            bg = (28, 34, 44) if i % 2 == 0 else (24, 28, 36)
            pygame.draw.rect(self.screen, bg, row, border_radius=4)

            # Progress bar toward next level
            bar = pygame.Rect(row.x + 232, row.y + 24, 100, 5)
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
            self.screen.blit(self.font.render(str(lvl), True, (220, 230, 245)), (row.x + 156, row.y + 8))
            self.screen.blit(self.font_small.render(f"{xp:,}", True, (180, 200, 230)), (row.x + 228, row.y + 4))
            self.screen.blit(
                self.font_small.render(f"{xp_at_level:,}", True, GREY),
                (row.x + 340, row.y + 8),
            )
            next_txt = "MAX" if to_next <= 0 else f"{to_next:,}"
            self.screen.blit(self.font_small.render(next_txt, True, GREY), (row.x + 480, row.y + 8))
            y += row_h

        foot = self.font_tiny.render(
            "Lighting logs with a tinderbox trains Firemaking.  Combat = Att/Str/Def/HP.",
            True, (140, 138, 120),
        )
        self.screen.blit(foot, (box.x + 20, box.bottom - 28))

    def draw_pets_modal(self):
        box = pygame.Rect(260, 100, 520, 420)
        pygame.draw.rect(self.screen, (16, 22, 30), box)
        pygame.draw.rect(self.screen, (120, 180, 230), box, 2)
        title = self.font_big.render("Your Pets", True, WHITE)
        self.screen.blit(title, (box.x + 18, box.y + 14))
        self.screen.blit(
            self.font_small.render("Click a companion to switch  ·  Esc closes", True, GREY),
            (box.x + 18, box.y + 48),
        )

        owned = (self.player or {}).get("owned_pets") or []
        self.pet_switch_rects = []
        y = box.y + 80
        if not owned:
            self.screen.blit(
                self.font.render("You don't own any pets yet.", True, GREY),
                (box.x + 18, y),
            )
            return
        for entry in owned:
            row = pygame.Rect(box.x + 16, y, box.w - 32, 56)
            active = entry.get("active")
            pygame.draw.rect(self.screen, (42, 70, 50) if active else (34, 40, 52), row, border_radius=6)
            pygame.draw.rect(
                self.screen, GREEN if active else PANEL_LINE, row, 1, border_radius=6,
            )
            self.pet_switch_rects.append((row, entry.get("pet_id")))

            icon = pygame.Rect(row.x + 10, row.y + 8, 40, 40)
            pygame.draw.rect(self.screen, (24, 28, 36), icon)
            sprites.draw_pet(
                self.screen, entry.get("sprite") or entry.get("pet_id"),
                icon.centerx, icon.centery + 6, 28, time.time(),
                facing=1,
            )
            name = entry.get("name", "?")
            lvl = entry.get("level", 1)
            status = "ACTIVE" if active else "Switch"
            self.screen.blit(self.font.render(name, True, WHITE), (row.x + 62, row.y + 10))
            self.screen.blit(
                self.font_small.render(f"Level {lvl}  ·  {status}", True, YELLOW if active else GREY),
                (row.x + 62, row.y + 32),
            )
            y += 64

        self.screen.blit(
            self.font_tiny.render("Buy more at Pet Emporium (Luna). Owned pets stay yours.", True, GREY),
            (box.x + 18, box.bottom - 28),
        )

    def handle_pets_click(self, mx, my):
        box = pygame.Rect(260, 100, 520, 420)
        if not box.collidepoint(mx, my):
            self.show_pets = False
            return
        for rect, pet_id in self.pet_switch_rects:
            if rect.collidepoint(mx, my) and pet_id:
                self.net.send("SET_PET", pet_id=pet_id)
                return

    def draw_help_modal(self):
        box = pygame.Rect(120, 30, 580, 640)
        pygame.draw.rect(self.screen, (16, 18, 26), box)
        pygame.draw.rect(self.screen, (120, 190, 255), box, 2)
        title = self.font_big.render("Controls", True, WHITE)
        self.screen.blit(title, (box.x + 16, box.y + 14))

        sections = [
            ("Movement & combat", [
                ("Arrow keys", "Walk one tile (cancels click-walk)"),
                ("Click ground", "Walk there"),
                ("Click monster / NPC", "Walk over, then attack / talk"),
                ("Space", "Attack nearest adjacent monster"),
                ("Att/Str/Def/HP", "Combat XP style (sidebar or keys 1-4)"),
            ]),
            ("World", [
                ("Click ore / tree", "Walk over and gather"),
                ("Click shoreline water", "Walk beside it and fish"),
                ("Click door / entrance", "Walk through into the building or dungeon"),
                ("Click furnace", "Smelt ores into bars"),
                ("Click anvil", "Smith bars into weapons & armour"),
                ("Click hearth", "Cook raw fish into food"),
                ("Click campfire", "Cook on a fire you lit with logs + tinderbox"),
                ("Click bank booth", "Walk over and open bank"),
                ("Click loot / player", "Walk over and pick up / trade"),
                ("Use logs / tinderbox", "Light a campfire on your tile"),
                ("G", "Pick up items on your tile"),
                ("P / sidebar button", "Toggle auto-pickup items (coins always auto)"),
            ]),
            ("Panels", [
                ("E", "Equipment & stats"),
                ("F", "Forge UI (furnace or anvil only)"),
                ("C", "Cooking UI (hearth or campfire)"),
                ("B", "Bank (at booth / Banker Iris)"),
                ("H", "This help popup"),
                ("Tab", "Skills modal (levels, XP, combat & total)"),
                ("I", "Toggle inventory focus"),
                ("Q", "Toggle quest log"),
                ("Enter", "Open / send chat"),
                ("Esc", "Close popups / dialogue"),
                ("Logout", "Sidebar button — return to login screen"),
            ]),
            ("Dialogue / forge", [
                ("A / T", "Accept / turn in quest"),
                ("B", "Browse shop or open bank"),
                ("S", "Open forge at nearest furnace/anvil (talking to Gareth)"),
                ("Y / N", "Accept or decline trade"),
            ]),
            ("Limits", [
                ("Purse", "65,000 coins max on you"),
                ("Bank vault", "10,000,000 coins + 48 item slots"),
                ("Ores", "100 ores max in inventory (bank the rest)"),
            ]),
            ("Inventory", [
                ("Left-click item", "Equip, eat, or use"),
                ("Right-click bones", "Bury one for Karma XP"),
                ("Right-click other", "Drop one"),
                ("Right-click item", "Drop"),
            ]),
        ]

        y = box.y + 52
        for heading, rows in sections:
            self.screen.blit(self.font.render(heading, True, YELLOW), (box.x + 20, y))
            y += 22
            for key, desc in rows:
                self.screen.blit(self.font_small.render(f"{key:<16}", True, (160, 210, 255)), (box.x + 28, y))
                self.screen.blit(self.font_small.render(desc, True, WHITE), (box.x + 160, y))
                y += 17
            y += 8

        self.screen.blit(
            self.font_small.render("Press H or Esc to close  ·  click outside to close", True, GREY),
            (box.x + 20, box.y + box.h - 28),
        )

    def draw_leaderboard_modal(self):
        box = pygame.Rect(160, 70, 780, 580)
        pygame.draw.rect(self.screen, (14, 16, 24), box)
        pygame.draw.rect(self.screen, (230, 190, 70), box, 2)
        title = self.font_big.render("Hiscores — Top Players", True, YELLOW)
        self.screen.blit(title, (box.x + 20, box.y + 14))

        skills = self.leaderboard_skills or list(self.leaderboard.keys()) or (
            ["total"] + list(XP_SKILLS)
        )
        self.leaderboard_tab_rects = {}
        tx, ty = box.x + 20, box.y + 55
        for skill in skills:
            label = SKILL_DISPLAY_NAMES.get(skill, skill.title())
            if skill == "total":
                label = "Total"
            short = label if len(label) <= 10 else label[:8]
            tw = max(72, self.font_small.size(short)[0] + 16)
            if tx + tw > box.right - 20:
                tx = box.x + 20
                ty += 30
            r = pygame.Rect(tx, ty, tw, 26)
            self.leaderboard_tab_rects[skill] = r
            active = skill == self.leaderboard_skill
            pygame.draw.rect(self.screen, (70, 90, 40) if active else (32, 34, 44), r)
            pygame.draw.rect(self.screen, YELLOW if active else PANEL_LINE, r, 1)
            txt = self.font_small.render(short, True, WHITE if active else GREY)
            self.screen.blit(txt, (r.x + (r.w - txt.get_width()) // 2, r.y + 5))
            tx += tw + 6

        header_y = ty + 44
        skill_name = "Total" if self.leaderboard_skill == "total" else (
            SKILL_DISPLAY_NAMES.get(self.leaderboard_skill, self.leaderboard_skill.title())
        )
        skill_title = self.font.render(f"{skill_name} rankings", True, WHITE)
        self.screen.blit(skill_title, (box.x + 24, header_y))
        self.screen.blit(self.font_small.render("Rank", True, GREY), (box.x + 30, header_y + 30))
        self.screen.blit(self.font_small.render("Player", True, GREY), (box.x + 90, header_y + 30))
        level_hdr = "Total lvl" if self.leaderboard_skill == "total" else "Level"
        self.screen.blit(self.font_small.render(level_hdr, True, GREY), (box.x + 400, header_y + 30))
        xp_hdr = "Total XP" if self.leaderboard_skill == "total" else "XP"
        self.screen.blit(self.font_small.render(xp_hdr, True, GREY), (box.x + 520, header_y + 30))

        rows = self.leaderboard.get(self.leaderboard_skill) or []
        y = header_y + 54
        if not rows:
            self.screen.blit(
                self.font.render("No players yet — be the first!", True, GREY),
                (box.x + 30, y),
            )
        for i, entry in enumerate(rows):
            rank_color = YELLOW if i == 0 else (200, 200, 210) if i < 3 else WHITE
            pygame.draw.rect(self.screen, (28, 30, 40), (box.x + 24, y - 4, 730, 34))
            self.screen.blit(self.font.render(str(i + 1), True, rank_color), (box.x + 40, y))
            self.screen.blit(self.font.render(entry.get("name", "?"), True, WHITE), (box.x + 90, y))
            self.screen.blit(self.font.render(str(entry.get("level", 1)), True, GREEN), (box.x + 410, y))
            xp_val = int(entry.get("xp", 0) or 0)
            self.screen.blit(self.font.render(f"{xp_val:,}", True, GREY), (box.x + 520, y))
            y += 40

        self.screen.blit(
            self.font_small.render(
                "Click a skill tab  ·  Left/Right arrows switch skill  ·  Esc or click outside to close",
                True, GREY,
            ),
            (box.x + 24, box.y + box.h - 28),
        )

    def handle_leaderboard_click(self, pos):
        mx, my = pos
        for skill, rect in self.leaderboard_tab_rects.items():
            if rect.collidepoint(mx, my):
                self.leaderboard_skill = skill
                return
        box = pygame.Rect(160, 70, 780, 580)
        if not box.collidepoint(mx, my):
            self.show_leaderboard = False


if __name__ == "__main__":
    GameClient().run()
