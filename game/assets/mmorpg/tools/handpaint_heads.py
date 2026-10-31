"""Hand-painted head plates (David, 30 Oct 2026): for figures where the runtime erase cut arms,
weapons or collars, the old head is painted out of the frame pixels once, here, and saved beside the
art as {anim}_{facing}_clean.png (same strip layout). face_layer.apply() then draws the chosen head on
that plate with no erase at all, so raised arms, hafts and collars stay whole.

Per frame: the figure's own hair + face skin above its neck line, the dark backdrop behind the old head
and a thin halo around them go transparent; old hair hanging below the neck over the clothes is
repainted from the clothes' own texture (fix_armour_back_skin._texfill). Never edits the source art.
Usage: python3 tools/handpaint_heads.py            (all JOBS)
"""
import os, sys
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
import numpy as np
import pygame
from scipy import ndimage as ndi

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "client"))
sys.path.insert(0, HERE)

# (sex, layer, anim, facing, measuring face)
JOBS = [("female", "outfit_set_water_f_hd", f"melee_axe", fc, "queen") for fc in "sen"] + \
       [("male", "outfit_set_fire_m_hd", an, "e", "king") for an in ("idle", "walk")] + [
    ("male", "outfit_set_water_m_hd", "melee_sword", "s", "king"),
    ("male", "outfit_set_water_m_hd", "melee_sword", "e", "king"),
    ("male", "outfit_villager_hd", "melee_axe", "e", "king"),
    ("male", "outfit_set_fire_m_hd", "melee_axe", "n", "king"),
    ("female", "outfit_set_fire_f_hd", "melee_axe", "n", "queen"),
]
TAGS = ("1x", "2x", "4x")
# per-job hand settings: "tight" = take only the old hair/face and its halo (an arm raised over the head
# shares the shirt's colours, so no filled head region); "neck" = keep the old pixels a few rows above the
# chosen head's neck end so the neck join never opens a see-through row
OPTS = {("male", "outfit_villager_hd", "melee_axe", "e"): {"tight": True, "neck": True},
        # Tide queen swing: the haft is repainted along its whole measured length (one clean shaft), and the
        # thin black backdrop slivers left between arm and hair are taken too
        ("female", "outfit_set_water_f_hd", "melee_axe", "s"): {"fullhaft": True, "darkgrow": True}}

# hand-erased leftovers (2x px boxes, frame-local): the tiara peak the haft crosses at the top of the swing
ERASE = {("female", "outfit_set_water_f_hd", "melee_axe", "s", 7): [(137, 112, 155, 122)]}

# hand-kept parts (2x px boxes, frame-local): the original hand / sleeve pixels inside are put back
# as drawn - the villager's hand, haft and sleeve across the top of his head
KEEP = {("male", "outfit_villager_hd", "melee_axe", "e", 3): [(150, 76, 164, 96), (144, 92, 170, 108), (158, 100, 171, 130), (143, 104, 158, 120)]}


def _haft_mask(key, h, pad=1.5):
    m = np.zeros((h, h), bool)
    kk = h / 288.0
    for (x0, y0, x1, y1, wd) in HAFTS.get(key, ()):
        x0, y0, x1, y1, wd = x0 * kk, y0 * kk, x1 * kk, y1 * kk, wd * kk
        L_ = max(1.0, np.hypot(x1 - x0, y1 - y0))
        for t in np.arange(-2 * kk, L_ + 2 * kk, 0.5):
            cx = x0 + (x1 - x0) * t / L_; cy = y0 + (y1 - y0) * t / L_
            r = wd / 2 + pad * kk
            xa, xb = int(max(0, cx - r)), int(min(h - 1, cx + r)) + 1
            ya, yb = int(max(0, cy - r)), int(min(h - 1, cy + r)) + 1
            m[xa:xb, ya:yb] = True
    return m
