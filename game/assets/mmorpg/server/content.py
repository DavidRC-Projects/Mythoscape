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
    "mithril_dagger":   {"name": "Mithril Dagger",     "type": "weapon", "stackable": False, "value": 160, "equip_slot": "weapon", "str_bonus": 15, "att_bonus": 26},
    "mithril_sword":    {"name": "Mithril Sword",      "type": "weapon", "stackable": False, "value": 280, "equip_slot": "weapon", "str_bonus": 28, "att_bonus": 26},
    "mithril_battleaxe":{"name": "Mithril Battleaxe",  "type": "weapon", "stackable": False, "value": 360, "equip_slot": "weapon", "str_bonus": 36, "att_bonus": 14},
    "adamant_dagger":   {"name": "Adamantite Dagger",  "type": "weapon", "stackable": False, "value": 320, "equip_slot": "weapon", "str_bonus": 22, "att_bonus": 35},
    "adamant_sword":    {"name": "Adamantite Sword",   "type": "weapon", "stackable": False, "value": 520, "equip_slot": "weapon", "str_bonus": 40, "att_bonus": 38},
    "adamant_battleaxe":{"name": "Adamantite Battleaxe","type": "weapon","stackable": False, "value": 680, "equip_slot": "weapon", "str_bonus": 50, "att_bonus": 20},
    # Mythos set — dragon drops; top public gear (~70 bonuses)
    "mythos_dagger": {
        "name": "Mythos Dagger", "type": "weapon", "stackable": False, "value": 2500,
        "equip_slot": "weapon", "str_bonus": 65, "att_bonus": 70,
    },
    "mythos_longsword": {
        "name": "Mythos Longsword", "type": "weapon", "stackable": False, "value": 8000,
        "equip_slot": "weapon", "str_bonus": 70, "att_bonus": 70,
    },
    "mythos_body": {
        "name": "Mythos Armour", "type": "armor", "stackable": False, "value": 12000,
        "equip_slot": "body", "def_bonus": 70,
    },
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
    "mithril_sq_shield":{"name": "Mithril Square Shield","type": "armor", "stackable": False, "value": 190, "equip_slot": "shield", "def_bonus": 26},
    "mithril_shield":   {"name": "Mithril Kiteshield", "type": "armor", "stackable": False, "value": 240, "equip_slot": "shield", "def_bonus": 32},
    "adamant_sq_shield":{"name": "Adamantite Square Shield","type": "armor", "stackable": False, "value": 380, "equip_slot": "shield", "def_bonus": 36},
    "adamant_shield":   {"name": "Adamantite Kiteshield","type": "armor", "stackable": False, "value": 460, "equip_slot": "shield", "def_bonus": 44},
    "leather_cowl":     {"name": "Leather Cowl",       "type": "armor", "stackable": False, "value": 10, "equip_slot": "helmet", "def_bonus": 3},
    "bronze_helmet":    {"name": "Bronze Helmet",      "type": "armor", "stackable": False, "value": 20, "equip_slot": "helmet", "def_bonus": 5},
    "iron_helmet":      {"name": "Iron Helmet",        "type": "armor", "stackable": False, "value": 40, "equip_slot": "helmet", "def_bonus": 9},
    "steel_helmet":     {"name": "Steel Helmet",       "type": "armor", "stackable": False, "value": 85, "equip_slot": "helmet", "def_bonus": 14},
    "mithril_helmet":   {"name": "Mithril Helmet",     "type": "armor", "stackable": False, "value": 170, "equip_slot": "helmet", "def_bonus": 20},
    "adamant_helmet":   {"name": "Adamantite Helmet",  "type": "armor", "stackable": False, "value": 320, "equip_slot": "helmet", "def_bonus": 28},
    "leather_body":     {"name": "Leather Body",       "type": "armor", "stackable": False, "value": 18, "equip_slot": "body",   "def_bonus": 6},
    "bronze_chainbody": {"name": "Bronze Chainbody",   "type": "armor", "stackable": False, "value": 38, "equip_slot": "body",   "def_bonus": 9},
    "bronze_body":      {"name": "Bronze Platebody",   "type": "armor", "stackable": False, "value": 55, "equip_slot": "body",   "def_bonus": 14},
    "iron_chainbody":   {"name": "Iron Chainbody",     "type": "armor", "stackable": False, "value": 75, "equip_slot": "body",   "def_bonus": 16},
    "iron_body":        {"name": "Iron Platebody",     "type": "armor", "stackable": False, "value": 110, "equip_slot": "body",  "def_bonus": 24},
    "steel_chainbody":  {"name": "Steel Chainbody",    "type": "armor", "stackable": False, "value": 160, "equip_slot": "body",  "def_bonus": 26},
    "steel_body":       {"name": "Steel Platebody",    "type": "armor", "stackable": False, "value": 240, "equip_slot": "body",  "def_bonus": 36},
    "mithril_chainbody":{"name": "Mithril Chainbody",  "type": "armor", "stackable": False, "value": 320, "equip_slot": "body",  "def_bonus": 38},
    "mithril_body":     {"name": "Mithril Platebody",  "type": "armor", "stackable": False, "value": 480, "equip_slot": "body",  "def_bonus": 52},
    "adamant_chainbody":{"name": "Adamantite Chainbody","type": "armor","stackable": False, "value": 600, "equip_slot": "body",  "def_bonus": 54},
    "adamant_body":     {"name": "Adamantite Platebody","type": "armor","stackable": False, "value": 900, "equip_slot": "body",  "def_bonus": 72},
    "goblin_mail":      {"name": "Goblin Mail",        "type": "armor", "stackable": False, "value": 8,  "equip_slot": "body",   "def_bonus": 3},
    "leather_chaps":    {"name": "Leather Chaps",      "type": "armor", "stackable": False, "value": 15, "equip_slot": "legs",   "def_bonus": 5},
    "bronze_chainlegs": {"name": "Bronze Chainlegs",   "type": "armor", "stackable": False, "value": 28, "equip_slot": "legs",   "def_bonus": 7},
    "bronze_legs":      {"name": "Bronze Platelegs",   "type": "armor", "stackable": False, "value": 42, "equip_slot": "legs",   "def_bonus": 11},
    "iron_chainlegs":   {"name": "Iron Chainlegs",     "type": "armor", "stackable": False, "value": 55, "equip_slot": "legs",   "def_bonus": 12},
    "iron_legs":        {"name": "Iron Platelegs",     "type": "armor", "stackable": False, "value": 85, "equip_slot": "legs",   "def_bonus": 18},
    "steel_chainlegs":  {"name": "Steel Chainlegs",    "type": "armor", "stackable": False, "value": 130, "equip_slot": "legs",  "def_bonus": 19},
    "steel_legs":       {"name": "Steel Platelegs",    "type": "armor", "stackable": False, "value": 190, "equip_slot": "legs",  "def_bonus": 28},
    "mithril_chainlegs":{"name": "Mithril Chainlegs",  "type": "armor", "stackable": False, "value": 260, "equip_slot": "legs",  "def_bonus": 28},
    "mithril_legs":     {"name": "Mithril Platelegs",  "type": "armor", "stackable": False, "value": 380, "equip_slot": "legs",  "def_bonus": 40},
    "adamant_chainlegs":{"name": "Adamantite Chainlegs","type": "armor","stackable": False, "value": 500, "equip_slot": "legs",  "def_bonus": 40},
    "adamant_legs":     {"name": "Adamantite Platelegs","type": "armor","stackable": False, "value": 720, "equip_slot": "legs",  "def_bonus": 56},

    "logs":             {"name": "Logs",              "type": "resource", "stackable": True, "value": 2,  "equip_slot": None},
    "oak_logs":         {"name": "Oak Logs",           "type": "resource", "stackable": True, "value": 6,  "equip_slot": None},
    "tinderbox":        {"name": "Tinderbox",          "type": "tool",     "stackable": False, "value": 5,  "equip_slot": None, "tool_for": "firemaking"},
    "copper_ore":       {"name": "Copper Ore",         "type": "resource", "stackable": True, "value": 3,  "equip_slot": None},
    "tin_ore":          {"name": "Tin Ore",            "type": "resource", "stackable": True, "value": 3,  "equip_slot": None},
    "iron_ore":         {"name": "Iron Ore",           "type": "resource", "stackable": True, "value": 7,  "equip_slot": None},
    "coal":             {"name": "Coal",               "type": "resource", "stackable": True, "value": 8,  "equip_slot": None},
    "mithril_ore":      {"name": "Mithril Ore",        "type": "resource", "stackable": True, "value": 22, "equip_slot": None},
    "adamantite_ore":   {"name": "Adamantite Ore",     "type": "resource", "stackable": True, "value": 45, "equip_slot": None},
    "bronze_bar":       {"name": "Bronze Bar",         "type": "resource", "stackable": True, "value": 12, "equip_slot": None},
    "iron_bar":         {"name": "Iron Bar",           "type": "resource", "stackable": True, "value": 25, "equip_slot": None},
    "steel_bar":        {"name": "Steel Bar",          "type": "resource", "stackable": True, "value": 55, "equip_slot": None},
    "mithril_bar":      {"name": "Mithril Bar",        "type": "resource", "stackable": True, "value": 120, "equip_slot": None},
    "adamantite_bar":   {"name": "Adamantite Bar",     "type": "resource", "stackable": True, "value": 250, "equip_slot": None},

    "raw_shrimp":       {"name": "Raw Shrimp",         "type": "resource", "stackable": True, "value": 2,  "equip_slot": None},
    "raw_sardine":      {"name": "Raw Sardine",        "type": "resource", "stackable": True, "value": 3,  "equip_slot": None},
    "cooked_shrimp":    {"name": "Cooked Shrimp",      "type": "food",     "stackable": True, "value": 5,  "equip_slot": None, "heal": 3},
    "cooked_sardine":   {"name": "Cooked Sardine",     "type": "food",     "stackable": True, "value": 7,  "equip_slot": None, "heal": 4},
    "burnt_shrimp":     {"name": "Burnt Shrimp",       "type": "food",     "stackable": True, "value": 1,  "equip_slot": None, "heal": 0},
    "burnt_sardine":    {"name": "Burnt Sardine",      "type": "food",     "stackable": True, "value": 1,  "equip_slot": None, "heal": 0},
    "bread":            {"name": "Bread",              "type": "food",     "stackable": True, "value": 6,  "equip_slot": None, "heal": 5},
    "health_potion":    {"name": "Health Potion",      "type": "food",     "stackable": True, "value": 25, "equip_slot": None, "heal": 12},

    "rat_tail":         {"name": "Giant Rat Tail",     "type": "quest",  "stackable": True,  "value": 0, "equip_slot": None},
    "spider_silk":      {"name": "Spider Silk",        "type": "misc",   "stackable": True,  "value": 4, "equip_slot": None},
    "bones":            {"name": "Bones",              "type": "misc",   "stackable": True,  "value": 1, "equip_slot": None, "karma_xp": 18},
    "big_bones":        {"name": "Big Bones",          "type": "misc",   "stackable": True,  "value": 3, "equip_slot": None, "karma_xp": 54},
    "dragon_bones":     {"name": "Dragon Bones",       "type": "misc",   "stackable": True,  "value": 12, "equip_slot": None, "karma_xp": 144},
    "gold_ring":        {"name": "Gold Ring",          "type": "misc",   "stackable": False, "value": 40, "equip_slot": None},
    "lost_locket":      {"name": "Lost Locket",        "type": "quest",  "stackable": False, "value": 0, "equip_slot": None},

    # Pet shop companions (buying activates the pet; not carried as inventory gear)
    "pet_cat": {
        "name": "Cat (Lv 1)", "type": "pet", "stackable": False, "value": 10, "equip_slot": None,
        "pet_id": "cat", "tradeable": False, "sellable": False,
    },
    "pet_husky": {
        "name": "White Husky (Lv 10)", "type": "pet", "stackable": False, "value": 1000, "equip_slot": None,
        "pet_id": "husky", "tradeable": False, "sellable": False,
    },
    "pet_skeleton": {
        "name": "Skeleton Pet (Lv 25)", "type": "pet", "stackable": False, "value": 10000, "equip_slot": None,
        "pet_id": "skeleton_pet", "tradeable": False, "sellable": False,
    },
    "pet_dragon": {
        "name": "Dragon Pet (Lv 50)", "type": "pet", "stackable": False, "value": 65000, "equip_slot": None,
        "pet_id": "dragon_pet", "tradeable": False, "sellable": False,
    },
}

