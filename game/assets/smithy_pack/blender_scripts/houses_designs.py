"""houses_designs.py - one build function per building. Each returns a meta dict.
All coordinates are local tiles (see houses_geo.py). FL = south face of the enclosed walls
(= D - 1.3): the last ~1.3 tiles are the porch/stoop where props stand (WALL tiles on the server,
except the door column which is PATH)."""
import math
from houses_geo import T, icon_ox, icon_coin, icon_paw, icon_fish, icon_sack, icon_anchor, icon_shield

SPECS = {   # key: (building_id, name, x0, y0, W, D, door_x_local, floor_local (x0,y0,x1,y1) inclusive tiles)
    "elders_hall":        ("cottage_nw", "Elder's Hall", 2, 2, 16, 10, 5, (1, 1, 14, 7)),
    "general_store":      ("cottage_ne", "General Store", 23, 2, 11, 10, 4, (1, 1, 9, 7)),
    "resting_ox":         ("cottage_sw", "The Resting Ox", 2, 21, 14, 12, 5, (1, 1, 12, 9)),
    "farmhouse":          ("cottage_se", "Farmhouse", 23, 23, 13, 10, 4, (1, 1, 7, 7)),
    "village_bank":       ("bank", "Village Bank", 33, 13, 11, 8, 5, (1, 1, 9, 5)),
    "pet_emporium":       ("pet_emporium", "Pet Emporium", 50, 22, 14, 11, 5, (1, 1, 9, 8)),
    "stonehaven_cottage": ("city_house_nw", "Stonehaven Cottage", 81, 42, 11, 11, 5, (1, 1, 9, 8)),
    "stonehaven_house":   ("city_house_sw", "Stonehaven House", 80, 58, 13, 9, 6, (1, 1, 11, 6)),
    "city_barracks":      ("city_barracks", "City Barracks", 109, 57, 11, 12, 5, (1, 1, 9, 9)),
    "kais_catch":         ("harbour_fishmonger", "Kai's Catch", 130, 20, 14, 9, 8, (5, 1, 12, 6)),
    "harbour_tackle":     ("harbour_tackle", "Harbourreach Tackle", 134, 6, 13, 9, 4, (1, 1, 7, 6)),
}
E = 0.15   # wall inset from the footprint edge (tiles)


def porch(k, x0, x1, FL, D, mat="cobble", z=0.12):
    k.use("ground")
    k.B(x0, FL - 0.1, x1, D - 0.05, 0, z, mat)
    k.use("body")


# ------------------------------------------------------------------ village
def elders_hall(k, W, D, dx):
    FL = D - 1.3
    cx = dx + 0.5
    porch(k, E, W - E, FL, D, "plank_w", 0.3)
    k.use("ground"); k.steps(cx - 2.2, cx + 2.2, D - 0.75, n=2, depth=0.5); k.use("body")
    k.plinth(E, E, W - E, FL, 0.45, "plinth")
    k.walls(E, E, W - E, FL, 0.45, 4.2, "wood")
    for i in range(9):                                   # vertical log posts on the facade
        x = (E + (W - 2 * E) * i / 8) * T
        k.Bm(x, -FL * T - 0.08, 2.3, 0.3, 0.16, 3.8, "beam")
    k.roof_ew(E, E, W - E, FL, 4.2, 6.2, "roof_brown", o=0.45, gable="wood")
    # carved ridge finials (dragon heads) + ridge crests
    ym = -(E + FL) / 2 * T
    for x, s in ((E - 0.45, -1), (W - E + 0.45, 1)):
        k.box((x * T + s * 0.3, ym, 4.2 + 6.2 + 0.4), (1.1, 0.25, 0.35), "beam", rot=(0, -s * 35, 0))
        k.box((x * T + s * 0.75, ym, 4.2 + 6.2 + 0.85), (0.5, 0.22, 0.3), "gold", rot=(0, s * 20, 0))
    for i in range(1, 8):
        k.Bm((E + (W - 2 * E) * i / 8) * T, ym, 10.6, 0.16, 0.2, 0.5, "beam")
    # cross gable over the door, projecting forward as the porch roof
    k.roof_ns(cx - 2.6, FL - 2.5, cx + 2.6, D - 0.35, 3.6, 4.2, "roof_brown", o=0.25, gable="wood", barge="gold")
    for sx in (-1, 1):                                   # carved pillars
        k.column(cx + sx * 2.3, D - 0.6, 3.6, r=0.2, mat="beam")
    k.Bm(cx * T, -(D - 0.6) * T, 3.62, 4.9 * T, 0.3, 0.25, "wood_d")
    # side porch roof (lean-to) with more pillars
    for a, b in ((E - 0.3, cx - 2.6), (cx + 2.6, W - E + 0.3)):
        k.slab([(a * T, -(D - 0.3) * T, 3.0), (b * T, -(D - 0.3) * T, 3.0), (b * T, -FL * T, 3.9), (a * T, -FL * T, 3.9)],
               0.2, "roof_brown")
        n = max(1, int((b - a) / 2.4))
        for i in range(n + 1):
            k.column(a + 0.3 + (b - a - 0.6) * i / n, D - 0.55, 3.0, r=0.16, mat="beam")
    # banners between pillars
    for i, x in enumerate((1.6, 3.6, 9.0, 11.2, 13.4)):
        m = "red" if i % 2 == 0 else "banner_g"
        k.Bm(x * T, -FL * T - 0.12, 2.6, 0.9, 0.05, 1.6, m)
        k.box((x * T, -FL * T - 0.12, 1.6), (0.9, 0.05, 0.4), m, taper=0.01)
        k.Bm(x * T, -FL * T - 0.14, 3.45, 1.1, 0.08, 0.08, "gold")
    k.door(cx, FL, w=1.8, h=2.9, arch="beam", wood="door", z0=0.45)
    for x in (2.6, 12.0, 14.4):
        k.window(x, FL, 2.5, w=0.7, h=0.9, lit=True, shutters="wood_d")
    k.chimney(12.5, 3.0, 8.0, 11.6)
    return {"door_face_ly": FL}


