"""Bare-head armour (armour_*_bh_hd), back views: the skin masks reached onto the plate (upper back,
hips, arms), so the chosen skin tone painted flesh-coloured blotches on the armour. Keep skin only on
the neck under the head; everything else in the _n skin masks is cleared. Idempotent.
Backup of the originals: ~/grokbot_tmp/faces_pre/armour_bh_masks_pre/."""
import os, glob
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
import pygame
import numpy as np

BASE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "player_hd", "assets")


def fix(skin_path):
    hair_path = skin_path.replace("_skin.png", "_hair.png")
    sk = pygame.image.load(skin_path)
    hr = pygame.image.load(hair_path) if os.path.exists(hair_path) else None
    sh = sk.get_height()
    sa = pygame.surfarray.pixels_alpha(sk)
    ha = pygame.surfarray.array_alpha(hr) if hr is not None else None
    cleared = 0
    for i in range(sk.get_width() // sh):
        x0 = i * sh
        fa = sa[x0:x0 + sh]
        keep = np.zeros(fa.shape, bool)
        if ha is not None:
            hm = ha[x0:x0 + sh] > 90
            if hm.any():
                xs, ys = np.where(hm)
                top = ys.min()
                # head centre from the top part of the hair (a ponytail must not pull it sideways)
                tm = ys < top + 0.06 * sh
                cx = float(np.median(xs[tm]))
                hw = max(6, (xs[tm].max() - xs[tm].min()) / 2.0)
                # neck: just under the head, never down onto the shoulder plates
                male = os.sep + "male" + os.sep in skin_path
                # male backs: short hair, so the kept neck is shorter and narrower (no pale gorget patch)
                y1 = int(min(top + (0.10 if male else 0.125) * sh, ys.max() + (0.005 if male else 0.03) * sh))
                wk = 0.8 if male else 1.1
                keep[max(0, int(cx - hw * wk)):int(cx + hw * wk) + 1, top:y1] = True
        n = int(((fa > 0) & ~keep).sum())
        fa[~keep] = 0
        cleared += n
    del sa
    pygame.image.save(sk, skin_path)
    return cleared


def _inpaint(rgb, unk):
    """Diffusion fill of unk from the known pixels around it (rgb float HxWx3 in surfarray order)."""
    known = ~unk
    for _ in range(400):
        if not unk.any():
            break
        acc = np.zeros(rgb.shape, np.float32); cnt = np.zeros(unk.shape, np.float32)
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1), (1, 1), (-1, -1), (1, -1), (-1, 1)):
            k = np.roll(np.roll(known, dx, 0), dy, 1)
            acc += np.roll(np.roll(rgb * known[..., None], dx, 0), dy, 1)
            cnt += k
        front = unk & (cnt >= 2)
        if not front.any():
            front = unk & (cnt > 0)
            if not front.any():
                break
        rgb[front] = acc[front] / cnt[front][:, None]
        known |= front
        unk &= ~front
    return rgb


