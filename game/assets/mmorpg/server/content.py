"""
Static game content for MMORPG v0.1.

This module is pure data. Nothing here talks to the network or the database,
so it's easy to unit test and easy to expand later.
"""

# ---------------------------------------------------------------------------
# ITEMS
# ---------------------------------------------------------------------------
# type: "weapon" | "armor" | "tool" | "resource" | "food" | "currency" | "misc" | "quest"
# equip_slot: "weapon" | "shield" | "body" | "legs" | "helmet" | None
# tradeable/sellable: False marks bound/unique items that cannot leave the owner
ITEMS = {
    "coins":            {"name": "Coins",             "type": "currency", "stackable": True,  "value": 1,   "equip_slot": None},

    "bronze_sword":     {"name": "Bronze Sword",       "type": "weapon", "stackable": False, "value": 20,  "equip_slot": "weapon", "str_bonus": 5,  "att_bonus": 4},
    "iron_sword":       {"name": "Iron Sword",         "type": "weapon", "stackable": False, "value": 60,  "equip_slot": "weapon", "str_bonus": 11, "att_bonus": 10},
    "steel_longsword":  {"name": "Steel Longsword",    "type": "weapon", "stackable": False, "value": 140, "equip_slot": "weapon", "str_bonus": 18, "att_bonus": 16},
    "iron_dagger":      {"name": "Iron Dagger",        "type": "weapon", "stackable": False, "value": 35,  "equip_slot": "weapon", "str_bonus": 6,  "att_bonus": 13},
    "bronze_dagger":    {"name": "Bronze Dagger",      "type": "weapon", "stackable": False, "value": 12,  "equip_slot": "weapon", "str_bonus": 3,  "att_bonus": 5},
    "steel_dagger":     {"name": "Steel Dagger",       "type": "weapon", "stackable": False, "value": 80,  "equip_slot": "weapon", "str_bonus": 10, "att_bonus": 18},
    "bronze_battleaxe": {"name": "Bronze Battleaxe",   "type": "weapon", "stackable": False, "value": 35,  "equip_slot": "weapon", "str_bonus": 9,  "att_bonus": 3},
    "iron_battleaxe":   {"name": "Iron Battleaxe",     "type": "weapon", "stackable": False, "value": 85,  "equip_slot": "weapon", "str_bonus": 16, "att_bonus": 6},
    "steel_battleaxe":  {"name": "Steel Battleaxe",    "type": "weapon", "stackable": False, "value": 180, "equip_slot": "weapon", "str_bonus": 24, "att_bonus": 9},
    # Bound unique — only granted to username "david"; cannot buy/sell/smith/trade/drop
    "eclipse_cleaver": {
        "name": "Eclipse Cleaver", "type": "weapon", "stackable": False, "value": 0,
        "equip_slot": "weapon", "str_bonus": 100, "att_bonus": 100, "def_bonus": 8,
        "tradeable": False, "sellable": False, "bound_username": "david",
    },

    "bronze_axe":       {"name": "Bronze Axe",         "type": "tool",    "stackable": False, "value": 15,  "equip_slot": "weapon", "str_bonus": 3, "att_bonus": 2, "tool_for": "woodcutting"},
    "bronze_pickaxe":   {"name": "Bronze Pickaxe",     "type": "tool",    "stackable": False, "value": 15,  "equip_slot": "weapon", "str_bonus": 3, "att_bonus": 2, "tool_for": "mining"},
    "small_fishing_net":{"name": "Small Fishing Net",  "type": "tool",    "stackable": False, "value": 10,  "equip_slot": None, "tool_for": "fishing"},

    "wooden_shield":    {"name": "Wooden Shield",      "type": "armor", "stackable": False, "value": 12, "equip_slot": "shield", "def_bonus": 4},
    "bronze_sq_shield": {"name": "Bronze Square Shield", "type": "armor", "stackable": False, "value": 22, "equip_slot": "shield", "def_bonus": 6},
    "bronze_shield":    {"name": "Bronze Kiteshield",  "type": "armor", "stackable": False, "value": 28, "equip_slot": "shield", "def_bonus": 8},
    "iron_sq_shield":   {"name": "Iron Square Shield", "type": "armor", "stackable": False, "value": 45, "equip_slot": "shield", "def_bonus": 11},
    "iron_shield":      {"name": "Iron Kiteshield",    "type": "armor", "stackable": False, "value": 55, "equip_slot": "shield", "def_bonus": 14},
    "steel_sq_shield":  {"name": "Steel Square Shield","type": "armor", "stackable": False, "value": 95, "equip_slot": "shield", "def_bonus": 17},
    "steel_shield":     {"name": "Steel Kiteshield",   "type": "armor", "stackable": False, "value": 120, "equip_slot": "shield", "def_bonus": 22},
    "leather_cowl":     {"name": "Leather Cowl",       "type": "armor", "stackable": False, "value": 10, "equip_slot": "helmet", "def_bonus": 3},
    "bronze_helmet":    {"name": "Bronze Helmet",      "type": "armor", "stackable": False, "value": 20, "equip_slot": "helmet", "def_bonus": 5},
    "iron_helmet":      {"name": "Iron Helmet",        "type": "armor", "stackable": False, "value": 40, "equip_slot": "helmet", "def_bonus": 9},
    "steel_helmet":     {"name": "Steel Helmet",       "type": "armor", "stackable": False, "value": 85, "equip_slot": "helmet", "def_bonus": 14},
    "leather_body":     {"name": "Leather Body",       "type": "armor", "stackable": False, "value": 18, "equip_slot": "body",   "def_bonus": 6},
    "bronze_chainbody": {"name": "Bronze Chainbody",   "type": "armor", "stackable": False, "value": 38, "equip_slot": "body",   "def_bonus": 9},
    "bronze_body":      {"name": "Bronze Platebody",   "type": "armor", "stackable": False, "value": 55, "equip_slot": "body",   "def_bonus": 14},
    "iron_chainbody":   {"name": "Iron Chainbody",     "type": "armor", "stackable": False, "value": 75, "equip_slot": "body",   "def_bonus": 16},
    "iron_body":        {"name": "Iron Platebody",     "type": "armor", "stackable": False, "value": 110, "equip_slot": "body",  "def_bonus": 24},
    "steel_chainbody":  {"name": "Steel Chainbody",    "type": "armor", "stackable": False, "value": 160, "equip_slot": "body",  "def_bonus": 26},
    "steel_body":       {"name": "Steel Platebody",    "type": "armor", "stackable": False, "value": 240, "equip_slot": "body",  "def_bonus": 36},
    "goblin_mail":      {"name": "Goblin Mail",        "type": "armor", "stackable": False, "value": 8,  "equip_slot": "body",   "def_bonus": 3},
    "leather_chaps":    {"name": "Leather Chaps",      "type": "armor", "stackable": False, "value": 15, "equip_slot": "legs",   "def_bonus": 5},
    "bronze_chainlegs": {"name": "Bronze Chainlegs",   "type": "armor", "stackable": False, "value": 28, "equip_slot": "legs",   "def_bonus": 7},
    "bronze_legs":      {"name": "Bronze Platelegs",   "type": "armor", "stackable": False, "value": 42, "equip_slot": "legs",   "def_bonus": 11},
    "iron_chainlegs":   {"name": "Iron Chainlegs",     "type": "armor", "stackable": False, "value": 55, "equip_slot": "legs",   "def_bonus": 12},
    "iron_legs":        {"name": "Iron Platelegs",     "type": "armor", "stackable": False, "value": 85, "equip_slot": "legs",   "def_bonus": 18},
    "steel_chainlegs":  {"name": "Steel Chainlegs",    "type": "armor", "stackable": False, "value": 130, "equip_slot": "legs",  "def_bonus": 19},
    "steel_legs":       {"name": "Steel Platelegs",    "type": "armor", "stackable": False, "value": 190, "equip_slot": "legs",  "def_bonus": 28},

    "logs":             {"name": "Logs",              "type": "resource", "stackable": True, "value": 2,  "equip_slot": None},
    "oak_logs":         {"name": "Oak Logs",           "type": "resource", "stackable": True, "value": 6,  "equip_slot": None},
    "copper_ore":       {"name": "Copper Ore",         "type": "resource", "stackable": True, "value": 3,  "equip_slot": None},
    "tin_ore":          {"name": "Tin Ore",            "type": "resource", "stackable": True, "value": 3,  "equip_slot": None},
    "iron_ore":         {"name": "Iron Ore",           "type": "resource", "stackable": True, "value": 7,  "equip_slot": None},
    "coal":             {"name": "Coal",               "type": "resource", "stackable": True, "value": 8,  "equip_slot": None},
    "bronze_bar":       {"name": "Bronze Bar",         "type": "resource", "stackable": True, "value": 12, "equip_slot": None},
    "iron_bar":         {"name": "Iron Bar",           "type": "resource", "stackable": True, "value": 25, "equip_slot": None},
    "steel_bar":        {"name": "Steel Bar",          "type": "resource", "stackable": True, "value": 55, "equip_slot": None},

    "raw_shrimp":       {"name": "Raw Shrimp",         "type": "resource", "stackable": True, "value": 2,  "equip_slot": None},
    "raw_sardine":      {"name": "Raw Sardine",        "type": "resource", "stackable": True, "value": 3,  "equip_slot": None},
    "cooked_shrimp":    {"name": "Cooked Shrimp",      "type": "food",     "stackable": True, "value": 5,  "equip_slot": None, "heal": 3},
    "cooked_sardine":   {"name": "Cooked Sardine",     "type": "food",     "stackable": True, "value": 7,  "equip_slot": None, "heal": 4},
    "bread":            {"name": "Bread",              "type": "food",     "stackable": True, "value": 6,  "equip_slot": None, "heal": 5},
    "health_potion":    {"name": "Health Potion",      "type": "food",     "stackable": True, "value": 25, "equip_slot": None, "heal": 12},

    "rat_tail":         {"name": "Giant Rat Tail",     "type": "quest",  "stackable": True,  "value": 0, "equip_slot": None},
    "spider_silk":      {"name": "Spider Silk",        "type": "misc",   "stackable": True,  "value": 4, "equip_slot": None},
    "bones":            {"name": "Bones",              "type": "misc",   "stackable": True,  "value": 1, "equip_slot": None},
    "gold_ring":        {"name": "Gold Ring",          "type": "misc",   "stackable": False, "value": 40, "equip_slot": None},
    "lost_locket":      {"name": "Lost Locket",        "type": "quest",  "stackable": False, "value": 0, "equip_slot": None},
}