def general_store(k, W, D, dx):
    """v2b: tall two-storey front block with a stepped false front + signboard; low rear block."""
    FL = D - 1.3
    cx = dx + 0.5
    MW = 9.0
    FB = FL - 4.2                                   # front block depth (tiles)
    porch(k, E, W - E, FL, D, "plank", 0.2)
    k.plinth(E, E, W - E, FL, 0.35)
    # rear block (1 storey, low side-gabled roof)
    k.walls(E, E, MW, FB + 0.2, 0.35, 3.4, "plank")
    k.roof_ew(E, E, MW, FB + 0.2, 3.4, 1.5, "roof_brown", o=0.25, gable="plank")
    k.chimney(1.6, 1.4, 3.6, 6.2)
    # front block: plank ground floor, jettied timber-framed upper floor, low roof hidden by the false front
    k.walls(E, FB, MW, FL, 0.35, 3.5, "plank_l")
    for z in (1.0, 1.7, 2.4, 3.1):
        k.Bm((E + MW) / 2 * T, -FL * T - 0.03, z, (MW - E) * T, 0.05, 0.05, "wood_d", jitter=False)
    k.walls(E - 0.05, FB, MW + 0.05, FL + 0.2, 3.5, 6.6, "plaster")
    k.Bm((E + MW) / 2 * T, -(FL + 0.2) * T, 3.5, (MW - E + 0.2) * T, 0.35, 0.3, "beam")
    k.beams_front(E, MW, FL + 0.2, 3.5, 6.6, n=6)
    k.roof_ew(E, FB, MW, FL + 0.2, 6.6, 1.4, "roof_tile", o=0.2, gable="plaster")
    # stepped false front (parapet) with the shop signboard
    y = -(FL + 0.2) * T - 0.06
    k.Bm((E + MW) / 2 * T, y, 7.3, (MW - E) * T, 0.25, 1.4, "plank_l")
    k.Bm((E + MW) / 2 * T, y, 8.4, (MW - E) * T * 0.62, 0.25, 0.8, "plank_l")
    k.Bm((E + MW) / 2 * T, y, 9.05, (MW - E) * T * 0.3, 0.25, 0.5, "plank_l")
    for zz, wf in ((8.0, 1.0), (8.8, 0.62), (9.3, 0.3)):
        k.Bm((E + MW) / 2 * T, y - 0.02, zz, (MW - E) * T * wf + 0.15, 0.3, 0.14, "beam")
    k.Bm((E + MW) / 2 * T, y - 0.16, 7.25, (MW - E) * T * 0.8, 0.08, 0.95, "red")
    k.Bm((E + MW) / 2 * T, y - 0.2, 7.25, (MW - E) * T * 0.8 + 0.12, 0.05, 1.07, "gold")
    k.Bm((E + MW) / 2 * T, y - 0.22, 7.25, (MW - E) * T * 0.8 - 0.1, 0.05, 0.8, "red")
    for i, m in enumerate(("cream", "gold", "cream", "gold", "cream", "gold", "cream")):     # lettering blocks
        k.Bm(((E + MW) / 2 - 2.6 + i * 0.87) * T, y - 0.27, 7.25, 0.42, 0.04, 0.42, m, jitter=False)
    icon_sack(k, (E + MW) / 2 * T, y - 0.1, 8.45)
    # east storeroom (lower lean-to, full depth)
    k.walls(MW, E, W - E, FL, 0.35, 3.2, "plank")
    k.slab([(MW * T, -(FL + 0.3) * T, 3.3), ((W - E + 0.3) * T, -(FL + 0.3) * T, 3.3),
            ((W - E + 0.3) * T, -(E - 0.2) * T, 4.6), (MW * T, -(E - 0.2) * T, 4.6)], 0.2, "roof_brown")
    k.window(10.0, FL, 2.0, w=0.8, h=0.8, shutters="shutter")
    # shopfront: big display window + striped awning
    k.window(7.0, FL, 1.9, w=2.8, h=1.6, lit=True, frame="beam")
    for i, m in enumerate(("red", "blue", "yellow", "green", "gold", "trim")):
        k.Bm((5.9 + i * 0.44) * T, -FL * T - 0.2, 1.25, 0.4, 0.3, 0.3 + (i % 2) * 0.2, m)
    k.awning(5.2, 8.8, FL, 3.3, depth=1.5, drop=0.7, mats=("red", "cream"))
    k.door(cx, FL, w=1.5, h=2.5, arch="brick_arch", round_top=False, double=True)
    k.sign(2.4, FL, 3.3, w=1.1, h=0.75, icon=icon_sack)
    for x in (1.6, 3.4, 6.0, 8.0):
        k.window(x, FL + 0.2, 5.0, w=0.8, h=1.0, lit=(x == 3.4), box=("flower_r", "leaf", "flower_y"))
    k.crate(0.8, D - 0.7); k.crate(1.5, D - 0.65, 0.6); k.crate(0.95, D - 0.7, 0.55, z=0.75)
    k.sack(2.4, D - 0.55); k.sack(2.9, D - 0.7, mat="hay")
    k.barrel(6.2, D - 0.55); k.sack(7.6, D - 0.5); k.crate(8.3, D - 0.6, 0.6)
    k.crate(9.8, D - 0.65); k.barrel(10.5, D - 0.6)
    return {"door_face_ly": FL}


def resting_ox(k, W, D, dx):
    FL = D - 1.3
    cx = dx + 0.5
    MW = 10.0
    porch(k, E, W - E, FL, D, "cobble", 0.12)
    k.plinth(E, E, W - E, FL, 0.35)
    k.walls(E, E, MW, FL, 0.35, 3.4, "sstone")
    k.walls(E - 0.05, E, MW + 0.05, FL + 0.25, 3.4, 6.8, "plaster")
    k.Bm((E + MW) / 2 * T, -(FL + 0.25) * T, 3.42, (MW - E + 0.2) * T, 0.4, 0.3, "beam")
    k.beams_front(E, MW, FL + 0.25, 3.4, 6.8, n=8)
    k.roof_ew(E, E, MW, FL + 0.25, 6.8, 4.8, "roof_tile", o=0.4, gable="plaster")
    for x in (2.6, 7.4):                                 # dormers
        k.walls(x - 0.9, FL - 2.6, x + 0.9, FL - 1.5, 7.0, 8.8, "plaster")
        k.roof_ns(x - 0.9, FL - 3.5, x + 0.9, FL - 1.5, 8.8, 1.3, "roof_tile", o=0.2, gable="plaster", barge=None)
        k.window(x, FL - 1.5, 7.9, w=0.7, h=0.8, lit=True)
    k.chimney(1.2, 3.0, 8.0, 12.2); k.chimney(9.0, 3.0, 8.0, 12.0)
    for x in (1.6, 3.7, 7.6):
        k.window(x, FL, 1.9, w=1.0, h=1.1, lit=True, shutters="wood_red")
    for x in (1.4, 3.4, 5.5, 7.6, 9.2):
        k.window(x, FL + 0.25, 5.1, w=0.8, h=1.0, lit=(x in (3.4, 7.6)), box=("flower_r", "leaf") if x in (1.4, 9.2) else None)
    k.door(cx, FL, w=1.7, h=2.6, arch="brick_arch")
    k.sign(3.0, FL, 3.2, w=1.2, h=0.9, icon=icon_ox)
    k.lantern(cx * T - 1.3, -FL * T - 0.25, 2.6); k.lantern(cx * T + 1.3, -FL * T - 0.25, 2.6)
    # stable wing with an arch
    k.walls(MW, E, W - E, FL, 0.2, 3.8, "plank")
    k.roof_ew(MW, E, W - E, FL, 3.8, 2.4, "roof_brown", o=0.3, gable="plank")
    sx = 11.9
    k.Bm(sx * T, -FL * T + 0.05, 1.5, 2.6, 0.2, 2.6, "interior_deep")
    k.door(sx, FL, w=2.6, h=3.1, arch="sstone_l", wood="interior_deep", z0=0.2, double=False)
    k.bale(sx, FL - 0.3, 0.0)
    k.Bm(sx * T, -FL * T - 0.08, 3.6, 1.0, 0.1, 0.4, "hay")
    # benches, table, barrels
    k.bench(7.4, D - 0.45, 1.4); k.table(8.5, D - 0.7, 1.0); k.bench(9.6, D - 0.45, 1.4)
    k.barrel(0.7, D - 0.6); k.barrel(1.45, D - 0.65); k.barrel(1.05, D - 0.62, z=0.95)
    k.barrel(12.9, D - 0.6); k.crate(13.4, D - 0.55, 0.55)
    return {"door_face_ly": FL}


