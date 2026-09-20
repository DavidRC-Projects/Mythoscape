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

from database import Database, INVENTORY_SIZE
from content import (
    ITEMS, MONSTERS, MONSTER_SPAWNS, NPCS, SHOPS, QUESTS, XP_SKILLS, RESOURCE_YIELDS,
    CRAFT_RECIPES, INTERACTABLES, BUILDINGS, PETS,
    MAX_PURSE_COINS, MAX_BANK_COINS, MAX_ORES, ORE_ITEM_IDS, BANK_SLOTS,
    karma_total_bonus, FIRE_LOGS, cook_burn_chance,
)
from world_map import (
    generate_world, build_resource_nodes, is_walkable, WIDTH, HEIGHT, SPAWN_POINT, get_zone,
    room_containing, in_room,
)
import combat

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("server")

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
        self.xp = {
            "attack": row["attack_xp"], "strength": row["strength_xp"], "defence": row["defence_xp"],
            "hitpoints": row["hitpoints_xp"], "woodcutting": row["woodcutting_xp"],
            "mining": row["mining_xp"], "fishing": row["fishing_xp"],
            "cooking": row["cooking_xp"] if "cooking_xp" in row.keys() else 0,
            "firemaking": row["firemaking_xp"] if "firemaking_xp" in row.keys() else 0,
            "smithing": row["smithing_xp"] if "smithing_xp" in row.keys() else 0,
            "karma": row["karma_xp"] if "karma_xp" in row.keys() else 0,
        }
        self.coins = min(int(row["coins"]), MAX_PURSE_COINS)
        self.bank_coins = int(row["bank_coins"]) if "bank_coins" in row.keys() else 0
        self.bank = {}  # slot -> {item_id, qty}
        self.equipment = {
            "weapon": row["equip_weapon"], "shield": row["equip_shield"],
            "body": row["equip_body"], "legs": row["equip_legs"],
            "helmet": row["equip_helmet"] if "equip_helmet" in row.keys() else None,
        }
        self.inventory = {}  # slot -> {"item_id":, "qty":}
        self.quests = {}     # quest_id -> {"status":, "progress":}
        self.in_combat_with = None   # ("monster", instance_id) or ("player", player_id)
        self.combat_style = "attack"  # attack | strength | defence | hitpoints
        self.gathering_node = None   # (x, y) currently gathering
        self.trade_partner_id = None
        self.trade_offer = {}        # slot -> qty
        self.trade_confirmed = False
        self.last_move_tick = 0
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

    def level(self, skill):
        return combat.level_from_xp(self.xp[skill])

    def max_hp(self):
        return self.level("hitpoints")

    def combat_stats(self, attack_bonus=0, strength_bonus=0, defence_bonus=0):
        wb = self.weapon_bonuses()
        return {
            "attack": self.level("attack"), "strength": self.level("strength"), "defence": self.level("defence"),
            "attack_bonus": wb["att_bonus"], "strength_bonus": wb["str_bonus"], "defence_bonus": wb["def_bonus"],
        }

    def weapon_bonuses(self):
        total = {"att_bonus": 0, "str_bonus": 0, "def_bonus": 0}
        for slot_name, item_id in self.equipment.items():
            if not item_id:
                continue
            item = ITEMS.get(item_id, {})
            total["att_bonus"] += item.get("att_bonus", 0)
            total["str_bonus"] += item.get("str_bonus", 0)
            total["def_bonus"] += item.get("def_bonus", 0)
        karma = self.level("karma") if "karma" in self.xp else 1
        for k, v in karma_total_bonus(karma, self.equipment).items():
            total[k] += v
        return total

    def public_state(self):
        return {
            "id": self.player_id, "name": self.char_name, "x": self.x, "y": self.y,
            "hp": self.hp, "max_hp": self.max_hp(),
            "combat_level": self.combat_level(),
            "equipment": self.equipment,  # client uses this for sprite weapons/armor
        }

    def total_level(self):
        return sum(self.level(s) for s in XP_SKILLS)

    def combat_level(self):
        return combat.combat_level(
            self.level("attack"), self.level("strength"),
            self.level("defence"), self.level("hitpoints"),
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
            "karma_bonuses": karma_total_bonus(karma_lvl, self.equipment),
            "pet_id": self.pet_id,
            "pet": self.pet_public() if self.pet_id else None,
            "owned_pets": self.owned_pets_public(),
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
    def __init__(self, inst_id, mtype, x, y):
        self.id = inst_id
        self.type = mtype
        self.spawn_x = x
        self.spawn_y = y
        self.x = x
        self.y = y
        data = MONSTERS[mtype]
        self.max_hp = data["hp"]
        self.hp = data["hp"]
        self.alive = True
        self.respawn_at_tick = 0
        self.target_player_id = None
        self.ticks_since_wander = 0
        # Dungeon monsters are confined to the room they spawned in
        self.home_room = room_containing(x, y)

    def public_state(self):
        mdef = MONSTERS[self.type]
        return {
            "id": self.id, "type": self.type, "name": mdef["name"],
            "level": mdef["level"],
            "x": self.x, "y": self.y, "hp": self.hp, "max_hp": self.max_hp, "alive": self.alive,
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
            if s.x == x and s.y == y and s.player_id != exclude_player:
                return True
        return False

    def add_item_to_inventory(self, session, item_id, qty):
        """Returns True if it fit, False if inventory is full."""
        item_def = ITEMS[item_id]
        if item_def.get("stackable"):
            for slot, entry in session.inventory.items():
                if entry["item_id"] == item_id:
                    entry["qty"] += qty
                    self.db.add_item_to_slot(session.player_id, slot, item_id, entry["qty"])
                    return True
        for slot in range(INVENTORY_SIZE):
            if slot not in session.inventory:
                session.inventory[slot] = {"item_id": item_id, "qty": qty}
                self.db.add_item_to_slot(session.player_id, slot, item_id, qty)
                return True
        return False

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

    def count_item_bank(self, session, item_id):
        return sum(e["qty"] for e in session.bank.values() if e["item_id"] == item_id)

    def ensure_tinderbox(self, session):
        """Existing characters predating firemaking get a free tinderbox once."""
        if self.count_item(session, "tinderbox") > 0 or self.count_item_bank(session, "tinderbox") > 0:
            return False
        return self.add_item_to_inventory(session, "tinderbox", 1)

    def count_ores(self, session):
        return sum(
            e["qty"] for e in session.inventory.values() if e["item_id"] in ORE_ITEM_IDS
        )

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


def check_quest_progress_on_kill(session, monster_type):
    for qid, qdef in QUESTS.items():
        if qdef["type"] != "kill" or qdef["target"] != monster_type:
            continue
        prog = session.quests.get(qid)
        if prog and prog["status"] == "active":
            prog["progress"] += 1
            if prog["progress"] >= qdef["count"]:
                prog["status"] = "ready"
            WORLD.db.set_quest_progress(session.player_id, qid, prog["status"], prog["progress"])


def check_quest_progress_on_talk(session, npc_id):
    for qid, qdef in QUESTS.items():
        if qdef["type"] != "find_npc" or qdef["target"] != npc_id:
            continue
        prog = session.quests.get(qid)
        if prog and prog["status"] == "active":
            prog["status"] = "ready"
            WORLD.db.set_quest_progress(session.player_id, qid, prog["status"], prog["progress"])


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
        if WORLD.db.get_player_by_username(username):
            await send(ws, "LOGIN_FAIL", reason="That username is already taken.")
            return
        row = WORLD.db.create_account(username, password, char_name)
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
    # Persist owned-pets list (includes migrated active_pet)
    WORLD.db.save_player_stats(session.player_id, owned_pets=json.dumps(session.owned_pets))
    if WORLD.ensure_tinderbox(session):
        log.info("%s received a starter tinderbox", session.char_name)

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
            if eq_slot and not session.equipment.get(eq_slot):
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
    if not is_walkable(WORLD.grid, nx, ny):
        return
    if WORLD.occupied(nx, ny, exclude_player=session.player_id):
        return
    session.x, session.y = nx, ny
    session.gathering_node = None
    WORLD.db.save_player_position(session.player_id, nx, ny)
    await vacuum_ground_loot(session)
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


def adjacent_or_same(ax, ay, bx, by):
    return max(abs(ax - bx), abs(ay - by)) <= 1


async def handle_attack(session, msg):
    target_id = msg.get("target_id")
    monster = WORLD.monsters.get(target_id)
    if monster is None or not monster.alive:
        await send(session.ws, "ERROR", message="That target isn't there.")
        return
    if not adjacent_or_same(session.x, session.y, monster.x, monster.y):
        await send(session.ws, "ERROR", message="You're too far away to attack.")
        return
    session.in_combat_with = ("monster", monster.id)
    monster.target_player_id = session.player_id


COMBAT_STYLES = ("attack", "strength", "defence", "hitpoints")


async def handle_set_combat_style(session, msg):
    style = (msg.get("style") or "").lower().strip()
    if style not in COMBAT_STYLES:
        await send(session.ws, "ERROR", message="Choose Attack, Strength, Defence, or Hitpoints.")
        return
    session.combat_style = style
    await send(session.ws, "PLAYER_UPDATE", player=session.full_state())
    await send(
        session.ws, "CHAT_MSG",
        **{"from": "Combat", "text": f"Fighting style: {style.title()} — XP goes to {style.title()}."},
    )


async def handle_gather(session, msg):
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
    session.gathering_node = (x, y)


async def handle_craft(session, msg):
    recipe_id = msg.get("recipe_id")
    recipe = CRAFT_RECIPES.get(recipe_id)
    if not recipe:
        await send(session.ws, "ERROR", message="Unknown recipe.")
        return
    category = recipe.get("category")
    # Smelt at furnace, smith at anvil, cook at a hearth/range or campfire.
    if category == "smelt":
        needed_kinds = ("furnace",)
        where = "the furnace"
    elif category == "smith":
        needed_kinds = ("anvil",)
        where = "the anvil"
    elif category == "cook":
        needed_kinds = ("range", "fireplace")
        where = "a cooking fire"
    else:
        await send(session.ws, "ERROR", message="You can't make that here.")
        return
    near_station = False
    if category == "cook":
        near_station = WORLD.near_cook_spot(session)
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
    for item_id, need in recipe["inputs"].items():
        if WORLD.count_item(session, item_id) < need:
            await send(
                session.ws, "ERROR",
                message=f"You need {need}x {ITEMS[item_id]['name']}.",
            )
            return
    out_id, out_qty = recipe["output"]
    burnt = False
    if category == "cook" and recipe.get("burnt"):
        chance = cook_burn_chance(cook_lvl, recipe["level_req"])
        if chance > 0 and random.random() < chance:
            out_id, out_qty = recipe["burnt"]
            burnt = True
    # Reserve output space: try add after remove; roll back on failure.
    for item_id, need in recipe["inputs"].items():
        WORLD.remove_item_qty(session, item_id, need)
    if not WORLD.add_item_to_inventory(session, out_id, out_qty):
        for item_id, need in recipe["inputs"].items():
            WORLD.add_item_to_inventory(session, item_id, need)
        await send(session.ws, "ERROR", message="Your inventory is full.")
        return
    if category == "cook" and burnt:
        await send(session.ws, "PLAYER_UPDATE", player=session.full_state())
        await send(
            session.ws, "CHAT_MSG",
            **{"from": "Kitchen", "text": f"You accidentally burn the food. You get {ITEMS[out_id]['name']}."},
        )
        return
    before, after = WORLD.grant_xp(session, skill, recipe["xp"])
    await send(
        session.ws, "SKILL_XP",
        player_id=session.player_id, skill=skill, gained=recipe["xp"],
        xp=session.xp[skill], level=after, leveled_up=after > before,
    )
    await send(session.ws, "PLAYER_UPDATE", player=session.full_state())
    source = "Kitchen" if category == "cook" else "Forge"
    verb = "cook" if category == "cook" else "make"
    await send(
        session.ws, "CHAT_MSG",
        **{"from": source, "text": f"You {verb} {ITEMS[out_id]['name']}."},
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
    if WORLD.count_item(session, log_item_id) < 1:
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
    WORLD.remove_item_qty(session, log_item_id, 1)
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

    quest_id = npc.get("quest_id")
    quest_info = None
    if quest_id:
        prog = session.quests.get(quest_id)
        qdef = QUESTS[quest_id]
        if prog is None:
            quest_info = {"quest_id": quest_id, "name": qdef["name"], "description": qdef["description"], "state": "offerable"}
        elif prog["status"] == "active":
            quest_info = {"quest_id": quest_id, "name": qdef["name"], "description": qdef["description"], "state": "active"}
        elif prog["status"] == "ready":
            quest_info = {"quest_id": quest_id, "name": qdef["name"], "description": qdef["description"], "state": "ready"}
        else:
            quest_info = {"quest_id": quest_id, "name": qdef["name"], "description": qdef["description"], "state": "complete"}

    await send(
        session.ws, "DIALOGUE", npc_id=npc_id, npc_name=npc["name"], lines=npc["lines"],
        shop_id=npc.get("shop_id"), quest=quest_info, forge=bool(npc.get("forge")),
        bank=bool(npc.get("bank")),
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
        if session.coins < cost:
            await send(session.ws, "ERROR", message="You can't afford that.")
            return
        session.coins -= cost
        if not already and stock["qty"] < 99:
            stock["qty"] = max(0, stock["qty"] - 1)
        session.activate_pet(pet_id)
        WORLD.db.save_player_stats(session.player_id, coins=session.coins)
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
    if not item_is_sellable(item_id):
        await send(session.ws, "ERROR", message="You can't sell that.")
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
    old = session.equipment.get(eq_slot)
    session.equipment[eq_slot] = entry["item_id"]
    WORLD.db.set_equipment(session.player_id, eq_slot, entry["item_id"])
    WORLD.remove_item_qty(session, entry["item_id"], 1)
    if old:
        WORLD.add_item_to_inventory(session, old, 1)
    await send(session.ws, "PLAYER_UPDATE", player=session.full_state())


async def handle_unequip(session, msg):
    slot_name = msg.get("equip_slot")
    item_id = session.equipment.get(slot_name)
    if not item_id:
        return
    if not WORLD.add_item_to_inventory(session, item_id, 1):
        await send(session.ws, "ERROR", message="Your inventory is full.")
        return
    session.equipment[slot_name] = None
    WORLD.db.set_equipment(session.player_id, slot_name, None)
    await send(session.ws, "PLAYER_UPDATE", player=session.full_state())


async def handle_use_item(session, msg):
    slot_index = msg.get("slot_index")
    entry = session.inventory.get(slot_index)
    if not entry:
        return
    item_id = entry["item_id"]
    item = ITEMS[item_id]
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
        # Use tinderbox: light the first stack of logs found in inventory
        for slot, inv in session.inventory.items():
            if inv["item_id"] in FIRE_LOGS:
                await light_fire(session, inv["item_id"])
                return
        await send(session.ws, "ERROR", message="You need logs to light a fire.")
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
    else:
        await send(session.ws, "ERROR", message="Nothing happens.")


async def handle_drop(session, msg):
    slot_index, qty = msg.get("slot_index"), max(1, int(msg.get("qty", 1)))
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
    await send(session.ws, "PLAYER_UPDATE", player=session.full_state())


async def handle_pickup(session, msg):
    """Manual pickup: take the next non-coin stack (coins auto-vacuum on step)."""
    await vacuum_ground_loot(session, quiet=True)
    items_here = WORLD.ground_items.get((session.x, session.y))
    if not items_here:
        await send(session.ws, "PLAYER_UPDATE", player=session.full_state())
        return
    entry = items_here.pop(0)
    item_id, qty = entry["item_id"], entry["qty"]
    if item_id == "coins":
        gained, left = WORLD.add_coins(session, qty)
        if left:
            items_here.insert(0, {"item_id": "coins", "qty": left})
        await send(session.ws, "CHAT_MSG", **{"from": "World", "text": f"You pick up {gained} coins."})
    elif ITEMS.get(item_id, {}).get("karma_xp"):
        await bury_bone_stack(session, item_id, qty, quiet=False)
    elif item_id in ORE_ITEM_IDS and WORLD.count_ores(session) + qty > MAX_ORES:
        items_here.insert(0, entry)
        await send(session.ws, "ERROR", message=f"You can't carry more than {MAX_ORES} ores.")
        await send(session.ws, "PLAYER_UPDATE", player=session.full_state())
        return
    elif not WORLD.add_item_to_inventory(session, item_id, qty):
        items_here.insert(0, entry)
        await send(session.ws, "ERROR", message="Your inventory is full.")
        await send(session.ws, "PLAYER_UPDATE", player=session.full_state())
        return
    else:
        await send(session.ws, "CHAT_MSG", **{
            "from": "World", "text": f"You pick up {ITEMS[item_id]['name']}.",
        })
    if not items_here:
        del WORLD.ground_items[(session.x, session.y)]
    await send(session.ws, "PLAYER_UPDATE", player=session.full_state())


async def handle_quest_accept(session, msg):
    quest_id = msg.get("quest_id")
    if quest_id not in QUESTS or quest_id in session.quests:
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

    if qdef["type"] == "collect":
        have = WORLD.count_item(session, qdef["target"])
        if have < qdef["count"]:
            await send(session.ws, "ERROR", message=f"You need {qdef['count']}x {ITEMS[qdef['target']]['name']}.")
            return
        WORLD.remove_item_qty(session, qdef["target"], qdef["count"])
    elif qdef["type"] == "collect_multi":
        for iid, need in qdef["targets"].items():
            if WORLD.count_item(session, iid) < need:
                await send(session.ws, "ERROR", message=f"You need {need}x {ITEMS[iid]['name']}.")
                return
        for iid, need in qdef["targets"].items():
            WORLD.remove_item_qty(session, iid, need)
    elif qdef["type"] in ("kill", "find_npc"):
        if prog["status"] != "ready":
            await send(session.ws, "ERROR", message="You haven't finished this quest yet.")
            return

    rewards = qdef["rewards"]
    if "coins" in rewards:
        gained, left = WORLD.add_coins(session, rewards["coins"])
        if left:
            await send(session.ws, "CHAT_MSG", **{
                "from": "World", "text": f"Purse full — {left} reward coins couldn't fit.",
            })
    if "xp" in rewards:
        for skill, amount in rewards["xp"].items():
            WORLD.grant_xp(session, skill, amount)
    if "item" in rewards:
        iid, qty = rewards["item"]
        WORLD.add_item_to_inventory(session, iid, qty)

    prog["status"] = "complete"
    WORLD.db.set_quest_progress(session.player_id, quest_id, "complete", prog.get("progress", 0))
    await send(session.ws, "QUEST_COMPLETE", quest_id=quest_id, rewards=rewards)
    await send(session.ws, "PLAYER_UPDATE", player=session.full_state())
    await send(session.ws, "QUEST_LOG", quests={qid: quest_status_for(session, qid) for qid in QUESTS})


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
            elif mtype == "SET_COMBAT_STYLE":
                await handle_set_combat_style(session, msg)
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
            elif mtype == "DROP":
                await handle_drop(session, msg)
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
        process_pets(events)

        state = {
            "players": [s.public_state() for s in WORLD.sessions.values()],
            "monsters": [m.public_state() for m in WORLD.monsters.values()],
            "pets": [s.pet_public() for s in WORLD.sessions.values() if s.pet_id],
            "ground_items": {f"{x},{y}": items for (x, y), items in WORLD.ground_items.items()},
            "resources": {
                f"{x},{y}": n["type"]
                for (x, y), n in WORLD.resource_nodes.items()
                if not n["depleted"]
            },
            "fires": [f"{x},{y}" for (x, y) in WORLD.fires],
        }
        await broadcast("STATE_UPDATE", **state)
        for ev in events:
            await broadcast(ev["type"], **ev["data"])


def process_fires():
    expired = [k for k, until in WORLD.fires.items() if WORLD.tick_count >= until]
    for k in expired:
        del WORLD.fires[k]


async def process_combat(events):
    MAX_ATTACKERS = 2
    for session in list(WORLD.sessions.values()):
        # Up to two adjacent monsters that have aggro on this player may hit them.
        attackers = [
            m for m in WORLD.monsters.values()
            if m.alive and m.target_player_id == session.player_id
            and adjacent_or_same(session.x, session.y, m.x, m.y)
        ]
        attackers = attackers[:MAX_ATTACKERS]

        # Player swings at their locked target (or the first adjacent attacker).
        primary = None
        if session.in_combat_with and session.in_combat_with[0] == "monster":
            primary = WORLD.monsters.get(session.in_combat_with[1])
            if primary and (not primary.alive or primary not in attackers and not adjacent_or_same(session.x, session.y, primary.x, primary.y)):
                primary = None
        if primary is None and attackers:
            primary = attackers[0]
            session.in_combat_with = ("monster", primary.id)

        if primary and adjacent_or_same(session.x, session.y, primary.x, primary.y):
            dmg, hit = combat.resolve_hit(session.combat_stats(), {
                "attack": 1, "strength": 1, "defence": MONSTERS[primary.type]["defence"],
                "defence_bonus": MONSTERS[primary.type]["def_bonus"],
            })
            primary.hp = max(0, primary.hp - dmg)
            events.append({"type": "COMBAT_EVENT", "data": {
                "attacker_id": session.player_id, "defender_id": primary.id, "damage": dmg,
                "hit": hit, "defender_hp": primary.hp, "defender_max_hp": primary.max_hp,
                "kind": "player_hits_monster",
            }})
            style = session.combat_style if session.combat_style in COMBAT_STYLES else "attack"
            amount = dmg * 2  # 1 dmg → 2 xp, 2 dmg → 4 xp, etc.
            if amount > 0:
                before, after = WORLD.grant_xp(session, style, amount)
                events.append({"type": "SKILL_XP", "data": {
                    "player_id": session.player_id, "skill": style, "gained": amount,
                    "xp": session.xp[style], "level": after, "leveled_up": after > before,
                }})

            if primary.hp <= 0:
                primary.alive = False
                primary.respawn_at_tick = WORLD.tick_count + MONSTERS[primary.type]["respawn_ticks"]
                primary.target_player_id = None
                if session.in_combat_with == ("monster", primary.id):
                    session.in_combat_with = None
                drops = WORLD.drop_loot(primary.x, primary.y, MONSTERS[primary.type]["drops"])
                events.append({"type": "DEATH", "data": {"entity_id": primary.id, "entity_kind": "monster"}})
                if drops:
                    events.append({"type": "LOOT_DROPPED", "data": {"x": primary.x, "y": primary.y, "items": drops}})
                    await vacuum_ground_loot(session)
                    await send(session.ws, "PLAYER_UPDATE", player=session.full_state())
                check_quest_progress_on_kill(session, primary.type)
                attackers = [m for m in attackers if m is not primary]

        # Each adjacent aggro'd monster (max 2) hits the player
        died = False
        for monster in attackers:
            if not monster.alive:
                continue
            mstats = MONSTERS[monster.type]
            dmg2, hit2 = combat.resolve_hit(
                {"attack": mstats["attack"], "strength": mstats["strength"]},
                {"defence": session.level("defence"), "defence_bonus": session.weapon_bonuses()["def_bonus"]},
            )
            session.hp = max(0, session.hp - dmg2)
            events.append({"type": "COMBAT_EVENT", "data": {
                "attacker_id": monster.id, "defender_id": session.player_id, "damage": dmg2,
                "hit": hit2, "defender_hp": session.hp, "defender_max_hp": session.max_hp(),
                "kind": "monster_hits_player",
            }})
            before_hp, after_hp = WORLD.grant_xp(session, "hitpoints", 1)
            events.append({"type": "SKILL_XP", "data": {
                "player_id": session.player_id, "skill": "hitpoints", "gained": 1,
                "xp": session.xp["hitpoints"], "level": after_hp, "leveled_up": after_hp > before_hp,
            }})
            if session.hp <= 0:
                died = True
                break

        if died:
            lost = session.coins
            session.hp = session.max_hp()
            session.x, session.y = SPAWN_POINT
            session.coins = 0
            session.in_combat_with = None
            session.pet_target_id = None
            if session.pet_id:
                session.pet_x, session.pet_y = SPAWN_POINT
                session.pet_hp = PETS[session.pet_id]["hp"]
            for mon in WORLD.monsters.values():
                if mon.target_player_id == session.player_id:
                    mon.target_player_id = None
            WORLD.db.save_player_stats(session.player_id, coins=session.coins)
            events.append({"type": "DEATH", "data": {
                "entity_id": session.player_id, "entity_kind": "player",
                "coins_lost": lost,
            }})
            await send(session.ws, "PLAYER_UPDATE", player=session.full_state())
        elif not session.in_combat_with and not attackers:
            # Clear stale lock if nothing is fighting you
            pass


def _pet_step_toward(session, tx, ty):
    """Move pet one tile toward (tx, ty) if walkable."""
    px, py = session.pet_x, session.pet_y
    if (px, py) == (tx, ty):
        return
    options = []
    dx = 0 if px == tx else (1 if tx > px else -1)
    dy = 0 if py == ty else (1 if ty > py else -1)
    for nx, ny in ((px + dx, py), (px, py + dy), (px + dx, py + dy)):
        if is_walkable(WORLD.grid, nx, ny):
            options.append((nx, ny))
    if not options:
        return
    # Prefer tile closest to target
    options.sort(key=lambda p: max(abs(p[0] - tx), abs(p[1] - ty)))
    session.pet_x, session.pet_y = options[0]


def process_pets(events):
    """Pets follow their owner and attack monsters that aggro the player."""
    for session in list(WORLD.sessions.values()):
        if not session.pet_id or session.pet_id not in PETS:
            continue
        pdef = PETS[session.pet_id]
        if session.pet_hp <= 0:
            session.pet_hp = pdef["hp"]  # respawn with owner

        # Too far from owner → snap back
        if max(abs(session.pet_x - session.x), abs(session.pet_y - session.y)) > 10:
            session.pet_x, session.pet_y = session.x, session.y

        attackers = [
            m for m in WORLD.monsters.values()
            if m.alive and m.target_player_id == session.player_id
        ]
        target = None
        if attackers:
            target = min(
                attackers,
                key=lambda m: max(abs(m.x - session.pet_x), abs(m.y - session.pet_y)),
            )
            session.pet_target_id = target.id
        elif session.pet_target_id:
            m = WORLD.monsters.get(session.pet_target_id)
            if m and m.alive:
                target = m
            else:
                session.pet_target_id = None

        if target is not None:
            if adjacent_or_same(session.pet_x, session.pet_y, target.x, target.y):
                mstats = MONSTERS[target.type]
                dmg, hit = combat.resolve_hit(
                    {"attack": pdef["attack"], "strength": pdef["strength"]},
                    {"defence": mstats["defence"], "defence_bonus": mstats["def_bonus"]},
                )
                target.hp = max(0, target.hp - dmg)
                events.append({"type": "COMBAT_EVENT", "data": {
                    "attacker_id": f"pet:{session.player_id}",
                    "defender_id": target.id,
                    "damage": dmg, "hit": hit,
                    "defender_hp": target.hp, "defender_max_hp": target.max_hp,
                    "kind": "pet_hits_monster",
                }})
                if target.hp <= 0:
                    target.alive = False
                    target.respawn_at_tick = WORLD.tick_count + mstats["respawn_ticks"]
                    target.target_player_id = None
                    if session.in_combat_with == ("monster", target.id):
                        session.in_combat_with = None
                    session.pet_target_id = None
                    drops = WORLD.drop_loot(target.x, target.y, mstats["drops"])
                    events.append({"type": "DEATH", "data": {
                        "entity_id": target.id, "entity_kind": "monster",
                    }})
                    if drops:
                        events.append({"type": "LOOT_DROPPED", "data": {
                            "x": target.x, "y": target.y, "items": drops,
                        }})
                    check_quest_progress_on_kill(session, target.type)
            else:
                _pet_step_toward(session, target.x, target.y)
            continue

        # Idle: follow owner
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
        if ydef["item"] in ORE_ITEM_IDS and WORLD.count_ores(session) >= MAX_ORES:
            await send(session.ws, "ERROR", message=f"You can't carry more than {MAX_ORES} ores. Bank some first.")
            session.gathering_node = None
            continue
        if not WORLD.add_item_to_inventory(session, ydef["item"], 1):
            continue  # inventory full, just wait
        before, after = WORLD.grant_xp(session, ydef["skill"], ydef["xp"])
        events.append({"type": "SKILL_XP", "data": {
            "player_id": session.player_id, "skill": ydef["skill"], "gained": ydef["xp"],
            "xp": session.xp[ydef["skill"]], "level": after, "leveled_up": after > before,
        }})
        await send(session.ws, "PLAYER_UPDATE", player=session.full_state())
        if ydef["depletion_chance"] > 0 and random.random() < ydef["depletion_chance"]:
            node["depleted"] = True
            node["respawn_at"] = WORLD.tick_count + RESOURCE_YIELDS[node["type"]]["respawn_ticks"]
            session.gathering_node = None


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
            if not session:
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
        if m.ticks_since_wander < 5:
            continue
        m.ticks_since_wander = 0
        if random.random() < 0.4:
            dx, dy = random.choice([(1, 0), (-1, 0), (0, 1), (0, -1), (0, 0)])
            nx, ny = m.x + dx, m.y + dy
            radius = mdef["wander_radius"]
            if (is_walkable(WORLD.grid, nx, ny)
                    and abs(nx - m.spawn_x) <= radius
                    and abs(ny - m.spawn_y) <= radius
                    and in_room(nx, ny, m.home_room)):
                if not WORLD.occupied(nx, ny):
                    m.x, m.y = nx, ny


async def main():
    log.info("Starting MMORPG server on ws://%s:%s", HOST, PORT)
    async with websockets.serve(handler, HOST, PORT, ping_interval=20, ping_timeout=20):
        await game_loop()


if __name__ == "__main__":
    asyncio.run(main())
