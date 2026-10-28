"""Build *_hair.png ratio masks for starter painted outfits (Villager / Village Lady).

RGB = shade ratio * 128 (grey), A = hair. Same contract as bare-head armour hair strips
and skin masks, so player_hd_client._skin_whole can recolour hair.

For idle/walk loops, the best-covered frame's hair mask is moved with the head into
sparse frames (mirrors skin_stabilise hole-fill) so walk never flashes baked hair.

Idempotent: writes a .hair_mask marker per layer folder.
Run: python3 tools/hair_mask_build.py
"""
from __future__ import annotations

import glob
import os
import sys
from collections import deque

import numpy as np
from PIL import Image
from scipy import ndimage as ndi

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "player_hd", "assets")

STARTERS = (
    ("male", "outfit_villager_hd", False),
    ("female", "outfit_village_lady_hd", True),
)

SCALES = ("1x", "2x", "4x")


def _figure(alpha):
    ys, xs = np.nonzero(alpha > 128)
    if not len(ys):
        return None
    top, bot = int(ys.min()), int(ys.max())
    H = bot - top
    band = xs[ys < top + max(3, int(0.05 * H))]
    return top, int(round(band.mean())), H


def _segment_frame(frame: np.ndarray, skin: np.ndarray, female: bool) -> np.ndarray:
    """Boolean hair mask for one square frame (H,H,4) + matching skin mask."""
    ch = frame.shape[0]
    fig = _figure(frame[:, :, 3])
    if fig is None:
        return np.zeros((ch, ch), dtype=bool)
    top, cx, H = fig
    yy, xx = np.mgrid[0:ch, 0:ch]
    h_bot = 0.18 * H if not female else 0.38 * H
    h_rad = 0.12 * H if not female else 0.16 * H
    head = (yy >= top - 3) & (yy <= top + h_bot) & (np.abs(xx - cx) <= h_rad) & (frame[:, :, 3] > 160)
    not_skin = skin[:, :, 3] < 120
    rgb = frame[:, :, :3].astype(np.float32)
    r, g, b = rgb[:, :, 0], rgb[:, :, 1], rgb[:, :, 2]
    lum = rgb.mean(-1)
    greenish = (g > r + 8) & (g > b + 5) & (g > 40)
    pale = (lum > 135) & (np.max(np.abs(rgb - lum[..., None]), -1) < 30)
    cloth = (
        ((g >= r - 5) & (g >= b) & (lum > 40) & (lum < 130) & (g > 55))
        | ((np.abs(r - g) < 20) & (b < r - 15) & (lum > 45) & (lum < 100) & (yy > top + 0.18 * H))
    )
    hairish = (
        (~greenish) & (~pale) & (~cloth)
        & (lum >= 10) & (lum <= 125)
        & (b <= r + 18) & (np.abs(r - g) < 50)
    )
    cand = head & not_skin & hairish
    crown = cand & (yy <= top + 0.10 * H)
    if not crown.any():
        crown = cand & (yy <= top + 0.14 * H)
    vis = np.zeros_like(cand)
    q = deque(zip(*np.where(crown)))
    for y, x in q:
        vis[y, x] = True
    while q:
        y, x = q.popleft()
        for dy, dx in ((-1, 0), (1, 0), (0, -1), (0, 1), (-1, -1), (-1, 1), (1, -1), (1, 1)):
            ny, nx = y + dy, x + dx
            if 0 <= ny < ch and 0 <= nx < ch and cand[ny, nx] and not vis[ny, nx]:
                vis[ny, nx] = True
                q.append((ny, nx))
    keep = ndi.binary_closing(vis, iterations=1)
    return ndi.binary_fill_holes(keep)


def _encode_hair(frame: np.ndarray, mask: np.ndarray, base_lum: float) -> np.ndarray:
    """RGBA hair strip cell: grey ratio*128, A from mask."""
    out = np.zeros(frame.shape, dtype=np.uint8)
    if not mask.any() or base_lum <= 1e-3:
        return out
    lum = frame[:, :, :3].astype(np.float32).mean(-1)
    ratio = np.clip(lum / base_lum * 128.0, 0, 255)
    soft = ndi.distance_transform_edt(mask)
    alpha = np.where(mask, np.clip(soft / 1.2 * 255.0, 40, 255), 0.0)
    # feather outer ring slightly lower
    edge = mask & (soft <= 1.5)
    alpha = np.where(edge, np.minimum(alpha, 200), alpha)
    g = ratio.astype(np.uint8)
    out[:, :, 0] = out[:, :, 1] = out[:, :, 2] = g
    out[:, :, 3] = alpha.astype(np.uint8)
    out[~mask, 3] = 0
    return out


