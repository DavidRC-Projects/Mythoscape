"""Track each figure's own head through every animation frame (position + tilt), so a chosen face rides
the body exactly: a leaning chop/axe swing tilts the new head with the old one instead of leaving it
floating upright. Writes player_hd/assets/faces/targets/track.json:
  {"<sex>/<layer>/<anim>_<facing>": [[dx, dy, deg, size], ...]}   (2x native px, neck-relative to idle frame 0;
   deg = counter-clockwise tilt about the neck)."""
import os, sys, json
import numpy as np
from PIL import Image
from scipy.signal import fftconvolve

sys.path[:0] = [os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "client"),
                os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "server")]
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
import pygame

HERE = os.path.dirname(os.path.abspath(__file__))
ASSETS = os.path.join(HERE, "..", "..", "player_hd", "assets")
FACES = os.path.join(ASSETS, "faces")
OUT = os.path.join(FACES, "targets", "track.json")
R = 26                                   # search radius (2x px) around the frame's head
ANGLES = list(range(-50, 51))
COARSE = set(range(-50, 51, 5))


def _strips(sex, layer):
    d = os.path.join(ASSETS, sex, "2x", layer)
    for f in sorted(os.listdir(d)) if os.path.isdir(d) else ():
        b = f[:-4]
        if f.endswith(".png") and not b.endswith(("_hair", "_skin")):
            anim, _, fac = b.rpartition("_")
            if fac in ("s", "e", "n") and not anim.startswith("fx"):    # fx_*: effect layers, no head
                yield anim, fac, os.path.join(d, f)


SKIN_W = 0.0                             # (skin masks of action strips are not reliable enough)


def _feat(img, skin=None):
    a = np.asarray(img.convert("RGBA"), np.float32) / 255.0
    al = a[..., 3:4]
    if skin is None:
        sk = np.zeros_like(al)
    else:
        sk = np.asarray(skin.convert("RGBA").getchannel("A"), np.float32)[..., None] / 255.0
    return np.concatenate([a[..., :3] * al, al * 1.5, sk * SKIN_W], 2)   # colour, silhouette, skin


def _head_box(frame_a, guess_top, guess_cx):
    return guess_top, guess_cx


def _mask_head(path, i, hh, near):
    """The figure's own head from its hair + skin masks: the blob nearest `near` (x, y top guess).
    Returns (top, cx, width) in frame px, or None. Width is the widest row in the blob's upper 60%."""
    from scipy import ndimage
    m = _hs_mask(path, i, hh)
    if m is None or not m.any():
        return None
    lab, n = ndimage.label(ndimage.binary_closing(m, iterations=2))
    best = None
    for j in range(1, n + 1):
        ys, xs = np.where(lab == j)
        if len(ys) < 60:
            continue
        d = np.hypot(xs.mean() - near[0], ys.min() - near[1])
        if best is None or d < best[0]:
            best = (d, ys, xs)
    if best is None or best[0] > 45:
        return None
    _d, ys, xs = best
    top, bot = ys.min(), ys.max()
    up = ys < top + 0.6 * (bot - top + 1)
    rows = {}
    for y, x in zip(ys[up], xs[up]):
        lo, hi = rows.get(y, (x, x))
        rows[y] = (min(lo, x), max(hi, x))
    wid = max(hi - lo + 1 for lo, hi in rows.values())
    return float(top), float(xs[up].mean()), float(wid)


_MASKS = {}


def _hs_mask(path, i, hh):
    m = sk = None
    for suf in ("_hair.png", "_skin.png"):
        q = path[:-4] + suf
        if os.path.exists(q):
            if q not in _MASKS:
                _MASKS[q] = np.asarray(Image.open(q).convert("RGBA").getchannel("A")) > 128
            a = _MASKS[q][:, i * hh:(i + 1) * hh]
            if suf == "_skin":
                sk = a
            m = a if m is None else (m | a)
    if m is not None and sk is not None and sk.any():
        # hair-only blobs that touch no skin are not the head (a dark axe blade painted as hair)
        from scipy import ndimage
        lab, n = ndimage.label(ndimage.binary_dilation(m, iterations=2))
        keep = np.isin(lab, [k for k in range(1, n + 1) if (sk & (lab == k)).sum() >= 20])
        m = m & keep
    return m


