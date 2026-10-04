"""king_geo.py - Castle Realm #3: the King's Castle (60x60 tiles = 6.25x the Stonehaven castle's area).

A concentric royal castle in gold and blue:
  * 3-tile moat; a grand outer gatehouse (twin D-towers, royal crest, machicolations) with a 2-wide drawbridge
    and portcullis (12 frames)
  * DOUBLE curtain walls: a lower outer wall (7 m) and a taller inner wall (10 m) with an 8-tile outer bailey
    between them (tilt yard, market stalls, stables, an ENTERABLE barracks and an orchard) and an inner gatehouse
  * inner ward: a parade square with the golden statue of the king, formal gardens and banner poles
  * the King's Keep: 16x14 tiles, 4 storeys (great hall, throne room, royal apartments, battlements) and a tall
    central Great Tower. The interior floors are exactly 16x14 (inside = outside)
  * light roofs: flat battlemented roofs everywhere, with only slim blue slate cones (gold rims) on the towers
  * y-sorted layers: parts 'sort_31' (keep) and 'sort_47' (inner south wall + inner gatehouse) are rendered as
    separate sprites so players north of them are correctly hidden behind them
"""
import math
from castle_geo import (T, M, dbl, slit, merlon_row, ashlar, flag, banner, wedge, wall_torch, brazier, reeds,
                        PartKit, tower)
from rose_geo import (hedge_box, lamp_post, bench, arched_window, flower_patch, face_neg_y, face_x)
import castle_geo as base

NX = NY = 60
WATER_Z = -0.7
MOAT = 3.0
WALL_H = 7.0            # outer curtain
IWALL_H = 10.0          # inner curtain
S_WALL_OUT, S_WALL_IN = 57.0, 55.0
GATE_X0, GATE_X1 = 29.0, 31.0
HINGE_LY = 57.0
BRIDGE_L = 4.6
BRIDGE_W = 3.2
PORT_LY = 56.6
PORT_W, PORT_H, PORT_RISE = 3.1, 4.6, 3.8
PULLEY = (1.45, 0.12, 6.4)
CHAIN_L = 8.4
KEEP = (22, 17, 38, 31)            # tile edges -> 16 x 14
KH = 18.0                          # 4 storeys x 4.5 m
BARRACKS = (48, 18, 55, 34)        # tile edges -> 7 x 16 (enterable)
STABLES = (5, 18, 11, 34)
NFW = 0                            # no fountain frames on this castle

PAL = dict(base.PAL)
PAL.update({
    "cstone": "#d3c8ae", "cstone_d": "#b6aa8e", "cstone_l": "#e4dcc6", "ctrim": "#ece4d0", "cplinth": "#a99d82",
    "roof": "#3f62ad", "roof_d": "#2d4a86", "roof_edge": "#d9ac3c", "banner": "#2b4ca3", "banner_d": "#1c3474",
    "gold": "#e2b33e", "arch_brick": "#c9bb98", "court": "#cdc3aa", "court_d": "#bbb096", "grass": "#6a9446",
    "bank": "#958d77", "water": "#3f7fb0", "water_hi": "#a8d6ef", "window": "#ffd580", "glimpse": "#e6dcc0",
    "lawn": "#72a04c", "lawn_d": "#63903f", "gravel": "#ddd2b4", "hedge": "#3f6f30", "hedge_d": "#32592a",
    "vine": "#4f7d3a", "flower_p": "#e88fb0", "flower_l": "#8a9ae8", "flower_y": "#f2d25a", "rose_w": "#fbfaf3",
    "blue_cloth": "#2b4ca3", "gold_cloth": "#e0b040", "red_cloth": "#a33030", "timber": "#6a4a30", "timber_d": "#4e3522",
    "hay": "#c9a54e", "horse": "#7a5234", "horse_d": "#4a3020", "horse_w": "#e8e0d0", "trunk": "#6a5040",
    "leaf": "#4f8a3a", "leaf_d": "#3f7430", "apple": "#c83a2a", "lamp": "#2f3236", "bench": "#8a6a48", "marble": "#f0ebe0",
    "wood": "#8a6440", "plank": "#9a7048",
})
EMISSIVE = dict(base.EMISSIVE)
EMISSIVE.update({"water": 0.35, "water_hi": 0.55, "window": 2.0})

COLBOXES = [("COL_moat_n", 0, 0, 60, 3, -1, 0.2), ("COL_moat_w", 0, 3, 3, 57, -1, 0.2), ("COL_moat_e", 57, 3, 60, 57, -1, 0.2),
            ("COL_moat_sw", 0, 57, 29, 60, -1, 0.2), ("COL_moat_se", 31, 57, 60, 60, -1, 0.2),
            ("COL_owall_n", 3, 3, 57, 5, -1, 7), ("COL_owall_w", 3, 5, 5, 55, -1, 7), ("COL_owall_e", 55, 5, 57, 55, -1, 7),
            ("COL_owall_sw", 3, 55, 29, 57, -1, 7), ("COL_owall_se", 31, 55, 57, 57, -1, 7),
            ("COL_iwall_n", 13, 13, 47, 15, 0, 10), ("COL_iwall_w", 13, 15, 15, 45, 0, 10), ("COL_iwall_e", 45, 15, 47, 45, 0, 10),
            ("COL_iwall_sw", 13, 45, 29, 47, 0, 10), ("COL_iwall_se", 31, 45, 47, 47, 0, 10),
            ("COL_keep", 22, 17, 38, 31, 0, 30), ("COL_barracks", 48, 18, 55, 34, 0, 8), ("COL_stables", 5, 18, 11, 34, 0, 6),
            ("COL_gate_when_closed", 29, 56, 31, 57, 0, 4.5, "gate"),
            ("TRIGGER_gate_front", 28, 60, 32, 61, 0, 2.0, "interact"), ("TRIGGER_gate_inner", 29, 50, 31, 52, 0, 2.0, "interact")]


