"""
Static game content for MMORPG v0.1.

This module is pure data. Nothing here talks to the network or the database,
so it's easy to unit test and easy to expand later.
"""

# ---------------------------------------------------------------------------
# ITEMS
# ---------------------------------------------------------------------------
# type: "weapon" | "armor" | "tool" | "resource" | "food" | "currency" | "misc" | "quest"
# equip_slot: "weapon" | "shield" | "body" | "legs" | None
ITEMS = {
    "coins":            {"name": "Coins",             "type": "currency", "stackable": True,  "value": 1,   "equip_slot": None},

    "bronze_sword":     {"name": "Bronze Sword",       "type": "weapon", "stackable": False, "value": 20,  "equip_slot": "weapon", "str_bonus": 5,  "att_bonus": 4},
    "iron_sword":       {"name": "Iron Sword",         "type": "weapon", "stackable": False, "value": 60,  "equip_slot": "weapon", "str_bonus": 11, "att_bonus": 10},
    "iron_dagger":      {"name": "Iron Dagger",        "type": "weapon", "stackable": False, "value": 35,  "equip_slot": "weapon", "str_bonus": 6,  "att_bonus": 13},

    "bronze_axe":       {"name": "Bronze Axe",         "type": "tool",    "stackable": False, "value": 15,  "equip_slot": "weapon", "str_bonus": 3, "att_bonus": 2, "tool_for": "woodcutting"},
    "bronze_pickaxe":   {"name": "Bronze Pickaxe",     "type": "tool",    "stackable": False, "value": 15,  "equip_slot": "weapon", "str_bonus": 3, "att_bonus": 2, "tool_for": "mining"},
    "small_fishing_net":{"name": "Small Fishing Net",  "type": "tool",    "stackable": False, "value": 10,  "equip_slot": None, "tool_for": "fishing"},

    "wooden_shield":    {"name": "Wooden Shield",      "type": "armor", "stackable": False, "value": 12, "equip_slot": "shield", "def_bonus": 4},
    "leather_body":     {"name": "Leather Body",       "type": "armor", "stackable": False, "value": 18, "equip_slot": "body",   "def_bonus": 6},
    "leather_chaps":    {"name": "Leather Chaps",      "type": "armor", "stackable": False, "value": 15, "equip_slot": "legs",   "def_bonus": 5},
    "goblin_mail":      {"name": "Goblin Mail",        "type": "armor", "stackable": False, "value": 8,  "equip_slot": "body",   "def_bonus": 3},

    "logs":             {"name": "Logs",              "type": "resource", "stackable": True, "value": 2,  "equip_slot": None},
    "oak_logs":         {"name": "Oak Logs",           "type": "resource", "stackable": True, "value": 6,  "equip_slot": None},
    "copper_ore":       {"name": "Copper Ore",         "type": "resource", "stackable": True, "value": 3,  "equip_slot": None},
    "tin_ore":          {"name": "Tin Ore",            "type": "resource", "stackable": True, "value": 3,  "equip_slot": None},
    "iron_ore":         {"name": "Iron Ore",           "type": "resource", "stackable": True, "value": 7,  "equip_slot": None},

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
        "wander_radius": 3,
    },
    "goblin": {
        "name": "Goblin", "level": 8, "hp": 15, "attack": 5, "strength": 5, "defence": 4,
        "def_bonus": 2, "xp": 28, "respawn_ticks": 25,
        "drops": [("bones", 1.0, (1, 1)), ("goblin_mail", 0.35, (1, 1)), ("coins", 0.8, (2, 12)), ("spider_silk", 0.1, (1, 1))],
        "wander_radius": 4,
    },
    "skeleton": {
        "name": "Skeleton", "level": 15, "hp": 26, "attack": 10, "strength": 10, "defence": 8,
        "def_bonus": 4, "xp": 55, "respawn_ticks": 35,
        "drops": [("bones", 1.0, (1, 1)), ("iron_ore", 0.2, (1, 2)), ("coins", 0.9, (8, 25)), ("gold_ring", 0.05, (1, 1))],
        "wander_radius": 2,
    },
}

