"""Per-frame head anchors for action strips, so the helmet overlay stays on mid-swing (David, 23 Oct 2026).

A raised weapon breaks the head-top anchor, so each action frame's head is found by matching the idle head
(hair + face, guided by the _skin face mask) inside a window around where the head sits relative to the feet.
Writes player_hd/assets/helmets/action_anchors.json:
  {"<sex>/<layer>/<anim>_<facing>": [[top, cx, h], ...]}   as fractions of the cell height / width / height.
Run:  python3 tools/helm_anchors.py
"""
import json
import os
import sys

import numpy as np
import pygame

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "player_hd", "assets")
OUT = os.path.join(ROOT, "helmets", "action_anchors.json")
ACTIONS = ("melee", "melee_sword", "melee_axe", "chop", "mine", "fish", "ranged")   # no helmet anchors for death (falls over)


CELL_W = None


def frames(path, cell_h=None):
    s = pygame.image.load(path)
    w, h = s.get_size()
    cw = CELL_W or h
    n = max(1, w // cw)
    rgb = pygame.surfarray.array3d(s).transpose(1, 0, 2).astype(np.float32)
    a = pygame.surfarray.array_alpha(s).T.astype(np.float32) / 255.0
    return [(rgb[:, i * cw:(i + 1) * cw], a[:, i * cw:(i + 1) * cw]) for i in range(n)], cw, h


def n_frames(meta_strip, path):
    s = pygame.image.load(path)
    return s.get_size()


def head_of(alpha):
    m = alpha > 0.5
    rows = np.where(m.any(1))[0]
    top, bot = int(rows[0]), int(rows[-1])
    h = bot - top
    band = m[top + int(0.02 * h): top + int(0.07 * h) + 1]
    xs = np.nonzero(band)[1]
    lo = max(0, bot - max(2, int(0.04 * h)))
    fx = float(np.nonzero(m[lo:bot + 1])[1].mean())
    return top, float(xs.mean()), h, fx, bot


def match(tpl_rgb, tpl_a, img_rgb, img_a, xlim, ylim, want_map=False):
    """Best (score, x, y) of the head template (RGB weighted by its alpha, plus an alpha-shape term)."""
    from numpy.lib.stride_tricks import sliding_window_view as sw
    th, tw = tpl_a.shape
    H, W = img_a.shape
    xa, xb = max(0, int(xlim[0])), min(W - tw, int(xlim[1]))
    ya, yb = max(0, int(ylim[0])), min(H - th, int(ylim[1]))
    if xb < xa or yb < ya:
        return None
    R = sw(img_rgb[ya:yb + th, xa:xb + tw], (th, tw), axis=(0, 1))     # ny,nx,3,th,tw
    A = sw(img_a[ya:yb + th, xa:xb + tw], (th, tw), axis=(0, 1))       # ny,nx,th,tw
    T = tpl_rgb.transpose(2, 0, 1)[None, None]
    wa = tpl_a[None, None]
    d1 = (((R - T) ** 2).sum(2) * wa).sum((2, 3)) / (tpl_a.sum() * 3 + 1e-6)
    d2 = ((A - wa) ** 2).sum((2, 3)) / tpl_a.size
    d = d1 + 4000.0 * d2
    if want_map:
        return d, xa, ya
    k = int(np.argmin(d))
    y, x = divmod(k, d.shape[1])
    return float(d.flat[k]), xa + x, ya + y


def anchors_for(idle_path, act_path, cell_h):
    idle, icw, ih = frames(idle_path, cell_h)
    act, acw, ah = frames(act_path, cell_h)
    sk = lambda p: [f[1] for f in frames(p, cell_h)[0]] if os.path.isfile(p) else None
    iskin = sk(idle_path[:-4] + "_skin.png")
    askin = sk(act_path[:-4] + "_skin.png")
    irgb, ia = idle[0]
    top, hcx, h, ifx, ibot = head_of(ia)
    # head template: crown down to the chin (RGB + alpha; the _skin masks of the action strips are too broken up
    # to track the face alone). The head is searched only in the top 30% of the figure., centred on the head column
    tw = max(6, int(0.11 * h)); th = max(6, int(0.13 * h))
    x0 = int(round(hcx - tw / 2)); y0 = top
    t_rgb = irgb[y0:y0 + th, x0:x0 + tw]; t_a = ia[y0:y0 + th, x0:x0 + tw]
    # rotated / scaled copies of the head template, for bent and turned heads; each keeps where its crown point
    # (top centre of the upright template) lands, so the anchor follows the rotation
    from scipy import ndimage
    variants = []
    pad = int(0.35 * max(tw, th))
    big_rgb = np.zeros((th + 2 * pad, tw + 2 * pad, 3), np.float32); big_a = np.zeros(big_rgb.shape[:2], np.float32)
    big_rgb[pad:pad + th, pad:pad + tw] = t_rgb; big_a[pad:pad + th, pad:pad + tw] = t_a
    cy, cx = (th + 2 * pad) / 2.0, (tw + 2 * pad) / 2.0
    for ang in (0, -15, 15, -30, 30, -45, 45, -60, 60):
        r_a = ndimage.rotate(big_a, ang, reshape=False, order=1)
        r_rgb = np.stack([ndimage.rotate(big_rgb[..., c], ang, reshape=False, order=1) for c in range(3)], -1)
        ys, xs = np.nonzero(r_a > 0.05)
        if not len(ys):
            continue
        y0r, y1r, x0r, x1r = ys.min(), ys.max() + 1, xs.min(), xs.max() + 1
        t = np.radians(ang)
        px, py = (pad + tw / 2.0) - cx, pad - cy           # crown point, relative to the centre
        qx = cx + px * np.cos(t) + py * np.sin(t)
        qy = cy - px * np.sin(t) + py * np.cos(t)
        variants.append((ang, r_rgb[y0r:y1r, x0r:x1r], r_a[y0r:y1r, x0r:x1r], qx - x0r, qy - y0r))
    # candidates per frame: the best few distinct head positions over all template variants
    per = []
    sep = 0.07 * h
    for rgb, a in act:
        try:
            ftop, _c, _h, fx, bot = head_of(a)
        except IndexError:
            per.append([]); continue
        ex = x0 + (fx - ifx)
        cands = []
        for ang, vr, va, qx, qy in variants:
            r = match(vr, va, rgb, a, (ex - 0.4 * h, ex + 0.4 * h), (ftop - 4, ftop + 0.3 * h), want_map=True)
            if r is None:
                continue
            d, xa, ya = r
            d = d * (1.0 + abs(ang) / 300.0)
            flat = np.argsort(d, axis=None)[:200]
            for k in flat:
                yy, xx = divmod(int(k), d.shape[1])
                cands.append((float(d.flat[k]), xa + xx + qx, ya + yy + qy))
        cands.sort()
        keep = []
        for c in cands:
            if all((c[1] - k[1]) ** 2 + (c[2] - k[2]) ** 2 > sep * sep for k in keep):
                keep.append(c)
            if len(keep) >= 6:
                break
        per.append(keep)
    # smooth path through the candidates (heads move smoothly frame to frame; strips loop)
    lam = 4.0 / max(1.0, (0.02 * h) ** 2) * 100.0
    n = len(per)
    idx = [i for i in range(n) if per[i]]
    choice = {}
    if idx:
        cost = {(idx[0], c): per[idx[0]][c][0] for c in range(len(per[idx[0]]))}
        back = {}
        for pi, i in zip(idx, idx[1:]):
            for c, cc in enumerate(per[i]):
                best = None
                for p_, pc in enumerate(per[pi]):
                    mv = (cc[1] - pc[1]) ** 2 + (cc[2] - pc[2]) ** 2
                    v = cost[(pi, p_)] + lam * mv / 100.0
                    if best is None or v < best[0]:
                        best = (v, p_)
                cost[(i, c)] = best[0] + cc[0]
                back[(i, c)] = best[1]
        last = idx[-1]
        c = min(range(len(per[last])), key=lambda c: cost[(last, c)])
        for i in reversed(idx):
            choice[i] = c
            if i != idx[0]:
                c = back[(i, c)]
    out = []
    for i in range(n):
        if i not in choice:
            out.append(None); continue
        _d, x, y = per[i][choice[i]]
        out.append([round(y / ah, 4), round(x / acw, 4), round(h / ah, 4)])
    return out


def main():
    os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
    pygame.init()
    global CELL_W
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "client"))
    import player_hd_client as P
    CELL_W = int(P._load_meta().get("canvas", {}).get("2x", [144, 144])[0])
    res = {}
    for sex in ("male", "female"):
        base = os.path.join(ROOT, sex, "2x")
        for layer in sorted(os.listdir(base)):
            if not (layer.startswith("outfit_") or (layer.startswith("armour_") and layer.endswith("_bh_hd"))):
                continue
            d = os.path.join(base, layer)
            for fn in sorted(os.listdir(d)):
                if not fn.endswith(".png") or fn.endswith(("_skin.png", "_tint.png", "_hair.png")):
                    continue
                stem = fn[:-4]
                anim, facing = stem.rsplit("_", 1)
                if anim not in ACTIONS:
                    continue
                idle = os.path.join(d, f"idle_{facing}.png")
                if not os.path.isfile(idle):
                    continue
                ch = pygame.image.load(idle).get_height()
                res[f"{sex}/{layer}/{stem}"] = anchors_for(idle, os.path.join(d, fn), ch)
                print(sex, layer, stem, len(res[f"{sex}/{layer}/{stem}"]), flush=True)
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    json.dump(res, open(OUT, "w"))
    print("wrote", OUT, len(res))


if __name__ == "__main__":
    main()
