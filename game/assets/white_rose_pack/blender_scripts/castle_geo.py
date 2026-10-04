"""castle_geo.py - geometry for the new Stonehaven Castle Keep (Mythoscape).

Everything is built in TILE coordinates and converted to metres:
    M(lx, ly, z) -> (lx*T, -ly*T, z)       T = 40 px / 26.9 px-per-m = 1.487 m
lx, ly are continuous local tile coords: tile (i, j) spans [i, i+1] x [j, j+1];
local (0,0) = NW corner of world tile (X0, Y0) = (100, 31).  Footprint 24 x 24 tiles.
Front (gate) faces -Y (south / towards the camera).  Z up.  1 unit = 1 m.

Faces are routed into PARTS (see PartKit.use):
  ground  - moat banks, bridge abutment slab, reeds, rocks      (drawn under entities)
  water   - moat water (soft emissive like the fountain)        (drawn under entities)
  body    - walls, towers, keep, gatehouse                       (back layer)
  court   - courtyard floor + courtyard props                    (back layer; dropped in cutaway)
  front   - south curtain parapets (in front of wall-walk NPCs)  (drawn after entities)
  posts   - abutment pillars + braziers (y-sorted at world row 54)
  bridge / portcullis / chain_l / chain_r - animated gate parts, built in LOCAL pivot space
"""
import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from osrs_kit import Kit, GAME_PX_PER_M  # noqa: E402
import prop_parts as pp  # noqa: E402

T = 40.0 / GAME_PX_PER_M
X0, Y0, NX, NY = 100, 31, 24, 24
WATER_Z = -0.7
WALL_H = 6.5          # curtain wall-walk height (m)
S_WALL_OUT, S_WALL_IN = 22.0, 20.0     # south curtain faces (ly)
GATE_X0, GATE_X1 = 11.0, 13.0          # gate opening (lx)
HINGE_LY = 22.0
BRIDGE_L = 3.25       # m, hinge -> tip (rests on the outer abutment at ly ~24.2)
BRIDGE_W = 3.2
PORT_LY = 21.6        # portcullis slot
PORT_W, PORT_H, PORT_RISE = 3.1, 3.6, 2.25
PULLEY = (1.45, 0.12, 4.5)   # +-x from gate centre, m behind face, z
CHAIN_L = 5.8

PAL = dict(pp.P)
PAL.update({
    "cstone": "#8d8e92", "cstone_d": "#6d6e73", "cstone_l": "#a8a9ac", "ctrim": "#b2b0a8",
    "cplinth": "#7a7a7c", "roof": "#3e4049", "roof_d": "#2d2f36", "roof_edge": "#5a5b63",
    "banner": "#a3262b", "banner_d": "#6e1a1e", "arch_brick": "#9a5a3c", "iron": "#3b3e44",
    "chain": "#6a6e76", "slit": "#18171b", "court": "#8b877c", "court_d": "#77736a",
    "grass": "#5e7a3c", "bank": "#77725f", "mud": "#5a4a36", "reed": "#6f8a3a", "reed_d": "#4f6a2a",
    "cattail": "#6a4428", "lily": "#4f7a36", "glimpse": "#b9b3a2", "hay": "#c2a24e",
    "wood_dark": "#4a3222", "flagpole": "#5b4a38", "straw": "#b89a4e",
    "water": "#3a6f96", "water_hi": "#86bfe0", "window": "#ffcf6a",
})
EMISSIVE = {"water": 0.45, "water_hi": 0.6, "fire": 6.0, "fire_core": 8.0, "ember": 3.0,
            "window": 2.2, "candle": 6.0}


def M(lx, ly, z=0.0):
    return (lx * T, -ly * T, z)


class PartKit(Kit):
    """Kit whose geometry is routed into named parts (one object each)."""

    def __init__(self, *a, **kw):
        super().__init__(*a, **kw)
        self.parts = {}
        self.part = None
        self.use("body")

    def use(self, name):
        if self.part is not None:
            self.parts[self.part] = (self.verts, self.faces)
        self.part = name
        self.verts, self.faces = self.parts.get(name, ([], []))
        self.parts[name] = (self.verts, self.faces)

    def all_parts(self):
        self.parts[self.part] = (self.verts, self.faces)
        return self.parts


# ----------------------------------------------------------------- helpers
def dbl(k, pts, mat, jitter=False):
    """Double-wound polygon (visible from both sides, Panda culls backfaces)."""
    k.add(pts, [list(range(len(pts))), list(range(len(pts)))[::-1]], mat, jitter=jitter)


def slit(k, x, y, z, rot_z=0.0, h=0.95, big=False):
    """Arrow slit on a face whose outward normal is -Y rotated by rot_z (deg)."""
    w = 0.16 if not big else 0.22
    k.box((x, y, z), (w + 0.26, 0.08, h + 0.3), "ctrim", rot=(0, 0, rot_z))
    k.box((x, y, z), (w, 0.14, h), "slit!", rot=(0, 0, rot_z))
    k.box((x, y, z + h * 0.18), (w * 2.6, 0.14, w * 0.8), "slit!", rot=(0, 0, rot_z))   # cross slit


def merlon_row(k, x0, x1, y, z, depth=0.45, h=0.8, w=0.7, gap=0.55, mat="cstone", along="x"):
    n = max(1, int((abs(x1 - x0) + gap) / (w + gap)))
    span = n * w + (n - 1) * gap
    start = (x0 + x1) / 2 - span / 2 + w / 2
    for i in range(n):
        c = start + i * (w + gap)
        if along == "x":
            k.box((c, y, z + h / 2), (w, depth, h), mat)
        else:
            k.box((y, c, z + h / 2), (depth, w, h), mat)


def ashlar(k, x0, x1, z0, z1, y, n, mats=("cstone_d", "cstone_l", "cplinth"), proud=0.05, along="x"):
    """Scatter slightly proud stone blocks over a flat face (breaks up big flat areas)."""
    for _ in range(n):
        w = k.rng.uniform(0.55, 1.25)
        h = k.rng.uniform(0.32, 0.5)
        c = k.rng.uniform(min(x0, x1) + w / 2, max(x0, x1) - w / 2)
        z = k.rng.uniform(z0 + h / 2, z1 - h / 2)
        mt = k.rng.choice(mats)
        if along == "x":
            k.box((c, y - proud / 2, z), (w, proud + 0.02, h), mt)
        else:   # face along y at x = y param (sign of proud gives side)
            k.box((y - proud / 2, c, z), (abs(proud) + 0.02, w, h), mt)


