"""
Static game content for MMORPG v0.1.

This module is pure data. Nothing here talks to the network or the database,
so it's easy to unit test and easy to expand later.
"""

# ---------------------------------------------------------------------------
# ITEMS
# ---------------------------------------------------------------------------
# type: "weapon" | "armor" | "tool" | "resource" | "food" | "currency" | "misc" | "quest" | "ammo"
# equip_slot: "weapon" | "shield" | "body" | "legs" | "helmet" | "amulet" | "ring" | "ammo" | None
# tradeable/sellable: False marks bound/unique items that cannot leave the owner
# Bows use weapon_type "bow" with range / ranged_att / ranged_str (Archery combat).
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
    # Mythos set — dragon drops; top public gear (100 bonuses)
    "mythos_dagger": {
        "name": "Mythos Dagger", "type": "weapon", "stackable": False, "value": 2500,
        "equip_slot": "weapon", "str_bonus": 100, "att_bonus": 100,
    },
    "mythos_longsword": {
        "name": "Mythos Longsword", "type": "weapon", "stackable": False, "value": 8000,
        "equip_slot": "weapon", "str_bonus": 100, "att_bonus": 100,
    },
    "mythos_body": {
        "name": "Mythos Armour", "type": "armor", "stackable": False, "value": 12000,
        "equip_slot": "body", "def_bonus": 100,
    },
    "mythos_helmet": {
        "name": "Mythos Dragon Helm", "type": "armor", "stackable": False, "value": 9000,
        "equip_slot": "helmet", "def_bonus": 100, "att_bonus": 100,
        "desc": "Crimson dragon-plate helm of the Mythos set.",
    },
    "mythos_legs": {
        "name": "Mythos Platelegs", "type": "armor", "stackable": False, "value": 10000,
        "equip_slot": "legs", "def_bonus": 100,
        "desc": "Crimson dragon-plate legs of the Mythos set.",
    },
    "mythos_shield": {
        "name": "Mythos Kiteshield", "type": "armor", "stackable": False, "value": 8500,
        "equip_slot": "shield", "def_bonus": 100,
        "desc": "Crimson dragon-plate kite of the Mythos set.",
    },
    # Tidehollow Cave completion medal — worn as an amulet
    "tidehollow_amulet": {
        "name": "Tidehollow Medal", "type": "armor", "stackable": False, "value": 1,
        "equip_slot": "amulet", "def_bonus": 5, "att_bonus": 5, "str_bonus": 5,
        "regen_hp": 1, "regen_seconds": 3,
        "tradeable": False, "sellable": False,
        "desc": "Proof you cleared Tidehollow. While worn: restore 1 Hitpoint every 3 seconds.",
    },
    "emberdeep_amulet": {
        "name": "Emberdeep Medal", "type": "armor", "stackable": False, "value": 1,
        "equip_slot": "amulet", "def_bonus": 8, "att_bonus": 6, "str_bonus": 6,
        "regen_hp": 1, "regen_seconds": 2,
        "tradeable": False, "sellable": False,
        "desc": "Proof you conquered Emberdeep. While worn: restore 1 Hitpoint every 2 seconds.",
    },
    # Bound unique — only granted to username "david"; cannot buy/sell/smith/trade/drop
    "eclipse_cleaver": {
        "name": "Eclipse Cleaver", "type": "weapon", "stackable": False, "value": 0,
        "equip_slot": "weapon", "str_bonus": 200, "att_bonus": 200, "def_bonus": 8,
        "tradeable": False, "sellable": False, "bound_username": "david",
    },
    # Bound unique companion shield — future monster drop (not on any table yet)
    "eclipse_shield": {
        "name": "Eclipse Aegis", "type": "armor", "stackable": False, "value": 0,
        "equip_slot": "shield", "def_bonus": 150,
        "tradeable": False, "sellable": False, "bound_username": "david",
        "bound_to_inventory": True,
        "desc": "Black steel and gold — the twin of the Eclipse Cleaver. Destined as a rare monster drop (not obtainable yet).",
    },
    "eclipse_body": {
        "name": "Eclipse Platebody", "type": "armor", "stackable": False, "value": 0,
        "equip_slot": "body", "def_bonus": 150,
        "tradeable": False, "sellable": False, "bound_username": "david",
        "bound_to_inventory": True,
        "desc": "Obsidian plate with gold filigree and an eclipse chest seal. Future monster drop — not obtainable yet.",
    },
    "eclipse_legs": {
        "name": "Eclipse Platelegs", "type": "armor", "stackable": False, "value": 0,
        "equip_slot": "legs", "def_bonus": 145,
        "tradeable": False, "sellable": False, "bound_username": "david",
        "bound_to_inventory": True,
        "desc": "Black steel greaves with gold knee-cops and thrice-riveted faulds. Future monster drop — not obtainable yet.",
    },
    "eclipse_helmet": {
        "name": "Eclipse Grillhelm", "type": "armor", "stackable": False, "value": 0,
        "equip_slot": "helmet", "def_bonus": 150, "att_bonus": 150,
        "tradeable": False, "sellable": False, "bound_username": "david",
        "bound_to_inventory": True,
        "desc": "Full black helm with a gold-barred face grill. Outclasses the Mythos Dragon Helm. Future monster drop — not obtainable yet.",
    },

    "bronze_axe":       {"name": "Bronze Axe",         "type": "tool",    "stackable": False, "value": 15,  "equip_slot": "weapon", "str_bonus": 3, "att_bonus": 2, "tool_for": "woodcutting"},
    "bronze_pickaxe":   {"name": "Bronze Pickaxe",     "type": "tool",    "stackable": False, "value": 15,  "equip_slot": "weapon", "str_bonus": 3, "att_bonus": 2, "tool_for": "mining"},
    "small_fishing_net":{"name": "Small Fishing Net",  "type": "tool",    "stackable": False, "value": 10,  "equip_slot": None, "tool_for": "fishing"},
    "fishing_rod":      {"name": "Fishing Rod",        "type": "tool",    "stackable": False, "value": 45,  "equip_slot": None, "tool_for": "fishing"},
    "fly_fishing_rod":  {"name": "Fly Fishing Rod",    "type": "tool",    "stackable": False, "value": 90,  "equip_slot": None, "tool_for": "fishing"},
    "lobster_pot":      {"name": "Lobster Pot",        "type": "tool",    "stackable": False, "value": 120, "equip_slot": None, "tool_for": "fishing"},
    "harpoon":          {"name": "Harpoon",            "type": "tool",    "stackable": False, "value": 160, "equip_slot": None, "tool_for": "fishing"},

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
    "willow_logs":      {"name": "Willow Logs",        "type": "resource", "stackable": True, "value": 12, "equip_slot": None},
    "maple_logs":       {"name": "Maple Logs",         "type": "resource", "stackable": True, "value": 22, "equip_slot": None},
    "yew_logs":         {"name": "Yew Logs",           "type": "resource", "stackable": True, "value": 45, "equip_slot": None},
    "magic_logs":       {"name": "Magic Logs",         "type": "resource", "stackable": True, "value": 90, "equip_slot": None},
    "tinderbox":        {"name": "Tinderbox",          "type": "tool",     "stackable": False, "value": 5,  "equip_slot": None, "tool_for": "firemaking"},
    "knife":            {"name": "Knife",              "type": "tool",     "stackable": False, "value": 8,  "equip_slot": None, "tool_for": "fletching",
                         "desc": "Carve logs into shafts and unstrung bows."},
    "bow_string":       {"name": "Bowstring",          "type": "resource", "stackable": True,  "value": 10, "equip_slot": None},
    "feather":          {"name": "Feather",            "type": "resource", "stackable": True,  "value": 2,  "equip_slot": None},
    "arrow_shaft":      {"name": "Arrow Shaft",        "type": "resource", "stackable": True,  "value": 1,  "equip_slot": None},
    "headless_arrow":   {"name": "Headless Arrow",     "type": "resource", "stackable": True,  "value": 2,  "equip_slot": None},
    "bronze_arrowtips": {"name": "Bronze Arrowtips",   "type": "resource", "stackable": True,  "value": 4,  "equip_slot": None},
    "iron_arrowtips":   {"name": "Iron Arrowtips",     "type": "resource", "stackable": True,  "value": 8,  "equip_slot": None},
    "steel_arrowtips":  {"name": "Steel Arrowtips",    "type": "resource", "stackable": True,  "value": 18, "equip_slot": None},
    "mithril_arrowtips":{"name": "Mithril Arrowtips",  "type": "resource", "stackable": True,  "value": 40, "equip_slot": None},
    "adamant_arrowtips":{"name": "Adamantite Arrowtips","type": "resource","stackable": True,  "value": 80, "equip_slot": None},
    "bronze_arrow": {
        "name": "Bronze Arrow", "type": "ammo", "stackable": True, "value": 3, "equip_slot": "ammo",
        "ammo_type": "arrow", "ranged_att": 1, "ranged_str": 1,
    },
    "iron_arrow": {
        "name": "Iron Arrow", "type": "ammo", "stackable": True, "value": 6, "equip_slot": "ammo",
        "ammo_type": "arrow", "ranged_att": 2, "ranged_str": 2,
    },
    "steel_arrow": {
        "name": "Steel Arrow", "type": "ammo", "stackable": True, "value": 14, "equip_slot": "ammo",
        "ammo_type": "arrow", "ranged_att": 3, "ranged_str": 3,
    },
    "mithril_arrow": {
        "name": "Mithril Arrow", "type": "ammo", "stackable": True, "value": 32, "equip_slot": "ammo",
        "ammo_type": "arrow", "ranged_att": 5, "ranged_str": 4,
    },
    "adamant_arrow": {
        "name": "Adamantite Arrow", "type": "ammo", "stackable": True, "value": 60, "equip_slot": "ammo",
        "ammo_type": "arrow", "ranged_att": 7, "ranged_str": 6,
    },
    # Equippable ammo pouch — holds up to QUIVER_CAPACITY of each arrow type; archery draws best first
    "arrow_quiver": {
        "name": "Arrow Quiver", "type": "armor", "stackable": False, "value": 50,
        "equip_slot": "ammo",
        "desc": "Holds up to 1000 of each arrow type. Equip it, then use arrows to load. Archery fires the best arrows first.",
    },
    # Inventory storage for smith'd arrowtips (used automatically when fletching)
    "arrowtip_box": {
        "name": "Arrowtip Box", "type": "tool", "stackable": False, "value": 40,
        "equip_slot": None,
        "desc": "Holds up to 200 of each arrowtip type. Use tips to pack them; fletching draws from the box first.",
    },
    "food_bag": {
        "name": "Food Bag", "type": "tool", "stackable": False, "value": 35,
        "equip_slot": None,
        "desc": "Holds up to 200 of each cooked fish. Pack fish into it; use the bag to eat (highest heal first).",
    },
    "raw_food_bag": {
        "name": "Raw Food Bag", "type": "tool", "stackable": False, "value": 35,
        "equip_slot": None,
        "desc": "Holds up to 200 of each raw fish. Cooking draws from the bag first.",
    },
    "mining_bag": {
        "name": "Mining Bag", "type": "tool", "stackable": False, "value": 45,
        "equip_slot": None,
        "desc": "Holds up to 200 of each ore and metal bar. Smelting and smithing draw from it first.",
    },
    "log_bag": {
        "name": "Log Bag", "type": "tool", "stackable": False, "value": 40,
        "equip_slot": None,
        "desc": "Holds up to 200 of each log type. Firemaking and fletching draw from it first.",
    },
    "fletch_pouch": {
        "name": "Fletching Pouch", "type": "tool", "stackable": False, "value": 40,
        "equip_slot": None,
        "desc": "Holds feathers, shafts, bowstring, and headless arrows (200 each). Fletching draws from it first.",
    },
    "potion_pouch": {
        "name": "Potion Pouch", "type": "tool", "stackable": False, "value": 40,
        "equip_slot": None,
        "desc": "Holds up to 200 of each potion (including health potions).",
    },
    "gem_bag": {
        "name": "Gem Bag", "type": "tool", "stackable": False, "value": 50,
        "equip_slot": None,
        "desc": "Holds up to 200 of each unset gem. Jewelry crafting at the anvil draws from it first.",
    },
    "shortbow": {
        "name": "Shortbow", "type": "weapon", "stackable": False, "value": 25, "equip_slot": "weapon",
        "weapon_type": "bow", "range": 4, "ranged_att": 8, "ranged_str": 8, "att_bonus": 0, "str_bonus": 0,
    },
    "oak_shortbow": {
        "name": "Oak Shortbow", "type": "weapon", "stackable": False, "value": 55, "equip_slot": "weapon",
        "weapon_type": "bow", "range": 4, "ranged_att": 14, "ranged_str": 14,
    },
    "willow_shortbow": {
        "name": "Willow Shortbow", "type": "weapon", "stackable": False, "value": 110, "equip_slot": "weapon",
        "weapon_type": "bow", "range": 5, "ranged_att": 20, "ranged_str": 20,
    },
    "maple_shortbow": {
        "name": "Maple Shortbow", "type": "weapon", "stackable": False, "value": 220, "equip_slot": "weapon",
        "weapon_type": "bow", "range": 5, "ranged_att": 28, "ranged_str": 28,
    },
    "yew_shortbow": {
        "name": "Yew Shortbow", "type": "weapon", "stackable": False, "value": 450, "equip_slot": "weapon",
        "weapon_type": "bow", "range": 6, "ranged_att": 38, "ranged_str": 38,
    },
    "magic_shortbow": {
        "name": "Magic Shortbow", "type": "weapon", "stackable": False, "value": 900, "equip_slot": "weapon",
        "weapon_type": "bow", "range": 7, "ranged_att": 50, "ranged_str": 50,
    },
    "unstrung_shortbow":      {"name": "Unstrung Shortbow",      "type": "resource", "stackable": False, "value": 8,  "equip_slot": None},
    "unstrung_oak_shortbow":  {"name": "Unstrung Oak Shortbow",  "type": "resource", "stackable": False, "value": 18, "equip_slot": None},
    "unstrung_willow_shortbow":{"name": "Unstrung Willow Shortbow","type": "resource","stackable": False, "value": 35, "equip_slot": None},
    "unstrung_maple_shortbow":{"name": "Unstrung Maple Shortbow","type": "resource", "stackable": False, "value": 70, "equip_slot": None},
    "unstrung_yew_shortbow":  {"name": "Unstrung Yew Shortbow",  "type": "resource", "stackable": False, "value": 150,"equip_slot": None},
    "unstrung_magic_shortbow":{"name": "Unstrung Magic Shortbow","type": "resource", "stackable": False, "value": 300,"equip_slot": None},
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
    "raw_trout":        {"name": "Raw Trout",          "type": "resource", "stackable": True, "value": 8,  "equip_slot": None},
    "raw_salmon":       {"name": "Raw Salmon",         "type": "resource", "stackable": True, "value": 14, "equip_slot": None},
    "raw_lobster":      {"name": "Raw Lobster",        "type": "resource", "stackable": True, "value": 22, "equip_slot": None},
    "raw_tuna":         {"name": "Raw Tuna",           "type": "resource", "stackable": True, "value": 28, "equip_slot": None},
    "raw_swordfish":    {"name": "Raw Swordfish",      "type": "resource", "stackable": True, "value": 45, "equip_slot": None},
    "cooked_shrimp":    {"name": "Cooked Shrimp",      "type": "food",     "stackable": True, "value": 5,  "equip_slot": None, "heal": 3},
    "cooked_sardine":   {"name": "Cooked Sardine",     "type": "food",     "stackable": True, "value": 7,  "equip_slot": None, "heal": 4},
    "cooked_trout":     {"name": "Cooked Trout",       "type": "food",     "stackable": True, "value": 16, "equip_slot": None, "heal": 7},
    "cooked_salmon":    {"name": "Cooked Salmon",      "type": "food",     "stackable": True, "value": 28, "equip_slot": None, "heal": 9},
    "cooked_lobster":   {"name": "Cooked Lobster",     "type": "food",     "stackable": True, "value": 45, "equip_slot": None, "heal": 12},
    "cooked_tuna":      {"name": "Cooked Tuna",        "type": "food",     "stackable": True, "value": 55, "equip_slot": None, "heal": 10},
    "cooked_swordfish": {"name": "Cooked Swordfish",   "type": "food",     "stackable": True, "value": 85, "equip_slot": None, "heal": 14},
    "burnt_shrimp":     {"name": "Burnt Shrimp",       "type": "food",     "stackable": True, "value": 1,  "equip_slot": None, "heal": 0},
    "burnt_sardine":    {"name": "Burnt Sardine",      "type": "food",     "stackable": True, "value": 1,  "equip_slot": None, "heal": 0},
    "burnt_trout":      {"name": "Burnt Trout",        "type": "food",     "stackable": True, "value": 1,  "equip_slot": None, "heal": 0},
    "burnt_salmon":     {"name": "Burnt Salmon",       "type": "food",     "stackable": True, "value": 1,  "equip_slot": None, "heal": 0},
    "burnt_lobster":    {"name": "Burnt Lobster",      "type": "food",     "stackable": True, "value": 1,  "equip_slot": None, "heal": 0},
    "burnt_tuna":       {"name": "Burnt Tuna",         "type": "food",     "stackable": True, "value": 1,  "equip_slot": None, "heal": 0},
    "burnt_swordfish":  {"name": "Burnt Swordfish",    "type": "food",     "stackable": True, "value": 1,  "equip_slot": None, "heal": 0},
    "bread":            {"name": "Bread",              "type": "food",     "stackable": True, "value": 6,  "equip_slot": None, "heal": 5},
    "health_potion":    {"name": "Health Potion",      "type": "food",     "stackable": True, "value": 25, "equip_slot": None, "heal": 12},
    # Mad Scientist combat elixirs — temporary level boosts (seconds)
    "attack_potion":    {"name": "Attack Potion",      "type": "potion", "stackable": True, "value": 40,  "equip_slot": None,
                         "boost_skill": "attack", "boost_amount": 10, "boost_seconds": 60},
    "strength_potion":  {"name": "Strength Potion",    "type": "potion", "stackable": True, "value": 40,  "equip_slot": None,
                         "boost_skill": "strength", "boost_amount": 10, "boost_seconds": 60},
    "defence_potion":   {"name": "Defence Potion",     "type": "potion", "stackable": True, "value": 40,  "equip_slot": None,
                         "boost_skill": "defence", "boost_amount": 10, "boost_seconds": 60},
    "super_attack_potion":   {"name": "Super Attack Potion",   "type": "potion", "stackable": True, "value": 120, "equip_slot": None,
                              "boost_skill": "attack", "boost_amount": 20, "boost_seconds": 60},
    "super_strength_potion": {"name": "Super Strength Potion", "type": "potion", "stackable": True, "value": 120, "equip_slot": None,
                              "boost_skill": "strength", "boost_amount": 20, "boost_seconds": 60},
    "super_defence_potion":  {"name": "Super Defence Potion",  "type": "potion", "stackable": True, "value": 120, "equip_slot": None,
                              "boost_skill": "defence", "boost_amount": 20, "boost_seconds": 60},

    "rat_tail":         {"name": "Giant Rat Tail",     "type": "quest",  "stackable": True,  "value": 0, "equip_slot": None},
    "spider_silk":      {"name": "Spider Silk",        "type": "misc",   "stackable": True,  "value": 4, "equip_slot": None},
    "bones":            {"name": "Bones",              "type": "misc",   "stackable": True,  "value": 1, "equip_slot": None, "karma_xp": 18},
    "big_bones":        {"name": "Big Bones",          "type": "misc",   "stackable": True,  "value": 3, "equip_slot": None, "karma_xp": 54},
    "dragon_bones":     {"name": "Dragon Bones",       "type": "misc",   "stackable": True,  "value": 12, "equip_slot": None, "karma_xp": 144},
    # --- Cut gems (stackable drops — set into jewelry at the anvil) ---
    "opal": {
        "name": "Opal", "type": "gem", "stackable": True, "value": 15, "equip_slot": None,
        "desc": "Milky gem. Anvil + bronze bar → Opal jewelry.", "gem_color": (230, 220, 200),
    },
    "jade": {
        "name": "Jade", "type": "gem", "stackable": True, "value": 25, "equip_slot": None,
        "desc": "Smooth green stone. Anvil + bronze bar → Jade jewelry.", "gem_color": (70, 160, 90),
    },
    "topaz": {
        "name": "Topaz", "type": "gem", "stackable": True, "value": 40, "equip_slot": None,
        "desc": "Warm amber crystal. Anvil + bronze bar → Topaz jewelry.", "gem_color": (220, 150, 50),
    },
    "sapphire": {
        "name": "Sapphire", "type": "gem", "stackable": True, "value": 70, "equip_slot": None,
        "desc": "Deep blue gem. Anvil + iron bar → Sapphire jewelry.", "gem_color": (50, 90, 210),
    },
    "emerald": {
        "name": "Emerald", "type": "gem", "stackable": True, "value": 110, "equip_slot": None,
        "desc": "Vivid green. Anvil + iron bar → Emerald jewelry.", "gem_color": (40, 170, 90),
    },
    "ruby": {
        "name": "Ruby", "type": "gem", "stackable": True, "value": 160, "equip_slot": None,
        "desc": "Blood-red gem. Anvil + steel bar → Ruby jewelry.", "gem_color": (200, 40, 50),
    },
    "diamond": {
        "name": "Diamond", "type": "gem", "stackable": True, "value": 280, "equip_slot": None,
        "desc": "Hard white brilliance. Anvil + mithril bar → Diamond jewelry.", "gem_color": (220, 235, 255),
    },
    "onyx": {
        "name": "Onyx", "type": "gem", "stackable": True, "value": 450, "equip_slot": None,
        "desc": "Void-black gem. Anvil + adamantite bar → Onyx jewelry.", "gem_color": (30, 28, 40),
    },

    # --- Rings ---
    "gold_ring": {
        "name": "Gold Ring", "type": "jewelry", "stackable": False, "value": 40,
        "equip_slot": "ring", "att_bonus": 1, "str_bonus": 0, "def_bonus": 0,
        "desc": "A plain gold band. Craftable from a bronze bar.",
        "gem_color": (230, 190, 60),
    },
    "opal_ring": {
        "name": "Opal Ring", "type": "jewelry", "stackable": False, "value": 55,
        "equip_slot": "ring", "att_bonus": 2, "str_bonus": 0, "def_bonus": 0,
        "ranged_att": 2,
        "desc": "Light accuracy polish for melee and archery.",
        "gem_color": (230, 220, 200),
    },
    "jade_ring": {
        "name": "Jade Ring", "type": "jewelry", "stackable": False, "value": 70,
        "equip_slot": "ring", "att_bonus": 0, "str_bonus": 0, "def_bonus": 3,
        "desc": "A sturdy green band that favours defence.",
        "gem_color": (70, 160, 90),
    },
    "topaz_ring": {
        "name": "Topaz Ring", "type": "jewelry", "stackable": False, "value": 85,
        "equip_slot": "ring", "att_bonus": 1, "str_bonus": 3, "def_bonus": 0,
        "desc": "Amber fire — a touch of extra strength.",
        "gem_color": (220, 150, 50),
    },
    "sapphire_ring": {
        "name": "Sapphire Ring", "type": "jewelry", "stackable": False, "value": 180,
        "equip_slot": "ring", "att_bonus": 4, "str_bonus": 1, "def_bonus": 0,
        "ranged_att": 3,
        "desc": "Improves melee and ranged accuracy.",
        "gem_color": (50, 90, 210),
    },
    "emerald_ring": {
        "name": "Emerald Ring", "type": "jewelry", "stackable": False, "value": 260,
        "equip_slot": "ring", "att_bonus": 2, "str_bonus": 5, "def_bonus": 1,
        "ability": "lifesteal", "ability_value": 0.08,
        "desc": "Sustain ring — best early lifesteal.",
        "gem_color": (40, 170, 90),
    },
    "ruby_ring": {
        "name": "Ruby Ring", "type": "jewelry", "stackable": False, "value": 340,
        "equip_slot": "ring", "att_bonus": 3, "str_bonus": 7, "def_bonus": 0,
        "ability": "crit", "ability_value": 0.10, "ability_mult": 1.6,
        "desc": "Crit specialist — highest crit chance in the game.",
        "gem_color": (200, 40, 50),
    },
    "diamond_ring": {
        "name": "Diamond Ring", "type": "jewelry", "stackable": False, "value": 480,
        "equip_slot": "ring", "att_bonus": 6, "str_bonus": 4, "def_bonus": 4,
        "ability": "dodge", "ability_value": 0.08,
        "desc": "Evasion ring — pairs well with a thorns amulet.",
        "gem_color": (220, 235, 255),
    },
    "onyx_ring": {
        "name": "Onyx Ring", "type": "jewelry", "stackable": False, "value": 900,
        "equip_slot": "ring", "att_bonus": 10, "str_bonus": 8, "def_bonus": 4,
        "ability": "lifesteal", "ability_value": 0.10,
        "ability2": "crit", "ability2_value": 0.06, "ability2_mult": 1.5,
        "desc": "Hybrid sustain + crit. Void Ring is stronger overall.",
        "gem_color": (30, 28, 40),
    },
    "void_ring": {
        "name": "Void Ring", "type": "jewelry", "stackable": False, "value": 1600,
        "equip_slot": "ring", "att_bonus": 14, "str_bonus": 12, "def_bonus": 6,
        "ability": "void_strike", "ability_value": 5,
        "ability2": "lifesteal", "ability2_value": 0.12,
        "desc": "Endgame ring — flat damage and strong lifesteal. Drop only.",
        "gem_color": (90, 40, 160),
    },

    # --- Amulets ---
    "bronze_amulet": {
        "name": "Bronze Amulet", "type": "jewelry", "stackable": False, "value": 35,
        "equip_slot": "amulet", "att_bonus": 2, "str_bonus": 2, "def_bonus": 1,
        "desc": "A simple cast-bronze charm.",
        "gem_color": (180, 120, 60),
    },
    "opal_amulet": {
        "name": "Opal Amulet", "type": "jewelry", "stackable": False, "value": 60,
        "equip_slot": "amulet", "att_bonus": 2, "str_bonus": 1, "def_bonus": 1,
        "ranged_att": 1,
        "desc": "Starter charm with a hint of accuracy.",
        "gem_color": (230, 220, 200),
    },
    "jade_amulet": {
        "name": "Jade Amulet", "type": "jewelry", "stackable": False, "value": 75,
        "equip_slot": "amulet", "att_bonus": 1, "str_bonus": 1, "def_bonus": 3,
        "regen_hp": 1, "regen_seconds": 6,
        "desc": "Slow passive regen while worn.",
        "gem_color": (70, 160, 90),
    },
    "topaz_amulet": {
        "name": "Topaz Amulet", "type": "jewelry", "stackable": False, "value": 90,
        "equip_slot": "amulet", "att_bonus": 2, "str_bonus": 3, "def_bonus": 1,
        "desc": "Warm stone that favours raw power.",
        "gem_color": (220, 150, 50),
    },
    "sapphire_amulet": {
        "name": "Sapphire Amulet", "type": "jewelry", "stackable": False, "value": 220,
        "equip_slot": "amulet", "att_bonus": 5, "str_bonus": 2, "def_bonus": 2,
        "ranged_att": 4, "ranged_str": 2,
        "desc": "Favours accurate strikes and archery.",
        "gem_color": (50, 90, 210),
    },
    "emerald_amulet": {
        "name": "Emerald Amulet", "type": "jewelry", "stackable": False, "value": 300,
        "equip_slot": "amulet", "att_bonus": 2, "str_bonus": 3, "def_bonus": 6,
        "regen_hp": 1, "regen_seconds": 4,
        "ability": "lifesteal", "ability_value": 0.05,
        "desc": "Defence + mild sustain. Good until Onyx/Void.",
        "gem_color": (40, 170, 90),
    },
    "ruby_amulet": {
        "name": "Ruby Amulet", "type": "jewelry", "stackable": False, "value": 380,
        "equip_slot": "amulet", "att_bonus": 3, "str_bonus": 6, "def_bonus": 2,
        "ability": "thorns", "ability_value": 0.25,
        "desc": "Thorns specialist — reflect damage to attackers.",
        "gem_color": (200, 40, 50),
    },
    "diamond_amulet": {
        "name": "Diamond Amulet", "type": "jewelry", "stackable": False, "value": 560,
        "equip_slot": "amulet", "att_bonus": 6, "str_bonus": 6, "def_bonus": 6,
        "regen_hp": 1, "regen_seconds": 3,
        "ability": "dodge", "ability_value": 0.05,
        "desc": "Balanced stats with regen and light dodge.",
        "gem_color": (220, 235, 255),
    },
    "onyx_amulet": {
        "name": "Onyx Amulet", "type": "jewelry", "stackable": False, "value": 1100,
        "equip_slot": "amulet", "att_bonus": 10, "str_bonus": 10, "def_bonus": 8,
        "regen_hp": 2, "regen_seconds": 3,
        "ability": "lifesteal", "ability_value": 0.08,
        "desc": "Strong regen + lifesteal. Void Amulet is the endgame upgrade.",
        "gem_color": (30, 28, 40),
    },
    "void_amulet": {
        "name": "Void Amulet", "type": "jewelry", "stackable": False, "value": 2000,
        "equip_slot": "amulet", "att_bonus": 14, "str_bonus": 14, "def_bonus": 12,
        "regen_hp": 2, "regen_seconds": 2.5,
        "ability": "void_ward", "ability_value": 3,
        "ability2": "lifesteal", "ability2_value": 0.10,
        "desc": "Endgame amulet — damage reduction and lifesteal. Drop only.",
        "gem_color": (90, 40, 160),
    },
    "lost_locket": {
        "name": "Lost Locket", "type": "quest", "stackable": False, "value": 0, "equip_slot": None,
        "desc": "A silver locket with a cracked sapphire. Lira the Jeweler is looking for this.",
    },

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
        "name": "Green Dragon (Lv 50)", "type": "pet", "stackable": False, "value": 65000, "equip_slot": None,
        "pet_id": "dragon_pet", "tradeable": False, "sellable": False,
    },
    "pet_dragon_crimson": {
        "name": "Crimson Dragon (Lv 65)", "type": "pet", "stackable": False, "value": 180000, "equip_slot": None,
        "pet_id": "dragon_crimson", "tradeable": False, "sellable": False,
    },
    "pet_dragon_frost": {
        "name": "Frost Dragon (Lv 75)", "type": "pet", "stackable": False, "value": 450000, "equip_slot": None,
        "pet_id": "dragon_frost", "tradeable": False, "sellable": False,
    },
    "pet_dragon_shadow": {
        "name": "Shadow Dragon (Lv 85)", "type": "pet", "stackable": False, "value": 900000, "equip_slot": None,
        "pet_id": "dragon_shadow", "tradeable": False, "sellable": False,
    },
    "pet_dragon_mythic": {
        "name": "Mythic Dragon (Lv 99)", "type": "pet", "stackable": False, "value": 2000000, "equip_slot": None,
        "pet_id": "dragon_mythic", "tradeable": False, "sellable": False,
    },
}