def _texfill(sub, u, bad):
    """Fill u with the plate / cloak texture around it, not a flat colour. The base colour is a
    diffusion from the edge (so no seam), and on top of it goes the fine detail (high-pass) of the
    plate itself, taken from the nearest usable pixels mirrored in across the hole: first down the
    column (the lower back below the ponytail), else along the row. Hair-coloured and off-figure
    pixels are never a source. sub float WxHx3 (surfarray order), u / bad bool WxH."""
    from scipy.ndimage import gaussian_filter
    W, H = u.shape
    low = _inpaint(np.where((u | bad)[..., None], 0, sub).copy(), (u | bad).copy())
    src = ~u & ~bad
    wsum = gaussian_filter(src.astype(np.float32), 2.0) + 1e-4
    blur = np.stack([gaussian_filter(sub[..., c] * src, 2.0) for c in range(3)], -1) / wsum[..., None]
    hp = np.where(src[..., None], sub - blur, 0)
    det = np.zeros(sub.shape, np.float32)
    have = np.zeros(u.shape, bool)
    xs, ys = np.where(u)
    if len(xs):
        # one coherent block: the plate just below the hole, flipped up into it (the same shift for
        # every column, so the borrowed detail keeps its 2-D structure instead of streaking)
        yb = int(ys.max()) + 1
        q = 2 * yb - 1 - ys
        ok = (q >= 0) & (q < H)
        ok[ok] = src[xs[ok], q[ok]]
        det[xs[ok], ys[ok]] = hp[xs[ok], q[ok]]
        have[xs[ok], ys[ok]] = True
        # rows the flip can't reach (or that landed on hair / off-figure): the same from the side
        for sgn in (1, -1):
            r = u & ~have
            if not r.any():
                break
            x0 = int(xs.max()) + 1 if sgn > 0 else int(xs.min()) - 1
            rx, ry = np.where(r)
            qx = 2 * x0 - rx - (1 if sgn > 0 else -1)
            ok = (qx >= 0) & (qx < W)
            ok[ok] = src[qx[ok], ry[ok]]
            det[rx[ok], ry[ok]] = hp[qx[ok], ry[ok]]
            have[rx[ok], ry[ok]] = True
    det = np.clip(det, -28, 28)
    # fade the borrowed detail in from the hole's edge so no ring shows
    from scipy.ndimage import distance_transform_edt
    fade = np.clip(distance_transform_edt(u) / 3.0, 0, 1)[..., None]
    det *= fade
    out = sub.copy()
    out[u] = low[u] + 0.8 * det[u]
    return out