def farmhouse(k, W, D, dx):
    FL = D - 1.3
    cx = dx + 0.5
    MW = 9.0
    porch(k, E, MW, FL, D, "cobble", 0.1)
    k.use("ground")
    k.B(MW + 0.1, 5.5, W - E, D - 0.1, 0, 0.12, "soil")                  # veg patch soil
    k.use("body")
    k.plinth(E, E, MW, FL, 0.35, "sstone_d")
    k.walls(E, E, MW, FL, 0.35, 3.2, "white")
    k.beams_front(E, MW, FL, 0.35, 3.2, n=4, diag=False)
    k.roof_ew(E, E, MW, FL, 3.2, 4.6, "thatch", o=0.6, gable="white", thick=0.55, hip=1.6, courses=False)
    k.Bm((MW + E) / 2 * T, -(FL + 0.6) * T, 3.05, (MW - E + 1.2) * T, 0.5, 0.35, "thatch_d")
    k.Bm((MW + E) / 2 * T, -(E + FL) / 2 * T, 7.85, (MW - E - 3.0) * T, 0.9, 0.45, "thatch_d")
    k.chimney(1.8, 3.5, 5.5, 8.6)
    # eyebrow dormer over the door
    k.walls(cx - 0.8, FL - 1.2, cx + 0.8, FL - 0.2, 3.0, 4.4, "white")
    k.roof_ew(cx - 0.8, FL - 1.2, cx + 0.8, FL - 0.2, 4.4, 1.1, "thatch", o=0.35, gable="white", thick=0.4, hip=0.5, courses=False)
    k.window(cx, FL - 0.2, 3.7, w=0.6, h=0.6, lit=True)
    k.door(cx, FL, w=1.3, h=2.3, arch=None, round_top=False, double=False, z0=0.35)
    for sx in (-1, 1):
        k.Bm(cx * T + sx * 0.75, -FL * T - 0.08, 1.5, 0.16, 0.14, 2.4, "beam")
    k.Bm(cx * T, -FL * T - 0.08, 2.75, 1.7, 0.14, 0.16, "beam")
    for x in (1.8, 7.2):
        k.window(x, FL, 1.8, w=0.9, h=0.9, shutters="shutter", box=("flower_y", "leaf", "flower_r"))
    # barn lean-to
    k.walls(MW, E, W - E, 5.2, 0.0, 3.4, "wood_red")
    k.slab([(MW * T, -(5.2 + 0.35) * T, 3.4), ((W - E + 0.3) * T, -(5.2 + 0.35) * T, 3.4),
            ((W - E + 0.3) * T, -(E - 0.2) * T, 5.4), (MW * T, -(E - 0.2) * T, 5.4)], 0.2, "roof_brown")
    bx = 11.0
    k.Bm(bx * T, -5.2 * T - 0.05, 1.3, 2.4, 0.1, 2.6, "wood")
    k._beam((bx * T - 1.2, -5.2 * T - 0.12, 0.1), (bx * T + 1.2, -5.2 * T - 0.12, 2.5), 0.16, "trim")
    k._beam((bx * T - 1.2, -5.2 * T - 0.12, 2.5), (bx * T + 1.2, -5.2 * T - 0.12, 0.1), 0.16, "trim")
    k.Bm(bx * T, -5.2 * T - 0.08, 3.0, 0.8, 0.1, 0.5, "hay")
    # fenced veg patch with cabbages + scarecrow
    k.fence([(MW + 0.2, 5.5), (MW + 0.2, D - 0.15), (W - 0.2, D - 0.15), (W - 0.2, 5.5)])
    for r in range(3):
        for c in range(4):
            x, y = (MW + 0.9 + c * 0.9) * T, -(6.2 + r * 1.0) * T
            k.cyl((x, y, 0.1), 0.25, 0.3, 0.35, "leaf" if (r + c) % 3 else "green", segs=6)
    k.post(12.2, 7.2, 2.0); k.B(11.8, 7.15, 12.6, 7.25, 1.5, 1.6, "post")
    k.box((12.2 * T, -7.2 * T, 1.6), (0.5, 0.3, 0.6), "red"); k.cyl((12.2 * T, -7.2 * T, 1.9), 0.18, 0.18, 0.3, "hay", segs=6)
    k.cone((12.2 * T, -7.2 * T, 2.2), 0.35, 0.3, "thatch_d", segs=6)
    # hay bales, trough, cart wheel
    k.bale(0.9, D - 0.6); k.bale(1.9, D - 0.6); k.bale(1.4, D - 0.6, z=0.7)
    x, y = 6.9 * T, -(D - 0.55) * T
    k.Bm(x, y, 0.3, 1.5, 0.6, 0.6, "wood_d"); k.Bm(x, y, 0.58, 1.3, 0.42, 0.06, "water", jitter=False)
    k.cyl((8.3 * T, -(D - 0.3) * T, 0.6), 0.6, 0.6, 0.12, "wood_d", segs=10, rot=(90, 0, 0))
    return {"door_face_ly": FL}


