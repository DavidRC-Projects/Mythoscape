"""Chosen face (David, 29 Oct 2026): one head that stays the same on every outfit and armour set.

Builds player_hd/assets/faces/ from the faces already painted in the game (no new art):
  faces/<sex>/<face_id>/head_<f>.png  (2x and 4x): the painted head of that outfit's idle frame 0, cut at
                                      the neck line, feathered into the neck.
  faces/<sex>/<face_id>/skin_<f>.png  skin ratio mask (same contract as *_skin strips).
  faces/<sex>/<face_id>/hair_<f>.png  hair ratio mask confined to the head cut (never below the neck line).
  faces/targets/<sex>/<layer>/erase_<f>.png  the layer's own head silhouette above its neck line (2x).
  faces/faces.json  neck points / head tops for donors and targets (2x canvas pixels, feet at 144,248).
Facings: s, e, n (w = e mirrored at draw time).  Run: nice python3 tools/build_faces.py
"""
import glob
import json
import os

import numpy as np
from PIL import Image
from scipy import ndimage as ndi

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "player_hd", "assets")
OUT = os.path.join(ROOT, "faces")
FACINGS = ("s", "e", "n")
FEET_Y = 248.0
# Faces on offer: every painted outfit face already in the game (David: offer ALL existing faces).
FACES = {
    "male": [
        ("villager", "Villager", "outfit_villager_hd"),
        ("squire", "Squire", "outfit_squire_hd"),
        ("noble_lord", "Noble Lord", "outfit_noble_lord_hd"),
        ("count", "Count", "outfit_count_hd"),
        ("prince_consort", "Prince", "outfit_prince_consort_hd"),
        ("kings_champion", "Champion", "outfit_kings_champion_hd"),
        ("king", "King", "outfit_king_hd"),
        ("ember", "Ember", "outfit_set_fire_m_hd"),
        ("tide", "Tide", "outfit_set_water_m_hd"),
    ],
    "female": [
        ("village_lady", "Village Lady", "outfit_village_lady_hd"),
        ("noble_lady", "Noble Lady", "outfit_noble_lady_hd"),
        ("countess", "Countess", "outfit_countess_hd"),
        ("court_gown", "Courtier", "outfit_court_gown_hd"),
        ("princess_consort", "Princess", "outfit_princess_consort_hd"),
        ("royal_favourite", "Favourite", "outfit_royal_favourite_hd"),
        ("queen", "Queen", "outfit_queen_hd"),
        ("ember", "Ember", "outfit_set_fire_f_hd"),
        ("tide", "Tide", "outfit_set_water_f_hd"),
    ],
}


def _frame0(path):
    if not os.path.isfile(path):
        return None
    im = np.array(Image.open(path).convert("RGBA"))
    h = im.shape[0]
    return im[:, :h].copy()


def _head(alpha):
    m = alpha > 128
    rows = np.where(m.any(1))[0]
    top, bot = int(rows[0]), int(rows[-1])
    h = bot - top
    band = m[top + int(0.02 * h): top + int(0.07 * h) + 1]
    xs = np.nonzero(band)[1]
    return top, float(xs.mean()), h


def _neck(art, skin, facing, fallback_y=None):
    """(neck x, neck y): bottom of the face/neck skin blob under the head (2x px)."""
    top, cx, h = _head(art[..., 3])
    if skin is not None and facing != "n":
        sk = skin[..., 3] > 90
        yy, xx = np.mgrid[0:sk.shape[0], 0:sk.shape[1]]
        band = sk & (yy < top + 0.30 * h) & (np.abs(xx - cx) < 0.12 * h)
        lab, n = ndi.label(band)
        if n:
            sizes = ndi.sum(band, lab, range(1, n + 1))
            best = 1 + int(np.argmax(sizes))
            blob = lab == best
            ys, xs = np.nonzero(blob)
            y0, y1 = int(ys.min()), int(ys.max())
            widths = blob.sum(1)
            # neck = narrowest skin row between the jaw and the blob bottom (gowns show the chest:
            # the cut must stop at the neck, not at the neckline of the dress)
            face_rows = range(y0, min(y1, y0 + int(0.11 * h)) + 1)
            yf = max(face_rows, key=lambda y: widths[y])
            lo, hi = yf + int(0.03 * h), min(y1, yf + int(0.10 * h))
            if hi > lo:
                ny = min(range(lo, hi + 1), key=lambda y: (widths[y], -y)) + int(0.012 * h)
            else:
                ny = y1
            ny = min(ny, y1)
            row = np.nonzero(blob[max(y0, ny - 2):ny + 1])[1]
            if ny - top > 0.08 * h and len(row):
                return float(row.mean()), float(ny)
    if fallback_y is not None:
        return cx, float(fallback_y)
    return cx, float(top + 0.17 * h)


