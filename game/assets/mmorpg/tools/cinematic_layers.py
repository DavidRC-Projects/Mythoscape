"""Build 2.5D layers for a cinematic key shot (offline, box tool).

For SHOT.jpg + SHOT_mask.png (subject matte from rembg) writes:
  SHOT_plate.jpg   background with the subjects painted out (inpaint)
  SHOT_fgL.png / SHOT_fgR.png   subject cut-outs split at column SPLIT (0..1) so the
                                 hero and the champion can move independently.
Usage: python tools/cinematic_layers.py DIR SHOT SPLIT [SHOT SPLIT ...]
"""
import sys, os
import cv2
import numpy as np


def build(d, shot, split):
    img = cv2.imread(os.path.join(d, shot + ".jpg"))
    m = cv2.imread(os.path.join(d, shot + "_mask.png"), cv2.IMREAD_GRAYSCALE)
    H, W = m.shape
    hard = (m > 60).astype(np.uint8) * 255
    grow = cv2.dilate(hard, np.ones((35, 35), np.uint8))
    small = cv2.resize(img, (W // 2, H // 2)); sm = cv2.resize(grow, (W // 2, H // 2))
    plate = cv2.inpaint(small, sm, 12, cv2.INPAINT_TELEA)
    plate = cv2.resize(cv2.GaussianBlur(plate, (0, 0), 2.5), (W, H))
    g = cv2.GaussianBlur(grow, (0, 0), 6)[..., None] / 255.0
    out = (img * (1 - g) + plate * g).astype(np.uint8)
    cv2.imwrite(os.path.join(d, shot + "_plate.jpg"), out, [cv2.IMWRITE_JPEG_QUALITY, 92])
    alpha = cv2.GaussianBlur(cv2.erode(m, np.ones((5, 5), np.uint8)), (0, 0), 0.9)  # tighter edge: no smudge halo when layers move
    rgba = np.dstack([img, alpha])
    sx = int(W * split)
    for tag, sl in (("L", slice(0, sx)), ("R", slice(sx, W))):
        part = np.zeros_like(rgba)
        part[:, sl] = rgba[:, sl]
        cv2.imwrite(os.path.join(d, f"{shot}_fg{tag}.png"), part)


if __name__ == "__main__":
    d = sys.argv[1]
    a = sys.argv[2:]
    for i in range(0, len(a), 2):
        build(d, a[i], float(a[i + 1]))
        print("built", a[i])