# Fixed monster spawn points: (monster_type, x, y)
MONSTER_SPAWNS = [
    ("giant_rat", 10, 22), ("giant_rat", 13, 24), ("giant_rat", 8, 26),
    ("giant_rat", 15, 20), ("giant_rat", 6, 21),
    ("goblin", 24, 22), ("goblin", 34, 20), ("goblin", 22, 28),
    ("goblin", 30, 21), ("goblin", 25, 30),
    ("skeleton", 35, 19), ("skeleton", 32, 27), ("skeleton", 23, 31),
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
    "fishing_spot_shrimp":  {"skill": "fishing", "level_req": 1,  "xp": 10, "item": "raw_shrimp",  "respawn_ticks": 5, "depletion_chance": 0.0},
    "fishing_spot_sardine": {"skill": "fishing", "level_req": 5,  "xp": 18, "item": "raw_sardine", "respawn_ticks": 6, "depletion_chance": 0.0},
}

# ---------------------------------------------------------------------------
# NPCS
# ---------------------------------------------------------------------------
NPCS = [
    {"id": "shopkeeper_joe", "name": "Shopkeeper Joe", "x": 9, "y": 5,
     "lines": ["Welcome to my general store!", "Take a look at my stock."], "shop_id": "general_store"},

    {"id": "blacksmith_gareth", "name": "Blacksmith Gareth", "x": 12, "y": 6,
     "lines": ["Need a new blade? I've got the finest bronze and iron in the village."],
     "shop_id": "blacksmith_shop", "quest_id": "ore_for_the_forge"},

    {"id": "elder_miriam", "name": "Elder Miriam", "x": 6, "y": 4,
     "lines": ["The rats in the mine have gotten out of hand. Could you thin their numbers?"],
     "quest_id": "rat_problem"},

    {"id": "farmer_tom", "name": "Farmer Tom", "x": 5, "y": 9,
     "lines": ["My daughter Mia wandered off into the forest and hasn't come back!"],
     "quest_id": "lost_child"},

    {"id": "old_fisherman_pete", "name": "Old Fisherman Pete", "x": 4, "y": 11,
     "lines": ["Bring me some fresh shrimp and I'll teach you a thing or two about fishing."],
     "quest_id": "fishermans_request"},

    {"id": "mysterious_traveler", "name": "Mysterious Traveler", "x": 15, "y": 12,
     "lines": ["The goblins in the dungeon wear strange mail. Bring me a piece and I'll make it worth your while."],
     "quest_id": "the_mysterious_traveler"},

    {"id": "guard_marcus", "name": "Guard Marcus", "x": 9, "y": 2,
     "lines": ["Halt! ...just kidding, welcome to the village.", "Stay safe out in the wilds."]},
    {"id": "guard_aldric", "name": "Guard Aldric", "x": 3, "y": 5,
     "lines": ["Keep an eye out, the mine's been noisy lately."]},

    {"id": "innkeeper_sarah", "name": "Innkeeper Sarah", "x": 11, "y": 9,
     "lines": ["Rooms are full up, but stay a while and rest your feet."]},
    {"id": "priest_cedric", "name": "Priest Cedric", "x": 14, "y": 4,
     "lines": ["May your travels be safe. If you're ever low on health, a meal will do you good."]},

    {"id": "village_kid_timmy", "name": "Timmy", "x": 8, "y": 10,
     "lines": ["Wanna race? ...no? Okay."]},
    {"id": "village_idiot_bob", "name": "Bob", "x": 10, "y": 11,
     "lines": ["I once punched a goblin. It hurt. A lot. Don't recommend it."]},
    {"id": "merchant_wanderer", "name": "Wandering Merchant", "x": 7, "y": 7,
     "lines": ["Bah, I've got nothing to sell you today. Come back later."]},

    {"id": "mia", "name": "Mia", "x": 27, "y": 8,
     "lines": ["I'm lost! I want to go home to my dad in the village."],
     "quest_target_for": "lost_child"},

    {"id": "monk_healer", "name": "Monk Alaric", "x": 13, "y": 8,
     "lines": ["Peace be with you, traveler."]},
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
        "name": "Gareth's Forge",
        "stock": {
            "bronze_sword": {"price": 20, "qty": 5},
            "iron_sword": {"price": 60, "qty": 3},
            "iron_dagger": {"price": 35, "qty": 3},
            "wooden_shield": {"price": 12, "qty": 5},
            "leather_body": {"price": 18, "qty": 4},
            "leather_chaps": {"price": 15, "qty": 4},
        },
        "buys": True,
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

XP_SKILLS = ["attack", "strength", "defence", "hitpoints", "woodcutting", "mining", "fishing"]
