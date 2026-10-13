import sys
from PIL import Image
W = "/workspace/fairy_village/work/ground"
names = sys.argv[1:]
rows = []
for n in names:
    im = Image.open(f"{W}/{n}_render.png").convert("RGB")
    t160 = im.resize((160, 160), Image.LANCZOS); t40 = im.resize((40, 40), Image.LANCZOS)
    a = Image.new("RGB", (480, 480)); b = Image.new("RGB", (240, 240))
    for i in range(3):
        for j in range(3): a.paste(t160, (i * 160, j * 160))
    for i in range(6):
        for j in range(6): b.paste(t40, (i * 40, j * 40))
    b = b.resize((480, 480), Image.NEAREST)
    r = Image.new("RGB", (960 + 8, 480), (20, 20, 20)); r.paste(a, (0, 0)); r.paste(b, (488, 0)); rows.append(r)
out = Image.new("RGB", (968, 480 * len(rows) + 8 * len(rows)), (20, 20, 20))
for k, r in enumerate(rows): out.paste(r, (0, k * 488))
import time; fn = "/tmp/peek_%d.png" % int(time.time()); out.save(fn); print(fn)
