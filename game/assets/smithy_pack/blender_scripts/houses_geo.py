"""houses_geo.py - geometry for the 11 bigger Mythoscape houses (OSRS low-poly, per-face colours).

Local tile coords: lx east, ly south; (0,0) = NW corner of the footprint's NW tile.
M(lx, ly, z) -> metres (lx*T, -ly*T, z).  T = 40 px / 26.9 px-per-m = 1.487 m.
Front (door) faces -Y (south, towards the game camera).  Parts: 'ground' (under entities) and
'body' (y-sorted at the footprint's south row).  The camera looks straight north at 32 deg, so all
detail goes on south faces, roofs and things that stick out.
"""
import math, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from osrs_kit import Kit, GAME_PX_PER_M  # noqa: E402
import prop_parts as pp  # noqa: E402

T = 40.0 / GAME_PX_PER_M

PAL = dict(pp.P)
PAL.update({
    "plinth": "#76767a", "step": "#8e8c86", "plaster": "#e2d7bd", "white": "#e9e4d6", "beam": "#4a3322",
    "plank_l": "#a4804e", "plank_g": "#7f8a90", "plank_b": "#6f8596", "plank_w": "#8c7a62",
    "roof_brown": "#6b3f28", "roof_tile": "#8e4a32", "roof_slate": "#4b5059", "roof_green": "#4a5e56",
    "roof_purple": "#6c4a82", "thatch": "#c9a452", "thatch_d": "#a88538", "trim": "#d8cfb8",
    "sstone": "#9a9a9c", "sstone_d": "#7c7d80", "sstone_l": "#b4b4b4", "marble": "#c9c6bd",
    "glass": "#35506a", "window": "#ffd27a", "frame": "#3a2a1e", "frame_w": "#e6e1d4", "shutter": "#3f6a4a",
    "door": "#6a4226", "door_d": "#4a2c18", "iron": "#3b3e44", "gold": "#d7b03e", "red": "#a3262b",
    "blue": "#2f5f9a", "teal": "#3f9c98", "pink": "#d98aa6", "yellow": "#e3c24a", "purple": "#7a4f9a",
    "cream": "#efe6cf", "green": "#4f8a3a", "leaf": "#5f9a3e", "soil": "#5a4430", "grass": "#5e7a3c",
    "hay": "#d2b25a", "water": "#3a6f96", "water_hi": "#86bfe0", "ice": "#cfe6ee", "fish": "#9fb4c0",
    "fish_d": "#6d8796", "rope": "#b09560", "net": "#5a5040", "flower_r": "#d0443c", "flower_y": "#f0cf4a",
    "dog": "#b07a44", "bird": "#f2d03a", "lantern": "#ffcf6a", "brick_arch": "#9a5a3c", "fire": "#ff9a3a",
    "banner_g": "#3d6b3a", "cobble": "#8a8780", "deck": "#8f7a5c", "post": "#5a4632",
})
EMISSIVE = {"window": 1.6, "lantern": 5.0, "fire": 6.0, "water": 0.35, "water_hi": 0.5}


def M(lx, ly, z=0.0):
    return (lx * T, -ly * T, z)


