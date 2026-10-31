"""Crown-free King / Queen faces + their crowns as separate overlay art (David, 29 Oct 2026).
Source: the original painted royal heads (kept in faces/_src/royal/orig) and painted crown-free hair tops
(faces/_src/royal/<face>_<facing>_gen.jpg, same framing as boxes.json). Output:
  faces/<sex>/<face>/<tag>/head|hair|skin_<facing>.png   crown-free head (face pixels untouched)
  crowns/<crown>/<tag>/crown_<facing>.png + crowns/crowns.json   the crown, anchored to the head top
Run: python3 tools/build_royal_faces.py"""
import json
import os
import shutil

import numpy as np
from PIL import Image, ImageFilter

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ART = os.path.join(ROOT, "..", "player_hd", "assets")
FACES = os.path.join(ART, "faces")
SRC = os.path.join(FACES, "_src", "royal")
CROWNS = os.path.join(ART, "crowns")
ROYAL = (("male", "king", "kings_crown", "King's Crown"), ("female", "queen", "queens_crown", "Queen's Crown"))
TAGS = {"1x": 0.25, "2x": 0.5, "4x": 1.0}      # relative to the 4x art


def _orig(sex, fid, tag, kind, facing):
    keep = os.path.join(SRC, "orig", sex, fid, tag)
    os.makedirs(keep, exist_ok=True)
    p = os.path.join(keep, f"{kind}_{facing}.png")
    if not os.path.exists(p):           # first run: keep the painted original as the source
        shutil.copy(os.path.join(FACES, sex, fid, tag, f"{kind}_{facing}.png"), p)
    return np.array(Image.open(p).convert("RGBA")).astype(np.float32)


def _gold(a):
    r, g, b, al = a[..., 0], a[..., 1], a[..., 2], a[..., 3]
    rr = np.maximum(r, 1)
    return (al > 20) & (r > 70) & ((r - b) / rr > 0.5) & (g / rr > 0.72) & (g > b + 15)


def head_metrics(alpha):
    """(top, cx, width) of a head from its alpha: top row, centre and width of the upper skull."""
    rows = np.where((alpha > 128).any(1))[0]
    if not len(rows):
        return None
    top, bot = int(rows[0]), int(rows[-1])
    band = alpha[top:top + max(2, int((bot - top) * 0.25))] > 128
    xs = np.where(band.any(0))[0]
    return top, float(xs.mean()), float(xs[-1] - xs[0] + 1)


def _pts(sex, fid):
    m = json.load(open(os.path.join(FACES, "faces.json")))
    return next(f for f in m["faces"][sex] if f["id"] == fid)["points"]


def _bbox(alpha):
    ys = np.where((alpha > 100).any(1))[0]
    xs = np.where((alpha > 100).any(0))[0]
    return xs[0], ys[0], xs[-1] + 1, ys[-1] + 1


def _to_tag(arr, ref_big, ref_small, size, mask=False):
    """4x art -> another scale folder's own painting: registered on the two original (crowned) heads'
    bounding boxes, which show the same painting, so the new top lands exactly on the small head."""
    bx, sx_ = _bbox(ref_big[..., 3]), _bbox(ref_small[..., 3])
    k = ((sx_[2] - sx_[0]) / float(bx[2] - bx[0]) + (sx_[3] - sx_[1]) / float(bx[3] - bx[1])) / 2
    ox = (sx_[0] + sx_[2]) / 2 - (bx[0] + bx[2]) / 2 * k
    oy = sx_[3] - bx[3] * k
    im = Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8))
    return np.array(im.transform(size, Image.AFFINE, (1 / k, 0, -ox / k, 0, 1 / k, -oy / k),
                                 resample=Image.BILINEAR if mask else Image.BICUBIC)).astype(np.float32)