STARTER_INVENTORY = [
    ("bronze_sword", 1),
    ("bronze_axe", 1),
    ("bronze_pickaxe", 1),
    ("small_fishing_net", 1),
    ("tinderbox", 1),
    ("knife", 1),
    ("bread", 3),
    ("coins", 25),
]

# Logs that can be lit with a tinderbox → temporary campfire.
# duration = ticks the fire lasts; level_req / xp = Firemaking.
FIRE_LOGS = {
    "logs": {"duration": 50, "level_req": 1, "xp": 40},
    "oak_logs": {"duration": 80, "level_req": 15, "xp": 60},
    "willow_logs": {"duration": 100, "level_req": 25, "xp": 90},
    "maple_logs": {"duration": 120, "level_req": 40, "xp": 135},
    "yew_logs": {"duration": 150, "level_req": 55, "xp": 200},
    "magic_logs": {"duration": 180, "level_req": 70, "xp": 300},
}

# Wood types usable by Fletching (knife carving / stringing).
FLETCH_LOGS = {
    "logs": {"tier": "normal", "shaft_qty": 15},
    "oak_logs": {"tier": "oak", "shaft_qty": 20},
    "willow_logs": {"tier": "willow", "shaft_qty": 25},
    "maple_logs": {"tier": "maple", "shaft_qty": 30},
    "yew_logs": {"tier": "yew", "shaft_qty": 35},
    "magic_logs": {"tier": "magic", "shaft_qty": 40},
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
            ("cooked_shrimp", 0.35, (1, 1)),
            ("bread", 0.12, (1, 1)),
            ("opal", 0.10, (1, 1)),
            ("bronze_amulet", 0.02, (1, 1)),
            ("opal_ring", 0.015, (1, 1)),
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
            ("feather", 0.45, (1, 4)),
            ("bronze_arrow", 0.18, (2, 8)),
            ("cooked_shrimp", 0.30, (1, 2)),
            ("bread", 0.22, (1, 1)),
            (("opal", "jade"), 0.12, (1, 1)),
            ("gold_ring", 0.03, (1, 1)),
            ("bronze_amulet", 0.04, (1, 1)),
            (("opal_ring", "jade_ring", "jade_amulet"), 0.03, (1, 1)),
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
            ("feather", 0.25, (2, 6)),
            ("iron_arrow", 0.15, (3, 10)),
            ("cooked_sardine", 0.28, (1, 2)),
            ("bread", 0.20, (1, 1)),
            (("jade", "topaz", "sapphire"), 0.10, (1, 1)),
            ("sapphire_ring", 0.02, (1, 1)),
            ("sapphire_amulet", 0.015, (1, 1)),
            (("topaz_ring", "topaz_amulet", "opal_amulet"), 0.035, (1, 1)),
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
            ("bread", 0.35, (1, 2)),
            ("cooked_sardine", 0.25, (1, 2)),
            ("health_potion", 0.08, (1, 1)),
            (("topaz", "sapphire", "emerald"), 0.12, (1, 1)),
            ("emerald_ring", 0.03, (1, 1)),
            ("emerald_amulet", 0.025, (1, 1)),
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
            ("bread", 0.30, (1, 2)),
            ("health_potion", 0.10, (1, 1)),
            (("sapphire", "emerald"), 0.12, (1, 1)),
            ("sapphire_ring", 0.04, (1, 1)),
            ("emerald_amulet", 0.03, (1, 1)),
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
            ("feather", 0.70, (3, 12)),
            ("mithril_arrow", 0.20, (5, 15)),
            ("mithril_ore", 0.18, (1, 2)),
            (("mithril_dagger", "mithril_sword", "mithril_helmet"), 0.08, (1, 1)),
            ("health_potion", 0.18, (1, 1)),
            ("bread", 0.25, (1, 2)),
            ("cooked_sardine", 0.20, (1, 2)),
            (("emerald", "ruby"), 0.14, (1, 1)),
            ("ruby_ring", 0.035, (1, 1)),
            ("ruby_amulet", 0.03, (1, 1)),
        ],
        "wander_radius": 4, "aggro_range": 7,
    },
    # Adamantite lair boss — tough for ~level 50 combat
    "dragon": {
        "name": "Adamant Dragon", "level": 78, "hp": 200, "attack": 90, "strength": 155, "defence": 80,
        "def_bonus": 50, "xp": 650, "respawn_ticks": 120,
        "drops": [
            ("dragon_bones", 1.0, (1, 1)),
            ("coins", 1.0, (250, 900)),
            ("adamantite_ore", 0.55, (1, 3)),
            ("adamantite_bar", 0.12, (1, 1)),
            ("mythos_dagger", 0.10, (1, 1)),       # 1 in 10
            ("mythos_longsword", 0.02, (1, 1)),    # 1 in 50
            ("mythos_helmet", 0.015, (1, 1)),      # 1 in ~67
            ("mythos_legs", 0.012, (1, 1)),        # 1 in ~83
            ("mythos_shield", 0.012, (1, 1)),      # 1 in ~83
            ("mythos_body", 0.01, (1, 1)),         # 1 in 100 armour
            ("health_potion", 0.40, (1, 2)),
            ("bread", 0.35, (2, 4)),
            (("ruby", "diamond"), 0.22, (1, 2)),
            ("diamond_ring", 0.06, (1, 1)),
            ("diamond_amulet", 0.05, (1, 1)),
            ("onyx", 0.04, (1, 1)),
        ],
        "wander_radius": 3, "aggro_range": 8,
    },
    # Mountain pass — packs of wolves guarding the route to the harbour
    "wolf": {
        "name": "Wolf", "level": 40, "hp": 62, "attack": 32, "strength": 34, "defence": 28,
        "def_bonus": 10, "xp": 145, "respawn_ticks": 40,
        "drops": [
            ("bones", 1.0, (1, 1)),
            ("coins", 0.90, (18, 55)),
            ("cooked_trout", 0.22, (1, 1)),
            ("raw_trout", 0.18, (1, 1)),
            ("health_potion", 0.08, (1, 1)),
            (("topaz", "sapphire", "emerald"), 0.10, (1, 1)),
            ("emerald_ring", 0.025, (1, 1)),
        ],
        "wander_radius": 4, "aggro_range": 6,
    },
    # Stonehaven City — peaceful until attacked
    "guard": {
        "name": "City Guard", "level": 28, "hp": 55, "attack": 20, "strength": 20, "defence": 26,
        "def_bonus": 28, "xp": 120, "respawn_ticks": 45,
        "drops": [
            ("bones", 1.0, (1, 1)),
            ("coins", 0.95, (25, 70)),
            ("steel_helmet", 0.08, (1, 1)),
            ("steel_body", 0.04, (1, 1)),
            ("steel_legs", 0.04, (1, 1)),
            ("steel_shield", 0.06, (1, 1)),
            ("steel_longsword", 0.05, (1, 1)),
            ("bread", 0.35, (1, 2)),
            ("health_potion", 0.12, (1, 1)),
            (("sapphire", "emerald"), 0.08, (1, 1)),
            ("sapphire_amulet", 0.03, (1, 1)),
        ],
        "wander_radius": 3, "wander_ticks": 10, "wander_chance": 0.4,
        "patrol_steps": (1, 3),  # short street beat, then idle
        "aggro_range": 0,  # peaceful unless you attack — short street patrol
    },
    "knight": {
        "name": "Castle Knight", "level": 48, "hp": 100, "attack": 38, "strength": 40, "defence": 42,
        "def_bonus": 40, "xp": 260, "respawn_ticks": 60,
        "drops": [
            ("bones", 1.0, (1, 1)),
            ("coins", 0.95, (60, 160)),
            ("adamant_helmet", 0.05, (1, 1)),
            ("adamant_body", 0.03, (1, 1)),
            ("adamant_legs", 0.03, (1, 1)),
            ("adamant_sword", 0.04, (1, 1)),
            ("adamant_shield", 0.04, (1, 1)),
            ("health_potion", 0.22, (1, 1)),
            ("bread", 0.30, (1, 2)),
            (("emerald", "ruby", "diamond"), 0.12, (1, 1)),
            ("ruby_ring", 0.04, (1, 1)),
            ("ruby_amulet", 0.035, (1, 1)),
            ("diamond_amulet", 0.02, (1, 1)),
        ],
        "wander_radius": 4, "wander_ticks": 8, "wander_chance": 0.5,
        "patrol_steps": (2, 4),  # walk a short leg around the keep, then idle
        "aggro_range": 0,  # peaceful unless you attack
    },
    "mythos_champion": {
        "name": "Mythos Champion", "level": 90, "hp": 280, "attack": 95, "strength": 100, "defence": 98,
        "def_bonus": 70, "xp": 850, "respawn_ticks": 120,
        "drops": [
            ("bones", 1.0, (1, 1)),
            ("coins", 1.0, (300, 900)),
            (("mythos_dagger", "mythos_helmet"), 0.06, (1, 1)),
            (("mythos_legs", "mythos_shield"), 0.04, (1, 1)),
            ("mythos_longsword", 0.03, (1, 1)),
            ("mythos_body", 0.02, (1, 1)),
            ("super_attack_potion", 0.25, (1, 2)),
            ("super_strength_potion", 0.25, (1, 2)),
            ("super_defence_potion", 0.25, (1, 2)),
            ("health_potion", 0.45, (2, 3)),
            (("diamond", "onyx"), 0.18, (1, 2)),
            ("diamond_ring", 0.07, (1, 1)),
            ("onyx_ring", 0.04, (1, 1)),
            ("onyx_amulet", 0.035, (1, 1)),
        ],
        "wander_radius": 2, "wander_ticks": 14, "wander_chance": 0.3,
        "patrol_steps": (1, 2),
        "aggro_range": 0,  # peaceful unless you attack — mostly stands post
    },
    # Void Sanctum (SE mystical dungeon) — high-level rooms
    "shade": {
        "name": "Shade", "level": 55, "hp": 110, "attack": 48, "strength": 50, "defence": 40,
        "def_bonus": 18, "xp": 260, "respawn_ticks": 50,
        "drops": [
            ("bones", 1.0, (1, 1)),
            ("coins", 0.95, (60, 160)),
            ("mithril_arrow", 0.25, (8, 20)),
            ("health_potion", 0.22, (1, 1)),
            ("super_attack_potion", 0.06, (1, 1)),
            (("sapphire", "emerald", "ruby"), 0.14, (1, 1)),
            ("ruby_ring", 0.03, (1, 1)),
            ("emerald_amulet", 0.03, (1, 1)),
        ],
        "wander_radius": 3, "aggro_range": 7,
    },
    "crypt_ghoul": {
        "name": "Crypt Ghoul", "level": 62, "hp": 135, "attack": 55, "strength": 58, "defence": 48,
        "def_bonus": 22, "xp": 310, "respawn_ticks": 55,
        "drops": [
            ("bones", 1.0, (1, 1)),
            ("coins", 0.95, (80, 200)),
            ("mithril_ore", 0.20, (1, 2)),
            (("mithril_sword", "mithril_helmet", "mithril_chainbody"), 0.08, (1, 1)),
            ("health_potion", 0.25, (1, 2)),
            (("emerald", "ruby", "diamond"), 0.15, (1, 1)),
            ("diamond_ring", 0.03, (1, 1)),
            ("ruby_amulet", 0.04, (1, 1)),
        ],
        "wander_radius": 3, "aggro_range": 7,
    },
    "void_imp": {
        "name": "Void Imp", "level": 70, "hp": 150, "attack": 65, "strength": 68, "defence": 52,
        "def_bonus": 24, "xp": 380, "respawn_ticks": 55,
        "drops": [
            ("bones", 1.0, (1, 1)),
            ("coins", 0.95, (100, 260)),
            ("adamantite_ore", 0.12, (1, 1)),
            ("super_strength_potion", 0.08, (1, 1)),
            ("feather", 0.60, (4, 14)),
            (("ruby", "diamond", "onyx"), 0.16, (1, 1)),
            ("diamond_amulet", 0.04, (1, 1)),
            ("onyx_ring", 0.025, (1, 1)),
        ],
        "wander_radius": 4, "aggro_range": 8,
    },
    "obsidian_colossus": {
        "name": "Obsidian Colossus", "level": 78, "hp": 190, "attack": 72, "strength": 78, "defence": 85,
        "def_bonus": 40, "xp": 480, "respawn_ticks": 70,
        "drops": [
            ("big_bones", 1.0, (1, 1)),
            ("coins", 0.95, (140, 360)),
            ("adamantite_ore", 0.28, (1, 2)),
            ("adamantite_bar", 0.08, (1, 1)),
            ("super_defence_potion", 0.10, (1, 1)),
            ("health_potion", 0.30, (1, 2)),
            (("diamond", "onyx"), 0.18, (1, 1)),
            ("onyx_amulet", 0.035, (1, 1)),
            ("onyx_ring", 0.03, (1, 1)),
        ],
        "wander_radius": 2, "aggro_range": 6,
    },
    "shadow_knight": {
        "name": "Shadow Knight", "level": 88, "hp": 230, "attack": 95, "strength": 100, "defence": 90,
        "def_bonus": 48, "xp": 620, "respawn_ticks": 80,
        "drops": [
            ("bones", 1.0, (1, 1)),
            ("coins", 1.0, (200, 500)),
            (("mythos_dagger", "mythos_helmet"), 0.04, (1, 1)),
            ("adamantite_bar", 0.10, (1, 1)),
            ("super_attack_potion", 0.12, (1, 1)),
            ("super_strength_potion", 0.12, (1, 1)),
            ("health_potion", 0.35, (1, 2)),
            ("onyx", 0.14, (1, 2)),
            ("onyx_ring", 0.05, (1, 1)),
            ("onyx_amulet", 0.045, (1, 1)),
            ("void_ring", 0.015, (1, 1)),
        ],
        "wander_radius": 3, "aggro_range": 8,
    },
    "void_horror": {
        "name": "Void Horror", "level": 95, "hp": 320, "attack": 115, "strength": 125, "defence": 105,
        "def_bonus": 55, "xp": 900, "respawn_ticks": 140,
        "drops": [
            ("dragon_bones", 1.0, (1, 1)),
            ("coins", 1.0, (400, 1200)),
            ("adamantite_bar", 0.25, (1, 2)),
            ("mythos_longsword", 0.03, (1, 1)),
            ("mythos_body", 0.02, (1, 1)),
            ("mythos_shield", 0.025, (1, 1)),
            # Future: ("eclipse_shield", 0.01, (1, 1)),  # Eclipse Aegis — not enabled yet
            # Future: ("eclipse_body", 0.008, (1, 1)),
            # Future: ("eclipse_legs", 0.008, (1, 1)),
            # Future: ("eclipse_helmet", 0.01, (1, 1)),
            ("super_attack_potion", 0.20, (1, 2)),
            ("super_strength_potion", 0.20, (1, 2)),
            ("super_defence_potion", 0.20, (1, 2)),
            ("health_potion", 0.50, (2, 3)),
            ("onyx", 0.28, (1, 3)),
            ("void_ring", 0.06, (1, 1)),
            ("void_amulet", 0.05, (1, 1)),
            ("onyx_amulet", 0.08, (1, 1)),
        ],
        "wander_radius": 3, "aggro_range": 9,
    },
    # Emberdeep instance visuals (spawned only inside the private dungeon)
    "magma_slug": {
        "name": "Magma Slug", "level": 22, "hp": 48, "attack": 18, "strength": 18, "defence": 16,
        "def_bonus": 8, "xp": 90, "respawn_ticks": 40,
        "drops": [("coins", 0.9, (20, 60)), ("topaz", 0.08, (1, 1))],
        "wander_radius": 2, "aggro_range": 5,
    },
    "ash_imp": {
        "name": "Ash Imp", "level": 38, "hp": 70, "attack": 32, "strength": 30, "defence": 26,
        "def_bonus": 12, "xp": 160, "respawn_ticks": 45,
        "drops": [("coins", 0.95, (40, 100)), ("sapphire", 0.10, (1, 1)), ("health_potion", 0.2, (1, 1))],
        "wander_radius": 3, "aggro_range": 6,
    },
    "ember_wolf": {
        "name": "Ember Wolf", "level": 58, "hp": 110, "attack": 48, "strength": 50, "defence": 40,
        "def_bonus": 18, "xp": 280, "respawn_ticks": 50,
        "drops": [("bones", 1.0, (1, 1)), ("coins", 0.95, (80, 180)), ("ruby", 0.10, (1, 1))],
        "wander_radius": 3, "aggro_range": 7,
    },
    "magma_knight": {
        "name": "Magma Knight", "level": 78, "hp": 180, "attack": 72, "strength": 75, "defence": 70,
        "def_bonus": 40, "xp": 520, "respawn_ticks": 70,
        "drops": [
            ("bones", 1.0, (1, 1)), ("coins", 1.0, (150, 400)),
            ("adamant_sword", 0.05, (1, 1)), ("ruby", 0.14, (1, 1)), ("diamond", 0.06, (1, 1)),
        ],
        "wander_radius": 2, "aggro_range": 8,
    },
    "crucible_beast": {
        "name": "Crucible Beast", "level": 88, "hp": 260, "attack": 90, "strength": 95, "defence": 85,
        "def_bonus": 55, "xp": 780, "respawn_ticks": 100,
        "drops": [
            ("bones", 1.0, (1, 1)), ("coins", 1.0, (300, 800)),
            ("diamond", 0.18, (1, 2)), ("onyx", 0.08, (1, 1)),
            ("mythos_dagger", 0.04, (1, 1)),
        ],
        "wander_radius": 2, "aggro_range": 9,
    },
}