class HK(Kit):
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

    # --- tile-space helpers ------------------------------------------------
    def B(self, lx0, ly0, lx1, ly1, z0, z1, mat, taper=1.0, jitter=True):
        self.box(((lx0 + lx1) / 2 * T, -(ly0 + ly1) / 2 * T, (z0 + z1) / 2),
                 (abs(lx1 - lx0) * T, abs(ly1 - ly0) * T, z1 - z0), mat, taper=taper, jitter=jitter)

    def Bm(self, cx, cy, cz, sx, sy, sz, mat, jitter=True):     # metres, centre
        self.box((cx, cy, cz), (sx, sy, sz), mat, jitter=jitter)

    def slab(self, p, thick, mat, jitter=True):
        top = [tuple(q) for q in p]
        bot = [(q[0], q[1], q[2] - thick) for q in p]
        self.add(top + bot, [(0, 1, 2, 3), (7, 6, 5, 4), (0, 4, 5, 1), (1, 5, 6, 2), (2, 6, 7, 3), (3, 7, 4, 0)],
                 mat, jitter=jitter)

    def shingles(self, p, thick, mat, n=None):
        """Slope quad p = [eaveA, eaveB, ridgeB, ridgeA] split into n overlapping courses (tile rows)."""
        import mathutils
        P = [mathutils.Vector(q) for q in p]
        L = (P[3] - P[0]).length
        n = n or max(3, int(L / 0.55))
        for i in range(n):
            t0, t1 = i / n, min(1.0, (i + 1) / n + 0.04)
            a = P[0].lerp(P[3], t0); b = P[1].lerp(P[2], t0)
            c = P[1].lerp(P[2], t1); d = P[0].lerp(P[3], t1)
            drop = mathutils.Vector((0, 0, -0.06 if i % 2 == 0 else 0.0))
            self.slab([a + drop, b + drop, c, d], thick, mat)

    def tri(self, a, b, c, mat):
        self.add([a, b, c], [(0, 1, 2)], mat, jitter=False)

    def roof_ew(self, lx0, ly0, lx1, ly1, zb, rh, mat, o=0.3, gable="plaster", thick=0.25, hip=0.0, courses=True):
        """Ridge along X. hip>0 pulls the ridge ends in (tiles) = hipped roof."""
        x0, x1 = (lx0 - o) * T, (lx1 + o) * T
        yS, yN = -(ly1 + o) * T, -(ly0 - o) * T
        ym = (yS + yN) / 2
        zt = zb + rh
        h = hip * T
        (self.shingles if courses else self.slab)([(x0, yS, zb), (x1, yS, zb), (x1 - h, ym, zt), (x0 + h, ym, zt)], thick, mat)
        self.slab([(x1, yN, zb), (x0, yN, zb), (x0 + h, ym, zt), (x1 - h, ym, zt)], thick, mat)
        if hip > 0:
            self.tri((x0, yS, zb), (x0 + h, ym, zt), (x0, yN, zb), mat)
            self.tri((x1, yN, zb), (x1 - h, ym, zt), (x1, yS, zb), mat)
        else:
            wy0, wy1 = -ly1 * T, -ly0 * T
            for xx in (lx0 * T + 0.02, lx1 * T - 0.02):
                self.tri((xx, wy0, zb), (xx, (wy0 + wy1) / 2, zb + rh * (wy1 - wy0) / (yN - yS)), (xx, wy1, zb), gable)
        self.Bm((x0 + x1) / 2, ym, zt + 0.05, x1 - x0 - 2 * h + 0.1, 0.3, 0.22, mat + "!" if False else mat)

    def roof_ns(self, lx0, ly0, lx1, ly1, zb, rh, mat, o=0.3, gable="plaster", thick=0.25, barge="beam"):
        """Ridge along Y: a front gable facing the camera."""
        x0, x1 = (lx0 - o) * T, (lx1 + o) * T
        yS, yN = -(ly1 + o) * T, -(ly0 - o) * T
        xm = (x0 + x1) / 2
        zt = zb + rh
        self.shingles([(x0, yN, zb), (x0, yS, zb), (xm, yS, zt), (xm, yN, zt)], thick, mat)
        self.shingles([(x1, yS, zb), (x1, yN, zb), (xm, yN, zt), (xm, yS, zt)], thick, mat)
        wx0, wx1 = lx0 * T, lx1 * T
        ys = -ly1 * T - 0.02
        k = (wx1 - wx0) / (x1 - x0)
        self.tri((wx0, ys, zb), (wx1, ys, zb), (xm, ys, zb + rh * k), gable)
        self.tri((wx1, -ly0 * T, zb), (wx0, -ly0 * T, zb), (xm, -ly0 * T, zb + rh * k), gable)
        # bargeboards along the front gable edge
        if barge:
            for sx in (-1, 1):
                ex = x0 if sx < 0 else x1
                self._beam((ex, yS - 0.04, zb - 0.05), (xm, yS - 0.04, zt + 0.02), 0.22, barge)
        self.Bm(xm, (yS + yN) / 2, zt + 0.04, 0.3, yN - yS + 0.1, 0.2, mat)

    def _beam(self, a, b, w, mat):
        dx, dz = b[0] - a[0], b[2] - a[2]
        L = math.hypot(dx, dz)
        ang = math.degrees(math.atan2(dz, dx))
        self.box(((a[0] + b[0]) / 2, (a[1] + b[1]) / 2, (a[2] + b[2]) / 2), (L, 0.12, w), mat,
                 rot=(0, -ang, 0))

    def walls(self, lx0, ly0, lx1, ly1, z0, z1, mat):
        self.B(lx0, ly0, lx1, ly1, z0, z1, mat)

    def plinth(self, lx0, ly0, lx1, ly1, h=0.35, mat="plinth", grow=0.12):
        self.B(lx0 - grow, ly0 - grow, lx1 + grow, ly1 + grow, 0, h, mat)

    def chimney(self, lx, ly, z0, z1, mat="sstone", w=0.55):
        self.B(lx - w / 2, ly - w / 2, lx + w / 2, ly + w / 2, z0, z1, mat)
        self.B(lx - w / 2 - 0.06, ly - w / 2 - 0.06, lx + w / 2 + 0.06, ly + w / 2 + 0.06, z1, z1 + 0.25, "sstone_d")

    # --- south-face details (face_ly = wall's south face) ------------------
    def door(self, cx, face_ly, w=1.6, h=2.6, arch="brick_arch", wood="door", band="iron", double=True,
             round_top=True, z0=0.35):
        x = cx * T
        y = -face_ly * T
        self.Bm(x, y + 0.05, z0 + h / 2, w + 0.1, 0.14, h, "interior_deep")
        n = 2 if double else 1
        for i in range(n):
            px = x + (i - (n - 1) / 2) * (w / n)
            hh = h - (w / 2 if round_top else 0)
            self.Bm(px, y - 0.03, z0 + hh / 2, w / n - 0.06, 0.1, hh, wood)
            for bz in (0.35, hh - 0.35):
                self.Bm(px, y - 0.1, z0 + bz, w / n - 0.1, 0.05, 0.12, band)
        if round_top:
            r = w / 2
            zc = z0 + h - r
            pts = [(x + r * math.cos(math.pi * i / 8), y - 0.04, zc + r * math.sin(math.pi * i / 8)) for i in range(9)]
            self.add([(x, y - 0.04, zc)] + pts, [(0, i + 1, i + 2) for i in range(8)], wood, jitter=False)
            if arch:
                for i in range(9):
                    a = math.pi * i / 8
                    rr = r + 0.18
                    self.box((x + rr * math.cos(a), y - 0.1, zc + rr * math.sin(a)), (0.3, 0.2, 0.34), arch,
                             rot=(0, -math.degrees(a) + 90, 0))
                for sx in (-1, 1):
                    self.Bm(x + sx * (r + 0.18), y - 0.1, z0 + (h - r) / 2, 0.34, 0.2, h - r, arch)
        elif arch:
            for sx in (-1, 1):
                self.Bm(x + sx * (w / 2 + 0.12), y - 0.1, z0 + h / 2, 0.24, 0.2, h, arch)
            self.Bm(x, y - 0.1, z0 + h + 0.14, w + 0.5, 0.22, 0.3, arch)
        self.Bm(x + 0.25, y - 0.12, z0 + 1.1, 0.1, 0.06, 0.1, "gold")

    def window(self, cx, face_ly, zc, w=0.9, h=1.1, lit=False, frame="frame", bars=False, shutters=None,
               box=None, sill="trim"):
        x, y = cx * T, -face_ly * T
        self.Bm(x, y - 0.01, zc, w, 0.08, h, "window" if lit else "glass", jitter=False)
        for dx in (-w / 2, w / 2):
            self.Bm(x + dx, y - 0.06, zc, 0.1, 0.1, h + 0.1, frame)
        for dz in (-h / 2, h / 2):
            self.Bm(x, y - 0.06, zc + dz, w + 0.1, 0.1, 0.1, frame)
        self.Bm(x, y - 0.06, zc, 0.07, 0.08, h, frame)
        self.Bm(x, y - 0.06, zc, w, 0.08, 0.07, frame)
        if bars:
            for i in range(4):
                self.Bm(x - w / 2 + (i + 0.5) * w / 4, y - 0.12, zc, 0.05, 0.05, h, "iron")
        self.Bm(x, y - 0.12, zc - h / 2 - 0.05, w + 0.3, 0.26, 0.1, sill)
        if shutters:
            for sx in (-1, 1):
                self.Bm(x + sx * (w / 2 + 0.25), y - 0.06, zc, 0.42, 0.08, h, shutters)
        if box:
            self.Bm(x, y - 0.25, zc - h / 2 - 0.22, w + 0.2, 0.34, 0.28, "wood")
            for i in range(5):
                self.Bm(x - w / 2 + i * w / 4, y - 0.28, zc - h / 2 - 0.02, 0.18, 0.22, 0.2,
                        box[i % len(box)], jitter=False)

    def beams_front(self, lx0, lx1, face_ly, z0, z1, n=6, mat="beam", diag=True):
        y = -face_ly * T - 0.04
        for i in range(n + 1):
            x = (lx0 + (lx1 - lx0) * i / n) * T
            self.Bm(x, y, (z0 + z1) / 2, 0.18, 0.08, z1 - z0, mat)
        for z in (z0 + 0.08, z1 - 0.08):
            self.Bm((lx0 + lx1) / 2 * T, y, z, (lx1 - lx0) * T, 0.08, 0.16, mat)
        if diag:
            for i in range(n):
                xa = (lx0 + (lx1 - lx0) * i / n) * T
                xb = (lx0 + (lx1 - lx0) * (i + 1) / n) * T
                if i % 2 == 0:
                    self._beam((xa, y, z0), (xb, y, z1), 0.14, mat)
                else:
                    self._beam((xa, y, z1), (xb, y, z0), 0.14, mat)

    def sign(self, cx, face_ly, z, w=1.0, h=0.7, board="wood", icon=None, side=1):
        x, y = cx * T, -face_ly * T
        self.Bm(x, y - 0.55, z + 0.1, 0.1, 1.1, 0.1, "iron")
        self.Bm(x, y - 0.15, z - 0.25, 0.08, 0.08, 0.6, "iron")
        for sx in (-1, 1):
            self.Bm(x + sx * w * 0.35, y - 0.95, z - 0.15, 0.03, 0.03, 0.3, "iron", jitter=False)
        self.Bm(x, y - 0.95, z - 0.3 - h / 2, w, 0.1, h, board)
        self.Bm(x, y - 0.95, z - 0.3 - h / 2, w + 0.1, 0.07, h + 0.1, "beam")
        if icon:
            icon(self, x, y - 1.02, z - 0.3 - h / 2)

    def awning(self, lx0, lx1, face_ly, ztop, depth=1.4, drop=0.7, mats=("red", "cream"), n=None):
        y0 = -face_ly * T
        n = n or max(2, int((lx1 - lx0) * T / 0.45))
        for i in range(n):
            xa = (lx0 + (lx1 - lx0) * i / n) * T
            xb = (lx0 + (lx1 - lx0) * (i + 1) / n) * T
            m = mats[i % len(mats)]
            self.slab([(xa, y0 - depth, ztop - drop), (xb, y0 - depth, ztop - drop), (xb, y0, ztop), (xa, y0, ztop)],
                      0.06, m, jitter=False)
            self.Bm((xa + xb) / 2, y0 - depth - 0.02, ztop - drop - 0.18, xb - xa - 0.02, 0.05, 0.36, m, jitter=False)
        for lx in (lx0, lx1):
            self._beam((lx * T, y0 - depth, ztop - drop), (lx * T, y0, ztop), 0.06, "iron")

    # --- props (tile coords of the prop's centre) ----------------------------
    def barrel(self, lx, ly, z=0.0, r=0.36, h=0.95, mat="wood"):
        x, y = lx * T, -ly * T
        self.cyl((x, y, z), r * 0.92, r, h / 2, mat, segs=8)
        self.cyl((x, y, z + h / 2), r, r * 0.92, h / 2, mat, segs=8)
        for zz in (0.18, h - 0.2):
            self.cyl((x, y, z + zz), r + 0.02, r + 0.02, 0.06, "iron", segs=8, jitter=False)

    def crate(self, lx, ly, s=0.75, z=0.0, mat="plank"):
        x, y = lx * T, -ly * T
        self.Bm(x, y, z + s / 2, s, s, s, mat)
        self.Bm(x, y - s / 2 - 0.01, z + s / 2, s * 0.9, 0.03, 0.1, "wood_d", jitter=False)

    def sack(self, lx, ly, z=0.0, mat="plank_l"):
        x, y = lx * T, -ly * T
        self.box((x, y, z + 0.35), (0.6, 0.45, 0.7), "hay" if mat == "hay" else "trim", taper=0.7)
        self.Bm(x, y, z + 0.74, 0.12, 0.12, 0.1, "rope")

    def bale(self, lx, ly, z=0.0, rot=0):
        self.box((lx * T, -ly * T, z + 0.35), (1.1, 0.7, 0.7), "hay", rot=(0, 0, rot))
        self.box((lx * T, -ly * T, z + 0.35), (1.12, 0.1, 0.72), "thatch_d", rot=(0, 0, rot), jitter=False)

    def fence(self, pts, h=0.9, mat="plank_w"):
        for (ax, ay), (bx, by) in zip(pts, pts[1:]):
            L = math.hypot(bx - ax, by - ay)
            n = max(1, int(L * T / 1.2))
            for i in range(n + 1):
                t = i / n
                self.B(ax + (bx - ax) * t - 0.05, ay + (by - ay) * t - 0.05, ax + (bx - ax) * t + 0.05,
                       ay + (by - ay) * t + 0.05, 0, h, "post")
            ang = math.degrees(math.atan2(-(by - ay), bx - ax))
            for z in (h * 0.45, h * 0.85):
                self.box(((ax + bx) / 2 * T, -(ay + by) / 2 * T, z), (L * T, 0.07, 0.1), mat, rot=(0, 0, ang))

    def bench(self, lx, ly, w=1.6):
        x, y = lx * T, -ly * T
        self.Bm(x, y, 0.45, w, 0.4, 0.08, "plank")
        for sx in (-1, 1):
            self.Bm(x + sx * (w / 2 - 0.15), y, 0.22, 0.1, 0.34, 0.44, "wood_d")

    def table(self, lx, ly, w=1.3):
        x, y = lx * T, -ly * T
        self.Bm(x, y, 0.75, w, 0.8, 0.08, "plank")
        self.Bm(x, y, 0.37, 0.16, 0.16, 0.74, "wood_d")

    def column(self, lx, ly, h, r=0.3, mat="marble"):
        x, y = lx * T, -ly * T
        self.Bm(x, y, 0.12, r * 2.6, r * 2.6, 0.24, mat)
        self.cyl((x, y, 0.24), r, r * 0.88, h - 0.5, mat, segs=10)
        self.Bm(x, y, h - 0.13, r * 2.6, r * 2.6, 0.26, mat)

    def post(self, lx, ly, h, w=0.28, mat="post"):
        self.B(lx - w / T / 2, ly - w / T / 2, lx + w / T / 2, ly + w / T / 2, 0, h, mat)

    def lantern(self, x, y, z):
        self.Bm(x, y, z, 0.26, 0.26, 0.34, "lantern")
        self.Bm(x, y, z + 0.22, 0.34, 0.34, 0.08, "iron")
        self.Bm(x, y, z - 0.2, 0.3, 0.3, 0.06, "iron")

    def steps(self, lx0, lx1, ly_face, n=2, depth=0.35, rise=0.17, mat="step"):
        for i in range(n):
            ly = ly_face + i * depth / T
            self.B(lx0 - i * 0.05, ly, lx1 + i * 0.05, ly + depth / T, 0, rise * (n - i), mat)