STARTER_INVENTORY = [
    ("bronze_sword", 1),
    ("bronze_axe", 1),
    ("bronze_pickaxe", 1),
    ("small_fishing_net", 1),
    ("tinderbox", 1),
    ("bread", 3),
    ("coins", 25),
]

# Logs that can be lit with a tinderbox → temporary campfire.
# duration = ticks the fire lasts; level_req / xp = Firemaking.
FIRE_LOGS = {
    "logs": {"duration": 50, "level_req": 1, "xp": 40},
    "oak_logs": {"duration": 80, "level_req": 15, "xp": 60},
}


def cook_burn_chance(cook_level, level_req):
    """Probability of burning food. Higher cooking → lower chance; 0 at req+20."""
    span = 20
    excess = cook_level - level_req
    if excess >= span:
        return 0.0
    if excess < 0:
        return 1.0
    return max(0.0, 0.55 * (1.0 - excess / float(span)))

# ---------------------------------------------------------------------------
# MONSTERS  (RS2001-style stats: attack / strength / defence / hitpoints)
# ---------------------------------------------------------------------------
MONSTERS = {
    "giant_rat": {
        "name": "Giant Rat", "level": 3, "hp": 8, "attack": 1, "strength": 1, "defence": 1,
        "def_bonus": 0, "xp": 12, "respawn_ticks": 15,
        "drops": [
            ("bones", 1.0, (1, 1)),
            ("coins", 0.85, (1, 8)),
            ("rat_tail", 0.5, (1, 1)),
        ],
        "wander_radius": 3, "aggro_range": 0,
    },
    "goblin": {
        "name": "Goblin", "level": 8, "hp": 15, "attack": 5, "strength": 5, "defence": 4,
        "def_bonus": 2, "xp": 28, "respawn_ticks": 25,
        "drops": [
            ("bones", 1.0, (1, 1)),
            ("coins", 0.95, (4, 18)),
            ("goblin_mail", 0.35, (1, 1)),
            # 1 in 10 — one random bronze weapon or armour piece
            (("bronze_dagger", "bronze_sword", "bronze_helmet", "bronze_sq_shield",
              "bronze_chainbody", "bronze_chainlegs"), 0.10, (1, 1)),
            ("spider_silk", 0.10, (1, 1)),
        ],
        "wander_radius": 4, "aggro_range": 3,
    },
    "skeleton": {
        "name": "Skeleton", "level": 15, "hp": 26, "attack": 10, "strength": 10, "defence": 8,
        "def_bonus": 4, "xp": 55, "respawn_ticks": 35,
        "drops": [
            ("bones", 1.0, (1, 1)),
            ("coins", 0.95, (10, 32)),
            ("iron_ore", 0.22, (1, 2)),
            # 1 in 10 — one random iron weapon or armour piece
            (("iron_dagger", "iron_sword", "iron_helmet", "iron_sq_shield",
              "iron_chainbody", "iron_chainlegs"), 0.10, (1, 1)),
            ("gold_ring", 0.05, (1, 1)),
        ],
        "wander_radius": 3, "aggro_range": 6,
    },
    "giant": {
        "name": "Giant", "level": 28, "hp": 55, "attack": 18, "strength": 20, "defence": 14,
        "def_bonus": 8, "xp": 120, "respawn_ticks": 50,
        "drops": [
            ("big_bones", 1.0, (1, 1)),
            ("coins", 0.95, (25, 70)),
            ("coal", 0.35, (1, 3)),
            ("iron_ore", 0.25, (1, 2)),
            ("steel_longsword", 0.02, (1, 1)),  # 1 in 50
        ],
        "wander_radius": 4, "aggro_range": 0,  # peaceful unless you attack
    },
    # Double normal skeleton stats — mithril cavern
    "big_skeleton": {
        "name": "Big Skeleton", "level": 30, "hp": 52, "attack": 20, "strength": 20, "defence": 16,
        "def_bonus": 8, "xp": 110, "respawn_ticks": 40,
        "drops": [
            ("bones", 1.0, (1, 1)),
            ("coins", 0.95, (20, 60)),
            ("mithril_ore", 0.28, (1, 2)),
            (("mithril_dagger", "mithril_helmet", "mithril_sq_shield",
              "mithril_chainbody", "mithril_chainlegs"), 0.10, (1, 1)),
            ("gold_ring", 0.08, (1, 1)),
        ],
        "wander_radius": 4, "aggro_range": 7,
    },
    # Spider nest — tougher than big skeletons, weaker than the dragon
    "spider": {
        "name": "Giant Spider", "level": 48, "hp": 95, "attack": 38, "strength": 42, "defence": 30,
        "def_bonus": 14, "xp": 210, "respawn_ticks": 55,
        "drops": [
            ("bones", 1.0, (1, 1)),
            ("coins", 0.95, (40, 110)),
            ("spider_silk", 0.85, (1, 3)),
            ("mithril_ore", 0.18, (1, 2)),
            (("mithril_dagger", "mithril_sword", "mithril_helmet"), 0.08, (1, 1)),
            ("health_potion", 0.12, (1, 1)),
        ],
        "wander_radius": 4, "aggro_range": 7,
    },
    # Adamantite lair boss — tough for ~level 50 combat
    "dragon": {
        "name": "Adamant Dragon", "level": 78, "hp": 200, "attack": 90, "strength": 180, "defence": 80,
        "def_bonus": 50, "xp": 650, "respawn_ticks": 120,
        "drops": [
            ("dragon_bones", 1.0, (1, 1)),
            ("coins", 1.0, (250, 900)),
            ("adamantite_ore", 0.55, (1, 3)),
            ("adamantite_bar", 0.12, (1, 1)),
            ("mythos_dagger", 0.10, (1, 1)),       # 1 in 10
            ("mythos_longsword", 0.02, (1, 1)),    # 1 in 50
            ("mythos_body", 0.01, (1, 1)),         # 1 in 100 armour
        ],
        "wander_radius": 3, "aggro_range": 8,
    },
}

