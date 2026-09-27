"""Wolf Den - rooty hillside den under a gnarled tree, with claw scratch marks and gnawed bones.
Run:  blender --background --python blender_scripts/wolf_den.py [-- --no-render]
"""
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from osrs_kit import Kit  # noqa: E402

PALETTE = {
    "earth": "#6b5440", "grass": "#5f6d3a", "grass_dk": "#4d5a30", "root": "#5a4632",
    "bark": "#4f3d2c", "leaf": "#4f5f33", "rock": "#7c776e", "bone": "#c1b8a5",
    "scratch": "#231f1c", "fur": "#57524b", "socket": "#221e19",
    "interior": "#2a221c", "interior_deep": "#140f0c",
}
k = Kit("wolf_den", PALETTE, seed=79, title="Wolf Den")

W, SPRING, DEPTH = 2.4, 1.1, 2.6          # den mouth 2.4 m wide x 2.3 m tall
k.archway(W, SPRING, DEPTH, outer_w=6.4, outer_h=3.1, front="earth", shape="round", segs=7,
          jag=0.45, bulge=0.5)
k.mound(0, 3.0, 6.4, 5.8, 4.4, "earth", mat_top="grass", top_frac=0.3, grid=7, rough=0.15,
        crop_y=0.35)
# grassy overhang over the mouth
for x in (-2.4, -1.2, 0.0, 1.2, 2.4):
    k.rock((x, 0.35, 3.1 + k.rng.uniform(-0.1, 0.15)), (0.95, 0.85, 0.45), "grass", rough=0.25)
# gnarled tree on the hill above the den, roots spilling down over the mouth
k.cyl((0.6, 2.6, 3.4), 0.6, 0.38, 2.6, "bark", segs=6, rot=(0, -6, 0))
k.tube([(0.5, 2.6, 5.7), (1.4, 2.4, 6.6), (2.2, 2.6, 7.0)], [0.26, 0.18, 0.1], "bark", segs=5)
k.tube([(0.6, 2.6, 5.6), (-0.5, 2.8, 6.5), (-1.2, 2.5, 6.8)], [0.24, 0.16, 0.1], "bark", segs=5)
for (x, y, z, s) in ((0.6, 2.6, 7.2, 1.9), (2.1, 2.5, 7.0, 1.3), (-1.1, 2.6, 6.9, 1.4)):
    k.rock((x, y, z), (s, s, s * 0.8), "leaf", rough=0.25, flat_bottom=False)
roots = [
    ((-0.2, 2.2, 3.6), (-1.6, 0.2, 3.4), (-1.35, -0.35, 1.5)),
    ((0.4, 2.0, 3.6), (0.2, -0.3, 3.3), (0.55, -0.4, 2.35)),
    ((1.2, 2.2, 3.6), (1.9, 0.1, 3.3), (1.45, -0.35, 1.2)),
    ((-0.8, 2.4, 3.5), (-2.8, 0.4, 3.0), (-2.6, -0.4, 0.4)),
    ((1.6, 2.4, 3.5), (3.0, 0.4, 2.8), (2.8, -0.4, 0.3)),
]
for a, c, b in roots:
    pts = k.arc_pts(a, c, b, n=5)
    k.tube(pts, [0.2, 0.18, 0.15, 0.12, 0.08, 0.0], "root", segs=5)
for (a, b) in (((-0.9, -0.3, 2.9), (-0.7, -0.45, 2.1)), ((0.1, -0.35, 2.95), (0.05, -0.45, 2.4)),
               ((1.0, -0.3, 2.9), (0.8, -0.45, 2.2))):                     # dangling rootlets
    k.tube([a, b], [0.06, 0.0], "root", segs=3)
