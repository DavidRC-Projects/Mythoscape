"""Fairy ground: ground_under map, silhouette-trimmed collision proposal, deterministic decal placement.

Run:  python3 src/ground_layout.py      (writes json/ground_under.json, json/collision_trimmed/*.json,
                                          json/ground_decals.json, json/contact_decals.json)
Then: python3 src/decal_check.py        (independent PASS/FAIL check of the decal placement)
Everything is read from json/village_layout.json, json/collision/*.json, json/npc_spawns.json,
json/dungeon_entrance.json and the 1x building / fountain sprites. Grid: x east, y south, inclusive rects.
"""
import json, os, glob
import numpy as np
from PIL import Image

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
J = os.path.join(ROOT, "json")
TILE = 40


def load(p):
    return json.load(open(os.path.join(ROOT, p)))


LAYOUT = load("json/village_layout.json")
ZONE = tuple(LAYOUT["fairy_zone"])
COLL = {os.path.basename(p)[:-5]: json.load(open(p)) for p in sorted(glob.glob(os.path.join(J, "collision", "*.json")))}
NPCS = load("json/npc_spawns.json")["npcs"]
DUNG = load("json/dungeon_entrance.json")
KIND = {k: ("fountains" if k in LAYOUT["fountains"] else "buildings") for k in COLL}


def in_zone(x, y):
    return ZONE[0] <= x <= ZONE[2] and ZONE[1] <= y <= ZONE[3]


def painted():
    """ground type per tile from the paint ops only (what the layout paints BEFORE the WALL stamp)."""
    g = {}
    for op in LAYOUT["paint_ops"]:
        x0, y0, x1, y1 = op["rect"]
        for y in range(y0, y1 + 1):
            for x in range(x0, x1 + 1):
                g[(x, y)] = op["tile"]
    return g


PAINT = painted()