def flag(k, x, y, z, length=1.5, height=0.9, mat="banner"):
    """Pole top at (x,y,z); cloth waves east (+X) in the XZ plane (faces the camera)."""
    k.cyl((x, y, z - 2.0), 0.06, 0.05, 2.25, "flagpole", segs=5)
    k.cone((x, y, z + 0.25), 0.1, 0.22, "gold", segs=5)
    pts_top, pts_bot = [], []
    for i in range(5):
        t = i / 4
        dx = t * length
        wav = math.sin(t * math.pi * 1.6) * 0.14
        pts_top.append((x + dx, y + wav, z - 0.02 - t * 0.12))
        pts_bot.append((x + dx, y + wav, z - height + t * 0.18 * (1 if i < 4 else 2.2)))
    for i in range(4):
        q = [pts_bot[i], pts_bot[i + 1], pts_top[i + 1], pts_top[i]]
        dbl(k, q, mat if i % 2 == 0 else mat + "_d")
    # gold stripe
    for i in range(4):
        t0, t1 = i / 4, (i + 1) / 4
        a = pts_top[i]; b = pts_top[i + 1]
        q = [(a[0], a[1] - 0.01, a[2] - 0.28), (b[0], b[1] - 0.01, b[2] - 0.28),
             (b[0], b[1] - 0.01, b[2] - 0.2), (a[0], a[1] - 0.01, a[2] - 0.2)]
        dbl(k, q, "gold")


def banner(k, x, y, z_top, w=1.0, h=2.4, emblem=True):
    """Hanging banner on a -Y facing wall at depth y (cloth slightly in front)."""
    yy = y - 0.08
    k.box((x, yy, z_top + 0.05), (w + 0.35, 0.1, 0.1), "wood_dark")
    for sx in (-1, 1):
        k.box((x + sx * (w / 2 + 0.12), yy, z_top + 0.05), (0.1, 0.12, 0.14), "gold!")
    pts = [(x - w / 2, yy - 0.02, z_top), (x + w / 2, yy - 0.02, z_top),
           (x + w / 2, yy - 0.05, z_top - h), (x, yy - 0.07, z_top - h - 0.45), (x - w / 2, yy - 0.05, z_top - h)]
    dbl(k, pts, "banner")
    dbl(k, [(x - w / 2, yy - 0.03, z_top), (x - w / 2 + 0.12, yy - 0.035, z_top),
            (x - w / 2 + 0.12, yy - 0.06, z_top - h), (x - w / 2, yy - 0.06, z_top - h)], "banner_d")
    if emblem:
        cz = z_top - h * 0.42
        dbl(k, [(x, yy - 0.09, cz + 0.42), (x + 0.3, yy - 0.09, cz + 0.2), (x + 0.24, yy - 0.09, cz - 0.2),
                (x, yy - 0.09, cz - 0.4), (x - 0.24, yy - 0.09, cz - 0.2), (x - 0.3, yy - 0.09, cz + 0.2)], "gold")
        dbl(k, [(x - 0.06, yy - 0.1, cz + 0.28), (x + 0.06, yy - 0.1, cz + 0.28),
                (x + 0.06, yy - 0.1, cz - 0.26), (x - 0.06, yy - 0.1, cz - 0.26)], "banner_d")


def wedge(k, x, yf, w, d, z0, z_wall, z_out, mat):
    """Sloped buttress against a -Y facing wall at depth yf: top falls from z_wall (at the wall)
    to z_out (d metres in front)."""
    hw = w / 2
    v = [(x - hw, yf, z0), (x + hw, yf, z0), (x + hw, yf - d, z0), (x - hw, yf - d, z0),
         (x - hw, yf, z_wall), (x + hw, yf, z_wall), (x + hw, yf - d, z_out), (x - hw, yf - d, z_out)]
    f = [(0, 3, 2, 1), (4, 5, 6, 7), (3, 7, 6, 2), (1, 2, 6, 5), (0, 4, 7, 3), (0, 1, 5, 4)]
    k.add(v, [tuple(reversed(q)) for q in f], mat)   # outward winding (Panda culls backfaces)
    k.add([(x - hw - 0.04, yf - d + 0.02, z_out), (x + hw + 0.04, yf - d + 0.02, z_out),
           (x + hw + 0.04, yf + 0.02, z_wall), (x - hw - 0.04, yf + 0.02, z_wall)], [(0, 1, 2, 3)], "ctrim")


def wall_torch(k, x, y, z):
    """Iron bracket torch on a -Y facing wall."""
    k.box((x, y - 0.15, z - 0.25), (0.12, 0.3, 0.1), "iron!")
    k.cyl((x, y - 0.3, z - 0.35), 0.07, 0.1, 0.45, "wood_dark", segs=5)
    k.cyl((x, y - 0.3, z + 0.08), 0.13, 0.11, 0.1, "iron!", segs=6)
    k.cone((x, y - 0.3, z + 0.16), 0.15, 0.5, "fire", segs=5)
    k.cone((x, y - 0.3, z + 0.18), 0.08, 0.3, "fire_core", segs=4)


def brazier(k, x, y, z):
    k.cyl((x, y, z), 0.12, 0.1, 0.35, "iron!", segs=6)
    k.cyl((x, y, z + 0.35), 0.18, 0.42, 0.3, "iron", segs=8)
    k.cyl((x, y, z + 0.6), 0.34, 0.3, 0.06, "ember", segs=8)
    k.cone((x, y, z + 0.62), 0.3, 0.75, "fire", segs=6)
    k.cone((x + 0.05, y - 0.03, z + 0.64), 0.16, 0.5, "fire_core", segs=5)