# hand-measured haft lines where the haft crossed the old head's backdrop: 2x px (x0, y0, x1, y1, width)
HAFTS = {
    ("female", "outfit_set_water_f_hd", "melee_axe", "s", 4): [(100, 108.5, 170, 112.5, 4)],
    ("female", "outfit_set_water_f_hd", "melee_axe", "s", 5): [(105, 105.5, 172, 107.5, 4)],
    ("female", "outfit_set_water_f_hd", "melee_axe", "s", 6): [(110, 105.0, 172, 108.5, 4)],
    ("female", "outfit_set_water_f_hd", "melee_axe", "s", 7): [(112, 111.5, 168, 133.0, 4)],
}


def _mask(path, i, sh):
    if not os.path.exists(path):
        return None
    st = pygame.image.load(path)
    if st.get_width() < (i + 1) * sh:
        return None
    return pygame.surfarray.array_alpha(st.subsurface((i * sh, 0, sh, sh))) > 90


def _disk(r):
    r = max(1, int(round(r)))
    y, x = np.ogrid[-r:r + 1, -r:r + 1]
    return x * x + y * y <= r * r


def _paint_shaft(rgb, al, opq, skinish, S, sleeve, key, h, fr0):
    """One clean wooden shaft along each measured haft line: the line is refitted to the haft's own
    visible pixels, the old (cut / stepped) haft pixels in its band are cleared and the shaft is painted
    anti-aliased with one wood profile: dark rim, brown body, a soft highlight on the upper side.
    Hands (skin) gripping it stay in front."""
    kk = h / 288.0
    xx = np.arange(h)[:, None].repeat(h, 1).astype(np.float32)
    yy = np.arange(h)[None, :].repeat(h, 0).astype(np.float32)
    lum = fr0.max(2)
    r_, g_, b_ = fr0[..., 0], fr0[..., 1], fr0[..., 2]
    wood = opq & (r_ > b_ + 6) & (lum > 38) & (lum < 150) & ~skinish & ~sleeve
    hand = skinish | (S if S is not None else False)
    hand = ndi.binary_dilation(hand, _disk(max(1, 0.6 * kk))) & (al > 100)   # a hand painted out is no hand
    for (x0, y0, x1, y1, wd) in HAFTS.get(key, ()):
        x0, y0, x1, y1, wd = x0 * kk, y0 * kk, x1 * kk, y1 * kk, max(2.0, wd * kk)
        for _ in range(0):                       # (refit off: the measured lines are used as drawn)
            L_ = max(1.0, np.hypot(x1 - x0, y1 - y0))
            ux, uy = (x1 - x0) / L_, (y1 - y0) / L_
            t = (xx - x0) * ux + (yy - y0) * uy
            d = -(xx - x0) * uy + (yy - y0) * ux
            sel = wood & (np.abs(d) < wd) & (t > 0) & (t < L_)
            if sel.sum() < 10:
                break
            tt, dd = t[sel], d[sel]
            A = np.vstack([tt, np.ones_like(tt)]).T
            m_, c_ = np.linalg.lstsq(A, dd, rcond=None)[0]
            nx, ny = -uy, ux
            x0, y0 = x0 + c_ * nx, y0 + c_ * ny
            x1, y1 = x1 + (c_ + m_ * L_) * nx, y1 + (c_ + m_ * L_) * ny
        L_ = max(1.0, np.hypot(x1 - x0, y1 - y0))
        ux, uy = (x1 - x0) / L_, (y1 - y0) / L_
        t = (xx - x0) * ux + (yy - y0) * uy
        d = -(xx - x0) * uy + (yy - y0) * ux
        on = (t >= 0) & (t <= L_)
        half = wd / 2.0
        band = on & (np.abs(d) < half + 2.6 * kk) & ~hand & ~sleeve
        # clear the old haft remains around it (stepped edges, dark seams)
        al[band & (np.abs(d) >= half + 0.5)] = 0
        cov = np.clip(half + 0.5 - np.abs(d), 0, 1) * (band)
        u = np.clip(d / half, -1, 1)              # -1 upper edge .. 1 lower edge
        rim = (18, 13, 13)
        body = np.array((58, 40, 36), np.float32)
        hi = np.array((98, 72, 62), np.float32)
        wgt_hi = np.exp(-((u + 0.35) / 0.35) ** 2)
        col = body[None, None, :] * (1 - wgt_hi[..., None]) + hi[None, None, :] * wgt_hi[..., None]
        edge = np.clip((np.abs(u) - 0.55) / 0.45, 0, 1)
        col = col * (1 - edge[..., None]) + np.array(rim, np.float32)[None, None, :] * edge[..., None]
        # faint grain along the shaft so it is not a flat ruler line
        col *= (1 + 0.05 * np.sin(t * 0.9 / kk))[..., None]
        pm = cov > 0
        a0 = al.astype(np.float32) / 255.0
        a_new = cov + a0 * (1 - cov)
        rgb[pm] = (col[pm] * cov[pm, None] + rgb[pm] * (a0[pm] * (1 - cov[pm]))[:, None]) / np.maximum(a_new[pm], 1e-3)[:, None]
        al[pm] = np.clip(a_new[pm] * 255, 0, 255).astype(al.dtype)