def build():
    boxes = json.load(open(os.path.join(SRC, "boxes.json")))
    meta = {"version": 1, "crowns": {}}
    for sex, fid, cid, name in ROYAL:
        P = _pts(sex, fid)
        meta["crowns"][cid] = {"name": name, "sex": sex, "anchor": {}}
        for facing in "sen":
            a4 = _orig(sex, fid, "4x", "head", facing)
            box = boxes[f"{fid}_{facing}"]
            S = box[2] - box[0]
            gen = Image.open(os.path.join(SRC, f"{fid}_{facing}_gen.jpg")).convert("RGB").resize((S, S), Image.LANCZOS)
            g = np.array(gen).astype(np.float32)
            key = (g[..., 1] > 150) & (g[..., 0] < 120) & (g[..., 2] < 120)
            ga = np.where(key, 0, 255).astype(np.float32)
            ga = np.array(Image.fromarray(ga.astype(np.uint8)).filter(ImageFilter.MinFilter(3)))
            full_g = np.zeros_like(a4)
            H, W = a4.shape[:2]
            y0, x0 = box[1], box[0]
            sl = (slice(max(0, y0), min(H, y0 + S)), slice(max(0, x0), min(W, x0 + S)))
            gy, gx = sl[0].start - y0, sl[1].start - x0
            hh, ww = sl[0].stop - sl[0].start, sl[1].stop - sl[1].start
            full_g[sl][..., :3] = g[gy:gy + hh, gx:gx + ww]
            full_g[sl][..., 3] = ga[gy:gy + hh, gx:gx + ww]
            # de-spill green on the generated fringe
            gg = full_g[..., 1]
            full_g[..., 1] = np.minimum(gg, (full_g[..., 0] + full_g[..., 2]) / 2 + 12)
            # the crown is where the crown-free painting differs from the original, from the top down to
            # the rim (the first row where they agree again); dark hair between the points stays hair
            df = ((np.abs(a4[..., :3] - full_g[..., :3]).sum(2) > 110) | (full_g[..., 3] < 128)) & (a4[..., 3] > 100)
            frac = df.sum(1) / np.maximum(1, (a4[..., 3] > 100).sum(1))
            rows = np.where(a4[..., 3].max(1) > 100)[0]
            if not len(rows):
                continue
            c_top = int(rows[0])
            c_bot = c_top
            for y in range(c_top, H):
                if frac[y] < 0.1:
                    break
                c_bot = y
            crown = df.copy()
            crown[:c_top] = False
            crown[c_bot + 1:] = False
            crown &= ~((a4[..., :3].mean(2) < 55) & (full_g[..., 3] > 128))
            cm = Image.fromarray((crown * 255).astype(np.uint8)).filter(ImageFilter.MaxFilter(5))
            cm = np.array(cm) > 0
            cm[c_bot + 3:] = False
            # region to repaint: the crown and everything above the crown's lower rim
            region = cm.copy()
            region[:c_bot + 1] |= True
            region[c_bot + 1:] = cm[c_bot + 1:]
            # soft blend into the original over a few rows below the rim
            wgt = np.zeros(a4.shape[:2], np.float32)
            wgt[region] = 1.0
            wgt = np.array(Image.fromarray((wgt * 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(1.5))) / 255.0
            wgt[region] = 1.0
            new4 = a4 * (1 - wgt[..., None]) + full_g * wgt[..., None]
            crown_rgba = a4.copy()
            crown_rgba[..., 3] = np.where(cm, a4[..., 3], 0)
            hair_mask = _orig(sex, fid, "4x", "hair", facing)[..., 3]
            skin_mask = _orig(sex, fid, "4x", "skin", facing)[..., 3]
            # repainted top is hair (dark, not skin-toned) unless it was the face
            dark = (full_g[..., :3].mean(2) < 110) & (full_g[..., 3] > 20)
            hair_new = np.where(region, np.where(dark, full_g[..., 3], 0), hair_mask)
            skin_new = np.where(region & ~dark, np.minimum(skin_mask, full_g[..., 3]), skin_mask)
            skin_new = np.where(cm, 0, skin_new)
            for tag in TAGS:
                d = os.path.join(FACES, sex, fid, tag)
                cd = os.path.join(CROWNS, cid, tag)
                os.makedirs(cd, exist_ok=True)
                small = _orig(sex, fid, tag, "head", facing)
                size = (small.shape[1], small.shape[0])
                if tag == "4x":
                    w2, big, crn = wgt, new4, crown_rgba
                    hn, sn = hair_new, skin_new
                else:
                    w2 = _to_tag(wgt * 255, a4, small, size, mask=True) / 255.0
                    big = _to_tag(new4, a4, small, size)
                    crn = _to_tag(crown_rgba, a4, small, size)
                    hn = _to_tag(hair_new, a4, small, size, mask=True)
                    sn = _to_tag(skin_new, a4, small, size, mask=True)
                if w2.ndim == 3:
                    w2 = w2[..., 0]
                if tag != "4x":   # the smaller paintings sit a touch differently: cover their crown fully
                    w2 = np.array(Image.fromarray((w2 * 255).astype(np.uint8)).filter(ImageFilter.MaxFilter(3))) / 255.0
                    full_rows = np.where((w2 > 0.5).mean(1) > 0.6)[0]   # rows wholly above the rim at 4x
                    if len(full_rows):
                        w2[:full_rows[-1] + 2] = 1.0
                head = small * (1 - w2[..., None]) + big * w2[..., None]
                Image.fromarray(np.clip(head, 0, 255).astype(np.uint8)).save(os.path.join(d, f"head_{facing}.png"))
                for kind, arr in (("hair", hn), ("skin", sn)):
                    base = _orig(sex, fid, tag, kind, facing)
                    o = base.copy()
                    o[..., 3] = base[..., 3] * (1 - w2) + arr * w2
                    if kind == "skin":
                        o[..., 3] = np.where(crn[..., 3] > 40, 0, o[..., 3])
                    o[..., :3] = np.where(o[..., 3:4] > 0, np.maximum(o[..., :3], 0), 0)
                    Image.fromarray(np.clip(o, 0, 255).astype(np.uint8)).save(os.path.join(d, f"{kind}_{facing}.png"))
                Image.fromarray(np.clip(crn, 0, 255).astype(np.uint8)).save(os.path.join(cd, f"crown_{facing}.png"))
                mt = head_metrics(np.clip(head[..., 3], 0, 255))
                meta["crowns"][cid]["anchor"].setdefault(facing, {})[tag] = {
                    "top": mt[0], "cx": mt[1], "w": mt[2], "face": fid}
    os.makedirs(CROWNS, exist_ok=True)
    json.dump(meta, open(os.path.join(CROWNS, "crowns.json"), "w"), indent=1)
    print("built", list(meta["crowns"]))


if __name__ == "__main__":
    build()
