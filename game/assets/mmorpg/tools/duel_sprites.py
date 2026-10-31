"""Cut painted duel pose sheets into per-state sprite frames.

Usage (needs rembg + cv2, e.g. /workspace/.rembg/bin/python):
    python tools/duel_sprites.py SHEET_DIR [ids...]
SHEET_DIR holds <id>_sheet.jpg (5 poses in a row: idle attack block dodge hit;
hero ids face right, boss ids face left).  Frames are written to
client/assets/castle_realm/arena/duel_sprites/<id>/<state>.png, all cropped to
one shared top..baseline so jumps/crouches keep their offset (feet of grounded
poses sit on the bottom edge).  Prompts: tools/duel_sprite_prompts.md.
Re-run on a new player_hd: python tools/duel_hero_ref.py REFDIR, regenerate the
hero sheets with those refs, then rerun this script.
"""
import os, sys
import numpy as np
from PIL import Image
import cv2
from rembg import remove, new_session

STATES = ["idle", "attack", "block", "dodge", "hit"]
OUT_H = 380
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DST = os.path.join(ROOT, "client/assets/castle_realm/arena/duel_sprites")
IDS = ["hero_sword", "hero_axe", "hero_bow", "varro", "brutus", "crixus",
       "sabina", "ignatius", "unbroken"]


def _main_only(mk, near=14):
    """Keep the figure blob plus pieces touching it (bow strings, sword tips); drop
    stray weapon tips from the neighbouring pose."""
    n, lab, st, _ = cv2.connectedComponentsWithStats(mk.astype(np.uint8), 8)
    if n <= 2:
        return mk
    main = 1 + int(np.argmax(st[1:, cv2.CC_STAT_AREA]))
    grow = cv2.dilate((lab == main).astype(np.uint8), np.ones((near * 2 + 1, near * 2 + 1), np.uint8))
    keep = set(np.unique(lab[grow > 0])) - {0}
    return np.isin(lab, list(keep))


def cut(path, sess):
    img = Image.open(path).convert("RGB")
    rgba = np.array(remove(img, session=sess, post_process_mask=True))
    a = rgba[:, :, 3]
    h, w = a.shape
    m = (a > 40).astype(np.uint8)
    # drop small blobs (labels, specks)
    n, lab, st, _ = cv2.connectedComponentsWithStats(m, 8)
    if n > 1:
        big = st[1:, cv2.CC_STAT_AREA].max()
        for i in range(1, n):
            if st[i, cv2.CC_STAT_AREA] < big * 0.04:
                a[lab == i] = 0
    rgba[:, :, 3] = a
    col = (a > 40).sum(0).astype(float)
    cuts = [0]
    for k in range(1, 5):
        lo, hi = int(w * (k / 5 - 0.08)), int(w * (k / 5 + 0.08))
        cuts.append(lo + int(np.argmin(col[lo:hi])))
    cuts.append(w)
    m = (a > 40).astype(np.uint8)
    n, lab, st, cen = cv2.connectedComponentsWithStats(m, 8)
    owner = np.full(n, -1)
    seg_of = lambda cx: int(np.searchsorted(cuts, cx, side="right") - 1)
    mains = {}
    for i in range(1, n):
        if st[i, cv2.CC_STAT_WIDTH] > 1.6 * w / 5:
            continue  # merged figures: fall back to the column cut
        k = seg_of(cen[i][0])
        if k not in mains or st[i, cv2.CC_STAT_AREA] > st[mains[k], cv2.CC_STAT_AREA]:
            mains[k] = i
    dist = {k: cv2.distanceTransform((lab != i).astype(np.uint8), cv2.DIST_L2, 3) for k, i in mains.items()}
    for i in range(1, n):
        if st[i, cv2.CC_STAT_WIDTH] > 1.6 * w / 5:
            continue
        if i in mains.values():
            owner[i] = [k for k, j in mains.items() if j == i][0]
            continue
        pts = lab == i   # loose piece (axe head, sword tip): give it to the nearest body
        owner[i] = min(dist, key=lambda k: dist[k][pts].min())
    masks = []
    for k in range(5):
        mk = np.isin(lab, np.where(owner == k)[0])
        merged = np.isin(lab, np.where((owner == -1) & (np.arange(n) > 0))[0])
        colm = np.zeros_like(mk); colm[:, cuts[k]:cuts[k + 1]] = True
        mk = mk | (merged & colm)
        masks.append(_main_only(mk))
    rows = np.where(np.any(masks, axis=(0, 2)))[0]
    top = rows.min()
    segs = [np.where(mk.any(1))[0].max() for mk in masks]
    base = max(int(np.median(segs)), segs[0])
    frames = []
    for k, mk in enumerate(masks):
        f = rgba.copy(); f[:, :, 3] = np.where(mk, a, 0)
        xs = np.where(mk.any(0))[0]
        sub = f[top:max(base, segs[k]) + 1, xs.min():xs.max() + 1]
        frames.append(Image.fromarray(sub))
    sc = OUT_H / float(base - top + 1)
    return [f.resize((max(1, int(f.width * sc)), max(1, int(f.height * sc))),
                     Image.LANCZOS) for f in frames]


def main():
    sd = sys.argv[1]
    ids = sys.argv[2:] or IDS
    sess = new_session("isnet-general-use")
    for i in ids:
        p = os.path.join(sd, i + "_sheet.jpg")
        if not os.path.exists(p):
            print("skip", i); continue
        od = os.path.join(DST, i); os.makedirs(od, exist_ok=True)
        for s, f in zip(STATES, cut(p, sess)):
            f.save(os.path.join(od, s + ".png"))
        print("ok", i)


if __name__ == "__main__":
    main()
