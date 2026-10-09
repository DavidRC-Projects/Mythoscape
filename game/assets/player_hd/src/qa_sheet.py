import sys, glob
from PIL import Image, ImageDraw
pat, out, cols = sys.argv[1], sys.argv[2], int(sys.argv[3])
fs = sorted(glob.glob(pat))
ims = [Image.open(f).convert("RGBA") for f in fs]
w, h = ims[0].size
sc = 0.5 if len(sys.argv) < 5 else float(sys.argv[4])
W, Hh = int(w * sc), int(h * sc)
rows = (len(ims) + cols - 1) // cols
sheet = Image.new("RGBA", (W * cols, (Hh + 14) * rows), (150, 150, 150, 255))
d = ImageDraw.Draw(sheet)
for i, (f, im) in enumerate(zip(fs, ims)):
    x, y = (i % cols) * W, (i // cols) * (Hh + 14)
    sheet.alpha_composite(im.resize((W, Hh), Image.LANCZOS), (x, y + 14))
    d.text((x + 3, y + 1), f.split("/")[-1].replace(".png", "")[-28:], fill=(0, 0, 0, 255))
sheet.convert("RGB").save(out)
print(out, sheet.size)
