"""smithy_design.py - Gareth's Smithy v2 (same kit, camera and conventions as the 11-building pack).

Footprint unchanged: world (78,4)-(94,18) = 17 x 15 tiles, floor (79,5)-(93,17), door (86,18) -> local x 8.
Facade-first massing (the pack's roof fix):
  * front stone forge hall (west) with a camera-facing stone GABLE (roof_ns, low slate slopes);
  * open-sided timber lean-to (east) over the forge hearth + anvil, glowing coals;
  * big stone chimney with smoke (4 frames);
  * the rear third is an open walled forge yard (smelting furnace, coal heap, ore, woodpile) instead of roof.
"""
import math
import houses_geo as hg
from houses_geo import T

hg.PAL.update({
    "coal": "#26221f", "soot": "#4d4845", "soot_d": "#3a3533", "ember": "#ff6a1c", "hot": "#ffb347",
    "smoke": "#a9a7a4", "smoke_l": "#cbc9c5", "leather": "#6e4526", "ore_cu": "#b56d3a", "ore_sn": "#a7adb0",
    "ore_fe": "#7d4f3e", "yard": "#5d5750", "stone_warm": "#a39a8c",
})
hg.EMISSIVE.update({"ember": 5.0, "hot": 4.0})

SPECS = {"smithy": ("smithy", "Gareth's Smithy", 78, 4, 17, 15, 8, (1, 1, 15, 13))}
E = 0.15


def icon_anvil(k, x, y, z):
    k.Bm(x - 0.02, y, z + 0.08, 0.34, 0.06, 0.1, "iron", jitter=False)          # face
    k.box((x + 0.2, y, z + 0.08), (0.14, 0.06, 0.08), "iron", taper=0.3)        # horn
    k.Bm(x - 0.02, y, z - 0.03, 0.14, 0.06, 0.14, "iron", jitter=False)          # waist
    k.Bm(x - 0.02, y, z - 0.13, 0.28, 0.06, 0.07, "iron", jitter=False)          # foot
    k.box((x - 0.08, y - 0.02, z + 0.25), (0.05, 0.05, 0.22), "wood", rot=(0, 35, 0))   # hammer
    k.box((x - 0.02, y - 0.02, z + 0.33), (0.14, 0.05, 0.07), "iron", rot=(0, 35, 0))


def anvil(k, lx, ly, z=0.0, s=1.0):
    x, y = lx * T, -ly * T
    k.cyl((x, y, z), 0.34 * s, 0.3 * s, 0.55 * s, "wood_d", segs=8)
    k.Bm(x, y, z + 0.6 * s, 0.36 * s, 0.3 * s, 0.12 * s, "iron")
    k.Bm(x, y, z + 0.72 * s, 0.22 * s, 0.22 * s, 0.14 * s, "iron")
    k.Bm(x - 0.05 * s, y, z + 0.87 * s, 0.7 * s, 0.3 * s, 0.18 * s, "iron")
    k.box((x + 0.44 * s, y, z + 0.9 * s), (0.28 * s, 0.2 * s, 0.12 * s), "iron", taper=0.25)
    k.Bm(x - 0.1 * s, y, z + 0.97 * s, 0.35 * s, 0.05 * s, 0.03 * s, "hot", jitter=False)   # hot blade
    k.box((x + 0.15 * s, y - 0.12 * s, z + 1.0 * s), (0.07, 0.36, 0.06), "wood", rot=(0, 0, 25))  # hammer
    k.Bm(x + 0.1 * s, y - 0.28 * s, z + 1.0 * s, 0.16, 0.12, 0.12, "iron")