def _cover(hs, t, dx, dy):
    """IoU of a placed head template's mask with the figure's own hair/skin pixels near it."""
    ang, T, M, x0, y0, tt, ms = t
    H, W = hs.shape
    X0, Y0 = int(round(x0 + dx)), int(round(y0 + dy))
    th, tw = M.shape
    a0, b0 = max(0, Y0), max(0, X0)
    a1, b1 = min(H, Y0 + th), min(W, X0 + tw)
    if a1 <= a0 or b1 <= b0:
        return 0.0
    mm = M[a0 - Y0:a1 - Y0, b0 - X0:b1 - X0] > 0.3
    hh_ = hs[a0:a1, b0:b1]
    inter = float((mm & hh_).sum())
    # own head pixels left uncovered nearby (a band around the template box) count against it
    pad = 8
    A0, B0, A1, B1 = max(0, a0 - pad), max(0, b0 - pad), min(H, a1 + pad), min(W, b1 + pad)
    near = float(hs[A0:A1, B0:B1].sum())
    return inter / max(1.0, float(mm.sum()) + near - inter)


def _mask_seed(path, i, hh, idle_box, ny, gx, gy):
    """(dx, dy, k) of the head from the mask blob nearest a candidate placement, or None."""
    if not idle_box:
        return None
    nx_top = idle_box[1] + gx
    mb = _mask_head(path, i, hh, (nx_top, idle_box[0] + gy))
    if not mb:
        return None
    k_m = max(0.85, min(1.8, mb[2] / max(1.0, idle_box[2])))
    return mb[1] - idle_box[1], mb[0] + k_m * (ny - idle_box[0]) - ny, k_m


def _try(F, hh, prev, ang, T, M, x0, y0, tt, ms, best):
    th, tw = M.shape
    # window: template box moved by up to R (around the previous frame's offset)
    r = RR[0]
    wx0 = int(max(0, x0 + prev[0] - r)); wy0 = int(max(0, y0 + prev[1] - r))
    wx1 = int(min(hh, x0 + prev[0] + tw + r)); wy1 = int(min(hh, y0 + prev[1] + th + r))
    W = F[wy0:wy1, wx0:wx1]
    if W.shape[0] < th or W.shape[1] < tw:
        return best
    cross = sum(fftconvolve(W[..., c], T[::-1, ::-1, c], mode="valid") for c in range(W.shape[2]))
    f2 = sum(fftconvolve(W[..., c] ** 2, M[::-1, ::-1], mode="valid") for c in range(W.shape[2]))
    ssd = (f2 - 2 * cross + tt) / ms
    ssd += 0.0004 * abs(ang)                       # prefer upright when tied
    yy, xx = np.mgrid[0:ssd.shape[0], 0:ssd.shape[1]]
    ssd += 0.00008 * np.hypot(wx0 + xx - x0 - prev[0], wy0 + yy - y0 - prev[1])   # and near the anchor
    k = np.unravel_index(np.argmin(ssd), ssd.shape)
    v = float(ssd[k])
    if best is None or v < best[0]:
        best = (v, wx0 + k[1] - x0, wy0 + k[0] - y0, ang)
    return best


_SHEETS = {}
RR = [R]
SNAP = 6


def _global(F, temps_half):
    """Best (score, dx, dy, deg) over the whole frame at half resolution (dx/dy in full px)."""
    Fh = F[::2, ::2]
    best = None
    for ang, T, M, x0, y0, tt, ms in temps_half:
        th, tw = M.shape
        cross = sum(fftconvolve(Fh[..., c], T[::-1, ::-1, c], mode="valid") for c in range(Fh.shape[2]))
        f2 = sum(fftconvolve(Fh[..., c] ** 2, M[::-1, ::-1], mode="valid") for c in range(Fh.shape[2]))
        ssd = (f2 - 2 * cross + tt) / ms + 0.0004 * abs(ang)
        k = np.unravel_index(np.argmin(ssd), ssd.shape)
        v = float(ssd[k])
        if best is None or v < best[0]:
            best = (v, (k[1] - x0) * 2.0, (k[0] - y0) * 2.0, ang)
    return best
