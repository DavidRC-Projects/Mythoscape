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
from content import ITEMS, RESOURCE_LABELS  # noqa: E402
import world_map as wm  # noqa: E402
import procedural_sprites_finished as sprites  # noqa: E402

SERVER_HOST = sys.argv[1] if len(sys.argv) > 1 else "localhost"
SERVER_URI = f"ws://{SERVER_HOST}:8765"

SCREEN_W, SCREEN_H = 1200, 800
MAP_W, MAP_H = 900, 640
SIDEBAR_X = MAP_W
TILE = 36

# Larger on-screen characters / props relative to the tile grid.
sprites.set_art_scale(2.0)

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
    "coal_rock": ((45, 45, 50), (90, 90, 100)),
}
ROBED_NPC_IDS = {
    "elder_miriam", "priest_cedric", "monk_healer", "mysterious_traveler",
}
ORE_LABEL_COLORS = {
    "copper_rock": (255, 170, 90),
    "tin_rock": (200, 210, 230),
    "iron_rock": (220, 150, 120),
    "coal_rock": (160, 160, 170),
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
        self.shop = None           # {"shop_id","name","stock","your_coins","buys"}
        self.show_shop_panel = False
        self.shop_buy_rects = []   # [(rect, item_id), ...]
        self.shop_sell_rects = []  # [(rect, slot_index, item_id), ...]
        self.combat_style = "attack"
        self.combat_style_rects = []  # [(rect, style), ...]
        self.trade_incoming = None  # {"from_player_id","from_name"}
        self.trade_state = None     # {"other_name","your_offer","other_offer",...}
        self.interactables = []
        self.craft_recipes = {}
        self.show_equipment = False
        self.show_forge = False
        self.show_help = False
        self.show_leaderboard = False
        self.leaderboard = {}       # skill -> [{name, xp, level}]
        self.leaderboard_skills = []
        self.leaderboard_skill = "attack"
        self.leaderboard_tab_rects = {}
        self.forge_tab = "smelt"  # or "smith"
        self.forge_metal = "all"  # all | bronze | iron | steel
        self.forge_gear = "all"   # all | weapon | shield | body | legs | helmet | bar
        self.forge_recipe_rects = []
        self.forge_filter_rects = {}

        self.floaters = []  # floating text/hitsplats: dicts with x,y,text,color,expire,kind
        self.attack_anims = {}  # entity_id -> expire timestamp
        self.level_up_until = 0.0  # gold glow / banner while celebrating a level-up
        self.level_up_label = ""
        self.show_inventory = True
        self.show_stats = True
        self.show_xp = False
        self.show_quests = False
        self._prev_entity_pos = {}  # id -> (x, y) for walk animation

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
        elif t == "LEADERBOARD":
            self.leaderboard = msg.get("boards") or {}
            self.leaderboard_skills = msg.get("skills") or list(self.leaderboard.keys())
            if self.leaderboard_skills and self.leaderboard_skill not in self.leaderboard_skills:
                self.leaderboard_skill = self.leaderboard_skills[0]
            # Only show on the login screen (ignore late replies after logging in).
            if self.state == "LOGIN":
                self.show_leaderboard = True
        elif t == "LOGIN_OK":
            self.player = msg["player"]
            self.combat_style = self.player.get("combat_style") or "attack"
            self.state = "GAME"
            self.login_error = ""
            self.show_leaderboard = False
        elif t == "WORLD_STATE":
            self.tiles = msg["tiles"]
            self.world_w, self.world_h = msg["width"], msg["height"]
            self.npcs = msg["npcs"]
            self.resources = msg["resources"]
            self.interactables = msg.get("interactables") or []
            self.craft_recipes = msg.get("craft_recipes") or {}
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
                "forge": msg.get("forge"),
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
                if kind == "player_hits_monster":
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
                # Always type into the active field — never steal letter keys for shortcuts.
                self.fields[self.active_field] += event.unicode
        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            mx, my = event.pos
            login_tab = pygame.Rect(350, 200, 190, 34)
            register_tab = pygame.Rect(550, 200, 200, 34)
            submit_y = 410 if self.login_mode == "register" else 360
            submit_btn = pygame.Rect(350, submit_y, 400, 40)
            hiscores_btn = pygame.Rect(780, 200, 160, 34)
            if login_tab.collidepoint(mx, my):
                self.set_login_mode("login")
                return
            if register_tab.collidepoint(mx, my):
                self.set_login_mode("register")
                return
            if hiscores_btn.collidepoint(mx, my):
                self.request_leaderboard()
                return
            if submit_btn.collidepoint(mx, my):
                self.submit_login()
                return
            if 350 <= mx <= 750:
                if 250 <= my <= 285:
                    self.active_field = "username"
                elif 300 <= my <= 335:
                    self.active_field = "password"
                elif self.login_mode == "register" and 350 <= my <= 385:
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
            if self.show_forge or self.show_equipment or self.show_help:
                if event.key == pygame.K_ESCAPE:
                    self.show_forge = False
                    self.show_equipment = False
                    self.show_help = False
                elif event.key == pygame.K_h:
                    self.show_help = not self.show_help
                    if self.show_help:
                        self.show_forge = False
                        self.show_equipment = False
                elif event.key == pygame.K_e:
                    self.show_equipment = not self.show_equipment
                    if self.show_equipment:
                        self.show_forge = False
                        self.show_help = False
                elif event.key == pygame.K_f:
                    self.show_forge = not self.show_forge
                    if self.show_forge:
                        self.show_equipment = False
                        self.show_help = False
                elif self.show_forge and event.key == pygame.K_1:
                    self.forge_tab = "smelt"
                elif self.show_forge and event.key == pygame.K_2:
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
                self.show_stats = not self.show_stats
            elif event.key == pygame.K_q:
                self.show_quests = not self.show_quests
            elif event.key == pygame.K_x:
                self.show_xp = not self.show_xp
            elif event.key == pygame.K_e:
                self.show_equipment = not self.show_equipment
                if self.show_equipment:
                    self.show_forge = False
                    self.show_help = False
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
                self.show_shop_panel = False
                self.clear_walk()
        elif event.type == pygame.MOUSEBUTTONDOWN:
            self.handle_mouse_click(event)

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
        self.show_equipment = False
        self.show_help = False
        if kind == "furnace":
            self.forge_tab = "smelt"
            self.forge_gear = "bar"
        elif kind == "anvil":
            self.forge_tab = "smith"
            if self.forge_gear == "bar":
                self.forge_gear = "all"
        # Prefer the highest metal you can currently work
        smith_lvl = (self.player.get("levels") or {}).get("smithing", 1) if self.player else 1
        if smith_lvl >= 30:
            self.forge_metal = "steel"
        elif smith_lvl >= 15:
            self.forge_metal = "iron"
        else:
            self.forge_metal = "bronze"

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
        if self.show_forge:
            self.handle_forge_click(mx, my)
            return
        if self.show_equipment:
            self.handle_equipment_click(mx, my)
            return
        if self.show_shop_panel and self.shop:
            self.handle_shop_click(mx, my, event.button)
            return
        if self.show_help:
            box = pygame.Rect(140, 50, 540, 560)
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

        # smithy stations — walk onto/beside them, then open the right panel
        for spot in self.interactables:
            if spot["x"] == tx and spot["y"] == ty:
                kind = spot.get("kind")
                if kind in ("furnace", "anvil", "forge"):
                    goals = self.adjacent_goals(tx, ty)
                    if self.tile_walkable(tx, ty):
                        goals = set(goals) | {(tx, ty)}
                    self.walk_and_act(goals, {"type": "FORGE", "kind": kind})
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
        size = 46
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
                if button == 3:  # right click = drop 1
                    self.net.send("DROP", slot_index=slot, qty=1)
                elif item.get("equip_slot"):
                    self.net.send("EQUIP", slot_index=slot)
                elif item["type"] == "food":
                    self.net.send("USE_ITEM", slot_index=slot)
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
        self.draw_button("Hiscores", pygame.Rect(780, 200, 160, 34), primary=False)

        hint = self.font_small.render("Tab: switch field   Enter: submit   F2: mode   F3: hiscores", True, GREY)
        self.screen.blit(hint, (350, submit_y + 55))
        if self.login_error:
            err = self.font.render(self.login_error, True, RED)
            self.screen.blit(err, (350, submit_y + 80))

        if self.show_leaderboard:
            self.draw_leaderboard_modal()

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
        if self.show_equipment:
            self.draw_equipment_modal()
        if self.show_forge:
            self.draw_forge_modal()
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

        # resource nodes (trees, rocks, fishing spots)
        for key, rtype in self.resources.items():
            x, y = map(int, key.split(","))
            sx, sy = x - cam_x, y - cam_y
            if 0 <= sx <= vis_w and 0 <= sy <= vis_h:
                cx, cy = sx * TILE + TILE // 2, sy * TILE + TILE // 2
                self.draw_resource_sprite(rtype, cx, cy, t)
                label = RESOURCE_LABELS.get(rtype)
                if label:
                    color = ORE_LABEL_COLORS.get(rtype, WHITE)
                    surf = self.font_small.render(label, True, color)
                    self.screen.blit(surf, (cx - surf.get_width() // 2, cy - TILE // 2 - 14))

        # smithy stations (furnace / anvil)
        for spot in self.interactables:
            sx, sy = spot["x"] - cam_x, spot["y"] - cam_y
            if 0 <= sx <= vis_w and 0 <= sy <= vis_h:
                cx, cy = sx * TILE + TILE // 2, sy * TILE + TILE // 2
                kind = spot.get("kind")
                if kind == "furnace":
                    sprites.draw_furnace(self.screen, cx, cy, TILE, t)
                elif kind == "anvil":
                    sprites.draw_anvil(self.screen, cx, cy, TILE, t)
                elif kind == "forge":
                    sprites.draw_forge(self.screen, cx, cy, TILE, t)
                self.blit_label(spot.get("name", "Station"), cx, cy - TILE // 2 - 4)
        # smithy doorway label
        door_sx, door_sy = 21 - cam_x, 13 - cam_y
        if 0 <= door_sx <= vis_w and 0 <= door_sy <= vis_h:
            label = self.font_small.render("Smithy", True, (255, 200, 120))
            self.screen.blit(
                label,
                (door_sx * TILE + TILE // 2 - label.get_width() // 2, door_sy * TILE - 14),
            )
        # dungeon entrance (mine east wall)
        dun_sx, dun_sy = 31 - cam_x, 42 - cam_y
        if 0 <= dun_sx <= vis_w and 0 <= dun_sy <= vis_h:
            label = self.font_small.render("Dungeon", True, (200, 160, 220))
            self.screen.blit(
                label,
                (dun_sx * TILE + TILE // 2 - label.get_width() // 2, dun_sy * TILE - 14),
            )

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
                atk = self._attack_progress(m["id"], t)
                sprites.draw_monster(self.screen, m["type"], cx, cy, TILE, t, hurt=hurt, attacking=atk)
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
                atk = self._attack_progress(p["id"], t)
                if is_self and time.time() < self.level_up_until:
                    self.draw_level_up_glow(cx, cy, time.time())
                sprites.draw_humanoid_detailed(
                    self.screen, cx, cy, TILE, body, skin, hair,
                    weapon=weapon_style(eq.get("weapon")),
                    shield=bool(eq.get("shield")),
                    moving=moving, t=t,
                    equipment=eq,
                    attacking=atk,
                )
                self.blit_label(p["name"], cx, cy - TILE // 2 - 12)
                self.draw_hp_bar(cx, cy - TILE // 2 - 6, p["hp"], p["max_hp"])
                if is_self and time.time() < self.level_up_until:
                    self.draw_level_up_banner(cx, cy - TILE // 2 - 28, time.time())
            now_pos[("p", p["id"])] = (p["x"], p["y"])

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

        pygame.draw.rect(self.screen, PANEL_LINE, (0, 0, MAP_W, MAP_H), 2)
        zone = wm.get_zone(self.player["x"], self.player["y"])
        zone_label = self.font.render(zone.title(), True, WHITE)
        self.screen.blit(zone_label, (10, 10))

    def draw_terrain_tile(self, rect, tile_id, wx, wy, t):
        zone = wm.get_zone(wx, wy) if self.world_w else "wilderness"
        if tile_id in (wm.TREE, wm.OAK_TREE, wm.FISH_SPOT):
            sprites.draw_grass(self.screen, rect, wx, wy)
        elif tile_id in (wm.ORE, wm.IRON_ORE):
            sprites.draw_floor(self.screen, rect, wx, wy, zone=zone)
        elif tile_id == wm.GRASS:
            sprites.draw_grass(self.screen, rect, wx, wy)
        elif tile_id == wm.PATH:
            sprites.draw_path(self.screen, rect, wx, wy)
        elif tile_id == wm.FLOOR:
            sprites.draw_floor(self.screen, rect, wx, wy, zone=zone)
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
            sprites.draw_rock_detailed(
                self.screen, cx, cy, TILE,
                variant=sum(ord(c) for c in rtype) % 3,
                ore_type=rtype,
            )
        elif rtype.startswith("fishing_spot"):
            sprites.draw_fishing_spot(self.screen, cx, cy, TILE, t)
        else:
            sprites.draw_tree(self.screen, cx, cy, TILE)
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
        xp_map = self.player.get("xp") or {}
        for skill in ["attack", "strength", "defence", "hitpoints",
                      "woodcutting", "mining", "fishing", "smithing"]:
            lvl = levels.get(skill, 1)
            if self.show_xp:
                xp_val = int(xp_map.get(skill, 0))
                row = self.font_small.render(f"{skill.title():<11}{lvl:>2}  {xp_val} xp", True, (200, 220, 255))
            else:
                row = self.font_small.render(f"{skill.title():<12} {lvl:>2}", True, GREY)
            self.screen.blit(row, (SIDEBAR_X + 16, y))
            y += 18

        y += 4
        xp_hint = self.font_small.render(
            "X hide XP" if self.show_xp else "X show XP totals",
            True, (180, 180, 120),
        )
        self.screen.blit(xp_hint, (SIDEBAR_X + 16, y))
        y += 18
        hint = self.font_small.render("E gear   F forge   H help", True, (180, 180, 120))
        self.screen.blit(hint, (SIDEBAR_X + 16, y))
        y += 22

        # Combat style — XP from fighting goes to the selected skill
        style_label = self.font_small.render("Combat XP →", True, WHITE)
        self.screen.blit(style_label, (SIDEBAR_X + 16, y))
        y += 18
        self._combat_style_oy = y
        current = self.combat_style or (self.player.get("combat_style") if self.player else "attack") or "attack"
        self.combat_style_rects = []
        for rect, style, label in self.combat_style_button_rects():
            selected = style == current
            bg = (50, 90, 50) if selected else (40, 42, 52)
            border = GREEN if selected else PANEL_LINE
            pygame.draw.rect(self.screen, bg, rect, border_radius=4)
            pygame.draw.rect(self.screen, border, rect, 2, border_radius=4)
            txt = self.font_small.render(label, True, WHITE if selected else GREY)
            self.screen.blit(txt, (rect.x + (rect.w - txt.get_width()) // 2,
                                   rect.y + (rect.h - txt.get_height()) // 2))
            self.combat_style_rects.append((rect, style))

        inv_y = y + 66
        self._inventory_oy = inv_y + 22
        # inventory grid
        inv_label = self.font.render("Inventory (click=use/equip, right-click=drop)", True, WHITE)
        self.screen.blit(inv_label, (SIDEBAR_X + 16, inv_y))
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
        qy = 620
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
            "Arrows move  Space attack  E gear  F forge  H help", True, GREY)
        self.screen.blit(controls, (SIDEBAR_X + 10, SCREEN_H - 18))

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
        y = MAP_H + 6
        for line in self.chat_log[-6:]:
            if isinstance(line, dict):
                text = line.get("text", "")
                color = line.get("color") or WHITE
                highlight = bool(line.get("highlight"))
            else:
                text, color, highlight = line, WHITE, False
            if highlight:
                bar = pygame.Rect(4, y - 1, MAP_W - 12, 16)
                pygame.draw.rect(self.screen, (70, 55, 18), bar, border_radius=3)
                pygame.draw.rect(self.screen, (210, 170, 50), bar, 1, border_radius=3)
            surf = self.font_small.render(str(text)[:110], True, color)
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
            self.screen.blit(self.font_small.render("Press B to open shop (buy & sell)", True, (255, 210, 120)),
                              (box.x + 12, box.y + box.h - 40))
        if self.dialogue.get("forge"):
            self.screen.blit(self.font_small.render("Press S to use the forge (smelt & smith)", True, (255, 180, 100)),
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
        box = pygame.Rect(180, 60, 460, 480)
        pygame.draw.rect(self.screen, (18, 20, 28), box)
        pygame.draw.rect(self.screen, YELLOW, box, 2)
        title = self.font_big.render("Equipment & Stats", True, WHITE)
        self.screen.blit(title, (box.x + 16, box.y + 12))

        eq = self.player.get("equipment") or {}
        bonuses = {"att_bonus": 0, "str_bonus": 0, "def_bonus": 0}
        y = box.y + 48
        self.equip_slot_rects = {}
        for slot in ("helmet", "weapon", "shield", "body", "legs"):
            item_id = eq.get(slot)
            item = ITEMS.get(item_id) if item_id else None
            name = item["name"] if item else "(empty)"
            row = pygame.Rect(box.x + 20, y, 420, 44)
            pygame.draw.rect(self.screen, (40, 42, 52), row)
            pygame.draw.rect(self.screen, PANEL_LINE, row, 1)
            self.equip_slot_rects[slot] = row
            icon = pygame.Rect(row.x + 8, row.y + 6, 32, 32)
            pygame.draw.rect(self.screen, (30, 30, 38), icon)
            if item_id:
                sprites.draw_item_icon(self.screen, icon, item_id, ITEMS)
                for k in bonuses:
                    bonuses[k] += item.get(k, 0)
            label = self.font.render(f"{slot.title()}: {name}", True, WHITE)
            self.screen.blit(label, (row.x + 50, row.y + 6))
            if item:
                detail = self.font_small.render(
                    f"Att +{item.get('att_bonus', 0)}  Str +{item.get('str_bonus', 0)}  Def +{item.get('def_bonus', 0)}",
                    True, GREY)
                self.screen.blit(detail, (row.x + 50, row.y + 24))
            y += 50

        y += 6
        levels = self.player.get("levels") or {}
        wb = bonuses
        stats = [
            f"Attack {levels.get('attack', 1)}  (+{wb['att_bonus']} gear)",
            f"Strength {levels.get('strength', 1)}  (+{wb['str_bonus']} gear)",
            f"Defence {levels.get('defence', 1)}  (+{wb['def_bonus']} gear)",
            f"Hitpoints {self.player['hp']} / {self.player['max_hp']}",
            f"Smithing {levels.get('smithing', 1)}",
        ]
        self.screen.blit(self.font.render("Combat summary", True, YELLOW), (box.x + 20, y))
        y += 24
        for line in stats:
            self.screen.blit(self.font_small.render(line, True, WHITE), (box.x + 24, y))
            y += 16

        self.screen.blit(
            self.font_small.render("Click a worn item to unequip it.  Esc / E to close", True, GREY),
            (box.x + 20, box.y + box.h - 28),
        )

    def handle_equipment_click(self, mx, my):
        for slot, rect in getattr(self, "equip_slot_rects", {}).items():
            if rect.collidepoint(mx, my) and (self.player.get("equipment") or {}).get(slot):
                self.net.send("UNEQUIP", equip_slot=slot)
                return
        # click outside closes
        box = pygame.Rect(180, 60, 460, 480)
        if not box.collidepoint(mx, my):
            self.show_equipment = False

    def draw_forge_modal(self):
        box = pygame.Rect(100, 40, 620, 560)
        pygame.draw.rect(self.screen, (18, 20, 28), box)
        pygame.draw.rect(self.screen, (255, 160, 80), box, 2)
        title = self.font_big.render("Gareth's Smithy", True, WHITE)
        self.screen.blit(title, (box.x + 16, box.y + 10))
        smith_lvl = (self.player.get("levels") or {}).get("smithing", 1)
        self.screen.blit(
            self.font.render(f"Smithing level: {smith_lvl}", True, YELLOW),
            (box.x + 400, box.y + 16),
        )

        tabs = [("smelt", "1 Furnace"), ("smith", "2 Anvil")]
        self.forge_tab_rects = {}
        for i, (key, label) in enumerate(tabs):
            r = pygame.Rect(box.x + 20 + i * 140, box.y + 46, 130, 28)
            self.forge_tab_rects[key] = r
            active = self.forge_tab == key
            pygame.draw.rect(self.screen, (55, 90, 50) if active else (35, 35, 45), r)
            pygame.draw.rect(self.screen, GREEN if active else PANEL_LINE, r, 2)
            txt = self.font.render(label, True, WHITE)
            self.screen.blit(txt, (r.x + (r.w - txt.get_width()) // 2, r.y + 4))

        # Metal + gear type toggles
        self.forge_filter_rects = {}
        metal_opts = [("all", "All"), ("bronze", "Bronze"), ("iron", "Iron"), ("steel", "Steel")]
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
        y_filter = box.y + 82
        self.screen.blit(self.font_small.render("Metal:", True, GREY), (box.x + 20, y_filter + 6))
        x = box.x + 70
        for key, label in metal_opts:
            r = pygame.Rect(x, y_filter, 70, 24)
            self.forge_filter_rects[("metal", key)] = r
            active = self.forge_metal == key
            pygame.draw.rect(self.screen, (70, 60, 40) if active else (32, 34, 42), r)
            pygame.draw.rect(self.screen, (255, 200, 100) if active else PANEL_LINE, r, 1)
            txt = self.font_small.render(label, True, WHITE if active else GREY)
            self.screen.blit(txt, (r.x + (r.w - txt.get_width()) // 2, r.y + 4))
            x += 76

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
        y = box.y + 148
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
                (box.x + 20, box.y + 160),
            )

        self.screen.blit(
            self.font_small.render(
                "Click furnace/anvil to walk there · Toggle metal & type · Esc / F closes",
                True, GREY,
            ),
            (box.x + 20, box.y + box.h - 26),
        )

    def _forge_recipe_metal(self, rid, recipe):
        blob = f"{rid} {recipe.get('name', '')} {recipe.get('output', ('',))[0]}".lower()
        for metal in ("steel", "iron", "bronze"):
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

    def draw_help_modal(self):
        box = pygame.Rect(140, 50, 540, 560)
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
                ("Click water", "Walk beside it and fish"),
                ("Click furnace / anvil", "Walk over and open forge"),
                ("Click loot / player", "Walk over and pick up / trade"),
                ("G", "Pick up items on your tile"),
            ]),
            ("Panels", [
                ("E", "Equipment & stats"),
                ("F", "Forge UI (inside smithy, by furnace/anvil)"),
                ("H", "This help popup"),
                ("X", "Toggle XP totals next to each skill"),
                ("I", "Toggle inventory focus"),
                ("Tab", "Toggle stats list"),
                ("Q", "Toggle quest log"),
                ("Enter", "Open / send chat"),
                ("Esc", "Close popups / dialogue"),
            ]),
            ("Dialogue / forge", [
                ("A / T", "Accept / turn in quest"),
                ("B", "Browse shop"),
                ("S", "Open forge UI (talking to Gareth in the smithy)"),
                ("1 / 2", "Furnace (smelt) / Anvil (smith) tabs"),
                ("Y / N", "Accept or decline trade"),
            ]),
            ("Inventory", [
                ("Left-click item", "Equip, eat, or use"),
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

        skills = self.leaderboard_skills or list(self.leaderboard.keys()) or [
            "attack", "strength", "defence", "hitpoints",
            "woodcutting", "mining", "fishing", "smithing",
        ]
        self.leaderboard_tab_rects = {}
        tx, ty = box.x + 20, box.y + 55
        for skill in skills:
            label = skill.title()[:8]
            tw = max(72, self.font_small.size(label)[0] + 16)
            if tx + tw > box.right - 20:
                tx = box.x + 20
                ty += 30
            r = pygame.Rect(tx, ty, tw, 26)
            self.leaderboard_tab_rects[skill] = r
            active = skill == self.leaderboard_skill
            pygame.draw.rect(self.screen, (70, 90, 40) if active else (32, 34, 44), r)
            pygame.draw.rect(self.screen, YELLOW if active else PANEL_LINE, r, 1)
            txt = self.font_small.render(label, True, WHITE if active else GREY)
            self.screen.blit(txt, (r.x + (r.w - txt.get_width()) // 2, r.y + 5))
            tx += tw + 6

        header_y = ty + 44
        skill_title = self.font.render(f"{self.leaderboard_skill.title()} rankings", True, WHITE)
        self.screen.blit(skill_title, (box.x + 24, header_y))
        self.screen.blit(self.font_small.render("Rank", True, GREY), (box.x + 30, header_y + 30))
        self.screen.blit(self.font_small.render("Player", True, GREY), (box.x + 90, header_y + 30))
        self.screen.blit(self.font_small.render("Level", True, GREY), (box.x + 420, header_y + 30))
        self.screen.blit(self.font_small.render("XP", True, GREY), (box.x + 520, header_y + 30))

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
            self.screen.blit(self.font.render(str(entry.get("level", 1)), True, GREEN), (box.x + 430, y))
            self.screen.blit(self.font.render(str(entry.get("xp", 0)), True, GREY), (box.x + 520, y))
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
