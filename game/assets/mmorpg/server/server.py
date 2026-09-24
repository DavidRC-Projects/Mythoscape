"""
Server-authoritative MMORPG v0.1 server.

Run with:  python server.py
Requires:  pip install websockets
"""
import asyncio
import json
import time
import random
import itertools
import logging

import websockets

from content import (
    ITEMS, MONSTERS, MONSTER_SPAWNS, NPCS, SHOPS, QUESTS, XP_SKILLS, RESOURCE_YIELDS,
    CRAFT_RECIPES, INTERACTABLES, BUILDINGS, PETS,
    MAX_PURSE_COINS, MAX_BANK_COINS, MAX_ORES, ORE_ITEM_IDS, BANK_SLOTS,
    karma_total_bonus, FIRE_LOGS, cook_burn_chance, is_bow, bow_attack_range,
    MAGIC_ABILITIES, MAGIC_ABILITY_ORDER, MANUAL_MAGIC_CD_FACTOR,
    QUIVER_CAPACITY, TIP_BOX_CAPACITY, FOOD_BAG_CAPACITY, RAW_BAG_CAPACITY,
    RESOURCE_BAG_CAPACITY, RAW_FISH_IDS, COOKED_FISH_IDS, FLETCH_POUCH_IDS,
    INVENTORY_SIZE, INVENTORY_TAB_SIZE, INVENTORY_TABS,
    is_arrowtip, is_raw_fish, is_cooked_fish,
    is_mining_bag_item, is_log_item, is_fletch_pouch_item, is_potion_item,
    is_gem_item,
    inventory_tab_for_item, is_storage_bag,
)
from database import Database
from world_map import (
    generate_world, build_resource_nodes, is_walkable, WIDTH, HEIGHT, SPAWN_POINT, get_zone,
    room_containing, in_room, FLOOR,
)
import combat
import dungeon as tidehollow
import emberdeep

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("server")

# Private instance dungeons keyed by id (interactable dungeon_id / session.dungeon["id"])
DUNGEON_MODS = {
    "tidehollow": tidehollow,
    "emberdeep": emberdeep,
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
}

