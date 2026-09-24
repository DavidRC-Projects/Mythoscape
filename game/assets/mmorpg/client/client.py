"""
MMORPG v0.1 client. Run with:  python client.py [server_host]

Requires: pip install pygame websockets
"""
import sys
import os
import time
import math

import pygame
from pygame.locals import K_TAB

from network import NetworkClient

# Reuse the server's static content module for item names/icons/etc so the
# client doesn't have to duplicate a second copy of the game data.
_HERE = os.path.dirname(__file__)
sys.path.insert(0, os.path.join(_HERE, "..", "server"))
sys.path.insert(0, os.path.join(_HERE, "..", "..", "characters"))
import building_sprites  # noqa: E402 — pre-rendered building shells
from camera_yaw import CameraYaw  # noqa: E402 — RS-style view rotate
from content import (
    ITEMS, RESOURCE_LABELS, karma_slot_bonus, cook_burn_chance,
    XP_SKILLS, SKILL_DISPLAY_NAMES, TRAVEL_DESTINATIONS, MONSTERS, QUESTS, NPCS,
    is_bow, bow_attack_range, FIRE_LOGS, FLETCH_LOGS,
    MAGIC_ABILITIES, MAGIC_ABILITY_ORDER, MANUAL_MAGIC_CD_FACTOR,
    is_raw_fish, is_cooked_fish, is_mining_bag_item, is_log_item,
    is_fletch_pouch_item, is_potion_item, is_gem_item,
    INVENTORY_TABS, INVENTORY_TAB_SIZE, INVENTORY_SIZE,
)  # noqa: E402
import world_map as wm  # noqa: E402
import combat  # noqa: E402
import procedural_sprites_finished as sprites  # noqa: E402
import building_textures as btex  # noqa: E402
import dungeon_interior_3d  # noqa: E402 — 3D dungeon interior props

# CC0 photoreal building textures (ambientCG) — walls, roofs, pier
btex.set_texture_dir(os.path.join(_HERE, "textures"))

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
    pet=2.05,
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
# Ornate sidebar chrome (fantasy mockup)
SB_BG = (14, 18, 28)
SB_BG_MID = (20, 26, 38)
SB_CARD = (26, 32, 46)
SB_CARD_HI = (34, 42, 60)
SB_GOLD = (206, 168, 78)
SB_GOLD_DIM = (128, 98, 48)
SB_GOLD_HI = (240, 208, 120)
SB_EDGE = (58, 48, 32)
SB_INSET = (10, 12, 18)

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
    "mad_scientist", "herald_rowan",
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
    if is_bow(item_id) or "bow" in item_id:
        return "bow"
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


