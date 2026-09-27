"""Skeleton Crypt - stone mausoleum with steps going DOWN to a cracked, half-open door,
a pillared portico and a pediment with a skull.
Run:  blender --background --python blender_scripts/skeleton_crypt.py [-- --no-render]

Note: the stairwell goes below ground (to z = -1.5). In a 3D world lower/hide the terrain
inside json "ground_cutout"; in a 2D sprite game nothing is needed.
"""
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from osrs_kit import Kit  # noqa: E402

PALETTE = {
    "stone": "#8a8578", "stone_dark": "#6c685e", "roof": "#5d5a55", "slab": "#9d978a", "moss": "#5f6d3a",
    "door": "#77736a", "crack": "#1d1a18", "bone": "#d6cdb2", "socket": "#221e19",
    "iron": "#505254", "necro": "#86d1b8",
    "interior": "#27241f", "interior_deep": "#121110",
}
k = Kit("skeleton_crypt", PALETTE, seed=31, title="Skeleton Crypt", emissive={"necro": 2.0})

Z0 = -1.5                   # floor level at the bottom of the stairs
DW, DH, DEPTH = 2.2, 2.3, 3.0
FRONT = 0.0                 # mausoleum front wall plane (y)
# front wall + passage: rises from the stair bottom to 4.2 m above ground
k.archway(DW, DH, DEPTH, outer_w=7.2, outer_h=5.7, front="stone", shape="round", segs=6,
          z0=Z0, y0=FRONT, jag=0.0, bulge=0.0)
# mausoleum body behind the front wall
k.box((0, DEPTH + 2.0, 1.35), (7.2, 4.0, 5.7), "stone")
k.box((0, DEPTH / 2 + 1.0, 4.35), (7.8, DEPTH + 4.6, 0.3), "stone_dark")               # cornice
# gabled roof
L, R = -3.9, 3.9
y0r, y1r = -1.5, DEPTH + 4.3
for (ya, yb) in ((y0r, y1r),):
    k.add([(L, ya, 4.5), (R, ya, 4.5), (0, ya, 6.2), (L, yb, 4.5), (R, yb, 4.5), (0, yb, 6.2)],
          [(0, 1, 2), (5, 4, 3), (0, 3, 4, 1), (1, 4, 5, 2), (2, 5, 3, 0)],
          ["slab", "slab", "stone_dark", "roof", "roof"])
k.box((0, (y0r + y1r) / 2, 6.25), (0.4, y1r - y0r + 0.2, 0.2), "stone_dark")
for sx in (-1, 1):                                            # corner pilasters + plinth
    for yy in (0.1, DEPTH + 3.9):
        k.box((sx * 3.55, yy, 1.35), (0.5, 0.5, 5.7), "stone_dark")
    k.box((sx * 3.62, DEPTH / 2 + 2.0, 0.2), (0.3, DEPTH + 4.0, 0.4), "stone_dark")
# portico: entablature carried by 4 pillars on the ground apron in front of the wall
k.box((0, -1.35, 4.2), (7.8, 0.5, 0.6), "stone_dark")
k.skull((0, -1.62, 5.05), 0.55)                                                        # pediment skull
for sx in (-1, 1):
    k.skull((sx * 1.4, -1.62, 4.85), 0.32)
for x in (-3.3, -1.9, 1.9, 3.3):
    k.box((x, -1.35, 0.25), (0.8, 0.8, 0.3), "stone_dark")
    k.cyl((x, -1.35, 0.4), 0.3, 0.26, 3.3, "stone", segs=8)
    k.box((x, -1.35, 3.8), (0.72, 0.72, 0.22), "stone_dark")
# ground apron (flagstones) around the stairwell - stairwell x in [-1.3, 1.3], y in [-6.0, 0]
k.box((-2.9, -3.3, 0.06), (3.2, 6.6, 0.12), "slab")
k.box((2.9, -3.3, 0.06), (3.2, 6.6, 0.12), "slab")
for i in range(6):                                            # flagstone seams
    k.box((-2.9, -0.6 - i * 1.0, 0.125), (3.1, 0.06, 0.01), "stone_dark!")
    k.box((2.9, -0.6 - i * 1.0, 0.125), (3.1, 0.06, 0.01), "stone_dark!")
# stairwell: side walls and steps going DOWN from y=-6 (ground) to the door (z=-1.5)
for sx in (-1, 1):
    k.box((sx * 1.45, -3.0, (Z0 + 0.35) / 2), (0.3, 6.0, -Z0 + 0.35), "stone_dark")
    k.box((sx * 1.45, -3.0, 0.42), (0.5, 6.1, 0.14), "stone")                        # coping
N = 7
for i in range(N):
    top = -(i + 1) * (-Z0 / N)
    y = -5.6 + i * 0.72
    k.box((0, y, (top + Z0 - 0.05) / 2), (2.6, 0.74, top - Z0 + 0.05), "slab" if i % 2 else "stone")