def paint_frame(F, P, tex, sex, layer, anim, fc, face, tag, i, st):
    sh = st.get_height()
    fr = st.subsurface((i * sh, 0, sh, sh)).copy()
    base = os.path.join(F._BASE, sex, tag, layer, f"{anim}_{fc}")
    H = _mask(base + "_hair.png", i, sh)
    S = _mask(base + "_skin.png", i, sh)
    res = F.apply(fr, sex, layer, anim, fc, i, face, (198, 150, 120), (70, 48, 32), P._skin_whole, tag=tag)
    if res is None or H is None:
        return None
    tx, ty = F.LAST["tx"], F.LAST["ty"]
    h = sh
    rgb = pygame.surfarray.array3d(fr).astype(np.float32)
    fr0 = rgb.copy()
    al = pygame.surfarray.array_alpha(fr).copy()
    opq = al > 100
    yy = np.arange(h)[None, :].repeat(h, 0)
    xx = np.arange(h)[:, None].repeat(h, 1)
    m = max(1, int(round(0.012 * h)))
    # never above where the chosen head ends: what is under its neck must stay (no see-through gap)
    cut = ty + (F.LAST["bot"] - F.LAST["neck"][1]) * F.LAST["sc"]
    opt = OPTS.get((sex, layer, anim, fc), {})
    above = yy < min(ty + m, cut)
    nb = np.zeros_like(above)
    if opt.get("neck"):
        nb = (np.abs(xx - tx) < 0.07 * h) & (yy >= min(ty + m, cut) - max(2, 0.01 * h))
        above &= ~nb
    old = H & above
    if opt.get("tight") and old.any():
        # this art's hair mask also covers the raised hand and the axe: only the blob sitting on the neck
        lab, n = ndi.label(ndi.binary_dilation(old, _disk(1)) & above)
        if n > 1:
            best_k, best_d = 1, 1e9
            for k in range(1, n + 1):
                c = (lab == k) & old
                if not c.any():
                    continue
                d = np.hypot(xx[c].mean() - tx, yy[c].max() - ty)
                if d < best_d:
                    best_k, best_d = k, d
            old &= lab == best_k
    hair0 = old.copy()
    raised = np.zeros_like(old)
    if S is not None:
        lab, n = ndi.label(S & above)
        for k in range(1, n + 1):
            c = lab == k
            if abs(xx[c].mean() - tx) < 0.06 * h:
                # only its part inside the old hair's box: an arm raised past the head stays
                hb = hair0 if opt.get("tight") else H & above
                if hb.any():
                    hx_, hy_ = np.nonzero(hb)
                    pad = max(2, int(0.01 * h))
                    up = c & (yy < hy_.min() - pad)        # an arm raised past the top of the head
                    raised |= up
                    c = c & ~up
                if opt.get("tight") and hb.any():
                    # face skin only inside the old hair's own box (forearm / hand skin outside it stays)
                    bx = np.zeros_like(c)
                    bx[max(0, hx_.min() - pad):hx_.max() + pad + 1, max(0, hy_.min() - pad):hy_.max() + pad + 1] = True
                    # and only its lower part (the face): a forearm raised across the top of the head stays
                    bx &= yy > hy_.min() + 0.4 * (ty - hy_.min())
                    hands_t = c & ~bx
                    raised |= hands_t
                    c = c & bx
                old |= c
    if old.sum() < 4:
        return None
    lum = rgb.max(2)
    # dark backdrop behind the old head (thin dark hafts survive the opening)
    dark = opq & above & (lum < 30)
    blob = ndi.binary_opening(dark, _disk(0.014 * h))
    blob = ndi.binary_dilation(blob, _disk(1.5)) & dark
    lab, n = ndi.label(blob)
    near = ndi.binary_dilation(old, _disk(0.02 * h))
    bd = np.zeros_like(blob)
    for k in range(1, n + 1):
        c = lab == k
        if (c & near).any():
            bd |= c
    # thin halo around the old head: hair / skin coloured, not sleeve, metal or haft
    ref = np.median(rgb[old], 0)
    halo = ndi.binary_dilation(old | bd, _disk(max(1.5, 0.008 * h))) & above & ~old & ~bd
    halo &= (np.abs(rgb - ref).sum(2) < (55 if opt.get("tight") else 110)) | (lum < 30)
    gone = old | bd | halo
    # the whole old head outline: everything inside its filled shape above the neck goes, except
    # sleeve blue, bright metal and thin straight runs (hafts) crossing it
    reg = ndi.binary_closing(gone, _disk(0.02 * h), iterations=1)
    reg = ndi.binary_fill_holes(reg)
    reg = ndi.binary_dilation(reg, _disk(max(1.0, 0.006 * h))) & above
    r_, g_, b_ = rgb[..., 0], rgb[..., 1], rgb[..., 2]
    sleeve = (b_ > r_ + 12) & (b_ > 90)
    sat = rgb.max(2) - rgb.min(2)
    metal = (lum > 150) & (sat < 40)
    hands = np.zeros_like(old)
    if S is not None:
        lab, n = ndi.label(S)
        for k in range(1, n + 1):
            c = lab == k
            if not (c & old).any():
                hands |= c
    hands |= raised
    rod = np.zeros_like(old)
    best = (0, None)
    lit = opq & (lum >= 22)
    thin = opq & ~ndi.binary_opening(opq, _disk(max(3, 0.013 * h)))
    for ang in range(0, 180, 6):
        t = np.deg2rad(ang)
        L = max(5, int(0.03 * h))
        se = np.zeros((2 * L + 1, 2 * L + 1), bool)
        for d in range(-L, L + 1):
            se[int(round(L + d * np.cos(t))), int(round(L + d * np.sin(t)))] = True
        rp = ndi.binary_opening(thin & ~H, se)
        if rp.sum() > 2 * L:
            # bridge gaps along the same line (a haft crossing the dark backdrop), up to 3L
            br = ndi.binary_closing(rp, np.pad(se, L, constant_values=False), iterations=1) & lit
            rp |= br
        rod |= rp
        if rp.sum() > best[0]:
            best = (int(rp.sum()), rp)
    # a tiara / hair jewel sits wholly inside the old head: only metal reaching outside it is kept
    lab, n = ndi.label(metal)
    for k in range(1, n + 1):
        c = lab == k
        if not (c & ~reg).any():
            metal &= ~c
    skinish = (r_ > g_) & (r_ - b_ > 30) & (r_ > 90)
    if opt.get("darkgrow"):
        # a tiara / hair jewel the haft crosses: dropped unless it is part of the measured haft line
        hm0 = _haft_mask((sex, layer, anim, fc, i), h, pad=0.5)
        near_h = ndi.binary_dilation(H & above, _disk(0.07 * h))
        lab, n = ndi.label(metal)
        for k in range(1, n + 1):
            c = lab == k
            if not (c & ~near_h).any() and not (c & hm0).any():
                metal &= ~c
    prot = sleeve | metal | ndi.binary_dilation(hands, _disk(1)) | ndi.binary_dilation(rod, _disk(1))
    if opt.get("tight"):
        # the raised sleeve (olive shirt cloth: green >= red) crossing the hair mask is the arm, not hair
        shirt = opq & (g_ >= r_ - 2) & (lum > 35)
        shirt = ndi.binary_opening(shirt, _disk(1))
        hands = hands | shirt
        gone = (old | halo) & ~(ndi.binary_dilation(hands, _disk(1)) | ndi.binary_dilation(rod, _disk(1)))
        reg = ndi.binary_dilation(old, _disk(max(1.0, 0.006 * h))) & above
    else:
        gone |= reg & opq & ~prot
    if opt.get("darkgrow"):
        # black backdrop slivers squeezed between the arms and the old hair (survived the opening as
        # "thin rods"): grown from what is removed through near-black pixels, never into the haft line
        hm = _haft_mask((sex, layer, anim, fc, i), h)
        dk = opq & above & (lum < 42) & ~hm & ~sleeve & ~metal & ~skinish & ~ndi.binary_dilation(hands, _disk(1))
        seed = gone & ndi.binary_dilation(dk, _disk(1))
        if seed.any():
            gone |= ndi.binary_propagation(seed, mask=dk | seed) & dk
        # and a 1px dark edge they leave against the sleeve
        gone |= ndi.binary_dilation(gone, _disk(1)) & opq & above & (lum < 55) & ~hm & ~sleeve & ~metal & ~skinish
    # lone specks left between removed parts: tiny opaque islands go too
    keep = opq & ~gone
    lab, n = ndi.label(keep)
    if n:
        sz = ndi.sum(np.ones_like(keep), lab, range(1, n + 1))
        for k in range(1, n + 1):
            if sz[k - 1] < max(6, (0.02 * h) ** 2):
                c = lab == k
                if (c & ndi.binary_dilation(gone, _disk(2))).any():
                    gone |= c
    al[gone & above] = 0
    # the old head's soft anti-aliased rim (below the opaque cut) goes with it
    rim = (reg | ndi.binary_dilation(gone, _disk(max(2, 0.01 * h)))) & above & ~opq & ~prot
    al[rim] = 0
    # the haft where it crossed the old head's dark backdrop: painted by hand along its measured line
    # (2x px, frame-local), each cross-section cloned from the haft's own visible pixels
    if KEEP.get((sex, layer, anim, fc, i)):
        al0 = pygame.surfarray.array_alpha(fr)
        R0, G0, B0 = fr0[..., 0], fr0[..., 1], fr0[..., 2]
        cloth = (G0 >= R0 - 8) & (fr0.max(2) > 28)
        sk0 = (R0 > G0) & (R0 - B0 > 30) & (R0 > 90)
        for (kx0, ky0, kx1, ky1) in KEEP[(sex, layer, anim, fc, i)]:
            kk_ = h / 288.0
            kb = np.zeros_like(opq)
            kb[int(kx0 * kk_):int(np.ceil(kx1 * kk_)), int(ky0 * kk_):int(np.ceil(ky1 * kk_))] = True
            kb &= al0 > 0
            rgb[kb] = fr0[kb]
            al[kb] = al0[kb]
    for (ex0, ey0, ex1, ey1) in ERASE.get((sex, layer, anim, fc, i), ()):
        kk_ = h / 288.0
        eb = np.zeros_like(opq)
        eb[int(ex0 * kk_):int(np.ceil(ex1 * kk_)), int(ey0 * kk_):int(np.ceil(ey1 * kk_))] = True
        al[eb] = 0
    if opt.get("fullhaft"):
        _paint_shaft(rgb, al, opq, skinish, S, sleeve, (sex, layer, anim, fc, i), h, fr0=fr0)
    else:
        for (x0, y0, x1, y1, wd) in HAFTS.get((sex, layer, anim, fc, i), ()):
            kk = h / 288.0
            x0, y0, x1, y1, wd = x0 * kk, y0 * kk, x1 * kk, y1 * kk, max(1.0, wd * kk)
            L_ = max(1.0, np.hypot(x1 - x0, y1 - y0))
            ax_ = np.array([(x1 - x0) / L_, (y1 - y0) / L_]); nx_ = np.array([-ax_[1], ax_[0]])
            offs = np.arange(-wd / 2, wd / 2 + 1e-6, 0.5)
            prof = []
            for o_ in offs:
                cols = []
                for t in np.arange(0, L_, 0.5):
                    x = int(round(x0 + t * ax_[0] + o_ * nx_[0])); y = int(round(y0 + t * ax_[1] + o_ * nx_[1]))
                    if 0 <= x < h and 0 <= y < h and opq[x, y] and not gone[x, y] and not bd[x, y] and lum[x, y] > 12 \
                            and not (S is not None and S[x, y]) and not skinish[x, y]:
                        cols.append(rgb[x, y])
                prof.append(np.median(cols, 0) if len(cols) > 2 else None)
            for t in np.arange(0, L_, 0.5):
                for o_, col in zip(offs, prof):
                    if col is None:
                        continue
                    x = int(round(x0 + t * ax_[0] + o_ * nx_[0])); y = int(round(y0 + t * ax_[1] + o_ * nx_[1]))
                    if 0 <= x < h and 0 <= y < h and (gone[x, y] or (opt.get("fullhaft") and not skinish[x, y]
                                                         and not (S is not None and S[x, y]))):
                        rgb[x, y] = col
                        al[x, y] = 255
    # old hair below the neck over the clothes: repainted from the clothes' texture
    below = H & ~above & opq
    if below.any():
        body = opq & ~H
        rows_ok = np.zeros_like(below)
        span = int(0.06 * h)
        for y in np.unique(np.nonzero(below)[1]):
            cols = np.nonzero(body[:, y])[0]
            if len(cols) == 0:
                continue
            for x in np.nonzero(below[:, y])[0]:
                if (cols < x).any() and (cols > x).any() and (x - cols[cols < x].max()) < span \
                        and (cols[cols > x].min() - x) < span:
                    rows_ok[x, y] = True
        if opt.get("neck"):
            # under the chin the old beard / hair stands for the neck: always repainted, never see-through
            rows_ok |= below & (np.abs(xx - tx) < 0.07 * h) & (yy < ty + 0.05 * h)
        fillm = below & rows_ok
        al[below & ~rows_ok] = 0
        if fillm.any():
            xs, ys = np.nonzero(fillm)
            X0, X1 = max(0, xs.min() - 8), min(h, xs.max() + 9)
            Y0, Y1 = max(0, ys.min() - 8), min(h, ys.max() + 9)
            sub = rgb[X0:X1, Y0:Y1]
            u = fillm[X0:X1, Y0:Y1]
            bad = ~opq[X0:X1, Y0:Y1] | H[X0:X1, Y0:Y1] | (yy[X0:X1, Y0:Y1] < ty + m)
            out = tex(sub, u, bad)
            blk = rgb[X0:X1, Y0:Y1]
            blk[u] = out[u]
    if anim in ("idle", "walk") and fc in ("e", "w"):
        # side view: the collar / cloak top below the cut was a flat shelf; hand-shape it so it rises to
        # the neck and falls away to the shoulders, with a soft feathered edge (no straight seam)
        nw = 0.028 * h
        W = 0.07 * h
        D = 0.045 * h
        dx = np.abs(xx - tx)
        f = np.clip((dx - nw) / W, 0, 1)
        f = f * f * (3 - 2 * f)
        top = cut + D * f
        fe = max(1.5, 0.008 * h)
        band = (yy >= cut - 1) & (yy < cut + D + fe + 1) & (dx > nw)
        a_ = np.clip((yy - top) / fe, 0, 1)
        al[band] = (al[band] * a_[band]).astype(al.dtype)
        # a stray speck left floating by the carve (the tip of a shoulder spike): small islands near the
        # neck that no longer touch the figure go
        lab, n = ndi.label(al > 30)
        if n > 1:
            sz = ndi.sum(np.ones_like(al), lab, range(1, n + 1))
            for k in range(1, n + 1):
                if sz[k - 1] < (0.03 * h) ** 2:
                    c = lab == k
                    if np.hypot(xx[c].mean() - tx, yy[c].mean() - ty) < 0.15 * h:
                        al[ndi.binary_dilation(c, _disk(1)) & (al <= 30) | c] = 0
    o = pygame.Surface((h, h), pygame.SRCALPHA)
    pygame.surfarray.blit_array(o, np.clip(rgb, 0, 255).astype(np.uint8))
    pa = pygame.surfarray.pixels_alpha(o)
    pa[...] = al
    del pa
    return o


