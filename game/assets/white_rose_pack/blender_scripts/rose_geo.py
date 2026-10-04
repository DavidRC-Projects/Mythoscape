"""rose_geo.py - Castle Realm #2: the White Rose Castle (48x48 tiles = 4x the Stonehaven castle's area).

A new layout, not a re-skin:
  * 3-tile moat ring; the 2-wide drawbridge spans all 3 tiles into a twin-towered south gatehouse
  * chamfered white curtain with 4 big corner towers and 2 mid-wall towers, all with dusty-rose roofs
  * outer ward (south): pergola walk from the gate, a flower-border plaza
  * central walled rose garden: 4 hedged beds of white roses and flowers around a 3-tier fountain
    (6 animated water frames: part fwater_0..5)
  * west: glass Rose Nursery; east: Chapel of the White Rose with a bell-cote
  * north: the Rose Palace keep, 24x11 tiles and 4 storeys. Its interior floors use the SAME 24x11
    footprint (no inside/outside scale mismatch). It has a roof terrace with a glass conservatory,
    a stair-head hut and 4 corner belvederes.
White stone everywhere and climbing white roses on the walls.
"""
import math
from castle_geo import (T, M, dbl, slit, merlon_row, ashlar, flag, banner, wedge, wall_torch, brazier, reeds,
                        PartKit, tower)
import castle_geo as base

NX = NY = 48
WATER_Z = -0.7
WALL_H = 7.0
MOAT = 3.0
S_WALL_OUT, S_WALL_IN = 45.0, 43.0
GATE_X0, GATE_X1 = 23.0, 25.0
HINGE_LY = 45.0
BRIDGE_L = 4.6
BRIDGE_W = 3.2
PORT_LY = 44.6
PORT_W, PORT_H, PORT_RISE = 3.1, 4.6, 3.8
PULLEY = (1.45, 0.12, 6.0)
CHAIN_L = 8.2
KEEP = (12, 5, 36, 16)          # lx0, ly0, lx1, ly1 (tile edges) -> 24 x 11 tiles
KH = 16.8                       # 4 storeys x 4.2 m
FOUNTAIN = (24.0, 28.0)         # centre (tile edge between cols 23|24, rows 27|28)
NFW = 6                         # fountain water frames

PAL = dict(base.PAL)
PAL.update({
    "cstone": "#e6e2d8", "cstone_d": "#cbc5b8", "cstone_l": "#f5f2ea", "ctrim": "#d8cdb2", "cplinth": "#bab3a4",
    "roof": "#b98488", "roof_d": "#976569", "roof_edge": "#d9b9b4", "banner": "#3d6b3a", "banner_d": "#284a26",
    "arch_brick": "#d9cfb9", "court": "#d9d1bd", "court_d": "#c7bea8", "grass": "#6c9a48", "bank": "#9a9380",
    "water": "#4c90b8", "water_hi": "#b5e0f2", "window": "#ffd98a", "glimpse": "#e8e0c8",
    "vine": "#4f7d3a", "vine_d": "#3b6530", "rose_w": "#fbfaf3", "rose_c": "#efe2a8", "hedge": "#4a7a36",
    "hedge_d": "#3a6329", "gravel": "#e0d6bd", "lawn": "#79a852", "lawn_d": "#6a9846", "flower_p": "#e88fb0",
    "flower_l": "#a58ad8", "flower_y": "#f2d25a", "marble": "#f2efe8", "marble_d": "#d8d3c8", "glass": "#bfe3ea",
    "glass_d": "#8fc0cc", "glass_frame": "#f0ede4", "water_fall": "#cdeefa", "foam": "#ffffff", "bench": "#8a6a48",
    "lamp": "#2f3236", "blossom": "#fff6f4", "trunk": "#6a5040", "wood": "#8a6440", "plank": "#9a7048",
})
EMISSIVE = dict(base.EMISSIVE)
EMISSIVE.update({"water": 0.35, "water_hi": 0.6, "water_fall": 0.55, "foam": 0.4, "window": 2.0, "glass": 0.25})

COLBOXES = [("COL_moat_n", 0, 0, 48, 3, -1, 0.2), ("COL_moat_w", 0, 3, 3, 45, -1, 0.2), ("COL_moat_e", 45, 3, 48, 45, -1, 0.2),
            ("COL_moat_sw", 0, 45, 23, 48, -1, 0.2), ("COL_moat_se", 25, 45, 48, 48, -1, 0.2),
            ("COL_wall_n", 3, 3, 45, 5, -1, 7), ("COL_wall_w", 3, 5, 5, 43, -1, 7), ("COL_wall_e", 43, 5, 45, 43, -1, 7),
            ("COL_wall_sw", 3, 43, 23, 45, -1, 7), ("COL_wall_se", 25, 43, 45, 45, -1, 7),
            ("COL_keep", 12, 5, 36, 16, 0, 22), ("COL_fountain", 21, 25, 27, 31, 0, 3),
            ("COL_nursery", 6, 19, 12, 31, 0, 5), ("COL_chapel", 37, 19, 43, 32, 0, 9),
            ("COL_gate_when_closed", 23, 44, 25, 45, 0, 4.5, "gate"),
            ("TRIGGER_gate_front", 22, 48, 26, 49, 0, 2.0, "interact"), ("TRIGGER_gate_inner", 23, 41, 25, 43, 0, 2.0, "interact")]