def village_bank(k, W, D, dx):
    FL = D - 1.5
    cx = dx + 0.5
    porch(k, E, W - E, FL, D, "marble", 0.15)
    k.use("ground"); k.steps(1.2, W - 1.2, D - 0.9, n=3, depth=0.3); k.use("body")
    k.plinth(E, E, W - E, FL, 0.5, "sstone_d")
    k.walls(E, E, W - E, FL, 0.5, 5.0, "sstone")
    k.B(E - 0.03, FL - 0.2, W - E + 0.03, FL + 0.03, 0.5, 1.4, "sstone_d")
    for z in (2.3, 3.4):
        k.Bm(W / 2 * T, -FL * T - 0.03, z, (W - 2 * E) * T, 0.06, 0.06, "sstone_d", jitter=False)
    k.B(E - 0.1, E - 0.1, W - E + 0.1, FL + 0.1, 5.0, 5.45, "marble")
    k.roof_ew(E, E, W - E, FL, 5.45, 2.6, "roof_slate", o=0.2, hip=2.2)
    # portico: 4 columns, entablature, pediment with gold coin
    PY = FL + 1.05
    for x in (1.5, 3.3, 7.7, 9.5):
        k.column(x, PY, 4.3, r=0.28)
    k.B(1.0, FL, W - 1.0, PY + 0.3, 4.3, 4.85, "marble")
    k.Bm(W / 2 * T, -(PY + 0.3) * T - 0.02, 4.55, (W - 2.0) * T, 0.05, 0.12, "gold", jitter=False)
    ys = -(PY + 0.3) * T - 0.01
    k.tri((1.0 * T, ys, 4.85), ((W - 1.0) * T, ys, 4.85), (W / 2 * T, ys, 6.3), "marble")
    k.slab([(0.9 * T, -(PY + 0.35) * T, 4.85), (W / 2 * T, -(PY + 0.35) * T, 6.35), (W / 2 * T, -FL * T, 6.35),
            (0.9 * T, -FL * T, 4.85)], 0.15, "roof_slate")
    k.slab([(W / 2 * T, -(PY + 0.35) * T, 6.35), ((W - 0.9) * T, -(PY + 0.35) * T, 4.85), ((W - 0.9) * T, -FL * T, 4.85),
            (W / 2 * T, -FL * T, 6.35)], 0.15, "roof_slate")
    k.cyl((W / 2 * T, ys - 0.02, 5.4), 0.45, 0.45, 0.1, "gold", segs=12, rot=(90, 0, 0), jitter=False)
    k.cyl((W / 2 * T, ys - 0.1, 5.4), 0.3, 0.3, 0.06, "coin", segs=12, rot=(90, 0, 0), jitter=False)
    k.door(cx, FL, w=1.8, h=3.0, arch="marble", wood="door_d", band="iron", z0=0.5)
    for zz in (1.0, 1.7, 2.3):
        k.Bm(cx * T, -FL * T - 0.12, 0.5 + zz, 1.75, 0.05, 0.1, "iron")
    for x in (1.3, 3.2, 7.8, 9.7):
        k.window(x, FL, 2.8, w=0.8, h=1.3, bars=True, frame="sstone_d", sill="marble")
    k.lantern(cx * T - 1.6, -FL * T - 0.2, 2.9); k.lantern(cx * T + 1.6, -FL * T - 0.2, 2.9)
    k.chimney(2.0, 2.0, 6.0, 8.2)
    return {"door_face_ly": FL}


def pet_emporium(k, W, D, dx):
    """v2b: tall colourful front block with a scalloped false front + big paw sign; low rear block."""
    FL = D - 1.3
    cx = dx + 0.5
    MW = 10.85
    FB = FL - 4.4
    porch(k, E, MW, FL, D, "plank", 0.15)
    k.use("ground"); k.B(MW + 0.2, 2.8, W - E, D - 0.1, 0, 0.1, "grass"); k.use("body")
    k.plinth(E, E, MW, FL, 0.35, "plinth")
    k.walls(E, E, MW, FB + 0.2, 0.35, 3.2, "teal")                     # rear block
    k.roof_ew(E, E, MW, FB + 0.2, 3.2, 1.4, "roof_purple", o=0.25, gable="teal", hip=1.2)
    k.chimney(9.0, 1.4, 3.4, 6.0, "brick")
    k.walls(E, FB, MW, FL, 0.35, 6.2, "teal")                          # tall front block
    for i in range(8):
        k.Bm((E + (MW - E) * i / 7) * T, -FL * T - 0.05, 3.25, 0.16, 0.1, 5.8, "yellow")
    k.Bm((E + MW) / 2 * T, -FL * T - 0.05, 3.55, (MW - E) * T, 0.12, 0.2, "yellow")
    k.roof_ew(E, FB, MW, FL, 6.2, 1.3, "roof_purple", o=0.2, gable="teal")
    # scalloped pink false front with a big paw medallion
    y = -FL * T - 0.08
    k.Bm((E + MW) / 2 * T, y, 7.0, (MW - E) * T, 0.25, 1.6, "pink")
    for i in range(7):
        xx = (E + (MW - E) * (i + 0.5) / 7) * T
        hh = 0.5 + 0.9 * (1 - abs(i - 3) / 3.5)
        k.Bm(xx, y, 7.8 + hh / 2, (MW - E) * T / 7 - 0.05, 0.25, hh, "pink")
        k.cyl((xx, y, 7.8 + hh), 0.28, 0.28, 0.2, "yellow", segs=8, rot=(90, 0, 0), jitter=False)
    k.Bm((E + MW) / 2 * T, y - 0.05, 6.25, (MW - E) * T + 0.1, 0.3, 0.18, "yellow")
    mx, mz = (E + MW) / 2 * T, 8.0
    k.cyl((mx, y - 0.14, mz), 1.05, 1.05, 0.12, "yellow", segs=14, rot=(90, 0, 0), jitter=False)
    k.cyl((mx, y - 0.2, mz), 0.9, 0.9, 0.08, "cream", segs=14, rot=(90, 0, 0), jitter=False)
    k.cyl((mx, y - 0.26, mz - 0.18), 0.36, 0.36, 0.06, "door_d", segs=10, rot=(90, 0, 0), jitter=False)
    for ddx, ddz in ((-0.44, 0.2), (-0.16, 0.44), (0.16, 0.44), (0.44, 0.2)):
        k.cyl((mx + ddx, y - 0.26, mz + ddz), 0.13, 0.13, 0.06, "door_d", segs=8, rot=(90, 0, 0), jitter=False)
    for x in (2.2, 8.6):
        k.window(x, FL, 5.0, w=1.0, h=1.0, lit=True, frame="frame_w", box=("flower_r", "flower_y", "pink"))
        k.cyl((x * T, -FL * T - 0.1, 5.65), 0.62, 0.62, 0.08, "pink", segs=10, rot=(90, 0, 0), jitter=False)
    k.door(cx, FL, w=1.5, h=2.5, arch="yellow", wood="red", z0=0.35)
    for x in (2.3, 8.4):
        k.window(x, FL, 1.9, w=1.6, h=1.3, lit=True, frame="frame_w", box=("flower_r", "flower_y", "pink", "leaf"))
    k.awning(7.1, 9.8, FL, 3.25, depth=1.2, drop=0.6, mats=("yellow", "pink"))
    k.awning(0.9, 3.7, FL, 3.25, depth=1.0, drop=0.5, mats=("teal", "cream"))
    k.sign(3.9, FL, 3.3, w=0.9, h=0.9, board="cream", icon=icon_paw)
    bx, by = 7.0 * T, -(D - 0.6) * T
    k.cyl((bx, by, 0), 0.25, 0.25, 0.08, "iron", segs=6); k.cyl((bx, by, 0.08), 0.04, 0.04, 1.3, "iron", segs=4)
    for i in range(8):
        a = 2 * math.pi * i / 8
        k.cyl((bx + 0.28 * math.cos(a), by + 0.28 * math.sin(a), 1.35), 0.02, 0.02, 0.7, "gold", segs=3, jitter=False)
    k.cyl((bx, by, 1.33), 0.3, 0.3, 0.05, "gold", segs=8); k.cone((bx, by, 2.02), 0.32, 0.3, "gold", segs=8)
    k.box((bx, by, 1.62), (0.2, 0.14, 0.18), "bird"); k.box((bx + 0.12, by, 1.66), (0.08, 0.06, 0.05), "fire")
    k.fence([(MW + 0.25, 3.0), (MW + 0.25, D - 0.15), (W - 0.2, D - 0.15), (W - 0.2, 3.0), (MW + 0.25, 3.0)])
    kx, ky = 12.4, 5.0
    k.walls(kx - 0.7, ky - 0.6, kx + 0.7, ky + 0.6, 0, 1.0, "plank_w")
    k.roof_ns(kx - 0.7, ky - 0.6, kx + 0.7, ky + 0.6, 1.0, 0.8, "red", o=0.12, gable="plank_w", barge=None)
    k.Bm(kx * T, -(ky + 0.6) * T - 0.02, 0.4, 0.55, 0.05, 0.65, "interior_deep")
    dx_, dy_ = 12.2 * T, -8.4 * T
    k.Bm(dx_, dy_, 0.45, 0.8, 0.35, 0.35, "dog"); k.Bm(dx_ + 0.48, dy_, 0.7, 0.35, 0.3, 0.3, "dog")
    k.Bm(dx_ + 0.68, dy_, 0.66, 0.16, 0.18, 0.14, "door_d")
    for ox in (-0.3, 0.3):
        k.Bm(dx_ + ox, dy_, 0.14, 0.1, 0.25, 0.28, "dog")
    k.box((dx_ - 0.45, dy_, 0.65), (0.3, 0.08, 0.08), "dog", rot=(0, -40, 0))
    k.cyl((11.6 * T, -9.6 * T, 0.1), 0.25, 0.22, 0.12, "blue", segs=8)
    k.crate(0.8, D - 0.6, 0.6); k.barrel(1.6, D - 0.55, r=0.3, h=0.8)
    return {"door_face_ly": FL}


