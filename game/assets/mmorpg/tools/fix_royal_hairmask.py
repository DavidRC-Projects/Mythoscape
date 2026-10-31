"""King/Queen crown-free heads (David, 29 Oct 2026): where the crown was repainted as hair, the masks still
called some of it skin and left holes in the hair mask, so a skin tone / hair colour showed a crown-shaped
patch. In the old crown's rows: dark (hair) pixels leave the skin mask and join the hair mask, with a shade
ratio from their own brightness. Face pixels are untouched. Run after tools/build_royal_faces.py."""
import os
import numpy as np
from PIL import Image
HERE = os.path.dirname(os.path.abspath(__file__))
ART = os.path.join(HERE, "..", "..", "player_hd", "assets")
FACES = os.path.join(ART, "faces")
ROYAL = (("male", "king", "kings_crown"), ("female", "queen", "queens_crown"))


def _load(p):
    return np.array(Image.open(p).convert("RGBA")).astype(np.float32)


def fix(sex, fid, cid):
    for tag in ("1x", "2x", "4x"):
        d = os.path.join(FACES, sex, fid, tag)
        for facing in ("s", "e", "n"):
            hp, sp, kp = (os.path.join(d, f"{k}_{facing}.png") for k in ("hair", "skin", "head"))
            cp = os.path.join(ART, "crowns", cid, tag, f"crown_{facing}.png")
            if not all(os.path.exists(p) for p in (hp, sp, kp, cp)):
                continue
            head, hair, skin, crown = _load(kp), _load(hp), _load(sp), _load(cp)
            if crown.shape[:2] != head.shape[:2]:
                continue
            crows = np.where((crown[..., 3] > 40).any(1))[0]
            if not len(crows):
                continue
            zone = np.zeros(head.shape[:2], bool)
            zone[:int(crows[-1]) + max(2, head.shape[0] // 60)] = True
            ha, lum = head[..., 3], head[..., :3].mean(2)
            hairy = zone & (ha > 20) & ((lum < 110) | (facing == "n"))
            # shade ratio: this pixel's brightness against the hair's typical painted brightness
            known = (hair[..., 3] > 60) & (ha > 100) & ~zone
            if not known.any():
                known = (hair[..., 3] > 60) & (ha > 100)
            kr = np.maximum(hair[..., :3].mean(2)[known] / 128.0, 0.05)
            base = float(np.median(lum[known] / kr)) if known.any() else 60.0
            val = float(np.median(hair[..., 3][known])) if known.any() else 200.0
            r = np.clip(lum / max(base, 1.0) * 128.0, 0, 255)
            add = hairy & (hair[..., 3] < val * 0.8)
            for c in range(3):
                hair[..., c] = np.where(add, r, hair[..., c])
            hair[..., 3] = np.where(add, val * ha / 255.0, hair[..., 3])
            skin[..., 3] = np.where(hairy, 0, skin[..., 3])
            # the old masks' shade ratios there were painted for the crown, not the new hair: take the ratio
            # from the repainted head's own brightness (same scale as the hair below), blended in over 3 rows
            hz = zone & (hair[..., 3] > 20) & ((lum < 110) | (facing == "n"))
            from scipy import ndimage
            wz = ndimage.gaussian_filter(hz.astype(np.float32), 1.0)
            wz = np.where(hz, np.maximum(wz, 0.6), wz * (hair[..., 3] > 20))
            for c in range(3):
                hair[..., c] = hair[..., c] * (1 - wz) + r * wz
            Image.fromarray(np.clip(hair, 0, 255).astype(np.uint8)).save(hp)
            Image.fromarray(np.clip(skin, 0, 255).astype(np.uint8)).save(sp)
            print(sex, fid, tag, facing, "hair px added", int(add.sum()), "skin px removed", int(hairy.sum()))


if __name__ == "__main__":
    for row in ROYAL:
        fix(*row)
