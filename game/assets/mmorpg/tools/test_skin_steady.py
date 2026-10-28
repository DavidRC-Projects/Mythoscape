"""Skin stays steady across walk frames on every painted figure (David, 23 Oct 2026).
Tints each walk strip with a mid skin tone the way the client does and checks frame-to-frame drift of the
tinted skin colour, plus that the face never drops out of the mask in a frame."""
import glob, os, sys
import numpy as np
from PIL import Image
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
try:
    import skin_stabilise as S
except ModuleNotFoundError as exc:
    if "scipy" in str(exc):
        print("skip test_skin_steady (scipy not installed; optional asset-pipeline dep)")
        raise SystemExit(0) from exc
    raise

TONE = np.array([196, 150, 118], np.float32)
MAX_DRIFT = 0.02       # tinted skin mean, per frame vs the strip median
MIN_FACE = 0.35        # face pixels per frame vs the best frame


def _strips():
    for p in sorted(glob.glob(os.path.join(S.ROOT, "male", "2x", "*", "walk_*_skin.png")) + glob.glob(os.path.join(S.ROOT, "female", "2x", "*", "walk_*_skin.png"))):
        layer = p.split(os.sep)[-2]
        if layer.startswith(("outfit_", "armour_")):
            yield p


def test_tinted_skin_drift():
    bad = []
    for p in _strips():
        sk = np.array(Image.open(p).convert("RGBA")).astype(np.float32); ch = sk.shape[0]
        ms = []
        for i in range(sk.shape[1] // ch):
            c = sk[:, i * ch:(i + 1) * ch]; w = c[..., 3] / 255.0
            if w.sum() > 4:
                ms.append(float(((TONE * c[..., :1] / 128.0).mean(-1) * w).sum() / w.sum()))
        if ms:
            med = np.median(ms); d = max(abs(m - med) for m in ms) / med
            if d > MAX_DRIFT:
                bad.append((p, round(d, 3)))
    assert not bad, bad


def test_face_never_drops_out():
    bad = []
    for p in _strips():
        art = np.array(Image.open(p[:-9] + ".png").convert("RGBA")); sk = np.array(Image.open(p).convert("RGBA"))
        ch = sk.shape[0]; cnt = []
        for i in range(sk.shape[1] // ch):
            s = slice(i * ch, (i + 1) * ch); f = S._figure(art[:, s, 3])
            cnt.append(int(((sk[:, s, 3] > 128) & S._head_box((ch, ch), f)).sum()) if f else 0)
        if max(cnt) > 12 and min(cnt) < MIN_FACE * max(cnt):
            bad.append((p.split(os.sep)[-4] + "/" + p.split(os.sep)[-2] + "/" + os.path.basename(p), round(min(cnt) / max(cnt), 2)))
    assert not bad, bad


if __name__ == "__main__":
    tests = [(n, f) for n, f in sorted(globals().items()) if n.startswith("test_")]
    fails = 0
    for n, f in tests:
        try:
            f(); print("ok  ", n)
        except AssertionError as e:
            fails += 1; print("FAIL", n, e)
    print(f"{len(tests) - fails}/{len(tests)} skin steady tests passed")
    sys.exit(1 if fails else 0)