def main(jobs=JOBS, tags=TAGS):
    pygame.init()
    pygame.display.set_mode((8, 8))
    import face_layer as F
    import player_hd_client as P
    from fix_armour_back_skin import _texfill
    F._clean_frame = lambda *a, **k: None          # measure on the untouched art
    done = 0
    for sex, layer, anim, fc, face in jobs:
        for tag in tags:
            p = os.path.join(F._BASE, sex, tag, layer, f"{anim}_{fc}.png")
            if not os.path.exists(p):
                continue
            st = pygame.image.load(p).convert_alpha()
            sh = st.get_height()
            n = st.get_width() // sh
            strip = st.copy()
            any_ = False
            for i in range(n):
                o = paint_frame(F, P, _texfill, sex, layer, anim, fc, face, tag, i, st)
                if o is not None:
                    strip.fill((0, 0, 0, 0), pygame.Rect(i * sh, 0, sh, sh))
                    strip.blit(o, (i * sh, 0))
                    any_ = True
            if any_:
                q = p[:-4] + "_clean.png"
                pygame.image.save(strip, q)
                print("wrote", q)
                hp = p[:-4] + "_hair.png"
                if os.path.exists(hp):
                    # the plate's own hair mask: the art's hair mask kept only where the plate still
                    # shows the art's pixels (repainted / cleared old hair drops out of it)
                    hm = pygame.image.load(hp).convert_alpha()
                    if hm.get_size() == st.get_size():
                        a0 = pygame.surfarray.pixels3d(st)
                        a1 = pygame.surfarray.pixels3d(strip)
                        same = (np.abs(a0.astype(int) - a1).max(2) < 6) & \
                            (pygame.surfarray.array_alpha(strip) > 100)
                        del a0, a1
                        hm2 = hm.copy()
                        ha = pygame.surfarray.pixels_alpha(hm2)
                        ha[~same] = 0
                        del ha
                        pygame.image.save(hm2, p[:-4] + "_clean_hair.png")
                done += 1
    return done