def coverage(key):
    """fraction of each world tile covered (alpha>0.5) by the 1x sprite of a building / fountain."""
    d = os.path.join(ROOT, "assets", KIND[key], key)
    meta = json.load(open(os.path.join(d, "meta.json")))
    p = os.path.join(d, meta["files"]["1x"]) if KIND[key] == "buildings" else os.path.join(d, "frames_1x", "f00.png")
    a = np.asarray(Image.open(p).convert("RGBA"))[..., 3] > 127
    ox, oy = meta["origin_px"]["1x"]; fp = meta["footprint"]
    cov = {}
    H, W = a.shape
    for ty in range((-oy) // TILE - 1, (H - oy) // TILE + 2):
        for tx in range((-ox) // TILE - 1, (W - ox) // TILE + 2):
            px, py = ox + tx * TILE, oy + ty * TILE
            if px < 0 or py < 0 or px + TILE > W or py + TILE > H:
                continue
            c = float(a[py:py + TILE, px:px + TILE].mean())
            if c > 0:
                cov[(fp["x0"] + tx, fp["y0"] + ty)] = c
    return cov


COV = {k: coverage(k) for k in COLL}


def ground_under():
    out = {}
    for k, c in COLL.items():
        for x, y in c["blocked_tiles"]:
            out[f"{x},{y}"] = PAINT.get((x, y), "GRASS")
    by = {}
    for k, c in COLL.items():
        cnt = {}
        for x, y in c["blocked_tiles"]:
            t = PAINT.get((x, y), "GRASS"); cnt[t] = cnt.get(t, 0) + 1
        by[k] = cnt
    doc = {
        "rule": "Inside ZONES['fairy_village'], a WALL tile listed here is a building/fountain collision tile. Draw the "
                "ground named here (GRASS -> fairy_moss, STONE -> moonstone_paving, PATH -> petal_path) instead of the "
                "default dark wall tile. Collision is unchanged: the tile stays WALL / unwalkable. For autotile edges treat "
                "the tile as its ground_under type.",
        "source": "json/village_layout.json paint_ops (value painted before the collision WALL stamp)",
        "summary": by,
        "tiles": out,
    }
    json.dump(doc, open(os.path.join(J, "ground_under.json"), "w"), indent=1)
    return out


def trimmed(threshold=0.5):
    """blocked tiles whose 1x sprite coverage < threshold stick out past the silhouette -> proposed for removal.
    The door / interaction tile always stays blocked."""
    os.makedirs(os.path.join(J, "collision_trimmed"), exist_ok=True)
    res = {}
    for k, c in COLL.items():
        keep, drop = [], []
        inter = tuple(c.get("interaction_tile") or ())
        for x, y in c["blocked_tiles"]:
            cv = COV[k].get((x, y), 0.0)
            (keep if (cv >= threshold or (x, y) == inter) else drop).append([x, y, round(cv, 2)])
        res[k] = (keep, drop)
        json.dump({"key": k, "rule": f"keep a blocked tile when >= {int(threshold*100)}% of it is covered by the 1x sprite "
                   "(alpha > 0.5) or it is the interaction/door tile", "proposal_only": True,
                   "blocked_tiles": [t[:2] for t in keep], "removed": [{"tile": t[:2], "coverage": t[2]} for t in drop],
                   "interaction_tile": c.get("interaction_tile"), "stand_tile": c.get("stand_tile"),
                   "coverage_of_kept": {f"{t[0]},{t[1]}": t[2] for t in keep}},
                  open(os.path.join(J, "collision_trimmed", f"{k}.json"), "w"), indent=1)
    return res


# ------------------------------------------------------------------ decals
DECALS = {   # id: footprint (w, h)
    "mushroom_ring": (2, 2), "toadstool_cluster": (1, 1), "moonpetal_clump": (1, 1), "rosebell_clump": (1, 1),
    "fallen_petals": (1, 1), "glow_stones": (1, 1), "fairy_lantern": (1, 1), "fern_clump": (1, 1), "pebbles": (1, 1),
}


def forbidden():
    """tiles a ground decal may never touch (reason per tile)."""
    f = {}
    def add(t, why):
        f.setdefault(tuple(t), why)
    for k, c in COLL.items():
        for t in c["blocked_tiles"]:
            add(t, f"collision:{k}")
        if c.get("interaction_tile"): add(c["interaction_tile"], f"door/interact:{k}")
        if c.get("stand_tile"): add(c["stand_tile"], f"stand:{k}")
        if KIND[k] == "fountains":
            fp = c["footprint"]
            for y in range(fp["y0"], fp["y1"] + 1):
                for x in range(fp["x0"], fp["x1"] + 1):
                    add((x, y), f"fountain:{k}")
    for n in NPCS:
        add((n["x"], n["y"]), f"npc:{n['id']}")
    new = DUNG["new"]
    for t in new["mouth_tiles"]: add(t, "dungeon_mouth")
    add(new["return_tile"], "dungeon_return"); add(new["enter"], "dungeon_enter"); add(new["exit"], "dungeon_exit")
    for name, (old, nw) in DUNG["moves"].items():
        add(nw, f"moved_entity:{name.split(' ')[0]}")
    return f


def vhash(x, y, salt=0):
    h = (x * 73856093) ^ (y * 19349663) ^ (salt * 83492791)
    h = (h ^ (h >> 13)) * 1274126177 & 0xFFFFFFFF
    return ((h >> 8) & 0xFFFF) / 65536.0


def place():
    F = forbidden()
    hidden = set()
    for k, cov in COV.items():
        for t, c in cov.items():
            if c > 0.5:
                hidden.add(t)          # under a roof / canopy: a decal there would never be seen
    near_bld = set()
    for k, c in COLL.items():
        for x, y in c["blocked_tiles"]:
            for dx in (-1, 0, 1):
                for dy in (-1, 0, 1):
                    near_bld.add((x + dx, y + dy))

    def ok(x, y, w=1, h=1):
        for yy in range(y, y + h):
            for xx in range(x, x + w):
                if not in_zone(xx, yy) or (xx, yy) in F or PAINT.get((xx, yy)) != "GRASS" or (xx, yy) in hidden:
                    return False
        return True

    taken = set(); out = []

    def free(x, y, w, h, gap=1):
        return all((xx, yy) not in taken for yy in range(y - gap, y + h + gap) for xx in range(x - gap, x + w + gap))

    def put(did, x, y):
        w, h = DECALS[did]
        out.append({"id": did, "x": x, "y": y, "w": w, "h": h})
        for yy in range(y, y + h):
            for xx in range(x, x + w):
                taken.add((xx, yy))

    # 1) lanterns along both edges of the Lantern Walk (rows 69 and 73) and the Petal Avenue (cols 26 / 30), every 4 tiles
    for x in range(3, 41, 4):
        for y in (69, 73):
            if ok(x, y) and free(x, y, 1, 1):
                put("fairy_lantern", x, y)
    for y in range(74, 89, 4):
        for x in (26, 30):
            if ok(x, y) and free(x, y, 1, 1):
                put("fairy_lantern", x, y)
    # 2) mushroom rings in the most open lawns (first two that fit, scanning in hash order)
    cands = sorted(((vhash(x, y, 7), x, y) for y in range(ZONE[1], ZONE[3]) for x in range(ZONE[0], ZONE[2])))
    rings = 0
    for _, x, y in cands:
        if rings >= 3:
            break
        if ok(x - 1, y - 1, 4, 4) and free(x, y, 2, 2, 2):
            put("mushroom_ring", x, y); rings += 1
    # 3) scatter: context-weighted choice, ~16% of eligible tiles, never adjacent to another decal
    for y in range(ZONE[1], ZONE[3] + 1):
        for x in range(ZONE[0], ZONE[2] + 1):
            if not ok(x, y) or not free(x, y, 1, 1):
                continue
            r = vhash(x, y, 1)
            if r > 0.16:
                continue
            nb = [PAINT.get((x + dx, y + dy)) for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1))]
            if (x, y) in near_bld:
                pool = ["fern_clump", "toadstool_cluster", "rosebell_clump", "moonpetal_clump", "fern_clump"]
            elif "PATH" in nb or "STONE" in nb:
                pool = ["fallen_petals", "pebbles", "glow_stones", "moonpetal_clump", "fallen_petals"]
            else:
                pool = ["moonpetal_clump", "rosebell_clump", "fern_clump", "pebbles", "fallen_petals", "glow_stones", "toadstool_cluster"]
            put(pool[int(vhash(x, y, 2) * len(pool)) % len(pool)], x, y)
    return out, F


