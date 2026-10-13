"""Step 1 of the ground pipeline: periodic albedo / height / emission maps + 3D scatter lists
for fairy_moss, petal_path and moonstone_paving (v1..v5). Blender (bl_ground.py) renders them.

Every variant shares its outer border band (pixels + objects), so ANY variant tiles seamlessly
next to ANY other variant, and each one is periodic on its own.
Run: python3 src/ground/gtex.py
"""
import json, sys, numpy as np
from PIL import Image
sys.path.insert(0, __import__("os").path.dirname(__file__))
from gcommon import *

NV = 5
BD = border_dist()
X, Y = grid()
WBLEND = smooth(BAND_IN + 0.01, 0.16, BD)        # texture blend shared->unique


def mix(shared, unique):
    """variance-preserving blend (no low-contrast ring where the two noises cross-fade)."""
    w = WBLEND if shared.ndim == 2 else WBLEND[..., None]
    ms, mu = shared.mean(), unique.mean()
    out = ((shared - ms) * (1 - w) + (unique - mu) * w) / np.sqrt((1 - w) ** 2 + w ** 2)
    return out + ms * (1 - w) + mu * w


def objs_split(shared_list, unique_list):
    """shared_list: objects from the set rng (kept if centre in band); unique: kept if clear of band."""
    out = [o for o in shared_list if bdist_pt(o["x"], o["y"]) < OBJ_SHARED]
    out += [o for o in unique_list if bdist_pt(o["x"], o["y"]) >= OBJ_SHARED + o.get("r", 0.03)]
    return out


def save_maps(name, albedo, height, emis, objs, extra=None):
    Image.fromarray(np.clip(albedo, 0, 255).astype(np.uint8)).save(f"{WORK}/{name}_albedo.png")
    Image.fromarray(np.clip(emis, 0, 255).astype(np.uint8)).save(f"{WORK}/{name}_emis.png")
    np.save(f"{WORK}/{name}_height.npy", height.astype(np.float32))
    hv = (height - height.min()) / (height.max() - height.min() + 1e-9)
    Image.fromarray((hv * 65535).astype(np.uint16)).save(f"{WORK}/{name}_height16.png")
    meta = {"objects": objs}
    meta.update(extra or {})
    json.dump(meta, open(f"{WORK}/{name}_scatter.json", "w"))


def pick(r, lst):
    return lst[int(r.random() * len(lst)) % len(lst)]


# ------------------------------------------------------------------ fairy moss grass
def cushions(rng, r=0.10):
    """moss cushion mounds: periodic bumps around Poisson points (reads at 40 px as light/shade clumps)."""
    pts = poisson(rng, r)
    h = np.zeros((N, N))
    for (px, py) in pts:
        rad = rng.uniform(0.6, 1.0) * r
        d = pdist(X, Y, px, py)
        h = np.maximum(h, np.clip(1 - (d / rad) ** 2, 0, 1) ** 0.7 * rng.uniform(0.6, 1.0))
    return h


def moss_fields(rng):
    m = fbm(N, rng, (6, 12, 24, 48, 96), (0.35, 0.25, 0.18, 0.12, 0.1))
    p = fbm(N, rng, (3, 5, 9), (0.5, 0.3, 0.2))
    d = fbm(N, rng, (4, 7, 13), (0.5, 0.3, 0.2))
    fine = fbm(N, rng, (64, 128, 160), (0.4, 0.35, 0.25))
    cu = cushions(rng)
    return m, p, d, fine, cu


