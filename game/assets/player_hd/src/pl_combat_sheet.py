"""Combat preview: melee/ranged with anchors + contact/release markers, hit & death in 4 facings."""
import sys, json
sys.path.insert(0, "/workspace/player_hd/src")
from PIL import ImageDraw
import pl_previews as P
A = json.load(open("/workspace/player_hd/assets/anchors.json"))["anchors"]
M = json.load(open("/workspace/player_hd/assets/meta.json"))
BG = (150, 150, 150)
def tile(kind, L, anim, face, k, hair, tier, mark=None, dots=True, W=("wpn_sword",)):
    im = P.compose(kind, "2x", L, anim, face, k, hair=hair, tier=tier, bg=BG)
    if anim == "melee" and W:
        from PIL import Image as _I
        fp = f"/workspace/player_hd/assets/{kind}/2x/fx_swing_{W[0]}/melee_e.png"
        import os as _os
        if _os.path.exists(fp):
            fxs = _I.open(fp).convert("RGBA").crop((k * 288, 0, k * 288 + 288, 288))
            if face == "w": fxs = fxs.transpose(_I.FLIP_LEFT_RIGHT)
            im.alpha_composite(fxs)
    d = ImageDraw.Draw(im)
    if dots and face in ("e", "w") and anim in A[kind] and "e" in A[kind][anim]:
        a = A[kind][anim]["e"][k]
        fx = (lambda x: 288 - x) if face == "w" else (lambda x: x)
        pts = [("head_top", (255, 0, 0)), ("hand_L", (0, 120, 255)), ("hand_R", (0, 200, 0))]
        for n, c in pts:
            x, y = a[n]; d.ellipse((fx(x) - 3, y - 3, fx(x) + 3, y + 3), fill=c)
        for w, (x, y) in a.get("tip", {}).items():
            if w in W:
                d.ellipse((fx(x) - 3, y - 3, fx(x) + 3, y + 3), fill=(255, 220, 0))
    d.line((144 - 40, 248, 144 + 40, 248), fill=(0, 0, 0))   # 1-tile footprint (80 px at 2x)
    if mark: d.rectangle((1, 1, 286, 286), outline=(255, 40, 40), width=3); d.text((6, 4), mark, fill=(200, 0, 0))
    return im.crop((0, 40, 288, 288))
rows = []
for kind, li, hair, tier in (("male", 4, "dark_brown", "steel"), ("female", 3, "chestnut", "bronze")):
    L = P.resolve(kind, P.LOOKS[kind][li][1])
    t = [tile(kind, L, "melee", "e", k, hair, tier, "CONTACT 0.48" if k == 4 else None) for k in range(10)]
    rows.append(P.label(P.grid(t, 10, bg=BG, pad=0), f"{kind} melee e: frame 4 = strike_t 0.48 (hitsplat). dots: red head_top, green hand_R, blue hand_L, yellow sword tip"))
    for anim, n in (("hit", 4), ("death", 8)):
        t = [tile(kind, L, anim, f, k, hair, tier, dots=False) for f in ("s", "e", "n", "w") for k in range(n)]
        rows.append(P.label(P.grid(t, n * 2 if n == 4 else 8, bg=BG, pad=0), f"{kind} {anim} s/e/n/w"))
    if kind == "female":
        Ls = P.resolve(kind, P.LOOKS[kind][2][1])
        t = [tile(kind, Ls, "melee", "e", k, "blonde", "wood", "CONTACT 0.48" if k == 4 else None, W=("wpn_staff",)) for k in range(10)]
        rows.append(P.label(P.grid(t, 10, bg=BG, pad=0), "female mage melee e with staff (own layer) + swing smear"))
    Lb = P.resolve(kind, P.starter(kind, wpn=["wpn_bow"]))
    t = [tile(kind, Lb, "ranged", "e", k, P.D[kind]["hair_colour"], "wood", "RELEASE 0.55" if k == 5 else None, W=()) for k in range(8)]
    rows.append(P.label(P.grid(t, 8, bg=BG, pad=0), f"{kind} ranged e: frame 5 = arrow spawn 0.55; blue = hand_L arrow origin"))
from PIL import Image
W_ = max(r.width for r in rows); H_ = sum(r.height + 8 for r in rows) + 40
g = Image.new("RGBA", (W_, H_), BG + (255,)); y = 40
ImageDraw.Draw(g).text((8, 12), "HD player combat states (2x, black line = 1-tile footprint at feet anchor)", fill=(0, 0, 0))
for r in rows: g.alpha_composite(r.convert("RGBA"), (0, y)); y += r.height + 8
g = g.resize((g.width * 3 // 4, g.height * 3 // 4))
g.convert("RGB").save(f"{P.PV}/combat_states_2x.png", optimize=True)
print("combat", g.size)
