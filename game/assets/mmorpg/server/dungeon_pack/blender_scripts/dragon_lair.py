"""Dragon Lair - scorched cliff maw with fangs, huge horns and a bone pile.
Run:  blender --background --python blender_scripts/dragon_lair.py [-- --no-render]
"""
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from osrs_kit import Kit  # noqa: E402

PALETTE = {
    "rock": "#4d433c", "ash": "#6b625a", "char": "#2b2623", "scorch": "#332c28",
    "bone": "#cfc3a0", "horn": "#bfb49a", "horn_dark": "#8f8570", "socket": "#221e19",
    "ember": "#d0662e", "ember_deep": "#8c3b2a",
    "interior": "#221a16", "interior_deep": "#120d0b",
}
k = Kit("dragon_lair", PALETTE, seed=23, title="Dragon Lair",
        emissive={"ember": 2.5, "ember_deep": 1.5})

W, SPRING, DEPTH = 4.0, 2.4, 3.4          # maw: 4 m wide, ~4.4 m tall, 3.4 m deep
k.archway(W, SPRING, DEPTH, outer_w=9.0, outer_h=6.0, front="rock", shape="pointed",
          peak=1.8, segs=8, jag=0.7, bulge=0.7)
k.mound(0, 4.2, 7.2, 6.2, 7.6, "rock", mat_top="ash", top_frac=0.7, grid=7, rough=0.22,
        power=0.55, crop_y=0.45)
# craggy boulders framing the cliff face
for (x, y, z, s) in ((-4.3, 0.2, 0.7, 2.0), (4.4, 0.3, 0.7, 2.1), (-3.6, -0.2, 3.6, 1.3),
                     (3.7, -0.1, 3.8, 1.3), (-1.6, 0.1, 5.5, 1.5), (1.7, 0.2, 5.6, 1.4),
                     (0.0, 0.4, 6.2, 1.3), (-5.6, 1.5, 1.0, 1.8), (5.7, 1.6, 1.0, 1.7)):
    k.rock((x, y, z), (s, s * 0.9, s * 0.8), "rock", rough=0.28)

# fangs: stalactite teeth hanging round the top of the maw, tusks rising at the sides
for i, (x, z, ln) in enumerate(((-1.7, 3.1, 0.8), (-1.15, 3.75, 1.0), (-0.45, 4.25, 1.15),
                                (0.3, 4.25, 1.1), (1.0, 3.9, 1.0), (1.65, 3.2, 0.8))):
    k.cone((x, -0.35, z + 0.2), 0.26, ln + 0.2, "bone", segs=4, rot=(180, 0, 45))
for sx in (-1, 1):
    k.cone((sx * 1.85, -0.45, 0.0), 0.3, 1.3, "bone", segs=4, rot=(0, sx * -8, 45))
    k.cone((sx * 2.3, -0.55, 0.0), 0.24, 0.8, "bone", segs=4, rot=(0, sx * -14, 45))

# two huge curved horns sprouting from the cliff top (the lair's silhouette)
for sx in (-1, 1):
    pts = k.arc_pts((sx * 2.9, 1.0, 5.6), (sx * 5.6, -0.4, 6.6), (sx * 5.1, 1.0, 9.4), n=5)
    k.tube(pts, [0.75, 0.62, 0.48, 0.34, 0.2, 0.0], "horn", segs=6)
    k.rock(pts[0], (1.1, 1.0, 0.8), "rock", rough=0.25)      # horn socket boss

# bone pile: dragon skull (left) and a ribcage (right)
SX, SY = -3.3, -2.1
k.rock((SX, SY, 0.5), (0.85, 0.95, 0.62), "bone", rough=0.08)                          # cranium
k.box((SX + 0.3, SY - 1.05, 0.38), (0.75, 1.3, 0.48), "bone", rot=(0, 0, 18), taper=0.75)  # snout
k.box((SX + 0.22, SY - 0.95, 0.1), (0.62, 1.1, 0.2), "horn_dark", rot=(0, 0, 18))     # lower jaw
for sx in (-1, 1):
    k.box((SX + sx * 0.36 + 0.05, SY - 0.55, 0.78), (0.28, 0.3, 0.2), "socket!", rot=(-25, 0, 18))
    k.tube(k.arc_pts((SX + sx * 0.45, SY + 0.5, 0.8), (SX + sx * 1.0, SY + 1.2, 1.2),
                     (SX + sx * 0.8, SY + 1.9, 1.6), n=3), [0.18, 0.13, 0.07, 0.0], "horn", segs=5)
for i in range(4):                                                                     # teeth
    k.cone((SX + 0.02 + i * 0.12, SY - 1.5 + i * 0.04, 0.18), 0.05, 0.2, "bone!", segs=3)
for i in range(5):                                                                     # ribs
    y = -2.6 + i * 0.45
    for sx in (-1, 1):
        k.tube(k.arc_pts((2.9, y, 0.05), (2.9 + sx * 1.0, y - 0.1, 0.9), (2.9 + sx * 0.25, y - 0.15, 1.5 - i * 0.12), n=3),
               [0.08, 0.08, 0.07, 0.05], "bone", segs=4)
k.tube([(2.9, -2.9, 1.45), (2.9, -0.6, 1.0)], [0.1, 0.09], "bone", segs=5)            # spine
for (a, b) in (((-1.0, -2.9, 0.06), (0.0, -3.4, 0.08)), ((1.1, -1.9, 0.06), (1.8, -2.8, 0.06)),
               ((-2.0, -0.8, 0.06), (-1.4, -1.4, 0.06))):
    k.tube([a, b], [0.07, 0.07], "bone", segs=4)
    k.rock(a, (0.14, 0.14, 0.12), "bone", subdiv=1, rough=0.1)

# scorched ground, embers, and a dull glow deep in the throat
k.disc((0, -2.0, 0), 3.6, "scorch", segs=11, sy=0.75, jag=0.25)
k.disc((0, -1.6, 0), 2.0, "char", segs=9, sy=0.8, jag=0.3, z=0.016)
for (x, y, r) in ((-0.9, -1.5, 0.28), (0.6, -2.2, 0.22), (1.3, -1.0, 0.2), (-0.2, -2.9, 0.18)):
    k.rock((x, y, 0.03), (r, r, r * 0.5), "ember", rough=0.2)
k.poly([(-1.0, DEPTH - 0.06, 0.02), (1.0, DEPTH - 0.06, 0.02), (0.6, DEPTH - 0.06, 1.2), (-0.6, DEPTH - 0.06, 1.2)][::-1], "ember_deep")
k.rock((0, DEPTH - 0.5, 0.1), (0.6, 0.4, 0.3), "ember", rough=0.2)

k.collider("cliff_left", (-3.4, 2.5, 3.0), (3.4, 5.0, 6.0))
k.collider("cliff_right", (3.4, 2.5, 3.0), (3.4, 5.0, 6.0))
k.collider("cliff_back", (0, 7.0, 3.5), (13.0, 6.0, 7.0))
k.collider("skull", (SX, SY - 0.4, 0.5), (1.6, 2.6, 1.0))
k.collider("ribcage", (2.9, -1.7, 0.8), (2.0, 2.6, 1.6))
k.trigger((0, 1.2, 1.3), (W - 0.4, 1.4, 2.6))
k.figure((1.0, -3.3, 0), rot_z=-25)
k.finish()