def stonehaven_cottage(k, W, D, dx):
    FL = D - 1.3
    cx = dx + 0.5
    porch(k, E, W - E, FL, D, "cobble", 0.1)
    k.plinth(E, E, W - E, FL, 0.35, "sstone_d")
    k.walls(E, E, W - E, FL, 0.35, 3.5, "sstone")
    for x in (E, W - E):                                  # corner quoins
        for i in range(5):
            k.Bm(x * T, -FL * T - 0.03, 0.6 + i * 0.6, 0.55 if i % 2 else 0.35, 0.1, 0.3, "sstone_l")
    k.roof_ew(E, E, W - E, FL, 3.5, 5.0, "roof_slate", o=0.4, gable="sstone", hip=2.2)
    k.chimney(9.2, 4.0, 5.0, 8.6, "sstone_d", w=0.7)
    k.walls(cx - 1.0, FL - 1.6, cx + 1.0, FL - 0.4, 3.2, 5.0, "sstone")
    k.roof_ns(cx - 1.0, FL - 3.2, cx + 1.0, FL - 0.4, 5.0, 1.4, "roof_slate", o=0.25, gable="sstone", barge=None)
    k.window(cx, FL - 0.4, 4.1, w=0.7, h=0.8, lit=True, frame="frame_w")
    k.chimney(1.6, 3.2, 5.0, 9.4, "sstone_d", w=0.9)
    k.door(cx, FL, w=1.4, h=2.4, arch="sstone_l", wood="door", z0=0.35)
    for x in (2.6, 8.4):
        k.window(x, FL, 1.9, w=1.0, h=1.1, frame="frame_w", box=("flower_r", "leaf", "flower_r"))
    # planters + bench on the paving
    for x in (1.0, 10.0):
        k.B(x - 0.35, D - 0.95, x + 0.35, D - 0.35, 0, 0.55, "sstone_d")
        k.cone((x * T, -(D - 0.65) * T, 0.55), 0.45, 1.1, "leaf", segs=6)
    k.bench(8.0, D - 0.5, 1.4)
    k.lantern(cx * T + 1.2, -FL * T - 0.2, 2.5)
    return {"door_face_ly": FL}