def moss_objects(rng, dens, interior):
    r = rng
    objs = []
    def region(x, y):
        b = bdist_pt(x, y)
        return (b >= OBJ_SHARED + 0.05) if interior else (b < OBJ_SHARED)
    def dval(x, y):
        return dens[int(y * N) % N, int(x * N) % N]
    # clover trios, in soft patches
    for (x, y) in poisson(r, 0.050, region=region):
        if r.random() < 0.15 + 0.85 * smooth(0.40, 0.70, dval(x, y)):
            g = r.random()
            col = (int(74 + 34 * g), int(134 + 32 * g), int(66 + 18 * g)) if r.random() < 0.85 else (int(62 + 20 * g), int(124 + 20 * g), int(96 + 20 * g))
            objs.append({"t": "clover", "x": x, "y": y, "rot": r.random() * 6.283, "s": r.uniform(0.075, 0.11), "col": col, "r": 0.055})
    # grass blade tufts (fine texture)
    for (x, y) in poisson(r, 0.050, region=region):
        g = r.random()
        col = (int(50 + 44 * g), int(98 + 50 * g), int(40 + 24 * g))
        objs.append({"t": "tuft", "x": x, "y": y, "rot": r.random() * 6.283, "s": r.uniform(0.06, 0.09), "col": col, "r": 0.045})
    # moonpetal flowers: rare little clusters of 2-3 (interior only: shared border flowers would repeat on
    # every tile edge and read as a dotted grid)
    for (x, y) in poisson(r, 0.40, region=region):
        if interior and r.random() < 0.7:
            col = pick(r, [(214, 196, 246), (240, 236, 252), (246, 200, 228), (200, 214, 252)])
            for k in range(int(r.integers(1, 4))):
                fx = (x + r.uniform(-0.035, 0.035)) % 1; fy = (y + r.uniform(-0.035, 0.035)) % 1
                objs.append({"t": "flower", "x": fx, "y": fy, "rot": r.random() * 6.283, "s": r.uniform(0.06, 0.075), "col": col, "r": 0.08})
    # tiny glowing specks
    for (x, y) in poisson(r, 0.34, region=region):
        if interior and r.random() < 0.4:
            col = pick(r, [(150, 240, 255), (255, 236, 150), (220, 190, 255)])
            objs.append({"t": "speck", "x": x, "y": y, "rot": 0, "s": r.uniform(0.008, 0.011), "col": col, "r": 0.012})
    return objs


def make_moss():
    rs = np.random.default_rng(1001)
    Cm, Cp, Cd, Cf, Cc = moss_fields(rs)
    tone = pnoise(N, 2, np.random.default_rng(1002)) * 0.6 + pnoise(N, 3, np.random.default_rng(1003)) * 0.4  # shared LF
    shared_objs = moss_objects(np.random.default_rng(1004), Cd, interior=False)
    for v in range(1, NV + 1):
        ru = np.random.default_rng(1100 + v)
        Um, Up, Ud, Uf, Uc = moss_fields(ru)
        m, p, d, fine, cu = mix(Cm, Um), mix(Cp, Up), mix(Cd, Ud), mix(Cf, Uf), mix(Cc, Uc)
        v_ = 0.40 * m + 0.25 * fine + 0.35 * cu
        alb = ramp(v_, [(0.0, (28, 56, 30)), (0.35, (44, 86, 40)), (0.62, (62, 110, 48)), (0.85, (86, 132, 58)), (1.0, (108, 146, 66))])
        teal = smooth(0.55, 0.85, p)[..., None]; yel = smooth(0.55, 0.85, 1 - p)[..., None]
        alb = alb * (1 - 0.30 * teal) + np.array((44, 112, 96)) * 0.30 * teal
        alb = alb * (1 - 0.22 * yel) + np.array((116, 140, 58)) * 0.22 * yel
        alb = alb * (0.94 + 0.12 * tone[..., None])
        h = 0.006 * m + 0.003 * fine + 0.016 * cu
        uobjs = moss_objects(np.random.default_rng(1200 + v), d, interior=True)
        objs = shared_objs + uobjs
        save_maps(f"fairy_moss_v{v}", alb, h, np.zeros_like(alb), objs, {"set": "fairy_moss", "rough": 0.85})
    print("moss done", len(shared_objs))


# ------------------------------------------------------------------ petal path
def blob_field(stones):
    """height bump + mask for flat embedded stones (periodic)."""
    hm = np.zeros((N, N)); mk = np.zeros((N, N)); rim = np.zeros((N, N)); tone = np.zeros((N, N))
    ang_cache = {}
    for s in stones:
        for ox in (-1, 0, 1):
            for oy in (-1, 0, 1):
                cx, cy = s["x"] + ox, s["y"] + oy
                if cx + s["R"] * 1.6 < 0 or cx - s["R"] * 1.6 > 1 or cy + s["R"] * 1.6 < 0 or cy - s["R"] * 1.6 > 1:
                    continue
                dx = X - cx; dy = (Y - cy) / s["asp"]
                ca, sa = np.cos(s["rot"]), np.sin(s["rot"])
                rx, ry = dx * ca + dy * sa, -dx * sa + dy * ca
                rho = np.sqrt(rx * rx + ry * ry); th = np.arctan2(ry, rx)
                rr = s["R"] * (1 + sum(a * np.cos(k * th + ph) for k, a, ph in s["harm"]))
                dd = 1 - rho / rr
                inside = smooth(0.0, 0.18, dd)
                hm = np.maximum(hm, inside * s["h"] * (0.85 + 0.15 * smooth(0, 1, dd)))
                mk = np.maximum(mk, inside)
                rim = np.maximum(rim, np.clip(1 - np.abs(dd + 0.04) / 0.10, 0, 1))
                tone = np.where(inside > 0.01, s["tone"], tone)
    return hm, mk, rim, tone