# Fixed monster spawn points: (monster_type, x, y)
MONSTER_SPAWNS = [
    ("giant_rat", 10, 42), ("giant_rat", 18, 46), ("giant_rat", 8, 50),
    ("giant_rat", 24, 42), ("giant_rat", 6, 44), ("giant_rat", 16, 54),
    # Upper dungeon — goblins (more packed)
    ("goblin", 44, 42), ("goblin", 48, 40), ("goblin", 42, 44),
    ("goblin", 62, 40), ("goblin", 66, 42), ("goblin", 58, 44),
    ("goblin", 42, 54), ("goblin", 46, 56), ("goblin", 50, 52),
    ("goblin", 58, 54), ("goblin", 64, 54), ("goblin", 68, 58),
    ("goblin", 48, 58), ("goblin", 60, 48),
    # Upper dungeon — skeletons
    ("skeleton", 64, 40), ("skeleton", 68, 44), ("skeleton", 60, 54),
    ("skeleton", 44, 56), ("skeleton", 50, 58), ("skeleton", 66, 58),
    ("skeleton", 50, 42), ("skeleton", 46, 40), ("skeleton", 54, 54),
    ("skeleton", 62, 56), ("skeleton", 42, 52), ("skeleton", 70, 52),
    # Deep dungeon — giants
    ("giant", 60, 70), ("giant", 64, 72), ("giant", 62, 76),
    ("giant", 66, 78), ("giant", 61, 74),
    # Mithril cavern — big skeletons
    ("big_skeleton", 44, 88), ("big_skeleton", 48, 90), ("big_skeleton", 42, 94),
    ("big_skeleton", 50, 92), ("big_skeleton", 46, 96),
    # Spider nest — mid-late dungeon
    ("spider", 60, 82), ("spider", 64, 83), ("spider", 68, 82),
    ("spider", 62, 84), ("spider", 66, 84), ("spider", 60, 84),
    ("spider", 68, 83),
    # Adamantite lair — dragon
    ("dragon", 62, 94),
    # Mountain pass — wolves (patrol clearings along the pass)
    ("wolf", 108, 16), ("wolf", 112, 13), ("wolf", 114, 16),
    ("wolf", 118, 16), ("wolf", 120, 18), ("wolf", 116, 15),
    ("wolf", 110, 17), ("wolf", 122, 16),
    # Stonehaven City — guards on the streets, knights by the castle
    ("guard", 90, 56), ("guard", 96, 60), ("guard", 102, 56),
    ("guard", 86, 50), ("guard", 94, 64), ("guard", 112, 62),
    ("guard", 100, 68), ("guard", 88, 62),
    ("knight", 108, 50), ("knight", 112, 48), ("knight", 106, 46),
    ("knight", 110, 52), ("knight", 114, 50),
    ("mythos_champion", 110, 48),  # Castle elite — full Mythos set
    # Void Sanctum — SE mystical dungeon (6 rooms, high level)
    ("shade", 126, 85), ("shade", 129, 87), ("shade", 131, 84),
    ("crypt_ghoul", 138, 85), ("crypt_ghoul", 142, 87), ("crypt_ghoul", 144, 84),
    ("void_imp", 126, 92), ("void_imp", 129, 94), ("void_imp", 131, 91), ("void_imp", 128, 95),
    ("obsidian_colossus", 138, 92), ("obsidian_colossus", 142, 94), ("obsidian_colossus", 144, 91),
    ("shadow_knight", 126, 100), ("shadow_knight", 129, 102), ("shadow_knight", 131, 99),
    ("void_horror", 140, 100), ("void_horror", 143, 102),
]

