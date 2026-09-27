"""Giant's Cavern - huge stacked-boulder archway with a giant-sized timber door (one leaf open).
Run:  blender --background --python blender_scripts/giants_cavern.py [-- --no-render]
"""
import math
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from osrs_kit import Kit  # noqa: E402

PALETTE = {
    "boulder": "#7b776c", "boulder_dk": "#5b584f", "moss": "#5f6d3a", "grass": "#63703d",
    "wood": "#6b4c30", "wood_dk": "#47331f", "iron": "#505254", "rivet": "#35373a",
    "bone": "#bdb59c", "hide": "#7d5b43", "rope": "#a08a5c", "socket": "#221e19",
    "interior": "#27231f", "interior_deep": "#12100e",
}
k = Kit("giants_cavern", PALETTE, seed=67, title="Giant's Cavern")

W, SPRING, DEPTH = 6.0, 4.3, 4.0            # opening 6 m wide x 7.3 m tall
k.archway(W, SPRING, DEPTH, outer_w=14.0, outer_h=10.0, front="boulder_dk", shape="round",
          segs=8, jag=0.8, bulge=0.8)
k.mound(0, 6.5, 10.0, 8.0, 11.5, "boulder", mat_top="moss", top_frac=0.72, grid=7, rough=0.2,
        power=0.6, crop_y=0.5)
# the archway itself: huge boulders stacked round the opening
for i in range(9):
    a = math.pi * i / 8
    s = 2.0 if i in (0, 8) else (2.3 if i == 4 else 1.7)
    r = W / 2 + s * 0.62                       # keep every boulder OUTSIDE the opening
    x, z = math.cos(a) * r, SPRING + math.sin(a) * (W / 2 + s * 0.55)
    k.rock((x, -0.35, max(z, 1.0)), (s, s * 0.85, s * 0.85), "boulder", subdiv=1, rough=0.2)
for sx in (-1, 1):                                      # footing boulders and side piles
    k.rock((sx * 5.0, -0.5, 0.9), (1.9, 1.8, 1.7), "boulder", rough=0.22)
    k.rock((sx * 6.4, 0.6, 1.0), (2.2, 2.0, 2.0), "boulder_dk", rough=0.25)
    k.rock((sx * 6.0, -1.4, 0.4), (1.1, 1.0, 0.8), "boulder", rough=0.25)
for (x, z) in ((-2.0, 9.3), (2.1, 9.2), (0.0, 10.2)):
    k.rock((x, 0.2, z), (1.6, 1.4, 1.2), "moss", rough=0.25)
# giant-sized double door, set 1 m into the passage. Right leaf shut, left leaf swung open
# (so the 3/4 camera looks straight into the dark opening).
DY = 1.0
LW, LH = 3.0, SPRING + 1.6
def leaf(cx, cy, rot_z, pivot):
    import math as m
    c, s_ = m.cos(m.radians(rot_z)), m.sin(m.radians(rot_z))
    def P(lx, ly):        # local door coords (lx across, ly thickness) -> world
        return (pivot[0] + lx * c - ly * s_, pivot[1] + lx * s_ + ly * c)
    for i in range(5):     # planks
        lx = -(i + 0.5) * LW / 5 if pivot[0] > 0 else (i + 0.5) * LW / 5
        x, y = P(lx, 0)
        k.box((x, y, LH / 2), (LW / 5 - 0.04, 0.3, LH - (0.25 if i % 2 else 0)), "wood" if i % 2 else "wood_dk",
              rot=(0, 0, rot_z))
    for bz in (1.2, LH - 1.3):   # iron bands with rivets
        lx = -LW / 2 if pivot[0] > 0 else LW / 2
        x, y = P(lx, -0.2)
        k.box((x, y, bz), (LW, 0.08, 0.3), "iron", rot=(0, 0, rot_z))
        for j in range(4):
            rx = -(j + 0.5) * LW / 4 if pivot[0] > 0 else (j + 0.5) * LW / 4
            x2, y2 = P(rx, -0.26)
            k.box((x2, y2, bz), (0.14, 0.06, 0.14), "rivet!", rot=(0, 0, rot_z))
    return P
P = leaf(LW / 2, DY, 0, (W / 2, DY))                      # shut (right)
# huge iron ring knocker on the shut leaf
k.tube([(1.1 + 0.55 * math.cos(t), DY - 0.3, 2.4 + 0.55 * math.sin(t)) for t in
        [2 * math.pi * i / 8 for i in range(9)]], [0.09] * 9, "iron", segs=4, cap_end=False)
k.box((1.1, DY - 0.25, 2.95), (0.3, 0.1, 0.3), "rivet!")
leaf(0, DY, 72, (-W / 2, DY))                            # open (left, swung inwards)
# stone doorstep and giant props: a club leaning on the rocks, a huge bone, a hide banner
k.box((0, -0.3, 0.1), (W + 0.6, 1.2, 0.2), "boulder_dk")
k.tube([(4.6, -2.0, 0.1), (4.2, -1.3, 2.4), (4.0, -1.0, 3.6)], [0.18, 0.3, 0.55], "wood_dk", segs=6)
for i in range(3):
    k.cone((4.1 + 0.25 * (i - 1), -1.25, 3.2 + i * 0.2), 0.08, 0.35, "iron", segs=3, rot=(90, 0, 0))
k.tube([(-5.8, -2.6, 0.2), (-3.9, -3.4, 0.2)], [0.25, 0.22], "bone", segs=5)
for p in ((-5.8, -2.6, 0.25), (-3.9, -3.4, 0.25)):
    k.rock(p, (0.4, 0.4, 0.35), "bone", rough=0.1)
k.box((-4.6, -0.9, 5.0), (1.6, 0.1, 2.2), "hide", rot=(0, 4, 0))
k.box((-4.6, -0.95, 6.15), (1.9, 0.18, 0.18), "wood_dk")
k.skull((-4.6, -1.05, 4.8), 0.45)
k.disc((0, -2.5, 0), 3.8, "boulder_dk!", segs=10, sy=0.6, jag=0.2)

# stepping stones up to the doorstep, chains on the open leaf and extra rubble
for i, (x, y) in enumerate(((0.6, -1.6), (1.1, -2.7), (0.5, -3.8))):
    k.box((x, y, 0.06), (1.1, 0.9, 0.12), "boulder" if i % 2 else "boulder_dk", rot=(0, 0, 15 * i))
for (x, y, s_) in ((-7.6, -0.4, 1.2), (7.8, -0.2, 1.3), (-3.2, -2.9, 0.6), (3.6, -3.2, 0.5), (-8.2, 1.9, 1.6), (8.3, 2.2, 1.5)):
    k.rock((x, y, s_ * 0.35), (s_, s_ * 0.9, s_ * 0.75), "boulder", rough=0.25)
for j in range(5):
    k.box((3.2 - 0.05 * j, -0.9, 7.6 - j * 0.35), (0.14, 0.14, 0.3), "iron!", rot=(0, 0, 90 * (j % 2)))

k.collider("arch_left", (-5.3, 0.8, 4.0), (4.6, 4.0, 8.0))
k.collider("arch_right", (5.3, 0.8, 4.0), (4.6, 4.0, 8.0))
k.collider("door_right_leaf", (1.5, DY, LH / 2), (3.0, 0.4, LH))
k.collider("hill", (0, 9.0, 5.0), (18.0, 8.0, 10.0))
k.trigger((-1.5, DY + 0.8, 1.5), (2.8, 1.2, 3.0))    # through the OPEN left leaf
k.figure((0.8, -2.8, 0.0), rot_z=-25)
k.finish()