k.box((0, -0.35, Z0 + 0.02), (2.6, 1.1, 0.04), "stone_dark")                          # landing
# cracked door: left leaf pushed half open inwards, right leaf broken with a missing corner
k.box((-DW / 2 + 0.12 + 0.3, 0.55 + 0.4, Z0 + 1.2), (0.16, 1.05, 2.3), "door", rot=(0, 0, 0))
k.box((-DW / 2 + 0.2 + 0.28, 0.2 + 0.01, Z0 + 1.2), (0.02, 0.02, 0.02), "crack!")
k.box((DW / 2 - 0.08, 0.95, Z0 + 0.85), (0.16, 1.0, 1.7), "door")                     # broken leaf
k.box((DW / 2 - 0.35, 0.3, Z0 + 0.12), (0.5, 0.5, 0.24), "door", rot=(0, 12, 30))      # fallen chunk
k.box((DW / 2 - 0.8, 0.0, Z0 + 0.08), (0.3, 0.3, 0.16), "door", rot=(0, 0, 10))
# cracks on the facade
for (x, z, a, ln) in ((-2.4, 2.2, 70, 1.2), (-2.1, 1.3, 120, 0.8), (2.6, 3.1, 110, 1.0),
                      (1.6, 1.4, 60, 0.7), (-0.6, 2.8, 20, 0.6)):
    k.box((x, -0.02, z), (0.07, 0.03, ln), "crack!", rot=(0, a, 0))
# moss and rubble
for (x, y, z, s) in ((-3.4, -0.5, 0.2, 0.7), (3.5, -0.6, 0.15, 0.6), (-3.6, -5.8, 0.15, 0.5),
                     (3.4, -6.2, 0.1, 0.45)):
    k.rock((x, y, z), (s, s, s * 0.6), "stone_dark", rough=0.25)
for (x, y, z, sx_, sz_) in ((-2.9, -0.12, 3.6, 1.4, 0.5), (2.3, -0.12, 0.6, 1.0, 0.8), (-1.9, -1.8, 0.14, 1.1, 0.04)):
    k.box((x, y, z), (sx_, 0.1, sz_), "moss")
# broken urns / candles with a faint necrotic glow and bones on the steps
for sx in (-1, 1):
    k.cyl((sx * 2.6, -3.0, 0.12), 0.26, 0.34, 0.55, "stone_dark", segs=6)
    k.cyl((sx * 2.6, -3.0, 0.67), 0.34, 0.2, 0.2, "stone_dark", segs=6)
    k.cone((sx * 2.6, -3.0, 0.8), 0.14, 0.35, "necro", segs=4)
k.poly([(-0.7, DEPTH - 0.05, Z0 + 0.02), (0.7, DEPTH - 0.05, Z0 + 0.02), (0.5, DEPTH - 0.05, Z0 + 0.9),
        (-0.5, DEPTH - 0.05, Z0 + 0.9)][::-1], "necro")                                   # glow deep inside
k.skull((0.6, -1.9, -1.02 + 0.02), 0.28, rot=(0, 0, 30))
k.tube([(-0.7, -3.1, -0.6), (-0.1, -3.4, -0.62)], [0.05, 0.05], "bone", segs=4)
# two tilted gravestones
for (x, y, r) in ((-4.4, -4.2, -8), (4.5, -3.2, 10)):
    k.box((x, y, 0.55), (0.8, 0.22, 1.1), "stone", rot=(r, 0, 5))
    k.box((x, y - 0.12, 0.7), (0.4, 0.03, 0.08), "crack!", rot=(r, 0, 5))

# wrought-iron railing with spear tips along the stairwell and the apron front
posts = [(-1.62, -5.9 + i * 1.15) for i in range(6)] + [(1.62, -5.9 + i * 1.15) for i in range(6)]
for (x, y) in posts:
    k.box((x, y, 0.95), (0.08, 0.08, 1.1), "iron!")
    k.cone((x, y, 1.5), 0.08, 0.22, "iron!", segs=4)
for sx in (-1, 1):
    k.box((sx * 1.62, -3.0, 1.3), (0.06, 5.9, 0.07), "iron!")
    k.box((sx * 1.62, -3.0, 0.62), (0.06, 5.9, 0.07), "iron!")
# a cracked sarcophagus lid leaning by the portico and skulls on the steps
k.box((-3.9, -2.2, 0.75), (0.9, 0.25, 2.0), "slab", rot=(-12, 0, 8))
k.box((-3.9, -2.36, 0.9), (0.06, 0.04, 1.3), "crack!", rot=(-12, 25, 8))
k.skull((-3.9, -2.45, 1.2), 0.22, rot=(-12, 0, 8))
k.skull((-0.6, -4.8, -0.43), 0.24, rot=(0, 0, -25))
k.skull((0.7, -2.6, -1.05 + 0.02), 0.22, rot=(0, 0, 40))

k.meta["ground_cutout"] = {"center": [0, -1.5, 0], "size": [2.6, 9.0], "note": "stairwell + passage: lower/hide terrain here in 3D"}
k.collider("stair_wall_left", (-1.45, -3.0, 0.0), (0.5, 6.0, 1.0))
k.collider("stair_wall_right", (1.45, -3.0, 0.0), (0.5, 6.0, 1.0))
k.collider("mausoleum", (0, DEPTH + 1.5, 2.0), (7.8, 5.0, 7.0))
k.collider("front_wall_left", (-2.3, 0.3, 1.5), (2.4, 0.8, 5.0))
k.collider("front_wall_right", (2.3, 0.3, 1.5), (2.4, 0.8, 5.0))
for x in (-3.3, -1.9, 1.9, 3.3):
    k.collider(f"pillar_{x:+.1f}", (x, -1.35, 2.0), (0.8, 0.8, 4.0))
k.trigger((0, 0.9, Z0 + 1.2), (DW - 0.4, 1.2, 2.4))
k.figure((-2.3, -2.2, 0.12), rot_z=-30)
k.finish()