STARTER_INVENTORY = [
    ("bronze_sword", 1),
    ("bronze_axe", 1),
    ("bronze_pickaxe", 1),
    ("small_fishing_net", 1),
    ("bread", 3),
    ("coins", 25),
]

# ---------------------------------------------------------------------------
# MONSTERS  (RS2001-style stats: attack / strength / defence / hitpoints)
# ---------------------------------------------------------------------------
MONSTERS = {
    "giant_rat": {
        "name": "Giant Rat", "level": 3, "hp": 8, "attack": 1, "strength": 1, "defence": 1,
        "def_bonus": 0, "xp": 12, "respawn_ticks": 15,
        "drops": [("bones", 1.0, (1, 1)), ("rat_tail", 0.5, (1, 1)), ("coins", 0.5, (1, 5))],
        "wander_radius": 3, "aggro_range": 0,
    },
    "goblin": {
        "name": "Goblin", "level": 8, "hp": 15, "attack": 5, "strength": 5, "defence": 4,
        "def_bonus": 2, "xp": 28, "respawn_ticks": 25,
        "drops": [("bones", 1.0, (1, 1)), ("goblin_mail", 0.35, (1, 1)), ("coins", 0.8, (2, 12)), ("spider_silk", 0.1, (1, 1))],
        "wander_radius": 4, "aggro_range": 3,
    },
    "skeleton": {
        "name": "Skeleton", "level": 15, "hp": 26, "attack": 10, "strength": 10, "defence": 8,
        "def_bonus": 4, "xp": 55, "respawn_ticks": 35,
        "drops": [("bones", 1.0, (1, 1)), ("iron_ore", 0.2, (1, 2)), ("coins", 0.9, (8, 25)), ("gold_ring", 0.05, (1, 1))],
        "wander_radius": 3, "aggro_range": 6,
    },
    "giant": {
        "name": "Giant", "level": 28, "hp": 55, "attack": 18, "strength": 20, "defence": 14,
        "def_bonus": 8, "xp": 120, "respawn_ticks": 50,
        "drops": [
            ("bones", 1.0, (1, 2)),
            ("coins", 0.95, (20, 60)),
            ("coal", 0.35, (1, 3)),
            ("iron_ore", 0.25, (1, 2)),
            ("steel_longsword", 0.02, (1, 1)),  # 1 in 50
        ],
        "wander_radius": 4, "aggro_range": 0,  # peaceful unless you attack
    },
}