# ----------------------------------------------------------------- icons for signs
def icon_ox(k, x, y, z):
    k.Bm(x, y, z, 0.42, 0.06, 0.34, "roof_brown")
    for sx in (-1, 1):
        k.box((x + sx * 0.28, y, z + 0.16), (0.24, 0.06, 0.07), "trim", rot=(0, sx * 30, 0))
    k.Bm(x, y - 0.02, z - 0.12, 0.2, 0.06, 0.1, "trim")


def icon_coin(k, x, y, z):
    k.cyl((x, y, z), 0.24, 0.24, 0.06, "gold", segs=10, rot=(90, 0, 0), jitter=False)


def icon_paw(k, x, y, z):
    k.cyl((x, y, z - 0.07), 0.14, 0.14, 0.05, "door_d", segs=8, rot=(90, 0, 0), jitter=False)
    for dx, dz in ((-0.17, 0.08), (-0.06, 0.16), (0.06, 0.16), (0.17, 0.08)):
        k.cyl((x + dx, y, z + dz), 0.05, 0.05, 0.05, "door_d", segs=6, rot=(90, 0, 0), jitter=False)


def icon_fish(k, x, y, z):
    k.box((x - 0.05, y, z), (0.5, 0.06, 0.18), "fish", taper=1.0)
    k.box((x + 0.27, y, z), (0.12, 0.06, 0.26), "fish_d")


def icon_sack(k, x, y, z):
    k.box((x, y, z - 0.03), (0.3, 0.06, 0.3), "trim", taper=0.7)
    k.Bm(x, y - 0.02, z + 0.15, 0.08, 0.06, 0.06, "rope")


def icon_anchor(k, x, y, z):
    k.Bm(x, y, z + 0.02, 0.06, 0.06, 0.4, "iron")
    k.Bm(x, y, z + 0.15, 0.24, 0.06, 0.05, "iron")
    k.Bm(x, y, z - 0.17, 0.34, 0.06, 0.05, "iron")
    for sx in (-1, 1):
        k.Bm(x + sx * 0.17, y, z - 0.1, 0.05, 0.06, 0.14, "iron")


def icon_shield(k, x, y, z):
    k.box((x, y, z), (0.36, 0.06, 0.42), "red", taper=1.0)
    k.Bm(x, y - 0.02, z, 0.06, 0.05, 0.36, "gold")
    k.Bm(x, y - 0.02, z + 0.05, 0.3, 0.05, 0.06, "gold")