TICK_SECONDS = 0.6
HOST = "0.0.0.0"
PORT = 8765

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
        self.player_id = row["id"]
        self.username = row["username"]
        self.char_name = row["char_name"]
        self.x = row["x"]
        self.y = row["y"]
        self.hp = row["hp"]
        raw_gender = row["gender"] if "gender" in row.keys() else "male"
        self.gender = "female" if str(raw_gender).lower() == "female" else "male"
        self.last_wish_date = row["last_wish_date"] if "last_wish_date" in row.keys() else None
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
        }
        self.coins = min(int(row["coins"]), MAX_PURSE_COINS)
        self.bank_coins = int(row["bank_coins"]) if "bank_coins" in row.keys() else 0
        self.bank = {}  # slot -> {item_id, qty}
        self.equipment = {
            "weapon": row["equip_weapon"], "shield": row["equip_shield"],
            "body": row["equip_body"], "legs": row["equip_legs"],
            "helmet": row["equip_helmet"] if "equip_helmet" in row.keys() else None,
            "amulet": row["equip_amulet"] if "equip_amulet" in row.keys() else None,
            "ring": row["equip_ring"] if "equip_ring" in row.keys() else None,
            "ammo": row["equip_ammo"] if "equip_ammo" in row.keys() else None,
        }
        self.inventory = {}  # slot -> {"item_id":, "qty":}
        self.quests = {}     # quest_id -> {"status":, "progress":}
        self.quest_log_dirty = False  # push QUEST_LOG on next tick flush
        self.in_combat_with = None   # ("monster", instance_id) or ("player", player_id)
        self.combat_style = "attack"  # attack | strength | defence | hitpoints | archery
        self.gathering_node = None   # (x, y) currently gathering
        self.dungeon = None  # Tidehollow private instance state or None
        self.trade_partner_id = None
        self.trade_offer = {}        # slot -> qty
        self.trade_confirmed = False
        self.last_move_tick = 0
        self.last_equip_regen_at = 0.0  # passive HP from worn gear (e.g. Tidehollow Medal)
        self.auto_pickup_items = bool(row["auto_pickup_items"]) if "auto_pickup_items" in row.keys() else False
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
        self.fletch_pouch = self._load_bag_dict(row, "fletch_pouch_contents", is_fletch_pouch_item, RESOURCE_BAG_CAPACITY)
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
                        out[iid] = max(0, min(int(capacity), int(qty)))
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
        return self.level("hitpoints")

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
        space = max(0, int(capacity) - cur)
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
            self.fletch_pouch, "fletch_pouch_contents", RESOURCE_BAG_CAPACITY,
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
        }

    def public_state(self):
        return {
            "id": self.player_id, "name": self.char_name, "x": self.x, "y": self.y,
            "hp": self.hp, "max_hp": self.max_hp(),
            "combat_level": self.combat_level(),
            "equipment": self.equipment,  # client uses this for sprite weapons/armor
            "gathering": self.gathering_public(),
            "gender": self.gender,
        }

    def total_level(self):
        return sum(self.level(s) for s in XP_SKILLS)

    def combat_level(self):
        return combat.combat_level(
            self.level("attack"), self.level("strength"),
            self.level("defence"), self.level("hitpoints"),
            self.level("archery") if "archery" in self.xp else 1,
        )

    def full_state(self):
        wb = self.weapon_bonuses()
        karma_lvl = self.level("karma") if "karma" in self.xp else 1
        levels = {s: self.level(s) for s in XP_SKILLS}
        return {
            "id": self.player_id, "name": self.char_name, "x": self.x, "y": self.y,
            "hp": self.hp, "max_hp": self.max_hp(), "coins": self.coins,
            "bank_coins": self.bank_coins,
            "levels": levels,
            "xp": self.xp,
            "total_level": sum(levels.values()),
            "combat_level": self.combat_level(),
            "equipment": self.equipment,
            "inventory": self.inventory,
            "combat_style": self.combat_style,
            "auto_pickup_items": self.auto_pickup_items,
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
            "wish_available": self.can_wish(),
            "unlimited_wishes": self.has_unlimited_wishes(),
            "quest_points": self.quest_points(),
            "magic": self.magic_public(),
            "quiver": dict(self.quiver),
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
        self.pet_x, self.pet_y = self.x, self.y
        self.pet_target_id = None
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
        # Short multi-step patrol (castle knights / city guards)
        self.patrol_dx = 0
        self.patrol_dy = 0
        self.patrol_steps_left = 0
        # Dungeon monsters are confined to the room they spawned in
        self.home_room = None if stats else room_containing(x, y)

    def is_frozen(self):
        return time.time() < float(self.frozen_until or 0)

    def def_stats(self):
        if self.stats:
            return self.stats
        return MONSTERS[self.type]

    def public_state(self):
        mdef = self.def_stats()
        name = mdef.get("name") or MONSTERS.get(self.type, {}).get("name", "Monster")
        frozen = self.is_frozen()
        return {
            "id": self.id, "type": self.type, "name": name,
            "level": mdef.get("level", 1),
            "x": self.x, "y": self.y, "hp": self.hp, "max_hp": self.max_hp, "alive": self.alive,
            "frozen": frozen,
        }


# ---------------------------------------------------------------------------
# World / server state
# ---------------------------------------------------------------------------
class World:
    def __init__(self):
        self.db = Database()
        self.grid = generate_world()
        self.resource_nodes = build_resource_nodes(self.grid)
        self.monsters = {}
        for mtype, x, y in MONSTER_SPAWNS:
            mid = next_id()
            self.monsters[mid] = MonsterInstance(mid, mtype, x, y)
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

    def has_gather_tool(self, session, skill, allowed_tools=None):
        """True if inventory or equipped weapon is a valid gather tool.

        If allowed_tools is a list of item ids, one of those must be present.
        Otherwise any item with tool_for == skill counts.
        """
        def ok(item_id):
            if not item_id:
                return False
            if allowed_tools:
                return item_id in allowed_tools
            return ITEMS.get(item_id, {}).get("tool_for") == skill

        weapon = session.equipment.get("weapon")
        if ok(weapon):
            return True
        for entry in session.inventory.values():
            if ok(entry["item_id"]):
                return True
        return False

    def count_item_bank(self, session, item_id):
        return sum(e["qty"] for e in session.bank.values() if e["item_id"] == item_id)

    def ensure_tinderbox(self, session):
        """Existing characters predating firemaking get a free tinderbox once."""
        if self.count_item(session, "tinderbox") > 0 or self.count_item_bank(session, "tinderbox") > 0:
            return False
        return self.add_item_to_inventory(session, "tinderbox", 1)

    def ensure_david_mythos_helm(self, session):
        """One-off Mythos Dragon Helm for username david (if they don't already own one)."""
        if (session.username or "").strip().lower() != "david":
            return False
        if session.equipment.get("helmet") == "mythos_helmet":
            return False
        if self.count_item(session, "mythos_helmet") > 0 or self.count_item_bank(session, "mythos_helmet") > 0:
            return False
        return self.add_item_to_inventory(session, "mythos_helmet", 1)

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
        before = session.level(skill)
        session.xp[skill] += amount
        after = session.level(skill)
        if skill == "hitpoints" and after > before:
            session.hp += (after - before)  # HP levels heal you up by the level gained
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
            dropped.append({"item_id": item_id, "qty": qty})
        if dropped:
            self.ground_items.setdefault((x, y), []).extend(dropped)
        return dropped


WORLD = World()


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


def quest_status_for(session, quest_id):
    return session.quests.get(quest_id, {"status": "not_started", "progress": 0})


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
    if qdef["type"] == "find_npc":
        npc = NPC_BY_ID.get(qdef["target"]) or {}
        name = npc.get("name") or qdef["target"].replace("_", " ").title()
        if status in ("ready", "complete"):
            return f"Spoke with {name}"
        return f"Find and speak to {name}"
    if qdef["type"] == "gift":
        return "Talk to receive your reward"
    return qdef.get("description", "")


def check_quest_progress_on_kill(session, monster_type):
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
        await send(
            session.ws, "QUEST_LOG",
            quests={qid: quest_status_for(session, qid) for qid in QUESTS},
        )


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
        char_name = (msg.get("char_name") or username).strip()[:16]
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
        await send(ws, "LOGIN_FAIL", reason="That character is already logged in.")
        return

    session = PlayerSession(ws, row)
    # Clamp / reset position if the world layout changed since last save.
    if not is_walkable(WORLD.grid, session.x, session.y):
        session.x, session.y = SPAWN_POINT
        WORLD.db.save_player_position(session.player_id, session.x, session.y)
    session.inventory = WORLD.db.get_inventory(row["id"])
    session.bank = WORLD.db.get_bank(row["id"])
    session.quests = WORLD.db.get_quest_progress(row["id"])
    WORLD.sessions[session.player_id] = session
    enforce_bound_items(session)
    WORLD.rearrange_bags_tab(session)
    # Persist owned-pets list (includes migrated active_pet)
    WORLD.db.save_player_stats(session.player_id, owned_pets=json.dumps(session.owned_pets))
    if WORLD.ensure_tinderbox(session):
        log.info("%s received a starter tinderbox", session.char_name)
    if WORLD.ensure_david_mythos_helm(session):
        log.info("%s received a one-off Mythos Dragon Helm", session.char_name)

    needs_alloc = not session.stats_allocated
    await send(ws, "LOGIN_OK", player=session.full_state(), needs_stat_alloc=needs_alloc)
    if needs_alloc:
        await send(
            ws, "STAT_ALLOC_REQUIRED",
            points=10,
            skills=["attack", "strength", "defence", "hitpoints"],
            base_levels={"attack": 5, "strength": 5, "defence": 5, "hitpoints": 10},
        )
        log.info("%s logged in as %s (id=%s) — awaiting stat allocation", username, session.char_name, session.player_id)
        return

    await send_world_join(session)
    log.info("%s logged in as %s (id=%s)", username, session.char_name, session.player_id)


async def send_world_join(session):
    await send(
        session.ws, "WORLD_STATE",
        width=WIDTH, height=HEIGHT, tiles=WORLD.grid, npcs=NPCS,
        resources={f"{x},{y}": n["type"] for (x, y), n in WORLD.resource_nodes.items() if not n["depleted"]},
        interactables=INTERACTABLES,
        craft_recipes=CRAFT_RECIPES,
        buildings=BUILDINGS,
    )
    quest_log = {qid: quest_status_for(session, qid) for qid in QUESTS}
    await send(session.ws, "QUEST_LOG", quests=quest_log)
    await send(session.ws, "PLAYER_UPDATE", player=session.full_state())
    await send_starter_tips(session)


async def send_starter_tips(session):
    """Short first-session pointers — H for the full help list."""
    tips = [
        "Welcome to Mythoscape! Press H anytime for controls · Esc closes popups.",
        "Talk to Elder Miriam (NW) for a quest, Elena (east) for a free bow kit, Lira for jewelry (B = shop).",
        "Bank (B): Deposit inventory, shift-click vault to withdraw 1. Purse max 65k — keep coins in the vault.",
        "Gareth smelts & smiths (F) — jewelry too. Mira sells food. Tidehollow Cave is at Harbourreach.",
        "P toggles auto-pickup · Tab skills · Q journal · M travel · Space attacks · R eats food (bags first).",
    ]
    for text in tips:
        await send(session.ws, "CHAT_MSG", **{"from": "Guide", "text": text})


async def handle_allocate_stats(session, msg):
    if session.stats_allocated:
        await send(session.ws, "ERROR", message="You already chose your starting stats.")
        return
    allowed = ("attack", "strength", "defence", "hitpoints")
    raw = msg.get("stats") or {}
    try:
        alloc = {s: max(0, int(raw.get(s, 0))) for s in allowed}
    except (TypeError, ValueError):
        await send(session.ws, "ERROR", message="Invalid stat allocation.")
        return
    if sum(alloc.values()) != 10:
        await send(session.ws, "ERROR", message="You must spend exactly 10 stat points.")
        return
    base = {"attack": 5, "strength": 5, "defence": 5, "hitpoints": 10}
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
    WORLD.db.save_player_stats(session.player_id, **xp_fields)
    session.stats_allocated = True
    await send(session.ws, "CHAT_MSG", **{
        "from": "World",
        "text": "Your starting stats are set. Welcome to Mythoscape!",
    })
    await send_world_join(session)
    log.info("%s allocated starting stats %s", session.username, alloc)


def item_is_sellable(item_id):
    item = ITEMS.get(item_id) or {}
    return item.get("sellable", True) and item.get("tradeable", True)


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


def session_has_item(session, item_id):
    if item_id in (session.equipment or {}).values():
        return True
    return any(e.get("item_id") == item_id for e in session.inventory.values())


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
    limit = max(1, min(10, int(msg.get("limit", 5))))
    boards = WORLD.db.get_leaderboards(limit=limit)
    # Total overall first, then individual skills
    skills = ["total"] + [s for s in XP_SKILLS if s in boards]
    await send(ws, "LEADERBOARD", skills=skills, boards=boards)


async def handle_move(session, msg):
    dx, dy = msg.get("dx", 0), msg.get("dy", 0)
    if abs(dx) + abs(dy) != 1:
        return
    nx, ny = session.x + dx, session.y + dy
    if session.dungeon:
        mod = _dungeon_mod(session)
        if not mod or not mod.dungeon_walkable(session.dungeon["tiles"], nx, ny):
            return
        session.x, session.y = nx, ny
        session.gathering_node = None
        await send(session.ws, "PLAYER_UPDATE", player=session.full_state())
        return
    if not is_walkable(WORLD.grid, nx, ny):
        return
    if WORLD.occupied(nx, ny, exclude_player=session.player_id):
        return
    session.x, session.y = nx, ny
    session.gathering_node = None
    WORLD.db.save_player_position(session.player_id, nx, ny)
    await vacuum_ground_loot(session)
    await send(session.ws, "PLAYER_UPDATE", player=session.full_state())


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
    tiles = mod.generate_floor_tiles(floor)
    spots = mod.pick_spawn_tiles(tiles, info["count"])
    stats = mod.scaled_monster_stats(info["level"])
    visual = mod.visual_type_for_floor(floor)
    if hasattr(mod, "monster_display_name"):
        stats["name"] = mod.monster_display_name(visual, info["level"])
    monsters = {}
    for sx, sy in spots:
        mid = next_id()
        m = MonsterInstance(mid, visual, sx, sy, stats=dict(stats), no_respawn=True)
        m.target_player_id = session.player_id
        monsters[mid] = m
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
        "return_x": prev.get("return_x", mod.CAVE_RETURN[0]),
        "return_y": prev.get("return_y", mod.CAVE_RETURN[1]),
    }
    session.x, session.y = mod.DUNGEON_SPAWN
    session.in_combat_with = None
    session.gathering_node = None
    if session.pet_id:
        session.pet_x, session.pet_y = session.x, session.y
        session.pet_target_id = None