def build(k, W, D, dx):
    FL = D - 1.3                 # 13.7 - hall face; row 14 = porch strip (WALL tiles, door column PATH)
    cx = dx + 0.5
    HX = 11.3                    # hall | lean-to split
    HY = 9.0                     # yard | hall split
    LY = 11.0                    # lean-to back
    # ------------------------------------------------ ground
    k.use("ground")
    k.B(E, FL - 0.1, W - E, D - 0.05, 0, 0.1, "cobble")
    k.B(E + 0.3, E + 0.3, W - E - 0.3, HY, 0, 0.08, "yard")
    k.B(HX, LY, W - E, FL, 0, 0.1, "soot")
    k.steps(cx - 1.2, cx + 1.2, FL, n=1, depth=0.45, rise=0.18)
    k.use("body")
    # ------------------------------------------------ rear forge yard (open, walled)
    k.B(E, E, W - E, E + 0.45, 0, 2.3, "sstone_d")
    k.B(E - 0.05, E - 0.05, W - E + 0.05, E + 0.5, 2.3, 2.5, "sstone_l")
    for x0, x1 in ((E, E + 0.45), (W - E - 0.45, W - E)):
        k.B(x0, E, x1, LY, 0, 2.3, "sstone_d")
        k.B(x0 - 0.05, E, x1 + 0.05, LY, 2.3, 2.5, "sstone_l")
    # smelting furnace (beehive) where the interior furnace is (80,6) -> local (2,2)
    fx, fy = 2.6 * T, -2.6 * T
    k.cyl((fx, fy, 0), 1.45, 1.35, 1.3, "sstone_d", segs=10)
    k.cyl((fx, fy, 1.3), 1.35, 0.7, 1.4, "stone_warm", segs=10)
    k.cyl((fx, fy, 2.7), 0.5, 0.42, 1.8, "sstone_d", segs=8)
    k.Bm(fx, fy - 1.3, 0.7, 0.9, 0.3, 0.8, "coal")
    k.Bm(fx, fy - 1.42, 0.62, 0.7, 0.1, 0.55, "ember", jitter=False)
    k.Bm(fx, fy - 1.46, 1.15, 1.1, 0.2, 0.18, "sstone_l")
    # coal heap + ore piles + yard anvil (interior anvil (87,6) -> local (9,2))
    for i, (ox, oy, s) in enumerate(((5.2, 2.2, 1.0), (6.0, 2.6, 0.8), (5.5, 1.5, 0.75), (6.5, 1.8, 0.6), (4.9, 3.0, 0.55))):
        k.rock((ox * T, -oy * T, 0.2 * s), (0.95 * s, 0.85 * s, 0.6 * s), "coal", rough=0.3)
    for i, (ox, oy, m) in enumerate(((7.3, 4.2, "ore_cu"), (7.9, 4.6, "ore_cu"), (7.5, 5.0, "ore_cu"),
                                     (11.3, 4.4, "ore_sn"), (11.9, 4.9, "ore_sn"), (12.6, 4.3, "ore_fe"), (13.1, 4.9, "ore_fe"))):
        k.rock((ox * T, -oy * T, 0.12), (0.42, 0.38, 0.3), m, rough=0.3)
    anvil(k, 9.4, 2.4)
    # woodpile along the back wall (logs end-on to the camera)
    for r in range(3):
        for c in range(7 - r):
            x = (11.2 + c * 0.55 + r * 0.27) * T
            k.cyl((x, -0.75 * T + 0.6, 0.28 + r * 0.5), 0.27, 0.27, 1.3, "wood" if (r + c) % 2 else "wood_d",
                  segs=7, rot=(90, 0, 0))
    k.post(10.6, 0.9, 1.8, w=0.12); k.post(15.9, 0.9, 1.8, w=0.12)
    # barrels (interior barrels at local (1,5),(1,6)), crates, water butt, cart wheel on the wall
    k.barrel(1.1, 5.4); k.barrel(1.1, 6.3); k.barrel(1.1, 5.85, z=0.95)
    k.crate(15.8, 5.6); k.crate(15.8, 6.5, 0.6); k.barrel(15.9, 7.5, mat="wood_d")
    k.cyl((3.9 * T, -0.5 * T, 1.2), 0.75, 0.75, 0.12, "wood_d", segs=12, rot=(90, 0, 0))
    k.cyl((3.9 * T, -0.5 * T - 0.1, 1.2), 0.16, 0.16, 0.14, "iron", segs=6, rot=(90, 0, 0))
    # ------------------------------------------------ front forge hall (west), stone gable to camera
    k.plinth(E, HY, HX, FL, 0.4, "sstone_d")
    k.walls(E, HY, HX, FL, 0.4, 5.4, "sstone")
    k.B(E - 0.02, FL - 0.1, HX + 0.02, FL + 0.02, 4.5, 5.4, "soot")               # soot band under the parapet
    for x in (E, HX):                                                              # quoins
        for i in range(7):
            k.Bm(x * T, -FL * T - 0.04, 0.7 + i * 0.62, 0.62 if i % 2 else 0.4, 0.12, 0.34, "sstone_l")
    rng = k.rng
    for i in range(26):                                                            # masonry blocks
        bx = rng.uniform(E + 0.5, HX - 0.5); bz = rng.uniform(0.7, 3.7)
        if abs(bx - cx) < 1.4:
            continue
        k.Bm(bx * T, -FL * T - 0.03, bz, rng.uniform(0.45, 0.8), 0.06, 0.3, rng.choice(("sstone_l", "sstone_d", "stone_warm")))
    # low slate roof behind a crow-stepped stone parapet (the facade hides most of the roof)
    k.roof_ew(E, HY, HX, FL - 0.3, 5.4, 1.3, "roof_slate", o=0.2, gable="sstone")
    gx = (E + HX) / 2 * T; gy = -FL * T
    full = (HX - E) * T
    k.Bm(gx, gy + 0.18, 5.75, full + 0.1, 0.4, 0.7, "sstone")
    k.Bm(gx, gy - 0.04, 6.12, full + 0.2, 0.46, 0.12, "sstone_l")
    for i, wf in enumerate((0.78, 0.58, 0.4, 0.24)):
        z0 = 6.1 + i * 0.55
        k.Bm(gx, gy + 0.18, z0 + 0.275, full * wf, 0.4, 0.55, "sstone")
        k.Bm(gx, gy - 0.02, z0 + 0.6, full * wf + 0.12, 0.46, 0.1, "sstone_l")
    # plaque with the anvil on the parapet + lit vent
    k.cyl((gx, gy - 0.32, 6.95), 0.85, 0.85, 0.12, "beam", segs=12, rot=(90, 0, 0), jitter=False)
    k.cyl((gx, gy - 0.4, 6.95), 0.72, 0.72, 0.1, "cream", segs=12, rot=(90, 0, 0), jitter=False)
    icon_anvil(k, gx, gy - 0.48, 6.9)
    k.Bm(gx, gy - 0.02, 7.95, 0.5, 0.06, 0.34, "window", jitter=False)
    k.Bm(gx, gy - 0.05, 4.9, full * 0.7, 0.05, 0.12, "sstone_l", jitter=False)
    # big iron-banded double door with a timber canopy
    k.door(cx, FL, w=2.0, h=3.0, arch="sstone_l", wood="door_d", band="iron", round_top=False, z0=0.4)
    for zz in (1.2, 2.2):
        k.Bm(cx * T, -FL * T - 0.12, 0.4 + zz, 1.95, 0.05, 0.1, "iron")
    k.slab([((cx - 1.4) * T, -(FL + 0.55) * T, 3.8), ((cx + 1.4) * T, -(FL + 0.55) * T, 3.8),
            ((cx + 1.4) * T, -FL * T, 4.2), ((cx - 1.4) * T, -FL * T, 4.2)], 0.12, "roof_brown")
    for sx in (-1, 1):
        k.box(((cx + sx * 1.35) * T, -(FL + 0.35) * T, 3.55), (0.14, 0.75, 0.14), "beam", rot=(-40, 0, 0))
    # lit windows (forge glow) with iron bars
    for x in (2.2, 5.0):
        k.window(x, FL, 2.3, w=1.1, h=1.2, lit=True, frame="beam", bars=True, sill="sstone_l")
    k.lantern(cx * T - 1.55, -FL * T - 0.22, 2.9)
    # hanging sign on an iron bracket (anvil)
    k.sign(10.5, FL, 3.7, w=1.5, h=1.05, board="plank_l", icon=icon_anvil)
    # weapon rack + shields on the wall (west porch)
    rx, ry = 2.2 * T, -(FL + 0.35) * T
    k.Bm(rx, ry, 1.2, 2.3, 0.12, 0.1, "wood_d"); k.Bm(rx, ry, 0.35, 2.3, 0.12, 0.1, "wood_d")
    for sx in (-1, 1):
        k.Bm(rx + sx * 1.1, ry, 0.7, 0.12, 0.2, 1.4, "wood_d")
    for i in range(5):
        k.Bm(rx - 0.8 + i * 0.4, ry - 0.06, 0.95, 0.07, 0.05, 1.5, "steel")
        k.Bm(rx - 0.8 + i * 0.4, ry - 0.07, 0.35, 0.22, 0.06, 0.05, "gold" if i % 2 else "iron")
    k.box((rx + 0.9, ry - 0.08, 1.65), (0.1, 0.05, 0.9), "wood", rot=(0, 20, 0))       # axe
    k.box((rx + 1.05, ry - 0.1, 1.95), (0.35, 0.05, 0.3), "steel", taper=0.6, rot=(0, 20, 0))
    for sx, m in ((3.9, "red"), (6.3, "blue")):                                         # round shields on the wall
        k.cyl((sx * T, -FL * T - 0.06, 3.1), 0.45, 0.45, 0.08, m, segs=10, rot=(90, 0, 0), jitter=False)
        k.cyl((sx * T, -FL * T - 0.12, 3.1), 0.14, 0.14, 0.08, "steel", segs=8, rot=(90, 0, 0), jitter=False)
        k.Bm(sx * T, -FL * T - 0.1, 3.1, 0.9, 0.04, 0.08, "gold", jitter=False)
    # armour stand (steel platebody + helm) left of the door
    ax_, ay_ = 6.4 * T, -(D - 0.6) * T
    k.post(6.4, D - 0.6, 1.3, w=0.1)
    k.box((ax_, ay_, 1.15), (0.62, 0.36, 0.7), "steel", taper=0.8)
    k.Bm(ax_, ay_, 1.52, 0.8, 0.34, 0.14, "steel")
    k.cyl((ax_, ay_, 1.62), 0.2, 0.18, 0.32, "steel", segs=8)
    k.Bm(ax_, ay_ - 0.2, 1.75, 0.22, 0.03, 0.05, "coal", jitter=False)
    k.B(6.0, D - 0.85, 6.8, D - 0.35, 0, 0.12, "wood_d")
    # ------------------------------------------------ open-sided lean-to (east) over forge + anvil
    k.B(HX, LY, W - E, LY + 0.25, 0, 3.9, "soot_d")                                  # sooty back wall
    # reverse-pitch lean-to: high open front (4.5 m), low back (3.9 m) - the forge shows under it
    k.shingles([(HX * T - 0.2, -(FL + 0.45) * T, 4.5), ((W - E + 0.25) * T, -(FL + 0.45) * T, 4.5),
                ((W - E + 0.25) * T, -(LY - 0.1) * T, 3.9), (HX * T - 0.2, -(LY - 0.1) * T, 3.9)], 0.18, "wood_d")
    k.Bm((HX + W - E) / 2 * T, -(FL + 0.45) * T - 0.05, 4.45, (W - E - HX) * T + 0.5, 0.12, 0.3, "plank_l")
    for x in (HX + 0.25, 14.1, W - E - 0.2):
        k.post(x, FL + 0.2, 4.4, w=0.3, mat="beam")
        k.post(x, LY + 0.35, 3.9, w=0.26, mat="beam")
    k.Bm((HX + W - E) / 2 * T, -(FL + 0.2) * T, 4.25, (W - E - HX) * T + 0.3, 0.3, 0.26, "beam")
    for a, b in ((HX + 0.25, 14.1), (14.1, W - E - 0.2)):
        k._beam(((a + 0.1) * T, -(FL + 0.2) * T - 0.05, 3.4), ((a + 0.9) * T, -(FL + 0.2) * T - 0.05, 4.15), 0.12, "beam")
        k._beam(((b - 0.1) * T, -(FL + 0.2) * T - 0.05, 3.4), ((b - 0.9) * T, -(FL + 0.2) * T - 0.05, 4.15), 0.12, "beam")
    # chimney breast + big stone stack, rising behind the lean-to roof
    chx, chy = 13.0, 10.3
    k.B(chx - 1.25, chy - 0.8, chx + 1.25, LY + 0.3, 0, 4.9, "sstone_d")
    k.B(chx - 0.95, chy - 0.7, chx + 0.95, chy + 0.55, 4.9, 6.2, "sstone", taper=0.85)
    k.B(chx - 0.72, chy - 0.55, chx + 0.72, chy + 0.5, 6.2, 11.2, "sstone")
    k.B(chx - 0.85, chy - 0.65, chx + 0.85, chy + 0.6, 11.2, 11.55, "sstone_l")
    for i in range(9):
        z = 6.5 + i * 0.52
        k.Bm((chx + rng.uniform(-0.4, 0.4)) * T, -(chy + 0.52) * T - 0.03, z, rng.uniform(0.35, 0.6), 0.06, 0.24,
             rng.choice(("sstone_l", "sstone_d")))
    k.B(chx - 0.45, chy - 0.3, chx + 0.45, chy + 0.3, 11.55, 11.62, "coal")
    # forge hearth with glowing coals (front half visible under the eave)
    hx0, hx1, hy0, hy1 = 11.9, 14.2, LY + 0.3, 12.7
    k.B(hx0, hy0, hx1, hy1, 0, 1.0, "sstone_d")
    k.B(hx0 - 0.05, hy1 - 0.2, hx1 + 0.05, hy1 + 0.02, 0, 1.08, "sstone_l")
    k.B(hx0 + 0.2, hy0, hx1 - 0.2, hy1 - 0.22, 1.0, 1.06, "coal")
    for i in range(14):
        ex = rng.uniform(hx0 + 0.3, hx1 - 0.3); ey = rng.uniform(hy0 + 0.2, hy1 - 0.3)
        k.Bm(ex * T, -ey * T, 1.1, rng.uniform(0.16, 0.3), rng.uniform(0.16, 0.3), 0.1, rng.choice(("ember", "ember", "hot", "coal")))
    k.Bm(13.0 * T, -(hy1 - 0.1) * T - 0.05, 0.5, 0.9, 0.08, 0.45, "ember", jitter=False)    # ash-pit glow
    k.Bm(12.6 * T, -12.2 * T, 1.18, 0.9, 0.06, 0.05, "hot", jitter=False)                   # bar in the coals
    k.box((12.1 * T, -12.2 * T, 1.3), (0.8, 0.06, 0.05), "iron", rot=(0, -12, 0))           # tongs
    # bellows (leather) on the west side of the hearth
    bx, by = (hx0 - 0.45) * T, -12.0 * T
    k.box((bx, by, 0.9), (0.55, 0.9, 0.35), "leather", taper=0.5)
    k.Bm(bx, by, 0.72, 0.6, 0.95, 0.06, "wood")
    k.box((bx, by + 0.25, 1.25), (0.06, 0.06, 0.7), "wood", rot=(35, 0, 0))
    # anvil in front of the forge, quench trough, grindstone
    anvil(k, 15.3, 12.9, s=1.1)
    k.B(14.4, 13.85, 16.5, 14.6, 0, 0.55, "sstone_d")
    k.B(14.52, 13.95, 16.38, 14.5, 0.45, 0.58, "water_hi", jitter=False)
    k.cyl((16.2 * T, -12.0 * T, 0.75), 0.5, 0.5, 0.16, "sstone_l", segs=12, rot=(90, 0, 0))
    k.B(16.0, 11.85, 16.4, 12.15, 0, 0.6, "wood_d")
    # tool rack on the lean-to back wall (tongs + hammers), low enough to show
    for i in range(5):
        k.Bm((14.6 + i * 0.35) * T, -(LY + 0.27) * T, 1.6, 0.05, 0.05, 0.8, "iron")
    # porch clutter: ore barrel, sacks of coal, crate of ingots
    k.barrel(0.8, D - 0.6); k.barrel(11.6, D - 0.55, mat="wood_d")
    k.crate(12.4, D - 0.6, 0.6)
    for i in range(3):
        k.Bm((12.25 + i * 0.15) * T, -(D - 0.6) * T, 0.65 + i * 0.1, 0.4, 0.16, 0.1, ("steel", "ore_cu", "gold")[i], jitter=False)
    k.sack(13.3, D - 0.55)
    # ------------------------------------------------ smoke frames (rendered as separate layers)
    for f in range(4):
        k.use(f"smoke{f}")
        for j in range(4):
            t = j + f / 4.0
            z = 11.9 + t * 1.25
            s = 0.45 + 0.26 * t
            k.rock(((chx + 0.25 * t + 0.08 * math.sin(t * 2.1)) * T, -(chy - 0.1 * t) * T, z), (s, s * 0.9, s * 0.62),
                   "smoke_l" if j < 2 else "smoke", subdiv=2, flat_bottom=False, rough=0.08, rot=(10 * j, 20 * f, 37 * j + 15 * f))
    k.use("body")
    return {"door_face_ly": FL}


BUILD = {"smithy": build}
