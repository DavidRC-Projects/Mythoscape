"""Spider Nest - webbed rocky burrow with egg sacs and a wrapped cocoon.
Run:  blender --background --python blender_scripts/spider_nest.py [-- --no-render]
"""
import math
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from osrs_kit import Kit  # noqa: E402

PALETTE = {
    "rock": "#57504a", "dirt": "#5a4a3a", "moss": "#4f5a36",
    "web": "#cfcabc", "egg": "#d8d0b8", "egg_spot": "#9a8458", "cocoon": "#b8ae96",
    "bone": "#bdb59c", "socket": "#221e19", "eye": "#c23a26",
    "interior": "#221d19", "interior_deep": "#100d0b",
}
k = Kit("spider_nest", PALETTE, seed=41, title="Spider Nest", emissive={"eye": 2.2})

W, SPRING, DEPTH = 2.8, 1.25, 2.8               # low round burrow: 2.8 m wide, 2.65 m tall
k.archway(W, SPRING, DEPTH, outer_w=7.4, outer_h=3.5, front="rock", shape="round", segs=7,
          jag=0.55, bulge=0.6)
k.mound(0, 3.4, 6.0, 5.4, 4.3, "rock", mat_top="dirt", top_frac=0.55, grid=7, rough=0.2,
        crop_y=0.4)
# ring of boulders around the mouth (the burrow rim)
import math as _m
for i in range(7):                       # rim boulders kept OUTSIDE the opening, set back
    a = _m.pi * i / 6
    s = 0.8 if i not in (0, 6) else 1.1
    x = _m.cos(a) * (W / 2 + s * 0.65)
    z = SPRING + _m.sin(a) * (W / 2 + s * 0.7)
    k.rock((x, 0.15, max(z, 0.4)), (s, s * 0.8, s * 0.8), "rock", rough=0.3)
for (x, y, s) in ((-3.9, -0.2, 1.4), (3.9, -0.1, 1.5), (-5.0, 1.4, 1.2), (5.0, 1.5, 1.2),
                  (-3.1, -1.4, 0.6), (3.4, -1.6, 0.5)):
    k.rock((x, y, s * 0.3), (s, s * 0.9, s * 0.7), "rock", rough=0.28)

# funnel web: pale strands radiating from the mouth's edge out over the rocks and ground,
# tied together by sagging rings - the classic "something lives in here" read
spokes = []
for i in range(9):
    a = _m.pi * (-0.08 + 1.16 * i / 8)
    inner = (_m.cos(a) * W / 2, -0.02, max(SPRING + _m.sin(a) * W / 2, 0.05) if 0 <= a <= _m.pi else 0.05)
    outer = (_m.cos(a) * (W / 2 + 1.7), -1.0, max(SPRING + _m.sin(a) * (W / 2 + 1.3), 0.05))
    k.tube([inner, outer], [0.05, 0.05], "web", segs=3)
    spokes.append((inner, outer))
for t in (0.35, 0.7):
    ring = [tuple(a + (b - a) * t for a, b in zip(i_, o_)) for i_, o_ in spokes]
    for p0, p1 in zip(ring, ring[1:]):
        mid = tuple((a + b) / 2 for a, b in zip(p0, p1))
        k.tube([p0, (mid[0], mid[1], mid[2] - 0.12), p1], [0.04, 0.04, 0.04], "web", segs=3)
# corner webs spun across the upper corners of the opening (pale against the dark inside)
k.web(-W / 2 + 0.05, -0.05, SPRING + 1.2, 1.2, -80, 0, spokes=5, rings=3, t=0.05)
k.web(W / 2 - 0.05, -0.05, SPRING + 1.2, 1.2, 180, 260, spokes=5, rings=3, t=0.05)
# egg sacs: clusters of pale lumpy eggs stuck to the rocks
def eggs(cx, cy, cz, n, s):
    for i in range(n):
        a = 2 * math.pi * i / n + k.rng.uniform(-0.3, 0.3)
        r = s * 0.9
        x, z = cx + math.cos(a) * r, cz + abs(math.sin(a)) * r * 0.6
        k.rock((x, cy + k.rng.uniform(-0.15, 0.15), z), (s * 0.55, s * 0.5, s * 0.72), "egg", rough=0.04)
        k.box((x - s * 0.1, cy - s * 0.5, z + s * 0.2), (s * 0.18, 0.04, s * 0.14), "egg_spot!")
    k.rock((cx, cy, cz + s * 0.25), (s * 0.6, s * 0.55, s * 0.8), "egg", rough=0.08)
eggs(-3.4, -1.3, 0.45, 4, 0.8)
eggs(3.5, -1.2, 0.4, 3, 0.7)
# a wrapped cocoon hanging from the rim, with web wrap bands
k.tube([(2.4, -0.9, 3.4), (2.4, -0.95, 2.9)], [0.04, 0.04], "web", segs=3)
k.rock((2.4, -0.95, 2.35), (0.36, 0.34, 0.66), "cocoon", rough=0.1)
k.tube([(2.1, -0.95, 2.7), (2.7, -1.0, 2.2), (2.2, -0.95, 1.9)], [0.04, 0.04, 0.04], "web", segs=3)
# glinting eyes deep in the burrow, husks and bones outside
for (x, z) in ((-0.35, 0.75), (-0.18, 0.82), (0.18, 0.82), (0.35, 0.75)):
    k.box((x, DEPTH - 0.1, z), (0.1, 0.04, 0.08), "eye")
k.disc((0, -1.5, 0), 2.3, "dirt!", segs=9, sy=0.75)
k.skull((-0.9, -1.8, 0.0), 0.28, rot=(15, 0, -25))
for (a, b) in (((0.4, -2.2, 0.05), (1.1, -1.8, 0.05)), ((-1.4, -2.6, 0.05), (-0.8, -2.9, 0.05))):
    k.tube([a, b], [0.05, 0.045], "bone", segs=4)
k.box((0.9, -1.2, 0.12), (0.5, 0.3, 0.24), "cocoon", rot=(0, 0, 40))

k.collider("rim_left", (-3.0, 1.2, 1.8), (3.0, 3.6, 3.6))
k.collider("rim_right", (3.0, 1.2, 1.8), (3.0, 3.6, 3.6))
k.collider("mound", (0, 5.0, 2.2), (10.0, 5.0, 4.4))
k.trigger((0, 1.0, 1.1), (W - 0.5, 1.2, 2.2))
k.figure((1.2, -2.4, 0), rot_z=-25)
k.finish()
