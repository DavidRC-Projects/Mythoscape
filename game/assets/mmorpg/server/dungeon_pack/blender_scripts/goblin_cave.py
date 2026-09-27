"""Goblin Cave - crude timber-framed hole in an earth bank, with a totem and skulls on stakes.
Run:  blender --background --python blender_scripts/goblin_cave.py [-- --no-render]
"""
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from osrs_kit import Kit  # noqa: E402

PALETTE = {
    "earth": "#6b5440", "grass": "#5f6d3a", "rock": "#7b776c",
    "wood": "#6b4c30", "wood_dark": "#47331f", "rope": "#a08a5c",
    "bone": "#d6cdb2", "socket": "#221e19",
    "paint_red": "#8c3b2a", "paint_ochre": "#a3823f", "goblin": "#6e7b3c",
    "interior": "#2e2620", "interior_deep": "#17120f", "flame": "#e0a542",
}
k = Kit("goblin_cave", PALETTE, seed=11, title="Goblin Cave", emissive={"flame": 3.0})

# earth bank with a timber-lined passage (opening 2.2 w x 2.6 h, 2.6 deep)
DOOR_W, DOOR_H, DEPTH = 2.2, 2.6, 2.6
k.archway(DOOR_W, DOOR_H, DEPTH, outer_w=6.6, outer_h=3.7, front="earth",
          shape="flat", segs=3, jag=0.45, bulge=0.45)
k.mound(0, 3.2, 5.6, 5.6, 4.7, "earth", mat_top="grass", top_frac=0.62, grid=7,
        crop_y=0.35, skirt_mat="earth")
# grassy overhang lumps along the top of the bank
for x in (-2.6, -1.3, 0.0, 1.3, 2.6):
    k.rock((x, 0.5, 3.75 + k.rng.uniform(-0.1, 0.1)), (1.0, 0.9, 0.45), "grass", rough=0.25)
# rocks hiding the bank edges
for (x, y, s) in ((-3.8, 0.2, 1.5), (-4.9, 0.9, 1.3), (3.8, 0.3, 1.4), (4.9, 1.0, 1.2),
                  (-2.9, -0.4, 0.8), (2.9, -0.45, 0.75), (-5.6, 2.2, 1.1), (5.7, 2.4, 1.0)):
    k.rock((x, y, s * 0.35), (s, s * 0.9, s * 0.8), "rock")

# crude timber frame: two leaning posts, a lintel, a crooked brace and plank cladding
for sx in (-1, 1):
    k.box((sx * 1.28, -0.12, 1.5), (0.34, 0.34, 3.0), "wood", rot=(0, sx * -4, sx * 3))
    k.box((sx * 1.28, -0.12, 0.08), (0.46, 0.46, 0.16), "wood_dark")
k.box((0, -0.18, 2.95), (3.6, 0.42, 0.4), "wood", rot=(0, 3, 0))           # lintel
k.box((0.4, -0.3, 3.35), (2.4, 0.3, 0.26), "wood_dark", rot=(0, -7, 2))    # crooked second beam
for sx in (-1, 1):                                                         # rope lashings
    k.box((sx * 1.28, -0.2, 2.95), (0.44, 0.44, 0.12), "rope!")
# plank cladding either side of the posts
for i, x in enumerate((-2.25, -1.8, 1.8, 2.25)):
    h = 2.2 + k.rng.uniform(-0.3, 0.3)
    k.box((x, -0.06, h / 2), (0.42, 0.12, h), "wood_dark" if i % 2 else "wood",
          rot=(0, k.rng.uniform(-5, 5), 0))
# skull nailed on the lintel + pair of horns
k.skull((0, -0.48, 3.05), 0.34)
k.tube(k.arc_pts((-0.22, -0.45, 3.35), (-0.6, -0.5, 3.55), (-0.62, -0.55, 3.9)), [0.07, 0.05, 0.035, 0.02, 0.0], "bone", segs=4)
k.tube(k.arc_pts((0.22, -0.45, 3.35), (0.6, -0.5, 3.55), (0.62, -0.55, 3.9)), [0.07, 0.05, 0.035, 0.02, 0.0], "bone", segs=4)