def crest(k, x, yf, z, s=1.0):
    """Royal crest: blue shield, gold border + crown, flanked by a gold laurel."""
    pts = [(x - 0.8 * s, yf, z + 0.9 * s), (x + 0.8 * s, yf, z + 0.9 * s), (x + 0.75 * s, yf, z - 0.2 * s), (x, yf, z - 1.0 * s),
           (x - 0.75 * s, yf, z - 0.2 * s)]
    dbl(k, [(p[0] + (p[0] - x) * 0.12, yf + 0.01, z + (p[2] - z) * 1.12) for p in pts], "gold")
    dbl(k, [(p[0], yf - 0.02, p[2]) for p in pts], "banner")
    dbl(k, [(x - 0.06 * s, yf - 0.04, z + 0.7 * s), (x + 0.06 * s, yf - 0.04, z + 0.7 * s), (x + 0.06 * s, yf - 0.04, z - 0.7 * s),
            (x - 0.06 * s, yf - 0.04, z - 0.7 * s)], "gold")
    dbl(k, [(x - 0.55 * s, yf - 0.04, z + 0.12 * s), (x + 0.55 * s, yf - 0.04, z + 0.12 * s), (x + 0.55 * s, yf - 0.04, z - 0.02 * s),
            (x - 0.55 * s, yf - 0.04, z - 0.02 * s)], "gold")
    cz = z + 1.25 * s     # crown
    dbl(k, [(x - 0.55 * s, yf - 0.02, cz - 0.2 * s), (x + 0.55 * s, yf - 0.02, cz - 0.2 * s), (x + 0.6 * s, yf - 0.02, cz + 0.35 * s),
            (x + 0.3 * s, yf - 0.02, cz + 0.1 * s), (x, yf - 0.02, cz + 0.45 * s), (x - 0.3 * s, yf - 0.02, cz + 0.1 * s),
            (x - 0.6 * s, yf - 0.02, cz + 0.35 * s)], "gold")


def royal_banner(k, x, yf, z_top, w=1.2, h=3.6):
    """Long blue banner with a gold border stripe + gold crown."""
    yy = yf - 0.08
    k.box((x, yy, z_top + 0.05), (w + 0.35, 0.1, 0.1), "gold!")
    dbl(k, [(x - w / 2, yy - 0.02, z_top), (x + w / 2, yy - 0.02, z_top), (x + w / 2, yy - 0.05, z_top - h), (x, yy - 0.07, z_top - h - 0.5),
            (x - w / 2, yy - 0.05, z_top - h)], "blue_cloth")
    for sx in (-1, 1):
        dbl(k, [(x + sx * (w / 2 - 0.12), yy - 0.03, z_top), (x + sx * w / 2, yy - 0.03, z_top), (x + sx * w / 2, yy - 0.06, z_top - h),
                (x + sx * (w / 2 - 0.12), yy - 0.06, z_top - h)], "gold_cloth")
    cz = z_top - h * 0.35
    dbl(k, [(x - 0.35, yy - 0.09, cz - 0.15), (x + 0.35, yy - 0.09, cz - 0.15), (x + 0.4, yy - 0.09, cz + 0.25), (x + 0.2, yy - 0.09, cz + 0.08),
            (x, yy - 0.09, cz + 0.32), (x - 0.2, yy - 0.09, cz + 0.08), (x - 0.4, yy - 0.09, cz + 0.25)], "gold_cloth")


def banner_pole(k, x, y, h=6.0):
    k.cyl((x, y, 0), 0.2, 0.15, 0.4, "cstone_d", 6); k.cyl((x, y, 0.4), 0.07, 0.06, h, "gold", 5)
    k.cone((x, y, h + 0.4), 0.12, 0.3, "gold", segs=5)
    flag(k, x, y, h + 0.2, length=2.0, height=1.2)


def tree(k, x, y, s=1.0, fruit=False):
    k.cyl((x, y, 0), 0.18 * s, 0.13 * s, 1.6 * s, "trunk", 6)
    for (dx, dy, dz, r) in ((0, 0, 2.2, 1.1), (0.6, 0.2, 1.9, 0.8), (-0.6, -0.1, 2.0, 0.8), (0.1, 0.3, 2.7, 0.7)):
        k.rock((x + dx * s, y + dy * s, dz * s), (r * s, r * s, r * 0.85 * s), k.rng.choice(["leaf", "leaf_d"]), sink=0.0)
    if fruit:
        for _ in range(6):
            a = k.rng.uniform(0, 6.28)
            k.box((x + math.cos(a) * 0.9 * s, y + math.sin(a) * 0.9 * s - 0.2, k.rng.uniform(1.8, 2.6) * s), (0.14, 0.14, 0.14), "apple", jitter=False)


def horse(k, x, y, mat="horse"):
    k.box((x, y, 1.0), (0.5, 1.5, 0.6), mat); k.box((x, y - 0.85, 1.45), (0.3, 0.45, 0.7), mat, rot=(25, 0, 0))
    k.box((x, y - 1.05, 1.75), (0.28, 0.55, 0.28), mat)
    for sx in (-1, 1):
        for sy in (-1, 1):
            k.box((x + sx * 0.17, y + sy * 0.55, 0.38), (0.12, 0.12, 0.76), "horse_d")
    k.box((x, y + 0.8, 1.0), (0.1, 0.2, 0.6), "horse_d")


def stall(k, x, y, cloth):
    for sx in (-1, 1):
        for sy in (-1, 1):
            k.box((x + sx * 0.9, y + sy * 0.55, 1.1), (0.1, 0.1, 2.2), "timber")
    k.box((x, y, 0.8), (2.0, 1.1, 0.1), "timber"); k.box((x, y, 0.4), (1.9, 1.0, 0.8), "timber_d")
    for i in range(5):
        k.box((x - 0.8 + i * 0.4, y - 0.1, 0.95), (0.3, 0.3, 0.2), k.rng.choice(["apple", "hay", "gold", "horse_w"]))
    for i in range(4):
        k.box((x - 0.75 + i * 0.5, y, 2.35), (0.5, 1.4, 0.08), cloth if i % 2 == 0 else "ctrim", rot=(10, 0, 0))


def dummy(k, x, y):
    k.cyl((x, y, 0), 0.07, 0.07, 1.6, "timber", 5); k.box((x, y, 1.15), (0.9, 0.12, 0.12), "timber")
    k.cyl((x, y, 0.95), 0.26, 0.24, 0.6, "hay", 6); k.box((x, y, 1.62), (0.3, 0.3, 0.32), "hay")