# ----------------------------------------------------------------- helpers
def roses_on_face(k, p, u0, u1, z0, z1, n_patch=3, density=1.0):
    """Climbing white roses on a wall face. p(u, z, d) -> xyz, where d is the offset out of the face."""
    rng = k.rng
    for _ in range(n_patch):
        uc = rng.uniform(u0 + 0.6, u1 - 0.6)
        w = rng.uniform(1.0, 2.2)
        top = rng.uniform(z0 + 1.8, z1)
        # vine stems
        for s in range(3):
            us = uc + rng.uniform(-w / 2, w / 2)
            q = [p(us - 0.04, z0, 0.05), p(us + 0.04, z0, 0.05), p(us + 0.04 + rng.uniform(-0.3, 0.3), top, 0.05),
                 p(us - 0.04 + rng.uniform(-0.3, 0.3), top, 0.05)]
            k.add(q, [(0, 1, 2, 3), (3, 2, 1, 0)], "vine_d")
        # leaf clumps
        nl = int(10 * w * density)
        for _ in range(nl):
            uu = uc + rng.uniform(-w / 2, w / 2)
            zz = rng.uniform(z0 + 0.2, top)
            s = rng.uniform(0.28, 0.5)
            q = [p(uu - s, zz - s * 0.6, 0.07), p(uu + s * 0.8, zz - s * 0.7, 0.08), p(uu + s, zz + s * 0.6, 0.07),
                 p(uu - s * 0.7, zz + s * 0.7, 0.08)]
            k.add(q, [(0, 1, 2, 3), (3, 2, 1, 0)], rng.choice(["vine", "vine", "vine_d", "hedge"]))
        # white blossoms
        for _ in range(int(9 * w * density)):
            uu = uc + rng.uniform(-w / 2, w / 2)
            zz = rng.uniform(z0 + 0.4, top)
            c = p(uu, zz, 0.14)
            k.box(c, (0.2, 0.2, 0.2), "rose_w", jitter=False)
            if rng.random() < 0.4:
                k.box(p(uu, zz, 0.2), (0.07, 0.07, 0.07), "rose_c", jitter=False)


def face_neg_y(yf):          # face looking at the camera (-Y), u = x
    return lambda u, z, d: (u, yf - d, z)


def face_x(xf, sgn):         # face looking +X (sgn=1) or -X (sgn=-1), u = y
    return lambda u, z, d: (xf + sgn * d, u, z)


def rose_bush(k, x, y, s=1.0):
    k.rock((x, y, 0.35 * s), (0.55 * s, 0.5 * s, 0.45 * s), k.rng.choice(["hedge", "vine"]), sink=0.05)
    for _ in range(int(7 * s)):
        a = k.rng.uniform(0, 2 * math.pi); r = k.rng.uniform(0.1, 0.45) * s
        k.box((x + math.cos(a) * r, y + math.sin(a) * r, k.rng.uniform(0.45, 0.8) * s), (0.17, 0.17, 0.15), "rose_w", jitter=False)


def flower_patch(k, x0, y0, x1, y1, n):
    for _ in range(n):
        x, y = k.rng.uniform(x0, x1), k.rng.uniform(y1, y0) if y0 > y1 else k.rng.uniform(y0, y1)
        k.box((x, y, 0.12), (0.06, 0.06, 0.24), "vine", jitter=False)
        k.box((x, y, 0.28), (0.18, 0.18, 0.1), k.rng.choice(["flower_p", "flower_l", "flower_y", "rose_w"]), jitter=False)


def hedge_box(k, lx0, ly0, lx1, ly1, h=0.7, t=0.45):
    a, b = M(lx0, ly0), M(lx1, ly1)
    x0, x1 = a[0], b[0]; y1, y0 = a[1], b[1]
    cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
    for (c, s) in (((cx, y1 - t / 2), (x1 - x0, t)), ((cx, y0 + t / 2), (x1 - x0, t)),
                   ((x0 + t / 2, cy), (t, y1 - y0)), ((x1 - t / 2, cy), (t, y1 - y0))):
        k.box((c[0], c[1], h / 2), (s[0], s[1], h), "hedge")
        k.box((c[0], c[1], h + 0.03), (s[0] * 0.98, s[1] * 0.9, 0.06), "hedge_d")


def lamp_post(k, x, y):
    k.cyl((x, y, 0), 0.16, 0.12, 0.3, "lamp", 6); k.cyl((x, y, 0.3), 0.06, 0.06, 2.5, "lamp", 5)
    k.box((x, y, 2.95), (0.34, 0.34, 0.42), "window"); k.cone((x, y, 3.15), 0.3, 0.35, "lamp", segs=4)


def bench(k, x, y, rot=0):
    k.box((x, y, 0.42), (1.5, 0.45, 0.08), "bench", rot=(0, 0, rot))
    k.box((x, y, 0.21), (1.3, 0.3, 0.42), "cstone_d", rot=(0, 0, rot))


def blossom_tree(k, x, y, s=1.0):
    k.cyl((x, y, 0), 0.18 * s, 0.12 * s, 1.8 * s, "trunk", 6)
    for (dx, dy, dz, r) in ((0, 0, 2.3, 1.1), (0.6, 0.2, 2.0, 0.8), (-0.6, -0.1, 2.1, 0.8), (0.1, 0.4, 2.8, 0.7)):
        k.rock((x + dx * s, y + dy * s, dz * s), (r * s, r * s, r * 0.8 * s), "blossom", sink=0.0)


def arched_window(k, x, yf, z, w=0.8, h=1.5, lit=True):
    k.box((x, yf - 0.04, z), (w + 0.3, 0.1, h + 0.1), "ctrim")
    k.box((x, yf - 0.07, z - 0.05), (w, 0.1, h - 0.1), "window" if lit else "slit!")
    k.cyl((x, yf - 0.07, z + h / 2 - 0.1), w / 2, w / 2, 0.1, "window" if lit else "slit!", 8, rot=(90, 0, 0), jitter=False)
    k.cyl((x, yf - 0.04, z + h / 2 - 0.1), w / 2 + 0.15, w / 2 + 0.15, 0.08, "ctrim", 8, rot=(90, 0, 0), jitter=False)
    k.box((x, yf - 0.13, z - h / 2 - 0.05), (w + 0.4, 0.22, 0.12), "cstone_l")


def rose_emblem(k, x, yf, z, r=0.9):
    k.cyl((x, yf - 0.02, z), r + 0.2, r + 0.2, 0.08, "ctrim", 12, rot=(90, 0, 0), jitter=False)
    k.cyl((x, yf - 0.06, z), r, r, 0.06, "banner", 12, rot=(90, 0, 0), jitter=False)
    for i in range(5):
        a = 2 * math.pi * i / 5 + math.pi / 2
        k.cyl((x + math.cos(a) * r * 0.42, yf - 0.1, z + math.sin(a) * r * 0.42), r * 0.34, r * 0.34, 0.05, "rose_w", 7,
              rot=(90, 0, 0), jitter=False)
    k.cyl((x, yf - 0.13, z), r * 0.22, r * 0.22, 0.05, "rose_c", 7, rot=(90, 0, 0), jitter=False)


