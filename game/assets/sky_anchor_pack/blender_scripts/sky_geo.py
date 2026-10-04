"""sky_geo.py - Castle Realm #4: the Sky-Anchor Citadel (48x48 tiles = 4x the Stonehaven castle's area).

A castle on a FLOATING ROCK, held down by four great iron chains:
  * ground level: 2-tile moat, pale lilac curtain walls with glowing CRYSTAL TOWERS (corners + mid-walls),
    a crystal-crowned grand gatehouse with drawbridge + portcullis (12 frames), crystal gardens and two
    chain-anchor bastions
  * the Anchor Mere under the rock - waterfalls spill off the rock into it and, through carved spouts at the
    rock's east/west tips, arc over the walls into the outer moat (6 animated frames)
  * the floating rock (top at 14 m): grass cap, earth band, craggy underside with hanging roots and glowing
    crystal shards; rock towers + back turrets, all crystal-tipped
  * the Sky Keep on the rock: 16x14 tiles, 3 storeys + the open Crystal Crown terrace (floors exactly 16x14)
  * the CHAIN-LIFT: iron lattice from the lift pier (grid row 24, the only door) up to the keep's landing balcony
  * no flat roof slabs: slim hexagonal crystal spires or battlemented terraces
  * y-sorted layer 'sort_24' = rock + keep + lift (sort row 24)
"""
import math
from castle_geo import (T, M, dbl, slit, merlon_row, ashlar, flag, wedge, wall_torch, brazier, PartKit, tower)
from rose_geo import arched_window
import castle_geo as base
import king_geo as kgeo

NX = NY = 48
WATER_Z = -0.7
MOAT = 2.0
WALL_H = 7.0
S_WALL_OUT, S_WALL_IN = 46.0, 44.0
GATE_X0, GATE_X1 = 23.0, 25.0
HINGE_LY = 46.0
BRIDGE_L = 3.1
BRIDGE_W = 3.2
PORT_LY = 45.6
PORT_W, PORT_H, PORT_RISE = 3.1, 4.6, 3.8
PULLEY = (1.45, 0.12, 6.5)
CHAIN_L = 8.0
RT = 14.0                               # rock top (m)
RCX, RCY, RX, RY = 24.0, 15.0, 18.0, 10.5  # rock superellipse (tiles)
KEEP = (16.0, 11.0, 32.0, 25.0)          # keep body edges (= grid rect 16-31 x 11-24 incl. pier)
KH = 18.0
NWF = 6                                 # waterfall frames

PAL = dict(kgeo.PAL)
PAL.update({
    "cstone": "#d9d5e4", "cstone_d": "#b5b0c6", "cstone_l": "#e9e6f1", "ctrim": "#f3f1f8", "cplinth": "#9f9ab2",
    "roof": "#7d6be0", "roof_d": "#5b4cb0", "roof_edge": "#c9ced8", "banner": "#1f8a9a", "banner_d": "#146270",
    "blue_cloth": "#1f8a9a", "gold_cloth": "#c9ced8", "gold": "#e0b84a", "silver": "#c9ced8",
    "crystal": "#6fe6ff", "crystal_v": "#b58cff", "crystal_d": "#35a9cf", "earth": "#7a5a3c", "earth_d": "#5e4430",
    "rock_u": "#6f6a78", "rock_ud": "#56515f", "grass_top": "#6fa84a", "grass_lip": "#5a9a3e", "vine": "#4f8a3a",
    "court": "#cbc8d5", "court_d": "#b9b5c6", "gravel": "#d8d4e0", "water": "#3f8fc0", "water_hi": "#a8e0f5",
    "water_fall": "#c4ecff", "foam": "#f4fbff", "iron": "#3a3d44", "chain": "#4d515b", "brass": "#c9a050",
    "window": "#bff4ff", "lawn": "#6fa84a", "lawn_d": "#5f963f", "leaf": "#4f8a3a", "leaf_d": "#3f7430",
})
EMISSIVE = dict(kgeo.EMISSIVE)
EMISSIVE.update({"crystal": 1.6, "crystal_v": 1.4, "crystal_d": 0.7, "water_fall": 0.45, "foam": 0.6, "window": 1.8,
                 "roof": 0.35})

COLBOXES = [("COL_moat_n", 0, 0, 48, 2, -1, 0.2), ("COL_moat_w", 0, 2, 2, 46, -1, 0.2), ("COL_moat_e", 46, 2, 48, 46, -1, 0.2),
            ("COL_moat_sw", 0, 46, 23, 48, -1, 0.2), ("COL_moat_se", 25, 46, 48, 48, -1, 0.2),
            ("COL_wall_n", 2, 2, 46, 4, -1, 7), ("COL_wall_w", 2, 4, 4, 44, -1, 7), ("COL_wall_e", 44, 4, 46, 44, -1, 7),
            ("COL_wall_sw", 2, 44, 23, 46, -1, 7), ("COL_wall_se", 25, 44, 46, 46, -1, 7),
            ("COL_mere", 8, 6, 40, 24, -1, 0.2), ("COL_lift_pier", 16, 24, 32, 25, -1, 15),
            ("COL_rock_and_keep", 6, 4, 42, 25, 2.0, 45), ("COL_anchor_w", 8, 26, 12, 30, 0, 3), ("COL_anchor_e", 36, 26, 40, 30, 0, 3),
            ("COL_gate_when_closed", 23, 45, 25, 46, 0, 4.5, "gate"),
            ("TRIGGER_gate_front", 22, 48, 26, 49, 0, 2.0, "interact"), ("TRIGGER_gate_inner", 23, 38, 25, 40, 0, 2.0, "interact"),
            ("TRIGGER_lift", 23, 24, 25, 25, 0, 2.0, "interact")]



def rock_xy(t, s):
    ct, st = math.cos(t), math.sin(t)
    return (RCX + RX * s * math.copysign(abs(ct) ** (2 / 3), ct), RCY + RY * s * math.copysign(abs(st) ** (2 / 3), st))


def rock_edge_y(lx):
    d = min(0.999, abs(lx - RCX) / RX)
    return RCY + RY * (1 - d ** 3) ** (1 / 3)


def add_out(k, pts, mat, centre):
    """Add a polygon oriented so its normal points away from `centre` (outward)."""
    a, b, c = pts[0], pts[1], pts[2]
    u = (b[0] - a[0], b[1] - a[1], b[2] - a[2]); v = (c[0] - a[0], c[1] - a[1], c[2] - a[2])
    n = (u[1] * v[2] - u[2] * v[1], u[2] * v[0] - u[0] * v[2], u[0] * v[1] - u[1] * v[0])
    fc = [sum(p[i] for p in pts) / len(pts) for i in range(3)]
    o = (fc[0] - centre[0], fc[1] - centre[1], fc[2] - centre[2])
    if n[0] * o[0] + n[1] * o[1] + n[2] * o[2] < 0:
        pts = pts[::-1]
    k.add(pts, [list(range(len(pts)))], mat, jitter=False)


