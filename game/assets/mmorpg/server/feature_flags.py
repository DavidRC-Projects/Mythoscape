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

# Hand-authored Void Sanctum. Set USE_NEW_VOID_DUNGEON=1 to enter it.
# Default off: the old Sanctum is unchanged.
USE_NEW_VOID_DUNGEON = _on("USE_NEW_VOID_DUNGEON", "0")
# Hand-authored Depths crypt. Set USE_NEW_DEPTHS_DUNGEON=1 to enter it.
# Default off: today's Depths (ore rooms, giants, the Adamant Dragon) is unchanged.
USE_NEW_DEPTHS_DUNGEON = _on("USE_NEW_DEPTHS_DUNGEON", "0")
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