PATH_STONE_PLAN = {1: [], 2: [0.13], 3: [], 4: [0.10], 5: [0.075, 0.06]}   # interior stones per variant (radius)


def _stone(r, x, y, R):
    return {"x": x, "y": y, "R": R, "asp": r.uniform(0.65, 1.0), "rot": r.random() * 6.28,
            "h": r.uniform(0.004, 0.006), "tone": r.uniform(0.92, 1.06),
            "harm": [(k, r.uniform(0.03, 0.10) / k ** 0.5, r.random() * 6.28) for k in (2, 3, 5)]}


def path_stones(r, interior, v=1):
    """interior: a few big flat stepping stones per variant (PATH_STONE_PLAN, ~40% of tiles carry one), so a
    long path does not show a stone in every tile.  border (shared): rare small stones."""
    out = []
    if interior:
        for R in PATH_STONE_PLAN[v]:
            for _ in range(500):
                x, y = r.random(), r.random()
                if bdist_pt(x, y) < OBJ_SHARED + R + 0.04:
                    continue
                if all(((x - o["x"]) ** 2 + (y - o["y"]) ** 2) ** 0.5 > R + o["R"] + 0.06 for o in out):
                    out.append(_stone(r, x, y, R)); break
        return out
    for (x, y) in poisson(r, 0.30, region=lambda x, y: bdist_pt(x, y) < OBJ_SHARED):
        if r.random() < 0.18:
            out.append(_stone(r, x, y, r.uniform(0.025, 0.04)))
    return out


def path_objects(r, rim, interior):
    objs = []
    def region(x, y):
        b = bdist_pt(x, y)
        return (b >= OBJ_SHARED + 0.04) if interior else (b < OBJ_SHARED)
    for (x, y) in poisson(r, 0.095, region=region):          # petals (inn-roof pink, mushroom lilac, cream)
        if r.random() < 0.65:
            col = pick(r, [(236, 120, 172), (244, 160, 200), (196, 136, 230), (250, 214, 226), (228, 100, 160), (236, 120, 172)])
            objs.append({"t": "petal", "x": x, "y": y, "rot": r.random() * 6.283, "s": r.uniform(0.065, 0.085), "col": col, "r": 0.045})
    for (x, y) in poisson(r, 0.075, region=region):          # pebbles
        if r.random() < 0.5:
            g = r.uniform(0.78, 1.1)
            objs.append({"t": "pebble", "x": x, "y": y, "rot": r.random() * 6.283, "s": r.uniform(0.010, 0.017),
                         "col": (int(172 * g), int(160 * g), int(140 * g)), "r": 0.02})
    for (x, y) in poisson(r, 0.030, region=region):          # grass + moss in the cracks round the stones
        c = rim[int(y * N) % N, int(x * N) % N]
        if c > 0.45 and r.random() < 0.55:
            g = r.random()
            if r.random() < 0.6:
                objs.append({"t": "tuft", "x": x, "y": y, "rot": r.random() * 6.283, "s": r.uniform(0.03, 0.05),
                             "col": (int(64 + 40 * g), int(112 + 40 * g), int(46 + 20 * g)), "r": 0.03})
            else:
                objs.append({"t": "moss", "x": x, "y": y, "rot": r.random() * 6.283, "s": r.uniform(0.010, 0.018),
                             "col": (int(62 + 30 * g), int(106 + 30 * g), int(48 + 14 * g)), "r": 0.02})
    return objs