def crystal(k, x, y, z, h, r, mat="crystal", tilt=(0, 0)):
    """Hexagonal crystal: prism + pointed tip, optionally tilted."""
    k.cyl((x, y, z), r * 0.8, r, h * 0.65, mat, 6, rot=(tilt[0], tilt[1], 0), jitter=False)
    dx = math.sin(math.radians(tilt[1])) * h * 0.65; dy = -math.sin(math.radians(tilt[0])) * h * 0.65
    k.cyl((x + dx, y + dy, z + h * 0.65 * math.cos(math.radians(max(abs(tilt[0]), abs(tilt[1]))))), r, 0.0, h * 0.35, mat, 6,
          rot=(tilt[0], tilt[1], 0), jitter=False)


def cluster(k, x, y, z, s=1.0, mats=("crystal", "crystal_v", "crystal_d")):
    rng = k.rng
    crystal(k, x, y, z, 1.6 * s, 0.22 * s, mats[0])
    for i in range(4):
        a = 2 * math.pi * i / 4 + rng.uniform(-0.4, 0.4)
        crystal(k, x + math.cos(a) * 0.25 * s, y + math.sin(a) * 0.25 * s, z, rng.uniform(0.6, 1.1) * s, 0.13 * s,
                mats[i % len(mats)], tilt=(math.sin(a) * -25, math.cos(a) * 25))


def crystal_tower(k, cx, cy, r_t, h, spire, z0=WATER_Z, mat="crystal", **kw):
    """Round pale tower (castle_geo.tower gallery) crowned by a slim glowing hexagonal crystal spire - no roof slab."""
    ztop = tower(k, cx, cy, r_t, h, 0.01, z0=z0, flag_len=0, roof_over=-0.2, **kw)
    x, y, _ = M(cx, cy)
    r = r_t * T
    k.cyl((x, y, ztop + 0.7), r * 0.62, r * 0.55, 0.6, "silver", 6, jitter=False)
    crystal(k, x, y, ztop + 1.2, spire, r * 0.48, mat)
    for i in range(3):
        a = 2 * math.pi * i / 3 + 0.5
        crystal(k, x + math.cos(a) * r * 0.55, y + math.sin(a) * r * 0.55, ztop + 1.0, spire * 0.4, r * 0.2,
                "crystal_v" if mat == "crystal" else "crystal", tilt=(math.sin(a) * -22, math.cos(a) * 22))
    for i in range(6):     # glowing band
        a = 2 * math.pi * (i + 0.5) / 6
        k.box((x + math.cos(a) * (r + 0.02), y + math.sin(a) * (r + 0.02), (z0 + h) * 0.5 + 1.5), (0.3, 0.12, 0.7), "crystal",
              rot=(0, 0, math.degrees(a) + 90), jitter=False)
    return ztop


def chain(k, p0, p1, link=0.62, w=0.3, t=0.08, mat="chain", sag=0.0):
    """Great iron chain from p0 to p1: alternating links (flattened octagon tubes) in two perpendicular planes."""
    L = math.dist(p0, p1)
    n = max(2, int(L / (link * 0.8)))
    d = [(p1[i] - p0[i]) / L for i in range(3)]
    ref = (0, 0, 1) if abs(d[2]) < 0.9 else (1, 0, 0)
    a = (d[1] * ref[2] - d[2] * ref[1], d[2] * ref[0] - d[0] * ref[2], d[0] * ref[1] - d[1] * ref[0])
    la = math.sqrt(sum(c * c for c in a)); a = [c / la for c in a]
    b = (d[1] * a[2] - d[2] * a[1], d[2] * a[0] - d[0] * a[2], d[0] * a[1] - d[1] * a[0])
    for i in range(n):
        s = (i + 0.5) / n
        c = [p0[j] + (p1[j] - p0[j]) * s for j in range(3)]
        c[2] -= sag * 4 * s * (1 - s)
        e = a if i % 2 == 0 else b
        pts = []
        for j in range(9):
            ang = 2 * math.pi * j / 8
            pts.append(tuple(c[m] + d[m] * math.cos(ang) * link / 2 + e[m] * math.sin(ang) * w / 2 for m in range(3)))
        k.tube(pts, [t] * 9, mat, segs=4, jitter=False, cap_end=False)


def anchor_emblem(k, x, yf, z, s=1.0, mat="silver"):
    """Anchor sigil on a -Y face."""
    k.box((x, yf - 0.03, z), (0.16 * s, 0.06, 1.5 * s), mat, jitter=False)
    k.box((x, yf - 0.03, z + 0.55 * s), (0.7 * s, 0.06, 0.14 * s), mat, jitter=False)
    k.cyl((x, yf - 0.03, z + 0.85 * s), 0.18 * s, 0.18 * s, 0.06, mat, 8, rot=(90, 0, 0), jitter=False)
    pts = []
    for i in range(9):
        a = math.pi * (1.1 + 0.8 * i / 8)
        pts.append((x + math.cos(a) * 0.6 * s, yf - 0.04, z - 0.35 * s + math.sin(a) * 0.45 * s))
    for i in range(8):
        k.tube([pts[i], pts[i + 1]], [0.07 * s, 0.07 * s], mat, segs=4, jitter=False)
    for sx in (-1, 1):
        k.cone((x + sx * 0.62 * s, yf - 0.04, z - 0.5 * s), 0.12 * s, 0.3 * s, mat, segs=4, jitter=False)
    k.cyl((x, yf - 0.05, z + 0.85 * s), 0.08 * s, 0.08 * s, 0.06, "crystal", 6, rot=(90, 0, 0), jitter=False)


def sky_banner(k, x, yf, z_top, w=1.1, h=3.2):
    yy = yf - 0.08
    k.box((x, yy, z_top + 0.05), (w + 0.35, 0.1, 0.1), "silver")
    dbl(k, [(x - w / 2, yy - 0.02, z_top), (x + w / 2, yy - 0.02, z_top), (x + w / 2, yy - 0.05, z_top - h), (x, yy - 0.07, z_top - h - 0.5),
            (x - w / 2, yy - 0.05, z_top - h)], "banner")
    for sx in (-1, 1):
        dbl(k, [(x + sx * (w / 2 - 0.1), yy - 0.03, z_top), (x + sx * w / 2, yy - 0.03, z_top), (x + sx * w / 2, yy - 0.06, z_top - h),
                (x + sx * (w / 2 - 0.1), yy - 0.06, z_top - h)], "silver")
    anchor_emblem(k, x, yy - 0.06, z_top - h * 0.45, s=w * 0.42)