def tower(k, cx, cy, r_t, h, roof_h, segs=10, flag_len=1.6, slits=(), gallery=True, z0=WATER_Z,
          roof_over=0.45, windows=()):
    """Round OSRS tower: battered plinth, string course, corbelled crenellated gallery, cone roof."""
    x, y, _ = M(cx, cy)
    r = r_t * T
    k.cyl((x, y, z0), r * 1.1, r, 1.6, "cplinth", segs)
    k.cyl((x, y, z0 + 1.6), r, r * 0.98, h - 1.6 - z0 - 1.1, "cstone", segs, caps=False)
    zc = h - 1.1
    k.cyl((x, y, 3.2), r * 1.015, r * 1.015, 0.22, "ctrim", segs, caps=False)
    if gallery:
        for i in range(segs):   # corbels
            a = 2 * math.pi * (i + 0.5) / segs
            k.box((x + math.cos(a) * (r + 0.12), y + math.sin(a) * (r + 0.12), zc - 0.35), (0.34, 0.34, 0.5),
                  "cstone_d", rot=(0, 0, math.degrees(a)))
        k.cyl((x, y, zc - 0.1), r + 0.3, r + 0.3, 1.2, "cstone", segs)
        # merlons on the gallery rim
        for i in range(segs):
            a = 2 * math.pi * i / segs
            k.box((x + math.cos(a) * (r + 0.18), y + math.sin(a) * (r + 0.18), zc + 1.1 + 0.36),
                  (0.62, 0.3, 0.72), "cstone_l", rot=(0, 0, math.degrees(a) + 90))
    ztop = zc + 1.1
    rb = ztop + 0.74
    k.cyl((x, y, rb), r + roof_over + 0.08, r + roof_over, 0.16, "roof_edge", segs)
    k.cyl((x, y, rb + 0.16), r + roof_over, 0, roof_h, "roof", segs)
    k.cone((x, y, rb + 0.16 + roof_h - 0.1), 0.14, 0.45, "gold", segs=5)
    if flag_len:
        flag(k, x, y, rb + 0.16 + roof_h + 2.2, length=flag_len, height=flag_len * 0.6)
    for ang, z in slits:          # ang: 0 = facing camera (-Y); +ve towards +X
        a = math.radians(-90 + ang)
        slit(k, x + math.cos(a) * (r + 0.02), y + math.sin(a) * (r + 0.02), z, rot_z=ang)
    for ang, z in windows:
        a = math.radians(-90 + ang)
        wx, wy = x + math.cos(a) * (r + 0.03), y + math.sin(a) * (r + 0.03)
        k.box((wx, wy, z), (0.8, 0.1, 1.2), "ctrim", rot=(0, 0, ang))
        k.box((wx, wy, z - 0.05), (0.46, 0.14, 0.8), "window", rot=(0, 0, ang))
    return ztop


def reeds(k, x, y, n=7, h=1.1, spread=0.5):
    for _ in range(n):
        px = x + k.rng.uniform(-spread, spread)
        py = y + k.rng.uniform(-spread * 0.4, spread * 0.4)
        hh = h * k.rng.uniform(0.6, 1.1)
        lean = k.rng.uniform(-0.25, 0.25)
        dbl(k, [(px - 0.05, py, WATER_Z + 0.02), (px + 0.05, py, WATER_Z + 0.02), (px + lean, py, WATER_Z + hh)],
            k.rng.choice(["reed", "reed_d"]))
        if k.rng.random() < 0.35:
            k.cyl((px + lean * 0.8, py, WATER_Z + hh * 0.7), 0.05, 0.05, 0.22, "cattail", segs=4)