# totem (left): stacked carved blocks, painted, horned top
TX, TY = -3.1, -1.4
k.box((TX, TY, 0.1), (0.9, 0.9, 0.2), "rock")
blocks = [(0.75, "wood", 0.72), (1.45, "wood_dark", 0.66), (2.12, "wood", 0.6)]
for z, mt, w in blocks:
    k.box((TX, TY, z), (w, w, 0.66), mt, rot=(0, 0, 8))
    k.box((TX - 0.14, TY - w / 2 - 0.02, z + 0.08), (0.16, 0.06, 0.12), "socket!")   # eyes
    k.box((TX + 0.14, TY - w / 2 - 0.02, z + 0.08), (0.16, 0.06, 0.12), "socket!")
    k.box((TX, TY - w / 2 - 0.03, z - 0.14), (0.42, 0.06, 0.1), "paint_red!")      # mouth paint
k.box((TX, TY - 0.34, 1.12), (0.9, 0.12, 0.1), "paint_ochre!")
k.box((TX, TY, 2.62), (0.9, 0.5, 0.2), "paint_red")                                # cap
k.tube(k.arc_pts((TX - 0.35, TY, 2.62), (TX - 0.85, TY, 2.8), (TX - 0.8, TY, 3.25)), [0.1, 0.07, 0.05, 0.03, 0.0], "bone", segs=4)
k.tube(k.arc_pts((TX + 0.35, TY, 2.62), (TX + 0.85, TY, 2.8), (TX + 0.8, TY, 3.25)), [0.1, 0.07, 0.05, 0.03, 0.0], "bone", segs=4)
k.box((TX - 0.36, TY - 0.2, 1.75), (0.1, 0.1, 0.5), "goblin", rot=(0, 20, 0))       # rag banner
k.box((TX - 0.52, TY - 0.2, 1.55), (0.28, 0.04, 0.55), "goblin", rot=(0, 12, 0))

# skulls on stakes (right)
for (x, y, h) in ((2.9, -1.3, 1.5), (3.6, -0.7, 1.25), (2.3, -1.9, 1.15)):
    k.cyl((x, y, 0), 0.06, 0.05, h, "wood_dark", segs=4)
    k.skull((x, y, h - 0.05), 0.3, rot=(0, 0, k.rng.uniform(-20, 20)))
# a scatter of bones and a dirt path in front
k.disc((0, -1.6, 0), 1.7, "earth!", segs=9, sy=0.8)
k.tube([(-0.9, -2.0, 0.05), (-0.3, -2.3, 0.07)], [0.05, 0.05], "bone", segs=4)
k.tube([(0.7, -1.3, 0.05), (1.2, -1.7, 0.05)], [0.045, 0.04], "bone", segs=4)
k.skull((-1.5, -1.0, 0.0), 0.26, rot=(20, 0, 30))

# torches either side of the door, a leaning broken plank door and a crate
k.torch((-1.75, -0.7, 0))
k.torch((1.75, -0.7, 0))
for i in range(4):
    k.box((2.2 + i * 0.28, -0.75, 0.9), (0.26, 0.1, 1.8), "wood" if i % 2 else "wood_dark",
          rot=(-8, 18, 0))
k.box((-0.2 + 2.6, -2.3, 0.3), (0.6, 0.6, 0.6), "wood", rot=(0, 0, 25))
k.box((-0.2 + 2.6, -2.3, 0.3), (0.64, 0.64, 0.1), "wood_dark!", rot=(0, 0, 25))

# gameplay volumes: solid bank either side of the door, doorway trigger just inside
k.collider("bank_left", (-2.4, 1.6, 2.0), (2.6, 3.4, 4.0))
k.collider("bank_right", (2.4, 1.6, 2.0), (2.6, 3.4, 4.0))
k.collider("mound", (0, 5.0, 2.3), (9.0, 5.0, 4.6))
k.collider("totem", (TX, TY, 1.4), (1.0, 1.0, 2.8))
k.trigger((0, 0.9, 1.2), (DOOR_W - 0.2, 1.2, 2.4))
k.figure((1.3, -2.0, 0), rot_z=-25)
k.finish()
