"""Shared feature flags. Client and server both import this module."""
import os

def _on(name, default="1"):
    return os.environ.get(name, default).strip().lower() not in ("0", "false", "no", "off")

# Bigger pre-rendered castle (moat, drawbridge, portcullis).
# Set USE_NEW_CASTLE=0 to keep today's volume castle and tile grid.
USE_NEW_CASTLE = _on("USE_NEW_CASTLE")

# Pre-rendered unique houses. Only ids in the set are replaced.
# Set USE_NEW_BUILDINGS=0 to keep today's volume shells.
USE_NEW_BUILDINGS = _on("USE_NEW_BUILDINGS")

# OSRS-leaning character bodies, faces, armour and weapon looks.
# Set USE_NEW_CHARACTERS=0 to keep today's figures.
USE_NEW_CHARACTERS = _on("USE_NEW_CHARACTERS", "1")

# Redesigned Equipment & Stats screen.
# Set USE_NEW_EQUIPMENT_UI=0 to keep today's panel.
USE_NEW_EQUIPMENT_UI = _on("USE_NEW_EQUIPMENT_UI", "1")

# Separate castle plane (realm map + Duskspire Keep). On by default.
# Set USE_CASTLE_REALM=0 to hide the overworld portal.
USE_CASTLE_REALM = _on("USE_CASTLE_REALM", "1")
# Hand-authored Void Sanctum. On by default.
# Set USE_NEW_VOID_DUNGEON=0 to keep the old Sanctum.
USE_NEW_VOID_DUNGEON = _on("USE_NEW_VOID_DUNGEON", "1")
# Hand-authored Depths crypt. On by default.
# Set USE_NEW_DEPTHS_DUNGEON=0 to keep today's Depths (ore rooms, giants, the Adamant Dragon).
USE_NEW_DEPTHS_DUNGEON = _on("USE_NEW_DEPTHS_DUNGEON", "1")
NEW_BUILDINGS_ENABLED = {
    "cottage_nw", "cottage_ne", "cottage_sw", "cottage_se",
    "bank", "pet_emporium",
    "city_house_nw", "city_house_sw", "city_barracks",
    "harbour_tackle", "harbour_fishmonger",
    "smithy",
}
# Forge glow and chimney smoke on the pre-rendered smithy.
# Set SMITHY_FX=0 to keep the still body sprite.
SMITHY_FX = _on("SMITHY_FX")

# Navy / gold HUD chrome. Set USE_NEW_HUD=0 to keep today's sidebar and chat.
USE_NEW_HUD = _on("USE_NEW_HUD", "1")

# ChatGPT mockup plates over the navy HUD. Set USE_HUD_MOCKUP_PLATES=0
# to keep the flat navy / gold chrome.
USE_HUD_MOCKUP_PLATES = _on("USE_HUD_MOCKUP_PLATES", "1")

# Code-drawn chat, inventory, and combat bar. Set USE_HUD_DRAWN_PANELS=0
# to keep the mockup plates.
USE_HUD_DRAWN_PANELS = _on("USE_HUD_DRAWN_PANELS", "1")

# Low-poly pets and leftover monsters (rat, guard, knight, sanctum, emberdeep).
# Set USE_NEW_PETS_AND_MONSTERS=0 to keep today's procedural pets and those monsters.
# Does not turn off the existing dragon sheets or anim strips.
USE_NEW_PETS_AND_MONSTERS = _on("USE_NEW_PETS_AND_MONSTERS", "1")

# Stone-ring art for the Castle Realm portal. Set USE_NEW_CASTLE_PORTAL=0
# to keep the purple circle.
USE_NEW_CASTLE_PORTAL = _on("USE_NEW_CASTLE_PORTAL", "1")

# King's Row player homes. Set USE_PLAYER_HOUSING=0 to leave the SW grass empty.
USE_PLAYER_HOUSING = _on("USE_PLAYER_HOUSING", "1")

# Castle Realm sellers, deeds, and gate plaques. Requires the realm.
# Set USE_CASTLE_OWNERS=0 to hide sellers and plaques.
USE_CASTLE_OWNERS = _on("USE_CASTLE_OWNERS", "1") and USE_CASTLE_REALM

# Larger multi-room castle interiors. Set USE_CASTLE_INTERIORS_V2=0
# to keep the original floor rows and interior door arrivals.
USE_CASTLE_INTERIORS_V2 = _on("USE_CASTLE_INTERIORS_V2", "1")

# Low-poly item icons for inventory and ground drops.
# Set USE_REALISTIC_ITEM_ICONS=0 to keep the old inventory and ground art.
USE_REALISTIC_ITEM_ICONS = _on("USE_REALISTIC_ITEM_ICONS", "1")