class GameClient(CameraYaw):
    def __init__(self):
        pygame.init()
        pygame.display.set_caption("Mythoscape — Tiny MMORPG")
        self.screen = pygame.display.set_mode((SCREEN_W, SCREEN_H))
        self.clock = pygame.time.Clock()
        self.camera_yaw = 0  # 0=N up, 1=E up, 2=S up, 3=W up (RS-style)
        self.cam_drag = None  # {ox, accum, last_yaw} while middle-mouse orbiting
        self._cam_drag_threshold = 56  # pixels of drag per 90° snap

        # Readable UI text (slightly larger after skill/UI growth)
        ui = pygame.font.match_font("arial,helvetica,segoe ui,dejavu sans") or None
        mono = pygame.font.match_font("menlo,consolas,monaco,dejavu sans mono") or None
        self.font = pygame.font.SysFont(ui or mono, 20)
        self.font_small = pygame.font.SysFont(ui or mono, 18)
        self.font_big = pygame.font.SysFont(ui or mono, 30, bold=True)
        self.font_tiny = pygame.font.SysFont(ui or mono, 15)
        self.font_label = pygame.font.SysFont(ui or mono, 16, bold=True)
        self.font_inv = pygame.font.SysFont(ui or mono, 18)  # inventory qty / sidebar hints
        # Fantasy login / register branding (serif)
        serif = pygame.font.match_font(
            "times new roman,times,georgia,palatino,dejavu serif,liberation serif,serif"
        ) or ui or mono
        self.font_title = pygame.font.SysFont(serif, 42, bold=True)
        self.font_login = pygame.font.SysFont(serif, 20, bold=True)
        self.font_login_sm = pygame.font.SysFont(serif, 15, bold=True)
        self.font_login_tiny = pygame.font.SysFont(serif, 13)

        self.net = NetworkClient(SERVER_URI)
        self.net.start()

        self.state = "LOGIN"
        self.login_mode = "login"  # or "register"
        self.fields = {"username": "", "password": "", "char_name": ""}
        self.register_gender = "male"
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
        self.dialogue_btn_rects = {}  # action -> pygame.Rect
        self.shop = None           # {"shop_id","name","stock","your_coins","buys"}
        self.show_shop_panel = False
        self.shop_buy_rects = []   # [(rect, item_id), ...]
        self.shop_sell_rects = []  # [(rect, slot_index, item_id), ...]
        self.shop_buy_scroll = 0
        self.shop_sell_scroll = 0
        self.shop_scroll_meta = None  # {"buy": {...}, "sell": {...}, "mid_x", "box"}
        self.shop_drag = None  # {"side": "buy"|"sell", "y0", "scroll0"}
        self.combat_style = "attack"
        self.combat_style_confirmed = False  # ask on first melee attack each session
        self.combat_style_prompt = None  # {"target_id": int} while choosing XP skill
        self.combat_style_prompt_rects = {}
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
        self.sidebar_tab = "inventory"  # inventory | combat | magic | quests
        self.sidebar_action_rects = {}
        self.sidebar_tab_rects = {}
        self.magic_btn_rects = {}  # ability_id -> rect (fight bar + tab)
        self.magic_mode_btn_rect = None
        self.quest_row_rects = []  # [(rect, quest_id)] for journal click-to-giver
        self.quests_scroll = 0  # pixel offset into the journal list
        self.quests_scroll_meta = None
        self.magic_fx = []  # ephemeral cast visuals
        self.bank = None  # BANK_STATE payload
        self.bank_inv_rects = []
        self.bank_slot_rects = []
        self.bank_btn_rects = {}
        self.bank_inv_scroll = 0
        self.bank_page = 0
        self.bank_page_size = 36  # 6x6 grid visible per page
        self.auto_pickup_btn_rect = None
        self.logout_btn_rect = None
        self.sidebar_bank_btn_rect = None
        self.sidebar_settings_rect = None
        self.skills_view_all_rect = None
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
        self.show_fletch = False
        self.fletch_recipe_rects = []
        self.fletch_tab = "all"
        self.fletch_tab_rects = {}
        self.fires = set()  # {"x,y", ...} active campfires from STATE_UPDATE
        self.dungeon = None  # Tidehollow instance HUD state or None
        self._overworld_tiles = None
        self._overworld_size = None
        self.show_skills = False
        self.skills_scroll = 0  # pixel offset into the skills list
        self.skills_drag = None  # scrollbar drag state
        self.skills_scroll_meta = None  # {"list_top","view_h","max_scroll","track"} set while drawing
        self.help_scroll = 0  # pixel offset into the Controls help list
        self.help_drag = None  # scrollbar drag state
        self.help_scroll_meta = None  # set while drawing help modal
        self.inv_drag = None  # inventory rearrange drag state
        self.skills_btn_rect = None
        self.show_pets = False
        self.pets_btn_rect = None
        self.pet_switch_rects = []
        self.show_travel = False
        self.travel_btn_rects = []
        self.travel_scroll = 0  # pixel offset into the travel destination lists
        self.travel_drag = None  # scrollbar drag state
        self.travel_scroll_meta = None  # set while drawing travel modal
        self.show_world_map = False  # scrollable click-to-walk map (minimap icon)
        self.world_map_scroll = [0, 0]  # top-left world tile of the map viewport
        self.world_map_drag = None  # (mx, my, scroll_x, scroll_y) while dragging
        self.world_map_scale = 5  # pixels per world tile in the scrollable map
        self.minimap_rect = None
        self._minimap_base = None
        self._minimap_size = (0, 0)
        self.fire_prompt = None  # {"slot": int, "item_id": str, "name": str} or None
        self.fire_prompt_rects = {}
        self.drop_prompt = None  # {"slot", "item_id", "name", "qty"} or None
        self.drop_prompt_rects = {}
        self.arrow_prompt = None  # {"slot", "item_id", "name", "qty"} load quiver / drop
        self.arrow_prompt_rects = {}
        self.tip_prompt = None  # {"slot", "item_id", "name", "qty"} pack tip box / drop
        self.tip_prompt_rects = {}
        self.food_prompt = None  # cooked fish: eat / pack / drop
        self.food_prompt_rects = {}
        self.raw_prompt = None  # raw fish: pack / drop
        self.raw_prompt_rects = {}
        self.food_bag_prompt = None  # food bag: eat / pack all
        self.food_bag_prompt_rects = {}
        self.storage_bag_prompt = None  # generic bag: pack all / unpack all
        self.storage_bag_prompt_rects = {}
        self.pack_prompt = None  # generic pack/drop for ores, fletch mats, etc.
        self.pack_prompt_rects = {}
        self.log_prompt = None
        self.log_prompt_rects = {}
        self.potion_prompt = None
        self.potion_prompt_rects = {}
        self.cook_prompt = None  # {"recipe_id", "name", "available"} or None
        self.cook_prompt_rects = {}
        self.dungeon_prompt = None  # True when confirming Tidehollow entry
        self.dungeon_prompt_rects = {}
        self.dungeon_leave_rect = None
        self.show_wish = False
        self.wish_rects = {}
        self.wish_stat_choice = None  # {"skills": [...], "message": str} or None
        self.wish_stat_rects = {}
        self.well_fx = None  # {"x","y","until","kind"} lightning/sparkle at well

        self.floaters = []  # floating text/hitsplats: dicts with x,y,text,color,expire,kind
        self.pending_floaters = []  # hitsplats queued until strike frame
        self.attack_anims = {}  # entity_id -> expire timestamp
        self.attack_face = {}  # entity_id -> 1 | -1 while swinging
        self.attack_anim_kind = {}  # entity_id -> "melee" | "ranged"
        self.projectiles = []  # flying arrows: {ax,ay,tx,ty,start,dur}
        self.ATTACK_ANIM_SECS = 0.62
        self.RANGED_ANIM_SECS = 0.72
        self.level_up_until = 0.0  # gold glow / banner while celebrating a level-up
        self.level_up_label = ""
        self.show_inventory = True
        self.inv_tab = 0
        self.inv_tab_rects = {}
        self.show_stats = True
        self.show_xp = False
        self.show_quests = False
        self.inv_hover_slot = None
        self._prev_entity_pos = {}  # id -> (x, y) for walk animation
        self._entity_facing = {}  # id -> 1 | -1
        self._entity_moving_until = {}  # id -> timestamp while walk cycle plays

        # Click-to-walk: path of tile coords to step onto, then optional action.
        self.walk_path = []
        self.pending_action = None  # {"type": "ATTACK"|"TALK"|..., ...}
        self._next_walk_at = 0.0
        self.combat_target_id = None  # monster id currently fighting
        self.combat_quick = None  # above-head heal/potion buttons while under attack
        self.combat_quick_rects = {}
        self.combat_quick_until = 0.0
        self._low_hp_warn_until = 0.0  # pulse timer for sidebar warning
        self.death_banner_until = 0.0
        self.death_banner_text = ""
        self.chat_scroll = 0  # 0 = pinned to newest; higher = scrolled up
        self.CHAT_VISIBLE = 6
        self.CHAT_MAX = 80

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
            self.combat_style = "attack"
            self.combat_style_confirmed = False
            self.combat_style_prompt = None
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
            if self.combat_target_id is not None and self.combat_target_id not in self.monsters:
                self.combat_target_id = None
                self.combat_quick = None
                self.combat_quick_until = 0.0
            if "resources" in msg:
                self.resources = msg["resources"]
            self.fires = set(msg.get("fires") or [])
            if "dungeon" in msg and msg["dungeon"] and self.dungeon is not None:
                self.dungeon.update({
                    "floor": msg["dungeon"].get("floor", self.dungeon.get("floor")),
                    "floors": msg["dungeon"].get("floors", self.dungeon.get("floors")),
                    "remaining": msg["dungeon"].get("remaining", 0),
                    "label": msg["dungeon"].get("label", self.dungeon.get("label")),
                })
            # Keep local player coords in sync so the camera can follow.
            if self.player and self.player["id"] in self.players:
                live = self.players[self.player["id"]]
                self.player["x"] = live["x"]
                self.player["y"] = live["y"]
                self.player["hp"] = live["hp"]
                self.player["max_hp"] = live["max_hp"]
                self.player["gathering"] = live.get("gathering")
        elif t == "DUNGEON_ENTER":
            self._enter_dungeon_view(msg)
        elif t == "DUNGEON_FLOOR":
            self._enter_dungeon_view(msg, advance=True)
        elif t == "DUNGEON_EXIT":
            self._exit_dungeon_view()
            if self.player:
                self.player["x"] = msg.get("x", self.player["x"])
                self.player["y"] = msg.get("y", self.player["y"])
        elif t == "DUNGEON_COMPLETE":
            self._exit_dungeon_view()
            rewards = msg.get("rewards") or []
            names = []
            for r in rewards:
                it = ITEMS.get(r.get("item_id"), {})
                names.append(f"{r.get('qty', 1)}x {it.get('name', r.get('item_id'))}")
            if names:
                self.add_chat(
                    "Tidehollow conquered! Reward: " + ", ".join(names),
                    color=(255, 215, 90),
                    highlight=True,
                )
        elif t == "PLAYER_UPDATE":
            prev_boosts = (self.player or {}).get("stat_boosts") or {}
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
                    "gathering": self.player.get("gathering"),
                    "gender": self.player.get("gender") or "male",
                }
            self._announce_new_stat_boosts(prev_boosts, self.player.get("stat_boosts") or {})
            if self.combat_quick and time.time() < float(getattr(self, "combat_quick_until", 0) or 0):
                self.refresh_combat_quick_prompt(force=True)
        elif t == "CHAT_MSG":
            style = msg.get("style")
            text = f"{msg['from']}: {msg['text']}"
            if style == "gold":
                self.add_chat(text, color=(255, 215, 90), highlight=True)
            else:
                self.add_chat(text)
            body = (msg.get("text") or "").lower()
            if "arrow" in body or "too far" in body or "equip" in body:
                self._maybe_combat_floater(msg.get("text") or "")
        elif t == "WISH_STAT_CHOICE":
            self.wish_stat_choice = {
                "skills": msg.get("skills") or ["attack", "strength", "defence", "hitpoints"],
                "message": msg.get("message") or "Choose a skill to raise.",
            }
            self.show_wish = False
        elif t == "WISH_RESULT":
            self.show_wish = False
            if msg.get("text"):
                self.add_chat(msg["text"])
        elif t == "WELL_RARE":
            self.well_fx = {
                "x": msg.get("x", 24), "y": msg.get("y", 18),
                "until": time.time() + 2.8,
                "kind": msg.get("kind") or "rare",
            }
            if msg.get("text"):
                self.add_chat(msg["text"])
        elif t == "COMBAT_EVENT":
            self.handle_combat_event(msg)
        elif t == "DEATH":
            if msg["entity_kind"] == "player" and msg["entity_id"] == (self.player or {}).get("id"):
                lost = int(msg.get("coins_lost") or 0)
                if lost:
                    text = f"You died and lost {lost} coins."
                else:
                    text = "You have died and respawned in the village."
                self.add_chat(f"*** {text} ***", color=(255, 120, 100), highlight=True)
                self.death_banner_until = time.time() + 4.0
                self.death_banner_text = text
                self.clear_walk()
                self.combat_target_id = None
                if self.player:
                    self.player["coins"] = 0
        elif t == "LOOT_DROPPED":
            # Brief kill-loot feedback at the corpse (vacuum may already take it)
            lx = msg.get("x")
            ly = msg.get("y")
            items = msg.get("items") or []
            if lx is not None and ly is not None and items:
                names = []
                for entry in items[:4]:
                    if isinstance(entry, dict):
                        iid = entry.get("item_id") or entry.get("id")
                        qty = int(entry.get("qty") or entry.get("quantity") or 1)
                    elif isinstance(entry, (list, tuple)) and len(entry) >= 2:
                        iid, qty = entry[0], int(entry[1])
                    else:
                        continue
                    label = ITEMS.get(iid, {}).get("name", str(iid).replace("_", " ").title())
                    names.append(label if qty <= 1 else f"{label} x{qty}")
                if names:
                    text = ", ".join(names)
                    if len(items) > 4:
                        text += "…"
                    self.floaters.append({
                        "x": lx, "y": ly,
                        "text": text,
                        "color": (255, 230, 140),
                        "expire": time.time() + 2.2,
                        "kind": "loot",
                    })
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
                skill_name = skill.replace("_", " ").title()
                if gained > 0:
                    if self.show_xp:
                        px, py = self.player["x"], self.player["y"]
                        # Slight stagger so multi-skill ticks don't stack perfectly
                        jitter = (hash((skill, total)) % 7) * 0.04
                        self.floaters.append({
                            "x": px, "y": py,
                            "text": f"+{gained} {skill_name}",
                            "color": (180, 220, 255),
                            "expire": time.time() + 1.6 + jitter,
                            "kind": "xp",
                        })
                    else:
                        self.add_chat(f"You gained {gained} {skill_name} XP.")
                if msg.get("leveled_up"):
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
            qid = msg.get("quest_id") or ""
            title = qid.replace("_", " ").title() or "Quest"
            qp = int(msg.get("quest_points") or 0)
            rewards = msg.get("rewards") or {}
            self.add_chat(f"Quest complete: {title}!", color=(255, 220, 90), highlight=True)
            if qp:
                self.add_chat(
                    f"+{qp} quest point{'s' if qp != 1 else ''}.",
                    color=(200, 230, 255),
                )
            # Reward summary in chat
            bits = []
            if rewards.get("coins"):
                bits.append(f"{rewards['coins']} coins")
            for skill, amount in (rewards.get("xp") or {}).items():
                bits.append(f"{amount} {skill.replace('_', ' ').title()} XP")
            if rewards.get("item"):
                iid, qty = rewards["item"]
                bits.append(f"{qty}x {ITEMS.get(iid, {}).get('name', iid)}")
            for iid, qty in (rewards.get("items") or []):
                bits.append(f"{qty}x {ITEMS.get(iid, {}).get('name', iid)}")
            if bits:
                self.add_chat("Rewards: " + ", ".join(bits), color=(180, 255, 180))
            # Celebrate like a level-up
            self.level_up_until = time.time() + 3.4
            self.level_up_label = f"Quest Complete! {title}"
            if self.player:
                px, py = self.player["x"], self.player["y"]
                self.floaters.append({
                    "x": px, "y": py,
                    "text": "Quest Complete!",
                    "color": (255, 220, 90),
                    "expire": time.time() + 3.0,
                    "kind": "level_up",
                })
                if qp:
                    self.floaters.append({
                        "x": px, "y": py,
                        "text": f"+{qp} QP",
                        "color": (160, 210, 255),
                        "expire": time.time() + 2.4,
                        "kind": "xp",
                    })
        elif t == "MAGIC_CAST":
            self.handle_magic_cast(msg)
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
            text = msg.get("message") or "Something went wrong."
            self.add_chat(f"[!] {text}", color=(255, 140, 100), highlight=True)
            self._maybe_combat_floater(text)
            if self.state == "STAT_ALLOC":
                self.stat_alloc_error = text
                self.login_error = text

    def handle_combat_event(self, msg):
        kind = msg.get("kind", "")
        did_hit = msg.get("hit")
        if did_hit is None:
            did_hit = msg.get("damage", 0) > 0

        # Resolve attacker / defender world positions for facing + splat placement
        def entity_xy(eid, prefer_player=False):
            if prefer_player or (self.player and eid == self.player.get("id")):
                if self.player and eid == self.player.get("id"):
                    return self.player["x"], self.player["y"]
            if eid in self.players:
                p = self.players[eid]
                return p["x"], p["y"]
            if eid in self.monsters:
                m = self.monsters[eid]
                return m["x"], m["y"]
            return None, None

        def_id = msg.get("defender_id")
        atk_id = msg.get("attacker_id")
        x = y = None
        if kind == "monster_hits_player":
            x, y = entity_xy(def_id, prefer_player=True)
        elif kind in ("player_hits_monster", "pet_hits_monster"):
            x, y = entity_xy(def_id)
        else:
            x, y = entity_xy(def_id, prefer_player=True)
            if x is None:
                x, y = entity_xy(def_id)

        ax, ay = entity_xy(atk_id, prefer_player=(kind == "player_hits_monster"))
        if ax is None and kind == "pet_hits_monster":
            # attacker_id is "pet:<owner_id>" — resolve from live pet list
            for pet in self.pets:
                if f"pet:{pet.get('owner_id')}" == atk_id:
                    ax, ay = pet["x"], pet["y"]
                    break

        now = time.time()
        anim_key = atk_id
        ranged = bool(msg.get("ranged"))
        anim_secs = self.RANGED_ANIM_SECS if ranged else self.ATTACK_ANIM_SECS
        self.attack_anims[anim_key] = now + anim_secs
        self.attack_anim_kind[anim_key] = "ranged" if ranged else "melee"
        # Track current combat target for the local player
        my_id = (self.player or {}).get("id")
        if kind == "player_hits_monster" and atk_id == my_id:
            self.combat_target_id = def_id
        elif kind == "monster_hits_player" and def_id == my_id:
            self.combat_target_id = atk_id
            self.refresh_combat_quick_prompt(force=True)
        # Face the defender sideways (±1) — never front/back during a swing
        if ax is not None and ay is not None and x is not None and y is not None:
            self.attack_face[anim_key] = self.face_toward_target(ax, ay, x, y, key=anim_key)
            if atk_id == my_id:
                pkey = ("p", my_id)
                self._entity_facing[pkey] = self.attack_face[anim_key]
                if x == ax and not self.player_using_bow():
                    self._maybe_flank_combat_target()
            elif def_id == my_id and kind == "monster_hits_player":
                pkey = ("p", my_id)
                self.attack_face[anim_key] = self.face_toward_target(
                    (self.player or {}).get("x", ax), (self.player or {}).get("y", ay),
                    ax, ay, key=pkey,
                )
                self._entity_facing[pkey] = self.attack_face[anim_key]

        if ranged and ax is not None and x is not None and ay is not None and y is not None:
            # Arrow leaves near release (~58% of draw) and arrives with the splat
            flight = 0.32
            self.projectiles.append({
                "ax": ax, "ay": ay, "tx": x, "ty": y,
                "start": now + anim_secs * 0.55,
                "dur": flight,
            })

        if x is not None:
            if msg.get("dodged"):
                text = "DODGE"
                splat = "hit_dodge"
                color = (120, 220, 140)
                if kind == "monster_hits_player" and self.player and def_id == self.player["id"]:
                    self.add_chat("You dodge the attack!", color=(120, 220, 140))
            elif not did_hit:
                text = "MISS"
                splat = "hit_miss"
                color = (90, 180, 255)
                if kind == "monster_hits_player" and self.player and def_id == self.player["id"]:
                    self.add_chat("The monster missed!")
            else:
                dmg = int(msg.get("damage") or 0)
                if msg.get("crit") and kind in ("player_hits_monster", "pet_hits_monster"):
                    text = f"CRIT {dmg}"
                    splat = "hit_crit"
                    color = (255, 220, 70)
                elif kind in ("player_hits_monster", "pet_hits_monster"):
                    text = str(dmg)
                    splat = "hit_red"
                    color = (255, 70, 55)
                elif kind == "monster_hits_player":
                    text = str(dmg)
                    splat = "hit_blue"
                    color = (70, 160, 255)
                else:
                    text = str(dmg)
                    splat = "hit_red"
                    color = (255, 70, 55)
            # Show splat on the strike / arrow-impact frame
            strike_t = 0.58 if ranged else 0.48
            self.pending_floaters.append({
                "x": x, "y": y, "text": text,
                "color": color, "kind": splat,
                "show_at": now + anim_secs * strike_t,
            })
            # Lifesteal heal floater on the player
            ls = int(msg.get("lifesteal") or 0)
            if ls > 0 and self.player:
                self.pending_floaters.append({
                    "x": self.player["x"], "y": self.player["y"],
                    "text": f"+{ls}",
                    "color": (90, 230, 120), "kind": "heal",
                    "show_at": now + anim_secs * strike_t + 0.05,
                })
            # Thorns reflect splat on the monster
            thorns = int(msg.get("thorns") or 0)
            tid = msg.get("thorns_target")
            if thorns > 0 and tid is not None:
                tx, ty = entity_xy(tid)
                if tx is not None:
                    self.pending_floaters.append({
                        "x": tx, "y": ty,
                        "text": str(thorns),
                        "color": (255, 160, 60), "kind": "hit_thorns",
                        "show_at": now + anim_secs * 0.55,
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
        if self.show_bank or self.show_forge or self.show_cook or self.show_equipment or self.show_help or self.show_shop_panel or self.show_skills or self.show_pets or self.show_travel or self.fire_prompt or self.drop_prompt or self.arrow_prompt or self.tip_prompt or self.food_prompt or self.raw_prompt or self.food_bag_prompt or self.pack_prompt or self.log_prompt or self.potion_prompt or self.cook_prompt or self.combat_style_prompt:
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
        self._login_ui_geom_cache = None  # login/register mockups differ in size
        if mode == "login" and self.active_field == "char_name":
            self.active_field = "username"

    def login_layout(self):
        """Hitboxes mapped onto login_ui.png / login_ui_register.png mockups."""
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
            field_x -= 22
            user_y = R(0, pad + 214, 1, 1).y - 2   # username sits a bit higher than the others
            pass_y = R(0, pad + 298, 1, 1).y + 8
            char_y = R(0, pad + 400, 1, 1).y + 8
            user_text_dx = -26  # extra left shift for typed text
            pass_text_dx = -18
            char_text_dx = -18
            # Full ornate gender buttons (match baked female-selected crops)
            male_btn = R(205, pad + 478, 295, 52)
            female_btn = R(500, pad + 478, 315, 52)
            submit = R(190, pad + 560, 640, 42)
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
            submit = R(160, 632, 700, 48)
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
        hit = rect.inflate(pad_x * 2, pad_y * 2)
        hit.clamp_ip(pygame.Rect(0, 0, SCREEN_W, SCREEN_H))
        return hit

    def _register_title_pad(self):
        """Virtual top padding (source px) so the full logo sits on the scenic backdrop."""
        return 110

    def _login_ui_geom(self):
        """Scale/letterbox the active mockup to the window; map image px → screen."""
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
        """Load login or register mockup art for the current mode/gender."""
        mode = getattr(self, "login_mode", "login")
        if mode == "register" and getattr(self, "register_gender", "male") == "female":
            return self._register_ui_female_selected()
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
        setattr(self, attr, img)
        return img

    def _register_ui_female_selected(self):
        """
        Bake Female-selected into the register mockup: Female gets the same ornate
        green selected chrome as Male; Male gets the dark idle chrome.
        """
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
        """Full MYTHOSCAPE logo with transparent background (no dark plate)."""
        cached = getattr(self, "_login_title_overlay", None)
        if cached is not None:
            return cached
        path = os.path.join(_HERE, "assets", "login_title_overlay.png")
        try:
            overlay = pygame.image.load(path).convert_alpha()
        except Exception:
            overlay = None
        self._login_title_overlay = overlay
        return overlay

    def _login_chrome(self, key):
        """Crop reusable widgets from the login mockup (source px), cached."""
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
            # Use the same rects as the visible controls (no inflate / Y-nudge hacks).
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
            if lay["submit"].collidepoint(mx, my):
                self.submit_login()
                return
            # Generous padded hit target for HiScores (visual button is easy to miss)
            hs = self._login_hit(lay["hiscores"], 28, 22)
            if hs.collidepoint(mx, my):
                self.request_leaderboard()
                return
            if self.login_mode == "register":
                # Padded click targets aligned to the visible gender buttons
                if self._login_hit(lay["male_btn"], 16, 14).collidepoint(mx, my):
                    self.register_gender = "male"
                    return
                if self._login_hit(lay["female_btn"], 16, 14).collidepoint(mx, my):
                    self.register_gender = "female"
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
        # Open immediately so the button feels responsive; rows fill in when the
        # server replies (or show the empty state if offline / no players yet).
        self.show_leaderboard = True
        try:
            self.net.send("LEADERBOARD", limit=5)
        except Exception:
            pass

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
            self.net.send("CREATE_CHARACTER", username=u, password=p, char_name=c,
                          gender=self.register_gender)
        else:
            self.net.send("LOGIN", username=u, password=p)

    def handle_game_event(self, event):
        if event.type == pygame.KEYDOWN:
            if self.chat_typing:
                self.handle_chat_typing(event)
                return
            # Leave private dungeon before other Esc handlers eat the key
            if event.key == pygame.K_ESCAPE and self.dungeon and not (
                self.trade_incoming or self.trade_state
                or self.show_forge or self.show_equipment or self.show_help
                or self.show_bank or self.show_shop_panel or self.show_skills
                or self.show_pets or self.show_travel or self.show_world_map or self.show_cook
                or self.fire_prompt or self.drop_prompt or self.arrow_prompt or self.tip_prompt
                or self.food_prompt or self.raw_prompt or self.food_bag_prompt or self.pack_prompt
                or self.log_prompt or self.potion_prompt or self.cook_prompt
                or self.dungeon_prompt or self.combat_style_prompt or self.show_wish
                or self.wish_stat_choice
            ):
                self.clear_walk()
                self.net.send("LEAVE_DUNGEON")
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
            if self.show_shop_panel:
                if event.key == pygame.K_ESCAPE:
                    self.show_shop_panel = False
                    self.shop = None
                return
            if self.show_forge or self.show_cook or self.show_fletch or self.show_equipment or self.show_help or self.show_skills or self.show_pets or self.show_travel or self.show_world_map or self.fire_prompt or self.drop_prompt or self.arrow_prompt or self.tip_prompt or self.food_prompt or self.raw_prompt or self.food_bag_prompt or self.pack_prompt or self.log_prompt or self.potion_prompt or self.cook_prompt or self.dungeon_prompt or self.show_wish or self.wish_stat_choice or self.combat_style_prompt:
                if event.key == pygame.K_ESCAPE:
                    self.show_forge = False
                    self.show_cook = False
                    self.show_fletch = False
                    self.show_equipment = False
                    self.show_help = False
                    self.show_skills = False
                    self.show_pets = False
                    self.show_travel = False
                    self.show_world_map = False
                    self.fire_prompt = None
                    self.drop_prompt = None
                    self.arrow_prompt = None
                    self.tip_prompt = None
                    self.food_prompt = None
                    self.raw_prompt = None
                    self.food_bag_prompt = None
                    self.storage_bag_prompt = None
                    self.pack_prompt = None
                    self.log_prompt = None
                    self.potion_prompt = None
                    self.cook_prompt = None
                    self.dungeon_prompt = None
                    self.show_wish = False
                    self.wish_stat_choice = None
                    self.combat_style_prompt = None
                elif self.combat_style_prompt and event.key in (
                    pygame.K_1, pygame.K_2, pygame.K_3, pygame.K_4, pygame.K_5,
                ):
                    styles = ("attack", "strength", "defence", "hitpoints", "archery")
                    style = styles[event.key - pygame.K_1]
                    if self.player_using_bow():
                        if style == "archery":
                            self.confirm_combat_style(style)
                    elif style != "archery":
                        self.confirm_combat_style(style)
                elif event.key == pygame.K_m:
                    self.toggle_travel_modal()
                elif event.key == pygame.K_h:
                    self.show_help = not self.show_help
                    if self.show_help:
                        self.help_scroll = 0
                        self.show_forge = False
                        self.show_cook = False
                        self.show_equipment = False
                        self.show_skills = False
                        self.show_pets = False
                        self.show_travel = False
                        self.show_world_map = False
                elif self.show_help and event.key in (
                    pygame.K_UP, pygame.K_DOWN, pygame.K_PAGEUP, pygame.K_PAGEDOWN,
                ):
                    step = 28
                    meta = self.help_scroll_meta or {}
                    max_scroll = float(meta.get("max_scroll", 9999))
                    if event.key == pygame.K_UP:
                        self.help_scroll = max(0, self.help_scroll - step)
                    elif event.key == pygame.K_DOWN:
                        self.help_scroll = min(max_scroll, self.help_scroll + step)
                    elif event.key == pygame.K_PAGEUP:
                        self.help_scroll = max(0, self.help_scroll - step * 8)
                    else:
                        self.help_scroll = min(max_scroll, self.help_scroll + step * 8)
                elif self.show_skills and event.key in (
                    pygame.K_UP, pygame.K_DOWN, pygame.K_PAGEUP, pygame.K_PAGEDOWN,
                ):
                    step = 42
                    meta = self.skills_scroll_meta or {}
                    max_scroll = float(meta.get("max_scroll", 9999))
                    if event.key == pygame.K_UP:
                        self.skills_scroll = max(0, self.skills_scroll - step)
                    elif event.key == pygame.K_DOWN:
                        self.skills_scroll = min(max_scroll, self.skills_scroll + step)
                    elif event.key == pygame.K_PAGEUP:
                        self.skills_scroll = max(0, self.skills_scroll - step * 5)
                    else:
                        self.skills_scroll = min(max_scroll, self.skills_scroll + step * 5)
                elif self.show_travel and event.key in (
                    pygame.K_UP, pygame.K_DOWN, pygame.K_PAGEUP, pygame.K_PAGEDOWN,
                ):
                    step = 48
                    meta = self.travel_scroll_meta or {}
                    max_scroll = float(meta.get("max_scroll", 9999))
                    if event.key == pygame.K_UP:
                        self.travel_scroll = max(0, self.travel_scroll - step)
                    elif event.key == pygame.K_DOWN:
                        self.travel_scroll = min(max_scroll, self.travel_scroll + step)
                    elif event.key == pygame.K_PAGEUP:
                        self.travel_scroll = max(0, self.travel_scroll - step * 5)
                    else:
                        self.travel_scroll = min(max_scroll, self.travel_scroll + step * 5)
                elif event.key == pygame.K_e:
                    self.show_equipment = not self.show_equipment
                    if self.show_equipment:
                        self.show_forge = False
                        self.show_cook = False
                        self.show_help = False
                        self.show_skills = False
                        self.show_pets = False
                        self.show_travel = False
                        self.show_world_map = False
                elif event.key == pygame.K_f:
                    self.show_forge = not self.show_forge
                    if self.show_forge:
                        self.show_equipment = False
                        self.show_cook = False
                        self.show_help = False
                        self.show_skills = False
                        self.show_pets = False
                        self.show_travel = False
                        self.show_world_map = False
                elif event.key == pygame.K_c:
                    self.show_cook = False
                elif event.key == K_TAB:
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
            elif self.show_skills and event.key in (pygame.K_UP, pygame.K_DOWN, pygame.K_PAGEUP, pygame.K_PAGEDOWN):
                step = 42
                meta = self.skills_scroll_meta or {}
                max_scroll = float(meta.get("max_scroll", 9999))
                if event.key == pygame.K_UP:
                    self.skills_scroll = max(0, self.skills_scroll - step)
                elif event.key == pygame.K_DOWN:
                    self.skills_scroll = min(max_scroll, self.skills_scroll + step)
                elif event.key == pygame.K_PAGEUP:
                    self.skills_scroll = max(0, self.skills_scroll - step * 5)
                else:
                    self.skills_scroll = min(max_scroll, self.skills_scroll + step * 5)
            elif event.key == pygame.K_UP:
                self.clear_walk()
                dx, dy = self.rotate_move_delta(0, -1)
                self.try_move(dx, dy)
            elif event.key == pygame.K_DOWN:
                self.clear_walk()
                dx, dy = self.rotate_move_delta(0, 1)
                self.try_move(dx, dy)
            elif event.key == pygame.K_LEFT:
                self.clear_walk()
                dx, dy = self.rotate_move_delta(-1, 0)
                self.try_move(dx, dy)
            elif event.key == pygame.K_RIGHT:
                self.clear_walk()
                dx, dy = self.rotate_move_delta(1, 0)
                self.try_move(dx, dy)
            elif event.key in (pygame.K_LEFTBRACKET, pygame.K_COMMA):
                self.rotate_camera(-1)
                self.add_chat(f"Camera · facing {self.yaw_label()}  ([ ] or middle-click)", color=(200, 220, 255))
            elif event.key in (pygame.K_RIGHTBRACKET, pygame.K_PERIOD):
                self.rotate_camera(1)
                self.add_chat(f"Camera · facing {self.yaw_label()}  ([ ] or middle-click)", color=(200, 220, 255))
            elif event.key == pygame.K_i:
                self.sidebar_tab = "inventory"
                self.show_inventory = True
            elif event.key == K_TAB:
                self.toggle_skills_modal()
            elif event.key == pygame.K_q:
                self.sidebar_tab = "quests"
                self.show_quests = True
            elif event.key == pygame.K_x:
                self.show_xp = not self.show_xp
                self.add_chat(
                    f"Floating XP {'ON' if self.show_xp else 'OFF'} (X)",
                    color=(180, 220, 255),
                )
            elif event.key == pygame.K_p:
                self.toggle_auto_pickup()
            elif event.key == pygame.K_m:
                self.toggle_travel_modal()
            elif event.key == pygame.K_b:
                self.try_open_bank()
            elif event.key == pygame.K_e:
                self.show_equipment = not self.show_equipment
                if self.show_equipment:
                    self.sidebar_tab = "combat"
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
            elif event.key == pygame.K_n:
                if self.show_fletch:
                    self.show_fletch = False
                else:
                    self.open_fletch()
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
                    self.help_scroll = 0
                    self.show_equipment = False
                    self.show_forge = False
                    self.show_cook = False
                    self.show_skills = False
            elif event.key == pygame.K_g:
                self.clear_walk()
                shift = bool(pygame.key.get_mods() & pygame.KMOD_SHIFT)
                if shift:
                    self.net.send("PICKUP", all=True)
                else:
                    self.net.send("PICKUP")
            elif event.key == pygame.K_r:
                self.try_eat_food()
            elif event.key == pygame.K_SPACE:
                self.try_attack_nearest()
            elif event.key in (pygame.K_1, pygame.K_2, pygame.K_3, pygame.K_4, pygame.K_5):
                styles = ("attack", "strength", "defence", "hitpoints", "archery")
                style = styles[event.key - pygame.K_1]
                if self.player_using_bow():
                    if style == "archery":
                        self.set_combat_style(style)
                elif style != "archery":
                    self.set_combat_style(style)
            elif event.key == pygame.K_ESCAPE:
                if self.dungeon and not (
                    self.show_forge or self.show_equipment or self.show_help
                    or self.show_bank or self.show_shop_panel or self.show_skills
                    or self.show_pets or self.show_travel or self.show_world_map or self.show_cook
                    or self.fire_prompt or self.drop_prompt or self.arrow_prompt or self.tip_prompt or self.food_prompt or self.raw_prompt or self.food_bag_prompt or self.pack_prompt or self.log_prompt or self.potion_prompt or self.cook_prompt
                    or self.dungeon_prompt or self.combat_style_prompt
                ):
                    self.clear_walk()
                    self.net.send("LEAVE_DUNGEON")
                    return
                self.show_forge = False
                self.show_equipment = False
                self.show_help = False
                self.show_bank = False
                self.combat_style_prompt = None
                self.show_shop_panel = False
                self.show_skills = False
                self.show_pets = False
                self.show_travel = False
                self.show_world_map = False
                self.show_cook = False
                self.fire_prompt = None
                self.drop_prompt = None
                self.arrow_prompt = None
                self.tip_prompt = None
                self.food_prompt = None
                self.raw_prompt = None
                self.food_bag_prompt = None
                self.storage_bag_prompt = None
                self.pack_prompt = None
                self.log_prompt = None
                self.potion_prompt = None
                self.cook_prompt = None
                self.combat_quick = None
                self.combat_quick_until = 0.0
                self.dungeon_prompt = None
                self.clear_walk()
        elif event.type == pygame.MOUSEWHEEL:
            if self.state == "GAME" and self.show_help:
                dy = getattr(event, "precise_y", None)
                if dy is None:
                    dy = float(event.y)
                meta = self.help_scroll_meta or {}
                max_scroll = float(meta.get("max_scroll", 9999))
                self.help_scroll = max(0, min(max_scroll, self.help_scroll - dy * 40))
            elif self.state == "GAME" and self.show_skills:
                # Prefer precise trackpad deltas; fall back to discrete notches
                dy = getattr(event, "precise_y", None)
                if dy is None:
                    dy = float(event.y)
                meta = self.skills_scroll_meta or {}
                max_scroll = float(meta.get("max_scroll", 9999))
                self.skills_scroll = max(0, min(max_scroll, self.skills_scroll - dy * 48))
            elif self.state == "GAME" and self.show_travel:
                dy = getattr(event, "precise_y", None)
                if dy is None:
                    dy = float(event.y)
                meta = self.travel_scroll_meta or {}
                max_scroll = float(meta.get("max_scroll", 9999))
                self.travel_scroll = max(0, min(max_scroll, self.travel_scroll - dy * 48))
            elif self.state == "GAME" and self.sidebar_tab == "quests":
                mx, my = pygame.mouse.get_pos()
                if mx >= SIDEBAR_X:
                    dy = getattr(event, "precise_y", None)
                    if dy is None:
                        dy = float(event.y)
                    meta = self.quests_scroll_meta or {}
                    max_scroll = float(meta.get("max_scroll", 9999))
                    self.quests_scroll = max(0, min(max_scroll, self.quests_scroll - dy * 40))
            elif self.state == "GAME" and self.show_shop_panel and self.shop:
                mx, my = pygame.mouse.get_pos()
                box = pygame.Rect(160, 70, 700, 520)
                if box.collidepoint(mx, my):
                    dy = getattr(event, "precise_y", None)
                    if dy is None:
                        dy = float(event.y)
                    mid_x = box.x + box.w // 2
                    meta = self.shop_scroll_meta or {}
                    if mx < mid_x:
                        max_s = float((meta.get("buy") or {}).get("max_scroll", 9999))
                        self.shop_buy_scroll = max(0, min(max_s, self.shop_buy_scroll - dy * 40))
                    else:
                        max_s = float((meta.get("sell") or {}).get("max_scroll", 9999))
                        self.shop_sell_scroll = max(0, min(max_s, self.shop_sell_scroll - dy * 40))
            elif self.state == "GAME" and self.show_world_map:
                # Pan the scrollable world map
                step = 4
                mods = pygame.key.get_mods()
                if mods & pygame.KMOD_SHIFT:
                    self.world_map_scroll[0] -= event.y * step
                else:
                    self.world_map_scroll[1] -= event.y * step
                self.clamp_world_map_scroll()
            elif self.state == "GAME" and self.show_bank:
                mx, my = pygame.mouse.get_pos()
                box = pygame.Rect(120, 50, 780, 560)
                mid_x = box.x + box.w // 2
                if box.collidepoint(mx, my):
                    if mx < mid_x:
                        self.bank_inv_scroll = max(0, self.bank_inv_scroll - event.y)
                    else:
                        self.bank_page = max(0, self.bank_page - event.y)
            elif self.state == "GAME":
                mx, my = pygame.mouse.get_pos()
                chat_box = pygame.Rect(0, MAP_H, MAP_W, SCREEN_H - MAP_H)
                if chat_box.collidepoint(mx, my):
                    max_off = max(0, len(self.chat_log) - self.CHAT_VISIBLE)
                    self.chat_scroll = max(0, min(max_off, self.chat_scroll + event.y))
        elif event.type == pygame.MOUSEBUTTONDOWN:
            # Legacy mouse-wheel buttons (4=up, 5=down)
            if self.state == "GAME" and self.show_help and event.button in (4, 5):
                meta = self.help_scroll_meta or {}
                max_scroll = float(meta.get("max_scroll", 9999))
                delta = -40 if event.button == 4 else 40
                self.help_scroll = max(0, min(max_scroll, self.help_scroll + delta))
            elif self.state == "GAME" and self.show_skills and event.button in (4, 5):
                meta = self.skills_scroll_meta or {}
                max_scroll = float(meta.get("max_scroll", 9999))
                delta = -48 if event.button == 4 else 48
                self.skills_scroll = max(0, min(max_scroll, self.skills_scroll + delta))
            elif self.state == "GAME" and self.show_travel and event.button in (4, 5):
                meta = self.travel_scroll_meta or {}
                max_scroll = float(meta.get("max_scroll", 9999))
                delta = -48 if event.button == 4 else 48
                self.travel_scroll = max(0, min(max_scroll, self.travel_scroll + delta))
            elif self.state == "GAME" and self.show_shop_panel and self.shop and event.button in (4, 5):
                mx, my = event.pos
                box = pygame.Rect(160, 70, 700, 520)
                if box.collidepoint(mx, my):
                    mid_x = box.x + box.w // 2
                    meta = self.shop_scroll_meta or {}
                    delta = -40 if event.button == 4 else 40
                    if mx < mid_x:
                        max_s = float((meta.get("buy") or {}).get("max_scroll", 9999))
                        self.shop_buy_scroll = max(0, min(max_s, self.shop_buy_scroll + delta))
                    else:
                        max_s = float((meta.get("sell") or {}).get("max_scroll", 9999))
                        self.shop_sell_scroll = max(0, min(max_s, self.shop_sell_scroll + delta))
            elif self.state == "GAME" and self.show_help and event.button == 1:
                if self._help_scrollbar_mousedown(event.pos):
                    pass
                else:
                    self.handle_mouse_click(event)
            elif self.state == "GAME" and self.show_skills and event.button == 1:
                if self._skills_scrollbar_mousedown(event.pos):
                    pass
                else:
                    self.handle_mouse_click(event)
            elif self.state == "GAME" and self.show_travel and event.button == 1:
                if self._travel_scrollbar_mousedown(event.pos):
                    pass
                else:
                    self.handle_mouse_click(event)
            elif self.state == "GAME" and self.show_shop_panel and self.shop and event.button == 1:
                if self._shop_scrollbar_mousedown(event.pos):
                    pass
                else:
                    self.handle_mouse_click(event)
            elif self.state == "GAME" and event.button == 2:
                # Middle mouse — start RS-style camera orbit drag on the map
                mx, my = event.pos
                if my < MAP_H and mx < MAP_W:
                    self.cam_drag = {
                        "ox": mx, "oy": my, "accum": 0.0,
                        "moved": False, "button": 2,
                    }
                else:
                    self.cam_drag = None
            elif self.state == "GAME" and event.button == 1 and self._inventory_drag_start(event.pos):
                pass
            else:
                self.handle_mouse_click(event)
        elif event.type == pygame.MOUSEMOTION:
            if self.cam_drag is not None:
                pressed = pygame.mouse.get_pressed(num_buttons=3)
                if pressed[1]:
                    mx, my = event.pos
                    dx = mx - self.cam_drag["ox"]
                    self.cam_drag["ox"] = mx
                    self.cam_drag["accum"] += dx
                    if abs(self.cam_drag["accum"]) > 8:
                        self.cam_drag["moved"] = True
                    thr = float(getattr(self, "_cam_drag_threshold", 56) or 56)
                    while self.cam_drag["accum"] >= thr:
                        self.cam_drag["accum"] -= thr
                        self.rotate_camera(1)
                    while self.cam_drag["accum"] <= -thr:
                        self.cam_drag["accum"] += thr
                        self.rotate_camera(-1)
                else:
                    self.cam_drag = None
            if self.help_drag is not None:
                self._help_scrollbar_drag(event.pos)
            elif self.skills_drag is not None:
                self._skills_scrollbar_drag(event.pos)
            elif self.travel_drag is not None:
                self._travel_scrollbar_drag(event.pos)
            elif self.shop_drag is not None:
                self._shop_scrollbar_drag(event.pos)
            elif self.inv_drag is not None:
                self.inv_drag["x"], self.inv_drag["y"] = event.pos
                if abs(event.pos[0] - self.inv_drag["ox"]) + abs(event.pos[1] - self.inv_drag["oy"]) > 6:
                    self.inv_drag["moved"] = True
        elif event.type == pygame.MOUSEBUTTONUP:
            if event.button == 2:
                # Click without drag = one step; drag already snapped while moving
                if self.cam_drag is not None and not self.cam_drag.get("moved"):
                    mods = pygame.key.get_mods()
                    self.rotate_camera(-1 if (mods & pygame.KMOD_SHIFT) else 1)
                self.cam_drag = None
            elif event.button == 1:
                if self.help_drag is not None:
                    self.help_drag = None
                elif self.skills_drag is not None:
                    self.skills_drag = None
                elif self.travel_drag is not None:
                    self.travel_drag = None
                elif self.shop_drag is not None:
                    self.shop_drag = None
                elif self.inv_drag is not None:
                    self._inventory_drag_end(event.pos)

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
        self.show_travel = False
        self.show_bank = False
        self.fire_prompt = None
        self.drop_prompt = None
        self.arrow_prompt = None
        self.tip_prompt = None
        self.food_prompt = None
        self.raw_prompt = None
        self.food_bag_prompt = None
        self.storage_bag_prompt = None
        self.pack_prompt = None
        self.log_prompt = None
        self.potion_prompt = None
        self.cook_prompt = None
        self.combat_style_prompt = None
        self.combat_style = "attack"
        self.combat_style_confirmed = False
        self.bank = None
        self.chat_typing = False
        self.chat_text = ""
        self.floaters = []
        self.attack_anims = {}
        self.attack_anim_kind = {}
        self.projectiles = []
        self.clear_walk()
        self._prev_entity_pos = {}
        self._entity_facing = {}
        self._entity_moving_until = {}
        self.active_field = "username"
        self._minimap_base = None
        self.minimap_rect = None
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

    def near_cave_entrance(self, px=None, py=None):
        if not self.player:
            return False
        if px is None or py is None:
            px, py = self.player_xy()
        for spot in self.interactables:
            if spot.get("kind") in ("cave_entrance", "volcano_entrance"):
                if max(abs(spot["x"] - px), abs(spot["y"] - py)) <= 1:
                    return True
        return False

    def near_dungeon_entrance(self, dungeon_id=None, px=None, py=None):
        """True when standing at a private-instance mouth (optionally matching id)."""
        if not self.player:
            return False
        if px is None or py is None:
            px, py = self.player_xy()
        for spot in self.interactables:
            if spot.get("kind") not in ("cave_entrance", "volcano_entrance"):
                continue
            if max(abs(spot["x"] - px), abs(spot["y"] - py)) > 1:
                continue
            if dungeon_id and spot.get("dungeon_id") and spot.get("dungeon_id") != dungeon_id:
                continue
            return True
        return False

    def open_cook(self):
        self.show_cook = True
        self.show_fletch = False
        self.show_forge = False
        self.show_equipment = False
        self.show_help = False
        self.show_skills = False

    def open_fletch(self):
        self.show_fletch = True
        self.show_cook = False
        self.show_forge = False
        self.show_equipment = False
        self.show_help = False
        self.show_skills = False

    def toggle_skills_modal(self):
        self.show_skills = not self.show_skills
        if self.show_skills:
            self.skills_scroll = 0
            self.show_forge = False
            self.show_cook = False
            self.show_fletch = False
            self.show_equipment = False
            self.show_help = False
            self.show_bank = False
            self.show_shop_panel = False
            self.show_pets = False
            self.show_travel = False

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
            self.show_travel = False

    def toggle_travel_modal(self):
        self.show_travel = not self.show_travel
        if self.show_travel:
            self.travel_scroll = 0
            self.travel_drag = None
            self.show_world_map = False
            self.show_forge = False
            self.show_cook = False
            self.show_equipment = False
            self.show_help = False
            self.show_bank = False
            self.show_shop_panel = False
            self.show_skills = False
            self.show_pets = False

    def toggle_world_map(self):
        """Open/close the scrollable world map (click-to-walk)."""
        if self.dungeon:
            self.chat_log.append("[!] Map travel is unavailable inside Tidehollow.")
            self.chat_log = self.chat_log[-8:]
            return
        self.show_world_map = not self.show_world_map
        if self.show_world_map:
            self.show_travel = False
            self.show_forge = False
            self.show_cook = False
            self.show_equipment = False
            self.show_help = False
            self.show_bank = False
            self.show_shop_panel = False
            self.show_skills = False
            self.show_pets = False
            # Centre the scroll viewport on the player
            scale = self.world_map_scale
            view_w = max(1, 700 // scale)
            view_h = max(1, 480 // scale)
            px, py = self.player_xy()
            self.world_map_scroll = [
                max(0, min(self.world_w - view_w, px - view_w // 2)),
                max(0, min(self.world_h - view_h, py - view_h // 2)),
            ]
            self.world_map_drag = None

    def travel_to_destination(self, dest):
        """Auto-walk to a travel destination (same style as B → bank)."""
        if not self.player or not dest:
            return
        tx, ty = int(dest["x"]), int(dest["y"])
        action = dest.get("action")
        # Prefer standing on the tile; else any adjacent walkable tile
        goals = set()
        if self.tile_walkable(tx, ty):
            goals.add((tx, ty))
        goals |= self.adjacent_goals(tx, ty)
        if not goals:
            self.chat_log.append(f"[!] Can't reach {dest.get('label', 'that')}.")
            self.chat_log = self.chat_log[-8:]
            return
        self.show_travel = False
        label = dest.get("label", "destination")
        self.chat_log.append(f"Walking to {label}...")
        self.chat_log = self.chat_log[-8:]
        self.walk_and_act(goals, action)

    def player_combat_level(self):
        if not self.player:
            return 1
        levels = self.player.get("levels") or {}
        return combat.combat_level(
            levels.get("attack", 1), levels.get("strength", 1),
            levels.get("defence", 1), levels.get("hitpoints", 10),
            levels.get("archery", 1),
        )

    def equipped_bow_range(self):
        eq = (self.player or {}).get("equipment") or {}
        wid = eq.get("weapon")
        if is_bow(wid):
            return bow_attack_range(wid)
        return 1

    def attack_range_goals(self, tx, ty):
        """Walkable tiles within bow/melee reach of target."""
        reach = self.equipped_bow_range()
        goals = set()
        for dx in range(-reach, reach + 1):
            for dy in range(-reach, reach + 1):
                if max(abs(dx), abs(dy)) > reach:
                    continue
                if dx == 0 and dy == 0:
                    continue
                nx, ny = tx + dx, ty + dy
                if self.tile_walkable(nx, ny):
                    goals.add((nx, ny))
        return goals

    def melee_flank_goals(self, tx, ty):
        """Prefer east/west of the foe so fights play in side profile."""
        goals = set()
        for dx in (1, -1):
            nx, ny = tx + dx, ty
            if self.tile_walkable(nx, ny):
                goals.add((nx, ny))
        if not goals:
            for dx, dy in ((1, -1), (1, 1), (-1, -1), (-1, 1)):
                nx, ny = tx + dx, ty + dy
                if self.tile_walkable(nx, ny):
                    goals.add((nx, ny))
        return goals if goals else self.adjacent_goals(tx, ty)

    def combat_approach_goals(self, tx, ty):
        """Melee: flank beside the foe. Ranged: any tile in bow reach."""
        if self.player_using_bow():
            return self.attack_range_goals(tx, ty)
        # Prefer side tiles, but accept any in-reach tile if flanks are blocked
        flanks = self.melee_flank_goals(tx, ty)
        reach = self.equipped_bow_range()
        if reach <= 1:
            return flanks
        return flanks | self.attack_range_goals(tx, ty)

    def face_toward_target(self, px, py, tx, ty, key=None):
        """Always ±1 side profile toward the target (never front/back in fights)."""
        dx = tx - px
        if dx > 0:
            face = 1
        elif dx < 0:
            face = -1
        else:
            face = 1
            if key is not None:
                prev = self._entity_facing.get(key, 1)
                if isinstance(prev, (int, float)) and prev not in (2, -2) and float(prev) < 0:
                    face = -1
        if key is not None:
            self._entity_facing[key] = face
        return face

    def _maybe_flank_combat_target(self):
        """If fighting directly above/below a foe, step beside them for a side fight."""
        if self.player_using_bow():
            return
        if self.walk_path or self.pending_action:
            return
        tid = self.combat_target_id
        if tid is None or not self.player:
            return
        m = self.monsters.get(tid)
        if not m or not m.get("alive"):
            return
        px, py = self.player_xy()
        mx, my = m["x"], m["y"]
        if max(abs(mx - px), abs(my - py)) > self.equipped_bow_range():
            return
        if mx != px:
            return  # already offset horizontally
        goals = self.melee_flank_goals(mx, my)
        path = self.find_path(px, py, goals)
        if path:
            self.walk_path = path

    def player_total_level(self):
        if not self.player:
            return 0
        levels = self.player.get("levels") or {}
        return sum(int(levels.get(s, 1)) for s in XP_SKILLS)

    def try_attack_nearest(self):
        """Space: attack in-range foe, or run into range of the nearest / current target."""
        if not self.player:
            return
        px, py = self.player_xy()

        best = None
        best_score = None
        # Prefer current combat target if still alive
        if self.combat_target_id is not None:
            ct = self.monsters.get(self.combat_target_id)
            if ct and ct.get("alive"):
                best = ct
        if best is None:
            for m in self.monsters.values():
                if not m["alive"]:
                    continue
                dist = max(abs(m["x"] - px), abs(m["y"] - py))
                score = (dist, m["id"])
                if best is None or score < best_score:
                    best = m
                    best_score = score
        if not best:
            return
        self.combat_target_id = best["id"]
        reach = self.equipped_bow_range()
        dist = max(abs(best["x"] - px), abs(best["y"] - py))
        if dist <= reach:
            self.clear_walk()
            self.begin_attack(best["id"])
        else:
            self.walk_and_act(self.combat_approach_goals(best["x"], best["y"]), {
                "type": "ATTACK", "target_id": best["id"],
            })

    def try_eat_food(self):
        """R: eat the strongest healing food in inventory (or food bag)."""
        if not self.player:
            return
        hp = int(self.player.get("hp") or 0)
        max_hp = max(1, int(self.player.get("max_hp") or 1))
        if hp >= max_hp:
            self.add_chat("You're already at full health.")
            return
        opts = self.combat_consumable_options()
        if opts.get("food"):
            self.net.send("QUICK_CONSUME", kind="food")
            return
        if opts.get("health"):
            self.net.send("QUICK_CONSUME", kind="health")
            return
        self.add_chat("You have no food to eat.")

    def _owned_item_qty(self, item_id):
        """Inventory + potion pouch counts from PLAYER_UPDATE."""
        n = 0
        for entry in ((self.player or {}).get("inventory") or {}).values():
            if entry and entry.get("item_id") == item_id:
                n += int(entry.get("qty") or 0)
        if is_potion_item(item_id) and (self.player or {}).get("has_potion_pouch"):
            pouch = (self.player or {}).get("potion_pouch") or {}
            n += int(pouch.get(item_id) or 0)
        return n

    def combat_consumable_options(self):
        """What combat quick-buttons can offer right now."""
        p = self.player or {}
        opts = {"food": False, "health": False, "attack": False, "strength": False, "defence": False}
        for entry in (p.get("inventory") or {}).values():
            if not entry:
                continue
            iid = entry.get("item_id") or ""
            it = ITEMS.get(iid) or {}
            if it.get("type") == "food" and iid != "health_potion" and int(it.get("heal") or 0) > 0:
                opts["food"] = True
            if iid == "health_potion":
                opts["health"] = True
            skill = it.get("boost_skill")
            if skill in opts and int(it.get("boost_amount") or 0) > 0:
                opts[skill] = True
        if int(p.get("food_bag_total") or 0) > 0 and p.get("has_food_bag"):
            opts["food"] = True
        pouch = p.get("potion_pouch") or {}
        if p.get("has_potion_pouch") and pouch:
            if int(pouch.get("health_potion") or 0) > 0:
                opts["health"] = True
            for iid, qty in pouch.items():
                if int(qty or 0) <= 0:
                    continue
                skill = (ITEMS.get(iid) or {}).get("boost_skill")
                if skill in ("attack", "strength", "defence"):
                    opts[skill] = True
        return opts

    def refresh_combat_quick_prompt(self, force=False):
        """Show above-head Eat / potion buttons when attacked (if supplies exist)."""
        if not self.player:
            return
        opts = self.combat_consumable_options()
        buttons = []
        if opts["food"]:
            buttons.append(("food", "Eat food"))
        if opts["health"]:
            buttons.append(("health", "HP potion"))
        if opts["attack"]:
            buttons.append(("attack", "Att pot"))
        if opts["strength"]:
            buttons.append(("strength", "Str pot"))
        if opts["defence"]:
            buttons.append(("defence", "Def pot"))
        if not buttons:
            # Nothing to offer — keep quiet rather than a useless prompt
            if force:
                self.combat_quick = None
            return
        # Prefer not to spam if already showing the same set
        prev = (self.combat_quick or {}).get("buttons")
        new_keys = [b[0] for b in buttons]
        if not force and prev == new_keys and time.time() < float(getattr(self, "combat_quick_until", 0) or 0):
            self.combat_quick_until = time.time() + 10.0
            return
        self.combat_quick = {"buttons": new_keys, "labels": {k: lab for k, lab in buttons}}
        self.combat_quick_until = time.time() + 10.0

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
            self.shop_buy_scroll = 0
            self.shop_sell_scroll = 0
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

    def handle_dialogue_click(self, mx, my):
        box = pygame.Rect(150, 450, MAP_W - 300, 230)
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
            elif action == "shop" and self.dialogue.get("shop_id"):
                self.show_shop_panel = True
                self.shop_buy_scroll = 0
                self.shop_sell_scroll = 0
                self.dialogue = None
            elif action == "bank" and self.dialogue.get("bank"):
                self.dialogue = None
                self.net.send("BANK_OPEN")
            elif action == "forge" and self.dialogue.get("forge"):
                self.dialogue = None
                self.open_forge_at()
            elif action == "close":
                self.dialogue = None
            return

    def _wrap_ui_text(self, text, font, max_w):
        words = (text or "").split()
        if not words:
            return [""]
        lines, cur = [], words[0]
        for w in words[1:]:
            trial = f"{cur} {w}"
            if font.size(trial)[0] <= max_w:
                cur = trial
            else:
                lines.append(cur)
                cur = w
        lines.append(cur)
        return lines

    def _count_player_item(self, item_id):
        """Inventory count for quest objective display (bags included via server status)."""
        total = 0
        inv = (self.player or {}).get("inventory") or {}
        for entry in inv.values():
            if entry and entry.get("item_id") == item_id:
                total += int(entry.get("qty") or 0)
        # Storage bags that hold quest mats
        bag_maps = (
            (self.player or {}).get("raw_bag") or {},
            (self.player or {}).get("mining_bag") or {},
            (self.player or {}).get("food_bag") or {},
            (self.player or {}).get("log_bag") or {},
            (self.player or {}).get("fletch_pouch") or {},
            (self.player or {}).get("gem_bag") or {},
        )
        for bag in bag_maps:
            if item_id in bag:
                total += int(bag.get(item_id) or 0)
        return total

    def _quest_objective_text(self, qid, info):
        qdef = QUESTS.get(qid) or {}
        status = (info or {}).get("status", "not_started")
        progress = int((info or {}).get("progress") or 0)
        if qdef.get("type") == "kill":
            name = (MONSTERS.get(qdef["target"]) or {}).get("name") or qdef["target"].replace("_", " ").title()
            need = int(qdef.get("count") or 0)
            cur = need if status in ("ready", "complete") else min(progress, need)
            return f"{cur}/{need} {name}"
        if qdef.get("type") == "collect":
            iid = qdef["target"]
            name = (ITEMS.get(iid) or {}).get("name", iid)
            need = int(qdef.get("count") or 0)
            have = self._count_player_item(iid)
            return f"{min(have, need)}/{need} {name}"
        if qdef.get("type") == "collect_multi":
            parts = []
            for iid, need in (qdef.get("targets") or {}).items():
                name = (ITEMS.get(iid) or {}).get("name", iid)
                have = self._count_player_item(iid)
                parts.append(f"{min(have, need)}/{need} {name}")
            return " · ".join(parts) if parts else qdef.get("description", "")
        if qdef.get("type") == "find_npc":
            npc = next((n for n in NPCS if n.get("id") == qdef.get("target")), None) or {}
            name = npc.get("name") or str(qdef.get("target", "?")).replace("_", " ").title()
            if status in ("ready", "complete"):
                return f"Spoke with {name}"
            return f"Find {name}"
        return qdef.get("description") or ""

    def _format_quest_rewards(self, qdef_or_rewards):
        """Short reward blurb for dialogue / journal."""
        if isinstance(qdef_or_rewards, dict) and "rewards" in qdef_or_rewards:
            rewards = qdef_or_rewards.get("rewards") or {}
            qp = int(qdef_or_rewards.get("quest_points") or 0)
        else:
            rewards = qdef_or_rewards or {}
            qp = 0
        bits = []
        if qp:
            bits.append(f"+{qp} QP")
        if rewards.get("coins"):
            bits.append(f"{rewards['coins']} coins")
        if rewards.get("xp"):
            for sk, amt in rewards["xp"].items():
                bits.append(f"+{amt} {sk.title()} XP")
        entries = []
        if rewards.get("item"):
            entries.append(rewards["item"])
        if rewards.get("items"):
            entries.extend(rewards["items"])
        for iid, qty in entries:
            name = (ITEMS.get(iid) or {}).get("name", iid)
            bits.append(f"{qty}x {name}" if qty != 1 else name)
        return " · ".join(bits) if bits else ""

    def _walk_to_quest_giver(self, qid):
        qdef = QUESTS.get(qid) or {}
        giver_id = qdef.get("giver")
        if not giver_id:
            return
        npc = next((n for n in NPCS if n.get("id") == giver_id), None)
        if not npc:
            return
        self.walk_and_act(self.adjacent_goals(npc["x"], npc["y"]), {
            "type": "TALK", "npc_id": npc["id"],
        })

    def try_move(self, dx, dy):
        if self.player:
            key = ("p", self.player.get("id"))
            if abs(dx) >= abs(dy) and dx != 0:
                self._entity_facing[key] = 1 if dx > 0 else -1
            elif dy != 0:
                self._entity_facing[key] = "back" if dy < 0 else "front"
            # Hold travel facing through inter-tile gaps so combat lock can't snap back
            self._entity_moving_until[key] = time.time() + 0.55
        self.net.send("MOVE", dx=dx, dy=dy)

    def _enter_dungeon_view(self, msg, advance=False):
        """Swap client map to the private Tidehollow floor tiles."""
        if not advance or self._overworld_tiles is None:
            self._overworld_tiles = [row[:] for row in self.tiles]
            self._overworld_size = (self.world_w, self.world_h)
        tiles = msg.get("tiles") or []
        self.tiles = tiles
        self.world_w = int(msg.get("width") or (len(tiles[0]) if tiles else 0))
        self.world_h = int(msg.get("height") or len(tiles))
        self.dungeon = {
            "id": msg.get("id", "tidehollow"),
            "floor": msg.get("floor", 1),
            "floors": msg.get("floors", 10),
            "label": msg.get("label", "Tidehollow"),
            "remaining": msg.get("remaining", 0),
            "exit_x": int(msg.get("exit_x", (msg.get("width") or 10) // 2)),
            "exit_y": int(msg.get("exit_y", (msg.get("height") or 14) - 1)),
        }
        self.monsters = {m["id"]: m for m in (msg.get("monsters") or [])}
        self.resources = {}
        self.ground_items = {}
        self.fires = set()
        self.npcs = []
        self.clear_walk()
        self._minimap_base = None
        if self.player:
            self.player["x"] = msg.get("player_x", self.player.get("x", 0))
            self.player["y"] = msg.get("player_y", self.player.get("y", 0))

    def _exit_dungeon_view(self):
        if self._overworld_tiles is not None:
            self.tiles = self._overworld_tiles
            if self._overworld_size:
                self.world_w, self.world_h = self._overworld_size
            self._overworld_tiles = None
            self._overworld_size = None
        self.dungeon = None
        self.clear_walk()
        self._minimap_base = None

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

    def _is_deep_pier_tile(self, x, y):
        """PATH out over the harbour bay — looks like standing in water."""
        if not self._is_pier_tile(x, y):
            return False
        water_n = 0
        for dx, dy in ((-1, 0), (1, 0), (0, -1), (0, 1)):
            nx, ny = x + dx, y + dy
            if 0 <= ny < len(self.tiles) and 0 <= nx < self.world_w:
                if self.tiles[ny][nx] == wm.WATER:
                    water_n += 1
        # Deep pier / end deck: water on multiple sides, or far east over the bay
        return water_n >= 2 or x >= 145

    def fishing_shore_goals(self, wx, wy):
        """Walkable land next to a water tile — never stand on WATER or deep pier."""
        goals = []
        for dx, dy in ((-1, 0), (1, 0), (0, -1), (0, 1)):
            nx, ny = wx + dx, wy + dy
            if not self.tile_walkable(nx, ny):
                continue
            if self.tiles[ny][nx] == wm.WATER:
                continue
            goals.append((nx, ny))
        if not goals:
            # Diagonals as last resort (still no water / deep pier)
            for dx, dy in ((-1, -1), (1, -1), (-1, 1), (1, 1)):
                nx, ny = wx + dx, wy + dy
                if self.tile_walkable(nx, ny) and self.tiles[ny][nx] != wm.WATER:
                    goals.append((nx, ny))
        shore = [g for g in goals if not self._is_deep_pier_tile(*g)]
        return set(shore or goals)

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
        # Cap search high enough for harbour / void / castle from spawn (~14k visits)
        limit = 50000
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
            reach = self.equipped_bow_range()
            return bool(m and m["alive"] and max(abs(m["x"] - px), abs(m["y"] - py)) <= reach)
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
        if kind == "WISH":
            return max(abs(action["x"] - px), abs(action["y"] - py)) <= 1
        if kind == "ENTER_DUNGEON":
            return self.near_dungeon_entrance(action.get("dungeon_id"), px, py)
        if kind == "LEAVE_DUNGEON":
            if not self.dungeon:
                return False
            ex = int(self.dungeon.get("exit_x", self.world_w // 2))
            ey = int(self.dungeon.get("exit_y", self.world_h - 1))
            return max(abs(ex - px), abs(ey - py)) <= 1
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
            self.begin_attack(action["target_id"])
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
        elif kind == "WISH":
            self.show_wish = True
        elif kind == "ENTER_DUNGEON":
            # Walk-then-enter: go straight in (no confirm popup)
            self.dungeon_prompt = None
            kwargs = {}
            if action.get("dungeon_id"):
                kwargs["dungeon_id"] = action["dungeon_id"]
            self.net.send("ENTER_DUNGEON", **kwargs)
        elif kind == "LEAVE_DUNGEON":
            self.clear_walk()
            self.net.send("LEAVE_DUNGEON")
        elif kind == "PICKUP":
            kwargs = {}
            if action.get("all"):
                kwargs["all"] = True
            self.net.send("PICKUP", **kwargs)

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

        # While melee-fighting directly N/S of a foe, step beside them
        self._maybe_flank_combat_target()

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
                goals = self.combat_approach_goals(m["x"], m["y"])
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
                goals = self.combat_approach_goals(m["x"], m["y"]) if m else set()
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
        # Face the step just taken (and hold it) so post-combat lock can't override
        pkey = ("p", self.player["id"])
        if abs(dx) >= abs(dy) and dx != 0:
            self._entity_facing[pkey] = 1 if dx > 0 else -1
        elif dy != 0:
            self._entity_facing[pkey] = "back" if dy < 0 else "front"
        self._entity_moving_until[pkey] = now + 0.55
        self._next_walk_at = now + 0.2

        if self.pending_action and self.can_do_action(self.pending_action, nx, ny):
            self.fire_action(self.pending_action)
            self.clear_walk()

    # -- mouse interaction on the map -----------------------------------
    def screen_to_tile(self, mx, my):
        """Map pixel → world tile (accounts for camera yaw)."""
        if not self.player:
            return None
        if mx < 0 or my < 0 or mx >= MAP_W or my >= MAP_H:
            return None
        cam_x, cam_y = self.camera_origin()
        vx = cam_x + mx // TILE
        vy = cam_y + my // TILE
        return self.view_to_world(vx, vy)

    def camera_origin(self):
        """Center the viewport on the player in *view* space, clamped."""
        px, py = self.player_xy()
        pvx, pvy = self.world_to_view(px, py)
        vis_w, vis_h = MAP_W // TILE, MAP_H // TILE
        vw, vh = self.view_size()
        max_cam_x = max(0, vw - vis_w)
        max_cam_y = max(0, vh - vis_h)
        cam_x = max(0, min(pvx - vis_w // 2, max_cam_x))
        cam_y = max(0, min(pvy - vis_h // 2, max_cam_y))
        return cam_x, cam_y

    def map_screen_pos(self, wx, wy, cam_x=None, cam_y=None):
        """World tile center → screen pixel (map viewport)."""
        if cam_x is None:
            cam_x, cam_y = self.camera_origin()
        vx, vy = self.world_to_view(wx, wy)
        return (
            (vx - cam_x) * TILE + TILE // 2,
            (vy - cam_y) * TILE + TILE // 2,
        )

    def map_screen_rect(self, wx, wy, cam_x=None, cam_y=None):
        if cam_x is None:
            cam_x, cam_y = self.camera_origin()
        vx, vy = self.world_to_view(wx, wy)
        return pygame.Rect((vx - cam_x) * TILE, (vy - cam_y) * TILE, TILE, TILE)

    def world_to_view_offset(self, wx, wy, cam_x, cam_y):
        """World tile → viewport tile offset (sx, sy)."""
        vx, vy = self.world_to_view(wx, wy)
        return vx - cam_x, vy - cam_y

    def handle_mouse_click(self, event):
        mx, my = event.pos
        # Leave dungeon button (always on top of the map HUD)
        if self.dungeon and self.dungeon_leave_rect and self.dungeon_leave_rect.collidepoint(mx, my):
            self.clear_walk()
            self.net.send("LEAVE_DUNGEON")
            return
        if self.dungeon_prompt:
            self.handle_dungeon_prompt_click(mx, my)
            return
        if self.drop_prompt:
            self.handle_drop_prompt_click(mx, my)
            return
        if self.arrow_prompt:
            self.handle_arrow_prompt_click(mx, my)
            return
        if self.tip_prompt:
            self.handle_tip_prompt_click(mx, my)
            return
        if self.food_prompt:
            self.handle_food_prompt_click(mx, my)
            return
        if self.raw_prompt:
            self.handle_raw_prompt_click(mx, my)
            return
        if self.food_bag_prompt:
            self.handle_food_bag_prompt_click(mx, my)
            return
        if self.storage_bag_prompt:
            self.handle_storage_bag_prompt_click(mx, my)
            return
        if self.pack_prompt:
            self.handle_pack_prompt_click(mx, my)
            return
        if self.log_prompt:
            self.handle_log_prompt_click(mx, my)
            return
        if self.potion_prompt:
            self.handle_potion_prompt_click(mx, my)
            return
        if self.cook_prompt:
            self.handle_cook_prompt_click(mx, my)
            return
        if self.combat_quick and time.time() < float(getattr(self, "combat_quick_until", 0) or 0):
            if self.handle_combat_quick_click(mx, my):
                return
        # Manual magic fight bar (below map)
        for aid, rect in (getattr(self, "magic_fight_rects", {}) or {}).items():
            if rect.collidepoint(mx, my):
                self.cast_magic_ability(aid)
                return
        if self.combat_style_prompt:
            self.handle_combat_style_prompt_click(mx, my)
            return
        if self.fire_prompt:
            self.handle_fire_prompt_click(mx, my)
            return
        if self.wish_stat_choice:
            self.handle_wish_stat_click(mx, my)
            return
        if self.show_wish:
            self.handle_wish_click(mx, my)
            return
        if self.show_world_map:
            self.handle_world_map_click(mx, my, event.button)
            return
        if self.show_bank:
            self.handle_bank_click(mx, my, event.button)
            return
        if self.show_forge:
            self.handle_forge_click(mx, my)
            return
        if self.show_cook:
            self.handle_cook_click(mx, my)
            return
        if self.show_fletch:
            self.handle_fletch_click(mx, my)
            return
        if self.show_skills:
            box = pygame.Rect(140, 30, 680, 660)
            if not box.collidepoint(mx, my):
                self.show_skills = False
            return
        if self.show_pets:
            self.handle_pets_click(mx, my)
            return
        if self.show_travel:
            self.handle_travel_click(mx, my)
            return
        if self.show_equipment:
            self.handle_equipment_click(mx, my)
            return
        if self.show_shop_panel and self.shop:
            self.handle_shop_click(mx, my, event.button)
            return
        if self.dialogue:
            self.handle_dialogue_click(mx, my)
            return
        if self.show_help:
            box = pygame.Rect(120, 30, 580, 640)
            if not box.collidepoint(mx, my):
                self.show_help = False
            return
        if self.minimap_rect and self.minimap_rect.collidepoint(mx, my):
            # Left-click walks; right-click opens the scrollable world map
            if event.button == 3:
                self.toggle_world_map()
            else:
                self.minimap_walk_click(mx, my)
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
        if self.dungeon:
            # Exit mouth on the south wall — click to leave
            ex = int((self.dungeon or {}).get("exit_x", self.world_w // 2))
            ey = int((self.dungeon or {}).get("exit_y", self.world_h - 1))
            if max(abs(tx - ex), abs(ty - ey)) <= 1:
                goals = self.adjacent_goals(ex, ey)
                if self.tile_walkable(ex, ey):
                    goals = set(goals) | {(ex, ey)}
                self.walk_and_act(goals, {"type": "LEAVE_DUNGEON"})
                return
            # Inside instance: only walk / attack / pickup (no overworld interactables)
            pass
        else:
            landmark = self.resolve_landmark_click(tx, ty)
            if landmark is not None:
                spot = landmark
                kind = spot.get("kind")
                lx, ly = spot["x"], spot["y"]
                if kind == "wishing_well":
                    goals = self.adjacent_goals(lx, ly)
                    if self.tile_walkable(lx, ly):
                        goals = set(goals) | {(lx, ly)}
                    self.walk_and_act(goals, {"type": "WISH", "x": lx, "y": ly})
                    return
                if kind in ("cave_entrance", "volcano_entrance"):
                    goals = self.adjacent_goals(lx, ly)
                    if self.tile_walkable(lx, ly):
                        goals = set(goals) | {(lx, ly)}
                    act = {"type": "ENTER_DUNGEON"}
                    if spot.get("dungeon_id"):
                        act["dungeon_id"] = spot["dungeon_id"]
                    self.walk_and_act(goals, act)
                    return
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
                    # wishing_well / cave_entrance handled via resolve_landmark_click

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
            shift = bool(pygame.key.get_mods() & pygame.KMOD_SHIFT)
            pickup = {"type": "PICKUP", "x": tx, "y": ty}
            if shift:
                pickup["all"] = True
            if self.tile_walkable(tx, ty):
                self.walk_and_act({(tx, ty)}, pickup)
            else:
                self.walk_and_act(self.adjacent_goals(tx, ty), pickup)
            return
        # monster?
        for m in self.monsters.values():
            if m["alive"] and m["x"] == tx and m["y"] == ty:
                self.walk_and_act(self.combat_approach_goals(m["x"], m["y"]), {
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
        # resource node (ores, trees, fishing) — trees draw tall so canopy clicks map north of trunk
        gather = self.resolve_gather_click(tx, ty)
        if gather is not None:
            gx, gy = gather
            rtype = self.resources.get(f"{gx},{gy}") or ""
            if "fishing" in str(rtype) or (
                0 <= gy < len(self.tiles) and 0 <= gx < self.world_w
                and self.tiles[gy][gx] == wm.WATER
            ):
                goals = self.fishing_shore_goals(gx, gy)
            else:
                goals = self.adjacent_goals(gx, gy)
            self.walk_and_act(goals, {"type": "GATHER", "x": gx, "y": gy})
            return
        # Click bare water: fish from true shore (never walk onto water / deep pier)
        if (0 <= ty < len(self.tiles) and 0 <= tx < self.world_w
                and self.tiles[ty][tx] == wm.WATER):
            key = f"{tx},{ty}"
            if key in self.resources or any(
                str(self.resources.get(f"{tx + dx},{ty + dy}") or "").startswith("fishing")
                for dx, dy in ((0, 0), (-1, 0), (1, 0), (0, -1), (0, 1))
            ):
                # Prefer exact water tile if it has a node; else nearest fish spot
                fx, fy = tx, ty
                if key not in self.resources:
                    for dx, dy in ((0, 0), (-1, 0), (1, 0), (0, -1), (0, 1)):
                        k2 = f"{tx + dx},{ty + dy}"
                        if str(self.resources.get(k2) or "").startswith("fishing"):
                            fx, fy = tx + dx, ty + dy
                            break
                self.walk_and_act(
                    self.fishing_shore_goals(fx, fy),
                    {"type": "GATHER", "x": fx, "y": fy},
                )
            else:
                # No fish here — just walk to the shore beside the click
                self.walk_and_act(self.fishing_shore_goals(tx, ty), None)
            return
        # Empty ground — walk there
        if self.tile_walkable(tx, ty):
            self.walk_and_act({(tx, ty)}, None)
            return

    def resolve_landmark_click(self, tx, ty):
        """Larger click footprint for tall/wide landmarks (well, cave mouth)."""
        best = None
        best_d = 99
        for spot in self.interactables:
            kind = spot.get("kind")
            if kind == "wishing_well":
                radius = 2
            elif kind in ("cave_entrance", "volcano_entrance"):
                radius = 2
            else:
                continue
            d = max(abs(spot["x"] - tx), abs(spot["y"] - ty))
            if d <= radius and d < best_d:
                best = spot
                best_d = d
        return best

    def resolve_gather_click(self, tx, ty):
        """Return (x, y) of a resource under the click, including tall tree canopies."""
        key = f"{tx},{ty}"
        if key in self.resources:
            rtype = self.resources[key]
            if rtype in ("tree", "oak_tree", "willow_tree", "maple_tree", "yew_tree", "magic_tree"):
                if self._tree_blocks_building(tx, ty):
                    pass
                else:
                    return tx, ty
            else:
                return tx, ty
        # Tree sprites tower several tiles above the trunk — click on foliage
        # lands on a tile north of the resource; search south for a trunk.
        for dy in range(1, 6):
            for dx in (0, -1, 1):
                nx, ny = tx + dx, ty + dy
                rtype = self.resources.get(f"{nx},{ny}")
                if rtype in ("tree", "oak_tree", "willow_tree", "maple_tree", "yew_tree", "magic_tree"):
                    if self._tree_blocks_building(nx, ny):
                        continue
                    return nx, ny
        return None

    def handle_sidebar_click(self, mx, my, button):
        if self.logout_btn_rect and self.logout_btn_rect.collidepoint(mx, my):
            self.logout()
            return
        if self.sidebar_settings_rect and self.sidebar_settings_rect.collidepoint(mx, my):
            self.show_help = not self.show_help
            if self.show_help:
                self.help_scroll = 0
                self.show_forge = False
                self.show_cook = False
                self.show_equipment = False
                self.show_skills = False
                self.show_pets = False
                self.show_travel = False
                self.show_world_map = False
            return
        if self.sidebar_bank_btn_rect and self.sidebar_bank_btn_rect.collidepoint(mx, my):
            self.try_open_bank()
            return
        if self.skills_btn_rect and self.skills_btn_rect.collidepoint(mx, my):
            self.toggle_skills_modal()
            return
        if self.skills_view_all_rect and self.skills_view_all_rect.collidepoint(mx, my):
            self.toggle_skills_modal()
            return
        if self.pets_btn_rect and self.pets_btn_rect.collidepoint(mx, my):
            self.toggle_pets_modal()
            return
        if self.auto_pickup_btn_rect and self.auto_pickup_btn_rect.collidepoint(mx, my):
            self.toggle_auto_pickup()
            return
        for key, rect in (self.sidebar_action_rects or {}).items():
            if rect.collidepoint(mx, my):
                if key == "travel":
                    self.toggle_travel_modal()
                elif key == "bank":
                    self.try_open_bank()
                elif key == "gear":
                    self.show_equipment = not self.show_equipment
                    if self.show_equipment:
                        self.show_forge = False
                        self.show_cook = False
                        self.show_help = False
                        self.show_skills = False
                        self.show_travel = False
                        self.show_pets = False
                        self.sidebar_tab = "combat"
                return
        for key, rect in (self.sidebar_tab_rects or {}).items():
            if rect.collidepoint(mx, my):
                self.sidebar_tab = key
                self.show_quests = key == "quests"
                self.show_inventory = key == "inventory"
                return
        if self.sidebar_tab == "inventory":
            for tab_i, rect in (self.inv_tab_rects or {}).items():
                if rect.collidepoint(mx, my):
                    self.inv_tab = int(tab_i)
                    return
        if self.trade_state:
            self.handle_trade_inventory_click(mx, my)
            return
        if self.sidebar_tab == "combat":
            for rect, style, _label in self.combat_style_button_rects():
                if rect.collidepoint(mx, my):
                    self.set_combat_style(style)
                    return
            # Click worn slot to unequip quickly
            for slot, rect in (getattr(self, "sidebar_equip_rects", {}) or {}).items():
                if rect.collidepoint(mx, my) and (self.player.get("equipment") or {}).get(slot):
                    self.net.send("UNEQUIP", equip_slot=slot)
                    return
        if self.sidebar_tab == "magic":
            if self.magic_mode_btn_rect and self.magic_mode_btn_rect.collidepoint(mx, my):
                self.toggle_magic_auto()
                return
            for aid, rect in (self.magic_btn_rects or {}).items():
                if rect.collidepoint(mx, my):
                    self.cast_magic_ability(aid)
                    return
        if self.sidebar_tab == "quests":
            for rect, qid in (self.quest_row_rects or []):
                if rect.collidepoint(mx, my):
                    self._walk_to_quest_giver(qid)
                    return
        if self.sidebar_tab == "inventory" and self.show_inventory:
            self.handle_inventory_click(mx, my, button)

    def player_using_bow(self):
        eq = (self.player or {}).get("equipment") or {}
        return is_bow(eq.get("weapon"))

    def handle_magic_cast(self, msg):
        """Visual feedback for a quest-magic cast."""
        effect = msg.get("effect") or "lightning"
        tid = msg.get("target_id")
        m = self.monsters.get(tid) if tid is not None else None
        if m:
            tx, ty = m["x"], m["y"]
        else:
            tx, ty = self.player_xy() if self.player else (0, 0)
        self.magic_fx.append({
            "x": tx, "y": ty,
            "effect": effect,
            "name": msg.get("name") or "Magic",
            "damage": int(msg.get("damage") or 0),
            "until": time.time() + 0.85,
        })
        # Refresh local cooldown from next PLAYER_UPDATE; optimistic ready_at
        magic = (self.player or {}).get("magic") or {}
        abilities = magic.get("abilities") or {}
        aid = msg.get("ability_id")
        if aid and aid in abilities:
            ab = abilities[aid]
            base = float(ab.get("cooldown") or 8)
            factor = float(magic.get("manual_cd_factor") or MANUAL_MAGIC_CD_FACTOR)
            cd = base * (factor if msg.get("manual") else 1.0)
            ab["ready_at"] = time.time() + cd
            ab["ready"] = False

    def cast_magic_ability(self, ability_id):
        self.net.send("CAST_MAGIC", ability_id=ability_id)

    def toggle_magic_auto(self):
        magic = (self.player or {}).get("magic") or {}
        auto = not bool(magic.get("auto", True))
        self.net.send("SET_MAGIC_MODE", auto=auto)

    def player_in_fight(self):
        if self.combat_target_id is not None:
            m = self.monsters.get(self.combat_target_id)
            if m and m.get("alive"):
                return True
        return False

    def set_combat_style(self, style):
        if self.player_using_bow():
            if style != "archery":
                return
        elif style == "archery":
            return
        self.combat_style = style
        self.combat_style_confirmed = True
        self.net.send("SET_COMBAT_STYLE", style=style)

    def begin_attack(self, target_id):
        """Start combat — prompt for XP skill on first melee attack this session."""
        if self.player_using_bow():
            self.combat_style = "archery"
            self.combat_style_confirmed = True
            self.net.send("SET_COMBAT_STYLE", style="archery")
            self.net.send("ATTACK", target_id=target_id)
            return
        if not self.combat_style_confirmed:
            self.combat_style_prompt = {"target_id": target_id}
            return
        self.net.send("ATTACK", target_id=target_id)

    def confirm_combat_style(self, style):
        """Pick XP skill from the first-attack popup, then attack."""
        if self.player_using_bow():
            if style != "archery":
                return
        elif style == "archery":
            return
        tid = (self.combat_style_prompt or {}).get("target_id")
        self.combat_style_prompt = None
        self.set_combat_style(style)
        if tid is not None:
            self.net.send("ATTACK", target_id=tid)

    def inventory_slot_rects(self):
        """Visible skill-tab slots (24). Keys are global slot indices."""
        rects = {}
        cols, rows = 4, 6  # INVENTORY_TAB_SIZE
        tab = max(0, min(len(INVENTORY_TABS) - 1, int(getattr(self, "inv_tab", 0) or 0)))
        base = tab * INVENTORY_TAB_SIZE
        ox = SIDEBAR_X + 16
        oy = getattr(self, "_inventory_oy", 348)
        bottom = getattr(self, "_inventory_bottom", SCREEN_H - 58)
        gap = 3
        avail = max(120, bottom - oy)
        size = min(56, max(40, (avail - (rows - 1) * gap) // rows))
        for local in range(cols * rows):
            col, row = local % cols, local // cols
            rects[base + local] = pygame.Rect(
                ox + col * (size + gap), oy + row * (size + gap), size, size,
            )
        return rects

    def combat_style_button_rects(self):
        """Combat style pills in one row (melee + archery)."""
        styles = ("attack", "strength", "defence", "hitpoints", "archery")
        labels = {
            "attack": "Att", "strength": "Str", "defence": "Def",
            "hitpoints": "HP", "archery": "Arch",
        }
        rects = []
        ox = SIDEBAR_X + 14
        oy = getattr(self, "_combat_style_oy", 268)
        gap = 4
        bw = max(40, (SCREEN_W - SIDEBAR_X - 28 - gap * 4) // 5)
        bh = 28
        for i, style in enumerate(styles):
            rect = pygame.Rect(ox + i * (bw + gap), oy, bw, bh)
            rects.append((rect, style, labels[style]))
        return rects

    def handle_inventory_click(self, mx, my, button):
        if not self.player:
            return
        shift = bool(pygame.key.get_mods() & pygame.KMOD_SHIFT)
        for slot, rect in self.inventory_slot_rects().items():
            if rect.collidepoint(mx, my):
                entry = self.player["inventory"].get(str(slot)) or self.player["inventory"].get(slot)
                if not entry:
                    return
                item = ITEMS[entry["item_id"]]
                item_id = entry["item_id"]
                is_arrow = item.get("ammo_type") == "arrow"
                is_tip = str(item_id).endswith("arrowtips")
                cooked = is_cooked_fish(item_id)
                raw = is_raw_fish(item_id)
                mining = is_mining_bag_item(item_id)
                logs = is_log_item(item_id)
                fletch_mat = is_fletch_pouch_item(item_id)
                potion = is_potion_item(item_id)
                gem = is_gem_item(item_id)
                bag_ids = (
                    "arrowtip_box", "food_bag", "raw_food_bag",
                    "mining_bag", "log_bag", "fletch_pouch", "potion_pouch",
                    "gem_bag",
                )
                if button == 3:  # right-click
                    if is_arrow:
                        self.open_arrow_prompt(slot, entry)
                    elif is_tip:
                        self.open_tip_prompt(slot, entry)
                    elif cooked:
                        self.open_food_prompt(slot, entry)
                    elif raw:
                        self.open_raw_prompt(slot, entry)
                    elif mining or fletch_mat or potion or gem:
                        self.open_pack_prompt(slot, entry)
                    elif logs:
                        self.open_log_prompt(slot, entry)
                    elif item.get("karma_xp"):
                        self.net.send("USE_ITEM", slot_index=slot)  # bury one
                    elif shift:
                        self.net.send("DROP", slot_index=slot, qty=max(1, int(entry.get("qty") or 1)))
                    else:
                        self.open_drop_prompt(slot, entry)
                elif is_arrow:
                    self.open_arrow_prompt(slot, entry)
                elif is_tip:
                    self.open_tip_prompt(slot, entry)
                elif cooked:
                    self.open_food_prompt(slot, entry)
                elif raw:
                    self.open_raw_prompt(slot, entry)
                elif potion:
                    self.open_potion_prompt(slot, entry)
                elif mining or fletch_mat or gem:
                    self.open_pack_prompt(slot, entry)
                elif logs:
                    self.open_log_prompt(slot, entry)
                elif item_id == "food_bag":
                    self.open_food_bag_prompt(slot, entry)
                elif item_id in bag_ids:
                    self.open_storage_bag_prompt(slot, entry)
                elif item.get("equip_slot"):
                    self.net.send("EQUIP", slot_index=slot)
                elif item["type"] == "food":
                    self.net.send("USE_ITEM", slot_index=slot)
                elif item.get("karma_xp"):
                    self.net.send("USE_ITEM", slot_index=slot)  # bury one
                elif entry["item_id"] == "knife" or item.get("tool_for") == "fletching":
                    self.open_fletch()
                elif entry["item_id"] in FIRE_LOGS or entry["item_id"] in FLETCH_LOGS:
                    # Prefer fletch if holding a knife; otherwise firemaking prompt
                    has_knife = any(
                        e and (e.get("item_id") == "knife" or ITEMS.get(e.get("item_id"), {}).get("tool_for") == "fletching")
                        for e in ((self.player or {}).get("inventory") or {}).values()
                    )
                    if has_knife and entry["item_id"] in FLETCH_LOGS:
                        self.open_fletch()
                    elif entry["item_id"] in FIRE_LOGS:
                        self.open_fire_prompt(slot, entry["item_id"])
                elif entry["item_id"] == "tinderbox":
                    self.open_fire_prompt_from_tinderbox()
                return

    def open_drop_prompt(self, slot, entry):
        item_id = entry["item_id"]
        name = ITEMS.get(item_id, {}).get("name", "item")
        qty = max(1, int(entry.get("qty") or 1))
        self.drop_prompt = {"slot": slot, "item_id": item_id, "name": name, "qty": qty}
        self.cook_prompt = None
        self.fire_prompt = None
        self.arrow_prompt = None
        self.tip_prompt = None
        self.food_prompt = None
        self.raw_prompt = None
        self.food_bag_prompt = None
        self.storage_bag_prompt = None
        self.pack_prompt = None
        self.log_prompt = None
        self.potion_prompt = None

    def open_arrow_prompt(self, slot, entry):
        item_id = entry["item_id"]
        name = ITEMS.get(item_id, {}).get("name", "arrows")
        qty = max(1, int(entry.get("qty") or 1))
        self.arrow_prompt = {"slot": slot, "item_id": item_id, "name": name, "qty": qty}
        self.drop_prompt = None
        self.tip_prompt = None
        self.food_prompt = None
        self.raw_prompt = None
        self.food_bag_prompt = None
        self.storage_bag_prompt = None
        self.pack_prompt = None
        self.log_prompt = None
        self.potion_prompt = None
        self.cook_prompt = None
        self.fire_prompt = None

    def open_tip_prompt(self, slot, entry):
        item_id = entry["item_id"]
        name = ITEMS.get(item_id, {}).get("name", "arrowtips")
        qty = max(1, int(entry.get("qty") or 1))
        self.tip_prompt = {"slot": slot, "item_id": item_id, "name": name, "qty": qty}
        self.drop_prompt = None
        self.arrow_prompt = None
        self.food_prompt = None
        self.raw_prompt = None
        self.food_bag_prompt = None
        self.storage_bag_prompt = None
        self.pack_prompt = None
        self.log_prompt = None
        self.potion_prompt = None
        self.cook_prompt = None
        self.fire_prompt = None

    def open_food_prompt(self, slot, entry):
        item_id = entry["item_id"]
        name = ITEMS.get(item_id, {}).get("name", "food")
        qty = max(1, int(entry.get("qty") or 1))
        self.food_prompt = {"slot": slot, "item_id": item_id, "name": name, "qty": qty}
        self.drop_prompt = None
        self.arrow_prompt = None
        self.tip_prompt = None
        self.raw_prompt = None
        self.food_bag_prompt = None
        self.storage_bag_prompt = None
        self.pack_prompt = None
        self.log_prompt = None
        self.potion_prompt = None
        self.cook_prompt = None
        self.fire_prompt = None

    def open_raw_prompt(self, slot, entry):
        item_id = entry["item_id"]
        name = ITEMS.get(item_id, {}).get("name", "raw fish")
        qty = max(1, int(entry.get("qty") or 1))
        self.raw_prompt = {"slot": slot, "item_id": item_id, "name": name, "qty": qty}
        self.drop_prompt = None
        self.arrow_prompt = None
        self.tip_prompt = None
        self.food_prompt = None
        self.food_bag_prompt = None
        self.storage_bag_prompt = None
        self.pack_prompt = None
        self.log_prompt = None
        self.potion_prompt = None
        self.cook_prompt = None
        self.fire_prompt = None

    def open_food_bag_prompt(self, slot, entry):
        self.food_bag_prompt = {"slot": slot, "item_id": "food_bag"}
        self.storage_bag_prompt = None
        self.drop_prompt = None
        self.arrow_prompt = None
        self.tip_prompt = None
        self.food_prompt = None
        self.raw_prompt = None
        self.pack_prompt = None
        self.log_prompt = None
        self.potion_prompt = None
        self.cook_prompt = None
        self.fire_prompt = None

    def open_storage_bag_prompt(self, slot, entry):
        item_id = entry["item_id"]
        labels = {
            "arrowtip_box": ("Tip Box", "tip_box_total", "has_tip_box"),
            "raw_food_bag": ("Raw Food Bag", "raw_bag_total", "has_raw_bag"),
            "mining_bag": ("Mining Bag", "mining_bag_total", "has_mining_bag"),
            "log_bag": ("Log Bag", "log_bag_total", "has_log_bag"),
            "fletch_pouch": ("Fletching Pouch", "fletch_pouch_total", "has_fletch_pouch"),
            "potion_pouch": ("Potion Pouch", "potion_pouch_total", "has_potion_pouch"),
            "gem_bag": ("Gem Bag", "gem_bag_total", "has_gem_bag"),
        }
        label, tot_key, flag = labels.get(item_id, ("Bag", None, None))
        tot = int((self.player or {}).get(tot_key) or 0) if tot_key else 0
        self.storage_bag_prompt = {
            "slot": slot, "item_id": item_id, "label": label, "total": tot,
        }
        self.food_bag_prompt = None
        self.drop_prompt = None
        self.arrow_prompt = None
        self.tip_prompt = None
        self.food_prompt = None
        self.raw_prompt = None
        self.pack_prompt = None
        self.log_prompt = None
        self.potion_prompt = None
        self.cook_prompt = None
        self.fire_prompt = None

    def open_pack_prompt(self, slot, entry):
        item_id = entry["item_id"]
        name = ITEMS.get(item_id, {}).get("name", "item")
        qty = max(1, int(entry.get("qty") or 1))
        if is_mining_bag_item(item_id):
            kind, bag_flag, bag_label, buy_hint = (
                "mining", "has_mining_bag", "Mining Bag",
                "Buy a Mining Bag from Gareth or the General Store.",
            )
        elif is_fletch_pouch_item(item_id):
            kind, bag_flag, bag_label, buy_hint = (
                "fletch", "has_fletch_pouch", "Fletching Pouch",
                "Buy a Fletching Pouch from Elena.",
            )
        elif is_gem_item(item_id):
            kind, bag_flag, bag_label, buy_hint = (
                "gem", "has_gem_bag", "Gem Bag",
                "Buy a Gem Bag from Lira or the General Store.",
            )
        else:
            kind, bag_flag, bag_label, buy_hint = (
                "pack", "has_mining_bag", "bag", "You need the matching bag first.",
            )
        self.pack_prompt = {
            "slot": slot, "item_id": item_id, "name": name, "qty": qty,
            "kind": kind, "bag_flag": bag_flag, "bag_label": bag_label, "buy_hint": buy_hint,
        }
        self.drop_prompt = None
        self.arrow_prompt = None
        self.tip_prompt = None
        self.food_prompt = None
        self.raw_prompt = None
        self.food_bag_prompt = None
        self.log_prompt = None
        self.potion_prompt = None
        self.cook_prompt = None
        self.fire_prompt = None

    def open_log_prompt(self, slot, entry):
        item_id = entry["item_id"]
        name = ITEMS.get(item_id, {}).get("name", "logs")
        qty = max(1, int(entry.get("qty") or 1))
        has_knife = any(
            e and (e.get("item_id") == "knife" or ITEMS.get(e.get("item_id"), {}).get("tool_for") == "fletching")
            for e in ((self.player or {}).get("inventory") or {}).values()
        )
        self.log_prompt = {
            "slot": slot, "item_id": item_id, "name": name, "qty": qty,
            "can_fletch": bool(has_knife and item_id in FLETCH_LOGS),
            "can_fire": item_id in FIRE_LOGS,
        }
        self.drop_prompt = None
        self.arrow_prompt = None
        self.tip_prompt = None
        self.food_prompt = None
        self.raw_prompt = None
        self.food_bag_prompt = None
        self.storage_bag_prompt = None
        self.pack_prompt = None
        self.potion_prompt = None
        self.cook_prompt = None
        self.fire_prompt = None

    def open_potion_prompt(self, slot, entry):
        item_id = entry["item_id"]
        name = ITEMS.get(item_id, {}).get("name", "potion")
        qty = max(1, int(entry.get("qty") or 1))
        self.potion_prompt = {"slot": slot, "item_id": item_id, "name": name, "qty": qty}
        self.drop_prompt = None
        self.arrow_prompt = None
        self.tip_prompt = None
        self.food_prompt = None
        self.raw_prompt = None
        self.food_bag_prompt = None
        self.storage_bag_prompt = None
        self.pack_prompt = None
        self.log_prompt = None
        self.cook_prompt = None
        self.fire_prompt = None

    def handle_drop_prompt_click(self, mx, my):
        rects = self.drop_prompt_rects
        box = rects.get("box")
        prompt = self.drop_prompt
        if not prompt:
            return
        if rects.get("one") and rects["one"].collidepoint(mx, my):
            self.net.send("DROP", slot_index=prompt["slot"], qty=1)
            self.drop_prompt = None
            return
        if rects.get("all") and rects["all"].collidepoint(mx, my):
            self.net.send("DROP", slot_index=prompt["slot"], qty=prompt["qty"])
            self.drop_prompt = None
            return
        if rects.get("cancel") and rects["cancel"].collidepoint(mx, my):
            self.drop_prompt = None
            return
        if box and not box.collidepoint(mx, my):
            self.drop_prompt = None

    def handle_arrow_prompt_click(self, mx, my):
        rects = self.arrow_prompt_rects
        box = rects.get("box")
        prompt = self.arrow_prompt
        if not prompt:
            return
        if rects.get("quiver") and rects["quiver"].collidepoint(mx, my):
            self.net.send("USE_ITEM", slot_index=prompt["slot"], action="pack")
            self.arrow_prompt = None
            return
        if rects.get("drop") and rects["drop"].collidepoint(mx, my):
            entry = {"item_id": prompt["item_id"], "qty": prompt["qty"]}
            self.open_drop_prompt(prompt["slot"], entry)
            return
        if rects.get("cancel") and rects["cancel"].collidepoint(mx, my):
            self.arrow_prompt = None
            return
        if box and not box.collidepoint(mx, my):
            self.arrow_prompt = None

    def handle_tip_prompt_click(self, mx, my):
        rects = self.tip_prompt_rects
        box = rects.get("box")
        prompt = self.tip_prompt
        if not prompt:
            return
        if rects.get("box_pack") and rects["box_pack"].collidepoint(mx, my):
            if not (self.player or {}).get("has_tip_box"):
                self.chat_log.append("[!] Buy an Arrowtip Box from Elena first.")
                self.chat_log = self.chat_log[-8:]
                return
            self.net.send("USE_ITEM", slot_index=prompt["slot"], action="pack")
            self.tip_prompt = None
            return
        if rects.get("drop") and rects["drop"].collidepoint(mx, my):
            entry = {"item_id": prompt["item_id"], "qty": prompt["qty"]}
            self.open_drop_prompt(prompt["slot"], entry)
            return
        if rects.get("cancel") and rects["cancel"].collidepoint(mx, my):
            self.tip_prompt = None
            return
        if box and not box.collidepoint(mx, my):
            self.tip_prompt = None

    def handle_food_prompt_click(self, mx, my):
        rects = self.food_prompt_rects
        box = rects.get("box")
        prompt = self.food_prompt
        if not prompt:
            return
        if rects.get("eat") and rects["eat"].collidepoint(mx, my):
            self.net.send("USE_ITEM", slot_index=prompt["slot"])
            self.food_prompt = None
            return
        if rects.get("pack") and rects["pack"].collidepoint(mx, my):
            if not (self.player or {}).get("has_food_bag"):
                self.chat_log.append("[!] Buy a Food Bag from Kai or Mira first.")
                self.chat_log = self.chat_log[-8:]
                return
            self.net.send("USE_ITEM", slot_index=prompt["slot"], action="pack")
            self.food_prompt = None
            return
        if rects.get("drop") and rects["drop"].collidepoint(mx, my):
            entry = {"item_id": prompt["item_id"], "qty": prompt["qty"]}
            self.open_drop_prompt(prompt["slot"], entry)
            return
        if rects.get("cancel") and rects["cancel"].collidepoint(mx, my):
            self.food_prompt = None
            return
        if box and not box.collidepoint(mx, my):
            self.food_prompt = None

    def handle_raw_prompt_click(self, mx, my):
        rects = self.raw_prompt_rects
        box = rects.get("box")
        prompt = self.raw_prompt
        if not prompt:
            return
        if rects.get("pack") and rects["pack"].collidepoint(mx, my):
            if not (self.player or {}).get("has_raw_bag"):
                self.chat_log.append("[!] Buy a Raw Food Bag at Harbourreach Tackle first.")
                self.chat_log = self.chat_log[-8:]
                return
            self.net.send("USE_ITEM", slot_index=prompt["slot"], action="pack")
            self.raw_prompt = None
            return
        if rects.get("drop") and rects["drop"].collidepoint(mx, my):
            entry = {"item_id": prompt["item_id"], "qty": prompt["qty"]}
            self.open_drop_prompt(prompt["slot"], entry)
            return
        if rects.get("cancel") and rects["cancel"].collidepoint(mx, my):
            self.raw_prompt = None
            return
        if box and not box.collidepoint(mx, my):
            self.raw_prompt = None

    def handle_food_bag_prompt_click(self, mx, my):
        rects = self.food_bag_prompt_rects
        box = rects.get("box")
        prompt = self.food_bag_prompt
        if not prompt:
            return
        if rects.get("eat") and rects["eat"].collidepoint(mx, my):
            self.net.send("USE_ITEM", slot_index=prompt["slot"], action="eat")
            self.food_bag_prompt = None
            self.pack_prompt = None
            self.log_prompt = None
            self.potion_prompt = None
            return
        if rects.get("pack") and rects["pack"].collidepoint(mx, my):
            self.net.send("USE_ITEM", slot_index=prompt["slot"])
            self.food_bag_prompt = None
            self.storage_bag_prompt = None
            self.pack_prompt = None
            self.log_prompt = None
            self.potion_prompt = None
            return
        if rects.get("unpack") and rects["unpack"].collidepoint(mx, my):
            self.net.send("USE_ITEM", slot_index=prompt["slot"], action="unpack")
            self.food_bag_prompt = None
            return
        if rects.get("cancel") and rects["cancel"].collidepoint(mx, my):
            self.food_bag_prompt = None
            self.pack_prompt = None
            self.log_prompt = None
            self.potion_prompt = None
            return
        if box and not box.collidepoint(mx, my):
            self.food_bag_prompt = None
            self.pack_prompt = None
            self.log_prompt = None
            self.potion_prompt = None

    def handle_storage_bag_prompt_click(self, mx, my):
        rects = self.storage_bag_prompt_rects
        box = rects.get("box")
        prompt = self.storage_bag_prompt
        if not prompt:
            return
        if rects.get("pack") and rects["pack"].collidepoint(mx, my):
            self.net.send("USE_ITEM", slot_index=prompt["slot"], action="pack")
            self.storage_bag_prompt = None
            return
        if rects.get("unpack") and rects["unpack"].collidepoint(mx, my):
            self.net.send("USE_ITEM", slot_index=prompt["slot"], action="unpack")
            self.storage_bag_prompt = None
            return
        if rects.get("cancel") and rects["cancel"].collidepoint(mx, my):
            self.storage_bag_prompt = None
            return
        if box and not box.collidepoint(mx, my):
            self.storage_bag_prompt = None

    def handle_pack_prompt_click(self, mx, my):
        rects = self.pack_prompt_rects
        box = rects.get("box")
        prompt = self.pack_prompt
        if not prompt:
            return
        if rects.get("pack") and rects["pack"].collidepoint(mx, my):
            if not (self.player or {}).get(prompt.get("bag_flag")):
                self.chat_log.append(f"[!] {prompt.get('buy_hint') or 'Buy the matching bag first.'}")
                self.chat_log = self.chat_log[-8:]
                return
            self.net.send("USE_ITEM", slot_index=prompt["slot"], action="pack")
            self.pack_prompt = None
            return
        if rects.get("drop") and rects["drop"].collidepoint(mx, my):
            entry = {"item_id": prompt["item_id"], "qty": prompt["qty"]}
            self.open_drop_prompt(prompt["slot"], entry)
            return
        if rects.get("cancel") and rects["cancel"].collidepoint(mx, my):
            self.pack_prompt = None
            return
        if box and not box.collidepoint(mx, my):
            self.pack_prompt = None

    def handle_log_prompt_click(self, mx, my):
        rects = self.log_prompt_rects
        box = rects.get("box")
        prompt = self.log_prompt
        if not prompt:
            return
        if rects.get("fire") and rects["fire"].collidepoint(mx, my):
            self.open_fire_prompt(prompt["slot"], prompt["item_id"])
            return
        if rects.get("fletch") and rects["fletch"].collidepoint(mx, my):
            self.log_prompt = None
            self.open_fletch()
            return
        if rects.get("pack") and rects["pack"].collidepoint(mx, my):
            if not (self.player or {}).get("has_log_bag"):
                self.chat_log.append("[!] Buy a Log Bag from the General Store or Elena first.")
                self.chat_log = self.chat_log[-8:]
                return
            self.net.send("USE_ITEM", slot_index=prompt["slot"], action="pack")
            self.log_prompt = None
            return
        if rects.get("drop") and rects["drop"].collidepoint(mx, my):
            entry = {"item_id": prompt["item_id"], "qty": prompt["qty"]}
            self.open_drop_prompt(prompt["slot"], entry)
            return
        if rects.get("cancel") and rects["cancel"].collidepoint(mx, my):
            self.log_prompt = None
            return
        if box and not box.collidepoint(mx, my):
            self.log_prompt = None

    def handle_potion_prompt_click(self, mx, my):
        rects = self.potion_prompt_rects
        box = rects.get("box")
        prompt = self.potion_prompt
        if not prompt:
            return
        if rects.get("drink") and rects["drink"].collidepoint(mx, my):
            self.net.send("USE_ITEM", slot_index=prompt["slot"])
            self.potion_prompt = None
            return
        if rects.get("pack") and rects["pack"].collidepoint(mx, my):
            if not (self.player or {}).get("has_potion_pouch"):
                self.chat_log.append("[!] Buy a Potion Pouch from Mira or the Lab first.")
                self.chat_log = self.chat_log[-8:]
                return
            self.net.send("USE_ITEM", slot_index=prompt["slot"], action="pack")
            self.potion_prompt = None
            return
        if rects.get("drop") and rects["drop"].collidepoint(mx, my):
            entry = {"item_id": prompt["item_id"], "qty": prompt["qty"]}
            self.open_drop_prompt(prompt["slot"], entry)
            return
        if rects.get("cancel") and rects["cancel"].collidepoint(mx, my):
            self.potion_prompt = None
            return
        if box and not box.collidepoint(mx, my):
            self.potion_prompt = None

    def handle_combat_quick_click(self, mx, my):
        rects = self.combat_quick_rects or {}
        for kind, rect in rects.items():
            if kind == "dismiss":
                if rect.collidepoint(mx, my):
                    self.combat_quick = None
                    self.combat_quick_until = 0.0
                    return True
                continue
            if rect.collidepoint(mx, my):
                self.net.send("QUICK_CONSUME", kind=kind)
                # Refresh options after a short delay via next PLAYER_UPDATE;
                # keep panel up briefly so they can drink another pot
                self.combat_quick_until = time.time() + 8.0
                return True
        return False

    def open_fire_prompt(self, slot, item_id):
        name = ITEMS.get(item_id, {}).get("name", "logs")
        has_tinder = False
        inv = (self.player or {}).get("inventory") or {}
        for entry in inv.values():
            if entry and entry.get("item_id") == "tinderbox":
                has_tinder = True
                break
        if not has_tinder:
            self.chat_log.append("[!] You need a tinderbox to light a fire.")
            self.chat_log = self.chat_log[-8:]
            return
        self.fire_prompt = {"slot": slot, "item_id": item_id, "name": name}
        self.drop_prompt = None
        self.arrow_prompt = None
        self.tip_prompt = None
        self.food_prompt = None
        self.raw_prompt = None
        self.food_bag_prompt = None
        self.storage_bag_prompt = None
        self.pack_prompt = None
        self.log_prompt = None
        self.potion_prompt = None
        self.cook_prompt = None

    def open_fire_prompt_from_tinderbox(self):
        inv = (self.player or {}).get("inventory") or {}
        for slot_key, entry in inv.items():
            if entry and entry.get("item_id") in ("logs", "oak_logs"):
                try:
                    slot = int(slot_key)
                except (TypeError, ValueError):
                    slot = slot_key
                self.open_fire_prompt(slot, entry["item_id"])
                return
        self.chat_log.append("[!] You need logs to light a fire.")
        self.chat_log = self.chat_log[-8:]

    def handle_fire_prompt_click(self, mx, my):
        yes = self.fire_prompt_rects.get("yes")
        no = self.fire_prompt_rects.get("no")
        box = self.fire_prompt_rects.get("box")
        if yes and yes.collidepoint(mx, my) and self.fire_prompt:
            self.net.send("USE_ITEM", slot_index=self.fire_prompt["slot"])
            self.fire_prompt = None
            return
        if no and no.collidepoint(mx, my):
            self.fire_prompt = None
            return
        if box and not box.collidepoint(mx, my):
            self.fire_prompt = None

    def count_inventory_item(self, item_id):
        total = 0
        inv = (self.player or {}).get("inventory") or {}
        for entry in inv.values():
            if entry and entry.get("item_id") == item_id:
                total += int(entry.get("qty") or 0)
        return total

    def cook_available_count(self, recipe):
        """How many times the player can cook this recipe from inventory + raw bag."""
        available = None
        raw_bag = (self.player or {}).get("raw_bag") or {}
        has_raw = bool((self.player or {}).get("has_raw_bag"))
        for item_id, need in recipe.get("inputs", {}).items():
            have = self.count_inventory_item(item_id)
            if has_raw and is_raw_fish(item_id):
                have += int(raw_bag.get(item_id) or 0)
            can = have // max(1, int(need))
            available = can if available is None else min(available, can)
        return max(0, available or 0)

    def open_cook_prompt(self, recipe_id):
        recipe = self.craft_recipes.get(recipe_id) or {}
        available = self.cook_available_count(recipe)
        if available < 1:
            need = ", ".join(f"{n}x {ITEMS[i]['name']}" for i, n in recipe.get("inputs", {}).items())
            self.chat_log.append(f"[!] You need {need}.")
            self.chat_log = self.chat_log[-8:]
            return
        self.cook_prompt = {
            "recipe_id": recipe_id,
            "name": recipe.get("name", "food"),
            "available": available,
        }
        self.drop_prompt = None
        self.fire_prompt = None

    def handle_cook_prompt_click(self, mx, my):
        rects = self.cook_prompt_rects
        box = rects.get("box")
        prompt = self.cook_prompt
        if not prompt:
            return
        if rects.get("one") and rects["one"].collidepoint(mx, my):
            self.net.send("CRAFT", recipe_id=prompt["recipe_id"], qty=1)
            self.cook_prompt = None
            return
        if rects.get("all") and rects["all"].collidepoint(mx, my):
            self.net.send("CRAFT", recipe_id=prompt["recipe_id"], qty=prompt["available"])
            self.cook_prompt = None
            return
        if rects.get("cancel") and rects["cancel"].collidepoint(mx, my):
            self.cook_prompt = None
            return
        if box and not box.collidepoint(mx, my):
            self.cook_prompt = None

    def sell_price(self, item_id):
        return max(1, int(ITEMS.get(item_id, {}).get("value", 0) * 0.4))

    def shop_will_buy_item(self, item_id):
        """Match server shop buy filters (types / equip slots)."""
        if not self.shop or not self.shop.get("buys", True):
            return False
        item = ITEMS.get(item_id) or {}
        if item.get("sellable") is False or item.get("tradeable") is False:
            return False
        buy_types = self.shop.get("buys_types") or []
        buy_slots = self.shop.get("buys_slots") or []
        if not buy_types and not buy_slots:
            return True
        if buy_types and item.get("type") in buy_types:
            return True
        if buy_slots and item.get("equip_slot") in buy_slots:
            return True
        return False

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
        shift = bool(pygame.key.get_mods() & pygame.KMOD_SHIFT)
        for rect, item_id in self.shop_buy_rects:
            if rect.collidepoint(mx, my):
                self.net.send("SHOP_BUY", shop_id=self.shop["shop_id"], item_id=item_id, qty=1)
                return
        if self.shop.get("buys", True):
            for rect, slot, item_id in self.shop_sell_rects:
                if rect.collidepoint(mx, my):
                    qty = 1
                    if shift and self.player:
                        entry = self.player["inventory"].get(str(slot)) or self.player["inventory"].get(slot)
                        qty = max(1, int((entry or {}).get("qty") or 1))
                    self.net.send("SHOP_SELL", shop_id=self.shop["shop_id"], item_id=item_id, qty=qty)
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
            self._login_vignette = v
        self.screen.blit(self._login_vignette, (0, 0))

    def draw_login(self):
        """Draw login/register from mockup art (pixel-identical to design images)."""
        self.draw_login_backdrop(time.time())
        ui = self._load_login_ui()
        geom = self._login_ui_geom()
        if ui is not None:
            if self.login_mode == "register":
                # Form card only (skip clipped title band); logo composited over live backdrop
                pad = self._register_title_pad()
                body_y0 = 78  # below clipped title / dark plate in source
                src = pygame.Rect(0, body_y0, ui.get_width(), ui.get_height() - body_y0)
                panel_img = ui.subsurface(src)
                dw = max(1, int(src.w * geom["scale"]))
                dh = max(1, int(src.h * geom["scale"]))
                scaled = pygame.transform.smoothscale(panel_img, (dw, dh))
                px = geom["ox"]
                py = geom["oy"] + int((pad + body_y0) * geom["scale"])
                self.screen.blit(scaled, (px, py))
                # Full unclipped MYTHOSCAPE over the scenic backdrop (no dark plate)
                title = self._load_login_title_overlay()
                if title is not None:
                    tw = max(1, int(title.get_width() * geom["scale"]))
                    th = max(1, int(title.get_height() * geom["scale"]))
                    tscaled = pygame.transform.smoothscale(title, (tw, th))
                    # Sit in the reserved pad band, just above the form join
                    tx = geom["ox"] + (geom["dw"] - tw) // 2
                    ty = geom["oy"] + int((pad + body_y0) * geom["scale"]) - th - max(4, int(8 * geom["scale"]))
                    ty = max(geom["oy"] + 2, ty)
                    self.screen.blit(tscaled, (tx, ty))
            else:
                # Login form below the title plate so scenery shows behind the logo
                body_y0 = 170  # below dark title plate / crest band in login_ui.png
                src = pygame.Rect(98, body_y0, 827, ui.get_height() - body_y0)
                src.w = min(src.w, ui.get_width() - src.x)
                src.h = min(src.h, ui.get_height() - src.y)
                panel_img = ui.subsurface(src)
                dw = max(1, int(src.w * geom["scale"]))
                dh = max(1, int(src.h * geom["scale"]))
                scaled = pygame.transform.smoothscale(panel_img, (dw, dh))
                px = geom["ox"] + int(src.x * geom["scale"])
                py = geom["oy"] + int(src.y * geom["scale"])
                self.screen.blit(scaled, (px, py))
                title = self._load_login_title_overlay()
                if title is not None:
                    tw = max(1, int(title.get_width() * geom["scale"]))
                    th = max(1, int(title.get_height() * geom["scale"]))
                    tscaled = pygame.transform.smoothscale(title, (tw, th))
                    tx = geom["ox"] + (geom["dw"] - tw) // 2
                    # Center in the scenery gap above the form card
                    ty = max(4, py - th - max(6, int(10 * geom["scale"])))
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

        if self.show_leaderboard:
            self.draw_leaderboard_modal()

    def _swap_register_gender_art(self, lay):
        """Deprecated: gender is baked into the register mockup via _load_login_ui()."""
        return

    def _draw_login_field_text(self, key, y, x, w, h, mask=False):
        """Overlay typed characters on the mockup input slots."""
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

    def _octagon(self, rect, cut=8):
        x, y, w, h = rect.x, rect.y, rect.w, rect.h
        c = min(cut, w // 3, h // 3)
        return [
            (x + c, y), (x + w - c, y), (x + w, y + c), (x + w, y + h - c),
            (x + w - c, y + h), (x + c, y + h), (x, y + h - c), (x, y + c),
        ]

    def _fill_octagon(self, surf, color, rect, cut=8):
        pygame.draw.polygon(surf, color, self._octagon(rect, cut))

    def _stroke_octagon(self, surf, color, rect, cut=8, width=2):
        pygame.draw.polygon(surf, color, self._octagon(rect, cut), width)

    def _stroke_ornate_panel(self, panel, gold, gold_dim):
        """Gold frame with corner flourishes."""
        self._stroke_octagon(self.screen, gold, panel, cut=10, width=2)
        inner = panel.inflate(-8, -8)
        self._stroke_octagon(self.screen, gold_dim, inner, cut=8, width=1)
        # Corner ticks
        for cx, cy, dx, dy in (
            (panel.x + 14, panel.y + 14, 1, 1),
            (panel.right - 14, panel.y + 14, -1, 1),
            (panel.x + 14, panel.bottom - 14, 1, -1),
            (panel.right - 14, panel.bottom - 14, -1, -1),
        ):
            pygame.draw.line(self.screen, gold, (cx, cy), (cx + dx * 12, cy), 2)
            pygame.draw.line(self.screen, gold, (cx, cy), (cx, cy + dy * 12), 2)

    def _draw_login_crest(self, cx, cy, gold, gold_hi):
        """Stylized mountain range above the title."""
        peaks = [
            (cx - 48, cy + 14), (cx - 28, cy - 2), (cx - 12, cy + 10),
            (cx, cy - 10), (cx + 14, cy + 8), (cx + 32, cy - 4), (cx + 48, cy + 14),
        ]
        pygame.draw.lines(self.screen, gold, False, peaks, 2)
        # Lit peaks
        for px, py in ((cx - 28, cy - 2), (cx, cy - 10), (cx + 32, cy - 4)):
            pygame.draw.circle(self.screen, gold_hi, (int(px), int(py)), 2)

    def _draw_login_tab(self, rect, label, icon, active, green, green_hi, gold):
        if active:
            self._fill_octagon(self.screen, green, rect, cut=8)
            # top glow
            hi = pygame.Surface((rect.w - 8, max(6, rect.h // 3)), pygame.SRCALPHA)
            hi.fill((*green_hi, 55))
            self.screen.blit(hi, (rect.x + 4, rect.y + 3))
            self._stroke_octagon(self.screen, gold, rect, cut=8, width=2)
            col = gold
        else:
            self._fill_octagon(self.screen, (28, 28, 34), rect, cut=8)
            self._stroke_octagon(self.screen, gold, rect, cut=8, width=1)
            col = (180, 175, 160)
        text = self.font_login_sm.render(label, True, col)
        tx = rect.centerx - text.get_width() // 2
        if icon:
            tx += 8
            self._draw_login_icon(rect.x + 14, rect.centery, icon, col)
        self.screen.blit(text, (tx, rect.centery - text.get_height() // 2))

    def _draw_login_field(self, label, key, y, x, w, h, placeholder="", icon=None,
                          mask=False, gold=(212, 175, 55), gold_hi=(255, 230, 140)):
        active = self.active_field == key
        # Label with diamond bullet
        pygame.draw.polygon(self.screen, gold, [
            (x + 4, y - 14), (x + 8, y - 10), (x + 4, y - 6), (x, y - 10),
        ])
        lbl = self.font_login_sm.render(label, True, gold_hi if active else gold)
        self.screen.blit(lbl, (x + 14, y - 20))
        rect = pygame.Rect(x, y, w, h)
        self._fill_octagon(self.screen, (12, 12, 16), rect, cut=8)
        self._stroke_octagon(self.screen, gold_hi if active else gold, rect, cut=8, width=2)
        if icon:
            self._draw_login_icon(rect.x + 16, rect.centery, icon, (120, 118, 110))
        text = self.fields.get(key, "")
        show = ("•" * len(text)) if mask and text else text
        if show:
            txt = self.font.render(show, True, (235, 230, 220))
        else:
            txt = self.font_login_tiny.render(placeholder, True, (110, 108, 100))
        self.screen.blit(txt, (rect.x + 36, rect.centery - txt.get_height() // 2))
        if active and int(time.time() * 2) % 2 == 0:
            cx = rect.x + 36 + (self.font.size(show)[0] if show else 0) + 2
            pygame.draw.line(
                self.screen, (235, 230, 220),
                (cx, rect.y + 10), (cx, rect.bottom - 10), 2,
            )

    def _draw_login_primary(self, rect, label, green, green_hi, gold, gold_hi):
        self._fill_octagon(self.screen, green, rect, cut=10)
        # subtle vertical gradient wash
        wash = pygame.Surface((rect.w - 6, rect.h - 6), pygame.SRCALPHA)
        for i in range(wash.get_height()):
            a = int(40 * (1 - i / max(1, wash.get_height())))
            pygame.draw.line(wash, (*green_hi, a), (0, i), (wash.get_width(), i))
        self.screen.blit(wash, (rect.x + 3, rect.y + 3))
        self._stroke_octagon(self.screen, gold, rect, cut=10, width=2)
        text = self.font_login.render(label, True, gold_hi)
        self.screen.blit(text, (rect.centerx - text.get_width() // 2, rect.centery - text.get_height() // 2))

    def _draw_login_secondary(self, rect, label, gold):
        self._fill_octagon(self.screen, (28, 28, 34), rect, cut=8)
        self._stroke_octagon(self.screen, gold, rect, cut=8, width=1)
        text = self.font_login_sm.render(label, True, gold)
        self.screen.blit(text, (rect.centerx - text.get_width() // 2, rect.centery - text.get_height() // 2))

    def _draw_login_icon(self, cx, cy, kind, color):
        """Tiny geometric icons for login chrome."""
        if kind == "person":
            pygame.draw.circle(self.screen, color, (cx, cy - 4), 4)
            pygame.draw.ellipse(self.screen, color, (cx - 6, cy + 1, 12, 8))
        elif kind == "lock":
            pygame.draw.rect(self.screen, color, (cx - 5, cy - 1, 10, 8), border_radius=1)
            pygame.draw.arc(self.screen, color, (cx - 4, cy - 8, 8, 10), 0, 3.14, 2)
        elif kind == "helmet":
            pygame.draw.polygon(self.screen, color, [
                (cx - 6, cy + 4), (cx - 6, cy - 2), (cx, cy - 7), (cx + 6, cy - 2), (cx + 6, cy + 4),
            ])
            pygame.draw.line(self.screen, color, (cx - 7, cy - 1), (cx + 7, cy - 1), 1)
        elif kind == "trophy":
            pygame.draw.rect(self.screen, color, (cx - 2, cy + 2, 4, 5))
            pygame.draw.polygon(self.screen, color, [
                (cx - 6, cy - 4), (cx + 6, cy - 4), (cx + 4, cy + 2), (cx - 4, cy + 2),
            ])

    def _draw_login_hint_icon(self, x, y, kind, color):
        if kind == "key":
            pygame.draw.rect(self.screen, color, (x, y, 12, 8), 1)
            pygame.draw.line(self.screen, color, (x + 3, y + 8), (x + 3, y + 11), 1)
        elif kind == "enter":
            pygame.draw.lines(self.screen, color, False, [(x + 2, y + 2), (x + 2, y + 8), (x + 10, y + 8)], 1)
            pygame.draw.polygon(self.screen, color, [(x + 8, y + 5), (x + 12, y + 8), (x + 8, y + 11)])
        elif kind == "swap":
            pygame.draw.arc(self.screen, color, (x, y, 12, 12), 0.4, 3.0, 1)
            pygame.draw.polygon(self.screen, color, [(x + 9, y + 1), (x + 12, y + 4), (x + 7, y + 4)])
        elif kind == "trophy":
            self._draw_login_icon(x + 6, y + 5, "trophy", color)

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
        self.draw_magic_fx()
        self.draw_magic_fight_bar()
        self.draw_sidebar()
        self.draw_chat()
        if self.dungeon:
            self.draw_dungeon_hud()
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
        if self.show_fletch:
            self.draw_fletch_modal()
        if self.show_skills:
            self.draw_skills_modal()
        if self.show_pets:
            self.draw_pets_modal()
        if self.show_travel:
            self.draw_travel_modal()
        if self.show_world_map:
            self.draw_world_map_modal()
        if self.dungeon_prompt:
            self.draw_dungeon_prompt()
        if self.fire_prompt:
            self.draw_fire_prompt()
        if self.drop_prompt:
            self.draw_drop_prompt()
        if self.arrow_prompt:
            self.draw_arrow_prompt()
        if self.tip_prompt:
            self.draw_tip_prompt()
        if self.food_prompt:
            self.draw_food_prompt()
        if self.raw_prompt:
            self.draw_raw_prompt()
        if self.food_bag_prompt:
            self.draw_food_bag_prompt()
        if self.storage_bag_prompt:
            self.draw_storage_bag_prompt()
        if self.pack_prompt:
            self.draw_pack_prompt()
        if self.log_prompt:
            self.draw_log_prompt()
        if self.potion_prompt:
            self.draw_potion_prompt()
        if self.cook_prompt:
            self.draw_cook_prompt()
        if self.combat_style_prompt:
            self.draw_combat_style_prompt()
        if self.show_wish:
            self.draw_wish_modal()
        if self.wish_stat_choice:
            self.draw_wish_stat_modal()
        if self.show_help:
            self.draw_help_modal()

    def draw_map(self):
        cam_x, cam_y = self.camera_origin()
        vis_w, vis_h = MAP_W // TILE, MAP_H // TILE
        t = time.time()
        now_pos = {}
        vw, vh = self.view_size()

        for sy in range(vis_h + 1):
            for sx in range(vis_w + 1):
                vx, vy = cam_x + sx, cam_y + sy
                rect = pygame.Rect(sx * TILE, sy * TILE, TILE, TILE)
                if 0 <= vx < vw and 0 <= vy < vh:
                    wx, wy = self.view_to_world(vx, vy)
                    if 0 <= wx < self.world_w and 0 <= wy < len(self.tiles) and wy < self.world_h:
                        tile_id = self.tiles[wy][wx]
                        self.draw_terrain_tile(rect, tile_id, wx, wy, t)
                    else:
                        pygame.draw.rect(self.screen, (8, 6, 10), rect)
                else:
                    # Outside view map: void
                    pygame.draw.rect(self.screen, (8, 6, 10), rect)

        # Click-walk destination + path crumbs
        self.draw_walk_markers(cam_x, cam_y, vis_w, vis_h, t)

        # --- World objects: collect then Y-sort for depth ---
        px, py = self.player_xy() if self.player else (None, None)
        draw_list = []  # (sort_y, layer, draw_fn)

        # Tall volcano / lava-chamber cliff faces
        self._queue_volcano_cliffs(draw_list, cam_x, cam_y, vis_w, vis_h, t)

        # Exit mouth inside private dungeons
        if self.dungeon:
            ex = int(self.dungeon.get("exit_x", self.world_w // 2))
            ey = int(self.dungeon.get("exit_y", self.world_h - 1))
            sx, sy = self.world_to_view_offset(ex, ey, cam_x, cam_y)
            if 0 <= sx <= vis_w and 0 <= sy <= vis_h:
                cx, cy = sx * TILE + TILE // 2, sy * TILE + TILE // 2
                did = self.dungeon.get("id")

                def _draw_exit(cx=cx, cy=cy, did=did):
                    yaw = self.camera_yaw
                    if did == "emberdeep":
                        sprites.draw_volcano_entrance(self.screen, cx, cy, TILE, t, yaw=yaw)
                        self.blit_nameplate("EXIT · Leave", cx, cy - TILE - 4, (255, 180, 100))
                    else:
                        sprites.draw_cave_entrance(self.screen, cx, cy, TILE, t, yaw=yaw)
                        self.blit_nameplate("EXIT · Leave", cx, cy - TILE - 4, (180, 220, 255))
                draw_list.append((cy + TILE // 3, 2, _draw_exit))

        def facing_for(key, x, y, anim_id=None):
            my_id = (self.player or {}).get("id")
            is_local = key == ("p", my_id)
            prev = self._prev_entity_pos.get(key)
            moving_now = prev is not None and prev != (x, y)
            # Keyboard / click-walk: travel facing wins over combat lock (incl. inter-tile gaps)
            traveling = bool(
                is_local and (
                    self.walk_path
                    or moving_now
                    or time.time() < self._entity_moving_until.get(key, 0.0)
                )
            )

            def face_from_delta(dx, dy):
                if abs(dx) >= abs(dy) and dx != 0:
                    return 1 if dx > 0 else -1
                if abs(dy) > abs(dx) and dy != 0:
                    return "back" if dy < 0 else "front"
                return None

            if traveling:
                if self.walk_path:
                    nx, ny = self.walk_path[0]
                    face = face_from_delta(nx - x, ny - y)
                    if face is not None:
                        self._entity_facing[key] = face
                        return face
                if prev is not None:
                    face = face_from_delta(x - prev[0], y - prev[1])
                    if face is not None:
                        self._entity_facing[key] = face
                        return face
                # try_move / update_walk already stored travel facing — keep it
                return self._entity_facing.get(key, 1)

            # Prefer combat facing while a swing is active (idle / in melee only)
            aid = anim_id if anim_id is not None else key
            if isinstance(aid, tuple):
                aid = aid[1] if len(aid) > 1 else aid[0]
            expire = self.attack_anims.get(aid)
            if expire and expire > time.time() and aid in self.attack_face:
                face = self.attack_face[aid]
                # Combat always uses side profile
                if face in ("front", "back"):
                    face = 1
                elif isinstance(face, (int, float)) and abs(float(face)) >= 1.5:
                    face = 1 if float(face) > 0 else -1
                self._entity_facing[key] = face
                return face
            # Standing still while locked onto a live foe — face them sideways
            if is_local and self.combat_target_id is not None:
                m = self.monsters.get(self.combat_target_id)
                if m and m.get("alive"):
                    return self.face_toward_target(x, y, m["x"], m["y"], key=key)
            face = self._entity_facing.get(key, 1)
            if prev is not None:
                faced = face_from_delta(x - prev[0], y - prev[1])
                if faced is not None:
                    face = faced
            self._entity_facing[key] = face
            return face

        def moving_for(key, x, y):
            """True while stepping — hold the gait for ~one tick after each tile move."""
            prev = self._prev_entity_pos.get(key)
            now = time.time()
            if prev is not None and prev != (x, y):
                self._entity_moving_until[key] = now + 0.55
            return now < self._entity_moving_until.get(key, 0.0)

        # Resources
        if not self.dungeon:
            for key, rtype in self.resources.items():
                x, y = map(int, key.split(","))
                # Skip trees that sit on / canopy-cover building shells
                if rtype in ("tree", "oak_tree", "willow_tree", "maple_tree", "yew_tree", "magic_tree"):
                    if self._tree_blocks_building(x, y):
                        continue
                sx, sy = self.world_to_view_offset(x, y, cam_x, cam_y)
                if 0 <= sx <= vis_w and 0 <= sy <= vis_h:
                    cx, cy = sx * TILE + TILE // 2, sy * TILE + TILE // 2
                    label = RESOURCE_LABELS.get(rtype)
                    near = px is not None and max(abs(x - px), abs(y - py)) <= 3
                    color = ORE_LABEL_COLORS.get(rtype, WHITE)
                    # Ghost canopy when the player walks under / behind the tree
                    tree_alpha = 255
                    if rtype in ("tree", "oak_tree", "willow_tree", "maple_tree", "yew_tree", "magic_tree") and px is not None:
                        dist = max(abs(x - px), abs(y - py))
                        if dist == 0:
                            tree_alpha = 95
                        elif dist == 1:
                            tree_alpha = 130
                        elif dist == 2 and y <= py:
                            tree_alpha = 170

                    def _draw_res(cx=cx, cy=cy, rtype=rtype, label=label, near=near, color=color, tree_alpha=tree_alpha):
                        self.draw_resource_sprite(rtype, cx, cy, t, alpha=tree_alpha)
                        if label and near:
                            self.blit_nameplate(label, cx, cy - TILE // 2 - 2, color)
                    draw_list.append((cy + TILE // 3, 1, _draw_res))

        # Interactables
        if not self.dungeon:
            outdoor_kinds = {
                "door", "dungeon_entrance", "cave_entrance", "volcano_entrance", "wishing_well",
                "warning_sign",
                "fountain", "market_stall",
            }
            for spot in self.interactables:
                kind = spot.get("kind")
                # Hide indoor props while the roof is up (can't peek inside)
                if kind not in outdoor_kinds and self.entity_hidden_by_roof(spot["x"], spot["y"]):
                    continue
                sx, sy = self.world_to_view_offset(spot["x"], spot["y"], cam_x, cam_y)
                if 0 <= sx <= vis_w and 0 <= sy <= vis_h:
                    cx, cy = sx * TILE + TILE // 2, sy * TILE + TILE // 2

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
                            is_gate = "castle" in (spot.get("id") or "") or "Gate" in (spot.get("name") or "")
                            # Shell already paints the façade door — only show nameplate
                            has_shell = bool(self._building_for_door(spot))
                            if not is_gate and not has_shell:
                                sprites.draw_door(self.screen, cx, cy, TILE, open_=near, t=t, gate=False)
                            if near:
                                self.blit_nameplate(spot.get("name", "Door"), cx, cy - TILE // 2 - 6)
                        elif kind == "bank":
                            if spot.get("variant") == "chest":
                                sprites.draw_chest(self.screen, cx, cy, TILE, t)
                            else:
                                sprites.draw_bank_booth(self.screen, cx, cy, TILE, t)
                            self.blit_nameplate(spot.get("name", "Bank"), cx, cy - TILE // 2 - 6)
                        elif kind == "dungeon_entrance":
                            # Crypt/house shells already own the recessed mouth —
                            # never paste a separate 3D entrance box on top.
                            has_shell = bool(self._building_covering_spot(spot))
                            if not has_shell:
                                sprites.draw_dungeon_entrance(self.screen, cx, cy, TILE, t, yaw=self.camera_yaw)
                            if spot.get("warning") or "Void" in (spot.get("name") or ""):
                                self.blit_nameplate("⚠ HIGH LEVEL", cx, cy - TILE - 18, (255, 120, 100))
                                self.blit_nameplate("VOID SANCTUM", cx, cy - TILE - 4, (200, 140, 255))
                            else:
                                self.blit_nameplate("DUNGEON", cx, cy - TILE - 4, (210, 170, 255))
                        elif kind == "warning_sign":
                            sprites.draw_warning_sign(self.screen, cx, cy, TILE, t)
                            self.blit_nameplate(spot.get("name", "⚠ DANGER"), cx, cy - TILE // 2 - 8, (255, 140, 90))
                        elif kind == "cave_entrance":
                            sprites.draw_cave_entrance(self.screen, cx, cy, TILE, t, yaw=self.camera_yaw)
                            self.blit_nameplate("TIDEHOLLOW", cx, cy - TILE - 4, (180, 220, 255))
                        elif kind == "volcano_entrance":
                            sprites.draw_volcano_entrance(self.screen, cx, cy, TILE, t, yaw=self.camera_yaw)
                            self.blit_nameplate("⚠ EMBERDEEP", cx, cy - TILE - 18, (255, 140, 80))
                            self.blit_nameplate("LAVA DUNGEON", cx, cy - TILE - 4, (255, 200, 100))
                        elif kind in ("range", "fireplace"):
                            sprites.draw_fireplace(self.screen, cx, cy, TILE, t)
                            self.blit_nameplate(spot.get("name", "Hearth"), cx, cy - TILE // 2 - 2)
                        elif kind == "wishing_well":
                            sprites.draw_wishing_well(self.screen, cx, cy, TILE, t)
                            self.blit_nameplate(spot.get("name", "Wishing Well"), cx, cy - TILE // 2 - 10, (180, 220, 255))
                        else:
                            self.draw_furniture(kind, cx, cy, t, spot)
                    # Rugs / fountains sit under feet; other furniture Y-sorts normally
                    if kind in ("rug", "fountain"):
                        draw_list.append((cy - TILE // 2, 0, _draw_spot))
                    else:
                        draw_list.append((cy + TILE // 4, 2, _draw_spot))

        # Player-lit campfires
        for key in self.fires:
            x, y = map(int, key.split(","))
            sx, sy = self.world_to_view_offset(x, y, cam_x, cam_y)
            if 0 <= sx <= vis_w and 0 <= sy <= vis_h:
                cx, cy = sx * TILE + TILE // 2, sy * TILE + TILE // 2
                near = px is not None and max(abs(x - px), abs(y - py)) <= 2

                def _draw_fire(cx=cx, cy=cy, near=near):
                    sprites.draw_campfire(self.screen, cx, cy, TILE, t)
                    if near:
                        self.blit_nameplate("Fire", cx, cy - TILE // 2 - 2, (255, 170, 80))
                draw_list.append((cy + TILE // 4, 2, _draw_fire))

        # Ground items
        mx, my = pygame.mouse.get_pos()
        hover_tile = None
        if mx < MAP_W and my < MAP_H:
            hover_tile = self.screen_to_tile(mx, my)

        for key, items in self.ground_items.items():
            if not items:
                continue
            x, y = map(int, key.split(","))
            sx, sy = self.world_to_view_offset(x, y, cam_x, cam_y)
            if 0 <= sx <= vis_w and 0 <= sy <= vis_h:
                r = pygame.Rect(sx * TILE + 6, sy * TILE + 6, TILE - 12, TILE - 12)
                top = items[0]
                near_loot = px is not None and max(abs(x - px), abs(y - py)) <= 1
                hovered = hover_tile == (x, y)

                def _draw_loot(r=r, items=items, top=top, near_loot=near_loot, hovered=hovered):
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
                    if near_loot or hovered:
                        item = ITEMS.get(top.get("item_id"), {})
                        name = item.get("name", top.get("item_id", "?"))
                        qty = int(top.get("qty") or 1)
                        label = f"{name} ×{qty}" if qty > 1 else name
                        if top.get("item_id") == "coins":
                            label = f"{qty} coins" if qty != 1 else "1 coin"
                        if len(items) > 1:
                            label += f"  (+{len(items) - 1})"
                        self.blit_nameplate(label, r.centerx, r.y - 2, (255, 230, 160))
                        if hovered or near_loot:
                            hint = self.font_tiny.render("G pickup · Shift+G all", True, (170, 175, 160))
                            hb = pygame.Rect(
                                r.centerx - hint.get_width() // 2 - 4,
                                r.y - 26,
                                hint.get_width() + 8,
                                hint.get_height() + 2,
                            )
                            pygame.draw.rect(self.screen, (12, 12, 16), hb, border_radius=3)
                            self.screen.blit(hint, (hb.x + 4, hb.y + 1))
                draw_list.append((r.bottom, 0, _draw_loot))

        # NPCs
        if not self.dungeon:
            for n in self.npcs:
              if self.entity_hidden_by_roof(n["x"], n["y"]):
                  continue
              sx, sy = self.world_to_view_offset(n["x"], n["y"], cam_x, cam_y)
              if 0 <= sx <= vis_w and 0 <= sy <= vis_h:
                  cx, cy = sx * TILE + TILE // 2, sy * TILE + TILE // 2
                  nid = abs(hash(n["id"]))
                  body, skin, hair = sprites.palette_for(nid)
                  key = ("n", n["id"])
                  face = self.facing_for_view(facing_for(key, n["x"], n["y"]))
                  mov = moving_for(key, n["x"], n["y"])
                  now_pos[key] = (n["x"], n["y"])

                  def _draw_npc(cx=cx, cy=cy, body=body, skin=skin, hair=hair, n=n, face=face, mov=mov):
                      if n["id"] == "mad_scientist":
                          body, skin, hair = (40, 140, 70), (235, 195, 150), (200, 200, 210)
                      elif n["id"] == "herald_rowan":
                          body, skin, hair = (148, 36, 48), (235, 195, 150), (70, 50, 40)
                      elif n["id"] == "city_vendor_mira":
                          body, skin, hair = (70, 110, 150), (230, 185, 145), (90, 55, 35)
                      sprites.draw_humanoid_detailed(
                          self.screen, cx, cy, TILE, body, skin, hair,
                          robe=n["id"] in ROBED_NPC_IDS, t=t, facing=face, moving=mov,
                      )
                      ny, _ = self.entity_anchor(cx, cy, "character")
                      self.blit_nameplate(n["name"], cx, ny, (255, 230, 160))
                      self._blit_npc_role_badges(n, cx, ny - 18)
                  draw_list.append((cy + TILE // 2, 3, _draw_npc))

        # Monsters
        for m in self.monsters.values():
            if not m["alive"]:
                continue
            sx, sy = self.world_to_view_offset(m["x"], m["y"], cam_x, cam_y)
            if 0 <= sx <= vis_w and 0 <= sy <= vis_h:
                cx, cy = sx * TILE + TILE // 2, sy * TILE + TILE // 2
                hurt = m["hp"] < m["max_hp"]
                atk = self._attack_progress(m["id"], t)
                mkey = ("m", m["id"])
                face = self.facing_for_view(facing_for(mkey, m["x"], m["y"], anim_id=m["id"]))
                # Face the local player while swinging if no stored face
                if atk > 0 and px is not None and m["x"] != px:
                    face = 1 if px > m["x"] else -1
                    self.attack_face[m["id"]] = face
                near = px is not None and max(abs(m["x"] - px), abs(m["y"] - py)) <= 5
                now_pos[mkey] = (m["x"], m["y"])
                m_moving = moving_for(mkey, m["x"], m["y"])

                def _draw_mon(cx=cx, cy=cy, m=m, hurt=hurt, atk=atk, near=near, face=face, m_moving=m_moving):
                    targeted = self.combat_target_id == m["id"]
                    if m.get("frozen"):
                        # Ice rim while frost-bound
                        pygame.draw.circle(self.screen, (140, 210, 255), (cx, cy), TILE // 2 + 4, 2)
                    if targeted:
                        ring = pygame.Surface((TILE + 12, TILE + 12), pygame.SRCALPHA)
                        pygame.draw.ellipse(ring, (255, 90, 70, 90), (2, TILE // 2 + 2, TILE + 8, TILE // 2))
                        pygame.draw.ellipse(ring, (255, 160, 80, 180), (2, TILE // 2 + 2, TILE + 8, TILE // 2), 2)
                        self.screen.blit(ring, (cx - TILE // 2 - 6, cy - TILE // 2 - 6))
                    sprites.draw_monster(
                        self.screen, m["type"], cx, cy, TILE, t,
                        hurt=hurt, attacking=atk, facing=face, moving=m_moving,
                    )
                    ny, hy = self.entity_anchor(cx, cy, "monster")
                    lvl = int(m.get("level") or 1)
                    lvl_color = self.monster_threat_color(lvl)
                    if hurt or near or targeted or m.get("frozen"):
                        self.blit_nameplate(m["name"], cx, ny)
                        self.draw_hp_bar(cx, hy, m["hp"], m["max_hp"])
                        self.blit_combat_level(lvl, cx, ny - 16, lvl_color)
                    else:
                        self.blit_combat_level(lvl, cx, ny, lvl_color)
                draw_list.append((cy + TILE // 2, 4, _draw_mon))

        # Pets
        for pet in self.pets:
            sx, sy = self.world_to_view_offset(pet["x"], pet["y"], cam_x, cam_y)
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
                if atk > 0:
                    mov = False
                face = self.facing_for_view(facing_for(pkey, pet["x"], pet["y"], anim_id=f"pet:{pet.get('owner_id')}"))
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
            sx, sy = self.world_to_view_offset(p["x"], p["y"], cam_x, cam_y)
            if 0 <= sx <= vis_w and 0 <= sy <= vis_h:
                cx, cy = sx * TILE + TILE // 2, sy * TILE + TILE // 2
                if is_self:
                    body, skin, hair = (70, 210, 90), (235, 195, 150), (70, 45, 30)
                    eq = self.player.get("equipment") or {}
                    gather = (self.player or {}).get("gathering") or p.get("gathering")
                    gender = (self.player or {}).get("gender") or p.get("gender") or "male"
                else:
                    body, skin, hair = sprites.palette_for(p["id"])
                    eq = p.get("equipment") or {}
                    gather = p.get("gathering")
                    gender = p.get("gender") or "male"
                key = ("p", p["id"])
                mov = moving_for(key, p["x"], p["y"])
                atk = self._attack_progress(p["id"], t)
                face = self.facing_for_view(facing_for(key, p["x"], p["y"], anim_id=p["id"]))
                action = None
                if gather and isinstance(gather, dict) and gather.get("skill") and atk <= 0:
                    action = gather["skill"]
                    mov = False
                    gx, gy = gather.get("x"), gather.get("y")
                    if gx is not None and gy is not None:
                        dx, dy = gx - p["x"], gy - p["y"]
                        if dx != 0:
                            face = 1 if dx > 0 else -1
                        else:
                            # Pure N/S cast — face toward a side that also borders water
                            face = self._entity_facing.get(key, face)
                            for side in (1, -1, face):
                                nx = p["x"] + side
                                ny = p["y"]
                                if (0 <= ny < len(self.tiles) and 0 <= nx < self.world_w
                                        and self.tiles[ny][nx] == wm.WATER):
                                    face = side
                                    break
                            else:
                                # Prefer facing the larger water delta visually (east for harbour)
                                face = 1 if dy == 0 else face
                        self._entity_facing[key] = face
                    # Remember water target so the cast pose can lean toward it
                    if is_self:
                        self._fish_target = (gx, gy)
                if atk > 0:
                    mov = False  # freeze gait during the swing
                now_pos[key] = (p["x"], p["y"])

                def _draw_pl(cx=cx, cy=cy, body=body, skin=skin, hair=hair, eq=eq,
                             mov=mov, face=face, atk=atk, p=p, is_self=is_self,
                             action=action, gather=gather, gender=gender):
                    if is_self and time.time() < self.level_up_until:
                        self.draw_level_up_glow(cx, cy, time.time())
                    sprites.draw_humanoid_detailed(
                        self.screen, cx, cy, TILE, body, skin, hair,
                        weapon=weapon_style(eq.get("weapon")),
                        shield=bool(eq.get("shield")),
                        moving=mov, t=t, facing=face,
                        equipment=eq, attacking=atk, action=action,
                        gender=gender,
                    )
                    if action and gather:
                        self.draw_gather_fx(cx, cy, action, gather, t, face)
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
                    if is_self:
                        self._combat_quick_anchor = (cx, ny - 22)
                draw_list.append((cy + TILE // 2, 6 if is_self else 5, _draw_pl))

        draw_list.sort(key=lambda item: (item[0], item[1]))
        for _, __, fn in draw_list:
            fn()

        # 3D dungeon interior props (Void Sanctum pillars, braziers, walls)
        zone = wm.get_zone(self.player["x"], self.player["y"]) if self.player else None
        if zone == "shadow_crypt" and not self.dungeon:
            # Void Sanctum rooms - add 3D interior props
            # Get room bounds in screen space
            for sy in range(vis_h + 1):
                for sx in range(vis_w + 1):
                    vx, vy = cam_x + sx, cam_y + sy
                    if 0 <= vx < vw and 0 <= vy < vh:
                        wx, wy = self.view_to_world(vx, vy)
                        if wm.get_zone(wx, wy) == "shadow_crypt":
                            # Check if this is a room corner/center for props
                            # Draw props for the visible room area
                            room_rect = pygame.Rect(sx * TILE, sy * TILE, TILE * 4, TILE * 4)
                            if sx % 4 == 0 and sy % 4 == 0:  # Room anchor points
                                dungeon_interior_3d.draw_dungeon_props(
                                    self.screen, room_rect, TILE, zone="shadow_crypt", t=t
                                )
                                break

        # Combat quick-heal buttons above the local player's head
        if getattr(self, "_combat_quick_anchor", None):
            self.draw_combat_quick_prompt(*self._combat_quick_anchor)
            self._combat_quick_anchor = None
        else:
            self.combat_quick_rects = {}

        # Flying arrows (world space → screen)
        self._draw_projectiles(cam_x, cam_y, t)

        # roofs after entities (overworld only — Tidehollow has no village buildings)
        if not self.dungeon:
            self.draw_building_roofs(cam_x, cam_y, vis_w, vis_h)

        self._prev_entity_pos = now_pos

        # floating combat / XP text (hitsplats release on the strike frame)
        now = time.time()
        self._flush_pending_floaters(now)
        self.floaters = [f for f in self.floaters if f["expire"] > now]
        for floater in self.floaters:
            wx, wy = floater["x"], floater["y"]
            sx, sy = self.world_to_view_offset(wx, wy, cam_x, cam_y)
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
                elif kind == "stat_boost":
                    font = self.font_big
                    for ox, oy in ((-1, 0), (1, 0), (0, -1), (0, 1)):
                        shadow = font.render(floater["text"], True, (10, 40, 15))
                        self.screen.blit(shadow, (px - shadow.get_width() // 2 + ox, py - 8 + oy))
                    surf = font.render(floater["text"], True, floater["color"])
                    self.screen.blit(surf, (px - surf.get_width() // 2, py - 8))
                elif kind == "xp":
                    font = self.font_small
                    for ox, oy in ((-1, 0), (1, 0), (0, -1), (0, 1)):
                        shadow = font.render(floater["text"], True, (12, 20, 40))
                        self.screen.blit(shadow, (px - shadow.get_width() // 2 + ox, py + oy))
                    surf = font.render(floater["text"], True, floater["color"])
                    self.screen.blit(surf, (px - surf.get_width() // 2, py))
                elif kind == "loot":
                    font = self.font_small
                    for ox, oy in ((-1, 0), (1, 0), (0, -1), (0, 1)):
                        shadow = font.render(floater["text"], True, (40, 28, 8))
                        self.screen.blit(shadow, (px - shadow.get_width() // 2 + ox, py + oy))
                    surf = font.render(floater["text"], True, floater["color"])
                    self.screen.blit(surf, (px - surf.get_width() // 2, py))
                else:
                    surf = self.font.render(floater["text"], True, floater["color"])
                    self.screen.blit(surf, (px - surf.get_width() // 2, py))

        if self.well_fx and self.well_fx.get("until", 0) > now:
            self.draw_well_rare_fx(cam_x, cam_y, vis_w, vis_h, now)
        elif self.well_fx:
            self.well_fx = None

        self.draw_map_vignette()
        pygame.draw.rect(self.screen, ACCENT_DIM, (0, 0, MAP_W, MAP_H), 2)

        # Death respawn banner overlay
        if time.time() < self.death_banner_until and self.death_banner_text:
            self.draw_death_banner()
        zone = wm.get_zone(self.player["x"], self.player["y"])
        # Zone chip (hidden inside private instances — dungeon HUD covers it)
        if not self.dungeon:
            zone_labels = {
                "fishing_village": "Harbourreach",
                "city": "Stonehaven",
                "shadow_crypt": "Void Sanctum",
                "volcano": "Emberdeep",
                "dungeon": "Dungeon",
            }
            zone_name = zone_labels.get(zone, zone.replace("_", " ").title())
            zone_txt = self.font_small.render(zone_name, True, WHITE)
            chip_w = zone_txt.get_width() + 16
            chip = pygame.Rect(10, 10, chip_w, 22)
            pygame.draw.rect(self.screen, (28, 26, 36), chip, border_radius=6)
            accent = (255, 140, 70) if zone_name == "Emberdeep" else ACCENT
            pygame.draw.rect(self.screen, accent, chip, 1, border_radius=6)
            self.screen.blit(zone_txt, (chip.x + 8, chip.y + 4))
        # Camera compass (RS-style yaw)
        compass = pygame.Rect(8, 36, 72, 22)
        pygame.draw.rect(self.screen, (18, 16, 14), compass, border_radius=4)
        pygame.draw.rect(self.screen, (180, 150, 70), compass, 1, border_radius=4)
        ctxt = self.font_tiny.render(f"Cam {self.yaw_label()}  MMB drag", True, (230, 220, 190))
        self.screen.blit(ctxt, (compass.x + 6, compass.y + 3))
        self.draw_minimap()

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
            # Volcano mouth — lift shell so the crater approach is visible
            if b.get("kind") == "volcano" and spot.get("kind") == "volcano_entrance":
                if max(abs(spot["x"] - px), abs(spot["y"] - py)) <= 2:
                    return True
        return False

    def player_inside_any_building(self):
        return any(self.player_inside_building(b) for b in self.buildings)

    def entity_hidden_by_roof(self, x, y):
        """True if (x,y) is under a building roof that is currently drawn."""
        if self.dungeon:
            return False
        for b in self.buildings:
            if self.player_inside_building(b):
                continue
            if b["x0"] <= x <= b["x1"] and b["y0"] <= y <= b["y1"]:
                return True
        return False

    def building_covering_tile(self, wx, wy):
        """Building whose roof is up and whose floor covers this tile (or None)."""
        if self.dungeon:
            return None
        for b in self.buildings:
            if self.player_inside_building(b):
                continue
            if (
                b["floor_x0"] <= wx <= b["floor_x1"]
                and b["floor_y0"] <= wy <= b["floor_y1"]
            ):
                return b
        return None

    def building_material_at(self, wx, wy):
        """Wood or brick for a village wall tile belonging to a building."""
        for b in self.buildings:
            if b["x0"] <= wx <= b["x1"] and b["y0"] <= wy <= b["y1"]:
                return b.get("material") or ("brick" if b.get("style", 0) % 2 else "wood")
        return "wood"

    def _tree_blocks_building(self, tx, ty):
        """True if a tree trunk would cover or canopy-overlap a building shell."""
        for b in self.buildings:
            if b.get("kind") == "volcano":
                continue
            x0, y0, x1, y1 = b["x0"], b["y0"], b["x1"], b["y1"]
            # Yard margin
            if x0 - 2 <= tx <= x1 + 2 and y0 - 2 <= ty <= y1 + 2:
                return True
            # Canopy from trunks just south of the building hangs onto the roof
            if x0 - 1 <= tx <= x1 + 1 and y1 + 1 <= ty <= y1 + 4:
                return True
        return False

    def _building_for_door(self, spot):
        """Return building dict whose south wall holds this door, or None."""
        dx, dy = int(spot.get("x", -1)), int(spot.get("y", -1))
        for b in self.buildings or []:
            if b.get("kind") in ("volcano", "castle"):
                continue
            if int(b.get("y1", -99)) == dy and int(b.get("x0", 0)) <= dx <= int(b.get("x1", 0)):
                return b
        return None

    def _building_covering_spot(self, spot):
        """Return shell-capable building whose footprint contains this tile, or None."""
        dx, dy = int(spot.get("x", -1)), int(spot.get("y", -1))
        for b in self.buildings or []:
            if b.get("kind") in ("volcano", "castle"):
                continue
            if (
                int(b.get("x0", 0)) <= dx <= int(b.get("x1", 0))
                and int(b.get("y0", 0)) <= dy <= int(b.get("y1", 0))
            ):
                return b
        return None

    def _door_frac_for_building(self, b):
        """Fraction across building width where the south-wall door sits."""
        x0, x1 = int(b.get("x0", 0)), int(b.get("x1", 0))
        y1 = int(b.get("y1", 0))
        span = max(1, x1 - x0)
        for spot in self.interactables or []:
            if spot.get("kind") != "door":
                continue
            if int(spot.get("y", -1)) == y1 and x0 <= int(spot.get("x", -1)) <= x1:
                return (int(spot["x"]) - x0 + 0.5) / span
        return 0.5

    def draw_building_roofs(self, cam_x, cam_y, vis_w, vis_h):
        t = time.time()
        for b in self.buildings:
            vx0, vy0, vx1, vy1 = self.building_view_bounds(b)
            sx0, sy0 = vx0 - cam_x, vy0 - cam_y
            sx1, sy1 = vx1 - cam_x, vy1 - cam_y
            if sx1 < -2 or sy1 < -2 or sx0 > vis_w + 2 or sy0 > vis_h + 2:
                continue
            rect = pygame.Rect(
                sx0 * TILE, sy0 * TILE,
                (vx1 - vx0 + 1) * TILE, (vy1 - vy0 + 1) * TILE,
            )
            bid = b.get("id") or ""
            door_frac = self._door_frac_for_building(b)
            inside = self.player_inside_building(b)
            # Dungeons/crypts: completely hide exterior when inside (classic overworld→interior)
            if inside and b.get("kind") in ("crypt", "dungeon"):
                continue  # Skip drawing entirely - player sees interior space
            # Houses: keep wall cutaway so the shell doesn't vanish (RS indoor feel)
            if inside:
                if bid and building_sprites.draw_building_cutaway(
                    self.screen, rect, bid, yaw=0, alpha=255,
                ):
                    pass
                else:
                    sprites.draw_building_cutaway(
                        self.screen, rect, kind=b.get("kind", "house"),
                        style=b.get("style", 0), material=b.get("material"),
                        yaw=0, alpha=255, door_frac=door_frac,
                    )
                continue
            # Opaque shells only — never ghost alpha
            if (
                self.camera_yaw == 0
                and bid
                and building_sprites.draw_building_sprite(
                    self.screen, rect, bid, alpha=255, yaw=0,
                )
            ):
                pass
            elif b.get("kind") == "volcano":
                sprites._draw_volcano_mountain(self.screen, rect, alpha=255, t=t)
            else:
                sprites.draw_building_roof(
                    self.screen, rect, kind=b.get("kind", "house"), style=b.get("style", 0),
                    material=b.get("material"), yaw=0, alpha=255, door_frac=door_frac,
                )
            name = b.get("name")
            if name:
                label = self.font_small.render(name, True, (255, 230, 180))
                self.screen.blit(
                    label,
                    (rect.centerx - label.get_width() // 2, rect.y + rect.h * 0.14),
                )

    def _queue_volcano_cliffs(self, draw_list, cam_x, cam_y, vis_w, vis_h, t):
        """Queue tall cliff sprites for volcano rock faces and dungeon corridor walls."""
        in_ember = bool(self.dungeon and self.dungeon.get("id") == "emberdeep")
        in_dungeon = bool(self.dungeon)
        # "Camera-south" neighbor in world space (tile toward bottom of screen)
        _sdx, _sdy = self.rotate_move_delta(0, 1)

        for sy in range(vis_h + 1):
            for sx in range(vis_w + 1):
                vx, vy = cam_x + sx, cam_y + sy
                wx, wy = self.view_to_world(vx, vy)
                if not (0 <= wy < len(self.tiles) and 0 <= wx < self.world_w):
                    continue
                if self.tiles[wy][wx] != wm.WALL:
                    continue
                zone = "volcano" if in_ember else (wm.get_zone(wx, wy) if self.world_w else "")
                if in_dungeon and not in_ember:
                    zone = "dungeon"
                if zone not in ("volcano", "dungeon") and not in_ember:
                    continue
                # Open ground toward camera-south (bottom of screen)
                nx, ny = wx + _sdx, wy + _sdy
                if not (0 <= ny < len(self.tiles) and 0 <= nx < self.world_w):
                    continue
                south = self.tiles[ny][nx]
                if south == wm.WALL:
                    continue
                if self.dungeon and south not in (wm.FLOOR, wm.PATH, wm.STONE, wm.WATER):
                    continue
                if not in_ember and not in_dungeon and self.entity_hidden_by_roof(wx, wy):
                    continue
                cx = sx * TILE + TILE // 2
                cy = sy * TILE + TILE // 2

                if zone == "dungeon" and not in_ember:
                    def _draw(cx=cx, cy=cy, wx=wx, wy=wy):
                        sprites.draw_dungeon_cliff(self.screen, cx, cy, TILE, wx, wy, t)
                else:
                    def _draw(cx=cx, cy=cy, wx=wx, wy=wy):
                        sprites.draw_volcano_cliff(self.screen, cx, cy, TILE, wx, wy, t)
                draw_list.append((cy + TILE // 2, 1, _draw))

    def click_door(self, spot):
        """Walk through a door / dungeon mouth toward the far side only."""
        px, py = self.player_xy()
        enter = (int(spot.get("enter_x", spot["x"])), int(spot.get("enter_y", spot["y"])))
        exit_ = (int(spot.get("exit_x", spot["x"])), int(spot.get("exit_y", spot["y"])))
        door = (int(spot["x"]), int(spot["y"]))
        # Closer to the outside (exit) → go inside (enter); closer to inside → go out
        d_enter = max(abs(px - enter[0]), abs(py - enter[1]))
        d_exit = max(abs(px - exit_[0]), abs(py - exit_[1]))
        target = enter if d_exit <= d_enter else exit_
        if not self.tile_walkable(*target):
            other = exit_ if target == enter else enter
            target = other if self.tile_walkable(*other) else door
        # Only the far-side tile — including both sides made "enter" stop at the apron
        goals = set()
        if self.tile_walkable(*target):
            goals.add(target)
        else:
            goals |= self.adjacent_goals(target[0], target[1])
            if self.tile_walkable(*door):
                goals.add(door)
        if not goals:
            self.chat_log.append("[!] Can't use that door.")
            self.chat_log = self.chat_log[-8:]
            return
        self.walk_and_act(goals, None)

    def draw_terrain_tile(self, rect, tile_id, wx, wy, t):
        if self.dungeon:
            zone = "volcano" if self.dungeon.get("id") == "emberdeep" else "dungeon"
        else:
            zone = wm.get_zone(wx, wy) if self.world_w else "wilderness"
        if tile_id in (wm.TREE, wm.OAK_TREE, wm.WILLOW_TREE, wm.MAPLE_TREE, wm.YEW_TREE, wm.MAGIC_TREE, wm.FISH_SPOT):
            sprites.draw_grass(self.screen, rect, wx, wy)
        elif tile_id in (wm.ORE, wm.IRON_ORE, wm.COAL, wm.MITHRIL_ORE, wm.ADAMANTITE_ORE):
            sprites.draw_floor(self.screen, rect, wx, wy, zone=zone)
        elif tile_id == wm.GRASS:
            sprites.draw_grass(self.screen, rect, wx, wy)
        elif tile_id == wm.PATH:
            if self._is_pier_tile(wx, wy):
                sprites.draw_pier(self.screen, rect, wx, wy)
            else:
                sprites.draw_path(self.screen, rect, wx, wy, zone=zone)
        elif tile_id == wm.STONE:
            sprites.draw_stone_floor(self.screen, rect, wx, wy)
        elif tile_id == wm.FLOOR:
            covered = self.building_covering_tile(wx, wy)
            if covered:
                mat = covered.get("material") or (
                    "brick" if covered.get("style", 0) % 2 else "wood"
                )
                sprites.draw_building_wall(self.screen, rect, wx, wy, material=mat)
            else:
                sprites.draw_floor(self.screen, rect, wx, wy, zone=zone)
        elif tile_id == wm.WALL:
            mat = None
            if zone in ("village", "fishing_village", "city"):
                mat = self.building_material_at(wx, wy)
            sprites.draw_wall(self.screen, rect, zone, wx, wy, material=mat)
        elif tile_id == wm.WATER:
            if zone == "volcano" or (self.dungeon and self.dungeon.get("id") == "emberdeep"):
                sprites.draw_lava(self.screen, rect, t, wx, wy)
            else:
                shores = self._water_shores(wx, wy)
                sprites.draw_water_detailed(self.screen, rect, t, wx, wy, shores=shores)
        else:
            sprites.draw_grass(self.screen, rect, wx, wy)
        # Ambient occlusion on floors/paths next to walls (dungeon + overworld)
        if tile_id not in (wm.WALL,) and not (
            tile_id == wm.FLOOR and self.building_covering_tile(wx, wy)
        ):
            walls = self._wall_neighbors(wx, wy)
            if any(walls.values()):
                # Stronger AO in dungeons / volcano floors
                ao_a = 95 if (self.dungeon or zone in ("dungeon", "volcano", "shadow_crypt")) else 68
                sprites.draw_tile_wall_ao(self.screen, rect, walls, alpha=ao_a)

    def _wall_neighbors(self, wx, wy):
        """True when adjacent tile is WALL — used for floor contact AO."""
        def is_wall(x, y):
            if not (0 <= y < len(self.tiles) and 0 <= x < self.world_w):
                return False
            return self.tiles[y][x] == wm.WALL
        return {
            "N": is_wall(wx, wy - 1),
            "S": is_wall(wx, wy + 1),
            "W": is_wall(wx - 1, wy),
            "E": is_wall(wx + 1, wy),
        }

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

    def _is_pier_tile(self, wx, wy):
        """PATH tiles in the harbour that sit next to water — draw as wood planks."""
        if not (0 <= wy < len(self.tiles) and 0 <= wx < self.world_w):
            return False
        if self.tiles[wy][wx] != wm.PATH:
            return False
        if wm.get_zone(wx, wy) != "fishing_village":
            return False
        for dy, dx in ((-1, 0), (1, 0), (0, -1), (0, 1)):
            nx, ny = wx + dx, wy + dy
            if 0 <= ny < len(self.tiles) and 0 <= nx < self.world_w:
                if self.tiles[ny][nx] == wm.WATER:
                    return True
        # Also treat the pier approach strip (east of shops) as planks
        return wx >= 105

    def draw_resource_sprite(self, rtype, cx, cy, t, alpha=255):
        tree_variants = {
            "tree": 0, "oak_tree": 1, "willow_tree": 2,
            "maple_tree": 3, "yew_tree": 4, "magic_tree": 5,
        }
        if rtype in tree_variants:
            sprites.draw_tree_detailed(
                self.screen, cx, cy, TILE, variant=tree_variants[rtype], t=t, alpha=alpha,
            )
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
            "wishing_well": sprites.draw_wishing_well,
            "throne": sprites.draw_throne,
            "fountain": sprites.draw_fountain,
            "market_stall": sprites.draw_market_stall,
            "brazier": sprites.draw_brazier,
            "banner": sprites.draw_banner_stand,
        }
        fn = drawers.get(kind)
        if fn is None:
            return
        if kind == "chair":
            fn(self.screen, cx, cy, TILE, t, facing=spot.get("facing", 1))
        elif kind in ("rug", "banner"):
            color = spot.get("color") or ((140, 50, 50) if kind == "rug" else (160, 40, 48))
            fn(self.screen, cx, cy, TILE, t, color=tuple(color))
        else:
            fn(self.screen, cx, cy, TILE, t)
    def _draw_projectiles(self, cam_x, cam_y, t):
        """Draw in-flight arrows between attacker and target tiles."""
        now = time.time()
        keep = []
        for proj in self.projectiles:
            start = proj["start"]
            dur = max(0.05, proj["dur"])
            if now < start:
                keep.append(proj)
                continue
            u = (now - start) / dur
            if u >= 1.0:
                continue
            # Ease out slightly so the tip reaches the target cleanly
            ease = 1.0 - (1.0 - u) * (1.0 - u)
            ax, ay = proj["ax"], proj["ay"]
            tx, ty = proj["tx"], proj["ty"]
            wx = ax + (tx - ax) * ease
            wy = ay + (ty - ay) * ease
            # Slight arc
            arc = math.sin(ease * math.pi) * 0.35
            sx = int(self.map_screen_pos(wx, wy, cam_x, cam_y)[0])
            sy = int(self.map_screen_pos(wx, wy, cam_x, cam_y)[1] - arc * TILE)
            dx = (tx - ax)
            dy = (ty - ay)
            length = max(0.01, (dx * dx + dy * dy) ** 0.5)
            ux, uy = dx / length, dy / length
            tip = (sx + ux * 10, sy + uy * 10)
            tail = (sx - ux * 8, sy - uy * 8)
            pygame.draw.line(self.screen, (150, 105, 55), tail, tip, 3)
            pygame.draw.line(self.screen, (210, 175, 120), tail, tip, 1)
            # Tip
            pygame.draw.circle(self.screen, (190, 195, 205), (int(tip[0]), int(tip[1])), 3)
            # Fletching
            fx, fy = -uy, ux
            pygame.draw.line(
                self.screen, (245, 245, 250),
                (tail[0] + fx * 4, tail[1] + fy * 4),
                (tail[0] - fx * 4, tail[1] - fy * 4),
                2,
            )
            keep.append(proj)
        self.projectiles = keep

    def _attack_progress(self, entity_id, now=None):
        """Return 0..1 swing progress while an attack anim is active."""
        expire = self.attack_anims.get(entity_id)
        if not expire:
            return 0.0
        now = now if now is not None else time.time()
        if now >= expire:
            self.attack_anims.pop(entity_id, None)
            self.attack_face.pop(entity_id, None)
            self.attack_anim_kind.pop(entity_id, None)
            return 0.0
        kind = self.attack_anim_kind.get(entity_id, "melee")
        dur = self.RANGED_ANIM_SECS if kind == "ranged" else self.ATTACK_ANIM_SECS
        return max(0.0, min(1.0, 1.0 - (expire - now) / dur))

    def _flush_pending_floaters(self, now=None):
        """Release hitsplats timed to the strike frame of an attack."""
        now = now if now is not None else time.time()
        keep = []
        for f in self.pending_floaters:
            if now >= f.get("show_at", 0):
                expire = f.get("expire")
                if not expire:
                    expire = now + 1.05
                self.floaters.append({
                    "x": f["x"], "y": f["y"], "text": f["text"],
                    "color": f["color"], "expire": expire, "kind": f["kind"],
                })
            else:
                keep.append(f)
        self.pending_floaters = keep

    def draw_gather_fx(self, cx, cy, skill, gather, t, facing=1):
        """Chips / sparks / splash timed to the gather swing loop."""
        import math as _m
        facing = 1 if facing >= 0 else -1
        if skill == "woodcutting":
            ph = (t * 1.1) % 1.0
            if 0.48 <= ph <= 0.62:
                u = (ph - 0.48) / 0.14
                for i in range(4):
                    ang = -0.6 + i * 0.45
                    dist = (4 + u * 10 + i) * (TILE / 40)
                    px = cx + facing * (8 + dist * _m.cos(ang))
                    py = cy - 6 - dist * _m.sin(ang) - u * 4
                    col = (140, 100, 55) if i % 2 == 0 else (90, 65, 35)
                    pygame.draw.circle(self.screen, col, (int(px), int(py)), max(1, 2 - int(u * 1.5)))
        elif skill == "mining":
            ph = (t * 1.05) % 1.0
            if 0.50 <= ph <= 0.64:
                u = (ph - 0.50) / 0.14
                for i in range(5):
                    ang = -0.9 + i * 0.4
                    dist = (3 + u * 12) * (TILE / 40)
                    px = cx + facing * (10 + dist * _m.cos(ang))
                    py = cy - 4 - dist * abs(_m.sin(ang)) - u * 3
                    col = (255, 230, 140) if i % 2 else (200, 200, 210)
                    pygame.draw.circle(self.screen, col, (int(px), int(py)), max(1, 2 - int(u)))
        elif skill == "fishing":
            # Soft ripple near the water tile in front of the angler
            gx, gy = gather.get("x"), gather.get("y")
            cam_x, cam_y = self.camera_origin()
            if gx is not None and gy is not None:
                wx = self.map_screen_pos(gx, gy, cam_x, cam_y)[0]
                wy = self.map_screen_pos(gx, gy, cam_x, cam_y)[1]
            else:
                wx = cx + facing * TILE * 0.7
                wy = cy + TILE * 0.15
            pulse = 0.5 + 0.5 * _m.sin(t * 3.2)
            for i in range(3):
                r = int((4 + i * 3 + pulse * 2) * (TILE / 40))
                alpha = max(30, 110 - i * 30)
                ring = pygame.Surface((r * 2 + 4, r + 6), pygame.SRCALPHA)
                pygame.draw.ellipse(ring, (180, 220, 255, alpha), (2, 2, r * 2, r))
                self.screen.blit(ring, (wx - r - 2, wy - r // 2))
            # Occasional splash drop
            if _m.sin(t * 2.1) > 0.85:
                pygame.draw.circle(self.screen, (210, 235, 255), (int(wx + facing * 3), int(wy - 4)), 2)

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

    def draw_magic_fight_bar(self):
        """Manual-mode ability buttons along the bottom of the map while fighting."""
        self.magic_fight_rects = {}
        if not self.player:
            return
        magic = self.player.get("magic") or {}
        if magic.get("auto", True):
            return
        if not self.player_in_fight():
            return
        abilities = magic.get("abilities") or {}
        unlocked = [
            aid for aid in reversed(magic.get("order") or MAGIC_ABILITY_ORDER)
            if (abilities.get(aid) or {}).get("unlocked")
        ]
        if not unlocked:
            return
        now = time.time()
        n = len(unlocked)
        bw, bh, gap = 78, 36, 6
        total_w = n * bw + (n - 1) * gap
        x0 = max(8, (MAP_W - total_w) // 2)
        y0 = MAP_H - 48
        banner = pygame.Rect(x0 - 8, y0 - 8, total_w + 16, bh + 16)
        pygame.draw.rect(self.screen, (16, 18, 26, ), banner, border_radius=8)
        # solid fill (no alpha on main screen without SRCALPHA)
        pygame.draw.rect(self.screen, (18, 22, 32), banner, border_radius=8)
        pygame.draw.rect(self.screen, (90, 120, 160), banner, 1, border_radius=8)
        for i, aid in enumerate(unlocked):
            ab = abilities.get(aid) or {}
            ready_at = float(ab.get("ready_at") or 0)
            cd_left = max(0.0, ready_at - now)
            ready = cd_left <= 0
            effect = ab.get("effect") or "lightning"
            r = pygame.Rect(x0 + i * (bw + gap), y0, bw, bh)
            col = {
                "lightning": (70, 110, 180),
                "fire": (150, 70, 40),
                "freeze": (50, 110, 150),
            }.get(effect, (60, 70, 90))
            if not ready:
                col = (40, 42, 50)
            pygame.draw.rect(self.screen, col, r, border_radius=6)
            border = (180, 220, 255) if ready else (70, 74, 85)
            pygame.draw.rect(self.screen, border, r, 1, border_radius=6)
            name = (ab.get("name") or aid)[:9]
            self.screen.blit(
                self.font_tiny.render(name, True, WHITE if ready else GREY),
                (r.x + 4, r.y + 4),
            )
            status = "Ready" if ready else f"{cd_left:.1f}s"
            self.screen.blit(
                self.font_tiny.render(status, True, (200, 230, 180) if ready else (160, 150, 140)),
                (r.x + 4, r.y + 18),
            )
            if ready:
                self.magic_fight_rects[aid] = r

    def draw_magic_fx(self):
        now = time.time()
        self.magic_fx = [fx for fx in self.magic_fx if fx.get("until", 0) > now]
        if not self.magic_fx or not self.player:
            return
        cam_x, cam_y = self.camera_origin()
        for fx in self.magic_fx:
            sx, sy = self.map_screen_pos(fx["x"], fx["y"], cam_x, cam_y)
            if not (0 <= sx <= MAP_W and 0 <= sy <= MAP_H):
                continue
            effect = fx.get("effect") or "lightning"
            life = max(0.05, fx["until"] - now)
            u = 1.0 - min(1.0, life / 0.85)
            if effect == "fire":
                col = (255, 120 + int(80 * (1 - u)), 40)
                for i in range(5):
                    pygame.draw.circle(
                        self.screen, col,
                        (sx + int(math.sin(u * 9 + i) * 10), sy - int(u * 28) - i * 4),
                        max(2, 8 - i),
                    )
            elif effect == "freeze":
                col = (160, 220, 255)
                pygame.draw.circle(self.screen, col, (sx, sy), int(10 + u * 18), 2)
                pygame.draw.circle(self.screen, (200, 240, 255), (sx, sy - 4), 4)
            else:  # lightning
                col = (200, 230, 255)
                pts = [(sx, sy - 28), (sx + 6, sy - 14), (sx - 4, sy - 10), (sx + 8, sy), (sx, sy + 6)]
                if len(pts) >= 2:
                    pygame.draw.lines(self.screen, col, False, pts, 2)
            if fx.get("damage"):
                dmg = self.font_small.render(str(fx["damage"]), True, YELLOW)
                self.screen.blit(dmg, (sx - dmg.get_width() // 2, sy - 40 - int(u * 12)))

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
        return box

    def _blit_npc_role_badges(self, npc, cx, top_y):
        """Compact role pills above an NPC nameplate (shop / bank / quest / forge)."""
        static = next((n for n in NPCS if n.get("id") == npc.get("id")), None) or {}
        merged = {**static, **(npc or {})}
        tags = []
        if merged.get("shop_id"):
            tags.append(("Shop", (200, 160, 60), (40, 32, 16)))
        if merged.get("bank"):
            tags.append(("Bank", (140, 190, 255), (20, 32, 48)))
        if merged.get("forge"):
            tags.append(("Forge", (255, 150, 90), (48, 28, 16)))
        qids = list(merged.get("quest_ids") or [])
        legacy = merged.get("quest_id")
        if legacy and legacy not in qids:
            qids.insert(0, legacy)
        qid = None
        for c in qids:
            req = (QUESTS.get(c) or {}).get("requires")
            if req:
                needed = req if isinstance(req, (list, tuple)) else [req]
                if any((self.quests.get(r) or {}).get("status") != "complete" for r in needed):
                    continue
            st = (self.quests.get(c) or {}).get("status", "not_started")
            if st != "complete":
                qid = c
                break
        if qid:
            qst = (self.quests.get(qid) or {}).get("status", "not_started")
            label = "Turn in" if qst == "ready" else ("Quest" if qst == "active" else "Quest!")
            tags.append((label, (210, 160, 255), (36, 24, 48)))
        if merged.get("quest_target_for"):
            tags.append(("Find me", (120, 220, 200), (20, 40, 36)))
        if not tags:
            return
        gap = 4
        widths = []
        for label, _fg, _bg in tags:
            widths.append(self.font_tiny.size(label)[0] + 10)
        total_w = sum(widths) + gap * (len(tags) - 1)
        x = cx - total_w // 2
        for (label, fg, bg), w in zip(tags, widths):
            r = pygame.Rect(x, top_y - 12, w, 14)
            pygame.draw.rect(self.screen, bg, r, border_radius=4)
            pygame.draw.rect(self.screen, fg, r, 1, border_radius=4)
            self.screen.blit(self.font_tiny.render(label, True, fg), (r.x + 5, r.y + 1))
            x += w + gap

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

    def minimap_dims(self):
        """Pixel size of the minimap (fits top-right of the map view)."""
        max_h = 196
        vw, vh = self.view_size()
        if vw <= 0 or vh <= 0:
            return 140, max_h
        mm_h = max_h
        mm_w = max(96, int(round(max_h * vw / vh)))
        mm_w = min(mm_w, 168)
        return mm_w, mm_h

    def minimap_tile_color(self, tile_id):
        if tile_id == wm.WATER:
            return (40, 90, 160)
        if tile_id == wm.PATH:
            return (150, 130, 90)
        if tile_id == wm.STONE:
            return (128, 128, 136)
        if tile_id == wm.FLOOR:
            return (70, 68, 78)
        if tile_id == wm.WALL:
            return (45, 42, 48)
        if tile_id in (wm.TREE, wm.OAK_TREE, wm.WILLOW_TREE, wm.MAPLE_TREE, wm.YEW_TREE, wm.MAGIC_TREE):
            return (28, 90, 40)
        if tile_id in (wm.ORE, wm.IRON_ORE, wm.COAL, wm.MITHRIL_ORE, wm.ADAMANTITE_ORE):
            return (110, 95, 70)
        if tile_id == wm.GRASS:
            return (55, 110, 50)
        return (40, 55, 40)

    def rebuild_minimap_base(self):
        mm_w, mm_h = self.minimap_dims()
        surf = pygame.Surface((mm_w, mm_h))
        surf.fill((18, 20, 26))
        vw, vh = self.view_size()
        if not self.tiles or vw <= 0 or vh <= 0:
            self._minimap_base = surf
            self._minimap_size = (mm_w, mm_h)
            self._minimap_yaw = int(self.camera_yaw) % 4
            return
        # Paint in *view* space so the minimap rotates with camera yaw
        for vy in range(vh):
            py0 = int(vy * mm_h / vh)
            py1 = int((vy + 1) * mm_h / vh)
            for vx in range(vw):
                wx, wy = self.view_to_world(vx, vy)
                if not (0 <= wy < len(self.tiles) and 0 <= wx < len(self.tiles[wy])):
                    continue
                px0 = int(vx * mm_w / vw)
                px1 = int((vx + 1) * mm_w / vw)
                color = self.minimap_tile_color(self.tiles[wy][wx])
                if px1 <= px0:
                    px1 = px0 + 1
                if py1 <= py0:
                    py1 = py0 + 1
                surf.fill(color, (px0, py0, px1 - px0, py1 - py0))
        self._minimap_base = surf
        self._minimap_size = (mm_w, mm_h)
        self._minimap_yaw = int(self.camera_yaw) % 4

    def world_to_minimap(self, wx, wy, rect):
        vw, vh = self.view_size()
        if vw <= 0 or vh <= 0:
            return rect.centerx, rect.centery
        vx, vy = self.world_to_view(int(wx), int(wy))
        mx = rect.x + int(vx * rect.w / vw)
        my = rect.y + int(vy * rect.h / vh)
        return mx, my

    def minimap_to_world(self, mx, my):
        rect = self.minimap_rect
        vw, vh = self.view_size()
        if not rect or vw <= 0 or vh <= 0:
            return None
        lx = max(0, min(rect.w - 1, mx - rect.x))
        ly = max(0, min(rect.h - 1, my - rect.y))
        vx = int(lx * vw / rect.w)
        vy = int(ly * vh / rect.h)
        wx, wy = self.view_to_world(vx, vy)
        return max(0, min(self.world_w - 1, wx)), max(0, min(self.world_h - 1, wy))

    def minimap_walk_click(self, mx, my):
        pos = self.minimap_to_world(mx, my)
        if not pos:
            return
        wx, wy = pos
        goals = set()
        if self.tile_walkable(wx, wy):
            goals.add((wx, wy))
        goals |= self.adjacent_goals(wx, wy)
        if not goals:
            # spiral for nearest walkable
            for r in range(1, 8):
                for dx in range(-r, r + 1):
                    for dy in (-r, r):
                        if self.tile_walkable(wx + dx, wy + dy):
                            goals.add((wx + dx, wy + dy))
                    for dy in range(-r + 1, r):
                        for dx in (-r, r):
                            if self.tile_walkable(wx + dx, wy + dy):
                                goals.add((wx + dx, wy + dy))
                if goals:
                    break
        if goals:
            self.chat_log.append("Walking toward map marker...")
            self.chat_log = self.chat_log[-8:]
            self.walk_and_act(goals, None)

    def draw_minimap(self):
        if not self.player or self.world_w <= 0:
            self.minimap_rect = None
            return
        mm_w, mm_h = self.minimap_dims()
        yaw = int(self.camera_yaw) % 4
        if (
            self._minimap_base is None
            or self._minimap_size != (mm_w, mm_h)
            or getattr(self, "_minimap_yaw", None) != yaw
        ):
            self.rebuild_minimap_base()
        pad = 10
        rect = pygame.Rect(MAP_W - mm_w - pad, pad, mm_w, mm_h)
        self.minimap_rect = rect
        frame = rect.inflate(6, 6)
        pygame.draw.rect(self.screen, (12, 14, 20), frame, border_radius=6)
        pygame.draw.rect(self.screen, (90, 120, 160), frame, 2, border_radius=6)
        self.screen.blit(self._minimap_base, rect.topleft)

        # Destination markers
        for dest in TRAVEL_DESTINATIONS:
            dx, dy = self.world_to_minimap(dest["x"], dest["y"], rect)
            if dest["kind"] == "monster":
                mdef = MONSTERS.get(dest.get("monster") or "", {})
                col = self.monster_threat_color(mdef.get("level", 1))
                pygame.draw.circle(self.screen, col, (dx, dy), 3)
            else:
                if dest.get("id") == "emberdeep":
                    col = (255, 140, 70)
                elif dest.get("action"):
                    col = (255, 220, 120)
                else:
                    col = (200, 210, 230)
                pygame.draw.rect(self.screen, col, (dx - 2, dy - 2, 4, 4))

        # Other players
        for p in self.players.values():
            if self.player and p["id"] == self.player["id"]:
                continue
            ox, oy = self.world_to_minimap(p["x"], p["y"], rect)
            pygame.draw.circle(self.screen, (180, 200, 255), (ox, oy), 2)

        # Camera view rectangle (already in view space — matches rotated minimap)
        cam_x, cam_y = self.camera_origin()
        vis_w, vis_h = MAP_W // TILE, MAP_H // TILE
        vw, vh = self.view_size()
        if vw > 0 and vh > 0:
            vx0 = rect.x + int(cam_x * rect.w / vw)
            vy0 = rect.y + int(cam_y * rect.h / vh)
            vx1 = rect.x + int((cam_x + vis_w) * rect.w / vw)
            vy1 = rect.y + int((cam_y + vis_h) * rect.h / vh)
            view = pygame.Rect(vx0, vy0, max(2, vx1 - vx0), max(2, vy1 - vy0))
            pygame.draw.rect(self.screen, (255, 255, 255), view, 1)

        # You are here
        px, py = self.player_xy()
        mx, my = self.world_to_minimap(px, py, rect)
        pygame.draw.circle(self.screen, (40, 40, 40), (mx, my), 4)
        pygame.draw.circle(self.screen, (255, 80, 70), (mx, my), 3)

        hint = self.font_tiny.render("Click walk · Right map · M travel", True, (200, 210, 230))
        self.screen.blit(hint, (rect.x + 4, rect.bottom - 14))

    def world_map_view_rect(self):
        return pygame.Rect(110, 40, 780, 560)

    def world_map_canvas_rect(self):
        box = self.world_map_view_rect()
        return pygame.Rect(box.x + 20, box.y + 70, 700, 430)

    def clamp_world_map_scroll(self):
        scale = self.world_map_scale
        canvas = self.world_map_canvas_rect()
        view_w = max(1, canvas.w // scale)
        view_h = max(1, canvas.h // scale)
        max_x = max(0, self.world_w - view_w)
        max_y = max(0, self.world_h - view_h)
        self.world_map_scroll[0] = max(0, min(max_x, int(self.world_map_scroll[0])))
        self.world_map_scroll[1] = max(0, min(max_y, int(self.world_map_scroll[1])))

    def draw_world_map_modal(self):
        box = self.world_map_view_rect()
        canvas = self.world_map_canvas_rect()
        pygame.draw.rect(self.screen, (14, 18, 26), box, border_radius=8)
        pygame.draw.rect(self.screen, (120, 170, 220), box, 2, border_radius=8)
        title = self.font_big.render("World Map", True, WHITE)
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
                pygame.draw.rect(
                    self.screen, col,
                    (canvas.x + tx * scale, canvas.y + ty * scale, scale, scale),
                )

        # Destination pins
        for dest in TRAVEL_DESTINATIONS:
            dx = dest["x"] - ox
            dy = dest["y"] - oy
            if 0 <= dx <= view_w and 0 <= dy <= view_h:
                px = canvas.x + dx * scale + scale // 2
                py = canvas.y + dy * scale + scale // 2
                if dest["kind"] == "monster":
                    mdef = MONSTERS.get(dest.get("monster") or "", {})
                    col = self.monster_threat_color(mdef.get("level", 1))
                    pygame.draw.circle(self.screen, col, (px, py), 3)
                else:
                    pygame.draw.rect(self.screen, (255, 220, 120), (px - 2, py - 2, 4, 4))

        # Player marker
        if self.player:
            px, py = self.player_xy()
            dx, dy = px - ox, py - oy
            if 0 <= dx <= view_w and 0 <= dy <= view_h:
                mx = canvas.x + dx * scale + scale // 2
                my = canvas.y + dy * scale + scale // 2
                pygame.draw.circle(self.screen, (40, 40, 40), (mx, my), 5)
                pygame.draw.circle(self.screen, (255, 80, 70), (mx, my), 4)

        foot = self.font_tiny.render(
            "Right-click the corner minimap for a quick walk  ·  Press M for Travel list",
            True, (140, 138, 120),
        )
        self.screen.blit(foot, (box.x + 20, box.bottom - 28))

    def handle_world_map_click(self, mx, my, button=1):
        box = self.world_map_view_rect()
        canvas = self.world_map_canvas_rect()
        if not box.collidepoint(mx, my):
            self.show_world_map = False
            self.world_map_drag = None
            return
        if button == 1 and canvas.collidepoint(mx, my):
            # Start drag; short clicks still walk (mouseup not tracked — walk on click)
            self.world_map_drag = (mx, my, self.world_map_scroll[0], self.world_map_scroll[1])
            scale = self.world_map_scale
            ox, oy = self.world_map_scroll
            wx = ox + (mx - canvas.x) // scale
            wy = oy + (my - canvas.y) // scale
            wx = max(0, min(self.world_w - 1, wx))
            wy = max(0, min(self.world_h - 1, wy))
            goals = set()
            if self.tile_walkable(wx, wy):
                goals.add((wx, wy))
            goals |= self.adjacent_goals(wx, wy)
            if not goals:
                for r in range(1, 8):
                    for dx in range(-r, r + 1):
                        for dy in (-r, r):
                            if self.tile_walkable(wx + dx, wy + dy):
                                goals.add((wx + dx, wy + dy))
                        for dy in range(-r + 1, r):
                            for dx in (-r, r):
                                if self.tile_walkable(wx + dx, wy + dy):
                                    goals.add((wx + dx, wy + dy))
                    if goals:
                        break
            if goals:
                self.show_world_map = False
                self.world_map_drag = None
                self.chat_log.append("Walking toward map marker...")
                self.chat_log = self.chat_log[-8:]
                self.walk_and_act(goals, None)

    def draw_dungeon_prompt(self):
        box = pygame.Rect(250, 120, 560, 420)
        self.dungeon_prompt_rects = {"box": box}
        pygame.draw.rect(self.screen, (16, 18, 28), box, border_radius=10)
        pygame.draw.rect(self.screen, (90, 160, 210), box, 2, border_radius=10)
        title = self.font_big.render("Enter Tidehollow Cave?", True, WHITE)
        self.screen.blit(title, (box.x + 28, box.y + 22))

        rules = [
            "Private 10-floor instance — only you are inside.",
            "Clear every beast on a floor to open the next.",
            "Floors scale from combat level 10 up to 80.",
            "Dying or pressing Esc returns you to Harbourreach.",
            "Finish floor 10 for rare loot and the Tidehollow Medal.",
            "Progress does not save if you leave early.",
        ]
        y = box.y + 72
        for line in rules:
            self.screen.blit(self.font.render(f"•  {line}", True, (220, 215, 200)), (box.x + 28, y))
            y += 36

        tip = self.font_tiny.render(
            "Bring food and potions. Mythos gear can also drop from the Adamant Dragon.",
            True, GREY,
        )
        self.screen.blit(tip, (box.x + 28, box.bottom - 100))

        yes = pygame.Rect(box.x + 28, box.bottom - 64, 220, 40)
        no = pygame.Rect(box.right - 248, box.bottom - 64, 220, 40)
        self.dungeon_prompt_rects["yes"] = yes
        self.dungeon_prompt_rects["no"] = no
        pygame.draw.rect(self.screen, (40, 100, 130), yes, border_radius=6)
        pygame.draw.rect(self.screen, (90, 180, 220), yes, 1, border_radius=6)
        pygame.draw.rect(self.screen, (70, 45, 40), no, border_radius=6)
        pygame.draw.rect(self.screen, (180, 90, 70), no, 1, border_radius=6)
        yt = self.font.render("Enter cave", True, WHITE)
        nt = self.font.render("Stay outside", True, WHITE)
        self.screen.blit(yt, (yes.centerx - yt.get_width() // 2, yes.centery - yt.get_height() // 2))
        self.screen.blit(nt, (no.centerx - nt.get_width() // 2, no.centery - nt.get_height() // 2))

    def handle_dungeon_prompt_click(self, mx, my):
        yes = self.dungeon_prompt_rects.get("yes")
        no = self.dungeon_prompt_rects.get("no")
        box = self.dungeon_prompt_rects.get("box")
        if yes and yes.collidepoint(mx, my):
            self.dungeon_prompt = None
            self.net.send("ENTER_DUNGEON")
            return
        if no and no.collidepoint(mx, my):
            self.dungeon_prompt = None
            return
        if box and not box.collidepoint(mx, my):
            self.dungeon_prompt = None

    def draw_travel_modal(self):
        box = pygame.Rect(140, 40, 720, 580)
        pygame.draw.rect(self.screen, (16, 20, 28), box)
        pygame.draw.rect(self.screen, (120, 170, 220), box, 2)
        title = self.font_big.render("Travel", True, WHITE)
        self.screen.blit(title, (box.x + 20, box.y + 12))
        self.screen.blit(
            self.font_small.render(
                "Click a destination to walk there  ·  Scroll / drag bar  ·  Esc closes",
                True, GREY,
            ),
            (box.x + 20, box.y + 46),
        )

        places = [d for d in TRAVEL_DESTINATIONS if d["kind"] == "place"]
        monsters = [d for d in TRAVEL_DESTINATIONS if d["kind"] == "monster"]
        self.travel_btn_rects = []

        # Leave room for the scrollbar on the right edge of the panel
        col_w = (box.w - 72) // 2
        left_x = box.x + 20
        right_x = box.x + 36 + col_w
        hdr_y = box.y + 74
        self.screen.blit(self.font.render("Places", True, (255, 220, 140)), (left_x, hdr_y))
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
                pygame.draw.rect(self.screen, border, row, 1, border_radius=6)
                self.travel_btn_rects.append((row, dest))
                label = dest["label"]
                if lvl is not None:
                    label = f"{label}  ·  Lv {lvl}"
                self.screen.blit(self.font_small.render(label, True, WHITE), (row.x + 12, row.y + 6))
                blurb = dest.get("blurb") or ""
                self.screen.blit(self.font_tiny.render(blurb, True, GREY), (row.x + 12, row.y + 24))

        draw_btns(places, left_x)
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

    def handle_travel_click(self, mx, my):
        box = pygame.Rect(140, 40, 720, 580)
        if not box.collidepoint(mx, my):
            self.show_travel = False
            return
        clip = (self.travel_scroll_meta or {}).get("clip")
        if clip is not None and not clip.collidepoint(mx, my):
            return  # title / footer / scrollbar — ignore
        for rect, dest in self.travel_btn_rects:
            if rect.collidepoint(mx, my):
                self.travel_to_destination(dest)
                return

    def _travel_scrollbar_mousedown(self, pos):
        meta = self.travel_scroll_meta
        if not meta or meta.get("max_scroll", 0) <= 0:
            return False
        track = meta.get("track")
        thumb = meta.get("thumb")
        if thumb is not None and thumb.collidepoint(pos):
            self.travel_drag = {"y0": pos[1], "scroll0": self.travel_scroll}
            return True
        if track is not None and track.collidepoint(pos):
            # Jump scrollbar toward click
            view_h = meta["view_h"]
            max_scroll = meta["max_scroll"]
            thumb_h = thumb.h if thumb is not None else 28
            rel = (pos[1] - meta["list_top"] - thumb_h / 2) / max(1, view_h - thumb_h)
            self.travel_scroll = max(0, min(max_scroll, rel * max_scroll))
            self.travel_drag = {"y0": pos[1], "scroll0": self.travel_scroll}
            return True
        return False

    def _travel_scrollbar_drag(self, pos):
        meta = self.travel_scroll_meta
        drag = self.travel_drag
        if not meta or not drag or meta.get("max_scroll", 0) <= 0:
            return
        view_h = meta["view_h"]
        max_scroll = meta["max_scroll"]
        thumb = meta.get("thumb")
        thumb_h = thumb.h if thumb is not None else 28
        span = max(1, view_h - thumb_h)
        dy = pos[1] - drag["y0"]
        self.travel_scroll = max(0, min(max_scroll, drag["scroll0"] + dy * max_scroll / span))

    def draw_fire_prompt(self):
        prompt = self.fire_prompt or {}
        name = prompt.get("name", "logs")
        box = pygame.Rect(340, 240, 420, 200)
        self.fire_prompt_rects = {"box": box}
        pygame.draw.rect(self.screen, (18, 22, 30), box, border_radius=8)
        pygame.draw.rect(self.screen, (255, 170, 80), box, 2, border_radius=8)
        title = self.font_big.render("Light a fire?", True, WHITE)
        self.screen.blit(title, (box.x + 24, box.y + 22))
        body = self.font.render(
            f"Use your tinderbox on the {name.lower()}?",
            True, (220, 210, 190),
        )
        self.screen.blit(body, (box.x + 24, box.y + 70))
        tip = self.font_tiny.render(
            "The fire appears on your tile and can cook food.",
            True, GREY,
        )
        self.screen.blit(tip, (box.x + 24, box.y + 100))

        yes = pygame.Rect(box.x + 24, box.bottom - 58, 170, 36)
        no = pygame.Rect(box.right - 194, box.bottom - 58, 170, 36)
        self.fire_prompt_rects["yes"] = yes
        self.fire_prompt_rects["no"] = no
        pygame.draw.rect(self.screen, (50, 110, 60), yes, border_radius=6)
        pygame.draw.rect(self.screen, GREEN, yes, 1, border_radius=6)
        pygame.draw.rect(self.screen, (70, 45, 40), no, border_radius=6)
        pygame.draw.rect(self.screen, (180, 90, 70), no, 1, border_radius=6)
        yt = self.font.render("Yes — light fire", True, WHITE)
        nt = self.font.render("No", True, WHITE)
        self.screen.blit(yt, (yes.centerx - yt.get_width() // 2, yes.centery - yt.get_height() // 2))
        self.screen.blit(nt, (no.centerx - nt.get_width() // 2, no.centery - nt.get_height() // 2))

    def draw_combat_style_prompt(self):
        """First attack of the session — pick which combat skill to train."""
        box = pygame.Rect(300, 180, 500, 340)
        self.combat_style_prompt_rects = {"box": box}
        pygame.draw.rect(self.screen, (18, 22, 30), box, border_radius=8)
        pygame.draw.rect(self.screen, (230, 180, 90), box, 2, border_radius=8)
        title = self.font_big.render("What do you want to train?", True, WHITE)
        self.screen.blit(title, (box.x + 24, box.y + 20))
        body = self.font.render("Choose the skill that receives combat XP.", True, (220, 210, 190))
        self.screen.blit(body, (box.x + 24, box.y + 58))
        tip = self.font_tiny.render(
            "You can change this later on the Combat tab (keys 1–5).",
            True, GREY,
        )
        self.screen.blit(tip, (box.x + 24, box.y + 88))

        has_bow = self.player_using_bow()
        options = (
            ("attack", "Attack", "1", "Accuracy / hit chance"),
            ("strength", "Strength", "2", "Heavier hits"),
            ("defence", "Defence", "3", "Take less damage"),
            ("hitpoints", "Hitpoints", "4", "More max HP"),
            ("archery", "Archery", "5", "Ranged (bow only)"),
        )
        y = box.y + 118
        for style, label, hot, blurb in options:
            row = pygame.Rect(box.x + 24, y, box.w - 48, 36)
            locked = (has_bow and style != "archery") or (not has_bow and style == "archery")
            if locked:
                bg, border, col = (28, 30, 36), (55, 58, 68), (100, 100, 110)
            else:
                bg, border, col = (42, 58, 78), (140, 180, 230), WHITE
                self.combat_style_prompt_rects[style] = row
            pygame.draw.rect(self.screen, bg, row, border_radius=6)
            pygame.draw.rect(self.screen, border, row, 1, border_radius=6)
            self.screen.blit(self.font.render(f"{hot}  {label}", True, col), (row.x + 12, row.y + 8))
            self.screen.blit(self.font_tiny.render(blurb, True, GREY if locked else (180, 190, 210)), (row.x + 160, row.y + 12))
            y += 40

        cancel = pygame.Rect(box.centerx - 60, box.bottom - 42, 120, 28)
        self.combat_style_prompt_rects["cancel"] = cancel
        pygame.draw.rect(self.screen, (60, 40, 40), cancel, border_radius=5)
        pygame.draw.rect(self.screen, (180, 90, 70), cancel, 1, border_radius=5)
        ct = self.font_small.render("Cancel (Esc)", True, WHITE)
        self.screen.blit(ct, (cancel.centerx - ct.get_width() // 2, cancel.centery - ct.get_height() // 2))

    def handle_combat_style_prompt_click(self, mx, my):
        rects = self.combat_style_prompt_rects or {}
        box = rects.get("box")
        if rects.get("cancel") and rects["cancel"].collidepoint(mx, my):
            self.combat_style_prompt = None
            return
        for style in ("attack", "strength", "defence", "hitpoints", "archery"):
            r = rects.get(style)
            if r and r.collidepoint(mx, my):
                self.confirm_combat_style(style)
                return
        if box and not box.collidepoint(mx, my):
            self.combat_style_prompt = None

    def draw_drop_prompt(self):
        prompt = self.drop_prompt or {}
        name = prompt.get("name", "item")
        qty = max(1, int(prompt.get("qty") or 1))
        box = pygame.Rect(340, 230, 420, 220)
        self.drop_prompt_rects = {"box": box}
        pygame.draw.rect(self.screen, (18, 22, 30), box, border_radius=8)
        pygame.draw.rect(self.screen, (200, 150, 90), box, 2, border_radius=8)
        title = self.font_big.render("Drop item?", True, WHITE)
        self.screen.blit(title, (box.x + 24, box.y + 22))
        body = self.font.render(f"Drop {name}?", True, (220, 210, 190))
        self.screen.blit(body, (box.x + 24, box.y + 70))
        tip = self.font_tiny.render(
            f"You have {qty} in this stack." if qty > 1 else "Drop onto the ground at your feet.",
            True, GREY,
        )
        self.screen.blit(tip, (box.x + 24, box.y + 100))

        one = pygame.Rect(box.x + 24, box.bottom - 58, 110, 36)
        self.drop_prompt_rects["one"] = one
        pygame.draw.rect(self.screen, (50, 90, 120), one, border_radius=6)
        pygame.draw.rect(self.screen, (120, 170, 210), one, 1, border_radius=6)
        ot = self.font.render("Drop 1", True, WHITE)
        self.screen.blit(ot, (one.centerx - ot.get_width() // 2, one.centery - ot.get_height() // 2))

        if qty > 1:
            allb = pygame.Rect(box.x + 148, box.bottom - 58, 140, 36)
            self.drop_prompt_rects["all"] = allb
            pygame.draw.rect(self.screen, (110, 70, 40), allb, border_radius=6)
            pygame.draw.rect(self.screen, (220, 150, 80), allb, 1, border_radius=6)
            at = self.font.render(f"Drop all ({qty})", True, WHITE)
            self.screen.blit(at, (allb.centerx - at.get_width() // 2, allb.centery - at.get_height() // 2))
            cancel = pygame.Rect(box.right - 118, box.bottom - 58, 94, 36)
        else:
            cancel = pygame.Rect(box.right - 118, box.bottom - 58, 94, 36)
        self.drop_prompt_rects["cancel"] = cancel
        pygame.draw.rect(self.screen, (70, 45, 40), cancel, border_radius=6)
        pygame.draw.rect(self.screen, (180, 90, 70), cancel, 1, border_radius=6)
        ct = self.font.render("Cancel", True, WHITE)
        self.screen.blit(ct, (cancel.centerx - ct.get_width() // 2, cancel.centery - ct.get_height() // 2))

    def draw_arrow_prompt(self):
        prompt = self.arrow_prompt or {}
        name = prompt.get("name", "arrows")
        qty = max(1, int(prompt.get("qty") or 1))
        box = pygame.Rect(320, 210, 460, 240)
        self.arrow_prompt_rects = {"box": box}
        pygame.draw.rect(self.screen, (18, 22, 30), box, border_radius=8)
        pygame.draw.rect(self.screen, (120, 180, 220), box, 2, border_radius=8)
        title = self.font_big.render("Arrows", True, WHITE)
        self.screen.blit(title, (box.x + 24, box.y + 22))
        body = self.font.render(f"{name}  ×{qty}", True, (220, 210, 190))
        self.screen.blit(body, (box.x + 24, box.y + 70))
        tip = self.font_tiny.render(
            "Load into your quiver, or drop onto the ground.",
            True, GREY,
        )
        self.screen.blit(tip, (box.x + 24, box.y + 100))

        quiver = pygame.Rect(box.x + 24, box.bottom - 58, 170, 36)
        self.arrow_prompt_rects["quiver"] = quiver
        pygame.draw.rect(self.screen, (40, 90, 70), quiver, border_radius=6)
        pygame.draw.rect(self.screen, (100, 200, 140), quiver, 1, border_radius=6)
        qt = self.font.render("Add to quiver", True, WHITE)
        self.screen.blit(qt, (quiver.centerx - qt.get_width() // 2, quiver.centery - qt.get_height() // 2))

        drop = pygame.Rect(box.x + 210, box.bottom - 58, 110, 36)
        self.arrow_prompt_rects["drop"] = drop
        pygame.draw.rect(self.screen, (110, 70, 40), drop, border_radius=6)
        pygame.draw.rect(self.screen, (220, 150, 80), drop, 1, border_radius=6)
        dt = self.font.render("Drop…", True, WHITE)
        self.screen.blit(dt, (drop.centerx - dt.get_width() // 2, drop.centery - dt.get_height() // 2))

        cancel = pygame.Rect(box.right - 118, box.bottom - 58, 94, 36)
        self.arrow_prompt_rects["cancel"] = cancel
        pygame.draw.rect(self.screen, (70, 45, 40), cancel, border_radius=6)
        pygame.draw.rect(self.screen, (180, 90, 70), cancel, 1, border_radius=6)
        ct = self.font.render("Cancel", True, WHITE)
        self.screen.blit(ct, (cancel.centerx - ct.get_width() // 2, cancel.centery - ct.get_height() // 2))

    def draw_tip_prompt(self):
        prompt = self.tip_prompt or {}
        name = prompt.get("name", "arrowtips")
        qty = max(1, int(prompt.get("qty") or 1))
        has_box = bool((self.player or {}).get("has_tip_box"))
        box = pygame.Rect(320, 210, 460, 240)
        self.tip_prompt_rects = {"box": box}
        pygame.draw.rect(self.screen, (18, 22, 30), box, border_radius=8)
        pygame.draw.rect(self.screen, (200, 170, 90), box, 2, border_radius=8)
        title = self.font_big.render("Arrowtips", True, WHITE)
        self.screen.blit(title, (box.x + 24, box.y + 22))
        body = self.font.render(f"{name}  ×{qty}", True, (220, 210, 190))
        self.screen.blit(body, (box.x + 24, box.y + 70))
        tip = self.font_tiny.render(
            "Pack into your Arrowtip Box, or drop onto the ground."
            if has_box else "Buy an Arrowtip Box from Elena to store these.",
            True, GREY,
        )
        self.screen.blit(tip, (box.x + 24, box.y + 100))

        pack = pygame.Rect(box.x + 24, box.bottom - 58, 170, 36)
        self.tip_prompt_rects["box_pack"] = pack
        pygame.draw.rect(self.screen, (90, 80, 40) if has_box else (50, 50, 55), pack, border_radius=6)
        pygame.draw.rect(self.screen, (220, 190, 100) if has_box else (90, 90, 100), pack, 1, border_radius=6)
        pt = self.font.render("Add to tip box", True, WHITE if has_box else GREY)
        self.screen.blit(pt, (pack.centerx - pt.get_width() // 2, pack.centery - pt.get_height() // 2))

        drop = pygame.Rect(box.x + 210, box.bottom - 58, 110, 36)
        self.tip_prompt_rects["drop"] = drop
        pygame.draw.rect(self.screen, (110, 70, 40), drop, border_radius=6)
        pygame.draw.rect(self.screen, (220, 150, 80), drop, 1, border_radius=6)
        dt = self.font.render("Drop…", True, WHITE)
        self.screen.blit(dt, (drop.centerx - dt.get_width() // 2, drop.centery - dt.get_height() // 2))

        cancel = pygame.Rect(box.right - 118, box.bottom - 58, 94, 36)
        self.tip_prompt_rects["cancel"] = cancel
        pygame.draw.rect(self.screen, (70, 45, 40), cancel, border_radius=6)
        pygame.draw.rect(self.screen, (180, 90, 70), cancel, 1, border_radius=6)
        ct = self.font.render("Cancel", True, WHITE)
        self.screen.blit(ct, (cancel.centerx - ct.get_width() // 2, cancel.centery - ct.get_height() // 2))

    def draw_food_prompt(self):
        prompt = self.food_prompt or {}
        name = prompt.get("name", "food")
        qty = max(1, int(prompt.get("qty") or 1))
        has_bag = bool((self.player or {}).get("has_food_bag"))
        heal = int((ITEMS.get(prompt.get("item_id")) or {}).get("heal") or 0)
        box = pygame.Rect(300, 200, 500, 250)
        self.food_prompt_rects = {"box": box}
        pygame.draw.rect(self.screen, (18, 22, 30), box, border_radius=8)
        pygame.draw.rect(self.screen, (220, 160, 90), box, 2, border_radius=8)
        title = self.font_big.render("Cooked fish", True, WHITE)
        self.screen.blit(title, (box.x + 24, box.y + 22))
        body = self.font.render(f"{name}  ×{qty}", True, (220, 210, 190))
        self.screen.blit(body, (box.x + 24, box.y + 70))
        tip = self.font_tiny.render(
            f"Heals {heal} HP. Eat now, pack into your Food Bag, or drop."
            if has_bag else f"Heals {heal} HP. Buy a Food Bag to store cooked fish.",
            True, GREY,
        )
        self.screen.blit(tip, (box.x + 24, box.y + 100))

        eat = pygame.Rect(box.x + 24, box.bottom - 58, 100, 36)
        self.food_prompt_rects["eat"] = eat
        pygame.draw.rect(self.screen, (50, 110, 60), eat, border_radius=6)
        pygame.draw.rect(self.screen, GREEN, eat, 1, border_radius=6)
        et = self.font.render("Eat", True, WHITE)
        self.screen.blit(et, (eat.centerx - et.get_width() // 2, eat.centery - et.get_height() // 2))

        pack = pygame.Rect(box.x + 136, box.bottom - 58, 150, 36)
        self.food_prompt_rects["pack"] = pack
        pygame.draw.rect(self.screen, (90, 80, 40) if has_bag else (50, 50, 55), pack, border_radius=6)
        pygame.draw.rect(self.screen, (220, 190, 100) if has_bag else (90, 90, 100), pack, 1, border_radius=6)
        pt = self.font.render("Pack in bag", True, WHITE if has_bag else GREY)
        self.screen.blit(pt, (pack.centerx - pt.get_width() // 2, pack.centery - pt.get_height() // 2))

        drop = pygame.Rect(box.x + 300, box.bottom - 58, 90, 36)
        self.food_prompt_rects["drop"] = drop
        pygame.draw.rect(self.screen, (110, 70, 40), drop, border_radius=6)
        pygame.draw.rect(self.screen, (220, 150, 80), drop, 1, border_radius=6)
        dt = self.font.render("Drop…", True, WHITE)
        self.screen.blit(dt, (drop.centerx - dt.get_width() // 2, drop.centery - dt.get_height() // 2))

        cancel = pygame.Rect(box.right - 110, box.bottom - 58, 90, 36)
        self.food_prompt_rects["cancel"] = cancel
        pygame.draw.rect(self.screen, (70, 45, 40), cancel, border_radius=6)
        pygame.draw.rect(self.screen, (180, 90, 70), cancel, 1, border_radius=6)
        ct = self.font.render("Cancel", True, WHITE)
        self.screen.blit(ct, (cancel.centerx - ct.get_width() // 2, cancel.centery - ct.get_height() // 2))

    def draw_raw_prompt(self):
        prompt = self.raw_prompt or {}
        name = prompt.get("name", "raw fish")
        qty = max(1, int(prompt.get("qty") or 1))
        has_bag = bool((self.player or {}).get("has_raw_bag"))
        box = pygame.Rect(320, 210, 460, 240)
        self.raw_prompt_rects = {"box": box}
        pygame.draw.rect(self.screen, (18, 22, 30), box, border_radius=8)
        pygame.draw.rect(self.screen, (100, 170, 200), box, 2, border_radius=8)
        title = self.font_big.render("Raw fish", True, WHITE)
        self.screen.blit(title, (box.x + 24, box.y + 22))
        body = self.font.render(f"{name}  ×{qty}", True, (220, 210, 190))
        self.screen.blit(body, (box.x + 24, box.y + 70))
        tip = self.font_tiny.render(
            "Pack into your Raw Food Bag, or drop onto the ground."
            if has_bag else "Buy a Raw Food Bag at Harbourreach Tackle to store these.",
            True, GREY,
        )
        self.screen.blit(tip, (box.x + 24, box.y + 100))

        pack = pygame.Rect(box.x + 24, box.bottom - 58, 170, 36)
        self.raw_prompt_rects["pack"] = pack
        pygame.draw.rect(self.screen, (40, 80, 100) if has_bag else (50, 50, 55), pack, border_radius=6)
        pygame.draw.rect(self.screen, (120, 190, 220) if has_bag else (90, 90, 100), pack, 1, border_radius=6)
        pt = self.font.render("Add to raw bag", True, WHITE if has_bag else GREY)
        self.screen.blit(pt, (pack.centerx - pt.get_width() // 2, pack.centery - pt.get_height() // 2))

        drop = pygame.Rect(box.x + 210, box.bottom - 58, 110, 36)
        self.raw_prompt_rects["drop"] = drop
        pygame.draw.rect(self.screen, (110, 70, 40), drop, border_radius=6)
        pygame.draw.rect(self.screen, (220, 150, 80), drop, 1, border_radius=6)
        dt = self.font.render("Drop…", True, WHITE)
        self.screen.blit(dt, (drop.centerx - dt.get_width() // 2, drop.centery - dt.get_height() // 2))

        cancel = pygame.Rect(box.right - 118, box.bottom - 58, 94, 36)
        self.raw_prompt_rects["cancel"] = cancel
        pygame.draw.rect(self.screen, (70, 45, 40), cancel, border_radius=6)
        pygame.draw.rect(self.screen, (180, 90, 70), cancel, 1, border_radius=6)
        ct = self.font.render("Cancel", True, WHITE)
        self.screen.blit(ct, (cancel.centerx - ct.get_width() // 2, cancel.centery - ct.get_height() // 2))

    def draw_food_bag_prompt(self):
        tot = int((self.player or {}).get("food_bag_total") or 0)
        box = pygame.Rect(320, 210, 460, 240)
        self.food_bag_prompt_rects = {"box": box}
        pygame.draw.rect(self.screen, (18, 22, 30), box, border_radius=8)
        pygame.draw.rect(self.screen, (220, 160, 90), box, 2, border_radius=8)
        title = self.font_big.render("Food Bag", True, WHITE)
        self.screen.blit(title, (box.x + 24, box.y + 22))
        body = self.font.render(f"Packed fish: {tot}", True, (220, 210, 190))
        self.screen.blit(body, (box.x + 24, box.y + 70))
        tip = self.font_tiny.render(
            "Eat uses highest-heal first. Pack scoops cooked fish; Unpack empties the bag.",
            True, GREY,
        )
        self.screen.blit(tip, (box.x + 24, box.y + 100))

        eat = pygame.Rect(box.x + 24, box.bottom - 58, 100, 36)
        self.food_bag_prompt_rects["eat"] = eat
        pygame.draw.rect(self.screen, (50, 110, 60), eat, border_radius=6)
        pygame.draw.rect(self.screen, GREEN, eat, 1, border_radius=6)
        et = self.font.render("Eat 1", True, WHITE)
        self.screen.blit(et, (eat.centerx - et.get_width() // 2, eat.centery - et.get_height() // 2))

        pack = pygame.Rect(box.x + 136, box.bottom - 58, 100, 36)
        self.food_bag_prompt_rects["pack"] = pack
        pygame.draw.rect(self.screen, (90, 80, 40), pack, border_radius=6)
        pygame.draw.rect(self.screen, (220, 190, 100), pack, 1, border_radius=6)
        pt = self.font.render("Pack", True, WHITE)
        self.screen.blit(pt, (pack.centerx - pt.get_width() // 2, pack.centery - pt.get_height() // 2))

        unpack = pygame.Rect(box.x + 248, box.bottom - 58, 100, 36)
        self.food_bag_prompt_rects["unpack"] = unpack
        can = tot > 0
        pygame.draw.rect(self.screen, (70, 80, 110) if can else (50, 50, 55), unpack, border_radius=6)
        pygame.draw.rect(self.screen, (140, 170, 220) if can else (90, 90, 100), unpack, 1, border_radius=6)
        ut = self.font.render("Unpack", True, WHITE if can else GREY)
        self.screen.blit(ut, (unpack.centerx - ut.get_width() // 2, unpack.centery - ut.get_height() // 2))

        cancel = pygame.Rect(box.right - 118, box.bottom - 58, 94, 36)
        self.food_bag_prompt_rects["cancel"] = cancel
        pygame.draw.rect(self.screen, (70, 45, 40), cancel, border_radius=6)
        pygame.draw.rect(self.screen, (180, 90, 70), cancel, 1, border_radius=6)
        ct = self.font.render("Cancel", True, WHITE)
        self.screen.blit(ct, (cancel.centerx - ct.get_width() // 2, cancel.centery - ct.get_height() // 2))

    def draw_storage_bag_prompt(self):
        prompt = self.storage_bag_prompt or {}
        label = prompt.get("label") or "Bag"
        tot = int(prompt.get("total") or 0)
        # Refresh total from live player state
        key_map = {
            "arrowtip_box": "tip_box_total",
            "raw_food_bag": "raw_bag_total",
            "mining_bag": "mining_bag_total",
            "log_bag": "log_bag_total",
            "fletch_pouch": "fletch_pouch_total",
            "potion_pouch": "potion_pouch_total",
            "gem_bag": "gem_bag_total",
        }
        tot_key = key_map.get(prompt.get("item_id"))
        if tot_key:
            tot = int((self.player or {}).get(tot_key) or 0)
        box = pygame.Rect(320, 210, 460, 240)
        self.storage_bag_prompt_rects = {"box": box}
        pygame.draw.rect(self.screen, (18, 22, 30), box, border_radius=8)
        pygame.draw.rect(self.screen, (140, 170, 210), box, 2, border_radius=8)
        title = self.font_big.render(label, True, WHITE)
        self.screen.blit(title, (box.x + 24, box.y + 22))
        body = self.font.render(f"Stored: {tot}", True, (220, 210, 190))
        self.screen.blit(body, (box.x + 24, box.y + 70))
        tip = self.font_tiny.render(
            "Pack scoops matching items from inventory. Unpack empties the bag into free slots.",
            True, GREY,
        )
        self.screen.blit(tip, (box.x + 24, box.y + 100))

        pack = pygame.Rect(box.x + 24, box.bottom - 58, 140, 36)
        self.storage_bag_prompt_rects["pack"] = pack
        pygame.draw.rect(self.screen, (50, 90, 70), pack, border_radius=6)
        pygame.draw.rect(self.screen, (100, 200, 140), pack, 1, border_radius=6)
        pt = self.font.render("Pack all", True, WHITE)
        self.screen.blit(pt, (pack.centerx - pt.get_width() // 2, pack.centery - pt.get_height() // 2))

        unpack = pygame.Rect(box.x + 180, box.bottom - 58, 150, 36)
        self.storage_bag_prompt_rects["unpack"] = unpack
        can = tot > 0
        pygame.draw.rect(self.screen, (70, 80, 110) if can else (50, 50, 55), unpack, border_radius=6)
        pygame.draw.rect(self.screen, (140, 170, 220) if can else (90, 90, 100), unpack, 1, border_radius=6)
        ut = self.font.render("Unpack all", True, WHITE if can else GREY)
        self.screen.blit(ut, (unpack.centerx - ut.get_width() // 2, unpack.centery - ut.get_height() // 2))

        cancel = pygame.Rect(box.right - 118, box.bottom - 58, 94, 36)
        self.storage_bag_prompt_rects["cancel"] = cancel
        pygame.draw.rect(self.screen, (70, 45, 40), cancel, border_radius=6)
        pygame.draw.rect(self.screen, (180, 90, 70), cancel, 1, border_radius=6)
        ct = self.font.render("Cancel", True, WHITE)
        self.screen.blit(ct, (cancel.centerx - ct.get_width() // 2, cancel.centery - ct.get_height() // 2))

    def draw_pack_prompt(self):
        prompt = self.pack_prompt or {}
        name = prompt.get("name", "item")
        qty = max(1, int(prompt.get("qty") or 1))
        bag_label = prompt.get("bag_label") or "bag"
        bag_flag = prompt.get("bag_flag") or ""
        has_bag = bool((self.player or {}).get(bag_flag)) if bag_flag else False
        box = pygame.Rect(320, 210, 460, 240)
        self.pack_prompt_rects = {"box": box}
        pygame.draw.rect(self.screen, (18, 22, 30), box, border_radius=8)
        pygame.draw.rect(self.screen, (160, 150, 100), box, 2, border_radius=8)
        title = self.font_big.render(bag_label, True, WHITE)
        self.screen.blit(title, (box.x + 24, box.y + 22))
        body = self.font.render(f"{name}  ×{qty}", True, (220, 210, 190))
        self.screen.blit(body, (box.x + 24, box.y + 70))
        tip = self.font_tiny.render(
            f"Pack into your {bag_label}, or drop onto the ground."
            if has_bag else (prompt.get("buy_hint") or f"Buy a {bag_label} to store these."),
            True, GREY,
        )
        self.screen.blit(tip, (box.x + 24, box.y + 100))

        pack = pygame.Rect(box.x + 24, box.bottom - 58, 170, 36)
        self.pack_prompt_rects["pack"] = pack
        pygame.draw.rect(self.screen, (70, 90, 50) if has_bag else (50, 50, 55), pack, border_radius=6)
        pygame.draw.rect(self.screen, (160, 200, 100) if has_bag else (90, 90, 100), pack, 1, border_radius=6)
        pt = self.font.render(f"Add to {bag_label.split()[0].lower()}", True, WHITE if has_bag else GREY)
        self.screen.blit(pt, (pack.centerx - pt.get_width() // 2, pack.centery - pt.get_height() // 2))

        drop = pygame.Rect(box.x + 210, box.bottom - 58, 110, 36)
        self.pack_prompt_rects["drop"] = drop
        pygame.draw.rect(self.screen, (110, 70, 40), drop, border_radius=6)
        pygame.draw.rect(self.screen, (220, 150, 80), drop, 1, border_radius=6)
        dt = self.font.render("Drop…", True, WHITE)
        self.screen.blit(dt, (drop.centerx - dt.get_width() // 2, drop.centery - dt.get_height() // 2))

        cancel = pygame.Rect(box.right - 118, box.bottom - 58, 94, 36)
        self.pack_prompt_rects["cancel"] = cancel
        pygame.draw.rect(self.screen, (70, 45, 40), cancel, border_radius=6)
        pygame.draw.rect(self.screen, (180, 90, 70), cancel, 1, border_radius=6)
        ct = self.font.render("Cancel", True, WHITE)
        self.screen.blit(ct, (cancel.centerx - ct.get_width() // 2, cancel.centery - ct.get_height() // 2))

    def draw_log_prompt(self):
        prompt = self.log_prompt or {}
        name = prompt.get("name", "logs")
        qty = max(1, int(prompt.get("qty") or 1))
        has_bag = bool((self.player or {}).get("has_log_bag"))
        can_fire = bool(prompt.get("can_fire"))
        can_fletch = bool(prompt.get("can_fletch"))
        box = pygame.Rect(300, 190, 500, 270)
        self.log_prompt_rects = {"box": box}
        pygame.draw.rect(self.screen, (18, 22, 30), box, border_radius=8)
        pygame.draw.rect(self.screen, (180, 130, 70), box, 2, border_radius=8)
        title = self.font_big.render("Logs", True, WHITE)
        self.screen.blit(title, (box.x + 24, box.y + 22))
        body = self.font.render(f"{name}  ×{qty}", True, (220, 210, 190))
        self.screen.blit(body, (box.x + 24, box.y + 70))
        tip = self.font_tiny.render(
            "Light a fire, fletch, pack into your Log Bag, or drop."
            if has_bag else "Buy a Log Bag (General Store / Elena) to store these.",
            True, GREY,
        )
        self.screen.blit(tip, (box.x + 24, box.y + 100))

        x = box.x + 24
        y = box.bottom - 58
        if can_fire:
            fire = pygame.Rect(x, y, 100, 36)
            self.log_prompt_rects["fire"] = fire
            pygame.draw.rect(self.screen, (120, 70, 40), fire, border_radius=6)
            pygame.draw.rect(self.screen, (255, 160, 70), fire, 1, border_radius=6)
            ft = self.font.render("Fire", True, WHITE)
            self.screen.blit(ft, (fire.centerx - ft.get_width() // 2, fire.centery - ft.get_height() // 2))
            x = fire.right + 10
        if can_fletch:
            fl = pygame.Rect(x, y, 100, 36)
            self.log_prompt_rects["fletch"] = fl
            pygame.draw.rect(self.screen, (60, 90, 70), fl, border_radius=6)
            pygame.draw.rect(self.screen, (120, 200, 140), fl, 1, border_radius=6)
            flt = self.font.render("Fletch", True, WHITE)
            self.screen.blit(flt, (fl.centerx - flt.get_width() // 2, fl.centery - flt.get_height() // 2))
            x = fl.right + 10
        pack = pygame.Rect(x, y, 110, 36)
        self.log_prompt_rects["pack"] = pack
        pygame.draw.rect(self.screen, (70, 90, 50) if has_bag else (50, 50, 55), pack, border_radius=6)
        pygame.draw.rect(self.screen, (160, 200, 100) if has_bag else (90, 90, 100), pack, 1, border_radius=6)
        pt = self.font.render("Pack", True, WHITE if has_bag else GREY)
        self.screen.blit(pt, (pack.centerx - pt.get_width() // 2, pack.centery - pt.get_height() // 2))
        x = pack.right + 10

        drop = pygame.Rect(x, y, 90, 36)
        self.log_prompt_rects["drop"] = drop
        pygame.draw.rect(self.screen, (110, 70, 40), drop, border_radius=6)
        pygame.draw.rect(self.screen, (220, 150, 80), drop, 1, border_radius=6)
        dt = self.font.render("Drop…", True, WHITE)
        self.screen.blit(dt, (drop.centerx - dt.get_width() // 2, drop.centery - dt.get_height() // 2))

        cancel = pygame.Rect(box.right - 118, y, 94, 36)
        self.log_prompt_rects["cancel"] = cancel
        pygame.draw.rect(self.screen, (70, 45, 40), cancel, border_radius=6)
        pygame.draw.rect(self.screen, (180, 90, 70), cancel, 1, border_radius=6)
        ct = self.font.render("Cancel", True, WHITE)
        self.screen.blit(ct, (cancel.centerx - ct.get_width() // 2, cancel.centery - ct.get_height() // 2))

    def draw_potion_prompt(self):
        prompt = self.potion_prompt or {}
        name = prompt.get("name", "potion")
        qty = max(1, int(prompt.get("qty") or 1))
        has_bag = bool((self.player or {}).get("has_potion_pouch"))
        box = pygame.Rect(300, 200, 500, 250)
        self.potion_prompt_rects = {"box": box}
        pygame.draw.rect(self.screen, (18, 22, 30), box, border_radius=8)
        pygame.draw.rect(self.screen, (140, 100, 200), box, 2, border_radius=8)
        title = self.font_big.render("Potion", True, WHITE)
        self.screen.blit(title, (box.x + 24, box.y + 22))
        body = self.font.render(f"{name}  ×{qty}", True, (220, 210, 190))
        self.screen.blit(body, (box.x + 24, box.y + 70))
        tip = self.font_tiny.render(
            "Drink one, pack into your Potion Pouch, or drop."
            if has_bag else "Buy a Potion Pouch from Mira or the Lab to store these.",
            True, GREY,
        )
        self.screen.blit(tip, (box.x + 24, box.y + 100))

        drink = pygame.Rect(box.x + 24, box.bottom - 58, 110, 36)
        self.potion_prompt_rects["drink"] = drink
        pygame.draw.rect(self.screen, (70, 50, 100), drink, border_radius=6)
        pygame.draw.rect(self.screen, (180, 140, 240), drink, 1, border_radius=6)
        dt = self.font.render("Drink 1", True, WHITE)
        self.screen.blit(dt, (drink.centerx - dt.get_width() // 2, drink.centery - dt.get_height() // 2))

        pack = pygame.Rect(box.x + 148, box.bottom - 58, 140, 36)
        self.potion_prompt_rects["pack"] = pack
        pygame.draw.rect(self.screen, (70, 90, 50) if has_bag else (50, 50, 55), pack, border_radius=6)
        pygame.draw.rect(self.screen, (160, 200, 100) if has_bag else (90, 90, 100), pack, 1, border_radius=6)
        pt = self.font.render("Add to pouch", True, WHITE if has_bag else GREY)
        self.screen.blit(pt, (pack.centerx - pt.get_width() // 2, pack.centery - pt.get_height() // 2))

        drop = pygame.Rect(box.x + 302, box.bottom - 58, 90, 36)
        self.potion_prompt_rects["drop"] = drop
        pygame.draw.rect(self.screen, (110, 70, 40), drop, border_radius=6)
        pygame.draw.rect(self.screen, (220, 150, 80), drop, 1, border_radius=6)
        dropt = self.font.render("Drop…", True, WHITE)
        self.screen.blit(dropt, (drop.centerx - dropt.get_width() // 2, drop.centery - dropt.get_height() // 2))

        cancel = pygame.Rect(box.right - 118, box.bottom - 58, 94, 36)
        self.potion_prompt_rects["cancel"] = cancel
        pygame.draw.rect(self.screen, (70, 45, 40), cancel, border_radius=6)
        pygame.draw.rect(self.screen, (180, 90, 70), cancel, 1, border_radius=6)
        ct = self.font.render("Cancel", True, WHITE)
        self.screen.blit(ct, (cancel.centerx - ct.get_width() // 2, cancel.centery - ct.get_height() // 2))

    def draw_cook_prompt(self):
        prompt = self.cook_prompt or {}
        name = prompt.get("name", "food")
        available = max(1, int(prompt.get("available") or 1))
        box = pygame.Rect(320, 220, 460, 230)
        self.cook_prompt_rects = {"box": box}
        pygame.draw.rect(self.screen, (18, 22, 30), box, border_radius=8)
        pygame.draw.rect(self.screen, (255, 170, 90), box, 2, border_radius=8)
        title = self.font_big.render("Cook?", True, WHITE)
        self.screen.blit(title, (box.x + 24, box.y + 22))
        body = self.font.render(f"Cook {name}?", True, (220, 210, 190))
        self.screen.blit(body, (box.x + 24, box.y + 70))
        tip = self.font_tiny.render(
            f"You can cook {available} from your inventory." if available > 1
            else "Cook one portion at the fire.",
            True, GREY,
        )
        self.screen.blit(tip, (box.x + 24, box.y + 100))

        one = pygame.Rect(box.x + 24, box.bottom - 58, 110, 36)
        self.cook_prompt_rects["one"] = one
        pygame.draw.rect(self.screen, (50, 110, 60), one, border_radius=6)
        pygame.draw.rect(self.screen, GREEN, one, 1, border_radius=6)
        ot = self.font.render("Cook 1", True, WHITE)
        self.screen.blit(ot, (one.centerx - ot.get_width() // 2, one.centery - ot.get_height() // 2))

        if available > 1:
            allb = pygame.Rect(box.x + 148, box.bottom - 58, 170, 36)
            self.cook_prompt_rects["all"] = allb
            pygame.draw.rect(self.screen, (110, 80, 40), allb, border_radius=6)
            pygame.draw.rect(self.screen, (255, 170, 90), allb, 1, border_radius=6)
            at = self.font.render(f"Cook all ({available})", True, WHITE)
            self.screen.blit(at, (allb.centerx - at.get_width() // 2, allb.centery - at.get_height() // 2))
            cancel = pygame.Rect(box.right - 118, box.bottom - 58, 94, 36)
        else:
            cancel = pygame.Rect(box.right - 118, box.bottom - 58, 94, 36)
        self.cook_prompt_rects["cancel"] = cancel
        pygame.draw.rect(self.screen, (70, 45, 40), cancel, border_radius=6)
        pygame.draw.rect(self.screen, (180, 90, 70), cancel, 1, border_radius=6)
        ct = self.font.render("Cancel", True, WHITE)
        self.screen.blit(ct, (cancel.centerx - ct.get_width() // 2, cancel.centery - ct.get_height() // 2))

    def draw_wish_modal(self):
        box = pygame.Rect(280, 160, 540, 380)
        self.wish_rects = {"box": box}
        pygame.draw.rect(self.screen, (16, 22, 36), box, border_radius=10)
        pygame.draw.rect(self.screen, (120, 180, 255), box, 2, border_radius=10)
        title = self.font_big.render("Wishing Well", True, (220, 235, 255))
        self.screen.blit(title, (box.centerx - title.get_width() // 2, box.y + 18))
        unlimited = bool((self.player or {}).get("unlimited_wishes"))
        avail = bool((self.player or {}).get("wish_available", True))
        if unlimited:
            sub = "David — unlimited wishes"
        elif avail:
            sub = "You may make 1 wish today"
        else:
            sub = "You already wished today — return tomorrow"
        tip = self.font_small.render(sub, True, GREY)
        self.screen.blit(tip, (box.centerx - tip.get_width() // 2, box.y + 52))

        options = [
            ("power", "Power", "Potion often, ~half super · 5% +1 skill"),
            ("gear", "Gear", "Often steel/mithril · 5% Mythos"),
            ("gold", "Gold", "Often 5k+ · 25% chance of 10k"),
        ]
        y = box.y + 90
        for kind, label, blurb in options:
            row = pygame.Rect(box.x + 28, y, box.w - 56, 58)
            enabled = avail or unlimited
            pygame.draw.rect(self.screen, (34, 48, 70) if enabled else (28, 30, 36), row, border_radius=8)
            pygame.draw.rect(self.screen, (140, 190, 255) if enabled else (60, 60, 70), row, 1, border_radius=8)
            self.wish_rects[kind] = row
            self.screen.blit(self.font.render(label, True, WHITE if enabled else GREY), (row.x + 16, row.y + 10))
            self.screen.blit(self.font_tiny.render(blurb, True, GREY), (row.x + 16, row.y + 34))
            y += 68

        close = pygame.Rect(box.centerx - 60, box.bottom - 48, 120, 32)
        self.wish_rects["close"] = close
        pygame.draw.rect(self.screen, (50, 40, 40), close, border_radius=6)
        ct = self.font_small.render("Close", True, WHITE)
        self.screen.blit(ct, (close.centerx - ct.get_width() // 2, close.centery - ct.get_height() // 2))

    def handle_wish_click(self, mx, my):
        box = self.wish_rects.get("box")
        if box and not box.collidepoint(mx, my):
            self.show_wish = False
            return
        if self.wish_rects.get("close") and self.wish_rects["close"].collidepoint(mx, my):
            self.show_wish = False
            return
        for kind in ("power", "gear", "gold"):
            rect = self.wish_rects.get(kind)
            if rect and rect.collidepoint(mx, my):
                self.net.send("WISH", kind=kind)
                return

    def draw_wish_stat_modal(self):
        choice = self.wish_stat_choice or {}
        box = pygame.Rect(300, 180, 500, 340)
        self.wish_stat_rects = {"box": box}
        pygame.draw.rect(self.screen, (20, 18, 36), box, border_radius=10)
        pygame.draw.rect(self.screen, (255, 210, 90), box, 2, border_radius=10)
        title = self.font_big.render("Rare Wish!", True, (255, 230, 150))
        self.screen.blit(title, (box.centerx - title.get_width() // 2, box.y + 18))
        msg = self.font_small.render(choice.get("message") or "Choose a skill.", True, WHITE)
        self.screen.blit(msg, (box.centerx - msg.get_width() // 2, box.y + 58))
        y = box.y + 100
        for skill in choice.get("skills") or []:
            row = pygame.Rect(box.x + 40, y, box.w - 80, 40)
            pygame.draw.rect(self.screen, (48, 70, 50), row, border_radius=6)
            pygame.draw.rect(self.screen, (140, 220, 140), row, 1, border_radius=6)
            self.wish_stat_rects[skill] = row
            label = self.font.render(skill.title(), True, WHITE)
            self.screen.blit(label, (row.centerx - label.get_width() // 2, row.centery - label.get_height() // 2))
            y += 48

    def handle_wish_stat_click(self, mx, my):
        box = self.wish_stat_rects.get("box")
        if box and not box.collidepoint(mx, my):
            return
        for skill, rect in self.wish_stat_rects.items():
            if skill == "box":
                continue
            if rect.collidepoint(mx, my):
                self.net.send("WISH_STAT", skill=skill)
                self.wish_stat_choice = None
                return

    def draw_well_rare_fx(self, cam_x, cam_y, vis_w, vis_h, now):
        """Lightning strike + sparkles at the wishing well for rare finds."""
        import math as _m
        fx = self.well_fx or {}
        wx, wy = fx.get("x", 24), fx.get("y", 18)
        sx, sy = self.world_to_view_offset(wx, wy, cam_x, cam_y)
        if not (0 <= sx <= vis_w and 0 <= sy <= vis_h):
            return
        cx = sx * TILE + TILE // 2
        cy = sy * TILE + TILE // 2
        age = max(0.0, fx.get("until", now) - now)
        u = 1.0 - min(1.0, age / 2.8)
        # Flash bolt
        if u < 0.55:
            bolt = [
                (cx + 4, cy - 120),
                (cx - 10, cy - 70),
                (cx + 8, cy - 55),
                (cx - 6, cy - 20),
                (cx + 2, cy + 2),
            ]
            pygame.draw.lines(self.screen, (255, 255, 255), False, bolt, 3)
            pygame.draw.lines(self.screen, (180, 210, 255), False, bolt, 1)
            # Ground flash
            flash = pygame.Surface((TILE * 3, TILE * 2), pygame.SRCALPHA)
            a = int(180 * (1.0 - u / 0.55))
            pygame.draw.ellipse(flash, (255, 255, 220, a), flash.get_rect())
            self.screen.blit(flash, (cx - TILE * 1.5, cy - TILE // 2))
        # Sparkles
        for i in range(12):
            ang = i * 0.55 + now * 3
            rad = 10 + (i % 4) * 6 + u * 18
            px = cx + _m.cos(ang) * rad
            py = cy - 8 - abs(_m.sin(ang * 1.3)) * 20 - u * 10
            col = (255, 240, 160) if i % 2 == 0 else (200, 230, 255)
            pygame.draw.circle(self.screen, col, (int(px), int(py)), max(1, 3 - int(u * 2)))

    def draw_combat_quick_prompt(self, cx, top_y):
        """Compact Eat / potion buttons above the player during combat."""
        self.combat_quick_rects = {}
        if not self.combat_quick or time.time() > float(getattr(self, "combat_quick_until", 0) or 0):
            self.combat_quick = None
            return
        # Refresh availability so used-up pots disappear
        opts = self.combat_consumable_options()
        order = ("food", "health", "attack", "strength", "defence")
        labels = {
            "food": "Eat food",
            "health": "HP potion",
            "attack": "Att pot",
            "strength": "Str pot",
            "defence": "Def pot",
        }
        colors = {
            "food": ((50, 110, 60), (120, 200, 120)),
            "health": ((120, 50, 70), (220, 120, 150)),
            "attack": ((90, 70, 40), (220, 180, 90)),
            "strength": ((100, 45, 45), (230, 120, 100)),
            "defence": ((40, 70, 110), (120, 170, 230)),
        }
        buttons = [k for k in order if opts.get(k)]
        if not buttons:
            self.combat_quick = None
            return
        self.combat_quick = {
            "buttons": buttons,
            "labels": {k: labels[k] for k in buttons},
        }
        btn_h = 22
        pad = 4
        # Measure widths
        surfs = []
        for k in buttons:
            surfs.append((k, self.font_tiny.render(labels[k], True, WHITE)))
        widths = [max(58, s.get_width() + 12) for _, s in surfs]
        total_w = sum(widths) + pad * (len(widths) - 1) + 22  # + dismiss
        x0 = int(cx - total_w // 2)
        y0 = int(top_y - btn_h - 4)
        # Keep on screen
        x0 = max(4, min(x0, MAP_W - total_w - 4))
        y0 = max(4, y0)

        # Soft panel behind buttons
        panel = pygame.Rect(x0 - 4, y0 - 4, total_w + 8, btn_h + 8)
        pygame.draw.rect(self.screen, (18, 22, 30), panel, border_radius=6)
        pygame.draw.rect(self.screen, (200, 180, 90), panel, 1, border_radius=6)

        x = x0
        for (k, surf), w in zip(surfs, widths):
            r = pygame.Rect(x, y0, w, btn_h)
            bg, edge = colors[k]
            pygame.draw.rect(self.screen, bg, r, border_radius=5)
            pygame.draw.rect(self.screen, edge, r, 1, border_radius=5)
            self.screen.blit(surf, (r.centerx - surf.get_width() // 2, r.centery - surf.get_height() // 2))
            self.combat_quick_rects[k] = r
            x = r.right + pad

        dismiss = pygame.Rect(x, y0, 18, btn_h)
        pygame.draw.rect(self.screen, (70, 40, 40), dismiss, border_radius=5)
        pygame.draw.rect(self.screen, (180, 90, 80), dismiss, 1, border_radius=5)
        xt = self.font_tiny.render("×", True, WHITE)
        self.screen.blit(xt, (dismiss.centerx - xt.get_width() // 2, dismiss.centery - xt.get_height() // 2))
        self.combat_quick_rects["dismiss"] = dismiss

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
        # Ember heat wash inside the lava dungeon
        if self.dungeon and self.dungeon.get("id") == "emberdeep":
            heat = pygame.Surface((MAP_W, MAP_H), pygame.SRCALPHA)
            pulse = int(18 + 10 * abs(math.sin(time.time() * 1.5)))
            for i in range(36):
                a = int((pulse + 20) * (1 - i / 36))
                pygame.draw.rect(heat, (255, 80, 20, a), (i, i, MAP_W - 2 * i, MAP_H - 2 * i), 1)
            self.screen.blit(heat, (0, 0))

    # -- sidebar: ornate fantasy chrome + stats / tabs --------------------
    def _sb_fill_panel(self):
        """Deep navy panel + thick gold frame with corner ticks."""
        panel = pygame.Rect(SIDEBAR_X, 0, SCREEN_W - SIDEBAR_X, SCREEN_H)
        pygame.draw.rect(self.screen, SB_BG, panel)
        mid = pygame.Rect(SIDEBAR_X + 6, 6, panel.w - 12, panel.h - 12)
        pygame.draw.rect(self.screen, SB_BG_MID, mid, border_radius=4)
        pygame.draw.rect(self.screen, SB_EDGE, panel, 5)
        pygame.draw.rect(self.screen, SB_GOLD_DIM, panel, 3)
        pygame.draw.rect(self.screen, SB_GOLD, panel.inflate(-4, -4), 2)
        pygame.draw.rect(self.screen, (40, 36, 28), panel.inflate(-10, -10), 1)
        g, gd = SB_GOLD_HI, SB_GOLD_DIM
        for cx, cy, sx, sy in (
            (SIDEBAR_X + 8, 8, 1, 1),
            (SCREEN_W - 8, 8, -1, 1),
            (SIDEBAR_X + 8, SCREEN_H - 8, 1, -1),
            (SCREEN_W - 8, SCREEN_H - 8, -1, -1),
        ):
            pygame.draw.line(self.screen, g, (cx, cy), (cx + sx * 14, cy), 2)
            pygame.draw.line(self.screen, g, (cx, cy), (cx, cy + sy * 14), 2)
            pygame.draw.line(self.screen, gd, (cx + sx * 3, cy + sy * 3), (cx + sx * 10, cy + sy * 3), 1)
            pygame.draw.line(self.screen, gd, (cx + sx * 3, cy + sy * 3), (cx + sx * 3, cy + sy * 10), 1)

    def _sb_card(self, rect, bg=None, border=None, radius=7, fill=True):
        bg = bg or SB_CARD
        border = border or SB_GOLD_DIM
        if fill:
            pygame.draw.rect(self.screen, bg, rect, border_radius=radius)
            hi = pygame.Rect(rect.x + 3, rect.y + 2, max(4, rect.w - 6), max(3, rect.h // 4))
            overlay = pygame.Surface((hi.w, hi.h), pygame.SRCALPHA)
            overlay.fill((255, 255, 255, 16))
            self.screen.blit(overlay, hi.topleft)
        pygame.draw.rect(self.screen, border, rect, 1, border_radius=radius)

    def _sb_bevel_button(self, rect, bg, border, active=False, radius=8):
        c = tuple(min(255, x + 22) for x in bg) if active else bg
        pygame.draw.rect(self.screen, c, rect, border_radius=radius)
        pygame.draw.line(
            self.screen, tuple(min(255, x + 40) for x in c),
            (rect.x + 4, rect.y + 2), (rect.right - 4, rect.y + 2), 1,
        )
        pygame.draw.line(
            self.screen, tuple(max(0, x - 30) for x in c),
            (rect.x + 4, rect.bottom - 3), (rect.right - 4, rect.bottom - 3), 1,
        )
        pygame.draw.rect(self.screen, border, rect, 2 if active else 1, border_radius=radius)

    def _sidebar_section(self, title, y, right_label=None, right_rect_attr=None):
        """Gold section title + rule; optional right link."""
        x0 = SIDEBAR_X + 14
        self.screen.blit(self.font_small.render(title, True, SB_GOLD), (x0, y))
        if right_label:
            link = self.font_tiny.render(right_label, True, (160, 190, 230))
            lx = SCREEN_W - 16 - link.get_width()
            self.screen.blit(link, (lx, y + 2))
            if right_rect_attr:
                setattr(self, right_rect_attr, pygame.Rect(lx - 4, y, link.get_width() + 8, 16))
        pygame.draw.line(self.screen, SB_GOLD_DIM, (x0, y + 17), (SCREEN_W - 16, y + 17), 1)
        return y + 22

    def _sb_icon_coin(self, cx, cy, r=6):
        pygame.draw.circle(self.screen, (210, 170, 55), (cx, cy), r)
        pygame.draw.circle(self.screen, (255, 220, 110), (cx - 1, cy - 1), max(2, r - 3))
        pygame.draw.circle(self.screen, (120, 80, 30), (cx, cy), r, 1)

    def _sb_icon_heart(self, cx, cy, s=7):
        col = (210, 55, 70)
        pygame.draw.circle(self.screen, col, (cx - s // 2, cy - 1), s // 2 + 1)
        pygame.draw.circle(self.screen, col, (cx + s // 2, cy - 1), s // 2 + 1)
        pygame.draw.polygon(self.screen, col, [
            (cx - s, cy), (cx + s, cy), (cx, cy + s + 2),
        ])

    def _sb_icon_gear(self, cx, cy, r=7, col=None):
        col = col or SB_GOLD
        pygame.draw.circle(self.screen, col, (cx, cy), r, 2)
        pygame.draw.circle(self.screen, col, (cx, cy), max(2, r // 3))
        for ang in range(0, 360, 45):
            rad = math.radians(ang)
            x1 = cx + int(math.cos(rad) * (r - 1))
            y1 = cy + int(math.sin(rad) * (r - 1))
            x2 = cx + int(math.cos(rad) * (r + 3))
            y2 = cy + int(math.sin(rad) * (r + 3))
            pygame.draw.line(self.screen, col, (x1, y1), (x2, y2), 2)

    def _sb_icon_chevron(self, cx, cy, col=None):
        col = col or (160, 175, 200)
        pygame.draw.lines(self.screen, col, False, [
            (cx - 3, cy - 5), (cx + 3, cy), (cx - 3, cy + 5),
        ], 2)

    def _sb_icon_dragon(self, cx, cy, r=14):
        pygame.draw.circle(self.screen, (40, 32, 18), (cx, cy), r + 2)
        pygame.draw.circle(self.screen, SB_GOLD_DIM, (cx, cy), r + 1)
        pygame.draw.circle(self.screen, SB_GOLD, (cx, cy), r)
        pygame.draw.circle(self.screen, (255, 230, 140), (cx - 3, cy - 4), max(3, r // 3))
        pygame.draw.polygon(self.screen, (30, 24, 14), [
            (cx - 2, cy), (cx + r - 2, cy - 2), (cx + r - 4, cy + 4), (cx, cy + 5),
        ])
        pygame.draw.circle(self.screen, (200, 40, 40), (cx + 2, cy - 2), 2)

    def _sb_icon_pet(self, cx, cy):
        pygame.draw.ellipse(self.screen, (50, 140, 70), (cx - 8, cy - 5, 14, 11))
        pygame.draw.circle(self.screen, (60, 160, 80), (cx + 5, cy - 2), 5)
        pygame.draw.circle(self.screen, (20, 20, 20), (cx + 7, cy - 3), 1)
        pygame.draw.polygon(self.screen, (40, 120, 55), [
            (cx - 6, cy - 4), (cx - 10, cy - 9), (cx - 2, cy - 6),
        ])

    def _sb_icon_bank(self, cx, cy):
        pygame.draw.rect(self.screen, (180, 160, 90), (cx - 8, cy - 2, 16, 10), border_radius=1)
        pygame.draw.polygon(self.screen, (210, 190, 110), [
            (cx - 10, cy - 2), (cx, cy - 9), (cx + 10, cy - 2),
        ])
        pygame.draw.rect(self.screen, (40, 36, 28), (cx - 2, cy + 1, 4, 7))

    def _sb_icon_person(self, cx, cy, col=(220, 230, 220)):
        pygame.draw.circle(self.screen, col, (cx, cy - 4), 4)
        pygame.draw.ellipse(self.screen, col, (cx - 6, cy, 12, 9))

    def _sb_icon_compass(self, cx, cy):
        pygame.draw.circle(self.screen, (180, 210, 255), (cx, cy), 8, 1)
        pygame.draw.polygon(self.screen, (255, 120, 100), [(cx, cy - 7), (cx + 3, cy), (cx, cy + 2)])
        pygame.draw.polygon(self.screen, (200, 210, 230), [(cx, cy + 7), (cx - 3, cy), (cx, cy - 2)])

    def _sb_icon_chest(self, cx, cy):
        pygame.draw.rect(self.screen, (160, 110, 50), (cx - 8, cy - 3, 16, 10), border_radius=2)
        pygame.draw.rect(self.screen, (210, 170, 70), (cx - 8, cy - 5, 16, 4), border_radius=1)
        pygame.draw.circle(self.screen, (255, 220, 100), (cx, cy + 1), 2)

    def _sb_icon_pack(self, cx, cy):
        pygame.draw.rect(self.screen, (150, 100, 55), (cx - 7, cy - 5, 14, 12), border_radius=3)
        pygame.draw.arc(self.screen, (200, 150, 80), (cx - 6, cy - 10, 12, 10), 3.4, 6.0, 2)

    def _sb_icon_bag(self, cx, cy):
        pygame.draw.ellipse(self.screen, (150, 120, 70), (cx - 7, cy - 3, 14, 11))
        pygame.draw.line(self.screen, (100, 80, 40), (cx - 3, cy - 5), (cx + 3, cy - 5), 2)

    def _sb_icon_swords(self, cx, cy, col=(220, 200, 160)):
        pygame.draw.line(self.screen, col, (cx - 6, cy + 6), (cx + 6, cy - 6), 2)
        pygame.draw.line(self.screen, col, (cx - 6, cy - 6), (cx + 6, cy + 6), 2)
        pygame.draw.circle(self.screen, col, (cx, cy), 2)

    def _sb_icon_hat(self, cx, cy):
        pygame.draw.polygon(self.screen, (80, 120, 200), [
            (cx, cy - 8), (cx + 8, cy + 4), (cx - 8, cy + 4),
        ])
        pygame.draw.ellipse(self.screen, (60, 90, 160), (cx - 9, cy + 2, 18, 5))

    def _sb_icon_scroll(self, cx, cy):
        pygame.draw.rect(self.screen, (210, 190, 140), (cx - 6, cy - 7, 12, 14), border_radius=1)
        pygame.draw.line(self.screen, (120, 100, 60), (cx - 3, cy - 3), (cx + 3, cy - 3), 1)
        pygame.draw.line(self.screen, (120, 100, 60), (cx - 3, cy), (cx + 3, cy), 1)
        pygame.draw.line(self.screen, (120, 100, 60), (cx - 3, cy + 3), (cx + 2, cy + 3), 1)

    def _sb_icon_chart(self, cx, cy):
        pygame.draw.line(self.screen, SB_GOLD, (cx - 6, cy + 5), (cx - 6, cy - 5), 1)
        pygame.draw.line(self.screen, SB_GOLD, (cx - 6, cy + 5), (cx + 7, cy + 5), 1)
        for i, h in enumerate((4, 7, 5, 9)):
            pygame.draw.rect(self.screen, (140, 180, 230), (cx - 4 + i * 3, cy + 5 - h, 2, h))

    def _sb_icon_star(self, cx, cy, col=None):
        col = col or SB_GOLD
        pts = []
        for i in range(10):
            ang = math.radians(-90 + i * 36)
            r = 6 if i % 2 == 0 else 3
            pts.append((cx + int(math.cos(ang) * r), cy + int(math.sin(ang) * r)))
        pygame.draw.polygon(self.screen, col, pts)

    def _sb_icon_sword(self, cx, cy, col=(255, 140, 100)):
        pygame.draw.line(self.screen, col, (cx - 1, cy + 6), (cx - 1, cy - 6), 2)
        pygame.draw.line(self.screen, col, (cx - 4, cy + 2), (cx + 3, cy + 2), 2)

    def _sb_icon_fist(self, cx, cy, col=(140, 220, 120)):
        pygame.draw.ellipse(self.screen, col, (cx - 5, cy - 4, 10, 9))
        pygame.draw.rect(self.screen, col, (cx - 5, cy - 1, 10, 5))

    def _sb_icon_shield(self, cx, cy, col=(120, 170, 255)):
        pygame.draw.polygon(self.screen, col, [
            (cx, cy - 6), (cx + 6, cy - 3), (cx + 5, cy + 4), (cx, cy + 7),
            (cx - 5, cy + 4), (cx - 6, cy - 3),
        ])

    def _sb_icon_power(self, cx, cy, col=(255, 200, 200)):
        pygame.draw.circle(self.screen, col, (cx, cy), 7, 2)
        pygame.draw.line(self.screen, col, (cx, cy - 8), (cx, cy + 1), 2)

    def draw_sidebar(self):
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
            f"Auto-pickup {'ON' if auto else 'OFF'} (P)", True, WHITE,
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
        fill_c = (70, 200, 100) if pct > 0.55 else ((220, 170, 50) if pct > 0.25 else (210, 60, 55))
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
        actions = (
            ("travel", "Travel", "M", (42, 78, 130), (130, 190, 255), self._sb_icon_compass),
            ("bank", "Bank", "B", (40, 100, 70), (120, 230, 150), self._sb_icon_chest),
            ("gear", "Gear", "E", (110, 72, 42), (240, 180, 100), self._sb_icon_pack),
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

    def _draw_sidebar_inventory_tab(self, y, content_bottom):
        self.inv_tab_rects = {}
        tab_w = 66
        for i, tab in enumerate(INVENTORY_TABS):
            r = pygame.Rect(SIDEBAR_X + 12 + i * (tab_w + 4), y, tab_w, 24)
            self.inv_tab_rects[i] = r
            active = i == self.inv_tab
            self._sb_card(
                r,
                bg=(50, 70, 55) if active else (34, 36, 44),
                border=GREEN if active else SB_GOLD_DIM,
                radius=5,
            )
            lab = self.font_tiny.render(tab["label"], True, WHITE if active else GREY)
            self.screen.blit(lab, (r.centerx - lab.get_width() // 2, r.y + 5))
        y += 28
        hint_txt = (
            "Bags tab · storage only · click use · drag · right drop"
            if self.inv_tab == 3 else
            f"Tab {self.inv_tab + 1}/{len(INVENTORY_TABS)} · 24 slots · click use · drag · right drop"
        )
        hint = self.font_tiny.render(hint_txt, True, (160, 158, 140))
        self.screen.blit(hint, (SIDEBAR_X + 14, y))
        self._inventory_oy = y + 16
        self._inventory_bottom = content_bottom
        hover_entry = None
        hover_rect = None
        drag = self.inv_drag
        for slot, rect in self.inventory_slot_rects().items():
            if rect.bottom > content_bottom + 2:
                continue
            entry = self.player["inventory"].get(str(slot)) or self.player["inventory"].get(slot)
            dragging_here = bool(drag and drag.get("moved") and drag["from"] == slot)
            hovered = slot == self.inv_hover_slot and not dragging_here
            bg = (48, 52, 66) if entry else (32, 34, 44)
            if hovered:
                bg = (62, 78, 48)
            if dragging_here:
                bg = (28, 30, 38)
            pygame.draw.rect(self.screen, bg, rect, border_radius=5)
            border = ACCENT if hovered else (PANEL_LINE if not entry else (78, 82, 98))
            if dragging_here:
                border = (90, 100, 120)
            pygame.draw.rect(self.screen, border, rect, 2 if hovered else 1, border_radius=5)
            if entry and not dragging_here:
                sprites.draw_item_icon(self.screen, rect.inflate(-8, -8), entry["item_id"], ITEMS)
                if entry["qty"] > 1:
                    qty_s = str(entry["qty"])
                    qty = self.font_inv.render(qty_s, True, YELLOW)
                    for ox, oy in ((-1, 0), (1, 0), (0, -1), (0, 1)):
                        shadow = self.font_inv.render(qty_s, True, (0, 0, 0))
                        self.screen.blit(shadow, (rect.x + 3 + ox, rect.y + 1 + oy))
                    self.screen.blit(qty, (rect.x + 3, rect.y + 1))
                if hovered:
                    hover_entry = entry
                    hover_rect = rect

        if drag and drag.get("moved"):
            ghost = pygame.Rect(0, 0, 48, 48)
            ghost.center = (drag["x"], drag["y"])
            ghost_s = pygame.Surface((48, 48), pygame.SRCALPHA)
            sprites.draw_item_icon(ghost_s, ghost_s.get_rect().inflate(-8, -8), drag["item_id"], ITEMS)
            ghost_s.set_alpha(200)
            self.screen.blit(ghost_s, ghost.topleft)
            if drag.get("qty", 1) > 1:
                qty_s = str(drag["qty"])
                qty = self.font_inv.render(qty_s, True, YELLOW)
                self.screen.blit(qty, (ghost.x + 3, ghost.y + 1))

        if hover_entry and hover_rect:
            self.draw_inventory_tooltip(hover_entry, hover_rect)
        return content_bottom

    def _draw_sidebar_combat_tab(self, y, content_bottom):
        """Worn gear summary + combat bonuses + XP style."""
        eq = self.player.get("equipment") or {}
        wb = self.player.get("gear_bonuses") or {"att_bonus": 0, "str_bonus": 0, "def_bonus": 0}
        levels = self.player.get("levels") or {}
        self.sidebar_equip_rects = {}
        x0 = SIDEBAR_X + 14

        slots = (
            ("helmet", "HELM"),
            ("amulet", "AMULET"),
            ("ring", "RING"),
            ("weapon", "WEAPON"),
            ("body", "BODY"),
            ("shield", "SHIELD"),
            ("legs", "LEGS"),
            ("ammo", "AMMO"),
        )
        cell = 40
        cols = 4
        gap = 6
        for i, (slot, tag) in enumerate(slots):
            col, row = i % cols, i // cols
            r = pygame.Rect(x0 + col * (cell + gap), y + row * (cell + gap), cell, cell)
            item_id = eq.get(slot)
            bg = (40, 52, 72) if item_id else (24, 28, 36)
            border = (120, 180, 255) if item_id else (60, 70, 90)
            pygame.draw.rect(self.screen, bg, r, border_radius=6)
            if item_id:
                pygame.draw.rect(self.screen, (70, 120, 180), r.inflate(2, 2), 2, border_radius=7)
            pygame.draw.rect(self.screen, border, r, 1, border_radius=6)
            tag_s = self.font_tiny.render(tag, True, (140, 155, 180))
            self.screen.blit(tag_s, (r.x + 3, r.y + 1))
            if item_id:
                sprites.draw_item_icon(self.screen, r.inflate(-10, -14), item_id, ITEMS)
                if slot == "ammo" and item_id == "arrow_quiver":
                    qtot = int((self.player or {}).get("quiver_total") or 0)
                    if qtot > 0:
                        qty = self.font_tiny.render(str(qtot), True, YELLOW)
                        self.screen.blit(qty, (r.x + 3, r.bottom - 13))
            self.sidebar_equip_rects[slot] = r
        rows_used = (len(slots) + cols - 1) // cols
        y += rows_used * (cell + gap) + 6

        self._sb_icon_star(x0 + 6, y + 7)
        self.screen.blit(self.font_small.render("Worn Bonuses", True, SB_GOLD), (x0 + 16, y))
        y += 18
        for label, key, col, icon_fn in (
            ("Attack", "att_bonus", (255, 150, 100), self._sb_icon_sword),
            ("Strength", "str_bonus", (140, 230, 120), self._sb_icon_fist),
            ("Defence", "def_bonus", (130, 180, 255), self._sb_icon_shield),
        ):
            val = int(wb.get(key, 0))
            icon_fn(x0 + 8, y + 7, col)
            self.screen.blit(self.font_small.render(label, True, (200, 198, 190)), (x0 + 20, y))
            num = self.font_small.render(f"+{val}", True, col)
            self.screen.blit(num, (SCREEN_W - 18 - num.get_width(), y))
            y += 16
        js = (self.player or {}).get("jewelry_specials") or {}
        bits = []
        if js.get("lifesteal"):
            bits.append(f"LS {int(round(float(js['lifesteal']) * 100))}%")
        if js.get("crit"):
            bits.append(f"Crit {int(round(float(js['crit']) * 100))}%")
        if js.get("dodge"):
            bits.append(f"Dodge {int(round(float(js['dodge']) * 100))}%")
        if js.get("thorns"):
            bits.append(f"Thorns {int(round(float(js['thorns']) * 100))}%")
        if js.get("void_strike"):
            bits.append(f"+{int(js['void_strike'])} dmg")
        if js.get("void_ward"):
            bits.append(f"−{int(js['void_ward'])} taken")
        if bits:
            line = " · ".join(bits)
            while self.font_tiny.size(line)[0] > SCREEN_W - SIDEBAR_X - 28 and len(line) > 8:
                line = line[:-5] + "…"
            self.screen.blit(self.font_tiny.render(line, True, (200, 180, 120)), (x0, y))
            y += 14
        pygame.draw.line(self.screen, SB_GOLD_DIM, (x0, y), (SCREEN_W - 16, y), 1)
        y += 6
        self.screen.blit(
            self.font_tiny.render(
                f"HP {self.player['hp']}/{self.player['max_hp']}  ·  "
                f"Att {levels.get('attack', 1)}  ·  Str {levels.get('strength', 1)}  ·  "
                f"Def {levels.get('defence', 1)}",
                True, (210, 208, 200),
            ),
            (x0, y),
        )
        y += 16
        tip = self.font_tiny.render("Click slot to unequip · Gear for full view", True, GREY)
        self.screen.blit(tip, (x0, y))
        y += 16

        self._sb_icon_swords(x0 + 6, y + 7)
        self.screen.blit(self.font_small.render("Combat XP", True, SB_GOLD), (x0 + 16, y))
        y += 20
        self._combat_style_oy = y
        current = self.combat_style or (self.player.get("combat_style") if self.player else "attack") or "attack"
        has_bow = self.player_using_bow()
        if has_bow:
            current = "archery"
            self.combat_style = "archery"
        elif current == "archery":
            current = "attack"
            self.combat_style = "attack"
        self.combat_style_rects = []
        for rect, style, label in self.combat_style_button_rects():
            if has_bow:
                locked = style != "archery"
            else:
                locked = style == "archery"
            selected = style == current and not locked
            if locked:
                bg, border, col = (28, 30, 36), (55, 58, 68), (90, 90, 100)
            elif selected:
                bg, border, col = (42, 100, 58), (110, 230, 140), WHITE
            else:
                bg, border, col = (36, 48, 72), (90, 130, 190), (200, 210, 230)
            pygame.draw.rect(self.screen, bg, rect, border_radius=12)
            pygame.draw.rect(self.screen, border, rect, 1, border_radius=12)
            txt = self.font_tiny.render(label, True, col)
            self.screen.blit(
                txt,
                (rect.x + (rect.w - txt.get_width()) // 2,
                 rect.y + (rect.h - txt.get_height()) // 2),
            )
            if not locked:
                self.combat_style_rects.append((rect, style))
        arch_hint = self.font_tiny.render(
            "Bow equipped — Archery only" if has_bow else "Equip a bow to use Archery",
            True, (140, 180, 140) if has_bow else (140, 138, 120),
        )
        self.screen.blit(arch_hint, (x0, y + 34))
        return content_bottom

    def _draw_sidebar_magic_tab(self, y, content_bottom):
        """Quest-point magic abilities — unlock list + auto/manual toggle."""
        magic = (self.player or {}).get("magic") or {}
        qp = int((self.player or {}).get("quest_points") or 0)
        auto = bool(magic.get("auto", True))
        abilities = magic.get("abilities") or {}
        order = list(reversed(magic.get("order") or MAGIC_ABILITY_ORDER))
        max_qp = sum(int(q.get("quest_points") or 0) for q in QUESTS.values())
        # Next unlock the player can still reach with current content
        next_need = None
        next_name = None
        for aid in reversed(MAGIC_ABILITY_ORDER):  # weakest → strongest
            ab = MAGIC_ABILITIES.get(aid) or {}
            need = int(ab.get("quest_points") or 0)
            unlocked = bool((abilities.get(aid) or {}).get("unlocked")) if aid in abilities else (qp >= need)
            if not unlocked and need <= max_qp:
                next_need, next_name = need, ab.get("name", aid)
                break

        self.screen.blit(
            self.font_small.render(f"Quest points  {qp} / {max_qp}", True, YELLOW),
            (SIDEBAR_X + 14, y),
        )
        y += 18
        if next_need is not None:
            tip = self.font_tiny.render(
                f"Next: {next_name} at {next_need} QP",
                True, (200, 190, 140),
            )
        else:
            tip = self.font_tiny.render(
                "All listed quest magic unlocked — hunt more quests for QP.",
                True, (160, 158, 140),
            )
        self.screen.blit(tip, (SIDEBAR_X + 14, y))
        y += 18

        # Auto / Manual toggle
        mode = pygame.Rect(SIDEBAR_X + 14, y, SCREEN_W - SIDEBAR_X - 28, 30)
        self.magic_mode_btn_rect = mode
        pygame.draw.rect(self.screen, (36, 78, 48) if auto else (78, 58, 36), mode, border_radius=6)
        pygame.draw.rect(self.screen, GREEN if auto else (230, 170, 90), mode, 1, border_radius=6)
        label = "Auto cast  ON" if auto else "Manual cast  ON"
        sub = "longer CD · casts in combat" if auto else "shorter CD · fight buttons"
        self.screen.blit(self.font_small.render(label, True, WHITE), (mode.x + 10, mode.y + 2))
        self.screen.blit(self.font_tiny.render(sub, True, (200, 210, 200)), (mode.x + 10, mode.y + 16))
        y += 38

        self.magic_btn_rects = {}
        now = time.time()
        for aid in order:
            if y + 44 > content_bottom:
                break
            ab = abilities.get(aid) or MAGIC_ABILITIES.get(aid) or {}
            name = ab.get("name") or aid
            need = int(ab.get("quest_points") or (MAGIC_ABILITIES.get(aid) or {}).get("quest_points") or 0)
            unlocked = bool(ab.get("unlocked")) if "unlocked" in ab else (qp >= need)
            ready_at = float(ab.get("ready_at") or 0)
            cd_left = max(0.0, ready_at - now) if unlocked else 0.0
            effect = ab.get("effect") or (MAGIC_ABILITIES.get(aid) or {}).get("effect") or "lightning"
            row = pygame.Rect(SIDEBAR_X + 14, y, SCREEN_W - SIDEBAR_X - 28, 42)
            if unlocked:
                bg = (40, 48, 62) if cd_left <= 0 else (32, 34, 42)
                border = {
                    "lightning": (160, 200, 255),
                    "fire": (255, 140, 80),
                    "freeze": (140, 210, 255),
                }.get(effect, ACCENT)
            else:
                bg, border = (26, 28, 34), (55, 58, 68)
            pygame.draw.rect(self.screen, bg, row, border_radius=5)
            pygame.draw.rect(self.screen, border, row, 1, border_radius=5)
            title_c = WHITE if unlocked else GREY
            self.screen.blit(self.font_small.render(name, True, title_c), (row.x + 8, row.y + 4))
            if unlocked:
                dmg = int(ab.get("damage") or 0)
                fr = float(ab.get("freeze") or 0)
                bits = [effect.title(), f"{dmg} dmg"]
                if fr > 0:
                    bits.append(f"freeze {fr:.1f}s")
                status = "Ready" if cd_left <= 0 else f"CD {cd_left:.1f}s"
                self.screen.blit(
                    self.font_tiny.render(" · ".join(bits) + f"  ·  {status}", True, (180, 190, 210)),
                    (row.x + 8, row.y + 22),
                )
                if not auto and cd_left <= 0:
                    self.magic_btn_rects[aid] = row
            else:
                if need > max_qp:
                    lock = f"Coming soon · needs more quests ({need} QP)"
                else:
                    lock = f"Locked · {qp}/{need} QP"
                self.screen.blit(
                    self.font_tiny.render(lock, True, (120, 120, 130)),
                    (row.x + 8, row.y + 22),
                )
            y += 46
        return content_bottom

    def _draw_sidebar_quests_tab(self, y, content_bottom):
        qp = int((self.player or {}).get("quest_points") or 0)
        self.quest_row_rects = []
        self.screen.blit(self.font_small.render(f"Journal  ·  {qp} QP", True, YELLOW), (SIDEBAR_X + 14, y))
        y += 16
        tip = self.font_tiny.render("Click a quest · scroll for more", True, (140, 145, 160))
        self.screen.blit(tip, (SIDEBAR_X + 14, y))
        y += 18
        if not self.quests:
            self.screen.blit(
                self.font_small.render("Talk to NPCs to begin quests.", True, GREY),
                (SIDEBAR_X + 14, y),
            )
            self.quests_scroll_meta = {"max_scroll": 0}
            return content_bottom

        # Ready → active → available → complete
        order = {"ready": 0, "active": 1, "not_started": 2, "complete": 3}
        entries = []
        for qid in QUESTS:
            info = self.quests.get(qid) or {"status": "not_started", "progress": 0}
            status = info.get("status") or "not_started"
            req = (QUESTS.get(qid) or {}).get("requires")
            if status == "not_started" and req:
                needed = req if isinstance(req, (list, tuple)) else [req]
                if any((self.quests.get(r) or {}).get("status") != "complete" for r in needed):
                    continue  # hide locked chain steps
            entries.append((qid, info, status))
        entries.sort(key=lambda t: (order.get(t[2], 9), QUESTS.get(t[0], {}).get("name", t[0])))

        list_top = y
        view_h = max(40, content_bottom - list_top)
        content_h = 0
        row_heights = []
        for _, _, status in entries:
            rh = 54 if status in ("active", "ready") else 44
            row_heights.append(rh)
            content_h += rh
        max_scroll = max(0, content_h - view_h)
        self.quests_scroll = max(0, min(float(self.quests_scroll), max_scroll))
        self.quests_scroll_meta = {
            "list_top": list_top, "view_h": view_h, "max_scroll": max_scroll,
            "track": pygame.Rect(SCREEN_W - 14, list_top, 8, view_h),
        }

        prev_clip = self.screen.get_clip()
        self.screen.set_clip(pygame.Rect(SIDEBAR_X + 8, list_top, SCREEN_W - SIDEBAR_X - 22, view_h))

        y = list_top - self.quests_scroll
        for (qid, info, status), row_h in zip(entries, row_heights):
            row_top = y
            y += row_h
            if row_top + row_h < list_top or row_top > content_bottom:
                continue
            qdef = QUESTS.get(qid) or {}
            color = {
                "not_started": GREY,
                "active": WHITE,
                "ready": YELLOW,
                "complete": GREEN,
            }.get(status, GREY)
            title = qdef.get("name") or qid.replace("_", " ").title()
            row = pygame.Rect(SIDEBAR_X + 14, int(row_top), SCREEN_W - SIDEBAR_X - 36, row_h - 4)
            bg = (42, 48, 36) if status == "ready" else ((32, 36, 46) if status != "complete" else (28, 34, 32))
            pygame.draw.rect(self.screen, bg, row, border_radius=5)
            border = YELLOW if status == "ready" else PANEL_LINE
            pygame.draw.rect(self.screen, border, row, 1, border_radius=5)
            self.screen.blit(self.font_small.render(title, True, color), (row.x + 8, row.y + 3))
            giver = next((n for n in NPCS if n.get("id") == qdef.get("giver")), None) or {}
            giver_name = giver.get("name") or ""
            status_label = {
                "not_started": f"Available · {giver_name}" if giver_name else "Available",
                "active": "In progress",
                "ready": "Ready to turn in",
                "complete": "Complete",
            }.get(status, status)
            self.screen.blit(
                self.font_tiny.render(status_label, True, (160, 165, 180)),
                (row.x + 8, row.y + 19),
            )
            if status in ("active", "ready"):
                obj = self._quest_objective_text(qid, info)
                if obj:
                    max_w = row.w - 16
                    while self.font_tiny.size(obj)[0] > max_w and len(obj) > 4:
                        obj = obj[:-4] + "…"
                    self.screen.blit(
                        self.font_tiny.render(obj, True, (200, 210, 230) if status == "active" else (255, 230, 140)),
                        (row.x + 8, row.y + 33),
                    )
            elif status == "not_started":
                qp_bit = int(qdef.get("quest_points") or 0)
                if qp_bit:
                    self.screen.blit(
                        self.font_tiny.render(f"+{qp_bit} QP", True, (180, 170, 120)),
                        (row.x + 8, row.y + 33),
                    )
            if status != "complete":
                self.quest_row_rects.append((row, qid))

        self.screen.set_clip(prev_clip)
        if max_scroll > 0:
            track = self.quests_scroll_meta["track"]
            pygame.draw.rect(self.screen, (28, 32, 42), track, border_radius=3)
            thumb_h = max(20, int(view_h * view_h / max(1, content_h)))
            thumb_y = list_top + int((view_h - thumb_h) * self.quests_scroll / max_scroll)
            pygame.draw.rect(self.screen, (120, 160, 200), pygame.Rect(track.x, thumb_y, track.w, thumb_h), border_radius=3)
        return content_bottom

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
            cap = int((self.player or {}).get("resource_bag_capacity") or 200)
            lines.append(f"Stores {cap} of each fletching supply")
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

    def _maybe_combat_floater(self, text):
        """Short banner above the player for attack/cast failures."""
        if not self.player or not text:
            return
        key = text.lower()
        triggers = (
            "too far", "arrow", "bow", "archery", "shoot", "cast",
            "equip", "attack", "ammo", "cannot", "can't",
        )
        if not any(t in key for t in triggers):
            return
        short = text if len(text) <= 40 else text[:37] + "…"
        px, py = self.player["x"], self.player["y"]
        self.floaters.append({
            "x": px, "y": py,
            "text": short,
            "color": (255, 170, 110),
            "expire": time.time() + 2.2,
            "kind": "combat_hint",
        })

    def add_chat(self, text, color=None, highlight=False):
        """Append a chat line; optional color and gold highlight bar."""
        pinned = self.chat_scroll == 0
        self.chat_log.append({
            "text": text,
            "color": color or WHITE,
            "highlight": highlight,
        })
        self.chat_log = self.chat_log[-self.CHAT_MAX:]
        if pinned:
            self.chat_scroll = 0
        else:
            max_off = max(0, len(self.chat_log) - self.CHAT_VISIBLE)
            self.chat_scroll = min(self.chat_scroll, max_off)

    def draw_walk_markers(self, cam_x, cam_y, vis_w, vis_h, t):
        """Yellow destination + faint path dots for click-to-walk."""
        if not self.walk_path:
            return
        dest = self.walk_path[-1]
        # Path crumbs (skip first few if long)
        step = max(1, len(self.walk_path) // 12)
        for i, (wx, wy) in enumerate(self.walk_path[::step]):
            sx, sy = self.world_to_view_offset(wx, wy, cam_x, cam_y)
            if 0 <= sx <= vis_w and 0 <= sy <= vis_h:
                cx = sx * TILE + TILE // 2
                cy = sy * TILE + TILE // 2
                pygame.draw.circle(self.screen, (255, 210, 70), (cx, cy), 3)
        dx, dy = self.world_to_view_offset(dest[0], dest[1], cam_x, cam_y)
        if 0 <= dx <= vis_w and 0 <= dy <= vis_h:
            cx = dx * TILE + TILE // 2
            cy = dy * TILE + TILE // 2
            pulse = 0.55 + 0.45 * abs(math.sin(t * 5))
            r = int(10 + 3 * pulse)
            ring = pygame.Surface((r * 2 + 4, r * 2 + 4), pygame.SRCALPHA)
            pygame.draw.circle(ring, (255, 220, 70, int(90 * pulse)), (r + 2, r + 2), r, 2)
            pygame.draw.circle(ring, (255, 240, 120, 200), (r + 2, r + 2), 4)
            self.screen.blit(ring, (cx - r - 2, cy - r - 2))

    def draw_death_banner(self):
        """Centered overlay when you die / respawn."""
        now = time.time()
        remaining = max(0.0, self.death_banner_until - now)
        fade = min(1.0, remaining / 0.6)
        panel = pygame.Surface((MAP_W, 90), pygame.SRCALPHA)
        panel.fill((40, 10, 12, int(200 * fade)))
        self.screen.blit(panel, (0, MAP_H // 2 - 50))
        title = self.font_big.render("You died", True, (255, 120, 110))
        title.set_alpha(int(255 * fade))
        self.screen.blit(title, (MAP_W // 2 - title.get_width() // 2, MAP_H // 2 - 42))
        sub = self.font.render(self.death_banner_text, True, (255, 210, 200))
        sub.set_alpha(int(255 * fade))
        self.screen.blit(sub, (MAP_W // 2 - sub.get_width() // 2, MAP_H // 2 - 8))
        tip = self.font_small.render("Respawned — eat food (R) and gear up", True, (200, 180, 170))
        tip.set_alpha(int(220 * fade))
        self.screen.blit(tip, (MAP_W // 2 - tip.get_width() // 2, MAP_H // 2 + 18))

    def _announce_new_stat_boosts(self, prev, current):
        """Floating text + chat when a potion boost is freshly applied or increased."""
        if not self.player:
            return
        px = self.player.get("x", 0)
        py = self.player.get("y", 0)
        levels = self.player.get("levels") or {}
        for skill in ("attack", "strength", "defence"):
            now_buff = current.get(skill)
            if not now_buff:
                continue
            amt = int(now_buff.get("amount") or 0)
            if amt <= 0:
                continue
            prev_amt = int((prev.get(skill) or {}).get("amount") or 0)
            # New drink, or re-drink with same/higher boost (refresh)
            prev_until = float((prev.get(skill) or {}).get("until") or 0)
            now_until = float(now_buff.get("until") or 0)
            refreshed = now_until > prev_until + 0.5 or amt > prev_amt or skill not in prev
            if not refreshed:
                continue
            base = int(levels.get(skill, 1))
            label = skill.title()
            self.add_chat(
                f"{label} boosted to {base + amt} (+{amt}) for 1 minute!",
                color=(110, 255, 140),
                highlight=True,
            )
            self.floaters.append({
                "x": px, "y": py,
                "text": f"{label} +{amt}",
                "color": (110, 255, 140),
                "expire": time.time() + 2.4,
                "kind": "stat_boost",
            })

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
        max_off = max(0, len(self.chat_log) - self.CHAT_VISIBLE)
        self.chat_scroll = max(0, min(max_off, self.chat_scroll))
        end = len(self.chat_log) - self.chat_scroll
        start = max(0, end - self.CHAT_VISIBLE)
        y = MAP_H + 8
        for line in self.chat_log[start:end]:
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
        if self.chat_scroll > 0:
            hint = self.font_tiny.render(f"↑ {self.chat_scroll} older  ·  scroll chat", True, (140, 150, 170))
            self.screen.blit(hint, (MAP_W - hint.get_width() - 10, MAP_H + 4))
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

    def draw_dungeon_hud(self):
        d = self.dungeon or {}
        box = pygame.Rect(12, 12, 400, 78)
        pygame.draw.rect(self.screen, (18, 22, 32, 220), box, border_radius=8)
        # opaque fallback
        panel = pygame.Surface((box.w, box.h), pygame.SRCALPHA)
        did = d.get("id") or "tidehollow"
        if did == "emberdeep":
            panel.fill((36, 18, 14, 220))
            border = (255, 140, 60)
            title_col = (255, 200, 110)
            name = "Emberdeep"
        else:
            panel.fill((16, 20, 30, 210))
            border = (210, 175, 70)
            title_col = (255, 220, 110)
            name = "Tidehollow"
        self.screen.blit(panel, box.topleft)
        pygame.draw.rect(self.screen, border, box, 2, border_radius=8)
        title = self.font.render(
            f"{name} · Floor {d.get('floor', 1)}/{d.get('floors', 10)}",
            True, title_col,
        )
        self.screen.blit(title, (box.x + 12, box.y + 10))
        sub = self.font_small.render(
            f"{d.get('label', '')}  ·  {d.get('remaining', 0)} beasts left",
            True, (200, 205, 220),
        )
        self.screen.blit(sub, (box.x + 12, box.y + 40))
        # Explicit Leave button (Esc also works)
        leave = pygame.Rect(box.right - 108, box.y + 18, 92, 42)
        self.dungeon_leave_rect = leave
        pygame.draw.rect(self.screen, (90, 40, 35), leave, border_radius=6)
        pygame.draw.rect(self.screen, (220, 100, 80), leave, 2, border_radius=6)
        lt = self.font_small.render("Leave", True, WHITE)
        self.screen.blit(lt, (leave.centerx - lt.get_width() // 2, leave.y + 6))
        tip = self.font_tiny.render("Esc", True, (200, 180, 160))
        self.screen.blit(tip, (leave.centerx - tip.get_width() // 2, leave.y + 24))

    # -- modals ---------------------------------------------------------------
    def draw_dialogue(self):
        box = pygame.Rect(150, 450, MAP_W - 300, 230)
        pygame.draw.rect(self.screen, (25, 25, 35), box)
        pygame.draw.rect(self.screen, WHITE, box, 2)
        self.dialogue_btn_rects = {}

        name = self.font.render(self.dialogue["npc_name"], True, YELLOW)
        self.screen.blit(name, (box.x + 12, box.y + 10))

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

        if quest and quest.get("state") == "offerable":
            bx = add_btn("accept", "Accept (A)", (50, 110, 60), bx)
        if quest and quest.get("state") == "ready":
            bx = add_btn("turnin", "Turn in (T)", (160, 120, 40), bx)
        if self.dialogue.get("shop_id"):
            bx = add_btn("shop", "Shop (B)", (120, 90, 40), bx)
        if self.dialogue.get("bank"):
            bx = add_btn("bank", "Bank (B)", (50, 90, 130), bx)
        if self.dialogue.get("forge"):
            bx = add_btn("forge", "Forge (S)", (140, 80, 40), bx)
        add_btn("close", "Close", (60, 60, 70), box.right - 80)

        # Body text — clipped above buttons
        text_bottom = btn_y - 8
        y = box.y + 36
        max_w = box.w - 24
        prev_clip = self.screen.get_clip()
        self.screen.set_clip(pygame.Rect(box.x + 8, box.y + 34, box.w - 16, text_bottom - (box.y + 34)))

        for line in self.dialogue.get("lines") or []:
            for wrapped in self._wrap_ui_text(line, self.font_small, max_w):
                if y + 16 > text_bottom:
                    break
                self.screen.blit(self.font_small.render(wrapped, True, WHITE), (box.x + 12, y))
                y += 17
            if y + 16 > text_bottom:
                break

        if quest:
            y += 6
            q_title = f"Quest: {quest.get('name', '?')}"
            self.screen.blit(self.font_small.render(q_title, True, (200, 200, 255)), (box.x + 12, y))
            y += 18
            desc = quest.get("description") or ""
            for wrapped in self._wrap_ui_text(desc, self.font_tiny, max_w):
                if y + 14 > text_bottom:
                    break
                self.screen.blit(self.font_tiny.render(wrapped, True, (180, 185, 210)), (box.x + 12, y))
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
                    (box.x + 12, y),
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
                        (box.x + 12, y),
                    )
                    y += 14
            if quest.get("state") == "offerable":
                hint, hcol = "Accept this quest to begin.", GREEN
            elif quest.get("state") == "active":
                hint, hcol = "Quest in progress — check your journal.", GREY
            elif quest.get("state") == "ready":
                hint, hcol = "You have what they need — turn it in!", YELLOW
            else:
                hint, hcol = "Quest already completed.", GREEN
            if y + 16 <= text_bottom:
                self.screen.blit(self.font_small.render(hint, True, hcol), (box.x + 12, y))

        self.screen.set_clip(prev_clip)

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

        list_top = box.y + 100
        list_bottom = box.bottom - 36
        view_h = max(40, list_bottom - list_top)
        row_h = 40
        sb_w = 10

        # --- Buy column ---
        self.screen.blit(self.font.render("Buy", True, GREEN), (box.x + 18, box.y + 72))
        self.screen.blit(
            self.font_small.render("Click to buy 1 · scroll / drag bar", True, GREY),
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
                icon = pygame.Rect(row.x + 6, row.y + 4, 28, 28)
                sprites.draw_item_icon(self.screen, icon, item_id, ITEMS)
                name = self.font_small.render(info["name"], True, WHITE)
                self.screen.blit(name, (row.x + 42, row.y + 4))
                meta = self.font_small.render(f"{info['price']}c   stock {info['qty']}", True, (180, 200, 140))
                self.screen.blit(meta, (row.x + 42, row.y + 18))
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
                        meta = self.font_small.render(f"sell {price}c each", True, (255, 200, 120))
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
        if self.bank_btn_rects.get("dep_inv") and self.bank_btn_rects["dep_inv"].collidepoint(mx, my):
            self.net.send("BANK_DEPOSIT", deposit_inventory=True)
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
        shift = bool(pygame.key.get_mods() & pygame.KMOD_SHIFT)
        for rect, slot in self.bank_slot_rects:
            if rect.collidepoint(mx, my):
                entry = (self.bank.get("bank") or {}).get(str(slot)) or (self.bank.get("bank") or {}).get(slot)
                if entry:
                    if shift:
                        self.net.send("BANK_WITHDRAW", slot_index=slot, qty=1)
                    else:
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
        box = pygame.Rect(90, 36, 760, 560)
        pygame.draw.rect(self.screen, (16, 18, 26), box, border_radius=8)
        pygame.draw.rect(self.screen, YELLOW, box, 2, border_radius=8)
        title = self.font_big.render("Equipment & Stats", True, WHITE)
        self.screen.blit(title, (box.x + 18, box.y + 12))
        name = (self.player or {}).get("name") or "You"
        cmb = self.player_combat_level()
        self.screen.blit(
            self.font.render(f"{name}  ·  Combat {cmb}", True, (180, 210, 255)),
            (box.x + 280, box.y + 18),
        )

        eq = self.player.get("equipment") or {}
        karma_lvl = (self.player.get("levels") or {}).get("karma", 1)
        bonuses = {"att_bonus": 0, "str_bonus": 0, "def_bonus": 0}
        for slot in ("helmet", "amulet", "ring", "weapon", "ammo", "shield", "body", "legs"):
            item_id = eq.get(slot)
            if not item_id:
                continue
            item = ITEMS.get(item_id) or {}
            kb = karma_slot_bonus(slot, karma_lvl)
            for k in bonuses:
                bonuses[k] += int(item.get(k, 0) or 0) + int(kb.get(k, 0) or 0)

        # --- Paperdoll stage (left) ---
        stage = pygame.Rect(box.x + 18, box.y + 52, 340, 460)
        pygame.draw.rect(self.screen, (24, 28, 38), stage, border_radius=8)
        pygame.draw.rect(self.screen, (70, 90, 120), stage, 1, border_radius=8)

        # Slot column on the left of the stage
        slot_size = 40
        slot_order = ("helmet", "amulet", "ring", "weapon", "body", "shield", "legs", "ammo")
        self.equip_slot_rects = {}
        inv = self.player.get("inventory") or {}
        slot_y0 = stage.y + 10
        for i, slot in enumerate(slot_order):
            item_id = eq.get(slot)
            sx = stage.x + 14
            sy = slot_y0 + i * (slot_size + 4)
            row = pygame.Rect(sx, sy, slot_size, slot_size)
            filled = bool(item_id)
            pygame.draw.rect(self.screen, (48, 54, 70) if filled else (30, 34, 44), row, border_radius=6)
            pygame.draw.rect(
                self.screen,
                (140, 190, 255) if filled else (70, 78, 95),
                row, 2 if filled else 1, border_radius=6,
            )
            self.equip_slot_rects[slot] = row
            tag = self.font_tiny.render(slot[:3].upper(), True, (130, 140, 160))
            self.screen.blit(tag, (row.x + 3, row.y + 1))
            if item_id:
                icon = pygame.Rect(row.x + 5, row.y + 11, 30, 26)
                sprites.draw_item_icon(self.screen, icon, item_id, ITEMS)
                if slot == "ammo" and item_id == "arrow_quiver":
                    qtot = int((self.player or {}).get("quiver_total") or 0)
                    qty = self.font_tiny.render(str(qtot), True, YELLOW)
                    self.screen.blit(qty, (row.x + 4, row.y + 26))
            else:
                empty = self.font_tiny.render("—", True, (80, 88, 100))
                self.screen.blit(empty, (row.centerx - empty.get_width() // 2, row.centery - 2))
            name_lbl = self.font_tiny.render(slot.title(), True, (160, 168, 185))
            self.screen.blit(name_lbl, (row.right + 8, row.y + 2))
            if item_id:
                short = (ITEMS.get(item_id) or {}).get("name", item_id)
                if len(short) > 14:
                    short = short[:13] + "…"
                self.screen.blit(
                    self.font_tiny.render(short, True, WHITE),
                    (row.right + 8, row.y + 16),
                )

        # Character preview on the right side of the stage
        preview_tile = 118
        cx = stage.x + 230
        cy = stage.y + 250
        floor = pygame.Rect(cx - 72, cy + 78, 144, 30)
        pygame.draw.ellipse(self.screen, (38, 48, 62), floor)
        pygame.draw.ellipse(self.screen, (55, 70, 90), floor, 1)
        body, skin, hair = (70, 210, 90), (235, 195, 150), (70, 45, 30)
        gender = (self.player or {}).get("gender") or "male"
        sprites.draw_humanoid_detailed(
            self.screen, cx, cy, preview_tile, body, skin, hair,
            weapon=weapon_style(eq.get("weapon")),
            shield=bool(eq.get("shield")),
            moving=False, t=0.0, facing=1,
            equipment=eq, attacking=0.0, action="stand",
            gender=gender,
        )
        self.draw_hp_bar(cx, floor.bottom + 4, self.player["hp"], self.player["max_hp"])

        # Hover / selected slot detail
        hover_slot = None
        mx, my = pygame.mouse.get_pos()
        for slot, rect in self.equip_slot_rects.items():
            if rect.collidepoint(mx, my):
                hover_slot = slot
                break
        detail_slot = hover_slot
        if detail_slot is None:
            for prefer in ("weapon", "body", "helmet", "shield", "legs", "amulet", "ring", "ammo"):
                if eq.get(prefer):
                    detail_slot = prefer
                    break
        detail_y = stage.bottom - 72
        pygame.draw.rect(self.screen, (20, 24, 34), (stage.x + 10, detail_y, stage.w - 20, 58), border_radius=6)
        if detail_slot:
            item_id = eq.get(detail_slot)
            item = ITEMS.get(item_id) if item_id else None
            if item:
                label_name = item["name"]
                if detail_slot == "ammo" and item_id == "arrow_quiver":
                    qtot = int((self.player or {}).get("quiver_total") or 0)
                    label_name = f"Arrow Quiver  ·  {qtot} arrows"
                elif detail_slot == "ammo":
                    qty = sum(int(e.get("qty") or 0) for e in inv.values() if e and e.get("item_id") == item_id)
                    label_name = f"{item['name']}  ×{qty}"
                self.screen.blit(
                    self.font_small.render(f"{detail_slot.title()}: {label_name}", True, WHITE),
                    (stage.x + 18, detail_y + 6),
                )
                kb = karma_slot_bonus(detail_slot, karma_lvl)
                if detail_slot == "ammo" and item_id == "arrow_quiver":
                    best = (self.player or {}).get("quiver_best")
                    best_item = ITEMS.get(best) or {}
                    detail = (
                        f"Fires best first · next: {best_item.get('name', '—')}  "
                        f"(+{best_item.get('ranged_att', 0)} att / +{best_item.get('ranged_str', 0)} str)"
                    )
                elif detail_slot == "ammo":
                    detail = (
                        f"Ranged +{item.get('ranged_att', 0)} att / "
                        f"+{item.get('ranged_str', 0)} str"
                    )
                else:
                    detail = (
                        f"Att +{item.get('att_bonus', 0)}(+{kb['att_bonus']}k)   "
                        f"Str +{item.get('str_bonus', 0)}(+{kb['str_bonus']}k)   "
                        f"Def +{item.get('def_bonus', 0)}(+{kb['def_bonus']}k)"
                    )
                self.screen.blit(
                    self.font_tiny.render(detail, True, (170, 175, 190)),
                    (stage.x + 18, detail_y + 26),
                )
                self.screen.blit(
                    self.font_tiny.render("Click slot to unequip", True, (120, 130, 150)),
                    (stage.x + 18, detail_y + 40),
                )
            else:
                self.screen.blit(
                    self.font_small.render(f"{detail_slot.title()}: empty", True, GREY),
                    (stage.x + 18, detail_y + 20),
                )
        else:
            self.screen.blit(
                self.font_small.render("No gear equipped — wear items from inventory", True, GREY),
                (stage.x + 18, detail_y + 20),
            )

        # --- Stats panel (right) ---
        panel = pygame.Rect(box.x + 372, box.y + 52, 370, 460)
        pygame.draw.rect(self.screen, (22, 26, 36), panel, border_radius=8)
        pygame.draw.rect(self.screen, (70, 90, 120), panel, 1, border_radius=8)

        levels = self.player.get("levels") or {}
        wb = self.player.get("gear_bonuses") or bonuses
        kb_tot = self.player.get("karma_bonuses") or {"att_bonus": 0, "str_bonus": 0, "def_bonus": 0}
        pot = self.player.get("stat_boosts") or {}
        y = panel.y + 14
        self.screen.blit(self.font.render("Worn bonuses", True, YELLOW), (panel.x + 14, y))
        y += 26
        for label, key, color in (
            ("Attack", "att_bonus", (255, 160, 120)),
            ("Strength", "str_bonus", (255, 200, 100)),
            ("Defence", "def_bonus", (140, 190, 255)),
        ):
            val = int(wb.get(key, 0))
            bar_bg = pygame.Rect(panel.x + 14, y + 16, panel.w - 28, 8)
            pygame.draw.rect(self.screen, (35, 40, 52), bar_bg, border_radius=3)
            fill_w = min(bar_bg.w, int(bar_bg.w * min(1.0, val / 200.0)))
            if fill_w > 0:
                pygame.draw.rect(self.screen, color, (bar_bg.x, bar_bg.y, fill_w, bar_bg.h), border_radius=3)
            self.screen.blit(self.font_small.render(f"{label}  +{val}", True, WHITE), (panel.x + 14, y))
            y += 36

        y += 4
        self.screen.blit(self.font.render("Combat levels", True, YELLOW), (panel.x + 14, y))
        y += 24

        def combat_line(label, skill, gear_key):
            base = int(levels.get(skill, 1))
            b = pot.get(skill) or {}
            amt = int(b.get("amount") or 0)
            gear = int(wb.get(gear_key, 0))
            if amt > 0:
                return f"{label}  {base + amt}", f"base {base}  pot +{amt}  gear +{gear}"
            return f"{label}  {base}", f"gear +{gear}"

        for skill_label, skill, gkey in (
            ("Attack", "attack", "att_bonus"),
            ("Strength", "strength", "str_bonus"),
            ("Defence", "defence", "def_bonus"),
            ("Archery", "archery", "att_bonus"),
            ("Hitpoints", "hitpoints", "def_bonus"),
        ):
            if skill == "hitpoints":
                main = f"Hitpoints  {self.player['hp']} / {self.player['max_hp']}"
                sub = f"level {levels.get('hitpoints', 1)}"
            elif skill == "archery":
                base = int(levels.get("archery", 1))
                main = f"Archery  {base}"
                ranged_att = int(wb.get("ranged_att", 0) or 0)
                ranged_str = int(wb.get("ranged_str", 0) or 0)
                sub = f"ranged +{ranged_att} att / +{ranged_str} str"
            else:
                main, sub = combat_line(skill_label, skill, gkey)
            self.screen.blit(self.font_small.render(main, True, WHITE), (panel.x + 18, y))
            self.screen.blit(self.font_tiny.render(sub, True, (150, 155, 170)), (panel.x + 18, y + 16))
            y += 34

        y += 2
        divider = pygame.Rect(panel.x + 14, y, panel.w - 28, 1)
        pygame.draw.rect(self.screen, (55, 65, 85), divider)
        y += 10
        self.screen.blit(
            self.font_small.render(
                f"Karma {levels.get('karma', 1)}   "
                f"(+{kb_tot.get('att_bonus', 0)}a / +{kb_tot.get('str_bonus', 0)}s / +{kb_tot.get('def_bonus', 0)}d)",
                True, (200, 190, 255),
            ),
            (panel.x + 14, y),
        )
        y += 22
        self.screen.blit(
            self.font_small.render(
                f"Combat {self.player_combat_level()}   ·   Total {self.player_total_level()}",
                True, (180, 255, 180),
            ),
            (panel.x + 14, y),
        )
        y += 28
        self.screen.blit(
            self.font_small.render("Hover a slot for details · Esc / E to close", True, GREY),
            (box.x + 20, box.y + box.h - 26),
        )

    def handle_equipment_click(self, mx, my):
        for slot, rect in getattr(self, "equip_slot_rects", {}).items():
            if rect.collidepoint(mx, my) and (self.player.get("equipment") or {}).get(slot):
                self.net.send("UNEQUIP", equip_slot=slot)
                return
        # click outside closes
        box = pygame.Rect(90, 36, 760, 560)
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
        if any(k in blob for k in ("dagger", "sword", "battleaxe", "axe", "scimitar", "cleaver", "arrowtip")):
            return "weapon"
        if "shield" in blob:
            return "shield"
        if "helmet" in blob or "cowl" in blob or "helm" in blob:
            return "helmet"
        if any(k in blob for k in ("chainbody", "platebody", "_body", "body")):
            return "body"
        if any(k in blob for k in ("chainlegs", "platelegs", "_legs", "legs")):
            return "legs"
        if any(k in blob for k in ("ring", "amulet", "jewelry")):
            return "jewelry"
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
            self.font_small.render("Click a recipe · choose Cook 1 or Cook all · Esc / C closes", True, GREY),
            (box.x + 16, box.y + box.h - 28),
        )

    def handle_cook_click(self, mx, my):
        for rect, rid in getattr(self, "cook_recipe_rects", []):
            if rect.collidepoint(mx, my):
                self.open_cook_prompt(rid)
                return
        box = pygame.Rect(220, 80, 520, 420)
        if not box.collidepoint(mx, my):
            self.show_cook = False

    def draw_fletch_modal(self):
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

    def handle_fletch_click(self, mx, my):
        for key, rect in getattr(self, "fletch_tab_rects", {}).items():
            if rect.collidepoint(mx, my):
                self.fletch_tab = key
                return
        for rect, rid in getattr(self, "fletch_recipe_rects", []):
            if rect.collidepoint(mx, my):
                self.net.send("CRAFT", recipe_id=rid, qty=1)
                return
        box = pygame.Rect(100, 40, 620, 560)
        if not box.collidepoint(mx, my):
            self.show_fletch = False

    def draw_skills_modal(self):
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
        n_skills = len(XP_SKILLS)
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
        for i, skill in enumerate(XP_SKILLS):
            row_top = y
            y += row_h
            if row_top + row_h < list_top or row_top > list_bottom:
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

    def _skills_scrollbar_mousedown(self, pos):
        meta = self.skills_scroll_meta
        if not meta or meta.get("max_scroll", 0) <= 0:
            return False
        track = meta["track"]
        thumb = meta.get("thumb")
        if thumb and thumb.collidepoint(pos):
            self.skills_drag = {"y0": pos[1], "scroll0": self.skills_scroll}
            return True
        if track.collidepoint(pos):
            # Jump scrollbar toward click
            view_h = meta["view_h"]
            max_scroll = meta["max_scroll"]
            thumb_h = thumb.h if thumb else 28
            rel = (pos[1] - track.y - thumb_h / 2) / max(1, view_h - thumb_h)
            self.skills_scroll = max(0, min(max_scroll, rel * max_scroll))
            self.skills_drag = {"y0": pos[1], "scroll0": self.skills_scroll}
            return True
        return False

    def _skills_scrollbar_drag(self, pos):
        meta = self.skills_scroll_meta
        drag = self.skills_drag
        if not meta or not drag or meta.get("max_scroll", 0) <= 0:
            return
        view_h = meta["view_h"]
        max_scroll = meta["max_scroll"]
        thumb = meta.get("thumb")
        thumb_h = thumb.h if thumb else 28
        dy = pos[1] - drag["y0"]
        span = max(1, view_h - thumb_h)
        self.skills_scroll = max(0, min(max_scroll, drag["scroll0"] + dy * max_scroll / span))

    def _shop_scrollbar_mousedown(self, pos):
        meta = self.shop_scroll_meta
        if not meta:
            return False
        for side in ("buy", "sell"):
            side_meta = meta.get(side) or {}
            max_scroll = float(side_meta.get("max_scroll") or 0)
            if max_scroll <= 0:
                continue
            track = side_meta.get("track")
            thumb = side_meta.get("thumb")
            if not track:
                continue
            if thumb and thumb.collidepoint(pos):
                scroll0 = self.shop_buy_scroll if side == "buy" else self.shop_sell_scroll
                self.shop_drag = {"side": side, "y0": pos[1], "scroll0": scroll0}
                return True
            if track.collidepoint(pos):
                view_h = side_meta["view_h"]
                thumb_h = thumb.h if thumb else 28
                rel = (pos[1] - track.y - thumb_h / 2) / max(1, view_h - thumb_h)
                scroll = max(0, min(max_scroll, rel * max_scroll))
                if side == "buy":
                    self.shop_buy_scroll = scroll
                else:
                    self.shop_sell_scroll = scroll
                self.shop_drag = {"side": side, "y0": pos[1], "scroll0": scroll}
                return True
        return False

    def _shop_scrollbar_drag(self, pos):
        meta = self.shop_scroll_meta
        drag = self.shop_drag
        if not meta or not drag:
            return
        side = drag.get("side")
        side_meta = meta.get(side) or {}
        max_scroll = float(side_meta.get("max_scroll") or 0)
        if max_scroll <= 0:
            return
        view_h = side_meta.get("view_h", 1)
        thumb = side_meta.get("thumb")
        thumb_h = thumb.h if thumb else 28
        dy = pos[1] - drag["y0"]
        span = max(1, view_h - thumb_h)
        scroll = max(0, min(max_scroll, drag["scroll0"] + dy * max_scroll / span))
        if side == "buy":
            self.shop_buy_scroll = scroll
        else:
            self.shop_sell_scroll = scroll

    def _inventory_drag_start(self, pos):
        if not self.player or not self.show_inventory:
            return False
        if self.show_skills or self.show_bank or self.show_forge or self.show_cook or self.show_fletch:
            return False
        if self.show_equipment or self.show_shop_panel or self.show_help or self.show_pets:
            return False
        if self.drop_prompt or self.arrow_prompt or self.tip_prompt or self.food_prompt or self.raw_prompt or self.food_bag_prompt or self.pack_prompt or self.log_prompt or self.potion_prompt or self.fire_prompt or self.cook_prompt or self.combat_style_prompt or self.trade_state:
            return False
        mx, my = pos
        if mx < SIDEBAR_X:
            return False
        for slot, rect in self.inventory_slot_rects().items():
            if rect.collidepoint(mx, my):
                entry = self.player["inventory"].get(str(slot)) or self.player["inventory"].get(slot)
                if not entry:
                    return False
                self.inv_drag = {
                    "from": slot, "ox": mx, "oy": my, "x": mx, "y": my,
                    "moved": False, "item_id": entry["item_id"], "qty": entry.get("qty", 1),
                }
                return True
        return False

    def _inventory_drag_end(self, pos):
        drag = self.inv_drag
        self.inv_drag = None
        if not drag or not self.player:
            return
        mx, my = pos
        to_slot = None
        for slot, rect in self.inventory_slot_rects().items():
            if rect.collidepoint(mx, my):
                to_slot = slot
                break
        if drag["moved"] and to_slot is not None and to_slot != drag["from"]:
            self.net.send("INV_MOVE", from_slot=drag["from"], to_slot=to_slot)
            return
        # No meaningful drag — treat as a normal inventory use click
        if not drag["moved"]:
            self.handle_inventory_click(drag["ox"], drag["oy"], 1)

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
        hint = self.font_tiny.render(
            "Scroll wheel / ↑↓ / drag bar  ·  H or Esc closes",
            True, GREY,
        )
        self.screen.blit(hint, (box.x + 16, box.y + 44))

        sections = [
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
                ("P / sidebar button", "Toggle auto-pickup items (coins always auto)"),
                ("X", "Toggle floating XP drops above your head (off = chat XP)"),
                ("Minimap left-click", "Walk toward that area"),
                ("Minimap right-click", "Open the scrollable world map"),
            ]),
            ("Panels", [
                ("Travel / Bank / Gear", "Sidebar buttons (also M / B / E)"),
                ("Inventory / Combat / Magic / Quests", "Sidebar tabs"),
                ("E", "Equipment paperdoll + Combat tab"),
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
                ("Q", "Quests sidebar tab"),
                ("1–5", "Combat XP style (or first-attack popup)"),
                ("Enter", "Open / send chat"),
                ("Scroll chat", "Mouse-wheel over chat to read history"),
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
            ("Tidehollow", [
                ("Cave mouth", "Harbourreach north — private 10-floor dungeon"),
                ("Per kill", "Coins/food/tips drop straight into your pack"),
                ("Clear floor", "Slay all beasts to advance; floor 10 = medal reward"),
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
                ("Right-click", "Drop prompt (1 / all) or bury bones"),
                ("Shift+right", "Drop the whole stack immediately"),
                ("Bags", "Pack/Unpack storage bags; crafting draws from bags first"),
            ]),
            ("Bank", [
                ("Deposit inventory", "Banks every tradeable item at once"),
                ("Vault click", "Withdraw stack · Shift+click = withdraw 1"),
                ("Shop sell", "Click = sell 1 · Shift+click = sell whole stack"),
                ("Esc", "Closes bank, shops, and most popups"),
            ]),
        ]

        list_top = box.y + 64
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

    def _help_scrollbar_mousedown(self, pos):
        meta = self.help_scroll_meta
        if not meta or meta.get("max_scroll", 0) <= 0:
            return False
        track = meta["track"]
        thumb = meta.get("thumb")
        if thumb and thumb.collidepoint(pos):
            self.help_drag = {"y0": pos[1], "scroll0": self.help_scroll}
            return True
        if track.collidepoint(pos):
            view_h = meta["view_h"]
            max_scroll = meta["max_scroll"]
            thumb_h = thumb.h if thumb else 28
            rel = (pos[1] - track.y - thumb_h / 2) / max(1, view_h - thumb_h)
            self.help_scroll = max(0, min(max_scroll, rel * max_scroll))
            self.help_drag = {"y0": pos[1], "scroll0": self.help_scroll}
            return True
        return False

    def _help_scrollbar_drag(self, pos):
        meta = self.help_scroll_meta
        drag = self.help_drag
        if not meta or not drag or meta.get("max_scroll", 0) <= 0:
            return
        view_h = meta["view_h"]
        max_scroll = meta["max_scroll"]
        thumb = meta.get("thumb")
        thumb_h = thumb.h if thumb else 28
        dy = pos[1] - drag["y0"]
        span = max(1, view_h - thumb_h)
        self.help_scroll = max(0, min(max_scroll, drag["scroll0"] + dy * max_scroll / span))

    def draw_leaderboard_modal(self):
        box = pygame.Rect(160, 70, 780, 580)
        pygame.draw.rect(self.screen, (14, 16, 24), box)
        pygame.draw.rect(self.screen, (230, 190, 70), box, 2)
        title = self.font_big.render("Hiscores — Top Players", True, YELLOW)
        self.screen.blit(title, (box.x + 20, box.y + 14))

        skills = self.leaderboard_skills or list(self.leaderboard.keys()) or (
            ["total"] + list(XP_SKILLS)
        )
        if not self.leaderboard_skill or self.leaderboard_skill not in skills:
            self.leaderboard_skill = "total" if "total" in skills else skills[0]
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