def statue_king(k, x, y):
    k.box((x, y, 0.6), (2.4, 2.4, 1.2), "cstone_l"); k.box((x, y, 1.25), (2.6, 2.6, 0.12), "ctrim")
    k.box((x, y, 1.9), (1.2, 1.0, 1.3), "cstone"); k.box((x, y - 0.52, 1.9), (0.6, 0.04, 0.5), "banner")
    k.box((x, y, 3.1), (0.7, 0.5, 1.2), "gold"); k.box((x, y, 3.95), (0.34, 0.34, 0.4), "gold")
    k.box((x, y + 0.25, 3.0), (0.9, 0.12, 1.4), "blue_cloth")
    k.cyl((x, y, 4.15), 0.22, 0.25, 0.15, "gold", 6)
    for i in range(5):
        a = 2 * math.pi * i / 5
        k.cone((x + math.cos(a) * 0.18, y + math.sin(a) * 0.18, 4.3), 0.05, 0.14, "gold", segs=3)
    k.box((x + 0.45, y - 0.1, 3.6), (0.08, 0.08, 1.6), "iron!", rot=(0, 15, 0))


def slim_tower(k, cx, cy, r_t, h, roof_h, **kw):
    return tower(k, cx, cy, r_t, h, roof_h, **kw)


def build(k):
    rng = k.rng
    W = NX
    wz = WATER_Z
    e = 0.3
    gc = (GATE_X0 + GATE_X1) / 2
    # ------------------------------------------------ WATER + BANKS
    k.use("water")
    ring = [((e, e), (W - e, MOAT)), ((e, S_WALL_OUT), (GATE_X0 - 0.05, W - e)), ((GATE_X1 + 0.05, S_WALL_OUT), (W - e, W - e)),
            ((GATE_X0 - 0.05, S_WALL_OUT), (GATE_X1 + 0.05, W - e)), ((e, MOAT), (MOAT, S_WALL_OUT)), ((W - MOAT, MOAT), (W - e, S_WALL_OUT))]
    for (ax, ay), (bx, by) in ring:
        a, b = M(ax, ay, wz), M(bx, by, wz)
        k.poly([(a[0], b[1], wz), (b[0], b[1], wz), (b[0], a[1], wz), (a[0], a[1], wz)], "water")
    for _ in range(110):
        side = rng.random()
        if side < 0.3:
            lx, ly = rng.uniform(0.6, W - 0.6), rng.uniform(S_WALL_OUT + 0.3, W - 0.5)
        elif side < 0.5:
            lx, ly = rng.uniform(0.6, W - 0.6), rng.uniform(0.4, MOAT - 0.3)
        elif side < 0.75:
            lx, ly = rng.uniform(0.4, MOAT - 0.3), rng.uniform(MOAT, S_WALL_OUT)
        else:
            lx, ly = rng.uniform(W - MOAT + 0.3, W - 0.4), rng.uniform(MOAT, S_WALL_OUT)
        if GATE_X0 - 0.3 < lx < GATE_X1 + 0.3 and ly > S_WALL_OUT - 0.5:
            continue
        x, y, _ = M(lx, ly)
        L = rng.uniform(0.4, 1.2)
        k.poly([(x - L / 2, y - 0.05, wz + 0.01), (x + L / 2, y - 0.05, wz + 0.01),
                (x + L / 2 - 0.1, y + 0.05, wz + 0.01), (x - L / 2 + 0.1, y + 0.05, wz + 0.01)], "water_hi")
    k.use("ground")
    for _ in range(40):     # lilies with white flowers
        side = rng.random()
        lx, ly = (rng.uniform(0.6, W - 0.6), rng.uniform(S_WALL_OUT + 0.4, W - 0.5)) if side < 0.5 else \
                 (rng.uniform(0.5, MOAT - 0.4), rng.uniform(4, S_WALL_OUT - 1)) if side < 0.75 else \
                 (rng.uniform(W - MOAT + 0.4, W - 0.5), rng.uniform(4, S_WALL_OUT - 1))
        if GATE_X0 - 0.6 < lx < GATE_X1 + 0.6 and ly > S_WALL_OUT - 0.5:
            continue
        x, y, _ = M(lx, ly)
        k.disc((x, y, 0), rng.uniform(0.24, 0.36), "lily", segs=7, z=wz + 0.03, jag=0.1)
        if rng.random() < 0.5:
            k.box((x, y, wz + 0.1), (0.16, 0.16, 0.1), "rose_w", jitter=False)

    def bank(ax, ay, bx, by, face):
        a, b = M(ax, ay), M(bx, by)
        x0, x1 = sorted((a[0], b[0])); y0, y1 = sorted((a[1], b[1]))
        k.poly([(x0, y0, 0.0), (x1, y0, 0.0), (x1, y1, 0.0), (x0, y1, 0.0)], "bank")
        if face == "N":
            q = [(x0, y1, wz - 0.1), (x0, y1, 0.0), (x1, y1, 0.0), (x1, y1, wz - 0.1)]
        elif face == "S":
            q = [(x0, y0, wz - 0.1), (x1, y0, wz - 0.1), (x1, y0, 0.0), (x0, y0, 0.0)]
        elif face == "E":
            q = [(x1, y0, wz - 0.1), (x1, y1, wz - 0.1), (x1, y1, 0.0), (x1, y0, 0.0)]
        else:
            q = [(x0, y0, wz - 0.1), (x0, y0, 0.0), (x0, y1, 0.0), (x0, y1, wz - 0.1)]
        k.add(q, [(0, 1, 2, 3)], "cstone_d")
        L = math.hypot(x1 - x0, y1 - y0)
        n = int(L / 0.9)
        for i in range(n):
            t = (i + 0.5) / n
            cx, cy = x0 + (x1 - x0) * t, y0 + (y1 - y0) * t
            if face in ("N", "S"):
                cy = y1 - 0.12 if face == "N" else y0 + 0.12
                k.box((cx, cy, 0.05), (0.8, 0.3, 0.14), "ctrim")
            else:
                cx = x1 - 0.12 if face == "E" else x0 + 0.12
                k.box((cx, cy, 0.05), (0.3, 0.8, 0.14), "ctrim")
    bank(0, 0, W, e, "S")
    bank(0, W - e, GATE_X0 - 0.35, W, "N")
    bank(GATE_X1 + 0.35, W - e, W, W, "N")
    bank(0, e, e, W - e, "E")
    bank(W - e, e, W, W - e, "W")
    a, b = M(GATE_X0 - 0.7, W - 0.35), M(GATE_X1 + 0.7, W + 0.55)
    k.box(((a[0] + b[0]) / 2, (a[1] + b[1]) / 2, -0.05), (b[0] - a[0], a[1] - b[1], 0.22), "ctrim")
    for i in range(6):
        x, y, _ = M(GATE_X0 - 0.45 + i * (GATE_X1 - GATE_X0 + 0.9) / 5, W + 0.2)
        k.box((x, y, 0.07), (0.62, 0.9, 0.06), rng.choice(["cstone_l", "cstone", "ctrim"]))
    x, y, _ = M((GATE_X0 + GATE_X1) / 2, W - 0.3)
    k.box((x, y, wz / 2 - 0.05), (BRIDGE_W + 1.6, 0.35, -wz + 0.2), "cstone_d")
    x, y, _ = M((GATE_X0 + GATE_X1) / 2, HINGE_LY + 0.08)
    k.box((x, y, (wz - 0.02) / 2), (3.3, 0.3, -wz + 0.02), "cplinth")
    for i in range(22):
        side = rng.random()
        lx, ly = (rng.uniform(0.6, W - 0.6), rng.uniform(W - 0.7, W - 0.4)) if side < 0.5 else \
                 (rng.uniform(0.3, 0.6), rng.uniform(3, W - 3)) if side < 0.75 else (rng.uniform(W - 0.6, W - 0.3), rng.uniform(3, W - 3))
        if GATE_X0 - 1 < lx < GATE_X1 + 1 and ly > W - 1:
            continue
        x, y, _ = M(lx, ly)
        reeds(k, x, y, n=7, h=1.1)

    # ------------------------------------------------ COURT (surfaces + props)
    k.use("court")
    def rectp(lx0, ly0, lx1, ly1, z, mat):
        a, b = M(lx0, ly0), M(lx1, ly1)
        k.poly([(a[0], b[1], z), (b[0], b[1], z), (b[0], a[1], z), (a[0], a[1], z)], mat)
    rectp(5, 5, 55, 55, 0.0, "lawn")                         # outer bailey = grass
    rectp(15, 15, 45, 45, 0.005, "court")                    # inner ward = paving
    for (a0, b0, a1, b1) in ((5, 47, 55, 52), (5, 5, 55, 7), (5, 5, 7, 55), (53, 5, 55, 55), (47, 13, 48, 47), (12, 13, 13, 47)):
        rectp(a0, b0, a1, b1, 0.01, "gravel")                # bailey ring road
    rectp(29, 31, 31, 57, 0.015, "gravel")                   # processional way
    rectp(24, 33, 36, 42, 0.012, "court_d")                  # parade square
    for i in range(420):
        lx, ly = rng.uniform(15.3, 44.7), rng.uniform(15.3, 44.7)
        x, y, _ = M(lx, ly); s = rng.uniform(0.5, 1.0)
        k.poly([(x - s / 2, y - s / 2, 0.02), (x + s / 2, y - s / 2, 0.02), (x + s / 2, y + s / 2, 0.02), (x - s / 2, y + s / 2, 0.02)],
               rng.choice(["court_d", "cstone_l", "gravel"]))
    x, y, _ = M(30, 38); statue_king(k, x, y)
    for (lx, ly) in ((25, 34), (35, 34), (25, 41), (35, 41), (27, 43.5), (33, 43.5)):
        x, y, _ = M(lx, ly); banner_pole(k, x, y, 6.5)
    # formal gardens either side of the keep (H tiles)
    for (a0, b0, a1, b1) in ((16, 18, 20, 28), (40, 18, 44, 28)):
        rectp(a0, b0, a1, b1, 0.03, "lawn")
        hedge_box(k, a0, b0, a1, b1, h=0.8, t=0.4)
        a, b = M(a0, b0), M(a1, b1)
        flower_patch(k, a[0] + 0.5, b[1] + 0.5, b[0] - 0.5, a[1] - 0.5, 120)
        for j in range(3):
            x, y, _ = M((a0 + a1) / 2, b0 + 2 + j * 3)
            k.cyl((x, y, 0), 0.35, 0.35, 0.3, "cstone_l", 6); k.cyl((x, y, 0.3), 0.5, 0.0, 1.9, "hedge", 6)
    for (lx, ly) in ((22, 33), (38, 33), (22, 43), (38, 43)):
        x, y, _ = M(lx, ly); lamp_post(k, x, y)
    # outer bailey: market (SW), tilt yard (SE), orchard (N), stables (W)
    for i, lx in enumerate((9, 13, 17, 21)):
        x, y, _ = M(lx, 49.5); stall(k, x, y, ["blue_cloth", "red_cloth", "gold_cloth", "blue_cloth"][i])
    for lx in (39, 41, 43, 45):
        x, y, _ = M(lx, 49.5); dummy(k, x, y)
    a, b = M(37, 48.5), M(50, 51)
    k.box(((a[0] + b[0]) / 2, (a[1] + b[1]) / 2 + 1.6, 0.5), (b[0] - a[0], 0.12, 1.0), "timber")      # tilt barrier
    for i in range(8):
        k.box((a[0] + i * (b[0] - a[0]) / 7, (a[1] + b[1]) / 2 + 1.6, 0.5), (0.14, 0.14, 1.1), "timber_d")
    for (lx, ly) in ((9, 8.5), (14, 9.5), (19, 8.5), (24, 9.5), (36, 9.5), (41, 8.5), (46, 9.5), (51, 8.5), (8.5, 40), (51.5, 40), (8.5, 44), (51.5, 44)):
        x, y, _ = M(lx, ly); tree(k, x, y, rng.uniform(0.9, 1.15), fruit=ly < 12)
    x, y, _ = M(9, 12.5)      # well
    k.cyl((x, y, 0), 0.9, 0.9, 0.8, "cstone", 10); k.disc((x, y, 0), 0.7, "water", segs=10, z=0.7, jag=0.0)
    for sx in (-1, 1):
        k.box((x + sx * 0.8, y, 1.3), (0.12, 0.12, 1.6), "timber")
    k.cyl((x, y, 2.1), 1.2, 0.0, 0.8, "roof", 4, rot=(0, 0, 45))
    # ------------------------------------------------ OUTER CURTAIN (7 m)
    k.use("body")
    zb = wz
    def wall_box(ax, ay, bx, by, h=WALL_H, mat="cstone", z0=None):
        a, b = M(ax, ay), M(bx, by)
        x0, x1 = sorted((a[0], b[0])); y0, y1 = sorted((a[1], b[1]))
        zz = zb if z0 is None else z0
        k.box(((x0 + x1) / 2, (y0 + y1) / 2, (zz + h) / 2), (x1 - x0, y1 - y0, h - zz), mat)
        return x0, x1, y0, y1
    x0, x1, y0, y1 = wall_box(5.5, 3.0, 54.5, 5.0)
    merlon_row(k, x0 + 1, x1 - 1, y1 - 0.25, WALL_H, depth=0.5)
    k.box(((x0 + x1) / 2, y0 + 0.1, WALL_H + 0.15), (x1 - x0, 0.2, 0.3), "ctrim")
    ashlar(k, x0 + 1, x1 - 1, 0.3, WALL_H - 0.3, y0, 60)
    for sgn, (ax, bx) in ((1, (3.0, 5.0)), (-1, (55.0, 57.0))):
        x0, x1, y0, y1 = wall_box(ax, 5.5, bx, 54.5)
        xo = x0 + 0.25 if sgn > 0 else x1 - 0.25
        merlon_row(k, y0 + 1, y1 - 1, xo, WALL_H, depth=0.5, along="y")
        xi = x1 - 0.1 if sgn > 0 else x0 + 0.1
        k.box((xi, (y0 + y1) / 2, WALL_H + 0.15), (0.2, y1 - y0, 0.3), "ctrim")
        xp = x0 - 0.12 if sgn > 0 else x1 + 0.12
        k.box((xp, (y0 + y1) / 2, (zb + 0.5) / 2), (0.3, y1 - y0, 0.5 - zb), "cplinth")
    for (ax, bx) in ((5.5, 23.5), (36.5, 54.5)):
        x0, x1, y0, y1 = wall_box(ax, S_WALL_IN, bx, S_WALL_OUT)
        yf = y0
        k.box(((x0 + x1) / 2, yf - 0.12, (zb + 0.9) / 2), (x1 - x0, 0.3, 0.9 - zb), "cplinth")
        k.box(((x0 + x1) / 2, yf - 0.03, 2.2), (x1 - x0, 0.1, 0.22), "gold")
        ashlar(k, x0 + 1, x1 - 1, 0.2, WALL_H - 0.5, yf, 50)
        for t in (0.25, 0.5, 0.75):
            xb = x0 + (x1 - x0) * t
            wedge(k, xb, yf, 1.25, 1.0, zb, 4.8, 1.2, "cstone")
        for t in (0.12, 0.37, 0.63, 0.88):
            slit(k, x0 + (x1 - x0) * t, yf - 0.02, 4.0)
        for t in (0.25, 0.75):
            royal_banner(k, x0 + (x1 - x0) * t, yf, WALL_H - 0.4, w=1.1, h=3.0)
        k.use("front")
        k.box(((x0 + x1) / 2, yf + 0.3, WALL_H + 0.45), (x1 - x0, 0.6, 0.9), "cstone")
        k.box(((x0 + x1) / 2, yf + 0.3, WALL_H + 0.92), (x1 - x0 + 0.02, 0.64, 0.08), "ctrim")
        merlon_row(k, x0 + 1, x1 - 1, yf + 0.3, WALL_H + 0.95, depth=0.6, h=0.8)
        k.use("body")
    RW = dict(slits=((0, 4.0), (-35, 7.0), (35, 7.0)), flag_len=1.8)
    for (cx, cy) in ((4.2, 4.2), (55.8, 4.2), (4.2, 55.8), (55.8, 55.8)):
        slim_tower(k, cx, cy, 2.2, 12.0, 5.5, segs=14, windows=((0, 9.0),), **RW)
    for (cx, cy) in ((4.0, 30.0), (56.0, 30.0), (30.0, 4.0), (17.0, 4.0), (43.0, 4.0), (4.0, 17.0), (56.0, 17.0), (4.0, 43.0), (56.0, 43.0)):
        slim_tower(k, cx, cy, 1.6, 10.0, 4.2, segs=12, flag_len=1.2, slits=((0, 4.5), (0, 7.4)))
    # ------------------------------------------------ INNER CURTAIN (10 m) - north/west/east in body
    def inner_wall(ax, ay, bx, by, along, face_sgn):
        x0, x1, y0, y1 = wall_box(ax, ay, bx, by, h=IWALL_H, z0=0.0)
        if along == "x":
            merlon_row(k, x0 + 0.8, x1 - 0.8, y1 - 0.25 if face_sgn < 0 else y0 + 0.25, IWALL_H, depth=0.5)
            merlon_row(k, x0 + 0.8, x1 - 0.8, y0 + 0.25 if face_sgn < 0 else y1 - 0.25, IWALL_H, depth=0.5, h=0.6)
            yf = y0
            k.box(((x0 + x1) / 2, yf - 0.03, 3.0), (x1 - x0, 0.1, 0.22), "gold")
            ashlar(k, x0 + 1, x1 - 1, 0.3, IWALL_H - 0.4, yf, int((x1 - x0) * 1.6))
        else:
            merlon_row(k, y0 + 0.8, y1 - 0.8, x0 + 0.25, IWALL_H, depth=0.5, along="y")
            merlon_row(k, y0 + 0.8, y1 - 0.8, x1 - 0.25, IWALL_H, depth=0.5, along="y")
        return x0, x1, y0, y1
    inner_wall(15.5, 13.0, 44.5, 15.0, "x", -1)
    x0, x1, y0, y1 = M(15.5, 13)[0], M(44.5, 13)[0], M(0, 15)[1], M(0, 13)[1]
    for t in (0.2, 0.4, 0.6, 0.8):
        royal_banner(k, x0 + (x1 - x0) * t, y0, IWALL_H - 0.6, w=1.2, h=3.6)
    inner_wall(13.0, 15.5, 15.0, 44.5, "y", 1)
    inner_wall(45.0, 15.5, 47.0, 44.5, "y", 1)
    for (cx, cy) in ((14.0, 14.0), (46.0, 14.0)):
        slim_tower(k, cx, cy, 2.0, 15.0, 6.5, segs=14, z0=0.0, windows=((0, 8.0), (-40, 11.5), (40, 11.5)), flag_len=1.8)
    # ------------------------------------------------ GRAND OUTER GATEHOUSE
    gx, gy_face, _ = M(gc, S_WALL_OUT)
    gw = 12.0 * T
    gdepth = (S_WALL_OUT - 52.0) * T
    GH = 12.0
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
              "gold" if i == nv // 2 else "cstone_l", rot=(0, -math.degrees(a) + 90, 0))
    for sx in (-1, 1):
        px, pz = gx + sx * PULLEY[0], PULLEY[2]
        k.box((px, gy_face - 0.02, pz), (0.36, 0.1, 0.4), "slit!")
        k.cyl((px, gy_face - 0.12, pz + 0.25), 0.2, 0.2, 0.12, "iron", 8, rot=(90, 0, 0))
    k.box((gx, gy_face - 0.4, 9.2), (gw - 0.4, 0.8, 1.1), "cstone")
    for i in range(13):
        k.box((gx - gw / 2 + 0.5 + i * (gw - 1.0) / 12, gy_face - 0.35, 8.4), (0.3, 0.7, 0.5), "cstone_d")
    k.box((gx, gy_face - 0.82, 9.85), (gw - 0.3, 0.1, 0.25), "gold")
    merlon_row(k, gx - gw / 2 + 0.3, gx + gw / 2 - 0.3, gy_face - 0.5, 9.75, depth=0.5, h=0.8, w=0.6, gap=0.45)
    crest(k, gx, gy_face - 0.02, 6.4, s=1.2)
    for sx in (-1, 1):
        royal_banner(k, gx + sx * 3.6, gy_face, 8.0, w=1.2, h=4.2)
        wall_torch(k, gx + sx * (hw + 0.95), gy_face, 3.3)
    k.box((gx, gy_face + 0.25, GH + 0.4), (gw, 0.5, 0.8), "cstone")
    merlon_row(k, gx - gw / 2 + 0.3, gx + gw / 2 - 0.3, gy_face + 0.25, GH + 0.8, depth=0.5, h=0.7, w=0.6, gap=0.45)
    k.box((gx, gy_face + gdepth - 0.25, GH + 0.4), (gw, 0.5, 0.8), "cstone")
    for sx in (-1, 1):
        tcx = gc + sx * 5.3
        tower(k, tcx, 56.3, 2.4, 15.0, 6.0, segs=14, slits=((0, 2.8), (-sx * 40, 5.6)), windows=((0, 10.5), (0, 7.4)), flag_len=2.0)
        x, y, _ = M(tcx, 56.3)
        royal_banner(k, x, y - 2.4 * T - 0.02, 12.8, w=1.1, h=3.4)
    # ------------------------------------------------ STABLES (west, sprite only) + BARRACKS (east, enterable)
    a, b = M(STABLES[0], STABLES[1]), M(STABLES[2], STABLES[3])
    sx0, sx1, sy1, sy0 = a[0], b[0], a[1], b[1]
    scx, scy = (sx0 + sx1) / 2, (sy0 + sy1) / 2
    k.box((sx0 + 1.2, scy, 2.0), (2.4, sy1 - sy0, 4.0), "cstone")              # back (west) wall block
    k.box((scx + 0.6, scy, 3.9), (sx1 - sx0 - 0.6, sy1 - sy0 + 0.2, 0.2), "timber_d", rot=(0, -8, 0))   # low lean-to roof
    k.box((scx + 0.6, scy, 4.02), (sx1 - sx0 - 0.8, sy1 - sy0, 0.06), "roof", rot=(0, -8, 0))
    for i in range(9):
        yy = sy0 + 0.3 + i * (sy1 - sy0 - 0.6) / 8
        k.box((sx1 - 0.3, yy, 1.8), (0.2, 0.2, 3.6), "timber")
        k.box((scx + 0.4, yy, 0.7), (sx1 - sx0 - 3.2, 0.1, 1.4), "timber_d")
        if i < 8:
            k.box((sx1 - 0.3, yy + 0.8, 0.8), (0.12, 1.4, 0.14), "timber")
            horse(k, scx + 0.9, yy + 0.8, rng.choice(["horse", "horse_d", "horse_w"])) if i % 2 == 0 else \
                k.box((scx + 0.5, yy + 0.9, 0.4), (1.2, 0.9, 0.8), "hay")
    k.box((scx, sy0 - 0.05, 2.0), (sx1 - sx0, 0.1, 4.0), "cstone_l")
    crest(k, scx, sy0 - 0.08, 2.4, s=0.6)
    a, b = M(BARRACKS[0], BARRACKS[1]), M(BARRACKS[2], BARRACKS[3])
    bx0, bx1, by1, by0 = a[0], b[0], a[1], b[1]
    bcx, bcy = (bx0 + bx1) / 2, (by0 + by1) / 2
    BH = 7.0
    k.box((bcx, bcy, BH / 2), (bx1 - bx0, by1 - by0, BH), "cstone")
    k.box((bcx, bcy, 0.4), (bx1 - bx0 + 0.25, by1 - by0 + 0.25, 0.8), "cplinth")
    k.box((bcx, by0 - 0.05, 3.5), (bx1 - bx0, 0.12, 0.2), "gold")
    merlon_row(k, bx0 + 0.4, bx1 - 0.4, by0 + 0.25, BH, depth=0.45, h=0.7)
    merlon_row(k, by0 + 0.6, by1 - 0.6, bx0 + 0.25, BH, depth=0.45, h=0.7, along="y")
    k.box((bcx, bcy, BH + 0.05), (bx1 - bx0 - 0.2, by1 - by0 - 0.2, 0.1), "court_d")
    k.box((bcx, bcy + 3.0, BH + 1.0), (2.0, 2.0, 2.0), "cstone_l")                  # small lantern / bell turret
    k.cyl((bcx, bcy + 3.0, BH + 2.0), 1.5, 0.0, 1.8, "roof", 4, rot=(0, 0, 45))
    dxb = M(51.5, 0)[0]
    k.box((dxb, by0 - 0.07, 1.4), (1.8, 0.12, 2.8), "ctrim"); k.box((dxb, by0 - 0.1, 1.25), (1.3, 0.1, 2.5), "timber_d")
    k.cyl((dxb, by0 - 0.1, 2.5), 0.65, 0.65, 0.1, "timber_d", 8, rot=(90, 0, 0))
    crest(k, dxb, by0 - 0.06, 5.2, s=0.7)
    for sx in (-1, 1):
        arched_window(k, dxb + sx * 2.6, by0, 2.2, w=0.6, h=1.2)
        arched_window(k, dxb + sx * 2.6, by0, 5.2, w=0.6, h=1.2)
        wall_torch(k, dxb + sx * 1.3, by0, 2.6)
    for i in range(6):
        arched_window(k, bx0 - 0.02, by0 + 1.5 + i * 3.6, 4.5, w=0.1, h=0.1, lit=False) if False else None
    # ------------------------------------------------ KEEP (y-sorted layer sort_31)
    k.use("sort_31")
    (kl0, kf0, kl1, kf1) = KEEP
    a, b = M(kl0, kf0), M(kl1, kf1)
    KX0, KX1, KYB, KYS = a[0], b[0], a[1], b[1]
    kcx, kcy = (KX0 + KX1) / 2, (KYB + KYS) / 2
    k.box((kcx, kcy, KH / 2), (KX1 - KX0, KYB - KYS, KH), "cstone")
    k.box((kcx, KYS - 0.15, 0.6), (KX1 - KX0 + 0.3, 0.3, 1.2), "cplinth")
    for z in (4.5, 9.0, 13.5):
        k.box((kcx, KYS - 0.07, z), (KX1 - KX0, 0.14, 0.24), "gold")
    ashlar(k, KX0 + 1, KX1 - 1, 0.5, KH - 0.5, KYS, 80)
    for fl, z in enumerate((2.4, 6.8, 11.3, 15.8)):
        for i in range(8):
            lx = kl0 + 1 + i * 2
            if 27 <= lx <= 33:
                continue
            x, _, _ = M(lx, 0)
            arched_window(k, x, KYS, z, w=0.7, h=1.8 if fl == 1 else 1.4, lit=(i + fl) % 3 != 0)
    for (xx, zz) in ((KX0 + 0.1, KH), (KX1 - 0.1, KH)):          # corner bartizans (inside the footprint)
        for yy in (KYS + 0.9, KYB - 0.9):
            k.cyl((xx, yy, zz - 2.0), 0.4, 1.0, 1.0, "cstone_d", 10)
            k.cyl((xx, yy, zz - 1.0), 1.0, 1.0, 2.2, "cstone_l", 10)
            k.cyl((xx, yy, zz + 1.2), 1.12, 0.0, 3.2, "roof", 10); k.cyl((xx, yy, zz + 1.1), 1.2, 1.12, 0.12, "roof_edge", 10)
            k.cone((xx, yy, zz + 4.35), 0.08, 0.35, "gold", segs=4)
    merlon_row(k, KX0 + 1.3, KX1 - 1.3, KYS + 0.25, KH, depth=0.5, h=0.9)
    merlon_row(k, KX0 + 1.3, KX1 - 1.3, KYB - 0.25, KH, depth=0.5, h=0.9)
    merlon_row(k, KYS + 1.5, KYB - 1.5, KX0 + 0.25, KH, depth=0.5, h=0.9, along="y")
    merlon_row(k, KYS + 1.5, KYB - 1.5, KX1 - 0.25, KH, depth=0.5, h=0.9, along="y")
    k.box((kcx, kcy, KH + 0.05), (KX1 - KX0 - 0.3, KYB - KYS - 0.3, 0.1), "court")
    # frontispiece (lx 27-33) with grand stair, portal, balcony, crest and two huge banners
    fa, fb = M(27, 0)[0], M(33, 0)[0]
    FS = KYS - 0.9
    k.box(((fa + fb) / 2, KYS - 0.45, (KH + 1.5) / 2), (fb - fa, 0.9, KH + 1.5), "cstone_l")
    merlon_row(k, fa + 0.3, fb - 0.3, FS + 0.25, KH + 1.5, depth=0.5, h=0.9)
    for z in (4.5, 9.0, 13.5):
        k.box(((fa + fb) / 2, FS - 0.05, z), (fb - fa + 0.1, 0.12, 0.24), "gold")
    for sx in (-1, 1):
        k.box(((fa + fb) / 2 + sx * ((fb - fa) / 2 - 0.25), FS - 0.12, (KH + 1.5) / 2), (0.5, 0.3, KH + 1.5), "ctrim")
        royal_banner(k, (fa + fb) / 2 + sx * 2.6, FS, 15.5, w=1.6, h=7.0)
    crest(k, (fa + fb) / 2, FS - 0.02, 14.0, s=1.6)
    dx = M(30, 0)[0]
    k.box((dx, FS - 0.06, 2.2), (3.4, 0.14, 4.4), "gold")
    k.box((dx, FS - 0.1, 1.9), (2.8, 0.12, 3.8), "timber_d")
    k.cyl((dx, FS - 0.1, 3.8), 1.4, 1.4, 0.12, "timber_d", 10, rot=(90, 0, 0))
    k.cyl((dx, FS - 0.06, 3.8), 1.75, 1.75, 0.1, "gold", 10, rot=(90, 0, 0))
    for sx in (-1, 1):
        wall_torch(k, dx + sx * 2.3, FS, 3.1)
    k.box((dx, FS - 0.75, 4.9), (5.0, 1.5, 0.3), "cstone_l")
    for i in range(14):
        k.cyl((dx - 2.3 + i * 0.35, FS - 1.4, 5.05), 0.07, 0.07, 0.8, "gold", 5)
    k.box((dx, FS - 1.4, 5.9), (5.0, 0.2, 0.14), "gold")
    arched_window(k, dx, FS, 7.4, w=1.3, h=2.4)
    arched_window(k, dx, FS, 11.3, w=1.0, h=1.8)
    # grand outside stair (rows 31-32, walkable decor)
    for i in range(4):
        x, y, _ = M(30, 31.2 + (3 - i) * 0.45)
        k.box((x, y, 0.1 + i * 0.12), (6.0 - i * 0.6, 0.5, 0.2 + i * 0.24), "cstone_l")
    # Great Tower over the crown room (lx 26-34, ly 20-28) rising to ~30 m + slim spire
    ta, tb = M(26, 20), M(34, 28)
    tx0, tx1, ty1, ty0 = ta[0], tb[0], ta[1], tb[1]
    tcx, tcy = (tx0 + tx1) / 2, (ty0 + ty1) / 2
    TH = KH + 10.0
    k.box((tcx, tcy, (KH + TH) / 2), (tx1 - tx0, ty1 - ty0, TH - KH), "cstone_l")
    k.box((tcx, ty0 - 0.05, KH + 5.0), (tx1 - tx0, 0.12, 0.24), "gold")
    for i, lx in enumerate((27.5, 30, 32.5)):
        x, _, _ = M(lx, 0)
        arched_window(k, x, ty0, KH + 2.6, w=0.8, h=1.8)
        arched_window(k, x, ty0, KH + 7.4, w=0.8, h=1.8, lit=i != 1)
    crest(k, tcx, ty0 - 0.02, KH + 5.0, s=0.0001) if False else None
    for sx in (-1, 1):
        for sy in (-1, 1):
            xx, yy = tcx + sx * ((tx1 - tx0) / 2 - 0.2), tcy + sy * ((ty1 - ty0) / 2 - 0.2)
            k.cyl((xx, yy, TH - 1.5), 0.9, 0.9, 2.6, "cstone", 10)
            k.cyl((xx, yy, TH + 1.1), 1.0, 0.0, 3.8, "roof", 10); k.cyl((xx, yy, TH + 1.0), 1.08, 1.0, 0.12, "roof_edge", 10)
            k.cone((xx, yy, TH + 4.85), 0.07, 0.35, "gold", segs=4)
    merlon_row(k, tx0 + 1.2, tx1 - 1.2, ty0 + 0.25, TH, depth=0.5, h=0.9)
    k.cyl((tcx, tcy, TH), (tx1 - tx0) * 0.33, (tx1 - tx0) * 0.33, 1.2, "cstone", 12)
    k.cyl((tcx, tcy, TH + 1.2), (tx1 - tx0) * 0.36, (tx1 - tx0) * 0.35, 0.15, "roof_edge", 12)
    k.cyl((tcx, tcy, TH + 1.35), (tx1 - tx0) * 0.35, 0.0, 6.5, "roof", 12)
    k.cone((tcx, tcy, TH + 7.8), 0.14, 0.6, "gold", segs=5)
    flag(k, tcx, tcy, TH + 10.4, length=2.6, height=1.5)
    # ------------------------------------------------ INNER SOUTH WALL + INNER GATEHOUSE (y-sorted layer sort_47)
    k.use("sort_47")
    for (ax, bx) in ((15.5, 26.5), (33.5, 44.5)):
        x0, x1, y0, y1 = wall_box(ax, 45.0, bx, 47.0, h=IWALL_H, z0=0.0)
        yf = y0
        merlon_row(k, x0 + 0.8, x1 - 0.8, yf + 0.25, IWALL_H, depth=0.5)
        merlon_row(k, x0 + 0.8, x1 - 0.8, y1 - 0.25, IWALL_H, depth=0.5, h=0.6)
        k.box(((x0 + x1) / 2, yf - 0.03, 3.0), (x1 - x0, 0.1, 0.22), "gold")
        ashlar(k, x0 + 1, x1 - 1, 0.3, IWALL_H - 0.4, yf, 30)
        for t in (0.3, 0.7):
            royal_banner(k, x0 + (x1 - x0) * t, yf, IWALL_H - 0.6, w=1.2, h=3.6)
    for (cx, cy) in ((14.0, 46.0), (46.0, 46.0)):
        slim_tower(k, cx, cy, 2.0, 15.0, 6.5, segs=14, z0=0.0, windows=((0, 8.0), (-40, 11.5), (40, 11.5)), flag_len=1.8)
    igx, igy, _ = M(gc, 47.0)
    igw = 7.0 * T
    mark = len(k.verts)
    k.archway(width=(GATE_X1 - GATE_X0) * T, spring=3.2, depth=3.0 * T, outer_w=igw, outer_h=12.0,
              front="cstone", inner=["cstone_d", "interior", "interior"], shape="round", segs=9,
              y0=0.0, z0=0.0, jag=0.0, floor="ctrim", back=False, slices=3, bulge=0.04)
    k.transform_since(mark, offset=(igx, igy, 0))
    pts = [(igx - hw, igy + 3.0 * T - 0.02, 0.0)]
    for i in range(10):
        a = math.pi * (1 - i / 9)
        pts.append((igx + hw * math.cos(a), igy + 3.0 * T - 0.02, 3.2 + hw * math.sin(a)))
    pts.append((igx + hw, igy + 3.0 * T - 0.02, 0.0))
    dbl(k, pts, "glimpse")
    merlon_row(k, igx - igw / 2 + 0.3, igx + igw / 2 - 0.3, igy + 0.25, 12.0, depth=0.5, h=0.8, w=0.6, gap=0.45)
    k.box((igx, igy - 0.05, 8.6), (igw, 0.12, 0.26), "gold")
    crest(k, igx, igy - 0.03, 6.6, s=0.9)
    for sx in (-1, 1):
        tower(k, gc + sx * 3.4, 46.4, 1.6, 14.0, 5.5, segs=12, z0=0.0, windows=((0, 9.5),), flag_len=1.5)
        wall_torch(k, igx + sx * (hw + 0.8), igy, 3.3)
    for i in range(7):     # raised inner portcullis teeth (decor)
        k.box((igx - 1.35 + i * 0.45, igy + 0.5, 4.3), (0.08, 0.1, 0.9), "iron")
    # ------------------------------------------------ POSTS (abutment pillars + braziers)
    k.use("posts")
    for sx in (-1, 1):
        x, y, _ = M(gc + sx * 1.35, W - 0.12)
        k.box((x, y, 0.55), (0.62, 0.62, 1.3), "cstone")
        k.box((x, y, 1.25), (0.78, 0.78, 0.14), "ctrim")
        brazier(k, x, y, 1.32)
    # ------------------------------------------------ GATE PARTS (local pivot space)
    k.use("bridge")
    L, Wd = BRIDGE_L, BRIDGE_W
    nb = 7
    for i in range(nb):
        bx = -Wd / 2 + (i + 0.5) * Wd / nb
        k.box((bx, -L / 2, -0.12), (Wd / nb - 0.03, L, 0.22), rng.choice(["plank", "wood", "plank"]))
    for yy in (-0.35, -L / 2, -L + 0.35):
        k.box((0, yy, 0.005), (Wd + 0.04, 0.16, 0.03), "iron!")
        k.box((0, yy, -0.245), (Wd + 0.04, 0.16, 0.03), "iron!")
    for sx in (-1, 1):
        k.box((sx * (Wd / 2 + 0.07), -L / 2, -0.1), (0.14, L, 0.3), "wood_dark")
        for j in range(6):
            k.box((sx * (Wd / 2 + 0.15), -0.3 - j * (L - 0.6) / 5, -0.08), (0.04, 0.1, 0.1), "iron!")
    for yy in (-0.9, -L / 2, -L + 0.9):
        k.box((0, yy, -0.3), (Wd, 0.22, 0.14), "wood_dark")
    for sx in (-1, 1):
        k.cyl((sx * 1.5, -L + 0.12, 0.02), 0.09, 0.09, 0.05, "iron!", 6)
    k.use("portcullis")
    nvb, nhb = 8, 7
    for i in range(nvb):
        bx = -PORT_W / 2 + (i + 0.5) * PORT_W / nvb
        k.box((bx, 0, PORT_H / 2 + 0.15), (0.1, 0.12, PORT_H - 0.3), "iron")
        k.cyl((bx, 0, 0.32), 0.07, 0.0, 0.32, "steel", segs=4, rot=(180, 0, 0))
    for j in range(nhb):
        z = 0.45 + j * (PORT_H - 0.7) / (nhb - 1)
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