GOOD = 0.25                              # match error this far above the idle self-match: head hidden, interpolate


def _spikes(res):
    """A lone jump that both neighbours (agreeing with each other) refuse is a mismatch: drop it."""
    out = list(res)
    for i in range(1, len(res) - 1):
        a, v, b = res[i - 1], res[i], res[i + 1]
        if a is None or v is None or b is None:
            continue
        d = lambda p, q: max(abs(p[0] - q[0]), abs(p[1] - q[1]))
        if d(a, b) < 8 and d(v, a) > 12 and d(v, b) > 12:
            out[i] = None
    d = lambda p, q: max(abs(p[0] - q[0]), abs(p[1] - q[1]))
    for i, j, k in ((0, 1, 2), (len(res) - 1, len(res) - 2, len(res) - 3)):
        # the strip's ends: a jump away from the two frames next to it (which agree) is a mismatch too
        if k >= 0 and k < len(res) and None not in (res[i], res[j], res[k]):
            if d(res[j], res[k]) < 8 and d(res[i], res[j]) > 15:
                out[i] = None
    return out


def _fill(res):
    """Frames without a trustworthy match take the line between their nearest matched neighbours."""
    ok = [i for i, v in enumerate(res) if v is not None]
    if not ok:
        return [[0.0, 0.0, 0, 1.0, 0] for _ in res]
    out = []
    for i, v in enumerate(res):
        if v is not None:
            out.append(v)
            continue
        a = max([j for j in ok if j < i], default=None)
        b = min([j for j in ok if j > i], default=None)
        if a is None or b is None:
            out.append(list(res[a if b is None else b])[:4] + [0])
            continue
        t = (i - a) / float(b - a)
        out.append([round(res[a][k] + (res[b][k] - res[a][k]) * t, 2) for k in range(4)] + [0])
    return out
SCORES = []


def _guess(sex, layer, anim, fac, i, path, hh, tp):
    """The anchor-measured head offset of this frame (2x px), the centre of the search."""
    import face_layer as FL
    if not pygame.display.get_init():
        pygame.init(); pygame.display.set_mode((1, 1))
    if path not in _SHEETS:
        _SHEETS[path] = pygame.image.load(path).convert_alpha()
    fr = _SHEETS[path].subsurface((i * hh, 0, hh, hh))
    off = FL._offset(sex, layer, anim, fac, i, fr, tp, hh / 288.0)
    if off is None or abs(off[0]) > 40 or abs(off[1]) > 40:
        return (0.0, 0.0)
    return off


def _on_top(F, temps, dx, dy, ang):
    """A head is the top of the figure: the band just above the matched skull is mostly see-through
    (a torso or shoulder match has the real head above it)."""
    for a, T, M, x0, y0, tt, ms in temps:
        if a == ang:
            cols = np.where(M[:4].max(0) > 0.3)[0]
            if not len(cols):
                return True
            ty0 = int(round(y0 + dy))
            xs = (cols + x0 + int(round(dx))).clip(0, F.shape[1] - 1)
            band = F[max(0, ty0 - 8):max(0, ty0 - 2)][:, xs, 3] / 1.5
            return band.size == 0 or float(band.mean()) < 0.45
    return True