def stonehaven_house(k, W, D, dx):
    FL = D - 1.3
    cx = dx + 0.5
    porch(k, E, W - E, FL, D, "cobble", 0.1)
    k.use("ground"); k.steps(cx - 1.0, cx + 1.0, FL, n=2, depth=0.35); k.use("body")
    k.plinth(E, E, W - E, FL, 0.35, "sstone_d")
    k.walls(E, E, W - E, FL, 0.35, 6.6, "sstone")
    k.Bm(W / 2 * T, -FL * T - 0.04, 3.5, (W - 2 * E) * T, 0.1, 0.18, "sstone_l")
    k.roof_ew(E, E, W - E, FL, 6.6, 3.8, "roof_slate", o=0.35, gable="sstone")
    for a, b in ((0.8, 5.2), (7.8, 12.2)):                # twin front gables
        k.walls(a, FL - 2.0, b, FL + 0.05, 6.4, 7.4, "sstone")
        k.roof_ns(a, FL - 3.5, b, FL + 0.05, 7.4, 2.4, "roof_slate", o=0.3, gable="sstone_l", barge="sstone_d")
        k.window((a + b) / 2, FL + 0.05, 8.0, w=0.6, h=0.7, frame="frame_w")
    # bay window (ground floor, left of the door)
    bx0, bx1, by = 1.4, 4.6, FL + 0.8
    k.B(bx0, FL, bx1, by, 0.35, 1.1, "sstone_l")
    k.B(bx0 + 0.05, FL, bx1 - 0.05, by - 0.05, 1.1, 2.8, "glass")
    for i in range(6):
        k.Bm((bx0 + (bx1 - bx0) * i / 5) * T, -by * T - 0.02, 1.95, 0.12, 0.1, 1.7, "frame_w")
    k.B(bx0 - 0.1, FL, bx1 + 0.1, by + 0.1, 2.8, 3.0, "sstone_l")
    k.slab([((bx0 - 0.1) * T, -(by + 0.15) * T, 3.0), ((bx1 + 0.1) * T, -(by + 0.15) * T, 3.0),
            ((bx1 + 0.1) * T, -FL * T, 3.6), ((bx0 - 0.1) * T, -FL * T, 3.6)], 0.15, "roof_slate")
    k.door(cx, FL, w=1.4, h=2.5, arch="sstone_l", wood="blue", z0=0.35)
    k.lantern(cx * T - 1.1, -FL * T - 0.2, 2.6)
    k.window(9.6, FL, 1.9, w=1.0, h=1.2, frame="frame_w", shutters="blue")
    k.window(11.6, FL, 1.9, w=0.8, h=1.2, frame="frame_w", shutters="blue")
    for x in (1.8, 4.2, cx, 9.0, 11.3):
        k.window(x, FL, 5.0, w=0.8, h=1.2, lit=(x == cx), frame="frame_w", shutters="blue")
    k.chimney(0.9, 2.5, 8.0, 11.4, "sstone_d", w=0.8); k.chimney(12.1, 2.5, 8.0, 11.2, "sstone_d", w=0.8)
    k.B(9.0, D - 0.9, 12.3, D - 0.4, 0, 0.5, "sstone_d")
    for i in range(5):
        k.Bm((9.3 + i * 0.7) * T, -(D - 0.65) * T, 0.62, 0.35, 0.35, 0.3, ("flower_r", "leaf", "flower_y")[i % 3])
    return {"door_face_ly": FL}


def city_barracks(k, W, D, dx):
    """v2b: terraced flat roofs with crenellated parapets - tall front keep-block, lower rear block,
    corner watch turret; balcony, shield, banners, arrow slits, weapon rack, dummy."""
    FL = D - 1.3
    cx = dx + 0.5
    FB = FL - 4.6
    porch(k, E, W - E, FL, D, "cobble", 0.1)
    k.plinth(E, E, W - E, FL, 0.35, "sstone_d")

    def crenels(x0, x1, ly, z, n):
        for i in range(n):
            a = x0 + (x1 - x0) * (i + 0.15) / n
            k.B(a, ly - 0.22, a + (x1 - x0) * 0.55 / n, ly + 0.02, z, z + 0.75, "sstone_l")
        k.B(x0, ly - 0.22, x1, ly + 0.02, z - 0.25, z, "sstone_l")
    # rear block, lower terrace
    k.walls(E, E, W - E, FB + 0.1, 0.35, 4.6, "sstone_d")
    k.B(E, E, W - E, FB + 0.1, 4.6, 4.75, "cobble")
    crenels(E, W - E, E + 0.22, 4.9, 9)
    k.B(E, E, E + 0.2, FB, 4.6, 5.3, "sstone_l"); k.B(W - E - 0.2, E, W - E, FB, 4.6, 5.3, "sstone_l")
    k.chimney(2.2, 1.6, 4.7, 6.4, "sstone_d")
    k.Bm(6.0 * T, -2.0 * T, 5.0, 0.9, 0.9, 0.5, "plank")         # crates on the terrace
    k.Bm(6.7 * T, -2.1 * T, 4.95, 0.7, 0.7, 0.4, "plank")
    # tall front block with flat roof + crenellated parapet
    k.walls(E, FB, W - E, FL, 0.35, 7.0, "sstone")
    for z in (3.6,):
        k.Bm(W / 2 * T, -FL * T - 0.04, z, (W - 2 * E) * T, 0.1, 0.18, "sstone_l")
    k.B(E, FB, W - E, FL, 7.0, 7.12, "cobble")
    crenels(E - 0.05, W - E + 0.05, FL + 0.05, 7.35, 10)
    k.B(E, FB, E + 0.2, FL, 7.0, 7.7, "sstone_l"); k.B(W - E - 0.2, FB, W - E, FL, 7.0, 7.7, "sstone_l")
    k.B(E, FB, W - E, FB + 0.2, 7.0, 7.7, "sstone_l")
    for i in range(10):                                           # corbels under the parapet
        k.Bm((E + 0.3 + i * (W - 2 * E - 0.6) / 9) * T, -FL * T - 0.12, 6.85, 0.22, 0.24, 0.3, "sstone_d")
    # corner watch turret (front-right) with a slate cone
    tx, ty = (W - E - 0.55) * T, -(FL - 0.55) * T
    k.cyl((tx, ty, 5.0), 1.0, 1.0, 4.4, "sstone", segs=10)
    k.cyl((tx, ty, 9.4), 1.15, 1.15, 0.25, "sstone_l", segs=10)
    k.cone((tx, ty, 9.65), 1.3, 2.4, "roof_slate", segs=10)
    k.Bm(tx, ty - 1.0, 7.9, 0.16, 0.08, 0.6, "slit") if "slit" in k.palette else k.Bm(tx, ty - 1.0, 7.9, 0.16, 0.08, 0.6, "interior_deep")
    k.post(W - E - 0.55, FL - 0.55, 13.0, w=0.08, mat="iron")
    k.box((tx + 0.5, ty, 12.5), (0.9, 0.05, 0.6), "red")
    # banners, shield, balcony, door, windows
    for x in (1.6, 9.3):
        k.Bm(x * T, -FL * T - 0.1, 5.2, 1.0, 0.05, 2.6, "red")
        k.Bm(x * T, -FL * T - 0.12, 5.3, 0.12, 0.05, 2.0, "gold")
        k.box((x * T, -FL * T - 0.1, 3.7), (1.0, 0.05, 0.4), "red", taper=0.01)
        k.Bm(x * T, -FL * T - 0.14, 6.5, 1.2, 0.1, 0.1, "iron")
    k.B(cx - 1.7, FL, cx + 1.7, FL + 0.75, 3.7, 3.9, "plank")
    for sx in (-1, 1):
        k.box(((cx + sx * 1.4) * T, -(FL + 0.4) * T, 3.4), (0.18, 0.8, 0.18), "beam", rot=(-35, 0, 0))
    for i in range(9):
        k.Bm((cx - 1.65 + i * 3.3 / 8) * T, -(FL + 0.72) * T, 4.35, 0.08, 0.08, 0.9, "beam")
    k.Bm(cx * T, -(FL + 0.72) * T, 4.82, 3.4 * T, 0.12, 0.1, "beam")
    k.window(cx, FL, 5.2, w=1.0, h=1.8, lit=True, frame="beam")
    icon_shield(k, cx * T, -FL * T - 0.12, 6.55)
    k.Bm(cx * T, -FL * T - 0.1, 6.55, 0.62, 0.04, 0.7, "sstone_l")
    k.door(cx, FL, w=1.7, h=2.7, arch="sstone_l", wood="door_d", z0=0.35)
    for zz in (1.1, 1.9):
        k.Bm(cx * T, -FL * T - 0.12, 0.35 + zz, 1.65, 0.05, 0.1, "iron")
    for x in (3.1, 7.9):
        k.window(x, FL, 1.9, w=0.7, h=1.1, bars=True, frame="sstone_d")
        k.window(x, FL, 5.2, w=0.7, h=1.2, frame="frame_w", box=("flower_r", "leaf"))
    for x in (0.9, 10.1):
        k.Bm(x * T, -FL * T - 0.03, 2.2, 0.16, 0.06, 1.0, "interior_deep")
    # weapon rack + training dummy + lantern
    rx, ry = 8.4 * T, -(D - 0.55) * T
    k.Bm(rx, ry, 0.9, 1.4, 0.12, 0.1, "wood_d"); k.Bm(rx, ry, 0.3, 1.4, 0.12, 0.1, "wood_d")
    for i in range(4):
        k.Bm(rx - 0.5 + i * 0.33, ry - 0.05, 0.85, 0.05, 0.05, 1.6, "steel")
    k.post(10.1, D - 0.6, 1.2, w=0.12, mat="post")
    k.cyl((10.1 * T, -(D - 0.6) * T, 1.0), 0.3, 0.3, 0.7, "hay", segs=6); k.Bm(10.1 * T, -(D - 0.6) * T, 1.3, 1.1, 0.12, 0.12, "post")
    k.cyl((10.1 * T, -(D - 0.6) * T, 1.7), 0.18, 0.18, 0.3, "hay", segs=6)
    k.lantern(cx * T + 1.4, -FL * T - 0.2, 2.4); k.lantern(cx * T - 1.4, -FL * T - 0.2, 2.4)
    k.barrel(1.0, D - 0.6); k.barrel(1.7, D - 0.6)
    return {"door_face_ly": FL}