def pink_cone_tower(k, cx, cy, r_t, h, roof_h, segs=12, flag_len=1.6, windows=(), slits=()):
    return tower(k, cx, cy, r_t, h, roof_h, segs=segs, flag_len=flag_len, windows=windows, slits=slits)


# ----------------------------------------------------------------- build
def build(k):
    rng = k.rng
    W = NX
    wz = WATER_Z
    e = 0.3
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

    # ------------------------------------------------ COURT (bailey surfaces, gardens, fountain, props)
    k.use("court")
    def rectp(lx0, ly0, lx1, ly1, z, mat):
        a, b = M(lx0, ly0), M(lx1, ly1)
        k.poly([(a[0], b[1], z), (b[0], b[1], z), (b[0], a[1], z), (a[0], a[1], z)], mat)
    rectp(5, 5, 43, 43, 0.0, "court")
    for i in range(260):     # flagstone variation
        lx, ly = rng.uniform(5.3, 42.7), rng.uniform(5.3, 42.7)
        x, y, _ = M(lx, ly)
        s = rng.uniform(0.5, 1.0)
        k.poly([(x - s / 2, y - s / 2, 0.005), (x + s / 2, y - s / 2, 0.005), (x + s / 2, y + s / 2, 0.005), (x - s / 2, y + s / 2, 0.005)],
               rng.choice(["court_d", "cstone_l", "gravel"]))
    # garden square: lawn + gravel cross + fountain ring
    rectp(13, 18, 35, 38, 0.01, "lawn")
    rectp(22.6, 16, 25.4, 45, 0.02, "gravel")
    rectp(13, 26.6, 35, 29.4, 0.02, "gravel")
    fx, fy, _ = M(*FOUNTAIN)
    k.disc((fx, fy, 0), 7.4, "gravel", segs=16, z=0.025, jag=0.0)
    pass  # (no outer garden hedge: keeps the 4 path openings clear)
    # four beds (H tiles): hedged, white roses + flower mixes
    beds = [(14, 20, 21, 26), (27, 20, 34, 26), (14, 30, 21, 36), (27, 30, 34, 36)]
    for (a0, b0, a1, b1) in beds:
        rectp(a0, b0, a1, b1, 0.03, "mud")
        hedge_box(k, a0, b0, a1, b1, h=0.75, t=0.42)
        for i in range(int((a1 - a0) - 1)):
            for j in range(int((b1 - b0) - 1)):
                x, y, _ = M(a0 + 1 + i, b0 + 1 + j)
                if (i + j) % 2 == 0:
                    rose_bush(k, x + rng.uniform(-0.2, 0.2), y + rng.uniform(-0.2, 0.2), s=rng.uniform(0.9, 1.2))
                else:
                    flower_patch(k, x - 0.6, y - 0.6, x + 0.6, y + 0.6, 8)
        # topiary cones on bed corners
        for (cx, cy) in ((a0 + 0.3, b0 + 0.3), (a1 - 0.3, b0 + 0.3), (a0 + 0.3, b1 - 0.3), (a1 - 0.3, b1 - 0.3)):
            x, y, _ = M(cx, cy)
            k.cyl((x, y, 0), 0.35, 0.35, 0.3, "cstone_l", 6)
            k.cyl((x, y, 0.3), 0.45, 0.0, 1.6, "hedge", 6)
    # fountain: octagonal basin + 2 tiers + rose finial (water frames in fwater_*)
    k.cyl((fx, fy, 0), 4.7, 4.6, 0.75, "marble", 16, jitter=False)
    k.cyl((fx, fy, 0.75), 4.75, 4.75, 0.12, "marble_d", 16, jitter=False)
    k.disc((fx, fy, 0), 4.3, "water", segs=16, z=0.88, jag=0.0)
    k.cyl((fx, fy, 0.8), 0.75, 0.6, 1.1, "marble", 8)
    k.cyl((fx, fy, 1.8), 0.55, 2.1, 0.5, "marble", 12)
    k.disc((fx, fy, 0), 1.9, "water", segs=12, z=2.32, jag=0.0)
    k.cyl((fx, fy, 2.3), 0.35, 0.3, 1.0, "marble_d", 8)
    k.cyl((fx, fy, 3.25), 0.3, 1.15, 0.35, "marble", 10)
    k.disc((fx, fy, 0), 1.0, "water", segs=10, z=3.62, jag=0.0)
    for i in range(6):   # rose finial petals
        a = 2 * math.pi * i / 6
        k.box((fx + math.cos(a) * 0.22, fy + math.sin(a) * 0.22, 3.95), (0.28, 0.12, 0.4), "rose_w", rot=(0, 25, math.degrees(a) + 90))
    k.cyl((fx, fy, 3.7), 0.16, 0.12, 0.45, "rose_c", 6)
    for i in range(8):   # basin corner spouts (swans)
        a = 2 * math.pi * (i + 0.5) / 8
        sx, sy = fx + math.cos(a) * 4.55, fy + math.sin(a) * 4.55
        k.box((sx, sy, 1.05), (0.35, 0.35, 0.35), "marble")
        k.cyl((sx, sy, 1.2), 0.08, 0.06, 0.45, "marble", 5)
    # animated water: curtains, jet, ripples, foam
    for f in range(NFW):
        k.use("fwater_%d" % f)
        ph = f / NFW
        for (r0, z0, r1, z1, n) in ((2.05, 2.32, 2.6, 0.9, 20), (1.1, 3.62, 1.45, 2.34, 12)):
            for i in range(n):
                a0, a1 = 2 * math.pi * i / n, 2 * math.pi * (i + 1) / n
                q = [(fx + math.cos(a0) * r1, fy + math.sin(a0) * r1, z1), (fx + math.cos(a1) * r1, fy + math.sin(a1) * r1, z1),
                     (fx + math.cos(a1) * r0, fy + math.sin(a1) * r0, z0), (fx + math.cos(a0) * r0, fy + math.sin(a0) * r0, z0)]
                k.add(q, [(0, 1, 2, 3), (3, 2, 1, 0)], "water_fall")
                # moving streaks
                for s in range(2):
                    t = (ph + s * 0.5 + (i % 3) * 0.17) % 1.0
                    am = (a0 + a1) / 2
                    rr, zz = r0 + (r1 - r0) * t, z0 + (z1 - z0) * t
                    k.box((fx + math.cos(am) * (rr + 0.03), fy + math.sin(am) * (rr + 0.03), zz), (0.12, 0.12, 0.22), "foam", jitter=False)
        hj = 1.1 + 0.35 * math.sin(2 * math.pi * ph)
        k.cyl((fx, fy, 4.1), 0.1, 0.05, hj, "water_fall", 6, jitter=False)
        for i in range(8):
            a = 2 * math.pi * i / 8 + ph * 1.2
            rr = 0.25 + 0.3 * ((ph + i * 0.13) % 1.0)
            k.box((fx + math.cos(a) * rr, fy + math.sin(a) * rr, 4.1 + hj - 0.3 * ((ph + i * 0.13) % 1.0)), (0.09, 0.09, 0.14), "foam", jitter=False)
        for rr in ((2.8 + 1.5 * ph), (2.8 + 1.5 * ((ph + 0.5) % 1.0))):
            for i in range(24):
                a0, a1 = 2 * math.pi * i / 24, 2 * math.pi * (i + 0.6) / 24
                q = [(fx + math.cos(a0) * rr, fy + math.sin(a0) * rr, 0.9), (fx + math.cos(a1) * rr, fy + math.sin(a1) * rr, 0.9),
                     (fx + math.cos(a1) * (rr + 0.1), fy + math.sin(a1) * (rr + 0.1), 0.9), (fx + math.cos(a0) * (rr + 0.1), fy + math.sin(a0) * (rr + 0.1), 0.9)]
                k.add(q, [(0, 1, 2, 3)], "water_hi")
        for i in range(8):   # swan spout arcs
            a = 2 * math.pi * (i + 0.5) / 8
            for s in range(3):
                t = ((ph + s / 3) % 1.0)
                r = 4.45 - t * 0.9
                k.box((fx + math.cos(a) * r, fy + math.sin(a) * r, 1.45 + 0.35 * math.sin(math.pi * t) - t * 0.5), (0.1, 0.1, 0.1), "water_fall", jitter=False)
    k.use("court")
    # benches + lamps around the fountain, blossom trees in the outer ward, pergola walk
    for i in range(4):
        a = math.pi / 4 + i * math.pi / 2
        bench(k, fx + math.cos(a) * 6.4, fy + math.sin(a) * 6.4, rot=math.degrees(a) + 90)
    for (lx, ly) in ((13.4, 18.4), (34.6, 18.4), (13.4, 37.6), (34.6, 37.6), (22.0, 40.5), (26.0, 40.5), (22.0, 17.0), (26.0, 17.0)):
        x, y, _ = M(lx, ly)
        lamp_post(k, x, y)
    for (lx, ly) in ((8.0, 38.5), (40.0, 38.5), (8.5, 9.0), (39.5, 9.0), (16.0, 40.5), (32.0, 40.5)):
        x, y, _ = M(lx, ly)
        blossom_tree(k, x, y, s=rng.uniform(1.0, 1.25))
    for ly in (38.5, 40.0, 41.5):       # rose pergola arches over the path from the gate
        for sx in (22.55, 25.45):
            x, y, _ = M(sx, ly)
            k.box((x, y, 1.3), (0.2, 0.2, 2.6), "cstone_l")
        xa, y, _ = M(22.55, ly); xb, _, _ = M(25.45, ly)
        k.box(((xa + xb) / 2, y, 2.65), (xb - xa + 0.4, 0.22, 0.2), "cstone_l")
        roses_on_face(k, lambda u, z, d, y=y: (u, y - 0.1 - d, z), xa - 0.2, xb + 0.2, 1.8, 2.9, n_patch=1, density=0.8)
    # flower borders along the inner walls (H tiles)
    for (a0, b0, a1, b1) in ((6, 42, 19, 43), (29, 42, 42, 43), (5, 6, 6, 17), (42, 6, 43, 17), (5, 33, 6, 41), (42, 33, 43, 41)):
        rectp(a0, b0, a1, b1, 0.03, "mud")
        a, b = M(a0, b0), M(a1, b1)
        flower_patch(k, a[0] + 0.2, b[1] + 0.2, b[0] - 0.2, a[1] - 0.2, int(10 * (a1 - a0) * (b1 - b0)))
        for i in range(int(max(a1 - a0, b1 - b0) / 2)):
            if a1 - a0 > b1 - b0:
                x, y, _ = M(a0 + 1 + i * 2, (b0 + b1) / 2)
            else:
                x, y, _ = M((a0 + a1) / 2, b0 + 1 + i * 2)
            rose_bush(k, x, y, 0.9)
    # keep forecourt steps
    x, y, _ = M(24, 16.35)
    for i in range(3):
        k.box((x, y + 0.25 - i * 0.28, 0.08 + i * 0.0), (4.2 - i * 0.5, 0.5, 0.16 + i * 0.16), "cstone_l")

    # ------------------------------------------------ CURTAIN WALLS
    k.use("body")
    zb = wz
    def wall_box(ax, ay, bx, by, h=WALL_H, mat="cstone"):
        a, b = M(ax, ay), M(bx, by)
        x0, x1 = sorted((a[0], b[0])); y0, y1 = sorted((a[1], b[1]))
        k.box(((x0 + x1) / 2, (y0 + y1) / 2, (zb + h) / 2), (x1 - x0, y1 - y0, h - zb), mat)
        return x0, x1, y0, y1
    x0, x1, y0, y1 = wall_box(5.5, 3.0, 42.5, 5.0)
    merlon_row(k, x0 + 1, x1 - 1, y1 - 0.25, WALL_H, depth=0.5)
    k.box(((x0 + x1) / 2, y1 - 0.25, WALL_H + 0.2), (x1 - x0, 0.5, 0.4), "cstone_l")
    k.box(((x0 + x1) / 2, y0 + 0.1, WALL_H + 0.15), (x1 - x0, 0.2, 0.3), "ctrim")
    ashlar(k, x0 + 1, x1 - 1, 0.3, WALL_H - 0.3, y0, 70)
    for (u0, u1) in ((x0 + 0.5, M(12, 0)[0] - 0.3), (M(36, 0)[0] + 0.3, x1 - 0.5)):
        roses_on_face(k, face_neg_y(y0), u0, u1, 0.1, WALL_H - 0.6, n_patch=3)
    for sgn, (ax, bx) in ((1, (3.0, 5.0)), (-1, (43.0, 45.0))):
        x0, x1, y0, y1 = wall_box(ax, 5.5, bx, 42.5)
        xo = x0 + 0.25 if sgn > 0 else x1 - 0.25
        merlon_row(k, y0 + 1, y1 - 1, xo, WALL_H, depth=0.5, along="y")
        k.box((xo, (y0 + y1) / 2, WALL_H + 0.2), (0.5, y1 - y0, 0.4), "cstone_l")
        xi = x1 - 0.1 if sgn > 0 else x0 + 0.1
        k.box((xi, (y0 + y1) / 2, WALL_H + 0.15), (0.2, y1 - y0, 0.3), "ctrim")
        xp = x0 - 0.12 if sgn > 0 else x1 + 0.12
        k.box((xp, (y0 + y1) / 2, (zb + 0.5) / 2), (0.3, y1 - y0, 0.5 - zb), "cplinth")
        xf = x1 if sgn > 0 else x0
        roses_on_face(k, face_x(xf, sgn), y0 + 1, y1 - 1, 0.1, WALL_H - 0.5, n_patch=6)
        for ly in (12.0, 36.0):
            _, yy, _ = M(0, ly)
            xb = x0 - 0.35 if sgn > 0 else x1 + 0.35
            k.box((xb, yy, (zb + 4.8) / 2), (0.75, 1.1, 4.8 - zb), "cstone", taper=0.8)
    for (ax, bx) in ((5.5, 19.4), (28.6, 42.5)):
        x0, x1, y0, y1 = wall_box(ax, S_WALL_IN, bx, S_WALL_OUT)
        yf = y0
        k.box(((x0 + x1) / 2, yf - 0.12, (zb + 0.9) / 2), (x1 - x0, 0.3, 0.9 - zb), "cplinth")
        k.box(((x0 + x1) / 2, yf - 0.03, 2.2), (x1 - x0, 0.1, 0.22), "ctrim")
        k.box(((x0 + x1) / 2, yf - 0.05, WALL_H - 0.25), (x1 - x0, 0.14, 0.2), "ctrim")
        ashlar(k, x0 + 1, x1 - 1, 0.2, WALL_H - 0.5, yf, 50)
        for t in (0.22, 0.5, 0.78):
            xb = x0 + (x1 - x0) * t
            wedge(k, xb, yf, 1.25, 1.0, zb, 4.8, 1.2, "cstone")
            wedge(k, xb, yf - 0.02, 1.45, 1.15, zb, 0.9, 0.5, "cplinth")
        for t in (0.1, 0.36, 0.64, 0.9):
            arched_window(k, x0 + (x1 - x0) * t, yf - 0.02, 4.4, w=0.5, h=1.0, lit=False)
        roses_on_face(k, face_neg_y(yf - 0.02), x0 + 0.5, x1 - 0.5, 0.0, 5.2, n_patch=4)
        k.box(((x0 + x1) / 2, y1 - 0.1, WALL_H + 0.12), (x1 - x0, 0.2, 0.25), "ctrim")
        k.use("front")
        k.box(((x0 + x1) / 2, yf + 0.3, WALL_H + 0.45), (x1 - x0, 0.6, 0.9), "cstone")
        k.box(((x0 + x1) / 2, yf + 0.3, WALL_H + 0.92), (x1 - x0 + 0.02, 0.64, 0.08), "ctrim")
        merlon_row(k, x0 + 1, x1 - 1, yf + 0.3, WALL_H + 0.95, depth=0.6, h=0.8)
        k.use("body")
        for t in (0.3, 0.7):
            banner(k, x0 + (x1 - x0) * t, yf, WALL_H - 0.5, w=1.1, h=2.6)
    # ------------------------------------------------ TOWERS
    for (cx, cy) in ((4.4, 4.4), (43.6, 4.4)):
        pink_cone_tower(k, cx, cy, 2.3, 15.0, 8.0, segs=14, flag_len=2.0, windows=((-30, 8.0), (30, 8.0), (0, 11.5)))
    for (cx, cy) in ((4.4, 43.6), (43.6, 43.6)):
        pink_cone_tower(k, cx, cy, 2.3, 15.0, 8.0, segs=14, flag_len=2.0, windows=((-35, 4.0), (0, 7.0), (35, 4.0), (0, 11.0)))
        x, y, _ = M(cx, cy)
        roses_on_face(k, lambda u, z, d, x=x, y=y: (x + u, y - 2.3 * T - d, z), -2.0, 2.0, 0.0, 6.0, n_patch=2)
    for (cx, cy) in ((4.0, 24.0), (44.0, 24.0)):
        pink_cone_tower(k, cx, cy, 1.7, 12.0, 6.0, segs=12, flag_len=1.4, windows=((0, 6.0), (0, 9.2)))
    # ------------------------------------------------ GATEHOUSE
    gc = (GATE_X0 + GATE_X1) / 2
    gx, gy_face, _ = M(gc, S_WALL_OUT)
    gw = 8.6 * T
    gdepth = (S_WALL_OUT - 41.0) * T
    GH = 10.5
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
              "ctrim" if i != nv // 2 else "cstone_l", rot=(0, -math.degrees(a) + 90, 0))
    for sx in (-1, 1):
        px, pz = gx + sx * PULLEY[0], PULLEY[2]
        k.box((px, gy_face - 0.02, pz), (0.36, 0.1, 0.4), "slit!")
        k.cyl((px, gy_face - 0.12, pz + 0.25), 0.2, 0.2, 0.12, "iron", 8, rot=(90, 0, 0))
    k.box((gx, gy_face - 0.35, 7.6), (gw - 0.4, 0.7, 1.0), "cstone")
    for i in range(9):
        k.box((gx - gw / 2 + 0.5 + i * (gw - 1.0) / 8, gy_face - 0.3, 6.9), (0.3, 0.6, 0.45), "cstone_d")
    k.box((gx, gy_face - 0.72, 8.25), (gw - 0.3, 0.1, 0.3), "ctrim")
    merlon_row(k, gx - gw / 2 + 0.3, gx + gw / 2 - 0.3, gy_face - 0.45, 8.1, depth=0.5, h=0.75, w=0.6, gap=0.45)
    rose_emblem(k, gx, gy_face, 5.1, r=0.75)
    k.box((gx, gy_face + 0.25, GH + 0.4), (gw, 0.5, 0.8), "cstone")
    k.box((gx, gy_face + gdepth - 0.25, GH + 0.4), (gw, 0.5, 0.8), "cstone")
    merlon_row(k, gx - gw / 2 + 0.3, gx + gw / 2 - 0.3, gy_face + 0.25, GH + 0.8, depth=0.5, h=0.7, w=0.6, gap=0.45)
    k.box((gx, gy_face + gdepth * 0.55, GH + 1.1), (3.4, 2.2, 2.2), "cstone_l")
    k.box((gx, gy_face + gdepth * 0.55 - 0.55, GH + 2.6), (3.9, 1.5, 0.12), "roof", rot=(32, 0, 0))
    k.box((gx, gy_face + gdepth * 0.55 + 0.55, GH + 2.6), (3.9, 1.5, 0.12), "roof_d", rot=(-32, 0, 0))
    for sx in (-1, 1):
        wall_torch(k, gx + sx * (hw + 0.95), gy_face, 3.3)
        tcx = gc + sx * 3.7
        tower(k, tcx, 44.6, 1.9, 13.0, 7.0, segs=12, slits=((0, 2.6), (-sx * 40, 5.4)), windows=((0, 9.0),), flag_len=1.6)
        x, y, _ = M(tcx, 44.6)
        banner(k, x, y - 1.9 * T - 0.02, 7.6, w=1.0, h=2.6)
        roses_on_face(k, lambda u, z, d, x=x, y=y: (x + u, y - 1.9 * T - d, z), -1.8, 1.8, 0.0, 4.5, n_patch=2)
    # ------------------------------------------------ SIDE BUILDINGS
    # west: glass Rose Nursery (lx 6-12, ly 19-31)
    a, b = M(6, 19), M(12, 31)
    nx0, nx1, ny1, ny0 = a[0], b[0], a[1], b[1]
    ncx, ncy = (nx0 + nx1) / 2, (ny0 + ny1) / 2
    k.box((ncx, ncy, 0.5), (nx1 - nx0, ny1 - ny0, 1.0), "cstone")
    k.box((ncx, ncy, 2.5), (nx1 - nx0 - 0.2, ny1 - ny0 - 0.2, 3.0), "glass")
    for i in range(13):
        yy = ny0 + 0.1 + i * (ny1 - ny0 - 0.2) / 12
        k.box((nx1 - 0.08, yy, 2.5), (0.12, 0.1, 3.0), "glass_frame")
        k.box((nx0 + 0.08, yy, 2.5), (0.12, 0.1, 3.0), "glass_frame")
    for i in range(6):
        xx = nx0 + 0.1 + i * (nx1 - nx0 - 0.2) / 5
        k.box((xx, ny0 + 0.08, 2.5), (0.1, 0.12, 3.0), "glass_frame")
    rw = (nx1 - nx0) / 2 / math.cos(math.radians(30))
    k.box((ncx - (nx1 - nx0) / 4, ncy, 4.0 + (nx1 - nx0) / 4 * math.tan(math.radians(30))), (rw, ny1 - ny0, 0.1), "glass_d", rot=(0, -30, 0))
    k.box((ncx + (nx1 - nx0) / 4, ncy, 4.0 + (nx1 - nx0) / 4 * math.tan(math.radians(30))), (rw, ny1 - ny0, 0.1), "glass", rot=(0, 30, 0))
    k.box((ncx, ncy, 4.0 + (nx1 - nx0) / 2 * math.tan(math.radians(30))), (0.2, ny1 - ny0, 0.2), "glass_frame")
    for i in range(10):
        k.rock((nx0 + 1 + (i % 2) * (nx1 - nx0 - 2), ny0 + 1.3 + (i // 2) * (ny1 - ny0 - 2.6) / 4, 1.3), (0.6, 0.6, 0.5), "vine", sink=0)
        k.box((nx0 + 1 + (i % 2) * (nx1 - nx0 - 2), ny0 + 1.3 + (i // 2) * (ny1 - ny0 - 2.6) / 4, 1.8), (0.25, 0.25, 0.25), "rose_w", jitter=False)
    k.box((ncx, ny0 - 0.05, 1.3), (1.3, 0.1, 2.4), "glass_frame"); k.box((ncx, ny0 - 0.08, 1.2), (1.0, 0.1, 2.2), "wood_dark")
    # east: Chapel of the White Rose (lx 37-43, ly 19-32)
    a, b = M(37, 19), M(43, 32)
    cx0, cx1, cy1, cy0 = a[0], b[0], a[1], b[1]
    ccx, ccy = (cx0 + cx1) / 2, (cy0 + cy1) / 2
    CHH = 6.2
    k.box((ccx, ccy, CHH / 2), (cx1 - cx0, cy1 - cy0, CHH), "cstone")
    k.box((ccx, ccy, 0.4), (cx1 - cx0 + 0.3, cy1 - cy0 + 0.3, 0.8), "cplinth")
    rw = (cx1 - cx0) / 2 / math.cos(math.radians(50)) + 0.3
    rh = (cx1 - cx0) / 4 * math.tan(math.radians(50))
    k.box((ccx - (cx1 - cx0) / 4, ccy, CHH + rh), (rw, cy1 - cy0 + 0.6, 0.15), "roof_d", rot=(0, -50, 0))
    k.box((ccx + (cx1 - cx0) / 4, ccy, CHH + rh), (rw, cy1 - cy0 + 0.6, 0.15), "roof", rot=(0, 50, 0))
    gz = CHH + (cx1 - cx0) / 2 * math.tan(math.radians(50))
    k.add([(cx0, cy0 - 0.02, CHH), (cx1, cy0 - 0.02, CHH), (ccx, cy0 - 0.02, gz)], [(0, 1, 2), (2, 1, 0)], "cstone")
    rose_emblem(k, ccx, cy0 - 0.03, CHH + 1.3, r=0.9)
    k.box((ccx, cy0 - 0.06, 1.5), (1.6, 0.12, 3.0), "ctrim"); k.box((ccx, cy0 - 0.1, 1.35), (1.1, 0.1, 2.6), "wood_dark")
    k.cyl((ccx, cy0 - 0.1, 2.65), 0.55, 0.55, 0.1, "wood_dark", 8, rot=(90, 0, 0))
    for yy in (cy0 + 2.5, cy0 + 6.0, cy0 + 9.5, cy0 + 13.0):     # side lancets (west face, seen edge-on) + buttresses
        k.box((cx0 - 0.3, yy, 2.2), (0.6, 0.8, 4.4), "cstone_d", taper=0.7)
    k.box((ccx, cy0 + 0.8, gz + 0.9), (1.2, 1.2, 1.8), "cstone_l")     # bell-cote
    k.box((ccx, cy0 + 0.2, gz + 0.8), (0.6, 0.1, 1.0), "slit!")
    k.cyl((ccx, cy0 + 0.8, gz + 1.8), 1.0, 0.0, 2.6, "roof", 4, rot=(0, 0, 45))
    k.cone((ccx, cy0 + 0.8, gz + 4.3), 0.1, 0.4, "gold", segs=4)
    roses_on_face(k, face_neg_y(cy0 - 0.03), cx0 + 0.2, cx1 - 0.2, 0.0, 4.5, n_patch=2)
    roses_on_face(k, face_x(cx0, -1), cy0 + 0.5, cy1 - 0.5, 0.0, 4.0, n_patch=3)
    # ------------------------------------------------ KEEP: the Rose Palace (24 x 11 tiles, 4 storeys)
    (kl0, kf0, kl1, kf1) = KEEP
    a, b = M(kl0, kf0), M(kl1, kf1)
    KX0, KX1, KYB, KYS = a[0], b[0], a[1], b[1]         # KYS = front (south) face y
    kcx = (KX0 + KX1) / 2
    k.box((kcx, (KYB + KYS) / 2, KH / 2), (KX1 - KX0, KYB - KYS, KH), "cstone")
    k.box((kcx, KYS - 0.15, 0.5), (KX1 - KX0 + 0.3, 0.3, 1.0), "cplinth")
    for z in (4.2, 8.4, 12.6):
        k.box((kcx, KYS - 0.06, z), (KX1 - KX0, 0.14, 0.22), "ctrim")
    ashlar(k, KX0 + 1, KX1 - 1, 0.5, KH - 0.5, KYS, 90)
    # windows: per storey, every 2 tiles, skipping the central frontispiece
    for fl, z in enumerate((2.3, 6.3, 10.5, 14.6)):
        for i in range(12):
            lx = kl0 + 1 + i * 2
            if 21 <= lx <= 27:
                continue
            x, _, _ = M(lx, 0)
            arched_window(k, x, KYS, z, w=0.7, h=1.6 if fl else 1.2, lit=(i + fl) % 3 != 0)
    # frontispiece (lx 21-27): projecting centre bay with balcony, door, gable + rose window
    fa, fb = M(21, 0)[0], M(27, 0)[0]
    fyc = KYS - 0.4
    k.box(((fa + fb) / 2, fyc + 0.2, (KH + 2.0) / 2), (fb - fa, 1.2, KH + 2.0), "cstone_l")
    FS = fyc - 0.4
    gzt = KH + 2.0 + (fb - fa) / 2 * math.tan(math.radians(40))
    k.add([(fa, FS - 0.01, KH + 2.0), (fb, FS - 0.01, KH + 2.0), ((fa + fb) / 2, FS - 0.01, gzt)], [(0, 1, 2), (2, 1, 0)], "cstone_l")
    rwid = (fb - fa) / 2 / math.cos(math.radians(40)) + 0.2
    for sx in (-1, 1):
        k.box(((fa + fb) / 2 + sx * (fb - fa) / 4, fyc + 0.2, KH + 2.0 + (fb - fa) / 4 * math.tan(math.radians(40))),
              (rwid, 1.6, 0.15), "roof" if sx > 0 else "roof_d", rot=(0, sx * 40, 0))
    rose_emblem(k, (fa + fb) / 2, FS, KH + 1.2, r=1.4)
    for z in (4.2, 8.4, 12.6):
        k.box(((fa + fb) / 2, FS - 0.05, z), (fb - fa + 0.1, 0.12, 0.22), "ctrim")
    for sx in (-1, 1):
        k.box(((fa + fb) / 2 + sx * ((fb - fa) / 2 - 0.25), FS - 0.12, (KH + 2) / 2), (0.5, 0.3, KH + 2), "ctrim")    # pilasters
        banner(k, (fa + fb) / 2 + sx * 3.0, FS, 12.2, w=1.1, h=3.2)
    dx = M(24, 0)[0]
    k.box((dx, FS - 0.06, 1.8), (3.1, 0.14, 3.6), "ctrim")
    k.box((dx, FS - 0.1, 1.55), (2.4, 0.12, 3.1), "wood_dark")
    k.cyl((dx, FS - 0.1, 3.1), 1.2, 1.2, 0.12, "wood_dark", 10, rot=(90, 0, 0))
    k.cyl((dx, FS - 0.06, 3.1), 1.55, 1.55, 0.1, "ctrim", 10, rot=(90, 0, 0))
    k.box((dx, FS - 0.14, 1.55), (0.06, 0.1, 3.0), "gold!")
    for sx in (-1, 1):
        wall_torch(k, dx + sx * 2.1, FS, 2.9)
        arched_window(k, dx + sx * 2.2, FS, 10.5, w=0.7, h=1.6)
        arched_window(k, dx + sx * 2.2, FS, 14.6, w=0.7, h=1.4)
    # balcony at storey 2 above the door
    k.box((dx, FS - 0.7, 4.35), (4.6, 1.4, 0.3), "cstone_l")
    for i in range(13):
        k.cyl((dx - 2.1 + i * 0.35, FS - 1.3, 4.5), 0.07, 0.07, 0.8, "cstone_l", 5)
    k.box((dx, FS - 1.3, 5.35), (4.6, 0.2, 0.14), "ctrim")
    arched_window(k, dx, FS, 6.4, w=1.2, h=2.2)
    for i in range(5):
        k.box((dx - 2.0 + i * 1.0, FS - 0.9, 3.8), (0.25, 0.9, 0.5), "cstone_d")     # corbels
    # climbing roses on the palace facade
    for (u0, u1) in ((KX0 + 2.8, fa - 0.4), (fb + 0.4, KX1 - 2.8)):
        roses_on_face(k, face_neg_y(KYS - 0.02), u0, u1, 0.0, 9.0, n_patch=5)
    roses_on_face(k, face_neg_y(FS - 0.02), fa + 0.2, dx - 1.8, 0.0, 6.5, n_patch=1)
    roses_on_face(k, face_neg_y(FS - 0.02), dx + 1.8, fb - 0.2, 0.0, 6.5, n_patch=1)
    # roof: balustrade parapet, terrace floor, corner belvederes, conservatory, stair-head hut
    k.box((kcx, (KYB + KYS) / 2, KH + 0.05), (KX1 - KX0 - 0.1, KYB - KYS - 0.1, 0.1), "court")
    for (yy, along) in ((KYS + 0.15, "x"), (KYB - 0.15, "x")):
        k.box((kcx, yy, KH + 1.05), (KX1 - KX0, 0.3, 0.12), "ctrim")
        n = int((KX1 - KX0) / 0.4)
        for i in range(n):
            k.cyl((KX0 + 0.2 + i * 0.4, yy, KH), 0.08, 0.06, 1.0, "cstone_l", 5)
    for xx in (KX0 + 0.15, KX1 - 0.15):
        k.box((xx, (KYB + KYS) / 2, KH + 1.05), (0.3, KYB - KYS, 0.12), "ctrim")
    for (cx, cy) in ((kl0 + 1, kf0 + 1), (kl1 - 1, kf0 + 1), (kl0 + 1, kf1 - 1), (kl1 - 1, kf1 - 1)):
        x, y, _ = M(cx, cy)
        k.box((x, y, (KH + 4.2) / 2), (2 * T, 2 * T, KH + 4.2), "cstone_l")
        k.box((x, y, KH + 4.25), (2 * T + 0.3, 2 * T + 0.3, 0.2), "ctrim")
        for (ox, oy) in ((0, -T - 0.02),):
            arched_window(k, x + ox, y + oy, KH + 2.3, w=0.7, h=1.4)
        k.cyl((x, y, KH + 4.35), T * 1.3, 0, 5.2, "roof", 8, rot=(0, 0, 22.5))
        k.cone((x, y, KH + 9.4), 0.12, 0.5, "gold", segs=5)
        flag(k, x, y, KH + 11.6, length=1.6, height=1.0)
    ca, cb = M(17, 6), M(29, 14)
    gx0, gx1, gy1, gy0 = ca[0], cb[0], ca[1], cb[1]
    gcx, gcy = (gx0 + gx1) / 2, (gy0 + gy1) / 2
    k.box((gcx, gcy, KH + 0.35), (gx1 - gx0, gy1 - gy0, 0.5), "cstone")
    k.box((gcx, gcy, KH + 2.1), (gx1 - gx0 - 0.2, gy1 - gy0 - 0.2, 3.0), "glass")
    for i in range(13):
        xx = gx0 + 0.1 + i * (gx1 - gx0 - 0.2) / 12
        k.box((xx, gy0 + 0.06, KH + 2.1), (0.1, 0.12, 3.0), "glass_frame")
    k.cyl((gcx, gcy, KH + 3.6), (gy1 - gy0) / 2, 0.4, 2.8, "glass_d", 12)
    k.cyl((gcx, gcy, KH + 6.35), 0.45, 0.45, 0.6, "glass_frame", 8)
    k.cone((gcx, gcy, KH + 6.9), 0.2, 0.7, "gold", segs=5)
    k.box((gcx, gy0 - 0.05, KH + 1.2), (1.2, 0.1, 2.0), "glass_frame")
    ha, hb = M(32, 12), M(35, 15)
    hx, hy = (ha[0] + hb[0]) / 2, (ha[1] + hb[1]) / 2
    k.box((hx, hy, KH + 1.3), (hb[0] - ha[0] - 0.3, ha[1] - hb[1] - 0.3, 2.6), "cstone_l")
    k.cyl((hx, hy, KH + 2.6), (hb[0] - ha[0]) * 0.72, 0, 2.2, "roof", 4, rot=(0, 0, 45))
    k.box((ha[0] + 0.1, hy, KH + 1.1), (0.1, 1.0, 2.0), "wood_dark")
    for (lx, ly) in ((14.5, 7.5), (14.5, 13.5), (31, 7.5), (20, 15.0), (27, 15.0)):     # planters on the terrace
        x, y, _ = M(lx, ly)
        k.box((x, y, KH + 0.35), (1.2, 0.8, 0.6), "cstone_d")
        rose_bush(k, x, y, 0.8)
        for v in k.verts[-60:]:
            pass
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