# Fixed monster spawn points: (monster_type, x, y)
MONSTER_SPAWNS = [
    ("giant_rat", 10, 38), ("giant_rat", 18, 42), ("giant_rat", 8, 46),
    ("giant_rat", 24, 36), ("giant_rat", 6, 40), ("giant_rat", 16, 50),
    # Upper dungeon — goblins (more packed)
    ("goblin", 44, 38), ("goblin", 48, 36), ("goblin", 42, 40),
    ("goblin", 62, 36), ("goblin", 66, 38), ("goblin", 58, 40),
    ("goblin", 42, 50), ("goblin", 46, 52), ("goblin", 50, 48),
    ("goblin", 58, 50), ("goblin", 64, 50), ("goblin", 68, 54),
    ("goblin", 48, 54), ("goblin", 60, 44),
    # Upper dungeon — skeletons
    ("skeleton", 64, 36), ("skeleton", 68, 40), ("skeleton", 60, 50),
    ("skeleton", 44, 52), ("skeleton", 50, 54), ("skeleton", 66, 54),
    ("skeleton", 50, 38), ("skeleton", 46, 36), ("skeleton", 54, 50),
    ("skeleton", 62, 52), ("skeleton", 42, 48), ("skeleton", 70, 48),
    # Deep dungeon — giants
    ("giant", 60, 66), ("giant", 64, 68), ("giant", 62, 72),
    ("giant", 66, 74), ("giant", 61, 70),
    # Mithril cavern — big skeletons
    ("big_skeleton", 44, 84), ("big_skeleton", 48, 86), ("big_skeleton", 42, 90),
    ("big_skeleton", 50, 88), ("big_skeleton", 46, 92),
    # Spider nest — mid-late dungeon
    ("spider", 60, 78), ("spider", 64, 79), ("spider", 68, 78),
    ("spider", 62, 80), ("spider", 66, 80), ("spider", 60, 80),
    ("spider", 68, 79),
    # Adamantite lair — dragon
    ("dragon", 62, 90),
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
    "mithril_rock":{"skill": "mining",     "level_req": 55, "xp": 80, "item": "mithril_ore", "respawn_ticks": 18, "depletion_chance": 0.16},
    "adamantite_rock":{"skill": "mining",  "level_req": 70, "xp": 110,"item": "adamantite_ore","respawn_ticks": 22, "depletion_chance": 0.14},
    "fishing_spot_shrimp":  {"skill": "fishing", "level_req": 1,  "xp": 10, "item": "raw_shrimp",  "respawn_ticks": 5, "depletion_chance": 0.0},
    "fishing_spot_sardine": {"skill": "fishing", "level_req": 5,  "xp": 18, "item": "raw_sardine", "respawn_ticks": 6, "depletion_chance": 0.0},
}