def main():
    gu = ground_under()
    tr = trimmed()
    dec, F = place()
    cat = {}
    for did, (w, h) in DECALS.items():
        mp = os.path.join(ROOT, "assets", "decals", did, "meta.json")
        cat[did] = json.load(open(mp)) if os.path.exists(mp) else {"footprint_tiles": [w, h]}
    json.dump({
        "version": 1, "zone": ZONE, "tile_px": {"1x": 40, "2x": 80, "4x": 160},
        "draw_order": "terrain -> edge overlays -> contact skirts -> ground decals -> entities/buildings (y-sorted)",
        "draw_rule": "blit decal image at (x*TILE - origin_px[scale][0]*TILE/tile_px[scale], y*TILE - origin_px[scale][1]*TILE/tile_px[scale]) "
                     "where (x, y) is the decal's NW footprint tile. Purely visual: no collision, no clicks.",
        "placement": "deterministic (src/ground_layout.py: hash(x,y) + lantern rows); checked by src/decal_check.py",
        "count": len(dec), "decals": dec, "catalog": cat}, open(os.path.join(J, "ground_decals.json"), "w"), indent=1)
    contact = []
    for k, cid in (("queens_tree_hall", "queens_tree_hall_skirt"), ("moonstone_fountain", "moonstone_fountain_rim"),
                   ("lily_fountain", "lily_fountain_rim")):
        fp = COLL[k]["footprint"]
        mp = os.path.join(ROOT, "assets", "decals", cid, "meta.json")
        contact.append({"id": cid, "for": k, "anchor_tile": [fp["x0"], fp["y0"]],
                        "meta": json.load(open(mp)) if os.path.exists(mp) else None})
    json.dump({"rule": "Draw after terrain/edges and BEFORE the building or fountain sprite. Anchor = footprint NW tile; "
                       "blit at (x0*TILE - origin_px.x, y0*TILE - origin_px.y) at the matching scale. Visual only.",
               "contact_decals": contact}, open(os.path.join(J, "contact_decals.json"), "w"), indent=1)
    print("ground_under tiles:", len(gu), {k: v for k, v in json.load(open(os.path.join(J, 'ground_under.json')))['summary'].items()})
    for k, (keep, drop) in tr.items():
        print(f"trim {k}: keep {len(keep)}, remove {len(drop)}: {[tuple(t) for t in drop]}")
    from collections import Counter
    print("decals:", len(dec), dict(Counter(d['id'] for d in dec)))


if __name__ == "__main__":
    main()