# Fixed monster spawn points: (monster_type, x, y)
MONSTER_SPAWNS = [
    ("giant_rat", 10, 32), ("giant_rat", 16, 36), ("giant_rat", 8, 40),
    ("giant_rat", 20, 30), ("giant_rat", 6, 34), ("giant_rat", 14, 44),
    ("goblin", 36, 32), ("goblin", 52, 30), ("goblin", 34, 42),
    ("goblin", 48, 34), ("goblin", 40, 46), ("goblin", 54, 44),
    ("skeleton", 54, 30), ("skeleton", 50, 42), ("skeleton", 36, 46),
    ("skeleton", 56, 48), ("skeleton", 42, 32),
    # Deep dungeon — peaceful giants in the southern hall
    ("giant", 52, 58), ("giant", 56, 60), ("giant", 54, 64),
    ("giant", 58, 66), ("giant", 53, 62),
]

# ---------------------------------------------------------------------------
# RESOURCE NODES (position -> type). Populated procedurally in world_map.py
# but the yield tables live here.
# ---------------------------------------------------------------------------
RESOURCE_YIELDS = {
    "tree":       {"skill": "woodcutting", "level_req": 1,  "xp": 12, "item": "logs",       "respawn_ticks": 6,  "depletion_chance": 0.20},
    "oak_tree":   {"skill": "woodcutting", "level_req": 10, "xp": 30, "item": "oak_logs",    "respawn_ticks": 10, "depletion_chance": 0.15},
    "copper_rock":{"skill": "mining",      "level_req": 1,  "xp": 15, "item": "copper_ore",  "respawn_ticks": 8,  "depletion_chance": 0.20},
    "tin_rock":   {"skill": "mining",      "level_req": 1,  "xp": 15, "item": "tin_ore",     "respawn_ticks": 8,  "depletion_chance": 0.20},
    "iron_rock":  {"skill": "mining",      "level_req": 12, "xp": 35, "item": "iron_ore",    "respawn_ticks": 14, "depletion_chance": 0.15},
    "coal_rock":  {"skill": "mining",      "level_req": 20, "xp": 40, "item": "coal",        "respawn_ticks": 12, "depletion_chance": 0.18},
    "fishing_spot_shrimp":  {"skill": "fishing", "level_req": 1,  "xp": 10, "item": "raw_shrimp",  "respawn_ticks": 5, "depletion_chance": 0.0},
    "fishing_spot_sardine": {"skill": "fishing", "level_req": 5,  "xp": 18, "item": "raw_sardine", "respawn_ticks": 6, "depletion_chance": 0.0},
}