def _dungeon_payload(session):
    d = session.dungeon
    alive = [m.public_state() for m in d["monsters"].values() if m.alive]
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
    return {
        "id": d["id"],
        "floor": d["floor"],
        "floors": d["floors"],
        "label": d["label"],
        "tiles": d["tiles"],
        "width": d["width"],
        "height": d["height"],
        "monsters": alive,
        "remaining": len(alive),
        "player_x": session.x,
        "player_y": session.y,
        "exit_x": exit_x,
        "exit_y": exit_y,
    }


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


def _find_dungeon_entrance(session, preferred_id=None):
    """Return (spot, dungeon_id) if the player stands at a private-dungeon mouth."""
    kinds = set()
    for meta in DUNGEON_META.values():
        kinds.update(meta["entrance_kinds"])
    for spot in INTERACTABLES:
        kind = spot.get("kind")
        if kind not in kinds:
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


async def handle_enter_dungeon(session, msg):
    if session.dungeon:
        meta = _dungeon_meta(session.dungeon.get("id") or "tidehollow")
        await send(session.ws, "ERROR", message=f"You are already inside {meta['name']}.")
        return
    preferred = msg.get("dungeon_id")
    spot, dungeon_id = _find_dungeon_entrance(session, preferred_id=preferred)
    if not dungeon_id:
        await send(session.ws, "ERROR", message="Stand at a dungeon entrance.")
        return
    mod = DUNGEON_MODS.get(dungeon_id, tidehollow)
    meta = _dungeon_meta(dungeon_id)
    session._dungeon_return = (session.x, session.y)
    _build_dungeon_floor(session, 1, dungeon_id=dungeon_id)
    session.dungeon["return_x"] = mod.CAVE_RETURN[0]
    session.dungeon["return_y"] = mod.CAVE_RETURN[1]
    await send(session.ws, "DUNGEON_ENTER", **_dungeon_payload(session))
    await send(session.ws, "PLAYER_UPDATE", player=session.full_state())
    await send(
        session.ws, "CHAT_MSG",
        **{"from": meta["chat_from"],
           "text": f"Floor 1/{session.dungeon['floors']}: {session.dungeon['label']}. Slay every beast to advance."},
    )


async def handle_leave_dungeon(session, msg=None, silent=False):
    if not session.dungeon:
        return
    dungeon_id = session.dungeon.get("id") or "tidehollow"
    mod = DUNGEON_MODS.get(dungeon_id, tidehollow)
    meta = _dungeon_meta(dungeon_id)
    rx, ry = session.dungeon.get("return_x"), session.dungeon.get("return_y")
    saved = getattr(session, "_dungeon_return", None)
    if saved:
        rx, ry = saved
    session.dungeon = None
    session.in_combat_with = None
    session.pet_target_id = None
    session.x = rx if rx is not None else mod.CAVE_RETURN[0]
    session.y = ry if ry is not None else mod.CAVE_RETURN[1]
    WORLD.db.save_player_position(session.player_id, session.x, session.y)
    if session.pet_id:
        session.pet_x, session.pet_y = session.x, session.y
    await send(session.ws, "DUNGEON_EXIT", x=session.x, y=session.y)
    await send(session.ws, "PLAYER_UPDATE", player=session.full_state())
    if not silent:
        await send(session.ws, "CHAT_MSG", **{"from": meta["chat_from"], "text": f"You leave {meta['name']}."})