# scratch marks: gouged into a boulder and the earth beside the mouth
k.rock((-2.7, -0.9, 0.7), (1.2, 1.0, 1.1), "rock", rough=0.18, rot=(0, 0, 10))
k.scratches(-2.7, -1.95, 0.85, n=3, length=0.8, angle=-65)
k.scratches(2.25, -0.55, 1.2, n=3, length=0.7, angle=-115, w=0.06)
k.scratches(-1.9, -0.55, 1.5, n=4, length=0.6, angle=-70, gap=0.13, w=0.05)
k.rock((3.3, -0.3, 0.4), (0.9, 0.8, 0.7), "rock", rough=0.2)
k.rock((-4.3, 0.6, 0.6), (1.2, 1.1, 1.0), "rock", rough=0.22)
k.rock((4.5, 0.8, 0.5), (1.3, 1.1, 0.9), "rock", rough=0.22)
# trodden dirt, gnawed bones, an animal skull, tufts of fur and grass
k.disc((0, -1.6, 0), 2.2, "earth!", segs=9, sy=0.8)
for (a, b) in (((0.6, -1.8, 0.06), (1.3, -2.3, 0.06)), ((-1.1, -2.4, 0.06), (-0.4, -2.2, 0.06)),
               ((1.7, -1.1, 0.06), (1.9, -1.8, 0.06))):
    k.tube([a, b], [0.06, 0.05], "bone", segs=4)
    k.rock(a, (0.1, 0.1, 0.09), "bone", subdiv=1, rough=0.1)
k.box((-0.6, -1.3, 0.14), (0.3, 0.55, 0.26), "bone", rot=(0, 0, 25), taper=0.7)            # deer skull
k.box((-0.72, -1.2, 0.24), (0.1, 0.1, 0.06), "socket!", rot=(0, 0, 25))
k.tube(k.arc_pts((-0.55, -1.1, 0.25), (-0.2, -0.9, 0.6), (-0.4, -0.7, 0.8), n=2), [0.04, 0.03, 0.0], "bone", segs=3)
for (x, y) in ((-0.2, -0.25), (0.8, -0.3), (2.7, -1.6)):
    k.box((x, y, 0.08), (0.3, 0.2, 0.12), "fur", rot=(0, 0, 30))
for (x, y) in ((-3.3, -1.6), (3.7, -1.4), (-1.9, -2.9), (2.4, -2.6), (-4.6, -0.8), (4.9, -0.6)):
    for j in range(3):
        k.cone((x + j * 0.14, y + (j % 2) * 0.1, 0), 0.1, 0.45, "grass_dk", segs=3, rot=(k.rng.uniform(-15, 15), 0, 0))

# fallen log to the right, extra roots on the flanks and a boulder pile
k.cyl((3.2, -1.9, 0.3), 0.32, 0.3, 2.6, "bark", segs=7, rot=(0, 90, 20))
k.cyl((3.2, -1.9, 0.3), 0.2, 0.2, 0.02, "earth!", segs=7, rot=(0, -90, 20))
for a, c, b in (((-3.2, 1.8, 2.6), (-4.3, 0.2, 2.0), (-4.0, -0.4, 0.2)),
                ((3.4, 1.8, 2.5), (4.4, 0.4, 1.6), (4.2, -0.3, 0.1))):
    k.tube(k.arc_pts(a, c, b, n=4), [0.16, 0.14, 0.1, 0.06, 0.0], "root", segs=5)
for (x, y, s_) in ((-5.2, -0.6, 0.7), (-4.8, -1.4, 0.5), (5.3, -0.2, 0.6)):
    k.rock((x, y, s_ * 0.3), (s_, s_ * 0.9, s_ * 0.7), "rock", rough=0.25)
k.skull((1.9, -2.9, 0.0), 0.2, mat="bone", rot=(10, 0, -30))

k.collider("bank_left", (-2.4, 1.4, 1.6), (2.4, 3.0, 3.2))
k.collider("bank_right", (2.4, 1.4, 1.6), (2.4, 3.0, 3.2))
k.collider("hill", (0, 4.8, 2.2), (10.0, 5.0, 4.4))
k.collider("scratched_rock", (-2.7, -0.9, 0.6), (1.4, 1.2, 1.2))
k.trigger((0, 1.0, 1.0), (W - 0.5, 1.2, 2.0))
k.figure((1.3, -2.3, 0), rot_z=-25)
k.finish()