def fix_ponytail(art_path):
    """Female back views: the long hair down the back of the armour (and the flesh-coloured patches
    beside it) is baked into the art. The chosen head ends at the neck, so below the neck it is
    repainted from the plate around it and taken out of the hair / skin masks."""
    hair_path = art_path.replace(".png", "_hair.png")
    skin_path = art_path.replace(".png", "_skin.png")
    if not (os.path.exists(hair_path) and os.path.exists(skin_path)):
        return 0
    art = pygame.image.load(art_path)
    hr = pygame.image.load(hair_path)
    sk = pygame.image.load(skin_path)
    sh = art.get_height()
    px = pygame.surfarray.pixels3d(art)
    aa = pygame.surfarray.array_alpha(art)
    hra = pygame.surfarray.pixels_alpha(hr)
    ska = pygame.surfarray.pixels_alpha(sk)
    done = 0
    for i in range(art.get_width() // sh):
        sl = slice(i * sh, (i + 1) * sh)
        hm = hra[sl] > 60
        if not hm.any():
            continue
        ys = np.where(hm)[1]
        y_neck = int(ys.min() + 0.05 * sh)
        reg = np.zeros(hm.shape, bool)
        reg[:, y_neck:] = True
        unk = ((hra[sl] > 40) | (ska[sl] > 40)) & reg & (aa[sl] > 100)
        # strands of the ponytail the hair mask missed (dark plate): brown, not gold, grown from the mask
        c = px[sl].astype(np.int16)
        r_, g_, b_ = c[..., 0], c[..., 1], c[..., 2]
        brown = (r_ - g_ > 12) & (g_ - b_ < 30) & (g_ - b_ > -5) & (r_ > 45) & (r_ < 200) & (aa[sl] > 100) & reg
        xs0 = np.where(hm)[0]
        cx0 = float(np.median(xs0)); hw0 = 0.07 * sh
        lane = np.zeros(hm.shape, bool)
        lane[max(0, int(cx0 - hw0)):int(cx0 + hw0) + 1, :] = True
        brown &= lane
        plate = lane & reg & (aa[sl] > 100) & ~(hra[sl] > 40)
        if plate.any() and (brown & plate).sum() > 0.35 * plate.sum():
            # brown / bronze plate: most of the plate reads as "hair brown", so colour can't tell the
            # ponytail from the armour. Only the hair mask is trusted there.
            brown[...] = False
        grow = (hra[sl] > 40) & reg
        for _ in range(int(0.3 * sh)):
            g2 = grow.copy()
            g2[1:] |= grow[:-1]; g2[:-1] |= grow[1:]; g2[:, 1:] |= grow[:, :-1]; g2[:, :-1] |= grow[:, 1:]
            g2 &= brown | grow
            if g2.sum() == grow.sum():
                break
            grow = g2
        unk |= grow
        if unk.sum() < 4:
            continue
        g = unk.copy()
        g[1:] |= unk[:-1]; g[:-1] |= unk[1:]; g[:, 1:] |= unk[:, :-1]; g[:, :-1] |= unk[:, 1:]
        unk = g & reg & (aa[sl] > 100)
        xs_, ys_ = np.where(unk)
        X0, X1 = max(0, xs_.min() - 8), min(sh, xs_.max() + 9)
        Y0, Y1 = max(0, ys_.min() - 8), min(sh, ys_.max() + 9)
        sub = px[sl][X0:X1, Y0:Y1].astype(np.float32)
        u = unk[X0:X1, Y0:Y1].copy()
        # outside the figure is not a colour source
        u_src_bad = aa[sl][X0:X1, Y0:Y1] <= 100
        # nor is any hair-coloured pixel (strands of the ponytail left beside the filled lane)
        hk_ = hm & (aa[sl] > 100)
        if hk_.sum() > 20:
            href = np.median(px[sl][hk_].astype(np.float32), 0)
            u_src_bad = u_src_bad | (np.abs(sub - href).sum(2) < 70)
        # the neck/hair above the chosen head's neck line is not plate either
        u_src_bad[:, :max(0, y_neck + 2 - Y0)] = True
        # nor are pale leftovers (skin, lit strands) much brighter than the dark plate
        lum_ = sub.max(2)
        ok_ = ~u_src_bad & ~u
        if ok_.sum() > 20:
            u_src_bad = u_src_bad | (lum_ > 1.5 * np.median(lum_[ok_]) + 10)
        rgb = _texfill(sub, u, u_src_bad)
        fill = unk[X0:X1, Y0:Y1]
        blk = px[sl][X0:X1, Y0:Y1]
        blk[fill] = np.clip(rgb[fill], 0, 255).astype(np.uint8)
        hra[sl][unk] = 0
        ska[sl][unk] = 0
        done += int(unk.sum())
    del px, hra, ska
    if done:
        pygame.image.save(art, art_path); pygame.image.save(hr, hair_path); pygame.image.save(sk, skin_path)
    return done


def rebuild_thin_hair_masks():
    """A 4x hair mask that came out (nearly) empty (female eclipse back idle): rebuilt from the 2x
    mask of the same pose. Only when the 4x one is under a tenth of what the 2x one implies."""
    for p4 in glob.glob(os.path.join(BASE, "*", "4x", "armour_*_bh_hd", "*_hair.png")):
        p2 = p4.replace(os.sep + "4x" + os.sep, os.sep + "2x" + os.sep)
        if not os.path.exists(p2):
            continue
        m4 = pygame.image.load(p4); m2 = pygame.image.load(p2)
        s2 = m2.get_height()
        f2 = m2.subsurface((0, 0, s2, s2))
        n4 = int((pygame.surfarray.array_alpha(m4) > 60).sum())
        n2 = int((pygame.surfarray.array_alpha(f2) > 60).sum()) * (m4.get_height() / s2) ** 2
        if n2 > 200 and n4 < 0.1 * n2:
            pygame.image.save(pygame.transform.smoothscale(f2, (m4.get_height(), m4.get_height())), p4)
            print("rebuilt", os.path.relpath(p4, BASE))


if __name__ == "__main__":
    pygame.init()
    rebuild_thin_hair_masks()
    tot = 0
    for p in sorted(glob.glob(os.path.join(BASE, "*", "*", "armour_*_bh_hd", "*_n_skin.png"))):
        n = fix(p)
        tot += n
        print(n, os.path.relpath(p, BASE))
    print("cleared", tot)
    tp = 0
    for p in sorted(glob.glob(os.path.join(BASE, "female", "*", "armour_*_bh_hd", "*_n.png"))):
        n = fix_ponytail(p)
        tp += n
    print("ponytail px repainted", tp)
