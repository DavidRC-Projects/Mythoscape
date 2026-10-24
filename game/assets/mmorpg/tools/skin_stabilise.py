"""Steady skin on painted whole figures (David, 23 Oct 2026: skin colour shifted frame to frame in walks).

Two causes, both fixed per layer in its *_skin.png strips (RGB = grey shade ratio*128, A = skin):
 1. video lighting drift: each frame's mean shade ratio differs -> every frame is scaled to the layer's base
    (median frame mean over the layer's idle + walk strips), keeping the shading inside the frame;
 2. face-mask dropout in idle/walk loops (the untinted painted face shows through): the best-covered frame's
    face mask is moved with the head into the weak frames, kept only on tightly skin-coloured pixels in the head box.
Idempotent: a .skin_stable marker per layer folder. Run: python3 tools/skin_stabilise.py [layer ...]"""
import glob, os, sys
import numpy as np
from PIL import Image
from scipy import ndimage as ndi

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "player_hd", "assets")


def head_xy(alpha):
    ys, xs = np.nonzero(alpha > 128)
    if not len(ys):
        return None
    top = ys.min(); band = xs[ys < top + max(3, alpha.shape[0] // 40)]
    return int(top), int(round(band.mean()))


def frame_mean(r, w):
    return float((r * w).sum() / w.sum()) if w.sum() > 4 else None


def _figure(alpha):
    ys, xs = np.nonzero(alpha > 128)
    if not len(ys):
        return None
    top, bot = int(ys.min()), int(ys.max()); H = bot - top
    band = xs[ys < top + max(3, int(0.05 * H))]
    return top, int(round(band.mean())), H


def _head_box(shape, fig):
    top, cx, H = fig
    yy, xx = np.mgrid[0:shape[0], 0:shape[1]]
    return (yy >= top) & (yy <= top + 0.17 * H) & (np.abs(xx - cx) <= 0.09 * H)


def stabilise_strip(skin_p, art_p, base):
    sk = np.array(Image.open(skin_p).convert("RGBA")).astype(np.float32)
    art = np.array(Image.open(art_p).convert("RGBA")).astype(np.float32) if os.path.isfile(art_p) else None
    ch = sk.shape[0]; n = max(1, sk.shape[1] // ch)
    cells = [slice(i * ch, (i + 1) * ch) for i in range(n)]
    loop = os.path.basename(skin_p).startswith(("idle_", "walk_")) and art is not None and n > 1
    if loop:
        figs = [_figure(art[:, c, 3]) for c in cells]
        boxes = [(_head_box((ch, ch), f) if f else None) for f in figs]
        face = [(sk[:, c, 3] > 128) & bx if bx is not None else None for c, bx in zip(cells, boxes)]
        cnt = [int(f.sum()) if f is not None else 0 for f in face]
        b = int(np.argmax(cnt))
        if cnt[b] > 12:
            rgb_b = art[:, cells[b], :3]; c0 = rgb_b[face[b]].mean(0); l0 = c0.mean()
            for i, c in enumerate(cells):
                if figs[i] is None or cnt[i] >= 0.8 * cnt[b]:
                    continue
                dy, dx = figs[i][0] - figs[b][0], figs[i][1] - figs[b][1]
                moved = ndi.binary_dilation(np.roll(np.roll(face[b], dy, 0), dx, 1), iterations=2) & boxes[i]
                rgb = art[:, c, :3]; lum = rgb.mean(-1)
                chroma = np.abs(rgb / np.maximum(lum[..., None], 1) - c0 / max(l0, 1)).max(-1)
                gate = (chroma < 0.11) & (lum > 0.5 * l0) & (lum < 1.5 * l0) & (art[:, c, 3] > 230)
                add = moved & gate & (sk[:, c, 3] <= 128)
                r = sk[:, c, 0]
                sk[:, c, 0] = np.where(add, np.clip(lum / max(l0, 1) * base, 0, 255), r)
                sk[:, c, 3] = np.where(add, 255, sk[:, c, 3])
    for c in cells:
        r = sk[:, c, 0]; a = sk[:, c, 3] / 255.0
        m = frame_mean(r, a)
        if m:
            r = np.clip(r * (base / m), 0, 255)
        sk[:, c, 0] = sk[:, c, 1] = sk[:, c, 2] = r
    Image.fromarray(sk.round().astype(np.uint8), "RGBA").save(skin_p)


def layer_base(paths):
    ms = []
    for p in paths:
        b = os.path.basename(p)
        if not b.startswith(("idle_", "walk_")):
            continue
        sk = np.array(Image.open(p).convert("RGBA")).astype(np.float32); ch = sk.shape[0]
        for i in range(max(1, sk.shape[1] // ch)):
            m = frame_mean(sk[:, i * ch:(i + 1) * ch, 0], sk[:, i * ch:(i + 1) * ch, 3] / 255.0)
            if m:
                ms.append(m)
    return float(np.median(ms)) if ms else None


def main(layers):
    for sex in ("male", "female"):
        for sc in ("1x", "2x", "4x"):
            for d in sorted(glob.glob(os.path.join(ROOT, sex, sc, "*"))):
                name = os.path.basename(d)
                if not (name.startswith(("outfit_", "armour_"))) or (layers and name not in layers):
                    continue
                mk = os.path.join(d, ".skin_stable")
                if os.path.exists(mk):
                    continue
                skins = sorted(glob.glob(os.path.join(d, "*_skin.png")))
                base = layer_base(skins) or layer_base(sorted(glob.glob(os.path.join(ROOT, sex, "2x", name, "*_skin.png"))))
                if not skins or not base:
                    continue
                for p in skins:
                    stabilise_strip(p, p[:-len("_skin.png")] + ".png", base)
                open(mk, "w").write(f"base {base:.1f}\n")
                print(sex, sc, name, len(skins), round(base, 1), flush=True)


if __name__ == "__main__":
    main(set(sys.argv[1:]))
