"""Identity, scale and reserved future integration points.

None of these IDs collide with the live Castle Realm dungeon id
(`castle_realm`) or the live king's-castle ownership key (`king`).
"""

MAP_ID = "kings_castle_siege"
MAP_TITLE = "King's Castle"
PLANE_BATTLEFIELD = "kings_castle_siege.battlefield"
PLANE_THRONE = "kings_castle_siege.throne_room"

OWNERSHIP_KEY_RESERVED = "kings_castle_siege"

FORBIDDEN_IDS = frozenset({
    "castle_realm",
    "king",
    "gothic",
    "white_rose",
    "sky_anchor",
})

# Milestone 2: square-ish playable grid so the castle sits inside a full
# perimeter battlefield (north, south, east, west) rather than on the
# northern map edge.
WIDTH = 280
HEIGHT = 280

TILE_PX_DESIGN = 40
TILE_METERS = 1.6
STEP_SECONDS = 0.16
PLAYER_FOOTPRINT = 1

DESIGN_ATTACKERS = 100
DESIGN_DEFENDERS = 100
STAGING_TILES_PER_PLAYER = 4

GATE_STATES = ("intact", "damaged", "destroyed")

# Curtain in absolute tiles — keep is inside the courtyard, not the map edge.
WALL_W, WALL_N, WALL_E, WALL_S = 82, 92, 197, 187
WALL_THICK = 6
KEEP_RECT = (118, 114, 161, 150)  # x0,y0,x1,y1 inclusive

# Sample demonstration counts for previews/tests — NOT approved gameplay caps.
DEMO_ENGINE_SAMPLE = {
    "ram": 2,
    "trebuchet": 4,
    "siege_tower": 2,
    "ladder": 3,
}