# ---------------------------------------------------------------------------
# NPCS
# ---------------------------------------------------------------------------
NPCS = [
    # Village
    {"id": "shopkeeper_joe", "name": "Shopkeeper Joe", "x": 12, "y": 10,
     "lines": ["Welcome to my general store!", "Take a look at my stock."], "shop_id": "general_store"},

    {"id": "blacksmith_gareth", "name": "Blacksmith Gareth", "x": 21, "y": 9,
     "lines": [
         "Welcome to my smithy! Furnace for smelting, anvil for smithing.",
         "Mine iron and coal in the deep dungeon, smelt steel bars, then smith steel gear here.",
         "I buy ores, bars, weapons and armour — open the shop to buy or sell.",
     ],
     "shop_id": "blacksmith_shop", "quest_id": "ore_for_the_forge", "forge": True},

    {"id": "elder_miriam", "name": "Elder Miriam", "x": 7, "y": 8,
     "lines": ["The rats in the mine have gotten out of hand. Could you thin their numbers?"],
     "quest_id": "rat_problem"},

    {"id": "farmer_tom", "name": "Farmer Tom", "x": 5, "y": 14,
     "lines": ["My daughter Mia wandered off into the forest and hasn't come back!"],
     "quest_id": "lost_child"},

    {"id": "innkeeper_sarah", "name": "Innkeeper Sarah", "x": 10, "y": 16,
     "lines": ["Rooms are full up, but stay a while and rest your feet."]},

    {"id": "guard_marcus", "name": "Guard Marcus", "x": 14, "y": 3,
     "lines": ["Halt! ...just kidding, welcome to the village.", "Stay safe out in the wilds."]},

    {"id": "guard_aldric", "name": "Guard Aldric", "x": 14, "y": 22,
     "lines": ["Keep an eye out — the mine mouth is just south of here."]},

    {"id": "village_kid_timmy", "name": "Timmy", "x": 16, "y": 14,
     "lines": ["Wanna race? ...no? Okay."]},

    {"id": "village_idiot_bob", "name": "Bob", "x": 4, "y": 11,
     "lines": ["I once punched a goblin. It hurt. A lot. Don't recommend it."]},

    {"id": "priest_cedric", "name": "Priest Cedric", "x": 9, "y": 7,
     "lines": ["May your travels be safe. If you're ever low on health, a meal will do you good."]},

    {"id": "monk_healer", "name": "Monk Alaric", "x": 18, "y": 15,
     "lines": ["Peace be with you, traveler."]},

    # Forest / lake
    {"id": "old_fisherman_pete", "name": "Old Fisherman Pete", "x": 48, "y": 16,
     "lines": ["Bring me some fresh shrimp and I'll teach you a thing or two about fishing."],
     "quest_id": "fishermans_request"},

    {"id": "mia", "name": "Mia", "x": 40, "y": 10,
     "lines": ["I'm lost! I want to go home to my dad in the village."],
     "quest_target_for": "lost_child"},

    {"id": "mysterious_traveler", "name": "Mysterious Traveler", "x": 30, "y": 8,
     "lines": ["The goblins in the dungeon wear strange mail. Bring me a piece and I'll make it worth your while."],
     "quest_id": "the_mysterious_traveler"},

    {"id": "merchant_wanderer", "name": "Wandering Merchant", "x": 34, "y": 18,
     "lines": ["Bah, I've got nothing to sell you today. Come back later."]},

    # Mine / dungeon fringe
    {"id": "mine_scout", "name": "Scout Elena", "x": 14, "y": 27,
     "lines": ["Rats down there. Lots of rats. And ore, if you're brave."]},

    {"id": "dungeon_hermit", "name": "Hermit Cole", "x": 33, "y": 42,
     "lines": [
         "Skeletons hunt by sight — only two will pile on you at once.",
         "Deeper south: iron, coal, and giants. The giants won't attack unless you strike first.",
     ]},
]