def kais_catch(k, W, D, dx):
    """v2b: side-gabled (E-W ridge, eaves to camera) two-storey front block, big fish signboard on a
    low parapet, lower rear block; awning + ice counter, nets, open market shed."""
    FL = D - 1.3
    cx = dx + 0.5
    MX = 4.0
    FB = FL - 3.6
    porch(k, E, W - E, FL, D, "plank", 0.12)
    k.plinth(MX, E, W - E, FL, 0.35, "plinth")
    k.walls(MX, E, W - E, FB + 0.2, 0.35, 3.3, "plank_b")                 # rear block
    k.roof_ew(MX, E, W - E, FB + 0.2, 3.3, 1.2, "roof_slate", o=0.2, gable="plank_b")
    k.chimney(12.2, 1.2, 3.5, 6.0, "sstone_d")
    k.walls(MX, FB, W - E, FL, 0.35, 5.9, "white")                          # two-storey front
    for i in range(16):
        k.Bm((MX + W - E) / 2 * T, -FL * T - 0.03, 0.8 + i * 0.32, (W - E - MX) * T, 0.05, 0.05, "plank_b", jitter=False)
    for x in (MX, W - E):
        k.Bm(x * T, -FL * T - 0.05, 3.1, 0.2, 0.1, 5.6, "blue")
    k.Bm((MX + W - E) / 2 * T, -FL * T - 0.06, 3.5, (W - E - MX) * T, 0.12, 0.16, "blue")
    k.roof_ew(MX, FB, W - E, FL, 5.9, 1.9, "roof_slate", o=0.4, gable="white")
    # big fish signboard on a low parapet above the eaves
    y = -FL * T - 0.25
    sx0 = (MX + W - E) / 2 * T
    k.Bm(sx0, y, 6.6, 4.6 * T, 0.14, 1.1, "cream")
    k.Bm(sx0, y + 0.02, 6.6, 4.6 * T + 0.14, 0.1, 1.24, "blue")
    for sx in (-1, 1):
        k.Bm(sx0 + sx * 2.0 * T, y + 0.3, 6.1, 0.12, 0.6, 0.12, "beam")
    k.box((sx0 - 0.4, y - 0.1, 6.6), (2.4, 0.08, 0.7), "fish", taper=0.7)
    k.box((sx0 + 1.1, y - 0.1, 6.6), (0.6, 0.08, 0.9), "fish_d", taper=0.4)
    k.Bm(sx0 - 1.3, y - 0.14, 6.7, 0.14, 0.05, 0.14, "door_d")
    for x in (5.4, 8.9, 12.5):
        k.window(x, FL, 4.6, w=0.9, h=1.0, lit=(x == 8.9), frame="frame_w", shutters="blue")
    k.door(cx, FL, w=1.4, h=2.5, arch=None, round_top=False, wood="blue", z0=0.35)
    k.Bm(cx * T, -FL * T - 0.08, 3.0, 1.9, 0.12, 0.2, "white")
    k.sign(6.0, FL, 3.3, w=1.4, h=0.7, board="cream", icon=icon_fish)
    k.awning(9.6, 13.6, FL, 3.3, depth=1.4, drop=0.6, mats=("blue", "white"))
    x0, x1 = 9.9 * T, 13.3 * T
    k.Bm((x0 + x1) / 2, -(FL + 0.55) * T, 0.45, x1 - x0, 0.7, 0.9, "plank_b")
    k.Bm((x0 + x1) / 2, -(FL + 0.55) * T, 0.95, x1 - x0 - 0.1, 0.62, 0.12, "ice", jitter=False)
    for i in range(9):
        fx = x0 + 0.3 + i * (x1 - x0 - 0.6) / 8
        k.box((fx, -(FL + 0.55) * T + (0.12 if i % 2 else -0.12), 1.06), (0.2, 0.55, 0.1),
              ("fish", "fish_d", "fire")[i % 3] if i != 4 else "flower_r", taper=0.8)
    for i in range(5):
        k._beam(((6.8 + i * 0.3) * T, -FL * T - 0.06, 0.9), ((7.6 + i * 0.3) * T, -FL * T - 0.06, 2.6), 0.04, "net")
        k._beam(((6.8 + i * 0.3) * T, -FL * T - 0.06, 2.6), ((7.6 + i * 0.3) * T, -FL * T - 0.06, 0.9), 0.04, "net")
    for x in (0.4, 3.6):
        for yy in (2.4, FL):
            k.post(x, yy, 3.0, w=0.2)
    k.slab([(E * T - 0.3, -(FL + 0.3) * T, 2.9), (MX * T, -(FL + 0.3) * T, 2.9), (MX * T, -2.0 * T, 3.9),
            (E * T - 0.3, -2.0 * T, 3.9)], 0.18, "roof_brown")
    k.B(0.4, 2.3, 3.6, 2.5, 0.3, 2.8, "plank_w")
    for i in range(4):
        k.Bm((0.8 + i * 0.8) * T, -2.6 * T, 1.9, 0.9, 0.04, 1.4, "net")
    k.Bm(2.0 * T, -(FL - 0.5) * T, 2.2, 3.2 * T, 0.06, 0.06, "rope")
    for i in range(4):
        k.box(((0.9 + i * 0.7) * T, -(FL - 0.5) * T, 1.8), (0.18, 0.08, 0.7), "fish_d", taper=0.6)
    k.barrel(0.8, D - 0.6); k.barrel(1.6, D - 0.6); k.crate(2.6, D - 0.6, 0.7); k.barrel(4.6, D - 0.55, r=0.3)
    k.cyl((3.4 * T, -(D - 0.5) * T, 0.1), 0.35, 0.35, 0.25, "rope", segs=8)
    return {"door_face_ly": FL}