# ---------------------------------------------------------------------------
# RESOURCE NODES (position -> type). Populated procedurally in world_map.py
# but the yield tables live here.
# ---------------------------------------------------------------------------
RESOURCE_YIELDS = {
    "tree":       {"skill": "woodcutting", "level_req": 1,  "xp": 12, "item": "logs",        "respawn_ticks": 6,  "depletion_chance": 0.20},
    "oak_tree":   {"skill": "woodcutting", "level_req": 10, "xp": 30, "item": "oak_logs",     "respawn_ticks": 10, "depletion_chance": 0.15},
    "willow_tree":{"skill": "woodcutting", "level_req": 20, "xp": 45, "item": "willow_logs",  "respawn_ticks": 14, "depletion_chance": 0.14},
    "maple_tree": {"skill": "woodcutting", "level_req": 35, "xp": 70, "item": "maple_logs",   "respawn_ticks": 20, "depletion_chance": 0.12},
    "yew_tree":   {"skill": "woodcutting", "level_req": 50, "xp": 110,"item": "yew_logs",     "respawn_ticks": 30, "depletion_chance": 0.10},
    "magic_tree": {"skill": "woodcutting", "level_req": 70, "xp": 180,"item": "magic_logs",   "respawn_ticks": 45, "depletion_chance": 0.08},
    "copper_rock":{"skill": "mining",      "level_req": 1,  "xp": 15, "item": "copper_ore",  "respawn_ticks": 8,  "depletion_chance": 0.20},
    "tin_rock":   {"skill": "mining",      "level_req": 1,  "xp": 15, "item": "tin_ore",     "respawn_ticks": 8,  "depletion_chance": 0.20},
    "iron_rock":  {"skill": "mining",      "level_req": 12, "xp": 35, "item": "iron_ore",    "respawn_ticks": 14, "depletion_chance": 0.15},
    "coal_rock":  {"skill": "mining",      "level_req": 20, "xp": 40, "item": "coal",        "respawn_ticks": 12, "depletion_chance": 0.18},
    "mithril_rock":{"skill": "mining",     "level_req": 55, "xp": 80, "item": "mithril_ore", "respawn_ticks": 18, "depletion_chance": 0.16},
    "adamantite_rock":{"skill": "mining",  "level_req": 70, "xp": 110,"item": "adamantite_ore","respawn_ticks": 22, "depletion_chance": 0.14},
    "fishing_spot_shrimp":  {
        "skill": "fishing", "level_req": 1,  "xp": 10, "item": "raw_shrimp",
        "respawn_ticks": 5, "depletion_chance": 0.0,
        "tools": ["small_fishing_net"], "cast": "You cast your net...",
    },
    "fishing_spot_sardine": {
        "skill": "fishing", "level_req": 5,  "xp": 18, "item": "raw_sardine",
        "respawn_ticks": 6, "depletion_chance": 0.0,
        "tools": ["small_fishing_net", "fishing_rod"], "cast": "You cast your net...",
    },
    "fishing_spot_trout": {
        "skill": "fishing", "level_req": 20, "xp": 40, "item": "raw_trout",
        "respawn_ticks": 7, "depletion_chance": 0.0,
        "tools": ["fishing_rod"], "cast": "You cast your line...",
    },
    "fishing_spot_salmon": {
        "skill": "fishing", "level_req": 30, "xp": 58, "item": "raw_salmon",
        "respawn_ticks": 8, "depletion_chance": 0.0,
        "tools": ["fly_fishing_rod"], "cast": "You cast a fly...",
    },
    "fishing_spot_lobster": {
        "skill": "fishing", "level_req": 40, "xp": 75, "item": "raw_lobster",
        "respawn_ticks": 9, "depletion_chance": 0.05,
        "tools": ["lobster_pot"], "cast": "You lower a lobster pot...",
    },
    "fishing_spot_tuna": {
        "skill": "fishing", "level_req": 35, "xp": 70, "item": "raw_tuna",
        "respawn_ticks": 9, "depletion_chance": 0.0,
        "tools": ["harpoon"], "cast": "You ready your harpoon...",
    },
    "fishing_spot_swordfish": {
        "skill": "fishing", "level_req": 50, "xp": 100, "item": "raw_swordfish",
        "respawn_ticks": 10, "depletion_chance": 0.0,
        "tools": ["harpoon"], "cast": "You ready your harpoon...",
    },
}