def _cut(art, nx, ny, h, ov):
    """Head silhouette above the neck line, connected to the head, feathered over 2*ov rows."""
    a = art[..., 3].astype(np.float32) / 255.0
    yy, xx = np.mgrid[0:a.shape[0], 0:a.shape[1]]
    region = (yy <= ny + ov) & (np.abs(xx - nx) <= 0.22 * h) & (a > 0.05)
    lab, n = ndi.label(region)
    if n > 1:
        top_lab = lab[np.nonzero(region)[0].min(), :]
        ids = set(top_lab[top_lab > 0].tolist())
        sizes = ndi.sum(region, lab, range(1, n + 1))
        keep_ids = ids | {1 + int(np.argmax(sizes))}
        region = np.isin(lab, list(keep_ids))
    ramp = np.clip((ny + ov - yy) / float(2 * ov), 0.0, 1.0)
    return region.astype(np.float32) * ramp


def _gold(rgb):
    r, g, b = [rgb[..., i].astype(np.float32) for i in range(3)]
    mx, mn = np.maximum(np.maximum(r, g), b), np.minimum(np.minimum(r, g), b)
    sat = (mx - mn) / np.maximum(mx, 1)
    return (r > 150) & (g > 110) & (b < g - 35) & (sat > 0.42) & (mx > 160)


def _skin_from_art(art, cut):
    """Skin ratio mask read off the head's own pixels (some layers' painted skin masks are offset from
    their art, which tinted a ghost face beside the real one)."""
    rgb = art[..., :3].astype(np.float32)
    r, g, b = rgb[..., 0], rgb[..., 1], rgb[..., 2]
    lum = rgb.mean(-1)
    mx = np.maximum(np.maximum(r, g), b)
    sat = (mx - np.minimum(np.minimum(r, g), b)) / np.maximum(mx, 1)
    m = (cut > 0.05) & (art[..., 3] > 100) & (r > g) & (g > b - 6) & (r - b > 22) & (r > 105) & (lum > 80) & (sat < 0.62)
    m = ndi.binary_closing(m, iterations=2) & (cut > 0.05) & (art[..., 3] > 60)
    m = ndi.binary_opening(m, iterations=1)
    out = np.zeros(art.shape, np.uint8)
    if not m.any():
        return out
    base = float(np.median(lum[m])) or 150.0
    gr = np.clip(lum / base * 128.0, 0, 255).astype(np.uint8)
    out[..., 0] = out[..., 1] = out[..., 2] = gr
    soft = ndi.distance_transform_edt(m)
    out[..., 3] = np.where(m, np.clip(soft / 1.5, 0.3, 1.0) * 255 * cut, 0).astype(np.uint8)
    return out


def _hair_mask(art, skin, cut):
    sk = skin[..., 3] > 60 if skin is not None else np.zeros(cut.shape, bool)
    m = (cut > 0.05) & ~sk & ~_gold(art[..., :3]) & (art[..., 3] > 100)
    m = ndi.binary_opening(m, iterations=1)
    out = np.zeros(art.shape, np.uint8)
    if not m.any():
        return out
    lum = art[..., :3].astype(np.float32).mean(-1)
    base = float(np.median(lum[m])) or 40.0
    g = np.clip(lum / base * 128.0, 0, 255).astype(np.uint8)
    out[..., 0] = out[..., 1] = out[..., 2] = g
    soft = ndi.distance_transform_edt(m)
    out[..., 3] = np.where(m, np.clip(soft / 1.5, 0.3, 1.0) * 255 * cut, 0).astype(np.uint8)
    return out


def _save(arr, path):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    Image.fromarray(arr, "RGBA").save(path, optimize=True)


NECK_BAND = {"male": (0.148, 0.172), "female": (0.140, 0.158)}
TAGS = {"1x": 0.5, "2x": 1.0, "4x": 2.0}


def _layer_points(sex, layer, tag="2x"):
    """Per facing (native px of this scale): top, cx, h, neck. n reuses the s neck height (same idle body)."""
    pts = {}
    d = os.path.join(ROOT, sex, tag, layer)
    s_neck = None
    for f in ("s", "e", "n"):
        art = _frame0(os.path.join(d, f"idle_{f}.png"))
        if art is None:
            continue
        skin = _frame0(os.path.join(d, f"idle_{f}_skin.png"))
        if skin is not None and skin.shape != art.shape:
            skin = None
        top, cx, h = _head(art[..., 3])
        nx, ny = _neck(art, skin, f, fallback_y=s_neck if f != "s" else None)
        # skin-based necks wander to dress necklines / beards: keep the neck within the painted
        # figures' head-to-height band (measured on the clean villager / armour figures)
        lo, hi = NECK_BAND["female" if sex == "female" else "male"]
        ny = min(max(ny, top + lo * h), top + hi * h)
        if f == "s":
            s_neck = ny
        if f == "e" and s_neck is not None and abs(ny - s_neck) > 0.06 * h:
            ny = s_neck
        if f == "n":
            # back view: join at the nape (collars sit high at the back); the figure's own collar stays
            ny = top + 0.72 * (ny - top)
        pts[f] = {"top": top, "cx": round(cx, 1), "h": h, "neck": [round(nx, 1), round(ny, 1)],
                  "ov": max(2, int(0.018 * h))}
    return pts, d