def track_one(sex, layer, fac, tp, strips):
    idle = os.path.join(ASSETS, sex, "2x", layer, f"idle_{fac}.png")
    erase = os.path.join(FACES, "targets", sex, layer, "2x", f"erase_{fac}.png")
    if not (os.path.exists(idle) and os.path.exists(erase)):
        return {}
    sh = Image.open(idle).convert("RGBA")
    h = sh.height
    f0 = sh.crop((0, 0, h, h))
    sp = idle[:-4] + "_skin.png"
    s0 = Image.open(sp).convert("RGBA").crop((0, 0, h, h)) if os.path.exists(sp) else None
    em = Image.open(erase).convert("RGBA").getchannel("A")
    nx, ny = tp["neck"]
    # template: the idle head down to just under the neck line
    m0 = (np.asarray(em, np.float32) / 255.0) * (np.asarray(f0.getchannel("A"), np.float32) / 255.0)
    m0[int(ny) + 4:] = 0
    temps = []
    def make(ang, k=1.0):
        def sc_(im):
            if k == 1.0:
                return im
            big = im.resize((int(round(im.width * k)), int(round(im.height * k))), Image.BILINEAR)
            c = Image.new(im.mode, im.size, 0)
            c.paste(big, (int(round(nx - nx * k)), int(round(ny - ny * k))))
            return c
        ti = sc_(f0).rotate(ang, resample=Image.BILINEAR, center=(nx, ny))
        si = sc_(s0).rotate(ang, resample=Image.BILINEAR, center=(nx, ny)) if s0 is not None else None
        mi = np.asarray(sc_(Image.fromarray((m0 * 255).astype(np.uint8))).rotate(
            ang, resample=Image.BILINEAR, center=(nx, ny)), np.float32) / 255.0
        ys, xs = np.where(mi > 0.05)
        y0, y1, x0, x1 = ys.min(), ys.max() + 1, xs.min(), xs.max() + 1
        T = _feat(ti, si)[y0:y1, x0:x1] * mi[y0:y1, x0:x1, None]
        M = mi[y0:y1, x0:x1]
        return (ang, T, M, x0, y0, float((T * T).sum()), float(M.sum()))

    lim = 50 if fac == "e" else (20 if fac == "s" else 8)      # front/back views lean sideways only a little
    for ang in [a for a in ANGLES if abs(a) <= lim]:
        ti = f0.rotate(ang, resample=Image.BILINEAR, center=(nx, ny))
        si = s0.rotate(ang, resample=Image.BILINEAR, center=(nx, ny)) if s0 is not None else None
        mi = np.asarray(Image.fromarray((m0 * 255).astype(np.uint8)).rotate(ang, resample=Image.BILINEAR,
                                                                              center=(nx, ny)), np.float32) / 255.0
        ys, xs = np.where(mi > 0.05)
        y0, y1, x0, x1 = ys.min(), ys.max() + 1, xs.min(), xs.max() + 1
        T = _feat(ti, si)[y0:y1, x0:x1] * mi[y0:y1, x0:x1, None]
        M = mi[y0:y1, x0:x1]
        temps.append((ang, T, M, x0, y0, float((T * T).sum()), float(M.sum())))
    temps_half = []
    for ang, T, M, x0, y0, tt, ms in temps:
        if ang % 10:
            continue
        Th, Mh = T[(y0 % 2)::2, (x0 % 2)::2], M[(y0 % 2)::2, (x0 % 2)::2]
        temps_half.append((ang, Th, Mh, (x0 + 1) // 2, (y0 + 1) // 2, float((Th * Th).sum()), float(Mh.sum())))
    def halves(tl):
        o = []
        for ang, T, M, x0, y0, tt, ms in tl:
            if ang % 10:
                continue
            Th, Mh = T[(y0 % 2)::2, (x0 % 2)::2], M[(y0 % 2)::2, (x0 % 2)::2]
            o.append((ang, Th, Mh, (x0 + 1) // 2, (y0 + 1) // 2, float((Th * Th).sum()), float(Mh.sum())))
        return o
    BIG = {}                                   # action strips: the whole search again at bigger head sizes
    def big(k):
        if k not in BIG:
            tl = [make(a, k) for a in ANGLES if abs(a) <= lim]
            BIG[k] = (tl, halves(tl))
        return BIG[k]
    idle_box = _mask_head(idle, 0, h, (nx, ny - 25))
    RR[0] = 2
    b0 = None
    for ang, T, M, x0, y0, tt, ms in temps:
        if ang == 0:
            b0 = _try(_feat(f0, s0), h, (0.0, 0.0), ang, T, M, x0, y0, tt, ms, None)
    RR[0] = R
    base = b0[0] if b0 else 0.0
    out = {}
    def above(Fi, hh, b, kk):
        """How opaque the band just over a matched head is (a head is the top of the figure)."""
        ang_, T, M, x0, y0, tt, ms = make(b[3], kk)
        cols = np.where(M[:4].max(0) > 0.3)[0]
        if not len(cols):
            return 0.0
        ty0 = int(round(y0 + b[2]))
        xs = (cols + x0 + int(round(b[1]))).clip(0, hh - 1)
        band = Fi[max(0, ty0 - 10):max(0, ty0 - 2)][:, xs, 3] / 1.5
        return float(band.mean()) if band.size else 0.0

    for anim, f, path in strips:
        if f != fac:
            continue
        st = Image.open(path).convert("RGBA")
        hh = st.height
        skp = path[:-4] + "_skin.png"
        sst = Image.open(skp).convert("RGBA") if (s0 is not None and os.path.exists(skp)) else None
        res = []
        Fs = []
        Gs = []
        prev = (0.0, 0.0)
        for i in range(st.width // hh):
            Fs.append(None)
            F = _feat(st.crop((i * hh, 0, (i + 1) * hh, hh)),
                      sst.crop((i * hh, 0, (i + 1) * hh, hh)) if sst is not None else None)
            Fs[-1] = F
            prev = _guess(sex, layer, anim, fac, i, path, hh, tp)
            Gs.append(tuple(prev))
            guess = prev
            best = None
            def pick(cands):
                nonlocal best
                for ang, T, M, x0, y0, tt, ms in cands:
                    best = _try(F, hh, prev, ang, T, M, x0, y0, tt, ms, best)
            # 1) the whole frame at half size, every 10 degrees; 2) full size near that, every degree
            # back views: the head is all hair, the whole-frame search wanders; stay near the anchor
            g = _global(F, temps_half) if fac != "n" else (0.0, prev[0], prev[1], 0)
            if g is not None:
                prev = (g[1], g[2])
                c = g[3]
                RR[0] = 5 if fac != "n" else 10
                pick([t for t in temps if abs(t[0] - c) <= 6])
                RR[0] = R
            kfull = 1.0
            if fac != "n" and not anim.startswith(("idle", "walk")):
                for kk in (1.25, 1.5):
                    tl, th = big(kk)
                    gk = _global(F, th)
                    if gk is None:
                        continue
                    bk = None
                    RR[0] = 5
                    for t in tl:
                        if abs(t[0] - gk[3]) <= 6 and t[0] % 2 == 0:
                            bk = _try(F, hh, (gk[1], gk[2]), *t, bk)
                    RR[0] = R
                    if bk is not None and (best is None or bk[0] < best[0] - 0.004):
                        best, kfull = bk, kk
            if False:
                pass
            if best is None:
                res.append(None)
                continue
            # 3) the figure leaning toward us draws its head bigger: try a few sizes at that tilt
            kbest = kfull
            if fac != "n":
                a0 = best[3]
                prev2 = (best[1], best[2])
                for k in sorted({round(kfull * m, 3) for m in (0.92, 1.08, 1.16)}):
                    RR[0] = 4
                    nb = _try(F, hh, prev2, a0, *make(a0, k)[1:], None)
                    RR[0] = R
                    if nb is not None and nb[0] < best[0] - 0.004:
                        best, kbest = nb, k
            # 4) action frames: the head blob in the figure's own hair/skin masks gives its size and
            #    place; a match seeded there wins unless clearly worse (template scores favour small heads)
            mk = None
            if idle_box and not anim.startswith(("idle", "walk")) and fac != "n":
                gx = nx + (best[1] if best else guess[0])
                gy = idle_box[0] + (best[2] if best else guess[1])
                mb = _mask_head(path, i, hh, (gx, gy))
                if mb:
                    k_m = max(0.85, min(1.8, mb[2] / max(1.0, idle_box[2])))
                    sdx = mb[1] - idle_box[1]
                    sdy = mb[0] + k_m * (ny - idle_box[0]) - ny
                    bm = None
                    RR[0] = 6
                    for a in [a for a in ANGLES if abs(a) <= lim and a % 2 == 0]:
                        bm = _try(F, hh, (sdx, sdy), *make(a, round(k_m, 2)), bm)
                    RR[0] = R
                    if bm is not None:
                        mk = (bm, k_m)
                        if best is None or bm[0] <= best[0] + 0.03 or \
                                max(abs(bm[1] - best[1]), abs(bm[2] - best[2])) > 10:
                            best, kbest = bm, round(k_m, 2)
            _v, dx, dy, ang = best
            SCORES.append((round(_v, 4), f'{layer} {anim}_{fac}#{i}', prev))
            prev = (dx, dy)
            ok = (mk is not None and best is mk[0]) or (_v - base <= GOOD and abs(dx) <= 48 and abs(dy) <= 48)
            if ok and mk is None and guess != (0.0, 0.0) and max(abs(dx - guess[0]), abs(dy - guess[1])) > 20:
                ok = False                       # far from the measured anchor: not trustworthy
            if ok and guess != (0.0, 0.0) and max(abs(dx - guess[0]), abs(dy - guess[1])) > 15 \
                    and above(F, hh, best, kbest) > 0.35:
                ok = False                       # far from the anchor with the figure going on above it
            if abs(ang) <= SNAP:
                ang = 0                  # a near-upright head stays unrotated (crisp, no resampling blur)
            res.append([round(float(dx), 1), round(float(dy), 1), ang, kbest] if ok else None)
        filled = _fill(_spikes(res))
        if not anim.startswith(("idle", "walk")):
            # 2nd pass, action frames left unmatched: best head match near the line between matched
            # neighbours, every tilt and size, no score cut (the chosen face is always drawn)
            lim2 = 50 if fac == "e" else (25 if fac == "s" else 10)
            for i, v in enumerate(filled):
                trusted = len(v) < 5
                hs0 = _hs_mask(path, i, hh)
                if trusted and (hs0 is None or hs0.sum() <= 80):
                    continue                     # matched, and no masks to check it against
                c = (v[0], v[1])
                best = None
                RR[0] = 16
                for t in temps:
                    if abs(t[0]) <= lim2 and t[0] % 2 == 0:
                        best = _try(Fs[i], hh, c, *t, best)
                RR[0] = R
                if best is None:
                    continue
                kb = 1.0
                if fac != "n":
                    for k in (0.92, 1.08, 1.16, 1.25, 1.35, 1.5, 1.7):
                        RR[0] = 4 if k < 1.3 else 10      # a lunge at the camera: much bigger, lower head
                        nb = _try(Fs[i], hh, (best[1], best[2]), best[3], *make(best[3], k)[1:], None)
                        RR[0] = R
                        if nb is not None and nb[0] < best[0] - 0.004:
                            best, kb = nb, k
                # the relaxed match, the measured anchor and the neighbours' line all compete; a head is
                # the top of the figure (little of it above), then the lower score wins
                cands = [(best, kb)]
                if trusted:
                    cands.insert(0, ((0.0, v[0], v[1], v[2]), v[3]))
                gs = [Gs[i]] if Gs[i] != (0.0, 0.0) else []
                for cxy in gs + [c]:
                    RR[0] = 3
                    cb = None
                    for t in temps:
                        if abs(t[0]) <= 8:
                            cb = _try(Fs[i], hh, cxy, *t, cb)
                    RR[0] = R
                    if cb is not None:
                        cands.append((cb, 1.0))
                tops = [cd for cd in cands if above(Fs[i], hh, *cd) < 0.6]
                if os.environ.get("DBG"):
                    print(anim, fac, i, [(round(cd[0][0], 3), cd[0][1:], cd[1], round(above(Fs[i], hh, *cd), 2))
                                         for cd in cands])
                best, kb = min(tops or cands, key=lambda cd: cd[0][0])
                hs = _hs_mask(path, i, hh)
                strong = False
                gi = 2 if trusted else 1                  # where the measured anchor's candidate sits
                if hs is not None and hs.sum() > 80:
                    # the figure's own hair/skin masks decide: the placement whose head covers most of
                    # them (and least else) is where the head really is
                    rel = [mb_ for mb_ in (_mask_seed(path, i, hh, idle_box, ny, cd[0][1], cd[0][2])
                                           for cd in cands) if mb_]
                    for sdx, sdy, k_m in rel:
                        bm = None
                        RR[0] = 5
                        for a in [a for a in ANGLES if abs(a) <= lim and a % 4 == 0]:
                            bm = _try(Fs[i], hh, (sdx, sdy), *make(a, round(k_m, 2)), bm)
                        RR[0] = R
                        if bm is not None:
                            cands.append((bm, round(k_m, 2)))
                    cw = max(cands, key=lambda cd: _cover(hs, make(cd[0][3], cd[1]), cd[0][1], cd[0][2]))
                    # a weak best cover (sparse or mislabelled masks) decides nothing
                    if _cover(hs, make(cw[0][3], cw[1]), cw[0][1], cw[0][2]) >= 0.4:
                        best, kb = cw
                        strong = True
                    if os.environ.get("DBG") == anim + fac:
                        print("COVER", i, [(cd[0][1:], cd[1], round(_cover(hs, make(cd[0][3], cd[1]), cd[0][1], cd[0][2]), 3)) for cd in cands])
                if trusted and not strong:
                    continue                     # nothing better to go on than the first-pass match
                if not strong and gs and len(cands) > gi and cands[gi] in tops:
                    # the measured anchor is on top of the figure: it wins over a better-scoring match
                    # unless that one sits close to it (a far-off match is the chest or an arm)
                    gb = cands[gi]
                    if max(abs(best[1] - gb[0][1]), abs(best[2] - gb[0][2])) > 15:
                        best, kb = gb
                _v, dx, dy, ang = best
                if trusted and (dx, dy, ang) == (v[0], v[1], v[2]):
                    continue                     # the first-pass match also covers the own head best
                if abs(ang) <= SNAP:
                    ang = 0
                filled[i] = [round(float(dx), 1), round(float(dy), 1), ang, kb, 2]   # 2 = relaxed match
        if not anim.startswith(("idle", "walk")) and len(filled) >= 3:
            d = lambda p, q: max(abs(p[0] - q[0]), abs(p[1] - q[1]))
            for i, j, k in ((0, 1, 2), (len(filled) - 1, len(filled) - 2, len(filled) - 3)):
                hs_e = _hs_mask(path, i, hh)
                if hs_e is not None and hs_e.sum() > 80:
                    continue                     # its own masks already placed it
                if d(filled[j], filled[k]) < 8 and d(filled[i], filled[j]) > 15:
                    filled[i] = list(filled[j][:4]) + [2]      # a lone end-frame jump: its neighbour's place
        out[f"{sex}/{layer}/{anim}_{fac}"] = filled
    return out


def build(only=None):
    meta = json.load(open(os.path.join(FACES, "faces.json")))
    track = {}
    for key, tags in sorted((meta.get("targets") or {}).items()):
        if only and only not in key:
            continue
        sex, layer = key.split("/", 1)
        tp_all = tags.get("2x") or {}
        strips = list(_strips(sex, layer))
        for fac, tp in tp_all.items():
            track.update(track_one(sex, layer, fac, tp, strips))
        print(key, flush=True)
    if only and os.path.exists(OUT):
        old = json.load(open(OUT)); old.update(track); track = old
    with open(OUT, "w") as f:
        json.dump(track, f, separators=(",", ":"))
    return track


if __name__ == "__main__":
    build(sys.argv[1] if len(sys.argv) > 1 else None)