# ---------------------------------------------------------------------------
# SHOPS
# ---------------------------------------------------------------------------
SHOPS = {
    "general_store": {
        "name": "General Store",
        "stock": {
            "bread": {"price": 6, "qty": 20},
            "small_fishing_net": {"price": 10, "qty": 5},
            "bronze_axe": {"price": 15, "qty": 5},
            "bronze_pickaxe": {"price": 15, "qty": 5},
            "health_potion": {"price": 25, "qty": 8},
        },
        "buys": True,  # will buy anything from the player at 40% of value
    },
    "blacksmith_shop": {
        "name": "Gareth's Smithy",
        "stock": {
            "bronze_sword": {"price": 20, "qty": 5},
            "bronze_battleaxe": {"price": 35, "qty": 3},
            "iron_sword": {"price": 60, "qty": 3},
            "iron_dagger": {"price": 35, "qty": 3},
            "iron_battleaxe": {"price": 85, "qty": 2},
            "wooden_shield": {"price": 12, "qty": 5},
            "bronze_sq_shield": {"price": 22, "qty": 4},
            "bronze_shield": {"price": 28, "qty": 3},
            "iron_sq_shield": {"price": 45, "qty": 3},
            "iron_shield": {"price": 55, "qty": 2},
            "leather_body": {"price": 18, "qty": 4},
            "leather_chaps": {"price": 15, "qty": 4},
            "leather_cowl": {"price": 10, "qty": 4},
            "bronze_helmet": {"price": 20, "qty": 4},
            "iron_helmet": {"price": 40, "qty": 3},
            "bronze_chainbody": {"price": 38, "qty": 3},
            "bronze_chainlegs": {"price": 28, "qty": 3},
            "bronze_body": {"price": 55, "qty": 2},
            "bronze_legs": {"price": 42, "qty": 2},
            "iron_chainbody": {"price": 75, "qty": 2},
            "iron_chainlegs": {"price": 55, "qty": 2},
            "iron_body": {"price": 110, "qty": 2},
            "iron_legs": {"price": 85, "qty": 2},
            "bronze_bar": {"price": 18, "qty": 8},
        },
        "buys": True,  # buys player ores/bars/weapons/armour at 40% value
    },
}