def make_path():
    rs = np.random.default_rng(2001)
    sh_stones = path_stones(np.random.default_rng(2002), False)
    Ce = fbm(N, rs, (6, 12, 24, 48, 96), (0.35, 0.25, 0.18, 0.12, 0.1))
    Cg = fbm(N, rs, (64, 128, 160), (0.4, 0.35, 0.25))
    Cw = fbm(N, rs, (3, 5, 8), (0.5, 0.3, 0.2))
    Cs = fbm(N, rs, (16, 32, 64), (0.5, 0.3, 0.2))
    Cmo = fbm(N, rs, (12, 24, 48), (0.5, 0.3, 0.2))
    Cc1 = fbm(N, rs, (5, 10, 20), (0.6, 0.3, 0.1)); Cc2 = fbm(N, rs, (3, 6), (0.6, 0.4))
    tone = pnoise(N, 2, np.random.default_rng(2004))
    sh_hm, sh_mk, sh_rim, sh_tone = blob_field(sh_stones)
    for v in range(1, NV + 1):
        ru = np.random.default_rng(2100 + v)
        ust = path_stones(np.random.default_rng(2200 + v), True, v)
        hm, mk, rim, stone_tone = blob_field(ust)
        hm, mk, rim = np.maximum(hm, sh_hm), np.maximum(mk, sh_mk), np.maximum(rim, sh_rim)
        stone_tone = np.where(sh_mk > 0.01, sh_tone, stone_tone)
        e = mix(Ce, fbm(N, ru, (6, 12, 24, 48, 96), (0.35, 0.25, 0.18, 0.12, 0.1)))
        gr = mix(Cg, fbm(N, ru, (64, 128, 160), (0.4, 0.35, 0.25)))
        wear = mix(Cw, fbm(N, ru, (3, 5, 8), (0.5, 0.3, 0.2)))
        sg = mix(Cs, fbm(N, ru, (16, 32, 64), (0.5, 0.3, 0.2)))
        mossn = mix(Cmo, fbm(N, ru, (12, 24, 48), (0.5, 0.3, 0.2)))
        ev = np.clip(0.55 * e + 0.45 * gr, 0, 1)
        crn = mix(Cc1, fbm(N, ru, (5, 10, 20), (0.6, 0.3, 0.1)))
        crack = np.clip(1 - np.abs(crn - 0.5) * 40, 0, 1) * smooth(0.45, 0.7, mix(Cc2, fbm(N, ru, (3, 6), (0.6, 0.4)))) * (1 - mk)
        alb = ramp(ev, [(0.0, (112, 84, 58)), (0.4, (146, 114, 80)), (0.7, (170, 140, 102)), (1.0, (192, 166, 128))])
        alb = alb * (0.90 + 0.14 * wear[..., None]) * (0.96 + 0.06 * tone[..., None])
        # flat stepping stones: pale cream-grey (inn plinth stone), mossy rims
        salb = ramp(sg, [(0, (160, 150, 134)), (0.5, (186, 176, 158)), (1, (206, 196, 176))]) * stone_tone[..., None]
        moss_on = (smooth(0.40, 0.70, mossn) * np.clip(rim * 1.5, 0, 1))[..., None]
        salb = salb * (1 - 0.75 * moss_on) + np.array((76, 120, 54)) * 0.75 * moss_on
        alb = alb * (1 - mk[..., None]) + salb * mk[..., None]
        ring = np.clip(rim - mk, 0, 1)[..., None]
        alb = alb * (1 - 0.30 * ring) + np.array((70, 96, 46)) * 0.18 * ring * smooth(0.5, 0.8, mossn)[..., None]
        alb = alb * (1 - 0.40 * crack[..., None])
        h = 0.004 * e + 0.002 * gr + hm - 0.003 * crack
        grassy = np.maximum(rim - mk, crack)
        objs = objs_split(path_objects(np.random.default_rng(2400), grassy, False),
                          path_objects(np.random.default_rng(2500 + v), grassy, True))
        save_maps(f"petal_path_v{v}", alb, h, np.zeros_like(alb), objs, {"set": "petal_path", "rough": 0.9})
    print("path done")


# ------------------------------------------------------------------ moonstone paving
def draw_veins(r, pts):
    """silver-blue moonstone veins: branching wandering polylines, anti-aliased (drawn at 2x then reduced)."""
    from PIL import ImageDraw, ImageFilter
    S = 2 * N
    im = Image.new("L", (S, S), 0); d = ImageDraw.Draw(im)
    for (px, py) in pts:
        for _ in range(int(r.integers(2, 4))):
            x, y = px + r.uniform(-0.08, 0.08), py + r.uniform(-0.08, 0.08)
            a = r.uniform(0, 6.283); steps = int(r.integers(8, 15)); w = r.uniform(4.0, 7.0)
            for k in range(steps):
                a += r.normal(0, 0.45); ln = r.uniform(0.012, 0.03)
                nx, ny = x + np.cos(a) * ln, y + np.sin(a) * ln
                d.line((x * S, y * S, nx * S, ny * S), fill=int(255 * r.uniform(0.6, 1.0)), width=max(1, int(w)))
                if r.random() < 0.18:
                    b = a + r.choice([-1, 1]) * r.uniform(0.6, 1.2); bx, by = nx, ny
                    for j in range(int(r.integers(2, 5))):
                        b += r.normal(0, 0.4); l2 = r.uniform(0.01, 0.022)
                        d.line((bx * S, by * S, (bx + np.cos(b) * l2) * S, (by + np.sin(b) * l2) * S), fill=150, width=max(1, int(w * 0.6)))
                        bx, by = bx + np.cos(b) * l2, by + np.sin(b) * l2
                x, y = nx, ny
                w = max(2.0, w * 0.94)
    im = im.filter(ImageFilter.GaussianBlur(1.6)).resize((N, N), Image.LANCZOS)
    return np.clip(np.asarray(im, float) / 200.0, 0, 1)


