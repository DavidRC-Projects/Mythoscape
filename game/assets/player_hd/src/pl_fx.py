"""Swing smear (motion highlight) strips for melee contact frames, built in 2D from anchors.json.
Out: assets/<kind>/<2x|1x>/fx_swing_<weapon>/melee_e.png (10 frames; only frames 4 (contact) and 5 (trail) are non-empty)."""
import json, math, os
from PIL import Image, ImageDraw, ImageFilter
A = json.load(open("/workspace/player_hd/assets/anchors.json"))["anchors"]
OUT = "/workspace/player_hd/assets"
SS = 4; W = 288


def arc_poly(h0, t0, h1, t1, n=24, inner=0.62):
    a0 = math.atan2(t0[1] - h0[1], t0[0] - h0[0]); a1 = math.atan2(t1[1] - h1[1], t1[0] - h1[0])
    r0 = math.dist(h0, t0); r1 = math.dist(h1, t1)
    da = (a1 - a0 + math.pi) % (2 * math.pi) - math.pi
    if da < 0:     # swing is clockwise on screen (overhead -> forward-down) for east; keep the long way if needed
        pass
    outer, inn = [], []
    for i in range(n + 1):
        u = i / n
        a = a0 + da * u; r = r0 + (r1 - r0) * u
        hx = h0[0] + (h1[0] - h0[0]) * u; hy = h0[1] + (h1[1] - h0[1]) * u
        outer.append((hx + math.cos(a) * r, hy + math.sin(a) * r, u))
        inn.append((hx + math.cos(a) * r * inner, hy + math.sin(a) * r * inner, u))
    return outer, inn


def smear(frm, to, strength):
    im = Image.new("RGBA", (W * SS, W * SS), (0, 0, 0, 0))
    outer, inn = arc_poly(frm[0], frm[1], to[0], to[1])
    d = ImageDraw.Draw(im)
    n = len(outer) - 1
    for i in range(n):
        u = outer[i][2]
        al = int(255 * strength * (0.15 + 0.85 * u ** 1.6))
        quad = [(outer[i][0] * SS, outer[i][1] * SS), (outer[i + 1][0] * SS, outer[i + 1][1] * SS),
                (inn[i + 1][0] * SS, inn[i + 1][1] * SS), (inn[i][0] * SS, inn[i][1] * SS)]
        d.polygon(quad, fill=(255, 250, 235, al))
    # bright leading edge line along the outer rim
    d.line([(p[0] * SS, p[1] * SS) for p in outer[n // 2:]], fill=(255, 255, 255, int(255 * strength)), width=2 * SS)
    im = im.filter(ImageFilter.GaussianBlur(SS * 0.8))
    return im.resize((W, W), Image.LANCZOS)


def main():
    made = []
    for kind in A:
        fr = A[kind]["melee"]["e"]
        weps = list(fr[0]["tip"].keys())
        for w in weps:
            hand = [tuple(f["hand_R"]) for f in fr]; tip = [tuple(f["tip"][w]) for f in fr]
            frames = [Image.new("RGBA", (W, W), (0, 0, 0, 0)) for _ in fr]
            frames[4] = smear((hand[3], tip[3]), (hand[4], tip[4]), 0.55)
            tr = smear((hand[3], tip[3]), (hand[4], tip[4]), 0.18)
            frames[5] = Image.alpha_composite(tr, smear((hand[4], tip[4]), (hand[5], tip[5]), 0.25))
            strip = Image.new("RGBA", (W * len(fr), W), (0, 0, 0, 0))
            for i, f in enumerate(frames):
                strip.paste(f, (i * W, 0))
            for sc, div in (("2x", 1), ("1x", 2)):
                d = f"{OUT}/{kind}/{sc}/fx_swing_{w}"; os.makedirs(d, exist_ok=True)
                s2 = strip if div == 1 else strip.resize((strip.width // 2, W // 2), Image.LANCZOS)
                s2.save(f"{d}/melee_e.png", optimize=True)
            made.append(f"{kind}/{w}")
    print("[fx] made", made)


if __name__ == "__main__":
    main()