def harbour_tackle(k, W, D, dx):
    FL = D - 1.3
    cx = dx + 0.5
    MW = 9.0
    DZ = 0.7
    k.use("ground")
    k.B(MW, -0.3, W + 0.3, D + 0.3, -0.35, -0.3, "water")
    k.B(E, FL - 0.1, MW, D - 0.05, 0, DZ, "deck")
    k.steps(cx - 0.9, cx + 0.9, D - 0.75, n=3, depth=0.25, rise=0.23, mat="deck")
    k.use("body")
    k.B(E, E, MW, FL, 0, DZ, "deck")
    for x in (0.4, 2.5, 6.5, 8.7):
        k.post(x, D - 0.2, DZ, w=0.25)
    k.walls(E, E, MW, FL, DZ, 3.9, "plank_g")
    for i in range(10):
        k.Bm((E + MW) / 2 * T, -FL * T - 0.03, DZ + 0.3 + i * 0.32, (MW - E) * T, 0.05, 0.05, "plank_b", jitter=False)
    k.roof_ns(E, E, MW, FL, 3.9, 4.3, "roof_green", o=0.35, gable="plank_g", barge="plank_w")
    k.window(MW / 2, FL, 5.3, w=0.9, h=0.9, frame="frame_w")
    k.chimney(7.6, 2.5, 5.5, 8.0, "post", w=0.45)
    k.door(cx, FL, w=1.4, h=2.4, arch=None, round_top=False, wood="plank_w", z0=DZ)
    k.Bm(cx * T, -FL * T - 0.08, DZ + 2.55, 1.9, 0.12, 0.18, "plank_w")
    k.window(2.0, FL, 2.3, w=1.0, h=1.0, frame="frame_w", shutters="plank_b")
    k.window(7.2, FL, 2.3, w=1.0, h=1.0, lit=True, frame="frame_w", shutters="plank_b")
    k.sign(2.2, FL, 3.7, w=0.9, h=0.8, board="plank_w", icon=icon_anchor)
    # lifebuoy
    k.cyl((6.0 * T, -FL * T - 0.08, 2.4), 0.35, 0.35, 0.1, "red", segs=10, rot=(90, 0, 0), jitter=False)
    k.cyl((6.0 * T, -FL * T - 0.14, 2.4), 0.2, 0.2, 0.1, "plank_g", segs=10, rot=(90, 0, 0), jitter=False)
    # dock deck on stilts (east)
    k.B(MW, 0.3, W - E, D - 0.1, DZ - 0.15, DZ, "deck")
    for i in range(1, 8):
        k.Bm((MW + (W - E - MW) * i / 8) * T, -(D - 0.1) * T + 0.02, DZ - 0.07, 0.03, 0.03, 0.14, "post", jitter=False)
    for x in (MW + 0.3, W - 0.5):
        for y in (0.6, 3.5, 6.2, D - 0.4):
            k.B(x - 0.1, y - 0.1, x + 0.1, y + 0.1, -0.6, DZ, "post")
    k.fence([(MW + 0.1, D - 0.2), (W - 0.3, D - 0.2), (W - 0.3, 0.4)], h=0.9 + DZ, mat="plank_w")
    # rod racks
    rx, ry = 10.8 * T, -3.0 * T
    k.Bm(rx, ry, DZ + 1.0, 1.8, 0.12, 0.1, "wood_d"); k.Bm(rx, ry, DZ + 0.2, 1.8, 0.12, 0.1, "wood_d")
    for i in range(6):
        k.cyl((rx - 0.75 + i * 0.3, ry - 0.08, DZ + 0.1), 0.025, 0.012, 2.4, ("wood", "steel")[i % 2], segs=4, jitter=False)
    # coiled rope, lobster pots, crates, lantern post
    k.cyl((10.2 * T, -6.4 * T, DZ), 0.45, 0.45, 0.15, "rope", segs=10); k.cyl((10.2 * T, -6.4 * T, DZ + 0.15), 0.32, 0.32, 0.1, "rope", segs=10)
    for x, y in ((11.6, 5.6), (12.2, 6.3), (11.8, 6.0)):
        z = DZ + (0.5 if (x, y) == (11.8, 6.0) else 0)
        k.cyl((x * T, -y * T, z), 0.35, 0.3, 0.5, "net", segs=6); k.cyl((x * T, -y * T, z + 0.5), 0.3, 0.3, 0.05, "wood", segs=6)
    k.crate(12.0, 1.4, 0.7, z=DZ); k.barrel(10.0, 1.3, z=DZ)
    k.post(8.7, D - 0.45, DZ + 2.2, w=0.14)
    k.Bm(8.7 * T - 0.3, -(D - 0.45) * T, DZ + 2.15, 0.6, 0.08, 0.08, "iron")
    k.lantern(8.7 * T - 0.55, -(D - 0.45) * T, DZ + 1.85)
    k.cyl((1.0 * T, -(D - 0.55) * T, DZ), 0.35, 0.35, 0.2, "rope", segs=8)
    k.barrel(0.9, FL + 0.35, z=DZ, r=0.3)
    return {"door_face_ly": FL}


BUILD = {k: globals()[k] for k in SPECS}