# ---------------------------------------------------------------------------
# NPCS
# ---------------------------------------------------------------------------
NPCS = [
    # Village
    {"id": "shopkeeper_joe", "name": "Shopkeeper Joe", "x": 27, "y": 6,
     "lines": ["Welcome to my general store!", "Take a look at my stock."], "shop_id": "general_store"},

    {"id": "jeweler_lira", "name": "Lira the Jeweler", "x": 33, "y": 8,
     "lines": [
         "Rings, amulets, and unset gems — press B to browse.",
         "I stock everyday pieces. Rubies, diamonds, onyx and void jewelry you'll have to find yourself.",
         "I'll buy any jewelry or gems you bring, rare included — just not for a king's ransom.",
         "Need a Gem Bag? It packs unset stones so your pack stays clear for the anvil.",
     ],
     "shop_id": "jewelry_shop", "quest_id": "liras_lost_locket"},

    {"id": "fletcher_elena", "name": "Fletcher Elena", "x": 64, "y": 18,
     "lines": [
         "Welcome to my bow shop! Press B to browse bows, arrows, and supplies.",
         "Fletching: chop logs → use a knife (N) to carve shafts or an unstrung bow.",
         "Shafts + feathers = headless arrows; add smith'd arrowtips = arrows.",
         "String an unstrung bow with bowstring, equip the bow + arrows, then fight with Archery.",
     ],
     "shop_id": "fletcher_shop",
     "quest_id": "elena_archery_lesson",
     "starter_kit": True},

    {"id": "blacksmith_gareth", "name": "Blacksmith Gareth", "x": 56, "y": 8,
     "lines": [
         "Welcome to my smithy! Furnace for smelting, anvil for smithing.",
         "Mine iron and coal in the deep dungeon, smelt steel bars, then smith steel gear here.",
         "I buy ores, bars, weapons and armour — open the shop to buy or sell.",
     ],
     "shop_id": "blacksmith_shop", "quest_id": "ore_for_the_forge", "forge": True},

    {"id": "banker_iris", "name": "Banker Iris", "x": 38, "y": 16,
     "lines": [
         "Welcome to the Village Bank.",
         "Store coins and items here. Purse max 65,000 — vault holds 10 million coins.",
         "Click the bank booth (or talk to me) to open your bank.",
     ],
     "bank": True},

    {"id": "elder_miriam", "name": "Elder Miriam", "x": 7, "y": 5,
     "lines": [
         "The rats in the mine have gotten out of hand. Could you thin their numbers?",
         "Those giant rats leave tails behind — bring me a handful and I'll pay extra.",
     ],
     "quest_ids": ["rat_problem", "rat_tails"]},

    {"id": "farmer_tom", "name": "Farmer Tom", "x": 27, "y": 27,
     "lines": ["My daughter Mia wandered off into the forest and hasn't come back!"],
     "quest_id": "lost_child"},

    {"id": "innkeeper_sarah", "name": "Innkeeper Sarah", "x": 7, "y": 27,
     "lines": [
         "Rooms are full up, but stay a while and rest your feet.",
         "Cook your catch on the hearth — raw fish won't restore your health.",
         "Bring me a platter of cooked trout for the evening rush and I'll tip you well.",
     ],
     "quest_id": "inn_special"},

    {"id": "guard_marcus", "name": "Guard Marcus", "x": 30, "y": 4,
     "lines": [
         "Halt! ...just kidding, welcome to the village.",
         "Stay safe out in the wilds.",
         "Goblins keep spilling from the dungeon. Thin eight of them for the watch.",
     ],
     "quest_id": "goblin_watch"},

    {"id": "guard_aldric", "name": "Guard Aldric", "x": 22, "y": 35,
     "lines": ["Keep an eye out — the mine mouth is just south of here."]},

    {"id": "village_kid_timmy", "name": "Timmy", "x": 28, "y": 22,
     "lines": ["Wanna race? ...no? Okay."]},

    {"id": "village_idiot_bob", "name": "Bob", "x": 5, "y": 17,
     "lines": ["I once punched a goblin. It hurt. A lot. Don't recommend it."]},

    {"id": "priest_cedric", "name": "Priest Cedric", "x": 5, "y": 6,
     "lines": [
         "May your travels be safe. If you're ever low on health, a meal will do you good.",
         "The fallen leave bones. Bring me a stack and I'll bless your karma.",
     ],
     "quest_id": "blessed_bones"},

    {"id": "monk_healer", "name": "Monk Alaric", "x": 36, "y": 24,
     "lines": ["Peace be with you, traveler."]},

    # Forest / lake
    {"id": "old_fisherman_pete", "name": "Old Fisherman Pete", "x": 78, "y": 16,
     "lines": ["Bring me some fresh shrimp and I'll teach you a thing or two about fishing."],
     "quest_id": "fishermans_request"},

    {"id": "mia", "name": "Mia", "x": 74, "y": 8,
     "lines": ["I'm lost! I want to go home to my dad in the village."],
     "quest_target_for": "lost_child"},

    {"id": "mysterious_traveler", "name": "Mysterious Traveler", "x": 64, "y": 8,
     "lines": ["The goblins in the dungeon wear strange mail. Bring me a piece and I'll make it worth your while."],
     "quest_id": "the_mysterious_traveler"},

    {"id": "merchant_wanderer", "name": "Wandering Merchant", "x": 68, "y": 22,
     "lines": ["Bah, I've got nothing to sell you today. Come back later."]},

    {"id": "pet_keeper_luna", "name": "Pet Keeper Luna", "x": 55, "y": 27,
     "lines": [
         "Welcome to the Pet Emporium!",
         "Companions follow you and fight when monsters attack.",
         "Cat 10c · Husky 1k · Skeleton 10k · Green Dragon 65k",
         "Higher dragons: Crimson 180k · Frost 450k · Shadow 900k · Mythic 2M (Lv 99)",
         "Bank coins can pay for expensive pets — purse max is 65,000.",
     ],
     "shop_id": "pet_shop"},

    # Mine / dungeon fringe
    {"id": "mine_scout", "name": "Scout Elena", "x": 22, "y": 39,
     "lines": [
         "Rats down there. Lots of rats. And ore, if you're brave.",
         "Deeper still — a spider nest. Bring me their silk and I'll pay well.",
     ],
     "quest_id": "silk_harvest"},

    {"id": "dungeon_hermit", "name": "Hermit Cole", "x": 40, "y": 52,
     "lines": [
         "Skeletons hunt by sight — only two will pile on you at once.",
         "Clear a dozen of those rattling fools and I'll tip you for it.",
         "Deeper south: iron, coal, and giants. Bring me their big bones.",
         "Past the mithril bones lies a spider nest — harder than big skeletons, softer than the dragon.",
         "Prove yourself against the adamant dragon — one set of dragon bones will do.",
     ],
     "quest_ids": ["bone_and_blade", "giants_tithe", "adamant_proof"]},

    {"id": "mad_scientist", "name": "Mad Scientist", "x": 70, "y": 22,
     "lines": [
         "Behold! Potions of pure combat potential!",
         "Regular doses raise Attack, Strength or Defence by 10 for one minute.",
         "My SUPER formulae push them by 20 — then the effect wears off completely.",
         "Don't ask what I put in them. Buy. Drink. Dominate.",
         "The Void Sanctum has shades — then ghouls, imps, and worse. Fetch me samples!",
     ],
     "shop_id": "potion_lab",
     "quest_ids": ["void_samples", "void_crypt", "void_imps", "sanctum_apex"]},

    # Mountain pass / fishing village
    {"id": "pass_scout", "name": "Scout Bren", "x": 104, "y": 16,
     "lines": [
         "The mountain pass leads east to Harbourreach.",
         "Wolves hunt those rocks — combat around forty. Pack food.",
         "Thin the packs for me and I'll make it worth your while.",
     ],
     "quest_id": "wolves_on_the_pass"},
    {"id": "tackle_merchant", "name": "Marina the Angler", "x": 138, "y": 9,
     "lines": [
         "Welcome to Harbourreach Tackle!",
         "Nets for shrimp, rods for trout, fly rods for salmon,",
         "lobster pots for the pots, and harpoons for the deep.",
         "Higher fish need higher Fishing — and the right gear.",
     ],
     "shop_id": "harbour_tackle"},
    {"id": "fishmonger_kai", "name": "Fishmonger Kai", "x": 138, "y": 23,
     "lines": [
         "Catch it raw, cook it here on the hearth.",
         "Trout, salmon, lobster, tuna, swordfish — the pier has them all.",
         "I buy spare catch if your pack is full.",
     ],
     "shop_id": "harbour_fishmonger"},
    {"id": "harbour_cook", "name": "Cook Nell", "x": 136, "y": 23,
     "lines": [
         "Use the harbour hearth to cook your catch.",
         "Burnt fish is still fish — just worse.",
         "I need cooked lobsters for a feast — ten will do.",
     ],
     "quest_id": "harbour_feast"},

    # Stonehaven City
    {"id": "herald_rowan", "name": "Herald Rowan", "x": 110, "y": 47,
     "lines": [
         "Welcome to Stonehaven Keep.",
         "The City Guard keeps the plazas safe — leave them be and they'll leave you be.",
         "Knights of the Keep patrol the courtyard. Strike first and they answer in steel.",
         "The throne hall is open to travellers. Mind your manners.",
         "Still — if you can best six guards, then the knights, then our champion… the Keep will notice.",
     ],
     "quest_ids": ["city_watch", "knights_of_the_keep", "champions_challenge"]},
    {"id": "city_vendor_mira", "name": "Mira the Vendor", "x": 96, "y": 58,
     "lines": [
         "Fresh bread and travel kits from the market square! Press B to browse.",
         "I stock food, potions, and a few steel scraps for travellers heading to the keep.",
         "Stonehaven's gates open south and west — castle keep sits to the north.",
     ],
     "shop_id": "stonehaven_market"},
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
            "knife": {"price": 8, "qty": 10},
            "small_fishing_net": {"price": 10, "qty": 5},
            "bronze_axe": {"price": 15, "qty": 5},
            "bronze_pickaxe": {"price": 15, "qty": 5},
            "health_potion": {"price": 25, "qty": 8},
            "feather": {"price": 3, "qty": 50},
            "bow_string": {"price": 12, "qty": 30},
            "log_bag": {"price": 40, "qty": 10},
            "mining_bag": {"price": 45, "qty": 8},
            "gem_bag": {"price": 50, "qty": 8},
            "potion_pouch": {"price": 40, "qty": 8},
        },
        "buys": True,  # will buy anything from the player at 40% of value
    },
    "fletcher_shop": {
        "name": "Elena's Bow Shop",
        "stock": {
            "knife": {"price": 8, "qty": 20},
            "bow_string": {"price": 12, "qty": 100},
            "feather": {"price": 3, "qty": 250},
            "arrow_shaft": {"price": 2, "qty": 150},
            "bronze_arrowtips": {"price": 6, "qty": 80},
            "iron_arrowtips": {"price": 12, "qty": 40},
            "shortbow": {"price": 30, "qty": 12},
            "oak_shortbow": {"price": 90, "qty": 6},
            "willow_shortbow": {"price": 180, "qty": 4},
            "bronze_arrow": {"price": 4, "qty": 400},
            "iron_arrow": {"price": 8, "qty": 200},
            "steel_arrow": {"price": 16, "qty": 100},
            "arrow_quiver": {"price": 50, "qty": 15},
            "arrowtip_box": {"price": 40, "qty": 15},
            "fletch_pouch": {"price": 40, "qty": 15},
            "log_bag": {"price": 40, "qty": 10},
            "logs": {"price": 5, "qty": 40},
            "oak_logs": {"price": 15, "qty": 20},
        },
        "buys": True,
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
            "bronze_arrowtips": {"price": 6, "qty": 40},
            "iron_arrowtips": {"price": 12, "qty": 25},
            "mining_bag": {"price": 45, "qty": 10},
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
            "pet_dragon_crimson": {"price": 180000, "qty": 99},
            "pet_dragon_frost": {"price": 450000, "qty": 99},
            "pet_dragon_shadow": {"price": 900000, "qty": 99},
            "pet_dragon_mythic": {"price": 2000000, "qty": 99},
        },
        "buys": False,
    },
    "potion_lab": {
        "name": "Mad Scientist's Lab",
        "stock": {
            "attack_potion": {"price": 40, "qty": 30},
            "strength_potion": {"price": 40, "qty": 30},
            "defence_potion": {"price": 40, "qty": 30},
            "super_attack_potion": {"price": 120, "qty": 20},
            "super_strength_potion": {"price": 120, "qty": 20},
            "super_defence_potion": {"price": 120, "qty": 20},
            "health_potion": {"price": 25, "qty": 15},
            "potion_pouch": {"price": 40, "qty": 12},
        },
        "buys": False,
    },
    "harbour_tackle": {
        "name": "Harbourreach Tackle",
        "stock": {
            "small_fishing_net": {"price": 10, "qty": 20},
            "fishing_rod": {"price": 45, "qty": 15},
            "fly_fishing_rod": {"price": 90, "qty": 12},
            "lobster_pot": {"price": 120, "qty": 10},
            "harpoon": {"price": 160, "qty": 10},
            "tinderbox": {"price": 5, "qty": 10},
            "raw_food_bag": {"price": 35, "qty": 15},
        },
        "buys": False,
    },
    "harbour_fishmonger": {
        "name": "Kai's Catch",
        "stock": {
            "cooked_shrimp": {"price": 6, "qty": 20},
            "cooked_trout": {"price": 18, "qty": 15},
            "cooked_salmon": {"price": 32, "qty": 12},
            "cooked_lobster": {"price": 50, "qty": 8},
            "bread": {"price": 6, "qty": 20},
            "health_potion": {"price": 25, "qty": 10},
            "food_bag": {"price": 35, "qty": 15},
            "raw_food_bag": {"price": 35, "qty": 10},
        },
        "buys": True,
    },
    "stonehaven_market": {
        "name": "Mira's Market Stall",
        "stock": {
            "bread": {"price": 6, "qty": 40},
            "cooked_trout": {"price": 18, "qty": 20},
            "cooked_salmon": {"price": 32, "qty": 12},
            "health_potion": {"price": 25, "qty": 20},
            "tinderbox": {"price": 5, "qty": 10},
            "knife": {"price": 8, "qty": 8},
            "food_bag": {"price": 35, "qty": 10},
            "potion_pouch": {"price": 40, "qty": 8},
            "steel_longsword": {"price": 180, "qty": 3},
            "steel_sq_shield": {"price": 120, "qty": 3},
            "steel_helmet": {"price": 90, "qty": 3},
            "bronze_arrow": {"price": 4, "qty": 100},
            "iron_arrow": {"price": 8, "qty": 60},
            "feather": {"price": 3, "qty": 40},
            "bow_string": {"price": 12, "qty": 20},
        },
        "buys": True,
    },
    "jewelry_shop": {
        "name": "Lira's Jewelry",
        # Common only — no ruby / diamond / onyx / void (those stay drop/craft)
        "stock": {
            "gold_ring": {"price": 50, "qty": 12},
            "bronze_amulet": {"price": 45, "qty": 12},
            "opal_ring": {"price": 70, "qty": 8},
            "opal_amulet": {"price": 75, "qty": 8},
            "jade_ring": {"price": 90, "qty": 6},
            "jade_amulet": {"price": 95, "qty": 6},
            "topaz_ring": {"price": 110, "qty": 5},
            "topaz_amulet": {"price": 115, "qty": 5},
            "sapphire_ring": {"price": 220, "qty": 4},
            "sapphire_amulet": {"price": 260, "qty": 4},
            "emerald_ring": {"price": 320, "qty": 3},
            "emerald_amulet": {"price": 360, "qty": 3},
            # Unset commons for anvil crafting
            "opal": {"price": 20, "qty": 20},
            "jade": {"price": 32, "qty": 16},
            "topaz": {"price": 50, "qty": 12},
            "sapphire": {"price": 90, "qty": 8},
            "emerald": {"price": 140, "qty": 6},
            "gem_bag": {"price": 50, "qty": 12},
        },
        "buys": True,
        "buys_types": ("jewelry", "gem"),
        "buys_slots": ("ring", "amulet"),
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
        "quest_points": 1,
        "rewards": {"coins": 50, "xp": {"attack": 30}},
    },
    "lost_child": {
        "name": "Lost Child",
        "giver": "farmer_tom",
        "description": "Find Mia in the forest and speak to her, then return to Farmer Tom.",
        "type": "find_npc", "target": "mia",
        "quest_points": 1,
        "rewards": {"coins": 75},
    },
    "fishermans_request": {
        "name": "Fisherman's Request",
        "giver": "old_fisherman_pete",
        "description": "Catch 10 Raw Shrimp and bring them to Old Fisherman Pete.",
        "type": "collect", "target": "raw_shrimp", "count": 10,
        "quest_points": 2,
        "rewards": {"coins": 40, "xp": {"fishing": 50}},
    },
    "ore_for_the_forge": {
        "name": "Ore for the Forge",
        "giver": "blacksmith_gareth",
        "description": "Mine 5 Copper Ore and 5 Tin Ore for Blacksmith Gareth.",
        "type": "collect_multi", "targets": {"copper_ore": 5, "tin_ore": 5},
        "quest_points": 2,
        "rewards": {"coins": 20, "item": ("bronze_sword", 1)},
    },
    "the_mysterious_traveler": {
        "name": "The Mysterious Traveler",
        "giver": "mysterious_traveler",
        "description": "Defeat a Goblin, loot its mail, and bring it back.",
        "type": "collect", "target": "goblin_mail", "count": 1,
        "quest_points": 2,
        "rewards": {"coins": 60, "item": ("gold_ring", 1)},
    },
    "elena_archery_lesson": {
        "name": "Elena's Archery Lesson",
        "giver": "fletcher_elena",
        "description": "Talk to Fletcher Elena (east of the village) to learn fletching and claim a free bow kit.",
        "type": "gift",
        "quest_points": 1,
        "rewards": {
            "items": [
                ("knife", 1),
                ("logs", 5),
                ("feather", 40),
                ("bow_string", 3),
                ("arrow_shaft", 30),
                ("bronze_arrowtips", 30),
                ("shortbow", 1),
                ("bronze_arrow", 50),
                ("arrow_quiver", 1),
                ("arrowtip_box", 1),
            ],
            "xp": {"fletching": 25, "archery": 25},
        },
    },
    "liras_lost_locket": {
        "name": "Lira's Lost Locket",
        "giver": "jeweler_lira",
        "description": "Find Lira's Lost Locket near the wishing well (south of the crossroads) and return it. She'll thank you with a Gem Bag and a few stones.",
        "type": "collect", "target": "lost_locket", "count": 1,
        "quest_points": 1,
        "rewards": {
            "coins": 40,
            "items": [("gem_bag", 1), ("opal", 3), ("sapphire", 1)],
            "xp": {"smithing": 20},
        },
    },
    # Mid-game — unlock Flame Lash (15) through Chain Bolt (30)
    "wolves_on_the_pass": {
        "name": "Wolves on the Pass",
        "giver": "pass_scout",
        "description": "Thin the wolf packs on the mountain pass — kill 8 Wolves, then return to Scout Bren.",
        "type": "kill", "target": "wolf", "count": 8,
        "quest_points": 3,
        "rewards": {"coins": 120, "xp": {"attack": 80, "hitpoints": 40}},
    },
    "bone_and_blade": {
        "name": "Bone and Blade",
        "giver": "dungeon_hermit",
        "description": "Clear the upper dungeon — kill 12 Skeletons and report to Hermit Cole.",
        "type": "kill", "target": "skeleton", "count": 12,
        "quest_points": 3,
        "rewards": {"coins": 150, "xp": {"defence": 100}, "item": ("health_potion", 3)},
    },
    "harbour_feast": {
        "name": "Harbour Feast",
        "giver": "harbour_cook",
        "description": "Cook 10 Lobsters on a hearth and bring them to Cook Nell in Harbourreach.",
        "type": "collect", "target": "cooked_lobster", "count": 10,
        "quest_points": 3,
        "rewards": {"coins": 90, "xp": {"cooking": 120, "fishing": 60}},
    },
    "city_watch": {
        "name": "City Watch",
        "giver": "herald_rowan",
        "description": "Herald Rowan needs proof you can handle Stonehaven steel — defeat 6 City Guards (they fight back).",
        "type": "kill", "target": "guard", "count": 6,
        "quest_points": 4,
        "rewards": {"coins": 200, "xp": {"strength": 120, "defence": 80}},
    },
    "silk_harvest": {
        "name": "Silk Harvest",
        "giver": "mine_scout",
        "description": "Hunt the spider nest deep in the dungeon — bring Scout Elena 8 Spider Silk.",
        "type": "collect", "target": "spider_silk", "count": 8,
        "quest_points": 4,
        "rewards": {"coins": 180, "xp": {"attack": 100}, "item": ("super_defence_potion", 1)},
    },
    "void_samples": {
        "name": "Void Samples",
        "giver": "mad_scientist",
        "description": "Slay 8 Shades in the Void Sanctum and return to the Mad Scientist.",
        "type": "kill", "target": "shade", "count": 8,
        "quest_points": 4,
        "rewards": {
            "coins": 250,
            "xp": {"hitpoints": 150},
            "items": [("super_attack_potion", 2), ("health_potion", 5)],
        },
    },
    "rat_tails": {
        "name": "Rat Tails",
        "giver": "elder_miriam",
        "description": "Collect 5 Giant Rat Tails from the mine rats and return to Elder Miriam.",
        "type": "collect", "target": "rat_tail", "count": 5,
        "requires": "rat_problem",
        "quest_points": 2,
        "rewards": {"coins": 60, "xp": {"attack": 40}, "item": ("health_potion", 2)},
    },
    "inn_special": {
        "name": "Inn Special",
        "giver": "innkeeper_sarah",
        "description": "Cook 8 Trout and bring them to Innkeeper Sarah.",
        "type": "collect", "target": "cooked_trout", "count": 8,
        "quest_points": 2,
        "rewards": {"coins": 50, "xp": {"cooking": 80}},
    },
    "goblin_watch": {
        "name": "Goblin Watch",
        "giver": "guard_marcus",
        "description": "Help the village watch — kill 8 Goblins in the upper dungeon, then report to Guard Marcus.",
        "type": "kill", "target": "goblin", "count": 8,
        "quest_points": 2,
        "rewards": {"coins": 70, "xp": {"defence": 50}},
    },
    "blessed_bones": {
        "name": "Blessed Bones",
        "giver": "priest_cedric",
        "description": "Bring Priest Cedric 12 Bones from fallen foes for a blessing.",
        "type": "collect", "target": "bones", "count": 12,
        "quest_points": 2,
        "rewards": {"coins": 40, "xp": {"karma": 100}},
    },
    "giants_tithe": {
        "name": "Giant's Tithe",
        "giver": "dungeon_hermit",
        "description": "Hunt the dungeon giants — bring Hermit Cole 8 Big Bones.",
        "type": "collect", "target": "big_bones", "count": 8,
        "requires": "bone_and_blade",
        "quest_points": 5,
        "rewards": {"coins": 200, "xp": {"strength": 120, "hitpoints": 80}},
    },
    "adamant_proof": {
        "name": "Adamant Proof",
        "giver": "dungeon_hermit",
        "description": "Slay the Adamant Dragon and bring Hermit Cole 1 Dragon Bones.",
        "type": "collect", "target": "dragon_bones", "count": 1,
        "requires": "giants_tithe",
        "quest_points": 6,
        "rewards": {"coins": 400, "xp": {"attack": 200, "defence": 150}, "item": ("super_strength_potion", 2)},
    },
    "knights_of_the_keep": {
        "name": "Knights of the Keep",
        "giver": "herald_rowan",
        "description": "Defeat 5 Castle Knights in Stonehaven (they fight back), then return to Herald Rowan.",
        "type": "kill", "target": "knight", "count": 5,
        "requires": "city_watch",
        "quest_points": 5,
        "rewards": {"coins": 280, "xp": {"defence": 160, "strength": 100}},
    },
    "champions_challenge": {
        "name": "Champion's Challenge",
        "giver": "herald_rowan",
        "description": "Defeat the Mythos Champion in the castle courtyard, then report to Herald Rowan.",
        "type": "kill", "target": "mythos_champion", "count": 1,
        "requires": "knights_of_the_keep",
        "quest_points": 6,
        "rewards": {"coins": 500, "xp": {"attack": 200, "hitpoints": 150}, "item": ("super_defence_potion", 2)},
    },
    "void_crypt": {
        "name": "Void Crypt",
        "giver": "mad_scientist",
        "description": "Cull 6 Crypt Ghouls in the Void Sanctum and return to the Mad Scientist.",
        "type": "kill", "target": "crypt_ghoul", "count": 6,
        "requires": "void_samples",
        "quest_points": 5,
        "rewards": {"coins": 320, "xp": {"hitpoints": 180}, "item": ("super_attack_potion", 2)},
    },
    "void_imps": {
        "name": "Impish Samples",
        "giver": "mad_scientist",
        "description": "Slay 6 Void Imps deeper in the Sanctum and return with the news.",
        "type": "kill", "target": "void_imp", "count": 6,
        "requires": "void_crypt",
        "quest_points": 5,
        "rewards": {"coins": 360, "xp": {"hitpoints": 200}, "items": [("super_strength_potion", 1), ("health_potion", 5)]},
    },
    "sanctum_apex": {
        "name": "Sanctum Apex",
        "giver": "mad_scientist",
        "description": "Defeat a Void Horror in the Sanctum depths, then report to the Mad Scientist.",
        "type": "kill", "target": "void_horror", "count": 1,
        "requires": "void_imps",
        "quest_points": 8,
        "rewards": {
            "coins": 750,
            "xp": {"hitpoints": 300, "attack": 200},
            "items": [("super_attack_potion", 3), ("super_defence_potion", 3), ("health_potion", 10)],
        },
    },
}

# ---------------------------------------------------------------------------
# QUEST MAGIC — abilities unlocked by quest points (not a leveled skill)
# ---------------------------------------------------------------------------
# Manual casts use MANUAL_MAGIC_CD_FACTOR of the listed cooldown (faster than auto).
# Starter quests ≈ 9 QP; mid-game quests add ~21 QP (total ≈ 30 → Chain Bolt).
MANUAL_MAGIC_CD_FACTOR = 0.70

MAGIC_ABILITIES = {
    "spark": {
        "name": "Spark",
        "desc": "A crackling jolt of lightning.",
        "quest_points": 1,
        "effect": "lightning",
        "damage": 8,
        "freeze": 0.0,
        "cooldown": 7.0,
    },
    "ember": {
        "name": "Ember",
        "desc": "Scorch the foe with a burst of flame.",
        "quest_points": 3,
        "effect": "fire",
        "damage": 12,
        "freeze": 0.0,
        "cooldown": 9.0,
    },
    "frost_bind": {
        "name": "Frost Bind",
        "desc": "Ice roots — the enemy cannot strike for a short time.",
        "quest_points": 6,
        "effect": "freeze",
        "damage": 4,
        "freeze": 2.4,
        "cooldown": 12.0,
    },
    "thunderclap": {
        "name": "Thunderclap",
        "desc": "A heavier lightning strike.",
        "quest_points": 9,
        "effect": "lightning",
        "damage": 18,
        "freeze": 0.0,
        "cooldown": 11.0,
    },
    "flame_lash": {
        "name": "Flame Lash",
        "desc": "A whip of searing fire.",
        "quest_points": 15,
        "effect": "fire",
        "damage": 24,
        "freeze": 0.0,
        "cooldown": 13.0,
    },
    "ice_prison": {
        "name": "Ice Prison",
        "desc": "Encased in ice — no attacks for several seconds.",
        "quest_points": 22,
        "effect": "freeze",
        "damage": 10,
        "freeze": 3.6,
        "cooldown": 16.0,
    },
    "chain_bolt": {
        "name": "Chain Bolt",
        "desc": "Forked lightning that hits hard.",
        "quest_points": 30,
        "effect": "lightning",
        "damage": 34,
        "freeze": 0.0,
        "cooldown": 14.0,
    },
    "pyroclasm": {
        "name": "Pyroclasm",
        "desc": "An eruption of combat fire magic.",
        "quest_points": 42,
        "effect": "fire",
        "damage": 44,
        "freeze": 0.0,
        "cooldown": 17.0,
    },
    "blizzard": {
        "name": "Blizzard",
        "desc": "Biting cold — damage and a long freeze.",
        "quest_points": 55,
        "effect": "freeze",
        "damage": 18,
        "freeze": 5.0,
        "cooldown": 20.0,
    },
    "tempest": {
        "name": "Tempest",
        "desc": "Storm and flame together — the pinnacle of quest magic.",
        "quest_points": 75,
        "effect": "lightning",
        "damage": 58,
        "freeze": 1.8,
        "cooldown": 24.0,
    },
}