def power_voronoi(pts, wts, Xw, Yw):
    d1 = np.full((N, N), 9.0); d2 = np.full((N, N), 9.0); idx = np.zeros((N, N), int)
    for k, ((px, py), w) in enumerate(zip(pts, wts)):
        d = np.sqrt(np.maximum((Xw - px) ** 2 + (Yw - py) ** 2 - w, 0))
        m = d < d1
        d2 = np.where(m, d1, np.minimum(d2, d)); idx = np.where(m, k, idx); d1 = np.where(m, d, d1)
    return d1, d2, idx


PAVE_JOINT = 0.006   # joint half-width at the tile border


def make_paving():
    """Flagstones fitted inside each tile: the tile border is always a (wavy, mossy) joint shared by all
    variants, so variants are completely different inside yet tile seamlessly in any order."""
    rs = np.random.default_rng(3001)
    wob = -(0.7 * pnoise(N, 8, rs) + 0.3 * pnoise(N, 16, rs)) * 0.006                # shared, periodic, <= 0
    Cm = fbm(N, rs, (10, 20, 40), (0.5, 0.3, 0.2))                                  # shared moss field
    jfine = fbm(N, rs, (64, 128), (0.6, 0.4))
    bdw = BD + wob                                                                  # wavy border distance
    tone = pnoise(N, 2, np.random.default_rng(3003))
    tint_cols = np.array([(210, 208, 214), (190, 197, 212), (202, 194, 214), (210, 204, 196), (198, 202, 208)], float)
    for v in range(1, NV + 1):
        ru = np.random.default_rng(3200 + v)
        pts = poisson(ru, 0.30, region=lambda x, y: 0.06 < x < 0.94 and 0.06 < y < 0.94)
        wts = ru.uniform(0, 0.012, len(pts))
        jx = X + (pnoise(N, 6, ru) - 0.5) * 0.04; jy = Y + (pnoise(N, 6, ru) - 0.5) * 0.04
        d1, d2, idx = power_voronoi(pts, wts, jx, jy)
        chip = (fbm(N, ru, (48, 96, 160), (0.5, 0.3, 0.2)) - 0.5) * 0.006 * smooth(0.002, 0.006, BD)
        edge = np.maximum(np.minimum(d2 - d1, 2 * np.maximum(bdw, 0)) + chip, 0)
        tones = ru.uniform(0.90, 1.05, len(pts)); tints = ru.integers(0, len(tint_cols), len(pts))
        tilt = ru.normal(0, 1, (len(pts), 2)) * 0.006
        n = fbm(N, ru, (8, 16, 32, 64, 128), (0.3, 0.25, 0.2, 0.15, 0.1))
        warp = fbm(N, ru, (6, 12), (0.6, 0.4))
        vn = np.mod(pnoise(N, 3, ru) * 1.4 + warp * 0.9, 1.0)
        vn2 = np.mod(pnoise(N, 5, ru) * 1.2 + fbm(N, ru, (10, 20), (0.6, 0.4)) * 0.8, 1.0)
        has_vein = (ru.random(len(pts)) < 0.85)[idx]
        cloud = fbm(N, ru, (4, 8, 16), (0.5, 0.3, 0.2))
        speck = fbm(N, ru, (128, 160), (0.5, 0.5))
        base = tint_cols[tints[idx]] * tones[idx][..., None]
        base = base * (0.92 + 0.10 * n[..., None]) * (0.97 + 0.05 * tone[..., None])
        base = base * (0.94 + 0.10 * cloud[..., None]) * (0.91 + 0.15 * speck[..., None])
        base = base * (0.86 + 0.14 * smooth(0.008, 0.07, edge))[..., None]
        vein = draw_veins(ru, pts) * smooth(0.012, 0.035, edge) * has_vein
        halo = np.clip(vein * 1.0, 0, 1)
        base = base * (1 - 0.55 * halo[..., None]) + np.array((126, 156, 214)) * 0.55 * halo[..., None]
        core = np.clip(vein - 0.6, 0, 0.4)[..., None] / 0.4
        base = base * (1 - 0.6 * core) + np.array((232, 240, 255)) * 0.6 * core
        joint = 1 - smooth(0.006, 0.014, edge)
        bevel = smooth(0.003, 0.024, edge)
        cc = np.array(pts)
        lift = ru.uniform(-0.0015, 0.0015, len(pts))[idx]
        h = (0.011 + lift) * bevel + 0.0012 * n + 0.0006 * speck
        h = h + (tilt[idx][..., 0] * (X - cc[idx][..., 0]) + tilt[idx][..., 1] * (Y - cc[idx][..., 1])) * bevel
        mn = np.where(BD < 0.05, Cm, Cm * 0.5 + fbm(N, ru, (10, 20, 40), (0.5, 0.3, 0.2)) * 0.5)
        moss_amt = smooth(0.30, 0.60, mn)
        jc = ramp(0.6 * mn + 0.4 * jfine, [(0, (70, 76, 74)), (0.5, (84, 96, 80)), (1, (96, 122, 74))])
        jc = jc * (1 - moss_amt[..., None] * 0.35) + np.array((70, 110, 56)) * moss_amt[..., None] * 0.35
        alb = base * (1 - joint[..., None]) + jc * joint[..., None]
        creep = ((1 - smooth(0.014, 0.05, edge + 0.02 * jfine)) * smooth(0.55, 0.85, mn))[..., None]
        alb = alb * (1 - 0.65 * creep) + np.array((84, 126, 62)) * 0.65 * creep
        emis = np.array((120, 175, 255)) * (core[..., 0] * 0.8 + vein * 0.25 + 0.03 * smooth(0.6, 0.9, cloud) * (1 - joint))[..., None]
        objs = []
        shared_mask = (BD < 0.0025) & (smooth(0.35, 0.70, Cm) > 0.3)
        inter_mask = (joint > 0.8) & (moss_amt > 0.3) & (BD >= 0.07)
        for inter, src in ((False, np.random.default_rng(3400)), (True, np.random.default_rng(3500 + v))):
            ys, xs = np.where(inter_mask if inter else shared_mask)
            used = []
            for k in src.permutation(len(xs))[:3000]:
                x, y = (xs[k] + 0.5) / N, (ys[k] + 0.5) / N
                b = BD[ys[k], xs[k]]
                if any(min(abs(x - a), 1 - abs(x - a)) ** 2 + min(abs(y - c), 1 - abs(y - c)) ** 2 < 0.03 ** 2 for a, c in used):
                    continue
                used.append((x, y)); g = src.random()
                if src.random() < 0.10:
                    objs.append({"t": "speck", "x": x, "y": y, "rot": 0, "s": src.uniform(0.007, 0.010),
                                 "col": [(160, 230, 255), (230, 210, 255)][int(src.random() * 2)], "r": 0.01})
                else:
                    objs.append({"t": "mossflat", "x": x, "y": y, "rot": src.random() * 6.28, "s": src.uniform(0.013, 0.022),
                                 "col": (int(56 + 26 * g), int(94 + 26 * g), int(46 + 12 * g)), "r": 0.02})
        # shared border objects must be identical across variants: keep only those from the shared rng in band
        save_maps(f"moonstone_paving_v{v}", alb, h, emis, objs, {"set": "moonstone_paving", "rough": 0.40,
                                                               "band": [0.0015, 0.003]})
        print("paving", v, len(pts), len(objs))


