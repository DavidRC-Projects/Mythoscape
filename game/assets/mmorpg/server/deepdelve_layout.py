"""Deepdelve Mine layout (MINE_SPEC v2, see ../MINE_SPEC.md). Pure data: server and client both import it.

v2 (levels): the shaft mouth is the way DOWN.  Ground level = yard + B0 + Coal Seams (copper, tin,
iron, coal).  Level 2 = Silver Dark (mithril).  Level 3 = The Green Deep (adamantite, Colossus).
Yard <-> B0 now walk through a west slope; stepping into the shaft takes you to Level 2.

The old rat/wolf square (VOLCANO_MINE, x 50-84, y 99-132) becomes:
  * the exterior yard (shared, overworld)        y 100-107
  * the shaft mouth + ramp down to B0            x 65-69, y 103-108
  * B0 "The Upper Drift" (shared, no monsters)   y 109-116
  * three sealed mining chambers (shared, safe)  y 118-131, reached only by lift:
        F1 Coal Seams  x 51-60 | F2 Silver Dark x 62-72 | F3 The Green Deep x 74-83
The monster gauntlets and the Heartstone Colossus are private instances (server/deepdelve.py).
"""

BOX = (50, 99, 84, 132)          # outer wall ring (same footprint as the old square)
DOOR_X = (66, 67, 68)            # path gap in the north wall
YARD = (51, 100, 63, 106)        # walkable yard, west of the path
PATH_COLS = (64, 70)             # x span of the path / shaft lane, y 100-102
SHAFT = (64, 103, 70, 108)       # timber frame (x 64 and 70 are walls), ramp x 65-69
RAMP = (65, 103, 69, 108)
B0 = (51, 109, 83, 116)
CHAMBERS = {
    1: (51, 118, 60, 131),
    2: (62, 118, 72, 131),
    3: (74, 118, 83, 131),
}
FLOOR_NAMES = {0: "The Upper Drift", 1: "Coal Seams", 2: "Silver Dark", 3: "The Green Deep"}
# Mining gates per floor = the game's real level for that floor's ore (content.RESOURCE_YIELDS).
FLOOR_GATE = {1: 12, 2: 40, 3: 46}

# --- rocks: (x, y, node_type) ---------------------------------------------------
YARD_ROCKS = [
    (53, 101, "copper_rock"), (56, 101, "copper_rock"), (53, 104, "copper_rock"),
    (59, 101, "tin_rock"), (56, 104, "tin_rock"), (59, 104, "tin_rock"),
]
B0_ROCKS = []
for _i, _x in enumerate((54, 57, 60, 63)):
    B0_ROCKS.append((_x, 111, "copper_rock" if _i % 2 == 0 else "tin_rock"))
    B0_ROCKS.append((_x, 114, "tin_rock" if _i % 2 == 0 else "copper_rock"))
for _i, _x in enumerate((72, 75, 78, 81)):
    B0_ROCKS.append((_x, 113, "copper_rock" if _i % 2 == 0 else "tin_rock"))
    B0_ROCKS.append((_x, 115, "tin_rock" if _i % 2 == 0 else "copper_rock"))
B0_ROCKS += [(52, 113, "copper_rock"), (52, 115, "tin_rock"),
             (66, 115, "copper_rock"), (68, 115, "tin_rock")]
B0_ROCKS += [(58, 116, "copper_rock"), (61, 116, "tin_rock"), (76, 111, "copper_rock"), (79, 111, "tin_rock")]

CHAMBER_ROCKS = {1: [], 2: [], 3: []}
for _x in (52, 54, 56, 58, 60):
    CHAMBER_ROCKS[1] += [(_x, 121, "iron_rock"), (_x, 124, "iron_rock"),
                         (_x, 127, "coal_rock"), (_x, 130, "coal_rock")]
for _x in (63, 66, 69, 72):
    CHAMBER_ROCKS[2] += [(_x, 122, "mithril_rock"), (_x, 126, "mithril_rock")]
CHAMBER_ROCKS[2] += [(64, 130, "gem_vein"), (70, 130, "gem_vein")]
for _x in (75, 78, 81):
    CHAMBER_ROCKS[3] += [(_x, 122, "adamantite_rock"), (_x, 125, "adamantite_rock")]
CHAMBER_ROCKS[3] += [(75, 128, "gem_vein"), (81, 128, "gem_vein")]
HEART_VEIN = [(77, 131, "heart_vein"), (78, 131, "heart_vein"), (79, 131, "heart_vein")]
CHAMBER_ROCKS[3] += HEART_VEIN

ALL_ROCKS = YARD_ROCKS + B0_ROCKS + [r for k in (1, 2, 3) for r in CHAMBER_ROCKS[k]]