# Ordered for auto-cast priority (strongest unlocked ready ability first)
MAGIC_ABILITY_ORDER = (
    "tempest", "blizzard", "pyroclasm", "chain_bolt", "ice_prison",
    "flame_lash", "thunderclap", "frost_bind", "ember", "spark",
)

XP_SKILLS = [
    "attack", "strength", "defence", "hitpoints", "archery",
    "woodcutting", "mining", "fishing", "cooking", "firemaking", "smithing", "fletching", "karma",
]

# Skills that contribute to combat level (classic RS melee/ranged formula, no prayer).
COMBAT_SKILLS = ("attack", "strength", "defence", "hitpoints", "archery")

SKILL_DISPLAY_NAMES = {
    "attack": "Attack", "strength": "Strength", "defence": "Defence",
    "hitpoints": "Hitpoints", "archery": "Archery",
    "woodcutting": "Woodcutting", "mining": "Mining",
    "fishing": "Fishing", "cooking": "Cooking", "firemaking": "Firemaking",
    "smithing": "Smithing", "fletching": "Fletching", "karma": "Karma",
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
    if slot_name == "amulet":
        return {"att_bonus": L // 6, "str_bonus": L // 6, "def_bonus": L // 5}
    if slot_name == "ring":
        return {"att_bonus": L // 5, "str_bonus": L // 5, "def_bonus": L // 8}
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
        "name": "Green Dragon", "level": 50, "sprite": "pet_dragon",
        "hp": 120, "attack": 55, "strength": 62, "defence": 48, "def_bonus": 20,
    },
    "dragon_crimson": {
        "name": "Crimson Dragon", "level": 65, "sprite": "pet_dragon_crimson",
        "hp": 165, "attack": 72, "strength": 80, "defence": 62, "def_bonus": 28,
    },
    "dragon_frost": {
        "name": "Frost Dragon", "level": 75, "sprite": "pet_dragon_frost",
        "hp": 200, "attack": 88, "strength": 95, "defence": 78, "def_bonus": 36,
    },
    "dragon_shadow": {
        "name": "Shadow Dragon", "level": 85, "sprite": "pet_dragon_shadow",
        "hp": 250, "attack": 105, "strength": 115, "defence": 95, "def_bonus": 45,
    },
    "dragon_mythic": {
        "name": "Mythic Dragon", "level": 99, "sprite": "pet_dragon_mythic",
        "hp": 320, "attack": 130, "strength": 145, "defence": 120, "def_bonus": 60,
    },
}

# Economy / inventory caps
MAX_PURSE_COINS = 65000
MAX_BANK_COINS = 10_000_000
MAX_ORES = 100
ORE_ITEM_IDS = frozenset({
    "copper_ore", "tin_ore", "iron_ore", "coal", "mithril_ore", "adamantite_ore",
})
BAR_ITEM_IDS = frozenset({
    "bronze_bar", "iron_bar", "steel_bar", "mithril_bar", "adamantite_bar",
})
# Inventory pages (skill-related). Flat slot index = tab_index * TAB_SIZE + local.
INVENTORY_TAB_SIZE = 24
INVENTORY_TABS = (
    {"id": "general", "label": "Gen"},    # gear, tools, food, potions, misc
    {"id": "gather", "label": "Gath"},    # ores, logs, raw fish
    {"id": "craft", "label": "Craft"},    # bars, fletch mats, tips, unstrung
    {"id": "bags", "label": "Bags"},      # storage bags & pouches only
)
INVENTORY_SIZE = INVENTORY_TAB_SIZE * len(INVENTORY_TABS)  # 96
BANK_SLOTS = 96
QUIVER_CAPACITY = 1000  # max of each arrow type stored in an equipped Arrow Quiver
TIP_BOX_CAPACITY = 200  # max of each arrowtip type stored in an Arrowtip Box
FOOD_BAG_CAPACITY = 200  # max of each cooked fish type in a Food Bag
RAW_BAG_CAPACITY = 200  # max of each raw fish type in a Raw Food Bag
RESOURCE_BAG_CAPACITY = 200  # mining / log / fletch / potion / gem bags

# Inventory "Bags" tab — containers only (not their contents)
STORAGE_BAG_IDS = frozenset({
    "arrow_quiver", "arrowtip_box",
    "food_bag", "raw_food_bag",
    "mining_bag", "log_bag",
    "fletch_pouch", "potion_pouch",
    "gem_bag",
})

RAW_FISH_IDS = frozenset({
    "raw_shrimp", "raw_sardine", "raw_trout", "raw_salmon",
    "raw_lobster", "raw_tuna", "raw_swordfish",
})
COOKED_FISH_IDS = frozenset({
    "cooked_shrimp", "cooked_sardine", "cooked_trout", "cooked_salmon",
    "cooked_lobster", "cooked_tuna", "cooked_swordfish",
})
FLETCH_POUCH_IDS = frozenset({
    "feather", "arrow_shaft", "bow_string", "headless_arrow",
})


def is_arrowtip(item_id):
    return bool(item_id) and str(item_id).endswith("arrowtips")


def is_raw_fish(item_id):
    return item_id in RAW_FISH_IDS


def is_cooked_fish(item_id):
    return item_id in COOKED_FISH_IDS


def is_mining_bag_item(item_id):
    return item_id in ORE_ITEM_IDS or item_id in BAR_ITEM_IDS


def is_log_item(item_id):
    return item_id in FIRE_LOGS


def is_fletch_pouch_item(item_id):
    return item_id in FLETCH_POUCH_IDS


def is_potion_item(item_id):
    item = ITEMS.get(item_id) or {}
    if item.get("type") == "potion":
        return True
    return item_id == "health_potion"


def is_gem_item(item_id):
    """Unset cut gems only (not jewelry)."""
    return (ITEMS.get(item_id) or {}).get("type") == "gem"


def is_storage_bag(item_id):
    """True for inventory bag/pouch/box/quiver containers (Bags tab)."""
    return item_id in STORAGE_BAG_IDS


def inventory_tab_for_item(item_id):
    """Preferred inventory tab index for auto-placing a new stack (not armour/weapons)."""
    if is_storage_bag(item_id):
        return 3  # Bags — containers only
    item = ITEMS.get(item_id) or {}
    slot = item.get("equip_slot")
    # Worn gear always prefers General so combat loadouts stay together
    if slot in ("weapon", "shield", "body", "legs", "helmet", "amulet", "ring", "ammo"):
        return 0
    if is_log_item(item_id) or is_raw_fish(item_id) or item_id in ORE_ITEM_IDS:
        return 1
    if (
        item_id in BAR_ITEM_IDS
        or is_arrowtip(item_id) or is_fletch_pouch_item(item_id)
        or str(item_id).startswith("unstrung_")
        or item_id in ("knife",)
    ):
        return 2
    # Food, potions, bones, ammo, burnt fish → General (Bags tab reserved)
    return 0

# World clickables (sent once with WORLD_STATE).
# ---------------------------------------------------------------------------
# TRAVEL DESTINATIONS  (minimap / Travel modal — client auto-walks here)
# kind: "place" | "monster"
# action: optional post-arrive action {"type": "BANK"} etc.
# ---------------------------------------------------------------------------
TRAVEL_DESTINATIONS = [
    # Places
    {"id": "crossroads", "kind": "place", "label": "Village Crossroads",
     "x": 22, "y": 18, "blurb": "Spawn & hub"},
    {"id": "bank", "kind": "place", "label": "Village Bank",
     "x": 38, "y": 17, "blurb": "Store coins & items", "action": {"type": "BANK"}},
    {"id": "general_store", "kind": "place", "label": "General Store",
     "x": 27, "y": 7, "blurb": "Shopkeeper Joe"},
    {"id": "jewelry_shop", "kind": "place", "label": "Lira's Jewelry",
     "x": 33, "y": 8, "blurb": "Common rings & amulets — buys gems · Gem Bag · quest"},
    {"id": "bow_shop", "kind": "place", "label": "Elena's Bow Shop",
     "x": 64, "y": 18, "blurb": "Bows, arrows & fletching — free starter kit"},
    {"id": "smithy", "kind": "place", "label": "Smithy Furnace",
     "x": 52, "y": 7, "blurb": "Smelt ores"},
    {"id": "anvil", "kind": "place", "label": "Smithy Anvil",
     "x": 59, "y": 7, "blurb": "Smith gear & jewelry"},
    {"id": "pet_shop", "kind": "place", "label": "Pet Emporium",
     "x": 55, "y": 30, "blurb": "Luna's companions"},
    {"id": "inn_hearth", "kind": "place", "label": "Inn Hearth",
     "x": 5, "y": 29, "blurb": "Cook food", "action": {"type": "COOK"}},
    {"id": "wishing_well", "kind": "place", "label": "Wishing Well",
     "x": 30, "y": 21, "blurb": "Coin tosses & rare gifts · Lost Locket nearby"},
    {"id": "lake", "kind": "place", "label": "Fishing Lake",
     "x": 78, "y": 17, "blurb": "Shore fishing"},
    {"id": "mad_scientist", "kind": "place", "label": "Mad Scientist",
     "x": 70, "y": 22, "blurb": "Combat potions (+10 / +20)"},
    {"id": "mountain_pass", "kind": "place", "label": "Mountain Pass",
     "x": 112, "y": 16, "blurb": "Wolves (lvl 40) — path east"},
    {"id": "harbourreach", "kind": "place", "label": "Harbourreach",
     "x": 138, "y": 18, "blurb": "Fishing village & harbour"},
    {"id": "harbour_tackle", "kind": "place", "label": "Tackle Shop",
     "x": 138, "y": 10, "blurb": "Rods, pots, harpoons"},
    {"id": "tidehollow", "kind": "place", "label": "Tidehollow Cave",
     "x": 138, "y": 3, "blurb": "Private 10-floor instance",
     "action": {"type": "ENTER_DUNGEON", "dungeon_id": "tidehollow"}},
    {"id": "harbour_pier", "kind": "place", "label": "Harbour Pier",
     "x": 143, "y": 18, "blurb": "Shore fishing — trout → swordfish"},
    {"id": "stonehaven", "kind": "place", "label": "Stonehaven City",
     "x": 98, "y": 58, "blurb": "Stone plazas & castle"},
    {"id": "emberdeep", "kind": "place", "label": "Emberdeep Volcano",
     "x": 136, "y": 58, "blurb": "⚠ Lava dungeon — 8 floors · east of the city",
     "action": {"type": "ENTER_DUNGEON", "dungeon_id": "emberdeep"}},
    {"id": "mira_market", "kind": "place", "label": "Mira's Market",
     "x": 96, "y": 58, "blurb": "Food, potions & steel scraps"},
    {"id": "stonehaven_castle", "kind": "place", "label": "Castle Keep",
     "x": 108, "y": 50, "blurb": "Knights on patrol"},
    {"id": "dungeon_gate", "kind": "place", "label": "Dungeon Entrance",
     "x": 30, "y": 53, "blurb": "Enter the depths"},
    {"id": "dungeon_bank", "kind": "place", "label": "Dungeon Bank",
     "x": 36, "y": 50, "blurb": "Chest near the gate", "action": {"type": "BANK"}},
    {"id": "void_sanctum", "kind": "place", "label": "Void Sanctum",
     "x": 137, "y": 79, "blurb": "⚠ High-level mystical dungeon (SE)"},
    # Quest givers
    {"id": "quest_scout_bren", "kind": "place", "label": "Scout Bren",
     "x": 104, "y": 16, "blurb": "Quest: Wolves on the Pass"},
    {"id": "quest_hermit_cole", "kind": "place", "label": "Hermit Cole",
     "x": 40, "y": 52, "blurb": "Dungeon quests — bones & dragon"},
    {"id": "quest_cook_nell", "kind": "place", "label": "Cook Nell",
     "x": 136, "y": 23, "blurb": "Quest: Harbour Feast"},
    {"id": "quest_herald_rowan", "kind": "place", "label": "Herald Rowan",
     "x": 110, "y": 47, "blurb": "Stonehaven quest chain"},
    {"id": "quest_scout_elena", "kind": "place", "label": "Scout Elena",
     "x": 22, "y": 39, "blurb": "Quest: Silk Harvest"},
    # Monsters (camp centres)
    {"id": "rats", "kind": "monster", "label": "Giant Rats",
     "x": 14, "y": 46, "monster": "giant_rat", "blurb": "Starter mine"},
    {"id": "goblins", "kind": "monster", "label": "Goblins",
     "x": 50, "y": 52, "monster": "goblin", "blurb": "Upper dungeon"},
    {"id": "skeletons", "kind": "monster", "label": "Skeletons",
     "x": 62, "y": 56, "monster": "skeleton", "blurb": "Upper dungeon"},
    {"id": "giants", "kind": "monster", "label": "Giants",
     "x": 63, "y": 74, "monster": "giant", "blurb": "Peaceful until hit"},
    {"id": "guards", "kind": "monster", "label": "City Guards",
     "x": 98, "y": 58, "monster": "guard", "blurb": "Stonehaven — peaceful until hit"},
    {"id": "knights", "kind": "monster", "label": "Castle Knights",
     "x": 108, "y": 50, "monster": "knight", "blurb": "Castle keep — peaceful until hit"},
    {"id": "mythos_champion", "kind": "monster", "label": "Mythos Champion",
     "x": 110, "y": 48, "monster": "mythos_champion", "blurb": "⚠ Lv 90 — full Mythos plate (peaceful until hit)"},
    {"id": "big_skeletons", "kind": "monster", "label": "Big Skeletons",
     "x": 46, "y": 92, "monster": "big_skeleton", "blurb": "Mithril cavern"},
    {"id": "spiders", "kind": "monster", "label": "Giant Spiders",
     "x": 64, "y": 83, "monster": "spider", "blurb": "Spider nest"},
    {"id": "dragon", "kind": "monster", "label": "Adamant Dragon",
     "x": 62, "y": 94, "monster": "dragon", "blurb": "Adamantite lair"},
    {"id": "wolves", "kind": "monster", "label": "Mountain Wolves",
     "x": 114, "y": 16, "monster": "wolf", "blurb": "Mountain pass (lvl 40)"},
    {"id": "shades", "kind": "monster", "label": "Shades",
     "x": 128, "y": 85, "monster": "shade", "blurb": "Void Sanctum room 1"},
    {"id": "crypt_ghouls", "kind": "monster", "label": "Crypt Ghouls",
     "x": 141, "y": 85, "monster": "crypt_ghoul", "blurb": "Void Sanctum room 2"},
    {"id": "void_imps", "kind": "monster", "label": "Void Imps",
     "x": 128, "y": 93, "monster": "void_imp", "blurb": "Void Sanctum room 3"},
    {"id": "obsidian_colossi", "kind": "monster", "label": "Obsidian Colossi",
     "x": 141, "y": 93, "monster": "obsidian_colossus", "blurb": "Void Sanctum room 4"},
    {"id": "shadow_knights", "kind": "monster", "label": "Shadow Knights",
     "x": 128, "y": 100, "monster": "shadow_knight", "blurb": "Void Sanctum room 5"},
    {"id": "void_horror", "kind": "monster", "label": "Void Horror",
     "x": 141, "y": 101, "monster": "void_horror", "blurb": "Sanctum boss (lvl 95)"},
]


INTERACTABLES = [
    {"id": "smithy_furnace", "kind": "furnace", "name": "Furnace", "x": 52, "y": 6},
    {"id": "smithy_anvil", "kind": "anvil", "name": "Anvil", "x": 59, "y": 6},
    {"id": "smithy_door", "kind": "door", "name": "Smithy Door", "x": 56, "y": 14,
     "enter_x": 56, "enter_y": 12, "exit_x": 56, "exit_y": 15, "building": "smithy"},
    {"id": "cottage_nw_door", "kind": "door", "name": "Door", "x": 7, "y": 11,
     "enter_x": 7, "enter_y": 9, "exit_x": 7, "exit_y": 12, "building": "cottage_nw"},
    {"id": "cottage_ne_door", "kind": "door", "name": "Door", "x": 27, "y": 11,
     "enter_x": 27, "enter_y": 9, "exit_x": 27, "exit_y": 12, "building": "cottage_ne"},
    {"id": "cottage_sw_door", "kind": "door", "name": "Door", "x": 7, "y": 32,
     "enter_x": 7, "enter_y": 30, "exit_x": 7, "exit_y": 33, "building": "cottage_sw"},
    {"id": "cottage_se_door", "kind": "door", "name": "Door", "x": 27, "y": 32,
     "enter_x": 27, "enter_y": 30, "exit_x": 27, "exit_y": 33, "building": "cottage_se"},
    {"id": "bank_door", "kind": "door", "name": "Bank Door", "x": 38, "y": 20,
     "enter_x": 38, "enter_y": 18, "exit_x": 38, "exit_y": 21, "building": "bank"},
    {"id": "pet_door", "kind": "door", "name": "Pet Emporium Door", "x": 55, "y": 32,
     "enter_x": 55, "enter_y": 30, "exit_x": 55, "exit_y": 33, "building": "pet_emporium"},
    {"id": "bank_booth", "kind": "bank", "name": "Bank Booth", "x": 38, "y": 16},
    {"id": "dungeon_bank", "kind": "bank", "name": "Dungeon Bank Chest", "x": 36, "y": 50,
     "variant": "chest"},
    {"id": "dungeon_entrance", "kind": "dungeon_entrance", "name": "Dungeon Entrance",
     "x": 38, "y": 53, "enter_x": 40, "enter_y": 53, "exit_x": 30, "exit_y": 53},
    {"id": "tidehollow_cave", "kind": "cave_entrance", "name": "Tidehollow Cave",
     "x": 138, "y": 2, "blurb": "10 floors · clear each level · medal on completion",
     "dungeon_id": "tidehollow"},
    {"id": "emberdeep_mouth", "kind": "volcano_entrance", "name": "Emberdeep Crater",
     "x": 136, "y": 58, "blurb": "8 lava floors · new beasts · Emberdeep Medal",
     "dungeon_id": "emberdeep"},

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
    {"id": "shop_counter", "kind": "counter", "name": "Shop Counter", "x": 27, "y": 5},
    {"id": "shop_shelf_a", "kind": "shelf", "name": "Shelves", "x": 24, "y": 4},
    {"id": "shop_shelf_b", "kind": "shelf", "name": "Shelves", "x": 30, "y": 4},
    {"id": "shop_crate_a", "kind": "crate", "name": "Crate", "x": 24, "y": 8},
    {"id": "shop_crate_b", "kind": "crate", "name": "Crate", "x": 25, "y": 9},
    {"id": "shop_barrel", "kind": "barrel", "name": "Barrel", "x": 30, "y": 8},
    {"id": "shop_barrel_b", "kind": "barrel", "name": "Barrel", "x": 29, "y": 9},
    {"id": "shop_rug", "kind": "rug", "name": "Rug", "x": 27, "y": 8, "color": [70, 90, 130]},

    # --- The Resting Ox inn (cottage_sw) floor 4–10, 21–27 ---
    {"id": "inn_fireplace", "kind": "range", "name": "Cooking Hearth", "x": 4, "y": 29},
    {"id": "inn_table", "kind": "table", "name": "Table", "x": 9, "y": 27},
    {"id": "inn_chair_a", "kind": "chair", "name": "Chair", "x": 8, "y": 27, "facing": 1},
    {"id": "inn_chair_b", "kind": "chair", "name": "Chair", "x": 10, "y": 27, "facing": -1},
    {"id": "inn_bed_a", "kind": "bed", "name": "Bed", "x": 4, "y": 29},
    {"id": "inn_bed_b", "kind": "bed", "name": "Bed", "x": 4, "y": 30},
    {"id": "inn_barrel", "kind": "barrel", "name": "Ale Barrel", "x": 9, "y": 29},
    {"id": "inn_barrel_b", "kind": "barrel", "name": "Ale Barrel", "x": 10, "y": 25},
    {"id": "inn_rug", "kind": "rug", "name": "Rug", "x": 7, "y": 28, "color": [130, 70, 40]},
    {"id": "inn_candle", "kind": "candle", "name": "Candle", "x": 9, "y": 29},

    # --- Farmhouse (cottage_se) floor 16–22, 21–27 ---
    {"id": "farm_bed", "kind": "bed", "name": "Bed", "x": 24, "y": 25},
    {"id": "farm_table", "kind": "table", "name": "Table", "x": 29, "y": 27},
    {"id": "farm_chair", "kind": "chair", "name": "Chair", "x": 28, "y": 27, "facing": 1},
    {"id": "farm_crate", "kind": "crate", "name": "Crate", "x": 30, "y": 25},
    {"id": "farm_barrel", "kind": "barrel", "name": "Barrel", "x": 24, "y": 29},
    {"id": "farm_chest", "kind": "chest", "name": "Chest", "x": 30, "y": 30},
    {"id": "farm_rug", "kind": "rug", "name": "Rug", "x": 27, "y": 28, "color": [100, 80, 50]},
    {"id": "farm_candle", "kind": "candle", "name": "Candle", "x": 29, "y": 25},

    # --- Village Bank floor 27–33, 13–17 ---
    {"id": "bank_booth_w", "kind": "bank", "name": "Bank Booth", "x": 36, "y": 16},
    {"id": "bank_booth_e", "kind": "bank", "name": "Bank Booth", "x": 40, "y": 16},
    {"id": "bank_chest_a", "kind": "chest", "name": "Vault Chest", "x": 35, "y": 15},
    {"id": "bank_chest_b", "kind": "chest", "name": "Vault Chest", "x": 41, "y": 15},
    {"id": "bank_stool_a", "kind": "stool", "name": "Stool", "x": 36, "y": 18},
    {"id": "bank_stool_b", "kind": "stool", "name": "Stool", "x": 40, "y": 18},
    {"id": "bank_rug", "kind": "rug", "name": "Rug", "x": 38, "y": 17, "color": [50, 70, 110]},

    # --- Gareth's Smithy floor 37–47, 5–13 ---
    {"id": "smith_workbench", "kind": "workbench", "name": "Workbench", "x": 54, "y": 6},
    {"id": "smith_weapon_rack", "kind": "weapon_rack", "name": "Weapon Rack", "x": 61, "y": 5},
    {"id": "smith_barrel_a", "kind": "barrel", "name": "Ore Barrel", "x": 51, "y": 9},
    {"id": "smith_barrel_b", "kind": "barrel", "name": "Ore Barrel", "x": 51, "y": 10},
    {"id": "smith_crate", "kind": "crate", "name": "Crate", "x": 61, "y": 10},
    {"id": "smith_quench", "kind": "quench_bucket", "name": "Quench Bucket", "x": 64, "y": 8},
    {"id": "smith_chest", "kind": "chest", "name": "Tool Chest", "x": 61, "y": 12},

    # --- Pet Emporium floor 37–45, 21–27 ---
    {"id": "pet_counter", "kind": "counter", "name": "Counter", "x": 55, "y": 26},
    {"id": "pet_cage_a", "kind": "pet_cage", "name": "Cage", "x": 51, "y": 25},
    {"id": "pet_cage_b", "kind": "pet_cage", "name": "Cage", "x": 52, "y": 25},
    {"id": "pet_bed_a", "kind": "pet_bed", "name": "Pet Bed", "x": 58, "y": 25},
    {"id": "pet_bed_b", "kind": "pet_bed", "name": "Pet Bed", "x": 59, "y": 26},
    {"id": "pet_shelf", "kind": "shelf", "name": "Supplies", "x": 51, "y": 28},
    {"id": "pet_barrel", "kind": "barrel", "name": "Feed Barrel", "x": 59, "y": 29},
    {"id": "pet_rug", "kind": "rug", "name": "Rug", "x": 55, "y": 28, "color": [80, 120, 70]},
    {"id": "pet_candle", "kind": "candle", "name": "Candle", "x": 53, "y": 30},

    # --- Harbourreach Tackle (98–106, 4–12) ---
    {"id": "tackle_door", "kind": "door", "name": "Tackle Shop Door", "x": 138, "y": 14,
     "enter_x": 138, "enter_y": 12, "exit_x": 138, "exit_y": 15, "building": "harbour_tackle"},
    {"id": "tackle_counter", "kind": "counter", "name": "Counter", "x": 138, "y": 8},
    {"id": "tackle_shelf_a", "kind": "shelf", "name": "Rod Racks", "x": 135, "y": 7},
    {"id": "tackle_shelf_b", "kind": "shelf", "name": "Net Baskets", "x": 141, "y": 7},
    {"id": "tackle_barrel", "kind": "barrel", "name": "Bait Barrel", "x": 135, "y": 11},
    {"id": "tackle_crate", "kind": "crate", "name": "Crate", "x": 141, "y": 11},

    # --- Kai's Catch / harbour cookhouse (98–106, 18–26) ---
    {"id": "fishmonger_door", "kind": "door", "name": "Fishmonger Door", "x": 138, "y": 28,
     "enter_x": 138, "enter_y": 26, "exit_x": 138, "exit_y": 29, "building": "harbour_fishmonger"},
    {"id": "harbour_hearth", "kind": "range", "name": "Harbour Hearth", "x": 135, "y": 21},
    {"id": "fish_counter", "kind": "counter", "name": "Fish Counter", "x": 138, "y": 22},
    {"id": "fish_barrel_a", "kind": "barrel", "name": "Ice Barrel", "x": 141, "y": 21},
    {"id": "fish_barrel_b", "kind": "barrel", "name": "Salt Barrel", "x": 141, "y": 25},
    {"id": "fish_table", "kind": "table", "name": "Gutting Table", "x": 136, "y": 25},
    {"id": "fish_rug", "kind": "rug", "name": "Rug", "x": 138, "y": 24, "color": [50, 90, 120]},

    # Village wishing well (east of crossroads, south of the road)
    {"id": "wishing_well", "kind": "wishing_well", "name": "Wishing Well", "x": 30, "y": 21},

    # Stonehaven City doors
    {"id": "city_house_nw_door", "kind": "door", "name": "Door", "x": 86, "y": 52,
     "enter_x": 86, "enter_y": 50, "exit_x": 86, "exit_y": 53, "building": "city_house_nw"},
    {"id": "city_house_sw_door", "kind": "door", "name": "Door", "x": 86, "y": 66,
     "enter_x": 86, "enter_y": 64, "exit_x": 86, "exit_y": 67, "building": "city_house_sw"},
    {"id": "city_barracks_door", "kind": "door", "name": "Barracks Door", "x": 114, "y": 68,
     "enter_x": 114, "enter_y": 66, "exit_x": 114, "exit_y": 69, "building": "city_barracks"},
    {"id": "castle_gate", "kind": "door", "name": "Castle Gate", "x": 108, "y": 54,
     "enter_x": 108, "enter_y": 52, "exit_x": 108, "exit_y": 56, "building": "stonehaven_castle"},
    {"id": "castle_gate_e", "kind": "door", "name": "Castle Gate", "x": 109, "y": 54,
     "enter_x": 109, "enter_y": 52, "exit_x": 109, "exit_y": 56, "building": "stonehaven_castle"},

    # --- Castle Keep interior ---
    {"id": "castle_throne", "kind": "throne", "name": "Throne", "x": 110, "y": 45},
    {"id": "castle_rug", "kind": "rug", "name": "Royal Rug", "x": 110, "y": 48, "color": [120, 36, 48]},
    {"id": "castle_table", "kind": "table", "name": "Council Table", "x": 106, "y": 48},
    {"id": "castle_chair_a", "kind": "chair", "name": "Chair", "x": 105, "y": 48, "facing": 1},
    {"id": "castle_chair_b", "kind": "chair", "name": "Chair", "x": 107, "y": 48, "facing": -1},
    {"id": "castle_banner_w", "kind": "banner", "name": "Banner", "x": 104, "y": 45, "color": [160, 40, 48]},
    {"id": "castle_banner_e", "kind": "banner", "name": "Banner", "x": 116, "y": 45, "color": [160, 40, 48]},
    {"id": "castle_rack", "kind": "weapon_rack", "name": "Armoury Rack", "x": 103, "y": 50},
    {"id": "castle_chest", "kind": "chest", "name": "Keep Chest", "x": 115, "y": 50},
    {"id": "castle_brazier_w", "kind": "brazier", "name": "Brazier", "x": 103, "y": 46},
    {"id": "castle_brazier_e", "kind": "brazier", "name": "Brazier", "x": 115, "y": 46},
    {"id": "castle_candle", "kind": "candle", "name": "Candle", "x": 108, "y": 46},

    # --- City plaza atmosphere ---
    {"id": "city_fountain", "kind": "fountain", "name": "Plaza Fountain", "x": 98, "y": 58},
    {"id": "city_stall_a", "kind": "market_stall", "name": "Market Stall", "x": 94, "y": 56},
    {"id": "city_stall_b", "kind": "market_stall", "name": "Market Stall", "x": 102, "y": 56},
    {"id": "city_stall_c", "kind": "market_stall", "name": "Market Stall", "x": 94, "y": 61},
    {"id": "city_crate_a", "kind": "crate", "name": "Crate", "x": 101, "y": 60},
    {"id": "city_barrel_a", "kind": "barrel", "name": "Barrel", "x": 96, "y": 60},

    # --- City house NW furniture ---
    {"id": "city_nw_bed", "kind": "bed", "name": "Bed", "x": 84, "y": 46},
    {"id": "city_nw_table", "kind": "table", "name": "Table", "x": 87, "y": 48},
    {"id": "city_nw_chair", "kind": "chair", "name": "Chair", "x": 86, "y": 48, "facing": 1},
    {"id": "city_nw_rug", "kind": "rug", "name": "Rug", "x": 86, "y": 49, "color": [80, 70, 100]},
    {"id": "city_nw_chest", "kind": "chest", "name": "Chest", "x": 88, "y": 46},

    # --- City house SW furniture ---
    {"id": "city_sw_bed", "kind": "bed", "name": "Bed", "x": 84, "y": 60},
    {"id": "city_sw_table", "kind": "table", "name": "Table", "x": 87, "y": 62},
    {"id": "city_sw_barrel", "kind": "barrel", "name": "Barrel", "x": 88, "y": 64},
    {"id": "city_sw_rug", "kind": "rug", "name": "Rug", "x": 86, "y": 63, "color": [100, 70, 50]},

    # --- Barracks furniture ---
    {"id": "barracks_rack_a", "kind": "weapon_rack", "name": "Weapon Rack", "x": 112, "y": 60},
    {"id": "barracks_rack_b", "kind": "weapon_rack", "name": "Weapon Rack", "x": 116, "y": 60},
    {"id": "barracks_bed_a", "kind": "bed", "name": "Cot", "x": 112, "y": 64},
    {"id": "barracks_bed_b", "kind": "bed", "name": "Cot", "x": 115, "y": 64},
    {"id": "barracks_table", "kind": "table", "name": "Table", "x": 114, "y": 62},
    {"id": "barracks_chest", "kind": "chest", "name": "Footlocker", "x": 116, "y": 66},
    {"id": "barracks_barrel", "kind": "barrel", "name": "Barrel", "x": 112, "y": 66},

    # Void Sanctum — dark mystical entrance (SE of Stonehaven)
    {"id": "void_sanctum_door", "kind": "door", "name": "Void Sanctum Gate",
     "x": 137, "y": 80,
     "enter_x": 137, "enter_y": 78, "exit_x": 137, "exit_y": 81, "building": "void_sanctum"},
    {"id": "void_sanctum_portal", "kind": "dungeon_entrance", "name": "Descent into the Void",
     "x": 137, "y": 79,
     "enter_x": 137, "enter_y": 84, "exit_x": 137, "exit_y": 77, "warning": True},
    {"id": "void_warning", "kind": "warning_sign", "name": "⚠ DANGER — High Level Monsters",
     "x": 135, "y": 81},
    {"id": "void_warning_e", "kind": "warning_sign", "name": "⚠ DANGER — High Level Monsters",
     "x": 139, "y": 81},
    {"id": "void_candle_a", "kind": "candle", "name": "Void Candle", "x": 134, "y": 76},
    {"id": "void_candle_b", "kind": "candle", "name": "Void Candle", "x": 140, "y": 76},
    {"id": "void_altar", "kind": "bookshelf", "name": "Forbidden Tomes", "x": 133, "y": 75},
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
        "x0": 23, "y0": 3, "x1": 31, "y1": 11,
        "floor_x0": 24, "floor_y0": 4, "floor_x1": 30, "floor_y1": 10,
    },
    {
        "id": "cottage_sw", "name": "The Resting Ox", "kind": "house", "style": 1,
        "material": "brick",
        "x0": 3, "y0": 24, "x1": 11, "y1": 32,
        "floor_x0": 4, "floor_y0": 25, "floor_x1": 10, "floor_y1": 31,
    },
    {
        "id": "cottage_se", "name": "Farmhouse", "kind": "house", "style": 1,
        "material": "wood",
        "x0": 23, "y0": 24, "x1": 31, "y1": 32,
        "floor_x0": 24, "floor_y0": 25, "floor_x1": 30, "floor_y1": 31,
    },
    {
        "id": "bank", "name": "Village Bank", "kind": "house", "style": 1,
        "material": "brick",
        "x0": 34, "y0": 14, "x1": 42, "y1": 20,
        "floor_x0": 35, "floor_y0": 15, "floor_x1": 41, "floor_y1": 19,
    },
    {
        "id": "smithy", "name": "Gareth's Smithy", "kind": "smithy", "style": 1,
        "material": "brick",
        "x0": 50, "y0": 4, "x1": 62, "y1": 14,
        "floor_x0": 51, "floor_y0": 5, "floor_x1": 61, "floor_y1": 13,
    },
    {
        "id": "pet_emporium", "name": "Pet Emporium", "kind": "house", "style": 0,
        "material": "wood",
        "x0": 50, "y0": 24, "x1": 60, "y1": 32,
        "floor_x0": 51, "floor_y0": 25, "floor_x1": 59, "floor_y1": 31,
    },
    {
        "id": "harbour_tackle", "name": "Harbourreach Tackle", "kind": "house", "style": 0,
        "material": "wood",
        "x0": 134, "y0": 6, "x1": 142, "y1": 14,
        "floor_x0": 135, "floor_y0": 7, "floor_x1": 141, "floor_y1": 13,
    },
    {
        "id": "harbour_fishmonger", "name": "Kai's Catch", "kind": "house", "style": 1,
        "material": "wood",
        "x0": 134, "y0": 20, "x1": 142, "y1": 28,
        "floor_x0": 135, "floor_y0": 21, "floor_x1": 141, "floor_y1": 27,
    },
    {
        "id": "city_house_nw", "name": "Stonehaven Cottage", "kind": "house", "style": 1,
        "material": "brick",
        "x0": 82, "y0": 44, "x1": 90, "y1": 52,
        "floor_x0": 83, "floor_y0": 45, "floor_x1": 89, "floor_y1": 51,
    },
    {
        "id": "city_house_sw", "name": "Stonehaven House", "kind": "house", "style": 1,
        "material": "brick",
        "x0": 82, "y0": 58, "x1": 90, "y1": 66,
        "floor_x0": 83, "floor_y0": 59, "floor_x1": 89, "floor_y1": 65,
    },
    {
        "id": "city_barracks", "name": "City Barracks", "kind": "house", "style": 1,
        "material": "brick",
        "x0": 110, "y0": 58, "x1": 118, "y1": 68,
        "floor_x0": 111, "floor_y0": 59, "floor_x1": 117, "floor_y1": 67,
    },
    {
        "id": "stonehaven_castle", "name": "Castle Keep", "kind": "castle", "style": 1,
        "material": "brick",
        "x0": 100, "y0": 42, "x1": 118, "y1": 54,
        "floor_x0": 102, "floor_y0": 44, "floor_x1": 116, "floor_y1": 52,
    },
    {
        "id": "void_sanctum", "name": "Void Sanctum", "kind": "crypt", "style": 1,
        "material": "dark_stone",
        "x0": 132, "y0": 74, "x1": 142, "y1": 80,
        "floor_x0": 133, "floor_y0": 75, "floor_x1": 141, "floor_y1": 79,
    },
    {
        "id": "emberdeep_volcano", "name": "Emberdeep", "kind": "volcano", "style": 0,
        "material": "basalt",
        "x0": 128, "y0": 46, "x1": 146, "y1": 58,
        "floor_x0": 134, "floor_y0": 52, "floor_x1": 140, "floor_y1": 56,
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
    "smith_bronze_arrowtips": {
        "name": "Bronze Arrowtips", "category": "smith", "skill": "smithing", "level_req": 5, "xp": 25,
        "inputs": {"bronze_bar": 1}, "output": ("bronze_arrowtips", 15),
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
    "smith_iron_arrowtips": {
        "name": "Iron Arrowtips", "category": "smith", "skill": "smithing", "level_req": 20, "xp": 40,
        "inputs": {"iron_bar": 1}, "output": ("iron_arrowtips", 15),
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
    "smith_steel_arrowtips": {
        "name": "Steel Arrowtips", "category": "smith", "skill": "smithing", "level_req": 35, "xp": 75,
        "inputs": {"steel_bar": 1}, "output": ("steel_arrowtips", 15),
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
    "smith_mithril_arrowtips": {
        "name": "Mithril Arrowtips", "category": "smith", "skill": "smithing", "level_req": 55, "xp": 110,
        "inputs": {"mithril_bar": 1}, "output": ("mithril_arrowtips", 15),
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
    "smith_adamant_arrowtips": {
        "name": "Adamantite Arrowtips", "category": "smith", "skill": "smithing", "level_req": 75, "xp": 170,
        "inputs": {"adamantite_bar": 1}, "output": ("adamant_arrowtips", 15),
    },
    # Jewelry — gem + metal bar at the anvil (void jewelry stays drop-only)
    "smith_gold_ring": {
        "name": "Gold Ring", "category": "smith", "skill": "smithing", "level_req": 5, "xp": 20,
        "inputs": {"bronze_bar": 1}, "output": ("gold_ring", 1),
    },
    "smith_bronze_amulet": {
        "name": "Bronze Amulet", "category": "smith", "skill": "smithing", "level_req": 7, "xp": 22,
        "inputs": {"bronze_bar": 1}, "output": ("bronze_amulet", 1),
    },
    "smith_opal_ring": {
        "name": "Opal Ring", "category": "smith", "skill": "smithing", "level_req": 8, "xp": 30,
        "inputs": {"bronze_bar": 1, "opal": 1}, "output": ("opal_ring", 1),
    },
    "smith_opal_amulet": {
        "name": "Opal Amulet", "category": "smith", "skill": "smithing", "level_req": 8, "xp": 30,
        "inputs": {"bronze_bar": 1, "opal": 1}, "output": ("opal_amulet", 1),
    },
    "smith_jade_ring": {
        "name": "Jade Ring", "category": "smith", "skill": "smithing", "level_req": 12, "xp": 40,
        "inputs": {"bronze_bar": 1, "jade": 1}, "output": ("jade_ring", 1),
    },
    "smith_jade_amulet": {
        "name": "Jade Amulet", "category": "smith", "skill": "smithing", "level_req": 12, "xp": 40,
        "inputs": {"bronze_bar": 1, "jade": 1}, "output": ("jade_amulet", 1),
    },
    "smith_topaz_ring": {
        "name": "Topaz Ring", "category": "smith", "skill": "smithing", "level_req": 16, "xp": 50,
        "inputs": {"bronze_bar": 1, "topaz": 1}, "output": ("topaz_ring", 1),
    },
    "smith_topaz_amulet": {
        "name": "Topaz Amulet", "category": "smith", "skill": "smithing", "level_req": 16, "xp": 50,
        "inputs": {"bronze_bar": 1, "topaz": 1}, "output": ("topaz_amulet", 1),
    },
    "smith_sapphire_ring": {
        "name": "Sapphire Ring", "category": "smith", "skill": "smithing", "level_req": 20, "xp": 65,
        "inputs": {"iron_bar": 1, "sapphire": 1}, "output": ("sapphire_ring", 1),
    },
    "smith_sapphire_amulet": {
        "name": "Sapphire Amulet", "category": "smith", "skill": "smithing", "level_req": 20, "xp": 65,
        "inputs": {"iron_bar": 1, "sapphire": 1}, "output": ("sapphire_amulet", 1),
    },
    "smith_emerald_ring": {
        "name": "Emerald Ring", "category": "smith", "skill": "smithing", "level_req": 27, "xp": 85,
        "inputs": {"iron_bar": 1, "emerald": 1}, "output": ("emerald_ring", 1),
    },
    "smith_emerald_amulet": {
        "name": "Emerald Amulet", "category": "smith", "skill": "smithing", "level_req": 27, "xp": 85,
        "inputs": {"iron_bar": 1, "emerald": 1}, "output": ("emerald_amulet", 1),
    },
    "smith_ruby_ring": {
        "name": "Ruby Ring", "category": "smith", "skill": "smithing", "level_req": 34, "xp": 110,
        "inputs": {"steel_bar": 1, "ruby": 1}, "output": ("ruby_ring", 1),
    },
    "smith_ruby_amulet": {
        "name": "Ruby Amulet", "category": "smith", "skill": "smithing", "level_req": 34, "xp": 110,
        "inputs": {"steel_bar": 1, "ruby": 1}, "output": ("ruby_amulet", 1),
    },
    "smith_diamond_ring": {
        "name": "Diamond Ring", "category": "smith", "skill": "smithing", "level_req": 50, "xp": 150,
        "inputs": {"mithril_bar": 1, "diamond": 1}, "output": ("diamond_ring", 1),
    },
    "smith_diamond_amulet": {
        "name": "Diamond Amulet", "category": "smith", "skill": "smithing", "level_req": 50, "xp": 150,
        "inputs": {"mithril_bar": 1, "diamond": 1}, "output": ("diamond_amulet", 1),
    },
    "smith_onyx_ring": {
        "name": "Onyx Ring", "category": "smith", "skill": "smithing", "level_req": 70, "xp": 220,
        "inputs": {"adamantite_bar": 1, "onyx": 1}, "output": ("onyx_ring", 1),
    },
    "smith_onyx_amulet": {
        "name": "Onyx Amulet", "category": "smith", "skill": "smithing", "level_req": 70, "xp": 220,
        "inputs": {"adamantite_bar": 1, "onyx": 1}, "output": ("onyx_amulet", 1),
    },
    # Fletching — knife in inventory (no station)
    "fletch_shafts_logs": {
        "name": "Arrow Shafts (Logs)", "category": "fletch", "skill": "fletching", "level_req": 1, "xp": 5,
        "inputs": {"logs": 1}, "output": ("arrow_shaft", 15),
    },
    "fletch_shafts_oak": {
        "name": "Arrow Shafts (Oak)", "category": "fletch", "skill": "fletching", "level_req": 15, "xp": 10,
        "inputs": {"oak_logs": 1}, "output": ("arrow_shaft", 20),
    },
    "fletch_shafts_willow": {
        "name": "Arrow Shafts (Willow)", "category": "fletch", "skill": "fletching", "level_req": 25, "xp": 15,
        "inputs": {"willow_logs": 1}, "output": ("arrow_shaft", 25),
    },
    "fletch_shafts_maple": {
        "name": "Arrow Shafts (Maple)", "category": "fletch", "skill": "fletching", "level_req": 40, "xp": 25,
        "inputs": {"maple_logs": 1}, "output": ("arrow_shaft", 30),
    },
    "fletch_shafts_yew": {
        "name": "Arrow Shafts (Yew)", "category": "fletch", "skill": "fletching", "level_req": 55, "xp": 40,
        "inputs": {"yew_logs": 1}, "output": ("arrow_shaft", 35),
    },
    "fletch_shafts_magic": {
        "name": "Arrow Shafts (Magic)", "category": "fletch", "skill": "fletching", "level_req": 70, "xp": 60,
        "inputs": {"magic_logs": 1}, "output": ("arrow_shaft", 40),
    },
    "fletch_unstrung_shortbow": {
        "name": "Unstrung Shortbow", "category": "fletch", "skill": "fletching", "level_req": 5, "xp": 15,
        "inputs": {"logs": 1}, "output": ("unstrung_shortbow", 1),
    },
    "fletch_unstrung_oak_shortbow": {
        "name": "Unstrung Oak Shortbow", "category": "fletch", "skill": "fletching", "level_req": 15, "xp": 30,
        "inputs": {"oak_logs": 1}, "output": ("unstrung_oak_shortbow", 1),
    },
    "fletch_unstrung_willow_shortbow": {
        "name": "Unstrung Willow Shortbow", "category": "fletch", "skill": "fletching", "level_req": 25, "xp": 50,
        "inputs": {"willow_logs": 1}, "output": ("unstrung_willow_shortbow", 1),
    },
    "fletch_unstrung_maple_shortbow": {
        "name": "Unstrung Maple Shortbow", "category": "fletch", "skill": "fletching", "level_req": 40, "xp": 80,
        "inputs": {"maple_logs": 1}, "output": ("unstrung_maple_shortbow", 1),
    },
    "fletch_unstrung_yew_shortbow": {
        "name": "Unstrung Yew Shortbow", "category": "fletch", "skill": "fletching", "level_req": 55, "xp": 120,
        "inputs": {"yew_logs": 1}, "output": ("unstrung_yew_shortbow", 1),
    },
    "fletch_unstrung_magic_shortbow": {
        "name": "Unstrung Magic Shortbow", "category": "fletch", "skill": "fletching", "level_req": 70, "xp": 180,
        "inputs": {"magic_logs": 1}, "output": ("unstrung_magic_shortbow", 1),
    },
    "fletch_string_shortbow": {
        "name": "Shortbow", "category": "fletch", "skill": "fletching", "level_req": 5, "xp": 10,
        "inputs": {"unstrung_shortbow": 1, "bow_string": 1}, "output": ("shortbow", 1),
    },
    "fletch_string_oak_shortbow": {
        "name": "Oak Shortbow", "category": "fletch", "skill": "fletching", "level_req": 15, "xp": 20,
        "inputs": {"unstrung_oak_shortbow": 1, "bow_string": 1}, "output": ("oak_shortbow", 1),
    },
    "fletch_string_willow_shortbow": {
        "name": "Willow Shortbow", "category": "fletch", "skill": "fletching", "level_req": 25, "xp": 35,
        "inputs": {"unstrung_willow_shortbow": 1, "bow_string": 1}, "output": ("willow_shortbow", 1),
    },
    "fletch_string_maple_shortbow": {
        "name": "Maple Shortbow", "category": "fletch", "skill": "fletching", "level_req": 40, "xp": 55,
        "inputs": {"unstrung_maple_shortbow": 1, "bow_string": 1}, "output": ("maple_shortbow", 1),
    },
    "fletch_string_yew_shortbow": {
        "name": "Yew Shortbow", "category": "fletch", "skill": "fletching", "level_req": 55, "xp": 80,
        "inputs": {"unstrung_yew_shortbow": 1, "bow_string": 1}, "output": ("yew_shortbow", 1),
    },
    "fletch_string_magic_shortbow": {
        "name": "Magic Shortbow", "category": "fletch", "skill": "fletching", "level_req": 70, "xp": 110,
        "inputs": {"unstrung_magic_shortbow": 1, "bow_string": 1}, "output": ("magic_shortbow", 1),
    },
    "fletch_headless_arrow": {
        "name": "Headless Arrows", "category": "fletch", "skill": "fletching", "level_req": 1, "xp": 15,
        "inputs": {"arrow_shaft": 15, "feather": 15}, "output": ("headless_arrow", 15),
    },
    "fletch_bronze_arrow": {
        "name": "Bronze Arrows", "category": "fletch", "skill": "fletching", "level_req": 1, "xp": 20,
        "inputs": {"headless_arrow": 15, "bronze_arrowtips": 15}, "output": ("bronze_arrow", 15),
    },
    "fletch_iron_arrow": {
        "name": "Iron Arrows", "category": "fletch", "skill": "fletching", "level_req": 15, "xp": 40,
        "inputs": {"headless_arrow": 15, "iron_arrowtips": 15}, "output": ("iron_arrow", 15),
    },
    "fletch_steel_arrow": {
        "name": "Steel Arrows", "category": "fletch", "skill": "fletching", "level_req": 30, "xp": 70,
        "inputs": {"headless_arrow": 15, "steel_arrowtips": 15}, "output": ("steel_arrow", 15),
    },
    "fletch_mithril_arrow": {
        "name": "Mithril Arrows", "category": "fletch", "skill": "fletching", "level_req": 45, "xp": 110,
        "inputs": {"headless_arrow": 15, "mithril_arrowtips": 15}, "output": ("mithril_arrow", 15),
    },
    "fletch_adamant_arrow": {
        "name": "Adamantite Arrows", "category": "fletch", "skill": "fletching", "level_req": 60, "xp": 160,
        "inputs": {"headless_arrow": 15, "adamant_arrowtips": 15}, "output": ("adamant_arrow", 15),
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
    "cook_trout": {
        "name": "Cook Trout", "category": "cook", "skill": "cooking", "level_req": 15, "xp": 55,
        "inputs": {"raw_trout": 1}, "output": ("cooked_trout", 1), "burnt": ("burnt_trout", 1),
    },
    "cook_salmon": {
        "name": "Cook Salmon", "category": "cook", "skill": "cooking", "level_req": 25, "xp": 75,
        "inputs": {"raw_salmon": 1}, "output": ("cooked_salmon", 1), "burnt": ("burnt_salmon", 1),
    },
    "cook_tuna": {
        "name": "Cook Tuna", "category": "cook", "skill": "cooking", "level_req": 30, "xp": 90,
        "inputs": {"raw_tuna": 1}, "output": ("cooked_tuna", 1), "burnt": ("burnt_tuna", 1),
    },
    "cook_lobster": {
        "name": "Cook Lobster", "category": "cook", "skill": "cooking", "level_req": 40, "xp": 110,
        "inputs": {"raw_lobster": 1}, "output": ("cooked_lobster", 1), "burnt": ("burnt_lobster", 1),
    },
    "cook_swordfish": {
        "name": "Cook Swordfish", "category": "cook", "skill": "cooking", "level_req": 45, "xp": 130,
        "inputs": {"raw_swordfish": 1}, "output": ("cooked_swordfish", 1), "burnt": ("burnt_swordfish", 1),
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
    "willow_tree": "Willow",
    "maple_tree": "Maple",
    "yew_tree": "Yew",
    "magic_tree": "Magic",
    "fishing_spot_shrimp": "Shrimp",
    "fishing_spot_sardine": "Sardine",
    "fishing_spot_trout": "Trout",
    "fishing_spot_salmon": "Salmon",
    "fishing_spot_lobster": "Lobster",
    "fishing_spot_tuna": "Tuna",
    "fishing_spot_swordfish": "Swordfish",
}


def is_bow(item_id):
    """True if the item is a ranged bow weapon."""
    item = ITEMS.get(item_id) or {}
    return item.get("weapon_type") == "bow" or "shortbow" in (item_id or "")


def bow_attack_range(item_id):
    item = ITEMS.get(item_id) or {}
    return max(4, int(item.get("range") or 4))
