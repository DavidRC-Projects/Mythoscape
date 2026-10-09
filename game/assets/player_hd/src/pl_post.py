"""Post: raw frames -> strips (2x, 1x) + 4x portrait frames, tint split via AOV mask, meta + catalogue JSON.
python3 pl_post.py [kind ...]"""
import os, sys, json, glob, re
import numpy as np
from PIL import Image

RAW = "/workspace/player_hd/renders"
OUT = "/workspace/player_hd/assets"
CAT = json.load(open("/workspace/player_hd/work/catalog_raw.json"))
ANIMS = CAT["anims"]
QUANT = os.environ.get("PL_QUANT", "1") == "1"


def split(png):
    im = np.asarray(Image.open(png).convert("RGBA")).astype(np.float32) / 255.0
    mp = png[:-4] + "_m.png"
    if not os.path.exists(mp):
        return im, None
    m = np.asarray(Image.open(mp).convert("L")).astype(np.float32) / 255.0
    a = im[..., 3]
    mm = np.where(a > 0.004, np.clip(m / np.maximum(a, 1e-3), 0, 1), 0.0)
    fixed = im.copy(); fixed[..., 3] = a * (1 - mm)
    tint = im.copy(); tint[..., 3] = a * mm
    return fixed, tint


def to_img(arr):
    return Image.fromarray(np.clip(arr * 255 + 0.5, 0, 255).astype(np.uint8), "RGBA")


def save(img, path):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    if QUANT:
        # 256-colour RGBA palette (libimagequant-style) keeps sprite strips small; alpha preserved
        q = img.quantize(colors=256, method=Image.Quantize.FASTOCTREE, dither=Image.Dither.FLOYDSTEINBERG)
        q.save(path, optimize=True)
    else:
        img.save(path, optimize=True)


def nonempty(arr):
    return arr is not None and float(arr[..., 3].max()) > 0.03


def process(kind):
    report = {}
    for scale in ("2x", "4x"):
        base = f"{RAW}/{kind}/{scale}"
        if not os.path.isdir(base):
            continue
        for lid in sorted(os.listdir(base)):
            ld = f"{base}/{lid}"
            if not os.path.exists(f"{ld}/DONE"):
                print("[post] skip unfinished", kind, scale, lid); continue
            info = report.setdefault(lid, {"anims": {}, "fixed": False, "tint": False})
            groups = {}
            for f in os.listdir(ld):
                mt = re.match(r"(\w+?)_([sen])_(\d\d)\.png$", f)
                if mt:
                    groups.setdefault((mt.group(1), mt.group(2)), []).append((int(mt.group(3)), f"{ld}/{f}"))
            for (anim, face), lst in sorted(groups.items()):
                lst.sort()
                parts = [split(p) for _, p in lst]
                fx = [p[0] for p in parts]; tn = [p[1] for p in parts]
                has_t = any(nonempty(t) for t in tn if t is not None)
                has_f = any(nonempty(x) for x in fx)
                info["fixed"] |= has_f; info["tint"] |= has_t
                info["anims"].setdefault(anim, set()).add(face)
                for tag, arrs, ok in (("", fx, has_f), ("_tint", tn, has_t)):
                    if not ok:
                        continue
                    strip = np.concatenate(arrs, axis=1)
                    img = to_img(strip)
                    if scale == "4x":
                        save(img, f"{OUT}/{kind}/4x/{lid}/{anim}_{face}{tag}.png")
                    else:
                        save(img, f"{OUT}/{kind}/2x/{lid}/{anim}_{face}{tag}.png")
                        w, h = img.size
                        save(img.resize((w // 2, h // 2), Image.LANCZOS), f"{OUT}/{kind}/1x/{lid}/{anim}_{face}{tag}.png")
    for v in report.values():
        v["anims"] = {a: sorted(f) for a, f in v["anims"].items()}
    return report


def main():
    kinds = sys.argv[1:] or ["male", "female"]
    layers = {}
    for k in kinds:
        layers[k] = process(k)
    json.dump(layers, open("/workspace/player_hd/work/post_report.json", "w"), indent=1)
    print("[post] done", {k: len(v) for k, v in layers.items()})


if __name__ == "__main__":
    main()