def _strip_cells(arr: np.ndarray):
    ch = arr.shape[0]
    n = max(1, arr.shape[1] // ch)
    return ch, n, [slice(i * ch, (i + 1) * ch) for i in range(n)]


def _stabilize_loop(hair: np.ndarray, art: np.ndarray, female: bool) -> np.ndarray:
    """Move best-frame hair into sparse idle/walk frames using head motion."""
    ch, n, cells = _strip_cells(hair)
    if n <= 1:
        return hair
    figs = [_figure(art[:, c, 3]) for c in cells]
    counts = [int((hair[:, c, 3] > 40).sum()) for c in cells]
    b = int(np.argmax(counts))
    if counts[b] < 12 or figs[b] is None:
        return hair
    out = hair.copy()
    for i, c in enumerate(cells):
        if figs[i] is None or counts[i] >= 0.75 * counts[b]:
            continue
        dy = figs[i][0] - figs[b][0]
        dx = figs[i][1] - figs[b][1]
        src = hair[:, cells[b], :]
        moved = np.roll(np.roll(src, dy, 0), dx, 1)
        # Only keep moved hair on non-skin-looking opaque figure pixels in head band
        fig = figs[i]
        top, cx, H = fig
        yy, xx = np.mgrid[0:ch, 0:ch]
        h_bot = 0.18 * H if not female else 0.38 * H
        h_rad = 0.12 * H if not female else 0.16 * H
        head = (yy >= top - 3) & (yy <= top + h_bot) & (np.abs(xx - cx) <= h_rad)
        gate = head & (art[:, c, 3] > 180) & (moved[:, :, 3] > 40)
        weak = out[:, c, 3] <= 40
        add = gate & weak
        for k in range(4):
            plane = out[:, c, k]
            plane = np.where(add, moved[:, :, k], plane)
            out[:, c, k] = plane
    return out


def build_strip(art_path: str, skin_path: str, out_path: str, female: bool, stabilize: bool) -> int:
    art = np.array(Image.open(art_path).convert("RGBA"))
    skin = (
        np.array(Image.open(skin_path).convert("RGBA"))
        if os.path.isfile(skin_path)
        else np.zeros_like(art)
    )
    if skin.shape != art.shape:
        skin = np.zeros_like(art)
    ch, n, cells = _strip_cells(art)
    masks = []
    lums = []
    for c in cells:
        m = _segment_frame(art[:, c], skin[:, c], female)
        masks.append(m)
        if m.any():
            lums.append(float(art[:, c, :3][m].mean()))
    base_lum = float(np.median(lums)) if lums else 40.0
    hair = np.zeros_like(art)
    total = 0
    for i, c in enumerate(cells):
        cell = _encode_hair(art[:, c], masks[i], base_lum)
        hair[:, c] = cell
        total += int((cell[:, :, 3] > 40).sum())
    if stabilize:
        hair = _stabilize_loop(hair, art, female)
        total = int((hair[:, :, 3] > 40).sum())
    # Never let hair mask cover skin (face / neck / hands) — colour must stay on hair.
    if skin.shape == hair.shape:
        ch, n, cells = _strip_cells(hair)
        for c in cells:
            kill = (hair[:, c, 3] > 40) & (skin[:, c, 3] > 60)
            hair[:, c, 3] = np.where(kill, 0, hair[:, c, 3])
        total = int((hair[:, :, 3] > 40).sum())
    Image.fromarray(hair, "RGBA").save(out_path)
    return total


def _upscale_4x_idle_from_2x(sex: str, layer: str) -> int:
    """Shop portraits are 4x single-frame idle — derive hair from 2x frame 0 (more reliable)."""
    d2 = os.path.join(ROOT, sex, "2x", layer)
    d4 = os.path.join(ROOT, sex, "4x", layer)
    if not os.path.isdir(d4):
        return 0
    wrote = 0
    for art4 in sorted(glob.glob(os.path.join(d4, "idle_*.png"))):
        if art4.endswith(("_skin.png", "_hair.png")):
            continue
        stem = os.path.basename(art4)[:-4]
        h2 = os.path.join(d2, stem + "_hair.png")
        if not os.path.isfile(h2):
            continue
        hair2 = Image.open(h2).convert("RGBA")
        art4im = Image.open(art4).convert("RGBA")
        ch = hair2.size[1]
        f0 = hair2.crop((0, 0, ch, ch)).resize(art4im.size, Image.Resampling.LANCZOS)
        a = np.array(f0)
        art = np.array(art4im)
        mask = a[:, :, 3] > 40
        if not mask.any():
            continue
        lum = art[:, :, :3].astype(np.float32).mean(-1)
        base_lum = float(np.median(lum[mask])) or 40.0
        ratio = np.clip(lum / base_lum * 128.0, 0, 255).astype(np.uint8)
        out = np.zeros_like(art)
        out[:, :, 0] = out[:, :, 1] = out[:, :, 2] = ratio
        out[:, :, 3] = a[:, :, 3]
        out[~mask, 3] = 0
        out_p = os.path.join(d4, stem + "_hair.png")
        Image.fromarray(out, "RGBA").save(out_p)
        print(f"  {sex}/4x/{layer}/{stem}_hair.png <- 2x f0 px={int(mask.sum())}")
        wrote += 1
    open(os.path.join(d4, ".hair_mask"), "w").write("ok\n")
    return wrote


def process_layer(sex: str, layer: str, female: bool, scale: str) -> int:
    d = os.path.join(ROOT, sex, scale, layer)
    if not os.path.isdir(d):
        print("skip missing", d)
        return 0
    if scale == "4x":
        return _upscale_4x_idle_from_2x(sex, layer)
    marker = os.path.join(d, ".hair_mask")
    mains = sorted(
        p for p in glob.glob(os.path.join(d, "*.png"))
        if not p.endswith(("_skin.png", "_hair.png", "_tint.png"))
        and "anchors" not in os.path.basename(p)
    )
    wrote = 0
    for art_p in mains:
        stem = art_p[:-4]
        skin_p = stem + "_skin.png"
        out_p = stem + "_hair.png"
        base = os.path.basename(art_p)
        stabilize = base.startswith(("idle_", "walk_"))
        px = build_strip(art_p, skin_p, out_p, female, stabilize)
        print(f"  {sex}/{scale}/{layer}/{base} -> hair px {px}")
        wrote += 1
    open(marker, "w").write("ok\n")
    return wrote


def main(argv=None):
    argv = argv or sys.argv[1:]
    only = set(argv) if argv else None
    total = 0
    for sex, layer, female in STARTERS:
        if only and layer not in only and sex not in only:
            continue
        for scale in SCALES:
            print(f"=== {sex}/{scale}/{layer} ===")
            total += process_layer(sex, layer, female, scale)
    print(f"done: {total} strips")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