# --- levels (v2) ---------------------------------------------------------------
LEVEL_OF = {"yard": 1, 0: 1, 1: 1, 2: 2, 3: 3}               # region -> mine level (1 = ground)
LEVEL_NAMES = {1: "Ground Level", 2: "Level 2 - Silver Dark", 3: "Level 3 - The Green Deep"}
WEST_SLOPE = [(52, 107), (53, 107), (52, 108), (53, 108)]   # yard <-> B0 on foot
# Stepping into the shaft (either end) goes down to Level 2.  Row 105 = came from the yard,
# row 106 = came up the ramp from B0.  Refused players are put back on the side they came from.
TUNNEL_DOWN = {(x, 105): (67, 102) for x in range(65, 70)}
TUNNEL_DOWN.update({(x, 106): (67, 109) for x in range(65, 70)})
TUNNEL_TOP_STAND, TUNNEL_BOTTOM_STAND = (67, 102), (67, 109)
SHAFT_DOWN = (67, 130)                                       # Level 2 -> Level 3 ladder shaft
SHAFT_DOWN_STAND = (67, 128)
# --- pads (walkable tiles that do something when stepped on) --------------------
LIFT_PADS = {1: (75, 110)}                                   # B0 cage: down to Coal Seams (ground level)
LIFT_UP = {1: (52, 118), 2: (63, 118), 3: (75, 118)}        # chamber way back up
CHAMBER_ARRIVE = {1: (53, 119), 2: (64, 119), 3: (76, 119)}
B0_ARRIVE = {1: (75, 112)}
# Where "up" (and a gauntlet's way out) puts you: one level higher, at the way down you came by.
UP_ARRIVE = {1: (75, 112), 2: TUNNEL_BOTTOM_STAND, 3: SHAFT_DOWN_STAND}
SIGNPOSTS = [   # (x, y, text, sub) painted plank signs; non-blocking, purely visual
    (63, 103, "MINE  DOWN", "Level 2: Mithril - Mining 40"),
    (65, 110, "MINE  DOWN", "Level 2: up the ramp, into the shaft"),
    (65, 129, "LEVEL 3", "Level 3: Adamantite - Mining 46"),
]
HEART_DOOR = (83, 119)                                       # F3 side door -> Colossus instance
HEART_DOOR_STAND = (82, 119)

# --- Ore Bank chests (bank interactables; the tile blocks like furniture) -------
BANK_CHESTS = [
    ("deepdelve_bank_yard", 62, 101), ("deepdelve_bank_b0", 52, 110),
    ("deepdelve_bank_f1", 59, 118), ("deepdelve_bank_f2", 71, 118), ("deepdelve_bank_f3", 79, 118),
]

# --- decorative props (x, y, kind, blocks) ---------------------------------------
PROPS = [
    (61, 104, "crates", True), (62, 105, "barrel", True), (51, 106, "rope", False),
    (63, 100, "lantern", False), (71, 102, "cart", True),
    (56, 109, "torch", False), (62, 109, "torch", False), (72, 109, "torch", False), (82, 109, "torch", False),
    (51, 109, "timber", False), (60, 109, "timber", False), (71, 109, "timber", False), (83, 109, "timber", False),
    (70, 111, "cart", True), (83, 113, "barrel", True), (83, 116, "crates", True),
    (55, 118, "torch", False), (58, 118, "timber", False), (66, 118, "torch", False), (69, 118, "timber", False),
    (78, 118, "torch", False), (82, 118, "timber", False),
    (51, 131, "barrel", True), (72, 131, "crates", True), (83, 131, "lantern", False), (76, 131, "torch", False),
]
PROPS += [  # v2: deeper levels get more lanterns
    (62, 120, "lantern", False), (72, 124, "lantern", False), (62, 128, "lantern", False), (69, 129, "lantern", False),
    (74, 121, "lantern", False), (83, 124, "lantern", False), (74, 127, "lantern", False), (83, 129, "lantern", False),
]
# v2: crystal clusters (decor, walkable) lighting the deep levels.
CRYSTALS = {2: [(62, 124), (72, 120), (72, 128), (65, 131), (68, 121)],
            3: [(74, 124), (83, 122), (83, 127), (74, 130), (80, 120), (80, 130)]}
# Rails: west spur along B0 ends at the junction (67, 112), then turns north up the ramp.
RAILS = [(x, 112) for x in range(53, 68)] + [(67, y) for y in range(103, 112)]
TORCH_LIGHTS = [(x, y) for x, y, k, _b in PROPS if k in ("torch", "lantern")] + [(65, 103), (69, 103)]

# Ambient light per floor (spec section 5).  Overworld yard is daylight.
AMBIENT = {"yard": 1.0, 0: 0.70, 1: 0.45, 2: 0.30, 3: 0.20}


def region(x, y):
    """'yard' | 0 | 1 | 2 | 3 | None for a world tile."""
    if not (BOX[0] <= x <= BOX[2] and BOX[1] <= y <= BOX[3]):
        return None
    if y <= SHAFT[3] and not (B0[1] <= y):
        return "yard"
    if B0[1] <= y <= B0[3]:
        return 0
    for k, (x0, y0, x1, y1) in CHAMBERS.items():
        if x0 <= x <= x1 and y0 <= y <= y1:
            return k
    return 0 if y <= B0[3] + 1 else None


def level_at(x, y):
    """1 (ground) | 2 | 3 | None."""
    return LEVEL_OF.get(region(x, y))


def rock_type_at(x, y):
    for rx, ry, t in ALL_ROCKS:
        if (rx, ry) == (x, y):
            return t
    return None