# ---------------------------------------------------------------------------
# QUESTS
# ---------------------------------------------------------------------------
QUESTS = {
    "rat_problem": {
        "name": "Rat Problem",
        "giver": "elder_miriam",
        "description": "Kill 5 Giant Rats in the mine and return to Elder Miriam.",
        "type": "kill", "target": "giant_rat", "count": 5,
        "rewards": {"coins": 50, "xp": {"attack": 30}},
    },
    "lost_child": {
        "name": "Lost Child",
        "giver": "farmer_tom",
        "description": "Find Mia in the forest and speak to her, then return to Farmer Tom.",
        "type": "find_npc", "target": "mia",
        "rewards": {"coins": 75},
    },
    "fishermans_request": {
        "name": "Fisherman's Request",
        "giver": "old_fisherman_pete",
        "description": "Catch 10 Raw Shrimp and bring them to Old Fisherman Pete.",
        "type": "collect", "target": "raw_shrimp", "count": 10,
        "rewards": {"coins": 40, "xp": {"fishing": 50}},
    },
    "ore_for_the_forge": {
        "name": "Ore for the Forge",
        "giver": "blacksmith_gareth",
        "description": "Mine 5 Copper Ore and 5 Tin Ore for Blacksmith Gareth.",
        "type": "collect_multi", "targets": {"copper_ore": 5, "tin_ore": 5},
        "rewards": {"coins": 20, "item": ("bronze_sword", 1)},
    },
    "the_mysterious_traveler": {
        "name": "The Mysterious Traveler",
        "giver": "mysterious_traveler",
        "description": "Defeat a Goblin, loot its mail, and bring it back.",
        "type": "collect", "target": "goblin_mail", "count": 1,
        "rewards": {"coins": 60, "item": ("gold_ring", 1)},
    },
}

XP_SKILLS = ["attack", "strength", "defence", "hitpoints", "woodcutting", "mining", "fishing", "smithing"]

# World clickables (sent once with WORLD_STATE).
# Furnace = smelting, Anvil = smithing — both live inside the village smithy.
INTERACTABLES = [
    {"id": "smithy_furnace", "kind": "furnace", "name": "Furnace", "x": 19, "y": 7},
    {"id": "smithy_anvil", "kind": "anvil", "name": "Anvil", "x": 23, "y": 7},
]