async def _dungeon_on_clear(session):
    """Called when the last monster on the current floor dies."""
    d = session.dungeon
    if not d:
        return
    dungeon_id = d.get("id") or "tidehollow"
    mod = DUNGEON_MODS.get(dungeon_id, tidehollow)
    meta = _dungeon_meta(dungeon_id)
    chat_from = meta["chat_from"]
    floor = d["floor"]
    if floor >= d["floors"]:
        # Complete!
        item_id, qty = mod.pick_completion_reward()
        medal_id = meta["medal_id"]
        drop_xy = (mod.CAVE_RETURN[0], mod.CAVE_RETURN[1])
        rewards = []
        if item_id == "coins":
            gained, left = WORLD.add_coins(session, qty)
            rewards.append({"item_id": "coins", "qty": gained})
            if left:
                WORLD.ground_items.setdefault(drop_xy, []).append(
                    {"item_id": "coins", "qty": left}
                )
        elif WORLD.add_item_to_inventory(session, item_id, qty):
            rewards.append({"item_id": item_id, "qty": qty})
        else:
            WORLD.ground_items.setdefault(drop_xy, []).append(
                {"item_id": item_id, "qty": qty}
            )
            rewards.append({"item_id": item_id, "qty": qty, "ground": True})
        # Medal — inventory or equip if free
        has_medal = (
            session.equipment.get("amulet") == medal_id
            or any(e and e.get("item_id") == medal_id for e in session.inventory.values())
        )
        if not has_medal:
            if not session.equipment.get("amulet"):
                session.equipment["amulet"] = medal_id
                WORLD.db.set_equipment(session.player_id, "amulet", medal_id)
            elif WORLD.add_item_to_inventory(session, medal_id, 1):
                pass
            else:
                WORLD.ground_items.setdefault(drop_xy, []).append(
                    {"item_id": medal_id, "qty": 1}
                )
            rewards.append({"item_id": medal_id, "qty": 1})
        name = session.char_name
        reward_name = ITEMS.get(item_id, {}).get("name", item_id)
        await handle_leave_dungeon(session, silent=True)
        await send(session.ws, "DUNGEON_COMPLETE", rewards=rewards)
        await send(session.ws, "PLAYER_UPDATE", player=session.full_state())
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
        return

    # Advance to next floor
    nxt = floor + 1
    _build_dungeon_floor(session, nxt, dungeon_id=dungeon_id)
    await send(session.ws, "DUNGEON_FLOOR", **_dungeon_payload(session))
    await send(session.ws, "PLAYER_UPDATE", player=session.full_state())
    await send(
        session.ws, "CHAT_MSG",
        **{"from": chat_from,
           "text": f"Floor {nxt}/{session.dungeon['floors']}: {session.dungeon['label']}. The beasts grow fiercer."},
    )


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
                    remaining.append({"item_id": "coins", "qty": left})
                continue
            # Always bury bones from vacuum range (never keep them from the ground)
            if ITEMS.get(item_id, {}).get("karma_xp"):
                await bury_bone_stack(session, item_id, qty, quiet=True)
                bones_buried += qty
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
    if "auto_pickup_items" in msg:
        session.auto_pickup_items = bool(msg["auto_pickup_items"])
        WORLD.db.save_player_stats(session.player_id, auto_pickup_items=1 if session.auto_pickup_items else 0)
        state = "ON" if session.auto_pickup_items else "OFF"
        await send(session.ws, "CHAT_MSG", **{
            "from": "Options", "text": f"Auto-pickup items: {state} (coins always collect).",
        })
        await send(session.ws, "PLAYER_UPDATE", player=session.full_state())


async def handle_chat(session, msg):
    text = (msg.get("text") or "").strip()[:200]
    if not text:
        return
    await broadcast("CHAT_MSG", **{"from": session.char_name, "text": text})


WISH_WELL_POS = (30, 21)

WISH_GEAR_POOL = [
    # Common / uncommon armour & weapons
    "leather_body", "leather_chaps", "leather_cowl",
    "bronze_sword", "bronze_dagger", "bronze_battleaxe",
    "bronze_helmet", "bronze_sq_shield", "bronze_body", "bronze_legs",
    "bronze_chainbody", "bronze_chainlegs",
    "iron_sword", "iron_dagger", "iron_battleaxe",
    "iron_helmet", "iron_sq_shield", "iron_body", "iron_legs",
    "iron_chainbody", "iron_chainlegs",
    "steel_longsword", "steel_dagger", "steel_battleaxe",
    "steel_helmet", "steel_sq_shield", "steel_body", "steel_legs",
    "steel_chainbody", "steel_chainlegs",
    "mithril_dagger", "mithril_sword", "mithril_helmet",
    "mithril_sq_shield", "mithril_chainbody", "mithril_chainlegs",
]

WISH_MYTHOS_POOL = [
    "mythos_dagger", "mythos_longsword", "mythos_body",
    "mythos_helmet", "mythos_legs", "mythos_shield",
]

# Mid/high gear given preferential weight on gear wishes
WISH_GEAR_BETTER = [
    "steel_longsword", "steel_battleaxe", "steel_body", "steel_legs",
    "steel_helmet", "steel_shield", "steel_chainbody", "steel_chainlegs",
    "mithril_dagger", "mithril_sword", "mithril_helmet",
    "mithril_sq_shield", "mithril_chainbody", "mithril_chainlegs",
    "mithril_body", "mithril_legs", "mithril_battleaxe", "mithril_shield",
    "adamant_chainbody", "adamant_body",
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
                skills=["attack", "strength", "defence", "hitpoints"],
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
        # 20% → 100, 20% → mid, 35% → 5k, 25% → 10k
        roll = random.random()
        if roll < 0.20:
            amount = 100
        elif roll < 0.40:
            amount = random.choice((1000, 1500, 2000, 2500, 3000))
        elif roll < 0.75:
            amount = 5000
        else:
            amount = 10000
            rare = True
        gained, left = WORLD.add_coins(session, amount)
        if left > 0:
            session.bank_coins = min(MAX_BANK_COINS, session.bank_coins + left)
            WORLD.db.save_player_stats(session.player_id, bank_coins=session.bank_coins)
            result_text = f"You wish for gold — {gained} fill your purse; {left} spill into the bank!"
        else:
            result_text = f"You wish for gold and receive {gained} coins!"
        if rare:
            await _broadcast_well_rare("gold", f"{session.char_name} hauled 10,000 coins from the well!")

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
    if skill not in ("attack", "strength", "defence", "hitpoints"):
        await send(session.ws, "ERROR", message="Choose attack, strength, defence, or hitpoints.")
        return
    cur = session.level(skill)
    new_level = min(99, cur + 1)
    session.xp[skill] = combat.xp_for_level(new_level)
    col = f"{skill}_xp"
    WORLD.db.save_player_stats(session.player_id, **{col: session.xp[skill]})
    if skill == "hitpoints":
        session.hp = min(session.max_hp(), session.hp + (new_level - cur))
        WORLD.db.save_player_stats(session.player_id, hp=session.hp)
    session.pending_wish_stat = False
    text = f"Your {skill.title()} permanently rises to level {new_level}!"
    await send(session.ws, "CHAT_MSG", **{"from": "Wishing Well", "text": text})
    await send(session.ws, "WISH_RESULT", kind="power", text=text, rare=True, skill=skill, level=new_level)
    await send(session.ws, "PLAYER_UPDATE", player=session.full_state())


def chebyshev(ax, ay, bx, by):
    return max(abs(ax - bx), abs(ay - by))


def adjacent_or_same(ax, ay, bx, by):
    return chebyshev(ax, ay, bx, by) <= 1


async def handle_attack(session, msg):
    target_id = msg.get("target_id")
    monster = None
    if session.dungeon:
        monster = session.dungeon["monsters"].get(target_id)
    else:
        monster = WORLD.monsters.get(target_id)
    if monster is None or not monster.alive:
        await send(session.ws, "ERROR", message="That target isn't there.")
        return
    reach = session.attack_reach()
    if chebyshev(session.x, session.y, monster.x, monster.y) > reach:
        await send(session.ws, "ERROR", message="You're too far away to attack.")
        return
    if session.using_bow():
        if not session.has_arrow_ammo():
            await send(session.ws, "ERROR", message="You need arrows equipped to shoot.")
            return
    session.in_combat_with = ("monster", monster.id)
    session.pet_target_id = monster.id  # pet only assists monsters you have attacked
    monster.target_player_id = session.player_id


COMBAT_STYLES = ("attack", "strength", "defence", "hitpoints", "archery")


async def handle_set_combat_style(session, msg):
    style = (msg.get("style") or "").lower().strip()
    if style not in COMBAT_STYLES:
        await send(session.ws, "ERROR", message="Choose Attack, Strength, Defence, Hitpoints, or Archery.")
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
    if chebyshev(session.x, session.y, monster.x, monster.y) > reach:
        return False, "Too far away."

    dmg = max(0, int(ab.get("damage") or 0))
    freeze = float(ab.get("freeze") or 0)
    effect = ab.get("effect") or "lightning"
    monster.hp = max(0, monster.hp - dmg)
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
    monster.alive = False
    if not getattr(monster, "no_respawn", False):
        monster.respawn_at_tick = WORLD.tick_count + MONSTERS[monster.type]["respawn_ticks"]
    monster.target_player_id = None
    if session.in_combat_with == ("monster", monster.id):
        session.in_combat_with = None
    if not session.dungeon:
        drops = WORLD.drop_loot(monster.x, monster.y, MONSTERS[monster.type]["drops"])
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
        await _grant_tidehollow_kill_loot(session)
        remaining = sum(1 for m in session.dungeon["monsters"].values() if m.alive)
        if remaining == 0:
            await _dungeon_on_clear(session)


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
                await send(session.ws, "ERROR", message=f"You need a {need} for this spot.")
            else:
                tool_name = {"woodcutting": "an axe", "mining": "a pickaxe", "fishing": "a fishing tool"}.get(skill)
                await send(session.ws, "ERROR", message=f"You need {tool_name} to do that.")
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
    fm_lvl = session.level("firemaking")
    if fm_lvl < info["level_req"]:
        await send(
            session.ws, "ERROR",
            message=f"You need Firemaking level {info['level_req']} to light {ITEMS[log_item_id]['name']}.",
        )
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
    before, after = WORLD.grant_xp(session, "firemaking", info["xp"])
    await send(
        session.ws, "SKILL_XP",
        player_id=session.player_id, skill="firemaking", gained=info["xp"],
        xp=session.xp["firemaking"], level=after, leveled_up=after > before,
    )
    await send(session.ws, "PLAYER_UPDATE", player=session.full_state())
    await send(
        session.ws, "CHAT_MSG",
        **{"from": "You", "text": f"You light the {ITEMS[log_item_id]['name'].lower()} and a fire springs up."},
    )


async def handle_talk(session, msg):
    npc_id = msg.get("npc_id")
    npc = NPC_BY_ID.get(npc_id)
    if npc is None:
        return
    if not adjacent_or_same(session.x, session.y, npc["x"], npc["y"]):
        await send(session.ws, "ERROR", message="You're too far away to talk to them.")
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

    await send(
        session.ws, "DIALOGUE", npc_id=npc_id, npc_name=npc["name"], lines=npc["lines"],
        shop_id=npc.get("shop_id"), quest=quest_info, forge=bool(npc.get("forge")),
        bank=bool(npc.get("bank")),
    )
    if session.quest_log_dirty:
        session.quest_log_dirty = False
        await send(
            session.ws, "QUEST_LOG",
            quests={qid: quest_status_for(session, qid) for qid in QUESTS},
        )
    if npc.get("shop_id"):
        await send_shop_state(session, npc["shop_id"])


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
            if not item_is_tradeable(item_id):
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
            await send(session.ws, "ERROR", message="Nothing tradeable to deposit.")
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
    if not item_is_tradeable(item_id):
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


async def send_shop_state(session, shop_id):
    shop = SHOPS[shop_id]
    stock = {iid: {"price": info["price"], "qty": info["qty"], "name": ITEMS[iid]["name"]} for iid, info in shop["stock"].items()}
    await send(
        session.ws, "SHOP_STATE",
        shop_id=shop_id, name=shop["name"], stock=stock,
        your_coins=session.coins, buys=bool(shop.get("buys")),
        buys_types=list(shop.get("buys_types") or []),
        buys_slots=list(shop.get("buys_slots") or []),
    )


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
        "from": "Pets",
        "text": f"You switch to your {PETS[pet_id]['name']}.",
    })


