import sys, os
import numpy as np
from PIL import Image
sys.path.insert(0, "/workspace/player_hd/src")
from pl_post import split, to_img
R = "/workspace/player_hd/renders"
def comp(kind, layers, anim, face, k, tints, scale="2x", bg=(150, 150, 150)):
    W, H = (192, 256) if scale == "2x" else (384, 512)
    out = Image.new("RGBA", (W, H), bg + (255,))
    for lid in layers:
        p = f"{R}/{kind}/{scale}/{lid}/{anim}_{face}_{k:02d}.png"
        if not os.path.exists(p):
            continue
        fx, tn = split(p)
        out.alpha_composite(to_img(fx))
        if tn is not None:
            c = np.array(tints.get(lid, (1, 1, 1)) + (1,), np.float32)
            out.alpha_composite(to_img(tn * c))
    return out
if __name__ == "__main__":
    kind = sys.argv[1]; layers = sys.argv[2].split(","); out = sys.argv[3]
    frames = [tuple(x.split(":")) for x in sys.argv[4].split(",")]
    hair = (0.55, 0.32, 0.16); steel = (170/255*1.15, 175/255*1.15, 185/255*1.15)
    tints = {l: (hair if l.startswith("hair") or l == "brows" else steel) for l in layers}
    ims = [comp(kind, layers, a, f, int(k), tints) for a, f, k in frames]
    sheet = Image.new("RGBA", (192 * len(ims), 256))
    for i, im in enumerate(ims):
        sheet.paste(im, (192 * i, 0))
    sheet = sheet.resize((sheet.width * 2, 512), Image.NEAREST)
    sheet.save(out); print(out)