def pine(k, x, y, z=0.0, s=1.0):
    k.cyl((x, y, z), 0.14 * s, 0.1 * s, 0.8 * s, "trunk", 5)
    for i, (r, zz) in enumerate(((0.9, 0.6), (0.7, 1.3), (0.45, 1.9))):
        k.cyl((x, y, z + zz * s), r * s, 0.0, 1.1 * s, "leaf" if i % 2 else "leaf_d", 7)


def build(k):
    rng = k.rng
    W = NX
    wz = WATER_Z
    e = 0.25
    gc = (GATE_X0 + GATE_X1) / 2
    # ------------------------------------------------ WATER: outer moat + Anchor Mere
    k.use("water")
    ring = [((e, e), (W - e, MOAT)), ((e, S_WALL_OUT), (GATE_X0 - 0.05, W - e)), ((GATE_X1 + 0.05, S_WALL_OUT), (W - e, W - e)),
            ((GATE_X0 - 0.05, S_WALL_OUT), (GATE_X1 + 0.05, W - e)), ((e, MOAT), (MOAT, S_WALL_OUT)), ((W - MOAT, MOAT), (W - e, S_WALL_OUT)),
            ((8.0, 6.0), (40.0, 24.0))]
    for (ax, ay), (bx, by) in ring:
        a, b = M(ax, ay, wz), M(bx, by, wz)
        k.poly([(a[0], b[1], wz), (b[0], b[1], wz), (b[0], a[1], wz), (a[0], a[1], wz)], "water")
    for _ in range(140):
        r_ = rng.random()
        if r_ < 0.4:
            lx, ly = rng.uniform(8.4, 39.6), rng.uniform(6.3, 23.7)
        elif r_ < 0.6:
            lx, ly = rng.uniform(0.5, W - 0.5), rng.uniform(S_WALL_OUT + 0.3, W - 0.4)
        elif r_ < 0.8:
            lx, ly = rng.uniform(0.3, MOAT - 0.3), rng.uniform(0.5, S_WALL_OUT)
        else:
            lx, ly = rng.uniform(W - MOAT + 0.3, W - 0.3), rng.uniform(0.5, S_WALL_OUT)
        if GATE_X0 - 0.3 < lx < GATE_X1 + 0.3 and ly > S_WALL_OUT - 0.5:
            continue
        x, y, _ = M(lx, ly); L = rng.uniform(0.4, 1.1)
        k.poly([(x - L / 2, y - 0.05, wz + 0.01), (x + L / 2, y - 0.05, wz + 0.01), (x + L / 2 - 0.1, y + 0.05, wz + 0.01),
                (x - L / 2 + 0.1, y + 0.05, wz + 0.01)], "water_hi")
    k.use("ground")
    def bankrect(ax, ay, bx, by):
        a, b = M(ax, ay), M(bx, by)
        k.poly([(a[0], b[1], 0.0), (b[0], b[1], 0.0), (b[0], a[1], 0.0), (a[0], a[1], 0.0)], "bank")
    bankrect(0, 0, W, e); bankrect(0, W - e, GATE_X0 - 0.35, W); bankrect(GATE_X1 + 0.35, W - e, W, W)
    bankrect(0, e, e, W - e); bankrect(W - e, e, W, W - e)
    for (ax, ay, bx, by) in ((8, 24, 40, 24.25), (7.75, 6, 8, 24.25), (40, 6, 40.25, 24.25)):
        a, b = M(ax, ay), M(bx, by)
        k.box(((a[0] + b[0]) / 2, (a[1] + b[1]) / 2, -0.25), (b[0] - a[0], a[1] - b[1], 0.9), "ctrim")
    for (lx, ly) in ((9.2, 8.0), (38.6, 8.5), (16.0, 20.2), (32.4, 19.6), (12.5, 14.0), (35.8, 14.8), (24.0, 21.5)):
        x, y, _ = M(lx, ly); cluster(k, x, y, wz, s=rng.uniform(0.8, 1.25))
    a, b = M(GATE_X0 - 0.7, W - 0.35), M(GATE_X1 + 0.7, W + 0.55)
    k.box(((a[0] + b[0]) / 2, (a[1] + b[1]) / 2, -0.05), (b[0] - a[0], a[1] - b[1], 0.22), "ctrim")
    x, y, _ = M(gc, HINGE_LY + 0.08)
    k.box((x, y, (wz - 0.02) / 2), (3.3, 0.3, -wz + 0.02), "cplinth")
    # ------------------------------------------------ COURT
    k.use("court")
    def rectp(lx0, ly0, lx1, ly1, z, mat):
        a, b = M(lx0, ly0), M(lx1, ly1)
        k.poly([(a[0], b[1], z), (b[0], b[1], z), (b[0], a[1], z), (a[0], a[1], z)], mat)
    rectp(4, 4, 8, 44, 0.0, "court"); rectp(40, 4, 44, 44, 0.0, "court"); rectp(8, 24, 40, 44, 0.0, "court")
    rectp(5, 8, 7, 22, 0.0, "court"); rectp(41, 8, 43, 22, 0.0, "court")   # under-rock walks
    rectp(23, 25, 25, 44, 0.01, "gravel"); rectp(4, 25, 44, 27, 0.008, "gravel")
    for i in range(280):
        lx, ly = rng.uniform(4.2, 43.8), rng.uniform(24.4, 43.8)
        x, y, _ = M(lx, ly); s = rng.uniform(0.5, 0.95)
        k.poly([(x - s / 2, y - s / 2, 0.02), (x + s / 2, y - s / 2, 0.02), (x + s / 2, y + s / 2, 0.02), (x - s / 2, y + s / 2, 0.02)],
               rng.choice(["court_d", "cstone_l", "gravel"]))
    for (a0, b0, a1, b1) in ((4, 32, 9, 37), (39, 32, 44, 37)):
        a, b = M(a0, b0), M(a1, b1)
        k.box(((a[0] + b[0]) / 2, (a[1] + b[1]) / 2, 0.25), (b[0] - a[0] - 0.2, a[1] - b[1] - 0.2, 0.5), "cstone_l")
        k.box(((a[0] + b[0]) / 2, (a[1] + b[1]) / 2, 0.52), (b[0] - a[0] - 0.5, a[1] - b[1] - 0.5, 0.06), "lawn")
        for j in range(5):
            x, y, _ = M(a0 + 0.7 + (j % 3) * 1.2, b0 + 0.8 + (j // 3) * 1.6)
            cluster(k, x, y, 0.55, s=0.85 + 0.15 * (j % 2))
        for _ in range(40):
            x, y, _ = M(rng.uniform(a0 + 0.4, a1 - 0.4), rng.uniform(b0 + 0.4, b1 - 0.4))
            k.box((x, y, 0.62), (0.14, 0.14, 0.14), rng.choice(["flower_l", "flower_y", "rose_w"]), jitter=False)
    for (lx, ly) in ((14.5, 30.5), (33.5, 30.5), (12.5, 38.5), (35.5, 38.5), (20.5, 34.5), (27.5, 34.5)):
        x, y, _ = M(lx, ly)
        k.cyl((x, y, 0), 0.35, 0.28, 0.9, "cstone", 8); k.cyl((x, y, 0.9), 0.3, 0.5, 0.25, "silver", 8)
        cluster(k, x, y, 1.1, s=0.55)
    anchors = []
    for lx in (10.0, 38.0):
        x, y, _ = M(lx, 28.0)
        k.box((x, y, 0.8), (3.2, 3.2, 1.6), "cstone_d"); k.box((x, y, 1.65), (3.4, 3.4, 0.14), "ctrim")
        k.box((x, y, 2.2), (2.0, 2.0, 1.0), "cstone")
        k.cyl((x - 1.0, y, 2.9), 0.7, 0.7, 1.8, "iron", 10, rot=(0, 90, 0))
        for sx in (-1, 1):
            k.box((x + sx * 1.15, y, 2.8), (0.22, 1.1, 1.5), "iron")
        k.box((x, y + 1.61, 1.1), (1.1, 0.06, 1.1), "banner")
        anchor_emblem(k, x, y + 1.59, 1.1, s=0.7)
        anchors.append((x, y, 3.5))
    # ------------------------------------------------ CURTAIN
    k.use("body")
    zb = wz
    def wall_box(ax, ay, bx, by, h=WALL_H, mat="cstone", z0=None):
        a, b = M(ax, ay), M(bx, by)
        x0, x1 = sorted((a[0], b[0])); y0, y1 = sorted((a[1], b[1]))
        zz = zb if z0 is None else z0
        k.box(((x0 + x1) / 2, (y0 + y1) / 2, (zz + h) / 2), (x1 - x0, y1 - y0, h - zz), mat)
        return x0, x1, y0, y1
    x0, x1, y0, y1 = wall_box(4.5, 2.0, 43.5, 4.0)
    merlon_row(k, x0 + 1, x1 - 1, y1 - 0.25, WALL_H, depth=0.5); merlon_row(k, x0 + 1, x1 - 1, y0 + 0.25, WALL_H, depth=0.4, h=0.6)
    ashlar(k, x0 + 1, x1 - 1, 0.3, WALL_H - 0.3, y0, 50)
    k.box(((x0 + x1) / 2, y0 - 0.03, 2.4), (x1 - x0, 0.1, 0.2), "crystal_d")
    for sgn, (ax, bx) in ((1, (2.0, 4.0)), (-1, (44.0, 46.0))):
        x0, x1, y0, y1 = wall_box(ax, 4.5, bx, 43.5)
        merlon_row(k, y0 + 1, y1 - 1, x0 + 0.25, WALL_H, depth=0.5, along="y")
        merlon_row(k, y0 + 1, y1 - 1, x1 - 0.25, WALL_H, depth=0.5, along="y", h=0.6)
        xp = x0 - 0.12 if sgn > 0 else x1 + 0.12
        k.box((xp, (y0 + y1) / 2, (zb + 0.5) / 2), (0.3, y1 - y0, 0.5 - zb), "cplinth")
    for (ax, bx) in ((4.5, 17.5), (30.5, 43.5)):
        x0, x1, y0, y1 = wall_box(ax, S_WALL_IN, bx, S_WALL_OUT)
        yf = y0
        k.box(((x0 + x1) / 2, yf - 0.12, (zb + 0.9) / 2), (x1 - x0, 0.3, 0.9 - zb), "cplinth")
        k.box(((x0 + x1) / 2, yf - 0.03, 2.2), (x1 - x0, 0.1, 0.2), "crystal_d")
        ashlar(k, x0 + 0.6, x1 - 0.6, 0.2, WALL_H - 0.5, yf, 30)
        for t in (0.25, 0.5, 0.75):
            slit(k, x0 + (x1 - x0) * t, yf - 0.02, 3.8)
        sky_banner(k, (x0 + x1) / 2, yf, WALL_H - 0.4, w=1.1, h=3.0)
        k.use("front")
        k.box(((x0 + x1) / 2, yf + 0.3, WALL_H + 0.4), (x1 - x0, 0.6, 0.8), "cstone")
        k.box(((x0 + x1) / 2, yf + 0.3, WALL_H + 0.82), (x1 - x0 + 0.02, 0.64, 0.08), "ctrim")
        merlon_row(k, x0 + 0.6, x1 - 0.6, yf + 0.3, WALL_H + 0.85, depth=0.6, h=0.75)
        k.use("body")
    RW = dict(slits=((0, 3.8),), windows=((0, 8.0),))
    crystal_tower(k, 3.0, 3.0, 2.0, 10.0, 3.6, segs=12, **RW)
    crystal_tower(k, 45.0, 3.0, 2.0, 10.0, 3.6, segs=12, **RW)
    crystal_tower(k, 3.0, 45.0, 2.0, 12.0, 7.0, segs=12, mat="crystal_v", **RW)
    crystal_tower(k, 45.0, 45.0, 2.0, 12.0, 7.0, segs=12, mat="crystal_v", **RW)
    crystal_tower(k, 3.0, 24.0, 1.6, 9.0, 3.2, segs=12, **RW)
    crystal_tower(k, 45.0, 24.0, 1.6, 9.0, 3.2, segs=12, **RW)
    crystal_tower(k, 24.0, 3.0, 1.6, 9.0, 3.2, segs=12, **RW)
    # ------------------------------------------------ GATEHOUSE
    gx, gy_face, _ = M(gc, S_WALL_OUT)
    gw = 12.0 * T
    gdepth = (S_WALL_OUT - 42.0) * T
    GH = 11.0
    mark = len(k.verts)
    k.archway(width=(GATE_X1 - GATE_X0) * T, spring=2.9, depth=gdepth, outer_w=gw, outer_h=GH,
              front="cstone", inner=["cstone_d", "interior", "interior"], shape="round", segs=9,
              y0=0.0, z0=0.0, jag=0.0, floor="ctrim", back=False, slices=3, bulge=0.04)
    k.transform_since(mark, offset=(gx, gy_face, 0))
    k.box((gx, gy_face + gdepth / 2, zb / 2), (gw, gdepth, -zb), "cplinth")
    hw = (GATE_X1 - GATE_X0) * T / 2
    pts = [(gx - hw, gy_face + gdepth - 0.02, 0.0)]
    for i in range(10):
        a = math.pi * (1 - i / 9)
        pts.append((gx + hw * math.cos(a), gy_face + gdepth - 0.02, 2.9 + hw * math.sin(a)))
    pts.append((gx + hw, gy_face + gdepth - 0.02, 0.0))
    dbl(k, pts, "glimpse")
    k.box((gx, gy_face + gdepth / 2, 0.02), (2 * hw, gdepth, 0.04), "cstone_l")
    nv = 15
    for i in range(nv):
        a = math.pi * (1 - (i + 0.5) / nv)
        rr = hw + 0.3
        k.box((gx + rr * math.cos(a), gy_face - 0.06, 2.9 + rr * math.sin(a)), (0.36, 0.14, 0.6),
              "crystal" if i == nv // 2 else "cstone_l", rot=(0, -math.degrees(a) + 90, 0))
    for sx in (-1, 1):
        px, pz = gx + sx * PULLEY[0], PULLEY[2]
        k.box((px, gy_face - 0.02, pz), (0.36, 0.1, 0.4), "slit!")
        k.cyl((px, gy_face - 0.12, pz + 0.25), 0.2, 0.2, 0.12, "iron", 8, rot=(90, 0, 0))
    k.box((gx, gy_face - 0.4, 8.6), (gw - 0.4, 0.8, 1.0), "cstone")
    for i in range(13):
        k.box((gx - gw / 2 + 0.5 + i * (gw - 1.0) / 12, gy_face - 0.35, 7.85), (0.3, 0.7, 0.5), "cstone_d")
    k.box((gx, gy_face - 0.82, 9.15), (gw - 0.3, 0.1, 0.2), "crystal_d")
    merlon_row(k, gx - gw / 2 + 0.3, gx + gw / 2 - 0.3, gy_face - 0.5, 9.1, depth=0.5, h=0.7, w=0.55, gap=0.45)
    anchor_emblem(k, gx, gy_face - 0.02, 5.8, s=1.2)
    for sx in (-1, 1):
        wall_torch(k, gx + sx * (hw + 0.95), gy_face, 3.2)
        sky_banner(k, gx + sx * 4.0, gy_face, 8.5, w=1.1, h=3.6)
    k.box((gx, gy_face + 0.25, GH + 0.35), (gw, 0.5, 0.7), "cstone")
    merlon_row(k, gx - gw / 2 + 0.3, gx + gw / 2 - 0.3, gy_face + 0.25, GH + 0.7, depth=0.5, h=0.7, w=0.55, gap=0.45)
    k.box((gx, gy_face + gdepth - 0.25, GH + 0.35), (gw, 0.5, 0.7), "cstone")
    k.box((gx, gy_face + gdepth / 2, GH + 0.05), (gw - 0.4, gdepth - 0.4, 0.1), "court_d")
    cluster(k, gx, gy_face + gdepth / 2, GH + 0.1, s=1.8)
    for sx in (-1, 1):
        crystal_tower(k, gc + sx * 5.5, 45.0, 1.7, 13.0, 4.5, segs=12, slits=((0, 2.8),), windows=((0, 9.0),))
        x, y, _ = M(gc + sx * 5.5, 45.0)
        sky_banner(k, x, y - 1.7 * T - 0.02, 10.5, w=1.0, h=3.0)
    # ------------------------------------------------ SORT_24: floating rock + keep + lift
    k.use("sort_24")
    N = 56
    levels = [(1.0, RT, "grass_lip"), (1.0, RT - 0.45, "earth"), (0.995, RT - 2.2, "earth_d"), (0.985, RT - 4.0, "rock_u"),
              (0.95, RT - 5.8, "rock_ud"), (0.86, RT - 7.0, "rock_u"), (0.66, RT - 8.2, "rock_ud"), (0.4, RT - 9.3, "rock_u"),
              (0.18, RT - 10.1, "rock_ud")]
    def under_z(s):
        for (s0, z0, _), (s1, z1, _) in zip(levels[3:], levels[4:]):
            if s1 <= s <= s0:
                return z0 + (z1 - z0) * (s0 - s) / (s0 - s1)
        return RT - 10.3
    rings = []
    for li, (s, z, _) in enumerate(levels):
        ring_ = []
        for j in range(N):
            t = 2 * math.pi * j / N
            jit = 1.0 if li < 2 else rng.uniform(0.9, 1.05)
            lx, ly = rock_xy(t, s * jit)
            x, y, _ = M(lx, ly)
            ring_.append((x, y, z + (0 if li < 2 else rng.uniform(-0.35, 0.35))))
        rings.append(ring_)
    ctr = M(RCX, RCY, RT - 4.5)
    tip = M(RCX + 0.3, RCY - 0.2, RT - 10.8)
    for li in range(len(rings) - 1):
        for j in range(N):
            j1 = (j + 1) % N
            add_out(k, [rings[li][j], rings[li][j1], rings[li + 1][j1], rings[li + 1][j]], levels[li][2], ctr)
    for j in range(N):
        add_out(k, [rings[-1][j], rings[-1][(j + 1) % N], tip], "rock_ud", ctr)
    top_c = M(RCX, RCY, RT)
    for j in range(N):
        add_out(k, [top_c, rings[0][j], rings[0][(j + 1) % N]], "grass_top", ctr)
    for _ in range(48):
        t = rng.uniform(0, 2 * math.pi) if _ < 20 else rng.uniform(0.1 * math.pi, 0.9 * math.pi)
        s = rng.uniform(0.3, 0.92)
        lx, ly = rock_xy(t, s); zz = under_z(s) - 0.2
        x, y, _ = M(lx, ly)
        k.rock((x, y, zz), (rng.uniform(0.7, 1.5), rng.uniform(0.7, 1.5), rng.uniform(0.6, 1.2)), rng.choice(["rock_u", "rock_ud"]), flat_bottom=False)
    for _ in range(30):
        t = rng.uniform(0.15 * math.pi, 0.85 * math.pi); s = rng.uniform(0.35, 0.9)
        lx, ly = rock_xy(t, s); zz = under_z(s) - 0.1
        x, y, _ = M(lx, ly)
        k.cyl((x, y, zz), rng.uniform(0.18, 0.35), 0.0, rng.uniform(1.0, 2.4), rng.choice(["crystal", "crystal_v", "crystal"]), 6,
              rot=(180 + rng.uniform(-15, 15), rng.uniform(-15, 15), 0), jitter=False)
    for _ in range(55):
        t = rng.uniform(0.08 * math.pi, 0.92 * math.pi)
        lx, ly = rock_xy(t, 1.0); x, y, _ = M(lx, ly); L = rng.uniform(1.0, 3.5)
        k.tube([(x, y - 0.05, RT - 0.3), (x + rng.uniform(-0.3, 0.3), y - 0.25, RT - 0.3 - L * 0.5),
                (x + rng.uniform(-0.4, 0.4), y - 0.2, RT - 0.3 - L)],
               [0.07, 0.05, 0.0], rng.choice(["vine", "trunk", "vine"]), segs=4, jitter=False)
    def top_rect(lx0, ly0, lx1, ly1, mat, dz=0.02):
        a, b = M(lx0, ly0), M(lx1, ly1)
        k.poly([(a[0], b[1], RT + dz), (b[0], b[1], RT + dz), (b[0], a[1], RT + dz), (a[0], a[1], RT + dz)], mat)
    top_rect(14.5, 9.5, 33.5, 24.5, "court")
    top_rect(8.0, 14.0, 40.0, 16.0, "gravel", 0.015)
    for (lx, ly, s) in ((9.5, 19.5, 1.1), (38.5, 19.8, 1.0), (10.2, 10.5, 1.0), (37.8, 10.2, 1.1), (40.5, 16.0, 0.9), (7.5, 12.5, 0.9),
                        (15.0, 8.5, 0.85), (33.0, 8.5, 0.85)):
        x, y, _ = M(lx, ly); pine(k, x, y, RT, s)
    for (lx, ly) in ((7.2, 16.5), (40.8, 12.5), (13.0, 22.5), (35.0, 22.8), (20.0, 7.5), (28.0, 7.5)):
        x, y, _ = M(lx, ly); cluster(k, x, y, RT, s=0.9)
    spouts, lips = [], []
    for sx in (-1, 1):
        lx = RCX + sx * (RX - 0.1)
        x, y, _ = M(lx, RCY)
        k.box((x + sx * 0.9, y, RT - 0.8), (2.6, 1.2, 0.5), "cstone_d")
        k.box((x + sx * 0.9, y + 0.5, RT - 0.45), (2.6, 0.2, 0.4), "cstone"); k.box((x + sx * 0.9, y - 0.5, RT - 0.45), (2.6, 0.2, 0.4), "cstone")
        k.box((x + sx * 0.9, y, RT - 0.52), (2.6, 0.8, 0.04), "water")
        spouts.append((x + sx * 2.3, y, RT - 0.55, sx))
    for lx in (12.0, 24.0, 36.0):
        ly = rock_edge_y(lx); x, y, _ = M(lx, ly)
        k.box((x, y + 0.2, RT - 0.1), (1.6, 0.9, 0.3), "cstone_d")
        k.box((x, y + 0.3, RT + 0.02), (1.2, 1.2, 0.04), "water")
        lips.append((x, y - 0.25, RT - 0.1))
    crystal_tower(k, 8.5, RCY, 1.4, RT + 9.5, 5.0, z0=RT, segs=10, windows=((0, RT + 6.0),))
    crystal_tower(k, 39.5, RCY, 1.4, RT + 9.5, 5.0, z0=RT, segs=10, windows=((0, RT + 6.0),))
    crystal_tower(k, 16.5, 6.8, 1.15, RT + 12.0, 4.5, z0=RT, segs=10, mat="crystal_v")
    crystal_tower(k, 31.5, 6.8, 1.15, RT + 12.0, 4.5, z0=RT, segs=10, mat="crystal_v")
    # Sky Keep 16x14
    a, b = M(KEEP[0], KEEP[1]), M(KEEP[2], KEEP[3])
    KX0, KX1, KYB, KYS = a[0], b[0], a[1], b[1]
    kcx, kcy = (KX0 + KX1) / 2, (KYB + KYS) / 2
    k.box((kcx, kcy, RT + KH / 2), (KX1 - KX0, KYB - KYS, KH), "cstone")
    k.box((kcx, KYS - 0.15, RT + 0.5), (KX1 - KX0 + 0.3, 0.3, 1.0), "cplinth")
    for z in (4.5, 9.0, 13.5):
        k.box((kcx, KYS - 0.07, RT + z), (KX1 - KX0, 0.14, 0.22), "crystal_d")
    ashlar(k, KX0 + 1, KX1 - 1, RT + 0.5, RT + KH - 0.5, KYS, 70)
    for fl, z in enumerate((2.4, 6.8, 11.3, 15.8)):
        for i in range(8):
            lx = KEEP[0] + 1.0 + i * 1.85
            if 21.5 < lx < 26.5 and fl == 0:
                continue
            x, _, _ = M(lx, 0)
            arched_window(k, x, KYS, RT + z, w=0.7, h=1.7 if fl == 1 else 1.35, lit=(i + fl) % 3 != 1)
    for xx in (KX0 + 0.1, KX1 - 0.1):
        for yy in (KYS + 0.9, KYB - 0.9):
            k.cyl((xx, yy, RT + KH - 2.0), 0.4, 1.0, 1.0, "cstone_d", 8)
            k.cyl((xx, yy, RT + KH - 1.0), 1.0, 1.0, 2.2, "cstone_l", 8)
            k.cyl((xx, yy, RT + KH + 1.2), 1.08, 1.08, 0.14, "silver", 8)
            crystal(k, xx, yy, RT + KH + 1.3, 2.6, 0.48, "crystal")
    merlon_row(k, KX0 + 1.3, KX1 - 1.3, KYS + 0.25, RT + KH, depth=0.5, h=0.85)
    merlon_row(k, KX0 + 1.3, KX1 - 1.3, KYB - 0.25, RT + KH, depth=0.5, h=0.85)
    merlon_row(k, KYS + 1.5, KYB - 1.5, KX0 + 0.25, RT + KH, depth=0.5, h=0.85, along="y")
    merlon_row(k, KYS + 1.5, KYB - 1.5, KX1 - 0.25, RT + KH, depth=0.5, h=0.85, along="y")
    k.box((kcx, kcy, RT + KH + 0.05), (KX1 - KX0 - 0.3, KYB - KYS - 0.3, 0.1), "court")
    dx = M(24.0, 0)[0]
    k.box((dx, KYS - 0.4, RT + (KH + 1.4) / 2), (6.5, 0.8, KH + 1.4), "cstone_l")
    FS = KYS - 0.8
    merlon_row(k, dx - 3.0, dx + 3.0, FS + 0.25, RT + KH + 1.4, depth=0.5, h=0.85)
    for sx in (-1, 1):
        sky_banner(k, dx + sx * 2.2, FS, RT + KH - 1.0, w=1.4, h=6.5)
    anchor_emblem(k, dx, FS - 0.02, RT + 12.5, s=1.7)
    arched_window(k, dx, FS, RT + 7.5, w=1.3, h=2.4)
    k.box((dx, FS - 0.06, RT + 1.8), (3.2, 0.14, 3.6), "silver"); k.box((dx, FS - 0.1, RT + 1.55), (2.6, 0.12, 3.1), "timber_d")
    k.cyl((dx, FS - 0.1, RT + 3.1), 1.3, 1.3, 0.12, "timber_d", 10, rot=(90, 0, 0))
    for sx in (-1, 1):
        wall_torch(k, dx + sx * 2.2, FS, RT + 2.8)
    # Crystal Crown chamber
    cc = M(24.0, 17.0)
    k.box((cc[0], cc[1], RT + KH + 2.0), (7.5 * T - 0.4, 7.5 * T - 0.4, 4.0), "cstone_l")
    for sx in (-1, 1):
        for sy in (-1, 1):
            k.cyl((cc[0] + sx * (3.5 * T - 0.3), cc[1] + sy * (3.5 * T - 0.3), RT + KH), 0.55, 0.55, 4.8, "cstone", 8)
            crystal(k, cc[0] + sx * (3.5 * T - 0.3), cc[1] + sy * (3.5 * T - 0.3), RT + KH + 4.8, 2.5, 0.45, "crystal_v")
    for i in range(3):
        arched_window(k, cc[0] - 3.0 + i * 3.0, cc[1] - 3.5 * T + 0.2, RT + KH + 2.1, w=1.0, h=2.0)
    k.box((cc[0], cc[1], RT + KH + 4.1), (7.5 * T, 7.5 * T, 0.2), "silver")
    merlon_row(k, cc[0] - 3.5 * T + 0.5, cc[0] + 3.5 * T - 0.5, cc[1] - 3.5 * T + 0.4, RT + KH + 4.2, depth=0.4, h=0.6)
    crystal(k, cc[0], cc[1], RT + KH + 4.2, 10.5, 1.25, "crystal")
    for i in range(6):
        a = 2 * math.pi * i / 6
        crystal(k, cc[0] + math.cos(a) * 1.6, cc[1] + math.sin(a) * 1.6, RT + KH + 4.2, 3.6, 0.45,
                "crystal_v" if i % 2 else "crystal_d", tilt=(math.sin(a) * -20, math.cos(a) * 20))
    for i in range(18):
        a = 2 * math.pi * i / 18
        k.box((cc[0] + math.cos(a) * 3.0, cc[1] + math.sin(a) * 3.0, RT + KH + 10.5), (0.55, 0.18, 0.18), "crystal",
              rot=(0, 0, math.degrees(a) + 90), jitter=False)
    flag(k, cc[0], cc[1], RT + KH + 17.0, length=2.6, height=1.5)
    # landing balcony + crane + lift
    lb0, lb1 = M(20.0, KEEP[3] - 1.0), M(28.0, 25.2)
    ly_s = lb1[1]
    k.box((dx, (lb0[1] + ly_s) / 2, RT - 0.2), (lb1[0] - lb0[0], lb0[1] - ly_s, 0.5), "cstone_l")
    for i in range(5):
        k.box((lb0[0] + 0.7 + i * (lb1[0] - lb0[0] - 1.4) / 4, (lb0[1] + ly_s) / 2, RT - 1.2), (0.4, lb0[1] - ly_s - 0.2, 1.6), "cstone_d")
    for i in range(16):
        xx = lb0[0] + 0.25 + i * (lb1[0] - lb0[0] - 0.5) / 15
        if abs(xx - dx) < 1.2: continue
        k.cyl((xx, ly_s + 0.12, RT + 0.05), 0.06, 0.06, 0.9, "silver", 5)
    k.box((dx, ly_s + 0.12, RT + 0.95), (lb1[0] - lb0[0], 0.12, 0.1), "silver")
    k.box((dx, KYS - 1.0, RT + 5.8), (0.4, 2.6, 0.4), "iron")
    wheel = (dx, ly_s + 0.1, RT + 5.8)
    k.cyl(wheel, 0.9, 0.9, 0.2, "brass", 12, rot=(0, 90, 0))
    k.cyl(wheel, 0.2, 0.2, 0.35, "iron", 8, rot=(0, 90, 0))
    p_ = [M(21.2, 24.15), M(26.8, 24.15), M(21.2, 24.95), M(26.8, 24.95)]
    for (x, y, _) in p_:
        k.box((x, y, (RT + 0.5) / 2 - 0.2), (0.24, 0.24, RT + 1.0), "iron")
    zz = 0.3
    while zz < RT - 0.5:
        for (i0, i1) in ((0, 1), (2, 3), (0, 2), (1, 3)):
            a0, a1 = p_[i0], p_[i1]
            k.box(((a0[0] + a1[0]) / 2, (a0[1] + a1[1]) / 2, zz), (abs(a1[0] - a0[0]) + 0.2, abs(a1[1] - a0[1]) + 0.2, 0.1), "iron", jitter=False)
        a0, a1 = p_[2], p_[3]
        k.tube([(a0[0], a0[1] - 0.05, zz), (a1[0], a1[1] - 0.05, zz + 2.2)], [0.05, 0.05], "iron", segs=4, jitter=False)
        k.tube([(a1[0], a1[1] - 0.05, zz), (a0[0], a0[1] - 0.05, zz + 2.2)], [0.05, 0.05], "iron", segs=4, jitter=False)
        zz += 2.2
    cx_, cy_ = dx, (p_[0][1] + p_[2][1]) / 2
    cz0 = 5.2
    k.box((cx_, cy_, cz0), (3.0, 1.1, 0.14), "brass"); k.box((cx_, cy_, cz0 + 2.5), (3.0, 1.1, 0.14), "brass")
    for sx in (-1.4, -0.7, 0, 0.7, 1.4):
        k.box((cx_ + sx, cy_ - 0.52, cz0 + 1.25), (0.06, 0.06, 2.5), "brass", jitter=False)
    k.cyl((cx_, cy_, cz0 + 2.57), 1.0, 0.0, 0.8, "brass", 8)
    k.box((cx_, cy_, cz0 + 1.6), (0.35, 0.35, 0.45), "crystal")
    k.box((cx_ - 0.5, cy_ - 0.1, cz0 + 0.6), (0.4, 0.35, 0.9), "blue_cloth")
    chain(k, (cx_, cy_, cz0 + 3.3), (wheel[0], wheel[1] - 0.2, wheel[2] - 0.8), link=0.38, w=0.2, t=0.045)
    k.box((M(27.5, 0)[0], cy_, 9.5), (0.55, 0.55, 1.5), "iron"); k.box((M(27.5, 0)[0], cy_, 10.3), (0.6, 0.6, 0.1), "brass")
    chain(k, (M(27.5, 0)[0], cy_, 10.35), (wheel[0] + 0.7, wheel[1], wheel[2]), link=0.38, w=0.2, t=0.045)
    a, b = M(16.0, 24.0), M(32.0, 25.0)
    k.box(((a[0] + b[0]) / 2, (a[1] + b[1]) / 2, (wz + 0.4) / 2), (b[0] - a[0], a[1] - b[1], 0.4 - wz), "cstone_l")
    k.box(((a[0] + b[0]) / 2, b[1] + 0.05, 0.35), (b[0] - a[0], 0.14, 0.14), "ctrim")
    for sx in (-1, 1):
        k.box((dx + sx * 2.0, b[1] + 0.1, 1.8), (0.35, 0.35, 3.6), "silver")
        k.cone((dx + sx * 2.0, b[1] + 0.1, 3.6), 0.22, 0.55, "crystal", segs=6)
    k.box((dx, b[1] + 0.1, 3.5), (4.2, 0.22, 0.22), "silver")
    anchor_emblem(k, dx, b[1] + 0.02, 2.8, s=0.45)
    for i in range(9):
        k.box((dx - 1.6 + i * 0.4, b[1] + 0.12, 1.5), (0.05, 0.05, 2.8), "brass", jitter=False)
    # four great chains
    for (lx, ly, zr), anc in zip(((12.5, 20.5, RT - 8.0), (35.5, 20.5, RT - 8.0)), anchors):
        x, y, _ = M(lx, ly)
        k.box((x, y, zr + 0.2), (1.1, 1.1, 0.7), "iron")
        chain(k, (x, y, zr), (anc[0] - 0.9, anc[1], anc[2] - 0.5), link=0.85, w=0.45, t=0.11, sag=0.7)
    for (lx, ly, tx) in ((14.0, 7.5, 10.0), (34.0, 7.5, 38.0)):
        x, y, _ = M(lx, ly); xa, ya, _ = M(tx, 3.0)
        chain(k, (x, y, RT - 8.0), (xa, ya, WALL_H + 0.5), link=0.85, w=0.45, t=0.11, sag=0.35)
        k.box((xa, ya, WALL_H + 0.4), (1.1, 1.1, 0.7), "iron")
    # ------------------------------------------------ WATERFALLS
    falls = []
    for (x, y, z) in lips:
        path = [(x, y, z), (x, y - 0.4, z - 0.5), (x, y - 0.7, z - 2.0), (x, y - 0.85, z - 5.0), (x, y - 0.9, wz + 0.05)]
        falls.append((path, 1.15, "x"))
    for (x, y, z, sx) in spouts:
        pts = []
        for i in range(10):
            t = i / 9
            pts.append((x + sx * 2.4 * math.sqrt(t), y, z - (z - wz - 0.05) * t))
        falls.append((pts, 0.85, "y"))
    for f in range(NWF):
        k.use("wfall_%d" % f)
        ph = f / NWF
        for (path, w, ax) in falls:
            def off(p, s, ax=ax):
                return (p[0] + (s if ax == "x" else 0), p[1] + (s if ax == "y" else 0), p[2])
            for i in range(len(path) - 1):
                q = [off(path[i], -w / 2), off(path[i], w / 2), off(path[i + 1], w / 2 + 0.1), off(path[i + 1], -w / 2 - 0.1)]
                dbl(k, q, "water_fall")
            L = len(path) - 1
            for sidx in range(8):
                for rep_ in range(3):
                    t = (ph + rep_ / 3 + sidx * 0.137) % 1.0
                    fi = t * L; i0 = min(int(fi), L - 1); fr = fi - i0
                    p = [path[i0][m] + (path[i0 + 1][m] - path[i0][m]) * fr for m in range(3)]
                    s = -w / 2 + (sidx + 0.5) * w / 8
                    pp = off(p, s)
                    k.box((pp[0], pp[1] - (0.06 if ax == "x" else 0), pp[2]), (0.12, 0.12, 0.5), "foam", jitter=False)
            bx_, by_, _ = path[-1]
            for i in range(8):
                a = 2 * math.pi * i / 8 + ph * 2.0
                rr = 0.35 + 0.55 * ((ph + i * 0.19) % 1.0)
                k.rock((bx_ + math.cos(a) * rr, by_ + math.sin(a) * rr * 0.6, wz + 0.1),
                       (0.32, 0.32, 0.22 + 0.15 * math.sin(2 * math.pi * (ph + i / 8))), "foam", flat_bottom=True, jitter=False)
    # ------------------------------------------------ POSTS + GATE PARTS
    k.use("posts")
    for sx in (-1, 1):
        x, y, _ = M(gc + sx * 1.35, W - 0.12)
        k.box((x, y, 0.55), (0.62, 0.62, 1.3), "cstone")
        k.box((x, y, 1.25), (0.78, 0.78, 0.14), "ctrim")
        cluster(k, x, y, 1.32, s=0.55)
    k.use("bridge")
    L, Wd = BRIDGE_L, BRIDGE_W
    for i in range(7):
        bx = -Wd / 2 + (i + 0.5) * Wd / 7
        k.box((bx, -L / 2, -0.12), (Wd / 7 - 0.03, L, 0.22), rng.choice(["plank", "wood", "plank"]))
    for yy in (-0.35, -L / 2, -L + 0.35):
        k.box((0, yy, 0.005), (Wd + 0.04, 0.16, 0.03), "iron!")
        k.box((0, yy, -0.245), (Wd + 0.04, 0.16, 0.03), "iron!")
    for sx in (-1, 1):
        k.box((sx * (Wd / 2 + 0.07), -L / 2, -0.1), (0.14, L, 0.3), "wood_dark")
    for yy in (-0.8, -L + 0.8):
        k.box((0, yy, -0.3), (Wd, 0.22, 0.14), "wood_dark")
    for sx in (-1, 1):
        k.cyl((sx * 1.5, -L + 0.12, 0.02), 0.09, 0.09, 0.05, "iron!", 6)
    k.use("portcullis")
    for i in range(8):
        bx = -PORT_W / 2 + (i + 0.5) * PORT_W / 8
        k.box((bx, 0, PORT_H / 2 + 0.15), (0.1, 0.12, PORT_H - 0.3), "iron")
        k.cyl((bx, 0, 0.32), 0.07, 0.0, 0.32, "steel", segs=4, rot=(180, 0, 0))
    for j in range(7):
        z = 0.45 + j * (PORT_H - 0.7) / 6
        k.box((0, 0.0, z), (PORT_W, 0.1, 0.1), "iron")
    k.box((0, 0, PORT_H - 0.05), (PORT_W + 0.1, 0.16, 0.18), "iron!")
    for side in ("chain_l", "chain_r"):
        k.use(side)
        n = int(CHAIN_L / 0.16)
        for i in range(n):
            z = 0.08 + i * 0.16
            k.box((0, 0, z), (0.15, 0.05, 0.21) if i % 2 == 0 else (0.05, 0.15, 0.21), "chain", jitter=False)
    k.use("body")
    return {"gate_centre_x_m": gx, "gate_face_y_m": gy_face, "keep_h": KH, "gatehouse_h": GH}