if __name__ == "__main__":
    main()


def paint_back_mirror(cur_path, pre_path, hair_pre_path=None, y_rel=(0.36, 0.75)):
    """Back views (female eclipse): pixels the ponytail repaint changed are re-painted from the
    mirror image of the untouched plate on the other side of the spine, where that side is clean plate.
    Edits the art in place (backup: faces_pre/handpaint_pre/assets_art.tgz)."""
    cur = pygame.image.load(cur_path)
    pre = pygame.image.load(pre_path)
    hp = pygame.image.load(hair_pre_path) if hair_pre_path and os.path.exists(hair_pre_path) else None
    sh = cur.get_height()
    A = pygame.surfarray.pixels3d(cur)
    Aa = pygame.surfarray.pixels_alpha(cur)
    Pp = pygame.surfarray.array3d(pre).astype(np.int32)
    Pa = pygame.surfarray.array_alpha(pre)
    Hp = (pygame.surfarray.array_alpha(hp) > 60) if hp is not None else np.zeros_like(Pa, bool)
    n = cur.get_width() // sh
    done = 0
    for i in range(n):
        sl = slice(i * sh, (i + 1) * sh)
        a = A[sl].astype(np.int32)
        aa = Aa[sl]
        p, pa, hm = Pp[sl], Pa[sl], Hp[sl]
        chg = (np.abs(a - p).sum(2) > 24) & (aa > 100)
        y0, y1 = int(y_rel[0] * sh), int(y_rel[1] * sh)
        chg[:, :y0] = False
        chg[:, y1:] = False
        if chg.sum() < 4:
            continue
        lum = a.max(2)
        sat = a.max(2) - a.min(2)
        done_f = np.zeros_like(chg)
        for y in range(y0, y1):
            cols = np.nonzero(aa[:, y] > 100)[0]
            if len(cols) < 4:
                continue
            # spine: the middle of the torso on this row (the arms swing, so the widest run is used)
            runs = np.split(cols, np.nonzero(np.diff(cols) > 1)[0] + 1)
            run = max(runs, key=len)
            cx2 = run[0] + run[-1]
            for x in np.nonzero(chg[:, y])[0]:
                xm = cx2 - x
                if 0 <= xm < sh and abs(xm - x) > 2 and pa[xm, y] > 100 and not hm[xm, y] \
                        and not chg[xm, y]:
                    a[x, y] = p[xm, y]
                    done_f[x, y] = True
        # the lane on the spine itself (mirrors onto itself): painted across from the plate either side
        left = chg & ~done_f
        for y in np.unique(np.nonzero(left)[1]):
            xs_ = np.nonzero(left[:, y])[0]
            okx = np.nonzero((aa[:, y] > 100) & ~(chg[:, y] & ~done_f[:, y]))[0]
            for x in xs_:
                lo = okx[okx < x]; hi = okx[okx > x]
                if len(lo) and len(hi) and hi.min() - lo.max() < 0.08 * sh:
                    xl, xr = lo.max(), hi.min()
                    w_ = (x - xl) / float(xr - xl)
                    a[x, y] = (1 - w_) * a[xl, y] + w_ * a[xr, y]
                    done_f[x, y] = True
        # soften the seam between mirrored plate and what stays: a 1px blend ring
        ring = ndi.binary_dilation(done_f, _disk(1)) & ~done_f & (aa > 100)
        if ring.any():
            bl = ndi.uniform_filter(a.astype(np.float32), size=(3, 3, 1))
            a[ring] = ((a[ring] + bl[ring]) / 2).astype(np.int32)
        # hand-smoothing of the repainted plate: soft vertical blend kills the row-by-row banding
        if done_f.any():
            D = done_f.astype(np.float32)
            sg = (max(0.6, 0.006 * sh), max(1.2, 0.018 * sh))
            den = ndi.gaussian_filter(D, sg) + 1e-6
            af = a.astype(np.float32)
            for c in range(3):
                sm = ndi.gaussian_filter(af[..., c] * D, sg) / den
                af[..., c][done_f] = 0.25 * af[..., c][done_f] + 0.75 * sm[done_f]
            a = af.astype(np.int32)
        A[sl] = np.clip(a, 0, 255).astype(np.uint8)
        done += int(done_f.sum())
    del A, Aa
    pygame.image.save(cur, cur_path)
    return done