async def handle_shop_buy(session, msg):
    shop_id, item_id, qty = msg.get("shop_id"), msg.get("item_id"), max(1, int(msg.get("qty", 1)))
    shop = SHOPS.get(shop_id)
    if not shop or item_id not in shop["stock"]:
        return
    stock = shop["stock"][item_id]
    item = ITEMS.get(item_id) or {}
    # Pets: buy adds to collection and activates (re-buy of owned = free switch)
    if item.get("type") == "pet":
        qty = 1
        pet_id = item.get("pet_id")
        if pet_id not in PETS:
            return
        already = pet_id in session.owned_pets
        cost = 0 if already else stock["price"]
        # Expensive pets (above purse cap) can be paid from bank coins
        if not already:
            purse = int(session.coins)
            bank = int(session.bank_coins)
            if purse + bank < cost:
                await send(session.ws, "ERROR", message="You can't afford that (check purse + bank).")
                return
            take_purse = min(purse, cost)
            session.coins -= take_purse
            session.bank_coins -= (cost - take_purse)
        if not already and stock["qty"] < 99:
            stock["qty"] = max(0, stock["qty"] - 1)
        session.activate_pet(pet_id)
        WORLD.db.save_player_stats(
            session.player_id, coins=session.coins, bank_coins=session.bank_coins,
        )
        await send_shop_state(session, shop_id)
        await send(session.ws, "PLAYER_UPDATE", player=session.full_state())
        if already:
            msg_text = f"You call your {PETS[pet_id]['name']} to your side."
        else:
            msg_text = f"You adopt a {PETS[pet_id]['name']}! It will follow and fight for you."
        await send(session.ws, "CHAT_MSG", **{"from": "Pet Emporium", "text": msg_text})
        return
    qty = min(qty, stock["qty"])
    cost = stock["price"] * qty
    if qty <= 0 or session.coins < cost:
        await send(session.ws, "ERROR", message="You can't afford that.")
        return
    stock["qty"] -= qty
    session.coins -= cost
    if not WORLD.add_item_to_inventory(session, item_id, qty):
        session.coins += cost
        stock["qty"] += qty
        await send(session.ws, "ERROR", message="Your inventory is full.")
        return
    WORLD.db.save_player_stats(session.player_id, coins=session.coins)
    await send_shop_state(session, shop_id)
    await send(session.ws, "PLAYER_UPDATE", player=session.full_state())


async def handle_shop_sell(session, msg):
    shop_id, item_id, qty = msg.get("shop_id"), msg.get("item_id"), max(1, int(msg.get("qty", 1)))
    shop = SHOPS.get(shop_id)
    if not shop or not shop.get("buys"):
        return
    if not shop_will_buy(shop, item_id):
        await send(session.ws, "ERROR", message="This shop isn't interested in that.")
        return
    have = WORLD.count_item(session, item_id)
    qty = min(qty, have)
    if qty <= 0:
        return
    value = int(ITEMS[item_id]["value"] * 0.4) * qty
    WORLD.remove_item_qty(session, item_id, qty)
    gained, left = WORLD.add_coins(session, value)
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
    old = session.equipment.get(eq_slot)
    session.equipment[eq_slot] = entry["item_id"]
    WORLD.db.set_equipment(session.player_id, eq_slot, entry["item_id"])
    WORLD.remove_item_qty(session, entry["item_id"], 1)
    if old:
        WORLD.add_item_to_inventory(session, old, 1)
    if is_bow(entry["item_id"]):
        session.combat_style = "archery"
    elif session.combat_style == "archery":
        session.combat_style = "attack"
    await send(session.ws, "PLAYER_UPDATE", player=session.full_state())
    await send(
        session.ws, "CHAT_MSG",
        **{"from": "You", "text": f"You equip the {item['name']}."},
    )


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
    if not WORLD.add_item_to_inventory(session, item_id, 1):
        await send(session.ws, "ERROR", message="Your inventory is full.")
        return
    name = ITEMS.get(item_id, {}).get("name", "item")
    session.equipment[slot_name] = None
    WORLD.db.set_equipment(session.player_id, slot_name, None)
    if slot_name == "weapon" and session.combat_style == "archery":
        session.combat_style = "attack"
    await send(session.ws, "PLAYER_UPDATE", player=session.full_state())
    await send(session.ws, "CHAT_MSG", **{"from": "You", "text": f"You unequip the {name}."})