def build():
    meta = {"version": 2, "tags": TAGS, "faces": {}, "targets": {}}
    for sex, rows in FACES.items():
        meta["faces"][sex] = []
        for fid, name, layer in rows:
            entry = {"id": fid, "name": name, "layer": layer, "points": {}}
            for tag in TAGS:
                pts, d = _layer_points(sex, layer, tag)
                if len(pts) < 3:
                    continue
                for f in FACINGS:
                    p = pts[f]
                    art = _frame0(os.path.join(d, f"idle_{f}.png"))
                    skin = _frame0(os.path.join(d, f"idle_{f}_skin.png"))
                    if skin is not None and skin.shape != art.shape:
                        skin = None
                    cut = _cut(art, p["neck"][0], p["neck"][1], p["h"], p["ov"])
                    # bottom of the cut: drop cool collar fabric (purple / blue ruffs); hair and skin stay
                    yy = np.arange(art.shape[0])[:, None]
                    low = yy > p["neck"][1] - 4 * p["ov"]
                    r, g, b = [art[..., i].astype(np.int32) for i in range(3)]
                    cool = (b > g + 5) & (b >= r - 6)
                    if f == "n":                     # back view: dark nape hair shades cool; only clear purple
                        cool = (b > g + 10) & (b > r + 4)
                    cut = np.where(low & cool, 0.0, cut)
                    # under the neck line only the neck itself joins (no shoulders / collar spread)
                    xx = np.arange(art.shape[1])[None, :]
                    wide = (yy > p["neck"][1]) & (np.abs(xx - p["neck"][0]) > 0.055 * p["h"])
                    cut = np.where(wide, 0.0, cut)
                    head = art.copy()
                    head[..., 3] = (art[..., 3].astype(np.float32) * cut).astype(np.uint8)
                    base = os.path.join(OUT, sex, fid, tag)
                    _save(head, os.path.join(base, f"head_{f}.png"))
                    sk = _skin_from_art(art, cut)
                    _save(sk, os.path.join(base, f"skin_{f}.png"))
                    _save(_hair_mask(art, sk, cut), os.path.join(base, f"hair_{f}.png"))
                entry["points"][tag] = pts
            if "2x" not in entry["points"]:
                print("skip face (missing 2x idle)", sex, fid)
                continue
            meta["faces"][sex].append(entry)
            print("face", sex, fid, {t: {f: v["neck"] for f, v in p.items()} for t, p in entry["points"].items()})
    # targets: every whole-figure layer that can carry a face (outfits + bare-head armour)
    for sex in FACES:
        for d2 in sorted(glob.glob(os.path.join(ROOT, sex, "2x", "*"))):
            layer = os.path.basename(d2)
            if not (layer.endswith("_bh_hd") or (layer.startswith("outfit_") and layer.endswith("_hd"))):
                continue
            tgt = {}
            for tag in TAGS:
                pts, d = _layer_points(sex, layer, tag)
                if len(pts) < 3:
                    continue
                for f in FACINGS:
                    p = pts[f]
                    art = _frame0(os.path.join(d, f"idle_{f}.png"))
                    cut = _cut(art, p["neck"][0], p["neck"][1], p["h"], p["ov"])
                    yy = np.mgrid[0:art.shape[0], 0:art.shape[1]][0]
                    m = ndi.binary_dilation(cut > 0.5, iterations=max(1, int(2 * TAGS[tag]))) & (yy <= p["neck"][1] - p["ov"])
                    er = np.zeros(art.shape, np.uint8)
                    er[..., 3] = np.maximum((m * 255).astype(np.uint8), (np.clip(cut * 1.6, 0, 1) * 255).astype(np.uint8))
                    er[..., :3] = 255
                    _save(er, os.path.join(OUT, "targets", sex, layer, tag, f"erase_{f}.png"))
                tgt[tag] = pts
            if tgt:
                meta["targets"][f"{sex}/{layer}"] = tgt
    with open(os.path.join(OUT, "faces.json"), "w") as fh:
        json.dump(meta, fh, indent=1)
    print("targets", len(meta["targets"]))
    # the King / Queen faces are repainted crown-free and their crowns split off (tools/build_royal_faces.py)
    import build_royal_faces
    build_royal_faces.build()


if __name__ == "__main__":
    build()