# =================================================================== BUILD
def build(k):
    rng = k.rng
    W24 = NX
    # ------------------------------------------------------------ WATER + BANKS
    k.use("water")
    wz = WATER_Z
    e = 0.3   # outer bank width (tiles)
    ring = [((e, e), (W24 - e, 2.0)), ((e, 22.0), (GATE_X0 - 0.05, W24 - e)), ((GATE_X1 + 0.05, 22.0), (W24 - e, W24 - e)),
            ((GATE_X0 - 0.05, 22.0), (GATE_X1 + 0.05, W24 - e)),
            ((e, 2.0), (2.0, 22.0)), ((22.0, 2.0), (W24 - e, 22.0))]
    for (ax, ay), (bx, by) in ring:
        a, b = M(ax, ay, wz), M(bx, by, wz)
        k.poly([(a[0], b[1], wz), (b[0], b[1], wz), (b[0], a[1], wz), (a[0], a[1], wz)], "water")
    # ripple highlights + lily pads
    for _ in range(46):
        side = rng.random()
        if side < 0.3:
            lx, ly = rng.uniform(0.6, 23.4), rng.uniform(22.3, 23.6)
        elif side < 0.5:
            lx, ly = rng.uniform(0.6, 23.4), rng.uniform(0.4, 1.7)
        elif side < 0.75:
            lx, ly = rng.uniform(0.4, 1.7), rng.uniform(2, 22)
        else:
            lx, ly = rng.uniform(22.3, 23.6), rng.uniform(2, 22)
        if GATE_X0 - 0.2 < lx < GATE_X1 + 0.2 and ly > 21.5:
            continue
        x, y, _ = M(lx, ly)
        L = rng.uniform(0.4, 1.1)
        k.poly([(x - L / 2, y - 0.05, wz + 0.01), (x + L / 2, y - 0.05, wz + 0.01),
                (x + L / 2 - 0.1, y + 0.05, wz + 0.01), (x - L / 2 + 0.1, y + 0.05, wz + 0.01)], "water_hi")
    k.use("ground")
    for _ in range(14):
        side = rng.random()
        lx, ly = (rng.uniform(0.6, 23.4), rng.uniform(22.4, 23.5)) if side < 0.5 else \
                 (rng.uniform(0.5, 1.6), rng.uniform(3, 21)) if side < 0.75 else (rng.uniform(22.4, 23.5), rng.uniform(3, 21))
        if GATE_X0 - 0.4 < lx < GATE_X1 + 0.4 and ly > 21.5:
            continue
        x, y, _ = M(lx, ly)
        k.disc((x, y, 0), rng.uniform(0.22, 0.34), "lily", segs=7, z=wz + 0.03, jag=0.1)
    # outer bank: coping strip at z 0 + stone revetment down to the water (faces into the moat)
    def bank(ax, ay, bx, by, face):
        a, b = M(ax, ay), M(bx, by)
        x0, x1 = sorted((a[0], b[0])); y0, y1 = sorted((a[1], b[1]))
        k.poly([(x0, y0, 0.0), (x1, y0, 0.0), (x1, y1, 0.0), (x0, y1, 0.0)], "bank")
        # revetment
        if face == "N":     # bank on the south side of the moat, face looks north
            q = [(x0, y1, wz - 0.1), (x0, y1, 0.0), (x1, y1, 0.0), (x1, y1, wz - 0.1)]
        elif face == "S":
            q = [(x0, y0, wz - 0.1), (x1, y0, wz - 0.1), (x1, y0, 0.0), (x0, y0, 0.0)]
        elif face == "E":
            q = [(x1, y0, wz - 0.1), (x1, y1, wz - 0.1), (x1, y1, 0.0), (x1, y0, 0.0)]
        else:
            q = [(x0, y0, wz - 0.1), (x0, y0, 0.0), (x0, y1, 0.0), (x0, y1, wz - 0.1)]
        k.add(q, [(0, 1, 2, 3)], "cstone_d")
        # coping stones
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
    bank(0, 0, W24, e, "S")                       # north bank (looks south, visible!)
    bank(0, W24 - e, GATE_X0 - 0.35, W24, "N")    # south bank west of the bridge
    bank(GATE_X1 + 0.35, W24 - e, W24, W24, "N")
    bank(0, e, e, W24 - e, "E")
    bank(W24 - e, e, W24, W24 - e, "W")
    # bridge abutment slab (outer) + paving lip onto the apron row
    a, b = M(GATE_X0 - 0.7, W24 - 0.35), M(GATE_X1 + 0.7, W24 + 0.55)
    k.box(((a[0] + b[0]) / 2, (a[1] + b[1]) / 2, -0.05), (b[0] - a[0], a[1] - b[1], 0.22), "ctrim")
    for i in range(6):
        x, y, _ = M(GATE_X0 - 0.45 + i * (GATE_X1 - GATE_X0 + 0.9) / 5, W24 + 0.2)
        k.box((x, y, 0.07), (0.62, 0.9, 0.06), rng.choice(["cstone_l", "cstone", "ctrim"]))
    x, y, _ = M((GATE_X0 + GATE_X1) / 2, W24 - 0.3)
    k.box((x, y, wz / 2 - 0.05), (BRIDGE_W + 1.6, 0.35, -wz + 0.2), "cstone_d")     # abutment face
    # inner threshold ledge under the hinge
    x, y, _ = M((GATE_X0 + GATE_X1) / 2, HINGE_LY + 0.08)
    k.box((x, y, (wz - 0.02) / 2), (3.3, 0.3, -wz + 0.02), "cplinth")
    # rocks + reeds
    for (lx, ly, s) in [(1.0, 23.2, 0.5), (4.6, 23.5, 0.35), (19.8, 23.3, 0.45), (23.1, 17.0, 0.4), (0.7, 9.0, 0.45),
                        (22.9, 4.2, 0.35), (9.4, 23.55, 0.32), (15.0, 23.5, 0.3), (6.5, 0.6, 0.4), (17.5, 0.7, 0.35)]:
        x, y, _ = M(lx, ly)
        k.rock((x, y, wz + 0.1), (s * 1.3, s, s * 0.8), rng.choice(["cstone_d", "cplinth", "bank"]), sink=0.05)
    for (lx, ly) in [(2.2, 23.6), (6.0, 23.65), (8.2, 23.6), (16.4, 23.6), (18.4, 23.65), (21.6, 23.6),
                     (0.45, 5.0), (0.45, 14.0), (0.45, 19.0), (23.55, 7.0), (23.55, 12.5), (23.55, 18.0),
                     (4.0, 0.5), (12.0, 0.45), (20.0, 0.5)]:
        x, y, _ = M(lx, ly)
        reeds(k, x, y, n=8, h=1.15)
    # wall-base rocks inside the moat
    for (lx, ly) in [(5.2, 22.25), (17.8, 22.2), (1.9, 16.5), (22.1, 8.0)]:
        x, y, _ = M(lx, ly)
        k.rock((x, y, wz + 0.05), (0.5, 0.35, 0.3), "cplinth", sink=0.05)

    # ------------------------------------------------------------ COURTYARD (court part)
    k.use("court")
    a, b = M(3.6, 3.6), M(20.4, 20.1)
    k.poly([(a[0], b[1], 0.0), (b[0], b[1], 0.0), (b[0], a[1], 0.0), (a[0], a[1], 0.0)], "court")
    for _ in range(70):   # flagstone patches
        lx, ly = rng.uniform(4.2, 19.8), rng.uniform(10.5, 19.6)
        x, y, _ = M(lx, ly)
        w, d = rng.uniform(0.6, 1.3), rng.uniform(0.5, 1.0)
        k.poly([(x - w / 2, y - d / 2, 0.012), (x + w / 2, y - d / 2, 0.012), (x + w / 2, y + d / 2, 0.012),
                (x - w / 2, y + d / 2, 0.012)], rng.choice(["court_d", "cstone_l", "court_d", "ctrim"]))
    # processional path from gate to keep door
    for i in range(10):
        ly = 19.6 - i * 0.95
        x, y, _ = M(12.0, ly)
        k.box((x, y, 0.02), (2.6, 1.2, 0.04), rng.choice(["ctrim", "cstone_l"]))
    # well
    x, y, _ = M(6.5, 12.5)
    k.cyl((x, y, 0), 0.95, 0.95, 0.8, "cstone", 10)
    k.cyl((x, y, 0.8), 0.75, 0.75, 0.02, "water", 8)
    for sx in (-1, 1):
        k.box((x + sx * 0.8, y, 1.4), (0.14, 0.14, 1.3), "wood")
    k.box((x, y, 2.05), (1.9, 0.12, 0.12), "wood")
    k.box((x, y - 0.37, 2.4), (2.1, 0.85, 0.08), "roof", rot=(22, 0, 0))
    k.box((x, y + 0.37, 2.4), (2.1, 0.85, 0.08), "roof_d", rot=(-22, 0, 0))
    # training dummies + archery target
    for lx in (15.8, 17.6):
        x, y, _ = M(lx, 12.8)
        k.cyl((x, y, 0), 0.07, 0.07, 1.6, "wood", 5)
        k.box((x, y, 1.15), (0.9, 0.12, 0.12), "wood")
        k.cyl((x, y, 0.95), 0.26, 0.24, 0.6, "straw", 6)
        k.box((x, y, 1.62), (0.3, 0.3, 0.32), "straw")
    x, y, _ = M(18.6, 15.2)
    k.cyl((x, y, 1.0), 0.7, 0.7, 0.18, "straw", 12, rot=(90, 0, 0))
    k.cyl((x, y - 0.18, 1.0), 0.45, 0.45, 0.03, "red", 10, rot=(90, 0, 0))
    k.cyl((x, y - 0.2, 1.0), 0.18, 0.18, 0.03, "gold", 8, rot=(90, 0, 0))
    k.box((x, y + 0.2, 0.5), (0.1, 0.1, 1.2), "wood", rot=(15, 0, 0))
    # hay cart + bales, barrels, crates
    x, y, _ = M(8.5, 16.0)
    k.box((x, y, 0.8), (2.2, 1.2, 0.5), "wood")
    k.box((x, y, 1.25), (2.0, 1.0, 0.5), "hay")
    for sx in (-0.8, 0.8):
        k.cyl((x + sx, y - 0.62, 0.5), 0.5, 0.5, 0.12, "wood_dark", 8, rot=(90, 0, 0))
    k.box((x + 1.6, y, 0.6), (1.1, 0.12, 0.1), "wood")
    for (lx, ly) in [(4.8, 16.4), (5.3, 17.3), (4.7, 18.2)]:
        x, y, _ = M(lx, ly)
        k.box((x, y, 0.35), (1.2, 0.8, 0.7), "hay")
    for (lx, ly) in [(19.0, 17.6), (19.5, 18.4), (18.4, 18.6)]:
        x, y, _ = M(lx, ly)
        pp.barrel(k, x, y)
    for (lx, ly) in [(19.3, 10.8), (18.5, 11.2)]:
        x, y, _ = M(lx, ly)
        pp.crate(k, x, y, s=0.7)
    # lean-to sheds against the west & east walls (dark sloped roofs)
    for (lx, sgn) in ((4.35, 1), (19.65, -1)):
        x, y0, _ = M(lx, 11.0)
        _, y1, _ = M(lx, 18.8)
        k.box((x, (y0 + y1) / 2, 1.2), (1.9, y0 - y1, 2.4), "wood_red")
        k.box((x - sgn * 0.25, (y0 + y1) / 2, 2.55), (2.5, y0 - y1 + 0.4, 0.14), "roof", rot=(0, sgn * 18, 0))
        for i in range(3):
            _, yy, _ = M(lx, 12.2 + i * 2.6)
            k.box((x + sgn * 0.96, yy, 0.9), (0.06, 1.0, 1.7), "wood_dark")

    # ------------------------------------------------------------ CURTAIN WALLS (body / front)
    k.use("body")
    zb = WATER_Z
    # north wall: outer face ly 2.0, inner 3.7
    def wall_box(ax, ay, bx, by, h=WALL_H, mat="cstone"):
        a, b = M(ax, ay), M(bx, by)
        x0, x1 = sorted((a[0], b[0])); y0, y1 = sorted((a[1], b[1]))
        k.box(((x0 + x1) / 2, (y0 + y1) / 2, (zb + h) / 2), (x1 - x0, y1 - y0, h - zb), mat)
        return x0, x1, y0, y1
    # N wall
    x0, x1, y0, y1 = wall_box(2.9, 2.0, 21.1, 3.7)
    wall_box(2.9, 1.85, 21.1, 2.15, h=1.0, mat="cplinth")                 # plinth
    merlon_row(k, x0 + 1.5, x1 - 1.5, y1 - 0.25, WALL_H, depth=0.5)          # outer parapet (north)
    k.box(((x0 + x1) / 2, y1 - 0.25, WALL_H + 0.2), (x1 - x0, 0.5, 0.4), "cstone_l")
    k.box(((x0 + x1) / 2, y0 + 0.1, WALL_H + 0.15), (x1 - x0, 0.2, 0.3), "ctrim")   # inner lip
    k.box(((x0 + x1) / 2, y0 - 0.02, 2.2), (x1 - x0, 0.06, 0.2), "ctrim")          # string course (inner face)
    ashlar(k, x0 + 2, x1 - 2, 0.3, WALL_H - 0.3, y0, 50)
    for lx in (5.5, 9.0, 15.0, 18.5):   # doors / windows on the inner face of the N wall
        x, _, _ = M(lx, 0)
        k.box((x, y0 - 0.05, 1.1), (1.1, 0.12, 2.2), "wood_dark")
        k.box((x, y0 - 0.07, 2.25), (1.4, 0.1, 0.25), "ctrim")
    for lx in (7.0, 17.0):   # stairs up to the wall walk
        x, _, _ = M(lx, 0)
        for i in range(8):
            k.box((x + i * 0.35, y0 - 0.45, 0.4 + i * 0.75), (0.4, 0.9, 0.8), "cstone_d")
    # W + E walls (outer faces lx 2.0 / 22.0)
    for sgn, (ax, bx) in ((1, (2.0, 3.7)), (-1, (20.3, 22.0))):
        x0, x1, y0, y1 = wall_box(ax, 2.9, bx, 21.1)
        xo = x0 + 0.25 if sgn > 0 else x1 - 0.25
        merlon_row(k, y0 + 1.6, y1 - 1.6, xo, WALL_H, depth=0.5, along="y")
        k.box((xo, (y0 + y1) / 2, WALL_H + 0.2), (0.5, y1 - y0, 0.4), "cstone_l")
        xi = x1 - 0.1 if sgn > 0 else x0 + 0.1
        k.box((xi, (y0 + y1) / 2, WALL_H + 0.15), (0.2, y1 - y0, 0.3), "ctrim")
        # plinth into moat
        xp = x0 - 0.12 if sgn > 0 else x1 + 0.12
        k.box((xp, (y0 + y1) / 2, (zb + 0.5) / 2), (0.3, y1 - y0, 0.5 - zb), "cplinth")
        # buttresses on the outer face (seen edge-on but give the silhouette/top some bumps)
        for ly in (7.0, 16.5):
            _, yy, _ = M(0, ly)
            xb = x0 - 0.35 if sgn > 0 else x1 + 0.35
            k.box((xb, yy, (zb + 4.2) / 2), (0.75, 1.0, 4.2 - zb), "cstone", taper=0.8)
    # S wall segments (outer face ly 22.0, inner 20.0) - west and east of the gatehouse
    for (ax, bx) in ((2.9, 8.3), (15.7, 21.1)):
        x0, x1, y0, y1 = wall_box(ax, S_WALL_IN, bx, S_WALL_OUT)
        yf = y0          # south face (most negative y)
        k.box(((x0 + x1) / 2, yf - 0.12, (zb + 0.9) / 2), (x1 - x0, 0.3, 0.9 - zb), "cplinth", taper=1.0)
        k.box(((x0 + x1) / 2, yf - 0.03, 2.0), (x1 - x0, 0.1, 0.22), "ctrim")          # string course
        k.box(((x0 + x1) / 2, yf - 0.05, WALL_H - 0.25), (x1 - x0, 0.14, 0.2), "ctrim")
        ashlar(k, x0 + 1.4, x1 - 1.4, 0.2, WALL_H - 0.5, yf, 34)
        # buttresses into the moat
        for t in (0.3, 0.72):
            xb = x0 + (x1 - x0) * t
            wedge(k, xb, yf, 1.25, 1.0, zb, 4.6, 1.2, "cstone")
            wedge(k, xb, yf - 0.02, 1.45, 1.15, zb, 0.9, 0.5, "cplinth")
        # arrow slits
        for t in (0.15, 0.5, 0.86):
            slit(k, x0 + (x1 - x0) * t, yf - 0.02, 3.6)
        # wall walk surface + inner lip (visible between the parapet and the courtyard)
        k.box(((x0 + x1) / 2, y1 - 0.1, WALL_H + 0.12), (x1 - x0, 0.2, 0.25), "ctrim")
        # FRONT parapet (own layer: drawn after entities so wall-walk NPCs stand behind it)
        k.use("front")
        k.box(((x0 + x1) / 2, yf + 0.3, WALL_H + 0.45), (x1 - x0, 0.6, 0.9), "cstone")
        k.box(((x0 + x1) / 2, yf + 0.3, WALL_H + 0.92), (x1 - x0 + 0.02, 0.64, 0.08), "ctrim")
        merlon_row(k, x0 + 1.4, x1 - 1.4, yf + 0.3, WALL_H + 0.95, depth=0.6, h=0.8)
        k.use("body")
        # banner + torch on each segment
        xm = (x0 + x1) / 2
        banner(k, xm, yf, WALL_H - 0.5, w=1.1, h=2.6)
        wall_torch(k, xm - 1.2 if ax < 10 else xm + 1.2, yf, 3.1)

    # ------------------------------------------------------------ TOWERS
    for (cx, cy) in ((2.9, 2.9), (21.1, 2.9)):
        tower(k, cx, cy, 1.6, 12.0, 6.2, segs=10, slits=((-30, 7.5), (30, 7.5), (0, 9.5)), flag_len=1.7)
    for (cx, cy) in ((2.9, 21.1), (21.1, 21.1)):
        tower(k, cx, cy, 1.65, 12.0, 6.4, segs=10,
              slits=((-35, 3.2), (0, 5.3), (35, 3.2), (0, 8.4), (-40, 7.0), (40, 7.0)), flag_len=1.8)
    for (cx, cy) in ((2.6, 12.0), (21.4, 12.0)):
        tower(k, cx, cy, 1.3, 9.8, 5.0, segs=9, slits=((0, 4.5), (0, 7.6)), flag_len=1.3)

    # ------------------------------------------------------------ GATEHOUSE
    gc = (GATE_X0 + GATE_X1) / 2
    gx, gy_face, _ = M(gc, S_WALL_OUT)
    gw = (13.9 - 10.1) * T
    gdepth = (S_WALL_OUT - 19.6) * T
    GH = 9.4
    mark = len(k.verts)
    info = k.archway(width=(GATE_X1 - GATE_X0) * T, spring=2.0, depth=gdepth, outer_w=gw, outer_h=GH,
                     front="cstone", inner=["cstone_d", "interior", "interior"], shape="round", segs=9,
                     y0=0.0, z0=0.0, jag=0.0, floor="ctrim", back=False, slices=3, bulge=0.04)
    k.transform_since(mark, offset=(gx, gy_face, 0))
    # archway z0=0 -> extend the slab down into the water (plinth)
    k.box((gx, gy_face + gdepth / 2, zb / 2), (gw, gdepth, -zb), "cplinth")
    # passage end: a sunlit glimpse of the courtyard
    hw = (GATE_X1 - GATE_X0) * T / 2
    pts = [(gx - hw, gy_face + gdepth - 0.02, 0.0)]
    for i in range(10):
        a = math.pi * (1 - i / 9)
        pts.append((gx + hw * math.cos(a), gy_face + gdepth - 0.02, 2.0 + hw * math.sin(a)))
    pts.append((gx + hw, gy_face + gdepth - 0.02, 0.0))
    dbl(k, pts, "glimpse")
    # passage floor (walkable look)
    k.box((gx, gy_face + gdepth / 2, 0.02), (2 * hw, gdepth, 0.04), "cstone_l")
    # brick voussoirs around the arch (like the old castle's brick arch)
    nv = 13
    for i in range(nv):
        a = math.pi * (1 - (i + 0.5) / nv)
        rr = hw + 0.28
        vx, vz = gx + rr * math.cos(a), 2.0 + rr * math.sin(a)
        k.box((vx, gy_face - 0.06, vz), (0.34, 0.14, 0.55), "arch_brick" if i != nv // 2 else "ctrim",
              rot=(0, -math.degrees(a) + 90, 0))
    for sx in (-1, 1):   # brick jambs
        for j in range(3):
            k.box((gx + sx * (hw + 0.24), gy_face - 0.06, 0.35 + j * 0.62), (0.5, 0.14, 0.5), "arch_brick")
    # chain slots + pulleys
    for sx in (-1, 1):
        px, pz = gx + sx * PULLEY[0], PULLEY[2]
        k.box((px, gy_face - 0.02, pz), (0.36, 0.1, 0.4), "slit!")
        k.cyl((px, gy_face - 0.12, pz + 0.25), 0.2, 0.2, 0.12, "iron", 8, rot=(90, 0, 0))
    # machicolation gallery above the arch
    k.box((gx, gy_face - 0.35, 6.4), (gw - 0.4, 0.7, 1.0), "cstone")
    for i in range(7):
        k.box((gx - gw / 2 + 0.5 + i * (gw - 1.0) / 6, gy_face - 0.3, 5.7), (0.3, 0.6, 0.45), "cstone_d")
    k.box((gx, gy_face - 0.72, 7.05), (gw - 0.3, 0.1, 0.3), "ctrim")
    merlon_row(k, gx - gw / 2 + 0.3, gx + gw / 2 - 0.3, gy_face - 0.45, 6.9, depth=0.5, h=0.75, w=0.6, gap=0.45)
    # coat of arms between the pulleys
    cz = 4.75
    dbl(k, [(gx - 0.55, gy_face - 0.1, cz + 0.6), (gx + 0.55, gy_face - 0.1, cz + 0.6), (gx + 0.5, gy_face - 0.1, cz - 0.1),
            (gx, gy_face - 0.1, cz - 0.6), (gx - 0.5, gy_face - 0.1, cz - 0.1)], "banner")
    dbl(k, [(gx - 0.08, gy_face - 0.12, cz + 0.45), (gx + 0.08, gy_face - 0.12, cz + 0.45),
            (gx + 0.08, gy_face - 0.12, cz - 0.4), (gx - 0.08, gy_face - 0.12, cz - 0.4)], "gold")
    dbl(k, [(gx - 0.38, gy_face - 0.12, cz + 0.2), (gx + 0.38, gy_face - 0.12, cz + 0.2),
            (gx + 0.38, gy_face - 0.12, cz + 0.06), (gx - 0.38, gy_face - 0.12, cz + 0.06)], "gold")
    # gatehouse top parapet (front + back) and a roofed winch house
    k.box((gx, gy_face + 0.25, GH + 0.4), (gw, 0.5, 0.8), "cstone")
    merlon_row(k, gx - gw / 2 + 0.3, gx + gw / 2 - 0.3, gy_face + 0.25, GH + 0.8, depth=0.5, h=0.7, w=0.6, gap=0.45)
    k.box((gx, gy_face + gdepth - 0.25, GH + 0.4), (gw, 0.5, 0.8), "cstone")
    merlon_row(k, gx - gw / 2 + 0.3, gx + gw / 2 - 0.3, gy_face + gdepth - 0.25, GH + 0.8, depth=0.5, h=0.7, w=0.6, gap=0.45)
    k.box((gx, gy_face + gdepth * 0.55, GH + 1.0), (2.8, 1.8, 2.0), "cstone_l")
    k.box((gx, gy_face + gdepth * 0.55 - 0.45, GH + 2.35), (3.3, 1.25, 0.12), "roof", rot=(32, 0, 0))
    k.box((gx, gy_face + gdepth * 0.55 + 0.45, GH + 2.35), (3.3, 1.25, 0.12), "roof_d", rot=(-32, 0, 0))
    k.box((gx, gy_face + gdepth * 0.55 - 0.92, GH + 0.8), (0.7, 0.08, 1.1), "wood_dark")
    # torches either side of the arch
    for sx in (-1, 1):
        wall_torch(k, gx + sx * (hw + 0.95), gy_face, 2.8)
    # gate towers
    for sx in (-1, 1):
        tcx = gc + sx * 2.75
        ztop = tower(k, tcx, 21.35, 1.45, 11.0, 5.4, segs=10,
                     slits=((0, 2.3), (0, 7.9), (-sx * 40, 5.0), (sx * 40, 5.0)), flag_len=1.5)
        x, y, _ = M(tcx, 21.35)
        banner(k, x, y - 1.45 * T - 0.02, 6.3, w=0.9, h=2.2)

    # ------------------------------------------------------------ KEEP (central)
    kx0, ky0, kx1, ky1 = 7.0, 4.2, 17.0, 10.0
    a, b = M(kx0, ky0), M(kx1, ky1)
    KX0, KX1 = a[0], b[0]
    KYN, KYS = a[1], b[1]          # north (less negative) / south face y
    KH = 11.5
    kcx = (KX0 + KX1) / 2
    k.box((kcx, (KYN + KYS) / 2, 0.8), (KX1 - KX0 + 0.5, KYN - KYS + 0.5, 1.6), "cplinth", taper=0.96)
    k.box((kcx, (KYN + KYS) / 2, KH / 2), (KX1 - KX0, KYN - KYS, KH), "cstone")
    for z in (4.4, 8.6):
        k.box((kcx, KYS - 0.04, z), (KX1 - KX0 + 0.08, 0.12, 0.24), "ctrim")
    ashlar(k, KX0 + 0.6, KX1 - 0.6, 1.8, KH - 0.8, KYS, 60)
    # pilaster buttresses on the front face
    for t in (0.0, 0.25, 0.75, 1.0):
        xb = KX0 + (KX1 - KX0) * t
        k.box((xb, KYS - 0.25, 4.5), (0.8, 0.6, 9.0), "cstone", taper=0.9)
    # windows (2 rows, some lit)
    for row, z in ((0, 6.1), (1, 10.2)):
        for t in (0.12, 0.37, 0.63, 0.88):
            xw = KX0 + (KX1 - KX0) * t
            lit = (row + int(t * 10)) % 3 == 0
            k.box((xw, KYS - 0.05, z), (0.95, 0.12, 1.55), "ctrim")
            k.box((xw, KYS - 0.08, z - 0.05), (0.55, 0.1, 1.15), "window" if lit else "slit!")
            k.box((xw, KYS - 0.1, z + 0.62), (0.75, 0.14, 0.2), "cstone_l")
    # keep door with steps and a porch
    dx = kcx
    k.box((dx, KYS - 0.06, 1.7), (2.2, 0.14, 3.4), "ctrim")
    k.box((dx, KYS - 0.1, 1.45), (1.6, 0.12, 2.9), "wood_dark")
    for i in range(3):
        k.box((dx - 0.4 + i * 0.4, KYS - 0.14, 1.45), (0.06, 0.1, 2.8), "wood")
    k.cyl((dx, KYS - 0.13, 2.9), 0.8, 0.8, 0.1, "arch_brick", 8, rot=(90, 0, 0))
    for i in range(3):
        k.box((dx, KYS - 0.5 - i * 0.35, 0.12 + (2 - i) * 0.2), (3.2 + i * 0.4, 0.4, 0.24 + (2 - i) * 0.4), "cstone_l")
    for sx in (-1, 1):
        banner(k, dx + sx * 3.2, KYS, 9.3, w=1.3, h=3.6)
        wall_torch(k, dx + sx * 1.6, KYS, 2.6)
    # keep parapet + corner bartizans
    for (xa, xb2, yy) in ((KX0, KX1, KYS + 0.25), (KX0, KX1, KYN - 0.25)):
        k.box(((xa + xb2) / 2, yy, KH + 0.35), (xb2 - xa, 0.5, 0.7), "cstone")
        merlon_row(k, xa + 0.6, xb2 - 0.6, yy, KH + 0.7, depth=0.5, h=0.75)
    for xx in (KX0 + 0.25, KX1 - 0.25):
        k.box((xx, (KYN + KYS) / 2, KH + 0.35), (0.5, KYN - KYS, 0.7), "cstone")
        merlon_row(k, KYS + 0.6, KYN - 0.6, xx, KH + 0.7, depth=0.5, h=0.75, along="y")
    for (xx, yy) in ((KX0, KYS), (KX1, KYS), (KX0, KYN), (KX1, KYN)):
        k.cyl((xx, yy, KH - 2.5), 0.3, 1.0, 1.0, "cstone_d", 8)
        k.cyl((xx, yy, KH - 1.5), 1.0, 1.0, 2.6, "cstone", 8)
        k.cyl((xx, yy, KH + 1.1), 1.2, 0, 3.0, "roof", 8)
        k.cone((xx, yy, KH + 4.0), 0.08, 0.3, "gold", segs=4)
    # central great tower rising from the keep
    tcx, tcy = kcx, (KYN + KYS) / 2 + 0.6
    TS = 5.0
    k.box((tcx, tcy, KH + 3.25), (TS, TS, 6.5), "cstone")
    k.box((tcx, tcy - TS / 2 - 0.03, KH + 3.0), (TS + 0.06, 0.1, 0.22), "ctrim")
    for (ox, z, lit) in ((-1.2, KH + 2.0, True), (1.2, KH + 2.0, False), (0.0, KH + 4.6, True)):
        k.box((tcx + ox, tcy - TS / 2 - 0.04, z), (0.8, 0.1, 1.3), "ctrim")
        k.box((tcx + ox, tcy - TS / 2 - 0.07, z - 0.05), (0.45, 0.1, 0.95), "window" if lit else "slit!")
    for i in range(8):   # corbels
        for side in (-1, 1):
            k.box((tcx - TS / 2 + 0.35 + i * (TS - 0.7) / 7, tcy + side * (TS / 2 + 0.12), KH + 6.2), (0.3, 0.35, 0.45), "cstone_d")
    k.box((tcx, tcy, KH + 6.9), (TS + 0.6, TS + 0.6, 0.8), "cstone")
    for side in (-1, 1):
        merlon_row(k, tcx - TS / 2, tcx + TS / 2, tcy + side * (TS / 2 + 0.05), KH + 7.3, depth=0.45, h=0.75, w=0.6, gap=0.5)
        merlon_row(k, tcy - TS / 2, tcy + TS / 2, tcx + side * (TS / 2 + 0.05), KH + 7.3, depth=0.45, h=0.75, w=0.6, gap=0.5, along="y")
    k.cyl((tcx, tcy, KH + 8.1), (TS / 2) * 1.25, 0, 5.8, "roof", 8, rot=(0, 0, 22.5))
    k.cone((tcx, tcy, KH + 13.8), 0.16, 0.5, "gold", segs=5)
    flag(k, tcx, tcy, KH + 16.2, length=2.4, height=1.4)

    # ------------------------------------------------------------ POSTS (abutment pillars + braziers)
    k.use("posts")
    for sx in (-1, 1):
        x, y, _ = M(gc + sx * 1.35, W24 - 0.12)
        k.box((x, y, 0.55), (0.62, 0.62, 1.3), "cstone")
        k.box((x, y, 1.25), (0.78, 0.78, 0.14), "ctrim")
        brazier(k, x, y, 1.32)

    # ------------------------------------------------------------ GATE PARTS (local pivot space)
    # drawbridge: hinge line at origin, deck lies along -Y (open), top surface z=0
    k.use("bridge")
    L, Wd = BRIDGE_L, BRIDGE_W
    nb = 7
    for i in range(nb):
        bx = -Wd / 2 + (i + 0.5) * Wd / nb
        k.box((bx, -L / 2, -0.12), (Wd / nb - 0.03, L, 0.22), rng.choice(["plank", "wood", "plank"]))
    for yy in (-0.35, -L / 2, -L + 0.35):                 # iron bands top + bottom
        k.box((0, yy, 0.005), (Wd + 0.04, 0.16, 0.03), "iron!")
        k.box((0, yy, -0.245), (Wd + 0.04, 0.16, 0.03), "iron!")
    for sx in (-1, 1):                                      # side beams + studs
        k.box((sx * (Wd / 2 + 0.07), -L / 2, -0.1), (0.14, L, 0.3), "wood_dark")
        for j in range(5):
            k.box((sx * (Wd / 2 + 0.15), -0.3 - j * (L - 0.6) / 4, -0.08), (0.04, 0.1, 0.1), "iron!")
    for yy in (-0.9, -L + 0.9):                            # underside cross beams (seen when raised)
        k.box((0, yy, -0.3), (Wd, 0.22, 0.14), "wood_dark")
    k.box((0, -L / 2, -0.3), (0.2, L - 0.4, 0.12), "wood_dark", rot=(0, 0, 0))
    for sx in (-1, 1):                                      # tip rings
        k.cyl((sx * 1.5, -L + 0.12, 0.02), 0.09, 0.09, 0.05, "iron!", 6)
    # portcullis: bottom centre at origin, grid in the XZ plane
    k.use("portcullis")
    nvb, nhb = 8, 6
    for i in range(nvb):
        bx = -PORT_W / 2 + (i + 0.5) * PORT_W / nvb
        k.box((bx, 0, PORT_H / 2 + 0.15), (0.1, 0.12, PORT_H - 0.3), "iron")
        k.cyl((bx, 0, 0.32), 0.07, 0.0, 0.32, "steel", segs=4, rot=(180, 0, 0))
    for j in range(nhb):
        z = 0.45 + j * (PORT_H - 0.7) / (nhb - 1)
        k.box((0, 0.0, z), (PORT_W, 0.1, 0.1), "iron")
    k.box((0, 0, PORT_H - 0.05), (PORT_W + 0.1, 0.16, 0.18), "iron!")
    # chains: rigid rods, origin at the bridge-tip ring, links along local +Z
    for side in ("chain_l", "chain_r"):
        k.use(side)
        n = int(CHAIN_L / 0.16)
        for i in range(n):
            z = 0.08 + i * 0.16
            if i % 2 == 0:
                k.box((0, 0, z), (0.15, 0.05, 0.21), "chain", jitter=False)
            else:
                k.box((0, 0, z), (0.05, 0.15, 0.21), "chain", jitter=False)
    k.use("body")
    return {"gate_centre_x_m": gx, "gate_face_y_m": gy_face, "keep_h": KH, "gatehouse_h": GH}
