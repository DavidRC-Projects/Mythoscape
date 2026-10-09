import sys, glob, os
from PIL import Image
key = sys.argv[1]; sub = sys.argv[2] if len(sys.argv) > 2 else "test"
base = f"/workspace/knights_hd/renders/{key}/{sub}"
files = []
for f in ("s", "e", "n", "w"):
    for st in ("idle", "walk", "attack"):
        files += sorted(glob.glob(f"{base}/{st}/{f}/f*.png"))
ims = [Image.open(p).convert("RGBA") for p in files]
w, h = ims[0].size
cols = min(len(ims), 10); rows = (len(ims) + cols - 1) // cols
sheet = Image.new("RGBA", (w * cols, h * rows), (150, 150, 150, 255))
for i, im in enumerate(ims):
    bg = Image.new("RGBA", im.size, (150, 150, 150, 255)); bg.alpha_composite(im)
    sheet.paste(bg, ((i % cols) * w, (i // cols) * h))
out = f"/workspace/knights_hd/work/{key}_{sub}.png"; sheet.save(out); print(out, len(ims))
