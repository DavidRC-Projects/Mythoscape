import sys
from PIL import Image
paths = sys.argv[2:]; out = sys.argv[1]
ims = []
for p in paths:
    im = Image.open(p).convert("RGBA"); bg = Image.new("RGBA", im.size, (150, 150, 150, 255)); bg.alpha_composite(im); ims.append(bg)
w = sum(i.width for i in ims); h = max(i.height for i in ims)
sh = Image.new("RGBA", (w, h)); x = 0
for i in ims:
    sh.paste(i, (x, 0)); x += i.width
sh.save(out)