# ---------------------------------------------------------------------------
# NPCS
# ---------------------------------------------------------------------------
NPCS = [
    # Village
    {"id": "shopkeeper_joe", "name": "Shopkeeper Joe", "x": 19, "y": 6,
     "lines": ["Welcome to my general store!", "Take a look at my stock."], "shop_id": "general_store"},

    {"id": "blacksmith_gareth", "name": "Blacksmith Gareth", "x": 42, "y": 8,
     "lines": [
         "Welcome to my smithy! Furnace for smelting, anvil for smithing.",
         "Mine iron and coal in the deep dungeon, smelt steel bars, then smith steel gear here.",
         "I buy ores, bars, weapons and armour — open the shop to buy or sell.",
     ],
     "shop_id": "blacksmith_shop", "quest_id": "ore_for_the_forge", "forge": True},

    {"id": "banker_iris", "name": "Banker Iris", "x": 30, "y": 14,
     "lines": [
         "Welcome to the Village Bank.",
         "Store coins and items here. Purse max 65,000 — vault holds 10 million coins.",
         "Click the bank booth (or talk to me) to open your bank.",
     ],
     "bank": True},

    {"id": "elder_miriam", "name": "Elder Miriam", "x": 7, "y": 5,
     "lines": ["The rats in the mine have gotten out of hand. Could you thin their numbers?"],
     "quest_id": "rat_problem"},

    {"id": "farmer_tom", "name": "Farmer Tom", "x": 19, "y": 23,
     "lines": ["My daughter Mia wandered off into the forest and hasn't come back!"],
     "quest_id": "lost_child"},

    {"id": "innkeeper_sarah", "name": "Innkeeper Sarah", "x": 7, "y": 23,
     "lines": [
         "Rooms are full up, but stay a while and rest your feet.",
         "Cook your catch on the hearth — raw fish won't restore your health.",
     ]},

    {"id": "guard_marcus", "name": "Guard Marcus", "x": 20, "y": 4,
     "lines": ["Halt! ...just kidding, welcome to the village.", "Stay safe out in the wilds."]},

    {"id": "guard_aldric", "name": "Guard Aldric", "x": 20, "y": 29,
     "lines": ["Keep an eye out — the mine mouth is just south of here."]},

    {"id": "village_kid_timmy", "name": "Timmy", "x": 24, "y": 17,
     "lines": ["Wanna race? ...no? Okay."]},

    {"id": "village_idiot_bob", "name": "Bob", "x": 5, "y": 15,
     "lines": ["I once punched a goblin. It hurt. A lot. Don't recommend it."]},

    {"id": "priest_cedric", "name": "Priest Cedric", "x": 5, "y": 6,
     "lines": ["May your travels be safe. If you're ever low on health, a meal will do you good."]},

    {"id": "monk_healer", "name": "Monk Alaric", "x": 28, "y": 21,
     "lines": ["Peace be with you, traveler."]},

    # Forest / lake
    {"id": "old_fisherman_pete", "name": "Old Fisherman Pete", "x": 60, "y": 17,
     "lines": ["Bring me some fresh shrimp and I'll teach you a thing or two about fishing."],
     "quest_id": "fishermans_request"},

    {"id": "mia", "name": "Mia", "x": 52, "y": 10,
     "lines": ["I'm lost! I want to go home to my dad in the village."],
     "quest_target_for": "lost_child"},

    {"id": "mysterious_traveler", "name": "Mysterious Traveler", "x": 44, "y": 8,
     "lines": ["The goblins in the dungeon wear strange mail. Bring me a piece and I'll make it worth your while."],
     "quest_id": "the_mysterious_traveler"},

    {"id": "merchant_wanderer", "name": "Wandering Merchant", "x": 48, "y": 20,
     "lines": ["Bah, I've got nothing to sell you today. Come back later."]},

    {"id": "pet_keeper_luna", "name": "Pet Keeper Luna", "x": 41, "y": 23,
     "lines": [
         "Welcome to the Pet Emporium!",
         "Companions follow you and fight when monsters attack.",
         "Cat 10c · White Husky 1,000c · Skeleton 10,000c · Dragon 65,000c",
     ],
     "shop_id": "pet_shop"},

    # Mine / dungeon fringe
    {"id": "mine_scout", "name": "Scout Elena", "x": 20, "y": 33,
     "lines": ["Rats down there. Lots of rats. And ore, if you're brave."]},

    {"id": "dungeon_hermit", "name": "Hermit Cole", "x": 40, "y": 48,
     "lines": [
         "Skeletons hunt by sight — only two will pile on you at once.",
         "Deeper south: iron, coal, and giants. The giants won't attack unless you strike first.",
         "Past the mithril bones lies a spider nest — harder than big skeletons, softer than the dragon.",
         "Their silk is worth coin, but watch those fangs.",
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
            "tinderbox": {"price": 5, "qty": 10},
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
    "pet_shop": {
        "name": "Pet Emporium",
        "stock": {
            "pet_cat": {"price": 10, "qty": 99},
            "pet_husky": {"price": 1000, "qty": 99},
            "pet_skeleton": {"price": 10000, "qty": 99},
            "pet_dragon": {"price": 65000, "qty": 99},
        },
        "buys": False,
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

XP_SKILLS = [
    "attack", "strength", "defence", "hitpoints",
    "woodcutting", "mining", "fishing", "cooking", "firemaking", "smithing", "karma",
]

# Skills that contribute to combat level (classic RS melee formula, no prayer).
COMBAT_SKILLS = ("attack", "strength", "defence", "hitpoints")

SKILL_DISPLAY_NAMES = {
    "attack": "Attack", "strength": "Strength", "defence": "Defence",
    "hitpoints": "Hitpoints", "woodcutting": "Woodcutting", "mining": "Mining",
    "fishing": "Fishing", "cooking": "Cooking", "firemaking": "Firemaking",
    "smithing": "Smithing", "karma": "Karma",
}

# Karma blesses worn gear. Level 2 weapons get +2 attack (matches L).
# Armour pieces favour defence with smaller attack/strength drips, scaling to 200.
def karma_slot_bonus(slot_name, karma_level):
    L = max(0, min(200, int(karma_level)))
    if L <= 0:
        return {"att_bonus": 0, "str_bonus": 0, "def_bonus": 0}
    if slot_name == "weapon":
        return {"att_bonus": L, "str_bonus": (L * 3) // 4, "def_bonus": L // 20}
    if slot_name == "shield":
        return {"att_bonus": L // 10, "str_bonus": 0, "def_bonus": (L // 2) + (L // 10)}
    if slot_name == "helmet":
        return {"att_bonus": L // 8, "str_bonus": 0, "def_bonus": L // 3}
    if slot_name == "body":
        return {"att_bonus": L // 12, "str_bonus": L // 10, "def_bonus": L}
    if slot_name == "legs":
        return {"att_bonus": 0, "str_bonus": L // 8, "def_bonus": (L * 2) // 3}
    return {"att_bonus": 0, "str_bonus": 0, "def_bonus": 0}


def karma_total_bonus(karma_level, equipment):
    total = {"att_bonus": 0, "str_bonus": 0, "def_bonus": 0}
    for slot_name, item_id in (equipment or {}).items():
        if not item_id:
            continue
        for k, v in karma_slot_bonus(slot_name, karma_level).items():
            total[k] += v
    return total


# ---------------------------------------------------------------------------
# PETS — companions bought from Pet Keeper Luna
# ---------------------------------------------------------------------------
PETS = {
    "cat": {
        "name": "Cat", "level": 1, "sprite": "pet_cat",
        "hp": 10, "attack": 3, "strength": 3, "defence": 2, "def_bonus": 0,
    },
    "husky": {
        "name": "White Husky", "level": 10, "sprite": "pet_husky",
        "hp": 32, "attack": 14, "strength": 14, "defence": 12, "def_bonus": 4,
    },
    "skeleton_pet": {
        "name": "Skeleton", "level": 25, "sprite": "pet_skeleton",
        "hp": 60, "attack": 28, "strength": 28, "defence": 22, "def_bonus": 8,
    },
    "dragon_pet": {
        "name": "Dragon", "level": 50, "sprite": "pet_dragon",
        "hp": 120, "attack": 55, "strength": 62, "defence": 48, "def_bonus": 20,
    },
}

# Economy / inventory caps
MAX_PURSE_COINS = 65000
MAX_BANK_COINS = 10_000_000
MAX_ORES = 100
ORE_ITEM_IDS = frozenset({
    "copper_ore", "tin_ore", "iron_ore", "coal", "mithril_ore", "adamantite_ore",
})
BANK_SLOTS = 96

# World clickables (sent once with WORLD_STATE).
# ---------------------------------------------------------------------------
# TRAVEL DESTINATIONS  (minimap / Travel modal — client auto-walks here)
# kind: "place" | "monster"
# action: optional post-arrive action {"type": "BANK"} etc.
# ---------------------------------------------------------------------------
TRAVEL_DESTINATIONS = [
    # Places
    {"id": "crossroads", "kind": "place", "label": "Village Crossroads",
     "x": 20, "y": 16, "blurb": "Spawn & hub"},
    {"id": "bank", "kind": "place", "label": "Village Bank",
     "x": 30, "y": 15, "blurb": "Store coins & items", "action": {"type": "BANK"}},
    {"id": "general_store", "kind": "place", "label": "General Store",
     "x": 19, "y": 7, "blurb": "Shopkeeper Joe"},
    {"id": "smithy", "kind": "place", "label": "Smithy Furnace",
     "x": 38, "y": 7, "blurb": "Smelt ores"},
    {"id": "anvil", "kind": "place", "label": "Smithy Anvil",
     "x": 45, "y": 7, "blurb": "Smith gear"},
    {"id": "pet_shop", "kind": "place", "label": "Pet Emporium",
     "x": 41, "y": 26, "blurb": "Luna's companions"},
    {"id": "inn_hearth", "kind": "place", "label": "Inn Hearth",
     "x": 5, "y": 22, "blurb": "Cook food"},
    {"id": "lake", "kind": "place", "label": "Fishing Lake",
     "x": 58, "y": 17, "blurb": "Shore fishing"},
    {"id": "dungeon_gate", "kind": "place", "label": "Dungeon Entrance",
     "x": 30, "y": 49, "blurb": "Enter the depths"},
    {"id": "dungeon_bank", "kind": "place", "label": "Dungeon Bank",
     "x": 36, "y": 46, "blurb": "Chest near the gate", "action": {"type": "BANK"}},
    # Monsters (camp centres)
    {"id": "rats", "kind": "monster", "label": "Giant Rats",
     "x": 14, "y": 42, "monster": "giant_rat", "blurb": "Starter mine"},
    {"id": "goblins", "kind": "monster", "label": "Goblins",
     "x": 52, "y": 44, "monster": "goblin", "blurb": "Upper dungeon"},
    {"id": "skeletons", "kind": "monster", "label": "Skeletons",
     "x": 56, "y": 46, "monster": "skeleton", "blurb": "Upper dungeon"},
    {"id": "giants", "kind": "monster", "label": "Giants",
     "x": 63, "y": 70, "monster": "giant", "blurb": "Peaceful until hit"},
    {"id": "big_skeletons", "kind": "monster", "label": "Big Skeletons",
     "x": 46, "y": 88, "monster": "big_skeleton", "blurb": "Mithril cavern"},
    {"id": "spiders", "kind": "monster", "label": "Giant Spiders",
     "x": 64, "y": 79, "monster": "spider", "blurb": "Spider nest"},
    {"id": "dragon", "kind": "monster", "label": "Adamant Dragon",
     "x": 62, "y": 90, "monster": "dragon", "blurb": "Adamantite lair"},
]


INTERACTABLES = [
    {"id": "smithy_furnace", "kind": "furnace", "name": "Furnace", "x": 38, "y": 6},
    {"id": "smithy_anvil", "kind": "anvil", "name": "Anvil", "x": 45, "y": 6},
    {"id": "smithy_door", "kind": "door", "name": "Smithy Door", "x": 42, "y": 14,
     "enter_x": 42, "enter_y": 12, "exit_x": 42, "exit_y": 15, "building": "smithy"},
    {"id": "cottage_nw_door", "kind": "door", "name": "Door", "x": 7, "y": 11,
     "enter_x": 7, "enter_y": 9, "exit_x": 7, "exit_y": 12, "building": "cottage_nw"},
    {"id": "cottage_ne_door", "kind": "door", "name": "Door", "x": 19, "y": 11,
     "enter_x": 19, "enter_y": 9, "exit_x": 19, "exit_y": 12, "building": "cottage_ne"},
    {"id": "cottage_sw_door", "kind": "door", "name": "Door", "x": 7, "y": 28,
     "enter_x": 7, "enter_y": 26, "exit_x": 7, "exit_y": 29, "building": "cottage_sw"},
    {"id": "cottage_se_door", "kind": "door", "name": "Door", "x": 19, "y": 28,
     "enter_x": 19, "enter_y": 26, "exit_x": 19, "exit_y": 29, "building": "cottage_se"},
    {"id": "bank_door", "kind": "door", "name": "Bank Door", "x": 30, "y": 18,
     "enter_x": 30, "enter_y": 16, "exit_x": 30, "exit_y": 19, "building": "bank"},
    {"id": "pet_door", "kind": "door", "name": "Pet Emporium Door", "x": 41, "y": 28,
     "enter_x": 41, "enter_y": 26, "exit_x": 41, "exit_y": 29, "building": "pet_emporium"},
    {"id": "bank_booth", "kind": "bank", "name": "Bank Booth", "x": 30, "y": 14},
    {"id": "dungeon_bank", "kind": "bank", "name": "Dungeon Bank Chest", "x": 36, "y": 46,
     "variant": "chest"},
    {"id": "dungeon_entrance", "kind": "dungeon_entrance", "name": "Dungeon Entrance",
     "x": 38, "y": 49, "enter_x": 40, "enter_y": 49, "exit_x": 30, "exit_y": 49},

    # --- Elder's Hall (cottage_nw) floor 4–10, 4–10 ---
    {"id": "elder_fireplace", "kind": "range", "name": "Hearth", "x": 5, "y": 4},
    {"id": "elder_bookshelf", "kind": "bookshelf", "name": "Bookshelf", "x": 9, "y": 4},
    {"id": "elder_table", "kind": "table", "name": "Council Table", "x": 5, "y": 8},
    {"id": "elder_chair_a", "kind": "chair", "name": "Chair", "x": 4, "y": 8, "facing": 1},
    {"id": "elder_chair_b", "kind": "chair", "name": "Chair", "x": 6, "y": 8, "facing": -1},
    {"id": "elder_rug", "kind": "rug", "name": "Rug", "x": 7, "y": 7, "color": [90, 50, 110]},
    {"id": "elder_candle", "kind": "candle", "name": "Candle", "x": 9, "y": 8},
    {"id": "elder_chest", "kind": "chest", "name": "Chest", "x": 9, "y": 9},

    # --- General Store (cottage_ne) floor 16–22, 4–10 ---
    {"id": "shop_counter", "kind": "counter", "name": "Shop Counter", "x": 19, "y": 5},
    {"id": "shop_shelf_a", "kind": "shelf", "name": "Shelves", "x": 16, "y": 4},
    {"id": "shop_shelf_b", "kind": "shelf", "name": "Shelves", "x": 22, "y": 4},
    {"id": "shop_crate_a", "kind": "crate", "name": "Crate", "x": 16, "y": 8},
    {"id": "shop_crate_b", "kind": "crate", "name": "Crate", "x": 17, "y": 9},
    {"id": "shop_barrel", "kind": "barrel", "name": "Barrel", "x": 22, "y": 8},
    {"id": "shop_barrel_b", "kind": "barrel", "name": "Barrel", "x": 21, "y": 9},
    {"id": "shop_rug", "kind": "rug", "name": "Rug", "x": 19, "y": 8, "color": [70, 90, 130]},

    # --- The Resting Ox inn (cottage_sw) floor 4–10, 21–27 ---
    {"id": "inn_fireplace", "kind": "range", "name": "Cooking Hearth", "x": 4, "y": 21},
    {"id": "inn_table", "kind": "table", "name": "Table", "x": 9, "y": 23},
    {"id": "inn_chair_a", "kind": "chair", "name": "Chair", "x": 8, "y": 23, "facing": 1},
    {"id": "inn_chair_b", "kind": "chair", "name": "Chair", "x": 10, "y": 23, "facing": -1},
    {"id": "inn_bed_a", "kind": "bed", "name": "Bed", "x": 4, "y": 25},
    {"id": "inn_bed_b", "kind": "bed", "name": "Bed", "x": 4, "y": 26},
    {"id": "inn_barrel", "kind": "barrel", "name": "Ale Barrel", "x": 9, "y": 21},
    {"id": "inn_barrel_b", "kind": "barrel", "name": "Ale Barrel", "x": 10, "y": 21},
    {"id": "inn_rug", "kind": "rug", "name": "Rug", "x": 7, "y": 24, "color": [130, 70, 40]},
    {"id": "inn_candle", "kind": "candle", "name": "Candle", "x": 9, "y": 25},

    # --- Farmhouse (cottage_se) floor 16–22, 21–27 ---
    {"id": "farm_bed", "kind": "bed", "name": "Bed", "x": 16, "y": 21},
    {"id": "farm_table", "kind": "table", "name": "Table", "x": 21, "y": 23},
    {"id": "farm_chair", "kind": "chair", "name": "Chair", "x": 20, "y": 23, "facing": 1},
    {"id": "farm_crate", "kind": "crate", "name": "Crate", "x": 22, "y": 21},
    {"id": "farm_barrel", "kind": "barrel", "name": "Barrel", "x": 16, "y": 25},
    {"id": "farm_chest", "kind": "chest", "name": "Chest", "x": 22, "y": 26},
    {"id": "farm_rug", "kind": "rug", "name": "Rug", "x": 19, "y": 24, "color": [100, 80, 50]},
    {"id": "farm_candle", "kind": "candle", "name": "Candle", "x": 21, "y": 21},

    # --- Village Bank floor 27–33, 13–17 ---
    {"id": "bank_booth_w", "kind": "bank", "name": "Bank Booth", "x": 28, "y": 14},
    {"id": "bank_booth_e", "kind": "bank", "name": "Bank Booth", "x": 32, "y": 14},
    {"id": "bank_chest_a", "kind": "chest", "name": "Vault Chest", "x": 27, "y": 13},
    {"id": "bank_chest_b", "kind": "chest", "name": "Vault Chest", "x": 33, "y": 13},
    {"id": "bank_stool_a", "kind": "stool", "name": "Stool", "x": 28, "y": 16},
    {"id": "bank_stool_b", "kind": "stool", "name": "Stool", "x": 32, "y": 16},
    {"id": "bank_rug", "kind": "rug", "name": "Rug", "x": 30, "y": 15, "color": [50, 70, 110]},

    # --- Gareth's Smithy floor 37–47, 5–13 ---
    {"id": "smith_workbench", "kind": "workbench", "name": "Workbench", "x": 40, "y": 6},
    {"id": "smith_weapon_rack", "kind": "weapon_rack", "name": "Weapon Rack", "x": 47, "y": 5},
    {"id": "smith_barrel_a", "kind": "barrel", "name": "Ore Barrel", "x": 37, "y": 9},
    {"id": "smith_barrel_b", "kind": "barrel", "name": "Ore Barrel", "x": 37, "y": 10},
    {"id": "smith_crate", "kind": "crate", "name": "Crate", "x": 47, "y": 10},
    {"id": "smith_quench", "kind": "quench_bucket", "name": "Quench Bucket", "x": 44, "y": 8},
    {"id": "smith_chest", "kind": "chest", "name": "Tool Chest", "x": 47, "y": 12},

    # --- Pet Emporium floor 37–45, 21–27 ---
    {"id": "pet_counter", "kind": "counter", "name": "Counter", "x": 41, "y": 22},
    {"id": "pet_cage_a", "kind": "pet_cage", "name": "Cage", "x": 37, "y": 21},
    {"id": "pet_cage_b", "kind": "pet_cage", "name": "Cage", "x": 38, "y": 21},
    {"id": "pet_bed_a", "kind": "pet_bed", "name": "Pet Bed", "x": 44, "y": 21},
    {"id": "pet_bed_b", "kind": "pet_bed", "name": "Pet Bed", "x": 45, "y": 22},
    {"id": "pet_shelf", "kind": "shelf", "name": "Supplies", "x": 37, "y": 24},
    {"id": "pet_barrel", "kind": "barrel", "name": "Feed Barrel", "x": 45, "y": 25},
    {"id": "pet_rug", "kind": "rug", "name": "Rug", "x": 41, "y": 24, "color": [80, 120, 70]},
    {"id": "pet_candle", "kind": "candle", "name": "Candle", "x": 39, "y": 26},
]

# Enterable buildings — roofs hide when the local player stands on the floor.
# material: "wood" (timber/plank) or "brick" (grey masonry)
BUILDINGS = [
    {
        "id": "cottage_nw", "name": "Elder's Hall", "kind": "house", "style": 0,
        "material": "wood",
        "x0": 3, "y0": 3, "x1": 11, "y1": 11,
        "floor_x0": 4, "floor_y0": 4, "floor_x1": 10, "floor_y1": 10,
    },
    {
        "id": "cottage_ne", "name": "General Store", "kind": "house", "style": 0,
        "material": "wood",
        "x0": 15, "y0": 3, "x1": 23, "y1": 11,
        "floor_x0": 16, "floor_y0": 4, "floor_x1": 22, "floor_y1": 10,
    },
    {
        "id": "cottage_sw", "name": "The Resting Ox", "kind": "house", "style": 1,
        "material": "brick",
        "x0": 3, "y0": 20, "x1": 11, "y1": 28,
        "floor_x0": 4, "floor_y0": 21, "floor_x1": 10, "floor_y1": 27,
    },
    {
        "id": "cottage_se", "name": "Farmhouse", "kind": "house", "style": 1,
        "material": "wood",
        "x0": 15, "y0": 20, "x1": 23, "y1": 28,
        "floor_x0": 16, "floor_y0": 21, "floor_x1": 22, "floor_y1": 27,
    },
    {
        "id": "bank", "name": "Village Bank", "kind": "house", "style": 1,
        "material": "brick",
        "x0": 26, "y0": 12, "x1": 34, "y1": 18,
        "floor_x0": 27, "floor_y0": 13, "floor_x1": 33, "floor_y1": 17,
    },
    {
        "id": "smithy", "name": "Gareth's Smithy", "kind": "smithy", "style": 1,
        "material": "brick",
        "x0": 36, "y0": 4, "x1": 48, "y1": 14,
        "floor_x0": 37, "floor_y0": 5, "floor_x1": 47, "floor_y1": 13,
    },
    {
        "id": "pet_emporium", "name": "Pet Emporium", "kind": "house", "style": 0,
        "material": "wood",
        "x0": 36, "y0": 20, "x1": 46, "y1": 28,
        "floor_x0": 37, "floor_y0": 21, "floor_x1": 45, "floor_y1": 27,
    },
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
    "smelt_mithril": {
        "name": "Smelt Mithril Bar", "category": "smelt", "skill": "smithing", "level_req": 50, "xp": 80,
        "inputs": {"mithril_ore": 1, "coal": 4}, "output": ("mithril_bar", 1),
    },
    "smelt_adamantite": {
        "name": "Smelt Adamantite Bar", "category": "smelt", "skill": "smithing", "level_req": 70, "xp": 120,
        "inputs": {"adamantite_ore": 1, "coal": 6}, "output": ("adamantite_bar", 1),
    },
    "smith_mithril_dagger": {
        "name": "Mithril Dagger", "category": "smith", "skill": "smithing", "level_req": 50, "xp": 90,
        "inputs": {"mithril_bar": 1}, "output": ("mithril_dagger", 1),
    },
    "smith_mithril_helmet": {
        "name": "Mithril Helmet", "category": "smith", "skill": "smithing", "level_req": 50, "xp": 95,
        "inputs": {"mithril_bar": 1}, "output": ("mithril_helmet", 1),
    },
    "smith_mithril_sword": {
        "name": "Mithril Sword", "category": "smith", "skill": "smithing", "level_req": 54, "xp": 120,
        "inputs": {"mithril_bar": 2}, "output": ("mithril_sword", 1),
    },
    "smith_mithril_battleaxe": {
        "name": "Mithril Battleaxe", "category": "smith", "skill": "smithing", "level_req": 55, "xp": 130,
        "inputs": {"mithril_bar": 2}, "output": ("mithril_battleaxe", 1),
    },
    "smith_mithril_sq_shield": {
        "name": "Mithril Square Shield", "category": "smith", "skill": "smithing", "level_req": 52, "xp": 120,
        "inputs": {"mithril_bar": 1}, "output": ("mithril_sq_shield", 1),
    },
    "smith_mithril_shield": {
        "name": "Mithril Kiteshield", "category": "smith", "skill": "smithing", "level_req": 56, "xp": 140,
        "inputs": {"mithril_bar": 1}, "output": ("mithril_shield", 1),
    },
    "smith_mithril_chainlegs": {
        "name": "Mithril Chainlegs", "category": "smith", "skill": "smithing", "level_req": 53, "xp": 140,
        "inputs": {"mithril_bar": 2}, "output": ("mithril_chainlegs", 1),
    },
    "smith_mithril_legs": {
        "name": "Mithril Platelegs", "category": "smith", "skill": "smithing", "level_req": 58, "xp": 170,
        "inputs": {"mithril_bar": 2}, "output": ("mithril_legs", 1),
    },
    "smith_mithril_chainbody": {
        "name": "Mithril Chainbody", "category": "smith", "skill": "smithing", "level_req": 55, "xp": 160,
        "inputs": {"mithril_bar": 2}, "output": ("mithril_chainbody", 1),
    },
    "smith_mithril_body": {
        "name": "Mithril Platebody", "category": "smith", "skill": "smithing", "level_req": 60, "xp": 200,
        "inputs": {"mithril_bar": 3}, "output": ("mithril_body", 1),
    },
    "smith_adamant_dagger": {
        "name": "Adamantite Dagger", "category": "smith", "skill": "smithing", "level_req": 70, "xp": 140,
        "inputs": {"adamantite_bar": 1}, "output": ("adamant_dagger", 1),
    },
    "smith_adamant_helmet": {
        "name": "Adamantite Helmet", "category": "smith", "skill": "smithing", "level_req": 70, "xp": 145,
        "inputs": {"adamantite_bar": 1}, "output": ("adamant_helmet", 1),
    },
    "smith_adamant_sword": {
        "name": "Adamantite Sword", "category": "smith", "skill": "smithing", "level_req": 74, "xp": 180,
        "inputs": {"adamantite_bar": 2}, "output": ("adamant_sword", 1),
    },
    "smith_adamant_battleaxe": {
        "name": "Adamantite Battleaxe", "category": "smith", "skill": "smithing", "level_req": 75, "xp": 195,
        "inputs": {"adamantite_bar": 2}, "output": ("adamant_battleaxe", 1),
    },
    "smith_adamant_sq_shield": {
        "name": "Adamantite Square Shield", "category": "smith", "skill": "smithing", "level_req": 72, "xp": 180,
        "inputs": {"adamantite_bar": 1}, "output": ("adamant_sq_shield", 1),
    },
    "smith_adamant_shield": {
        "name": "Adamantite Kiteshield", "category": "smith", "skill": "smithing", "level_req": 76, "xp": 210,
        "inputs": {"adamantite_bar": 1}, "output": ("adamant_shield", 1),
    },
    "smith_adamant_chainlegs": {
        "name": "Adamantite Chainlegs", "category": "smith", "skill": "smithing", "level_req": 73, "xp": 210,
        "inputs": {"adamantite_bar": 2}, "output": ("adamant_chainlegs", 1),
    },
    "smith_adamant_legs": {
        "name": "Adamantite Platelegs", "category": "smith", "skill": "smithing", "level_req": 78, "xp": 250,
        "inputs": {"adamantite_bar": 2}, "output": ("adamant_legs", 1),
    },
    "smith_adamant_chainbody": {
        "name": "Adamantite Chainbody", "category": "smith", "skill": "smithing", "level_req": 75, "xp": 240,
        "inputs": {"adamantite_bar": 2}, "output": ("adamant_chainbody", 1),
    },
    "smith_adamant_body": {
        "name": "Adamantite Platebody", "category": "smith", "skill": "smithing", "level_req": 80, "xp": 300,
        "inputs": {"adamantite_bar": 3}, "output": ("adamant_body", 1),
    },
    # Cooking — hearth, range, or a player-lit campfire
    "cook_shrimp": {
        "name": "Cook Shrimp", "category": "cook", "skill": "cooking", "level_req": 1, "xp": 30,
        "inputs": {"raw_shrimp": 1}, "output": ("cooked_shrimp", 1), "burnt": ("burnt_shrimp", 1),
    },
    "cook_sardine": {
        "name": "Cook Sardine", "category": "cook", "skill": "cooking", "level_req": 5, "xp": 40,
        "inputs": {"raw_sardine": 1}, "output": ("cooked_sardine", 1), "burnt": ("burnt_sardine", 1),
    },
}

RESOURCE_LABELS = {
    "copper_rock": "Copper",
    "tin_rock": "Tin",
    "iron_rock": "Iron",
    "coal_rock": "Coal",
    "mithril_rock": "Mithril",
    "adamantite_rock": "Adamantite",
    "tree": "Tree",
    "oak_tree": "Oak",
    "fishing_spot_shrimp": "Shrimp",
    "fishing_spot_sardine": "Sardine",
}
