"""Void Rift - dark crystal shards round a glowing purple portal on a cracked platform.
Run:  blender --background --python blender_scripts/void_rift.py [-- --no-render]
"""
import math
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from osrs_kit import Kit  # noqa: E402

PALETTE = {
    "stone": "#3f3b46", "stone_edge": "#57525e", "crystal": "#3a3150", "crystal_lt": "#5b4b7a",
    "crystal_dk": "#241f33", "rim": "#8a52b8", "glow": "#b56ad9", "glow_mid": "#6c3b99",
    "core": "#2a1543", "rune": "#b56ad9", "rock": "#34303a",
}
k = Kit("void_rift", PALETTE, seed=53, title="Void Rift",
        emissive={"rim": 1.6, "glow": 2.6, "glow_mid": 1.6, "core": 0.7, "rune": 2.2})

PZ = 0.35                                   # platform top
CX, CZ, RX, RZ = 0.0, PZ + 1.85, 1.35, 1.85  # portal ellipse: 2.7 m wide x 3.7 m tall
# cracked octagonal platform made of slabs with gaps
for i in range(8):
    a0, a1 = 2 * math.pi * i / 8 + 0.03, 2 * math.pi * (i + 1) / 8 - 0.03
    pts = []
    for (r, a) in ((0.4, a0), (4.1, a0), (4.1, a1), (0.4, a1)):
        pts.append((math.cos(a) * r, math.sin(a) * r * 0.85 + 0.6))
    top = PZ + k.rng.uniform(-0.05, 0.04)
    v = [(x, y, top) for x, y in pts] + [(x * 1.03, y * 1.02, 0) for x, y in pts]
    k.add(v, [(0, 1, 2, 3), (4, 5, 1, 0), (5, 6, 2, 1), (6, 7, 3, 2), (7, 4, 0, 3)], "stone")
k.cyl((0, 0.6, 0), 0.45, 0.45, PZ + 0.02, "stone_edge", segs=8)
# two steps up at the front (the walkable approach)
k.box((0, -3.25, 0.12), (2.8, 0.7, 0.24), "stone_edge")
k.box((0, -3.9, 0.06), (3.2, 0.7, 0.12), "stone")
# the portal: stone-framed ellipse ring + glowing bands getting darker toward the core
N = 24
def ell(sx, sz, y):
    return [(CX + math.cos(2 * math.pi * i / N) * RX * sx, y, CZ + math.sin(2 * math.pi * i / N) * RZ * sz)
            for i in range(N)]
bands = [(1.0, "glow"), (0.78, "glow_mid"), (0.52, "core")]
for y, flip in ((0.0, False), (0.12, True)):     # front and back faces of the portal
    for (s0, mat), (s1, _) in zip(bands, bands[1:] + [(0.0, None)]):
        o, inn = ell(s0, s0, y), ell(max(s1, 0.001), max(s1, 0.001), y)
        for i in range(N):
            j = (i + 1) % N
            q = [o[i], o[j], inn[j], inn[i]] if s1 > 0 else [o[i], o[j], inn[0]]
            q = q if flip else q[::-1]
            k.add(q, [list(range(len(q)))], mat)
rim = ell(1.08, 1.06, 0.06)
k.tube(rim + rim[:1], [0.2] * (N + 1), "rim", segs=5, cap_end=False)
# jagged stone frame blocks round the ring
for i in range(10):
    a = math.pi * (-0.05 + 1.1 * i / 9)
    x, z = CX + math.cos(a) * RX * 1.32, CZ + math.sin(a) * RZ * 1.22
    k.box((x, 0.06, z), (0.55, 0.5, 0.7), "stone_edge", rot=(0, -math.degrees(a) + 90, 0))
for sx in (-1, 1):
    k.box((sx * RX * 1.3, 0.06, PZ + 0.5), (0.7, 0.6, 1.0), "stone")
# crystal shards: pointed hexagonal prisms leaning outwards, clustered behind and beside
def shard(x, y, h, r, lean_x, lean_y, mat="crystal"):
    k.cyl((x, y, PZ - 0.1), r, r * 0.8, h * 0.72, mat, segs=5, rot=(lean_y, lean_x, k.rng.uniform(0, 70)))
    import math as m
    dx = m.sin(m.radians(lean_x)) * h * 0.72
    dy = -m.sin(m.radians(lean_y)) * h * 0.72
    k.cone((x + dx, y + dy, PZ - 0.1 + m.cos(m.radians(lean_x)) * m.cos(m.radians(lean_y)) * h * 0.72),
           r * 0.8, h * 0.4, mat, segs=5, rot=(lean_y, lean_x, 0))
