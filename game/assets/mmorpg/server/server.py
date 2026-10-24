"""
Server-authoritative MMORPG v0.1 server.

Run with:  python server.py
Requires:  pip install websockets
"""
import asyncio
import json
import os
import time
import random
import itertools
import logging

import websockets

from content import (
    ITEMS, MONSTERS, MONSTER_SPAWNS, NPCS, SHOPS, QUESTS, XP_SKILLS, RESOURCE_YIELDS,
    CRAFT_RECIPES, INTERACTABLES, BUILDINGS, PETS, entrance_mouth_tiles,
    MAX_PURSE_COINS, MAX_BANK_COINS, MAX_ORES, ORE_ITEM_IDS, BANK_SLOTS,
    karma_total_bonus, FIRE_LOGS, cook_burn_chance, is_bow, bow_attack_range,
    weapon_stats, SWING_SECONDS_PER_SPEED,
    MAGIC_ABILITIES, MAGIC_ABILITY_ORDER, MANUAL_MAGIC_CD_FACTOR,
    QUIVER_CAPACITY, TIP_BOX_CAPACITY, FOOD_BAG_CAPACITY, RAW_BAG_CAPACITY,
    RESOURCE_BAG_CAPACITY, RAW_FISH_IDS, COOKED_FISH_IDS, FLETCH_POUCH_IDS,
    INVENTORY_SIZE, INVENTORY_TAB_SIZE, INVENTORY_TABS,
    is_arrowtip, is_raw_fish, is_cooked_fish,
    is_mining_bag_item, is_log_item, is_fletch_pouch_item, fletch_pouch_capacity, is_potion_item,
    is_gem_item,
    inventory_tab_for_item, is_storage_bag,
    TELEPORT_DESTINATIONS, TELEPORT_STARTER_MARKS, TELEPORT_DISCOVER_RADIUS,
    WIZARD_ID, drops_for_kill, LOW_LEVEL_DROP_CAP,
)
from database import Database
import explore_dungeons
import fishing_spots

from world_map import (
    generate_world, build_resource_nodes, is_walkable, WIDTH, HEIGHT, SPAWN_POINT, get_zone,
    room_containing, in_room, FLOOR, stamp_emberdeep_mouth, stamp_outfitters_shell,
    stamp_volcano_mine, near_volcano_mine, VOLCANO_RAT_LEASH, VOLCANO_WOLF_LEASH,
)
import combat
import dungeon as tidehollow
import dungeon_props
import emberdeep
import feature_flags

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("server")

# Private instance dungeons keyed by id (interactable dungeon_id / session.dungeon["id"])
DUNGEON_MODS = {
    "tidehollow": tidehollow,
    "emberdeep": emberdeep,
    "depths": explore_dungeons,
    "sanctum": explore_dungeons,
}
DUNGEON_META = {
    "tidehollow": {
        "name": "Tidehollow Cave",
        "chat_from": "Tidehollow",
        "medal_id": "tidehollow_amulet",
        "entrance_kinds": ("cave_entrance",),
        "floors_attr": "TIDEHOLLOW_FLOORS",
    },
    "emberdeep": {
        "name": "Emberdeep",
        "chat_from": "Emberdeep",
        "medal_id": "emberdeep_amulet",
        "entrance_kinds": ("volcano_entrance",),
        "floors_attr": "EMBERDEEP_FLOORS",
    },
    "depths": {
        "name": "The Depths",
        "chat_from": "Dungeon",
        "medal_id": None,
        "entrance_kinds": ("dungeon_entrance",),
        "floors_attr": None,
    },
    "sanctum": {
        "name": "Void Sanctum",
        "chat_from": "Void Sanctum",
        "medal_id": None,
        "entrance_kinds": ("dungeon_entrance",),
        "floors_attr": None,
    },
}

TICK_SECONDS = 0.6
# Idle logout (server-tracked). Only real player actions count; INPUT_PING may credit local input (a click that
# sends nothing) but never more than INPUT_PING_GRACE_TICKS past the last real action.
IDLE_WARN_TICKS = 450            # 4:30
IDLE_LOGOUT_TICKS = 500          # 5:00
COMBAT_LINGER_TICKS = 17         # 10 s after the last hit
PK_LINGER_TICKS = 100            # 60 s when PK-flagged
INPUT_PING_GRACE_TICKS = 50      # 30 s
PASSIVE_MESSAGE_TYPES = frozenset(("INPUT_PING",))
HOST = "0.0.0.0"
PORT = 8765

NPC_BY_ID = {n["id"]: n for n in NPCS}
import housing as _housing
import royal_treasury
import reputation
import apprentice
import property as _property
import nobility
import throne
import throne_live
import ruling
import politics
import politics_live
import outfits
import gear_rules
import welcome_kit
import copy as _copy
for _e in politics.ENVOYS:
    NPCS.append({"id": _e["id"], "name": _e["name"], "x": _e["x"], "y": _e["y"], "house": _e["house"],
                 "options": politics.ENVOY_OPTIONS, "lines": [politics.HOUSE_BLURB[_e["house"]]]})
for _c in politics.CRIERS:
    NPCS.append({"id": _c["id"], "name": _c["name"], "x": _c["x"], "y": _c["y"], "crier": True,
                 "lines": ["Hear ye! The notice boards carry the kingdom's news. Say /news for the latest."]})
for _b in politics.BOARDS:
    INTERACTABLES.append({
        "id": _b["id"], "kind": "signpost", "name": "Notice Board",
        "x": _b["x"], "y": _b["y"], "facing": "s",
        "lines": ["Village Notice Board", "Click for kingdom news"],
        "notice_board": True,
    })
_SHOP_STOCK_START = {sid: {iid: info.get("qty") for iid, info in shop["stock"].items()} for sid, shop in SHOPS.items()}
_housing.attach(NPCS)
for _n in NPCS:
    if _n.get("apprentice"):
        _n["options"] = apprentice.MASTER_OPTIONS
    elif _n.get("id") == "royal_herald":
        _n["options"] = throne.HERALD_OPTIONS
    elif _n.get("id") == "mistress_celia":
        _n["options"] = throne.CELIA_OPTIONS
    elif _n.get("id") == "chaplain_mirelle":
        _n["options"] = throne.CHAPLAIN_OPTIONS
    elif _n.get("id") == "chamberlain_aric":
        _n["options"] = nobility.CHAMBERLAIN_OPTIONS
    elif _n.get("id") == "estate_agent_mira":
        _n["options"] = _property.OFFICE_OPTIONS
NPC_BY_ID = {n["id"]: n for n in NPCS}
_next_id = itertools.count(1)


def next_id():
    return next(_next_id)


# ---------------------------------------------------------------------------
# In-memory session state
# ---------------------------------------------------------------------------
class PlayerSession:
    def __init__(self, ws, row):
        self.ws = ws
        self.row = row
        self.player_id = row["id"]
        self.username = row["username"]
        self.char_name = row["char_name"]
        self.x = row["x"]
        self.y = row["y"]
        self.hp = row["hp"]
        raw_gender = row["gender"] if "gender" in row.keys() else "male"
        self.gender = "female" if str(raw_gender).lower() == "female" else "male"
        self.last_wish_date = row["last_wish_date"] if "last_wish_date" in row.keys() else None
        self.knows_teleport = bool(row["knows_teleport"]) if "knows_teleport" in row.keys() else False
        self.teleport_marks = _parse_teleport_marks(
            row["teleport_marks"] if "teleport_marks" in row.keys() else "[]"
        )
        # Already taught before marks existed: keep the spell, seed the starters.
        self._teleport_marks_dirty = False
        if self.knows_teleport and not self.teleport_marks:
            self.teleport_marks = list(TELEPORT_STARTER_MARKS)
            self._teleport_marks_dirty = True
        self.player_killer = bool(row["player_killer"]) if "player_killer" in row.keys() else False
        self.pk_kills = int(row["pk_kills"]) if "pk_kills" in row.keys() else 0
        self.pk_locked_until = float(row["pk_locked_until"]) if "pk_locked_until" in row.keys() else 0.0
        self.teleport_ready_at = 0.0
        self.pending_wish_stat = False  # awaiting skill pick after rare power wish
        self.xp = {
            "attack": row["attack_xp"], "strength": row["strength_xp"], "defence": row["defence_xp"],
            "hitpoints": row["hitpoints_xp"], "woodcutting": row["woodcutting_xp"],
            "mining": row["mining_xp"], "fishing": row["fishing_xp"],
            "cooking": row["cooking_xp"] if "cooking_xp" in row.keys() else 0,
            "firemaking": row["firemaking_xp"] if "firemaking_xp" in row.keys() else 0,
            "smithing": row["smithing_xp"] if "smithing_xp" in row.keys() else 0,
            "fletching": row["fletching_xp"] if "fletching_xp" in row.keys() else 0,
            "archery": row["archery_xp"] if "archery_xp" in row.keys() else 0,
            "karma": row["karma_xp"] if "karma_xp" in row.keys() else 0,
            "charisma": row["charisma_xp"] if "charisma_xp" in row.keys() else 0,
            "etiquette": row["etiquette_xp"] if "etiquette_xp" in row.keys() else 0,
        }
        # A full life under the old hitpoints skill fills the new pool.
        # A wounded life stays wounded, and never sits above the new max.
        pool = self.max_hp()
        if self.hp >= self.level("hitpoints"):
            self.hp = pool
        else:
            self.hp = min(int(self.hp), pool)
        self.coins = min(int(row["coins"]), MAX_PURSE_COINS)
        self.bank_coins = int(row["bank_coins"]) if "bank_coins" in row.keys() else 0
        self.tax_notice_seen = bool(row["tax_notice_seen"]) if "tax_notice_seen" in row.keys() else False
        self.reputation = int(row["reputation"] or 0) if "reputation" in row.keys() else 0
        self.noble_rank = int(row["noble_rank"] or 0) if "noble_rank" in row.keys() else 0
        self.royal_title = row["royal_title"] if "royal_title" in row.keys() else None
        try:
            self.house_suffix = politics.title_suffix(royal_treasury._SETTINGS_CONN, self.player_id)
        except Exception:
            self.house_suffix = ""
        self.bank = {}  # slot -> {item_id, qty}
        self.equipment = {
            "weapon": row["equip_weapon"], "shield": row["equip_shield"],
            "body": row["equip_body"], "legs": row["equip_legs"],
            "helmet": row["equip_helmet"] if "equip_helmet" in row.keys() else None,
            "amulet": row["equip_amulet"] if "equip_amulet" in row.keys() else None,
            "ring": row["equip_ring"] if "equip_ring" in row.keys() else None,
            "ammo": row["equip_ammo"] if "equip_ammo" in row.keys() else None,
            "tool": row["equip_tool"] if "equip_tool" in row.keys() else None,
        }
        # Hatchets and pickaxes used to sit in the weapon slot; they live in the tool slot now.
        _w = self.equipment.get("weapon")
        if _w and (ITEMS.get(_w) or {}).get("equip_slot") == "tool" and not self.equipment.get("tool"):
            self.equipment["tool"], self.equipment["weapon"] = _w, None
            try:
                WORLD.db.set_equipment(self.player_id, "tool", _w)
                WORLD.db.set_equipment(self.player_id, "weapon", None)
            except Exception:
                pass
        self.inventory = {}  # slot -> {"item_id":, "qty":}
        self.quests = {}     # quest_id -> {"status":, "progress":}
        self.quest_log_dirty = False  # push QUEST_LOG on next tick flush
        self.in_combat_with = None   # ("monster", instance_id) or ("player", player_id)
        self.last_input_tick = None        # tick of the last counted input (idle logout)
        self.last_real_input_tick = None   # tick of the last real action message
        self.last_combat_tick = -10 ** 9   # last tick in combat or taking damage
        self.idle_warned = False
        self.idle_kicked = False
        self.idle_exempt = False           # ::idle off (dev testing)
        self.linger_until = None           # body left in the world after a mid-fight disconnect
        self._idle_hp = None
        # After STOP_ATTACK / flee-click, skip auto-retaliate until this time
        self.combat_flee_until = 0.0
        self.combat_rounds = 0
        self.combat_lock_id = None
        self.combat_style = "attack"  # attack unless the player picks strength or defence
        self.melee_style = "attack"
        self.gathering_node = None   # (x, y) currently gathering
        self.dungeon = None  # Tidehollow private instance state or None
        self.trade_partner_id = None
        self.trade_offer = {}        # slot -> qty
        self.trade_confirmed = False
        self.last_move_tick = 0
        self.last_equip_regen_at = 0.0  # passive HP from worn gear (e.g. Tidehollow Medal)
        self.auto_pickup_items = bool(row["auto_pickup_items"]) if "auto_pickup_items" in row.keys() else False
        raw_ignore = row["pickup_ignore"] if "pickup_ignore" in row.keys() else "[]"
        try:
            self.pickup_ignore = set(json.loads(raw_ignore or "[]"))
        except (TypeError, ValueError):
            self.pickup_ignore = set()
        # Missing column (pre-migration) => already allocated
        if "stats_allocated" in row.keys():
            self.stats_allocated = bool(row["stats_allocated"])
        else:
            self.stats_allocated = True
        self.pet_id = None
        if "active_pet" in row.keys() and row["active_pet"] in PETS:
            self.pet_id = row["active_pet"]
        self.owned_pets = []
        raw_owned = row["owned_pets"] if "owned_pets" in row.keys() else "[]"
        try:
            parsed = json.loads(raw_owned or "[]")
            if isinstance(parsed, list):
                self.owned_pets = [p for p in parsed if p in PETS]
        except (TypeError, json.JSONDecodeError):
            self.owned_pets = []
        # Migrate: active pet counts as owned (persisted on login)
        if self.pet_id and self.pet_id not in self.owned_pets:
            self.owned_pets.append(self.pet_id)
        self.pet_x = self.x
        self.pet_y = self.y
        self.pet_hp = PETS[self.pet_id]["hp"] if self.pet_id else 0
        self.pet_target_id = None  # monster instance id
        # Temporary combat potions: skill -> {"amount": int, "until": unix_ts}
        self.stat_boosts = {}
        # Quest magic — unlocked by quest points; cooldowns are session-local
        self.magic_auto = True
        self.magic_ready_at = {}  # ability_id -> unix timestamp when usable again
        # Arrow quiver contents: arrow_id -> qty (max QUIVER_CAPACITY each)
        self.quiver = {}
        raw_q = row["quiver_contents"] if "quiver_contents" in row.keys() else "{}"
        try:
            parsed_q = json.loads(raw_q or "{}")
            if isinstance(parsed_q, dict):
                for aid, qty in parsed_q.items():
                    if (ITEMS.get(aid) or {}).get("ammo_type") == "arrow":
                        self.quiver[aid] = max(0, min(int(QUIVER_CAPACITY), int(qty)))
        except (TypeError, json.JSONDecodeError, ValueError):
            self.quiver = {}
        # Arrowtip box contents: tip_id -> qty (max TIP_BOX_CAPACITY each)
        self.tip_box = {}
        raw_t = row["tip_box_contents"] if "tip_box_contents" in row.keys() else "{}"
        try:
            parsed_t = json.loads(raw_t or "{}")
            if isinstance(parsed_t, dict):
                for tid, qty in parsed_t.items():
                    if is_arrowtip(tid):
                        self.tip_box[tid] = max(0, min(int(TIP_BOX_CAPACITY), int(qty)))
        except (TypeError, json.JSONDecodeError, ValueError):
            self.tip_box = {}
        # Cooked / raw fish bags
        self.food_bag = {}
        raw_fb = row["food_bag_contents"] if "food_bag_contents" in row.keys() else "{}"
        try:
            parsed_fb = json.loads(raw_fb or "{}")
            if isinstance(parsed_fb, dict):
                for fid, qty in parsed_fb.items():
                    if is_cooked_fish(fid):
                        self.food_bag[fid] = max(0, min(int(FOOD_BAG_CAPACITY), int(qty)))
        except (TypeError, json.JSONDecodeError, ValueError):
            self.food_bag = {}
        self.raw_bag = {}
        raw_rb = row["raw_bag_contents"] if "raw_bag_contents" in row.keys() else "{}"
        try:
            parsed_rb = json.loads(raw_rb or "{}")
            if isinstance(parsed_rb, dict):
                for fid, qty in parsed_rb.items():
                    if is_raw_fish(fid):
                        self.raw_bag[fid] = max(0, min(int(RAW_BAG_CAPACITY), int(qty)))
        except (TypeError, json.JSONDecodeError, ValueError):
            self.raw_bag = {}
        self.mining_bag = self._load_bag_dict(row, "mining_bag_contents", is_mining_bag_item, RESOURCE_BAG_CAPACITY)
        self.log_bag = self._load_bag_dict(row, "log_bag_contents", is_log_item, RESOURCE_BAG_CAPACITY)
        self.fletch_pouch = self._load_bag_dict(row, "fletch_pouch_contents", is_fletch_pouch_item, fletch_pouch_capacity)
        self.potion_pouch = self._load_bag_dict(row, "potion_pouch_contents", is_potion_item, RESOURCE_BAG_CAPACITY)
        self.gem_bag = self._load_bag_dict(row, "gem_bag_contents", is_gem_item, RESOURCE_BAG_CAPACITY)

    @staticmethod
    def _load_bag_dict(row, column, predicate, capacity):
        out = {}
        raw = row[column] if column in row.keys() else "{}"
        try:
            parsed = json.loads(raw or "{}")
            if isinstance(parsed, dict):
                for iid, qty in parsed.items():
                    if predicate(iid):
                        cap = capacity(iid) if callable(capacity) else int(capacity)
                        out[iid] = max(0, min(int(cap), int(qty)))
        except (TypeError, json.JSONDecodeError, ValueError):
            return {}
        return out

    def level(self, skill):
        return combat.level_from_xp(self.xp[skill])

    def boost_amount(self, skill):
        buff = self.stat_boosts.get(skill)
        if not buff:
            return 0
        if time.time() >= buff["until"]:
            return 0
        return int(buff["amount"])

    def effective_level(self, skill):
        return self.level(skill) + self.boost_amount(skill)

    def apply_stat_boost(self, skill, amount, seconds):
        self.stat_boosts[skill] = {
            "amount": int(amount),
            "until": time.time() + float(seconds),
        }

    def active_boosts_public(self):
        now = time.time()
        out = {}
        for skill, buff in list(self.stat_boosts.items()):
            left = buff["until"] - now
            if left <= 0:
                del self.stat_boosts[skill]
                continue
            out[skill] = {
                "amount": int(buff["amount"]),
                "until": float(buff["until"]),
                "seconds_left": max(1, int(left + 0.999)),
            }
        return out

    def has_unlimited_wishes(self):
        return (self.username or "").strip().lower() == "david"

    def can_wish(self):
        if self.has_unlimited_wishes():
            return True
        today = time.strftime("%Y-%m-%d")
        return self.last_wish_date != today

    def mark_wish_used(self):
        if self.has_unlimited_wishes():
            return
        today = time.strftime("%Y-%m-%d")
        self.last_wish_date = today
        WORLD.db.save_player_stats(self.player_id, last_wish_date=today)

    def max_hp(self):
        """Hitpoints is the sum of the three highest combat skills, not its own XP."""
        arch = self.level("archery") if "archery" in self.xp else 1
        return combat.combat_level(
            self.level("attack"), self.level("strength"),
            self.level("defence"), archery=arch,
        )

    def combat_stats(self, attack_bonus=0, strength_bonus=0, defence_bonus=0):
        wb = self.weapon_bonuses()
        if self.using_bow():
            # Ranged hits use Archery only (accuracy + max hit) — not melee Attack/Strength.
            arch = self.effective_level("archery")
            return {
                "attack": arch,
                "strength": arch,
                "defence": self.effective_level("defence"),
                "attack_bonus": wb["ranged_att"],
                "strength_bonus": wb["ranged_str"],
                "defence_bonus": wb["def_bonus"],
            }
        return {
            "attack": self.effective_level("attack"),
            "strength": self.effective_level("strength"),
            "defence": self.effective_level("defence"),
            "attack_bonus": wb["att_bonus"],
            "strength_bonus": wb["str_bonus"],
            "defence_bonus": wb["def_bonus"],
        }

    def using_bow(self):
        return is_bow(self.equipment.get("weapon"))

    def attack_reach(self):
        if self.using_bow():
            return bow_attack_range(self.equipment.get("weapon"))
        return 1

    def weapon_bonuses(self):
        total = {
            "att_bonus": 0, "str_bonus": 0, "def_bonus": 0,
            "ranged_att": 0, "ranged_str": 0,
        }
        for slot_name, item_id in self.equipment.items():
            if not item_id:
                continue
            # Quiver itself has no combat bonus — arrows inside do
            if slot_name == "ammo" and item_id == "arrow_quiver":
                continue
            item = ITEMS.get(item_id, {})
            total["att_bonus"] += item.get("att_bonus", 0)
            total["str_bonus"] += item.get("str_bonus", 0)
            total["def_bonus"] += item.get("def_bonus", 0)
            total["ranged_att"] += item.get("ranged_att", 0)
            total["ranged_str"] += item.get("ranged_str", 0)
        # Best arrow currently in the quiver contributes ranged bonuses
        if self.equipment.get("ammo") == "arrow_quiver":
            best = self.best_quiver_arrow()
            if best:
                ab = ITEMS.get(best) or {}
                total["ranged_att"] += int(ab.get("ranged_att") or 0)
                total["ranged_str"] += int(ab.get("ranged_str") or 0)
        karma = self.level("karma") if "karma" in self.xp else 1
        for k, v in karma_total_bonus(karma, self.equipment).items():
            total[k] += v
        return total

    def jewelry_ability_total(self, ability_name):
        """Sum ability_value / ability2_value for a named jewelry special across ring+amulet."""
        total = 0.0
        for slot in ("ring", "amulet"):
            iid = self.equipment.get(slot)
            if not iid:
                continue
            it = ITEMS.get(iid) or {}
            if it.get("ability") == ability_name:
                total += float(it.get("ability_value") or 0)
            if it.get("ability2") == ability_name:
                total += float(it.get("ability2_value") or 0)
        return total

    def jewelry_crit_mult(self):
        """Best critical multiplier among worn jewelry (default 1.5)."""
        best = 1.5
        for slot in ("ring", "amulet"):
            iid = self.equipment.get(slot)
            if not iid:
                continue
            it = ITEMS.get(iid) or {}
            if it.get("ability") == "crit":
                best = max(best, float(it.get("ability_mult") or 1.5))
            if it.get("ability2") == "crit":
                best = max(best, float(it.get("ability2_mult") or 1.5))
        return best

    def jewelry_specials_public(self):
        """Worn jewelry special totals for the combat UI."""
        ls = min(0.40, self.jewelry_ability_total("lifesteal"))
        crit = min(0.45, self.jewelry_ability_total("crit"))
        dodge = min(0.35, self.jewelry_ability_total("dodge"))
        thorns = min(0.50, self.jewelry_ability_total("thorns"))
        void_strike = int(self.jewelry_ability_total("void_strike"))
        void_ward = int(self.jewelry_ability_total("void_ward"))
        return {
            "lifesteal": ls,
            "crit": crit,
            "crit_mult": self.jewelry_crit_mult() if crit > 0 else 1.0,
            "dodge": dodge,
            "thorns": thorns,
            "void_strike": void_strike,
            "void_ward": void_ward,
        }

    def quiver_equipped(self):
        return self.equipment.get("ammo") == "arrow_quiver"

    def auto_equip_quiver(self):
        """Wear an available quiver when a bow needs it. Returns whether one was worn."""
        if self.equipment.get("ammo"):
            return False
        slot = next(
            (slot for slot, entry in self.inventory.items()
             if entry and entry.get("item_id") == "arrow_quiver"),
            None,
        )
        if slot is None:
            return False
        self.equipment["ammo"] = "arrow_quiver"
        WORLD.db.set_equipment(self.player_id, "ammo", "arrow_quiver")
        WORLD.remove_item_qty(self, "arrow_quiver", 1)
        return True

    def best_quiver_arrow(self):
        """Highest-tier arrow currently stored in the quiver, or None."""
        best_id = None
        best_key = None
        for aid, qty in self.quiver.items():
            if int(qty or 0) <= 0:
                continue
            item = ITEMS.get(aid) or {}
            if item.get("ammo_type") != "arrow":
                continue
            key = (int(item.get("ranged_str") or 0), int(item.get("ranged_att") or 0))
            if best_key is None or key > best_key:
                best_key = key
                best_id = aid
        return best_id

    def quiver_total(self):
        return sum(int(q or 0) for q in self.quiver.values())

    def save_quiver(self):
        WORLD.db.save_player_stats(self.player_id, quiver_contents=json.dumps(self.quiver))

    def deposit_arrows_to_quiver(self, arrow_id, qty):
        """Move up to qty arrows from inventory into the quiver. Returns amount deposited."""
        item = ITEMS.get(arrow_id) or {}
        if item.get("ammo_type") != "arrow":
            return 0
        have = WORLD.count_item(self, arrow_id)
        if have <= 0 or qty <= 0:
            return 0
        cur = int(self.quiver.get(arrow_id) or 0)
        space = max(0, int(QUIVER_CAPACITY) - cur)
        take = min(int(qty), have, space)
        if take <= 0:
            return 0
        WORLD.remove_item_qty(self, arrow_id, take)
        self.quiver[arrow_id] = cur + take
        self.save_quiver()
        return take

    def has_tip_box(self):
        return WORLD.count_item(self, "arrowtip_box") > 0

    def tip_box_total(self):
        return sum(int(q or 0) for q in self.tip_box.values())

    def save_tip_box(self):
        WORLD.db.save_player_stats(self.player_id, tip_box_contents=json.dumps(self.tip_box))

    def deposit_tips_to_box(self, tip_id, qty):
        """Move up to qty arrowtips from inventory into the tip box. Returns amount deposited."""
        if not is_arrowtip(tip_id) or not self.has_tip_box():
            return 0
        have = WORLD.count_item(self, tip_id)
        if have <= 0 or qty <= 0:
            return 0
        cur = int(self.tip_box.get(tip_id) or 0)
        space = max(0, int(TIP_BOX_CAPACITY) - cur)
        take = min(int(qty), have, space)
        if take <= 0:
            return 0
        WORLD.remove_item_qty(self, tip_id, take)
        self.tip_box[tip_id] = cur + take
        self.save_tip_box()
        return take

    def has_food_bag(self):
        return WORLD.count_item(self, "food_bag") > 0

    def food_bag_total(self):
        return sum(int(q or 0) for q in self.food_bag.values())

    def save_food_bag(self):
        WORLD.db.save_player_stats(self.player_id, food_bag_contents=json.dumps(self.food_bag))

    def deposit_cooked_to_food_bag(self, food_id, qty):
        if not is_cooked_fish(food_id) or not self.has_food_bag():
            return 0
        have = WORLD.count_item(self, food_id)
        if have <= 0 or qty <= 0:
            return 0
        cur = int(self.food_bag.get(food_id) or 0)
        space = max(0, int(FOOD_BAG_CAPACITY) - cur)
        take = min(int(qty), have, space)
        if take <= 0:
            return 0
        WORLD.remove_item_qty(self, food_id, take)
        self.food_bag[food_id] = cur + take
        self.save_food_bag()
        return take

    def best_food_bag_item(self):
        """Highest-heal cooked fish currently in the food bag, or None."""
        best_id = None
        best_heal = -1
        for fid, qty in self.food_bag.items():
            if int(qty or 0) <= 0:
                continue
            heal = int((ITEMS.get(fid) or {}).get("heal") or 0)
            if heal > best_heal:
                best_heal = heal
                best_id = fid
        return best_id

    def eat_one_from_food_bag(self):
        """Eat one highest-heal fish from the food bag. Returns (ok, name, heal)."""
        if not self.has_food_bag():
            return False, None, 0
        fid = self.best_food_bag_item()
        if not fid:
            return False, None, 0
        item = ITEMS.get(fid) or {}
        heal = int(item.get("heal") or 0)
        self.food_bag[fid] = int(self.food_bag.get(fid) or 0) - 1
        if self.food_bag[fid] <= 0:
            del self.food_bag[fid]
        self.save_food_bag()
        if heal > 0:
            self.hp = min(self.max_hp(), self.hp + heal)
            WORLD.db.save_player_stats(self.player_id, hp=self.hp)
        return True, item.get("name", fid), heal

    def count_owned_item(self, item_id):
        """Inventory qty + potion-pouch stock when the pouch is owned."""
        n = WORLD.count_item(self, item_id)
        if is_potion_item(item_id) and self.has_potion_pouch():
            n += int(self.potion_pouch.get(item_id) or 0)
        return n

    def take_one_owned_item(self, item_id):
        """Remove one from inventory first, else from potion pouch. Returns True if taken."""
        if WORLD.count_item(self, item_id) > 0:
            return WORLD.remove_item_qty(self, item_id, 1)
        if is_potion_item(item_id) and self.has_potion_pouch():
            before = int(self.potion_pouch.get(item_id) or 0)
            if before <= 0:
                return False
            self._take_from_bag(self.potion_pouch, "potion_pouch_contents", item_id, 1)
            return True
        return False

    def best_boost_potion_id(self, skill):
        """Best attack/strength/defence potion id owned (inventory or pouch)."""
        best_id = None
        best_amt = -1
        for iid, it in ITEMS.items():
            if it.get("boost_skill") != skill:
                continue
            if self.count_owned_item(iid) <= 0:
                continue
            amt = int(it.get("boost_amount") or 0)
            if amt > best_amt:
                best_amt = amt
                best_id = iid
        return best_id

    def has_raw_bag(self):
        return WORLD.count_item(self, "raw_food_bag") > 0

    def raw_bag_total(self):
        return sum(int(q or 0) for q in self.raw_bag.values())

    def save_raw_bag(self):
        WORLD.db.save_player_stats(self.player_id, raw_bag_contents=json.dumps(self.raw_bag))

    def deposit_raw_to_raw_bag(self, food_id, qty):
        if not is_raw_fish(food_id) or not self.has_raw_bag():
            return 0
        have = WORLD.count_item(self, food_id)
        if have <= 0 or qty <= 0:
            return 0
        cur = int(self.raw_bag.get(food_id) or 0)
        space = max(0, int(RAW_BAG_CAPACITY) - cur)
        take = min(int(qty), have, space)
        if take <= 0:
            return 0
        WORLD.remove_item_qty(self, food_id, take)
        self.raw_bag[food_id] = cur + take
        self.save_raw_bag()
        return take

    def _has_bag_item(self, item_id):
        return WORLD.count_item(self, item_id) > 0

    def _bag_total(self, bag):
        return sum(int(q or 0) for q in bag.values())

    def _deposit_resource_bag(self, bag, save_col, capacity, predicate, bag_item_id, item_id, qty):
        if not predicate(item_id) or not self._has_bag_item(bag_item_id):
            return 0
        have = WORLD.count_item(self, item_id)
        if have <= 0 or qty <= 0:
            return 0
        cur = int(bag.get(item_id) or 0)
        cap = capacity(item_id) if callable(capacity) else int(capacity)
        space = max(0, int(cap) - cur)
        take = min(int(qty), have, space)
        if take <= 0:
            return 0
        WORLD.remove_item_qty(self, item_id, take)
        bag[item_id] = cur + take
        WORLD.db.save_player_stats(self.player_id, **{save_col: json.dumps(bag)})
        return take

    def _withdraw_bag_to_inventory(self, bag, save_col):
        """Move as many bag items as will fit into inventory. Returns (moved, left_in_bag)."""
        moved = 0
        for iid in list(bag.keys()):
            qty = int(bag.get(iid) or 0)
            while qty > 0:
                item = ITEMS.get(iid) or {}
                chunk = qty if item.get("stackable") else min(1, qty)
                if WORLD.add_item_to_inventory(self, iid, chunk):
                    moved += chunk
                    qty -= chunk
                elif chunk > 1 and WORLD.add_item_to_inventory(self, iid, 1):
                    moved += 1
                    qty -= 1
                else:
                    break  # no room for this item — try others
                if qty <= 0:
                    bag.pop(iid, None)
                else:
                    bag[iid] = qty
        WORLD.db.save_player_stats(self.player_id, **{save_col: json.dumps(bag)})
        return moved, self._bag_total(bag)

    def has_mining_bag(self):
        return self._has_bag_item("mining_bag")

    def deposit_mining_bag(self, item_id, qty):
        return self._deposit_resource_bag(
            self.mining_bag, "mining_bag_contents", RESOURCE_BAG_CAPACITY,
            is_mining_bag_item, "mining_bag", item_id, qty,
        )

    def has_log_bag(self):
        return self._has_bag_item("log_bag")

    def deposit_log_bag(self, item_id, qty):
        return self._deposit_resource_bag(
            self.log_bag, "log_bag_contents", RESOURCE_BAG_CAPACITY,
            is_log_item, "log_bag", item_id, qty,
        )

    def has_fletch_pouch(self):
        return self._has_bag_item("fletch_pouch")

    def deposit_fletch_pouch(self, item_id, qty):
        return self._deposit_resource_bag(
            self.fletch_pouch, "fletch_pouch_contents", fletch_pouch_capacity,
            is_fletch_pouch_item, "fletch_pouch", item_id, qty,
        )

    def has_potion_pouch(self):
        return self._has_bag_item("potion_pouch")

    def deposit_potion_pouch(self, item_id, qty):
        return self._deposit_resource_bag(
            self.potion_pouch, "potion_pouch_contents", RESOURCE_BAG_CAPACITY,
            is_potion_item, "potion_pouch", item_id, qty,
        )

    def has_gem_bag(self):
        return self._has_bag_item("gem_bag")

    def deposit_gem_bag(self, item_id, qty):
        return self._deposit_resource_bag(
            self.gem_bag, "gem_bag_contents", RESOURCE_BAG_CAPACITY,
            is_gem_item, "gem_bag", item_id, qty,
        )

    def available_craft_input(self, item_id):
        """Inventory count + bag stock when the matching container is owned."""
        n = WORLD.count_item(self, item_id)
        if is_arrowtip(item_id) and self.has_tip_box():
            n += int(self.tip_box.get(item_id) or 0)
        if is_raw_fish(item_id) and self.has_raw_bag():
            n += int(self.raw_bag.get(item_id) or 0)
        if is_cooked_fish(item_id) and self.has_food_bag():
            n += int(self.food_bag.get(item_id) or 0)
        if is_mining_bag_item(item_id) and self.has_mining_bag():
            n += int(self.mining_bag.get(item_id) or 0)
        if is_log_item(item_id) and self.has_log_bag():
            n += int(self.log_bag.get(item_id) or 0)
        if is_fletch_pouch_item(item_id) and self.has_fletch_pouch():
            n += int(self.fletch_pouch.get(item_id) or 0)
        if is_gem_item(item_id) and self.has_gem_bag():
            n += int(self.gem_bag.get(item_id) or 0)
        return n

    def _take_from_bag(self, bag, save_col, item_id, remaining):
        in_bag = int(bag.get(item_id) or 0)
        take = min(remaining, in_bag)
        if take <= 0:
            return remaining
        left = in_bag - take
        if left <= 0:
            bag.pop(item_id, None)
        else:
            bag[item_id] = left
        WORLD.db.save_player_stats(self.player_id, **{save_col: json.dumps(bag)})
        return remaining - take

    def consume_craft_input(self, item_id, qty):
        """Spend crafting inputs — resource bags first, then inventory."""
        remaining = int(qty)
        if remaining <= 0:
            return True
        if is_arrowtip(item_id) and self.has_tip_box():
            remaining = self._take_from_bag(self.tip_box, "tip_box_contents", item_id, remaining)
        if remaining > 0 and is_raw_fish(item_id) and self.has_raw_bag():
            remaining = self._take_from_bag(self.raw_bag, "raw_bag_contents", item_id, remaining)
        if remaining > 0 and is_cooked_fish(item_id) and self.has_food_bag():
            remaining = self._take_from_bag(self.food_bag, "food_bag_contents", item_id, remaining)
        if remaining > 0 and is_mining_bag_item(item_id) and self.has_mining_bag():
            remaining = self._take_from_bag(self.mining_bag, "mining_bag_contents", item_id, remaining)
        if remaining > 0 and is_log_item(item_id) and self.has_log_bag():
            remaining = self._take_from_bag(self.log_bag, "log_bag_contents", item_id, remaining)
        if remaining > 0 and is_fletch_pouch_item(item_id) and self.has_fletch_pouch():
            remaining = self._take_from_bag(self.fletch_pouch, "fletch_pouch_contents", item_id, remaining)
        if remaining > 0 and is_gem_item(item_id) and self.has_gem_bag():
            remaining = self._take_from_bag(self.gem_bag, "gem_bag_contents", item_id, remaining)
        if remaining > 0:
            return WORLD.remove_item_qty(self, item_id, remaining)
        return True

    def refund_craft_input(self, item_id, qty):
        """Undo a craft consume — prefer packing materials back into bags."""
        qty = int(qty)
        if qty <= 0:
            return
        WORLD.add_item_to_inventory(self, item_id, qty)
        if is_arrowtip(item_id) and self.has_tip_box():
            self.deposit_tips_to_box(item_id, qty)
        elif is_raw_fish(item_id) and self.has_raw_bag():
            self.deposit_raw_to_raw_bag(item_id, qty)
        elif is_cooked_fish(item_id) and self.has_food_bag():
            self.deposit_cooked_to_food_bag(item_id, qty)
        elif is_mining_bag_item(item_id) and self.has_mining_bag():
            self.deposit_mining_bag(item_id, qty)
        elif is_log_item(item_id) and self.has_log_bag():
            self.deposit_log_bag(item_id, qty)
        elif is_fletch_pouch_item(item_id) and self.has_fletch_pouch():
            self.deposit_fletch_pouch(item_id, qty)
        elif is_gem_item(item_id) and self.has_gem_bag():
            self.deposit_gem_bag(item_id, qty)

    def has_arrow_ammo(self):
        if self.quiver_equipped():
            return self.best_quiver_arrow() is not None
        # Legacy: ammo slot pointing at an arrow type still in inventory
        ammo_id = self.equipment.get("ammo")
        if not ammo_id:
            return False
        item = ITEMS.get(ammo_id) or {}
        if item.get("ammo_type") != "arrow":
            return False
        return WORLD.count_item(self, ammo_id) > 0

    def consume_one_arrow(self):
        """Spend one arrow — quiver uses best tier first; legacy ammo uses inventory."""
        if self.quiver_equipped():
            aid = self.best_quiver_arrow()
            if not aid:
                return False
            self.quiver[aid] = int(self.quiver.get(aid) or 0) - 1
            if self.quiver[aid] <= 0:
                del self.quiver[aid]
            self.save_quiver()
            return True
        ammo_id = self.equipment.get("ammo")
        if not ammo_id:
            return False
        item = ITEMS.get(ammo_id) or {}
        if item.get("ammo_type") != "arrow":
            return False
        if WORLD.count_item(self, ammo_id) <= 0:
            self.equipment["ammo"] = None
            WORLD.db.set_equipment(self.player_id, "ammo", None)
            return False
        WORLD.remove_item_qty(self, ammo_id, 1)
        if WORLD.count_item(self, ammo_id) <= 0:
            self.equipment["ammo"] = None
            WORLD.db.set_equipment(self.player_id, "ammo", None)
        return True

    def gathering_public(self):
        """Visible gather action for other clients (skill + resource tile)."""
        if not self.gathering_node:
            return None
        node = WORLD.resource_nodes.get(self.gathering_node)
        if not node or node.get("depleted"):
            return None
        ydef = RESOURCE_YIELDS.get(node["type"])
        if not ydef:
            return None
        gx, gy = self.gathering_node
        return {
            "skill": ydef["skill"],
            "x": gx,
            "y": gy,
            "resource": node["type"],
            "tool": WORLD.gather_tool_id(self, ydef["skill"], ydef.get("tools")),
        }

    def _row_val(self, key, default=None):
        if key in self.row.keys():
            return self.row[key]
        return default

    def appearance_state(self):
        import json
        appearance = None
        raw = self._row_val("appearance")
        if raw:
            try:
                appearance = json.loads(raw)
            except Exception:
                appearance = None
        # None is only for a brand-new account. That is what opens the creator.
        # Anyone who already spent their stat points gets a look in the payload
        # only — nothing is written back to the database.
        # Only the new HD skins are shown: a look without any outfit is shown in the free starter set
        # (Villager / Village Lady), armour or not. Payload only; the saved look is untouched.
        if self.stats_allocated:
            base = outfits.normalise(appearance) if isinstance(appearance, dict) else None
            if not outfits.has_outfit(base):
                appearance = outfits.starter_look(self.gender, base)
        if appearance is None and self.stats_allocated:
            if self.gender == "female":
                appearance = {
                    "skin": "skin_base", "skin_tone": "tone_3", "hair": "hair_ponytail", "hair_colour": "chestnut",
                    "top": "top_linen_shirt", "bottom": "bottom_long_skirt", "shoes": "shoes_leather",
                    "outfit": None, "accessories": [],
                }
            else:
                appearance = {
                    "skin": "skin_base", "skin_tone": "tone_3", "hair": "hair_side_part", "hair_colour": "dark_brown",
                    "top": "top_linen_shirt", "bottom": "bottom_work_trousers", "shoes": "shoes_leather",
                    "outfit": None, "accessories": [],
                }
        if isinstance(appearance, dict):
            try:
                appearance = outfits.strip_regalia(self, outfits.normalise(appearance))
            except Exception:
                logging.getLogger("outfits").exception("appearance normalise failed")
        return appearance

    def appearance_saved(self):
        return bool(self._row_val("appearance"))

    def _json_list(self, key):
        import json
        raw = self._row_val(key)
        if not raw:
            return []
        try:
            data = json.loads(raw)
        except Exception:
            return []
        return data if isinstance(data, list) else []

    def public_state(self):
        return {
            "id": self.player_id, "name": self.char_name, "x": self.x, "y": self.y,
            "hp": self.hp, "max_hp": self.max_hp(),
            "combat_level": self.combat_level(),
            "equipment": self.equipment,  # client uses this for sprite weapons/armor
            # Skill levels, so another player can examine you. Levels only —
            # no XP and no inventory, and nothing the highscore tables do not
            # already publish.
            "levels": {s: self.level(s) for s in ("attack", "strength", "defence",
                                                  "hitpoints", "archery")},
            "gathering": self.gathering_public(),
            "gender": self.gender,
            "noble_rank": int(getattr(self, "noble_rank", 0) or 0),
            "noble_title": nobility.title_prefix(getattr(self, "noble_rank", 0), self.gender,
                                                 getattr(self, "royal_title", None)),
            "royal_title": getattr(self, "royal_title", None),
            "house_suffix": getattr(self, "house_suffix", ""),
            "player_killer": bool(self.player_killer),
            "pk_kills": int(self.pk_kills or 0),
            "appearance": self.appearance_state(),
            "hd_player": bool(self._row_val("hd_player", 1)),
        }

    def total_level(self):
        return sum(self.level(s) for s in XP_SKILLS)

    def combat_level(self):
        """Top three combat skills, plus karma level."""
        base = combat.combat_level(
            self.level("attack"), self.level("strength"),
            self.level("defence"), self.level("hitpoints"),
            self.level("archery") if "archery" in self.xp else 1,
        )
        karma = self.level("karma") if "karma" in self.xp else 1
        return base + karma

    def full_state(self):
        wb = self.weapon_bonuses()
        karma_lvl = self.level("karma") if "karma" in self.xp else 1
        levels = {s: self.level(s) for s in XP_SKILLS}
        appearance = self.appearance_state()
        
        return {
            "id": self.player_id, "name": self.char_name, "x": self.x, "y": self.y,
            "hp": self.hp, "max_hp": self.max_hp(), "coins": self.coins,
            "bank_coins": self.bank_coins,
            "reputation": int(getattr(self, "reputation", 0) or 0),
            "rep_tier": reputation.tier(getattr(self, "reputation", 0)),
            "work": _work_state(self.player_id),
            "noble_rank": int(getattr(self, "noble_rank", 0) or 0),
            "noble_title": nobility.title_prefix(getattr(self, "noble_rank", 0), self.gender,
                                                 getattr(self, "royal_title", None)),
            "noble_rank_name": nobility.rank_name(getattr(self, "noble_rank", 0), self.gender),
            "royal_title": getattr(self, "royal_title", None),
            "house_suffix": getattr(self, "house_suffix", ""),
            "kingdom": politics.hud_line(WORLD.db.conn),
            "levels": levels,
            "xp": {s: self.xp[s] for s in XP_SKILLS if s in self.xp},
            "total_level": sum(levels.values()),
            "combat_level": self.combat_level(),
            "equipment": self.equipment,
            "inventory": self.inventory,
            "combat_style": self.combat_style,
            "auto_pickup_items": self.auto_pickup_items,
            "pickup_ignore": sorted(self.pickup_ignore),
            "stats_allocated": self.stats_allocated,
            "max_purse_coins": MAX_PURSE_COINS,
            "max_bank_coins": MAX_BANK_COINS,
            "max_ores": MAX_ORES,
            "gear_bonuses": wb,
            "jewelry_specials": self.jewelry_specials_public(),
            "karma_bonuses": karma_total_bonus(karma_lvl, self.equipment),
            "pet_id": self.pet_id,
            "pet": self.pet_public() if self.pet_id else None,
            "owned_pets": self.owned_pets_public(),
            "stat_boosts": self.active_boosts_public(),
            "gathering": self.gathering_public(),
            "gender": self.gender,
            "appearance": appearance,
            "appearance_saved": self.appearance_saved(),
            "owned_cosmetics": self._json_list("owned_cosmetics"),
            "saved_outfits": outfits.saved_slots(self._json_list("saved_outfits")),
            "outfit_unlocks": outfits.unlocks(self, WORLD.db.conn),
            "outfit_pricing": _outfit_pricing(self),
            "hd_player": bool(self._row_val("hd_player", 1)),
            "wish_available": self.can_wish(),
            "unlimited_wishes": self.has_unlimited_wishes(),
            "quest_points": self.quest_points(),
            "magic": self.magic_public(),
            "quiver": dict(self.quiver),
            "quiver_arrows": dict(self.quiver),
            "quiver_capacity": int(QUIVER_CAPACITY),
            "quiver_total": self.quiver_total(),
            "quiver_best": self.best_quiver_arrow() if self.quiver_equipped() else None,
            "tip_box": dict(self.tip_box) if self.has_tip_box() else {},
            "tip_box_capacity": int(TIP_BOX_CAPACITY),
            "tip_box_total": self.tip_box_total() if self.has_tip_box() else 0,
            "has_tip_box": self.has_tip_box(),
            "food_bag": dict(self.food_bag) if self.has_food_bag() else {},
            "food_bag_capacity": int(FOOD_BAG_CAPACITY),
            "food_bag_total": self.food_bag_total() if self.has_food_bag() else 0,
            "has_food_bag": self.has_food_bag(),
            "raw_bag": dict(self.raw_bag) if self.has_raw_bag() else {},
            "raw_bag_capacity": int(RAW_BAG_CAPACITY),
            "raw_bag_total": self.raw_bag_total() if self.has_raw_bag() else 0,
            "has_raw_bag": self.has_raw_bag(),
            "mining_bag": dict(self.mining_bag) if self.has_mining_bag() else {},
            "mining_bag_total": self._bag_total(self.mining_bag) if self.has_mining_bag() else 0,
            "has_mining_bag": self.has_mining_bag(),
            "log_bag": dict(self.log_bag) if self.has_log_bag() else {},
            "log_bag_total": self._bag_total(self.log_bag) if self.has_log_bag() else 0,
            "has_log_bag": self.has_log_bag(),
            "fletch_pouch": dict(self.fletch_pouch) if self.has_fletch_pouch() else {},
            "fletch_pouch_total": self._bag_total(self.fletch_pouch) if self.has_fletch_pouch() else 0,
            "has_fletch_pouch": self.has_fletch_pouch(),
            "feather_bag_capacity": int(fletch_pouch_capacity("feather")),
            "potion_pouch": dict(self.potion_pouch) if self.has_potion_pouch() else {},
            "potion_pouch_total": self._bag_total(self.potion_pouch) if self.has_potion_pouch() else 0,
            "has_potion_pouch": self.has_potion_pouch(),
            "gem_bag": dict(self.gem_bag) if self.has_gem_bag() else {},
            "gem_bag_total": self._bag_total(self.gem_bag) if self.has_gem_bag() else 0,
            "has_gem_bag": self.has_gem_bag(),
            "resource_bag_capacity": int(RESOURCE_BAG_CAPACITY),
            "inventory_tabs": list(INVENTORY_TABS),
            "inventory_tab_size": int(INVENTORY_TAB_SIZE),
            "inventory_size": int(INVENTORY_SIZE),
            "knows_teleport": bool(self.knows_teleport),
            "teleport_marks": list(self.teleport_marks),
            "player_killer": bool(self.player_killer),
            "pk_kills": int(self.pk_kills or 0),
            "pk_locked_until": float(self.pk_locked_until or 0),
            "house_level": int(getattr(self, "house_level", 0) or 0),
            "home": (
                _housing.home_info(WORLD.db.conn, self.player_id)
                if feature_flags.USE_PLAYER_HOUSING and WORLD is not None else None
            ),
        }

    def quest_points(self):
        total = 0
        for qid, prog in self.quests.items():
            if (prog or {}).get("status") != "complete":
                continue
            total += int(QUESTS.get(qid, {}).get("quest_points") or 0)
        return total

    def magic_public(self):
        now = time.time()
        qp = self.quest_points()
        abilities = {}
        for aid, ab in MAGIC_ABILITIES.items():
            need = int(ab.get("quest_points") or 0)
            unlocked = qp >= need
            ready_at = float(self.magic_ready_at.get(aid) or 0)
            cd_left = max(0.0, ready_at - now) if unlocked else 0.0
            abilities[aid] = {
                "unlocked": unlocked,
                "quest_points": need,
                "ready": unlocked and ready_at <= now,
                "ready_at": ready_at,
                "cooldown_left": round(cd_left, 2),
                "cooldown": float(ab.get("cooldown") or 8),
                "name": ab["name"],
                "desc": ab.get("desc") or "",
                "effect": ab.get("effect") or "lightning",
                "damage": int(ab.get("damage") or 0),
                "freeze": float(ab.get("freeze") or 0),
            }
        return {
            "auto": bool(self.magic_auto),
            "manual_cd_factor": MANUAL_MAGIC_CD_FACTOR,
            "abilities": abilities,
            "order": list(MAGIC_ABILITY_ORDER),
        }

    def owned_pets_public(self):
        out = []
        for pid in self.owned_pets:
            if pid not in PETS:
                continue
            pdef = PETS[pid]
            out.append({
                "pet_id": pid,
                "name": pdef["name"],
                "level": pdef["level"],
                "sprite": pdef["sprite"],
                "active": pid == self.pet_id,
            })
        # Stable order by pet level
        out.sort(key=lambda e: (e["level"], e["name"]))
        return out

    def pet_public(self):
        if not self.pet_id or self.pet_id not in PETS:
            return None
        if (self.pet_x, self.pet_y) == (self.x, self.y):
            _park_pet(self)
        pdef = PETS[self.pet_id]
        return {
            "owner_id": self.player_id,
            "pet_id": self.pet_id,
            "name": pdef["name"],
            "level": pdef["level"],
            "sprite": pdef["sprite"],
            "x": self.pet_x,
            "y": self.pet_y,
            "hp": self.pet_hp,
            "max_hp": pdef["hp"],
            "facing": getattr(self, "pet_facing", None) or "s",
        }

    def grant_pet(self, pet_id):
        """Add a pet to the collection if new. Returns True if newly owned."""
        if pet_id not in PETS:
            return False
        if pet_id in self.owned_pets:
            return False
        self.owned_pets.append(pet_id)
        WORLD.db.save_player_stats(self.player_id, owned_pets=json.dumps(self.owned_pets))
        return True

    def activate_pet(self, pet_id):
        if pet_id not in PETS:
            return False
        if pet_id not in self.owned_pets:
            self.owned_pets.append(pet_id)
            WORLD.db.save_player_stats(self.player_id, owned_pets=json.dumps(self.owned_pets))
        self.pet_id = pet_id
        self.pet_hp = PETS[pet_id]["hp"]
        self.pet_target_id = None
        _bring_pet(self)
        WORLD.db.save_player_stats(self.player_id, active_pet=pet_id)
        return True


class MonsterInstance:
    def __init__(self, inst_id, mtype, x, y, stats=None, no_respawn=False):
        self.id = inst_id
        self.type = mtype
        self.spawn_x = x
        self.spawn_y = y
        self.x = x
        self.y = y
        data = MONSTERS.get(mtype) or {}
        self.stats = stats  # optional override dict (dungeon scaling)
        self.max_hp = int((stats or data).get("hp", data.get("hp", 10)))
        self.hp = self.max_hp
        self.alive = True
        self.respawn_at_tick = 0
        self.target_player_id = None
        self.ticks_since_wander = 0
        self.no_respawn = no_respawn
        self.frozen_until = 0.0  # unix time — cannot attack while frozen
        self.next_attack_at = 0.0  # unix time — attack cooldown gate
        # Short multi-step patrol (castle knights / city guards)
        self.patrol_dx = 0
        self.patrol_dy = 0
        self.patrol_steps_left = 0
        # Dungeon monsters stay in spawn room; bosses may set confine_room=False.
        # A leash area (mountain wolves) is their home even when no dungeon room exists.
        area = data.get("leash_area")
        if area:
            self.home_room = tuple(area)
        elif stats or data.get("confine_room", True) is False:
            self.home_room = None
        else:
            self.home_room = room_containing(x, y)

    def is_frozen(self):
        return time.time() < float(self.frozen_until or 0)

    def attack_ready(self):
        return time.time() >= float(self.next_attack_at or 0)

    def mark_attacked(self, cooldown=None):
        """Start post-swing cooldown (dragon defaults to 1s flee window)."""
        mdef = self.def_stats() or {}
        if cooldown is None:
            cooldown = float(mdef.get("attack_cooldown") or 0.0)
        if cooldown > 0:
            self.next_attack_at = time.time() + cooldown

    def can_strike(self, px, py):
        """True if this monster may hit a target at (px, py) this tick."""
        if not self.alive or self.is_frozen() or not self.attack_ready():
            return False
        mdef = self.def_stats() or {}
        cones = mdef.get("cone_tiles")
        if cones:
            if not getattr(self, "_cone_strike", False):
                return False
            return (int(px), int(py)) in {(int(p[0]), int(p[1])) for p in cones}
        reach = max(1, int(mdef.get("attack_range") or 1))
        if mdef.get("side_by_side"):
            gap = abs(self.x - px)
            return self.y == py and 1 <= gap <= reach
        return chebyshev(self.x, self.y, px, py) <= reach

    def def_stats(self):
        # Dungeon scaling replaces hp and level. It must keep the type's
        # fight rules (side-by-side, reach, cooldown) or the client walks
        # to a gap the server then calls out of range.
        base = MONSTERS.get(self.type)
        if not self.stats:
            return base or {}
        if not base:
            return self.stats
        merged = dict(base)
        merged.update(self.stats)
        return merged

    def public_state(self):
        mdef = self.def_stats()
        name = mdef.get("name") or MONSTERS.get(self.type, {}).get("name", "Monster")
        frozen = self.is_frozen()
        state = {
            "id": self.id, "type": self.type, "name": name,
            "level": combat.monster_combat_level(mdef, self.type),
            "x": self.x, "y": self.y, "hp": self.hp, "max_hp": self.max_hp, "alive": self.alive,
            "frozen": frozen,
        }
        cones = (self.stats or {}).get("cone_tiles")
        if cones:
            state["cone_tiles"] = cones
        facing = (self.stats or {}).get("facing")
        if facing:
            state["facing"] = {"south": "s", "north": "n", "east": "e", "west": "w"}.get(facing, facing)
        return state


# ---------------------------------------------------------------------------
# World / server state
# ---------------------------------------------------------------------------
class World:
    def __init__(self):
        self.db = Database()
        self.grid = generate_world()
        import housing
        housing.bind(self)
        import castle_owners
        castle_owners.bind(self)
        explore_dungeons.capture_and_hide(self.grid)
        stamp_volcano_mine(self.grid)
        stamp_outfitters_shell(self.grid)
        # After roads — cone WALL must not be punched by the y=73 city cut.
        stamp_emberdeep_mouth(self.grid)
        self.resource_nodes = build_resource_nodes(self.grid)
        # One-time save fix for the castle move / harbour seal / Fairy Glade.
        try:
            import position_migrations
            from database import DB_PATH as _DBP
            from world_map import WALKABLE_TILES as _WT
            position_migrations.run_once(
                self.db.conn, self.grid, _WT, SPAWN_POINT,
                db_path=getattr(self.db, "path", None) or _DBP, log=log.info,
            )
        except Exception:
            log.exception("castle-move position migration failed; positions left as saved")
        for _pos, _node in self.resource_nodes.items():
            if fishing_spots.is_spot(_node, RESOURCE_YIELDS.get(_node["type"])):
                fishing_spots.init_spot(_node, _pos, RESOURCE_YIELDS.get(_node["type"]))
        self.moving_fish_spots = []      # spots between tiles (server only)
        self.monsters = {}
        for mtype, x, y in MONSTER_SPAWNS:
            camp = mtype in ("giant_rat", "wolf") and near_volcano_mine(x, y)
            if explore_dungeons.contains_region(x, y) and not camp:
                continue
            mid = next_id()
            monster = MonsterInstance(mid, mtype, x, y)
            if mtype == "giant_rat" and camp:
                monster.home_room = VOLCANO_RAT_LEASH
            elif mtype == "wolf" and camp:
                monster.home_room = VOLCANO_WOLF_LEASH
            self.monsters[mid] = monster
        self.sessions = {}     # player_id -> PlayerSession
        self.ground_items = {}  # (x, y) -> [{"item_id","qty"}]
        # Quest prop — Lira's Lost Locket near the wishing well
        self.ground_items[(29, 22)] = [{"item_id": "lost_locket", "qty": 1}]
        self.fires = {}         # (x, y) -> expire_tick
        self.tick_count = 0

    def near_fire(self, session):
        for (fx, fy) in self.fires:
            if adjacent_or_same(session.x, session.y, fx, fy):
                return True
        return False

    def near_cook_spot(self, session):
        for spot in INTERACTABLES:
            if spot["kind"] in ("range", "fireplace") and adjacent_or_same(
                session.x, session.y, spot["x"], spot["y"]
            ):
                return True
        return self.near_fire(session)

    # -- helpers --------------------------------------------------------
    def find_session_by_ws(self, ws):
        for s in self.sessions.values():
            if s.ws == ws:
                return s
        return None

    def occupied(self, x, y, exclude_player=None):
        for s in self.sessions.values():
            if getattr(s, "dungeon", None):
                continue
            if s.x == x and s.y == y and s.player_id != exclude_player:
                return True
        return False

    def add_item_to_inventory(self, session, item_id, qty):
        """Returns True if it fit, False if inventory is full.

        Stackables merge into any existing stack. New stacks prefer the
        skill tab that matches the item. The Bags tab is reserved for
        storage containers only.
        """
        item_def = ITEMS[item_id]
        if item_def.get("stackable"):
            for slot, entry in session.inventory.items():
                if entry["item_id"] == item_id:
                    entry["qty"] += qty
                    self.db.add_item_to_slot(session.player_id, slot, item_id, entry["qty"])
                    return True
        bags_tab = 3
        prefer = inventory_tab_for_item(item_id)
        if is_storage_bag(item_id):
            tab_order = [bags_tab] + [t for t in range(len(INVENTORY_TABS)) if t != bags_tab]
        else:
            # Never auto-place non-bags into the Bags tab
            tab_order = [prefer] + [
                t for t in range(len(INVENTORY_TABS)) if t != prefer and t != bags_tab
            ]
        for tab in tab_order:
            base = tab * INVENTORY_TAB_SIZE
            for local in range(INVENTORY_TAB_SIZE):
                slot = base + local
                if slot not in session.inventory:
                    session.inventory[slot] = {"item_id": item_id, "qty": qty}
                    self.db.add_item_to_slot(session.player_id, slot, item_id, qty)
                    return True
        return False

    def rearrange_bags_tab(self, session):
        """Move storage bags into the Bags tab; kick non-bags out of it."""
        bags_tab = 3
        base = bags_tab * INVENTORY_TAB_SIZE
        bags_slots = range(base, base + INVENTORY_TAB_SIZE)

        def free_slot_outside_bags():
            for tab in range(len(INVENTORY_TABS)):
                if tab == bags_tab:
                    continue
                b = tab * INVENTORY_TAB_SIZE
                for local in range(INVENTORY_TAB_SIZE):
                    slot = b + local
                    if slot not in session.inventory:
                        return slot
            return None

        def free_bags_slot():
            for slot in bags_slots:
                if slot not in session.inventory:
                    return slot
            return None

        # 1) Evict non-bags from Bags tab
        for slot in list(bags_slots):
            entry = session.inventory.get(slot)
            if not entry or is_storage_bag(entry.get("item_id")):
                continue
            dest = free_slot_outside_bags()
            if dest is None:
                break
            session.inventory[dest] = entry
            del session.inventory[slot]
            self.db.clear_slot(session.player_id, slot)
            self.db.add_item_to_slot(session.player_id, dest, entry["item_id"], entry["qty"])

        # 2) Pull bags from other tabs into Bags
        for slot in list(session.inventory.keys()):
            if slot in bags_slots:
                continue
            entry = session.inventory.get(slot)
            if not entry or not is_storage_bag(entry.get("item_id")):
                continue
            dest = free_bags_slot()
            if dest is None:
                break
            session.inventory[dest] = entry
            del session.inventory[slot]
            self.db.clear_slot(session.player_id, slot)
            self.db.add_item_to_slot(session.player_id, dest, entry["item_id"], entry["qty"])

    def remove_item_qty(self, session, item_id, qty):
        remaining = qty
        for slot in list(session.inventory.keys()):
            entry = session.inventory[slot]
            if entry["item_id"] != item_id:
                continue
            take = min(entry["qty"], remaining)
            entry["qty"] -= take
            remaining -= take
            if entry["qty"] <= 0:
                del session.inventory[slot]
                self.db.clear_slot(session.player_id, slot)
            else:
                self.db.add_item_to_slot(session.player_id, slot, item_id, entry["qty"])
            if remaining <= 0:
                break
        return remaining == 0

    def count_item(self, session, item_id):
        return sum(e["qty"] for e in session.inventory.values() if e["item_id"] == item_id)

    def gather_tool_id(self, session, skill, allowed_tools=None):
        """The tool item in use: the one in the tool slot, if it fits this skill / spot."""
        def ok(item_id):
            if not item_id:
                return False
            if allowed_tools:
                return item_id in allowed_tools
            return ITEMS.get(item_id, {}).get("tool_for") == skill

        tool = session.equipment.get("tool")
        return tool if ok(tool) else None

    def has_gather_tool(self, session, skill, allowed_tools=None):
        """True if the equipped tool (tool slot) is a valid gather tool.

        If allowed_tools is a list of item ids, one of those must be present.
        Otherwise any item with tool_for == skill counts.
        """
        def ok(item_id):
            if not item_id:
                return False
            if allowed_tools:
                return item_id in allowed_tools
            return ITEMS.get(item_id, {}).get("tool_for") == skill

        return ok(session.equipment.get("tool"))

    def count_item_bank(self, session, item_id):
        return sum(e["qty"] for e in session.bank.values() if e["item_id"] == item_id)

    def ensure_tinderbox(self, session):
        """Existing characters predating firemaking get a free tinderbox once."""
        if self.count_item(session, "tinderbox") > 0 or self.count_item_bank(session, "tinderbox") > 0:
            return False
        return self.add_item_to_inventory(session, "tinderbox", 1)

    def count_ores(self, session):
        total = sum(
            e["qty"] for e in session.inventory.values() if e["item_id"] in ORE_ITEM_IDS
        )
        if session.has_mining_bag():
            total += sum(
                int(q or 0) for iid, q in session.mining_bag.items() if iid in ORE_ITEM_IDS
            )
        return total

    def add_coins(self, session, qty):
        """Add to purse, clamped at MAX_PURSE_COINS. Returns (gained, leftover)."""
        if qty <= 0:
            return 0, 0
        room = max(0, MAX_PURSE_COINS - session.coins)
        take = min(qty, room)
        session.coins += take
        self.db.save_player_stats(session.player_id, coins=session.coins)
        return take, qty - take

    def near_bank(self, session):
        for spot in INTERACTABLES:
            if spot.get("kind") == "bank" and adjacent_or_same(session.x, session.y, spot["x"], spot["y"]):
                return True
        for n in NPCS:
            if n.get("bank") and adjacent_or_same(session.x, session.y, n["x"], n["y"]):
                return True
        return False

    def grant_xp(self, session, skill, amount):
        # Hitpoints and firemaking are not experience skills.
        if skill in ("hitpoints", "firemaking") or skill not in session.xp:
            return session.level(skill) if skill in session.xp else 1, session.level(skill) if skill in session.xp else 1
        before_pool = session.max_hp() if skill in ("attack", "strength", "defence", "archery") else None
        before = session.level(skill)
        session.xp[skill] += amount
        after = session.level(skill)
        if before_pool is not None:
            gained = session.max_hp() - before_pool
            if gained > 0:
                session.hp += gained
        self.db.save_player_stats(session.player_id, **{f"{skill}_xp": session.xp[skill]})
        return before, after

    def drop_loot(self, x, y, drops):
        dropped = []
        for item_id, chance, (lo, hi) in drops:
            if random.random() > chance:
                continue
            # Tuple/list = pick one random item from the pool (e.g. 1/10 gear table)
            if isinstance(item_id, (list, tuple)):
                item_id = random.choice(item_id)
            qty = random.randint(lo, hi)
            dropped.append(_ground_drop(item_id, qty))
        if dropped:
            self.ground_items.setdefault((x, y), []).extend(dropped)
        return dropped


WORLD = World()


def _ground_drop(item_id, qty):
    entry = {"item_id": item_id, "qty": qty}
    if feature_flags.USE_REALISTIC_ITEM_ICONS:
        entry["expires_at"] = time.time() + 300
    return entry


def expire_ground_items(now=None):
    """Remove player and monster drops that have sat for 5 minutes."""
    if not feature_flags.USE_REALISTIC_ITEM_ICONS:
        return
    now = time.time() if now is None else now

    def _expire(piles):
        if not isinstance(piles, dict):
            return
        for key, pile in list(piles.items()):
            kept = [entry for entry in pile if not entry.get("expires_at") or entry["expires_at"] > now]
            if kept:
                piles[key] = kept
            else:
                piles.pop(key, None)

    _expire(WORLD.ground_items)
    for session in list(WORLD.sessions.values()):
        dungeon = getattr(session, "dungeon", None) or {}
        _expire(dungeon.get("ground"))


# ---------------------------------------------------------------------------
# Networking helpers
# ---------------------------------------------------------------------------
async def send(ws, msg_type, **fields):
    try:
        await ws.send(json.dumps({"type": msg_type, **fields}))
    except websockets.exceptions.ConnectionClosed:
        pass


async def broadcast(msg_type, **fields):
    if not WORLD.sessions:
        return
    payload = json.dumps({"type": msg_type, **fields})
    await asyncio.gather(*[
        s.ws.send(payload) for s in WORLD.sessions.values()
    ], return_exceptions=True)


async def broadcast_player_state(session):
    """A changed look reaches everyone on the next world-state tick (public_state carries appearance).
    Called by the appearance handlers; this was referenced but never defined, so they raised NameError
    after saving."""
    return None


def quest_status_for(session, quest_id):
    info = dict(session.quests.get(quest_id, {"status": "not_started", "progress": 0}))
    if quest_id == "fairy_oath":
        import fairy_village
        info["objective"] = fairy_village.objective_text(session)
    return info


def npc_quest_ids(npc):
    """Ordered quest list for an NPC (`quest_ids` preferred, else legacy `quest_id`)."""
    ids = list(npc.get("quest_ids") or [])
    legacy = npc.get("quest_id")
    if legacy and legacy not in ids:
        ids.insert(0, legacy)
    return ids


def quest_prereqs_met(session, qdef):
    req = qdef.get("requires")
    if not req:
        return True
    needed = req if isinstance(req, (list, tuple)) else [req]
    for qid in needed:
        prog = session.quests.get(qid)
        if not prog or prog.get("status") != "complete":
            return False
    return True


def pick_npc_quest(session, npc):
    """First incomplete quest this NPC offers (respecting `requires` chains)."""
    last = (None, None, None)
    for qid in npc_quest_ids(npc):
        qdef = QUESTS.get(qid)
        if not qdef:
            continue
        if not quest_prereqs_met(session, qdef):
            continue
        prog = session.quests.get(qid)
        last = (qid, qdef, prog)
        if prog is None or prog.get("status") != "complete":
            return qid, qdef, prog
    return last


def reward_inv_slots_needed(session, rewards):
    """Free inventory slots required to receive item rewards (stack-aware)."""
    if not rewards:
        return 0
    need = 0
    entries = []
    if "item" in rewards:
        entries.append(rewards["item"])
    if "items" in rewards:
        entries.extend(rewards["items"])
    for iid, _qty in entries:
        item = ITEMS.get(iid) or {}
        if item.get("stackable") and WORLD.count_item(session, iid) > 0:
            continue
        need += 1
    return need


def quest_collect_met(session, qdef):
    """True if the player currently holds everything a collect quest needs."""
    if qdef["type"] == "collect":
        return session.available_craft_input(qdef["target"]) >= qdef["count"]
    if qdef["type"] == "collect_multi":
        return all(
            session.available_craft_input(iid) >= need
            for iid, need in qdef["targets"].items()
        )
    return False


def refresh_collect_quest_status(session):
    """Flip collect quests between active/ready based on inventory. Returns True if changed."""
    changed = False
    for qid, qdef in QUESTS.items():
        if qdef["type"] not in ("collect", "collect_multi"):
            continue
        prog = session.quests.get(qid)
        if not prog or prog.get("status") not in ("active", "ready"):
            continue
        met = quest_collect_met(session, qdef)
        if met and prog["status"] == "active":
            prog["status"] = "ready"
            WORLD.db.set_quest_progress(session.player_id, qid, "ready", prog.get("progress", 0))
            changed = True
        elif not met and prog["status"] == "ready":
            prog["status"] = "active"
            WORLD.db.set_quest_progress(session.player_id, qid, "active", prog.get("progress", 0))
            changed = True
    return changed


def quest_objective_line(session, qdef, prog):
    """Human-readable progress line for dialogue / journal."""
    status = (prog or {}).get("status", "not_started")
    progress = int((prog or {}).get("progress") or 0)
    if qdef["type"] == "kill":
        name = (MONSTERS.get(qdef["target"]) or {}).get("name") or qdef["target"].replace("_", " ").title()
        need = int(qdef["count"])
        cur = min(progress, need) if status != "complete" else need
        if status == "ready":
            cur = need
        return f"{cur}/{need} {name}{'s' if need != 1 and not name.endswith('s') else ''}"
    if qdef["type"] == "collect":
        iid = qdef["target"]
        name = (ITEMS.get(iid) or {}).get("name", iid)
        need = int(qdef["count"])
        have = session.available_craft_input(iid) if session is not None else 0
        return f"{min(have, need)}/{need} {name}"
    if qdef["type"] == "collect_multi":
        parts = []
        for iid, need in qdef["targets"].items():
            name = (ITEMS.get(iid) or {}).get("name", iid)
            have = session.available_craft_input(iid) if session is not None else 0
            parts.append(f"{min(have, need)}/{need} {name}")
        return " · ".join(parts)
    if qdef["type"] == "guild":
        if status in ("ready", "complete"):
            return "Return to Guildmaster Ysolde" if status == "ready" else "Done"
        return " · ".join([("✓ " if progress & 1 else "") + "Create or join a guild",
                           ("✓ " if progress & 2 else "") + "/guild deposit any amount"])
    if qdef["type"] == "find_npc":
        npc = NPC_BY_ID.get(qdef["target"]) or {}
        name = npc.get("name") or qdef["target"].replace("_", " ").title()
        if status in ("ready", "complete"):
            return f"Spoke with {name}"
        return f"Find and speak to {name}"
    if qdef["type"] == "gift":
        return "Talk to receive your reward"
    if qdef["type"] == "oath":
        import fairy_village
        return fairy_village.objective_text(session)
    return qdef.get("description", "")


def _bounty_hook(session, monster_type):
    """Event hook only: a royal bounty pays the first killer's bank."""
    try:
        paid = ruling.claim_bounty(WORLD.db.conn, monster_type, session.player_id)
    except Exception:
        log.exception("bounty hook failed")
        return
    if paid:
        politics.note_bounty_paid(WORLD.db.conn)
        session.bank_coins = apprentice.bank_get(WORLD.db.conn, session.player_id)
        name = (MONSTERS.get(monster_type) or {}).get("name", monster_type)
        asyncio.ensure_future(broadcast("CHAT_MSG", **{"from": "Royal Marshal",
                              "text": f"{session.char_name} claims the royal bounty on a {name}: {paid:,} coins!"}))


def check_quest_progress_on_kill(session, monster_type):
    _bounty_hook(session, monster_type)
    changed = False
    for qid, qdef in QUESTS.items():
        if qdef["type"] != "kill" or qdef["target"] != monster_type:
            continue
        prog = session.quests.get(qid)
        if prog and prog["status"] == "active":
            prog["progress"] += 1
            if prog["progress"] >= qdef["count"]:
                prog["status"] = "ready"
            WORLD.db.set_quest_progress(session.player_id, qid, prog["status"], prog["progress"])
            changed = True
    if changed:
        session.quest_log_dirty = True
    return changed


def check_quest_progress_on_talk(session, npc_id):
    changed = False
    for qid, qdef in QUESTS.items():
        if qdef["type"] != "find_npc" or qdef["target"] != npc_id:
            continue
        prog = session.quests.get(qid)
        if prog and prog["status"] == "active":
            prog["status"] = "ready"
            WORLD.db.set_quest_progress(session.player_id, qid, "ready", prog["progress"])
            changed = True
    if changed:
        session.quest_log_dirty = True
    return changed


async def flush_quest_logs():
    """Push QUEST_LOG to any session whose quest progress changed this tick."""
    for session in list(WORLD.sessions.values()):
        if refresh_collect_quest_status(session):
            session.quest_log_dirty = True
        if not getattr(session, "quest_log_dirty", False):
            continue
        session.quest_log_dirty = False
        quests = {qid: quest_status_for(session, qid) for qid in QUESTS}
        await send(session.ws, "QUEST_LOG", quests=quests)
        # A brand-new player accepting their first quest ends the arrival guide's
        # stage-2 trail (to Elder Miriam) — tell the client the quest is underway.
        if getattr(session, "arrival_guide", False):
            session.arrival_guide = False
            st = _welcome_status(session)
            st["claimed"] = True
            st["show_path"] = True
            await send_welcome_state(session, st)


# ---------------------------------------------------------------------------
# Message handlers
# ---------------------------------------------------------------------------
async def handle_login(ws, msg, is_register):
    username = (msg.get("username") or "").strip()
    password = msg.get("password") or ""
    if not username or not password:
        await send(ws, "LOGIN_FAIL", reason="Username and password required.")
        return
    if is_register:
        # Reject unusable usernames before anything is written. The client
        # checks this too, but the server is the one that can be talked to
        # directly. Length bounds also stop a blank or a single character
        # username becoming an account nobody can identify.
        if len(username) < 3 or len(username) > 20 or not username.isascii():
            await send(ws, "LOGIN_FAIL", reason="Usernames need 3-20 letters or numbers.")
            return
        # "   " is truthy, so `msg.get("char_name") or username` passed it
        # straight through and strip() then saved an empty name. Fall back to
        # the username *after* stripping, and refuse a name with no letters.
        char_name = str(msg.get("char_name") or "").strip()[:16] or username[:16]
        if not any(ch.isalnum() for ch in char_name):
            await send(ws, "LOGIN_FAIL", reason="Pick a character name with letters or numbers.")
            return
        gender = msg.get("gender") or "male"
        if WORLD.db.get_player_by_username(username):
            await send(ws, "LOGIN_FAIL", reason="That username is already taken.")
            return
        row = WORLD.db.create_account(username, password, char_name, gender=gender)
    else:
        row = WORLD.db.verify_login(username, password)
        if row is None:
            await send(ws, "LOGIN_FAIL", reason="Invalid username or password.")
            return
    if row["id"] in WORLD.sessions:
        ghost = WORLD.sessions[row["id"]]
        if getattr(ghost, "linger_until", None) is not None:
            await send(ws, "LOGIN_FAIL", reason="Your character is still in a fight. Try again in a few seconds.")
        else:
            await send(ws, "LOGIN_FAIL", reason="That character is already logged in.")
        return

    session = PlayerSession(ws, row)
    resume = _read_dungeon_resume(row)
    # Clamp / reset position if the world layout changed since last save.
    if not is_walkable(WORLD.grid, session.x, session.y):
        session.x, session.y = SPAWN_POINT
        WORLD.db.save_player_position(session.player_id, session.x, session.y)
    session.inventory = WORLD.db.get_inventory(row["id"])
    session.bank = WORLD.db.get_bank(row["id"])
    session.quests = WORLD.db.get_quest_progress(row["id"])
    WORLD.sessions[session.player_id] = session
    migrate_removed_daggers(session)
    enforce_bound_items(session)
    import void_v2
    # Keys stay in the bag when the visit itself is still going.
    if not resume:
        void_v2.strip_keys(session)
    WORLD.rearrange_bags_tab(session)
    # Persist owned-pets list (includes migrated active_pet)
    WORLD.db.save_player_stats(session.player_id, owned_pets=json.dumps(session.owned_pets))
    if getattr(session, "_teleport_marks_dirty", False):
        _save_teleport_marks(session)
        session._teleport_marks_dirty = False
    _discover_teleport_marks(session)
    if WORLD.ensure_tinderbox(session):
        log.info("%s received a starter tinderbox", session.char_name)

    trade_in = _outfits_migrate_v2(session)
    needs_alloc = not session.stats_allocated
    await send(ws, "LOGIN_OK", player=session.full_state(), needs_stat_alloc=needs_alloc)
    if trade_in:
        await send(ws, "CHAT_MSG", **{"from": "Mae", "text": trade_in})
    if needs_alloc:
        await send(
            ws, "STAT_ALLOC_REQUIRED",
            points=10,
            skills=["attack", "strength", "defence", "archery"],
            base_levels={"attack": 5, "strength": 5, "defence": 5, "archery": 1},
        )
        log.info("%s logged in as %s (id=%s) — awaiting stat allocation", username, session.char_name, session.player_id)
        return

    await send_world_join(session)
    if resume:
        await _resume_dungeon(session, resume)
    log.info("%s logged in as %s (id=%s)", username, session.char_name, session.player_id)


async def send_world_join(session):
    import world_clock
    await send(
        session.ws, "WORLD_STATE",
        width=WIDTH, height=HEIGHT, tiles=WORLD.grid,
        npcs=[n for n in NPCS if not n.get("plane")],
        resources={f"{x},{y}": n["type"] for (x, y), n in WORLD.resource_nodes.items() if not n["depleted"]},
        interactables=INTERACTABLES,
        craft_recipes=CRAFT_RECIPES,
        buildings=BUILDINGS,
        env=world_clock.snapshot(),
    )
    quest_log = {qid: quest_status_for(session, qid) for qid in QUESTS}
    await send(session.ws, "QUEST_LOG", quests=quest_log)
    await send(session.ws, "PLAYER_UPDATE", player=session.full_state())
    import clans
    await clans.on_login(session)
    await send_starter_tips(session)
    await welcome_on_join(session)
    await settle_work(session, login=True)
    if feature_flags.USE_PLAYER_HOUSING:
        await _housing.on_login(session)
        import castle_owners
        await castle_owners.on_login(session)


async def send_starter_tips(session):
    """Short first-session pointers — H for the full help list.

    Only for a character who has never played before. This used to run on
    every login, so a returning player was re-tutored each session and the
    five lines drowned whatever they had actually logged in to read.
    """
    if getattr(session, "_starter_tips_sent", False):
        return
    session._starter_tips_sent = True
    try:
        seen = WORLD.db.get_player_by_id(session.player_id)["starter_tips_seen"]
    except (KeyError, IndexError, TypeError):
        seen = 0
    if seen:
        return
    WORLD.db.save_player_stats(session.player_id, starter_tips_seen=1)
    # One instruction, then play.
    #
    # This used to dump five dense lines naming six NPCs, four keybinds, the
    # bank limits and the purse cap before the player had taken a single step.
    # Onboarding guidance is blunt about this: players act on one clear next
    # step, not on a wall of reference text. Everything else is still there —
    # it arrives when it is relevant, and H always lists the lot.
    await send(session.ws, "CHAT_MSG", **{
        "from": "Guide",
        "text": "Follow the golden trail to Warden Tamsin — she has your starting kit. (H = all controls.)",
    })


async def handle_allocate_stats(session, msg):
    if session.stats_allocated:
        await send(session.ws, "ERROR", message="You already chose your starting stats.")
        return
    allowed = ("attack", "strength", "defence", "archery")
    raw = msg.get("stats") or {}
    try:
        alloc = {s: max(0, int(raw.get(s, 0))) for s in allowed}
    except (TypeError, ValueError):
        await send(session.ws, "ERROR", message="Invalid stat allocation.")
        return
    if sum(alloc.values()) != 10:
        await send(session.ws, "ERROR", message="You must spend exactly 10 stat points.")
        return
    base = {"attack": 5, "strength": 5, "defence": 5, "archery": 1}
    xp_fields = {}
    for skill, pts in alloc.items():
        new_level = base[skill] + pts
        if new_level > 40:
            await send(session.ws, "ERROR", message="Stat level too high.")
            return
        xp = combat.xp_for_level(new_level)
        session.xp[skill] = xp
        xp_fields[f"{skill}_xp"] = xp
    session.hp = session.max_hp()
    xp_fields["hp"] = session.hp
    xp_fields["stats_allocated"] = 1
    gender = "female" if str(msg.get("gender") or "male").lower() == "female" else "male"
    session.gender = gender
    xp_fields["gender"] = gender
    WORLD.db.save_player_stats(session.player_id, **xp_fields)
    session.stats_allocated = True
    await send(session.ws, "CHAT_MSG", **{
        "from": "World",
        "text": "Your starting stats are set. Welcome to Crownfall!",
    })
    await send_world_join(session)
    log.info("%s allocated starting stats %s", session.username, alloc)


# Item id -> Session attribute holding what a packed bag is currently carrying.
BAG_CONTENTS_ATTR = {
    "arrow_quiver": "quiver", "arrowtip_box": "tip_box",
    "food_bag": "food_bag", "raw_food_bag": "raw_bag",
    "mining_bag": "mining_bag", "log_bag": "log_bag",
    "fletch_pouch": "fletch_pouch", "potion_pouch": "potion_pouch",
    "gem_bag": "gem_bag",
}


def item_is_sellable(item_id):
    item = ITEMS.get(item_id) or {}
    return item.get("sellable", True) and item.get("tradeable", True)


def owns_unique_item(session, item_id):
    """True when this character already owns a one-per-account container (bag, pouch or quiver).

    Counts every place an owned bag can be: worn, in the pack, in the bank, or
    holding its items. Bags are bought once and can never be sold, so a second
    copy could only ever be dead weight.
    """
    item = ITEMS.get(item_id) or {}
    if not item.get("unique"):
        return False
    if (session.equipment or {}).get(item.get("equip_slot")) == item_id:
        return True
    if WORLD.count_item(session, item_id) > 0 or WORLD.count_item_bank(session, item_id) > 0:
        return True
    # Last resort: merged contents. Bags normally keep their item, but an empty
    # stored bag is still indistinguishable from "never owned", so this must
    # stay tighter than the has_* helpers or an empty packed bag could be re-bought.
    attr = BAG_CONTENTS_ATTR.get(item_id)
    contents = getattr(session, attr, None) if attr else None
    if isinstance(contents, dict):
        return any(int(q or 0) > 0 for q in contents.values())
    return False


def shop_will_buy(shop, item_id):
    """True if this shop accepts the item when the player sells."""
    if not shop or not shop.get("buys"):
        return False
    if not item_is_sellable(item_id):
        return False
    item = ITEMS.get(item_id) or {}
    buy_types = shop.get("buys_types")
    buy_slots = shop.get("buys_slots")
    if not buy_types and not buy_slots:
        return True  # unrestricted buyer
    ok = False
    if buy_types and item.get("type") in buy_types:
        ok = True
    if buy_slots and item.get("equip_slot") in buy_slots:
        ok = True
    return ok


def item_is_tradeable(item_id):
    item = ITEMS.get(item_id) or {}
    return item.get("tradeable", True)


def item_is_bankable(item_id):
    """Medals stay unsellable, but they can sit in the bank.

    One-per-character containers can't: their ownership is checked by reading
    the bag itself, so banking the empty item would let a second be bought.
    """
    item = ITEMS.get(item_id) or {}
    if item.get("unique"):
        return False
    if item.get("dungeon_bound"):
        return False
    if "bankable" in item:
        return bool(item["bankable"])
    return item.get("tradeable", True)


def pickup_ignored(session, item_id):
    if item_id == "coins" or (ITEMS.get(item_id) or {}).get("karma_xp"):
        return False
    return item_id in session.pickup_ignore


def session_has_item(session, item_id):
    if item_id in (session.equipment or {}).values():
        return True
    return any(e.get("item_id") == item_id for e in session.inventory.values())


def migrate_removed_daggers(session):
    """Daggers were removed: swap any saved dagger for the same-tier sword and persist."""
    from item_migrations import migrate_daggers
    inv, bank, eq = migrate_daggers(session.inventory, session.bank, session.equipment)
    for slot in inv:
        e = session.inventory[slot]
        WORLD.db.add_item_to_slot(session.player_id, slot, e["item_id"], e["qty"])
    for slot in bank:
        e = session.bank[slot]
        WORLD.db.set_bank_slot(session.player_id, slot, e["item_id"], e["qty"])
    for slot in eq:
        WORLD.db.set_equipment(session.player_id, slot, session.equipment[slot])
    if inv or bank or eq:
        log.info("Replaced daggers with swords for %s (inv %d, bank %d, equipped %d)",
                 session.username, len(inv), len(bank), len(eq))


def enforce_bound_items(session):
    """Grant bound uniques to their owner; strip them from anyone else."""
    for item_id, item in ITEMS.items():
        owner = (item.get("bound_username") or "").lower()
        if not owner:
            continue
        mine = session.username.lower() == owner
        has = session_has_item(session, item_id)
        if mine and not has:
            # Prefer matching equip slot if empty, else inventory
            eq_slot = item.get("equip_slot")
            prefer_inv = bool(item.get("bound_to_inventory"))
            if (not prefer_inv) and eq_slot and not session.equipment.get(eq_slot):
                session.equipment[eq_slot] = item_id
                WORLD.db.set_equipment(session.player_id, eq_slot, item_id)
                log.info("Granted bound item %s to %s (equipped %s)", item_id, session.username, eq_slot)
            elif not WORLD.add_item_to_inventory(session, item_id, 1):
                log.warning("Could not grant bound item %s to %s (inventory full)", item_id, session.username)
            else:
                log.info("Granted bound item %s to %s", item_id, session.username)
        elif not mine and has:
            # Strip illicit copies
            for slot, entry in list(session.inventory.items()):
                if entry.get("item_id") == item_id:
                    WORLD.remove_item_qty(session, item_id, entry["qty"])
            for slot_name, eid in list(session.equipment.items()):
                if eid == item_id:
                    session.equipment[slot_name] = None
                    WORLD.db.set_equipment(session.player_id, slot_name, None)
            log.info("Stripped bound item %s from %s", item_id, session.username)


async def handle_leaderboard(ws, msg):
    limit = max(1, min(50, int(msg.get("limit", 50))))
    boards = WORLD.db.get_leaderboards(limit=limit)
    # Total overall first, then individual skills
    skills = ["total"] + [s for s in XP_SKILLS if s in boards]
    await send(ws, "LEADERBOARD", skills=skills, boards=boards)


async def _send_stair_prompt(session):
    import castle_realm
    plane = session.dungeon.get("plane")
    await send(session.ws, "STAIR_PROMPT", tiles=castle_realm.stair_tiles(plane))


async def handle_stair(session, msg):
    """Climb the one spiral staircase after the player chooses up or down."""
    if not session.dungeon or session.dungeon.get("id") != "castle_realm":
        return
    if not feature_flags.USE_CASTLE_INTERIORS_V2:
        return
    import castle_realm
    plane = session.dungeon.get("plane")
    if not castle_realm.near_stair(plane, session.x, session.y, 1):
        await send(session.ws, "CHAT_MSG", **{"from": "Castle", "text": "Step closer to the stairs."})
        return
    direction = msg.get("dir")
    if direction not in ("up", "down"):
        await _send_stair_prompt(session)
        return
    stair = castle_realm.stair_going(plane, direction)
    if stair is None:
        text = "You are on the top floor." if direction == "up" else "You are on the ground floor."
        await send(session.ws, "CHAT_MSG", **{"from": "Castle", "text": text})
        return
    castle_realm.move_to_plane(session, stair["to_plane"], stair["arrive"])
    _bring_pet(session)
    await send(session.ws, "REALM_PLANE", **castle_realm.payload(session))
    import castle_owners
    await castle_owners.send_state(session)
    level = session.dungeon.get("floor") or 1
    total = session.dungeon.get("floors") or 1
    title = session.dungeon.get("name") or "the next floor"
    way = "up" if direction == "up" else "down"
    await send(session.ws, "CHAT_MSG", **{
        "from": "Castle",
        "text": f"You climb {way} to floor {level} of {total}: {title}.",
    })
    await send(session.ws, "PLAYER_UPDATE", player=session.full_state())


COMBAT_LOCK_ROUNDS = 5


def _combat_rounds(session):
    return int(getattr(session, "combat_rounds", 0) or 0)


def _fight_holds_you(session, monster=None):
    """Five-round lock applies to other players and the Adamant Duelist only."""
    if not session.in_combat_with:
        return False
    kind = session.in_combat_with[0]
    if kind == "player":
        return True
    if kind != "monster":
        return False
    if monster is None:
        mid = session.in_combat_with[1]
        if session.dungeon:
            monster = session.dungeon["monsters"].get(mid)
        else:
            monster = WORLD.monsters.get(mid)
    if monster is None:
        return False
    return bool((monster.def_stats() or {}).get("requires_pk"))


def _combat_locked(session):
    """True after a player or duelist fight has started, until five rounds pass."""
    if not _fight_holds_you(session):
        return False
    rounds = _combat_rounds(session)
    return 0 < rounds < COMBAT_LOCK_ROUNDS


async def handle_move(session, msg):
    """Apply one step. If the tile is refused, tell the client so it can undo a predicted step."""
    origin = (session.x, session.y)
    await _handle_move_body(session, msg)
    if (session.x, session.y) == origin:
        await send(session.ws, "MOVE_DENIED", x=session.x, y=session.y)


async def _handle_move_body(session, msg):
    if getattr(session, "rooted_until", 0) > WORLD.tick_count:
        return
    if _combat_locked(session):
        left = COMBAT_LOCK_ROUNDS - _combat_rounds(session)
        await send(
            session.ws, "ERROR",
            message=f"You cannot run yet. {left} round{'s' if left != 1 else ''} of fighting left.",
        )
        return
    dx, dy = msg.get("dx", 0), msg.get("dy", 0)
    if abs(dx) + abs(dy) != 1:
        return
    nx, ny = session.x + dx, session.y + dy
    if session.dungeon and session.dungeon.get("id") == "castle_realm":
        import castle_realm
        if not castle_realm.walkable(session.dungeon.get("plane"), nx, ny):
            return
        session.x, session.y = nx, ny
        session.gathering_node = None
        _release_monster_fight_on_step(session)
        step = castle_realm.transition_at(session.dungeon.get("plane"), session.x, session.y)
        if step and step.get("to_plane") == "overworld":
            await handle_leave_dungeon(session)
            return
        kind = str((step or {}).get("kind") or "")
        if step and kind.startswith("stair_") and feature_flags.USE_CASTLE_INTERIORS_V2:
            _pet_keep_up(session, dx, dy)
            await send(session.ws, "PLAYER_UPDATE", player=session.full_state())
            await _send_stair_prompt(session)
            return
        if step:
            castle_realm.move_to_plane(session, step["to_plane"], step["arrive"])
            _bring_pet(session)
            await send(session.ws, "REALM_PLANE", **castle_realm.payload(session))
            import castle_owners
            await castle_owners.send_state(session)
        else:
            _pet_keep_up(session, dx, dy)
        await send(session.ws, "PLAYER_UPDATE", player=session.full_state())
        await _notify_teleport_marks(session, _discover_teleport_marks(session))
        return
    if session.dungeon:
        if session.dungeon.get("v2"):
            import depths_v2
            import void_v2
            door_mod = depths_v2 if session.dungeon.get("v2") == "depths" else void_v2
            stepped = await door_mod.try_blocked_step(session, nx, ny)
            if stepped == "blocked":
                return
        mod = _dungeon_mod(session)
        if not mod or not mod.dungeon_walkable(session.dungeon["tiles"], nx, ny):
            return
        session.x, session.y = nx, ny
        session.gathering_node = None
        _release_monster_fight_on_step(session)
        # Tidehollow: seal the active chamber behind the player once they step
        # inside, and keep further chambers locked until each one is cleared.
        if (
            session.dungeon.get("id") == "tidehollow"
            and session.dungeon.get("rooms")
            and hasattr(mod, "apply_seals")
        ):
            await _refresh_tidehollow_seals(session)
        ex = session.dungeon.get("exit_x")
        ey = session.dungeon.get("exit_y")
        if ex is not None and (session.x, session.y) == (int(ex), int(ey)):
            await handle_leave_dungeon(session)
            return
        _save_dungeon_resume(session)
        _pet_keep_up(session, dx, dy)
        await send(session.ws, "PLAYER_UPDATE", player=session.full_state())
        return
    if not is_walkable(WORLD.grid, nx, ny):
        return
    if feature_flags.USE_PLAYER_HOUSING and not _housing.allow_step(session, nx, ny):
        await send(session.ws, "CHAT_MSG", **{"from": "Home", "text": "The stairs are the way down."})
        return
    if WORLD.occupied(nx, ny, exclude_player=session.player_id):
        return
    session.x, session.y = nx, ny
    session.gathering_node = None
    _release_monster_fight_on_step(session)
    WORLD.db.save_player_position(session.player_id, nx, ny)
    if feature_flags.USE_PLAYER_HOUSING:
        await _housing.on_step(session)
    await vacuum_ground_loot(session)
    _pet_keep_up(session, dx, dy)
    await send(session.ws, "PLAYER_UPDATE", player=session.full_state())
    await _notify_teleport_marks(session, _discover_teleport_marks(session))
    # Walking into a dungeon mouth enters it — same as clicking the entrance.
    spot, dungeon_id = _find_dungeon_entrance(session)
    if dungeon_id and (session.x, session.y) in entrance_mouth_tiles(
        spot["x"], spot["y"], spot.get("kind"),
    ):
        await handle_enter_dungeon(session, {"dungeon_id": dungeon_id})


def _dungeon_mod(session_or_id):
    """Resolve dungeon module from a session or dungeon id string."""
    if isinstance(session_or_id, str):
        return DUNGEON_MODS.get(session_or_id)
    d = getattr(session_or_id, "dungeon", None) or {}
    return DUNGEON_MODS.get(d.get("id") or "tidehollow", tidehollow)


def _dungeon_meta(dungeon_id: str) -> dict:
    return DUNGEON_META.get(dungeon_id) or DUNGEON_META["tidehollow"]


def _dungeon_monster_lookup(session, mid):
    if not session.dungeon:
        return None
    return session.dungeon["monsters"].get(mid)


def _build_dungeon_floor(session, floor: int, dungeon_id: str = None):
    dungeon_id = dungeon_id or (session.dungeon or {}).get("id") or "tidehollow"
    mod = DUNGEON_MODS.get(dungeon_id, tidehollow)
    meta = _dungeon_meta(dungeon_id)
    info = mod.floor_info(floor)
    # Tidehollow is segmented: a chain of chambers, each sealing its exits until
    # its own wave is dead. Other dungeons keep the single open floor they were
    # designed around.
    rooms = None
    if dungeon_id == "tidehollow" and hasattr(mod, "generate_rooms"):
        tiles, rooms = mod.generate_rooms(floor)
        mod.apply_seals(tiles, rooms)
    else:
        tiles = mod.generate_floor_tiles(floor)
    props = dungeon_props.install(
        tiles, dungeon_id, floor, mod.DUNGEON_SPAWN, (mod.DUNGEON_SPAWN[0], mod.DUNGEON_H - 1),
    )
    blocked = dungeon_props.cells(props)
    reserved = set()
    if dungeon_id == "emberdeep" and feature_flags.USE_EMBERDEEP_CREATURES and feature_flags.USE_EMBERDEEP_V2:
        import emberdeep_creatures
        reserved = emberdeep_creatures.reserved_tiles(tiles)
    spot_room = {}
    spot_visual = {}
    spot_level = {}
    if rooms:
        # Spread the floor's monsters across the chambers, leaving the
        # entrance hall empty so the player gets a moment to orient.
        #
        # Any chamber left holding no monsters must be considered cleared, or
        # its doors seal forever with no fight to open them.
        fight_rooms = [r for r in rooms if not r["cleared"]] or rooms
        spots = []
        per_room = mod.room_spawn_count(floor) if hasattr(mod, "room_spawn_count") else 3
        # Populate every chamber individually. Each room's kill target is the
        # number that actually spawned inside it, so "kill N to open the door"
        # is always achievable without farming respawns.
        claimed = set()
        for room in fight_rooms:
            if dungeon_id == "tidehollow":
                pool = [
                    p for p in mod.spawn_tiles_for_room(room, tiles, 64, rooms=rooms)
                    if p not in blocked and p not in reserved and p not in claimed
                ]
            else:
                pool = [
                    p for p in mod.spawn_tiles_for_room(room, tiles, 64)
                    if p not in blocked and p not in reserved and p not in claimed
                ]
            mod.random.Random(floor * 131 + room["id"]).shuffle(pool)
            room_spots = pool[:per_room]
            claimed.update(room_spots)
            types = ()
            if dungeon_id == "tidehollow" and hasattr(mod, "room_monster_types"):
                types = mod.room_monster_types(room["id"])
            room_level = (
                mod.room_combat_level(room["id"])
                if dungeon_id == "tidehollow" and hasattr(mod, "room_combat_level")
                else info["level"]
            )
            for i, pos in enumerate(room_spots):
                spot_room[pos] = room["id"]
                spot_level[pos] = room_level
                if types:
                    spot_visual[pos] = types[i % len(types)]
            spots.extend(room_spots)
            room["kills"] = 0
            # The target is the number that *actually* spawned here. Rooms are
            # only ever credited by looking up the tile a monster died on, and
            # corridors overlap room footprints, so a mismatch here would leave
            # a chamber needing kills it can never be given.
            room["kill_target"] = len(room_spots)
            if not room_spots:
                # A chamber props have filled cannot be fought in; leave it
                # open rather than sealing a door nothing can unlock.
                room["cleared"] = True
        for room in rooms:
            if room["cleared"]:
                room["kill_target"] = 0
                room["kills"] = 0
        # Seals were written before spawns were placed. Re-apply now that we
        # know which chambers are empty, so an empty room is never shut.
        for row in tiles:
            for i, tile in enumerate(row):
                if tile == mod.SEALED:
                    row[i] = mod.FLOOR
        mod.apply_seals(tiles, rooms)
    else:
        spots = [
            p for p in mod.pick_spawn_tiles(tiles, info["count"] + len(blocked) + len(reserved))
            if p not in blocked and p not in reserved
        ][: info["count"]]
    default_stats = mod.scaled_monster_stats(info["level"])
    default_visual = mod.visual_type_for_floor(floor)
    if hasattr(mod, "monster_display_name"):
        default_stats["name"] = mod.monster_display_name(default_visual, default_stats["level"])
    # Named encounters. These replace ordinary monsters rather than adding to
    # them. Tidehollow puts the elite + Leviathan in the final (dragon) chamber.
    elite_name = info.get("elite") if dungeon_id == "tidehollow" else None
    boss_info = info.get("boss") if dungeon_id == "tidehollow" else None

    def _indices_in_last_room():
        """Spawn indices in the furthest chamber (finale), furthest first."""
        if not spots:
            return []
        if rooms is None:
            return [len(spots) - 1]
        best_room = -1
        for pos in spots:
            rid = spot_room.get(pos)
            if rid is None:
                room = mod.room_at(rooms, pos[0], pos[1])
                rid = room["id"] if room is not None else -1
            if rid > best_room:
                best_room = rid
        return [idx for idx, pos in enumerate(spots) if spot_room.get(pos) == best_room]

    finale = _indices_in_last_room()
    boss_index = finale[-1] if boss_info and finale else -1
    elite_index = -1
    if elite_name and finale:
        # Prefer a different dragon than the Leviathan when the finale has 2+.
        for idx in reversed(finale):
            if idx != boss_index:
                elite_index = idx
                break
        if elite_index < 0 and boss_index < 0:
            elite_index = finale[-1]

    monsters = {}
    for index, (sx, sy) in enumerate(spots):
        mid = next_id()
        visual = spot_visual.get((sx, sy), default_visual)
        level = int(spot_level.get((sx, sy), info["level"]))
        mstats = mod.scaled_monster_stats(level)
        if hasattr(mod, "monster_display_name"):
            mstats["name"] = mod.monster_display_name(visual, mstats["level"])
        else:
            mstats["name"] = default_stats.get("name") or mstats.get("name")
        if index == boss_index and boss_info:
            bonus = int(boss_info.get("level_bonus") or 0)
            mstats = mod.scaled_monster_stats(level + bonus)
            mstats["name"] = boss_info["name"]
            mstats["boss"] = True
            mstats["hp"] = int(mstats["hp"] * 1.35)
            mstats["xp"] = int(mstats["xp"] * 2.2)
            visual = "dragon" if dungeon_id == "tidehollow" else visual
        elif index == elite_index and elite_name:
            mstats["name"] = elite_name
            mstats["elite"] = True
            mstats["hp"] = int(mstats["hp"] * 1.45)
            mstats["xp"] = int(mstats["xp"] * 1.6)
            mstats["def_bonus"] = int(mstats.get("def_bonus", 0)) + 2
        # Segmented floors progress on a kill *count*, so a respawn is a
        # feature: it lets the player finish a chamber's target without
        # hunting every corner. Other dungeons are still "kill everything",
        # where a respawn would make clearing impossible.
        respawns = dungeon_id == "tidehollow" and rooms
        m = MonsterInstance(mid, visual, sx, sy, stats=mstats,
                            no_respawn=not respawns)
        # Remember the chamber this beast belongs to. Kills are credited to
        # that room even if it wanders down a corridor into another.
        m._dungeon_room_id = spot_room.get((sx, sy))
        # Stay inside their chamber. A loose leash let Tidehollow beasts walk
        # into the next room before the door sealed, leaving the player in an
        # empty chamber with the exit barred.
        if dungeon_id == "emberdeep" and feature_flags.USE_EMBERDEEP_V2:
            m.home_room = emberdeep.room_box(tiles, sx, sy)
        elif dungeon_id == "tidehollow" and rooms is not None and m._dungeon_room_id is not None:
            home = next((r for r in rooms if r["id"] == m._dungeon_room_id), None)
            if home is not None and hasattr(mod, "room_interior_box"):
                m.home_room = mod.room_interior_box(home)
            else:
                cx, cy = (home or {}).get("center") or (sx, sy)
                m.home_room = (cx - 5, cy - 3, cx + 5, cy + 3)
        else:
            leash = 6
            m.home_room = (
                max(0, sx - leash),
                max(0, sy - leash),
                min(mod.DUNGEON_W - 1, sx + leash),
                min(mod.DUNGEON_H - 1, sy + leash),
            )
        monsters[mid] = m
    if dungeon_id == "emberdeep" and feature_flags.USE_EMBERDEEP_CREATURES and feature_flags.USE_EMBERDEEP_V2:
        import emberdeep_creatures
        extra_props, extra_monsters = emberdeep_creatures.build(
            tiles, next_id, MonsterInstance, emberdeep.scaled_monster_stats,
        )
        props = list(props) + extra_props
        for extra in extra_monsters:
            if not (extra.stats or {}).get("static"):
                extra.home_room = emberdeep.room_box(tiles, extra.x, extra.y)
            monsters[extra.id] = extra
    floors_list = getattr(mod, meta["floors_attr"], None) or getattr(mod, "TIDEHOLLOW_FLOORS", [])
    prev = session.dungeon or {}
    session.dungeon = {
        "id": dungeon_id,
        "floor": floor,
        "floors": len(floors_list),
        "label": info["label"],
        "tiles": tiles,
        "width": mod.DUNGEON_W,
        "height": mod.DUNGEON_H,
        "monsters": monsters,
        "rooms": rooms,
        "return_x": prev.get("return_x", mod.CAVE_RETURN[0]),
        "return_y": prev.get("return_y", mod.CAVE_RETURN[1]),
        "props": props,
    }
    if dungeon_id == "emberdeep" and feature_flags.USE_EMBERDEEP_V2:
        boss = emberdeep.v2_marks().get("boss")
        if boss:
            session.dungeon["boss_door"] = [int(boss[0]), int(boss[1])]
    session.x, session.y = mod.DUNGEON_SPAWN
    session.in_combat_with = None
    session.gathering_node = None
    if session.pet_id:
        _bring_pet(session)


def _dungeon_room_hud(session):
    """Room-scoped numbers for segmented floors: which chamber the player is
    standing in, its remaining wave, and how many are done. Empty for floors
    that are one open map."""
    d = session.dungeon
    if not d or not d.get("rooms"):
        return {}
    here = tidehollow.room_at(d["rooms"], session.x, session.y)
    left = {}
    for mon in d["monsters"].values():
        if not mon.alive:
            continue
        room = tidehollow.room_at(d["rooms"], mon.x, mon.y)
        if room is not None:
            left[room["id"]] = left.get(room["id"], 0) + 1
    # Which chamber is this, counting only the ones with fights, so "Chamber
    # 2 of 3" means something to the player.
    rooms = d["rooms"]
    fought = [r for r in rooms if r["doors"]] or rooms
    here_no = None
    if here is not None and here in fought:
        here_no = fought.index(here) + 1
    # Surface a named elite or boss when one is still alive in this chamber.
    threat = None
    if here is not None and not here["cleared"]:
        for mon in d["monsters"].values():
            stats = mon.stats or {}
            if not mon.alive or not (stats.get("boss") or stats.get("elite")):
                continue
            if tidehollow.room_at(rooms, mon.x, mon.y) is here:
                threat = {"name": stats.get("name") or "Something stirs",
                          "boss": bool(stats.get("boss"))}
                break
    # Kills earned vs kills needed. This is the number that opens the door, so
    # it is the one the HUD shows — "remaining alive" is not the goal any more
    # (respawns count), and showing it would be misleading.
    kills = int(here.get("kills") or 0) if here is not None else 0
    need = int(here.get("kill_target") or 0) if here is not None else 0
    return {
        "room": None if here is None else {
            "id": here["id"],
            "doors_open": bool(here["cleared"]),
            "kills": kills,
            "target": need,
            "remaining": max(0, need - kills),
            "alive": left.get(here["id"], 0),
            "number": here_no,
            "threat": threat,
        },
        "rooms_total": len(fought),
        "rooms_cleared": sum(1 for r in fought if r["cleared"]),
    }


def _dungeon_payload(session):
    d = session.dungeon
    alive = [m.public_state() for m in d["monsters"].values() if m.alive and not getattr(m, "concealed", False)]
    mod = _dungeon_mod(session)
    spawn = getattr(mod, "DUNGEON_SPAWN", (d["width"] // 2, max(0, d["height"] - 2)))
    exit_x, exit_y = int(spawn[0]), int(spawn[1])
    tiles = d.get("tiles") or []
    if tiles and 0 <= exit_x < d["width"]:
        # Southernmost floor on the spawn column = exit mouth
        for y in range(d["height"] - 1, -1, -1):
            if tiles[y][exit_x] == FLOOR:
                exit_y = y
                break
    if d.get("explore") and d.get("exit_x") is not None:
        exit_x = int(d["exit_x"])
        exit_y = int(d["exit_y"])
    else:
        d["exit_x"] = exit_x
        d["exit_y"] = exit_y
    payload = {
        "id": d["id"],
        "floor": d["floor"],
        "floors": d["floors"],
        "label": d["label"],
        "explore": bool(d.get("explore")),
        "name": d.get("name") or _dungeon_meta(d.get("id") or "tidehollow")["name"],
        "tiles": d["tiles"],
        "width": d["width"],
        "height": d["height"],
        "monsters": alive,
        "remaining": _dungeon_remaining(d),
        "player_x": session.x,
        "boss_door": d.get("boss_door"),
        "player_y": session.y,
        "exit_x": exit_x,
        "exit_y": exit_y,
        "props": d.get("props") or [],
    }
    payload.update(_dungeon_room_hud(session))
    if d.get("v2") == "depths":
        import depths_v2
        payload.update(depths_v2.client_extra(session))
    elif d.get("v2"):
        import void_v2
        payload.update(void_v2.client_extra(session))
    return payload


async def _grant_dungeon_kill_loot(session):
    """Auto-loot per instance-dungeon kill — coins/food scale with floor."""
    d = session.dungeon
    if not d:
        return
    mod = _dungeon_mod(session)
    meta = _dungeon_meta(d.get("id") or "tidehollow")
    chat_from = meta["chat_from"]
    floor = int(d.get("floor") or 1)
    info = mod.floor_info(floor)
    level = int(info.get("level") or floor * 8)
    loot = mod.roll_kill_loot(floor, level)
    if level < LOW_LEVEL_DROP_CAP:
        coins = next((qty for item_id, qty in loot if item_id == "coins"), None)
        if not coins:
            coins = random.randint(max(1, level), max(2, level * 4))
        loot = [("coins", coins)]
        if random.random() < 0.15:
            loot.append(("bones", 1))
    if not loot:
        return
    got = []
    for item_id, qty in loot:
        if item_id == "coins":
            gained, left = WORLD.add_coins(session, qty)
            if gained:
                got.append(f"{gained} coins")
            if left:
                await send(session.ws, "CHAT_MSG", **{
                    "from": chat_from,
                    "text": f"Purse full — {left} coins couldn't fit.",
                })
            continue
        if WORLD.add_item_to_inventory(session, item_id, qty):
            name = ITEMS.get(item_id, {}).get("name", item_id)
            got.append(f"{name} x{qty}" if qty > 1 else name)
        else:
            await send(session.ws, "CHAT_MSG", **{
                "from": chat_from,
                "text": f"Inventory full — missed {ITEMS.get(item_id, {}).get('name', item_id)}.",
            })
            break
    if got:
        shown = ", ".join(got[:4])
        extra = f" (+{len(got) - 4} more)" if len(got) > 4 else ""
        await send(session.ws, "CHAT_MSG", **{
            "from": chat_from, "text": f"Loot: {shown}{extra}.",
        })
        await send(session.ws, "PLAYER_UPDATE", player=session.full_state())


# Back-compat alias
_grant_tidehollow_kill_loot = _grant_dungeon_kill_loot


async def _grant_monster_table(session, monster):
    """Give a copied-dungeon kill its normal drop table, straight into the inventory."""
    spec = drops_for_kill(monster.type)
    got = []
    for item_id, chance, bounds in spec:
        if random.random() > chance:
            continue
        if isinstance(item_id, (list, tuple)):
            item_id = random.choice(item_id)
        lo, hi = bounds
        qty = random.randint(lo, hi)
        if item_id == "coins":
            gained, left = WORLD.add_coins(session, qty)
            if gained:
                got.append(f"{gained} coins")
            if left:
                # The purse caps at MAX_PURSE_COINS. Dropping the overflow
                # silently destroyed real rewards; say so instead (the quest
                # reward path already warned, this one did not).
                got.append(f"{left} coins lost (purse full — bank first)")
            continue
        if WORLD.add_item_to_inventory(session, item_id, qty):
            name = ITEMS.get(item_id, {}).get("name", item_id)
            got.append(f"{name} x{qty}" if qty > 1 else name)
    if got:
        await send(session.ws, "CHAT_MSG", **{
            "from": "Loot", "text": "Loot: " + ", ".join(got[:4]) + ".",
        })
        await send(session.ws, "PLAYER_UPDATE", player=session.full_state())


async def _finish_dungeon_kill(session, monster=None):
    """Floor dungeons advance when cleared. Explore maps drop normal loot and stay open."""
    d = session.dungeon
    if not d or d.get("completed"):
        return
    if d.get("explore"):
        if monster is not None:
            await _grant_monster_table(session, monster)
            check_quest_progress_on_kill(session, monster.type)
            if d.get("v2") and monster.type == "nyxarath":
                import void_v2
                await void_v2.announce_first_kill(session)
            if d.get("v2") == "depths" and monster.type == "morvath":
                import depths_v2
                await depths_v2.announce_first_kill(session)
        return
    await _grant_dungeon_kill_loot(session)
    if d.get("rooms"):
        # Count the kill toward its chamber's target. This is what opens doors
        # now; it replaces the old "are there any monsters left alive?" check,
        # so a respawn still contributes and nothing can stall progress.
        await credit_dungeon_room_kill(session, monster)
        _nudge_off_sealed_door(session)
    if not d.get("explore") and _floor_uncleared(d) == 0:
        await _dungeon_on_clear(session)


def _grant_room_cache(session, floor):
    """Give the loot for clearing one Tidehollow chamber. Returns labels."""
    try:
        loot = tidehollow.room_clear_reward(floor)
    except Exception:
        return []
    got = []
    for item_id, qty in loot:
        if item_id == "coins":
            gained, left = WORLD.add_coins(session, qty)
            if gained:
                got.append(f"{gained} coins")
            if left:
                got.append(f"{left} coins lost (purse full — bank first)")
            continue
        if WORLD.add_item_to_inventory(session, item_id, qty):
            name = ITEMS.get(item_id, {}).get("name", item_id)
            got.append(f"{name} x{qty}" if qty > 1 else name)
        else:
            got.append(f"{ITEMS.get(item_id, {}).get('name', item_id)} (bag full, left behind)")
    return got


def _nudge_off_sealed_door(session):
    """Never leave the player standing inside a door that just sealed.

    A door can slam while someone is on its threshold. Standing there is not
    fatal (they can step off), but it looks like a bug and can strand a player
    who walked in behind a wave. Push them to the nearest open floor tile.
    """
    d = session.dungeon
    if not d or not d.get("tiles"):
        return
    tiles = d["tiles"]
    x, y = int(session.x), int(session.y)
    if not (0 <= y < len(tiles) and 0 <= x < len(tiles[y])):
        return
    if tiles[y][x] != tidehollow.SEALED:
        return
    best = None
    for radius in range(1, 6):
        for dx in range(-radius, radius + 1):
            for dy in range(-radius, radius + 1):
                nx, ny = x + dx, y + dy
                if not (0 <= ny < len(tiles) and 0 <= nx < len(tiles[ny])):
                    continue
                if tiles[ny][nx] != FLOOR:
                    continue
                dist = abs(dx) + abs(dy)
                if best is None or dist < best[0]:
                    best = (dist, nx, ny)
        if best:
            break
    if best:
        session.x, session.y = best[1], best[2]


async def reconcile_dungeon_doors():
    """Safety net: reopen any chamber that is empty but still sealed.

    Doors normally open on the kill event. This runs every tick and fixes any
    room whose monsters are all dead but whose doors are still SEALED — the
    state a player gets stuck in when a kill is ever missed (a monster dying
    from a pet, a poison tick, a save/restore, or an older build).

    Cheap enough to run unconditionally: dungeons are private and short-lived,
    and it touches only sessions that are actually inside one.
    """
    for session in list(WORLD.sessions.values()):
        d = getattr(session, "dungeon", None)
        if not d or d.get("explore"):
            continue
        rooms = d.get("rooms")
        if not rooms:
            continue
        # Fast path: skip sessions with nothing sealed on the floor.
        if not any(tile == tidehollow.SEALED for row in (d.get("tiles") or []) for tile in row):
            continue
        try:
            await _open_cleared_rooms(session)
        except Exception:
            log.exception("door reconcile failed for %s", getattr(session, "char_name", "?"))


async def credit_dungeon_room_kill(session, monster):
    """Count one kill toward the chamber it happened in, and open the door when
    that chamber's target is met.

    Progression is a kill *count*, not "no monsters left alive". A monster that
    respawns therefore still counts when killed again — the player just needs
    the number, which is what the HUD promises — and it can never soft-lock on
    a beast that wandered out of reach or died somewhere off-screen.
    """
    d = getattr(session, "dungeon", None)
    rooms = (d or {}).get("rooms")
    if not rooms or not monster:
        return
    # Credit the chamber the monster belongs to. Room footprints include their
    # connecting corridor and two rooms can share one, so the room recorded at
    # spawn — not wherever the beast happened to die — is the reliable answer.
    home = getattr(monster, "_dungeon_room_id", None)
    if home is not None:
        room = next((r for r in rooms if r["id"] == home), None)
    else:
        room = tidehollow.room_at(rooms, monster.x, monster.y)
    if room is None or room.get("cleared"):
        return
    room["kills"] = int(room.get("kills") or 0) + 1
    target = int(room.get("kill_target") or 0)
    if room["kills"] < target:
        await send(session.ws, "CHAT_MSG", **{
            "from": "Tidehollow",
            "text": f"Chamber {room['id'] + 1}: {room['kills']}/{target} slain.",
        })
        return
    await _open_cleared_rooms(session)


async def _refresh_tidehollow_seals(session):
    """Recompute chamber seals from clear progress + player position.

    Returns the list of ``[x, y, tile]`` changes pushed to the client (may be empty).
    """
    d = session.dungeon
    if not d or d.get("id") != "tidehollow" or not d.get("rooms"):
        return []
    tiles = d.get("tiles") or []
    before = {
        (x, y): tile
        for y, row in enumerate(tiles)
        for x, tile in enumerate(row)
        if tile in (tidehollow.FLOOR, tidehollow.SEALED)
    }
    tidehollow.apply_seals(tiles, d["rooms"], player_xy=(session.x, session.y))
    _nudge_off_sealed_door(session)
    changes = []
    for y, row in enumerate(tiles):
        for x, tile in enumerate(row):
            if tile not in (tidehollow.FLOOR, tidehollow.SEALED):
                continue
            if before.get((x, y)) != tile:
                changes.append([int(x), int(y), tile])
    if changes:
        await send(session.ws, "DUNGEON_TILES", changes=changes)
    return changes


async def _open_cleared_rooms(session):
    """Unseal any chamber whose kill target has been reached."""
    d = session.dungeon
    rooms = d.get("rooms")
    if not rooms:
        return
    opened = []
    for room in rooms:
        if room["cleared"]:
            continue
        if int(room.get("kills") or 0) < int(room.get("kill_target") or 0):
            continue
        if not room["doors"]:
            continue
        room["cleared"] = True
        opened.append(room)
    if not opened:
        return
    # Say exactly where the player stands. The only progress signal used to be
    # a door opening, so "have I hit the number?" was guesswork.
    total_rooms = len([r for r in rooms if r["doors"]]) or len(rooms)
    cleared_rooms = sum(1 for r in rooms if r["cleared"] and r["doors"])
    floor_left = sum(1 for m in d["monsters"].values() if m.alive)
    await send(session.ws, "CHAT_MSG", **{
        "from": "Tidehollow",
        "text": (f"The chamber falls silent — {cleared_rooms}/{total_rooms} chambers clear, "
                 f"{floor_left} beast{'s' if floor_left != 1 else ''} left. The way ahead opens."),
    })
    # Clearing a chamber earns a cache: coins plus something to keep going.
    # Paid once per room, on the same event that opens the door, so it cannot
    # be farmed by walking in and out.
    if d.get("id") == "tidehollow":
        for room in opened:
            if room.get("reward_paid"):
                continue
            room["reward_paid"] = True
            got = _grant_room_cache(session, int(d.get("floor") or 1))
            if got:
                await send(session.ws, "CHAT_MSG", **{
                    "from": "Cache", "text": "Hidden cache: " + ", ".join(got) + ".",
                })
                await send(session.ws, "PLAYER_UPDATE", player=session.full_state())
    await _refresh_tidehollow_seals(session)


def _find_dungeon_entrance(session, preferred_id=None):
    """Return (spot, dungeon_id) if the player stands at a private-dungeon mouth."""
    kinds = set()
    for meta in DUNGEON_META.values():
        kinds.update(meta["entrance_kinds"])
    for spot in INTERACTABLES:
        kind = spot.get("kind")
        if kind not in kinds:
            continue
        on_mouth = (session.x, session.y) in entrance_mouth_tiles(
            spot["x"], spot["y"], kind,
        )
        # Volcano: door tiles only — never enter from adjacent cone/apron sides.
        if not on_mouth:
            if kind == "volcano_entrance":
                continue
            if not adjacent_or_same(session.x, session.y, spot["x"], spot["y"]):
                continue
        did = spot.get("dungeon_id")
        if not did:
            # Infer from entrance kind
            for kid, meta in DUNGEON_META.items():
                if kind in meta["entrance_kinds"]:
                    did = kid
                    break
        if preferred_id and did != preferred_id:
            continue
        return spot, did
    return None, None


def _read_dungeon_resume(row):
    if row is None or "dungeon_resume" not in row.keys():
        return None
    raw = row["dungeon_resume"] or ""
    if not raw:
        return None
    try:
        data = json.loads(raw)
    except (TypeError, ValueError):
        return None
    if not isinstance(data, dict) or not data.get("id"):
        return None
    return data


def _resume_payload(session):
    d = session.dungeon
    if not d or d.get("id") == "castle_realm":
        return None
    return {
        "id": d.get("id") or "tidehollow",
        "x": int(session.x),
        "y": int(session.y),
        "return_x": d.get("return_x"),
        "return_y": d.get("return_y"),
        "opened": list(d.get("opened") or []),
        "floor": int(d.get("floor") or 1),
    }


def _save_dungeon_resume(session):
    blob = _resume_payload(session)
    if blob is None:
        return
    WORLD.db.save_player_stats(session.player_id, dungeon_resume=json.dumps(blob))


def _clear_dungeon_resume(session):
    WORLD.db.save_player_stats(session.player_id, dungeon_resume="")


def _apply_opened_doors(session, opened):
    d = session.dungeon
    if not d:
        return
    clean = []
    for ch in opened or []:
        if isinstance(ch, str) and len(ch) == 1 and ch not in clean:
            clean.append(ch)
    d["opened"] = clean
    if d.get("v2") == "depths":
        import depths_v2
        depths_v2.refresh(d)
    elif d.get("v2"):
        import void_v2
        void_v2._refresh(d)


def _stand_in_dungeon(session, x, y):
    tiles = session.dungeon.get("tiles") or []
    mod = _dungeon_mod(session)

    def walkable(nx, ny):
        if mod is None:
            return False
        return mod.dungeon_walkable(tiles, nx, ny)

    if not walkable(x, y):
        found = None
        for radius in range(1, 8):
            for dy in range(-radius, radius + 1):
                for dx in range(-radius, radius + 1):
                    if walkable(x + dx, y + dy):
                        found = (x + dx, y + dy)
                        break
                if found:
                    break
            if found:
                break
        if found:
            x, y = found
        else:
            x, y = session.x, session.y
    session.x, session.y = int(x), int(y)
    if session.pet_id:
        _bring_pet(session)


async def _relock_dungeon_doors(session):
    """Death puts every opened seal back to locked."""
    d = session.dungeon
    if not d:
        return
    before = [row[:] for row in (d.get("tiles") or [])]
    had = list(d.get("opened") or [])
    d["opened"] = []
    if d.get("v2") == "depths":
        import depths_v2
        depths_v2.refresh(d)
    elif d.get("v2"):
        import void_v2
        void_v2._refresh(d)
    if not had:
        return
    import void_v2
    changes = void_v2._changes_from(before, d.get("tiles") or [])
    await send(session.ws, "DUNGEON_TILES", changes=changes, decor=d.get("decor") or {})
    await send(session.ws, "CHAT_MSG", **{
        "from": "Dungeon",
        "text": "The seals grind shut.",
    })


async def _resume_dungeon(session, resume):
    dungeon_id = resume.get("id")
    if not explore_dungeons.is_explore(dungeon_id) and dungeon_id not in DUNGEON_MODS:
        _clear_dungeon_resume(session)
        return
    meta = _dungeon_meta(dungeon_id)
    if explore_dungeons.is_explore(dungeon_id):
        explore_dungeons.build(session, dungeon_id, next_id, MonsterInstance, MONSTER_SPAWNS)
    else:
        _build_dungeon_floor(session, int(resume.get("floor") or 1), dungeon_id=dungeon_id)
    if not session.dungeon:
        _clear_dungeon_resume(session)
        return
    rx, ry = resume.get("return_x"), resume.get("return_y")
    session.dungeon["return_x"] = rx
    session.dungeon["return_y"] = ry
    if rx is not None and ry is not None:
        session._dungeon_return = (int(rx), int(ry))
    _apply_opened_doors(session, resume.get("opened") or [])
    _stand_in_dungeon(session, int(resume.get("x") or session.x), int(resume.get("y") or session.y))
    _save_dungeon_resume(session)
    await send(session.ws, "DUNGEON_ENTER", **_dungeon_payload(session))
    await send(session.ws, "PLAYER_UPDATE", player=session.full_state())
    await send(session.ws, "CHAT_MSG", **{
        "from": meta["chat_from"],
        "text": f"You wake in {meta['name']}, where you left off.",
    })


async def handle_enter_dungeon(session, msg):
    if session.dungeon:
        meta = _dungeon_meta(session.dungeon.get("id") or "tidehollow")
        await send(session.ws, "ERROR", message=f"You are already inside {meta['name']}.")
        return
    preferred = msg.get("dungeon_id")
    if preferred == "castle_realm" and feature_flags.USE_CASTLE_REALM:
        spot, dungeon_id = _find_dungeon_entrance(session, preferred_id=preferred)
        if dungeon_id != "castle_realm":
            await send(session.ws, "ERROR", message="Stand at the Castle Realm portal.")
            return
        import castle_realm
        castle_realm.enter(session)
        _bring_pet(session)
        await send(session.ws, "DUNGEON_ENTER", **castle_realm.payload(session))
        import castle_owners
        await castle_owners.send_state(session)
        await send(session.ws, "PLAYER_UPDATE", player=session.full_state())
        await send(session.ws, "CHAT_MSG", **{
            "from": "Castle Realm",
            "text": "You step through the portal into the Castle Realm. The return portal stands south of the plaza.",
        })
        return
    spot, dungeon_id = _find_dungeon_entrance(session, preferred_id=preferred)
    if not dungeon_id:
        await send(session.ws, "ERROR", message="Stand at a dungeon entrance.")
        return
    missing = gear_rules.gate_missing(session, ITEMS)
    if missing:
        await send(session.ws, "ERROR", message=gear_rules.gate_message(missing))
        return
    mod = DUNGEON_MODS.get(dungeon_id, tidehollow)
    meta = _dungeon_meta(dungeon_id)
    # Step back off the mouth so leaving doesn't drop you straight back inside.
    rx, ry = session.x, session.y
    if (rx, ry) in entrance_mouth_tiles(spot["x"], spot["y"], spot.get("kind")):
        stand = spot.get("stand") or []
        if len(stand) == 2:
            rx, ry = int(stand[0]), int(stand[1])
        else:
            # South of a 3-wide door + apron enter zone.
            rx, ry = spot["x"], spot["y"] + 3
    session._dungeon_return = (rx, ry)
    # Keep the overworld tile. A later logout must not store the dungeon coordinates.
    WORLD.db.save_player_position(session.player_id, rx, ry)
    _clear_dungeon_resume(session)
    if explore_dungeons.is_explore(dungeon_id):
        explore_dungeons.build(session, dungeon_id, next_id, MonsterInstance, MONSTER_SPAWNS)
        session.dungeon["return_x"] = rx
        session.dungeon["return_y"] = ry
        _bring_pet(session)
        await send(session.ws, "DUNGEON_ENTER", **_dungeon_payload(session))
        await send(session.ws, "PLAYER_UPDATE", player=session.full_state())
        await send(
            session.ws, "CHAT_MSG",
            **{"from": meta["chat_from"],
               "text": f"You enter {meta['name']}. The EXIT is just south of where you came in — walk onto it, or press Leave."},
        )
        return
    _build_dungeon_floor(session, 1, dungeon_id=dungeon_id)
    session.dungeon["return_x"] = mod.CAVE_RETURN[0]
    session.dungeon["return_y"] = mod.CAVE_RETURN[1]
    await send(session.ws, "DUNGEON_ENTER", **_dungeon_payload(session))
    await send(session.ws, "PLAYER_UPDATE", player=session.full_state())
    if dungeon_id == "tidehollow":
        rooms_n = len([r for r in (session.dungeon.get("rooms") or []) if r["doors"]])
        await send(session.ws, "CHAT_MSG", **{
            "from": meta["chat_from"],
            "text": (f"You enter Tidehollow Cave — {rooms_n} chambers. "
                     "Three beasts share each room with you; clear them to open the way. "
                     "Dragons wait in the last. The EXIT behind you always stays open."),
        })
        info = tidehollow.floor_info(1)
        if info.get("boss"):
            await send(session.ws, "CHAT_MSG", **{
                "from": meta["chat_from"],
                "text": f"{info['boss']['name']} coils in the final chamber.",
                "style": "gold",
            })
        try:
            my_level = session.combat_level()
        except Exception:
            my_level = 0
        # First chamber is easy; warn against the finale tier.
        if my_level and my_level < 60:
            await send(session.ws, "CHAT_MSG", **{
                "from": meta["chat_from"],
                "text": (f"Caution: the deepest beasts climb toward level 80, and you are "
                         f"combat level {my_level}. Bring food, and remember the EXIT."),
                "style": "gold",
            })
    else:
        await send(
            session.ws, "CHAT_MSG",
            **{"from": meta["chat_from"],
               "text": f"Floor 1/{session.dungeon['floors']}: {session.dungeon['label']}. "
                       "Slay every beast to advance. Leave anytime from the EXIT."},
        )


async def handle_leave_dungeon(session, msg=None, silent=False):
    if not session.dungeon:
        return
    task = getattr(session, "_dungeon_victory_task", None)
    if task and not task.done():
        task.cancel()
    session._dungeon_victory_task = None
    if session.dungeon.get("id") == "castle_realm":
        import castle_realm
        castle_realm.leave(session)
        WORLD.db.save_player_position(session.player_id, session.x, session.y)
        _bring_pet(session)
        await send(session.ws, "DUNGEON_EXIT", x=session.x, y=session.y)
        await send(session.ws, "PLAYER_UPDATE", player=session.full_state())
        if not silent:
            await send(session.ws, "CHAT_MSG", **{
                "from": "Castle Realm", "text": "You return beside the Castle Realm portal.",
            })
        return
    if session.dungeon.get("v2"):
        import void_v2
        void_v2.strip_keys(session)
    _clear_dungeon_resume(session)
    dungeon_id = session.dungeon.get("id") or "tidehollow"
    mod = DUNGEON_MODS.get(dungeon_id, tidehollow)
    meta = _dungeon_meta(dungeon_id)
    rx, ry = session.dungeon.get("return_x"), session.dungeon.get("return_y")
    saved = getattr(session, "_dungeon_return", None)
    if saved:
        rx, ry = saved
    cave = getattr(mod, "CAVE_RETURN", None)
    session.dungeon = None
    session.in_combat_with = None
    session.pet_target_id = None
    session.x = rx if rx is not None else (cave[0] if cave else session.x)
    session.y = ry if ry is not None else (cave[1] if cave else session.y)
    WORLD.db.save_player_position(session.player_id, session.x, session.y)
    _bring_pet(session)
    await send(session.ws, "DUNGEON_EXIT", x=session.x, y=session.y)
    await send(session.ws, "PLAYER_UPDATE", player=session.full_state())
    if not silent:
        await send(session.ws, "CHAT_MSG", **{"from": meta["chat_from"], "text": f"You leave {meta['name']}."})


DUNGEON_VICTORY_HOLD_S = 5.0


async def _leave_after_dungeon_victory(session, delay):
    """Wait, then eject a player who finished a private dungeon."""
    try:
        await asyncio.sleep(max(0.0, float(delay)))
    except asyncio.CancelledError:
        return
    d = getattr(session, "dungeon", None)
    if not d or not d.get("completed"):
        return
    meta = _dungeon_meta(d.get("id") or "tidehollow")
    await handle_leave_dungeon(session, silent=True)
    await send(session.ws, "PLAYER_UPDATE", player=session.full_state())
    await send(session.ws, "CHAT_MSG", **{
        "from": meta["chat_from"],
        "text": f"You leave {meta['name']}.",
    })


async def _dungeon_on_clear(session):
    """Called when the last monster on the current floor dies."""
    d = session.dungeon
    if not d or d.get("completed"):
        return
    dungeon_id = d.get("id") or "tidehollow"
    mod = DUNGEON_MODS.get(dungeon_id, tidehollow)
    meta = _dungeon_meta(dungeon_id)
    chat_from = meta["chat_from"]
    floor = d["floor"]
    if floor >= d["floors"]:
        # Complete! Hold the player in the instance briefly so the victory
        # screen can read, then auto-leave.
        item_id, qty = mod.pick_completion_reward()
        medal_id = meta["medal_id"]
        drop_xy = (mod.CAVE_RETURN[0], mod.CAVE_RETURN[1])
        rewards = []
        if item_id == "coins":
            gained, left = WORLD.add_coins(session, qty)
            rewards.append({"item_id": "coins", "qty": gained})
            if left:
                WORLD.ground_items.setdefault(drop_xy, []).append(_ground_drop("coins", left))
        elif WORLD.add_item_to_inventory(session, item_id, qty):
            rewards.append({"item_id": item_id, "qty": qty})
        else:
            WORLD.ground_items.setdefault(drop_xy, []).append(_ground_drop(item_id, qty))
            rewards.append({"item_id": item_id, "qty": qty, "ground": True})
        # Medal — guaranteed drop on first clear (bag → ground at the mouth → equip).
        has_medal = bool(medal_id) and (
            session.equipment.get("amulet") == medal_id
            or any(e and e.get("item_id") == medal_id for e in session.inventory.values())
            or WORLD.count_item_bank(session, medal_id) > 0
        )
        if medal_id and not has_medal:
            if WORLD.add_item_to_inventory(session, medal_id, 1):
                pass
            else:
                # Bag full: leave it on the ground at the cave mouth so it is never lost.
                WORLD.ground_items.setdefault(drop_xy, []).append(_ground_drop(medal_id, 1))
                rewards.append({"item_id": medal_id, "qty": 1, "ground": True})
            if not any(r.get("item_id") == medal_id for r in rewards):
                rewards.append({"item_id": medal_id, "qty": 1})
        name = session.char_name
        reward_name = ITEMS.get(item_id, {}).get("name", item_id)
        hold = DUNGEON_VICTORY_HOLD_S
        d["completed"] = True
        d["leave_at"] = time.time() + hold
        session.in_combat_with = None
        await send(session.ws, "DUNGEON_COMPLETE", rewards=rewards,
                   name=meta["name"], leave_in=hold)
        await send(session.ws, "PLAYER_UPDATE", player=session.full_state())
        await send(session.ws, "CHAT_MSG", **{
            "from": chat_from,
            "text": (f"{meta['name']} conquered! Returning outside in "
                     f"{int(hold)} seconds…"),
            "style": "gold",
        })
        # Golden global announcement
        for s in WORLD.sessions.values():
            await send(
                s.ws, "CHAT_MSG",
                **{
                    "from": chat_from,
                    "text": f"{name} has conquered {meta['name']} and claimed {qty}x {reward_name}!",
                    "style": "gold",
                },
            )
        task = getattr(session, "_dungeon_victory_task", None)
        if task and not task.done():
            task.cancel()
        session._dungeon_victory_task = asyncio.create_task(
            _leave_after_dungeon_victory(session, hold)
        )
        return

    # Advance to next floor
    nxt = floor + 1
    _build_dungeon_floor(session, nxt, dungeon_id=dungeon_id)
    await send(session.ws, "DUNGEON_FLOOR", **_dungeon_payload(session))
    await send(session.ws, "PLAYER_UPDATE", player=session.full_state())
    if dungeon_id == "tidehollow":
        ninfo = tidehollow.floor_info(nxt)
        boss = ninfo.get("boss")
        if boss:
            await send(session.ws, "CHAT_MSG", **{
                "from": chat_from,
                "text": f"Something vast shifts in the dark below: {boss['name']} waits on floor {nxt}.",
                "style": "gold",
            })
    await send(
        session.ws, "CHAT_MSG",
        **{"from": chat_from,
           "text": f"Floor {nxt}/{session.dungeon['floors']}: {session.dungeon['label']}. The beasts grow fiercer."},
    )
    if dungeon_id == "tidehollow":
        # A clear target for the floor, so the player knows exactly what to aim
        # for instead of finding out only when a door opens.
        info = tidehollow.floor_info(nxt)
        rooms_n = len([r for r in (session.dungeon.get("rooms") or []) if r["doors"]])
        await send(session.ws, "CHAT_MSG", **{
            "from": chat_from,
            "text": (f"Target: slay {info['count']} beasts across {rooms_n} chambers "
                     f"(level {info['level']}). Your health is restored on each new floor."),
        })
        # Restore some health between floors: a long run on nothing but found
        # food is punishing, and a fresh floor is a natural checkpoint.
        healed = min(session.max_hp(), session.hp + int(session.max_hp() * 0.35))
        if healed > session.hp:
            session.hp = healed
            await send(session.ws, "PLAYER_UPDATE", player=session.full_state())


async def bury_bone_stack(session, item_id, qty, quiet=False):
    """Bury karma bones one at a time. Returns total XP gained."""
    item = ITEMS.get(item_id) or {}
    xp_each = int(item.get("karma_xp") or 0)
    qty = max(0, int(qty))
    if xp_each <= 0 or qty <= 0:
        return 0
    before = session.level("karma")
    total_xp = 0
    leveled = False
    final_level = before
    for _ in range(qty):
        b, a = WORLD.grant_xp(session, "karma", xp_each)
        total_xp += xp_each
        if a > b:
            leveled = True
        final_level = a
    await send(
        session.ws, "SKILL_XP",
        player_id=session.player_id, skill="karma", gained=total_xp,
        xp=session.xp["karma"], level=final_level, leveled_up=leveled,
    )
    if not quiet:
        noun = item.get("name", "bones").lower()
        if qty == 1:
            text = f"You bury the {noun}. Karma +{total_xp} XP."
        else:
            text = f"You bury {qty} {noun}. Karma +{total_xp} XP."
        await send(session.ws, "CHAT_MSG", **{"from": "World", "text": text})
    return total_xp


async def vacuum_ground_loot(session, quiet=False):
    """Scoop coins underfoot and adjacent; scoop items on your tile if auto-pickup is on.
    Bones are always auto-buried one at a time (never kept in inventory from the ground).
    """
    expire_ground_items()
    if session.dungeon and session.dungeon.get("v2"):
        import void_v2
        await void_v2.vacuum(session, quiet)
        return
    expire_ground_items()
    tiles = [(session.x, session.y)]
    for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1), (1, 1), (1, -1), (-1, 1), (-1, -1)):
        tiles.append((session.x + dx, session.y + dy))
    collected_coins = 0
    collected_names = []
    bones_buried = 0
    for key in tiles:
        items_here = WORLD.ground_items.get(key)
        if not items_here:
            continue
        remaining = []
        on_me = key == (session.x, session.y)
        for entry in items_here:
            item_id, qty = entry["item_id"], entry["qty"]
            if item_id == "coins":
                gained, left = WORLD.add_coins(session, qty)
                collected_coins += gained
                if left:
                    leftover = {"item_id": "coins", "qty": left}
                    if entry.get("expires_at"):
                        leftover["expires_at"] = entry["expires_at"]
                    remaining.append(leftover)
                continue
            # Always bury bones from vacuum range (never keep them from the ground)
            if ITEMS.get(item_id, {}).get("karma_xp"):
                await bury_bone_stack(session, item_id, qty, quiet=True)
                bones_buried += qty
                continue
            if pickup_ignored(session, item_id):
                remaining.append(entry)
                continue
            if not (on_me and session.auto_pickup_items):
                remaining.append(entry)
                continue
            if WORLD.add_item_to_inventory(session, item_id, qty):
                collected_names.append(ITEMS.get(item_id, {}).get("name", item_id))
            else:
                remaining.append(entry)
        if remaining:
            WORLD.ground_items[key] = remaining
        elif key in WORLD.ground_items:
            del WORLD.ground_items[key]
    if collected_coins:
        if not quiet:
            msg = f"You collect {collected_coins} coins."
            if session.coins >= MAX_PURSE_COINS:
                msg += " (purse full — bank the rest)"
            await send(session.ws, "CHAT_MSG", **{"from": "World", "text": msg})
    if bones_buried and not quiet:
        await send(session.ws, "CHAT_MSG", **{
            "from": "World",
            "text": f"You bury {bones_buried} bone{'s' if bones_buried != 1 else ''}.",
        })
    if collected_names and not quiet:
        shown = ", ".join(collected_names[:3])
        extra = f" (+{len(collected_names) - 3} more)" if len(collected_names) > 3 else ""
        await send(session.ws, "CHAT_MSG", **{
            "from": "World", "text": f"You pick up {shown}{extra}.",
        })


async def handle_set_option(session, msg):
    changed = False
    if "auto_pickup_items" in msg:
        session.auto_pickup_items = bool(msg["auto_pickup_items"])
        WORLD.db.save_player_stats(session.player_id, auto_pickup_items=1 if session.auto_pickup_items else 0)
        state = "ON" if session.auto_pickup_items else "OFF"
        await send(session.ws, "CHAT_MSG", **{
            "from": "Options", "text": f"Auto-pickup items: {state} (coins always collect).",
        })
        changed = True
    add_id = msg.get("pickup_ignore_add")
    remove_id = msg.get("pickup_ignore_remove")
    if add_id and add_id in ITEMS and add_id != "coins":
        session.pickup_ignore.add(add_id)
        WORLD.db.save_player_stats(
            session.player_id, pickup_ignore=json.dumps(sorted(session.pickup_ignore)),
        )
        name = ITEMS[add_id]["name"]
        await send(session.ws, "CHAT_MSG", **{
            "from": "Options", "text": f"You will never pick up {name} again.",
        })
        changed = True
    if remove_id and remove_id in session.pickup_ignore:
        session.pickup_ignore.discard(remove_id)
        WORLD.db.save_player_stats(
            session.player_id, pickup_ignore=json.dumps(sorted(session.pickup_ignore)),
        )
        name = ITEMS.get(remove_id, {}).get("name", remove_id)
        await send(session.ws, "CHAT_MSG", **{
            "from": "Options", "text": f"You will pick up {name} again.",
        })
        changed = True
    if changed:
        await send(session.ws, "PLAYER_UPDATE", player=session.full_state())


async def handle_chat(session, msg):
    text = (msg.get("text") or "").strip()[:200]
    if not text:
        return
    if text.startswith("::"):
        await handle_dev_command(session, text)
        return
    if text.lower().startswith("/news"):
        for line in politics.latest_news(WORLD.db.conn, politics.NEWS_CMD_LINES) or ["No news yet."]:
            await send(session.ws, "CHAT_MSG", **{"from": "Notice Board", "text": line})
        return
    if text.lower().startswith("/house"):
        parts = text.split()
        conn = WORLD.db.conn
        if len(parts) >= 2 and parts[1].lower() in ("support", "oppose"):
            _ok, msg_ = politics.support(conn, session.player_id, parts[1].lower())
            await send(session.ws, "CHAT_MSG", **{"from": "Noble Houses", "text": msg_})
            return
        for line in politics.house_lines(conn, session.player_id):
            await send(session.ws, "CHAT_MSG", **{"from": "Noble Houses", "text": line})
        return
    if text.lower().startswith("/kingdom"):
        await handle_politics_msg(session, "KINGDOM_STATE", {})
        return
    if text.lower().startswith("/court"):
        parts = text.split()
        if len(parts) >= 2:
            await handle_politics_msg(session, "COURT_CHOOSE", {"choice": parts[1].lower()})
            return
        ev = politics.event_payload(WORLD.db.conn, session.player_id)
        if not ev:
            await send(session.ws, "CHAT_MSG", **{"from": "Royal Herald", "text": "No court matter is open."})
        else:
            await send(session.ws, "COURT_EVENT", event=ev)
        return
    if text.lower().startswith("/reigns"):
        for line in ruling.reign_lines(WORLD.db.conn):
            await send(session.ws, "CHAT_MSG", **{"from": "Keeper of Records", "text": line})
        return
    if text.lower().startswith("/treasury"):
        parts = text.split()
        sub = parts[1].lower() if len(parts) > 1 else ""
        if sub == "bounty" and len(parts) >= 4:
            await handle_rule(session, "RULE_POST_BOUNTY", {"monster": parts[2], "amount": parts[3]})
        elif sub == "cancel" and len(parts) >= 3:
            await handle_rule(session, "RULE_CANCEL_BOUNTY", {"id": parts[2].lstrip("#")})
        elif sub == "appoint" and len(parts) >= 4:
            post, _sep, who = text.split(None, 2)[2].rpartition(" ")
            await handle_rule(session, "RULE_APPOINT", {"post": post.strip().title(), "player": who})
        elif sub == "dismiss" and len(parts) >= 3:
            await handle_rule(session, "RULE_DISMISS", {"post": " ".join(parts[2:]).title()})
        elif sub == "tax" and len(parts) >= 4:
            await handle_rule(session, "RULE_SET_TAX", {"key": parts[2], "value": parts[3]})
        elif sub == "fund" and len(parts) >= 3:
            await handle_rule(session, "RULE_FUND_WORK", {"key": parts[2]})
        elif sub == "announce":
            await handle_rule(session, "RULE_ANNOUNCE", {"text": text.split(None, 2)[2] if len(parts) > 2 else ""})
        elif sub == "free":
            await handle_rule(session, "RULE_FREE_KING", {})
        elif sub == "recall":
            await handle_rule(session, "RULE_RECALL_KING", {})
        else:
            await handle_rule(session, "RULE_STATE", {})
        return
    if text.lower().startswith("/throne"):
        parts = text.split()
        if len(parts) >= 3 and parts[1].lower() in ("crown", "castle", "acclaim"):
            msg_ = await throne_schedule(session, parts[1].lower(), parts[2])
            await send(session.ws, "CHAT_MSG", **{"from": "Royal Herald", "text": msg_})
            return
        for line in throne.summary_lines(WORLD.db.conn, throne_live._name):
            await send(session.ws, "CHAT_MSG", **{"from": "Royal Herald", "text": line})
        return
    if text.lower().startswith(("/clan", "/guild")):
        import clans
        await clans.handle_command(session, text)
        return
    await broadcast(
        "CHAT_MSG",
        **{"from": nobility.display_name(session), "text": text, "player_id": session.player_id, "speech": True},
    )


def _wish_well_pos():
    """Tile of the wishing well interactable. The old constant (30, 21) is not that tile."""
    for spot in INTERACTABLES:
        if spot.get("id") == "wishing_well" or spot.get("kind") == "wishing_well":
            return int(spot["x"]), int(spot["y"])
    return (32, 22)


WISH_WELL_POS = _wish_well_pos()

WISH_GEAR_POOL = [
    # Common / uncommon armour & weapons
    "leather_body", "leather_chaps", "leather_cowl",
    "bronze_sword", "bronze_battleaxe",
    "bronze_helmet", "bronze_sq_shield", "bronze_body", "bronze_legs",
    "bronze_chainbody", "bronze_chainlegs",
    "iron_sword", "iron_battleaxe",
    "iron_helmet", "iron_sq_shield", "iron_body", "iron_legs",
    "iron_chainbody", "iron_chainlegs",
    "steel_longsword", "steel_battleaxe",
    "steel_helmet", "steel_sq_shield", "steel_body", "steel_legs",
    "steel_chainbody", "steel_chainlegs",
    "mithril_sword", "mithril_helmet",
    "mithril_sq_shield", "mithril_chainbody", "mithril_chainlegs",
]

WISH_MYTHOS_POOL = [
    "mythos_longsword", "mythos_body",
    "mythos_helmet", "mythos_legs", "mythos_shield",
]

# Mid/high gear given preferential weight on gear wishes
WISH_GEAR_BETTER = [
    "steel_longsword", "steel_battleaxe", "steel_body", "steel_legs",
    "steel_helmet", "steel_shield", "steel_chainbody", "steel_chainlegs",
    "mithril_sword", "mithril_helmet",
    "mithril_sq_shield", "mithril_chainbody", "mithril_chainlegs",
    "mithril_body", "mithril_legs", "mithril_battleaxe", "mithril_shield",
]


def _near_wishing_well(session):
    return adjacent_or_same(session.x, session.y, *WISH_WELL_POS)


async def _broadcast_well_rare(kind, text):
    await broadcast(
        "WELL_RARE",
        x=WISH_WELL_POS[0], y=WISH_WELL_POS[1],
        kind=kind, text=text,
    )


async def handle_wish(session, msg):
    kind = (msg.get("kind") or "").strip().lower()
    if kind not in ("power", "gear", "gold"):
        await send(session.ws, "ERROR", message="Choose power, gear, or gold.")
        return
    if not _near_wishing_well(session):
        await send(session.ws, "ERROR", message="Stand next to the Wishing Well.")
        return
    if session.pending_wish_stat:
        await send(session.ws, "ERROR", message="Choose which skill to raise first.")
        return
    if not session.can_wish():
        await send(session.ws, "ERROR", message="You already made a wish today. Come back tomorrow.")
        return

    session.mark_wish_used()
    rare = False
    result_text = ""

    if kind == "power":
        roll = random.random()
        if roll < 0.05:
            # Permanent +1 to a skill of the player's choice (5%)
            session.pending_wish_stat = True
            rare = True
            await send(
                session.ws, "WISH_STAT_CHOICE",
                skills=["attack", "strength", "defence", "archery"],
                message="The well grants a permanent power — choose a skill to raise by 1!",
            )
            await _broadcast_well_rare("power", f"{session.char_name} got a rare permanent power from the well!")
            await send(session.ws, "PLAYER_UPDATE", player=session.full_state())
            return
        # Remaining: ~45% strength, ~50% super strength
        if roll < 0.50:
            item_id = "strength_potion"
        else:
            item_id = "super_strength_potion"
        if not WORLD.add_item_to_inventory(session, item_id, 1):
            # Refund wish day if inventory full (fairness)
            if not session.has_unlimited_wishes():
                session.last_wish_date = None
                WORLD.db.save_player_stats(session.player_id, last_wish_date=None)
            await send(session.ws, "ERROR", message="Your inventory is full — the well keeps your wish.")
            return
        result_text = f"You pull out a {ITEMS[item_id]['name']}!"

    elif kind == "gear":
        roll = random.random()
        if roll < 0.05:
            item_id = random.choice(WISH_MYTHOS_POOL)
            rare = True
        elif roll < 0.45:
            # Stronger mid-tier pull
            item_id = random.choice(WISH_GEAR_BETTER)
        else:
            item_id = random.choice(WISH_GEAR_POOL)
        if not WORLD.add_item_to_inventory(session, item_id, 1):
            if not session.has_unlimited_wishes():
                session.last_wish_date = None
                WORLD.db.save_player_stats(session.player_id, last_wish_date=None)
            await send(session.ws, "ERROR", message="Your inventory is full — the well keeps your wish.")
            return
        result_text = f"The well gives you a {ITEMS[item_id]['name']}!"
        if rare:
            await _broadcast_well_rare("gear", f"{session.char_name} found Mythos gear in the well!")

    else:  # gold
        # 40% pocket change, 35% a few hundred, 20% a modest purse, 5% a rare haul
        roll = random.random()
        if roll < 0.40:
            amount = random.randint(40, 120)
        elif roll < 0.75:
            amount = random.choice((200, 300, 400, 500))
        elif roll < 0.95:
            amount = 1000
        else:
            amount = 2500
            rare = True
        gained, left = WORLD.add_coins(session, amount)
        if left > 0:
            session.bank_coins = min(MAX_BANK_COINS, session.bank_coins + left)
            WORLD.db.save_player_stats(session.player_id, bank_coins=session.bank_coins)
            result_text = f"You wish for gold — {gained} fill your purse; {left} spill into the bank!"
        else:
            result_text = f"You wish for gold and receive {gained} coins!"
        if rare:
            await _broadcast_well_rare("gold", f"{session.char_name} hauled 2,500 coins from the well!")

    await send(session.ws, "CHAT_MSG", **{"from": "Wishing Well", "text": result_text})
    await send(session.ws, "WISH_RESULT", kind=kind, text=result_text, rare=rare)
    await send(session.ws, "PLAYER_UPDATE", player=session.full_state())


async def handle_wish_stat(session, msg):
    if not session.pending_wish_stat:
        await send(session.ws, "ERROR", message="No pending power wish.")
        return
    if not _near_wishing_well(session):
        await send(session.ws, "ERROR", message="Stand next to the Wishing Well.")
        return
    skill = (msg.get("skill") or "").strip().lower()
    if skill not in ("attack", "strength", "defence", "archery"):
        await send(session.ws, "ERROR", message="Choose attack, strength, defence, or archery.")
        return
    cur = session.level(skill)
    new_level = min(99, cur + 1)
    before_pool = session.max_hp()
    session.xp[skill] = combat.xp_for_level(new_level)
    col = f"{skill}_xp"
    gained = session.max_hp() - before_pool
    if gained > 0:
        session.hp += gained
    WORLD.db.save_player_stats(session.player_id, **{col: session.xp[skill], "hp": session.hp})
    session.pending_wish_stat = False
    text = f"Your {skill.title()} permanently rises to level {new_level}!"
    await send(session.ws, "CHAT_MSG", **{"from": "Wishing Well", "text": text})
    await send(session.ws, "WISH_RESULT", kind="power", text=text, rare=True, skill=skill, level=new_level)
    await send(session.ws, "PLAYER_UPDATE", player=session.full_state())


def chebyshev(ax, ay, bx, by):
    return max(abs(ax - bx), abs(ay - by))


def _ember_wyrm_can_hit(monster, px, py):
    """True/False when this is the static wyrm. None for every other monster.

    Outside the lair the fight is over, even on tiles that touch the body.
    """
    if getattr(monster, "type", None) != "emberdeep_wyrm":
        return None
    import emberdeep_creatures
    lair = (emberdeep_creatures.manifest().get("boss") or {}).get("lair") or {}
    px, py = int(px), int(py)
    if lair and not (lair["x0"] <= px <= lair["x1"] and lair["y0"] <= py <= lair["y1"]):
        return False
    cones = (monster.def_stats() or {}).get("cone_tiles")
    if not cones:
        return None
    body = emberdeep_creatures.footprint(monster.x, monster.y)
    return (px, py) in emberdeep_creatures.swing_tiles(cones, body)


def _release_monster_fight_on_step(session):
    """A step the player chose leaves a monster fight. Duels stay locked.

    Further steps keep the leave window open so the next tick cannot
    pull them back into swinging while they are still walking away.
    """
    if _combat_locked(session):
        return
    fighting = session.in_combat_with and session.in_combat_with[0] == "monster"
    fleeing = time.time() < float(getattr(session, "combat_flee_until", 0) or 0)
    if not fighting and not fleeing:
        return
    if fighting:
        session.in_combat_with = None
        session.combat_rounds = 0
        session.combat_lock_id = None
        session.pet_target_id = None
    session.combat_flee_until = time.time() + 1.0


def adjacent_or_same(ax, ay, bx, by):
    return chebyshev(ax, ay, bx, by) <= 1


async def handle_attack(session, msg):
    # A downed player must not be able to open a fight. HP only hits zero the
    # instant a killing blow lands, and the death handler resets it on the next
    # tick, so there is a window where a click could otherwise start combat.
    if session.hp <= 0:
        session.in_combat_with = None
        await send(session.ws, "ERROR", message="You're in no state to fight. Eat something first.")
        return
    target_id = msg.get("target_id")
    monster = None
    if session.dungeon:
        monster = session.dungeon["monsters"].get(target_id)
        if monster is None and target_id is not None:
            monster = session.dungeon["monsters"].get(int(target_id)) if str(target_id).isdigit() else None
    else:
        monster = WORLD.monsters.get(target_id)
        if monster is None and target_id is not None:
            try:
                monster = WORLD.monsters.get(int(target_id))
            except (TypeError, ValueError):
                monster = None
    # Resolve the target before complaining about gear. Checking the outfit
    # first meant clicking a monster that had already died told the player
    # "you can't fight dressed like this", which is both wrong and alarming.
    if monster is None or not monster.alive:
        await send(session.ws, "ERROR", message="That target isn't there.")
        return
    if not gear_rules.can_fight(session, ITEMS):
        session.in_combat_with = None
        await send(session.ws, "ERROR", message=gear_rules.NO_FIGHT_MSG)
        return
    mdef = monster.def_stats() or {}
    if mdef.get("requires_pk") and not session.player_killer:
        lines = mdef.get("pk_tutorial") or [
            "Switch to player killer mode before you can attack me.",
        ]
        await send(
            session.ws, "DIALOGUE",
            npc_id=monster.type, npc_name=mdef.get("name") or "Duelist", lines=lines,
        )
        return
    reach = session.attack_reach()
    # Side-by-side foes: allow engaging from nearby; strikes still require same row.
    if mdef.get("side_by_side"):
        reach = max(reach, int(mdef.get("attack_range") or 1))
    wyrm = _ember_wyrm_can_hit(monster, session.x, session.y)
    in_reach = wyrm if wyrm is not None else chebyshev(session.x, session.y, monster.x, monster.y) <= reach
    if not in_reach:
        await send(session.ws, "ERROR", message="You're too far away to attack.")
        return
    if session.using_bow():
        if not session.has_arrow_ammo():
            stored = session.quiver_total()
            has_quiver = WORLD.count_item(session, "arrow_quiver") > 0
            if stored and has_quiver:
                message = (
                    f"Your quiver holds {stored} arrows but is not equipped. "
                    "Open Bags and choose Equip on the Arrow Quiver."
                )
            elif stored:
                message = f"Your quiver holds {stored} arrows, but no Arrow Quiver is available to equip."
            else:
                message = "You need arrows in an equipped Arrow Quiver to shoot."
            await send(session.ws, "ERROR", message=message)
            return
    session.combat_flee_until = 0.0
    already = session.in_combat_with == ("monster", monster.id)
    session.in_combat_with = ("monster", monster.id)
    if not already:
        session.combat_rounds = 0
        session.combat_lock_id = monster.id
    session.pet_target_id = None if mdef.get("requires_pk") else monster.id
    if not mdef.get("passive") or mdef.get("strikes_in_place"):
        monster.target_player_id = session.player_id


PK_LOCK_SECONDS = 10 * 60


def _save_pk(session):
    WORLD.db.save_player_stats(
        session.player_id,
        player_killer=1 if session.player_killer else 0,
        pk_kills=int(session.pk_kills or 0),
        pk_locked_until=float(session.pk_locked_until or 0),
    )


def _note_pk_kill(session, monster):
    """Killing the training duelist counts as a player kill."""
    mdef = MONSTERS.get(getattr(monster, "type", ""), {}) or {}
    if not mdef.get("requires_pk"):
        return False
    session.pk_kills = int(getattr(session, "pk_kills", 0) or 0) + 1
    _save_pk(session)
    session._pk_notice = session.pk_kills
    return True


async def _credit_pk_kill(session, monster):
    if not _note_pk_kill(session, monster):
        return
    session._pk_notice = None
    await send(session.ws, "CHAT_MSG", **{
        "from": "Combat",
        "text": f"Player kill. You have {session.pk_kills}.",
    })
    await send(session.ws, "PLAYER_UPDATE", player=session.full_state())


async def _flush_pk_notices():
    for session in list(WORLD.sessions.values()):
        kills = getattr(session, "_pk_notice", None)
        if kills is None:
            continue
        session._pk_notice = None
        await send(session.ws, "CHAT_MSG", **{
            "from": "Combat",
            "text": f"Player kill. You have {kills}.",
        })
        await send(session.ws, "PLAYER_UPDATE", player=session.full_state())


async def handle_set_pk(session, msg):
    now = time.time()
    locked = float(getattr(session, "pk_locked_until", 0) or 0)
    if now < locked:
        left = int(locked - now)
        mins, secs = divmod(max(0, left), 60)
        await send(session.ws, "ERROR", message=f"Player killer mode is locked for {mins}:{secs:02d}.")
        return
    session.player_killer = not bool(session.player_killer)
    session.pk_locked_until = now + PK_LOCK_SECONDS
    if not session.player_killer and session.in_combat_with and session.in_combat_with[0] == "monster":
        mid = session.in_combat_with[1]
        foe = WORLD.monsters.get(mid)
        if foe and (foe.def_stats() or {}).get("requires_pk"):
            session.in_combat_with = None
    _save_pk(session)
    await send(session.ws, "PLAYER_UPDATE", player=session.full_state())
    if session.player_killer:
        text = "Player killer mode on for 10 minutes. Others see your PK status when they examine you."
    else:
        text = "Player killer mode off. You cannot change it again for 10 minutes."
    await send(session.ws, "CHAT_MSG", **{"from": "Combat", "text": text})


async def handle_stop_attack(session, msg):
    """Player clicked away — stop auto-swinging; dragon may still chase in its lair."""
    if _combat_locked(session):
        left = COMBAT_LOCK_ROUNDS - _combat_rounds(session)
        await send(
            session.ws, "ERROR",
            message=f"You cannot run yet. {left} round{'s' if left != 1 else ''} of fighting left.",
        )
        return
    session.in_combat_with = None
    session.combat_rounds = 0
    session.combat_lock_id = None
    session.pet_target_id = None
    # Brief window so force_retaliate mobs don't instantly re-lock
    session.combat_flee_until = time.time() + 1.0


COMBAT_STYLES = ("attack", "strength", "defence", "archery")


async def handle_set_combat_style(session, msg):
    style = (msg.get("style") or "").lower().strip()
    if style == "hitpoints":
        await send(
            session.ws, "ERROR",
            message="Hitpoints follows your three highest combat skills. Train Attack, Strength, Defence, or Archery.",
        )
        return
    if style not in COMBAT_STYLES:
        await send(session.ws, "ERROR", message="Choose Attack, Strength, Defence, or Archery.")
        return
    if session.using_bow():
        if style != "archery":
            await send(
                session.ws, "ERROR",
                message="A bow is equipped — only the Archery fighting style is available. Unequip the bow for melee styles.",
            )
            return
    elif style == "archery":
        await send(session.ws, "ERROR", message="Equip a bow to use the Archery fighting style.")
        return
    if style in ("attack", "strength", "defence"):
        session.melee_style = style
    session.combat_style = style
    await send(session.ws, "PLAYER_UPDATE", player=session.full_state())
    await send(
        session.ws, "CHAT_MSG",
        **{"from": "Combat", "text": f"Fighting style: {style.title()} — XP goes to {style.title()}."},
    )


def _magic_cooldown_secs(ability, manual):
    base = float(ability.get("cooldown") or 8.0)
    if manual:
        return base * float(MANUAL_MAGIC_CD_FACTOR)
    return base


def _session_combat_target(session):
    """Return the MonsterInstance the player is currently fighting, or None."""
    if not session.in_combat_with or session.in_combat_with[0] != "monster":
        return None
    mid = session.in_combat_with[1]
    if session.dungeon:
        return session.dungeon["monsters"].get(mid)
    return WORLD.monsters.get(mid)


def apply_magic_cast(session, ability_id, monster, manual, events, dungeon_tag=None):
    """
    Apply a quest-magic ability to monster. Returns (ok, error_message).
    Appends COMBAT_EVENT / MAGIC_CAST / death events as needed.
    """
    ab = MAGIC_ABILITIES.get(ability_id)
    if not ab:
        return False, "Unknown magic ability."
    qp = session.quest_points()
    need = int(ab.get("quest_points") or 0)
    if qp < need:
        return False, f"Need {need} quest points (you have {qp})."
    now = time.time()
    ready_at = float(session.magic_ready_at.get(ability_id) or 0)
    if ready_at > now:
        return False, f"{ab['name']} is on cooldown ({ready_at - now:.1f}s)."
    if not monster or not monster.alive:
        return False, "No target."
    reach = session.attack_reach()
    wyrm = _ember_wyrm_can_hit(monster, session.x, session.y)
    in_reach = wyrm if wyrm is not None else chebyshev(session.x, session.y, monster.x, monster.y) <= reach
    if not in_reach:
        return False, "Too far away."

    dmg = max(0, int(ab.get("damage") or 0))
    freeze = float(ab.get("freeze") or 0)
    effect = ab.get("effect") or "lightning"
    if session.dungeon and session.dungeon.get("v2"):
        import void_v2
        dmg = void_v2.mitigate(session, monster, dmg)
    monster.hp = max(0, monster.hp - dmg)
    if not (monster.def_stats() or {}).get("requires_pk"):
        session.pet_target_id = monster.id
    if freeze > 0:
        monster.frozen_until = max(float(monster.frozen_until or 0), now + freeze)

    cd = _magic_cooldown_secs(ab, manual=manual)
    session.magic_ready_at[ability_id] = now + cd

    cast_ev = {
        "caster_id": session.player_id,
        "target_id": monster.id,
        "ability_id": ability_id,
        "name": ab["name"],
        "effect": effect,
        "damage": dmg,
        "freeze": freeze,
        "manual": bool(manual),
        "defender_hp": monster.hp,
        "defender_max_hp": monster.max_hp,
    }
    if dungeon_tag:
        cast_ev["_dungeon_player"] = dungeon_tag
    events.append({"type": "MAGIC_CAST", "data": cast_ev})

    if dmg > 0:
        hit_ev = {
            "attacker_id": session.player_id, "defender_id": monster.id, "damage": dmg,
            "hit": True, "defender_hp": monster.hp, "defender_max_hp": monster.max_hp,
            "kind": "player_magic_monster",
            "ranged": bool(session.using_bow()),
            "magic_effect": effect,
        }
        if dungeon_tag:
            hit_ev["_dungeon_player"] = dungeon_tag
        events.append({"type": "COMBAT_EVENT", "data": hit_ev})

    return True, None


async def resolve_magic_kill(session, monster, events, dungeon_tag=None):
    """Shared death/loot path after magic (or other) finishes a monster."""
    if monster.hp > 0:
        return
    _mark_monster_dead(monster)
    await _credit_pk_kill(session, monster)
    if session.in_combat_with == ("monster", monster.id):
        session.in_combat_with = None
    if not session.dungeon:
        drops = WORLD.drop_loot(monster.x, monster.y, drops_for_kill(monster.type))
        events.append({"type": "DEATH", "data": {"entity_id": monster.id, "entity_kind": "monster"}})
        if drops:
            events.append({"type": "LOOT_DROPPED", "data": {"x": monster.x, "y": monster.y, "items": drops}})
            await vacuum_ground_loot(session)
        check_quest_progress_on_kill(session, monster.type)
    else:
        events.append({
            "type": "DEATH",
            "data": {"entity_id": monster.id, "entity_kind": "monster", "_dungeon_player": dungeon_tag},
        })
        await _finish_dungeon_kill(session, monster)


async def handle_cast_magic(session, msg):
    ability_id = (msg.get("ability_id") or "").strip()
    if ability_id not in MAGIC_ABILITIES:
        await send(session.ws, "ERROR", message="Unknown magic ability.")
        return
    monster = _session_combat_target(session)
    if monster is None:
        await send(session.ws, "ERROR", message="Attack a monster before casting magic.")
        return
    dungeon_tag = session.player_id if session.dungeon else None
    events = []
    ok, err = apply_magic_cast(session, ability_id, monster, manual=True, events=events, dungeon_tag=dungeon_tag)
    if not ok:
        await send(session.ws, "ERROR", message=err or "Cannot cast.")
        return
    await resolve_magic_kill(session, monster, events, dungeon_tag=dungeon_tag)
    for ev in events:
        data = dict(ev["data"])
        if data.get("_dungeon_player"):
            pid = data.pop("_dungeon_player")
            target = WORLD.sessions.get(pid)
            if target:
                await send(target.ws, ev["type"], **data)
        else:
            await broadcast(ev["type"], **data)
    await send(session.ws, "PLAYER_UPDATE", player=session.full_state())


async def handle_set_magic_mode(session, msg):
    if "auto" in msg:
        session.magic_auto = bool(msg.get("auto"))
    await send(session.ws, "PLAYER_UPDATE", player=session.full_state())
    mode = "Auto" if session.magic_auto else "Manual"
    tip = (
        "abilities cast themselves in combat (longer cooldown)."
        if session.magic_auto else
        "tap ability buttons while fighting (shorter cooldown)."
    )
    await send(
        session.ws, "CHAT_MSG",
        **{"from": "Magic", "text": f"{mode} magic — {tip}"},
    )


def try_auto_magic(session, primary, events, dungeon_tag=None):
    """Cast the strongest ready unlocked ability (auto mode only)."""
    if not session.magic_auto or primary is None or not primary.alive:
        return
    now = time.time()
    qp = session.quest_points()
    for aid in MAGIC_ABILITY_ORDER:
        ab = MAGIC_ABILITIES.get(aid)
        if not ab:
            continue
        if qp < int(ab.get("quest_points") or 0):
            continue
        if float(session.magic_ready_at.get(aid) or 0) > now:
            continue
        ok, _ = apply_magic_cast(session, aid, primary, manual=False, events=events, dungeon_tag=dungeon_tag)
        if ok:
            return


async def handle_gather(session, msg):
    if session.dungeon:
        await send(session.ws, "ERROR", message="There's nothing to gather in the cave.")
        return
    if getattr(session, "last_gather_tick", None) == WORLD.tick_count:
        # One start per tick, but say so. Returning silently made a fast second
        # click look like a dropped input, especially when switching straight
        # from a tree to a rock.
        await send(session.ws, "ERROR", message="You are already gathering — give it a moment.")
        return
    session.last_gather_tick = WORLD.tick_count
    x, y = msg.get("x"), msg.get("y")
    node = WORLD.resource_nodes.get((x, y))
    if node is None or node["depleted"]:
        await send(session.ws, "ERROR", message="There's nothing to gather there.")
        return
    if not adjacent_or_same(session.x, session.y, x, y):
        await send(session.ws, "ERROR", message="You're too far away.")
        return
    yield_def = RESOURCE_YIELDS[node["type"]]
    if session.level(yield_def["skill"]) < yield_def["level_req"]:
        await send(session.ws, "ERROR", message=f"You need {yield_def['skill']} level {yield_def['level_req']} for this.")
        return
    skill = yield_def["skill"]
    allowed = yield_def.get("tools")
    if skill in ("woodcutting", "mining", "fishing"):
        if not WORLD.has_gather_tool(session, skill, allowed_tools=allowed):
            if allowed:
                names = [ITEMS[t]["name"] for t in allowed if t in ITEMS]
                need = names[0] if len(names) == 1 else " or ".join(names)
                await send(session.ws, "ERROR", message=f"Equip a {need} to fish this spot.")
            else:
                tool_name = {"woodcutting": "an axe", "mining": "a pickaxe", "fishing": "a fishing tool"}.get(skill)
                await send(session.ws, "ERROR", message=f"Equip {tool_name} to do that (click it in your bag).")
            return
    session.gathering_node = (x, y)
    label = yield_def.get("cast") or {
        "woodcutting": "You swing your axe at the tree...",
        "mining": "You swing your pickaxe at the rock...",
        "fishing": "You cast your net...",
    }.get(skill, "You start gathering...")
    await send(session.ws, "CHAT_MSG", **{"from": "You", "text": label})


async def handle_craft(session, msg):
    recipe_id = msg.get("recipe_id")
    recipe = CRAFT_RECIPES.get(recipe_id)
    if not recipe:
        await send(session.ws, "ERROR", message="Unknown recipe.")
        return
    category = recipe.get("category")
    # Smelt at furnace, smith at anvil, cook at a hearth/range or campfire,
    # fletch anywhere with a knife in inventory.
    if category == "smelt":
        needed_kinds = ("furnace",)
        where = "the furnace"
    elif category == "smith":
        needed_kinds = ("anvil",)
        where = "the anvil"
    elif category == "cook":
        needed_kinds = ("range", "fireplace")
        where = "a cooking fire"
    elif category == "fletch":
        needed_kinds = ()
        where = None
    else:
        await send(session.ws, "ERROR", message="You can't make that here.")
        return
    near_station = False
    if category == "cook":
        near_station = WORLD.near_cook_spot(session)
    elif category == "fletch":
        if not WORLD.has_gather_tool(session, "fletching"):
            await send(session.ws, "ERROR", message="You need a knife to fletch.")
            return
        near_station = True
    else:
        for spot in INTERACTABLES:
            if spot["kind"] in needed_kinds and adjacent_or_same(session.x, session.y, spot["x"], spot["y"]):
                near_station = True
                break
    if not near_station:
        await send(session.ws, "ERROR", message=f"Stand next to {where}.")
        return
    skill = recipe["skill"]
    cook_lvl = session.level(skill)
    if cook_lvl < recipe["level_req"]:
        await send(
            session.ws, "ERROR",
            message=f"You need {skill} level {recipe['level_req']} for that.",
        )
        return

    # How many times to craft (cook-all / multi-drop style). Fletch allows multi too.
    try:
        want = max(1, int(msg.get("qty") or 1))
    except (TypeError, ValueError):
        want = 1
    if category not in ("cook", "fletch"):
        want = 1
    # Cap by input availability
    max_by_inputs = want
    for item_id, need in recipe["inputs"].items():
        have = session.available_craft_input(item_id)
        max_by_inputs = min(max_by_inputs, have // max(1, need))
    want = max(0, max_by_inputs)
    if want < 1:
        need_msg = ", ".join(f"{n}x {ITEMS[i]['name']}" for i, n in recipe["inputs"].items())
        await send(session.ws, "ERROR", message=f"You need {need_msg}.")
        return

    cooked_ok = 0
    burnt_count = 0
    last_out = None
    total_xp = 0
    leveled = False
    final_level = cook_lvl

    for _ in range(want):
        for item_id, need in recipe["inputs"].items():
            if session.available_craft_input(item_id) < need:
                want = cooked_ok + burnt_count  # stop early
                break
        else:
            out_id, out_qty = recipe["output"]
            burnt = False
            if category == "cook" and recipe.get("burnt"):
                chance = cook_burn_chance(cook_lvl, recipe["level_req"])
                if chance > 0 and random.random() < chance:
                    out_id, out_qty = recipe["burnt"]
                    burnt = True
            for item_id, need in recipe["inputs"].items():
                session.consume_craft_input(item_id, need)
            if not WORLD.add_item_to_inventory(session, out_id, out_qty):
                for item_id, need in recipe["inputs"].items():
                    session.refund_craft_input(item_id, need)
                await send(session.ws, "ERROR", message="Your inventory is full.")
                break
            last_out = out_id
            if burnt:
                burnt_count += 1
            else:
                cooked_ok += 1
                before, after = WORLD.grant_xp(session, skill, recipe["xp"])
                total_xp += recipe["xp"]
                final_level = after
                if after > before:
                    leveled = True
                    cook_lvl = after
            continue
        break

    await send(session.ws, "PLAYER_UPDATE", player=session.full_state())
    if total_xp > 0:
        await send(
            session.ws, "SKILL_XP",
            player_id=session.player_id, skill=skill, gained=total_xp,
            xp=session.xp[skill], level=final_level, leveled_up=leveled,
        )

    source = "Kitchen" if category == "cook" else "Forge"
    if category == "cook":
        parts = []
        if cooked_ok:
            parts.append(f"cook {cooked_ok} {ITEMS[recipe['output'][0]]['name']}")
        if burnt_count:
            burnt_name = ITEMS.get((recipe.get("burnt") or (None, None))[0], {}).get("name", "burnt food")
            parts.append(f"burn {burnt_count} ({burnt_name})")
        if parts:
            await send(session.ws, "CHAT_MSG", **{"from": source, "text": "You " + " and ".join(parts) + "."})
        elif last_out is None and want < 1:
            pass
    elif last_out:
        await send(
            session.ws, "CHAT_MSG",
            **{"from": source, "text": f"You make {ITEMS[last_out]['name']}."},
        )


async def light_fire(session, log_item_id):
    """Light a campfire on the player's tile using a tinderbox + logs."""
    info = FIRE_LOGS.get(log_item_id)
    if not info:
        await send(session.ws, "ERROR", message="You can't light that.")
        return
    if WORLD.count_item(session, "tinderbox") < 1:
        await send(session.ws, "ERROR", message="You need a tinderbox to light a fire.")
        return
    if session.available_craft_input(log_item_id) < 1:
        await send(session.ws, "ERROR", message=f"You need {ITEMS[log_item_id]['name']}.")
        return
    if not is_walkable(WORLD.grid, session.x, session.y):
        await send(session.ws, "ERROR", message="You can't light a fire here.")
        return
    key = (session.x, session.y)
    if key in WORLD.fires:
        await send(session.ws, "ERROR", message="There's already a fire here.")
        return
    session.consume_craft_input(log_item_id, 1)
    WORLD.fires[key] = WORLD.tick_count + info["duration"]
    await send(session.ws, "PLAYER_UPDATE", player=session.full_state())
    await send(
        session.ws, "CHAT_MSG",
        **{"from": "You", "text": f"You light the {ITEMS[log_item_id]['name'].lower()} and a fire springs up."},
    )


def _parse_teleport_marks(raw):
    """JSON list of destination ids the player has unlocked."""
    if isinstance(raw, (list, tuple)):
        vals = raw
    else:
        try:
            vals = json.loads(raw or "[]")
        except (TypeError, ValueError, json.JSONDecodeError):
            vals = []
    known = {d["id"] for d in TELEPORT_DESTINATIONS}
    out = []
    seen = set()
    for item in vals:
        mid = str(item or "")
        if mid in known and mid not in seen:
            seen.add(mid)
            out.append(mid)
    return out


def _save_teleport_marks(session):
    WORLD.db.save_player_stats(
        session.player_id, teleport_marks=json.dumps(list(session.teleport_marks)),
    )


def _grant_teleport_marks(session, mark_ids):
    """Add marks; return newly granted destination dicts (for chat)."""
    known = {d["id"]: d for d in TELEPORT_DESTINATIONS}
    have = set(session.teleport_marks)
    newly = []
    for mid in mark_ids:
        if mid in have or mid not in known:
            continue
        session.teleport_marks.append(mid)
        have.add(mid)
        newly.append(known[mid])
    if newly:
        _save_teleport_marks(session)
    return newly


def _teleport_plane(session):
    """Map plane used for discovery, or None inside unrelated instances."""
    data = session.dungeon
    if data and data.get("id") == "castle_realm":
        return "castle"
    if data:
        return None
    return "overworld"


def _discover_teleport_marks(session):
    """Unlock teleport landings the player has walked near. Returns new dests."""
    plane = _teleport_plane(session)
    if plane is None:
        return []
    have = set(session.teleport_marks)
    found = []
    for dest in TELEPORT_DESTINATIONS:
        if dest["id"] in have:
            continue
        if dest.get("where") != plane:
            continue
        if max(abs(session.x - int(dest["x"])), abs(session.y - int(dest["y"]))) <= TELEPORT_DISCOVER_RADIUS:
            found.append(dest["id"])
    return _grant_teleport_marks(session, found)


async def _notify_teleport_marks(session, newly):
    if not newly:
        return
    # Marks still save before the spell is taught; only announce once Elowen has.
    if session.knows_teleport:
        for dest in newly:
            await send(
                session.ws, "CHAT_MSG",
                **{"from": "You", "text": f"You mark {dest['label']} on your teleport spell."},
            )
    await send(session.ws, "PLAYER_UPDATE", player=session.full_state())


def _teleport_unlocked(session, dest_id):
    if dest_id == "home":
        return True
    return dest_id in set(session.teleport_marks)


def _teleport_dest(dest_id, session=None):
    if dest_id == "home" and session is not None and feature_flags.USE_PLAYER_HOUSING:
        home = _housing.home_info(WORLD.db.conn, session.player_id)
        if home:
            return {
                "id": "home",
                "label": f"My Home ({home['name']})",
                "blurb": home["blurb"],
                "where": "overworld",
                "x": home["x"],
                "y": home["y"],
            }
    for dest in TELEPORT_DESTINATIONS:
        if dest["id"] == dest_id:
            return dest
    return None


def _drop_instance(session):
    """Leave a dungeon or the castle realm without the usual farewell chat."""
    data = session.dungeon
    if not data:
        return False
    if data.get("id") == "castle_realm":
        import castle_realm
        castle_realm.leave(session)
        return True
    if data.get("v2"):
        import void_v2
        void_v2.strip_keys(session)
    session.dungeon = None
    session.in_combat_with = None
    session.pet_target_id = None
    session.gathering_node = None
    return True


def _open_arrival(x, y, walk_fn, session):
    """Nearest walkable tile that is not already occupied on the overworld."""
    for radius in range(0, 3):
        for dy in range(-radius, radius + 1):
            for dx in range(-radius, radius + 1):
                if max(abs(dx), abs(dy)) != radius:
                    continue
                nx, ny = x + dx, y + dy
                if not walk_fn(nx, ny):
                    continue
                if WORLD.occupied(nx, ny, session.player_id):
                    continue
                return nx, ny
    return None


async def handle_teleport(session, msg):
    if not session.knows_teleport:
        await send(session.ws, "ERROR", message="Speak with Wizard Elowen first. She stands northwest of the village crossroads.")
        return
    if session.in_combat_with:
        await send(session.ws, "ERROR", message="You can't teleport during a fight.")
        return
    if session.hp <= 0:
        await send(session.ws, "ERROR", message="You can't teleport right now.")
        return
    now = time.time()
    if now < session.teleport_ready_at:
        await send(session.ws, "ERROR", message="The spell is still settling.")
        return
    dest_id = msg.get("dest")
    dest = _teleport_dest(dest_id, session)
    if dest is None:
        if dest_id == "home":
            await send(session.ws, "ERROR", message="You don't own a home yet. Speak to Estate Agent Mira.")
        else:
            await send(session.ws, "ERROR", message="That place isn't marked.")
        return
    if not _teleport_unlocked(session, dest["id"]):
        await send(
            session.ws, "ERROR",
            message="You haven't explored that place yet. Walk there to mark it on your spell.",
        )
        return
    label = dest["label"]
    tx, ty = int(dest["x"]), int(dest["y"])
    was_inside = bool(session.dungeon)
    if dest["where"] == "castle":
        if not feature_flags.USE_CASTLE_REALM:
            await send(session.ws, "ERROR", message="The Castle Realm is closed.")
            return
        import castle_realm
        if not castle_realm.walkable("realm", tx, ty):
            await send(session.ws, "ERROR", message="That castle landing is blocked.")
            return
        fresh = not session.dungeon or session.dungeon.get("id") != "castle_realm"
        if session.dungeon and session.dungeon.get("id") != "castle_realm":
            _drop_instance(session)
        if fresh:
            castle_realm.enter(session)
        plane_changed = session.dungeon.get("plane") != "realm"
        if plane_changed:
            castle_realm.move_to_plane(session, "realm", (tx, ty))
        else:
            session.x, session.y = tx, ty
        session.in_combat_with = None
        session.pet_target_id = None
        session.gathering_node = None
        session.house_level = 0
        _bring_pet(session)
        if fresh:
            await send(session.ws, "DUNGEON_ENTER", **castle_realm.payload(session))
            import castle_owners
            await castle_owners.send_state(session)
        elif plane_changed:
            await send(session.ws, "REALM_PLANE", **castle_realm.payload(session))
    else:
        spot = _open_arrival(tx, ty, lambda x, y: is_walkable(WORLD.grid, x, y), session)
        if spot is None:
            await send(session.ws, "ERROR", message="That place is too crowded.")
            return
        if was_inside:
            _drop_instance(session)
        session.x, session.y = spot
        session.in_combat_with = None
        session.pet_target_id = None
        session.gathering_node = None
        session.house_level = 0
        _bring_pet(session)
        WORLD.db.save_player_position(session.player_id, session.x, session.y)
        if was_inside:
            await send(session.ws, "DUNGEON_EXIT", x=session.x, y=session.y, map="overworld")
    session.teleport_ready_at = now + 1.2
    arrived = "castle" if dest["where"] == "castle" else "overworld"
    await send(session.ws, "TELEPORT", x=session.x, y=session.y, label=label, map=arrived)
    await send(session.ws, "PLAYER_UPDATE", player=session.full_state())
    await send(session.ws, "CHAT_MSG", **{"from": "You", "text": f"You teleport to {label}."})
    await _notify_teleport_marks(session, _discover_teleport_marks(session))


async def handle_talk(session, msg):
    npc_id = msg.get("npc_id")
    import castle_owners
    if castle_owners.is_seller(npc_id):
        await castle_owners.open_talk(session, npc_id)
        return
    npc = NPC_BY_ID.get(npc_id)
    if npc is None:
        return
    if not adjacent_or_same(session.x, session.y, npc["x"], npc["y"]):
        await send(session.ws, "ERROR", message="You're too far away to talk to them.")
        return
    if reputation.first_talk_today(WORLD.db.conn, session.player_id, npc_id):
        await social_event(session, "talk", xp={"charisma": reputation.CHARISMA_TALK_XP})
    if npc.get("welcome_guide"):
        await welcome_talk(session, npc)
        return
    if npc_id in ("old_king_prisoner", "old_king_aldous", "keeper_records"):
        conn = WORLD.db.conn
        opts = None
        if npc_id == "old_king_prisoner":
            lines = ruling.king_visit_line(conn, session.player_id)
            if ruling.role(conn, session.player_id) == "Monarch":
                opts = [{"id": "king_free", "label": f"Free him ({ruling.FREE_KING_COST:,} from the treasury)"}]
        elif npc_id == "old_king_aldous":
            import random as _r
            lines = [_r.choice(ruling.ADVISOR_TIPS)]
            got = ruling.counsel(conn, session.player_id)
            if got:
                WORLD.grant_xp(session, "charisma", got)
                lines.append(f"(His counsel: +{got} Charisma XP.)")
        else:
            lines = ruling.reign_lines(conn) or ["The records are empty."]
        await send(session.ws, "DIALOGUE", npc_id=npc_id, npc_name=npc["name"], lines=lines, options=opts)
        return
    import fairy_village
    if npc_id in fairy_village.FAIRY_NPCS:
        await fairy_village.open_talk(session, npc)
        return
    if npc_id == WIZARD_ID:
        if not session.knows_teleport:
            session.knows_teleport = True
            WORLD.db.save_player_stats(session.player_id, knows_teleport=1)
        newly = _grant_teleport_marks(session, TELEPORT_STARTER_MARKS)
        # Also mark anywhere they're standing near when they learn the spell.
        newly.extend(_discover_teleport_marks(session))
        await send(session.ws, "DIALOGUE", npc_id=npc["id"], npc_name=npc["name"],
                   lines=npc["lines"], teleport=True)
        await send(session.ws, "PLAYER_UPDATE", player=session.full_state())
        for dest in newly:
            if dest["id"] in TELEPORT_STARTER_MARKS:
                continue
            await send(
                session.ws, "CHAT_MSG",
                **{"from": "You", "text": f"You mark {dest['label']} on your teleport spell."},
            )
        return
    check_quest_progress_on_talk(session, npc_id)
    # Collect quests can become ready just from carrying items
    if refresh_collect_quest_status(session):
        session.quest_log_dirty = True

    quest_id, qdef, prog = pick_npc_quest(session, npc)
    quest_info = None
    if quest_id and qdef:

        def _quest_payload(state):
            return {
                "quest_id": quest_id,
                "name": qdef["name"],
                "description": qdef["description"],
                "state": state,
                "objective": quest_objective_line(session, qdef, prog),
                "quest_points": int(qdef.get("quest_points") or 0),
                "rewards": qdef.get("rewards") or {},
            }

        if qdef.get("type") == "gift":
            # One-time lesson / starter kit — grant on first talk
            if prog is None or prog.get("status") != "complete":
                need_slots = reward_inv_slots_needed(session, qdef.get("rewards") or {})
                free = INVENTORY_SIZE - len(session.inventory)
                if free < need_slots:
                    await send(
                        session.ws, "CHAT_MSG",
                        **{
                            "from": npc["name"],
                            "text": (
                                f"Your pack is too full for my starter kit "
                                f"(need {need_slots} free slots). Bank some items and talk again!"
                            ),
                        },
                    )
                    quest_info = _quest_payload("offerable")
                else:
                    await grant_quest_rewards(session, qdef.get("rewards") or {})
                    session.quests[quest_id] = {"status": "complete", "progress": 1}
                    WORLD.db.set_quest_progress(session.player_id, quest_id, "complete", 1)
                    # Pack starter bronze arrows into the new quiver if present
                    if WORLD.count_item(session, "arrow_quiver") > 0:
                        session.deposit_arrows_to_quiver("bronze_arrow", 50)
                        # The starter kit is immediately usable: players should
                        # not need to discover an ammo-slot toggle before their
                        # first bow shot.
                        if not session.equipment.get("ammo"):
                            qslot = next(
                                (slot for slot, entry in session.inventory.items()
                                 if entry and entry.get("item_id") == "arrow_quiver"),
                                None,
                            )
                            if qslot is not None:
                                await handle_equip(session, {"slot_index": qslot})
                    if WORLD.count_item(session, "arrowtip_box") > 0:
                        session.deposit_tips_to_box("bronze_arrowtips", 30)
                    qp = session.quest_points()
                    qp_gain = int(qdef.get("quest_points") or 0)
                    await send(
                        session.ws, "QUEST_COMPLETE",
                        quest_id=quest_id, rewards=qdef.get("rewards") or {},
                        quest_points=qp_gain, total_quest_points=qp,
                    )
                    await send(session.ws, "QUEST_LOG", quests={qid: quest_status_for(session, qid) for qid in QUESTS})
                    session.quest_log_dirty = False
                    await send(session.ws, "PLAYER_UPDATE", player=session.full_state())
                    await send(
                        session.ws, "CHAT_MSG",
                        **{
                            "from": npc["name"],
                            "text": (
                                "Here's a starter kit — knife, logs, feathers, shafts, tips, "
                                "bowstring, a shortbow, bronze arrows, an Arrow Quiver, and an "
                                "Arrowtip Box. Equip the quiver and bow, then press N with the knife to fletch more!"
                            ),
                        },
                    )
                    if qp_gain:
                        await send(session.ws, "CHAT_MSG", **{
                            "from": "Magic",
                            "text": f"+{qp_gain} quest point{'s' if qp_gain != 1 else ''} (total {qp}). Check the Magic tab.",
                        })
                    prog = session.quests[quest_id]
                    quest_info = _quest_payload("complete")
            else:
                quest_info = _quest_payload("complete")
        elif prog is None:
            quest_info = _quest_payload("offerable")
        elif prog["status"] == "active":
            quest_info = _quest_payload("active")
        elif prog["status"] == "ready":
            quest_info = _quest_payload("ready")
        else:
            quest_info = _quest_payload("complete")

    hello = reputation.greeting(session.reputation)
    title_hello = nobility.address(getattr(session, "noble_rank", 0), session.gender)
    if title_hello:
        hello = f"{hello} {title_hello}".strip() if hello else title_hello
    persuade = npc.get("persuade")
    npc_lines = [outfits.mae_line(session)] if npc_id == "outfitter_mae" else list(npc["lines"])
    await send(
        session.ws, "DIALOGUE", npc_id=npc_id, npc_name=npc["name"],
        lines=([hello] if hello else []) + npc_lines,
        shop_id=npc.get("shop_id"), quest=quest_info, forge=bool(npc.get("forge")),
        bank=bool(npc.get("bank")), housing=bool(npc.get("housing")),
        persuade={"req": int(persuade["req"])} if persuade else None,
        options=_options_for(session, npc),
    )
    if session.quest_log_dirty:
        session.quest_log_dirty = False
        await send(
            session.ws, "QUEST_LOG",
            quests={qid: quest_status_for(session, qid) for qid in QUESTS},
        )
    if npc.get("shop_id"):
        await send_shop_state(session, npc["shop_id"])


def _work_state(player_id):
    try:
        conn = WORLD.db.conn
        return {"job": apprentice.status(conn, player_id), "property": _property.status(conn, player_id)}
    except Exception:
        return None


def _sync_bank(player_id, value):
    s = WORLD.sessions.get(player_id)
    if s is not None:
        s.bank_coins = int(value)


apprentice.set_bank_hook(_sync_bank)


async def settle_work(session, login=False):
    """Apprentice shifts, property worker income and property land fees (phase 4)."""
    conn = WORLD.db.conn
    changed = False
    r = apprentice.settle(conn, session, grant_xp=WORLD.grant_xp)
    if r and r["shifts"]:
        changed = True
        await send(session.ws, "CHAT_MSG", **{"from": "Apprentice", "text": apprentice.message(r)})
        await social_event(
            session, "apprentice", rep=apprentice.REP_PER_SHIFT * r["shifts"],
            rep_cap_key="rep_shift", rep_cap=apprentice.REP_SHIFT_DAILY_CAP,
            xp={"etiquette": apprentice.ETIQUETTE_PER_SHIFT * r["shifts"]},
            xp_cap_key="fee_xp", xp_cap=reputation.ETIQUETTE_FEE_DAILY_CAP,
        )
    if r and r["skipped"]:
        await send(session.ws, "CHAT_MSG", **{"from": "Apprentice",
                   "text": f"Your master couldn't pay {r['skipped']} shift(s), so they went unpaid."})
    inc = _property.settle_income(conn, session.player_id)
    if inc:
        changed = True
        if inc["shifts"]:
            await send(session.ws, "CHAT_MSG", **{"from": "Property", "text": _property.income_message(inc)})
        if inc["skipped"]:
            await send(session.ws, "CHAT_MSG", **{"from": "Property",
                       "text": f"Your bank couldn't cover {inc['skipped']} worker wage(s); those shifts were skipped."})
    purse, bank, fees = _property.settle_land_fee_rows(
        conn, session.player_id, int(session.coins), int(session.bank_coins))
    if fees:
        changed = True
        if (purse, bank) != (session.coins, session.bank_coins):
            session.coins, session.bank_coins = purse, bank
            WORLD.db.save_player_stats(session.player_id, coins=purse, bank_coins=bank)
        for kind, paid, days in fees:
            fee = _property.land_fee(kind)
            missed = min(days, royal_treasury.LAND_FEE_MAX_DAYS) - paid
            await social_event(
                session, "land_fee",
                rep=reputation.REP_LAND_FEE_PAID * paid + reputation.REP_LAND_FEE_MISSED * missed,
                xp={"etiquette": reputation.ETIQUETTE_FEE_XP * paid} if paid else None,
                xp_cap_key="fee_xp", xp_cap=reputation.ETIQUETTE_FEE_DAILY_CAP,
            )
            text = (f"The King's land fee of {fee * paid:,} coins for your {_property.kind_name(kind).lower()} is paid."
                    if paid else
                    f"You couldn't cover the King's land fee for your {_property.kind_name(kind).lower()}. No debt is kept.")
            await send(session.ws, "CHAT_MSG", **{"from": "Royal Tax Collector", "text": text})
    if changed:
        await send(session.ws, "PLAYER_UPDATE", player=session.full_state())


async def ruling_daily_tick(now=None):
    """Once per real day: pending rates apply, stipends, council rep, works expire, reign days."""
    now = time.time() if now is None else now
    conn = WORLD.db.conn
    day = time.strftime("%Y-%m-%d", time.localtime(now))
    row = conn.execute("SELECT value FROM realm_settings WHERE key = 'daily:last'").fetchone()
    last = None if row is None else time.strftime("%Y-%m-%d", time.localtime(float(row[0])))
    ruling.update_days(conn, now)
    if last == day:
        return
    conn.execute("INSERT OR REPLACE INTO realm_settings (key, value, changed_at) VALUES ('daily:last', ?, ?)", (now, now))
    conn.commit()
    for key, old, new, actor in ruling.apply_pending(conn, now):
        await broadcast("CHAT_MSG", **{"from": "Royal Herald", "text":
                        f"By royal decree, {ruling.setting_label(key)} is now {ruling._fmt(key, new)}."})
        politics.news(conn, "decree", f"By royal decree, {ruling.setting_label(key)} is now {ruling._fmt(key, new)}.", now)
        live = WORLD.sessions.get(int(actor)) if actor else None
        if live and ruling.role(conn, actor) == "Monarch":
            await social_event(live, "tax_change", rep=ruling.REP_TAX_RAISE if new > old else ruling.REP_TAX_CUT)
    _paid, _skipped = ruling.pay_stipends(conn, now)
    old_band = politics.mood_band(conn)
    _v, band, _parts, ev = politics.daily_mood_tick(conn, now, len(_skipped))
    if band != old_band:
        await broadcast("CHAT_MSG", **{"from": "Town Crier", "text": f"The kingdom's mood turns: {band}."})
    if ev:
        await court_event_notify()
    for s_ in WORLD.sessions.values():
        row = conn.execute("SELECT reputation FROM players WHERE id = ?", (s_.player_id,)).fetchone()
        if row:
            s_.reputation = int(row[0] or 0)
        s_.bank_coins = apprentice.bank_get(conn, s_.player_id)
    ruling._snapshot(conn, now)
    conn.commit()


# ---- dev commands (testing only; the "david" account, nobody else) -----------------------------
DEV_ACCOUNT = "david"
DEV_SKIP_MAX_HOURS = 24 * 30
_DEV_TIME_COLS = ("since", "ts", "last_settled", "last_income_settled", "land_fee_paid_through",
                  "last_petition_refused")


def _is_dev(session):
    return (getattr(session, "username", "") or "").strip().lower() == DEV_ACCOUNT


def dev_shift_time(conn, seconds):
    """Move every stored timestamp back, as if `seconds` had passed. Returns rows touched."""
    touched = 0
    for (table,) in conn.execute("SELECT name FROM sqlite_master WHERE type = 'table'").fetchall():
        if table.startswith("sqlite_"):
            continue
        for col in [r[1] for r in conn.execute(f'PRAGMA table_info("{table}")')]:
            if col.endswith("_at") or col in _DEV_TIME_COLS:
                cur = conn.execute(f'UPDATE "{table}" SET "{col}" = "{col}" - ? WHERE typeof("{col}") IN '
                                   f'(\'integer\', \'real\') AND "{col}" > 1000000000', (seconds,))
                touched += max(0, cur.rowcount)
    conn.execute("UPDATE realm_settings SET value = value - ? WHERE key IN ('politics:last_raid', "
                 "'politics:ironhold_due') AND value > 1000000000", (seconds,))
    conn.commit()
    return touched


async def handle_dev_command(session, text):
    def say(t):
        return send(session.ws, "CHAT_MSG", **{"from": "Dev", "text": t})
    if not _is_dev(session):
        await say("Unknown command.")
        return
    conn = WORLD.db.conn
    parts = text[2:].split()
    cmd = parts[0].lower() if parts else ""
    try:
        if cmd == "skip" and len(parts) >= 2:
            hours = max(1, min(DEV_SKIP_MAX_HOURS, int(float(parts[1]))))
            n = dev_shift_time(conn, hours * 3600)
            days = hours // 24
            for _d in range(days):
                conn.execute("DELETE FROM realm_settings WHERE key = 'daily:last'")
                conn.execute("UPDATE house_pledges SET errand_day = NULL, support_day = NULL")
                conn.commit()
                await ruling_daily_tick()
            for s_ in list(WORLD.sessions.values()):
                await settle_work(s_)
            await politics_live.tick()
            await throne_live.tick()
            await say(f"Skipped {hours}h ({n} timestamps moved, {days} daily tick(s) run). "
                      f"{politics.hud_line(conn)}")
        elif cmd == "rep" and len(parts) >= 2:
            v = max(-1000, min(1000, int(parts[1])))
            before = int(getattr(session, "reputation", 0) or 0)
            conn.execute("UPDATE players SET reputation = ? WHERE id = ?", (v, session.player_id))
            conn.commit()
            session.reputation = v
            await say(f"Reputation set to {v} ({reputation.tier(v)}), was {before}. "
                      f"This sets the score; it does not add to it.")
        elif cmd == "rank" and len(parts) >= 2:
            r = max(0, min(nobility.MAX_RANK, int(parts[1])))
            conn.execute("UPDATE players SET noble_rank = ? WHERE id = ?", (r, session.player_id))
            conn.commit()
            session.noble_rank = r
            await say(f"Noble rank set to {r} ({nobility.rank_name(r, session.gender)}).")
        elif cmd == "title" and len(parts) >= 2:
            want = " ".join(parts[1:]).strip().lower()
            titles = {"king": "King", "queen": "Queen", "prince consort": "Prince Consort",
                      "queen consort": "Queen Consort", "none": None}
            if want not in titles:
                await say("Usage: ::title <King|Queen|Prince Consort|Queen Consort|none>")
                return
            t_ = titles[want]
            conn.execute("UPDATE players SET royal_title = ? WHERE id = ?", (t_, session.player_id))
            conn.commit()
            session.royal_title = t_
            await say(f"Royal title set to {t_ or 'none'} (dev only; the next throne change re-applies real titles).")
            await broadcast_player_state(session)
        elif cmd == "favour" and len(parts) >= 2:
            want = max(0, min(throne.FAVOUR_MAX, int(parts[1])))
            have = int(throne.favour_row(conn, session.player_id)["favour"] or 0)
            now_f = throne.add_favour(conn, session.player_id, want - have)
            await say(f"Court favour set to {now_f}, was {have}.")
        elif cmd == "xp" and len(parts) >= 3:
            skill = parts[1].lower()
            if skill not in session.xp:
                await say(f"No such skill: {skill}. Try: {', '.join(sorted(session.xp))}")
                return
            raw = parts[2].lower()
            if raw.startswith("l"):      # ::xp mining L60 sets the level; ::xp mining 5000 adds xp
                lvl = max(1, min(120, int(raw.lstrip("lvl"))))
                target = combat.xp_for_level(lvl)
                gain = max(0, target - int(session.xp[skill]))
                note = f"to level {lvl}"
            else:
                gain = max(0, min(200_000_000, int(raw)))
                note = f"+{gain:,} xp"
            before, after = WORLD.grant_xp(session, skill, gain)
            await say(f"{skill}: {note} (level {before} -> {after}).")
        elif cmd == "welcome":
            arg = (parts[1].lower() if len(parts) >= 2 else "status")
            if arg == "reset":
                welcome_kit.reset(WORLD.db.conn, session.player_id)
            elif arg == "skip":
                welcome_kit.set_skipped(WORLD.db.conn, session.player_id)
            st = _welcome_status(session)
            await send_welcome_state(session, st)
            await say(f"Welcome kit: claimed={st['claimed']} skipped={st['skipped']} veteran={st['veteran']} "
                      f"owed={len(st['owed'])} trail={'on' if st['show_path'] else 'off'} "
                      f"(::welcome reset | skip)")
        elif cmd == "idle":
            arg = (parts[1].lower() if len(parts) >= 2 else "status")
            if arg in ("off", "on"):
                session.idle_exempt = arg == "off"
            idle_s = int((WORLD.tick_count - (session.last_input_tick or WORLD.tick_count)) * TICK_SECONDS)
            await say(f"Idle logout is {'off' if session.idle_exempt else 'on'} for you "
                      f"(idle {idle_s}s; warning at {int(IDLE_WARN_TICKS * TICK_SECONDS)}s, "
                      f"logout at {int(IDLE_LOGOUT_TICKS * TICK_SECONDS)}s).")
        elif cmd == "give" and len(parts) >= 2:
            item = parts[1]
            qty = max(1, min(1_000_000, int(parts[2]) if len(parts) >= 3 else 1))
            if item not in ITEMS:
                await say(f"No such item: {item}")
                return
            ok = WORLD.add_item_to_inventory(session, item, qty)
            await say(f"Gave {qty} x {item}." if ok else "Your inventory is full.")
        elif cmd == "fakeguild" and len(parts) >= 2:
            import clans
            n = max(0, int(parts[1]))
            cid = clans.clan_of(session.player_id)
            if not cid:
                await say("Make a guild first (/guild create <name>), then ::fakeguild <n>.")
                return
            clans._db().execute("DELETE FROM clan_members WHERE clan_id = ? AND player_id < 0", (cid,))
            n = min(n, clans.MAX_PLAYER_MEMBERS - clans.member_count(cid))
            for i in range(n):
                clans._db().execute("INSERT OR REPLACE INTO clan_members (player_id, clan_id, joined_at, rank) "
                                    "VALUES (?, ?, ?, 'Member')", (-(cid * 1000 + i + 1), cid, time.time()))
            clans._db().commit()
            await say(f"Guild now has {clans.member_count(cid)} members ({n} fake). {clans.strength_line(cid)}")
        elif cmd == "env":
            import world_clock
            if len(parts) < 2 or parts[1].lower() in ("?", "help"):
                await say("::env auto | ::env <season> [weather] [phase] | ::env skip [days] | "
                          "::env weather <name> | ::env phase <dawn|day|dusk|night>")
                return
            sub = parts[1].lower()
            if sub == "auto":
                snap = world_clock.clear_override()
            elif sub == "skip":
                days = max(1, min(28, int(float(parts[2])))) if len(parts) >= 3 else 1
                snap = world_clock.advance_days(days)
            elif sub == "weather" and len(parts) >= 3:
                snap = world_clock.force_env(weather=parts[2])
            elif sub == "phase" and len(parts) >= 3:
                snap = world_clock.force_env(phase=parts[2])
            elif sub in world_clock.SEASONS:
                weather = parts[2] if len(parts) >= 3 else None
                phase = parts[3] if len(parts) >= 4 else None
                snap = world_clock.force_env(season=sub, weather=weather, phase=phase)
            else:
                await say("Unknown ::env. Try ::env winter snow night")
                return
            await broadcast("ENV_UPDATE", env=snap)
            lab = snap.get("label") or {}
            await say(f"Env: {lab.get('date')} — {lab.get('line')}")
        else:
            await say("Dev: ::skip <hours> · ::rep <value> (sets) · ::rank <0-5> · ::title <King|Queen|Prince Consort|"
                      "Queen Consort|none> · ::favour <n> · ::xp <skill> <amount | L<level>> · ::give <item_id> [qty]"
                      " · ::fakeguild <n> · ::idle <on|off> · ::welcome <reset|skip> · ::env …")
            return
    except (ValueError, TypeError):
        await say("Bad number.")
        return
    await send(session.ws, "PLAYER_UPDATE", player=session.full_state())


async def court_event_notify():
    """COURT_EVENT to the monarch and council online (the NPC King answers on the next politics tick)."""
    conn = WORLD.db.conn
    for s_ in list(WORLD.sessions.values()):
        r = ruling.role(conn, s_.player_id)
        if r == "Monarch" or r in ruling.POSTS:
            ev = politics.event_payload(conn, s_.player_id)
            if ev:
                await send(s_.ws, "COURT_EVENT", event=ev)


async def handle_politics_msg(session, mtype, msg):
    conn = WORLD.db.conn
    if mtype == "COURT_CHOOSE":
        ok, text = politics.resolve(conn, session.player_id, str(msg.get("choice") or ""), monsters=MONSTERS)
        await send(session.ws, "CHAT_MSG", **{"from": "Royal Herald", "text": text})
        if ok:
            await broadcast("CHAT_MSG", **{"from": "Royal Herald", "text": "Court: " + text})
            s_ = session
            row = conn.execute("SELECT reputation FROM players WHERE id = ?", (s_.player_id,)).fetchone()
            if row:
                s_.reputation = int(row[0] or 0)
            await send(session.ws, "PLAYER_UPDATE", player=session.full_state())
    elif mtype == "NEWS_BOARD":
        lines = politics.latest_news(conn, politics.NEWS_BOARD_LINES) or ["The board is bare. No news yet."]
        await send(session.ws, "DIALOGUE", npc_id="notice_board", npc_name="Notice Board", lines=lines)
        return
    await send(session.ws, "KINGDOM_STATE", state=politics.state_payload(conn, session.player_id))


async def handle_house_option(session, npc, opt):
    conn = WORLD.db.conn
    pid = session.player_id
    house = npc.get("house")
    if opt == "house_pledge":
        ok, text = politics.pledge(conn, pid, house)
    elif opt == "house_errand":
        ok, text = politics.can_errand(conn, pid, house)
        if ok:
            item, qty, what = politics.ERRANDS[house]
            if WORLD.count_item(session, item) < qty:
                ok, text = False, f"Today's errand: bring {what}."
            else:
                WORLD.remove_item_qty(session, item, qty)
                ok, text = politics.errand_done(conn, pid, house)
                if ok:
                    WORLD.grant_xp(session, "charisma", politics.ERRAND_CHARISMA)
                    text += f" (+{politics.ERRAND_CHARISMA} Charisma XP.)"
                session.bank_coins = apprentice.bank_get(conn, pid)
                row = conn.execute("SELECT reputation FROM players WHERE id = ?", (pid,)).fetchone()
                session.reputation = int(row[0] or 0) if row else session.reputation
    elif opt in ("house_support", "house_oppose"):
        p = politics.pledge_of(conn, pid)
        if not p or p["house"] != house:
            ok, text = False, f"Only those pledged to {politics.HOUSES[house]} speak in its halls."
        else:
            ok, text = politics.support(conn, pid, "support" if opt == "house_support" else "oppose")
    else:
        ok, text = True, ""
    session.house_suffix = politics.title_suffix(conn, pid)
    lines = ([text] if text else []) + politics.house_lines(conn, pid)
    return lines


async def handle_rule(session, mtype, msg):
    """RULE_* requests. Every role and bound is checked in ruling.py."""
    global _SHOP_STOCK_START
    conn = WORLD.db.conn
    pid = session.player_id
    ok, text = True, ""
    if mtype == "RULE_SET_TAX":
        ok, out = ruling.set_tax(conn, pid, msg.get("key"), msg.get("value"))
        text = (f"Decree recorded: {ruling.setting_label(msg.get('key'))} becomes "
                f"{ruling._fmt(msg.get('key'), out)} at the next daily tick." if ok else out)
    elif mtype == "RULE_FUND_WORK":
        ok, text = ruling.fund_work(conn, pid, msg.get("key"))
        if ok and msg.get("key") == "feast":
            for s_ in list(WORLD.sessions.values()):
                await social_event(s_, "feast", rep=ruling.FEAST_REP)
        if ok and msg.get("key") == "markets":
            if _SHOP_STOCK_START is not None:
                for sid, shop in SHOPS.items():
                    for iid, info in shop["stock"].items():
                        info["qty"] = _SHOP_STOCK_START[sid][iid]
        if ok:
            await broadcast("CHAT_MSG", **{"from": "Royal Herald", "text": f"By royal order: {text}"})
    elif mtype == "RULE_POST_BOUNTY":
        ok, text = ruling.post_bounty(conn, pid, msg.get("monster"), msg.get("amount"), MONSTERS)
        if ok:
            await broadcast("CHAT_MSG", **{"from": "Royal Marshal", "text": text})
    elif mtype == "RULE_CANCEL_BOUNTY":
        try:
            ok, text = ruling.cancel_bounty(conn, pid, int(msg.get("id")))
        except (TypeError, ValueError):
            ok, text = False, "Which bounty?"
    elif mtype in ("RULE_APPOINT", "RULE_DISMISS"):
        if mtype == "RULE_APPOINT":
            row = conn.execute("SELECT id FROM players WHERE char_name = ? COLLATE NOCASE",
                               (str(msg.get("player") or "").strip(),)).fetchone()
            ok, text = (ruling.appoint(conn, pid, msg.get("post"), row[0]) if row else (False, "No such player."))
        else:
            ok, text = ruling.dismiss(conn, pid, msg.get("post"))
    elif mtype == "RULE_ANNOUNCE":
        ok, out = ruling.herald_announce(conn, pid, msg.get("text"))
        text = "Proclaimed." if ok else out
        if ok:
            await broadcast("CHAT_MSG", **{"from": f"Royal Herald {session.char_name}", "text": out})
    elif mtype in ("RULE_FREE_KING", "RULE_RECALL_KING"):
        fn = ruling.free_king if mtype == "RULE_FREE_KING" else ruling.recall_king
        ok, text = fn(conn, pid)
        if ok:
            throne_live.apply_king_state()
            await broadcast("CHAT_MSG", **{"from": "Royal Herald", "text":
                            "The old King is free, and now serves the Crown as Royal Advisor."})
    elif mtype != "RULE_STATE":
        return
    if text:
        await send(session.ws, "CHAT_MSG", **{"from": "Royal Treasury", "text": text})
    if ruling.role(conn, pid):
        await send(session.ws, "ROYAL_STATE", **ruling.state_payload(conn, pid))
    elif mtype == "RULE_STATE":
        await send(session.ws, "CHAT_MSG", **{"from": "Royal Treasury",
                   "text": "Only the monarch and the royal council may open the treasury."})
    await send(session.ws, "PLAYER_UPDATE", player=session.full_state())


def _nearest_other_player(session, reach):
    best = None
    for other in WORLD.sessions.values():
        if other is session or other.dungeon != session.dungeon:
            continue
        d = max(abs(other.x - session.x), abs(other.y - session.y))
        if d <= reach and (best is None or d < best[0]):
            best = (d, other)
    return best[1] if best else None


async def throne_schedule(session, kind, hours):
    conn = WORLD.db.conn
    fn = {"crown": throne.schedule_crown, "castle": throne.schedule_castle,
          "acclaim": throne.schedule_acclaim}.get(kind)
    if not fn:
        return "Unknown challenge."
    ok, out = fn(session, conn, hours)
    if not ok:
        return out
    import clans
    guild = clans._clan_row(clans.clan_of(session.player_id))
    gname = guild[1] if guild else "no guild"
    if kind == "crown":
        text = (f"⚔ {session.char_name} of {gname} challenges the Crown! "
                f"The battle begins in {out} hours at the King's Castle.")
    elif kind == "castle":
        text = f"⚔ {session.char_name} of {gname} challenges for a castle! The battle begins in {out} hours."
    else:
        text = f"👑 {session.char_name} petitions the court for Acclaim. The court decides in {out} hours."
    await broadcast("CHAT_MSG", **{"from": "Royal Herald", "text": text})
    await send(session.ws, "PLAYER_UPDATE", player=session.full_state())
    return f"Scheduled in {out} hours."


# ---- Warden Tamsin: the welcome talk, the Recruit's Bronze kit, the trail flag (server/welcome_kit.py) -------
def _welcome_status(session):
    return welcome_kit.status(WORLD.db.conn, session, ITEMS)


async def send_welcome_state(session, st=None):
    st = st or _welcome_status(session)
    await send(session.ws, "WELCOME_STATE", **welcome_kit.public_state(st, NPC_BY_ID.get(welcome_kit.GUIDE_ID)))


async def welcome_on_join(session):
    st = _welcome_status(session)
    await send_welcome_state(session, st)
    if st["show_path"]:
        text = "Over here, by the crossroads! Follow the golden trail. I've a Bronze kit for you."
    elif st["owed"]:
        text = "I'm still holding part of your kit. Come and see me when you've room in your bag."
    else:
        return
    await send(session.ws, "CHAT_MSG", **{"from": welcome_kit.GUIDE_NAME, "text": text})


async def welcome_talk(session, npc, tour=False, note=None):
    st = _welcome_status(session)
    pages = welcome_kit.pages(st, session.char_name, tour=tour, note=note)
    await send(session.ws, "DIALOGUE", npc_id=npc["id"], npc_name=npc["name"], lines=pages[0],
               pages=pages if len(pages) > 1 else None, options=welcome_kit.options(st))


def _welcome_put(session, item_id):
    """Bag first, then bank. 'bag', 'bank', or None when neither has room."""
    if WORLD.add_item_to_inventory(session, item_id, 1):
        return "bag"
    if _bank_put(session, item_id, 1):
        return "bank"
    return None


def _welcome_deliver(session, item_ids):
    placed, owed = {"bag": [], "bank": []}, []
    for item_id in item_ids:
        where = _welcome_put(session, item_id)
        (placed[where] if where else owed).append(item_id)
    return placed, owed


def _welcome_note(placed, owed, head):
    def names(ids):
        return ", ".join(ITEMS[i]["name"] for i in ids)
    lines = [head]
    if placed["bank"]:
        lines.append(f"Your bag was full, so I sent your {names(placed['bank'])} to the bank.")
    if owed:
        lines.append(f"Your bag and bank are both full. I'll keep your {names(owed)} safe. "
                     "Make some room and talk to me again to collect it.")
    return lines


async def welcome_equip(session):
    """Put kit pieces from the bag into empty (or tool-only) slots, through the normal equip path, so an
    outfit comes off by the gear rules."""
    worn = []
    for item_id, slot in welcome_kit.equippable_kit(session, ITEMS):
        slot_index = next((s for s, e in session.inventory.items() if e and e["item_id"] == item_id), None)
        if slot_index is None:
            continue
        await handle_equip(session, {"slot_index": slot_index})
        if session.equipment.get(slot) == item_id:
            worn.append(item_id)
    return worn


async def welcome_option(session, npc, opt):
    if not adjacent_or_same(session.x, session.y, npc["x"], npc["y"]):
        await send(session.ws, "ERROR", message="You're too far away to talk to them.")
        return
    conn, pid = WORLD.db.conn, session.player_id
    st = _welcome_status(session)
    if opt not in welcome_kit.allowed(st):
        await welcome_talk(session, npc)            # stale menu (double click, other client): show the real one
        return
    if opt == welcome_kit.OPT_REMIND:
        await welcome_talk(session, npc, tour=True)
        return
    note = None
    if opt in (welcome_kit.OPT_WEAR, welcome_kit.OPT_TAKE):
        try:
            with welcome_kit.one_transaction(WORLD.db, session):
                if not welcome_kit.take_claim(conn, pid):
                    raise welcome_kit.Rollback()
                placed, owed = _welcome_deliver(session, welcome_kit.KIT_IDS)
                welcome_kit.set_owed(conn, pid, owed)
        except welcome_kit.Rollback:
            await welcome_talk(session, npc)
            return
        log.info("%s claimed the welcome kit (bag %s, bank %s, owed %s)", session.char_name,
                 placed["bag"], placed["bank"], owed)
        # Stage 2 of the arrival guide: point them at Elder Miriam's starter quest.
        session.arrival_guide = True
        note = _welcome_note(placed, owed, "Here's your Recruit's Bronze kit: helmet, chest plate, leg armour "
                                           "and a sword. It's bound to you, so look after it.")
        await send(session.ws, "PLAYER_UPDATE", player=session.full_state())
        if opt == welcome_kit.OPT_WEAR and await welcome_equip(session):
            note.append("There, all buckled up. You're ready for the dungeon gate now.")
    elif opt == welcome_kit.OPT_COLLECT:
        with welcome_kit.one_transaction(WORLD.db, session):
            placed, owed = _welcome_deliver(session, welcome_kit.record(conn, pid)["owed"])
            welcome_kit.set_owed(conn, pid, owed)
        note = _welcome_note(placed, owed, "Here's the rest of your kit." if placed["bag"] or placed["bank"]
                             else "Still no room, I'm afraid.")
    elif opt == welcome_kit.OPT_EQUIP:
        worn = await welcome_equip(session)
        note = (["There, all buckled up."] if worn
                else ["There's nothing for me to put on you. Your kit's either on already or in the bank."])
    elif opt == welcome_kit.OPT_SWORD:
        try:
            with welcome_kit.one_transaction(WORLD.db, session):
                if not welcome_kit.take_sword(conn, pid):
                    raise welcome_kit.Rollback()
                where = _welcome_put(session, welcome_kit.SWORD)
                if where is None:
                    raise welcome_kit.Rollback()
            log.info("%s got a replacement Recruit's sword (%s)", session.char_name, where)
            note = ["Here, take this one. Try not to lose it. I can only spare one an hour."]
            if where == "bank":
                note.append("Your bag was full, so it's waiting in your bank.")
        except welcome_kit.Rollback:
            note = ["Your bag and bank are both full. Make some room and ask me again."]
    elif opt == welcome_kit.OPT_SKIP:
        welcome_kit.set_skipped(conn, pid)
        note = ["Right you are. I'll be here by the crossroads if you change your mind, "
                "and the kit's still yours to claim."]
    await send(session.ws, "PLAYER_UPDATE", player=session.full_state())
    if getattr(session, "arrival_guide", False) and opt in (welcome_kit.OPT_WEAR, welcome_kit.OPT_TAKE):
        # Kit just claimed: flip the trail to stage 2 (Elder Miriam) in the same breath.
        st = _welcome_status(session)
        st["claimed"] = True
        st["show_path"] = True
        await send_welcome_state(session, st)
    else:
        await send_welcome_state(session)
    await welcome_talk(session, npc, note=note)


async def welcome_skip(session):
    """The X on the trail banner. The trail stays off; the kit can still be claimed by talking to her."""
    welcome_kit.set_skipped(WORLD.db.conn, session.player_id)
    await send_welcome_state(session)


def _options_for(session, npc):
    """Celia's court options are female-only on the server."""
    if npc.get("id") == "mistress_celia" and str(session.gender).lower() != "female":
        return None
    return npc.get("options")


async def handle_npc_option(session, msg):
    """Dialogue menu options for apprentice masters and the estate office (phase 4)."""
    npc = NPC_BY_ID.get(msg.get("npc_id"))
    opt = msg.get("option")
    if npc and npc.get("welcome_guide"):
        await welcome_option(session, npc, opt)
        return
    allowed = {o["id"] for o in (_options_for(session, npc) if npc else None) or []}
    if npc and npc.get("id") == "chamberlain_aric":
        allowed.add("noble_pay")
    if npc and npc.get("id") == "old_king_prisoner":
        allowed.add("king_free")
    if allowed and isinstance(opt, str) and opt.startswith(throne.DYNAMIC_PREFIXES):
        allowed.add(opt)
    if not npc or not allowed or opt not in allowed:
        return
    if not adjacent_or_same(session.x, session.y, npc["x"], npc["y"]):
        await send(session.ws, "ERROR", message="You're too far away to talk to them.")
        return
    conn = WORLD.db.conn
    pid = session.player_id
    wp = npc.get("apprentice")
    lines = []
    if npc.get("house"):
        lines = await handle_house_option(session, npc, opt)
    elif opt == "app_sign":
        ok, text = apprentice.sign_on(conn, pid, npc["id"], wp)
        lines = [text]
    elif opt == "app_collect":
        if not apprentice.active(conn, pid):
            lines = ["You're not signed on with anyone."]
        else:
            await settle_work(session)
            st = apprentice.status(conn, pid) or {}
            lines = [f"Wages settled. Shifts today: {st.get('today', 0)}/{apprentice.DAILY_SHIFT_CAP}. "
                     "A shift is a whole hour, so check back later."]
    elif opt == "app_leave":
        await settle_work(session)
        lines = [apprentice.leave(conn, pid)[1]]
    elif opt == "app_info":
        lines = apprentice.info_lines(wp)
    elif opt == "noble_petition":
        rows = nobility.check_rows(session, conn)
        if not rows:
            lines = ["You already hold the highest rank the Crown grants."]
        else:
            nxt = session.noble_rank + 1
            lines = [f"Next rank: {nobility.rank_name(nxt, session.gender)} · patent fee {nobility.fee(nxt):,}",
                     "  ".join(("✓ " if ok else "✗ ") + label for label, ok in rows)]
            left = nobility.cooldown_left(conn, pid)
            if left > 0:
                lines.append(f"Your last petition was refused. Come back in {int(left // 3600) + 1} hours.")
            elif all(ok for _l, ok in rows):
                await send(session.ws, "DIALOGUE", npc_id=npc["id"], npc_name=npc["name"], lines=lines,
                           options=[{"id": "noble_pay", "label": f"Pay {nobility.fee(nxt):,}"}]
                           + npc["options"][1:])
                return
    elif opt == "noble_pay":
        old_name = nobility.display_name(session)
        ok, text, _old = nobility.petition(session, conn)
        lines = [text]
        if ok:
            await social_event(session, "noble_patent", rep=nobility.REP_PROMOTION,
                               xp={"etiquette": nobility.ETIQUETTE_PROMOTION_XP})
            herald = (f"By the King's patent, {old_name} is now "
                      f"{nobility.rank_name(session.noble_rank, session.gender)} {session.char_name}.")
            if session.noble_rank >= nobility.BROADCAST_FROM_RANK:
                await broadcast("CHAT_MSG", **{"from": "Herald", "text": herald})
            else:
                await send(session.ws, "CHAT_MSG", **{"from": "Herald", "text": herald})
    elif opt in ("crown_check", "castle_check", "acclaim_check"):
        kind = opt.split("_")[0]
        if kind == "crown":
            ok, missing = throne.crown_eligible(session, conn)
            import politics as _po
            lines = [f"Crown Challenge (fee {_po.crown_fee(conn, throne.CROWN_FEE):,}; 30-minute battle in the throne room):"]
            lines.append("✓ All requirements met." if ok else "✗ " + " · ✗ ".join(missing))
        elif kind == "castle":
            import clans
            cid = clans.clan_of(pid)
            row = conn.execute("SELECT challenge_castle_id FROM clans WHERE clan_id = ?", (cid,)).fetchone() if cid else None
            castle = row[0] if row else None
            ok = bool(castle) and clans.can_challenge_castle(cid, castle)
            fee_txt = f"{throne.castle_fee(castle):,}" if castle else "1% of the deed"
            lines = [f"Castle Challenge (fee {fee_txt}; 7 days between challenges; 20 minutes at the keep): "
                     + (f"{castle} ✓" if ok else "only when every castle is owned, after /guild challenge <castle>.")]
        else:
            ok, missing = throne.courtier_eligible(session, conn)
            fav = throne.favour_row(conn, pid)["favour"]
            ok = ok and fav >= throne.FAVOUR_MAX
            lines = [f"Court Acclaim (fee {throne.ACCLAIM_FEE:,}): favour {fav}/{throne.FAVOUR_MAX}"
                     + ("" if not missing else " · ✗ " + " · ✗ ".join(missing))]
        if ok:
            hours = [{"id": f"{kind}_h{h}", "label": f"In {h}h"} for h in throne.HOUR_CHOICES]
            lines.append("Pick a start time (or /throne " + kind + " <12-48>).")
            await send(session.ws, "DIALOGUE", npc_id=npc["id"], npc_name=npc["name"], lines=lines,
                       options=hours + list(_options_for(session, npc) or []))
            return
    elif isinstance(opt, str) and opt.startswith(throne.DYNAMIC_PREFIXES):
        kind, _h, hours = opt.partition("_h")
        lines = [await throne_schedule(session, kind, hours)]
    elif opt == "throne_list":
        lines = throne.summary_lines(conn, throne_live._name)
    elif opt == "court_status":
        f = throne.favour_row(conn, pid)
        conn.commit()
        lines = [f"Court Favour {f['favour']}/{throne.FAVOUR_MAX}. Three small services a day (+20 each); "
                 "the Court Ball, Saturdays 20:00 in the throne room, is +100 once a week.",
                 "Standing at Neutral or worse costs 50 favour a day."]
    elif opt in throne.COURT_TASKS:
        ok, missing = throne.courtier_eligible(session, conn)
        label, items = throne.COURT_TASKS[opt]
        have = next((i for i in items if WORLD.count_item(session, i) > 0), None)
        if not ok:
            lines = ["Not yet: " + "; ".join(missing)]
        elif not have:
            lines = [f"{label}: you have nothing suitable with you."]
        else:
            got = throne.court_task(conn, pid)
            if got:
                WORLD.remove_item_qty(session, have, 1)
                lines = [f"Thank you. +{got} Court Favour."]
            else:
                lines = ["That's enough service for today. Come back tomorrow."]
    elif opt == "wed_propose":
        target = _nearest_other_player(session, 2)
        if not target:
            lines = ["Stand beside the one you wish to marry, then propose."]
        else:
            throne.propose(pid, target.player_id)
            lines = [f"You propose to {target.char_name}. They have a minute to accept here."]
            await send(target.ws, "CHAT_MSG", **{"from": "Chaplain Mirelle",
                       "text": f"{session.char_name} proposes marriage. Talk to me and choose Accept proposal."})
    elif opt == "wed_accept":
        other = throne.pending_proposal(pid)
        o_sess = WORLD.sessions.get(int(other)) if other else None
        if not o_sess:
            lines = ["No one has proposed to you (or the minute passed)."]
        else:
            ok, text = throne.marry(conn, other, pid)
            lines = [text]
            if ok:
                for s_ in (session, o_sess):
                    s_.bank_coins = apprentice.bank_get(conn, s_.player_id)
                    await social_event(s_, "marriage", rep=throne.REP_MARRIAGE)
                    await send(s_.ws, "PLAYER_UPDATE", player=s_.full_state())
                await broadcast("CHAT_MSG", **{"from": "Chaplain Mirelle",
                                "text": f"{session.char_name} and {o_sess.char_name} are wed."})
    elif opt == "wed_divorce":
        lines = [throne.divorce(conn, pid)[1]]
    elif opt == "wed_status":
        sp = throne.spouse_of(conn, pid)
        lines = [f"You are married to {throne_live._name(sp)}." if sp else "You are not married."]
    elif opt == "king_free":
        await handle_rule(session, "RULE_FREE_KING", {})
        return
    elif opt == "noble_perks":
        lines = nobility.perks_lines()
    elif opt == "noble_leave":
        await send(session.ws, "DIALOGUE", npc_id=npc["id"], npc_name=npc["name"],
                   lines=["Good day to you."])
        return
    elif opt == "prop_buy":
        lines = [_property.buy_plot(conn, pid)[1]]
    elif opt == "prop_farm":
        lines = [_property.upgrade(conn, pid, "farm")[1]]
    elif opt == "prop_workshop":
        lines = [_property.upgrade(conn, pid, "workshop")[1]]
    elif opt == "prop_hire":
        await settle_work(session)
        lines = [_property.hire(conn, pid)[1]]
    elif opt == "prop_dismiss":
        await settle_work(session)
        lines = [_property.dismiss(conn, pid)[1]]
    elif opt == "prop_mine":
        lines = _property.describe(conn, pid)
    elif opt == "prop_work":
        found = _property.find_workplace(conn, pid)
        if not found:
            lines = ["No player farm or workshop has a free worker slot right now."]
        else:
            prop_id, _owner, kind = found
            ok, text = apprentice.sign_on(conn, pid, f"property:{prop_id}", _property.WORKPLACE_FOR[kind], prop_id)
            lines = [text + (" The owner pays your wage." if ok else "")]
    await send(
        session.ws, "DIALOGUE", npc_id=npc["id"], npc_name=npc["name"], lines=lines,
        options=npc.get("options"), housing=bool(npc.get("housing")),
    )
    await send(session.ws, "PLAYER_UPDATE", player=session.full_state())


async def handle_persuade(session, msg):
    """[Persuade (Charisma N)] dialogue check. Success if charisma level >= req."""
    npc = NPC_BY_ID.get(msg.get("npc_id"))
    node = (npc or {}).get("persuade")
    if not node or not adjacent_or_same(session.x, session.y, npc["x"], npc["y"]):
        return
    ok = session.level("charisma") >= int(node["req"])
    await send(
        session.ws, "DIALOGUE", npc_id=npc["id"], npc_name=npc["name"],
        lines=list(node["success"] if ok else node["fail"]),
        shop_id=npc.get("shop_id"),
    )


async def send_bank_state(session):
    await send(
        session.ws, "BANK_STATE",
        inventory=session.inventory,
        bank=session.bank,
        coins=session.coins,
        bank_coins=session.bank_coins,
        max_purse=MAX_PURSE_COINS,
        max_bank_coins=MAX_BANK_COINS,
        bank_slots=BANK_SLOTS,
    )


async def handle_bank_open(session, msg):
    if not WORLD.near_bank(session):
        await send(session.ws, "ERROR", message="You need to be at the bank booth.")
        return
    await send_bank_state(session)


async def handle_bank_deposit(session, msg):
    if not WORLD.near_bank(session):
        await send(session.ws, "ERROR", message="You need to be at the bank.")
        return
    # Deposit coins
    if msg.get("coins"):
        qty = max(0, int(msg.get("coins", 0)))
        qty = min(qty, session.coins)
        room = max(0, MAX_BANK_COINS - session.bank_coins)
        qty = min(qty, room)
        if qty <= 0:
            await send(session.ws, "ERROR", message="Can't deposit that many coins.")
            return
        session.coins -= qty
        session.bank_coins += qty
        WORLD.db.save_player_stats(session.player_id, coins=session.coins, bank_coins=session.bank_coins)
        await send_bank_state(session)
        await send(session.ws, "PLAYER_UPDATE", player=session.full_state())
        return
    # Deposit every tradeable inventory stack
    if msg.get("deposit_inventory"):
        deposited = 0
        skipped = 0
        for slot in sorted(list(session.inventory.keys())):
            entry = session.inventory.get(slot)
            if not entry:
                continue
            item_id, qty = entry["item_id"], entry["qty"]
            if not item_is_bankable(item_id):
                skipped += 1
                continue
            placed = False
            if ITEMS[item_id].get("stackable"):
                for bslot, bent in session.bank.items():
                    if bent["item_id"] == item_id:
                        bent["qty"] += qty
                        WORLD.db.set_bank_slot(session.player_id, bslot, item_id, bent["qty"])
                        placed = True
                        break
            if not placed:
                for bslot in range(BANK_SLOTS):
                    if bslot not in session.bank:
                        session.bank[bslot] = {"item_id": item_id, "qty": qty}
                        WORLD.db.set_bank_slot(session.player_id, bslot, item_id, qty)
                        placed = True
                        break
            if not placed:
                await send(session.ws, "ERROR", message="Your bank is full.")
                break
            del session.inventory[slot]
            WORLD.db.clear_slot(session.player_id, slot)
            deposited += 1
        await send_bank_state(session)
        await send(session.ws, "PLAYER_UPDATE", player=session.full_state())
        if deposited:
            extra = f" ({skipped} kept)" if skipped else ""
            await send(session.ws, "CHAT_MSG", **{
                "from": "Bank", "text": f"Deposited {deposited} stack{'s' if deposited != 1 else ''}{extra}.",
            })
        elif skipped and not deposited:
            await send(session.ws, "ERROR", message="Nothing you can bank.")
        return
    # Deposit inventory slot
    slot = msg.get("slot_index")
    if slot is None:
        return
    try:
        slot = int(slot)
    except (TypeError, ValueError):
        return
    entry = session.inventory.get(slot)
    if not entry:
        return
    item_id, qty = entry["item_id"], entry["qty"]
    if not item_is_bankable(item_id):
        if (ITEMS.get(item_id) or {}).get("unique"):
            await send(session.ws, "ERROR",
                       message=f"Your {ITEMS[item_id]['name']} stays with you — bags can't be banked.")
            return
        await send(session.ws, "ERROR", message="You can't bank that.")
        return
    # stack into existing bank slot or free slot
    placed = False
    if ITEMS[item_id].get("stackable"):
        for bslot, bent in session.bank.items():
            if bent["item_id"] == item_id:
                bent["qty"] += qty
                WORLD.db.set_bank_slot(session.player_id, bslot, item_id, bent["qty"])
                placed = True
                break
    if not placed:
        for bslot in range(BANK_SLOTS):
            if bslot not in session.bank:
                session.bank[bslot] = {"item_id": item_id, "qty": qty}
                WORLD.db.set_bank_slot(session.player_id, bslot, item_id, qty)
                placed = True
                break
    if not placed:
        await send(session.ws, "ERROR", message="Your bank is full.")
        return
    del session.inventory[slot]
    WORLD.db.clear_slot(session.player_id, slot)
    await send_bank_state(session)
    await send(session.ws, "PLAYER_UPDATE", player=session.full_state())


async def handle_bank_withdraw(session, msg):
    if not WORLD.near_bank(session):
        await send(session.ws, "ERROR", message="You need to be at the bank.")
        return
    if msg.get("coins"):
        qty = max(0, int(msg.get("coins", 0)))
        qty = min(qty, session.bank_coins)
        room = max(0, MAX_PURSE_COINS - session.coins)
        qty = min(qty, room)
        if qty <= 0:
            await send(session.ws, "ERROR", message="Can't withdraw that many coins.")
            return
        session.bank_coins -= qty
        session.coins += qty
        WORLD.db.save_player_stats(session.player_id, coins=session.coins, bank_coins=session.bank_coins)
        await send_bank_state(session)
        await send(session.ws, "PLAYER_UPDATE", player=session.full_state())
        return
    slot = msg.get("slot_index")
    if slot is None:
        return
    try:
        slot = int(slot)
    except (TypeError, ValueError):
        return
    entry = session.bank.get(slot)
    if not entry:
        return
    item_id, qty = entry["item_id"], entry["qty"]
    want = min(qty, max(1, int(msg.get("qty", qty))))
    if item_id in ORE_ITEM_IDS and WORLD.count_ores(session) + want > MAX_ORES:
        await send(session.ws, "ERROR", message=f"You can't carry more than {MAX_ORES} ores.")
        return
    if not WORLD.add_item_to_inventory(session, item_id, want):
        await send(session.ws, "ERROR", message="Your inventory is full.")
        return
    entry["qty"] -= want
    if entry["qty"] <= 0:
        del session.bank[slot]
        WORLD.db.clear_bank_slot(session.player_id, slot)
    else:
        WORLD.db.set_bank_slot(session.player_id, slot, item_id, entry["qty"])
    await send_bank_state(session)
    await send(session.ws, "PLAYER_UPDATE", player=session.full_state())


def _shop_discount(session):
    """Noble rank + consort + Stock the markets; reputation.buy_price applies the −10% cap."""
    d = nobility.shop_discount(getattr(session, "noble_rank", 0))
    d += ruling.consort_discount(getattr(session, "royal_title", None))
    if ruling.work_active(WORLD.db.conn, "markets"):
        d += ruling.MARKETS_EXTRA_DISCOUNT
    return d


async def send_shop_state(session, shop_id):
    shop = SHOPS[shop_id]
    score = getattr(session, "reputation", 0)
    noble = _shop_discount(session)
    stock = {iid: {"price": reputation.buy_price(info["price"], score, noble), "qty": info["qty"],
                   "name": ITEMS[iid]["name"]}
             for iid, info in shop["stock"].items()}
    await send(
        session.ws, "SHOP_STATE",
        shop_id=shop_id, name=shop["name"], stock=stock,
        your_coins=session.coins, buys=bool(shop.get("buys")),
        buys_types=list(shop.get("buys_types") or []),
        buys_slots=list(shop.get("buys_slots") or []),
        tax_rate=royal_treasury.sales_tax_rate(),
        rep_tier=reputation.tier(score), rep_mult=reputation.price_mult(score),
        sell_mult=reputation.sell_mult(score),
        noble_discount=noble,
        noble_title=nobility.rank_name(getattr(session, "noble_rank", 0), session.gender),
    )


async def social_event(session, source, **kw):
    await reputation.social_event(WORLD, send, session, source, **kw)


async def _pay_royal_tax(session, source, amount):
    """Credit a paid sales tax to the treasury; first one ever shows the notice."""
    if amount <= 0:
        return
    royal_treasury.credit(WORLD.db.conn, source, session.player_id, amount)
    if amount >= reputation.MIN_TAX_FOR_STANDING:      # 1-coin trades can't farm standing
        await social_event(
            session, source, rep=reputation.REP_TAX, rep_cap_key="rep_tax", rep_cap=reputation.REP_TAX_DAILY_CAP,
            xp={"etiquette": reputation.ETIQUETTE_TAX_XP}, xp_cap_key="fee_xp",
            xp_cap=reputation.ETIQUETTE_FEE_DAILY_CAP,
        )
    if not getattr(session, "tax_notice_seen", False):
        session.tax_notice_seen = True
        WORLD.db.save_player_stats(session.player_id, tax_notice_seen=1)
        pct = int(round(royal_treasury.sales_tax_rate() * 100))
        await send(session.ws, "CHAT_MSG", **{
            "from": "Royal Tax Collector",
            "text": f"By decree of the King of Crownfall, {pct}% of every shop sale goes to the royal treasury.",
        })


async def handle_set_pet(session, msg):
    """Switch the active companion among owned pets."""
    pet_id = msg.get("pet_id")
    if not pet_id:
        await send(session.ws, "ERROR", message="Pick a pet to switch to.")
        return
    if pet_id not in PETS:
        await send(session.ws, "ERROR", message="Unknown pet.")
        return
    if pet_id not in session.owned_pets:
        await send(session.ws, "ERROR", message="You don't own that pet. Buy it at the Pet Emporium.")
        return
    if pet_id == session.pet_id:
        await send(session.ws, "CHAT_MSG", **{
            "from": "Pets", "text": f"{PETS[pet_id]['name']} is already with you.",
        })
        return
    session.activate_pet(pet_id)
    await send(session.ws, "PLAYER_UPDATE", player=session.full_state())
    await send(session.ws, "CHAT_MSG", **{
        "from": "Pets", "text": f"{PETS[pet_id]['name']} joins you.",
    })


async def handle_toggle_hd_player(session, msg):
    """Toggle HD player rendering (2D/3D)."""
    enabled = bool(msg.get("enabled", True))
    WORLD.db.save_player_stats(session.player_id, hd_player=int(enabled))
    session.row = WORLD.db.get_player_by_id(session.player_id)
    await send(session.ws, "PLAYER_UPDATE", player=session.full_state())
    mode = "3D" if enabled else "2D"
    await send(session.ws, "CHAT_MSG", **{"from": "Settings", "text": f"Player rendering: {mode}"})


def _cosmetic_catalogue():
    """Outfitter catalogue, cached by file mtime (outfits.catalogue)."""
    return outfits.catalogue()


def _clean_appearance(session, appearance, owned=None):
    """Return a saved look, or an error string. Ownership, sex, regalia, palette and level are checked."""
    if owned is None:
        owned = set(session._json_list("owned_cosmetics"))
    return outfits.clean(session, appearance, set(owned))


def outfit_unlocked(session, item):
    """(ok, hint, progress) for one catalogue item or set (OUTFITS_SPEC §3)."""
    return outfits.outfit_unlocked(session, item, WORLD.db.conn)


def _outfit_pricing(session):
    return {"price_mult": reputation.price_mult(getattr(session, "reputation", 0)),
            "discount": _shop_discount(session), "cap": reputation.MAX_TOTAL_DISCOUNT,
            "tax_rate": royal_treasury.sales_tax_rate()}


def _outfits_migrate_v2(session):
    """SIDEBAR_DESIGN §4: one-off, idempotent move of a saved look (and wardrobe) to the painted-set block.

    Paid layered pieces are refunded 100% to the bank (purse if the vault is full). Returns the
    "Your old clothing was traded in" note to post, or None.
    """
    raw = session._row_val("appearance")
    if not raw:
        return None
    try:
        look = json.loads(raw)
    except Exception:
        return None
    if not isinstance(look, dict) or int(look.get("appearance_version") or 0) >= outfits.APPEARANCE_VERSION:
        return None
    try:
        owned = session._json_list("owned_cosmetics")
        tier_ok = lambda tier: outfits.tier_unlocked(session, tier, WORLD.db.conn)
        new, refund, ids = outfits.migrate_v2(look, owned, session.gender, tier_ok)
        slots = []
        for entry in session._json_list("saved_outfits") or []:
            if isinstance(entry, dict):
                moved, _r, _i = outfits.migrate_v2(entry, [], session.gender, tier_ok)
                moved.pop("appearance_legacy", None)
                moved["name"] = entry.get("name") or "Outfit"
                moved["note"] = "Updated for the new outfits"
                slots.append(moved)
            else:
                slots.append(entry)
        to_bank = min(refund, max(0, MAX_BANK_COINS - int(session.bank_coins)))
        session.bank_coins += to_bank
        session.coins += refund - to_bank
        WORLD.db.save_player_stats(session.player_id, appearance=json.dumps(new), saved_outfits=json.dumps(slots),
                                   coins=session.coins, bank_coins=session.bank_coins)
        session.row = WORLD.db.get_player_by_id(session.player_id)
        logging.getLogger("outfits").info("migrate_v2 %s: set=%s refund=%d items=%d slots=%d",
                                          session.char_name, new.get("set"), refund, len(ids), len(slots))
    except Exception:
        logging.getLogger("outfits").exception("migrate_v2 failed for %s", getattr(session, "char_name", "?"))
        return None
    if refund:
        return f"{outfits.TRADE_IN_MAIL}: {refund:,} coins for {len(ids)} old purchase{'s' if len(ids) != 1 else ''} (clothing, colours, upgrades) went to your bank."
    return None


async def handle_buy_collection_set(session, msg):
    """BUY_COLLECTION_SET {set}: buy a live Collection design (§6.1) and wear it. Re-buy refused."""
    set_id = str(msg.get("set") or "")
    entry = outfits.collection_entry(set_id)
    if not entry:
        await send(session.ws, "ERROR", message="That design is not in the catalogue.")
        return
    if not outfits.collection_live(entry):
        await send(session.ws, "ERROR", message="That design is coming soon.")
        return
    if entry.get("sex") != outfits._sex(session.gender):
        await send(session.ws, "ERROR", message="That isn't cut for you.")
        return
    owned = session._json_list("owned_cosmetics")
    if set_id in owned:
        await send(session.ws, "ERROR", message="You already own that design.")
        return
    if entry.get("tier") and not outfits.tier_unlocked(session, entry["tier"], WORLD.db.conn):
        await send(session.ws, "ERROR", message="That design needs its story tier first.")
        return
    charge = await _charge_outfitter(session, int(entry.get("price") or 0))
    if charge is None:
        return
    cost, tax = charge
    owned.append(set_id)
    base = session.appearance_state() or {}
    look, error = _clean_appearance(session, dict(base, set=set_id), set(owned))
    if error:
        await send(session.ws, "ERROR", message=error)
        return
    _pay_purse_then_bank(session, cost + tax)
    WORLD.db.save_player_stats(session.player_id, coins=session.coins, bank_coins=session.bank_coins,
                               owned_cosmetics=json.dumps(owned), appearance=json.dumps(look))
    session.row = WORLD.db.get_player_by_id(session.player_id)
    if tax:
        await _pay_royal_tax(session, "sales_tax_buy", tax)
    await send(session.ws, "PLAYER_UPDATE", player=session.full_state())
    await broadcast_player_state(session)
    await send(session.ws, "CHAT_MSG", **{"from": "Mae", "text": f"{entry.get('name')} is yours: {cost:,} coins (+{tax:,} royal tax)."})


async def handle_set_gender(session, msg):
    gender = "female" if str(msg.get("gender") or "").lower() == "female" else "male"
    session.gender = gender
    WORLD.db.save_player_stats(session.player_id, gender=gender)
    session.row = WORLD.db.get_player_by_id(session.player_id)
    await send(session.ws, "PLAYER_UPDATE", player=session.full_state())


async def handle_update_appearance(session, msg):
    """Save a look. Paid pieces must already be owned."""
    import json
    appearance, error = _clean_appearance(session, msg.get("appearance"))
    if error:
        await send(session.ws, "ERROR", message=error)
        return
    error = await _outfit_gear_check(session, appearance)
    if error:
        await send(session.ws, "ERROR", message=error)
        return
    WORLD.db.save_player_stats(session.player_id, appearance=json.dumps(appearance))
    session.row = WORLD.db.get_player_by_id(session.player_id)
    await send(session.ws, "PLAYER_UPDATE", player=session.full_state())
    await broadcast_player_state(session)
    notes = outfits.clean_notes(session, msg.get("appearance"), set(session._json_list("owned_cosmetics")))
    await send(session.ws, "CHAT_MSG", **{"from": "Mae", "text": "Look saved." + (" " + " ".join(notes) if notes else "")})


def _wallet_total(session):
    """Purse + bank. Outfitter prices can exceed the 65k purse cap."""
    return int(session.coins) + int(session.bank_coins)


def _pay_purse_then_bank(session, amount):
    """Spend from the purse first, then the bank. Caller must have checked affordability."""
    amount = int(amount)
    take_purse = min(int(session.coins), amount)
    session.coins -= take_purse
    session.bank_coins -= amount - take_purse


async def handle_buy_cosmetics(session, msg):
    """Buy the unowned pieces being tried on (unlock-checked, shop pricing + royal tax), then wear the look."""
    import json
    table = outfits.items()
    owned = session._json_list("owned_cosmetics")
    owned_set = set(owned)
    ids = [i for i in dict.fromkeys(msg.get("items") or [])]
    buy_ids = []
    skipped_regalia = []
    for item_id in ids:
        item = table.get(item_id)
        if not item:
            await send(session.ws, "ERROR", message="That item is not in the catalogue.")
            return
        if item.get("starter") or item_id in owned_set:
            continue
        ok, hint, _progress = outfit_unlocked(session, item)
        if not ok:
            await send(session.ws, "ERROR", message=hint or "That piece is locked.")
            return
        if not outfits.regalia_ok(session, item):
            # Title regalia (King's crown, etc.): skip and still buy/wear the rest of the set.
            skipped_regalia.append(item.get("name") or item_id)
            continue
        buy_ids.append(item_id)
    q = outfits.quote(session, buy_ids, owned_set, _shop_discount(session), msg.get("set"))
    cost = int(q["total"])
    tax = royal_treasury.buy_tax(cost)
    due = cost + tax
    if due > _wallet_total(session):
        await send(session.ws, "ERROR", message=f"You need {due - _wallet_total(session):,} more coins (purse + bank).")
        return
    buying = list(q["pieces"])
    for b_id in list(buying):            # jewellery bundles (Crown Jewels): grant the pieces at the bundle price
        buying += [p for p in (table.get(b_id) or {}).get("bundle") or [] if p not in buying and p not in owned_set]
    appearance, error = _clean_appearance(session, msg.get("appearance"), owned_set | set(buying))
    if error:
        await send(session.ws, "ERROR", message=error)
        return
    error = await _outfit_gear_check(session, appearance)
    if error:
        await send(session.ws, "ERROR", message=error)
        return
    owned.extend(b for b in buying if b not in owned_set)
    _pay_purse_then_bank(session, due)
    WORLD.db.save_player_stats(
        session.player_id,
        coins=session.coins,
        bank_coins=session.bank_coins,
        owned_cosmetics=json.dumps(owned),
        appearance=json.dumps(appearance),
    )
    session.row = WORLD.db.get_player_by_id(session.player_id)
    if tax:
        await _pay_royal_tax(session, "sales_tax_buy", tax)
    await send(session.ws, "PLAYER_UPDATE", player=session.full_state())
    await broadcast_player_state(session)
    note = ""
    if skipped_regalia:
        note = " " + (", ".join(skipped_regalia[:2]) + ("…" if len(skipped_regalia) > 2 else "")
                      + " need the matching title.")
    if cost:
        await send(session.ws, "CHAT_MSG", **{"from": "Mae",
                   "text": f"Bought and worn for {cost:,} coins (+{tax:,} royal tax).{note}"})
    else:
        await send(session.ws, "CHAT_MSG", **{"from": "Mae", "text": f"Worn.{note}"})


async def _charge_outfitter(session, base):
    """Shop price (standing x discount, -10% cap) + royal tax. Returns (cost, tax) or None when short.

    Purse first, then bank — sets can cost more than the 65k purse holds.
    """
    cost = reputation.buy_price(base, getattr(session, "reputation", 0), _shop_discount(session)) if base else 0
    tax = royal_treasury.buy_tax(cost)
    due = cost + tax
    if due > _wallet_total(session):
        await send(session.ws, "ERROR", message=f"You need {due - _wallet_total(session):,} more coins (purse + bank).")
        return None
    return cost, tax


async def handle_buy_palette(session, msg):
    """BUY_PALETTE {set? | item?, palette}: one extra colour for a whole set (default) or one piece."""
    import json
    palette = msg.get("palette")
    set_id, item_id = msg.get("set"), msg.get("item")
    entry = outfits.sets().get(set_id) if set_id else outfits.items().get(item_id)
    if not entry or palette not in (entry.get("palettes") or []):
        await send(session.ws, "ERROR", message="That colour is not offered for it.")
        return
    if entry.get("sex") and entry["sex"] != ("female" if session.gender == "female" else "male"):
        await send(session.ws, "ERROR", message="That isn't cut for you.")
        return
    ok, hint, _p = outfit_unlocked(session, entry)
    if not ok:
        await send(session.ws, "ERROR", message=hint or "That set is locked.")
        return
    key = f"palette:{set_id or item_id}:{palette}"
    owned = session._json_list("owned_cosmetics")
    if palette == entry["palettes"][0] or key in owned:
        await send(session.ws, "CHAT_MSG", **{"from": "Mae", "text": "You already have that colour."})
        return
    tier = int(entry.get("tier") or 1)
    base = int(((outfits.catalogue().get("garment_palettes") or {}).get(palette) or {}).get("price") or 0) \
        or int(entry.get("palette_price") or 0)
    if item_id and not set_id:
        base = max(1, base // 2)
    charged = await _charge_outfitter(session, base)
    if charged is None:
        return
    cost, tax = charged
    owned.append(key)
    _pay_purse_then_bank(session, cost + tax)
    WORLD.db.save_player_stats(
        session.player_id, coins=session.coins, bank_coins=session.bank_coins,
        owned_cosmetics=json.dumps(owned),
    )
    session.row = WORLD.db.get_player_by_id(session.player_id)
    if tax:
        await _pay_royal_tax(session, "sales_tax_buy", tax)
    await send(session.ws, "PLAYER_UPDATE", player=session.full_state())
    await send(session.ws, "CHAT_MSG", **{"from": "Mae", "text": f"New colour for {cost:,} coins (+{tax:,} tax). Tier {tier} cloth, dyed fresh."})


async def handle_upgrade_outfit(session, msg):
    """UPGRADE_OUTFIT {set, level}: Plain -> Fine (2) -> Regal (3) for a set you own."""
    import json
    set_id = msg.get("set")
    entry = outfits.sets().get(set_id)
    try:
        level = int(msg.get("level"))
    except (TypeError, ValueError):
        level = 0
    if not entry or level not in (2, 3):
        await send(session.ws, "ERROR", message="Nothing to upgrade there.")
        return
    owned = session._json_list("owned_cosmetics")
    outfit_piece = next((p for p in entry.get("pieces") or [] if (outfits.items().get(p) or {}).get("slot") == "outfit"), None)
    if outfit_piece not in owned:
        await send(session.ws, "ERROR", message="Buy the set's outfit first.")
        return
    have = outfits.owned_level(set(owned), set_id)
    if level != have + 1:
        await send(session.ws, "ERROR", message="Upgrade one level at a time." if level > have else "You already have that level.")
        return
    ok, hint = outfits.upgrade_requirement(session, entry, level, WORLD.db.conn)
    if not ok:
        await send(session.ws, "ERROR", message=hint)
        return
    base = int((entry.get("upgrade_prices") or [0, 0])[level - 2])
    charged = await _charge_outfitter(session, base)
    if charged is None:
        return
    cost, tax = charged
    owned.append(f"{set_id}@{level}")
    _pay_purse_then_bank(session, cost + tax)
    WORLD.db.save_player_stats(
        session.player_id, coins=session.coins, bank_coins=session.bank_coins,
        owned_cosmetics=json.dumps(owned),
    )
    session.row = WORLD.db.get_player_by_id(session.player_id)
    if tax:
        await _pay_royal_tax(session, "sales_tax_buy", tax)
    await send(session.ws, "PLAYER_UPDATE", player=session.full_state())
    label = "Fine" if level == 2 else "Regal"
    await send(session.ws, "CHAT_MSG", **{"from": "Mae", "text": f"{entry['name']} raised to {label} for {cost:,} coins (+{tax:,} tax)."})


async def handle_save_outfit(session, msg):
    """SAVE_OUTFIT {slot 0-5, appearance, name?}: six named wardrobe slots."""
    import json
    try:
        slot = int(msg.get("slot"))
    except (TypeError, ValueError):
        return
    if not 0 <= slot < outfits.SAVED_SLOTS:
        return
    appearance, error = _clean_appearance(session, msg.get("appearance"))
    if error:
        await send(session.ws, "ERROR", message=error)
        return
    outfits_list = outfits.saved_slots(session._json_list("saved_outfits"))
    name = str(msg.get("name") or (outfits_list[slot] or {}).get("name") or f"Outfit {slot + 1}").strip()[:24]
    appearance["name"] = name or f"Outfit {slot + 1}"
    outfits_list[slot] = appearance
    WORLD.db.save_player_stats(session.player_id, saved_outfits=json.dumps(outfits_list))
    session.row = WORLD.db.get_player_by_id(session.player_id)
    await send(session.ws, "PLAYER_UPDATE", player=session.full_state())
    await send(session.ws, "CHAT_MSG", **{"from": "Mae", "text": f"Saved \"{appearance['name']}\" to wardrobe slot {slot + 1}."})


async def handle_shop_buy(session, msg):
    shop_id, item_id, qty = msg.get("shop_id"), msg.get("item_id"), max(1, int(msg.get("qty", 1)))
    shop = SHOPS.get(shop_id)
    if not shop:
        # A stale shop panel used to swallow the click entirely, so the player
        # saw nothing happen. Tell them the panel is out of date.
        await send(session.ws, "ERROR", message="That shop is no longer open — reopen it.")
        return
    if item_id not in shop["stock"]:
        await send(session.ws, "ERROR", message="That shop doesn't sell that.")
        return
    stock = shop["stock"][item_id]
    item = ITEMS.get(item_id) or {}
    # Bags, pouches and the quiver are bought once per character and never resold.
    if item.get("unique"):
        qty = 1
        if owns_unique_item(session, item_id):
            await send(session.ws, "ERROR",
                       message=f"You already own the {item.get('name', item_id)}. One per character is enough.")
            return
    # Pets: buy adds to collection and activates (re-buy of owned = free switch)
    if item.get("type") == "pet":
        qty = 1
        pet_id = item.get("pet_id")
        if pet_id not in PETS:
            return
        already = pet_id in session.owned_pets
        cost = 0 if already else reputation.buy_price(
            stock["price"], session.reputation, _shop_discount(session))
        tax = royal_treasury.buy_tax(cost)
        # Expensive pets (above purse cap) can be paid from bank coins
        if not already:
            purse = int(session.coins)
            bank = int(session.bank_coins)
            if purse + bank < cost + tax:
                await send(session.ws, "ERROR", message="You can't afford that (check purse + bank).")
                return
            take_purse = min(purse, cost + tax)
            session.coins -= take_purse
            session.bank_coins -= (cost + tax - take_purse)
        if not already and stock["qty"] < 99:
            stock["qty"] = max(0, stock["qty"] - 1)
        session.activate_pet(pet_id)
        WORLD.db.save_player_stats(
            session.player_id, coins=session.coins, bank_coins=session.bank_coins,
        )
        if not already:
            await _pay_royal_tax(session, "sales_tax_buy", tax)
        await send_shop_state(session, shop_id)
        await send(session.ws, "PLAYER_UPDATE", player=session.full_state())
        if already:
            msg_text = f"You call your {PETS[pet_id]['name']} to your side."
        else:
            msg_text = f"You adopt a {PETS[pet_id]['name']}! It will follow and fight for you."
        await send(session.ws, "CHAT_MSG", **{"from": "Pet Emporium", "text": msg_text})
        return
    qty = min(qty, stock["qty"])
    cost = reputation.buy_price(stock["price"], session.reputation, _shop_discount(session)) * qty
    tax = royal_treasury.buy_tax(cost)
    if qty <= 0 or session.coins < cost + tax:
        await send(session.ws, "ERROR", message="You can't afford that (price + royal tax).")
        return
    stock["qty"] -= qty
    session.coins -= cost + tax
    if not WORLD.add_item_to_inventory(session, item_id, qty):
        session.coins += cost + tax
        stock["qty"] += qty
        await send(session.ws, "ERROR", message="Your inventory is full.")
        return
    WORLD.db.save_player_stats(session.player_id, coins=session.coins)
    await _pay_royal_tax(session, "sales_tax_buy", tax)
    await send_shop_state(session, shop_id)
    await send(session.ws, "PLAYER_UPDATE", player=session.full_state())


async def handle_shop_sell(session, msg):
    shop_id, item_id, qty = msg.get("shop_id"), msg.get("item_id"), max(1, int(msg.get("qty", 1)))
    shop = SHOPS.get(shop_id)
    if not shop:
        await send(session.ws, "ERROR", message="That shop is no longer open — reopen it.")
        return
    if not shop.get("buys"):
        await send(session.ws, "ERROR", message="This shop doesn't buy anything.")
        return
    if not shop_will_buy(shop, item_id):
        item = ITEMS.get(item_id) or {}
        if item.get("unique"):
            await send(session.ws, "ERROR",
                       message=f"The {item.get('name', item_id)} is yours for good — bags never sell.")
            return
        await send(session.ws, "ERROR", message="This shop isn't interested in that.")
        return
    have = WORLD.count_item(session, item_id)
    qty = min(qty, have)
    if qty <= 0:
        return
    each = int(ITEMS[item_id]["value"] * 0.4)
    value = (reputation.sell_value(each, session.reputation) if each > 0 else 0) * qty
    tax = royal_treasury.sell_tax(value)
    WORLD.remove_item_qty(session, item_id, qty)
    gained, left = WORLD.add_coins(session, value - tax)
    await _pay_royal_tax(session, "sales_tax_sell", tax)
    if left:
        await send(session.ws, "ERROR", message=f"Purse full ({MAX_PURSE_COINS}). {left} coins lost — bank first next time.")
    await send_shop_state(session, shop_id)
    await send(session.ws, "PLAYER_UPDATE", player=session.full_state())


async def handle_equip(session, msg):
    slot_index = msg.get("slot_index")
    entry = session.inventory.get(slot_index)
    if not entry:
        return
    item = ITEMS[entry["item_id"]]
    eq_slot = item.get("equip_slot")
    if not eq_slot:
        await send(session.ws, "ERROR", message="You can't wear that.")
        return
    owner = (item.get("bound_username") or "").lower()
    if owner and session.username.lower() != owner:
        await send(session.ws, "ERROR", message="That item is bound to another character.")
        return
    # Ammo slot: Arrow Quiver (stores arrows) or legacy arrow-type selection.
    if eq_slot == "ammo":
        if entry["item_id"] == "arrow_quiver":
            old = session.equipment.get("ammo")
            # If legacy arrow type was selected, just clear it (arrows stay in inv)
            if old and old != "arrow_quiver" and (ITEMS.get(old) or {}).get("ammo_type") == "arrow":
                old = None
            session.equipment["ammo"] = "arrow_quiver"
            WORLD.db.set_equipment(session.player_id, "ammo", "arrow_quiver")
            WORLD.remove_item_qty(session, "arrow_quiver", 1)
            if old == "arrow_quiver":
                pass
            elif old:
                WORLD.add_item_to_inventory(session, old, 1)
            await send(session.ws, "PLAYER_UPDATE", player=session.full_state())
            await send(
                session.ws, "CHAT_MSG",
                **{"from": "You", "text": "You equip your Arrow Quiver. Use arrows to load it (1000 of each type)."},
            )
            return
        if item.get("ammo_type") == "arrow":
            # With quiver equipped: load arrows into it. Otherwise legacy ammo select.
            if session.quiver_equipped():
                qty = int(entry.get("qty") or 1)
                took = session.deposit_arrows_to_quiver(entry["item_id"], qty)
                await send(session.ws, "PLAYER_UPDATE", player=session.full_state())
                if took <= 0:
                    cur = int(session.quiver.get(entry["item_id"]) or 0)
                    await send(session.ws, "ERROR", message=f"Quiver is full of {item['name']}s ({cur}/{QUIVER_CAPACITY}).")
                else:
                    left = int(session.quiver.get(entry["item_id"]) or 0)
                    await send(
                        session.ws, "CHAT_MSG",
                        **{"from": "You", "text": f"You load {took} {item['name']}{'s' if took != 1 else ''} into your quiver ({left}/{QUIVER_CAPACITY})."},
                    )
                return
            session.equipment["ammo"] = entry["item_id"]
            WORLD.db.set_equipment(session.player_id, "ammo", entry["item_id"])
            await send(session.ws, "PLAYER_UPDATE", player=session.full_state())
            await send(
                session.ws, "CHAT_MSG",
                **{"from": "You", "text": f"You ready your {item['name']}s. (Tip: equip an Arrow Quiver to store {QUIVER_CAPACITY} of each type.)"},
            )
            return
        await send(session.ws, "ERROR", message="You can only equip arrows or an Arrow Quiver as ammo.")
        return
    # David, 23 Oct 2026: equipping armour no longer takes the outfit off. Partial armour keeps the outfit's
    # painted figure (stats apply, the gear isn't drawn); a full matching tier set shows its painted armour.
    # David, 23 Oct 2026: body and legs go on together and both are needed (gear_rules pair rule).
    if eq_slot in gear_rules.PAIR_SLOTS:
        found = gear_rules.find_partner_in_bag(entry["item_id"], session.inventory, ITEMS)
        if found is None:
            await send(session.ws, "ERROR", message=gear_rules.pair_need_message(entry["item_id"], ITEMS))
            return
        if found[0] != "solo":
            p_slot = gear_rules.pair_slot(eq_slot)
            p_id = found[1]
            p_old = session.equipment.get(p_slot)
            session.equipment[p_slot] = p_id
            WORLD.db.set_equipment(session.player_id, p_slot, p_id)
            WORLD.remove_item_qty(session, p_id, 1)
            if p_old:
                WORLD.add_item_to_inventory(session, p_old, 1)
            item = dict(item, name=f"{item['name']} and {ITEMS.get(p_id, {}).get('name', p_id)}")
    old = session.equipment.get(eq_slot)
    session.equipment[eq_slot] = entry["item_id"]
    WORLD.db.set_equipment(session.player_id, eq_slot, entry["item_id"])
    WORLD.remove_item_qty(session, entry["item_id"], 1)
    if old:
        WORLD.add_item_to_inventory(session, old, 1)
    auto_quiver = False
    if eq_slot != "weapon":
        pass
    elif is_bow(entry["item_id"]):
        session.combat_style = "archery"
        auto_quiver = session.auto_equip_quiver()
    elif session.combat_style == "archery":
        session.combat_style = getattr(session, "melee_style", None) or "attack"
    await send(session.ws, "PLAYER_UPDATE", player=session.full_state())
    await send(
        session.ws, "CHAT_MSG",
        **{"from": "You", "text": (
            f"You equip the {item['name']}"
            f"{' and your Arrow Quiver' if auto_quiver else ''}."
        )},
    )


async def _take_outfit_off(session):
    """Outfits and armour never mix: drop to the plain base clothes. Returns True when an outfit came off."""
    import json
    look = gear_rules.saved_look(session)
    if not gear_rules.wearing_outfit(look):
        return False
    base = gear_rules.base_look(look, getattr(session, "gender", "male"), outfits.items())
    WORLD.db.save_player_stats(session.player_id, appearance=json.dumps(base))
    session.row = WORLD.db.get_player_by_id(session.player_id)
    await broadcast_player_state(session)
    await send(session.ws, "CHAT_MSG", **{"from": "You", "text": gear_rules.OUTFIT_OFF_MSG})
    return True


def _bank_put(session, item_id, qty=1):
    if ITEMS.get(item_id, {}).get("stackable"):
        for bslot, bent in session.bank.items():
            if bent["item_id"] == item_id:
                bent["qty"] += qty
                WORLD.db.set_bank_slot(session.player_id, bslot, item_id, bent["qty"])
                return True
    for bslot in range(BANK_SLOTS):
        if bslot not in session.bank:
            session.bank[bslot] = {"item_id": item_id, "qty": qty}
            WORLD.db.set_bank_slot(session.player_id, bslot, item_id, qty)
            return True
    return False


async def _take_armour_off(session):
    """Putting an outfit on: every armour piece and weapon goes to the bag, or the bank if the bag is full.
    Returns an error string (and leaves the rest worn) only when neither has room. Nothing is lost."""
    banked = []
    for slot, item_id in gear_rules.worn_armour(session):
        if WORLD.add_item_to_inventory(session, item_id, 1):
            pass
        elif _bank_put(session, item_id, 1):
            banked.append(ITEMS.get(item_id, {}).get("name", item_id))
        else:
            await send(session.ws, "PLAYER_UPDATE", player=session.full_state())
            return "Your bag and bank are both full, so your armour can't come off for the outfit."
        session.equipment[slot] = None
        WORLD.db.set_equipment(session.player_id, slot, None)
        if slot == "weapon" and session.combat_style == "archery":
            session.combat_style = getattr(session, "melee_style", None) or "attack"
    if banked:
        await send(session.ws, "CHAT_MSG", **{"from": "Mae", "text": f"Your bag was full, so I sent your {', '.join(banked)} to the bank."})
    return None


async def _outfit_gear_check(session, appearance):
    """Before an outfit is worn: refuse inside a dungeon, otherwise take the armour off. Returns an error or None."""
    if not gear_rules.wearing_outfit(appearance):
        return None
    # David, 23 Oct 2026: the outfit is the look, armour gives the stats, so putting an outfit on keeps
    # every armour piece equipped (_take_armour_off is kept unused). The dungeon lock still applies.
    if gear_rules.worn_armour(session) and gear_rules.in_real_dungeon(session):
        return "You can't change into an outfit inside a dungeon."
    return None


async def handle_unequip(session, msg):
    slot_name = msg.get("equip_slot")
    item_id = session.equipment.get(slot_name)
    if not item_id:
        return
    # Ammo: unequipping a quiver returns the pouch; contents stay stored for next equip.
    if slot_name == "ammo":
        if item_id == "arrow_quiver":
            if not WORLD.add_item_to_inventory(session, "arrow_quiver", 1):
                await send(session.ws, "ERROR", message="Your inventory is full.")
                return
            session.equipment["ammo"] = None
            WORLD.db.set_equipment(session.player_id, "ammo", None)
            await send(session.ws, "PLAYER_UPDATE", player=session.full_state())
            total = session.quiver_total()
            msg = "You unequip your Arrow Quiver."
            if total:
                msg += f" ({total} arrows stay packed for next time.)"
            await send(session.ws, "CHAT_MSG", **{"from": "You", "text": msg})
            return
        session.equipment["ammo"] = None
        WORLD.db.set_equipment(session.player_id, "ammo", None)
        await send(session.ws, "PLAYER_UPDATE", player=session.full_state())
        await send(session.ws, "CHAT_MSG", **{"from": "You", "text": "You put your ammo away."})
        return
    p_slot = gear_rules.pair_slot(slot_name)
    p_id = session.equipment.get(p_slot) if p_slot else None
    if p_id:
        # Body and legs come off together: check room for both before moving either.
        free = sum(1 for i in range(int(INVENTORY_SIZE))
                   if i // INVENTORY_TAB_SIZE != 3 and i not in session.inventory)   # Bags tab holds bags only
        if free < 2:
            await send(session.ws, "ERROR", message=gear_rules.PAIR_ROOM_MSG)
            return
    if not WORLD.add_item_to_inventory(session, item_id, 1):
        await send(session.ws, "ERROR", message="Your inventory is full.")
        return
    name = ITEMS.get(item_id, {}).get("name", "item")
    session.equipment[slot_name] = None
    WORLD.db.set_equipment(session.player_id, slot_name, None)
    if p_id and WORLD.add_item_to_inventory(session, p_id, 1):
        session.equipment[p_slot] = None
        WORLD.db.set_equipment(session.player_id, p_slot, None)
        name = f"{name} and {ITEMS.get(p_id, {}).get('name', p_id)}"
    if slot_name == "weapon" and session.combat_style == "archery":
        session.combat_style = getattr(session, "melee_style", None) or "attack"
    await send(session.ws, "PLAYER_UPDATE", player=session.full_state())
    await send(session.ws, "CHAT_MSG", **{"from": "You", "text": f"You unequip the {name}."})


async def _use_key_on_nearby_door(session, item_id):
    """Open an adjacent locked door that takes this key. Same path as walking into it."""
    d = session.dungeon
    if not d:
        return False
    px, py = int(session.x), int(session.y)
    target = None
    kind = None
    if d.get("v2") == "depths":
        doors = ((d.get("spec") or {}).get("doors") or {})
        opened = d.get("opened") or []
        for ch, door in doors.items():
            if ch in opened or len(door) < 4:
                continue
            dx, dy, key = int(door[0]), int(door[1]), door[2]
            if key == item_id and max(abs(px - dx), abs(py - dy)) <= 1:
                target = (dx, dy)
                kind = "depths"
                break
    elif d.get("v2"):
        import void_v2
        opened = d.get("opened") or []
        for ch, door in void_v2.DOORS.items():
            if ch in opened:
                continue
            dx, dy, key = int(door[0]), int(door[1]), door[2]
            if key == item_id and max(abs(px - dx), abs(py - dy)) <= 1:
                target = (dx, dy)
                kind = "void"
                break
    if target is None:
        return False
    msg = {"x": target[0], "y": target[1]}
    if kind == "depths":
        import depths_v2
        await depths_v2.handle_interact(session, msg)
    else:
        import void_v2
        await void_v2.handle_interact(session, msg)
    return True


async def handle_use_item(session, msg):
    slot_index = msg.get("slot_index")
    entry = session.inventory.get(slot_index)
    if not entry:
        return
    item_id = entry["item_id"]
    item = ITEMS[item_id]
    action = (msg.get("action") or "use").lower()

    if action == "use" and item.get("type") == "key":
        if await _use_key_on_nearby_door(session, item_id):
            return
        await send(session.ws, "CHAT_MSG", **{
            "from": "You",
            "text": (
                f"Stand next to the door the {item['name']} opens, then click the key. "
                "Right-click it to drop it."
            ),
        })
        return

    # Explicit pack action (from inventory prompts) — deposit into the right bag
    if action == "pack":
        qty = int(entry.get("qty") or 1)
        if item.get("ammo_type") == "arrow":
            took = session.deposit_arrows_to_quiver(item_id, qty)
            await send(session.ws, "PLAYER_UPDATE", player=session.full_state())
            if took <= 0:
                cur = int(session.quiver.get(item_id) or 0)
                await send(session.ws, "ERROR", message=f"Quiver is full of {item['name']}s ({cur}/{QUIVER_CAPACITY}).")
            else:
                left = int(session.quiver.get(item_id) or 0)
                await send(session.ws, "CHAT_MSG", **{
                    "from": "You",
                    "text": f"You load {took} {item['name']}{'s' if took != 1 else ''} ({left}/{QUIVER_CAPACITY}).",
                })
            return
        if is_arrowtip(item_id):
            if not session.has_tip_box():
                await send(session.ws, "ERROR", message="You need an Arrowtip Box first (Elena sells them).")
                return
            took = session.deposit_tips_to_box(item_id, qty)
            await send(session.ws, "PLAYER_UPDATE", player=session.full_state())
            if took <= 0:
                cur = int(session.tip_box.get(item_id) or 0)
                await send(session.ws, "ERROR", message=f"Tip box is full of {item['name']} ({cur}/{TIP_BOX_CAPACITY}).")
            else:
                left = int(session.tip_box.get(item_id) or 0)
                await send(session.ws, "CHAT_MSG", **{
                    "from": "You",
                    "text": f"You pack {took} {item['name']} ({left}/{TIP_BOX_CAPACITY}).",
                })
            return
        if is_cooked_fish(item_id):
            if not session.has_food_bag():
                await send(session.ws, "ERROR", message="You need a Food Bag first (Kai or Mira sell them).")
                return
            took = session.deposit_cooked_to_food_bag(item_id, qty)
            await send(session.ws, "PLAYER_UPDATE", player=session.full_state())
            if took <= 0:
                cur = int(session.food_bag.get(item_id) or 0)
                await send(session.ws, "ERROR", message=f"Food bag is full of {item['name']} ({cur}/{FOOD_BAG_CAPACITY}).")
            else:
                left = int(session.food_bag.get(item_id) or 0)
                await send(session.ws, "CHAT_MSG", **{
                    "from": "You",
                    "text": f"You pack {took} {item['name']} ({left}/{FOOD_BAG_CAPACITY}).",
                })
            return
        if is_raw_fish(item_id):
            if not session.has_raw_bag():
                await send(session.ws, "ERROR", message="You need a Raw Food Bag first (Harbourreach Tackle sells them).")
                return
            took = session.deposit_raw_to_raw_bag(item_id, qty)
            await send(session.ws, "PLAYER_UPDATE", player=session.full_state())
            if took <= 0:
                cur = int(session.raw_bag.get(item_id) or 0)
                await send(session.ws, "ERROR", message=f"Raw bag is full of {item['name']} ({cur}/{RAW_BAG_CAPACITY}).")
            else:
                left = int(session.raw_bag.get(item_id) or 0)
                await send(session.ws, "CHAT_MSG", **{
                    "from": "You",
                    "text": f"You pack {took} {item['name']} ({left}/{RAW_BAG_CAPACITY}).",
                })
            return
        if is_mining_bag_item(item_id):
            if not session.has_mining_bag():
                await send(session.ws, "ERROR", message="You need a Mining Bag first (Gareth or the General Store).")
                return
            took = session.deposit_mining_bag(item_id, qty)
            await send(session.ws, "PLAYER_UPDATE", player=session.full_state())
            if took <= 0:
                cur = int(session.mining_bag.get(item_id) or 0)
                await send(session.ws, "ERROR", message=f"Mining bag is full of {item['name']} ({cur}/{RESOURCE_BAG_CAPACITY}).")
            else:
                left = int(session.mining_bag.get(item_id) or 0)
                await send(session.ws, "CHAT_MSG", **{
                    "from": "You",
                    "text": f"You pack {took} {item['name']} ({left}/{RESOURCE_BAG_CAPACITY}).",
                })
            return
        if is_log_item(item_id):
            if not session.has_log_bag():
                await send(session.ws, "ERROR", message="You need a Log Bag first (General Store or Elena).")
                return
            took = session.deposit_log_bag(item_id, qty)
            await send(session.ws, "PLAYER_UPDATE", player=session.full_state())
            if took <= 0:
                cur = int(session.log_bag.get(item_id) or 0)
                await send(session.ws, "ERROR", message=f"Log bag is full of {item['name']} ({cur}/{RESOURCE_BAG_CAPACITY}).")
            else:
                left = int(session.log_bag.get(item_id) or 0)
                await send(session.ws, "CHAT_MSG", **{
                    "from": "You",
                    "text": f"You pack {took} {item['name']} ({left}/{RESOURCE_BAG_CAPACITY}).",
                })
            return
        if is_fletch_pouch_item(item_id):
            if not session.has_fletch_pouch():
                await send(session.ws, "ERROR", message="You need a Fletching Pouch first (Nell or Elena sells them).")
                return
            took = session.deposit_fletch_pouch(item_id, qty)
            await send(session.ws, "PLAYER_UPDATE", player=session.full_state())
            cap = fletch_pouch_capacity(item_id)
            if took <= 0:
                cur = int(session.fletch_pouch.get(item_id) or 0)
                await send(session.ws, "ERROR", message=f"Fletching pouch is full of {item['name']} ({cur}/{cap}).")
            else:
                left = int(session.fletch_pouch.get(item_id) or 0)
                await send(session.ws, "CHAT_MSG", **{
                    "from": "You",
                    "text": f"You pack {took} {item['name']} ({left}/{cap}).",
                })
            return
        if is_potion_item(item_id):
            if not session.has_potion_pouch():
                await send(session.ws, "ERROR", message="You need a Potion Pouch first (Mira or the Lab).")
                return
            took = session.deposit_potion_pouch(item_id, qty)
            await send(session.ws, "PLAYER_UPDATE", player=session.full_state())
            if took <= 0:
                cur = int(session.potion_pouch.get(item_id) or 0)
                await send(session.ws, "ERROR", message=f"Potion pouch is full of {item['name']} ({cur}/{RESOURCE_BAG_CAPACITY}).")
            else:
                left = int(session.potion_pouch.get(item_id) or 0)
                await send(session.ws, "CHAT_MSG", **{
                    "from": "You",
                    "text": f"You pack {took} {item['name']} ({left}/{RESOURCE_BAG_CAPACITY}).",
                })
            return
        if is_gem_item(item_id):
            if not session.has_gem_bag():
                await send(session.ws, "ERROR", message="You need a Gem Bag first (Lira or the General Store).")
                return
            took = session.deposit_gem_bag(item_id, qty)
            await send(session.ws, "PLAYER_UPDATE", player=session.full_state())
            if took <= 0:
                cur = int(session.gem_bag.get(item_id) or 0)
                await send(session.ws, "ERROR", message=f"Gem bag is full of {item['name']} ({cur}/{RESOURCE_BAG_CAPACITY}).")
            else:
                left = int(session.gem_bag.get(item_id) or 0)
                await send(session.ws, "CHAT_MSG", **{
                    "from": "You",
                    "text": f"You pack {took} {item['name']} ({left}/{RESOURCE_BAG_CAPACITY}).",
                })
            return
        await send(session.ws, "ERROR", message="You can't pack that.")
        return

    if item.get("karma_xp"):
        # Right-click / use: bury exactly one bone from this stack
        WORLD.remove_item_qty(session, item_id, 1)
        await bury_bone_stack(session, item_id, 1, quiet=False)
        await send(session.ws, "PLAYER_UPDATE", player=session.full_state())
        return
    if item_id in FIRE_LOGS:
        await light_fire(session, item_id)
        return
    if item_id == "tinderbox":
        # Use tinderbox: light the first stack of logs found in inventory or log bag
        for lid in FIRE_LOGS:
            if session.available_craft_input(lid) > 0:
                await light_fire(session, lid)
                return
        await send(session.ws, "ERROR", message="You need logs to light a fire.")
        return
    if item.get("ammo_type") == "arrow":
        # Quiver storage is character-bound (equip only required to fire)
        qty = int(entry.get("qty") or 1)
        took = session.deposit_arrows_to_quiver(item_id, qty)
        await send(session.ws, "PLAYER_UPDATE", player=session.full_state())
        if took <= 0:
            cur = int(session.quiver.get(item_id) or 0)
            await send(session.ws, "ERROR", message=f"Quiver is full of {item['name']}s ({cur}/{QUIVER_CAPACITY}).")
        else:
            left = int(session.quiver.get(item_id) or 0)
            note = "" if session.quiver_equipped() else " Equip the quiver to fire them."
            await send(
                session.ws, "CHAT_MSG",
                **{"from": "You", "text": f"You load {took} {item['name']}{'s' if took != 1 else ''} ({left}/{QUIVER_CAPACITY}).{note}"},
            )
        return
    if is_arrowtip(item_id):
        if not session.has_tip_box():
            await send(
                session.ws, "ERROR",
                message="You need an Arrowtip Box first (Elena sells them).",
            )
            return
        qty = int(entry.get("qty") or 1)
        took = session.deposit_tips_to_box(item_id, qty)
        await send(session.ws, "PLAYER_UPDATE", player=session.full_state())
        if took <= 0:
            cur = int(session.tip_box.get(item_id) or 0)
            await send(session.ws, "ERROR", message=f"Tip box is full of {item['name']} ({cur}/{TIP_BOX_CAPACITY}).")
        else:
            left = int(session.tip_box.get(item_id) or 0)
            await send(
                session.ws, "CHAT_MSG",
                **{"from": "You", "text": f"You pack {took} {item['name']} ({left}/{TIP_BOX_CAPACITY})."},
            )
        return
    if item_id == "arrow_quiver" and action == "unpack":
        # A quiver's contents survive even if the quiver item is gone (traded away),
        # so unpacking without holding one would mint arrows from nothing.
        if not owns_unique_item(session, "arrow_quiver"):
            await send(session.ws, "ERROR", message="You have no quiver to unpack.")
            return
        moved, left = session._withdraw_bag_to_inventory(session.quiver, "quiver_contents")
        await send(session.ws, "PLAYER_UPDATE", player=session.full_state())
        await send(session.ws, "CHAT_MSG", **{
            "from": "You",
            "text": (f"You unpack {moved} arrows ({left} still in the quiver)." if moved
                     else ("Your quiver is empty." if left <= 0 else "No free inventory space.")),
        })
        return
    if item_id == "arrow_quiver":
        # Use quiver from pack: scoop every arrow stack into storage (even if not worn)
        deposited = 0
        for aid, it in list(ITEMS.items()):
            if it.get("ammo_type") != "arrow":
                continue
            have = WORLD.count_item(session, aid)
            if have <= 0:
                continue
            deposited += session.deposit_arrows_to_quiver(aid, have)
        await send(session.ws, "PLAYER_UPDATE", player=session.full_state())
        if deposited <= 0:
            await send(session.ws, "CHAT_MSG", **{
                "from": "You",
                "text": f"Your quiver holds {session.quiver_total()} arrows. Equip it in the Ammo slot to fire them.",
            })
        else:
            await send(session.ws, "CHAT_MSG", **{
                "from": "You",
                "text": f"You pack {deposited} arrows into the quiver ({session.quiver_total()} total). Equip it to shoot.",
            })
        return
    if item_id == "arrowtip_box":
        if action == "unpack":
            moved, left = session._withdraw_bag_to_inventory(session.tip_box, "tip_box_contents")
            await send(session.ws, "PLAYER_UPDATE", player=session.full_state())
            msg = (
                f"You unpack {moved} tips ({left} still in the box)."
                if moved else ("Your tip box is empty." if left <= 0 else "No free inventory space.")
            )
            await send(session.ws, "CHAT_MSG", **{"from": "You", "text": msg})
            return
        deposited = 0
        for tid, it in list(ITEMS.items()):
            if not is_arrowtip(tid):
                continue
            have = WORLD.count_item(session, tid)
            if have <= 0:
                continue
            deposited += session.deposit_tips_to_box(tid, have)
        await send(session.ws, "PLAYER_UPDATE", player=session.full_state())
        if deposited <= 0:
            await send(session.ws, "CHAT_MSG", **{
                "from": "You",
                "text": f"Your tip box holds {session.tip_box_total()} tips. Fletching uses them automatically.",
            })
        else:
            await send(session.ws, "CHAT_MSG", **{
                "from": "You",
                "text": f"You pack {deposited} tips into the box ({session.tip_box_total()} total).",
            })
        return
    if item_id == "food_bag":
        if action == "eat":
            ok, name, heal = session.eat_one_from_food_bag()
            await send(session.ws, "PLAYER_UPDATE", player=session.full_state())
            if not ok:
                await send(session.ws, "ERROR", message="Your food bag is empty.")
            elif heal <= 0:
                await send(session.ws, "CHAT_MSG", **{"from": "You", "text": f"You eat the {name}. It tastes awful."})
            else:
                await send(session.ws, "CHAT_MSG", **{
                    "from": "You",
                    "text": f"You eat a {name} from your bag and restore {heal} Hitpoints.",
                })
            return
        if action == "unpack":
            moved, left = session._withdraw_bag_to_inventory(session.food_bag, "food_bag_contents")
            await send(session.ws, "PLAYER_UPDATE", player=session.full_state())
            msg = (
                f"You unpack {moved} fish ({left} still in the bag)."
                if moved else ("Your food bag is empty." if left <= 0 else "No free inventory space.")
            )
            await send(session.ws, "CHAT_MSG", **{"from": "You", "text": msg})
            return
        deposited = 0
        for fid in list(COOKED_FISH_IDS):
            have = WORLD.count_item(session, fid)
            if have <= 0:
                continue
            deposited += session.deposit_cooked_to_food_bag(fid, have)
        await send(session.ws, "PLAYER_UPDATE", player=session.full_state())
        if deposited <= 0:
            await send(session.ws, "CHAT_MSG", **{
                "from": "You",
                "text": f"Your food bag holds {session.food_bag_total()} fish. Use it again with Eat to snack.",
            })
        else:
            await send(session.ws, "CHAT_MSG", **{
                "from": "You",
                "text": f"You pack {deposited} cooked fish into the bag ({session.food_bag_total()} total).",
            })
        return
    if item_id == "raw_food_bag":
        if action == "unpack":
            moved, left = session._withdraw_bag_to_inventory(session.raw_bag, "raw_bag_contents")
            await send(session.ws, "PLAYER_UPDATE", player=session.full_state())
            msg = (
                f"You unpack {moved} raw fish ({left} still in the bag)."
                if moved else ("Your raw bag is empty." if left <= 0 else "No free inventory space.")
            )
            await send(session.ws, "CHAT_MSG", **{"from": "You", "text": msg})
            return
        deposited = 0
        for fid in list(RAW_FISH_IDS):
            have = WORLD.count_item(session, fid)
            if have <= 0:
                continue
            deposited += session.deposit_raw_to_raw_bag(fid, have)
        await send(session.ws, "PLAYER_UPDATE", player=session.full_state())
        if deposited <= 0:
            await send(session.ws, "CHAT_MSG", **{
                "from": "You",
                "text": f"Your raw bag holds {session.raw_bag_total()} fish. Cooking uses them automatically.",
            })
        else:
            await send(session.ws, "CHAT_MSG", **{
                "from": "You",
                "text": f"You pack {deposited} raw fish into the bag ({session.raw_bag_total()} total).",
            })
        return
    if item_id == "mining_bag":
        if action == "unpack":
            moved, left = session._withdraw_bag_to_inventory(session.mining_bag, "mining_bag_contents")
            await send(session.ws, "PLAYER_UPDATE", player=session.full_state())
            msg = (
                f"You unpack {moved} ores/bars ({left} still in the bag)."
                if moved else ("Your mining bag is empty." if left <= 0 else "No free inventory space.")
            )
            await send(session.ws, "CHAT_MSG", **{"from": "You", "text": msg})
            return
        deposited = 0
        for iid in list(ITEMS):
            if not is_mining_bag_item(iid):
                continue
            have = WORLD.count_item(session, iid)
            if have > 0:
                deposited += session.deposit_mining_bag(iid, have)
        await send(session.ws, "PLAYER_UPDATE", player=session.full_state())
        tot = session._bag_total(session.mining_bag)
        msg = (
            f"You pack {deposited} ores/bars into the mining bag ({tot} total)."
            if deposited else f"Your mining bag holds {tot} items. Smelting/smithing use them first."
        )
        await send(session.ws, "CHAT_MSG", **{"from": "You", "text": msg})
        return
    if item_id == "log_bag":
        if action == "unpack":
            moved, left = session._withdraw_bag_to_inventory(session.log_bag, "log_bag_contents")
            await send(session.ws, "PLAYER_UPDATE", player=session.full_state())
            msg = (
                f"You unpack {moved} logs ({left} still in the bag)."
                if moved else ("Your log bag is empty." if left <= 0 else "No free inventory space.")
            )
            await send(session.ws, "CHAT_MSG", **{"from": "You", "text": msg})
            return
        deposited = 0
        for iid in FIRE_LOGS:
            have = WORLD.count_item(session, iid)
            if have > 0:
                deposited += session.deposit_log_bag(iid, have)
        await send(session.ws, "PLAYER_UPDATE", player=session.full_state())
        tot = session._bag_total(session.log_bag)
        msg = (
            f"You pack {deposited} logs into the bag ({tot} total)."
            if deposited else f"Your log bag holds {tot} logs. Firemaking/fletching use them first."
        )
        await send(session.ws, "CHAT_MSG", **{"from": "You", "text": msg})
        return
    if item_id == "fletch_pouch":
        if action == "unpack":
            moved, left = session._withdraw_bag_to_inventory(session.fletch_pouch, "fletch_pouch_contents")
            await send(session.ws, "PLAYER_UPDATE", player=session.full_state())
            msg = (
                f"You unpack {moved} supplies ({left} still in the pouch)."
                if moved else ("Your fletching pouch is empty." if left <= 0 else "No free inventory space.")
            )
            await send(session.ws, "CHAT_MSG", **{"from": "You", "text": msg})
            return
        deposited = 0
        for iid in FLETCH_POUCH_IDS:
            have = WORLD.count_item(session, iid)
            if have > 0:
                deposited += session.deposit_fletch_pouch(iid, have)
        await send(session.ws, "PLAYER_UPDATE", player=session.full_state())
        tot = session._bag_total(session.fletch_pouch)
        msg = (
            f"You pack {deposited} fletching supplies ({tot} total)."
            if deposited else f"Your fletching pouch holds {tot} items. Fletching uses them first."
        )
        await send(session.ws, "CHAT_MSG", **{"from": "You", "text": msg})
        return
    if item_id == "potion_pouch":
        if action == "unpack":
            moved, left = session._withdraw_bag_to_inventory(session.potion_pouch, "potion_pouch_contents")
            await send(session.ws, "PLAYER_UPDATE", player=session.full_state())
            msg = (
                f"You unpack {moved} potions ({left} still in the pouch)."
                if moved else ("Your potion pouch is empty." if left <= 0 else "No free inventory space.")
            )
            await send(session.ws, "CHAT_MSG", **{"from": "You", "text": msg})
            return
        deposited = 0
        for iid, it in ITEMS.items():
            if not is_potion_item(iid):
                continue
            have = WORLD.count_item(session, iid)
            if have > 0:
                deposited += session.deposit_potion_pouch(iid, have)
        await send(session.ws, "PLAYER_UPDATE", player=session.full_state())
        tot = session._bag_total(session.potion_pouch)
        msg = (
            f"You pack {deposited} potions ({tot} total)."
            if deposited else f"Your potion pouch holds {tot} potions."
        )
        await send(session.ws, "CHAT_MSG", **{"from": "You", "text": msg})
        return
    if item_id == "gem_bag":
        if action == "unpack":
            moved, left = session._withdraw_bag_to_inventory(session.gem_bag, "gem_bag_contents")
            await send(session.ws, "PLAYER_UPDATE", player=session.full_state())
            msg = (
                f"You unpack {moved} gems ({left} still in the bag)."
                if moved else ("Your gem bag is empty." if left <= 0 else "No free inventory space.")
            )
            await send(session.ws, "CHAT_MSG", **{"from": "You", "text": msg})
            return
        deposited = 0
        for iid, it in ITEMS.items():
            if not is_gem_item(iid):
                continue
            have = WORLD.count_item(session, iid)
            if have > 0:
                deposited += session.deposit_gem_bag(iid, have)
        await send(session.ws, "PLAYER_UPDATE", player=session.full_state())
        tot = session._bag_total(session.gem_bag)
        msg = (
            f"You pack {deposited} gems into the bag ({tot} total)."
            if deposited else f"Your gem bag holds {tot} gems. Anvil jewelry crafting uses them first."
        )
        await send(session.ws, "CHAT_MSG", **{"from": "You", "text": msg})
        return
    if item["type"] == "food":
        heal = item.get("heal", 0)
        if heal <= 0:
            WORLD.remove_item_qty(session, item_id, 1)
            await send(session.ws, "PLAYER_UPDATE", player=session.full_state())
            await send(
                session.ws, "CHAT_MSG",
                **{"from": "You", "text": f"You eat the {item['name']}. It tastes awful."},
            )
            return
        # At full health the food was eaten for nothing: the message even
        # claimed it restored HEAL hitpoints when it restored none. Refuse and
        # keep the meal.
        if session.hp >= session.max_hp():
            await send(session.ws, "ERROR", message="You're already at full health.")
            return
        before = session.hp
        session.hp = min(session.max_hp(), session.hp + heal)
        restored = session.hp - before
        WORLD.remove_item_qty(session, item_id, 1)
        WORLD.db.save_player_stats(session.player_id, hp=session.hp)
        await send(session.ws, "PLAYER_UPDATE", player=session.full_state())
        await send(
            session.ws, "CHAT_MSG",
            **{"from": "You", "text": f"You eat the {item['name']} and restore {restored} Hitpoints."},
        )
        return
    if item["type"] == "potion":
        skill = item.get("boost_skill")
        amount = int(item.get("boost_amount") or 0)
        seconds = int(item.get("boost_seconds") or 60)
        if skill not in ("attack", "strength", "defence") or amount <= 0:
            await send(session.ws, "ERROR", message="The potion does nothing.")
            return
        WORLD.remove_item_qty(session, item_id, 1)
        session.apply_stat_boost(skill, amount, seconds)
        await send(session.ws, "PLAYER_UPDATE", player=session.full_state())
        label = skill.title()
        await send(
            session.ws, "CHAT_MSG",
            **{
                "from": "You",
                "text": f"You drink the {item['name']}. {label} +{amount} for {seconds} seconds!",
            },
        )
        return
    await send(session.ws, "ERROR", message="Nothing happens.")


async def handle_quick_consume(session, msg):
    """Combat quick-use: food, health potion, or Att/Str/Def potion from inv or bags."""
    kind = str(msg.get("kind") or "").lower()
    if kind == "food":
        if session.hp >= session.max_hp():
            await send(session.ws, "ERROR", message="You're already at full health.")
            return
        best_slot = None
        best_heal = 0
        for slot, entry in session.inventory.items():
            iid = entry.get("item_id")
            it = ITEMS.get(iid) or {}
            if it.get("type") != "food" or iid == "health_potion":
                continue
            heal = int(it.get("heal") or 0)
            if heal > best_heal:
                best_heal = heal
                best_slot = slot
        if best_slot is not None:
            entry = session.inventory[best_slot]
            item = ITEMS[entry["item_id"]]
            heal = int(item.get("heal") or 0)
            # Refuse at full health: eating used to consume the food for no
            # benefit at all, quietly costing the player a meal.
            if session.hp >= session.max_hp():
                await send(session.ws, "ERROR", message="You're already at full health.")
                return
            session.hp = min(session.max_hp(), session.hp + heal)
            WORLD.remove_item_qty(session, entry["item_id"], 1)
            WORLD.db.save_player_stats(session.player_id, hp=session.hp)
            await send(session.ws, "PLAYER_UPDATE", player=session.full_state())
            await send(session.ws, "CHAT_MSG", **{
                "from": "You",
                "text": f"You eat the {item['name']} and restore {heal} Hitpoints.",
            })
            return
        if session.has_food_bag() and session.food_bag_total() > 0:
            if session.hp >= session.max_hp():
                await send(session.ws, "ERROR", message="You're already at full health.")
                return
            ok, name, heal = session.eat_one_from_food_bag()
            await send(session.ws, "PLAYER_UPDATE", player=session.full_state())
            if ok:
                await send(session.ws, "CHAT_MSG", **{
                    "from": "You",
                    "text": f"You eat {name} from your food bag (+{heal} HP).",
                })
            return
        await send(session.ws, "ERROR", message="You have no food to eat.")
        return

    if kind == "health":
        if session.hp >= session.max_hp():
            await send(session.ws, "ERROR", message="You're already at full health.")
            return
        if session.count_owned_item("health_potion") <= 0:
            await send(session.ws, "ERROR", message="You have no health potions.")
            return
        if session.hp >= session.max_hp():
            # A potion drunk at full health used to vanish with no effect.
            await send(session.ws, "ERROR", message="You're already at full health.")
            return
        if not session.take_one_owned_item("health_potion"):
            await send(session.ws, "ERROR", message="You have no health potions.")
            return
        item = ITEMS["health_potion"]
        heal = int(item.get("heal") or 0)
        session.hp = min(session.max_hp(), session.hp + heal)
        WORLD.db.save_player_stats(session.player_id, hp=session.hp)
        await send(session.ws, "PLAYER_UPDATE", player=session.full_state())
        await send(session.ws, "CHAT_MSG", **{
            "from": "You",
            "text": f"You drink a Health Potion and restore {heal} Hitpoints.",
        })
        return

    if kind in ("attack", "strength", "defence"):
        pid = session.best_boost_potion_id(kind)
        if not pid:
            await send(session.ws, "ERROR", message=f"You have no {kind} potions.")
            return
        item = ITEMS[pid]
        if not session.take_one_owned_item(pid):
            await send(session.ws, "ERROR", message=f"You have no {kind} potions.")
            return
        amount = int(item.get("boost_amount") or 0)
        seconds = int(item.get("boost_seconds") or 60)
        session.apply_stat_boost(kind, amount, seconds)
        await send(session.ws, "PLAYER_UPDATE", player=session.full_state())
        await send(session.ws, "CHAT_MSG", **{
            "from": "You",
            "text": f"You drink the {item['name']}. {kind.title()} +{amount} for {seconds} seconds!",
        })
        return

    await send(session.ws, "ERROR", message="Nothing happens.")


async def handle_drop(session, msg):
    try:
        slot_index = int(msg.get("slot_index"))
    except (TypeError, ValueError):
        return
    qty = max(1, int(msg.get("qty", 1)))
    entry = session.inventory.get(slot_index)
    if not entry:
        return
    qty = min(qty, entry["qty"])
    item_id = entry["item_id"]
    if not item_is_tradeable(item_id):
        if (ITEMS.get(item_id) or {}).get("unique"):
            await send(session.ws, "ERROR",
                       message=f"The {ITEMS[item_id]['name']} is yours for good — you can't drop or trade it.")
            return
        await send(session.ws, "ERROR", message="You can't drop that.")
        return
    WORLD.remove_item_qty(session, item_id, qty)
    if session.dungeon and session.dungeon.get("v2"):
        import void_v2
        void_v2.place_ground(session, item_id, qty)
    else:
        WORLD.ground_items.setdefault((session.x, session.y), []).append(_ground_drop(item_id, qty))
    name = ITEMS.get(item_id, {}).get("name", "item")
    await send(session.ws, "PLAYER_UPDATE", player=session.full_state())
    if qty > 1:
        await send(session.ws, "CHAT_MSG", **{"from": "You", "text": f"You drop {qty}x {name}."})
    else:
        await send(session.ws, "CHAT_MSG", **{"from": "You", "text": f"You drop the {name}."})


async def handle_inv_move(session, msg):
    """Rearrange inventory: move into empty slot, swap, or merge stackables."""
    try:
        from_slot = int(msg.get("from_slot"))
        to_slot = int(msg.get("to_slot"))
    except (TypeError, ValueError):
        return
    if from_slot == to_slot:
        return
    if not (0 <= from_slot < INVENTORY_SIZE and 0 <= to_slot < INVENTORY_SIZE):
        return
    if session.trade_partner_id:
        await send(session.ws, "ERROR", message="Finish or cancel the trade first.")
        return
    src = session.inventory.get(from_slot)
    if not src:
        return
    dst = session.inventory.get(to_slot)
    if dst is None:
        session.inventory[to_slot] = src
        del session.inventory[from_slot]
        WORLD.db.clear_slot(session.player_id, from_slot)
        WORLD.db.add_item_to_slot(session.player_id, to_slot, src["item_id"], src["qty"])
    elif dst["item_id"] == src["item_id"] and ITEMS.get(src["item_id"], {}).get("stackable"):
        dst["qty"] += src["qty"]
        del session.inventory[from_slot]
        WORLD.db.clear_slot(session.player_id, from_slot)
        WORLD.db.add_item_to_slot(session.player_id, to_slot, dst["item_id"], dst["qty"])
    else:
        session.inventory[from_slot] = dst
        session.inventory[to_slot] = src
        WORLD.db.add_item_to_slot(session.player_id, from_slot, dst["item_id"], dst["qty"])
        WORLD.db.add_item_to_slot(session.player_id, to_slot, src["item_id"], src["qty"])
    await send(session.ws, "PLAYER_UPDATE", player=session.full_state())


async def handle_pickup(session, msg):
    """Manual pickup: take one stack, or all=True for the whole pile.
    Item types on the never-pickup list stay on the ground unless this click forces one.
    """
    expire_ground_items()
    if session.dungeon and session.dungeon.get("v2"):
        import void_v2
        await void_v2.handle_pickup(session, msg)
        return
    await vacuum_ground_loot(session, quiet=True)
    take_all = bool(msg.get("all"))
    force = bool(msg.get("force"))
    want = msg.get("item_id")
    picked = 0
    while True:
        items_here = WORLD.ground_items.get((session.x, session.y))
        if not items_here:
            break
        idx = None
        for i, cand in enumerate(items_here):
            cid = cand["item_id"]
            if want and cid != want:
                continue
            if pickup_ignored(session, cid) and not (force and cid == want):
                continue
            idx = i
            break
        if idx is None:
            break
        entry = items_here.pop(idx)
        item_id, qty = entry["item_id"], entry["qty"]
        if item_id == "coins":
            gained, left = WORLD.add_coins(session, qty)
            if left:
                items_here.insert(idx, {"item_id": "coins", "qty": left})
            if gained:
                picked += 1
                if not take_all:
                    await send(session.ws, "CHAT_MSG", **{"from": "World", "text": f"You pick up {gained} coins."})
            if left or not take_all:
                break
        elif ITEMS.get(item_id, {}).get("karma_xp"):
            await bury_bone_stack(session, item_id, qty, quiet=False)
            picked += 1
            if not take_all:
                break
        elif item_id in ORE_ITEM_IDS and WORLD.count_ores(session) + qty > MAX_ORES:
            items_here.insert(idx, entry)
            await send(session.ws, "ERROR", message=f"You can't carry more than {MAX_ORES} ores.")
            break
        elif not WORLD.add_item_to_inventory(session, item_id, qty):
            items_here.insert(idx, entry)
            await send(session.ws, "ERROR", message="Your inventory is full.")
            break
        else:
            picked += 1
            if not take_all:
                await send(session.ws, "CHAT_MSG", **{
                    "from": "World", "text": f"You pick up {ITEMS[item_id]['name']}.",
                })
                break
        items_here = WORLD.ground_items.get((session.x, session.y))
        if items_here is not None and not items_here:
            del WORLD.ground_items[(session.x, session.y)]
        if not take_all:
            break
    items_here = WORLD.ground_items.get((session.x, session.y))
    if items_here is not None and not items_here:
        del WORLD.ground_items[(session.x, session.y)]
    if take_all and picked:
        await send(session.ws, "CHAT_MSG", **{
            "from": "World",
            "text": f"You pick up {picked} stack{'s' if picked != 1 else ''}.",
        })
    await send(session.ws, "PLAYER_UPDATE", player=session.full_state())


async def handle_quest_accept(session, msg):
    quest_id = msg.get("quest_id")
    qdef = QUESTS.get(quest_id)
    if not qdef or quest_id in session.quests:
        return
    if not quest_prereqs_met(session, qdef):
        await send(session.ws, "ERROR", message="You haven't finished the required quest yet.")
        return
    session.quests[quest_id] = {"status": "active", "progress": 0}
    WORLD.db.set_quest_progress(session.player_id, quest_id, "active", 0)
    if qdef["type"] == "guild":
        import clans
        if clans.clan_of(session.player_id):
            await guild_tutorial_event(session, "guild", quiet=True)
    await send(session.ws, "QUEST_LOG", quests={qid: quest_status_for(session, qid) for qid in QUESTS})


GUILD_STEP_BITS = {"guild": 1, "deposit": 2}


async def guild_tutorial_event(session, step, quiet=False):
    """guild_basics steps come from server events: joining/creating and depositing."""
    prog = session.quests.get("guild_basics")
    if not prog or prog.get("status") != "active":
        return
    prog["progress"] = int(prog.get("progress") or 0) | GUILD_STEP_BITS[step]
    if prog["progress"] == 3:
        prog["status"] = "ready"
        if not quiet:
            await send(session.ws, "CHAT_MSG", **{"from": "Guildmaster Ysolde",
                       "text": "Well done. Come back to me at the castle gate for your reward."})
    WORLD.db.set_quest_progress(session.player_id, "guild_basics", prog["status"], prog["progress"])
    session.quest_log_dirty = True


async def handle_quest_turnin(session, msg):
    quest_id = msg.get("quest_id")
    qdef = QUESTS.get(quest_id)
    prog = session.quests.get(quest_id)
    if not qdef or not prog:
        return

    rewards = qdef.get("rewards") or {}
    need_slots = reward_inv_slots_needed(session, rewards)
    free = INVENTORY_SIZE - len(session.inventory)
    if need_slots and free < need_slots:
        await send(session.ws, "ERROR", message=(
            f"Inventory full — free {need_slots} slot{'s' if need_slots != 1 else ''} "
            "before turning this in."
        ))
        return

    if qdef["type"] == "collect":
        have = session.available_craft_input(qdef["target"])
        if have < qdef["count"]:
            await send(session.ws, "ERROR", message=f"You need {qdef['count']}x {ITEMS[qdef['target']]['name']}.")
            return
        session.consume_craft_input(qdef["target"], qdef["count"])
    elif qdef["type"] == "collect_multi":
        for iid, need in qdef["targets"].items():
            if session.available_craft_input(iid) < need:
                await send(session.ws, "ERROR", message=f"You need {need}x {ITEMS[iid]['name']}.")
                return
        for iid, need in qdef["targets"].items():
            session.consume_craft_input(iid, need)
    elif qdef["type"] in ("kill", "find_npc", "guild"):
        if prog["status"] != "ready":
            await send(session.ws, "ERROR", message="You haven't finished this quest yet.")
            return
    elif qdef["type"] == "oath":
        import fairy_village
        _lines, ready = fairy_village.oath_progress(session)
        if not ready:
            await send(session.ws, "ERROR", message="The Moonwater Oath is not yet fulfilled.")
            return

    # Grant all item rewards without aborting mid-list (slots pre-checked).
    await grant_quest_rewards(session, rewards)

    prog["status"] = "complete"
    WORLD.db.set_quest_progress(session.player_id, quest_id, "complete", prog.get("progress", 0))
    qp = session.quest_points()
    qp_gain = int(qdef.get("quest_points") or 0)
    await send(session.ws, "QUEST_COMPLETE", quest_id=quest_id, rewards=rewards, quest_points=qp_gain, total_quest_points=qp)
    await send(session.ws, "PLAYER_UPDATE", player=session.full_state())
    await send(session.ws, "QUEST_LOG", quests={qid: quest_status_for(session, qid) for qid in QUESTS})
    if qp_gain:
        await send(session.ws, "CHAT_MSG", **{
            "from": "Magic",
            "text": f"+{qp_gain} quest point{'s' if qp_gain != 1 else ''} (total {qp}). Check the Magic tab for new abilities.",
        })


async def grant_quest_rewards(session, rewards):
    """Apply coins / xp / single item / item list rewards from a quest def.

    Every quest completion goes through here, so it also grants standing and Charisma.
    """
    await social_event(
        session, "quest", rep=int((rewards or {}).get("reputation", reputation.REP_QUEST)),
        xp={"charisma": int((rewards or {}).get("charisma_xp", reputation.CHARISMA_QUEST_XP))},
    )
    if not rewards:
        return
    if "coins" in rewards:
        gained, left = WORLD.add_coins(session, rewards["coins"])
        if left:
            await send(session.ws, "CHAT_MSG", **{
                "from": "World", "text": f"Purse full — {left} reward coins couldn't fit.",
            })
    if "xp" in rewards:
        for skill, amount in rewards["xp"].items():
            WORLD.grant_xp(session, skill, amount)
    entries = []
    if "item" in rewards:
        entries.append(rewards["item"])
    if "items" in rewards:
        entries.extend(rewards["items"])
    for iid, qty in entries:
        if not WORLD.add_item_to_inventory(session, iid, qty):
            await send(session.ws, "CHAT_MSG", **{
                "from": "World",
                "text": f"Inventory full — could not receive {ITEMS.get(iid, {}).get('name', iid)}.",
            })


# --- Trading -----------------------------------------------------------
async def handle_trade_request(session, msg):
    target_id = msg.get("target_player_id")
    target = WORLD.sessions.get(target_id)
    if not target or target_id == session.player_id:
        return
    if not adjacent_or_same(session.x, session.y, target.x, target.y):
        await send(session.ws, "ERROR", message="You need to be next to them to trade.")
        return
    await send(target.ws, "TRADE_REQUEST_IN", from_player_id=session.player_id, from_name=session.char_name)


async def handle_trade_respond(session, msg, from_player_id):
    other = WORLD.sessions.get(from_player_id)
    if not other:
        return
    if not msg.get("accept"):
        await send(other.ws, "TRADE_CANCELLED", reason=f"{session.char_name} declined.")
        return
    session.trade_partner_id = other.player_id
    other.trade_partner_id = session.player_id
    session.trade_offer, other.trade_offer = {}, {}
    session.trade_confirmed = other.trade_confirmed = False
    await push_trade_state(session)
    await push_trade_state(other)


async def push_trade_state(session):
    other = WORLD.sessions.get(session.trade_partner_id)
    if not other:
        return
    await send(
        session.ws, "TRADE_STATE", other_name=other.char_name,
        your_offer=session.trade_offer, other_offer=other.trade_offer,
        your_confirmed=session.trade_confirmed, other_confirmed=other.trade_confirmed,
    )


async def handle_trade_offer(session, msg):
    other = WORLD.sessions.get(session.trade_partner_id)
    if not other:
        return
    offer = {}
    for item in msg.get("items", []):
        slot = item.get("slot_index")
        entry = session.inventory.get(slot)
        if not entry:
            continue
        if not item_is_tradeable(entry["item_id"]):
            await send(session.ws, "ERROR", message=f"{ITEMS[entry['item_id']]['name']} can't be traded.")
            continue
        qty = min(item.get("qty", entry["qty"]), entry["qty"])
        offer[slot] = qty
    session.trade_offer = offer
    session.trade_confirmed = False
    other.trade_confirmed = False
    await push_trade_state(session)
    await push_trade_state(other)


async def handle_trade_confirm(session, msg):
    other = WORLD.sessions.get(session.trade_partner_id)
    if not other:
        return
    session.trade_confirmed = True
    await push_trade_state(other)
    await push_trade_state(session)
    if session.trade_confirmed and other.trade_confirmed:
        await execute_trade(session, other)


async def execute_trade(a, b):
    # Validate both sides still have what they offered.
    for giver, offer in ((a, a.trade_offer), (b, b.trade_offer)):
        for slot, qty in offer.items():
            entry = giver.inventory.get(slot)
            if not entry or entry["qty"] < qty:
                await handle_trade_cancel(a, {})
                return
    a_items = [(a.inventory[slot]["item_id"], qty) for slot, qty in a.trade_offer.items()]
    b_items = [(b.inventory[slot]["item_id"], qty) for slot, qty in b.trade_offer.items()]
    for slot, qty in a.trade_offer.items():
        WORLD.remove_item_qty(a, a.inventory[slot]["item_id"], qty)
    for slot, qty in b.trade_offer.items():
        WORLD.remove_item_qty(b, b.inventory[slot]["item_id"], qty)
    for item_id, qty in b_items:
        WORLD.add_item_to_inventory(a, item_id, qty)
    for item_id, qty in a_items:
        WORLD.add_item_to_inventory(b, item_id, qty)
    for s in (a, b):
        s.trade_partner_id = None
        s.trade_offer = {}
        s.trade_confirmed = False
        await send(s.ws, "TRADE_DONE")
        await send(s.ws, "PLAYER_UPDATE", player=s.full_state())


async def handle_trade_cancel(session, msg):
    other = WORLD.sessions.get(session.trade_partner_id)
    session.trade_partner_id = None
    session.trade_offer = {}
    session.trade_confirmed = False
    if other:
        other.trade_partner_id = None
        other.trade_offer = {}
        other.trade_confirmed = False
        await send(other.ws, "TRADE_CANCELLED", reason=f"{session.char_name} cancelled the trade.")


# ---------------------------------------------------------------------------
# Connection lifecycle
# ---------------------------------------------------------------------------
async def handler(ws):
    session = None
    try:
        async for raw in ws:
            try:
                msg = json.loads(raw)
            except json.JSONDecodeError:
                continue
            mtype = msg.get("type")

            if session is None:
                if mtype == "LOGIN":
                    await handle_login(ws, msg, is_register=False)
                    session = WORLD.find_session_by_ws(ws)
                elif mtype == "CREATE_CHARACTER":
                    await handle_login(ws, msg, is_register=True)
                    session = WORLD.find_session_by_ws(ws)
                elif mtype == "LEADERBOARD":
                    await handle_leaderboard(ws, msg)
                continue

            if mtype == "INPUT_PING":
                await idle_input_ping(session, msg)
                continue
            if mtype not in PASSIVE_MESSAGE_TYPES:
                await note_real_input(session)

            if mtype == "LEADERBOARD":
                await handle_leaderboard(ws, msg)
            elif mtype == "ALLOCATE_STATS":
                await handle_allocate_stats(session, msg)
            elif not session.stats_allocated:
                await send(session.ws, "ERROR", message="Choose your starting stats first.")
            elif mtype == "MOVE":
                await handle_move(session, msg)
            elif mtype == "CHAT":
                await handle_chat(session, msg)
            elif mtype == "ATTACK":
                await handle_attack(session, msg)
            elif mtype == "SET_PK":
                await handle_set_pk(session, msg)
            elif mtype == "STOP_ATTACK":
                await handle_stop_attack(session, msg)
            elif mtype == "ENTER_DUNGEON":
                await handle_enter_dungeon(session, msg)
            elif mtype == "LEAVE_DUNGEON":
                await handle_leave_dungeon(session, msg)
            elif mtype == "DUNGEON_INTERACT":
                if session.dungeon and session.dungeon.get("v2") == "depths":
                    import depths_v2
                    await depths_v2.handle_interact(session, msg)
                else:
                    import void_v2
                    await void_v2.handle_interact(session, msg)
            elif mtype == "SET_COMBAT_STYLE":
                await handle_set_combat_style(session, msg)
            elif mtype == "CAST_MAGIC":
                await handle_cast_magic(session, msg)
            elif mtype == "SET_MAGIC_MODE":
                await handle_set_magic_mode(session, msg)
            elif mtype == "GATHER":
                await handle_gather(session, msg)
            elif mtype == "CRAFT":
                await handle_craft(session, msg)
            elif mtype == "TALK":
                await handle_talk(session, msg)
            elif mtype == "PERSUADE":
                await handle_persuade(session, msg)
            elif mtype == "NPC_OPTION":
                await handle_npc_option(session, msg)
            elif mtype == "WELCOME_SKIP":
                await welcome_skip(session)
            elif mtype in ("COURT_CHOOSE", "NEWS_BOARD", "KINGDOM_STATE"):
                await handle_politics_msg(session, mtype, msg)
            elif isinstance(mtype, str) and mtype.startswith("RULE_"):
                await handle_rule(session, mtype, msg)
            elif mtype == "TELEPORT":
                await handle_teleport(session, msg)
            elif mtype == "STAIR":
                await handle_stair(session, msg)
            elif mtype == "HOUSING_OPEN":
                await _housing.open_lots(session)
            elif mtype == "HOUSING_BUY":
                await _housing.buy(session, msg.get("key"))
            elif mtype == "CASTLE_OPTION":
                import castle_owners
                await castle_owners.choose(session, msg.get("npc_id"), msg.get("node"), msg.get("option_id"))
            elif mtype == "SHOP_BUY":
                await handle_shop_buy(session, msg)
            elif mtype == "SHOP_SELL":
                await handle_shop_sell(session, msg)
            elif mtype == "SET_PET":
                await handle_set_pet(session, msg)
            elif mtype == "TOGGLE_HD_PLAYER":
                await handle_toggle_hd_player(session, msg)
            elif mtype == "UPDATE_APPEARANCE":
                await handle_update_appearance(session, msg)
            elif mtype == "BUY_COSMETICS":
                await handle_buy_cosmetics(session, msg)
            elif mtype == "SAVE_OUTFIT":
                await handle_save_outfit(session, msg)
            elif mtype in ("BUY_PALETTE", "UPGRADE_OUTFIT"):
                # Colour options and Plain/Fine/Regal were removed (SIDEBAR_DESIGN §9).
                await send(session.ws, "ERROR", message="Mae no longer sells colours or upgrades: each set is shown as painted.")
            elif mtype == "BUY_COLLECTION_SET":
                await handle_buy_collection_set(session, msg)
            elif mtype == "SET_GENDER":
                await handle_set_gender(session, msg)
            elif mtype == "EQUIP":
                await handle_equip(session, msg)
            elif mtype == "UNEQUIP":
                await handle_unequip(session, msg)
            elif mtype == "USE_ITEM":
                await handle_use_item(session, msg)
            elif mtype == "QUICK_CONSUME":
                await handle_quick_consume(session, msg)
            elif mtype == "DROP":
                await handle_drop(session, msg)
            elif mtype == "INV_MOVE":
                await handle_inv_move(session, msg)
            elif mtype == "PICKUP":
                await handle_pickup(session, msg)
            elif mtype == "SET_OPTION":
                await handle_set_option(session, msg)
            elif mtype == "BANK_OPEN":
                await handle_bank_open(session, msg)
            elif mtype == "BANK_DEPOSIT":
                await handle_bank_deposit(session, msg)
            elif mtype == "BANK_WITHDRAW":
                await handle_bank_withdraw(session, msg)
            elif mtype == "QUEST_ACCEPT":
                await handle_quest_accept(session, msg)
            elif mtype == "QUEST_TURNIN":
                await handle_quest_turnin(session, msg)
            elif mtype == "WISH":
                await handle_wish(session, msg)
            elif mtype == "WISH_STAT":
                await handle_wish_stat(session, msg)
            elif mtype == "TRADE_REQUEST":
                await handle_trade_request(session, msg)
            elif mtype == "TRADE_RESPOND":
                await handle_trade_respond(session, msg, msg.get("from_player_id"))
            elif mtype == "TRADE_OFFER":
                await handle_trade_offer(session, msg)
            elif mtype == "TRADE_CONFIRM":
                await handle_trade_confirm(session, msg)
            elif mtype == "TRADE_CANCEL":
                await handle_trade_cancel(session, msg)
            elif mtype == "FAIRY_ACT":
                import fairy_village
                await fairy_village.act(session, msg.get("id"))
            elif mtype == "LOGOUT":
                break
    except websockets.exceptions.ConnectionClosed:
        pass
    finally:
        if session and WORLD.sessions.get(session.player_id) is session:
            if _should_linger(session):
                await begin_linger(session)
            else:
                await logout_session(session, "disconnect")


async def logout_session(session, reason="logout"):
    """The one logout path (LOGOUT, socket close, idle kick, end of a combat linger): save and remove."""
    if WORLD.sessions.get(session.player_id) is not session:
        return
    if getattr(session, "trade_partner_id", None):
        await handle_trade_cancel(session, {})
    if session.dungeon and session.dungeon.get("id") == "castle_realm":
        session.x = int(session.dungeon.get("return_x", session.x))
        session.y = int(session.dungeon.get("return_y", session.y))
        session.dungeon = None
        WORLD.db.save_player_position(session.player_id, session.x, session.y)
        _clear_dungeon_resume(session)
    elif session.dungeon:
        _save_dungeon_resume(session)
        session.dungeon = None
    else:
        WORLD.db.save_player_position(session.player_id, session.x, session.y)
        _clear_dungeon_resume(session)
    WORLD.db.save_player_stats(session.player_id, hp=session.hp)
    del WORLD.sessions[session.player_id]
    log.info("%s disconnected (%s)", session.char_name, reason)


# ---- idle logout and combat linger ----------------------------------------------------------------
class _GhostSocket:
    """Stands in for a closed socket while a body lingers after a mid-fight disconnect."""
    closed = True

    async def send(self, _raw):
        return None

    async def close(self, *args, **kwargs):
        return None


def _linger_ticks(session):
    return PK_LINGER_TICKS if getattr(session, "player_killer", False) else COMBAT_LINGER_TICKS


def _in_combat_recently(session, tick=None):
    tick = WORLD.tick_count if tick is None else tick
    return bool(session.in_combat_with) or tick - int(session.last_combat_tick) < COMBAT_LINGER_TICKS


def _should_linger(session):
    return _in_combat_recently(session) and not getattr(session, "idle_kicked", False)


async def begin_linger(session):
    """Socket closed mid-fight: the body stays (attackable, can die) until the linger runs out."""
    if getattr(session, "trade_partner_id", None):
        await handle_trade_cancel(session, {})
    session.ws = _GhostSocket()
    session.gathering_node = None
    session.linger_until = WORLD.tick_count + _linger_ticks(session)
    session.linger_started = WORLD.tick_count
    log.info("%s disconnected mid-fight; body stays %d ticks", session.char_name, _linger_ticks(session))


async def note_real_input(session):
    tick = WORLD.tick_count
    session.last_input_tick = session.last_real_input_tick = tick
    if session.idle_warned:
        session.idle_warned = False
        await send(session.ws, "IDLE_CLEAR")


async def idle_input_ping(session, msg):
    """Credit local input the client saw, capped: never later than now, never past the grace after a real action."""
    tick = WORLD.tick_count
    try:
        ago_ms = max(0, min(10 ** 7, int(msg.get("last_input_ms_ago") or 0)))
    except (TypeError, ValueError):
        return
    claimed = tick - int(-(-ago_ms // int(TICK_SECONDS * 1000)))
    real = session.last_real_input_tick if session.last_real_input_tick is not None else tick
    credit = min(claimed, tick, real + INPUT_PING_GRACE_TICKS)
    if session.last_input_tick is None or credit > session.last_input_tick:
        session.last_input_tick = credit
    if session.idle_warned and tick - session.last_input_tick < IDLE_WARN_TICKS:
        session.idle_warned = False
        await send(session.ws, "IDLE_CLEAR")


async def idle_kick(session):
    session.idle_kicked = True
    if getattr(session, "trade_partner_id", None):
        await handle_trade_cancel(session, {})
    await send(session.ws, "LOGGED_OUT", reason="idle")
    log.info("%s logged out for inactivity", session.char_name)
    try:
        # closing waits for the handshake, so don't hold the game tick on it
        asyncio.ensure_future(session.ws.close())
    except Exception:
        pass
    # the handler's finally runs logout_session once the socket loop ends


async def process_idle():
    tick = WORLD.tick_count
    for s in list(WORLD.sessions.values()):
        if s.last_input_tick is None:
            s.last_input_tick = s.last_real_input_tick = tick
        hp = int(getattr(s, "hp", 0) or 0)
        if s.in_combat_with or (s._idle_hp is not None and hp < s._idle_hp):
            s.last_combat_tick = tick
        s._idle_hp = hp
        if s.linger_until is not None:
            # 10 s (60 s PK) after the last hit; a fight that never ends still lets go after 5 minutes
            if (tick >= max(s.linger_until, s.last_combat_tick + _linger_ticks(s))
                    or tick - getattr(s, "linger_started", tick) >= IDLE_LOGOUT_TICKS):
                await logout_session(s, "combat linger over")
            continue
        if s.idle_exempt or s.idle_kicked:
            continue
        idle = tick - s.last_input_tick
        if idle >= IDLE_WARN_TICKS and not s.idle_warned:
            s.idle_warned = True
            secs = max(1, int(round((IDLE_LOGOUT_TICKS - idle) * TICK_SECONDS)))
            await send(s.ws, "IDLE_WARNING", seconds=secs)
        if idle >= IDLE_LOGOUT_TICKS and not _in_combat_recently(s, tick):
            await idle_kick(s)


# ---------------------------------------------------------------------------
# Game tick loop: combat resolution, gathering, monster AI, respawns
# ---------------------------------------------------------------------------
async def _ember_cones():
    """Breath on a timer. Damage is the normal strike when someone stands in the cone."""
    if not feature_flags.USE_EMBERDEEP_CREATURES:
        return
    import emberdeep_creatures
    for session in list(WORLD.sessions.values()):
        dungeon = session.dungeon or {}
        if dungeon.get("id") != "emberdeep":
            continue
        players = [(session.x, session.y)]
        for monster in dungeon.get("monsters", {}).values():
            stats = monster.stats or {}
            if not monster.alive or not stats.get("static"):
                continue
            emberdeep_creatures.wyrm_tick(monster, dungeon.get("tiles") or [], players, WORLD.tick_count)
            lair = (emberdeep_creatures.manifest().get("boss") or {}).get("lair") or {}
            in_lair = (
                lair
                and lair["x0"] <= int(session.x) <= lair["x1"]
                and lair["y0"] <= int(session.y) <= lair["y1"]
            )
            if not in_lair:
                monster._cone_pending = False
                monster._cone_strike = False
                if monster.target_player_id == session.player_id:
                    monster.target_player_id = None
                continue
            cones = {tuple(p) for p in (monster.stats or {}).get("cone_tiles") or []}
            if getattr(monster, "_cone_pending", False):
                monster._cone_pending = False
                standing = (session.x, session.y) in cones
                monster._cone_strike = standing
                if standing:
                    monster.target_player_id = session.player_id
                else:
                    monster.target_player_id = None
                    monster._cone_strike = False
                    monster.mark_attacked(2.4)
                continue
            if WORLD.tick_count - getattr(monster, "_turned_tick", -99) < 1:
                continue
            if not monster.attack_ready():
                continue
            await send(session.ws, "EMBER_CONE", tiles=stats.get("cone_tiles") or [])
            monster._cone_pending = True
            monster._cone_strike = False


async def game_loop():
    while True:
        await asyncio.sleep(TICK_SECONDS)
        WORLD.tick_count += 1
        expire_ground_items()
        events = []

        try:
            await _ember_cones()
            await process_combat(events)
            await process_gathering(events)
            await process_fishing_spots()
            await process_idle()
            await reconcile_dungeon_doors()
            process_monster_respawns()
            process_resource_respawns()
            process_fires()
            process_monster_ai()
            process_dungeon_ai()
            import void_v2
            await void_v2.tick_sessions()
            import depths_v2
            await depths_v2.tick_sessions()
            process_pets(events)
            await _flush_pk_notices()
            await process_stat_boosts()
            await process_equip_regen()
            await flush_quest_logs()
            if feature_flags.USE_PLAYER_HOUSING and WORLD.tick_count % 500 == 0:
                await _housing.tick_leases()
            if WORLD.tick_count % 10 == 0:
                await throne_live.tick()
                await politics_live.tick()
            if WORLD.tick_count % 100 == 0:
                await ruling_daily_tick()
            if WORLD.tick_count % 10 == 0:
                import world_clock
                env_snap = world_clock.poll_update()
                if env_snap is not None:
                    await broadcast("ENV_UPDATE", env=env_snap)
            if WORLD.tick_count % 500 == 0:
                for _s in list(WORLD.sessions.values()):
                    await settle_work(_s)
                import clans
                await clans.tick_upkeep()
            if feature_flags.USE_CASTLE_OWNERS and WORLD.tick_count % 500 == 0:
                import castle_owners
                await castle_owners.tick_taxes()
        except Exception:
            log.exception("game tick failed (tick=%s)", WORLD.tick_count)
            events = []

        # Pet clears / loot of dungeon floors
        for ev in list(events):
            if ev["type"] == "_DUNGEON_LOOT":
                events.remove(ev)
                pid = ev["data"].get("_dungeon_player")
                s = WORLD.sessions.get(pid)
                if s and s.dungeon:
                    mid = ev["data"].get("monster_id")
                    monster = s.dungeon["monsters"].get(mid) if mid is not None else None
                    await _finish_dungeon_kill(s, monster)
            elif ev["type"] == "_DUNGEON_CLEAR":
                events.remove(ev)
                pid = ev["data"].get("_dungeon_player")
                s = WORLD.sessions.get(pid)
                if s and s.dungeon and not s.dungeon.get("explore"):
                    await _dungeon_on_clear(s)

        # World state for overworld players
        world_players = [s.public_state() for s in WORLD.sessions.values() if not s.dungeon]
        world_state = {
            "players": world_players,
            "monsters": [m.public_state() for m in WORLD.monsters.values()],
            "pets": [s.pet_public() for s in WORLD.sessions.values() if s.pet_id and not s.dungeon],
            "ground_items": {f"{x},{y}": items for (x, y), items in WORLD.ground_items.items()},
            "resources": {
                f"{x},{y}": n["type"]
                for (x, y), n in WORLD.resource_nodes.items()
                if not n["depleted"]
            },
            "fires": [f"{x},{y}" for (x, y) in WORLD.fires],
        }
        for session in list(WORLD.sessions.values()):
            if session.dungeon:
                d = session.dungeon
                alive = [m.public_state() for m in d["monsters"].values() if m.alive and not getattr(m, "concealed", False)]
                if d.get("id") == "castle_realm":
                    plane = d.get("plane")
                    realm_players = [
                        other.public_state()
                        for other in WORLD.sessions.values()
                        if (other.dungeon or {}).get("id") == "castle_realm"
                        and (other.dungeon or {}).get("plane") == plane
                    ]
                else:
                    realm_players = [session.public_state()]
                await send(session.ws, "STATE_UPDATE", **{
                    "players": realm_players,
                    "monsters": alive,
                    "pets": [session.pet_public()] if session.pet_id else [],
                    "ground_items": (
                        __import__("void_v2").ground_public(d) if d.get("v2") else {}
                    ),
                    "resources": {},
                    "fires": [],
                    "dungeon": {
                        "floor": d["floor"],
                        "floors": d["floors"],
                        "remaining": _dungeon_remaining(d),
                        "label": d["label"],
                        **_dungeon_room_hud(session),
                        **(__import__("void_v2").hud_state(d, WORLD.tick_count) if d.get("v2") else {}),
                    },
                })
            else:
                await send(session.ws, "STATE_UPDATE", **world_state)
        for ev in events:
            data = ev["data"]
            if data.get("_dungeon_player"):
                pid = data.pop("_dungeon_player")
                target = WORLD.sessions.get(pid)
                if target:
                    await send(target.ws, ev["type"], **data)
            else:
                await broadcast(ev["type"], **data)


def process_fires():
    expired = [k for k, until in WORLD.fires.items() if WORLD.tick_count >= until]
    for k in expired:
        del WORLD.fires[k]


async def process_stat_boosts():
    """Expire combat potions and notify the player when bonuses wear off."""
    now = time.time()
    for session in list(WORLD.sessions.values()):
        expired = []
        for skill, buff in list(session.stat_boosts.items()):
            if now >= buff["until"]:
                expired.append((skill, int(buff["amount"])))
                del session.stat_boosts[skill]
        if not expired:
            continue
        await send(session.ws, "PLAYER_UPDATE", player=session.full_state())
        for skill, amount in expired:
            await send(
                session.ws, "CHAT_MSG",
                **{
                    "from": "You",
                    "text": f"Your {skill} boost (+{amount}) has worn off.",
                },
            )


async def process_equip_regen():
    """Passive HP from worn gear (Tidehollow Medal: +1 HP / 5s)."""
    now = time.time()
    for session in list(WORLD.sessions.values()):
        if session.hp <= 0:
            continue
        max_hp = session.max_hp()
        if session.hp >= max_hp:
            continue
        # Best regen among all worn pieces
        best_hp, best_secs = 0, 0.0
        for slot, iid in (session.equipment or {}).items():
            if not iid:
                continue
            it = ITEMS.get(iid) or {}
            rh = int(it.get("regen_hp") or 0)
            rs = float(it.get("regen_seconds") or 0)
            if rh > 0 and rs > 0 and (best_secs <= 0 or rh / rs > best_hp / best_secs):
                best_hp, best_secs = rh, rs
        if best_hp <= 0 or best_secs <= 0:
            continue
        last = float(getattr(session, "last_equip_regen_at", 0) or 0)
        if now - last < best_secs:
            continue
        session.last_equip_regen_at = now
        session.hp = min(max_hp, session.hp + best_hp)
        WORLD.db.save_player_stats(session.player_id, hp=session.hp)
        await send(session.ws, "PLAYER_UPDATE", player=session.full_state())


async def process_combat(events):
    MAX_ATTACKERS = 1
    for session in list(WORLD.sessions.values()):
        if session.dungeon:
            pool = [m for m in session.dungeon["monsters"].values() if m.alive and not getattr(m, "concealed", False)]
            dungeon_tag = session.player_id
        else:
            pool = list(WORLD.monsters.values())
            dungeon_tag = None

        attackers = [
            m for m in pool
            if m.alive and m.target_player_id == session.player_id
            and m.can_strike(session.x, session.y)
        ]
        # Only the monster you are already fighting may land a hit.
        engaged_id = None
        if session.in_combat_with and session.in_combat_with[0] == "monster":
            engaged_id = session.in_combat_with[1]
        attackers.sort(key=lambda m: (0 if m.id == engaged_id else 1, m.id))
        attackers = attackers[:MAX_ATTACKERS]
        for m in pool:
            if getattr(m, "_cone_strike", False) and m not in attackers and m.can_strike(session.x, session.y):
                attackers.append(m)

        primary = None
        if session.in_combat_with and session.in_combat_with[0] == "monster":
            mid = session.in_combat_with[1]
            primary = next((m for m in pool if m.id == mid), None)
            reach = session.attack_reach()
            if primary:
                mreach = int(primary.def_stats().get("attack_range") or 1)
                if session.y == primary.y and abs(session.x - primary.x) <= mreach:
                    reach = max(reach, mreach)
            if primary and (primary.def_stats() or {}).get("requires_pk") and not session.player_killer:
                session.in_combat_with = None
                primary = None
            elif primary and not primary.alive:
                primary = None
            elif primary:
                wyrm = _ember_wyrm_can_hit(primary, session.x, session.y)
                close = wyrm if wyrm is not None else chebyshev(session.x, session.y, primary.x, primary.y) <= reach
                if not close:
                    # The wyrm does not chase. Once you leave the fire, the fight ends.
                    if wyrm is False:
                        session.in_combat_with = None
                    primary = None
        fights = gear_rules.can_fight(session, ITEMS)
        if not fights:
            if primary is not None:
                session.in_combat_with = None
            primary = None
        if primary is None and attackers and fights:
            # Auto-retaliate only when the monster forces it (default). Bosses like
            # the dragon can hit you without locking you into fighting back.
            fleeing = time.time() < float(getattr(session, "combat_flee_until", 0) or 0)
            if not fleeing:
                for atk in attackers:
                    if atk.def_stats().get("force_retaliate", True):
                        primary = atk
                        session.in_combat_with = ("monster", atk.id)
                        break

        if primary:
            reach = session.attack_reach()
            # Side-by-side fights may leave a 1–2 tile gap; allow melee to land across it
            # when the foe fights at extended range (e.g. dragonfire).
            mreach = int(primary.def_stats().get("attack_range") or 1)
            if session.y == primary.y and abs(session.x - primary.x) <= mreach:
                reach = max(reach, mreach)
            wyrm = _ember_wyrm_can_hit(primary, session.x, session.y)
            in_reach = wyrm if wyrm is not None else chebyshev(session.x, session.y, primary.x, primary.y) <= reach
            if in_reach:
                ranged = bool(session.using_bow())
                # 50 ms grace so a 1.2s swing is not pushed a whole tick late by loop jitter
                skip_player_swing = time.time() < float(getattr(session, "next_swing_at", 0) or 0) - 0.05
                if skip_player_swing:
                    pass
                elif ranged:
                    if not session.consume_one_arrow():
                        await send(
                            session.ws, "CHAT_MSG",
                            **{"from": "You", "text": "You have run out of arrows."},
                        )
                        session.in_combat_with = None
                        await send(session.ws, "PLAYER_UPDATE", player=session.full_state())
                        skip_player_swing = True
                    else:
                        await send(session.ws, "PLAYER_UPDATE", player=session.full_state())
                if not skip_player_swing:
                    wstats = None if ranged else weapon_stats(session.equipment.get("weapon"))
                    interval = 1.2 if not wstats else SWING_SECONDS_PER_SPEED * float(wstats["attack_speed"])
                    now_ = time.time()
                    prev_ = float(getattr(session, "next_swing_at", 0) or 0)
                    # Chained swings keep the exact average pace (an axe's 1.5s alternates 1.2/1.8 ticks)
                    session.next_swing_at = (prev_ if now_ - prev_ < 0.6 else now_) + interval
                    mdef = primary.def_stats()
                    dmg, hit = combat.resolve_hit(session.combat_stats(), {
                        "attack": 1, "strength": 1, "defence": mdef["defence"],
                        "defence_bonus": mdef.get("def_bonus", 0),
                    })
                    crit = False
                    if hit and dmg > 0:
                        flat = int(session.jewelry_ability_total("void_strike"))
                        if flat:
                            dmg += flat
                        if wstats and wstats.get("heavy_bonus"):
                            dmg = max(1, int(round(dmg * (1 + float(wstats["heavy_bonus"])))))
                        crit_chance = session.jewelry_ability_total("crit") + (
                            float(wstats.get("crit_chance") or 0) if wstats else 0.0)
                        if crit_chance > 0 and random.random() < min(0.45, crit_chance):
                            dmg = max(1, int(round(dmg * session.jewelry_crit_mult())))
                            crit = True
                    if session.dungeon and session.dungeon.get("v2"):
                        import void_v2
                        dmg = void_v2.mitigate(session, primary, dmg)
                    primary.hp = max(0, primary.hp - dmg)
                    healed = 0
                    if hit and dmg > 0:
                        steal = session.jewelry_ability_total("lifesteal")
                        if steal > 0:
                            heal = max(1, int(round(dmg * min(0.40, steal))))
                            max_hp = session.max_hp()
                            if session.hp < max_hp:
                                before_hp = session.hp
                                session.hp = min(max_hp, session.hp + heal)
                                healed = session.hp - before_hp
                                if healed:
                                    WORLD.db.save_player_stats(session.player_id, hp=session.hp)
                    if (primary.def_stats() or {}).get("requires_pk"):
                        session.pet_target_id = None
                    else:
                        session.pet_target_id = primary.id
                    ev = {
                        "attacker_id": session.player_id, "defender_id": primary.id, "damage": dmg,
                        "hit": hit, "defender_hp": primary.hp, "defender_max_hp": primary.max_hp,
                        "kind": "player_hits_monster",
                        "ranged": ranged,
                    }
                    if crit:
                        ev["crit"] = True
                    if healed:
                        ev["lifesteal"] = healed
                    if _fight_holds_you(session, primary):
                        if getattr(session, "combat_lock_id", None) != primary.id:
                            session.combat_rounds = 0
                            session.combat_lock_id = primary.id
                        session.combat_rounds = _combat_rounds(session) + 1
                        ev["combat_rounds"] = session.combat_rounds
                        if session.combat_rounds == COMBAT_LOCK_ROUNDS:
                            await send(session.ws, "CHAT_MSG", **{
                                "from": "Combat",
                                "text": "Five rounds are done. You can run.",
                            })
                    else:
                        session.combat_rounds = 0
                        session.combat_lock_id = None
                        ev["combat_rounds"] = 0
                    if dungeon_tag:
                        ev["_dungeon_player"] = dungeon_tag
                    events.append({"type": "COMBAT_EVENT", "data": ev})
                    if ranged:
                        style = "archery"
                        session.combat_style = "archery"
                    else:
                        style = session.combat_style if session.combat_style in COMBAT_STYLES else "attack"
                        if style == "archery":
                            style = "attack"
                            session.combat_style = "attack"
                    amount = dmg * 15
                    if amount > 0:
                        before, after = WORLD.grant_xp(session, style, amount)
                        xp_ev = {
                            "player_id": session.player_id, "skill": style, "gained": amount,
                            "xp": session.xp[style], "level": after, "leveled_up": after > before,
                        }
                        if dungeon_tag:
                            xp_ev["_dungeon_player"] = dungeon_tag
                        events.append({"type": "SKILL_XP", "data": xp_ev})
                    try_auto_magic(session, primary, events, dungeon_tag=dungeon_tag)
                    if primary.hp <= 0:
                        _mark_monster_dead(primary)
                        await _credit_pk_kill(session, primary)
                        if session.in_combat_with == ("monster", primary.id):
                            session.in_combat_with = None
                        if not session.dungeon:
                            drops = WORLD.drop_loot(primary.x, primary.y, drops_for_kill(primary.type))
                            events.append({"type": "DEATH", "data": {"entity_id": primary.id, "entity_kind": "monster"}})
                            if drops:
                                events.append({"type": "LOOT_DROPPED", "data": {"x": primary.x, "y": primary.y, "items": drops}})
                                await vacuum_ground_loot(session)
                                await send(session.ws, "PLAYER_UPDATE", player=session.full_state())
                            check_quest_progress_on_kill(session, primary.type)
                        else:
                            death_ev = {"entity_id": primary.id, "entity_kind": "monster", "_dungeon_player": dungeon_tag}
                            events.append({"type": "DEATH", "data": death_ev})
                            if not session.dungeon.get("explore"):
                                bonus_xp = int(mdef.get("xp", 20))
                                if bonus_xp > 0:
                                    before, after = WORLD.grant_xp(session, style, bonus_xp)
                                    events.append({"type": "SKILL_XP", "data": {
                                        "player_id": session.player_id, "skill": style, "gained": bonus_xp,
                                        "xp": session.xp[style], "level": after, "leveled_up": after > before,
                                        "_dungeon_player": dungeon_tag,
                                    }})
                            await _finish_dungeon_kill(session, primary)
                        attackers = [m for m in attackers if m is not primary]

        died = False
        for monster in attackers:
            if not monster.alive:
                continue
            if monster.is_frozen():
                continue
            mstats = monster.def_stats()
            dmg2, hit2 = combat.resolve_hit(
                {"attack": mstats["attack"], "strength": mstats["strength"]},
                {
                    "defence": session.effective_level("defence"),
                    "defence_bonus": session.weapon_bonuses()["def_bonus"],
                },
            )
            dodged = False
            if hit2 and dmg2 > 0:
                dodge_chance = session.jewelry_ability_total("dodge")
                if dodge_chance > 0 and random.random() < min(0.35, dodge_chance):
                    dmg2 = 0
                    hit2 = False
                    dodged = True
                else:
                    ward = int(session.jewelry_ability_total("void_ward"))
                    if ward:
                        dmg2 = max(0, dmg2 - ward)
            session.hp = max(0, session.hp - dmg2)
            # Thorns reflect a portion of damage taken back to the monster
            thorns_dmg = 0
            if hit2 and dmg2 > 0 and not dodged:
                thorns = session.jewelry_ability_total("thorns")
                if thorns > 0 and monster.alive:
                    reflect = max(1, int(round(dmg2 * min(0.50, thorns))))
                    thorns_dmg = reflect
                    monster.hp = max(0, monster.hp - reflect)
                    if monster.hp <= 0:
                        _mark_monster_dead(monster)
                        await _credit_pk_kill(session, monster)
                        if session.in_combat_with == ("monster", monster.id):
                            session.in_combat_with = None
                        if not session.dungeon:
                            drops = WORLD.drop_loot(monster.x, monster.y, drops_for_kill(monster.type))
                            events.append({"type": "DEATH", "data": {"entity_id": monster.id, "entity_kind": "monster"}})
                            if drops:
                                events.append({"type": "LOOT_DROPPED", "data": {"x": monster.x, "y": monster.y, "items": drops}})
                            check_quest_progress_on_kill(session, monster.type)
                        else:
                            events.append({"type": "DEATH", "data": {
                                "entity_id": monster.id, "entity_kind": "monster",
                                "_dungeon_player": dungeon_tag,
                            }})
                            await _finish_dungeon_kill(session, monster)
            hit_ev = {
                "attacker_id": monster.id, "defender_id": session.player_id, "damage": dmg2,
                "hit": hit2, "defender_hp": session.hp, "defender_max_hp": session.max_hp(),
                "kind": "monster_hits_player",
            }
            if monster.type == "dragon":
                hit_ev["fx"] = "dragonfire"
            elif (monster.stats or {}).get("cone_tiles"):
                hit_ev["fx"] = "fire_cone"
                hit_ev["cone"] = monster.stats.get("cone_tiles")
                monster._cone_strike = False
            if dodged:
                hit_ev["dodged"] = True
            if thorns_dmg:
                hit_ev["thorns"] = thorns_dmg
                hit_ev["thorns_target"] = monster.id
            if dungeon_tag:
                hit_ev["_dungeon_player"] = dungeon_tag
            events.append({"type": "COMBAT_EVENT", "data": hit_ev})
            # Post-swing cooldown (dragon: 1s so the player can run)
            monster.mark_attacked()
            if session.hp <= 0:
                died = True
                break

        if died:
            # A quarter, not everything. Losing the entire purse to one bad
            # fight is the harshest possible outcome, and it hit hardest on a
            # good run (the 65k purse cap means a long session has the most to
            # lose). A quarter still stings and still rewards banking first.
            lost = int(session.coins * 0.25)
            session.hp = session.max_hp()
            session.coins = max(0, session.coins - lost)
            session.in_combat_with = None
            session.pet_target_id = None
            where = "village"
            if session.dungeon:
                v2_kind = session.dungeon.get("v2")
                realm_death = session.dungeon.get("id") == "castle_realm"
                v2_death = bool(v2_kind)
                stayed = False
                if v2_death and session.dungeon.get("checkpoint"):
                    import void_v2
                    stayed = await void_v2.on_death(session)
                    if stayed:
                        await _relock_dungeon_doors(session)
                        _save_dungeon_resume(session)
                        where = "checkpoint"
                if not stayed:
                    where = "entrance"
                    if v2_death:
                        import void_v2
                        void_v2.strip_keys(session)
                    await handle_leave_dungeon(session, silent=True)
                    if v2_kind == "depths":
                        fall = "You fall in the crypt and wake outside. The dead keep what you carried."
                    elif v2_death:
                        fall = "You fall in the sanctum and wake outside. The dark keeps what you carried."
                    elif realm_death:
                        fall = "You wake outside the Castle Realm portal."
                    else:
                        fall = "You fall in the cave and wake outside — the depths reclaim their silence."
                    await send(session.ws, "CHAT_MSG", **{"from": "Tidehollow", "text": fall})
            else:
                session.x, session.y = SPAWN_POINT
                if session.pet_id:
                    session.pet_hp = PETS[session.pet_id]["hp"]
                    _bring_pet(session)
                for mon in WORLD.monsters.values():
                    if mon.target_player_id == session.player_id:
                        mon.target_player_id = None
            WORLD.db.save_player_stats(session.player_id, coins=session.coins)
            if not session.dungeon:
                WORLD.db.save_player_position(session.player_id, session.x, session.y)
            death_data = {
                "entity_id": session.player_id, "entity_kind": "player",
                "coins_lost": lost,
                "where": where,
            }
            if dungeon_tag:
                death_data["_dungeon_player"] = dungeon_tag
            events.append({"type": "DEATH", "data": death_data})
            await send(session.ws, "PLAYER_UPDATE", player=session.full_state())
        elif not session.in_combat_with and not attackers:
            pass


def _pet_walkable(session, nx, ny):
    if session.dungeon and session.dungeon.get("id") == "castle_realm":
        import castle_realm
        return castle_realm.walkable(session.dungeon.get("plane"), nx, ny)
    if session.dungeon:
        mod = _dungeon_mod(session)
        return bool(mod and mod.dungeon_walkable(session.dungeon["tiles"], nx, ny))
    return is_walkable(WORLD.grid, nx, ny)


def _pet_ring(session, distance):
    """Free tiles at this Chebyshev distance. Behind the player comes first."""
    px, py = int(session.x), int(session.y)
    last = getattr(session, "last_step", None)
    order = []
    if last in ((0, 1), (0, -1), (1, 0), (-1, 0)):
        bx, by = -int(last[0]) * distance, -int(last[1]) * distance
        order.append((bx, by))
        if bx == 0:
            order.extend(((1, by), (-1, by), (distance, 0), (-distance, 0)))
        else:
            order.extend(((bx, 1), (bx, -1), (0, distance), (0, -distance)))
    order.extend(((0, distance), (-distance, 0), (distance, 0), (0, -distance)))
    for dy in range(-distance, distance + 1):
        for dx in range(-distance, distance + 1):
            if max(abs(dx), abs(dy)) == distance:
                order.append((dx, dy))
    free = []
    seen = set()
    for dx, dy in order:
        cell = (px + dx, py + dy)
        if cell in seen or cell == (px, py):
            continue
        seen.add(cell)
        if _pet_walkable(session, cell[0], cell[1]):
            free.append(cell)
    return free


def _pet_preferred_tiles(session):
    """Two tiles away: behind, then beside. One tile only if that ring is blocked."""
    free = _pet_ring(session, 2)
    if free:
        return free
    return _pet_ring(session, 1)


def _pet_face_owner(session):
    dx = int(session.x) - int(session.pet_x)
    dy = int(session.y) - int(session.pet_y)
    if abs(dx) >= abs(dy) and dx != 0:
        session.pet_facing = "e" if dx > 0 else "w"
    elif dy > 0:
        session.pet_facing = "s"
    elif dy < 0:
        session.pet_facing = "n"
    else:
        session.pet_facing = getattr(session, "pet_facing", None) or "s"


def _pet_off_screen(session):
    """The pet has left the view around the player. Further than two tiles is fine."""
    dx = abs(int(session.pet_x) - int(session.x))
    dy = abs(int(session.pet_y) - int(session.y))
    # Default camera: 900x640 at 40px tiles, player in the middle.
    return dx > 11 or dy > 8


def _pet_reappear(session):
    """Place the pet two tiles away. Used when it must skip the walk."""
    if not getattr(session, "pet_id", None):
        return
    free = _pet_preferred_tiles(session)
    if free:
        session.pet_x, session.pet_y = free[0]
    _pet_face_owner(session)


def _park_pet(session):
    """If the pet shares the player's tile, reappear two tiles away."""
    if not getattr(session, "pet_id", None):
        return
    if (int(session.pet_x), int(session.pet_y)) != (int(session.x), int(session.y)):
        _pet_face_owner(session)
        return
    _pet_reappear(session)


def _bring_pet(session):
    """After a teleport or summon, reappear two tiles away."""
    if not getattr(session, "pet_id", None):
        return
    session.pet_target_id = None
    _pet_reappear(session)


def _pet_step_toward(session, tx, ty, avoid=None):
    """Move pet one tile toward (tx, ty) if walkable. Never onto avoid."""
    px, py = session.pet_x, session.pet_y
    if (px, py) == (tx, ty):
        return False
    options = []
    dx = 0 if px == tx else (1 if tx > px else -1)
    dy = 0 if py == ty else (1 if ty > py else -1)
    blocked = tuple(avoid) if avoid is not None else None
    for nx, ny in ((px + dx, py), (px, py + dy), (px + dx, py + dy)):
        if blocked is not None and (nx, ny) == blocked:
            continue
        if _pet_walkable(session, nx, ny):
            options.append((nx, ny))
    if not options:
        return False
    options.sort(key=lambda p: max(abs(p[0] - tx), abs(p[1] - ty)))
    nx, ny = options[0]
    sdx, sdy = nx - px, ny - py
    if abs(sdx) >= abs(sdy) and sdx:
        session.pet_facing = "e" if sdx > 0 else "w"
    elif sdy:
        session.pet_facing = "s" if sdy > 0 else "n"
    session.pet_x, session.pet_y = nx, ny
    return True


def _pet_follow_tile(session):
    """Preferred stand spot: about two tiles behind the player."""
    free = _pet_preferred_tiles(session)
    return free[0] if free else None


def _pet_chebyshev(session):
    return max(abs(int(session.pet_x) - int(session.x)), abs(int(session.pet_y) - int(session.y)))


# Pets step on the world tick, not on every player keypress — keeps follow cheap.
_PET_STEP_EVERY = 2   # ~1.2s at TICK_SECONDS=0.6


def _pet_walk_follow(session):
    """Slow walk toward the follow spot. Teleport only when off-screen (or stuck on the player)."""
    if not getattr(session, "pet_id", None) or session.pet_id not in PETS:
        return
    if session.pet_target_id:
        return
    if _pet_off_screen(session):
        _pet_reappear(session)
        return
    tick = int(getattr(WORLD, "tick_count", 0) or 0)
    ready = int(getattr(session, "_pet_step_ready", 0) or 0)
    if tick < ready:
        _pet_face_owner(session)
        return
    dist = _pet_chebyshev(session)
    # Close enough: don't thrash pathfinding every tick.
    if dist <= 2 and (int(session.pet_x), int(session.pet_y)) != (int(session.x), int(session.y)):
        _pet_face_owner(session)
        return
    target = _pet_follow_tile(session)
    if (int(session.pet_x), int(session.pet_y)) == (int(session.x), int(session.y)):
        if target and _pet_step_toward(session, target[0], target[1], avoid=(session.x, session.y)):
            session._pet_step_ready = tick + _PET_STEP_EVERY
        elif not target:
            _pet_reappear(session)
        return
    if not target:
        _pet_face_owner(session)
        return
    if dist > 2 and _pet_step_toward(session, target[0], target[1], avoid=(session.x, session.y)):
        session._pet_step_ready = tick + _PET_STEP_EVERY
    _pet_face_owner(session)


def _pet_keep_up(session, dx=0, dy=0):
    """On each player step: remember facing; teleport only if the pet left the screen.

    Walking is handled on the slower pet tick so rapid player moves don't stall the server.
    """
    if dx or dy:
        if abs(dx) >= abs(dy) and dx:
            session.last_step = (1 if dx > 0 else -1, 0)
        elif dy:
            session.last_step = (0, 1 if dy > 0 else -1)
    if not getattr(session, "pet_id", None) or session.pet_id not in PETS:
        return
    if session.pet_target_id:
        return
    if _pet_off_screen(session) or (session.pet_x, session.pet_y) == (session.x, session.y):
        # Same-tile: nudge off on the next pet tick instead of scanning rings here.
        if _pet_off_screen(session):
            _pet_reappear(session)


def _pet_note_player_step(session):
    prev = getattr(session, "_pet_seen_xy", None)
    cur = (int(session.x), int(session.y))
    moving = prev is not None and prev != cur
    if moving:
        dx, dy = cur[0] - prev[0], cur[1] - prev[1]
        if abs(dx) >= abs(dy) and dx:
            session.last_step = (1 if dx > 0 else -1, 0)
        elif dy:
            session.last_step = (0, 1 if dy > 0 else -1)
    session._pet_seen_xy = cur
    return moving


def process_pets(events):
    """Pets follow their owner and only attack monsters the player has attacked."""
    for session in list(WORLD.sessions.values()):
        if not session.pet_id or session.pet_id not in PETS:
            continue
        pdef = PETS[session.pet_id]
        if session.pet_hp <= 0:
            session.pet_hp = pdef["hp"]

        _pet_note_player_step(session)

        dungeon_tag = session.player_id if session.dungeon else None

        # Only engage a monster the player has attacked (pet_target_id set on attack)
        target = None
        if session.pet_target_id:
            if session.dungeon:
                m = session.dungeon["monsters"].get(session.pet_target_id)
            else:
                m = WORLD.monsters.get(session.pet_target_id)
            if m and m.alive and not (m.def_stats() or {}).get("requires_pk"):
                target = m
            else:
                session.pet_target_id = None

        if target is not None:
            if _pet_off_screen(session):
                _pet_reappear(session)
            if adjacent_or_same(session.pet_x, session.pet_y, target.x, target.y):
                mstats = target.def_stats()
                dmg, hit = combat.resolve_hit(
                    {"attack": pdef["attack"], "strength": pdef["strength"]},
                    {"defence": mstats["defence"], "defence_bonus": mstats.get("def_bonus", 0)},
                )
                target.hp = max(0, target.hp - dmg)
                hit_ev = {
                    "attacker_id": f"pet:{session.player_id}",
                    "defender_id": target.id,
                    "damage": dmg, "hit": hit,
                    "defender_hp": target.hp, "defender_max_hp": target.max_hp,
                    "kind": "pet_hits_monster",
                }
                if dungeon_tag:
                    hit_ev["_dungeon_player"] = dungeon_tag
                events.append({"type": "COMBAT_EVENT", "data": hit_ev})
                if target.hp <= 0:
                    _mark_monster_dead(target)
                    _note_pk_kill(session, target)
                    if session.in_combat_with == ("monster", target.id):
                        session.in_combat_with = None
                    session.pet_target_id = None
                    death_ev = {"entity_id": target.id, "entity_kind": "monster"}
                    if dungeon_tag:
                        death_ev["_dungeon_player"] = dungeon_tag
                    events.append({"type": "DEATH", "data": death_ev})
                    if session.dungeon:
                        events.append({
                            "type": "_DUNGEON_LOOT",
                            "data": {"_dungeon_player": session.player_id, "monster_id": target.id},
                        })
                        if not session.dungeon.get("explore") and _floor_uncleared(session.dungeon) == 0:
                            events.append({
                                "type": "_DUNGEON_CLEAR",
                                "data": {"_dungeon_player": session.player_id},
                            })
                    else:
                        drops = WORLD.drop_loot(target.x, target.y, drops_for_kill(target.type))
                        if drops:
                            events.append({"type": "LOOT_DROPPED", "data": {
                                "x": target.x, "y": target.y, "items": drops,
                            }})
                        check_quest_progress_on_kill(session, target.type)
            else:
                tick = int(getattr(WORLD, "tick_count", 0) or 0)
                if tick >= int(getattr(session, "_pet_step_ready", 0) or 0):
                    if _pet_step_toward(session, target.x, target.y, avoid=(session.x, session.y)):
                        session._pet_step_ready = tick + _PET_STEP_EVERY
            if (session.pet_x, session.pet_y) == (session.x, session.y):
                _park_pet(session)
            continue

        _pet_walk_follow(session)


async def process_gathering(events):
    for session in list(WORLD.sessions.values()):
        if not session.gathering_node:
            continue
        node = WORLD.resource_nodes.get(session.gathering_node)
        if not node or node["depleted"] or not adjacent_or_same(session.x, session.y, *session.gathering_node):
            session.gathering_node = None
            continue
        ydef = RESOURCE_YIELDS[node["type"]]
        if session.level(ydef["skill"]) < ydef["level_req"]:
            session.gathering_node = None
            continue
        if not WORLD.has_gather_tool(session, ydef["skill"], allowed_tools=ydef.get("tools")):
            session.gathering_node = None
            continue
        if ydef["item"] in ORE_ITEM_IDS and WORLD.count_ores(session) >= MAX_ORES:
            await send(session.ws, "ERROR", message=f"You can't carry more than {MAX_ORES} ores. Bank some first.")
            session.gathering_node = None
            continue
        if not WORLD.add_item_to_inventory(session, ydef["item"], 1):
            await send(session.ws, "ERROR", message="Your inventory is full.")
            session.gathering_node = None
            continue
        before, after = WORLD.grant_xp(session, ydef["skill"], ydef["xp"])
        events.append({"type": "SKILL_XP", "data": {
            "player_id": session.player_id, "skill": ydef["skill"], "gained": ydef["xp"],
            "xp": session.xp[ydef["skill"]], "level": after, "leveled_up": after > before,
        }})
        await send(session.ws, "PLAYER_UPDATE", player=session.full_state())
        if fishing_spots.is_spot(node, ydef):
            # shared stock: every catch by anyone drains it; the spot moves when it's gone
            if fishing_spots.take_catch(node, WORLD.tick_count, ydef):
                await fish_spot_moves(session.gathering_node)
            continue
        # Quiet gather feedback — only announce depletion / first hit style messages elsewhere
        if ydef["depletion_chance"] > 0 and random.random() < ydef["depletion_chance"]:
            node["depleted"] = True
            node["respawn_at"] = WORLD.tick_count + RESOURCE_YIELDS[node["type"]]["respawn_ticks"]
            session.gathering_node = None
            rtype = node.get("type") or "resource"
            if "tree" in rtype:
                msg = "The tree has been chopped down."
            elif "rock" in rtype or "ore" in rtype:
                msg = "The rock is depleted."
            elif "fishing" in rtype:
                msg = "The fishing spot moves away."
            else:
                msg = "That resource is depleted."
            await send(session.ws, "CHAT_MSG", **{"from": "You", "text": msg})


def _respawn_delay(monster):
    """Ticks until a corpse stands back up. Unknown types wait about 15s."""
    data = MONSTERS.get(monster.type) or {}
    stats = monster.stats or {}
    ticks = stats.get("respawn_ticks", data.get("respawn_ticks", 25))
    if data.get("training_dummy") or stats.get("training_dummy"):
        return max(3, int(ticks))
    return max(10, int(ticks))


def _mark_monster_dead(monster):
    if getattr(monster, "raid_id", None) is not None:   # phase 9: remember who drove a raider off
        monster.killer_id = monster.target_player_id
    monster.alive = False
    monster.defeated = True
    monster.target_player_id = None
    if getattr(monster, "no_respawn", False):
        return
    monster.respawn_at_tick = WORLD.tick_count + _respawn_delay(monster)


def _floor_uncleared(dungeon):
    """Kills still owed across the map.

    For a segmented floor that is the sum of what each chamber still needs, not
    a count of living monsters: respawns must not make a floor unwinnable, and
    a chamber that has met its target is done however many beasts are still
    shuffling about inside it.
    """
    rooms = dungeon.get("rooms")
    if rooms:
        owed = 0
        for room in rooms:
            if room.get("cleared"):
                continue
            owed += max(0, int(room.get("kill_target") or 0) - int(room.get("kills") or 0))
        return owed
    return sum(1 for m in dungeon["monsters"].values() if not getattr(m, "defeated", False))


def _dungeon_remaining(dungeon):
    if dungeon.get("explore"):
        return sum(1 for m in dungeon["monsters"].values() if m.alive)
    return _floor_uncleared(dungeon)


def _revive_monster(monster):
    monster.hp = monster.max_hp
    monster.x, monster.y = monster.spawn_x, monster.spawn_y
    monster.alive = True
    monster.target_player_id = None
    monster.frozen_until = 0.0
    monster.patrol_steps_left = 0
    monster.fight_side = None


def process_monster_respawns():
    pending = list(WORLD.monsters.values())
    for session in WORLD.sessions.values():
        dungeon = getattr(session, "dungeon", None)
        if dungeon:
            pending.extend(dungeon["monsters"].values())
    for m in pending:
        if m.alive or getattr(m, "no_respawn", False):
            continue
        if m.respawn_at_tick <= 0:
            m.respawn_at_tick = WORLD.tick_count + _respawn_delay(m)
            continue
        if WORLD.tick_count >= m.respawn_at_tick:
            _revive_monster(m)


async def fish_spot_moves(pos):
    """The spot leaves its tile: everyone fishing it stops and is told, then it waits to reappear nearby."""
    pos = tuple(pos)
    node = WORLD.resource_nodes.get(pos)
    if not node:
        return
    ydef = RESOURCE_YIELDS.get(node["type"]) or {}
    WORLD.moving_fish_spots.append(fishing_spots.depart(WORLD.resource_nodes, pos, WORLD.tick_count, ydef))
    for s in list(WORLD.sessions.values()):
        if s.gathering_node and tuple(s.gathering_node) == pos:
            s.gathering_node = None
            await send(s.ws, "CHAT_MSG", **{"from": "You", "text": fishing_spots.MOVED_MSG})


async def process_fishing_spots():
    """Timed-out spots move; waiting spots come back 3-6 tiles from home."""
    tick = WORLD.tick_count
    for pos, node in list(WORLD.resource_nodes.items()):
        if node.get("is_fish_spot") and fishing_spots.expired(node, tick):
            await fish_spot_moves(pos)
    if WORLD.moving_fish_spots:
        from world_map import WATER, WALKABLE_TILES
        fishing_spots.return_due(WORLD.moving_fish_spots, WORLD.resource_nodes, WORLD.grid, tick,
                                 WATER, WALKABLE_TILES, RESOURCE_YIELDS)


def process_resource_respawns():
    for pos, node in WORLD.resource_nodes.items():
        if node["depleted"] and WORLD.tick_count >= node["respawn_at"]:
            node["depleted"] = False


def side_by_side_goal(monster, px, py, can_stand):
    """Post for a foe that must share the player's row.

    False: already in reach, so hold still.
    None: this foe does not fight side by side.
    (x, y): walk toward that tile.
    """
    mdef = monster.def_stats() or {}
    if not mdef.get("side_by_side"):
        return None
    px, py = int(px), int(py)
    reach = max(1, int(mdef.get("attack_range") or 1))
    gap = abs(int(monster.x) - px)
    if int(monster.y) == py and 1 <= gap <= reach:
        return False
    prefer = max(1, min(int(mdef.get("side_gap") or 2), reach))
    side = getattr(monster, "fight_side", None)
    if side not in (1, -1):
        side = 1 if monster.x >= px else -1
        monster.fight_side = side
    fallback = None
    for g in (prefer, 3, 2, 1, 4):
        if g < 1 or g > reach:
            continue
        for s in (side, -side):
            tx, ty = px + s * g, py
            if (tx, ty) == (px, py):
                continue
            if fallback is None:
                fallback = (tx, ty)
            if can_stand(tx, ty):
                monster.fight_side = s
                return (tx, ty)
    return fallback


def _walk_sheet_ids():
    """Monster ids whose HD pack includes a walk cycle."""
    found = getattr(_walk_sheet_ids, "ids", None)
    if found is not None:
        return found
    assets = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    ids = set()
    for root in (
        os.path.join(assets, "monsters_hd"),
        os.path.join(assets, "knights_hd", "assets"),
    ):
        if not os.path.isdir(root):
            continue
        for name in os.listdir(root):
            walk = os.path.join(root, name, "sprite_1x", "walk")
            if os.path.isdir(walk):
                ids.add(name)
    _walk_sheet_ids.ids = ids
    return ids


def dungeon_idle_patrol(monster, can_step):
    """Walk a few tiles out from spawn, then back, and repeat.

    Only monsters with a walk sheet do this. Combat chase is unchanged.
    """
    if not monster.alive or (monster.stats or {}).get("static"):
        return False
    if monster.type not in _walk_sheet_ids():
        return False
    mdef = MONSTERS.get(monster.type) or {}
    radius = int((monster.stats or {}).get("wander_radius", mdef.get("wander_radius") or 0) or 0)
    if radius <= 0:
        radius = 3
    radius = min(radius, 4)

    def inside(nx, ny):
        return (
            abs(nx - monster.spawn_x) <= radius
            and abs(ny - monster.spawn_y) <= radius
            and can_step(nx, ny)
        )

    pause = int(getattr(monster, "patrol_pause", 0) or 0)
    if pause > 0:
        monster.patrol_pause = pause - 1
        return False

    if monster.patrol_steps_left > 0:
        nx = monster.x + monster.patrol_dx
        ny = monster.y + monster.patrol_dy
        if inside(nx, ny):
            monster.x, monster.y = nx, ny
            monster.patrol_steps_left -= 1
            if monster.patrol_steps_left == 0 and getattr(monster, "patrol_leg", "") == "out":
                monster.patrol_dx = -monster.patrol_dx
                monster.patrol_dy = -monster.patrol_dy
                monster.patrol_steps_left = int(getattr(monster, "patrol_return", 0) or 0)
                monster.patrol_leg = "back"
            elif monster.patrol_steps_left == 0:
                monster.patrol_leg = ""
                monster.patrol_pause = 2
            return True
        monster.patrol_steps_left = 0
        monster.patrol_leg = ""
        monster.patrol_pause = 2
        return False

    cap = min(3, radius)
    dirs = [(1, 0), (-1, 0), (0, 1), (0, -1)]
    random.shuffle(dirs)
    for dx, dy in dirs:
        n = 0
        x, y = monster.x, monster.y
        while n < cap:
            tx, ty = x + dx, y + dy
            if not inside(tx, ty):
                break
            x, y = tx, ty
            n += 1
        if n < 1:
            continue
        monster.x += dx
        monster.y += dy
        monster.patrol_return = n
        if n == 1:
            monster.patrol_dx, monster.patrol_dy = -dx, -dy
            monster.patrol_steps_left = 1
            monster.patrol_leg = "back"
        else:
            monster.patrol_dx, monster.patrol_dy = dx, dy
            monster.patrol_steps_left = n - 1
            monster.patrol_leg = "out"
        return True
    monster.patrol_pause = 2
    return False


def process_dungeon_ai():
    """At most one monster chases, and only while you are still in its area."""
    max_pursuers = 1
    for session in list(WORLD.sessions.values()):
        if not session.dungeon:
            continue
        tiles = session.dungeon["tiles"]
        mod = _dungeon_mod(session)
        if session.dungeon.get("v2"):
            import void_v2
            void_v2.process_ai(session)
            continue
        monsters = list(session.dungeon["monsters"].values())

        def occupied(nx, ny, me):
            return any(o.alive and o.id != me.id and o.x == nx and o.y == ny for o in monsters)

        def step_toward(m, tx, ty, stay_in_room):
            if (m.x, m.y) == (tx, ty):
                return
            ember = session.dungeon.get("id") == "emberdeep"
            if ember and WORLD.tick_count - getattr(m, "ember_step_tick", -99) < 3:
                return
            dx = 0 if tx == m.x else (1 if tx > m.x else -1)
            dy = 0 if ty == m.y else (1 if ty > m.y else -1)
            if abs(tx - m.x) >= abs(ty - m.y):
                steps = [(dx, 0), (0, dy)] if ember else [(dx, 0), (0, dy), (dx, dy)]
            else:
                steps = [(0, dy), (dx, 0)] if ember else [(0, dy), (dx, 0), (dx, dy)]
            for sx, sy in steps:
                if sx == 0 and sy == 0:
                    continue
                nx, ny = m.x + sx, m.y + sy
                if (nx, ny) == (session.x, session.y):
                    continue
                if stay_in_room and m.home_room and not in_room(nx, ny, m.home_room):
                    continue
                if not mod.dungeon_walkable(tiles, nx, ny) or occupied(nx, ny, m):
                    continue
                m.x, m.y = nx, ny
                if ember:
                    m.ember_step_tick = WORLD.tick_count
                return

        def can_patrol_step(me, nx, ny):
            if (nx, ny) == (session.x, session.y):
                return False
            if me.home_room and not in_room(nx, ny, me.home_room):
                return False
            if not mod.dungeon_walkable(tiles, nx, ny) or occupied(nx, ny, me):
                return False
            return True

        eligible = []
        for m in monsters:
            if not m.alive:
                continue
            if (m.stats or {}).get("static"):
                continue
            in_area = in_room(session.x, session.y, m.home_room) if m.home_room else True
            if not in_area:
                if m.target_player_id == session.player_id:
                    m.target_player_id = None
                if session.in_combat_with == ("monster", m.id):
                    session.in_combat_with = None
                if (m.x, m.y) != (m.spawn_x, m.spawn_y):
                    m.patrol_steps_left = 0
                    step_toward(m, m.spawn_x, m.spawn_y, stay_in_room=True)
                else:
                    dungeon_idle_patrol(m, lambda nx, ny, me=m: can_patrol_step(me, nx, ny))
                continue
            dist = max(abs(session.x - m.x), abs(session.y - m.y))
            eligible.append((dist, m.id, m))
        eligible.sort()
        active_ids = {mid for _dist, mid, _m in eligible[:max_pursuers]}
        closest_strike = None
        for dist, mid, m in eligible:
            if mid not in active_ids:
                if m.target_player_id == session.player_id:
                    m.target_player_id = None
                if session.in_combat_with == ("monster", m.id):
                    session.in_combat_with = None
                dungeon_idle_patrol(m, lambda nx, ny, me=m: can_patrol_step(me, nx, ny))
                continue
            m.patrol_steps_left = 0
            m.patrol_leg = ""
            m.target_player_id = session.player_id
            reach = 1
            mdef = MONSTERS.get(m.type) or {}
            if m.stats:
                reach = max(1, int(m.stats.get("attack_range") or mdef.get("attack_range") or 1))
            else:
                reach = max(1, int(mdef.get("attack_range") or 1))
            if dist <= reach and closest_strike is None:
                closest_strike = m.id

            def can_stand(tx, ty, me=m):
                if (tx, ty) == (session.x, session.y):
                    return False
                if me.home_room and not in_room(tx, ty, me.home_room):
                    return False
                if not mod.dungeon_walkable(tiles, tx, ty) or occupied(tx, ty, me):
                    return False
                return True

            goal = side_by_side_goal(m, session.x, session.y, can_stand)
            if goal is False:
                pass
            elif goal:
                step_toward(m, goal[0], goal[1], stay_in_room=True)
            elif dist > 1:
                step_toward(m, session.x, session.y, stay_in_room=True)
        engaged = None
        if session.in_combat_with and session.in_combat_with[0] == "monster":
            engaged = session.dungeon["monsters"].get(session.in_combat_with[1])
        # The wyrm never chases. A step away, or leaving the lair, ends the fight.
        boss_fight = bool(engaged and engaged.alive and (engaged.stats or {}).get("static"))
        fleeing = time.time() < float(getattr(session, "combat_flee_until", 0) or 0)
        if closest_strike is not None and not boss_fight and not fleeing:
            session.in_combat_with = ("monster", closest_strike)
        elif session.in_combat_with and session.in_combat_with[0] == "monster":
            current = engaged
            if fleeing:
                session.in_combat_with = None
            elif current and current.alive and (current.stats or {}).get("static"):
                if _ember_wyrm_can_hit(current, session.x, session.y) is False:
                    session.in_combat_with = None
            elif current is None or not current.alive or current.id not in active_ids:
                session.in_combat_with = None


def process_monster_ai():
    """Wander, aggro, chase, and force the player to fight back.

    Only one monster may target the same player at once.
    """
    MAX_ATTACKERS = 1

    def attackers_on(player_id):
        return sum(
            1 for mon in WORLD.monsters.values()
            if mon.alive and mon.target_player_id == player_id
        )

    for m in WORLD.monsters.values():
        if not m.alive:
            continue
        mdef = MONSTERS[m.type]
        if mdef.get("passive"):
            if mdef.get("strikes_in_place") and m.target_player_id:
                sess = WORLD.sessions.get(m.target_player_id)
                fighting = sess and sess.in_combat_with == ("monster", m.id)
                if not fighting:
                    m.target_player_id = None
            else:
                m.target_player_id = None
            continue
        aggro = mdef.get("aggro_range", 0)

        # Drop stale targets
        if m.target_player_id and m.target_player_id not in WORLD.sessions:
            m.target_player_id = None

        # Acquire aggro. A second monster waits until the first lets go.
        if aggro and not m.target_player_id:
            best = None
            best_d = None
            for s in WORLD.sessions.values():
                if getattr(s, "dungeon", None):
                    continue
                # Confined monsters only aggro players still inside their area
                if m.home_room and not in_room(s.x, s.y, m.home_room):
                    continue
                if attackers_on(s.player_id) >= MAX_ATTACKERS:
                    continue
                d = max(abs(s.x - m.x), abs(s.y - m.y))
                if d <= aggro and (best_d is None or d < best_d):
                    best, best_d = s, d
            if best:
                m.target_player_id = best.player_id
                # Lock the player into auto-hitting back only when the monster requires it
                fleeing = time.time() < float(getattr(best, "combat_flee_until", 0) or 0)
                if mdef.get("force_retaliate", True) and not best.in_combat_with and not fleeing:
                    best.in_combat_with = ("monster", m.id)

        if m.target_player_id:
            session = WORLD.sessions.get(m.target_player_id)
            if not session or getattr(session, "dungeon", None):
                m.target_player_id = None
                continue
            dist = max(abs(session.x - m.x), abs(session.y - m.y))
            atk_reach = max(1, int(mdef.get("attack_range") or 1))
            # Leave the lair → drop aggro immediately and walk home
            left_area = bool(m.home_room) and not in_room(session.x, session.y, m.home_room)
            leash = max(int(aggro) * 2, 10) if aggro else 10
            if left_area or dist > leash:
                if session.in_combat_with == ("monster", m.id):
                    session.in_combat_with = None
                m.target_player_id = None
                m.fight_side = None
                # Step toward spawn so the boss returns to its post
                if (m.x, m.y) != (m.spawn_x, m.spawn_y):
                    dx = 0 if m.spawn_x == m.x else (1 if m.spawn_x > m.x else -1)
                    dy = 0 if m.spawn_y == m.y else (1 if m.spawn_y > m.y else -1)
                    for sx, sy in ((dx, 0), (0, dy), (dx, dy)):
                        if sx == 0 and sy == 0:
                            continue
                        nx, ny = m.x + sx, m.y + sy
                        outside = bool(m.home_room) and not in_room(m.x, m.y, m.home_room)
                        if (is_walkable(WORLD.grid, nx, ny)
                                and (outside or in_room(nx, ny, m.home_room))
                                and not WORLD.occupied(nx, ny)):
                            m.x, m.y = nx, ny
                            break
                continue
            # Keep the player locked into fighting back (skipped when force_retaliate
            # is False, or while the player is fleeing after STOP_ATTACK).
            fleeing = time.time() < float(getattr(session, "combat_flee_until", 0) or 0)
            if mdef.get("force_retaliate", True) and not fleeing and dist <= atk_reach:
                if not session.in_combat_with or session.in_combat_with[0] != "monster":
                    session.in_combat_with = ("monster", m.id)
                elif session.in_combat_with[1] not in WORLD.monsters or not WORLD.monsters[session.in_combat_with[1]].alive:
                    session.in_combat_with = ("monster", m.id)
            # Side-by-side bosses: snap onto the player's row when above/below,
            # then hold still once parallel (stops the jump flicker).
            side_by_side = bool(mdef.get("side_by_side"))
            prefer = max(1, min(int(mdef.get("side_gap") or 2), atk_reach))
            if side_by_side:
                gap = abs(m.x - session.x)
                lined_up = (m.y == session.y and 1 <= gap <= atk_reach)
                if lined_up:
                    # Stay put on the side post (Y already matches)
                    pass
                else:
                    side = getattr(m, "fight_side", None)
                    if side not in (1, -1):
                        side = 1 if m.x >= session.x else -1
                        m.fight_side = side
                    placed = False
                    # Drop onto the player's row (same Y), east or west
                    for g in (prefer, 3, 2, 1, 4):
                        if g > atk_reach and g != prefer:
                            continue
                        for s in (side, -side):
                            tx = session.x + s * g
                            ty = session.y
                            if (tx, ty) == (session.x, session.y):
                                continue
                            if (is_walkable(WORLD.grid, tx, ty)
                                    and in_room(tx, ty, m.home_room)
                                    and not WORLD.occupied(tx, ty)):
                                m.x, m.y = tx, ty
                                m.fight_side = s
                                placed = True
                                break
                        if placed:
                            break
                    if not placed:
                        # At minimum, drop onto the player's row this tick
                        if m.y != session.y:
                            old_y = m.y
                            m.y = session.y
                            if (WORLD.occupied(m.x, m.y)
                                    or not is_walkable(WORLD.grid, m.x, m.y)
                                    or not in_room(m.x, m.y, m.home_room)):
                                # Side-step off the player / unblock
                                stepped = False
                                for s in (side, -side, 1, -1):
                                    nx = session.x + s
                                    if (is_walkable(WORLD.grid, nx, session.y)
                                            and in_room(nx, session.y, m.home_room)
                                            and not WORLD.occupied(nx, session.y)):
                                        m.x, m.y = nx, session.y
                                        m.fight_side = s if s in (1, -1) else side
                                        stepped = True
                                        break
                                if not stepped:
                                    m.y = old_y
            elif dist > atk_reach:
                # Generic chase: step toward the player
                dx = 0 if session.x == m.x else (1 if session.x > m.x else -1)
                dy = 0 if session.y == m.y else (1 if session.y > m.y else -1)
                for sx, sy in ((dx, 0), (0, dy), (dx, dy)):
                    if sx == 0 and sy == 0:
                        continue
                    nx, ny = m.x + sx, m.y + sy
                    if (is_walkable(WORLD.grid, nx, ny)
                            and in_room(nx, ny, m.home_room)
                            and not WORLD.occupied(nx, ny)):
                        m.x, m.y = nx, ny
                        break
            continue

        # Idle wander when not aggro'd
        m.ticks_since_wander += 1
        # Continue an in-progress short patrol leg (one tile per tick)
        if m.patrol_steps_left > 0:
            nx, ny = m.x + m.patrol_dx, m.y + m.patrol_dy
            radius = int(mdef.get("wander_radius") or 0)
            if (radius > 0
                    and is_walkable(WORLD.grid, nx, ny)
                    and abs(nx - m.spawn_x) <= radius
                    and abs(ny - m.spawn_y) <= radius
                    and in_room(nx, ny, m.home_room)
                    and not WORLD.occupied(nx, ny)):
                m.x, m.y = nx, ny
                m.patrol_steps_left -= 1
            else:
                m.patrol_steps_left = 0
            continue

        wander_ticks = mdef.get("wander_ticks", 5)
        if m.ticks_since_wander < wander_ticks:
            continue
        m.ticks_since_wander = 0
        radius = int(mdef.get("wander_radius") or 0)
        if radius <= 0:
            continue
        if random.random() >= mdef.get("wander_chance", 0.4):
            continue  # stand still this cycle
        # Prefer a short straight patrol (2–4 steps) when configured
        step_range = mdef.get("patrol_steps")
        if step_range:
            lo, hi = int(step_range[0]), int(step_range[1])
            dx, dy = random.choice([(1, 0), (-1, 0), (0, 1), (0, -1)])
            steps = random.randint(lo, hi)
            nx, ny = m.x + dx, m.y + dy
            if (is_walkable(WORLD.grid, nx, ny)
                    and abs(nx - m.spawn_x) <= radius
                    and abs(ny - m.spawn_y) <= radius
                    and in_room(nx, ny, m.home_room)
                    and not WORLD.occupied(nx, ny)):
                m.x, m.y = nx, ny
                m.patrol_dx, m.patrol_dy = dx, dy
                m.patrol_steps_left = max(0, steps - 1)
        else:
            dx, dy = random.choice([(1, 0), (-1, 0), (0, 1), (0, -1)])
            nx, ny = m.x + dx, m.y + dy
            if (is_walkable(WORLD.grid, nx, ny)
                    and abs(nx - m.spawn_x) <= radius
                    and abs(ny - m.spawn_y) <= radius
                    and in_room(nx, ny, m.home_room)
                    and not WORLD.occupied(nx, ny)):
                m.x, m.y = nx, ny

    # If a click pulled a second monster in, keep only the one being fought.
    by_player = {}
    for mon in WORLD.monsters.values():
        if mon.alive and mon.target_player_id:
            by_player.setdefault(mon.target_player_id, []).append(mon)
    for pid, group in by_player.items():
        if len(group) <= MAX_ATTACKERS:
            continue
        sess = WORLD.sessions.get(pid)
        keep = None
        if sess and sess.in_combat_with and sess.in_combat_with[0] == "monster":
            keep = next((mon for mon in group if mon.id == sess.in_combat_with[1]), None)
        if keep is None and sess:
            group.sort(key=lambda mon: max(abs(mon.x - sess.x), abs(mon.y - sess.y)))
            keep = group[0]
        elif keep is None:
            keep = group[0]
        for mon in group:
            if mon is keep:
                continue
            mon.target_player_id = None
            mon.fight_side = None


async def main():
    log.info("Starting MMORPG server on ws://%s:%s", HOST, PORT)
    async with websockets.serve(handler, HOST, PORT, ping_interval=20, ping_timeout=20):
        await game_loop()


if __name__ == "__main__":
    asyncio.run(main())