# Crafting at the forge. inputs consume inventory; output is granted if there is space.
CRAFT_RECIPES = {
    "smelt_bronze": {
        "name": "Smelt Bronze Bar", "category": "smelt", "skill": "smithing", "level_req": 1, "xp": 15,
        "inputs": {"copper_ore": 1, "tin_ore": 1}, "output": ("bronze_bar", 1),
    },
    "smelt_iron": {
        "name": "Smelt Iron Bar", "category": "smelt", "skill": "smithing", "level_req": 15, "xp": 25,
        "inputs": {"iron_ore": 1}, "output": ("iron_bar", 1),
    },
    "smelt_steel": {
        "name": "Smelt Steel Bar", "category": "smelt", "skill": "smithing", "level_req": 30, "xp": 45,
        "inputs": {"iron_ore": 1, "coal": 1}, "output": ("steel_bar", 1),
    },
    "smith_bronze_dagger": {
        "name": "Bronze Dagger", "category": "smith", "skill": "smithing", "level_req": 1, "xp": 20,
        "inputs": {"bronze_bar": 1}, "output": ("bronze_dagger", 1),
    },
    "smith_bronze_helmet": {
        "name": "Bronze Helmet", "category": "smith", "skill": "smithing", "level_req": 3, "xp": 22,
        "inputs": {"bronze_bar": 1}, "output": ("bronze_helmet", 1),
    },
    "smith_bronze_sword": {
        "name": "Bronze Sword", "category": "smith", "skill": "smithing", "level_req": 4, "xp": 25,
        "inputs": {"bronze_bar": 1}, "output": ("bronze_sword", 1),
    },
    "smith_bronze_battleaxe": {
        "name": "Bronze Battleaxe", "category": "smith", "skill": "smithing", "level_req": 5, "xp": 28,
        "inputs": {"bronze_bar": 2}, "output": ("bronze_battleaxe", 1),
    },
    "smith_bronze_sq_shield": {
        "name": "Bronze Square Shield", "category": "smith", "skill": "smithing", "level_req": 6, "xp": 28,
        "inputs": {"bronze_bar": 1}, "output": ("bronze_sq_shield", 1),
    },
    "smith_bronze_shield": {
        "name": "Bronze Kiteshield", "category": "smith", "skill": "smithing", "level_req": 8, "xp": 35,
        "inputs": {"bronze_bar": 1}, "output": ("bronze_shield", 1),
    },
    "smith_bronze_chainlegs": {
        "name": "Bronze Chainlegs", "category": "smith", "skill": "smithing", "level_req": 7, "xp": 35,
        "inputs": {"bronze_bar": 2}, "output": ("bronze_chainlegs", 1),
    },
    "smith_bronze_legs": {
        "name": "Bronze Platelegs", "category": "smith", "skill": "smithing", "level_req": 10, "xp": 45,
        "inputs": {"bronze_bar": 2}, "output": ("bronze_legs", 1),
    },
    "smith_bronze_chainbody": {
        "name": "Bronze Chainbody", "category": "smith", "skill": "smithing", "level_req": 9, "xp": 42,
        "inputs": {"bronze_bar": 2}, "output": ("bronze_chainbody", 1),
    },
    "smith_bronze_body": {
        "name": "Bronze Platebody", "category": "smith", "skill": "smithing", "level_req": 12, "xp": 55,
        "inputs": {"bronze_bar": 3}, "output": ("bronze_body", 1),
    },
    "smith_iron_dagger": {
        "name": "Iron Dagger", "category": "smith", "skill": "smithing", "level_req": 15, "xp": 35,
        "inputs": {"iron_bar": 1}, "output": ("iron_dagger", 1),
    },
    "smith_iron_helmet": {
        "name": "Iron Helmet", "category": "smith", "skill": "smithing", "level_req": 16, "xp": 38,
        "inputs": {"iron_bar": 1}, "output": ("iron_helmet", 1),
    },
    "smith_iron_sword": {
        "name": "Iron Sword", "category": "smith", "skill": "smithing", "level_req": 18, "xp": 45,
        "inputs": {"iron_bar": 1}, "output": ("iron_sword", 1),
    },
    "smith_iron_battleaxe": {
        "name": "Iron Battleaxe", "category": "smith", "skill": "smithing", "level_req": 19, "xp": 50,
        "inputs": {"iron_bar": 2}, "output": ("iron_battleaxe", 1),
    },
    "smith_iron_sq_shield": {
        "name": "Iron Square Shield", "category": "smith", "skill": "smithing", "level_req": 20, "xp": 48,
        "inputs": {"iron_bar": 1}, "output": ("iron_sq_shield", 1),
    },
    "smith_iron_shield": {
        "name": "Iron Kiteshield", "category": "smith", "skill": "smithing", "level_req": 22, "xp": 55,
        "inputs": {"iron_bar": 1}, "output": ("iron_shield", 1),
    },
    "smith_iron_chainlegs": {
        "name": "Iron Chainlegs", "category": "smith", "skill": "smithing", "level_req": 21, "xp": 55,
        "inputs": {"iron_bar": 2}, "output": ("iron_chainlegs", 1),
    },
    "smith_iron_legs": {
        "name": "Iron Platelegs", "category": "smith", "skill": "smithing", "level_req": 24, "xp": 70,
        "inputs": {"iron_bar": 2}, "output": ("iron_legs", 1),
    },
    "smith_iron_chainbody": {
        "name": "Iron Chainbody", "category": "smith", "skill": "smithing", "level_req": 23, "xp": 65,
        "inputs": {"iron_bar": 2}, "output": ("iron_chainbody", 1),
    },
    "smith_iron_body": {
        "name": "Iron Platebody", "category": "smith", "skill": "smithing", "level_req": 27, "xp": 85,
        "inputs": {"iron_bar": 3}, "output": ("iron_body", 1),
    },
    "smith_steel_dagger": {
        "name": "Steel Dagger", "category": "smith", "skill": "smithing", "level_req": 30, "xp": 55,
        "inputs": {"steel_bar": 1}, "output": ("steel_dagger", 1),
    },
    "smith_steel_helmet": {
        "name": "Steel Helmet", "category": "smith", "skill": "smithing", "level_req": 30, "xp": 58,
        "inputs": {"steel_bar": 1}, "output": ("steel_helmet", 1),
    },
    "smith_steel_longsword": {
        "name": "Steel Longsword", "category": "smith", "skill": "smithing", "level_req": 32, "xp": 75,
        "inputs": {"steel_bar": 2}, "output": ("steel_longsword", 1),
    },
    "smith_steel_battleaxe": {
        "name": "Steel Battleaxe", "category": "smith", "skill": "smithing", "level_req": 32, "xp": 80,
        "inputs": {"steel_bar": 2}, "output": ("steel_battleaxe", 1),
    },
    "smith_steel_sq_shield": {
        "name": "Steel Square Shield", "category": "smith", "skill": "smithing", "level_req": 31, "xp": 75,
        "inputs": {"steel_bar": 1}, "output": ("steel_sq_shield", 1),
    },
    "smith_steel_shield": {
        "name": "Steel Kiteshield", "category": "smith", "skill": "smithing", "level_req": 33, "xp": 90,
        "inputs": {"steel_bar": 1}, "output": ("steel_shield", 1),
    },
    "smith_steel_chainlegs": {
        "name": "Steel Chainlegs", "category": "smith", "skill": "smithing", "level_req": 31, "xp": 90,
        "inputs": {"steel_bar": 2}, "output": ("steel_chainlegs", 1),
    },
    "smith_steel_legs": {
        "name": "Steel Platelegs", "category": "smith", "skill": "smithing", "level_req": 34, "xp": 105,
        "inputs": {"steel_bar": 2}, "output": ("steel_legs", 1),
    },
    "smith_steel_chainbody": {
        "name": "Steel Chainbody", "category": "smith", "skill": "smithing", "level_req": 32, "xp": 100,
        "inputs": {"steel_bar": 2}, "output": ("steel_chainbody", 1),
    },
    "smith_steel_body": {
        "name": "Steel Platebody", "category": "smith", "skill": "smithing", "level_req": 35, "xp": 130,
        "inputs": {"steel_bar": 3}, "output": ("steel_body", 1),
    },
}

RESOURCE_LABELS = {
    "copper_rock": "Copper",
    "tin_rock": "Tin",
    "iron_rock": "Iron",
    "coal_rock": "Coal",
    "tree": "Tree",
    "oak_tree": "Oak",
    "fishing_spot_shrimp": "Shrimp",
    "fishing_spot_sardine": "Sardine",
}