for (x, y, h, r, lx, ly, mt) in ((-2.3, 0.4, 4.6, 0.5, -14, 0, "crystal"), (2.4, 0.5, 5.0, 0.55, 15, 0, "crystal"),
                                 (-1.4, 1.1, 5.6, 0.48, -6, -8, "crystal_dk"), (1.5, 1.2, 5.2, 0.5, 8, -8, "crystal_dk"),
                                 (-3.1, 1.2, 3.2, 0.42, -24, -6, "crystal_lt"), (3.1, 1.4, 3.4, 0.44, 22, -6, "crystal_lt"),
                                 (0.1, 1.6, 6.3, 0.55, 0, -10, "crystal"), (-2.7, -0.9, 2.0, 0.34, -20, 12, "crystal"),
                                 (2.8, -1.0, 2.3, 0.36, 22, 12, "crystal_dk"), (-3.6, 2.6, 2.6, 0.4, -18, -14, "crystal_dk"),
                                 (3.5, 2.8, 2.4, 0.38, 16, -14, "crystal"), (0.9, 2.9, 3.5, 0.42, 6, -18, "crystal_lt"),
                                 (-1.0, 3.0, 3.8, 0.44, -6, -16, "crystal")):
    shard(x, y, h, r, lx, ly, mt)
# small glowing shards and runes on the platform, floating rocks
for (x, y) in ((-1.9, -1.6), (1.8, -1.7), (-3.2, 0.1), (3.3, 0.2)):
    k.cone((x, y, PZ - 0.05), 0.14, 0.55, "glow", segs=4, rot=(k.rng.uniform(-15, 15), k.rng.uniform(-15, 15), 0))
for i in range(8):
    a = math.pi * (1.1 + 0.8 * i / 7)
    k.box((math.cos(a) * 2.6, math.sin(a) * 2.2 + 0.6, PZ + 0.02), (0.3, 0.3, 0.02), "rune", rot=(0, 0, 45))
for (x, y, z, s) in ((-2.0, -0.4, 5.2, 0.45), (2.1, -0.2, 5.6, 0.35), (0.3, -0.3, 5.9, 0.3)):
    k.rock((x, y, z), (s, s, s * 0.8), "rock", rough=0.3)

# outer ring of small shards on the platform rim and broken ruin pillars
for (x, y, h, r, lx, ly) in ((-3.9, -0.6, 1.4, 0.26, -25, 10), (3.9, -0.4, 1.6, 0.28, 25, 10),
                             (-4.2, 1.6, 1.8, 0.3, -20, -5), (4.1, 1.9, 1.5, 0.28, 22, -5),
                             (-1.9, 3.8, 2.2, 0.32, -10, -20), (2.0, 3.9, 2.0, 0.3, 12, -20),
                             (-3.4, -2.0, 1.0, 0.22, -30, 20), (3.3, -2.1, 1.1, 0.22, 30, 20)):
    shard(x, y, h, r, lx, ly, "crystal_dk" if x < 0 else "crystal")
for (x, y, h) in ((-3.7, 3.1, 1.6), (3.8, 3.2, 2.3)):
    k.cyl((x, y, PZ - 0.05), 0.4, 0.36, h, "stone_edge", segs=6)
    k.box((x + 0.1, y, PZ + h + 0.1), (0.8, 0.8, 0.22), "stone", rot=(8, -6, 20))
# shards floating in the rift's pull
for (x, y, z, sz) in ((-1.9, -0.5, 3.8, 0.5), (1.9, -0.4, 3.4, 0.45), (-1.7, -0.3, 1.2, 0.35), (1.8, -0.5, 1.6, 0.4)):
    k.cone((x, y, z), sz * 0.4, sz * 1.6, "crystal_lt", segs=4, rot=(k.rng.uniform(-40, 40), k.rng.uniform(-40, 40), 0))
    k.cone((x, y, z), sz * 0.4, sz * 1.0, "crystal_lt", segs=4, rot=(180 + k.rng.uniform(-30, 30), 0, 0))

k.meta["openings"] = [{"width": 2 * RX, "height": 2 * RZ, "depth": 0.0, "y0": 0.0, "z0": PZ, "note": "portal ellipse"}]
k.collider("platform_left", (-2.9, 0.8, 1.5), (2.4, 4.0, 3.0))
k.collider("platform_right", (2.9, 0.8, 1.5), (2.4, 4.0, 3.0))
k.collider("crystals_back", (0, 2.6, 3.0), (8.0, 2.2, 6.0))
k.trigger((0, -0.2, PZ + 1.2), (2.2, 0.8, 2.4))
k.figure((1.3, -3.4, 0.12), rot_z=-25)
k.finish()
