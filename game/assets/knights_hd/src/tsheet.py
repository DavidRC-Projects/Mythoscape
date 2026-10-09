import sys
from PIL import Image
keys = sys.argv[2:]; out = sys.argv[1]
rows = []
for k in keys:
    ims = []
    for f in ("s", "e"):
        for st, i in (("idle", 0), ("walk", 2), ("attack", 1), ("attack", 3)):
            im = Image.open(f"/workspace/knights_hd/renders/{k}/test/{st}/{f}/f{i:02d}.png").convert("RGBA")
            bg = Image.new("RGBA", im.size, (150, 150, 150, 255)); bg.alpha_composite(im); ims.append(bg.crop((30, 40, 226, 288)))
    w = sum(i.width for i in ims); r = Image.new("RGBA", (w, ims[0].height)); x = 0
    for i in ims:
        r.paste(i, (x, 0)); x += i.width
    rows.append(r)
sh = Image.new("RGBA", (rows[0].width, sum(r.height for r in rows))); y = 0
for r in rows:
    sh.paste(r, (0, y)); y += r.height
sh.save(out)