# ------------------------------------------------------------------ moonstone paving, macro version
PAVE_M = 4          # the plaza texture is ONE seamless 4x4-tile texture cut into 16 tiles (v1..v16)


def make_paving_macro(M=PAVE_M):
    """Crazy paving that ignores the tile grid: one periodic M x M-tile texture (2560 px master), joints run
    freely across tile borders, cut into M*M tiles.  Tile for world (x, y) = v{(y % M) * M + (x % M) + 1}.
    All lengths below are in TILE units; u = 1/M converts to macro units."""
    from PIL import ImageDraw, ImageFilter
    NM = N * M; u = 1.0 / M
    c = (np.arange(NM) + 0.5) / NM
    XM, YM = np.meshgrid(c, c)
    def pn(cells, r): return pnoise(NM, cells * M, r)
    def fb(r, octs, amps): return fbm(NM, r, tuple(o * M for o in octs), amps)
    rs = np.random.default_rng(3701)
    pts = poisson(rs, 0.27 * u)                                   # stone centres (macro units, periodic)
    P = len(pts)
    wts = rs.uniform(0, 0.014, P) * u * u
    jx = XM + (pn(6, rs) - 0.5) * 0.04 * u; jy = YM + (pn(6, rs) - 0.5) * 0.04 * u
    d1 = np.full((NM, NM), 9.0, np.float32); d2 = d1.copy(); idx = np.zeros((NM, NM), np.int32)
    for k, ((px, py), w) in enumerate(zip(pts, wts)):
        dx = np.abs(jx - px); dx = np.minimum(dx, 1 - dx); dy = np.abs(jy - py); dy = np.minimum(dy, 1 - dy)
        d = np.sqrt(np.maximum(dx * dx + dy * dy - w, 0)).astype(np.float32)
        m = d < d1
        d2 = np.where(m, d1, np.minimum(d2, d)); idx = np.where(m, k, idx); d1 = np.where(m, d, d1)
    chip = (fb(rs, (48, 96, 160), (0.5, 0.3, 0.2)) - 0.5) * 0.006
    edge = np.maximum((d2 - d1) / u + chip, 0)                     # tile units again
    tint_cols = np.array([(206, 205, 212), (194, 199, 212), (201, 197, 212), (207, 204, 199), (198, 201, 208)], float)
    tones = rs.uniform(0.90, 1.05, P); tints = rs.integers(0, len(tint_cols), P)
    tilt = rs.normal(0, 1, (P, 2)) * 0.006
    n = fb(rs, (8, 16, 32, 64, 128), (0.3, 0.25, 0.2, 0.15, 0.1))
    tone = pn(2, rs)
    cloud = fb(rs, (4, 8, 16), (0.5, 0.3, 0.2))
    speck = fb(rs, (128, 160), (0.5, 0.5))
    base = tint_cols[tints[idx]] * tones[idx][..., None]
    base = base * (0.92 + 0.10 * n[..., None]) * (0.97 + 0.05 * tone[..., None])
    base = base * (0.94 + 0.10 * cloud[..., None]) * (0.91 + 0.15 * speck[..., None])
    base = base * (0.84 + 0.16 * smooth(0.008, 0.07, edge))[..., None]
    # veins: branching polylines drawn on a periodic canvas (3x3 wrap) at 1x master res
    S = NM
    im = Image.new("L", (S, S), 0); dr = ImageDraw.Draw(im)
    has_vein = rs.random(P) < 0.8
    for k, (px, py) in enumerate(pts):
        if not has_vein[k]:
            continue
        for _ in range(int(rs.integers(2, 4))):
            x, y = px + rs.uniform(-0.07, 0.07) * u, py + rs.uniform(-0.07, 0.07) * u
            a = rs.uniform(0, 6.283); steps = int(rs.integers(8, 14)); w = rs.uniform(6.0, 9.0)
            for _s in range(steps):
                a += rs.normal(0, 0.45); ln = rs.uniform(0.012, 0.03) * u
                nx, ny = x + np.cos(a) * ln, y + np.sin(a) * ln
                for ox in (-1, 0, 1):
                    for oy in (-1, 0, 1):
                        dr.line(((x + ox) * S, (y + oy) * S, (nx + ox) * S, (ny + oy) * S), fill=int(255 * rs.uniform(0.7, 1.0)), width=max(1, int(w)))
                if rs.random() < 0.2:
                    b = a + rs.choice([-1, 1]) * rs.uniform(0.6, 1.2); bx, by = nx, ny
                    for _j in range(int(rs.integers(2, 5))):
                        b += rs.normal(0, 0.4); l2 = rs.uniform(0.01, 0.022) * u
                        ex, ey = bx + np.cos(b) * l2, by + np.sin(b) * l2
                        for ox in (-1, 0, 1):
                            for oy in (-1, 0, 1):
                                dr.line(((bx + ox) * S, (by + oy) * S, (ex + ox) * S, (ey + oy) * S), fill=170, width=max(1, int(w * 0.6)))
                        bx, by = ex, ey
                x, y = nx, ny
                w = max(3.0, w * 0.94)
    vein = np.asarray(im.filter(ImageFilter.GaussianBlur(1.5)), float) / 200.0
    vein = np.clip(vein, 0, 1) * smooth(0.012, 0.035, edge)
    halo = np.asarray(im.filter(ImageFilter.GaussianBlur(9.0)), float) / 160.0 * smooth(0.012, 0.035, edge)
    base = base * (1 - 0.35 * halo[..., None]) + np.array((150, 178, 230)) * 0.35 * halo[..., None]
    base = base * (1 - 0.70 * vein[..., None]) + np.array((128, 160, 222)) * 0.70 * vein[..., None]
    core = (np.clip(vein - 0.55, 0, 0.45) / 0.45)[..., None]
    base = base * (1 - 0.75 * core) + np.array((236, 244, 255)) * 0.75 * core
    joint = 1 - smooth(0.006, 0.014, edge)
    bevel = smooth(0.003, 0.024, edge)
    cc = np.array(pts)
    lift = rs.uniform(-0.0015, 0.0015, P)[idx]
    h = (0.011 + lift) * bevel + 0.0012 * n + 0.0006 * speck
    ddx = XM - cc[idx][..., 0]; ddx = (ddx + 0.5) % 1 - 0.5
    ddy = YM - cc[idx][..., 1]; ddy = (ddy + 0.5) % 1 - 0.5
    h = h + (tilt[idx][..., 0] * ddx / u + tilt[idx][..., 1] * ddy / u) * bevel
    mn = fb(rs, (10, 20, 40), (0.5, 0.3, 0.2)); jfine = fb(rs, (64, 128), (0.6, 0.4))
    moss_amt = smooth(0.30, 0.60, mn)
    jc = ramp(0.6 * mn + 0.4 * jfine, [(0, (70, 76, 74)), (0.5, (84, 96, 80)), (1, (96, 122, 74))])
    jc = jc * (1 - moss_amt[..., None] * 0.35) + np.array((70, 110, 56)) * moss_amt[..., None] * 0.35
    alb = base * (1 - joint[..., None]) + jc * joint[..., None]
    creep = ((1 - smooth(0.014, 0.05, edge + 0.02 * jfine)) * smooth(0.55, 0.85, mn))[..., None]
    alb = alb * (1 - 0.65 * creep) + np.array((84, 126, 62)) * 0.65 * creep
    emis = np.array((120, 175, 255)) * (core[..., 0] * 0.9 + vein * 0.3 + 0.03 * smooth(0.6, 0.9, cloud) * (1 - joint))[..., None]
    # 3D joint dressing (macro tile units 0..M): moss clumps + rare glow specks, spaced with a hash grid
    objs = []
    ys, xs = np.where((joint > 0.8) & (moss_amt > 0.3))
    cell = {}
    sp = 0.03
    for k in rs.permutation(len(xs))[:3000 * M * M]:
        x, y = (xs[k] + 0.5) / N, (ys[k] + 0.5) / N                 # tile units within macro
        gx, gy = int(x / sp), int(y / sp)
        G = int(M / sp)
        if any(((x - a) ** 2 + (y - b) ** 2) < sp * sp
               for ox in (-1, 0, 1) for oy in (-1, 0, 1) for (a, b) in cell.get(((gx + ox) % G, (gy + oy) % G), [])):
            continue
        cell.setdefault((gx % G, gy % G), []).append((x, y)); g = rs.random()
        if rs.random() < 0.10:
            objs.append({"t": "speck", "x": x, "y": y, "rot": 0, "s": rs.uniform(0.007, 0.010),
                         "col": [(160, 230, 255), (230, 210, 255)][int(rs.random() * 2)], "r": 0.01})
        else:
            objs.append({"t": "mossflat", "x": x, "y": y, "rot": rs.random() * 6.28, "s": rs.uniform(0.013, 0.022),
                         "col": (int(56 + 26 * g), int(94 + 26 * g), int(46 + 12 * g)), "r": 0.02})
    base_name = "moonstone_paving_macro"
    save_maps(base_name, alb, h, emis, objs, {"set": "moonstone_paving", "rough": 0.40})
    for j in range(M):
        for i in range(M):
            v = j * M + i + 1
            json.dump({"objects": objs, "set": "moonstone_paving", "rough": 0.40,
                       "macro": {"M": M, "i": i, "j": j, "base": base_name}},
                      open(f"{WORK}/moonstone_paving_v{v}_scatter.json", "w"))
    print("paving macro", P, "stones", len(objs), "objects")


if __name__ == "__main__":
    which = sys.argv[1:] or ["moss", "path", "paving"]
    if "moss" in which: make_moss()
    if "path" in which: make_path()
    if "paving" in which: make_paving_macro()
    if "paving_tilefit" in which: make_paving()