async def handle_use_item(session, msg):
    slot_index = msg.get("slot_index")
    entry = session.inventory.get(slot_index)
    if not entry:
        return
    item_id = entry["item_id"]
    item = ITEMS[item_id]
    action = (msg.get("action") or "use").lower()

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
                await send(session.ws, "ERROR", message="You need a Fletching Pouch first (Elena sells them).")
                return
            took = session.deposit_fletch_pouch(item_id, qty)
            await send(session.ws, "PLAYER_UPDATE", player=session.full_state())
            if took <= 0:
                cur = int(session.fletch_pouch.get(item_id) or 0)
                await send(session.ws, "ERROR", message=f"Fletching pouch is full of {item['name']} ({cur}/{RESOURCE_BAG_CAPACITY}).")
            else:
                left = int(session.fletch_pouch.get(item_id) or 0)
                await send(session.ws, "CHAT_MSG", **{
                    "from": "You",
                    "text": f"You pack {took} {item['name']} ({left}/{RESOURCE_BAG_CAPACITY}).",
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
        session.hp = min(session.max_hp(), session.hp + heal)
        WORLD.remove_item_qty(session, item_id, 1)
        WORLD.db.save_player_stats(session.player_id, hp=session.hp)
        await send(session.ws, "PLAYER_UPDATE", player=session.full_state())
        await send(
            session.ws, "CHAT_MSG",
            **{"from": "You", "text": f"You eat the {item['name']} and restore {heal} Hitpoints."},
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
        await send(session.ws, "ERROR", message="You can't drop that.")
        return
    WORLD.remove_item_qty(session, item_id, qty)
    WORLD.ground_items.setdefault((session.x, session.y), []).append({"item_id": item_id, "qty": qty})
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
    """Manual pickup: take one stack, or all=True for the whole pile."""
    await vacuum_ground_loot(session, quiet=True)
    take_all = bool(msg.get("all"))
    picked = 0
    while True:
        items_here = WORLD.ground_items.get((session.x, session.y))
        if not items_here:
            break
        entry = items_here.pop(0)
        item_id, qty = entry["item_id"], entry["qty"]
        if item_id == "coins":
            gained, left = WORLD.add_coins(session, qty)
            if left:
                items_here.insert(0, {"item_id": "coins", "qty": left})
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
            items_here.insert(0, entry)
            await send(session.ws, "ERROR", message=f"You can't carry more than {MAX_ORES} ores.")
            break
        elif not WORLD.add_item_to_inventory(session, item_id, qty):
            items_here.insert(0, entry)
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
    await send(session.ws, "QUEST_LOG", quests={qid: quest_status_for(session, qid) for qid in QUESTS})


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
    elif qdef["type"] in ("kill", "find_npc"):
        if prog["status"] != "ready":
            await send(session.ws, "ERROR", message="You haven't finished this quest yet.")
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
    """Apply coins / xp / single item / item list rewards from a quest def."""
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
            elif mtype == "ENTER_DUNGEON":
                await handle_enter_dungeon(session, msg)
            elif mtype == "LEAVE_DUNGEON":
                await handle_leave_dungeon(session, msg)
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
            elif mtype == "SHOP_BUY":
                await handle_shop_buy(session, msg)
            elif mtype == "SHOP_SELL":
                await handle_shop_sell(session, msg)
            elif mtype == "SET_PET":
                await handle_set_pet(session, msg)
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
            elif mtype == "LOGOUT":
                break
    except websockets.exceptions.ConnectionClosed:
        pass
    finally:
        if session:
            if session.dungeon:
                session.dungeon = None
            WORLD.db.save_player_position(session.player_id, session.x, session.y)
            WORLD.db.save_player_stats(session.player_id, hp=session.hp)
            del WORLD.sessions[session.player_id]
            log.info("%s disconnected", session.char_name)


# ---------------------------------------------------------------------------
# Game tick loop: combat resolution, gathering, monster AI, respawns
# ---------------------------------------------------------------------------
async def game_loop():
    while True:
        await asyncio.sleep(TICK_SECONDS)
        WORLD.tick_count += 1
        events = []

        await process_combat(events)
        await process_gathering(events)
        process_monster_respawns()
        process_resource_respawns()
        process_fires()
        process_monster_ai()
        process_dungeon_ai()
        process_pets(events)
        await process_stat_boosts()
        await process_equip_regen()
        await flush_quest_logs()

        # Pet clears / loot of dungeon floors
        for ev in list(events):
            if ev["type"] == "_DUNGEON_LOOT":
                events.remove(ev)
                pid = ev["data"].get("_dungeon_player")
                s = WORLD.sessions.get(pid)
                if s and s.dungeon:
                    await _grant_tidehollow_kill_loot(s)
            elif ev["type"] == "_DUNGEON_CLEAR":
                events.remove(ev)
                pid = ev["data"].get("_dungeon_player")
                s = WORLD.sessions.get(pid)
                if s and s.dungeon:
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
                alive = [m.public_state() for m in d["monsters"].values() if m.alive]
                await send(session.ws, "STATE_UPDATE", **{
                    "players": [session.public_state()],
                    "monsters": alive,
                    "pets": [session.pet_public()] if session.pet_id else [],
                    "ground_items": {},
                    "resources": {},
                    "fires": [],
                    "dungeon": {
                        "floor": d["floor"],
                        "floors": d["floors"],
                        "remaining": len(alive),
                        "label": d["label"],
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
    MAX_ATTACKERS = 2
    for session in list(WORLD.sessions.values()):
        if session.dungeon:
            pool = [m for m in session.dungeon["monsters"].values() if m.alive]
            dungeon_tag = session.player_id
        else:
            pool = list(WORLD.monsters.values())
            dungeon_tag = None

        attackers = [
            m for m in pool
            if m.alive and m.target_player_id == session.player_id
            and adjacent_or_same(session.x, session.y, m.x, m.y)
        ]
        attackers = attackers[:MAX_ATTACKERS]

        primary = None
        if session.in_combat_with and session.in_combat_with[0] == "monster":
            mid = session.in_combat_with[1]
            primary = next((m for m in pool if m.id == mid), None)
            reach = session.attack_reach()
            if primary and (not primary.alive or chebyshev(session.x, session.y, primary.x, primary.y) > reach):
                primary = None
        if primary is None and attackers:
            primary = attackers[0]
            session.in_combat_with = ("monster", primary.id)

        if primary and chebyshev(session.x, session.y, primary.x, primary.y) <= session.attack_reach():
            ranged = bool(session.using_bow())
            if ranged:
                if not session.consume_one_arrow():
                    await send(
                        session.ws, "CHAT_MSG",
                        **{"from": "You", "text": "You have run out of arrows."},
                    )
                    session.in_combat_with = None
                    await send(session.ws, "PLAYER_UPDATE", player=session.full_state())
                    continue
                await send(session.ws, "PLAYER_UPDATE", player=session.full_state())
            mdef = primary.def_stats()
            dmg, hit = combat.resolve_hit(session.combat_stats(), {
                "attack": 1, "strength": 1, "defence": mdef["defence"],
                "defence_bonus": mdef.get("def_bonus", 0),
            })
            crit = False
            if hit and dmg > 0:
                # Jewelry: flat void strike, then crit chance
                flat = int(session.jewelry_ability_total("void_strike"))
                if flat:
                    dmg += flat
                crit_chance = session.jewelry_ability_total("crit")
                if crit_chance > 0 and random.random() < min(0.45, crit_chance):
                    dmg = max(1, int(round(dmg * session.jewelry_crit_mult())))
                    crit = True
            primary.hp = max(0, primary.hp - dmg)
            # Jewelry lifesteal on successful damage
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
            session.pet_target_id = primary.id  # pet assists only after you swing
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
            if dungeon_tag:
                ev["_dungeon_player"] = dungeon_tag
            events.append({"type": "COMBAT_EVENT", "data": ev})
            # Bow combat always trains Archery (no melee style switching while ranged).
            if ranged:
                style = "archery"
                session.combat_style = "archery"
            else:
                style = session.combat_style if session.combat_style in COMBAT_STYLES else "attack"
                if style == "archery":
                    style = "attack"
                    session.combat_style = "attack"
            amount = dmg * 2
            if amount > 0:
                before, after = WORLD.grant_xp(session, style, amount)
                xp_ev = {
                    "player_id": session.player_id, "skill": style, "gained": amount,
                    "xp": session.xp[style], "level": after, "leveled_up": after > before,
                }
                if dungeon_tag:
                    xp_ev["_dungeon_player"] = dungeon_tag
                events.append({"type": "SKILL_XP", "data": xp_ev})

            # Auto quest-magic after a swing
            try_auto_magic(session, primary, events, dungeon_tag=dungeon_tag)

            if primary.hp <= 0:
                primary.alive = False
                if not getattr(primary, "no_respawn", False):
                    primary.respawn_at_tick = WORLD.tick_count + MONSTERS[primary.type]["respawn_ticks"]
                primary.target_player_id = None
                if session.in_combat_with == ("monster", primary.id):
                    session.in_combat_with = None
                if not session.dungeon:
                    drops = WORLD.drop_loot(primary.x, primary.y, MONSTERS[primary.type]["drops"])
                    events.append({"type": "DEATH", "data": {"entity_id": primary.id, "entity_kind": "monster"}})
                    if drops:
                        events.append({"type": "LOOT_DROPPED", "data": {"x": primary.x, "y": primary.y, "items": drops}})
                        await vacuum_ground_loot(session)
                        await send(session.ws, "PLAYER_UPDATE", player=session.full_state())
                    check_quest_progress_on_kill(session, primary.type)
                else:
                    death_ev = {"entity_id": primary.id, "entity_kind": "monster", "_dungeon_player": dungeon_tag}
                    events.append({"type": "DEATH", "data": death_ev})
                    await _grant_tidehollow_kill_loot(session)
                    # XP bonus from scaled dungeon beast
                    bonus_xp = int(mdef.get("xp", 20))
                    if bonus_xp > 0:
                        before, after = WORLD.grant_xp(session, style, bonus_xp)
                        events.append({"type": "SKILL_XP", "data": {
                            "player_id": session.player_id, "skill": style, "gained": bonus_xp,
                            "xp": session.xp[style], "level": after, "leveled_up": after > before,
                            "_dungeon_player": dungeon_tag,
                        }})
                    remaining = sum(1 for m in session.dungeon["monsters"].values() if m.alive)
                    if remaining == 0:
                        await _dungeon_on_clear(session)
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
                        monster.alive = False
                        if not getattr(monster, "no_respawn", False):
                            monster.respawn_at_tick = WORLD.tick_count + MONSTERS[monster.type]["respawn_ticks"]
                        monster.target_player_id = None
                        if session.in_combat_with == ("monster", monster.id):
                            session.in_combat_with = None
                        if not session.dungeon:
                            drops = WORLD.drop_loot(monster.x, monster.y, MONSTERS[monster.type]["drops"])
                            events.append({"type": "DEATH", "data": {"entity_id": monster.id, "entity_kind": "monster"}})
                            if drops:
                                events.append({"type": "LOOT_DROPPED", "data": {"x": monster.x, "y": monster.y, "items": drops}})
                            check_quest_progress_on_kill(session, monster.type)
                        else:
                            events.append({"type": "DEATH", "data": {
                                "entity_id": monster.id, "entity_kind": "monster",
                                "_dungeon_player": dungeon_tag,
                            }})
            hit_ev = {
                "attacker_id": monster.id, "defender_id": session.player_id, "damage": dmg2,
                "hit": hit2, "defender_hp": session.hp, "defender_max_hp": session.max_hp(),
                "kind": "monster_hits_player",
            }
            if dodged:
                hit_ev["dodged"] = True
            if thorns_dmg:
                hit_ev["thorns"] = thorns_dmg
                hit_ev["thorns_target"] = monster.id
            if dungeon_tag:
                hit_ev["_dungeon_player"] = dungeon_tag
            events.append({"type": "COMBAT_EVENT", "data": hit_ev})
            before_hp, after_hp = WORLD.grant_xp(session, "hitpoints", 1)
            hp_ev = {
                "player_id": session.player_id, "skill": "hitpoints", "gained": 1,
                "xp": session.xp["hitpoints"], "level": after_hp, "leveled_up": after_hp > before_hp,
            }
            if dungeon_tag:
                hp_ev["_dungeon_player"] = dungeon_tag
            events.append({"type": "SKILL_XP", "data": hp_ev})
            if session.hp <= 0:
                died = True
                break

        if died:
            lost = session.coins
            session.hp = session.max_hp()
            session.coins = 0
            session.in_combat_with = None
            session.pet_target_id = None
            if session.dungeon:
                await handle_leave_dungeon(session, silent=True)
                await send(
                    session.ws, "CHAT_MSG",
                    **{"from": "Tidehollow", "text": "You fall in the cave and wake outside — the depths reclaim their silence."},
                )
            else:
                session.x, session.y = SPAWN_POINT
                if session.pet_id:
                    session.pet_x, session.pet_y = SPAWN_POINT
                    session.pet_hp = PETS[session.pet_id]["hp"]
                for mon in WORLD.monsters.values():
                    if mon.target_player_id == session.player_id:
                        mon.target_player_id = None
            WORLD.db.save_player_stats(session.player_id, coins=session.coins)
            WORLD.db.save_player_position(session.player_id, session.x, session.y)
            death_data = {
                "entity_id": session.player_id, "entity_kind": "player",
                "coins_lost": lost,
            }
            if dungeon_tag:
                death_data["_dungeon_player"] = dungeon_tag
            events.append({"type": "DEATH", "data": death_data})
            await send(session.ws, "PLAYER_UPDATE", player=session.full_state())
        elif not session.in_combat_with and not attackers:
            pass


def _pet_step_toward(session, tx, ty):
    """Move pet one tile toward (tx, ty) if walkable."""
    px, py = session.pet_x, session.pet_y
    if (px, py) == (tx, ty):
        return
    options = []
    dx = 0 if px == tx else (1 if tx > px else -1)
    dy = 0 if py == ty else (1 if ty > py else -1)
    if session.dungeon:
        mod = _dungeon_mod(session)
        walk = lambda nx, ny, _mod=mod: _mod.dungeon_walkable(session.dungeon["tiles"], nx, ny)
    else:
        walk = lambda nx, ny: is_walkable(WORLD.grid, nx, ny)
    for nx, ny in ((px + dx, py), (px, py + dy), (px + dx, py + dy)):
        if walk(nx, ny):
            options.append((nx, ny))
    if not options:
        return
    options.sort(key=lambda p: max(abs(p[0] - tx), abs(p[1] - ty)))
    session.pet_x, session.pet_y = options[0]


def process_pets(events):
    """Pets follow their owner and only attack monsters the player has attacked."""
    for session in list(WORLD.sessions.values()):
        if not session.pet_id or session.pet_id not in PETS:
            continue
        pdef = PETS[session.pet_id]
        if session.pet_hp <= 0:
            session.pet_hp = pdef["hp"]

        if max(abs(session.pet_x - session.x), abs(session.pet_y - session.y)) > 10:
            session.pet_x, session.pet_y = session.x, session.y

        dungeon_tag = session.player_id if session.dungeon else None

        # Only engage a monster the player has attacked (pet_target_id set on attack)
        target = None
        if session.pet_target_id:
            if session.dungeon:
                m = session.dungeon["monsters"].get(session.pet_target_id)
            else:
                m = WORLD.monsters.get(session.pet_target_id)
            if m and m.alive:
                target = m
            else:
                session.pet_target_id = None

        if target is not None:
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
                    target.alive = False
                    target.target_player_id = None
                    if not getattr(target, "no_respawn", False):
                        base = MONSTERS.get(target.type, {})
                        target.respawn_at_tick = WORLD.tick_count + base.get("respawn_ticks", 20)
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
                            "data": {"_dungeon_player": session.player_id},
                        })
                        remaining = sum(1 for m in session.dungeon["monsters"].values() if m.alive)
                        if remaining == 0:
                            events.append({
                                "type": "_DUNGEON_CLEAR",
                                "data": {"_dungeon_player": session.player_id},
                            })
                    else:
                        drops = WORLD.drop_loot(target.x, target.y, MONSTERS[target.type]["drops"])
                        if drops:
                            events.append({"type": "LOOT_DROPPED", "data": {
                                "x": target.x, "y": target.y, "items": drops,
                            }})
                        check_quest_progress_on_kill(session, target.type)
            else:
                _pet_step_toward(session, target.x, target.y)
            continue

        if max(abs(session.pet_x - session.x), abs(session.pet_y - session.y)) > 1:
            _pet_step_toward(session, session.x, session.y)


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


def process_monster_respawns():
    for m in WORLD.monsters.values():
        if not m.alive and WORLD.tick_count >= m.respawn_at_tick:
            m.hp = m.max_hp
            m.x, m.y = m.spawn_x, m.spawn_y
            m.alive = True


def process_resource_respawns():
    for pos, node in WORLD.resource_nodes.items():
        if node["depleted"] and WORLD.tick_count >= node["respawn_at"]:
            node["depleted"] = False


def process_dungeon_ai():
    """Chase the instance owner inside Tidehollow floors."""
    for session in list(WORLD.sessions.values()):
        if not session.dungeon:
            continue
        tiles = session.dungeon["tiles"]
        for m in session.dungeon["monsters"].values():
            if not m.alive:
                continue
            m.target_player_id = session.player_id
            dist = max(abs(session.x - m.x), abs(session.y - m.y))
            if not session.in_combat_with:
                session.in_combat_with = ("monster", m.id)
            if dist <= 1:
                continue
            dx = 0 if session.x == m.x else (1 if session.x > m.x else -1)
            dy = 0 if session.y == m.y else (1 if session.y > m.y else -1)
            if abs(session.x - m.x) >= abs(session.y - m.y):
                steps = [(dx, 0), (0, dy), (dx, dy)]
            else:
                steps = [(0, dy), (dx, 0), (dx, dy)]
            for sx, sy in steps:
                if sx == 0 and sy == 0:
                    continue
                nx, ny = m.x + sx, m.y + sy
                if _dungeon_mod(session).dungeon_walkable(tiles, nx, ny) and (nx, ny) != (session.x, session.y):
                    # Don't stack on other living beasts
                    blocked = any(
                        o.alive and o.id != m.id and o.x == nx and o.y == ny
                        for o in session.dungeon["monsters"].values()
                    )
                    if not blocked:
                        m.x, m.y = nx, ny
                        break


def process_monster_ai():
    """Wander, aggro (skeletons/goblins), chase, and force the player to fight back.

    At most MAX_ATTACKERS monsters may target the same player at once.
    """
    MAX_ATTACKERS = 2

    def attackers_on(player_id):
        return sum(
            1 for mon in WORLD.monsters.values()
            if mon.alive and mon.target_player_id == player_id
        )

    for m in WORLD.monsters.values():
        if not m.alive:
            continue
        mdef = MONSTERS[m.type]
        aggro = mdef.get("aggro_range", 0)

        # Drop stale targets
        if m.target_player_id and m.target_player_id not in WORLD.sessions:
            m.target_player_id = None

        # Acquire aggro (respect simultaneous attacker cap)
        if aggro and not m.target_player_id:
            best = None
            best_d = None
            for s in WORLD.sessions.values():
                if getattr(s, "dungeon", None):
                    continue
                if attackers_on(s.player_id) >= MAX_ATTACKERS:
                    continue
                d = max(abs(s.x - m.x), abs(s.y - m.y))
                if d <= aggro and (best_d is None or d < best_d):
                    best, best_d = s, d
            if best:
                m.target_player_id = best.player_id
                # Only lock combat if the player isn't already fighting someone else
                if not best.in_combat_with:
                    best.in_combat_with = ("monster", m.id)

        if m.target_player_id:
            session = WORLD.sessions.get(m.target_player_id)
            if not session or getattr(session, "dungeon", None):
                m.target_player_id = None
                continue
            dist = max(abs(session.x - m.x), abs(session.y - m.y))
            # Lose interest if the player flees far enough
            if dist > max(aggro * 2, 10):
                if session.in_combat_with == ("monster", m.id):
                    session.in_combat_with = None
                m.target_player_id = None
                continue
            # Keep the player locked into fighting back against one of their attackers
            if not session.in_combat_with or session.in_combat_with[0] != "monster":
                session.in_combat_with = ("monster", m.id)
            elif session.in_combat_with[1] not in WORLD.monsters or not WORLD.monsters[session.in_combat_with[1]].alive:
                session.in_combat_with = ("monster", m.id)
            # Chase one step toward the player when not adjacent (stay in home room)
            if dist > 1:
                dx = 0 if session.x == m.x else (1 if session.x > m.x else -1)
                dy = 0 if session.y == m.y else (1 if session.y > m.y else -1)
                # Prefer axis with larger delta
                if abs(session.x - m.x) >= abs(session.y - m.y):
                    steps = [(dx, 0), (0, dy), (dx, dy)]
                else:
                    steps = [(0, dy), (dx, 0), (dx, dy)]
                for sx, sy in steps:
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


async def main():
    log.info("Starting MMORPG server on ws://%s:%s", HOST, PORT)
    async with websockets.serve(handler, HOST, PORT, ping_interval=20, ping_timeout=20):
        await game_loop()


if __name__ == "__main__":
    asyncio.run(main())
